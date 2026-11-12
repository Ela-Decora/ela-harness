# Subagentes

Dois agentes, ambos só leitura:

- `ela-harness:pesquisador-fatos`, no passo 0: levanta os fatos que o documento ou o pacote precisa e que as fontes do dossiê não têm.
- `ela-harness:revisor-requisitos`, no passo 5, como [revisor.md](revisor.md) descreve.

## Pesquisa de fatos

Fato é o que se verifica numa fonte (campo de uma API, limite publicado, prazo de um fornecedor); decisão é do usuário e vai para a entrevista. Comparar opções, fornecedores ou tecnologias é do `/ela-harness:assessor`.

1. Antes de despachar, procure cada fato com `grep -rl` nas pastas `pesquisa-*` da pasta de relatórios e nas linhas que o dossiê apontou. Relatório que responde é lido e citado como fonte, sem despacho.
2. Sobrando fato, um despacho por documento ou por pacote, em segundo plano, com o bloco abaixo. Anote a hora com `date` e avise o usuário em uma linha: "Pesquisa do pacote em segundo plano: <N> fatos (<lista curta>), prazo de 15 minutos. Diga "sem pesquisa" para cancelar."
3. Com "sem pesquisa", ou sem retorno em 15 minutos, pare o agente (`TaskStop`): as seções que dependem do fato saem com `[A CONFIRMAR: pesquisa pendente]`. Um segundo despacho no mesmo documento ou pacote, só a pedido do usuário; fato que surgir na entrevista vira `[A CONFIRMAR: pesquisa pendente]`.

```
Pacote: {os documentos, um por linha; num documento sozinho, só ele}
Fatos:
1. {pergunta curta}
Fontes locais: {as pastas da linha de precedência das fontes de "Este projeto", uma por linha}
Relatórios já lidos: {caminhos, para não repetir}
Web permitida para: {os sistemas do cliente de "Este projeto"}
Prazo: 15 minutos, até 25 chamadas de ferramenta
Hoje: {AAAA-MM-DD}
```

## Relatórios de pesquisa

A pasta deles vem na linha "Relatórios de pesquisa" de "Este projeto".

1. Retorno `DONE` ou `DONE_WITH_CONCERNS`: grave o relatório em `<pasta>/pesquisa-<primeiro documento sem .md>-<AAAA-MM-DD>/fatos.md`, com um cabeçalho de quatro linhas (`Pergunta:`, `Fontes lidas:`, `Data:`, `Status:`) e o relatório abaixo. `BLOCKED`: nada é gravado; diga ao usuário o que bloqueou.
2. Fato que contradiz uma decisão registrada segue o registro no ato de [pacote.md](pacote.md): no documento do ciclo, pergunta; fora dele, a escada de `.claude/harness/nucleo/nucleo/planejamento/pendencias.md`.
3. Os tokens, as chamadas e a duração do agente, lidos da notificação, entram por `harness.py registrar medicao "<medição>" "<valor>"`.
4. O relatório entra no commit do documento ou do pacote (passo 7), e os dossiês seguintes o encontram.
