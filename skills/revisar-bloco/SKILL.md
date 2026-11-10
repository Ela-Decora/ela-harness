---
name: revisar-bloco
description: Revisa o bloco da lane com o workflow revisao-do-bloco e registra o resultado no revisao.md, até o bloco pronto para finalizar. Use só dentro da lane de um bloco em ready_for_review ou reviewing, ou quando o bloco status disser /ela-harness:revisar-bloco.
argument-hint: "[orientação do dono]"
allowed-tools: Bash(python3 .claude/harness/harness.py bloco status *)
---

# Revisar o bloco

## Este bloco

!`python3 .claude/harness/harness.py bloco status --para revisar-bloco`

Se o bloco acima veio como `[shell command execution disabled by policy]`, rode o mesmo comando pelo Bash antes do passo 1.

Argumento: `$ARGUMENTS`. Nos comandos, `harness.py` abrevia `python3 .claude/harness/harness.py`, rodado da raiz da árvore em que a sessão trabalha: a lane, depois do `EnterWorktree`. Com a linha `fora de lane: ...`, ou com a segunda linha do `bloco status` (`este bloco está em ...; a skill para ele é ...`), mostre a linha e pare.

## Passos

1. **Revisando.** Vindo de `ready_for_review`, rode `harness.py bloco revisando`.
2. **Preparar.** Rode `harness.py revisao preparar`, com `--orientacao "<texto>"` quando há argumento ou orientação do dono no chat. A última linha da saída é o JSON dos `args`.
3. **Workflow.** Chame a ferramenta Workflow com `name: "ela-harness:revisao-do-bloco"` e `args` igual ao JSON do passo 2, passado como objeto, não como texto. Termine o turno e espere o aviso do fim, sem mexer na lane.
   - Com a marca da revisão em andamento no `bloco status` e nenhum workflow lançado nesta sessão, volte ao passo 2.
   - Workflow que falha volta ao passo 2. Na segunda falha pelo mesmo motivo, chame o dono (item 6 do `ciclo.md`).
4. **Registro.** Grave o JSON que o workflow devolveu, inteiro, pelo Write em `.superpowers/revisao/rodada-<n>.json`, com `<n>` a rodada do passo 2, e, se ainda não existe, o `.superpowers/revisao/.gitignore` com `*`, para o resultado ficar fora do git. Depois rode, nesta forma exata:

```
python3 .claude/harness/harness.py revisao registrar .superpowers/revisao/rodada-<n>.json
```

   Recusado, mostre a recusa e confira se o arquivo traz o JSON do workflow inteiro, sem mudança. Se não traz, regrave e rode de novo. Se traz, a recusa é do resultado: volte ao passo 2, como no workflow que falha.

5. **Em aberto.** Sem Crítico nem Importante em aberto, rode `harness.py bloco revisado` e invoque a skill `ela-harness:finalizar-bloco` pela ferramenta Skill, sem perguntar; com a sessão já compactada, ou com o pedido do dono de outra sessão, entregue no lugar a linha de sessão nova do `ciclo.md` e pare. Com algum, leia [references/dono.md](references/dono.md).

## Quando chamar o dono

1. A revisão gasta os 3 consertos de uma execução e sobra Crítico ou Importante em aberto: siga [references/dono.md](references/dono.md).
2. O workflow falha duas vezes pelo mesmo motivo: mostre o erro e pergunte como seguir.
3. Falta contexto que nem a spec, nem o plano, nem o código trazem: pergunte o que falta, com a dúvida escrita.

## Retomada

Numa lane em `reviewing`, rode `harness.py bloco status` e siga do passo 2, ou do 4 se o workflow já devolveu o resultado. Sem argumento, não repita o passo 1.
