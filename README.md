# 🌱 IZES-AGROSENSORES

<p align="center">
  <strong>Backend inteligente para monitoramento agrícola, sensores IoT, alertas de solo e apoio à decisão no campo.</strong>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-API-009688?style=for-the-badge&logo=fastapi&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-ready-2496ED?style=for-the-badge&logo=docker&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL%2FSupabase-planned-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white">
</p>

---

## ✨ O Que É

O **IZES-AGROSENSORES** é uma API backend para agricultura de precisão.

Ele recebe leituras de sensores agrícolas, valida os dados, registra histórico, aplica regras agronômicas e gera alertas para ajudar produtores, técnicos e gestores a tomarem decisões mais rápidas no campo.

Pense nele como o cérebro entre:

- sensores físicos ou simulados;
- banco de dados agrícola;
- dashboard web;
- aplicativo mobile;
- sistema de alertas;
- análise com IA.

---

## 🚜 O Que Ele Entrega

| Área | Entrega |
|---|---|
| Sensores IoT | Cadastro, status, histórico e recebimento de leituras via webhook |
| Solo | Avaliação de pH, umidade, temperatura, condutividade e NPK |
| Alertas | Geração automática de alertas por severidade |
| Dashboard/App | Endpoints para consumo por frontend ou mobile |
| IA | Base para análise contextualizada com OpenAI |
| Observabilidade | Health checks, logs e métricas Prometheus |
| Docker | Container da API FastAPI pronto para build e execução |

---

## 🧠 Fluxo Principal

```mermaid
flowchart LR
    A["Sensor IoT"] --> B["Webhook /webhook/sensor/{id}"]
    B --> C["Validação dos dados"]
    C --> D["Leitura salva"]
    D --> E["Motor de regras"]
    E --> F{"Problema detectado?"}
    F -- "Sim" --> G["Alerta criado"]
    F -- "Não" --> H["Histórico atualizado"]
    G --> I["Dashboard / App / Notificação"]
    H --> I
    I --> J["Análise com IA"]
```

---

## 🌾 Parâmetros Monitorados

O sistema trabalha com leituras como:

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

Cada leitura pode gerar avaliações como:

- solo seco;
- solo encharcado;
- pH ácido ou alcalino;
- temperatura crítica;
- deficiência de nitrogênio;
- deficiência de fósforo;
- deficiência de potássio.

---

## 🧩 Módulos do Sistema

### Sensores

Responsável por cadastrar sensores, consultar detalhes, listar sensores por cliente e receber leituras.

Rotas principais:

```text
POST   /api/sensores/cadastrar
PATCH  /api/sensores/{sensor_id}/status
DELETE /api/sensores/{sensor_id}
GET    /api/sensores/{cliente}
GET    /api/sensores/{cliente}/{sensor_id}
GET    /api/sensores/{cliente}/{sensor_id}/historico
```

### Webhook IoT

Entrada para sensores físicos enviarem dados em tempo real.

```text
POST /webhook/sensor/{sensor_id}
GET  /webhook/sensor/{sensor_id}/status
GET  /webhook/health
```

### Motor de Regras

Avalia leituras e classifica cada parâmetro em níveis como `ok`, `aviso`, `alerta` ou `critico`.

Arquivos principais:

```text
agrisoil-backend/app/rules/ph_rules.py
agrisoil-backend/app/rules/moisture_rules.py
agrisoil-backend/app/rules/temperature_rules.py
agrisoil-backend/app/rules/nitrogen_rules.py
agrisoil-backend/app/rules/phosphorus_rules.py
agrisoil-backend/app/rules/potassium_rules.py
```

### Alertas

Cria alertas automáticos quando uma leitura indica risco. Também possui deduplicação para evitar alerta repetido do mesmo tipo no mesmo dia.

```text
GET  /alertas/
GET  /alertas/resumo
GET  /alertas/{alerta_id}
POST /alertas/reconhecer-todos
```

### IA Agronômica

O módulo de IA usa contexto agrícola para responder perguntas e gerar recomendações.

Hoje o código está preparado para OpenAI via `OPENAI_API_KEY`.
Se `OPENAI_API_KEY` não estiver configurada, o endpoint usa fallback local seguro sem chamada externa.

