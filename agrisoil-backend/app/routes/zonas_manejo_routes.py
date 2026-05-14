"""
Rotas de Zonas de Manejo (CAMADA 1 - Contexto Fixo)
Gerenciamento de zonas dentro de uma propriedade.
"""

from datetime import datetime
import logging
from typing import List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.contexto_fixo import (
    NomeCultura,
    TipoSolo,
    ZonaManejoCreate,
    ZonaManejoResponse,
    ZonaManejoUpdate,
)
from app.models.database import AgriParcelDB, ZonaManejoDB
from app.security import (
    get_current_user,
    obter_usuario_atual,
    verificar_produtor_ou_superior,
)

router = APIRouter(prefix="/api/zonas-manejo", tags=["Zonas de Manejo"])
logger = logging.getLogger(__name__)


def _enum_value(value):
    return getattr(value, "value", value)


def _zona_response(zona: ZonaManejoDB) -> ZonaManejoResponse:
    coordenadas = tuple(zona.location_coordinates) if zona.location_coordinates else None
    return ZonaManejoResponse(
        id=zona.zona_id,
        parcel_id=zona.parcel_id,
        nome=zona.nome,
        cultura=zona.cultura,
        variedade=zona.variedade,
        tipo_solo=zona.tipo_solo,
        profundidade_sensor_cm=zona.profundidade_sensor_cm,
        objetivo=zona.objetivo,
        area_hectares=zona.area_hectares,
        location_coordinates=coordenadas,
        criado_em=zona.criado_em,
        atualizado_em=zona.atualizado_em,
        deletado_em=zona.deletado_em,
        ativo=zona.ativo,
    )


def _obter_zona_ou_404(db: Session, zona_id: str) -> ZonaManejoDB:
    zona = db.query(ZonaManejoDB).filter(ZonaManejoDB.zona_id == zona_id).first()
    if not zona or not zona.ativo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zona nao encontrada")
    return zona


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ZonaManejoResponse)
async def criar_zona_manejo(
    parcel_id: str,
    zona_data: ZonaManejoCreate,
    user: dict = Depends(verificar_produtor_ou_superior),
    db: Session = Depends(get_db),
):
    """Criar nova zona de manejo dentro de um talhao real."""
    parcel = db.query(AgriParcelDB).filter(
        AgriParcelDB.parcel_id == parcel_id,
        AgriParcelDB.ativo.is_(True),
    ).first()
    if not parcel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Talhao nao encontrado")

    zona = ZonaManejoDB(
        zona_id=f"zona_{uuid4().hex[:12]}",
        parcel_id=parcel_id,
        prop_id=parcel.farm_id,
        cliente_id=parcel.cliente_id,
        nome=zona_data.nome,
        cultura=_enum_value(zona_data.cultura),
        variedade=zona_data.variedade,
        tipo_solo=_enum_value(zona_data.tipo_solo),
        profundidade_sensor_cm=zona_data.profundidade_sensor_cm,
        objetivo=_enum_value(zona_data.objetivo),
        area_hectares=zona_data.area_hectares,
        location_coordinates=list(zona_data.location_coordinates) if zona_data.location_coordinates else None,
        ativo=True,
    )

    db.add(zona)
    db.commit()
    db.refresh(zona)

    logger.info("Zona criada: %s por %s", zona.zona_id, user)
    return _zona_response(zona)


@router.get("/propriedade/{prop_id}", response_model=List[ZonaManejoResponse])
async def listar_zonas_por_propriedade(
    prop_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Listar todas as zonas ativas de uma propriedade."""
    zonas = db.query(ZonaManejoDB).filter(
        ZonaManejoDB.prop_id == prop_id,
        ZonaManejoDB.ativo.is_(True),
    ).order_by(ZonaManejoDB.nome.asc()).all()

    logger.debug("Listando %s zonas para propriedade %s por %s", len(zonas), prop_id, user_id)
    return [_zona_response(zona) for zona in zonas]


@router.get("/talhao/{parcel_id}", response_model=List[ZonaManejoResponse])
async def listar_zonas_por_talhao(
    parcel_id: str,
    usuario=Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Listar todas as zonas de um talhao."""
    zonas = db.query(ZonaManejoDB).filter(
        ZonaManejoDB.parcel_id == parcel_id,
        ZonaManejoDB.ativo.is_(True),
    ).order_by(ZonaManejoDB.nome.asc()).all()

    logger.debug("Listando %s zonas para talhao %s por %s", len(zonas), parcel_id, usuario)
    return [_zona_response(zona) for zona in zonas]


@router.get("/catalogo/culturas", tags=["Catalogo"])
async def listar_culturas_disponiveis():
    """Retorna lista de culturas disponiveis para selecao."""
    return {"culturas": [c.value for c in NomeCultura], "total": len(list(NomeCultura))}


@router.get("/catalogo/solos", tags=["Catalogo"])
async def listar_solos_disponiveis():
    """Retorna lista de tipos de solo disponiveis."""
    return {"solos": [s.value for s in TipoSolo], "total": len(list(TipoSolo))}


@router.get("/{zona_id}", response_model=ZonaManejoResponse)
async def obter_zona(
    zona_id: str,
    usuario=Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Obter detalhes de uma zona de manejo."""
    logger.debug("Consulta de zona %s por %s", zona_id, usuario)
    return _zona_response(_obter_zona_ou_404(db, zona_id))


@router.put("/{zona_id}", response_model=ZonaManejoResponse)
async def atualizar_zona(
    zona_id: str,
    zona_data: ZonaManejoUpdate,
    usuario=Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Atualizar informacoes de uma zona de manejo."""
    zona = _obter_zona_ou_404(db, zona_id)
    payload = zona_data.model_dump(exclude_unset=True)

    for field, value in payload.items():
        if field == "location_coordinates":
            value = list(value) if value else None
        else:
            value = _enum_value(value)
        setattr(zona, field, value)

    zona.atualizado_em = datetime.utcnow()
    db.commit()
    db.refresh(zona)

    logger.info("Zona atualizada: %s por %s", zona_id, usuario)
    return _zona_response(zona)


@router.delete("/{zona_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_zona(
    zona_id: str,
    usuario=Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Soft delete de zona de manejo."""
    zona = _obter_zona_ou_404(db, zona_id)
    zona.ativo = False
    zona.deletado_em = datetime.utcnow()
    zona.atualizado_em = datetime.utcnow()
    db.commit()

    logger.info("Zona deletada: %s por %s", zona_id, usuario)
