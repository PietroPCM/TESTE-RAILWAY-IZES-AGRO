"""
Serviço de gestão de alertas
Criação, deduplicação e gerenciamento de alertas
Integração com push notifications via Firebase
"""
import logging
import hashlib
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.database import AlertaDB, SensorDB, LeituraDB, UsuarioDB, SeveridadeAlerta, StatusAlerta, TipoAlerta
from app.models.alerta import AlertaCreate, AlertaResponse, AlertaUpdate, ResumoAlertas
from app.services.push_notification_service import PushNotificationService

logger = logging.getLogger(__name__)


def _mapear_severidade(nivel: str) -> Optional[SeveridadeAlerta]:
    """Mapeia nível do motor de regras para severidade de alerta"""
    mapa = {
        "critico": SeveridadeAlerta.CRITICO,
        "alerta": SeveridadeAlerta.ALTO,
        "baixo": SeveridadeAlerta.MEDIO,
        "ok": None,  # Não gera alerta
        "ideal": None
    }
    return mapa.get(nivel)


def _gerar_hash_deduplicacao(sensor_id: str, tipo: str, severidade: str, data: datetime) -> str:
    """
    Gera hash único para deduplicação de alertas
    Mesmo sensor + tipo + severidade + dia = mesmo hash
    """
    dia_str = data.strftime("%Y-%m-%d")
    conteudo = f"{sensor_id}|{tipo}|{severidade}|{dia_str}"
    return hashlib.sha256(conteudo.encode()).hexdigest()


def criar_alerta_automatico(
    db: Optional[Session],
    sensor_id: str,
    cliente_id: str,
    leitura_id: Optional[int],
    tipo: TipoAlerta,
    nivel: str,
    mensagem: str,
    valor_medido: Optional[float] = None,
    valor_referencia: Optional[str] = None,
    recomendacao: Optional[str] = None
) -> Optional[AlertaDB]:
    """
    Cria alerta automaticamente baseado no motor de regras
    Implementa deduplicação para evitar alertas repetidos
    
    FUNCIONA MESMO SEM DB: Se db=None, apenas loga o alerta
    """
    # Verificar se deve criar alerta
    severidade = _mapear_severidade(nivel)
    if not severidade:
        return None  # Níveis "ok" e "ideal" não geram alertas
    
    # Se não tem DB, apenas logar
    if not db:
        logger.warning(f"[SEM DB] Alerta seria criado: {tipo.value} - {severidade.value} - {mensagem}")
        return None
    
    # Gerar hash para deduplicação
    hash_dedup = _gerar_hash_deduplicacao(sensor_id, tipo.value, severidade.value, datetime.utcnow())
    
    # Verificar se já existe alerta ativo com mesmo hash nas últimas 24h
    limite_tempo = datetime.utcnow() - timedelta(hours=24)
    alerta_existente = db.query(AlertaDB).filter(
        AlertaDB.hash_deduplicacao == hash_dedup,
        AlertaDB.status == StatusAlerta.ATIVO,
        AlertaDB.criado_em >= limite_tempo
    ).first()
    
    if alerta_existente:
        logger.info(f"Alerta duplicado ignorado: {tipo.value} - {severidade.value}")
        return alerta_existente
    
    # Gerar título baseado no tipo e severidade
    titulos = {
        TipoAlerta.PH: f"pH {severidade.value}: {valor_medido:.1f}" if valor_medido else f"pH {severidade.value}",
        TipoAlerta.UMIDADE: f"Umidade {severidade.value}: {valor_medido:.1f}%" if valor_medido else f"Umidade {severidade.value}",
        TipoAlerta.TEMPERATURA: f"Temperatura {severidade.value}: {valor_medido:.1f}°C" if valor_medido else f"Temperatura {severidade.value}",
        TipoAlerta.NITROGENIO: f"Nitrogênio {severidade.value}: {valor_medido:.1f} mg/kg" if valor_medido else f"Nitrogênio {severidade.value}",
        TipoAlerta.FOSFORO: f"Fósforo {severidade.value}: {valor_medido:.1f} mg/kg" if valor_medido else f"Fósforo {severidade.value}",
        TipoAlerta.POTASSIO: f"Potássio {severidade.value}: {valor_medido:.1f} mg/kg" if valor_medido else f"Potássio {severidade.value}",
    }
    
    titulo = titulos.get(tipo, f"Alerta {tipo.value}")
    
    # Criar novo alerta
    alerta = AlertaDB(
        sensor_id=sensor_id,
        cliente_id=cliente_id,
        leitura_id=leitura_id,
        tipo=tipo,
        severidade=severidade,
        status=StatusAlerta.ATIVO,
        titulo=titulo,
        mensagem=mensagem,
        valor_medido=valor_medido,
        valor_referencia=valor_referencia,
        recomendacao=recomendacao,
        hash_deduplicacao=hash_dedup,
        notificacao_enviada=False
    )
    
    db.add(alerta)
    db.commit()
    db.refresh(alerta)
    
    logger.info(f"✅ Alerta criado: {titulo} - ID: {alerta.id}")
    
    # ENVIAR PUSH NOTIFICATION se FCM estiver habilitado
    _disparar_push_para_alerta(db, alerta)
    
    return alerta


