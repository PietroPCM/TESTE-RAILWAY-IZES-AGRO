"""
Cálculo central de metadados da resposta: origem, validade e confiança.

Centraliza o que antes estava hardcoded/espalhado:
- ``origem`` reflete os recursos realmente usados;
- ``validade`` depende do tipo de resposta (não aplica "Previsão muda
  frequentemente" universalmente);
- ``confianca`` é normalizada (ausência != zero) e penalizada por incerteza.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional

# Confiança neutra quando o modelo não informa um valor utilizável.
CONFIANCA_BASE = 0.6


def calcular_origem(
    *,
    usou_openai: bool,
    usou_dados: bool = False,
    usou_clima: bool = False,
    usou_rag: bool = False,
    fallback: bool = False,
    regra_contextual: bool = False,
    fora_escopo: bool = False,
    apenas_clima: bool = False,
) -> str:
    """Deriva a string de origem a partir dos recursos efetivamente usados."""
    if fora_escopo:
        return "fora_escopo"
    if regra_contextual:
        return "regra_contextual"
    if apenas_clima and not usou_openai:
        return "servico_climatico"
    if fallback or not usou_openai:
        return "fallback_local"

    sufixos = []
    if usou_dados:
        sufixos.append("dados")
    if usou_clima:
        sufixos.append("clima")
    if usou_rag:
        sufixos.append("rag")

    if not sufixos:
        return "openai"
    if len(sufixos) == 1:
        return f"openai_com_{sufixos[0]}"
    corpo = "_".join(sufixos[:-1]) + "_e_" + sufixos[-1]
    return f"openai_com_{corpo}"


def calcular_validade(
    modo: str,
    *,
    usou_clima: bool = False,
    tem_dados: bool = False,
    timestamp_leitura: Optional[datetime] = None,
    agora: Optional[datetime] = None,
) -> Optional[dict]:
    """Validade conforme a natureza da resposta. Pode ser None (sem validade)."""
    agora = agora or datetime.now()

    if usou_clima or modo == "clima":
        return {
            "ate": agora + timedelta(hours=3),
            "razao": "Previsão climática sujeita a alterações.",
            "atualizado_em": agora,
        }

    if modo == "agro_com_dados" and tem_dados:
        validade = {
            "ate": agora + timedelta(hours=6),
            "razao": "Condições podem mudar com novas leituras, chuva, irrigação ou manejo.",
        }
        if timestamp_leitura:
            validade["leitura_em"] = timestamp_leitura
        return validade

    # agro_geral, esclarecimento, fora_escopo, erro técnico: sem validade temporal.
    return None


def normalizar_confianca(
    valor: object,
    *,
    base: float = CONFIANCA_BASE,
    penalidades: Optional[dict] = None,
) -> float:
    """Normaliza confiança para [0,1].

    - valor ausente/NaN/inválido -> base (default neutro documentado, não zero);
    - aplica penalidades por incerteza (dados ausentes, leitura antiga, RAG fraco,
      clima indisponível, recomendação que exige validação).
    """
    try:
        conf = float(valor)
        if math.isnan(conf) or math.isinf(conf):
            conf = base
        elif conf <= 0.0:
            # 0 quase sempre significa "modelo não preencheu"; usa base neutra.
            conf = base
    except (TypeError, ValueError):
        conf = base

    penalidades = penalidades or {}
    fatores = {
        "dados_ausentes": 0.2,
        "leitura_antiga": 0.1,
        "rag_fraco": 0.1,
        "clima_indisponivel": 0.15,
        "requer_validacao": 0.1,
    }
    for chave, ativo in penalidades.items():
        if ativo:
            conf -= fatores.get(chave, 0.0)

    return max(0.05, min(conf, 1.0))
