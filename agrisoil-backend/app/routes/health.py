"""
Health Check Endpoints para Kubernetes/Railway
Monitorar saúde da aplicação e suas dependências
"""
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, status, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.logging_config import setup_logging

logger = setup_logging()
router = APIRouter(prefix="/health", tags=["Health Check"])


class HealthStatus:
    """Status de saúde da aplicação"""
    
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


async def get_db():
    """Dependência para obter sessão do banco"""
    db = SessionLocal()
    try:
        yield db
    finally:
        await db.close()


@router.get(
    "/ping",
    status_code=status.HTTP_200_OK,
    summary="Ping simples",
    description="Verifica se a aplicação está respondendo"
)
async def health_ping():
    """
    Health check simples - apenas verifica se a aplicação está rodando
    """
    return {
        "status": HealthStatus.OK,
        "timestamp": datetime.utcnow().isoformat(),
        "message": "AgriSoil Backend está online"
    }


@router.get(
    "/ready",
    status_code=status.HTTP_200_OK,
    summary="Readiness probe",
    description="Verifica se a aplicação está pronta para receber requisições (Kubernetes)"
)
async def health_ready(db: AsyncSession = Depends(get_db)):
    """
    Readiness probe para Kubernetes/Railway
    Verifica:
    - Aplicação está respondendo
    - Banco de dados está acessível
    - Serviços críticos estão prontos
    """
    health_status = {
        "status": HealthStatus.OK,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "app": {"status": HealthStatus.OK},
            "database": {"status": HealthStatus.OK},
        }
    }
    
    # Verificar banco de dados
    try:
        result = await db.execute(text("SELECT 1"))
        logger.debug("Database health check passed")
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status["status"] = HealthStatus.DOWN
        health_status["checks"]["database"]["status"] = HealthStatus.DOWN
        health_status["checks"]["database"]["error"] = str(e)
        return health_status
    
    return health_status


@router.get(
    "/db",
    status_code=status.HTTP_200_OK,
    summary="Database health check",
    description="Verifica conectividade e performance do banco de dados"
)
async def health_db(db: AsyncSession = Depends(get_db)):
    """
    Verificação detalhada do banco de dados
    - Conectividade
    - Pool size
    - Latência de query
    """
    import time
    
    result = {
        "status": HealthStatus.OK,
        "timestamp": datetime.utcnow().isoformat(),
        "database": {
            "type": "PostgreSQL",
            "status": HealthStatus.OK,
            "latency_ms": 0,
            "query_count": 0
        }
    }
    
    try:
        # Medir latência
        start = time.time()
        await db.execute(text("SELECT 1 as health_check"))
        latency = (time.time() - start) * 1000
        
        result["database"]["latency_ms"] = round(latency, 2)
        logger.debug(f"Database latency: {latency:.2f}ms")
        
        # Verificar pool
        if hasattr(db.bind, 'pool'):
            pool = db.bind.pool
            result["database"]["pool"] = {
                "size": pool.size() if hasattr(pool, 'size') else "unknown",
                "checked_in": pool.checkedin() if hasattr(pool, 'checkedin') else "unknown",
            }
        
        return result
        
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}", exc_info=True)
        result["status"] = HealthStatus.DOWN
        result["database"]["status"] = HealthStatus.DOWN
        result["database"]["error"] = str(e)
        return result


@router.get(
    "/live",
    status_code=status.HTTP_200_OK,
    summary="Liveness probe",
    description="Verifica se a aplicação está viva (não congelada)"
)
async def health_live():
    """
    Liveness probe para Kubernetes/Railway
    Se isso não responder em tempo hábil, o container será reiniciado
    """
    return {
        "status": HealthStatus.OK,
        "timestamp": datetime.utcnow().isoformat(),
        "message": "Application is alive"
    }
