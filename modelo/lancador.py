#!/usr/bin/env python3
"""Lançador do harness no projeto: acha o núcleo, que mora no plugin ela-harness, e passa a ele os argumentos.

O CLAUDE.md, as skills, o pre-commit, o pre-push e a CI chamam este arquivo, nunca o plugin direto. O núcleo é a raiz do
plugin, procurada nesta ordem:

1. a variável HARNESS_NUCLEO, que a CI define depois de baixar o plugin;
2. o link .claude/harness/nucleo do projeto, que os hooks do plugin refazem a cada sessão do Claude Code;
3. o link da árvore principal, quando o projeto é uma worktree (as lanes do desenvolvimento): o link é ignorado pelo
   git e só existe na árvore principal;
4. o registro de plugins do Claude Code, ~/.claude/plugins/installed_plugins.json, com a instalação do projeto ou da
   árvore principal antes da do usuário.

Um link que não leva a um nucleo/comum/harness.py existente conta como ausente: depois de atualizar o plugin, o link
velho aponta para a pasta antiga do cache, que sumiu, e fora de uma sessão o registro já tem a nova.

Sem núcleo, sai com 3 e diz como instalar o plugin; o pre-commit trata o 3 como aviso, não como recusa. O lançador não
mexe no caminho de import nem roda o git: o nucleo/comum/harness.py roda como script e põe as pastas do núcleo no
caminho.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJETO = Path(__file__).resolve().parents[2]
PREFIXO_DO_PLUGIN = "ela-harness@"
SEM_NUCLEO = 3
LINK = Path(".claude") / "harness" / "nucleo"
SCRIPT = Path("nucleo") / "comum" / "harness.py"


def _arvore_principal(projeto: Path) -> Path | None:
    """A árvore principal, quando o `projeto` é uma worktree: o `.git` dela é um arquivo com
    `gitdir: <repositório>/.git/worktrees/<nome>`, e a principal é a pasta acima desse `.git`. Em qualquer outro caso
    (repositório comum, submódulo, sem git), None. Só lê o arquivo."""
    try:
        linha = (projeto / ".git").read_text(encoding="utf-8").splitlines()[0]
    except (OSError, ValueError, IndexError):
        return None
    if not linha.startswith("gitdir:"):
        return None
    gitdir = Path(os.path.normpath(projeto / linha[len("gitdir:"):].strip()))
    if gitdir.parent.name != "worktrees" or gitdir.parent.parent.name != ".git":
        return None
    return gitdir.parent.parent.parent


def _tem_nucleo(raiz: Path) -> bool:
    return (raiz / SCRIPT).is_file()


def _do_link(projeto: Path) -> Path | None:
    link = projeto / LINK
    return link.resolve() if _tem_nucleo(link) else None


def _do_registro(donos: list[Path]) -> Path | None:
    """O núcleo do registro: a instalação de um dos `donos` (o projeto e, numa worktree, a árvore principal) vem antes
    da do usuário, e a do projeto antes da principal."""
    registro = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    try:
        dados = json.loads(registro.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    candidatos = []
    for chave, instalacoes in (dados.get("plugins") or {}).items():
        if not chave.startswith(PREFIXO_DO_PLUGIN) or not isinstance(instalacoes, list):
            continue
        for instalacao in instalacoes:
            caminho = instalacao.get("installPath")
            projeto = instalacao.get("projectPath")
            if not caminho or not _tem_nucleo(Path(caminho)):
                continue
            if not projeto:
                candidatos.append((len(donos), Path(caminho)))
            elif Path(projeto).resolve() in donos:
                candidatos.append((donos.index(Path(projeto).resolve()), Path(caminho)))
    return min(candidatos)[1] if candidatos else None


def nucleo() -> Path | None:
    definida = os.environ.get("HARNESS_NUCLEO")
    if definida:
        return Path(definida)
    principal = _arvore_principal(PROJETO)
    donos = [PROJETO] + ([principal.resolve()] if principal else [])
    for dono in donos:
        achado = _do_link(dono)
        if achado:
            return achado
    return _do_registro(donos)


def principal() -> int:
    raiz = nucleo()
    script = raiz / SCRIPT if raiz else None
    if script is None or not script.is_file():
        print(
            "erro: núcleo do harness não encontrado; instale o plugin "
            "(claude plugin install ela-harness@ela-harness --scope project) "
            "e abra uma sessão do Claude Code no projeto, ou defina HARNESS_NUCLEO com a raiz do plugin"
        )
        return SEM_NUCLEO
    os.environ.setdefault("CLAUDE_PROJECT_DIR", str(PROJETO))
    os.execv(sys.executable, [sys.executable, str(script), *sys.argv[1:]])
    return 0


if __name__ == "__main__":
    sys.exit(principal())
