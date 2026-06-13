"""
Construção do índice RAG a partir dos textos extraídos validados.

Uso:
    python -m app.services.rag.build_index

Gera ``app/services/rag/index/rag_index.json`` com os chunks e seus metadados.
Não acessa rede, banco ou produção. Não baixa PDFs. Não reextrai documentos.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from app.services.rag.chunking import carregar_texto_extraido, gerar_chunks
from app.services.rag.metadata import (
    DOCUMENTOS_PROIBIDOS,
    carregar_inventario,
    documentos_validos,
)

# Campos obrigatórios para um chunk entrar no índice.
CAMPOS_OBRIGATORIOS = (
    "chunk_id",
    "documento_id",
    "titulo",
    "instituicao",
    "ano",
    "pagina_inicio",
    "pagina_fim",
    "tema",
    "tipo_extracao",
    "confiabilidade",
    "texto",
)


def index_path() -> Path:
    return Path(__file__).resolve().parent / "index" / "rag_index.json"


def _chunk_valido(chunk: Dict) -> bool:
    for campo in CAMPOS_OBRIGATORIOS:
        valor = chunk.get(campo)
        if valor is None or (isinstance(valor, (str, list)) and not valor):
            return False
    if chunk["documento_id"] in DOCUMENTOS_PROIBIDOS:
        return False
    return True


def construir_indice() -> Dict:
    docs = documentos_validos()
    chunks: List[Dict] = []
    relatorio_docs: List[Dict] = []

    for documento_id, documento in sorted(docs.items()):
        conteudo = carregar_texto_extraido(documento)
        if not conteudo:
            relatorio_docs.append(
                {"documento_id": documento_id, "chunks": 0, "status": "sem_texto_extraido"}
            )
            continue

        gerados = gerar_chunks(documento, conteudo)
        validos = [c for c in gerados if _chunk_valido(c)]
        chunks.extend(validos)
        relatorio_docs.append(
            {
                "documento_id": documento_id,
                "chunks": len(validos),
                "rejeitados": len(gerados) - len(validos),
                "status": "ok" if validos else "sem_chunks_validos",
            }
        )

    inventario = carregar_inventario()
    indice = {
        "schema_version": 1,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "total_documentos_inventario": len(inventario),
        "total_documentos_indexados": sum(1 for r in relatorio_docs if r["chunks"] > 0),
        "documentos_proibidos": sorted(DOCUMENTOS_PROIBIDOS),
        "total_chunks": len(chunks),
        "relatorio_documentos": relatorio_docs,
        "chunks": chunks,
    }
    return indice


def salvar_indice(indice: Dict, caminho: Path | None = None) -> Path:
    caminho = caminho or index_path()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(indice, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return caminho


def main() -> None:
    indice = construir_indice()
    caminho = salvar_indice(indice)
    print(f"Índice RAG gerado em: {caminho}")
    print(f"Documentos indexados: {indice['total_documentos_indexados']}")
    print(f"Total de chunks: {indice['total_chunks']}")
    print("Documentos ignorados (proibidos):", ", ".join(indice["documentos_proibidos"]))
    for rel in indice["relatorio_documentos"]:
        if rel["chunks"] == 0:
            print(f"  [ATENÇÃO] {rel['documento_id']}: {rel['status']}")


if __name__ == "__main__":
    main()
