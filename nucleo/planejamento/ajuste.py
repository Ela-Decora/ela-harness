"""O comando `ajuste`: abre o ajuste no passo 6, para editar o documento sem voltar ao passo 3."""
from __future__ import annotations

from pathlib import Path

import comum
import estado
import resumo
import versao
from perfil import Perfil

PROXIMO_PADRAO = "ajuste: edite, rode harness.py checar e marque de novo com harness.py passo 6"

AJUDA = """\
Abre o ajuste: no passo 6, libera a edição do documento em refino sem voltar ao passo 3.

Só no planejamento, no passo 6, com a versão marcada (`Versao-aprovacao` com hash) e, para cada documento em refino,
uma versão revisada no histórico: a última entrada que não é de ajuste. O pedido de um ajuste cabe nas edições que
não mudam a estrutura do documento; a estrutura nova volta ao passo 3.

Grava `Ajuste: aberto` no STATUS.md, logo depois do `Documento` (ou do `Pacote` ou do `Lote`), e o `Proximo`: o
`--proximo`, ou `ajuste: edite, rode harness.py checar e marque de novo com harness.py passo 6`. Com o campo aberto,
a guarda libera a edição dos documentos no passo 6; o passo 7 não a libera. Abrir de novo grava o mesmo. O campo sai
quando o passo 6 marca a versão de novo, num passo de 0 a 5, no `fechar`, num `Documento` novo e no
`versao limpar`.

Saída, com 0: `Ajuste = aberto; Proximo = <texto>`.

Recusas, com 1 e nada gravado, depois de `recusado: `: `o ajuste só vale no passo 6`,
`nenhuma versão marcada; rode harness.py passo 6` e, uma linha por documento,
`nenhuma versão revisada no histórico de <documento>; o pedido volta ao passo 3`.
"""


class AjusteRecusado(Exception):
    """O ajuste não abre. A `mensagem` é a primeira recusa; as outras, uma por documento, vão em `detalhes`; todas
    sem o `recusado: `, que o comando põe na frente de cada linha."""

    def __init__(self, mensagem: str, detalhes: tuple[str, ...] = ()):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.detalhes = detalhes


def abrir(raiz: Path, perfil: Perfil, proximo: str = PROXIMO_PADRAO, hoje: str | None = None) -> dict[str, str]:
    """Grava `Ajuste: aberto` e o `Proximo` no STATUS.md; devolve os dois campos gravados.

    Recusa fora do passo 6, sem versão marcada e com algum documento sem versão revisada no histórico (a primeira
    recusa na `mensagem`, as outras em `detalhes`). Lança EstadoInvalido com o STATUS.md ou a lista do lote que não
    servem. Nada é gravado numa recusa."""
    caminho = raiz / perfil.caminhos.status
    dados = estado.ler(caminho, perfil)
    if dados.get("Passo") != "6":
        raise AjusteRecusado("o ajuste só vale no passo 6")
    if dados.get("Versao-aprovacao", estado.SEM_PACOTE) == estado.SEM_PACOTE:
        raise AjusteRecusado("nenhuma versão marcada; rode harness.py passo 6")
    recusas = tuple(
        f"nenhuma versão revisada no histórico de {documento}; o pedido volta ao passo 3"
        for documento in estado.documentos(dados, raiz)
        if versao.ultima_revisada(raiz, documento) is None
    )
    if recusas:
        raise AjusteRecusado(recusas[0], recusas[1:])
    mudancas = {estado.CAMPO_AJUSTE: estado.AJUSTE_ABERTO, "Proximo": proximo}
    estado.definir_varios(caminho, mudancas, perfil, hoje)
    return mudancas


def estrutura_mudada(raiz: Path, perfil: Perfil, documentos: list[str]) -> list[str]:
    """O que mudou na estrutura de cada documento desde a última versão revisada dele no histórico, comparada ao disco:
    `<documento>: seção nova «<título>»`, `seção removida «<título>»`, `ID novo <ID>` e `ID removido <ID>`, nessa
    ordem por documento. A seção alterada e o ID com a linha de definição mudada passam. O documento sem versão
    revisada, ou que não está no disco, fica de fora: quem o recusa é o `ajuste` e o `versao marcar`."""
    linhas: list[str] = []
    for documento in documentos:
        revisada = versao.ultima_revisada(raiz, documento)
        if revisada is None or not (raiz / documento).is_file():
            continue
        mudancas = resumo.comparar(
            documento, comum.ler_texto(revisada.caminho), comum.ler_texto(raiz / documento), perfil
        )
        if mudancas is None:
            continue
        for tipo in ("nova", "removida"):
            linhas += [f"{documento}: seção {tipo} «{titulo}»" for titulo, de_tipo, _, _ in mudancas.secoes
                       if de_tipo == tipo]
        linhas += [f"{documento}: ID novo {id_}" for id_ in mudancas.entrou]
        linhas += [f"{documento}: ID removido {id_}" for id_ in mudancas.saiu]
    return linhas
