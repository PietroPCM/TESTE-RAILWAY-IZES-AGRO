"""
Leitura dos metadados oficiais da biblioteca documental (conhecimento-rag).

A fonte de verdade é o inventário validado em
``conhecimento-rag/fontes/inventario_documentos.csv``.

Este módulo NÃO inventa conhecimento técnico: apenas lê os metadados já
produzidos e validados, e expõe quais documentos podem entrar no índice.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# Documentos sem original validado: NUNCA podem entrar no RAG.
DOCUMENTOS_PROIBIDOS = {
    "DOC_IRRIGACAO_FAO_001",
    "DOC_SENSOR_ARTIGO_003",
}


def _repo_root() -> Path:
    # app/services/rag/metadata.py -> sobe 4 níveis até agrisoil-backend, +1 até a raiz do repo
    return Path(__file__).resolve().parents[4]


def base_conhecimento_dir() -> Path:
    """Diretório raiz da biblioteca documental.

    Pode ser sobrescrito por ``IZES_RAG_KB_DIR`` (útil em testes).
    """
    override = os.environ.get("IZES_RAG_KB_DIR")
    if override:
        return Path(override)
    return _repo_root() / "conhecimento-rag"


def inventario_path() -> Path:
    return base_conhecimento_dir() / "fontes" / "inventario_documentos.csv"


@dataclass
class DocumentoMeta:
    documento_id: str
    titulo: str
    instituicao: str
    autores: List[str]
    ano: Optional[int]
    url: str
    arquivo_original: str
    caminho_extraido: str
    tema: List[str]
    subtema: str
    cultura: str
    regiao: str
    tipo_extracao: str
    status_validacao: str
    confiabilidade: str = field(default="media")

    @property
    def valido_para_rag(self) -> bool:
        return (
            self.documento_id not in DOCUMENTOS_PROIBIDOS
            and self.status_validacao.strip().upper().startswith("VÁLID")
            and bool(self.caminho_extraido.strip())
        )


def _dedup(itens: List[str]) -> List[str]:
    vistos = []
    for item in itens:
        item = item.strip()
        if item and item not in vistos:
            vistos.append(item)
    return vistos


def _parse_ano(valor: str) -> Optional[int]:
    valor = (valor or "").strip()
    if valor.isdigit():
        return int(valor)
    return None


def _confiabilidade(tipo_extracao: str, instituicao: str) -> str:
    tipo = (tipo_extracao or "").lower()
    if "ocr" in tipo:
        return "media"
    if "camada textual" in tipo:
        return "alta"
    return "media"


def carregar_inventario(caminho: Optional[Path] = None) -> List[DocumentoMeta]:
    """Lê o inventário completo (válidos e inválidos)."""
    caminho = caminho or inventario_path()
    if not caminho.exists():
        return []

    documentos: List[DocumentoMeta] = []
    with caminho.open("r", encoding="utf-8-sig", newline="") as fh:
        leitor = csv.DictReader(fh)
        for linha in leitor:
            doc = DocumentoMeta(
                documento_id=(linha.get("documento_id") or "").strip(),
                titulo=(linha.get("titulo") or "").strip(),
                instituicao=(linha.get("instituicao") or "").strip(),
                autores=_dedup((linha.get("autores") or "").split(";")),
                ano=_parse_ano(linha.get("ano")),
                url=(linha.get("url_original") or "").strip(),
                arquivo_original=(linha.get("caminho_original") or "").strip(),
                caminho_extraido=(linha.get("caminho_extraido") or "").strip(),
                tema=_dedup((linha.get("tema") or "").split("|")),
                subtema=(linha.get("subtema") or "").strip(),
                cultura=(linha.get("cultura") or "").strip(),
                regiao=(linha.get("regiao") or "").strip(),
                tipo_extracao=(linha.get("tipo_extracao") or "").strip(),
                status_validacao=(linha.get("status_validacao") or "").strip(),
            )
            doc.confiabilidade = _confiabilidade(doc.tipo_extracao, doc.instituicao)
            documentos.append(doc)
    return documentos


def documentos_validos(caminho: Optional[Path] = None) -> Dict[str, DocumentoMeta]:
    """Mapa documento_id -> metadados, apenas para documentos válidos para RAG."""
    return {
        doc.documento_id: doc
        for doc in carregar_inventario(caminho)
        if doc.valido_para_rag
    }
