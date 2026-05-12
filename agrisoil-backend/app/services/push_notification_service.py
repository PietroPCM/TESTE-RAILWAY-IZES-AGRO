"""
Serviço de Push Notifications via Firebase Cloud Messaging (FCM)

Envia notificações push para aplicativos mobile quando há novos alertas.
Funciona mesmo com o app fechado/em background.
"""

import firebase_admin
from firebase_admin import credentials, messaging
from typing import Optional, List, Dict, Any
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class PushNotificationService:
    """Gerencia envio de push notifications via FCM"""
    
    _initialized = False
    _enabled = False
    
    @classmethod
    def initialize(cls, service_account_path: Optional[str] = None):
        """
        Inicializa Firebase Admin SDK
        
        Args:
            service_account_path: Caminho para arquivo JSON das credenciais Firebase
                                 Se None, procura em FIREBASE_CREDENTIALS_PATH env var
        """
        if cls._initialized:
            return
            
        try:
            import os
            
            # Procurar credenciais
            credentials_path = service_account_path or os.getenv('FIREBASE_CREDENTIALS_PATH')
            
            if not credentials_path or not Path(credentials_path).exists():
                logger.warning(
                    "🔕 Firebase credentials não encontradas. "
                    "Push notifications desabilitadas. "
                    "Configure FIREBASE_CREDENTIALS_PATH para habilitar."
                )
                cls._enabled = False
                cls._initialized = True
                return
            
            # Inicializar Firebase
            cred = credentials.Certificate(credentials_path)
            firebase_admin.initialize_app(cred)
            
            cls._enabled = True
            cls._initialized = True
            logger.info("✅ Firebase Cloud Messaging inicializado com sucesso")
            
        except ImportError:
            logger.warning(
                "⚠️  Pacote 'firebase-admin' não instalado. "
                "Execute: pip install firebase-admin"
            )
            cls._enabled = False
            cls._initialized = True
            
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar Firebase: {e}")
            cls._enabled = False
            cls._initialized = True
    
    @classmethod
    def is_enabled(cls) -> bool:
        """Retorna se push notifications estão habilitadas"""
        if not cls._initialized:
            cls.initialize()
        return cls._enabled
    
    @classmethod
    async def enviar_alerta_push(
        cls,
        device_token: str,
        alerta: Dict[str, Any],
        cliente_nome: str = "Cliente",
        sensor_localizacao: str = "Área"
    ) -> bool:
        """
        Envia push notification de alerta para um dispositivo
        
        Args:
            device_token: Token FCM do dispositivo (obtido no login do app)
            alerta: Dicionário com dados do alerta (id, tipo, severidade, mensagem, etc)
            cliente_nome: Nome do cliente para exibir
            sensor_localizacao: Localização do sensor
            
        Returns:
            True se enviado com sucesso, False caso contrário
        """
        if not cls.is_enabled():
            logger.warning("Push notifications desabilitadas, ignorando envio")
            return False
        
        try:
            # Definir título e ícone baseado na severidade
            severidade = alerta.get('severidade', 'baixo')
            tipo = alerta.get('tipo', 'SENSOR')
            
            emoji_map = {
                'critico': '🔴',
                'alto': '🟠',
                'medio': '🟡',
                'baixo': '🔵'
            }
            
            titulo = f"{emoji_map.get(severidade, '⚠️')} Alerta {severidade.upper()}: {tipo}"
            
            # Criar notificação
            notification = messaging.Notification(
                title=titulo,
                body=alerta.get('mensagem', 'Verifique o sensor')
            )
            
            # Dados adicionais (payload)
            data = {
                'alerta_id': str(alerta.get('id', '')),
                'tipo': tipo,
                'severidade': severidade,
                'sensor_id': str(alerta.get('sensor_id', '')),
                'sensor_localizacao': sensor_localizacao,
                'cliente': cliente_nome,
                'mensagem': alerta.get('mensagem', ''),
                'recomendacao': alerta.get('recomendacao', ''),
                'timestamp': alerta.get('data_criacao', ''),
                'click_action': 'FLUTTER_NOTIFICATION_CLICK',
                'route': '/notifications'  # Abrir tela de notificações
            }
            
            # Configuração Android
            android_config = messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    icon='ic_notification',
                    color='#2E7D32',  # Verde AgriSoil
                    sound='default',
                    channel_id='alertas_agrisoil'
                )
            )
            
            # Configuração iOS
            apns_config = messaging.APNSConfig(
                headers={'apns-priority': '10'},
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        alert=messaging.ApsAlert(
                            title=titulo,
                            body=alerta.get('mensagem', '')
                        ),
                        badge=1,
                        sound='default'
                    )
                )
            )
            
            # Criar mensagem
            message = messaging.Message(
                notification=notification,
                data=data,
                token=device_token,
                android=android_config,
                apns=apns_config
            )
            
            # Enviar
            response = messaging.send(message)
            logger.info(f"✅ Push enviado com sucesso: {response}")
            return True
            
        except messaging.UnregisteredError:
            logger.warning(f"⚠️  Token inválido ou app desinstalado: {device_token[:20]}...")
            return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar push: {e}")
            return False
    
    @classmethod
    async def enviar_alerta_push_multiplo(
        cls,
        device_tokens: List[str],
        alerta: Dict[str, Any],
        cliente_nome: str = "Cliente",
        sensor_localizacao: str = "Área"
    ) -> Dict[str, int]:
        """
        Envia push notification para múltiplos dispositivos
        
        Args:
            device_tokens: Lista de tokens FCM
            alerta: Dados do alerta
            cliente_nome: Nome do cliente
            sensor_localizacao: Localização do sensor
            
        Returns:
            {'sucesso': int, 'falhas': int}
        """
        if not cls.is_enabled() or not device_tokens:
            return {'sucesso': 0, 'falhas': 0}
        
        resultados = {'sucesso': 0, 'falhas': 0}
        
        for token in device_tokens:
            sucesso = await cls.enviar_alerta_push(
                token, alerta, cliente_nome, sensor_localizacao
            )
            if sucesso:
                resultados['sucesso'] += 1
            else:
                resultados['falhas'] += 1
        
        logger.info(
            f"📤 Push múltiplo: {resultados['sucesso']} enviados, "
            f"{resultados['falhas']} falharam"
        )
        
        return resultados
    
    @classmethod
    async def enviar_teste(cls, device_token: str) -> bool:
        """Envia notificação de teste"""
        alerta_teste = {
            'id': 'teste-001',
            'tipo': 'TESTE',
            'severidade': 'baixo',
            'mensagem': 'Notificação de teste do AgriSoil',
            'recomendacao': 'Sistema funcionando corretamente!',
            'sensor_id': 'TEST001',
            'data_criacao': '2026-01-22T10:00:00'
        }
        
        return await cls.enviar_alerta_push(
            device_token,
            alerta_teste,
            "Cliente Teste",
            "Área de Testes"
        )


# Inicializar automaticamente ao importar
PushNotificationService.initialize()
