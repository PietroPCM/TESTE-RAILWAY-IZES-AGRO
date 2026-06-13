"""
Recuperador lexical local (BM25) sobre o índice RAG.

Características:
- Sem dependências externas, sem banco vetorial, compatível com Railway.
- Normalização de acentos, tokenização, remoção de stopwords e sinônimos agrícolas.
- Ranking BM25, filtros por cultura, remoção de duplicidade e limite de contexto.
- Nunca derruba o chamador: se o índice faltar ou a busca falhar, retorna vazio.
- Ponto de evolução futura: substituir/combinar com embeddings ou pgvector.
"""

from __future__ import annotations

import json
import logging
import math
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from app.services.rag.text_utils import expandir_sinonimos, normalizar, tokenizar

logger = logging.getLogger(__name__)

# Parâmetros BM25
_BM25_K1 = 1.5
_BM25_B = 0.75

# Limites de contexto
MAX_CHUNKS_PADRAO = 3
MAX_CHARS_CONTEXTO = 3500
SCORE_MINIMO = 1.5
# Fração do melhor score abaixo da qual um chunk é considerado fraco/incidental.
FRACAO_RELATIVA_MINIMA = 0.45
# Peso do casamento em campos de alto sinal (título, tema, subtema, cultura).
PESO_CAMPOS = 3.0
PESO_PARAMETRO = 2.5


def _default_index_path() -> Path:
    return Path(__file__).resolve().parent / "index" / "rag_index.json"


@dataclass
class ResultadoRAG:
    """Um chunk recuperado, com seu score e metadados de fonte."""

    chunk: Dict
    score: float

    @property
    def documento_id(self) -> str:
        return self.chunk.get("documento_id", "")

    def fonte(self) -> Dict:
        """Metadados da fonte para exibição (somente do que entrou no contexto)."""
        ini = self.chunk.get("pagina_inicio")
        fim = self.chunk.get("pagina_fim")
        if ini and fim and ini != fim:
            paginas = f"{ini}-{fim}"
        elif ini:
            paginas = str(ini)
        else:
            paginas = None
        return {
            "documento_id": self.chunk.get("documento_id"),
            "titulo": self.chunk.get("titulo"),
            "instituicao": self.chunk.get("instituicao"),
            "ano": self.chunk.get("ano"),
            "url": self.chunk.get("url"),
            "paginas": paginas,
        }


