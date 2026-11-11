"""Arquivos gerados do repositório de código (spec 6d-gerador, §5 e §7): os textos, a partir da passagem e do perfil.

São oito: as regras por área do código, o `AGENTS.md`, o Registry, o `produto.md`, o `verificacoes.md`, o `papeis.md`, o
`ciclo.md` e a legenda. Cada um sai inteiro, com o aviso de que é gerado, e nenhum traz a versão da passagem, menos o `produto.md`. A lista
`GERADORES` dá, na ordem, a função de cada arquivo; o `gerar` é a função pura que devolve o texto de cada um, com um
`ler` que dá o texto de um caminho relativo à raiz ou None. O comando, a conferência, a invariante e o `importar` usam
o mesmo `gerar`. As pastas do gerador, `PASTAS`, só têm arquivos dele: o que ele não escreveria agora é órfão. O
`AGENTS.md` e a legenda têm caminho fixo, fora delas.

O `gerar` recusa, com a `GeracaoRecusada`, quando a passagem não serve: o manifesto que falta, não se lê, tem outro
formato ou não diz uma versão publicada, sozinho; senão, juntas e em ordem, as regras de arquitetura que a cópia não
confirma, as áreas com regras que dão o mesmo arquivo ou não têm pasta e a legenda da passagem que não se acha ou não tem a tabela. O
agente do ciclo que falta ou não se lê recusa sozinho, com a recusa do `papel`.

O comando confere os textos contra o disco (`problemas`), byte a byte, com os arquivos das pastas do gerador pelo git,
fora os ignorados, e grava só o que muda, apagando os órfãos (`gravar`); o `--check` só confere.

Na trilha de planejamento (spec do porte 1, §9), o gerador escreve um arquivo só, o `planejamento.md`, com o texto do
`gerado_planejamento`, e a única pasta dele é `.claude/harness/gerado/`. O `gerar_na_trilha` e o `pastas_da_trilha`
escolhem pelo tipo do perfil, e o resto do comando é o mesmo nas duas trilhas.
"""
from __future__ import annotations

import json
import posixpath
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import bloco
import ci
import comum
import fichas
import gerado_planejamento
import legenda
import manifesto
import papeis
import perfil_comum
import regras
from manifesto import Area, Manifesto
from perfil import Perfil, carregar as carregar_perfil
from regras import Regra

AJUDA = """\
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
"""

AVISO = "Arquivo gerado por harness.py gerar. Não edite: rode harness.py gerar."
AGENTS = "AGENTS.md"
PASTA_DAS_REGRAS = ".claude/rules/harness"
PASTA_DOS_GERADOS = ".claude/harness/gerado"
PASTAS = (PASTA_DAS_REGRAS, PASTA_DOS_GERADOS)
REGISTRY = f"{PASTA_DOS_GERADOS}/registry.json"
PRODUTO = f"{PASTA_DOS_GERADOS}/produto.md"
VERIFICACOES = f"{PASTA_DOS_GERADOS}/verificacoes.md"
PAPEIS = f"{PASTA_DOS_GERADOS}/papeis.md"
CICLO = f"{PASTA_DOS_GERADOS}/ciclo.md"
PLANEJAMENTO = f"{PASTA_DOS_GERADOS}/planejamento.md"
AUSENTE = "ausente"
DESATUALIZADO = "desatualizado"
ORFAO = "órfão"

_COMENTARIO = f"<!-- {AVISO} -->"
_FRASE_DA_REGRA = ("Regras de arquitetura desta área, copiadas da passagem. Teste e lint se conferem pelas "
                   "verificações; revisão, na revisão do bloco.")
