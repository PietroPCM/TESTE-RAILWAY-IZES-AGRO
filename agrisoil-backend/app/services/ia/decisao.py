"""
Decisão estruturada de intenção da IA agro.

Em vez de retornar apenas uma string de modo, produz uma ``DecisaoIntencao``
que descreve: domínio, recursos necessários (dados do cliente, clima, RAG,
OpenAI), entidades mencionadas (tipo, culturas, parâmetros), se é comparação,
se há referência contextual e se precisa de esclarecimento.

A decisão é tomada UMA vez e não deve ser sobrescrita depois. Usa sinais
combinados (entidades + contexto + possessivos + dêixis + comparativos + IDs),
não uma lista de frases prontas.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional

from app.services import intent_classifier as ic

# Modos (reaproveita os existentes e acrescenta o domínio climático).
MODO_AGRO_COM_DADOS = ic.MODO_AGRO_COM_DADOS
MODO_AGRO_GERAL = ic.MODO_AGRO_GERAL
MODO_ESCLARECIMENTO = ic.MODO_ESCLARECIMENTO
MODO_FORA_ESCOPO = ic.MODO_FORA_ESCOPO
MODO_CLIMA = "clima"


def _norm(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(ch for ch in sem_acento if not unicodedata.combining(ch))
    return sem_acento.lower().strip()


def _palavras(texto_norm: str) -> set:
    return set(re.findall(r"[a-z0-9-]+", texto_norm))


# Tipos de entidade da propriedade e seus termos (inclui erros comuns de digitação).
TIPOS_ENTIDADE = {
    "canteiro": {"canteiro", "canteiros", "cantero", "canteros"},
    "estufa": {"estufa", "estufas"},
    "talhao": {"talhao", "talhoes", "talhoe", "talhão"},
    "area": {"area", "areas"},
    "sensor": {"sensor", "sensores", "ponto", "pontos"},
    "propriedade": {"propriedade", "propriedades", "fazenda", "lavoura", "lavouras", "sitio"},
}

CULTURAS = {
    "soja": {"soja"},
    "milho": {"milho"},
    "batata-doce": {"batata-doce", "batata"},
    "feijao": {"feijao"},
    "arroz": {"arroz"},
    "trigo": {"trigo"},
    "cafe": {"cafe"},
    "cana": {"cana"},
    "tomate": {"tomate"},
}

PARAMETROS = {
    "ph": {"ph", "acidez", "acido", "acida", "calagem", "calcario"},
    "umidade": {"umidade", "seco", "seca", "molhar", "molhada", "agua", "rega", "regar", "irrigar", "irrigacao"},
    "nitrogenio": {"nitrogenio", "nitrogênio"},
    "fosforo": {"fosforo", "fósforo"},
    "potassio": {"potassio", "potássio"},
    "npk": {"npk", "nutriente", "nutrientes", "adubo", "adubacao"},
    "temperatura": {"temperatura", "calor", "frio"},
    "condutividade": {"condutividade", "salinidade", "ce"},
}

COMPARACAO_PALAVRAS = {
    "qual", "quais", "pior", "melhor", "mais", "menos", "maior", "menor",
    "compara", "comparar", "compare", "entre", "ambos", "destaque",
}
COMPARACAO_FRASES = ("mais seco", "mais seca", "mais umido", "menos umido",
                     "qual esta pior", "qual area", "qual canteiro", "qual sensor",
                     "qual estufa", "qual talhao", "qual ponto", "qual cultura",
                     "merece mais atencao", "precisa de mais atencao")

# Sinais de domínio climático / previsão.
CLIMA_PALAVRAS = {"chover", "chove", "chovendo", "chuva", "chuvas", "geada",
                  "gear", "previsao", "tempo", "garoa", "temporal", "vento",
                  "nublado", "ensolarado", "sol"}
CLIMA_FRASES = ("vai chover", "tem chuva", "previsao de chuva", "previsao do tempo",
                "como fica o tempo", "como esta o tempo", "risco de geada",
                "vai gear", "temperatura prevista", "previsao da semana",
                "como fica o clima", "clima esta semana", "clima da semana",
                "tempo amanha", "chove hoje", "chove amanha", "vai chover hoje",
                "previsao climatica")

# Referência contextual / dêixis.
DEIXIS = {"esse", "essa", "esses", "essas", "este", "esta", "desse", "deste",
          "nesse", "neste", "aqui", "ele", "ela", "anterior", "outro", "outra"}


@dataclass
class DecisaoIntencao:
    modo: str
    dominio: str
    necessita_dados_cliente: bool = False
    necessita_clima: bool = False
    necessita_rag: bool = False
    necessita_openai: bool = True
    tipo_entidade: Optional[str] = None
    culturas: List[str] = field(default_factory=list)
    parametros: List[str] = field(default_factory=list)
    comparacao: bool = False
    referencia_contextual: bool = False
    localizacao_texto: Optional[str] = None
    necessita_esclarecimento: bool = False
    parametro_foco: Optional[str] = None
    extremo: Optional[str] = None  # "menor" | "maior" para comparações
    motivo: str = ""


def _detectar(texto_norm: str, mapa: dict) -> List[str]:
    palavras = _palavras(texto_norm)
    achados = []
    for chave, termos in mapa.items():
        if palavras & {_norm(t) for t in termos} or any(
            "-" in t and _norm(t) in texto_norm for t in termos
        ):
            achados.append(chave)
    return achados


def _tem_localizacao_texto(texto_norm: str) -> Optional[str]:
    # Heurística leve: "em <Cidade>", "na cidade de", "/UF". Não inventa local.
    m = re.search(r"\bem ([a-z][a-z\s]{2,40})", texto_norm)
    if m:
        candidato = m.group(1).strip()
        # Evita capturar "em casa", "em campo" etc. muito curtos.
        if len(candidato) >= 3 and candidato not in {"campo", "casa", "dia", "risco"}:
            return candidato
    return None


def detectar_clima(texto_norm: str) -> bool:
    if any(f in texto_norm for f in CLIMA_FRASES):
        return True
    palavras = _palavras(texto_norm)
    # "chuva/chover/geada/previsao" são fortes; "tempo/sol/vento" exigem contexto.
    fortes = {"chover", "chove", "chovendo", "chuva", "chuvas", "geada", "gear", "previsao"}
    if palavras & fortes:
        return True
    return False


def decidir(
    pergunta: str,
    cliente_id: Optional[str] = None,
    sensor_id: Optional[str] = None,
) -> DecisaoIntencao:
    """Produz a decisão de intenção combinando sinais e IDs disponíveis."""
    texto = _norm(pergunta)

    tipos = _detectar(texto, TIPOS_ENTIDADE)
    culturas = _detectar(texto, CULTURAS)
    parametros = _detectar(texto, PARAMETROS)
    palavras = _palavras(texto)
    comparacao = bool(palavras & COMPARACAO_PALAVRAS) or any(f in texto for f in COMPARACAO_FRASES)
    referencia = bool(palavras & DEIXIS)
    localizacao_texto = _tem_localizacao_texto(texto)
    eh_clima = detectar_clima(texto)
    tem_externo = bool(palavras & set(ic.TERMOS_FORA))

    tipo_entidade = tipos[0] if tipos else None

    # ----------------------------------------------------------------- CLIMA
    # Clima é decidido primeiro: "vai chover?" não deve virar fora_escopo só por
    # não conter termo agro. Exige ausência de sinal externo forte.
    if eh_clima and not tem_externo:
        # Híbrido se também fala de umidade/irrigação/sensor do cliente.
        hibrido = ("umidade" in parametros or tipo_entidade in {"sensor", "canteiro", "estufa", "talhao", "area"}
                   or bool(palavras & {"irrigar", "irrigacao", "molhar", "regar"}))
        necessita_dados = bool(hibrido and (cliente_id or sensor_id))
        return DecisaoIntencao(
            modo=MODO_AGRO_COM_DADOS if necessita_dados else MODO_CLIMA,
            dominio="clima",
            necessita_dados_cliente=necessita_dados,
            necessita_clima=True,
            necessita_rag=False,
            necessita_openai=True,
            tipo_entidade=tipo_entidade,
            culturas=culturas,
            parametros=parametros,
            comparacao=comparacao,
            referencia_contextual=referencia,
            localizacao_texto=localizacao_texto,
            motivo="pergunta climatica" + (" hibrida com dados do cliente" if necessita_dados else ""),
        )

    # Modo base pelo classificador existente (4 modos), já considerando IDs.
    modo_base = ic.classificar(pergunta, cliente_id=cliente_id, sensor_id=sensor_id)

    # --------------------------------------------------------- FORA / ESCLAR.
    if modo_base == MODO_FORA_ESCOPO:
        return DecisaoIntencao(
            modo=MODO_FORA_ESCOPO, dominio="fora_escopo",
            necessita_openai=False, motivo="pergunta externa ao agro",
        )

    if modo_base == MODO_ESCLARECIMENTO:
        return DecisaoIntencao(
            modo=MODO_ESCLARECIMENTO, dominio="esclarecimento",
            necessita_openai=False, necessita_esclarecimento=True,
            tipo_entidade=tipo_entidade, culturas=culturas, parametros=parametros,
            comparacao=comparacao, referencia_contextual=referencia,
            motivo="ambiguo sem contexto suficiente",
        )

    # ------------------------------------------------------------ AGRO GERAL
    if modo_base == MODO_AGRO_GERAL:
        return DecisaoIntencao(
            modo=MODO_AGRO_GERAL, dominio="agro_geral",
            necessita_dados_cliente=False, necessita_rag=True, necessita_openai=True,
            tipo_entidade=None, culturas=culturas, parametros=parametros,
            comparacao=False, referencia_contextual=referencia,
            motivo="duvida agro geral (sem dados do cliente)",
        )

    # --------------------------------------------------------- AGRO COM DADOS
    parametro_foco = parametros[0] if parametros else ("umidade" if comparacao else None)
    extremo = None
    if comparacao:
        if any(t in texto for t in ("mais umido", "maior", "mais alta", "mais alto", "melhor")):
            extremo = "maior"
        else:
            # "mais seco", "menor", "pior", "precisa de atencao" -> menor valor
            extremo = "menor"
    return DecisaoIntencao(
        modo=MODO_AGRO_COM_DADOS, dominio="comparacao" if comparacao else "dados_propriedade",
        necessita_dados_cliente=True, necessita_rag=True, necessita_openai=True,
        tipo_entidade=tipo_entidade, culturas=culturas, parametros=parametros,
        comparacao=comparacao, referencia_contextual=referencia,
        parametro_foco=parametro_foco, extremo=extremo,
        motivo="analise da situacao real do cliente",
    )
