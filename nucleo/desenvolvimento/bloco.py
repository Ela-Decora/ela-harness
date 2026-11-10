"""Bloco do desenvolvimento (spec 6c, §9.2 e §9.4): o formato do `estado.md`, as lanes vivas e os blocos do ramo principal.

O `estado.md` são linhas `chave: valor` entre duas linhas `---`, sem YAML; o que vem depois da segunda fica fora da
leitura. Lane viva é a worktree dentro de `lane.pasta`, com branch, que não está `prunable` e tem um bloco cujo `ramo`
é a branch dela. A lane da árvore, a do Stop, do `verificar`, da `aceitacao` e do `contexto`, é reconhecida pelos
arquivos, sem rodar o git: o `.git` e o `HEAD` da worktree e o `estado.md` do bloco da branch,
`<blocos>/<último trecho da branch>/estado.md`, com as pastas comparadas por dispositivo e inode e sem ler as outras
lanes. Os blocos do ramo principal saem do `origin/<ramo_principal>`, sem
fetch. Em toda leitura, a pasta do bloco confere com o `<id>-<slug>` do `estado.md`. Aqui ficam também a `Recusa`, a
linha que os comandos do desenvolvimento imprimem antes de sair com 1, e o git que eles usam.
"""
from __future__ import annotations

import datetime
import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import comum

FORMATO = 1
ARQUIVO = "estado.md"
ARQUIVO_DA_ACEITACAO = "aceitacao.md"
# Os outros arquivos do bloco que mais de um módulo conhece pelo nome (spec 6d-bloco, §7 e §8).
ARQUIVO_DA_SPEC = "spec.md"
ARQUIVO_DA_REVISAO = "revisao.md"
ARQUIVO_DO_GABARITO = "gabarito.md"
SEM = "—"
ONDE_FECHAR_A_LANE = "de uma sessão aberta na árvore principal, ou pelo terminal como última ação"
TEMPO_LIMITE_GIT = 10
TEMPO_DO_COMMIT = 60
TIPOS = ("feat", "fix", "chore", "refactor", "infra", "cicd", "docs")
ESTADOS = ("planning", "ready_for_execution", "executing", "ready_for_review", "reviewing", "ready_for_closure",
           "closing", "blocked")
BLOQUEIOS = ("manual", "passagem", "retorno")
CAMINHOS = ("normal", "curto")
CHAVES = ("formato", "id", "slug", "estado", "estado_anterior", "bloqueio", "motivo", "efeito_externo", "caminho",
          "spec", "passagem", "ramo", "lane", "base", "retornos", "atualizado_em")

_RE_LINHA = re.compile(r"([a-z_]+): (.+)")
_RE_ID = re.compile(r"[A-Z]{2,}-[0-9]{2,}")
_RE_PASTA_DE_BLOCO = re.compile(r"[A-Z]{2,}-[0-9]{2,}-[a-z0-9]+(-[a-z0-9]+)*")
_RE_SLUG = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
_RE_PASSAGEM = re.compile(r"v([1-9][0-9]*)")
_RE_LANE = re.compile(r"[1-9]")
_RE_SPEC = re.compile(r"[0-9a-f]{64}")
_RE_BASE = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
_RE_RETORNO = re.compile(r"#([0-9]+) (fato|decisao)")
_RE_DATA_HORA = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}")


class Recusa(Exception):
    """A linha que o comando do desenvolvimento imprime como está, antes de sair com 1."""

    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


class BlocoInvalido(Recusa):
    """O `estado.md` fora do formato: `<caminho>: estado.md inválido: <motivo>`."""

    def __init__(self, caminho: str, motivo: str):
        super().__init__(f"{caminho}: estado.md inválido: {motivo}")
        self.caminho = caminho
        self.motivo = motivo


