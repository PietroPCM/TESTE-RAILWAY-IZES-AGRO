"""
Regras de avaliação de pH do solo
Baseado em padrões agronômicos internacionais
"""

def avaliar_ph(ph: float) -> dict:
    """
    Avalia o nível de pH do solo e retorna recomendação.
    
    Args:
        ph: Valor de pH (escala 0-14)
    
    Returns:
        dict com nivel, mensagem e ação recomendada
    """
    if ph is None:
        return {
            "nivel": "desconhecido",
            "valor": None,
            "mensagem": "Leitura de pH não disponível",
            "acao": "Aguardando dados do sensor"
        }

    if ph < 4.5:
        return {
            "nivel": "critico",
            "valor": ph,
            "mensagem": "Solo extremamente ácido. Risco de toxidez de alumínio.",
            "acao": "Aplicar calcário imediatamente",
            "alerta": True
        }

    if ph < 5.5:
        return {
            "nivel": "critico",
            "valor": ph,
            "mensagem": "Solo muito ácido. Recomendada calagem.",
            "acao": "Elevar pH com aplicação de calcário",
            "alerta": True
        }

    if ph < 6.0:
        return {
            "nivel": "alerta",
            "valor": ph,
            "mensagem": "pH baixo. Pode comprometer disponibilidade de nutrientes.",
            "acao": "Considerar aplicação leve de calcário",
            "alerta": False
        }

    if 6.0 <= ph <= 7.5:
        return {
            "nivel": "ok",
            "valor": ph,
            "mensagem": "pH adequado para a maioria das culturas",
            "acao": "Manter monitoramento",
            "alerta": False
        }

    if ph <= 8.5:
        return {
            "nivel": "alerta",
            "valor": ph,
            "mensagem": "Solo ligeiramente alcalino. Verificar disponibilidade de micronutrientes.",
            "acao": "Monitorar disponibilidade de Fe, Zn, Mn",
            "alerta": False
        }

    if ph > 8.5:
        return {
            "nivel": "critico",
            "valor": ph,
            "mensagem": "Solo muito alcalino. Risco de deficiência de micronutrientes.",
            "acao": "Considerar aplicação de enxofre ou adubação foliar",
            "alerta": True
        }

    return {
        "nivel": "ok",
        "valor": ph,
        "mensagem": "pH dentro da faixa aceitável",
        "acao": "Continuar monitoramento regular",
        "alerta": False
    }
