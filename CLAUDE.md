# CLAUDE.md — IZES-AGRO (ambiente de desenvolvimento)

Resumo de arquitetura e regras de segurança para trabalho assistido por IA.

## Arquitetura
- **Backend FastAPI**: `agrisoil-backend/` (app em `agrisoil-backend/app/`).
- **IA agro (chat)**: `app/routes/ia_routes.py` → `POST /api/ia/chat`.
  - Classificação de intenção: `app/services/intent_classifier.py`.
  - Geração/integração OpenAI + fallback: `app/services/openai_service.py`.
  - Montagem do contexto com dados reais: `app/services/contexto_ia.py`.
- **RAG (conhecimento técnico)**: `app/services/rag/`
  - `metadata.py` (inventário), `chunking.py`, `build_index.py`, `retriever.py` (BM25).
  - Índice gerado: `app/services/rag/index/rag_index.json`.
- **Biblioteca documental**: `conhecimento-rag/` (PDFs originais + textos extraídos + validação).
  - Detalhes do fluxo de IA/RAG: `docs/IA_RAG.md`.

## Comandos seguros (rodar em `agrisoil-backend/`)
- Testes da IA/RAG: `python -m pytest tests/test_ia_intent.py tests/test_rag.py tests/test_ia_integration.py -q`
- Suíte completa: `python -m pytest tests/ -q`
- Reconstruir índice RAG: `python -m app.services.rag.build_index`
- Compilação: `python -m compileall -q app`

## Regras absolutas
- **Não tocar em produção.** Repositório de produção (`PietroPCM/TESTE-RAILWAY-IZES-AGRO`)
  é separado: não acessar, não clonar, não enviar. Sem deploy/push/merge para produção.
- **Não acessar banco real.** Use SQLite temporário, fixtures ou mocks nos testes.
- **Não usar OpenAI real em testes.** Sempre mockar.
- **Não ler nem imprimir segredos** nem o conteúdo de `.env`.
- **Não alterar o app Flutter** nem funcionalidades sem relação com IA/RAG.
- **RAG**: indexar apenas documentos validados. Nunca indexar
  `DOC_IRRIGACAO_FAO_001` e `DOC_SENSOR_ARTIGO_003`. Não inventar fonte nem citação.