def _disparar_push_para_alerta(db: Session, alerta: AlertaDB):
    """Executa envio push sem criar coroutine esquecida."""
    if not PushNotificationService.is_enabled():
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(_enviar_push_para_alerta(db, alerta))
    else:
        loop.create_task(_enviar_push_para_alerta(db, alerta))


async def _enviar_push_para_alerta(db: Session, alerta: AlertaDB):
    """
    Envia push notification para todos os dispositivos do cliente
    Executa de forma assíncrona para não bloquear criação do alerta
    """
    if not PushNotificationService.is_enabled():
        return
    
    try:
        # Buscar usuário e seus tokens FCM
        usuario = db.query(UsuarioDB).filter(
            UsuarioDB.cliente_id == alerta.cliente_id
        ).first()
        
        if not usuario:
            return
        
        # Verificar preferências de push
        prefs = usuario.preferencias_notificacao or {}
        if not prefs.get('push_ativo', True):
            logger.info(f"Push desabilitado para cliente {alerta.cliente_id}")
            return
        
        # Obter tokens FCM
        tokens = usuario.fcm_tokens or []
        if not tokens:
            logger.info(f"Nenhum token FCM cadastrado para cliente {alerta.cliente_id}")
            return
        
        # Buscar dados do sensor para localização
        sensor = db.query(SensorDB).filter(
            SensorDB.sensor_id == alerta.sensor_id
        ).first()
        
        sensor_localizacao = "Área desconhecida"
        if sensor:
            sensor_localizacao = sensor.local_especifico or sensor.propriedade or "Sensor"
        
        # Preparar payload do alerta
        alerta_payload = {
            'id': alerta.id,
            'tipo': alerta.tipo.value,
            'severidade': alerta.severidade.value,
            'mensagem': alerta.mensagem,
            'recomendacao': alerta.recomendacao or 'Verificar sensor',
            'sensor_id': alerta.sensor_id,
            'data_criacao': alerta.criado_em.isoformat()
        }
        
        # Enviar para todos os dispositivos
        resultado = await PushNotificationService.enviar_alerta_push_multiplo(
            device_tokens=tokens,
            alerta=alerta_payload,
            cliente_nome=usuario.nome or "Cliente",
            sensor_localizacao=sensor_localizacao
        )
        
        # Marcar notificação como enviada
        if resultado['sucesso'] > 0:
            alerta.notificacao_enviada = True
            db.commit()
            logger.info(
                f"📤 Push enviado: {resultado['sucesso']} dispositivos "
                f"(falhas: {resultado['falhas']})"
            )
        
    except Exception as e:
        logger.error(f"❌ Erro ao enviar push notification: {e}")
        # Não falhar a criação do alerta por causa de erro no push


def buscar_alertas_ativos(
    db: Optional[Session],
    cliente_id: str,
    severidade_minima: Optional[SeveridadeAlerta] = None,
    tipo: Optional[TipoAlerta] = None,
    limit: int = 50
) -> List[AlertaDB]:
    """
    Busca alertas ativos com filtros
    
    FUNCIONA MESMO SEM DB: Se db=None, retorna lista vazia
    """
    if not db:
        logger.warning("[SEM DB] Nenhum alerta disponível sem banco de dados")
        return []
    
    query = db.query(AlertaDB).filter(
        AlertaDB.cliente_id == cliente_id,
        AlertaDB.status == StatusAlerta.ATIVO
    )
    
    if tipo:
        query = query.filter(AlertaDB.tipo == tipo)
    
    if severidade_minima:
        # Filtrar por severidade mínima (ordem: critico > alto > medio > baixo)
        ordem_severidade = {
            SeveridadeAlerta.CRITICO: 4,
            SeveridadeAlerta.ALTO: 3,
            SeveridadeAlerta.MEDIO: 2,
            SeveridadeAlerta.BAIXO: 1
        }
        valor_minimo = ordem_severidade[severidade_minima]
        query = query.filter(
            AlertaDB.severidade.in_([
                s for s, v in ordem_severidade.items() if v >= valor_minimo
            ])
        )
    
    return query.order_by(
        AlertaDB.severidade.desc(),  # Mais críticos primeiro
        AlertaDB.criado_em.desc()
    ).limit(limit).all()


