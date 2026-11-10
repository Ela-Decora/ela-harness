"""Regras de arquitetura (spec 6d-gerador, §6): a linha da regra, o casamento do "Onde vale" com as áreas e as regras
da passagem.

Os três são comuns ao planejamento e ao desenvolvimento. A regra de arquitetura é um item de lista de uma linha,
`RA-NN: <texto>. Onde vale: <áreas>. Como se confere: <como>.`, com o trecho opcional ` Severidade: <valor>.` no fim.
O `ler` tira da linha o ID, o texto, o "Onde vale", a lista do "Como se confere" e a severidade como está, ou dá None
fora desse formato. O `casar` acha no "Onde vale" os nomes de área, o maior
primeiro, e devolve as áreas na ordem em que aparecem e o resto que sobrou sem área, vazio quando só sobram os
separadores `, ` e ` e `: é o casamento do `areas-cobertas` do planejamento e o do gerador do desenvolvimento. O
`da_passagem` acha as regras pelo campo `ids` do manifesto, em ordem de número, e lê o texto de cada uma na cópia da
passagem, com o texto, as áreas, a conferência e a fonte. A regra que não cabe no formato, que ocupa mais de uma
linha, cuja área não está na tabela ou cujo arquivo falta na cópia sai numa recusa, e nada some calado.
"""
from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from typing import Callable, Iterable

import comum
import manifesto

SEVERIDADES = ("critical", "major", "minor")
RE_ID = re.compile(r"RA-[0-9]{2,}")
SEPARADORES = (", ", " e ")
# A regra de arquitetura: `RA-NN: <regra>. Onde vale: <áreas>. Como se confere: <como>.`, e a severidade, opcional.
_RE_LINHA = re.compile(r"\b(RA-[0-9]{2,}): (.+?\.) Onde vale: (.+?)\. Como se confere: (.+?)\."
                       r"(?: Severidade: ([^.]+)\.)?$")
_SEPARADOR_DA_CONFERENCIA = ", "


@dataclass(frozen=True)
class Linha:
    id: str
    texto: str  # com o ponto final
    onde: str
    conferencia: tuple[str, ...]
    severidade: str | None = None  # como está na linha, sem conferir a escala


@dataclass(frozen=True)
class Regra:
    id: str
    texto: str
    areas: tuple[str, ...]
    conferencia: tuple[str, ...]
    fonte: manifesto.Definicao  # o arquivo com a pasta da cópia, as linhas e o sha256 do manifesto
    severidade: str | None = None  # da escala `SEVERIDADES`; None quando a linha não diz


class RegrasRecusadas(Exception):
    """As regras do manifesto que a cópia não confirma: cada motivo cabe numa linha, na ordem de número."""

    def __init__(self, motivos: tuple[str, ...]):
        super().__init__("; ".join(motivos))
        self.motivos = motivos


def ler(linha: str) -> Linha | None:
    """A regra da linha, sem a quebra e os espaços do fim, ou None quando ela não tem o formato da regra."""
    achado = _RE_LINHA.search(linha.rstrip())
    if achado is None:
        return None
    return Linha(achado.group(1), achado.group(2), achado.group(3),
                 tuple(achado.group(4).split(_SEPARADOR_DA_CONFERENCIA)), achado.group(5))


# O `da_passagem` recebe um parâmetro `ler`, que esconde a função do módulo dentro dele.
_ler_linha = ler


def casar(onde: str, nomes: Iterable[str]) -> tuple[tuple[str, ...], str]:
    """As áreas do `onde`, na ordem em que aparecem e sem repetir, e o resto a partir do primeiro trecho que nenhum
    nome casa, vazio quando todo ele casa.

    Os `nomes` vêm do maior para o menor. Em cada posição, vale o primeiro nome seguido do fim ou de um separador,
    `, ` ou ` e `, que é consumido.
    """
    nomes = tuple(nomes)
    areas: list[str] = []
    posicao = 0
    while posicao < len(onde):
        for nome in nomes:
            if not onde.startswith(nome, posicao):
                continue
            depois = posicao + len(nome)
            if depois == len(onde):
                separador: str | None = ""
            else:
                separador = next((s for s in SEPARADORES if onde.startswith(s, depois)), None)
            if separador is None:
                continue
            if nome not in areas:
                areas.append(nome)
            posicao = depois + len(separador)
            break
        else:
            return tuple(areas), onde[posicao:]
    return tuple(areas), ""


def da_passagem(m: manifesto.Manifesto, ler: Callable[[str], str | None], pasta: str) -> tuple[Regra, ...]:
    """As regras de arquitetura do manifesto, em ordem de número, lidas de `<pasta>/<arquivo>` pelo `ler`.

    Os IDs de `m.ids` que casam o `RE_ID` dão as regras; as áreas saem do `casar` sobre os nomes de `m.areas`. As
    falhas, de todas as regras, saem juntas na `RegrasRecusadas`: `<pasta>/<arquivo>:<linha>: <ID> fora do formato da
    regra de arquitetura`, `... ocupa <n> linhas; a regra de arquitetura tem uma linha`, `<ID>: área sem linha na
    tabela das áreas: <resto>`, `<ID>: severidade <valor> fora da escala critical, major e minor` e, uma vez por arquivo que o `ler` não acha, `falta <pasta>/<arquivo>`, no lugar das
    falhas das regras dele.
    """
    nomes = sorted({area.area for area in m.areas}, key=lambda nome: (-len(nome), nome))
    ids = sorted((id_ for id_ in m.ids if RE_ID.fullmatch(id_)), key=lambda id_: (int(id_.split("-", 1)[1]), id_))
    textos: dict[str, str | None] = {}
    regras: list[Regra] = []
    motivos: list[str] = []
    for id_ in ids:
        fonte = m.ids[id_]
        caminho = f"{pasta}/{fonte.arquivo}"
        if caminho not in textos:
            textos[caminho] = ler(caminho)
            if textos[caminho] is None:
                motivos.append(f"falta {caminho}")
        texto = textos[caminho]
        if texto is None:
            continue
        primeira, ultima = fonte.linhas
        onde_esta = f"{caminho}:{primeira}"
        if ultima > primeira:
            motivos.append(f"{onde_esta}: {id_} ocupa {ultima - primeira + 1} linhas; "
                           "a regra de arquitetura tem uma linha")
            continue
        linhas = texto.split("\n")
        achada = _ler_linha(linhas[primeira - 1]) if primeira <= len(linhas) else None
        if achada is None or achada.id != id_:
            motivos.append(f"{onde_esta}: {id_} fora do formato da regra de arquitetura")
            continue
        areas, resto = casar(achada.onde, nomes)
        severidade_fora = achada.severidade is not None and achada.severidade not in SEVERIDADES
        if resto:
            motivos.append(f"{onde_esta}: {id_}: área sem linha na tabela das áreas: {resto}")
        if severidade_fora:
            motivos.append(f"{onde_esta}: {id_}: severidade {achada.severidade} fora da escala "
                           f"{comum.juntar(SEVERIDADES)}")
        if resto or severidade_fora:
            continue
        regras.append(Regra(id_, achada.texto, areas, achada.conferencia, dataclasses.replace(fonte, arquivo=caminho),
                            achada.severidade))
    if motivos:
        raise RegrasRecusadas(tuple(motivos))
    return tuple(regras)
