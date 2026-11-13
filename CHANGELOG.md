# Changelog

## v0.4.2 — 2026-11-12

Um pedido pequeno na aprovação não reabre mais o ciclo inteiro: o ajuste fica no passo 6, sem revisor, e o núcleo trava só a mudança de estrutura. Junto vêm o tratamento do relatório de pesquisa que chega atrasado, o pacote do módulo calculado pelo núcleo e a espera do commit do gate guardada no STATUS.md.

### O que mudou desde a 0.4.1

- O `harness.py ajuste [--proximo "<texto>"]`, só no planejamento, abre o ajuste no passo 6: grava o campo opcional `Ajuste: aberto` no STATUS.md, logo depois do `Documento` (ou do `Pacote` ou do `Lote`), e o `Proximo`, que sem o `--proximo` é `ajuste: edite, rode harness.py checar e marque de novo com harness.py passo 6`. Imprime `Ajuste = aberto; Proximo = <texto>`. Recusa, com 1 e nada gravado, `recusado: o ajuste só vale no passo 6`, `recusado: nenhuma versão marcada; rode harness.py passo 6` e, uma linha por documento, `recusado: nenhuma versão revisada no histórico de <documento>; o pedido volta ao passo 3`. Com o `Ajuste` aberto, a guarda libera a edição dos documentos em refino no passo 6; o passo 7 não a libera. A mensagem de negação da guarda, nos documentos com versão em aprovação, agora cita o comando: `<documento> tem versão em aprovação (passo <n>); para mudar, rode harness.py passo 3 (ou passo 2) ou, num ajuste, harness.py ajuste, edite e marque de novo com harness.py passo 6`. O campo sai quando o `passo 6` marca de novo, num `passo` de 0 a 5, no `fechar`, num `Documento` novo e no `versao limpar`.
- O `harness.py passo 6` com o `Ajuste` aberto confere a estrutura antes de marcar: compara cada documento em refino com a última versão revisada do histórico. Seção de nível 2 ou 3 nova ou removida, ou ID definido que entrou ou saiu, é recusa, com 1, sem gravar e sem desfazer a edição, com `recusado: o ajuste mudou a estrutura desde a versão revisada; é volta de correção: rode harness.py passo 3` e uma linha por mudança: `<documento>: seção nova «<título>»`, `<documento>: seção removida «<título>»`, `<documento>: ID novo <ID>` ou `<documento>: ID removido <ID>`. O ID cuja linha de definição mudou não trava. Sem nada disso, o passo marca a versão como de ajuste e tira o `Ajuste` na mesma escrita. O `passo 7` com o `Ajuste` aberto recusa com `recusado: ajuste aberto; marque de novo com harness.py passo 6`, e o `passo 3` o tira.
- O histórico do `versao` rotula as versões: a marcação de ajuste entra como `NN-<AAAA-MM-DD>T<HHMM>-<12 hexadecimais>-ajuste.md`, e o `harness.py versao historico` imprime `  ajuste` no fim da linha dela; a entrada sem o sufixo é a "revisada", e as de antes seguem válidas. A marcação sem o `Ajuste` de uma versão igual à última entrada de ajuste, como no "revisar de novo" sem edição, renomeia essa entrada para revisada, em vez de não entrar pela deduplicação. O `harness.py versao resumo --desde-revisada`, também com `--conferir <arquivo>`, compara com a última versão revisada de cada documento, sem contar os ajustes, e grava o diff de cada camada para o revisor; é exclusivo com o `--desde-marcada`. Sem versão revisada, recusa com `recusado: nenhuma versão revisada no histórico de <documento>`. O resumo e o `ver` que o usuário lê seguem com o `--desde-marcada`.
- A `/ela-harness:refinar-documento` trata o pedido de mudança do passo 6 por três caminhos, no `aprovacao.md`, no lugar do retorno ao passo 3 em todo caso. O ajuste, quando o pedido não reescreve seção, não acrescenta ID nem regra e não muda o sentido de ID ou de regra que já existe, fica no passo 6, sem revisor: `harness.py ajuste`, a edição, `harness.py checar`, o resumo do `versao resumo --desde-marcada`, o `harness.py passo 6` e a mensagem fixa, depois da linha `Ajuste, sem revisor. Responda "revisar de novo" para mandar ao revisor.`. A correção volta ao passo 3 e dá ao revisor só o diff desde a última versão revisada, em uma rodada, e o que sobrar vai ao usuário; o passo 6 dela começa pela linha `Correção: revisor no diff, 1 rodada.`. O despacho leva a linha `Volta: correção`, que o agente `revisor-requisitos` lê como o pedido do usuário no `Escopo:`, e o `revisor.md` ganha o bloco "Volta de correção". O escopo segue a escada do `pendencias.md`: o do documento volta ao passo 2, e o de outro documento vira nota ou pergunta. O pedido misto segue pelo caminho mais pesado, o "revisar de novo" é uma correção sobre o que já foi editado, e no pacote e no lote cada documento do "mudar" é classificado sozinho. A medição de cada pedido vai por `harness.py registrar medicao`.
- O `harness.py proximo` com o `Ajuste` aberto não trata a divergência da marcação como consertar e mostra a retomada do passo 6, com o `Proximo` do STATUS.md como motivo; a regra de retomada do `aprovacao.md` e do `pacote.md` diz para seguir o ajuste, sem o `versao conferir`. Sem documento em refino e com "quando o usuário liberar" no `Proximo`, ele recomenda, antes da fila e depois do consertar, `perguntar ao usuário se libera o commit do <gate>`, com o motivo `o usuário pediu para esperar o commit; liberado: harness.py estado set Proximo "<ação do primeiro item da fila>" e o commit`; o início da sessão mostra a mesma linha.
- A composição do pacote de um módulo sai do núcleo: o `harness.py dossie <módulo>`, com um módulo que casa o `por` de um item `ligados`, grava no arquivo e imprime no resumo o bloco `### Pacote do módulo (<N>)`, uma linha `- <caminho>` por derivado, na ordem dos links, ou `- nenhum: os rascunhos linkados são de outro módulo`. O derivado é o documento da fase, não aprovado, que casa os `documentos` do item e que o módulo linka fora de três exclusões: a seção de nível 2 com "outros módulos" no título; a lista aberta por uma linha que não é item e diz "outros módulos" ou "só lê", sem distinguir maiúscula nem acento; e a linha do link com a anotação `(módulo <nome>)` de outro módulo. O `proximo` usa a mesma lista no lugar da sua, com os rascunhos linkados só por outro módulo deixando de gerar o item `derivados`, e o rascunho que nenhum módulo compõe sai com o motivo `em rascunho; nenhum módulo o compõe`, no lugar de `; nenhum módulo o linka`. O passo 0 do `pacote.md` lê o bloco em vez de julgar de novo; a resposta "não" à composição corrige o texto do módulo, no próprio pacote quando ele está em rascunho e, quando está aprovado, pelo modo revisão dele.
- O "antes do" do destino de uma pendência aceita o arquivo como link Markdown, `[<texto>](<caminho>.md)`, com ou sem `#âncora`, na fila e no `estado lote`; o rótulo segue `antes do <arquivo>`. A revisão com `antes do <arquivo>` cujo arquivo é derivado de um módulo da fila entra logo antes do item desse módulo, como já entrava antes do próprio módulo, do rascunho, do obrigatório e do documento novo.
- A `/ela-harness:assessor` trata o relatório do pesquisador fora do prazo, que segue de 15 minutos: ao receber o relatório, e ao retomar sem ele, roda `date` e compara com o despacho. No caso 1, o relatório chegou além do prazo antes de a sessão seguir: entra em "Pesquisa" como veio, com a nota `chegou às <hora>, <n> min além do prazo`. No caso 2, o prazo passou sem relatório: a sessão pergunta pela ferramenta de opções, com `Esperar a pesquisa (Recommended)` e `Seguir sem ela`, e não corta mais sozinha; só o "seguir" para o agente com `TaskStop`. No caso 3, o relatório chegou depois de a sessão seguir: antes da resposta do usuário ao parecer, entra no estudo, e o parecer diz o que mudou; depois da decisão, o estudo não muda, "Pesquisa" anota a chegada e a sessão oferece a revisão pelo caminho de "Antes do passo 1". A linha de medição vira `retorno às <hora>[, <n> min além do prazo de 15]; <esperado | seguido sem ela | chegou depois da decisão>`.
- A `/ela-harness:gate-fase` guarda a espera do commit no STATUS.md: com o pedido de espera, o `passo 0` da cadeia do registro leva `--proximo "commit do <gate> quando o usuário liberar"` e o commit não sai. Quando o usuário liberar, roda `harness.py estado set Proximo "<primeiro passo da camada nova>" && git commit …`, e o commit leva o STATUS.md. A regra de retomada: com `commit do <gate> quando o usuário liberar` no `Proximo`, a skill vai direto ao passo 6, sem refazer o gate.

