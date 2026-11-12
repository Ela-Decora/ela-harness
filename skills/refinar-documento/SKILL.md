---
name: refinar-documento
description: Refina um documento de planejamento a partir do rascunho e do molde, em entrevista por rodadas, até a aprovação do usuário.
argument-hint: "[caminho do documento na pasta do planejamento]"
disable-model-invocation: true
allowed-tools: Bash(python3 "${CLAUDE_PROJECT_DIR}"/.claude/harness/harness.py perfil *), Bash(python3 .claude/harness/harness.py perfil *)
---

# Refinar documento de planejamento

## Este projeto

!`python3 "${CLAUDE_PROJECT_DIR}"/.claude/harness/harness.py perfil --para refinar-documento`

Se o bloco acima veio como `[shell command execution disabled by policy]` ou começa por `ERRO`, rode `python3 .claude/harness/harness.py perfil --para refinar-documento` pelo Bash antes do passo 0; com o perfil ainda inválido, diga o erro ao usuário e pare.

Documento alvo: `$ARGUMENTS`, caminho relativo à raiz, dentro da pasta do planejamento. Sem argumento, use os documentos em refino do `STATUS.md` (o `Pacote`, ou o `Documento`); se não houver, rode `harness.py proximo` e pergunte, pela ferramenta de opções, se abre o recomendado, com até 3 alternativas da fila; se o recomendado não for um documento, diga o comando ao usuário e pare. O caminho com `<pasta>` ou `<documento>` vem de uma pendência: proponha o caminho pelo texto dela e pelos documentos irmãos, e confirme com o usuário antes do passo 0.

Pacote: um módulo e as entidades e telas que ele cria, ou os aprovados que uma pendência cita no destino, passam juntos pelos sete passos, com uma aprovação para todos. Leia [references/pacote.md](references/pacote.md) ao abrir ou retomar um pacote; cada passo abaixo diz o que muda.

Camada 3: documento na pasta da fase que contém o `documento` da seção `[der]` do perfil segue também [references/camada-3.md](references/camada-3.md), lido ao abrir ou retomar o documento.

## Os sete passos e quando cada um termina

| Passo | Termina quando |
|---|---|
| 0 Preparação | `Documento` gravado, ou o `Pacote`; arquivo alvo existe (copiado do molde se não existia); dossiê lido; trecho do rascunho localizado, ou ausência dele anotada; mapa "seção do molde → fonte" montado |
| 1 Entendimento devolvido | o usuário confirmou ou corrigiu o resumo "dito × inferido" e respondeu a fronteira do MVP |
| 2 Entrevista em rodadas | fronteira vazia e toda seção do molde com fonte: resposta do usuário, rascunho, referência ou `[A CONFIRMAR]` declarado |
| 3 Versão refinada | arquivo escrito com todas as seções do molde, sem comentário `<!-- -->`, inferências marcadas |
| 4 Checagem e confirmação | `harness.py checar` rodado e saída colada: `OK` em placeholders, títulos, IDs, IDs citados e adjetivos vagos; cada `[A CONFIRMAR]` confirmado, tirado ou corrigido pelo usuário, ou deixado de fora com motivo |
| 5 Revisão por subagente | veredito "Sem lacunas" ou cada achado corrigido, recusado com motivo ou posto em "Para você"; no máximo 2 rodadas |
| 6 Aprovação humana | o usuário escreveu que aprova este documento, ou o pacote inteiro |
| 7 Registro | `harness.py passo 7` gravou `aprovado`; pendências e decisões atualizadas; commit feito sem pedido, com `harness.py fechar` na mesma chamada |

Três regras sem exceção: só o usuário aprova (passo 6), com a palavra dele escrita no chat, nunca por uma opção da ferramenta de opções; o commit sai só depois dessa palavra, no passo 7, sem nova pergunta, a menos que o usuário peça para esperar; e pendência nova só com a resposta do usuário à pergunta da escada de `.claude/harness/nucleo/nucleo/planejamento/pendencias.md`, ou com o pedido dele no modo revisão: Ruling, achado do revisor e pergunta aberta não abrem pendência, e o que levam a outro documento vai como nota na pendência aberta de mesmo destino, quando há uma. Ao retomar um documento, leia no `STATUS.md` o passo em que parou e continue dele, mesmo com o arquivo pronto.

Ferramenta de opções: a resposta livre ("Other") nem sempre chega com o texto. Opção que pede texto, como "Corrigir" ou "Há tema fora", ou "Other" sem texto: peça o texto no chat, em uma linha, e espere a resposta antes de seguir.

O `STATUS.md` é a única memória que sobra depois de `/clear` ou de compactar. Ao fechar cada passo, grave-o com `harness.py passo <passo seguinte> --proximo "<o que vem>"`; rodada nova, com `--rodada <r>`. O `passo` grava também o status do artefato no backlog. `estado set` fica para `Documento`, `Pacote`, `Fase`, os gates e a espera do commit no `Proximo`. Comandos encadeados por `&&` numa chamada só, nunca em chamadas paralelas; nos exemplos, `harness.py` abrevia `python3 .claude/harness/harness.py`. Texto que começa com `-` vai com `=`: `--proximo=-texto`.

