"""
Motor de Regras - Processa CLIMA_BRUTO e gera CLIMA_TRATADO
Aplica lógica de negócio e decisões
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from app.models.contratos import (
    ClimaBruto, 
    ClimaProcessado, 
    DecisaoAlerta, 
    RecomendacaoAcao
)

logger = logging.getLogger(__name__)


class MotorRegras:
    """Motor de regras que processa clima bruto e gera decisões"""
    
    def __init__(self):
        """Inicializa configurações das regras"""
        self.regras = self._carregar_regras()
        
    def _carregar_regras(self) -> Dict[str, Dict[str, Any]]:
        """Carrega configurações de regras"""
        return {
            "geada": {
                "condicao": lambda temp, **kw: temp <= -1,
                "severidade": "critica",
                "mensagem": lambda temp, **kw: f"CRÍTICO: Risco de geada! Temperatura {temp}°C. Proteja plantas sensíveis IMEDIATAMENTE!",
                "acao": "Ativar sistema de proteção contra geada, ligar aspersores ou aquecedores",
                "acao_secundarias": ["Monitorar continuamente", "Avisar vizinhos"],
                "urgencia": "critica",
                "prazo_horas": 0.5
            },
            "seca": {
                "condicao": lambda umidade, chuva_prob=0, **kw: umidade <= 20 and chuva_prob < 10,
                "severidade": "alta",
                "mensagem": lambda umidade, **kw: f"ALERTA: Risco de seca! Umidade {umidade}%, chuva improvável",
                "acao": "Aumentar frequência de irrigação em 30-50%",
                "acao_secundarias": ["Monitorar umidade do solo", "Revisar sistema de irrigação"],
                "urgencia": "alta",
                "prazo_horas": 2
            },
            "umidade_excessiva": {
                "condicao": lambda umidade, **kw: umidade >= 90,
                "severidade": "media",
                "mensagem": lambda umidade, **kw: f"AVISO: Umidade excessiva {umidade}%. Risco de doenças fúngicas",
                "acao": "Melhorar ventilação, drenar solo, evitar irrigação",
                "acao_secundarias": ["Inspecionar plantas", "Preparar fungicida se necessário"],
                "urgencia": "alta",
                "prazo_horas": 6
            },
            "calor_intenso": {
                "condicao": lambda temp, **kw: temp >= 35,
                "severidade": "media",
                "mensagem": lambda temp, **kw: f"AVISO: Calor intenso {temp}°C! Plantas sob estresse",
                "acao": "Aumentar irrigação, aplicar sombra se possível, pulverizar folhas",
                "acao_secundarias": ["Manter solo úmido", "Monitorar murcha de plantas"],
                "urgencia": "alta",
                "prazo_horas": 4
            },
            "chuva": {
                "condicao": lambda chuva_prob=0, **kw: chuva_prob >= 50,
                "severidade": "baixa",
                "mensagem": lambda chuva_prob=0, **kw: f"INFO: Chuva prevista com {chuva_prob}% de probabilidade",
                "acao": "Aguarde antes de irrigar, aproveite água da chuva",
                "acao_secundarias": ["Preparar drenagem", "Não adubar antes da chuva"],
                "urgencia": "normal",
                "prazo_horas": 24
            }
        }
    
    def processar_clima(
        self, 
        clima_bruto: ClimaBruto,
        historico_7_dias: Optional[List[ClimaBruto]] = None
    ) -> ClimaProcessado:
        """
        Processa CLIMA_BRUTO e gera CLIMA_TRATADO
        
        Args:
            clima_bruto: Dados brutos do provedor
            historico_7_dias: Últimos 7 dias de clima (para contexto)
        
        Returns:
            ClimaProcessado com decisões
        """
        logger.info(f"Processando clima para sensor {clima_bruto.sensor_id}")
        
        # Preparar contexto
        contexto = {
            "temp": clima_bruto.temperatura_celsius,
            "umidade": clima_bruto.umidade_relativa,
            "chuva_prob": self._calcular_chuva_probabilidade(clima_bruto),
            "vento": clima_bruto.velocidade_vento_kmh,
            "pressao": clima_bruto.pressao_atm,
            "condicao": clima_bruto.condicao,
            "historico": historico_7_dias or []
        }
        
        # Aplicar regras e encontrar alerta
        alerta_tipo, alerta_sev, alerta_msg, regras_disparadas = self._aplicar_regras(contexto)
        
        # Gerar recomendação
        recomendacao = self._gerar_recomendacao(
            alerta_tipo, 
            alerta_sev, 
            contexto, 
            historico_7_dias
        )
        
        # Calcular confiança
        confianca = self._calcular_confianca(alerta_tipo, contexto, historico_7_dias)
        
        # Criar objeto CLIMA_TRATADO
        clima_tratado = ClimaProcessado(
            sensor_id=clima_bruto.sensor_id,
            cliente_id=clima_bruto.cliente_id,
            alerta=DecisaoAlerta(
                tipo=alerta_tipo,
                severidade=alerta_sev,
                mensagem=alerta_msg,
                ativa=alerta_tipo is not None,
                desde=datetime.now()
            ),
            recomendacao=recomendacao,
            confianca_decisao=confianca,
            regras_disparadas=regras_disparadas,
            historico_considerado_dias=7 if historico_7_dias else 0
        )
        
        logger.info(
            f"Clima processado: sensor={clima_bruto.sensor_id}, "
            f"alerta={alerta_tipo}, confianca={confianca:.2%}"
        )
        
        return clima_tratado
    
    def _aplicar_regras(self, contexto: Dict[str, Any]) -> tuple:
        """
        Aplica todas as regras ao contexto
        Retorna: (tipo_alerta, severidade, mensagem, regras_disparadas)
        """
        regras_disparadas = []
        alerta_tipo = None
        alerta_sev = "baixa"
        alerta_msg = "Condições normais"
        
        # Aplicar regras em ordem de severidade (crítica -> normal)
        ordem_severidade = ["critica", "alta", "media", "baixa"]
        
        for nome_regra, config in self.regras.items():
            try:
                # Verificar se regra dispara
                if config["condicao"](**contexto):
                    regras_disparadas.append(nome_regra)
                    
                    # Se severidade >= alerta_sev, atualiza
                    if self._severidade_valor(config["severidade"]) >= self._severidade_valor(alerta_sev):
                        alerta_tipo = nome_regra
                        alerta_sev = config["severidade"]
                        alerta_msg = config["mensagem"](**contexto)
                        
                        # Para na primeira severidade crítica
                        if config["severidade"] == "critica":
                            break
            except Exception as e:
                logger.error(f"Erro ao aplicar regra {nome_regra}: {e}")
        
        return alerta_tipo, alerta_sev, alerta_msg, regras_disparadas
    
    def _gerar_recomendacao(
        self, 
        alerta_tipo: Optional[str], 
        severidade: str,
        contexto: Dict[str, Any],
        historico: Optional[List[ClimaBruto]]
    ) -> RecomendacaoAcao:
        """Gera recomendação de ação baseada no alerta"""
        if not alerta_tipo or alerta_tipo not in self.regras:
            return RecomendacaoAcao(
                principal="Monitorar condições",
                secundarias=[],
                urgencia="normal"
            )
        
        config = self.regras[alerta_tipo]
        
        return RecomendacaoAcao(
            principal=config["acao"],
            secundarias=config.get("acao_secundarias", []),
            urgencia=config.get("urgencia", "normal"),
            prazo_horas=config.get("prazo_horas")
        )
    
    def _calcular_confianca(
        self, 
        alerta_tipo: Optional[str],
        contexto: Dict[str, Any],
        historico: Optional[List[ClimaBruto]]
    ) -> float:
        """
        Calcula confiança da decisão
        Fatores: confirmação de dados, consistência histórica, múltiplas regras
        """
        confianca = 0.5  # Base 50%
        
        # Se não há alerta, confiança máxima em condições normais
        if not alerta_tipo:
            return 0.95
        
        # Aumentar por cada regra disparada
        num_regras = len([r for r in self.regras if self.regras[r]["condicao"](**contexto)])
        confianca += (num_regras * 0.1)
        
        # Aumentar se há consistência histórica
        if historico and len(historico) > 3:
            confianca += 0.15
        
        # Cap em 0.95
        return min(0.95, confianca)
    
    def _calcular_chuva_probabilidade(self, clima: ClimaBruto) -> int:
        """Calcula probabilidade de chuva a partir dos dados"""
        # Se há precipitação registrada, alta probabilidade
        if clima.precipitacao_mm > 0:
            return 100
        
        # Baseado em cobertura de nuvens e umidade
        prob = (clima.cobertura_nuvens_percent * 0.5) + (max(0, clima.umidade_relativa - 60) * 0.5)
        
        return min(100, int(prob))
    
    def _severidade_valor(self, severidade: str) -> int:
        """Converte severidade em valor numérico para comparação"""
        mapa = {"baixa": 1, "media": 2, "alta": 3, "critica": 4}
        return mapa.get(severidade, 0)
    
    def processar_lote(
        self,
        climas_brutos: List[ClimaBruto],
        cliente_id: str
    ) -> List[ClimaProcessado]:
        """
        Processa vários climas de um cliente
        Útil para atualizar todos os sensores de uma vez
        """
        resultados = []
        
        logger.info(f"Processando lote de {len(climas_brutos)} climas para cliente {cliente_id}")
        
        for clima_bruto in climas_brutos:
            try:
                clima_processado = self.processar_clima(clima_bruto)
                resultados.append(clima_processado)
            except Exception as e:
                logger.error(f"Erro ao processar clima {clima_bruto.sensor_id}: {e}")
        
        return resultados


# Instância global
motor_regras = MotorRegras()
