"""
Rotas de Plantio e Fase da Cultura (CAMADA 2)
Registro de plantio e detecção automática de fase
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import logging

from app.db import get_db
from app.models.fase_cultura import (
    FaseAtual, FaseAtualCreate, DeteccaoFaseResponse, HistoricoFase,
    MetodoDeteccaoFase
)
from app.security import obter_usuario_atual

router = APIRouter(prefix="/api/plantio", tags=["Plantio e Fase"])
logger = logging.getLogger(__name__)


# ============================================================================
# REGISTRAR PLANTIO
# ============================================================================

@router.post("/registrar/{zona_id}", response_model=dict)
async def registrar_plantio(
    zona_id: str,
    plantio_data: FaseAtualCreate,
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Registrar data de plantio para uma zona
    
    Isso inicia:
    1. Detecção automática de fase
    2. Geração de alertas contextualizados
    3. Rastreamento do ciclo
    
    Exemplo:
    ```json
    {
      "data_plantio": "2025-10-17T08:00:00Z",
      "fase_observada": null,
      "observacoes": "Plantio de soja com boa umidade",
      "validado_por_agronomia": false
    }
    ```
    """
    try:
        # Validar data
        if plantio_data.data_plantio > datetime.now():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Data de plantio não pode ser no futuro"
            )
        
        # TODO: Buscar zona no banco
        # zona = db.query(ZonaManejo)\
        #     .filter(ZonaManejo.id == zona_id)\
        #     .first()
        
        # if not zona:
        #     raise HTTPException(
        #         status_code=status.HTTP_404_NOT_FOUND,
        #         detail="Zona não encontrada"
        #     )
        
        # Calcular dias após plantio
        dias_apos_plantio = (datetime.now() - plantio_data.data_plantio).days
        
        # Detectar fase automaticamente
        # TODO: Usar motor de detecção de fase
        # fase_detectada = detector_fase.detectar(
        #     cultura=zona.cultura,
        #     data_plantio=plantio_data.data_plantio
        # )
        
        # Mock
        fase_atual = FaseAtual(
            zona_id=zona_id,
            cultura="soja",  # zona.cultura
            fase="emergencia",  # fase_detectada
            metodo=MetodoDeteccaoFase.DATA_PLANTIO,
            data_plantio=plantio_data.data_plantio,
            dias_apos_plantio=dias_apos_plantio,
            data_inicio_fase=plantio_data.data_plantio,
            data_prevista_proxima_fase=datetime.now(),  # Calcular
            graus_dias_acumulados=None,
            graus_dias_necessarios=None,
            certeza_fase_percentual=95,
            validado_por_agronomia=plantio_data.validado_por_agronomia,
            detectado_em=datetime.now(),
            ultima_validacao=None if not plantio_data.validado_por_agronomia else datetime.now()
        )
        
        # TODO: Salvar no banco
        # db.add(fase_atual)
        # db.commit()
        # db.refresh(fase_atual)
        
        logger.info(f"Plantio registrado: zona={zona_id}, data={plantio_data.data_plantio}")
        
        return {
            "zona_id": zona_id,
            "data_plantio": plantio_data.data_plantio,
            "fase_atual": "emergencia",
            "dias_apos_plantio": dias_apos_plantio,
            "proximamente": "Alertas contextualizados ativados!",
            "mensagem": "Sistema pronto para monitorar a cultura"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao registrar plantio: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# OBTER FASE ATUAL
# ============================================================================

@router.get("/{zona_id}/fase-atual", response_model=DeteccaoFaseResponse)
async def obter_fase_atual(
    zona_id: str,
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Obter fase atual da cultura em uma zona
    
    Retorna:
    - Fase atual
    - Dias até próxima fase
    - Confiança da detecção
    - Status (em dia, adiantado, atrasado)
    """
    try:
        # TODO: Query no banco
        # fase = db.query(FaseAtual)\
        #     .filter(FaseAtual.zona_id == zona_id)\
        #     .order_by(FaseAtual.detectado_em.desc())\
        #     .first()
        
        # if not fase:
        #     raise HTTPException(
        #         status_code=status.HTTP_404_NOT_FOUND,
        #         detail="Sem registro de plantio para esta zona"
        #     )
        
        # Mock
        return DeteccaoFaseResponse(
            zona_id=zona_id,
            fase_atual=FaseAtual(
                zona_id=zona_id,
                cultura="soja",
                fase="emergencia",
                metodo=MetodoDeteccaoFase.DATA_PLANTIO,
                data_plantio=datetime(2025, 10, 17),
                dias_apos_plantio=21,
                data_inicio_fase=datetime(2025, 10, 17),
                data_prevista_proxima_fase=datetime(2025, 11, 10),
                graus_dias_acumulados=120.5,
                graus_dias_necessarios=80,
                certeza_fase_percentual=95,
                validado_por_agronomia=True,
                detectado_em=datetime.now(),
                ultima_validacao=datetime.now()
            ),
            proxima_fase_em_dias=20,
            status="em_dia",
            alerta_fase=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter fase: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter fase atual"
        )


# ============================================================================
# VALIDAR FASE MANUALMENTE
# ============================================================================

@router.post("/{zona_id}/fase-atual/validar", response_model=dict)
async def validar_fase_manualmente(
    zona_id: str,
    fase_observada: str,  # ex: "emergencia", "vegetativo"
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Validar fase manualmente (agrônomo foi ao campo)
    
    Isso atualiza a confiança e pode corrigir detecção automática
    """
    try:
        # TODO: Query no banco e update
        
        logger.info(f"Fase validada: zona={zona_id}, fase={fase_observada}")
        
        return {
            "zona_id": zona_id,
            "fase_validada": fase_observada,
            "confirmada_por": usuario,
            "timestamp": datetime.now(),
            "mensagem": "Fase validada com sucesso"
        }
        
    except Exception as e:
        logger.error(f"Erro ao validar fase: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao validar fase"
        )


# ============================================================================
# HISTÓRICO DE FASES
# ============================================================================

@router.get("/{zona_id}/historico-fases", response_model=dict)
async def obter_historico_fases(
    zona_id: str,
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Obter histórico de transições de fase
    
    Mostra quando entrou em cada fase e quanto tempo ficou
    """
    try:
        # TODO: Query no banco
        historico = [
            {
                "fase_anterior": None,
                "fase_nova": "emergencia",
                "data_transicao": datetime(2025, 10, 17),
                "dias_na_fase": 21,
                "metodo": "data_plantio",
                "validado": True
            },
            {
                "fase_anterior": "emergencia",
                "fase_nova": "vegetativo",
                "data_transicao": datetime(2025, 11, 7),
                "dias_na_fase": 15,  # Previsto
                "metodo": "automatico",
                "validado": False
            }
        ]
        
        return {
            "zona_id": zona_id,
            "total_fases": len(historico),
            "historico": historico
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter histórico: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter histórico de fases"
        )
