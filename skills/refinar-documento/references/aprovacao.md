# Passos 6 e 7: aprovação humana e registro

## Passo 6: aprovação humana

Antes da mensagem fixa, rode `harness.py passo 6 --proximo "usuário revisa <documento> e responde aprovado ou o que mudar"`: ele grava em `Versao-aprovacao` o hash da versão apresentada, guarda uma cópia dela e grava o passo. Depois de cada pedido de mudança, rode de novo antes de reapresentar. Ao retomar uma sessão com `Passo` 6 ou 7 no `STATUS.md`, rode `harness.py versao conferir`, sem argumento (confere o `Pacote` ou o `Documento` do STATUS), antes de qualquer outra coisa; se divergir, mostre o diff ao usuário e espere a decisão dele. Com `Ajuste` no STATUS, siga o ajuste, sem o `versao conferir`. O disco diverge da versão marcada de propósito. O `Proximo` traz o pedido do ajuste.

Mensagem fixa:

> Documento `<caminho>` refinado.
> <N> seções, <M> `[A CONFIRMAR]` (<seção de cada um>).
> Revisão do subagente: <veredito>, <K> rodada(s).
> Pesquisa pendente: <seções>.
> Revise o arquivo e responda "aprovado" ou o que mudar.
> A aprovação vale só para este documento, não para o próximo nem para o gate da camada.

No modo revisão, o resumo das mudanças vem antes da mensagem fixa: o esqueleto de `harness.py versao resumo`, o resumo escrito em `.harness-aprovacao/resumo.md` no molde "Resumo das mudanças" de `.claude/harness/nucleo/nucleo/comum/saida.md`, o `harness.py versao resumo --conferir <arquivo>` até o `OK:` e a legenda de `harness.py legenda --ids-de <arquivo>`, como em [lote.md](lote.md).

Num pacote, a marcação, a mensagem fixa e as três respostas estão em [pacote.md](pacote.md); num lote, em [lote.md](lote.md).

A linha "Pesquisa pendente" só entra quando alguma seção tem `[A CONFIRMAR: pesquisa pendente]`. A resposta aprova só o que foi apresentado. A ferramenta de opções não pede aprovação: a aprovação é a palavra do usuário, escrita no chat. A resposta do usuário depois da marcação é anotada sozinha, pelo hook. Não registre aprovação sem a palavra do usuário.

### Pedido de mudança: três caminhos

Classifique o pedido antes de editar. A classificação é sua; o núcleo só trava a mudança de estrutura no ajuste.

- **Ajuste**: o pedido não reescreve seção, não acrescenta ID nem regra e não muda o sentido de ID ou de regra que já existe. Ele fica no passo 6, sem revisor. Nesta ordem:
  1. `harness.py ajuste --proximo "ajuste de <documento>: <o pedido>; edite, rode harness.py checar e marque de novo com harness.py passo 6"`, que libera a edição no passo 6. O pedido vai em poucas palavras, para o `Proximo` caber nos 200 caracteres.
  2. A edição.
  3. `harness.py checar <documento>`. Um `[A CONFIRMAR]` novo é permitido, e a confirmação dele, a do passo 4, é feita ali mesmo.
  4. O resumo de `harness.py versao resumo --desde-marcada`, escrito e conferido com o `--desde-marcada --conferir <arquivo>`.
  5. `harness.py passo 6 --proximo "usuário revisa <documento> e responde aprovado ou o que mudar"`.
  6. Com a marcação aceita, a linha `Ajuste, sem revisor. Responda "revisar de novo" para mandar ao revisor.`, o resumo depois dela e a mensagem fixa.

  O `passo 6` compara cada documento com a última versão revisada. Seção nova ou removida, ou ID novo ou removido, dá a recusa `o ajuste mudou a estrutura desde a versão revisada`, com uma linha por mudança. A recusa vira volta de correção sobre a edição feita: a edição fica, e o caminho segue do `harness.py passo 3`. O usuário não vê a linha do ajuste: o passo 6 da volta começa pela linha `Correção: revisor no diff, 1 rodada.`.
- **Volta de correção**: o pedido muda o conteúdo além do ajuste. Nesta ordem:
  1. `harness.py passo 3 --proximo "..."`, antes de editar.
  2. A edição e o passo 4.
  3. O passo 5, com o bloco "Volta de correção" de [revisor.md](revisor.md). O revisor recebe só o diff desde a última versão revisada, pelo `harness.py versao resumo --desde-revisada`, e roda uma rodada só.
  4. O relato da rodada. O que sobrar vai ao usuário no passo 6.
  5. O resumo, escrito e conferido como no item 4 do ajuste.
  6. `harness.py passo 6 --proximo "usuário revisa <documento> e responde aprovado ou o que mudar"`.
  7. A linha `Correção: revisor no diff, 1 rodada.`, o resumo depois dela e a mensagem fixa.

  Sem correção do revisor, como no "revisar de novo" sem achado, o `versao resumo --desde-marcada` responde `nenhuma mudança contra a versão marcada`. Então não há resumo a escrever. No lugar dele, depois da linha da correção, vai a frase "nenhuma mudança desde a versão apresentada".
- **Volta de escopo**: o pedido traz assunto novo. Ele segue a escada de `.claude/harness/nucleo/nucleo/planejamento/pendencias.md`, como ela é. O escopo deste documento volta ao passo 2: `harness.py passo 2 --proximo "..."` e a entrevista. O escopo de outro documento vira nota ou pergunta, e a aprovação deste segue.

