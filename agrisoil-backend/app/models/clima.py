"""
Modelos de dados de Clima e Previsão
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class DadosClimaAtual(BaseModel):
    """Dados climáticos atuais"""
    temperatura_celsius: float
    temperatura_maxima: Optional[float] = None
    temperatura_minima: Optional[float] = None
    sensacao_termica: Optional[float] = None
    umidade_relativa: int  # 0-100%
    pressao_atm: float  # hPa
    velocidade_vento: float  # m/s ou km/h
    direcao_vento: Optional[str] = None  # N, NE, E, SE, S, SO, O, NO
    cobertura_nuvens: int  # 0-100%
    precipitacao: float  # mm
    indice_uv: Optional[float] = None
    visibilidade: Optional[float] = None
    condicao: str  # "ensolarado", "nublado", "chuvoso", etc
    descricao: str
    icone: str  # Código do ícone para app mobile


class PrevisaoClima(BaseModel):
    """Previsão de clima para um dia"""
    data: datetime
    temperatura_maxima: float
    temperatura_minima: float
    condicao: str
    descricao: str
    precipitacao_probabilidade: int  # 0-100%
    precipitacao_mm: float
    umidade: int
    velocidade_vento: float
    icone: str


class ClimaCompletoSensor(BaseModel):
    """Dados completos de clima para um sensor"""
    sensor_id: str
    cliente_id: str
    localizacao: dict  # Contém latitude, longitude, local_especifico
    timestamp: datetime
    clima_atual: DadosClimaAtual
    previsao_proximas_horas: List[PrevisaoClima]  # Próximas 24h em intervalos
    indice_risco_geada: Optional[float] = None  # 0-100%
    indice_risco_seca: Optional[float] = None  # 0-100%
    alerta_clima: Optional[str] = None  # Ex: "Risco de geada", "Secura extrema"
    
    class Config:
        from_attributes = True


class RespostaMobileClima(BaseModel):
    """Resposta formatada para app mobile"""
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
    recomendacoes: List[str]  # Recomendações agrícolas baseadas no clima
