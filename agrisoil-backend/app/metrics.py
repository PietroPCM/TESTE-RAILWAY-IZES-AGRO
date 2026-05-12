"""
Métricas customizadas Prometheus - AgriSoil
Rastreamento de métricas de negócio específicas
"""

from prometheus_client import Counter, Gauge, Histogram, Summary
import time
from functools import wraps

# ===== MÉTRICAS DE NEGÓCIO =====

# Leituras de sensores
leituras_recebidas_total = Counter(
    'agrisoil_leituras_recebidas_total',
    'Total de leituras de sensores recebidas',
    ['sensor_id', 'tipo_sensor']
)

leituras_invalidas_total = Counter(
    'agrisoil_leituras_invalidas_total',
    'Total de leituras rejeitadas por validação',
    ['sensor_id', 'motivo']
)

# Alertas
alertas_criados_total = Counter(
    'agrisoil_alertas_criados_total',
    'Total de alertas gerados',
    ['tipo_alerta', 'severidade']
)

alertas_enviados_total = Counter(
    'agrisoil_alertas_enviados_total',
    'Total de alertas enviados com sucesso',
    ['tipo_alerta', 'canal']
)

alertas_falha_envio_total = Counter(
    'agrisoil_alertas_falha_envio_total',
    'Total de falhas ao enviar alertas',
    ['tipo_alerta', 'motivo']
)

# Push Notifications
push_enviados_total = Counter(
    'agrisoil_push_enviados_total',
    'Total de push notifications enviados'
)

push_falhas_total = Counter(
    'agrisoil_push_falhas_total',
    'Total de falhas em push notifications',
    ['motivo']
)

# Sensores ativos
sensores_ativos_gauge = Gauge(
    'agrisoil_sensores_ativos',
    'Número de sensores atualmente ativos'
)

sensores_inativos_gauge = Gauge(
    'agrisoil_sensores_inativos',
    'Número de sensores inativos'
)

# Valores dos sensores (para alertar no Prometheus)
sensor_ph_gauge = Gauge(
    'agrisoil_sensor_ph',
    'Último valor de pH lido',
    ['sensor_id', 'localizacao']
)

sensor_umidade_gauge = Gauge(
    'agrisoil_sensor_umidade',
    'Último valor de umidade do solo (%)',
    ['sensor_id', 'localizacao']
)

sensor_temperatura_gauge = Gauge(
    'agrisoil_sensor_temperatura',
    'Último valor de temperatura (°C)',
    ['sensor_id', 'localizacao']
)

sensor_nitrogenio_gauge = Gauge(
    'agrisoil_sensor_nitrogenio',
    'Último valor de nitrogênio (ppm)',
    ['sensor_id', 'localizacao']
)

# Cache
cache_hit_total = Counter(
    'agrisoil_cache_hit_total',
    'Total de cache hits',
    ['cache_key_type']
)

cache_miss_total = Counter(
    'agrisoil_cache_miss_total',
    'Total de cache misses',
    ['cache_key_type']
)

# Database
db_query_duration = Histogram(
    'agrisoil_db_query_duration_seconds',
    'Duração das queries no banco de dados',
    ['query_type'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

db_connections_active = Gauge(
    'agrisoil_db_connections_active',
    'Número de conexões ativas no pool do banco'
)

# ===== DECORATORS PARA RASTREAMENTO =====

def track_time(metric: Histogram, labels: dict = None):
    """Decorator para rastrear tempo de execução"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                if labels:
                    metric.labels(**labels).observe(duration)
                else:
                    metric.observe(duration)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                if labels:
                    metric.labels(**labels).observe(duration)
                else:
                    metric.observe(duration)
        
        # Retornar wrapper correto baseado se é async ou não
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def track_db_query(query_type: str):
    """Decorator específico para queries de banco"""
    return track_time(db_query_duration, labels={'query_type': query_type})


# ===== FUNÇÕES AUXILIARES =====

def registrar_leitura_sensor(sensor_id: str, tipo_sensor: str, valores: dict):
    """Registrar métricas de uma leitura de sensor"""
    leituras_recebidas_total.labels(
        sensor_id=sensor_id,
        tipo_sensor=tipo_sensor
    ).inc()
    
    # Atualizar gauges com valores
    if valores.get('ph') is not None:
        sensor_ph_gauge.labels(
            sensor_id=sensor_id,
            localizacao=valores.get('localizacao', 'desconhecido')
        ).set(valores['ph'])
    
    if valores.get('umidade') is not None:
        sensor_umidade_gauge.labels(
            sensor_id=sensor_id,
            localizacao=valores.get('localizacao', 'desconhecido')
        ).set(valores['umidade'])
    
    if valores.get('temperatura') is not None:
        sensor_temperatura_gauge.labels(
            sensor_id=sensor_id,
            localizacao=valores.get('localizacao', 'desconhecido')
        ).set(valores['temperatura'])
    
    if valores.get('nitrogenio') is not None:
        sensor_nitrogenio_gauge.labels(
            sensor_id=sensor_id,
            localizacao=valores.get('localizacao', 'desconhecido')
        ).set(valores['nitrogenio'])


def registrar_alerta(tipo: str, severidade: str):
    """Registrar criação de um alerta"""
    alertas_criados_total.labels(
        tipo_alerta=tipo,
        severidade=severidade
    ).inc()


def registrar_push_enviado():
    """Registrar envio bem-sucedido de push notification"""
    push_enviados_total.inc()


def registrar_push_falha(motivo: str):
    """Registrar falha no envio de push notification"""
    push_falhas_total.labels(motivo=motivo).inc()


def atualizar_contadores_sensores(ativos: int, inativos: int):
    """Atualizar contadores de sensores ativos/inativos"""
    sensores_ativos_gauge.set(ativos)
    sensores_inativos_gauge.set(inativos)
