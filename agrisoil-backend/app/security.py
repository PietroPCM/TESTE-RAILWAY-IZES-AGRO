"""
Segurança: JWT, Hashing e Autenticação
Production-ready com PyJWT e bcrypt
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
import bcrypt
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

logger = logging.getLogger(__name__)
security = HTTPBearer()


def hash_password(password: str) -> str:
    """Hash de senha usando bcrypt"""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verificar senha contra hash"""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Criar JWT token
    
    Args:
        data: Dados a codificar (ex: {"sub": "usuario_id"})
        expires_delta: Tempo de expiração customizado
    
    Returns:
        Token JWT assinado
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )
    
    to_encode.update({"exp": expire})
    
    try:
        encoded_jwt = jwt.encode(
            to_encode,
            settings.secret_key,
            algorithm=settings.jwt_algorithm
        )
        return encoded_jwt
    except Exception as e:
        logger.error(f"Erro ao criar token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao gerar token"
        )


def decode_access_token(token: str) -> dict:
    """
    Decodificar e validar JWT token
    
    Args:
        token: Token JWT
    
    Returns:
        Dados decodificados
    
    Raises:
        HTTPException: Se token inválido ou expirado
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token expirado")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        logger.warning("Token inválido")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Erro ao decodificar token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao processar token"
        )


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Dependency: Obter usuário atual do JWT
    
    Uso:
        @app.get("/me")
        async def get_profile(user_id: str = Depends(get_current_user)):
            return {"user_id": user_id}
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    user_id: str = payload.get("sub")
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sem identificação de usuário"
        )
    
    return user_id


# Alias em PT-BR para compatibilidade com rotas existentes
async def obter_usuario_atual(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Alias de `get_current_user`.
    Mantido para compatibilidade com rotas antigas.
    """
    return await get_current_user(credentials)


async def get_current_app_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Dependency: Validar token de aplicação móvel
    Simples validação - em produção, verificar contra BD
    """
    token = credentials.credentials
    
    if not token.startswith("app_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de aplicação inválido"
        )
    
    return token


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Dependency: Verificar token JWT e retornar ID do cliente
    
    Uso:
        @app.get("/api/alertas")
        async def listar_alertas(cliente: str = Depends(verify_token)):
            # cliente contém o user_id extraído do token
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    
    cliente_id: str = payload.get("sub")
    if cliente_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sem identificação de cliente"
        )
    
    return cliente_id


async def verificar_admin(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Dependency: Verificar se usuário é admin

    Critérios aceitos no JWT:
    - role: "admin"
    - is_admin: True (retrocompatibilidade)
    - email == "admin@agrisoil.com" (fallback)
    
    Returns:
        dict: Payload do token com dados do usuário
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    email = (payload.get("email") or "").lower()
    role = (payload.get("role") or "").lower()
    is_admin = bool(payload.get("is_admin") or payload.get("admin"))

    # Verificar role
    if role == "admin":
        is_admin = True

    # Fallback para email específico
    if email == "admin@agrisoil.com":
        is_admin = True

    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores"
        )

    return payload


async def verificar_gestor_ou_superior(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Dependency: Verificar se usuário é gestor, admin ou superior
    
    Permite: admin, gestor
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    role = (payload.get("role") or "").lower()
    
    roles_permitidas = {"admin", "gestor"}
    
    if role not in roles_permitidas:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Acesso restrito. Requer role: {', '.join(roles_permitidas)}"
        )
    
    return payload


async def verificar_produtor_ou_superior(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Dependency: Verificar se usuário é produtor, gestor, admin ou superior
    
    Permite: admin, gestor, produtor
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    role = (payload.get("role") or "").lower()
    
    roles_permitidas = {"admin", "gestor", "produtor"}
    
    if role not in roles_permitidas:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Acesso restrito. Requer role: {', '.join(roles_permitidas)}"
        )
    
    return payload


def require_role(*allowed_roles: str):
    """
    Decorator factory: Criar dependency customizada para verificar roles específicas
    
    Uso:
        @app.post("/api/config")
        async def configurar(user = Depends(require_role("admin", "gestor"))):
            return {"msg": "Configurado"}
    
    Args:
        *allowed_roles: Roles permitidas (ex: "admin", "gestor")
    
    Returns:
        Dependency function que valida role
    """
    async def verificar_role(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
        token = credentials.credentials
        payload = decode_access_token(token)
        role = (payload.get("role") or "").lower()
        
        # Normalizar roles permitidas
        roles_normalizadas = {r.lower() for r in allowed_roles}
        
        if role not in roles_normalizadas:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado. Role '{role}' não autorizada. Requer: {', '.join(roles_normalizadas)}"
            )
        
        return payload
    
    return verificar_role
