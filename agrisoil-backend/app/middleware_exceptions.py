"""
Middleware para tratamento de exceções global
Fornece respostas estruturadas e logging consistente
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging
from datetime import datetime
from typing import Union

from app.exceptions import AgriSoilException, RateLimitError

logger = logging.getLogger("agrisoil")


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handler global para todas as exceções não capturadas
    """
    logger.error(
        f"Unhandled exception: {type(exc).__name__}",
        exc_info=exc,
        extra={
            "method": request.method,
            "path": request.url.path,
            "client": request.client.host if request.client else "unknown"
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "Erro interno do servidor",
            "timestamp": datetime.utcnow().isoformat(),
            "path": request.url.path,
        }
    )


async def agrisoil_exception_handler(request: Request, exc: AgriSoilException) -> JSONResponse:
    """
    Handler para AgriSoilException
    """
    log_level = logging.WARNING if exc.status_code >= 500 else logging.INFO
    logger.log(
        log_level,
        f"{exc.error_code}: {exc.message}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "client": request.client.host if request.client else "unknown",
            "error_code": exc.error_code,
            "status_code": exc.status_code,
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
            "timestamp": datetime.utcnow().isoformat(),
            "path": request.url.path,
        }
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handler para erros de validação Pydantic
    """
    errors = []
    for error in exc.errors():
        field = ".".join(str(x) for x in error["loc"][1:])  # Pula "body"
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"]
        })
    
    logger.warning(
        f"Validation error on {request.method} {request.url.path}",
        extra={
            "errors": errors,
            "client": request.client.host if request.client else "unknown"
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": "Erro de validação dos dados",
            "errors": errors,
            "timestamp": datetime.utcnow().isoformat(),
            "path": request.url.path,
        }
    )


async def rate_limit_handler(request: Request, exc: RateLimitError) -> JSONResponse:
    """
    Handler para erros de rate limiting
    """
    logger.warning(
        f"Rate limit exceeded: {request.method} {request.url.path}",
        extra={
            "client": request.client.host if request.client else "unknown"
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error_code": "RATE_LIMIT_EXCEEDED",
            "message": "Muitas requisições. Tente novamente mais tarde.",
            "timestamp": datetime.utcnow().isoformat(),
            "path": request.url.path,
        }
    )
