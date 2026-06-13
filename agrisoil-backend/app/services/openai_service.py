"""
Serviço de Integração com Izes IA (powered by OpenAI/ChatGPT)

Fluxo estrutural:
    decisão de intenção (DecisaoIntencao, calculada UMA vez na rota)
      -> recursos reunidos pela rota (dados do cliente, clima, RAG)
      -> este serviço monta o contexto separado (dados x clima x conhecimento),
         chama o modelo (com fallback seguro) e calcula, de forma central:
         origem, validade, confiança, fontes realmente usadas e segurança da
         recomendação, com encerramento contextual adequado.
"""

import base64
import logging
from openai import OpenAI
from app.config import settings
from app.models.contratos import ContextoIA, RespostaIA, RecomendacaoIA
from datetime import datetime
import json
import re
import unicodedata
from typing import List, Optional

from app.services.ia.decisao import (
    DecisaoIntencao,
    MODO_AGRO_COM_DADOS,
    MODO_AGRO_GERAL,
    MODO_CLIMA,
    MODO_ESCLARECIMENTO,
    MODO_FORA_ESCOPO,
)
from app.services.ia import metadados
from app.services.ia.selecao import destacar
from app.services import intent_classifier
from app.services.rag.retriever import ResultadoRAG, recuperar_conhecimento

logger = logging.getLogger(__name__)

RESPOSTA_FORA_ESCOPO = (
    "Eu sou o assistente agro do IZES. Posso ajudar com plantio, solo, "
    "sensores, alertas, animais e manejo da lavoura."
)

AVISO_DOSE = "Não aplique dose exata sem análise de solo ou agrônomo."
PROMPT_ANALISE_IMAGEM = (
    "Analise a imagem enviada pelo usuário. Descreva de forma objetiva o que aparece nela. "
    "Se parecer algo agrícola, planta, solo, praga ou doença, explique apenas sinais visuais observáveis, "
    "sem inventar diagnóstico."
)

MAX_CHUNKS_RAG = 3

# Verbos imperativos fortes que não devem aparecer numa recomendação baseada em
# leitura isolada (segurança da recomendação).
_PADROES_IMPERATIVOS = re.compile(
    r"\b(irrigue|irrig(ar|ue) agora|aplique|adube|fa(ç|c)a calagem|"
    r"pulverize|use \d|aplicar \d)\b",
    re.IGNORECASE,
)


class OpenAIImageAnalysisError(Exception):
    """Erro amigável para análise de imagem com OpenAI."""


