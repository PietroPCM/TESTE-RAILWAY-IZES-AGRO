# IA Agro do IZES com RAG — guia técnico

Primeira versão funcional da IA agro com recuperação de conhecimento técnico
(RAG) local. Documento cobre o fluxo de intenção, os modos da IA, a recuperação,
como reconstruir o índice, como adicionar/validar documentos, como testar e as
limitações atuais.

## 1. Fluxo de intenção

```
pergunta do usuário
 → interpretação semântica da intenção (intent_classifier)
 → decisão sobre uso dos dados do cliente
 → decisão sobre uso do RAG
 → recuperação dos dados necessários (contexto_ia) e do conhecimento técnico (rag)
 → montagem controlada do contexto (dados reais x conhecimento técnico, separados)
 → chamada do modelo (com fallback seguro)
 → resposta natural e estruturada, com fontes e encerramento contextual
```

A classificação acontece **antes** de consultar o banco e o modelo, mas usa
`cliente_id` e `sensor_id` para desambiguar. Não há mais um bloqueio rígido por
lista de palavras: a antiga `classificar_escopo_pergunta` caía em `fora_escopo`
sempre que a pergunta não batia em frases específicas. Agora a decisão combina
sinais (entidades, possessivos, status, dêixis, comparação, conhecimento geral,
sinais externos) — ver `app/services/intent_classifier.py`.

## 2. Modos da IA

| Modo | Quando | Origem | Dados reais |
|------|--------|--------|-------------|
| `agro_com_dados` | pergunta sobre a situação real (áreas, canteiros, sensores, leituras, comparações, “esse aqui”, “qual está pior”) | `openai` / `fallback_local` | sim |
| `agro_geral` | dúvida agro/rural geral (“o que é pH?”, “como funciona irrigação?”) | `openai_com_rag` / `fallback_local` | não |
| `esclarecimento` | pergunta ambígua **sem** contexto suficiente (“Como está?” sem cliente/sensor) | `regra_contextual` | não |
| `fora_escopo` | claramente externo ao agro (capital, código, futebol…) | `sem_openai` | não |

Regras de desambiguação:
- **Com `cliente_id` e sem `sensor_id`**: perguntas gerais do cliente viram
  `agro_com_dados` (consulta os sensores relevantes e últimas leituras; permite
  comparação). Não exige a palavra “sensor” ou “solo”.
- **Com `sensor_id`**: referências como “esse”, “aqui”, “ele”, “essa área”
  apontam para o sensor informado; o sensor é validado como pertencente ao cliente.
- **Ambíguo sem contexto**: pede esclarecimento objetivo (termina com pergunta),
  sem a frase genérica antiga.

## 3. Uso de `cliente_id` e `sensor_id`
- Toda consulta de dados usa **somente** o `cliente_id` informado (isolamento total
  entre clientes — ver `contexto_ia._buscar_sensores_relevantes`).
- `sensor_id` é validado: se não pertence ao cliente, retorna 404
  (`SensorIANaoEncontrado`).
- Sem `sensor_id`, a consulta abrange múltiplos sensores (comparação entre áreas).

## 4. Arquitetura do RAG (`app/services/rag/`)
- **Local, sem banco vetorial**, compatível com Railway. Ponto de evolução futura:
  embeddings ou pgvector.
- `metadata.py`: lê o inventário oficial
  (`conhecimento-rag/fontes/inventario_documentos.csv`) e expõe quais documentos
  são válidos. `DOC_IRRIGACAO_FAO_001` e `DOC_SENSOR_ARTIGO_003` são **proibidos**
  e nunca entram no índice.
- `chunking.py`: quebra fiel dos textos extraídos, preservando o vínculo com o
  documento e as **páginas** (`--- PÁGINA N ---`). Rejeita texto corrompido/curto/
  com alta proporção de caracteres inválidos (OCR ruim).
- `build_index.py`: gera `index/rag_index.json` com chunks + metadados completos
  (`chunk_id, documento_id, titulo, instituicao, autores, ano, url,
  arquivo_original, pagina_inicio, pagina_fim, tema, subtema, cultura, regiao,
  tipo_extracao, confiabilidade, texto`).
- `retriever.py`: recuperação **BM25** com normalização de acentos, tokenização,
  remoção de stopwords, **sinônimos agrícolas** (canteiro seco → umidade/irrigação;
  terra ácida → pH/calagem; NPK → nutrientes…), filtro por cultura, remoção de
  duplicidade (máx. 2 chunks por documento) e limite de contexto. Nunca derruba o
  chamador: se o índice faltar ou a busca falhar, retorna vazio.

