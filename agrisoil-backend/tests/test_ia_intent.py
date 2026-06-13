"""
Testes da classificação de intenção da IA agro (ETAPA 2 / ETAPA 8).

Garante que perguntas naturais, curtas, informais e contextuais NÃO caiam
indevidamente em ``fora_escopo`` e que perguntas externas continuem bloqueadas.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.services.intent_classifier import (
    MODO_AGRO_COM_DADOS,
    MODO_AGRO_GERAL,
    MODO_ESCLARECIMENTO,
    MODO_FORA_ESCOPO,
    classificar,
)

CLIENTE = "agrisoil"
SENSOR = "estufa-1-canteiro-03"


# 1 a 15 e 21 a 25: com contexto adequado NÃO podem virar fora_escopo.
PERGUNTAS_COM_DADOS = [
    "Como estão minhas áreas?",
    "Como estão meus canteiros?",
    "Qual está pior?",
    "Tem algo precisando de atenção?",
    "Como está a situação?",
    "E o Canteiro 03?",
    "E esse aqui?",
    "Está bom?",
    "Preciso irrigar?",
    "Analise minha propriedade.",
    "O que faço primeiro?",
    "como tao minhas area",
    "qual cantero ta pior",
    "precisa irriga",
    "olha tudo pra mim",
    "tem alguma coisa errada",
    "como está tudo",
    "qual área está ruim",
    "e o outro",
    "esse sensor está bom",
]


@pytest.mark.parametrize("pergunta", PERGUNTAS_COM_DADOS)
def test_perguntas_naturais_nao_caem_em_fora_escopo(pergunta):
    modo = classificar(pergunta, cliente_id=CLIENTE)
    assert modo != MODO_FORA_ESCOPO
    assert modo in (MODO_AGRO_COM_DADOS, MODO_AGRO_GERAL, MODO_ESCLARECIMENTO)


@pytest.mark.parametrize("pergunta", PERGUNTAS_COM_DADOS)
def test_perguntas_naturais_com_cliente_viram_agro_com_dados(pergunta):
    assert classificar(pergunta, cliente_id=CLIENTE) == MODO_AGRO_COM_DADOS


@pytest.mark.parametrize(
    "pergunta",
    [
        "Como plantar batata-doce?",
        "O que é pH?",
        "Sensor NPK substitui análise laboratorial?",
        "O que significa condutividade elétrica?",
        "Como funciona irrigação?",
        "Para que serve o potássio?",
    ],
)
def test_perguntas_agro_geral(pergunta):
    assert classificar(pergunta, cliente_id=CLIENTE) == MODO_AGRO_GERAL


@pytest.mark.parametrize(
    "pergunta",
    [
        "Qual é a capital da Itália?",
        "Faça um código Java.",
        "Quem ganhou o jogo?",
        "Escreva uma redação.",
        "Me explique física quântica.",
        "Crie uma página HTML.",
    ],
)
def test_perguntas_fora_escopo(pergunta):
    assert classificar(pergunta, cliente_id=CLIENTE) == MODO_FORA_ESCOPO


def test_referencia_contextual_com_sensor_vira_agro_com_dados():
    assert classificar("E esse aqui?", cliente_id=CLIENTE, sensor_id=SENSOR) == MODO_AGRO_COM_DADOS
    assert classificar("Está bom?", cliente_id=CLIENTE, sensor_id=SENSOR) == MODO_AGRO_COM_DADOS


def test_sensor_id_com_pergunta_geral_continua_agro_geral():
    # Usuário tem um sensor aberto, mas faz pergunta de conhecimento geral.
    assert classificar("O que é pH?", cliente_id=CLIENTE, sensor_id=SENSOR) == MODO_AGRO_GERAL


def test_ambiguo_sem_contexto_pede_esclarecimento():
    assert classificar("Como está?") == MODO_ESCLARECIMENTO
    assert classificar("Está bom?") == MODO_ESCLARECIMENTO


def test_ambiguo_com_cliente_tenta_visao_geral():
    assert classificar("Como está?", cliente_id=CLIENTE) == MODO_AGRO_COM_DADOS


def test_deixis_sem_contexto_nao_e_fora_escopo():
    # Sem cliente nem sensor, "e o outro?" é ambíguo, mas não é externo.
    assert classificar("e o outro") in (MODO_ESCLARECIMENTO, MODO_AGRO_COM_DADOS)


def test_compatibilidade_texto_apenas():
    assert classificar("Qual capital da Itália?") == MODO_FORA_ESCOPO
    assert classificar("O que é milho?") == MODO_AGRO_GERAL
    assert classificar("Como plantar soja?") == MODO_AGRO_GERAL
    assert classificar("O que fazer com potássio baixo?") == MODO_AGRO_GERAL
    assert classificar("O que fazer com esse potássio baixo?") == MODO_AGRO_COM_DADOS
    assert classificar("Qual o principal risco desse sensor agora?") == MODO_AGRO_COM_DADOS
