"""O resumo das mudanças dos documentos em refino: o esqueleto contra o HEAD ou a cópia marcada e o diff por camada.

A seção é o título de nível 2 ou 3 fora dos blocos de código; o que vem antes do primeiro título é a seção do título
de nível 1, ou `início`, sem ele. O título repetido no mesmo documento ganha ` (2)`, ` (3)`, na ordem.
"""
from __future__ import annotations

import difflib
import itertools
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import campos
import checar
import comum
import dossie
import estado
import legenda
import versao
from perfil import Perfil

SEM_TITULO = "início"
RECUSA_SEM_DOCUMENTO = "Documento: nenhum no STATUS.md; não há o que resumir"
_RE_TITULO = re.compile(r"(#{1,3}) +(.*\S)")
_RE_DIFF_DA_CAMADA = re.compile(r"diff-camada-(\d+)\.diff$")


class ResumoRecusado(Exception):
    """Recusa do resumo, com o motivo na `mensagem`."""

    def __init__(self, mensagem: str):
        self.mensagem = mensagem
        super().__init__(mensagem)


class SemMudancas(ResumoRecusado):
    """O documento do `ver` não mudou: não é recusa, o comando sai com 0."""


@dataclass(frozen=True)
class Mudancas:
    """As mudanças de um documento: `secoes` traz `(título, "alterada" | "nova" | "removida", mais, menos)`, e
    `entrou`, `saiu` e `mudou` os IDs definidos que entraram, saíram ou mudaram a linha de definição."""

    documento: str
    novo: bool
    secoes: tuple[tuple[str, str, int, int], ...]
    entrou: tuple[str, ...]
    saiu: tuple[str, ...]
    mudou: tuple[str, ...]


def secoes(texto: str) -> list[tuple[str, list[str]]]:
    """`(título, linhas)` de cada seção do texto, na ordem; as linhas vão do título, exclusive, até o seguinte, com os
    blocos de código dentro. O título repetido ganha ` (2)`, ` (3)`."""
    linhas = campos._linhas(texto)
    titulos = {}
    for numero, linha in campos._fora_de_blocos(linhas):
        achado = _RE_TITULO.fullmatch(linha.rstrip())
        if achado:
            titulos[numero] = (len(achado.group(1)), achado.group(2))
    achadas: list[tuple[str, list[str]]] = []
    contagem: dict[str, int] = {}
    for numero, linha in enumerate(linhas, start=1):
        if numero in titulos and (titulos[numero][0] > 1 or not achadas):
            titulo = titulos[numero][1]
            contagem[titulo] = contagem.get(titulo, 0) + 1
            achadas.append((titulo if contagem[titulo] == 1 else f"{titulo} ({contagem[titulo]})", []))
        elif achadas:
            achadas[-1][1].append(linha)
        elif linha.strip():
            achadas.append((SEM_TITULO, [linha]))
    return achadas


def _ids(texto: str, perfil: Perfil) -> dict[str, str]:
    """ID para a linha que o define, sem espaços nas pontas; a primeira definição vale."""
    linhas = campos._linhas(texto)
    definidos: dict[str, str] = {}
    for numero, id_ in checar.ids_definidos(texto, perfil):
        definidos.setdefault(id_, linhas[numero - 1].strip())
    return definidos


def _contar(antigas: list[str], novas: list[str]) -> tuple[int, int]:
    mais = menos = 0
    for linha in itertools.islice(difflib.unified_diff(antigas, novas, lineterm="", n=0), 2, None):
        if linha.startswith("+"):
            mais += 1
        elif linha.startswith("-"):
            menos += 1
    return mais, menos


