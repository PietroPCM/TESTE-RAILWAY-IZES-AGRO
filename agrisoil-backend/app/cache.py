"""
Redis Cache para performance
10x mais rápido no dashboard
"""

import redis
from typing import Optional, Any
import json
import logging
from app.config import settings

logger = logging.getLogger(__name__)


class RedisCache:
    """Cliente Redis singleton para cache"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            try:
                cls._instance.client = redis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    db=settings.redis_db,
                    password=settings.redis_password if settings.redis_password else None,
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True,
                )
                # Testar conexão
                cls._instance.client.ping()
                logger.info(" Redis conectado com sucesso")
            except Exception as e:
                logger.warning(f" Redis não disponível: {e}. Cache desabilitado.")
                cls._instance.client = None
        return cls._instance
    
    def get(self, key: str) -> Optional[Any]:
        """Buscar valor do cache"""
        if not self.client:
            return None
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.error(f" Erro ao buscar cache {key}: {e}")
        return None
    
    def set(self, key: str, value: Any, ttl: int = 300):
        """Salvar no cache com TTL em segundos"""
        if not self.client:
            return False
        try:
            self.client.setex(
                key,
                ttl,
                json.dumps(value, default=str)
            )
            return True
        except Exception as e:
            logger.error(f" Erro ao salvar cache {key}: {e}")
            return False
    
    def delete(self, key: str):
        """Remover do cache"""
        if not self.client:
            return False
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f" Erro ao deletar cache {key}: {e}")
            return False
    
    def clear_pattern(self, pattern: str):
        """Limpar todas as keys que correspondem ao pattern"""
        if not self.client:
            return False
        try:
            keys = self.client.keys(pattern)
            if keys:
                self.client.delete(*keys)
            return True
        except Exception as e:
            logger.error(f" Erro ao limpar pattern {pattern}: {e}")
            return False


# Instância global
cache = RedisCache()
