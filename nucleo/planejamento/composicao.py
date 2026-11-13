"""A composição do pacote de um módulo (spec "Menos voltas", §6.1): os rascunhos que ele compõe, pelos links fora
dos de outro módulo. Só lê o texto que recebe; o `proximo` e o `dossie` a usam."""
from __future__ import annotations

import posixpath
import re
from typing import Callable

import checar
import comum
import rastreio
from perfil import Perfil

LIGADOS = "ligados"

# No texto normalizado (sem acento e em minúsculas): as frases que marcam o que é de outro módulo.
_RE_DE_OUTRO_MODULO = re.compile(r"(?<!\w)(?:outros\s+modulos|so\s+le)(?!\w)")
_RE_ANOTACAO = re.compile(r"\(\s*modulo\s+([^)]*?)\s*\)")
_RE_TITULO = re.compile(r"(#{1,6})\s")
_RE_ITEM = re.compile(r"\s*(?:[-*+]|[0-9]+[.)])(?:\s|$)")
_RE_COMENTARIO = re.compile(r"<!--.*?-->")


def _de_outro_modulo(linha: str) -> bool:
    return bool(_RE_DE_OUTRO_MODULO.search(rastreio.normalizar(_RE_COMENTARIO.sub("", linha))))


def _anotada_de_outro(linha: str, nome_do_modulo: str) -> bool:
    """A linha traz uma anotação `(módulo <nome>)` cujo nome, normalizado e com hífens no lugar dos espaços, não está
    no nome do arquivo do módulo."""
    for achado in _RE_ANOTACAO.finditer(rastreio.normalizar(linha)):
        if "-".join(achado.group(1).split()) not in nome_do_modulo:
            return True
    return False


def _linhas_excluidas(texto: str, modulo: str) -> set[int]:
    """Os números das linhas, fora dos blocos de código, cujos links não compõem o pacote: as da seção de nível 2 com
    "outros módulos" no título; a linha que não é item e diz "outros módulos" ou "só lê", com a lista que ela abre, até
    a próxima linha não vazia que não é item nem continuação recuada; e as com a anotação de outro módulo."""
    nome = rastreio.normalizar(posixpath.basename(modulo))
    nome = nome[: -len(".md")] if nome.endswith(".md") else nome
    excluidas: set[int] = set()
    na_secao = False
    na_lista = False
    for numero, linha in checar.linhas_fora_de_blocos(texto):
        titulo = _RE_TITULO.match(linha)
        if titulo:
            na_lista = False
            if len(titulo.group(1)) <= 2:
                na_secao = len(titulo.group(1)) == 2 and _de_outro_modulo(linha)
        elif na_lista and linha.strip() and not _RE_ITEM.match(linha) and not linha[:1].isspace():
            na_lista = False
        if not _RE_ITEM.match(linha) and _de_outro_modulo(linha):
            na_lista = True
        if na_secao or na_lista or _anotada_de_outro(linha, nome):
            excluidas.add(numero)
    return excluidas


def links_que_compoem(texto: str, modulo: str) -> list[str]:
    """Os destinos dos links do módulo, resolvidos por `checar.resolver_link` a partir dele, fora das exclusões do
    §6.1, na ordem da primeira aparição e sem repetir; o externo e o que sai da raiz ficam de fora."""
    excluidas = _linhas_excluidas(texto, modulo)
    destinos: list[str] = []
    for numero, escrito in checar.ler_links(texto):
        destino = checar.resolver_link(escrito, modulo)
        if (numero in excluidas or destino is None or destino == ".." or destino.startswith("../")
                or destino in destinos):
            continue
        destinos.append(destino)
    return destinos


def _interno(perfil: Perfil, documento: str) -> str:
    return documento[len(perfil.caminhos.planejamento.rstrip("/")) + 1:]


def _ligados_do_modulo(perfil: Perfil, modulo: str) -> list:
    """Os itens `ligados` do gate da fase do documento cujo `por` casa com ele."""
    fase = perfil.fase_do_documento(modulo)
    checklist = perfil.gates.get(fase.gate) if fase is not None else None
    interno = _interno(perfil, modulo)
    return [item for item in (checklist.itens if checklist else ())
            if item.verificacao == LIGADOS and any(comum.casa_padrao(padrao, interno)
                                                   for padrao in item.parametros["por"])]


def e_modulo(perfil: Perfil, documento: str) -> bool:
    """O documento casa com o `por` de um item `ligados` do gate da fase dele."""
    return bool(_ligados_do_modulo(perfil, documento))


def candidatos(perfil: Perfil, modulo: str, documentos_da_fase: list[str],
               aprovado: Callable[[str], bool]) -> list[str]:
    """Os documentos da fase, na ordem dada, não aprovados e diferentes do módulo, que casam os `documentos` de um item
    `ligados` cujo `por` casa o módulo."""
    ligados = _ligados_do_modulo(perfil, modulo)
    return [
        documento for documento in documentos_da_fase
        if documento != modulo and not aprovado(documento)
        and any(comum.casa_padrao(padrao, _interno(perfil, documento))
                for item in ligados for padrao in item.parametros["documentos"])
    ]


def derivados(perfil: Perfil, modulo: str, texto: str, documentos_da_fase: list[str],
              aprovado: Callable[[str], bool]) -> list[str]:
    """Os `candidatos` que estão nos `links_que_compoem` do texto do módulo, na ordem dos links."""
    possiveis = set(candidatos(perfil, modulo, documentos_da_fase, aprovado))
    return [destino for destino in links_que_compoem(texto, modulo) if destino in possiveis]
