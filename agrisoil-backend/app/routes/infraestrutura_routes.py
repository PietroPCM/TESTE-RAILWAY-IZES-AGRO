"""
ROTAS DE INFRAESTRUTURA DE PROPRIEDADES
Gerenciar equipamentos e recursos disponíveis para contextualizar alertas
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import logging

from app.db import get_db
from app.security import obter_usuario_atual
from app.models.infraestrutura import (
    InfraestruturaPropiedade,
    TipoIrrigacao,
    TipoAplicacao,
    FonteAgua,
    RecomendacaoContextualizada,
    adaptar_recomendacao_irrigacao,
    adaptar_recomendacao_calcario
)

router = APIRouter(prefix="/api/infraestrutura", tags=["Infraestrutura de Propriedades"])
logger = logging.getLogger(__name__)


# ============================================================================
# CADASTRAR/ATUALIZAR INFRAESTRUTURA
# ============================================================================

@router.post("/propriedade", response_model=dict)
async def cadastrar_infraestrutura(
    infraestrutura: InfraestruturaPropiedade,
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Cadastrar ou atualizar infraestrutura da propriedade
    
    Usado para contextualizar alertas:
    - Se não tem irrigação, não recebe alerta de "ligar pivô"
    - Se não tem calcareadeira, recomenda terceirização
    - Se depende de terceiros, calcula custos
    """
    try:
        # TODO: Salvar no banco
        # infra_db = InfraestruturaDB(**infraestrutura.dict())
        # db.add(infra_db)
        # db.commit()
        
        # Validações inteligentes
        avisos = []
        
        if not infraestrutura.possui_irrigacao:
            avisos.append("⚠️ Sem sistema de irrigação: Alertas serão adaptados para recomendar alternativas")
        
        if not infraestrutura.possui_maquinario_proprio:
            avisos.append("💰 Sem maquinário próprio: Custos de terceirização serão incluídos nas recomendações")
        
        if infraestrutura.limitacoes:
            avisos.append(f"📋 {len(infraestrutura.limitacoes)} limitações cadastradas: Sistema considerará nas recomendações")
        
        logger.info(f"Infraestrutura cadastrada para {infraestrutura.propriedade_id}")
        
        return {
            "sucesso": True,
            "propriedade_id": infraestrutura.propriedade_id,
            "mensagem": "Infraestrutura cadastrada com sucesso",
            "avisos": avisos,
            "proximos_passos": [
                "Alertas agora serão contextualizados para sua realidade",
                "Recomendações vão considerar equipamentos disponíveis",
                "Custos de terceirização incluídos quando necessário"
            ]
        }
        
    except Exception as e:
        logger.error(f"Erro ao cadastrar infraestrutura: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao cadastrar infraestrutura"
        )


# ============================================================================
# CONSULTAR INFRAESTRUTURA
# ============================================================================

@router.get("/propriedade/{propriedade_id}", response_model=InfraestruturaPropiedade)
async def obter_infraestrutura(
    propriedade_id: str,
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Obter infraestrutura cadastrada de uma propriedade
    """
    try:
        # TODO: Buscar no banco
        
        # Mock para exemplo
        return InfraestruturaPropiedade(
            propriedade_id=propriedade_id,
            produtor_nome="João Silva",
            possui_irrigacao=False,
            sistemas_irrigacao=[TipoIrrigacao.NAO_POSSUI],
            area_irrigada_ha=None,
            fonte_agua=None,
            capacidade_agua_m3_dia=None,
            equipamentos_aplicacao=[TipoAplicacao.PULVERIZADOR_COSTAL],
            possui_hangar_aeronave=False,
            possui_maquinario_proprio=False,
            possui_armazem=False,
            possui_energia_eletrica=True,
            limitacoes=[
                "Sem trator próprio",
                "Depende de chuva para umidade"
            ],
            depende_terceiros_para=["pulverização", "distribuição de calcário"],
            custo_medio_terceiros={
                "irrigacao": 45.0,
                "pulverizacao": 35.0,
                "distribuicao_calcario": 50.0
            }
        )
        
    except Exception as e:
        logger.error(f"Erro ao obter infraestrutura: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Infraestrutura não encontrada"
        )


# ============================================================================
# SIMULAR RECOMENDAÇÃO CONTEXTUALIZADA
# ============================================================================

@router.post("/simular-recomendacao", response_model=RecomendacaoContextualizada)
async def simular_recomendacao(
    propriedade_id: str,
    tipo_acao: str,  # "irrigar" ou "aplicar_calcario"
    area_ha: float,
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Simular como seria a recomendação baseada na infraestrutura
    
    Exemplo: "Como seria a recomendação de irrigação para minha propriedade?"
    """
    try:
        # TODO: Buscar infraestrutura do banco
        # Mock
        infraestrutura = InfraestruturaPropiedade(
            propriedade_id=propriedade_id,
            produtor_nome="João Silva",
            possui_irrigacao=False,
            sistemas_irrigacao=[TipoIrrigacao.NAO_POSSUI],
            area_irrigada_ha=None,
            fonte_agua=None,
            capacidade_agua_m3_dia=None,
            equipamentos_aplicacao=[TipoAplicacao.PULVERIZADOR_COSTAL],
            possui_maquinario_proprio=False,
            possui_armazem=False,
            possui_energia_eletrica=True,
            depende_terceiros_para=["irrigação", "distribuição de calcário"],
            custo_medio_terceiros={
                "irrigacao": 45.0,
                "distribuicao_calcario": 50.0
            }
        )
        
        if tipo_acao == "irrigar":
            return adaptar_recomendacao_irrigacao(infraestrutura, area_ha)
        elif tipo_acao == "aplicar_calcario":
            return adaptar_recomendacao_calcario(infraestrutura, area_ha)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de ação '{tipo_acao}' não suportado"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao simular recomendação: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao simular recomendação"
        )


