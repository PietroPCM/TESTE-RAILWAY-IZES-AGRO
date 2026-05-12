# IZES-AGROSENSORES - Documento do Sistema

## 1. Visao geral

O IZES-AGROSENSORES e um backend de monitoramento agricola inteligente. Ele foi pensado para receber dados de sensores de solo e clima, armazenar leituras, aplicar regras agronomicas, gerar alertas e fornecer respostas para aplicativos, paineis administrativos ou sistemas externos.

Na pratica, o sistema funciona como uma API central para uma plataforma de agricultura de precisao. Ele nao e apenas um cadastro simples de sensores: a proposta e transformar leituras brutas, como pH, umidade, temperatura e NPK, em informacoes uteis para tomada de decisao no campo.

O backend esta construido em Python com FastAPI, usa modelos Pydantic para contratos de API, SQLAlchemy para persistencia e possui integracoes planejadas com banco PostgreSQL, IA, notificacoes push, metricas e tarefas em background.

## 2. Que tipo de sistema e esse

E um sistema backend/API para agricultura de precisao, com foco em:

- monitoramento de sensores agricolas;
- historico de leituras de solo;
- deteccao de problemas agronomicos;
- geracao de alertas;
- apoio a decisoes de manejo;
- exposicao de dados para dashboard ou app mobile;
- integracao futura com banco externo, provavelmente Supabase;
- integracao com IA para analise contextualizada.

Ele pode ser entendido como o nucleo tecnico de uma plataforma maior. Um aplicativo mobile, painel web ou dashboard pode consumir essa API para mostrar dados ao produtor, tecnico, gestor ou agronomo.

## 3. O que o sistema faz

### 3.1 Cadastro e gestao de sensores

O sistema possui rotas para cadastrar sensores, ativar/desativar sensores, deletar sensores, listar sensores de um cliente e consultar detalhes de um sensor especifico.

Cada sensor pode ter dados como:

- identificador unico;
- cliente/proprietario;
- nome;
- tipo, como solo, ar ou agua;
- latitude e longitude;
- propriedade;
- municipio;
- estado;
- local especifico, como talhao, estufa ou setor.

Esse modulo e a base para conectar sensores fisicos ou simulados ao backend.

### 3.2 Recebimento de leituras IoT

O sistema possui webhook para sensores enviarem leituras por HTTP.

O endpoint principal recebe dados como:

- timestamp;
- pH;
- umidade do solo;
- temperatura;
- condutividade;
- nitrogenio;
- fosforo;
- potassio.

Ao receber uma leitura, o backend valida os valores, confirma se o sensor existe e esta ativo, grava a leitura e executa regras agronomicas para identificar situacoes de risco.

Exemplos de leituras aceitas:

```json
{
  "timestamp": "2026-02-02T14:30:00Z",
  "ph": 6.8,
  "umidade": 45.2,
  "temperatura": 24.5,
  "condutividade": 1.2,
  "nitrogenio": 120,
  "fosforo": 30,
  "potassio": 80
}
```

### 3.3 Motor de regras agronomicas

O sistema possui regras para avaliar parametros do solo. Hoje existem regras separadas para:

- pH;
- umidade;
- temperatura;
- nitrogenio;
- fosforo;
- potassio.

Essas regras classificam a leitura em niveis como `ok`, `aviso`, `alerta` ou `critico`, e retornam mensagens e acoes recomendadas.

Exemplos de decisoes:

- pH muito baixo pode gerar recomendacao de calagem;
- umidade muito baixa pode gerar alerta de irrigacao urgente;
- temperatura muito alta pode indicar risco de dano a raizes;
- nitrogenio, fosforo ou potassio baixos podem indicar necessidade de adubacao.

## 4. O que o sistema entrega

O backend entrega uma API capaz de:

- receber dados de sensores;
- validar leituras;
- salvar historico;
- calcular avaliacoes agronomicas;
- gerar alertas automaticos;
- expor informacoes para dashboard;
- consultar historico de sensores;
- retornar resumo de alertas;
- servir uma pagina de dashboard estatica quando disponivel;
- expor health checks;
- expor metricas Prometheus;
- preparar notificacoes push;
- estruturar contexto para analise com IA.

Em termos de produto, ele entrega uma camada de inteligencia entre o campo e a interface do usuario. O sensor envia numero bruto; o sistema devolve contexto, risco, recomendacao e historico.

## 5. Modulos principais

### 5.1 API FastAPI

