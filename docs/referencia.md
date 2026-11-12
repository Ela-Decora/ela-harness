# Referência do harness

Gerado por `harness.py referencia --gravar`. Não edite este arquivo: mude a `AJUDA` no módulo do comando e gere de novo.

## Convenções

- Saída 0: deu certo. Saída 1: recusa, falha de verificação ou erro de entrada. Nenhum comando sai com 2.
- Toda recusa sai com 1 e diz o motivo na primeira linha, às vezes com detalhes nas linhas de baixo. A maior parte
  começa por um prefixo: `recusado:`, `uso inválido:`, `perfil inválido:`, `erro:` ou `erro de arquivo:`. Saem sem
  ele as recusas de entrada do `checar`, do `molde`, do `dossie` e do `versao`, menos as do `versao diff`, e as
  pré-condições do `gate`; o `estado` sem ação e o `proximo` saem com `STATUS.md inválido: ...`, e o `backlog ids`,
  com `backlog.md ilegível: ...`.
- Saem sempre com 0, porque são injetados e não podem abortar a sessão nem a skill: `estado --hook`,
  `perfil --para` e `guarda`. Neles, o erro vem no texto: `ERRO no hook: ...`, `ERRO: ...` e
  `guarda do harness com erro, sem decisão: ...`.
- A saída é sempre UTF-8, mesmo com o locale `C`.
- Todo caminho de documento é relativo à raiz do projeto, ou absoluto.
- `harness.py` abrevia `python3 .claude/harness/harness.py`, rodado da raiz do projeto.
- Cada comando e cada ação têm `--help`: `harness.py <comando> --help` mostra o uso, os argumentos, as opções e o
  texto do comando, e `harness.py <comando> <ação> --help`, os da ação.
- As mensagens do próprio argparse ficam em inglês depois de `uso inválido:`, como
  `the following arguments are required`.

## Conceitos

| Termo | O que é |
|---|---|
| **Fase** ou **camada** | Um nível do planejamento, com uma pasta própria dentro da pasta do planejamento (`caminhos.planejamento`), com o nome do `id` da fase, e uma regra de escrita. As fases ficam em `fases` no perfil, na ordem; a atual, no campo `Fase` do STATUS.md. |
| **Gate** | Ponto de aprovação que fecha uma fase: o `gate` da fase no perfil. O checklist fica em `gates.<gate>.itens`, com itens de script, de revisor, de leitor frio e humanos; a situação de cada gate, na linha dos gates do STATUS.md. |
| **Regra da camada** | A restrição de escrita da fase, na chave `regra` dela no perfil. O bloco "Este projeto" das skills a mostra. |
| **Documento** | Um arquivo `.md` de planejamento dentro da pasta de uma fase. O STATUS.md acompanha um documento ou um pacote por vez, no campo `Documento`. |
| **Pacote** | Documentos que passam juntos pelo ciclo, com uma checagem, um revisor e uma aprovação para todos. A lista fica no campo `Pacote` do STATUS.md, e o `Documento` é o primeiro dela. |
| **Molde** | O arquivo da pasta de moldes (`moldes.pasta`) que dá a forma do documento. Vale o primeiro par do `mapa` do perfil (`moldes.mapa`) cujo padrão casa com o caminho do documento relativo à pasta do planejamento; sem par, o do mesmo caminho relativo. Os títulos do molde são o contrato do documento. |
| **Ciclo** | Os oito passos, de 0 a 7, por que passa cada documento ou pacote; o 0 é a preparação. O passo atual fica no campo `Passo` do STATUS.md. |
| **Rodada** | Uma volta de perguntas da entrevista (passo 2), até 4 perguntas numa chamada da ferramenta de opções, ou uma volta do revisor (passo 5), no máximo 2. Fica no campo `Rodada` e recomeça em 1 no passo 5. |
| **Fonte** | De onde vem o conteúdo, em ordem de precedência: as decisões registradas e o `CLAUDE.md`, depois o rascunho, depois as pastas de `caminhos.fontes`, na ordem do perfil. |
| **`[A CONFIRMAR: motivo]`** | Marca de inferência do modelo. No passo 4, cada uma vira pergunta da ferramenta de opções: confirmada, a marca sai e o texto fica; "tirar", o trecho sai; corrigida, o trecho é reescrito sem marca. Ficam de fora as que citam uma pendência, "pesquisa pendente" ou "pergunta aberta". O `checar` conta as marcas, mas não falha por elas. |
| **Ruling** | Decisão que vale além de um documento, registrada no arquivo de decisões (`caminhos.decisoes`) como `Ruling: o quê — por quê — custo se errado`, por `harness.py registrar ruling`. |
| **Pendência** | Linha `<prefixo>-NN` da tabela de pendências do backlog.md (`caminhos.backlog`), com origem, destino e status; o prefixo é o `ids.prefixo_pendencia`. A pendência aberta com o marcador do gate no destino (`gates.<gate>.marcador_pendencia`) bloqueia o gate. |
| **Relato** | Informação nova que surge na conversa, acrescentada por `harness.py registrar relato` à seção de informação nova do rascunho (`caminhos.rascunho`) como `<prefixo>-NN`, com o prefixo de `ids.prefixo_relato`. Entra confirmada ou não confirmada e fica pendente até ser incorporada a um documento ou descartada. |
| **Artefato** | Linha da tabela de artefatos do backlog.md: caminho, camada, status (`rascunho`, `em-revisao` ou `aprovado`) e data. O gate exige todos os documentos da fase como `aprovado`. |
| **Versão em aprovação** | Hash `sha256:` de 12 dígitos do documento apresentado no passo 6, ou do manifesto do pacote, gravado no campo `Versao-aprovacao`. Protege a versão aprovada até o commit. |
| **Estudo** | Arquivo do assessor que compara opções de uma decisão, com critérios, fontes, recomendação e a decisão do usuário, na pasta `caminhos.estudos`. |
| **Modo revisão** | O ciclo de um documento já `aprovado` que volta para correção: os mesmos passos, cada um só no escopo da pendência ou do pedido. O `Proximo` de cada passo começa por `modo revisão:`. |
| **Relatório de pesquisa** | O que o agente `pesquisador-fatos` devolve, guardado numa pasta `pesquisa-<documento>-<AAAA-MM-DD>/` dentro de `caminhos.pesquisas`. Antes de um despacho novo, o modelo procura relatório que já responda. Entra no commit do documento. |
| **Atrito** | Falha ou incômodo observado no uso do harness, registrado no arquivo de atritos (`caminhos.atritos`). É o que justifica uma peça nova. |

## Comandos

