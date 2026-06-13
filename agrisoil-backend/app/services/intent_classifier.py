"""
Classificação de intenção da IA agro do IZES.

Substitui a antiga lista rígida de palavras-chave (que jogava perguntas
naturais em ``fora_escopo``) por uma classificação por sinais combinados:

- entidades agrícolas e do cliente (áreas, canteiros, sensores, leituras...);
- possessivos ("minha", "meus");
- linguagem de situação/status ("como está", "qual está pior", "tem algo errado");
- referências contextuais / dêixis ("esse", "aqui", "ele", "o outro");
- comparação e superlativo ("qual", "pior", "mais seca");
- conhecimento geral agro ("o que é pH", "como funciona irrigação");
- sinais externos fortes (capital, java, futebol, filme...).

Decide entre 4 modos usando também ``cliente_id`` e ``sensor_id``.
Não chama OpenAI. Tolera erros de digitação e linguagem informal.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

MODO_FORA_ESCOPO = "fora_escopo"
MODO_AGRO_GERAL = "agro_geral"
MODO_AGRO_COM_DADOS = "agro_com_dados"
MODO_ESCLARECIMENTO = "esclarecimento"


def _norm(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(ch for ch in sem_acento if not unicodedata.combining(ch))
    return sem_acento.lower().strip()


# Entidades que se referem à situação real do cliente (áreas/dispositivos).
ENTIDADES_DADOS = {
    "area", "areas", "canteiro", "canteiros", "talhao", "talhoes", "talhoe",
    "estufa", "estufas", "propriedade", "propriedades", "lavoura", "lavouras",
    "plantacao", "plantio", "horta", "hortas", "sensor", "sensores", "leitura",
    "leituras", "ponto", "pontos", "cultivo", "roca", "roça",
}

# Culturas: agro, mas só viram "com dados" se houver posse/status/dêixis.
CULTURAS = {
    "soja", "milho", "batata", "batata-doce", "feijao", "arroz", "trigo",
    "cafe", "mandioca", "cana", "algodao", "tomate", "hortalica", "hortalicas",
}

POSSESSIVOS = {
    "minha", "minhas", "meu", "meus", "mina", "minas", "nossa", "nossas",
    "nosso", "nossos",
}

# Dêixis / referências contextuais (sem nomear a entidade).
DEIXIS = {
    "esse", "essa", "esses", "essas", "este", "desse", "deste", "nesse",
    "neste", "aqui", "ele", "ela",
}

# Frases de status/situação (verificadas por substring no texto normalizado).
FRASES_STATUS = (
    "como esta", "como estao", "como ta", "como tao", "como tudo",
    "esta bom", "ta bom", "esta ruim", "ta ruim", "esta tudo", "ta tudo",
    "situacao", "tem algo", "alguma coisa errada", "algo errado",
    "algo de errado", "fora do normal", "precisa de atencao", "precisando",
    "precisa de mais atencao", "merece atencao", "qual esta pior",
    "esta pior", "o pior", "pior ponto", "qual e o pior", "o que faco",
    "o que fazer primeiro", "faco primeiro", "por onde comeco",
    "olha tudo", "olhar tudo", "ver tudo", "mostra tudo", "me mostra",
    "analise tudo", "analisa tudo", "analisar tudo", "analise minha",
    "analise meus", "analise minhas", "compara", "comparar", "compare",
    "o outro", "a outra", "qual area", "qual sensor", "qual canteiro",
    "qual cantero", "qual o pior", "esta seca", "mais seca", "mais seco",
    "esta errado", "esta errada",
)

# Intenção explícita de irrigação do próprio cliente.
FRASES_IRRIGACAO_DADOS = (
    "preciso irrigar", "precisa irrigar", "preciso irriga", "precisa irriga",
    "devo irrigar", "irrigar agora", "preciso molhar", "precisa molhar",
    "preciso regar", "precisa regar",
)

# Padrões de pergunta de conhecimento geral.
FRASES_GERAL = (
    "o que e", "o que significa", "como funciona", "como plantar",
    "como se planta", "para que serve", "qual a importancia",
    "qual e a importancia", "como identificar", "como medir", "como calcular",
    "por que", "porque calibrar", "substitui analise", "substitui a analise",
    "como funciona a", "quais sao as limitacoes", "como funciona o",
)

# Termos agro amplos (conhecimento geral).
TERMOS_AGRO = {
    "agro", "agricola", "agricultura", "agronom", "rural", "produtor",
    "colheita", "cultivar", "cultura", "safra", "semente", "sementes",
    "germinacao", "solo", "manejo", "irrigacao", "irrigar", "adubo",
    "adubacao", "fertilizante", "corretivo", "calagem", "calcario", "acidez",
    "ph", "nitrogenio", "fosforo", "potassio", "npk", "nutriente",
    "nutrientes", "praga", "pragas", "fungo", "fungos", "doenca", "umidade",
    "condutividade", "calibracao", "calibrar", "sensor", "sensores", "gado",
    "pecuaria", "animal", "animais", "vaca", "vacas", "boi", "leite",
    "reproducao", "ordenha", "geada", "seca", "clima", "lagarta", "pulgao",
    "produtividade", "fenologia",
}

# Sinais externos fortes (fora do agro).
TERMOS_FORA = {
    "capital", "italia", "franca", "paris", "roma", "copa", "futebol",
    "jogo", "campeonato", "politica", "presidente", "eleicao", "celebridade",
    "piada", "filme", "filmes", "musica", "cantor", "novela", "seriado",
    "java", "javascript", "python", "html", "css", "codigo", "programacao",
    "programa", "redacao", "fisica", "quantica", "matematica", "equacao",
    "quimica", "historia", "geografia", "receita",
}


def _tem_termo(texto_norm: str, conjunto) -> bool:
    palavras = set(re.findall(r"[a-z0-9-]+", texto_norm))
    if palavras & conjunto:
        return True
    # Termos compostos (com espaço ou hífen) são checados por substring.
    return any(t in texto_norm for t in conjunto if " " in t or "-" in t)


def _tem_frase(texto_norm: str, frases) -> bool:
    return any(f in texto_norm for f in frases)


def classificar(
    pergunta: str,
    cliente_id: Optional[str] = None,
    sensor_id: Optional[str] = None,
    tem_dados_cliente: Optional[bool] = None,
) -> str:
    """Classifica a pergunta em um dos quatro modos.

    ``cliente_id`` e ``sensor_id`` ajudam a desambiguar perguntas curtas,
    informais ou contextuais. ``tem_dados_cliente`` é opcional e, quando
    informado, evita prometer análise sem dados.
    """
    texto = _norm(pergunta)
    if not texto:
        return MODO_ESCLARECIMENTO if (cliente_id or sensor_id) else MODO_FORA_ESCOPO

    tem_externo = _tem_termo(texto, TERMOS_FORA)
    tem_entidade = _tem_termo(texto, ENTIDADES_DADOS)
    tem_cultura = _tem_termo(texto, CULTURAS)
    tem_agro = tem_entidade or tem_cultura or _tem_termo(texto, TERMOS_AGRO)
    tem_possessivo = _tem_termo(texto, POSSESSIVOS)
    tem_deixis = _tem_termo(texto, DEIXIS)
    tem_status = _tem_frase(texto, FRASES_STATUS)
    tem_irrigacao_dados = _tem_frase(texto, FRASES_IRRIGACAO_DADOS)
    eh_geral = _tem_frase(texto, FRASES_GERAL)

    # 1) Claramente fora do escopo agro.
    if tem_externo and not (tem_agro or tem_entidade or tem_possessivo or tem_status):
        return MODO_FORA_ESCOPO

    # 2) Contexto de um sensor específico: referências apontam para ele.
    if sensor_id:
        somente_conhecimento = eh_geral and not (
            tem_possessivo or tem_status or tem_deixis or tem_entidade
            or tem_irrigacao_dados
        )
        if somente_conhecimento:
            return MODO_AGRO_GERAL
        return MODO_AGRO_COM_DADOS

    # 3) Intenção de usar os dados reais do cliente (sinais de texto).
    intencao_dados = (
        tem_irrigacao_dados
        or (tem_possessivo and (tem_entidade or tem_cultura or tem_status or tem_agro))
        or (tem_entidade and not eh_geral)
        or (tem_deixis and (tem_entidade or tem_cultura or tem_agro))
        or (tem_status and (tem_entidade or tem_cultura or tem_possessivo))
    )
    if intencao_dados:
        return MODO_AGRO_COM_DADOS

    # 4) Status / dêixis ambíguos (sem nomear entidade): usar contexto.
    if tem_status or tem_deixis:
        if cliente_id:
            return MODO_AGRO_COM_DADOS  # tenta visão geral do cliente
        return MODO_ESCLARECIMENTO

    # 5) Conhecimento agro geral.
    if tem_agro or eh_geral:
        return MODO_AGRO_GERAL

    # 6) Sem sinais claros: favorecer agro quando há contexto do cliente.
    if cliente_id or sensor_id:
        return MODO_ESCLARECIMENTO
    return MODO_FORA_ESCOPO
