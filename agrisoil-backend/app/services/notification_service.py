"""
Serviço de notificações por e-mail e push com retry logic
Envia alertas para usuários configurados com resiliência
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
import firebase_admin
from firebase_admin import credentials, messaging
import os

from app.models.database import AlertaDB, UsuarioDB, SensorDB, SeveridadeAlerta, StatusAlerta
from app.config import settings

logger = logging.getLogger(__name__)

# Inicializar Firebase com retry
firebase_app = None
try:
    if os.path.exists(settings.firebase_credentials_path):
        cred = credentials.Certificate(settings.firebase_credentials_path)
        firebase_app = firebase_admin.initialize_app(cred)
        logger.info("✅ Firebase inicializado com sucesso")
    else:
        logger.warning(f"⚠️ Firebase credentials não encontrado: {settings.firebase_credentials_path}")
except Exception as e:
    logger.warning(f"⚠️ Firebase não inicializado: {e}")


class NotificationService:
    """Serviço de notificação por e-mail"""
    
    def __init__(self):
        self.smtp_server = getattr(settings, 'SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = getattr(settings, 'SMTP_PORT', 587)
        self.smtp_user = getattr(settings, 'SMTP_USER', None)
        self.smtp_password = getattr(settings, 'SMTP_PASSWORD', None)
        self.from_email = getattr(settings, 'FROM_EMAIL', self.smtp_user)
        self.from_name = getattr(settings, 'FROM_NAME', 'AgriSoil Alertas')
        
    def _verificar_configuracao(self) -> bool:
        """Verifica se o serviço está configurado"""
        if not self.smtp_user or not self.smtp_password:
            logger.warning("SMTP não configurado. Configure SMTP_USER e SMTP_PASSWORD nas variáveis de ambiente.")
            return False
        return True
    
    def _criar_email_alerta(
        self,
        destinatario: str,
        nome_usuario: str,
        alertas: List[AlertaDB],
        sensor_info: dict
    ) -> MIMEMultipart:
        """Cria o e-mail formatado com os alertas"""
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"🚨 {len(alertas)} Alerta(s) - {sensor_info['nome']}"
        msg['From'] = f"{self.from_name} <{self.from_email}>"
        msg['To'] = destinatario
        
        # Contar por severidade
        criticos = sum(1 for a in alertas if a.severidade == SeveridadeAlerta.CRITICO)
        altos = sum(1 for a in alertas if a.severidade == SeveridadeAlerta.ALTO)
        medios = sum(1 for a in alertas if a.severidade == SeveridadeAlerta.MEDIO)
        
        # Texto simples
        texto = f"""
Olá {nome_usuario},

Você tem {len(alertas)} alerta(s) no sensor {sensor_info['nome']}:

"""
        if criticos > 0:
            texto += f"🔴 {criticos} CRÍTICO(S)\n"
        if altos > 0:
            texto += f"🟠 {altos} ALTO(S)\n"
        if medios > 0:
            texto += f"🟡 {medios} MÉDIO(S)\n"
        
        texto += "\n--- DETALHES DOS ALERTAS ---\n\n"
        
        for i, alerta in enumerate(alertas, 1):
            emoji = {
                SeveridadeAlerta.CRITICO: "🔴",
                SeveridadeAlerta.ALTO: "🟠",
                SeveridadeAlerta.MEDIO: "🟡",
                SeveridadeAlerta.BAIXO: "⚪"
            }.get(alerta.severidade, "•")
            
            texto += f"{emoji} {i}. {alerta.titulo}\n"
            texto += f"   {alerta.mensagem}\n"
            if alerta.valor_medido:
                texto += f"   Valor medido: {alerta.valor_medido}\n"
            if alerta.recomendacao:
                texto += f"   Recomendação: {alerta.recomendacao}\n"
            texto += f"   Data: {alerta.criado_em.strftime('%d/%m/%Y %H:%M')}\n\n"
        
        texto += f"""
---
Acesse o painel para mais detalhes e tomar ações.

