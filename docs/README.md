# Harness de planejamento

O harness conduz documentos de planejamento do rascunho à aprovação, dentro do Claude Code. O núcleo não sabe nada do
projeto: são os scripts, as skills, os agentes e este manual, que moram no plugin `ela-harness`. O perfil,
`.claude/perfil.toml` do projeto, diz ao núcleo o que é do projeto: pastas, fases, gates, padrões de ID e checklists.
Este manual é da trilha de planejamento; o [README da raiz](../README.md) traz as duas trilhas.

## Requisitos

- Claude Code aberto na raiz do repositório, com o trust da pasta aceito (sem ele, os hooks não rodam) e com o plugin
  `ela-harness@ela-harness` instalado para a pasta: cada clone novo roda uma vez os comandos de
  [Instalar](../README.md#instalar).
- Python 3.9 ou mais novo, com o pacote `tomli` no 3.9 e no 3.10.
- git com o pre-commit ativo: `git config core.hooksPath .githooks`, uma vez por clone.

Confira o Python e o pre-commit com o comando abaixo, que também avisa quando a sessão abriu num worktree:

```bash
python3 .claude/harness/harness.py ambiente
```

## O manual

| Arquivo | Para quê |
|---|---|
| [Tutorial](tutorial.md) | o primeiro documento, do ambiente ao commit, passo a passo |
| [Guias](guias.md) | um guia por tarefa: documento, pacote, gate, recusa, perfil, projeto novo, migração |
| [Referência](referencia.md) | cada comando, skill e agente, gerada por `harness.py referencia --gravar` |
| [Explicação](explicacao.md) | os porquês do desenho e os limites |

## As skills do planejamento

Só o usuário as chama, no chat; o modelo não as invoca sozinho. O prefixo `ela-harness:` é o do plugin.

- `/ela-harness:iniciar planejamento [nome]` cria o projeto a partir do modelo ([Começar um projeto](guias.md#começar-um-projeto)).
- `/ela-harness:refinar-documento <caminho>` começa ou retoma um documento e o leva pelo ciclo até a aprovação.
- `/ela-harness:gerar-modulos` gera em rascunho os módulos e as entidades e telas que eles juntam, a partir do escopo aprovado ([Gerar os módulos](guias.md#gerar-os-módulos)).
- `/ela-harness:gate-fase <gate>` fecha uma camada pelo checklist do gate.
- `/ela-harness:assessor <tema>` compara as opções de uma decisão e grava o estudo; a decisão fica com o usuário.

## Convenções

- `harness.py` abrevia `python3 .claude/harness/harness.py`, o lançador do projeto, que acha o núcleo no plugin.
- Todo caminho citado é relativo à raiz do repositório do projeto; os links partem da pasta do arquivo que os traz.

## O que é do projeto

- O `CLAUDE.md` da raiz: o mapa, as decisões fixas e o ciclo, lidos em toda sessão ([modelo](../modelo/planejamento/CLAUDE.md)).
- O perfil, `.claude/perfil.toml`, que os scripts e as skills leem ([modelo](../modelo/planejamento/.claude/perfil.toml)).
- O planejamento: a pasta `planejamento/`, com o `STATUS.md`, o backlog, as decisões, o rascunho e os moldes.
