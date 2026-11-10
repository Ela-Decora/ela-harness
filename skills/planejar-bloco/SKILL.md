---
name: planejar-bloco
description: Planeja um bloco do código a partir de uma ficha ou de um pedido em texto livre, até o plano pronto para execução, com a spec aprovada pelo dono. Use quando o dono pedir para planejar uma ficha ou corrigir um defeito, ou quando o bloco status disser /ela-harness:planejar-bloco.
argument-hint: "[<ficha> | texto livre]"
allowed-tools: Bash(python3 .claude/harness/harness.py bloco status *)
---

# Planejar o bloco

## Este bloco

!`python3 .claude/harness/harness.py bloco status --para planejar-bloco`

Se o bloco acima veio como `[shell command execution disabled by policy]`, rode o mesmo comando pelo Bash antes do passo 1.

Pedido: `$ARGUMENTS`. Nos comandos, `harness.py` abrevia `python3 .claude/harness/harness.py`, rodado da raiz da árvore em que a sessão trabalha: a lane, depois do `EnterWorktree`. Fora de lane é o normal desta skill. Numa lane em outro estado que não `planning`, mostre a linha do bloco acima e pare.

## Passos

1. **Na árvore principal.** Sem argumento, rode `harness.py fichas` e pergunte qual abrir, com as urgentes primeiro. Com texto livre, leia [references/ficha.md](references/ficha.md) e crie a ficha. Numa lane em `planning`, siga a Retomada.
2. **A lane.** Rode `harness.py lane abrir <ficha>`, com `--tipo fix` quando a ficha é DEV e o pedido é corrigir um defeito, e entre pelo `EnterWorktree` com o caminho que ele imprime. O texto da ficha fica na pasta das fichas (`harness.py fichas` lista as fichas) e, depois do `lane abrir`, na seção `## Ficha` de `<bloco>/contexto.md`.
3. **Contexto.** Com `Contexto: sim` na ficha, leia [references/contexto.md](references/contexto.md) e siga.
4. **Normal ou curto.** Curto quando a ficha é DEV e o pedido é corrigir um defeito; normal no resto. A primeira linha depois do título da spec é `Caminho: normal` ou `Caminho: curto`.
5. **Spec.** Normal: [references/spec-normal.md](references/spec-normal.md). Curto: [references/spec-curta.md](references/spec-curta.md). Ela vai para `<bloco>/spec.md`.
6. **Aprovação.** Mostre ao dono, em até 10 linhas, o resumo da spec e o caminho com o motivo, e espere a palavra dele no chat. Só a palavra escrita aprova; uma opção da ferramenta de opções não aprova. A decisão do dono que muda o que a spec diz muda a spec antes, e só a palavra dada depois dela vale.
7. **Plano.** Leia [references/plano.md](references/plano.md) e escreva o `<bloco>/plano.md`.
8. **Transição.** Rode `harness.py bloco planejado`, ou `harness.py bloco planejado --curto`, e confirme na guarda. Recusado, corrija pelo quadro das recusas de `plano.md` e rode de novo.
9. **Encadeia.** Invoque a skill `ela-harness:executar-bloco` pela ferramenta Skill, sem perguntar. Com a sessão já compactada, ou com o pedido do dono de outra sessão, entregue no lugar a linha de sessão nova do `ciclo.md` e pare.

## Quando chamar o dono

1. A investigação do bloco curto não acha a causa, ou acha mais de uma: "A investigação não achou a causa do defeito (ou achou N): o que sabe do defeito que ajude, ou prefere replanejar como bloco normal?"
2. O bloco esbarra numa decisão da passagem: abra `harness.py retorno abrir <ID> --tipo decisao --contradiz "<o que o código mostrou>" --evidencia "<a prova>"`, com o ID da passagem, que trava o bloco até o `harness.py bloco desbloquear`, e pergunte: "O bloco depende de uma decisão que a passagem não traz: <a decisão>. Qual é?"
3. O bloco curto cresce, com mais de 3 tarefas ou uma decisão de desenho: "O bloco curto cresceu: <o motivo>. Posso replanejar como bloco normal, com `harness.py bloco replanejar`?"

## Retomada

Numa lane em `planning`, siga do primeiro passo cujo artefato falta: sem `spec.md`, o passo 4; sem a aprovação na linha `**Spec approval:**` do `plano.md`, na conversa nem no resumo da compactação, o passo 6; sem `plano.md`, o passo 7; com tudo, o passo 8.

Depois de um `bloco replanejar`, o último commit do bloco é `chore(<ID>): replaneja: <motivo>`, e a spec e a aprovação de antes dele não contam. Com o `spec.md` sem mudança desde esse commit (o `git status --short` não o lista), siga do passo 4 com o motivo: reescreva a spec, e o bloco curto que cresceu vira normal, com `Caminho: normal`. Com a spec já reescrita, só vale a aprovação dada depois do replanejar; sem ela, o passo 6.
