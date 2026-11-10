"""Quadro das lanes (spec 6c, §17): o `LANES.md` da árvore principal, fora do git, e o resumo do início de sessão, sem
rede.

A fonte é o `git worktree list --porcelain` e o `estado.md` do bloco da branch de cada worktree dentro de
`lane.pasta`. As atenções são as do `lane conferir` que não pedem rede e a do bloco afetado pela versão da passagem no
`origin/<ramo_principal>`, calculada sem fetch; nenhuma derruba o quadro.
"""
from __future__ import annotations

import datetime
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import bloco
import comum
import fichas
import importacao
import manifesto
from bloco import LaneViva, Recusa

AJUDA = """\
Imprime o quadro das lanes e o regrava no `LANES.md` da raiz da árvore principal, também quando roda numa lane. O
arquivo fica fora do git: o comando põe `/LANES.md` no `info/exclude` do diretório do git da árvore principal quando a
linha falta, e a guarda nega a edição dele. A fonte é o `git worktree list --porcelain` e o `estado.md` do bloco da
branch de cada worktree dentro de `lane.pasta`; o comando não consulta a rede.

A tabela tem uma linha por lane viva, na ordem das fichas (as FICHA e depois as do prefixo, pelo número), com as
colunas Bloco, Estado, Branch, Worktree (relativa à árvore principal), Portas (`lane <k>: <nome> <porta>`, na ordem do
perfil) e Nota (o motivo do bloco em `blocked`, com o `|` escrito `\\|`, ou `—`). Sem lanes, a tabela vira
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
"""

ARQUIVO = "LANES.md"
_RE_PASTA = re.compile(r"([A-Z]{2,}-[0-9]{2,})-[a-z0-9]+(?:-[a-z0-9]+)*")
_FORA_DOS_AFETADOS = ("blocked", "closing")


@dataclass(frozen=True)
class QuadroDasLanes:
    principal: Path  # a árvore principal, na grafia do git
    lanes: tuple[LaneViva, ...]  # na ordem das fichas
    worktrees: tuple[str, ...]  # as atenções das worktrees e das branches de bloco sem worktree
    afetadas: tuple[str, ...]  # as atenções de passagem
    versao: int | None  # a da cópia no origin/<ramo_principal>
    invalidas: tuple[Path, ...] = ()  # as worktrees cujo estado.md da branch não se lê

    @property
    def atencoes(self) -> tuple[str, ...]:
        return self.worktrees + self.afetadas


def _ordem(id_: str) -> tuple[bool, int]:
    """As FICHA e depois as do prefixo, cada grupo pelo número."""
    return id_.split("-", 1)[0] != fichas.PREFIXO_DA_PASSAGEM, fichas.numero(id_)


def _relativo(caminho: Path, base: Path) -> str:
    """O caminho relativo à base. O git escreve a árvore principal com o caminho resolvido, e a sessão pode chegar por
    um link (no macOS, o `/var` é um link para o `/private/var`): quando o relativo direto falha, compara os dois
    resolvidos; fora da base também resolvida, o caminho absoluto."""
    try:
        return caminho.relative_to(base).as_posix()
    except ValueError:
        pass
    try:
        return caminho.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return caminho.as_posix()


def _branches_sem_worktree(raiz: Path, executar) -> list[str]:
    """As branches de bloco sem worktree, na ordem do nome."""
    feito = bloco.git(raiz, ["for-each-ref", "--format=%(refname) %(worktreepath)", "refs/heads"], executar)
    if feito.returncode != 0:
        raise Recusa(f"git for-each-ref falhou: {comum.motivo_do_git(feito, 'for-each-ref')}")
    soltas = []
    for linha in feito.stdout.decode("utf-8", errors="replace").splitlines():
        ref, _, pasta = linha.partition(" ")
        ramo = ref[len("refs/heads/"):]
        if not pasta and bloco.branch_de_bloco(ramo):
            soltas.append(ramo)
    return sorted(soltas)


