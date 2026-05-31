"""
Serviço de Contexto IA
Monta CONTEXTO_IA com dados relevantes para a IA processar
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import uuid4
from sqlalchemy import desc
from sqlalchemy.orm import Session
from app.models.contratos import (
    ContextoIA,
    SensorInfo,
    DecisaoAlerta,
    ClimaHistoricoSemana,
    AlertaHistorico,
    ClimaBruto,
    ClimaProcessado
)
from app.models.database import AlertaDB, LeituraDB, SensorDB, StatusAlerta
from app.models.database import ClienteDB

logger = logging.getLogger(__name__)


class ClienteIANaoEncontrado(ValueError):
    """Cliente informado não existe no contexto persistido da IA."""


class SensorIANaoEncontrado(ValueError):
    """Sensor informado não existe para o cliente no contexto persistido da IA."""


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
        usar_cache: bool = True,
        db: Optional[Session] = None
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
        chave_cache = f"{cliente_id}:{sensor_id}:{hash(pergunta)}:{bool(db)}"
        if usar_cache and chave_cache in self.cache_contexto:
            contexto = self.cache_contexto[chave_cache]
            if contexto["expira_em"] > datetime.now():
                logger.info("✓ Contexto IA retornado do cache")
                return contexto["dados"]
        
        if db and not await self._cliente_existe(cliente_id, db):
            raise ClienteIANaoEncontrado("Cliente não encontrado.")

        # Montar novo contexto
        sensores_relevantes = await self._buscar_sensores_relevantes(cliente_id, sensor_id, db)
        if db and sensor_id and not sensores_relevantes:
            raise SensorIANaoEncontrado("Sensor não encontrado para este cliente.")

        clima_atual = await self._buscar_clima_atual(sensores_relevantes)
        clima_7_dias = await self._buscar_clima_historico(sensores_relevantes, dias=7)
        previsao_7_dias = await self._buscar_previsao(sensores_relevantes)
        alertas_ativos = await self._buscar_alertas_ativos(cliente_id, db)
        alertas_historico = await self._buscar_alertas_historico(cliente_id, dias=30, db=db)
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

    async def _cliente_existe(self, cliente_id: str, db: Session) -> bool:
        """Confirma cliente real sem criar dados artificiais."""
        cliente = db.query(ClienteDB).filter(
            ClienteDB.cliente_id == cliente_id,
            ClienteDB.ativo == True
        ).first()
        if cliente:
            return True

        return db.query(SensorDB).filter(
            SensorDB.cliente_id == cliente_id,
            SensorDB.ativo == True
        ).first() is not None
    
    async def _buscar_sensores_relevantes(
        self,
        cliente_id: str,
        sensor_id: Optional[str] = None,
        db: Optional[Session] = None
    ) -> List[SensorInfo]:
        """Busca sensores relevantes do cliente"""
        if not db:
            logger.info("Contexto IA sem sessão de banco; nenhum sensor real será carregado.")
            return []

        query = db.query(SensorDB).filter(SensorDB.cliente_id == cliente_id, SensorDB.ativo == True)
        if sensor_id:
            query = query.filter(SensorDB.sensor_id == sensor_id)

        sensores_db = query.order_by(desc(SensorDB.criado_em)).limit(10).all()
        sensores = []

        for sensor in sensores_db:
            ultima = db.query(LeituraDB).filter(
                LeituraDB.sensor_id == sensor.sensor_id
            ).order_by(desc(LeituraDB.timestamp)).first()

            sensores.append(SensorInfo(
                sensor_id=sensor.sensor_id,
                nome=sensor.nome,
                propriedade=sensor.propriedade or "Não informado",
                tipo=sensor.tipo or "solo",
                local_especifico=sensor.local_especifico,
                localizacao={
                    "latitude": sensor.latitude,
                    "longitude": sensor.longitude,
                    "municipio": sensor.municipio,
                    "estado": sensor.estado,
                    "local_especifico": sensor.local_especifico,
                },
                ultima_leitura=self._serializar_leitura(ultima) if ultima else None,
                avaliacoes=self._serializar_avaliacoes(ultima) if ultima else {},
            ))

        return sensores
    
    async def _buscar_clima_atual(
        self,
        sensores: List[SensorInfo]
    ) -> Optional[Dict[str, Any]]:
        """Busca clima atual dos sensores"""
        return None
    
    async def _buscar_clima_historico(
        self,
        sensores: List[SensorInfo],
        dias: int = 7
    ) -> Dict[str, ClimaHistoricoSemana]:
        """Busca histórico de clima dos últimos N dias"""
        return {}
    
    async def _buscar_previsao(
        self,
        sensores: List[SensorInfo]
    ) -> List[Dict[str, Any]]:
        """Busca previsão para os próximos 7 dias"""
        return []
    
    async def _buscar_alertas_ativos(
        self,
        cliente_id: str,
        db: Optional[Session] = None
    ) -> List[DecisaoAlerta]:
        """Busca alertas ativos do cliente"""
        if not db:
            return []

        alertas = db.query(AlertaDB).filter(
            AlertaDB.cliente_id == cliente_id,
            AlertaDB.status == StatusAlerta.ATIVO
        ).order_by(desc(AlertaDB.criado_em)).limit(20).all()

        return [
            DecisaoAlerta(
                tipo=getattr(alerta.tipo, "value", alerta.tipo),
                severidade=getattr(alerta.severidade, "value", alerta.severidade),
                mensagem=alerta.mensagem,
                ativa=True,
                desde=alerta.criado_em or datetime.now(),
            )
            for alerta in alertas
        ]
    
    async def _buscar_alertas_historico(
        self,
        cliente_id: str,
        dias: int = 30,
        db: Optional[Session] = None
    ) -> List[AlertaHistorico]:
        """Busca histórico de alertas dos últimos N dias"""
        if not db:
            return []

        data_inicial = datetime.now() - timedelta(days=dias)
        alertas = db.query(AlertaDB).filter(
            AlertaDB.cliente_id == cliente_id,
            AlertaDB.criado_em >= data_inicial
        ).order_by(desc(AlertaDB.criado_em)).limit(50).all()

        return [
            AlertaHistorico(
                tipo=getattr(alerta.tipo, "value", alerta.tipo),
                severidade=getattr(alerta.severidade, "value", alerta.severidade),
                desde=alerta.criado_em or datetime.now(),
                ate=alerta.resolvido_em,
                acao_tomada=alerta.observacao,
            )
            for alerta in alertas
        ]
    
    async def _buscar_plano_agronomo(
        self,
        cliente_id: str
    ) -> Optional[Dict[str, Any]]:
        """Busca plano agronômico do cliente"""
        return None
    
    async def _buscar_conversas_anteriores(
        self,
        cliente_id: str,
        dias: int = 30
    ) -> List[Dict[str, Any]]:
        """Busca histórico de conversas IA dos últimos N dias"""
        return []
    
    def _calcular_prioridades(
        self,
        pergunta: str,
        alertas_ativos: List[Dict[str, Any]],
        clima_7_dias: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calcula prioridades baseado no contexto"""
        prioridades = {
            "é_critico": any(
                self._valor_alerta(a, "severidade") in {"critica", "critico"}
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

    def _valor_alerta(self, alerta: Any, campo: str) -> Any:
        """Lê campo de alerta aceitando dict ou modelo Pydantic."""
        if isinstance(alerta, dict):
            return alerta.get(campo)
        return getattr(alerta, campo, None)
    
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

    def _serializar_leitura(self, leitura: Optional[LeituraDB]) -> Optional[Dict[str, Any]]:
        """Serializa ultima leitura real sem inventar campos."""
        if not leitura:
            return None

        return {
            "timestamp": leitura.timestamp.isoformat() if leitura.timestamp else None,
            "ph": leitura.ph,
            "umidade": leitura.umidade,
            "temperatura": leitura.temperatura,
            "condutividade": leitura.condutividade,
            "nitrogenio": leitura.nitrogenio,
            "fosforo": leitura.fosforo,
            "potassio": leitura.potassio,
            "alerta_ativo": leitura.alerta_ativo,
            "nivel_critico": leitura.nivel_critico,
        }

    def _serializar_avaliacoes(self, leitura: Optional[LeituraDB]) -> Dict[str, Any]:
        """Serializa avaliacoes agronomicas ja calculadas na leitura."""
        if not leitura:
            return {}

        avaliacoes = {}
        for campo, nivel, mensagem in [
            ("ph", leitura.ph_nivel, leitura.ph_mensagem),
            ("umidade", leitura.umidade_nivel, leitura.umidade_mensagem),
            ("temperatura", leitura.temperatura_nivel, leitura.temperatura_mensagem),
            ("nitrogenio", leitura.nitrogenio_nivel, leitura.nitrogenio_mensagem),
            ("fosforo", leitura.fosforo_nivel, leitura.fosforo_mensagem),
            ("potassio", leitura.potassio_nivel, leitura.potassio_mensagem),
        ]:
            if nivel or mensagem:
                avaliacoes[campo] = {
                    "nivel": nivel,
                    "mensagem": mensagem,
                }

        return avaliacoes
    
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
