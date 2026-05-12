"""
Custom Exceptions for AgriSoil Backend
Estrutura padronizada de erros para toda a aplicação
"""
from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class AgriSoilException(Exception):
    """Exceção base para todas as exceções da aplicação"""
    
    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(AgriSoilException):
    """Erro de autenticação"""
    
    def __init__(self, message: str = "Autenticação falhou", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details
        )


class AuthorizationError(AgriSoilException):
    """Erro de autorização"""
    
    def __init__(self, message: str = "Acesso negado", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=status.HTTP_403_FORBIDDEN,
            details=details
        )


class NotFoundError(AgriSoilException):
    """Recurso não encontrado"""
    
    def __init__(self, resource: str = "Recurso", details: Optional[Dict] = None):
        super().__init__(
            message=f"{resource} não encontrado",
            error_code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details
        )


class ValidationError(AgriSoilException):
    """Erro de validação de dados"""
    
    def __init__(self, message: str = "Dados inválidos", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details
        )


class ConflictError(AgriSoilException):
    """Conflito de recurso (já existe)"""
    
    def __init__(self, message: str = "Recurso já existe", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
            details=details
        )


class DatabaseError(AgriSoilException):
    """Erro de banco de dados"""
    
    def __init__(self, message: str = "Erro ao acessar banco de dados", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details
        )


class ExternalAPIError(AgriSoilException):
    """Erro ao chamar API externa"""
    
    def __init__(self, api_name: str, message: str = "Erro na API externa", details: Optional[Dict] = None):
        super().__init__(
            message=f"{api_name}: {message}",
            error_code="EXTERNAL_API_ERROR",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=details
        )


class RateLimitError(AgriSoilException):
    """Erro de rate limiting"""
    
    def __init__(self, message: str = "Muitas requisições", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details
        )


class ServiceUnavailableError(AgriSoilException):
    """Serviço indisponível"""
    
    def __init__(self, service: str = "Serviço", details: Optional[Dict] = None):
        super().__init__(
            message=f"{service} indisponível no momento",
            error_code="SERVICE_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details
        )


def agrisoil_exception_to_http_exception(exc: AgriSoilException) -> HTTPException:
    """Converter AgriSoilException para HTTPException"""
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details
        }
    )
