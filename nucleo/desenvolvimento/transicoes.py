"""Comandos do bloco (spec 6c, §14): cada um confere a transição e o passo, grava o `estado.md`, faz o commit e regrava
o `LANES.md`.

Todos rodam dentro da lane do bloco, achada pelos arquivos. O commit leva só os arquivos do passo, e o resto do índice
fica como estava; quando ele é recusado, os arquivos que o harness gravou no passo voltam ao último commit. A transição
que o comando gravou sai também como aviso ao Linear na `Saida.avisos` (spec 6d-repositorio, §9.5), que quem imprime a
saída envia.
"""
from __future__ import annotations

import dataclasses
import datetime
import posixpath
import re
import shutil
import subprocess
from pathlib import Path

import aceitacao
import bloco
import campos
import comum
import contexto
import fichas
import importacao
import lanes
import verificacao
from bloco import Aviso, EstadoDoBloco, LaneViva, Recusa, Saida

AJUDA = """\
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
| `desbloquear [--replanejar \\| --seguir <ficha>]` | `blocked` → pela causa | a opção que a causa pede |
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

  O `--curto` grava `caminho: curto`. O hash da `spec.md` troca `\\r\\n` por `\\n`. Grava o `efeito_externo`: `não`
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
"""

# Verbo: os estados de origem e o de destino; o `desbloquear` vai pela causa.
VERBOS: dict[str, tuple[tuple[str, ...], str | None]] = {
    "planejado": (("planning",), "ready_for_execution"),
    "executando": (("ready_for_execution",), "executing"),
    "executado": (("executing",), "ready_for_review"),
    "revisando": (("ready_for_review",), "reviewing"),
    "revisado": (("reviewing",), "ready_for_closure"),
    "corrigir": (("reviewing", "closing"), "executing"),
    "finalizar": (("ready_for_closure",), "closing"),
    "bloquear": (bloco.ESTADOS[:6], "blocked"),
    "desbloquear": (("blocked",), None),
    "replanejar": (("ready_for_execution", "executing", "ready_for_review", "reviewing", "ready_for_closure"),
                   "planning"),
}
RULINGS = "rulings.md"
PLANO = "plano.md"
PASTA_DO_SDD = ".superpowers/sdd"
SECAO_EM_ABERTO = "## Em aberto"
# Os arquivos do plano descartado, que a volta a `planning` tira do bloco (spec 6d-bloco, §8.2).
TIRADOS_NO_REPLANEJAR = (PLANO, aceitacao.ARQUIVO, RULINGS, bloco.ARQUIVO_DA_REVISAO, bloco.ARQUIVO_DO_GABARITO)

_RE_TITULO = re.compile(r"#{1,6} ")
_RE_TAREFA_FEITA = re.compile(r"^[ \t]*(?:[-*+][ \t]+)?Task ([0-9]+): complete\b", re.M)
_RE_MARCADOR = re.compile(r"^[-*+]\s+")
_RE_ITEM = re.compile(r"(?:[-*+]|[0-9]+[.)])\s+\S")
_RE_COMENTARIO = re.compile(r"<!--.*?-->", re.S)


def da_lane(raiz: Path, perfil) -> LaneViva:
    """A lane da raiz, pelos arquivos; fora de lane, a recusa."""
    lane = bloco.lane_pelos_arquivos(raiz, perfil)
    if lane is None:
        raise Recusa("fora de lane: rode dentro da lane do bloco")
    return lane


def _transicao(lane: LaneViva, verbo: str) -> str | None:
    """A linha da repetição, no estado de destino, ou None; a transição fora de ordem recusa."""
    origens, destino = VERBOS[verbo]
    bloco_ = lane.bloco
    if destino is not None and bloco_.estado == destino:
        return f"{bloco_.id} já está em {bloco_.estado}"
    if verbo in ("bloquear", "replanejar") and bloco_.estado == "closing":
        raise Recusa(f"bloco {verbo}: {bloco_.id} está em closing; rode harness.py bloco corrigir antes")
    if verbo == "replanejar" and bloco_.estado == "blocked":
        raise Recusa(f"bloco replanejar: {bloco_.id} está em blocked; rode harness.py bloco desbloquear")
    if bloco_.estado not in origens:
        raise Recusa(f"{bloco_.id} está em {bloco_.estado}; bloco {verbo} vale só em {comum.juntar(origens)}")
    return None


def mudar(bloco_: EstadoDoBloco, estado: str, agora, **trocas) -> EstadoDoBloco:
    """O bloco no estado novo, com o anterior igual ao de agora e o `atualizado_em`; fora de `blocked`, o `bloqueio` e
    o `motivo` voltam a `—`. As trocas vêm por último."""
    limpos = {} if estado == "blocked" else {"bloqueio": bloco.SEM, "motivo": bloco.SEM}
    return dataclasses.replace(bloco_, estado=estado, estado_anterior=bloco_.estado,
                               atualizado_em=agora().strftime("%Y-%m-%dT%H:%M"), **{**limpos, **trocas})


def pasta_do_bloco(perfil, bloco_: EstadoDoBloco) -> str:
    """A pasta do bloco relativa à raiz: `<blocos>/<id>-<slug>`."""
    return f"{perfil.caminhos.blocos}/{bloco_.pasta}"


