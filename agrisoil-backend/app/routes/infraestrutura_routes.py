"""
Rotas de infraestrutura de propriedades.
Gerencia equipamentos e recursos disponiveis para contextualizar alertas.
"""

import logging
from statistics import mean

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.database import InfraestruturaDB
from app.models.infraestrutura import (
    InfraestruturaPropiedade,
    RecomendacaoContextualizada,
    adaptar_recomendacao_calcario,
    adaptar_recomendacao_irrigacao,
)
from app.security import obter_usuario_atual

router = APIRouter(prefix="/api/infraestrutura", tags=["Infraestrutura de Propriedades"])
logger = logging.getLogger(__name__)


def _enum_list(values):
    return [getattr(value, "value", value) for value in (values or [])]


def _enum_value(value):
    return getattr(value, "value", value)


def _infra_to_model(infra: InfraestruturaDB) -> InfraestruturaPropiedade:
    return InfraestruturaPropiedade(
        propriedade_id=infra.propriedade_id,
        produtor_nome=infra.produtor_nome,
        possui_irrigacao=infra.possui_irrigacao,
        sistemas_irrigacao=infra.sistemas_irrigacao or [],
        area_irrigada_ha=infra.area_irrigada_ha,
        fonte_agua=infra.fonte_agua,
        capacidade_agua_m3_dia=infra.capacidade_agua_m3_dia,
        equipamentos_aplicacao=infra.equipamentos_aplicacao or [],
        possui_hangar_aeronave=infra.possui_hangar_aeronave,
        possui_maquinario_proprio=infra.possui_maquinario_proprio,
        possui_armazem=infra.possui_armazem,
        capacidade_armazem_ton=infra.capacidade_armazem_ton,
        possui_silo=infra.possui_silo,
        possui_energia_eletrica=infra.possui_energia_eletrica,
        possui_geradores=infra.possui_geradores,
        limitacoes=infra.limitacoes or [],
        depende_terceiros_para=infra.depende_terceiros_para or [],
        custo_medio_terceiros=infra.custo_medio_terceiros or {},
    )


def _payload_infra(infraestrutura: InfraestruturaPropiedade) -> dict:
    return {
        "propriedade_id": infraestrutura.propriedade_id,
        "produtor_nome": infraestrutura.produtor_nome,
        "possui_irrigacao": infraestrutura.possui_irrigacao,
        "sistemas_irrigacao": _enum_list(infraestrutura.sistemas_irrigacao),
        "area_irrigada_ha": infraestrutura.area_irrigada_ha,
        "fonte_agua": _enum_value(infraestrutura.fonte_agua),
        "capacidade_agua_m3_dia": infraestrutura.capacidade_agua_m3_dia,
        "equipamentos_aplicacao": _enum_list(infraestrutura.equipamentos_aplicacao),
        "possui_hangar_aeronave": infraestrutura.possui_hangar_aeronave,
        "possui_maquinario_proprio": infraestrutura.possui_maquinario_proprio,
        "possui_armazem": infraestrutura.possui_armazem,
        "capacidade_armazem_ton": infraestrutura.capacidade_armazem_ton,
        "possui_silo": infraestrutura.possui_silo,
        "possui_energia_eletrica": infraestrutura.possui_energia_eletrica,
        "possui_geradores": infraestrutura.possui_geradores,
        "limitacoes": infraestrutura.limitacoes or [],
        "depende_terceiros_para": infraestrutura.depende_terceiros_para or [],
        "custo_medio_terceiros": infraestrutura.custo_medio_terceiros or {},
        "ativo": True,
    }


def _obter_infra_ou_404(db: Session, propriedade_id: str) -> InfraestruturaDB:
    infra = db.query(InfraestruturaDB).filter(
        InfraestruturaDB.propriedade_id == propriedade_id,
        InfraestruturaDB.ativo.is_(True),
    ).first()
    if not infra:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Infraestrutura nao encontrada")
    return infra


def _avisos(infraestrutura: InfraestruturaPropiedade) -> list[str]:
    avisos = []
    if not infraestrutura.possui_irrigacao:
        avisos.append("Sem sistema de irrigacao: recomendacoes serao adaptadas para alternativas viaveis")
    if not infraestrutura.possui_maquinario_proprio:
        avisos.append("Sem maquinario proprio: custos de terceirizacao serao considerados")
    if infraestrutura.limitacoes:
        avisos.append(f"{len(infraestrutura.limitacoes)} limitacoes cadastradas serao consideradas nas recomendacoes")
    return avisos


