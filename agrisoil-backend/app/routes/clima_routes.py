"""
Rotas da API de Clima
"""
import httpx
from fastapi import APIRouter, HTTPException, Query, Header
from typing import List, Optional
import logging
from app.models.sensor import Sensor, LocalizacaoSensor, ClienteConfig
from app.models.clima import (
    ClimaCompletoSensor,
    RespostaClimaAtualLocalizacao,
    RespostaMobileClima,
)
from app.services.clima_service import servico_clima
from app.utils.datetime_utils import utc_iso

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/clima", tags=["clima"])


@router.get("/atual", response_model=RespostaClimaAtualLocalizacao)
async def obter_clima_atual_por_localizacao(
    lat: float = Query(..., ge=-90, le=90, description="Latitude da localizacao"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude da localizacao"),
    provedor: Optional[str] = Query(None, description="Provedor: openweathermap ou weatherapi"),
):
    """
    Obtem clima atual, resumo de previsao e alerta agricola por latitude/longitude.

    Exemplo:
    GET /api/clima/atual?lat=-24.9555&lon=-53.4552
    """
    try:
        return await servico_clima.obter_clima_por_coordenadas(
            latitude=lat,
            longitude=lon,
            provedor=provedor,
        )
    except ValueError as exc:
        logger.error("Erro de configuracao do clima: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        logger.error("Erro HTTP do provedor de clima: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Falha ao consultar o provedor de clima.",
        ) from exc
    except httpx.RequestError as exc:
        logger.error("Erro de conexao com o provedor de clima: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Nao foi possivel conectar ao provedor de clima.",
        ) from exc
    except Exception as exc:
        logger.error("Erro inesperado ao obter clima por localizacao: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao consultar o clima atual.",
        ) from exc


@router.post("/sensor/registrar", response_model=Sensor)
async def registrar_sensor(
    sensor_id: str,
    cliente_id: str,
    nome: str,
    tipo: str,
    latitude: float,
    longitude: float,
    propriedade: str,
    municipio: str,
    estado: str,
    local_especifico: Optional[str] = None
):
    """
    Registra um novo sensor com localização.
    
    Exemplo:
    - sensor_id: "sensor_001"
    - cliente_id: "cliente_agritech"
    - nome: "Sensor Solo Talhão A"
    - tipo: "solo"
    - latitude: -15.7801
    - longitude: -48.0896
    - propriedade: "Fazenda São João"
    - municipio: "Brasília"
    - estado: "DF"
    """
    try:
        localizacao = LocalizacaoSensor(
            latitude=latitude,
            longitude=longitude,
            propriedade=propriedade,
            municipio=municipio,
            estado=estado,
            local_especifico=local_especifico
        )
        
        sensor = Sensor(
            sensor_id=sensor_id,
            cliente_id=cliente_id,
            nome=nome,
            tipo=tipo,
            localizacao=localizacao
        )
        
        logger.info(f"Sensor {sensor_id} registrado para cliente {cliente_id}")
        return sensor
    
    except Exception as e:
        logger.error(f"Erro ao registrar sensor: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sensor/{sensor_id}/clima-atual", response_model=ClimaCompletoSensor)
async def obter_clima_sensor(
    sensor_id: str,
    cliente_id: str = Query(..., description="ID do cliente"),
    latitude: float = Query(..., description="Latitude da localização"),
    longitude: float = Query(..., description="Longitude da localização"),
    provedor: Optional[str] = Query(None, description="Provedor: openweathermap ou weatherapi"),
    api_key: Optional[str] = Query(None, description="API Key do provedor (opcional, usa config)")
):
    """
    Obtém dados climáticos atuais para um sensor específico.
    
    Exemplo de requisição:
    GET /api/clima/sensor/sensor_001/clima-atual?cliente_id=cliente_agritech&latitude=-15.7801&longitude=-48.0896
    """
    try:
        clima = await servico_clima.obter_clima_sensor(
            sensor_id=sensor_id,
            cliente_id=cliente_id,
            latitude=latitude,
            longitude=longitude,
            provedor=provedor,
            api_key=api_key
        )
        return clima
    
    except Exception as e:
        logger.error(f"Erro ao obter clima: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cliente/configurar", response_model=ClienteConfig)
async def configurar_cliente(
    cliente_id: str,
    nome: str,
    email_contato: str,
    provedor_clima: str = "openweathermap",
    frequencia_atualizacao_minutos: int = 30,
    receber_alertas: bool = True,
    webhook_url: Optional[str] = None,
    app_token: Optional[str] = None,
    chave_api_clima: Optional[str] = None
):
    """
    Configura um cliente para receber dados de clima.
    
    Exemplo:
    - cliente_id: "cliente_agritech"
    - nome: "AgriTech Soluções"
    - email_contato: "suporte@agritech.com.br"
    - provedor_clima: "openweathermap"
    - webhook_url: "https://app.agritech.com.br/webhook/clima"
    - app_token: "token_super_secreto_123"
    """
    try:
        config = ClienteConfig(
            cliente_id=cliente_id,
            nome=nome,
            email_contato=email_contato,
            provedor_clima=provedor_clima,
            frequencia_atualizacao_minutos=frequencia_atualizacao_minutos,
            receber_alertas=receber_alertas,
            webhook_url=webhook_url,
            app_token=app_token,
            chave_api_clima=chave_api_clima
        )
        
        logger.info(f"Cliente {cliente_id} configurado com sucesso")
        return config
    
    except Exception as e:
        logger.error(f"Erro ao configurar cliente: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/cliente/{cliente_id}/sensores/clima", response_model=List[RespostaMobileClima])
async def obter_clima_cliente(
    cliente_id: str,
    x_app_token: str = Header(..., description="Token de autenticação do app mobile")
):
    """
    Obtém dados de clima para TODOS os sensores de um cliente.
    
    Usado pelo app mobile para sincronizar dados de todos os sensores registrados.
    
    Headers necessários:
    - X-App-Token: token_do_app_mobile
    
    Exemplo:
    GET /api/clima/cliente/cliente_agritech/sensores/clima
    """
    try:
        # TODO: Implementar busca no banco de dados dos sensores do cliente
        # e suas configurações
        
        # Retorno exemplo (em produção, virá do BD)
        logger.info(f"Retornando clima para {len([])} sensores do cliente {cliente_id}")
        
        return []
    
    except Exception as e:
        logger.error(f"Erro ao obter clima do cliente: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sensor/{sensor_id}/alerta", response_model=dict)
async def verificar_alerta_sensor(
    sensor_id: str,
    cliente_id: str = Query(...),
    latitude: float = Query(...),
    longitude: float = Query(...)
):
    """
    Verifica se há alertas climáticos para um sensor.
    
    Retorna alerta e recomendações agrícolas.
    """
    try:
        clima = await servico_clima.obter_clima_sensor(
            sensor_id=sensor_id,
            cliente_id=cliente_id,
            latitude=latitude,
            longitude=longitude
        )
        
        recomendacoes = servico_clima._gerar_recomendacoes(clima)
        
        return {
            "sensor_id": sensor_id,
            "tem_alerta": clima.alerta_clima is not None,
            "alerta": clima.alerta_clima,
            "risco_geada": clima.indice_risco_geada,
            "risco_seca": clima.indice_risco_seca,
            "recomendacoes": recomendacoes
        }
    
    except Exception as e:
        logger.error(f"Erro ao verificar alerta: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook/teste")
async def testar_webhook(
    webhook_url: str,
    app_token: str
):
    """
    Testa a configuração de webhook enviando dados de teste.
    
    Útil para validar se o app mobile está recebendo dados corretamente.
    """
    try:
        from app.models.clima import RespostaMobileClima, DadosClimaAtual, PrevisaoClima
        from datetime import datetime
        
        # Simular resposta de teste
        teste_resposta = RespostaMobileClima(
            id_envio="teste_webhook_001",
            cliente_id="teste",
            sensor_id="sensor_teste",
            propriedade="Propriedade Teste",
            municipio="Brasília",
            local="Talhão A",
            timestamp=datetime.now(),
            temperatura_atual=22.5,
            condicao="nublado",
            umidade=65,
            vento_velocidade=2.5,
            chuva_probabilidade=30,
            previsao_dia=[],
            alerta=None,
            recomendacoes=["Teste de webhook bem-sucedido"]
        )
        
        sucesso = await servico_clima.enviar_para_webhook(
            teste_resposta,
            webhook_url,
            app_token
        )
        
        return {
            "sucesso": sucesso,
            "mensagem": "Webhook testado com sucesso!" if sucesso else "Falha ao enviar para webhook"
        }
    
    except Exception as e:
        logger.error(f"Erro ao testar webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/saude")
async def health_check():
    """Verifica saúde da API de clima"""
    return {
        "status": "ok",
        "servico": "API de Clima",
        "timestamp": utc_iso(__import__('datetime').datetime.utcnow())
    }
