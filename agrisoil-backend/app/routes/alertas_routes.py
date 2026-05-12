

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from enum import Enum
import logging

from app.db import get_db
from app.models.regra_alerta import AlertaGerado, AcaoRecomendada
from app.security import obter_usuario_atual
from app.services.motor_regras_contextualizado import MotorRegras

router = APIRouter(prefix="/api/alertas", tags=["Alertas"])
logger = logging.getLogger(__name__)


class StatusAlerta(str, Enum):
    """Status de um alerta no ciclo de vida"""
    NOVO = "novo"
    RECONHECIDO = "reconhecido"
    RESOLVIDO = "resolvido"
    CANCELADO = "cancelado"


# ============================================================================
# LISTAR ALERTAS DO USUÁRIO
# ============================================================================

@router.get("", response_model=dict)
async def listar_alertas(
    status: Optional[StatusAlerta] = None,
    zona_id: Optional[str] = None,
    sensor_id: Optional[str] = None,
    limite_dias: int = Query(7, ge=1, le=90),
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Listar todos os alertas do cliente com filtros
    
    Query params:
    - status: novo, reconhecido, resolvido, cancelado
    - zona_id: Filtrar por zona
    - sensor_id: Filtrar por sensor
    - limite_dias: Últimos N dias (padrão 7)
    """
    try:
        # TODO: Query no banco com filtros
        # SELECT * FROM alertas 
        # WHERE cliente_id = usuario.cliente_id
        # AND data_geracao >= datetime.now() - timedelta(days=limite_dias)
        # AND (status = ? OR status IS NULL)
        # AND (zona_id = ? OR zona_id IS NULL)
        # AND (sensor_id = ? OR sensor_id IS NULL)
        
        # Mock
        alertas = [
            {
                "id": "alerta_001",
                "zona_id": "zona_soja_01",
                "sensor_id": "sensor_ph_001",
                "parametro": "pH",
                "valor_leitura": 5.2,
                "ideal_minimo": 6.0,
                "ideal_maximo": 7.5,
                "status": "NOVO",
                "severidade": "ALTO",
                "acao_recomendada": "aplicar_calcario",
                "acao_descricao": "Aplicar calcário para elevar pH",
                "cultura": "soja",
                "fase_cultura": "emergencia",
                "mensagem_ia": "pH baixo na zona de plantio de soja. Recomendável aplicação de calcário para estabilizar nutrientes.",
                "data_geracao": datetime.now(),
                "data_atualizacao": datetime.now(),
                "reconhecido_por": None,
                "data_reconhecimento": None
            }
        ]
        
        return {
            "total": len(alertas),
            "usuario": usuario,
            "filtros_aplicados": {
                "status": status,
                "zona_id": zona_id,
                "sensor_id": sensor_id,
                "limite_dias": limite_dias
            },
            "alertas": alertas
        }
        
    except Exception as e:
        logger.error(f"Erro ao listar alertas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter alertas"
        )


# ============================================================================
# OBTER DETALHES DO ALERTA
# ============================================================================

@router.get("/{alerta_id}", response_model=dict)
async def obter_alerta_detalhes(
    alerta_id: str,
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Obter detalhes completos de um alerta
    
    Inclui:
    - Leitura que gerou o alerta
    - Regra aplicada
    - Histórico de status
    - Ações recomendadas
    """
    try:
        # TODO: Query no banco
        # alerta = db.query(AlertaGerado)\
        #     .filter(AlertaGerado.id == alerta_id)\
        #     .first()
        
        return {
            "id": alerta_id,
            "zona_id": "zona_soja_01",
            "sensor_id": "sensor_ph_001",
            "parametro": "pH",
            "valor_leitura": 5.2,
            "leitura_timestamp": datetime(2025, 10, 27, 14, 30),
            "ideal_minimo": 6.0,
            "ideal_maximo": 7.5,
            "alerta_minimo": 5.5,
            "critico_minimo": 5.0,
            "cultura": "soja",
            "fase_cultura": "emergencia",
            "severidade": "ALTO",
            "acao_recomendada": "aplicar_calcario",
            "acao_descricao": "Aplicar 2t/ha de calcário",
            "template_explicacao": "pH do solo baixo. Em fase de emergência, pH abaixo de 6.0 afeta germinação.",
            "mensagem_ia_contextualizada": "pH baixo em solo franco-arenoso durante emergência de soja. Recomenda-se calcário dolomítico para elevar pH a 6.5.",
            "status": "novo",
            "data_criacao": datetime.now(),
            "data_atualizacao": datetime.now(),
            "reconhecido_por": None,
            "reconhecido_em": None,
            "resolucao_executada": None,
            "evidencia_resolucao": None,
            "historico_status": [
                {
                    "status_anterior": None,
                    "status_novo": "novo",
                    "data_transicao": datetime.now(),
                    "motivo": "Alerta gerado automaticamente pelo MotorRegras"
                }
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter alerta: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter detalhes do alerta"
        )


# ============================================================================
# ATUALIZAR STATUS DO ALERTA
# ============================================================================

@router.put("/{alerta_id}/status", response_model=dict)
async def atualizar_status_alerta(
    alerta_id: str,
    novo_status: StatusAlerta,
    motivo: Optional[str] = None,
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Atualizar status do alerta
    
    Estados:
    - novo → reconhecido (Agrônomo viu e reconheceu)
    - reconhecido → resolvido (Ação executada)
    - * → cancelado (Falso positivo)
    """
    try:
        if novo_status == StatusAlerta.RESOLVIDO and not motivo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Motivo necessário para resolver alerta"
            )
        
        # TODO: Update no banco
        # alerta.status = novo_status
        # alerta.data_atualizacao = datetime.now()
        # db.commit()
        
        logger.info(f"Alerta {alerta_id} atualizado para {novo_status} por {usuario}")
        
        return {
            "alerta_id": alerta_id,
            "novo_status": novo_status,
            "atualizado_por": usuario,
            "motivo": motivo,
            "timestamp": datetime.now(),
            "mensagem": f"Alerta {novo_status} com sucesso"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar status"
        )


# ============================================================================
# ALERTAS POR ZONA
# ============================================================================

@router.get("/zona/{zona_id}", response_model=dict)
async def obter_alertas_zona(
    zona_id: str,
    status: Optional[StatusAlerta] = None,
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Obter todos os alertas de uma zona específica
    
    Útil para painel de zona no frontend
    """
    try:
        # TODO: Query filtrada por zona_id
        alertas = [
            {
                "id": "alerta_001",
                "parametro": "pH",
                "valor": 5.2,
                "status": "novo",
                "severidade": "ALTO",
                "data_geracao": datetime.now()
            },
            {
                "id": "alerta_002",
                "parametro": "Umidade do Solo",
                "valor": 45.8,
                "status": "novo",
                "severidade": "MÉDIO",
                "data_geracao": datetime.now()
            }
        ]
        
        return {
            "zona_id": zona_id,
            "total_alertas": len(alertas),
            "alertas_novo": sum(1 for a in alertas if a["status"] == "novo"),
            "alertas_reconhecido": 0,
            "alertas_resolvido": 0,
            "alertas": alertas
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter alertas da zona: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter alertas da zona"
        )


# ============================================================================
# ALERTAS POR SENSOR
# ============================================================================

@router.get("/sensor/{sensor_id}", response_model=dict)
async def obter_alertas_sensor(
    sensor_id: str,
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Obter histórico de alertas de um sensor
    
    Útil para diagnóstico de sensores problemáticos
    """
    try:
        # TODO: Query no banco
        alertas = [
            {
                "id": "alerta_sensor_001",
                "parametro": "pH",
                "valor_leitura": 5.2,
                "status": "novo",
                "severidade": "ALTO",
                "data_geracao": datetime(2025, 10, 27, 14, 30),
                "dias_pendente": 0
            }
        ]
        
        return {
            "sensor_id": sensor_id,
            "total_alertas": len(alertas),
            "alertas_pendentes": sum(1 for a in alertas if a["status"] in ["novo", "reconhecido"]),
            "alertas": alertas
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter alertas do sensor: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter alertas do sensor"
        )


# ============================================================================
# SILENCIAR ALERTA (SEM RESOLVER)
# ============================================================================

@router.post("/{alerta_id}/silenciar", response_model=dict)
async def silenciar_alerta(
    alerta_id: str,
    horas: int = Query(24, ge=1, le=168),
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Silenciar alerta temporariamente
    
    Útil quando o agrônomo sabe do problema e quer focar em outras coisas
    Após N horas, alerta volta
    """
    try:
        # TODO: Update com silenciamento
        logger.info(f"Alerta {alerta_id} silenciado por {horas} horas")
        
        return {
            "alerta_id": alerta_id,
            "silenciado": True,
            "silenciado_por_horas": horas,
            "silenciado_por": usuario,
            "data_reaparecimento": datetime.now(),
            "mensagem": "Alerta silenciado temporariamente"
        }
        
    except Exception as e:
        logger.error(f"Erro ao silenciar alerta: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao silenciar alerta"
        )


# ============================================================================
# DASHBOARD DE ALERTAS (RESUMO)
# ============================================================================

@router.get("/dashboard/resumo", response_model=dict)
async def obter_resumo_alertas(
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Resumo executivo de alertas do cliente
    
    Mostra:
    - Total por status
    - Distribuição por severidade
    - Zonas mais problemáticas
    - Padrões de alertas
    """
    try:
        return {
            "periodo": "ultimas_24h",
            "resumo_status": {
                "novo": 3,
                "reconhecido": 1,
                "resolvido": 2,
                "cancelado": 0
            },
            "resumo_severidade": {
                "critico": 1,
                "alto": 2,
                "medio": 2,
                "baixo": 1
            },
            "zonas_em_alerta": [
                {"zona_id": "zona_soja_01", "total": 3, "critico": 1},
                {"zona_id": "zona_milho_02", "total": 1, "critico": 0}
            ],
            "alertas_recorrentes": [
                "pH baixo (3 vezes)",
                "Umidade abaixo do ideal (2 vezes)"
            ],
            "recomendacao_ia": "Priorizar calibração de sensores de pH na zona soja_01. Padrão sugere sensor descalibrado."
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter resumo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter resumo de alertas"
        )