O pedido misto segue inteiro pelo caminho mais pesado, numa volta só, com o diff inteiro ao revisor. A resposta "revisar de novo" é a volta de correção sobre o que já foi editado, sem edição nova. No pacote e no lote, o pedido que leva um documento por um caminho e outro documento por outro é pedido misto. O pacote e o lote têm um `Passo` só, e vale o caminho mais pesado para todos. A classificação de cada documento, sozinho, fica para a medição.

O resumo é escrito e conferido antes do `harness.py passo 6`. Depois de marcar de novo, a comparação não acharia mais nada.

Medição, a cada pedido: `harness.py registrar medicao "passo 6, <documento>: <ajuste | volta de correção | volta de escopo>" "<valor>"`. Na volta de correção, o valor traz os tokens e a duração do revisor. No ajuste, o valor é `sem revisor`.

## Passo 7: registro

Nesta ordem:

1. `harness.py passo 7 --proximo "commit de <documento> e harness.py fechar"`; se o usuário pediu, ao aprovar, para esperar o commit, `--proximo "commit de <documento> quando o usuário liberar"`, e nada de commit; os itens 2 e 3 rodam mesmo assim. O `passo 7` confere a versão e grava `aprovado`, com a data, na tabela de artefatos. Se a versão divergir, nada é gravado: mostre o diff ao usuário e espere a decisão dele. A recusa "nenhuma mensagem do usuário depois da última marcação" quer dizer que o passo 6 foi remarcado sem o usuário responder: apresente a versão e espere a resposta. Ao aceitar, ele imprime `prova: mensagem das <hora>: «<trecho>»`; se o trecho não parece a resposta do usuário à mensagem de aprovação, pare e pergunte a ele. Num pacote, ele confere cada documento e grava `aprovado` em cada um.
2. Pendências: o que sobrou do ciclo sobe a escada de `.claude/harness/nucleo/nucleo/planejamento/pendencias.md`; cada resolvida, por `harness.py backlog resolver <prefixo>-NN --em <documento> "<como>"` (o `<documento>` é o caminho a partir da raiz, como `CLAUDE.md` ou `<pasta do planejamento>/.../<documento>.md`, ou só o nome do arquivo, quando ele é único no repositório); a pendência do ciclo com nota `resta em` desta volta fica aberta, com o destino trocado por `harness.py backlog destino` (seção "O passo 7" do mesmo arquivo). Confira com `harness.py backlog ids`.
3. `harness.py estudos --pendentes`: estudo com decisão do usuário vira Ruling aqui (ou ADR, no arquivo de ADRs, se o estudo disser) e o `registro pendente` dele vira `registrada em <arquivo>`; ilegível: avise o usuário. Decisões: Ruling (`o quê — por quê — custo se errado`) para decisão que vale além do documento, por `harness.py registrar ruling`, se o registro no ato não a gravou; a aprovação, com a data, quem aprovou e o caminho de cada documento a partir da raiz, que o dossiê do modo revisão procura na linha, por `harness.py registrar aprovacao "<texto>"`; cada abordagem descartada, por `harness.py registrar descartada "<texto>"`; e o trecho do rascunho processado, por `harness.py registrar trecho "<texto>"`. Para cada relato do rascunho que o documento usou: `harness.py registrar relato --id <ID> --status incorporada --em <documento>`.
4. Commit sem pedido: a palavra que aprovou vale como pedido. Na primeira aprovação, o assunto é `docs(planejamento): <documento> camada <N>` (num pacote, `docs(planejamento): pacote <módulo> camada <N>`). Em modo revisão, é `docs(planejamento): revisão do <documento> camada <N> (<IDs das pendências resolvidas>)` (num lote, o assunto de [lote.md](lote.md)), e o corpo diz que é uma nova refinação, dá a data da aprovação anterior de cada documento e diz o que cada pendência mudou, inclusive as parciais e o que resta. Entram só os documentos aprovados e os arquivos de registro, a pasta de pesquisa do documento ou do pacote, se houver, e a linha de atribuição exigida pelo ambiente.
5. Depois do commit, na mesma chamada: `git commit ... && harness.py fechar`. O `fechar` confere que a versão marcada está no HEAD, apaga a marcação e as cópias, fecha o `Documento` e grava no `Proximo` o próximo passo calculado. O `fechar` leva o `STATUS.md` fechado ao commit: faz o amend do commit do documento quando o HEAD é esse commit e nenhuma outra branch, local ou remota, o contém, ou faz um commit `chore`, e imprime `STATUS.md no commit <hash> (amend)` ou `(chore)`. Se o commit falhar, ele diz o motivo, e o commit do `STATUS.md` sai à mão. Diga ao usuário, numa linha, o hash da linha `STATUS.md no commit` e o que fechou.

Se o usuário pediu para esperar, o documento fica em `Passo 7` com a versão marcada, protegida pelo `conferir` até o commit; ao retomar com o `Proximo` "quando o usuário liberar", pergunte antes do commit. Pedido de espera depois do `passo 7`: `harness.py estado set Proximo "commit de <documento> quando o usuário liberar"`. `versao limpar` antes disso, só com a autorização do usuário. Quando o `harness.py proximo`, ou o início da sessão, recomenda `harness.py fechar`, a versão marcada já está no HEAD, como depois de um pull noutra máquina: rode-o sem perguntar e diga ao usuário, numa linha, o que fechou.
