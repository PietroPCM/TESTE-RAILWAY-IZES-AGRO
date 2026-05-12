"""
Rotas de Clientes
Gestão de clientes (empresas agrícolas, agropecuárias)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
import logging

from app.db import get_db
from app.security import obter_usuario_atual, verificar_admin

router = APIRouter(prefix="/api/clientes", tags=["Clientes"])
logger = logging.getLogger(__name__)


# ============================================================================
# MODELS
# ============================================================================

class ClienteCreate(BaseModel):
    """Dados para criar novo cliente"""
    nome: str
    email: str
    telefone: Optional[str] = None
    cnpj: Optional[str] = None
    endereco: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    responsavel_nome: str
    responsavel_email: str
    responsavel_telefone: Optional[str] = None
    observacoes: Optional[str] = None
    
    class Config:
        from_attributes = True


class ClienteUpdate(BaseModel):
    """Dados para atualizar cliente"""
    nome: Optional[str] = None
    email: Optional[str] = None
    telefone: Optional[str] = None
    endereco: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    responsavel_nome: Optional[str] = None
    responsavel_email: Optional[str] = None
    responsavel_telefone: Optional[str] = None
    observacoes: Optional[str] = None
    
    class Config:
        from_attributes = True


class ClienteResponse(BaseModel):
    """Resposta ao retornar cliente"""
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


# ============================================================================
# CRIAR NOVO CLIENTE (ADMIN ONLY)
# ============================================================================

@router.post("", status_code=status.HTTP_201_CREATED, response_model=ClienteResponse)
async def criar_cliente(
    cliente_data: ClienteCreate,
    usuario = Depends(obter_usuario_atual),
    _admin = Depends(verificar_admin),
    db: Session = Depends(get_db)
):
    """
    Criar novo cliente (SÓ ADMIN)
    
    Isso também cria o usuário principal (responsável) do cliente
    com permissões de gerenciar propriedades, zonas e sensores
    """
    try:
        # Validar CNPJ se fornecido
        if cliente_data.cnpj:
            cnpj_limpo = cliente_data.cnpj.replace(".", "").replace("/", "").replace("-", "")
            if len(cnpj_limpo) != 14:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="CNPJ inválido"
                )
        
        # TODO: Verificar se email já existe
        # cliente_existente = db.query(Cliente)\
        #     .filter(Cliente.email == cliente_data.email)\
        #     .first()
        # if cliente_existente:
        #     raise HTTPException(...)
        
        # TODO: Criar novo cliente no banco
        # novo_cliente = Cliente(
        #     nome=cliente_data.nome,
        #     email=cliente_data.email,
        #     telefone=cliente_data.telefone,
        #     cnpj=cliente_data.cnpj,
        #     endereco=cliente_data.endereco,
        #     cidade=cliente_data.cidade,
        #     estado=cliente_data.estado,
        #     responsavel_nome=cliente_data.responsavel_nome,
        #     responsavel_email=cliente_data.responsavel_email,
        #     responsavel_telefone=cliente_data.responsavel_telefone,
        #     ativo=True,
        #     data_criacao=datetime.now()
        # )
        # db.add(novo_cliente)
        # db.commit()
        # db.refresh(novo_cliente)
        
        # TODO: Criar usuário principal (responsável) com email=responsavel_email
        # usuario_principal = Usuario(
        #     email=cliente_data.responsavel_email,
        #     nome=cliente_data.responsavel_nome,
        #     senha_hash=gerar_hash_padrao(),
        #     cliente_id=novo_cliente.id,
        #     role="cliente_admin",
        #     ativo=True
        # )
        # db.add(usuario_principal)
        # db.commit()
        
        # Enviar email de boas-vindas com instruções de login
        # TODO: send_welcome_email(cliente_data.responsavel_email, cliente_data.responsavel_nome)
        
        logger.info(f"Cliente criado: {cliente_data.nome} por {usuario}")
        
        return ClienteResponse(
            id="cliente_001",
            nome=cliente_data.nome,
            email=cliente_data.email,
            telefone=cliente_data.telefone,
            cnpj=cliente_data.cnpj,
            endereco=cliente_data.endereco,
            cidade=cliente_data.cidade,
            estado=cliente_data.estado,
            responsavel_nome=cliente_data.responsavel_nome,
            responsavel_email=cliente_data.responsavel_email,
            responsavel_telefone=cliente_data.responsavel_telefone,
            ativo=True,
            data_criacao=datetime.now(),
            data_atualizacao=None,
            total_propriedades=0,
            total_zonas=0,
            total_sensores=0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar cliente: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao criar cliente"
        )


# ============================================================================
# OBTER CLIENTE (POR ID OU PRÓPRIO)
# ============================================================================

@router.get("/{cliente_id}", response_model=ClienteResponse)
async def obter_cliente(
    cliente_id: str,
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Obter detalhes de um cliente
    
    - Clientes podem ver só suas próprias informações
    - Admin pode ver qualquer cliente
    """
    try:
        # Validação de permissão
        if cliente_id != usuario.cliente_id and not usuario.eh_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sem permissão para acessar este cliente"
            )
        
        # TODO: Query no banco
        # cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
        # if not cliente:
        #     raise HTTPException(...)
        
        # Mock
        return ClienteResponse(
            id=cliente_id,
            nome="Fazenda Santa Clara",
            email="contato@santaclara.com.br",
            telefone="(11) 98765-4321",
            cnpj="12.345.678/0001-90",
            endereco="Rodovia SP-310, km 150",
            cidade="Ribeirão Preto",
            estado="SP",
            responsavel_nome="João da Silva",
            responsavel_email="joao@santaclara.com.br",
            responsavel_telefone="(11) 98765-4321",
            ativo=True,
            data_criacao=datetime(2025, 1, 15),
            data_atualizacao=datetime(2025, 10, 1),
            total_propriedades=3,
            total_zonas=12,
            total_sensores=48
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter cliente: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter cliente"
        )


