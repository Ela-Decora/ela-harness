"""O texto do `.github/workflows/harness.yml` de cada projeto (spec do CI dos projetos, §4).

É uma função pura da trilha, do ramo principal, da `ref` do plugin que o `.claude/settings.json` fixa e, no
desenvolvimento, das verificações do momento `finalizar`, que viram a matriz do job `verificacao`.

O `gerar` lê o settings pelo `ler` que recebe e devolve `{}` quando ele não existe. As recusas sobem como
`RecusaDoCi`, com a linha inteira em `.motivo`. Os SHAs das actions moram aqui, numa definição só, que o gerador e os
testes dos `action.yml` e do `ci/planejamento/diagramas.yml` leem.
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
SETUP_NODE = ("49933ea5288caeca8642d1e84afbd3f7d6820020", "v4.4.0")
_ACTIONS = {
    CHECKOUT: "actions/checkout", SETUP_PYTHON: "actions/setup-python", SETUP_NODE: "actions/setup-node",
}

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

_PASSOS_DO_NUCLEO = """      - id: nucleo
        uses: {checkout}
        with:
          repository: {distribuicao}
          ref: {ref}
          path: .harness-nucleo
      - if: failure() && steps.nucleo.outcome == 'failure'
        run: |
          echo "{falha}"
"""

_AVISOS = """# As actions vão fixadas por SHA, que sobe com a versão do plugin: um PR do Dependabot neste arquivo fica \
vermelho.
# Se o run cai antes de qualquer passo, a causa provável é a política de actions da conta do GitHub.
"""

_MOLDE_DO_PLANEJAMENTO = """{primeira}
""" + _AVISOS + """name: harness
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
{passos}      - uses: ./.harness-nucleo/ci/planejamento
"""

_MOLDE_DO_DESENVOLVIMENTO = """{primeira}
{stack}""" + _AVISOS + """name: harness
on:
  pull_request:
    branches: [{ramo}]
permissions:
  contents: read
concurrency:
  group: harness-${{{{ github.ref }}}}
  cancel-in-progress: true
jobs:
  invariantes:
    name: invariantes
    runs-on: ubuntu-24.04
    steps:
      - uses: {checkout}
        with:
          fetch-depth: 0
{passos}      - uses: ./.harness-nucleo/ci/desenvolvimento
        with:
          passo: invariantes
{verificacao}  harness:
    name: harness
    if: always()
    needs: [{precisa}]
    runs-on: ubuntu-24.04
    steps:
      - env:
          RESULTADOS: ${{{{ join(needs.*.result, ' ') }}}}
        run: |
          echo "$RESULTADOS"
          for resultado in $RESULTADOS; do [ "$resultado" = success ] || exit 1; done
"""

_JOB_DAS_VERIFICACOES = """  verificacao:
    name: "verificação: ${{{{ matrix.verificacao }}}}"
    runs-on: ubuntu-24.04
    strategy:
      fail-fast: false
      matrix:
        verificacao: [{nomes}]
    steps:
      - uses: {checkout}
""" + "{passos}" + """      - uses: ./.harness-nucleo/ci/desenvolvimento
        with:
          verificacao: ${{{{ matrix.verificacao }}}}
"""


class RecusaDoCi(Exception):
    """O `harness.yml` não se gera. `motivo` é a linha inteira da recusa."""

    def __init__(self, motivo: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo


def uses(par: tuple[str, str]) -> str:
    """O `uses` de uma action fixada: `<repo>@<sha> # <versão>`, a partir de `CHECKOUT`, `SETUP_PYTHON` ou
    `SETUP_NODE`."""
    return f"{_ACTIONS[par]}@{par[0]} # {par[1]}"


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
            f"{PREFIXO}o plugin carregado é v{versao} e o {SETTINGS} fixa {ref}; reinstale o plugin e depois "
            "apague o link .claude/harness/nucleo ou abra uma sessão nova"
        )


def texto(trilha: str, ramo: str, ref: str, verificacoes: tuple[str, ...] = ()) -> str:
    """O YAML do `harness.yml` da trilha (`desenvolvimento` ou `planejamento`), com o ramo e a `ref` dados. No
    desenvolvimento, `verificacoes` são os nomes do momento `finalizar`, um job cada; sem nenhum, o job `verificacao`
    não existe. O planejamento ignora `verificacoes`."""
    checkout = uses(CHECKOUT)
    passos = _PASSOS_DO_NUCLEO.format(
        checkout=checkout, distribuicao=DISTRIBUICAO, ref=ref,
        falha=_FALHA_SEM_NUCLEO.format(distribuicao=DISTRIBUICAO, ref=ref),
    )
    if trilha != perfil_comum.DESENVOLVIMENTO:
        return _MOLDE_DO_PLANEJAMENTO.format(
            primeira=_PRIMEIRA_LINHA, ramo=ramo, checkout=checkout, passos=passos
        )
    nomes = ", ".join(json.dumps(nome, ensure_ascii=False) for nome in verificacoes)
    job = _JOB_DAS_VERIFICACOES.format(checkout=checkout, nomes=nomes, passos=passos) if verificacoes else ""
    return _MOLDE_DO_DESENVOLVIMENTO.format(
        primeira=_PRIMEIRA_LINHA, stack=_LINHA_DA_STACK, ramo=ramo, checkout=checkout, passos=passos,
        verificacao=job, precisa="invariantes, verificacao" if verificacoes else "invariantes",
    )


def gerar(ler: Callable[[str], str | None], trilha: str, ramo: str, versao: str,
          verificacoes: tuple[str, ...] = ()) -> dict[str, str]:
    """`{}` sem settings; senão `{CAMINHO: texto}`, com a `ref` do settings, que tem de ser `v<versao>`, e as
    `verificacoes` dadas. As recusas sobem."""
    ref = ref_do_settings(ler(SETTINGS))
    if ref is None:
        return {}
    conferir_versao(ref, versao)
    return {CAMINHO: texto(trilha, ramo, ref, verificacoes)}
