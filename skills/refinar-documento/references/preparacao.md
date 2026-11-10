# Passos 0 e 1: preparação e entendimento devolvido

## Passo 0: preparação

1. O `STATUS.md` já veio pelo hook do início da sessão; releia só se ele mudou. Se o `Documento` não é o alvo, grave: `harness.py estado set Documento <alvo> && harness.py passo 0 --proximo "<o que vem>"`. O script recusa trocar o `Documento` enquanto houver `Versao-aprovacao` marcada para outro documento: nesse caso, se o documento marcado está no passo 7, já aprovado, faça o commit dele e o `harness.py fechar`, como diz [aprovacao.md](aprovacao.md), e diga ao usuário (com "quando o usuário liberar" no `Proximo`, pergunte antes); se está no passo 6, pare e pergunte ao usuário se ele aprova ou autoriza o `versao limpar`. Recusa também documento de camada à frente da `Fase`: diga isso ao usuário e pare. Num pacote, pule o `estado set Documento`: a composição e o `estado set Pacote`, que grava o `Documento`, estão em [pacote.md](pacote.md). Pendências e decisões: por `grep`, só as linhas que citam o documento alvo ou os temas das seções dele.
2. Procure o alvo na tabela de artefatos do arquivo de pendências, por `grep` do caminho. Com status `aprovado`, o pedido é de revisão: siga também [modo-revisao.md](modo-revisao.md), que diz o que muda em cada passo. A exceção é o módulo aprovado com derivados em `rascunho`, que abre o pacote deles ([pacote.md](pacote.md)).
3. A pasta da fase no caminho diz a camada; aplique a regra dela, de "Este projeto".
4. Rode `harness.py molde <alvo>`: ele imprime o caminho do molde, achado pelo mapa do perfil. Se o arquivo alvo não existir, copie com `mkdir -p <pasta do alvo> && cp <molde> <alvo>`. Saída `molde não encontrado: ...`: diga isso ao usuário e pare.
5. Leia o molde e o arquivo alvo. Os títulos de seção do molde são o contrato do documento.
6. No rascunho, localize só o trecho pertinente: o cabeçalho com o nome do documento ou, na falta dele, os parágrafos sobre os temas das seções. Leia esse trecho, não o arquivo inteiro. Se o rascunho não existir ou não tratar do documento, anote e diga isso no passo 1; o passo 0 termina mesmo assim.
7. Rode `harness.py dossie` (sem argumento, o documento ou o pacote do `STATUS.md`) e leia uma vez o arquivo que a primeira linha da saída aponta: o contrato do molde, as citações do documento nos aprovados, os IDs delas, os links que ele faz, os termos dele nas decisões, pendências, rascunho, relatórios e fontes, o que o gate da camada vai cobrar e, no documento aprovado ou em revisão, os Rulings depois da aprovação. Leia direto só o que o dossiê aponta: as linhas do rascunho e dos relatórios de pesquisa, só o trecho pertinente, e, num documento sem módulo de origem, a primeira das fontes, que é a voz do cliente. Monte o mapa: para cada seção do molde, a fonte do conteúdo (rascunho, uma das fontes, relatório de pesquisa, decisão registrada, documento aprovado, ou "falta"); os itens do gate entram como exigência da seção. O mapa aponta arquivo e seção, não precisa dos fatos em si.
8. Fatos pontuais (campos, limites, prazos, formatos) que uma seção vai precisar e que o dossiê não traz: antes, procure relatório de pesquisa que já responda; sem ele, despache o `ela-harness:pesquisador-fatos`, como [subagentes.md](subagentes.md) diz, e siga para o passo 1 sem esperar. O mapa já está montado; o fato só preenche a seção no passo 3.

## Passo 1: entendimento devolvido

Antes da primeira pergunta, escreva ao usuário, em até 20 linhas mais uma tabela, duas listas: "O que você disse" (rascunho, decisões, pendências, respostas anteriores) e "O que eu inferi" (vira `[A CONFIRMAR]` se não for tratado). Se o rascunho não existe ou não trata do documento, diga na primeira linha. Em seguida, a tabela do mapa, com duas colunas: seção do molde e fonte (ou "falta"); e a lista de temas que o mapa encontrou, um por linha.

Camada com fronteira do MVP em "Este projeto": logo depois do texto, uma chamada da ferramenta de opções (`AskUserQuestion`) com duas perguntas:

- `header` "Resumo", `question` "O resumo e o mapa conferem?": opções "Conferem (Recommended)", com a descrição "sigo para a entrevista", e "Corrigir", com a descrição "diga a correção na mensagem seguinte".
- `header` "Fronteira", `question` "Algo deste documento fica fora da fronteira do MVP (<a fronteira de "Este projeto">)?": opções "Nada fica fora (Recommended)", com a descrição "todos os temas da lista entram", e "Há tema fora", com a descrição "diga o tema na mensagem seguinte".

"Corrigir" ou "Há tema fora" sem o texto: peça a correção ou o tema no chat, em uma linha, e espere.

Num pacote, a mensagem segue o molde "Resumo do pacote" de `.claude/harness/nucleo/nucleo/comum/saida.md`, e a chamada traz antes a pergunta da composição, como [pacote.md](pacote.md) diz.

Camada sem fronteira em "Este projeto", ou ferramenta indisponível ou recusada pelo usuário: peça a correção do resumo em texto e feche a mensagem com a pergunta fixa, neste texto, e a lista de temas logo abaixo:

> O que deste documento entra no MVP e o que fica para depois?

O usuário responde antes da rodada 1. Temas fora do MVP entram no documento como fora de escopo, não como seção vazia. Nenhuma pergunta de entrevista nesta mensagem. Ao fechar o passo, `harness.py passo 2 --proximo "rodada 1 da entrevista: <temas>"`; a rodada começa em 1.
