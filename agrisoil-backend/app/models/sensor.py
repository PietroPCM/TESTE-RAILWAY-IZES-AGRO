"""
Modelos de Sensor com Localização
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class LocalizacaoSensor(BaseModel):
    """Localização geográfica do sensor"""
    latitude: float
    longitude: float
    propriedade: str
    municipio: str
    estado: str
    local_especifico: Optional[str] = None  # Ex: "Talhão A", "Estufa 1"


class Sensor(BaseModel):
    """Modelo de Sensor com localização"""
    sensor_id: str
    cliente_id: str
    nome: str
    tipo: str  # "solo", "ar", "água"
    localizacao: LocalizacaoSensor
    ativo: bool = True
    criado_em: datetime = datetime.now()
    ultima_atualizacao: datetime = datetime.now()

    class Config:
        from_attributes = True


class ClienteConfig(BaseModel):
    """Configuração de cliente para receber dados de clima"""
    cliente_id: str
    nome: str
    email_contato: str
    chave_api_clima: Optional[str] = None  # Para usar API própria
    provedor_clima: str = "openweathermap"  # openweathermap, weatherapi, inmet
    frequencia_atualizacao_minutos: int = 30
    receber_alertas: bool = True
    webhook_url: Optional[str] = None  # URL para enviar dados ao mobile
    app_token: Optional[str] = None  # Token para autenticação do app mobile
    
    class Config:
        from_attributes = True
