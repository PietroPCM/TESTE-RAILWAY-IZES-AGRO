"""
Endpoints para gerenciamento de tokens FCM (Firebase Cloud Messaging)
Permite apps móveis registrarem/removerem tokens para receber push notifications
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import logging

from app.db import get_db
from app.models.database import UsuarioDB
from app.services.push_notification_service import PushNotificationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fcm", tags=["Push Notifications"])


class FCMTokenRequest(BaseModel):
    """Request para registrar/remover token FCM"""
    cliente_id: str
    token: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "cliente_id": "CLIENTE001",
                "token": "eXyZ...abc123"  # Token gerado pelo Firebase no app
            }
        }


class FCMTestRequest(BaseModel):
    """Request para testar envio de push"""
    token: str


@router.post("/register", summary="Registrar token FCM do dispositivo")
async def registrar_token_fcm(
    request: FCMTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Registra token FCM de um dispositivo para receber push notifications
    
    **Como funciona:**
    1. App mobile obtém token FCM do Firebase ao iniciar
    2. Após login, app envia token para este endpoint
    3. Backend armazena token associado ao cliente
    4. Quando houver alerta, backend envia push via FCM para todos os tokens
    
    **Múltiplos dispositivos:**
    - Um cliente pode ter vários tokens (celular, tablet, etc)
    - Tokens são armazenados em lista JSON no banco
    - Push é enviado para todos os dispositivos simultaneamente
    """
    try:
        # Buscar usuário
        usuario = db.query(UsuarioDB).filter(
            UsuarioDB.cliente_id == request.cliente_id
        ).first()
        
        if not usuario:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")
        
        # Inicializar lista de tokens se não existir
        if not usuario.fcm_tokens:
            usuario.fcm_tokens = []
        
        # Adicionar token se não existir
        if request.token not in usuario.fcm_tokens:
            usuario.fcm_tokens.append(request.token)
            db.commit()
            logger.info(f"✅ Token FCM registrado para cliente {request.cliente_id}")
        else:
            logger.info(f"ℹ️  Token FCM já existe para cliente {request.cliente_id}")
        
        return {
            "sucesso": True,
            "mensagem": "Token FCM registrado com sucesso",
            "total_dispositivos": len(usuario.fcm_tokens),
            "push_habilitado": PushNotificationService.is_enabled()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao registrar token FCM: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/unregister", summary="Remover token FCM do dispositivo")
async def remover_token_fcm(
    request: FCMTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Remove token FCM de um dispositivo (logout ou desinstalação do app)
    
    **Quando usar:**
    - Ao fazer logout do app
    - Ao desinstalar o app
    - Quando o token expirar/for inválido
    """
    try:
        # Buscar usuário
        usuario = db.query(UsuarioDB).filter(
            UsuarioDB.cliente_id == request.cliente_id
        ).first()
        
        if not usuario:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")
        
        # Remover token se existir
        if usuario.fcm_tokens and request.token in usuario.fcm_tokens:
            usuario.fcm_tokens.remove(request.token)
            db.commit()
            logger.info(f"✅ Token FCM removido para cliente {request.cliente_id}")
            removido = True
        else:
            logger.info(f"ℹ️  Token FCM não encontrado para cliente {request.cliente_id}")
            removido = False
        
        return {
            "sucesso": True,
            "mensagem": "Token FCM removido" if removido else "Token não encontrado",
            "total_dispositivos": len(usuario.fcm_tokens or [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao remover token FCM: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{cliente_id}", summary="Status das notificações push")
async def status_push(
    cliente_id: str,
    db: Session = Depends(get_db)
):
    """
    Verifica status das notificações push para um cliente
    
    Retorna:
    - Quantos dispositivos estão registrados
    - Se push está habilitado no servidor
    - Preferências de notificação
    """
    try:
        # Buscar usuário
        usuario = db.query(UsuarioDB).filter(
            UsuarioDB.cliente_id == cliente_id
        ).first()
        
        if not usuario:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")
        
        prefs = usuario.preferencias_notificacao or {}
        
        return {
            "cliente_id": cliente_id,
            "total_dispositivos": len(usuario.fcm_tokens or []),
            "push_habilitado_servidor": PushNotificationService.is_enabled(),
            "push_habilitado_cliente": prefs.get('push_ativo', True),
            "tokens": [f"{t[:10]}...{t[-10:]}" for t in (usuario.fcm_tokens or [])]  # Mascarado por segurança
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao verificar status push: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test", summary="Testar envio de push notification")
async def testar_push(request: FCMTestRequest):
    """
    Envia notificação de teste para um token FCM específico
    
    **Útil para:**
    - Validar que o token está correto
    - Testar se push notifications estão funcionando
    - Debug durante desenvolvimento
    """
    if not PushNotificationService.is_enabled():
        raise HTTPException(
            status_code=503,
            detail="Push notifications não habilitadas. Configure FIREBASE_CREDENTIALS_PATH"
        )
    
    try:
        sucesso = await PushNotificationService.enviar_teste(request.token)
        
        if sucesso:
            return {
                "sucesso": True,
                "mensagem": "Push notification de teste enviada com sucesso! Verifique o dispositivo."
            }
        else:
            return {
                "sucesso": False,
                "mensagem": "Falha ao enviar push. Token pode estar inválido ou app desinstalado."
            }
            
    except Exception as e:
        logger.error(f"❌ Erro ao testar push: {e}")
        raise HTTPException(status_code=500, detail=str(e))