def gravar_transicao(raiz: Path, perfil, lane: LaneViva, novo: EstadoDoBloco, caminhos: list[str],
                     do_harness: list[str], executar=subprocess.run, agora=datetime.datetime.now,
                     mensagem: str | None = None, corpo: str | None = None) -> tuple[str, ...]:
    """Grava o `estado.md`, faz o commit (por padrão, `chore(<ID>): <estado novo>`) com ele e os caminhos, e regrava o
    `LANES.md`. Devolve `<ID>: <de> → <para>` e, quando o `LANES.md` falhou, a linha dele."""
    estado_md = f"{pasta_do_bloco(perfil, novo)}/{bloco.ARQUIVO}"
    comum.escrever_texto(Path(raiz) / estado_md, bloco.para_texto(novo))
    bloco.commitar(raiz, [*caminhos, estado_md], mensagem or f"chore({novo.id}): {novo.estado}",
                   [estado_md, *do_harness], executar, corpo)
    falha = lanes.linha_do_regravar(raiz, perfil, executar, agora)
    return (f"{novo.id}: {lane.bloco.estado} → {novo.estado}", *([falha] if falha else []))


def aviso(raiz: Path, lane: LaneViva, novo: EstadoDoBloco, pr: str = "") -> Aviso:
    """O aviso ao Linear da transição da `lane` ao bloco `novo`, gravada com commit na árvore `raiz`; o `pr` é o link do
    PR, quando há (spec 6d-repositorio, §9.5)."""
    return Aviso(id=novo.id, de=lane.bloco.estado, para=novo.estado, arvore=str(raiz), bloco=novo, pr=pr)


def avisos(raiz: Path, perfil, lane: LaneViva, novo: EstadoDoBloco, pr: str = "") -> tuple[Aviso, ...]:
    """O `aviso` da transição, para a `Saida.avisos`; sem a `[desenvolvimento.linear]` no perfil, nenhum."""
    return (aviso(raiz, lane, novo, pr),) if perfil.linear is not None else ()


def _passo_simples(raiz: Path, perfil, verbo: str, executar, agora, conferir=None) -> Saida:
    """A transição sem artefato: a lane, a repetição, a transição, o `conferir(lane)` e o `estado.md`."""
    lane = da_lane(raiz, perfil)
    repetido = _transicao(lane, verbo)
    if repetido is not None:
        return Saida((repetido,))
    if conferir is not None:
        conferir(lane)
    novo = mudar(lane.bloco, VERBOS[verbo][1], agora)
    return Saida(gravar_transicao(raiz, perfil, lane, novo, [], [], executar, agora),
                 avisos=avisos(raiz, perfil, lane, novo))


def lane_sem_alteracao(raiz: Path, executar=subprocess.run) -> bool:
    """O `git status --porcelain` vazio; os ignorados não contam."""
    feito = bloco.git(raiz, ["status", "--porcelain"], executar)
    if feito.returncode != 0:
        raise Recusa(f"git status falhou: {comum.motivo_do_git(feito, 'status')}")
    return not feito.stdout.strip()


LIMITE_DO_CURTO = 3

_RE_TAREFA = re.compile(r"### Task ([0-9]+):")
_RE_TITULO_ALTO = re.compile(r"#{1,2} ")
_RE_ARQUIVO_DO_PLANO = re.compile(r"\s*[-*+]\s+(?:Create|Modify|Test):")
_RE_PROVA = re.compile(r"Prova:\s*\S")
_RE_TRECHO_EM_CRASES = re.compile(r"`([^`]+)`")
_RE_ALVO_DE_LINK = re.compile(r"\]\(([^)]+)\)")


def tarefas_do_plano(texto: str) -> list[tuple[int, str]]:
    """O número e o texto da seção de cada `### Task <n>:` do plano, fora dos blocos de código. A seção vai do título
    até o próximo `### Task` ou até um título de nível 1 ou 2; o texto traz só as linhas de fora dos blocos."""
    tarefas: list[tuple[int, list[str]]] = []
    atual: list[str] | None = None
    for _, linha in campos.linhas_fora_de_blocos(texto):
        achada = _RE_TAREFA.match(linha)
        if achada:
            atual = [linha]
            tarefas.append((int(achada.group(1)), atual))
        elif _RE_TITULO_ALTO.match(linha):
            atual = None
        elif atual is not None:
            atual.append(linha)
    return [(numero, "\n".join(linhas)) for numero, linhas in tarefas]


def _aponta_para_a_spec(texto: str, alvo: str, pasta_do_plano: str) -> bool:
    """Se a linha `**Spec:**` do plano aponta para `alvo`: algum trecho entre crases, alvo de link, sem o `#<âncora>`,
    ou a primeira palavra do texto depois dos dois-pontos é o caminho, normalizado (`./` e `..` resolvidos), ou o dá
    resolvido a partir da pasta do plano."""
    linha = next((linha for _, linha in campos.linhas_fora_de_blocos(texto) if linha.startswith("**Spec:**")), None)
    if linha is None:
        return False
    resto = linha[len("**Spec:**"):]
    links = [link.split("#", 1)[0] for link in _RE_ALVO_DE_LINK.findall(resto)]
    candidatos = [c.strip() for c in (*_RE_TRECHO_EM_CRASES.findall(resto), *links, *resto.split()[:1])]
    return any(alvo in (posixpath.normpath(c), posixpath.normpath(posixpath.join(pasta_do_plano, c)))
               for c in candidatos if c)


