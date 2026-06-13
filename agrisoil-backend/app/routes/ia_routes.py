"""
Rotas de IA
POST /api/ia/chat - Chat com IA agrícola
GET /api/ia/historico/{cliente_id} - Histórico de conversas
"""

from fastapi import APIRouter, HTTPException, Query, Depends, File, UploadFile
from sqlalchemy.orm import Session
from typing import Optional, List
import logging
from datetime import datetime
import json

from app.models.contratos import RespostaIA, RecomendacaoIA, ContextoIA, RespostaAnaliseImagemIA
from app.db import get_db
from app.security import verificar_app_internal_token
from app.services.contexto_ia import (
    ClienteIANaoEncontrado,
    SensorIANaoEncontrado,
    servico_contexto_ia,
)
from app.services.openai_service import (
    MODO_AGRO_COM_DADOS,
    MODO_AGRO_GERAL,
    MODO_ESCLARECIMENTO,
    MODO_FORA_ESCOPO,
    OpenAIImageAnalysisError,
    ServicoOpenAI,
    classificar_escopo_pergunta,
)
from app.utils.datetime_utils import utc_iso

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ia", tags=["ia-agronomica"])

# Histórico em memória (TODO: Persistir em BD)
historico_conversas = {}


@router.post(
    "/analisar-imagem",
    response_model=RespostaAnaliseImagemIA,
    summary="Analisar imagem com IA",
    description="Recebe uma imagem do app, envia para a OpenAI com visão e retorna uma descrição textual objetiva."
)
async def analisar_imagem_ia(
    imagem: UploadFile = File(..., description="Arquivo de imagem enviado pelo app"),
    x_app_token: str = Depends(verificar_app_internal_token),
):
    if not imagem.content_type or not imagem.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="O arquivo enviado deve ser uma imagem válida.")

    try:
        conteudo = await imagem.read()
        if not conteudo:
            raise HTTPException(status_code=400, detail="A imagem enviada está vazia.")

        resposta = await ServicoOpenAI().analisar_imagem(
            image_bytes=conteudo,
            mime_type=imagem.content_type,
        )
        return RespostaAnaliseImagemIA(resposta=resposta)
    except HTTPException:
        raise
    except OpenAIImageAnalysisError as exc:
        detalhe = str(exc)
        status_code = 503 if "OPENAI_API_KEY" in detalhe else 502
        raise HTTPException(status_code=status_code, detail=detalhe) from exc
    except Exception as exc:
        logger.error("Erro ao analisar imagem na rota IA: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao processar a imagem enviada."
        ) from exc
    finally:
        await imagem.close()


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
    x_app_token: str = Depends(verificar_app_internal_token),
    db: Session = Depends(get_db)
):
    """
    Chat com IA Agrícola
    
    A IA recebe somente contexto agrícola real disponível no banco e responde
    de forma curta, segura e contextualizada.
    
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
      "pergunta_id": "conv_cliente_abc123",
      "resposta_texto": "Situação:\nHá leitura real do sensor.\n\nRisco:\nUmidade baixa exige atenção.\n\nO que fazer agora:\n1. Conferir dashboard.\n2. Coletar nova leitura.\n3. Validar em campo.\n\nAtenção:\nNão aplique dose exata sem análise de solo ou agrônomo.",
      "recomendacao": {
        "acao": "Conferir leitura e validar em campo.",
        "confianca": 0.80,
        "motivo": "Resposta baseada no contexto real disponível."
      },
      "atencoes": ["Não substitui laudo agronômico."],
      "proximos_passos": ["Conferir dashboard", "Coletar nova leitura"],
      "confianca_geral": 0.80
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
        
        # 1. Interpretar a intenção usando também cliente_id e sensor_id.
        #    Perguntas curtas/informais/contextuais não caem mais em fora_escopo
        #    quando há contexto adequado.
        modo_pergunta = classificar_escopo_pergunta(pergunta, cliente_id, sensor_id)
        logger.info(f"IA Chat: intenção classificada como '{modo_pergunta}'")

        # 2. Modos que não dependem dos dados reais do cliente.
        if modo_pergunta in (MODO_FORA_ESCOPO, MODO_ESCLARECIMENTO, MODO_AGRO_GERAL):
            contexto = ContextoIA(
                cliente_id=cliente_id,
                sensor_id=None,
                usuario_pergunta=pergunta,
            )
            return await ServicoOpenAI().analisar_contexto(
                contexto, pergunta_id, modo=modo_pergunta
            )

        # 3. Modo agro_com_dados: montar contexto com dados reais do cliente.
        logger.debug("Montando contexto IA com dados reais...")
        try:
            contexto = await servico_contexto_ia.montar_contexto(
                cliente_id=cliente_id,
                pergunta=pergunta,
                sensor_id=sensor_id,
                usar_cache=True,
                db=db,
                exigir_cliente=True,
            )
        except (ClienteIANaoEncontrado, SensorIANaoEncontrado):
            raise
        except Exception as e:
            # Falha do banco/contexto não deve derrubar o endpoint.
            logger.error(f"Erro ao montar contexto IA; retornando erro controlado: {e}", exc_info=True)
            raise HTTPException(
                status_code=503,
                detail="Não foi possível consultar os dados do cliente agora. Tente novamente em instantes.",
            )

        logger.debug(f"Contexto montado: {contexto.tokens_estimado} tokens")

        # 4. Chamar IA com o modo já decidido.
        logger.debug("Enviando para IA...")
        resposta = await _chamar_ia(contexto, pergunta_id, modo=modo_pergunta)
        
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
        
    except ClienteIANaoEncontrado:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    except SensorIANaoEncontrado:
        raise HTTPException(status_code=404, detail="Sensor não encontrado.")
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
    x_app_token: str = Depends(verificar_app_internal_token)
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
    x_app_token: str = Depends(verificar_app_internal_token)
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

async def _chamar_ia(contexto: ContextoIA, pergunta_id: str, modo: Optional[str] = None) -> RespostaIA:
    """
    Chama IA Izes (powered by OpenAI) com contexto agrícola

    Raises:
        HTTPException: Se Izes não estiver disponível
    """

    try:
        from app.services.openai_service import ServicoOpenAI

        servico = ServicoOpenAI()
        resposta = await servico.analisar_contexto(contexto, pergunta_id, modo=modo)
        
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
