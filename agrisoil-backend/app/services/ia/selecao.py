"""
Seleção de sensores/áreas conforme a entidade pedida na pergunta.

Usa metadados do próprio sensor (nome, tipo, local_específico, propriedade) —
nunca IDs fixos. Se a pergunta fala em "canteiros", não inclui uma área de soja.
Se o filtro não casar com nada, devolve todos (não esconde dados) sinalizando.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import List, Optional

from app.services.ia.decisao import CULTURAS, TIPOS_ENTIDADE, DecisaoIntencao


def _norm(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(ch for ch in sem_acento if not unicodedata.combining(ch))
    return sem_acento.lower()


def _haystack(sensor) -> str:
    partes = [
        getattr(sensor, "nome", "") or "",
        getattr(sensor, "tipo", "") or "",
        getattr(sensor, "local_especifico", "") or "",
        getattr(sensor, "propriedade", "") or "",
        getattr(sensor, "sensor_id", "") or "",
    ]
    loc = getattr(sensor, "localizacao", None)
    if isinstance(loc, dict):
        partes.append(str(loc.get("local_especifico") or ""))
    return _norm(" ".join(partes))


@dataclass
class ResultadoSelecao:
    sensores: list
    filtrado: bool
    motivo: str


# Tipos "amplos" não restringem (área/propriedade = visão geral; sensor/ponto = todos).
TIPOS_AMPLOS = {"area", "propriedade", "sensor", None}


def _casa_tipo(sensor_hay: str, tipo_entidade: str) -> bool:
    termos = {_norm(t) for t in TIPOS_ENTIDADE.get(tipo_entidade, set())}
    return any(t in sensor_hay for t in termos)


def _casa_cultura(sensor_hay: str, culturas: List[str]) -> bool:
    for cultura in culturas:
        termos = {_norm(t) for t in CULTURAS.get(cultura, {cultura})}
        if any(t in sensor_hay for t in termos):
            return True
    return False


def filtrar_sensores(sensores: list, decisao: DecisaoIntencao) -> ResultadoSelecao:
    """Filtra a lista de sensores pela entidade/cultura pedida na decisão."""
    if not sensores:
        return ResultadoSelecao(sensores=[], filtrado=False, motivo="sem sensores")

    tipo = decisao.tipo_entidade
    culturas = decisao.culturas or []

    aplica_tipo = tipo is not None and tipo not in TIPOS_AMPLOS
    aplica_cultura = bool(culturas)

    if not aplica_tipo and not aplica_cultura:
        return ResultadoSelecao(sensores=list(sensores), filtrado=False,
                                motivo="sem filtro de entidade (visão geral)")

    selecionados = []
    for sensor in sensores:
        hay = _haystack(sensor)
        ok_tipo = (not aplica_tipo) or _casa_tipo(hay, tipo)
        ok_cultura = (not aplica_cultura) or _casa_cultura(hay, culturas)
        if ok_tipo and ok_cultura:
            selecionados.append(sensor)

    if not selecionados:
        # Não esconder dados: se nada casou, devolve todos sinalizando.
        return ResultadoSelecao(sensores=list(sensores), filtrado=False,
                                motivo=f"nenhum sensor casou com {tipo or ''}/{culturas}; usando todos")

    alvo = tipo or (culturas[0] if culturas else "")
    return ResultadoSelecao(sensores=selecionados, filtrado=True,
                            motivo=f"filtrado por {alvo}")


# Mapa parâmetro -> chave na última leitura.
_CHAVE_LEITURA = {
    "umidade": "umidade", "ph": "ph", "nitrogenio": "nitrogenio",
    "fosforo": "fosforo", "potassio": "potassio", "temperatura": "temperatura",
    "condutividade": "condutividade",
}


def _valor_parametro(sensor, parametro: str):
    leitura = getattr(sensor, "ultima_leitura", None) or {}
    chave = _CHAVE_LEITURA.get(parametro)
    if not chave:
        return None
    valor = leitura.get(chave)
    try:
        return float(valor) if valor is not None else None
    except (TypeError, ValueError):
        return None


def destacar(sensores: list, parametro: str, preferir_menor: bool = True) -> Optional[dict]:
    """Identifica, a partir dos DADOS, qual sensor se destaca no parâmetro.

    Determinístico e baseado nos valores reais (não em IDs). Retorna o destaque
    e a lista comparada, ou None se não houver valores suficientes.
    """
    comparados = []
    for sensor in sensores:
        valor = _valor_parametro(sensor, parametro)
        if valor is not None:
            comparados.append({"sensor_id": getattr(sensor, "sensor_id", None),
                               "nome": getattr(sensor, "nome", None), "valor": valor})
    if not comparados:
        return None
    escolhido = (min if preferir_menor else max)(comparados, key=lambda c: c["valor"])
    return {
        "parametro": parametro,
        "criterio": "menor" if preferir_menor else "maior",
        "destaque": escolhido,
        "comparados": sorted(comparados, key=lambda c: c["valor"]),
    }
