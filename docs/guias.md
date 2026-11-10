# Guias

Um guia por tarefa: quando usar, os passos que você faz e vê e o que fazer se der errado. O que o modelo faz fica nas
skills, citadas pelo caminho. `harness.py` abrevia `python3 .claude/harness/harness.py`, rodado da raiz.

## Refinar um documento

**Quando:** o `harness.py proximo` recomenda `/ela-harness:refinar-documento <caminho>`. Primeiro uso: [tutorial](tutorial.md). O
modelo segue [`skills/refinar-documento/SKILL.md`](../skills/refinar-documento/SKILL.md).

1. Chame `/ela-harness:refinar-documento <caminho>`. Sem argumento, a skill retoma do `Passo` gravado o documento ou o pacote do
   `STATUS.md`, numa sessão nova inclusive; sem nenhum, pergunta se abre o recomendado.
2. Após três rodadas com decisões ainda abertas, o modelo lista o que resta e oferece escrevê-lo com `[A CONFIRMAR]`.
3. Para escrever sem a pesquisa, diga "sem pesquisa" ao aviso do despacho, ou escolha "Escrever com a seção marcada" no
   passo 3: a seção sai com `[A CONFIRMAR: pesquisa pendente]`, e a mensagem de aprovação a cita.
4. No passo 6, responda `aprovado` ou o que mudar: a mudança refaz a checagem e a revisão e mostra o `versao diff`.

