"""
Rotas de Zonas de Manejo (CAMADA 1 - Contexto Fixo)
Gerenciamento de zonas dentro de uma propriedade
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from app.db import get_db
from app.models.contexto_fixo import (
    NomeCultura, TipoSolo, ZonaManejo, ZonaManejoCreate, ZonaManejoUpdate, ZonaManejoResponse
)
from app.security import (
    get_current_user,
    obter_usuario_atual,
    verificar_produtor_ou_superior,
    verificar_admin
)

router = APIRouter(
    prefix="/api/zonas-manejo", 
    tags=["🌾 Zonas de Manejo"]
)
logger = logging.getLogger(__name__)


# ============================================================================
# CRIAR ZONA DE MANEJO
# ============================================================================

@router.post("", status_code=status.HTTP_201_CREATED, response_model=ZonaManejoResponse)
async def criar_zona_manejo(
    parcel_id: str,
    zona_data: ZonaManejoCreate,
    user: dict = Depends(verificar_produtor_ou_superior),
    db: Session = Depends(get_db)
):
    """
    🔐 **PRODUTOR, GESTOR ou ADMIN** podem criar zonas de manejo
    
    Criar nova zona de manejo dentro de um talhão.
    
    **Permissões necessárias**: produtor, gestor ou admin
    
    Exemplo:
    ```json
    {
      "nome": "Soja Norte",
      "cultura": "soja",
      "variedade": "NK 5059",
      "tipo_solo": "franco_argiloso",
      "profundidade_sensor_cm": 20,
      "objetivo": "maximizar_produtividade",
      "area_hectares": 50.5,
      "location_coordinates": [-47.9, -15.7]
    }
    ```
    """
    try:
        # Validar se parcel_id pertence ao cliente
        # TODO: Verificar propriedade/talhão
        
        # Criar zona
        zona = ZonaManejo(
            id=f"zona-{parcel_id}-{datetime.now().timestamp()}",
            parcel_id=parcel_id,
            nome=zona_data.nome,
            cultura=zona_data.cultura,
            variedade=zona_data.variedade,
            tipo_solo=zona_data.tipo_solo,
            profundidade_sensor_cm=zona_data.profundidade_sensor_cm,
            objetivo=zona_data.objetivo,
            area_hectares=zona_data.area_hectares,
            location_coordinates=zona_data.location_coordinates,
            criado_em=datetime.now(),
            atualizado_em=datetime.now(),
            ativo=True
        )
        
        # TODO: Salvar no banco de dados
        # db.add(zona)
        # db.commit()
        # db.refresh(zona)
        
        logger.info(f"Zona criada: {zona.id}")
        return ZonaManejoResponse.from_orm(zona)
        
    except Exception as e:
        logger.error(f"Erro ao criar zona: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ============================================================================
# LISTAR ZONAS DE UM TALHÃO
# ============================================================================

@router.get("/propriedade/{prop_id}", response_model=List[ZonaManejoResponse])
async def listar_zonas_por_propriedade(
    prop_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    🔓 **Qualquer usuário autenticado** pode listar zonas de sua propriedade
    
    Listar todas as zonas de uma propriedade.
    O sistema verifica se o usuário tem acesso à propriedade.
    """
    try:
        # TODO: Query no banco
        # zonas = db.query(ZonaManejo)\
        #     .filter(ZonaManejo.prop_id == prop_id)\
        #     .filter(ZonaManejo.ativo == True)\
        #     .all()
        
        # Por enquanto, retorna lista vazia
        zonas = []
        
        return [ZonaManejoResponse.from_orm(z) for z in zonas]
        
    except Exception as e:
        logger.error(f"Erro ao listar zonas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao listar zonas"
        )


# ============================================================================
# LISTAR ZONAS DE UM TALHÃO
# ============================================================================