def git(raiz: Path, argumentos: list[str], executar=subprocess.run,
        tempo: int = TEMPO_LIMITE_GIT) -> subprocess.CompletedProcess:
    """O `git -C <raiz>`, com a saída em bytes; o git que não roda ou passa do tempo lança
    `Recusa("git indisponível: <motivo>")`."""
    try:
        return executar(["git", "-C", str(raiz), *argumentos], capture_output=True, timeout=tempo)
    except OSError as erro:
        raise Recusa(f"git indisponível: {comum.motivo_do_sistema(erro)}") from None
    except subprocess.TimeoutExpired:
        raise Recusa(f"git indisponível: passou de {tempo} s") from None
    except subprocess.SubprocessError as erro:
        raise Recusa(f"git indisponível: {type(erro).__name__}: {erro}") from None


@dataclass(frozen=True)
class Aviso:
    """A transição que o comando gravou e que o Linear deve saber (spec 6d-repositorio, §9.5): o ID da ficha, o estado
    de antes e o de depois, como vão no comentário, e a `arvore` onde o e-mail, o ramo e o commit se leem. O `bloco` é
    o novo, com o `atualizado_em` e o motivo; sem ele, vale a hora do envio. O `pr` é o link, quando há."""

    id: str
    de: str
    para: str
    arvore: str
    bloco: EstadoDoBloco | None = None
    pr: str = ""


@dataclass(frozen=True)
class Saida:
    """A volta dos comandos de bloco e de lane: as linhas que o comando imprime e, com `falhou`, a saída com 1.

    Os `avisos` são as transições que o comando gravou com commit, uma por ficha, e que o `harness._imprimir_saida`
    manda ao Linear depois das linhas; vazios sem a `[desenvolvimento.linear]` no perfil, e nunca mudam as linhas nem o
    código de saída."""

    linhas: tuple[str, ...]
    falhou: bool = False
    avisos: tuple[Aviso, ...] = ()


def _mudados(saida: bytes) -> list[str]:
    """Os caminhos do `git status --porcelain -z`: o texto de cada entrada depois de `XY `; com `R` ou `C` no `X`, a
    entrada seguinte, o nome antigo, não conta."""
    mudados = []
    entradas = iter(saida.decode("utf-8", errors="replace").split("\0"))
    for entrada in entradas:
        if len(entrada) < 4:
            continue
        mudados.append(entrada[3:])
        if entrada[0] in "RC":
            next(entradas, None)
    return mudados


def _voltar(raiz: Path, caminhos: list[str], executar) -> bool:
    """Volta cada caminho ao último commit: o que está no HEAD pelo `git restore --staged --worktree`; o novo sai do
    índice e do disco. Uma volta que falha dá False."""
    try:
        for caminho in caminhos:
            if git(raiz, ["cat-file", "-e", f"HEAD:{caminho}"], executar).returncode == 0:
                feito = git(raiz, ["restore", "--staged", "--worktree", "--", caminho], executar)
            else:
                feito = git(raiz, ["rm", "-q", "--cached", "--ignore-unmatch", "--", caminho], executar)
                if feito.returncode == 0 and (Path(raiz) / caminho).exists():
                    (Path(raiz) / caminho).unlink()
            if feito.returncode != 0:
                return False
    except (Recusa, OSError):
        return False
    return True


def _commit_falhou(raiz: Path, feito: subprocess.CompletedProcess, subcomando: str, voltam: list[str],
                   executar) -> Recusa:
    """A recusa do commit, depois de voltar os arquivos do harness ao último commit."""
    motivo = f"git commit falhou: {comum.motivo_do_git(feito, subcomando)}"
    if not voltam or not _voltar(raiz, voltam, executar):
        return Recusa(motivo)
    return Recusa(f"{motivo}; {comum.juntar(voltam)} {'voltou' if len(voltam) == 1 else 'voltaram'} ao último commit")


