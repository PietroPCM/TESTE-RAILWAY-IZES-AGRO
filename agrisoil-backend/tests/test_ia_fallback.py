import asyncio
import os
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException
from fastapi.testclient import TestClient

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models.contratos import ContextoIA, DecisaoAlerta, RecomendacaoIA, RespostaIA, SensorInfo
from app.models.database import (
    AlertaDB,
    ClienteDB,
    LeituraDB,
    SensorDB,
    SeveridadeAlerta,
    StatusAlerta,
    TipoAlerta,
)
from app.routes.ia_routes import chat_ia
import app.services.openai_service as openai_service_module
from app.main import app
from app.services.contexto_ia import ClienteIANaoEncontrado, SensorIANaoEncontrado, ServicoContextoIA
from app.services.openai_service import (
    MODO_AGRO_COM_DADOS,
    MODO_AGRO_GERAL,
    MODO_FORA_ESCOPO,
    RESPOSTA_FORA_ESCOPO,
    ServicoOpenAI,
    classificar_escopo_pergunta,
)


client = TestClient(app)


def test_openai_service_returns_safe_fallback_without_api_key(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    service = ServicoOpenAI()
    contexto = ContextoIA(
        cliente_id="cliente_teste",
        usuario_pergunta="Com base nesse sensor, devo irrigar agora?",
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
    assert "Atenção:" in resposta.resposta_texto
    assert "Não aplique dose exata" in resposta.resposta_texto
    assert "ultima_leitura" in resposta.dados_consultados
    assert resposta.tokens_usados == 0
    assert len([linha for linha in resposta.resposta_texto.splitlines() if linha.strip()]) <= 8


def test_openai_prompt_uses_existing_context_fields_only(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    service = ServicoOpenAI()
    contexto = ContextoIA(
        cliente_id="cliente_teste",
        usuario_pergunta="Com base nesse sensor, como está o solo?",
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

    assert "RESPONDA SOMENTE COM JSON VÁLIDO" in prompt
    assert "Não invente" in prompt
    assert "sensor_001" in prompt


def test_classifica_perguntas_em_tres_modos():
    assert classificar_escopo_pergunta("Qual capital da Itália?") == MODO_FORA_ESCOPO
    assert classificar_escopo_pergunta("O que é milho?") == MODO_AGRO_GERAL
    assert classificar_escopo_pergunta("Como plantar soja?") == MODO_AGRO_GERAL
    assert classificar_escopo_pergunta("Como plantar milho?") == MODO_AGRO_GERAL
    assert classificar_escopo_pergunta("Como funciona reprodução de vaca?") == MODO_AGRO_GERAL
    assert classificar_escopo_pergunta("O que fazer com potássio baixo?") == MODO_AGRO_GERAL
    assert classificar_escopo_pergunta("O que fazer com esse potássio baixo?") == MODO_AGRO_COM_DADOS
    assert classificar_escopo_pergunta("Qual o principal risco desse sensor agora?") == MODO_AGRO_COM_DADOS


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


def test_pergunta_fora_de_escopo_nao_chama_openai_e_nao_inventa_dados(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "fake-key")
    service = ServicoOpenAI()
    service.disponivel = True

    class ClienteQueFalha:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    raise AssertionError("OpenAI não deveria ser chamada para pergunta fora de escopo")

    service.client = ClienteQueFalha()
    contexto = ContextoIA(
        cliente_id="cliente_teste",
        usuario_pergunta="Qual capital da Itália?",
        sensores_relevantes=[
            SensorInfo(
                sensor_id="sensor_001",
                nome="Sensor teste",
                propriedade="Propriedade teste",
                tipo="solo",
                localizacao={},
                ultima_leitura={"umidade": 22.0},
            )
        ],
    )

    resposta = asyncio.run(service.analisar_contexto(contexto, "pergunta_fora_escopo"))

    assert resposta.resposta_texto == RESPOSTA_FORA_ESCOPO
    assert resposta.resposta_estruturada["modo"] == "fora_escopo"
    assert "Itália" not in resposta.resposta_texto
    assert resposta.modelo == "sem-openai"


def test_pergunta_agro_geral_chama_openai_sem_usar_sensor(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "fake-key")
    service = ServicoOpenAI()
    service.disponivel = True
    service.model = "modelo-teste"

    payload = {
        "resposta_texto": (
            "Situação: Para plantar soja, prepare o solo e escolha boa semente.\n\n"
            "Risco: Sem análise de solo, a adubação pode errar.\n\n"
            "O que fazer agora:\n1. Fazer análise de solo.\n2. Plantar na época certa.\n3. Monitorar pragas.\n\n"
            "Atenção: Não aplique dose exata sem análise de solo ou agrônomo."
        ),
        "recomendacao": {
            "acao": "Planejar o plantio com análise de solo.",
            "motivo": "Soja precisa de solo corrigido e boa semente.",
            "riscos_se_nao_fizer": "Pode perder produtividade.",
            "beneficios": "Melhora o início da lavoura.",
        },
        "atencoes": ["Não inventar dados do cliente."],
        "proximos_passos": ["Fazer análise de solo.", "Escolher semente.", "Monitorar pragas."],
        "confianca_geral": 0.78,
    }

    class RespostaFake:
        choices = [type("Choice", (), {"message": type("Message", (), {"content": json_dumps(payload)})()})()]
        usage = type("Usage", (), {"total_tokens": 111})()

    class ClienteFake:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    assert kwargs["response_format"] == {"type": "json_object"}
                    prompt = kwargs["messages"][1]["content"]
                    assert "Modo da pergunta: agro_geral" in prompt
                    assert "sensor_critico" not in prompt
                    assert "potassio" not in prompt.lower()
                    assert "nitrogenio" not in prompt.lower()
                    return RespostaFake()

    service.client = ClienteFake()
    contexto = ContextoIA(
        cliente_id="cliente_teste",
        sensor_id="sensor_critico",
        usuario_pergunta="Como plantar soja?",
        sensores_relevantes=[
            SensorInfo(
                sensor_id="sensor_critico",
                nome="Sensor crítico",
                propriedade="Fazenda não deve aparecer",
                tipo="solo",
                localizacao={},
                ultima_leitura={"potassio": 5.0, "nitrogenio": 3.0},
                avaliacoes={"potassio": {"nivel": "critico", "mensagem": "Potássio baixo"}},
            )
        ],
    )

    resposta = asyncio.run(service.analisar_contexto(contexto, "pergunta_milho"))

    assert resposta.resposta_estruturada["modo"] == MODO_AGRO_GERAL
    assert resposta.resposta_estruturada["origem"] == "openai"
    assert resposta.dados_consultados == ["conhecimento_agro_geral"]
    assert resposta.sensor_id is None
    assert resposta.tokens_usados == 111
    assert "soja" in resposta.resposta_texto.lower()
    assert "fazenda" not in resposta.resposta_texto.lower()
    assert "sensor_" not in resposta.resposta_texto.lower()
    assert "potássio" not in resposta.resposta_texto.lower()
    assert "nitrogênio" not in resposta.resposta_texto.lower()
    assert len(resposta.proximos_passos) <= 3


def test_pergunta_agro_geral_sem_openai_tem_fallback_util(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    service = ServicoOpenAI()
    contexto = ContextoIA(
        cliente_id="cliente_teste",
        usuario_pergunta="Como plantar milho?",
        sensores_relevantes=[],
    )

    resposta = asyncio.run(service.analisar_contexto(contexto, "pergunta_milho_fallback"))

    assert resposta.resposta_estruturada["modo"] == MODO_AGRO_GERAL
    assert resposta.dados_consultados == ["conhecimento_agro_geral"]
    assert resposta.modelo == "fallback-local"
    assert "sensor" not in resposta.dados_consultados
    assert len(resposta.proximos_passos) <= 3


def test_pergunta_pecuaria_agro_geral_chama_openai(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "fake-key")
    service = ServicoOpenAI()
    service.disponivel = True
    service.model = "modelo-teste"

    payload = {
        "resposta_texto": (
            "Situação: A reprodução de vaca depende de cio, nutrição e sanidade.\n\n"
            "Risco: Se o cio passar sem manejo, a prenhez atrasa.\n\n"
            "O que fazer agora:\n1. Observar cio.\n2. Avaliar escore corporal.\n3. Chamar veterinário.\n\n"
            "Atenção: Não aplique dose exata sem análise de solo ou agrônomo."
        ),
        "recomendacao": {
            "acao": "Organizar manejo reprodutivo com apoio técnico.",
            "motivo": "Nutrição e cio bem acompanhados melhoram a prenhez.",
            "riscos_se_nao_fizer": "Pode atrasar a reprodução do rebanho.",
            "beneficios": "Melhora o planejamento do rebanho.",
        },
        "atencoes": ["Orientação geral."],
        "proximos_passos": ["Observar cio.", "Avaliar escore corporal.", "Consultar veterinário."],
        "confianca_geral": 0.76,
    }

    class RespostaFake:
        choices = [type("Choice", (), {"message": type("Message", (), {"content": json_dumps(payload)})()})()]
        usage = type("Usage", (), {"total_tokens": 90})()

    class ClienteFake:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    assert "Modo da pergunta: agro_geral" in kwargs["messages"][1]["content"]
                    return RespostaFake()

    service.client = ClienteFake()
    contexto = ContextoIA(
        cliente_id="cliente_teste",
        usuario_pergunta="Como funciona reprodução de vaca?",
    )

    resposta = asyncio.run(service.analisar_contexto(contexto, "pergunta_vaca"))

    assert resposta.resposta_estruturada["modo"] == MODO_AGRO_GERAL
    assert resposta.dados_consultados == ["conhecimento_agro_geral"]
    assert "vaca" in resposta.resposta_texto.lower()


def test_rota_chat_fora_escopo_nao_chama_openai_nem_banco(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "fake-key")

    resposta = asyncio.run(
        chat_ia(
            cliente_id="cliente_qualquer",
            pergunta="Qual capital da Itália?",
            sensor_id=None,
            x_app_token="token_teste",
            db=None,
        )
    )

    assert resposta.resposta_texto == RESPOSTA_FORA_ESCOPO
    assert resposta.resposta_estruturada["modo"] == MODO_FORA_ESCOPO
    assert resposta.modelo == "sem-openai"
    assert resposta.tokens_usados == 0


def test_rota_chat_agro_geral_nao_exige_cliente_ou_sensor(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        resposta = asyncio.run(
            chat_ia(
                cliente_id="cliente_sem_cadastro_agro_geral",
                pergunta="Como plantar milho?",
                sensor_id=None,
                x_app_token="token_teste",
                db=db,
            )
        )

        assert resposta.resposta_estruturada["modo"] == MODO_AGRO_GERAL
        assert resposta.modelo == "fallback-local"
        assert resposta.dados_consultados == ["conhecimento_agro_geral"]
        assert resposta.tokens_usados == 0
    finally:
        db.close()


def test_rota_chat_agro_geral_com_sensor_id_nao_monta_contexto(monkeypatch):
    class ServicoFake:
        async def analisar_contexto(self, contexto, pergunta_id):
            assert contexto.sensor_id is None
            assert contexto.sensores_relevantes == []
            assert contexto.alertas_ativos == []
            return RespostaFakeAgroGeral(contexto, pergunta_id)

    monkeypatch.setattr(openai_service_module, "ServicoOpenAI", ServicoFake)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    cliente_id = "cliente_rota_agro_geral_sensor"
    sensor_id = "sensor_rota_nao_usar"
    try:
        db.query(LeituraDB).filter(LeituraDB.cliente_id == cliente_id).delete()
        db.query(SensorDB).filter(SensorDB.cliente_id == cliente_id).delete()
        db.commit()
        db.add(SensorDB(
            sensor_id=sensor_id,
            cliente_id=cliente_id,
            nome="Sensor não deve ser usado",
            tipo="solo",
            ativo=True,
            propriedade="Fazenda não deve aparecer",
        ))
        db.commit()
        db.add(LeituraDB(
            sensor_id=sensor_id,
            cliente_id=cliente_id,
            ph=4.8,
            potassio=5.0,
            nitrogenio=2.0,
            potassio_nivel="critico",
            nitrogenio_nivel="baixo",
        ))
        db.commit()

        resposta = asyncio.run(
            chat_ia(
                cliente_id=cliente_id,
                pergunta="Como plantar soja?",
                sensor_id=sensor_id,
                x_app_token="token_teste",
                db=db,
            )
        )

        assert resposta.resposta_estruturada["modo"] == MODO_AGRO_GERAL
        assert resposta.dados_consultados == ["conhecimento_agro_geral"]
        assert resposta.sensor_id is None
        assert "potássio" not in resposta.resposta_texto.lower()
        assert "nitrogênio" not in resposta.resposta_texto.lower()
    finally:
        db.close()


def test_rota_chat_com_dados_exige_cliente_real(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    cliente_id = "cliente_rota_inexistente_ia"
    try:
        db.query(AlertaDB).filter(AlertaDB.cliente_id == cliente_id).delete()
        db.query(LeituraDB).filter(LeituraDB.cliente_id == cliente_id).delete()
        db.query(SensorDB).filter(SensorDB.cliente_id == cliente_id).delete()
        db.query(ClienteDB).filter(ClienteDB.cliente_id == cliente_id).delete()
        db.commit()

        try:
            asyncio.run(
                chat_ia(
                    cliente_id=cliente_id,
                    pergunta="Qual o principal risco desse sensor agora?",
                    sensor_id=None,
                    x_app_token="token_teste",
                    db=db,
                )
            )
            assert False, "Cliente inexistente deveria retornar HTTP 404"
        except HTTPException as exc:
            assert exc.status_code == 404
            assert exc.detail == "Cliente não encontrado."
    finally:
        db.close()


def test_contexto_ia_cliente_inexistente_retorna_erro_claro():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    cliente_id = "cliente_inexistente_ia"
    try:
        db.query(AlertaDB).filter(AlertaDB.cliente_id == cliente_id).delete()
        db.query(LeituraDB).filter(LeituraDB.cliente_id == cliente_id).delete()
        db.query(SensorDB).filter(SensorDB.cliente_id == cliente_id).delete()
        db.query(ClienteDB).filter(ClienteDB.cliente_id == cliente_id).delete()
        db.commit()

        try:
            asyncio.run(
                ServicoContextoIA().montar_contexto(
                    cliente_id=cliente_id,
                    pergunta="Como está o solo?",
                    usar_cache=False,
                    db=db,
                )
            )
            assert False, "Cliente inexistente deveria gerar erro"
        except ClienteIANaoEncontrado as exc:
            assert "Cliente não encontrado" in str(exc)
    finally:
        db.close()


def test_contexto_ia_sensor_inexistente_retorna_erro_claro():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    cliente_id = "cliente_sensor_inexistente_ia"
    try:
        db.query(ClienteDB).filter(ClienteDB.cliente_id == cliente_id).delete()
        db.query(SensorDB).filter(SensorDB.cliente_id == cliente_id).delete()
        db.commit()
        db.add(ClienteDB(
            cliente_id=cliente_id,
            nome="Cliente IA",
            email="cliente-sensor-inexistente@example.test",
            responsavel_nome="Responsavel IA",
            responsavel_email="resp-sensor-inexistente@example.test",
            ativo=True,
        ))
        db.commit()

        try:
            asyncio.run(
                ServicoContextoIA().montar_contexto(
                    cliente_id=cliente_id,
                    pergunta="Como está o solo?",
                    sensor_id="sensor_nao_existe",
                    usar_cache=False,
                    db=db,
                )
            )
            assert False, "Sensor inexistente deveria gerar erro"
        except SensorIANaoEncontrado as exc:
            assert "Sensor não encontrado" in str(exc)
    finally:
        db.close()


def test_sensor_real_sem_leitura_retorna_dados_insuficientes(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    service = ServicoOpenAI()
    contexto = ContextoIA(
        cliente_id="cliente_teste",
        usuario_pergunta="Qual o principal risco desse sensor agora?",
        sensores_relevantes=[
            SensorInfo(
                sensor_id="sensor_sem_leitura",
                nome="Sensor sem leitura",
                propriedade="Propriedade teste",
                tipo="solo",
                localizacao={},
            )
        ],
    )

    resposta = asyncio.run(service.analisar_contexto(contexto, "pergunta_sem_dados"))

    assert resposta.resposta_estruturada["modo"] == MODO_AGRO_COM_DADOS
    assert "não tenho leitura real" in resposta.resposta_texto.lower()
    assert resposta.modelo == "sem-openai"


def test_openai_resposta_estruturada_limpa_com_cliente_real_simulado(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    service = ServicoOpenAI()
    service.disponivel = True
    service.model = "modelo-teste"

    payload = {
        "resposta_texto": (
            "Situação:\nUmidade baixa na última leitura.\n\n"
            "Risco:\nPode faltar água no solo.\n\n"
            "O que fazer agora:\n1. Conferir o dashboard.\n2. Verificar o sensor em campo.\n3. Registrar nova leitura.\n\n"
            "Atenção:\nNão aplique dose exata sem análise de solo ou agrônomo."
        ),
        "recomendacao": {
            "acao": "Conferir leitura e validar em campo.",
            "motivo": "Há leitura real com umidade baixa.",
            "riscos_se_nao_fizer": "O solo pode seguir seco.",
            "beneficios": "Ajuda a decidir com dado real.",
        },
        "atencoes": ["Não substitui laudo agronômico.", "Não aplicar dose exata."],
        "proximos_passos": ["Conferir dashboard.", "Verificar sensor.", "Registrar nova leitura."],
        "confianca_geral": 0.82,
    }

    class RespostaFake:
        choices = [type("Choice", (), {"message": type("Message", (), {"content": json_dumps(payload)})()})()]
        usage = type("Usage", (), {"total_tokens": 123})()

    class ClienteFake:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    assert kwargs["response_format"] == {"type": "json_object"}
                    return RespostaFake()

    service.client = ClienteFake()
    contexto = ContextoIA(
        cliente_id="cliente_teste",
        usuario_pergunta="Qual o principal risco desse sensor agora?",
        sensores_relevantes=[
            SensorInfo(
                sensor_id="sensor_001",
                nome="Sensor teste",
                propriedade="Propriedade teste",
                tipo="solo",
                localizacao={},
                ultima_leitura={"umidade": 22.0},
                avaliacoes={"umidade": {"nivel": "critico", "mensagem": "Solo seco"}},
            )
        ],
    )

    resposta = asyncio.run(service.analisar_contexto(contexto, "pergunta_openai"))

    assert resposta.modelo == "modelo-teste"
    assert resposta.tokens_usados == 123
    assert resposta.resposta_estruturada["modo"] == MODO_AGRO_COM_DADOS
    assert resposta.resposta_estruturada["origem"] == "openai"
    assert resposta.recomendacao.acao == "Conferir leitura e validar em campo."
    assert len(resposta.atencoes) <= 3
    assert len(resposta.proximos_passos) <= 3
    assert len([linha for linha in resposta.resposta_texto.splitlines() if linha.strip()]) <= 8


def test_openai_json_invalido_usa_fallback_seguro(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    service = ServicoOpenAI()
    contexto = ContextoIA(
        cliente_id="cliente_teste",
        usuario_pergunta="Qual o risco no solo agora?",
        sensores_relevantes=[
            SensorInfo(
                sensor_id="sensor_001",
                nome="Sensor teste",
                propriedade="Propriedade teste",
                tipo="solo",
                localizacao={},
                ultima_leitura={"umidade": 22.0},
            )
        ],
    )

    resposta = service._resposta_openai_estruturada(
        contexto=contexto,
        pergunta_id="pergunta_json_invalido",
        resposta_texto="resposta sem json",
        tokens_usados=50,
    )

    assert resposta.modelo == "fallback-local"
    assert resposta.tokens_usados == 0
    assert resposta.resposta_estruturada["modo"] == "fallback_local"
    assert resposta.resposta_estruturada["origem"] == "fallback_local"


class RespostaFakeAgroGeral(RespostaIA):
    def __init__(self, contexto, pergunta_id):
        super().__init__(
            pergunta_id=pergunta_id,
            cliente_id=contexto.cliente_id,
            sensor_id=None,
            resposta_texto=(
                "Situação: A soja precisa de solo bem preparado e semente adequada.\n\n"
                "Risco: Sem planejamento, o plantio pode perder produtividade.\n\n"
                "O que fazer agora:\n1. Fazer análise de solo.\n2. Escolher cultivar adaptada.\n3. Monitorar pragas.\n\n"
                "Atenção: Não aplique dose exata sem análise de solo ou agrônomo."
            ),
            resposta_estruturada={
                "modo": MODO_AGRO_GERAL,
                "origem": "openai",
                "dados_reais": False,
            },
            recomendacao=RecomendacaoIA(
                acao="Planejar o plantio com análise de solo.",
                confianca=0.8,
                motivo="A pergunta é geral e não pediu sensor.",
                riscos_se_nao_fizer="Pode reduzir produtividade.",
                beneficios="Melhora o início da lavoura.",
            ),
            dados_consultados=["conhecimento_agro_geral"],
            atencoes=["Não substitui laudo agronômico."],
            proximos_passos=["Fazer análise de solo.", "Escolher cultivar.", "Monitorar pragas."],
            confianca_geral=0.8,
            requer_validacao_humana=True,
            modelo="modelo-teste",
            tokens_usados=80,
            tempo_resposta_segundos=0,
        )


def json_dumps(payload):
    import json

    return json.dumps(payload, ensure_ascii=False)


def test_analisar_imagem_retorna_400_quando_arquivo_nao_e_imagem(monkeypatch):
    monkeypatch.setattr(settings, "app_internal_token", "app_teste_local")

    response = client.post(
        "/api/ia/analisar-imagem",
        headers={"X-App-Token": "app_teste_local"},
        files={"imagem": ("arquivo.txt", BytesIO(b"texto puro"), "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "O arquivo enviado deve ser uma imagem válida."


def test_analisar_imagem_valida_retorna_campo_resposta(monkeypatch):
    monkeypatch.setattr(settings, "app_internal_token", "app_teste_local")

    async def analisar_imagem_fake(self, image_bytes, mime_type):
        assert mime_type == "image/png"
        assert image_bytes.startswith(b"\x89PNG")
        return "Imagem com folha verde sobre fundo claro."

    monkeypatch.setattr(ServicoOpenAI, "analisar_imagem", analisar_imagem_fake)

    response = client.post(
        "/api/ia/analisar-imagem",
        headers={"X-App-Token": "app_teste_local"},
        files={"imagem": ("folha.png", BytesIO(b"\x89PNG\r\n\x1a\nconteudo"), "image/png")},
    )

    assert response.status_code == 200
    assert response.json() == {"resposta": "Imagem com folha verde sobre fundo claro."}


def test_analisar_imagem_sem_openai_api_key_retorna_erro_claro(monkeypatch):
    monkeypatch.setattr(settings, "app_internal_token", "app_teste_local")
    monkeypatch.setattr(settings, "openai_api_key", "")

    response = client.post(
        "/api/ia/analisar-imagem",
        headers={"X-App-Token": "app_teste_local"},
        files={"imagem": ("folha.png", BytesIO(b"\x89PNG\r\n\x1a\nconteudo"), "image/png")},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "OPENAI_API_KEY não configurada no backend."
