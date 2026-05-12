"""
Serviço de orquestração para sensores
Aplica regras e coordena ações
"""
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.rules.ph_rules import avaliar_ph
from app.rules.moisture_rules import avaliar_umidade
from app.rules.temperature_rules import avaliar_temperatura
from app.rules.nitrogen_rules import avaliar_nitrogenio
from app.rules.phosphorus_rules import avaliar_fosforo
from app.rules.potassium_rules import avaliar_potassio
from app.models.leitura import Leitura
from app.models.database import TipoAlerta
from app.services.alerta_service import criar_alerta_automatico, resolver_alertas_automaticamente

logger = logging.getLogger(__name__)


def processar_leitura(
    sensor_id: str, 
    cliente: str, 
    leitura: Leitura,
    db: Optional[Session] = None,
    leitura_id: Optional[int] = None
) -> dict:
    """
    Processa uma leitura de sensor aplicando todas as regras de negócio.
    Agora também cria alertas automaticamente no banco de dados.
    
    Args:
        sensor_id: ID do sensor
        cliente: Cliente dono do sensor
        leitura: Dados da leitura
        db: Sessão do banco de dados (opcional, para criar alertas)
        leitura_id: ID da leitura no banco (opcional, para vincular alertas)
    
    Returns:
        Dicionário com resultados das avaliações
    """
    logger.info(f"Processando leitura do sensor {sensor_id} para cliente {cliente}")
    
    # Avaliar cada parâmetro com suas respectivas regras
    resultado_ph = avaliar_ph(leitura.ph)
    resultado_umidade = avaliar_umidade(leitura.soilMoisture)
    resultado_temperatura = avaliar_temperatura(leitura.temperature)
    resultado_nitrogenio = avaliar_nitrogenio(leitura.nitrogen)
    resultado_fosforo = avaliar_fosforo(leitura.phosphorus)
    resultado_potassio = avaliar_potassio(leitura.potassium)
    
    # Criar alertas automáticos se db e leitura_id forem fornecidos
    alertas_criados = []
    if db and leitura_id:
        parametros = [
            (TipoAlerta.PH, resultado_ph, leitura.ph),
            (TipoAlerta.UMIDADE, resultado_umidade, leitura.soilMoisture),
            (TipoAlerta.TEMPERATURA, resultado_temperatura, leitura.temperature),
            (TipoAlerta.NITROGENIO, resultado_nitrogenio, leitura.nitrogen),
            (TipoAlerta.FOSFORO, resultado_fosforo, leitura.phosphorus),
            (TipoAlerta.POTASSIO, resultado_potassio, leitura.potassium),
        ]
        
        for tipo, resultado, valor in parametros:
            if not resultado:
                continue
                
            nivel = resultado.get("nivel")
            
            # Se está ok/ideal, resolver alertas antigos deste tipo
            if nivel in ["ok", "ideal"]:
                resolver_alertas_automaticamente(db, sensor_id, tipo)
                continue
            
            # Se tem problema, criar alerta
            if resultado.get("alerta", False):
                alerta = criar_alerta_automatico(
                    db=db,
                    sensor_id=sensor_id,
                    cliente_id=cliente,
                    leitura_id=leitura_id,
                    tipo=tipo,
                    nivel=nivel,
                    mensagem=resultado.get("mensagem", ""),
                    valor_medido=valor,
                    valor_referencia=resultado.get("referencia"),
                    recomendacao=resultado.get("acao")
                )
                if alerta:
                    alertas_criados.append(alerta.id)
    
    # Verificar se há algum alerta ativo
    alerta_ativo = any([
        resultado_ph.get("alerta", False),
        resultado_umidade.get("alerta", False),
        resultado_temperatura.get("alerta", False),
        resultado_nitrogenio.get("alerta", False),
        resultado_fosforo.get("alerta", False),
        resultado_potassio.get("alerta", False)
    ])
    
    resultado = {
        "sensor_id": sensor_id,
        "cliente": cliente,
        "timestamp": datetime.now().isoformat(),
        "valores_lidos": {
            "ph": leitura.ph,
            "umidade": leitura.soilMoisture,
            "temperatura": leitura.temperature,
            "condutividade": leitura.electricalConductivity,
            "nitrogenio": leitura.nitrogen,
            "fosforo": leitura.phosphorus,
            "potassio": leitura.potassium
        },
        "avaliacoes": {
            "ph": resultado_ph,
            "umidade": resultado_umidade,
            "temperatura": resultado_temperatura,
            "nitrogenio": resultado_nitrogenio,
            "fosforo": resultado_fosforo,
            "potassio": resultado_potassio
        },
        "alerta_ativo": alerta_ativo,
        "nivel_critico": any([
            resultado_ph.get("nivel") == "critico",
            resultado_umidade.get("nivel") == "critico",
            resultado_temperatura.get("nivel") == "critico",
            resultado_nitrogenio.get("nivel") == "critico",
            resultado_fosforo.get("nivel") == "critico",
            resultado_potassio.get("nivel") == "critico"
        ]),
        "alertas_criados": alertas_criados  # IDs dos alertas criados
    }
    
    if alerta_ativo:
        logger.warning(f"ALERTA ATIVO no sensor {sensor_id}: {len(alertas_criados)} alertas criados")
    
    return resultado
