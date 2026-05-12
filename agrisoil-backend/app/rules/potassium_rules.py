"""
Regras de avaliação de Potássio (K) no solo
Baseado em padrões agronômicos para NPK
Valores em mg/kg (ppm)
"""

def avaliar_potassio(potassium: float) -> dict:
    """
    Avalia o nível de Potássio no solo e retorna recomendação.
    
    Faixas de referência (mg/kg):
    - Muito Baixo: < 30
    - Baixo: 30-60
    - Médio: 60-120
    - Adequado: 120-200
    - Alto: > 200
    
    Args:
        potassium: Valor de Potássio em mg/kg (ppm)
    
    Returns:
        dict com nível, mensagem e ação recomendada
    """
    if potassium is None:
        return {
            "nivel": "desconhecido",
            "valor": None,
            "mensagem": "Leitura de Potássio não disponível",
            "acao": "Aguardando dados do sensor",
            "alerta": False
        }

    if potassium < 30:
        return {
            "nivel": "critico",
            "valor": potassium,
            "mensagem": "Potássio muito baixo. Compromete qualidade de frutos e resistência a doenças.",
            "acao": "Aplicar adubação potássica urgente (cloreto de K, sulfato de K)",
            "alerta": True
        }

    if potassium < 60:
        return {
            "nivel": "alerta",
            "valor": potassium,
            "mensagem": "Potássio baixo. Pode afetar enchimento de grãos e qualidade.",
            "acao": "Planejar adubação potássica de cobertura",
            "alerta": True
        }

    if potassium < 120:
        return {
            "nivel": "ok",
            "valor": potassium,
            "mensagem": "Potássio em nível médio. Adequado para manutenção.",
            "acao": "Manter adubação de manutenção",
            "alerta": False
        }

    if 120 <= potassium <= 200:
        return {
            "nivel": "ok",
            "valor": potassium,
            "mensagem": "Potássio adequado para alta produtividade",
            "acao": "Continuar monitoramento regular",
            "alerta": False
        }

    if potassium > 200:
        return {
            "nivel": "alerta",
            "valor": potassium,
            "mensagem": "Potássio alto. Excesso pode causar desequilíbrio com Ca e Mg.",
            "acao": "Suspender adubação potássica, verificar relação K/Ca/Mg",
            "alerta": False
        }

    return {
        "nivel": "ok",
        "valor": potassium,
        "mensagem": "Potássio dentro da faixa aceitável",
        "acao": "Continuar monitoramento regular",
        "alerta": False
    }
