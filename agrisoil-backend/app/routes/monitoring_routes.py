"""
Health Check e Monitoring Routes
Endpoints para health checks e recebimento de alertas do Prometheus
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])
logger = logging.getLogger(__name__)


@router.post("/alertmanager/webhook")
async def alertmanager_webhook(request: Request):
    """
    Receber webhooks do Alertmanager do Prometheus
    Você pode processar e salvar no banco, enviar notificações, etc.
    """
    try:
        payload = await request.json()
        
        # Log dos alertas recebidos
        alerts = payload.get('alerts', [])
        for alert in alerts:
            status = alert.get('status')
            labels = alert.get('labels', {})
            annotations = alert.get('annotations', {})
            
            if status == 'firing':
                logger.warning(
                    f"🚨 Alerta Prometheus: {labels.get('alertname')} "
                    f"- Severidade: {labels.get('severity')} "
                    f"- {annotations.get('summary')}"
                )
            elif status == 'resolved':
                logger.info(
                    f"✅ Alerta Resolvido: {labels.get('alertname')}"
                )
        
        # TODO: Salvar no banco, enviar notificações, etc.
        # from app.services.alerta_service import processar_alerta_prometheus
        # await processar_alerta_prometheus(payload)
        
        return {"status": "ok", "received_alerts": len(alerts)}
    
    except Exception as e:
        logger.error(f"Erro ao processar webhook Alertmanager: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )
