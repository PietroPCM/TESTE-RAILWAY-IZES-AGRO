"""
Regras de avaliação de Nitrogênio (N) no solo
Baseado em padrões agronômicos para NPK
Valores em mg/kg (ppm)
"""

def avaliar_nitrogenio(nitrogen: float) -> dict:
    """
    Avalia o nível de Nitrogênio no solo e retorna recomendação.
    
    Faixas de referência (mg/kg):
    - Muito Baixo: < 20
    - Baixo: 20-40
    - Médio: 40-60
    - Adequado: 60-100
    - Alto: > 100
    
    Args:
        nitrogen: Valor de Nitrogênio em mg/kg (ppm)
    
    Returns:
        dict com nível, mensagem e ação recomendada
    """
    if nitrogen is None:
        return {
            "nivel": "desconhecido",
            "valor": None,
            "mensagem": "Leitura de Nitrogênio não disponível",
            "acao": "Aguardando dados do sensor",
            "alerta": False
        }

    if nitrogen < 20:
        return {
            "nivel": "critico",
            "valor": nitrogen,
            "mensagem": "Nitrogênio muito baixo. Planta pode apresentar clorose e crescimento reduzido.",
            "acao": "Aplicar adubação nitrogenada urgente (ureia, sulfato de amônio)",
            "alerta": True
        }

    if nitrogen < 40:
        return {
            "nivel": "alerta",
            "valor": nitrogen,
            "mensagem": "Nitrogênio baixo. Pode comprometer desenvolvimento vegetativo.",
            "acao": "Planejar adubação nitrogenada de cobertura",
            "alerta": True
        }

    if nitrogen < 60:
        return {
            "nivel": "ok",
            "valor": nitrogen,
            "mensagem": "Nitrogênio em nível médio. Monitorar conforme demanda da cultura.",
            "acao": "Manter adubação de manutenção",
            "alerta": False
        }

    if 60 <= nitrogen <= 100:
        return {
            "nivel": "ok",
            "valor": nitrogen,
            "mensagem": "Nitrogênio adequado para a maioria das culturas",
            "acao": "Continuar monitoramento regular",
            "alerta": False
        }

    if nitrogen > 100:
        return {
            "nivel": "alerta",
            "valor": nitrogen,
            "mensagem": "Nitrogênio alto. Excesso pode causar crescimento vegetativo excessivo.",
            "acao": "Evitar adubação nitrogenada temporariamente, monitorar lixiviação",
            "alerta": False
        }

    return {
        "nivel": "ok",
        "valor": nitrogen,
        "mensagem": "Nitrogênio dentro da faixa aceitável",
        "acao": "Continuar monitoramento regular",
        "alerta": False
    }
