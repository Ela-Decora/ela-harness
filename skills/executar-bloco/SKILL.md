---
name: executar-bloco
description: Executa o plano do bloco da lane pelo subagent-driven-development, com os agentes do harness, até o bloco pronto para revisão. Use só dentro da lane de um bloco em ready_for_execution ou executing, quando o bloco status disser /ela-harness:executar-bloco, ou com pr quando o PR do bloco voltou com pedido de mudança.
argument-hint: "[correção: <orientação> | pr]"
allowed-tools: Bash(python3 .claude/harness/harness.py bloco status *)
---

# Executar o bloco

## Este bloco

!`python3 .claude/harness/harness.py bloco status --para executar-bloco`

Se o bloco acima veio como `[shell command execution disabled by policy]`, rode o mesmo comando pelo Bash antes do passo 1.

Argumento: `$ARGUMENTS`. Nos comandos, `harness.py` abrevia `python3 .claude/harness/harness.py`, rodado da raiz da árvore em que a sessão trabalha: a lane, depois do `EnterWorktree`. Com a linha `fora de lane: ...`, ou com a segunda linha do `bloco status` (`este bloco está em ...; a skill para ele é ...`), mostre a linha e pare. Exceção: o argumento `pr` com o bloco em `closing` segue pelo passo 1.

## Passos

1. **Exceção da parada.** Com o argumento `pr` e o bloco em `closing`, rode `harness.py bloco corrigir` e siga.
2. **Executando.** Vindo de `ready_for_execution`, rode `harness.py bloco executando`.
3. **Correção.** Só com argumento (`correção: <orientação>` ou `pr`), leia [references/correcao.md](references/correcao.md) e acrescente as tarefas ao plano.
4. **SDD.** Invoque a skill `superpowers:subagent-driven-development` pela ferramenta Skill sobre `<bloco>/plano.md`, com os despachos de [references/despachos.md](references/despachos.md).
5. **Dispensas.** Sem revisão final do branch, sem `superpowers:finishing-a-development-branch` e sem apagar a pasta do plano em `.superpowers/sdd/`, como o `ciclo.md` manda.
6. **Executado.** Rode `harness.py bloco executado`. Recusado pelo ledger, retome o SDD; pela lane com alterações, devolva ao SDD o arquivo da tarefa. Depois, invoque a skill `ela-harness:revisar-bloco` pela ferramenta Skill, sem perguntar; com a sessão já compactada, ou com o pedido do dono de outra sessão, entregue no lugar a linha de sessão nova do `ciclo.md` e pare.

## Quando chamar o dono

1. O bloco esbarra numa decisão da passagem: abra `harness.py retorno abrir <ID> --tipo decisao --contradiz "<o que o código mostrou>" --evidencia "<a prova>"`, com o ID da passagem, que trava o bloco até o `harness.py bloco desbloquear`, e pergunte: "O bloco depende de uma decisão que a passagem não traz: <a decisão>. Qual é?"
2. O SDD chega a uma das quatro paradas que a skill dele nomeia: mostre a parada ao dono, com a pergunta que o SDD escreve.
3. Falta contexto que nem o plano, nem a spec, nem o código trazem: pergunte o que falta, com a dúvida escrita.

## Retomada

Numa lane em `executing`, o SDD retoma pelo ledger da lane: ele dá as tarefas feitas como feitas e segue da primeira que falta. Sem argumento, não refaça os passos 1 a 3.
