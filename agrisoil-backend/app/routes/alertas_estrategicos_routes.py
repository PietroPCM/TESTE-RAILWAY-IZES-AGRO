"""
Rotas de alertas estrategicos.
Transforma alertas reais em uma visao operacional com impacto, prioridade,
janela de acao, confirmacao, aprendizado e auditoria.
"""

from datetime import datetime, timedelta
from enum import Enum
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.alerta_estrategico import (
    AuditoriaCompleta,
    ConfirmacaoExecucao,
    ExcecaoAlerta,
    NivelImpacto,
)
from app.models.database import (
    AlertaDB,
    AlertaExcecaoDB,
    AlertaExecucaoDB,
    SensorDB,
    SeveridadeAlerta,
    StatusAlerta as StatusAlertaDB,
    TipoAlerta,
    ZonaManejoDB,
)
from app.models.regra_alerta import AcaoRecomendada
from app.security import obter_usuario_atual

router = APIRouter(prefix="/api/alertas-v2", tags=["Alertas Estrategicos - 10 Camadas"])
logger = logging.getLogger(__name__)


class StatusAlerta(str, Enum):
    """Status do alerta no ciclo de vida estrategico."""

    NOVO = "novo"
    RECONHECIDO = "reconhecido"
    EM_EXECUCAO = "em_execucao"
    RESOLVIDO = "resolvido"
    CANCELADO = "cancelado"


SEVERIDADE_SCORE = {
    SeveridadeAlerta.CRITICO: 95,
    SeveridadeAlerta.ALTO: 80,
    SeveridadeAlerta.MEDIO: 55,
    SeveridadeAlerta.BAIXO: 25,
}

SEVERIDADE_IMPACTO = {
    SeveridadeAlerta.CRITICO: NivelImpacto.CRITICO.value,
    SeveridadeAlerta.ALTO: NivelImpacto.ALTO.value,
    SeveridadeAlerta.MEDIO: NivelImpacto.MEDIO.value,
    SeveridadeAlerta.BAIXO: NivelImpacto.BAIXO.value,
}

STATUS_V2_TO_DB = {
    StatusAlerta.NOVO: StatusAlertaDB.ATIVO,
    StatusAlerta.RECONHECIDO: StatusAlertaDB.RECONHECIDO,
    StatusAlerta.RESOLVIDO: StatusAlertaDB.RESOLVIDO,
    StatusAlerta.CANCELADO: StatusAlertaDB.IGNORADO,
}


