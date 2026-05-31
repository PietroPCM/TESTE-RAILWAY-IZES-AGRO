"""
Serviço de Integração com Izes IA (powered by OpenAI/ChatGPT)
"""

import logging
from openai import OpenAI
from app.config import settings
from app.models.contratos import ContextoIA, RespostaIA, RecomendacaoIA
from datetime import datetime
import json

logger = logging.getLogger(__name__)


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
        
        if not self.disponivel:
            logger.info("Izes IA sem OpenAI configurada; retornando fallback local.")
            return self._resposta_fallback(contexto, pergunta_id, motivo="OPENAI_API_KEY ausente")
        
        try:
            # Montar prompt com contexto
            prompt = self._montar_prompt(contexto)
            
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
                max_tokens=settings.openai_max_tokens,
            )
            
            # Extrair resposta
            resposta_texto = response.choices[0].message.content
            tokens_usados = response.usage.total_tokens if response.usage else 0
            
            logger.info(f"Resposta Izes: {len(resposta_texto)} caracteres, {tokens_usados} tokens")
            
            # Estruturar resposta
            return RespostaIA(
                pergunta_id=pergunta_id,
                cliente_id=contexto.cliente_id,
                sensor_id=contexto.sensor_id,
                resposta_texto=resposta_texto,
                resposta_estruturada={
                    "modo": "openai",
                    "dados_reais": True,
                    "aviso": "Orientação técnica preliminar; não substitui laudo agronômico."
                },
                recomendacao=self._extrair_recomendacao(resposta_texto),
                dados_consultados=self._dados_consultados(contexto),
                atencoes=self._extrair_atencoes(resposta_texto),
                proximos_passos=self._extrair_passos(resposta_texto),
                confianca_geral=0.80,
                requer_validacao_humana=True,
                modelo=self.model,
                tokens_usados=tokens_usados,
                tempo_resposta_segundos=0,
                criado_em=datetime.now()
            )
            
        except Exception as e:
            logger.error("Erro ao chamar OpenAI; usando fallback local: %s", type(e).__name__)
            return self._resposta_fallback(contexto, pergunta_id, motivo="OpenAI indisponível")
    
    def _montar_prompt(self, contexto: ContextoIA) -> str:
        """Monta prompt estruturado para ChatGPT"""
        dados = {
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
ANÁLISE AGRÍCOLA IZES - USE SOMENTE OS DADOS ABAIXO

Dados disponíveis em JSON:
{json.dumps(dados, ensure_ascii=False, indent=2, default=str)}

Pergunta do usuário:
{contexto.usuario_pergunta}

Formato obrigatório da resposta:
1. Situação: explique em linguagem simples o que os dados mostram.
2. Risco: descreva os riscos agronômicos e a urgência.
3. Recomendação: indique ações práticas e seguras.
4. Próximos passos: diga o que monitorar ou confirmar.
5. Limitações: informe dados ausentes e deixe claro que é orientação, não laudo agronômico.

Regras obrigatórias:
- Não invente sensor, leitura, alerta, cultura, clima, área ou histórico que não esteja no JSON.
- Use as avaliações e alertas já calculados quando existirem.
- Não recomende dose exata de fertilizante/corretivo sem cultura, área, análise de solo e validação técnica.
- Recomende agrônomo ou análise laboratorial quando a decisão exigir validação técnica.
- Se faltar dado, diga exatamente qual dado faltou.
""".strip()

    def _prompt_sistema(self) -> str:
        return (
            "Você é a IA agrícola do IZES para apoio à decisão no campo. "
            "Responda em português claro, com prudência agronômica, usando apenas os dados recebidos. "
            "Separe situação, risco, recomendação, próximos passos e limitações. "
            "Não dê dose exata de fertilizante ou corretivo sem cultura, área, análise de solo e validação técnica. "
            "Deixe claro que a resposta é orientação e não substitui laudo agronômico."
        )
    
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
            urgencia = "Verifique os pontos sinalizados antes de tomar decisão operacional."
        else:
            risco_texto = "Não há alerta ativo ou avaliação crítica disponível no contexto recebido."
            urgencia = "Continue monitorando e envie novas leituras para melhorar a análise."

        resposta_texto = (
            f"Situação: {situacao}\n\n"
            f"Risco: {risco_texto}\n\n"
            "Recomendação: use esta resposta como triagem. Confira a última leitura no dashboard, "
            "compare com o histórico e valide em campo antes de executar manejo.\n\n"
            f"Urgência: {urgencia}\n\n"
            "Limitações: a OpenAI não foi usada nesta resposta. Esta orientação não substitui laudo agronômico. "
            "Não recomendo dose exata de fertilizante ou corretivo sem cultura, área, análise de solo "
            "e validação de um profissional responsável."
        )

        return RespostaIA(
            pergunta_id=pergunta_id,
            cliente_id=contexto.cliente_id,
            sensor_id=contexto.sensor_id,
            resposta_texto=resposta_texto,
            resposta_estruturada={
                "modo": "fallback_local",
                "motivo": motivo,
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
                "Não usar para dose exata sem análise de solo e validação técnica.",
            ],
            proximos_passos=[
                "Conferir última leitura e alertas no dashboard.",
                "Coletar nova leitura se os dados estiverem antigos.",
                "Acionar agrônomo quando houver alerta crítico ou decisão de adubação/correção.",
            ],
            confianca_geral=0.55 if sensores_com_leitura or alertas else 0.35,
            requer_validacao_humana=True,
            modelo="fallback-local",
            tokens_usados=0,
            tempo_resposta_segundos=0,
            criado_em=datetime.now()
        )

    def _extrair_recomendacao(self, resposta_texto: str) -> RecomendacaoIA:
        """Extrai estrutura de RecomendacaoIA da resposta"""
        
        # Tenta extrair ação (primeira linha com "ação" ou "recomend")
        linhas = resposta_texto.split('\n')
        acao = "Ver análise completa acima"
        
        for linha in linhas:
            if any(palavra in linha.lower() for palavra in ['ação:', 'recomendo:', 'aplique']):
                acao = linha.replace('Ação:', '').replace('ação:', '').strip()
                break
        
        return RecomendacaoIA(
            acao=acao[:200],  # Primeiros 200 caracteres
            confianca=0.80,
            motivo="Análise de IA com dados disponíveis no contexto IZES",
            riscos_se_nao_fizer="Ver análise completa para detalhes",
            beneficios="Otimização da produção e saúde da planta"
        )
    
    def _extrair_atencoes(self, resposta_texto: str) -> list:
        """Extrai pontos de atenção da resposta"""
        atencoes = []
        
        # Palavras-chave que indicam atenção
        linhas = resposta_texto.split('\n')
        for linha in linhas:
            if any(palavra in linha.lower() for palavra in ['cuidado', 'atenção', 'risco', 'monitorar', 'evitar']):
                atencao_limpa = linha.replace('Atenção:', '').replace('atenção:', '').strip()
                if atencao_limpa and len(atencao_limpa) > 10:
                    atencoes.append(atencao_limpa[:150])
        
        return atencoes[:3] if atencoes else []
    
    def _extrair_passos(self, resposta_texto: str) -> list:
        """Extrai próximos passos da resposta"""
        passos = []
        
        # Procura por listas numeradas ou próximas passos
        linhas = resposta_texto.split('\n')
        for linha in linhas:
            if any(prefixo in linha for prefixo in ['1.', '2.', '3.', '-', '*', 'Próximo:', 'Depois:']):
                passo_limpo = linha.lstrip('123456789. -* ').strip()
                if passo_limpo and len(passo_limpo) > 10:
                    passos.append(passo_limpo[:150])
        
        return passos[:5] if passos else ["Monitorar os parâmetros nos próximos dias"]
