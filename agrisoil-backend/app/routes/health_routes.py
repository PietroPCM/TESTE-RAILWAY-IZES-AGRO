"""
Health checks e status endpoints - Production Ready
Monitoramento completo de todos os serviços
"""

from fastapi import APIRouter, status, Response
from datetime import datetime
import logging
from app.db import engine
from app.config import settings
from sqlalchemy import text
from typing import Dict, Any

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> Dict[str, Any]:
    """
    Health check completo com todos os serviços
    
    Verifica:
    - Database PostgreSQL
    - Redis Cache (opcional)
    - Firebase (opcional)
    - Celery Workers (opcional)
    
    Response:
        - status: ok/degraded/down
        - timestamp
        - services: status de cada serviço
    """
    services = {}
    overall_status = "ok"
    
    # 1. Database (não crítico para healthcheck básico)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            conn.commit()
        services["database"] = {"status": "ok", "message": "Connected"}
    except Exception as e:
        services["database"] = {"status": "down", "message": str(e)}
        overall_status = "degraded"  # Não falha o healthcheck, só marca como degradado
        logger.warning(f"⚠️ Database down: {e}")
    
    # 2. Redis
    try:
        from app.cache import cache
        if cache.client:
            cache.client.ping()
            services["redis"] = {"status": "ok", "message": "Connected"}
        else:
            services["redis"] = {"status": "disabled", "message": "Not configured"}
    except Exception as e:
        services["redis"] = {"status": "down", "message": str(e)}
        overall_status = "degraded"  # Redis é opcional
        logger.warning(f"⚠️ Redis down: {e}")
    
    # 3. Firebase
    try:
        from app.services.notification_service import firebase_app
        if firebase_app:
            services["firebase"] = {"status": "ok", "message": "Initialized"}
        else:
            services["firebase"] = {"status": "disabled", "message": "Not configured"}
    except Exception as e:
        services["firebase"] = {"status": "down", "message": str(e)}
        overall_status = "degraded"
        logger.warning(f"⚠️ Firebase down: {e}")
    
    # 4. Celery
    try:
        from app.celery_worker import celery_app
        inspect = celery_app.control.inspect(timeout=1.0)
        active_workers = inspect.active()
        if active_workers:
            services["celery"] = {
                "status": "ok",
                "message": f"{len(active_workers)} workers"
            }
        else:
            services["celery"] = {
                "status": "degraded",
                "message": "Nenhum worker"
            }
            overall_status = "degraded"
    except Exception as e:
        services["celery"] = {"status": "disabled", "message": "Not running"}
        logger.warning(f"⚠️ Celery down: {e}")
    
    response_data = {
        "status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "services": services
    }
    
    # Retornar 503 se sistema crítico está down
    if overall_status == "down":
        return Response(
            content=str(response_data),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    return response_data


@router.get("/health/ping", status_code=status.HTTP_200_OK)
async def ping():
    """Ping rápido para load balancers"""
    return {"status": "ok", "message": "pong"}


@router.get("/health/deep", status_code=status.HTTP_200_OK)
async def deep_health_check() -> dict:
    """
    Health check profundo com BD
    
    Response:
        - status: "ok" se API e BD estão funcionando
        - database: status da conexão BD
        - timestamp: timestamp do check
    """
    db_status = "down"
    
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            db_status = "ok"
    except Exception as e:
        logger.error(f"BD health check falhou: {e}")
        db_status = "down"
    
    overall_status = "ok" if db_status == "ok" else "degraded"
    
    return {
        "status": overall_status,
        "database": db_status,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/status", status_code=status.HTTP_200_OK)
async def status_check() -> dict:
    """
    Status detalhado da aplicação
    """
    return {
        "application": "AgriSoil Backend",
        "version": "2.0.0",
        "environment": settings.environment,
        "status": "running",
        "timestamp": datetime.utcnow().isoformat()
    }
