"""
Serviço de Integração com Izes IA (powered by OpenAI/ChatGPT)

Fluxo:
    pergunta -> classificação de intenção (intent_classifier)
             -> decisão sobre dados do cliente / uso do RAG
             -> montagem controlada do contexto (dados reais x conhecimento técnico)
             -> chamada do modelo (com fallback seguro)
             -> resposta natural, com fontes rastreáveis e encerramento contextual.
"""

import base64
import logging
from openai import OpenAI
from app.config import settings
from app.models.contratos import ContextoIA, RespostaIA, RecomendacaoIA
from datetime import datetime
import json
import unicodedata
from typing import List, Optional

from app.services import intent_classifier
from app.services.intent_classifier import (
    MODO_AGRO_COM_DADOS,
    MODO_AGRO_GERAL,
    MODO_ESCLARECIMENTO,
    MODO_FORA_ESCOPO,
)
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

# Quantidade máxima de chunks de conhecimento técnico no contexto.
MAX_CHUNKS_RAG = 3


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
    """Classifica a pergunta usando o classificador de intenção.

    Mantém compatibilidade com chamadas antigas (apenas ``pergunta``) e usa
    ``cliente_id`` / ``sensor_id`` para desambiguar perguntas curtas, informais
    ou contextuais.
    """
    return intent_classifier.classificar(pergunta, cliente_id=cliente_id, sensor_id=sensor_id)


def buscar_conhecimento_agro(
    pergunta: str,
    modo: str,
    cultura: Optional[str] = None,
) -> List[ResultadoRAG]:
    """Recupera conhecimento técnico do índice RAG local.

    Retorna lista vazia (sem derrubar o fluxo) quando não há conteúdo relevante
    ou o índice está ausente. Nunca inventa fonte.
    """
    if modo == MODO_FORA_ESCOPO:
        return []
    try:
        return recuperar_conhecimento(pergunta, top_k=MAX_CHUNKS_RAG, cultura=cultura)
    except Exception as exc:  # pragma: no cover - proteção defensiva
        logger.warning("RAG indisponível (%s); seguindo sem conhecimento técnico.", type(exc).__name__)
        return []