def _conferir_plano(texto: str, perfil, bloco_: EstadoDoBloco) -> list[tuple[int, str]]:
    """As tarefas do plano, depois de conferir que há alguma, que cada uma tem a lista Files e que a linha `**Spec:**`
    aponta para a spec do bloco."""
    tarefas = tarefas_do_plano(texto)
    if not tarefas:
        raise Recusa("bloco planejado: plano sem ### Task N")
    for numero, secao in tarefas:
        if not any(_RE_ARQUIVO_DO_PLANO.match(linha) for linha in secao.splitlines()):
            raise Recusa(f"bloco planejado: Task {numero} sem a lista Files com Create, Modify ou Test")
    pasta = pasta_do_bloco(perfil, bloco_)
    if not _aponta_para_a_spec(texto, f"{pasta}/{bloco.ARQUIVO_DA_SPEC}", pasta):
        raise Recusa("bloco planejado: o plano não aponta para a spec do bloco na linha **Spec:**")
    return tarefas


def _conferir_curto(spec: str, perfil, bloco_: EstadoDoBloco, tarefas: list[tuple[int, str]]) -> None:
    """O que o `--curto` pede: a ficha do código, a linha `Prova:` na `## Causa` e no máximo `LIMITE_DO_CURTO`
    tarefas."""
    if not bloco_.id.startswith(f"{perfil.prefixo}-"):
        raise Recusa(f"bloco planejado: --curto vale só para ficha {perfil.prefixo}")
    causas = [linhas for _, titulo, linhas in campos.secoes(spec, "## Causa") if titulo == "## Causa"]
    if not any(_RE_PROVA.match(linha) for linhas in causas for _, linha in linhas[1:]):
        raise Recusa("bloco planejado: bloco curto sem ## Causa com a linha Prova:")
    if len(tarefas) > LIMITE_DO_CURTO:
        raise Recusa(f"bloco planejado: bloco curto com {len(tarefas)} tarefas; o limite é {LIMITE_DO_CURTO}; "
                     "replaneje como bloco normal")


def _conferir_lane_limpa(raiz: Path, pasta: str, executar) -> None:
    """A recusa da lane com entrada do `git status` fora da pasta do bloco; os ignorados não contam."""
    feito = bloco.git(raiz, ["status", "--porcelain", "-z", "--untracked-files=all"], executar)
    if feito.returncode != 0:
        raise Recusa(f"git status falhou: {comum.motivo_do_git(feito, 'status')}")
    fora = [caminho for caminho in bloco._mudados(feito.stdout) if not caminho.startswith(f"{pasta}/")]
    if fora:
        raise Recusa("bloco planejado: a lane tem alterações sem commit fora do bloco: "
                     f"{comum.juntar(fora[:5])}; o código muda só na execução")


def planejado(raiz: Path, perfil, curto: bool = False, executar=subprocess.run,
              agora=datetime.datetime.now) -> Saida:
    """De `planning`, confere os arquivos, a lane limpa, o plano e, com `curto`, a prova e o limite; grava o `caminho`
    e o hash da spec, que registram a aprovação (spec 6d-bloco, §8.1)."""
    lane = da_lane(raiz, perfil)
    repetido = _transicao(lane, "planejado")
    if repetido is not None:
        return Saida((repetido,))
    pasta = pasta_do_bloco(perfil, lane.bloco)
    for nome in (bloco.ARQUIVO_DA_SPEC, PLANO):
        if not (Path(raiz) / pasta / nome).is_file():
            raise Recusa(f"bloco planejado: falta {pasta}/{nome}")
    _conferir_lane_limpa(raiz, pasta, executar)
    spec_md = f"{pasta}/{bloco.ARQUIVO_DA_SPEC}"
    spec_texto = comum.ler_texto(Path(raiz) / spec_md)
    tarefas = _conferir_plano(comum.ler_texto(Path(raiz) / pasta / PLANO), perfil, lane.bloco)
    if curto:
        _conferir_curto(spec_texto, perfil, lane.bloco, tarefas)
    itens = aceitacao.itens_da_spec(spec_texto, perfil)
    aceitacao_md = f"{pasta}/{aceitacao.ARQUIVO}"
    comum.escrever_texto(Path(raiz) / aceitacao_md, aceitacao.para_texto(aceitacao.Tabela(lane.bloco.id, itens)))
    spec = bloco.hash_da_spec((Path(raiz) / spec_md).read_bytes())
    novo = mudar(lane.bloco, "ready_for_execution", agora, efeito_externo="sim" if itens else "não",
                 caminho="curto" if curto else "normal", spec=spec)
    notas = [f"{pasta}/{contexto.ARQUIVO}"]
    for nota in ["contexto-leitor.md", *sorted(p.name for p in (Path(raiz) / pasta).glob("pesquisa-*.md"))]:
        if (Path(raiz) / pasta / nota).is_file():
            notas.append(f"{pasta}/{nota}")
    caminhos = [spec_md, f"{pasta}/{PLANO}", aceitacao_md, *notas]
    return Saida(gravar_transicao(raiz, perfil, lane, novo, caminhos, [aceitacao_md], executar, agora),
                 avisos=avisos(raiz, perfil, lane, novo))


def executando(raiz: Path, perfil, executar=subprocess.run, agora=datetime.datetime.now) -> Saida:
    return _passo_simples(raiz, perfil, "executando", executar, agora)


def pasta_do_ledger(raiz: Path, plano: str) -> Path | None:
    """A pasta de `<raiz>/.superpowers/sdd/` cujo `plan-path`, sem os espaços das pontas, é o `plano` (relativo à
    raiz); a primeira na ordem dos nomes, ou None. A pasta de outro plano, ou sem o `plan-path`, não conta."""
    base = Path(raiz) / PASTA_DO_SDD
    if not base.is_dir():
        return None
    for pasta in sorted(p for p in base.iterdir() if p.is_dir()):
        try:
            if comum.ler_texto(pasta / "plan-path").strip() == plano:
                return pasta
        except (OSError, UnicodeDecodeError):
            continue
    return None