def _normalizar_texto(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    return "".join(ch for ch in sem_acento if not unicodedata.combining(ch)).lower()


def classificar_escopo_pergunta(
    pergunta: str,
    cliente_id: Optional[str] = None,
    sensor_id: Optional[str] = None,
) -> str:
    """Compatibilidade: classifica a pergunta em um dos modos (string)."""
    return intent_classifier.classificar(pergunta, cliente_id=cliente_id, sensor_id=sensor_id)


def decisao_basica(modo: str) -> DecisaoIntencao:
    """Constrói uma decisão mínima a partir apenas do modo (compatibilidade)."""
    if modo == MODO_FORA_ESCOPO:
        return DecisaoIntencao(modo=modo, dominio="fora_escopo", necessita_openai=False)
    if modo == MODO_ESCLARECIMENTO:
        return DecisaoIntencao(modo=modo, dominio="esclarecimento",
                               necessita_openai=False, necessita_esclarecimento=True)
    if modo == MODO_AGRO_GERAL:
        return DecisaoIntencao(modo=modo, dominio="agro_geral", necessita_rag=True)
    if modo == MODO_CLIMA:
        return DecisaoIntencao(modo=modo, dominio="clima", necessita_clima=True)
    return DecisaoIntencao(modo=MODO_AGRO_COM_DADOS, dominio="dados_propriedade",
                           necessita_dados_cliente=True, necessita_rag=True)


def buscar_conhecimento_agro(
    pergunta: str,
    modo: str,
    cultura: Optional[str] = None,
    parametros: Optional[List[str]] = None,
) -> List[ResultadoRAG]:
    """Recupera conhecimento técnico do índice RAG local (vazio se irrelevante)."""
    if modo == MODO_FORA_ESCOPO:
        return []
    try:
        return recuperar_conhecimento(
            pergunta, top_k=MAX_CHUNKS_RAG, cultura=cultura, parametros=parametros
        )
    except Exception as exc:  # pragma: no cover - proteção defensiva
        logger.warning("RAG indisponível (%s); seguindo sem conhecimento técnico.", type(exc).__name__)
        return []


class ServicoOpenAI:
    """Integração com Izes IA (utiliza OpenAI como backend)"""

    def __init__(self):
        self.client = None
        self.model = (settings.openai_model or "gpt-4-turbo").strip() or "gpt-4-turbo"
        if not settings.openai_api_key:
            logger.info("Izes IA rodando em modo fallback local: OPENAI_API_KEY não configurada.")
            self.disponivel = False
            return
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.disponivel = True
        logger.info(f"Izes IA {self.model} configurado")

    async def analisar_contexto(
        self,
        contexto: ContextoIA,
        pergunta_id: str,
        modo: Optional[str] = None,
        decisao: Optional[DecisaoIntencao] = None,
        clima_dados: Optional[dict] = None,
        clima_indisponivel: bool = False,
    ) -> RespostaIA:
        """Gera a resposta a partir da decisão de intenção e dos recursos reunidos."""
        if decisao is None:
            modo_efetivo = modo or classificar_escopo_pergunta(
                contexto.usuario_pergunta,
                cliente_id=contexto.cliente_id,
                sensor_id=contexto.sensor_id,
            )
            decisao = decisao_basica(modo_efetivo)

        if decisao.modo == MODO_FORA_ESCOPO:
            return self._resposta_fora_escopo(contexto, pergunta_id)

        if decisao.modo == MODO_ESCLARECIMENTO:
            return self._resposta_esclarecimento(contexto, pergunta_id)

        if decisao.modo == MODO_CLIMA and not decisao.necessita_dados_cliente:
            return self._resposta_clima(contexto, pergunta_id, decisao, clima_dados, clima_indisponivel)

        if decisao.modo == MODO_AGRO_GERAL:
            contexto = self._contexto_agro_geral(contexto)

        if decisao.modo == MODO_AGRO_COM_DADOS and not self._contexto_tem_dados_suficientes(contexto):
            if not decisao.necessita_clima:
                return self._resposta_dados_insuficientes(contexto, pergunta_id)

        resultados_rag = []
        if decisao.necessita_rag:
            resultados_rag = buscar_conhecimento_agro(
                contexto.usuario_pergunta, decisao.modo,
                cultura=contexto.cultura, parametros=decisao.parametros,
            )

        if not self.disponivel:
            logger.info("Izes IA sem OpenAI configurada; retornando fallback local.")
            if decisao.modo == MODO_AGRO_GERAL:
                return self._resposta_agro_geral_fallback(contexto, pergunta_id, decisao, resultados_rag)
            return self._resposta_fallback(
                contexto, pergunta_id, decisao, motivo="OPENAI_API_KEY ausente",
                resultados_rag=resultados_rag, clima_dados=clima_dados,
            )

        try:
            prompt = self._montar_prompt(contexto, decisao, resultados_rag, clima_dados)
            logger.info(f"Chamando Izes para {pergunta_id}...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._prompt_sistema()},
                    {"role": "user", "content": prompt},
                ],
                temperature=settings.openai_temperature,
                max_tokens=min(settings.openai_max_tokens, 700),
                response_format={"type": "json_object"},
            )
            resposta_texto = response.choices[0].message.content
            tokens_usados = response.usage.total_tokens if response.usage else 0
            logger.info(f"Resposta Izes: {len(resposta_texto)} caracteres, {tokens_usados} tokens")
            return self._resposta_openai_estruturada(
                contexto=contexto, pergunta_id=pergunta_id, resposta_texto=resposta_texto,
                tokens_usados=tokens_usados, decisao=decisao, resultados_rag=resultados_rag,
                clima_dados=clima_dados,
            )
        except Exception as e:
            logger.error("Erro ao chamar OpenAI; usando fallback local: %s", type(e).__name__)
            if decisao.modo == MODO_AGRO_GERAL:
                return self._resposta_agro_geral_fallback(contexto, pergunta_id, decisao, resultados_rag)
            return self._resposta_fallback(
                contexto, pergunta_id, decisao, motivo="OpenAI indisponível",
                resultados_rag=resultados_rag, clima_dados=clima_dados,
            )

    async def analisar_imagem(self, image_bytes: bytes, mime_type: str) -> str:
        """Envia uma imagem para a OpenAI com visão e retorna a análise textual."""
        if not settings.openai_api_key:
            raise OpenAIImageAnalysisError("OPENAI_API_KEY não configurada no backend.")
        if not image_bytes:
            raise OpenAIImageAnalysisError("A imagem enviada está vazia.")

        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        vision_model = (settings.openai_vision_model or "gpt-4o-mini").strip() or "gpt-4o-mini"
        try:
            response = self.client.chat.completions.create(
                model=vision_model,
                messages=[
                    {"role": "system", "content": (
                        "Você analisa imagens para o app IZES. "
                        "Responda em português do Brasil, de forma objetiva e sem inventar diagnóstico."
                    )},
                    {"role": "user", "content": [
                        {"type": "text", "text": PROMPT_ANALISE_IMAGEM},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_base64}"}},
                    ]},
                ],
                temperature=0.2,
                max_tokens=min(settings.openai_max_tokens, 400),
            )
        except Exception as exc:
            logger.error("Erro ao analisar imagem com OpenAI: %s", type(exc).__name__, exc_info=True)
            raise OpenAIImageAnalysisError(
                "Não foi possível analisar a imagem com a OpenAI no momento."
            ) from exc

        resposta = (response.choices[0].message.content or "").strip() if response.choices else ""
        if not resposta:
            raise OpenAIImageAnalysisError("A OpenAI não retornou texto para a imagem enviada.")
        return resposta

    # ----------------------------------------------------------- montagem
    def _montar_prompt(
        self,
        contexto: ContextoIA,
        decisao: DecisaoIntencao,
        resultados_rag: Optional[List[ResultadoRAG]] = None,
        clima_dados: Optional[dict] = None,
    ) -> str:
        """Monta o prompt separando dados reais, clima e conhecimento técnico."""
        resultados_rag = resultados_rag or []
        dados = self._dados_para_prompt(contexto, decisao.modo)

        conhecimento = [
            {
                "documento_id": r.chunk.get("documento_id"),
                "titulo": r.chunk.get("titulo"),
                "instituicao": r.chunk.get("instituicao"),
                "ano": r.chunk.get("ano"),
                "paginas": r.fonte().get("paginas"),
                "tema": r.chunk.get("tema"),
                "trecho": r.chunk.get("texto"),
            }
            for r in resultados_rag
        ]

        if decisao.modo == MODO_AGRO_GERAL:
            instrucao_modo = (
                "- Modo agro_geral: responda dúvida agro/rural geral.\n"
                "- Não use dados de sensor, leitura, alerta, pH, NPK, cidade, fazenda ou talhão do cliente.\n"
                "- Use o CONHECIMENTO TÉCNICO RECUPERADO quando existir; senão, orientação geral segura."
            )
        else:
            instrucao_modo = (
                "- Modo agro_com_dados: analise somente os DADOS REAIS fornecidos.\n"
                "- Separe medição (dado real) de interpretação e de referência técnica (RAG/clima).\n"
                "- Se a pergunta for comparativa, comece dizendo qual entidade se destaca e por quê, usando os valores.\n"
                "- Não inclua entidades não solicitadas; não invente dados ausentes."
            )

        partes = [
            "ANÁLISE AGRÍCOLA IZES - RESPONDA SOMENTE COM JSON VÁLIDO",
            f"Modo da pergunta: {decisao.modo}",
            f"Entidade pedida: {decisao.tipo_entidade or '-'} | Comparação: {decisao.comparacao} | Parâmetros: {decisao.parametros}",
            "",
            "PERGUNTA DO USUÁRIO:",
            contexto.usuario_pergunta,
            "",
            "DADOS REAIS DO CLIENTE (somente o que foi efetivamente consultado):",
            json.dumps(dados, ensure_ascii=False, indent=2, default=str),
        ]
        destaque = self._destaque_comparativo(contexto, decisao)
        if destaque:
            partes += ["", "DESTAQUE CALCULADO (a partir dos dados reais; use estes valores na resposta):",
                       json.dumps(destaque, ensure_ascii=False, indent=2, default=str)]
        if clima_dados:
            partes += ["", "CLIMA (serviço climático real):",
                       json.dumps(clima_dados, ensure_ascii=False, indent=2, default=str)]
        partes += [
            "",
            "CONHECIMENTO TÉCNICO RECUPERADO (use apenas estes trechos; não cite outra fonte):",
            json.dumps(conhecimento, ensure_ascii=False, indent=2, default=str),
            "",
            "Formato JSON obrigatório:",
            "{",
            '  "resposta_texto": "Situação:\\n...\\n\\nRisco:\\n...\\n\\nO que fazer agora:\\n1. ...\\n2. ...\\n3. ...\\n\\nAtenção:\\nNão aplique dose exata sem análise de solo ou agrônomo.",',
            '  "recomendacao": {"acao": "uma frase objetiva", "motivo": "uma frase simples", "riscos_se_nao_fizer": "uma frase", "beneficios": "uma frase"},',
            '  "atencoes": ["até 3 itens curtos"],',
            '  "proximos_passos": ["até 3 itens curtos"],',
            '  "confianca_geral": 0.0,',
            '  "documento_ids_utilizados": ["apenas os documento_id do CONHECIMENTO que você realmente usou"]',
            "}",
            "",
            "Regras do modo:",
            instrucao_modo,
            "",
            "Regras obrigatórias:",
            "- Máximo de 5 a 8 linhas em resposta_texto; frases curtas e simples.",
            "- Não cite documento que não esteja em CONHECIMENTO TÉCNICO RECUPERADO.",
            "- documento_ids_utilizados deve conter SOMENTE ids presentes no CONHECIMENTO acima; se não usou nenhum, retorne lista vazia.",
            "- Não trate sensor como análise laboratorial; admita incerteza e limitações.",
            "- Não ordene irrigação, calagem ou dose com base em leitura isolada; recomende avaliar antes (recência, profundidade, tipo de solo, cultura, fase, chuva).",
            "- confianca_geral entre 0 e 1, coerente com a certeza real.",
            "- Se faltar dado real no modo agro_com_dados, diga exatamente qual dado faltou.",
        ]
        return "\n".join(partes).strip()

    def _destaque_comparativo(self, contexto: ContextoIA, decisao: DecisaoIntencao) -> Optional[dict]:
        """Calcula, a partir dos dados reais, qual entidade se destaca (comparação)."""
        if not getattr(decisao, "comparacao", False):
            return None
        parametro = getattr(decisao, "parametro_foco", None) or "umidade"
        preferir_menor = getattr(decisao, "extremo", "menor") != "maior"
        sensores = [s for s in contexto.sensores_relevantes if s.ultima_leitura]
        if len(sensores) < 1:
            return None
        return destacar(sensores, parametro, preferir_menor=preferir_menor)

    def _dados_para_prompt(self, contexto: ContextoIA, modo: str) -> dict:
        if modo == MODO_AGRO_GERAL:
            return {
                "modo": modo,
                "pergunta": contexto.usuario_pergunta,
                "observacao": "Sem dados do cliente neste modo; usar apenas conhecimento técnico geral.",
            }
        return {
            "modo": modo,
            "cliente_id": contexto.cliente_id,
            "sensor_id_foco": contexto.sensor_id,
            "pergunta": contexto.usuario_pergunta,
            "sensores_relevantes": [s.model_dump(mode="json") for s in contexto.sensores_relevantes],
            "alertas_ativos": [a.model_dump(mode="json") for a in contexto.alertas_ativos],
            "alertas_historico_30_dias": [a.model_dump(mode="json") for a in contexto.alertas_historico_30_dias],
            "clima_atual": contexto.clima_atual,
            "cultura": contexto.cultura,
            "fase_desenvolvimento": contexto.fase_desenvolvimento,
            "prioridades": contexto.prioridades,
            "timestamp_coleta": contexto.timestamp_coleta.isoformat(),
        }

    def _prompt_sistema(self) -> str:
        return (
            "Você é o assistente agro do IZES para agricultura, pecuária, solo, sensores, clima e manejo. "
            "Responda apenas com JSON válido, curto, em português claro e respeitando o modo da pergunta. "
            "No modo agro_geral, não use nem invente dados de sensor, leitura, alerta, fazenda, cidade ou talhão. "
            "No modo agro_com_dados, use somente os dados reais fornecidos e separe medição de interpretação. "
            "Use apenas o conhecimento técnico recuperado fornecido; nunca cite documento que não foi recuperado. "
            "Não dê ordem de irrigação, calagem ou dose com base em leitura isolada. "
            "Deixe claro que a resposta é orientação e não substitui laudo agronômico."
        )

    def pergunta_dentro_escopo(self, pergunta: str) -> bool:
        return classificar_escopo_pergunta(pergunta) != MODO_FORA_ESCOPO

    def _normalizar(self, texto: str) -> str:
        return _normalizar_texto(texto)

    def _contexto_tem_dados_suficientes(self, contexto: ContextoIA) -> bool:
        return any([
            any(s.ultima_leitura for s in contexto.sensores_relevantes),
            any(s.avaliacoes for s in contexto.sensores_relevantes),
            bool(contexto.alertas_ativos),
            bool(contexto.alertas_historico_30_dias),
        ])

    def _contexto_agro_geral(self, contexto: ContextoIA) -> ContextoIA:
        return ContextoIA(
            cliente_id=contexto.cliente_id, sensor_id=None,
            usuario_pergunta=contexto.usuario_pergunta, tokens_estimado=0,
        )

    def _dados_consultados(self, contexto: ContextoIA, modo: Optional[str] = None) -> list:
        if modo == MODO_AGRO_GERAL:
            return ["conhecimento_agro_geral"]
        dados = []
        if contexto.sensores_relevantes:
            dados.append("sensores")
            if any(s.ultima_leitura for s in contexto.sensores_relevantes):
                dados.append("ultima_leitura")
            if any(s.avaliacoes for s in contexto.sensores_relevantes):
                dados.append("avaliacoes_agronomicas")
        if contexto.alertas_ativos:
            dados.append("alertas_ativos")
        if contexto.alertas_historico_30_dias:
            dados.append("historico_alertas")
        if contexto.clima_atual:
            dados.append("clima")
        if contexto.cultura or contexto.fase_desenvolvimento:
            dados.append("cultura")
        return dados or ["pergunta_usuario"]

    # ---------------------------------------------------- fontes realmente usadas
    def _fontes_validadas(
        self, resultados_rag: Optional[List[ResultadoRAG]], ids_declarados: Optional[list]
    ) -> list:
        """Expõe apenas fontes recuperadas E declaradas como usadas pelo modelo."""
        if not resultados_rag:
            return []
        ids_disponiveis = {r.chunk.get("documento_id") for r in resultados_rag}
        if ids_declarados is None:
            # Sem declaração confiável: não inventar uso.
            return []
        usados = {str(i) for i in ids_declarados} & ids_disponiveis
        fontes, vistos = [], set()
        for r in resultados_rag:
            doc = r.chunk.get("documento_id")
            if doc not in usados:
                continue
            fonte = r.fonte()
            chave = (fonte.get("documento_id"), fonte.get("paginas"))
            if chave in vistos:
                continue
            vistos.add(chave)
            fontes.append(fonte)
        return fontes

    # ------------------------------------------------------- encerramento
    def _encerramento_contextual(self, modo: str, contexto: ContextoIA, tem_dados: bool, usou_clima: bool) -> str:
        seed = abs(hash(contexto.usuario_pergunta or "")) % 2
        if usou_clima:
            opcoes = [
                "Posso cruzar essa previsão com a umidade atual dos seus sensores e indicar o melhor momento de irrigar. É só pedir.",
                "Se quiser, acompanho a previsão da semana e aviso o que planejar para as suas áreas. É só pedir.",
            ]
            return opcoes[seed]
        if modo == MODO_AGRO_GERAL:
            opcoes = [
                "Posso relacionar isso com a sua cultura, região ou com os dados dos seus sensores. É só pedir.",
                "Se quiser, comparo isso com as leituras atuais das suas áreas e mostro o que vale acompanhar. É só pedir.",
            ]
            return opcoes[seed]
        if not tem_dados:
            return "Posso analisar melhor quando você informar a área, o canteiro ou o sensor desejado. É só pedir."
        varios = len(contexto.sensores_relevantes) > 1
        if varios:
            opcoes = [
                "Também posso comparar esses pontos e indicar qual precisa de mais atenção primeiro. É só pedir.",
                "Se quiser, detalho os nutrientes de cada área e mostro qual acompanhar primeiro. É só pedir.",
            ]
        else:
            opcoes = [
                "Também posso comparar esse ponto com as outras áreas da propriedade. É só pedir.",
                "Se quiser, detalho os nutrientes desse ponto ou explico o que acompanhar antes de irrigar. É só pedir.",
            ]
        return opcoes[seed]

    def _aplicar_encerramento(self, resposta_texto, modo, contexto, tem_dados, usou_clima=False):
        if modo not in (MODO_AGRO_COM_DADOS, MODO_AGRO_GERAL, MODO_CLIMA):
            return resposta_texto
        texto = (resposta_texto or "").rstrip()
        if "é só pedir" in texto.lower():
            return texto
        return f"{texto}\n\n{self._encerramento_contextual(modo, contexto, tem_dados, usou_clima)}"

    # ------------------------------------------- segurança da recomendação
    def _suavizar_recomendacao(self, payload: dict, baseado_em_leitura_isolada: bool) -> bool:
        """Detecta/suaviza ordens fortes baseadas em base insuficiente.

        Retorna True se houve ajuste (a confiança será penalizada).
        """
        if not baseado_em_leitura_isolada:
            return False
        ajustou = False
        rec = payload.get("recomendacao") or {}
        acao = str(rec.get("acao") or "")
        if _PADROES_IMPERATIVOS.search(acao):
            rec["acao"] = "Avaliar em campo antes de irrigar ou aplicar insumo, considerando recência da leitura, tipo de solo, cultura e fase."
            payload["recomendacao"] = rec
            ajustou = True
        texto = str(payload.get("resposta_texto") or "")
        if _PADROES_IMPERATIVOS.search(texto):
            payload["resposta_texto"] = _PADROES_IMPERATIVOS.sub("considere avaliar/irrigar com cautela", texto)
            ajustou = True
        if ajustou:
            atencoes = payload.get("atencoes") or []
            if not isinstance(atencoes, list):
                atencoes = []
            atencoes.append("Recomendação preliminar: confirme em campo antes de agir.")
            payload["atencoes"] = atencoes
        return ajustou

    # --------------------------------------------------------- respostas
    def _resposta_openai_estruturada(
        self, contexto, pergunta_id, resposta_texto, tokens_usados, decisao,
        resultados_rag=None, clima_dados=None,
    ) -> RespostaIA:
        try:
            payload = json.loads(resposta_texto)
            tem_dados = self._contexto_tem_dados_suficientes(contexto)
            leitura_isolada = (
                decisao.modo == MODO_AGRO_COM_DADOS
                and len([s for s in contexto.sensores_relevantes if s.ultima_leitura]) <= 1
                and not contexto.alertas_ativos
            )
            recomendacao_suavizada = self._suavizar_recomendacao(payload, leitura_isolada)

            resposta_curta = self._limitar_texto(str(payload["resposta_texto"]), max_linhas=7, max_chars=820)
            recomendacao_raw = payload.get("recomendacao") or {}
            ids_declarados = payload.get("documento_ids_utilizados")
            if not isinstance(ids_declarados, list):
                ids_declarados = None
            fontes = self._fontes_validadas(resultados_rag, ids_declarados)

            penalidades = {
                "dados_ausentes": decisao.modo == MODO_AGRO_COM_DADOS and not tem_dados,
                "rag_fraco": decisao.necessita_rag and not fontes,
                "clima_indisponivel": decisao.necessita_clima and not clima_dados,
                "requer_validacao": recomendacao_suavizada,
            }
            confianca = metadados.normalizar_confianca(
                payload.get("confianca_geral"), penalidades=penalidades
            )
            recomendacao = RecomendacaoIA(
                acao=self._frase_curta(recomendacao_raw.get("acao"), "Validar dados no dashboard antes do manejo."),
                confianca=confianca,
                motivo=self._frase_curta(recomendacao_raw.get("motivo"), "Baseado apenas no contexto real recebido."),
                riscos_se_nao_fizer=self._frase_curta(recomendacao_raw.get("riscos_se_nao_fizer"), "Pode haver decisão sem validação."),
                beneficios=self._frase_curta(recomendacao_raw.get("beneficios"), "Reduz risco de agir com dado incompleto."),
            )
            atencoes = self._lista_curta(payload.get("atencoes"), fallback=[AVISO_DOSE])
            proximos = self._lista_curta(payload.get("proximos_passos"), fallback=["Conferir dados no dashboard."])
            return self._montar_resposta_segura(
                contexto=contexto, pergunta_id=pergunta_id, resposta_texto=resposta_curta,
                decisao=decisao, recomendacao=recomendacao, atencoes=atencoes,
                proximos_passos=proximos, confianca=confianca, modelo=self.model,
                tokens_usados=tokens_usados, fontes=fontes, clima_dados=clima_dados,
                usou_openai=True,
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            logger.warning("OpenAI retornou JSON inválido para IA; usando fallback local seguro.")
            if decisao.modo == MODO_AGRO_GERAL:
                return self._resposta_agro_geral_fallback(contexto, pergunta_id, decisao, resultados_rag)
            return self._resposta_fallback(
                contexto, pergunta_id, decisao, motivo="Resposta OpenAI inválida",
                resultados_rag=resultados_rag, clima_dados=clima_dados,
            )

    def _montar_resposta_segura(
        self, contexto, pergunta_id, resposta_texto, decisao, recomendacao,
        atencoes, proximos_passos, confianca, modelo, tokens_usados=0,
        fontes=None, clima_dados=None, usou_openai=True, origem_forcada=None,
    ) -> RespostaIA:
        modo = decisao.modo
        dados_consultados = self._dados_consultados(contexto, modo)
        tem_dados = self._contexto_tem_dados_suficientes(contexto)
        usou_dados = modo == MODO_AGRO_COM_DADOS and tem_dados
        usou_clima = bool(clima_dados)
        usou_rag = bool(fontes)

        origem = origem_forcada or metadados.calcular_origem(
            usou_openai=usou_openai, usou_dados=usou_dados, usou_clima=usou_clima,
            usou_rag=usou_rag, fallback=not usou_openai,
        )
        validade = metadados.calcular_validade(
            modo, usou_clima=usou_clima, tem_dados=tem_dados,
            timestamp_leitura=self._timestamp_leitura(contexto),
        )
        recursos = self._recursos_utilizados(usou_dados, usou_clima, usou_rag, usou_openai)
        resposta_texto = self._aplicar_encerramento(resposta_texto, modo, contexto, tem_dados, usou_clima)

        return RespostaIA(
            pergunta_id=pergunta_id, cliente_id=contexto.cliente_id, sensor_id=contexto.sensor_id,
            resposta_texto=resposta_texto,
            resposta_estruturada={
                "modo": modo, "origem": origem,
                "dados_reais": usou_dados,
                "recursos_utilizados": recursos,
            },
            recomendacao=recomendacao,
            dados_consultados=dados_consultados,
            atencoes=atencoes[:3], proximos_passos=proximos_passos[:3],
            fontes=fontes or [], recursos_utilizados=recursos,
            confianca_geral=max(0.0, min(float(confianca), 1.0)),
            requer_validacao_humana=True, modelo=modelo, tokens_usados=tokens_usados,
            tempo_resposta_segundos=0, validade=validade, criado_em=datetime.now(),
        )

    def _recursos_utilizados(self, usou_dados, usou_clima, usou_rag, usou_openai) -> list:
        recursos = []
        if usou_dados:
            recursos.append("dados_cliente")
        if usou_clima:
            recursos.append("clima")
        if usou_rag:
            recursos.append("rag")
        if usou_openai:
            recursos.append("openai")
        return recursos

    def _timestamp_leitura(self, contexto: ContextoIA) -> Optional[datetime]:
        for s in contexto.sensores_relevantes:
            leitura = s.ultima_leitura or {}
            ts = leitura.get("timestamp")
            if ts:
                try:
                    return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    return None
        return None

    def _resposta_fallback(self, contexto, pergunta_id, decisao, motivo,
                           resultados_rag=None, clima_dados=None) -> RespostaIA:
        sensores_com_leitura = [s for s in contexto.sensores_relevantes if s.ultima_leitura]
        alertas = contexto.alertas_ativos

        destaque = self._destaque_comparativo(contexto, decisao)
        if destaque and len(destaque["comparados"]) >= 1:
            d = destaque["destaque"]
            criterio = "menor" if destaque["criterio"] == "menor" else "maior"
            nome = d.get("nome") or d.get("sensor_id")
            situacao = (
                f"Comparando o parâmetro {destaque['parametro']}, {nome} se destaca "
                f"com o {criterio} valor ({d['valor']}). Merece acompanhamento mais próximo."
            )
        else:
            situacao = (
                f"Foram encontrados {len(contexto.sensores_relevantes)} sensor(es) relevante(s)"
                f" e {len(sensores_com_leitura)} com leitura recente disponível."
            )
        if alertas:
            situacao += f" Há {len(alertas)} alerta(s) ativo(s) no contexto."

        riscos = []
        for alerta in alertas[:3]:
            riscos.append(f"{alerta.tipo or 'alerta'} ({alerta.severidade or 'sem severidade'}): {alerta.mensagem}")
        for sensor in sensores_com_leitura[:3]:
            for parametro, avaliacao in (sensor.avaliacoes or {}).items():
                nivel = avaliacao.get("nivel")
                if nivel and nivel not in {"ok", "ideal"}:
                    riscos.append(f"{sensor.sensor_id} - {parametro}: {nivel}. {avaliacao.get('mensagem') or ''}".strip())
        risco_texto = " ".join(riscos) if riscos else "Não há alerta ativo ou avaliação crítica no contexto recebido."

        proximos = [
            "Conferir última leitura e alertas no dashboard.",
            "Coletar nova leitura se os dados estiverem antigos.",
            "Chamar agrônomo se houver alerta crítico.",
        ]
        texto = self._formatar_resposta_curta(situacao=situacao, risco=risco_texto, passos=proximos)
        confianca = metadados.normalizar_confianca(
            0.55 if sensores_com_leitura or alertas else None,
            penalidades={"dados_ausentes": not (sensores_com_leitura or alertas)},
        )
        return self._montar_resposta_segura(
            contexto=contexto, pergunta_id=pergunta_id, resposta_texto=texto, decisao=decisao,
            recomendacao=RecomendacaoIA(
                acao="Validar os dados no dashboard e monitorar novas leituras antes de executar manejo.",
                confianca=confianca,
                motivo="Resposta local baseada apenas nos dados já disponíveis no contexto.",
                riscos_se_nao_fizer="Decisão de manejo sem validação pode gerar ação inadequada.",
                beneficios="Reduz risco de agir com dados incompletos.",
            ),
            atencoes=["Orientação preliminar; não substitui laudo agronômico.", AVISO_DOSE],
            proximos_passos=proximos, confianca=confianca, modelo="fallback-local",
            fontes=[], clima_dados=clima_dados, usou_openai=False, origem_forcada="fallback_local",
        )

    def _resposta_dados_insuficientes(self, contexto, pergunta_id) -> RespostaIA:
        passos = [
            "Registrar uma leitura real do sensor.",
            "Verificar se há alertas no dashboard.",
            "Enviar nova pergunta depois da coleta.",
        ]
        decisao = DecisaoIntencao(modo=MODO_AGRO_COM_DADOS, dominio="dados_propriedade",
                                  necessita_dados_cliente=True)
        return self._montar_resposta_segura(
            contexto=contexto, pergunta_id=pergunta_id,
            resposta_texto=self._formatar_resposta_curta(
                situacao="Não tenho leitura real para esse caso.",
                risco="Não há dados suficientes para orientar manejo.", passos=passos),
            decisao=decisao,
            recomendacao=RecomendacaoIA(
                acao="Coletar uma leitura real antes de decidir manejo.",
                confianca=metadados.normalizar_confianca(None, penalidades={"dados_ausentes": True}),
                motivo="O contexto não tem leitura, alerta ou avaliação.",
                riscos_se_nao_fizer="A decisão pode ser tomada sem base real.",
                beneficios="A análise passa a usar dados reais do campo."),
            atencoes=[AVISO_DOSE], proximos_passos=passos,
            confianca=metadados.normalizar_confianca(None, penalidades={"dados_ausentes": True}),
            modelo="sem-openai", fontes=[], usou_openai=False, origem_forcada="fallback_local",
        )

    def _resposta_agro_geral_fallback(self, contexto, pergunta_id, decisao, resultados_rag=None) -> RespostaIA:
        passos = [
            "Descrever cultura, criação ou problema do campo.",
            "Usar análise de solo ou orientação técnica para decisões exatas.",
            "Ativar OpenAI para resposta agro geral mais completa.",
        ]
        return self._montar_resposta_segura(
            contexto=contexto, pergunta_id=pergunta_id,
            resposta_texto=self._formatar_resposta_curta(
                situacao="A pergunta é agro/rural geral e será respondida sem usar sensores do cliente.",
                risco="Para recomendação exata, faltam região, cultura/fase, área e análise técnica.",
                passos=passos),
            decisao=DecisaoIntencao(modo=MODO_AGRO_GERAL, dominio="agro_geral", necessita_rag=True),
            recomendacao=RecomendacaoIA(
                acao="Responder como orientação agro geral, sem dados de sensor.",
                confianca=metadados.normalizar_confianca(0.55),
                motivo="A pergunta não pediu análise de leitura, sensor ou alerta.",
                riscos_se_nao_fizer="Pode perder produtividade por preparo ou manejo inadequado.",
                beneficios="Ajuda a começar com mais segurança e menos desperdício."),
            atencoes=[AVISO_DOSE], proximos_passos=passos,
            confianca=metadados.normalizar_confianca(0.55), modelo="fallback-local",
            fontes=[], usou_openai=False, origem_forcada="fallback_local",
        )

    def _resposta_clima(self, contexto, pergunta_id, decisao, clima_dados, clima_indisponivel) -> RespostaIA:
        if clima_indisponivel or not clima_dados:
            texto = (
                "Situação: O serviço de previsão do tempo está indisponível agora.\n\n"
                "Risco: Não tenho como confirmar a previsão neste momento.\n\n"
                "O que fazer agora:\n1. Tentar novamente em alguns minutos.\n"
                "2. Conferir uma fonte oficial de clima.\n3. Evitar decidir irrigação só por previsão."
            )
            return RespostaIA(
                pergunta_id=pergunta_id, cliente_id=contexto.cliente_id, sensor_id=contexto.sensor_id,
                resposta_texto=texto,
                resposta_estruturada={"modo": MODO_CLIMA, "origem": "servico_climatico",
                                      "dados_reais": False, "recursos_utilizados": ["clima"]},
                recomendacao=RecomendacaoIA(
                    acao="Tentar novamente quando o serviço de clima voltar.",
                    confianca=metadados.normalizar_confianca(None, penalidades={"clima_indisponivel": True}),
                    motivo="A consulta ao serviço climático falhou.",
                    riscos_se_nao_fizer="Decidir sem previsão confiável pode levar a erro.",
                    beneficios="Evita agir sobre uma previsão inventada."),
                dados_consultados=["pergunta_usuario"], atencoes=["Não invento previsão do tempo."],
                proximos_passos=["Tentar novamente em instantes."], fontes=[],
                recursos_utilizados=["clima"],
                confianca_geral=metadados.normalizar_confianca(None, penalidades={"clima_indisponivel": True}),
                requer_validacao_humana=False, modelo="servico-climatico", tokens_usados=0,
                tempo_resposta_segundos=0, validade=None, criado_em=datetime.now(),
            )

        # Há dados de clima. Usa OpenAI para formatar se disponível; senão, determinístico.
        if self.disponivel:
            try:
                prompt = self._montar_prompt(contexto, decisao, [], clima_dados)
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "system", "content": self._prompt_sistema()},
                              {"role": "user", "content": prompt}],
                    temperature=settings.openai_temperature,
                    max_tokens=min(settings.openai_max_tokens, 600),
                    response_format={"type": "json_object"},
                )
                payload = json.loads(response.choices[0].message.content)
                tokens = response.usage.total_tokens if response.usage else 0
                texto = self._limitar_texto(str(payload["resposta_texto"]), max_linhas=7, max_chars=820)
                rec = payload.get("recomendacao") or {}
                confianca = metadados.normalizar_confianca(payload.get("confianca_geral"))
                return self._resposta_clima_final(
                    contexto, pergunta_id, texto,
                    RecomendacaoIA(
                        acao=self._frase_curta(rec.get("acao"), "Planejar o manejo conforme a previsão."),
                        confianca=confianca,
                        motivo=self._frase_curta(rec.get("motivo"), "Baseado na previsão climática consultada."),
                        riscos_se_nao_fizer=self._frase_curta(rec.get("riscos_se_nao_fizer"), "Pode ser surpreendido pelo tempo."),
                        beneficios=self._frase_curta(rec.get("beneficios"), "Ajuda a planejar o campo.")),
                    self._lista_curta(payload.get("atencoes"), ["Previsão pode mudar."]),
                    self._lista_curta(payload.get("proximos_passos"), ["Acompanhar a previsão."]),
                    confianca, self.model, tokens, clima_dados, usou_openai=True,
                )
            except Exception:
                logger.warning("Falha ao formatar clima com OpenAI; usando resumo determinístico.")

        # Determinístico a partir do clima_dados
        atual = (clima_dados or {}).get("clima_atual") or {}
        prev = (clima_dados or {}).get("previsao_resumo") or {}
        local = (clima_dados or {}).get("localizacao") or {}
        prob = prev.get("probabilidade_chuva")
        texto = (
            f"Situação: Clima em {local.get('cidade') or 'sua região'}: "
            f"{atual.get('descricao') or 'condições atuais'}, {atual.get('temperatura', '?')}°C.\n\n"
            f"Risco: Probabilidade de chuva próxima: {prob if prob is not None else 'não informada'}%.\n\n"
            "O que fazer agora:\n1. Considerar a previsão no planejamento.\n"
            "2. Conferir a umidade do solo antes de irrigar.\n3. Reavaliar com nova atualização."
        )
        return self._resposta_clima_final(
            contexto, pergunta_id, texto,
            RecomendacaoIA(
                acao="Planejar o manejo considerando a previsão e a umidade do solo.",
                confianca=metadados.normalizar_confianca(0.6),
                motivo="Baseado na previsão climática consultada.",
                riscos_se_nao_fizer="Pode ser pego de surpresa pelo tempo.",
                beneficios="Ajuda a planejar irrigação e operações."),
            ["A previsão pode mudar; reavalie."], ["Acompanhar a próxima atualização."],
            metadados.normalizar_confianca(0.6), "servico-climatico", 0, clima_dados, usou_openai=False,
        )

    def _resposta_clima_final(self, contexto, pergunta_id, texto, recomendacao, atencoes,
                              proximos, confianca, modelo, tokens, clima_dados, usou_openai) -> RespostaIA:
        texto = self._aplicar_encerramento(texto, MODO_CLIMA, contexto, tem_dados=False, usou_clima=True)
        origem = metadados.calcular_origem(usou_openai=usou_openai, usou_clima=True,
                                           apenas_clima=not usou_openai)
        return RespostaIA(
            pergunta_id=pergunta_id, cliente_id=contexto.cliente_id, sensor_id=contexto.sensor_id,
            resposta_texto=texto,
            resposta_estruturada={"modo": MODO_CLIMA, "origem": origem, "dados_reais": False,
                                  "recursos_utilizados": (["openai"] if usou_openai else []) + ["clima"]},
            recomendacao=recomendacao, dados_consultados=["clima"],
            atencoes=atencoes[:3], proximos_passos=proximos[:3], fontes=[],
            recursos_utilizados=(["clima", "openai"] if usou_openai else ["clima"]),
            confianca_geral=max(0.0, min(float(confianca), 1.0)),
            requer_validacao_humana=True, modelo=modelo, tokens_usados=tokens,
            tempo_resposta_segundos=0,
            validade=metadados.calcular_validade(MODO_CLIMA, usou_clima=True),
            criado_em=datetime.now(),
        )

    def _resposta_esclarecimento(self, contexto, pergunta_id) -> RespostaIA:
        pergunta = (
            "Você quer uma visão geral de todas as áreas ou a análise de um sensor específico? "
            "Qual área, canteiro ou sensor você deseja analisar?"
        )
        return RespostaIA(
            pergunta_id=pergunta_id, cliente_id=contexto.cliente_id, sensor_id=contexto.sensor_id,
            resposta_texto=pergunta,
            resposta_estruturada={"modo": MODO_ESCLARECIMENTO, "origem": "regra_contextual",
                                  "dados_reais": False, "recursos_utilizados": []},
            recomendacao=RecomendacaoIA(
                acao="Informar a área, o canteiro ou o sensor que deseja analisar.",
                confianca=metadados.normalizar_confianca(0.5),
                motivo="A pergunta está ambígua e não há contexto suficiente para responder com segurança.",
                riscos_se_nao_fizer="Sem o alvo, a análise pode usar dados que não são os desejados.",
                beneficios="Garante que a análise use exatamente a área ou sensor certo."),
            dados_consultados=["pergunta_usuario"], atencoes=[], proximos_passos=[], fontes=[],
            recursos_utilizados=[], confianca_geral=metadados.normalizar_confianca(0.5),
            requer_validacao_humana=False, modelo="regra-contextual", tokens_usados=0,
            tempo_resposta_segundos=0, validade=None, criado_em=datetime.now(),
        )

    def _resposta_fora_escopo(self, contexto, pergunta_id) -> RespostaIA:
        return RespostaIA(
            pergunta_id=pergunta_id, cliente_id=contexto.cliente_id, sensor_id=contexto.sensor_id,
            resposta_texto=RESPOSTA_FORA_ESCOPO,
            resposta_estruturada={"modo": MODO_FORA_ESCOPO, "origem": "fora_escopo",
                                  "dados_reais": False, "recursos_utilizados": []},
            recomendacao=RecomendacaoIA(
                acao="Fazer uma pergunta sobre sensores, solo, alertas, leituras, clima ou manejo.",
                confianca=metadados.normalizar_confianca(1.0),
                motivo="A pergunta está fora do escopo do assistente agro.",
                riscos_se_nao_fizer="A dúvida fora de escopo não será analisada pelo IZES.",
                beneficios="Mantém o assistente focado em dados reais do campo."),
            dados_consultados=["pergunta_usuario"], atencoes=[], proximos_passos=[], fontes=[],
            recursos_utilizados=[], confianca_geral=1.0,
            requer_validacao_humana=False, modelo="sem-openai", tokens_usados=0,
            tempo_resposta_segundos=0, validade=None, criado_em=datetime.now(),
        )

    def _formatar_resposta_curta(self, situacao, risco, passos) -> str:
        passos = passos[:3]
        linhas = [
            f"Situação: {self._limitar_texto(situacao, 1, 220)}",
            "", f"Risco: {self._limitar_texto(risco, 1, 260)}", "", "O que fazer agora:",
        ]
        linhas.extend(f"{i}. {self._limitar_texto(p, 1, 120)}" for i, p in enumerate(passos, 1))
        linhas.extend(["", f"Atenção: {AVISO_DOSE}"])
        return "\n".join(linhas)

    def _frase_curta(self, valor, fallback) -> str:
        return self._limitar_texto(str(valor or fallback).strip(), 1, 160)

    def _lista_curta(self, valor, fallback) -> list:
        if not isinstance(valor, list):
            valor = fallback
        itens = [self._frase_curta(item, "") for item in valor if str(item or "").strip()]
        return (itens or fallback)[:3]

    def _limitar_texto(self, texto, max_linhas, max_chars) -> str:
        linhas = [l.strip() for l in str(texto or "").splitlines() if l.strip()]
        return "\n".join(linhas[:max_linhas]).strip()[:max_chars].rstrip()
