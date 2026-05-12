"""
CAMADA 2: FASE DA CULTURA - Detecção automática da fase fenológica
Determina em qual estágio da cultura estamos
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
from app.models.contexto_fixo import FaseFenologica, NomeCultura


class MetodoDeteccaoFase(str, Enum):
    """Como determinar a fase atual"""
    DATA_PLANTIO = "data_plantio"  # Baseado em dias após plantio
    GRAUS_DIAS = "graus_dias"  # Soma térmica (GDU)
    OBSERVACAO_CAMPO = "observacao_campo"  # Agrônomo validou
    API_EXTERNA = "api_externa"  # Integração com API agrometeorológica


class FaseAtual(BaseModel):
    """Estado atual da cultura em uma zona"""
    zona_id: str
    cultura: NomeCultura
    fase: FaseFenologica
    
    # Como foi determinada
    metodo: MetodoDeteccaoFase
    
    # Datas
    data_plantio: datetime
    dias_apos_plantio: int
    data_inicio_fase: datetime
    data_prevista_proxima_fase: datetime
    
    # Temperatura (para método GDU)
    graus_dias_acumulados: Optional[float] = Field(None, description="Graus-dia útil acumulado")
    graus_dias_necessarios: Optional[float] = Field(None, description="GDU até próxima fase")
    
    # Confiança
    certeza_fase_percentual: float = Field(..., description="0-100% de confiança na fase detectada")
    validado_por_agronomia: bool = False
    
    # Timestamps
    detectado_em: datetime
    ultima_validacao: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "zona_id": "zona-001",
                "cultura": "soja",
                "fase": "emergencia",
                "metodo": "data_plantio",
                "data_plantio": "2025-10-17T08:00:00Z",
                "dias_apos_plantio": 15,
                "data_inicio_fase": "2025-10-17T08:00:00Z",
                "data_prevista_proxima_fase": "2025-11-10T08:00:00Z",
                "graus_dias_acumulados": 120.5,
                "graus_dias_necessarios": 80,
                "certeza_fase_percentual": 95,
                "validado_por_agronomia": True
            }
        }


class FaseAtualCreate(BaseModel):
    """Para atualizar fase manualmente"""
    data_plantio: datetime
    fase_observada: Optional[FaseFenologica] = None
    observacoes: Optional[str] = None
    validado_por_agronomia: bool = False


class DeteccaoFaseResponse(BaseModel):
    """Resposta da detecção de fase"""
    zona_id: str
    fase_atual: FaseAtual
    proxima_fase_em_dias: int
    status: str = Field(..., description="Em dia, adiantado, atrasado")
    alerta_fase: Optional[str] = None  # Aviso se fase parece incorreta


class HistoricoFase(BaseModel):
    """Registro de transições de fase"""
    zona_id: str
    fase_anterior: FaseFenologica
    fase_nova: FaseFenologica
    data_transicao: datetime
    dias_na_fase_anterior: int
    metodo: MetodoDeteccaoFase
    validado: bool