def ledger_do_plano(raiz: Path, plano: str) -> str | None:
    """O texto do `progress.md` da pasta do ledger do plano; None sem a pasta ou sem o arquivo legível."""
    pasta = pasta_do_ledger(raiz, plano)
    if pasta is None:
        return None
    try:
        return comum.ler_texto(pasta / "progress.md")
    except (OSError, UnicodeDecodeError):
        return None


def feitas(ledger: str) -> set[int]:
    """Os números das tarefas com a linha `Task <N>: complete` no ledger, com ou sem marcador de lista."""
    return {int(achada.group(1)) for achada in _RE_TAREFA_FEITA.finditer(ledger)}


def rulings(ledger: str) -> list[str]:
    """As linhas do ledger com `Ruling:`, sem o marcador de lista do começo e sem os espaços das pontas, na ordem."""
    return [_RE_MARCADOR.sub("", linha.strip(), count=1) for linha in ledger.splitlines() if "Ruling:" in linha]


def _tarefas_nao_feitas(numeros: list[int]) -> str:
    """A recusa do `executado` para as tarefas sem a linha de feita, no singular ou no plural."""
    if len(numeros) == 1:
        return f"não dá como feita a tarefa {numeros[0]}"
    return f"não dá como feitas as tarefas {' e '.join(str(n) for n in numeros)}"


def executado(raiz: Path, perfil, executar=subprocess.run, agora=datetime.datetime.now) -> Saida:
    """De `executing`, confere a lane sem alteração e o ledger do SDD do plano, com todas as tarefas feitas, e grava
    o `rulings.md` com as linhas `Ruling:` dele no commit da transição (spec 6d-bloco, §8.3)."""
    lane = da_lane(raiz, perfil)
    repetido = _transicao(lane, "executado")
    if repetido is not None:
        return Saida((repetido,))
    if not lane_sem_alteracao(raiz, executar):
        raise Recusa("bloco executado: a lane tem alterações sem commit")
    pasta = pasta_do_bloco(perfil, lane.bloco)
    plano = f"{pasta}/{PLANO}"
    ledger = ledger_do_plano(raiz, plano)
    if ledger is None:
        raise Recusa(f"bloco executado: falta o ledger do SDD do {PLANO}; "
                     f"rode o /{comum.PREFIXO_DAS_SKILLS}executar-bloco")
    if not (Path(raiz) / plano).is_file():
        raise Recusa(f"bloco executado: falta {plano}")
    feitas_no_ledger = feitas(ledger)
    abertas = [numero for numero, _ in tarefas_do_plano(comum.ler_texto(Path(raiz) / plano))
               if numero not in feitas_no_ledger]
    if abertas:
        raise Recusa(f"bloco executado: o ledger do SDD {_tarefas_nao_feitas(abertas)}")
    decisoes = rulings(ledger) or [f"Nenhuma decisão foi tomada em nome de {perfil.dono.nome}."]
    rulings_md = f"{pasta}/{RULINGS}"
    comum.escrever_texto(Path(raiz) / rulings_md, "\n".join(decisoes) + "\n")
    novo = mudar(lane.bloco, VERBOS["executado"][1], agora)
    return Saida(gravar_transicao(raiz, perfil, lane, novo, [rulings_md], [rulings_md], executar, agora),
                 avisos=avisos(raiz, perfil, lane, novo))


def revisando(raiz: Path, perfil, executar=subprocess.run, agora=datetime.datetime.now) -> Saida:
    return _passo_simples(raiz, perfil, "revisando", executar, agora)


def itens_em_aberto(texto: str) -> int | None:
    """Os itens da seção `## Em aberto` do `revisao.md`, ou None sem a seção: as linhas que começam, sem recuo, por um
    marcador de lista e um texto, até o próximo título, fora dos blocos de código e dos comentários."""
    trecho: list[str] | None = None
    for _, linha in campos.linhas_fora_de_blocos(texto):
        if _RE_TITULO.match(linha):
            if trecho is not None:
                break
            if linha.rstrip() == SECAO_EM_ABERTO:
                trecho = []
        elif trecho is not None:
            trecho.append(linha)
    if trecho is None:
        return None
    return sum(1 for linha in _RE_COMENTARIO.sub("", "\n".join(trecho)).split("\n") if _RE_ITEM.match(linha))


def revisado(raiz: Path, perfil, executar=subprocess.run, agora=datetime.datetime.now) -> Saida:
    lane = da_lane(raiz, perfil)
    repetido = _transicao(lane, "revisado")
    if repetido is not None:
        return Saida((repetido,))
    revisao_md = f"{pasta_do_bloco(perfil, lane.bloco)}/{bloco.ARQUIVO_DA_REVISAO}"
    arquivo = Path(raiz) / revisao_md
    abertos = itens_em_aberto(comum.ler_texto(arquivo)) if arquivo.is_file() else None
    if abertos is None:
        raise Recusa(f"bloco revisado: falta {bloco.ARQUIVO_DA_REVISAO} com a seção {SECAO_EM_ABERTO}")
    if abertos:
        itens = "1 item" if abertos == 1 else f"{abertos} itens"
        raise Recusa(f"bloco revisado: {bloco.ARQUIVO_DA_REVISAO} tem {itens} em {SECAO_EM_ABERTO}")
    novo = mudar(lane.bloco, "ready_for_closure", agora)
    return Saida(gravar_transicao(raiz, perfil, lane, novo, [revisao_md], [], executar, agora),
                 avisos=avisos(raiz, perfil, lane, novo))


