import httpx
import os
from typing import Optional
import time
import logging
import socket

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Use localhost:1026 when accessed from host, orion-mock:8000 when accessed from container
ORION_HOST = os.getenv("ORION_HOST", "orion-mock")
ORION_PORT = os.getenv("ORION_PORT", "8000")

# Resolve hostname to IP to avoid DNS issues
try:
    resolved_ip = socket.gethostbyname(ORION_HOST)
    ORION_URL = f"http://{resolved_ip}:{ORION_PORT}"
    logger.info(f"Resolvido {ORION_HOST} para {resolved_ip}")
except Exception as e:
    ORION_URL = f"http://{ORION_HOST}:{ORION_PORT}"
    logger.warning(f"Erro ao resolver {ORION_HOST}: {e}")

logger.info(f"Configurado ORION_URL: {ORION_URL}")

def criar_sensor(cliente: str, sensor_id: str, data: Optional[dict] = None):
    url = f"{ORION_URL}/ngsi-ld/v1/entities"

    logger.info(f"Criando sensor {sensor_id} para cliente {cliente}")
    logger.info(f"URL: {url}")

    headers = {
        "Content-Type": "application/ld+json",
        "Fiware-Service": cliente
    }

    payload = {
        "id": f"urn:ngsi-ld:IzesSensores:{sensor_id}",
        "type": "IzesSensores",

        "ph": {
            "type": "Property",
            "value": None
        },
        "soilMoisture": {
            "type": "Property",
            "value": None
        },
        "temperature": {
            "type": "Property",
            "value": None
        },
        "electricalConductivity": {
            "type": "Property",
            "value": None
        },

        "@context": [
            "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"
        ]
    }

    # Retry logic
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Tentativa {attempt + 1}/{max_retries}")
            response = httpx.post(url, headers=headers, json=payload, timeout=10.0)
            
            logger.info(f"Resposta: {response.status_code}")
            
            if response.status_code not in (201, 204):
                raise Exception(f"Erro Orion: {response.status_code} - {response.text}")
            
            logger.info("Sensor criado com sucesso")
            return response
        except Exception as e:
            logger.error(f"Erro na tentativa {attempt + 1}: {type(e).__name__}: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                raise Exception(f"Erro ao conectar com Orion após {max_retries} tentativas: {str(e)}")
