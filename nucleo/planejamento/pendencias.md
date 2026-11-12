# Pendências: resolver, anotar, perguntar ou abrir

Lido pela skill quando o ciclo encontra trabalho ou decisão que o texto do documento não resolve. O **escopo do ciclo** são os documentos que o ciclo aberto pode mudar: o documento, o pacote ou o lote em refino. A **pendência do ciclo** é a pendência aberta que trouxe o documento ao ciclo, como a do escopo no modo revisão; a primeira aprovação pode não ter. A **nota** é o texto que se acrescenta ao status de uma pendência aberta.

## A escada

Vale o primeiro degrau que couber:

1. Dentro do escopo: resolva agora. Se pede decisão do usuário, pergunte agora, pela ferramenta de opções.
2. Fora do escopo: nota na pendência do ciclo. Sem ela, nota numa pendência aberta com destino no documento atingido (`grep` do caminho no arquivo de pendências) e com o marcador que a pendência nova teria, o do gate ou `antes do`; a primeira que achar. O assunto dela pode ser outro: a pendência é a fila do documento, e a nota entra no escopo do ciclo que a revisar.
3. Sem pendência para a nota: a pergunta.

## A pergunta

Pela ferramenta de opções: o que apareceu, o documento atingido e duas opções, "Abrir pendência" e "Deixar de lado", com a recomendada e o motivo. "Abrir pendência" segue a seção seguinte. "Deixar de lado" grava `harness.py registrar descartada "<o que apareceu> — <o motivo do usuário>"`.

## A pendência nova

Só de três fontes: a resposta "Abrir pendência"; o pedido do usuário no modo revisão sem pendência aberta que cite o documento; o retorno do código sem pendência. Ruling, achado do revisor, fato da pesquisa e pergunta aberta não são fonte: sobem a escada, e a pendência que o ciclo já abriu recebe, por nota, o que vier depois para o mesmo destino. No máximo uma por destino a cada ciclo, com os itens no texto, separados por `; `:

`harness.py registrar pendencia "<texto>" --origem <documento> --destino "<destino>" --causa <causa>`

## A dúvida da entrevista

Fica na árvore do chat ("Fica para a próxima") até a redação. No passo 3, a que é deste documento entra como `[A CONFIRMAR: pergunta aberta: <a pergunta>]`, fora da rodada de confirmação do passo 4; a que é de outro documento sobe a escada a partir do degrau 2. Ela não vira pendência, nem por achado do revisor nem no passo 7: o marcador é o registro.

## A nota

`harness.py registrar nota <prefixo>-NN "<texto>"`. Quando sobra trabalho noutro documento, o texto começa por `resta em <nome do arquivo>: <o quê>`; fora disso, é livre. O arquivo é um documento que existe; o trabalho de um documento que ainda não existe resta no que vai criá-lo, como o módulo que gera a tela, com o nome do que falta no `<o quê>`. O mesmo vale para o destino da pendência. Com mais de uma pendência no escopo, a nota vai para a pendência cuja mudança atingiu o documento; quando nenhuma o atingiu, como no Ruling triado, para a de menor número. Com um lote aberto, o documento do lote não recebe nota `resta em`: o que resta dele se resolve no ciclo.

## O passo 7

A pendência do ciclo sem nota `resta em` desta volta fecha por `harness.py backlog resolver`, depois de resolvidas também as notas de outros ciclos que ela traz para o documento. Com ela, fica aberta, e, quando o que resta está fora do destino, `harness.py backlog destino <prefixo>-NN "<destino>"` troca o destino pelos documentos que restam, com os marcadores do antigo; o destino novo não cita documento do lote aberto. O relato do passo 7 diz o que resta e onde.

## As causas

O `--causa` é obrigatório, desta lista: `entrevista`, a pergunta da rodada; `pesquisa`, o fato que contradiz ou muda uma decisão; `pesquisa-sem-fonte`, o fato que a pesquisa não confirmou; `revisor`, o achado que não se aplica na hora; `ruling`, o Ruling triado no passo 0 do modo revisão; `cascata`, o documento atingido pela decisão de outro; `gerar-modulos`, a entidade ou o termo da geração; `camada-3`, a correção das camadas 1 e 2 pedida pela camada 3; `gate`, o item de atenção do gate; `leitor-frio`, a lacuna do leitor frio; `harness`, a mudança de molde, de método ou de exigência do harness; `triagem`, a revisão em lote depois do gate; `prototipo`, a lacuna do protótipo de tela; `pedido`, o pedido do usuário; `codigo`, o retorno do código; `outro`, nenhuma delas.
