"""
Rotas para gerenciamento de alertas
"""
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.security import verify_token
from app.models.alerta import (
    AlertaResponse, AlertaUpdate, ResumoAlertas, 
    SeveridadeAlerta, StatusAlerta, TipoAlerta
)
from app.models.database import AlertaDB, UsuarioDB
from app.services.alerta_service import (
    buscar_alertas_ativos,
    atualizar_status_alerta,
    obter_resumo_alertas
)
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/alertas", tags=["Alertas"])


@router.get("/resumo", response_model=ResumoAlertas)
def get_resumo_alertas(
    cliente: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """
    Retorna resumo de alertas para o dashboard
    - Total de alertas ativos
    - Por severidade (críticos, altos, médios, baixos)
    - Não reconhecidos
    - Últimas 24 horas
    - Por tipo de parâmetro
    - Top 10 alertas recentes
    
    FUNCIONA SEM DB: Retorna resumo vazio se banco não estiver disponível
    """
    try:
        resumo = obter_resumo_alertas(db, cliente)
        return resumo
    except Exception as e:
        logger.error(f"Erro ao obter resumo de alertas: {e}", exc_info=True)
        # Retornar resumo vazio ao invés de erro
        return ResumoAlertas(
            total_ativos=0,
            criticos=0,
            altos=0,
            medios=0,
            baixos=0,
            nao_reconhecidos=0,
            ultimas_24h=0,
            por_tipo={},
            alertas_recentes=[]
        )


@router.get("/", response_model=List[AlertaResponse])
def listar_alertas(
    cliente: str = Depends(verify_token),
    db: Session = Depends(get_db),
    status_filter: Optional[StatusAlerta] = Query(StatusAlerta.ATIVO, description="Filtrar por status"),
    severidade: Optional[SeveridadeAlerta] = Query(None, description="Severidade mínima"),
    tipo: Optional[TipoAlerta] = Query(None, description="Tipo de alerta"),
    limit: int = Query(50, ge=1, le=200, description="Limite de resultados")
):
    """
    Lista alertas com filtros opcionais
    - Status: ativo, reconhecido, resolvido, ignorado
    - Severidade mínima: critico, alto, medio, baixo
    - Tipo: ph, umidade, temperatura, npk, sistema
    
    FUNCIONA SEM DB: Retorna lista vazia se banco não estiver disponível
    """
    try:
        # Buscar apenas ativos
        if status_filter == StatusAlerta.ATIVO:
            alertas = buscar_alertas_ativos(
                db=db,
                cliente_id=cliente,
                severidade_minima=severidade,
                tipo=tipo,
                limit=limit
            )
        else:
            # Sem DB, retorna vazio
            if not db:
                return []
            
            # Buscar outros status
            query = db.query(AlertaDB).filter(
                AlertaDB.cliente_id == cliente,
                AlertaDB.status == status_filter
            )
            
            if tipo:
                query = query.filter(AlertaDB.tipo == tipo)
            
            if severidade:
                query = query.filter(AlertaDB.severidade == severidade)
            
            alertas = query.order_by(AlertaDB.criado_em.desc()).limit(limit).all()
        
        return [AlertaResponse.model_validate(a) for a in alertas]
        
    except Exception as e:
        logger.error(f"Erro ao listar alertas: {e}", exc_info=True)
        # Retornar lista vazia ao invés de erro
        return []


@router.get("/{alerta_id}", response_model=AlertaResponse)
def get_alerta(
    alerta_id: int,
    cliente: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Busca detalhes de um alerta específico"""
    alerta = db.query(AlertaDB).filter(
        AlertaDB.id == alerta_id,
        AlertaDB.cliente_id == cliente
    ).first()
    
    if not alerta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alerta não encontrado"
        )
    
    return AlertaResponse.model_validate(alerta)


@router.patch("/{alerta_id}", response_model=AlertaResponse)
def atualizar_alerta(
    alerta_id: int,
    update: AlertaUpdate,
    cliente: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """
    Atualiza status de um alerta
    - Reconhecer alerta (usuário visualizou)
    - Marcar como resolvido (problema corrigido)
    - Ignorar alerta (não é relevante)
    """
    try:
        alerta = atualizar_status_alerta(db, alerta_id, cliente, update)
        
        if not alerta:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alerta não encontrado"
            )
        
        return AlertaResponse.model_validate(alerta)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar alerta: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar alerta: {str(e)}"
        )


@router.post("/reconhecer-todos")
def reconhecer_todos_alertas(
    cliente: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Marca todos os alertas ativos como reconhecidos"""
    try:
        alertas = db.query(AlertaDB).filter(
            AlertaDB.cliente_id == cliente,
            AlertaDB.status == StatusAlerta.ATIVO,
            AlertaDB.reconhecido_em.is_(None)
        ).all()
        
        count = 0
        for alerta in alertas:
            alerta.status = StatusAlerta.RECONHECIDO
            alerta.reconhecido_em = db.query(AlertaDB).filter(
                AlertaDB.id == alerta.id
            ).first().criado_em
            count += 1
        
        db.commit()
        
        return {
            "sucesso": True,
            "alertas_reconhecidos": count
        }
        
    except Exception as e:
        logger.error(f"Erro ao reconhecer alertas: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao reconhecer alertas: {str(e)}"
        )


@router.get("/preferencias/notificacoes")
def get_preferencias_notificacao(
    cliente: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Obtém preferências de notificação do usuário"""
    usuario = db.query(UsuarioDB).filter(
        UsuarioDB.cliente_id == cliente
    ).first()
    
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    return usuario.preferencias_notificacao or {
        "email_ativo": True,
        "email_severidade_minima": "alto",
        "alertas_ph": True,
        "alertas_umidade": True,
        "alertas_temperatura": True,
        "alertas_npk": True,
        "alertas_sistema": True,
        "agrupar_alertas": True,
        "intervalo_minimo_minutos": 60
    }


@router.put("/preferencias/notificacoes")
def atualizar_preferencias_notificacao(
    preferencias: dict,
    cliente: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """
    Atualiza preferências de notificação do usuário
    
    Campos disponíveis:
    - email_ativo: bool - Ativar/desativar notificações por e-mail
    - email_severidade_minima: str - Severidade mínima (critico, alto, medio, baixo)
    - alertas_ph: bool - Receber alertas de pH
    - alertas_umidade: bool - Receber alertas de umidade
    - alertas_temperatura: bool - Receber alertas de temperatura
    - alertas_npk: bool - Receber alertas de NPK
    - alertas_sistema: bool - Receber alertas do sistema
    - agrupar_alertas: bool - Agrupar alertas em um único e-mail
    - intervalo_minimo_minutos: int - Intervalo mínimo entre notificações
    """
    try:
        usuario = db.query(UsuarioDB).filter(
            UsuarioDB.cliente_id == cliente
        ).first()
        
        if not usuario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado"
            )
        
        # Atualizar preferências
        usuario.preferencias_notificacao = preferencias
        db.commit()
        
        logger.info(f"Preferências de notificação atualizadas para usuário {usuario.email}")
        
        return {
            "sucesso": True,
            "preferencias": preferencias
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar preferências: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar preferências: {str(e)}"
        )


@router.post("/testar-notificacao")
def testar_notificacao_email(
    cliente: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """
    Envia um e-mail de teste para verificar configuração
    """
    try:
        # Buscar alerta mais recente do cliente
        alerta = db.query(AlertaDB).filter(
            AlertaDB.cliente_id == cliente
        ).order_by(AlertaDB.criado_em.desc()).first()
        
        if not alerta:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nenhum alerta encontrado para enviar teste"
            )
        
        # Tentar enviar
        sucesso = notification_service.enviar_alerta_email(db, alerta)
        
        if sucesso:
            return {
                "sucesso": True,
                "mensagem": "E-mail de teste enviado com sucesso"
            }
        else:
            return {
                "sucesso": False,
                "mensagem": "Falha ao enviar e-mail. Verifique as configurações SMTP."
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao enviar e-mail de teste: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao enviar e-mail de teste: {str(e)}"
        )