O arquivo principal e `agrisoil-backend/app/main.py`. Ele cria a aplicacao FastAPI, configura middlewares, registra rotas, ativa metricas e inicializa banco/cache quando disponivel.

Principais grupos de rotas:

- `/api/sensores`: sensores e leituras;
- `/webhook`: recebimento de dados IoT;
- `/alertas` e `/api/alertas`: alertas;
- `/api/clima`: clima;
- `/api/dashboard`: dados para dashboard;
- `/api/ia`: perguntas e analises com IA;
- `/api/agri`: entidades agricolas;
- `/api/clientes`: clientes;
- `/api/zonas-manejo`: zonas de manejo;
- `/api/plantio`: plantio e fase da cultura;
- `/api/infraestrutura`: infraestrutura da propriedade;
- `/health` e `/api/health`: saude da aplicacao;
- `/metrics`: metricas Prometheus, quando habilitado.

### 5.2 Banco de dados

Atualmente o codigo usa SQLAlchemy e espera uma URL de banco em `DATABASE_URL`. O modelo esta mais alinhado com PostgreSQL.

Como o banco ainda sera definido e provavelmente sera Supabase, o caminho natural e usar o Postgres do Supabase como banco principal. O Supabase fornece uma string de conexao PostgreSQL, que pode alimentar o `DATABASE_URL`.

O sistema ja possui tabelas/modelos para:

- sensores;
- leituras;
- alertas;
- usuarios;
- fazendas/propriedades;
- talhoes;
- culturas;
- operacoes agricolas;
- fertilizantes.

### 5.3 Alertas

Os alertas sao criados quando o motor de regras identifica uma leitura problematica. O sistema possui deduplicacao para evitar criar o mesmo alerta repetidamente no mesmo dia para o mesmo sensor, tipo e severidade.

Um alerta pode ter:

- tipo, como pH, umidade, temperatura, nitrogenio, fosforo ou potassio;
- severidade;
- status;
- mensagem;
- valor medido;
- referencia;
- recomendacao;
- vinculo com leitura e sensor.

### 5.4 IA

O sistema possui servico de IA em `app/services/openai_service.py`. A ideia e montar um contexto agricola com sensores, historico, clima, cultura e alertas, e enviar para um modelo de IA para gerar uma resposta mais explicativa.

Hoje a documentacao antiga fala em Gemini em alguns pontos, mas o codigo atual esta preparado para OpenAI via `OPENAI_API_KEY`.

Esse modulo entrega:

- resposta textual;
- recomendacao principal;
- pontos de atencao;
- proximos passos;
- confianca geral;
- quantidade de tokens usados.

### 5.5 Notificacoes

O sistema possui codigo para notificacoes push via Firebase Cloud Messaging e notificacoes por email.

As notificacoes podem ser usadas para avisar quando um alerta critico ou importante for criado.

Para funcionar de verdade, o ambiente precisa ter as credenciais do Firebase configuradas.

### 5.6 Observabilidade

O sistema possui suporte a:

- logs estruturados;
- Sentry, se `SENTRY_DSN` estiver configurado;
- Prometheus em `/metrics`;
- health checks;
- metricas customizadas de leituras, alertas, sensores e banco.

Isso ajuda a acompanhar se a API esta viva, se recebe leituras e se alertas estao sendo gerados.

## 6. Fluxo principal de uso

Um fluxo normal do sistema seria:

1. Cadastrar um sensor no backend.
2. Associar o sensor a um cliente/propriedade/local.
3. O sensor fisico ou simulador envia leituras para o webhook.
4. O backend valida a chave da API e os dados recebidos.
5. A leitura e salva.
6. O motor de regras avalia os parametros.
7. Se houver problema, o sistema cria alerta.
8. O dashboard ou app consulta sensores, historico e alertas.
9. A IA pode responder perguntas usando o contexto agricola.
10. Notificacoes podem ser disparadas quando configuradas.

## 7. O que funciona no Docker

O projeto possui um `Dockerfile` na raiz. Ele cria uma imagem Docker para rodar o backend FastAPI.

### 7.1 O que o Dockerfile faz

O Dockerfile:

- usa `python:3.13-slim`;
- instala dependencias de sistema necessarias, como `gcc` e `postgresql-client`;
- copia `agrisoil-backend/requirements.txt`;
- instala as dependencias Python;
- copia o codigo do backend para `/app`;
- cria um usuario nao-root chamado `appuser`;
- expoe a porta `8000`;
- adiciona um health check simples por socket;
- inicia a API com Uvicorn em `0.0.0.0:8000`.

