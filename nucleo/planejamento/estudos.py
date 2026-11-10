"""Estudos do assessor (spec da fase 2b, §8.2): lê o cabeçalho de cada estudo da pasta do perfil e diz em que
situação está a decisão."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import comum

AJUDA = """\
Lista os estudos do assessor, na pasta `caminhos.estudos`, e a situação da decisão de cada um.

Uma linha por estudo `.md`, em ordem de nome, e a contagem da pasta toda no fim. Com `--pendentes`, só os com decisão
por registrar e os ilegíveis, porque um ilegível pode esconder uma decisão fora da forma. Sai sempre com 0, mesmo com
a pasta ilegível (`pasta de estudos ilegível: <pasta> (<motivo>)`); sem estudo, `nenhum estudo (<pasta>)`.

```text
<arquivo>: <tema> — decisão pendente
<arquivo>: <tema> — decidida em <AAAA-MM-DD>, registro pendente
<arquivo>: <tema> — registrada em <onde>
<arquivo>: ilegível (<motivo>)
<N> estudos, <n> com decisão por registrar, <k> ilegíveis      (sempre; o ", <k> ilegíveis" só com algum ilegível)
```

Formato: o script lê só o cabeçalho, até a primeira linha em branco, e dele só as linhas `Tema:` e `Decisão:`; o
resto do estudo é da skill `assessor`. `Decisão:` aceita `pendente`, `<opção> em <AAAA-MM-DD>, registro pendente` ou
`<opção> em <AAAA-MM-DD>, registrada em <arquivo>`. Outra forma, data inválida, `Tema:` vazio ou linha ausente
deixam o estudo ilegível.
"""

PENDENTE = "pendente"
REGISTRO_PENDENTE = "registro pendente"
REGISTRADA = "registrada"
ILEGIVEL = "ilegível"

_TEMA = "Tema:"
_DECISAO = "Decisão:"
# As duas formas com data (spec §5.3). O `.+?` deixa a opção conter " em ": a data é a última que fecha a forma.
_RE_REGISTRO_PENDENTE = re.compile(r"(.+?) em ([0-9]{4}-[0-9]{2}-[0-9]{2}), registro pendente")
_RE_REGISTRADA = re.compile(r"(.+?) em ([0-9]{4}-[0-9]{2}-[0-9]{2}), registrada em (\S.*)")


@dataclass(frozen=True)
class Estudo:
    """Um estudo da pasta: o nome do arquivo dentro dela e a situação da decisão, com o que o cabeçalho diz."""

    arquivo: str
    situacao: str
    tema: str = ""
    opcao: str = ""
    data: str = ""
    onde: str = ""  # só em REGISTRADA
    motivo: str = ""  # só em ILEGIVEL

    @property
    def por_registrar(self) -> bool:
        """O usuário decidiu e a decisão ainda não entrou no registro do projeto."""
        return self.situacao == REGISTRO_PENDENTE


def _cabecalho(texto: str) -> list[str]:
    """Linhas até a primeira linha em branco, sem o espaço do fim (e sem o `\\r` das quebras `\\r\\n`)."""
    linhas = []
    for linha in texto.split("\n"):
        linha = linha.rstrip()
        if not linha:
            break
        linhas.append(linha)
    return linhas


def _valor(cabecalho: list[str], rotulo: str) -> str | None:
    """O que vem depois do rótulo na primeira linha que começa por ele; None se nenhuma começa."""
    for linha in cabecalho:
        if linha.startswith(rotulo):
            return linha[len(rotulo):].strip()
    return None


def analisar(arquivo: str, texto: str) -> Estudo:
    """Situação do estudo pelas linhas `Tema:` e `Decisão:` do cabeçalho. O corpo não conta."""
    cabecalho = _cabecalho(texto)
    tema = _valor(cabecalho, _TEMA)
    if tema is None:
        return Estudo(arquivo, ILEGIVEL, motivo="sem linha Tema:")
    if not tema:
        return Estudo(arquivo, ILEGIVEL, motivo="Tema: vazio")
    decisao = _valor(cabecalho, _DECISAO)
    if decisao is None:
        return Estudo(arquivo, ILEGIVEL, motivo="sem linha Decisão:")
    if decisao == PENDENTE:
        return Estudo(arquivo, PENDENTE, tema)
    for regex, situacao in ((_RE_REGISTRO_PENDENTE, REGISTRO_PENDENTE), (_RE_REGISTRADA, REGISTRADA)):
        partes = regex.fullmatch(decisao)
        if partes is None:
            continue
        opcao, data = partes.group(1), partes.group(2)
        if not comum.data_valida(data):
            return Estudo(arquivo, ILEGIVEL, motivo=f"data inválida em Decisão: {data}")
        onde = partes.group(3) if situacao == REGISTRADA else ""
        return Estudo(arquivo, situacao, tema, opcao, data, onde)
    return Estudo(arquivo, ILEGIVEL, motivo="Decisão: fora das três formas")


def listar(pasta: Path) -> list[Estudo]:
    """Os `.md` da pasta, em ordem de nome. Pasta ausente devolve lista vazia; outro erro ao abrir a pasta sobe.

    Um arquivo que não se lê vira ILEGIVEL com o motivo, sem parar a lista.
    """
    try:
        nomes = sorted(caminho.name for caminho in pasta.iterdir())
    except FileNotFoundError:
        return []
    lista = []
    for nome in nomes:
        if not nome.endswith(".md"):
            continue
        caminho = pasta / nome
        try:
            if not caminho.is_file():
                continue
            texto = comum.ler_texto(caminho)
        except UnicodeDecodeError:
            lista.append(Estudo(nome, ILEGIVEL, motivo="não está em UTF-8"))
            continue
        except OSError as erro:
            lista.append(Estudo(nome, ILEGIVEL, motivo=comum.motivo_do_sistema(erro)))
            continue
        lista.append(analisar(nome, texto))
    return lista


def contar(pasta: Path) -> tuple[int, int]:
    """Quantos estudos têm decisão por registrar e quantos são ilegíveis. Para o hook: erro da pasta conta zero,
    nunca lança."""
    try:
        lista = listar(pasta)
    except OSError:
        return 0, 0
    return (sum(1 for estudo in lista if estudo.por_registrar),
            sum(1 for estudo in lista if estudo.situacao == ILEGIVEL))


def _linha(estudo: Estudo) -> str:
    if estudo.situacao == PENDENTE:
        return f"{estudo.arquivo}: {estudo.tema} — decisão pendente"
    if estudo.situacao == REGISTRO_PENDENTE:
        return f"{estudo.arquivo}: {estudo.tema} — decidida em {estudo.data}, registro pendente"
    if estudo.situacao == REGISTRADA:
        return f"{estudo.arquivo}: {estudo.tema} — registrada em {estudo.onde}"
    return f"{estudo.arquivo}: {ILEGIVEL} ({estudo.motivo})"


def formatar(estudos: list[Estudo], pasta: str, so_pendentes: bool = False) -> str:
    """Uma linha por estudo e a contagem no fim, que é da pasta toda.

    `so_pendentes` deixa os por registrar e os ilegíveis: um ilegível pode esconder uma decisão escrita fora da forma.
    """
    if not estudos:
        return f"nenhum estudo ({pasta})\n"
    linhas = [_linha(estudo) for estudo in estudos
              if not so_pendentes or estudo.por_registrar or estudo.situacao == ILEGIVEL]
    total = len(estudos)
    por_registrar = sum(1 for estudo in estudos if estudo.por_registrar)
    ilegiveis = sum(1 for estudo in estudos if estudo.situacao == ILEGIVEL)
    contagem = f"{total} {'estudo' if total == 1 else 'estudos'}, {por_registrar} com decisão por registrar"
    if ilegiveis:
        contagem += f", {ilegiveis} {'ilegível' if ilegiveis == 1 else 'ilegíveis'}"
    linhas.append(contagem)
    return "\n".join(linhas) + "\n"
