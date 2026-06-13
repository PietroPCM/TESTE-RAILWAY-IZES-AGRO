"""
Testes da correção estrutural da IA (decisão, clima, entidades, metadados).

Validam COMPORTAMENTO e INVARIANTES (não textos prontos). Mockam apenas as
fronteiras externas (OpenAI e serviço climático). A lógica interna
(classificação, entidades, seleção, origem, validade, confiança, fontes) roda
de verdade. Usam IDs/valores variados para evitar overfitting.
"""

import asyncio
import json
import os
import sys
import types
from pathlib import Path

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models.contratos import ContextoIA, SensorInfo
from app.models.database import LeituraDB, SensorDB
import app.routes.ia_routes as ia_routes
from app.routes.ia_routes import chat_ia
from app.services.ia import metadados
from app.services.ia.decisao import (
    MODO_AGRO_COM_DADOS, MODO_AGRO_GERAL, MODO_CLIMA, MODO_ESCLARECIMENTO,
    MODO_FORA_ESCOPO, decidir,
)
from app.services.ia.localizacao import resolver_localizacao
from app.services.ia.selecao import destacar, filtrar_sensores
from app.services.openai_service import ServicoOpenAI


# ============================================================ helpers de dados
def _sensorinfo(sensor_id, nome, leitura=None, lat=None, lon=None, municipio=None):
    return SensorInfo(
        sensor_id=sensor_id, nome=nome, propriedade="Prop", tipo="solo",
        localizacao={"latitude": lat, "longitude": lon, "municipio": municipio, "estado": "PR"},
        ultima_leitura=leitura,
    )


def _ctx(pergunta, sensores=None, cliente="cli", cultura=None):
    return ContextoIA(cliente_id=cliente, usuario_pergunta=pergunta,
                      sensores_relevantes=sensores or [], cultura=cultura)


# ===================================================================== DECISÃO
@pytest.mark.parametrize("pergunta", [
    "Vai chover hoje?", "Tem chuva amanhã?", "Como fica o tempo na propriedade?",
    "Há risco de geada?", "Qual a previsão da semana?",
])
def test_decisao_clima(pergunta):
    d = decidir(pergunta, cliente_id="cli")
    assert d.necessita_clima is True
    assert d.modo in (MODO_CLIMA, MODO_AGRO_COM_DADOS)


def test_decisao_hibrida_clima_e_dados():
    d = decidir("Devo considerar chuva antes de irrigar?", cliente_id="cli")
    assert d.necessita_clima is True
    assert d.necessita_dados_cliente is True


@pytest.mark.parametrize("pergunta,esperado_tipo", [
    ("Qual canteiro está mais seco?", "canteiro"),
    ("Compare minhas estufas.", "estufa"),
    ("Qual talhão tem o menor pH?", "talhao"),
    ("Qual ponto tem maior umidade?", "sensor"),
])
def test_decisao_entidade_e_comparacao(pergunta, esperado_tipo):
    d = decidir(pergunta, cliente_id="cli")
    assert d.tipo_entidade == esperado_tipo
    assert d.comparacao is True
    assert d.necessita_dados_cliente is True


@pytest.mark.parametrize("pergunta", [
    "Como está?", "Tudo certo por aí?", "Há algo preocupante?",
    "Dá uma olhada nas minhas áreas.", "O que merece atenção hoje?", "como tao as coisa",
])
def test_decisao_visao_geral_com_cliente(pergunta):
    assert decidir(pergunta, cliente_id="cli").modo == MODO_AGRO_COM_DADOS


@pytest.mark.parametrize("pergunta", ["Como está?", "Tem algo errado?", "E aí?"])
def test_decisao_sem_contexto_pede_esclarecimento(pergunta):
    # Sem cliente nem sensor, perguntas dependentes de dados pedem esclarecimento.
    assert decidir(pergunta).modo in (MODO_ESCLARECIMENTO, MODO_FORA_ESCOPO)


