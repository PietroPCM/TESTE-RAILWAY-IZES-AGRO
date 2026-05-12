"""
CAMADA 3: REGRA DE ALERTA CONTEXTUALIZADA
A regra nunca é genérica. Sempre inclui: Cultura + Fase + Zona
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
from app.models.contexto_fixo import NomeCultura, FaseFenologica


class AcaoRecomendada(str, Enum):
    """Ações práticas que o produtor pode tomar"""
    IRRIGAR = "irrigar"
    DRENAR = "drenar"
    APLICAR_CALCARIO = "aplicar_calcario"
    APLICAR_ENXOFRE = "aplicar_enxofre"
    ADUBAR_NPK = "adubar_npk"
    ADUBAR_MICRONUTRIENTE = "adubar_micronutriente"
    INSPECIONAR_SENSOR = "inspecionar_sensor"
    CONTATAR_AGRONOMIA = "contatar_agronomia"
    AGUARDAR_CHUVA = "aguardar_chuva"
    MONITORAR = "monitorar"
    NENHUMA = "nenhuma"


class RegradeAlerta(BaseModel):
    """
    Regra de alerta CONTEXTUALIZADA
    
    Exemplo:
    - Cultura: Soja
    - Fase: Emergência
    - Parâmetro: Umidade
    - Limite: < 22% por 24h
    - Ação: Alerta de risco de falha de estande
    """
    id: str = Field(..., description="ID único da regra")
    
    # CONTEXTO (Camada 1)
    cultura: NomeCultura
    fase: FaseFenologica
    
    # PARÂMETRO
    parametro: str = Field(..., description="umidade, ph, temperatura, etc")
    
    # LIMITES (baseados nos ParametroIdeal da Camada 1)
    minimo_alerta: float
    maximo_alerta: float
    minimo_critico: float
    maximo_critico: float
    
    # DURAÇÃO (evita falsos positivos)
    duracao_minima_horas: int = Field(
        ..., 
        description="Quanto tempo o parâmetro deve estar fora dos limites para disparar"
    )
    
    # MENSAGEM CONTEXTUALIZADA (para produtor, não técnica demais)
    titulo_alerta: str = Field(..., description="Título do alerta")
    mensagem_produtor: str = Field(
        ..., 
        description="Linguagem simples, sem jargão técnico"
    )
    impacto_na_fase: str = Field(
        ..., 
        description="Por que isso é importante AGORA nesta fase"
    )
    
    # AÇÃO RECOMENDADA (Camada 3)
    acao_recomendada: AcaoRecomendada
    urgencia_acao: str = Field(
        ..., 
        description="imediata, 24h, 48h, monitorar"
    )
    
    # EXPLICAÇÃO IA (será gerada pela IA)
    template_explicacao_ia: str = Field(
        ..., 
        description="Template para IA explicar o alerta ao produtor"
    )
    
    # VALIDAÇÃO
    validado_por_agronomia: bool = False
    agronomica_responsavel: Optional[str] = None
    
    # CONTROLE
    ativo: bool = True
    criado_em: datetime
    atualizado_em: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "regra-soja-emergencia-umidade",
                "cultura": "soja",
                "fase": "emergencia",
                "parametro": "umidade",
                "minimo_alerta": 22,
                "maximo_alerta": 40,
                "minimo_critico": 20,
                "maximo_critico": 45,
                "duracao_minima_horas": 24,
                "titulo_alerta": "Umidade baixa durante emergência",
                "mensagem_produtor": "A zona está muito seca. Se não chover ou irrigar nas próximas 24h, a soja pode não germinar direito.",
                "impacto_na_fase": "Na emergência, umidade baixa causa falha de estande (plantas não nascem ou nascem fracas)",
                "acao_recomendada": "irrigar",
                "urgencia_acao": "24h",
                "template_explicacao_ia": "A umidade do solo em {zona} está em {valor}%, abaixo do ideal ({minimo_ideal}-{maximo_ideal}%) para a fase de emergência da soja.",
                "validado_por_agronomia": True,
                "agronomica_responsavel": "Dr. João Silva"
            }
        }


class AplicacaoRegra(BaseModel):
    """Resultado da aplicação de uma regra a um dado sensor"""
    regra_id: str
    sensor_id: str
    zona_id: str
    
    # CONTEXTO
    cultura: NomeCultura
    fase: FaseFenologica
    
    # DADO
    parametro: str
    valor_medido: float
    unidade: str
    timestamp_leitura: datetime
    
    # AVALIAÇÃO
    dentro_limites: bool
    tempo_fora_limite_horas: int = Field(0, description="Quantas horas consecutivas fora do limite")
    
    # RESULTADO
    alerta_disparado: bool
    severidade: Optional[str] = Field(None, description="critico, alto, medio, baixo")
    acao_recomendada: Optional[AcaoRecomendada] = None
    mensagem: Optional[str] = None
    
    # TIMESTAMPS
    avaliada_em: datetime
    proxima_reavaliacao_em: datetime


class AlertaGerado(BaseModel):
    """Alerta criado após aplicação de regra"""
    id: str
    regra_id: str
    sensor_id: str
    zona_id: str
    cultura: NomeCultura
    fase: FaseFenologica
    
    titulo: str
    mensagem_produtor: str
    impacto_na_fase: str
    
    severidade: str
    parametro: str
    valor_medido: float
    
    acao_recomendada: AcaoRecomendada
    urgencia_acao: str
    
    # IA irá preencher isso
    explicacao_ia: Optional[str] = None
    
    # Rastreabilidade
    criado_em: datetime
    status: str = "novo"
    reconhecido_em: Optional[datetime] = None
    resolvido_em: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class RegradeAlertaCreate(BaseModel):
    """Para criar nova regra"""
    cultura: NomeCultura
    fase: FaseFenologica
    parametro: str
    minimo_alerta: float
    maximo_alerta: float
    minimo_critico: float
    maximo_critico: float
    duracao_minima_horas: int
    titulo_alerta: str
    mensagem_produtor: str
    impacto_na_fase: str
    acao_recomendada: AcaoRecomendada
    urgencia_acao: str
    template_explicacao_ia: str


class BibliotecaRegras(BaseModel):
    """Biblioteca centralizada de regras (por cultura)"""
    cultura: NomeCultura
    regras: list[RegradeAlerta]
    total_regras: int
    regras_ativas: int
    ultima_atualizacao: datetime
    validada_por_agronomia: bool
