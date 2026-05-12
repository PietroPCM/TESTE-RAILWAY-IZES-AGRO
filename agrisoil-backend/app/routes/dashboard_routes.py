"""
Rotas do Dashboard Mobile - Com dados reais do banco
"""

from fastapi import APIRouter, HTTPException, Header, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
import logging
from datetime import datetime, timedelta

from app.db import get_db
from app.repositories.sensor_repository import SensorRepository, LeituraRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard-mobile"])


def validar_app_token(x_app_token: str = Header(...)) -> str:
    """
    Valida token da app mobile
    
    TODO: Implementar validação real contra BD
    Por agora aceita qualquer token iniciado com 'app_'
    """
    if not x_app_token.startswith("app_"):
        raise HTTPException(
            status_code=401,
            detail="Token inválido. Use header X-App-Token"
        )
    return x_app_token


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
                "atualizado_em": datetime.utcnow().isoformat()
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
                    "timestamp": ultima_leitura.timestamp.isoformat() if ultima_leitura else None,
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
            "atualizado_em": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Erro ao buscar dashboard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao buscar dashboard: {str(e)}")


@router.get("/cliente/{cliente_id}/resumo")
async def dashboard_resumo(cliente_id: str):
    """
    Resumo do dashboard com estatísticas gerais para o painel admin (Demo)
    """
    return {
        "total_clientes": 1,
        "total_fazendas": 1,
        "total_talhoes": 2,
        "total_sensores": 5,
        "sensores_ativos": 4,
        "alertas_criticos": 1,
        "alertas_ativos": 3,
        "operacoes_pendentes": 0
    }