def commitar(raiz: Path, caminhos: list[str], mensagem: str, do_harness: list[str], executar=subprocess.run,
             corpo: str | None = None) -> bool:
    """O commit só com os caminhos que mudaram, que deixa o resto do índice como estava; sem mudança, nada, e False.

    Os mudados saem do `git status --porcelain -z --untracked-files=all -- <caminhos>`; o caminho que não existe nem
    está no índice fica de fora. Vão pelo `git add -A` e pelo `git commit -q -m <mensagem> [-m <corpo>] -- <mudados>`,
    com TEMPO_DO_COMMIT, que roda o pre-commit. Na falha, os de `do_harness` entre os mudados (entre os `caminhos`, no
    status que falha) voltam ao último commit, e a recusa é `git commit falhou: <motivo>; <a> voltou ao último
    commit`, ou `<a> e <b> voltaram`; com uma volta que falha, só a primeira parte.
    """
    status = git(raiz, ["status", "--porcelain", "-z", "--untracked-files=all", "--", *caminhos], executar)
    if status.returncode != 0:
        raise _commit_falhou(raiz, status, "status", [c for c in do_harness if c in caminhos], executar)
    mudados = _mudados(status.stdout)
    if not mudados:
        return False
    voltam = [caminho for caminho in do_harness if caminho in mudados]
    for argumentos, tempo in ((["add", "-A", "--", *mudados], TEMPO_LIMITE_GIT),
                              (["commit", "-q", "-m", mensagem, *(["-m", corpo] if corpo else []), "--", *mudados],
                               TEMPO_DO_COMMIT)):
        feito = git(raiz, argumentos, executar, tempo)
        if feito.returncode != 0:
            raise _commit_falhou(raiz, feito, argumentos[0], voltam, executar)
    return True


@dataclass(frozen=True)
class EstadoDoBloco:
    id: str
    slug: str
    estado: str
    estado_anterior: str
    bloqueio: str
    motivo: str
    efeito_externo: str
    passagem: int
    ramo: str
    lane: int
    base: str
    retornos: tuple[tuple[int, str], ...]
    atualizado_em: str
    caminho: str = SEM
    spec: str = SEM

    @property
    def efetivo(self) -> str:
        """O estado que vale: o `estado_anterior` em `blocked`, senão o `estado`."""
        return self.estado_anterior if self.estado == "blocked" else self.estado

    @property
    def pasta(self) -> str:
        """A pasta do bloco em `caminhos.blocos`: `<id>-<slug>`."""
        return f"{self.id}-{self.slug}"


def hash_da_spec(dados: bytes) -> str:
    """O sha256 da spec aprovada, em 64 hexadecimais, com a quebra `CRLF` contada como `LF`."""
    return hashlib.sha256(dados.replace(b"\r\n", b"\n")).hexdigest()


ARQUIVO_DA_LANE = "harness-lane"  # o número da lane, no diretório do git da worktree
PASTA_DA_REVISAO = "harness-revisao"
MARCA_DA_REVISAO = "em-andamento"
VIDA_DA_MARCA = datetime.timedelta(hours=4)
_RE_MARCA = re.compile(r"([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}) rodada [1-9][0-9]*\n?")


def pasta_da_revisao(raiz: Path) -> Path:
    """A `<git-dir da worktree>/harness-revisao/`, achada pelos arquivos, sem rodar o git; sem o diretório do git,
    `Recusa("fora de um repositório git")`."""
    gitdir = comum.diretorio_do_git(Path(raiz))
    if gitdir is None:
        raise Recusa("fora de um repositório git")
    return gitdir / PASTA_DA_REVISAO


def gravar_marca_da_revisao(raiz: Path, inicio: datetime.datetime, rodada: int) -> None:
    """Grava a marca da revisão em andamento: `<AAAA-MM-DDTHH:MM> rodada <n>` e uma quebra."""
    comum.escrever_texto(pasta_da_revisao(raiz) / MARCA_DA_REVISAO,
                         f"{inicio.strftime('%Y-%m-%dT%H:%M')} rodada {rodada}\n")


def marca_da_revisao(raiz: Path, agora: datetime.datetime) -> datetime.datetime | None:
    """A hora da marca da revisão em andamento, enquanto ela vale (VIDA_DA_MARCA, contada da hora do texto), ou None:
    sem a marca, vencida, ilegível ou fora de um repositório git."""
    gitdir = comum.diretorio_do_git(Path(raiz))
    if gitdir is None:
        return None
    try:
        achado = _RE_MARCA.fullmatch(comum.ler_texto(gitdir / PASTA_DA_REVISAO / MARCA_DA_REVISAO))
    except (OSError, UnicodeDecodeError):
        return None
    if achado is None or not _data_hora_valida(achado.group(1)):
        return None
    inicio = datetime.datetime.strptime(achado.group(1), "%Y-%m-%dT%H:%M")
    return inicio if agora < inicio + VIDA_DA_MARCA else None


