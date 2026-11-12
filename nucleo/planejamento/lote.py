"""O lote de revisão: a ordem dos documentos e o `estado lote`, que o abre só com o que o destino da pendência cita.

O destino de uma pendência cita os documentos pelo nome do arquivo, sem contar os trechos `antes do <arquivo>.md`. O
lote vai em ordem de camada, na ordem das fases, e, dentro da camada, na ordem da primeira citação no destino; o
documento que o destino não cita fica no fim da camada dele, na ordem recebida.
"""
from __future__ import annotations

from pathlib import Path

import backlog
import estado
import rastreio
from perfil import Perfil


class LoteRecusado(Exception):
    """Recusa do `abrir`, sem nada gravado: `linhas` são os motivos, um por linha, e `mensagem` os junta."""

    def __init__(self, linhas: tuple[str, ...]):
        self.linhas = tuple(linhas)
        self.mensagem = "; ".join(self.linhas)
        super().__init__(self.mensagem)


def cita(destino: str, documento: str) -> bool:
    """O destino cita o documento pelo nome do arquivo, sem os trechos `antes do <arquivo>.md`."""
    return rastreio.padrao_do_nome(documento).search(backlog.antes_do_arquivo(destino)[1]) is not None


def ordenar(documentos: list[str], destino: str, perfil: Perfil) -> list[str]:
    """Os `documentos` por camada (a posição da fase na ordem das fases; fora das fases, depois de todas) e, na camada,
    pela posição da primeira citação no destino, sem os trechos `antes do`. Quem o destino não cita fica no fim da
    camada, na ordem recebida."""
    resto = backlog.antes_do_arquivo(destino)[1]

    def chave(documento: str) -> tuple[int, int]:
        fase = perfil.fase_do_documento(documento)
        camada = perfil.fases.index(fase) if fase is not None else len(perfil.fases)
        achado = rastreio.padrao_do_nome(documento).search(resto)
        return camada, achado.start() if achado else len(resto) + 1

    return sorted(documentos, key=chave)


def documentos_do_destino(destino: str, aprovados: list[str], perfil: Perfil) -> list[str]:
    """Os de `aprovados` que o destino cita, já ordenados."""
    return ordenar([documento for documento in aprovados if cita(destino, documento)], destino, perfil)


def abrir(
    raiz: Path, perfil: Perfil, id_: str, caminhos: list[str], hoje: str | None = None
) -> tuple[str, list[str]]:
    """Abre o lote da pendência aberta `id_` com os `caminhos`, na ordem do lote, e devolve o ID como está no backlog e a
    lista gravada. Recusa com LoteRecusado, sem gravar: a pendência fora do backlog ou fechada, os IDs com erro, cada
    documento que o destino não cita ou que não está aprovado na tabela de artefatos (todos de uma vez) e o que o
    `estado.definir_lote` recusa."""
    import registro  # tardio: o registro importa o lote

    try:
        conteudo = registro._ler(raiz, perfil.caminhos.backlog)
        numero, id_, _ = registro._pendencia_aberta(conteudo, perfil, id_, "abrir o lote")
    except registro.RegistroRecusado as erro:
        raise LoteRecusado((erro.mensagem, *erro.detalhes)) from None
    destino = backlog.celulas(conteudo.split("\n")[numero - 1])[-2]
    status = rastreio.status_dos_artefatos(conteudo, perfil)
    motivos = tuple(
        f"{caminho} não está no destino da {id_}" if not cita(destino, caminho)
        else f"{caminho} não está aprovado; o lote só revisa aprovados"
        for caminho in caminhos
        if not cita(destino, caminho) or rastreio.grupo_do_status(status.get(caminho)) != rastreio.APROVADO
    )
    if motivos:
        raise LoteRecusado(motivos)
    lista = ordenar(list(caminhos), destino, perfil)
    try:
        estado.definir_lote(raiz / perfil.caminhos.status, raiz, id_, lista, perfil, hoje=hoje)
    except estado.EstadoInvalido as erro:
        raise LoteRecusado((erro.mensagem,)) from None
    return id_, lista
