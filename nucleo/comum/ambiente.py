"""O que a máquina precisa para o harness rodar (spec 4a, §8.3): o Python com leitor de TOML, o pre-commit ativo e a
árvore em que a sessão abriu.

Só biblioteca padrão, sem o `perfil` nem o `estado`: o item do Python precisa funcionar justamente quando o perfil não
carrega. Cada item sai em `OK`, `AVISO` ou `FALHA`, com o comando que conserta.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

AJUDA = """\
Diz o que falta nesta máquina para o harness rodar: o Python com leitor de TOML, o pre-commit ativo e a árvore.

Uma linha por item, que começa por `OK:`, `AVISO:` ou `FALHA:` e traz o comando que conserta. Não lê o perfil, e por
isso funciona quando ele não carrega. Sai com 1 só com algum `FALHA`.

1. Python e TOML: o Python 3.9 ou mais novo, com `tomllib` ou `tomli`; sem leitor, `pip3 install --user tomli`.
2. Pre-commit: o `core.hooksPath` igual a `.githooks`; sem ele, `git config core.hooksPath .githooks`, que vale para o
   clone e os worktrees dele.
3. Árvore: `OK: árvore principal`, ou `AVISO` num worktree, onde o planejamento é a cópia da branch dele e o refino
   vai na árvore principal.

Sem `.git` na raiz, os itens 2 e 3 dão `OK`; o erro do git dá `AVISO`.
"""

OK = "OK"
AVISO = "AVISO"
FALHA = "FALHA"

_LEITORES_DE_TOML = ("tomllib", "tomli")
_VERSAO_MINIMA = (3, 9)
_TEMPO_LIMITE_GIT = 5
_PASTA_DOS_HOOKS = ".githooks"
_COMANDO_HOOKS_PATH = ["git", "config", "--get", "core.hooksPath"]
_COMANDO_GIT_DIR = ["git", "rev-parse", "--git-dir", "--git-common-dir"]
_COMANDO_BRANCH = ["git", "rev-parse", "--abbrev-ref", "HEAD"]


@dataclass(frozen=True)
class Item:
    nivel: str
    texto: str

    @property
    def linha(self) -> str:
        return f"{self.nivel}: {self.texto}"


@dataclass(frozen=True)
class Ambiente:
    """Os três itens, na ordem de §8.3, e a branch do worktree, ou None na árvore principal."""

    itens: tuple[Item, ...]
    worktree: str | None

    @property
    def avisos(self) -> tuple[Item, ...]:
        """Os itens `FALHA` e `AVISO`, na ordem."""
        return tuple(item for item in self.itens if item.nivel != OK)

    @property
    def falhou(self) -> bool:
        return any(item.nivel == FALHA for item in self.itens)


def leitor_de_toml() -> str | None:
    """`tomllib` ou `tomli`, o primeiro que esta máquina tem; None sem nenhum."""
    for nome in _LEITORES_DE_TOML:
        if importlib.util.find_spec(nome) is not None:
            return nome
    return None


def python_e_toml(versao: tuple[int, int, int], leitor: str | None) -> Item:
    """Python 3.9 ou mais novo, com leitor de TOML."""
    texto = ".".join(str(parte) for parte in versao)
    if tuple(versao[:2]) < _VERSAO_MINIMA:
        return Item(FALHA, f"Python {texto} é anterior ao 3.9: instale o Python 3.9 ou mais novo")
    if leitor is None:
        return Item(FALHA, f"Python {texto} sem leitor de TOML: pip3 install --user tomli")
    return Item(OK, f"Python {texto} com {leitor}")


def _rodar_git(comando: list[str], raiz: Path, executar) -> subprocess.CompletedProcess:
    return executar(
        comando,
        cwd=raiz,
        timeout=_TEMPO_LIMITE_GIT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _motivo(erro: Exception) -> str:
    return f"{type(erro).__name__}: " + " ".join(str(erro).split())


def pre_commit(raiz: Path, executar=subprocess.run) -> Item:
    """`core.hooksPath` igual a `.githooks`, com `.git` na raiz (pasta ou arquivo); sem ele, o item não se aplica."""
    if not os.path.lexists(raiz / ".git"):
        return Item(OK, "sem .git na raiz; pre-commit não se aplica")
    falhou = "git config --get core.hooksPath falhou"
    try:
        resultado = _rodar_git(_COMANDO_HOOKS_PATH, raiz, executar)
    except Exception as erro:
        return Item(AVISO, f"{falhou} ({_motivo(erro)})")
    if resultado.returncode == 0 and (resultado.stdout or "").strip() == _PASTA_DOS_HOOKS:
        return Item(OK, "pre-commit ativo (core.hooksPath .githooks)")
    if resultado.returncode in (0, 1):
        return Item(FALHA, "Pre-commit inativo: git config core.hooksPath .githooks")
    return Item(AVISO, f"{falhou} (código {resultado.returncode})")


def arvore(raiz: Path, executar=subprocess.run) -> tuple[Item, str | None]:
    """Árvore principal ou worktree: `--git-dir` diferente de `--git-common-dir` quer dizer worktree, e a branch vem
    junto (`?` se não se lê)."""
    if not os.path.lexists(raiz / ".git"):
        return Item(OK, "sem .git na raiz; sem worktree"), None
    falhou = "git rev-parse falhou"
    try:
        resultado = _rodar_git(_COMANDO_GIT_DIR, raiz, executar)
    except Exception as erro:
        return Item(AVISO, f"{falhou} ({_motivo(erro)})"), None
    linhas = (resultado.stdout or "").splitlines()
    if resultado.returncode != 0 or len(linhas) < 2:
        return Item(AVISO, f"{falhou} (código {resultado.returncode})"), None
    git_dir, comum = ((raiz / linha.strip()).resolve() for linha in linhas[:2])
    if git_dir == comum:
        return Item(OK, "árvore principal"), None
    try:
        branch = _rodar_git(_COMANDO_BRANCH, raiz, executar)
        ramo = (branch.stdout or "").strip() if branch.returncode == 0 else ""
    except Exception:
        ramo = ""
    ramo = ramo or "?"
    texto = (
        f"worktree {ramo}: o planejamento desta árvore é a cópia da branch dela; refine documentos na árvore principal"
    )
    return Item(AVISO, texto), ramo


def conferir(raiz: Path, executar=subprocess.run, python: Item | None = None) -> Ambiente:
    """Os três itens, na ordem: Python e TOML, pre-commit e árvore. `python` substitui o item desta máquina."""
    if python is None:
        python = python_e_toml(tuple(sys.version_info[:3]), leitor_de_toml())
    item_arvore, ramo = arvore(raiz, executar)
    return Ambiente((python, pre_commit(raiz, executar), item_arvore), ramo)


def formatar(amb: Ambiente) -> str:
    """Uma linha por item."""
    return "".join(item.linha + "\n" for item in amb.itens)