def bloquear(raiz: Path, perfil, motivo: str, executar=subprocess.run, agora=datetime.datetime.now) -> Saida:
    lane = da_lane(raiz, perfil)
    repetido = _transicao(lane, "bloquear")
    if repetido is not None:
        return Saida((repetido,))
    motivo = " ".join(motivo.split())
    if motivo in ("", bloco.SEM):
        raise Recusa("bloco bloquear: o motivo não pode ficar vazio")
    novo = mudar(lane.bloco, "blocked", agora, bloqueio="manual", motivo=motivo)
    return Saida(gravar_transicao(raiz, perfil, lane, novo, [], [], executar, agora),
                 avisos=avisos(raiz, perfil, lane, novo))


def _sem_pr_mesclado(raiz: Path, perfil, lane: LaneViva, comando: str, executar) -> None:
    """Recusa o `comando` do bloco em `closing` cujo PR da branch já foi mesclado no ramo principal."""
    mesclado = next((pr for pr in importacao.prs_da_branch(raiz, lane.ramo, executar)
                     if pr.estado == "MERGED" and pr.base == perfil.ramo_principal), None)
    if mesclado is not None:
        raise Recusa(f"bloco {comando}: o PR #{mesclado.numero} já foi mesclado; rode harness.py lane fechar "
                     f"{lane.bloco.id} {bloco.ONDE_FECHAR_A_LANE}")


def corrigir(raiz: Path, perfil, executar=subprocess.run, agora=datetime.datetime.now) -> Saida:
    """De `reviewing`, ou de `closing` sem o PR mesclado no ramo principal, volta a `executing`; o commit leva o
    `revisao.md` quando ele mudou. De `reviewing`, encerra a revisão: antes do commit, o `gabarito.md` que o
    `revisao preparar` gravou sem commit volta ao último commit, e o que não tem commit sai do disco; depois, a marca
    da revisão em andamento se apaga."""
    lane = da_lane(raiz, perfil)
    repetido = _transicao(lane, "corrigir")
    if repetido is not None:
        return Saida((repetido,))
    if lane.bloco.estado == "closing":
        _sem_pr_mesclado(raiz, perfil, lane, "corrigir", executar)
    pasta = pasta_do_bloco(perfil, lane.bloco)
    da_revisao = lane.bloco.estado == "reviewing"
    gabarito_md = f"{pasta}/{bloco.ARQUIVO_DO_GABARITO}"
    if da_revisao and not bloco._voltar(raiz, [gabarito_md], executar):
        raise Recusa(f"bloco corrigir: {gabarito_md} não voltou ao último commit")
    novo = mudar(lane.bloco, "executing", agora)
    linhas = gravar_transicao(raiz, perfil, lane, novo, [f"{pasta}/{bloco.ARQUIVO_DA_REVISAO}"], [], executar, agora)
    if da_revisao:
        bloco.apagar_marca_da_revisao(raiz)
    return Saida(linhas, avisos=avisos(raiz, perfil, lane, novo))


def _objetivo(raiz: Path, perfil, id_: str) -> str:
    """Os itens do Objetivo da ficha, juntados por um espaço, ou `—` sem a ficha ou sem o campo."""
    try:
        ficha, _ = contexto.ficha_da_arvore(raiz, perfil, id_)
    except Recusa:
        return bloco.SEM
    return " ".join(fichas.campo(ficha, "Objetivo") or []) or bloco.SEM


def _corpo(raiz: Path, perfil, lane: LaneViva, tabela: aceitacao.Tabela, relatorio: verificacao.Relatorio) -> str:
    """O corpo do PR e do commit `closing`: o Objetivo da ficha, a tabela da aceitação e as linhas do `verificar`."""
    linhas_da_tabela = aceitacao.para_texto(tabela).rstrip("\n").split("\n")[2:]
    return "\n\n".join((f"## Objetivo\n{_objetivo(raiz, perfil, lane.bloco.id)}",
                        "## Aceitação\n" + "\n".join(linhas_da_tabela),
                        "## Verificações\n" + "\n".join(relatorio.linhas)))


def _conferir_finalizar(raiz: Path, perfil, lane: LaneViva, executar) -> str:
    """O que o `finalizar` pede, nesta ordem: a lane sem alteração, a passagem do ramo principal depois do fetch, as
    verificações do `finalizar` e, com efeito externo, a aceitação de antes do merge. Devolve o corpo."""
    if not lane_sem_alteracao(raiz, executar):
        raise Recusa("bloco finalizar: a lane tem alterações sem commit")
    importacao.buscar_principal(raiz, perfil, executar)
    novo = importacao.manifesto_do_principal(raiz, perfil, executar)
    if novo is not None:
        for afetado in importacao.afetados(raiz, novo, [lane], perfil, executar):
            motivo = bloco.motivo_da_passagem(novo.versao, [*afetado.mudaram, *afetado.sairam])
            raise Recusa(f"bloco finalizar: {motivo}; rode harness.py lane conferir")
    base = verificacao.base_da_arvore(raiz, perfil, lane, executar)
    relatorio = verificacao.verificar(raiz, perfil, verificacao.FINALIZAR, verificacao.mudados(raiz, base, executar))
    if relatorio.falhou:
        primeira = next(execucao for execucao in relatorio.execucoes if execucao.estado == verificacao.FALHOU)
        raise Recusa("\n".join((f"bloco finalizar: verificação {primeira.nome} falhou", *relatorio.detalhes)))
    tabela = aceitacao.Tabela(lane.bloco.id, ())
    if lane.bloco.efeito_externo == "sim":
        relativo = f"{pasta_do_bloco(perfil, lane.bloco)}/{aceitacao.ARQUIVO}"
        if not (Path(raiz) / relativo).is_file():
            raise Recusa(f"{relativo} não existe; o bloco planejado o gera")
        tabela = aceitacao.ler(comum.ler_texto(Path(raiz) / relativo), relativo)
        abertos = [str(numero) for numero in aceitacao.pendentes(tabela, False)]
        if abertos:
            itens = f"item {abertos[0]}" if len(abertos) == 1 else f"itens {comum.juntar(abertos)}"
            raise Recusa(f"bloco finalizar: aceitação pendente: {itens}")
    return _corpo(raiz, perfil, lane, tabela, relatorio)


