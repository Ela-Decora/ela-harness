# Lote: a revisão de vários aprovados num ciclo só

O lote é a revisão, num ciclo só, dos documentos aprovados que o destino de uma pendência cita, de qualquer camada e sem teto, ou dos que o `harness.py migrar` corrigiu. Passa pelos sete passos, com uma checagem, um revisor por camada e um "aprovado" para todos. Os passos, as duas regras sem exceção e o [modo-revisao.md](modo-revisao.md) continuam os do `SKILL.md`; aqui fica só o que muda. Não é pacote: o pacote é o módulo com os derivados, até 6 ([pacote.md](pacote.md)). Um lote aberto por vez, e ele nunca abre outro sozinho. Os documentos são escritos por você, nunca por subagente.

## Passo 0: composição

1. O lote nasce da pendência do escopo cujo destino cita dois ou mais documentos aprovados. Com um só, segue o modo revisão do documento. O documento depois de `antes do` ou `antes da` só marca a ordem da fila e fica fora do lote, mesmo aprovado.
2. Com mais de uma pendência no escopo, a pergunta "Quais pendências entram agora?" de [modo-revisao.md](modo-revisao.md) é feita uma vez só, aqui, no fim do passo 0, antes de gravar o lote: o núcleo só aceita o `passo 1` com um `Documento`, então ela não espera o passo 1. O lote é o da pendência escolhida; as outras entram só se o destino delas citar documentos do lote, e não acrescentam documento.
3. Um comando mostra o escopo inteiro: `harness.py afetados <prefixo>-NN "<termo>" "<termo>" --gravar`, com o ID de cada pendência do escopo e os termos de cada uma. Ele grava a saída em `.claude/harness/dossie/afetados.txt`, que o revisor lê.
4. O lote leva só o que o destino cita. O que o `afetados` acha fora do destino sobe a escada de `.claude/harness/nucleo/nucleo/planejamento/pendencias.md`, com nota `resta em <documento>: <o quê>` na pendência do lote, e o lote não cresce.
5. Grave: `harness.py estado lote <prefixo>-NN <caminhos do destino> && harness.py passo 0 --proximo "modo revisão: lote <prefixo>-NN ..."`. Os caminhos podem vir em qualquer ordem: o núcleo ordena por camada e, dentro dela, pela ordem em que o destino cita. O primeiro da lista vira o `Documento`.
6. O núcleo recusa o documento que o destino não cita, com `recusado: <documento> não está no destino da <prefixo>-NN`, e o que não está aprovado, com `recusado: <documento> não está aprovado; o lote só revisa aprovados`, uma linha por documento, e a pendência fora do backlog ou fechada. Com `Lote` aberto, `harness.py backlog destino` e `harness.py registrar nota` com `resta em <documento>` recusam o documento do lote, com `recusado: <documento> está no lote aberto; o que resta dele se resolve neste ciclo`.
7. `harness.py dossie`, sem argumento, monta as fontes do lote. Leia o molde de cada tipo e o arquivo do dossiê.

## Passos 1 a 5

- Passo 1: uma mensagem para o lote, no molde "Resumo do lote" de `.claude/harness/nucleo/nucleo/comum/saida.md`, e uma chamada da ferramenta de opções com até quatro perguntas: a pergunta de qual pendência abre o lote já foi feita no passo 0 e não se repete; vêm primeiro as de cada Ruling triado, quando houver ("O Ruling de <data> entra agora?", em [modo-revisao.md](modo-revisao.md)), e depois `header` "Composição", "A composição do lote confere?". O que passa de quatro perguntas segue em chamada seguinte. A fronteira do MVP não entra.
- Passo 2: uma rodada para o lote inteiro; a mesma decisão em dois documentos vira uma pergunta só. Depois de cada rodada, o registro no ato ([pacote.md](pacote.md)).
- Passo 3: os documentos na ordem do lote, só os trechos afetados, como no modo revisão.
- Passo 4: `harness.py checar`, sem argumento, confere o lote. A confirmação dos marcadores novos vai em chamadas de até 4 perguntas.
- Passo 5: `harness.py versao resumo` grava um diff por camada em `.claude/harness/dossie/diff-camada-<N>.diff`. Um despacho do `ela-harness:revisor-requisitos` por camada, todos em paralelo e em segundo plano, cada um com o bloco "Lote" de [revisor.md](revisor.md). O relato junta as rodadas, com o onde começando pelo documento. A rodada 2 segue a regra de [revisor.md](revisor.md), só nas camadas em que a correção reescreveu uma seção ou acrescentou ID ou regra; antes dela, rode `harness.py versao resumo` de novo, para o `Diff:` da camada refletir a correção.

## Passo 6: aprovação do lote

Nesta ordem:

