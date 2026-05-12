"""
CAMADA 1: CONTEXTO FIXO - Configuração da Propriedade/Talhão
Define como interpretar TODOS os dados dessa zona

Entidades principais:
- Cultura (soja, milho, café, etc.)
- Variedade (quando aplicável)
- Tipo de solo
- Zona de manejo
- Profundidade do sensor
- Objetivo do produtor
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Tuple
from enum import Enum
from datetime import datetime, timezone


# ============================================================================
# CULTURAS DISPONÍVEIS
# ============================================================================

class NomeCultura(str, Enum):
    """Culturas suportadas no sistema"""
    SOJA = "soja"
    MILHO = "milho"
    TRIGO = "trigo"
    CAFE = "cafe"
    CANA = "cana_de_acucar"
    FEIJAO = "feijao"
    ALGODAO = "algodao"
    ARROZ = "arroz"
    ABACAXI = "abacaxi"
    BANANA = "banana"


# ============================================================================
# FASES FENOLÓGICAS (Ciclo da Cultura)
# ============================================================================

class FaseFenologica(str, Enum):
    """Fases padrão de qualquer cultura"""
    PRE_PLANTIO = "pre_plantio"
    EMERGENCIA = "emergencia"
    VEGETATIVO = "vegetativo"
    FLORESCIMENTO = "florescimento"
    ENCHIMENTO_GRAOS = "enchimento_graos"
    MATURACAO = "maturacao"
    COLHEITA = "colheita"


# ============================================================================
# TIPOS DE SOLO
# ============================================================================

class TipoSolo(str, Enum):
    """Classificação de solo"""
    ARENOSO = "arenoso"  # 0-10% argila
    FRANCO_ARENOSO = "franco_arenoso"  # 10-27% argila
    FRANCO = "franco"  # 27-40% argila
    FRANCO_SILTOSO = "franco_siltoso"  # 27-50% argila
    ARGILOSO = "argiloso"  # >40% argila


# ============================================================================
# OBJETIVO DO PRODUTOR
# ============================================================================

class ObjetivoProdutor(str, Enum):
    """Objetivos de manejo disponíveis"""
    MAXIMIZAR_PRODUTIVIDADE = "maximizar_produtividade"
    REDUZIR_CUSTO = "reduzir_custo"
    ESTABILIDADE = "estabilidade"
    SUSTENTABILIDADE = "sustentabilidade"


# ============================================================================
# PARÂMETROS DO SOLO
# ============================================================================

class NomeParametro(str, Enum):
    """Parâmetros padrão do sistema"""
    UMIDADE = "umidade"
    PH = "ph"
    TEMPERATURA = "temperatura"
    NITROGENIO = "nitrogenio"
    FOSFORO = "fosforo"
    POTASSIO = "potassio"
    CONDUTIVIDADE_ELETRICA = "condutividade_eletrica"
    COMPACTACAO = "compactacao"
    MATERIA_ORGANICA = "materia_organica"


# ============================================================================
# ZONA DE MANEJO
# ============================================================================

class ZonaManejo(BaseModel):
    """Define uma zona específica dentro do talhão.
    
    Uma zona representa uma área homogênea dentro de um talhão (parcel)
    com características e objetivos de manejo similares.
    """
    id: str = Field(..., description="ID único da zona")
    parcel_id: str = Field(..., description="ID do talhão")
    nome: str = Field(..., description="Ex: Zona Norte, Zona Baixa")
    cultura: NomeCultura
    variedade: Optional[str] = None
    tipo_solo: TipoSolo
    profundidade_sensor_cm: int = Field(..., ge=1, le=100, description="Profundidade do sensor em cm (1-100)")
    objetivo: ObjetivoProdutor
    
    # Localização
    area_hectares: Optional[float] = Field(None, ge=0.01, description="Área em hectares")
    location_coordinates: Optional[Tuple[float, float]] = Field(None, description="(longitude, latitude)")
    
    # Histórico
    criado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    atualizado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deletado_em: Optional[datetime] = None
    ativo: bool = True
    
    @field_validator('location_coordinates')
    @classmethod
    def validar_coordenadas(cls, v: Optional[Tuple[float, float]]) -> Optional[Tuple[float, float]]:
        """Validar se coordenadas estão no intervalo correto."""
        if v is not None:
            lon, lat = v
            if not (-180 <= lon <= 180):
                raise ValueError(f'Longitude {lon} deve estar entre -180 e 180')
            if not (-90 <= lat <= 90):
                raise ValueError(f'Latitude {lat} deve estar entre -90 e 90')
        return v


class ZonaManejoCreate(BaseModel):
    """Modelo para criar zona de manejo"""
    nome: str
    cultura: NomeCultura
    variedade: Optional[str] = None
    tipo_solo: TipoSolo
    profundidade_sensor_cm: int = Field(..., ge=1, le=100)
    objetivo: ObjetivoProdutor
    area_hectares: Optional[float] = Field(None, ge=0.01)
    location_coordinates: Optional[Tuple[float, float]] = None
    
    @field_validator('location_coordinates')
    @classmethod
    def validar_coordenadas(cls, v: Optional[Tuple[float, float]]) -> Optional[Tuple[float, float]]:
        """Validar coordenadas."""
        if v is not None:
            lon, lat = v
            if not (-180 <= lon <= 180):
                raise ValueError(f'Longitude {lon} deve estar entre -180 e 180')
            if not (-90 <= lat <= 90):
                raise ValueError(f'Latitude {lat} deve estar entre -90 e 90')
        return v


class ZonaManejoUpdate(BaseModel):
    """Modelo para atualizar zona de manejo (todos os campos opcionais)"""
    nome: Optional[str] = None
    cultura: Optional[NomeCultura] = None
    variedade: Optional[str] = None
    tipo_solo: Optional[TipoSolo] = None
    profundidade_sensor_cm: Optional[int] = Field(None, ge=1, le=100)
    objetivo: Optional[ObjetivoProdutor] = None
    area_hectares: Optional[float] = Field(None, ge=0.01)
    location_coordinates: Optional[Tuple[float, float]] = None
    ativo: Optional[bool] = None
    
    @field_validator('location_coordinates')
    @classmethod
    def validar_coordenadas(cls, v: Optional[Tuple[float, float]]) -> Optional[Tuple[float, float]]:
        """Validar coordenadas."""
        if v is not None:
            lon, lat = v
            if not (-180 <= lon <= 180):
                raise ValueError(f'Longitude {lon} deve estar entre -180 e 180')
            if not (-90 <= lat <= 90):
                raise ValueError(f'Latitude {lat} deve estar entre -90 e 90')
        return v


class ZonaManejoResponse(ZonaManejo):
    """Resposta da API"""
    class Config:
        from_attributes = True


# ============================================================================
# CALENDÁRIO FENOLÓGICO
# ============================================================================

class FaseCalendario(BaseModel):
    """Define quando uma cultura está em cada fase.
    
    Usa calendário juliano para representar períodos do ano.
    Exemplo: Soja em emergência começa no dia 290 (~17/10) até dia 310 (~6/11).
    """
    cultura: NomeCultura
    fase: FaseFenologica
    dia_juliano_inicio: int = Field(..., ge=1, le=365, description="Dia 1-365 do ano")
    dia_juliano_fim: int = Field(..., ge=1, le=365, description="Dia 1-365 do ano")
    descricao: str
    
    @field_validator('dia_juliano_fim')
    @classmethod
    def validar_dias_julianos(cls, v: int, info) -> int:
        """Validar dias julianos.
        
        Permite períodos que atravessam o ano (ex: 350 a 10).
        Para isso, basta que fim < início, indicando período circular.
        """
        inicio = info.data.get('dia_juliano_inicio')
        if inicio is not None:
            # Se fim == início, é inválido (período de 0 dias)
            if v == inicio:
                raise ValueError('dia_juliano_fim não pode ser igual a dia_juliano_inicio')
            # Períodos circulares são permitidos (ex: 350 a 10)
            # Períodos normais devem ter fim > início
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "cultura": "soja",
                "fase": "emergencia",
                "dia_juliano_inicio": 290,  # ~17 de outubro
                "dia_juliano_fim": 310,  # ~6 de novembro
                "descricao": "Emergência da soja no Brasil Central"
            }
        }


# ============================================================================
# PARÂMETROS IDEAIS POR FASE E CULTURA
# ============================================================================

class ParametroIdeal(BaseModel):
    """Define valores ideais de um parâmetro para uma cultura em uma fase.
    
    Estrutura de limites (do mais restritivo ao mais amplo):
    Crítico < Alerta < Ideal < Alerta < Crítico
    
    Exemplo para umidade:
    Crítico: <20% | Alerta: 20-22% | Ideal: 25-35% | Alerta: 40-45% | Crítico: >45%
    """
    id: str
    cultura: NomeCultura
    fase: FaseFenologica
    parametro: NomeParametro
    
    # Valores ideais
    minimo_ideal: float = Field(..., description="Limite inferior ideal")
    maximo_ideal: float = Field(..., description="Limite superior ideal")
    
    # Limites de alerta (quando sai do ideal)
    minimo_alerta: float = Field(..., description="Abaixo = alerta")
    maximo_alerta: float = Field(..., description="Acima = alerta")
    
    # Limites críticos (quando precisa ação urgente)
    minimo_critico: float = Field(..., description="Abaixo = crítico")
    maximo_critico: float = Field(..., description="Acima = crítico")
    
    # Unidade
    unidade: str = Field(..., description="%, pH, °C, mg/kg, etc")
    
    # Descrição de impacto
    impacto_desvio: str = Field(..., description="O que acontece se sair dos limites")
    
    @field_validator('minimo_ideal', 'maximo_ideal', 'minimo_alerta', 'maximo_alerta', 
                     'minimo_critico', 'maximo_critico', mode='before')
    @classmethod
    def validar_numeros(cls, v):
        """Validar se todos os valores são números."""
        if not isinstance(v, (int, float)):
            raise ValueError('Todos os limites devem ser números')
        return float(v)
    
    @model_validator(mode='after')
    def validar_ordem_completa_limites(self) -> 'ParametroIdeal':
        """Validar ordem completa: crítico_min < alerta_min < ideal_min < ideal_max < alerta_max < crítico_max."""
        limites = [
            ('minimo_critico', self.minimo_critico),
            ('minimo_alerta', self.minimo_alerta),
            ('minimo_ideal', self.minimo_ideal),
            ('maximo_ideal', self.maximo_ideal),
            ('maximo_alerta', self.maximo_alerta),
            ('maximo_critico', self.maximo_critico),
        ]
        
        # Verificar ordem crescente
        for i in range(len(limites) - 1):
            nome_atual, valor_atual = limites[i]
            nome_proximo, valor_proximo = limites[i + 1]
            
            if valor_atual >= valor_proximo:
                raise ValueError(
                    f'Ordem inválida: {nome_atual}={valor_atual} deve ser menor que '
                    f'{nome_proximo}={valor_proximo}. '
                    f'Ordem esperada: crítico_min < alerta_min < ideal_min < ideal_max < alerta_max < crítico_max'
                )
        
        return self
    
    class Config:
        json_schema_extra = {
            "example": {
                "cultura": "soja",
                "fase": "emergencia",
                "parametro": "umidade",
                "minimo_ideal": 25,
                "maximo_ideal": 35,
                "minimo_alerta": 22,
                "maximo_alerta": 40,
                "minimo_critico": 20,
                "maximo_critico": 45,
                "unidade": "%",
                "impacto_desvio": "Umidade muito baixa prejudica emergência. Risco de falha de estande."
            }
        }


# ============================================================================
# BIBLIOTECA DE CONTEXTOS (MASTER DATA)
# ============================================================================

class BibliotecaCultura(BaseModel):
    """Biblioteca centralizada de uma cultura.
    
    Contém informações master de fases fenológicas e parâmetros ideais
    para uma cultura específica. Serve como referência para todas as
    zonas que cultivam essa cultura.
    """
    id: str
    nome: NomeCultura
    descricao: str
    ciclo_dias: int = Field(..., ge=1, description="Dias do plantio até colheita")
    fases: List[FaseCalendario] = Field(..., min_length=1)
    parametros_ideais: List[ParametroIdeal] = Field(..., min_length=1)
    
    # Documentação
    fonte_agronomica: Optional[str] = None
    validado_por_agronomos: bool = False
    ultima_atualizacao: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ContextoFixoResponse(BaseModel):
    """Resposta completa do contexto fixo de uma zona.
    
    Integra a configuração de uma zona específica com as informações
    master de sua cultura e os parâmetros ideais para a fase atual.
    """
    zona: ZonaManejoResponse
    cultura_info: BibliotecaCultura
    parametros_fase_atual: List[ParametroIdeal]
    
    class Config:
        from_attributes = True
