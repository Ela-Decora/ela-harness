# ela-harness

O plugin `ela-harness` do Claude Code: um harness com duas trilhas e um perfil por projeto. O núcleo em Python, as skills, os agentes, o workflow, os modelos de projeto e o manual moram aqui; o projeto guarda só o perfil, o lançador e os arquivos dele. O núcleo não sabe nada do projeto: o perfil, `.claude/perfil.toml`, diz o que é dele e, em `[projeto] harness`, qual trilha ele roda.

- **Planejamento:** leva a ideia do projeto, por camadas com gates que só o humano aprova, do rascunho à aprovação de cada documento. O modelo escreve, um subagente revisa, e o estado fica em disco.
- **Desenvolvimento:** leva cada ficha do código ao merge, em blocos, cada um numa lane (uma worktree própria), com spec, plano, execução, revisão e PR, sobre a cópia da passagem do planejamento.

O plugin `ela-harness-papeis`, do mesmo marketplace, entra só na trilha de desenvolvimento: troca o modelo e o esforço dos agentes do ciclo do bloco.

## Instalar

Na raiz do repositório do projeto, com o `claude` no `PATH`, na versão `v0.4.0`:

```bash
claude plugin marketplace add Ela-Decora/ela-harness#v0.4.0 --scope project
claude plugin install ela-harness@ela-harness --scope project
claude plugin install ela-harness-papeis@ela-harness --scope project
```

O último comando é só da trilha de desenvolvimento. O `--scope project` grava no `.claude/settings.json` o marketplace fixado na tag e os plugins ligados, sem caminho absoluto: o projeto fixa a versão que usa, e trocar de versão é trocar a tag.

A instalação, porém, vale por pasta: cada clone novo roda uma vez o `claude plugin install <id> --scope project` de cada plugin da trilha. Sem isso, o lançador sai com 3 e mostra o comando e, no repositório de código, o `harness.py iniciar --conferir` aponta o plugin que falta.

## Começar

Numa sessão do Claude Code aberta na raiz de um repositório git, chame:

```text
/ela-harness:iniciar <trilha> [nome]
```

A `<trilha>` é `planejamento` ou `desenvolvimento`. A skill copia o modelo da trilha (`modelo/<trilha>/`) e o lançador para o projeto, liga o `core.hooksPath` aos githooks, instala os plugins da trilha e, no planejamento, gera o texto do ciclo. O que o projeto já tinha fica como está, com uma linha `mantido: <caminho>`; o `.claude/settings.json` que a instalação gravou recebe do modelo as permissões e o que mais faltar, sem perder a `ref` instalada, com a linha `mesclado: .claude/settings.json`. O `{{PROJETO}}` do modelo vira o `nome` ou o nome da pasta. A saída termina com o próximo passo.

## Requisitos

- Claude Code aberto na raiz do projeto, com o trust da pasta aceito; sem o trust, os hooks não rodam.
- Python 3.9 ou mais novo, com o pacote `tomli` no 3.9 e no 3.10.
- git com os githooks ativos: `git config core.hooksPath .githooks`, uma vez por clone; o `iniciar` já o faz no primeiro.

Na trilha de planejamento, confira o Python e o pre-commit com o comando abaixo, que também avisa quando a sessão abriu num worktree:

```bash
python3 .claude/harness/harness.py ambiente
```

A trilha de desenvolvimento não tem o `ambiente`: no repositório de código, o `python3 .claude/harness/harness.py iniciar --conferir` diz, um item por linha, o que falta para o primeiro bloco, os githooks e os plugins inclusive.

## O manual

O [`docs/README.md`](docs/README.md) é o índice do manual, que é da trilha de planejamento; a referência cobre as duas.

| Arquivo | Para quê |
|---|---|
| [Tutorial](docs/tutorial.md) | o primeiro documento, do ambiente ao commit, passo a passo |
| [Guias](docs/guias.md) | um guia por tarefa: documento, pacote, gate, recusa, perfil, projeto novo |
| [Referência](docs/referencia.md) | cada comando, skill e agente, gerada por `harness.py referencia --gravar` |
| [Explicação](docs/explicacao.md) | os porquês do desenho e os limites |

## As skills

O prefixo `ela-harness:` é o do plugin. O `iniciar` e as quatro do planejamento têm `disable-model-invocation: true`: só o usuário as chama, no chat, e o modelo não as invoca sozinho.

- `/ela-harness:iniciar <trilha> [nome]` cria o projeto a partir do modelo da trilha.
- Planejamento: `/ela-harness:refinar-documento <caminho>` leva um documento do rascunho à aprovação; `/ela-harness:gate-fase <gate>` fecha uma camada pelo checklist do gate; `/ela-harness:gerar-modulos` gera em rascunho as entidades, as telas e os módulos da camada a partir do escopo aprovado; `/ela-harness:assessor <tema>` compara as opções de uma decisão e grava o estudo, e a decisão fica com o usuário.
- Desenvolvimento, uma por estado do bloco, sem essa chave: o dono as chama, e o modelo também as invoca, quando o `harness.py bloco status` indica a skill do estado. `/ela-harness:planejar-bloco` planeja uma ficha ou um pedido em texto livre, a pedido do dono; `/ela-harness:executar-bloco`, `/ela-harness:revisar-bloco` e `/ela-harness:finalizar-bloco` valem só dentro da lane do bloco, no estado que cada uma atende.

## Convenções

- `harness.py` abrevia `python3 .claude/harness/harness.py`, o lançador do projeto, rodado da raiz dele. Ele acha o núcleo no plugin e passa os argumentos adiante.
- Caminho de arquivo do projeto parte da raiz dele; caminho do núcleo, da raiz deste repositório.
- O [`CHANGELOG.md`](CHANGELOG.md) diz o que mudou em cada tag; o projeto fixa a sua no `.claude/settings.json`.

## O que é do projeto

O [`modelo/`](modelo/) traz, em `modelo/planejamento/` e `modelo/desenvolvimento/`, o que cada projeto tem: o `CLAUDE.md`, o `.claude/perfil.toml`, o `.claude/settings.json` com as permissões e o plugin fixado, o pre-commit (e o pre-push, no desenvolvimento) e os arquivos de estado; o planejamento leva ainda os moldes. O lançador, `modelo/lancador.py`, é o mesmo nas duas trilhas. O workflow da CI, `.github/workflows/harness.yml`, não vem do modelo: o `iniciar` o gera, e o `harness.py gerar` o mantém em dia.

## De onde vem o código

Este repositório é a distribuição do plugin: cada versão chega aqui como um retrato do repositório de origem, que é privado, e a tag é a mesma nos dois. Por isso, pull request de fora não entra. Um defeito, uma dúvida ou um pedido vira uma [issue](https://github.com/Ela-Decora/ela-harness/issues), com a versão do plugin, o comando e a saída; a correção sai na origem e chega na versão seguinte.

A licença é a MIT, no [`LICENSE`](LICENSE). O texto adaptado de outros projetos traz a origem e a licença no [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md).
