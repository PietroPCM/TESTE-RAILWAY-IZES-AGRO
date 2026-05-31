"""
Serviço de Integração com Provedores de Clima
"""
import logging
import httpx
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from abc import ABC, abstractmethod
from app.config import settings
from app.models.clima import DadosClimaAtual, PrevisaoClima

logger = logging.getLogger(__name__)


class ProvadorClimaBase(ABC):
    """Classe base para provedores de clima"""
    
    @abstractmethod
    async def obter_clima_atual(self, latitude: float, longitude: float) -> DadosClimaAtual:
        """Obtém clima atual para coordenadas"""
        pass
    
    @abstractmethod
    async def obter_previsao(self, latitude: float, longitude: float, dias: int = 5) -> List[PrevisaoClima]:
        """Obtém previsão de clima"""
        pass


class OpenWeatherMapProvider(ProvadorClimaBase):
    """Integração com OpenWeatherMap"""
    
    BASE_URL = "https://api.openweathermap.org/data/2.5"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def obter_clima_atual(self, latitude: float, longitude: float) -> DadosClimaAtual:
        """Obtém clima atual do OpenWeatherMap"""
        try:
            url = f"{self.BASE_URL}/weather"
            params = {
                "lat": latitude,
                "lon": longitude,
                "appid": self.api_key,
                "units": "metric",
                "lang": "pt_br"
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            return DadosClimaAtual(
                cidade=data.get("name"),
                temperatura_celsius=data["main"]["temp"],
                temperatura_maxima=data["main"]["temp_max"],
                temperatura_minima=data["main"]["temp_min"],
                sensacao_termica=data["main"]["feels_like"],
                umidade_relativa=data["main"]["humidity"],
                pressao_atm=data["main"]["pressure"],
                velocidade_vento=data["wind"]["speed"],
                direcao_vento=self._graus_para_direcao(data["wind"].get("deg", 0)),
                cobertura_nuvens=data["clouds"]["all"],
                precipitacao=data.get("rain", {}).get("1h", 0),
                indice_uv=None,
                visibilidade=data.get("visibility", None),
                condicao=data["weather"][0]["main"].lower(),
                descricao=data["weather"][0]["description"],
                icone=data["weather"][0]["icon"]
            )
        except Exception as e:
            logger.error(f"Erro ao obter clima atual do OpenWeatherMap: {str(e)}")
            raise
    
    async def obter_previsao(self, latitude: float, longitude: float, dias: int = 5) -> List[PrevisaoClima]:
        """Obtém previsão de 5 dias do OpenWeatherMap"""
        try:
            url = f"{self.BASE_URL}/forecast"
            params = {
                "lat": latitude,
                "lon": longitude,
                "appid": self.api_key,
                "units": "metric",
                "lang": "pt_br",
                "cnt": dias * 8  # 8 previsões por dia (3h cada)
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            previsoes = []
            datas_processadas = set()
            
            for item in data["list"]:
                data_str = item["dt_txt"].split(" ")[0]
                
                if data_str not in datas_processadas:
                    datas_processadas.add(data_str)
                    previsoes.append(PrevisaoClima(
                        data=datetime.fromisoformat(item["dt_txt"]),
                        temperatura_maxima=item["main"]["temp_max"],
                        temperatura_minima=item["main"]["temp_min"],
                        condicao=item["weather"][0]["main"].lower(),
                        descricao=item["weather"][0]["description"],
                        precipitacao_probabilidade=int(item.get("pop", 0) * 100),
                        precipitacao_mm=item.get("rain", {}).get("3h", 0),
                        umidade=item["main"]["humidity"],
                        velocidade_vento=item["wind"]["speed"],
                        icone=item["weather"][0]["icon"]
                    ))
            
            return previsoes[:dias]
        except Exception as e:
            logger.error(f"Erro ao obter previsão do OpenWeatherMap: {str(e)}")
            raise
    
    @staticmethod
    def _graus_para_direcao(graus: float) -> str:
        """Converte graus em direção cardinal"""
        direcoes = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                   "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO"]
        indice = int((graus + 11.25) / 22.5) % 16
        return direcoes[indice]
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()


class WeatherAPIProvider(ProvadorClimaBase):
    """Integração com WeatherAPI"""
    
    BASE_URL = "https://api.weatherapi.com/v1"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def obter_clima_atual(self, latitude: float, longitude: float) -> DadosClimaAtual:
        """Obtém clima atual do WeatherAPI"""
        try:
            url = f"{self.BASE_URL}/current.json"
            params = {
                "q": f"{latitude},{longitude}",
                "key": self.api_key,
                "aqi": "no",
                "lang": "pt"
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            current = data["current"]
            
            return DadosClimaAtual(
                cidade=data.get("location", {}).get("name"),
                temperatura_celsius=current["temp_c"],
                temperatura_maxima=None,
                temperatura_minima=None,
                sensacao_termica=current["feelslike_c"],
                umidade_relativa=current["humidity"],
                pressao_atm=current["pressure_mb"],
                velocidade_vento=current["wind_kph"] / 3.6,  # Converter km/h para m/s
                direcao_vento=current["wind_dir"],
                cobertura_nuvens=current["cloud"],
                precipitacao=current.get("precip_mm", 0),
                indice_uv=current.get("uv", None),
                visibilidade=current["vis_km"],
                condicao=current["condition"]["text"].lower(),
                descricao=current["condition"]["text"],
                icone=current["condition"]["icon"]
            )
        except Exception as e:
            logger.error(f"Erro ao obter clima atual do WeatherAPI: {str(e)}")
            raise
    
    async def obter_previsao(self, latitude: float, longitude: float, dias: int = 5) -> List[PrevisaoClima]:
        """Obtém previsão do WeatherAPI"""
        try:
            url = f"{self.BASE_URL}/forecast.json"
            params = {
                "q": f"{latitude},{longitude}",
                "key": self.api_key,
                "days": dias,
                "aqi": "no",
                "lang": "pt"
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            previsoes = []
            for dia in data["forecast"]["forecastday"]:
                previsoes.append(PrevisaoClima(
                    data=datetime.fromisoformat(dia["date"]),
                    temperatura_maxima=dia["day"]["maxtemp_c"],
                    temperatura_minima=dia["day"]["mintemp_c"],
                    condicao=dia["day"]["condition"]["text"].lower(),
                    descricao=dia["day"]["condition"]["text"],
                    precipitacao_probabilidade=dia["day"]["daily_chance_of_rain"],
                    precipitacao_mm=dia["day"]["totalprecip_mm"],
                    umidade=dia["day"]["avg_humidity"],
                    velocidade_vento=dia["day"]["maxwind_kph"] / 3.6,
                    icone=dia["day"]["condition"]["icon"]
                ))
            
            return previsoes
        except Exception as e:
            logger.error(f"Erro ao obter previsão do WeatherAPI: {str(e)}")
            raise
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()


def obter_provador_clima(provedor: str = None, api_key: str = None) -> ProvadorClimaBase:
    """Factory para obter o provedor de clima configurado"""
    provedor = provedor or settings.clima_provedor
    
    if provedor == "openweathermap":
        api_key = api_key or settings.openweathermap_api_key
        if not api_key:
            raise ValueError("OPENWEATHERMAP_API_KEY não configurada")
        return OpenWeatherMapProvider(api_key)
    
    elif provedor == "weatherapi":
        api_key = api_key or settings.weatherapi_api_key
        if not api_key:
            raise ValueError("WEATHERAPI_API_KEY não configurada")
        return WeatherAPIProvider(api_key)
    
    else:
        raise ValueError(f"Provedor de clima não suportado: {provedor}")
