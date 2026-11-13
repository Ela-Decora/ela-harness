# Primeiro uso

Este tutorial leva você do ambiente ao commit do primeiro documento, o que o `harness.py proximo` recomendar no seu
projeto, chamado aqui de `<caminho>`. O modelo escreve e roda os comandos do ciclo; você responde e decide. Nada é
aprovado nem commitado sem a sua palavra escrita no chat. `harness.py` abrevia `python3 .claude/harness/harness.py`,
e todo caminho é relativo à raiz do repositório.

## 1. Conferir o ambiente

O harness pede o Python 3.9 ou mais novo, com o pacote `tomli` no 3.9 e no 3.10, o pre-commit ativo no clone, o plugin
instalado para a pasta e a sessão na árvore certa. O [índice](README.md) traz os outros requisitos. Na raiz, rode:

```bash
python3 .claude/harness/harness.py ambiente
```

Você vê uma linha por item, que começa por `OK:`, `AVISO:` ou `FALHA:`. Cada `FALHA` traz o comando que conserta, como
`pip3 install --user tomli` ou `git config core.hooksPath .githooks`: rode-o e confira de novo. O `ambiente` não lê o
perfil e roda mesmo sem o `tomli`. Num worktree, um `AVISO` dá a branch e lembra que o refino vai na árvore principal.

## 2. Abrir a sessão e ler o `Próximo:`

Abra o Claude Code na raiz do repositório (no terminal, `claude`) e aceite o trust da pasta, sem o qual os hooks não
rodam. No terminal, o aviso do hook do início da sessão é uma linha que começa por `Planejamento ·` e termina em
`Próximo: <ação>`. Na extensão do VS Code, o aviso não aparece, e o `CLAUDE.md` do projeto deve mandar o modelo repetir
o `Próximo:` calculado na primeira resposta. Com `FALHA` ou `AVISO` no ambiente, vem uma segunda linha, `Ambiente:`.

## 3. Ver o próximo passo

```bash
python3 .claude/harness/harness.py proximo
```