### Reconstruir o índice
```
cd agrisoil-backend
python -m app.services.rag.build_index
```
Saída: total de documentos indexados, total de chunks e documentos ignorados.

## 5. Como fontes são retornadas
- Apenas as fontes que **realmente entraram no contexto** aparecem no campo
  `fontes` da resposta e na seção de fontes do prompt. Formato:
```json
"fontes": [
  {
    "documento_id": "DOC_SENSOR_EMBRAPA_001",
    "titulo": "Protocolo para a calibração e a aferição de sensores de umidade de solo",
    "instituicao": "Embrapa",
    "ano": 2024,
    "url": "https://www.infoteca.cnptia.embrapa.br/...",
    "paginas": "1-2"
  }
]
```
- O prompt separa explicitamente: PERGUNTA, DADOS REAIS, CONHECIMENTO TÉCNICO
  RECUPERADO e FONTES. O modelo é instruído a **não citar documento que não foi
  recuperado**.

## 6. Padrão de encerramento contextual
- Respostas `agro_com_dados` e `agro_geral` terminam com uma sugestão curta,
  contextual, geralmente com “É só pedir.” (ver
  `openai_service._encerramento_contextual`). A frase varia conforme o contexto
  (vários sensores → comparar; sem dados → pedir a área/sensor; agro_geral →
  relacionar com cultura/região/sensores).
- **Não** é usado em: erros técnicos/HTTP, `fora_escopo` (que oferece uma
  alternativa agro breve) e `esclarecimento` (que termina com pergunta objetiva).
- Não aparece dentro de campos técnicos nem na lista de fontes — apenas no final de
  `resposta_texto`.

## 7. Robustez (degradação segura)
- **RAG indisponível/vazio**: a IA ainda responde (conhecimento geral seguro), sem
  inventar citação.
- **OpenAI indisponível ou JSON inválido**: fallback local determinístico
  (`modelo = fallback-local`), sem derrubar o endpoint.
- **Erro de banco ao montar contexto**: 503 controlado.
- O formato de `RespostaIA` foi **preservado**; `fontes` foi adicionado como campo
  opcional (compatível com o Swagger/app).

## 8. Como testar localmente
```
cd agrisoil-backend
python -m pytest tests/test_ia_intent.py tests/test_rag.py tests/test_ia_integration.py -q
python -m pytest tests/ -q          # suíte completa
python -m compileall -q app
```
Os testes usam SQLite temporário, fixtures (dados AgriSoil) e mocks da OpenAI.
Nenhum teste chama OpenAI real ou banco real.

### Testar no Swagger (`/docs`)
`POST /api/ia/chat` com header `X-App-Token` e query params:
- `cliente_id=agrisoil`, `pergunta=Qual canteiro precisa de mais atenção?`
- `cliente_id=agrisoil`, `pergunta=O que é pH?` (agro_geral, traz fontes)
- `cliente_id=agrisoil`, `pergunta=Qual a capital da Itália?` (fora_escopo)
- `cliente_id=agrisoil`, `sensor_id=estufa-1-canteiro-03`, `pergunta=E esse aqui?`

Confira `resposta_estruturada.modo`, `resposta_estruturada.origem` e o campo
`fontes` (deve corresponder ao conhecimento técnico usado).

## 9. Adicionar/validar um novo documento
1. Adicione o PDF em `conhecimento-rag/originais/<fonte>/` e o texto extraído fiel
   em `conhecimento-rag/extraidos/<tema>/` (com marcadores `--- PÁGINA N ---`).
2. Inclua a linha correspondente em
   `conhecimento-rag/fontes/inventario_documentos.csv` com `status_validacao=VÁLIDO`
   e `caminho_extraido` preenchido. Documentos sem original validado devem ficar
   `INVÁLIDO` (não entram no índice).
3. Rode `python -m app.services.rag.build_index` e
   `python -m pytest tests/test_rag.py -q`.

## 10. Limitações atuais e evolução
- Recuperação **lexical** (BM25): documentos em inglês (FAO/artigos) raramente são
  recuperados por consultas em português; isso evita poluir respostas, mas reduz a
  cobertura desse material.
- Sem embeddings/semântica densa: sinônimos são tratados por dicionário; consultas
  muito fora do vocabulário podem não recuperar o tema ideal.
- Histórico de conversa ainda é em memória (não persistido).
- Evolução planejada: embeddings/pgvector como camada semântica complementar ao
  BM25, mantendo o índice local como fallback.
