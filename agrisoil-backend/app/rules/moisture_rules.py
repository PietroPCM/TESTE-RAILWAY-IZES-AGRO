"""
Regras de avaliação de umidade do solo
Valores em percentual de umidade volumétrica
"""

def avaliar_umidade(umidade: float) -> dict:
    """
    Avalia o nível de umidade do solo e retorna recomendação.
    
    Args:
        umidade: Percentual de umidade volumétrica (0-100%)
    
    Returns:
        dict com nivel, mensagem e ação recomendada
    """
    if umidade is None:
        return {
            "nivel": "desconhecido",
            "valor": None,
            "mensagem": "Leitura de umidade não disponível",
            "acao": "Aguardando dados do sensor"
        }

    if umidade < 15:
        return {
            "nivel": "critico",
            "valor": umidade,
            "mensagem": "Solo muito seco. Risco de morte de plantas.",
            "acao": "Iniciar irrigação imediatamente",
            "alerta": True
        }

    if umidade < 25:
        return {
            "nivel": "alerta",
            "valor": umidade,
            "mensagem": "Solo seco. Recomendada irrigação urgente.",
            "acao": "Aumentar frequência de regas",
            "alerta": True
        }

    if umidade < 35:
        return {
            "nivel": "aviso",
            "valor": umidade,
            "mensagem": "Solo com umidade baixa. Próximo ponto crítico.",
            "acao": "Programar irrigação preventiva",
            "alerta": False
        }

    if 35 <= umidade <= 70:
        return {
            "nivel": "ok",
            "valor": umidade,
            "mensagem": "Umidade adequada para crescimento vegetal",
            "acao": "Manter regime de irrigação atual",
            "alerta": False
        }

    if umidade <= 80:
        return {
            "nivel": "aviso",
            "valor": umidade,
            "mensagem": "Solo com umidade elevada. Verificar drenagem.",
            "acao": "Monitorar para evitar encharcamento",
            "alerta": False
        }

    if 85 < umidade <= 90:
        return {
            "nivel": "alerta",
            "valor": umidade,
            "mensagem": "Solo encharcado. Risco de asfixia radicular e doenças fúngicas.",
            "acao": "Melhorar drenagem, suspender irrigação",
            "alerta": True
        }

    if umidade > 90:
        return {
            "nivel": "critico",
            "valor": umidade,
            "mensagem": "Solo extremamente saturado. Risco crítico.",
            "acao": "Intervir imediatamente com drenagem",
            "alerta": True
        }

    return {
        "nivel": "ok",
        "valor": umidade,
        "mensagem": "Umidade dentro da faixa ideal",
        "acao": "Continuar monitoramento",
        "alerta": False
    }
