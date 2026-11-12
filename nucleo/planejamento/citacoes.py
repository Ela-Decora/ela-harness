"""As verificações das citações de um documento da camada: a citação por número de linha e o item de Aceite que mudou.

Um trecho `<caminho>.md:<n>` ou `<caminho>.md:<n>-<m>` aponta para uma linha que anda quando o arquivo citado muda;
o documento deve citar o ID ou o título da seção. O arquivo de decisões (`caminhos.decisoes`) fica de fora, porque
só recebe acréscimos e as linhas dele não andam.

Um `<ID>.<n>` que outro documento aprovado cita é o item `n` da primeira lista numerada da seção do ID; o aviso
`aceite-renumerado` compara esse item com o do documento no HEAD e diz se ele mudou de número ou de texto.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import backlog
import checar
import comum
from campos import _fora_de_blocos, _linhas, _recuo
from perfil import Perfil

# O `*` vale no meio do caminho (`docs/guias/*/api.md`); o `*` e o `_` em volta da citação, do negrito e do
# itálico, ficam fora dela.
_RE_CITACAO = re.compile(r"(?<![^\W_]|[./-])(?=[^\W_]|[.-])((?:[\w.*-]+/)*[\w.*-]+\.md):[0-9]+(?:-[0-9]+)?"
                         r"(?![^\W_])")
MENSAGEM = "cita por número de linha; cite o ID ou o título da seção"
_RE_SECAO = re.compile(r"### [^\s]+ ((?:[A-Z0-9]+-)+[0-9]{2,}): ")
_RE_TITULO_ATE_3 = re.compile(r"#{1,3} ")
_RE_ITEM_NUMERADO = re.compile(r"(\s*)[0-9]+[.)]\s(.*)")


def _das_decisoes(caminho: str, perfil: Perfil) -> bool:
    """Se o caminho citado é o `caminhos.decisoes` ou a parte final dele depois de uma `/`."""
    decisoes = perfil.caminhos.decisoes
    return caminho == decisoes or decisoes.endswith("/" + caminho)


def citacoes_por_linha(texto: str, perfil: Perfil) -> list[tuple[int, str]]:
    """As citações por número de linha fora dos blocos de código, com o código em linha incluído."""
    return [(numero, f"{achado.group(0)} {MENSAGEM}")
            for numero, linha in _fora_de_blocos(_linhas(texto))
            for achado in _RE_CITACAO.finditer(linha) if not _das_decisoes(achado.group(1), perfil)]


def _itens_da_lista(linhas: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Os itens `(linha, texto normalizado)` da primeira lista numerada das linhas dadas."""
    itens: list[tuple[int, list[str]]] = []
    recuo = None
    for numero, linha in linhas:
        achado = _RE_ITEM_NUMERADO.match(linha)
        if recuo is None:
            if achado:
                recuo = len(achado.group(1))
                itens.append((numero, [achado.group(2)]))
        elif not linha.strip():
            continue
        elif achado and len(achado.group(1)) == recuo:
            itens.append((numero, [achado.group(2)]))
        elif _recuo(linha) > recuo:
            itens[-1][1].append(linha)
        else:
            break
    return [(numero, " ".join(" ".join(partes).split())) for numero, partes in itens]


def secoes_com_itens(texto: str) -> dict[str, tuple[int, list[tuple[int, str]]]]:
    """Por ID de seção `### <palavra> <ID>: <nome>`, a linha do título e os itens `(linha, texto)` da primeira lista
    numerada dela. A seção fecha no título seguinte de nível 1 a 3; o texto do item junta as linhas que o continuam,
    com os espaços normalizados. O ID repetido fica com a primeira seção."""
    secoes: dict[str, tuple[int, list[tuple[int, str]]]] = {}
    atual = None
    corpo: list[tuple[int, str]] = []

    def fechar() -> None:
        if atual is not None and atual[0] not in secoes:
            secoes[atual[0]] = (atual[1], _itens_da_lista(corpo))

    for numero, linha in _fora_de_blocos(_linhas(texto)):
        if _RE_TITULO_ATE_3.match(linha):
            fechar()
            achado = _RE_SECAO.match(linha)
            atual = (achado.group(1), numero) if achado else None
            corpo = []
        else:
            corpo.append((numero, linha))
    fechar()
    return secoes