def apagar_marca_da_revisao(raiz: Path) -> None:
    """Apaga a marca da revisão em andamento, se ela existe."""
    gitdir = comum.diretorio_do_git(Path(raiz))
    if gitdir is not None:
        (gitdir / PASTA_DA_REVISAO / MARCA_DA_REVISAO).unlink(missing_ok=True)


SKILL_DO_ESTADO = {"planning": "planejar-bloco", "ready_for_execution": "executar-bloco",
                   "executing": "executar-bloco", "ready_for_review": "revisar-bloco", "reviewing": "revisar-bloco",
                   "ready_for_closure": "finalizar-bloco", "closing": "finalizar-bloco"}


def proxima_acao(bloco_: EstadoDoBloco, revisao_desde: datetime.datetime | None = None,
                 compactado: bool = False) -> str:
    """A ação seguinte do bloco, pelo estado (spec 6d-bloco, §11). Com a marca da revisão em andamento
    (`revisao_desde`), `ready_for_review` e `reviewing` mandam esperar o aviso do workflow;
    com `compactado`, `executing` lembra o ledger."""
    if bloco_.estado == "blocked":
        return f"bloqueio por {bloco_.bloqueio}: {bloco_.motivo}; o dono decide com harness.py bloco desbloquear"
    if bloco_.estado == "planning":
        return f"/{comum.PREFIXO_DAS_SKILLS}planejar-bloco: termine a spec e o plano"
    if bloco_.estado == "closing":
        return f"aguarde o merge do PR; depois, harness.py lane fechar {bloco_.id} {ONDE_FECHAR_A_LANE}"
    if bloco_.estado in ("ready_for_review", "reviewing") and revisao_desde is not None:
        return "espere o aviso do workflow revisao-do-bloco"
    acao = f"/{comum.PREFIXO_DAS_SKILLS}{SKILL_DO_ESTADO[bloco_.estado]}"
    if bloco_.estado == "executing" and compactado:
        acao += "; o SDD retoma pelo ledger em .superpowers/sdd/"
    return acao


def _ramo_valido(ramo: str) -> bool:
    return not re.search(r"\s", ramo) and ".." not in ramo and not ramo.startswith("-")


def _data_hora_valida(valor: str) -> bool:
    if not _RE_DATA_HORA.fullmatch(valor):
        return False
    try:
        datetime.datetime.strptime(valor, "%Y-%m-%dT%H:%M")
    except ValueError:
        return False
    return True


def _retornos(valor: str) -> tuple[tuple[int, str], ...] | None:
    """Os retornos de `#N fato` e `#N decisao` separados por `, `, `()` para `—` e None fora da forma."""
    if valor == SEM:
        return ()
    retornos = []
    for parte in valor.split(", "):
        achado = _RE_RETORNO.fullmatch(parte)
        if not achado:
            return None
        retornos.append((int(achado.group(1)), achado.group(2)))
    return tuple(retornos)


# A conferência da forma de cada valor, na ordem de CHAVES; o `motivo` aceita qualquer texto.
_FORMAS = {
    "id": lambda v: bool(_RE_ID.fullmatch(v)),
    "slug": lambda v: bool(_RE_SLUG.fullmatch(v)),
    "estado": lambda v: v in ESTADOS,
    "estado_anterior": lambda v: v in ESTADOS or v == SEM,
    "bloqueio": lambda v: v in BLOQUEIOS or v == SEM,
    "efeito_externo": lambda v: v in ("sim", "não", SEM),
    "caminho": lambda v: v in CAMINHOS or v == SEM,
    "spec": lambda v: bool(_RE_SPEC.fullmatch(v)) or v == SEM,
    "passagem": lambda v: bool(_RE_PASSAGEM.fullmatch(v)),
    "ramo": _ramo_valido,
    "lane": lambda v: bool(_RE_LANE.fullmatch(v)),
    "base": lambda v: bool(_RE_BASE.fullmatch(v)),
    "retornos": lambda v: _retornos(v) is not None,
    "atualizado_em": _data_hora_valida,
}


