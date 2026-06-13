# Biblioteca documental do IZES-AGRO

Esta pasta preserva documentos originais, texto integral extraído, metadados e
relatórios de validação. Não contém resumos, interpretações, chunks, embeddings
ou conteúdo técnico derivado.

## Estrutura

- `fontes/`: inventário, fontes rejeitadas e matriz de cobertura.
- `originais/`: arquivos originais separados por instituição.
- `extraidos/`: texto integral extraído, separado por tema.
- `scripts/`: manifesto de coleta e scripts determinísticos.
- `validacao/`: relatórios de validação de arquivos e extrações.
- `pendencias/`: registros de documentos que exigem ação ou revisão humana.

## Adicionar um documento

1. Confirme a página oficial, instituição, título, autoria, ano e acesso público.
2. Adicione uma entrada em `scripts/documentos.json`.
3. Execute `npm run download`.
4. Execute `npm run validate`.
5. Execute `npm run extract`.
6. Execute `npm run inventory`.
7. Execute `npm run check`.

O arquivo original não deve ser modificado depois do download. Um documento com
o mesmo SHA-256 de outro registro é marcado como duplicado.

## Executar todo o processo

```powershell
npm install
npm run all
```

## Validação

`npm run validate` verifica assinatura PDF, presença de HTML falso, abertura
pelo analisador PDF, tamanho, SHA-256 e duplicidade. `npm run check` verifica
campos obrigatórios, caminhos, arquivos proibidos e consistência do inventário.

Os relatórios são gravados em `validacao/`. Falhas de extração e itens que
dependem de revisão humana são registrados em `pendencias/`.

## Reconstruir inventário

```powershell
npm run inventory
```

O inventário e a matriz são derivados de `scripts/documentos.json`, dos arquivos
originais e dos relatórios de validação. Não edite contagens manualmente.

## Pendências

Consulte:

- `pendencias/documentos_pendentes.csv`
- `validacao/documentos_invalidos.csv`
- `validacao/extracoes_com_falha.csv`
- `validacao/relatorio_qualidade.json`