1. `harness.py passo 6 --proximo "usuário revisa o lote <prefixo>-NN e responde aprovado ou o que mudar"` guarda a cópia de cada documento e grava em `Versao-aprovacao` o hash do manifesto.
2. `harness.py versao resumo` imprime o esqueleto das mudanças. Escreva o resumo em `.harness-aprovacao/resumo.md`, no molde "Resumo das mudanças" de `saida.md`, e rode `harness.py versao resumo --conferir .harness-aprovacao/resumo.md` até o `OK:`; o `FALTA:` e o `SOBRA:` dizem a seção que ficou errada.
3. `harness.py legenda --ids-de .harness-aprovacao/resumo.md` dá o título de cada ID e o significado de cada sigla, para a primeira aparição de cada um. Passe o resumo pelo arquivo, nunca colado entre aspas nem por `$(cat ...)`: a crase e o `$` do Markdown viram comando no shell, e o `$(...)` pede permissão a cada vez.
4. Mostre o resumo e, depois dele, a "Mensagem de aprovação do lote" de `saida.md`.

Respostas:

- "aprovado": vale para o lote apresentado; siga para o passo 7.
- "mudar <documento>: <o quê>": um dos três caminhos de [aprovacao.md](aprovacao.md), com o documento classificado sozinho. Edite só esse documento. Na volta de correção, `harness.py versao resumo --desde-revisada` grava o `Diff:` de cada camada que mudou desde a versão revisada. Vai o revisor de cada uma dessas camadas, e não só o da camada do documento: um ajuste anterior noutra camada também passa pelo revisor antes de virar versão revisada. O resumo vem antes do `harness.py passo 6` de novo, e a mensagem fixa depois dele. Na nova marcação, só o hash desse documento muda.
- "tirar <documento> do lote": a resposta vale como a autorização para `harness.py versao limpar`; depois, `git restore <documento>`, a linha dele na tabela de artefatos de volta a `aprovado` com a data anterior, que vem de `git show HEAD:<caminho do backlog>` (no lote de migração a tabela não mudou), `harness.py estado lote --tirar <documento> && harness.py passo 6 --proximo "<o que vem>"` e o resumo de novo. O documento fica fora da aprovação, a pendência continua aberta com o destino citando-o, e ele volta numa revisão própria. O lote nunca fica vazio: o último segue sozinho. Tirar o único documento é desistir do lote: `harness.py versao limpar`, `git restore <documento>`, a linha da tabela como acima e `harness.py estado set Documento nenhum && harness.py passo 0 --proximo "<o que vem>"`; no lote de migração, avise que o próximo `harness.py migrar` o reabre.
- "ver <documento>": não é resposta à aprovação. `harness.py versao ver <documento> <n>` mostra a seção alterada `n` (a 1, por padrão), com a legenda dos IDs; "mais" mostra a seguinte, e a aprovação segue esperando.

Aprovação parcial ("aprovo A e B") não existe: responda com as formas acima. Ao retomar no passo 6 ou 7, `harness.py versao conferir`, sem argumento, confere o lote e diz qual documento divergiu. Com `Ajuste` no STATUS, siga o ajuste, sem o `versao conferir`.

## Passo 7: registro do lote

`harness.py passo 7` confere cada documento e grava `aprovado` em cada um; se um diverge, nada é gravado. Depois, como num documento sozinho ([aprovacao.md](aprovacao.md)): as pendências resolvidas por `harness.py backlog resolver <prefixo>-NN --em <documento> "<como>"`, e a pendência com nota `resta em` desta volta fica aberta, com o destino trocado por `harness.py backlog destino <prefixo>-NN "<destino>"` pelo que resta fora do lote, e a próxima volta só começa pelo `harness.py proximo` e pela palavra do usuário. Commit sem pedido, um por lote: `docs(planejamento): lote <prefixo>-NN, <N> documentos (<IDs das pendências resolvidas>)`, com `1 documento` no singular, com o corpo no formato de revisão de [aprovacao.md](aprovacao.md) e a data da aprovação anterior de cada documento. Depois do commit, na mesma chamada: `git commit ... && harness.py fechar`, que confere cada documento no HEAD, apaga a lista do lote e tira o `Lote`.

## O lote de migração

O `harness.py migrar --de <versão>` abre o lote dos documentos que ele corrigiu, sem pendência, com `Lote: migração v<de>→v<para>`. Os passos 0 a 3 são dele; o `Proximo` manda começar pelo passo 4, `harness.py checar`. Comece o `--proximo` de cada `harness.py passo` por "lote de migração: ".

- Passo 4: `harness.py checar`, sem argumento. Não há marcador novo a confirmar.
- Passo 5: o despacho do revisor traz `Critério: forma` e `Escopo: migração v<de>→v<para>`, e o `Diff:` da camada. Ele confere só a forma: legível, fiel ao molde, sem perda de conteúdo e sem citação quebrada.
- Passo 6: como no lote de pendência. O "tirar" vale também aqui.
- Passo 7: não há pendência a resolver. Os documentos seguem `aprovado`, com a data de antes, e o `harness.py passo 7` grava sozinho a linha `migração v<de>→v<para>: <N> documentos` no arquivo de decisões. O assunto do commit é `docs(planejamento): migração v<de>→v<para>, <N> documentos`, com `1 documento` no singular, como na linha do arquivo de decisões.