# ============================================================================
# LISTAR CLIENTES (ADMIN ONLY)
# ============================================================================

@router.get("", response_model=dict)
async def listar_clientes(
    ativo: Optional[bool] = None,
    pagina: int = 1,
    por_pagina: int = 10,
    usuario = Depends(obter_usuario_atual),
    _admin = Depends(verificar_admin),
    db: Session = Depends(get_db)
):
    """
    Listar todos os clientes (SÓ ADMIN)
    """
    try:
        # TODO: Query com paginação
        # total = db.query(Cliente).count()
        # clientes = db.query(Cliente)\
        #     .offset((pagina-1)*por_pagina)\
        #     .limit(por_pagina)\
        #     .all()
        
        clientes = [
            {
                "id": "cliente_001",
                "nome": "Fazenda Santa Clara",
                "email": "contato@santaclara.com.br",
                "cidade": "Ribeirão Preto",
                "estado": "SP",
                "ativo": True,
                "total_propriedades": 3,
                "total_sensores": 48
            },
            {
                "id": "cliente_002",
                "nome": "Agropecuária Brasil",
                "email": "contato@agrobrasil.com.br",
                "cidade": "Goiás",
                "estado": "GO",
                "ativo": True,
                "total_propriedades": 2,
                "total_sensores": 24
            }
        ]
        
        return {
            "total": 2,
            "pagina": pagina,
            "por_pagina": por_pagina,
            "clientes": clientes
        }
        
    except Exception as e:
        logger.error(f"Erro ao listar clientes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao listar clientes"
        )


# ============================================================================
# ATUALIZAR CLIENTE
# ============================================================================

@router.put("/{cliente_id}", response_model=ClienteResponse)
async def atualizar_cliente(
    cliente_id: str,
    cliente_data: ClienteUpdate,
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Atualizar dados do cliente
    
    - Clientes podem atualizar só suas próprias informações
    - Admin pode atualizar qualquer cliente
    """
    try:
        # Validação de permissão
        if cliente_id != usuario.cliente_id and not usuario.eh_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sem permissão para atualizar este cliente"
            )
        
        # TODO: Query e update no banco
        # cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
        # if not cliente:
        #     raise HTTPException(...)
        
        # for field, value in cliente_data.dict(exclude_unset=True).items():
        #     setattr(cliente, field, value)
        # cliente.data_atualizacao = datetime.now()
        # db.commit()
        # db.refresh(cliente)
        
        logger.info(f"Cliente atualizado: {cliente_id} por {usuario}")
        
        return ClienteResponse(
            id=cliente_id,
            nome=cliente_data.nome or "Fazenda Santa Clara",
            email=cliente_data.email or "contato@santaclara.com.br",
            telefone=cliente_data.telefone,
            cnpj=None,
            endereco=cliente_data.endereco,
            cidade=cliente_data.cidade,
            estado=cliente_data.estado,
            responsavel_nome=cliente_data.responsavel_nome or "João da Silva",
            responsavel_email=cliente_data.responsavel_email or "joao@santaclara.com.br",
            responsavel_telefone=cliente_data.responsavel_telefone,
            ativo=True,
            data_criacao=datetime(2025, 1, 15),
            data_atualizacao=datetime.now(),
            total_propriedades=3,
            total_zonas=12,
            total_sensores=48
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar cliente: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar cliente"
        )


# ============================================================================
# DELETAR CLIENTE (SOFT DELETE - ADMIN ONLY)
# ============================================================================

@router.delete("/{cliente_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_cliente(
    cliente_id: str,
    usuario = Depends(obter_usuario_atual),
    _admin = Depends(verificar_admin),
    db: Session = Depends(get_db)
):
    """
    Deletar cliente (SOFT DELETE - marca como inativo)
    
    Preserva histórico e dados para auditoria
    """
    try:
        # TODO: Update com ativo=False
        # cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
        # if not cliente:
        #     raise HTTPException(...)
        # cliente.ativo = False
        # db.commit()
        
        logger.info(f"Cliente deletado (soft): {cliente_id} por {usuario}")
        
    except Exception as e:
        logger.error(f"Erro ao deletar cliente: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao deletar cliente"
        )


# ============================================================================
# OBTER RESUMO DO CLIENTE
# ============================================================================

@router.get("/{cliente_id}/resumo", response_model=dict)
async def obter_resumo_cliente(
    cliente_id: str,
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Obter resumo de estatísticas do cliente
    
    - Total de propriedades
    - Total de sensores
    - Alertas nos últimos 7 dias
    - Saúde geral do sistema
    """
    try:
        if cliente_id != usuario.cliente_id and not usuario.eh_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sem permissão"
            )
        
        return {
            "cliente_id": cliente_id,
            "nome_cliente": "Fazenda Santa Clara",
            "propriedades": {
                "total": 3,
                "nomes": ["Santa Clara - Sede", "Santa Clara - Extensão", "Experimental"]
            },
            "zonas_manejo": {
                "total": 12,
                "com_plantio": 8,
                "sem_plantio": 4
            },
            "sensores": {
                "total": 48,
                "funcionando": 46,
                "com_problema": 2,
                "bateria_baixa": 0
            },
            "alertas_ultimos_7_dias": {
                "total": 15,
                "novo": 3,
                "reconhecido": 5,
                "resolvido": 7,
                "criticos": 1
            },
            "saude_sistema": {
                "status": "bom",
                "percentual": 95,
                "ultima_verificacao": datetime.now()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter resumo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter resumo"
        )
