

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from enum import Enum
import logging

from app.db import get_db
from app.security import obter_usuario_atual
from app.models.alerta_estrategico import (
    AlertaEstrategico,
    ImpactoAlerta, NivelImpacto, ConsequenciaPratica,
    PrioridadeAlerta,
    JanelaAcao,
    LocalizacaoAlerta,
    AcaoDetalhada,
    ConfirmacaoExecucao,
    AprendizadoPropriedade,
    ExcecaoAlerta,
    AuditoriaCompleta,
    ComunicacaoAlerta
)
from app.models.regra_alerta import AcaoRecomendada

router = APIRouter(prefix="/api/alertas-v2", tags=["Alertas Estratégicos - 10 Camadas"])
logger = logging.getLogger(__name__)


class StatusAlerta(str, Enum):
    """Status do alerta no ciclo de vida"""
    NOVO = "novo"
    RECONHECIDO = "reconhecido"
    EM_EXECUCAO = "em_execucao"
    RESOLVIDO = "resolvido"
    CANCELADO = "cancelado"


# ============================================================================
# LISTAR ALERTAS ESTRATÉGICOS
# ============================================================================

@router.get("/completo", response_model=dict)
async def listar_alertas_estrategicos(
    status: Optional[StatusAlerta] = None,
    nivel_impacto: Optional[NivelImpacto] = None,
    zona_id: Optional[str] = None,
    urgencia: Optional[str] = None,
    score_prioridade_min: Optional[int] = Query(None, ge=0, le=100),
    limite_dias: int = Query(7, ge=1, le=90),
    ordenar_por: str = Query("prioridade", description="prioridade, tempo, impacto, localizacao"),
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Listar alertas ESTRATÉGICOS
    
    Filtros:
    - status: novo, reconhecido, em_execucao, resolvido, cancelado
    - nivel_impacto: baixo, medio, alto, critico
    - zona_id: Filtrar por zona específica
    - urgencia: imediata, hoje, 24h, 48h, esta_semana
    - score_prioridade_min: Alertas com score >= X (0-100)
    - ordenar_por: prioridade (padrão), tempo, impacto, localizacao
    """
    try:
        # TODO: Query complexa no banco
        # alertas = db.query(AlertaEstrategico)\
        #     .filter(filtros...)\
        #     .order_by(ordenacao...)\
        #     .all()
        
        # Mock com TODAS as 10 camadas
        alertas_mock = [
            {
                "id": "alerta_001",
                "criado_em": datetime.now() - timedelta(hours=2),
                "atualizado_em": datetime.now(),
                "regra_id": "regra_soja_emerg_umidade",
                "sensor_id": "sensor_001",
                "parametro": "Umidade do Solo",
                "valor_medido": 18.5,
                "unidade": "%",
                "cultura": "soja",
                "fase": "emergencia",
                "status": "novo",
                
                # 1️ IMPACTO
                "camada_1_impacto": {
                    "nivel": "alto",
                    "consequencia": "perda_estande",
                    "perda_estimada_kg_ha": 300,
                    "perda_estimada_percentual": 18,
                    "perda_financeira_estimada": 1800,
                    "irreversivel": True,
                    "impacto_descritivo": "Se não irrigar em 24h, até 20% das sementes podem não germinar. Isso NÃO tem como recuperar depois."
                },
                
                # 2️ PRIORIDADE
                "camada_2_prioridade": {
                    "score_prioridade": 85,
                    "ranking_propriedade": 1,
                    "fatores_calculo": {
                        "impacto": 30,
                        "fase_critica": 25,
                        "area_afetada": 15,
                        "tempo_ate_dano": 15
                    },
                    "comparacao": "MAIS URGENTE que todos os outros alertas da propriedade"
                },
                
                # 3️ TEMPO
                "camada_3_tempo": {
                    "janela_segura_horas": 18,
                    "ponto_nao_retorno": (datetime.now() + timedelta(hours=18)).isoformat(),
                    "urgencia": "hoje",
                    "tempo_restante_str": "Você tem 18 horas para agir. Depois disso, o dano será IRREVERSÍVEL.",
                    "pode_esperar": False
                },
                
                # 4️ LOCALIZAÇÃO
                "camada_4_localizacao": {
                    "zona_manejo_id": "zona_001",
                    "zona_manejo_nome": "Zona Soja Norte",
                    "talhao_id": "talhao_001",
                    "talhao_nome": "Talhão Santa Clara 1",
                    "ponto_sensor": "Centro da zona, 50m da estrada principal",
                    "area_afetada_ha": 12.5,
                    "percentual_zona": 35,
                    "localizacao_textual": "Zona Soja Norte (12,5 ha afetados - 35% da zona)"
                },
                
                # 5️ AÇÃO
                "camada_5_acao": {
                    "acao_principal": "irrigar",
                    "o_que_fazer": "1. Ligar pivô central ou aplicar 30mm via aspersão\n2. Irrigar no final da tarde (16-20h)\n3. Monitorar umidade nas próximas 48h",
                    "o_que_nao_fazer": "• NÃO irrigar no calor do dia (perde 40% por evaporação)\n• NÃO aplicar mais de 35mm de uma vez (lixiviação de nutrientes)\n• NÃO esperar mais de 24h",
                    "pode_esperar": False,
                    "se_esperar_acontece": "Sementes vão desidratar e não germinar. Perda de 15-20% da produção.",
                    "quantidade_estimada": "30mm (12,5 ha = 3.750m³)",
                    "custo_estimado": 450.00,
                    "acoes_alternativas": [
                        "Se não tiver irrigação: cobrir solo com palha",
                        "Aguardar previsão de chuva (se > 80%)"
                    ]
                },
                
                # 6️ CONFIRMAÇÃO (null = ainda não executado)
                "camada_6_confirmacao": None,
                
                # 7️ APRENDIZADO
                "camada_7_aprendizado": {
                    "zona_id": "zona_001",
                    "parametro": "umidade",
                    "padrao_recorrente": True,
                    "descricao_padrao": "Esta zona entra em estresse hídrico sempre 2-3 dias antes da chuva. Solo arenoso drena muito rápido.",
                    "ocorrencias_similares": 8,
                    "limite_ajustado": True,
                    "limite_original": 22.0,
                    "limite_atual": 24.0,
                    "razao_ajuste": "Solo arenoso precisa limite mais alto",
                    "ultima_ocorrencia": (datetime.now() - timedelta(days=12)).isoformat(),
                    "media_tempo_resolucao_horas": 18.5
                },
                
                # 8️ EXCEÇÃO (null = situação normal)
                "camada_8_excecao": None,
                
                # 9️ AUDITORIA
                "camada_9_auditoria": {
                    "alerta_id": "alerta_001",
                    "dado_sensor": {
                        "sensor_id": "sensor_001",
                        "parametro": "Umidade",
                        "valor": 18.5,
                        "unidade": "%"
                    },
                    "timestamp_leitura": (datetime.now() - timedelta(hours=2)).isoformat(),
                    "regra_id": "regra_soja_emerg_umidade",
                    "regra_versao": "v3.1",
                    "contexto_aplicacao": {
                        "cultura": "soja",
                        "fase": "emergencia",
                        "zona": "zona_001",
                        "solo": "arenoso"
                    },
                    "alerta_gerado": {"titulo": "Umidade crítica", "severidade": "alto"},
                    "timestamp_geracao": (datetime.now() - timedelta(hours=2, minutes=5)).isoformat(),
                    "decisao": None,
                    "executado": False,
                    "timestamp_execucao": None,
                    "resultado": None,
                    "efetivo": None,
                    "timestamp_resolucao": None,
                    "tempo_ate_reconhecimento_horas": None,
                    "tempo_ate_execucao_horas": None,
                    "tempo_ate_resolucao_horas": None
                },
                
                # 10️ COMUNICAÇÃO
                "camada_10_comunicacao": {
                    "alerta_id": "alerta_001",
                    "linguagem_produtor": "🚨 URGENTE: Zona Soja Norte está MUITO SECA!\n\nSe não irrigar em 18h, você vai perder até 20% da produção.\n\n✅ O que fazer:\n• Irrigar 30mm HOJE à tarde\n• Custo: R$ 450\n\n❌ NÃO faça:\n• Irrigar no calor (perde 40%)\n• Esperar até amanhã",
                    "linguagem_tecnica": "Umidade 18,5% (crítico < 20%). Emergência soja. Risco: perda estande 15-20%. Irrigar 30mm urgente.",
                    "tom": "urgente",
                    "emoji_sugerido": "🚨",
                    "tipo_mensagem": "alerta",
                    "enviado_em": (datetime.now() - timedelta(hours=2, minutes=5)).isoformat(),
                    "canais_envio": ["app"],
                    "requer_reforco": True,
                    "reforco_enviado": False,
                    "timestamp_reforco": None,
                    "visualizado": True,
                    "timestamp_visualizacao": (datetime.now() - timedelta(hours=1, minutes=45)).isoformat()
                }
            }
        ]
        
        return {
            "total": len(alertas_mock),
            "filtros": {
                "status": status,
                "nivel_impacto": nivel_impacto,
                "zona_id": zona_id,
                "urgencia": urgencia,
                "score_prioridade_min": score_prioridade_min
            },
            "alertas": alertas_mock,
            "metadados": {
                "critico": 1,
                "alto": 0,
                "medio": 0,
                "baixo": 0,
                "requer_acao_imediata": 1
            }
        }
        
    except Exception as e:
        logger.error(f"Erro ao listar alertas estratégicos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter alertas"
        )


# ============================================================================
# CONFIRMAR EXECUÇÃO (CAMADA 6)
# ============================================================================

@router.post("/{alerta_id}/confirmar-execucao", response_model=dict)
async def confirmar_execucao(
    alerta_id: str,
    confirmacao: ConfirmacaoExecucao,
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    6️ CAMADA DE CONFIRMAÇÃO - Produtor confirma que executou a ação
    
    Isso FECHA O CICLO: alerta → ação → resultado
    """
    try:
        # TODO: Salvar confirmação no banco
        # alerta = db.query(AlertaEstrategico).filter(id == alerta_id).first()
        # alerta.camada_6_confirmacao = confirmacao
        # alerta.status = "em_execucao" if confirmacao.produtor_executou else "cancelado"
        # db.commit()
        
        logger.info(f"Execução confirmada: {alerta_id} por {usuario}")
        
        return {
            "alerta_id": alerta_id,
            "confirmado": True,
            "executado": confirmacao.produtor_executou,
            "data_execucao": confirmacao.data_execucao,
            "acao_tomada": confirmacao.acao_tomada,
            "mensagem": "Obrigado por confirmar! Vamos monitorar o resultado."
        }
        
    except Exception as e:
        logger.error(f"Erro ao confirmar execução: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao confirmar execução"
        )


# ============================================================================
# REGISTRAR EXCEÇÃO (CAMADA 8)
# ============================================================================

@router.post("/{alerta_id}/registrar-excecao", response_model=dict)
async def registrar_excecao(
    alerta_id: str,
    excecao: ExcecaoAlerta,
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    8️ CAMADA DE EXCEÇÃO - Situação atípica precisa override agrônomo
    
    Exemplo: Sensor descalibrado, chuva prevista, condição rara
    """
    try:
        # TODO: Salvar exceção
        logger.info(f"Exceção registrada: {alerta_id}")
        
        return {
            "alerta_id": alerta_id,
            "excecao_registrada": True,
            "requer_validacao": excecao.requer_intervencao_agronomica,
            "mensagem": "Exceção registrada. Aguardando validação do agrônomo." if excecao.requer_intervencao_agronomica else "Exceção aplicada."
        }
        
    except Exception as e:
        logger.error(f"Erro ao registrar exceção: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao registrar exceção"
        )


# ============================================================================
# PADRÕES APRENDIDOS (CAMADA 7)
# ============================================================================

@router.get("/aprendizado/{zona_id}", response_model=dict)
async def obter_padroes_aprendidos(
    zona_id: str,
    parametro: Optional[str] = None,
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    7️ CAMADA DE APRENDIZADO - Ver padrões detectados em uma zona
    
    Mostra:
    - Padrões recorrentes
    - Limites ajustados
    - Tempo médio de resolução
    - Recomendações específicas
    """
    try:
        # TODO: Query aprendizados
        
        return {
            "zona_id": zona_id,
            "padroes_detectados": [
                {
                    "parametro": "umidade",
                    "padrao": "Estresse hídrico sempre 2-3 dias antes da chuva",
                    "ocorrencias": 8,
                    "ajuste_aplicado": "Limite aumentado de 22% para 24%",
                    "efetividade": "Reduziu falsos positivos em 40%"
                }
            ],
            "recomendacao_inteligente": "Essa zona precisa atenção especial 3 dias antes de previsão de chuva. Solo arenoso drena rápido.",
            "producao_historica": {
                "melhor_safra": "2024/2025: 3.800 kg/ha",
                "media": "3.450 kg/ha",
                "correlacao_alertas": "Safras com < 3 alertas críticos tiveram 12% mais produtividade"
            }
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter aprendizado: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter aprendizado"
        )


# ============================================================================
# DASHBOARD EXECUTIVO (VISÃO GERAL)
# ============================================================================

@router.get("/dashboard/executivo", response_model=dict)
async def dashboard_executivo(
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Dashboard executivo com visão das 10 camadas
    
    Mostra:
    - Alertas por nível de impacto
    - Ranking de prioridade
    - Janelas de ação vencendo
    - Taxa de execução
    - Padrões aprendidos
    """
    try:
        return {
            "periodo": "ultimas_24h",
            
            # 1️ IMPACTO
            "impacto": {
                "critico": 1,
                "alto": 3,
                "medio": 5,
                "baixo": 2,
                "perda_financeira_total_estimada": 12500
            },
            
            # 2️ PRIORIDADE
            "top_5_prioritarios": [
                {"id": "alerta_001", "score": 85, "zona": "Soja Norte", "acao": "Irrigar"},
                {"id": "alerta_002", "score": 78, "zona": "Milho Sul", "acao": "Adubar"},
            ],
            
            # 3️ TEMPO
            "janelas_acao": {
                "vencendo_hoje": 2,
                "vencendo_24h": 1,
                "vencendo_48h": 3,
                "ja_vencidas": 0
            },
            
            # 4️ LOCALIZAÇÃO
            "zonas_em_alerta": {
                "total": 8,
                "criticas": 2,
                "area_total_afetada_ha": 87.5
            },
            
            # 5️ AÇÕES
            "acoes_pendentes": {
                "irrigar": 2,
                "adubar": 1,
                "aplicar_calcario": 1,
                "inspecionar_sensor": 1
            },
            
            # 6️ CONFIRMAÇÕES
            "taxa_execucao": {
                "executados": 15,
                "nao_executados": 3,
                "percentual": 83.3,
                "tempo_medio_execucao_horas": 14.5
            },
            
            # 7️ APRENDIZADO
            "inteligencia": {
                "padroes_novos_detectados": 2,
                "limites_ajustados": 3,
                "predicoes_corretas": "92%"
            },
            
            # 8️ EXCEÇÕES
            "excecoes": {
                "situacoes_atipicas": 1,
                "overrides_agronomicos": 0
            },
            
            # 9️ AUDITORIA
            "metricas": {
                "alertas_gerados_24h": 11,
                "tempo_medio_reconhecimento_min": 45,
                "tempo_medio_resolucao_horas": 18.5
            },
            
            #  COMUNICAÇÃO
            "comunicacao": {
                "enviados": 11,
                "visualizados": 9,
                "taxa_visualizacao": "81.8%",
                "reforcos_necessarios": 2
            },
            
            "resumo_ia": "Priorize os 2 alertas críticos de hoje. Taxa de execução excelente (83%). Zona Soja Norte precisa atenção especial."
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter dashboard"
        )


# ============================================================================
# AUDITORIA COMPLETA (CAMADA 9)
# ============================================================================

@router.get("/{alerta_id}/auditoria", response_model=AuditoriaCompleta)
async def obter_auditoria_completa(
    alerta_id: str,
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    9️ CAMADA DE AUDITORIA - Rastreabilidade total
    
    Mostra:
    - Dado sensor → Regra aplicada → Alerta gerado
    - Decisão → Execução → Resultado
    - Métricas de tempo
    
    Essencial para:
    - Provar valor do sistema
    - Cases de sucesso
    - Defesa técnica
    """
    try:
        # TODO: Query auditoria
        
        return AuditoriaCompleta(
            alerta_id=alerta_id,
            dado_sensor={"valor": 18.5, "parametro": "umidade"},
            timestamp_leitura=datetime.now() - timedelta(days=5),
            regra_id="regra_001",
            regra_versao="v3.1",
            contexto_aplicacao={"cultura": "soja", "fase": "emergencia"},
            alerta_gerado={"severidade": "alto"},
            timestamp_geracao=datetime.now() - timedelta(days=5),
            decisao="Irrigar 30mm",
            executado=True,
            timestamp_execucao=datetime.now() - timedelta(days=4, hours=18),
            resultado="Umidade normalizou em 24h. Germinação ótima.",
            efetivo=True,
            timestamp_resolucao=datetime.now() - timedelta(days=3),
            tempo_ate_reconhecimento_horas=2.5,
            tempo_ate_execucao_horas=6.0,
            tempo_ate_resolucao_horas=48.0
        )
        
    except Exception as e:
        logger.error(f"Erro ao obter auditoria: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter auditoria"
        )