class ServicoOpenAI:
    """Integração com Izes IA (utiliza OpenAI como backend)"""

    def __init__(self):
        """Inicializa cliente Izes"""
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
    ) -> RespostaIA:
        """Chama Izes IA para analisar contexto agrícola.

        Args:
            contexto: Contexto montado com dados da propriedade (se houver).
            pergunta_id: ID da pergunta para rastreamento.
            modo: Modo já decidido pela rota (com cliente_id/sensor_id). Se None,
                  é recalculado a partir do texto e do sensor do contexto.
        """
        modo_pergunta = modo or classificar_escopo_pergunta(
            contexto.usuario_pergunta,
            cliente_id=contexto.cliente_id,
            sensor_id=contexto.sensor_id,
        )

        if modo_pergunta == MODO_FORA_ESCOPO:
            return self._resposta_fora_escopo(contexto, pergunta_id)

        if modo_pergunta == MODO_ESCLARECIMENTO:
            return self._resposta_esclarecimento(contexto, pergunta_id)

        if modo_pergunta == MODO_AGRO_GERAL:
            contexto = self._contexto_agro_geral(contexto)

        if modo_pergunta == MODO_AGRO_COM_DADOS and not self._contexto_tem_dados_suficientes(contexto):
            return self._resposta_dados_insuficientes(contexto, pergunta_id)

        # Recuperação de conhecimento técnico (RAG), separada dos dados reais.
        resultados_rag = buscar_conhecimento_agro(
            contexto.usuario_pergunta, modo_pergunta, cultura=contexto.cultura
        )

        if not self.disponivel:
            logger.info("Izes IA sem OpenAI configurada; retornando fallback local.")
            if modo_pergunta == MODO_AGRO_GERAL:
                return self._resposta_agro_geral_fallback(contexto, pergunta_id, resultados_rag)
            return self._resposta_fallback(
                contexto, pergunta_id, motivo="OPENAI_API_KEY ausente", resultados_rag=resultados_rag
            )

        try:
            prompt = self._montar_prompt(contexto, modo_pergunta, resultados_rag)

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
                contexto=contexto,
                pergunta_id=pergunta_id,
                resposta_texto=resposta_texto,
                tokens_usados=tokens_usados,
                modo=modo_pergunta,
                resultados_rag=resultados_rag,
            )

        except Exception as e:
            logger.error("Erro ao chamar OpenAI; usando fallback local: %s", type(e).__name__)
            if modo_pergunta == MODO_AGRO_GERAL:
                return self._resposta_agro_geral_fallback(contexto, pergunta_id, resultados_rag)
            return self._resposta_fallback(
                contexto, pergunta_id, motivo="OpenAI indisponível", resultados_rag=resultados_rag
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
                    {
                        "role": "system",
                        "content": (
                            "Você analisa imagens para o app IZES. "
                            "Responda em português do Brasil, de forma objetiva e sem inventar diagnóstico."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": PROMPT_ANALISE_IMAGEM},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_base64}",
                                },
                            },
                        ],
                    },
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
        modo_pergunta: Optional[str] = None,
        resultados_rag: Optional[List[ResultadoRAG]] = None,
    ) -> str:
        """Monta prompt estruturado, separando dados reais e conhecimento técnico."""
        modo = modo_pergunta or classificar_escopo_pergunta(
            contexto.usuario_pergunta,
            cliente_id=contexto.cliente_id,
            sensor_id=contexto.sensor_id,
        )
        dados = self._dados_para_prompt(contexto, modo)
        resultados_rag = resultados_rag or []

        conhecimento = [
            {
                "documento_id": r.chunk.get("documento_id"),
                "titulo": r.chunk.get("titulo"),
                "instituicao": r.chunk.get("instituicao"),
                "ano": r.chunk.get("ano"),
                "paginas": r.fonte().get("paginas"),
                "tema": r.chunk.get("tema"),
                "confiabilidade": r.chunk.get("confiabilidade"),
                "trecho": r.chunk.get("texto"),
            }
            for r in resultados_rag
        ]
        fontes = [r.fonte() for r in resultados_rag]

        if modo == MODO_AGRO_GERAL:
            instrucao_modo = (
                "- Modo agro_geral: responda uma dúvida agro/rural geral para pequeno produtor.\n"
                "- Não use dados de sensor, leitura, alerta, pH, NPK, cidade, fazenda ou talhão do cliente.\n"
                "- Use o CONHECIMENTO TÉCNICO RECUPERADO quando existir; se não houver, responda com orientação geral segura.\n"
                "- Não invente dados reais; se faltar base específica, diga que é orientação geral."
            )
        else:
            instrucao_modo = (
                "- Modo agro_com_dados: analise somente os DADOS REAIS fornecidos (sensores, leituras, avaliações, alertas).\n"
                "- Separe claramente medição (dado real) de interpretação e de referência técnica (RAG).\n"
                "- Compare os sensores/áreas quando a pergunta pedir e diga qual merece mais atenção.\n"
                "- Não invente dados ausentes; explique o risco principal e o que fazer agora em linguagem simples."
            )

        return f"""
ANÁLISE AGRÍCOLA IZES - RESPONDA SOMENTE COM JSON VÁLIDO
Modo da pergunta: {modo}

PERGUNTA DO USUÁRIO:
{contexto.usuario_pergunta}

DADOS REAIS DO CLIENTE (somente o que foi efetivamente consultado):
{json.dumps(dados, ensure_ascii=False, indent=2, default=str)}

CONHECIMENTO TÉCNICO RECUPERADO (use apenas estes trechos; não cite outra fonte):
{json.dumps(conhecimento, ensure_ascii=False, indent=2, default=str)}

FONTES DISPONÍVEIS (corresponderão ao que você usar):
{json.dumps(fontes, ensure_ascii=False, indent=2, default=str)}

Formato JSON obrigatório:
{{
  "resposta_texto": "Situação:\\n...\\n\\nRisco:\\n...\\n\\nO que fazer agora:\\n1. ...\\n2. ...\\n3. ...\\n\\nAtenção:\\nNão aplique dose exata sem análise de solo ou agrônomo.",
  "recomendacao": {{
    "acao": "uma frase objetiva",
    "motivo": "uma frase simples",
    "riscos_se_nao_fizer": "uma frase simples",
    "beneficios": "uma frase simples"
  }},
  "atencoes": ["até 3 itens curtos"],
  "proximos_passos": ["até 3 itens curtos"],
  "confianca_geral": 0.0
}}

Regras do modo:
{instrucao_modo}

Regras obrigatórias:
- Use no máximo 5 a 8 linhas no campo resposta_texto.
- Frases curtas, linguagem simples, sem relatório técnico.
- Não responda conhecimento geral fora do domínio agro/rural/sensores/solo/lavoura/app.
- Não invente fazenda, sensor, leitura, cultura, clima, cidade, talhão, histórico, alerta ou cliente.
- Não cite documento que não esteja em CONHECIMENTO TÉCNICO RECUPERADO.
- Não trate sensor como análise laboratorial; admita incerteza e limitações.
- Não recomende dose exata de fertilizante/corretivo sem cultura, área, análise de solo e validação técnica.
- Recomende agrônomo ou análise laboratorial quando a decisão exigir validação técnica.
- Se faltar dado real no modo agro_com_dados, diga exatamente qual dado faltou e não complete por suposição.
""".strip()

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
            "sensores_relevantes": [sensor.model_dump(mode="json") for sensor in contexto.sensores_relevantes],
            "alertas_ativos": [alerta.model_dump(mode="json") for alerta in contexto.alertas_ativos],
            "alertas_historico_30_dias": [alerta.model_dump(mode="json") for alerta in contexto.alertas_historico_30_dias],
            "clima_atual": contexto.clima_atual,
            "clima_ultimos_7_dias": {
                sensor_id: clima.model_dump(mode="json")
                for sensor_id, clima in contexto.clima_ultimos_7_dias.items()
            },
            "previsao_7_dias": contexto.previsao_7_dias,
            "plano_agronomo": contexto.plano_agronomo,
            "cultura": contexto.cultura,
            "fase_desenvolvimento": contexto.fase_desenvolvimento,
            "prioridades": contexto.prioridades,
            "timestamp_coleta": contexto.timestamp_coleta.isoformat(),
        }

    def _prompt_sistema(self) -> str:
        return (
            "Você é o assistente agro do IZES para agricultura, pecuária, solo, sensores e manejo. "
            "Responda apenas com JSON válido, curto, em português claro e respeitando o modo da pergunta. "
            "No modo agro_geral, não use nem invente dados de sensor, leitura, alerta, fazenda, cidade ou talhão. "
            "No modo agro_com_dados, use somente os dados reais fornecidos e separe medição de interpretação. "
            "Use apenas o conhecimento técnico recuperado fornecido; nunca cite documento que não foi recuperado. "
            "Recuse perguntas fora de escopo agro/rural/sensores/solo/lavoura/app. "
            "Não dê dose exata de fertilizante ou corretivo sem cultura, área, análise de solo e validação técnica. "
            "Deixe claro que a resposta é orientação e não substitui laudo agronômico."
        )

    def pergunta_dentro_escopo(self, pergunta: str) -> bool:
        return classificar_escopo_pergunta(pergunta) != MODO_FORA_ESCOPO

    def _normalizar(self, texto: str) -> str:
        return _normalizar_texto(texto)

    def _contexto_tem_dados_suficientes(self, contexto: ContextoIA) -> bool:
        return any([
            any(sensor.ultima_leitura for sensor in contexto.sensores_relevantes),
            any(sensor.avaliacoes for sensor in contexto.sensores_relevantes),
            bool(contexto.alertas_ativos),
            bool(contexto.alertas_historico_30_dias),
        ])

    def _contexto_agro_geral(self, contexto: ContextoIA) -> ContextoIA:
        """Remove qualquer dado real do cliente para dúvida agro/rural geral."""
        return ContextoIA(
            cliente_id=contexto.cliente_id,
            sensor_id=None,
            usuario_pergunta=contexto.usuario_pergunta,
            tokens_estimado=0,
        )

    def _dados_consultados(self, contexto: ContextoIA, modo: Optional[str] = None) -> list:
        if modo == MODO_AGRO_GERAL:
            return ["conhecimento_agro_geral"]

        dados = []
        if contexto.sensores_relevantes:
            dados.append("sensores")
            if any(sensor.ultima_leitura for sensor in contexto.sensores_relevantes):
                dados.append("ultima_leitura")
            if any(sensor.avaliacoes for sensor in contexto.sensores_relevantes):
                dados.append("avaliacoes_agronomicas")
        if contexto.alertas_ativos:
            dados.append("alertas_ativos")
        if contexto.alertas_historico_30_dias:
            dados.append("historico_alertas")
        if contexto.clima_atual or contexto.clima_ultimos_7_dias or contexto.previsao_7_dias:
            dados.append("clima")
        if contexto.plano_agronomo or contexto.cultura or contexto.fase_desenvolvimento:
            dados.append("cultura")
        return dados or ["pergunta_usuario"]

    # ------------------------------------------------------- encerramento
    def _encerramento_contextual(self, modo: str, contexto: ContextoIA, tem_dados: bool) -> str:
        """Sugestão final útil e contextual, terminando com 'É só pedir.'.

        Não é usado em erros técnicos, fora de escopo ou esclarecimento.
        """
        seed = abs(hash(contexto.usuario_pergunta or "")) % 2

        if modo == MODO_AGRO_GERAL:
            opcoes = [
                "Posso relacionar isso com a sua cultura, região ou com os dados dos seus sensores. É só pedir.",
                "Se quiser, comparo isso com as leituras atuais das suas áreas e mostro o que vale acompanhar. É só pedir.",
            ]
            return opcoes[seed]

        if not tem_dados:
            return (
                "Posso analisar melhor quando você informar a área, o canteiro ou o sensor desejado. É só pedir."
            )

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

    def _aplicar_encerramento(
        self, resposta_texto: str, modo: str, contexto: ContextoIA, tem_dados: bool
    ) -> str:
        if modo not in (MODO_AGRO_COM_DADOS, MODO_AGRO_GERAL):
            return resposta_texto
        encerramento = self._encerramento_contextual(modo, contexto, tem_dados)
        texto = (resposta_texto or "").rstrip()
        if "é só pedir" in texto.lower():
            return texto
        return f"{texto}\n\n{encerramento}"

    # --------------------------------------------------------- respostas
    def _resposta_fallback(
        self,
        contexto: ContextoIA,
        pergunta_id: str,
        motivo: str,
        resultados_rag: Optional[List[ResultadoRAG]] = None,
    ) -> RespostaIA:
        """Resposta local segura quando OpenAI não está configurada ou indisponível."""
        sensores_com_leitura = [
            sensor for sensor in contexto.sensores_relevantes if sensor.ultima_leitura
        ]
        alertas = contexto.alertas_ativos

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
                mensagem = avaliacao.get("mensagem")
                if nivel and nivel not in {"ok", "ideal"}:
                    riscos.append(f"{sensor.sensor_id} - {parametro}: {nivel}. {mensagem or ''}".strip())

        if riscos:
            risco_texto = " ".join(riscos)
        else:
            risco_texto = "Não há alerta ativo ou avaliação crítica disponível no contexto recebido."

        proximos_passos = [
            "Conferir última leitura e alertas no dashboard.",
            "Coletar nova leitura se os dados estiverem antigos.",
            "Chamar agrônomo se houver alerta crítico.",
        ]
        resposta_texto = self._formatar_resposta_curta(
            situacao=situacao,
            risco=risco_texto,
            passos=proximos_passos,
        )
        resposta_texto = self._aplicar_encerramento(
            resposta_texto, MODO_AGRO_COM_DADOS, contexto, tem_dados=True
        )

        return RespostaIA(
            pergunta_id=pergunta_id,
            cliente_id=contexto.cliente_id,
            sensor_id=contexto.sensor_id,
            resposta_texto=resposta_texto,
            resposta_estruturada={
                "modo": "fallback_local",
                "origem": "fallback_local",
                "motivo": motivo,
                "dados_reais": bool(self._dados_consultados(contexto) != ["pergunta_usuario"]),
                "sensores_consultados": len(contexto.sensores_relevantes),
                "sensores_com_leitura": len(sensores_com_leitura),
                "alertas_ativos": len(alertas),
            },
            recomendacao=RecomendacaoIA(
                acao="Validar os dados no dashboard e monitorar novas leituras antes de executar manejo.",
                confianca=0.55 if sensores_com_leitura or alertas else 0.35,
                motivo="Resposta local baseada apenas nos dados já disponíveis no contexto.",
                riscos_se_nao_fizer="Decisão de manejo sem validação pode gerar ação inadequada.",
                beneficios="Reduz risco de agir com dados incompletos."
            ),
            dados_consultados=self._dados_consultados(contexto),
            atencoes=[
                "Orientação preliminar; não substitui laudo agronômico.",
                AVISO_DOSE,
            ],
            proximos_passos=proximos_passos,
            fontes=self._fontes(resultados_rag),
            confianca_geral=0.55 if sensores_com_leitura or alertas else 0.35,
            requer_validacao_humana=True,
            modelo="fallback-local",
            tokens_usados=0,
            tempo_resposta_segundos=0,
            criado_em=datetime.now()
        )

    def _resposta_dados_insuficientes(self, contexto: ContextoIA, pergunta_id: str) -> RespostaIA:
        passos = [
            "Registrar uma leitura real do sensor.",
            "Verificar se há alertas no dashboard.",
            "Enviar nova pergunta depois da coleta.",
        ]
        return self._montar_resposta_segura(
            contexto=contexto,
            pergunta_id=pergunta_id,
            resposta_texto=self._formatar_resposta_curta(
                situacao="Não tenho leitura real para esse caso.",
                risco="Não há dados suficientes para orientar manejo.",
                passos=passos,
            ),
            modo=MODO_AGRO_COM_DADOS,
            origem="fallback_local",
            recomendacao=RecomendacaoIA(
                acao="Coletar uma leitura real antes de decidir manejo.",
                confianca=0.3,
                motivo="O contexto não tem leitura, alerta ou avaliação.",
                riscos_se_nao_fizer="A decisão pode ser tomada sem base real.",
                beneficios="A análise passa a usar dados reais do campo.",
            ),
            atencoes=[AVISO_DOSE],
            proximos_passos=passos,
            confianca=0.3,
            modelo="sem-openai",
            tem_dados=False,
        )

    def _resposta_agro_geral_fallback(
        self,
        contexto: ContextoIA,
        pergunta_id: str,
        resultados_rag: Optional[List[ResultadoRAG]] = None,
    ) -> RespostaIA:
        situacao = "A pergunta é agro/rural geral e será respondida sem usar sensores do cliente."
        risco = "Para recomendação exata, faltam região, cultura/fase, área e análise técnica."
        passos = [
            "Descrever cultura, criação ou problema do campo.",
            "Usar análise de solo ou orientação técnica para decisões exatas.",
            "Ativar OpenAI para resposta agro geral mais completa.",
        ]
        acao = "Responder como orientação agro geral, sem dados de sensor."
        motivo = "A pergunta não pediu análise de leitura, sensor ou alerta."

        return self._montar_resposta_segura(
            contexto=contexto,
            pergunta_id=pergunta_id,
            resposta_texto=self._formatar_resposta_curta(
                situacao=situacao,
                risco=risco,
                passos=passos,
            ),
            modo=MODO_AGRO_GERAL,
            origem="fallback_local",
            recomendacao=RecomendacaoIA(
                acao=acao,
                confianca=0.55,
                motivo=motivo,
                riscos_se_nao_fizer="Pode perder produtividade por preparo ou manejo inadequado.",
                beneficios="Ajuda a começar com mais segurança e menos desperdício.",
            ),
            atencoes=[AVISO_DOSE],
            proximos_passos=passos,
            confianca=0.55,
            modelo="fallback-local",
            resultados_rag=resultados_rag,
        )

    def _resposta_openai_estruturada(
        self,
        contexto: ContextoIA,
        pergunta_id: str,
        resposta_texto: str,
        tokens_usados: int,
        modo: str = MODO_AGRO_COM_DADOS,
        resultados_rag: Optional[List[ResultadoRAG]] = None,
    ) -> RespostaIA:
        try:
            payload = json.loads(resposta_texto)
            # Reserva 1 linha para o encerramento contextual (mantém o total <= 8).
            resposta_curta = self._limitar_texto(str(payload["resposta_texto"]), max_linhas=7, max_chars=820)
            recomendacao_raw = payload.get("recomendacao") or {}
            recomendacao = RecomendacaoIA(
                acao=self._frase_curta(recomendacao_raw.get("acao"), "Validar dados no dashboard antes do manejo."),
                confianca=float(payload.get("confianca_geral", 0.8)),
                motivo=self._frase_curta(recomendacao_raw.get("motivo"), "Baseado apenas no contexto real recebido."),
                riscos_se_nao_fizer=self._frase_curta(recomendacao_raw.get("riscos_se_nao_fizer"), "Pode haver decisão sem validação."),
                beneficios=self._frase_curta(recomendacao_raw.get("beneficios"), "Reduz risco de agir com dado incompleto."),
            )
            atencoes = self._lista_curta(payload.get("atencoes"), fallback=[AVISO_DOSE])
            proximos_passos = self._lista_curta(payload.get("proximos_passos"), fallback=["Conferir dados no dashboard."])
            return self._montar_resposta_segura(
                contexto=contexto,
                pergunta_id=pergunta_id,
                resposta_texto=resposta_curta,
                modo=modo,
                origem="openai",
                recomendacao=recomendacao,
                atencoes=atencoes,
                proximos_passos=proximos_passos,
                confianca=recomendacao.confianca,
                modelo=self.model,
                tokens_usados=tokens_usados,
                resultados_rag=resultados_rag,
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            logger.warning("OpenAI retornou JSON inválido para IA; usando fallback local seguro.")
            if modo == MODO_AGRO_GERAL:
                return self._resposta_agro_geral_fallback(contexto, pergunta_id, resultados_rag)
            return self._resposta_fallback(
                contexto, pergunta_id, motivo="Resposta OpenAI inválida", resultados_rag=resultados_rag
            )

    def _fontes(self, resultados_rag: Optional[List[ResultadoRAG]]) -> list:
        """Retorna apenas fontes que realmente entraram no contexto (sem duplicar)."""
        if not resultados_rag:
            return []
        fontes = []
        vistos = set()
        for resultado in resultados_rag:
            fonte = resultado.fonte()
            chave = (fonte.get("documento_id"), fonte.get("paginas"))
            if chave in vistos:
                continue
            vistos.add(chave)
            fontes.append(fonte)
        return fontes

    def _montar_resposta_segura(
        self,
        contexto: ContextoIA,
        pergunta_id: str,
        resposta_texto: str,
        modo: str,
        origem: str,
        recomendacao: RecomendacaoIA,
        atencoes: list,
        proximos_passos: list,
        confianca: float,
        modelo: str,
        tokens_usados: int = 0,
        resultados_rag: Optional[List[ResultadoRAG]] = None,
        tem_dados: Optional[bool] = None,
    ) -> RespostaIA:
        dados_consultados = self._dados_consultados(contexto, modo)
        fontes = self._fontes(resultados_rag)
        if tem_dados is None:
            tem_dados = self._contexto_tem_dados_suficientes(contexto)
        resposta_texto = self._aplicar_encerramento(resposta_texto, modo, contexto, tem_dados)
        return RespostaIA(
            pergunta_id=pergunta_id,
            cliente_id=contexto.cliente_id,
            sensor_id=contexto.sensor_id,
            resposta_texto=resposta_texto,
            resposta_estruturada={
                "modo": modo,
                "origem": origem,
                "dados_reais": dados_consultados not in (["pergunta_usuario"], ["conhecimento_agro_geral"]),
            },
            recomendacao=recomendacao,
            dados_consultados=dados_consultados,
            atencoes=atencoes[:3],
            proximos_passos=proximos_passos[:3],
            fontes=fontes,
            confianca_geral=max(0.0, min(float(confianca), 1.0)),
            requer_validacao_humana=True,
            modelo=modelo,
            tokens_usados=tokens_usados,
            tempo_resposta_segundos=0,
            criado_em=datetime.now()
        )

    def _resposta_esclarecimento(self, contexto: ContextoIA, pergunta_id: str) -> RespostaIA:
        """Pergunta ambígua sem contexto suficiente: pede um esclarecimento objetivo."""
        pergunta = (
            "Você quer uma visão geral de todas as áreas ou a análise de um sensor específico? "
            "Qual área, canteiro ou sensor você deseja analisar?"
        )
        return RespostaIA(
            pergunta_id=pergunta_id,
            cliente_id=contexto.cliente_id,
            sensor_id=contexto.sensor_id,
            resposta_texto=pergunta,
            resposta_estruturada={
                "modo": MODO_ESCLARECIMENTO,
                "origem": "regra_contextual",
                "dados_reais": False,
            },
            recomendacao=RecomendacaoIA(
                acao="Informar a área, o canteiro ou o sensor que deseja analisar.",
                confianca=0.5,
                motivo="A pergunta está ambígua e não há contexto suficiente para responder com segurança.",
                riscos_se_nao_fizer="Sem o alvo, a análise pode usar dados que não são os desejados.",
                beneficios="Garante que a análise use exatamente a área ou sensor certo.",
            ),
            dados_consultados=["pergunta_usuario"],
            atencoes=[],
            proximos_passos=[],
            fontes=[],
            confianca_geral=0.5,
            requer_validacao_humana=False,
            modelo="regra-contextual",
            tokens_usados=0,
            tempo_resposta_segundos=0,
            criado_em=datetime.now(),
        )

    def _resposta_fora_escopo(self, contexto: ContextoIA, pergunta_id: str) -> RespostaIA:
        return RespostaIA(
            pergunta_id=pergunta_id,
            cliente_id=contexto.cliente_id,
            sensor_id=contexto.sensor_id,
            resposta_texto=RESPOSTA_FORA_ESCOPO,
            resposta_estruturada={
                "modo": MODO_FORA_ESCOPO,
                "origem": "sem_openai",
                "dados_reais": False,
            },
            recomendacao=RecomendacaoIA(
                acao="Fazer uma pergunta sobre sensores, solo, alertas, leituras ou manejo.",
                confianca=1.0,
                motivo="A pergunta está fora do escopo do assistente agro.",
                riscos_se_nao_fizer="A dúvida fora de escopo não será analisada pelo IZES.",
                beneficios="Mantém o assistente focado em dados reais do campo.",
            ),
            dados_consultados=["pergunta_usuario"],
            atencoes=[],
            proximos_passos=[],
            fontes=[],
            confianca_geral=1.0,
            requer_validacao_humana=False,
            modelo="sem-openai",
            tokens_usados=0,
            tempo_resposta_segundos=0,
            criado_em=datetime.now(),
        )

    def _formatar_resposta_curta(self, situacao: str, risco: str, passos: list) -> str:
        passos = passos[:3]
        linhas = [
            f"Situação: {self._limitar_texto(situacao, max_linhas=1, max_chars=220)}",
            "",
            f"Risco: {self._limitar_texto(risco, max_linhas=1, max_chars=260)}",
            "",
            "O que fazer agora:",
        ]
        linhas.extend(f"{idx}. {self._limitar_texto(passo, max_linhas=1, max_chars=120)}" for idx, passo in enumerate(passos, 1))
        linhas.extend(["", f"Atenção: {AVISO_DOSE}"])
        return "\n".join(linhas)

    def _frase_curta(self, valor: object, fallback: str) -> str:
        texto = str(valor or fallback).strip()
        return self._limitar_texto(texto, max_linhas=1, max_chars=160)

    def _lista_curta(self, valor: object, fallback: list) -> list:
        if not isinstance(valor, list):
            valor = fallback
        itens = [self._frase_curta(item, "") for item in valor if str(item or "").strip()]
        return (itens or fallback)[:3]

    def _limitar_texto(self, texto: str, max_linhas: int, max_chars: int) -> str:
        linhas = [linha.strip() for linha in str(texto or "").splitlines() if linha.strip()]
        limitado = "\n".join(linhas[:max_linhas]).strip()
        return limitado[:max_chars].rstrip()