_FRASE_DAS_VERIFICACOES = (
    "O Stop da lane roda as de `stop` cujos caminhos casam com o que mudou; o `bloco finalizar` roda as de "
    "`finalizar`. A que tem um arquivo de `requer` faltando é pulada no Stop, com aviso, e falha no `bloco finalizar`."
)
_SEM_VERIFICACAO = "Nenhuma verificação no perfil."
_FRASE_DOS_PAPEIS = (
    "Modelo e esforço de cada agente; a troca fica em [desenvolvimento.modelos] do perfil e chega a cada despacho "
    "pelo mod do harness."
)
_CICLO = """\
# Ciclo do bloco

Instruções de {dono} para este repositório. Valem acima do que as skills de terceiros mandam.

| Skill | Estados | {dono} |
|---|---|---|
| /{prefixo}planejar-bloco | nenhum → planning → ready_for_execution | aprova a spec; confirma o bloco planejado |
| /{prefixo}executar-bloco | ready_for_execution → executing → ready_for_review | só quando falta contexto |
| /{prefixo}revisar-bloco | ready_for_review → reviewing → ready_for_closure | Crítico ou Importante aberto depois de 3 consertos: orienta, dispensa ou replaneja |
| /{prefixo}finalizar-bloco | ready_for_closure → closing | confirma o push e o PR; itens manuais; merge |

Aprovada a spec, o ciclo segue sozinho de uma skill para a seguinte.

## Quem decide

Chame {dono} só para aprovar a spec, nas confirmações da guarda, nos itens manuais e nestes casos:
1. a investigação do bloco curto não acha a causa, ou acha mais de uma;
2. o bloco esbarra numa decisão da passagem: abra o harness.py retorno abrir --tipo decisao;
3. o bloco curto passa de 3 tarefas ou pede uma decisão de desenho: proponha o harness.py bloco replanejar;
4. as paradas que o subagent-driven-development nomeia;
5. a revisão gasta os 3 consertos e sobra Crítico ou Importante em aberto: mostre cada achado e as saídas (orientação no chat, harness.py revisao dispensar com a palavra de {dono}, harness.py bloco replanejar);
6. o harness.py bloco finalizar recusa, ou o workflow revisao-do-bloco falha, duas vezes pelo mesmo motivo.

## Dispensas das skills de terceiros

- brainstorming, no caminho normal do /{prefixo}planejar-bloco: a ficha já traz o objetivo e o aceite. Não abra com a oferta de pular as perguntas nem com a pergunta aberta, não faça uma pergunta por mensagem, não devolva o desenho por partes e não ofereça o companheiro visual, a busca nem o protótipo; pergunte a {dono} só nos casos de Quem decide. Sem o tamanho do trabalho e sem a leitura do construtor (builder check) sobre a spec escrita. A spec vai para {blocos}/<ID>-<slug>/spec.md, não para docs/superpowers/specs, e quem chama o writing-plans é o /{prefixo}planejar-bloco, depois da aprovação da spec.
- writing-plans: não peça revisão do plano nem a escolha do método. {dono} aprovou a spec; o método é o subagent-driven-development.
- A spec vai para {blocos}/<ID>-<slug>/spec.md; o plano, em inglês, para {blocos}/<ID>-<slug>/plano.md.
- subagent-driven-development: não faça a revisão final do branch nem chame o finishing-a-development-branch, e não apague a pasta do plano em .superpowers/sdd/. Depois da última tarefa, volte ao /{prefixo}executar-bloco, que roda o harness.py bloco executado com o ledger dessa pasta.
- Despache pelo subagent_type: {prefixo}implementador-mecanico ou {prefixo}implementador-integracao por tarefa, {prefixo}revisor-task, {prefixo}re-revisor e, nas rodadas 4 e 5, {prefixo}corretor-tardio, com o texto de despacho do próprio SDD. O model e o effort de cada despacho são os do papeis.md, no lugar da escolha de modelo do SDD.
- diagnosing-bugs, no /{prefixo}planejar-bloco: pare depois da fase 4. O teste de regressão e a correção são tarefas do plano; tire a instrumentação [DEBUG-...] e a reprodução descartável antes do harness.py bloco planejado.
- wizard, no /{prefixo}finalizar-bloco: grave o script pelo Write em .superpowers/wizard/, com o .superpowers/wizard/.gitignore (*), sem cp, bash -n, chmod nem execução pela sessão; {dono} o roda no terminal.

## Idioma

Entre agentes, inglês: planos, despachos, definições e relatórios. Com {dono}, português. IDs, termos e trechos de RA, RF e FN, sem tradução.

## Skills de terceiros

{terceiros}

## Retomada

harness.py bloco status diz o estado e o próximo passo; depois de compactar, o hook de início diz o mesmo.

Sessão nova: num ponto de encadeamento, com a sessão já compactada ou com o pedido de {dono} de outra sessão, não invoque a skill seguinte. Entregue a linha de sessão nova, com os caminhos por extenso, e pare:

```
Abra a sessão nova na árvore principal (<raiz da árvore principal>), não na lane, e cole:
Entre pelo EnterWorktree em <caminho da lane> e invoque a skill {prefixo}<skill> pela ferramenta Skill, para o bloco <ID>; pare <onde>.
```

<onde> é o ponto que {dono} pediu e, sem pedido, com o PR aberto.
"""
_DESCRICAO_DA_FICHA = "ficha do código"
_RE_FORA_DO_SLUG = re.compile(r"[^a-z0-9]+")


