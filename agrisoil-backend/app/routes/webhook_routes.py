"""
Endpoints para receber dados dos sensores IoT via webhook HTTP.

Sensores físicos (Arduino/ESP32/comerciais) fazem POST para este endpoint
com leituras de pH, umidade, temperatura, NPK, etc.

Fluxo:
1. Sensor envia HTTP POST com dados JSON + API Key
2. Backend valida API Key e sensor_id
3. Processa leitura e cria alertas se necessário
4. Armazena no banco de dados
5. Envia push notification se alerta crítico
6. Retorna ACK para o sensor
"""

from fastapi import APIRouter, HTTPException, Header, Depends, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.db import get_db
from app.models.database import SensorDB as Sensor, LeituraDB as Leitura
from app.models.leitura import Leitura as LeituraSchema
from app.services.sensor_service import processar_leitura
from app.metrics import registrar_leitura_sensor
from app.security import verificar_sensor_api_key
from app.utils.datetime_utils import utc_iso

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["Webhook IoT"])
limiter = Limiter(key_func=get_remote_address)

class LeituraSensorSchema(BaseModel):
    """Schema validado para leituras de sensores IoT"""
    timestamp: str
    ph: Optional[float] = Field(None, ge=0, le=14, description="pH do solo (0-14)")
    umidade: Optional[float] = Field(None, ge=0, le=100, description="Umidade do solo (%)")
    temperatura: Optional[float] = Field(None, ge=-50, le=100, description="Temperatura (°C)")
    condutividade: Optional[float] = Field(None, ge=0, le=10, description="Condutividade (dS/m)")
    nitrogenio: Optional[int] = Field(None, ge=0, le=500, description="Nitrogênio (ppm)")
    fosforo: Optional[int] = Field(None, ge=0, le=500, description="Fósforo (ppm)")
    potassio: Optional[int] = Field(None, ge=0, le=500, description="Potássio (ppm)")
    
    @field_validator('timestamp')
    @classmethod
    def validar_timestamp(cls, v):
        """Validar formato ISO 8601"""
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError('Timestamp deve estar em formato ISO 8601 (ex: 2026-02-02T14:30:00Z)')
    
    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2026-02-02T14:30:00Z",
                "ph": 6.8,
                "umidade": 45.2,
                "temperatura": 24.5,
                "condutividade": 1.2,
                "nitrogenio": 120,
                "fosforo": 30,
                "potassio": 80
            }
        }


class DadosSensorIoT:
    """Payload esperado dos sensores IoT"""
    def __init__(
        self,
        timestamp: str,
        ph: Optional[float] = None,
        umidade: Optional[float] = None,
        temperatura: Optional[float] = None,
        condutividade: Optional[float] = None,
        nitrogenio: Optional[int] = None,
        fosforo: Optional[int] = None,
        potassio: Optional[int] = None,
    ):
        self.timestamp = timestamp
        self.ph = ph
        self.umidade = umidade
        self.temperatura = temperatura
        self.condutividade = condutividade
        self.nitrogenio = nitrogenio
        self.fosforo = fosforo
        self.potassio = potassio


def descrever_localizacao_sensor(sensor: Sensor) -> str:
    """Retorna uma localização legível usando os campos existentes no banco."""
    return (
        sensor.local_especifico
        or sensor.propriedade
        or sensor.municipio
        or sensor.estado
        or "desconhecido"
    )


