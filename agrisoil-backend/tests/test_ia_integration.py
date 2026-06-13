"""
Testes de dados reais + integração da IA agro com RAG (ETAPA 3/6/7/8).

Usa SQLite temporário com os dados AgriSoil, mocks da OpenAI e o índice RAG real.
Nunca chama OpenAI real, nunca conecta em banco real.
"""

import asyncio
import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models.database import LeituraDB, SensorDB
from app.services.contexto_ia import (
    ClienteIANaoEncontrado,
    SensorIANaoEncontrado,
    ServicoContextoIA,
)
import app.services.openai_service as openai_service_module
from app.services.openai_service import (
    MODO_AGRO_COM_DADOS,
    MODO_AGRO_GERAL,
    MODO_FORA_ESCOPO,
    ServicoOpenAI,
)

CLIENTE = "agrisoil"
OUTRO_CLIENTE = "outro_cliente"

SENSORES = [
    # (sensor_id, nome, umidade, ph, n, p, k)
    ("estufa-1-canteiro-03", "Canteiro 03 (batata-doce)", 27.4, None, 82, 31, 147),
    ("estufa-1-canteiro-07", "Canteiro 07 (batata-doce)", 41.8, None, 78, 29, 139),
    ("area-soja-01", "Área Soja 01", 34.2, 5.5, 52, 22, 96),
]


def _limpar(db, cliente_id):
    db.query(LeituraDB).filter(LeituraDB.cliente_id == cliente_id).delete()
    db.query(SensorDB).filter(SensorDB.cliente_id == cliente_id).delete()
    db.commit()


def _seed_agrisoil(db, com_leituras=True):
    Base.metadata.create_all(bind=engine)
    _limpar(db, CLIENTE)
    for sensor_id, nome, umidade, ph, n, p, k in SENSORES:
        db.add(SensorDB(
            sensor_id=sensor_id, cliente_id=CLIENTE, nome=nome, tipo="solo",
            ativo=True, propriedade="AgriSoil",
        ))
    db.commit()
    if com_leituras:
        for sensor_id, nome, umidade, ph, n, p, k in SENSORES:
            db.add(LeituraDB(
                sensor_id=sensor_id, cliente_id=CLIENTE,
                umidade=umidade, ph=ph, nitrogenio=n, fosforo=p, potassio=k,
                umidade_nivel="baixo" if umidade < 30 else "ok",
                umidade_mensagem="Umidade abaixo do ideal" if umidade < 30 else "Umidade adequada",
            ))
        db.commit()


def _montar(db, pergunta, sensor_id=None, cliente_id=CLIENTE, decisao=None):
    return asyncio.run(ServicoContextoIA().montar_contexto(
        cliente_id=cliente_id, pergunta=pergunta, sensor_id=sensor_id,
        usar_cache=False, db=db, exigir_cliente=True, decisao=decisao,
    ))


# ============================================================ DADOS (26-40)
def test_cliente_com_varios_sensores():
    db = SessionLocal()
    try:
        _seed_agrisoil(db)
        ctx = _montar(db, "Como estão minhas áreas?")
        assert len(ctx.sensores_relevantes) == 3
    finally:
        _limpar(db, CLIENTE); db.close()


def test_comparacao_entre_dois_canteiros():
    db = SessionLocal()
    try:
        _seed_agrisoil(db)
        ctx = _montar(db, "Qual canteiro precisa de mais atenção?")
        umidades = {s.sensor_id: s.ultima_leitura["umidade"] for s in ctx.sensores_relevantes}
        assert umidades["estufa-1-canteiro-03"] == 27.4
        assert umidades["estufa-1-canteiro-07"] == 41.8
        # Canteiro 03 é o de menor umidade (merece mais atenção).
        assert min(umidades, key=umidades.get) == "estufa-1-canteiro-03"
    finally:
        _limpar(db, CLIENTE); db.close()


def test_sensor_pertencente_ao_cliente():
    db = SessionLocal()
    try:
        _seed_agrisoil(db)
        ctx = _montar(db, "E esse aqui?", sensor_id="estufa-1-canteiro-03")
        assert len(ctx.sensores_relevantes) == 1
        assert ctx.sensores_relevantes[0].sensor_id == "estufa-1-canteiro-03"
    finally:
        _limpar(db, CLIENTE); db.close()


