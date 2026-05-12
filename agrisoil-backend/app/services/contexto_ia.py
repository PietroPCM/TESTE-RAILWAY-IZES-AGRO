"""
Serviço de Contexto IA
Monta CONTEXTO_IA com dados relevantes para a IA processar
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import uuid4
from app.models.contratos import (
    ContextoIA,
    SensorInfo,
    ClimaHistoricoSemana,
    AlertaHistorico,
    ClimaBruto,
    ClimaProcessado
)

logger = logging.getLogger(__name__)


class ServicoContextoIA:
    """Monta contexto rico para IA processar"""
    
    def __init__(self, db_service=None):
        """
        Inicializa serviço
        
        Args:
            db_service: Serviço de BD (para acessar histórico)
        """
        self.db_service = db_service
        self.cache_contexto = {}  # Cache TTL 5 min
    
    async def montar_contexto(
        self,
        cliente_id: str,
        pergunta: str,
        sensor_id: Optional[str] = None,
        usar_cache: bool = True
    ) -> ContextoIA:
        """
        Monta CONTEXTO_IA completo para IA processar
        
        Args:
            cliente_id: ID do cliente
            pergunta: Pergunta do usuário
            sensor_id: (Optional) Focar em um sensor específico
            usar_cache: Usar cache se disponível
        
        Returns:
            ContextoIA montado
        """
        logger.info(
            f"Montando contexto IA: cliente={cliente_id}, "
            f"sensor={sensor_id}, pergunta='{pergunta[:50]}...'"
        )
        
        # Verificar cache
        chave_cache = f"{cliente_id}:{sensor_id}:{hash(pergunta)}"
        if usar_cache and chave_cache in self.cache_contexto:
            contexto = self.cache_contexto[chave_cache]
            if contexto["expira_em"] > datetime.now():
                logger.info("✓ Contexto IA retornado do cache")
                return contexto["dados"]
        
        # Montar novo contexto
        sensores_relevantes = await self._buscar_sensores_relevantes(cliente_id, sensor_id)
        clima_atual = await self._buscar_clima_atual(sensores_relevantes)
        clima_7_dias = await self._buscar_clima_historico(sensores_relevantes, dias=7)
        previsao_7_dias = await self._buscar_previsao(sensores_relevantes)
        alertas_ativos = await self._buscar_alertas_ativos(cliente_id)
        alertas_historico = await self._buscar_alertas_historico(cliente_id, dias=30)
        plano_agronomo = await self._buscar_plano_agronomo(cliente_id)
        conversas_anteriores = await self._buscar_conversas_anteriores(cliente_id, dias=30)
        
        # Calcular prioridades
        prioridades = self._calcular_prioridades(
            pergunta,
            alertas_ativos,
            clima_7_dias
        )
        
        # Estimar tokens
        contexto_dict = {
            "cliente_id": cliente_id,
            "pergunta": pergunta,
            "sensores": sensores_relevantes,
            "clima": clima_atual,
            "clima_historico": clima_7_dias,
            "previsao": previsao_7_dias,
            "alertas": alertas_ativos,
            "plano": plano_agronomo
        }
        tokens_estimado = self._estimar_tokens(contexto_dict)
        
        # Criar contexto
        contexto = ContextoIA(
            cliente_id=cliente_id,
            sensor_id=sensor_id,
            usuario_pergunta=pergunta,
            sensores_relevantes=sensores_relevantes,
            clima_atual=clima_atual,
            clima_ultimos_7_dias=clima_7_dias,
            previsao_7_dias=previsao_7_dias,
            alertas_ativos=alertas_ativos,
            alertas_historico_30_dias=alertas_historico,
            plano_agronomo=plano_agronomo,
            conversas_anteriores_30_dias=conversas_anteriores,
            prioridades=prioridades,
            tokens_estimado=tokens_estimado,
            timestamp_coleta=datetime.now()
        )
        
        # Salvar em cache (TTL 5 minutos)
        self.cache_contexto[chave_cache] = {
            "dados": contexto,
            "expira_em": datetime.now() + timedelta(minutes=5)
        }
        
        logger.info(f"✓ Contexto IA montado: {tokens_estimado} tokens estimados")
        return contexto
    
    async def _buscar_sensores_relevantes(
        self,
        cliente_id: str,
        sensor_id: Optional[str] = None
    ) -> List[SensorInfo]:
        """Busca sensores relevantes do cliente"""
        sensores = []
        
        # TODO: Buscar do BD via db_service
        # Por enquanto, exemplo hardcoded
        if sensor_id:
            sensores.append(SensorInfo(
                sensor_id=sensor_id,
                propriedade="Fazenda São João",
                tipo="solo",
                localizacao={
                    "latitude": -15.7801,
                    "longitude": -48.0896,
                    "municipio": "Brasília",
                    "estado": "DF"
                }
            ))
        else:
            # Buscar todos do cliente
            sensores = [
                SensorInfo(
                    sensor_id=f"sensor_{i:03d}",
                    propriedade=f"Propriedade {i}",
                    tipo="solo",
                    localizacao={
                        "latitude": -15.7801,
                        "longitude": -48.0896,
                        "municipio": "Brasília",
                        "estado": "DF"
                    }
                )
                for i in range(1, 4)  # 3 sensores exemplo
            ]
        
        return sensores
    
    async def _buscar_clima_atual(
        self,
        sensores: List[SensorInfo]
    ) -> Optional[Dict[str, Any]]:
        """Busca clima atual dos sensores"""
        # TODO: Buscar do BD
        if sensores:
            return {
                "temperatura": 22.5,
                "umidade": 65,
                "chuva_probabilidade": 30,
                "condicao": "nublado",
                "timestamp": datetime.now().isoformat()
            }
        return None
    
    async def _buscar_clima_historico(
        self,
        sensores: List[SensorInfo],
        dias: int = 7
    ) -> Dict[str, ClimaHistoricoSemana]:
        """Busca histórico de clima dos últimos N dias"""
        historico = {}
        
        # TODO: Buscar do BD
        for sensor in sensores:
            historico[sensor.sensor_id] = ClimaHistoricoSemana(
                temperatura_media=21.2,
                temperatura_min=18.5,
                temperatura_max=26.3,
                umidade_media=62,
                umidade_min=45,
                umidade_max=85,
                chuva_total_mm=2.3,
                dias_com_chuva=1,
                dias_sem_chuva=6,
                vento_medio_kmh=8.5,
                previsao_proximos_dias=[]
            )
        
        return historico
    
    async def _buscar_previsao(
        self,
        sensores: List[SensorInfo]
    ) -> List[Dict[str, Any]]:
        """Busca previsão para os próximos 7 dias"""
        # TODO: Buscar do provedor de clima
        return [
            {
                "dia": "2026-01-21",
                "temperatura_max": 28,
                "temperatura_min": 19,
                "chuva_probabilidade": 20,
                "condicao": "ensolarado"
            },
            {
                "dia": "2026-01-22",
                "temperatura_max": 29,
                "temperatura_min": 20,
                "chuva_probabilidade": 50,
                "condicao": "nublado"
            }
        ]
    
    async def _buscar_alertas_ativos(
        self,
        cliente_id: str
    ) -> List[Dict[str, Any]]:
        """Busca alertas ativos do cliente"""
        # TODO: Buscar do BD
        return [
            {
                "tipo": "seca",
                "severidade": "alta",
                "mensagem": "Risco de seca detectado",
                "desde": datetime.now().isoformat(),
                "ativa": True
            }
        ]
    
    async def _buscar_alertas_historico(
        self,
        cliente_id: str,
        dias: int = 30
    ) -> List[AlertaHistorico]:
        """Busca histórico de alertas dos últimos N dias"""
        # TODO: Buscar do BD
        return [
            AlertaHistorico(
                tipo="seca",
                severidade="alta",
                desde=datetime.now() - timedelta(days=5),
                ate=datetime.now() - timedelta(days=3),
                acao_tomada="Aumentou irrigação"
            )
        ]
    
    async def _buscar_plano_agronomo(
        self,
        cliente_id: str
    ) -> Optional[Dict[str, Any]]:
        """Busca plano agronômico do cliente"""
        # TODO: Buscar do BD
        return {
            "cultura": "Milho",
            "fase": "V6 (6 folhas)",
            "data_plantio": "2025-12-15",
            "data_colheita_prevista": "2026-04-15",
            "ciclo_dias": 120,
            "proximo_evento": {
                "data": "2026-01-25",
                "acao": "Aplicar nitrogênio",
                "detalhes": "200kg/ha de ureia"
            }
        }
    
    async def _buscar_conversas_anteriores(
        self,
        cliente_id: str,
        dias: int = 30
    ) -> List[Dict[str, Any]]:
        """Busca histórico de conversas IA dos últimos N dias"""
        # TODO: Buscar do BD
        return [
            {
                "data": (datetime.now() - timedelta(days=3)).isoformat(),
                "pergunta": "Quanto vai chover essa semana?",
                "resposta": "Previsão de 20-30mm distribuídos em 2 dias"
            }
        ]
    
    def _calcular_prioridades(
        self,
        pergunta: str,
        alertas_ativos: List[Dict[str, Any]],
        clima_7_dias: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calcula prioridades baseado no contexto"""
        prioridades = {
            "é_critico": any(
                a.get("severidade") == "critica" 
                for a in alertas_ativos
            ),
            "é_tempo_sensivel": any(
                palavra in pergunta.lower() 
                for palavra in ["agora", "já", "urgente", "imediato", "hoje"]
            ),
            "tem_alerta_ativo": len(alertas_ativos) > 0,
            "relevancia": 0.85
        }
        
        return prioridades
    
    def _estimar_tokens(self, contexto_dict: Dict[str, Any]) -> int:
        """
        Estima quantidade de tokens que o contexto vai usar
        Regra de ouro: ~4 caracteres = 1 token
        """
        import json
        contexto_str = json.dumps(contexto_dict, default=str)
        # ~4 chars por token
        tokens = len(contexto_str.encode('utf-8')) // 4
        return tokens
    
    def limpar_cache(self):
        """Limpa cache expirado"""
        agora = datetime.now()
        chaves_expiradas = [
            k for k, v in self.cache_contexto.items()
            if v["expira_em"] < agora
        ]
        for chave in chaves_expiradas:
            del self.cache_contexto[chave]
        
        if chaves_expiradas:
            logger.info(f"Limpou {len(chaves_expiradas)} entradas do cache de contexto")


# Instância global
servico_contexto_ia = ServicoContextoIA()
