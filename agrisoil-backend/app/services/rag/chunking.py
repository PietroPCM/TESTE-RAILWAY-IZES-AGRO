"""
Quebra fiel dos textos extraídos em chunks com vínculo a documento e páginas.

Regras:
- O chunk mantém o texto fiel da fonte (não reescreve, não corrige, não resume).
- O chunk preserva páginas de origem (pagina_inicio / pagina_fim).
- O chunk não mistura documentos.
- Chunks vazios, muito curtos ou com alta proporção de caracteres inválidos
  (OCR ruim / texto corrompido) são rejeitados.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.services.rag.metadata import DocumentoMeta, base_conhecimento_dir

# Marcador de página inserido na extração: "--- PÁGINA 12 ---"
_RE_PAGINA = re.compile(r"^---\s*P[ÁA]GINA\s+(\d+)\s*---\s*$", re.IGNORECASE | re.MULTILINE)

# Alvo de tamanho do chunk (em caracteres). Mantém contexto sem estourar tokens.
TAMANHO_ALVO = 1100
TAMANHO_MAXIMO = 1800
TAMANHO_MINIMO = 180

# Proporção mínima de caracteres "legíveis" (letras/dígitos/pontuação comum)
# para aceitar o chunk. Abaixo disso, tratamos como texto corrompido/OCR ruim.
PROPORCAO_MINIMA_VALIDA = 0.62


def _separar_cabecalho(conteudo: str) -> str:
    """Remove o cabeçalho de metadados do arquivo extraído, mantendo só o corpo."""
    marcador = _RE_PAGINA.search(conteudo)
    if marcador:
        return conteudo[marcador.start():]
    # Sem marcador de página: tenta remover bloco de cabeçalho entre '---' iniciais.
    return conteudo


def _paginas_do_texto(conteudo: str) -> List[Tuple[int, str]]:
    """Extrai pares (numero_pagina, texto_da_pagina)."""
    corpo = _separar_cabecalho(conteudo)
    matches = list(_RE_PAGINA.finditer(corpo))
    if not matches:
        texto = corpo.strip()
        return [(1, texto)] if texto else []

    paginas: List[Tuple[int, str]] = []
    for idx, match in enumerate(matches):
        numero = int(match.group(1))
        inicio = match.end()
        fim = matches[idx + 1].start() if idx + 1 < len(matches) else len(corpo)
        texto = corpo[inicio:fim].strip()
        if texto:
            paginas.append((numero, texto))
    return paginas


def _proporcao_valida(texto: str) -> float:
    if not texto:
        return 0.0
    validos = 0
    total = 0
    for ch in texto:
        if ch.isspace():
            continue
        total += 1
        categoria = unicodedata.category(ch)
        # L* (letras), N* (números) e pontuação/símbolos comuns
        if categoria[0] in {"L", "N"} or ch in ".,;:%()/-+°ªº'\"!?À":
            validos += 1
    if total == 0:
        return 0.0
    return validos / total


def _texto_aproveitavel(texto: str) -> bool:
    texto = texto.strip()
    if len(texto) < TAMANHO_MINIMO:
        return False
    if _proporcao_valida(texto) < PROPORCAO_MINIMA_VALIDA:
        return False
    # Precisa ter ao menos algumas palavras "de verdade"
    palavras = re.findall(r"[A-Za-zÀ-ÿ]{3,}", texto)
    return len(palavras) >= 20


def _cortar_por_tamanho(texto: str, limite: int) -> List[str]:
    """Corta um texto longo em pedaços <= limite, preferindo fronteiras de espaço."""
    texto = texto.strip()
    if len(texto) <= limite:
        return [texto] if texto else []
    pedacos: List[str] = []
    while len(texto) > limite:
        corte = texto.rfind(" ", 0, limite)
        if corte < int(limite * 0.6):
            corte = limite
        pedacos.append(texto[:corte].strip())
        texto = texto[corte:].strip()
    if texto:
        pedacos.append(texto)
    return pedacos


def _quebrar_pagina_grande(texto: str) -> List[str]:
    """Quebra uma página muito grande em blocos por parágrafo, respeitando o alvo."""
    paragrafos = re.split(r"\n\s*\n", texto)
    blocos: List[str] = []
    atual = ""
    for paragrafo in paragrafos:
        paragrafo = paragrafo.strip()
        if not paragrafo:
            continue
        if atual and len(atual) + len(paragrafo) + 2 > TAMANHO_MAXIMO:
            blocos.append(atual.strip())
            atual = paragrafo
        else:
            atual = f"{atual}\n\n{paragrafo}" if atual else paragrafo
    if atual.strip():
        blocos.append(atual.strip())
    blocos = blocos or [texto.strip()]

    # Garante que nenhum bloco exceda o tamanho máximo (páginas sem parágrafos).
    finais: List[str] = []
    for bloco in blocos:
        if len(bloco) > TAMANHO_MAXIMO:
            finais.extend(_cortar_por_tamanho(bloco, TAMANHO_MAXIMO))
        else:
            finais.append(bloco)
    return finais


def gerar_chunks(documento: DocumentoMeta, conteudo: str) -> List[Dict]:
    """Gera chunks com metadados completos para um documento."""
    paginas = _paginas_do_texto(conteudo)
    if not paginas:
        return []

    # Agrupa páginas consecutivas até o tamanho alvo; páginas grandes viram vários blocos.
    chunks_brutos: List[Tuple[int, int, str]] = []  # (pagina_ini, pagina_fim, texto)
    buffer_texto = ""
    buffer_ini: Optional[int] = None
    buffer_fim: Optional[int] = None

    def flush():
        nonlocal buffer_texto, buffer_ini, buffer_fim
        if buffer_texto.strip() and buffer_ini is not None:
            chunks_brutos.append((buffer_ini, buffer_fim, buffer_texto.strip()))
        buffer_texto = ""
        buffer_ini = None
        buffer_fim = None

    for numero, texto in paginas:
        if len(texto) > TAMANHO_MAXIMO:
            flush()
            for bloco in _quebrar_pagina_grande(texto):
                chunks_brutos.append((numero, numero, bloco))
            continue

        if buffer_ini is None:
            buffer_ini = numero
        buffer_fim = numero
        buffer_texto = f"{buffer_texto}\n\n{texto}" if buffer_texto else texto

        if len(buffer_texto) >= TAMANHO_ALVO:
            flush()

    flush()

    chunks: List[Dict] = []
    seq = 0
    for pagina_ini, pagina_fim, texto in chunks_brutos:
        if not _texto_aproveitavel(texto):
            continue
        seq += 1
        chunk_id = f"{documento.documento_id}::p{pagina_ini}-{pagina_fim}::{seq:03d}"
        chunks.append(
            {
                "chunk_id": chunk_id,
                "documento_id": documento.documento_id,
                "titulo": documento.titulo,
                "instituicao": documento.instituicao,
                "autores": list(documento.autores),
                "ano": documento.ano,
                "url": documento.url,
                "arquivo_original": documento.arquivo_original,
                "pagina_inicio": pagina_ini,
                "pagina_fim": pagina_fim,
                "tema": list(documento.tema),
                "subtema": documento.subtema,
                "cultura": documento.cultura,
                "regiao": documento.regiao,
                "tipo_extracao": documento.tipo_extracao,
                "confiabilidade": documento.confiabilidade,
                "texto": texto,
            }
        )
    return chunks


def carregar_texto_extraido(documento: DocumentoMeta) -> Optional[str]:
    caminho = base_conhecimento_dir() / documento.caminho_extraido
    if not caminho.exists():
        return None
    return caminho.read_text(encoding="utf-8", errors="ignore")
