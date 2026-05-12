"""
Modelos de dados para leituras de sensores
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class Leitura(BaseModel):
    """Modelo para uma leitura de sensor"""
    ph: Optional[float] = None
    soilMoisture: Optional[float] = None
    temperature: Optional[float] = None
    electricalConductivity: Optional[float] = None
    # Macronutrientes NPK (mg/kg ou ppm)
    nitrogen: Optional[float] = None  # Nitrogênio (N)
    phosphorus: Optional[float] = None  # Fósforo (P)
    potassium: Optional[float] = None  # Potássio (K)


class ResultadoLeitura(BaseModel):
    """Modelo para resultado da avaliação de uma leitura"""
    sensor_id: str
    cliente: str
    timestamp: datetime
    valores_lidos: Leitura
    avaliacoes: dict
    alerta_ativo: bool


class ResultadoRegra(BaseModel):
    """Modelo para resultado de uma avaliação de regra"""
    nivel: str
    valor: Optional[float]
    mensagem: str
    acao: str
    alerta: bool
