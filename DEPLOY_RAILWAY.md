# Deploy Railway - IZES-AGRO Backend

## Status

O backend está preparado para subir no Railway como API FastAPI, desde que as variáveis obrigatórias sejam configuradas manualmente.

Nenhum deploy real deve ser executado sem confirmação explícita.

## Start command

Com Dockerfile:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

O `Dockerfile` já usa `PORT` quando a plataforma definir a variável.

## Variáveis necessárias no Railway

- `DATABASE_URL`: string de conexão do PostgreSQL provisionado para o ambiente.
- `SECRET_KEY`: chave forte para assinatura JWT.
- `SENSOR_API_KEY`: chave para sensores físicos e fluxo manual de teste via Swagger.
- `APP_INTERNAL_TOKEN`: token interno usado por endpoints com header `X-App-Token`, como `/api/ia/chat`.
- `APP_ENV`: ambiente da aplicação. Use `production` em produção e `development`/`test` apenas em ambiente controlado.
- `AUTO_CREATE_TABLES`: `false` por padrão. Habilitar apenas explicitamente em banco novo/teste.
- `AUTO_RUN_SEEDS`: `false` por padrão. Habilitar apenas explicitamente quando seeds forem desejados.
- `CORS_ORIGINS`: origens do app/site autorizadas, separadas por vírgula.
- `CORS_CREDENTIALS`: define se CORS aceita credenciais.
- `CORS_METHODS`: métodos HTTP permitidos.
- `CORS_HEADERS`: headers permitidos.
- `ALLOWED_HOSTS`: ainda não é lida por esta versão do backend. Hosts confiáveis estão definidos no código e devem ser tratados como pendência para produção final.
- `OPENAI_API_KEY`: necessária somente se o módulo de IA for usado.
- `OPENAI_MODEL`: modelo usado pela integração OpenAI.
- `OPENAI_TEMPERATURE`: temperatura da resposta de IA.
- `OPENAI_MAX_TOKENS`: limite de tokens da resposta de IA.
- `OPENWEATHERMAP_API_KEY`: necessária somente se o provedor de clima for usado.
- `WEATHERAPI_API_KEY`: necessária somente se esse provedor de clima for usado.
- `REDIS_HOST`: necessária somente se Redis/cache/Celery forem usados.
- `REDIS_PORT`: porta Redis.
- `REDIS_DB`: database Redis.
- `REDIS_PASSWORD`: senha Redis, se existir.
- `CELERY_BROKER_URL`: necessária somente se worker Celery for usado.
- `CELERY_RESULT_BACKEND`: backend de resultado Celery.
- `FIREBASE_CREDENTIALS_PATH`: caminho do arquivo de credenciais Firebase, se push notification for usado.
- `SENTRY_DSN`: DSN do Sentry, se monitoramento de erro for usado.
- `PROMETHEUS_ENABLED`: habilita `/metrics`.
- `FORCE_HTTPS`: força redirect HTTPS em produção.
- `PORT`: definida automaticamente pelo Railway.

Nunca registre valores reais dessas variáveis em documentação, git, memória ou logs.

## Banco de dados

Provisionar manualmente um PostgreSQL no Railway ou apontar `DATABASE_URL` para outro PostgreSQL gerenciado.

O backend normaliza URLs `postgres://` e `postgresql://` para o dialect `postgresql+psycopg://`, usando `psycopg` v3.

No Railway, `DATABASE_URL` deve referenciar a variável gerada pelo serviço PostgreSQL. Se a referência aparecer literalmente no runtime, por exemplo como texto não resolvido, o backend rejeita a configuração com erro seguro sem imprimir a URL.

Conferir no Railway:

- O serviço PostgreSQL existe no mesmo projeto/ambiente.
- A variável `DATABASE_URL` do backend referencia a variável do PostgreSQL e está resolvida no ambiente de deploy.
- A URL resolvida começa com `postgresql://`, `postgres://` ou `postgresql+psycopg://`.

## Schema e migrações

Alembic está presente nas dependências, mas não há configuração completa confirmada de Alembic no projeto.