@router.post(
    "/sensor/{sensor_id}",
    summary="Receber leitura de sensor IoT",
    description="""
    Endpoint para sensores físicos enviarem dados em tempo real.
    
    **Autenticação:** Header `X-API-Key` obrigatório
    
    **Formato do payload:**
    ```json
    {
        "timestamp": "2026-01-22T14:30:00Z",
        "ph": 6.8,
        "umidade": 45.2,
        "temperatura": 24.5,
        "condutividade": 1.2,
        "nitrogenio": 120,
        "fosforo": 30,
        "potassio": 80
    }
    ```
    
    **Validações:**
    - pH: 0-14
    - Umidade: 0-100%
    - Temperatura: -50 a 100°C
    - Condutividade: 0-10 dS/m
    - NPK: 0-500 ppm
    
    **Resposta:**
    - 200: Leitura processada com sucesso
    - 400: Dados inválidos
    - 401: API Key inválida
    - 404: Sensor não encontrado
    - 429: Rate limit excedido (max 1 req/min por sensor)
    """
)
@limiter.limit("1/minute")  # Rate limit: 1 request per minute per IP
async def receber_leitura_sensor(
    request: Request,
    sensor_id: str,
    dados: LeituraSensorSchema,
    db: Session = Depends(get_db),
    api_key: str = Depends(verificar_sensor_api_key)
):
    """
    Recebe e processa dados de um sensor IoT.
    
    Args:
        sensor_id: ID único do sensor (ex: "SENSOR-001")
        dados: Payload JSON validado com leituras
        db: Sessão do banco de dados
        api_key: API Key validada
        
    Returns:
        Confirmação de processamento + alertas gerados (se houver)
    """
    logger.info(f"📡 Recebendo leitura do sensor {sensor_id}")
    
    try:
        # 1. VALIDAR SENSOR EXISTE E ESTÁ ATIVO
        sensor = db.query(Sensor).filter(Sensor.sensor_id == sensor_id).first()
        
        if not sensor:
            logger.error(f"❌ Sensor {sensor_id} não encontrado no banco de dados")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sensor {sensor_id} não cadastrado. Cadastre via painel admin."
            )
        
        if not sensor.ativo:
            logger.warning(f"⚠️  Sensor {sensor_id} está desativado")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Sensor {sensor_id} está desativado"
            )
        
        # 2. VALIDAR FORMATO E RANGES DOS DADOS (REFORÇADO)
        timestamp_str = dados.timestamp
        if not timestamp_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Campo 'timestamp' obrigatório"
            )
        
        # Validar ranges rigorosos
        ph = dados.ph
        umidade = dados.umidade
        temperatura = dados.temperatura
        condutividade = dados.condutividade
        nitrogenio = dados.nitrogenio
        fosforo = dados.fosforo
        potassio = dados.potassio
        
        # Validação pH: 0-14 (escala universal)
        if ph is not None:
            if not isinstance(ph, (int, float)) or not (0 <= ph <= 14):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"pH inválido: {ph}. Deve estar entre 0 e 14"
                )
        
        # Validação umidade: 0-100%
        if umidade is not None:
            if not isinstance(umidade, (int, float)) or not (0 <= umidade <= 100):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Umidade inválida: {umidade}. Deve estar entre 0 e 100"
                )
        
        # Validação temperatura: -50 a 100°C
        if temperatura is not None:
            if not isinstance(temperatura, (int, float)) or not (-50 <= temperatura <= 100):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Temperatura inválida: {temperatura}. Deve estar entre -50 e 100°C"
                )
        
        # Validação condutividade: 0-10 dS/m
        if condutividade is not None:
            if not isinstance(condutividade, (int, float)) or not (0 <= condutividade <= 10):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Condutividade inválida: {condutividade}. Deve estar entre 0 e 10 dS/m"
                )
        
        # Validação NPK: 0-500 ppm
        for nome, valor in [("nitrogenio", nitrogenio), ("fosforo", fosforo), ("potassio", potassio)]:
            if valor is not None:
                if not isinstance(valor, (int, float)) or not (0 <= valor <= 500):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"{nome.capitalize()} inválido: {valor}. Deve estar entre 0 e 500 ppm"
                    )
        
        # Validar ranges
        ph = dados.ph
        if ph is not None and (ph < 0 or ph > 14):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"pH inválido: {ph}. Deve estar entre 0-14"
            )
        
        umidade = dados.umidade
        if umidade is not None and (umidade < 0 or umidade > 100):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Umidade inválida: {umidade}%. Deve estar entre 0-100"
            )
        
        temperatura = dados.temperatura
        if temperatura is not None and (temperatura < -50 or temperatura > 100):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Temperatura inválida: {temperatura}°C"
            )
        
        # 3. CRIAR REGISTRO DE LEITURA NO BANCO
        leitura = Leitura(
            sensor_id=sensor.sensor_id,
            cliente_id=sensor.cliente_id,
            timestamp=datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')),
            ph=ph,
            umidade=umidade,
            temperatura=temperatura,
            condutividade=dados.condutividade,
            nitrogenio=dados.nitrogenio,
            fosforo=dados.fosforo,
            potassio=dados.potassio,
        )
        
        db.add(leitura)
        db.flush()
        db.refresh(leitura)
        
        logger.info(f"✅ Leitura #{leitura.id} salva para sensor {sensor_id}")
        
        # 4. PROCESSAR REGRAS E ALERTAS
        leitura_schema = LeituraSchema(
            ph=ph,
            soilMoisture=umidade,
            temperature=temperatura,
            electricalConductivity=condutividade,
            nitrogen=nitrogenio,
            phosphorus=fosforo,
            potassium=potassio,
        )
        resultado = processar_leitura(
            sensor_id=sensor.sensor_id,
            cliente=sensor.cliente_id,
            leitura=leitura_schema,
            db=db,
            leitura_id=leitura.id,
        )

        avaliacoes = resultado.get("avaliacoes", {})
        leitura.ph_nivel = avaliacoes.get("ph", {}).get("nivel")
        leitura.ph_mensagem = avaliacoes.get("ph", {}).get("mensagem")
        leitura.umidade_nivel = avaliacoes.get("umidade", {}).get("nivel")
        leitura.umidade_mensagem = avaliacoes.get("umidade", {}).get("mensagem")
        leitura.temperatura_nivel = avaliacoes.get("temperatura", {}).get("nivel")
        leitura.temperatura_mensagem = avaliacoes.get("temperatura", {}).get("mensagem")
        leitura.nitrogenio_nivel = avaliacoes.get("nitrogenio", {}).get("nivel")
        leitura.nitrogenio_mensagem = avaliacoes.get("nitrogenio", {}).get("mensagem")
        leitura.fosforo_nivel = avaliacoes.get("fosforo", {}).get("nivel")
        leitura.fosforo_mensagem = avaliacoes.get("fosforo", {}).get("mensagem")
        leitura.potassio_nivel = avaliacoes.get("potassio", {}).get("nivel")
        leitura.potassio_mensagem = avaliacoes.get("potassio", {}).get("mensagem")
        leitura.alerta_ativo = resultado.get("alerta_ativo", False)
        leitura.nivel_critico = resultado.get("nivel_critico", False)
        db.commit()

        # 5. REGISTRAR MÉTRICAS PROMETHEUS
        registrar_leitura_sensor(
            sensor_id=sensor.sensor_id,
            tipo_sensor=sensor.tipo or "solo",
            valores={
                "ph": ph,
                "umidade": umidade,
                "temperatura": temperatura,
                "nitrogenio": nitrogenio,
                "localizacao": descrever_localizacao_sensor(sensor)
            }
        )
        
        # 6. RESPOSTA PARA O SENSOR
        return {
            "status": "sucesso",
            "mensagem": "Leitura processada com sucesso",
            "leitura_id": leitura.id,
            "sensor_id": sensor.sensor_id,
            "cliente_id": sensor.cliente_id,
            "timestamp": utc_iso(datetime.utcnow()),
            "alerta_ativo": leitura.alerta_ativo,
            "nivel_critico": leitura.nivel_critico,
            "alertas_criados": resultado.get("alertas_criados", []),
            "avaliacoes": avaliacoes,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao processar leitura do sensor {sensor_id}: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno ao processar leitura: {str(e)}"
        )


