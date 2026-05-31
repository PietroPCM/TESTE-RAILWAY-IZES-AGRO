"""
Rotas do Dashboard Mobile - Com dados reais do banco
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import logging
from datetime import datetime, timedelta

from app.db import get_db
from app.models.database import AlertaDB, SensorDB, StatusAlerta, SeveridadeAlerta
from app.repositories.sensor_repository import SensorRepository, LeituraRepository
from app.security import verificar_app_internal_token
from app.utils.datetime_utils import utc_iso

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard-mobile"])


validar_app_token = verificar_app_internal_token


@router.get("/cliente/{cliente_id}/sensores")
async def dashboard_sensores(
    cliente_id: str,
    db: Session = Depends(get_db)
):
    """
    Dashboard principal com dados reais dos sensores
    
    Retorna:
    - Lista de sensores
    - Última leitura de cada sensor
    - Alertas ativos
    - Estatísticas gerais
    """
    try:
        logger.info(f"Dashboard solicitado para cliente: {cliente_id}")
        
        # Buscar todos os sensores do cliente
        sensores = SensorRepository.listar_por_cliente(db, cliente_id, apenas_ativos=True)
        
        if not sensores:
            return {
                "cliente_id": cliente_id,
                "total_sensores": 0,
                "sensores": [],
                "alertas_ativos": 0,
                "atualizado_em": utc_iso(datetime.utcnow())
            }
        
        # Buscar dados de cada sensor
        sensores_data = []
        total_alertas = 0
        
        for sensor in sensores:
            # Última leitura
            ultima_leitura = LeituraRepository.buscar_ultima_leitura(db, sensor.sensor_id)
            
            if ultima_leitura and ultima_leitura.alerta_ativo:
                total_alertas += 1
            
            sensores_data.append({
                "sensor_id": sensor.sensor_id,
                "nome": sensor.nome,
                "propriedade": sensor.propriedade or "N/A",
                "municipio": sensor.municipio or "N/A",
                "estado": sensor.estado or "N/A",
                "ultima_leitura": {
                    "timestamp": utc_iso(ultima_leitura.timestamp) if ultima_leitura else None,
                    "temperatura": ultima_leitura.temperatura if ultima_leitura else None,
                    "umidade": ultima_leitura.umidade if ultima_leitura else None,
                    "ph": ultima_leitura.ph if ultima_leitura else None,
                    "alerta_ativo": ultima_leitura.alerta_ativo if ultima_leitura else False,
                    "nivel_critico": ultima_leitura.nivel_critico if ultima_leitura else False
                } if ultima_leitura else None
            })
        
        return {
            "cliente_id": cliente_id,
            "total_sensores": len(sensores),
            "sensores": sensores_data,
            "alertas_ativos": total_alertas,
            "atualizado_em": utc_iso(datetime.utcnow())
        }
    
    except Exception as e:
        logger.error(f"Erro ao buscar dashboard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao buscar dashboard: {str(e)}")


@router.get("/cliente/{cliente_id}/resumo")
async def dashboard_resumo(
    cliente_id: str,
    db: Session = Depends(get_db),
):
    """
    Resumo do dashboard com estatísticas reais disponíveis no banco.
    """
    try:
        sensores_query = db.query(SensorDB).filter(SensorDB.cliente_id == cliente_id)
        total_sensores = sensores_query.count()
        sensores_ativos = sensores_query.filter(SensorDB.ativo.is_(True)).count()
        propriedades = {
            sensor.propriedade
            for sensor in sensores_query.all()
            if sensor.propriedade
        }

        desde = datetime.utcnow() - timedelta(days=7)
        alertas_query = db.query(AlertaDB).filter(AlertaDB.cliente_id == cliente_id)
        alertas_ativos = alertas_query.filter(AlertaDB.status == StatusAlerta.ATIVO).count()
        alertas_criticos = alertas_query.filter(
            AlertaDB.status == StatusAlerta.ATIVO,
            AlertaDB.severidade == SeveridadeAlerta.CRITICO,
        ).count()
        alertas_ultimos_7_dias = alertas_query.filter(AlertaDB.criado_em >= desde).count()

        return {
            "cliente_id": cliente_id,
            "total_clientes": 1 if total_sensores or alertas_query.first() else 0,
            "total_fazendas": len(propriedades),
            "total_talhoes": None,
            "total_sensores": total_sensores,
            "sensores_ativos": sensores_ativos,
            "alertas_criticos": alertas_criticos,
            "alertas_ativos": alertas_ativos,
            "alertas_ultimos_7_dias": alertas_ultimos_7_dias,
            "operacoes_pendentes": 0,
            "dados_reais": True,
            "observacao": "Resumo calculado a partir de sensores e alertas existentes no banco.",
            "atualizado_em": utc_iso(datetime.utcnow()),
        }
    except Exception as e:
        logger.error(f"Erro ao buscar resumo do dashboard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao buscar resumo do dashboard")
