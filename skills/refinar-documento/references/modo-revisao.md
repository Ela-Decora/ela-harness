# Modo revisão

Vale quando o alvo tem status `aprovado` na tabela de artefatos no passo 0, menos o módulo aprovado com derivados em rascunho, que abre o pacote deles ([pacote.md](pacote.md)): o documento já foi aprovado e volta para uma correção. Os sete passos e a aprovação do usuário continuam; muda o tamanho de cada passo.

- Escopo: as pendências abertas cujo destino cita o documento, ou o pedido do usuário. No passo 0, `harness.py afetados <prefixo>-NN`, com o ID da pendência e os termos dela, mostra as linhas atingidas, já com os IDs que ela cita, que a primeira linha da saída lista, neste documento e nos outros ([pacote.md](pacote.md)); documento aprovado fora do destino que a mudança atinge ganha uma pendência com destino nele, e o escopo não cresce. Diga o escopo na primeira linha do passo 1. A mesma pendência com destino em mais de um documento aprovado abre um `Pacote` com eles, até 6, na ordem em que o destino os cita, um por camada; cada um segue as regras deste arquivo, e a composição está em [pacote.md](pacote.md). O documento depois de `antes do` ou `antes da` só marca a ordem da fila e fica fora do escopo e do pacote, mesmo aprovado.
- Retomada: comece o `--proximo` de cada `harness.py passo` por "modo revisão: ". A partir do passo 5 o status na tabela deixa de ser `aprovado`, e é essa marca que diz o modo depois de `/clear` ou de compactar.
- Passo 0: o bloco "Rulings depois da aprovação de <data>" do dossiê lista todos os Rulings posteriores à aprovação, sem corte, com os prováveis alvos marcados; cada um é triado, marcado ou não: o que toca o documento e a pendência não cobre vira pendência nova, e o escopo não cresce.
- Passo 1: só a mudança pedida e as seções afetadas, sem a pergunta de fronteira. A conferência do resumo vai pela ferramenta de opções, com a pergunta "O resumo e o mapa conferem?" ("os mapas", num pacote, depois da pergunta da composição).
- Passo 2: só se a pendência deixa decisão em aberto; senão, siga para o passo 3.
- Passo 3: só os trechos afetados; o resto do documento não muda.
- Passo 4: `checar` do documento inteiro; confirmação só dos marcadores novos.
- Passo 5: rodada 1 com `Escopo:` (os trechos alterados e o texto da pendência); rodada 2 pela regra de [revisor.md](revisor.md). O `harness.py passo 5` troca `aprovado` por `em-revisao` na tabela de artefatos.
- Passo 6: junto da mensagem fixa, o `git diff` do documento contra a última versão commitada; num pacote, um por documento.
- Passo 7: a pendência marcada como resolvida; o `harness.py passo 7` grava `aprovado` com a data nova.