A primeira linha, `Próximo:`, é a ação recomendada, com o motivo logo abaixo. `Depois:` lista até três ações da fila,
e `Atenção:` junta o que pede cuidado, como os avisos do ambiente. Num projeto que começa, o `Próximo:` aponta um
documento, `/ela-harness:refinar-documento <caminho>`, e esse `<caminho>` é o que você vai refinar aqui. Um `Próximo:` que começa
por `consertar:` traz o conserto que o modelo faz antes de tudo ([Retomar o trabalho](guias.md#retomar-o-trabalho)).

## 4. Abrir o documento

No chat, chame a skill com o caminho que o `Próximo:` deu:

```text
/ela-harness:refinar-documento <caminho>
```

Sem argumento, ela retoma o documento em refino do `STATUS.md` ou, sem nenhum, pergunta se abre o recomendado. As três
skills do harness só rodam quando você as chama. Você vê o modelo gravar o documento no `STATUS.md`, copiar o arquivo
do molde se ele não existe e ler as fontes. O que o modelo faz em cada passo do ciclo está na skill,
[`skills/refinar-documento/SKILL.md`](../skills/refinar-documento/SKILL.md); este é o passo 0 do ciclo.

## 5. Conferir o entendimento

O modelo escreve o que veio de você, o que ele inferiu, o mapa que liga cada seção do molde à fonte dela e os temas.
Depois, na ferramenta de opções, responda "Conferem" ou "Corrigir" a "O resumo e o mapa conferem?", e "Nada fica fora"
ou "Há tema fora" à pergunta de fronteira; a correção ou o tema vai no chat quando o modelo pedir. Na camada sem
`fronteira` no perfil, a mensagem fecha com "O que deste documento entra no MVP e o que fica para depois?", e você
responde em texto. Na skill, é o passo 1 do ciclo.

## 6. Responder as rodadas

Cada rodada traz até quatro perguntas na ferramenta de opções, cada uma ligada a uma seção do molde, com a opção
recomendada primeiro e "(Recommended)" no rótulo. Escolha uma opção em cada; a resposta própria vai em "Other". Na
extensão do VS Code, o texto de "Other" pode não chegar, e então o modelo o pede no chat. A rodada em texto, com as
perguntas numeradas, aceita a resposta curta: `1a 2c`. Depois de cada rodada, você vê a linha "Fica para a próxima".
As rodadas acabam quando não sobra decisão aberta. Na skill, é o passo 2 do ciclo.

## 7. Confirmar cada `[A CONFIRMAR]`

O modelo escreve o documento, marca como `[A CONFIRMAR]` o que inferiu e cola a saída do `harness.py checar`: uma
linha por verificação, com `OK` ou `FALHA`, e a contagem `a-confirmar`. Cada marca vira uma pergunta. Escolha
"Confirmo" para manter o texto sem a marca, "Tirar do documento" para apagar o trecho, ou escreva a correção em
"Other". A marca que cita uma pendência ou "pesquisa pendente" não vira pergunta: o modelo a lista no chat, com o
motivo. Ao fim, o `checar` roda de novo, com a contagem nova. Na skill, são os passos 3 e 4 do ciclo.

## 8. Decidir os itens "Para você"

Um subagente revisor lê o documento em segundo plano, e o modelo avisa isso numa linha. O relato segue o molde
"Relato da revisão" de `nucleo/comum/saida.md`, no plugin: os achados corrigidos, os recusados com o motivo e os itens
"Para você", numerados. Responda pelo número: `1: <sua decisão>`. Sem achados, o relato diz "sem lacunas". A revisão
tem no máximo duas rodadas. Na skill, é o passo 5 do ciclo.

## 9. Aprovar ou pedir mudança

O modelo marca a versão e mostra a mensagem de aprovação: as seções, os `[A CONFIRMAR]` e o veredito da revisão. Leia
o arquivo e responda `aprovado` no chat, ou diga o que mudar; a ferramenta de opções nunca pede aprovação. A aprovação
vale só para este documento, não para o próximo nem para o gate da camada. Um ajuste pequeno fica no passo 6, sem
revisor (`revisar de novo` o chama); a correção volta ao passo 3, e você vê o resumo antes da mensagem nova. Na skill, é o passo 6.

## 10. O commit

Depois do `aprovado`, o modelo registra a aprovação, as pendências e as decisões. Você vê a linha `prova:`, com o
trecho da sua mensagem que valeu como aprovação. A aprovação vale como pedido: o modelo faz o commit e, na mesma
chamada, fecha o ciclo:

```bash
git commit ... && python3 .claude/harness/harness.py fechar
```

Você vê `Fechado: <caminho> (<hash> no HEAD <commit>)` e `STATUS.md no commit <hash> (amend)`: o `STATUS.md` volta a
`Documento: nenhum` e entra no commit. Para segurar o commit, diga ao aprovar que é para esperar: o documento fica no passo 7.

## 11. Limpar a conversa

Antes do próximo documento, rode no chat:

```text
/clear
```

O aviso do início da sessão volta, e a linha `Próximo:` já aponta o que vem. Uma sessão por documento: o `STATUS.md`
guarda o estado, e a conversa anterior não precisa ficar no contexto. Para retomar no meio, numa sessão nova, chame
`/ela-harness:refinar-documento` sem argumento, e o trabalho continua do passo gravado.

## Depois

- [Refinar um pacote](guias.md#refinar-um-pacote): vários documentos juntos pelo ciclo, com uma aprovação e um commit.
- [Fechar uma camada](guias.md#fechar-uma-camada): o gate, quando a fila da fase acaba.
- [Resolver uma recusa](guias.md#resolver-uma-recusa): o que fazer quando uma guarda barra um comando ou um commit.
- A [referência](referencia.md) traz cada comando, skill e agente; a [explicação](explicacao.md), os porquês do desenho.
