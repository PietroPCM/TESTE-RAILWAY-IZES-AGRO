"""Pacote de recuperação de conhecimento técnico (RAG local) do IZES."""

from app.services.rag.retriever import (
    RecuperadorRAG,
    ResultadoRAG,
    get_retriever,
    recuperar_conhecimento,
)

__all__ = [
    "RecuperadorRAG",
    "ResultadoRAG",
    "get_retriever",
    "recuperar_conhecimento",
]