class GeracaoRecusada(Exception):
    """A passagem ou o perfil não dão os arquivos gerados: cada motivo cabe numa linha, na ordem em que aparecem."""

    def __init__(self, motivos: tuple[str, ...]):
        super().__init__("; ".join(motivos))
        self.motivos = motivos


@dataclass(frozen=True)
class _Estado:
    perfil: object  # o `PerfilDesenvolvimento`
    manifesto: Manifesto
    regras: tuple[Regra, ...]
    ler: Callable[[str], str | None]


def slug_da_area(nome: str) -> str:
    """O nome da área sem acentos, em minúsculas, com cada sequência fora de `[a-z0-9]` trocada por `-` e sem `-` nas
    pontas: `Serviço de Pedidos` dá `servico-de-pedidos`."""
    sem_marcas = "".join(c for c in unicodedata.normalize("NFKD", nome) if not unicodedata.combining(c))
    return _RE_FORA_DO_SLUG.sub("-", sem_marcas.lower()).strip("-")


def _arquivo_da_area(nome: str) -> str:
    return f"area-{slug_da_area(nome)}.md"


def globs_da_area(area: Area) -> list[str]:
    """Os `paths` da área: a pasta que termina em `/` ganha `**`, e o arquivo entra como está."""
    return [f"{pasta}**" if pasta.endswith("/") else pasta for pasta in area.pastas]


def _com_regras(estado: _Estado) -> list[tuple[Area, list[Regra]]]:
    """As áreas da tabela com pelo menos uma regra, na ordem dela, cada uma com as regras dela em ordem de número."""
    lista = []
    for area in estado.manifesto.areas:
        da_area = [regra for regra in estado.regras if area.area in regra.areas]
        if da_area:
            lista.append((area, da_area))
    return lista


def _pasta(perfil) -> str:
    return perfil.caminhos.passagem


def _caminho_do_manifesto(perfil) -> str:
    return f"{_pasta(perfil)}/{manifesto.NOME}"


def _regras_por_area(estado: _Estado) -> list[tuple[str, str]]:
    """Uma regra do Claude Code por área com regras: os `paths`, o aviso, o título, a frase e cada regra com a fonte."""
    arquivos = []
    for area, da_area in _com_regras(estado):
        linhas = ["---", "paths:"]
        linhas += [f"  - {json.dumps(glob, ensure_ascii=False)}" for glob in globs_da_area(area)]
        linhas += ["---", _COMENTARIO, f"# Área do código: {area.area}", "", _FRASE_DA_REGRA, ""]
        for regra in da_area:
            linhas.append(f"- **{regra.id}** ({', '.join(regra.conferencia)}): {regra.texto}")
            linhas.append(f"  Fonte: `{regra.fonte.arquivo}:{regra.fonte.linhas[0]}`, "
                          f"trecho `{regra.fonte.sha256[:12]}`.")
        arquivos.append((f"{PASTA_DAS_REGRAS}/{_arquivo_da_area(area.area)}", "\n".join(linhas) + "\n"))
    return arquivos


