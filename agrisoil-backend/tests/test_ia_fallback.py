import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models.contratos import ContextoIA, DecisaoAlerta, SensorInfo
from app.models.database import (
    AlertaDB,
    LeituraDB,
    SensorDB,
    SeveridadeAlerta,
    StatusAlerta,
    TipoAlerta,
)
from app.services.contexto_ia import ServicoContextoIA
from app.services.openai_service import ServicoOpenAI


def test_openai_service_returns_safe_fallback_without_api_key(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    service = ServicoOpenAI()
    contexto = ContextoIA(
        cliente_id="cliente_teste",
        usuario_pergunta="Devo irrigar agora?",
        sensores_relevantes=[
            SensorInfo(
                sensor_id="sensor_001",
                nome="Sensor teste",
                propriedade="Fazenda teste",
                tipo="solo",
                localizacao={"municipio": "Teste", "estado": "TS"},
                ultima_leitura={"umidade": 22.0, "timestamp": "2026-05-31T00:00:00"},
                avaliacoes={"umidade": {"nivel": "critico", "mensagem": "Solo seco"}},
            )
        ],
        alertas_ativos=[
            DecisaoAlerta(
                tipo="umidade",
                severidade="alta",
                mensagem="Umidade baixa",
                ativa=True,
                desde=datetime.utcnow(),
            )
        ],
    )

    resposta = asyncio.run(service.analisar_contexto(contexto, "pergunta_teste"))

    assert resposta.modelo == "fallback-local"
    assert resposta.requer_validacao_humana is True
    assert "não substitui laudo agronômico" in resposta.resposta_texto
    assert "ultima_leitura" in resposta.dados_consultados
    assert resposta.tokens_usados == 0


def test_openai_prompt_uses_existing_context_fields_only(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    service = ServicoOpenAI()
    contexto = ContextoIA(
        cliente_id="cliente_teste",
        usuario_pergunta="Como está o solo?",
        sensores_relevantes=[
            SensorInfo(
                sensor_id="sensor_001",
                propriedade="Fazenda teste",
                tipo="solo",
                localizacao={"municipio": "Teste"},
            )
        ],
    )

    prompt = service._montar_prompt(contexto)

    assert "USE SOMENTE OS DADOS ABAIXO" in prompt
    assert "Não invente" in prompt
    assert "sensor_001" in prompt


def test_contexto_ia_loads_real_sensor_reading_and_alert_from_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    cliente_id = "cliente_ia_teste"
    sensor_id = "sensor_ia_teste"
    try:
        db.query(AlertaDB).filter(AlertaDB.cliente_id == cliente_id).delete()
        db.query(LeituraDB).filter(LeituraDB.cliente_id == cliente_id).delete()
        db.query(SensorDB).filter(SensorDB.cliente_id == cliente_id).delete()
        db.commit()

        sensor = SensorDB(
            sensor_id=sensor_id,
            cliente_id=cliente_id,
            nome="Sensor IA Teste",
            tipo="solo",
            ativo=True,
            propriedade="Fazenda IA",
            municipio="Cidade IA",
            estado="TS",
        )
        db.add(sensor)
        db.commit()

        leitura = LeituraDB(
            sensor_id=sensor_id,
            cliente_id=cliente_id,
            ph=5.1,
            umidade=21.0,
            temperatura=28.0,
            umidade_nivel="critico",
            umidade_mensagem="Solo seco",
            alerta_ativo=True,
            nivel_critico=True,
        )
        db.add(leitura)
        db.commit()

        alerta = AlertaDB(
            sensor_id=sensor_id,
            cliente_id=cliente_id,
            leitura_id=leitura.id,
            tipo=TipoAlerta.UMIDADE,
            severidade=SeveridadeAlerta.ALTO,
            status=StatusAlerta.ATIVO,
            titulo="Umidade baixa",
            mensagem="Umidade do solo abaixo do ideal",
        )
        db.add(alerta)
        db.commit()

        contexto = asyncio.run(
            ServicoContextoIA().montar_contexto(
                cliente_id=cliente_id,
                pergunta="Qual o risco agora?",
                sensor_id=sensor_id,
                usar_cache=False,
                db=db,
            )
        )

        assert len(contexto.sensores_relevantes) == 1
        assert contexto.sensores_relevantes[0].ultima_leitura["umidade"] == 21.0
        assert contexto.sensores_relevantes[0].avaliacoes["umidade"]["nivel"] == "critico"
        assert len(contexto.alertas_ativos) == 1
        assert contexto.alertas_ativos[0].tipo == "umidade"
    finally:
        db.close()
