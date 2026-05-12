"""
Rotas de Biblioteca (Master Data).
Catalogos tecnicos versionados em codigo para culturas, fases, parametros
ideais e regras base. Pode migrar para Supabase depois sem mudar contrato.
"""

import logging

from fastapi import APIRouter, HTTPException, status

from app.models.contexto_fixo import FaseFenologica, NomeCultura

router = APIRouter(prefix="/api/biblioteca", tags=["Biblioteca"])
logger = logging.getLogger(__name__)


FASES_PADRAO = [
    {"fase": FaseFenologica.EMERGENCIA.value, "dia_inicio": 1, "dia_fim": 15, "descricao": "Emergencia das plantulas"},
    {"fase": FaseFenologica.VEGETATIVO.value, "dia_inicio": 16, "dia_fim": 45, "descricao": "Desenvolvimento vegetativo"},
    {"fase": FaseFenologica.FLORESCIMENTO.value, "dia_inicio": 46, "dia_fim": 65, "descricao": "Florescimento"},
    {"fase": FaseFenologica.ENCHIMENTO_GRAOS.value, "dia_inicio": 66, "dia_fim": 100, "descricao": "Enchimento de graos"},
    {"fase": FaseFenologica.MATURACAO.value, "dia_inicio": 101, "dia_fim": 125, "descricao": "Maturacao"},
    {"fase": FaseFenologica.COLHEITA.value, "dia_inicio": 126, "dia_fim": 140, "descricao": "Colheita"},
]

PARAMETROS_BASE = {
    "umidade": {
        "unidade": "%",
        "minimo_ideal": 25,
        "maximo_ideal": 35,
        "minimo_alerta": 22,
        "maximo_alerta": 40,
        "minimo_critico": 20,
        "maximo_critico": 45,
        "impacto_desvio": "Umidade fora da faixa reduz germinacao, vigor e absorcao de nutrientes.",
    },
    "ph": {
        "unidade": "pH",
        "minimo_ideal": 6.0,
        "maximo_ideal": 7.5,
        "minimo_alerta": 5.5,
        "maximo_alerta": 8.0,
        "minimo_critico": 4.5,
        "maximo_critico": 8.5,
        "impacto_desvio": "pH fora da faixa compromete disponibilidade de nutrientes.",
    },
    "temperatura": {
        "unidade": "C",
        "minimo_ideal": 20,
        "maximo_ideal": 30,
        "minimo_alerta": 18,
        "maximo_alerta": 32,
        "minimo_critico": 15,
        "maximo_critico": 35,
        "impacto_desvio": "Temperatura inadequada atrasa desenvolvimento e aumenta estresse.",
    },
    "nitrogenio": {
        "unidade": "mg/kg",
        "minimo_ideal": 20,
        "maximo_ideal": 60,
        "minimo_alerta": 15,
        "maximo_alerta": 75,
        "minimo_critico": 10,
        "maximo_critico": 90,
        "impacto_desvio": "Nitrogenio baixo reduz crescimento vegetativo e potencial produtivo.",
    },
}

REGRAS_BASE = {
    FaseFenologica.EMERGENCIA.value: [
        {
            "id": "regra-emergencia-umidade",
            "parametro": "umidade",
            "titulo": "Umidade baixa durante emergencia",
            "mensagem_produtor": "A zona esta seca para emergencia. Validar chuva/irrigacao nas proximas 24h.",
            "acao_recomendada": "irrigar",
            "urgencia_acao": "24h",
        }
    ],
    FaseFenologica.VEGETATIVO.value: [
        {
            "id": "regra-vegetativo-nitrogenio",
            "parametro": "nitrogenio",
            "titulo": "Nitrogenio abaixo do ideal",
            "mensagem_produtor": "A cultura pode perder vigor se a deficiencia continuar.",
            "acao_recomendada": "adubar_npk",
            "urgencia_acao": "48h",
        }
    ],
    FaseFenologica.FLORESCIMENTO.value: [
        {
            "id": "regra-florescimento-umidade",
            "parametro": "umidade",
            "titulo": "Estresse hidrico no florescimento",
            "mensagem_produtor": "Florescimento e uma fase sensivel. Priorize verificacao em campo.",
            "acao_recomendada": "irrigar",
            "urgencia_acao": "24h",
        }
    ],
}


def _validar_cultura(cultura: str) -> NomeCultura:
    try:
        return NomeCultura(cultura.lower())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Cultura '{cultura}' nao encontrada")


def _validar_fase(fase: str) -> FaseFenologica:
    try:
        return FaseFenologica(fase.lower())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Fase '{fase}' nao encontrada")


@router.get("/culturas", response_model=dict)
async def listar_culturas():
    """Listar culturas disponiveis no sistema."""
    culturas = [
        {
            "id": cultura.value,
            "nome": cultura.value.replace("_", " ").title(),
            "descricao": f"Cultura de {cultura.value.replace('_', ' ')}",
        }
        for cultura in NomeCultura
    ]
    return {"total": len(culturas), "culturas": culturas}


@router.get("/culturas/{cultura}", response_model=dict)
async def obter_cultura_detalhes(cultura: str):
    """Obter detalhes tecnicos de uma cultura."""
    cultura_enum = _validar_cultura(cultura)
    return {
        "id": cultura_enum.value,
        "nome": cultura_enum.value.replace("_", " ").title(),
        "ciclo_dias": FASES_PADRAO[-1]["dia_fim"],
        "fases": FASES_PADRAO,
    }


@router.get("/parametros-ideais/{cultura}/{fase}", response_model=dict)
async def obter_parametros_ideais(cultura: str, fase: str):
    """Obter parametros ideais para uma cultura em uma fase."""
    cultura_enum = _validar_cultura(cultura)
    fase_enum = _validar_fase(fase)
    parametros = [{"parametro": nome, **dados} for nome, dados in PARAMETROS_BASE.items()]
    return {"cultura": cultura_enum.value, "fase": fase_enum.value, "parametros": parametros}


@router.get("/regras/{cultura}", response_model=dict)
async def obter_regras_cultura(cultura: str):
    """Obter regras base de alerta para uma cultura."""
    cultura_enum = _validar_cultura(cultura)
    total_regras = sum(len(regras) for regras in REGRAS_BASE.values())
    regras = {
        fase: [
            {
                **regra,
                "id": regra["id"].replace("regra-", f"regra-{cultura_enum.value}-"),
            }
            for regra in regras_fase
        ]
        for fase, regras_fase in REGRAS_BASE.items()
    }
    return {"cultura": cultura_enum.value, "total_regras": total_regras, "regras_por_fase": regras}


@router.get("/fases", response_model=dict)
async def listar_fases():
    """Listar fases fenologicas disponiveis."""
    return {"fases": [fase.value for fase in FaseFenologica], "total": len(list(FaseFenologica))}