def test_sensor_de_outro_cliente_nao_e_acessivel():
    db = SessionLocal()
    try:
        _seed_agrisoil(db)
        _limpar(db, OUTRO_CLIENTE)
        db.add(SensorDB(sensor_id="sensor-do-outro", cliente_id=OUTRO_CLIENTE,
                        nome="Outro", tipo="solo", ativo=True))
        db.commit()
        with pytest.raises(SensorIANaoEncontrado):
            _montar(db, "Como está esse sensor?", sensor_id="sensor-do-outro")
    finally:
        _limpar(db, CLIENTE); _limpar(db, OUTRO_CLIENTE); db.close()


def test_sensor_inexistente():
    db = SessionLocal()
    try:
        _seed_agrisoil(db)
        with pytest.raises(SensorIANaoEncontrado):
            _montar(db, "Como está?", sensor_id="nao-existe")
    finally:
        _limpar(db, CLIENTE); db.close()


def test_sensor_sem_leitura():
    db = SessionLocal()
    try:
        _seed_agrisoil(db, com_leituras=False)
        ctx = _montar(db, "Como está esse sensor?", sensor_id="estufa-1-canteiro-03")
        assert ctx.sensores_relevantes[0].ultima_leitura is None
    finally:
        _limpar(db, CLIENTE); db.close()


def test_cliente_sem_cliente_id_valido_gera_erro():
    db = SessionLocal()
    try:
        Base.metadata.create_all(bind=engine)
        _limpar(db, "cliente_inexistente_xyz")
        with pytest.raises(ClienteIANaoEncontrado):
            _montar(db, "Como estão minhas áreas?", cliente_id="cliente_inexistente_xyz")
    finally:
        db.close()


def test_consulta_area_de_soja():
    db = SessionLocal()
    try:
        _seed_agrisoil(db)
        ctx = _montar(db, "Como está minha soja?", sensor_id="area-soja-01")
        leitura = ctx.sensores_relevantes[0].ultima_leitura
        assert leitura["ph"] == 5.5
        assert leitura["umidade"] == 34.2
    finally:
        _limpar(db, CLIENTE); db.close()


def test_isolamento_entre_clientes():
    db = SessionLocal()
    try:
        _seed_agrisoil(db)
        _limpar(db, OUTRO_CLIENTE)
        db.add(SensorDB(sensor_id="sensor-do-outro", cliente_id=OUTRO_CLIENTE,
                        nome="Outro", tipo="solo", ativo=True))
        db.commit()
        ctx = _montar(db, "Como estão minhas áreas?")
        ids = {s.sensor_id for s in ctx.sensores_relevantes}
        assert "sensor-do-outro" not in ids
        assert ids == {s[0] for s in SENSORES}
    finally:
        _limpar(db, CLIENTE); _limpar(db, OUTRO_CLIENTE); db.close()


# ===================================================== INTEGRAÇÃO (61-76)
class _FakeMsg:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()


class _FakeResp:
    def __init__(self, content, tokens=120):
        self.choices = [_FakeMsg(content)]
        self.usage = type("U", (), {"total_tokens": tokens})()


def _payload_valido():
    return json.dumps({
        "resposta_texto": (
            "Situação:\nO Canteiro 03 está com 27,4% de umidade.\n\n"
            "Risco:\nUmidade mais baixa que o Canteiro 07.\n\n"
            "O que fazer agora:\n1. Conferir o sensor.\n2. Avaliar irrigação.\n3. Validar em campo.\n\n"
            "Atenção:\nNão aplique dose exata sem análise de solo ou agrônomo."
        ),
        "recomendacao": {"acao": "Acompanhar o Canteiro 03.", "motivo": "Menor umidade.",
                          "riscos_se_nao_fizer": "Estresse hídrico.", "beneficios": "Decisão com dado real."},
        "atencoes": ["Sensor não substitui laudo."],
        "proximos_passos": ["Conferir sensor.", "Avaliar irrigação."],
        "confianca_geral": 0.8,
    }, ensure_ascii=False)


