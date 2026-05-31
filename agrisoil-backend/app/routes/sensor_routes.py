"""
Rotas de Sensores - CRUD completo com persistência
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import logging

from app.db import get_db
from app.models.database import SensorDB, LeituraDB
from app.models.sensor import Sensor as SensorSchema
from app.models.leitura import Leitura as LeituraSchema
from app.repositories.sensor_repository import SensorRepository, LeituraRepository
from app.security import assert_tenant_access, verificar_acesso_cliente_path, verificar_admin
from app.services.sensor_service import processar_leitura
from pydantic import BaseModel, Field, field_validator
from app.security import verificar_sensor_api_key

router = APIRouter(prefix="/api/sensores", tags=["Sensores"])
logger = logging.getLogger(__name__)


class SensorCadastro(BaseModel):
    """Modelo para cadastro de sensor via painel admin"""
    id: str
    cliente_id: str = "cliente_default"
    nome: str
    tipo: str = "solo"
    localizacao: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    propriedade: Optional[str] = None
    municipio: Optional[str] = None
    estado: Optional[str] = None
    local_especifico: Optional[str] = None
    configuracao: Optional[dict] = None


class LeituraManual(BaseModel):
    """Payload para leitura manual/teste via Swagger."""
    timestamp: Optional[datetime] = Field(default=None, description="Opcional; se omitido usa horário atual UTC")
    ph: Optional[float] = Field(None, ge=0, le=14)
    umidade: Optional[float] = Field(None, ge=0, le=100)
    temperatura: Optional[float] = Field(None, ge=-50, le=100)
    condutividade: Optional[float] = Field(None, ge=0, le=10)
    nitrogenio: Optional[float] = Field(None, ge=0, le=500)
    fosforo: Optional[float] = Field(None, ge=0, le=500)
    potassio: Optional[float] = Field(None, ge=0, le=500)
    soilMoisture: Optional[float] = Field(None, ge=0, le=100)
    temperature: Optional[float] = Field(None, ge=-50, le=100)
    electricalConductivity: Optional[float] = Field(None, ge=0, le=10)
    nitrogen: Optional[float] = Field(None, ge=0, le=500)
    phosphorus: Optional[float] = Field(None, ge=0, le=500)
    potassium: Optional[float] = Field(None, ge=0, le=500)

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, value):
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

    def to_leitura_schema(self) -> LeituraSchema:
        return LeituraSchema(
            ph=self.ph,
            soilMoisture=self.umidade if self.umidade is not None else self.soilMoisture,
            temperature=self.temperatura if self.temperatura is not None else self.temperature,
            electricalConductivity=self.condutividade if self.condutividade is not None else self.electricalConductivity,
            nitrogen=self.nitrogenio if self.nitrogenio is not None else self.nitrogen,
            phosphorus=self.fosforo if self.fosforo is not None else self.phosphorus,
            potassium=self.potassio if self.potassio is not None else self.potassium,
        )


@router.post("/cadastrar", status_code=status.HTTP_201_CREATED)
async def cadastrar_sensor_admin(
    sensor_data: SensorCadastro,
    _admin=Depends(verificar_admin),
    db: Session = Depends(get_db)
):
    """
    Cadastra novo sensor via painel administrativo.
    
    Usado pelo site admin (Next.js) para cadastrar sensores que serão
    vinculados posteriormente a hardware físico via webhook.
    """
    try:
        sensor_existente = db.query(SensorDB).filter(SensorDB.sensor_id == sensor_data.id).first()
        if sensor_existente:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Sensor {sensor_data.id} já cadastrado"
            )
        
        novo_sensor = SensorDB(
            sensor_id=sensor_data.id,
            cliente_id=sensor_data.cliente_id,
            nome=sensor_data.nome,
            tipo=sensor_data.tipo,
            latitude=sensor_data.latitude,
            longitude=sensor_data.longitude,
            propriedade=sensor_data.propriedade,
            municipio=sensor_data.municipio,
            estado=sensor_data.estado,
            local_especifico=sensor_data.local_especifico or sensor_data.localizacao,
            ativo=True,
            criado_em=datetime.utcnow()
        )

        db.add(novo_sensor)
        db.commit()
        db.refresh(novo_sensor)
        
        logger.info(f"Sensor {sensor_data.id} cadastrado com sucesso via admin")
        
        return {
            "message": "Sensor cadastrado com sucesso",
            "sensor": {
                "id": novo_sensor.sensor_id,
                "sensor_id": novo_sensor.sensor_id,
                "cliente_id": novo_sensor.cliente_id,
                "nome": novo_sensor.nome,
                "tipo": novo_sensor.tipo,
                "localizacao": {
                    "latitude": novo_sensor.latitude,
                    "longitude": novo_sensor.longitude,
                    "propriedade": novo_sensor.propriedade,
                    "municipio": novo_sensor.municipio,
                    "estado": novo_sensor.estado,
                    "local_especifico": novo_sensor.local_especifico,
                },
                "ativo": novo_sensor.ativo
            },
            "integracao": {
                "webhook_url": f"/webhook/sensor/{novo_sensor.sensor_id}",
                "metodo": "POST",
                "header": "X-API-Key: [sua_api_key]"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro ao cadastrar sensor", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao cadastrar sensor: {str(e)}"
        )


@router.post("/manual", status_code=status.HTTP_201_CREATED)
async def cadastrar_sensor_manual(
    sensor_data: SensorCadastro,
    _api_key: str = Depends(verificar_sensor_api_key),
    db: Session = Depends(get_db)
):
    """
    Cadastra sensor manual/teste pelo Swagger.

    Requer header `X-API-Key` com `SENSOR_API_KEY`. Não exige JWT admin para
    permitir preparação de ambientes de teste sem sensor físico.
    """
    try:
        sensor_existente = db.query(SensorDB).filter(SensorDB.sensor_id == sensor_data.id).first()
        if sensor_existente:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Sensor {sensor_data.id} já cadastrado"
            )

        novo_sensor = SensorDB(
            sensor_id=sensor_data.id,
            cliente_id=sensor_data.cliente_id,
            nome=sensor_data.nome,
            tipo=sensor_data.tipo,
            latitude=sensor_data.latitude,
            longitude=sensor_data.longitude,
            propriedade=sensor_data.propriedade,
            municipio=sensor_data.municipio,
            estado=sensor_data.estado,
            local_especifico=sensor_data.local_especifico or sensor_data.localizacao,
            ativo=True,
            criado_em=datetime.utcnow()
        )

        db.add(novo_sensor)
        db.commit()
        db.refresh(novo_sensor)

        return {
            "message": "Sensor manual cadastrado com sucesso",
            "sensor": {
                "id": novo_sensor.sensor_id,
                "sensor_id": novo_sensor.sensor_id,
                "cliente_id": novo_sensor.cliente_id,
                "nome": novo_sensor.nome,
                "tipo": novo_sensor.tipo,
                "ativo": novo_sensor.ativo,
                "localizacao": {
                    "latitude": novo_sensor.latitude,
                    "longitude": novo_sensor.longitude,
                    "propriedade": novo_sensor.propriedade,
                    "municipio": novo_sensor.municipio,
                    "estado": novo_sensor.estado,
                    "local_especifico": novo_sensor.local_especifico,
                },
            },
            "proximos_passos": {
                "enviar_leitura_manual": f"/api/sensores/{novo_sensor.cliente_id}/{novo_sensor.sensor_id}/leitura-manual",
                "enviar_leitura_iot": f"/webhook/sensor/{novo_sensor.sensor_id}",
                "dashboard_app": f"/api/dashboard/cliente/{novo_sensor.cliente_id}/sensores",
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro ao cadastrar sensor manual", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao cadastrar sensor manual: {str(e)}"
        )


@router.patch("/{sensor_id}/status")
async def atualizar_status_sensor(
    sensor_id: str,
    status_data: dict = Body(...),
    _admin=Depends(verificar_admin),
    db: Session = Depends(get_db)
):
    """Ativa ou desativa um sensor"""
    try:
        sensor = db.query(SensorDB).filter(SensorDB.sensor_id == sensor_id).first()
        if not sensor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sensor {sensor_id} não encontrado"
            )
        
        sensor.ativo = status_data.get("ativo", sensor.ativo)
        sensor.atualizado_em = datetime.utcnow()
        db.commit()
        
        logger.info(f"✅ Status do sensor {sensor_id} atualizado: ativo={sensor.ativo}")
        
        return {
            "message": "Status atualizado com sucesso",
            "sensor_id": sensor_id,
            "ativo": sensor.ativo
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar status: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar status: {str(e)}"
        )


@router.delete("/{sensor_id}")
async def deletar_sensor(
    sensor_id: str,
    _admin=Depends(verificar_admin),
    db: Session = Depends(get_db)
):
    """Deleta um sensor e todas suas leituras"""
    try:
        sensor = db.query(SensorDB).filter(SensorDB.sensor_id == sensor_id).first()
        if not sensor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sensor {sensor_id} não encontrado"
            )
        
        # Deletar leituras associadas
        db.query(LeituraDB).filter(LeituraDB.sensor_id == sensor_id).delete()
        
        # Deletar sensor
        db.delete(sensor)
        db.commit()
        
        logger.info(f"✅ Sensor {sensor_id} deletado com sucesso")
        
        return {
            "message": "Sensor deletado com sucesso",
            "sensor_id": sensor_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao deletar sensor: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao deletar sensor: {str(e)}"
        )


@router.post("/{cliente}/{sensor_id}/registrar", status_code=status.HTTP_201_CREATED)
def registrar_sensor(
    cliente: str,
    sensor_id: str,
    sensor: SensorSchema,
    payload: dict = Depends(verificar_acesso_cliente_path),
    db: Session = Depends(get_db)
):
    """Registrar novo sensor no sistema"""
    try:
        if sensor.cliente_id != cliente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="cliente_id do corpo deve ser igual ao cliente da URL"
            )
        assert_tenant_access(payload, cliente)

        # Verificar se já existe
        sensor_existente = SensorRepository.buscar_por_id(db, sensor_id)
        if sensor_existente:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Sensor já existe"
            )
        
        # Criar sensor
        db_sensor = SensorRepository.criar_sensor(db, sensor)
        
        logger.info(f"Sensor {sensor_id} registrado para cliente {cliente}")
        
        return {
            "message": "Sensor registrado com sucesso",
            "sensor_id": db_sensor.sensor_id,
            "nome": db_sensor.nome
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao registrar sensor: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao registrar sensor: {str(e)}"
        )


@router.post("/{cliente}/{sensor_id}/leitura")
def registrar_leitura(
    cliente: str,
    sensor_id: str,
    leitura: LeituraSchema,
    _payload: dict = Depends(verificar_acesso_cliente_path),
    db: Session = Depends(get_db)
):
    """Registra uma leitura de sensor e aplica regras de negócio"""
    logger.info(f"Registrando leitura para sensor {sensor_id} do cliente {cliente}")
    
    try:
        # Verificar se sensor existe
        sensor = SensorRepository.buscar_por_id(db, sensor_id)
        if not sensor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sensor não encontrado"
            )
        if sensor.cliente_id != cliente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sensor não encontrado"
            )
        
        # Salvar leitura no banco primeiro (para obter o ID)
        leitura_db = LeituraRepository.salvar_leitura(
            db=db,
            sensor_id=sensor_id,
            cliente_id=cliente,
            leitura=leitura,
            avaliacoes={},  # Será atualizado depois
            alerta_ativo=False,
            nivel_critico=False
        )
        
        resultado = processar_leitura(
            sensor_id=sensor_id, 
            cliente=cliente, 
            leitura=leitura,
            db=db,
            leitura_id=leitura_db.id
        )
        
        leitura_db.alerta_ativo = resultado["alerta_ativo"]
        leitura_db.nivel_critico = resultado["nivel_critico"]
        db.commit()
        
        logger.info(f"Leitura salva com sucesso para sensor {sensor_id} - {len(resultado.get('alertas_criados', []))} alertas criados")
        
        return resultado
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao processar leitura: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar leitura: {str(e)}"
        )


@router.post("/{cliente}/{sensor_id}/leitura-manual")
def registrar_leitura_manual(
    cliente: str,
    sensor_id: str,
    leitura_manual: LeituraManual,
    _api_key: str = Depends(verificar_sensor_api_key),
    db: Session = Depends(get_db)
):
    """
    Registra uma leitura manual/teste simulando sensor IoT.

    Requer header `X-API-Key` com `SENSOR_API_KEY`.
    """
    try:
        sensor = SensorRepository.buscar_por_id(db, sensor_id)
        if not sensor or sensor.cliente_id != cliente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sensor não encontrado"
            )
        if not sensor.ativo:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sensor desativado"
            )

        leitura = leitura_manual.to_leitura_schema()
        leitura_db = LeituraRepository.salvar_leitura(
            db=db,
            sensor_id=sensor_id,
            cliente_id=cliente,
            leitura=leitura,
            avaliacoes={},
            alerta_ativo=False,
            nivel_critico=False
        )
        if leitura_manual.timestamp:
            leitura_db.timestamp = leitura_manual.timestamp
            db.commit()
            db.refresh(leitura_db)

        resultado = processar_leitura(
            sensor_id=sensor_id,
            cliente=cliente,
            leitura=leitura,
            db=db,
            leitura_id=leitura_db.id
        )

        avaliacoes = resultado.get("avaliacoes", {})
        leitura_db.ph_nivel = avaliacoes.get("ph", {}).get("nivel")
        leitura_db.ph_mensagem = avaliacoes.get("ph", {}).get("mensagem")
        leitura_db.umidade_nivel = avaliacoes.get("umidade", {}).get("nivel")
        leitura_db.umidade_mensagem = avaliacoes.get("umidade", {}).get("mensagem")
        leitura_db.temperatura_nivel = avaliacoes.get("temperatura", {}).get("nivel")
        leitura_db.temperatura_mensagem = avaliacoes.get("temperatura", {}).get("mensagem")
        leitura_db.nitrogenio_nivel = avaliacoes.get("nitrogenio", {}).get("nivel")
        leitura_db.nitrogenio_mensagem = avaliacoes.get("nitrogenio", {}).get("mensagem")
        leitura_db.fosforo_nivel = avaliacoes.get("fosforo", {}).get("nivel")
        leitura_db.fosforo_mensagem = avaliacoes.get("fosforo", {}).get("mensagem")
        leitura_db.potassio_nivel = avaliacoes.get("potassio", {}).get("nivel")
        leitura_db.potassio_mensagem = avaliacoes.get("potassio", {}).get("mensagem")
        leitura_db.alerta_ativo = resultado.get("alerta_ativo", False)
        leitura_db.nivel_critico = resultado.get("nivel_critico", False)
        db.commit()

        return {
            "status": "sucesso",
            "message": "Leitura manual processada com sucesso",
            "leitura_id": leitura_db.id,
            "sensor_id": sensor_id,
            "cliente_id": cliente,
            "timestamp": leitura_db.timestamp.isoformat() if leitura_db.timestamp else None,
            "dashboard_app": f"/api/dashboard/cliente/{cliente}/sensores",
            **resultado,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro ao registrar leitura manual", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao registrar leitura manual: {str(e)}"
        )


@router.get("/{cliente}")
def listar_sensores(
    cliente: str,
    apenas_ativos: bool = True,
    _payload: dict = Depends(verificar_acesso_cliente_path),
    db: Session = Depends(get_db)
):
    """Listar todos os sensores de um cliente"""
    try:
        sensores = SensorRepository.listar_por_cliente(db, cliente, apenas_ativos)
        
        return {
            "cliente_id": cliente,
            "total": len(sensores),
            "sensores": [
                {
                    "sensor_id": s.sensor_id,
                    "nome": s.nome,
                    "tipo": s.tipo,
                    "ativo": s.ativo,
                    "localizacao": {
                        "propriedade": s.propriedade,
                        "municipio": s.municipio,
                        "estado": s.estado
                    },
                    "criado_em": s.criado_em.isoformat() if s.criado_em else None
                }
                for s in sensores
            ]
        }
    
    except Exception as e:
        logger.error(f"Erro ao listar sensores: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao listar sensores: {str(e)}"
        )


@router.get("/{cliente}/{sensor_id}")
def detalhes_sensor(
    cliente: str,
    sensor_id: str,
    _payload: dict = Depends(verificar_acesso_cliente_path),
    db: Session = Depends(get_db)
):
    """Buscar detalhes de um sensor específico"""
    try:
        sensor = SensorRepository.buscar_por_id(db, sensor_id)
        
        if not sensor or sensor.cliente_id != cliente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sensor não encontrado"
            )
        
        # Buscar última leitura
        ultima_leitura = LeituraRepository.buscar_ultima_leitura(db, sensor_id)
        
        return {
            "sensor_id": sensor.sensor_id,
            "nome": sensor.nome,
            "tipo": sensor.tipo,
            "ativo": sensor.ativo,
            "localizacao": {
                "latitude": sensor.latitude,
                "longitude": sensor.longitude,
                "propriedade": sensor.propriedade,
                "municipio": sensor.municipio,
                "estado": sensor.estado,
                "local_especifico": sensor.local_especifico
            },
            "criado_em": sensor.criado_em.isoformat() if sensor.criado_em else None,
            "ultima_leitura": {
                "timestamp": ultima_leitura.timestamp.isoformat() if ultima_leitura else None,
                "ph": ultima_leitura.ph if ultima_leitura else None,
                "umidade": ultima_leitura.umidade if ultima_leitura else None,
                "temperatura": ultima_leitura.temperatura if ultima_leitura else None,
                "alerta_ativo": ultima_leitura.alerta_ativo if ultima_leitura else False
            } if ultima_leitura else None
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar sensor: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar sensor: {str(e)}"
        )


@router.get("/{cliente}/{sensor_id}/historico")
def historico_leituras(
    cliente: str,
    sensor_id: str,
    dias: int = 7,
    limit: int = 100,
    _payload: dict = Depends(verificar_acesso_cliente_path),
    db: Session = Depends(get_db)
):
    """Buscar histórico de leituras de um sensor"""
    try:
        # Verificar se sensor existe e pertence ao cliente
        sensor = SensorRepository.buscar_por_id(db, sensor_id)
        if not sensor or sensor.cliente_id != cliente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sensor não encontrado"
            )
        
        leituras = LeituraRepository.buscar_historico(db, sensor_id, dias, limit)
        
        return {
            "sensor_id": sensor_id,
            "periodo_dias": dias,
            "total": len(leituras),
            "leituras": [
                {
                    "timestamp": l.timestamp.isoformat(),
                    "ph": l.ph,
                    "umidade": l.umidade,
                    "temperatura": l.temperatura,
                    "condutividade": l.condutividade,
                    "alerta_ativo": l.alerta_ativo,
                    "avaliacoes": {
                        "ph": {"nivel": l.ph_nivel, "mensagem": l.ph_mensagem} if l.ph_nivel else None,
                        "umidade": {"nivel": l.umidade_nivel, "mensagem": l.umidade_mensagem} if l.umidade_nivel else None,
                        "temperatura": {"nivel": l.temperatura_nivel, "mensagem": l.temperatura_mensagem} if l.temperatura_nivel else None
                    }
                }
                for l in leituras
            ]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar histórico: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar histórico: {str(e)}"
        )