def _corpo_do_closing(raiz: Path, id_: str, executar) -> str:
    """O corpo do último commit da lane de assunto `chore(<ID>): closing`."""
    assunto = f"chore({id_}): closing"
    feito = bloco.git(raiz, ["log", "--format=%H%x09%s"], executar)
    for linha in feito.stdout.decode("utf-8", errors="replace").splitlines():
        sha, _, titulo = linha.partition("\t")
        if titulo == assunto:
            corpo = bloco.git(raiz, ["log", "-1", "--format=%b", sha], executar)
            return corpo.stdout.decode("utf-8", errors="replace").rstrip("\n")
    raise Recusa(f"bloco finalizar: a lane não tem o commit {assunto}")


def _conferir_spec_aprovada(raiz: Path, perfil, bloco_: EstadoDoBloco) -> None:
    """A recusa da `spec.md` que não tem mais o hash que o `planejado` gravou; o `\\r\\n` conta como `\\n`."""
    arquivo = Path(raiz) / pasta_do_bloco(perfil, bloco_) / bloco.ARQUIVO_DA_SPEC
    if not arquivo.is_file() or bloco.hash_da_spec(arquivo.read_bytes()) != bloco_.spec:
        raise Recusa("bloco finalizar: spec.md mudou depois da aprovação; rode harness.py bloco replanejar")


def _de_novo(passo: str, motivo: str) -> str:
    return f"closing gravado, mas {passo} falhou: {motivo}; rode harness.py bloco finalizar de novo"


COMANDOS_DO_HARNESS = ("python3 .claude/harness/", "python .claude/harness/")


def aviso_da_instalacao(perfil) -> str | None:
    """A linha de aviso de quando o perfil não declara a instalação do CI e alguma verificação do `finalizar` roda um
    comando que não é do harness; sem as duas condições, None. Os nomes saem na ordem do perfil."""
    if perfil.ci_instalar:
        return None
    nomes = [item.nome for item in perfil.verificacoes
             if verificacao.FINALIZAR in item.momentos and not item.comando.startswith(COMANDOS_DO_HARNESS)]
    if not nomes:
        return None
    return f"aviso: [desenvolvimento.ci] instalar está vazio e {comum.juntar(nomes)} rodam no CI, que começa sem a stack"


def finalizar(raiz: Path, perfil, resumo: str | None = None, executar=subprocess.run,
              agora=datetime.datetime.now) -> Saida:
    """De `ready_for_closure`, confere, grava `closing` com o corpo no commit, empurra a branch e abre o PR, se ele
    falta; de `closing`, retoma a falha sem conferir de novo, com o corpo do commit `closing`.

    O aviso ao Linear (§9.5) sai da transição que gravou `closing`, com o link do PR quando o PR chegou a existir; a
    retomada avisa `closing → closing` só quando traz o link, que é o que o Linear ainda não sabe. Fora da retomada, a
    linha de `aviso_da_instalacao` vem depois das linhas da transição e fica fora do corpo do PR."""
    lane = da_lane(raiz, perfil)
    bloco_ = lane.bloco
    retomada = bloco_.estado == "closing"
    novo = bloco_
    if retomada:
        _sem_pr_mesclado(raiz, perfil, lane, "finalizar", executar)
        linhas = [f"{bloco_.id} já está em closing; retomado"]
        corpo = _corpo_do_closing(raiz, bloco_.id, executar)
    else:
        _transicao(lane, "finalizar")
        _conferir_spec_aprovada(raiz, perfil, bloco_)
        corpo = _conferir_finalizar(raiz, perfil, lane, executar)
        novo = mudar(bloco_, "closing", agora)
        linhas = list(gravar_transicao(raiz, perfil, lane, novo, [], [], executar, agora, corpo=corpo))
        aviso = aviso_da_instalacao(perfil)
        if aviso is not None:
            linhas.append(aviso)

    def avisos_com(pr: str = "") -> tuple[Aviso, ...]:
        return () if retomada and not pr else avisos(raiz, perfil, lane, novo, pr)

    _, motivo = importacao.falha(["git", "-C", str(raiz), "push", "-u", "origin", lane.ramo], "push", executar,
                                 importacao.TEMPO_LIMITE_REDE)
    if motivo is not None:
        return Saida((*linhas, _de_novo("git push", motivo)), True, avisos_com())
    linhas.append(f"branch {lane.ramo} enviada ao origin")
    try:
        prs = importacao.prs_da_branch(raiz, lane.ramo, executar)
    except Recusa as erro:
        return Saida((*linhas, f"closing gravado, mas {erro.mensagem}; rode harness.py bloco finalizar de novo"), True,
                     avisos_com())
    aberto = next((pr for pr in prs if pr.estado == "OPEN"), None)
    if aberto is not None:
        return Saida((*linhas, f"PR #{aberto.numero} já aberto: {aberto.url}"), avisos=avisos_com(aberto.url))
    resumo = " ".join((resumo or "").split()) or bloco_.slug.replace("-", " ")
    titulo = f"{lane.ramo.split('/', 1)[0]}({bloco_.id}): {resumo}"
    feito, motivo = importacao.falha(["gh", "pr", "create", "--base", perfil.ramo_principal, "--head", lane.ramo,
                                      "--title", titulo, "--body", corpo, "--assignee", perfil.dono.github],
                                     "pr create", executar, importacao.TEMPO_LIMITE_GH, raiz)
    if motivo is not None:
        return Saida((*linhas, _de_novo("gh pr create", motivo)), True, avisos_com())
    endereco = (feito.stdout.decode("utf-8", errors="replace").strip().splitlines() or [""])[-1]
    achado = re.search(r"/pull/([0-9]+)", endereco)
    return Saida((*linhas, f"PR #{achado.group(1)} aberto: {endereco}" if achado else f"PR aberto: {endereco}"),
                 avisos=avisos_com(endereco))


