"""
Rotas de Biblioteca (Master Data)
Culturas, Fases, Parâmetros ideais, Regras
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.db import get_db
from app.models.contexto_fixo import (
    NomeCultura, FaseFenologica, ParametroIdeal, BibliotecaCultura
)
from app.models.regra_alerta import RegradeAlerta
from app.security import obter_usuario_atual

router = APIRouter(prefix="/api/biblioteca", tags=["Biblioteca"])
logger = logging.getLogger(__name__)


# ============================================================================
# BIBLIOTECA DE CULTURAS
# ============================================================================

@router.get("/culturas", response_model=dict)
async def listar_culturas(db: Session = Depends(get_db)):
    """
    Listar todas as culturas disponíveis no sistema
    
    Retorna: Lista de culturas com informações básicas
    """
    try:
        culturas = [
            {
                "id": c.value,
                "nome": c.value.replace("_", " ").title(),
                "descricao": f"Cultura de {c.value}"
            }
            for c in NomeCultura
        ]
        
        return {
            "total": len(culturas),
            "culturas": culturas
        }
        
    except Exception as e:
        logger.error(f"Erro ao listar culturas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao listar culturas"
        )


@router.get("/culturas/{cultura}", response_model=dict)
async def obter_cultura_detalhes(
    cultura: str,
    db: Session = Depends(get_db)
):
    """
    Obter detalhes de uma cultura específica
    
    Retorna: 
    - Informações básicas
    - Fases fenológicas
    - Parâmetros ideais por fase
    - Regras de alerta
    
    Exemplo: /api/biblioteca/culturas/soja
    """
    try:
        # Validar cultura
        try:
            cultura_enum = NomeCultura(cultura.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cultura '{cultura}' não encontrada"
            )
        
        # TODO: Buscar no banco
        # biblioteca = db.query(BibliotecaCultura)\
        #     .filter(BibliotecaCultura.nome == cultura_enum)\
        #     .first()
        
        # if not biblioteca:
        #     raise HTTPException(
        #         status_code=status.HTTP_404_NOT_FOUND,
        #         detail=f"Dados da cultura '{cultura}' não disponíveis"
        #     )
        
        # Resposta mock por enquanto
        return {
            "id": cultura_enum.value,
            "nome": cultura_enum.value.title(),
            "ciclo_dias": 130,
            "fases": [
                {
                    "fase": "emergencia",
                    "dia_inicio": 1,
                    "dia_fim": 15,
                    "descricao": "Emergência das plântulas"
                },
                {
                    "fase": "vegetativo",
                    "dia_inicio": 16,
                    "dia_fim": 45,
                    "descricao": "Desenvolvimento vegetativo"
                },
                {
                    "fase": "florescimento",
                    "dia_inicio": 46,
                    "dia_fim": 65,
                    "descricao": "Florescimento"
                },
                {
                    "fase": "enchimento_graos",
                    "dia_inicio": 66,
                    "dia_fim": 100,
                    "descricao": "Enchimento de grãos"
                }
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter cultura: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter detalhes da cultura"
        )


# ============================================================================
# PARÂMETROS IDEAIS
# ============================================================================

@router.get("/parametros-ideais/{cultura}/{fase}", response_model=dict)
async def obter_parametros_ideais(
    cultura: str,
    fase: str,
    db: Session = Depends(get_db)
):
    """
    Obter parâmetros ideais para uma cultura em uma fase específica
    
    Inclui:
    - Umidade (min/max ideal, alerta, crítico)
    - pH
    - Temperatura
    - NPK
    
    Exemplo: /api/biblioteca/parametros-ideais/soja/emergencia
    """
    try:
        # Validar
        try:
            cultura_enum = NomeCultura(cultura.lower())
            fase_enum = FaseFenologica(fase.lower())
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cultura ou fase inválida"
            )
        
        # TODO: Query no banco
        # parametros = db.query(ParametroIdeal)\
        #     .filter(ParametroIdeal.cultura == cultura_enum)\
        #     .filter(ParametroIdeal.fase == fase_enum)\
        #     .all()
        
        # Mock response
        parametros = [
            {
                "parametro": "umidade",
                "unidade": "%",
                "minimo_ideal": 25,
                "maximo_ideal": 35,
                "minimo_alerta": 22,
                "maximo_alerta": 40,
                "minimo_critico": 20,
                "maximo_critico": 45,
                "impacto_desvio": "Umidade baixa prejudica emergência"
            },
            {
                "parametro": "ph",
                "unidade": "pH",
                "minimo_ideal": 6.0,
                "maximo_ideal": 7.5,
                "minimo_alerta": 5.5,
                "maximo_alerta": 8.0,
                "minimo_critico": 4.5,
                "maximo_critico": 8.5,
                "impacto_desvio": "pH fora do ideal compromete absorção de nutrientes"
            },
            {
                "parametro": "temperatura",
                "unidade": "°C",
                "minimo_ideal": 20,
                "maximo_ideal": 30,
                "minimo_alerta": 18,
                "maximo_alerta": 32,
                "minimo_critico": 15,
                "maximo_critico": 35,
                "impacto_desvio": "Temperatura baixa atrasa germinação"
            }
        ]
        
        return {
            "cultura": cultura,
            "fase": fase,
            "parametros": parametros
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter parâmetros: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter parâmetros ideais"
        )


# ============================================================================
# REGRAS DE ALERTA
# ============================================================================

@router.get("/regras/{cultura}", response_model=dict)
async def obter_regras_cultura(
    cultura: str,
    db: Session = Depends(get_db)
):
    """
    Obter todas as regras de alerta para uma cultura
    
    Retorna regras ativas contextualizadas por fase
    
    Exemplo: /api/biblioteca/regras/soja
    """
    try:
        # Validar
        try:
            cultura_enum = NomeCultura(cultura.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cultura '{cultura}' não encontrada"
            )
        
        # TODO: Query no banco
        # regras = db.query(RegradeAlerta)\
        #     .filter(RegradeAlerta.cultura == cultura_enum)\
        #     .filter(RegradeAlerta.ativo == True)\
        #     .all()
        
        # Mock response
        regras_por_fase = {
            "emergencia": [
                {
                    "id": "regra-soja-emergencia-umidade",
                    "parametro": "umidade",
                    "titulo": "Umidade baixa durante emergência",
                    "mensagem_produtor": "A zona está muito seca. Se não chover ou irrigar nas próximas 24h, a soja pode não germinar direito.",
                    "acao_recomendada": "irrigar",
                    "urgencia_acao": "24h"
                }
            ],
            "vegetativo": [
                {
                    "id": "regra-soja-vegetativo-nitrogenio",
                    "parametro": "nitrogenio",
                    "titulo": "Nitrogênio baixo",
                    "mensagem_produtor": "Falta nitrogênio para o desenvolvimento das plantas.",
                    "acao_recomendada": "adubar_npk",
                    "urgencia_acao": "48h"
                }
            ]
        }
        
        return {
            "cultura": cultura,
            "total_regras": 8,
            "regras_por_fase": regras_por_fase
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter regras: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter regras de alerta"
        )


# ============================================================================
# FASES FENOLÓGICAS
# ============================================================================

@router.get("/fases", response_model=dict)
async def listar_fases():
    """
    Listar todas as fases fenológicas disponíveis
    """
    return {
        "fases": [f.value for f in FaseFenologica],
        "total": len(list(FaseFenologica))
    }