def comparar(nome: str, antigo: str | None, novo: str, perfil: Perfil) -> Mudancas | None:
    """As mudanças do `antigo` para o `novo`, ou None sem mudança; `antigo=None` é o documento novo."""
    if antigo is None:
        return Mudancas(nome, True, (), (), (), ())
    secoes_antigas = dict(secoes(antigo))
    secoes_novas = secoes(novo)
    achadas: list[tuple[str, str, int, int]] = []
    for titulo, linhas in secoes_novas:
        if titulo not in secoes_antigas:
            achadas.append((titulo, "nova", len(linhas), 0))
        elif linhas != secoes_antigas[titulo]:
            achadas.append((titulo, "alterada", *_contar(secoes_antigas[titulo], linhas)))
    nos_novos = {titulo for titulo, _ in secoes_novas}
    achadas += [(titulo, "removida", 0, len(linhas)) for titulo, linhas in secoes_antigas.items() if titulo not in nos_novos]
    ids_antigos, ids_novos = _ids(antigo, perfil), _ids(novo, perfil)
    entrou = tuple(id_ for id_ in ids_novos if id_ not in ids_antigos)
    saiu = tuple(id_ for id_ in ids_antigos if id_ not in ids_novos)
    mudou = tuple(id_ for id_, linha in ids_novos.items() if id_ in ids_antigos and ids_antigos[id_] != linha)
    if not (achadas or entrou or saiu or mudou):
        return None
    return Mudancas(nome, False, tuple(achadas), entrou, saiu, mudou)


def formatar_esqueleto(mudancas: list[Mudancas]) -> str:
    """O esqueleto: o nome do documento, uma linha por seção e a linha `IDs:` sem os grupos vazios; o documento novo
    sai numa linha só."""
    saida: list[str] = []
    for item in mudancas:
        if item.novo:
            saida.append(f"{item.documento} · novo")
            continue
        saida.append(item.documento)
        for titulo, tipo, mais, menos in item.secoes:
            saida.append(f"  {titulo} · {tipo}" + (f" (+{mais} −{menos})" if tipo == "alterada" else ""))
        grupos = [f"{rotulo} {', '.join(ids)}" for rotulo, ids in
                  (("entrou", item.entrou), ("saiu", item.saiu), ("mudou", item.mudou)) if ids]
        if grupos:
            saida.append("  IDs: " + "; ".join(grupos))
    return "".join(linha + "\n" for linha in saida)


def base(
    raiz: Path, relativo: str, desde_marcada: bool, executar, desde_revisada: bool = False
) -> str | None:
    """O texto do documento no HEAD, ou None se ele não está lá; com `desde_marcada`, o da cópia marcada, e sem a cópia
    lança ResumoRecusado; com `desde_revisada`, o da última entrada revisada do histórico (a de ajuste fica de fora), e
    sem ela lança ResumoRecusado."""
    if desde_revisada:
        entrada = versao.ultima_revisada(raiz, relativo)
        if entrada is None:
            raise ResumoRecusado(f"nenhuma versão revisada no histórico de {relativo}")
        return comum.ler_texto(entrada.caminho)
    if desde_marcada:
        copia = raiz / comum.PASTA_APROVACAO / versao.nome_da_copia(relativo)
        if not copia.is_file():
            raise ResumoRecusado(f"sem a cópia marcada de {relativo}; rode sem --desde-marcada")
        return comum.ler_texto(copia)
    if not (raiz / ".git").exists():
        raise ResumoRecusado("a raiz não é um repositório git")
    try:
        formas = versao._formas_no_head(raiz, relativo, executar)
    except versao._GitIndisponivel as erro:
        raise ResumoRecusado(f"git indisponível: {erro}") from None
    return formas[0].decode("utf-8", errors="replace") if formas else None


def _camada(perfil: Perfil, relativo: str) -> int:
    fase = perfil.fase_do_documento(relativo)
    return perfil.fases.index(fase) + 1 if fase is not None else len(perfil.fases) + 1