@pytest.mark.parametrize("pergunta", [
    "Explique acidez do solo.", "Como sensores de umidade funcionam?", "O que é condutividade elétrica?",
])
def test_decisao_agro_geral_nao_usa_dados(pergunta):
    d = decidir(pergunta, cliente_id="cli")
    assert d.modo == MODO_AGRO_GERAL
    assert d.necessita_dados_cliente is False


@pytest.mark.parametrize("pergunta", ["Escreva código Java.", "Qual a capital da Itália?", "Quem venceu o campeonato?"])
def test_decisao_fora_escopo(pergunta):
    d = decidir(pergunta, cliente_id="cli")
    assert d.modo == MODO_FORA_ESCOPO
    assert d.necessita_openai is False


# ==================================================== SELEÇÃO (não-overfitting)
@pytest.mark.parametrize("v_a,v_b,mais_seco_id", [
    (18.0, 44.0, "s_b_diff"),   # b é id, a tem 18 -> a mais seco? ver abaixo
    (50.0, 12.0, "s_b_diff"),
    (30.0, 30.0, "s_a_diff"),   # empate -> min estável escolhe o primeiro
])
def test_destacar_segue_os_dados_nao_o_id(v_a, v_b, mais_seco_id):
    s_a = _sensorinfo("s_a_diff", "Canteiro X", {"umidade": v_a})
    s_b = _sensorinfo("s_b_diff", "Canteiro Y", {"umidade": v_b})
    resultado = destacar([s_a, s_b], "umidade", preferir_menor=True)
    esperado = "s_a_diff" if v_a <= v_b else "s_b_diff"
    assert resultado["destaque"]["sensor_id"] == esperado


def test_filtro_entidade_exclui_tipo_errado():
    sensores = [
        _sensorinfo("t1", "Talhão Norte", {"umidade": 20}),
        _sensorinfo("t2", "Talhão Sul", {"umidade": 35}),
        _sensorinfo("e1", "Estufa Central", {"umidade": 40}),
    ]
    d = decidir("Qual talhão está mais seco?", cliente_id="cli")
    resultado = filtrar_sensores(sensores, d)
    ids = {s.sensor_id for s in resultado.sensores}
    assert ids == {"t1", "t2"}
    assert "e1" not in ids


def test_filtro_cultura():
    sensores = [
        _sensorinfo("a", "Área Soja Leste", {"umidade": 20}),
        _sensorinfo("b", "Canteiro Milho 1", {"umidade": 35}),
    ]
    d = decidir("Como está minha soja?", cliente_id="cli")
    resultado = filtrar_sensores(sensores, d)
    assert {s.sensor_id for s in resultado.sensores} == {"a"}


# ===================================================================== LOCALIZAÇÃO
def test_resolver_localizacao_usa_sensor_com_coordenadas():
    sensores = [_sensorinfo("s1", "A", lat=None, lon=None), _sensorinfo("s2", "B", lat=-25.4, lon=-49.2)]
    loc = resolver_localizacao(sensores)
    assert loc is not None
    assert (loc.latitude, loc.longitude) == (-25.4, -49.2)


def test_resolver_localizacao_none_sem_coordenadas():
    sensores = [_sensorinfo("s1", "A")]
    assert resolver_localizacao(sensores) is None


# ===================================================================== METADADOS
def test_origem_reflete_recursos():
    assert metadados.calcular_origem(usou_openai=True, usou_dados=True) == "openai_com_dados"
    assert metadados.calcular_origem(usou_openai=True, usou_dados=True, usou_rag=True) == "openai_com_dados_e_rag"
    assert metadados.calcular_origem(usou_openai=True, usou_dados=True, usou_clima=True, usou_rag=True) == "openai_com_dados_clima_e_rag"
    assert metadados.calcular_origem(usou_openai=False, usou_clima=True, apenas_clima=True) == "servico_climatico"
    assert metadados.calcular_origem(usou_openai=False, fallback=True) == "fallback_local"