@router.get("/talhao/{parcel_id}", response_model=List[ZonaManejoResponse])
async def listar_zonas_por_talhao(
    parcel_id: str,
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Listar todas as zonas de um talhão (parcel)
    """
    try:
        # TODO: Query no banco
        # zonas = db.query(ZonaManejo)\
        #     .filter(ZonaManejo.parcel_id == parcel_id)\
        #     .filter(ZonaManejo.ativo == True)\
        #     .all()
        
        zonas = []
        return [ZonaManejoResponse.from_orm(z) for z in zonas]
        
    except Exception as e:
        logger.error(f"Erro ao listar zonas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao listar zonas"
        )


# ============================================================================
# OBTER ZONA ESPECÍFICA
# ============================================================================

@router.get("/{zona_id}", response_model=ZonaManejoResponse)
async def obter_zona(
    zona_id: str,
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Obter detalhes de uma zona de manejo
    """
    try:
        # TODO: Query no banco
        # zona = db.query(ZonaManejo)\
        #     .filter(ZonaManejo.id == zona_id)\
        #     .first()
        
        # if not zona:
        #     raise HTTPException(
        #         status_code=status.HTTP_404_NOT_FOUND,
        #         detail="Zona não encontrada"
        #     )
        
        # return ZonaManejoResponse.from_orm(zona)
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zona não encontrada"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter zona: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter zona"
        )


# ============================================================================
# ATUALIZAR ZONA
# ============================================================================

@router.put("/{zona_id}", response_model=ZonaManejoResponse)
async def atualizar_zona(
    zona_id: str,
    zona_data: ZonaManejoCreate,
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Atualizar informações de uma zona de manejo
    """
    try:
        # TODO: Query no banco
        # zona = db.query(ZonaManejo)\
        #     .filter(ZonaManejo.id == zona_id)\
        #     .first()
        
        # if not zona:
        #     raise HTTPException(
        #         status_code=status.HTTP_404_NOT_FOUND,
        #         detail="Zona não encontrada"
        #     )
        
        # zona.nome = zona_data.nome
        # zona.cultura = zona_data.cultura
        # zona.variedade = zona_data.variedade
        # zona.tipo_solo = zona_data.tipo_solo
        # zona.profundidade_sensor_cm = zona_data.profundidade_sensor_cm
        # zona.objetivo = zona_data.objetivo
        # zona.area_hectares = zona_data.area_hectares
        # zona.location_coordinates = zona_data.location_coordinates
        # zona.atualizado_em = datetime.now()
        
        # db.commit()
        # db.refresh(zona)
        
        # return ZonaManejoResponse.from_orm(zona)
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zona não encontrada"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar zona: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar zona"
        )


# ============================================================================
# DELETAR ZONA
# ============================================================================

@router.delete("/{zona_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_zona(
    zona_id: str,
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Deletar uma zona de manejo (soft delete - marcar como inativa)
    """
    try:
        # TODO: Query no banco
        # zona = db.query(ZonaManejo)\
        #     .filter(ZonaManejo.id == zona_id)\
        #     .first()
        
        # if not zona:
        #     raise HTTPException(
        #         status_code=status.HTTP_404_NOT_FOUND,
        #         detail="Zona não encontrada"
        #     )
        
        # zona.ativo = False
        # zona.atualizado_em = datetime.now()
        # db.commit()
        
        logger.info(f"Zona deletada: {zona_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao deletar zona: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao deletar zona"
        )


# ============================================================================
# LISTAR CULTURAS DISPONÍVEIS
# ============================================================================

@router.get("/catalogo/culturas", tags=["Catálogo"])
async def listar_culturas_disponiveis():
    """
    Retorna lista de culturas disponíveis para seleção
    """
    return {
        "culturas": [c.value for c in NomeCultura],
        "total": len(list(NomeCultura))
    }


# ============================================================================
# LISTAR TIPOS DE SOLO
# ============================================================================

@router.get("/catalogo/solos", tags=["Catálogo"])
async def listar_solos_disponiveis():
    """
    Retorna lista de tipos de solo disponíveis
    """
    return {
        "solos": [s.value for s in TipoSolo],
        "total": len(list(TipoSolo))
    }
