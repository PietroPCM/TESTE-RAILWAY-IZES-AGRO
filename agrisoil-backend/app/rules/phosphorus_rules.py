"""
Regras de avaliação de Fósforo (P) no solo
Baseado em padrões agronômicos para NPK
Valores em mg/kg (ppm)
"""

def avaliar_fosforo(phosphorus: float) -> dict:
    """
    Avalia o nível de Fósforo no solo e retorna recomendação.
    
    Faixas de referência (mg/kg):
    - Muito Baixo: < 5
    - Baixo: 5-10
    - Médio: 10-20
    - Adequado: 20-40
    - Alto: > 40
    
    Args:
        phosphorus: Valor de Fósforo em mg/kg (ppm)
    
    Returns:
        dict com nível, mensagem e ação recomendada
    """
    if phosphorus is None:
        return {
            "nivel": "desconhecido",
            "valor": None,
            "mensagem": "Leitura de Fósforo não disponível",
            "acao": "Aguardando dados do sensor",
            "alerta": False
        }

    if phosphorus < 5:
        return {
            "nivel": "critico",
            "valor": phosphorus,
            "mensagem": "Fósforo muito baixo. Compromete desenvolvimento radicular e floração.",
            "acao": "Aplicar fosfatagem urgente (superfosfato simples/triplo, MAP)",
            "alerta": True
        }

    if phosphorus < 10:
        return {
            "nivel": "alerta",
            "valor": phosphorus,
            "mensagem": "Fósforo baixo. Pode limitar produtividade.",
            "acao": "Planejar adubação fosfatada de base",
            "alerta": True
        }

    if phosphorus < 20:
        return {
            "nivel": "ok",
            "valor": phosphorus,
            "mensagem": "Fósforo em nível médio. Adequado para manutenção.",
            "acao": "Manter adubação de manutenção",
            "alerta": False
        }

    if 20 <= phosphorus <= 40:
        return {
            "nivel": "ok",
            "valor": phosphorus,
            "mensagem": "Fósforo adequado para alta produtividade",
            "acao": "Continuar monitoramento regular",
            "alerta": False
        }

    if phosphorus > 40:
        return {
            "nivel": "alerta",
            "valor": phosphorus,
            "mensagem": "Fósforo alto. Pode interferir na absorção de micronutrientes (Zn, Fe).",
            "acao": "Suspender fosfatagem, monitorar micronutrientes",
            "alerta": False
        }

    return {
        "nivel": "ok",
        "valor": phosphorus,
        "mensagem": "Fósforo dentro da faixa aceitável",
        "acao": "Continuar monitoramento regular",
        "alerta": False
    }