def _ids_do_prompt(prompt):
    """Extrai os documento_id presentes na seção de conhecimento do prompt."""
    sec = prompt.split("CONHECIMENTO TÉCNICO RECUPERADO", 1)[-1]
    return re.findall(r'"documento_id":\s*"([^"]+)"', sec)


def _servico_com_client(monkeypatch, captura, content=None, declarar_fontes=False):
    monkeypatch.setattr(settings, "openai_api_key", "fake-key")
    servico = ServicoOpenAI()
    servico.disponivel = True
    servico.model = "modelo-teste"

    class _Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    prompt = kwargs["messages"][1]["content"]
                    captura["prompt"] = prompt
                    payload = json.loads(content or _payload_valido())
                    if declarar_fontes:
                        # O modelo declara como usados os documentos enviados.
                        payload["documento_ids_utilizados"] = _ids_do_prompt(prompt)
                    captura["documento_ids"] = payload.get("documento_ids_utilizados", [])
                    return _FakeResp(json.dumps(payload, ensure_ascii=False))

    servico.client = _Client()
    return servico


def test_agro_com_dados_usa_sensores_e_rag(monkeypatch):
    db = SessionLocal()
    try:
        _seed_agrisoil(db)
        from app.services.ia.decisao import decidir
        decisao = decidir("Qual canteiro precisa de mais atenção?", cliente_id=CLIENTE)
        ctx = _montar(db, "Qual canteiro precisa de mais atenção?", decisao=decisao)
        captura = {}
        servico = _servico_com_client(monkeypatch, captura, declarar_fontes=True)
        resp = asyncio.run(servico.analisar_contexto(ctx, "pid", decisao=decisao))
        prompt = captura["prompt"]
        # Dados reais dos canteiros entram no prompt; área de soja é excluída.
        assert "27.4" in prompt and "41.8" in prompt
        assert "area-soja-01" not in prompt
        assert "DADOS REAIS DO CLIENTE" in prompt
        assert "CONHECIMENTO TÉCNICO RECUPERADO" in prompt
        assert resp.resposta_estruturada["modo"] == MODO_AGRO_COM_DADOS
        assert resp.resposta_estruturada["origem"].startswith("openai_com_dados")
        # Só fontes realmente declaradas/validadas aparecem (subconjunto do recuperado).
        for f in resp.fontes:
            assert f["documento_id"] in captura["documento_ids"]
        # Encerramento contextual presente.
        assert "é só pedir" in resp.resposta_texto.lower()
    finally:
        _limpar(db, CLIENTE); db.close()


def test_agro_geral_usa_rag_sem_sensores(monkeypatch):
    captura = {}
    servico = _servico_com_client(monkeypatch, captura)
    from app.models.contratos import ContextoIA
    ctx = ContextoIA(cliente_id=CLIENTE, usuario_pergunta="O que é condutividade elétrica?")
    resp = asyncio.run(servico.analisar_contexto(ctx, "pid", modo=MODO_AGRO_GERAL))
    prompt = captura["prompt"]
    assert "Modo da pergunta: agro_geral" in prompt
    assert resp.dados_consultados == ["conhecimento_agro_geral"]
    assert resp.resposta_estruturada["dados_reais"] is False
    # Não há dados de sensor do cliente no prompt.
    assert "sensores_relevantes" not in prompt


