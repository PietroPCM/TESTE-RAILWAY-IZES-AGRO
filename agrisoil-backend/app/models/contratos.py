"""
Modelos dos 5 Contratos JSON Fixos
- CLIMA_BRUTO (Interno)
- CLIMA_TRATADO (Processado)
- CLIMA_MOBILE (App)
- CONTEXTO_IA (IA)
- RESPOSTA_IA (IA Response)
"""

from pydantic import BaseModel, Field, model_serializer
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from app.utils.datetime_utils import serialize_utc_payload


# ============================================================================
# 1️⃣ CLIMA_BRUTO - Dados brutos do provedor (INTERNO)
# ============================================================================

class IndicesClimatico(BaseModel):
    """Índices climáticos calculados"""
    geada_risco: int = Field(..., ge=0, le=100, description="Risco de geada 0-100%")
    seca_risco: int = Field(..., ge=0, le=100, description="Risco de seca 0-100%")
    calor_risco: int = Field(..., ge=0, le=100, description="Risco de calor 0-100%")
    umidade_excessiva_risco: int = Field(..., ge=0, le=100, description="Risco de umidade excessiva 0-100%")


class PrevisaoHoraria(BaseModel):
    """Previsão horária"""
    timestamp: datetime
    temperatura: float
    umidade: int
    condicao: str
    chuva_probabilidade: int = Field(..., ge=0, le=100)
    chuva_mm: float = 0.0


class ClimaBruto(BaseModel):
    """
    CONTRATO 1: CLIMA_BRUTO
    Dados brutos do provedor (OpenWeatherMap, WeatherAPI)
    Nunca é exposto direto ao app mobile
    Armazenado em tabela: clima_bruto
    """
    coleta_id: str = Field(..., description="ID único da coleta (sensor_001_2026_01_20_15_30)")
    sensor_id: str
    cliente_id: str
    latitude: float
    longitude: float
    
    # Dados brutos
    temperatura_celsius: float
    umidade_relativa: int = Field(..., ge=0, le=100)
    pressao_atm: float = Field(..., description="Pressão atmosférica em hPa")
    velocidade_vento_kmh: float
    precipitacao_mm: float = 0.0
    condicao: str = Field(..., description="Ex: 'nublado', 'ensolarado', 'chuvoso'")
    cobertura_nuvens_percent: int = Field(..., ge=0, le=100)
    
    # Índices
    indices: IndicesClimatico
    
    # Previsão
    previsao_24h: List[PrevisaoHoraria] = []
    previsao_7dias: List[Dict[str, Any]] = []
    
    # Metadata
    timestamp: datetime = Field(default_factory=datetime.now)
    criado_em: datetime = Field(default_factory=datetime.now)
    provedor: str = Field(..., description="Ex: 'openweathermap', 'weatherapi'")
    
    class Config:
        json_schema_extra = {
            "example": {
                "coleta_id": "sensor_001_2026_01_20_15_30",
                "sensor_id": "sensor_001",
                "cliente_id": "cliente_agritech",
                "latitude": -15.7801,
                "longitude": -48.0896,
                "temperatura_celsius": 22.5,
                "umidade_relativa": 65,
                "pressao_atm": 1013.25,
                "velocidade_vento_kmh": 12.3,
                "precipitacao_mm": 0.0,
                "condicao": "nublado",
                "cobertura_nuvens_percent": 50,
                "indices": {
                    "geada_risco": 0,
                    "seca_risco": 50,
                    "calor_risco": 0,
                    "umidade_excessiva_risco": 5
                },
                "provedor": "openweathermap"
            }
        }


# ============================================================================
# 2️⃣ CLIMA_TRATADO - Resultado de regras (PROCESSADO)
# ============================================================================

class DecisaoAlerta(BaseModel):
    """Decisão de alerta gerada pelo motor de regras"""
    tipo: Optional[str] = Field(None, description="Ex: 'geada', 'seca', 'calor', 'umidade_excessiva', 'chuva'")
    severidade: Optional[str] = Field(None, description="'baixa', 'media', 'alta', 'critica'")
    mensagem: str = Field(..., description="Mensagem para o usuário")
    ativa: bool = Field(default=False, description="Alerta está ativo agora?")
    desde: datetime = Field(default_factory=datetime.now)


class RecomendacaoAcao(BaseModel):
    """Ação recomendada pelo motor de regras"""
    principal: str = Field(..., description="Ex: 'Aumentar irrigação', 'Preparar proteção contra geada'")
    secundarias: List[str] = []
    urgencia: str = Field(default="normal", description="'baixa', 'normal', 'alta', 'critica'")
    prazo_horas: Optional[int] = None