class RecuperadorRAG:
    """Carrega o índice e responde consultas de conhecimento técnico."""

    def __init__(self, indice: Optional[Dict] = None, caminho_indice: Optional[Path] = None):
        self._caminho = caminho_indice or _default_index_path()
        self._chunks: List[Dict] = []
        self._tokens_por_chunk: List[List[str]] = []
        self._tf_por_chunk: List[Dict[str, int]] = []
        self._df: Dict[str, int] = {}
        self._idf: Dict[str, float] = {}
        self._avg_len: float = 0.0
        self._carregado = False
        if indice is not None:
            self._construir(indice)

    # ------------------------------------------------------------------ carga
    def _carregar_se_preciso(self) -> None:
        if self._carregado:
            return
        try:
            if not self._caminho.exists():
                logger.info("Índice RAG ausente em %s; recuperação retornará vazio.", self._caminho)
                self._carregado = True
                return
            dados = json.loads(self._caminho.read_text(encoding="utf-8"))
            self._construir(dados)
        except Exception as exc:  # pragma: no cover - proteção defensiva
            logger.warning("Falha ao carregar índice RAG (%s); seguindo sem RAG.", type(exc).__name__)
            self._chunks = []
            self._carregado = True

    def _construir(self, indice: Dict) -> None:
        chunks = indice.get("chunks", []) if isinstance(indice, dict) else []
        self._chunks = chunks
        self._tokens_por_chunk = []
        self._tf_por_chunk = []
        self._campos_tokens = []  # tokens de titulo/tema/subtema/cultura (alto sinal)
        self._df = {}

        for chunk in chunks:
            tokens = tokenizar(chunk.get("texto", ""))
            self._tokens_por_chunk.append(tokens)
            tf: Dict[str, int] = {}
            for token in tokens:
                tf[token] = tf.get(token, 0) + 1
            self._tf_por_chunk.append(tf)
            for token in tf:
                self._df[token] = self._df.get(token, 0) + 1

            tema = chunk.get("tema") or []
            if isinstance(tema, str):
                tema = [tema]
            campos = " ".join([
                str(chunk.get("titulo") or ""),
                " ".join(str(t) for t in tema),
                str(chunk.get("subtema") or ""),
                str(chunk.get("cultura") or ""),
            ])
            self._campos_tokens.append(set(tokenizar(campos)))

        total = len(chunks)
        self._avg_len = (
            sum(len(t) for t in self._tokens_por_chunk) / total if total else 0.0
        )
        self._idf = {
            token: math.log(1 + (total - df + 0.5) / (df + 0.5))
            for token, df in self._df.items()
        }
        self._carregado = True

    @property
    def total_chunks(self) -> int:
        self._carregar_se_preciso()
        return len(self._chunks)

    # ------------------------------------------------------------- pontuação
    def _score_bm25(self, idx: int, termos: List[str]) -> float:
        tf = self._tf_por_chunk[idx]
        comprimento = len(self._tokens_por_chunk[idx]) or 1
        score = 0.0
        for termo in termos:
            freq = tf.get(termo)
            if not freq:
                continue
            idf = self._idf.get(termo, 0.0)
            numerador = freq * (_BM25_K1 + 1)
            denominador = freq + _BM25_K1 * (
                1 - _BM25_B + _BM25_B * comprimento / (self._avg_len or 1)
            )
            score += idf * numerador / denominador
        return score

    # -------------------------------------------------------------- consulta
    def recuperar(
        self,
        pergunta: str,
        *,
        top_k: int = MAX_CHUNKS_PADRAO,
        cultura: Optional[str] = None,
        parametros: Optional[List[str]] = None,
        max_chars: int = MAX_CHARS_CONTEXTO,
        score_minimo: float = SCORE_MINIMO,
    ) -> List[ResultadoRAG]:
        """Recupera os chunks mais relevantes. Nunca lança exceção ao chamador.

        Combina BM25 do corpo com peso em campos de alto sinal (título, tema,
        subtema, cultura) e reforço por parâmetro (pH, umidade, NPK...). Aplica
        limiar absoluto e relativo para descartar fontes apenas incidentais.
        """
        try:
            self._carregar_se_preciso()
            if not self._chunks:
                return []

            termos = expandir_sinonimos(tokenizar(pergunta))
            if not termos:
                return []

            cultura_norm = normalizar(cultura or "")
            termos_param = set()
            for p in (parametros or []):
                termos_param.update(tokenizar(p))
            termos_set = set(termos)

            candidatos: List[ResultadoRAG] = []
            for idx, chunk in enumerate(self._chunks):
                score = self._score_bm25(idx, termos)
                if score <= 0:
                    continue
                campos = self._campos_tokens[idx]
                # Alto sinal: termos da pergunta presentes em título/tema/cultura.
                acertos_campos = len(termos_set & campos)
                if acertos_campos:
                    score += PESO_CAMPOS * acertos_campos
                # Reforço quando o parâmetro pedido aparece nos campos do chunk.
                if termos_param and (termos_param & campos):
                    score += PESO_PARAMETRO * len(termos_param & campos)
                # Reforço quando a cultura combina explicitamente.
                if cultura_norm and cultura_norm in normalizar(chunk.get("cultura", "")):
                    score *= 1.25
                candidatos.append(ResultadoRAG(chunk=chunk, score=score))

            candidatos.sort(key=lambda r: r.score, reverse=True)
            if not candidatos:
                return []

            # Limiar relativo: descarta o que está muito abaixo do melhor.
            corte_relativo = candidatos[0].score * FRACAO_RELATIVA_MINIMA
            limiar = max(score_minimo, corte_relativo)

            selecionados: List[ResultadoRAG] = []
            documentos_usados: Dict[str, int] = {}
            total_chars = 0
            for resultado in candidatos:
                if resultado.score < limiar:
                    break
                doc_id = resultado.documento_id
                # Remoção de duplicidade: no máx. 2 chunks por documento.
                if documentos_usados.get(doc_id, 0) >= 2:
                    continue
                texto = resultado.chunk.get("texto", "")
                if total_chars + len(texto) > max_chars and selecionados:
                    break
                selecionados.append(resultado)
                documentos_usados[doc_id] = documentos_usados.get(doc_id, 0) + 1
                total_chars += len(texto)
                if len(selecionados) >= top_k:
                    break
            return selecionados
        except Exception as exc:  # pragma: no cover - proteção defensiva
            logger.warning("Falha na recuperação RAG (%s); seguindo sem RAG.", type(exc).__name__)
            return []


# ---------------------------------------------------------------- singleton
_lock = threading.Lock()
_instancia: Optional[RecuperadorRAG] = None


def get_retriever() -> RecuperadorRAG:
    """Retorna o recuperador global (carregado uma única vez)."""
    global _instancia
    if _instancia is None:
        with _lock:
            if _instancia is None:
                _instancia = RecuperadorRAG()
    return _instancia


def recuperar_conhecimento(
    pergunta: str,
    *,
    top_k: int = MAX_CHUNKS_PADRAO,
    cultura: Optional[str] = None,
    parametros: Optional[List[str]] = None,
) -> List[ResultadoRAG]:
    """Atalho de alto nível usado pelo serviço de IA."""
    return get_retriever().recuperar(
        pergunta, top_k=top_k, cultura=cultura, parametros=parametros
    )