```text
POST /api/ia/chat
GET  /api/ia/historico/{cliente_id}
```

Documentação de teste local:

```text
TESTE_IA.md
```

### Clima, Plantio e Gestão Agrícola

O projeto também possui módulos para:

- clima;
- clientes;
- fazendas;
- talhões;
- culturas;
- zonas de manejo;
- plantio;
- infraestrutura da propriedade;
- alertas estratégicos.

Algumas dessas áreas ainda estão em evolução e possuem trechos mockados ou pendentes de persistência real.

---

## 🏗️ Arquitetura

```mermaid
flowchart TD
    UI["Dashboard / Mobile App"] --> API["FastAPI Backend"]
    SENSOR["Sensores IoT"] --> WEBHOOK["Webhook IoT"]
    WEBHOOK --> API
    API --> RULES["Motor de Regras"]
    API --> DB["PostgreSQL / Supabase"]
    RULES --> ALERTS["Alertas"]
    ALERTS --> PUSH["Firebase Push"]
    API --> AI["OpenAI / IA Agronômica"]
    API --> METRICS["Prometheus / Metrics"]
```

---

## 🐳 Docker

O projeto possui um `Dockerfile` funcional para empacotar e rodar a API.

### O Que Funciona no Docker Hoje

O container:

- usa `python:3.13-slim`;
- instala as dependências do `requirements.txt`;
- copia o backend para `/app`;
- cria usuário não-root;
- expõe a porta `8000`;
- roda a API com Uvicorn;
- possui health check básico por socket;
- consegue conectar em um PostgreSQL externo via `DATABASE_URL`.

### O Que o Docker Ainda Não Sobe

O Dockerfile atual **não** sobe:

- banco de dados;
- Supabase local;
- Redis;
- Celery worker separado;
- Prometheus;
- Grafana;
- Firebase;
- frontend ou app mobile.

Ou seja: o Docker hoje roda a **API**, mas os serviços externos precisam ser configurados separadamente.

### Build

```bash
docker build -t izes-agrosensores .
```

### Run

```bash
docker run --rm -p 8000:8000 \
  -e DATABASE_URL="postgresql://usuario:senha@host:5432/banco" \
  -e SECRET_KEY="troque-essa-chave" \
  -e SENSOR_API_KEY="chave-dos-sensores" \
  -e ENVIRONMENT="development" \
  izes-agrosensores
```

Depois de subir:

```text
http://localhost:8000
http://localhost:8000/docs
http://localhost:8000/api/health
http://localhost:8000/metrics
```

---

## 🗄️ Banco de Dados

O código usa SQLAlchemy e espera uma variável:

```env
DATABASE_URL=postgresql://usuario:senha@host:5432/banco
```

O backend não possui mais fallback hardcoded de banco. Se `DATABASE_URL` não estiver configurada, a aplicação falha com erro claro e sem imprimir segredo.

Para Railway/teste real, veja:

```text
DEPLOY_RAILWAY.md
TESTE_SWAGGER.md
```

## Segurança de startup

Por padrão, o startup não cria schema e não executa seeds:

```env
AUTO_CREATE_TABLES=false
AUTO_RUN_SEEDS=false
```

Em banco novo de teste, é possível habilitar temporariamente:

```env
AUTO_CREATE_TABLES=true
AUTO_RUN_SEEDS=false
```

Não habilite criação automática de tabelas ou seeds em banco real sem autorização, backup e plano de migração.

## Teste manual sem sensor físico

O Swagger permite preparar dados de teste protegidos por `SENSOR_API_KEY`:

```text
POST /api/sensores/manual
POST /api/sensores/{cliente}/{sensor_id}/leitura-manual
GET  /api/dashboard/cliente/{cliente_id}/sensores
```

Use o header:

```text
X-API-Key: valor configurado em SENSOR_API_KEY
```

Endpoints internos do app que usam `X-App-Token`, como `/api/ia/chat`, exigem correspondência exata com `APP_INTERNAL_TOKEN`. Em produção/staging, configure essa variável no Railway sem registrar o valor no repositório.