def montar(raiz: Path, perfil, executar=subprocess.run) -> QuadroDasLanes:
    """O quadro do repositório da raiz, sem rede."""
    principal, worktrees = bloco.worktrees_de_lane(raiz, perfil, executar)
    lanes = []
    atencoes = []
    invalidas = []
    for worktree in worktrees:
        relativo = _relativo(worktree.pasta, principal)
        if worktree.sumida:
            achado = _RE_PASTA.fullmatch(worktree.pasta.name)
            if achado:
                id_ = achado.group(1)
                atencoes.append(f"{id_}: a pasta da lane sumiu; rode harness.py lane fechar {id_} --abandonar")
            continue
        try:
            estado = None if worktree.ramo is None else bloco.bloco_da_worktree(worktree.pasta, worktree.ramo, perfil,
                                                                                principal)
        except Recusa as erro:
            atencoes.append(erro.mensagem)
            invalidas.append(worktree.pasta)
            continue
        except (UnicodeDecodeError, OSError) as erro:
            atencoes.append(bloco.linha_do_ilegivel(worktree.pasta, worktree.ramo, perfil, principal, erro))
            invalidas.append(worktree.pasta)
            continue
        if estado is None:
            atencoes.append(f"{relativo}: worktree sem bloco")
        else:
            lanes.append(LaneViva(worktree.pasta, worktree.ramo, estado))
    atencoes += [f"{ramo}: branch sem worktree; recrie a worktree ou apague a branch"
                 for ramo in _branches_sem_worktree(raiz, executar)]
    lanes.sort(key=lambda lane: _ordem(lane.bloco.id))
    novo = importacao.manifesto_do_principal(raiz, perfil, executar)
    afetadas = []
    if novo is not None:
        for lane in lanes:
            if lane.bloco.estado in _FORA_DOS_AFETADOS:
                continue
            try:
                if importacao.afetados(raiz, novo, [lane], perfil, executar):
                    afetadas.append(f"{lane.bloco.id}: a lane está na {manifesto.PREFIXO_TAG}{lane.bloco.passagem}, e "
                                    f"o {perfil.ramo_principal} na v{novo.versao}; rode harness.py lane conferir")
            except Recusa as erro:
                afetadas.append(erro.mensagem)
    return QuadroDasLanes(principal, tuple(lanes), tuple(atencoes), tuple(afetadas),
                          None if novo is None else novo.versao, tuple(invalidas))


def _versao(quadro: QuadroDasLanes) -> str:
    return "nenhuma" if quadro.versao is None else f"v{quadro.versao}"


def portas(perfil, numero: int) -> str:
    """`lane <k>: <nome> <porta>, ...`, com as portas na ordem do perfil; sem portas no perfil, só `lane <k>`."""
    if not perfil.lane.portas:
        return f"lane {numero}"
    return f"lane {numero}: " + ", ".join(f"{nome} {perfil.lane.porta(nome, numero)}" for nome, _ in perfil.lane.portas)


def texto(quadro: QuadroDasLanes, perfil, agora: datetime.datetime) -> str:
    """O `LANES.md` (spec 6c, Anexo B.4)."""
    linhas = ["# Lanes ativas", "",
              f"Gerado por harness.py lanes em {agora.strftime('%Y-%m-%d %H:%M')}. Não edite: a fonte é o estado.md de "
              "cada lane.", ""]
    if quadro.lanes:
        linhas += ["| Bloco | Estado | Branch | Worktree | Portas | Nota |", "|---|---|---|---|---|---|"]
        for lane in quadro.lanes:
            b = lane.bloco
            nota = b.motivo.replace("|", "\\|") if b.estado == "blocked" else bloco.SEM
            linhas.append(f"| {b.id} | {b.estado} | {lane.ramo} | {_relativo(lane.pasta, quadro.principal)} | "
                          f"{portas(perfil, b.lane)} | {nota} |")
    else:
        linhas.append("Nenhuma lane viva.")
    linhas += ["", f"Lanes: {len(quadro.lanes)} de {perfil.lane.limite}. Passagem no {perfil.ramo_principal}: "
                   f"{_versao(quadro)}."]
    linhas += [f"Atenção: {linha}." for linha in quadro.atencoes]
    return "\n".join(linhas) + "\n"


def _excluir(principal: Path) -> None:
    """Põe `/LANES.md` no `info/exclude` do diretório comum do git da árvore principal, quando falta, com uma quebra
    antes se o arquivo não termina em quebra; o arquivo ausente é criado."""
    diretorio = comum.diretorio_comum(principal)
    if diretorio is None:
        return
    exclude = diretorio / "info" / "exclude"
    try:
        atual = comum.ler_texto(exclude)
    except FileNotFoundError:
        atual = ""
    if f"/{ARQUIVO}" in atual.splitlines():
        return
    if atual and not atual.endswith("\n"):
        atual += "\n"
    comum.escrever_texto(exclude, f"{atual}/{ARQUIVO}\n")


