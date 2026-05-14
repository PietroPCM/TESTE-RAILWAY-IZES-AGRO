"""
Celery worker para tarefas assíncronas
Processa alertas e notificações em background
"""

from celery import Celery
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Criar app Celery
celery_app = Celery(
    "agrisoil",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Configuração
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutos
    task_soft_time_limit=240,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=30,
    task_routes={
        "processar_alerta_async": {"queue": "sensores"},
        "enviar_push_async": {"queue": "notificacoes"},
        "limpar_dados_antigos": {"queue": "manutencao"},
    },
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=500,
)


@celery_app.task(
    name="processar_alerta_async",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def processar_alerta_async(self, leitura_id: int, usuario_id: int = 0):
    """
    Processar alerta em background
    Libera o webhook para responder imediatamente
    """
    from app.db import SessionLocal
    from app.models.database import LeituraDB
    from app.models.leitura import Leitura
    from app.services.sensor_service import processar_leitura
    
    db = SessionLocal()
    try:
        logger.info(f"⚡ Processando alerta async para leitura {leitura_id}")
        leitura_db = db.query(LeituraDB).filter(LeituraDB.id == leitura_id).first()
        if not leitura_db:
            logger.warning(f"Leitura {leitura_id} não encontrada para processamento async")
            return None

        leitura = Leitura(
            ph=leitura_db.ph,
            soilMoisture=leitura_db.umidade,
            temperature=leitura_db.temperatura,
            electricalConductivity=leitura_db.condutividade,
            nitrogen=leitura_db.nitrogenio,
            phosphorus=leitura_db.fosforo,
            potassium=leitura_db.potassio,
        )
        resultado = processar_leitura(
            sensor_id=leitura_db.sensor_id,
            cliente=leitura_db.cliente_id,
            leitura=leitura,
            db=db,
            leitura_id=leitura_db.id,
        )
        leitura_db.alerta_ativo = resultado.get("alerta_ativo", False)
        leitura_db.nivel_critico = resultado.get("nivel_critico", False)
        db.commit()
        logger.info(f" Alerta processado: leitura {leitura_id}")
        return resultado
    except Exception as e:
        logger.error(f" Erro ao processar alerta {leitura_id}: {e}")
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(
    name="enviar_push_async",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def enviar_push_async(self, token: str, titulo: str, mensagem: str, dados: dict = None):
    """
    Enviar push notification em background
    """
    from app.services.notification_service import enviar_notificacao_push
    
    try:
        logger.info(f" Enviando push async para token {token[:20]}...")
        result = enviar_notificacao_push(token, titulo, mensagem, dados)
        if result:
            logger.info(f" Push enviado com sucesso")
        else:
            logger.warning(f" Falha ao enviar push")
        return result
    except Exception as e:
        logger.error(f" Erro ao enviar push: {e}")
        raise


@celery_app.task(
    name="limpar_dados_antigos",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 2},
)
def limpar_dados_antigos(self):
    """
    Task periódica para limpar dados antigos
    Rodar 1x por dia
    """
    from app.db import SessionLocal
    from app.models.database import LeituraDB, AlertaDB, StatusAlerta
    from datetime import datetime, timedelta
    
    db = SessionLocal()
    try:
        # Limpar leituras > 90 dias
        data_limite = datetime.now() - timedelta(days=90)
        leituras_antigas = db.query(LeituraDB).filter(LeituraDB.timestamp < data_limite).count()
        db.query(LeituraDB).filter(LeituraDB.timestamp < data_limite).delete()
        
        # Limpar alertas encerrados > 30 dias
        data_limite_alertas = datetime.now() - timedelta(days=30)
        alertas_antigos = db.query(AlertaDB).filter(
            AlertaDB.status.in_([StatusAlerta.RESOLVIDO, StatusAlerta.IGNORADO]),
            AlertaDB.criado_em < data_limite_alertas
        ).count()
        db.query(AlertaDB).filter(
            AlertaDB.status.in_([StatusAlerta.RESOLVIDO, StatusAlerta.IGNORADO]),
            AlertaDB.criado_em < data_limite_alertas
        ).delete()
        
        db.commit()
        logger.info(f" Limpeza: {leituras_antigas} leituras + {alertas_antigos} alertas removidos")
    except Exception as e:
        logger.error(f" Erro na limpeza de dados: {e}")
        db.rollback()
        raise
    finally:
        db.close()