| Comando | O que faz |
|---|---|
| [`estado`](#estado) | valida e imprime o STATUS.md |
| [`backlog`](#backlog) | confere o backlog do planejamento, conta as causas, resolve uma pendência ou troca o destino dela |
| [`checar`](#checar) | confere documentos de planejamento contra o molde |
| [`dossie`](#dossie) | monta as fontes de cada documento num arquivo fora do git |
| [`afetados`](#afetados) | lista quem cita um ID ou um termo, pelo status do documento |
| [`registrar`](#registrar) | acrescenta no ato um Ruling, uma pendência, uma nota, um relato ou um registro do passo 7 |
| [`passo`](#passo) | fecha um passo do ciclo: grava o STATUS.md e o status do artefato |
| [`migrar`](#migrar) | migra os documentos aprovados para a forma da versão do plugin e abre o lote de migração |
| [`molde`](#molde) | imprime o molde de um documento de planejamento |
| [`der`](#der) | gera e confere o DDL e o diagrama do DER físico |
| [`versao`](#versao) | marca, confere e limpa a versão enviada para aprovação |
| [`perfil`](#perfil) | valida e resume o perfil do projeto (.claude/perfil.toml) |
| [`gate`](#gate) | roda os itens de script do checklist de um gate de fase |
| [`legenda`](#legenda) | gera a legenda das siglas e dos tipos de ID a partir dos documentos |
| [`passagem`](#passagem) | exporta, testa pelo leitor frio e publica a passagem do planejamento |
| [`estudos`](#estudos) | lista os estudos do assessor e a situação da decisão de cada um |
| [`invariantes`](#invariantes) | confere pelo git as invariantes da trilha do perfil, com os segredos |
| [`proximo`](#proximo) | diz o próximo passo pelo estado e pela tabela de artefatos |
| [`fechar`](#fechar) | fecha o ciclo depois do commit, conferindo a versão no HEAD, e leva o STATUS.md ao commit |
| [`ambiente`](#ambiente) | diz o que falta nesta máquina: Python e TOML, pre-commit e árvore |
| [`guarda`](#guarda) | hooks PreToolUse, UserPromptSubmit e Stop (payload no stdin) |
| [`iniciar`](#iniciar) | inicia um projeto de planejamento ou de desenvolvimento pelo modelo do plugin |
| [`gerar`](#gerar) | gera os arquivos do harness a partir do perfil e, no código, da passagem |
| [`referencia`](#referencia) | gera a referência dos comandos, das skills e agentes e do núcleo |

## estado

valida e imprime o STATUS.md

`harness.py estado [--hook] [<ação>]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `--hook` | não | imprime o bloco do SessionStart (sempre sai com 0); não combina com set |

Valida e imprime o STATUS.md, o estado curto do planejamento (`caminhos.status`), e muda um campo dele por vez.

Sem ação, imprime o arquivo em texto canônico e sai com 0; espaço no fim da linha, linha em branco e quebra de linha
do Windows passam. Arquivo inválido sai com 1 e `STATUS.md inválido: <erro>; <erro>`. O formato é o título fixo e um
campo por linha, nesta ordem, em até 2.000 caracteres; os gates do perfil ficam numa linha só, na ordem das fases, e o
`Pacote` e o `Lote`, opcionais, vêm logo depois do `Documento`, nessa ordem. Um projeto novo começa assim:

```text
# Status do planejamento
Fase: <fase>
Documento: nenhum
Passo: 0
Rodada: 0
Proximo: <o que vem a seguir, numa linha>
<gate>: pendente | <gate>: —
Versao-aprovacao: —
Atualizado: <AAAA-MM-DD>
```

`estado set <campo> <valor>` valida, grava de forma atômica, atualiza o `Atualizado` e imprime `<campo> = <valor>`,
com cada mudança automática numa linha a mais. Recusa sai com 1 e `recusado: <motivo>`, sem tocar o arquivo.

| Campo | Valor aceito |
|---|---|
| `Fase` | o `id` de uma fase do perfil |
| `Documento` | `nenhum`, ou um `.md` dentro da pasta do planejamento, com caminho normalizado e sem espaço |
| `Pacote` | de 2 a 6 caminhos como o do `Documento`, separados por um espaço, sem repetição; `—` tira a linha |
| `Lote` | `<prefixo de pendência>-NN (<N> documentos)` ou `migração v<de>→v<para> (<N> documentos)`, com `(1 documento)` no singular; só pelo `estado lote`, pelo `migrar` e pelo `fechar` |
| `Passo` | inteiro de 0 a 7 |
| `Rodada` | inteiro maior ou igual a 0 |
| `Proximo` | uma linha, até 200 caracteres |
| `<gate>` | `pendente`, `—` ou `aprovado em AAAA-MM-DD` |
| `Versao-aprovacao` | `—` ou `sha256:` e 12 hexadecimais; só pelo `versao`, pelo `passo 6` e pelo `fechar` |
| `Atualizado` | automático; o `set` recusa |

- A `Fase` não pula fase nem avança sem o gate atual `aprovado em ...`; voltar é aceito. O gate `—` da fase nova
  vira `pendente` na mesma gravação.
- `Documento` de fase posterior à `Fase` é recusado, com o pedido de aprovar o gate ou de avançar a `Fase`. Trocar o
  `Documento` ou o `Pacote` com versão marcada é recusado até `versao limpar`.
- O `Pacote` grava também o `Documento`, o primeiro da lista, e a trava de fase vale para cada documento dele.
  `Documento nenhum` tira o `Pacote`; outro `Documento` com pacote aberto é recusado.
- A lista dos documentos do `Lote` fica fora do STATUS.md, no arquivo `lote` da pasta da aprovação
  (`.claude/harness/aprovacao/lote`), um caminho por linha, e o `Documento` é o primeiro dela. O `Lote` e o `Pacote`
  não se abrem juntos. `Documento nenhum` tira também o `Lote` e deixa o arquivo, que sem o campo ninguém lê.
- O `set` do `Lote` é recusado com `recusado: Lote muda só por estado lote, migrar ou fechar`.
- `estado lote <prefixo>-NN <caminho>...` abre o lote da pendência aberta: confere que o destino dela cita cada
  caminho pelo nome do arquivo, sem os trechos `antes do`, e recusa, de uma vez, os que ele não cita, com
  `<caminho> não está no destino da <ID>`, e os que não estão aprovados na tabela de artefatos, com `<caminho> não
  está aprovado; o lote só revisa aprovados`, uma linha `recusado:` cada. Os caminhos entram em ordem de camada e, na
  camada, na ordem do destino, qualquer que seja a ordem passada; o que o destino não cita não entra. Grava a lista, o
  `Lote` e o `Documento` (o primeiro) e imprime o `Lote`, o `Documento` e um caminho por linha. `estado lote --tirar
  <caminho>` tira um documento do lote aberto, e o lote seguinte nunca fica vazio.
- O `set` do `Versao-aprovacao` é recusado com
  `recusado: Versao-aprovacao muda só por versao marcar, versao limpar, passo 6 ou fechar`.
- Valor vazio, com espaço no fim ou com quebra de linha é recusado; o que começa por `-` vai depois de `--`. Valor
  inválido noutro campo não impede a mudança, e os inválidos se corrigem um `set` por vez.
- Estrutura quebrada (título, campo ausente, repetido ou fora de ordem, linha dos gates) é recusada com
  `corrija à mão`: quem corrige é uma pessoa, porque o modelo não edita o arquivo.
- Cada `set` regrava o arquivo inteiro: encadeie vários com `&&`, nunca em chamadas paralelas.
- Cada gravação do STATUS.md pelo harness (`estado set`, `passo`, `versao` e `fechar`) grava também o
  `sha256:<hash>` do texto gravado no arquivo `harness-status` do diretório do git da cópia, que o
  `status-pelo-harness` do pre-commit compara; a falha nessa gravação não muda o resultado do comando.

Com `--hook`, imprime numa linha o JSON do início da sessão e sai sempre com 0; o `source` do payload no stdin diz de
onde a sessão vem. O `systemMessage` é o aviso ao usuário, no formato do molde "Linha do início da sessão" do
`nucleo/comum/saida.md`, e não sai depois de compactar. O `additionalContext` é o contexto do modelo, em até
2.000 caracteres, com:

1. o STATUS.md em texto canônico; num pacote, a linha do `Documento` ganha `(+<N> no pacote)`, e num lote,
   `(+<N> no lote)`; com a lista do lote ilegível, vem logo depois dele a linha `ERRO na lista do lote: <motivo>`;
2. `Pendências abertas: <n> (<backlog>)`, com `—` quando o backlog falta ou não se lê;
3. `[A CONFIRMAR] no documento atual: <n>`, ou `[A CONFIRMAR] no pacote: <n>` ou `no lote: <n>`, com `—` sem
   documento legível;
4. `Estudos com decisão por registrar: <n> (<pasta>)`, com os ilegíveis, só quando há algum;
5. `Últimos commits:` e as três linhas do `git log --oneline`, ou `Últimos commits: indisponível`;
6. `Próximo: <ação> (<motivo>)`, como no `harness.py proximo`, e `Depois:` com até duas ações da fila;
7. as linhas `FALHA` e `AVISO` do `harness.py ambiente`, só quando há.

Com o STATUS.md inválido, o contexto começa por `ERRO no STATUS.md: <motivo>.` e a correção, o `estado set` ou
`Peça ao usuário para corrigir o arquivo à mão`, seguidos do texto bruto, e o aviso é
`Planejamento: STATUS.md inválido: <motivo>`. Com o item do Python em `FALHA` no `ambiente`, como sem leitor de TOML,
o contexto e o aviso são a linha dele: `FALHA: Python <versão> sem leitor de TOML: pip3 install --user tomli`. Com
perfil inválido ou erro inesperado, o contexto é `ERRO no hook: <motivo>`, e o aviso,
`Planejamento: erro no início da sessão: <motivo>`.

### estado set

muda um campo do STATUS.md, validando antes de gravar

`harness.py estado set <campo> <valor>`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<campo>` | sim | nome do campo, como Passo ou um gate |
| `<valor>` | sim | o valor novo, numa linha |

### estado lote

abre o lote de uma pendência com os documentos que o destino cita, ou tira um dele

`harness.py estado lote [<argumento>...] [--tirar]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<argumento>...` | não | &lt;prefixo>-NN e os caminhos dos documentos; com --tirar, só o caminho a tirar |
| `--tirar` | não | tira o documento do lote aberto |

## backlog

confere o backlog do planejamento, conta as causas, resolve uma pendência ou troca o destino dela

`harness.py backlog <ação>`

Confere os IDs das pendências do backlog.md (`caminhos.backlog`) e conta as abertas e as causas, resolve uma
pendência ou troca o destino dela.

`backlog ids` sai com 0 e `OK: <total> pendências, <abertas> abertas`. Com erro, sai com 1 e um por linha: primeiro
`ID fora do formato <prefixo>-NN em L<n>`, pela linha; depois `ID duplicado: <prefixo>-NN (L<n> e L<m>)` e
`buraco na sequência: faltam <prefixo>-NN a <prefixo>-NN` (ou `falta <prefixo>-NN`), pelo número. O ID tem dois ou
mais algarismos, de 01 ao maior, e `<prefixo>-001` é o mesmo que `<prefixo>-01`; a ordem das linhas não importa.
Backlog ausente ou ilegível: `backlog.md ilegível: <motivo>`, com 1.

`backlog causas` conta as pendências pela causa que o `registrar pendencia` grava no fim da Origem, com `causa:
<causa>` depois da data. Sai com 0 e uma linha `<causa>: <total> (<abertas> abertas)` por causa presente, na ordem das
causas, depois `sem causa` quando houver, e `Total: <total> pendências, <abertas> abertas`. As recusas são as do
`backlog ids`: backlog ausente ou ilegível e IDs com erro, com 1.

`backlog resolver <prefixo>-NN --em <documento> "<como>"` troca só a célula de status da pendência aberta por
`resolvida em <nome do arquivo do documento>, <AAAA-MM-DD>: <como>`, com `; histórico: <status antigo>` no fim
quando o status era `aberta; <nota>`, e imprime `<prefixo>-NN resolvida em <arquivo>:<linha>`, com o ID como está
no backlog. O ID casa pelo número: `<prefixo>-3` acha a `<prefixo>-03`. Recusa sai com 1 e `recusado: <motivo>`, sem gravar: o `como` vazio,
com quebra de linha ou com `|`; o `--em` fora do repositório, que não existe ou ambíguo, com os candidatos abaixo, um
por linha; os IDs com erro, que vêm abaixo como no `backlog ids`; `<prefixo>-NN não está no backlog`;
`<prefixo>-NN não está aberta: <status>`.

`backlog destino <prefixo>-NN "<destino>"` troca só a célula de destino da pendência aberta e acrescenta
`; <AAAA-MM-DD>: destino era <destino antigo>` ao fim do status, para a pendência seguir ao que resta quando parte
dela se resolveu. Imprime `<prefixo>-NN com destino <destino> em <backlog>:<linha>`. O ID casa pelo número. Recusa sai
com 1 e `recusado: <motivo>`, sem gravar: o `destino` vazio, com quebra de linha ou com `|`; o destino novo que perde o
marcador de um gate (`gates.<gate>.marcador_pendencia`) que o antigo tinha, sem distinção de maiúsculas, com
`o destino novo perde "<marcador>", que segura o <gate>; na dispensa do gate, use --dispensa "<motivo>"`; o destino
igual ao atual, com `destino: igual ao atual`; o destino novo que cita um documento do lote aberto (o primeiro, na
ordem do lote), com `<documento> está no lote aberto; o que resta dele se resolve neste ciclo`; os IDs com erro,
abaixo como no `backlog ids`; `<prefixo>-NN não está no backlog`; `<prefixo>-NN não está aberta: <status>`;
`<prefixo>-NN não tem a célula de destino`.

`backlog destino --dispensa "<motivo>"` deixa o destino novo perder o marcador do primeiro gate, na ordem do perfil, que
o antigo tinha, e acrescenta `; <AAAA-MM-DD>: dispensada no <gate>: <motivo>; destino era <destino antigo>` ao status. O
`--dispensa` sem marcador perdido é recusado, com `--dispensa só vale quando o destino novo perde o marcador de um
gate`, e o motivo vazio, com quebra de linha ou com `|` também.

O `--em` é o caminho a partir da raiz, como `CLAUDE.md` ou `<pasta do planejamento>/<fase>/<documento>.md`, ou só o
nome do arquivo, quando ele é único entre os arquivos que o git não ignora, com commit ou sem.

Formato: duas tabelas lidas por script; o resto do arquivo é livre. O prefixo é o `ids.prefixo_pendencia`.

```text
| ID | Pendência | Origem | Destino | Status |
|---|---|---|---|---|
| <prefixo>-01 | <pendência> | <documento>, <AAAA-MM-DD>, causa: <causa> | <documento ou fase> | aberta |
| <prefixo>-02 | <pendência> | <documento>, <AAAA-MM-DD> | <destino> | resolvida em <documento>, <AAAA-MM-DD>: <como> |

| Caminho | Camada | Status | Data |
|---|---|---|---|
| <pasta do planejamento>/<fase>/<documento>.md | <número da fase> | rascunho | <AAAA-MM-DD> |
```

- A linha de pendência começa exatamente por `| <prefixo>-`; o ID é a primeira célula, o destino a penúltima e o
  status a última. Status que começa por `aberta` conta como aberta; a linha resolvida fica no arquivo.
- A causa é opcional: a linha sem ela segue válida e conta como `sem causa`. Uma causa fora da lista também conta
  como `sem causa`. Os termos do `rastreio` e do `dossie` não casam pela causa.
- A pendência aberta com o marcador do gate (`gates.<gate>.marcador_pendencia`) no destino, sem distinção de
  maiúsculas, bloqueia o gate.
- A tabela de artefatos vai do cabeçalho exato até a primeira linha que não começa por `|`; crases em volta do
  caminho valem. O status é `rascunho`, `em-revisao` ou `aprovado`; o `harness.py passo` grava os dois últimos.

### backlog ids

confere os IDs das pendências e conta as abertas

`harness.py backlog ids`

### backlog causas

conta as pendências por causa

`harness.py backlog causas`

### backlog resolver

marca uma pendência aberta como resolvida, com o documento e como

`harness.py backlog resolver <pendência> --em <documento> <como>`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<pendência>` | sim | o ID, como &lt;prefixo>-NN |
| `--em <documento>` | sim | o documento que a resolveu: o caminho a partir da raiz, ou só o nome, se for único |
| `<como>` | sim | como foi resolvida, numa linha, sem \| |

### backlog destino

leva o destino de uma pendência aberta ao que resta

`harness.py backlog destino <pendência> <destino> [--dispensa <motivo>]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<pendência>` | sim | o ID, como &lt;prefixo>-NN |
| `<destino>` | sim | o destino novo: os documentos que restam, com os marcadores do antigo |
| `--dispensa <motivo>` | não | o motivo da dispensa do gate, quando o destino novo perde o marcador dele; sem \| |

## checar

confere documentos de planejamento contra o molde

`harness.py checar [<documento>...] [--verbose]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<documento>...` | não | caminho do documento, relativo à raiz do projeto; sem nenhum, os em refino do STATUS.md |
| `--verbose` | não | mostra o detalhe de cada verificação |

Confere cada documento contra o molde dele, em seis verificações e nas regras do perfil que casam com ele, e sai com 1
se alguma falha, menos `a-confirmar` e `aceite-renumerado`.

Sem argumento, confere os documentos em refino do STATUS.md, o `Pacote` ou o `Documento`; sem nenhum, sai com 1 e
`sem documento: passe o caminho ou abra um no STATUS.md`, e com o STATUS.md inválido, `STATUS.md inválido: <motivo>`.
O molde é o que o `harness.py molde` resolve, e os blocos de código cercados por três crases ficam de fora, no
documento e no molde. Uma linha por verificação, nesta ordem: `<nome>: OK`, ou `<nome>: FALHA: <n> ocorrências`,
com `, primeira em L<linha>` quando há linha; o `--verbose` põe o detalhe de cada ocorrência abaixo.
Com mais de um documento, a linha `== <documento>` abre o bloco de cada um, e a recusa de um não para os outros.

- `placeholders`: sobra no texto um padrão de `moldes.placeholders`. Detalhe: `L<linha>: <trecho>`.
- `titulos`: os títulos de nível 1 a 3 não seguem os do molde, na ordem, já com as trocas de `moldes.trocas_de_nome`;
  o título com uma parte de `moldes.partes_variaveis` aceita o texto no lugar dela e pode se repetir. Detalhe, só da
  primeira divergência: `L<linha>: esperado "<título>", achado "<título>"`, `sem par no documento: <título>` ou
  `L<linha>: título sem par no molde: "<título>"`.
- `ids`: um token com prefixo de `ids.prefixos` fora dos `ids.padroes`, um ID definido duas vezes ou um buraco na
  sequência de um prefixo; o buraco só conta fora dos prefixos de `ids.com_buracos`. O token dentro de código em linha (entre crases, com a abertura e o fechamento do mesmo
  tamanho) não conta como fora do padrão; o ID entre crases ainda conta como citado, em `ids-citados`. Define o ID
  quem o põe no começo de item de lista, de linha de tabela ou de título, ou logo depois da primeira palavra do
  título (`### <palavra> <ID>: ...`), com `**` opcional; o citado no meio do texto não conta. Detalhe:
  `<token> fora do padrão`, `<ID> duplicado`, `falta <ID>` ou `faltam <ID> a <ID>`.
- `ids-citados`: um ID citado sem definição no documento nem num artefato da tabela da fase dele ou de fase anterior;
  fora das pastas de fase, só as definições do próprio documento. Dois IDs do mesmo prefixo separados por ` a `
  formam uma faixa, que vale por cada ID dela; a invertida ou com prefixos diferentes é problema. Detalhe:
  `L<linha>: <ID> citado e não definido`, `L<linha>: faixa invertida: <ID> a <ID>`,
  `L<linha>: faixa com prefixos diferentes: <ID> a <ID>` ou `backlog ilegível: <motivo>`.
- `a-confirmar`: nunca falha; a linha é `a-confirmar: <n>`, a contagem das marcas `[A CONFIRMAR`. Detalhe:
  `L<linha> (<seção>)`.
- `adjetivos-vagos`: um termo de `texto.adjetivos_vagos`, como palavra inteira e sem distinção de maiúsculas; linha
  de citação (`>`) e trecho entre aspas não contam. Detalhe: `L<linha>: <termo>`.

As verificações das regras do perfil vêm depois das seis, cada uma só no documento que casa, pelos `documentos`, com
uma regra dela. Elas rodam também no `checar-aprovados` do `harness.py invariantes`, com o backlog da mesma versão.

- `campos`, das regras `[[campos]]`: em cada seção cujo título começa pelo `titulo` da regra, até o próximo título de
  nível igual ou acima, o campo é o primeiro item de lista que começa pelo rótulo em negrito, com os dois-pontos
  dentro ou fora do negrito. São itens dele o valor na mesma linha e cada item de lista mais recuado abaixo, numerado
  ou não, sem os comentários `<!-- -->`; a linha mais recuada sem marcador continua o item de cima, e a linha em
  branco não corta a lista. Com um campo só, a regra pode pedir de quantos a quantos itens, um ID dos prefixos de
  `cita` em cada item, o `formato` que cada item casa por inteiro e trechos `proibidos`, sem distinção de
  maiúsculas. Detalhe: `L<linha>: seção "<título>" sem o campo <campo>` (ausente ou só com o comentário),
  `L<linha>: <campo> com <k> itens; de <mínimo> a <máximo>` (com `1 item` no singular),
  `L<linha>: item de <campo> sem ID de <prefixos>`, `L<linha>: <campo> fora do formato: <item>` e
  `L<linha>: <campo> com "<proibido>"`. A mesma falha de duas regras sai uma vez.
- `colunas`, das regras `[[colunas]]`: em toda tabela com a `coluna` da regra no cabeçalho, cada linha tem a célula
  dela não vazia e, com `formato`, casando com ele por inteiro. A linha toda vazia fica com o `sobras-de-molde`, a
  célula que falta vale vazia, e a tabela sem a coluna fica de fora. Detalhe: `L<linha>: coluna <coluna> vazia` e
  `L<linha>: coluna <coluna> fora do formato: <célula>`.
- `pendencia-na-linha`, das regras `[[pendencia_na_linha]]`: toda linha fora dos blocos de código e das citações
  (`>`) que tem um dos `termos`, como palavra inteira e sem distinção de maiúsculas, cita uma pendência
  (`ids.prefixo_pendencia`) aberta no backlog; com várias, basta uma. O texto achado entra na mensagem. Detalhe:
  `L<linha>: "<termo>" sem pendência na linha`, `L<linha>: "<termo>" com <pendência>, que não está no backlog`,
  `L<linha>: "<termo>" com <pendência>, que não está aberta: <status>` e, sem linha, `backlog ilegível: <motivo>`,
  só quando alguma linha tem um termo. Fora das pastas de fase, o documento que casa com a regra também lê o
  backlog.

Todo documento de uma pasta de fase, com ou sem `[der]` no perfil, ganha o `links` depois das regras do perfil; na
fase do `[der]`, ele vem entre o `c4` e o `drawio`. O pre-commit não o roda.

- `links`: link relativo fora dos blocos de código e do código em linha, resolvido a partir da pasta do documento,
  sem a âncora `#...` e sem o `?...`, com os `%xx` decodificados; o que começa por `/` parte da raiz, e o que começa
  por `//` é externo. O destino pode vir entre `<...>` e ter um nível de parênteses, como `a(1).md`. A regra é a da
  exportação da passagem, com a caixa de cada parte como no disco: o link que sai da raiz ou não acha o arquivo não
  resolve; o que cai numa chave de `[caminhos]` (`rascunho`, `status`, `decisoes`, `backlog`, `estudos`, `atritos` e
  `leitor_frio`) ou na pasta `.claude`, ou dentro delas, é excluído da passagem; o que cai numa pasta é recusado.
  Detalhe, com o destino como está escrito, sem os `<>`: `L<linha>: link <destino> não resolve`,
  `L<linha>: link <destino> excluído da passagem (<chave>)`, com a chave ou `.claude`, e
  `L<linha>: link <destino> é uma pasta; linke um arquivo`.

Logo depois do `links`, nos mesmos documentos, vêm as verificações das citações; na fase do `[der]`, elas ficam
entre o `links` e o `drawio`. O pre-commit não as roda.

- `citacao-por-linha`: trecho `<caminho>.md:<n>` ou `<caminho>.md:<n>-<m>` fora dos blocos de código, dentro ou fora
  do código em linha, com o `<caminho>` feito de letras, algarismos, `.`, `_`, `-`, `*` e `/`. Fica de fora o
  `caminhos.decisoes`, ou a parte final dele depois de uma `/`: o arquivo só recebe acréscimos, e as linhas dele não
  andam. Detalhe: `L<linha>: <citação> cita por número de linha; cite o ID ou o título da seção`.
- `aceite-renumerado`, que nunca falha: para cada `<ID>.<n>` que outro documento `aprovado` das pastas de fase cita,
  sozinho ou numa faixa `<ID>.<n> a <ID>.<m>`, compara o item `<n>` da seção `### <palavra> <ID>: <nome>` com o do
  documento no HEAD; o item é a posição na primeira lista numerada da seção. Linha: `aceite-renumerado: OK` ou
  `aceite-renumerado: AVISO: <n> ocorrências, primeira em L<linha>`. Detalhe:
  `L<linha>: <ID>.<n>, citado em <documentos>, virou <ID>.<m> desde o HEAD` ou
  `L<linha>: <ID>.<n>, citado em <documentos>, mudou ou saiu desde o HEAD`. Sem o documento no HEAD, passa.

Com a seção `[der]` no perfil, os documentos da fase que contém o `[der].documento` ganham quatro verificações
extras, depois das seis e das regras do perfil; o pre-commit não as roda:

- `sobras-de-molde`, em todos: item de lista vazio, ou item que termina em `:` ou num rótulo em negrito e ficou
  igual ao do molde, sem o comentário e sem conteúdo mais recuado abaixo; linha de tabela com todas as células
  vazias; bloco de três crases do tipo `text` só com linhas em branco. Detalhe:
  `L<linha>: <sobra>; preencha ou apague`, com a sobra `item de lista vazio`, `linha de tabela vazia` ou
  `bloco text vazio`.
- `mermaid`, em todos: bloco de três crases do tipo `mermaid` cuja primeira linha útil, sem as em branco, os
  comentários `%%` e o frontmatter `---`, não começa por `flowchart`, `graph`, `sequenceDiagram`, `classDiagram`,
  `stateDiagram-v2`, `erDiagram`, `C4Context` ou `C4Container`; ou bloco vazio, só com essa linha, `title` e
  comentários, menos o do DER antes do primeiro `der gerar`; ou bloco sem a cerca que fecha, ou com o frontmatter
  `---` sem o segundo `---`, que tomam o lugar das outras conferências do bloco. Detalhe, na linha da cerca:
  `L<linha>: bloco mermaid de tipo <tipo>; use flowchart, graph, ...`, `L<linha>: bloco mermaid vazio`,
  `L<linha>: cerca sem fechamento; feche o bloco com três crases` ou
  `L<linha>: frontmatter --- sem fechamento; feche com outra linha ---`.
- `c4`, em todos, nos blocos `C4Context` e `C4Container`: `Container`, `ContainerDb` ou `ContainerQueue` sem
  tecnologia ou sem descrição; `Person`, `System`, `System_Ext`, `SystemDb` ou `SystemQueue` sem descrição; `Rel` ou
  `BiRel` sem rótulo; o bloco sem nenhum elemento; o bloco sem a lista `Legenda:` logo depois, com ao menos um item.
  O bloco sem a cerca que fecha fica de fora. Detalhe:
  `L<linha>: <Função>(<alias>) sem tecnologia`, o mesmo com `sem descrição`, `L<linha>: <Rel>(<a>, <b>) sem rótulo`,
  `L<linha>: bloco <tipo> sem nenhum elemento` e `L<linha>: bloco <tipo> sem a lista "Legenda:" logo depois`.
- `drawio`, em todos: cada `.drawio` da pasta do documento, sem as subpastas, com XML válido, as células `0` e `1`
  no arquivo, sem compressão, toda aresta com `source` e `target` que existem na página dela e todo vértice com
  rótulo; ao lado, o `.drawio.svg` exportado com a cópia do diagrama, igual ao `.drawio`, página por página, em
  células, estilos, rótulos, ligações e geometria. A página é a posição do `<diagram>` no arquivo, a partir de 1.
  Detalhe, sem linha: `<arquivo>: XML inválido (<motivo>)`, `<arquivo>: sem as células 0 e 1`,
  `<arquivo>: compressed="true"; grave sem compressão`, `<arquivo>: diagrama compactado; grave sem compressão` (sem
  o atributo), `<arquivo>: aresta <id> com source <x>, que não existe`,
  `<arquivo>: aresta <id> sem source; ligue as duas pontas a vértices` (os dois também com `target`),
  `<arquivo>: vértice <id> sem rótulo`, `<arquivo>.svg ausente; exporte em SVG com "Include a copy of my diagram"`,
  `<arquivo>.svg sem a cópia do diagrama; exporte com "Include a copy of my diagram"` e
  `<arquivo>.svg de outra versão do <arquivo> (<k> células diferem, primeira <id>); exporte de novo`. Com duas
  páginas ou mais, `<arquivo>` vira `<arquivo>, página <n>` nas arestas e nos vértices, e a última mensagem termina
  em `primeira <id> na página <n>); exporte de novo`.
- No próprio documento de `[der]`, as do DER (`harness.py der --help`): `der-formato`, os erros de formato,
  `L<linha>: <motivo>`; `der-rastreio`, as regras de rastreio contra o modelo conceitual e os documentos das
  entidades; `der-em-dia`, o que o `der conferir` acusa; `workbench`, o manifesto ausente, de outra versão do DDL
  ou com arquivo listado que não existe. Com o formato inválido, `der-rastreio` e `der-em-dia` falham com
  `formato do DER inválido; corrija o der-formato antes`.

Uma verificação que entrou numa versão do plugin depois da aprovação só avisa no documento `aprovado` na tabela de
artefatos: a linha é `<nome>: AVISO: <n> ocorrências, verificação da v<x>, posterior à aprovação`, sem sair com 1.
Vale quando nenhuma migração registrada no arquivo de decisões chegou à `v<x>`, ou quando a data da aprovação na
tabela é anterior à da migração que chegou. Fora disso, e em documento que não está `aprovado`, falha como as outras.
Nesta versão, nenhuma verificação entra nessa regra. O `checar-aprovados` do pre-commit a segue.

Recusas do documento, numa linha: `documento fora de <pasta>/: <documento>`, `documento não encontrado: <caminho>`,
`molde não encontrado: <caminho>` e as de arquivo fora de UTF-8 ou ilegível.

## dossie

monta as fontes de cada documento num arquivo fora do git

`harness.py dossie [<documento>...] [--verbose]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<documento>...` | não | caminho do documento, relativo à raiz do projeto; sem nenhum, os em refino do STATUS.md |
| `--verbose` | não | imprime o arquivo inteiro no lugar do resumo |

Monta o dossiê de cada documento, as fontes dele achadas por script, num arquivo fora do git, e imprime um resumo.

Sem argumento, usa os documentos em refino do STATUS.md, o `Pacote` ou o `Documento`. Grava
`.claude/harness/dossie/<nome do primeiro documento>.md`, refeito a cada execução; a mesma entrada dá o mesmo
arquivo. O resumo tem até 20 linhas: o arquivo, uma linha por documento com as contagens (com `Rulings novos` e
`prováveis alvos`, no documento com o item 7) e os itens do gate, os IDs sem cobertura e os avisos. Com `--verbose`,
imprime o arquivo inteiro. Para cada documento, o dossiê junta:

1. o contrato: o molde e os títulos de nível 1 a 3 dele;
2. as linhas dos documentos aprovados que linkam o documento ou citam o nome do arquivo dele;
3. os IDs citados nessas linhas, com a linha da definição;
4. os links que o documento faz para outros documentos do planejamento, com o status de cada destino;
5. os termos do documento (o do título de nível 1 e o do nome do arquivo), procurados sem acento: as linhas do
   arquivo de decisões (os Rulings primeiro), das pendências abertas e do rascunho; nos `.md` e `.txt` dos relatórios
   de pesquisa (só as subpastas `pesquisa-*` de `caminhos.pesquisas`) e das fontes (`caminhos.fontes`), cada arquivo
   como `<arquivo>: <n> linhas`; até 15 itens por bloco, com `- [15 de <total>]` no corte (o bloco do item 7 não tem
   corte);
6. os itens de script que valem para ele no primeiro gate ainda não aprovado no STATUS.md, a partir do da fase
   dele, que tenha algum (sem nenhum, o gate da fase, com zero itens; STATUS ausente ou inválido conta como nenhum
   gate aprovado), e, nos itens `ids-cobertos`, os IDs ainda sem citação;
7. no documento `aprovado` ou `em-revisao` na tabela de artefatos, os Rulings do arquivo de decisões com data maior
   que a da aprovação, `<arquivo>:<linha>: <trecho>`, todos, sem corte, na ordem do arquivo. O Ruling em que casa um
   termo do item 5 ou um ID que o documento define, pela busca do `afetados`, sai como
   `provável alvo (<alvos que casaram>): <arquivo>:<linha>: <trecho>`. No `aprovado`, a data é a da tabela, e sem
   data legível nela sai `sem data na tabela de artefatos`, que também vai como aviso ao resumo. No
   `em-revisao`, a data é a da última linha `- <AAAA-MM-DD> ` da seção de aprovações do arquivo de decisões que cita
   o caminho do documento; sem ela, o documento nunca foi aprovado, e o bloco não sai.

Sai com 0 ao gravar; o molde ausente vira aviso. Sai com 1 sem documento, com `STATUS.md inválido: <motivo>` sem
argumento, ou com documento fora da pasta do planejamento (`documento fora de <pasta>/: <documento>`).

## afetados

lista quem cita um ID ou um termo, pelo status do documento

`harness.py afetados <alvo>... [--verbose] [--gravar]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<alvo>...` | sim | um ID de requisito ou de pendência, ou um termo entre aspas |
| `--verbose` | não | mostra todas as linhas, com o trecho |
| `--gravar` | não | grava a saída em .claude/harness/dossie/afetados.txt, para o revisor |

Lista quem cita cada alvo, um ID ou um termo, agrupado pelo status do documento na tabela de artefatos.

O alvo é um ID de requisito (um padrão de `ids.padroes`, `-` e o número), que casa também dentro de uma faixa, um ID
de pendência (`<prefixo>-NN`) ou um termo entre aspas, procurado sem acento e sem maiúscula, como palavra inteira, com
plural em `s` ou `es` e com espaço e hífen tratados como iguais. Procura nos `.md` da pasta do planejamento, fora dos
blocos de código, sem os moldes, o STATUS.md, o backlog, as decisões e o rascunho; nas linhas de Ruling do arquivo de
decisões; e nas pendências abertas do backlog.

Com um ID de pendência, entram também como alvos os IDs de requisito citados na linha dela no backlog, menos a célula
do ID, com as faixas expandidas, depois dos alvos dados e sem repetição. A saída começa por uma linha
`<prefixo>-NN cita: <IDs>` (ou `<prefixo>-NN cita: nenhum ID`) por pendência, na ordem dos alvos, e o resto sai para a
união dos alvos. A pendência que não está no backlog é recusada com `recusado: <prefixo>-NN não está no backlog`,
com 1.

Saída, com 0 mesmo sem citação:

- `<prefixo>-NN cita: <IDs>`, uma por pendência dada;
- `Afetados por <alvos>: <n> linhas em <d> documentos, <r> Rulings, <p> pendências abertas`;
- `Definição: <arquivo>:<linha>`, a linha que define o ID de requisito, ou a da própria pendência;
- os documentos por grupo de status, um `<arquivo>:<linha>` por linha: `aprovado` primeiro, porque pede revisão quando
  o alvo muda, depois `em-revisao`, `rascunho`, os outros status e `fora da tabela`;
- `Rulings (<n>)` e `Pendências abertas (<n>)`, estas com o ID.

Sem `--verbose`, até 20 linhas, e `[20 de <total> linhas; --verbose mostra todas, com o trecho]` quando há mais; com
ele, todas, com a seção e o trecho. Com `--gravar`, a saída vai também para `.claude/harness/dossie/afetados.txt`, para
o revisor, e a última linha é `Gravado: .claude/harness/dossie/afetados.txt`. Alvo vazio: `recusado: alvo vazio`, com 1.

## registrar

acrescenta no ato um Ruling, uma pendência, uma nota, um relato ou um registro do passo 7

`harness.py registrar <ação>`

Acrescenta no ato um Ruling ao arquivo de decisões, uma pendência ao backlog.md, uma nota a uma pendência aberta, um
relato ao rascunho ou um registro do passo 7.

Só o `registrar nota` muda uma linha que já existe, e só a célula de status; as outras ações não tiram nem
alteram linha: a linha nova entra no fim da seção ou da tabela, com a quebra de linha do arquivo,
e a saída diz onde. Recusa sai com 1 e `recusado: <motivo>`, sem gravar: texto vazio ou com quebra de linha, arquivo
ausente ou ilegível, arquivo sem a seção ou a tabela.

`registrar ruling` grava a linha na seção de Rulings do arquivo de decisões (`caminhos.decisoes`), do primeiro título
`## ` com "Ruling" até o próximo título de nível 1 ou 2, e imprime `Ruling acrescentado em <arquivo>:<linha>`. Vale o
Ruling mais recente.

`registrar pendencia` grava a pendência aberta, com o número seguinte ao maior, como última linha da tabela de
pendências do backlog.md, e imprime `<prefixo>-NN acrescentada em <arquivo>:<linha>`. O `--causa` é obrigatório, de
uma lista fixa, e é gravado no fim da Origem. Recusa também `|` no texto, na origem ou no destino, e IDs de pendência
com erro, que vêm abaixo como no `harness.py backlog ids`. Ela vem só de uma das três fontes da escada de
`pendencias.md` do núcleo (a resposta "Abrir pendência", o pedido do usuário no modo revisão, o retorno do código);
antes, a nota numa pendência aberta de mesmo destino.

`registrar nota` acrescenta `; <AAAA-MM-DD>: <nota>` ao fim da célula de status de uma pendência aberta, sem mexer no
resto da linha, e imprime `<prefixo>-NN anotada em <arquivo>:<linha>`. O ID casa pelo número, de modo que `<prefixo>-3`
acha a `<prefixo>-03`. Recusa nota vazia, com quebra de linha ou com `|`, pendência fora do backlog ou que não está
aberta, e IDs com erro. O que sobra noutro documento começa a nota por `resta em <documento>: `. A nota `resta em <documento>` de um documento do lote
aberto é recusada: o que resta dele se resolve no ciclo.

```text
- <AAAA-MM-DD> Ruling: <decisão> — <por quê> — <custo se errado>.
| <prefixo>-NN | <pendência> | <nome do arquivo de origem>, <AAAA-MM-DD>, causa: <causa> | <destino> | aberta |
| <prefixo>-NN | ... | ... | <destino> | aberta; <AAAA-MM-DD>: <nota> |
```

`registrar aprovacao`, `registrar descartada` e `registrar trecho` gravam a linha no fim da seção do arquivo de
decisões cujo título `## ` começa por "Aprovações", "Abordagens descartadas" ou "Trechos do rascunho", até o próximo
título de nível 1 ou 2, e imprimem `Aprovação acrescentada em <arquivo>:<linha>`,
`Abordagem descartada acrescentada em <arquivo>:<linha>` ou `Trecho acrescentado em <arquivo>:<linha>`.

```text
- <AAAA-MM-DD> <texto>
```

`registrar medicao` grava a linha no fim da primeira tabela `| Medição | Valor | Data |` da seção do arquivo de
atritos (`caminhos.atritos`) cujo título `## ` começa por "Medições dos ciclos", e imprime
`Medição acrescentada em <arquivo>:<linha>`. Recusa também `|` na medição ou no valor.

```text
| <medição> | <valor> | <AAAA-MM-DD> |
```

`registrar relato` grava na seção `## Informação nova da conversa` do rascunho (`caminhos.rascunho`), criada no fim
quando falta. Com o texto e `--origem`, acrescenta o relato e imprime `<prefixo>-NN acrescentado em <arquivo>:<linha>`;
com `--id` e `--status`, acrescenta uma linha de status, sem mudar a do relato, e imprime
`<prefixo>-NN: <status> (<arquivo>:<linha>)`. As duas formas juntas, ou nenhuma inteira, são uso inválido. O prefixo
é o `ids.prefixo_relato`, `REL` sem ele.

```text
- <AAAA-MM-DD> <prefixo>-NN: <relato> (<nome do arquivo de origem>) — não confirmada
- <AAAA-MM-DD> <prefixo>-NN: incorporada em <nome do documento>
```

- O relato entra `não confirmada`, ou `confirmada` com `--confirmada`, e fica pendente até ser incorporado ou
  descartado.
- O status é `confirmada` (recusado se já está), `incorporada` (pede `--em`, um arquivo do repositório que existe;
  cada documento o incorpora uma vez) ou `descartada` (pede `--motivo`; o relato descartado não muda mais).
- O `--origem` fica dentro da pasta do planejamento. O `--em` é o caminho a partir da raiz, ou só o nome do arquivo,
  quando ele é único entre os arquivos que o git não ignora; fora do repositório, ausente ou ambíguo, é recusado.

### registrar ruling

acrescenta um Ruling à seção de Rulings das decisões

`harness.py registrar ruling <decisão> --por <por> --custo <custo>`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<decisão>` | sim | o quê, numa linha |
| `--por <por>` | sim | por quê |
| `--custo <custo>` | sim | o custo se estiver errada |

### registrar pendencia

acrescenta uma pendência aberta à tabela de pendências

`harness.py registrar pendencia <pendência> --origem <origem> --destino <destino> --causa {entrevista,pesquisa,pesquisa-sem-fonte,revisor,ruling,cascata,gerar-modulos,camada-3,gate,leitor-frio,harness,triagem,prototipo,pedido,codigo,outro}`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<pendência>` | sim | a pendência, numa linha, sem \| |
| `--origem <origem>` | sim | o documento de onde ela veio |
| `--destino <destino>` | sim | o documento ou a camada que a resolve |
| `--causa {entrevista,pesquisa,pesquisa-sem-fonte,revisor,ruling,cascata,gerar-modulos,camada-3,gate,leitor-frio,harness,triagem,prototipo,pedido,codigo,outro}` | sim | o que abriu a pendência, da lista do núcleo: entrevista, pesquisa, pesquisa-sem-fonte, revisor, ruling, cascata, gerar-modulos, camada-3, gate, leitor-frio, harness, triagem, prototipo, pedido, codigo, outro |

### registrar nota

acrescenta uma nota datada ao status de uma pendência aberta

`harness.py registrar nota <pendência> <nota>`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<pendência>` | sim | o ID, como &lt;prefixo>-NN |
| `<nota>` | sim | a nota, numa linha, sem \|; o que sobra noutro documento começa por resta em &lt;documento>: |

### registrar relato

acrescenta informação nova da conversa ao rascunho, ou muda o status de um relato

`harness.py registrar relato [<relato>] [--origem <origem>] [--confirmada] [--id <id>] [--status {confirmada,incorporada,descartada}] [--em <em>] [--motivo <motivo>]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<relato>` | não | a informação nova, numa linha |
| `--origem <origem>` | não | o documento em discussão quando ela surgiu |
| `--confirmada` | não | o usuário já confirmou |
| `--id <id>` | não | o relato cujo status muda |
| `--status {confirmada,incorporada,descartada}` | não | o status novo |
| `--em <em>` | não | o documento em que foi incorporado: o caminho a partir da raiz, ou só o nome, se for único |
| `--motivo <motivo>` | não | por que foi descartado |

### registrar aprovacao

acrescenta uma aprovação, com a data e quem aprovou, à seção de aprovações das decisões

`harness.py registrar aprovacao <aprovação>`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<aprovação>` | sim | o texto, numa linha |

### registrar descartada

acrescenta uma abordagem descartada à seção dela nas decisões

`harness.py registrar descartada <abordagem>`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<abordagem>` | sim | o texto, numa linha |

### registrar trecho

acrescenta um trecho do rascunho já processado à seção dele nas decisões

`harness.py registrar trecho <trecho>`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<trecho>` | sim | o texto, numa linha |

### registrar medicao

acrescenta uma medição à tabela dos ciclos no arquivo de atritos

`harness.py registrar medicao <medição> <valor>`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<medição>` | sim | o que se mediu, numa linha, sem \| |
| `<valor>` | sim | o valor medido, numa linha, sem \| |

## passo

fecha um passo do ciclo: grava o STATUS.md e o status do artefato

`harness.py passo <numero> --proximo <proximo> [--rodada <rodada>]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<numero>` | sim | o passo que começa, de 0 a 7 |
| `--proximo <proximo>` | sim | o que vem a seguir, numa linha |
| `--rodada <rodada>` | não | a rodada; sem ela, 1 nos passos 2 e 5 e 0 nos outros |

Fecha um passo do ciclo: grava `Passo`, `Rodada`, `Proximo` e `Atualizado` no STATUS.md numa escrita só.

Valem as validações e as travas do `estado set`. Sem `--rodada`, a rodada é 1 nos passos 2 e 5 e 0 nos outros. Com
`Documento nenhum`, só o passo 0 é aceito. Valor que começa por `-` vai com `=`, como `--proximo=-texto`.

Efeito além do STATUS.md, nos documentos em refino (o `Pacote`, ou o `Documento`):

- passo 5: status `em-revisao`, com a data de hoje, na tabela de artefatos;
- passo 6: `versao marcar` antes dos campos, do pacote inteiro quando há um;
- passo 7: status `aprovado`, com a data de hoje, só se o `versao conferir` der OK e houver mensagem do usuário
  depois da última marcação (a `resposta` que a guarda grava).

No lote de migração (`Lote: migração v<de>→v<para>`, aberto pelo `migrar`), os passos 5 e 7 não mexem na tabela de
artefatos: os documentos seguem `aprovado`, com a data de antes. O passo 7 grava, no lugar, a linha
`- <data> migração v<de>→v<para>: <N> documentos` na seção de aprovações do arquivo de decisões (o `registrar
aprovacao`), depois das conferências e antes do STATUS.md.

Só o documento numa pasta de fase entra na tabela de artefatos; sem linha, ganha uma no fim dela. Tudo é conferido
antes de gravar; o backlog é gravado antes do STATUS.md e volta ao texto anterior se o STATUS.md não gravar. No
passo 6, a marcação fica se a gravação dos campos falhar depois, e repetir o comando é seguro.

Saída, com 0: `Passo = <n>; Rodada = <r>; Proximo = <texto>`, com `Versao-aprovacao = <hash>; ` antes no passo 6;
uma linha `backlog: <documento> = <status> em <AAAA-MM-DD>` por documento gravado; no passo 7, a mensagem do
usuário que valeu como aprovação, `prova: mensagem das <hora>: «<trecho>»`; e, no lote de migração,
`decisões: migração v<de>→v<para> registrada em <arquivo de decisões>:<linha>`.

Recusas, com 1 e nada gravado, depois de `recusado: `: `com Documento nenhum, só o passo 0 é aceito`;
`a versão em aprovação não confere; nada foi gravado`, seguida da saída do `versao conferir`;
`nenhuma mensagem do usuário depois da última marcação (<hash>); apresente a versão e espere a resposta`;
`STATUS.md inválido: <motivo>`, `backlog ilegível: <motivo>`, `backlog sem a tabela de artefatos (...)`, as do
`estado set` e, no passo 6, as do `versao marcar`, como `arquivo não existe: <documento>`; no passo 7 do lote de
migração, as do `registrar aprovacao`, como a falta da seção de aprovações.

## migrar

migra os documentos aprovados para a forma da versão do plugin e abre o lote de migração

`harness.py migrar [--de <versão>]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `--de <versão>` | não | a versão de partida, como v0.4.0; sem ela, a da última migração registrada no arquivo de decisões |

Migra os documentos aprovados para a forma da versão do plugin carregado e registra a migração.

Só no planejamento, fora de um ciclo. Os documentos são os da tabela de artefatos, nas pastas de fase, com o status
`aprovado`; cada um tem de estar no HEAD, sem mudança fora do commit. A versão de partida é a `--de`, ou a da última
linha `migração v<de>→v<para>` da seção de aprovações do arquivo de decisões; a de chegada é a do plugin.

Aplica as correções de forma cuja versão está entre as duas, e as que valem sempre. Hoje há uma, `item-de-aceite`: a
citação `<ID>.<n>` (ou a faixa `<ID>.<n> a <ID>.<m>`) do item de Aceite que outro documento renumerou segue o item de
texto igual de hoje. Sem item igual, ou com mais de um, a citação fica e sai um aviso. A citação por número de linha
não tem correção.

Sem correção, grava `- <data> migração v<de>→v<para>: nada a corrigir` na seção de aprovações do arquivo de decisões e
imprime `nada a corrigir; migração v<de>→v<para> registrada`; se a última migração registrada já chega a `v<para>`, não
grava de novo e imprime `nada a corrigir; migração até v<para> já registrada`. Com correção, grava os textos e abre o
lote de migração com os documentos corrigidos: `Lote: migração v<de>→v<para> (<N> documentos)`, `Passo: 3` e
`Proximo: lote de migração: passo 4, harness.py checar`. O ciclo segue pela `/ela-harness:refinar-documento`, com o critério forma no
revisor. Nos passos 5 e 7 a tabela de artefatos não muda: os documentos seguem `aprovado`, com a data de antes. O
passo 7 grava a linha `- <data> migração v<de>→v<para>: <N> documentos` no arquivo de decisões, e o commit é
`docs(planejamento): migração v<de>→v<para>, <N> documentos`, com `1 documento` no singular, também na linha.

Saída, com 0: uma linha `<documento>: <k> correções (<nome da correção>)` por documento corrigido, uma por aviso e,
com o lote aberto, as linhas `Lote = ...`, `Documento = ...`, `Passo = 3`, `Rodada = 0` e `Proximo = ...`.

Recusas, com 1 e nada gravado, depois de `recusado: `: `ciclo aberto (<Documento>); feche-o antes de migrar`,
`ciclo aberto (pacote de <N> documentos)`, `ciclo aberto (lote <origem>)`;
`nenhuma migração registrada; passe --de v<versão da última atualização>`;
`--de: esperado v<maior>.<menor>.<correção>, encontrado "<texto>"`;
`--de v<versão> é posterior à versão do plugin, v<versão>`; `<documento> tem mudança fora do commit; faça o commit
antes` (`<a>, <b> têm ...` com mais de um); `git indisponível: <motivo>`; `STATUS.md inválido: <motivo>`,
`backlog ilegível: <motivo>`, e as do `estado` e do `registrar aprovacao`.

## molde

imprime o molde de um documento de planejamento

`harness.py molde <documento>`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<documento>` | sim | caminho do documento, relativo à raiz do projeto |

Imprime o caminho do molde de um documento, relativo à raiz, e sai com 0; o documento não precisa existir.

O molde fica na pasta de moldes (`moldes.pasta`). Vale o primeiro par de `moldes.mapa` cujo padrão casa com o caminho
do documento relativo à pasta do planejamento, com `*`, `?` e `[...]` dentro de um segmento; sem par, o mesmo caminho
relativo dentro da pasta de moldes. Os títulos de nível 1 a 3 do molde são o contrato que o `checar` confere, e os
padrões de `moldes.placeholders` não podem sobrar no documento. Recusas, com 1:
`documento fora de <pasta>/: <documento>`, fora da pasta do planejamento, e `molde não encontrado: <molde>`.

## der

gera e confere o DDL e o diagrama do DER físico

`harness.py der <ação>`

Gera e confere o DDL e o diagrama do DER físico e grava o manifesto dos prints do Workbench.

O documento vem do argumento, relativo à raiz ou absoluto, ou da chave `[der].documento` do perfil. Sai com 1 e
`perfil sem a seção [der]` quando o perfil não a tem; com `documento fora do projeto: <caminho>` quando o argumento
aponta para fora da raiz; com `documento não encontrado: <caminho>` sem o arquivo; com
`<caminho> é uma pasta; passe o arquivo do DER`; e com `documento ilegível: <caminho> (<motivo>)`. As saídas ficam na
mesma posição, em relação ao documento, que as chaves `[der].sql` e `[der].workbench` dão às pastas delas em
relação ao documento de `[der]`; abaixo, `<sql>` e `<workbench>` são essas pastas.

- `gerar [<documento>]`: grava `<sql>/schema.mysql.sql` (MySQL 8.4, o que o Workbench lê), também
  `<sql>/schema.<dialeto>.sql` quando `[der].dialeto` não é `""` nem `mysql`, e o bloco `erDiagram` do documento,
  entre a linha `%% gerado por harness.py der gerar; não edite` e o fim do bloco. Imprime
  `Gravado: <caminho> (<n> linhas)` por SQL e `Gravado: <documento> (bloco erDiagram)`, e sai com 0. Com o formato
  inválido, sai com 1 e um erro por linha, `<documento>:L<n>: <motivo>`, sem gravar nada. O rastreio contra a
  camada 2 não impede a geração: ele sai no `checar` do documento e no gate.
- `conferir [<documento>]`: gera em memória e compara com o disco. Sai com 0 e `OK: DER em dia`, ou com 1 e uma
  linha por diferença: `<sql>/schema.<banco>.sql ausente; rode harness.py der gerar`, o mesmo com `desatualizado`,
  e `erDiagram editado à mão ou desatualizado; rode harness.py der gerar`.
- `workbench`: depois do passo do Workbench, grava `<workbench>/manifesto.txt` e imprime
  `Gravado: <caminho> (<k> arquivos)`. Recusa, com 1 e sem gravar: o DER desatualizado, a pasta sem print em PNG e
  a falta do `workbench.sql` exportado.

O manifesto cita os caminhos a partir da pasta do documento: na primeira linha,
`sha256:<12 hexadecimais> <sql>/schema.mysql.sql`; na segunda, a data `AAAA-MM-DD`; depois, um por linha e em ordem
alfabética, os `.png` e o `workbench.sql` da pasta do Workbench. O `checar` do documento recusa o manifesto ausente,
o hash de outra versão do DDL e o arquivo listado que não existe.

O `\r\n` conta como `\n` no `conferir`, no hash do manifesto e no rastreio, e o `gerar` mantém a quebra de linha
que o documento já tinha.

### der gerar

grava o DDL e o bloco erDiagram a partir das tabelas do DER

`harness.py der gerar [<documento>]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<documento>` | não | caminho do DER, relativo à raiz; sem ele, o documento de [der] do perfil |

### der conferir

diz se o DDL e o bloco erDiagram estão em dia com as tabelas

`harness.py der conferir [<documento>]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<documento>` | não | caminho do DER, relativo à raiz; sem ele, o documento de [der] do perfil |

### der workbench

grava o manifesto dos prints e do SQL exportado do Workbench

`harness.py der workbench`

## versao

marca, confere e limpa a versão enviada para aprovação

`harness.py versao <ação>`

Marca, confere e limpa a versão do documento, ou do pacote, enviada para aprovação, e mostra as versões marcadas.

- `marcar`: o documento é o `Documento` do STATUS.md, que vale sem caminho. Copia o arquivo para a pasta das cópias,
  apaga a `resposta` anterior, grava e imprime `Versao-aprovacao = sha256:<12 hexadecimais>`, o hash da cópia, e põe
  a versão no histórico, se ela não é igual à última de lá. Se o STATUS.md recusar o hash, a cópia sai.
- `conferir`: sai com 0 e `OK: <hash> confere` quando o arquivo é o marcado. Sai com 1 com
  `DIVERGE: arquivo mudou desde a marcação (<atual> != <marcado>)` e o diff da cópia para o arquivo, até 20 linhas, e
  quando o STATUS.md aponta para outro documento, não há versão marcada ou o arquivo sumiu. Sem a cópia e com outro
  hash, procura a versão marcada nos 50 commits mais recentes do arquivo e a restaura, com a linha
  `cópia restaurada do commit <commit>`, ou, sem achá-la, dá a linha
  `versão marcada ausente da cópia e dos últimos 50 commits do arquivo`; com o mesmo hash, ou sem o git, avisa
  `cópia ausente, comparado só o hash`.
- `limpar`: volta o campo para `—` e apaga as cópias, o manifesto, a `resposta` e o histórico; a lista do lote fica.
- `resumo`: o esqueleto das mudanças dos documentos em refino contra o HEAD, por documento e seção (`alterada (+a −r)`,
  `nova`, `removida`) e os IDs que entraram, saíram ou mudaram; o documento fora do HEAD é `novo`. Grava o diff de cada
  camada com mudança em `.claude/harness/dossie/diff-camada-<N>.diff` e cria a pasta `.harness-aprovacao/`, com um
  `.gitignore` de `*`, para o resumo escrito em `.harness-aprovacao/resumo.md`, fora do `.claude/`, onde o Claude Code
  pede permissão a cada escrita. `--desde-marcada` compara com a cópia marcada e,
  sem ela, recusa. Sem mudança: `nenhuma mudança contra o HEAD`, ou `contra a versão marcada`. Com
  `--conferir <arquivo>`, confere as linhas `Onde: <documento> · <seção>` do resumo escrito contra as seções que
  mudaram: `OK: <M> mudanças cobrem as <N> seções alteradas`, ou `FALTA:` e `SOBRA:`, e sai com 1.
- `ver <documento> [n]`: a `n`-ésima seção alterada do documento em refino (padrão 1; `--desde-marcada` como no
  `resumo`), só com as linhas que mudaram, a trocada palavra a palavra (`~~antigo~~ **novo**`), a acrescentada entre `**`
  e a tirada entre `~~`, e a legenda dos IDs na primeira aparição. Uma linha tirada e uma acrescentada só viram uma
  trocada quando mais da metade das palavras confere, como no `difflib.Differ`; senão, saem cada uma na sua linha.
  Seção nova: `Seção nova, <k> linhas.`; removida: `Seção removida.`.
- `historico`: lista as versões marcadas, por padrão as do `Documento`, da segunda em diante com as linhas
  acrescentadas e tiradas contra a anterior; sem nenhuma, `sem versões marcadas para <documento>`.
- `diff`: o diff unificado entre duas versões, com `--- versao <n>` e `+++ versao <m>`: sem número, a penúltima contra
  a última; com um, `<n>` contra a última; com dois, `<n>` contra `<m>`. Corta em 60 linhas sem `--completo`. Recusa:
  `recusado: menos de duas versões marcadas para <documento>` ou `recusado: versão <x> inexistente; há <k>`.

```text
01  <AAAA-MM-DD HH:MM>  sha256:<12 hexadecimais>
02  <AAAA-MM-DD HH:MM>  sha256:<12 hexadecimais>  +4 -1
```

Com `Pacote` ou `Lote` no STATUS.md, o `marcar` não aceita caminho e marca o pacote ou o lote: a cópia de cada
documento e o manifesto, uma linha `<hash> <caminho>` por documento, na ordem do `Pacote` ou da lista do lote; o hash
gravado é o do manifesto. O `conferir` sem caminho dá `OK: pacote <hash> confere (<N> documentos)` ou
`DIVERGE: <k> de <N> documentos mudaram desde a marcação: <lista>`, com uma linha `OK:` ou `DIVERGE:` por documento;
com um caminho do pacote, confere só ele, e o OK é `OK: <documento> confere (pacote <hash>)`. Sem o manifesto,
ignora o caminho e compara só o hash do pacote: o OK ganha a linha `manifesto ausente, comparado só o hash`, e a
divergência é `DIVERGE: pacote mudou desde a marcação (<atual> != <marcado>)`, com a linha
`manifesto ausente: não dá para dizer qual documento mudou`. Sai com 1 também com
`<documento> fora do Pacote do STATUS.md` e, quando é preciso marcar de novo, com
`o manifesto do pacote não é o da marcação <hash>; marque de novo com harness.py passo 6` ou
`o Pacote do STATUS.md mudou depois da marcação; marque de novo com harness.py passo 6`. No lote, a palavra é
`lote` em todas elas, `<documento> fora do lote` e `a lista do lote mudou depois da marcação; marque de novo com
harness.py passo 6`.

Pasta das cópias, `.claude/harness/aprovacao/`, fora do git: a cópia (`<caminho com / trocado por __>`), o manifesto
(`pacote`), o histórico (`historico/<nome da cópia>/NN-<AAAA-MM-DD>T<HHMM>-<12 hexadecimais>.md`) e a `resposta`.
A lista do lote (`lote`) é de outro comando e o `limpar` a deixa. A `resposta` é a linha `<hash marcado> <AAAA-MM-DDTHH:MM:SS> <trecho>`, que a guarda grava a cada mensagem do usuário
com `Passo` 6 e versão marcada, com os 80 primeiros caracteres dela. O `passo 7` recusa sem ela ou com o hash de outra
marcação: ela prova que houve mensagem depois da marcação, não que a mensagem aprova.

Recusas de entrada, com 1: `STATUS.md aponta para <documento>, não para <documento>`, `arquivo não existe: <documento>`
e o caminho passado com pacote ou lote aberto. No `marcar` e no `conferir` sem pacote, o caminho tem de ser o
`Documento` do STATUS.md, gravado antes com `estado set Documento`; com `Documento: nenhum`, com ou sem o caminho, o `marcar` dá
`Documento: nenhum no STATUS.md; abra o documento com harness.py estado set Documento <caminho>` e o `conferir`,
`Documento: nenhum no STATUS.md; não há versão a conferir`. No `historico` e no `diff --documento` sem o caminho, a
recusa é `Documento: nenhum no STATUS.md; passe o caminho do documento`.

### versao marcar

grava o hash da versão em aprovação no STATUS.md e guarda uma cópia

`harness.py versao marcar [<documento>]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<documento>` | não | caminho do documento; sem ele, o Documento do STATUS.md; com Pacote, nenhum |

### versao conferir

diz se o documento ou o pacote mudou depois da marcação

`harness.py versao conferir [<documento>]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<documento>` | não | caminho do documento; sem ele, o Documento do STATUS.md ou o pacote inteiro |

### versao limpar

desfaz a marcação e apaga a cópia e o histórico

`harness.py versao limpar`

### versao resumo

dá o esqueleto das mudanças contra o HEAD e grava o diff de cada camada

`harness.py versao resumo [--desde-marcada] [--conferir <arquivo>]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `--desde-marcada` | não | compara com a cópia marcada, não com o HEAD |
| `--conferir <arquivo>` | não | confere as linhas Onde: do resumo escrito contra as seções que mudaram |

### versao ver

mostra uma seção alterada do documento em refino, palavra a palavra

`harness.py versao ver <documento> [<n>] [--desde-marcada]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<documento>` | sim | nome ou caminho do documento em refino |
| `<n>` | não | número da seção alterada; padrão: 1 |
| `--desde-marcada` | não | compara com a cópia marcada, não com o HEAD |

### versao historico

lista as versões marcadas do documento

`harness.py versao historico [<documento>]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<documento>` | não | caminho do documento; padrão: o Documento do STATUS.md |

### versao diff

diff entre duas versões marcadas

`harness.py versao diff [<n>] [<m>] [--completo] [--documento <documento>]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<n>` | não | versão de partida; padrão: a penúltima |
| `<m>` | não | versão de chegada; padrão: a última |
| `--completo` | não | não corta o diff em 60 linhas |
| `--documento <documento>` | não | caminho do documento; padrão: o Documento do STATUS.md |

## perfil

valida e resume o perfil do projeto (.claude/perfil.toml)

`harness.py perfil [--para <skill>]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `--para <skill>` | não | imprime o bloco "Este projeto" da skill (sempre sai com 0) |

Valida o perfil do projeto, `.claude/perfil.toml`, e imprime um resumo dele, ou o bloco "Este projeto" de uma skill.

Sem opção, imprime quatro linhas: `perfil válido: <nome>`, as fases com os gates, os checklists com os itens por
tipo e os prefixos de ID. Todo comando que lê o perfil o valida inteiro; o primeiro problema sai com 1 e
`perfil inválido: <motivo>`.

Com `--para <skill>` (`refinar-documento`, `gate-fase`, `gerar-modulos` ou `assessor`), imprime o bloco que a skill
injeta ao carregar e sai sempre com 0, porque outro código abortaria a skill; o erro vem na primeira linha,
`ERRO: <motivo>`. O bloco acima do teto da skill, de 3.000 caracteres na `gate-fase`, 1.600 na `refinar-documento` e
1.500 nas outras, sai inteiro, depois de `AVISO: bloco com <N> caracteres, acima de <teto>`. Só os da `gate-fase` e da
`gerar-modulos` leem o STATUS.md, para mostrar a fase atual e o gate dela; com ele inválido, a primeira linha é
`ERRO no STATUS.md: <motivo>`. Na fase cujo gate não tem item `ligados`, a `gerar-modulos` dá
`ERRO: <gate> sem item ligados; a skill não se aplica à fase <fase>`.

Seções e chaves, todas obrigatórias, menos `[gates]` e as opcionais:

- `[projeto]`: `nome`; `harness`, opcional, `planejamento` ou `desenvolvimento`, `planejamento` por padrão; o
  perfil de desenvolvimento não vale nos comandos do planejamento. Chave desconhecida é recusada.
- `[caminhos]`, relativos à raiz: `planejamento` (a pasta das fases), `status`, `backlog`, `decisoes`, `rascunho`,
  `atritos`, `estudos` (pasta), `adrs`, `pesquisas` (pasta), `fontes` (pastas em ordem de precedência, ou `[]`),
  `leitor_frio`, opcional (a pasta dos gabaritos do teste do leitor frio), e `legenda`, opcional (a legenda gerada
  por `harness.py legenda`, fora da pasta do planejamento).
- `[moldes]`: `pasta`; `trocas_de_nome` (nome no molde para nome no documento); `placeholders` (regex que não pode
  sobrar no documento); `partes_variaveis` (regex do título do molde para a do documento; o título fica repetível);
  `mapa`, opcional (pares `[padrão, molde]`, relativos à pasta do planejamento e à pasta de moldes); `liberados`,
  opcional (caminho relativo à pasta de moldes para `sha256:` e 12 hexadecimais; o molde acrescentado ou alterado
  com esse hash passa no `moldes-intocados` do `harness.py invariantes`).
- `[[fases]]`, na ordem: `id` (a pasta da fase), `gate` (vira campo do STATUS.md), `regra` (a restrição de escrita);
  `obrigatorios`, opcional (documentos que o gate exige); `fronteira`, opcional (o corte do escopo na fase).
- `[ids]`: `prefixos`; `padroes` (o ID sem o número, começando por um prefixo); `prefixo_pendencia`;
  `prefixo_relato`, opcional, `REL` sem ele; `com_buracos`, opcional (os prefixos de ID que nunca se reusa, em que
  dividir ou tirar um deixa buraco; neles, o `checar` confere o padrão e a duplicata, sem a sequência); `formas`,
  opcional (a forma de cada ID no texto gerado do harness, uma por prefixo e na ordem dos `prefixos`, cada uma
  começando pelo dela; sem a chave, o texto mostra `<padrão>-NN`).
- `[texto]`: `adjetivos_vagos` (regex), `duvidas_de_escopo`, `sistemas_do_cliente`, `nomes_duplos`, `glossario`.
- `[der]`, opcional, com todas as chaves, os caminhos relativos à pasta do planejamento: `documento` (o `.md` do DER
  físico, numa pasta de fase), `sql` (a pasta do DDL gerado), `workbench` (a pasta dos prints e do SQL exportado
  pelo Workbench), `dialeto` (o banco do ADR: `""` até ele, depois `mysql` ou `postgres`), `conceitual` (o documento
  com o `erDiagram` das entidades), `entidades` (a pasta dos documentos delas), `tecnicas` (colunas em snake_case
  que aceitam a Origem `técnica`) e `rotulo_copia` (o texto que marca a relação de cópia, sem FK).
- `[guarda]`, opcional, com chave desconhecida recusada: `proibidos`, opcional (caminhos relativos à raiz que o
  modelo não grava, com `/**` no fim para uma pasta); `segredos_isentos`, opcional (padrões de caminho com a regra
  do `proibidos`, que a guarda e o `sem-segredos` não leem atrás de segredo); e a `[guarda.segredos]`, opcional,
  de nome (`[a-z0-9]+(-[a-z0-9]+)*`) para expressão regular que não casa com texto vazio, somada aos padrões do
  núcleo: `chave-privada`, `chave-aws`, `token-github` e `jwt`.
- `[[campos]]`, opcional, uma tabela por regra da verificação `campos` do `checar`: `documentos` (padrões relativos
  à pasta do planejamento), `titulo` (o começo do título das seções), `campo` (um rótulo, ou uma lista de rótulos,
  só para presença) e, com um rótulo só, os opcionais `itens` (`[mínimo, máximo]`), `cita` (prefixos de
  `ids.prefixos`, ou o da pendência), `formato` (regex que cada item casa por inteiro) e `proibidos` (trechos que
  nenhum item pode ter).
- `[[colunas]]`, opcional, uma tabela por regra da verificação `colunas` do `checar`: `documentos`, `coluna` (o texto
  exato do cabeçalho) e `formato`, opcional (regex que a célula casa por inteiro).
- `[[pendencia_na_linha]]`, opcional, uma tabela por regra da verificação `pendencia-na-linha` do `checar`:
  `documentos` e `termos`, regex de busca procuradas como palavra inteira e sem distinção de maiúsculas.
- `[leitor_frio]`, opcional: `perguntas`, as perguntas-tipo do teste do leitor frio. Cada uma tem `{ficha}` no lugar
  da ficha escolhida, ou não tem marcador, quando é transversal.
- `[passagem]`, opcional: `manifesto`, o caminho a partir da raiz que o `passagem publicar` commita; `areas`, uma
  tabela com `documento` (relativo à pasta do planejamento), `secao` (o texto do título, sem os `#`), `coluna_area`
  e `coluna_pastas`. Sem a seção, o `passagem exportar` recusa.
- `[ci]`, opcional, com chave desconhecida recusada: `ramo`, o ramo em que o `.github/workflows/harness.yml` gerado
  dispara, no push e no pull request; sem a tabela ou sem a chave, `main`. Com espaço, com `..` ou começando por `-`,
  é recusado.
- `[gates.<gate>]`: `marcador_pendencia` e os `[[gates.<gate>.itens]]`, numerados na ordem do arquivo, com `tipo`
  `script` (e `verificacao`, uma das do `harness.py gate`, com os parâmetros como chaves do item), `revisor`,
  `leitor-frio` ou `humano` (e `criterio`); o `leitor-frio` pede `caminhos.leitor_frio`, `[leitor_frio] perguntas`
  e `[passagem]`, e o item de script `areas-cobertas` pede `[passagem]`.

Regras que pegam quem edita:

- Todo caminho, inclusive de `mapa`, `obrigatorios` e dos parâmetros, é relativo e normalizado: sem `./`, `..`,
  `//`, barra no começo nem no fim. `obrigatorios` fica dentro da pasta da própria fase.
- `fases.id` é nome de pasta sem espaço nem barra; `fases.gate` não repete um campo do núcleo do STATUS.md; fase e
  gate não se repetem. `[gates.<gate>]` só para o gate de uma fase, com ao menos um item.
- Todo parâmetro é obrigatório, menos os opcionais da verificação (`definidos_em` e `quando` no `ids-cobertos`), e
  chave que a verificação não pede é recusada. Tipos: texto não vazio; título (de um a seis `#` e um espaço); caminho
  (um caminho normalizado, relativo à pasta do planejamento); padrões (caminhos com `*` dentro de um segmento);
  prefixos (de `ids.prefixos`); quando (tabela com `campo`, texto, e `formato`, regex); grupos (tabela com
  `secao`, título, e `coluna`, texto).
- `moldes.mapa` não repete padrão; `ids.prefixo_relato` não repete outro prefixo.
- Regex: sem flag global (use `(?i:...)`), sem grupo com nome (use `(?:...)`), sem referência a grupo; as de busca
  não casam com texto vazio.

Depois de editar, rode `harness.py perfil`, `harness.py estado` e `harness.py perfil --para <skill>` para cada skill.
Exemplo: `modelo/planejamento/.claude/perfil.toml`, na raiz do plugin.

## gate

roda os itens de script do checklist de um gate de fase

`harness.py gate <gate> [--verbose]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<gate>` | sim | nome do gate no perfil |
| `--verbose` | não | mostra cada ocorrência abaixo do item |

Roda os itens de script do checklist de um gate, na ordem do perfil, e assina o que o revisor do gate vai ler.

Pré-condições, cada uma com uma linha de recusa e saída 1, sem assinatura: o STATUS.md válido; o gate no perfil
(`gate desconhecido: <gate>; os do perfil: <gates>`), com checklist; a `Fase` atual igual à que o gate fecha
(`<gate> fecha a fase <fase>, e a Fase atual é <fase>`); o gate ainda não aprovado.

Saída: uma linha por item de script ou de leitor frio, `<item> <verificação>: PASS`,
`FAIL: <primeiro problema> (e mais <k>)` ou `INFO: <dado>`, com cada problema abaixo no `--verbose`; depois,
`revisor: itens <itens>; humano: item <item>`, os itens que o script não roda; por último, sempre,
`Assinatura: sha256:<12 hexadecimais>`, o hash dos itens do gate, de cada artefato da fase na ordem da tabela
(caminho e conteúdo, ou `ausente`), do arquivo de decisões, do `CLAUDE.md` da raiz e, com o item de leitor frio, do
gabarito que ele avalia (caminho e conteúdo, ou `sem gabarito`). Sai com 0 só sem FAIL. Abaixo, `<c>` é o caminho de um artefato e `<n>`, uma linha.

- `artefatos-da-fase`: todo `.md` da pasta da fase, fora das subpastas com o nome da pasta de moldes, está na tabela
  de artefatos com status `aprovado` e existe no disco, e todo obrigatório da fase está na tabela. Falha, entre
  outras: `<c> com status <s> (L<n>)`, `<c> fora da tabela de artefatos`, `<c> obrigatório e fora da tabela`.
- `checar-da-fase`: o `checar` passa em todo artefato da fase, e nenhum ID é definido em dois documentos.
- `ids-citados-definidos`: todo ID citado nos artefatos da fase é definido num artefato da fase ou de fase anterior
  (`<c>:<n>: <ID> citado e não definido`).
- `drawio-em-dia`: todo `.drawio` da pasta da fase, fora das subpastas com o nome da pasta de moldes, tem ao lado o
  `.drawio.svg` da mesma versão, como confere a verificação `drawio` do `checar`
  (`<arquivo>.svg de outra versão do <arquivo> (<k> células diferem, primeira <id>); exporte de novo`).
- `pendencias-do-gate`: nenhuma pendência aberta tem o marcador do gate no destino.
- `versao-limpa`: o `Versao-aprovacao` está `—`.
- `a-confirmar`: nunca falha; sai como `INFO`, com a contagem de `[A CONFIRMAR` por artefato.

Do DER físico, com a seção `[der]` do perfil; sem ela, falham com `perfil sem a seção [der]`, e com o documento de
`[der]` ausente ou com o formato inválido, com `<c>: arquivo ausente` ou
`formato do DER inválido (<k> problemas); rode harness.py checar <c>`:

- `der-rastreado`: as colunas, as tabelas e o "Não persistido" cobrem o modelo conceitual e os atributos das
  entidades, pelas regras do `der-rastreio` do `checar`.
- `der-em-dia`: o DDL e o bloco `erDiagram` estão como o `der gerar` os deixaria (`harness.py der conferir`).
- `workbench-em-dia`: o manifesto do Workbench existe, é da versão atual do DDL e lista só arquivos que existem.

Com parâmetros, chaves do próprio item; `documentos` e `por` são padrões relativos à pasta do planejamento, que casam
com os artefatos da fase na tabela:

- `ids-cobertos` (`documentos`, `prefixos` e os opcionais `definidos_em` e `quando`): todo ID dos `prefixos` definido
  em fase anterior é citado, direto ou numa faixa, num artefato que casa com `documentos`
  (`<ID> sem citação em <documentos> (definido em <c>:<n>)`). Com `definidos_em`, padrões como os de `documentos`, os
  IDs vêm dos artefatos da tabela que casam com eles, de qualquer fase e status, e sem nenhum o item falha com
  `nenhum artefato da tabela casa com <padrões>`. Com `quando` (`{ campo = "<rótulo>", formato = "<regex>" }`), só
  conta o ID definido num título cuja seção tem o campo com um item que casa por inteiro com `formato`.
- `secoes-com-id` (`documentos`, `titulo`, `prefixos`): toda seção cujo título começa por `titulo` cita um ID dos
  `prefixos` antes do próximo título de nível igual ou acima (`<c>:<n>: "<título>" sem ID de <prefixos>`).
- `coluna-com-texto` (`documentos`, `secao`, `coluna`, `texto`): a seção `secao` tem uma tabela com a coluna
  `coluna` e ao menos uma linha, e a célula dessa coluna é `texto` em todas.
- `coluna-sem-texto` (`documentos`, `secao`, `coluna`, `texto`): a mesma tabela, e nenhuma célula da coluna contém
  `texto` (`<c>:<n>: "<texto>" na coluna "<coluna>"; troque pelo valor decidido`); seção e tabela ausentes dão as
  recusas da `coluna-com-texto`. Ao contrário dos outros itens, `documentos` vale para os artefatos de todas as
  fases, para o gate de uma fase cobrar documentos de outra.
- `ligados` (`documentos`, `por`): todo artefato que casa com `documentos` é destino de um link, sem a âncora, de um
  que casa com `por`; o link externo ou que sai da raiz não conta (`<c> sem link vindo de <por>`).
- `er-sem-atributos` (`documentos`): o artefato tem um bloco de código que começa por `erDiagram`, sem `{` nem `PK`
  ou `FK` como palavra; os marcadores de cardinalidade não contam.
- `adr-minimos` (`documento`, `secao`): cada item `- [ ] <texto>` da seção `secao` do molde do documento está na
  mesma seção do documento como `- [x] <texto> — <ligação>`, e a ligação é o título de um `### Decisão: <título>`
  do documento ou `não se aplica: <motivo>` (`<c>:<n>: item mínimo "<item>" sem [x]`, `... sem ligação; ...`,
  `... ligado a "<título>", que não é uma decisão do documento`, `<c>: item mínimo "<item>" ausente; ...`).
- `adr-com-requisito` (`documento`): cada `### Decisão:` do documento tem `- **Status:**` (`proposto`, `aceito` ou
  `substituído por <título>` de outra decisão dele), `- **Data:**` em `AAAA-MM-DD` e uma Justificativa (o item
  `- **Justificativa:**` e as linhas que o continuam) que cita um ID definido nas fases até a atual
  (`<c>:<n>: decisão "<título>" sem ...`); sem nenhuma decisão, `<c>: nenhuma decisão ### Decisão:`.
- `dependencias` (`documento`, `titulo`, `campo`, `grupo`, `grupos`): em cada seção cujo título começa por `titulo`
  e cita um ID, as dependências, os IDs e as pendências que os itens do campo `campo` citam, são seções do
  documento ou pendências do backlog, de qualquer status; o grupo, o primeiro item do campo `grupo`, está na coluna
  da tabela de `grupos` (`{ secao = "<título>", coluna = "<coluna>" }`, a primeira tabela da seção com a coluna),
  cuja ordem é a dos grupos; nenhuma seção depende de outra de grupo posterior; e não há ciclo
  (`<c>:<n>: <ID> depende de <ID>, que não é uma seção do documento`,
  `<c>:<n>: <ID> depende de <pendência>, que não está no backlog`, `<c>:<n>: grupo "<valor>" fora da tabela <secao>`,
  `<c>:<n>: <ID> depende de <ID>, do grupo posterior "<grupo>"` e, no fim, `<c>: ciclo: <ID> → ... → <ID>`, um por
  ciclo). Sem a tabela, falha com `<c>: sem a seção "<secao>"` ou
  `<c>:<n>: seção "<secao>" sem tabela com a coluna "<coluna>"`, e as conferências de grupo param.

`documento` é um caminho relativo à pasta do planejamento, e o molde dele é o que o `harness.py molde` resolve.

Da passagem, com a seção `[passagem]` do perfil, que o item pede:

- `areas-cobertas`: todo "Onde vale" das regras de arquitetura (`RA-NN: ... Onde vale: <valor>. Como se confere:`)
  do arquivo de `caminhos.adrs`, fora de bloco de código, casa com os nomes da coluna da área da tabela de
  `[passagem] areas`, do mais longo para o mais curto, separados por `, ` ou ` e `
  (`<adrs>:<n>: área sem linha na tabela das áreas: <resto>`); sem a tabela, falha só com
  `tabela das áreas não achada: <documento> § <seção>`.

Do leitor frio, o item do tipo `leitor-frio` (a verificação `leitor-frio`): o gabarito do gate de data mais recente
em `caminhos.leitor_frio`, de nome `<gate>-<AAAA-MM-DD>.md` com data válida, passa só com a seção `## Resultado` do
`harness.py passagem leitor`, todo item do Gabarito `certa`, o formato da linha `Exportação:` igual ao atual e o
`sha256` dela igual ao da exportação do HEAD, refeita em memória. Falha com a primeira causa, nesta ordem:
`sem gabarito de <gate> em <pasta>`, `<g>: gabarito inválido: <motivo>`, `<g>: sem Resultado`,
`<g>: linha Exportação fora do formato`, `<g>: formato <n>, atual <m>`, `<g>: exportação falhou: <mensagem>`,
`<g>: exportação recusada: <primeira recusa>`, `<g>: exportação desatualizada; rode harness.py passagem leitor <g>`
e `<g>: item <n> não certo` ou `<g>: itens <n> e <m> não certos`, em que `<g>` é o caminho do gabarito. Os avisos
da exportação não contam.

Artefato ilegível vira problema (`<c>: arquivo ausente`, `<c>: não está em UTF-8`). Backlog ilegível faz falhar o
item que o lê, com `backlog ilegível: <motivo>`, menos o `a-confirmar`, que sai como `INFO`.

## legenda

gera a legenda das siglas e dos tipos de ID a partir dos documentos

`harness.py legenda [--check | --ids <texto> | --ids-de <arquivo>]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `--check` | não | só compara com o arquivo e sai com 1 se diferir |
| `--ids <texto>` | não | imprime o título de cada ID e o significado de cada sigla do texto |
| `--ids-de <arquivo>` | não | o mesmo que --ids, com o texto lido do arquivo |

Gera a legenda das siglas e dos tipos de ID no caminho de `caminhos.legenda`, a partir da cópia de trabalho, e
imprime `Gravado: <caminho> (<n> linhas)`. A primeira linha do arquivo é um comentário que diz que ele é gerado; a
guarda nega a edição à mão.

O arquivo tem três partes, cada uma com uma tabela:

- Siglas padrão da engenharia de software: a lista fixa do núcleo, inteira, usada ou não pelo projeto.
- Códigos do projeto: uma linha por título `<marcadores> <nome> (<prefixo>-<CÓDIGO>)` nos artefatos da tabela do
  backlog, de qualquer status, na ordem da tabela e das linhas; o mesmo código num segundo título fica de fora. O
  prefixo é um de `ids.prefixos` com algum padrão `<prefixo>-...` em `ids.padroes`. A linha de um domínio do RF traz
  também o `FN-<CÓDIGO>-NN`, quando o FN está em `ids.prefixos`, e aponta para o título com a âncora do GitHub.
- Siglas e IDs do harness: a lista fixa do núcleo, mais o gate de cada fase, a pendência (`ids.prefixo_pendencia`) e
  o relato (`ids.prefixo_relato`), em ordem de sigla.

Com `--check`, só compara o arquivo, byte a byte, com o que gravaria: `legenda em dia: <caminho>`, com 0, ou
`legenda desatualizada: rode harness.py legenda`, com 1, também para o arquivo ausente.

Com `--ids "<texto>"`, não grava nada e imprime, no lugar da legenda, uma linha `<ID> (<título>)` por ID do texto e
uma `<SIGLA> (<significado>)` por sigla, na ordem da primeira aparição e sem repetir. O título vem da primeira
definição do ID nos artefatos da tabela, ou da célula Pendência do backlog; o ID sem definição sai com `não definido`.
A citação de item de Aceite (`<ID>.<n>`, ou a faixa `<ID>.<n> a <ID>.<m>`) conta como o ID e leva o título depois da
citação inteira. É para pôr ao lado do ID na primeira aparição de um texto. Não combina com `--check` e não pede `caminhos.legenda`.

Com `--ids-de <arquivo>`, o mesmo, com o texto lido do arquivo, sem passar o Markdown pelo shell; o arquivo ilegível
sai com `recusado: <arquivo> ilegível (<motivo>)` e 1.

Os dois saem com 1, sem gravar, com `tipo de ID sem legenda: <tipo>`, uma linha por tipo: primeiro cada prefixo de
`ids.prefixos` sem entrada no núcleo, na ordem do perfil; depois cada `<prefixo>-<CÓDIGO>` citado com número fora de
bloco de código, nos artefatos da tabela, sem título que o nomeie, na ordem da primeira citação. O código de uma FN
vale com o título do RF de mesmo código. Sem `caminhos.legenda` no perfil, sai com 1 e
`erro: perfil sem caminhos.legenda`.

## passagem

exporta, testa pelo leitor frio e publica a passagem do planejamento

`harness.py passagem <ação>`

Exporta a passagem do planejamento ao código: `passagem exportar <pasta> [--ref <commit>]`. Pede `[passagem]` e
`caminhos.legenda` no perfil (`erro: perfil sem [passagem]`, `erro: perfil sem caminhos.legenda`).

Tudo vem do commit (`--ref`, ou o HEAD), lido pelo git como bytes do objeto, nunca do disco, e é calculado em memória
antes de gravar. Entram os artefatos da tabela do backlog do commit com status `aprovado`, ou `em-revisao` com linha nas
aprovações do arquivo de decisões, nas pastas das fases; a legenda; o DDL da pasta `[der] sql`, quando o
`[der] documento` está entre eles; e o fecho por link: cada link relativo de um `.md` copiado, sem a âncora, puxa o
destino, e o `.md` puxado é lido também, até não sobrar nada novo. O link com esquema e o só de âncora ficam de fora; o
caminho entre crases fica como texto.

Recusas, com saída 1 e nada gravado: `erro: <pasta> não está vazia`; `erro: git indisponível: <motivo>`;
`erro: <pasta> fica dentro de uma árvore git: <raiz>`; `erro: ref inválida: <ref>`; e, uma por link,
`<arquivo>:<linha>: link para <destino>: <motivo>`, em que o motivo é `fora do repositório`,
`excluído da passagem (<chave>)` (os caminhos de `[caminhos]` `rascunho`, `status`, `decisoes`, `backlog`, `estudos`,
`atritos` e `leitor_frio`, e a pasta `.claude`, ou o que fica dentro deles), `pasta` ou `ausente em <commit curto>`. O
`<destino>` é o texto do link como está escrito.

Avisos, com saída 0, que o `publicar` recusa: o link para um `.md` das pastas das fases fora da seleção, que não é
copiado (`<arquivo>:<linha>: link para <destino>: <status>`, ou `fora da tabela`); o ID definido duas vezes
(`<ID> definido em <a>:<n> e em <b>:<m>; vale o primeiro`, na ordem da tabela e das linhas); as falhas do
`areas-cobertas` (`areas-cobertas: <falha>`); a legenda ausente, recusada ou diferente da que o commit gera
(`legenda desatualizada em <commit curto>: rode harness.py legenda`); o artefato selecionado que falta no commit
(`<caminho> na tabela de artefatos e ausente em <commit curto>`); e o `em-revisao` sem aprovação, que fica de fora
(`<caminho> em revisão sem aprovação: fica de fora`).

A pasta, relativa ao diretório de onde o comando roda, recebe cada arquivo no mesmo caminho a partir da raiz do
repositório e o `manifesto.json`: o formato, a versão (`null` na exportação), a origem (o repositório do `origin`, o
commit, a data dele e o gatilho), o `sha256` de cada arquivo, o arquivo, as linhas e o `sha256` do trecho de cada ID dos
artefatos selecionados, as áreas do código da tabela de `[passagem] areas` e as pendências abertas citadas fora de bloco
de código. O mesmo commit dá os mesmos bytes. Saída: `exportados <n> arquivos, <m> IDs, <k> pendências em <pasta>`,
seguida dos avisos, cada um como `aviso: <aviso>`.

Testa pelo leitor frio: `passagem leitor <gabarito>`, com o gabarito a partir da raiz, ou absoluto. O gabarito fica
direto em `caminhos.leitor_frio`, com o nome `<gate>-<AAAA-MM-DD>.md` de um gate do perfil, e tem a seção
`## Gabarito` com itens numerados, cada um com os subitens `- Resposta:` e `- Fonte:`. Senão, sai com 1 e
`gabarito inválido: <motivo>`, sem rodar nada, com o primeiro destes motivos: `fora de <pasta>: <caminho>`,
`nome fora do formato <gate>-<AAAA-MM-DD>.md: <nome>`, `gate desconhecido: <gate>`, `arquivo ausente: <caminho>`,
`sem a seção ## Gabarito`, `## Gabarito sem itens numerados`, `item <n> sem - Resposta:` ou
`item <n> sem - Fonte:`.

O comando exporta o HEAD para uma pasta nova do `tempfile`, fora do repositório; a recusa da exportação sai com 1, como
`erro: exportação recusada` e uma recusa por linha, e o aviso só é impresso. Depois roda na pasta, com o ambiente sem
`CLAUDE_PROJECT_DIR` e limite de 900 s, o comando
`claude -p --restricted --safe-mode --tools Read,Grep,Glob --no-session-persistence --output-format json "<prompt>"`.
O prompt é uma frase fixa, que cita a legenda de `caminhos.legenda`, e as perguntas numeradas, cada uma com o texto
do item até o subitem `- Resposta:` ou `- Fonte:`, nunca as respostas nem as fontes. Erros, com saída 1 e o gabarito
sem mudar: `erro: claude indisponível: <motivo>`, `erro: leitor passou de 900 s`,
`erro: saída do leitor ilegível: JSON inválido`, `erro: saída do leitor ilegível: falta o campo <campo>` (o
`is_error` ou o `result`) e `erro: leitor falhou: <motivo>`: com `is_error` verdadeiro, o `result` ou o `subtype`,
ou `sem result`; com o `claude` saindo com código diferente de 0 e sem JSON, a primeira linha não vazia do stderr,
ou `claude -p saiu com <código>`.

As respostas saem do `result`: a linha sem recuo `<n>. ` ou `<n>) `, com o número em negrito ou não, de uma pergunta
ainda sem resposta abre a dela, e as outras seguem na aberta; a pergunta sem resposta fica `sem resposta`. O comando
troca a seção `## Resultado` do gabarito, até o próximo título de nível 1 ou 2, ou a acrescenta no fim. Ela tem a
linha `Exportação: <12 do commit> · formato <n> · sha256:<12 do hash da lista de arquivos>`, a linha `Leitor:` e,
por pergunta, `<n>. a corrigir` com a resposta em linhas `   > `; com alguma pergunta sem resposta, termina com a
linha `Saída inteira do leitor:` e o `result` em linhas `> `. A pasta é apagada também nos erros. Saída: os avisos,
como `aviso: <aviso>`, e a linha
`leitor: <s> s, <entrada> tokens de entrada, <saída> tokens de saída, US$ <custo>, <turnos> turnos, <k> negações`,
com cada negação abaixo, como `  <ferramenta>: <entrada em JSON>`.

Publica: `passagem publicar`, só na máquina, sem rede. Recusas, com saída 1, uma linha por recusa, na ordem, parando
no primeiro grupo que recusa: `publicar só na árvore principal: worktree <branch>`;
`publicar pede a árvore limpa: <k> arquivos alterados`, pelo `git status`; `publicar pede o remoto origin`;
`<documentos> em edição (passo <n>)`, com documento ou pacote no STATUS; `<caminho> com status <s>`, para cada artefato
das pastas das fases que não está `aprovado`; `primeira passagem só depois do <gate> aprovado`, sem tag
`passagem/vN` e com o último gate do perfil não aprovado; `nada a publicar: igual a passagem/v<n>`, com o hash da lista
de arquivos da exportação do HEAD igual ao do manifesto da última tag e nenhuma issue `retorno #<issue>` resolvida
desde ela; e as recusas e os avisos da exportação. O backlog ausente na última tag sai com
`erro: backlog ausente em passagem/v<n>`.

Depois, N é o maior `passagem/vN` mais 1, ou 1, e o gatilho é o último gate do perfil, sem tag, ou `revisão`. Na
revisão, as pendências resolvidas são as resolvidas no backlog do HEAD e não no da última tag, pelo número. O comando
grava o manifesto em `[passagem] manifesto`, com a versão, o commit do HEAD como origem, o gatilho e as pendências
resolvidas, e faz o commit só dele, `docs(passagem): passagem/vN (<gatilho>)`, com
`Pendências resolvidas desde passagem/v<N-1>: <IDs>.` no corpo quando há; o pre-commit roda. Na falha, o manifesto
volta ao do HEAD, e a recusa é `commit falhou: <motivo>`. Depois cria a tag anotada `passagem/vN` no commit novo, com o
gatilho, o commit de origem e as pendências resolvidas na mensagem, um parágrafo cada; na falha, a recusa é
`tag falhou: <motivo>; crie-a com git tag -a passagem/vN -m <...> -m <...> -m <...> <commit>`, o comando que cria a
mesma tag. Saída:
`passagem/vN pronta na máquina: commit <commit>, tag passagem/vN`;
`O envio empurra a tag passagem/vN e comenta e fecha: #<issue> (<pendências>), ...`, com as issues citadas como
`retorno #<issue>` em qualquer célula das pendências resolvidas desde a tag anterior, ou de todas as resolvidas na
primeira, uma vez cada, ou `... e não fecha nenhuma issue`, mais
`; só comenta: #<issue> (<pendências>, segue aberta pela <aberta>), ...` quando uma pendência aberta do backlog da
tag também cita a issue; e `Para enviar: harness.py passagem publicar --enviar vN`.

Envia: `passagem publicar --enviar vN`, só depois da confirmação do usuário. Cada recusa sai com 1, sem nada no
origin e sem mexer em issue: `erro: versão fora do formato vN: <valor>`, `passagem/vN não existe na máquina` e
`passagem/vN não é a última tag: passagem/v<m>`; depois, um `git ls-remote` traz as tags do `origin`, e cada tag da
máquina até a vN que está lá com outro sha que o da máquina (`git rev-parse refs/tags/passagem/vK`) dá
`a tag passagem/vK do origin é outra (<12 do origin>; na máquina, <12 da máquina>); confira antes de enviar`; a
falha do `ls-remote` dá `origin não consultado: <motivo>`.

Então, nesta ordem, com cada push por `git push origin refs/tags/passagem/vK`, com 60 s, e só a tag:
- cada vK que falta no origin, com K menor que N, em ordem crescente: primeiro as issues dela, com a tag anterior
  da máquina como base, e depois o push, com `tag passagem/vK enviada ao origin`. Qualquer falha numa vK, de issue
  ou do push, para o comando antes da tag seguinte, e a vK continua faltando no origin;
- a vN: o push, com `tag passagem/vN enviada ao origin`, ou `tag passagem/vN já estava no origin`; a falha é
  `push falhou: <motivo>` e para antes das issues; depois, as issues dela.

As issues de uma tag: uma vez por issue `retorno #N` das pendências resolvidas desde a tag anterior, calculadas
pelos backlogs das duas tags, ou de todas as resolvidas na primeira, cada `gh` na raiz com 30 s:
`gh issue view N --json state,comments`; aberta e sem pendência aberta da tag que a cite,
`gh issue close N --comment "Resolvida na passagem/vN pela <pendência>: <como>"`; aberta e citada por uma pendência
aberta, só `gh issue comment N --body "<corpo>"`, com o corpo `<pendência> resolvida na passagem/vN: <como>.` e
`A issue segue aberta pela <aberta>.`, sem ponto repetido. Com mais de uma pendência, as listas levam `e` antes da
última e o plural (`pelas`, `resolvidas`), e o `<como>` de cada resolvida vai numa linha `<pendência>: <como>`,
depois da frase. A issue fechada dá `#N já estava fechada (<pendências>)`, sem outro `gh`. A que já tem um
comentário igual ao corpo, sem os espaços das pontas e com o `\r\n` contado como `\n`, não ganha outro: a que
fecha passa pelo `gh issue close N`, sem comentário, e dá `#N fechada (<pendências>); já comentada`; a outra dá
`#N já comentada (<pendências>); segue aberta pela <aberta>`, sem outro `gh`. As outras linhas:
`#N comentada e fechada (<pendências>)` e
`#N comentada; segue aberta pela <aberta> (<pendência> resolvida na passagem/vN)`, com as listas separadas por
vírgula; a falha, `#N: gh issue <view | close | comment> falhou: <motivo>`, segue para a próxima issue da tag. Com
alguma falha, sai com 1. Rodar de novo é seguro: a issue fechada e o comentário igual não se repetem, e a vK que
parou no meio volta a ser processada.

### passagem exportar

copia de um commit os aprovados, o que eles citam por link e a legenda, com o manifesto

`harness.py passagem exportar <pasta> [--ref <commit>]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<pasta>` | sim | pasta nova ou vazia, fora de uma árvore git |
| `--ref <commit>` | não | o commit lido; sem ela, o HEAD |

### passagem leitor

exporta o HEAD, roda o leitor frio sobre ela e grava as respostas no gabarito

`harness.py passagem leitor <gabarito>`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<gabarito>` | sim | o gabarito, a partir da raiz, em caminhos.leitor_frio |

### passagem publicar

commita o manifesto e cria a tag passagem/vN, só na máquina

`harness.py passagem publicar [--enviar <vN>]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `--enviar <vN>` | não | empurra as tags passagem/vN que faltam no origin e fecha ou comenta as issues retorno resolvidas; só depois da confirmação do usuário |

## estudos

lista os estudos do assessor e a situação da decisão de cada um

`harness.py estudos [--pendentes]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `--pendentes` | não | só os estudos com decisão por registrar e os ilegíveis |

Lista os estudos do assessor, na pasta `caminhos.estudos`, e a situação da decisão de cada um.

Uma linha por estudo `.md`, em ordem de nome, e a contagem da pasta toda no fim. Com `--pendentes`, só os com decisão
por registrar e os ilegíveis, porque um ilegível pode esconder uma decisão fora da forma. Sai sempre com 0, mesmo com
a pasta ilegível (`pasta de estudos ilegível: <pasta> (<motivo>)`); sem estudo, `nenhum estudo (<pasta>)`.

```text
<arquivo>: <tema> — decisão pendente
<arquivo>: <tema> — decidida em <AAAA-MM-DD>, registro pendente
<arquivo>: <tema> — registrada em <onde>
<arquivo>: ilegível (<motivo>)
<N> estudos, <n> com decisão por registrar, <k> ilegíveis      (sempre; o ", <k> ilegíveis" só com algum ilegível)
```

Formato: o script lê só o cabeçalho, até a primeira linha em branco, e dele só as linhas `Tema:` e `Decisão:`; o
resto do estudo é da skill `assessor`. `Decisão:` aceita `pendente`, `<opção> em <AAAA-MM-DD>, registro pendente` ou
`<opção> em <AAAA-MM-DD>, registrada em <arquivo>`. Outra forma, data inválida, `Tema:` vazio ou linha ausente
deixam o estudo ilegível.

## invariantes

confere pelo git as invariantes da trilha do perfil, com os segredos

`harness.py invariantes (--arvore | --indice | --base <ref>) [--verbose]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `--arvore` | um do grupo | o disco contra o HEAD (Stop) |
| `--indice` | um do grupo | o índice contra o HEAD (pre-commit) |
| `--base <ref>` | um do grupo | o HEAD contra a merge-base da ref com ele (CI) |
| `--verbose` | não | mostra os arquivos ou as linhas de cada falha |

Confere pelo git os moldes intocados, as decisões só com acréscimos, o STATUS.md, o `checar` dos aprovados e os
segredos. Na trilha de desenvolvimento, as conferências do planejamento não rodam: rodam o `arquivos-do-harness` no
`--arvore`, o `passagem-em-dia` e o `gerados-em-dia` no `--indice` e no `--base`, e o `sem-segredos`. No planejamento,
o `gerados-em-dia` também roda no `--indice` e no `--base`, só com a linha do gerado no `CLAUDE.md`.

Um modo, e só um, é obrigatório: `--arvore`, o disco contra o HEAD, com os arquivos novos, que o hook de fim de turno
usa; `--indice`, o índice contra o HEAD, que o pre-commit usa; `--base <ref>`, o HEAD contra a merge-base da ref com
ele, que a CI usa. Os alterados vêm do git, com 10 s de limite por chamada; o renomeado conta pelos dois nomes.

- `moldes-intocados`: falha se um arquivo da pasta de moldes foi acrescentado, alterado, apagado ou renomeado. Sem
  nenhum arquivo da pasta na base, o `HEAD` ou a merge-base, a pasta nasce na mudança, e o acrescentado passa, com a
  linha `moldes-intocados: OK`. A outra exceção é o acrescentado ou alterado que o `moldes.liberados` do perfil libera
  com o hash do conteúdo novo, com `\r\n` contado como `\n`; com algum liberado e nenhuma falha, a linha é
  `moldes-intocados: OK (<n> liberados pelo perfil)`. O liberado com outro hash falha, e o `--verbose` diz
  `<arquivo>: hash <do conteúdo>, o perfil libera <do perfil>`.
- `so-acrescimos`: falha se uma linha do arquivo de decisões sumiu ou mudou, inclusive por texto acrescentado dentro
  dela, ou se o arquivo foi apagado; o acréscimo no meio passa, e a troca da quebra de linha do Windows não conta.
- `status-valido`: falha se o STATUS.md da versão nova falta ou não passa na validação do `estado`.
- `status-pelo-harness`, só com `--indice`, logo depois do `status-valido`: compara o STATUS.md do índice com o hash
  que o harness grava a cada mudança dele, no arquivo `harness-status` do diretório do git desta cópia. Nunca falha:
  `status-pelo-harness: OK`, com o STATUS fora dos alterados, acrescentado ou igual ao gravado; senão,
  `status-pelo-harness: AVISO: <status> do commit não é o que o harness gravou por último nesta cópia; confira com
  harness.py proximo`.
- `checar-aprovados`, só com `--indice` e `--base`: falha se um `.md` alterado da pasta do planejamento, `aprovado`
  no backlog da versão nova, falha no `checar`, com o texto e o molde da versão nova. A verificação do `DESDE` do
  `checar` que só avisa no aprovado anterior à migração dela não conta, com as decisões da versão nova.
- `legenda-em-dia`, só com `--indice` e `--base` e só com `caminhos.legenda` no perfil: gera a legenda com os
  arquivos da versão nova, sempre, sem olhar o que mudou, e a compara com a legenda da versão nova. Saídas:
  `legenda-em-dia: OK`; `legenda-em-dia: FALHA: rode harness.py legenda`, com a legenda ausente ou diferente; e
  `legenda-em-dia: FALHA: tipo de ID sem legenda: <tipo>`, quando a geração recusa, com todos os tipos no `--verbose`.
- `passagem-em-dia`, só na trilha de desenvolvimento, com `--indice` e `--base`, quando o que mudou toca a cópia da
  passagem (`caminhos.passagem`): falha se a cópia da versão nova não confere com o manifesto dela, que deve ser
  legível e de um formato que o harness lê, com cada arquivo no `sha256` do manifesto e nenhum a mais nem a menos, e
  com cada `ids[]` no arquivo dele e com o trecho refeito da primeira linha igual ao do manifesto, nas linhas e no
  `sha256`; o `ids[]` de um arquivo que falta ou difere não é conferido, e as `pendencias` ficam de fora. Sem arquivo
  da cópia na versão nova, passa. O resumo traz a primeira falha, na ordem do manifesto, com os `ids` depois dos
  arquivos e os arquivos a mais por último, e o `--verbose` lista todas:
  `<passagem>/<arquivo> difere do manifesto; a cópia muda só por harness.py importar`;
  `<passagem>/<arquivo> sobra na cópia`; `falta <passagem>/<arquivo>`;
  `ids.<ID>: <passagem>/<arquivo> não está em arquivos; a cópia muda só por harness.py importar`;
  `ids.<ID>: o trecho <passagem>/<arquivo>:<primeira>-<última> difere do manifesto; a cópia muda só por harness.py importar`;
  `manifesto ilegível: <motivo>`; e `formato <f>; este harness lê o formato <lista>`.
- `gerados-em-dia`, com `--indice` e `--base`: gera os arquivos como o
  `harness.py gerar` e os compara com os da versão nova, byte a byte, com o perfil (`.claude/perfil.toml`), a cópia da
  passagem e os arquivos das duas pastas do gerador da versão nova, lidos do índice ou do commit, nunca do disco. Falha
  se um arquivo gerado falta (`ausente`), difere (`desatualizado`) ou sobra nas pastas do gerador (`órfão`). Sem o
  perfil, passa calada: não há o que gerar. Sem o manifesto da cópia que ele aponta na versão nova, só o
  `.github/workflows/harness.yml` se confere. Esse arquivo vem do `.claude/settings.json` da versão nova, nas duas
  trilhas, e sem o settings fica de fora; o settings que não fixa a versão do plugin, ou a fixa diferente da do núcleo
  carregado, dá a recusa dele. O resumo traz o
  primeiro problema, na ordem do `gerar`, com `; <n> no total` quando há mais, e termina com `; rode harness.py gerar`:
  `gerados-em-dia: FALHA: desatualizado: <caminho>; rode harness.py gerar`. A recusa do `gerar` vira a falha, sem o
  comando, que ele também recusaria: `gerados-em-dia: FALHA: <recusa>`, com o total. O perfil da versão nova que não
  vale dá `gerados-em-dia: FALHA: .claude/perfil.toml: <motivo>`. O `--verbose` lista cada problema ou cada recusa.
  No planejamento, a conferência entra depois da `legenda-em-dia`: o `harness.yml` sempre se confere, e o
  `.claude/harness/gerado/planejamento.md`, com o perfil do planejamento e a única pasta dele,
  `.claude/harness/gerado/`, só quando o `CLAUDE.md` da versão nova tem uma linha igual a
  `@.claude/harness/gerado/planejamento.md`; as linhas de saída são as mesmas. Sem a linha e sem o settings, a saída é
  a de um repositório sem o gerado.
- `arquivos-do-harness`, só na trilha de desenvolvimento e só com `--arvore`: falha se um arquivo da cópia da
  passagem (`caminhos.passagem`), um `<blocos>/*/estado.md`, um `<blocos>/*/aceitacao.md` ou um
  `<blocos>/*/revisao.md` tem mudança sem commit: os comandos do harness fazem commit na hora, e a mudança sem commit
  veio de fora. O `<blocos>/*/gabarito.md` fica de fora: o `revisao preparar` o grava sem commit. O arquivo
  rastreado, o novo no índice inclusive, dá
  `<caminho> mudou fora de um comando do harness; desfaça com git restore --staged --worktree <caminho>`, e o não
  rastreado, `<caminho> não veio de um comando do harness; peça ao usuário que o apague`. O resumo traz o primeiro
  caminho, em ordem alfabética, com `; <n> no total` quando há mais; o `--verbose` lista todos. Sem HEAD, como na
  montagem, passa.
- `sem-segredos`, nos três modos e nas duas trilhas, por último: falha se uma linha acrescentada contra a base, ou
  contra a árvore vazia sem HEAD, casa um padrão de segredo do núcleo ou de `[guarda.segredos]`; o arquivo renomeado
  ou copiado compara com a origem dele, e uma origem de `segredos_isentos` conta como vazia; no `--arvore`, os
  não rastreados entram inteiros. Ficam de fora os arquivos de `segredos_isentos` e os binários, com um NUL nos
  primeiros 8.000 bytes. O resumo é `sem-segredos: FALHA: <arquivo>:<linha>: segredo (<nome do padrão>)`, o
  primeiro achado, com `; <n> no total` quando há mais; o `--verbose` lista cada um, e o texto nunca aparece.

Saída: uma linha por conferência, `<nome>: OK`, `<nome>: FALHA: <resumo>` ou, no `status-pelo-harness`,
`<nome>: AVISO: <resumo>`, que não muda o código de saída, como
`so-acrescimos: FALHA: linha <n> de <arquivo> tirada ou alterada`. Com `--verbose`, abaixo de cada falha: os arquivos
dos moldes, os erros do STATUS.md ou `<documento>: <verificações que falharam>`. Sem nenhum commit, as conferências
que comparam com a base passam. Sai com 1 se alguma falha, e também com `erro: fora de um repositório git`,
`erro: ref inválida ou sem ancestral comum: <ref>` ou `erro: git indisponível: <motivo>`.

## proximo

diz o próximo passo pelo estado e pela tabela de artefatos

`harness.py proximo [--verbose]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `--verbose` | não | mostra a fila inteira e as revisões por documento |

Diz o próximo passo do planejamento, pelo STATUS.md, pela tabela de artefatos, pelas pendências e pelos links.

Só lê; a rede só para o retorno, e o hook nunca consulta. A ação recomendada é a primeira que existir, nesta ordem:

1. consertar: no passo 7 com a versão marcada já no HEAD, `harness.py fechar`; nos passos 6 e 7 com o documento
   mudado desde a marcação, `harness.py versao conferir`; o documento em refino ausente do disco; o documento ou o
   pacote ou o lote do STATUS, nos passos 0 a 6, todo `aprovado` na tabela e sem pendência aberta que o cite:
   `perguntar ao usuário se o STATUS está velho`, com a volta no motivo; o lote de migração, que mantém os documentos
   `aprovado`, não entra nesse caso. Com o `Lote` no STATUS e a lista dele ausente, ilegível ou fora da conta,
   `a lista do lote falta ou não confere`, com a mensagem do `estado` e o jeito de refazer no motivo, que, com a
   versão marcada, começa por `com a autorização do usuário, harness.py versao limpar`. Num worktree, a ação ganha
   `(na árvore principal)`.
2. o documento, o pacote ou o lote em andamento: `/ela-harness:refinar-documento <documento>`, que retoma do passo
   atual, ou, no passo 7, o commit e o `harness.py fechar`; com "quando o usuário liberar" no `Proximo`, perguntar se o
   usuário libera o commit.
3. a fila da fase, sem nada aberto: `/ela-harness:gerar-modulos`, quando o gate da fase tem item `ligados`, nenhum
   documento da fase, no disco ou em refino, casa o `por` dele e todo obrigatório da fase existe e está aprovado, com
   o motivo `nenhum <padrões do por, juntados por " ou "> na fase`; os módulos em rascunho (os documentos que casam com o `por` de um item `ligados`
   do gate); os módulos aprovados com documentos linkados em rascunho; os outros rascunhos; os obrigatórios ausentes
   ou em rascunho; os documentos novos que as pendências abertas com o marcador do gate pedem; os aprovados citados
   por pendência aberta com o marcador do gate; as pendências com o marcador que nenhum item da fila resolve; por
   último, `/ela-harness:gate-fase <gate>`.
   O documento novo sai do destino da pendência, sem os trechos `antes do`: o caminho com pasta (a partir da raiz, ou
   da pasta do planejamento quando começa pelo id de uma fase) dentro da pasta de uma fase e sem arquivo no disco; o
   nome sem pasta de nenhum `.md` do planejamento, de nenhum arquivo da raiz e de nenhum caminho de estado do perfil,
   na pasta dos `.md` de mesmo prefixo (o nome até o primeiro `-`), ou `<pasta>/<nome>`, com o `<pasta>` literal, sem
   prefixo ou com eles em mais de uma pasta; a pasta dentro da pasta de uma fase, `<pasta citada>/<documento>.md`,
   com o `<documento>` literal. A ação é `/ela-harness:refinar-documento <caminho>`, com o motivo
   `documento novo: <IDs> (<marcador>)`, mais `; a pasta, com o usuário` no `<pasta>` e `; o nome sai da pendência` no
   `<documento>`; o mesmo caminho em duas pendências dá um item só. A pendência com o marcador que nenhum item da fila
   resolve, nem pelos IDs nem pelo nome, no destino, de um documento da fila, de um derivado em rascunho de um
   módulo da fila ou do documento em refino, vira `resolver <ID> com o usuário`, com o motivo
   `nenhum documento da fila a resolve: <destino>`.
   A revisão de um aprovado citado por pendência com `antes do <arquivo>.md` entra logo antes do item desse arquivo,
   se ele está na fila como módulo, rascunho, obrigatório ou documento novo; com mais de um arquivo
   (`antes do a.md e do b.md`), antes do primeiro deles na fila; senão, vai junto das revisões do marcador. Nenhum
   arquivo depois de um `antes do` conta como citado. A pendência cujo destino cita dois ou mais aprovados (fora os
   em refino) vira um item `lote` só, no lugar das revisões desses documentos e na posição da primeira delas, com a
   ação do refino do primeiro documento, na ordem do lote, e o motivo `lote <ID>: <N> documentos, camadas <a> a <b>`
   (`camada <a>` com uma só); o mesmo vale para as revisões sem o marcador. Com o gate aprovado,
   `harness.py estado set Fase <fase seguinte>`, e as pendências com `antes do` aparecem nas revisões sem o marcador;
   com o da última fase, `planejamento concluído: todos os gates aprovados`.

Pré-checagem, só no comando e com o gate recomendado: os itens de script do gate, os do `harness.py gate`, sem o
leitor frio, que a `gate-fase` roda à parte; só lê. Logo abaixo do motivo, `Pré-checagem do <gate>: <n> FAIL`,
`Pré-checagem do <gate>: sem FAIL` ou `Pré-checagem do <gate>: não rodou: <motivo>`, este com a pré-condição que
recusa ou `<Tipo>: <primeira linha da mensagem>` de outro erro; o gate segue recomendado. Abaixo, até 3 linhas FAIL
`  <item> <verificação>: FAIL: <resumo>` e `  +<k> FAIL: harness.py gate <gate> --verbose` quando há mais; com
`--verbose`, todas, sem o `+<k>`. O INFO não aparece. O hook e o `fechar` não a rodam.

A saída segue o molde "Próximo" do `nucleo/comum/saida.md`; a linha `Atenção` traz o backlog ilegível, os estudos
com decisão por registrar, os relatos não incorporados, os avisos do ambiente, o retorno e, por último, a passagem.
Com `--verbose`, a fila inteira, as revisões por documento, também as sem o marcador (o lote, pelo motivo dele), e
`Retornos com pendência (<n>):`, com uma linha `  #N <título>: <pendências>` por issue, cada pendência resolvida com
` (resolvida)`. STATUS.md inválido sai com 1 e `STATUS.md inválido: <motivo>`.

Com `[passagem]` no perfil:

- Passagem por publicar, sem rede, também no hook, só com o último gate aprovado:
  `passagem: <gate> aprovado e nada publicado; harness.py passagem publicar`, sem tag `passagem/vN`; ou
  `passagem: revisão aprovada depois de passagem/vN; harness.py passagem publicar`, quando o `git diff` da última tag
  ao HEAD toca um artefato aprovado das fases, a legenda ou a pasta `[der] sql`. Num worktree, a ação ganha
  `(na árvore principal)`; a falha do git dá `passagem não conferida: <motivo>`.
- Retorno, só no comando: `gh issue list --label retorno --state open --limit 1000 --json number,title`, na raiz,
  com 10 s. A issue sem pendência, aberta ou resolvida, que cite `retorno #N` em qualquer célula vira
  `retorno sem pendência: #N <título>; registre por harness.py registrar pendencia --causa codigo citando retorno #N`; a com
  pendência sai só no `--verbose`. A falha dá `retorno não consultado: <motivo>`: `gh indisponível: <motivo>`,
  `gh passou de 10 s`, a primeira linha do erro do `gh` ou `saída do gh ilegível`.

## fechar

fecha o ciclo depois do commit, conferindo a versão no HEAD, e leva o STATUS.md ao commit

`harness.py fechar [--proximo <proximo>]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `--proximo <proximo>` | não | o texto do Proximo; sem ele, o próximo passo calculado |

Fecha o ciclo do documento, do pacote ou do lote no passo 7, depois do commit, conferindo a versão marcada no HEAD.

Confere que cada documento em refino está no HEAD igual ao disco, pelo `git show` e pelo `git cat-file --filters`,
que aplica o `core.autocrlf`, e que o hash dele, ou o do manifesto refeito no pacote ou no lote, é o
`Versao-aprovacao`; vale noutra máquina, sem as cópias. Então grava numa escrita só `Versao-aprovacao: —`,
`Documento: nenhum`, sem `Pacote` e sem `Lote`, `Passo: 0`, `Rodada: 0` e o `Proximo` (o `--proximo`, ou a ação do
`harness.py proximo`), apaga as cópias da aprovação, a lista do lote e a saída gravada do `afetados` e imprime
`Fechado: <documento> (<hash> no HEAD <commit>)` e `Proximo = <texto>`, com 0. Num pacote, o documento vira
`pacote de <N> documentos`; num lote, `lote <origem> de <N> documentos`. Não pede autorização: com a versão no HEAD,
nada se perde.

Depois, faz o `git add` do `STATUS.md` e o commit dele. Quando o HEAD mudou um documento do ciclo e nenhuma outra
branch, local ou remota (pela referência do último fetch), contém o HEAD, sai o `git commit --amend --no-edit`; nos
outros casos, como o HEAD de outro trabalho, o merge ou o commit já no remoto, sai um commit
`chore: fecha o STATUS.md (<documento>)`. A terceira linha é `STATUS.md no commit <commit> (amend)` ou `(chore)`, com
0. Se o commit falha, o `STATUS.md` fica gravado e no índice, e a terceira linha é
`STATUS.md gravado; o commit falhou: <motivo>; faça o commit à mão`, com 1. O motivo é a primeira linha da saída do
git com `FALHA`, ou, sem ela, a primeira linha não vazia.

Recusas, com 1 e nada gravado, depois de `recusado: `: `Passo <n>; fechar só no passo 7`, `nenhuma versão marcada`,
`a raiz não é um repositório git`, `git indisponível: <motivo>`, `STATUS.md inválido: <motivo>`,
`<documento> tem mudança fora do commit; faça o commit antes`,
`a versão no HEAD não é a marcada (<head> != <marcado>); confira com harness.py versao conferir` e
`índice com arquivos além do STATUS.md; faça o commit deles antes`.

## ambiente

diz o que falta nesta máquina: Python e TOML, pre-commit e árvore

`harness.py ambiente`

Diz o que falta nesta máquina para o harness rodar: o Python com leitor de TOML, o pre-commit ativo e a árvore.

Uma linha por item, que começa por `OK:`, `AVISO:` ou `FALHA:` e traz o comando que conserta. Não lê o perfil, e por
isso funciona quando ele não carrega. Sai com 1 só com algum `FALHA`.

1. Python e TOML: o Python 3.9 ou mais novo, com `tomllib` ou `tomli`; sem leitor, `pip3 install --user tomli`.
2. Pre-commit: o `core.hooksPath` igual a `.githooks`; sem ele, `git config core.hooksPath .githooks`, que vale para o
   clone e os worktrees dele.
3. Árvore: `OK: árvore principal`, ou `AVISO` num worktree, onde o planejamento é a cópia da branch dele e o refino
   vai na árvore principal.

Sem `.git` na raiz, os itens 2 e 3 dão `OK`; o erro do git dá `AVISO`.

## guarda

hooks PreToolUse, UserPromptSubmit e Stop (payload no stdin)

`harness.py guarda {pre-tool,prompt,stop}`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `{pre-tool,prompt,stop}` | sim | o hook que chamou |

Decide, pelos hooks do Claude Code, o que o modelo não pode gravar: lê o payload JSON do stdin e sai sempre com 0.

Os hooks do `.claude/settings.json` chamam `guarda pre-tool` (PreToolUse, em Edit, Write, NotebookEdit e Bash),
`guarda prompt` (UserPromptSubmit) e `guarda stop` (Stop), com 30 s de limite no PreToolUse e no UserPromptSubmit e
900 s no Stop, que no repositório de código roda as verificações do perfil. No planejamento, o UserPromptSubmit vai
pela via curta do `gancho`, que grava a resposta sem carregar o `harness.py`, com a mesma saída.
A guarda recusa (`deny`), pede a confirmação do usuário (`ask`) ou não diz nada; nunca libera o que o `settings.json`
bloqueia. A raiz da sessão é a `CLAUDE_PROJECT_DIR`, ou a pasta com `CLAUDE.md` acima do harness; o prompt usa a raiz.
Árvore é a pasta mais próxima com `.git`, comparada pelo dispositivo e pelo inode. A árvore da sessão, que o PreToolUse
e o Stop usam, é a do `cwd` do payload quando ela é a raiz da sessão ou um worktree do mesmo repositório, pelo diretório
comum do git lido dos arquivos `.git` e `commondir`; senão, a raiz. Documento em aprovação é o `Documento`, ou cada um
do `Pacote`, com `Passo` 6 ou 7.

O perfil sai da árvore da sessão, em duas camadas: a parte comum (`[projeto]` e `[guarda]`), cujo erro vira o aviso
de erro, e o perfil da trilha. Com o da trilha inválido, valem só as regras comuns, de 1 a 6; quando nenhuma decide,
sai o aviso `guarda do harness: perfil inválido: <motivo>; só as regras comuns valem`. As regras 7 e 8 de baixo e os
alvos protegidos do Bash, menos o arquivo de ambiente, os `proibidos` e os do desenvolvimento, são do perfil de
planejamento; o `LANES.md` e os gerados do `gerar` da regra 7, a regra 9, os alvos dela no Bash, a restauração ampla
e o `git push --no-verify`, só do perfil de desenvolvimento.

PreToolUse em Edit, Write e NotebookEdit; vence a primeira regra que casa, nesta ordem:

1. alvo ausente: nada;
2. alvo fora de toda árvore git: nada;
3. alvo noutra árvore git que não a da sessão: recusa, com
   `<alvo> está na árvore <raiz do alvo>, e esta sessão trabalha na <árvore da sessão>` e o pedido de entrar nela
   pelo `EnterWorktree` ou abrir uma sessão lá;
4. segredo no conteúdo: recusa, com `segredo no conteúdo (<nome do padrão>); guarde-o fora do repositório`, sem o
   valor. A guarda procura no `content` do Write, no `new_string` do Edit e no de cada item de `edits`, e no
   `new_source` do NotebookEdit, os padrões do núcleo (`chave-privada`, `chave-aws`, `token-github` e `jwt`) e os de
   `[guarda.segredos]`. O alvo que casa um `segredos_isentos` do perfil fica de fora;
5. arquivo de ambiente, de nome `.env` ou que começa por `.env.` e não termina em `.example`, em qualquer pasta:
   recusa, com `recusado: <relativo> é arquivo de ambiente; no repositório vai só o .env.example`;
6. alvo casa com um dos `proibidos` do perfil (`[guarda]`; `pasta/**` casa com a pasta e com tudo dentro): recusa;
7. alvo é um arquivo gerado, a legenda (`caminhos.legenda`) ou o manifesto da passagem (`passagem.manifesto`):
   recusa, com `arquivo gerado: rode harness.py legenda` ou `arquivo gerado: rode harness.py passagem publicar`; no
   desenvolvimento, o `LANES.md` da raiz de qualquer árvore, sem distinguir maiúsculas: recusa, com
   `arquivo gerado: rode harness.py lanes`; e, também sem distinguir maiúsculas, o `AGENTS.md` da raiz, a legenda
   (`caminhos.legenda`), o `.github/workflows/harness.yml` e qualquer arquivo de `.claude/rules/harness/` e de
   `.claude/harness/gerado/`, que o `harness.py gerar` grava: recusa, com `arquivo gerado: rode harness.py gerar`; no planejamento, vale só a
   pasta `.claude/harness/gerado/`, onde o `gerar` grava o `planejamento.md`, e o `.github/workflows/harness.yml`: o
   alvo igual a eles ou dentro da pasta, sem distinguir maiúsculas, é recusado com a mesma mensagem;
8. alvo é um documento em aprovação: recusa; alvo é o arquivo de decisões (`caminhos.decisoes`), e a edição tira
   ou altera uma linha: recusa; sessão no checkout principal e alvo dentro de `.claude/`: pede confirmação;
9. no perfil de desenvolvimento, sem distinguir maiúsculas, porque o disco do Mac não as distingue: alvo dentro da
   cópia da passagem (`caminhos.passagem`), em qualquer árvore, a principal ou a de uma lane: recusa, com
   `a cópia da passagem muda só por harness.py importar`; alvo `<blocos>/*/aceitacao.md` (`caminhos.blocos`):
   recusa, com `a aceitação muda só por harness.py aceitacao conferir ou anotar`; alvo `<blocos>/*/estado.md`:
   recusa, com `o estado do bloco muda só por harness.py bloco <verbo>`; alvo `<blocos>/*/revisao.md`: recusa, com
   `a revisão muda só por harness.py revisao registrar e revisao dispensar`; alvo `<blocos>/*/gabarito.md`: recusa,
   com `o gabarito muda só por harness.py revisao preparar`; alvo `<blocos>/<pasta>/spec.md` cujo `estado.md`, na
   árvore da sessão, se lê com o estado efetivo (o `estado_anterior` em `blocked`) fora de `planning`: recusa, com
   `a spec aprovada muda só depois de harness.py bloco replanejar`; sem esse `estado.md`, ou com ele ilegível, a spec
   passa. Fora de lane, o alvo que não casa nenhum padrão de `desenvolvimento.fora_da_lane` é recusado com
   `fora de lane, só se grava em <padrões>; abra uma lane com harness.py lane abrir <ficha>`. Lane é a worktree
   dentro de `lane.pasta` com o bloco da branch dela, reconhecida pelos arquivos; a de `estado.md` inválido também
   conta, e o Stop acusa o arquivo.

PreToolUse em Bash: lê os alvos de escrita do comando (redirecionamentos, `tee`, `sed -i`, `rm`, `mv`, `mkdir`, o
destino de `cp`, os subcomandos de git que escrevem e outros), com o `cd`, o `git -C` e o código de `sh -c`, até dois
níveis. Confere, nesta ordem, a outra árvore de cada alvo e de cada diretório de git, o segredo no texto inteiro do
comando, as outras regras de cada alvo, o código de `-c` e as perguntas; a primeira recusa vence:

- recusa: alvo, ou diretório de um git que escreve (`add` e `commit` incluídos), noutra árvore; segredo no texto do
  comando, com o corpo dos heredocs, sem a isenção de `segredos_isentos` (o segredo falso num caminho isento vai pelo
  Write); alvo de arquivo de ambiente; alvo que casa com um dos `proibidos` do perfil, mas não a pasta que só o
  contém; alvo igual a um arquivo gerado (o `git restore` dele conta; o `git add` e o `git commit` passam); alvo que
  sobrepõe a pasta de moldes, o STATUS.md ou um documento em aprovação, também pela pasta que os contém; no perfil de
  desenvolvimento, o `LANES.md`, com a mensagem da regra 7, o alvo que sobrepõe a cópia da passagem, um
  `<blocos>/*/aceitacao.md`, um `<blocos>/*/estado.md`, um `<blocos>/*/revisao.md`, um `<blocos>/*/gabarito.md`, o
  `AGENTS.md` da raiz, o `.github/workflows/harness.yml`, a legenda ou uma das duas pastas do `gerar`
  (`.claude/rules/harness` e
  `.claude/harness/gerado`), também pela pasta que os contém quando ela é a raiz (`.`) ou existe, pelo primeiro nessa
  ordem: o próprio alvo, com a mensagem da regra 9 (a dos gerados é a da regra 7); a pasta que contém a cópia ou um
  arquivo de bloco, com
  `<alvo> contém <primeiro protegido>, que muda só por comando do harness; grave num caminho fora dela`, o protegido
  escrito como nesta lista (a pasta da cópia ou o padrão `<blocos>/*/<arquivo>`); a que contém um gerado, com
  `<alvo> contém arquivos gerados (<primeiro gerado>) e do harness; a pasta não se apaga nem se sobrescreve inteira`.
  Também a spec aprovada, com a mensagem da regra 9, e, fora de lane, o
  alvo fora do `fora_da_lane`; código de `python -c`, `node -e`, `ruby -e` ou `perl -e` que cita um desses, um
  arquivo gerado ou um proibido sem o `/**` do fim;
- passa pela regra 9: a restauração, que volta o arquivo ao índice ou ao HEAD, como o `arquivos-do-harness` pede: o
  `git restore` sem `-s` nem `--source`, em qualquer forma, e o `git checkout` com `--` e só opções antes dele. A de
  dentro da cópia, de um `estado.md`, de um `aceitacao.md`, de um `revisao.md`, de um `gabarito.md`, da spec
  aprovada ou de um gerado do `gerar` passa também fora de lane; as outras passam antes pelo `fora_da_lane`. As
  outras regras valem para ela, menos no `LANES.md`, que segue recusado, e o caminho que o mesmo comando também grava
  de outro jeito não conta como restauração;
- pede confirmação: sessão no checkout principal e alvo em `.claude/`; `git commit --no-verify` ou `-n`; no perfil
  de desenvolvimento, `git push --no-verify`, ou um começo dele, e a restauração ampla, que volta o disco (o
  `git restore` sem `--staged` ou com `--worktree`, e o `git checkout --`) e tem por alvo a raiz ou uma pasta que
  contém a cópia, um `estado.md`, um `aceitacao.md`, um `revisao.md`, um `gabarito.md` ou um gerado do `gerar`, com
  `a restauração de <alvo> apaga as mudanças sem commit de toda a pasta, não só as dos arquivos do harness`; o
  `git restore --staged .` e o de uma pasta sem arquivo da regra 9 passam calados; git que apaga trabalho ou
  reescreve o remoto:
  `git reset --hard`; `git clean` com `-f` ou `--force`, também em grupo, menos com `-n` ou `--dry-run`; `git stash`
  sem caminho (sozinho, com opções, `push` sem caminho ou `save`), `git stash drop` e `git stash clear`; `git push`
  com `--force`, `-f`, também em grupo, `--force-with-lease` ou uma refspec que começa por `+`. Cada um com a
  mensagem dele, terminada em `; confirme só se o usuário pediu`. Depois deles, o `--enviar` do `passagem publicar`
  depois de uma palavra que termina em `harness.py`, em qualquer forma (com `$CLAUDE_PROJECT_DIR`, com
  `--enviar=<v>` ou dentro de `sh -c`), com `confirme: o --enviar empurra a tag passagem/vN e fecha issues no origin`;
  o `importar` depois dessa palavra, também como argumento de outro comando, com
  `confirme: o importar abre branch e PR no origin, fora da montagem`; e o `aceitacao anotar`, com
  `confirme: o aceitacao anotar grava o resultado de um item manual, que só o usuário confere`; o `bloco finalizar`,
  com `confirme: o bloco finalizar empurra a branch e abre o PR`; o `bloco desbloquear`, com
  `confirme: o bloco desbloquear destrava o bloco pela causa do bloqueio, que só o usuário decide`; o
  `bloco planejado`, com `confirme: o bloco planejado registra a aprovação da spec pelo dono`; o `bloco replanejar`,
  com `confirme: o bloco replanejar descarta a aprovação da spec, que o dono dá de novo`; o `revisao dispensar`, com
  `confirme: o revisao dispensar tira o achado do ## Em aberto pela palavra do dono`; o `retorno abrir`, com
  `confirme: o retorno abrir cria uma issue no repositório de planejamento`; e o `lane fechar` com `--manual` ou
  `--abandonar`, com
  `confirme: o lane fechar --manual grava o resultado de itens manuais, que só o usuário confere` e
  `confirme: o lane fechar --abandonar apaga a worktree e a branch da lane sem PR mesclado`. A palavra que começa
  por `--` conta pelo que vem antes do `=`. Com mais de um pedido no comando, as mensagens saem juntas, separadas por
  `; `, com o `; confirme só se o usuário pediu` uma vez só, no fim;
- nada: leitura, o `harness.py`, menos os comandos que pedem confirmação, e o arquivo de decisões, porque `cat >>` é
  acréscimo e o Stop pega a linha tirada.

UserPromptSubmit: com `Passo` 6 e versão marcada, cada mensagem do usuário grava a `resposta` que o `passo 7` exige
(veja `harness.py versao`); a notificação de tarefa e o retorno de subagente não contam.

Stop: roda `invariantes --arvore` na árvore da sessão, com as conferências da trilha do perfil, no fim do turno. Com
falha, segura o turno uma vez e pede que o modelo desfaça com `git restore <arquivo>` ou explique; a falha em molde ou
no STATUS.md, ele pede ao usuário. Na segunda parada do turno (`stop_hook_active`), só avisa. Sem `.git` na árvore,
não decide.

Na trilha de desenvolvimento, o Stop roda as invariantes do `--arvore` e, numa lane reconhecida pelos arquivos, compara
a marca da árvore com a da última verificação aprovada: igual, nada roda; diferente, roda as verificações de `stop`
(veja `harness.py verificar`), que somam até 840 s. A falha de invariante ou de verificação segura o turno uma vez,
com `Corrija e pare de novo.` e, depois de uma quebra, as linhas das verificações que falharam; com `stop_hook_active`,
só avisa. Sem falha, as puladas e as sem tempo vão num aviso, sem segurar o turno. Fora de lane, nenhuma verificação
roda. Na lane, as verificações também não rodam em dois casos, e as invariantes seguem: com o bloco em `planning`, ou
em `blocked` vindo dele, e em `reviewing` com a marca da revisão em andamento de menos de 4 horas (veja
`harness.py revisao preparar`). Nos dois, o Stop não diz nada pelas verificações e não grava a marca da verificação.

```text
pre-tool: {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
           "permissionDecisionReason": "guarda do harness: <motivo>"}}       (ou "ask"; sem decisão, nada)
stop:     {"decision": "block", "reason": "guarda do harness: <falhas>. Desfaça com git restore <arquivo> ..."}
          {"systemMessage": "guarda do harness: <falhas>; o pre-commit vai recusar o commit"}
          {"decision": "block", "reason": "guarda do harness: <falhas>. Corrija e pare de novo.\n<linhas>"}
          {"systemMessage": "guarda do harness: <falhas>; corrija antes de seguir"}   (as duas, no desenvolvimento)
erro:     {"systemMessage": "guarda do harness com erro, sem decisão: <tipo>: <motivo>"}
          {"systemMessage": "guarda do harness com erro ao anotar a resposta: <tipo>: <motivo>"}   (no prompt)
```

O `settings.json` nega às ferramentas Edit e Write do modelo os moldes (`moldes.pasta`), o STATUS.md
(`caminhos.status`) e os `proibidos` do perfil, repetidos à mão no `deny`, e pede confirmação no rascunho
(`caminhos.rascunho`) e no perfil. Numa recusa, a mensagem diz o caminho certo quando há um, como `harness.py passo 3`
antes de editar o documento em aprovação; a mudança que o usuário quer de propósito ele faz com `!` no prompt, porque
a guarda só olha o modelo.

Limites: a guarda não lê o script executado por arquivo, `eval`, `xargs`, `find -exec`, a substituição de comando nem
o corpo de um heredoc, nos alvos (a regra do segredo lê o texto inteiro do comando, com o corpo), e o Stop cobre o
que passar. Ela falha aberta: um erro vira o aviso de erro, e a ferramenta
segue a permissão normal. Sem `python3`, os hooks somem sem aviso.

## iniciar

inicia um projeto de planejamento ou de desenvolvimento pelo modelo do plugin

`harness.py iniciar [<trilha>] [<pasta>] [--nome <nome>] [--conferir]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<trilha>` | não | planejamento ou desenvolvimento |
| `<pasta>` | não | a raiz do repositório git que recebe o harness; sem ela, a atual |
| `--nome <nome>` | não | o nome do projeto, no lugar do {{PROJETO}}; sem ele, o nome da pasta |
| `--conferir` | não | diz o que falta no repositório de código para o primeiro bloco |

Inicia um projeto pelo plugin, nas duas trilhas (spec do porte 1, §7.5), ou confere o repositório de código (spec
6d-repositorio, §7.4).

- `harness.py iniciar <trilha> [<pasta>] [--nome <nome>]`: a `<trilha>` é `planejamento` ou `desenvolvimento`, e a
  `<pasta>`, a raiz de um repositório git sem o harness; sem ela, a pasta atual. Copia, sem sobrescrever nada, o modelo
  da trilha (`modelo/<trilha>/` do plugin) e o lançador, `.claude/harness/harness.py`, executável. Em todo arquivo de
  texto copiado, troca `{{PROJETO}}` pelo `--nome` ou, sem ele, pelo nome da pasta, e `{{DATA}}` pela data
  de hoje. O que já existe fica como está, com uma linha `mantido: <caminho>`; a do `CLAUDE.md` mantido diz as linhas
  `@` do modelo que faltam nele. O `.gitignore` da equipe recebe só as linhas do modelo que faltam. O
  `.claude/settings.json` que a pasta já tem, como o que a instalação do plugin grava, recebe do modelo o que falta: em cada lista do `permissions`, as regras que faltam, no fim e na ordem
  do modelo; as outras chaves, como o `extraKnownMarketplaces.<nome>` e o `enabledPlugins.<id>`, só se faltarem, e a
  `ref` instalada fica. Com algo acrescentado, a linha é `mesclado: .claude/settings.json`; sem nada, `mantido:`. Liga o
  `core.hooksPath` aos githooks e instala os plugins da trilha pelo `claude plugin`, com o `--scope project`: o
  `ela-harness` e, no desenvolvimento, o `ela-harness-papeis`. O `.github/workflows/harness.yml` não vem do modelo:
  o `iniciar` o escreve, nas duas trilhas, igual ao do `gerar`, com o ramo do perfil (no planejamento, o `[ci] ramo`,
  `main` sem ele), lido sem validar o perfil, e a `ref` do settings já mesclado. O arquivo que já existe fica, com `mantido:`. A `ref`
  que não é a tag da versão do plugin carregado, ou o settings sem `ref`, dá a linha da recusa e nenhum arquivo, sem recusar o `iniciar`. O
  núcleo, as skills, os agentes e o workflow vêm do plugin e não são copiados.
- Com o `git config` falhando, sem o `claude` ou com ele falhando, a cópia fica, a linha do `core.hooksPath` ou a dos
  `plugins` diz o que falta e o código de saída é 0. O arquivo que não se grava ou não se lê, e o fora do UTF-8, saem
  com 1 e a linha `erro: <motivo>`.
- Recusa, antes de gravar qualquer coisa: sem o modelo ou o lançador no plugin, a `<pasta>` que não é a raiz de um
  repositório git, a `<pasta>` que já tem o lançador e o `.claude/settings.json` existente que não é um objeto JSON:
  `.claude/settings.json: JSON malformado na linha <n>; corrija o arquivo e rode o iniciar de novo` ou
  `.claude/settings.json: não é um objeto JSON; corrija o arquivo e rode o iniciar de novo`.
- `harness.py iniciar --conferir`: roda dentro do repositório de código e diz o que ainda falta para o primeiro
  bloco, um item por linha, na ordem: `perfil`, `plugin`, `githooks`, `.gitignore`, `ci`, `passagem`, `invariantes`,
  `instalado` e, só com a `[desenvolvimento.linear]` no perfil válido, `linear` (o item 9). No repositório de
  planejamento, com o `.claude/perfil.toml` legível e o `[projeto] harness` diferente de `desenvolvimento`, recusa antes
  de conferir, com `iniciar --conferir: é do repositório de código; no planejamento, rode harness.py gerar --check`, e
  sai com 1. O item `plugin` confere, no
  `.claude/settings.json`, o `extraKnownMarketplaces.ela-harness` do GitHub `Ela-Decora/ela-harness`, com `ref`, e os
  dois plugins no `enabledPlugins`, e depois o lançador. O item `instalado` confere os dois plugins habilitados para a
  pasta ou para o usuário, pelo `claude plugin list --json`, com o tempo limite de 30 s: a instalação vale por pasta,
  e cada clone novo roda os comandos uma vez. O item `.gitignore` confere as linhas fixas e, com o perfil válido, os
  arquivos da lane que o `lane abrir` confere (o `.env` do `env_modelo` e os `env_copiados`), pelo `git check-ignore`.
  O item `ci` compara o `.github/workflows/harness.yml` com o gerado, pelo ramo do perfil, lido sem validá-lo, e pela
  `ref` do settings; ausente ou diferente, ou com a recusa de versão ou a do settings, diz `ci: falta`.
  O item `linear` confere a chave `LINEAR_API_KEY` do ambiente e lê do Linear o time, o projeto e os rótulos do perfil,
  numa chamada só, de no máximo 10 s: diz `linear: ok` ou o que falta, e nunca mostra a chave. Cada linha é
  `<item>: ok` ou `<item>: falta: <o quê>; <comando>`, e um item que falha não impede os seguintes. Sai com 1 se
  alguma linha tem `falta`.
- O ramo principal e a pasta do backlog vêm do `.claude/perfil.toml` que a `<pasta>` já tiver; sem ele, `main` e
  `docs/backlog`.

## gerar

gera os arquivos do harness a partir do perfil e, no código, da passagem

`harness.py gerar [--check]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `--check` | não | só confere, sem gravar, e sai com 1 se algum difere |

Gera os arquivos do repositório de código a partir da cópia da passagem (`caminhos.passagem`) e do perfil. São oito
tipos, nesta ordem, a lista do gerador:

- as regras por área, `.claude/rules/harness/area-<slug>.md`, uma por área da tabela das áreas do manifesto com pelo
  menos uma regra de arquitetura, na ordem da tabela, com os `paths` das pastas da área e cada regra com a fonte;
- o `AGENTS.md`, na raiz, o ponteiro para os agentes que não leem o `CLAUDE.md` nem as regras do Claude Code;
- o Registry, `.claude/harness/gerado/registry.json`, com as áreas e as regras, cada uma com o `severity`: o trecho
  ` Severidade: critical|major|minor.` da regra de arquitetura ou, sem ele, o
  `desenvolvimento.registro.severidade_padrao` do perfil, `major` por padrão;
- o `.claude/harness/gerado/produto.md`, com a versão e a origem da passagem;
- o `.claude/harness/gerado/verificacoes.md`, com as verificações do perfil;
- o `.claude/harness/gerado/papeis.md`, com o modelo e o esforço de cada agente do ciclo do bloco, o do frontmatter do
  agente ou o do `[desenvolvimento.modelos]` do perfil;
- o `.claude/harness/gerado/ciclo.md`, com as instruções do ciclo do bloco: as skills, quem decide, as dispensas das
  skills de terceiros, o idioma entre agentes, as versões de terceiros e a retomada, com o nome do dono do perfil e a
  pasta dos blocos;
- a legenda do código, em `caminhos.legenda`, com a parte do projeto da legenda da passagem (`passagem.legenda`) e o
  prefixo das fichas do código.

As pastas do gerador, `.claude/rules/harness/` e `.claude/harness/gerado/`, só têm arquivos dele: o arquivo nelas que o
gerador não escreveria agora é órfão, como a regra de uma área que saiu da tabela. Os arquivos delas são os que o git
lista, rastreados ou não; o que o git ignora, como o `.DS_Store`, não conta. Também é órfão o arquivo rastreado fora
delas cuja primeira linha é o aviso de gerado, como a legenda do caminho antigo depois que o perfil muda o
`caminhos.legenda`; o que só cita o aviso, em outra linha, ou não é UTF-8, não conta. O `AGENTS.md` e a legenda têm caminho
fixo, fora delas.

O comando grava só o arquivo ausente ou diferente, byte a byte, e apaga cada órfão. Imprime `gravado: <caminho>` por
arquivo gravado, na ordem da lista, `removido: <caminho>` por órfão, em ordem alfabética, apagando também cada pasta que ele deixou vazia, da dele para
cima, sem passar da pasta do gerador que o contém nem da raiz, e a linha final
`<n> arquivos gerados, <m> mudaram, <k> removidos`. Não faz commit.

Com `--check`, não grava nada. Em dia, imprime `gerados em dia: <n> arquivos` e sai com 0; senão, uma linha por
problema, na ordem da lista e depois os órfãos, `ausente: <caminho>`, `desatualizado: <caminho>` ou
`órfão: <caminho>`, e `rode harness.py gerar`, com 1.

Recusa com 1, sem gravar, e o `--check` recusa igual, com uma linha por falha, na ordem em que aparecem:

- `desenvolvimento.caminhos.legenda: <caminho> é um arquivo do gerador`, a legenda do código no `AGENTS.md` ou numa
  pasta do gerador, sem distinguir maiúsculas; essa falha sai sozinha;
- `sem passagem: <passagem>/manifesto.json não existe; rode harness.py importar`, ou o manifesto ilegível, de outro
  formato ou sem versão publicada, com as mensagens do `importar`; essa falha sai sozinha;
- `<passagem>/<arquivo>:<linha>: <ID> fora do formato da regra de arquitetura`, a regra em mais de uma linha, a área
  sem linha na tabela das áreas, `<ID>: severidade <valor> fora da escala critical, major e minor` e
  `falta <passagem>/<arquivo>`;
- `a área <a> não dá nome de arquivo`, quando o nome não tem letra nem algarismo que o slug guarde,
  `as áreas <a> e <b> dão o mesmo arquivo area-<slug>.md`, na ordem da tabela, e
  `a área <a> tem regras e nenhuma pasta na tabela das áreas`;
- `<passagem>/<caminho>: legenda da passagem não achada`, sem o texto ou sem o título da parte do projeto, e
  `legenda da passagem sem a tabela: <passagem>/<caminho>`, com o título e sem a tabela nem a linha de vazio;
- `fora de um repositório git` e `git grep falhou: <motivo do git>`;
- a do agente do ciclo que falta, não se lê ou não tem o `model` ou o `effort` no frontmatter, com a recusa do
  `papel`, como `papel: falta o agente <nome> em <pasta>`; essa falha sai sozinha.

Nas duas trilhas, o comando escreve também o `.github/workflows/harness.yml`, o CI do projeto, com o ramo do perfil (o
`ramo_principal` no desenvolvimento e o `[ci] ramo` no planejamento, `main` sem ele) e a versão que o
`.claude/settings.json` fixa em `extraKnownMarketplaces.ela-harness.source.ref`; o `--check` o confere byte a byte,
com os mesmos `ausente` e `desatualizado`. Ele não entra nas pastas do gerador nem nos órfãos. Sem o settings, o
arquivo fica de fora. Duas recusas, com 1, que não impedem a gravação dos outros arquivos:

- `harness.yml: o plugin carregado é v<versão> e o .claude/settings.json fixa <ref>; reinstale o plugin e depois apague
  o link .claude/harness/nucleo ou abra uma sessão nova`, quando a `ref` não é `v<versão do plugin carregado>`;
- `harness.yml: o .claude/settings.json não fixa a versão do plugin (<motivo>); rode harness.py iniciar --conferir`,
  quando o settings não é um JSON legível com a `ref`.

A guarda nega a edição à mão dos arquivos gerados, com `arquivo gerado: rode harness.py gerar`.

Na trilha de planejamento, o comando gera um arquivo só, `.claude/harness/gerado/planejamento.md`, com as partes do
`CLAUDE.md` que são do harness: o mapa, o ciclo, os IDs e os marcadores, o que não fazer e os gatilhos, com os valores
do perfil. Nada depende da passagem, que o planejamento não tem. A única pasta do gerador é
`.claude/harness/gerado/`: o arquivo nela que o gerador não escreveria é órfão, e as regras do projeto em
`.claude/rules/harness/` ficam como estão. A saída, o `--check`, as linhas de problema e a guarda são os da trilha de
código. O `CLAUDE.md` do projeto puxa o arquivo pela linha `@.claude/harness/gerado/planejamento.md`; sem essa
linha, o `invariantes` não confere o arquivo.

## referencia

gera a referência dos comandos, das skills e agentes e do núcleo

`harness.py referencia [--gravar]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `--gravar` | não | grava em docs/referencia.md, na raiz do plugin, em vez de imprimir |

Gera a referência do harness em Markdown e a imprime: os comandos, as skills e os agentes e o mapa do núcleo.

De onde vem cada parte:

- o uso, os argumentos e as opções de cada comando e de cada ação: do parser montado no `harness.py`;
- o texto de cada comando: da constante `AJUDA` do módulo dele, a mesma que o `--help` do comando mostra;
- as skills e os agentes: do frontmatter de `skills/*/SKILL.md` e de `agents/*.md`, na raiz do plugin;
- o mapa do núcleo: da primeira frase da docstring de cada módulo das três pastas de `nucleo/`.

A referência tem as duas trilhas: os comandos do planejamento, com os comuns às duas, e, em
`## Comandos do desenvolvimento`, os que só a trilha de desenvolvimento tem.

Não lê o perfil nem o STATUS.md. A saída não depende da largura do terminal nem da versão do Python.

Com `--gravar`, grava o mesmo texto em `docs/referencia.md`, na raiz do plugin, em UTF-8 e de forma atômica, e
imprime `Gravado: docs/referencia.md (<N> linhas)`. Um teste da suíte compara esse arquivo com a saída do gerador
e, quando não batem, falha com "rode python3 nucleo/comum/harness.py referencia --gravar".

Para um comando novo:

1. escreva a `AJUDA` no módulo do comando;
2. passe a `AJUDA` como `description=` do subparser, no `harness.py`;
3. dê ao subparser um `help=` de uma linha, que é o texto do comando na tabela de comandos;
4. dê um `help=` a cada argumento e a cada opção;
5. acrescente o comando e a `AJUDA` dele à lista de ajudas do teste da referência, na ordem do parser, ou à
   lista da trilha de desenvolvimento, quando o comando é só dela; sem isso, um teste da suíte falha;
6. rode `harness.py referencia --gravar` e ponha o arquivo gerado no mesmo commit.

Sai com 0 ao imprimir ou ao gravar. Fora de um projeto, sai com 1 e `erro: raiz do projeto não encontrada: ...`;
sem conseguir ler ou gravar um arquivo, sai com 1 e `erro de arquivo: ...`.

## Comandos do desenvolvimento

Com `harness = "desenvolvimento"` no `[projeto]` do perfil. Valem os comandos comuns às duas trilhas, [`invariantes`](#invariantes), [`guarda`](#guarda), [`iniciar`](#iniciar) e [`gerar`](#gerar), e os desta tabela.

| Comando | O que faz |
|---|---|
| [`importar`](#importar) | copia a passagem do repositório de planejamento, conferida, e abre o PR dela |
| [`fichas`](#fichas) | lista as fichas da passagem e do backlog do código, com o estado de cada uma |
| [`contexto`](#contexto) | grava o Context Packet do bloco da lane, ou o imprime para uma ficha |
| [`verificar`](#verificar) | roda as verificações do perfil para o momento, na árvore atual |
| [`ci`](#ci) | comandos do CI do projeto, que só rodam no GitHub Actions |
| [`aceitacao`](#aceitacao) | confere e anota a aceitação do bloco da lane |
| [`prepush`](#prepush) | recusa o push direto no ramo principal; chamado pelo hook pre-push do git |
| [`bloco`](#bloco) | muda o estado do bloco da lane, um passo por vez |
| [`lane`](#lane) | abre, confere e fecha as lanes dos blocos |
| [`retorno`](#retorno) | abre a issue de retorno no repositório de planejamento |
| [`lanes`](#lanes) | imprime o quadro das lanes e regrava o LANES.md |
| [`papel`](#papel) | diz o modelo e o esforço de cada agente do ciclo do bloco |
| [`revisao`](#revisao) | prepara e registra a revisão do bloco da lane |
| [`linear`](#linear) | espelha as fichas, só de ida, no projeto do Linear |

## importar

copia a passagem do repositório de planejamento, conferida, e abre o PR dela

`harness.py importar [<vN>]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<vN>` | não | a versão da tag passagem/vN; sem ela, a maior do repositório de planejamento |

Copia a passagem do repositório de planejamento para o repositório de código, conferida, e abre o PR dela; no
repositório sem commit, grava a cópia direto na árvore e faz o primeiro commit.

- Versão: `vN` escolhe a tag `passagem/vN`; sem ela, vale a maior do repositório de planejamento, pelo
  `git ls-remote --tags`. O `passagem.repositorio` do perfil em `org/nome` vira o endereço do GitHub no protocolo do
  `origin`: SSH com o `origin` em SSH, HTTPS nos outros casos, sem a credencial do `origin`; URL e caminho ficam como
  estão. A tag vem por um clone raso numa pasta temporária, que sai no fim.
- Conferência, toda antes de gravar: o manifesto no caminho `passagem.manifesto` da tag, legível; o formato entre os
  que este harness lê; a versão igual a N; cada arquivo do manifesto na tag, com o `sha256` dele; cada `ids[].arquivo`
  em `arquivos`; nenhum ID com o prefixo das fichas do código; e o `gerar` sobre a cópia da tag, que dá os textos dos
  arquivos gerados. Cada problema é uma recusa, com saída 1 e nada gravado, como as de versão:
  `nenhuma passagem/vN em <repositorio>`, `passagem/vN não existe em <repositorio>`,
  `passagem/vN já está no <ramo_principal>` e `passagem/vN é mais velha que a v<m> do <ramo_principal>`. A recusa do
  `gerar` dá uma linha `importar: gerar recusou: <motivo>` por motivo, e a passagem não chega ao ramo principal.
- Montagem, no repositório sem commit: a cópia vai para `caminhos.passagem` na árvore, e a cópia de uma montagem
  anterior sai sem ser lida; os gerados vão com ela, conferidos contra a árvore: o diferente é gravado e o órfão das
  pastas do gerador, apagado do disco e também do índice, pelo `git rm --cached`. Depois vem o primeiro commit,
  `chore(harness): instala o harness e importa a passagem/vN`, pelo pre-commit, com `git add --` explícito: o que o
  `iniciar` deixou (o lançador, o workflow, o `settings.json`, o perfil, os githooks, a CI, o `.gitignore`, o
  `CLAUDE.md` e o `README.md` do backlog), a pasta da cópia e cada gerado, só dos que existem. Antes do add, o
  `git ls-files --others --ignored` sobre esses caminhos: com algum arquivo que o git ignora, o comando para, com saída
  1 e sem commit, na linha
  `o git ignora <k> arquivos (1 arquivo, no singular) que o importar põe no commit, como <primeiro>; ajuste o .gitignore e rode harness.py importar v<N> de novo`,
  com o `<primeiro>` em ordem alfabética; só o link do núcleo, `.claude/harness/nucleo`, que o hook refaz e o
  `.gitignore` ignora de propósito, não conta. O commit recusado dá
  `git commit falhou: <motivo>; rode harness.py importar vN de novo`, com saída 1; a cópia e os gerados ficam na
  árvore, e rodar de novo refaz a montagem.
- Nos outros, o PR próprio: o `git fetch origin +refs/heads/<ramo_principal>:refs/remotes/origin/<ramo_principal>`,
  com o refspec explícito, que não depende do `remote.origin.fetch`; um worktree temporário, fora do repositório, sem
  branch local, a partir do `origin/<ramo_principal>`; a cópia e os gerados, conferidos contra o
  `origin/<ramo_principal>`, com o diferente gravado e o órfão apagado; a mesma parada dos ignorados, com a mesma
  linha, no worktree e antes do add, sem push e sem PR; o commit `docs(passagem): importa passagem/vN`, com os dois e
  o relatório no corpo, que passa pelo pre-commit; o `git push origin HEAD:refs/heads/docs/passagem-vN`; e o
  `gh pr create`, com o relatório no corpo e o `dono.github` como responsável. O worktree temporário sai no fim,
  também na falha; o de uma rodada interrompida por sinal não prende a seguinte, e a árvore em que o comando roda,
  com as branches locais dela, não muda.
- Retomada: o passo que falha dá `<passo> falhou: <motivo>; rode harness.py importar vN de novo`, com saída 1. Rodar
  de novo retoma: com a branch no origin, só abre o PR. Com um PR aberto da branch, a saída é
  `PR #<n> já aberto: <url>`, com 0. Com o PR aberto da `docs/passagem-v<m>`, de outra versão, o comando recusa antes
  do clone, com saída 1 e nada gravado, e com o de menor número quando há mais de um:
  `PR #<n> da passagem/v<m> ainda aberto: <url>; mescle-o ou feche-o antes de importar a v<N>`.
- A saída tem cinco linhas: a conferência (`passagem/vN conferida: formato <f>, <n> arquivos, <k> IDs`); as fichas
  novas, as que saíram e as que mudaram, contra a cópia do `origin/<ramo_principal>`, ou `fichas: nenhuma mudança`;
  os blocos vivos afetados, como `<ID>, na v<N> (<partes>)`, ou `nenhum bloco vivo afetado`; os gerados,
  `gerados: <m> mudaram (<caminhos>), <k> removidos (<caminhos>)`, na ordem da lista do gerador e depois os órfãos,
  sem parênteses no grupo vazio; e `PR #<n> aberto: <url>`. Uma ficha mudou quando o `sha256` do trecho dela no
  manifesto novo difere do antigo. O corpo do commit e o do PR trazem as quatro primeiras, também na retomada.
- Bloco afetado: o `passagem` do `estado.md` é a versão com que o bloco está em dia, o `<N>` da linha; o bloco nela,
  ou numa mais nova que a importada, não é afetado. Nos outros, ele é afetado quando a ficha dele, ou um ID que ela
  cita, mudou ou saiu entre o manifesto dessa versão e o novo. O manifesto da versão é o da cópia da lane, quando ela
  está nessa versão; senão, o do histórico do `<passagem>/manifesto.json` no `origin/<ramo_principal>`; sem nenhum,
  recusa com `lane <ID>: sem o manifesto da passagem/v<N>, nem na cópia da lane nem no origin/<ramo_principal>`. A
  lane sem cópia fica de fora, e a cópia ilegível de uma lane recusa com `lane <ID>: <motivo>`.
- Na montagem, as fichas saem todas como novas, e a linha dos blocos afetados e a do PR viram uma, a última:
  `primeiro commit <sha7>: harness e passagem/vN; rode harness.py iniciar --conferir e faça o push do <ramo_principal>`.
- Com a `[desenvolvimento.linear]` no perfil, a saída que deu certo ganha uma última linha,
  `linear: rode harness.py linear espelhar depois do merge do PR da passagem`; na montagem, a última é
  `linear: rode harness.py linear espelhar depois do push`. Ela vem também depois de `PR #<n> já aberto`, não entra no
  corpo do commit nem no do PR e não sai com a falha de um passo.
- A guarda pede confirmação antes do comando, que abre branch e PR no origin.

## fichas

lista as fichas da passagem e do backlog do código, com o estado de cada uma

`harness.py fichas [<ação>]`

Lista as fichas da passagem e do backlog do código, uma por linha, com o estado de cada uma; `fichas nova` cria a
ficha do código seguinte.

- De onde vêm: as `FICHA-NN` do `ids` do manifesto da cópia da passagem (`caminhos.passagem`), com o texto do trecho
  no arquivo da cópia, e as fichas do código, uma por arquivo `<prefixo>-NN-<slug>.md` em `caminhos.backlog`. Saem as
  FICHA e depois as do prefixo, cada grupo em ordem de número, com o ID alinhado à esquerda.
- As fichas do código vêm de três fontes, sem repetir o nome do arquivo, nesta ordem: a árvore; a árvore principal,
  quando o comando roda numa lane, com as fichas ainda sem commit; e o `origin/<ramo_principal>`, sem fetch, com as
  que já entraram nele e ainda faltam numa árvore atrás dele.
- O estado vem dos blocos: as lanes vivas, as worktrees do `git worktree list` dentro de `lane.pasta` com um bloco
  cujo `ramo` é a branch delas, e os blocos do `origin/<ramo_principal>`, sem fetch; sem essa ref, como na montagem,
  nenhum.
- As situações, na primeira que vale:
  - `saiu da passagem/vN`: a FICHA de lane viva que o manifesto da cópia não tem mais;
  - `em bloco (<estado>)`: com lane viva;
  - `fechada`: com o bloco em `closing` no ramo principal e sem lane;
  - `bloco sem lane (<estado>)`: com o bloco no ramo principal noutro estado, que só um merge feito fora do harness
    produz;
  - `na lane <ID>; entra no <ramo_principal> com o PR dela`: a ficha do código que só existe na lane do bloco `<ID>`;
  - `fora da forma (<problema>)`: a ficha do código aberta que ainda não tem a forma que o `lane abrir` pede, como a
    criada pelo `fichas nova` e ainda por preencher;
  - `pronta`: aberta, com cada FICHA e ficha do código do Depende fechada e cada PEND fora das pendências do manifesto;
    a ficha do código com `Prioridade: urgente` e pronta leva ` · urgente` no fim da linha;
  - `espera <ID> (<estado>)`: aberta, com o primeiro do Depende que falta, em `aberta no planejamento`,
    `sem a cópia da passagem` (a PEND antes da primeira cópia), `em bloco, <estado>`, `bloco sem lane, <estado>`,
    `na lane <ID>`, `aberta` ou `não existe`.
- Sem ficha nenhuma, `nenhuma ficha`.
- O ID de ficha do código em mais de um arquivo vale pelo primeiro, em ordem do caminho, e sai no fim, depois das
  linhas, como `atenção: <ID> em mais de um arquivo: <caminhos>`, sem mudar a saída 0.
- `fichas nova <slug>`: o slug em minúsculas e algarismos, com hífens. O número é o maior do prefixo, mais 1, entre as
  fichas da árvore, as da árvore principal, as do `origin/<ramo_principal>`, sem fetch, as das lanes vivas e os
  blocos do prefixo, nas lanes e no ramo principal: nenhum número se reusa. Cria `<backlog>/<prefixo>-NN-<slug>.md`
  com o título e os onze campos (Marco, Depende, Tamanho, Prioridade, Contexto, Fonte, Objetivo, Escopo, Fora,
  Restrições e Aceite), cada um com o comentário do molde, e imprime `<caminho> criada; preencha os campos`.
- Recusas, com saída 1: `fora de um repositório git`; `slug inválido: <slug>`; `<caminho> já existe`;
  `<caminho>: estado.md inválido: <motivo>`; `<passagem>/manifesto.json: manifesto ilegível: <motivo>`; e
  `falta <arquivo>; a cópia muda só por harness.py importar`.

### fichas nova

cria a ficha do código seguinte, com os campos do molde

`harness.py fichas nova <slug>`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<slug>` | sim | o nome curto, em minúsculas, com hífens |

## contexto

grava o Context Packet do bloco da lane, ou o imprime para uma ficha

`harness.py contexto [<ficha>] [--imprimir]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<ficha>` | não | o ID da ficha, com --imprimir |
| `--imprimir` | não | imprime o pacote da ficha, sem gravar |

Monta o Context Packet de uma ficha: o pacote de leitura com o texto dela, os arquivos da passagem que ela cita por
link e os trechos dos IDs que ela cita, pela cópia da passagem da árvore (`caminhos.passagem`) e pelo manifesto dela.

- Dois usos. `contexto`, dentro da lane de um bloco, regrava `<blocos>/<pasta do bloco>/contexto.md` da lane, sem
  commit, e imprime o resumo. `contexto <ficha> --imprimir`, em qualquer árvore, imprime o pacote da ficha, sem
  gravar. A ficha vem da cópia da passagem, as FICHA, ou do backlog do código.
- As seções, nesta ordem, e a vazia sai: o título `# Context Packet: <ID> (passagem/vN)`; com o Contexto `sim`, a
  linha `Esta ficha pede contexto além deste pacote: o contexto-leitor completa (fase 6d).`; `## Ficha`, com o texto
  da ficha; `## Para ler`; `## Fatos`; `## Também citados`; `## Pendências abertas citadas`; e
  `## Não achados na passagem`.
- Para ler: até 5 arquivos da passagem que a ficha cita por link, resolvidos a partir do arquivo dela, sem repetir,
  na ordem. O link com esquema, o só de âncora e o que sai da cópia ou não está no manifesto ficam de fora.
- Fatos: os IDs citados que o manifesto define, primeiro os do campo Fonte, na ordem deles, e depois os outros, na
  ordem em que aparecem na ficha. Cada um vem com `### <ID> · <passagem>/<arquivo>:<primeira>-<última>` e o texto do
  trecho. Os títulos do trecho descem abaixo do `### <ID>`: o mais alto vai a `####` e os outros o mesmo tanto, até
  `######`, sem mexer nos blocos de código; o trecho sem título, ou com o mais alto já em `####` ou abaixo, sai igual.
- Corte: até 8 fatos e 1.200 palavras, contadas pelos espaços, sem o texto da ficha. O fato que não cabe vai para
  `## Também citados`, só com o ID, o caminho e as linhas, e o seguinte ainda pode entrar.
- Pendências abertas citadas: os PEND citados que estão nas pendências do manifesto, com o texto de lá; o resolvido
  não aparece. Não achados na passagem: os outros IDs citados que o manifesto não define, menos os das fichas do
  código.
- Resumo: `contexto.md com <f> fatos, <t> também citados e <p> pendências`.
- Recusas, com saída 1: `fora de lane: rode dentro da lane do bloco, ou use harness.py contexto <ficha> --imprimir`;
  `sem a cópia da passagem em <passagem>/; rode harness.py importar`; `<ID> não existe nesta árvore`;
  `fora de um repositório git`; e, como uso inválido, `a ficha vai com --imprimir` e `o --imprimir pede a ficha`.

## verificar

roda as verificações do perfil para o momento, na árvore atual

`harness.py verificar --momento {stop,finalizar}`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `--momento {stop,finalizar}` | sim | stop: as que casam com o que mudou; finalizar: todas as do fim do bloco |

Roda as verificações do perfil (`[[desenvolvimento.verificacoes]]`) na árvore atual, a lane ou a árvore principal, para
um dos dois momentos do `--momento`:

- `stop`: as que têm `stop` em `momentos` e um padrão de `caminhos` que casa com um arquivo mudado; com `caminhos`
  vazio, basta qualquer mudado. Sem mudado, nenhuma roda.
- `finalizar`: todas as que têm `finalizar` em `momentos`, mudado ou não.

Mudados são os arquivos do `git diff --name-only <base>...HEAD` e os do `git status`, sem commit e não rastreados. Numa
lane reconhecida pelos arquivos, a base é o `base` do `estado.md` do bloco, se o commit existe; fora de lane, a
merge-base do HEAD com o ramo principal do origin. Sem HEAD ou sem essa base, todo arquivo da árvore conta: os
rastreados e os não rastreados, sem os ignorados.

Antes de rodar, cada caminho de `requer` precisa existir na raiz. Faltando um, o `stop` dá
`<nome>: pulada; falta <caminho>`, sem falha, e o `finalizar` dá `<nome>: falta <caminho>`, com falha.

Cada verificação roda por `sh -c "<comando>"`, na raiz da árvore, com o ambiente herdado, a entrada fechada e a saída
de erro junto da saída, num grupo de processos próprio. Ela acaba quando o `sh` sai, sem esperar o processo em segundo
plano que segure a saída. No fim, pela saída do `sh`, pelo `tempo_limite`, pelo Ctrl-C, pelo SIGTERM ou pelo SIGHUP, o
grupo inteiro morre, os processos em segundo plano inclusive. As linhas:

- `<nome>: ok (<s> s)`, com o tempo numa casa decimal;
- `<nome>: falhou (saída <c>)`, seguida das últimas 30 linhas da saída, com recuo de 2;
- `<nome>: passou de <t> s`, que conta como falha, seguida das últimas 30 linhas da saída;
- sem nenhuma a rodar: `nada a verificar`.

Com `GITHUB_ACTIONS=true`, a falha, a que passou do tempo e a de `requer` ganham mais duas coisas:

- logo abaixo da linha da falha, uma linha
  `<nome>: a saída diz que falta o comando <cmd>; declare a instalação em [desenvolvimento.ci] instalar`
  para cada comando que a saída inteira, não só as 30 linhas, diz que falta, pelas linhas
  `sh: <n>: <cmd>: not found` ou `<cmd>: command not found`, sem repetir e na ordem;
- depois das 30 linhas, a anotação `::error title=harness: <nome> falhou::<primeira linha>`, com a primeira linha da
  falta ou, sem ela, a linha da falha.

O comando sai com 0 sem falha e com 1 com alguma. A pulada não é falha.

Numa lane, o `--momento stop` sem falha grava a marca da árvore, o resumo do HEAD, do `git diff HEAD --binary`, sem o
diff externo nem o textconv da configuração do usuário, e da lista e do conteúdo dos não rastreados, em
`harness-verificado`, no diretório do git da lane. O Stop da lane compara a marca antes de rodar: igual à gravada,
nada roda. O `finalizar` e a árvore principal não gravam marca.

No Stop, as verificações somam até 840 s, abaixo do tempo limite do hook: cada uma roda com o menor entre o
`tempo_limite` dela e o que resta, e a que não cabe, por não começar ou por ser interrompida no teto, dá
`<nome>: sem tempo no Stop; rode harness.py verificar --momento stop`, sem falha e sem gravar a marca. Pelo terminal,
o `verificar` não tem esse teto.

## ci

comandos do CI do projeto, que só rodam no GitHub Actions

`harness.py ci <ação>`

Roda no CI, um por um, os comandos de `[desenvolvimento.ci] instalar` do perfil, na raiz do projeto, por `sh -c`, com a
entrada fechada e o tempo limite de 900 s cada. Só roda com `GITHUB_ACTIONS=true`; fora do CI, recusa. Sem comando na
lista, diz que não há o que instalar.

Cada comando roda no ambiente do runner. Entre um comando e o seguinte, o PATH e as variáveis que o anterior gravou
nos arquivos `GITHUB_PATH` e `GITHUB_ENV` valem para o seguinte, como entre os passos do GitHub Actions: no
`GITHUB_PATH`, cada linha não vazia vai para a frente do PATH; no `GITHUB_ENV`, valem `NOME=valor` e o bloco
`NOME<<DELIM`, até a linha `DELIM`.

As linhas:

- `instalação do CI: <comando>: ok (<s> s)`;
- `instalação do CI: <comando> falhou (saída <c>)` ou `instalação do CI: <comando> passou de 900 s`, seguida das
  linhas de comando que falta, das últimas 30 linhas da saída e da anotação `::error`.

O primeiro que falha para a lista, e o comando sai com 1; com todos ok, sai com 0.

Serviço que precisa ficar de pé, como um banco, sobe com `docker compose up -d` ou `docker run -d`, que o deixam no
Docker. O `&` não serve: o processo em segundo plano morre com o grupo de processos do comando, que acaba no fim dele.

### ci instalar

roda os comandos de [desenvolvimento.ci] instalar, um por um

`harness.py ci instalar`

## aceitacao

confere e anota a aceitação do bloco da lane

`harness.py aceitacao <ação>`

Confere e anota a aceitação do bloco da lane, no `aceitacao.md` da pasta do bloco, que o bloco planejado gera da seção
`## Verificação externa` da spec do bloco. Roda só dentro da lane, reconhecida pelos arquivos.

- `conferir`: confere os itens de antes do merge com prova automática, `<alias> GET|HEAD|POST <caminho> -> <código>`.
  A URL é o alias da prova, de `aceitacao.aliases`, com cada `{porta.<nome>}` trocado pela porta da lane, mais o
  caminho. Com algum item automático do momento, o pedido de cada item vem do subitem `pedido:` do `spec.md` do bloco,
  que tem de ter o hash do `spec` do `estado.md`; diferente, ou sem o `spec.md`, a recusa é
  `aceitacao conferir: spec.md mudou depois da aprovação; rode harness.py bloco replanejar`, sem gravar nada. O pedido
  traz os `cabecalhos`; o `corpo`, só no POST, em JSON, com `Content-Type: application/json` quando os cabeçalhos não
  trazem outro; e os `campos` esperados no JSON da resposta, em que `"*"` quer dizer presente e não nulo. Cada
  `{env.NOME}` do caminho, dos cabeçalhos e do corpo é trocado pelo valor da variável: do ambiente do processo e, sem
  ela, do primeiro arquivo de env da lane que a define, cada `env_copiados` na ordem e depois o `.env` gerado do
  `env_modelo`. O valor não vai para a saída, para o arquivo nem para o commit; no caminho, entra codificado para URL.
  A requisição vai direto, sem o proxy do ambiente, e não segue redirecionamento: o 3xx conta como o código. O tempo
  limite é o `aceitacao.tempo_limite`. O resultado é `ok`, com o código esperado e os campos conferidos,
  `falhou: <código>`, `falhou: sem resposta (<motivo>)`, `falhou: passou de <t> s`, `falhou: sem a variável NOME` ou
  `falhou: variável NOME com quebra de linha`, sem requisição, `falhou: resposta sem JSON`,
  `falhou: sem o campo <caminho>` ou `falhou: campo <caminho> diferente do esperado`. O Resultado e a Data dos itens
  conferidos vão para o arquivo, num commit `chore(<ID>): aceitação` só com ele, que deixa o resto do índice como
  estava; sem mudança no arquivo, não há commit.
- `conferir --depois`: confere os itens de depois do merge, com o mesmo pedido e a mesma recusa da spec mudada, só
  imprimindo, sem gravar nem fazer commit.
- `anotar <n> ok|falhou "<nota>"`: grava `ok: <nota>` ou `falhou: <nota>`, com a nota numa linha, e a Data no item
  manual de antes do merge, com o mesmo commit; a guarda pede a confirmação do usuário. Recusa o item que não existe, o
  de prova automática e o de depois do merge, que se anota no `harness.py lane fechar --manual`.

A saída traz uma linha `<n> <prova>: <resultado>` por item do momento e o veredito na última:
`ACEITACAO OK: <n> item(ns)`; `ACEITACAO MANUAL: <k> de <n> item(ns): <números>`, quando todo item pendente de antes
do merge é manual e ainda sem resultado; ou `ACEITACAO PENDENTE: <k> de <n> item(ns): <números>`. Os manuais de antes
contam pelo Resultado gravado, e o `—` é pendente; no `--depois`, os manuais contam como pendentes. O `conferir` sai
com 0 no OK e com 1 no MANUAL e no PENDENTE; o `anotar` imprime o item anotado e o veredito de antes e sai com 0.

Fora de lane, a recusa é `fora de lane: rode dentro da lane do bloco`; sem o arquivo,
`<blocos>/<pasta>/aceitacao.md não existe; o bloco planejado o gera`; com um alias que saiu do perfil depois da
geração, `item <n>: alias <alias> não está em aceitacao.aliases`, sem gravar nada. No `conferir`, as linhas saem antes
do commit: com ele recusado, a recusa vem depois delas.

### aceitacao conferir

confere os itens com prova automática e grava o resultado

`harness.py aceitacao conferir [--depois]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `--depois` | não | confere os itens de depois do merge, só imprimindo |

### aceitacao anotar

anota o resultado de um item manual de antes do merge

`harness.py aceitacao anotar <n> {ok,falhou} <nota>`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<n>` | sim | o número do item |
| `{ok,falhou}` | sim | ok ou falhou |
| `<nota>` | sim | o que foi visto, entre aspas |

## prepush

recusa o push direto no ramo principal; chamado pelo hook pre-push do git

`harness.py prepush [<remoto>] [<url>]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<remoto>` | não | o nome do remoto, que o git passa |
| `<url>` | não | o endereço do remoto, que o git passa |

Chamado pelo hook `pre-push` do git, o `.githooks/pre-push` do repositório de código, que roda
`exec python3 .claude/harness/harness.py prepush "$@"`. O git passa o nome e o endereço do remoto, que o comando aceita
e não usa, e escreve no stdin uma linha por ref do push, na forma
`<ref local> <sha local> <ref remota> <sha remota>`, com os shas em hexadecimal de 40 ou 64 caracteres; sha só de
zeros é a ref que não existe daquele lado. Linha em branco não conta. A linha que não tem quatro campos, ou que tem um
sha fora dessa forma, dá `pre-push do harness: linha do git fora da forma: <linha>`.

Na ref remota `refs/heads/<ramo>`, com o `ramo_principal` do perfil:

- sha local só de zeros, a remoção: `pre-push do harness: apagar o <ramo> no remoto recusado`;
- sha remota só de zeros, a criação, que é a da montagem: passa;
- os outros casos, a atualização: `pre-push do harness: push direto no <ramo> recusado; abra um PR`.

As outras refs passam. O comando imprime as recusas, uma por linha, e sai com 1 com alguma, o que para o push; sem
recusa, não imprime nada e sai com 0.

O `git push --no-verify` pula o hook; a guarda pergunta antes de deixá-lo rodar.

Pelo terminal, o `prepush` lê o stdin só quando ele não é um terminal, como em
`echo "<linha>" | python3 .claude/harness/harness.py prepush`; sem linhas, passa.

## bloco

muda o estado do bloco da lane, um passo por vez

`harness.py bloco <ação>`

Muda o estado do bloco da lane, um passo por vez. Roda dentro da lane do bloco; fora dela, a recusa é
`fora de lane: rode dentro da lane do bloco`.

| Ação | De → para | Confere antes |
|---|---|---|
| `planejado [--curto]` | `planning` → `ready_for_execution` | o `spec.md` com a `## Verificação externa` e o `plano.md` no formato do plano; a lane limpa fora do bloco; gera o `aceitacao.md`; grava o `caminho` (`normal`, ou `curto` com o `--curto`) e o hash da `spec.md` no `estado.md` |
| `executando` | `ready_for_execution` → `executing` | — |
| `executado` | `executing` → `ready_for_review` | a lane sem alteração pendente e o ledger do SDD do plano com todas as tarefas feitas; grava o `rulings.md` com as decisões dele |
| `revisando` | `ready_for_review` → `reviewing` | — |
| `revisado` | `reviewing` → `ready_for_closure` | o `revisao.md` sem item em `## Em aberto` |
| `corrigir` | `reviewing`, ou `closing` sem PR mesclado → `executing` | em `closing`, os PRs da branch |
| `finalizar [--resumo "<texto>"]` | `ready_for_closure` → `closing` | a `spec.md` igual à aprovada, a lane sem alteração, a passagem nova, as verificações e a aceitação; empurra e abre o PR |
| `bloquear "<motivo>"` | os seis de `planning` a `ready_for_closure` → `blocked` | o motivo |
| `desbloquear [--replanejar \| --seguir <ficha>]` | `blocked` → pela causa | a opção que a causa pede |
| `status [--para <skill>]` | — | só lê: a linha do bloco com o estado, o caminho, a lane, a passagem, a spec e o próximo passo; sai sempre com 0 |
| `replanejar "<motivo>"` | de `ready_for_execution` a `ready_for_closure` → `planning` | o motivo; descarta a aprovação da `spec.md` e tira do bloco o plano, a aceitação, os rulings, a revisão e o gabarito |

Cada ação, nesta ordem: confere a transição (`<ID> está em <estado>; bloco <ação> vale só em <estados>`); confere o
que o passo exige; grava o `estado.md`, com o estado, o anterior, os campos do passo e o `atualizado_em`; faz o commit
`chore(<ID>): <estado novo>`; regrava o `LANES.md`; e imprime `<ID>: <de> → <para>`. O `LANES.md` que não regrava não
muda a saída: vem a linha `LANES.md não regravado: <motivo>`, depois da transição.

Repetir não faz mal: no estado de destino, a ação imprime `<ID> já está em <estado>`, sai com 0 e não faz commit.

Com a `[desenvolvimento.linear]` no perfil, toda ação que muda o estado avisa o Linear depois de imprimir as linhas
(`harness.py linear` traz o formato do comentário): o status da issue da ficha, o rótulo de bloqueio e o responsável
mudam com o estado novo, e o status pode recuar. O aviso não muda a saída nem o código de saída; o que não foi traz uma
linha a mais, `linear: aviso não enviado (<motivo>); rode harness.py linear espelhar`. O `finalizar` leva o link do PR
no comentário, e o que só retoma, `closing → closing`, avisa só quando traz o link do PR.

As recusas do passo:

- `planejado [--curto]`: `bloco planejado: falta <blocos>/<pasta>/spec.md`, a mesma com o `plano.md`; depois, nesta
  ordem:
  - a lane com entrada do `git status` fora da pasta do bloco, sem contar os ignorados:
    `bloco planejado: a lane tem alterações sem commit fora do bloco: <até 5 caminhos>; o código muda só na execução`;
  - o plano, com as tarefas lidas fora dos blocos de código: `bloco planejado: plano sem ### Task N`,
    `bloco planejado: Task <n> sem a lista Files com Create, Modify ou Test` e
    `bloco planejado: o plano não aponta para a spec do bloco na linha **Spec:**`;
  - o `--curto`: `bloco planejado: --curto vale só para ficha <prefixo>`,
    `bloco planejado: bloco curto sem ## Causa com a linha Prova:` e
    `bloco planejado: bloco curto com <n> tarefas; o limite é 3; replaneje como bloco normal`;
  - as da leitura da `## Verificação externa`, como `spec.md sem a seção ## Verificação externa`.

  O `--curto` grava `caminho: curto`. O hash da `spec.md` troca `\r\n` por `\n`. Grava o `efeito_externo`: `não`
  com `nenhuma`, `sim` com itens. O commit leva o `spec.md`, o `plano.md`, o `aceitacao.md`, o `contexto.md`, o
  `contexto-leitor.md`, os `pesquisa-*.md` e o `estado.md`, os que mudaram.
- `executado`: `bloco executado: a lane tem alterações sem commit`, com o `git status --porcelain` não vazio; os
  arquivos ignorados não contam, o ledger do SDD entre eles. Depois, o ledger do plano: a pasta de
  `.superpowers/sdd/` cujo `plan-path` é o `plano.md` do bloco. Sem ela,
  `bloco executado: falta o ledger do SDD do plano.md; rode o /ela-harness:executar-bloco`; com tarefa sem a linha
  `Task <N>: complete`, `bloco executado: o ledger do SDD não dá como feita a tarefa <N>` (`feitas as tarefas 2 e 3`
  no plural). Grava o `rulings.md` com as linhas `Ruling:` do ledger, uma por linha, ou com
  `Nenhuma decisão foi tomada em nome de <dono.nome>.`, e o leva no commit da transição.
- `revisado`: `bloco revisado: revisao.md tem <n> itens em ## Em aberto` (`1 item` no singular) e
  `bloco revisado: falta revisao.md com a seção ## Em aberto`. Item é a linha que começa, sem recuo, por `-`, `*`,
  `+`, `N.` ou `N)` e um texto, entre o título e o próximo título, fora dos blocos de código e dos comentários
  `<!-- -->`; o subitem recuado é parte do item. O commit leva o `revisao.md` e o `estado.md`.
- `bloquear "<motivo>"`: grava o `bloqueio` `manual` e o motivo, com os espaços e as quebras juntados num espaço;
  vazio ou `—`, `bloco bloquear: o motivo não pode ficar vazio`. Em `closing`, a recusa é
  `bloco bloquear: <ID> está em closing; rode harness.py bloco corrigir antes`.

O commit leva só os arquivos do passo que mudaram: o que já estava no índice e o que mudou no disco continuam como
estavam. Ele roda o pre-commit; recusado, os arquivos que o harness gravou no passo (o `estado.md` e, no `planejado`, o
`aceitacao.md`) voltam ao último commit, e a recusa é `git commit falhou: <motivo>; <arquivo> voltou ao último commit`,
ou `<a> e <b> voltaram ao último commit`.

- `corrigir`: de `reviewing`, ou de `closing` com o PR da branch aberto, fechado sem merge ou ainda sem PR, como
  depois de um push que falhou; com o PR mesclado no ramo principal, a recusa é
  `bloco corrigir: o PR #<n> já foi mesclado; rode harness.py lane fechar <ID> de uma sessão aberta na árvore principal, ou pelo terminal como última ação`.
  O PR mesclado noutra base não conta. Os PRs saem do `gh pr list --head <branch> --state all`. O commit leva o
  `revisao.md`, quando mudou.
  De `reviewing`, encerra a revisão: antes do commit, o `gabarito.md` que o `revisao preparar` gravou volta ao último
  commit, e o que não tem commit sai do disco (a volta que falha recusa com
  `bloco corrigir: <blocos>/<pasta>/gabarito.md não voltou ao último commit`); depois do commit, apaga a marca da
  revisão em andamento.
- `finalizar [--resumo "<texto>"]` confere, nesta ordem: a spec aprovada, só de `ready_for_closure`
  (`bloco finalizar: spec.md mudou depois da aprovação; rode harness.py bloco replanejar`); a lane sem alteração
  (`bloco finalizar: a lane tem alterações sem commit`); a passagem nova do `origin/<ramo_principal>`, depois do
  `git fetch` dele e antes das verificações, que podem levar minutos
  (`bloco finalizar: passagem/v<N> mudou <IDs>; rode harness.py lane conferir`, e a recusa do fetch como está); as
  verificações do momento `finalizar` (`bloco finalizar: verificação <nome> falhou`, a primeira, seguida das linhas
  das que falharam; a que `requer` um arquivo que falta falha); e, com efeito externo, os itens de antes do merge do
  `aceitacao.md` em `ok` (`bloco finalizar: aceitação pendente: item <n>`, ou `itens <a> e <b>`). Depois, grava
  `closing`, com o corpo no commit; faz o `git push -u origin <branch>`, com 60 s; e, sem PR aberto da branch, com
  30 s, o
  `gh pr create --base <ramo_principal> --head <branch> --title "<tipo>(<ID>): <resumo>" --body <corpo> --assignee <dono.github>`.
  O tipo é o começo da branch; o resumo, o `--resumo` com os espaços juntados, ou o slug com espaços. O corpo tem as seções `## Objetivo` (o Objetivo da ficha, ou `—`), `## Aceitação` (a tabela
  do `aceitacao.md`, ou `Sem verificação externa.`) e `## Verificações` (as linhas do `verificar`). As linhas são a da
  transição, `branch <branch> enviada ao origin` e `PR #<n> aberto: <url>`, ou `PR #<n> já aberto: <url>` com o PR
  aberto. A falha depois do commit dá
  `closing gravado, mas <passo> falhou: <motivo>; rode harness.py bloco finalizar de novo`, com saída 1. Em
  `closing`, o `finalizar` retoma: imprime `<ID> já está em closing; retomado`, não confere nada, refaz o push e abre o
  PR que falta, com o corpo do último commit `chore(<ID>): closing` da lane. Com o PR da branch já mesclado no ramo
  principal, recusa antes do push, com
  `bloco finalizar: o PR #<n> já foi mesclado; rode harness.py lane fechar <ID> de uma sessão aberta na árvore principal, ou pelo terminal como última ação`.

- `desbloquear [--replanejar | --seguir <ficha>]` age pela causa do bloqueio, o `bloqueio` do `estado.md`:
  - `manual`, sem opção, volta ao `estado_anterior`; com uma,
    `bloco desbloquear: bloqueio por manual; use bloco desbloquear sem opção`.
  - `passagem`, gravada pelo `lane conferir`, pede uma de duas opções
    (`bloco desbloquear: bloqueio por passagem; use --replanejar ou --seguir <ficha <prefixo>>`). O `--replanejar`,
    com a cópia da lane na versão da cópia do `origin/<ramo_principal>`, sem fetch, vai a `planning`; com a cópia
    velha, ou sem a do ramo principal, `bloco desbloquear: traga o <ramo_principal> para a lane antes de replanejar`.
    O `--seguir <ficha>` pede uma ficha do código, `<prefixo>-NN`
    (`bloco desbloquear: --seguir pede uma ficha <prefixo>-NN`), que esteja no backlog da lane ou no do
    `origin/<ramo_principal>` (`bloco desbloquear: <ficha> não existe na lane nem no <ramo_principal>`); volta ao `estado_anterior` e grava na
    `passagem` a versão que travou o bloco, o N do motivo `passagem/vN mudou <IDs>`, no commit
    `chore(<ID>): <estado>` com o corpo `A diferença da passagem/v<N> segue na <ficha>.`, que leva também a ficha,
    quando ela mudou na lane. O motivo fora dessa forma, que só uma edição fora do harness produz, recusa com
    `bloco desbloquear: motivo fora da forma passagem/vN mudou <IDs>: <motivo>`.
  - `retorno`, gravado pelo `retorno abrir`, pede o `--replanejar`
    (`bloco desbloquear: bloqueio por retorno; use --replanejar`); com a cópia da lane numa versão mais nova que a
    `passagem` do bloco, vai a `planning`; com a mesma, com o N da cópia,
    `bloco desbloquear: a lane ainda está na passagem/v<N>; traga o <ramo_principal> com a versão que resolve o retorno`.
  - Ir a `planning` grava na `passagem` a versão da cópia da lane, volta o `efeito_externo`, o `caminho` e a `spec` a `—` e regrava o
    `contexto.md`, no commit `chore(<ID>): planning`, que leva o `estado.md`, o `contexto.md` e os arquivos tirados,
    como no `replanejar`.
- `replanejar "<motivo>"` volta a `planning` e descarta a aprovação da spec, que o dono dá de novo. Em `closing`,
  `bloco replanejar: <ID> está em closing; rode harness.py bloco corrigir antes`; em `blocked`,
  `bloco replanejar: <ID> está em blocked; rode harness.py bloco desbloquear`; o motivo vazio ou `—`,
  `bloco replanejar: o motivo não pode ficar vazio`. Grava o `efeito_externo`, o `caminho` e a `spec` em `—`, regrava
  o `contexto.md` e tira do bloco o `plano.md`, o `aceitacao.md`, o `rulings.md`, o `revisao.md` e o `gabarito.md`
  que existem, no commit `chore(<ID>): replaneja: <motivo>`; a spec, o `contexto-leitor.md` e os `pesquisa-*.md`
  ficam. Depois do commit, apaga o ledger do SDD do plano e a marca da revisão em andamento. As linhas, depois da
  transição: `  tirados do bloco: <arquivos>` e `  ledger do SDD apagado: <pasta>`, quando houve. Recusado o commit,
  os arquivos tirados voltam como estavam, e o ledger fica. O ledger que não se apaga depois do commit dá, por último,
  `planning gravado, mas apagar o ledger do SDD <pasta> falhou: <motivo>; apague a pasta antes do /ela-harness:executar-bloco`,
  com saída 1; a marca da revisão se apaga do mesmo jeito.

### bloco planejado

planning → ready_for_execution: confere a spec e o plano e gera o aceitacao.md

`harness.py bloco planejado [--curto]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `--curto` | não | bloco curto: a spec com a prova da causa e o plano de até 3 tarefas |

### bloco executando

ready_for_execution → executing

`harness.py bloco executando`

### bloco executado

executing → ready_for_review, com a lane sem alteração pendente e o ledger do SDD com as tarefas feitas

`harness.py bloco executado`

### bloco revisando

ready_for_review → reviewing

`harness.py bloco revisando`

### bloco revisado

reviewing → ready_for_closure, com o revisao.md sem item em aberto

`harness.py bloco revisado`

### bloco corrigir

reviewing, ou closing sem PR mesclado → executing

`harness.py bloco corrigir`

### bloco finalizar

ready_for_closure → closing: confere, empurra a branch e abre o PR

`harness.py bloco finalizar [--resumo <texto>]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `--resumo <texto>` | não | o título do PR depois do tipo e do ID; o padrão é o slug com espaços |

### bloco desbloquear

destrava o bloco pela causa do bloqueio

`harness.py bloco desbloquear [--replanejar | --seguir <ficha>]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `--replanejar` | não | volta a planning, com a lane na versão nova da passagem |
| `--seguir <ficha>` | não | segue na versão antiga, com a diferença na ficha do código dada |

### bloco bloquear

trava o bloco

`harness.py bloco bloquear <motivo>`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<motivo>` | sim | por que o bloco para, entre aspas |

### bloco replanejar

de ready_for_execution a ready_for_closure → planning: descarta a aprovação da spec

`harness.py bloco replanejar <motivo>`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<motivo>` | sim | por que a spec aprovada muda, entre aspas |

### bloco status

mostra o estado do bloco e o próximo passo; sai sempre com 0

`harness.py bloco status [--para {planejar-bloco,executar-bloco,revisar-bloco,finalizar-bloco}]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `--para {planejar-bloco,executar-bloco,revisar-bloco,finalizar-bloco}` | não | a skill que pergunta; diz quando o estado do bloco é de outra |

## lane

abre, confere e fecha as lanes dos blocos

`harness.py lane <ação>`

Abre, confere e fecha as lanes dos blocos. A lane é uma worktree em `<lane.pasta>/<ID>-<slug>`, na branch
`<tipo>/<ID>-<slug>`, com as portas da lane `k` e o bloco em `<blocos>/<ID>-<slug>/`.

`lane abrir <ficha> [--tipo <tipo>]` abre a lane da ficha. O tipo é um de `feat`, `fix`, `chore`, `refactor`, `infra`,
`cicd` e `docs`, `feat` por padrão; ele vai à branch e ao título do PR. O comando roda de qualquer árvore do
repositório e age na árvore principal.

O portão confere tudo antes de mudar qualquer coisa; a recusa é `portão recusou: <motivo>`, com saída 1:

1. o `git fetch` do ramo principal (`origin não consultado: <motivo>`); a árvore principal no ramo principal
   (`a árvore principal não está no <ramo_principal>`) e igual ao origin
   (`<ramo_principal> local à frente do origin; leve os commits por PR` e
   `<ramo_principal> local atrás do origin; rode git pull`). As alterações sem commit da árvore principal não impedem;
2. a ficha: a FICHA na cópia da passagem, a do código no backlog, também sem commit na árvore principal
   (`<ID> não existe`), sem bloco vivo (`<ID> já tem bloco (<estado>)`) nem fechado (`<ID> já fechada`), fora de outra
   lane (`<ID> está na lane de <ID da lane>; entra no <ramo_principal> com o PR dela`), num arquivo só
   (`<ID> em mais de um arquivo: <caminhos>`) e, na FICHA, com o slug do título na forma do `estado.md`
   (`<ID>: slug fora da forma: <slug>`);
3. a forma da ficha do código (`<ID>: <problema>`), a do `fichas`;
4. as dependências (`<ID> espera <dependência> (<estado>)`);
5. uma lane livre de 1 ao `lane.limite` (`<n> lanes vivas; o limite é <limite>`);
6. a branch livre na máquina e no origin (`a branch <branch> já existe`), pelo nome exato, e a pasta da lane
   (`a pasta <pasta> já existe`);
7. o `env_modelo`, quando o perfil o tem, no `origin/<ramo_principal>` (`<env_modelo> não existe no <ramo_principal>`),
   só com os marcadores `{porta.<nome>}`, `{n}`, `{id}` e `{slug}` (`<env_modelo> cita {<marcador>}, que não existe`);
8. o `.env` que o `env_modelo` gera (ele sem o `.example`) e cada `env_copiados` ignorados pelo git, pelo
   `git check-ignore` na árvore principal (`<arquivo> não é ignorado pelo git; ponha-o no .gitignore`).

Depois do portão, em ordem: o `git worktree add --no-track -b <branch> <pasta> origin/<ramo_principal>`, que recusa
com `git worktree add falhou: <motivo>`; o número da lane, no arquivo `harness-lane` do diretório do git da
worktree (`<repositório>/.git/worktrees/<pasta>/`), com uma quebra, para o `--abandonar` achá-lo sem o `estado.md`; o
`.env` do `env_modelo`, com os marcadores trocados; a cópia dos `env_copiados` da árvore principal; cada comando do
`instalar` por `sh -c` na lane, com os marcadores e o `{pasta}`, a pasta absoluta da lane, e 900 s cada; a ficha do
código nova, sem commit na árvore principal, movida para a lane; o `estado.md`, em `planning`, com a lane `k`, a `base`
no `origin/<ramo_principal>` e a `passagem` na versão da cópia; o `contexto.md`; o commit `chore(<ID>): abre a lane`; e
o `LANES.md`.

A saída:

- `portão ok: <ramo_principal> igual ao origin; <ID> aberta; <dependências>; lanes <n> de <limite>`, com as fichas do
  Depende em `<a e b> fechadas` e as pendências em `<a e b> resolvidas`, ou `sem dependências`;
- `lane <ID> aberta em <pasta>`;
- `  branch <branch>; lane <k>: <nome> <porta>, ...`;
- `  .env gerado do <env_modelo>; copiado <arquivos>; instalar ok`, só com as partes que valem;
- `  env_copiados: <arquivo> não existe na árvore principal; pulado`, uma por arquivo que falta;
- `  estado planning; Context Packet com <n> fatos`;
- `Para entrar: EnterWorktree com path <pasta>`.

Lane pela metade: a falha depois do `git worktree add` devolve à árvore principal a ficha do código que já tinha ido à
lane e dá `lane pela metade: <passo> falhou (<motivo>); desfaça com harness.py lane fechar <ID> --abandonar`, com
saída 1. O passo é `harness-lane`, `.env`, `env_copiados`, `instalar`, `ficha`, `estado.md`, `contexto.md` ou
`git commit`; a falha do
`instalar` é `<comando>: saída <código>` ou `<comando>: passou de 900 s`.

`lane conferir` confere as lanes contra o origin. Usa a rede: o `git fetch` do ramo principal, cuja falha é a única
recusa (`origin não consultado: <motivo>`), e, conforme o caso, o `gh pr list` e o `gh issue view`; por isso não roda
em hook. Sai com 0 e imprime, nesta ordem:

- as linhas das worktrees do `lanes`: a pasta sumida, a worktree sem bloco, o `estado.md` inválido e a branch de bloco
  sem worktree;
- por lane, na ordem das fichas:
  - no bloco em `closing`, o PR mesclado no ramo principal: `<ID>: PR #<n> mesclado; rode harness.py lane fechar <ID>`;
  - o bloco afetado pela versão da cópia do `origin/<ramo_principal>`, pelo estado dele: de `planning` a
    `ready_for_closure`, o bloco é travado, com `bloqueio: passagem` e o `motivo` `passagem/v<N> mudou <IDs>`, no
    commit `chore(<ID>): blocked` da lane, e a linha é `<ID>: passagem/v<N> mudou <IDs>; bloco travado (blocked)`, ou
    `<ID>: não travado: <motivo>` quando a trava falha; em `closing`, sem o PR mesclado,
    `<ID>: passagem/v<N> mudou <IDs>; em closing, o bloco não é travado: decida antes do merge`, e, com ele, nada; em
    `blocked`, `<ID>: passagem/v<N> mudou <IDs>; o bloco já está travado (<bloqueio>)`, que não sai quando o bloco já
    foi travado pela mesma versão;
  - no bloco em `blocked` por `retorno`, cada retorno de decisão cuja issue, no repositório da passagem, está fechada
    com um comentário `Resolvida na passagem/v<N>`:
    `<ID>: retorno #<n> resolvido na passagem/v<N>; traga o <ramo_principal> e rode harness.py bloco desbloquear --replanejar`,
    ou `<ID>: retorno #<n> não consultado: <motivo>`;
- os planos que se cruzam, um par de lanes por linha: `<ID> e <ID>: os dois planos mexem em <caminhos>`, pelos
  caminhos entre crases das linhas `- Create:`, `- Modify:`, `- Test:` e `- Delete:` do `plano.md` de cada bloco, sem
  o `:N` ou `:N-M` do fim.

Sem nada a apontar, `lanes em ordem`. No fim, regrava o `LANES.md`.

`lane fechar <ficha> [--manual <n>=ok|falhou ...]` fecha a lane do bloco em `closing` depois do merge do PR. Roda de
fora da lane que fecha (`lane fechar: rode fora da lane <ID>`) e de uma sessão que não foi aberta nela, a de
`CLAUDE_PROJECT_DIR` fora da lane; com a sessão aberta dentro, recusa:
`lane fechar: a sessão foi aberta dentro da lane <ID>; feche a lane de uma sessão aberta na árvore principal, ou pelo terminal como última ação`.
Usa a rede: o `git fetch` do ramo principal, que vem primeiro, o `gh pr list`, o `gh pr view` e o `gh pr comment`. Em
ordem:

1. as recusas, sem mudar nada: `lane fechar: <ID> não tem lane`, `<ID> está em <estado>; lane fechar vale só em closing`
   e `a lane tem alterações sem commit; faça o commit ou descarte antes`. Com a pasta da lane sumida, o `estado.md` e
   o `aceitacao.md` vêm do commit da branch, o commit do PR é a ponta dela, e as alterações sem commit não se
   conferem;
2. o PR da branch, pela precedência: um aberto recusa (`PR #<n> ainda aberto; mescle antes`); senão, vale o mesclado
   de maior número com base no ramo principal, e o resto não conta; sem ele, a recusa é
   `<branch> sem PR; rode harness.py bloco finalizar na lane`. O commit do PR é o HEAD da lane; um commit anterior dá
   a recusa `a lane tem <k> commit(s) depois do PR #<n>, que já foi mesclado; ...`, que termina no
   `git reset --hard <sha>` de volta ao commit do PR, e um commit fora da lane,
   `o PR #<n> foi mesclado com <sha>, que não está na lane; confira antes de fechar`;
3. a aceitação de depois do merge: as provas automáticas de depois, como no `aceitacao conferir --depois`, e os itens
   manuais de depois pelo `--manual <n>=ok|falhou`, repetível. Antes de qualquer prova, o `--manual` recusa
   `item <n> não existe`, `item <n> é de antes do merge; anote com harness.py aceitacao anotar na lane` e
   `item <n> tem prova automática; o lane fechar a confere`. Com efeito externo, o veredito pendente deixa a lane como
   está e dá `ACEITACAO PENDENTE: ...; a lane fica; rode de novo quando o deploy terminar`, com saída 1;
4. o comentário no PR, com `Aceitação depois do merge:`, as linhas dos itens e o veredito, uma por linha, só quando
   nenhum comentário do PR tem o mesmo corpo. A falha do `gh pr view` ou do `gh pr comment` deixa a lane e dá
   `gh pr comment falhou: <motivo>; a lane fica; rode harness.py lane fechar <ID> de novo`, com o comando que falhou,
   e saída 1;
5. o `desmontar`: cada comando por `sh -c` na lane, com os marcadores e o `{pasta}`, e 900 s cada; todos rodam, e
   os que falham viram aviso e não param o fechamento;
6. a remoção: `git worktree remove <pasta>`, que aceita os arquivos ignorados, e `git branch -D <branch>`, cujas falhas
   recusam com `git worktree remove falhou: <motivo>` e `git branch -D falhou: <motivo>`; e o `LANES.md`.

A saída do fechamento:

- `PR #<n> mesclado, com o mesmo commit da lane`;
- `aceitação depois do merge: <linhas dos itens>`, com as linhas separadas por `; `, ou `nenhum item`;
- o veredito, com `; comentado no PR #<n>` ou `; já comentado no PR #<n>`;
- `desmontar ok; worktree e branch removidas`, `desmontar falhou: <comando> (saída <c>); worktree e branch removidas`,
  com `(passou de 900 s)` no tempo esgotado e as falhas juntadas por `e`, ou, sem `desmontar`,
  `worktree e branch removidas`; com a pasta sumida, o `desmontar` não roda, e a linha é
  `desmontar pulado: a pasta da lane sumiu; worktree e branch removidas`.

`lane fechar <ficha> --abandonar` remove a lane sem PR mesclado, em qualquer estado, também a lane pela metade e a de
pasta sumida; não combina com o `--manual`. A lane é a worktree em `lane.pasta` cuja pasta começa por `<ID>-`.
Recusa a lane em que a sessão foi aberta, como o `lane fechar` (`a sessão foi aberta dentro da lane <ID>`). Pula a
aceitação e o comentário e confere só duas coisas:

- a lane sem alteração sem commit; na lane pela metade, a de `estado.md` sem commit ou sem ele, não contam o
  `estado.md`, o `contexto.md` e a ficha do código do bloco, novos;
- nenhum PR da branch aberto (`PR #<n> aberto; feche-o antes de abandonar`), que recusa primeiro, nem mesclado no ramo
  principal (`PR #<n> já mesclado; feche a lane com harness.py lane fechar <ID>`).

A ficha do código do bloco que está na lane e não está nem na árvore principal nem no `origin/<ramo_principal>` volta
à árvore principal, sem commit; com a pasta sumida, a do commit da branch, se ele a tem. Depois vêm o `desmontar`, que
não roda com a pasta sumida, a remoção, com o `--force` na lane pela metade, e o `LANES.md`. A saída é
`lane <ID> abandonada; a ficha fica <estado>`, com o estado do `fichas`, ou `lane <ID> abandonada; a ficha não existe`,
quando o ID não tem ficha, lane nem bloco, depois de `desmontar falhou: <comando> (saída <c>)` ou de
`desmontar pulado: sem o estado.md, a lane não tem número`, quando valem. O `desmontar` usa o número do `estado.md` da
lane; sem ele legível, o do `harness-lane`, que o `lane abrir` grava e que sobra mesmo com o commit dele recusado, e o
slug da pasta; o `pulado` é para a lane sem nenhum dos dois, ou com o do arquivo fora de 1 ao `lane.limite`. O estado
da ficha se calcula sem a outra lane
cujo `estado.md` está fora do formato ou não se lê, e cada uma dessas vira, depois da linha da ficha, uma linha
`atenção: <caminho>: estado.md inválido: <motivo>` ou `atenção: <caminho>: estado.md ilegível: <motivo>`; o abandono
conclui com 0.

Com a `[desenvolvimento.linear]` no perfil, o `lane abrir`, o `lane conferir` que trava um bloco e o `lane fechar`, com
ou sem `--abandonar`, avisam o Linear depois de imprimir as linhas (`harness.py linear` traz o formato do comentário).
O `abrir` diz `pronta → planning`; o `conferir`, uma vez por bloco travado, `<estado> → blocked`, com o motivo; o
`fechar`, `closing → fechada`, com o link do PR mesclado, e o `--abandonar`, `<estado> → pronta (lane abandonada)`,
que devolve a ficha ao status `pronta`; a lane pela metade, sem o `estado.md` no commit, não avisa. O `--abandonar` com o
`estado.md` fora do formato ou ilegível não sabe o estado a avisar e diz, depois das outras linhas,
`linear: aviso não enviado (estado.md ilegível); acerte o status da issue à mão`, porque o espelho não recua uma issue.
O aviso não muda a saída nem o código de saída.

### lane abrir

abre a lane da ficha, depois do portão

`harness.py lane abrir <ficha> [--tipo {feat,fix,chore,refactor,infra,cicd,docs}]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<ficha>` | sim | o ID da ficha |
| `--tipo {feat,fix,chore,refactor,infra,cicd,docs}` | não | o tipo da branch e do PR; feat por padrão |

### lane conferir

confere as lanes contra o origin: passagem nova, PRs mesclados, retornos e planos que se cruzam

`harness.py lane conferir`

### lane fechar

fecha a lane com o PR mesclado e a aceitação de depois do merge

`harness.py lane fechar <ficha> [--manual <<n>=ok|falhou> | --abandonar]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<ficha>` | sim | o ID da ficha |
| `--manual <<n>=ok\|falhou>` | não | o resultado de um item manual de depois do merge |
| `--abandonar` | não | remove a lane sem PR mesclado |

## retorno

abre a issue de retorno no repositório de planejamento

`harness.py retorno <ação>`

`retorno abrir <ID> --tipo fato|decisao --contradiz "<texto>" --evidencia "<texto>"` abre, no repositório de
planejamento (`passagem.repositorio`), a issue de retorno de um ID da passagem que o código contradiz. O ID é um dos
`ids` do manifesto da cópia da passagem da árvore; fora dele, a recusa é `<ID> não está na passagem/v<N>`, e sem a
cópia, `sem a cópia da passagem em <passagem>/; rode harness.py importar`. O `--contradiz` e o `--evidencia` têm os
espaços juntados e não podem ficar vazios (`--contradiz e --evidencia não podem ficar vazios`).

Os dois tipos:

- `fato`: o código provou um fato diferente do planejado; o bloco segue;
- `decisao`: o código pede outra decisão; o bloco vai a `blocked`, com `bloqueio: retorno` e o motivo
  `retorno #<n>: espera a versão da passagem que o resolva`, e espera a versão da passagem que o resolva. Já em
  `blocked`, só a causa e o motivo mudam.

Com a `[desenvolvimento.linear]` no perfil, o retorno de `decisao` que trava o bloco avisa o Linear depois de imprimir a
linha (`harness.py linear` traz o formato do comentário), e o de `fato`, e o que só muda a causa de um bloco já em
`blocked`, não avisa, porque o estado do bloco não muda. O aviso não muda a saída nem o código de saída.

Antes de criar, o comando procura a issue aberta com o mesmo título e o mesmo corpo, com 30 s de limite:
`gh issue list --repo <repositorio> --state open --label retorno --search "<título> in:title"`, com
`--json number,title,body,url --limit 100`. O título é comparado inteiro, e o corpo, sem os espaços do fim; com mais
de uma issue vale a mais antiga. A falha da busca recusa com `gh issue list falhou: <motivo>`. Achando a issue, o
comando não cria outra: ela entra no bloco como a criada, e rodar o mesmo retorno de novo não abre issue repetida. A
issue de mesmo título e outro corpo, como a de outro tipo ou com outra evidência, não conta, e o comando cria a nova.

A issue nova sai pelo `gh issue create --repo <repositorio> --label retorno --title <título> --body <corpo>`, com 30 s
de limite. O título é `retorno: <ID> no bloco <bloco>`, ou `retorno: <ID>` fora de lane. O corpo tem uma linha por
campo:

- `ID afetado: <ID> (<passagem>/<arquivo>, linhas <i> a <f>)`, o trecho do manifesto;
- `Versão da passagem: passagem/v<N>`;
- `Bloco: <ID do bloco> (<branch>)`, ou `Bloco: nenhum` fora de lane;
- `Tipo: fato provado; o bloco segue` ou `Tipo: mudança de decisão; o bloco espera a versão da passagem que a resolva`;
- `O que contradiz: <texto>`;
- `Evidência: <texto>`.

A falha do `gh` recusa com `gh issue create falhou: <motivo>`. Sem o rótulo `retorno` no repositório, a recusa diz
também como criá-lo: `crie o rótulo: gh label create retorno --repo <repositorio>`.

Fora de lane, nenhum estado muda, e a saída é `issue #<n> aberta: <url>`, ou `issue #<n> já aberta: <url>` quando a
issue já existia. Dentro da lane, o `estado.md` do bloco ganha `#<n> <tipo>` nos `retornos` (sem repetir o que já está
lá), no commit `chore(<ID do bloco>): retorno #<n>`, e o `LANES.md` é regravado; a saída é
`issue #<n> aberta: <url>; <ID do bloco> segue (fato)` ou `issue #<n> aberta: <url>; <ID do bloco> travado (blocked)`,
e `issue #<n> já aberta: <url>; registrada no bloco` com a issue que já existia.

Depois da issue, a falha ao gravar o `estado.md` ou ao fazer o commit sai com 1 e a linha
`issue #<n> aberta, mas <passo> falhou: <motivo>; rode o mesmo retorno abrir de novo`, com `estado.md` ou `git commit`
no lugar do `<passo>`. Rodar o mesmo comando de novo acha a issue e termina o registro no bloco.

Com o bloco em `closing`, recusa com
`retorno abrir: <ID do bloco> está em closing; rode harness.py bloco corrigir antes, ou abra o retorno fora da lane`:
o commit do retorno ficaria depois do PR. A guarda pede a confirmação do usuário.

### retorno abrir

abre o retorno de um ID da passagem que o código contradiz

`harness.py retorno abrir <ID> --tipo {fato,decisao} --contradiz <contradiz> --evidencia <evidencia>`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<ID>` | sim | o ID da passagem |
| `--tipo {fato,decisao}` | sim | fato: o bloco segue; decisao: o bloco espera a versão que o resolva |
| `--contradiz <contradiz>` | sim | o que o código mostrou de diferente |
| `--evidencia <evidencia>` | sim | a prova, como a resposta de um serviço |

## lanes

imprime o quadro das lanes e regrava o LANES.md

`harness.py lanes [--hook]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `--hook` | não | o resumo do início de sessão, sem rede, com o payload no stdin |

Imprime o quadro das lanes e o regrava no `LANES.md` da raiz da árvore principal, também quando roda numa lane. O
arquivo fica fora do git: o comando põe `/LANES.md` no `info/exclude` do diretório do git da árvore principal quando a
linha falta, e a guarda nega a edição dele. A fonte é o `git worktree list --porcelain` e o `estado.md` do bloco da
branch de cada worktree dentro de `lane.pasta`; o comando não consulta a rede.

A tabela tem uma linha por lane viva, na ordem das fichas (as FICHA e depois as do prefixo, pelo número), com as
colunas Bloco, Estado, Branch, Worktree (relativa à árvore principal), Portas (`lane <k>: <nome> <porta>`, na ordem do
perfil) e Nota (o motivo do bloco em `blocked`, com o `|` escrito `\|`, ou `—`). Sem lanes, a tabela vira
`Nenhuma lane viva.` O rodapé diz `Lanes: <n> de <limite>. Passagem no <ramo_principal>: v<N>.`, com a versão da cópia
no `origin/<ramo_principal>`, ou `nenhuma` sem ela.

Depois do rodapé, uma linha `Atenção: <linha>.` por atenção, nesta ordem:

- das worktrees dentro de `lane.pasta`, na ordem da pasta: a pasta sumida, quando o nome dela é `<ID>-<slug>`
  (`<ID>: a pasta da lane sumiu; rode harness.py lane fechar <ID> --abandonar`); a worktree sem o bloco da branch
  (`<worktree>: worktree sem bloco`); o `estado.md` inválido, com a recusa da leitura; e o `estado.md` ilegível, fora
  do UTF-8 ou com erro do sistema (`<caminho>: estado.md ilegível: <motivo>`);
- as branches `<tipo>/<ID>-<slug>` sem worktree, na ordem do nome
  (`<branch>: branch sem worktree; recrie a worktree ou apague a branch`);
- os blocos afetados pela versão da passagem no `origin/<ramo_principal>`, na ordem das fichas
  (`<ID>: a lane está na passagem/v<N>, e o <ramo_principal> na v<M>; rode harness.py lane conferir`), fora dos
  blocos em `blocked` e em `closing`; a recusa do cálculo de uma lane sai no lugar da linha dela.

Com `--hook`, é o hook de início de sessão. Lê o JSON do evento no stdin, só quando ele não é um terminal, e acha a
raiz pelo `cwd` dele, quando é uma pasta absoluta que existe, ou pelo diretório do processo. Regrava o `LANES.md` e
imprime, nesta ordem:

- `Contexto compactado: retome pelo estado abaixo.`, só quando o JSON traz `"source": "compact"`;
- `Sessão: lane <ID> (<estado>) em <worktree>`, na lane; `Sessão: árvore principal`;
  `Sessão: lane <worktree> com estado.md inválido`, na lane cujo `estado.md` não se lê, inválido ou ilegível; ou
  `Sessão: worktree <pasta>, fora das lanes`, em outra worktree;
- `Próximo: <ação>`, só na lane, pelo estado do bloco (`/ela-harness:planejar-bloco: termine a spec e o plano`,
  `/ela-harness:executar-bloco`, `/ela-harness:revisar-bloco`, `/ela-harness:finalizar-bloco`, o aguardo do merge, o
  aviso do bloqueio), com `espere o aviso do workflow revisao-do-bloco` em `ready_for_review` ou `reviewing` com a
  revisão em andamento, e, depois da compactação, `; o SDD retoma pelo ledger em .superpowers/sdd/` em `executing`;
- `Lanes: <n> de <limite> · passagem no <ramo_principal>: v<N> · fichas prontas: <n>`, com ` (<u> urgentes)` (ou
  ` (1 urgente)`) depois do número quando alguma pronta tem `Prioridade: urgente`;
- `<ID> <estado> · <ID> <estado>`, os blocos na ordem das fichas, só com lanes;
- `Atenção: <linha>`, uma por atenção.

As fichas prontas são as do `fichas` da árvore principal; quando ele recusa ou não lê um arquivo, `—`. O hook nunca
falha: o que o impede de montar o quadro vira a linha única `Lanes: indisponíveis (<motivo>)`, e ele sai sempre com 0.

Os comandos `bloco` e `lane` regravam o `LANES.md` ao mudar um bloco ou uma lane.

## papel

diz o modelo e o esforço de cada agente do ciclo do bloco

`harness.py papel [<agente>] [--todos] [--json]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<agente>` | não | o agente; sem ele, o --todos |
| `--todos` | não | os oito agentes, na ordem da tabela |
| `--json` | não | a saída em JSON: o objeto do agente ou a lista dos oito |

Diz o modelo e o esforço de cada agente do ciclo do bloco. O `model` e o `effort` vêm do frontmatter do agente, na pasta
`agents/` do plugin, e o `[desenvolvimento.modelos]` do perfil troca os dois.

- `harness.py papel <agente>`: `<agente>: model <m>, effort <e>`, com ` (perfil)` no fim quando o valor vem do perfil.
  A linha do `verificador-achado` termina em `; em bloco sensível, model opus`, e essa subida o perfil não muda.
- `harness.py papel --todos`: uma linha por agente, na ordem da tabela dos agentes.
- `--json`, nos dois: `{"agente": ..., "model": ..., "effort": ..., "origem": "agente"|"perfil"}`, com
  `"model_sensivel": "opus"` no `verificador-achado`, ou a lista, no `--todos`.

O agente fora da lista recusa com `papel: <nome> não é um agente do harness; os agentes são <lista>`, e a chamada sem
agente e sem `--todos`, ou com os dois, com `uso inválido: papel pede um agente ou --todos`, as duas com 1.

## revisao

prepara e registra a revisão do bloco da lane

`harness.py revisao <ação>`

Prepara e registra a revisão do bloco da lane. Roda dentro da lane, com o bloco em `reviewing`; fora de lane, a recusa
é `fora de lane: rode dentro da lane do bloco`, e em outro estado,
`revisao preparar: <ID> está em <estado>; vale só em reviewing`.

- `harness.py revisao preparar [--orientacao "<texto>"]`:
  - a base é o `git merge-base HEAD refs/remotes/origin/<ramo_principal>`, sem fetch, como no diff do PR; sem essa
    ref, ou com o comando falhando, é o `base` do bloco;
  - grava o diff em `<git-dir da worktree>/harness-revisao/<base7>..<head7>.diff`, fora da árvore: a linha
    `commits <base7>..<head7>:`, um `<sha> <assunto>` por commit, o `git diff --stat` e o `git diff -U10` de
    `<base>...HEAD`;
  - as áreas tocadas são as da tabela das áreas da cópia da passagem com algum caminho que casa um arquivo mudado,
    pelos globs das regras geradas, e o bloco é sensível quando algum arquivo mudado casa um padrão de
    `[desenvolvimento.revisao] sensiveis`; nas duas contas, os arquivos sob `<blocos>/` e `<backlog>/`, os do próprio
    bloco e as fichas, não contam como mudados, e o diff fica como está;
  - grava, sem commit, o `<blocos>/<pasta>/gabarito.md`: a parte genérica, os `[desenvolvimento.revisao] itens` do
    perfil, na ordem, e as regras de arquitetura com `revisão` no "Como se confere" e alguma área tocada no "Onde
    vale", em ordem de número, com as áreas e a fonte;
  - a rodada é o número de títulos `## Rodada ` do `revisao.md` mais 1, e os achados do `## Em aberto` dele vão ao
    workflow;
  - grava a marca da revisão em andamento, `<git-dir da worktree>/harness-revisao/em-andamento`, com a hora e a
    rodada, que vale por 4 horas;
  - imprime
    `gabarito.md: <r> regras de <a> áreas e <i> itens do perfil; sensível: sim|não; rodada <n>; em aberto: <e>`
    (no singular com 1) e, na última linha, o JSON dos `args` do workflow: `bloco`, `rodada`, `base`, `head`, `diff`,
    `gabarito`, `spec`, `plano` (os caminhos absolutos), `sensivel`, `consertos_max` (3), `em_aberto` (os objetos com
    `id`, `eixo` (o da tabela da rodada em que o achado apareceu), `severidade`, `arquivo`, `linha`, `problema` e
    `prova`), `orientacao` (o texto com os espaços juntados, ou
    `null`) e `papeis` (o `model` e o `effort` de cada agente do workflow, com o verificador em `opus` no bloco
    sensível).

  Sem a cópia da passagem, a recusa é
  `revisao preparar: sem a cópia da passagem em <passagem>/; rode harness.py importar`; a regra de arquitetura que a
  cópia não confirma sai como `revisao preparar: <motivo>`, uma linha por motivo.
- `harness.py revisao registrar <arquivo>|-`, com o JSON do resultado do workflow no arquivo ou, com `-`, no stdin:
  - confere o esquema do resultado (o `bloco`, o `sensivel`, a `orientacao` e as `rodadas`, cada uma com a `rodada`,
    o `intervalo` e os `achados`), com as rodadas consecutivas a partir da seguinte às do `revisao.md`; o achado novo
    é `R<rodada>-<n>`, e o herdado, só na primeira rodada, é um ID do `## Em aberto`, `CONFIRMED` e com método
    `null`. A recusa é `revisao registrar: resultado inválido: <motivo>`, e o achado do `## Em aberto` que falta,
    `revisao registrar: resultado inválido: falta o achado em aberto <R-ID>`;
  - recusa a linha não vazia do `## Em aberto` que não é um achado na forma, como o item recuado ou numerado, a
    continuação de um item, o texto solto ou um bloco de código, com
    `revisao registrar: ## Em aberto: linha fora da forma: <linha>`, porque a seção é reescrita;
  - o achado pode trazer a chave opcional `absorvidos`, a lista de `{eixo, linha, problema, prova}` do achado do outro
    eixo que a fusão da primeira rodada guardou nele (o `eixo` é `padroes` ou `spec`, e difere do eixo do achado); a
    recusa de um item fora da forma traz o caminho `<achado>.absorvidos[<i>].<chave>`;
  - o achado pode trazer a chave opcional `sem_conserto`, um texto não vazio: o motivo do último conserto, que o
    workflow devolve quando o achado ficou aberto porque a lane não o resolve; fora disso, a recusa é
    `revisao registrar: resultado inválido: <achado>.sem_conserto fora da forma: <valor>`;
  - grava o `<blocos>/<pasta>/revisao.md`: o `# Revisão: <ID>`, o `## Em aberto` e o `## Dispensados` na primeira
    vez; as rodadas da execução logo abaixo do `## Dispensados`, a mais nova em cima, cada uma com a tabela dos
    achados, ou `Sem achados.`, com uma linha por absorvido abaixo da tabela,
    `- <R-ID>, absorvido (<eixo>): <problema> (<arquivo>:<linha do absorvido>)`, e, logo depois dela, uma linha por
    achado com o motivo, `- <R-ID>, sem conserto na lane: <motivo>`, e o placar,
    `Confirmados <c> · Plausíveis <p> · Refutados <r> de <v> verificados · `
    seguido de `Resolvidos <s> de <k> Críticos e Importantes · Menores <m>`, e a primeira com a
    `Orientação do dono: <texto>`, quando há; e o `## Em aberto` reescrito com os Críticos e Importantes confirmados
    que ficaram abertos, um por linha, `- <R-ID> (<severidade>): <problema> (<arquivo>:<linha>)`, com
    ` · prova: ` e o comando entre crases quando há prova;
  - faz o commit `chore(<ID>): revisão, rodada <n>`, ou `rodadas <n> a <m>`, com o `revisao.md` e o `gabarito.md`,
    e apaga a marca da revisão em andamento; com o commit recusado, o `revisao.md` volta ao último commit, e a marca
    fica;
  - imprime `rodadas <n> a <m>: <c> confirmados, <p> plausíveis, <r> refutados; <s> de <k> resolvidos; em aberto: <a>`,
    ou `rodada <n>: ...` com uma rodada só.

  Fora de `reviewing`, a recusa é `revisao registrar: <ID> está em <estado>; vale só em reviewing`.
- `harness.py revisao dispensar <R-ID> "<motivo>"`, só com a palavra do dono, que a guarda confirma:
  - vale em `reviewing`, com o achado no `## Em aberto`; as recusas são
    `revisao dispensar: <R-ID> não está em ## Em aberto`, `revisao dispensar: o motivo não pode ficar vazio` e, fora
    de `reviewing`, `revisao dispensar: <ID> está em <estado>; vale só em reviewing`;
  - tira a linha do `## Em aberto` e a acrescenta ao `## Dispensados`, sem a prova, com
    ` · dispensado por <dono> em <AAAA-MM-DD>: <motivo>`, o motivo com os espaços juntados;
  - faz o commit `chore(<ID>): revisão, dispensa <R-ID>`, só com o `revisao.md`, e imprime
    `<R-ID> dispensado; em aberto: <a>`.

### revisao preparar

grava o gabarito, o diff e a marca da revisão e imprime os args do workflow

`harness.py revisao preparar [--orientacao <texto>]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `--orientacao <texto>` | não | a orientação do dono para os consertos, entre aspas |

### revisao registrar

grava as rodadas do resultado do workflow no revisao.md e faz o commit

`harness.py revisao registrar <<arquivo>|->`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<<arquivo>\|->` | sim | o JSON do resultado; com -, o stdin |

### revisao dispensar

tira o achado do ## Em aberto pela palavra do dono, com o motivo, e faz o commit

`harness.py revisao dispensar <R-ID> <motivo>...`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `<R-ID>` | sim | o achado do ## Em aberto |
| `<motivo>...` | sim | por que o dono dispensa, entre aspas |

## linear

espelha as fichas, só de ida, no projeto do Linear

`harness.py linear <ação>`

`harness.py linear espelhar [--seco]` refaz, a partir do repositório, o espelho só de ida das fichas no Linear: uma
issue por ficha da passagem (`FICHA-NN`) e do backlog do código, no projeto do `[desenvolvimento.linear]` do perfil,
sem duplicar nada. A ficha muda pelo repositório, e o que alguém muda à mão na issue o espelho refaz. Rode-o depois do
merge do PR da passagem, que a última linha do `importar` lembra, e sempre que o aviso de uma transição falhou.

A chave pessoal vem do `LINEAR_API_KEY` do ambiente de quem roda o comando, nunca do repositório. O `projeto` e os dois
rótulos do perfil precisam existir no time, e o comando não os cria. A issue de uma ficha é achada pelo ID no começo do
título ou na primeira linha da descrição, entre as issues do projeto com o `rotulo`.

A ordem, com tudo lido e conferido antes da primeira gravação:

1. lê o time, o projeto, os rótulos, os status e as milestones; as issues do projeto com o rótulo, de página em página;
   e o quadro das fichas do repositório;
2. recusa o ID com duas issues: `duas issues para <ID> no Linear: <a> e <b>; apague uma`, com os identificadores do
   Linear;
3. cria as milestones que faltam, com o prazo do marco quando ele é uma data `AAAA-MM-DD`; a data de uma milestone que
   já existe não muda;
4. cria cada issue que falta e acerta as outras: o título `<ID>: <slug>`, a descrição, com a primeira linha
   `Espelho de <ID> (<caminho>); muda pelo repositório, não aqui.` e depois o texto da ficha, os rótulos, a milestone,
   o status e o responsável;
5. cria as relações `blocked by` do Depende, depois de todas as issues existirem, e apaga as que saíram do Depende; a
   relação com a ficha citada que ficou `fora da forma`, e já tem issue, fica; a PEND do Depende fica só na descrição;
6. manda para o status `saiu` a issue de uma ficha da passagem que a cópia não tem mais.

O que o espelho faz em cada campo:

- **Status:** só avança, na ordem `espera`, `pronta`, `andamento`, `revisao`, `fechada`, e nunca recua: a ficha que ele
  vê `pronta` e o Linear mostra `andamento` pode estar numa lane de outra máquina, e o recuo vem só do aviso da
  transição que o causa. Um status do Linear que não é um desses vale como abaixo de `espera`. O `saiu` vale sempre,
  menos para a issue que já saiu. No avanço para `andamento`, `revisao` ou `fechada`, o comentário é
  `estado acertado pelo espelho: <estado> (<atualizado_em>)`, com o estado e a hora do bloco, porque o aviso daquela
  transição se perdeu; de `espera` a `pronta` não há comentário.
- **Rótulos:** põe o `rotulo_bloqueio` enquanto o bloco está em `blocked`, com o comentário `bloqueado: <motivo>`, e o
  tira depois; um rótulo posto à mão no Linear fica. Com o bloco em `blocked`, o status é o do `estado_anterior`.
- **Descrição:** a descrição do repositório substitui a do Linear só quando as duas diferem depois de apagar o que o
  Linear re-renderiza (o `* ` do item, a linha em branco depois do título, o `<>` e o percent-encoding do alvo do link e
  a quebra do fim). O comentário é `mudou na passagem/v<N>: <partes>`, ou `mudou no backlog do código: <partes>`, com os
  campos da ficha cujo texto mudou, na ordem do molde, e sem a parte quando só o texto de fora dos campos mudou.
- **Milestone:** a do `Marco` da ficha, achada pelo nome. A ficha que perde o `Marco` mantém a milestone que a issue
  tem: o espelho não tira milestone, como não muda a data de uma que já existe.
- **Responsável:** só preenche o vazio, com o usuário do e-mail do `git config user.email` da raiz, e só na ficha cuja
  lane está nesta máquina; sem usuário com esse e-mail, a issue fica sem responsável.
- **A ficha que saiu:** a issue com o `rotulo` e um ID `FICHA-NN` que a cópia da passagem não tem vai a `saiu`, com o
  comentário `saiu da passagem/v<N>`. A issue de uma ficha do código sem arquivo dá a linha
  `<ID>: no Linear e fora do repositório; nada muda`.

A saída tem uma linha por issue que mudou, `<ID>: <partes>`, com as partes separadas por `; ` e nesta ordem:
`criada (<status>[, <milestone>])`, `título`, `descrição`, `rótulo <nome> +`, `rótulo <nome> -`, `milestone <nome>`,
`status <de> → <para>`, `responsável <e-mail>`, `blocked by +<ID>` e `blocked by -<ID>`. Os status saem com o nome do
Linear, e a ficha que saiu traz `status <de> → <para> (saiu da passagem/v<N>)`. A milestone criada dá a linha
`milestone <nome>: criada`; a ficha que não vai ao Linear (`fora da forma`, ou só numa lane) dá
`<ID>: não espelha (<situação>)`. O resumo é `linear: <c> criadas, <a> acertadas, <s> sem mudança`, e as linhas
`não espelha` e `no Linear e fora do repositório` ficam fora da conta.

- **`--seco`:** lê o Linear e o repositório e imprime as mesmas linhas e o mesmo resumo, sem gravar nada.
- **Recusas, com saída 1:** `sem [desenvolvimento.linear] no perfil`, olhada antes da chave;
  `sem LINEAR_API_KEY no ambiente`; `duas issues para <ID> no Linear: <a> e <b>; apague uma`; e `linear: <motivo>` para
  a chamada que não deu certo (a mensagem do Linear, `HTTP <código>`, `tempo esgotado`, `sem conexão (<motivo>)` ou
  `resposta ilegível`) e para o que o time não tem (`time <time> não existe no Linear`,
  `projeto <nome> não existe no time <time>`, `rótulo <nome> não existe no time <time>` e
  `status <nome> não existe no time <time>`). O redirecionamento que a API devolva não é seguido, para que a chave não
  vá a outro endereço, e dá `linear: HTTP <código>`.
- **A falha no meio da gravação:** a chamada que falha depois da primeira gravação que deu certo sai com 1 e mostra,
  antes do `linear: <motivo>` que fecha a saída, as linhas do que já gravou, no formato de sempre: as milestones
  criadas e, de cada ficha, o que se gravou nela, sem o resumo e sem as linhas que só aparecem na saída. A falha antes
  da primeira gravação (o contexto, as issues, o status que o time não tem) mostra só o `linear: <motivo>`, e a
  recusa das duas issues, só ela, sem o `linear: `. Rodar de novo faz o que faltou, sem duplicar issue, relação nem
  milestone, com uma exceção: se a gravação parar entre a de uma issue, criada ou acertada, e a do comentário dela,
  esse comentário se perde, porque a rodada seguinte já vê a issue sem mudança.

O aviso da transição (spec 6d-repositorio, §9.5) é de outro comando: com a `[desenvolvimento.linear]` no perfil, cada
comando que muda o estado de uma ficha com um commit (`lane abrir`, os `bloco` `planejado`, `executando`, `executado`,
`revisando`, `revisado`, `corrigir`, `finalizar`, `bloquear`, `desbloquear` e `replanejar`, o `lane conferir` que
trava um bloco, o `retorno abrir` de decisão e o `lane fechar`, com ou sem `--abandonar`) avisa o Linear depois de
imprimir as linhas dele. O aviso, com 10 s no total:

- põe a issue da ficha no status do estado novo, e este pode recuar (`bloco corrigir`, `bloco replanejar`,
  `lane fechar --abandonar`); põe ou tira o `rotulo_bloqueio`, e grava como responsável o usuário do e-mail do
  `git config user.email` da árvore, quando ele existe no Linear, senão o responsável não muda;
- cria a issue, pelo caminho do espelho, quando a ficha ainda não tem;
- grava o comentário `<ID> · <de> → <para> · <e-mail> · <atualizado_em> · <ramo>@<commit curto>`; o bloco em `blocked`
  acrescenta ` · motivo: <motivo>`, e o link do PR, quando há, vem por último, depois de ` · `; sem o e-mail, vale
  `sem e-mail`. No `lane fechar` o ramo e o commit são os da árvore principal e a hora é a do comando; o `--abandonar`
  diz `<estado> → pronta (lane abandonada)`; o `finalizar` que só retoma diz `closing → closing`, só quando traz o
  link do PR, e o `retorno abrir` de `fato` não avisa, porque o bloco segue.

O aviso nunca muda as linhas nem o código de saída do comando. Se não vai, uma linha a mais:
`linear: aviso não enviado (<motivo>); rode harness.py linear espelhar`, ou, sem a chave no ambiente,
`linear: sem LINEAR_API_KEY no ambiente; aviso não enviado`. Sem a `[desenvolvimento.linear]`, o comando não avisa e não
diz nada.

### linear espelhar

refaz o espelho das fichas no Linear, sem duplicar nada

`harness.py linear espelhar [--seco]`

| Argumento ou opção | Obrigatório | O que é |
|---|---|---|
| `--seco` | não | lê o Linear e imprime as mesmas linhas e o mesmo resumo, sem gravar nada |

## Skills e agentes

| Nome | Tipo | Quando usar | Argumento | O que pode usar | Modelo |
|---|---|---|---|---|---|
| `assessor` | skill | Compara opções de tecnologia, fornecedor ou abordagem numa decisão do planejamento, com critérios, trade-offs, recomendação e estudo gravado; a decisão é do usuário. | `[tema da decisão]` | `harness.py perfil`, `harness.py estudos`, `harness.py estado`, `date` | o da sessão |
| `contexto-leitor` | agente | Completes the Context Packet of a block, one domain of the handover copy per dispatch. Returns facts with file:line. Does not edit. | — | `Read`, `Grep`, `Glob` | sonnet |
| `corretor-tardio` | agente | Fresh-eyes fixer for the late rounds, SDD rounds 4 and 5 and the third fix of a block review. Dispatched when earlier fixes did not settle a finding. Edits files and commits. | — | as da sessão | opus |
| `executar-bloco` | skill | Executa o plano do bloco da lane pelo subagent-driven-development, com os agentes do harness, até o bloco pronto para revisão. Use só dentro da lane de um bloco em ready_for_execution ou executing, quando o bloco status disser /ela-harness:executar-bloco, ou com pr quando o PR do bloco voltou com pedido de mudança. | `[correção: <orientação> \| pr]` | `harness.py bloco` | o da sessão |
| `finalizar-bloco` | skill | Finaliza o bloco da lane: confere o que a spec promete, guia os itens manuais e abre o PR pelo harness. Use só dentro da lane de um bloco em ready_for_closure, ou quando o bloco status disser /ela-harness:finalizar-bloco. | `[resumo do PR]` | `harness.py bloco` | o da sessão |
| `gate-fase` | skill | Fecha uma camada do planejamento: roda o checklist do gate (script e revisor), apresenta o veredito e registra a aprovação dada pelo usuário. | `[gate, como no STATUS.md]` | `harness.py perfil`, `harness.py gate`, `harness.py passagem` | o da sessão |
| `gerar-modulos` | skill | Gera em rascunho as entidades, as telas e os módulos da camada a partir do escopo aprovado, com o usuário só nas dúvidas, quando o harness.py proximo a recomenda; cada módulo segue depois para o refinar-documento. | — | `harness.py perfil` | o da sessão |
| `implementador-integracao` | agente | Implements one plan task that spans several files or needs a pattern decision, and makes the first and second fix of a block review. Dispatched by the SDD loop and by the review loop. Edits files and commits. | — | as da sessão | sonnet |
| `implementador-mecanico` | agente | Implements one plan task whose code is already written in the plan, in one or two files. Dispatched by the SDD loop for mechanical tasks. Edits files and commits. | — | as da sessão | sonnet |
| `iniciar` | skill | Inicia um projeto de planejamento ou um repositório de código a partir do modelo do plugin: o modelo da trilha, o lançador, os githooks e os plugins da trilha. Use com /ela-harness:iniciar &lt;trilha> [nome do projeto]. | `<trilha> [nome do projeto]` | `harness.py "`, `harness.py iniciar` | o da sessão |
| `pesquisador-fatos` | agente | Levanta fatos com fonte que um pacote de documentos do planejamento precisa, nas fontes locais e, para sistemas externos, na web. Só leitura. Use apenas quando a skill refinar-documento mandar, no passo 0. | — | `Read`, `Grep`, `Glob`, `WebSearch`, `WebFetch` | sonnet |
| `pesquisador-opcoes` | agente | Pesquisa fatos com fonte sobre as opções de uma decisão de planejamento, na web e nas fontes locais. Só leitura. Use apenas quando a skill assessor mandar. | — | `Read`, `Grep`, `Glob`, `WebSearch`, `WebFetch` | sonnet |
| `planejar-bloco` | skill | Planeja um bloco do código a partir de uma ficha ou de um pedido em texto livre, até o plano pronto para execução, com a spec aprovada pelo dono. Use quando o dono pedir para planejar uma ficha ou corrigir um defeito, ou quando o bloco status disser /ela-harness:planejar-bloco. | `[<ficha> \| texto livre]` | `harness.py bloco` | o da sessão |
| `re-revisor` | agente | Reviews only the fix interval after a review round, in the SDD and in the block review. Checks that each fix resolves its finding. Does not edit. | — | `Read`, `Grep`, `Glob`, `Bash` | sonnet |
| `refinar-documento` | skill | Refina um documento de planejamento a partir do rascunho e do molde, em entrevista por rodadas, até a aprovação do usuário. | `[caminho do documento na pasta do planejamento]` | `harness.py perfil` | o da sessão |
| `revisar-bloco` | skill | Revisa o bloco da lane com o workflow revisao-do-bloco e registra o resultado no revisao.md, até o bloco pronto para finalizar. Use só dentro da lane de um bloco em ready_for_review ou reviewing, ou quando o bloco status disser /ela-harness:revisar-bloco. | `[orientação do dono]` | `harness.py bloco` | o da sessão |
| `revisor-bloco` | agente | Lens 1 of the block review. Reviews the block diff along one axis (standards, or spec and defects) and returns findings in the given schema. Does not edit. | — | `Read`, `Grep`, `Glob`, `Bash` | opus |
| `revisor-gate` | agente | Confere os itens de revisor do checklist de um gate de fase, olhando os documentos da camada juntos. Só leitura. Use apenas quando a skill gate-fase mandar. | — | `Read`, `Grep`, `Glob` | sonnet |
| `revisor-requisitos` | agente | Revisa um documento de planejamento, ou os documentos de um pacote, em busca de lacunas. Só leitura. Use apenas quando a skill refinar-documento mandar, no passo 5. | — | `Read`, `Grep`, `Glob` | sonnet |
| `revisor-task` | agente | Reviews one SDD task for spec compliance and code quality, using the SDD prompt template. Dispatched after each task. Does not edit. | — | `Read`, `Grep`, `Glob`, `Bash` | sonnet |
| `verificador-achado` | agente | Lens 2 of the block review. Verifies one finding per dispatch, by running its proof or by reading the code. Dispatched once per finding. Does not edit. | — | `Read`, `Grep`, `Glob`, `Bash` | sonnet |

## Mapa do núcleo

| Arquivo | O que é |
|---|---|
| `nucleo/comum/ambiente.py` | O que a máquina precisa para o harness rodar (spec 4a, §8.3): o Python com leitor de TOML, o pre-commit ativo e a árvore em que a sessão abriu. |
| `nucleo/comum/caminho.py` | Caminho de import do núcleo: põe as três pastas do núcleo no `sys.path`, na ordem comum, planejamento e desenvolvimento. |
| `nucleo/comum/campos.py` | Leitor de Markdown comum às duas trilhas (spec 6c, §7.5 e §10): as linhas fora dos blocos de código, as seções, os itens de um campo e os links. |
| `nucleo/comum/ci.py` | O texto do `.github/workflows/harness.yml` de cada projeto (spec do CI dos projetos, §4). |
| `nucleo/comum/comum.py` | Utilitários do harness: raiz do projeto, leitura e escrita de texto, datas, motivos de erro, listas em prosa e caminhos com padrões. |
| `nucleo/comum/escrita.py` | Alvos de escrita de um comando de Bash, para a guarda (spec 3b, §6.2). |
| `nucleo/comum/gancho.py` | Entrada dos hooks do plugin (spec do porte 1, §7.1): calada sem perfil; com ele, refaz o link do núcleo e roda o comando da trilha para o evento. |
| `nucleo/comum/gerador.py` | Arquivos gerados do repositório de código (spec 6d-gerador, §5 e §7): os textos, a partir da passagem e do perfil. |
| `nucleo/comum/guarda.py` | Guarda dos hooks do Claude Code (spec 3b, §6, §7.1, §9 e §12): o PreToolUse, a prova de mensagem do UserPromptSubmit e o Stop. |
| `nucleo/comum/harness.py` | Ponto de entrada do harness: monta os comandos pela trilha do perfil e despacha cada um para o módulo de uma das três pastas do núcleo. |
| `nucleo/comum/invariantes.py` | Invariantes conferidas pelo git (spec 3b, §8; 6c, §6.6, §8.5, §11.3; 6d-gerador, §9): planejamento, cópia, gerados, harness e segredos. |
| `nucleo/comum/manifesto.py` | Manifesto da passagem (spec 6b, §6.4 e §6.5): o formato, o trecho que define cada ID e o hash da lista de arquivos. |
| `nucleo/comum/perfil_comum.py` | Parte comum do perfil, às duas trilhas: `[projeto]`, `[guarda]` e a trilha do perfil. |
| `nucleo/comum/referencia.py` | Referência do harness gerada pelo núcleo (spec 4c, §7): os comandos pelo parser, as skills e os agentes pelo frontmatter e o mapa do núcleo. |
| `nucleo/comum/regras.py` | Regras de arquitetura (spec 6d-gerador, §6): a linha da regra, o casamento do "Onde vale" com as áreas e as regras da passagem. |
| `nucleo/comum/segredos.py` | Padrões de segredo: os do núcleo, com nome fixo, e a busca deles num texto, para a guarda e o `sem-segredos`. |
| `nucleo/desenvolvimento/aceitacao.py` | Aceitação do bloco (spec 6c, §12): a seção da spec, o `aceitacao.md`, a conferência das provas por HTTP e a anotação dos itens manuais. |
| `nucleo/desenvolvimento/bloco.py` | Bloco do desenvolvimento (spec 6c, §9.2 e §9.4): o formato do `estado.md`, as lanes vivas e os blocos do ramo principal. |
| `nucleo/desenvolvimento/contexto.py` | Context Packet (spec 6c, §10): o pacote de leitura de uma ficha, montado da ficha e da cópia da passagem da árvore. |
| `nucleo/desenvolvimento/fichas.py` | Fichas do desenvolvimento (spec 6c, §9.1 a §9.3): as da passagem e as do backlog do código, os campos, os IDs citados, a forma e o estado. |
| `nucleo/desenvolvimento/importacao.py` | Importação da passagem no repositório de código (spec 6c, §8): a tag conferida, a cópia, o relatório e o PR próprio, ou a cópia direta na montagem. |
| `nucleo/desenvolvimento/iniciar.py` | O `iniciar <trilha>` de um projeto pelo plugin e a conferência do repositório de código (spec do porte 1, §7.5 e §7.6; spec 6d-repositorio, §7). |
| `nucleo/desenvolvimento/instalacao_ci.py` | A instalação do CI (spec `ci-dos-projetos`, §6.2): os comandos de `[desenvolvimento.ci] instalar`, um por um. |
| `nucleo/desenvolvimento/lane.py` | Lanes dos blocos (spec 6c, §15): o `abrir` pelo portão, o `conferir` contra o origin e o `fechar` com o PR mesclado. |
| `nucleo/desenvolvimento/lanes.py` | Quadro das lanes (spec 6c, §17): o `LANES.md` da árvore principal, fora do git, e o resumo do início de sessão, sem rede. |
| `nucleo/desenvolvimento/linear.py` | O espelho só de ida das fichas no Linear, com a chave do ambiente (spec 6d-repositorio, §9). |
| `nucleo/desenvolvimento/papeis.py` | Os oito agentes do ciclo do bloco: o frontmatter de cada um, as trocas do perfil por cima e o comando `papel`. |
| `nucleo/desenvolvimento/perfil_desenvolvimento.py` | Perfil de desenvolvimento: a tabela `[desenvolvimento]` do repositório de código, sobre a parte comum do perfil. |
| `nucleo/desenvolvimento/prepush.py` | Pre-push do repositório de código (spec 6c, §13): recusa o push direto no ramo principal e a remoção dele, e deixa passar a criação, a da montagem. |
| `nucleo/desenvolvimento/retorno.py` | Retorno do código ao planejamento (spec 6c, §16): a issue com o ID contradito e, na lane, o registro no `estado.md`. |
| `nucleo/desenvolvimento/revisao.py` | Revisão do bloco (spec 6d-bloco, §7): o gabarito da lente 1 e os comandos `revisao preparar`, `registrar` e `dispensar`. |
| `nucleo/desenvolvimento/transicoes.py` | Comandos do bloco (spec 6c, §14): cada um confere a transição e o passo, grava o `estado.md`, faz o commit e regrava o `LANES.md`. |
| `nucleo/desenvolvimento/verificacao.py` | Verificações do perfil (spec 6c, §11.1 e §11.2): os mudados, a seleção pelo momento, a execução com tempo limite e a marca da última aprovada. |
| `nucleo/planejamento/anotacao.py` | Via curta do UserPromptSubmit do planejamento (spec da onda 1, §5.1): grava a resposta da aprovação sem carregar o harness.py. |
| `nucleo/planejamento/backlog.py` | Backlog do planejamento: IDs e contagem das pendências (spec 5.2 e 6.4), pendências e artefatos do gate (spec 2a, §6.1). |
| `nucleo/planejamento/blocos.py` | Textos tirados do perfil: o resumo do comando `perfil` e o bloco "Este projeto" de cada skill (spec 2a, §5.3 e §5.5). |
| `nucleo/planejamento/checar.py` | Checagem determinística de um documento de planejamento contra o molde: o passo 4 do ciclo (spec 6.2). |
| `nucleo/planejamento/citacoes.py` | As verificações das citações de um documento da camada: a citação por número de linha e o item de Aceite que mudou. |
| `nucleo/planejamento/der.py` | O DER físico em tabelas Markdown, o gerador do DDL e do erDiagram, o rastreio contra a camada 2 e o manifesto do Workbench. |
| `nucleo/planejamento/diagramas.py` | As checagens dos diagramas da camada, em Mermaid, C4 e `.drawio`, sem rodar o Mermaid. |
| `nucleo/planejamento/dossie.py` | Dossiê de um documento ou de um pacote (spec 4b, §7): as fontes de cada documento, achadas por script, sem LLM e sem rede. |
| `nucleo/planejamento/estado.py` | Leitura, validação e formatação do STATUS.md (formato fixo, spec 5.1) e bloco do hook SessionStart (spec 6.1). |
| `nucleo/planejamento/estudos.py` | Estudos do assessor (spec da fase 2b, §8.2): lê o cabeçalho de cada estudo da pasta do perfil e diz em que situação está a decisão. |
| `nucleo/planejamento/fechamento.py` | Fechamento do ciclo depois do commit (spec 4a, §7): confere a versão marcada no HEAD e fecha o STATUS.md numa escrita só. |
| `nucleo/planejamento/gate.py` | Gate de fase (spec 2a, §6.1): pré-condição e itens de script e de leitor frio do checklist, com as verificações do núcleo. |
| `nucleo/planejamento/gerado_planejamento.py` | Texto gerado do harness de planejamento (spec do porte 1, §9.1): as partes do `CLAUDE.md` que são do harness, com os valores do perfil. |
| `nucleo/planejamento/legenda.py` | Legenda das siglas e dos tipos de ID (spec 6b, §5), gerada a partir dos documentos e conferida no commit. |
| `nucleo/planejamento/lote.py` | O lote de revisão: a ordem dos documentos e o `estado lote`, que o abre só com o que o destino da pendência cita. |
| `nucleo/planejamento/migrar.py` | As migrações do projeto entre versões do harness: a leitura delas, as correções de forma e o comando `migrar`. |
| `nucleo/planejamento/passagem.py` | Passagem do planejamento ao código (spec 6b, §6 a §10): exportação, áreas do código, `areas-cobertas`, leitor frio e publicação. |
| `nucleo/planejamento/passo.py` | Fechar um passo do ciclo (spec da fase 3a, §8): grava o STATUS.md e, nos passos 5 e 7, o status do artefato. |
| `nucleo/planejamento/perfil.py` | Perfil do projeto (spec da fase 2a, §5): tudo o que é do projeto, lido de .claude/perfil.toml e validado. |
| `nucleo/planejamento/proximo.py` | O próximo passo do planejamento (spec 4a, §6), calculado pelo STATUS, pelos artefatos, pelas pendências, pelos links e pelo ambiente. |
| `nucleo/planejamento/rastreio.py` | Rastreio entre os documentos do planejamento (spec 4b, §5 e §11): quem cita cada documento, termo ou ID, e com que status. |
| `nucleo/planejamento/registro.py` | Registro no ato (spec 4b, §10, e 4a, §9): Ruling, pendência e relato acrescentados no formato de cada arquivo, sem tirar linha. |
| `nucleo/planejamento/resumo.py` | O resumo das mudanças dos documentos em refino: o esqueleto contra o HEAD ou a cópia marcada e o diff por camada. |
| `nucleo/planejamento/sessao.py` | Início da sessão (spec 4a, §8.1 e §18): o JSON do hook SessionStart, com o aviso ao usuário e o contexto do modelo. |
| `nucleo/planejamento/versao.py` | Hash da versão enviada para aprovação (passo 6 do ciclo): marcar, conferir e limpar. |
| `nucleo/comum/saida.md` | os moldes do que o usuário lê no chat; o passo que produz cada saída lê este arquivo na hora de escrever |
| `aprovacao/` | as cópias das versões marcadas no passo 6, o manifesto do pacote, o histórico e a resposta; fora do git |
| `dossie/` | o dossiê do documento ou do pacote, refeito a cada `harness.py dossie`; fora do git |
| `nucleo/planejamento/ferramentas/` | o que roda fora do `harness.py`: o validador Mermaid em Node, na CI e local, e o DDL nos bancos, só na CI |