Sem passo de migração: nenhuma mudança de forma nos documentos.

## v0.4.1 — 2026-11-12

A decisão que atinge muitos documentos aprovados passa por uma revisão só, o lote, com um revisor por camada e um "aprovado"; a mudança de forma que não pede decisão vai por script, o `migrar`.

### O que mudou desde a 0.4.0

- O lote revisa num ciclo só os documentos aprovados que o destino de uma pendência cita, de qualquer camada e sem teto, no lugar do pacote em modo revisão, que parava em 6 documentos e abria um pacote por camada. O pacote de módulo segue com até 6. O STATUS.md ganha o campo opcional `Lote: <origem> (<N> documentos)`, com a origem `<prefixo>-NN` ou `migração v<de>→v<para>`; a lista dos documentos fica fora dele, em `.claude/harness/aprovacao/lote`, um caminho por linha, na ordem do lote (por camada, e na camada pela ordem do destino), e o `Documento` é o primeiro. O `Lote` e o `Pacote` não se abrem juntos, e o `estado set Lote` é recusado com `recusado: Lote muda só por estado lote, migrar ou fechar`. O `harness.py estado lote <prefixo>-NN <caminho>...` abre o lote e recusa, de uma vez, uma linha `recusado:` por caminho que o destino não cita, com `<caminho> não está no destino da <ID>`, e por caminho que não está `aprovado` na tabela de artefatos, com `<caminho> não está aprovado; o lote só revisa aprovados`; o que o `afetados` acha a mais nunca entra. O `estado lote --tirar <caminho>` tira um documento do lote aberto, e o lote nunca fica vazio. O `harness.py passo 6` marca o lote como marca o pacote, com o hash do manifesto, também no lote de um documento só; o `fechar` tira o `Lote` e apaga a lista, as cópias e a saída gravada do `afetados`. As respostas à aprovação são "aprovado", "mudar <documento>: <o quê>", "tirar <documento> do lote" e "ver <documento>". O passo a passo está na referência `lote.md` da `/ela-harness:refinar-documento`, que leva o que o `pacote.md` dizia do modo revisão.
- Com `Lote` aberto, o `harness.py backlog destino` e o `harness.py registrar nota` com texto que começa por `resta em <documento>` recusam o documento do lote, com `<documento> está no lote aberto; o que resta dele se resolve neste ciclo`: o que resta do documento do lote se resolve no ciclo, e o lote não abre outro sozinho. O `lote` do STATUS.md também fica isento do aviso de "STATUS velho" quando é o de migração.
- O `harness.py proximo` mostra a pendência com destino em dois ou mais documentos aprovados como um item `lote` só, com a ação do refino do primeiro documento, na ordem do lote, e o motivo `lote <ID>: <N> documentos, camadas <a> a <b>` (`camada <a>` com uma só), na posição da primeira revisão que ele substitui. Com o `Lote` no STATUS.md e a lista ausente, ilegível ou fora da conta, o `consertar` é `a lista do lote falta ou não confere`, com a mensagem do `estado` e o jeito de refazer no motivo; com a versão marcada, o motivo começa por `com a autorização do usuário, harness.py versao limpar`.
- O `harness.py versao resumo` dá o esqueleto das mudanças dos documentos em refino contra o HEAD, por documento e seção (`alterada (+a −r)`, `nova`, `removida`) e os IDs que entraram, saíram ou mudaram, e grava o diff de cada camada em `.claude/harness/dossie/diff-camada-<N>.diff`, para o revisor ler no lugar do documento inteiro. O `--desde-marcada` compara com a cópia marcada, para a volta do "mudar <documento>". O `--conferir <arquivo>` confere as linhas `Onde: <documento> · <seção>` do resumo escrito contra as seções que mudaram e imprime `OK: <M> mudanças cobrem as <N> seções alteradas`, ou `FALTA:` e `SOBRA:`, com 1. O `harness.py versao ver <documento> [n]` mostra a `n`-ésima seção alterada, só com as linhas que mudaram, sem número de linha, a trocada palavra a palavra (`~~antigo~~ **novo**`), a acrescentada em `**` e a tirada em `~~`; uma linha tirada e uma acrescentada só viram uma trocada quando mais da metade das palavras confere, e senão saem cada uma na sua linha. Seção nova: `Seção nova, <k> linhas.`; removida: `Seção removida.`. O resumo por mudança, com a mesma mudança em vários documentos numa entrada só, vale em toda aprovação do modo revisão (documento, pacote e lote) e na volta do "mudar", no lugar do `git diff`. O resumo escrito fica em `.harness-aprovacao/resumo.md`, fora do `.claude/`, onde o Claude Code pede permissão a cada escrita mesmo com `acceptEdits`; o `versao resumo` cria a pasta com um `.gitignore` próprio, sem mexer no do projeto.
- O `harness.py legenda --ids "<texto>"` imprime, sem gravar, uma linha `<ID> (<título>)` por ID do texto e uma `<SIGLA> (<significado>)` por sigla, na ordem da primeira aparição e sem repetir; o ID sem definição sai com `não definido`. A citação de item de Aceite (`<ID>.<n>`, ou a faixa `<ID>.<n> a <ID>.<m>`) conta como o ID, e o título vai depois da citação inteira. O `saida.md` ganha a regra 8, "Na primeira aparição na mensagem, cada ID e cada sigla vêm com o título ou o significado entre parênteses, pela saída de `harness.py legenda --ids`", e a regra 9, "Uma ideia por frase; uma frase por linha nos itens". Os moldes do resumo do pacote e do lote, do relato da revisão e das mensagens de aprovação foram revistos com elas. O `--ids-de <arquivo>` faz o mesmo com o texto do arquivo, para o resumo escrito ir sem passar pelo shell.
- O `harness.py migrar [--de v<versão>]`, só no planejamento e fora de um ciclo, aplica de uma vez as correções de forma das versões acumuladas nos documentos `aprovado` e abre um lote só para elas, sem pendência, com `Lote: migração v<de>→v<para> (<N> documentos)`. A versão de partida é a `--de`, ou a da última linha `migração v<de>→v<para>` do arquivo de decisões. A correção desta versão, `item-de-aceite`, troca a citação `<ID>.<n>` (ou a faixa) do item de Aceite que outro documento renumerou pelo número de hoje do item de texto igual, partindo do commit da linha que cita (`git blame`); sem item igual, ou com mais de um, a citação fica e sai o aviso `<documento>:L<linha>: <ID>.<n> sem item igual hoje em <documento>; confira na revisão dele`. A citação por número de linha não tem correção. O lote de migração é revisado com o critério forma no revisor, os passos 5 e 7 não mexem na tabela de artefatos (os documentos seguem `aprovado`, com a data de antes), e o passo 7 grava `- <data> migração v<de>→v<para>: <N> documentos` no arquivo de decisões, com o commit `docs(planejamento): migração v<de>→v<para>, <N> documentos`. Sem correção, grava `- <data> migração v<de>→v<para>: nada a corrigir` e imprime `nada a corrigir; migração v<de>→v<para> registrada`; se a última migração registrada já chega a `v<para>`, não grava de novo e imprime `nada a corrigir; migração até v<para> já registrada`. Recusa, com 1, `recusado: ciclo aberto (<Documento>); feche-o antes de migrar` (também `ciclo aberto (pacote de <N> documentos)` e `ciclo aberto (lote <origem>)`), `recusado: nenhuma migração registrada; passe --de v<versão da última atualização>` e `recusado: <documento> tem mudança fora do commit; faça o commit antes`.
- A verificação que entrou numa versão do plugin depois da aprovação só avisa no documento `aprovado` na tabela de artefatos: o `checar` dá `<nome>: AVISO: <n> ocorrências, verificação da v<x>, posterior à aprovação`, sem sair com 1, enquanto nenhuma migração registrada chegou à `v<x>` ou a data da aprovação é anterior à da migração que chegou. O gate não conta o aviso como falha. Nesta versão nenhuma verificação entra nessa regra; o mecanismo (o mapa `DESDE`, do `checar.py`) fica pronto para a próxima.
- O `harness.py backlog destino <prefixo>-NN "<destino>" --dispensa "<motivo>"` deixa o destino novo perder o marcador do gate que o antigo tinha e acrescenta `; <AAAA-MM-DD>: dispensada no <gate>: <motivo>; destino era <destino antigo>` ao status. Sem o `--dispensa`, a recusa do marcador perdido ganha o fim `; na dispensa do gate, use --dispensa "<motivo>"`, e o `--dispensa` sem marcador perdido é recusado com `--dispensa só vale quando o destino novo perde o marcador de um gate`. O destino novo que cita um documento do lote aberto é recusado, como no item do lote.
- O "Para você" do relato da revisão traz a opção recomendada de cada item, em negrito e com "← recomendo:", na própria linha; com mais de uma pendência no escopo, a nota vai para a pendência cuja mudança atingiu o documento, ou, sem ela, para a de menor número; o `afetados` do passo 0 do modo revisão e do lote vai com todos os termos entre aspas num comando só.
- O `harness.py afetados --gravar` grava a saída em `.claude/harness/dossie/afetados.txt`, para o revisor do modo revisão e do lote ler no lugar dos documentos inteiros; o `fechar` apaga o arquivo.

