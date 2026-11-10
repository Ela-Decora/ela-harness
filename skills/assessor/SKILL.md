---
name: assessor
description: Compara opções de tecnologia, fornecedor ou abordagem numa decisão do planejamento, com critérios, trade-offs, recomendação e estudo gravado; a decisão é do usuário.
argument-hint: "[tema da decisão]"
disable-model-invocation: true
allowed-tools: Bash(python3 "${CLAUDE_PROJECT_DIR}"/.claude/harness/harness.py perfil *), Bash(python3 .claude/harness/harness.py perfil *), Bash(python3 .claude/harness/harness.py estudos *), Bash(python3 .claude/harness/harness.py estado), Bash(date)
---

# Assessor de opções

## Este projeto

!`python3 "${CLAUDE_PROJECT_DIR}"/.claude/harness/harness.py perfil --para assessor`

Se o bloco acima veio como `[shell command execution disabled by policy]` ou começa por `ERRO`, rode `python3 .claude/harness/harness.py perfil --para assessor` pelo Bash antes de qualquer passo; com o perfil ainda inválido, diga o erro ao usuário e pare.

Tema: `$ARGUMENTS`. Sem tema, pergunte qual e pare.

Quatro regras sem exceção:

- Esta skill não escreve em nenhum arquivo da pasta do planejamento e não registra decisão: grava só o estudo. A palavra do usuário entra no arquivo de decisões ou no de ADRs pelo passo 7 da `refinar-documento`.
- Toda opção tem custo declarado; toda afirmação de fato tem fonte com data, ou está marcada `sem fonte`. Número sem fonte não entra.
- A recomendação é uma só, com o custo de errar. "Adiar" é resposta válida do usuário.
- O commit do estudo sai sem pedido, logo depois de gravada a resposta do usuário.

Nos comandos, `harness.py` abrevia `python3 .claude/harness/harness.py`. O estudo é `<AAAA-MM-DD>-<tema em minúsculas, sem acento, com hífens>.md` na pasta de estudos de "Este projeto", copiado do molde [references/estudo.md](references/estudo.md). O parecer e o estudo podem usar termo técnico em qualquer camada: quem os lê é o usuário; a regra da camada vale quando a decisão entrar num documento, e o parecer diz em qual.

## Antes do passo 1: estudo do mesmo tema

Rode `harness.py estudos`. Se um estudo da lista trata do mesmo tema: com `registrada em`, diga onde a decisão está registrada e pare; senão, mostre a linha dele e pergunte se é revisão (passo 1 com o estudo como entrada, sem pesquisa nova a não ser para opção nova) ou estudo novo com outro nome, e espere a resposta.

## Passo 1: enquadramento e despacho

Por `grep`, leia só as linhas que citam o tema: no arquivo de decisões, nas Decisões fixas do `CLAUDE.md` e nos documentos aprovados (a tabela de artefatos do arquivo de pendências diz quais); nas fontes locais, só os arquivos cujo nome cita o tema. Escreva ao usuário, em até 20 linhas:

- a pergunta de decisão, em uma frase;
- os critérios, cada um com a origem (ID de requisito, regra da camada ou `Ruling AAAA-MM-DD`);
- as opções candidatas, de 2 a 5, com "manter como está" ou "adiar a decisão" entre elas quando couber; uma opção só não é estudo: diga isso e pare;
- o que o enquadramento inferiu, marcado `[A CONFIRMAR]`.

Na mesma mensagem, despache o agente `ela-harness:pesquisador-opcoes` em segundo plano, anote a hora do despacho (`date`) e diga em uma linha que a pesquisa corre com prazo de 15 minutos e que, se não voltar nele, basta o usuário dizer "seguir". No despacho, só textos curtos e caminhos:

```
Tema: {tema}
Pergunta: {a pergunta de decisão}
Critérios: {um por linha, com a origem}
Opções: {nome e uma frase cada, uma por linha, na ordem do enquadramento}
Fontes locais: {as pastas das fontes de "Este projeto", uma por linha, ou "nenhuma"}
Prazo: 15 minutos
Hoje: {AAAA-MM-DD}
```

Peça correção do enquadramento; nenhuma outra pergunta nesta mensagem.

## Passo 2: pesquisa

Enquanto o pesquisador corre, crie o estudo pelo molde com o enquadramento: Contexto, Critérios e a lista das opções, ainda sem as seis linhas de cada uma; `Decisão: pendente`. Espere o retorno até 15 minutos a partir do despacho; ao retomar sem o relatório, compare a hora (`date`) com a do despacho. Retorno no prazo: grave-o na seção "Pesquisa" como veio, com a data e a hora do despacho. Sem retorno no prazo, ou com o usuário dizendo "seguir": pare o agente (`TaskStop`), siga com o enquadramento e as fontes locais, marque cada fato sem fonte como `sem fonte` e anote em "Pesquisa" que o relatório entra numa revisão. Opção que o usuário acrescentou na correção do passo 1 ganha um despacho só dela, com o mesmo prazo.

## Passo 3: estudo

Preencha as opções (o que é, prós, contras, custo, riscos, fontes), a tabela de comparação e a recomendação: uma opção, o motivo em uma frase, o custo se errada, e em que camada e arquivo a decisão entra (Ruling no arquivo de decisões, ou ADR no arquivo de ADRs). ADR só se a camada dele já começou (a `Fase` de `harness.py estado`); antes, a decisão entra como Ruling, e o ADR nasce dele quando aquela camada começar. Cada fato cita a fonte do relatório ou o `arquivo:linha` local. O estudo não copia trechos dos documentos do planejamento: cita arquivo e ID. Rode `harness.py estudos` e cole a linha do estudo: tem de vir como `decisão pendente`.

## Passo 4: parecer

Leia agora o molde "Parecer do assessor" de `${CLAUDE_PLUGIN_ROOT}/nucleo/comum/saida.md` e escreva o parecer no chat.

## Passo 5: resposta

Com a resposta do usuário, grave no cabeçalho do estudo `Decisão: <opção> em <AAAA-MM-DD>, registro pendente` e, na seção "Decisão do usuário", a resposta entre aspas e a data. "Adiar" deixa `Decisão: pendente` e grava o motivo na mesma seção. Rode `harness.py estudos` de novo e cole a linha. Registre na seção Medições do arquivo de atritos os tokens, as chamadas e a duração do pesquisador, lidos da notificação do agente. Commit sem pedido: `docs(harness): estudo <tema>`.

Resposta que muda o enquadramento: volte ao passo em que a mudança entra; o estudo é reescrito, não duplicado. O registro da decisão (Ruling ou ADR) é do passo 7 da `refinar-documento`, que lê `harness.py estudos --pendentes` e troca o `registro pendente` do estudo por `registrada em <arquivo>`.
