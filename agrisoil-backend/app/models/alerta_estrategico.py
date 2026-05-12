"""
SISTEMA DE ALERTAS ESTRATÉGICOS - 10 CAMADAS
Gerenciamento avançado de alertas agronômicos com inteligência de decisão
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
from app.models.contexto_fixo import NomeCultura, FaseFenologica
from app.models.regra_alerta import AcaoRecomendada
from app.models.infraestrutura import RecomendacaoContextualizada


# ============================================================================
# 1️⃣ CAMADA DE IMPACTO
# ============================================================================

class NivelImpacto(str, Enum):
    """Classificação de impacto do alerta"""
    BAIXO = "baixo"
    MEDIO = "medio"
    ALTO = "alto"
    CRITICO = "critico"


class ConsequenciaPratica(str, Enum):
    """O que REALMENTE acontece se não agir"""
    PERDA_ESTANDE = "perda_estande"  # Plantas não nascem
    REDUCAO_VIGOR = "reducao_vigor"  # Crescimento lento
    RISCO_ABORTAMENTO = "risco_abortamento"  # Flores/grãos caem
    DESPERDICIO_INSUMO = "desperdicio_insumo"  # Adubo/agrotóxico não funciona
    ATRASO_CICLO = "atraso_ciclo"  # Cultura não avança de fase
    DOENCA = "doenca"  # Condições para patógenos
    PRAGA = "praga"  # Condições para insetos
    PERDA_QUALIDADE = "perda_qualidade"  # Grão/fruto perde valor
    PERDA_PRODUTIVIDADE = "perda_produtividade"  # Menos kg/ha
    CONTAMINACAO = "contaminacao"  # Lixiviação, contaminação


class ImpactoAlerta(BaseModel):
    """1️⃣ CAMADA DE IMPACTO - O QUE O PRODUTOR PERDE SE NÃO AGIR"""
    nivel: NivelImpacto
    consequencia: ConsequenciaPratica
    perda_estimada_kg_ha: Optional[float] = Field(
        None, 
        description="Perda estimada em kg/ha (ex: 300 kg/ha de soja)"
    )
    perda_estimada_percentual: Optional[float] = Field(
        None, 
        description="Perda estimada em % da produtividade esperada"
    )
    perda_financeira_estimada: Optional[float] = Field(
        None, 
        description="Perda em R$ (se tiver preço da saca)"
    )
    irreversivel: bool = Field(
        False, 
        description="Se True, o dano não pode ser revertido depois"
    )
    impacto_descritivo: str = Field(
        ..., 
        description="Linguagem do produtor: 'Você pode perder 20% da produção'"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "nivel": "alto",
                "consequencia": "perda_estande",
                "perda_estimada_kg_ha": 300,
                "perda_estimada_percentual": 15,
                "perda_financeira_estimada": 1500,
                "irreversivel": True,
                "impacto_descritivo": "Se não irrigar em 24h, até 20% das sementes podem não germinar. Isso não tem como recuperar depois."
            }
        }


# ============================================================================
# 2️⃣ CAMADA DE PRIORIDADE
# ============================================================================

class PrioridadeAlerta(BaseModel):
    """2️⃣ CAMADA DE PRIORIDADE - RANKING ENTRE ALERTAS"""
    score_prioridade: int = Field(
        ..., 
        ge=0, 
        le=100, 
        description="0-100, quanto maior mais prioritário"
    )
    ranking_propriedade: int = Field(
        ..., 
        description="Posição entre todos alertas da propriedade (1=mais urgente)"
    )
    fatores_calculo: dict = Field(
        ..., 
        description="Como o score foi calculado (transparência)"
    )
    comparacao: str = Field(
        ..., 
        description="'Mais urgente que alerta X' ou 'Prioridade similar a Y'"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "score_prioridade": 85,
                "ranking_propriedade": 2,
                "fatores_calculo": {
                    "impacto": 30,  # peso 30
                    "fase_critica": 25,  # peso 25
                    "area_afetada": 15,  # peso 15
                    "tempo_ate_dano": 15  # peso 15
                },
                "comparacao": "Mais urgente que o alerta de pH. Menos urgente que o de estresse hídrico na zona de milho."
            }
        }


# ============================================================================
# 3️⃣ CAMADA DE TEMPO
# ============================================================================

class JanelaAcao(BaseModel):
    """3️⃣ CAMADA DE TEMPO - JANELA DE DECISÃO"""
    janela_segura_horas: int = Field(
        ..., 
        description="Tempo disponível para agir sem prejuízo"
    )
    ponto_nao_retorno: datetime = Field(
        ..., 
        description="Depois desse momento, o dano começa a ser irreversível"
    )
    urgencia: str = Field(
        ..., 
        description="imediata, hoje, 24h, 48h, esta_semana"
    )
    tempo_restante_str: str = Field(
        ..., 
        description="'Você tem 18 horas para agir'"
    )
    pode_esperar: bool = Field(
        ..., 
        description="Se True, não há urgência real"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "janela_segura_horas": 18,
                "ponto_nao_retorno": "2026-01-28T08:00:00Z",
                "urgencia": "hoje",
                "tempo_restante_str": "Você tem até amanhã às 8h para irrigar. Depois disso, o dano será irreversível.",
                "pode_esperar": False
            }
        }


# ============================================================================
# 4️⃣ CAMADA DE LOCALIZAÇÃO
# ============================================================================

class LocalizacaoAlerta(BaseModel):
    """4️⃣ CAMADA DE LOCALIZAÇÃO - ONDE EXATAMENTE"""
    zona_manejo_id: str
    zona_manejo_nome: str
    talhao_id: str
    talhao_nome: str
    ponto_sensor: Optional[str] = Field(
        None, 
        description="Coordenadas ou descrição (ex: 'Centro da zona')"
    )
    area_afetada_ha: float = Field(
        ..., 
        description="Área estimada afetada em hectares"
    )
    percentual_zona: float = Field(
        ..., 
        description="% da zona afetada (ex: 30% da zona soja norte)"
    )
    localizacao_textual: str = Field(
        ..., 
        description="'Zona Soja Norte, próximo ao córrego, sensor #3'"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "zona_manejo_id": "zona_001",
                "zona_manejo_nome": "Zona Soja Norte",
                "talhao_id": "talhao_001",
                "talhao_nome": "Talhão Santa Clara 1",
                "ponto_sensor": "Centro da zona, 50m da estrada",
                "area_afetada_ha": 12.5,
                "percentual_zona": 35,
                "localizacao_textual": "Zona Soja Norte (12,5 ha afetados - 35% da zona)"
            }
        }


# ============================================================================
# 5️⃣ CAMADA DE AÇÃO RECOMENDADA
# ============================================================================

class AcaoDetalhada(BaseModel):
    """5️⃣ CAMADA DE AÇÃO - O QUE FAZER E O QUE NÃO FAZER (CONTEXTUALIZADO)"""
    acao_principal: AcaoRecomendada
    
    # CONTEXTUALIZAÇÃO POR INFRAESTRUTURA
    recomendacao_contextualizada: Optional[RecomendacaoContextualizada] = Field(
        None,
        description="Recomendação adaptada ao que o produtor POSSUI"
    )
    
    # Campos originais (ainda usados quando não há contextualização)
    o_que_fazer: str = Field(
        ..., 
        description="Passo a passo claro"
    )
    o_que_nao_fazer: str = Field(
        ..., 
        description="O que NÃO fazer (erros comuns)"
    )
    pode_esperar: bool
    se_esperar_acontece: Optional[str] = Field(
        None, 
        description="O que acontece se não agir agora"
    )
    quantidade_estimada: Optional[str] = Field(
        None, 
        description="'Aplicar 2t/ha de calcário' ou 'Irrigar 30mm'"
    )
    custo_estimado: Optional[float] = Field(
        None, 
        description="Custo estimado da ação em R$"
    )
    acoes_alternativas: Optional[List[str]] = Field(
        None, 
        description="Outras opções se não puder fazer a principal"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "acao_principal": "irrigar",
                "o_que_fazer": "1. Ligar pivô central ou aplicar 30mm via aspersão\n2. Irrigar no final da tarde/noite\n3. Monitorar umidade nas próximas 48h",
                "o_que_nao_fazer": "• NÃO irrigar no calor do dia (desperdício)\n• NÃO aplicar mais de 35mm de uma vez (lixiviação)\n• NÃO esperar mais de 24h",
                "pode_esperar": False,
                "se_esperar_acontece": "Se não irrigar em 24h, 15-20% das sementes não vão germinar.",
                "quantidade_estimada": "30mm de água (12,5 ha = 3.750m³)",
                "custo_estimado": 450.00,
                "acoes_alternativas": [
                    "Se não tiver irrigação, aguardar previsão de chuva",
                    "Cobrir solo com palha (reduz evaporação)"
                ]
            }
        }


# ============================================================================
# 6️⃣ CAMADA DE CONFIRMAÇÃO
# ============================================================================

class ConfirmacaoExecucao(BaseModel):
    """6️⃣ CAMADA DE CONFIRMAÇÃO - FECHAMENTO DO CICLO"""
    alerta_id: str
    produtor_executou: bool
    data_execucao: Optional[datetime] = None
    acao_tomada: Optional[str] = Field(
        None, 
        description="O que o produtor fez (pode ser diferente do recomendado)"
    )
    quantidade_aplicada: Optional[str] = None
    custo_real: Optional[float] = None
    observacoes: Optional[str] = None
    razao_nao_execucao: Optional[str] = Field(
        None, 
        description="Se não executou, por quê? (sem irrigação, choveu, etc)"
    )
    resultado_percebido: Optional[str] = Field(
        None, 
        description="O produtor viu melhora? Em quanto tempo?"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "alerta_id": "alerta_001",
                "produtor_executou": True,
                "data_execucao": "2026-01-27T18:30:00Z",
                "acao_tomada": "Irrigação por pivô central",
                "quantidade_aplicada": "32mm",
                "custo_real": 475.00,
                "observacoes": "Irrigou no final da tarde conforme recomendado",
                "razao_nao_execucao": None,
                "resultado_percebido": "Umidade normalizou em 12h. Germinação melhorou."
            }
        }


# ============================================================================
# 7️⃣ CAMADA DE APRENDIZADO
# ============================================================================

class AprendizadoPropriedade(BaseModel):
    """7️⃣ CAMADA DE APRENDIZADO - INTELIGÊNCIA PROPRIETÁRIA"""
    zona_id: str
    parametro: str
    
    # PADRÕES DETECTADOS
    padrao_recorrente: bool
    descricao_padrao: Optional[str] = Field(
        None, 
        description="'Essa zona sempre entra em estresse 2 dias antes da chuva'"
    )
    ocorrencias_similares: int = Field(
        0, 
        description="Quantas vezes esse padrão aconteceu"
    )
    
    # AJUSTES APRENDIDOS
    limite_ajustado: bool = Field(
        False, 
        description="Se True, o limite foi ajustado para essa zona específica"
    )
    limite_original: Optional[float] = None
    limite_atual: Optional[float] = None
    razao_ajuste: Optional[str] = None
    
    # HISTÓRICO
    ultima_ocorrencia: Optional[datetime] = None
    media_tempo_resolucao_horas: Optional[float] = Field(
        None, 
        description="Quanto tempo o produtor leva para resolver (média)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "zona_id": "zona_001",
                "parametro": "umidade",
                "padrao_recorrente": True,
                "descricao_padrao": "Esta zona entra em estresse hídrico sempre 2-3 dias antes da chuva. Solo arenoso drena rápido.",
                "ocorrencias_similares": 8,
                "limite_ajustado": True,
                "limite_original": 22.0,
                "limite_atual": 24.0,
                "razao_ajuste": "Solo arenoso precisa limite mais alto (drena mais rápido)",
                "ultima_ocorrencia": "2026-01-15T10:00:00Z",
                "media_tempo_resolucao_horas": 18.5
            }
        }


# ============================================================================
# 8️⃣ CAMADA DE EXCEÇÃO
# ============================================================================

class ExcecaoAlerta(BaseModel):
    """8️⃣ CAMADA DE EXCEÇÃO - SITUAÇÕES ATÍPICAS"""
    alerta_id: str
    situacao_atipica: bool
    descricao_atipico: Optional[str] = Field(
        None, 
        description="O que torna essa situação diferente do normal"
    )
    requer_intervencao_agronomica: bool
    override_aplicado: bool = Field(
        False, 
        description="Se True, agrônomo substituiu a regra"
    )
    regra_original: Optional[str] = None
    decisao_agronomica: Optional[str] = None
    justificativa: Optional[str] = None
    validado_por: Optional[str] = Field(
        None, 
        description="Engenheiro agrônomo responsável"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "alerta_id": "alerta_002",
                "situacao_atipica": True,
                "descricao_atipico": "Umidade baixa mas chuva prevista em 6 horas. Sensor pode estar descalibrado (leitura muito abaixo do esperado).",
                "requer_intervencao_agronomica": True,
                "override_aplicado": True,
                "regra_original": "Irrigar imediatamente",
                "decisao_agronomica": "Aguardar chuva e recalibrar sensor",
                "justificativa": "Previsão 90% chuva 40mm. Não vale custo de irrigação. Sensor suspeito (última calibração há 4 meses).",
                "validado_por": "Eng. Agr. Maria Santos CREA-SP 12345"
            }
        }


# ============================================================================
# 9️⃣ CAMADA DE AUDITORIA
# ============================================================================

class AuditoriaCompleta(BaseModel):
    """9️⃣ CAMADA DE AUDITORIA - RASTREABILIDADE TOTAL"""
    alerta_id: str
    
    # DADO RECEBIDO
    dado_sensor: dict = Field(
        ..., 
        description="Snapshot do dado que gerou o alerta"
    )
    timestamp_leitura: datetime
    
    # REGRA APLICADA
    regra_id: str
    regra_versao: str = Field(
        ..., 
        description="Versão da regra (caso tenha sido alterada depois)"
    )
    contexto_aplicacao: dict = Field(
        ..., 
        description="Cultura, fase, zona, solo (contexto completo)"
    )
    
    # ALERTA GERADO
    alerta_gerado: dict
    timestamp_geracao: datetime
    
    # DECISÃO TOMADA
    decisao: Optional[str] = None
    executado: bool = False
    timestamp_execucao: Optional[datetime] = None
    
    # RESULTADO OBSERVADO
    resultado: Optional[str] = None
    efetivo: Optional[bool] = Field(
        None, 
        description="A ação resolveu o problema?"
    )
    timestamp_resolucao: Optional[datetime] = None
    
    # MÉTRICAS
    tempo_ate_reconhecimento_horas: Optional[float] = None
    tempo_ate_execucao_horas: Optional[float] = None
    tempo_ate_resolucao_horas: Optional[float] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "alerta_id": "alerta_001",
                "dado_sensor": {
                    "sensor_id": "sensor_ph_001",
                    "parametro": "pH",
                    "valor": 5.2,
                    "unidade": "pH"
                },
                "timestamp_leitura": "2026-01-27T10:00:00Z",
                "regra_id": "regra_soja_emergencia_ph",
                "regra_versao": "v2.3",
                "contexto_aplicacao": {
                    "cultura": "soja",
                    "fase": "emergencia",
                    "zona": "zona_001",
                    "solo": "franco"
                },
                "alerta_gerado": {"titulo": "pH baixo", "severidade": "alto"},
                "timestamp_geracao": "2026-01-27T10:05:00Z",
                "decisao": "Aplicar calcário",
                "executado": True,
                "timestamp_execucao": "2026-01-28T08:00:00Z",
                "resultado": "pH subiu para 6.3 em 5 dias",
                "efetivo": True,
                "timestamp_resolucao": "2026-02-02T10:00:00Z",
                "tempo_ate_reconhecimento_horas": 2.5,
                "tempo_ate_execucao_horas": 22.0,
                "tempo_ate_resolucao_horas": 144.0
            }
        }


# ============================================================================
# 🔟 CAMADA DE COMUNICAÇÃO
# ============================================================================

class ComunicacaoAlerta(BaseModel):
    """🔟 CAMADA DE COMUNICAÇÃO - COMO O ALERTA CHEGA"""
    alerta_id: str
    
    # LINGUAGEM ADAPTADA
    linguagem_produtor: str = Field(
        ..., 
        description="Mensagem em linguagem simples, sem jargão"
    )
    linguagem_tecnica: Optional[str] = Field(
        None, 
        description="Versão técnica (para agrônomo)"
    )
    
    # TOM
    tom: str = Field(
        ..., 
        description="urgente, importante, informativo, preventivo"
    )
    emoji_sugerido: Optional[str] = Field(
        None, 
        description="🚨 (crítico), ⚠️ (alto), ℹ️ (médio)"
    )
    
    # CONSISTÊNCIA
    tipo_mensagem: str = Field(
        ..., 
        description="alerta, reforço, confirmacao, atualizacao"
    )
    enviado_em: datetime
    canais_envio: List[str] = Field(
        ..., 
        description="['app', 'sms', 'email', 'whatsapp']"
    )
    
    # REFORÇO
    requer_reforco: bool = Field(
        False, 
        description="Se ignorado, reforçar?"
    )
    reforco_enviado: bool = False
    timestamp_reforco: Optional[datetime] = None
    
    # LEITURA
    visualizado: bool = False
    timestamp_visualizacao: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "alerta_id": "alerta_001",
                "linguagem_produtor": "🚨 URGENTE: Sua zona de soja está muito seca!\n\nSe não irrigar em 24h, você pode perder até 20% da produção.\n\nO que fazer: Irrigar 30mm hoje à tarde.",
                "linguagem_tecnica": "Umidade do solo em 18% (crítico < 20%). Fase: emergência. Risco: falha de estande. Ação: irrigação 30mm.",
                "tom": "urgente",
                "emoji_sugerido": "🚨",
                "tipo_mensagem": "alerta",
                "enviado_em": "2026-01-27T10:05:00Z",
                "canais_envio": ["app", "sms"],
                "requer_reforco": True,
                "reforco_enviado": False,
                "timestamp_reforco": None,
                "visualizado": True,
                "timestamp_visualizacao": "2026-01-27T10:15:00Z"
            }
        }


# ============================================================================
# ALERTA ESTRATÉGICO (TODAS AS 10 CAMADAS)
# ============================================================================

class AlertaEstrategico(BaseModel):
    """
    ALERTA ESTRATÉGICO COM TODAS AS 10 CAMADAS
    
    Este é o modelo definitivo que o sistema deve usar.
    """
    # IDENTIFICAÇÃO
    id: str
    criado_em: datetime
    atualizado_em: datetime
    
    # BÁSICO (já existia)
    regra_id: str
    sensor_id: str
    parametro: str
    valor_medido: float
    unidade: str
    cultura: NomeCultura
    fase: FaseFenologica
    
    # STATUS
    status: str = Field(
        "novo", 
        description="novo, reconhecido, em_execucao, resolvido, cancelado"
    )
    
    # ✨ AS 10 CAMADAS ✨
    camada_1_impacto: ImpactoAlerta
    camada_2_prioridade: PrioridadeAlerta
    camada_3_tempo: JanelaAcao
    camada_4_localizacao: LocalizacaoAlerta
    camada_5_acao: AcaoDetalhada
    camada_6_confirmacao: Optional[ConfirmacaoExecucao] = None
    camada_7_aprendizado: Optional[AprendizadoPropriedade] = None
    camada_8_excecao: Optional[ExcecaoAlerta] = None
    camada_9_auditoria: AuditoriaCompleta
    camada_10_comunicacao: ComunicacaoAlerta
    
    class Config:
        from_attributes = True