def esqueleto(
    raiz: Path, perfil: Perfil, desde_marcada: bool = False, executar=subprocess.run, desde_revisada: bool = False
) -> tuple[list[Mudancas], list[str]]:
    """As mudanças dos documentos em refino contra o HEAD (ou a cópia marcada, ou a última versão revisada) e os caminhos dos diffs gravados, um por
    camada com mudança, em `diff-camada-<N>.diff` na pasta do dossiê; prepara a pasta do resumo escrito. Sem documento
    em refino, lança ResumoRecusado."""
    dados = estado.ler(raiz / perfil.caminhos.status, perfil)
    documentos = estado.documentos(dados, raiz)
    if not documentos:
        raise ResumoRecusado(RECUSA_SEM_DOCUMENTO)
    mudancas: list[Mudancas] = []
    diffs: dict[int, list[str]] = {}
    for relativo in documentos:
        novo = comum.ler_texto(raiz / relativo)
        antigo = base(raiz, relativo, desde_marcada, executar, desde_revisada)
        achadas = comparar(Path(relativo).name, antigo, novo, perfil)
        if achadas is None:
            continue
        mudancas.append(achadas)
        diff = difflib.unified_diff(
            [] if antigo is None else campos._linhas(antigo), campos._linhas(novo),
            fromfile=f"a/{relativo}", tofile=f"b/{relativo}", lineterm="",
        )
        diffs.setdefault(_camada(perfil, relativo), []).extend(diff)
    gravados: list[str] = []
    for antigo_gravado in (raiz / dossie.PASTA_DOSSIE).glob("diff-camada-*.diff"):
        antigo_gravado.unlink()
    for camada in sorted(diffs):
        caminho = f"{dossie.PASTA_DOSSIE}/diff-camada-{camada}.diff"
        comum.escrever_texto(raiz / caminho, "\n".join(diffs[camada]) + "\n")
        gravados.append(caminho)
    preparar_pasta_do_resumo(raiz)
    return mudancas, gravados


def preparar_pasta_do_resumo(raiz: Path) -> None:
    """Cria `comum.PASTA_RESUMO` com um `.gitignore` de `*`, para o resumo escrito ficar fora do git."""
    ignorar = raiz / comum.PASTA_RESUMO / ".gitignore"
    if not ignorar.is_file():
        comum.escrever_texto(ignorar, "*\n")


def formatar_diffs(caminhos: list[str]) -> str:
    """Uma linha `Diff para o revisor, camada <N>: <caminho>` por diff gravado."""
    saida = ""
    for caminho in caminhos:
        achado = _RE_DIFF_DA_CAMADA.search(caminho)
        saida += f"Diff para o revisor, camada {achado.group(1) if achado else '?'}: {caminho}\n"
    return saida


def _itens_do_onde(texto: str) -> list[str]:
    """Os itens `<documento> · <seção>` das linhas `Onde:` do resumo, sem `*` nem crases nas pontas, sem repetir."""
    itens: list[str] = []
    for linha in texto.splitlines():
        resto = linha.strip()
        if not resto.startswith("Onde:"):
            continue
        for pedaco in resto[len("Onde:"):].split(";"):
            if not pedaco.strip():
                continue
            partes = [parte.strip().strip("*`").strip() for parte in pedaco.split(" · ", 1)]
            item = " · ".join(partes)
            if item not in itens:
                itens.append(item)
    return itens


def conferir(texto_do_resumo: str, mudancas: list[Mudancas]) -> tuple[bool, str]:
    """Confere as linhas `Onde:` do resumo contra as seções que mudaram: `(ok, mensagem)`, com `FALTA:` para a seção
    sem linha e `SOBRA:` para a linha de seção que não mudou. O documento novo se cobre com `<documento> · novo`."""
    esperadas: list[str] = []
    for item in mudancas:
        if item.novo:
            esperadas.append(f"{item.documento} · novo")
        esperadas += [f"{item.documento} · {titulo}" for titulo, *_ in item.secoes]
    achadas = _itens_do_onde(texto_do_resumo)
    faltam = [item for item in esperadas if item not in achadas]
    sobram = [item for item in achadas if item not in esperadas]
    if not faltam and not sobram:
        linhas_onde = sum(1 for linha in texto_do_resumo.splitlines() if linha.strip().startswith("Onde:"))
        return True, f"OK: {linhas_onde} mudanças cobrem as {len(esperadas)} seções alteradas"
    partes: list[str] = []
    if faltam:
        partes.append(f"FALTA: {len(faltam)} seções sem mudança no resumo:\n" + "\n".join(faltam))
    partes += [f"SOBRA: {item} não mudou" for item in sobram]
    return False, "\n".join(partes)


def palavra_a_palavra(antiga: str, nova: str) -> str:
    """A linha nova com as palavras acrescentadas entre `**` e as tiradas entre `~~`; a trocada sai `~~antigo~~ **novo**`."""
    antigas, novas = antiga.split(), nova.split()
    saida: list[str] = []
    for tag, a1, a2, n1, n2 in difflib.SequenceMatcher(None, antigas, novas, autojunk=False).get_opcodes():
        if tag == "equal":
            saida += novas[n1:n2]
            continue
        if tag in ("delete", "replace"):
            saida.append("~~" + " ".join(antigas[a1:a2]) + "~~")
        if tag in ("insert", "replace"):
            saida.append("**" + " ".join(novas[n1:n2]) + "**")
    return " ".join(saida)


