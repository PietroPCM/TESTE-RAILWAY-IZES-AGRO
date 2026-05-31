"""
Redis cache opcional para performance.
"""

import json
import logging
from typing import Any, Optional

import redis

from app.config import settings

logger = logging.getLogger(__name__)


class RedisCache:
    """Cliente Redis singleton para cache."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            try:
                if settings.environment in {"development", "dev", "local", "test", "testing"}:
                    logger.info("Redis desabilitado no ambiente local.")
                    cls._instance.client = None
                    return cls._instance
                cls._instance.client = redis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    db=settings.redis_db,
                    password=settings.redis_password if settings.redis_password else None,
                    decode_responses=True,
                    socket_timeout=2,
                    socket_connect_timeout=2,
                    retry_on_timeout=True,
                )
                logger.info("Cliente Redis configurado")
            except Exception as exc:
                logger.warning("Redis nao disponivel: %s. Cache desabilitado.", exc)
                cls._instance.client = None
        return cls._instance

    def get(self, key: str) -> Optional[Any]:
        if not self.client:
            return None
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
        except Exception as exc:
            logger.error("Erro ao buscar cache %s: %s", key, exc)
        return None

    def set(self, key: str, value: Any, ttl: int = 300):
        if not self.client:
            return False
        try:
            self.client.setex(key, ttl, json.dumps(value, default=str))
            return True
        except Exception as exc:
            logger.error("Erro ao salvar cache %s: %s", key, exc)
            return False

    def delete(self, key: str):
        if not self.client:
            return False
        try:
            self.client.delete(key)
            return True
        except Exception as exc:
            logger.error("Erro ao deletar cache %s: %s", key, exc)
            return False

    def clear_pattern(self, pattern: str):
        if not self.client:
            return False
        try:
            keys = self.client.keys(pattern)
            if keys:
                self.client.delete(*keys)
            return True
        except Exception as exc:
            logger.error("Erro ao limpar pattern %s: %s", pattern, exc)
            return False


cache = RedisCache()
