"""Leitor de Markdown comum às duas trilhas (spec 6c, §7.5 e §10): as linhas fora dos blocos de código, as seções, os itens de um campo e os links.

O `checar` importa estes nomes, que seguem valendo como `checar.<nome>`.
"""
from __future__ import annotations

import posixpath
import re
from urllib.parse import unquote

CERCA = "```"
# O destino entre `<...>`, ou sem espaço e com um nível de parênteses; o título depois dele fica de fora.
_RE_LINK = re.compile(r"\[[^\]]*\]\(\s*(?:<([^<>\n]*)>|((?:[^()\s]|\([^()\s]*\))+))")
# Código em linha: a abertura e o fechamento com o mesmo número de crases.
_RE_CODIGO_EM_LINHA = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)")


def _linhas(texto: str) -> list[str]:
    """Linhas do texto, sem o `\\r` final de cada uma e sem a linha vazia que o `\\n` final deixaria."""
    linhas = texto.split("\n")
    if linhas[-1] == "":
        linhas.pop()
    return [linha.rstrip("\r") for linha in linhas]


def _fora_de_blocos(linhas: list[str]) -> list[tuple[int, str]]:
    """(número da linha a partir de 1, linha) de tudo que está fora dos blocos cercados por três crases.

    A linha da cerca também sai. Uma cerca que nunca fecha ignora o resto do arquivo.
    """
    uteis = []
    dentro = False
    for numero, linha in enumerate(linhas, start=1):
        if linha.lstrip().startswith(CERCA):
            dentro = not dentro
        elif not dentro:
            uteis.append((numero, linha))
    return uteis


def linhas_fora_de_blocos(texto: str) -> list[tuple[int, str]]:
    """(número a partir de 1, linha sem o `\\r` do fim) de cada linha do texto fora dos blocos de três crases."""
    return _fora_de_blocos(_linhas(texto))


_RE_TITULO_DE_SECAO = re.compile(r"(#{1,6}) ")


def secoes(texto: str, inicio: str) -> list[tuple[int, str, list[tuple[int, str]]]]:
    """(linha do título, título, linhas) de cada título fora dos blocos de código que começa por `inicio` e tem o
    nível dele (o número de `#`).

    A seção vai do título, inclusive, até o próximo título de nível igual ou acima; as linhas são as de fora dos
    blocos de código, numeradas a partir de 1.
    """
    nivel = len(inicio) - len(inicio.lstrip("#"))
    achadas: list[tuple[int, str, list[tuple[int, str]]]] = []
    atual: list[tuple[int, str]] | None = None
    for numero, linha in _fora_de_blocos(_linhas(texto)):
        titulo = _RE_TITULO_DE_SECAO.match(linha)
        if titulo and len(titulo.group(1)) <= nivel:
            atual = None
            if len(titulo.group(1)) == nivel and linha.startswith(inicio):
                atual = []
                achadas.append((numero, linha.rstrip(), atual))
        if atual is not None:
            atual.append((numero, linha))
    return achadas


_RE_COMENTARIO_HTML = re.compile(r"<!--.*?-->")
_RE_ITEM_DE_LISTA = re.compile(r"(\s*)(?:[-*+]|[0-9]+[.)])(?:\s+(.*))?")
_RE_ITEM_NUMERADO = re.compile(r"(\s*)[0-9]+[.)](?:\s+(.*))?")


def _recuo(linha: str) -> int:
    return len(linha) - len(linha.lstrip())