def _agents(estado: _Estado) -> list[tuple[str, str]]:
    """O ponteiro para os agentes que não leem o `CLAUDE.md` nem as regras do Claude Code."""
    perfil = estado.perfil
    com_regras = _com_regras(estado)
    linhas = [
        _COMENTARIO, "# AGENTS.md", "",
        "Ponteiro para os agentes que não leem o `CLAUDE.md` nem as regras do Claude Code. Leia, nesta ordem:", "",
        "1. `CLAUDE.md` e os arquivos que ele puxa com `@`.",
    ]
    if com_regras:
        linhas.append(f"2. As regras de arquitetura de `{PASTA_DAS_REGRAS}/`, cada uma nos caminhos em que vale:")
        for area, _ in com_regras:
            globs = ", ".join(f"`{glob}`" for glob in globs_da_area(area))
            linhas.append(f"   - `{_arquivo_da_area(area.area)}`: {globs}")
    else:
        linhas.append(f"2. As regras de arquitetura de `{PASTA_DAS_REGRAS}/`: nenhuma.")
    linhas.append(f"3. `{_caminho_do_manifesto(perfil)}`, para achar cada ID, e `{perfil.caminhos.legenda}`, para "
                  "cada sigla.")
    return [(AGENTS, "\n".join(linhas) + "\n")]


def _registry(estado: _Estado) -> list[tuple[str, str]]:
    """O Registry no formato da revisão: o aviso, as áreas da tabela e as regras, cada uma com a severidade da RA ou o
    padrão do perfil (spec 6d-bloco, §9.3), sem dependências proibidas."""
    dados = {
        "gerado": AVISO,
        "layers": [{"name": area.area, "paths": globs_da_area(area)} for area in estado.manifesto.areas],
        "rules": [
            {
                "id": regra.id,
                "description": regra.texto,
                "from": list(regra.areas),
                "severity": regra.severidade or estado.perfil.registro.severidade_padrao,
                "conferencia": list(regra.conferencia),
                "fonte": {"arquivo": regra.fonte.arquivo, "linhas": list(regra.fonte.linhas),
                          "sha256": regra.fonte.sha256},
            }
            for regra in estado.regras
        ],
    }
    return [(REGISTRY, json.dumps(dados, ensure_ascii=False, indent=2) + "\n")]


def _produto(estado: _Estado) -> list[tuple[str, str]]:
    """O produto em poucas linhas: a versão e a origem da passagem e onde se acha cada ID, cada sigla e cada regra."""
    perfil = estado.perfil
    m = estado.manifesto
    tag = f"{manifesto.PREFIXO_TAG}{m.versao}"
    linhas = [
        _COMENTARIO, f"# Produto: {perfil.comum.nome} ({tag})", "",
        f"O planejamento aprovado está em `{_pasta(perfil)}/`, só para leitura: a {tag}, de "
        f"`{m.origem.repositorio}`, no commit `{m.origem.commit[:12]}`, de {m.origem.data}.", "",
        f"- Cada ID se acha no `{_caminho_do_manifesto(perfil)}`, no campo `ids`, com o arquivo e as linhas.",
        f"- Cada sigla e tipo de ID se acha em `{perfil.caminhos.legenda}`.",
        f"- As regras de arquitetura de cada área do código estão em `{PASTA_DAS_REGRAS}/`, carregam sozinhas nos "
        f"arquivos da área e estão todas em `{REGISTRY}`.",
    ]
    return [(PRODUTO, "\n".join(linhas) + "\n")]


def _crases(itens: tuple[str, ...], vazio: str) -> str:
    return ", ".join(f"`{item}`" for item in itens) if itens else vazio


def _verificacoes(estado: _Estado) -> list[tuple[str, str]]:
    """As verificações do perfil numa tabela, na ordem dele: o nome, o comando, os momentos, os caminhos e o `requer`."""
    linhas = [_COMENTARIO, "# Verificações", "", _FRASE_DAS_VERIFICACOES, ""]
    verificacoes = estado.perfil.verificacoes
    if verificacoes:
        linhas += ["| Nome | Comando | Quando | Caminhos | Requer |", "|---|---|---|---|---|"]
        for verificacao in verificacoes:
            comando = verificacao.comando.replace("|", "\\|")
            celulas = [verificacao.nome, f"`{comando}`", ", ".join(verificacao.momentos),
                       _crases(verificacao.caminhos, "sempre"), _crases(verificacao.requer, "—")]
            linhas.append("| " + " | ".join(celulas) + " |")
    else:
        linhas.append(_SEM_VERIFICACAO)
    return [(VERIFICACOES, "\n".join(linhas) + "\n")]


