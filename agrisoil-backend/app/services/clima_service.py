"""
Serviço de Clima - Orquestração e Lógica de Negócio
"""
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import httpx
from app.config import settings
from app.models.clima import ClimaCompletoSensor, DadosClimaAtual, PrevisaoClima, RespostaMobileClima
from app.services.clima_provider import obter_provador_clima

logger = logging.getLogger(__name__)


class ServicoClima:
    """Serviço centralizado de clima e previsões"""
    
    def __init__(self):
        self.cache_clima: Dict[str, Dict] = {}
        self.last_update: Dict[str, datetime] = {}
    
    async def obter_clima_sensor(
        self,
        sensor_id: str,
        cliente_id: str,
        latitude: float,
        longitude: float,
        provedor: str = None,
        api_key: str = None
    ) -> ClimaCompletoSensor:
        """Obtém dados completos de clima para um sensor"""
        
        cache_key = f"{sensor_id}_{latitude}_{longitude}"
        
        # Verificar cache
        if cache_key in self.cache_clima:
            ultima_atualizacao = self.last_update.get(cache_key, datetime.now())
            tempo_decorrido = (datetime.now() - ultima_atualizacao).total_seconds() / 60
            
            if tempo_decorrido < settings.cache_clima_minutos:
                logger.debug(f"Retornando clima em cache para {cache_key}")
                return self.cache_clima[cache_key]
        
        try:
            # Obter provedor
            provador = obter_provador_clima(provedor, api_key)
            
            # Buscar dados
            clima_atual = await provador.obter_clima_atual(latitude, longitude)
            previsao = await provador.obter_previsao(latitude, longitude)
            
            # Calcular índices agrícolas
            indice_risco_geada = self._calcular_risco_geada(clima_atual)
            indice_risco_seca = self._calcular_risco_seca(clima_atual)
            alerta_clima = self._gerar_alerta_clima(clima_atual, indice_risco_geada, indice_risco_seca)
            
            # Montar resposta
            clima_completo = ClimaCompletoSensor(
                sensor_id=sensor_id,
                cliente_id=cliente_id,
                localizacao={
                    "latitude": latitude,
                    "longitude": longitude
                },
                timestamp=datetime.now(),
                clima_atual=clima_atual,
                previsao_proximas_horas=previsao[:24],  # Próximas 24h
                indice_risco_geada=indice_risco_geada,
                indice_risco_seca=indice_risco_seca,
                alerta_clima=alerta_clima
            )
            
            # Cache
            self.cache_clima[cache_key] = clima_completo
            self.last_update[cache_key] = datetime.now()
            
            return clima_completo
            
        except Exception as e:
            logger.error(f"Erro ao obter clima para sensor {sensor_id}: {str(e)}")
            raise
    
    def _calcular_risco_geada(self, clima: DadosClimaAtual) -> float:
        """Calcula índice de risco de geada (0-100%)"""
        if clima.temperatura_celsius <= settings.alerta_temp_min:
            return 100.0
        elif clima.temperatura_celsius <= 2:
            return 75.0 - (clima.temperatura_celsius * 12.5)
        elif clima.temperatura_celsius <= 5:
            return 30.0 - ((clima.temperatura_celsius - 2) * 10)
        else:
            return 0.0
    
    def _calcular_risco_seca(self, clima: DadosClimaAtual) -> float:
        """Calcula índice de risco de seca (0-100%)"""
        if clima.umidade_relativa <= settings.alerta_umidade_min:
            return 100.0
        elif clima.umidade_relativa <= 30:
            return 80.0 - ((clima.umidade_relativa - 20) * 8)
        elif clima.umidade_relativa <= 40:
            return 50.0 - ((clima.umidade_relativa - 30) * 5)
        else:
            return 0.0
    
    def _gerar_alerta_clima(
        self,
        clima: DadosClimaAtual,
        risco_geada: float,
        risco_seca: float
    ) -> Optional[str]:
        """Gera alerta de clima se necessário"""
        alertas = []
        
        if risco_geada > 60:
            alertas.append(f"⚠️ Risco de geada: {risco_geada:.0f}%")
        
        if risco_seca > 60:
            alertas.append(f"⚠️ Risco de seca: {risco_seca:.0f}%")
        
        if clima.temperatura_celsius > settings.alerta_temp_max:
            alertas.append(f"🌡️ Calor extremo: {clima.temperatura_celsius}°C")
        
        if clima.umidade_relativa > settings.alerta_umidade_max:
            alertas.append(f"💧 Umidade excessiva: {clima.umidade_relativa}%")
        
        if clima.precipitacao > settings.alerta_chuva_limite_mm:
            alertas.append(f"🌧️ Chuva intensa: {clima.precipitacao}mm")
        
        return " | ".join(alertas) if alertas else None
    
    def _gerar_recomendacoes(self, clima: ClimaCompletoSensor) -> List[str]:
        """Gera recomendações agrícolas baseadas no clima"""
        recomendacoes = []
        
        # Recomendações por temperatura
        if clima.indice_risco_geada and clima.indice_risco_geada > 50:
            recomendacoes.append("🌾 Proteger plantas sensíveis ao frio")
            recomendacoes.append("💨 Preparar sistemas de proteção contra geada")
        
        if clima.clima_atual.temperatura_celsius > settings.ALERTA_TEMP_MAX:
            recomendacoes.append("💧 Aumentar frequência de irrigação")
            recomendacoes.append("☀️ Considerar sombreamento das plantas")
        
        # Recomendações por umidade
        if clima.indice_risco_seca and clima.indice_risco_seca > 60:
            recomendacoes.append("💧 Aplicar irrigação suplementar")
            recomendacoes.append("🌾 Aumentar cobertura do solo")
        
        if clima.clima_atual.umidade_relativa > settings.ALERTA_UMIDADE_MAX:
            recomendacoes.append("🍄 Monitorar doenças fúngicas")
            recomendacoes.append("💨 Melhorar ventilação/drenagem")
        
        # Recomendações por chuva
        if clima.clima_atual.precipitacao > 20:
            recomendacoes.append("🌧️ Evitar aplicações de defensivos")
            recomendacoes.append("🚜 Postergar operações de solo")
        
        # Recomendações por vento
        if clima.clima_atual.velocidade_vento > 5:
            recomendacoes.append("💨 Risco aumentado de deriva de defensivos")
            recomendacoes.append("🌾 Adiar pulverizações")
        
        return recomendacoes
    
    async def formatar_resposta_mobile(
        self,
        clima_completo: ClimaCompletoSensor,
        localizacao: Dict
    ) -> RespostaMobileClima:
        """Formata resposta de clima para app mobile"""
        
        recomendacoes = self._gerar_recomendacoes(clima_completo)
        
        return RespostaMobileClima(
            id_envio=f"{clima_completo.sensor_id}_{int(datetime.now().timestamp())}",
            cliente_id=clima_completo.cliente_id,
            sensor_id=clima_completo.sensor_id,
            propriedade=localizacao.get("propriedade", ""),
            municipio=localizacao.get("municipio", ""),
            local=localizacao.get("local_especifico", ""),
            timestamp=clima_completo.timestamp,
            temperatura_atual=clima_completo.clima_atual.temperatura_celsius,
            condicao=clima_completo.clima_atual.condicao,
            umidade=clima_completo.clima_atual.umidade_relativa,
            vento_velocidade=clima_completo.clima_atual.velocidade_vento,
            chuva_probabilidade=int(clima_completo.previsao_proximas_horas[0].precipitacao_probabilidade if clima_completo.previsao_proximas_horas else 0),
            previsao_dia=clima_completo.previsao_proximas_horas[:5],  # Próximas 5 previsões
            alerta=clima_completo.alerta_clima,
            recomendacoes=recomendacoes
        )
    
    async def enviar_para_webhook(
        self,
        resposta_mobile: RespostaMobileClima,
        webhook_url: str,
        app_token: str
    ) -> bool:
        """Envia dados de clima para webhook do app mobile"""
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {app_token}",
                "X-Client-ID": resposta_mobile.cliente_id
            }
            
            payload = resposta_mobile.model_dump(mode='json')
            
            async with httpx.AsyncClient(timeout=settings.webhook_timeout_segundos) as client:
                for tentativa in range(settings.max_tentativas_webhook):
                    try:
                        response = await client.post(
                            webhook_url,
                            json=payload,
                            headers=headers
                        )
                        response.raise_for_status()
                        logger.info(f"Dados de clima enviados com sucesso para {webhook_url}")
                        return True
                    except httpx.RequestError as e:
                        if tentativa == settings.MAX_TENTATIVAS_WEBHOOK - 1:
                            raise
                        logger.warning(f"Tentativa {tentativa + 1} falhou: {str(e)}")
                        await httpx.AsyncClient().aclose()
        
        except Exception as e:
            logger.error(f"Erro ao enviar dados para webhook: {str(e)}")
            return False
    
    async def processar_sensores_cliente(
        self,
        cliente_id: str,
        sensores: List[Dict],
        config_cliente: Dict
    ) -> List[RespostaMobileClima]:
        """Processa clima para todos os sensores de um cliente"""
        
        respostas = []
        
        for sensor in sensores:
            try:
                clima = await self.obter_clima_sensor(
                    sensor_id=sensor["sensor_id"],
                    cliente_id=cliente_id,
                    latitude=sensor["localizacao"]["latitude"],
                    longitude=sensor["localizacao"]["longitude"],
                    provedor=config_cliente.get("provedor_clima"),
                    api_key=config_cliente.get("chave_api_clima")
                )
                
                resposta = await self.formatar_resposta_mobile(
                    clima,
                    sensor["localizacao"]
                )
                
                respostas.append(resposta)
                
                # Enviar para webhook se configurado
                if config_cliente.get("webhook_url") and config_cliente.get("app_token"):
                    await self.enviar_para_webhook(
                        resposta,
                        config_cliente["webhook_url"],
                        config_cliente["app_token"]
                    )
            
            except Exception as e:
                logger.error(f"Erro ao processar sensor {sensor.get('sensor_id')}: {str(e)}")
                continue
        
        return respostas


# Instância global
servico_clima = ServicoClima()
