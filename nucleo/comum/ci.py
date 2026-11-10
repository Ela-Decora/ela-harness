"""O texto do `.github/workflows/harness.yml` de cada projeto (spec do CI dos projetos, §4).

É uma função pura da trilha, do ramo principal e da `ref` do plugin que o `.claude/settings.json` fixa.

O `gerar` lê o settings pelo `ler` que recebe e devolve `{}` quando ele não existe. As recusas sobem como
`RecusaDoCi`, com a linha inteira em `.motivo`. Os SHAs das actions moram aqui, numa definição só, que o gerador e os
testes dos `action.yml` leem.
"""
from __future__ import annotations

import json
from typing import Callable

import caminho
import comum
import perfil_comum

CAMINHO = ".github/workflows/harness.yml"
DISTRIBUICAO = "Ela-Decora/ela-harness"
CHECKOUT = ("11d5960a326750d5838078e36cf38b85af677262", "v4.4.0")
SETUP_PYTHON = ("a26af69be951a213d495a4c3e4e4022e16d87065", "v5.6.0")

SETTINGS = ".claude/settings.json"
MOTIVO_FORA_DO_UTF8 = "fora do UTF-8"
PREFIXO = "harness.yml: "

_PRIMEIRA_LINHA = "# Arquivo gerado por harness.py gerar. Não edite: rode harness.py gerar."
_LINHA_DA_STACK = "# A stack do projeto se declara em [desenvolvimento.ci] instalar, no .claude/perfil.toml.\n"

_FALHA_SEM_NUCLEO = (
    "::error title=harness: plugin não baixado::{distribuicao}@{ref} não foi baixado. A versão do harness.yml tem de "
    "ser uma tag publicada (https://github.com/{distribuicao}/tags) e a mesma do ref do .claude/settings.json; "
    "confira com python3 .claude/harness/harness.py gerar --check. Se a tag existe, rode de novo: pode ser falha "
    "do GitHub."
)

_MOLDE = """{primeira}
{stack}# As actions vão fixadas por SHA, que sobe com a versão do plugin: um PR do Dependabot neste arquivo fica \
vermelho.
# Se o run cai antes de qualquer passo, a causa provável é a política de actions da conta do GitHub.
name: harness
on:
  push:
    branches: [{ramo}]
  pull_request:
    branches: [{ramo}]
permissions:
  contents: read
jobs:
  harness:
    name: harness
    runs-on: ubuntu-24.04
    steps:
      - uses: {checkout}
        with:
          fetch-depth: 0
      - id: nucleo
        uses: {checkout}
        with:
          repository: {distribuicao}
          ref: {ref}
          path: .harness-nucleo
      - if: failure() && steps.nucleo.outcome == 'failure'
        run: |
          echo "{falha}"
      - uses: ./.harness-nucleo/ci/{trilha}
"""


class RecusaDoCi(Exception):
    """O `harness.yml` não se gera. `motivo` é a linha inteira da recusa."""

    def __init__(self, motivo: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo


def uses(par: tuple[str, str]) -> str:
    """O `uses` de uma action fixada: `<repo>@<sha> # <versão>`, a partir de `CHECKOUT` ou `SETUP_PYTHON`."""
    repositorio = "actions/checkout" if par == CHECKOUT else "actions/setup-python"
    return f"{repositorio}@{par[0]} # {par[1]}"


def recusa_do_settings(motivo: str) -> RecusaDoCi:
    """A recusa de um settings que não fixa a versão do plugin, com o motivo entre parênteses."""
    return RecusaDoCi(
        f"{PREFIXO}o {SETTINGS} não fixa a versão do plugin ({motivo}); rode harness.py iniciar --conferir"
    )


def ref_do_settings(texto: str | None) -> str | None:
    """A `ref` do `extraKnownMarketplaces.ela-harness.source` do settings, None se `texto` é None (settings ausente),
    ou a `RecusaDoCi` do settings. O motivo `fora do UTF-8` não sai daqui, que recebe texto já decodificado."""
    if texto is None:
        return None
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as erro:
        raise recusa_do_settings(f"JSON malformado na linha {erro.lineno}") from erro
    if not isinstance(dados, dict):
        raise recusa_do_settings("não é um objeto JSON")
    for chave in ("extraKnownMarketplaces", "ela-harness", "source", "ref"):
        if not isinstance(dados, dict) or chave not in dados:
            dados = None
            break
        dados = dados[chave]
    if not isinstance(dados, str) or not dados:
        raise recusa_do_settings("sem extraKnownMarketplaces.ela-harness.source.ref")
    return dados


def versao_do_nucleo() -> str:
    """O `version` do `.claude-plugin/plugin.json` do plugin carregado."""
    manifesto = caminho.RAIZ_DO_PLUGIN / ".claude-plugin" / "plugin.json"
    return json.loads(comum.ler_texto(manifesto))["version"]


def conferir_versao(ref: str, versao: str) -> None:
    """Recusa quando a `ref` do settings não é a tag da versão do núcleo carregado."""
    if ref != "v" + versao:
        raise RecusaDoCi(
            f"{PREFIXO}o plugin carregado é v{versao} e o {SETTINGS} fixa {ref}; reinstale o plugin"
        )


def texto(trilha: str, ramo: str, ref: str) -> str:
    """O YAML do `harness.yml` da trilha (`desenvolvimento` ou `planejamento`), com o ramo e a `ref` dados."""
    return _MOLDE.format(
        primeira=_PRIMEIRA_LINHA,
        stack=_LINHA_DA_STACK if trilha == perfil_comum.DESENVOLVIMENTO else "",
        ramo=ramo,
        checkout=uses(CHECKOUT),
        distribuicao=DISTRIBUICAO,
        ref=ref,
        falha=_FALHA_SEM_NUCLEO.format(distribuicao=DISTRIBUICAO, ref=ref),
        trilha=trilha,
    )


def gerar(ler: Callable[[str], str | None], trilha: str, ramo: str, versao: str) -> dict[str, str]:
    """`{}` sem settings; senão `{CAMINHO: texto}`, com a `ref` do settings, que tem de ser `v<versao>`. As recusas
    sobem."""
    ref = ref_do_settings(ler(SETTINGS))
    if ref is None:
        return {}
    conferir_versao(ref, versao)
    return {CAMINHO: texto(trilha, ramo, ref)}
