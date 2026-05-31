"""
Rotas de Clientes
Gestao de clientes (empresas agricolas, agropecuarias)
"""

from datetime import datetime, timedelta
import logging
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, model_serializer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.database import (
    AgriFarmDB,
    AgriParcelDB,
    AlertaDB,
    ClienteDB,
    FaseAtualDB,
    SensorDB,
    SeveridadeAlerta,
    StatusAlerta,
    ZonaManejoDB,
)
from app.security import obter_usuario_atual, verificar_admin
from app.utils.datetime_utils import utc_iso

router = APIRouter(prefix="/api/clientes", tags=["Clientes"])
logger = logging.getLogger(__name__)


class ClienteCreate(BaseModel):
    """Dados para criar novo cliente."""

    nome: str
    email: EmailStr
    telefone: Optional[str] = None
    cnpj: Optional[str] = None
    endereco: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    responsavel_nome: str
    responsavel_email: EmailStr
    responsavel_telefone: Optional[str] = None
    observacoes: Optional[str] = None

    class Config:
        from_attributes = True


class ClienteUpdate(BaseModel):
    """Dados para atualizar cliente."""

    nome: Optional[str] = None
    email: Optional[EmailStr] = None
    telefone: Optional[str] = None
    endereco: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    responsavel_nome: Optional[str] = None
    responsavel_email: Optional[EmailStr] = None
    responsavel_telefone: Optional[str] = None
    observacoes: Optional[str] = None

    class Config:
        from_attributes = True


class ClienteResponse(BaseModel):
    """Resposta ao retornar cliente."""

    id: str
    nome: str
    email: str
    telefone: Optional[str]
    cnpj: Optional[str]
    endereco: Optional[str]
    cidade: Optional[str]
    estado: Optional[str]
    responsavel_nome: str
    responsavel_email: str
    responsavel_telefone: Optional[str]
    ativo: bool
    data_criacao: datetime
    data_atualizacao: Optional[datetime]
    total_propriedades: int
    total_zonas: int
    total_sensores: int

    class Config:
        from_attributes = True

    @model_serializer(mode="wrap")
    def serialize_model(self, handler):
        return {
            **handler(self),
            "data_criacao": utc_iso(self.data_criacao),
            "data_atualizacao": utc_iso(self.data_atualizacao),
        }


def _usuario_cliente_id(usuario) -> Optional[str]:
    if isinstance(usuario, dict):
        return usuario.get("cliente_id") or usuario.get("sub") or usuario.get("user_id")
    if isinstance(usuario, str):
        return usuario
    return getattr(usuario, "cliente_id", None)


def _usuario_eh_admin(usuario) -> bool:
    if isinstance(usuario, dict):
        return bool(usuario.get("eh_admin") or usuario.get("is_admin") or usuario.get("role") == "admin")
    return bool(getattr(usuario, "eh_admin", False) or getattr(usuario, "role", None) == "admin")


def _pode_acessar_cliente(usuario, cliente_id: str) -> bool:
    usuario_cliente_id = _usuario_cliente_id(usuario)
    return _usuario_eh_admin(usuario) or usuario_cliente_id in (None, cliente_id)


def _normalizar_cnpj(cnpj: Optional[str]) -> Optional[str]:
    if not cnpj:
        return None
    cnpj_limpo = "".join(ch for ch in cnpj if ch.isdigit())
    if len(cnpj_limpo) != 14:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CNPJ invalido")
    return cnpj_limpo


def _cliente_response(db: Session, cliente: ClienteDB) -> ClienteResponse:
    total_propriedades = db.query(AgriFarmDB).filter(
        AgriFarmDB.cliente_id == cliente.cliente_id,
        AgriFarmDB.ativo.is_(True),
    ).count()
    total_zonas = db.query(ZonaManejoDB).filter(
        ZonaManejoDB.cliente_id == cliente.cliente_id,
        ZonaManejoDB.ativo.is_(True),
    ).count()
    total_sensores = db.query(SensorDB).filter(
        SensorDB.cliente_id == cliente.cliente_id,
        SensorDB.ativo.is_(True),
    ).count()

    return ClienteResponse(
        id=cliente.cliente_id,
        nome=cliente.nome,
        email=cliente.email,
        telefone=cliente.telefone,
        cnpj=cliente.cnpj,
        endereco=cliente.endereco,
        cidade=cliente.cidade,
        estado=cliente.estado,
        responsavel_nome=cliente.responsavel_nome,
        responsavel_email=cliente.responsavel_email,
        responsavel_telefone=cliente.responsavel_telefone,
        ativo=cliente.ativo,
        data_criacao=cliente.data_criacao,
        data_atualizacao=cliente.data_atualizacao,
        total_propriedades=total_propriedades,
        total_zonas=total_zonas,
        total_sensores=total_sensores,
    )