def ler_estado(texto: str, caminho: str) -> EstadoDoBloco:
    """O `estado.md` lido; fora do formato, `BlocoInvalido` com o `caminho` e o primeiro motivo.

    A ordem das recusas: as linhas, na ordem do arquivo (a forma, a chave desconhecida e a repetida); as chaves que
    faltam, na ordem de CHAVES; os valores, na mesma ordem; a regra do `blocked`; e o `efeito_externo`, o `caminho` e a
    `spec` pelo estado efetivo: em `planning` os três são `—`, e fora dele nenhum é.
    """
    linhas = [linha[:-1] if linha.endswith("\r") else linha for linha in texto.split("\n")]
    fim = next((i for i, linha in enumerate(linhas) if i > 0 and linha == "---"), None)
    if linhas[0] != "---" or fim is None:
        raise BlocoInvalido(caminho, "sem as linhas --- de abertura e de fechamento")
    valores: dict[str, str] = {}
    for linha in linhas[1:fim]:
        achado = _RE_LINHA.fullmatch(linha)
        if not achado:
            raise BlocoInvalido(caminho, f"linha fora da forma chave: valor: {linha}")
        chave, valor = achado.group(1), achado.group(2).strip()
        if chave not in CHAVES:
            raise BlocoInvalido(caminho, f"chave desconhecida: {chave}")
        if chave in valores:
            raise BlocoInvalido(caminho, f"chave repetida: {chave}")
        valores[chave] = valor
    for chave in CHAVES:
        if chave not in valores:
            raise BlocoInvalido(caminho, f"falta a chave {chave}")
    if valores["formato"] != str(FORMATO):
        raise BlocoInvalido(caminho, f"formato {valores['formato']}; este harness lê o formato {FORMATO}")
    for chave in CHAVES:
        if chave in _FORMAS and not _FORMAS[chave](valores[chave]):
            raise BlocoInvalido(caminho, f"{chave} fora da forma: {valores[chave]}")
    estado = valores["estado"]
    if estado == "blocked" and (
        valores["estado_anterior"] in ("blocked", SEM) or SEM in (valores["bloqueio"], valores["motivo"])
    ):
        raise BlocoInvalido(caminho, "blocked pede estado_anterior, bloqueio e motivo")
    efetivo = valores["estado_anterior"] if estado == "blocked" else estado
    efeito = valores["efeito_externo"]
    if (efetivo == "planning") != (efeito == SEM):
        raise BlocoInvalido(caminho, f"efeito_externo fora da forma: {efeito}")
    for chave in ("caminho", "spec"):
        if (efetivo == "planning") != (valores[chave] == SEM):
            raise BlocoInvalido(caminho, f"{chave} fora da forma: {valores[chave]}")
    return EstadoDoBloco(
        id=valores["id"], slug=valores["slug"], estado=estado, estado_anterior=valores["estado_anterior"],
        bloqueio=valores["bloqueio"], motivo=valores["motivo"], efeito_externo=efeito,
        passagem=int(valores["passagem"][1:]), ramo=valores["ramo"], lane=int(valores["lane"]), base=valores["base"],
        retornos=_retornos(valores["retornos"]), atualizado_em=valores["atualizado_em"], caminho=valores["caminho"],
        spec=valores["spec"],
    )


