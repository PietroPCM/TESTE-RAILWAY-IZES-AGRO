"""
Regras de avaliação de temperatura do solo
Valores em graus Celsius
"""

def avaliar_temperatura(temperatura: float) -> dict:
    """
    Avalia o nível de temperatura do solo e retorna recomendação.
    
    Args:
        temperatura: Temperatura em graus Celsius
    
    Returns:
        dict com nivel, mensagem e ação recomendada
    """
    if temperatura is None:
        return {
            "nivel": "desconhecido",
            "valor": None,
            "mensagem": "Leitura de temperatura não disponível",
            "acao": "Aguardando dados do sensor"
        }

    if temperatura < 5:
        return {
            "nivel": "critico",
            "valor": temperatura,
            "mensagem": "Solo muito frio. Crescimento vegetativo inibido.",
            "acao": "Aguardar aquecimento natural ou usar proteção",
            "alerta": True
        }

    if temperatura < 10:
        return {
            "nivel": "alerta",
            "valor": temperatura,
            "mensagem": "Solo frio. Reduz metabolismo radicalar.",
            "acao": "Postergar plantio ou usar cobertura protetora",
            "alerta": True
        }

    if temperatura < 15:
        return {
            "nivel": "aviso",
            "valor": temperatura,
            "mensagem": "Solo com temperatura abaixo do ideal.",
            "acao": "Monitorar para volta ao intervalo ótimo",
            "alerta": False
        }

    if 18 <= temperatura <= 28:
        return {
            "nivel": "ok",
            "valor": temperatura,
            "mensagem": "Temperatura ideal para maioria das culturas",
            "acao": "Condições favoráveis para crescimento",
            "alerta": False
        }

    if temperatura <= 35:
        return {
            "nivel": "aviso",
            "valor": temperatura,
            "mensagem": "Solo aquecido. Aumentar monitoramento de umidade.",
            "acao": "Verificar necessidade de irrigação",
            "alerta": False
        }

    if temperatura <= 40:
        return {
            "nivel": "alerta",
            "valor": temperatura,
            "mensagem": "Solo muito quente. Risco de dano às raízes.",
            "acao": "Aumentar irrigação, usar mulch",
            "alerta": True
        }

    if temperatura <= 50:
        return {
            "nivel": "critico",
            "valor": temperatura,
            "mensagem": "Solo extremamente quente. Morte potencial de plantas.",
            "acao": "Aplicar técnicas urgentes de resfriamento",
            "alerta": True
        }

    return {
        "nivel": "ok",
        "valor": temperatura,
        "mensagem": "Temperatura dentro da faixa aceitável",
        "acao": "Continuar monitoramento",
        "alerta": False
    }
