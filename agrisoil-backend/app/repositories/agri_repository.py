"""
Repositórios para operações de banco de dados das entidades agrícolas
Pattern: Repository - abstrai acesso aos dados
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional
from datetime import datetime

from app.models.database import (
    AgriFarmDB, AgriParcelDB, AgriCropDB,
    AgriParcelRecordDB, AgriParcelOperationDB, AgriFertilizeDB
)
from app.models.agri_models import (
    AgriFarmCreate, AgriFarmUpdate,
    AgriParcelCreate, AgriParcelUpdate,
    AgriCropCreate, AgriCropUpdate,
    AgriParcelRecordCreate,
    AgriParcelOperationCreate, AgriParcelOperationUpdate,
    AgriFertilizeCreate, AgriFertilizeUpdate
)


# ============================================================================
# AGRI FARM REPOSITORY
# ============================================================================

class AgriFarmRepository:
    """Repositório para operações com Fazendas"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def criar(self, farm: AgriFarmCreate) -> AgriFarmDB:
        """Cria uma nova fazenda"""
        db_farm = AgriFarmDB(**farm.model_dump())
        self.db.add(db_farm)
        self.db.commit()
        self.db.refresh(db_farm)
        return db_farm
    
    def buscar_por_id(self, farm_id: str) -> Optional[AgriFarmDB]:
        """Busca fazenda por ID"""
        return self.db.query(AgriFarmDB).filter(
            AgriFarmDB.farm_id == farm_id
        ).first()
    
    def listar_por_cliente(self, cliente_id: str, apenas_ativas: bool = True) -> List[AgriFarmDB]:
        """Lista todas as fazendas de um cliente"""
        query = self.db.query(AgriFarmDB).filter(
            AgriFarmDB.cliente_id == cliente_id
        )
        if apenas_ativas:
            query = query.filter(AgriFarmDB.ativo == True)
        return query.all()
    
    def atualizar(self, farm_id: str, farm_update: AgriFarmUpdate) -> Optional[AgriFarmDB]:
        """Atualiza uma fazenda"""
        db_farm = self.buscar_por_id(farm_id)
        if not db_farm:
            return None
        
        update_data = farm_update.model_dump(exclude_unset=True)
        for campo, valor in update_data.items():
            setattr(db_farm, campo, valor)
        
        db_farm.atualizado_em = datetime.utcnow()
        self.db.commit()
        self.db.refresh(db_farm)
        return db_farm
    
    def desativar(self, farm_id: str) -> bool:
        """Desativa uma fazenda (soft delete)"""
        db_farm = self.buscar_por_id(farm_id)
        if not db_farm:
            return False
        
        db_farm.ativo = False
        self.db.commit()
        return True
    
    def deletar(self, farm_id: str) -> bool:
        """Deleta permanentemente uma fazenda"""
        db_farm = self.buscar_por_id(farm_id)
        if not db_farm:
            return False
        
        self.db.delete(db_farm)
        self.db.commit()
        return True


# ============================================================================
# AGRI PARCEL REPOSITORY
# ============================================================================

