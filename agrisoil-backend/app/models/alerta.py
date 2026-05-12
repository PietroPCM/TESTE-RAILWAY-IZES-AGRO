"""
Modelo de dados para Alertas
Sistema de histórico e gestão de alertas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class SeveridadeAlerta(str, Enum):
    """Níveis de severidade dos alertas"""
    CRITICO = "critico"  # Requer ação imediata
    ALTO = "alto"  # Atenção urgente
    MEDIO = "medio"  # Atenção necessária
    BAIXO = "baixo"  # Informativo


class StatusAlerta(str, Enum):
    """Status do alerta"""
    ATIVO = "ativo"  # Alerta ativo
    RECONHECIDO = "reconhecido"  # Usuário visualizou
    RESOLVIDO = "resolvido"  # Problema resolvido
    IGNORADO = "ignorado"  # Usuário optou por ignorar


class TipoAlerta(str, Enum):
    """Tipo de parâmetro que gerou o alerta"""
    PH = "ph"
    UMIDADE = "umidade"
    TEMPERATURA = "temperatura"
    NITROGENIO = "nitrogenio"
    FOSFORO = "fosforo"
    POTASSIO = "potassio"
    CONDUTIVIDADE = "condutividade"
    SISTEMA = "sistema"  # Alertas do sistema (sensor offline, etc)


class AlertaCreate(BaseModel):
    """Modelo para criar um alerta"""
    sensor_id: str
    leitura_id: Optional[int] = None
    tipo: TipoAlerta
    severidade: SeveridadeAlerta
    titulo: str = Field(..., max_length=200)
    mensagem: str
    valor_medido: Optional[float] = None
    valor_referencia: Optional[str] = None  # Ex: "pH ideal: 6.0-7.0"
    recomendacao: Optional[str] = None


class AlertaResponse(BaseModel):
    """Modelo de resposta de alerta"""
    id: int
    sensor_id: str
    sensor_nome: Optional[str] = None
    cliente_id: str
    leitura_id: Optional[int]
    tipo: TipoAlerta
    severidade: SeveridadeAlerta
    status: StatusAlerta
    titulo: str
    mensagem: str
    valor_medido: Optional[float]
    valor_referencia: Optional[str]
    recomendacao: Optional[str]
    criado_em: datetime
    reconhecido_em: Optional[datetime]
    resolvido_em: Optional[datetime]
    notificacao_enviada: bool
    
    class Config:
        from_attributes = True


class AlertaUpdate(BaseModel):
    """Modelo para atualizar status do alerta"""
    status: StatusAlerta
    observacao: Optional[str] = None


class PreferenciasNotificacao(BaseModel):
    """Preferências de notificação do usuário"""
    email_ativo: bool = True
    email_severidade_minima: SeveridadeAlerta = SeveridadeAlerta.ALTO
    
    # Tipos de alertas que deseja receber
    alertas_ph: bool = True
    alertas_umidade: bool = True
    alertas_temperatura: bool = True
    alertas_npk: bool = True
    alertas_sistema: bool = True
    
    # Frequência (evitar spam)
    agrupar_alertas: bool = True  # Enviar resumo ao invés de individual
    intervalo_minimo_minutos: int = 60  # Não enviar mais de 1x/hora


class ResumoAlertas(BaseModel):
    """Resumo de alertas para dashboard"""
    total_ativos: int
    criticos: int
    altos: int
    medios: int
    baixos: int
    nao_reconhecidos: int
    ultimas_24h: int
    por_tipo: dict[str, int]
    alertas_recentes: List[AlertaResponse]
