"""
Rotas de IA
POST /api/ia/chat - Chat com IA agrícola
GET /api/ia/historico/{cliente_id} - Histórico de conversas
"""

from fastapi import APIRouter, HTTPException, Header, Query, Depends
from typing import Optional, List
import logging
from datetime import datetime
import json

from app.models.contratos import RespostaIA, RecomendacaoIA, ContextoIA
from app.services.contexto_ia import servico_contexto_ia
from app.utils.datetime_utils import utc_iso

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ia", tags=["ia-agronomica"])

# Histórico em memória (TODO: Persistir em BD)
historico_conversas = {}


def validar_app_token(x_app_token: str = Header(...)) -> str:
    """Valida token da app mobile"""
    if not x_app_token.startswith("app_"):
        raise HTTPException(
            status_code=401,
            detail="Token inválido. Use header X-App-Token"
        )
    return x_app_token


@router.post(
    "/chat",
    response_model=RespostaIA,
    summary="Chat com IA Agrícola",
    description="Faz pergunta à IA com contexto agrícola completo"
)
async def chat_ia(
    cliente_id: str = Query(..., description="ID do cliente"),
    pergunta: str = Query(..., description="Pergunta do usuário"),
    sensor_id: Optional[str] = Query(None, description="(Opcional) ID do sensor específico"),
    x_app_token: str = Depends(validar_app_token)
):
    """
    Chat com IA Agrícola
    
    A IA recebe contexto completo (clima, alertas, histórico, plano agronômico)
    e responde de forma inteligente e contextualizada.
    
    Query Parameters:
    - cliente_id: ID do cliente (obrigatório)
    - pergunta: Pergunta do usuário (obrigatório)
    - sensor_id: ID do sensor para focar a resposta (opcional)
    
    Headers:
    - X-App-Token: Token de autenticação (obrigatório)
    
    Exemplo de pergunta:
    - "Devo irrigar agora?"
    - "Qual é o risco de geada essa semana?"
    - "Que adubo devo usar?"
    - "Como prevenir fungos com esse clima?"
    
    Exemplo de resposta:
    ```json
    {
      "pergunta_id": "conv_cliente_agritech_abc123",
      "resposta_texto": "Sim, recomendo irrigação imediata...",
      "recomendacao": {
        "acao": "Irrigar por 2-3 horas",
        "confianca": 0.92,
        "motivo": "Risco de seca 50%, solo seco, planta em fase crítica"
      },
      "atencoes": ["Chuva prevista amanhã", "Temperatura pode cair"],
      "proximos_passos": ["Ligar irrigação", "Monitorar próximas 3h"],
      "confianca_geral": 0.92
    }
    ```
    """
    try:
        from uuid import uuid4
        
        pergunta_id = f"conv_{cliente_id}_{uuid4().hex[:8]}"
        
        logger.info(
            f"IA Chat: cliente={cliente_id}, sensor={sensor_id}, "
            f"pergunta='{pergunta[:50]}...'"
        )
        
        # 1. Montar contexto
        logger.debug("Montando contexto IA...")
        contexto = await servico_contexto_ia.montar_contexto(
            cliente_id=cliente_id,
            pergunta=pergunta,
            sensor_id=sensor_id,
            usar_cache=True
        )
        
        logger.debug(f"Contexto montado: {contexto.tokens_estimado} tokens")
        
        # 2. Validar contexto
        if not contexto.sensores_relevantes:
            raise HTTPException(
                status_code=404,
                detail="Nenhum sensor encontrado para este cliente"
            )
        
        # 3. Chamar IA (por enquanto, resposta simulada)
        logger.debug("Enviando para IA...")
        resposta = await _chamar_ia(contexto, pergunta_id)
        
        # 4. Salvar no histórico
        if cliente_id not in historico_conversas:
            historico_conversas[cliente_id] = []
        
        historico_conversas[cliente_id].append({
            "pergunta_id": pergunta_id,
            "pergunta": pergunta,
            "resposta": resposta.dict(),
            "timestamp": utc_iso(datetime.utcnow())
        })
        
        logger.info(f"✓ IA respondeu: confiança {resposta.confianca_geral:.0%}")
        
        return resposta
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro no chat IA: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar pergunta: {str(e)}"
        )


@router.get(
    "/historico/{cliente_id}",
    response_model=dict,
    summary="Histórico de Conversas IA",
    description="Retorna histórico de conversas com IA dos últimos 30 dias"
)
async def historico_conversas_ia(
    cliente_id: str,
    limite: int = Query(20, ge=1, le=100, description="Número máximo de conversas"),
    x_app_token: str = Depends(validar_app_token)
):
    """
    Retorna histórico de conversas do cliente com IA
    
    Útil para:
    - Ver histórico de perguntas
    - Aprender padrões de uso
    - Verificar respostas anteriores
    
    Query Parameters:
    - limite: Número máximo de conversas (padrão: 20, máximo: 100)
    """
    try:
        if cliente_id not in historico_conversas:
            return {
                "cliente_id": cliente_id,
                "total": 0,
                "conversas": [],
                "mensagem": "Nenhuma conversa encontrada"
            }
        
        conversas = historico_conversas[cliente_id][-limite:]
        
        logger.info(f"Histórico IA retornado: {len(conversas)} conversas")
        
        return {
            "cliente_id": cliente_id,
            "total": len(historico_conversas[cliente_id]),
            "retornadas": len(conversas),
            "conversas": conversas
        }
        
    except Exception as e:
        logger.error(f"Erro ao buscar histórico IA: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao buscar histórico: {str(e)}"
        )


@router.delete(
    "/historico/{cliente_id}",
    summary="Limpar Histórico",
    description="Limpa histórico de conversas do cliente"
)
async def limpar_historico_ia(
    cliente_id: str,
    x_app_token: str = Depends(validar_app_token)
):
    """Limpa todo o histórico de conversas do cliente"""
    if cliente_id in historico_conversas:
        total = len(historico_conversas[cliente_id])
        del historico_conversas[cliente_id]
        logger.info(f"Histórico IA do cliente {cliente_id} foi limpo ({total} conversas)")
        return {
            "status": "sucesso",
            "mensagem": f"Histórico limpo ({total} conversas removidas)"
        }
    else:
        return {
            "status": "info",
            "mensagem": "Nenhum histórico para limpar"
        }


# ============================================================================
# Funções Auxiliares
# ============================================================================

async def _chamar_ia(contexto: ContextoIA, pergunta_id: str) -> RespostaIA:
    """
    Chama IA Izes (powered by OpenAI) com contexto agrícola
    
    Raises:
        HTTPException: Se Izes não estiver disponível
    """
    
    try:
        from app.services.openai_service import ServicoOpenAI
        
        servico = ServicoOpenAI()
        resposta = await servico.analisar_contexto(contexto, pergunta_id)
        
        if resposta:
            logger.info(f"Resposta Izes para {pergunta_id}")
            return resposta
        else:
            logger.error(f"Izes indisponível para {pergunta_id}")
            raise HTTPException(
                status_code=503,
                detail="Sistema Izes desconectado. Izes IA não respondeu. Tente novamente em alguns minutos."
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao chamar Izes: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Sistema Izes desconectado. Erro: {str(e)[:100]}"
        )


# Fim das funções auxiliares