def padrao_de_citacoes(ids: list[str]) -> re.Pattern[str]:
    """A citação `<ID>.<n>` de um dos `ids`, ou a faixa `<ID>.<n> a <ID>.<m>`: os grupos são o ID, o `n` e o `m`."""
    return re.compile(r"(?<![\w-])(" + "|".join(re.escape(id_) for id_ in sorted(ids, key=len, reverse=True))
                      + r")\.([0-9]+)(?:\s+a\s+\1\.([0-9]+))?(?![0-9])")


def _citacoes_de_aceite(raiz: Path, relativo: str, ids: list[str], texto_backlog: str | None,
                        perfil: Perfil) -> dict[str, list[tuple[int, int, str]]]:
    """Por ID, as citações `(de, ate, documento)` dos documentos aprovados das pastas de fase, menos o próprio."""
    padrao = padrao_de_citacoes(ids)
    achadas: dict[str, list[tuple[int, int, str]]] = {}
    for _, caminho, status in backlog.artefatos_da_pasta(texto_backlog or "", perfil.caminhos.planejamento):
        if not status.startswith("aprovado") or caminho == relativo or perfil.fase_do_documento(caminho) is None:
            continue
        try:
            texto = comum.ler_texto(raiz / caminho)
        except (OSError, UnicodeDecodeError):
            continue
        for _, linha in _fora_de_blocos(_linhas(texto)):
            for achado in padrao.finditer(linha):
                inicio = int(achado.group(2))
                fim = int(achado.group(3)) if achado.group(3) else inicio
                achadas.setdefault(achado.group(1), []).append((min(inicio, fim), max(inicio, fim), caminho))
    return achadas


def _texto_do_head(raiz: Path, relativo: str, executar) -> str | None:
    """O documento no HEAD, ou None sem repositório, sem HEAD, sem o documento ou com o `git show` lento."""
    try:
        feito = executar(["git", "-C", str(raiz), "show", f"HEAD:./{relativo}"], capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if feito.returncode != 0:
        return None
    return feito.stdout.decode("utf-8", errors="replace").replace("\r", "")


def aceite_renumerado(raiz: Path, relativo: str, texto: str, texto_backlog: str | None, perfil: Perfil,
                      executar) -> list[tuple[int, str]]:
    """Os itens `<ID>.<n>` citados por outro documento aprovado cujo texto, no HEAD, não é mais o do item `n`.

    A linha é a do item `n` de hoje ou, sem ele, a do título da seção. Sem citação, sem o documento no HEAD ou com
    falha do `git show`, lista vazia."""
    hoje = secoes_com_itens(texto)
    if not hoje:
        return []
    citadas = _citacoes_de_aceite(raiz, relativo, list(hoje), texto_backlog, perfil)
    if not citadas:
        return []
    texto_antes = _texto_do_head(raiz, relativo, executar)
    if texto_antes is None:
        return []
    antes = secoes_com_itens(texto_antes)
    achados = []
    for id_, citacoes_do_id in citadas.items():
        if id_ not in antes:
            continue
        titulo, itens_de_hoje = hoje[id_]
        textos_de_hoje = [item for _, item in itens_de_hoje]
        for n, (_, antigo) in enumerate(antes[id_][1], start=1):
            documentos = sorted({doc for de, ate, doc in citacoes_do_id if de <= n <= ate})
            if not documentos or textos_de_hoje[n - 1:n] == [antigo]:
                continue
            linha = itens_de_hoje[n - 1][0] if n <= len(itens_de_hoje) else titulo
            destino = f"virou {id_}.{textos_de_hoje.index(antigo) + 1}" if antigo in textos_de_hoje else "mudou ou saiu"
            achados.append((linha, id_, n, f"{id_}.{n}, citado em {', '.join(documentos)}, {destino} desde o HEAD"))
    return [(linha, detalhe) for linha, _, _, detalhe in sorted(achados)]


def verificacoes(raiz: Path, relativo: str, texto: str, texto_backlog: str | None, perfil: Perfil,
                 executar) -> list[checar.Resultado]:
    """As verificações das citações no `checar` de um documento da camada: `citacao-por-linha` e `aceite-renumerado`,
    que é só aviso e por isso nunca falha."""
    aviso = checar.de_ocorrencias(checar.ACEITE_RENUMERADO,
                                  aceite_renumerado(raiz, relativo, texto, texto_backlog, perfil, executar))
    aviso.ok = True
    return [checar.de_ocorrencias(checar.CITACAO_POR_LINHA, citacoes_por_linha(texto, perfil)), aviso]