def atualizar_status_alerta(
    db: Optional[Session],
    alerta_id: int,
    cliente_id: str,
    update: AlertaUpdate
) -> Optional[AlertaDB]:
    """
    Atualiza status de um alerta
    
    FUNCIONA MESMO SEM DB: Se db=None, retorna None
    """
    if not db:
        logger.warning("[SEM DB] Não é possível atualizar alertas sem banco de dados")
        return None
    
    alerta = db.query(AlertaDB).filter(
        AlertaDB.id == alerta_id,
        AlertaDB.cliente_id == cliente_id
    ).first()
    
    if not alerta:
        return None
    
    alerta.status = update.status
    if update.observacao:
        alerta.observacao = update.observacao
    
    # Atualizar timestamps
    if update.status == StatusAlerta.RECONHECIDO and not alerta.reconhecido_em:
        alerta.reconhecido_em = datetime.utcnow()
    elif update.status == StatusAlerta.RESOLVIDO:
        alerta.resolvido_em = datetime.utcnow()
    
    db.commit()
    db.refresh(alerta)
    
    logger.info(f"Alerta {alerta_id} atualizado para {update.status}")
    return alerta


def obter_resumo_alertas(db: Optional[Session], cliente_id: str) -> ResumoAlertas:
    """
    Obtém resumo de alertas para o dashboard
    
    FUNCIONA MESMO SEM DB: Se db=None, retorna resumo vazio
    """
    if not db:
        logger.info("[SEM DB] Retornando resumo vazio de alertas")
        return ResumoAlertas(
            total_ativos=0,
            criticos=0,
            altos=0,
            medios=0,
            baixos=0,
            nao_reconhecidos=0,
            ultimas_24h=0,
            por_tipo={},
            alertas_recentes=[]
        )
    
    # Total de alertas ativos
    alertas_ativos = db.query(AlertaDB).filter(
        AlertaDB.cliente_id == cliente_id,
        AlertaDB.status == StatusAlerta.ATIVO
    ).all()
    
    # Contadores por severidade
    criticos = sum(1 for a in alertas_ativos if a.severidade == SeveridadeAlerta.CRITICO)
    altos = sum(1 for a in alertas_ativos if a.severidade == SeveridadeAlerta.ALTO)
    medios = sum(1 for a in alertas_ativos if a.severidade == SeveridadeAlerta.MEDIO)
    baixos = sum(1 for a in alertas_ativos if a.severidade == SeveridadeAlerta.BAIXO)
    
    # Não reconhecidos
    nao_reconhecidos = sum(1 for a in alertas_ativos if not a.reconhecido_em)
    
    # Últimas 24 horas
    limite_24h = datetime.utcnow() - timedelta(hours=24)
    ultimas_24h = db.query(AlertaDB).filter(
        AlertaDB.cliente_id == cliente_id,
        AlertaDB.criado_em >= limite_24h
    ).count()
    
    # Por tipo
    por_tipo = {}
    for tipo in TipoAlerta:
        count = sum(1 for a in alertas_ativos if a.tipo == tipo)
        if count > 0:
            por_tipo[tipo.value] = count
    
    # Alertas recentes (top 10)
    alertas_recentes = db.query(AlertaDB).filter(
        AlertaDB.cliente_id == cliente_id,
        AlertaDB.status == StatusAlerta.ATIVO
    ).order_by(
        AlertaDB.severidade.desc(),
        AlertaDB.criado_em.desc()
    ).limit(10).all()
    
    return ResumoAlertas(
        total_ativos=len(alertas_ativos),
        criticos=criticos,
        altos=altos,
        medios=medios,
        baixos=baixos,
        nao_reconhecidos=nao_reconhecidos,
        ultimas_24h=ultimas_24h,
        por_tipo=por_tipo,
        alertas_recentes=[
            AlertaResponse.model_validate(a) for a in alertas_recentes
        ]
    )


def resolver_alertas_automaticamente(db: Optional[Session], sensor_id: str, tipo: TipoAlerta):
    """
    Marca alertas como resolvidos quando uma nova leitura está OK
    
    FUNCIONA MESMO SEM DB: Se db=None, apenas loga
    """
    if not db:
        logger.info(f"[SEM DB] Alertas seriam resolvidos: {sensor_id} - {tipo.value}")
        return
    
    alertas = db.query(AlertaDB).filter(
        AlertaDB.sensor_id == sensor_id,
        AlertaDB.tipo == tipo,
        AlertaDB.status == StatusAlerta.ATIVO
    ).all()
    
    for alerta in alertas:
        alerta.status = StatusAlerta.RESOLVIDO
        alerta.resolvido_em = datetime.utcnow()
        alerta.observacao = "Resolvido automaticamente - leitura normalizada"
    
    db.commit()
    
    if alertas:
        logger.info(f"{len(alertas)} alertas resolvidos automaticamente para {sensor_id} - {tipo.value}")
