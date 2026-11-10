"""As checagens dos diagramas da camada, em Mermaid, C4 e `.drawio`, sem rodar o Mermaid.

Os diagramas ficam em blocos de três crases do tipo `mermaid` nos documentos (spec 5a, §7). Aqui se conferem o tipo
de cada bloco, o bloco vazio, as chamadas do C4, os links relativos e o `.drawio` da nuvem com o `.drawio.svg`
exportado ao lado; a sintaxe Mermaid, só o validador em Node da pasta `ferramentas/`, na CI e local com Node.
"""
from __future__ import annotations

import base64
import binascii
import math
import os
import posixpath
import re
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path
from urllib.parse import unquote

import checar
import comum
import der
from perfil import Perfil

TIPOS_MERMAID = ("flowchart", "graph", "sequenceDiagram", "classDiagram", "stateDiagram-v2", "erDiagram",
                 "C4Context", "C4Container")
TIPOS_C4 = ("C4Context", "C4Container")
VAZIO = "bloco mermaid vazio"
CERCA_ABERTA = "cerca sem fechamento; feche o bloco com três crases"
FRONTMATTER_ABERTO = "frontmatter --- sem fechamento; feche com outra linha ---"

_CERCA_MERMAID = "```mermaid"
_COM_TECNOLOGIA = ("Container", "ContainerDb", "ContainerQueue")
_COM_DESCRICAO = ("Person", "System", "SystemDb", "SystemQueue")  # e as variantes `_Ext` destas e das de cima
_ELEMENTOS = ("Person", "System", "Container", "Component")  # prefixos; as fronteiras (`*Boundary`) não contam
_RE_CHAMADA = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)\s*\{?\s*")
_RE_INICIO_DE_CHAMADA = re.compile(r"\s*[A-Za-z_][A-Za-z0-9_]*\s*\(")
_RE_TITLE = re.compile(r"\s*title(?:\s|:|$)")
_RE_ITEM = re.compile(r"\s*(?:[-*+]|\d+[.)])\s+\S")


def _linhas(texto: str) -> list[str]:
    """Todas as linhas do texto, sem o `\\r` do fim; a linha N fica no índice N - 1."""
    return [linha.rstrip("\r") for linha in texto.split("\n")]


def blocos_mermaid(texto: str) -> list[tuple[int, list[tuple[int, str]]]]:
    """(linha da cerca de abertura, [(linha, texto)] do conteúdo) de cada bloco cuja cerca é ```` ```mermaid ````."""
    linhas = _linhas(texto)
    return [(cerca, conteudo) for cerca, conteudo in checar.blocos_de_codigo(texto)
            if linhas[cerca - 1].strip() == _CERCA_MERMAID]


def _fecha(linhas: list[str], cerca: int, conteudo: list[tuple[int, str]]) -> bool:
    """Se o bloco fecha: a linha logo depois do conteúdo existe e é uma cerca, pela regra do `checar`."""
    depois = conteudo[-1][0] if conteudo else cerca  # o número da linha seguinte é o índice dela
    return depois < len(linhas) and linhas[depois].lstrip().startswith(checar.CERCA)


def _frontmatter_aberto(conteudo: list[tuple[int, str]]) -> bool:
    """Se a primeira linha não vazia do bloco é `---` e nenhuma outra `---` vem depois dela."""
    cheias = [linha.strip() for _, linha in conteudo if linha.strip()]
    return bool(cheias) and cheias[0] == "---" and "---" not in cheias[1:]


def _uteis(conteudo: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """As linhas do bloco sem o frontmatter `---`, sem as em branco e sem os comentários `%%`."""
    linhas = list(conteudo)
    primeira = next((indice for indice, (_, linha) in enumerate(linhas) if linha.strip()), None)
    if primeira is not None and linhas[primeira][1].strip() == "---":
        fim = next((indice for indice in range(primeira + 1, len(linhas)) if linhas[indice][1].strip() == "---"), None)
        if fim is not None:
            linhas = linhas[fim + 1:]
    return [(numero, linha) for numero, linha in linhas if linha.strip() and not linha.strip().startswith("%%")]


def _tipo(uteis: list[tuple[int, str]]) -> str:
    return uteis[0][1].split()[0]


def conferir_mermaid(texto: str) -> list[tuple[int, str]]:
    """(linha da cerca, problema) de cada bloco Mermaid sem a cerca que fecha, com o frontmatter `---` aberto, de
    tipo fora de `TIPOS_MERMAID` ou vazio; a cerca aberta e o frontmatter aberto tomam o lugar das outras conferências.

    O tipo é a primeira linha útil, até o primeiro espaço. Vazio é o bloco que só tem a linha do tipo, `title` e
    comentários; o bloco com a linha do `der gerar` não conta, porque o DER ainda não foi gerado.
    """
    linhas = _linhas(texto)
    problemas: list[tuple[int, str]] = []
    use = ", ".join(TIPOS_MERMAID[:-1]) + " ou " + TIPOS_MERMAID[-1]
    for cerca, conteudo in blocos_mermaid(texto):
        if not _fecha(linhas, cerca, conteudo):
            problemas.append((cerca, CERCA_ABERTA))
            continue
        if _frontmatter_aberto(conteudo):
            problemas.append((cerca, FRONTMATTER_ABERTO))
            continue
        uteis = _uteis(conteudo)
        do_der = any(linha.strip() == der.MARCADOR for _, linha in conteudo)
        if uteis and _tipo(uteis) not in TIPOS_MERMAID:
            problemas.append((cerca, f"bloco mermaid de tipo {_tipo(uteis)}; use {use}"))
        elif not [linha for _, linha in uteis[1:] if not _RE_TITLE.match(linha)] and not do_der:
            problemas.append((cerca, VAZIO))
    return problemas


def _sem_comentario(linha: str) -> tuple[str, int]:
    """A linha sem o comentário `%%` do fim e o saldo de parênteses abertos, os dois fora das aspas."""
    aspas, saldo = False, 0
    for posicao, caractere in enumerate(linha):
        if caractere == '"':
            aspas = not aspas
        elif aspas:
            continue
        elif linha.startswith("%%", posicao):
            return linha[:posicao], saldo
        elif caractere == "(":
            saldo += 1
        elif caractere == ")":
            saldo -= 1
    return linha, saldo


def _instrucoes(uteis: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """(linha do início, texto) de cada instrução do bloco, sem o comentário do fim; a chamada que segue por várias
    linhas, até o parêntese fechar fora das aspas, vira uma só."""
    instrucoes: list[tuple[int, str]] = []
    abertos = 0
    for numero, linha in uteis:
        linha, saldo = _sem_comentario(linha)
        if abertos > 0:
            inicio, anterior = instrucoes.pop()
            numero, linha = inicio, f"{anterior} {linha.strip()}"
        else:
            abertos = 0
        instrucoes.append((numero, linha))
        abertos = abertos + saldo if _RE_INICIO_DE_CHAMADA.match(linha) else 0
    return instrucoes


def _argumentos(texto: str) -> tuple[list[str], dict[str, str]]:
    """Os argumentos de uma chamada, separados por vírgula fora das aspas e sem as aspas: os posicionais e os
    nomeados (`$nome=valor`), estes por nome."""
    partes, atual, aspas = [], "", False
    for caractere in texto:
        if caractere == '"':
            aspas = not aspas
        elif caractere == "," and not aspas:
            partes.append(atual)
            atual = ""
            continue
        atual += caractere
    partes.append(atual)
    posicionais, nomeados = [], {}
    for parte in (parte.strip() for parte in partes):
        nome = ""
        if parte.startswith("$"):
            if "=" not in parte:
                continue
            nome, parte = (pedaco.strip() for pedaco in parte[1:].split("=", 1))
        if len(parte) >= 2 and parte[0] == parte[-1] == '"':
            parte = parte[1:-1]
        if nome:
            nomeados[nome] = parte.strip()
        else:
            posicionais.append(parte.strip())
    return posicionais, nomeados


def _argumento(argumentos: tuple[list[str], dict[str, str]], indice: int, nome: str = "") -> str:
    """O argumento nomeado `$nome`, se houver, ou o posicional no índice."""
    posicionais, nomeados = argumentos
    if nome in nomeados:
        return nomeados[nome]
    return posicionais[indice] if indice < len(posicionais) else ""


def _com_legenda(linhas: list[str], fim: int) -> bool:
    """Se a primeira linha não vazia depois da linha `fim` (a cerca que fecha) é `Legenda:`, seguida de um item."""
    seguintes = [linha for linha in linhas[fim:] if linha.strip()]
    return len(seguintes) > 1 and seguintes[0].strip() == "Legenda:" and bool(_RE_ITEM.match(seguintes[1]))


def conferir_c4(texto: str) -> list[tuple[int, str]]:
    """(linha, problema) das chamadas de cada bloco `C4Context` e `C4Container`, e do bloco sem elemento ou sem a
    lista "Legenda:" logo depois, na linha da cerca. O bloco sem a cerca que fecha fica de fora: o `conferir_mermaid`
    o acusa."""
    linhas = _linhas(texto)
    problemas: list[tuple[int, str]] = []
    for cerca, conteudo in blocos_mermaid(texto):
        if not _fecha(linhas, cerca, conteudo):
            continue
        uteis = _uteis(conteudo)
        if not uteis or _tipo(uteis) not in TIPOS_C4:
            continue
        elementos = 0
        for numero, linha in _instrucoes(uteis[1:]):
            achado = _RE_CHAMADA.fullmatch(linha)
            if not achado:
                continue
            funcao, argumentos = achado.group(1), _argumentos(achado.group(2))
            alias, base = _argumento(argumentos, 0), funcao[:-len("_Ext")] if funcao.endswith("_Ext") else funcao
            if funcao.startswith(("Rel", "BiRel")):
                if not _argumento(argumentos, 2, "label"):
                    problemas.append((numero, f"{funcao}({alias}, {_argumento(argumentos, 1)}) sem rótulo"))
                continue
            if funcao.startswith(_ELEMENTOS) and not funcao.endswith("Boundary"):
                elementos += 1
            if base in _COM_TECNOLOGIA:
                if not _argumento(argumentos, 2, "techn"):
                    problemas.append((numero, f"{funcao}({alias}) sem tecnologia"))
                if not _argumento(argumentos, 3, "descr"):
                    problemas.append((numero, f"{funcao}({alias}) sem descrição"))
            elif base in _COM_DESCRICAO and not _argumento(argumentos, 2, "descr"):
                problemas.append((numero, f"{funcao}({alias}) sem descrição"))
        if not elementos:
            problemas.append((cerca, f"bloco {_tipo(uteis)} sem nenhum elemento"))
        fim = (conteudo[-1][0] if conteudo else cerca) + 1
        if not _com_legenda(linhas, fim):
            problemas.append((cerca, f'bloco {_tipo(uteis)} sem a lista "Legenda:" logo depois'))
    return sorted(problemas, key=lambda problema: problema[0])


def _existe_com_o_nome_exato(raiz: Path, relativo: str) -> bool:
    """Se o caminho existe com cada parte escrita como no disco: no disco que ignora maiúsculas (macOS), o link com a
    caixa errada resolve local, mas quebra no GitHub."""
    atual = raiz
    for parte in relativo.split("/"):
        if parte in ("", "."):
            continue
        try:
            if parte not in os.listdir(atual):
                return False
        except OSError:
            return False
        atual = atual / parte
    return True


def conferir_links(raiz: Path, relativo: str, texto: str, perfil: Perfil) -> list[tuple[int, str]]:
    """(linha, problema) de cada link de `checar.ler_links` que o `checar.recusa_do_link` recusa, resolvido pelo
    `checar.resolver_link`, com a caixa de cada parte como no disco. Link externo, só de âncora ou que começa por `//`
    fica de fora. O que sai da raiz e o ausente não resolvem; a pasta e o caminho excluído da passagem têm mensagem
    própria. A mensagem cita o destino como está escrito, sem os `<>`."""

    def arquivo(caminho: str) -> bool:
        return _existe_com_o_nome_exato(raiz, caminho) and (raiz / caminho).is_file()

    def pasta(caminho: str) -> bool:
        return _existe_com_o_nome_exato(raiz, caminho) and (raiz / caminho).is_dir()

    problemas: list[tuple[int, str]] = []
    for numero, destino in checar.ler_links(texto):
        resolvido = checar.resolver_link(destino, relativo)
        if resolvido is None:
            continue
        recusa = checar.recusa_do_link(resolvido, perfil, arquivo, pasta)
        if recusa in (checar.LINK_FORA, checar.LINK_AUSENTE):
            problemas.append((numero, f"link {destino} não resolve"))
        elif recusa == checar.LINK_PASTA:
            problemas.append((numero, f"link {destino} é uma pasta; linke um arquivo"))
        elif recusa:
            problemas.append((numero, f"link {destino} {recusa}"))
    return problemas


def _numero(valor: str) -> float | str:
    """O valor como `float`, ou o texto quando não é número finito: `NaN` nunca é igual a si mesmo."""
    try:
        numero = float(valor)
    except ValueError:
        return valor
    return numero if math.isfinite(numero) else valor


def _atributos(elemento: ET.Element) -> tuple:
    """Os atributos do elemento, em ordem do nome, com os números como `float`."""
    return tuple(sorted((chave, _numero(valor)) for chave, valor in elemento.attrib.items()))


def _descompactar(texto: str) -> str:
    """O `mxGraphModel` de um `<diagram>` compactado: `base64`, `deflate` cru e `encodeURIComponent`."""
    try:
        return unquote(zlib.decompress(base64.b64decode(texto), -15).decode("utf-8"))
    except (binascii.Error, zlib.error, UnicodeDecodeError) as erro:
        raise ValueError(f"diagrama compactado ilegível: {erro}") from None


def _compactado(diagrama: ET.Element) -> bool:
    """Se o `<diagram>` traz o modelo compactado em texto: sem `mxGraphModel` filho e com texto que não é só espaço."""
    return diagrama.find("mxGraphModel") is None and bool((diagrama.text or "").strip())


def _modelos(documento: ET.Element) -> list[tuple[int, ET.Element]]:
    """Os `mxGraphModel` do documento com a página de cada um: ele mesmo, na página 1, ou o de cada `<diagram>`, na
    posição dele no arquivo a partir de 1, descompactado quando vem em texto."""
    if documento.tag == "mxGraphModel":
        return [(1, documento)]
    modelos = []
    for pagina, diagrama in enumerate(documento.iter("diagram"), start=1):
        filho = diagrama.find("mxGraphModel")
        if filho is not None:
            modelos.append((pagina, filho))
        elif _compactado(diagrama):
            modelos.append((pagina, ET.fromstring(_descompactar(diagrama.text.strip()))))
    return modelos


def celulas(xml: str) -> dict[tuple[int, str], tuple]:
    """De cada `mxCell`, por página e `id`: `parent`, `value`, `style`, `vertex`, `edge`, `source`, `target` e a
    geometria.

    A geometria é `None` sem `mxGeometry`, ou os atributos dele e os de cada `mxPoint` dele, na ordem. A célula dentro
    de `UserObject` ou `object` tem o `id` e o rótulo (`label`) neles. Lança `ValueError` com o motivo no XML inválido.
    """
    try:
        modelos = _modelos(ET.fromstring(xml))
    except ET.ParseError as erro:
        raise ValueError(str(erro)) from None
    achadas: dict[tuple[int, str], tuple] = {}
    for pagina, modelo in modelos:
        raiz_do_modelo = modelo.find("root")
        for filho in raiz_do_modelo if raiz_do_modelo is not None else ():
            if filho.tag == "mxCell":
                celula, id_, valor = filho, filho.get("id"), filho.get("value")
            elif filho.tag in ("UserObject", "object") and filho.find("mxCell") is not None:
                celula, id_, valor = filho.find("mxCell"), filho.get("id"), filho.get("label")
            else:
                continue
            geometria = celula.find("mxGeometry")
            if geometria is not None:
                geometria = (_atributos(geometria), tuple(map(_atributos, geometria.iter("mxPoint"))))
            achadas[(pagina, id_)] = (celula.get("parent"), valor, celula.get("style"), celula.get("vertex"), celula.get("edge"),
                            celula.get("source"), celula.get("target"), geometria)
    return achadas


def _paginas(mapa: dict[tuple[int, str], tuple]) -> int:
    """A última página com células; com 2 ou mais, a página entra nas mensagens."""
    return max((pagina for pagina, _ in mapa), default=0)


def _celulas_do_arquivo(caminho: Path) -> dict[tuple[int, str], tuple]:
    """As células do `.drawio`; arquivo ilegível ou fora de UTF-8 também é `ValueError`."""
    try:
        return celulas(comum.ler_texto(caminho))
    except OSError as erro:
        raise ValueError(erro.strerror or type(erro).__name__) from None


def svg_em_dia(raiz: Path, caminho: str) -> list[str]:
    """Problemas do `.drawio.svg` ao lado do `.drawio` em `caminho`, relativo à raiz: ausente, sem a cópia do
    diagrama no atributo `content`, ou com células diferentes das do `.drawio`, página por página."""
    arquivo = posixpath.basename(caminho)
    svg = raiz / (caminho + ".svg")
    if not svg.is_file():
        return [f'{arquivo}.svg ausente; exporte em SVG com "Include a copy of my diagram"']
    try:
        copia = ET.fromstring(comum.ler_texto(svg)).get("content")
        do_svg = celulas(copia) if copia else {}
    except (ET.ParseError, ValueError, OSError):
        do_svg = {}
    if not do_svg:
        return [f'{arquivo}.svg sem a cópia do diagrama; exporte com "Include a copy of my diagram"']
    try:
        do_drawio = _celulas_do_arquivo(raiz / caminho)
    except ValueError as erro:
        return [f"{arquivo}: XML inválido ({erro})"]
    ids = list(do_drawio) + [id_ for id_ in do_svg if id_ not in do_drawio]
    diferentes = [chave for chave in ids if do_drawio.get(chave) != do_svg.get(chave)]
    if diferentes:
        pagina, primeira = diferentes[0]
        if max(_paginas(do_drawio), _paginas(do_svg)) > 1:
            primeira += f" na página {pagina}"
        return [f"{arquivo}.svg de outra versão do {arquivo} ({len(diferentes)} células diferem, "
                f"primeira {primeira}); exporte de novo"]
    return []


def conferir_drawio(raiz: Path, caminho: str) -> list[str]:
    """Problemas do `.drawio` em `caminho`, relativo à raiz, e os do `.drawio.svg` ao lado (spec 5a, §7.3).

    As células `0` e `1` são conferidas no arquivo inteiro; as pontas de cada aresta, na página dela. Com 2 páginas ou
    mais, a página entra nas mensagens das arestas e dos vértices."""
    arquivo = posixpath.basename(caminho)
    try:
        mapa = _celulas_do_arquivo(raiz / caminho)
    except ValueError as erro:
        return [f"{arquivo}: XML inválido ({erro})"]
    problemas = []
    documento = ET.fromstring(comum.ler_texto(raiz / caminho))
    if documento.get("compressed") == "true":
        problemas.append(f'{arquivo}: compressed="true"; grave sem compressão')
    elif any(_compactado(diagrama) for diagrama in documento.iter("diagram")):
        problemas.append(f"{arquivo}: diagrama compactado; grave sem compressão")
    ids = {id_ for _, id_ in mapa}
    if "0" not in ids or "1" not in ids:
        problemas.append(f"{arquivo}: sem as células 0 e 1")
    varias = _paginas(mapa) > 1
    for (pagina, id_), (_, valor, estilo, vertice, aresta, source, target, _) in mapa.items():
        onde = f"{arquivo}, página {pagina}" if varias else arquivo
        if aresta == "1":
            for ponta, alvo in (("source", source), ("target", target)):
                if not alvo:
                    problemas.append(f"{onde}: aresta {id_} sem {ponta}; ligue as duas pontas a vértices")
                elif (pagina, alvo) not in mapa:
                    problemas.append(f"{onde}: aresta {id_} com {ponta} {alvo}, que não existe")
        elif vertice == "1" and not (valor or "").strip() and (estilo or "").split(";")[0] != "group":
            problemas.append(f"{onde}: vértice {id_} sem rótulo")
    return problemas + svg_em_dia(raiz, caminho)


def _drawio_da_pasta(raiz: Path, relativo: str) -> list[str]:
    """Os problemas de cada `.drawio` da pasta do documento, sem as subpastas."""
    pasta = posixpath.dirname(relativo)
    if not (raiz / pasta).is_dir():
        return []
    return [problema for arquivo in sorted((raiz / pasta).glob("*.drawio")) if arquivo.is_file()
            for problema in conferir_drawio(raiz, posixpath.join(pasta, arquivo.name))]


def verificacoes(raiz: Path, perfil: Perfil, relativo: str, texto: str) -> list[checar.Resultado]:
    """As verificações dos diagramas no `checar` de um documento da camada: `mermaid`, `c4`, `links` e `drawio`."""
    drawio = _drawio_da_pasta(raiz, relativo)
    return [
        checar.de_ocorrencias("mermaid", conferir_mermaid(texto)),
        checar.de_ocorrencias("c4", conferir_c4(texto)),
        checar.de_ocorrencias("links", conferir_links(raiz, relativo, texto, perfil)),
        checar.Resultado("drawio", not drawio, len(drawio), None, drawio),
    ]
