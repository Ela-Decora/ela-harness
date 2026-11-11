"""Parte comum do perfil, às duas trilhas: `[projeto]`, `[guarda]` e a trilha do perfil.

Traz também a leitura do TOML e os auxiliares de validação que o perfil de planejamento e o de desenvolvimento usam.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python antes do 3.11: tenta o pacote `tomli`; sem ele, `ler_dados` recusa com uma linha de motivo
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        tomllib = None

import comum
import segredos

PLANEJAMENTO = "planejamento"
DESENVOLVIMENTO = "desenvolvimento"
TRILHAS = (PLANEJAMENTO, DESENVOLVIMENTO)

_CHAVES_DO_PROJETO = ("nome", "harness")
_CHAVES_DA_GUARDA = ("proibidos", "segredos_isentos", "segredos")


class PerfilInvalido(Exception):
    """O perfil não serve. `mensagem` começa por `perfil inválido: ` e cabe numa linha."""

    def __init__(self, motivo: str):
        mensagem = "perfil inválido: " + motivo.replace("\r", "\\r").replace("\n", "\\n")
        super().__init__(mensagem)
        self.mensagem = mensagem


@dataclass(frozen=True)
class PerfilComum:
    """`[projeto]` e `[guarda]`: o nome, a trilha, os caminhos proibidos, os padrões de segredo do perfil, como pares
    (nome, expressão) na ordem do arquivo, e os caminhos isentos da busca de segredo."""

    nome: str
    harness: str
    proibidos: tuple[str, ...] = ()
    segredos: tuple[tuple[str, str], ...] = ()
    segredos_isentos: tuple[str, ...] = ()


def secao(dados: dict, nome: str) -> dict:
    valor = dados.get(nome)
    if valor is None:
        raise PerfilInvalido(f"falta a seção [{nome}]")
    if not isinstance(valor, dict):
        raise PerfilInvalido(f"[{nome}] deve ser uma tabela")
    return valor


def texto(tabela: dict, chave: str, onde: str) -> str:
    if chave not in tabela:
        raise PerfilInvalido(f"falta a chave {onde}.{chave}")
    valor = tabela[chave]
    if not isinstance(valor, str) or not valor.strip():
        raise PerfilInvalido(f"{onde}.{chave} deve ser um texto não vazio")
    return valor


def textos(tabela: dict, chave: str, onde: str, vazia: bool = True) -> tuple[str, ...]:
    if chave not in tabela:
        raise PerfilInvalido(f"falta a chave {onde}.{chave}")
    valor = tabela[chave]
    if not isinstance(valor, list) or not all(isinstance(item, str) and item.strip() for item in valor):
        raise PerfilInvalido(f"{onde}.{chave} deve ser uma lista de textos não vazios")
    if not valor and not vazia:
        raise PerfilInvalido(f"{onde}.{chave} não pode ser uma lista vazia")
    return tuple(valor)


def normalizado(caminho, onde: str) -> None:
    if isinstance(caminho, str) and not comum.caminho_normalizado(caminho):
        raise PerfilInvalido(f"caminho não normalizado em {onde}: {caminho}")


def chaves(tabela: dict, chaves: tuple[str, ...], onde: str) -> None:
    """Recusa a chave fora de `chaves` e, depois, a que falta, as duas na ordem."""
    sem_desconhecida(tabela, chaves, onde)
    ausente = next((chave for chave in chaves if chave not in tabela), None)
    if ausente is not None:
        raise PerfilInvalido(f"falta a chave {onde}.{ausente}")


def sem_desconhecida(tabela: dict, permitidas: tuple[str, ...], onde: str) -> None:
    """Recusa a primeira chave, na ordem do arquivo, fora de `permitidas`."""
    desconhecida = next((chave for chave in tabela if chave not in permitidas), None)
    if desconhecida is not None:
        raise PerfilInvalido(f"{onde} com chave desconhecida: {desconhecida}")


def subtabela(tabela: dict, chave: str, onde: str, obrigatoria: bool = True) -> dict | None:
    """A tabela aninhada em `<onde>.<chave>`; ausente, recusa, ou None quando não é obrigatória."""
    if chave not in tabela:
        if obrigatoria:
            raise PerfilInvalido(f"falta a chave {onde}.{chave}")
        return None
    valor = tabela[chave]
    if not isinstance(valor, dict):
        raise PerfilInvalido(f"{onde}.{chave} deve ser uma tabela")
    return valor


def padroes_de_caminho(tabela: dict, chave: str, onde: str) -> tuple[str, ...]:
    """Os padrões de caminho de `<onde>.<chave>`, relativos à raiz e normalizados, com `**` só como último segmento,
    depois de `/`; a chave ausente dá a lista vazia."""
    if chave not in tabela:
        return ()
    padroes = textos(tabela, chave, onde)
    for padrao in padroes:
        normalizado(padrao, f"{onde}.{chave}")
        segmentos = padrao.split("/")
        if any("**" in segmento for segmento in segmentos[:-1]) or (
                "**" in segmentos[-1] and (segmentos[-1] != "**" or len(segmentos) == 1)):
            raise PerfilInvalido(f"{onde}.{chave}: ** só como último segmento: {padrao}")
    return padroes


def _segredos(guarda: dict) -> tuple[tuple[str, str], ...]:
    """`[guarda.segredos]`: cada nome no formato, fora dos do núcleo, com uma expressão que compila e não casa com o
    texto vazio."""
    tabela = subtabela(guarda, "segredos", "guarda", obrigatoria=False) or {}
    do_nucleo = {nome for nome, _ in segredos.NUCLEO}
    pares = []
    for nome, valor in tabela.items():
        if not segredos.RE_NOME.fullmatch(nome):
            raise PerfilInvalido(f"guarda.segredos: nome fora do formato {segredos.RE_NOME.pattern}: {nome}")
        if nome in do_nucleo:
            raise PerfilInvalido(f"guarda.segredos.{nome} é um padrão do núcleo")
        if not isinstance(valor, str) or not valor.strip():
            raise PerfilInvalido(f"guarda.segredos.{nome} deve ser um texto não vazio")
        try:
            compilado = re.compile(valor)
        except re.error as erro:
            raise PerfilInvalido(f"guarda.segredos.{nome}: expressão inválida: {erro}") from None
        if compilado.search("") is not None:
            raise PerfilInvalido(f"guarda.segredos.{nome} casa com texto vazio")
        pares.append((nome, valor))
    return tuple(pares)


def validar(dados: dict) -> PerfilComum:
    """Confere a parte comum do perfil já lido do TOML: o `[projeto]` (a tabela, a chave desconhecida, o `nome` e o
    `harness`) e, quando existe, o `[guarda]` (a tabela, a chave desconhecida, o `proibidos`, o `segredos_isentos` e o
    `segredos`). Lança PerfilInvalido no primeiro problema; as outras tabelas ficam com o carregador da trilha."""
    projeto = secao(dados, "projeto")
    sem_desconhecida(projeto, _CHAVES_DO_PROJETO, "projeto")
    nome = texto(projeto, "nome", "projeto")
    harness = projeto.get("harness", PLANEJAMENTO)
    if harness not in TRILHAS:
        raise PerfilInvalido(f"projeto.harness: {harness}; use {comum.juntar(TRILHAS, 'ou')}")
    if "guarda" not in dados:
        return PerfilComum(nome, harness)
    guarda = secao(dados, "guarda")
    sem_desconhecida(guarda, _CHAVES_DA_GUARDA, "guarda")
    proibidos = padroes_de_caminho(guarda, "proibidos", "guarda")
    isentos = padroes_de_caminho(guarda, "segredos_isentos", "guarda")
    return PerfilComum(nome, harness, proibidos, _segredos(guarda), isentos)


def _exigir_leitor_de_toml() -> None:
    """Python sem leitor de TOML vira PerfilInvalido, numa linha com o motivo e o remédio."""
    if tomllib is None:
        versao = ".".join(str(parte) for parte in sys.version_info[:3])
        raise PerfilInvalido(
            f"ler o perfil em TOML pede Python 3.11 ou mais novo, ou o pacote tomli (pip3 install --user tomli); "
            f"este é o {versao}"
        )


def dados_do_texto(conteudo: str, caminho: str) -> dict:
    """O TOML do `conteudo`, lido. Python sem leitor de TOML ou TOML malformado vira PerfilInvalido, que cita o
    `caminho` de onde o texto veio."""
    _exigir_leitor_de_toml()
    try:
        return tomllib.loads(conteudo)
    except tomllib.TOMLDecodeError as erro:
        raise PerfilInvalido(f"TOML malformado em {caminho}: {erro}") from None


def ler_dados(caminho: Path) -> dict:
    """O TOML em `caminho`, lido. Python sem leitor de TOML, arquivo ausente, ilegível, fora do UTF-8 ou malformado
    vira PerfilInvalido."""
    _exigir_leitor_de_toml()
    try:
        conteudo = comum.ler_texto(caminho)
    except FileNotFoundError:
        raise PerfilInvalido(f"arquivo ausente: {caminho}") from None
    except UnicodeDecodeError:
        raise PerfilInvalido(f"arquivo não está em UTF-8: {caminho}") from None
    except OSError as erro:
        raise PerfilInvalido(f"arquivo ilegível: {caminho} ({erro.strerror or type(erro).__name__})") from None
    return dados_do_texto(conteudo, str(caminho))


def carregar(raiz: Path) -> PerfilComum:
    """A parte comum do perfil em `<raiz>/.claude/perfil.toml`, validada."""
    return validar(ler_dados(raiz / comum.CAMINHO_PERFIL))


def trilha(raiz: Path) -> str:
    """A trilha do perfil da raiz: `desenvolvimento` só com o TOML legível e `[projeto] harness = "desenvolvimento"`;
    em qualquer outro caso, `planejamento`. Nunca lança: quem recusa o perfil é o carregador da trilha."""
    try:
        dados = ler_dados(raiz / comum.CAMINHO_PERFIL)
    except PerfilInvalido:
        return PLANEJAMENTO
    return trilha_dos_dados(dados)


def trilha_dos_dados(dados: dict) -> str:
    """A trilha de um TOML já lido: `desenvolvimento` só com `[projeto] harness = "desenvolvimento"`; em qualquer outro
    caso, inclusive sem a tabela `[projeto]`, `planejamento`."""
    projeto = dados.get("projeto")
    if isinstance(projeto, dict) and projeto.get("harness") == DESENVOLVIMENTO:
        return DESENVOLVIMENTO
    return PLANEJAMENTO