Dúvida que muda o escopo ou a ideia principal (a lista de "Este projeto"): pare e pergunte antes de escrever. Dúvida menor: escreva e marque `[A CONFIRMAR: motivo]`.

Fontes que divergem: vale a precedência de "Este projeto". Divergência que muda o escopo: pergunte. Divergência menor: siga a precedência e anote `[A CONFIRMAR: <fonte> diz <outra coisa>]`.

Nomes: nos documentos, aplique as trocas de nome de "Este projeto", também nos títulos; a checagem do passo 4 já as desconta.

Cada passo tem aqui um resumo. O detalhe está no arquivo de `references/` indicado: leia-o ao entrar no passo, também ao retomar depois de `/clear` ou de compactar.

## Passo 0: preparação

Grave o alvo com `harness.py estado set Documento <alvo> && harness.py passo 0 --proximo "<o que vem>"`; num pacote, no lugar dele, `estado set Pacote "<lista>"`. Arquivo ausente vem do molde que `harness.py molde <alvo>` aponta; alvo com status `aprovado` na tabela de artefatos abre o modo revisão, menos o módulo aprovado com derivados em rascunho, que abre o pacote deles ([references/pacote.md](references/pacote.md)), como o `harness.py proximo` já indica. `harness.py dossie` grava as fontes num arquivo: leia o molde, o alvo, o dossiê e só as linhas do rascunho e dos relatórios que ele aponta, e monte o mapa "seção do molde → fonte". Fato que nenhuma fonte responde vai para o `ela-harness:pesquisador-fatos`. Leia [references/preparacao.md](references/preparacao.md).

## Passo 1: entendimento devolvido

"O que você disse", "O que eu inferi", a tabela do mapa e a lista de temas. A conferência do resumo e a fronteira do MVP vão numa chamada da ferramenta de opções quando "Este projeto" traz a fronteira da camada; senão, em texto, com a pergunta fixa. Num pacote, o molde "Resumo do pacote" e a pergunta da composição. Leia [references/preparacao.md](references/preparacao.md).

## Passo 2: entrevista em rodadas

Cada rodada é uma chamada da ferramenta de opções, com até 4 perguntas da fronteira das decisões e a resposta recomendada primeiro; a reserva em texto segue o molde "Rodada da entrevista" de `${CLAUDE_PLUGIN_ROOT}/nucleo/comum/saida.md`. Depois de cada rodada, o registro no ato, por `harness.py registrar`; num pacote, a fronteira do pacote inteiro. Informação nova da conversa, que não é resposta, Ruling nem pendência, vai para o rascunho por `harness.py registrar relato`. Leia [references/entrevista.md](references/entrevista.md).

## Passo 3: versão refinada

Começa quando a pesquisa do documento voltou, ou quando o usuário escolheu escrever sem ela. No arquivo alvo, na ordem e com os títulos do molde; inferência como `[A CONFIRMAR: motivo]`; cheiros de ambiguidade em [references/cheiros-de-ambiguidade.md](references/cheiros-de-ambiguidade.md). Num pacote, todos os documentos, na ordem da lista. Leia [references/redacao.md](references/redacao.md).

## Passo 4: checagem e confirmação

`harness.py checar` (sem argumento, o documento ou o pacote) com a saída colada; a confirmação dos `[A CONFIRMAR]` pela ferramenta de opções; `checar` de novo; `harness.py passo 5`. Leia [references/redacao.md](references/redacao.md).

## Passo 5: revisão por subagente

O `ela-harness:revisor-requisitos`, em segundo plano: rodada 1 sempre; rodada 2 só se a correção reescreveu uma seção ou acrescentou ID ou regra; não há rodada 3. Relato no molde "Relato da revisão" de `${CLAUDE_PLUGIN_ROOT}/nucleo/comum/saida.md`. Num pacote, um despacho para todos. Leia [references/revisor.md](references/revisor.md).

## Passo 6: aprovação humana

`harness.py passo 6` marca a versão antes da mensagem fixa. Ao retomar no passo 6 ou 7, `harness.py versao conferir` antes de tudo. Num pacote, a marcação vale para a lista, e as respostas são "aprovado", "mudar <documento>" e "tirar <documento> do pacote". Leia [references/aprovacao.md](references/aprovacao.md).

## Passo 7: registro

`harness.py passo 7` confere a versão e grava `aprovado`; depois, pendências, estudos e decisões; o commit, sem pedido, com a pasta de pesquisa do documento, seguido de `harness.py fechar`. A linha `prova:` do `passo 7` diz qual mensagem valeu como aprovação. Num pacote, `aprovado` em cada documento e um commit para o pacote. Leia [references/aprovacao.md](references/aprovacao.md).

## Modo revisão

Documento já aprovado que volta para correção: os mesmos passos, cada um só no escopo da pendência ou do pedido do usuário, com as linhas atingidas dadas por `harness.py afetados`. Leia [references/modo-revisao.md](references/modo-revisao.md).

## Subagentes

O `ela-harness:pesquisador-fatos`, no passo 0, e o `ela-harness:revisor-requisitos`, no passo 5, ambos só leitura; os relatórios de pesquisa ficam na pasta de "Este projeto". Leia [references/subagentes.md](references/subagentes.md).
