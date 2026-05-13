"""
Database configuration e session management
Production-ready com SQLAlchemy 2.0
"""

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import logging
from app.config import settings

logger = logging.getLogger(__name__)
database_url = "postgresql+psycopg://postgres:123123@localhost:5432/agrisoil"
print("DB DRIVER: psycopg v3")

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
    """Inicializar banco de dados (criar todas as tabelas)"""
    try:
        # Importar modelos para registrar tabelas no metadata
        logger.info(f" Tabelas antes do import: {list(Base.metadata.tables.keys())}")
        
        from app.models.database import SensorDB, LeituraDB, AlertaDB, UsuarioDB  # noqa: F401
        logger.info(f" Modelos importados. Total: {len(Base.metadata.tables)} tabelas")
        
        logger.info(" Executando create_all()...")
        Base.metadata.create_all(bind=engine)
        
        logger.info(" Banco de dados inicializado com sucesso")
    except Exception as e:
        logger.error(f" Erro ao inicializar BD: {type(e).__name__}: {e}", exc_info=True)
        raise


async def close_db():
    """Fechar pool de conexões"""
    engine.dispose()
    logger.info(" Pool de conexões fechado")