Opções seguras:

- Para banco novo de teste: subir temporariamente com `AUTO_CREATE_TABLES=true` e `AUTO_RUN_SEEDS=false`, validar, depois voltar `AUTO_CREATE_TABLES=false`.
- Para produção real: preparar migrações antes de apontar para banco com dados. Não usar `create_all()` como processo definitivo de migração.

Não rode migrations, seeds ou scripts contra banco real sem backup e autorização.

## Healthcheck

Railway está configurado para healthcheck em:

```text
/health/live
```

Endpoints úteis:

```text
/docs
/openapi.json
/api/health
/health/live
/health/ready
```

## Passos manuais no Railway

1. Criar projeto Railway.
2. Provisionar PostgreSQL ou configurar `DATABASE_URL` de PostgreSQL externo.
3. Configurar variáveis obrigatórias, sem commitar valores.
4. Fazer primeiro deploy.
5. Em banco novo/teste, decidir se `AUTO_CREATE_TABLES=true` será usado temporariamente.
6. Validar `/health/live`, `/api/health` e `/docs`.
7. Criar sensor manual pelo Swagger.
8. Enviar leitura manual pelo Swagger.
9. Conferir `/api/dashboard/cliente/{cliente_id}/sensores`.
10. Ajustar `CORS_ORIGINS` para o domínio real do app/site.
11. Configurar `APP_INTERNAL_TOKEN` antes de testar endpoints com `X-App-Token`.

## Ações manuais necessárias

- Configurar `DATABASE_URL`, `SECRET_KEY`, `SENSOR_API_KEY`, `APP_INTERNAL_TOKEN` e `APP_ENV` no Railway; sem isso, o backend pode não subir ou endpoints protegidos podem falhar.
- Configurar `OPENAI_API_KEY` para usar OpenAI real; sem isso, a IA usa fallback local seguro.
- Configurar `OPENAI_MODEL`, `OPENAI_TEMPERATURE` e `OPENAI_MAX_TOKENS` se quiser sobrescrever os defaults; sem isso, o backend usa os defaults do código.
- Manter `AUTO_CREATE_TABLES=false` e `AUTO_RUN_SEEDS=false` após a criação inicial do schema; habilitar sem controle pode alterar banco indevidamente.
- Ajustar `CORS_ORIGINS` para o domínio real do app/site antes de produção; sem isso, navegador/app web pode bloquear chamadas ou ficar permissivo demais.
- Fazer redeploy após alterar variáveis; sem redeploy, o runtime pode continuar usando configuração anterior.
- Validar `/health/live`, `/docs`, sensor manual, leitura manual, dashboard e `/api/ia/chat` após redeploy.
- Não commitar `.env`, chaves, tokens, URLs reais ou arquivos de credenciais.
- Monitorar uso e custos da OpenAI API quando `OPENAI_API_KEY` estiver configurada.

## CORS e hosts

O staging Railway continua compatível porque `TrustedHostMiddleware` ainda permite hosts Railway/customizados. Para produção real, configure `CORS_ORIGINS` com as origens exatas do app/site consumidor, separadas por vírgula. Evite usar origem aberta em produção quando houver credenciais.

## Plano seguro de migrations/Alembic

Estado atual: Alembic está como dependência, mas o fluxo de migrations versionadas ainda não está fechado.

Plano recomendado antes de produção real:

1. Gerar uma migration inicial a partir dos models SQLAlchemy em ambiente local/teste.
2. Revisar manualmente o SQL gerado, índices e constraints.
3. Aplicar primeiro em banco de staging novo, com backup/snapshot quando houver dados.
4. Validar `/health/live`, `/docs`, criação de sensor, leitura manual, dashboard e IA.
5. Manter `AUTO_CREATE_TABLES=false` após a criação inicial.
6. Só aplicar em produção real com janela definida, backup e autorização explícita.

## Rollback

Use rollback de deploy do Railway. Se houver alteração de banco, rollback de código pode não reverter dados/schema; por isso mudanças de banco em produção exigem plano separado.
