"""Pre-push do repositório de código (spec 6c, §13): recusa o push direto no ramo principal e a remoção dele, e deixa
passar a criação, a da montagem.

O git passa ao hook o nome e o endereço do remoto, que não contam, e uma linha por ref no stdin. Só a ref remota do
ramo principal do perfil é conferida; as outras passam.
"""
from __future__ import annotations

import re

from perfil_desenvolvimento import PerfilDesenvolvimento

PREFIXO = "pre-push do harness: "
_RE_SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")

AJUDA = """\
Chamado pelo hook `pre-push` do git, o `.githooks/pre-push` do repositório de código, que roda
`exec python3 .claude/harness/harness.py prepush "$@"`. O git passa o nome e o endereço do remoto, que o comando aceita
e não usa, e escreve no stdin uma linha por ref do push, na forma
`<ref local> <sha local> <ref remota> <sha remota>`, com os shas em hexadecimal de 40 ou 64 caracteres; sha só de
zeros é a ref que não existe daquele lado. Linha em branco não conta. A linha que não tem quatro campos, ou que tem um
sha fora dessa forma, dá `pre-push do harness: linha do git fora da forma: <linha>`.

Na ref remota `refs/heads/<ramo>`, com o `ramo_principal` do perfil:

- sha local só de zeros, a remoção: `pre-push do harness: apagar o <ramo> no remoto recusado`;
- sha remota só de zeros, a criação, que é a da montagem: passa;
- os outros casos, a atualização: `pre-push do harness: push direto no <ramo> recusado; abra um PR`.

As outras refs passam. O comando imprime as recusas, uma por linha, e sai com 1 com alguma, o que para o push; sem
recusa, não imprime nada e sai com 0.

O `git push --no-verify` pula o hook; a guarda pergunta antes de deixá-lo rodar.

Pelo terminal, o `prepush` lê o stdin só quando ele não é um terminal, como em
`echo "<linha>" | python3 .claude/harness/harness.py prepush`; sem linhas, passa.
"""


def _so_zeros(sha: str) -> bool:
    return set(sha) == {"0"}


def conferir(linhas: list[str], perfil: PerfilDesenvolvimento) -> list[str]:
    """As recusas das linhas que o git passa ao pre-push, na ordem delas; vazia, o push passa."""
    ramo = perfil.ramo_principal
    recusas = []
    for linha in linhas:
        if not linha.strip():
            continue
        campos = linha.split()
        if len(campos) != 4 or not (_RE_SHA.fullmatch(campos[1]) and _RE_SHA.fullmatch(campos[3])):
            recusas.append(f"{PREFIXO}linha do git fora da forma: {linha}")
            continue
        _, local, remota, sha_remoto = campos
        if remota != f"refs/heads/{ramo}":
            continue
        if _so_zeros(local):
            recusas.append(f"{PREFIXO}apagar o {ramo} no remoto recusado")
        elif not _so_zeros(sha_remoto):
            recusas.append(f"{PREFIXO}push direto no {ramo} recusado; abra um PR")
    return recusas