AgriSoil - Sistema de Monitoramento Agrícola
"""
        
        # HTML formatado
        html = f"""
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                   color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .content {{ padding: 20px; background: #f9f9f9; }}
        .alerta {{ background: white; padding: 15px; margin: 10px 0; 
                   border-left: 4px solid #ddd; border-radius: 4px; }}
        .alerta.critico {{ border-left-color: #dc2626; }}
        .alerta.alto {{ border-left-color: #ea580c; }}
        .alerta.medio {{ border-left-color: #fbbf24; }}
        .titulo {{ font-weight: bold; font-size: 16px; margin-bottom: 8px; }}
        .mensagem {{ color: #555; margin-bottom: 8px; }}
        .detalhes {{ font-size: 14px; color: #666; }}
        .footer {{ background: #333; color: white; padding: 15px; 
                   text-align: center; border-radius: 0 0 8px 8px; }}
        .badge {{ display: inline-block; padding: 4px 12px; border-radius: 12px;
                  font-size: 12px; font-weight: bold; }}
        .badge.critico {{ background: #dc2626; color: white; }}
        .badge.alto {{ background: #ea580c; color: white; }}
        .badge.medio {{ background: #fbbf24; color: #000; }}
    </style>
</head>
<body>
    <div class="header">
        <h2>🚨 Alertas do Sistema AgriSoil</h2>
        <p>Sensor: <strong>{sensor_info['nome']}</strong></p>
    </div>
    
    <div class="content">
        <p>Olá <strong>{nome_usuario}</strong>,</p>
        <p>Você tem <strong>{len(alertas)} alerta(s)</strong> no seu sensor:</p>
        
        <div style="margin: 20px 0;">
"""
        
        if criticos > 0:
            html += f'<span class="badge critico">🔴 {criticos} CRÍTICO(S)</span> '
        if altos > 0:
            html += f'<span class="badge alto">🟠 {altos} ALTO(S)</span> '
        if medios > 0:
            html += f'<span class="badge medio">🟡 {medios} MÉDIO(S)</span> '
        
        html += """
        </div>
        
        <h3>Detalhes dos Alertas:</h3>
"""
        
        for alerta in alertas:
            classe_severidade = alerta.severidade.value
            emoji = {
                SeveridadeAlerta.CRITICO: "🔴",
                SeveridadeAlerta.ALTO: "🟠",
                SeveridadeAlerta.MEDIO: "🟡",
                SeveridadeAlerta.BAIXO: "⚪"
            }.get(alerta.severidade, "•")
            
            html += f"""
        <div class="alerta {classe_severidade}">
            <div class="titulo">{emoji} {alerta.titulo}</div>
            <div class="mensagem">{alerta.mensagem}</div>
            <div class="detalhes">
"""
            if alerta.valor_medido:
                html += f"                <strong>Valor medido:</strong> {alerta.valor_medido}<br>\n"
            if alerta.valor_referencia:
                html += f"                <strong>Referência:</strong> {alerta.valor_referencia}<br>\n"
            if alerta.recomendacao:
                html += f"                <strong>Recomendação:</strong> {alerta.recomendacao}<br>\n"
            
            html += f"""
                <strong>Data:</strong> {alerta.criado_em.strftime('%d/%m/%Y às %H:%M')}
            </div>
        </div>
"""
        
        html += """
    </div>
    
    <div class="footer">
        <p>AgriSoil - Sistema de Monitoramento Agrícola</p>
        <p style="font-size: 12px;">Acesse o painel para mais detalhes e tomar ações.</p>
    </div>
</body>
</html>
"""
        
        # Anexar ambas as versões
        part1 = MIMEText(texto, 'plain', 'utf-8')
        part2 = MIMEText(html, 'html', 'utf-8')
        msg.attach(part1)
        msg.attach(part2)
        
        return msg
    
    def enviar_alerta_email(
        self,
        db: Optional[Session],
        alerta: AlertaDB
    ) -> bool:
        """
        Envia notificação por e-mail de um alerta
        
        FUNCIONA MESMO SEM DB: Se db=None, apenas loga (não envia)
        """
        if not self._verificar_configuracao():
            return False
        
        if not db:
            logger.warning("[SEM DB] Não é possível enviar e-mail sem banco de dados")
            return False
        
        try:
            # Buscar informações do usuário
            usuario = db.query(UsuarioDB).filter(
                UsuarioDB.cliente_id == alerta.cliente_id,
                UsuarioDB.ativo == True
            ).first()
            
            if not usuario:
                logger.warning(f"Nenhum usuário ativo encontrado para cliente {alerta.cliente_id}")
                return False
            
            # Verificar preferências
            prefs = usuario.preferencias_notificacao or {}
            if not prefs.get('email_ativo', True):
                logger.info(f"Usuário {usuario.email} tem notificações desabilitadas")
                return False
            
            # Verificar severidade mínima
            severidade_minima = prefs.get('email_severidade_minima', 'alto')
            ordem = {'baixo': 1, 'medio': 2, 'alto': 3, 'critico': 4}
            if ordem.get(alerta.severidade.value, 0) < ordem.get(severidade_minima, 3):
                logger.info(f"Alerta abaixo da severidade mínima configurada")
                return False
            
            # Verificar tipo de alerta
            tipo_pref_map = {
                'ph': 'alertas_ph',
                'umidade': 'alertas_umidade',
                'temperatura': 'alertas_temperatura',
                'nitrogenio': 'alertas_npk',
                'fosforo': 'alertas_npk',
                'potassio': 'alertas_npk',
                'sistema': 'alertas_sistema'
            }
            
            tipo_pref = tipo_pref_map.get(alerta.tipo.value, 'alertas_sistema')
            if not prefs.get(tipo_pref, True):
                logger.info(f"Usuário desativou alertas do tipo {alerta.tipo.value}")
                return False
            
            # Buscar informações do sensor
            sensor = db.query(SensorDB).filter(
                SensorDB.sensor_id == alerta.sensor_id
            ).first()
            
            sensor_info = {
                'nome': sensor.nome if sensor else alerta.sensor_id,
                'propriedade': sensor.propriedade if sensor else 'N/A'
            }
            
            # Criar e enviar e-mail
            msg = self._criar_email_alerta(
                usuario.email,
                usuario.nome,
                [alerta],
                sensor_info
            )
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            # Marcar como enviado
            alerta.notificacao_enviada = True
            db.commit()
            
            logger.info(f"E-mail enviado para {usuario.email} - Alerta {alerta.id}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao enviar e-mail: {str(e)}")
            return False
    
    def enviar_alertas_agrupados(
        self,
        db: Optional[Session],
        cliente_id: str
    ) -> bool:
        """
        Envia um resumo com todos os alertas pendentes de notificação
        Útil quando agrupar_alertas está ativo
        
        FUNCIONA MESMO SEM DB: Se db=None, apenas loga (não envia)
        """
        if not self._verificar_configuracao():
            return False
        
        if not db:
            logger.warning("[SEM DB] Não é possível enviar alertas agrupados sem banco de dados")
            return False
        
        try:
            # Buscar alertas não notificados
            alertas = db.query(AlertaDB).filter(
                AlertaDB.cliente_id == cliente_id,
                AlertaDB.notificacao_enviada == False,
                AlertaDB.status == StatusAlerta.ATIVO
            ).order_by(
                AlertaDB.severidade.desc(),
                AlertaDB.criado_em.desc()
            ).limit(20).all()
            
            if not alertas:
                return True
            
            # Buscar usuário
            usuario = db.query(UsuarioDB).filter(
                UsuarioDB.cliente_id == cliente_id,
                UsuarioDB.ativo == True
            ).first()
            
            if not usuario:
                return False
            
            # Agrupar por sensor
            alertas_por_sensor = {}
            for alerta in alertas:
                if alerta.sensor_id not in alertas_por_sensor:
                    alertas_por_sensor[alerta.sensor_id] = []
                alertas_por_sensor[alerta.sensor_id].append(alerta)
            
            # Enviar um e-mail por sensor
            for sensor_id, alertas_sensor in alertas_por_sensor.items():
                try:
                    sensor = db.query(SensorDB).filter(
                        SensorDB.sensor_id == sensor_id
                    ).first()
                    
                    sensor_info = {
                        'nome': sensor.nome if sensor else sensor_id,
                        'propriedade': sensor.propriedade if sensor else 'N/A'
                    }
                    
                    msg = self._criar_email_alerta(
                        usuario.email,
                        usuario.nome,
                        alertas_sensor,
                        sensor_info
                    )
                    
                    with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                        server.starttls()
                        server.login(self.smtp_user, self.smtp_password)
                        server.send_message(msg)
                    
                    # Marcar como enviados
                    for alerta in alertas_sensor:
                        alerta.notificacao_enviada = True
                    
                    
                    logger.info(f"E-mail agrupado enviado: {len(alertas_sensor)} alertas do sensor {sensor_id}")
                    
                    # Enviar push notification também (com retry)
                    if hasattr(usuario, 'firebase_token') and usuario.firebase_token:
                        enviar_push_notification_com_retry(
                            usuario.firebase_token,
                            f"🚨 {len(alertas_sensor)} alerta(s)",
                            alertas_sensor[0].mensagem,
                            {
                                "tipo": "alerta",
                                "sensor_id": sensor_id,
                                "quantidade": str(len(alertas_sensor))
                            }
                        )
                    
                except Exception as e:
                    logger.error(f"Erro ao enviar notificações do sensor {sensor_id}: {e}")
            
            db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Erro ao enviar alertas agrupados: {str(e)}")
            return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
def enviar_push_notification_com_retry(
    token: str,
    titulo: str,
    mensagem: str,
    dados: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Enviar push notification com retry automático (3 tentativas)
    Backoff exponencial: 2s, 4s, 8s
    """
    if not firebase_app:
        logger.warning("Firebase não inicializado, push não enviado")
        return False
    
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=titulo,
                body=mensagem
            ),
            data=dados or {},
            token=token,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    sound="default",
                    channel_id="alertas"
                )
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound="default",
                        badge=1
                    )
                )
            )
        )
        
        response = messaging.send(message)
        logger.info(f"✅ Push enviado: {response}")
        return True
        
    except messaging.UnregisteredError:
        logger.warning(f"⚠️ Token inválido: {token[:20]}...")
        return False
    except Exception as e:
        logger.error(f"❌ Erro push (retry): {e}")
        raise


def enviar_notificacao_push(
    token: str,
    titulo: str,
    mensagem: str,
    dados: Optional[Dict[str, Any]] = None
) -> bool:
    """Wrapper simples sem retry - com fallback gracioso"""
    try:
        return enviar_push_notification_com_retry(token, titulo, mensagem, dados)
    except Exception as e:
        logger.error(f"❌ Falha definitiva push: {e}")
        return False


# Instância global
notification_service = NotificationService()

