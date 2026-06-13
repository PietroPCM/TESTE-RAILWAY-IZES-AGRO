"""
Testes do recuperador RAG (ETAPA 4/5/8).

Cobrem: recuperação por tema, sinônimos/linguagem informal, exclusão de
documentos inválidos, fidelidade de fontes/páginas, limite de contexto,
remoção de duplicidade, rejeição de texto corrompido e metadados obrigatórios.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("APP_ENV", "test")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.services.rag.build_index import _chunk_valido, construir_indice
from app.services.rag.chunking import _texto_aproveitavel, gerar_chunks
from app.services.rag.metadata import (
    DOCUMENTOS_PROIBIDOS,
    DocumentoMeta,
    documentos_validos,
)
from app.services.rag.retriever import RecuperadorRAG, get_retriever


@pytest.fixture(scope="module")
def retriever():
    return get_retriever()


# ----------------------------------------------------------- recuperação
@pytest.mark.parametrize(
    "pergunta",
    [
        "calibração de sensor",
        "umidade do solo",
        "irrigação",
        "condutividade elétrica",
        "NPK",
        "batata-doce",
        "soja",
        "milho",
    ],
)
def test_recupera_conteudo_por_tema(retriever, pergunta):
    resultados = retriever.recuperar(pergunta, top_k=3)
    assert resultados, f"esperava conteúdo para {pergunta!r}"
    for r in resultados:
        assert r.chunk["documento_id"] not in DOCUMENTOS_PROIBIDOS
        assert r.chunk["texto"].strip()


@pytest.mark.parametrize(
    "pergunta_informal",
    [
        "canteiro seco",
        "terra ácida",
        "sensor está errado",
        "precisa molhar?",
        "sensor barato é confiável?",
        "nutriente baixo",
    ],
)
def test_busca_informal_e_sinonimos(retriever, pergunta_informal):
    # Busca informal/sinônimo deve achar algum conteúdo (não busca exata).
    assert retriever.recuperar(pergunta_informal, top_k=3)


def test_pergunta_sem_resultado_relevante_retorna_vazio(retriever):
    assert retriever.recuperar("videogame console xbox campeonato", top_k=3) == []


# -------------------------------------------------------- índice e fontes
def test_documentos_invalidos_nao_entram_no_indice():
    indice = construir_indice()
    ids = {c["documento_id"] for c in indice["chunks"]}
    assert "DOC_IRRIGACAO_FAO_001" not in ids
    assert "DOC_SENSOR_ARTIGO_003" not in ids
    assert ids, "índice não deveria estar vazio"


def test_fonte_corresponde_ao_chunk(retriever):
    resultados = retriever.recuperar("calibração de sensor de umidade", top_k=2)
    assert resultados
    r = resultados[0]
    fonte = r.fonte()
    assert fonte["documento_id"] == r.chunk["documento_id"]
    assert fonte["titulo"] == r.chunk["titulo"]
    assert fonte["instituicao"] == r.chunk["instituicao"]


def test_paginas_correspondem_ao_chunk(retriever):
    resultados = retriever.recuperar("condutividade elétrica do solo", top_k=3)
    assert resultados
    for r in resultados:
        ini, fim = r.chunk["pagina_inicio"], r.chunk["pagina_fim"]
        assert isinstance(ini, int) and isinstance(fim, int)
        assert ini <= fim
        paginas = r.fonte()["paginas"]
        if ini == fim:
            assert paginas == str(ini)
        else:
            assert paginas == f"{ini}-{fim}"


def test_limite_de_contexto(retriever):
    resultados = retriever.recuperar("solo umidade irrigação sensor", top_k=3, max_chars=1200)
    assert len(resultados) <= 3
    total = sum(len(r.chunk["texto"]) for r in resultados)
    # Permite estourar no primeiro chunk, mas não acumular muito além do limite.
    assert total <= 1200 + 1800


def test_remocao_de_duplicidade_por_documento(retriever):
    resultados = retriever.recuperar("calibração sensor umidade solo", top_k=3)
    docs = [r.chunk["documento_id"] for r in resultados]
    for doc in set(docs):
        assert docs.count(doc) <= 2


def test_indice_carregado_tem_chunks(retriever):
    assert retriever.total_chunks > 0


# --------------------------------------------------------- qualidade/meta
def test_texto_corrompido_e_rejeitado():
    assert _texto_aproveitavel("@#@#@ %%% \x00\x01 ???? ▯▯▯▯ ::::") is False
    assert _texto_aproveitavel("abc") is False  # curto demais


def test_chunk_sem_metadado_obrigatorio_e_rejeitado():
    chunk_incompleto = {
        "chunk_id": "X::p1-1::001",
        "documento_id": "X",
        "titulo": "",  # faltando
        "instituicao": "Embrapa",
        "ano": 2024,
        "pagina_inicio": 1,
        "pagina_fim": 1,
        "tema": ["Solo"],
        "tipo_extracao": "OCR",
        "confiabilidade": "media",
        "texto": "conteúdo qualquer",
    }
    assert _chunk_valido(chunk_incompleto) is False


def test_documento_proibido_nao_gera_chunk_valido():
    chunk = {
        "chunk_id": "DOC_IRRIGACAO_FAO_001::p1-1::001",
        "documento_id": "DOC_IRRIGACAO_FAO_001",
        "titulo": "t", "instituicao": "FAO", "ano": 1998,
        "pagina_inicio": 1, "pagina_fim": 1, "tema": ["Irrigação"],
        "tipo_extracao": "OCR", "confiabilidade": "media", "texto": "x" * 300,
    }
    assert _chunk_valido(chunk) is False


def test_chunk_preserva_metadados_de_fonte():
    docs = documentos_validos()
    assert docs
    doc = next(iter(docs.values()))
    conteudo = "--- PÁGINA 1 ---\n" + ("A umidade do solo é importante para a irrigação. " * 30)
    chunks = gerar_chunks(doc, conteudo)
    assert chunks
    c = chunks[0]
    for campo in (
        "chunk_id", "documento_id", "titulo", "instituicao", "autores", "ano",
        "url", "arquivo_original", "pagina_inicio", "pagina_fim", "tema",
        "subtema", "cultura", "regiao", "tipo_extracao", "confiabilidade", "texto",
    ):
        assert campo in c
    assert c["documento_id"] == doc.documento_id
    assert c["pagina_inicio"] == 1


def test_documento_pendente_sem_texto_extraido_e_ignorado():
    # Documento válido em metadados, mas sem caminho_extraido -> não é válido p/ RAG.
    doc = DocumentoMeta(
        documento_id="DOC_PENDENTE",
        titulo="Pendente", instituicao="Embrapa", autores=[], ano=2020,
        url="http://x", arquivo_original="originais/x.pdf", caminho_extraido="",
        tema=["Solo"], subtema="", cultura="", regiao="Brasil",
        tipo_extracao="OCR", status_validacao="VÁLIDO",
    )
    assert doc.valido_para_rag is False


def test_indice_em_arquivo_inexistente_nao_quebra(tmp_path):
    r = RecuperadorRAG(caminho_indice=tmp_path / "nao_existe.json")
    assert r.recuperar("umidade do solo") == []
    assert r.total_chunks == 0
