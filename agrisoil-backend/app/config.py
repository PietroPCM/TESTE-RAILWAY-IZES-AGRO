"""
Configurações de ambiente para a aplicação
Usando Pydantic Settings para validação e type safety
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import List, Union
import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(BASE_DIR, ".env")

# Carregar .env com fallback de encoding para evitar erros em Windows
# IMPORTANTE: Não sobrescrever variáveis já definidas pelo ambiente (docker-compose)
try:
    load_dotenv(dotenv_path=ENV_FILE, override=False)
except UnicodeDecodeError:
    # Fallback para arquivos salvos em Latin-1/Windows-1252
    load_dotenv(dotenv_path=ENV_FILE, override=False, encoding="latin-1")


class Settings(BaseSettings):
    """Configurações da aplicação - Production Ready"""
    
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        case_sensitive=False,
        extra="ignore"
    )
    
    # Banco de dados
    database_url: str = Field(default="")
    database_pool_size: int = 20
    database_max_overflow: int = 40
    database_pool_timeout: int = 30
    database_pool_recycle: int = 3600
    
    # Segurança
    secret_key: str = Field(default="change-me-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    access_token_expire_minutes: int = 30
    
    # OpenAI / ChatGPT
    openai_api_key: str = Field(default="")
    openai_model: str = "gpt-4-turbo"
    openai_temperature: float = 0.7
    openai_max_tokens: int = 2000
    
    # Ambiente
    environment: str = Field(default="development")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    
    # Cache
    cache_ttl_dashboard: int = 600  # 10 minutos
    cache_ttl_context: int = 300    # 5 minutos

    # Clima
    clima_provedor: str = Field(default="openweathermap")
    openweathermap_api_key: str = Field(default="")
    weatherapi_api_key: str = Field(default="")
    cache_clima_minutos: int = 10
    alerta_temp_min: float = -2.0
    alerta_temp_max: float = 35.0
    alerta_umidade_min: int = 25
    alerta_umidade_max: int = 90
    alerta_chuva_limite_mm: float = 20.0
    webhook_timeout_segundos: int = 5
    max_tentativas_webhook: int = 3
    
    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 60
    
    # CORS
    cors_origins: Union[str, List[str]] = Field(default="http://localhost:3000,http://localhost:8080")
    cors_credentials: bool = True
    cors_methods: Union[str, List[str]] = Field(default="GET,POST,PUT,DELETE,OPTIONS")
    cors_headers: Union[str, List[str]] = Field(default="Content-Type,Authorization")
    
    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v
    
    @field_validator('cors_methods', mode='before')
    @classmethod
    def parse_cors_methods(cls, v):
        if isinstance(v, str):
            return [method.strip() for method in v.split(',')]
        return v
    
    @field_validator('cors_headers', mode='before')
    @classmethod
    def parse_cors_headers(cls, v):
        if isinstance(v, str):
            return [header.strip() for header in v.split(',')]
        return v
    
    # Monitoring
    sentry_dsn: str = Field(default="")
    prometheus_enabled: bool = True
    
    # Redis
    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379)
    redis_db: int = Field(default=0)
    redis_password: str = Field(default="")
    
    # Celery
    celery_broker_url: str = Field(default="redis://localhost:6379/1")
    celery_result_backend: str = Field(default="redis://localhost:6379/2")
    
    # Firebase
    firebase_credentials_path: str = Field(default="firebase-credentials.json")
    
    # Sensor API Key
    sensor_api_key: str = Field(default="dev_sensor_api_key")
    
    # HTTPS
    force_https: bool = Field(default=False, validation_alias="FORCE_HTTPS")


settings = Settings()