def para_texto(estado: EstadoDoBloco) -> str:
    """O `estado.md` do bloco, com uma quebra no fim de cada linha."""
    retornos = ", ".join(f"#{numero} {tipo}" for numero, tipo in estado.retornos) or SEM
    linhas = [
        "---", f"formato: {FORMATO}", f"id: {estado.id}", f"slug: {estado.slug}", f"estado: {estado.estado}",
        f"estado_anterior: {estado.estado_anterior}", f"bloqueio: {estado.bloqueio}", f"motivo: {estado.motivo}",
        f"efeito_externo: {estado.efeito_externo}", f"caminho: {estado.caminho}", f"spec: {estado.spec}",
        f"passagem: v{estado.passagem}", f"ramo: {estado.ramo}",
        f"lane: {estado.lane}", f"base: {estado.base}", f"retornos: {retornos}",
        f"atualizado_em: {estado.atualizado_em}", "---",
    ]
    return "".join(linha + "\n" for linha in linhas)


def _ler_da_pasta(texto: str, caminho: str, pasta: str) -> EstadoDoBloco:
    """O `ler_estado` do `estado.md` de `<blocos>/<pasta>/`; a pasta diferente de `<id>-<slug>` lança
    `BlocoInvalido`."""
    estado = ler_estado(texto, caminho)
    if pasta != estado.pasta:
        raise BlocoInvalido(caminho, f"a pasta {pasta} não confere com {estado.pasta}")
    return estado


def motivo_da_passagem(versao: int, ids: list[str]) -> str:
    """`passagem/v<N> mudou <IDs>`, com os IDs na ordem dada: os que mudaram e depois os que saíram."""
    return f"passagem/v{versao} mudou {comum.juntar(ids)}"


_RE_MOTIVO_DA_PASSAGEM = re.compile(r"passagem/v([1-9][0-9]*) mudou ")


def versao_do_motivo(motivo: str) -> int | None:
    """O N de um motivo do `motivo_da_passagem`, ou None fora dessa forma."""
    achado = _RE_MOTIVO_DA_PASSAGEM.match(motivo)
    return int(achado.group(1)) if achado else None


def pasta_da_branch(ramo: str) -> str:
    """A pasta do bloco de uma branch: o trecho depois da última `/`."""
    return ramo.rsplit("/", 1)[-1]


def branch_de_bloco(ramo: str) -> bool:
    """Se a branch tem a forma das de bloco, `<tipo>/<ID>-<slug>`, com o tipo de TIPOS e o slug na forma do
    `estado.md`."""
    tipo, barra, resto = ramo.partition("/")
    return bool(barra) and tipo in TIPOS and bool(_RE_PASTA_DE_BLOCO.fullmatch(resto))


@dataclass(frozen=True)
class LaneViva:
    pasta: Path
    ramo: str
    bloco: EstadoDoBloco


@dataclass(frozen=True)
class WorktreeDeLane:
    """Uma worktree dentro de `lane.pasta`: a pasta, na grafia do git, a branch (None sem ela) e se o git a dá como
    `prunable`, com a pasta sumida."""

    pasta: Path
    ramo: str | None
    sumida: bool


def _worktrees(raiz: Path, executar) -> list[dict[str, str]]:
    """As entradas do `git worktree list --porcelain`, cada uma de rótulo para valor; fora de um repositório,
    `Recusa("fora de um repositório git")`."""
    feito = git(raiz, ["worktree", "list", "--porcelain"], executar)
    if feito.returncode != 0:
        raise Recusa("fora de um repositório git")
    entradas = []
    for bruta in feito.stdout.decode("utf-8", errors="replace").split("\n\n"):
        entrada = {}
        for linha in bruta.splitlines():
            rotulo, _, valor = linha.partition(" ")
            entrada[rotulo] = valor
        if "worktree" in entrada:
            entradas.append(entrada)
    if not entradas:
        raise Recusa("fora de um repositório git")
    return entradas


def arvore_principal(raiz: Path, executar=subprocess.run) -> Path:
    """A árvore principal do repositório da raiz, a primeira do `git worktree list --porcelain`, na grafia do git."""
    return Path(_worktrees(raiz, executar)[0]["worktree"])


def _relativo(caminho: Path, base: Path) -> str:
    try:
        return caminho.relative_to(base).as_posix()
    except ValueError:
        return caminho.as_posix()