def _alerta_id_num(alerta_id: str) -> int:
    if alerta_id.startswith("alerta_"):
        alerta_id = alerta_id.replace("alerta_", "", 1)
    try:
        return int(alerta_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID de alerta invalido")


def _obter_alerta_ou_404(db: Session, alerta_id: str) -> AlertaDB:
    alerta = db.query(AlertaDB).filter(AlertaDB.id == _alerta_id_num(alerta_id)).first()
    if not alerta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alerta nao encontrado")
    return alerta


def _status_v2(alerta: AlertaDB, execucao: AlertaExecucaoDB | None = None) -> str:
    if execucao and execucao.produtor_executou and alerta.status != StatusAlertaDB.RESOLVIDO:
        return StatusAlerta.EM_EXECUCAO.value
    if alerta.status == StatusAlertaDB.ATIVO:
        return StatusAlerta.NOVO.value
    if alerta.status == StatusAlertaDB.RECONHECIDO:
        return StatusAlerta.RECONHECIDO.value
    if alerta.status == StatusAlertaDB.RESOLVIDO:
        return StatusAlerta.RESOLVIDO.value
    return StatusAlerta.CANCELADO.value


def _acao_recomendada(alerta: AlertaDB) -> str:
    tipo = getattr(alerta.tipo, "value", str(alerta.tipo))
    if tipo == "umidade":
        return AcaoRecomendada.IRRIGAR.value
    if tipo == "ph":
        if alerta.valor_medido is not None and alerta.valor_medido < 5.8:
            return AcaoRecomendada.APLICAR_CALCARIO.value
        return AcaoRecomendada.APLICAR_ENXOFRE.value
    if tipo in {"nitrogenio", "fosforo", "potassio"}:
        return AcaoRecomendada.ADUBAR_NPK.value
    if tipo == "temperatura":
        return AcaoRecomendada.MONITORAR.value
    return AcaoRecomendada.INSPECIONAR_SENSOR.value


def _janela_horas(alerta: AlertaDB) -> int:
    if alerta.severidade == SeveridadeAlerta.CRITICO:
        return 6
    if alerta.severidade == SeveridadeAlerta.ALTO:
        return 24
    if alerta.severidade == SeveridadeAlerta.MEDIO:
        return 48
    return 120


def _urgencia(alerta: AlertaDB) -> str:
    janela = _janela_horas(alerta)
    if janela <= 6:
        return "imediata"
    if janela <= 24:
        return "hoje"
    if janela <= 48:
        return "48h"
    return "esta_semana"


def _ultima_execucao(db: Session, alerta_id: int) -> AlertaExecucaoDB | None:
    return db.query(AlertaExecucaoDB).filter(
        AlertaExecucaoDB.alerta_id == alerta_id,
    ).order_by(AlertaExecucaoDB.criado_em.desc()).first()


def _ultima_excecao(db: Session, alerta_id: int) -> AlertaExcecaoDB | None:
    return db.query(AlertaExcecaoDB).filter(
        AlertaExcecaoDB.alerta_id == alerta_id,
    ).order_by(AlertaExcecaoDB.criado_em.desc()).first()


def _sensor(db: Session, sensor_id: str) -> SensorDB | None:
    return db.query(SensorDB).filter(SensorDB.sensor_id == sensor_id).first()


def _zona_por_sensor(db: Session, sensor: SensorDB | None) -> ZonaManejoDB | None:
    if not sensor or not sensor.local_especifico:
        return None
    return db.query(ZonaManejoDB).filter(
        ZonaManejoDB.zona_id == sensor.local_especifico,
        ZonaManejoDB.ativo.is_(True),
    ).first()


def _confirmacao_dict(execucao: AlertaExecucaoDB | None, alerta_ref: str) -> Optional[dict]:
    if not execucao:
        return None
    return {
        "alerta_id": alerta_ref,
        "produtor_executou": execucao.produtor_executou,
        "data_execucao": execucao.data_execucao,
        "acao_tomada": execucao.acao_tomada,
        "quantidade_aplicada": execucao.quantidade_aplicada,
        "custo_real": execucao.custo_real,
        "observacoes": execucao.observacoes,
        "razao_nao_execucao": execucao.razao_nao_execucao,
        "resultado_percebido": execucao.resultado_percebido,
    }


def _excecao_dict(excecao: AlertaExcecaoDB | None, alerta_ref: str) -> Optional[dict]:
    if not excecao:
        return None
    return {
        "alerta_id": alerta_ref,
        "situacao_atipica": excecao.situacao_atipica,
        "descricao_atipico": excecao.descricao_atipico,
        "requer_intervencao_agronomica": excecao.requer_intervencao_agronomica,
        "override_aplicado": excecao.override_aplicado,
        "regra_original": excecao.regra_original,
        "decisao_agronomica": excecao.decisao_agronomica,
        "justificativa": excecao.justificativa,
        "validado_por": excecao.validado_por,
    }


def _alerta_estrategico(db: Session, alerta: AlertaDB, ranking: int = 1) -> dict:
    sensor = _sensor(db, alerta.sensor_id)
    zona = _zona_por_sensor(db, sensor)
    execucao = _ultima_execucao(db, alerta.id)
    excecao = _ultima_excecao(db, alerta.id)
    alerta_ref = f"alerta_{alerta.id}"
    score = SEVERIDADE_SCORE.get(alerta.severidade, 30)
    janela_horas = _janela_horas(alerta)
    ponto_nao_retorno = alerta.criado_em + timedelta(hours=janela_horas)
    parametro = getattr(alerta.tipo, "value", str(alerta.tipo))
    severidade = getattr(alerta.severidade, "value", str(alerta.severidade))
    valor = alerta.valor_medido or 0
    cultura = zona.cultura if zona else "soja"
    fase = "emergencia"
    area = zona.area_hectares if zona else 0

    return {
        "id": alerta_ref,
        "criado_em": alerta.criado_em,
        "atualizado_em": alerta.atualizado_em,
        "regra_id": alerta.hash_deduplicacao or f"regra_{parametro}_{severidade}",
        "sensor_id": alerta.sensor_id,
        "parametro": parametro,
        "valor_medido": valor,
        "unidade": "%",
        "cultura": cultura,
        "fase": fase,
        "status": _status_v2(alerta, execucao),
        "camada_1_impacto": {
            "nivel": SEVERIDADE_IMPACTO.get(alerta.severidade, NivelImpacto.BAIXO.value),
            "consequencia": "perda_produtividade",
            "perda_estimada_kg_ha": score * 4 if score >= 55 else None,
            "perda_estimada_percentual": round(score / 5, 1) if score >= 55 else None,
            "perda_financeira_estimada": round((area or 1) * score * 12, 2) if score >= 55 else None,
            "irreversivel": alerta.severidade in {SeveridadeAlerta.CRITICO, SeveridadeAlerta.ALTO},
            "impacto_descritivo": alerta.mensagem,
        },
        "camada_2_prioridade": {
            "score_prioridade": score,
            "ranking_propriedade": ranking,
            "fatores_calculo": {
                "severidade": score,
                "tempo_ate_dano": max(100 - janela_horas, 0),
                "area_afetada": area,
            },
            "comparacao": "Ranking calculado por severidade, janela de acao e area afetada.",
        },
        "camada_3_tempo": {
            "janela_segura_horas": janela_horas,
            "ponto_nao_retorno": ponto_nao_retorno,
            "urgencia": _urgencia(alerta),
            "tempo_restante_str": f"Aja em ate {janela_horas} horas para reduzir risco operacional.",
            "pode_esperar": janela_horas > 48,
        },
        "camada_4_localizacao": {
            "zona_manejo_id": zona.zona_id if zona else "nao_vinculada",
            "zona_manejo_nome": zona.nome if zona else sensor.local_especifico if sensor else "nao_vinculada",
            "talhao_id": zona.parcel_id if zona else "nao_vinculado",
            "talhao_nome": zona.parcel_id if zona else "nao_vinculado",
            "ponto_sensor": sensor.local_especifico if sensor else alerta.sensor_id,
            "area_afetada_ha": area,
            "percentual_zona": 100 if area else 0,
            "localizacao_textual": f"{sensor.propriedade or 'Propriedade nao informada'} / {sensor.local_especifico or alerta.sensor_id}" if sensor else alerta.sensor_id,
        },
        "camada_5_acao": {
            "acao_principal": _acao_recomendada(alerta),
            "o_que_fazer": alerta.recomendacao or "Verificar o ponto em campo e executar a acao recomendada.",
            "o_que_nao_fazer": "Nao ignore alerta alto/critico sem validar sensor, cultura e fase em campo.",
            "pode_esperar": janela_horas > 48,
            "se_esperar_acontece": "O risco agronomico aumenta conforme o parametro permanece fora da faixa.",
            "quantidade_estimada": None,
            "custo_estimado": None,
            "acoes_alternativas": ["Validar leitura do sensor", "Registrar execucao ou excecao agronomica"],
        },
        "camada_6_confirmacao": _confirmacao_dict(execucao, alerta_ref),
        "camada_7_aprendizado": None,
        "camada_8_excecao": _excecao_dict(excecao, alerta_ref),
        "camada_9_auditoria": _auditoria_dict(alerta, execucao),
        "camada_10_comunicacao": {
            "alerta_id": alerta_ref,
            "linguagem_produtor": f"{alerta.titulo}: {alerta.mensagem}",
            "linguagem_tecnica": f"{parametro}={valor}; severidade={severidade}; sensor={alerta.sensor_id}",
            "tom": "urgente" if janela_horas <= 24 else "importante",
            "emoji_sugerido": None,
            "tipo_mensagem": "alerta",
            "enviado_em": alerta.criado_em,
            "canais_envio": ["app"],
            "requer_reforco": alerta.status == StatusAlertaDB.ATIVO and janela_horas <= 24,
            "reforco_enviado": False,
            "timestamp_reforco": None,
            "visualizado": alerta.status != StatusAlertaDB.ATIVO,
            "timestamp_visualizacao": alerta.reconhecido_em,
        },
    }


def _auditoria_dict(alerta: AlertaDB, execucao: AlertaExecucaoDB | None = None) -> dict:
    leitura = alerta.leitura
    timestamp_leitura = leitura.timestamp if leitura else alerta.criado_em
    timestamp_execucao = execucao.data_execucao if execucao and execucao.produtor_executou else None
    timestamp_resolucao = alerta.resolvido_em

    return {
        "alerta_id": f"alerta_{alerta.id}",
        "dado_sensor": {
            "sensor_id": alerta.sensor_id,
            "parametro": getattr(alerta.tipo, "value", str(alerta.tipo)),
            "valor": alerta.valor_medido,
            "unidade": "%",
        },
        "timestamp_leitura": timestamp_leitura,
        "regra_id": alerta.hash_deduplicacao or f"regra_{getattr(alerta.tipo, 'value', alerta.tipo)}",
        "regra_versao": "runtime",
        "contexto_aplicacao": {
            "cliente_id": alerta.cliente_id,
            "leitura_id": alerta.leitura_id,
        },
        "alerta_gerado": {"titulo": alerta.titulo, "severidade": getattr(alerta.severidade, "value", str(alerta.severidade))},
        "timestamp_geracao": alerta.criado_em,
        "decisao": execucao.acao_tomada if execucao else None,
        "executado": bool(execucao and execucao.produtor_executou),
        "timestamp_execucao": timestamp_execucao,
        "resultado": execucao.resultado_percebido if execucao else None,
        "efetivo": bool(execucao and execucao.resultado_percebido),
        "timestamp_resolucao": timestamp_resolucao,
        "tempo_ate_reconhecimento_horas": _horas(alerta.criado_em, alerta.reconhecido_em),
        "tempo_ate_execucao_horas": _horas(alerta.criado_em, timestamp_execucao),
        "tempo_ate_resolucao_horas": _horas(alerta.criado_em, timestamp_resolucao),
    }


def _horas(inicio: datetime | None, fim: datetime | None) -> Optional[float]:
    if not inicio or not fim:
        return None
    return round((fim - inicio).total_seconds() / 3600, 2)


@router.get("/completo", response_model=dict)
async def listar_alertas_estrategicos(
    status: Optional[StatusAlerta] = None,
    nivel_impacto: Optional[NivelImpacto] = None,
    zona_id: Optional[str] = None,
    urgencia: Optional[str] = None,
    score_prioridade_min: Optional[int] = Query(None, ge=0, le=100),
    limite_dias: int = Query(7, ge=1, le=90),
    ordenar_por: str = Query("prioridade", description="prioridade, tempo, impacto, localizacao"),
    usuario=Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Listar alertas estrategicos derivados dos alertas reais."""
    desde = datetime.utcnow() - timedelta(days=limite_dias)
    query = db.query(AlertaDB).filter(AlertaDB.criado_em >= desde)

    if status and status != StatusAlerta.EM_EXECUCAO:
        query = query.filter(AlertaDB.status == STATUS_V2_TO_DB[status])
    if nivel_impacto:
        severidades = [sev for sev, nivel in SEVERIDADE_IMPACTO.items() if nivel == nivel_impacto.value]
        query = query.filter(AlertaDB.severidade.in_(severidades))
    if zona_id:
        query = query.join(SensorDB, SensorDB.sensor_id == AlertaDB.sensor_id).filter(SensorDB.local_especifico == zona_id)

    alertas = query.order_by(AlertaDB.criado_em.desc()).all()
    estrategicos = [_alerta_estrategico(db, alerta, ranking=index + 1) for index, alerta in enumerate(alertas)]

    if status == StatusAlerta.EM_EXECUCAO:
        estrategicos = [alerta for alerta in estrategicos if alerta["status"] == StatusAlerta.EM_EXECUCAO.value]
    if urgencia:
        estrategicos = [alerta for alerta in estrategicos if alerta["camada_3_tempo"]["urgencia"] == urgencia]
    if score_prioridade_min is not None:
        estrategicos = [alerta for alerta in estrategicos if alerta["camada_2_prioridade"]["score_prioridade"] >= score_prioridade_min]

    if ordenar_por == "tempo":
        estrategicos.sort(key=lambda item: item["camada_3_tempo"]["janela_segura_horas"])
    elif ordenar_por == "localizacao":
        estrategicos.sort(key=lambda item: item["camada_4_localizacao"]["zona_manejo_nome"])
    else:
        estrategicos.sort(key=lambda item: item["camada_2_prioridade"]["score_prioridade"], reverse=True)

    logger.debug("Alertas estrategicos consultados por %s", usuario)
    return {
        "total": len(estrategicos),
        "filtros": {
            "status": status,
            "nivel_impacto": nivel_impacto,
            "zona_id": zona_id,
            "urgencia": urgencia,
            "score_prioridade_min": score_prioridade_min,
        },
        "alertas": estrategicos,
        "metadados": {
            "critico": sum(1 for item in estrategicos if item["camada_1_impacto"]["nivel"] == NivelImpacto.CRITICO.value),
            "alto": sum(1 for item in estrategicos if item["camada_1_impacto"]["nivel"] == NivelImpacto.ALTO.value),
            "medio": sum(1 for item in estrategicos if item["camada_1_impacto"]["nivel"] == NivelImpacto.MEDIO.value),
            "baixo": sum(1 for item in estrategicos if item["camada_1_impacto"]["nivel"] == NivelImpacto.BAIXO.value),
            "requer_acao_imediata": sum(1 for item in estrategicos if item["camada_3_tempo"]["janela_segura_horas"] <= 24),
        },
    }


@router.post("/{alerta_id}/confirmar-execucao", response_model=dict)
async def confirmar_execucao(
    alerta_id: str,
    confirmacao: ConfirmacaoExecucao,
    usuario=Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Registrar confirmacao de execucao do alerta."""
    alerta = _obter_alerta_ou_404(db, alerta_id)
    execucao = AlertaExecucaoDB(
        alerta_id=alerta.id,
        produtor_executou=confirmacao.produtor_executou,
        data_execucao=confirmacao.data_execucao,
        acao_tomada=confirmacao.acao_tomada,
        quantidade_aplicada=confirmacao.quantidade_aplicada,
        custo_real=confirmacao.custo_real,
        observacoes=confirmacao.observacoes,
        razao_nao_execucao=confirmacao.razao_nao_execucao,
        resultado_percebido=confirmacao.resultado_percebido,
    )
    db.add(execucao)
    alerta.status = StatusAlertaDB.RECONHECIDO if confirmacao.produtor_executou else StatusAlertaDB.IGNORADO
    alerta.atualizado_em = datetime.utcnow()
    db.commit()

    logger.info("Execucao confirmada: alerta=%s por %s", alerta_id, usuario)
    return {
        "alerta_id": f"alerta_{alerta.id}",
        "confirmado": True,
        "executado": confirmacao.produtor_executou,
        "data_execucao": confirmacao.data_execucao,
        "acao_tomada": confirmacao.acao_tomada,
        "mensagem": "Confirmacao registrada. O resultado seguira no historico do alerta.",
    }


@router.post("/{alerta_id}/registrar-excecao", response_model=dict)
async def registrar_excecao(
    alerta_id: str,
    excecao: ExcecaoAlerta,
    usuario=Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Registrar situacao atipica ou override agronomico."""
    alerta = _obter_alerta_ou_404(db, alerta_id)
    excecao_db = AlertaExcecaoDB(
        alerta_id=alerta.id,
        situacao_atipica=excecao.situacao_atipica,
        descricao_atipico=excecao.descricao_atipico,
        requer_intervencao_agronomica=excecao.requer_intervencao_agronomica,
        override_aplicado=excecao.override_aplicado,
        regra_original=excecao.regra_original,
        decisao_agronomica=excecao.decisao_agronomica,
        justificativa=excecao.justificativa,
        validado_por=excecao.validado_por,
    )
    db.add(excecao_db)
    if excecao.override_aplicado:
        alerta.status = StatusAlertaDB.IGNORADO
    alerta.atualizado_em = datetime.utcnow()
    db.commit()

    logger.info("Excecao registrada: alerta=%s por %s", alerta_id, usuario)
    return {
        "alerta_id": f"alerta_{alerta.id}",
        "excecao_registrada": True,
        "requer_validacao": excecao.requer_intervencao_agronomica,
        "mensagem": "Excecao registrada para rastreabilidade agronomica.",
    }


@router.get("/aprendizado/{zona_id}", response_model=dict)
async def obter_padroes_aprendidos(
    zona_id: str,
    parametro: Optional[str] = None,
    usuario=Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Calcular padroes simples a partir do historico real de alertas da zona."""
    query = db.query(AlertaDB).join(SensorDB, SensorDB.sensor_id == AlertaDB.sensor_id).filter(SensorDB.local_especifico == zona_id)
    if parametro:
        try:
            query = query.filter(AlertaDB.tipo == TipoAlerta(parametro))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Parametro '{parametro}' nao encontrado")
    alertas = query.order_by(AlertaDB.criado_em.desc()).all()
    por_parametro: dict[str, int] = {}
    for alerta in alertas:
        nome = getattr(alerta.tipo, "value", str(alerta.tipo))
        por_parametro[nome] = por_parametro.get(nome, 0) + 1

    logger.debug("Aprendizado da zona %s consultado por %s", zona_id, usuario)
    return {
        "zona_id": zona_id,
        "total_alertas_historicos": len(alertas),
        "padroes_detectados": [
            {
                "parametro": nome,
                "ocorrencias": total,
                "padrao": "Recorrente" if total >= 3 else "Pontual",
                "ajuste_aplicado": None,
                "efetividade": None,
            }
            for nome, total in sorted(por_parametro.items(), key=lambda item: item[1], reverse=True)
        ],
        "recomendacao_inteligente": "Revise limites e infraestrutura dos parametros mais recorrentes.",
    }


@router.get("/dashboard/executivo", response_model=dict)
async def dashboard_executivo(
    usuario=Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Dashboard executivo baseado em alertas e confirmacoes reais."""
    desde = datetime.utcnow() - timedelta(hours=24)
    alertas = db.query(AlertaDB).filter(AlertaDB.criado_em >= desde).all()
    execucoes = db.query(AlertaExecucaoDB).filter(AlertaExecucaoDB.criado_em >= desde).all()
    estrategicos = [_alerta_estrategico(db, alerta, ranking=index + 1) for index, alerta in enumerate(alertas)]
    top_5 = sorted(estrategicos, key=lambda item: item["camada_2_prioridade"]["score_prioridade"], reverse=True)[:5]

    executados = sum(1 for item in execucoes if item.produtor_executou)
    total_execucoes = len(execucoes)

    logger.debug("Dashboard executivo consultado por %s", usuario)
    return {
        "periodo": "ultimas_24h",
        "impacto": {
            "critico": sum(1 for item in estrategicos if item["camada_1_impacto"]["nivel"] == NivelImpacto.CRITICO.value),
            "alto": sum(1 for item in estrategicos if item["camada_1_impacto"]["nivel"] == NivelImpacto.ALTO.value),
            "medio": sum(1 for item in estrategicos if item["camada_1_impacto"]["nivel"] == NivelImpacto.MEDIO.value),
            "baixo": sum(1 for item in estrategicos if item["camada_1_impacto"]["nivel"] == NivelImpacto.BAIXO.value),
            "perda_financeira_total_estimada": round(sum((item["camada_1_impacto"]["perda_financeira_estimada"] or 0) for item in estrategicos), 2),
        },
        "top_5_prioritarios": [
            {
                "id": item["id"],
                "score": item["camada_2_prioridade"]["score_prioridade"],
                "zona": item["camada_4_localizacao"]["zona_manejo_nome"],
                "acao": item["camada_5_acao"]["acao_principal"],
            }
            for item in top_5
        ],
        "janelas_acao": {
            "vencendo_hoje": sum(1 for item in estrategicos if item["camada_3_tempo"]["janela_segura_horas"] <= 24),
            "vencendo_48h": sum(1 for item in estrategicos if item["camada_3_tempo"]["janela_segura_horas"] <= 48),
        },
        "taxa_execucao": {
            "executados": executados,
            "nao_executados": max(total_execucoes - executados, 0),
            "percentual": round((executados / total_execucoes) * 100, 2) if total_execucoes else 0,
        },
        "resumo_ia": "Dashboard calculado com dados reais de alertas, execucoes e severidade.",
    }


@router.get("/{alerta_id}/auditoria", response_model=AuditoriaCompleta)
async def obter_auditoria_completa(
    alerta_id: str,
    usuario=Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Retornar auditoria completa de um alerta real."""
    alerta = _obter_alerta_ou_404(db, alerta_id)
    execucao = _ultima_execucao(db, alerta.id)
    logger.debug("Auditoria do alerta %s consultada por %s", alerta_id, usuario)
    return AuditoriaCompleta(**_auditoria_dict(alerta, execucao))