def regravar(raiz: Path, perfil, executar=subprocess.run, agora=datetime.datetime.now) -> QuadroDasLanes:
    """O `montar`, o `LANES.md` na árvore principal e o `info/exclude`."""
    quadro = montar(raiz, perfil, executar)
    comum.escrever_texto(quadro.principal / ARQUIVO, texto(quadro, perfil, agora()))
    _excluir(quadro.principal)
    return quadro


def linha_do_regravar(raiz: Path, perfil, executar=subprocess.run, agora=datetime.datetime.now) -> str | None:
    """O `regravar` dos comandos de bloco e de lane, que não os derruba: a linha `LANES.md não regravado: <motivo>`,
    ou None."""
    try:
        regravar(raiz, perfil, executar, agora)
    except Recusa as erro:
        motivo = erro.mensagem
    except (UnicodeDecodeError, OSError) as erro:
        motivo = bloco.motivo_da_leitura(erro)
    else:
        return None
    return f"{ARQUIVO} não regravado: {motivo}"


def prontas_e_urgentes(principal: Path, perfil) -> tuple[int | None, int]:
    """As fichas prontas da árvore principal e quantas delas são urgentes; quando o `fichas` recusa, ou não lê um
    arquivo, `(None, 0)`."""
    try:
        quadro = fichas.quadro(principal, perfil)
    except (Recusa, UnicodeDecodeError, OSError):
        return None, 0
    ids = [id_ for id_, situacao in fichas.listar(quadro, perfil) if situacao == "pronta"]
    return len(ids), len(fichas.urgentes(quadro, perfil).intersection(ids))


def linha_das_lanes(quadro: QuadroDasLanes, perfil, prontas: int | None, urgentes: int = 0) -> str:
    """A linha `Lanes:` do hook; `prontas` None, quando o `fichas` recusa, sai `—`; as `urgentes`, acima de 0, entram
    depois das prontas: `(1 urgente)` ou `(<n> urgentes)` (spec 6d-bloco, §10)."""
    marca = ""
    if prontas is not None and urgentes > 0:
        marca = " (1 urgente)" if urgentes == 1 else f" ({urgentes} urgentes)"
    return (f"Lanes: {len(quadro.lanes)} de {perfil.lane.limite} · passagem no {perfil.ramo_principal}: "
            f"{_versao(quadro)} · fichas prontas: {bloco.SEM if prontas is None else prontas}{marca}")


def _sessao(quadro: QuadroDasLanes, arvore: Path, lane: LaneViva | None) -> str:
    if lane is not None:
        return (f"Sessão: lane {lane.bloco.id} ({lane.bloco.estado}) em "
                f"{_relativo(lane.pasta, quadro.principal)}")
    if comum.mesma_arvore(arvore, quadro.principal):
        return "Sessão: árvore principal"
    if any(comum.mesma_arvore(arvore, pasta) for pasta in quadro.invalidas):
        return f"Sessão: lane {_relativo(Path(arvore), quadro.principal)} com estado.md inválido"
    return f"Sessão: worktree {Path(arvore).name}, fora das lanes"


def linhas_do_hook(quadro: QuadroDasLanes, perfil, arvore: Path, prontas: int | None, urgentes: int = 0,
                   compactado: bool = False, agora=datetime.datetime.now) -> list[str]:
    """As linhas do hook de início de sessão (spec 6c, §17 e spec 6d-bloco, §11 e §12, item 4): com `compactado`, a
    linha do contexto compactado vem primeiro; depois a `Sessão:`; na lane, a `Próximo: <ação>` do estado do bloco;
    depois a `Lanes:`, com as prontas e as urgentes, os blocos e as atenções."""
    lane = bloco.lane_da_arvore(arvore, list(quadro.lanes))
    linhas = ["Contexto compactado: retome pelo estado abaixo."] if compactado else []
    linhas.append(_sessao(quadro, arvore, lane))
    if lane is not None:
        desde = bloco.marca_da_revisao(lane.pasta, agora())
        linhas.append(f"Próximo: {bloco.proxima_acao(lane.bloco, desde, compactado)}")
    linhas.append(linha_das_lanes(quadro, perfil, prontas, urgentes))
    if quadro.lanes:
        linhas.append(" · ".join(f"{lane.bloco.id} {lane.bloco.estado}" for lane in quadro.lanes))
    return linhas + [f"Atenção: {linha}" for linha in quadro.atencoes]