@router.get(
    "/sensor/{sensor_id}/status",
    summary="Verificar status do sensor",
    description="Endpoint para sensor verificar se está cadastrado e ativo"
)
async def verificar_status_sensor(
    sensor_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verificar_sensor_api_key)
):
    """Permite sensor verificar se está cadastrado e configurado corretamente"""
    
    sensor = db.query(Sensor).filter(Sensor.sensor_id == sensor_id).first()
    
    if not sensor:
        return {
            "cadastrado": False,
            "mensagem": "Sensor não encontrado. Cadastre via painel admin."
        }
    
    ultima_leitura = db.query(Leitura).filter(
        Leitura.sensor_id == sensor.sensor_id
    ).order_by(Leitura.timestamp.desc()).first()

    return {
        "cadastrado": True,
        "ativo": sensor.ativo,
        "nome": sensor.nome,
        "cliente_id": sensor.cliente_id,
        "ultima_leitura": utc_iso(ultima_leitura.timestamp) if ultima_leitura else None,
        "intervalo_envio_recomendado": "60s"  # 1 minuto
    }


@router.get(
    "/health",
    tags=["Health Check"],
    summary="Verificar saúde do sistema"
)
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint para monitoramento do sistema.
    
    Returns:
        - 200: Sistema saudável
        - 503: Erro de conexão com banco de dados
    """
    try:
        # Testar conexão com banco de dados
        db.execute(text("SELECT 1"))
        
        logger.info("Health check OK")
        return {
            "status": "healthy",
            "timestamp": utc_iso(datetime.utcnow()),
            "service": "agrisoil-webhook",
            "database": "connected"
        }
    except Exception as e:
        logger.error(f"Health check falhou: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unhealthy",
                "timestamp": utc_iso(datetime.utcnow()),
                "error": "Database connection failed"
            }
        )
