"""
Modelo de Usuário para Autenticação e Autorização
"""
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class UserRole(str, Enum):
    """Roles de usuário no sistema"""
    ADMIN = "admin"  # Acesso total, pode editar bibliotecas e configurações
    GESTOR = "gestor"  # Gerencia múltiplas fazendas/clientes
    PRODUTOR = "produtor"  # Gerencia sua propriedade
    TECNICO = "tecnico"  # Consulta e relatórios
    VIEWER = "viewer"  # Apenas visualização


class UserBase(BaseModel):
    """Base para usuário"""
    email: str
    nome: str
    cliente_id: str
    role: UserRole = Field(default=UserRole.VIEWER, description="Nível de permissão")


class UserCreate(UserBase):
    """Criar novo usuário"""
    password: str
    role: UserRole = Field(default=UserRole.VIEWER, description="Apenas admin pode definir roles")


class UserLogin(BaseModel):
    """Login de usuário"""
    email: str
    password: str


class UserInDB(UserBase):
    """Usuário no banco de dados"""
    id: str
    hashed_password: str
    ativo: bool = True
    role: UserRole = UserRole.VIEWER


class UserResponse(UserBase):
    """Resposta de usuário (sem senha)"""
    id: str
    ativo: bool
    role: UserRole


class TokenResponse(BaseModel):
    """Resposta de token JWT"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400  # 24 horas
    user: UserResponse