class ClimaProcessado(BaseModel):
    """
    CONTRATO 2: CLIMA_TRATADO
    Resultado do motor de regras
    Contém decisões e recomendações
    Armazenado em: clima_tratado
    """
    sensor_id: str
    cliente_id: str
    
    # Alerta
    alerta: DecisaoAlerta
    
    # Recomendação
    recomendacao: RecomendacaoAcao
    
    # Contexto da decisão
    confianca_decisao: float = Field(..., ge=0.0, le=1.0, description="Confiança 0.0-1.0")
    regras_disparadas: List[str] = []
    historico_considerado_dias: int = Field(default=7)
    
    # Metadata
    timestamp: datetime = Field(default_factory=datetime.now)
    criado_em: datetime = Field(default_factory=datetime.now)
    validade_ate: datetime = Field(default_factory=lambda: datetime.now() + timedelta(hours=1))
    
    class Config:
        json_schema_extra = {
            "example": {
                "sensor_id": "sensor_001",
                "cliente_id": "cliente_agritech",
                "alerta": {
                    "tipo": "seca",
                    "severidade": "alta",
                    "mensagem": "Risco de seca detectado: umidade 65%",
                    "ativa": True,
                    "desde": "2026-01-20T12:00:00Z"
                },
                "recomendacao": {
                    "principal": "Aumentar frequência de irrigação",
                    "secundarias": ["Monitorar solo", "Aumentar por 30%"],
                    "urgencia": "alta",
                    "prazo_horas": 2
                },
                "confianca_decisao": 0.92,
                "regras_disparadas": ["umidade_baixa", "chuva_insuficiente"]
            }
        }


# ============================================================================
# 3️⃣ CLIMA_MOBILE - Resumido para app (PUBLICO)
# ============================================================================

class ClimaMobile(BaseModel):
    """
    CONTRATO 3: CLIMA_MOBILE
    Dados resumidos para app mobile
    Apenas 6-7 campos essenciais
    Retornado por: GET /api/dashboard/cliente/{id}/sensores
    """
    sensor_id: str
    propriedade: str
    municipio: str
    local_especifico: Optional[str] = None
    
    # Dados climáticos (apenas essencial)
    temperatura: int = Field(..., description="Temperatura em °C (arredondada)")
    umidade: int = Field(..., ge=0, le=100, description="Umidade em %")
    condicao: str = Field(..., description="Ex: 'nublado', 'ensolarado'")
    chuva_probabilidade: int = Field(..., ge=0, le=100, description="Probabilidade de chuva em %")
    
    # Alerta e ação (resumido)
    alerta: Optional[str] = Field(None, description="Tipo de alerta (ex: 'seca', 'geada')")
    acao_recomendada: Optional[str] = Field(None, description="O que fazer agora")
    
    # Timestamp
    atualizado_em: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_schema_extra = {
            "example": {
                "sensor_id": "sensor_001",
                "propriedade": "Fazenda São João",
                "municipio": "Brasília",
                "local_especifico": "Talhão A",
                "temperatura": 22,
                "umidade": 65,
                "condicao": "nublado",
                "chuva_probabilidade": 30,
                "alerta": "seca",
                "acao_recomendada": "Aumentar irrigação",
                "atualizado_em": "2026-01-20T15:30:00Z"
            }
        }


class DashboardMobileResponse(BaseModel):
    """Resposta do endpoint /api/dashboard/cliente/{id}/sensores"""
    cliente_id: str
    sensores: List[ClimaMobile]
    atualizado_em: datetime = Field(default_factory=datetime.now)


# ============================================================================
# 4️⃣ CONTEXTO_IA - Dados ricos para IA processar
# ============================================================================

class SensorInfo(BaseModel):
    """Info do sensor para contexto IA"""
    sensor_id: str
    nome: Optional[str] = None
    propriedade: str
    tipo: str = Field(description="Ex: 'solo', 'ar', 'hybrid'")
    local_especifico: Optional[str] = None
    localizacao: Dict[str, Any] = Field(..., description="lat, lon, municipio, estado")
    ultima_leitura: Optional[Dict[str, Any]] = None
    avaliacoes: Dict[str, Any] = Field(default_factory=dict)


class ClimaHistoricoSemana(BaseModel):
    """Histórico de clima dos últimos 7 dias"""
    temperatura_media: float
    temperatura_min: float
    temperatura_max: float
    umidade_media: int
    umidade_min: int
    umidade_max: int
    chuva_total_mm: float
    dias_com_chuva: int
    dias_sem_chuva: int
    vento_medio_kmh: float
    previsao_proximos_dias: List[Dict[str, Any]] = []


class AlertaHistorico(BaseModel):
    """Alerta que ocorreu no passado"""
    tipo: str
    severidade: str
    desde: datetime
    ate: Optional[datetime] = None
    acao_tomada: Optional[str] = None


