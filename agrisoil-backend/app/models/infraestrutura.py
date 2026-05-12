"""
MODELO DE INFRAESTRUTURA DA PROPRIEDADE
Contextualiza alertas baseado no que o produtor REALMENTE possui
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class TipoIrrigacao(str, Enum):
    """Tipos de sistema de irrigação disponíveis"""
    PIVO_CENTRAL = "pivo_central"
    ASPERSAO = "aspersao"
    GOTEJAMENTO = "gotejamento"
    MICROASPERSAO = "microaspersao"
    SULCO = "sulco"
    INUNDACAO = "inundacao"
    NAO_POSSUI = "nao_possui"


class TipoAplicacao(str, Enum):
    """Equipamentos para aplicação de insumos"""
    PULVERIZADOR_COSTAL = "pulverizador_costal"
    PULVERIZADOR_TRATORIZADO = "pulverizador_tratorizado"
    AERONAVE = "aeronave"
    DISTRIBUIDOR_ADUBO = "distribuidor_adubo"
    CALCAREADEIRA = "calcareadeira"
    NAO_POSSUI = "nao_possui"


class FonteAgua(str, Enum):
    """Fontes de água disponíveis"""
    POCO_ARTESIANO = "poco_artesiano"
    RIO = "rio"
    ACUDE = "acude"
    REPRESA = "represa"
    REDE_PUBLICA = "rede_publica"
    NAO_POSSUI = "nao_possui"


class InfraestruturaPropiedade(BaseModel):
    """
    INFRAESTRUTURA REAL DA PROPRIEDADE
    
    Usado para adaptar recomendações ao que o produtor POSSUI.
    Se não tem pivô, não vai receber alerta para ligar pivô.
    """
    
    propriedade_id: str
    produtor_nome: str
    
    # IRRIGAÇÃO
    possui_irrigacao: bool = Field(
        ...,
        description="Tem algum sistema de irrigação?"
    )
    sistemas_irrigacao: List[TipoIrrigacao] = Field(
        default_factory=list,
        description="Quais sistemas de irrigação possui"
    )
    area_irrigada_ha: Optional[float] = Field(
        None,
        description="Quantos hectares podem ser irrigados"
    )
    fonte_agua: Optional[FonteAgua] = Field(
        None,
        description="De onde vem a água"
    )
    capacidade_agua_m3_dia: Optional[float] = Field(
        None,
        description="Quantos m³/dia consegue irrigar"
    )
    
    # APLICAÇÃO DE INSUMOS
    equipamentos_aplicacao: List[TipoAplicacao] = Field(
        default_factory=list,
        description="Equipamentos para aplicar adubo, calcário, defensivos"
    )
    possui_hangar_aeronave: bool = False
    possui_maquinario_proprio: bool = Field(
        ...,
        description="Tem trator, implementos próprios ou depende de terceiros?"
    )
    
    # ARMAZENAMENTO
    possui_armazem: bool = False
    capacidade_armazem_ton: Optional[float] = None
    possui_silo: bool = False
    
    # ENERGIA
    possui_energia_eletrica: bool = True
    possui_geradores: bool = False
    
    # OBSERVAÇÕES
    limitacoes: Optional[List[str]] = Field(
        default_factory=list,
        description="Ex: 'Água só disponível das 6h às 18h', 'Trator quebrado', 'Sem calcário disponível'"
    )
    
    # TERCEIROS
    depende_terceiros_para: Optional[List[str]] = Field(
        default_factory=list,
        description="Ex: ['irrigação', 'pulverização', 'distribuição calcário']"
    )
    custo_medio_terceiros: Optional[dict] = Field(
        None,
        description="Custo por hectare para serviços terceirizados: {'irrigacao': 45.0, 'pulverizacao': 35.0}"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "propriedade_id": "prop_001",
                "produtor_nome": "João Silva",
                
                # Produtor SEM irrigação
                "possui_irrigacao": False,
                "sistemas_irrigacao": ["nao_possui"],
                "area_irrigada_ha": None,
                "fonte_agua": None,
                "capacidade_agua_m3_dia": None,
                
                # Aplicação manual/terceirizada
                "equipamentos_aplicacao": ["pulverizador_costal"],
                "possui_hangar_aeronave": False,
                "possui_maquinario_proprio": False,
                
                # Sem armazenamento
                "possui_armazem": False,
                "capacidade_armazem_ton": None,
                "possui_silo": False,
                
                # Energia disponível
                "possui_energia_eletrica": True,
                "possui_geradores": False,
                
                # Limitações
                "limitacoes": [
                    "Sem trator próprio",
                    "Depende de chuva para umidade"
                ],
                
                # Terceiros
                "depende_terceiros_para": ["pulverização", "distribuição de calcário"],
                "custo_medio_terceiros": {
                    "pulverizacao": 35.0,
                    "distribuicao_calcario": 50.0
                }
            }
        }


class RecomendacaoContextualizada(BaseModel):
    """
    Recomendação adaptada à infraestrutura do produtor
    """
    
    infraestrutura_disponivel: bool = Field(
        ...,
        description="Produtor TEM o necessário para executar?"
    )
    
    # SE TEM infraestrutura
    acao_direta: Optional[str] = Field(
        None,
        description="O que fazer se tiver o equipamento"
    )
    
    # SE NÃO TEM infraestrutura
    acao_alternativa: Optional[str] = Field(
        None,
        description="O que fazer se NÃO tiver o equipamento"
    )
    opcoes_terceirizacao: Optional[List[dict]] = Field(
        None,
        description="Empresas/serviços que podem ajudar"
    )
    custo_estimado_terceiro: Optional[float] = None
    
    # PREVENÇÃO para o futuro
    pode_prevenir_sem_equipamento: bool = Field(
        ...,
        description="Consegue prevenir mesmo sem o equipamento?"
    )
    acoes_preventivas: Optional[List[str]] = Field(
        None,
        description="O que fazer para evitar esse problema no futuro"
    )
    
    # ALERTA DE VIABILIDADE
    viavel_executar: bool = Field(
        ...,
        description="É viável executar mesmo sem o equipamento ideal?"
    )
    razao_inviabilidade: Optional[str] = Field(
        None,
        description="Por que não é viável (se não for)"
    )
    
    class Config:
        json_schema_extra = {
            "example_sem_irrigacao": {
                "infraestrutura_disponivel": False,
                "acao_direta": None,
                "acao_alternativa": "Aguardar previsão de chuva (próximas 48h) ou considerar irrigação manual em área crítica",
                "opcoes_terceirizacao": [
                    {
                        "servico": "Irrigação terceirizada",
                        "fornecedor": "AgroServiços Ltda",
                        "contato": "(11) 9999-9999",
                        "custo_ha": 45.0
                    }
                ],
                "custo_estimado_terceiro": 562.50,  # 12.5 ha * 45
                "pode_prevenir_sem_equipamento": True,
                "acoes_preventivas": [
                    "Plantar em época com maior probabilidade de chuva",
                    "Usar cobertura morta (palha) para reter umidade",
                    "Escolher cultivares mais tolerantes à seca",
                    "Avaliar investimento em sistema de irrigação simples"
                ],
                "viavel_executar": True,
                "razao_inviabilidade": None
            },
            "example_com_irrigacao": {
                "infraestrutura_disponivel": True,
                "acao_direta": "Ligar pivô central ou aplicar 30mm via aspersão no final da tarde",
                "acao_alternativa": None,
                "opcoes_terceirizacao": None,
                "custo_estimado_terceiro": None,
                "pode_prevenir_sem_equipamento": True,
                "acoes_preventivas": [
                    "Manter calendário de irrigação preventivo",
                    "Calibrar sensores regularmente"
                ],
                "viavel_executar": True,
                "razao_inviabilidade": None
            }
        }


def adaptar_recomendacao_irrigacao(
    infraestrutura: InfraestruturaPropiedade,
    area_ha: float,
    lamina_mm: float = 30
) -> RecomendacaoContextualizada:
    """
    Adapta recomendação de irrigação baseado na infraestrutura
    """
    
    if infraestrutura.possui_irrigacao:
        # TEM irrigação
        sistemas = ", ".join([s.value.replace("_", " ").title() for s in infraestrutura.sistemas_irrigacao if s != TipoIrrigacao.NAO_POSSUI])
        
        return RecomendacaoContextualizada(
            infraestrutura_disponivel=True,
            acao_direta=f"Irrigar {lamina_mm}mm usando {sistemas}. Irrigar no final da tarde (16-20h) para reduzir evaporação.",
            acao_alternativa=None,
            opcoes_terceirizacao=None,
            custo_estimado_terceiro=None,
            pode_prevenir_sem_equipamento=True,
            acoes_preventivas=[
                "Manter calendário de irrigação preventivo",
                "Monitorar previsão do tempo",
                "Calibrar sensores de umidade regularmente"
            ],
            viavel_executar=True,
            razao_inviabilidade=None
        )
    else:
        # NÃO TEM irrigação
        custo_terceiro = None
        if infraestrutura.custo_medio_terceiros and "irrigacao" in infraestrutura.custo_medio_terceiros:
            custo_terceiro = infraestrutura.custo_medio_terceiros["irrigacao"] * area_ha
        
        return RecomendacaoContextualizada(
            infraestrutura_disponivel=False,
            acao_direta=None,
            acao_alternativa="🌧️ Sem sistema de irrigação. Opções:\n1. Aguardar previsão de chuva (se > 70% nas próximas 48h)\n2. Aplicar cobertura morta (palha) para reter umidade\n3. Considerar irrigação terceirizada em área crítica\n4. Irrigação manual (só viável em área pequena < 1 ha)",
            opcoes_terceirizacao=[
                {
                    "servico": "Irrigação terceirizada (caminhão-pipa)",
                    "nota": "Procurar empresas locais de irrigação",
                    "custo_estimado_ha": infraestrutura.custo_medio_terceiros.get("irrigacao", 45.0) if infraestrutura.custo_medio_terceiros else 45.0
                }
            ],
            custo_estimado_terceiro=custo_terceiro,
            pode_prevenir_sem_equipamento=True,
            acoes_preventivas=[
                "🌱 Plantar em época com maior probabilidade de chuva",
                "🌾 Usar cobertura morta (palha, casca) para reter umidade do solo",
                "🔬 Escolher cultivares mais tolerantes à seca",
                "💧 Avaliar investimento em sistema básico de irrigação (gotejamento)",
                "📊 Acompanhar previsão do tempo antes do plantio"
            ],
            viavel_executar=True,
            razao_inviabilidade=None
        )


def adaptar_recomendacao_calcario(
    infraestrutura: InfraestruturaPropiedade,
    area_ha: float,
    quantidade_ton_ha: float = 2.0
) -> RecomendacaoContextualizada:
    """
    Adapta recomendação de aplicação de calcário
    """
    
    tem_equipamento = any(
        eq in infraestrutura.equipamentos_aplicacao 
        for eq in [TipoAplicacao.CALCAREADEIRA, TipoAplicacao.DISTRIBUIDOR_ADUBO]
    )
    
    if tem_equipamento:
        return RecomendacaoContextualizada(
            infraestrutura_disponivel=True,
            acao_direta=f"Aplicar {quantidade_ton_ha}t/ha de calcário usando calcareadeira ou distribuidor. Total: {quantidade_ton_ha * area_ha:.1f} toneladas.",
            acao_alternativa=None,
            opcoes_terceirizacao=None,
            custo_estimado_terceiro=None,
            pode_prevenir_sem_equipamento=False,
            acoes_preventivas=[
                "Fazer análise de solo anual",
                "Manter estoque de calcário"
            ],
            viavel_executar=True,
            razao_inviabilidade=None
        )
    else:
        custo_terceiro = None
        if infraestrutura.custo_medio_terceiros and "distribuicao_calcario" in infraestrutura.custo_medio_terceiros:
            custo_terceiro = infraestrutura.custo_medio_terceiros["distribuicao_calcario"] * area_ha
        
        return RecomendacaoContextualizada(
            infraestrutura_disponivel=False,
            acao_direta=None,
            acao_alternativa=f"⚠️ Sem equipamento para aplicar calcário.\n\nQuantidade necessária: {quantidade_ton_ha * area_ha:.1f} toneladas\n\nOpções:\n1. Contratar serviço terceirizado (mais comum)\n2. Alugar calcareadeira\n3. Aplicação manual (só viável em área muito pequena)",
            opcoes_terceirizacao=[
                {
                    "servico": "Aplicação de calcário terceirizada",
                    "nota": "Procurar empresas de serviços agrícolas ou cooperativa",
                    "custo_estimado_ha": infraestrutura.custo_medio_terceiros.get("distribuicao_calcario", 50.0) if infraestrutura.custo_medio_terceiros else 50.0
                }
            ],
            custo_estimado_terceiro=custo_terceiro,
            pode_prevenir_sem_equipamento=False,
            acoes_preventivas=[
                "Fazer análise de solo ANTES do plantio para planejar",
                "Negociar com cooperativa para serviço coletivo (reduz custo)",
                "Considerar investimento em distribuidor de adubo (serve para calcário)"
            ],
            viavel_executar=True,
            razao_inviabilidade=None
        )
