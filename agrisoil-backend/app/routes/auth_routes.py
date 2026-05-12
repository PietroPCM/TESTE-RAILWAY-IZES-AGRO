"""
Rotas de Autenticação
Endpoints para login, registro e validação de tokens
"""
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict
from sqlalchemy.orm import Session

from ..models.user import UserLogin, TokenResponse, UserResponse, UserCreate
from ..models.database import UsuarioDB
from ..db import get_db
from ..security import (
    verify_password,
    hash_password,
    create_access_token,
    decode_access_token
)
from ..config import settings
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Autenticação"])
security = HTTPBearer()


@router.post("/login", response_model=TokenResponse, summary="Login de usuário")
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Login com email e senha
    
    Retorna JWT token para usar nos endpoints protegidos
    """
    logger.info(f"🔐 Tentativa de login: {credentials.email}")
    
    # Buscar usuário no banco de dados
    user = db.query(UsuarioDB).filter(UsuarioDB.email == credentials.email).first()
    
    if not user:
        logger.warning(f"❌ Usuário não encontrado: {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos"
        )
    
    # Verificar senha
    if not verify_password(credentials.password, user.senha_hash):
        logger.warning(f"❌ Senha incorreta para: {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos"
        )
    
    # Verificar se usuário está ativo
    if not user.ativo:
        logger.warning(f"❌ Usuário inativo: {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário desativado"
        )
    
    # Criar token JWT
    token_data = {
        "sub": user.user_id,
        "email": user.email,
        "nome": user.nome,
        "cliente_id": user.cliente_id,
        "role": user.role if hasattr(user, 'role') else "viewer"  # Retrocompatibilidade
    }
    access_token = create_access_token(token_data)
    
    logger.info(f"✅ Login bem-sucedido: {credentials.email}")
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserResponse(
            id=user.user_id,
            email=user.email,
            nome=user.nome,
            cliente_id=user.cliente_id,
            ativo=user.ativo,
            role=getattr(user, 'role', 'viewer') or 'viewer'  # Garante que sempre retorna role
        )
    )


@router.post("/register", response_model=UserResponse, summary="Registrar novo usuário")
async def register(user: UserCreate, db: Session = Depends(get_db)):
    """
    Registrar novo usuário
    
    **Nota:** Em produção, adicionar validações e salvar no banco
    """
    logger.info(f"📝 Registro de novo usuário: {user.email}")
    
    # Verificar se email já existe no banco
    existing = db.query(UsuarioDB).filter(UsuarioDB.email == user.email).first()
    if existing:
        logger.warning(f"❌ Email já cadastrado: {user.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já cadastrado"
        )
    
    # Hash da senha
    hashed_password = hash_password(user.password)
    
    # Criar novo usuário no banco de dados
    new_user = UsuarioDB(
        user_id=f"user_{uuid4().hex[:8]}",
        email=user.email,
        nome=user.nome,
        senha_hash=hashed_password,
        cliente_id=user.cliente_id,
        role=user.role.value if hasattr(user, 'role') else "viewer",
        ativo=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(f"✅ Usuário registrado: {user.email}")

    return UserResponse(
        id=new_user.user_id,
        email=new_user.email,
        nome=new_user.nome,
        cliente_id=new_user.cliente_id,
        ativo=new_user.ativo,
        role=new_user.role
    )


@router.get("/me", response_model=UserResponse, summary="Obter usuário atual")
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """
    Retorna informações do usuário autenticado
    
    **Requer:** Token JWT no header `Authorization: Bearer <token>`
    """
    try:
        # Decodificar token
        token = credentials.credentials
        payload = decode_access_token(token)
        
        email = payload.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido"
            )
        # Buscar usuário no banco
        user = db.query(UsuarioDB).filter(UsuarioDB.email == email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado"
            )

        return UserResponse(
            id=user.user_id,
            email=user.email,
            nome=user.nome,
            cliente_id=user.cliente_id,
            ativo=user.ativo,
            role=getattr(user, 'role', 'viewer') or 'viewer'
        )
        
    except Exception as e:
        logger.error(f"❌ Erro ao validar token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado"
        )


@router.post("/validate", summary="Validar token")
async def validate_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Valida se o token JWT é válido
    
    **Requer:** Token JWT no header `Authorization: Bearer <token>`
    """
    try:
        token = credentials.credentials
        payload = decode_access_token(token)
        
        return {
            "valid": True,
            "user_id": payload.get("sub"),
            "email": payload.get("email"),
            "cliente_id": payload.get("cliente_id")
        }
        
    except Exception as e:
        logger.error(f"❌ Token inválido: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado"
        )