def test_validade_depende_do_tipo():
    assert metadados.calcular_validade("agro_geral") is None
    assert metadados.calcular_validade("fora_escopo") is None
    assert metadados.calcular_validade("esclarecimento") is None
    clima = metadados.calcular_validade("clima", usou_clima=True)
    assert clima and "ate" in clima
    dados = metadados.calcular_validade("agro_com_dados", tem_dados=True)
    assert dados and "muda" in dados["razao"].lower()


def test_confianca_normalizada():
    assert metadados.normalizar_confianca(0) == 0.6          # 0 -> base, não zero
    assert metadados.normalizar_confianca(None) == 0.6
    assert metadados.normalizar_confianca("xx") == 0.6
    assert metadados.normalizar_confianca(float("nan")) == 0.6
    assert 0.0 <= metadados.normalizar_confianca(0.9, penalidades={"dados_ausentes": True}) <= 1.0
    assert metadados.normalizar_confianca(0.9, penalidades={"rag_fraco": True}) < 0.9


# ===================================================== OpenAI mock (fronteira)
class _FakeResp:
    def __init__(self, content, tokens=100):
        self.choices = [types.SimpleNamespace(message=types.SimpleNamespace(content=content))]
        self.usage = types.SimpleNamespace(total_tokens=tokens)


def _servico_openai(monkeypatch, payload, captura=None):
    monkeypatch.setattr(settings, "openai_api_key", "fake-key")
    servico = ServicoOpenAI()
    servico.disponivel = True
    servico.model = "gpt-fake"

    class _Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    if captura is not None:
                        captura["prompt"] = kwargs["messages"][1]["content"]
                    return _FakeResp(json.dumps(payload, ensure_ascii=False))

    servico.client = _Client()
    return servico


def _payload(**over):
    base = {
        "resposta_texto": "Situação: ok.\n\nRisco: baixo.\n\nO que fazer agora:\n1. Conferir.\n2. Avaliar.\n3. Validar.",
        "recomendacao": {"acao": "Avaliar em campo.", "motivo": "m", "riscos_se_nao_fizer": "r", "beneficios": "b"},
        "atencoes": ["a"], "proximos_passos": ["p"], "confianca_geral": 0.8,
    }
    base.update(over)
    return base


def test_confianca_nao_zera_por_campo_ausente(monkeypatch):
    sensores = [_sensorinfo("s1", "Canteiro", {"umidade": 22})]
    ctx = _ctx("Como está esse canteiro?", sensores)
    servico = _servico_openai(monkeypatch, _payload(confianca_geral=0))
    d = decidir("Como está esse canteiro?", cliente_id="cli")
    resp = asyncio.run(servico.analisar_contexto(ctx, "pid", decisao=d))
    assert resp.confianca_geral > 0.0


def test_recomendacao_perigosa_e_suavizada(monkeypatch):
    sensores = [_sensorinfo("s1", "Canteiro", {"umidade": 22})]
    ctx = _ctx("Preciso irrigar esse canteiro?", sensores)
    payload = _payload(
        resposta_texto="Situação: seco.\n\nO que fazer agora:\n1. Irrigue agora.",
        recomendacao={"acao": "Irrigue agora 2 horas.", "motivo": "m", "riscos_se_nao_fizer": "r", "beneficios": "b"},
    )
    servico = _servico_openai(monkeypatch, payload)
    d = decidir("Preciso irrigar esse canteiro?", cliente_id="cli")
    resp = asyncio.run(servico.analisar_contexto(ctx, "pid", decisao=d))
    assert "irrigue agora" not in resp.recomendacao.acao.lower()
    assert "irrigue agora" not in resp.resposta_texto.lower()