def _papeis(estado: _Estado) -> list[tuple[str, str]]:
    """A tabela dos oito agentes com o `model` e o `effort` de cada um e a origem do valor (spec 6d-bloco, §6.4); o
    verificador que sobe em bloco sensível diz isso na coluna do modelo. O agente que falta, não se lê ou não tem o
    `model` ou o `effort` dá a `GeracaoRecusada` com a recusa do `papeis`."""
    try:
        tabela = papeis.tabela(estado.perfil)
    except bloco.Recusa as erro:
        raise GeracaoRecusada((erro.mensagem,)) from None
    linhas = [_COMENTARIO, "# Papéis", "", _FRASE_DOS_PAPEIS, "",
              "| Agente | Papel | model | effort | Origem |", "|---|---|---|---|---|"]
    for papel in tabela:
        modelo = f"{papel.model}; {papel.model_sensivel} em bloco sensível" if papel.model_sensivel else papel.model
        linhas.append(f"| {papel.agente} | {papel.papel} | {modelo} | {papel.effort} | {papel.origem} |")
    return [(PAPEIS, "\n".join(linhas) + "\n")]


def _ciclo(estado: _Estado) -> list[tuple[str, str]]:
    """As instruções do ciclo do bloco (spec 6d-bloco, §9.2): o nome do dono e a pasta dos blocos vêm do perfil."""
    perfil = estado.perfil
    terceiros = "\n".join(f"- {plugin} {versao}: {comum.juntar(skills)}." for plugin, versao, skills in papeis.TERCEIROS)
    corpo = _CICLO.format(dono=perfil.dono.nome, blocos=perfil.caminhos.blocos, terceiros=terceiros,
                          prefixo=comum.PREFIXO_DAS_SKILLS)
    return [(CICLO, f"{_COMENTARIO}\n{corpo}")]


def _pasta_de(caminho: str) -> str:
    return posixpath.dirname(caminho) or "."


def _caminho_da_legenda_da_passagem(perfil) -> str:
    return f"{_pasta(perfil)}/{perfil.passagem.legenda}"


def _legenda(estado: _Estado) -> list[tuple[str, str]]:
    """A legenda do código: a parte 2 da legenda da passagem, com os links movidos para a pasta da legenda do código, e
    por último a linha do prefixo das fichas do código, com o link para a pasta do backlog."""
    perfil = estado.perfil
    destino = perfil.caminhos.legenda
    projeto: list[str] = []
    if perfil.passagem.legenda:
        origem = _caminho_da_legenda_da_passagem(perfil)
        linhas = legenda.linhas_do_projeto(estado.ler(origem) or "") or []
        projeto += [legenda.mover_links(linha, _pasta_de(origem), _pasta_de(destino)) for linha in linhas]
    backlog = perfil.caminhos.backlog
    link = posixpath.relpath(backlog, _pasta_de(destino)) + "/"
    projeto.append(f"| {perfil.prefixo} | {_DESCRICAO_DA_FICHA} | `{perfil.prefixo}-NN` | [{backlog}/]({link}) |")
    return [(destino, legenda.do_codigo(_COMENTARIO, projeto, fichas.PREFIXO_DA_PENDENCIA))]


GERADORES: tuple[Callable[[_Estado], list[tuple[str, str]]], ...] = (
    _regras_por_area, _agents, _registry, _produto, _verificacoes, _papeis, _ciclo, _legenda,
)


def _manifesto(ler: Callable[[str], str | None], perfil) -> Manifesto:
    """O manifesto da cópia, conferido como o `importar` confere o da tag; a falha é a única recusa."""
    caminho = _caminho_do_manifesto(perfil)
    texto = ler(caminho)
    if texto is None:
        raise GeracaoRecusada((f"sem passagem: {caminho} não existe; rode harness.py importar",))
    try:
        m = manifesto.de_json(texto)
    except manifesto.ManifestoInvalido as erro:
        raise GeracaoRecusada((f"{caminho}: manifesto ilegível: {erro.motivo}",)) from None
    if not manifesto.formato_lido(m.formato):
        raise GeracaoRecusada((f"{caminho}: {manifesto.motivo_do_formato(m.formato)}; atualize o harness",))
    if not isinstance(m.versao, int) or isinstance(m.versao, bool) or m.versao < 1:
        raise GeracaoRecusada((f"{caminho}: o manifesto diz versão {json.dumps(m.versao)}",))
    return m


