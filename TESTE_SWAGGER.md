# Teste via Swagger - Sensores e Leituras

## Acesso

Com o backend rodando:

```text
http://localhost:8000/docs
```

No Railway, usar:

```text
https://SEU-DOMINIO/docs
```

## Criar sensor manual

Endpoint:

```text
POST /api/sensores/manual
```

Autenticação:

```text
X-API-Key: valor configurado em SENSOR_API_KEY
```

Exemplo de corpo:

```json
{
  "id": "sensor_teste_001",
  "cliente_id": "cliente_teste",
  "nome": "Sensor Teste Swagger",
  "tipo": "solo",
  "propriedade": "Fazenda Teste",
  "municipio": "Cidade Teste",
  "estado": "UF",
  "local_especifico": "Talhao 1",
  "latitude": -23.5,
  "longitude": -46.6
}
```

## Enviar leitura manual

Endpoint:

```text
POST /api/sensores/{cliente}/{sensor_id}/leitura-manual
```

Autenticação:

```text
X-API-Key: valor configurado em SENSOR_API_KEY
```

Exemplo:

```text
POST /api/sensores/cliente_teste/sensor_teste_001/leitura-manual
```

Corpo:

```json
{
  "ph": 6.7,
  "umidade": 42.0,
  "temperatura": 24.0,
  "condutividade": 1.1,
  "nitrogenio": 120,
  "fosforo": 35,
  "potassio": 90
}
```

Também são aceitos os nomes usados pelo modelo interno:

```json
{
  "ph": 6.7,
  "soilMoisture": 42.0,
  "temperature": 24.0,
  "electricalConductivity": 1.1,
  "nitrogen": 120,
  "phosphorus": 35,
  "potassium": 90
}
```

## Consultar dados para app/dashboard

Endpoint principal consumido pelo app:

```text
GET /api/dashboard/cliente/{cliente_id}/sensores
```

Exemplo:

```text
GET /api/dashboard/cliente/cliente_teste/sensores
```

Esse endpoint retorna sensores, última leitura e contagem de alertas ativos.

## Endpoint IoT equivalente

Sensores físicos podem enviar para:

```text
POST /webhook/sensor/{sensor_id}
```

Autenticação:

```text
X-API-Key: valor configurado em SENSOR_API_KEY
```

O sensor precisa estar previamente cadastrado.

## Observações de segurança

- Não use `AUTO_CREATE_TABLES=true` em banco real sem autorização.
- Não use `AUTO_RUN_SEEDS=true` em banco real sem autorização.
- Não exponha `SENSOR_API_KEY` no app público.
- Configure `APP_INTERNAL_TOKEN` para testar endpoints com `X-App-Token`.
- Não registre valores reais de segredo em documentação ou memória.

## Ações manuais necessárias

- Confirmar `SENSOR_API_KEY` no Railway e usar o mesmo valor no header `X-API-Key`; sem isso, criação manual de sensor/leitura falha.
- Criar sensor manual antes de enviar leitura manual; sem sensor cadastrado, a leitura é recusada.
- Enviar pelo menos uma leitura manual para popular dashboard e contexto da IA.
- Conferir `GET /api/dashboard/cliente/{cliente_id}/sensores` após enviar leitura; sem leitura, o dashboard pode retornar sensor sem `ultima_leitura`.
- Não commitar `.env` nem valores reais de chave/token.