def test_fontes_apenas_declaradas(monkeypatch):
    sensores = [_sensorinfo("s1", "Canteiro", {"umidade": 22})]
    ctx = _ctx("Como está a umidade do solo nesse canteiro?", sensores)
    captura = {}
    # Modelo NÃO declara nenhum documento -> nenhuma fonte deve ser exposta.
    servico = _servico_openai(monkeypatch, _payload(documento_ids_utilizados=[]), captura)
    d = decidir("Como está a umidade do solo nesse canteiro?", cliente_id="cli")
    resp = asyncio.run(servico.analisar_contexto(ctx, "pid", decisao=d))
    assert resp.fontes == []


def test_fonte_declarada_inexistente_nao_e_aceita(monkeypatch):
    sensores = [_sensorinfo("s1", "Canteiro", {"umidade": 22})]
    ctx = _ctx("Como está a umidade do solo nesse canteiro?", sensores)
    # Modelo "alucina" um id que não estava no contexto -> não pode entrar.
    servico = _servico_openai(monkeypatch, _payload(documento_ids_utilizados=["DOC_INEXISTENTE_999"]))
    d = decidir("Como está a umidade do solo nesse canteiro?", cliente_id="cli")
    resp = asyncio.run(servico.analisar_contexto(ctx, "pid", decisao=d))
    assert all(f["documento_id"] != "DOC_INEXISTENTE_999" for f in resp.fontes)


def test_validade_nao_universal_em_agro_geral(monkeypatch):
    ctx = _ctx("O que é pH?")
    servico = _servico_openai(monkeypatch, _payload())
    d = decidir("O que é pH?", cliente_id="cli")
    resp = asyncio.run(servico.analisar_contexto(ctx, "pid", decisao=d))
    assert resp.validade is None


# =================================================== CLIMA (fronteira mockada)
def _fake_clima_resposta(prob=80, cidade="Curitiba"):
    return types.SimpleNamespace(
        localizacao=types.SimpleNamespace(cidade=cidade, latitude=-25.4, longitude=-49.2),
        clima_atual=types.SimpleNamespace(temperatura=21.0, sensacao_termica=21.0, umidade=70,
                                          descricao="parcialmente nublado", vento=3.0),
        previsao_resumo=types.SimpleNamespace(resumo="chuva à tarde", probabilidade_chuva=prob, precipitacao_mm=5.0),
        alerta_clima=types.SimpleNamespace(risco_geada=False, risco_seca=False, mensagem="estável"),
    )


def _seed_cliente_com_coords(db, cliente, sensor_id, lat=-25.4, lon=-49.2):
    Base.metadata.create_all(bind=engine)
    db.query(LeituraDB).filter(LeituraDB.cliente_id == cliente).delete()
    db.query(SensorDB).filter(SensorDB.cliente_id == cliente).delete()
    db.commit()
    db.add(SensorDB(sensor_id=sensor_id, cliente_id=cliente, nome="Canteiro Clima", tipo="solo",
                    ativo=True, propriedade="Prop", municipio="Curitiba", estado="PR",
                    latitude=lat, longitude=lon))
    db.commit()
    db.add(LeituraDB(sensor_id=sensor_id, cliente_id=cliente, umidade=30.0))
    db.commit()


