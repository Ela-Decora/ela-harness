---
name: finalizar-bloco
description: Finaliza o bloco da lane: confere o que a spec promete, guia os itens manuais e abre o PR pelo harness. Use só dentro da lane de um bloco em ready_for_closure, ou quando o bloco status disser /ela-harness:finalizar-bloco.
argument-hint: "[resumo do PR]"
allowed-tools: Bash(python3 .claude/harness/harness.py bloco status *)
---

# Finalizar o bloco

## Este bloco

!`python3 .claude/harness/harness.py bloco status --para finalizar-bloco`

Se o bloco acima veio como `[shell command execution disabled by policy]`, rode o mesmo comando pelo Bash antes do passo 1.

Argumento: `$ARGUMENTS`. Nos comandos, `harness.py` abrevia `python3 .claude/harness/harness.py`, rodado da raiz da árvore em que a sessão trabalha: a lane, depois do `EnterWorktree`. Com a linha `fora de lane: ...`, ou com a segunda linha do `bloco status` (`este bloco está em ...; a skill para ele é ...`), mostre a linha e pare.

## Passos

1. **Promessa da spec.** Invoque `superpowers:verification-before-completion` sobre o que a spec do bloco promete, com a saída de `harness.py verificar --momento finalizar` e de `harness.py aceitacao conferir` como evidência. A última linha do `aceitacao conferir` decide o passo seguinte: `ACEITACAO OK`, o passo 3; `ACEITACAO MANUAL`, o passo 2. Com a verificação vermelha, ou com outra última linha (`ACEITACAO PENDENTE` ou uma recusa), não siga: chame o dono (item 4 de Quando chamar o dono).
2. **Item manual.** Com `ACEITACAO MANUAL`, siga [references/manual.md](references/manual.md), um item por vez, até a última linha do `aceitacao anotar` dar `ACEITACAO OK`; então, o passo 3.
3. **Finalizar.** Escreva o corpo do PR por [references/corpo.md](references/corpo.md) e grave-o pelo Write em `.superpowers/pr/<ID>.md`, com o `.superpowers/pr/.gitignore` (`*`) se ele falta, sem `cp` nem redirecionamento do shell; o arquivo de um `finalizar` anterior é regravado, e o Write recusa o que a sessão não leu: leia-o antes de regravar. Rode `harness.py bloco finalizar --corpo .superpowers/pr/<ID>.md`, com `--resumo "<texto>"` quando há argumento, e peça a confirmação da guarda. Recusado, corrija (a recusa do corpo, no arquivo) e rode de novo; na segunda recusa pelo mesmo motivo, chame o dono.
4. **Fim.** Termine com o link do PR e estas duas linhas, como estão:

```
depois do merge: harness.py lane fechar <ID>, de uma sessão aberta na árvore principal ou pelo terminal como última ação
se o PR voltar com pedido de mudança: /ela-harness:executar-bloco pr
```

## Quando chamar o dono

1. O `bloco finalizar` recusa duas vezes pelo mesmo motivo: mostre a recusa e pergunte como seguir (item 6 do `ciclo.md`).
2. Um item manual falha, ou o dono não consegue fazê-lo: mostre o item e pergunte se anota `falhou` ou se o bloco volta.
3. Falta contexto que nem a spec, nem o plano, nem o código trazem: pergunte o que falta, com a dúvida escrita.
4. A verificação sai vermelha, ou o `aceitacao conferir` termina em outra linha que não `ACEITACAO OK` nem `ACEITACAO MANUAL`, no passo 1: mostre a saída e pergunte como seguir. Em `ready_for_closure`, o `bloco corrigir` não vale; a falha que vem de um conflito com a passagem sai pelo `retorno abrir` de [references/dono.md](../revisar-bloco/references/dono.md).

## Retomada

Numa lane em `ready_for_closure`, rode `harness.py bloco status` e siga do passo 1; o item manual já anotado no `aceitacao.md` não se repete. Em `closing`, com ou sem PR aberto, e depois de `closing gravado, mas <passo> falhou`, rode `harness.py bloco finalizar` sem o `--corpo`, sempre: o corpo vem do commit `closing`, e a retomada é idempotente (empurra de novo e troca o corpo do PR ou o abre). Depois siga para o passo 4. Depois de uma correção pedida no PR, o bloco volta a `ready_for_closure` e passa pelo passo 3 inteiro, com o corpo escrito de novo.
