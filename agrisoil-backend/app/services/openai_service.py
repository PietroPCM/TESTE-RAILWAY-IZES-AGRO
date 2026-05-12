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
        if not settings.openai_api_key:
            logger.warning("OPENAI_API_KEY não configurada!")
            self.disponivel = False
            return
        
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
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
            logger.error("Izes não disponível (API key não configurada)")
            return None
        
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
                        "content": "Você é um especialista em agronomia e agricultura de precisão. Forneça análises técnicas e recomendações práticas para agricultores."
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
                recomendacao=self._extrair_recomendacao(resposta_texto),
                dados_consultados=["leituras", "clima", "historico", "cultura"],
                atencoes=self._extrair_atencoes(resposta_texto),
                proximos_passos=self._extrair_passos(resposta_texto),
                confianca_geral=0.90,
                modelo=self.model,
                tokens_usados=tokens_usados,
                tempo_resposta_segundos=0,
                criado_em=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Erro ao chamar OpenAI: {e}")
            return None
    
    def _montar_prompt(self, contexto: ContextoIA) -> str:
        """Monta prompt estruturado para ChatGPT"""
        
        leitura = contexto.leitura_atual
        
        prompt = f"""
ANÁLISE AGRÍCOLA - DADOS ATUAIS

PROPRIEDADE:
- Cliente ID: {contexto.cliente_id}
- Pergunta: {contexto.usuario_pergunta}
- Sensor: {contexto.sensor_id}

DADOS DE SOLO (Leitura Atual):
- pH: {leitura.ph:.1f} (ideal: 5.5-7.5)
- Umidade do Solo: {leitura.umidade:.1f}% (ideal: 60-80%)
- Temperatura: {leitura.temperatura:.1f}°C (ideal: 15-30°C)
- Condutividade: {leitura.condutividade:.0f} µS/cm
- Nitrogênio (N): {leitura.nitrogenio:.0f} ppm (ideal: 100-300)
- Fósforo (P): {leitura.fosforo:.0f} ppm (ideal: 30-100)
- Potássio (K): {leitura.potassio:.0f} ppm (ideal: 150-400)

HISTÓRICO - ÚLTIMOS 7 DIAS:
{self._formatar_historico(contexto.historico_7_dias)}

CLIMA - ÚLTIMOS 7 DIAS:
{self._formatar_clima(contexto.clima_semana)}

CULTURA EM PLANTIO:
{self._formatar_cultura(contexto.cultura_info)}

ALERTAS ATIVOS:
{self._formatar_alertas(contexto.alertas_ativos)}

PARÂMETROS IDEAIS DA CULTURA:
{self._formatar_parametros(contexto.parametros_ideais)}

INSTRUÇÕES:
1. Analise os dados fornecidos
2. Identifique problemas ou oportunidades
3. Forneça recomendação principal com ação específica
4. Explique os riscos se não fizer a ação
5. Descreva os benefícios esperados
6. Dê próximos passos/monitoramento
7. Indique seu nível de confiança (0-100%)

Seja prático, específico e técnico. Forneça doses, dosagens, horários quando aplicável.
"""
        
        return prompt.strip()
    
    def _formatar_historico(self, historico) -> str:
        """Formata histórico de 7 dias"""
        if not historico:
            return "Sem histórico disponível"
        
        linhas = []
        for dia in historico[-7:]:  # Últimos 7 dias
            linhas.append(
                f"- {dia.criado_em.strftime('%d/%m')}: "
                f"pH {dia.ph:.1f}, Umidade {dia.umidade:.1f}%, "
                f"Temp {dia.temperatura:.1f}°C"
            )
        return "\n".join(linhas)
    
    def _formatar_clima(self, clima_semana) -> str:
        """Formata dados de clima para legibilidade"""
        if not clima_semana:
            return "Sem dados de clima"
        
        linhas = []
        for dia in clima_semana[-7:]:  # Últimos 7 dias
            linhas.append(
                f"- {dia.data.strftime('%d/%m')}: "
                f"{dia.temperatura_maxima:.0f}°C/{dia.temperatura_minima:.0f}°C, "
                f"{dia.chuva_mm:.1f}mm chuva, {dia.umidade_ar:.0f}% umidade"
            )
        return "\n".join(linhas) if linhas else "Sem dados"
    
    def _formatar_cultura(self, cultura_info) -> str:
        """Formata informações de cultura"""
        if not cultura_info:
            return "Nenhuma cultura em plantio"
        
        return f"""
- Cultura: {cultura_info.nome}
- Variedade: {cultura_info.variedade}
- Estágio Fenológico: {cultura_info.estagio_atual}
- Dias desde plantio: {cultura_info.dias_desde_plantio}
- Área: {cultura_info.area_hectares} ha
"""
    
    def _formatar_alertas(self, alertas) -> str:
        """Formata alertas ativos"""
        if not alertas:
            return "Nenhum alerta ativo"
        
        linhas = []
        for alerta in alertas:
            emoji = {"critico": "[CRITICO]", "alto": "[ALTO]", "medio": "[MEDIO]", "baixo": "[BAIXO]"}.get(
                alerta.severidade, "[DESCONHECIDO]"
            )
            linhas.append(
                f"{emoji} [{alerta.severidade.upper()}] {alerta.tipo}: {alerta.mensagem}"
            )
        return "\n".join(linhas) if linhas else "Nenhum alerta"
    
    def _formatar_parametros(self, parametros) -> str:
        """Formata parâmetros ideais da cultura"""
        if not parametros:
            return "Parâmetros não definidos"
        
        return f"""
- pH ideal: {parametros.get('ph_min', 5.5)} - {parametros.get('ph_max', 7.5)}
- Umidade ideal: {parametros.get('umidade_min', 60)} - {parametros.get('umidade_max', 80)}%
- Temperatura ideal: {parametros.get('temp_min', 15)} - {parametros.get('temp_max', 30)}°C
- N: {parametros.get('n_min', 100)} - {parametros.get('n_max', 300)} ppm
- P: {parametros.get('p_min', 30)} - {parametros.get('p_max', 100)} ppm
- K: {parametros.get('k_min', 150)} - {parametros.get('k_max', 400)} ppm
"""
    
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
            confianca=0.90,
            motivo="Análise de ChatGPT com dados atuais",
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