Passo de migração:

1. Atualize o plugin pelo guia [Atualizar o plugin](docs/guias.md#atualizar-o-plugin).
2. No planejamento, rode `harness.py migrar --de v<a versão de antes desta atualização, como v0.4.0>` e siga o lote que ele abrir; sem correção a fazer, ele só registra a migração.
3. Um ciclo aberto com `Pacote` em modo revisão termina como está; o lote vale do próximo ciclo em diante.

## v0.4.0 — 2026-11-12

O planejamento abre pendência só quando nenhum ciclo resolve o assunto e nenhuma pendência aberta o leva: o que sobra de um documento vira nota na pendência que já existe, e a pendência nova nasce com a causa dela.

### O que mudou desde a 0.3.2

- A regra de quando se abre pendência fica num arquivo só, o `nucleo/planejamento/pendencias.md`, e as skills apontam para ele. Ele traz a escada, em que vale o primeiro degrau que couber: dentro do escopo do ciclo, resolver agora, e perguntar agora o que pede decisão do usuário; fora do escopo, nota na pendência do ciclo ou, sem ela, numa pendência aberta com destino no documento atingido; sem pendência para a nota, a pergunta "Abrir pendência" ou "Deixar de lado", e esta grava `harness.py registrar descartada "<o que apareceu> — <o motivo do usuário>"`. Os pontos da `/ela-harness:refinar-documento`, da `/ela-harness:gerar-modulos` e da `/ela-harness:gate-fase` que abriam pendência por conta própria passam a seguir a escada, e as lacunas do mesmo documento entram juntas numa pendência só.
- O `harness.py registrar nota <prefixo>-NN "<texto>"` acrescenta `; <AAAA-MM-DD>: <nota>` ao fim da célula de status de uma pendência aberta, sem mexer no resto da linha, e imprime `<prefixo>-NN anotada em <arquivo>:<linha>`. O ID casa pelo número, de modo que `<prefixo>-3` acha a `<prefixo>-03`. Recusa a nota vazia, com quebra de linha ou com `|`, a pendência fora do backlog ou que não está aberta e os IDs com erro. Quando sobra trabalho noutro documento, a nota começa por `resta em <nome do arquivo>: <o quê>`.
- O `harness.py backlog destino <prefixo>-NN "<destino>"` troca só a célula de destino de uma pendência aberta e acrescenta `; <AAAA-MM-DD>: destino era <destino antigo>` ao fim do status, para a pendência seguir ao que resta quando parte dela se resolveu; imprime `<prefixo>-NN com destino <destino> em <backlog>:<linha>`. Recusa, com `recusado: <motivo>` e sem gravar: o destino vazio, com quebra de linha ou com `|`; o destino novo que perde o marcador de um gate que o antigo tinha, com `o destino novo perde "<marcador>", que segura o <gate>`; o destino igual ao atual, com `destino: igual ao atual`; a linha com menos de 3 células, com `<prefixo>-NN não tem a célula de destino`; a pendência fora do backlog ou que não está aberta; e os IDs com erro. No passo 7 do refino, a pendência do ciclo com nota `resta em` desta volta fica aberta, e esse comando troca o destino pelos documentos que restam.
- O modo revisão da `/ela-harness:refinar-documento` não abre mais pendência em cascata: o Ruling triado no passo 0 que toca o documento e a pendência não cobre vai para a pergunta de escopo do passo 1, e a decisão que atinge outro documento aprovado vira nota `resta em <documento>: <o quê>`, pela escada. A pergunta de escopo usa a ferramenta de opções, com `header` "Escopo", e lista as pendências abertas cujo destino cita o documento só quando são duas ou mais, até quatro por pergunta (`multiSelect`), e uma pergunta para cada Ruling triado, com "Entra agora" ou "Fica como nota". Sem nenhuma delas, o escopo fica só na primeira linha. O que passa de quatro perguntas segue em chamada seguinte, com a conferência do resumo na última. O achado do revisor fora do escopo vira nota na pendência do ciclo, ou vai para "Para você" no relato quando pede decisão; nunca um ID novo.
- O `harness.py registrar pendencia` exige o `--causa <causa>`, de uma lista fixa: `entrevista`, `pesquisa`, `pesquisa-sem-fonte`, `revisor`, `ruling`, `cascata`, `gerar-modulos`, `camada-3`, `gate`, `leitor-frio`, `harness`, `triagem`, `prototipo`, `pedido`, `codigo` e `outro`. A causa vai no fim da Origem, como `<documento>, <AAAA-MM-DD>, causa: <causa>`, e fora da lista a recusa é `--causa: <causa> não está na lista`. A linha sem causa, de antes da 0.4.0, segue válida e conta como `sem causa`; o `rastreio` e o `dossie` não casam pela causa. O `harness.py backlog causas` imprime, com saída 0, uma linha `<causa>: <total> (<abertas> abertas)` por causa presente, na ordem da lista, depois `sem causa` quando houver, e `Total: <total> pendências, <abertas> abertas`; recusa o backlog ausente ou ilegível e os IDs com erro, com 1.
- A dúvida da entrevista deixa de abrir pendência: fica na árvore do chat, em "Fica para a próxima", até a redação, e a que é deste documento entra no passo 3 como `[A CONFIRMAR: pergunta aberta: <a pergunta>]`, fora da rodada de confirmação do passo 4. A que é de outro documento sobe a escada a partir do degrau 2.
- O aviso do `proximo` para o retorno sem pendência passa a dizer `retorno sem pendência: #N <título>; registre por harness.py registrar pendencia --causa codigo citando retorno #N`.

Passo de migração:

1. Atualize o plugin pelo guia [Atualizar o plugin](docs/guias.md#atualizar-o-plugin). Nenhum backlog muda, e a linha sem causa conta como `sem causa`.
2. Quem chama o `registrar pendencia` à mão, ou num script, passa a dar o `--causa`.
3. As notas "resta" de texto livre, de antes da 0.4.0, não mudam o destino; quem quiser que o `proximo` as veja troca o destino delas por `harness.py backlog destino`.

## v0.3.2 — 2026-11-11

As arestas da migração dos projetos para a distribuição pública: o `iniciar --conferir` que recusa no planejamento, o comando do `iniciar` sem aspas que passa sem pedir permissão, os diagramas e o ramo do CI do planejamento, o link velho do núcleo e o guia de atualização do plugin.

### O que mudou desde a 0.3.1

- O `harness.py iniciar --conferir` recusa no repositório de planejamento, com o perfil legível e o `[projeto] harness` diferente de `desenvolvimento`, antes de conferir qualquer item, com `iniciar --conferir: é do repositório de código; no planejamento, rode harness.py gerar --check`, e sai com 1. Antes, ele dava faltas que não valiam para o planejamento. Sem perfil ou com o perfil ilegível, a conferência segue como antes, com `perfil: falta`.
- O `allowed-tools` da `/ela-harness:iniciar` traz duas regras, que casam o comando com e sem aspas em volta do `${CLAUDE_PLUGIN_ROOT}`: a skill deixa de pedir permissão quando o modelo escreve o caminho expandido sem aspas.
- O `bancos.py` passa a sair na distribuição, e o plugin traz o `ci/planejamento/diagramas.yml`, o workflow do check `diagramas`: valida o Mermaid da pasta do planejamento e, com `[der]` no perfil, aplica o DDL num MySQL e num Postgres e compara o `workbench.sql` com o `schema.mysql.sql`. O projeto o copia uma vez, pelo guia "Validar os diagramas no CI", para o `.github/workflows/diagramas.yml`; o `harness.py gerar` não o escreve nem o confere, e a versão do plugin sai da `ref` do `.claude/settings.json`, como no `harness.yml`. A referência `camada-3.md` da `/ela-harness:refinar-documento` passa a dizer que o CI do projeto só valida o Mermaid e compara o `workbench.sql` com esse workflow.
- A recusa de versão diz como sair do link velho do núcleo: `harness.yml: o plugin carregado é v<X> e o .claude/settings.json fixa <ref>; reinstale o plugin e depois apague o link .claude/harness/nucleo ou abra uma sessão nova`. A linha chega ao `gerar`, ao `gerar --check`, ao `gerados-em-dia`, ao `iniciar` e ao item `ci` do `iniciar --conferir`. Ela só aparece quando o núcleo em uso já é o `0.3.2`; no salto da `0.3.1`, quem roda é o núcleo velho, que diz só `reinstale o plugin`.
- O perfil do planejamento ganha a tabela `[ci]`, opcional, com a chave `ramo`: o ramo em que o `harness.yml` gerado dispara, no push e no pull request, `main` sem ela. O `gerar`, o `gerar --check`, a `gerados-em-dia` e o `iniciar planejamento` a leem. As recusas, todas depois de `perfil inválido: `, são `[ci] deve ser uma tabela`, `ci com chave desconhecida: <chave>`, `ci.ramo deve ser um texto não vazio` e `ci.ramo fora do formato de branch: <ramo>`, esta com espaço, com `..` ou com `-` no começo. O modelo do perfil do planejamento traz `[ci]` com `ramo = "main"` e um comentário.
- O guia [Atualizar o plugin](docs/guias.md#atualizar-o-plugin) substitui o "Sair da origem privada" e serve a toda subida de versão: troca o marketplace pela `ref` nova, reinstala o plugin, faz o passo de migração do `CHANGELOG.md`, roda o `gerar` e o `gerar --check` e commita. O passo 3 manda fechar as sessões do Claude Code abertas no projeto, porque os hooks delas refazem o link `.claude/harness/nucleo` para o núcleo carregado, o velho; depois, apagar o link e rodar o `gerar` numa sessão nova ou no terminal. O passo 4 tira o `harness.yml` do robô de dependências, com o `exclude-paths` do Dependabot ou, no Renovate, `{ "matchFileNames": [".github/workflows/harness.yml"], "enabled": false }` no `packageRules`. O "Relatar um problema" aponta o guia.

Passo de migração:

1. Atualize o plugin pelo guia [Atualizar o plugin](docs/guias.md#atualizar-o-plugin): feche as sessões do Claude Code do projeto, apague o link `.claude/harness/nucleo` e só então rode o `harness.py gerar`. O núcleo `0.3.1` ainda diz só `reinstale o plugin`, e o link velho o mantém carregado.
2. No planejamento que roda o CI fora da `main`, ponha `[ci] ramo = "<ramo>"` no `.claude/perfil.toml` antes do `gerar`.
3. No planejamento com os diagramas num workflow feito à mão, troque-o pelo `diagramas.yml` do guia [Validar os diagramas no CI](docs/guias.md#validar-os-diagramas-no-ci).

## v0.3.1 — 2026-11-10

Quatro consertos do dia a dia: o despacho em segundo plano termina o turno sem adiantar o resultado, a aceitação separa o item manual do pendente, o STATUS velho passa a ser avisado, e o `checar` recusa a citação por número de linha e avisa o item de Aceite citado que mudou.

### O que mudou desde a 0.3.0

- Os despachos em segundo plano terminam o turno. O revisor do `/ela-harness:refinar-documento` fecha a mensagem com `Revisor em segundo plano (rodada <n>); o relato vem quando ele voltar.`, o do `/ela-harness:gate-fase`, com `Revisor do gate em segundo plano; o checklist vem quando ele voltar.`, e, até a notificação do agente, nenhuma mensagem traz veredito, achado ou palpite; se o usuário pede antes, a resposta é que o revisor ainda não voltou. Os despachos do SDD no `/ela-harness:executar-bloco` ganham a regra **Espera**: o despacho que volta sem o resultado termina o turno, e nada que dependa dele sai antes da notificação.
- O `harness.py aceitacao conferir` dá `ACEITACAO MANUAL: <k> de <n> item(ns): <números>` quando todo item pendente de antes do merge é manual e ainda sem resultado, e sai com 1, como no `ACEITACAO PENDENTE`. A `/ela-harness:finalizar-bloco` segue pela última linha: `ACEITACAO OK`, o passo 3; `ACEITACAO MANUAL`, o passo 2, do item manual, um por vez, até o `aceitacao anotar` dar `ACEITACAO OK`; outra linha, o dono.
- O `proximo` avisa o STATUS velho: com o documento ou o pacote do STATUS, nos passos 0 a 6, todo `aprovado` no backlog e sem pendência aberta que o cite, o recomendado é `consertar: perguntar ao usuário se o STATUS está velho`, com a volta no motivo, e o início da sessão mostra o mesmo. No modo revisão do `/ela-harness:refinar-documento`, o pedido do usuário sem pendência aberta que cite o documento vira pendência no passo 0, pelo `harness.py registrar pendencia`, e entra no escopo.
- O harness grava o hash do STATUS a cada mudança dele, no arquivo `harness-status` do diretório do git da cópia, e o pre-commit do planejamento ganha a `status-pelo-harness`, que nunca falha: `status-pelo-harness: AVISO: <status> do commit não é o que o harness gravou por último nesta cópia; confira com harness.py proximo`, quando o STATUS do commit não é o que o harness gravou.
- O `harness.py checar` ganha duas verificações, logo depois do `links`. A `citacao-por-linha` recusa o trecho `<caminho>.md:<n>` ou `<caminho>.md:<n>-<m>` fora dos blocos de código, com o detalhe `L<linha>: <citação> cita por número de linha; cite o ID ou o título da seção`; o arquivo de decisões fica de fora, porque só recebe acréscimos, e o negrito e o itálico em volta da citação ficam fora do caminho. A `aceite-renumerado`, que nunca falha, compara cada `<ID>.<n>` que outro documento aprovado cita com o item do documento no HEAD e avisa `L<linha>: <ID>.<n>, citado em <documentos>, virou <ID>.<m> desde o HEAD` ou `[...] mudou ou saiu desde o HEAD`. A redação do `/ela-harness:refinar-documento` cita pelo ID ou pelo título da seção e mantém o número do item de Aceite citado: o item novo entra no fim, e a mudança de propósito leva a correção ao documento que cita.

Passo de migração: o planejamento não roda comando. O gate pode falhar na `citacao-por-linha` de um documento aprovado; a citação se troca pelo ID ou pelo título da seção na revisão dele. O primeiro commit que muda o STATUS depois de atualizar pode dar o aviso da `status-pelo-harness` uma vez, até o harness gravar o hash. O desenvolvimento não muda nada.

## v0.3.0 — 2026-11-10

O plugin passa a vir de um repositório público, e o CI dos projetos, a rodar sem credencial: o `harness.yml` vira arquivo gerado, a stack do projeto se instala no CI pelo perfil, e o harness avisa e explica a ferramenta que falta.

### O que mudou desde a 0.2.7

- O plugin é publicado no repositório público `Ela-Decora/ela-harness`, sob a licença MIT, com o `LICENSE` e o `THIRD-PARTY-NOTICES.md` na raiz. O `Ela-Decora/ElaHarness` segue privado, como origem: cada tag `v*` dele vira, pelo workflow `publicar.yml`, um commit e a mesma tag na distribuição, com o recorte do `.gitattributes`, sem os testes, as specs e a configuração da origem. O `repository` do `plugin.json`, o `repo` do `.claude/settings.json` dos modelos, o README e o `iniciar` apontam a distribuição, e o `iniciar --conferir` dá `plugin: falta` no projeto ainda fixado na origem. O manual fica só com o que serve a quem usa: sai "Evoluir o harness", e entram os guias "Relatar um problema" e "Sair da origem privada".
- O `.github/workflows/harness.yml` passa a ser arquivo gerado nas duas trilhas: o `iniciar` o escreve, e o `harness.py gerar` o mantém, pela `ref` do `.claude/settings.json`. Ele baixa a distribuição nessa tag, sem token, e chama a action do CI do plugin, `ci/<trilha>/action.yml`, que roda as invariantes e, no desenvolvimento, a instalação do CI e as verificações; o job segue com o nome `harness`. O `gerar --check` e a `gerados-em-dia` o conferem byte a byte, a guarda recusa editá-lo com `arquivo gerado: rode harness.py gerar`, e o item `ci` do `iniciar --conferir` diz `ci: falta: .github/workflows/harness.yml igual ao gerado; rode harness.py gerar`. O `gerar` recusa o arquivo com `harness.yml: o plugin carregado é v<versão> e o .claude/settings.json fixa <ref>; reinstale o plugin` ou `harness.yml: o .claude/settings.json não fixa a versão do plugin (<motivo>); rode harness.py iniciar --conferir`. Sem o núcleo baixado, o CI cai com `::error title=harness: plugin não baixado::`, a tag e o que conferir.
- O perfil de desenvolvimento ganha `[desenvolvimento.ci] instalar`, a lista de comandos que instala a stack do projeto no CI, vazia no modelo. O `harness.py ci instalar` os roda um por um, por `sh -c`, na raiz, com 900 s cada, e passa ao seguinte o PATH e as variáveis gravadas no `GITHUB_PATH` e no `GITHUB_ENV`. Só roda com `GITHUB_ACTIONS=true`; fora dele, recusa com `instalação do CI: só roda no CI (GITHUB_ACTIONS=true)`. As linhas são `instalação do CI: nada a instalar`, `instalação do CI: <comando>: ok (<s> s)`, `instalação do CI: <comando> falhou (saída <c>)` e `instalação do CI: <comando> passou de 900 s`, e o primeiro que falha para a lista. O serviço que fica de pé, como o banco, sobe com `docker compose up -d`: o que vai com `&` morre com o grupo de processos do comando.
- O `bloco finalizar` avisa, sem recusar, `aviso: [desenvolvimento.ci] instalar está vazio e <nomes> rodam no CI, que começa sem a stack`, quando a lista está vazia e alguma verificação do momento `finalizar` roda um comando que não é do harness.
- No CI, com `GITHUB_ACTIONS=true`, a verificação que falha lê a saída inteira e, para cada comando não encontrado pelo shell (`sh: <n>: <cmd>: not found` ou `<cmd>: command not found`), diz `<nome>: a saída diz que falta o comando <cmd>; declare a instalação em [desenvolvimento.ci] instalar`. Cada falha, a da instalação do CI inclusive, gera a anotação `::error title=harness: <nome> falhou::<primeira linha>`, que aparece no resumo do PR. Fora do CI, a saída fica como antes.

Passo de migração dos projetos gerados da `v0.2.1` à `v0.2.7`, que baixam o núcleo do `Ela-Decora/ElaHarness` com o segredo `ELA_HARNESS_TOKEN`: o guia [Atualizar o plugin](docs/guias.md#atualizar-o-plugin), à mão e uma vez. Ele troca o marketplace pela distribuição e reinstala o plugin, roda o `harness.py gerar`, declara a stack em `[desenvolvimento.ci] instalar` e commita; depois, o segredo pode sair. Quem não migra segue na origem, com o token.

Aviso: as actions do `harness.yml` vão fixadas por SHA, que sobe com a versão do plugin, e o PR do Dependabot nesse arquivo fica vermelho com `desatualizado: .github/workflows/harness.yml; rode harness.py gerar`. Feche-o, ou tire o arquivo do Dependabot pelo `exclude-paths`, como diz o guia: quem atualiza o `harness.yml` é o `harness.py gerar`.

## v0.2.7 — 2026-11-09

A camada 2 do planejamento ganha a skill `/ela-harness:gerar-modulos`, que gera em rascunho as entidades, as telas e os módulos a partir do escopo aprovado, e o `proximo` que a recomenda.

### O que mudou desde a 0.2.6

- A skill `/ela-harness:gerar-modulos` lista as entidades, as telas e os requisitos do escopo aprovado, cada um com a fonte, e abre uma rodada só, com a proposta de módulos, o uso das entidades como modelo lógico e as dúvidas; cada resposta vira Ruling ou pendência na hora. Depois escreve em rascunho, sem commit, as entidades, as telas e, por último, os módulos, e roda o `harness.py checar`. O relato traz os arquivos, os `[A CONFIRMAR]` e o pacote seguinte, que segue no `/ela-harness:refinar-documento`. A sessão que cai no meio retoma do Ruling da proposta e grava só o que falta. Só o usuário a invoca.
- O `proximo` recomenda a `gerar-modulos`: o item `gerar` vai primeiro na fila, com o motivo `nenhum <padrões do por, juntados por " ou "> na fase`, quando a fase tem item `ligados` no gate, nenhum documento do `por` está no disco nem em refino, e os obrigatórios da fase já estão aprovados. O módulo em refino segura o item, e a pendência do gate que pede um módulo pelo nome, sem módulo no disco, traz o `gerar` antes do documento novo.
- Os moldes de tela e de entidade ganham o que a skill preenche: a tela, os estados e a navegação; a entidade, o ciclo de vida.
- O `harness.py perfil --para gerar-modulos` dá o bloco "Este projeto" da skill: a fase, os itens `ligados` e `ids-cobertos` do gate, o molde de cada padrão e as fontes aprovadas. Na fase sem item `ligados`, imprime `ERRO: <gate> sem item ligados; a skill não se aplica à fase <fase>`.
- O revisor do `refinar-documento` confere a entidade, a tela e o módulo pelos princípios da `gerar-modulos`, com o arquivo de princípios do tipo no prompt de despacho.
- O CLAUDE.md gerado do projeto de planejamento ganha a linha da `gerar-modulos`, só quando o perfil tem item `ligados`, e o manual ganha o guia "Gerar os módulos".

Passo de migração do projeto de planejamento:

1. `harness.py gerar`, para a linha nova do texto gerado; até ele, o `gerados-em-dia` acusa.
2. Só com a camada 2 sem tela nem entidade aprovada: no terminal, na raiz do projeto, o trecho abaixo, com o nome do projeto, o mesmo do título dos moldes que o projeto tem, e a `[moldes].pasta` do perfil no lugar de `planejamento/Templates`, se for outra; as duas linhas que ele imprime vão para `[moldes.liberados]` do `.claude/perfil.toml`, com a seção criada se faltar, e o commit sai sem `--no-verify`. Com tela ou entidade aprovada, fique com os moldes antigos: a skill escreve no molde que o projeto tem. Os rascunhos de tela e de entidade já escritos no molde antigo falham no `checar` depois da cópia: ganham os títulos novos no `/ela-harness:refinar-documento`, ou se apagam e a skill os gera de novo.

```bash
python3 - "<nome do projeto>" <<'PY'
import hashlib, sys
from pathlib import Path
origem = Path(".claude/harness/nucleo/modelo/planejamento/planejamento/Templates/2-intermediario/Templates")
destino = Path("planejamento/Templates/2-intermediario/Templates")
for nome in ("_modelo-tela.md", "_modelo-entidade.md"):
    dados = (origem / nome).read_text(encoding="utf-8").replace("{{PROJETO}}", sys.argv[1]).encode("utf-8")
    (destino / nome).write_bytes(dados)
    print(f'"2-intermediario/Templates/{nome}" = "sha256:{hashlib.sha256(dados).hexdigest()[:12]}"')
PY
```

## v0.2.6 — 2026-11-09

Os três defeitos que travaram a camada 2 do planejamento: o título da funcionalidade, que o perfil do modelo não casava, as pendências que pedem um documento novo e o gate recomendado sem conferir se passa, e a regra de link da passagem, que só o leitor frio do gate aplicava.

### O que mudou desde a 0.2.5

- O perfil do modelo de planejamento casa os títulos dos moldes: as `partes_variaveis` ganham `'<MÓD>' = '[A-Z]+'` e `'-NN\b' = '-[0-9]{2,}'` e perdem a `'Funcionalidade:$'`, e o `secoes-com-id` do G2 passa a procurar `titulo = "### Funcionalidade"`, que acha também a funcionalidade escrita sem o ID. Antes, o `checar` reprovava todo módulo pelo `<MÓD>` e pelo `NN` literais, e o `secoes-com-id` passava sem conferir nada.
- O `proximo` põe na fila o documento novo que uma pendência aberta do gate pede: um item da categoria `novo`, com a ação `/ela-harness:refinar-documento <caminho>`, depois dos obrigatórios e antes das revisões. O motivo é `documento novo: <IDs> (<marcador>)`, com `; o nome sai da pendência` quando o destino é uma pasta, e `; a pasta, com o usuário` quando o destino é um nome sem irmãos, ou com irmãos em mais de uma pasta, e o caminho leva a `<pasta>` literal. A revisão com `antes do <arquivo>.md` entra antes do item novo desse arquivo.
- O `proximo` põe antes do gate a pendência que nenhum documento da fila resolve: `resolver <ID> com o usuário`, com o motivo `nenhum documento da fila a resolve: <destino>`. O módulo, o item de derivados, o rascunho, o obrigatório, o documento em refino e o derivado em rascunho de um módulo da fila cobrem a pendência que cita o nome deles; o documento novo e as revisões cobrem a que trazem pelos IDs. Antes, o gate era recomendado com `fila da fase vazia` e reprovava depois, no `pendencias-do-gate`.
- O `harness.py proximo` roda, com o gate como recomendado, os itens de script dele, sem o leitor frio, e mostra logo abaixo do motivo a linha `Pré-checagem do <gate>: <n> FAIL`, com até 3 linhas FAIL e `  +<k> FAIL: harness.py gate <gate> --verbose` quando há mais; `Pré-checagem do <gate>: sem FAIL`; ou `Pré-checagem do <gate>: não rodou: <motivo>`, quando a pré-condição do gate recusa, e `não rodou: <Tipo>: <primeira linha da mensagem>`, quando outro erro sai do gate, sem derrubar o `proximo`. Com `--verbose`, todas as linhas FAIL. O hook e o `fechar` não a rodam, e o `proximo` segue só lendo.
- O `links` do `checar` roda em todo documento de uma pasta de fase, com ou sem `[der]`, e aplica a regra de link da passagem: além do `link <destino> não resolve`, passa a dar `link <destino> é uma pasta; linke um arquivo` e `link <destino> excluído da passagem (<chave>)`, para o destino em `rascunho`, `status`, `decisoes`, `backlog`, `estudos`, `atritos`, `leitor_frio` ou na pasta `.claude`. O `checar-da-fase` dos gates passa a ver o link de toda fase. As recusas da exportação da passagem não mudam.

Passo de migração do projeto de planejamento: no `.claude/perfil.toml`, troque a linha das `partes_variaveis` por

```toml
partes_variaveis = { '<!--.*?-->' = '.+', 'XXX' = '[A-Z]+', '<MÓD>' = '[A-Z]+', '-NN\b' = '-[0-9]{2,}' }
```

sem a `'Funcionalidade:$'`, e ponha `titulo = "### Funcionalidade"` no `secoes-com-id` do G2.

Aviso: o `checar` passa a conferir os links de todo documento das pastas das fases, e o documento aprovado com link para uma pasta ou para um caminho excluído da passagem falha na próxima revisão e no `checar-da-fase` do gate. Troque o link por um arquivo.

## v0.2.5 — 2026-11-08

Os Minor das revisões da 6c e da 6d-repositorio: a guarda de segredos que acusava o renomeado, o `--enviar` que repetia comentário e consultas, o trecho do Context Packet com título do tamanho do fato, o `passagem-em-dia` que não olhava os `ids` e o `importar` que deixava passar o PR de outra versão, o órfão no índice e o arquivo ignorado.

### O que mudou desde a 0.2.4

- O `sem-segredos` compara o arquivo renomeado ou copiado com o arquivo de origem dele, e não com o vazio: só o segredo que o renomeado acrescenta é achado, e o segredo antigo, que já estava no arquivo, não é mais acusado. No `mv` sem `git add`, no modo `arvore` do hook `Stop`, o git não pareia os nomes, e o arquivo segue comparado com o vazio. O arquivo que sai de uma pasta de `segredos_isentos`, renomeado ou copiado, é conferido contra o vazio: a origem isenta nunca foi conferida, e o segredo dela não conta como já na base.
- O `passagem publicar --enviar` conta como igual o comentário da issue com `\r\n`, e a issue que já tem o comentário não ganha outro. As tags do `origin` vêm de um `git ls-remote` só, no lugar de um por tag; a tag de nome parecido, como `passagem/v2x`, fica de fora.
- Os títulos do trecho de um fato no Context Packet descem abaixo do `### <ID>`: o mais alto vai a `####` e os outros o mesmo tanto, até `######`, sem mexer nos blocos de código. O trecho sem título, ou com o mais alto já em `####` ou abaixo, sai igual.
- O `passagem-em-dia` confere os `ids` do manifesto: o `arquivo` de cada `ids[]` tem de estar em `arquivos`, e o trecho refeito a partir da primeira linha dele tem de ter as linhas e o `sha256` do manifesto. Duas linhas novas no resumo: `ids.<ID>: <passagem>/<arquivo> não está em arquivos; a cópia muda só por harness.py importar` e `ids.<ID>: o trecho <passagem>/<arquivo>:<primeira>-<última> difere do manifesto; a cópia muda só por harness.py importar`. O `ids[]` de um arquivo que falta ou difere não é conferido, e as `pendencias` ficam de fora.
- O `importar` recusa, antes do clone e sem gravar nada, com o PR aberto da `docs/passagem-v<m>`, de outra versão (o de menor número, quando há mais de um): `PR #<n> da passagem/v<m> ainda aberto: <url>; mescle-o ou feche-o antes de importar a v<N>`. O gerado órfão que o `importar` apaga sai também do índice, pelo `git rm --cached`, e não volta ao primeiro commit.
- O `importar` para, sem commit e com saída 1, com o arquivo que o git ignora entre os que ele põe no commit: `o git ignora <k> arquivos (1 arquivo, no singular) que o importar põe no commit, como <primeiro>; ajuste o .gitignore e rode harness.py importar v<N> de novo`. Vale no primeiro commit e no worktree do PR, antes do `git add`. O link do núcleo, `.claude/harness/nucleo`, que o hook refaz e o `.gitignore` ignora de propósito, não conta.

Não há passo de migração: o `contexto.md` novo sai no próximo `harness.py contexto`.

## v0.2.4 — 2026-11-08

O ciclo do bloco se protege pelo próprio texto nos pontos em que as skills de terceiros falharam no uso: a spec que não leu o código, o plano que não rodou o que fixa, a sessão compactada, o teste que gravou fora do worktree e o item manual que chegava ao dono sem conferência.

### O que mudou desde a 0.2.3

- Spec e plano do bloco: a spec cita com `arquivo:linha` o código de que o desenho depende, também na `## Correção` da spec curta; o plano roda uma vez, antes do `bloco planejado`, os fragmentos que fixa com os dados de teste, e grava a aprovação na linha `**Spec approval:**` e as decisões do dono na seção `## Owner decisions`.
- A linha de sessão nova: com a sessão compactada ou o pedido do dono de outra sessão, o `planejar-bloco`, o `executar-bloco` e o `revisar-bloco` entregam a linha pronta para colar numa sessão aberta na árvore principal, na forma da `## Retomada` do `ciclo.md`, no lugar de invocar a skill seguinte.
- Os agentes `implementador-mecanico`, `implementador-integracao` e `corretor-tardio`: nenhum teste roda um programa externo real que grava fora do worktree e da pasta temporária do teste, e o relato diz que os arquivos dele ficaram sem mudança.
- O item manual de antes do merge: a sessão confere sem o dono as pré-condições que um comando confere, invoca o `wizard` pela ferramenta Skill só com o que sobrou para uma pessoa e grava o script pelo Write em `.superpowers/wizard/`, sem rodar `bash` na lane. O `ciclo.md` dispensa o `cp`, o `bash -n` e o `chmod` do `wizard`.
- As mensagens que mandam rodar o `lane fechar` (a linha `closing` do `bloco status`, as recusas do `bloco finalizar` e do `bloco corrigir` com o PR mesclado e o fim do `finalizar-bloco`) passam a dizer `de uma sessão aberta na árvore principal, ou pelo terminal como última ação`, no lugar de `fora da lane`.

Passo de migração: rode `harness.py gerar` no projeto de desenvolvimento, para o `ciclo.md` novo.

## v0.2.3 — 2026-11-07

O ciclo do planejamento deixa de cair em três pontos: a aprovação que o hook do prompt não anotava, o `--em` preso à pasta do planejamento e o dossiê que cortava os Rulings.

### O que mudou desde a 0.2.2

- O hook do prompt (`UserPromptSubmit`) passa a responder pela via curta, sem carregar o `harness.py`: a mediana caiu de 164 ms, pela `main`, para 70 ms, pela via curta, no ensaio, no Python 3.12.3, com 4 CPUs. O `PreToolUse` e o `UserPromptSubmit` sobem o `timeout` de 10 s para 30 s, para dar folga em máquina lenta: o hook que estoura é cancelado, o prompt perde a `resposta` e o `PreToolUse` deixa a ferramenta passar sem a guarda.
- O `--em` aceita o caminho a partir da raiz do repositório ou o nome curto, quando ele é único entre os arquivos que o git não ignora, com commit ou sem. O `--origem` não muda.
- O dossiê traz o bloco de Rulings completo, com os prováveis alvos, e o resumo ganha a contagem `prováveis alvos`.

Não há passo de migração: o limite novo dos hooks chega com a troca de versão do plugin.

## v0.2.2 — 2026-11-06

O plugin deixa de trazer o produto de um cliente: as fixtures, os testes e os exemplos passam a um produto fictício, e o texto gerado do planejamento fica neutro.

### O que mudou desde a 0.2.1

- O texto gerado do planejamento troca quatro frases que só valiam para um projeto: a dos atritos, a do commit, a do pacote e a do aviso do hook. A do commit passa a dizer "o commit convencional do projeto": o `CLAUDE.md` do projeto, na parte que o projeto escreve, passa a dizer a própria convenção de commit.
- As fixtures e os testes usam o produto fictício das fixtures da trilha de desenvolvimento, uma biblioteca, no perfil, no DER, nas fixtures do `checar` e dos diagramas e nas strings dos testes. Sai a fixture do `CLAUDE.md` da tag do porte.
- Os exemplos das referências `spec-curta.md` e `spec-normal.md` do `planejar-bloco` e o exemplo do molde `requisitos-negocio.md` usam o mesmo produto fictício.

Não há passo de migração: o texto gerado muda no próximo `harness.py gerar`.

## v0.2.1 — 2026-11-06

A trilha de desenvolvimento fica pronta para a prova de um serviço chamado por POST, com corpo, cabeçalho e segredo no endereço.

### O que mudou desde a 0.2.0

- A prova por POST na `## Verificação externa` da spec do bloco: a linha da prova passa a ser `<alias> GET|HEAD|POST <caminho> -> <código>`, e o item ganha o subitem opcional `pedido:`, com um bloco JSON de `cabecalhos` (nos três métodos), `corpo` (só no POST) e `campos` (no GET e no POST, na notação `itens[].situacao`, com `"*"` para presente e não nulo). O segredo entra pelo marcador `{env.NOME}`, no caminho, nos cabeçalhos e nos textos do corpo: o valor vem do ambiente do processo ou dos arquivos de env da lane, e nunca vai para a saída, para o `aceitacao.md` nem para um commit. A falha de campo não mostra valores. A conferência lê o pedido da spec aprovada, na lane e no `lane fechar`, e recusa a spec que mudou depois da aprovação.
- O `lane fechar` recusa remover a lane em que a sessão do Claude Code foi aberta (`CLAUDE_PROJECT_DIR`), mesmo quando o comando roda da árvore principal.

Não há passo de migração: as provas GET e HEAD de hoje seguem valendo.

## v0.2.0 — 2026-11-05

O harness inteiro no plugin, nas duas trilhas, com o núcleo das fases 5 e 6 do projeto em que ele nasceu. O plugin passa a se chamar `ela-harness`.

### O que mudou desde a 0.1.0

- O plugin `harness` vira `ela-harness` (`ela-harness@ela-harness`). As skills passam a `/ela-harness:<skill>` e os agentes a `ela-harness:<agente>`, no lugar de `/harness:<skill>`.
- Duas trilhas, que o `[projeto] harness` do perfil escolhe: `planejamento`, que ganha a camada 3 e o G3, a passagem e o gerador, e `desenvolvimento`, que conduz blocos de código por lanes, revisões e PR. Sem a chave, vale o planejamento.
- O núcleo sai de `harness/` e vai para três pastas: `nucleo/comum/`, `nucleo/planejamento/` (com as `ferramentas/`: o validador Mermaid e o `bancos.py`) e `nucleo/desenvolvimento/`. O `harness/gancho.py` do 0.1.0 é hoje o `nucleo/comum/gancho.py`.
- Oito skills (`iniciar`, `refinar-documento`, `gate-fase`, `assessor`, `planejar-bloco`, `executar-bloco`, `revisar-bloco` e `finalizar-bloco`), doze agentes e o workflow `revisao-do-bloco`. O plugin `ela-harness-papeis`, segundo plugin do marketplace, traz o mod que troca o modelo e o esforço dos agentes do ciclo do bloco.
- Os hooks (`SessionStart`, `PreToolUse`, `UserPromptSubmit` e `Stop`) vêm do `hooks/hooks.json` e rodam o comando da trilha. Ficam calados em projeto sem `.claude/perfil.toml`. O gancho refaz, a cada sessão, o link `.claude/harness/nucleo` para a raiz do plugin.
- O lançador `.claude/harness/harness.py` acha o núcleo pela `HARNESS_NUCLEO`, pelo link, pelo link da árvore principal (numa lane, que é uma worktree) e pelo registro de plugins. Sem núcleo, sai com 3 e mostra como instalar.
- O `iniciar` é `harness.py iniciar <trilha> [<pasta>] [--nome <nome>]`, e a skill é `/ela-harness:iniciar <trilha> [nome]`. Copia o modelo da trilha e o lançador sem sobrescrever (o que já existe fica, com `mantido:`), troca `{{PROJETO}}`, `{{DATA}}` e `{{ramo_principal}}`, liga o `core.hooksPath`, instala os plugins com `--scope project` e, no planejamento, roda o `gerar`. Não copia mais o núcleo, as skills, os agentes nem o mod. O `iniciar --conferir` confere a instalação.
- O texto do ciclo do planejamento é gerado: o `gerar` grava `.claude/harness/gerado/planejamento.md` a partir do perfil, e o `CLAUDE.md` do projeto o puxa pela linha `@.claude/harness/gerado/planejamento.md`. A guarda recusa a edição à mão dessa pasta. O `[ids]` do perfil ganha a chave opcional `formas`.
- Os modelos são `modelo/planejamento/` e `modelo/desenvolvimento/`. O `.claude/settings.json` deles fixa o marketplace na tag da versão e liga os plugins; os hooks saem dele.
- O manual vai para `docs/`, com a pesquisa, as specs, os planos, os atritos e o glossário em `docs/harness-planejamento/`. O `docs/pesquisa/` do 0.1.0 sai, e o histórico dele fica no git.
- Num projeto cujo `.claude/settings.json` já existe (o `claude plugin install --scope project` o cria), o `iniciar` mescla o que falta do modelo e diz `mesclado: .claude/settings.json`, sem tirar nada.
- O `moldes-intocados` aceita o molde acrescentado quando a base não tem arquivo na pasta de moldes, o que deixa o primeiro commit do repositório montado passar.

A instalação `--scope project` vale por pasta: cada clone novo roda uma vez o `claude plugin install <id> --scope project` de cada plugin da trilha (o lançador mostra o comando).

### Migrar um projeto de planejamento

Para levar à 0.2.0 um projeto que roda o núcleo copiado em `.claude/`:

1. Troque o `.claude/harness/*.py` pelo lançador: apague de `.claude/harness/` os módulos, as `ferramentas/`, os `tests/`, o `modelo/`, o `desenvolvimento/` e o `saida.md`, e copie o `modelo/lancador.py` para `.claude/harness/harness.py`. Os comandos `python3 .claude/harness/harness.py ...` seguem os mesmos. A `aprovacao/` e o `dossie/` ficam.
2. Tire de `.claude/` as skills, os agentes e o manual: `.claude/skills/`, `.claude/agents/`, `.claude/README.md` e `.claude/docs/`.
3. Tire os hooks do `.claude/settings.json`: eles vêm do plugin. As permissões (`deny` e `ask`) e o `skillOverrides` ficam.
4. Fixe o marketplace e o plugin: no `.claude/settings.json`, acrescente o `extraKnownMarketplaces.ela-harness` (fonte `github`, repositório `Ela-Decora/ElaHarness`, `ref` `v0.2.0`) e o `enabledPlugins` com `ela-harness@ela-harness`, como em `modelo/planejamento/`, e rode os comandos de instalação do [README](README.md#instalar). Ponha `.claude/harness/nucleo` e `.harness-nucleo/` no `.gitignore`.
5. Puxe o gerado no `CLAUDE.md`: acrescente a linha `@.claude/harness/gerado/planejamento.md`, tire do texto o que o gerado já traz (o mapa do harness, o ciclo, os IDs e os marcadores, o que não fazer no ciclo, os gatilhos e o que preservar ao compactar) e troque os nomes das skills por `/ela-harness:<skill>`. Rode `harness.py gerar`.
6. Ajuste a CI: o workflow de `modelo/planejamento/.github/workflows/harness.yml` baixa o plugin na versão fixada, define a `HARNESS_NUCLEO` e roda o `harness.py invariantes --base`. Saem do workflow do projeto o job que rodava a suíte de `.claude/harness/tests/` (`harness (3.9)` e `harness (3.12)`) e o job `diagramas`, que usava o `npm ci --prefix .claude/harness/ferramentas`, o `validar-mermaid.mjs`, as fixtures de `tests/` e o `ferramentas/bancos.py`, todos apagados no passo 1: pelo §11.1 da spec do porte, o validador Mermaid e o `bancos.py` rodam na CI do plugin, sobre as fixtures dele. No projeto, o Mermaid de cada documento se valida com Node, local, pelo `validar-mermaid.mjs` do plugin (o reference `camada-3.md` traz o comando).

### Histórico

O histórico anterior à `v0.2.0` fica no repositório de origem.

## v0.1.0 — 2026-10-14

Primeira versão como plugin, extraída do projeto em que o harness nasceu (fases 1 a 4c).

- O núcleo (`harness/`), as skills e os agentes passam a morar no plugin `harness`, do marketplace `ela-harness`.
- Os hooks vêm do `hooks/hooks.json` do plugin, pelo `harness/gancho.py`, calados em projeto sem `.claude/perfil.toml`.
- O projeto guarda só o lançador `.claude/harness/harness.py`, que acha o núcleo pela `HARNESS_NUCLEO`, pelo link
  `.claude/harness/nucleo` ou pelo registro de plugins; os comandos `python3 .claude/harness/harness.py ...` seguem os
  mesmos.
- Comando `iniciar` e skill `/harness:iniciar`: criam o projeto a partir do `modelo/`.
- A raiz do projeto, sem `CLAUDE_PROJECT_DIR`, é procurada a partir da pasta atual, não mais do arquivo do núcleo.
- As skills passam a ser `/harness:refinar-documento`, `/harness:gate-fase` e `/harness:assessor`.

Para levar um projeto que tinha o núcleo copiado: apague `.claude/harness/*.py` e `tests/`, `.claude/skills/`,
`.claude/agents/`, `.claude/README.md` e `.claude/docs/`; copie o lançador, o pre-commit, o workflow e as linhas do
`.gitignore` do `modelo/`; tire os hooks do `.claude/settings.json` e acrescente `extraKnownMarketplaces` e
`enabledPlugins` como no modelo; troque os nomes das skills no `CLAUDE.md`.
