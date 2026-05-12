"""
Logging estruturado para produção
JSON logging para observability
"""

import logging
import logging.config
import json
from pythonjsonlogger import jsonlogger
from app.config import settings
import os

# Criar diretório de logs se não existir
os.makedirs("logs", exist_ok=True)

# Configuração de logging
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
        },
        "detailed": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s() - %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": settings.log_level,
            "formatter": "default",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": settings.log_level,
            "formatter": "json",
            "filename": "logs/agrisoil.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 10,
        },
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "ERROR",
            "formatter": "json",
            "filename": "logs/agrisoil_errors.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 10,
        }
    },
    "root": {
        "level": settings.log_level,
        "handlers": ["console", "file", "error_file"]
    },
    "loggers": {
        "uvicorn": {
            "level": settings.log_level,
            "handlers": ["console", "file"]
        },
        "uvicorn.access": {
            "level": "INFO",
            "handlers": ["console", "file"]
        },
        "sqlalchemy": {
            "level": "WARNING",
            "handlers": ["console", "file"]
        }
    }
}


def setup_logging():
    """Configurar logging estruturado"""
    logging.config.dictConfig(LOGGING_CONFIG)
    logger = logging.getLogger(__name__)
    logger.info(f"🔧 Logging iniciado - Environment: {settings.environment}")
    return logger


logger = setup_logging()