def worktrees_de_lane(raiz: Path, perfil, executar=subprocess.run) -> tuple[Path, list[WorktreeDeLane]]:
    """A árvore principal e as worktrees dentro de `<principal>/<lane.pasta>`, em ordem da pasta, pelo
    `git worktree list --porcelain`."""
    principal, *outras = _worktrees(raiz, executar)
    pasta_principal = Path(principal["worktree"])
    pasta_das_lanes = (pasta_principal / perfil.lane.pasta).resolve()
    worktrees = []
    for entrada in outras:
        pasta = Path(entrada["worktree"])
        try:
            pasta.resolve().relative_to(pasta_das_lanes)
        except ValueError:
            continue
        ramo = entrada.get("branch", "")
        ramo = ramo[len("refs/heads/"):] if ramo.startswith("refs/heads/") else None
        worktrees.append(WorktreeDeLane(pasta, ramo, "prunable" in entrada))
    return pasta_principal, sorted(worktrees, key=lambda worktree: str(worktree.pasta))


def motivo_da_leitura(erro: BaseException) -> str:
    """O motivo de um arquivo que não se lê: `arquivo fora do UTF-8` para o `UnicodeDecodeError`, e o
    `comum.motivo_do_sistema` para o `OSError` (spec 6d-bloco, §12, item 3)."""
    if isinstance(erro, UnicodeDecodeError):
        return "arquivo fora do UTF-8"
    return comum.motivo_do_sistema(erro)


def estado_da_branch(pasta: Path, ramo: str, perfil) -> Path:
    """O `estado.md` do bloco da branch numa worktree: `<pasta>/<blocos>/<último trecho do ramo>/estado.md`."""
    return Path(pasta) / perfil.caminhos.blocos / pasta_da_branch(ramo) / ARQUIVO


def linha_do_ilegivel(pasta: Path, ramo: str, perfil, base: Path, erro: BaseException) -> str:
    """`<caminho>: estado.md ilegível: <motivo>`, do `estado.md` da branch que não se lê, com o caminho relativo à
    `base` e o `motivo_da_leitura` do erro (spec 6d-bloco, §12, item 3)."""
    return f"{_relativo(estado_da_branch(pasta, ramo, perfil), base)}: estado.md ilegível: {motivo_da_leitura(erro)}"


def bloco_da_worktree(pasta: Path, ramo: str, perfil, base: Path) -> EstadoDoBloco | None:
    """O bloco da branch de uma worktree: o `<pasta>/<blocos>/<último trecho do ramo>/estado.md` de `ramo` igual ao
    dela, ou None, sem o arquivo ou com outro `ramo`. Fora do formato, ou numa pasta que não confere, `BlocoInvalido`,
    com o caminho relativo à `base`; o erro do sistema e o texto fora do UTF-8 passam."""
    arquivo = estado_da_branch(pasta, ramo, perfil)
    if not arquivo.is_file():
        return None
    estado = _ler_da_pasta(comum.ler_texto(arquivo), _relativo(arquivo, base), arquivo.parent.name)
    return estado if estado.ramo == ramo else None


def lanes_vivas(raiz: Path, perfil, executar=subprocess.run, ilegiveis: list[str] | None = None) -> list[LaneViva]:
    """As lanes vivas do repositório da raiz, em ordem da pasta: as worktrees de lane com branch, não sumidas, com o
    bloco da branch; um `estado.md` desses fora do formato lança `BlocoInvalido`, com o caminho relativo à árvore
    principal, e o que não se lê passa como `UnicodeDecodeError` ou `OSError`.

    Com `ilegiveis`, esse `estado.md` não lança: vai para a lista como `<caminho>: estado.md inválido: <motivo>` ou
    `<caminho>: estado.md ilegível: <motivo>`, e a lane fica de fora (spec 6d-bloco, §12, item 2)."""
    principal, worktrees = worktrees_de_lane(raiz, perfil, executar)
    lanes = []
    for worktree in worktrees:
        if worktree.ramo is None or worktree.sumida:
            continue
        try:
            estado = bloco_da_worktree(worktree.pasta, worktree.ramo, perfil, principal)
        except (BlocoInvalido, UnicodeDecodeError, OSError) as erro:
            if ilegiveis is None:
                raise
            if isinstance(erro, BlocoInvalido):
                ilegiveis.append(erro.mensagem)
            else:
                ilegiveis.append(linha_do_ilegivel(worktree.pasta, worktree.ramo, perfil, principal, erro))
            continue
        if estado is not None:
            lanes.append(LaneViva(worktree.pasta, worktree.ramo, estado))
    return lanes