def test_falha_do_recuperador_nao_derruba(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    def explode(*a, **k):
        raise RuntimeError("RAG quebrou")
    monkeypatch.setattr(openai_service_module, "recuperar_conhecimento", explode)
    from app.models.contratos import ContextoIA
    ctx = ContextoIA(cliente_id=CLIENTE, usuario_pergunta="Como funciona irrigação?")
    resp = asyncio.run(ServicoOpenAI().analisar_contexto(ctx, "pid", modo=MODO_AGRO_GERAL))
    assert resp.resposta_texto
    assert resp.fontes == []


def test_falha_da_openai_retorna_resposta_controlada(monkeypatch):
    db = SessionLocal()
    try:
        _seed_agrisoil(db)
        ctx = _montar(db, "Qual canteiro precisa de mais atenção?")
        monkeypatch.setattr(settings, "openai_api_key", "fake-key")
        servico = ServicoOpenAI()
        servico.disponivel = True

        class _Client:
            class chat:
                class completions:
                    @staticmethod
                    def create(**kwargs):
                        raise RuntimeError("OpenAI fora do ar")

        servico.client = _Client()
        resp = asyncio.run(servico.analisar_contexto(ctx, "pid", modo=MODO_AGRO_COM_DADOS))
        assert resp.modelo == "fallback-local"
        assert resp.resposta_texto
        assert resp.requer_validacao_humana is True
    finally:
        _limpar(db, CLIENTE); db.close()


def test_fontes_nao_utilizadas_nao_aparecem(monkeypatch):
    # RAG vazio -> nenhuma fonte deve aparecer.
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(openai_service_module, "recuperar_conhecimento", lambda *a, **k: [])
    from app.models.contratos import ContextoIA
    ctx = ContextoIA(cliente_id=CLIENTE, usuario_pergunta="Como funciona irrigação?")
    resp = asyncio.run(ServicoOpenAI().analisar_contexto(ctx, "pid", modo=MODO_AGRO_GERAL))
    assert resp.fontes == []
    assert resp.resposta_texto  # ainda responde


def test_resposta_geral_sem_rag_ainda_responde(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(openai_service_module, "recuperar_conhecimento", lambda *a, **k: [])
    from app.models.contratos import ContextoIA
    ctx = ContextoIA(cliente_id=CLIENTE, usuario_pergunta="O que é pH?")
    resp = asyncio.run(ServicoOpenAI().analisar_contexto(ctx, "pid", modo=MODO_AGRO_GERAL))
    assert resp.resposta_estruturada["modo"] == MODO_AGRO_GERAL
    assert resp.resposta_texto


def test_encerramento_nao_aparece_em_fora_escopo(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    from app.models.contratos import ContextoIA
    ctx = ContextoIA(cliente_id=CLIENTE, usuario_pergunta="Qual a capital da Itália?")
    resp = asyncio.run(ServicoOpenAI().analisar_contexto(ctx, "pid", modo=MODO_FORA_ESCOPO))
    assert "é só pedir" not in resp.resposta_texto.lower()


def test_esclarecimento_termina_com_pergunta(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    from app.models.contratos import ContextoIA
    from app.services.openai_service import MODO_ESCLARECIMENTO
    ctx = ContextoIA(cliente_id=CLIENTE, usuario_pergunta="Como está?")
    resp = asyncio.run(ServicoOpenAI().analisar_contexto(ctx, "pid", modo=MODO_ESCLARECIMENTO))
    assert resp.resposta_texto.strip().endswith("?")
    assert "é só pedir" not in resp.resposta_texto.lower()
    assert resp.resposta_estruturada["modo"] == MODO_ESCLARECIMENTO


def test_dados_de_outro_cliente_nunca_entram_na_resposta(monkeypatch):
    db = SessionLocal()
    try:
        _seed_agrisoil(db)
        _limpar(db, OUTRO_CLIENTE)
        db.add(SensorDB(sensor_id="sensor-secreto-outro", cliente_id=OUTRO_CLIENTE,
                        nome="Secreto", tipo="solo", ativo=True))
        db.commit()
        db.add(LeituraDB(sensor_id="sensor-secreto-outro", cliente_id=OUTRO_CLIENTE,
                         umidade=99.9, potassio=999))
        db.commit()
        ctx = _montar(db, "Como estão minhas áreas?")
        captura = {}
        servico = _servico_com_client(monkeypatch, captura)
        asyncio.run(servico.analisar_contexto(ctx, "pid", modo=MODO_AGRO_COM_DADOS))
        assert "sensor-secreto-outro" not in captura["prompt"]
        assert "99.9" not in captura["prompt"]
    finally:
        _limpar(db, CLIENTE); _limpar(db, OUTRO_CLIENTE); db.close()