# ============================================================================
# CHECKLIST DE INFRAESTRUTURA
# ============================================================================

@router.get("/checklist", response_model=dict)
async def checklist_infraestrutura(
    usuario = Depends(obter_usuario_atual)
):
    """
    Checklist para ajudar produtor a cadastrar infraestrutura
    """
    return {
        "titulo": "O que você possui na sua propriedade?",
        "categorias": [
            {
                "categoria": "💧 Irrigação",
                "perguntas": [
                    "Você possui algum sistema de irrigação?",
                    "Qual tipo? (Pivô central, aspersão, gotejamento, etc)",
                    "Quantos hectares consegue irrigar?",
                    "De onde vem a água? (Poço, rio, represa, etc)",
                    "Quantos m³ de água consegue usar por dia?"
                ]
            },
            {
                "categoria": "🚜 Equipamentos",
                "perguntas": [
                    "Possui trator próprio?",
                    "Possui pulverizador? Qual tipo?",
                    "Possui distribuidor de adubo/calcário?",
                    "Possui plantadeira/semeadora?",
                    "Possui colheitadeira?"
                ]
            },
            {
                "categoria": "🏗️ Infraestrutura",
                "perguntas": [
                    "Possui armazém? Qual capacidade?",
                    "Possui silo?",
                    "Possui energia elétrica?",
                    "Possui geradores?"
                ]
            },
            {
                "categoria": "💰 Terceirização",
                "perguntas": [
                    "Quais serviços você contrata de terceiros?",
                    "Quanto custa em média (por hectare)?",
                    "Há limitações (ex: só disponível em certas épocas)?"
                ]
            }
        ],
        "dica": "Quanto mais completo o cadastro, mais precisas serão as recomendações do sistema!"
    }


# ============================================================================
# ESTATÍSTICAS DE INFRAESTRUTURA
# ============================================================================

@router.get("/estatisticas", response_model=dict)
async def estatisticas_infraestrutura(
    usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Estatísticas de infraestrutura da região
    
    Ajuda produtor a entender:
    - Quantos % dos produtores têm irrigação
    - Custos médios de terceirização na região
    - Equipamentos mais comuns
    """
    try:
        # TODO: Query agregada no banco
        
        return {
            "regiao": "Região Sul - PR",
            "total_propriedades": 150,
            
            "irrigacao": {
                "possui_algum_sistema": "35%",
                "tipos_mais_comuns": [
                    "Pivô central (18%)",
                    "Aspersão (12%)",
                    "Gotejamento (5%)"
                ],
                "investimento_medio": "R$ 120.000 (pivô para 50ha)"
            },
            
            "terceirizacao": {
                "servicos_mais_terceirizados": [
                    "Pulverização (78%)",
                    "Distribuição de calcário (65%)",
                    "Colheita (45%)",
                    "Irrigação (12%)"
                ],
                "custos_medios_regiao": {
                    "irrigacao_ha": 45.0,
                    "pulverizacao_ha": 35.0,
                    "distribuicao_calcario_ha": 50.0,
                    "colheita_ha": 180.0
                }
            },
            
            "equipamentos": {
                "trator_proprio": "42%",
                "pulverizador_proprio": "38%",
                "distribuidor_proprio": "25%"
            },
            
            "dica": "Você pode comparar sua infraestrutura com a média regional para identificar oportunidades de investimento ou parceria."
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter estatísticas"
        )
