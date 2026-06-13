"""
Resolução segura da localização para perguntas climáticas.

Prioridade (Etapa 4):
1. localização escrita na pergunta (mantida como descrição; sem geocodificar);
2. coordenadas do sensor informado;
3. coordenadas da propriedade/cliente (primeiro sensor com coordenadas);
4. coordenadas consistentes dos sensores do cliente;
5. None -> a camada superior pede município/estado.

Nunca inventa coordenadas e nunca usa localização de outro cliente
(os sensores recebidos já são apenas do cliente).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class LocalizacaoResolvida:
    latitude: float
    longitude: float
    descricao: str
    origem: str  # "sensor" | "cliente"


def _coords(sensor) -> Optional[tuple]:
    loc = getattr(sensor, "localizacao", None) or {}
    lat = loc.get("latitude")
    lon = loc.get("longitude")
    if lat is None or lon is None:
        return None
    try:
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None


def _descricao(sensor, localizacao_texto: Optional[str]) -> str:
    if localizacao_texto:
        return localizacao_texto
    loc = getattr(sensor, "localizacao", None) or {}
    municipio = loc.get("municipio")
    estado = loc.get("estado")
    partes = [p for p in (municipio, estado) if p]
    if partes:
        return ", ".join(partes)
    return getattr(sensor, "propriedade", None) or "propriedade do cliente"


def resolver_localizacao(
    sensores: List,
    sensor_id: Optional[str] = None,
    localizacao_texto: Optional[str] = None,
) -> Optional[LocalizacaoResolvida]:
    """Resolve coordenadas a partir dos sensores do cliente."""
    if not sensores:
        return None

    # 2) Sensor informado explicitamente.
    if sensor_id:
        for sensor in sensores:
            if getattr(sensor, "sensor_id", None) == sensor_id:
                c = _coords(sensor)
                if c:
                    return LocalizacaoResolvida(c[0], c[1], _descricao(sensor, localizacao_texto), "sensor")

    # 3/4) Primeiro sensor do cliente com coordenadas válidas.
    for sensor in sensores:
        c = _coords(sensor)
        if c:
            return LocalizacaoResolvida(c[0], c[1], _descricao(sensor, localizacao_texto), "cliente")

    return None