**Se der errado:**
- `Versao-aprovacao ... está marcada para <documento>`: no passo 7, sai o commit; no 6, aprove ou autorize o `versao limpar`.
- `<documento> é da camada <fase>; aprove antes o <gate>`: [feche a camada atual](#fechar-uma-camada).
- `molde não encontrado: <caminho>`: confira os moldes e o `mapa` do perfil ([Mudar o perfil](#mudar-o-perfil)).

## Gerar os módulos

**Quando:** o `harness.py proximo` recomenda `/ela-harness:gerar-modulos`: a fase pede módulos e ainda não tem nenhum. O
modelo segue [`skills/gerar-modulos/SKILL.md`](../skills/gerar-modulos/SKILL.md).

1. Chame `/ela-harness:gerar-modulos`. O modelo lista as entidades, as telas e os requisitos, cada um com a fonte.
2. Responda numa rodada à proposta de módulos, às entidades como modelo lógico e às dúvidas: cada uma vira Ruling ou pendência.
3. O modelo escreve as entidades, as telas e, por último, os módulos, em rascunho e sem commit, e roda o `harness.py checar`.
4. O relato traz os arquivos, os `[A CONFIRMAR]` e o pacote seguinte; siga em [Refinar um pacote](#refinar-um-pacote).

**Se der errado:**
- `<gate> sem item ligados; a skill não se aplica à fase <fase>`: a fase não pede módulos; siga o `harness.py proximo`.
- A sessão caiu no meio: chame a skill de novo; ela lê o Ruling da proposta e grava só o que falta.

## Refinar um pacote

**Quando:** o `harness.py proximo` recomenda um módulo que cria ou compõe entidades e telas em rascunho. O detalhe está
em [`references/pacote.md`](../skills/refinar-documento/references/pacote.md).

1. Chame `/ela-harness:refinar-documento <módulo>`. No passo 0, o modelo propõe até 6 documentos pelos links do módulo e roda
   `harness.py estado set Pacote "<caminhos>"`: você vê `Pacote = <caminhos>` e `Documento = <primeiro>`, se ele muda.
2. Módulo aprovado fica como fonte; com pendência aberta nele, a skill pergunta se é a revisão do módulo ou o pacote.
3. No passo 1, responda "A composição do pacote confere?" e "O resumo e os mapas conferem?". A lista corrigida vira um
   `estado set Pacote` novo, aceito até a versão ser marcada.
4. As rodadas, a checagem, o revisor e a mensagem de aprovação cobrem o pacote inteiro.
5. No passo 6, responda `aprovado`, `mudar <documento>: <o quê>` ou `tirar <documento> do pacote`. O commit, um só,
   sai sem pedido; o `harness.py fechar` confere cada documento no HEAD e tira o `Pacote`.

**Se der errado:**
- Mais de 6 documentos: o modelo propõe dois pacotes, como as entidades num e as telas no outro.
- `rode versao limpar antes de trocar o Pacote`: use `tirar <documento> do pacote` ou autorize o `versao limpar`.
- `aprovo A e B` não vale, porque não há aprovação parcial: responda `aprovado`, `mudar` ou `tirar`.

## Revisar um documento aprovado

**Quando:** uma decisão nova muda o que um documento `aprovado` diz, ou uma pendência aberta tem destino nele. O detalhe
está em [`references/modo-revisao.md`](../skills/refinar-documento/references/modo-revisao.md).

1. Veja quem cita o que mudou: `harness.py afetados <ID>`, `<prefixo>-NN` (com os IDs que a pendência cita) ou
   `"<termo>"`. Os documentos vêm pelo status, `aprovado` primeiro, e depois os Rulings e as pendências abertas.
2. Sem pendência? Peça uma ([Registrar no ato](#registrar-no-ato)); o `harness.py proximo --verbose` lista as revisões.
3. Chame `/ela-harness:refinar-documento <documento>`: no `aprovado`, o modo revisão parte da pendência ou do seu pedido.
4. Só há entrevista se a pendência deixa decisão aberta; só os trechos afetados mudam; você confirma só as marcas novas.
5. No passo 6, você vê o `git diff` contra a versão commitada; no 7, a pendência fecha e o documento volta a `aprovado`.

**Se der errado:**
- `Afetados por <alvo>: 0 linhas`: ninguém cita o alvo assim; tente o ID, a pendência ou outro termo.
- Entidades e telas de um módulo aprovado, ou uma pendência com destino em vários aprovados: um pacote; veja [Refinar um pacote](#refinar-um-pacote).

## Produzir a camada 3

**Quando:** a camada 3 começa. O detalhe está em [`references/camada-3.md`](../skills/refinar-documento/references/camada-3.md).

1. Um documento por vez, na ordem dos `obrigatorios` da fase no perfil; o `harness.py proximo` recomenda nessa ordem.
   Depois dos diagramas e do índice vêm os contratos externos, a entrega e operação e, por último, as fichas.
2. No DER físico, as tabelas seguem o formato do reference, e a Origem de cada coluna diz de que atributo da camada 2
   ela veio. Depois de cada mudança nas tabelas, o modelo roda `harness.py der gerar`, que grava o SQL e o diagrama.
3. No passo 4, o passo do Workbench é seu: importe o `schema.mysql.sql`, salve os prints em PNG e exporte o
   `workbench.sql`. O modelo roda `harness.py der workbench`, que amarra os prints a essa versão do SQL.
4. No passo 4, o modelo roda o validador Mermaid, se houver Node. Na nuvem, ele escreve o `.drawio`: ajuste e grave no
   draw.io web, pelo Safari, ou no VS Code, e a cada mudança exporte o `<nome>.drawio.svg` na mesma pasta, com "Include
   a copy of my diagram" ("Draw.io: Export To..." em `.svg` no VS Code; o "Convert To..." apaga o `.drawio`).
5. Nos ADRs, cada decisão leva Status, Data, um requisito na Justificativa e as regras de arquitetura, `RA-NN` ou
   `nenhuma:` com o motivo; cada item mínimo aponta uma decisão.
6. A CI do projeto, o check `harness`, só confere as invariantes; o Mermaid se valida no passo 4.

**Se der errado:**
- `prints do Workbench feitos de outra versão do DDL`: as tabelas mudaram depois dos prints; refaça o Workbench.
- `"<termo>" sem pendência na linha`: registre a pendência, com destino num teste antes da virada, e cite-a na linha.
- `entidade <NOME>: atributo sem coluna`: crie a coluna, ou registre o atributo em "Não persistido", com o motivo.
- `<arquivo>.svg de outra versão do <arquivo>`: o `.drawio` mudou depois da exportação; exporte o `.drawio.svg` de novo.

## Fechar uma camada

**Quando:** o `harness.py proximo` recomenda `/ela-harness:gate-fase <gate>`, porque a fila da fase acabou. A linha `Pré-checagem`
abaixo dele mostra os FAIL do gate antes de chamá-lo. O detalhe está em [`skills/gate-fase/SKILL.md`](../skills/gate-fase/SKILL.md); o checklist, no perfil.

1. Chame `/ela-harness:gate-fase <gate>`; sem argumento, vale o gate da `Fase` atual.
2. Você vê o `harness.py gate <gate> --verbose`: cada item de script com `PASS`, `FAIL` ou `INFO`, e a `Assinatura:`.
3. Com `FAIL` de script, a skill para antes do revisor: corrija, ou dispense o item. Senão, o `revisor-gate` lê a fase
   em segundo plano, ou vale o veredito anterior, com a mesma assinatura na mesma conversa.
4. Você vê o checklist, por tipo (script, revisor, leitor frio e humano), e o veredito: `PASS`, `CONCERNS` ou `FAIL`.
5. Responda `aprovado` ou, para cada item que bloqueia, `dispenso o N: motivo`; sem a dispensa, a aprovação não vale.
6. O modelo grava `aprovado em <AAAA-MM-DD>` no gate, avança a `Fase` (no último, fica), registra nas decisões e commita.

**Se der errado:**
- Documento reprovado: a `gate-fase` não edita; corrija pela `/ela-harness:refinar-documento <documento>` e chame o gate de novo.
- `<gate> fecha a fase <fase>, e a Fase atual é <fase>`: chame o gate da `Fase` atual.
- `<gate> sem checklist no perfil`: escreva os itens em `[gates.<gate>]` ([Mudar o perfil](#mudar-o-perfil)).

## Rodar o leitor frio no gate

**Quando:** o `harness.py gate <gate>` dá `<n> leitor-frio: FAIL`; a `gate-fase` roda o teste no passo 1.

1. O modelo escreve o gabarito, `<caminhos.leitor_frio>/<gate>-<AAAA-MM-DD>.md`, pelas perguntas do perfil; confirme-o.
2. O `harness.py passagem leitor <gabarito>` exporta o HEAD para uma pasta temporária e roda nela um `claude -p` preso
   a ela, sem shell, sem `CLAUDE.md` e sem memória; as respostas entram no Resultado do gabarito.
3. O modelo propõe `certa`, `errada` ou `não achou` por item; confirme ou corrija. Cada erro é lacuna: pendência no
   planejamento, ou correção do contrato de passagem numa branch do harness.
4. O item passa só com todo item `certa` e a exportação do HEAD igual à do Resultado, e não se dispensa.

## Publicar a passagem

**Quando:** depois do último gate, ou de uma revisão aprovada, e só a seu pedido, na árvore principal e limpa.

1. O `harness.py passagem publicar` commita o manifesto, cria a tag `passagem/vN` na máquina e diz o que o envio fará.
2. Confirme o envio; o `harness.py passagem publicar --enviar vN` empurra as tags que faltam no origin e fecha
   as issues `retorno` resolvidas, ou só as comenta quando outra pendência aberta as cita. Rodar de novo é seguro.
3. `nada a publicar: igual a passagem/vN` quer dizer que a última passagem está em dia.
4. As outras recusas dizem o que falta: commit, documento em edição, artefato não aprovado ou aviso da exportação.

## Decidir entre opções

**Quando:** uma decisão depende de comparar tecnologias, fornecedores ou abordagens, e a entrevista sugere
`/ela-harness:assessor <tema>`. O detalhe está em [`skills/assessor/SKILL.md`](../skills/assessor/SKILL.md).

1. Chame `/ela-harness:assessor <tema>`. Já há estudo do tema? A skill diz onde a decisão está, ou pergunta se é revisão.
2. Corrija o enquadramento: a pergunta de decisão, os critérios com a origem, de 2 a 5 opções e o que foi inferido.
3. A pesquisa roda em segundo plano, por até 15 minutos; se demorar, diga `seguir`, e o que falta sai `sem fonte`.
4. Você vê o parecer, com as opções em letras, a recomendação e o estudo, gravado na pasta `caminhos.estudos`. Responda
   com a letra ou `adiar`. O commit do estudo sai sem pedido.
5. O registro é do passo 7 do próximo `/ela-harness:refinar-documento`: Ruling no arquivo de decisões, ou ADR no de ADRs
   (`caminhos.adrs`), se a camada dele já começou. O estudo passa a `registrada em <arquivo>`.

**Se der errado:**
- `estudos com decisão por registrar`, no `harness.py proximo`: o registro sai no passo 7 do próximo documento.
- `<arquivo>: ilegível (<motivo>)` no `harness.py estudos`: o cabeçalho saiu da [forma](referencia.md#estudos).

## Registrar no ato

**Quando:** surge uma decisão, uma pergunta aberta ou uma informação nova; o modelo registra a cada rodada. O detalhe
está em [`references/entrevista.md`](../skills/refinar-documento/references/entrevista.md); os formatos, em [registrar](referencia.md#registrar).

1. Decisão que vale além do documento: peça um Ruling. O `harness.py registrar ruling` grava o quê, o porquê e o custo
   se errado, e você vê `Ruling acrescentado em <arquivo>:<linha>`.
2. Pergunta que fica aberta: peça uma pendência, com o destino que a resolve. O `harness.py registrar pendencia` imprime
   `<prefixo>-NN acrescentada em <arquivo>:<linha>`.
3. Informação nova, que não responde ao documento, não é decisão nem pergunta e não está escrita: peça um relato. O
   `harness.py registrar relato` a guarda no rascunho, `confirmada` se você a afirmou.
4. Decisão que muda outra vira Ruling novo, com `substitui o Ruling de <data>`, e nada se apaga. O `harness.py afetados`
   acha os documentos `aprovado` que a citam, e cada um ganha uma pendência.

**Se der errado:**
- `recusado: <motivo>`, sem gravar: tire a quebra de linha do texto, ou o `|` da pendência, da origem e do destino.
- IDs de pendência com erro, como no `harness.py backlog ids`: corrija a tabela de pendências antes.
- `guarda do harness: <arquivo> só aceita acréscimos`: não mude a linha antiga; registre uma nova.

## Retomar o trabalho

**Quando:** você abre uma sessão nova, roda `/clear`, a conversa foi compactada, ou volta noutra máquina ou árvore.

1. Na sessão nova, no `/clear` e na compactação, o hook do início da sessão devolve o estado ao modelo. No terminal,
   você vê `Planejamento · ... · Próximo: <ação>`; depois de compactar, essa linha não sai.
2. Rode `harness.py proximo`: `Próximo:` é a ação recomendada, `Depois:` a fila e `Atenção:` o que pede cuidado.
3. Documento no meio: chame `/ela-harness:refinar-documento` sem argumento, e o trabalho segue do `Passo` gravado.
4. Nos passos 6 e 7, o modelo roda antes `harness.py versao conferir`. Com `DIVERGE: arquivo mudou desde a marcação`
   ou, num pacote, `DIVERGE: <k> de <N> documentos mudaram desde a marcação: <lista>`, reaprove ou desfaça pelo diff.
5. Noutra máquina, depois do pull, com a versão marcada já no HEAD, o `Próximo:` é `consertar: harness.py fechar`; o
   modelo o roda sem perguntar, e o `STATUS.md` fechado sai num commit `chore`, porque o HEAD já está no remoto.
6. Num worktree, o `harness.py ambiente` dá `AVISO: worktree <branch>`, e o `Próximo:` de conserto termina em
   `(na árvore principal)`: refine os documentos na árvore principal.

**Se der errado:**
- `nenhuma mensagem do usuário depois da última marcação`: leia a mensagem de aprovação e responda.
- `versão marcada ausente da cópia e dos últimos 50 commits do arquivo`: releia o arquivo e aprove-o de novo.
- `<alvo> está na árvore <raiz>, e esta sessão trabalha na <outra>`: entre na árvore do alvo pelo `EnterWorktree`, ou abra uma sessão lá.

## Resolver uma recusa

**Quando:** um hook, o pre-commit ou a CI recusa algo. As regras: [guarda](referencia.md#guarda) e [invariantes](referencia.md#invariantes).

1. Leia a mensagem. A do hook começa por `guarda do harness:` e diz o caminho certo, quando há um, como
   `harness.py passo 3` antes de editar o documento em aprovação, ou uma linha nova no arquivo de decisões.
2. A mudança é sua, como corrigir um molde, que o `deny` do `settings.json` nega ao modelo? Faça você mesmo, com `!` no
   prompt: a guarda só olha o modelo. Num pedido de confirmação, confirme só a mudança que é sua.
3. No fim do turno, o Stop confere as invariantes e pede ao modelo desfazer ou explicar; molde e `STATUS.md` só você desfaz.
4. O pre-commit recusa com uma linha por conferência, como `moldes-intocados: FALHA: 2 arquivos, primeiro <arquivo>`. O
   `harness.py invariantes --indice --verbose` lista todos. Desfaça cada um com `git restore --staged <arquivo>` e
   `git restore <arquivo>` (arquivo novo: só o `git restore --staged`, e apague-o) e commite de novo.
5. Molde novo ou mudado de propósito: o hash dele entra em `moldes.liberados` do perfil, com a sua confirmação, e você
   copia o molde: o commit sai sem `--no-verify`, com `moldes-intocados: OK (<n> liberados pelo perfil)`.
6. Na CI, o check `harness` roda o `harness.py invariantes --base <ref> --verbose` e só informa o resultado.

**Se der errado:**
- `guarda do harness com erro, sem decisão: <motivo>`: a guarda falhou aberta; corrija o que o motivo aponta.
- `<falhas>; o pre-commit vai recusar o commit`: na segunda parada do turno, o Stop só avisa; desfaça antes do commit.
- `estrutura do STATUS.md inválida (...); corrija à mão`: corrija você o arquivo, porque o modelo não pode.

## Problemas que a mensagem não resolve

**Quando:** o sintoma não diz o comando que conserta.

1. Comece pelo `harness.py ambiente`, que não lê o perfil: cada `FALHA` traz o conserto. Sem `tomli` no Python 3.9 ou
   3.10, os comandos e o pre-commit dão `perfil inválido`, e a guarda falha aberta; rode `pip3 install --user tomli`.
2. Sem a linha `Planejamento · ...` no início da sessão: é normal após compactar e no VS Code, onde o `CLAUDE.md` manda
   repetir o `Próximo:`. No terminal, aceite o trust na raiz e confira `/hooks` e o `claude plugin list` ([Instalar](../README.md#instalar)).
3. O bloco "Este projeto" de uma skill veio como `[shell command execution disabled by policy]`: a skill roda
   `harness.py perfil --para <skill>` pelo Bash e segue; se ela parar num `perfil inválido`, conserte o perfil.
4. `erro: raiz do projeto não encontrada`: crie o `CLAUDE.md` na raiz ou defina a `CLAUDE_PROJECT_DIR`.
5. "Other" chega sem texto, o que acontece na extensão do VS Code: o modelo pede o texto no chat; responda numa linha.

**Se der errado:**
- Sem `python3` na máquina, os hooks somem sem aviso: instale o Python 3.9 ou mais novo.
- Nada disso resolveu: [relate o problema](#relatar-um-problema).

## Mudar o perfil

**Quando:** o projeto ganha uma fase, um gate ou um checklist, ou muda um caminho, um prefixo de ID, o `mapa` dos moldes
ou um termo do texto. As chaves e as regras estão em [perfil](referencia.md#perfil).

1. Peça a mudança ao modelo, cuja edição do `.claude/perfil.toml` pede a sua confirmação, ou edite você mesmo.
2. Rode `harness.py perfil`: `perfil válido: <nome>`, as fases com os gates, os checklists e os prefixos de ID.
3. Rode `harness.py estado`: o `STATUS.md` segue válido com as fases e os gates do perfil.
4. Rode `harness.py perfil --para <skill>` por skill: o bloco sai sem `ERRO` nem `AVISO: bloco com <N> caracteres`.
5. Rode `harness.py gerar`, que refaz pelo perfil o `.claude/harness/gerado/planejamento.md`, e commite os dois.

**Se der errado:**
- `perfil inválido: <motivo>`: só o `ambiente` e o `referencia` rodam, e a guarda falha aberta; corrija a chave.
- Gate renomeado: `linha dos gates fora do formato` ou, no primeiro, `campo desconhecido: <antigo>` e `campo ausente:`
  do novo e dos outros; corrija o `STATUS.md`. Fase renomeada: `valor inválido em Fase`; rode `estado set Fase <fase>`.
- Mudou `moldes.pasta`, `caminhos.status` ou `caminhos.rascunho`: troque o `deny` e o `ask` do `.claude/settings.json`.

## Começar um projeto

**Quando:** um repositório novo vai planejar com o mesmo ciclo: o núcleo vem do plugin; perfil, estado e `CLAUDE.md` são do projeto.

1. Na raiz do repositório, instale o plugin com os comandos de [Instalar](../README.md#instalar), uma vez por clone.
2. Abra o Claude Code na raiz e chame `/ela-harness:iniciar planejamento [nome]`. O `harness.py iniciar` copia o modelo
   (perfil, `settings.json`, `CLAUDE.md`, pre-commit, moldes e estado) e o lançador, gera o `harness.yml` da CI, liga o
   `core.hooksPath` e roda o `gerar`. O que já havia fica (`mantido:`); o `settings.json` recebe o que falta (`mesclado:`).
3. Ajuste o `.claude/perfil.toml`: pastas, fases, gates, padrões de ID e checklists ([Mudar o perfil](#mudar-o-perfil)).
4. No `CLAUDE.md`, em menos de 100 linhas, escreva o mapa do produto, as decisões fixas e as regras de escrita, e mantenha
   a linha `@.claude/harness/gerado/planejamento.md`, do texto do ciclo; num que já existia, o `mantido:` diz o que falta.
5. Escreva a ideia em `planejamento/rascunho.md`.
6. Confira com `harness.py ambiente`, `perfil`, `estado`, `backlog ids` e `proximo`, e abra uma sessão nova.

**Se der errado:**
- `não é a raiz de um repositório git` ou `já tem o harness`: rode na raiz de um repositório sem o lançador.
- `erro: núcleo do harness não encontrado`, com saída 3: o plugin não está instalado para esta pasta; rode o passo 1.
- A linha `plugins: falta: ...` do `iniciar` traz o comando que faltou rodar.

## Sair da origem privada

**Quando:** o projeto veio da `v0.2.1` à `v0.2.7`, e o marketplace `ela-harness` do `.claude/settings.json` aponta a
origem privada, que o CI baixa com o segredo `ELA_HARNESS_TOKEN`. É à mão, uma vez; sem migrar, segue com o token.

1. Na raiz, troque o marketplace: o `add` grava no settings o `repo` `Ela-Decora/ela-harness` e a `ref`. O `remove`
   desinstala os plugins e tira as entradas do `enabledPlugins`; os `install` as devolvem, o último só no desenvolvimento.
   ```bash
   claude plugin marketplace remove ela-harness --scope project
   claude plugin marketplace add Ela-Decora/ela-harness#v0.3.0 --scope project
   claude plugin install ela-harness@ela-harness --scope project
   claude plugin install ela-harness-papeis@ela-harness --scope project
   ```
2. Rode `harness.py gerar`: o `.github/workflows/harness.yml` sai gerado, sem token, e a guarda passa a protegê-lo.
3. No desenvolvimento, com verificações além do harness, declare a stack em `[desenvolvimento.ci] instalar`, como
   `["corepack enable", "pnpm install --frozen-lockfile"]`; ela roda só no CI, antes das verificações. O banco sobe
   com `docker compose up -d`: o que vai com `&` morre no fim do comando.
4. Commite e, se quiser, apague o segredo `ELA_HARNESS_TOKEN`. Cada outro clone roda só os `install`, uma vez. Com o
   Dependabot, ponha `exclude-paths: [".github/workflows/harness.yml"]` no `github-actions` do `.github/dependabot.yml`.

**Se der errado:**
- `plugin: falta` no `harness.py iniciar --conferir`: o settings ainda aponta a origem; refaça o passo 1.
- `harness.yml: o plugin carregado é v<X> e o .claude/settings.json fixa <ref>; reinstale o plugin`: refaça o passo 1.
- PR do Dependabot no `harness.yml`, vermelho com `desatualizado`: feche-o; o arquivo sobe com o `harness.py gerar`.
- `<nome>: a saída diz que falta o comando <cmd>`, no CI: instale-o no passo 3. O `harness.yml` gerado não leva
  `secrets`, e não se edita: verificação que pede segredo do GitHub não roda no CI.

## Relatar um problema

**Quando:** um comando falha sem dizer o que fazer, uma saída contradiz o manual ou falta uma peça. Abra uma issue em
[`Ela-Decora/ela-harness`](https://github.com/Ela-Decora/ela-harness/issues); pull request de fora não entra. Traga a
versão (a `ref` do `.claude/settings.json`), a trilha, o comando ou a skill e a saída, sem nomes, dados nem segredos do
projeto. A correção chega numa versão nova: troque a `ref`, reinstale o plugin e rode `harness.py gerar`.
