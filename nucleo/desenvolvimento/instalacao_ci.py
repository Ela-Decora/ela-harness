"""A instalação do CI (spec `ci-dos-projetos`, §6.2): os comandos de `[desenvolvimento.ci] instalar`, um por um.

Rodam no GitHub Actions, e o PATH e as variáveis que cada um deixa nos arquivos do runner passam ao seguinte.
"""
from __future__ import annotations

import os
import time
from collections.abc import Mapping
from pathlib import Path

import lane
import verificacao

NOME = "instalação do CI"
TEMPO = lane.TEMPO_DOS_COMANDOS

AJUDA = """\
Roda no CI, um por um, os comandos de `[desenvolvimento.ci] instalar` do perfil, na raiz do projeto, por `sh -c`, com a
entrada fechada e o tempo limite de 900 s cada. Só roda com `GITHUB_ACTIONS=true`; fora do CI, recusa. Sem comando na
lista, diz que não há o que instalar.

Cada comando roda no ambiente do runner. Entre um comando e o seguinte, o PATH e as variáveis que o anterior gravou
nos arquivos `GITHUB_PATH` e `GITHUB_ENV` valem para o seguinte, como entre os passos do GitHub Actions: no
`GITHUB_PATH`, cada linha não vazia vai para a frente do PATH; no `GITHUB_ENV`, valem `NOME=valor` e o bloco
`NOME<<DELIM`, até a linha `DELIM`.

As linhas:

- `instalação do CI: <comando>: ok (<s> s)`;
- `instalação do CI: <comando> falhou (saída <c>)` ou `instalação do CI: <comando> passou de 900 s`, seguida das
  linhas de comando que falta, das últimas 30 linhas da saída e da anotação `::error`.

O primeiro que falha para a lista, e o comando sai com 1; com todos ok, sai com 0.

Serviço que precisa ficar de pé, como um banco, sobe com `docker compose up -d` ou `docker run -d`, que o deixam no
Docker. O `&` não serve: o processo em segundo plano morre com o grupo de processos do comando, que acaba no fim dele.
"""


def _linhas_do_arquivo(variavel: str, ambiente: Mapping[str, str]) -> list[str]:
    caminho = ambiente.get(variavel)
    if not caminho or not os.path.isfile(caminho):
        return []
    try:
        with open(caminho, encoding="utf-8", errors="replace") as arquivo:
            return arquivo.read().splitlines()
    except OSError:
        return []


def _variaveis(linhas: list[str]) -> dict[str, str]:
    achadas: dict[str, str] = {}
    i = 0
    while i < len(linhas):
        linha = linhas[i]
        i += 1
        if "<<" in linha and ("=" not in linha or linha.index("<<") < linha.index("=")):
            nome, _, delimitador = linha.partition("<<")
            valor: list[str] = []
            while i < len(linhas) and linhas[i] != delimitador:
                valor.append(linhas[i])
                i += 1
            i += 1
            if nome:
                achadas[nome] = "\n".join(valor)
        elif "=" in linha:
            nome, _, valor_ = linha.partition("=")
            if nome:
                achadas[nome] = valor_
    return achadas


def ambiente_do_runner(base: Mapping[str, str]) -> dict[str, str]:
    """A cópia de `base` com as variáveis do arquivo de `GITHUB_ENV` e, na frente do PATH, as linhas não vazias do
    arquivo de `GITHUB_PATH`, da última para a primeira; arquivo não definido ou inexistente não muda nada."""
    ambiente = dict(base)
    ambiente.update(_variaveis(_linhas_do_arquivo("GITHUB_ENV", base)))
    novos = [linha.strip() for linha in _linhas_do_arquivo("GITHUB_PATH", base) if linha.strip()]
    if novos:
        ambiente["PATH"] = os.pathsep.join([*reversed(novos), *([ambiente["PATH"]] if ambiente.get("PATH") else [])])
    return ambiente


def instalar(raiz: Path, perfil, ambiente: Mapping[str, str], rodar=verificacao.rodar_comando,
             relogio=time.monotonic) -> tuple[int, list[str]]:
    """Roda os comandos de `ci_instalar` na raiz, um por um, e devolve o código de saída e as linhas. Antes de cada
    comando recalcula o ambiente do runner, porque o anterior pode ter gravado nos arquivos dele."""
    if not verificacao.no_ci(ambiente):
        return 1, [f"{NOME}: só roda no CI ({verificacao.NO_CI}=true)"]
    if not perfil.ci_instalar:
        return 0, [f"{NOME}: nada a instalar"]
    linhas: list[str] = []
    for comando in perfil.ci_instalar:
        inicio = relogio()
        codigo, saida = rodar(comando, raiz, TEMPO, ambiente_do_runner(ambiente))
        fim = relogio()
        if codigo == 0:
            linhas.append(f"{NOME}: {comando}: ok ({f'{fim - inicio:.1f}'.replace('.', ',')} s)")
            continue
        falha = f"{NOME}: {comando} passou de {TEMPO} s" if codigo is None else f"{NOME}: {comando} falhou (saída {codigo})"
        ultimas = tuple("  " + linha for linha in saida.splitlines()[-verificacao.LINHAS_DA_SAIDA:])
        linhas.extend(verificacao.linhas_da_falha(NOME, falha, saida, ultimas, ambiente))
        return 1, linhas
    return 0, linhas