def _obter_cliente_ou_404(db: Session, cliente_id: str) -> ClienteDB:
    cliente = db.query(ClienteDB).filter(ClienteDB.cliente_id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente nao encontrado")
    return cliente


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ClienteResponse)
async def criar_cliente(
    cliente_data: ClienteCreate,
    usuario=Depends(obter_usuario_atual),
    _admin=Depends(verificar_admin),
    db: Session = Depends(get_db),
):
    """Criar novo cliente. A criacao de usuario principal fica para o modulo de login."""
    cnpj = _normalizar_cnpj(cliente_data.cnpj)

    if db.query(ClienteDB).filter(ClienteDB.email == cliente_data.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email ja cadastrado")
    if cnpj and db.query(ClienteDB).filter(ClienteDB.cnpj == cnpj).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CNPJ ja cadastrado")

    cliente = ClienteDB(
        cliente_id=f"cliente_{uuid4().hex[:12]}",
        nome=cliente_data.nome,
        email=str(cliente_data.email),
        telefone=cliente_data.telefone,
        cnpj=cnpj,
        endereco=cliente_data.endereco,
        cidade=cliente_data.cidade,
        estado=cliente_data.estado,
        responsavel_nome=cliente_data.responsavel_nome,
        responsavel_email=str(cliente_data.responsavel_email),
        responsavel_telefone=cliente_data.responsavel_telefone,
        observacoes=cliente_data.observacoes,
        ativo=True,
    )
    db.add(cliente)
    db.commit()
    db.refresh(cliente)

    logger.info("Cliente criado: %s por %s", cliente.cliente_id, usuario)
    return _cliente_response(db, cliente)


@router.get("/{cliente_id}", response_model=ClienteResponse)
async def obter_cliente(
    cliente_id: str,
    usuario=Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Obter detalhes de um cliente."""
    if not _pode_acessar_cliente(usuario, cliente_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para acessar este cliente")

    return _cliente_response(db, _obter_cliente_ou_404(db, cliente_id))


@router.get("", response_model=dict)
async def listar_clientes(
    ativo: Optional[bool] = None,
    pagina: int = 1,
    por_pagina: int = 10,
    usuario=Depends(obter_usuario_atual),
    _admin=Depends(verificar_admin),
    db: Session = Depends(get_db),
):
    """Listar clientes com paginacao."""
    if pagina < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="pagina deve ser maior que zero")

    por_pagina = max(1, min(por_pagina, 100))
    query = db.query(ClienteDB)
    if ativo is not None:
        query = query.filter(ClienteDB.ativo == ativo)

    total = query.count()
    clientes = query.order_by(ClienteDB.data_criacao.desc()).offset((pagina - 1) * por_pagina).limit(por_pagina).all()

    return {
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "clientes": [_cliente_response(db, cliente).model_dump() for cliente in clientes],
    }


@router.put("/{cliente_id}", response_model=ClienteResponse)
async def atualizar_cliente(
    cliente_id: str,
    cliente_data: ClienteUpdate,
    usuario=Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Atualizar dados do cliente."""
    if not _pode_acessar_cliente(usuario, cliente_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao para atualizar este cliente")

    cliente = _obter_cliente_ou_404(db, cliente_id)
    payload = cliente_data.model_dump(exclude_unset=True)

    if "email" in payload:
        email_existente = db.query(ClienteDB).filter(
            ClienteDB.email == str(payload["email"]),
            ClienteDB.cliente_id != cliente_id,
        ).first()
        if email_existente:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email ja cadastrado")
        payload["email"] = str(payload["email"])

    if "responsavel_email" in payload:
        payload["responsavel_email"] = str(payload["responsavel_email"])

    for field, value in payload.items():
        setattr(cliente, field, value)
    cliente.data_atualizacao = datetime.utcnow()
    db.commit()
    db.refresh(cliente)

    logger.info("Cliente atualizado: %s por %s", cliente_id, usuario)
    return _cliente_response(db, cliente)


@router.delete("/{cliente_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_cliente(
    cliente_id: str,
    usuario=Depends(obter_usuario_atual),
    _admin=Depends(verificar_admin),
    db: Session = Depends(get_db),
):
    """Soft delete de cliente para preservar historico."""
    cliente = _obter_cliente_ou_404(db, cliente_id)
    cliente.ativo = False
    cliente.data_atualizacao = datetime.utcnow()
    db.commit()

    logger.info("Cliente desativado: %s por %s", cliente_id, usuario)


@router.get("/{cliente_id}/resumo", response_model=dict)
async def obter_resumo_cliente(
    cliente_id: str,
    usuario=Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Obter resumo operacional real do cliente."""
    if not _pode_acessar_cliente(usuario, cliente_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissao")

    cliente = _obter_cliente_ou_404(db, cliente_id)
    sete_dias_atras = datetime.utcnow() - timedelta(days=7)

    propriedades = db.query(AgriFarmDB).filter(AgriFarmDB.cliente_id == cliente_id, AgriFarmDB.ativo.is_(True)).all()
    total_zonas = db.query(ZonaManejoDB).filter(ZonaManejoDB.cliente_id == cliente_id, ZonaManejoDB.ativo.is_(True)).count()
    zonas_com_plantio = db.query(FaseAtualDB.zona_id).join(
        ZonaManejoDB,
        FaseAtualDB.zona_id == ZonaManejoDB.zona_id,
    ).filter(ZonaManejoDB.cliente_id == cliente_id, ZonaManejoDB.ativo.is_(True)).distinct().count()
    sensores_total = db.query(SensorDB).filter(SensorDB.cliente_id == cliente_id).count()
    sensores_funcionando = db.query(SensorDB).filter(SensorDB.cliente_id == cliente_id, SensorDB.ativo.is_(True)).count()
    alertas_query = db.query(AlertaDB).filter(AlertaDB.cliente_id == cliente_id, AlertaDB.criado_em >= sete_dias_atras)
    total_alertas = alertas_query.count()
    alertas_ativos = alertas_query.filter(AlertaDB.status == StatusAlerta.ATIVO).count()
    alertas_resolvidos = alertas_query.filter(AlertaDB.status == StatusAlerta.RESOLVIDO).count()
    alertas_reconhecidos = alertas_query.filter(AlertaDB.status == StatusAlerta.RECONHECIDO).count()
    criticos = alertas_query.filter(AlertaDB.severidade == SeveridadeAlerta.CRITICO).count()
    percentual_saude = 100 if sensores_total == 0 else round((sensores_funcionando / sensores_total) * 100)

    return {
        "cliente_id": cliente_id,
        "nome_cliente": cliente.nome,
        "propriedades": {
            "total": len(propriedades),
            "nomes": [prop.name for prop in propriedades],
        },
        "zonas_manejo": {
            "total": total_zonas,
            "com_plantio": zonas_com_plantio,
            "sem_plantio": max(total_zonas - zonas_com_plantio, 0),
        },
        "sensores": {
            "total": sensores_total,
            "funcionando": sensores_funcionando,
            "com_problema": max(sensores_total - sensores_funcionando, 0),
            "bateria_baixa": 0,
        },
        "alertas_ultimos_7_dias": {
            "total": total_alertas,
            "novo": alertas_ativos,
            "reconhecido": alertas_reconhecidos,
            "resolvido": alertas_resolvidos,
            "criticos": criticos,
        },
        "saude_sistema": {
            "status": "bom" if percentual_saude >= 90 else "atencao",
            "percentual": percentual_saude,
            "ultima_verificacao": utc_iso(datetime.utcnow()),
        },
    }
