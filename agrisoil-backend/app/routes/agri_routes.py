"""
Rotas de API para Gestão Agrícola Completa
Endpoints CRUD para todas as entidades do Smart Data Models
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.db import get_db
from app.models.agri_models import *
from app.repositories.agri_repository import *

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agri", tags=["Gestão Agrícola"])


# ============================================================================
# AGRI FARM (Fazendas)
# ============================================================================

@router.post(
    "/farms",
    response_model=AgriFarmResponse,
    status_code=201,
    summary="Criar Fazenda"
)
async def criar_fazenda(
    farm: AgriFarmCreate,
    db: Session = Depends(get_db)
):
    """
    Cria uma nova fazenda/propriedade rural
    
    - **farm_id**: ID único da fazenda
    - **name**: Nome da fazenda
    - **area**: Área total em hectares
    - **location_coordinates**: [longitude, latitude]
    """
    try:
        repo = AgriFarmRepository(db)
        
        # Verificar se já existe
        existe = repo.buscar_por_id(farm.farm_id)
        if existe:
            raise HTTPException(status_code=400, detail=f"Fazenda {farm.farm_id} já existe")
        
        db_farm = repo.criar(farm)
        logger.info(f"✓ Fazenda criada: {farm.farm_id}")
        return db_farm
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar fazenda: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/farms/{farm_id}",
    response_model=AgriFarmResponse,
    summary="Buscar Fazenda"
)
async def buscar_fazenda(
    farm_id: str,
    db: Session = Depends(get_db)
):
    """Busca uma fazenda específica por ID"""
    repo = AgriFarmRepository(db)
    farm = repo.buscar_por_id(farm_id)
    
    if not farm:
        raise HTTPException(status_code=404, detail="Fazenda não encontrada")
    
    return farm


@router.get(
    "/farms/cliente/{cliente_id}",
    response_model=List[AgriFarmResponse],
    summary="Listar Fazendas do Cliente"
)
async def listar_fazendas_cliente(
    cliente_id: str,
    apenas_ativas: bool = Query(True, description="Retornar apenas fazendas ativas"),
    db: Session = Depends(get_db)
):
    """Lista todas as fazendas de um cliente"""
    repo = AgriFarmRepository(db)
    farms = repo.listar_por_cliente(cliente_id, apenas_ativas)
    return farms


@router.put(
    "/farms/{farm_id}",
    response_model=AgriFarmResponse,
    summary="Atualizar Fazenda"
)
async def atualizar_fazenda(
    farm_id: str,
    farm_update: AgriFarmUpdate,
    db: Session = Depends(get_db)
):
    """Atualiza informações de uma fazenda"""
    repo = AgriFarmRepository(db)
    farm = repo.atualizar(farm_id, farm_update)
    
    if not farm:
        raise HTTPException(status_code=404, detail="Fazenda não encontrada")
    
    logger.info(f"✓ Fazenda atualizada: {farm_id}")
    return farm


@router.delete(
    "/farms/{farm_id}",
    summary="Desativar Fazenda"
)
async def desativar_fazenda(
    farm_id: str,
    db: Session = Depends(get_db)
):
    """Desativa uma fazenda (soft delete)"""
    repo = AgriFarmRepository(db)
    sucesso = repo.desativar(farm_id)
    
    if not sucesso:
        raise HTTPException(status_code=404, detail="Fazenda não encontrada")
    
    return {"status": "sucesso", "mensagem": f"Fazenda {farm_id} desativada"}


# ============================================================================
# AGRI PARCEL (Talhões)
# ============================================================================

@router.post(
    "/parcels",
    response_model=AgriParcelResponse,
    status_code=201,
    summary="Criar Talhão"
)
async def criar_talhao(
    parcel: AgriParcelCreate,
    db: Session = Depends(get_db)
):
    """
    Cria um novo talhão dentro de uma fazenda
    
    - **parcel_id**: ID único do talhão
    - **farm_id**: ID da fazenda à qual pertence
    - **crop_id**: ID da cultura plantada (opcional)
    """
    try:
        repo = AgriParcelRepository(db)
        
        # Verificar se já existe
        existe = repo.buscar_por_id(parcel.parcel_id)
        if existe:
            raise HTTPException(status_code=400, detail=f"Talhão {parcel.parcel_id} já existe")
        
        db_parcel = repo.criar(parcel)
        logger.info(f"✓ Talhão criado: {parcel.parcel_id}")
        return db_parcel
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar talhão: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/parcels/{parcel_id}",
    response_model=AgriParcelResponse,
    summary="Buscar Talhão"
)
async def buscar_talhao(
    parcel_id: str,
    db: Session = Depends(get_db)
):
    """Busca um talhão específico por ID"""
    repo = AgriParcelRepository(db)
    parcel = repo.buscar_por_id(parcel_id)
    
    if not parcel:
        raise HTTPException(status_code=404, detail="Talhão não encontrado")
    
    return parcel


@router.get(
    "/parcels/cliente/{cliente_id}",
    response_model=List[AgriParcelResponse],
    summary="Listar Talhões do Cliente"
)
async def listar_talhoes_cliente(
    cliente_id: str,
    db: Session = Depends(get_db)
):
    """Lista todos os talhões de um cliente"""
    repo = AgriParcelRepository(db)
    parcels = repo.listar_por_cliente(cliente_id)
    return parcels


@router.get(
    "/parcels/farm/{farm_id}",
    response_model=List[AgriParcelResponse],
    summary="Listar Talhões da Fazenda"
)
async def listar_talhoes_fazenda(
    farm_id: str,
    db: Session = Depends(get_db)
):
    """Lista todos os talhões de uma fazenda"""
    repo = AgriParcelRepository(db)
    parcels = repo.listar_por_fazenda(farm_id)
    return parcels


@router.put(
    "/parcels/{parcel_id}",
    response_model=AgriParcelResponse,
    summary="Atualizar Talhão"
)
async def atualizar_talhao(
    parcel_id: str,
    parcel_update: AgriParcelUpdate,
    db: Session = Depends(get_db)
):
    """Atualiza informações de um talhão"""
    repo = AgriParcelRepository(db)
    parcel = repo.atualizar(parcel_id, parcel_update)
    
    if not parcel:
        raise HTTPException(status_code=404, detail="Talhão não encontrado")
    
    logger.info(f"✓ Talhão atualizado: {parcel_id}")
    return parcel


# ============================================================================
# AGRI CROP (Culturas)
# ============================================================================

@router.post(
    "/crops",
    response_model=AgriCropResponse,
    status_code=201,
    summary="Criar Cultura"
)
async def criar_cultura(
    crop: AgriCropCreate,
    db: Session = Depends(get_db)
):
    """
    Cadastra uma nova cultura/plantação
    
    - **crop_id**: ID único da cultura (ex: "soja", "milho")
    - **planting_from/to**: Período de plantio (--MM-DD)
    - **harvesting_from/to**: Período de colheita (--MM-DD)
    """
    try:
        repo = AgriCropRepository(db)
        
        # Verificar se já existe
        existe = repo.buscar_por_id(crop.crop_id)
        if existe:
            raise HTTPException(status_code=400, detail=f"Cultura {crop.crop_id} já existe")
        
        db_crop = repo.criar(crop)
        logger.info(f"✓ Cultura criada: {crop.crop_id}")
        return db_crop
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar cultura: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/crops/{crop_id}",
    response_model=AgriCropResponse,
    summary="Buscar Cultura"
)
async def buscar_cultura(
    crop_id: str,
    db: Session = Depends(get_db)
):
    """Busca uma cultura específica por ID"""
    repo = AgriCropRepository(db)
    crop = repo.buscar_por_id(crop_id)
    
    if not crop:
        raise HTTPException(status_code=404, detail="Cultura não encontrada")
    
    return crop


@router.get(
    "/crops",
    response_model=List[AgriCropResponse],
    summary="Listar Todas as Culturas"
)
async def listar_culturas(
    nome: Optional[str] = Query(None, description="Filtrar por nome"),
    db: Session = Depends(get_db)
):
    """Lista todas as culturas cadastradas"""
    repo = AgriCropRepository(db)
    
    if nome:
        crops = repo.buscar_por_nome(nome)
    else:
        crops = repo.listar_todas()
    
    return crops


@router.put(
    "/crops/{crop_id}",
    response_model=AgriCropResponse,
    summary="Atualizar Cultura"
)
async def atualizar_cultura(
    crop_id: str,
    crop_update: AgriCropUpdate,
    db: Session = Depends(get_db)
):
    """Atualiza informações de uma cultura"""
    repo = AgriCropRepository(db)
    crop = repo.atualizar(crop_id, crop_update)
    
    if not crop:
        raise HTTPException(status_code=404, detail="Cultura não encontrada")
    
    logger.info(f"✓ Cultura atualizada: {crop_id}")
    return crop


# ============================================================================
# AGRI PARCEL RECORD (Registros de Condições)
# ============================================================================

@router.post(
    "/records",
    response_model=AgriParcelRecordResponse,
    status_code=201,
    summary="Criar Registro de Condições"
)
async def criar_registro(
    record: AgriParcelRecordCreate,
    db: Session = Depends(get_db)
):
    """
    Salva um registro de condições do talhão
    
    Complementa os sensores com dados adicionais como:
    - Pressão atmosférica
    - Radiação solar
    - Umidade das folhas
    """
    try:
        repo = AgriParcelRecordRepository(db)
        db_record = repo.criar(record)
        logger.info(f"✓ Registro criado: {record.record_id} para talhão {record.parcel_id}")
        return db_record
        
    except Exception as e:
        logger.error(f"Erro ao criar registro: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/records/{record_id}",
    response_model=AgriParcelRecordResponse,
    summary="Buscar Registro"
)
async def buscar_registro(
    record_id: str,
    db: Session = Depends(get_db)
):
    """Busca um registro específico"""
    repo = AgriParcelRecordRepository(db)
    record = repo.buscar_por_id(record_id)
    
    if not record:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    
    return record


@router.get(
    "/records/parcel/{parcel_id}/last",
    response_model=AgriParcelRecordResponse,
    summary="Último Registro do Talhão"
)
async def ultimo_registro_talhao(
    parcel_id: str,
    db: Session = Depends(get_db)
):
    """Retorna o último registro de condições de um talhão"""
    repo = AgriParcelRecordRepository(db)
    record = repo.buscar_ultimo_registro(parcel_id)
    
    if not record:
        raise HTTPException(status_code=404, detail="Nenhum registro encontrado")
    
    return record


@router.get(
    "/records/parcel/{parcel_id}/history",
    response_model=List[AgriParcelRecordResponse],
    summary="Histórico de Registros do Talhão"
)
async def historico_registros_talhao(
    parcel_id: str,
    limit: int = Query(100, description="Quantidade máxima de registros"),
    offset: int = Query(0, description="Deslocamento para paginação"),
    db: Session = Depends(get_db)
):
    """Retorna histórico de registros de um talhão"""
    repo = AgriParcelRecordRepository(db)
    records = repo.buscar_historico(parcel_id, limit, offset)
    return records


# ============================================================================
# AGRI PARCEL OPERATION (Operações)
# ============================================================================

@router.post(
    "/operations",
    response_model=AgriParcelOperationResponse,
    status_code=201,
    summary="Criar Operação"
)
async def criar_operacao(
    operation: AgriParcelOperationCreate,
    db: Session = Depends(get_db)
):
    """
    Registra uma operação no talhão
    
    Tipos de operação:
    - **fertilising**: Fertilização
    - **irrigation**: Irrigação
    - **harvesting**: Colheita
    - **sowing**: Plantio
    - **pestControl**: Controle de pragas
    """
    try:
        repo = AgriParcelOperationRepository(db)
        db_operation = repo.criar(operation)
        logger.info(f"✓ Operação criada: {operation.operation_id} - {operation.operation_type}")
        return db_operation
        
    except Exception as e:
        logger.error(f"Erro ao criar operação: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/operations/{operation_id}",
    response_model=AgriParcelOperationResponse,
    summary="Buscar Operação"
)
async def buscar_operacao(
    operation_id: str,
    db: Session = Depends(get_db)
):
    """Busca uma operação específica"""
    repo = AgriParcelOperationRepository(db)
    operation = repo.buscar_por_id(operation_id)
    
    if not operation:
        raise HTTPException(status_code=404, detail="Operação não encontrada")
    
    return operation


@router.get(
    "/operations/parcel/{parcel_id}",
    response_model=List[AgriParcelOperationResponse],
    summary="Listar Operações do Talhão"
)
async def listar_operacoes_talhao(
    parcel_id: str,
    status: Optional[str] = Query(None, description="Filtrar por status"),
    db: Session = Depends(get_db)
):
    """Lista todas as operações de um talhão"""
    repo = AgriParcelOperationRepository(db)
    operations = repo.listar_por_talhao(parcel_id, status)
    return operations


@router.get(
    "/operations/cliente/{cliente_id}",
    response_model=List[AgriParcelOperationResponse],
    summary="Listar Operações do Cliente"
)
async def listar_operacoes_cliente(
    cliente_id: str,
    operation_type: Optional[str] = Query(None, description="Filtrar por tipo"),
    status: Optional[str] = Query(None, description="Filtrar por status"),
    limit: int = Query(100, description="Quantidade máxima"),
    db: Session = Depends(get_db)
):
    """Lista todas as operações de um cliente"""
    repo = AgriParcelOperationRepository(db)
    operations = repo.listar_por_cliente(cliente_id, operation_type, status, limit)
    return operations


@router.put(
    "/operations/{operation_id}",
    response_model=AgriParcelOperationResponse,
    summary="Atualizar Operação"
)
async def atualizar_operacao(
    operation_id: str,
    operation_update: AgriParcelOperationUpdate,
    db: Session = Depends(get_db)
):
    """Atualiza informações de uma operação"""
    repo = AgriParcelOperationRepository(db)
    operation = repo.atualizar(operation_id, operation_update)
    
    if not operation:
        raise HTTPException(status_code=404, detail="Operação não encontrada")
    
    logger.info(f"✓ Operação atualizada: {operation_id}")
    return operation


@router.post(
    "/operations/{operation_id}/start",
    response_model=AgriParcelOperationResponse,
    summary="Iniciar Operação"
)
async def iniciar_operacao(
    operation_id: str,
    db: Session = Depends(get_db)
):
    """Marca operação como iniciada"""
    repo = AgriParcelOperationRepository(db)
    operation = repo.iniciar_operacao(operation_id)
    
    if not operation:
        raise HTTPException(status_code=404, detail="Operação não encontrada")
    
    logger.info(f"✓ Operação iniciada: {operation_id}")
    return operation


@router.post(
    "/operations/{operation_id}/finish",
    response_model=AgriParcelOperationResponse,
    summary="Finalizar Operação"
)
async def finalizar_operacao(
    operation_id: str,
    db: Session = Depends(get_db)
):
    """Marca operação como finalizada"""
    repo = AgriParcelOperationRepository(db)
    operation = repo.finalizar_operacao(operation_id)
    
    if not operation:
        raise HTTPException(status_code=404, detail="Operação não encontrada")
    
    logger.info(f"✓ Operação finalizada: {operation_id}")
    return operation


# ============================================================================
# AGRI FERTILIZE (Fertilizantes)
# ============================================================================

@router.post(
    "/fertilizes",
    response_model=AgriFertilizeResponse,
    status_code=201,
    summary="Cadastrar Fertilizante"
)
async def cadastrar_fertilizante(
    fertilize: AgriFertilizeCreate,
    db: Session = Depends(get_db)
):
    """
    Cadastra um fertilizante no sistema
    
    Útil para rastreabilidade e compliance regulatório
    """
    try:
        repo = AgriFertilizeRepository(db)
        
        # Verificar se já existe
        existe = repo.buscar_por_id(fertilize.fertilize_id)
        if existe:
            raise HTTPException(status_code=400, detail=f"Fertilizante {fertilize.fertilize_id} já existe")
        
        db_fertilize = repo.criar(fertilize)
        logger.info(f"✓ Fertilizante cadastrado: {fertilize.fertilize_id}")
        return db_fertilize
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao cadastrar fertilizante: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/fertilizes/{fertilize_id}",
    response_model=AgriFertilizeResponse,
    summary="Buscar Fertilizante"
)
async def buscar_fertilizante(
    fertilize_id: str,
    db: Session = Depends(get_db)
):
    """Busca um fertilizante específico"""
    repo = AgriFertilizeRepository(db)
    fertilize = repo.buscar_por_id(fertilize_id)
    
    if not fertilize:
        raise HTTPException(status_code=404, detail="Fertilizante não encontrado")
    
    return fertilize


@router.get(
    "/fertilizes/cliente/{cliente_id}",
    response_model=List[AgriFertilizeResponse],
    summary="Listar Fertilizantes do Cliente"
)
async def listar_fertilizantes_cliente(
    cliente_id: str,
    nome: Optional[str] = Query(None, description="Filtrar por nome"),
    db: Session = Depends(get_db)
):
    """Lista todos os fertilizantes cadastrados por um cliente"""
    repo = AgriFertilizeRepository(db)
    
    if nome:
        fertilizes = repo.buscar_por_nome(cliente_id, nome)
    else:
        fertilizes = repo.listar_por_cliente(cliente_id)
    
    return fertilizes


@router.put(
    "/fertilizes/{fertilize_id}",
    response_model=AgriFertilizeResponse,
    summary="Atualizar Fertilizante"
)
async def atualizar_fertilizante(
    fertilize_id: str,
    fertilize_update: AgriFertilizeUpdate,
    db: Session = Depends(get_db)
):
    """Atualiza informações de um fertilizante"""
    repo = AgriFertilizeRepository(db)
    fertilize = repo.atualizar(fertilize_id, fertilize_update)
    
    if not fertilize:
        raise HTTPException(status_code=404, detail="Fertilizante não encontrado")
    
    logger.info(f"✓ Fertilizante atualizado: {fertilize_id}")
    return fertilize


@router.delete(
    "/fertilizes/{fertilize_id}",
    summary="Deletar Fertilizante"
)
async def deletar_fertilizante(
    fertilize_id: str,
    db: Session = Depends(get_db)
):
    """Deleta um fertilizante do cadastro"""
    repo = AgriFertilizeRepository(db)
    sucesso = repo.deletar(fertilize_id)
    
    if not sucesso:
        raise HTTPException(status_code=404, detail="Fertilizante não encontrado")
    
    return {"status": "sucesso", "mensagem": f"Fertilizante {fertilize_id} deletado"}
