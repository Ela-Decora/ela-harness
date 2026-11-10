---
name: gate-fase
description: Fecha uma camada do planejamento: roda o checklist do gate (script e revisor), apresenta o veredito e registra a aprovação dada pelo usuário.
argument-hint: "[gate, como no STATUS.md]"
disable-model-invocation: true
allowed-tools: Bash(python3 "${CLAUDE_PROJECT_DIR}"/.claude/harness/harness.py perfil *), Bash(python3 .claude/harness/harness.py perfil *), Bash(python3 .claude/harness/harness.py gate *), Bash(python3 .claude/harness/harness.py passagem leitor *)
---

# Gate de fase

## Este projeto

!`python3 "${CLAUDE_PROJECT_DIR}"/.claude/harness/harness.py perfil --para gate-fase`

Se o bloco acima veio como `[shell command execution disabled by policy]` ou começa por `ERRO`, rode `python3 .claude/harness/harness.py perfil --para gate-fase` pelo Bash antes do passo 1; com o perfil ou o `STATUS.md` ainda inválido, diga o erro ao usuário e pare.

Gate: `$ARGUMENTS`. Sem argumento, use o gate da linha "Fase atual" do bloco acima.

Quatro regras sem exceção:

- Só o usuário aprova o gate, com a palavra dele nesta conversa.
- Item que bloqueia só passa com dispensa explícita do usuário, item a item, pelo número e com motivo; o do leitor frio não se dispensa.
- O commit sai sem pedido, logo depois do registro da aprovação; se o usuário pedir para esperar, espere.
- Esta skill não edita os documentos da camada. Correção é pela `/ela-harness:refinar-documento <documento>`; depois, rode o gate de novo.

Nos comandos, `harness.py` abrevia `python3 .claude/harness/harness.py`.

## Passo 1: itens de script

Rode `harness.py gate <gate> --verbose` e cole a saída. Pré-condição que falha sai numa linha só, sem itens: diga o motivo ao usuário e pare.

Com a linha `<n> leitor-frio: FAIL`, rode o teste do leitor frio antes do passo 2, a não ser que a falha seja de itens não certos com os vereditos já confirmados:

1. Sem gabarito do gate, escreva `<caminhos.leitor_frio>/<gate>-<AAAA-MM-DD>.md`, com a data de hoje, pelo molde "Gabarito do leitor frio" do `saida.md` e pelas `[leitor_frio] perguntas` do perfil, e peça ao usuário que confirme o Gabarito. Com gabarito, use o mais recente, já confirmado.
2. Rode `harness.py passagem leitor <gabarito>` em segundo plano, porque ele pode levar até 15 minutos e o Bash em primeiro plano o corta antes; espere o aviso do fim e cole a linha `leitor:`.
3. Compare cada resposta com a Resposta e a Fonte do Gabarito e proponha, por item, `certa`, `errada` ou `não achou`, com uma frase de motivo quando não é `certa`. Com a confirmação ou a correção do usuário, troque cada `a corrigir` pelo veredito.
4. Rode de novo `harness.py gate <gate> --verbose` e cole a saída.

Cada `errada` ou `não achou` confirmado é lacuna. Se o conteúdo falta no planejamento, registre-a por `harness.py registrar pendencia`, com destino antes do <gate>. Se o conteúdo existe e a exportação o deixou de fora, leve ao usuário a correção do contrato de passagem, que se faz numa branch do harness. O gate espera a correção e uma rodada nova do leitor.

## Passo 2: revisor

Se algum item de script deu FAIL sem dispensa do usuário, ou o do leitor frio deu FAIL, não despache o revisor: monte o checklist do passo 3 só com esses itens, diga o que falta, peça a correção, ou "dispenso o N: motivo" para cada um de script, e pare. A dispensa dada aqui vale no passo 4.

Senão (o leitor frio em PASS e nenhum FAIL de script, ou todos os de script dispensados), compare a linha `Assinatura:` da saída do passo 1 com a do último veredito do `revisor-gate` nesta conversa. Igual: reaproveite aquele veredito, sem despacho, e diga isso em uma linha. Diferente, ou sem veredito nesta conversa (sessão nova ou depois de `/clear`): despache o agente `ela-harness:revisor-gate` em segundo plano e avise o usuário em uma linha. No despacho, só caminhos e textos curtos:

```
Gate: {gate}
Fase: {a fase que o gate fecha}
Regra da camada: {a regra dessa fase, do bloco "Este projeto"}
Sistemas do cliente: {a lista do bloco "Este projeto", ou "nenhum"}
Documentos da fase: {os caminhos da tabela de artefatos dentro da pasta da fase, um por linha; a tabela fica no arquivo de pendências, leia por grep}
Decisões: {caminho do arquivo de decisões}
CLAUDE.md: CLAUDE.md
Itens de revisor: {cada item de revisor do checklist, com o número do perfil, um por linha}
```

## Passo 3: checklist

Leia agora o molde "Checklist do gate" de `${CLAUDE_PLUGIN_ROOT}/nucleo/comum/saida.md` e monte o checklist com os itens de script e os do revisor. A evidência dos itens de script vem da saída do passo 1; a dos itens de revisor, da resposta do agente, com `arquivo:linha`.

O item do leitor frio sai na saída do passo 1 como os de script: PASS passa; FAIL bloqueia, e o do leitor frio não se dispensa: só passa com todo item `certa` e a exportação do HEAD igual à do Resultado. A evidência é a linha dele, com o caminho do gabarito. O gabarito segue o molde "Gabarito do leitor frio" do `saida.md`.

## Passo 4: veredito

FAIL se algum item bloqueia; CONCERNS se só há atenção; PASS se não. Peça "aprovado" ou, para cada item que bloqueia, "dispenso o N: motivo"; o do leitor frio não se dispensa. Com item que bloqueia sem dispensa, não aceite a aprovação: diga quais itens ainda bloqueiam.

## Passo 5: registro

Com a palavra do usuário, numa chamada só, os `set` encadeados por `&&`, nesta ordem:

`harness.py estado set <gate> "aprovado em <AAAA-MM-DD>" && harness.py estado set Fase <fase seguinte> && harness.py estado set Documento nenhum && harness.py passo 0 --proximo "<primeiro passo da camada nova>"`

O script só deixa a `Fase` avançar depois do gate aprovado, por isso o gate vem primeiro; a fase nova já sai com o gate dela em `pendente`. No último gate, a `Fase` fica: tire o `set Fase` da cadeia.

No arquivo de decisões, na seção de aprovações: data, gate, a resposta do usuário entre aspas, o veredito ("FAIL com dispensa dos itens N" quando houve dispensa), os itens com atenção e cada dispensa com o motivo. Pendência dispensada continua `aberta`, com o destino trocado pelo que o motivo disser.

Com o item do leitor frio, a linha de aprovação cita o caminho do gabarito, o gabarito entra no commit do gate, e as medições da linha `leitor:` (tempo, tokens, custo, turnos e negações) entram por `harness.py registrar medicao "<medição>" "<valor>"`.

Registre os tokens e a duração do `revisor-gate`, lidos da notificação do agente, por `harness.py registrar medicao "<medição>" "<valor>"`.

## Passo 6: commit

Depois do registro, sem pedido: `docs(planejamento): <gate> aprovado`, com a linha de atribuição exigida pelo ambiente.
