"""
Modelos de dados de clima e previsao.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, model_serializer

from app.utils.datetime_utils import serialize_utc_payload


class DadosClimaAtual(BaseModel):
    """Dados climaticos atuais."""

    cidade: Optional[str] = None
    temperatura_celsius: float
    temperatura_maxima: Optional[float] = None
    temperatura_minima: Optional[float] = None
    sensacao_termica: Optional[float] = None
    umidade_relativa: int
    pressao_atm: float
    velocidade_vento: float
    direcao_vento: Optional[str] = None
    cobertura_nuvens: int
    precipitacao: float
    indice_uv: Optional[float] = None
    visibilidade: Optional[float] = None
    condicao: str
    descricao: str
    icone: str


class PrevisaoClima(BaseModel):
    """Previsao de clima para um dia."""

    data: datetime
    temperatura_maxima: float
    temperatura_minima: float
    condicao: str
    descricao: str
    precipitacao_probabilidade: int
    precipitacao_mm: float
    umidade: int
    velocidade_vento: float
    icone: str


class ClimaCompletoSensor(BaseModel):
    """Dados completos de clima para um sensor."""

    sensor_id: str
    cliente_id: str
    localizacao: dict
    timestamp: datetime
    clima_atual: DadosClimaAtual
    previsao_proximas_horas: List[PrevisaoClima]
    indice_risco_geada: Optional[float] = None
    indice_risco_seca: Optional[float] = None
    alerta_clima: Optional[str] = None

    class Config:
        from_attributes = True

    @model_serializer(mode="wrap")
    def serialize_model(self, handler):
        return serialize_utc_payload(handler(self))


class RespostaMobileClima(BaseModel):
    """Resposta formatada para app mobile."""

    id_envio: str
    cliente_id: str
    sensor_id: str
    propriedade: str
    municipio: str
    local: str
    timestamp: datetime
    temperatura_atual: float
    condicao: str
    umidade: int
    vento_velocidade: float
    chuva_probabilidade: int
    previsao_dia: List[PrevisaoClima]
    alerta: Optional[str] = None
    recomendacoes: List[str]

    @model_serializer(mode="wrap")
    def serialize_model(self, handler):
        return serialize_utc_payload(handler(self))


class LocalizacaoClimaAtual(BaseModel):
    latitude: float
    longitude: float
    cidade: Optional[str] = None


class ClimaAtualResumo(BaseModel):
    temperatura: float
    sensacao_termica: Optional[float] = None
    umidade: int
    descricao: str
    vento: float


class PrevisaoResumoClima(BaseModel):
    resumo: str
    probabilidade_chuva: int
    precipitacao_mm: float


class AlertaClimaResumo(BaseModel):
    risco_geada: bool
    risco_seca: bool
    mensagem: str


class RespostaClimaAtualLocalizacao(BaseModel):
    localizacao: LocalizacaoClimaAtual
    clima_atual: ClimaAtualResumo
    previsao_resumo: Optional[PrevisaoResumoClima] = None
    alerta_clima: AlertaClimaResumo