@router.post("/propriedade", response_model=dict)
async def cadastrar_infraestrutura(
    infraestrutura: InfraestruturaPropiedade,
    usuario=Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Cadastrar ou atualizar infraestrutura da propriedade."""
    payload = _payload_infra(infraestrutura)
    infra_db = db.query(InfraestruturaDB).filter(
        InfraestruturaDB.propriedade_id == infraestrutura.propriedade_id,
    ).first()

    if infra_db:
        for field, value in payload.items():
            setattr(infra_db, field, value)
    else:
        infra_db = InfraestruturaDB(**payload)
        db.add(infra_db)

    db.commit()
    db.refresh(infra_db)

    logger.info("Infraestrutura salva para %s por %s", infraestrutura.propriedade_id, usuario)
    return {
        "sucesso": True,
        "propriedade_id": infraestrutura.propriedade_id,
        "mensagem": "Infraestrutura cadastrada com sucesso",
        "avisos": _avisos(infraestrutura),
        "proximos_passos": [
            "Alertas agora serao contextualizados para a realidade da propriedade",
            "Recomendacoes vao considerar equipamentos disponiveis",
            "Custos de terceirizacao entram quando necessarios",
        ],
    }


@router.get("/propriedade/{propriedade_id}", response_model=InfraestruturaPropiedade)
async def obter_infraestrutura(
    propriedade_id: str,
    usuario=Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Obter infraestrutura cadastrada de uma propriedade."""
    logger.debug("Infraestrutura %s consultada por %s", propriedade_id, usuario)
    return _infra_to_model(_obter_infra_ou_404(db, propriedade_id))


@router.post("/simular-recomendacao", response_model=RecomendacaoContextualizada)
async def simular_recomendacao(
    propriedade_id: str,
    tipo_acao: str,
    area_ha: float,
    usuario=Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Simular recomendacao baseada na infraestrutura real cadastrada."""
    if area_ha <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="area_ha deve ser maior que zero")

    infraestrutura = _infra_to_model(_obter_infra_ou_404(db, propriedade_id))
    logger.debug("Simulacao %s para %s por %s", tipo_acao, propriedade_id, usuario)

    if tipo_acao == "irrigar":
        return adaptar_recomendacao_irrigacao(infraestrutura, area_ha)
    if tipo_acao == "aplicar_calcario":
        return adaptar_recomendacao_calcario(infraestrutura, area_ha)

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Tipo de acao '{tipo_acao}' nao suportado")


@router.get("/checklist", response_model=dict)
async def checklist_infraestrutura(usuario=Depends(obter_usuario_atual)):
    """Checklist para ajudar produtor a cadastrar infraestrutura."""
    return {
        "titulo": "O que voce possui na sua propriedade?",
        "categorias": [
            {
                "categoria": "Irrigacao",
                "perguntas": [
                    "Voce possui algum sistema de irrigacao?",
                    "Qual tipo? Pivo central, aspersao, gotejamento etc.",
                    "Quantos hectares consegue irrigar?",
                    "De onde vem a agua?",
                    "Quantos m3 de agua consegue usar por dia?",
                ],
            },
            {
                "categoria": "Equipamentos",
                "perguntas": [
                    "Possui trator proprio?",
                    "Possui pulverizador? Qual tipo?",
                    "Possui distribuidor de adubo ou calcario?",
                    "Possui plantadeira/semeadora?",
                    "Possui colheitadeira?",
                ],
            },
            {
                "categoria": "Infraestrutura",
                "perguntas": [
                    "Possui armazem? Qual capacidade?",
                    "Possui silo?",
                    "Possui energia eletrica?",
                    "Possui geradores?",
                ],
            },
            {
                "categoria": "Terceirizacao",
                "perguntas": [
                    "Quais servicos voce contrata de terceiros?",
                    "Quanto custa em media por hectare?",
                    "Ha limitacoes de epoca, agenda ou disponibilidade?",
                ],
            },
        ],
        "dica": "Quanto mais completo o cadastro, mais precisas serao as recomendacoes do sistema.",
    }


@router.get("/estatisticas", response_model=dict)
async def estatisticas_infraestrutura(
    usuario=Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Estatisticas agregadas de infraestrutura cadastrada."""
    infraestruturas = db.query(InfraestruturaDB).filter(InfraestruturaDB.ativo.is_(True)).all()
    total = len(infraestruturas)
    if total == 0:
        return {
            "total_propriedades": 0,
            "irrigacao": {"possui_algum_sistema_percentual": 0, "tipos_mais_comuns": []},
            "terceirizacao": {"servicos_mais_terceirizados": [], "custos_medios": {}},
            "equipamentos": {"maquinario_proprio_percentual": 0, "armazem_percentual": 0},
        }

    def percentual(condicao):
        return round((sum(1 for item in infraestruturas if condicao(item)) / total) * 100, 2)

    servicos = {}
    custos = {}
    tipos_irrigacao = {}
    for infra in infraestruturas:
        for tipo in infra.sistemas_irrigacao or []:
            tipos_irrigacao[tipo] = tipos_irrigacao.get(tipo, 0) + 1
        for servico in infra.depende_terceiros_para or []:
            servicos[servico] = servicos.get(servico, 0) + 1
        for nome, valor in (infra.custo_medio_terceiros or {}).items():
            custos.setdefault(nome, []).append(float(valor))

    custos_medios = {nome: round(mean(valores), 2) for nome, valores in custos.items()}

    logger.debug("Estatisticas de infraestrutura consultadas por %s", usuario)
    return {
        "total_propriedades": total,
        "irrigacao": {
            "possui_algum_sistema_percentual": percentual(lambda item: item.possui_irrigacao),
            "tipos_mais_comuns": sorted(tipos_irrigacao, key=tipos_irrigacao.get, reverse=True)[:5],
        },
        "terceirizacao": {
            "servicos_mais_terceirizados": sorted(servicos, key=servicos.get, reverse=True)[:8],
            "custos_medios": custos_medios,
        },
        "equipamentos": {
            "maquinario_proprio_percentual": percentual(lambda item: item.possui_maquinario_proprio),
            "armazem_percentual": percentual(lambda item: item.possui_armazem),
            "energia_eletrica_percentual": percentual(lambda item: item.possui_energia_eletrica),
        },
    }