def _motivos_das_areas(m: Manifesto, lista: tuple[Regra, ...]) -> list[str]:
    """As áreas com regras, na ordem da tabela, que não dão nome de arquivo, dão o de uma anterior ou não têm
    pasta."""
    motivos = []
    vistas: dict[str, str] = {}
    for area in m.areas:
        if not any(area.area in regra.areas for regra in lista):
            continue
        arquivo = _arquivo_da_area(area.area)
        if not slug_da_area(area.area):
            motivos.append(f"a área {area.area} não dá nome de arquivo")
        elif arquivo in vistas:
            motivos.append(f"as áreas {vistas[arquivo]} e {area.area} dão o mesmo arquivo {arquivo}")
        else:
            vistas[arquivo] = area.area
        if not area.pastas:
            motivos.append(f"a área {area.area} tem regras e nenhuma pasta na tabela das áreas")
    return motivos


def gerar(ler: Callable[[str], str | None], perfil) -> dict[str, str]:
    """Os textos dos arquivos gerados, por caminho relativo à raiz, na ordem dos `GERADORES`.

    O `ler(caminho)` dá o texto do caminho ou None, também para o arquivo fora do UTF-8. As falhas saem juntas na
    `GeracaoRecusada`: a da legenda do código num arquivo do gerador sozinha, depois a do manifesto sozinha; senão, as
    das regras, as das áreas e a da legenda da passagem, nessa ordem. As áreas só se conferem com as regras lidas.
    """
    destino = perfil.caminhos.legenda.lower()
    if destino == AGENTS.lower() or any(destino == p.lower() or destino.startswith(p.lower() + "/") for p in PASTAS):
        raise GeracaoRecusada((f"desenvolvimento.caminhos.legenda: {perfil.caminhos.legenda} é um arquivo do gerador",))
    m = _manifesto(ler, perfil)
    motivos: list[str] = []
    lista: tuple[Regra, ...] = ()
    try:
        lista = regras.da_passagem(m, ler, _pasta(perfil))
    except regras.RegrasRecusadas as erro:
        motivos += erro.motivos
    else:
        motivos += _motivos_das_areas(m, lista)
    if perfil.passagem.legenda:
        caminho = _caminho_da_legenda_da_passagem(perfil)
        texto = ler(caminho)
        if texto is None or legenda.TITULO_DO_PROJETO not in texto.splitlines():
            motivos.append(f"{caminho}: legenda da passagem não achada")
        elif legenda.linhas_do_projeto(texto) is None:
            motivos.append(f"legenda da passagem sem a tabela: {caminho}")
    if motivos:
        raise GeracaoRecusada(tuple(motivos))
    estado = _Estado(perfil, m, lista, ler)
    textos: dict[str, str] = {}
    for gerador in GERADORES:
        for caminho, texto in gerador(estado):
            textos[caminho] = texto
    return textos


def gerar_na_trilha(ler: Callable[[str], str | None], perfil) -> dict[str, str]:
    """Os textos dos arquivos gerados da trilha do perfil. Com o `Perfil` de planejamento, o `planejamento.md`: o aviso
    de gerado e o texto do `gerado_planejamento`, que só depende do perfil e não chama o `ler`. Com o
    `PerfilDesenvolvimento`, o `gerar`, que recusa com a `GeracaoRecusada`."""
    if isinstance(perfil, Perfil):
        return {PLANEJAMENTO: f"{_COMENTARIO}\n{gerado_planejamento.texto(perfil)}"}
    return gerar(ler, perfil)


def pastas_da_trilha(perfil) -> tuple[str, ...]:
    """As pastas do gerador da trilha do perfil: só a dos gerados no planejamento, as duas no desenvolvimento."""
    return (PASTA_DOS_GERADOS,) if isinstance(perfil, Perfil) else PASTAS


