"""
Database configuration e session management
Production-ready com SQLAlchemy 2.0
"""

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import logging
from app.config import settings

logger = logging.getLogger(__name__)


class DatabaseUrlConfigurationError(RuntimeError):
    """Erro seguro para DATABASE_URL ausente, inválida ou não resolvida."""


def _normalize_database_url(url: str) -> str:
    """Normalize Railway/Supabase Postgres URLs for SQLAlchemy + psycopg v3."""
    database_url = (url or "").strip()
    if not database_url:
        raise DatabaseUrlConfigurationError(
            "DATABASE_URL não configurada. Defina a variável de ambiente antes de iniciar o backend."
        )

    if "${" in database_url or "{{" in database_url or "}}" in database_url:
        raise DatabaseUrlConfigurationError(
            "DATABASE_URL inválida: a referência de variável não foi resolvida. "
            "No Railway, configure DATABASE_URL referenciando a variável do serviço PostgreSQL."
        )

    if database_url.startswith("postgres://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix("postgres://")
    elif database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix("postgresql://")
    elif database_url.startswith("postgresql+psycopg2://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix("postgresql+psycopg2://")

    supported_prefixes = ("postgresql+psycopg://", "sqlite://")
    if not database_url.startswith(supported_prefixes):
        raise DatabaseUrlConfigurationError(
            "DATABASE_URL inválida. Use uma URL PostgreSQL válida iniciando com "
            "postgresql://, postgres:// ou postgresql+psycopg://."
        )

    try:
        make_url(database_url)
    except ArgumentError as exc:
        raise DatabaseUrlConfigurationError(
            "DATABASE_URL inválida ou mal formatada. Verifique a variável de ambiente sem expor o valor."
        ) from exc

    return database_url


def _get_database_url() -> str:
    return _normalize_database_url(settings.database_url)


database_url = _get_database_url()

# Base class para todos os modelos
Base = declarative_base()

# Criar engine com pool de conexões otimizado para produção
# SQLite requer configuração diferente de PostgreSQL
if database_url.startswith("sqlite"):
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},  # Necessário para SQLite
        echo=settings.debug,  # Log SQL em debug mode
    )
else:
    engine = create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
        pool_recycle=settings.database_pool_recycle,
        pool_pre_ping=True,  # Verifica se conexão está viva antes de usar
        echo=settings.debug,  # Log SQL em debug mode
    )

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Evento: Configurar conexão (apenas para PostgreSQL)"""
    # PostgreSQL usa autocommit por padrão com SQLAlchemy
    # Remover configuração manual que causa erro
    pass


def get_db():
    """
    Dependency injection para obter sessão de BD
    Uso: @app.get("/") def get_data(db: Session = Depends(get_db))
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Erro em transação BD: {e}")
        db.rollback()
        raise
    finally:
        db.close()


async def init_db():
    """Inicializar banco de dados sob chamada explícita."""
    try:
        # Importar modelos para registrar tabelas no metadata
        logger.info("Carregando metadata SQLAlchemy para inicialização explícita do banco.")
        
        from app.models.database import SensorDB, LeituraDB, AlertaDB, UsuarioDB  # noqa: F401
        logger.info("Modelos importados. Total: %s tabelas", len(Base.metadata.tables))
        
        logger.info("Executando create_all() por configuração explícita.")
        Base.metadata.create_all(bind=engine)
        
        logger.info("Banco de dados inicializado com sucesso")
    except Exception as e:
        logger.error("Erro ao inicializar BD: %s", type(e).__name__, exc_info=True)
        raise


async def close_db():
    """Fechar pool de conexões"""
    engine.dispose()
    logger.info(" Pool de conexões fechado")
