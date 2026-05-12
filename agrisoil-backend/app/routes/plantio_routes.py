"""
Rotas de Plantio e Fase da Cultura (CAMADA 2)
Registro de plantio e deteccao automatica de fase.
"""

from datetime import datetime, timedelta
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.contexto_fixo import FaseFenologica
from app.models.database import FaseAtualDB, HistoricoFaseDB, ZonaManejoDB
from app.models.fase_cultura import (
    DeteccaoFaseResponse,
    FaseAtual,
    FaseAtualCreate,
    MetodoDeteccaoFase,
)
from app.security import obter_usuario_atual

router = APIRouter(prefix="/api/plantio", tags=["Plantio e Fase"])
logger = logging.getLogger(__name__)


FASES_POR_DIA = [
    (15, FaseFenologica.EMERGENCIA),
    (45, FaseFenologica.VEGETATIVO),
    (65, FaseFenologica.FLORESCIMENTO),
    (100, FaseFenologica.ENCHIMENTO_GRAOS),
    (125, FaseFenologica.MATURACAO),
    (10_000, FaseFenologica.COLHEITA),
]


def _detectar_fase(dias_apos_plantio: int) -> FaseFenologica:
    for limite, fase in FASES_POR_DIA:
        if dias_apos_plantio <= limite:
            return fase
    return FaseFenologica.COLHEITA


def _dias_para_proxima_fase(dias_apos_plantio: int) -> int:
    for limite, _fase in FASES_POR_DIA:
        if dias_apos_plantio < limite:
            return max(limite - dias_apos_plantio, 0)
    return 0


def _fim_fase_atual(data_plantio: datetime, dias_apos_plantio: int) -> datetime:
    return data_plantio + timedelta(days=dias_apos_plantio + _dias_para_proxima_fase(dias_apos_plantio))


def _fase_atual_model(fase: FaseAtualDB) -> FaseAtual:
    return FaseAtual(
        zona_id=fase.zona_id,
        cultura=fase.cultura,
        fase=fase.fase,
        metodo=fase.metodo,
        data_plantio=fase.data_plantio,
        dias_apos_plantio=fase.dias_apos_plantio,
        data_inicio_fase=fase.data_inicio_fase,
        data_prevista_proxima_fase=fase.data_prevista_proxima_fase,
        graus_dias_acumulados=fase.graus_dias_acumulados,
        graus_dias_necessarios=fase.graus_dias_necessarios,
        certeza_fase_percentual=fase.certeza_fase_percentual,
        validado_por_agronomia=fase.validado_por_agronomia,
        detectado_em=fase.detectado_em,
        ultima_validacao=fase.ultima_validacao,
    )


def _obter_zona_ou_404(db: Session, zona_id: str) -> ZonaManejoDB:
    zona = db.query(ZonaManejoDB).filter(
        ZonaManejoDB.zona_id == zona_id,
        ZonaManejoDB.ativo.is_(True),
    ).first()
    if not zona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zona nao encontrada")
    return zona


def _ultima_fase(db: Session, zona_id: str) -> FaseAtualDB | None:
    return db.query(FaseAtualDB).filter(FaseAtualDB.zona_id == zona_id).order_by(FaseAtualDB.detectado_em.desc()).first()