def _versao_da_copia(raiz: Path, perfil) -> int | None:
    copia = fichas.ler_manifesto(raiz, perfil)
    return None if copia is None else copia.versao


def _voltar_a_planning(raiz: Path, perfil, lane: LaneViva, novo: EstadoDoBloco, executar, agora,
                       mensagem: str | None = None) -> Saida:
    """Grava o bloco `novo`, em `planning`, com o `contexto.md` regravado e, no mesmo commit, sem os
    TIRADOS_NO_REPLANEJAR que existem; depois do commit, apaga o ledger do SDD do plano e a marca da revisão em
    andamento (spec 6d-bloco, §8.2). Com o commit recusado, os tirados voltam como estavam, e o ledger fica. O ledger
    que não se apaga depois do commit dá a linha `planning gravado, mas ...` no fim, com a saída 1."""
    pasta = pasta_do_bloco(perfil, lane.bloco)
    ficha, copia = contexto.ficha_da_arvore(raiz, perfil, lane.bloco.id)
    contexto_md = f"{pasta}/{contexto.ARQUIVO}"
    comum.escrever_texto(Path(raiz) / contexto_md, contexto.montar(raiz, perfil, ficha, copia).texto)
    tirados: dict[str, bytes] = {}
    for nome in TIRADOS_NO_REPLANEJAR:
        arquivo = Path(raiz) / pasta / nome
        if arquivo.is_file():
            tirados[nome] = arquivo.read_bytes()
            arquivo.unlink()
    caminhos = [contexto_md, *(f"{pasta}/{nome}" for nome in tirados)]
    try:
        linhas = gravar_transicao(raiz, perfil, lane, novo, caminhos, caminhos, executar, agora, mensagem)
    except Recusa:
        for nome, dados in tirados.items():
            (Path(raiz) / pasta / nome).write_bytes(dados)
        raise
    detalhes = [f"  tirados do bloco: {comum.juntar(list(tirados))}"] if tirados else []
    falha = []
    ledger = pasta_do_ledger(raiz, f"{pasta}/{PLANO}")
    if ledger is not None:
        relativo = ledger.relative_to(Path(raiz)).as_posix()
        try:
            shutil.rmtree(ledger)
        except OSError as erro:
            falha.append(f"planning gravado, mas apagar o ledger do SDD {relativo} falhou: "
                         f"{comum.motivo_do_sistema(erro)}; "
                         f"apague a pasta antes do /{comum.PREFIXO_DAS_SKILLS}executar-bloco")
        else:
            detalhes.append(f"  ledger do SDD apagado: {relativo}")
    bloco.apagar_marca_da_revisao(raiz)
    return Saida((linhas[0], *detalhes, *linhas[1:], *falha), bool(falha), avisos(raiz, perfil, lane, novo))


def replanejar(raiz: Path, perfil, motivo: str, executar=subprocess.run, agora=datetime.datetime.now) -> Saida:
    """Volta o bloco a `planning` e descarta a aprovação da spec, no commit `chore(<ID>): replaneja: <motivo>`, sem o
    plano, a aceitação, os rulings, a revisão e o gabarito, e apaga o ledger do SDD do plano (spec 6d-bloco, §8.2)."""
    lane = da_lane(raiz, perfil)
    repetido = _transicao(lane, "replanejar")
    if repetido is not None:
        return Saida((repetido,))
    motivo = " ".join(motivo.split())
    if motivo in ("", bloco.SEM):
        raise Recusa("bloco replanejar: o motivo não pode ficar vazio")
    novo = mudar(lane.bloco, "planning", agora, efeito_externo=bloco.SEM, caminho=bloco.SEM, spec=bloco.SEM)
    return _voltar_a_planning(raiz, perfil, lane, novo, executar, agora,
                              f"chore({lane.bloco.id}): replaneja: {motivo}")


def _replanejar(raiz: Path, perfil, lane: LaneViva, versao: int, executar, agora) -> Saida:
    """Vai a `planning`, com a `passagem` da cópia da lane e o `efeito_externo`, o `caminho` e a `spec` em `—`, pelo
    `_voltar_a_planning`, que tira do bloco os arquivos do plano descartado (spec 6d-bloco, §3, item 27)."""
    novo = mudar(lane.bloco, "planning", agora, passagem=versao, efeito_externo=bloco.SEM, caminho=bloco.SEM,
                 spec=bloco.SEM)
    return _voltar_a_planning(raiz, perfil, lane, novo, executar, agora)