def test_clima_usa_servico_e_localizacao_do_cliente(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")  # sem OpenAI -> resumo determinístico
    cliente = "cli_clima_1"
    db = SessionLocal()
    try:
        _seed_cliente_com_coords(db, cliente, "sclima1")

        chamadas = {}

        async def fake_clima(lat, lon, **kw):
            chamadas["coords"] = (lat, lon)
            return _fake_clima_resposta(prob=90)

        monkeypatch.setattr(ia_routes.servico_clima, "obter_clima_por_coordenadas", fake_clima)

        resp = asyncio.run(chat_ia(cliente_id=cliente, pergunta="Vai chover amanhã?",
                                   sensor_id=None, x_app_token="t", db=db))
        assert chamadas["coords"] == (-25.4, -49.2)
        assert resp.resposta_estruturada["modo"] == MODO_CLIMA
        assert resp.resposta_estruturada["origem"] == "servico_climatico"
        assert resp.validade and "ate" in resp.validade
        assert "clima" in resp.recursos_utilizados
        assert "90" in resp.resposta_texto
        assert resp.resposta_texto.strip().lower().endswith("é só pedir.")
    finally:
        db.query(LeituraDB).filter(LeituraDB.cliente_id == cliente).delete()
        db.query(SensorDB).filter(SensorDB.cliente_id == cliente).delete()
        db.commit(); db.close()


def test_clima_falha_retorna_resposta_controlada(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    cliente = "cli_clima_2"
    db = SessionLocal()
    try:
        _seed_cliente_com_coords(db, cliente, "sclima2")

        async def fake_clima_falha(lat, lon, **kw):
            raise RuntimeError("API de clima fora do ar")

        monkeypatch.setattr(ia_routes.servico_clima, "obter_clima_por_coordenadas", fake_clima_falha)

        resp = asyncio.run(chat_ia(cliente_id=cliente, pergunta="Tem previsão de chuva?",
                                   sensor_id=None, x_app_token="t", db=db))
        assert resp.resposta_estruturada["modo"] == MODO_CLIMA
        assert "indispon" in resp.resposta_texto.lower()
        assert "é só pedir" not in resp.resposta_texto.lower()
    finally:
        db.query(LeituraDB).filter(LeituraDB.cliente_id == cliente).delete()
        db.query(SensorDB).filter(SensorDB.cliente_id == cliente).delete()
        db.commit(); db.close()


def test_clima_sem_localizacao_pede_esclarecimento(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    cliente = "cli_clima_3"
    db = SessionLocal()
    try:
        # Sensor sem coordenadas -> nenhuma localização segura.
        _seed_cliente_com_coords(db, cliente, "sclima3", lat=None, lon=None)

        async def nao_deve_chamar(lat, lon, **kw):
            raise AssertionError("não deveria consultar clima sem localização")

        monkeypatch.setattr(ia_routes.servico_clima, "obter_clima_por_coordenadas", nao_deve_chamar)

        resp = asyncio.run(chat_ia(cliente_id=cliente, pergunta="Vai chover?",
                                   sensor_id=None, x_app_token="t", db=db))
        assert resp.resposta_estruturada["modo"] == MODO_ESCLARECIMENTO
    finally:
        db.query(LeituraDB).filter(LeituraDB.cliente_id == cliente).delete()
        db.query(SensorDB).filter(SensorDB.cliente_id == cliente).delete()
        db.commit(); db.close()


def test_clima_hibrido_usa_dados_e_clima(monkeypatch):
    cliente = "cli_clima_4"
    db = SessionLocal()
    try:
        _seed_cliente_com_coords(db, cliente, "sclima4")

        async def fake_clima(lat, lon, **kw):
            return _fake_clima_resposta(prob=20)

        monkeypatch.setattr(ia_routes.servico_clima, "obter_clima_por_coordenadas", fake_clima)
        captura = {}
        servico = _servico_openai(monkeypatch, _payload(), captura)
        monkeypatch.setattr(ia_routes, "ServicoOpenAI", lambda: servico)

        resp = asyncio.run(chat_ia(cliente_id=cliente, pergunta="Posso irrigar hoje ou vai chover?",
                                   sensor_id=None, x_app_token="t", db=db))
        assert "CLIMA (serviço climático real)" in captura["prompt"]
        assert "DADOS REAIS DO CLIENTE" in captura["prompt"]
        assert "clima" in resp.recursos_utilizados
        assert "dados_cliente" in resp.recursos_utilizados
        assert "clima" in resp.resposta_estruturada["origem"]
    finally:
        db.query(LeituraDB).filter(LeituraDB.cliente_id == cliente).delete()
        db.query(SensorDB).filter(SensorDB.cliente_id == cliente).delete()
        db.commit(); db.close()