@router.post("/registrar/{zona_id}", response_model=dict)
async def registrar_plantio(
    zona_id: str,
    plantio_data: FaseAtualCreate,
    usuario=Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Registrar data de plantio para uma zona."""
    agora = datetime.utcnow()
    data_plantio = plantio_data.data_plantio.replace(tzinfo=None)
    if data_plantio > agora:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Data de plantio nao pode ser no futuro")

    zona = _obter_zona_ou_404(db, zona_id)
    fase_anterior = _ultima_fase(db, zona_id)
    dias_apos_plantio = max((agora - data_plantio).days, 0)
    fase_detectada = plantio_data.fase_observada or _detectar_fase(dias_apos_plantio)
    metodo = MetodoDeteccaoFase.OBSERVACAO_CAMPO if plantio_data.fase_observada else MetodoDeteccaoFase.DATA_PLANTIO

    fase_atual = FaseAtualDB(
        zona_id=zona_id,
        cultura=zona.cultura,
        fase=fase_detectada.value,
        metodo=metodo.value,
        data_plantio=data_plantio,
        dias_apos_plantio=dias_apos_plantio,
        data_inicio_fase=data_plantio,
        data_prevista_proxima_fase=_fim_fase_atual(data_plantio, dias_apos_plantio),
        certeza_fase_percentual=100 if plantio_data.validado_por_agronomia else 90,
        validado_por_agronomia=plantio_data.validado_por_agronomia,
        ultima_validacao=agora if plantio_data.validado_por_agronomia else None,
        observacoes=plantio_data.observacoes,
    )
    db.add(fase_atual)
    db.add(
        HistoricoFaseDB(
            zona_id=zona_id,
            fase_anterior=fase_anterior.fase if fase_anterior else None,
            fase_nova=fase_detectada.value,
            data_transicao=agora,
            dias_na_fase_anterior=(agora - fase_anterior.detectado_em).days if fase_anterior else 0,
            metodo=metodo.value,
            validado=plantio_data.validado_por_agronomia,
        )
    )
    db.commit()
    db.refresh(fase_atual)

    logger.info("Plantio registrado: zona=%s, fase=%s por %s", zona_id, fase_detectada.value, usuario)
    return {
        "zona_id": zona_id,
        "data_plantio": data_plantio,
        "fase_atual": fase_detectada.value,
        "dias_apos_plantio": dias_apos_plantio,
        "mensagem": "Sistema pronto para monitorar a cultura",
    }


@router.get("/{zona_id}/fase-atual", response_model=DeteccaoFaseResponse)
async def obter_fase_atual(
    zona_id: str,
    usuario=Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Obter fase atual da cultura em uma zona."""
    _obter_zona_ou_404(db, zona_id)
    fase = _ultima_fase(db, zona_id)
    if not fase:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sem registro de plantio para esta zona")

    logger.debug("Consulta de fase atual da zona %s por %s", zona_id, usuario)
    return DeteccaoFaseResponse(
        zona_id=zona_id,
        fase_atual=_fase_atual_model(fase),
        proxima_fase_em_dias=_dias_para_proxima_fase(fase.dias_apos_plantio),
        status="em_dia",
        alerta_fase=None,
    )


@router.post("/{zona_id}/fase-atual/validar", response_model=dict)
async def validar_fase_manualmente(
    zona_id: str,
    fase_observada: FaseFenologica,
    usuario=Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Validar fase manualmente quando tecnico/agronomo confirma no campo."""
    _obter_zona_ou_404(db, zona_id)
    fase = _ultima_fase(db, zona_id)
    if not fase:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sem registro de plantio para esta zona")

    agora = datetime.utcnow()
    fase_anterior = fase.fase
    fase.fase = fase_observada.value
    fase.metodo = MetodoDeteccaoFase.OBSERVACAO_CAMPO.value
    fase.validado_por_agronomia = True
    fase.certeza_fase_percentual = 100
    fase.ultima_validacao = agora
    fase.detectado_em = agora
    fase.data_prevista_proxima_fase = _fim_fase_atual(fase.data_plantio, fase.dias_apos_plantio)

    if fase_anterior != fase_observada.value:
        db.add(
            HistoricoFaseDB(
                zona_id=zona_id,
                fase_anterior=fase_anterior,
                fase_nova=fase_observada.value,
                data_transicao=agora,
                dias_na_fase_anterior=0,
                metodo=MetodoDeteccaoFase.OBSERVACAO_CAMPO.value,
                validado=True,
            )
        )

    db.commit()

    logger.info("Fase validada: zona=%s, fase=%s por %s", zona_id, fase_observada.value, usuario)
    return {
        "zona_id": zona_id,
        "fase_validada": fase_observada.value,
        "confirmada_por": usuario,
        "timestamp": agora,
        "mensagem": "Fase validada com sucesso",
    }


@router.get("/{zona_id}/historico-fases", response_model=dict)
async def obter_historico_fases(
    zona_id: str,
    usuario=Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Obter historico de transicoes de fase."""
    _obter_zona_ou_404(db, zona_id)
    historico = db.query(HistoricoFaseDB).filter(
        HistoricoFaseDB.zona_id == zona_id,
    ).order_by(HistoricoFaseDB.data_transicao.desc()).all()

    logger.debug("Historico de fases da zona %s consultado por %s", zona_id, usuario)
    return {
        "zona_id": zona_id,
        "total_fases": len(historico),
        "historico": [
            {
                "fase_anterior": item.fase_anterior,
                "fase_nova": item.fase_nova,
                "data_transicao": item.data_transicao,
                "dias_na_fase_anterior": item.dias_na_fase_anterior,
                "metodo": item.metodo,
                "validado": item.validado,
            }
            for item in historico
        ],
    }