def _seguir(raiz: Path, perfil, lane: LaneViva, ficha_id: str, executar, agora) -> Saida:
    """Volta ao estado anterior e grava na `passagem` a versão do motivo, com a diferença na ficha do código dada."""
    prefixo, ramo = perfil.prefixo, perfil.ramo_principal
    if not re.fullmatch(rf"{re.escape(prefixo)}-[0-9]{{2,}}", ficha_id):
        raise Recusa(f"bloco desbloquear: --seguir pede uma ficha {prefixo}-NN")
    da_lane = next((ficha for ficha in fichas.do_backlog(raiz, perfil) if ficha.id == ficha_id), None)
    if da_lane is None and all(ficha.id != ficha_id for ficha in fichas.do_principal(raiz, perfil, executar)):
        raise Recusa(f"bloco desbloquear: {ficha_id} não existe na lane nem no {ramo}")
    versao = bloco.versao_do_motivo(lane.bloco.motivo)
    if versao is None:
        raise Recusa(f"bloco desbloquear: motivo fora da forma passagem/vN mudou <IDs>: {lane.bloco.motivo}")
    anterior = lane.bloco.estado_anterior
    novo = dataclasses.replace(mudar(lane.bloco, anterior, agora), passagem=versao)
    caminhos = [] if da_lane is None else [da_lane.arquivo]
    return Saida(gravar_transicao(raiz, perfil, lane, novo, caminhos, [], executar, agora,
                                  corpo=f"A diferença da passagem/v{versao} segue na {ficha_id}."),
                 avisos=avisos(raiz, perfil, lane, novo))


def desbloquear(raiz: Path, perfil, replanejar: bool = False, seguir: str | None = None, executar=subprocess.run,
                agora=datetime.datetime.now) -> Saida:
    """Destrava o bloco pela causa do bloqueio (spec 6c, §14): `manual` volta ao estado anterior; `passagem` replaneja,
    com a lane na versão do ramo principal, ou segue na versão antiga; `retorno` replaneja, com a lane numa versão
    mais nova que a do bloco."""
    lane = da_lane(raiz, perfil)
    _transicao(lane, "desbloquear")
    bloco_ = lane.bloco
    ramo = perfil.ramo_principal
    if bloco_.bloqueio == "manual":
        if replanejar or seguir is not None:
            raise Recusa("bloco desbloquear: bloqueio por manual; use bloco desbloquear sem opção")
        novo = mudar(bloco_, bloco_.estado_anterior, agora)
        return Saida(gravar_transicao(raiz, perfil, lane, novo, [], [], executar, agora),
                     avisos=avisos(raiz, perfil, lane, novo))
    copia = _versao_da_copia(raiz, perfil)
    if bloco_.bloqueio == "passagem":
        if seguir is not None:
            return _seguir(raiz, perfil, lane, seguir, executar, agora)
        if not replanejar:
            raise Recusa("bloco desbloquear: bloqueio por passagem; use --replanejar ou --seguir "
                         f"<ficha {perfil.prefixo}>")
        do_principal = importacao.manifesto_do_principal(raiz, perfil, executar)
        if copia is None or do_principal is None or copia != do_principal.versao:
            raise Recusa(f"bloco desbloquear: traga o {ramo} para a lane antes de replanejar")
        return _replanejar(raiz, perfil, lane, copia, executar, agora)
    if not replanejar:
        raise Recusa("bloco desbloquear: bloqueio por retorno; use --replanejar")
    if copia is None or copia <= bloco_.passagem:
        versao = bloco_.passagem if copia is None else copia
        raise Recusa(f"bloco desbloquear: a lane ainda está na passagem/v{versao}; "
                     f"traga o {ramo} com a versão que resolve o retorno")
    return _replanejar(raiz, perfil, lane, copia, executar, agora)


def status(raiz: Path, perfil, para: str | None = None, executar=subprocess.run,
           agora=datetime.datetime.now) -> list[str]:
    """As linhas do `bloco status` (spec 6d-bloco, §8.5): na lane, `<ID> <estado> (<caminho>) · lane <k> · passagem
    v<N> · spec <12 primeiros ou "sem aprovação"> · próximo: <ação>`, com ` · revisão em andamento desde <hh:mm>`
    quando há a marca; com `para` e o estado fora dos dessa skill, a linha seguinte o diz. Fora de lane,
    `fora de lane: <a linha Lanes do hook>`."""
    lane = bloco.lane_pelos_arquivos(Path(raiz), perfil)
    if lane is None:
        quadro = lanes.montar(raiz, perfil, executar)
        prontas, urgentes = lanes.prontas_e_urgentes(quadro.principal, perfil)
        return [f"fora de lane: {lanes.linha_das_lanes(quadro, perfil, prontas, urgentes)}"]
    bloco_ = lane.bloco
    desde = bloco.marca_da_revisao(lane.pasta, agora())
    spec = bloco_.spec[:12] if bloco_.spec != bloco.SEM else "sem aprovação"
    linha = (f"{bloco_.id} {bloco_.estado} ({bloco_.caminho}) · lane {bloco_.lane} · passagem v{bloco_.passagem} · "
             f"spec {spec} · próximo: {bloco.proxima_acao(bloco_, desde)}")
    if desde is not None:
        linha += f" · revisão em andamento desde {desde.strftime('%H:%M')}"
    linhas = [linha]
    if bloco_.estado == "blocked" and para is not None:
        linhas.append("este bloco está em blocked; o dono decide com harness.py bloco desbloquear")
    elif para is not None and bloco.SKILL_DO_ESTADO[bloco_.estado] != para:
        linhas.append(f"este bloco está em {bloco_.estado}; "
                      f"a skill para ele é /{comum.PREFIXO_DAS_SKILLS}{bloco.SKILL_DO_ESTADO[bloco_.estado]}")
    return linhas
