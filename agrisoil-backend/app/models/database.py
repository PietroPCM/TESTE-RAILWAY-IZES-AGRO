"""
Modelos SQLAlchemy para persistência no banco de dados
Inclui entidades do Smart Data Models para agricultura completa
"""
from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Integer, Text, JSON, Enum, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db import Base
import enum


# Enums para alertas
class SeveridadeAlerta(str, enum.Enum):
    CRITICO = "critico"
    ALTO = "alto"
    MEDIO = "medio"
    BAIXO = "baixo"


class StatusAlerta(str, enum.Enum):
    ATIVO = "ativo"
    RECONHECIDO = "reconhecido"
    RESOLVIDO = "resolvido"
    IGNORADO = "ignorado"


class TipoAlerta(str, enum.Enum):
    PH = "ph"
    UMIDADE = "umidade"
    TEMPERATURA = "temperatura"
    NITROGENIO = "nitrogenio"
    FOSFORO = "fosforo"
    POTASSIO = "potassio"
    CONDUTIVIDADE = "condutividade"
    SISTEMA = "sistema"


class SensorDB(Base):
    """Tabela de sensores"""
    __tablename__ = "sensores"
    __table_args__ = (
        Index("ix_sensores_cliente_ativo", "cliente_id", "ativo"),
        Index("ix_sensores_cliente_local", "cliente_id", "local_especifico"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    sensor_id = Column(String(100), unique=True, index=True, nullable=False)
    cliente_id = Column(String(100), index=True, nullable=False)
    nome = Column(String(200), nullable=False)
    tipo = Column(String(50), default="solo")  # solo, ar, água
    ativo = Column(Boolean, default=True)
    
    # Localização
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    propriedade = Column(String(200), nullable=True)
    municipio = Column(String(100), nullable=True)
    estado = Column(String(50), nullable=True)
    local_especifico = Column(String(200), nullable=True)
    
    # Metadados
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    leituras = relationship("LeituraDB", back_populates="sensor", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Sensor {self.sensor_id} - {self.nome}>"


class LeituraDB(Base):
    """Tabela de leituras de sensores"""
    __tablename__ = "leituras"
    __table_args__ = (
        Index("ix_leituras_cliente_sensor_timestamp", "cliente_id", "sensor_id", "timestamp"),
        Index("ix_leituras_cliente_alerta_timestamp", "cliente_id", "alerta_ativo", "timestamp"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    sensor_id = Column(String(100), ForeignKey("sensores.sensor_id"), nullable=False, index=True)
    cliente_id = Column(String(100), index=True, nullable=False)
    
    # Valores lidos
    ph = Column(Float, nullable=True)
    umidade = Column(Float, nullable=True)  # soilMoisture
    temperatura = Column(Float, nullable=True)
    condutividade = Column(Float, nullable=True)  # electricalConductivity
    
    # Macronutrientes NPK (mg/kg ou ppm)
    nitrogenio = Column(Float, nullable=True)  # Nitrogênio (N)
    fosforo = Column(Float, nullable=True)  # Fósforo (P)
    potassio = Column(Float, nullable=True)  # Potássio (K)
    
    # Avaliações do motor de regras
    ph_nivel = Column(String(20), nullable=True)  # critico, alerta, ok
    ph_mensagem = Column(Text, nullable=True)
    umidade_nivel = Column(String(20), nullable=True)
    umidade_mensagem = Column(Text, nullable=True)
    temperatura_nivel = Column(String(20), nullable=True)
    temperatura_mensagem = Column(Text, nullable=True)
    
    # Avaliações NPK
    nitrogenio_nivel = Column(String(20), nullable=True)
    nitrogenio_mensagem = Column(Text, nullable=True)
    fosforo_nivel = Column(String(20), nullable=True)
    fosforo_mensagem = Column(Text, nullable=True)
    potassio_nivel = Column(String(20), nullable=True)
    potassio_mensagem = Column(Text, nullable=True)
    
    alerta_ativo = Column(Boolean, default=False)
    nivel_critico = Column(Boolean, default=False)
    
    # Metadados
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relacionamentos
    sensor = relationship("SensorDB", back_populates="leituras")
    alertas = relationship("AlertaDB", back_populates="leitura", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Leitura {self.sensor_id} - {self.timestamp}>"


class AlertaDB(Base):
    """Tabela de alertas - histórico e gestão de alertas"""
    __tablename__ = "alertas"
    __table_args__ = (
        Index("ix_alertas_cliente_status_criado", "cliente_id", "status", "criado_em"),
        Index("ix_alertas_cliente_severidade_tipo", "cliente_id", "severidade", "tipo"),
        Index("ux_alertas_hash_deduplicacao", "hash_deduplicacao", unique=True),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Relacionamentos
    sensor_id = Column(String(100), ForeignKey("sensores.sensor_id"), nullable=False, index=True)
    cliente_id = Column(String(100), index=True, nullable=False)
    leitura_id = Column(Integer, ForeignKey("leituras.id"), nullable=True)
    
    # Classificação
    tipo = Column(Enum(TipoAlerta), nullable=False, index=True)
    severidade = Column(Enum(SeveridadeAlerta), nullable=False, index=True)
    status = Column(Enum(StatusAlerta), default=StatusAlerta.ATIVO, nullable=False, index=True)
    
    # Conteúdo
    titulo = Column(String(200), nullable=False)
    mensagem = Column(Text, nullable=False)
    valor_medido = Column(Float, nullable=True)
    valor_referencia = Column(String(100), nullable=True)
    recomendacao = Column(Text, nullable=True)
    
    # Gestão
    notificacao_enviada = Column(Boolean, default=False)
    reconhecido_em = Column(DateTime, nullable=True)
    resolvido_em = Column(DateTime, nullable=True)
    observacao = Column(Text, nullable=True)
    
    # Hash para deduplicação (sensor_id + tipo + severidade + dia)
    hash_deduplicacao = Column(String(64), index=True, nullable=True)
    
    # Metadados
    criado_em = Column(DateTime, default=datetime.utcnow, index=True)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    sensor = relationship("SensorDB")
    leitura = relationship("LeituraDB", back_populates="alertas")
    
    def __repr__(self):
        return f"<Alerta {self.id} - {self.tipo} - {self.severidade} - {self.status}>"


class UsuarioDB(Base):
    """Tabela de usuários"""
    __tablename__ = "usuarios"
    __table_args__ = (
        Index("ix_usuarios_cliente_role_ativo", "cliente_id", "role", "ativo"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(200), unique=True, index=True, nullable=False)
    nome = Column(String(200), nullable=False)
    senha_hash = Column(String(200), nullable=False)
    cliente_id = Column(String(100), index=True, nullable=False)
    role = Column(String(50), nullable=False, default="viewer")  # admin, gestor, produtor, tecnico, viewer
    ativo = Column(Boolean, default=True)
    
    # Firebase Cloud Messaging (FCM) tokens para push notifications
    fcm_tokens = Column(JSON, nullable=True, default=list)  # Lista de tokens de dispositivos
    
    # Preferências de notificação (JSON)
    preferencias_notificacao = Column(JSON, nullable=True, default={
        "email_ativo": True,
        "push_ativo": True,
        "email_severidade_minima": "alto",
        "alertas_ph": True,
        "alertas_umidade": True,
        "alertas_temperatura": True,
        "alertas_npk": True,
        "alertas_sistema": True,
        "agrupar_alertas": True,
        "intervalo_minimo_minutos": 60
    })
    
    criado_em = Column(DateTime, default=datetime.utcnow)
    ultimo_acesso = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<Usuario {self.email}>"


# ============================================================================
# MODELOS OPERACIONAIS DE GESTAO
# ============================================================================

class ClienteDB(Base):
    """Tabela de clientes/organizacoes atendidas pelo sistema."""
    __tablename__ = "clientes"
    __table_args__ = (
        Index("ix_clientes_ativo_estado", "ativo", "estado"),
    )

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(String(100), unique=True, index=True, nullable=False)
    nome = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, index=True, nullable=False)
    telefone = Column(String(50), nullable=True)
    cnpj = Column(String(30), unique=True, index=True, nullable=True)
    endereco = Column(String(300), nullable=True)
    cidade = Column(String(100), nullable=True)
    estado = Column(String(50), nullable=True)
    responsavel_nome = Column(String(200), nullable=False)
    responsavel_email = Column(String(200), index=True, nullable=False)
    responsavel_telefone = Column(String(50), nullable=True)
    observacoes = Column(Text, nullable=True)
    ativo = Column(Boolean, default=True, index=True)
    data_criacao = Column(DateTime, default=datetime.utcnow, index=True)
    data_atualizacao = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Cliente {self.cliente_id} - {self.nome}>"


class ZonaManejoDB(Base):
    """Tabela de zonas de manejo dentro dos talhoes."""
    __tablename__ = "zonas_manejo"
    __table_args__ = (
        UniqueConstraint("parcel_id", "nome", name="uq_zonas_manejo_parcel_nome"),
        Index("ix_zonas_cliente_ativo", "cliente_id", "ativo"),
        Index("ix_zonas_prop_ativo", "prop_id", "ativo"),
    )

    id = Column(Integer, primary_key=True, index=True)
    zona_id = Column(String(100), unique=True, index=True, nullable=False)
    parcel_id = Column(String(100), ForeignKey("agri_parcels.parcel_id"), nullable=False, index=True)
    prop_id = Column(String(100), index=True, nullable=True)
    cliente_id = Column(String(100), index=True, nullable=True)
    nome = Column(String(200), nullable=False)
    cultura = Column(String(80), nullable=False)
    variedade = Column(String(100), nullable=True)
    tipo_solo = Column(String(80), nullable=False)
    profundidade_sensor_cm = Column(Integer, nullable=False)
    objetivo = Column(String(120), nullable=False)
    area_hectares = Column(Float, nullable=False)
    location_coordinates = Column(JSON, nullable=True)
    ativo = Column(Boolean, default=True, index=True)
    criado_em = Column(DateTime, default=datetime.utcnow, index=True)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deletado_em = Column(DateTime, nullable=True)

    parcel = relationship("AgriParcelDB")

    def __repr__(self):
        return f"<ZonaManejo {self.zona_id} - {self.nome}>"


class FaseAtualDB(Base):
    """Tabela com o estado fenologico atual detectado por zona."""
    __tablename__ = "fases_atuais"
    __table_args__ = (
        Index("ix_fases_zona_detectado", "zona_id", "detectado_em"),
    )

    id = Column(Integer, primary_key=True, index=True)
    zona_id = Column(String(100), ForeignKey("zonas_manejo.zona_id"), nullable=False, index=True)
    cultura = Column(String(80), nullable=False)
    fase = Column(String(80), nullable=False)
    metodo = Column(String(80), nullable=False)
    data_plantio = Column(DateTime, nullable=False, index=True)
    dias_apos_plantio = Column(Integer, nullable=False)
    data_inicio_fase = Column(DateTime, nullable=False)
    data_prevista_proxima_fase = Column(DateTime, nullable=False)
    graus_dias_acumulados = Column(Float, nullable=True)
    graus_dias_necessarios = Column(Float, nullable=True)
    certeza_fase_percentual = Column(Float, nullable=False, default=90)
    validado_por_agronomia = Column(Boolean, default=False)
    detectado_em = Column(DateTime, default=datetime.utcnow, index=True)
    ultima_validacao = Column(DateTime, nullable=True)
    observacoes = Column(Text, nullable=True)

    zona = relationship("ZonaManejoDB")

    def __repr__(self):
        return f"<FaseAtual {self.zona_id} - {self.fase}>"


class HistoricoFaseDB(Base):
    """Historico de transicoes fenologicas por zona."""
    __tablename__ = "historico_fases"
    __table_args__ = (
        Index("ix_historico_fases_zona_transicao", "zona_id", "data_transicao"),
    )

    id = Column(Integer, primary_key=True, index=True)
    zona_id = Column(String(100), ForeignKey("zonas_manejo.zona_id"), nullable=False, index=True)
    fase_anterior = Column(String(80), nullable=True)
    fase_nova = Column(String(80), nullable=False)
    data_transicao = Column(DateTime, default=datetime.utcnow, index=True)
    dias_na_fase_anterior = Column(Integer, default=0)
    metodo = Column(String(80), nullable=False)
    validado = Column(Boolean, default=False)

    zona = relationship("ZonaManejoDB")


class InfraestruturaDB(Base):
    """Infraestrutura real disponivel em cada propriedade."""
    __tablename__ = "infraestruturas"
    __table_args__ = (
        Index("ix_infra_ativo_irrigacao", "ativo", "possui_irrigacao"),
    )

    id = Column(Integer, primary_key=True, index=True)
    propriedade_id = Column(String(100), unique=True, index=True, nullable=False)
    produtor_nome = Column(String(200), nullable=False)
    possui_irrigacao = Column(Boolean, nullable=False, default=False, index=True)
    sistemas_irrigacao = Column(JSON, nullable=True)
    area_irrigada_ha = Column(Float, nullable=True)
    fonte_agua = Column(String(80), nullable=True)
    capacidade_agua_m3_dia = Column(Float, nullable=True)
    equipamentos_aplicacao = Column(JSON, nullable=True)
    possui_hangar_aeronave = Column(Boolean, default=False)
    possui_maquinario_proprio = Column(Boolean, nullable=False, default=False, index=True)
    possui_armazem = Column(Boolean, default=False, index=True)
    capacidade_armazem_ton = Column(Float, nullable=True)
    possui_silo = Column(Boolean, default=False)
    possui_energia_eletrica = Column(Boolean, default=True, index=True)
    possui_geradores = Column(Boolean, default=False)
    limitacoes = Column(JSON, nullable=True)
    depende_terceiros_para = Column(JSON, nullable=True)
    custo_medio_terceiros = Column(JSON, nullable=True)
    ativo = Column(Boolean, default=True, index=True)
    criado_em = Column(DateTime, default=datetime.utcnow, index=True)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Infraestrutura {self.propriedade_id}>"


class AlertaExecucaoDB(Base):
    """Confirmacao operacional de execucao de um alerta estrategico."""
    __tablename__ = "alertas_execucoes"
    __table_args__ = (
        Index("ix_alertas_execucoes_alerta_criado", "alerta_id", "criado_em"),
    )

    id = Column(Integer, primary_key=True, index=True)
    alerta_id = Column(Integer, ForeignKey("alertas.id"), nullable=False, index=True)
    produtor_executou = Column(Boolean, nullable=False)
    data_execucao = Column(DateTime, nullable=True)
    acao_tomada = Column(Text, nullable=True)
    quantidade_aplicada = Column(String(100), nullable=True)
    custo_real = Column(Float, nullable=True)
    observacoes = Column(Text, nullable=True)
    razao_nao_execucao = Column(Text, nullable=True)
    resultado_percebido = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow, index=True)

    alerta = relationship("AlertaDB")


class AlertaExcecaoDB(Base):
    """Registro de situacoes atipicas e overrides agronomicos."""
    __tablename__ = "alertas_excecoes"
    __table_args__ = (
        Index("ix_alertas_excecoes_alerta_criado", "alerta_id", "criado_em"),
    )

    id = Column(Integer, primary_key=True, index=True)
    alerta_id = Column(Integer, ForeignKey("alertas.id"), nullable=False, index=True)
    situacao_atipica = Column(Boolean, nullable=False, default=False)
    descricao_atipico = Column(Text, nullable=True)
    requer_intervencao_agronomica = Column(Boolean, nullable=False, default=False)
    override_aplicado = Column(Boolean, default=False)
    regra_original = Column(Text, nullable=True)
    decisao_agronomica = Column(Text, nullable=True)
    justificativa = Column(Text, nullable=True)
    validado_por = Column(String(200), nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow, index=True)

    alerta = relationship("AlertaDB")


# ============================================================================
# MODELOS DE GESTÃO AGRÍCOLA (Smart Data Models)
# ============================================================================

class AgriFarmDB(Base):
    """Tabela de Fazendas/Propriedades Rurais"""
    __tablename__ = "agri_farms"
    __table_args__ = (
        Index("ix_agri_farms_cliente_ativo", "cliente_id", "ativo"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(String(100), unique=True, index=True, nullable=False)
    cliente_id = Column(String(100), index=True, nullable=False)
    
    # Informações básicas
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Endereço completo
    address_street = Column(String(300), nullable=True)
    address_locality = Column(String(100), nullable=True)  # cidade
    address_region = Column(String(100), nullable=True)  # estado
    address_country = Column(String(100), default="Brasil")
    address_postal_code = Column(String(20), nullable=True)
    
    # Dados da propriedade
    area = Column(Float, nullable=True)  # hectares
    area_unit = Column(String(20), default="hectares")
    
    # Proprietário
    owned_by = Column(String(200), nullable=True)
    contact_point = Column(String(200), nullable=True)  # telefone/email
    
    # Localização
    location_type = Column(String(20), default="Point")  # GeoJSON type
    location_coordinates = Column(JSON, nullable=True)  # [longitude, latitude]
    
    # Metadados
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    parcels = relationship("AgriParcelDB", back_populates="farm", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<AgriFarm {self.farm_id} - {self.name}>"


class AgriParcelDB(Base):
    """Tabela de Talhões/Parcelas dentro de uma Fazenda"""
    __tablename__ = "agri_parcels"
    __table_args__ = (
        Index("ix_agri_parcels_cliente_ativo", "cliente_id", "ativo"),
        Index("ix_agri_parcels_farm_ativo", "farm_id", "ativo"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    parcel_id = Column(String(100), unique=True, index=True, nullable=False)
    cliente_id = Column(String(100), index=True, nullable=False)
    farm_id = Column(String(100), ForeignKey("agri_farms.farm_id"), nullable=False, index=True)
    
    # Informações básicas
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)  # arable, grassland, orchard, etc
    
    # Área e localização
    area = Column(Float, nullable=True)  # hectares
    area_unit = Column(String(20), default="hectares")
    location_type = Column(String(20), default="Polygon")  # GeoJSON type
    location_coordinates = Column(JSON, nullable=True)  # [[lon, lat], [lon, lat], ...]
    
    # Relacionamentos com outras entidades
    crop_id = Column(String(100), ForeignKey("agri_crops.crop_id"), nullable=True, index=True)
    soil_type = Column(String(100), nullable=True)  # referência ao tipo de solo
    
    # Metadados
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    farm = relationship("AgriFarmDB", back_populates="parcels")
    crop = relationship("AgriCropDB", back_populates="parcels")
    records = relationship("AgriParcelRecordDB", back_populates="parcel", cascade="all, delete-orphan")
    operations = relationship("AgriParcelOperationDB", back_populates="parcel", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<AgriParcel {self.parcel_id} - {self.name}>"


class AgriCropDB(Base):
    """Tabela de Culturas/Plantações"""
    __tablename__ = "agri_crops"
    
    id = Column(Integer, primary_key=True, index=True)
    crop_id = Column(String(100), unique=True, index=True, nullable=False)
    
    # Informações básicas
    name = Column(String(200), nullable=False)
    alternate_name = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    agrovoc_concept = Column(String(300), nullable=True)  # URL do conceito no AgroVoc
    
    # Calendário agrícola
    planting_from = Column(String(10), nullable=True)  # formato: --MM-DD
    planting_to = Column(String(10), nullable=True)
    harvesting_from = Column(String(10), nullable=True)
    harvesting_to = Column(String(10), nullable=True)
    
    # Requisitos
    watering_frequency = Column(String(50), nullable=True)  # daily, weekly, etc
    
    # Faixas ideais (opcional)
    ideal_temp_min = Column(Float, nullable=True)
    ideal_temp_max = Column(Float, nullable=True)
    ideal_ph_min = Column(Float, nullable=True)
    ideal_ph_max = Column(Float, nullable=True)
    ideal_moisture_min = Column(Float, nullable=True)
    ideal_moisture_max = Column(Float, nullable=True)
    
    # Fertilizantes e produtos recomendados (JSON array de IDs)
    recommended_fertilizers = Column(JSON, nullable=True)
    recommended_pesticides = Column(JSON, nullable=True)
    
    # Metadados
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    parcels = relationship("AgriParcelDB", back_populates="crop")
    
    def __repr__(self):
        return f"<AgriCrop {self.crop_id} - {self.name}>"


class AgriParcelRecordDB(Base):
    """Tabela de Registros de Condições dos Talhões"""
    __tablename__ = "agri_parcel_records"
    __table_args__ = (
        Index("ix_agri_records_cliente_parcel_timestamp", "cliente_id", "parcel_id", "timestamp"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(String(100), unique=True, index=True, nullable=False)
    parcel_id = Column(String(100), ForeignKey("agri_parcels.parcel_id"), nullable=False, index=True)
    cliente_id = Column(String(100), index=True, nullable=False)
    
    # Condições do solo
    soil_temperature = Column(Float, nullable=True)  # °C
    soil_moisture = Column(Float, nullable=True)  # %
    soil_moisture_vwc = Column(Float, nullable=True)  # volumetric water content
    soil_moisture_ec = Column(Float, nullable=True)  # electrical conductivity
    soil_salinity = Column(Float, nullable=True)
    
    # Condições atmosféricas
    atmospheric_pressure = Column(Float, nullable=True)  # hPa
    solar_radiation = Column(Float, nullable=True)  # W/m²
    relative_humidity = Column(Float, nullable=True)  # %
    air_temperature = Column(Float, nullable=True)  # °C
    
    # Observações sobre a planta
    leaf_wetness = Column(Float, nullable=True)  # %
    leaf_relative_humidity = Column(Float, nullable=True)
    leaf_temperature = Column(Float, nullable=True)
    
    # Observações gerais
    depth = Column(Float, nullable=True)  # profundidade da medição (cm)
    description = Column(Text, nullable=True)
    
    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relacionamentos
    parcel = relationship("AgriParcelDB", back_populates="records")
    
    def __repr__(self):
        return f"<AgriParcelRecord {self.record_id} - {self.timestamp}>"


class AgriParcelOperationDB(Base):
    """Tabela de Operações Realizadas nos Talhões"""
    __tablename__ = "agri_parcel_operations"
    __table_args__ = (
        Index("ix_agri_operations_cliente_status", "cliente_id", "status"),
        Index("ix_agri_operations_parcel_status", "parcel_id", "status"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    operation_id = Column(String(100), unique=True, index=True, nullable=False)
    parcel_id = Column(String(100), ForeignKey("agri_parcels.parcel_id"), nullable=False, index=True)
    cliente_id = Column(String(100), index=True, nullable=False)
    
    # Tipo de operação
    operation_type = Column(String(50), nullable=False)  # fertilising, irrigation, harvesting, sowing, etc
    description = Column(Text, nullable=True)
    
    # Status e datas
    status = Column(String(50), default="planned")  # planned, ongoing, finished, cancelled
    planned_start = Column(DateTime, nullable=True)
    planned_end = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    
    # Recursos utilizados
    operator = Column(String(200), nullable=True)  # nome do operador/responsável
    water_source = Column(String(100), nullable=True)  # para irrigação
    working_area = Column(Float, nullable=True)  # área trabalhada (hectares)
    
    # Quantidade e produto (se aplicável)
    quantity = Column(Float, nullable=True)  # quantidade aplicada/colhida
    quantity_unit = Column(String(50), nullable=True)  # kg, litros, ton, etc
    product_type = Column(String(100), nullable=True)  # tipo de produto usado
    
    # Custo (opcional)
    reported_cost = Column(Float, nullable=True)
    cost_currency = Column(String(10), default="BRL")
    
    # Relacionamento com fertilização (se for operation_type=fertilising)
    fertilize_id = Column(String(100), ForeignKey("agri_fertilizes.fertilize_id"), nullable=True, index=True)
    
    # Metadados
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    parcel = relationship("AgriParcelDB", back_populates="operations")
    fertilize = relationship("AgriFertilizeDB", back_populates="operations")
    
    def __repr__(self):
        return f"<AgriParcelOperation {self.operation_id} - {self.operation_type}>"


class AgriFertilizeDB(Base):
    """Tabela de Detalhes de Fertilização"""
    __tablename__ = "agri_fertilizes"
    __table_args__ = (
        Index("ix_agri_fertilizes_cliente_produto", "cliente_id", "product_name"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    fertilize_id = Column(String(100), unique=True, index=True, nullable=False)
    cliente_id = Column(String(100), index=True, nullable=False)
    
    # Produto
    product_name = Column(String(200), nullable=False)
    product_code = Column(String(100), nullable=True)
    manufacturer = Column(String(200), nullable=True)
    
    # Tipo de fertilizante
    fertilizer_type = Column(String(50), nullable=True)  # organic, inorganic, mixed
    application_method = Column(String(50), nullable=True)  # spreading, fertigation, foliar, etc
    
    # Composição química
    nitrogen_content = Column(Float, nullable=True)  # % N
    phosphorous_content = Column(Float, nullable=True)  # % P
    potassium_content = Column(Float, nullable=True)  # % K
    
    # Micronutrientes (JSON array)
    micronutrients = Column(JSON, nullable=True)  # ["Zn", "B", "Fe", ...]
    
    # Quantidade e forma
    quantity = Column(Float, nullable=True)
    quantity_unit = Column(String(50), default="kg")
    
    # Recomendações de uso
    recommended_dose = Column(Float, nullable=True)  # dose recomendada por hectare
    recommended_dose_unit = Column(String(50), nullable=True)
    
    # Documentação
    description = Column(Text, nullable=True)
    safety_instructions = Column(Text, nullable=True)
    
    # Metadados
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    operations = relationship("AgriParcelOperationDB", back_populates="fertilize")
    
    def __repr__(self):
        return f"<AgriFertilize {self.fertilize_id} - {self.product_name}>"