def itens_do_campo(linhas: list[tuple[int, str]], rotulo: str) -> tuple[int, list[tuple[int, str]]] | None:
    """(linha do rótulo, [(linha, texto)] dos itens) do primeiro campo com o rótulo nas linhas dadas, ou None.

    O campo é o primeiro item de lista, com `-`, `*` ou `+`, que começa por `**<rótulo>:**` ou `**<rótulo>**:`. O
    valor na mesma linha é um item. Abaixo, a primeira linha não vazia decide o recuo dos itens: mais recuada que o
    campo, os itens ficam no recuo dela; item numerado (`N.` ou `N)`) no recuo do campo, os itens são os numerados
    nesse recuo; outra, nenhum item abaixo. O item de lista no recuo dos itens abre um item, com o texto sem o
    marcador; a linha mais recuada, com ou sem marcador, e a sem marcador no recuo dos itens continuam o item aberto,
    sem o marcador, juntadas com um espaço, e assim o subitem é parte do item de cima; sem item aberto, abrem um. Os
    comentários `<!-- ... -->` saem, e o item que fica vazio não conta. A linha em branco não corta a lista, que acaba
    na primeira linha não vazia com recuo menor que o dos itens e, nos numerados, também na primeira linha no recuo
    deles que não é item numerado.
    """
    campo = re.compile(r"(\s*)[-*+]\s+\*\*" + re.escape(rotulo) + r"(?::\*\*|\*\*:)(.*)")
    for posicao, (numero, linha) in enumerate(linhas):
        achado = campo.fullmatch(linha)
        if achado:
            break
    else:
        return None
    recuo_do_campo = len(achado.group(1))
    itens: list[tuple[int, str]] = []
    valor = _RE_COMENTARIO_HTML.sub("", achado.group(2)).strip()
    if valor:
        itens.append((numero, valor))
    abaixo = linhas[posicao + 1:]
    primeira = next((linha for _, linha in abaixo if linha.strip()), None)
    if primeira is not None and _recuo(primeira) > recuo_do_campo:
        recuo, numerados = _recuo(primeira), False
    elif primeira is not None and _recuo(primeira) == recuo_do_campo and _RE_ITEM_NUMERADO.fullmatch(primeira):
        recuo, numerados = recuo_do_campo, True
    else:
        return numero, itens
    for numero_abaixo, linha in abaixo:
        if not linha.strip():
            continue
        if _recuo(linha) < recuo:
            break
        no_recuo = _recuo(linha) == recuo
        if numerados and no_recuo and not _RE_ITEM_NUMERADO.fullmatch(linha):
            break
        item = _RE_ITEM_DE_LISTA.fullmatch(linha)
        texto = _RE_COMENTARIO_HTML.sub("", (item.group(2) or "") if item else linha).strip()
        if (item and no_recuo) or not itens:
            itens.append((numero_abaixo, texto))
        elif texto:
            itens[-1] = (itens[-1][0], f"{itens[-1][1]} {texto}".strip())
    return numero, [(linha, texto) for linha, texto in itens if texto]


def ler_links(texto: str) -> list[tuple[int, str]]:
    """(linha, destino) de cada link markdown `[...](...)` fora dos blocos de código e do código em linha, na ordem.

    O destino entre `<...>` volta sem os `<>`; o destino sem eles vai até o primeiro espaço e aceita um nível de
    parênteses, como em `a(1).md`. O título depois do destino fica de fora.
    """
    achados = []
    for numero, linha in _fora_de_blocos(_linhas(texto)):
        for achado in _RE_LINK.finditer(_RE_CODIGO_EM_LINHA.sub(" ", linha)):
            achados.append((numero, achado.group(1) if achado.group(1) is not None else achado.group(2)))
    return achados


def resolver_link(destino: str, caminho: str) -> str | None:
    """O destino do link resolvido a partir da pasta de `caminho`, relativo à raiz e normalizado.

    Saem o `#...` e o `?...`, e os `%xx` são decodificados; o `/...` parte da raiz. `None` para o destino vazio
    depois do corte, para o externo (com `:`) e para o que começa por `//`. O que sai da raiz volta como `..` ou
    `../...`.
    """
    alvo = unquote(re.split(r"[#?]", destino, maxsplit=1)[0])
    if not alvo or ":" in alvo or alvo.startswith("//"):
        return None
    base = "" if alvo.startswith("/") else posixpath.dirname(caminho)
    return posixpath.normpath(posixpath.join(base, alvo.lstrip("/")))
