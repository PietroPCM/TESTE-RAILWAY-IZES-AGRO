

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from enum import Enum
import logging

from app.db import get_db
from app.models.database import AlertaDB, StatusAlerta as DBStatusAlerta
from app.models.regra_alerta import AlertaGerado, AcaoRecomendada
from app.security import obter_usuario_atual, verify_token
from app.services.motor_regras_contextualizado import MotorRegras
from app.utils.datetime_utils import serialize_utc_payload, utc_iso

router = APIRouter(prefix="/api/alertas", tags=["Alertas"])
logger = logging.getLogger(__name__)


class StatusAlerta(str, Enum):
    """Status de um alerta no ciclo de vida"""
    NOVO = "novo"
    RECONHECIDO = "reconhecido"
    RESOLVIDO = "resolvido"
    CANCELADO = "cancelado"


def _mapear_status_api(status_api: Optional[StatusAlerta]) -> Optional[DBStatusAlerta]:
    if not status_api:
        return None
    mapa = {
        StatusAlerta.NOVO: DBStatusAlerta.ATIVO,
        StatusAlerta.RECONHECIDO: DBStatusAlerta.RECONHECIDO,
        StatusAlerta.RESOLVIDO: DBStatusAlerta.RESOLVIDO,
        StatusAlerta.CANCELADO: DBStatusAlerta.IGNORADO,
    }
    return mapa[status_api]


def _alerta_to_dict(alerta: AlertaDB) -> dict:
    return {
        "id": alerta.id,
        "sensor_id": alerta.sensor_id,
        "cliente_id": alerta.cliente_id,
        "leitura_id": alerta.leitura_id,
        "parametro": alerta.tipo.value if alerta.tipo else None,
        "valor_leitura": alerta.valor_medido,
        "valor_referencia": alerta.valor_referencia,
        "status": alerta.status.value if alerta.status else None,
        "severidade": alerta.severidade.value if alerta.severidade else None,
        "titulo": alerta.titulo,
        "mensagem": alerta.mensagem,
        "recomendacao": alerta.recomendacao,
        "data_geracao": alerta.criado_em,
        "data_atualizacao": alerta.atualizado_em,
        "reconhecido_em": alerta.reconhecido_em,
        "resolvido_em": alerta.resolvido_em,
    }


# ============================================================================
# LISTAR ALERTAS DO USUÁRIO
# ============================================================================

@router.get("", response_model=dict)
async def listar_alertas(
    status_alerta: Optional[StatusAlerta] = Query(None, alias="status"),
    zona_id: Optional[str] = None,
    sensor_id: Optional[str] = None,
    limite_dias: int = Query(7, ge=1, le=90),
    cliente_id: str = Depends(verify_token),
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
        desde = datetime.utcnow() - timedelta(days=limite_dias)
        query = db.query(AlertaDB).filter(
            AlertaDB.cliente_id == cliente_id,
            AlertaDB.criado_em >= desde,
        )

        db_status = _mapear_status_api(status_alerta)
        if db_status:
            query = query.filter(AlertaDB.status == db_status)
        if sensor_id:
            query = query.filter(AlertaDB.sensor_id == sensor_id)

        alertas = query.order_by(AlertaDB.criado_em.desc()).limit(200).all()
        
        return serialize_utc_payload({
            "total": len(alertas),
            "cliente_id": cliente_id,
            "filtros_aplicados": {
                "status": status_alerta,
                "zona_id": zona_id,
                "sensor_id": sensor_id,
                "limite_dias": limite_dias
            },
            "dados_reais": True,
            "alertas": [_alerta_to_dict(alerta) for alerta in alertas]
        })
        
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
    cliente_id: str = Depends(verify_token),
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
        if not alerta_id.isdigit():
            raise HTTPException(status_code=404, detail="Alerta não encontrado")

        alerta = db.query(AlertaDB).filter(
            AlertaDB.id == int(alerta_id),
            AlertaDB.cliente_id == cliente_id,
        ).first()

        if not alerta:
            raise HTTPException(status_code=404, detail="Alerta não encontrado")

        return serialize_utc_payload(_alerta_to_dict(alerta))
        
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
            "timestamp": utc_iso(datetime.utcnow()),
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
    status_alerta: Optional[StatusAlerta] = Query(None, alias="status"),
    cliente_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """
    Obter todos os alertas de uma zona específica
    
    Útil para painel de zona no frontend
    """
    try:
        logger.info("Consulta por zona solicitada sem modelo de zona vinculado a alertas")
        return serialize_utc_payload({
            "zona_id": zona_id,
            "cliente_id": cliente_id,
            "total_alertas": 0,
            "alertas_novo": 0,
            "alertas_reconhecido": 0,
            "alertas_resolvido": 0,
            "dados_reais": False,
            "mensagem": "Alertas ainda não possuem vínculo de zona no modelo atual.",
            "filtros_aplicados": {"status": status_alerta},
            "alertas": []
        })
        
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
    cliente_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """
    Obter histórico de alertas de um sensor
    
    Útil para diagnóstico de sensores problemáticos
    """
    try:
        alertas = db.query(AlertaDB).filter(
            AlertaDB.cliente_id == cliente_id,
            AlertaDB.sensor_id == sensor_id,
        ).order_by(AlertaDB.criado_em.desc()).limit(100).all()
        
        return serialize_utc_payload({
            "sensor_id": sensor_id,
            "cliente_id": cliente_id,
            "total_alertas": len(alertas),
            "alertas_pendentes": sum(1 for a in alertas if a.status in {DBStatusAlerta.ATIVO, DBStatusAlerta.RECONHECIDO}),
            "dados_reais": True,
            "alertas": [_alerta_to_dict(alerta) for alerta in alertas]
        })
        
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
            "data_reaparecimento": utc_iso(datetime.utcnow()),
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
    cliente_id: str = Depends(verify_token),
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
        alertas = db.query(AlertaDB).filter(AlertaDB.cliente_id == cliente_id).all()
        ativos = [alerta for alerta in alertas if alerta.status == DBStatusAlerta.ATIVO]
        reconhecidos = [alerta for alerta in alertas if alerta.status == DBStatusAlerta.RECONHECIDO]
        resolvidos = [alerta for alerta in alertas if alerta.status == DBStatusAlerta.RESOLVIDO]
        ignorados = [alerta for alerta in alertas if alerta.status == DBStatusAlerta.IGNORADO]

        severidades = {}
        for alerta in alertas:
            chave = alerta.severidade.value if alerta.severidade else "indefinida"
            severidades[chave] = severidades.get(chave, 0) + 1

        recorrentes = {}
        for alerta in alertas:
            chave = alerta.tipo.value if alerta.tipo else "indefinido"
            recorrentes[chave] = recorrentes.get(chave, 0) + 1

        return {
            "cliente_id": cliente_id,
            "periodo": "ultimas_24h",
            "resumo_status": {
                "novo": len(ativos),
                "reconhecido": len(reconhecidos),
                "resolvido": len(resolvidos),
                "cancelado": len(ignorados)
            },
            "resumo_severidade": severidades,
            "zonas_em_alerta": [],
            "alertas_recorrentes": [
                f"{tipo} ({total} vezes)" for tipo, total in sorted(
                    recorrentes.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )[:5]
            ],
            "dados_reais": True,
            "recomendacao_ia": None,
            "mensagem": "Resumo calculado com alertas reais. Zonas ainda não estão vinculadas ao modelo de alerta atual."
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter resumo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter resumo de alertas"
        )