class ContextoIA(BaseModel):
    """
    CONTRATO 4: CONTEXTO_IA
    Dados ricos para IA processar
    Montado sob demanda pelo serviço contexto_ia.py
    Usado por: POST /api/ia/chat
    """
    cliente_id: str
    sensor_id: Optional[str] = None
    usuario_pergunta: str = Field(..., description="A pergunta do usuário")
    
    # Sensores relevantes
    sensores_relevantes: List[SensorInfo] = []
    
    # Clima atual e histórico
    clima_atual: Optional[Dict[str, Any]] = None
    clima_ultimos_7_dias: Dict[str, ClimaHistoricoSemana] = {}
    previsao_7_dias: List[Dict[str, Any]] = []
    
    # Alertas
    alertas_ativos: List[DecisaoAlerta] = []
    alertas_historico_30_dias: List[AlertaHistorico] = []
    
    # Contexto agrícola
    plano_agronomo: Optional[Dict[str, Any]] = None
    cultura: Optional[str] = None
    fase_desenvolvimento: Optional[str] = None
    
    # Histórico de IA
    conversas_anteriores_30_dias: List[Dict[str, Any]] = []
    
    # Prioridades
    prioridades: Dict[str, Any] = Field(
        default_factory=dict,
        description="É crítico? É tempo sensível? Relevância?"
    )
    
    # Metadata
    timestamp_coleta: datetime = Field(default_factory=datetime.now)
    tokens_estimado: int = 0
    
    class Config:
        json_schema_extra = {
            "example": {
                "cliente_id": "cliente_real",
                "usuario_pergunta": "Qual o risco no solo agora?",
                "sensores_relevantes": [
                    {
                        "sensor_id": "sensor_real_001",
                        "propriedade": "Propriedade cadastrada no banco",
                        "tipo": "solo",
                        "ultima_leitura": {"umidade": 22.0}
                    }
                ],
                "clima_ultimos_7_dias": {},
                "alertas_ativos": [
                    {
                        "tipo": "umidade",
                        "severidade": "alta",
                        "mensagem": "Alerta real cadastrado no banco"
                    }
                ]
            }
        }


# ============================================================================
# 5️⃣ RESPOSTA_IA - Resposta estruturada da IA
# ============================================================================

class RecomendacaoIA(BaseModel):
    """Recomendação estruturada da IA"""
    acao: str = Field(..., description="O que fazer (ex: 'Irrigar por 2-3 horas')")
    confianca: float = Field(..., ge=0.0, le=1.0, description="Confiança 0.0-1.0")
    motivo: str = Field(..., description="Por que essa ação (razão técnica)")
    riscos_se_nao_fizer: Optional[str] = None
    beneficios: Optional[str] = None


class RespostaIA(BaseModel):
    """
    CONTRATO 5: RESPOSTA_IA
    Resposta estruturada da IA GPT-4
    Retornado por: POST /api/ia/chat
    """
    pergunta_id: str = Field(..., description="ID único da conversa")
    cliente_id: str
    sensor_id: Optional[str] = None
    
    # Resposta
    resposta_texto: str = Field(..., description="Resposta em texto natural")
    resposta_estruturada: Optional[Dict[str, Any]] = None
    
    # Recomendação
    recomendacao: Optional[RecomendacaoIA] = None
    
    # Contexto adicional
    dados_consultados: List[str] = Field(default_factory=list, description="Quais dados foram consultados")
    atencoes: List[str] = Field(default_factory=list, description="Pontos de atenção adicionais")
    proximos_passos: List[str] = Field(default_factory=list, description="O que fazer depois")
    
    # Qualidade
    confianca_geral: float = Field(..., ge=0.0, le=1.0, description="Confiança geral da resposta")
    requer_validacao_humana: bool = Field(default=False, description="Precisa revisar antes de agir?")
    
    # Validade
    validade: Dict[str, Any] = Field(
        default_factory=lambda: {
            "ate": datetime.now() + timedelta(hours=1),
            "razao": "Previsão muda frequentemente"
        }
    )
    
    # Metadata
    modelo: str = Field(default="gpt-4-turbo", description="Modelo de IA usado")
    tokens_usados: int = 0
    tempo_resposta_segundos: float = 0.0
    criado_em: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_schema_extra = {
            "example": {
                "pergunta_id": "conv_cliente_real_abc123",
                "cliente_id": "cliente_real",
                "resposta_texto": "Situação: Há leitura real do sensor.\n\nRisco: Umidade baixa exige atenção.\n\nO que fazer agora:\n1. Conferir dashboard.\n2. Coletar nova leitura.\n3. Validar em campo.\n\nAtenção: Não aplique dose exata sem análise de solo ou agrônomo.",
                "recomendacao": {
                    "acao": "Conferir leitura e validar em campo.",
                    "confianca": 0.80,
                    "motivo": "Baseado apenas no contexto real recebido.",
                    "riscos_se_nao_fizer": "Pode haver decisão sem validação.",
                    "beneficios": "Reduz risco de agir com dado incompleto."
                },
                "atencoes": ["Não substitui laudo agronômico."],
                "proximos_passos": ["Conferir dashboard", "Coletar nova leitura"],
                "confianca_geral": 0.80
            }
        }

    @model_serializer(mode="wrap")
    def serialize_model(self, handler):
        return serialize_utc_payload(handler(self))


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "ClimaBruto",
    "ClimaProcessado",
    "ClimaMobile",
    "ContextoIA",
    "RespostaIA",
    "DashboardMobileResponse",
]
