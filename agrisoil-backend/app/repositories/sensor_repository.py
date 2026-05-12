"""
Repositório para operações de banco de dados com Sensores
"""
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import datetime, timedelta

from app.models.database import SensorDB, LeituraDB
from app.models.sensor import Sensor, LocalizacaoSensor
from app.models.leitura import Leitura


class SensorRepository:
    """Repositório para operações com sensores"""
    
    @staticmethod
    def criar_sensor(db: Session, sensor: Sensor) -> SensorDB:
        """Criar novo sensor no banco"""
        db_sensor = SensorDB(
            sensor_id=sensor.sensor_id,
            cliente_id=sensor.cliente_id,
            nome=sensor.nome,
            tipo=sensor.tipo,
            ativo=sensor.ativo,
            latitude=sensor.localizacao.latitude,
            longitude=sensor.localizacao.longitude,
            propriedade=sensor.localizacao.propriedade,
            municipio=sensor.localizacao.municipio,
            estado=sensor.localizacao.estado,
            local_especifico=sensor.localizacao.local_especifico
        )
        db.add(db_sensor)
        db.commit()
        db.refresh(db_sensor)
        return db_sensor
    
    @staticmethod
    def buscar_por_id(db: Session, sensor_id: str) -> Optional[SensorDB]:
        """Buscar sensor por ID"""
        return db.query(SensorDB).filter(SensorDB.sensor_id == sensor_id).first()
    
    @staticmethod
    def listar_por_cliente(db: Session, cliente_id: str, apenas_ativos: bool = True) -> List[SensorDB]:
        """Listar todos os sensores de um cliente"""
        query = db.query(SensorDB).filter(SensorDB.cliente_id == cliente_id)
        if apenas_ativos:
            query = query.filter(SensorDB.ativo == True)
        return query.order_by(desc(SensorDB.criado_em)).all()
    
    @staticmethod
    def atualizar_sensor(db: Session, sensor_id: str, dados: dict) -> Optional[SensorDB]:
        """Atualizar dados de um sensor"""
        sensor = SensorRepository.buscar_por_id(db, sensor_id)
        if not sensor:
            return None
        
        for key, value in dados.items():
            if hasattr(sensor, key):
                setattr(sensor, key, value)
        
        sensor.atualizado_em = datetime.utcnow()
        db.commit()
        db.refresh(sensor)
        return sensor
    
    @staticmethod
    def desativar_sensor(db: Session, sensor_id: str) -> bool:
        """Desativar um sensor (soft delete)"""
        sensor = SensorRepository.buscar_por_id(db, sensor_id)
        if not sensor:
            return False
        
        sensor.ativo = False
        sensor.atualizado_em = datetime.utcnow()
        db.commit()
        return True


class LeituraRepository:
    """Repositório para operações com leituras"""
    
    @staticmethod
    def salvar_leitura(
        db: Session, 
        sensor_id: str, 
        cliente_id: str,
        leitura: Leitura,
        avaliacoes: dict,
        alerta_ativo: bool,
        nivel_critico: bool
    ) -> LeituraDB:
        """Salvar nova leitura no banco"""
        db_leitura = LeituraDB(
            sensor_id=sensor_id,
            cliente_id=cliente_id,
            ph=leitura.ph,
            umidade=leitura.soilMoisture,
            temperatura=leitura.temperature,
            condutividade=leitura.electricalConductivity,
            # NPK
            nitrogenio=leitura.nitrogen,
            fosforo=leitura.phosphorus,
            potassio=leitura.potassium,
            # Avaliações
            ph_nivel=avaliacoes.get("ph", {}).get("nivel"),
            ph_mensagem=avaliacoes.get("ph", {}).get("mensagem"),
            umidade_nivel=avaliacoes.get("umidade", {}).get("nivel"),
            umidade_mensagem=avaliacoes.get("umidade", {}).get("mensagem"),
            temperatura_nivel=avaliacoes.get("temperatura", {}).get("nivel"),
            temperatura_mensagem=avaliacoes.get("temperatura", {}).get("mensagem"),
            nitrogenio_nivel=avaliacoes.get("nitrogenio", {}).get("nivel"),
            nitrogenio_mensagem=avaliacoes.get("nitrogenio", {}).get("mensagem"),
            fosforo_nivel=avaliacoes.get("fosforo", {}).get("nivel"),
            fosforo_mensagem=avaliacoes.get("fosforo", {}).get("mensagem"),
            potassio_nivel=avaliacoes.get("potassio", {}).get("nivel"),
            potassio_mensagem=avaliacoes.get("potassio", {}).get("mensagem"),
            alerta_ativo=alerta_ativo,
            nivel_critico=nivel_critico
        )
        db.add(db_leitura)
        db.commit()
        db.refresh(db_leitura)
        return db_leitura
    
    @staticmethod
    def buscar_ultima_leitura(db: Session, sensor_id: str) -> Optional[LeituraDB]:
        """Buscar última leitura de um sensor"""
        return db.query(LeituraDB).filter(
            LeituraDB.sensor_id == sensor_id
        ).order_by(desc(LeituraDB.timestamp)).first()
    
    @staticmethod
    def buscar_historico(
        db: Session, 
        sensor_id: str, 
        dias: int = 7,
        limit: int = 1000
    ) -> List[LeituraDB]:
        """Buscar histórico de leituras"""
        data_inicial = datetime.utcnow() - timedelta(days=dias)
        return db.query(LeituraDB).filter(
            LeituraDB.sensor_id == sensor_id,
            LeituraDB.timestamp >= data_inicial
        ).order_by(desc(LeituraDB.timestamp)).limit(limit).all()
    
    @staticmethod
    def buscar_alertas_ativos(db: Session, cliente_id: str, limit: int = 50) -> List[LeituraDB]:
        """Buscar leituras com alertas ativos"""
        return db.query(LeituraDB).filter(
            LeituraDB.cliente_id == cliente_id,
            LeituraDB.alerta_ativo == True
        ).order_by(desc(LeituraDB.timestamp)).limit(limit).all()
    
    @staticmethod
    def contar_alertas_periodo(db: Session, cliente_id: str, dias: int = 7) -> int:
        """Contar alertas em um período"""
        data_inicial = datetime.utcnow() - timedelta(days=dias)
        return db.query(LeituraDB).filter(
            LeituraDB.cliente_id == cliente_id,
            LeituraDB.alerta_ativo == True,
            LeituraDB.timestamp >= data_inicial
        ).count()