def lane_da_arvore(raiz: Path, lanes: list[LaneViva]) -> LaneViva | None:
    """A lane cuja pasta é a raiz, comparadas por dispositivo e inode, como o `os.path.samefile`; o erro do sistema
    conta como diferente. Sem nenhuma, None."""
    return next((lane for lane in lanes if comum.mesma_arvore(lane.pasta, Path(raiz))), None)


def lane_pelos_arquivos(arvore: Path, perfil) -> LaneViva | None:
    """A lane da árvore pelos arquivos, sem rodar o git (spec 6c, §3, item 27), ou None.

    É lane a worktree cujo `.git` é arquivo, com o `HEAD` do diretório do git dela em `ref: refs/heads/<ramo>`,
    cujo diretório comum se chama `.git` e tem acima dele a árvore principal, e que fica dentro de
    `<principal>/<lane.pasta>`, com as pastas comparadas por dispositivo e inode. O bloco é o `bloco_da_worktree`, com
    o caminho relativo à árvore; os outros `estado.md` dela não são lidos. A `pasta` da lane é a `arvore` recebida.
    """
    arvore = Path(arvore)
    if not (arvore / ".git").is_file():
        return None
    gitdir, comum_do_git = comum.diretorio_do_git(arvore), comum.diretorio_comum(arvore)
    if gitdir is None or comum_do_git is None or comum_do_git.name != ".git":
        return None
    try:
        cabeca = comum.ler_texto(gitdir / "HEAD").strip()
    except (OSError, UnicodeDecodeError):
        return None
    if not cabeca.startswith("ref: refs/heads/"):
        return None
    ramo = cabeca[len("ref: refs/heads/"):]
    pasta_das_lanes = comum_do_git.parent / perfil.lane.pasta
    if not any(comum.mesma_arvore(ancestral, pasta_das_lanes) for ancestral in Path(os.path.abspath(arvore)).parents):
        return None
    estado = bloco_da_worktree(arvore, ramo, perfil, arvore)
    return None if estado is None else LaneViva(arvore, ramo, estado)


def blocos_do_principal(raiz: Path, perfil, executar=subprocess.run) -> dict[str, EstadoDoBloco]:
    """Os blocos de `<blocos>/<pasta>/estado.md` no `origin/<ramo_principal>`, pelo ID, sem fetch; sem essa ref, `{}`."""
    ref = f"refs/remotes/origin/{perfil.ramo_principal}"
    if git(raiz, ["rev-parse", "--verify", "-q", ref], executar).returncode != 0:
        return {}
    blocos = perfil.caminhos.blocos
    listados = git(raiz, ["ls-tree", "-r", "-z", "--name-only", ref, "--", blocos], executar)
    if listados.returncode != 0:
        raise Recusa(f"git ls-tree falhou: {comum.motivo_do_git(listados, 'ls-tree')}")
    resultado = {}
    for caminho in listados.stdout.decode("utf-8", errors="replace").split("\0"):
        partes = caminho.split("/")
        if not caminho.startswith(blocos + "/") or len(partes) != blocos.count("/") + 3 or partes[-1] != ARQUIVO:
            continue
        lido = git(raiz, ["cat-file", "blob", f"{ref}:{caminho}"], executar)
        if lido.returncode != 0:
            raise Recusa(f"git cat-file falhou: {comum.motivo_do_git(lido, 'cat-file')}")
        estado = _ler_da_pasta(lido.stdout.decode("utf-8", errors="replace"),
                               f"origin/{perfil.ramo_principal}:{caminho}", partes[-2])
        resultado[estado.id] = estado
    return resultado
