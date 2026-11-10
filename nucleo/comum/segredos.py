"""Padrões de segredo: os do núcleo, com nome fixo, e a busca deles num texto, para a guarda e o `sem-segredos`.

Os padrões do perfil (`[guarda.segredos]`) vêm depois dos do núcleo, na ordem do arquivo. Quem recusa um texto diz o
nome do padrão que casou, nunca o valor.
"""
from __future__ import annotations

import re

# Os padrões do núcleo, na ordem em que a busca os tenta: nome e expressão regular.
NUCLEO: tuple[tuple[str, str], ...] = (
    ("chave-privada", r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----"),
    ("chave-aws", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ("token-github", r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})"),
    ("jwt", r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\."),
    ("chave-linear", r"\blin_api_[A-Za-z0-9]{32,}\b"),
)
# O nome de um padrão, do núcleo ou do perfil.
RE_NOME = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


def compilar(do_perfil: tuple[tuple[str, str], ...]) -> tuple[tuple[str, re.Pattern], ...]:
    """Os padrões do núcleo e depois os do perfil, na ordem, já compilados."""
    return tuple((nome, re.compile(expressao)) for nome, expressao in (*NUCLEO, *do_perfil))


def achar(texto: str, padroes: tuple[tuple[str, re.Pattern], ...]) -> str | None:
    """O nome do primeiro padrão, na ordem, que casa em algum ponto do texto; None sem nenhum."""
    return next((nome for nome, padrao in padroes if padrao.search(texto)), None)