Com isso, o container deve conseguir subir a API FastAPI, desde que as variaveis de ambiente e dependencias externas estejam corretas.

### 7.2 O que o Docker entrega hoje

Hoje o Docker entrega:

- container da API;
- instalacao das dependencias Python;
- servidor Uvicorn;
- porta `8000`;
- health check basico;
- runtime isolado;
- usuario nao-root;
- suporte a conexao com PostgreSQL externo.

Em outras palavras: o Docker empacota e roda o backend.

### 7.3 O que o Docker nao entrega hoje

O Docker atual nao sobe:

- banco de dados;
- Supabase local;
- Redis;
- Celery worker separado;
- Prometheus;
- Grafana;
- Firebase;
- servico de IA;
- frontend/app mobile.

Tambem nao existe `docker-compose.yml` no projeto hoje. Entao, se for rodar localmente com banco e Redis, sera necessario criar um compose ou usar servicos externos.

### 7.4 Variaveis importantes para rodar no Docker

Para o container funcionar bem, algumas variaveis precisam ser passadas:

```env
DATABASE_URL=postgresql://usuario:senha@host:5432/banco
SECRET_KEY=uma-chave-segura
SENSOR_API_KEY=chave-dos-sensores
ENVIRONMENT=development
OPENAI_API_KEY=sua-chave-openai
REDIS_HOST=host-do-redis
SENTRY_DSN=
```

Se o banco for Supabase, o `DATABASE_URL` deve apontar para o Postgres do Supabase.

### 7.5 Comandos esperados

Build da imagem:

```bash
docker build -t izes-agrosensores .
```

Rodar a API:

```bash
docker run --rm -p 8000:8000 \
  -e DATABASE_URL="postgresql://usuario:senha@host:5432/banco" \
  -e SECRET_KEY="troque-essa-chave" \
  -e SENSOR_API_KEY="chave-dos-sensores" \
  izes-agrosensores
```

Apos subir, a API deve responder em:

```text
http://localhost:8000
http://localhost:8000/docs
http://localhost:8000/api/health
```

### 7.6 Pontos de atencao no Docker

O Dockerfile esta funcional para empacotar a API, mas existem pontos que ainda precisam ser decididos:

- o banco final ainda sera definido;
- se for Supabase, nao precisa subir Postgres no Docker;
- se quiser desenvolvimento local completo, vale criar `docker-compose.yml`;
- Redis/Celery precisam de containers ou servicos externos proprios;
- as credenciais devem vir por variaveis de ambiente;
- o container nao deve guardar `.env` ou segredos dentro da imagem.

## 8. Estado atual do sistema

O sistema tem uma base boa e varios modulos ja estruturados. As partes mais concretas hoje sao:

- API FastAPI;
- cadastro/listagem de sensores;
- webhook de sensores;
- validacao de leitura;
- persistencia via SQLAlchemy;
- motor de regras;
- criacao de alertas;
- metricas;
- health checks;
- Dockerfile para rodar a API.

As partes que ainda parecem em evolucao ou dependem de configuracao externa sao:

- banco final, provavelmente Supabase;
- autenticacao/login, que sera alterada;
- IA em producao;
- notificacoes Firebase;
- Redis/Celery;
- dashboards completos;
- persistencia real de alguns modulos que ainda tem TODO/mock;
- padronizacao final da documentacao.

## 9. Valor entregue para o usuario final

Para o produtor, tecnico ou gestor, o sistema entrega:

- visao da saude do solo;
- alertas sobre problemas reais;
- historico de leituras;
- recomendacoes praticas;
- base para decisao de irrigacao, calagem, adubacao e manejo;
- acompanhamento por sensor, propriedade e local;
- possibilidade de analise com IA.

Para o time tecnico, entrega:

- API organizada;
- modelos de dados agricolas;
- separacao por rotas, servicos, regras e repositorios;
- caminho claro para integrar Supabase;
- container Docker para rodar a aplicacao;
- base para dashboards, mobile e automacoes.

## 10. Resumo final

O IZES-AGROSENSORES e um backend de agricultura de precisao voltado para transformar dados de sensores em inteligencia agricola. Ele recebe leituras, avalia os parametros do solo, gera alertas e disponibiliza informacoes para interfaces externas.

O Docker hoje funciona como empacotamento da API: ele sobe o backend FastAPI na porta `8000`, mas nao sobe o banco nem os servicos auxiliares. Para o proximo passo, o ideal e decidir o banco final no Supabase, ajustar `DATABASE_URL`, e depois criar um ambiente local completo se necessario.