class AgriParcelRepository:
    """Repositório para operações com Talhões"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def criar(self, parcel: AgriParcelCreate) -> AgriParcelDB:
        """Cria um novo talhão"""
        db_parcel = AgriParcelDB(**parcel.model_dump())
        self.db.add(db_parcel)
        self.db.commit()
        self.db.refresh(db_parcel)
        return db_parcel
    
    def buscar_por_id(self, parcel_id: str) -> Optional[AgriParcelDB]:
        """Busca talhão por ID"""
        return self.db.query(AgriParcelDB).filter(
            AgriParcelDB.parcel_id == parcel_id
        ).first()
    
    def listar_por_cliente(self, cliente_id: str, apenas_ativos: bool = True) -> List[AgriParcelDB]:
        """Lista todos os talhões de um cliente"""
        query = self.db.query(AgriParcelDB).filter(
            AgriParcelDB.cliente_id == cliente_id
        )
        if apenas_ativos:
            query = query.filter(AgriParcelDB.ativo == True)
        return query.all()
    
    def listar_por_fazenda(self, farm_id: str, apenas_ativos: bool = True) -> List[AgriParcelDB]:
        """Lista todos os talhões de uma fazenda"""
        query = self.db.query(AgriParcelDB).filter(
            AgriParcelDB.farm_id == farm_id
        )
        if apenas_ativos:
            query = query.filter(AgriParcelDB.ativo == True)
        return query.all()
    
    def atualizar(self, parcel_id: str, parcel_update: AgriParcelUpdate) -> Optional[AgriParcelDB]:
        """Atualiza um talhão"""
        db_parcel = self.buscar_por_id(parcel_id)
        if not db_parcel:
            return None
        
        update_data = parcel_update.model_dump(exclude_unset=True)
        for campo, valor in update_data.items():
            setattr(db_parcel, campo, valor)
        
        db_parcel.atualizado_em = datetime.utcnow()
        self.db.commit()
        self.db.refresh(db_parcel)
        return db_parcel
    
    def desativar(self, parcel_id: str) -> bool:
        """Desativa um talhão (soft delete)"""
        db_parcel = self.buscar_por_id(parcel_id)
        if not db_parcel:
            return False
        
        db_parcel.ativo = False
        self.db.commit()
        return True


# ============================================================================
# AGRI CROP REPOSITORY
# ============================================================================

class AgriCropRepository:
    """Repositório para operações com Culturas"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def criar(self, crop: AgriCropCreate) -> AgriCropDB:
        """Cria uma nova cultura"""
        db_crop = AgriCropDB(**crop.model_dump())
        self.db.add(db_crop)
        self.db.commit()
        self.db.refresh(db_crop)
        return db_crop
    
    def buscar_por_id(self, crop_id: str) -> Optional[AgriCropDB]:
        """Busca cultura por ID"""
        return self.db.query(AgriCropDB).filter(
            AgriCropDB.crop_id == crop_id
        ).first()
    
    def listar_todas(self) -> List[AgriCropDB]:
        """Lista todas as culturas cadastradas"""
        return self.db.query(AgriCropDB).all()
    
    def buscar_por_nome(self, nome: str) -> List[AgriCropDB]:
        """Busca culturas por nome (parcial)"""
        return self.db.query(AgriCropDB).filter(
            or_(
                AgriCropDB.name.ilike(f"%{nome}%"),
                AgriCropDB.alternate_name.ilike(f"%{nome}%")
            )
        ).all()
    
    def atualizar(self, crop_id: str, crop_update: AgriCropUpdate) -> Optional[AgriCropDB]:
        """Atualiza uma cultura"""
        db_crop = self.buscar_por_id(crop_id)
        if not db_crop:
            return None
        
        update_data = crop_update.model_dump(exclude_unset=True)
        for campo, valor in update_data.items():
            setattr(db_crop, campo, valor)
        
        db_crop.atualizado_em = datetime.utcnow()
        self.db.commit()
        self.db.refresh(db_crop)
        return db_crop
    
    def deletar(self, crop_id: str) -> bool:
        """Deleta uma cultura"""
        db_crop = self.buscar_por_id(crop_id)
        if not db_crop:
            return False
        
        self.db.delete(db_crop)
        self.db.commit()
        return True


# ============================================================================
# AGRI PARCEL RECORD REPOSITORY
# ============================================================================

