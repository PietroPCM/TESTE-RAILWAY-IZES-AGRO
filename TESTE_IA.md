# Teste IA/OpenAI - IZES-AGRO

## Endpoints

```text
POST /api/ia/chat
GET  /api/ia/historico/{cliente_id}
DELETE /api/ia/historico/{cliente_id}
```

Autenticação atual:

```text
X-App-Token: valor configurado em APP_INTERNAL_TOKEN
```

O token é comparado exatamente com `APP_INTERNAL_TOKEN`. Se a variável não estiver configurada em ambiente não local, o endpoint falha fechado sem aceitar prefixos genéricos.

## Variáveis

- `OPENAI_API_KEY`: chave da OpenAI. Se ausente, a IA usa fallback local seguro.
- `OPENAI_MODEL`: modelo usado quando `OPENAI_API_KEY` estiver configurada.
- `OPENAI_TEMPERATURE`: temperatura de geração.
- `OPENAI_MAX_TOKENS`: limite de tokens da resposta.
- `APP_INTERNAL_TOKEN`: token interno exigido no header `X-App-Token`.

Nunca registre valores reais dessas variáveis.

## Testar localmente sem chamada real OpenAI

Use ambiente de teste sem `OPENAI_API_KEY`.

O endpoint `POST /api/ia/chat` classifica a pergunta antes de chamar a OpenAI:

- `fora_escopo`: pergunta geral sem relação com agro. Não chama OpenAI.
- `agro_geral`: dúvida agro válida, como plantio, solo, cultura, praga ou adubação. Pode responder sem sensor.
- `agro_com_dados`: pergunta que pede risco/leitura/sensor/alerta. Usa dados reais quando existirem.

O fallback:

- usa sensores reais carregados do banco configurado quando a pergunta depende de dados;
- usa última leitura disponível;
- usa avaliações agronômicas já calculadas;
- usa alertas ativos;
- responde dúvida agro geral mesmo sem sensor, sem inventar dado real;
- deixa claro que é orientação, não laudo agronômico;
- não recomenda dose exata de fertilizante/corretivo.

Exemplo de pergunta válida:

```text
POST /api/ia/chat?cliente_id=cliente_teste&sensor_id=sensor_teste_001&pergunta=Qual o risco agora?
X-App-Token: app_teste_local
```

Exemplo de pergunta agro geral:

```text
POST /api/ia/chat?cliente_id=cliente_teste&pergunta=Como plantar milho?
X-App-Token: app_teste_local
```

Resposta esperada: orientação curta sobre preparo do solo, época, semente, análise de solo, pragas e irrigação, sem inventar fazenda, sensor ou leitura.

Exemplo de pergunta fora de escopo:

```text
POST /api/ia/chat?cliente_id=cliente_teste&pergunta=Qual capital da Itália?
X-App-Token: app_teste_local
```

Resposta esperada:

```text
Eu sou o assistente agro do IZES. Posso ajudar com sensores, solo, alertas, leituras e manejo da lavoura.
```

## Testar com OpenAI configurada

Depois de configurar `OPENAI_API_KEY` e `OPENAI_MODEL`, usar o mesmo endpoint pelo Swagger.

A resposta enviada para OpenAI usa somente o contexto recebido do backend:

- sensores relevantes;
- última leitura por sensor;
- avaliações calculadas;
- alertas ativos e histórico recente;
- clima/cultura somente quando esses dados existirem no contexto.

Como saber se usou OpenAI:

- `modelo` vem com o modelo configurado, por exemplo `gpt-4-turbo` ou outro valor de `OPENAI_MODEL`;
- `tokens_usados` vem maior que `0`;
- `resposta_estruturada.origem` vem como `openai`;
- `resposta_estruturada.modo` vem como `agro_geral` ou `agro_com_dados`.

Como saber se caiu em fallback:

- `modelo` vem como `fallback-local` quando a OpenAI não foi usada ou falhou;
- `tokens_usados` vem como `0`;
- `resposta_estruturada.origem` vem como `fallback_local`;
- se não houver leitura, alerta ou avaliação em pergunta com sensor, `resposta_estruturada.modo` vem como `agro_com_dados` e a resposta informa que não há leitura real;
- se a pergunta for fora de escopo, `resposta_estruturada.modo` vem como `fora_escopo`.

## Regra de não inventar dados

A IA não pode inventar fazenda, sensor, leitura, cultura, clima, cidade, talhão, histórico, alerta, cliente ou recomendação baseada em contexto ausente.

Se `cliente_id` não existir, o endpoint deve retornar cliente não encontrado.
Se `sensor_id` não existir para o cliente, o endpoint deve retornar sensor não encontrado.
Se não houver leitura, alertas ou avaliações em pergunta que depende de sensor, a resposta deve informar que não há dados suficientes.
Perguntas agro gerais, como `Como plantar milho?`, podem ser respondidas sem sensor como orientação geral.
Mocks, exemplos de Swagger e dados de documentação não contam como dados reais.

## Ações manuais necessárias

- Confirmar `APP_INTERNAL_TOKEN` no Railway e usar o mesmo valor no header `X-App-Token`; sem isso, `/api/ia/chat` retorna erro de autenticação/configuração.
- Confirmar `OPENAI_API_KEY` no Railway; sem isso, `/api/ia/chat` funciona em fallback local, mas não chama OpenAI.
- Conferir `OPENAI_MODEL`, `OPENAI_TEMPERATURE` e `OPENAI_MAX_TOKENS` se quiser controlar modelo/custo/tamanho de resposta; sem isso, valem os defaults do backend.
- Fazer redeploy depois de alterar variáveis; sem redeploy, a API pode continuar com configuração anterior.
- Criar sensor e leitura de teste antes de chamar IA; sem sensores reais para o `cliente_id`, `/api/ia/chat` retorna que não encontrou sensor.
- Monitorar uso e custos da OpenAI API após habilitar a chave.
- Não commitar `.env` nem valores reais de chave/token.

## Limitações

- A IA não deve inventar dados ausentes.
- A resposta é orientação de apoio à decisão, não laudo agronômico.
- Dose exata de fertilizante/corretivo exige cultura, área, análise de solo e validação técnica.
- O histórico de conversas ainda fica em memória.
- O `APP_INTERNAL_TOKEN` precisa ser configurado no Railway antes de testar a IA em staging.
