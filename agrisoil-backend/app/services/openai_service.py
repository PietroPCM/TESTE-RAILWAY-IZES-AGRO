"""
Serviço de Integração com Izes IA (powered by OpenAI/ChatGPT)
"""

import logging
from openai import OpenAI
from app.config import settings
from app.models.contratos import ContextoIA, RespostaIA, RecomendacaoIA
from datetime import datetime
import json
import unicodedata
from typing import Optional

logger = logging.getLogger(__name__)

MODO_FORA_ESCOPO = "fora_escopo"
MODO_AGRO_GERAL = "agro_geral"
MODO_AGRO_COM_DADOS = "agro_com_dados"

RESPOSTA_FORA_ESCOPO = (
    "Eu sou o assistente agro do IZES. Posso ajudar com sensores, solo, "
    "alertas, leituras e manejo da lavoura."
)

AVISO_DOSE = "Não aplique dose exata sem análise de solo ou agrônomo."


def _normalizar_texto(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    return "".join(ch for ch in sem_acento if not unicodedata.combining(ch)).lower()


def classificar_escopo_pergunta(pergunta: str) -> str:
    """Classifica pergunta sem depender de OpenAI ou contexto do banco."""
    texto = _normalizar_texto(pergunta)
    termos_dados = {
        "sensor", "sensores", "leitura", "leituras", "alerta", "alertas",
        "dashboard", "agora", "desse sensor", "deste sensor", "meu sensor",
        "minha leitura", "risco desse", "risco deste", "principal risco",
        "umidade", "ph", "temperatura", "condutividade", "nitrogenio",
        "fosforo", "potassio", "npk",
    }
    termos_agro = {
        "agro", "agricola", "agricultura", "agronom", "campo", "rural",
        "produtor", "lavoura", "plantar", "plantio", "planta", "plantacao",
        "colheita", "cultivo", "cultivar", "cultura", "safra", "semente",
        "sementes", "germinacao", "solo", "talhao", "fazenda", "propriedade",
        "manejo", "irrigacao", "irrigar", "adubo", "adubacao", "fertilizante",
        "corretivo", "calagem", "calcario", "acidez", "solo acido",
        "nitrogenio", "fosforo", "potassio", "npk", "praga", "pragas",
        "fungo", "fungos", "doenca", "ervas daninhas", "milho", "soja",
        "feijao", "arroz", "trigo", "cafe", "mandioca", "cana", "algodao",
        "horta", "hortalica", "tomate", "pastagem", "gado", "chuva",
        "seca", "geada", "clima", "inseto", "lagarta", "pulgao",
    }
    termos_fora = {
        "capital", "italia", "franca", "copa", "futebol", "politica",
        "presidente", "celebridade", "piada", "curiosidade", "matematica",
        "programacao", "receita", "filme", "musica",
    }

    if any(termo in texto for termo in termos_agro):
        if any(termo in texto for termo in termos_dados):
            return MODO_AGRO_COM_DADOS
        return MODO_AGRO_GERAL

    if any(termo in texto for termo in termos_dados):
        return MODO_AGRO_COM_DADOS

    if any(termo in texto for termo in termos_fora):
        return MODO_FORA_ESCOPO

    return MODO_FORA_ESCOPO


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
        pergunta_id: str
    ) -> RespostaIA:
        """
        Chama Izes IA para analisar contexto agrícola
        
        Args:
            contexto: Contexto montado com dados da propriedade
            pergunta_id: ID da pergunta para rastreamento
        
        Returns:
            RespostaIA com análise e recomendações
        """
        modo_pergunta = classificar_escopo_pergunta(contexto.usuario_pergunta)

        if modo_pergunta == MODO_FORA_ESCOPO:
            return self._resposta_fora_escopo(contexto, pergunta_id)

        if modo_pergunta == MODO_AGRO_COM_DADOS and not self._contexto_tem_dados_suficientes(contexto):
            return self._resposta_dados_insuficientes(contexto, pergunta_id)

        if not self.disponivel:
            logger.info("Izes IA sem OpenAI configurada; retornando fallback local.")
            if modo_pergunta == MODO_AGRO_GERAL:
                return self._resposta_agro_geral_fallback(contexto, pergunta_id)
            return self._resposta_fallback(contexto, pergunta_id, motivo="OPENAI_API_KEY ausente")
        
        try:
            # Montar prompt com contexto
            prompt = self._montar_prompt(contexto, modo_pergunta)
            
            # Chamar Izes IA
            logger.info(f"Chamando Izes para {pergunta_id}...")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._prompt_sistema()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=settings.openai_temperature,
                max_tokens=min(settings.openai_max_tokens, 700),
                response_format={"type": "json_object"},
            )
            
            # Extrair resposta
            resposta_texto = response.choices[0].message.content
            tokens_usados = response.usage.total_tokens if response.usage else 0
            
            logger.info(f"Resposta Izes: {len(resposta_texto)} caracteres, {tokens_usados} tokens")
            
            return self._resposta_openai_estruturada(
                contexto=contexto,
                pergunta_id=pergunta_id,
                resposta_texto=resposta_texto,
                tokens_usados=tokens_usados,
                modo=modo_pergunta,
            )
            
        except Exception as e:
            logger.error("Erro ao chamar OpenAI; usando fallback local: %s", type(e).__name__)
            if modo_pergunta == MODO_AGRO_GERAL:
                return self._resposta_agro_geral_fallback(contexto, pergunta_id)
            return self._resposta_fallback(contexto, pergunta_id, motivo="OpenAI indisponível")
    
    def _montar_prompt(self, contexto: ContextoIA, modo_pergunta: Optional[str] = None) -> str:
        """Monta prompt estruturado para ChatGPT"""
        modo = modo_pergunta or classificar_escopo_pergunta(contexto.usuario_pergunta)
        dados = {
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

        return f"""
ANÁLISE AGRÍCOLA IZES - RESPONDA SOMENTE COM JSON VÁLIDO
Modo da pergunta: {modo}

Dados disponíveis em JSON:
{json.dumps(dados, ensure_ascii=False, indent=2, default=str)}

Pergunta do usuário:
{contexto.usuario_pergunta}

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

Regras obrigatórias:
- Se o modo for agro_geral, responda orientação agrícola geral sem exigir sensor.
- Se o modo for agro_com_dados, use sensores, leituras, avaliações e alertas reais quando existirem.
- Use no máximo 5 a 8 linhas no campo resposta_texto.
- Frases curtas, linguagem simples, sem relatório técnico.
- Não responda conhecimento geral fora do domínio agro/sensores/solo/lavoura/app.
- Não invente fazenda, sensor, leitura, cultura, clima, cidade, talhão, histórico, alerta ou cliente.
- Se não houver dado real do cliente/sensor, diga que não tem leitura real para esse caso.
- Use as avaliações e alertas já calculados quando existirem.
- Não recomende dose exata de fertilizante/corretivo sem cultura, área, análise de solo e validação técnica.
- Recomende agrônomo ou análise laboratorial quando a decisão exigir validação técnica.
- Se faltar dado, diga exatamente qual dado faltou e não complete por suposição.
""".strip()

    def _prompt_sistema(self) -> str:
        return (
            "Você é a IA agrícola do IZES para apoio à decisão no campo. "
            "Responda apenas com JSON válido, curto, em português claro e usando somente os dados recebidos. "
            "Recuse perguntas fora de escopo agro/sensores/solo/lavoura/app. "
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
    
    def _dados_consultados(self, contexto: ContextoIA) -> list:
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

    def _resposta_fallback(self, contexto: ContextoIA, pergunta_id: str, motivo: str) -> RespostaIA:
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
        )

    def _resposta_agro_geral_fallback(self, contexto: ContextoIA, pergunta_id: str) -> RespostaIA:
        pergunta = self._normalizar(contexto.usuario_pergunta)
        if "milho" in pergunta:
            situacao = "Para plantar milho, comece pelo solo, semente certa e época indicada na sua região."
            risco = "Sem análise de solo, a adubação pode ficar fraca ou exagerada."
            passos = [
                "Preparar o solo e corrigir acidez se a análise indicar.",
                "Escolher semente adaptada e plantar na época recomendada.",
                "Acompanhar pragas, mato, umidade e nutrição da lavoura.",
            ]
            acao = "Planejar o plantio do milho com análise de solo e semente adequada."
            motivo = "Milho responde bem a solo corrigido, boa semente e manejo no começo."
        else:
            situacao = "Posso orientar de forma geral, mas não tenho leitura real para esse caso."
            risco = "Sem dados do talhão, a recomendação deve ser usada só como orientação inicial."
            passos = [
                "Verificar solo, cultura e fase da lavoura.",
                "Coletar análise de solo antes de adubar ou corrigir.",
                "Consultar um agrônomo para decisão de dose.",
            ]
            acao = "Usar orientação geral e coletar dados reais antes de decidir manejo."
            motivo = "A pergunta é agro, mas não veio com leitura real do campo."

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
        )

    def _resposta_openai_estruturada(
        self,
        contexto: ContextoIA,
        pergunta_id: str,
        resposta_texto: str,
        tokens_usados: int,
        modo: str = "openai",
    ) -> RespostaIA:
        try:
            payload = json.loads(resposta_texto)
            resposta_curta = self._limitar_texto(str(payload["resposta_texto"]), max_linhas=8, max_chars=900)
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
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            logger.warning("OpenAI retornou JSON inválido para IA; usando fallback local seguro.")
            if modo == MODO_AGRO_GERAL:
                return self._resposta_agro_geral_fallback(contexto, pergunta_id)
            return self._resposta_fallback(contexto, pergunta_id, motivo="Resposta OpenAI inválida")

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
    ) -> RespostaIA:
        return RespostaIA(
            pergunta_id=pergunta_id,
            cliente_id=contexto.cliente_id,
            sensor_id=contexto.sensor_id,
            resposta_texto=resposta_texto,
            resposta_estruturada={
                "modo": modo,
                "origem": origem,
                "dados_reais": bool(self._dados_consultados(contexto) != ["pergunta_usuario"]),
            },
            recomendacao=recomendacao,
            dados_consultados=self._dados_consultados(contexto),
            atencoes=atencoes[:3],
            proximos_passos=proximos_passos[:3],
            confianca_geral=max(0.0, min(float(confianca), 1.0)),
            requer_validacao_humana=True,
            modelo=modelo,
            tokens_usados=tokens_usados,
            tempo_resposta_segundos=0,
            criado_em=datetime.now()
        )

    def _resposta_fora_escopo(self, contexto: ContextoIA, pergunta_id: str) -> RespostaIA:
        return self._montar_resposta_segura(
            contexto=contexto,
            pergunta_id=pergunta_id,
            resposta_texto=RESPOSTA_FORA_ESCOPO,
            modo="fora_escopo",
            origem="sem_openai",
            recomendacao=RecomendacaoIA(
                acao="Fazer uma pergunta sobre sensores, solo, alertas, leituras ou manejo.",
                confianca=1.0,
                motivo="A pergunta está fora do escopo do assistente agro.",
                riscos_se_nao_fizer="A dúvida fora de escopo não será analisada pelo IZES.",
                beneficios="Mantém o assistente focado em dados reais do campo.",
            ),
            atencoes=[],
            proximos_passos=[],
            confianca=1.0,
            modelo="sem-openai",
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