class AgriParcelRecordRepository:
    """Repositório para Registros de Condições dos Talhões"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def criar(self, record: AgriParcelRecordCreate) -> AgriParcelRecordDB:
        """Cria um novo registro"""
        record_dict = record.model_dump()
        if record_dict.get('timestamp') is None:
            record_dict['timestamp'] = datetime.utcnow()
        
        db_record = AgriParcelRecordDB(**record_dict)
        self.db.add(db_record)
        self.db.commit()
        self.db.refresh(db_record)
        return db_record
    
    def buscar_por_id(self, record_id: str) -> Optional[AgriParcelRecordDB]:
        """Busca registro por ID"""
        return self.db.query(AgriParcelRecordDB).filter(
            AgriParcelRecordDB.record_id == record_id
        ).first()
    
    def buscar_ultimo_registro(self, parcel_id: str) -> Optional[AgriParcelRecordDB]:
        """Busca o último registro de um talhão"""
        return self.db.query(AgriParcelRecordDB).filter(
            AgriParcelRecordDB.parcel_id == parcel_id
        ).order_by(AgriParcelRecordDB.timestamp.desc()).first()
    
    def buscar_historico(
        self, 
        parcel_id: str, 
        limit: int = 100,
        offset: int = 0
    ) -> List[AgriParcelRecordDB]:
        """Busca histórico de registros de um talhão"""
        return self.db.query(AgriParcelRecordDB).filter(
            AgriParcelRecordDB.parcel_id == parcel_id
        ).order_by(
            AgriParcelRecordDB.timestamp.desc()
        ).limit(limit).offset(offset).all()
    
    def buscar_por_cliente(
        self, 
        cliente_id: str, 
        limit: int = 100
    ) -> List[AgriParcelRecordDB]:
        """Busca registros de todos os talhões de um cliente"""
        return self.db.query(AgriParcelRecordDB).filter(
            AgriParcelRecordDB.cliente_id == cliente_id
        ).order_by(
            AgriParcelRecordDB.timestamp.desc()
        ).limit(limit).all()


# ============================================================================
# AGRI PARCEL OPERATION REPOSITORY
# ============================================================================

class AgriParcelOperationRepository:
    """Repositório para Operações nos Talhões"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def criar(self, operation: AgriParcelOperationCreate) -> AgriParcelOperationDB:
        """Cria uma nova operação"""
        db_operation = AgriParcelOperationDB(**operation.model_dump())
        self.db.add(db_operation)
        self.db.commit()
        self.db.refresh(db_operation)
        return db_operation
    
    def buscar_por_id(self, operation_id: str) -> Optional[AgriParcelOperationDB]:
        """Busca operação por ID"""
        return self.db.query(AgriParcelOperationDB).filter(
            AgriParcelOperationDB.operation_id == operation_id
        ).first()
    
    def listar_por_talhao(
        self, 
        parcel_id: str, 
        status: Optional[str] = None
    ) -> List[AgriParcelOperationDB]:
        """Lista operações de um talhão"""
        query = self.db.query(AgriParcelOperationDB).filter(
            AgriParcelOperationDB.parcel_id == parcel_id
        )
        if status:
            query = query.filter(AgriParcelOperationDB.status == status)
        
        return query.order_by(
            AgriParcelOperationDB.planned_start.desc()
        ).all()
    
    def listar_por_cliente(
        self, 
        cliente_id: str,
        operation_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[AgriParcelOperationDB]:
        """Lista operações de um cliente"""
        query = self.db.query(AgriParcelOperationDB).filter(
            AgriParcelOperationDB.cliente_id == cliente_id
        )
        
        if operation_type:
            query = query.filter(AgriParcelOperationDB.operation_type == operation_type)
        if status:
            query = query.filter(AgriParcelOperationDB.status == status)
        
        return query.order_by(
            AgriParcelOperationDB.criado_em.desc()
        ).limit(limit).all()
    
    def atualizar(
        self, 
        operation_id: str, 
        operation_update: AgriParcelOperationUpdate
    ) -> Optional[AgriParcelOperationDB]:
        """Atualiza uma operação"""
        db_operation = self.buscar_por_id(operation_id)
        if not db_operation:
            return None
        
        update_data = operation_update.model_dump(exclude_unset=True)
        for campo, valor in update_data.items():
            setattr(db_operation, campo, valor)
        
        db_operation.atualizado_em = datetime.utcnow()
        self.db.commit()
        self.db.refresh(db_operation)
        return db_operation
    
    def iniciar_operacao(self, operation_id: str) -> Optional[AgriParcelOperationDB]:
        """Marca operação como iniciada"""
        db_operation = self.buscar_por_id(operation_id)
        if not db_operation:
            return None
        
        db_operation.status = "ongoing"
        db_operation.started_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(db_operation)
        return db_operation
    
    def finalizar_operacao(self, operation_id: str) -> Optional[AgriParcelOperationDB]:
        """Marca operação como finalizada"""
        db_operation = self.buscar_por_id(operation_id)
        if not db_operation:
            return None
        
        db_operation.status = "finished"
        db_operation.ended_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(db_operation)
        return db_operation


# ============================================================================
# AGRI FERTILIZE REPOSITORY
# ============================================================================

class AgriFertilizeRepository:
    """Repositório para Fertilizantes"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def criar(self, fertilize: AgriFertilizeCreate) -> AgriFertilizeDB:
        """Cria um novo registro de fertilizante"""
        db_fertilize = AgriFertilizeDB(**fertilize.model_dump())
        self.db.add(db_fertilize)
        self.db.commit()
        self.db.refresh(db_fertilize)
        return db_fertilize
    
    def buscar_por_id(self, fertilize_id: str) -> Optional[AgriFertilizeDB]:
        """Busca fertilizante por ID"""
        return self.db.query(AgriFertilizeDB).filter(
            AgriFertilizeDB.fertilize_id == fertilize_id
        ).first()
    
    def listar_por_cliente(self, cliente_id: str) -> List[AgriFertilizeDB]:
        """Lista todos os fertilizantes cadastrados por um cliente"""
        return self.db.query(AgriFertilizeDB).filter(
            AgriFertilizeDB.cliente_id == cliente_id
        ).all()
    
    def buscar_por_nome(self, cliente_id: str, nome: str) -> List[AgriFertilizeDB]:
        """Busca fertilizantes por nome"""
        return self.db.query(AgriFertilizeDB).filter(
            and_(
                AgriFertilizeDB.cliente_id == cliente_id,
                AgriFertilizeDB.product_name.ilike(f"%{nome}%")
            )
        ).all()
    
    def atualizar(
        self, 
        fertilize_id: str, 
        fertilize_update: AgriFertilizeUpdate
    ) -> Optional[AgriFertilizeDB]:
        """Atualiza um fertilizante"""
        db_fertilize = self.buscar_por_id(fertilize_id)
        if not db_fertilize:
            return None
        
        update_data = fertilize_update.model_dump(exclude_unset=True)
        for campo, valor in update_data.items():
            setattr(db_fertilize, campo, valor)
        
        db_fertilize.atualizado_em = datetime.utcnow()
        self.db.commit()
        self.db.refresh(db_fertilize)
        return db_fertilize
    
    def deletar(self, fertilize_id: str) -> bool:
        """Deleta um fertilizante"""
        db_fertilize = self.buscar_por_id(fertilize_id)
        if not db_fertilize:
            return False
        
        self.db.delete(db_fertilize)
        self.db.commit()
        return True
