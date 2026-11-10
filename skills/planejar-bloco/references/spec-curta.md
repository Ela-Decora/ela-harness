# A spec do bloco curto

Só para a ficha DEV e o pedido de corrigir um defeito.

1. Invoque a skill `mattpocock-skills:diagnosing-bugs` pela ferramenta Skill e siga da fase 1 à 4, até a causa ter um sinal que falha por causa dela, e pare antes da correção. O teste de regressão e a correção, das fases 5 e 6 dele, são tarefas do plano.
2. Antes do `harness.py bloco planejado`, tire a instrumentação `[DEBUG-...]` e a reprodução descartável. O `git status --short` fica sem nada fora da pasta do bloco.
3. Grave a spec em `<bloco>/spec.md`, com as seções, nesta ordem:
   - `# Spec: <ID> <slug>`, e a linha `Caminho: curto` logo depois;
   - `## Problema`;
   - `## Causa`, com a linha `` Prova: `<comando>` `` e a saída vermelha do comando num bloco de código;
   - `## Correção`, com o código que muda lido antes e citado com `arquivo:linha` e a propriedade usada, como no passo 1 de [spec-normal.md](spec-normal.md);
   - `## Verificação externa`, na forma de [spec-normal.md](spec-normal.md).
4. Sem causa, ou com mais de uma, chame o dono (item 1 de "Quando chamar o dono" do `SKILL.md`).
5. O bloco que cresce, com mais de 3 tarefas ou uma decisão de desenho, vai ao `harness.py bloco replanejar` como normal (item 3).

## Exemplo

````markdown
# Spec: DEV-09 prazo-do-cache

Caminho: curto

## Problema

A consulta de preço chama a distribuidora de novo a cada pedido, mesmo repetida em poucos segundos, e a resposta passa de 3 segundos.

## Causa

O prazo do cache vem da configuração como texto ("60") e é comparado como número, então nunca é maior que zero e a resposta guardada expira na hora.

Prova: `pnpm vitest run cache/prazo.test.ts`

```
FAIL  cache/prazo.test.ts > a resposta guardada vale dentro do prazo
AssertionError: expected undefined to equal { preco: 18.9 }
```

## Correção

Converter o prazo para número ao ler a configuração, com recusa do valor que não é número.

## Verificação externa

nenhuma
````