O caminho mais provável para o projeto é usar **Supabase**, já que ele entrega PostgreSQL gerenciado.

Nesse caso, basta apontar o `DATABASE_URL` para a string de conexão do Supabase.

Modelos já previstos:

- sensores;
- leituras;
- alertas;
- usuários;
- fazendas;
- talhões;
- culturas;
- operações agrícolas;
- fertilizantes.

---

## ⚙️ Variáveis de Ambiente

Exemplo básico:

```env
DATABASE_URL=postgresql://usuario:senha@host:5432/banco
SECRET_KEY=troque-essa-chave
SENSOR_API_KEY=chave-dos-sensores
APP_INTERNAL_TOKEN=token-interno-do-app
ENVIRONMENT=development
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4-turbo
REDIS_HOST=localhost
SENTRY_DSN=
```

`ALLOWED_HOSTS` ainda não é consumida por esta versão do backend; hosts confiáveis estão definidos no código e devem ser fechados em produção futura.

## Ações manuais necessárias

- Configurar variáveis obrigatórias no Railway: `DATABASE_URL`, `SECRET_KEY`, `SENSOR_API_KEY`, `APP_INTERNAL_TOKEN` e `APP_ENV`; sem isso, o backend pode não subir ou endpoints protegidos podem falhar.
- Configurar `OPENAI_API_KEY` para IA com OpenAI real; sem isso, `/api/ia/chat` usa fallback local seguro.
- Configurar `OPENAI_MODEL`, `OPENAI_TEMPERATURE` e `OPENAI_MAX_TOKENS` se quiser controlar comportamento/custo da IA; sem isso, valem os defaults do código.
- Fazer redeploy após alterar variáveis no Railway; sem redeploy, a aplicação pode continuar com configuração anterior.
- Testar `/health/live`, `/docs`, sensor manual, leitura manual, dashboard e `/api/ia/chat` após redeploy.
- Não commitar `.env`, chaves, tokens, URLs reais ou arquivos de credenciais.

> Login/autenticação ainda será modificado, então essa parte não deve ser tratada como final.

---

## 🚀 Rodando Localmente Sem Docker

```bash
cd agrisoil-backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Acesse:

```text
http://localhost:8000/docs
```

---

## 📡 Exemplo de Leitura via Webhook

```bash
curl -X POST "http://localhost:8000/webhook/sensor/SENSOR-001" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: chave-dos-sensores" \
  -d '{
    "timestamp": "2026-02-02T14:30:00Z",
    "ph": 6.8,
    "umidade": 45.2,
    "temperatura": 24.5,
    "condutividade": 1.2,
    "nitrogenio": 120,
    "fosforo": 30,
    "potassio": 80
  }'
```

---

## 📊 Estado Atual

| Parte | Status |
|---|---|
| API FastAPI | Funcional |
| Sensores | Funcional |
| Webhook IoT | Funcional |
| Motor de regras | Funcional |
| Alertas automáticos | Funcional |
| Docker da API | Funcional |
| Supabase | Planejado |
| Login/Auth | Será modificado |
| IA | Estrutura pronta, depende de chave |
| Firebase Push | Estrutura pronta, depende de credenciais |
| Redis/Celery | Estrutura presente, depende de ambiente |
| Alguns módulos de gestão | Em evolução |

---

## 🧭 Próximos Passos Recomendados

1. Definir Supabase como banco final.
2. Ajustar `DATABASE_URL` e validar criação das tabelas.
3. Criar `docker-compose.yml` se quiser ambiente local completo.
4. Redesenhar login/autenticação.
5. Separar o que é funcional do que ainda é mock nos módulos de gestão.
6. Criar testes para sensores, webhook, regras e alertas.
7. Padronizar encoding dos documentos antigos.

---

## 📚 Documentação Extra

- [Documento do Sistema](./DOCUMENTO_DO_SISTEMA.md)

---

## 🫶 Resumo

O **IZES-AGROSENSORES** transforma dados brutos do campo em informação útil.

Sensor entra com números.

O backend devolve contexto, alerta, histórico e recomendação.

Esse é o coração técnico de uma plataforma agrícola inteligente.
