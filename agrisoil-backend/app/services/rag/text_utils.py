"""Normalização e tokenização de texto para recuperação lexical (PT-BR)."""

from __future__ import annotations

import re
import unicodedata
from typing import List

_STOPWORDS = {
    "a", "o", "os", "as", "um", "uma", "uns", "umas", "de", "do", "da", "dos",
    "das", "e", "ou", "que", "com", "sem", "por", "para", "no", "na", "nos",
    "nas", "em", "ao", "aos", "se", "me", "minha", "meu", "meus", "minhas",
    "esse", "essa", "esses", "essas", "este", "esta", "isto", "isso", "aqui",
    "ele", "ela", "eles", "elas", "qual", "quais", "como", "esta", "estao",
    "ta", "tao", "ser", "estar", "ja", "tem", "ter", "the", "of", "and", "to",
    "is", "in", "for", "on", "muito", "mais", "menos", "meu", "sua", "seu",
}

# Sinônimos / linguagem informal -> termos canônicos agrícolas.
# Expandem a consulta para recuperar o tema correto mesmo em busca informal.
SINONIMOS = {
    "seco": ["umidade", "irrigacao", "agua"],
    "seca": ["umidade", "irrigacao", "agua"],
    "molhar": ["irrigacao", "umidade", "agua"],
    "molhada": ["umidade", "irrigacao"],
    "agua": ["umidade", "irrigacao"],
    "rega": ["irrigacao", "umidade"],
    "regar": ["irrigacao", "umidade"],
    "irriga": ["irrigacao", "umidade"],
    "irrigar": ["irrigacao", "umidade"],
    "acido": ["ph", "acidez", "calagem", "calcario"],
    "acida": ["ph", "acidez", "calagem", "calcario"],
    "acidez": ["ph", "calagem", "calcario"],
    "terra": ["solo"],
    "npk": ["nitrogenio", "fosforo", "potassio", "nutrientes"],
    "nutriente": ["nitrogenio", "fosforo", "potassio", "nutrientes"],
    "nutrientes": ["nitrogenio", "fosforo", "potassio"],
    "aduba": ["adubacao", "fertilizante", "nutrientes"],
    "adubo": ["adubacao", "fertilizante", "nutrientes"],
    "calibra": ["calibracao", "afericao", "sensor"],
    "calibrar": ["calibracao", "afericao", "sensor"],
    "barato": ["baixo custo", "limitacoes", "sensor"],
    "confiavel": ["calibracao", "limitacoes", "precisao"],
    "errado": ["calibracao", "afericao", "erro"],
    "condutividade": ["condutividade", "salinidade", "ce"],
    "ce": ["condutividade"],
    "batata": ["batata-doce", "batata doce"],
    "umidade": ["umidade", "irrigacao"],
}


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(ch for ch in sem_acento if not unicodedata.combining(ch))
    return sem_acento.lower()


def tokenizar(texto: str, remover_stopwords: bool = True) -> List[str]:
    normal = normalizar(texto)
    bruto = re.findall(r"[a-z0-9]+", normal)
    tokens = [t for t in bruto if len(t) >= 2]
    if remover_stopwords:
        tokens = [t for t in tokens if t not in _STOPWORDS]
    return tokens


def expandir_sinonimos(tokens: List[str]) -> List[str]:
    expandidos = list(tokens)
    for token in tokens:
        for extra in SINONIMOS.get(token, []):
            expandidos.extend(tokenizar(extra, remover_stopwords=False))
    # remove duplicatas preservando ordem
    vistos = []
    for token in expandidos:
        if token not in vistos:
            vistos.append(token)
    return vistos