def _linhas_da_secao(texto: str | None, titulo: str) -> list[str]:
    if texto is None:
        return []
    return [linha for linha in dict(secoes(texto)).get(titulo, []) if linha.strip()]


# A semelhança, palavra a palavra, acima da qual uma linha tirada e uma acrescentada viram uma linha mudada.
PARENTESCO_MINIMO = 0.5


def _trocadas(antigas: list[str], novas: list[str]) -> list[str]:
    """As linhas de um bloco trocado, como o `difflib.Differ` as pareia: o par mais parecido acima do
    PARENTESCO_MINIMO sai palavra a palavra, e o que vem antes e depois dele é pareado do mesmo jeito; sem par, a
    linha tirada sai `~~antiga~~` e a acrescentada `**nova**`, cada uma na sua linha."""
    melhor, par = PARENTESCO_MINIMO, None
    for i, antiga in enumerate(antigas):
        for j, nova in enumerate(novas):
            razao = difflib.SequenceMatcher(None, antiga.split(), nova.split(), autojunk=False).ratio()
            if razao > melhor:
                melhor, par = razao, (i, j)
    if par is None:
        return [f"~~{linha}~~" for linha in antigas] + [f"**{linha}**" for linha in novas]
    i, j = par
    return (_trocadas(antigas[:i], novas[:j]) + [palavra_a_palavra(antigas[i], novas[j])]
            + _trocadas(antigas[i + 1:], novas[j + 1:]))


def _corpo_alterado(antigas: list[str], novas: list[str]) -> list[str]:
    saida: list[str] = []
    for tag, a1, a2, n1, n2 in difflib.SequenceMatcher(None, antigas, novas, autojunk=False).get_opcodes():
        if tag != "equal":
            saida += _trocadas(antigas[a1:a2], novas[n1:n2])
    return saida


def ver(
    raiz: Path, perfil: Perfil, documento: str, n: int, desde_marcada: bool = False, executar=subprocess.run
) -> str:
    """A `n`-ésima seção alterada do documento em refino, com as linhas que mudaram, palavra a palavra, e a legenda dos
    IDs na primeira aparição de cada um. Lança ResumoRecusado."""
    dados = estado.ler(raiz / perfil.caminhos.status, perfil)
    relativo = next(
        (caminho for caminho in estado.documentos(dados, raiz) if documento in (caminho, Path(caminho).name)), None
    )
    if relativo is None:
        raise ResumoRecusado(f"{documento} não está em refino no STATUS.md")
    nome = Path(relativo).name
    novo = comum.ler_texto(raiz / relativo)
    antigo = base(raiz, relativo, desde_marcada, executar)
    achadas = comparar(nome, antigo, novo, perfil)
    if antigo is None:
        alteradas = [(titulo, "nova") for titulo, _ in secoes(novo)]
    else:
        alteradas = [(titulo, tipo) for titulo, tipo, *_ in achadas.secoes] if achadas else []
    if not alteradas:
        raise SemMudancas(f"{nome} sem mudanças contra " + ("a versão marcada" if desde_marcada else "o HEAD"))
    if not 1 <= n <= len(alteradas):
        raise ResumoRecusado(f"{nome} tem {len(alteradas)} seções alteradas; peça de 1 a {len(alteradas)}")
    titulo, tipo = alteradas[n - 1]
    cabecalho = f"**{nome} · {titulo}** ({n} de {len(alteradas)})"
    if tipo == "removida":
        corpo = ["Seção removida."]
    elif tipo == "nova":
        linhas = _linhas_da_secao(novo, titulo)
        corpo = [f"Seção nova, {len(linhas)} " + ("linha." if len(linhas) == 1 else "linhas.")] + linhas
    else:
        corpo = _corpo_alterado(_linhas_da_secao(antigo, titulo), _linhas_da_secao(novo, titulo))
    texto = "\n".join([cabecalho] + corpo) + "\n"
    return legenda.com_legenda(texto, legenda.titulos(comum.leitor_do_disco(raiz), perfil), perfil)