def problemas(textos: dict[str, str], dados: Callable[[str], bytes | None],
              presentes: Iterable[str]) -> list[tuple[str, str]]:
    """O `(problema, caminho)` de cada texto ausente ou diferente, byte a byte, na ordem dos `textos`, e depois cada
    caminho `presentes` fora dos textos, como órfão, em ordem alfabética. O `dados(caminho)` dá os bytes ou None."""
    lista = []
    for caminho, texto in textos.items():
        atual = dados(caminho)
        if atual is None:
            lista.append((AUSENTE, caminho))
        elif atual != texto.encode("utf-8"):
            lista.append((DESATUALIZADO, caminho))
    lista += [(ORFAO, caminho) for caminho in sorted(set(presentes) - set(textos))]
    return lista


def dados_do_disco(raiz: Path) -> Callable[[str], bytes | None]:
    """O `dados` sobre o disco: os bytes do caminho relativo à raiz, ou None se ele não existe."""

    def dados(relativo: str) -> bytes | None:
        try:
            return (raiz / relativo).read_bytes()
        except (FileNotFoundError, NotADirectoryError):
            return None

    return dados


def _gerados_fora_das_pastas(raiz: Path, executar) -> set[str]:
    """Os arquivos rastreados cuja primeira linha é o aviso de gerado, achados pelo `git grep` e conferidos pela
    primeira linha. O `git grep` sem achado sai com 1, e isso não é erro; com código maior, recusa com
    `git grep falhou: <motivo do git>`. O arquivo que não se lê ou não é UTF-8 não entra."""
    resultado = bloco.git(raiz, ["grep", "-l", "-z", "-F", "-e", _COMENTARIO], executar)
    if resultado.returncode not in (0, 1):
        raise bloco.Recusa(f"git grep falhou: {comum.motivo_do_git(resultado, 'grep')}")
    achados = set()
    for caminho in resultado.stdout.decode("utf-8", errors="replace").split("\0"):
        if not caminho:
            continue
        try:
            linhas = (raiz / caminho).read_bytes().decode("utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        if linhas and linhas[0] == _COMENTARIO:
            achados.add(caminho)
    return achados


def presentes_no_disco(raiz: Path, executar=subprocess.run, pastas: tuple[str, ...] = PASTAS) -> list[str]:
    """Os arquivos do gerador que existem, relativos à raiz e em ordem: os das `pastas` do gerador que o git lista,
    rastreados ou não, fora os ignorados, e os rastreados fora delas cuja primeira linha é o aviso de gerado, como a
    legenda do caminho antigo. As `pastas` são as da trilha (`pastas_da_trilha`). O `git ls-files` que falha dá
    `Recusa("fora de um repositório git")`, e o `git grep`, `Recusa("git grep falhou: <motivo>")`."""
    resultado = bloco.git(raiz, ["ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", *pastas],
                          executar)
    if resultado.returncode != 0:
        raise bloco.Recusa("fora de um repositório git")
    listados = resultado.stdout.decode("utf-8", errors="replace").split("\0")
    das_pastas = {caminho for caminho in listados if caminho and (raiz / caminho).is_file()}
    return sorted(das_pastas | _gerados_fora_das_pastas(raiz, executar))


def _apagar_pastas_vazias(raiz: Path, caminho: str) -> None:
    """Apaga cada pasta que ficou vazia, da do `caminho` para cima, sem passar da pasta do gerador que o contém, que
    fica; o caminho fora delas sobe até a raiz, que também fica."""
    pasta = posixpath.dirname(caminho)
    while pasta and pasta not in PASTAS:
        try:
            (raiz / pasta).rmdir()
        except OSError:
            return
        pasta = posixpath.dirname(pasta)


def gravar(raiz: Path, textos: dict[str, str], problemas_: list[tuple[str, str]]) -> None:
    """Grava cada texto ausente ou desatualizado e apaga cada órfão, com as pastas que ele deixou vazias."""
    for problema, caminho in problemas_:
        if problema == ORFAO:
            (raiz / caminho).unlink()
            _apagar_pastas_vazias(raiz, caminho)
        else:
            comum.escrever_texto(raiz / caminho, textos[caminho])


def textos_do_ci(ler: Callable[[str], str | None], perfil,
                 versao: str | None = None) -> tuple[dict[str, str], tuple[str, ...]]:
    """Os textos do `harness.yml` do projeto (vazio sem o `.claude/settings.json`) e as recusas dele, cada uma uma
    linha. O ramo é o `ramo_principal` do perfil de desenvolvimento e o `ramo_do_ci` no de planejamento. A `ref` do
    settings tem de ser `v<versao>`, com a `versao` None valendo a do núcleo carregado: senão a recusa é de versão."""
    if isinstance(perfil, Perfil):
        trilha, ramo = perfil_comum.PLANEJAMENTO, perfil.ramo_do_ci
    else:
        trilha, ramo = perfil_comum.DESENVOLVIMENTO, perfil.ramo_principal
    try:
        return ci.gerar(ler, trilha, ramo, ci.versao_do_nucleo() if versao is None else versao), ()
    except ci.RecusaDoCi as erro:
        return {}, (erro.motivo,)


def textos_e_problemas(raiz: Path, perfil, executar=subprocess.run
                       ) -> tuple[dict[str, str], list[tuple[str, str]], tuple[str, ...]]:
    """Os textos do `harness.yml` e da trilha do perfil, os problemas deles contra o disco de `raiz` e as recusas: o
    que o `gerar` grava e o `gerar --check` mostra. A recusa do gerador da trilha (`GeracaoRecusada`) vira recusas,
    depois as do CI, os textos são só os do CI e nenhum órfão se apaga."""
    ler = comum.leitor_do_disco(raiz)
    textos, recusas = textos_do_ci(ler, perfil)
    try:
        textos = {**textos, **gerar_na_trilha(ler, perfil)}
        presentes = presentes_no_disco(raiz, executar, pastas_da_trilha(perfil))
    except GeracaoRecusada as erro:
        recusas = (*erro.motivos, *recusas)
        presentes = []  # sem os textos da trilha, os gerados dela no disco não são órfãos
    return textos, problemas(textos, dados_do_disco(raiz), presentes), recusas


def gravar_o_planejamento(raiz: Path, executar=subprocess.run, com_ci: bool = True) -> tuple[str, ...]:
    """O `gerar` da trilha de planejamento em `raiz`, como o comando: carrega o perfil, gera e grava o que muda. O
    `iniciar planejamento` o roda depois de copiar o modelo; o perfil que não vale sobe com a `PerfilInvalido`.
    Devolve as recusas do `harness.yml`, que o chamador mostra. Com `com_ci` falso, o `harness.yml` fica de fora: não
    se grava e não há recusa dele, porque quem chama já tratou esse arquivo."""
    textos, achados, recusas = textos_e_problemas(raiz, carregar_perfil(raiz), executar)
    if not com_ci:
        textos = {caminho: texto for caminho, texto in textos.items() if caminho != ci.CAMINHO}
        achados = [(problema, caminho) for problema, caminho in achados if caminho != ci.CAMINHO]
        recusas = ()
    gravar(raiz, textos, achados)
    return recusas


def _contagem(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def linhas_da_gravacao(textos: dict[str, str], problemas_: list[tuple[str, str]]) -> list[str]:
    """A saída do `gerar`: `gravado:` e `removido:` por arquivo, na ordem dos problemas, e a linha das contagens."""
    removidos = sum(1 for problema, _ in problemas_ if problema == ORFAO)
    linhas = [f"{'removido' if problema == ORFAO else 'gravado'}: {caminho}" for problema, caminho in problemas_]
    linhas.append(f"{_contagem(len(textos), 'arquivo gerado', 'arquivos gerados')}, "
                  f"{_contagem(len(problemas_) - removidos, 'mudou', 'mudaram')}, "
                  f"{_contagem(removidos, 'removido', 'removidos')}")
    return linhas


def linhas_do_check(textos: dict[str, str], problemas_: list[tuple[str, str]]) -> list[str]:
    """A saída do `gerar --check`: em dia, a contagem; senão, um `<problema>: <caminho>` por problema e o comando."""
    if not problemas_:
        return [f"gerados em dia: {_contagem(len(textos), 'arquivo', 'arquivos')}"]
    return [f"{problema}: {caminho}" for problema, caminho in problemas_] + ["rode harness.py gerar"]
