"""
Script para adicionar coluna 'role' na tabela de usuários
e criar usuários de teste com diferentes roles

Execute: python -m scripts.add_role_column
"""

import asyncio
import sys
from pathlib import Path

# Adicionar o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.db import engine, SessionLocal
from app.models.database import UsuarioDB
from app.security import hash_password
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def add_role_column():
    """Adicionar coluna role se não existir"""
    try:
        async with engine.begin() as conn:
            # Verificar se coluna já existe
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='usuarios' AND column_name='role'
            """))
            
            if result.fetchone():
                logger.info("✅ Coluna 'role' já existe")
            else:
                # Adicionar coluna
                await conn.execute(text("""
                    ALTER TABLE usuarios 
                    ADD COLUMN role VARCHAR(50) NOT NULL DEFAULT 'viewer'
                """))
                logger.info("✅ Coluna 'role' adicionada com sucesso")
                
                # Atualizar usuários existentes
                await conn.execute(text("""
                    UPDATE usuarios 
                    SET role = CASE 
                        WHEN email LIKE '%admin%' THEN 'admin'
                        ELSE 'viewer'
                    END
                    WHERE role = 'viewer'
                """))
                logger.info("✅ Roles padrão atribuídas aos usuários existentes")
                
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar coluna: {e}")
        raise


def create_test_users():
    """Criar usuários de teste com diferentes roles"""
    db = SessionLocal()
    
    test_users = [
        {
            "user_id": "admin001",
            "email": "admin@agrisoil.com",
            "nome": "Administrador Sistema",
            "senha": "admin123",
            "cliente_id": "agrisoil",
            "role": "admin"
        },
        {
            "user_id": "gestor001",
            "email": "gestor@agrisoil.com",
            "nome": "Gestor Regional",
            "senha": "gestor123",
            "cliente_id": "regiao_sul",
            "role": "gestor"
        },
        {
            "user_id": "produtor001",
            "email": "joao@fazenda.com",
            "nome": "João Silva",
            "senha": "produtor123",
            "cliente_id": "fazenda_boa_vista",
            "role": "produtor"
        },
        {
            "user_id": "tecnico001",
            "email": "maria@agro.com",
            "nome": "Maria Santos",
            "senha": "tecnico123",
            "cliente_id": "agronomia_tech",
            "role": "tecnico"
        },
        {
            "user_id": "viewer001",
            "email": "viewer@agrisoil.com",
            "nome": "Visualizador",
            "senha": "viewer123",
            "cliente_id": "consulta",
            "role": "viewer"
        }
    ]
    
    try:
        for user_data in test_users:
            # Verificar se já existe
            existing = db.query(UsuarioDB).filter(
                UsuarioDB.email == user_data["email"]
            ).first()
            
            if existing:
                # Atualizar role se necessário
                if hasattr(existing, 'role') and existing.role != user_data["role"]:
                    existing.role = user_data["role"]
                    db.commit()
                    logger.info(f"♻️  Usuário atualizado: {user_data['email']} (role: {user_data['role']})")
                else:
                    logger.info(f"⏭️  Usuário já existe: {user_data['email']}")
                continue
            
            # Criar novo usuário
            new_user = UsuarioDB(
                user_id=user_data["user_id"],
                email=user_data["email"],
                nome=user_data["nome"],
                senha_hash=hash_password(user_data["senha"]),
                cliente_id=user_data["cliente_id"],
                role=user_data["role"],
                ativo=True
            )
            
            db.add(new_user)
            db.commit()
            logger.info(f"✅ Usuário criado: {user_data['email']} (role: {user_data['role']})")
        
        logger.info("\n" + "="*60)
        logger.info("🎉 USUÁRIOS DE TESTE CRIADOS COM SUCESSO!")
        logger.info("="*60)
        logger.info("\n📋 CREDENCIAIS PARA LOGIN:\n")
        for user in test_users:
            logger.info(f"🔑 {user['role'].upper().ljust(10)} | {user['email'].ljust(25)} | {user['senha']}")
        logger.info("\n" + "="*60)
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erro ao criar usuários: {e}")
        raise
    finally:
        db.close()


async def main():
    """Executar migrações"""
    logger.info("🚀 Iniciando migração...")
    
    # 1. Adicionar coluna role
    await add_role_column()
    
    # 2. Criar usuários de teste
    create_test_users()
    
    logger.info("✅ Migração concluída!")


if __name__ == "__main__":
    asyncio.run(main())
