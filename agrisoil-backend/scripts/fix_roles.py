"""
Script para corrigir roles de usuários
Preenche role para todos os usuários que estão NULL/vazio

Execute: python -m scripts.fix_roles
"""

import sys
from pathlib import Path

# Adicionar o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import SessionLocal
from app.models.database import UsuarioDB
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fix_user_roles():
    """Corrigir roles de usuários existentes"""
    db = SessionLocal()
    
    try:
        logger.info("🔍 Buscando usuários sem role...")
        
        # Buscar todos os usuários
        usuarios = db.query(UsuarioDB).all()
        
        if not usuarios:
            logger.warning("⚠️  Nenhum usuário encontrado no banco de dados")
            db.close()
            return
        
        logger.info(f"📊 Total de usuários: {len(usuarios)}")
        
        # Atualizar role para todos que estão vazio/NULL
        updated_count = 0
        for usuario in usuarios:
            current_role = getattr(usuario, 'role', None)
            
            # Se role está vazio ou NULL, preenche com "viewer"
            if not current_role or current_role == '':
                usuario.role = 'viewer'
                updated_count += 1
                logger.info(f"  ✓ {usuario.email} → role: 'viewer'")
        
        if updated_count > 0:
            db.commit()
            logger.info(f"\n✅ {updated_count} usuários atualizados com sucesso!")
        else:
            logger.info("\n✅ Todos os usuários já têm role definido!")
        
        # Mostrar todos os usuários com seus roles
        logger.info("\n📋 Usuários atuais:\n")
        usuarios_atualizados = db.query(UsuarioDB).all()
        for usuario in usuarios_atualizados:
            role = getattr(usuario, 'role', 'N/A')
            logger.info(f"  • {usuario.email.ljust(35)} | role: {role}")
        
        db.close()
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erro ao atualizar roles: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("🚀 Iniciando correção de roles...\n")
    fix_user_roles()
    logger.info("\n✅ Pronto! Reinicie a API para ver as mudanças no Swagger.")
