"""
MOTOR DE REGRAS - Aplicador de contexto em 3 camadas

Fluxo:
1. Dados chegam do sensor
2. Identifica zona/cultura/fase (Camada 1 + 2)
3. Aplica regras contextualizadas (Camada 3)
4. Gera alerta (ou não)
5. IA explica ao produtor
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List
from app.models.contexto_fixo import NomeCultura, FaseFenologica, ParametroIdeal
from app.models.fase_cultura import FaseAtual
from app.models.regra_alerta import (
    RegradeAlerta,
    AplicacaoRegra,
    AlertaGerado,
    AcaoRecomendada
)

logger = logging.getLogger(__name__)


class MotorRegras:
    """Motor central de aplicação de regras contextualizadas"""
    
    def __init__(self, db_session):
        """
        Args:
            db_session: Sessão do banco de dados
        """
        self.db = db_session
    
    # ========================================================================
    # PASSO 1: IDENTIFICAR CONTEXTO FIXO (Camada 1)
    # ========================================================================
    
    def obter_contexto_zona(self, zona_id: str):
        """
        Obtém o contexto fixo de uma zona:
        - Cultura
        - Tipo de solo
        - Profundidade sensor
        - Objetivo
        """
        # TODO: Query no banco
        # return zona com cultura, solo, etc
        pass
    
    # ========================================================================
    # PASSO 2: IDENTIFICAR FASE ATUAL (Camada 2)
    # ========================================================================
    
    def obter_fase_atual(self, zona_id: str) -> Optional[FaseAtual]:
        """
        Detecta fase atual da cultura:
        - Baseado em data de plantio
        - Ou graus-dia acumulado
        - Ou observação manual
        """
        # TODO: Query no banco, buscar FaseAtual da zona
        # return fase_atual
        pass
    
    def detectar_fase_por_data_plantio(
        self,
        data_plantio: datetime,
        cultura: NomeCultura
    ) -> FaseFenologica:
        """Detecta fase baseado em dias após plantio"""
        dias_apos_plantio = (datetime.now() - data_plantio).days
        
        # TODO: Buscar calendário de fases da cultura
        # Por hora, exemplo simplificado
        
        if dias_apos_plantio < 15:
            return FaseFenologica.EMERGENCIA
        elif dias_apos_plantio < 45:
            return FaseFenologica.VEGETATIVO
        elif dias_apos_plantio < 65:
            return FaseFenologica.FLORESCIMENTO
        else:
            return FaseFenologica.ENCHIMENTO_GRAOS
    
    # ========================================================================
    # PASSO 3: APLICAR REGRAS (Camada 3)
    # ========================================================================
    
    def aplicar_regras(
        self,
        sensor_id: str,
        zona_id: str,
        parametro: str,
        valor_medido: float,
        unidade: str
    ) -> List[AlertaGerado]:
        """
        Aplica regras contextualizadas para um dado de sensor
        
        Returns:
            Lista de alertas gerados (pode ser vazia)
        """
        alertas = []
        
        # 1. Obter contexto fixo
        zona = self.obter_contexto_zona(zona_id)
        if not zona:
            logger.warning(f"Zona {zona_id} não encontrada")
            return alertas
        
        # 2. Obter fase atual
        fase_atual = self.obter_fase_atual(zona_id)
        if not fase_atual:
            logger.warning(f"Fase não detectada para zona {zona_id}")
            return alertas
        
        # 3. Buscar regras aplicáveis
        regras = self._buscar_regras(
            cultura=zona.cultura,
            fase=fase_atual.fase,
            parametro=parametro
        )
        
        if not regras:
            logger.debug(f"Nenhuma regra encontrada para {zona.cultura}/{fase_atual.fase}/{parametro}")
            return alertas
        
        # 4. Aplicar cada regra
        for regra in regras:
            alerta = self._aplicar_regra_individual(
                regra=regra,
                sensor_id=sensor_id,
                zona_id=zona_id,
                valor_medido=valor_medido,
                unidade=unidade
            )
            
            if alerta:
                alertas.append(alerta)
        
        return alertas
    
    def _buscar_regras(
        self,
        cultura: NomeCultura,
        fase: FaseFenologica,
        parametro: str
    ) -> List[RegradeAlerta]:
        """Busca regras ativas para cultura/fase/parâmetro"""
        # TODO: Query no banco
        # SELECT * FROM regras WHERE cultura=? AND fase=? AND parametro=? AND ativo=true
        pass
    
    def _aplicar_regra_individual(
        self,
        regra: RegradeAlerta,
        sensor_id: str,
        zona_id: str,
        valor_medido: float,
        unidade: str
    ) -> Optional[AlertaGerado]:
        """
        Aplica uma regra específica
        
        Lógica:
        1. Verificar se valor está fora de limites
        2. Verificar se duração mínima foi atingida
        3. Se sim, gerar alerta
        """
        
        # Checkar limites
        dentro_ideal = (
            regra.minimo_alerta <= valor_medido <= regra.maximo_alerta
        )
        
        if dentro_ideal:
            # Sem alerta
            return None
        
        # Determinar severidade
        if valor_medido < regra.minimo_critico or valor_medido > regra.maximo_critico:
            severidade = "critico"
        else:
            severidade = "alto"
        
        # TODO: Verificar duração
        # - Buscar últimas leituras (últimas 24h por ex)
        # - Contar quantas estão fora do limite
        # - Se >= duracao_minima_horas, disparar
        
        # Por enquanto, dispara imediatamente (simplificado)
        tempo_fora = 1  # Assumir 1 hora
        
        if tempo_fora < regra.duracao_minima_horas:
            # Ainda não atingiu duração mínima
            return None
        
        # GERAR ALERTA
        alerta = AlertaGerado(
            id=f"alerta-{sensor_id}-{zona_id}-{regra.id}-{datetime.now().timestamp()}",
            regra_id=regra.id,
            sensor_id=sensor_id,
            zona_id=zona_id,
            cultura=regra.cultura,
            fase=regra.fase,
            
            titulo=regra.titulo_alerta,
            mensagem_produtor=regra.mensagem_produtor,
            impacto_na_fase=regra.impacto_na_fase,
            
            severidade=severidade,
            parametro=regra.parametro,
            valor_medido=valor_medido,
            
            acao_recomendada=regra.acao_recomendada,
            urgencia_acao=regra.urgencia_acao,
            
            criado_em=datetime.now(),
            status="novo"
        )
        
        logger.info(f"Alerta gerado: {alerta.id}")
        return alerta
    
    # ========================================================================
    # SUPORTE: Buscar histórico de valores
    # ========================================================================
    
    def obter_historico_parametro(
        self,
        sensor_id: str,
        parametro: str,
        horas: int = 24
    ) -> List[tuple]:
        """
        Obtém histórico de um parâmetro
        
        Returns:
            Lista de (timestamp, valor)
        """
        # TODO: Query no banco
        # SELECT timestamp, valor FROM leituras
        # WHERE sensor_id=? AND parametro=?
        # AND timestamp > now() - interval '? hours'
        pass
    
    def contar_leituras_fora_limite(
        self,
        sensor_id: str,
        parametro: str,
        minimo: float,
        maximo: float,
        horas: int = 24
    ) -> int:
        """Conta quantas leituras estão fora dos limites"""
        historico = self.obter_historico_parametro(sensor_id, parametro, horas)
        
        fora_limite = sum(
            1 for _, valor in historico
            if valor < minimo or valor > maximo
        )
        
        return fora_limite


# ============================================================================
# EXEMPLO DE USO
# ============================================================================

"""
# Instanciar o motor
motor = MotorRegras(db_session)

# Quando chega leitura do sensor
alertas = motor.aplicar_regras(
    sensor_id="sensor-001",
    zona_id="zona-soja-norte",
    parametro="umidade",
    valor_medido=18.5,  # Está baixo!
    unidade="%"
)

# alertas será uma lista com alertas gerados (ou vazia)
for alerta in alertas:
    print(f"{alerta.titulo}: {alerta.mensagem_produtor}")
    print(f"Ação recomendada: {alerta.acao_recomendada}")
    print(f"IA deve explicar: {alerta.template_explicacao_ia}")
"""
