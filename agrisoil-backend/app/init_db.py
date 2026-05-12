"""
Script de inicialização e setup do banco de dados
"""

import logging
import sys
from sqlalchemy import text
from app.db import engine, SessionLocal, Base
from app.config import settings

logger = logging.getLogger(__name__)


def init_database():
    """
    Inicializar banco de dados:
    1. Criar todas as tabelas
    2. Criar índices
    3. Inserir dados iniciais (se necessário)
    """
    logger.info("Inicializando banco de dados...")
    
    try:
        # Importar modelos para registrar tabelas
        logger.info(" Importando modelos...")
        from app.models.database import SensorDB, LeituraDB, AlertaDB, UsuarioDB  # noqa: F401
        logger.info(f"Modelos importados. Tabelas: {list(Base.metadata.tables.keys())}")
        
        # Criar todas as tabelas
        logger.info(" Criando tabelas...")
        Base.metadata.create_all(bind=engine)
        logger.info(" Tabelas criadas com sucesso")
        
        # Executar SQL de inicialização se existir
        try:
            with engine.connect() as conn:
                # Criar extensões PostgreSQL necessárias
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS uuid-ossp"))
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
                conn.commit()
                logger.info(" Extensões PostgreSQL criadas")
        except Exception as e:
            logger.warning(f"Não foi possível criar extensões: {e}")
        
        logger.info(" Banco de dados inicializado com sucesso")
        return True
        
    except Exception as e:
        logger.error(f" Erro ao inicializar BD: {e}", exc_info=True)
        return False


def check_database_connection():
    """Verificar conexão com banco de dados"""
    logger.info("Verificando conexão com banco de dados...")
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info(" Conexão com BD estabelecida com sucesso")
            return True
    except Exception as e:
        logger.error(f" Erro ao conectar com BD: {e}", exc_info=True)
        return False


def migrate_database():
    """
    Executar migrações (usando Alembic)
    Este é um placeholder - instalar e configurar Alembic em produção
    """
    logger.info("Verificando migrações...")
    logger.warning(" Use Alembic para gerenciar migrações em produção")


if __name__ == "__main__":
    print("Inicializando AgriSoil Backend...")
    
    # Verificar conexão
    if not check_database_connection():
        print(" Não foi possível conectar ao banco de dados")
        sys.exit(1)
    
    # Inicializar BD
    if not init_database():
        print(" Erro ao inicializar banco de dados")
        sys.exit(1)
    
    # Rodar migrações
    migrate_database()
    
    print(" Backend pronto para produção!")
