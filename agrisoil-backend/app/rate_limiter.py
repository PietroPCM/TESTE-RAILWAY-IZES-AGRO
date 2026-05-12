"""
Rate Limiting refinado por tipo de endpoint
Diferentes limites para diferentes operações
"""
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from functools import wraps


class EndpointRateLimiter:
    """Rate limiter customizado por tipo de endpoint"""
    
    def __init__(self):
        self.limiter = Limiter(key_func=get_remote_address)
    
    # Limites padrão (por minuto)
    LIMITS = {
        # Health checks - sem limite
        'health': '10000/minute',  # Praticamente ilimitado
        
        # Leitura de dados - limite alto
        'read': '300/minute',  # 5 por segundo
        
        # Escrita/Atualização - limite médio
        'write': '60/minute',   # 1 por segundo
        
        # Deleção - limite baixo
        'delete': '20/minute',  # 1 a cada 3 segundos
        
        # Autenticação - limite muito baixo (anti-brute force)
        'auth': '5/minute',     # 1 a cada 12 segundos
        
        # Upload de arquivos - limite baixo
        'upload': '10/minute',  # 1 a cada 6 segundos
        
        # APIs externas - limite conservador
        'external': '30/minute', # 1 a cada 2 segundos
    }
    
    def get_limit(self, endpoint_type: str) -> str:
        """Retorna limite para tipo de endpoint"""
        return self.LIMITS.get(endpoint_type, self.LIMITS['read'])


# Instância global
rate_limiter = EndpointRateLimiter()


# Decoradores para uso fácil em rotas
def rate_limit_health(f):
    """Rate limit para health checks"""
    @wraps(f)
    async def wrapped(*args, **kwargs):
        return await f(*args, **kwargs)
    return wrapped


def rate_limit_read(f):
    """Rate limit para leitura (GET)"""
    @wraps(f)
    async def wrapped(*args, **kwargs):
        return await f(*args, **kwargs)
    return wrapped


def rate_limit_write(f):
    """Rate limit para escrita (POST, PUT)"""
    @wraps(f)
    async def wrapped(*args, **kwargs):
        return await f(*args, **kwargs)
    return wrapped


def rate_limit_delete(f):
    """Rate limit para deleção (DELETE)"""
    @wraps(f)
    async def wrapped(*args, **kwargs):
        return await f(*args, **kwargs)
    return wrapped


def rate_limit_auth(f):
    """Rate limit para autenticação (anti-brute force)"""
    @wraps(f)
    async def wrapped(*args, **kwargs):
        return await f(*args, **kwargs)
    return wrapped


def rate_limit_upload(f):
    """Rate limit para upload de arquivos"""
    @wraps(f)
    async def wrapped(*args, **kwargs):
        return await f(*args, **kwargs)
    return wrapped


def rate_limit_external(f):
    """Rate limit para chamadas a APIs externas"""
    @wraps(f)
    async def wrapped(*args, **kwargs):
        return await f(*args, **kwargs)
    return wrapped
