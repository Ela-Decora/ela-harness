"""Fechar um passo do ciclo (spec da fase 3a, §8): grava o STATUS.md e, nos passos 5 e 7, o status do artefato.

Tudo é conferido antes de gravar. O backlog é gravado antes do STATUS.md e volta ao texto anterior se a gravação do
STATUS.md falhar. No passo 6, a versão é marcada antes; se a gravação dos campos falhar depois, a marcação fica, e
repetir o comando é seguro.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path

import ajuste
import backlog
import comum
import estado
import migrar
import registro
import versao
from perfil import Perfil

AJUDA = """\
Fecha um passo do ciclo: grava `Passo`, `Rodada`, `Proximo` e `Atualizado` no STATUS.md numa escrita só.

Valem as validações e as travas do `estado set`. Sem `--rodada`, a rodada é 1 nos passos 2 e 5 e 0 nos outros. Com
`Documento nenhum`, só o passo 0 é aceito. Valor que começa por `-` vai com `=`, como `--proximo=-texto`.

Efeito além do STATUS.md, nos documentos em refino (o `Pacote`, ou o `Documento`):

- passo 5: status `em-revisao`, com a data de hoje, na tabela de artefatos;
- passo 6: `versao marcar` antes dos campos, do pacote inteiro quando há um;
- passo 7: status `aprovado`, com a data de hoje, só se o `versao conferir` der OK e houver mensagem do usuário
  depois da última marcação (a `resposta` que a guarda grava).

Com o `Ajuste` aberto (o `ajuste`), o passo 6 compara cada documento em refino com a última versão revisada no
histórico: seção de nível 2 ou 3 nova ou removida, ou ID definido que entrou ou saiu, é recusa. Sem nada disso, marca
como de ajuste (a entrada do histórico com `-ajuste`) e tira o `Ajuste` na mesma escrita. O passo 7 recusa com o
`Ajuste` aberto, e os passos de 0 a 5 o tiram.

No lote de migração (`Lote: migração v<de>→v<para>`, aberto pelo `migrar`), os passos 5 e 7 não mexem na tabela de
artefatos: os documentos seguem `aprovado`, com a data de antes. O passo 7 grava, no lugar, a linha
`- <data> migração v<de>→v<para>: <N> documentos` na seção de aprovações do arquivo de decisões (o `registrar
aprovacao`), depois das conferências e antes do STATUS.md.

Só o documento numa pasta de fase entra na tabela de artefatos; sem linha, ganha uma no fim dela. Tudo é conferido
antes de gravar; o backlog é gravado antes do STATUS.md e volta ao texto anterior se o STATUS.md não gravar. No
passo 6, a marcação fica se a gravação dos campos falhar depois, e repetir o comando é seguro.

Saída, com 0: `Passo = <n>; Rodada = <r>; Proximo = <texto>`, com `Versao-aprovacao = <hash>; ` antes no passo 6;
uma linha `backlog: <documento> = <status> em <AAAA-MM-DD>` por documento gravado; no passo 7, a mensagem do
usuário que valeu como aprovação, `prova: mensagem das <hora>: «<trecho>»`; e, no lote de migração,
`decisões: migração v<de>→v<para> registrada em <arquivo de decisões>:<linha>`.

Recusas, com 1 e nada gravado, depois de `recusado: `: `com Documento nenhum, só o passo 0 é aceito`;
`a versão em aprovação não confere; nada foi gravado`, seguida da saída do `versao conferir`;
`nenhuma mensagem do usuário depois da última marcação (<hash>); apresente a versão e espere a resposta`;
`ajuste aberto; marque de novo com harness.py passo 6`;
`o ajuste mudou a estrutura desde a versão revisada; é volta de correção: rode harness.py passo 3`, seguida de uma
linha por mudança, `<documento>: seção nova «<título>»`, `<documento>: seção removida «<título>»`,
`<documento>: ID novo <ID>` ou `<documento>: ID removido <ID>`;
`STATUS.md inválido: <motivo>`, `backlog ilegível: <motivo>`, `backlog sem a tabela de artefatos (...)`, as do
`estado set` e, no passo 6, as do `versao marcar`, como `arquivo não existe: <documento>`; no passo 7 do lote de
migração, as do `registrar aprovacao`, como a falta da seção de aprovações.
"""

_STATUS_DO_PASSO = {5: "em-revisao", 7: "aprovado"}
_PASSOS_COM_RODADA = (2, 5)


class PassoRecusado(Exception):
    """O passo não pode ser gravado. `mensagem` cabe numa linha; `detalhes` vêm abaixo dela, como o diff."""

    def __init__(self, mensagem: str, detalhes: tuple[str, ...] = ()):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.detalhes = tuple(detalhes)


@dataclass(frozen=True)
class Gravado:
    """Os campos gravados no STATUS.md, na ordem da saída, e os artefatos (caminho, status, data) gravados no backlog,
    na ordem do pacote. `artefato` é o primeiro deles, ou None quando o backlog não mudou."""

    campos: dict[str, str]
    artefato: tuple[str, str, str] | None
    artefatos: tuple[tuple[str, str, str], ...] = ()
    prova: str = ""
    decisao: str = ""


def _backlog_novo(
    raiz: Path, perfil: Perfil, documentos: list[str], numero: int, hoje: str
) -> tuple[str, str, tuple[str, ...]] | None:
    """(texto antigo, texto novo, documentos gravados) do backlog nos passos 5 e 7, com os documentos que estão numa
    pasta de fase; None em outro passo, no lote de migração ou sem documento numa pasta de fase."""
    nas_fases = [(documento, perfil.fase_do_documento(documento)) for documento in documentos]
    nas_fases = [(documento, fase) for documento, fase in nas_fases if fase is not None]
    if numero not in _STATUS_DO_PASSO or not nas_fases:
        return None
    try:
        antigo = backlog.ler(raiz / perfil.caminhos.backlog)
    except backlog.BacklogIlegivel as erro:
        raise PassoRecusado(f"backlog ilegível: {erro.mensagem}") from None
    novo = antigo
    try:
        for documento, fase in nas_fases:
            camada = str(perfil.fases.index(fase) + 1)
            novo = backlog.gravar_artefato(novo, documento, camada, _STATUS_DO_PASSO[numero], hoje)
    except backlog.SemTabelaDeArtefatos as erro:
        raise PassoRecusado(erro.mensagem) from None
    return antigo, novo, tuple(documento for documento, _ in nas_fases)


def fechar(
    raiz: Path, perfil: Perfil, numero: int, proximo: str, rodada: int | None = None, hoje: str | None = None
) -> Gravado:
    """Grava `Passo`, `Rodada`, `Proximo` e `Atualizado` numa escrita só e, nos passos 5 e 7, o artefato no backlog.

    Passo 6: marca a versão do documento, ou do pacote, antes; com o `Ajuste` aberto, só sem mudança de estrutura
    desde a versão revisada, e a marcação é de ajuste. Passo 7: recusado com o `Ajuste` aberto, e só com o `versao
    conferir` dando OK para cada documento e com a `resposta` do usuário anotada depois da última marcação (spec 3b,
    §7.1). Os passos de 0 a 6 tiram o `Ajuste`. Com pacote, os passos 5 e 7 gravam o artefato de cada documento (spec
    4b, §6.2). Recusa lança PassoRecusado, sem nada gravado.
    """
    if hoje is None:
        hoje = datetime.date.today().isoformat()
    status = raiz / perfil.caminhos.status
    try:
        dados = estado.ler(status, perfil)
    except estado.EstadoInvalido as erro:
        raise PassoRecusado(f"STATUS.md inválido: {erro.mensagem}") from None
    documento = dados["Documento"]
    if rodada is None:
        rodada = 1 if numero in _PASSOS_COM_RODADA else 0
    mudancas = {"Passo": str(numero), "Rodada": str(rodada), "Proximo": proximo}
    if documento == "nenhum" and numero != 0:
        raise PassoRecusado("com Documento nenhum, só o passo 0 é aceito")
    com_ajuste = estado.CAMPO_AJUSTE in dados
    if com_ajuste and numero == 7:
        raise PassoRecusado("ajuste aberto; marque de novo com harness.py passo 6")
    # Fora do passo 7, o `Ajuste` sai: o passo 6 marca a versão do ajuste, e os outros são voltas.
    escrita = {**mudancas, estado.CAMPO_AJUSTE: estado.SEM_PACOTE} if com_ajuste else mudancas
    try:
        estado.preparar(status, escrita, perfil, hoje)
    except estado.EstadoInvalido as erro:
        raise PassoRecusado(erro.mensagem) from None
    try:
        em_refino = estado.documentos(dados, raiz)
    except estado.EstadoInvalido as erro:
        raise PassoRecusado(f"STATUS.md inválido: {erro.mensagem}") from None
    de_migracao = migrar.migracao_da_origem(estado.origem_do_lote(dados.get(estado.CAMPO_LOTE, "")))
    textos = None if de_migracao else _backlog_novo(raiz, perfil, em_refino, numero, hoje)
    if numero == 7:
        confere, mensagem = versao.conferir(raiz, None, perfil)
        if not confere:
            raise PassoRecusado("a versão em aprovação não confere; nada foi gravado", tuple(mensagem.splitlines()))
        marcado = dados[versao.CAMPO]
        if not versao.resposta_confere(raiz, marcado):
            raise PassoRecusado(
                f"nenhuma mensagem do usuário depois da última marcação ({marcado}); "
                "apresente a versão e espere a resposta"
            )

    decisao = ""
    # O `passo 7` repetido, na retomada, não grava de novo a linha da migração.
    if numero == 7 and de_migracao and dados["Passo"] != "7":
        texto = f"{migrar.ORIGEM.format(de=de_migracao[0], para=de_migracao[1])}: " \
                f"{len(em_refino)} documento{'' if len(em_refino) == 1 else 's'}"
        try:
            decisao = f"{perfil.caminhos.decisoes}:{registro.aprovacao(raiz, perfil, texto, hoje)}"
        except registro.RegistroRecusado as erro:
            raise PassoRecusado(erro.mensagem, tuple(erro.detalhes)) from None
    campos: dict[str, str] = {}
    if numero == 6:
        estrutura = ajuste.estrutura_mudada(raiz, perfil, em_refino) if com_ajuste else []
        if estrutura:
            raise PassoRecusado(
                "o ajuste mudou a estrutura desde a versão revisada; é volta de correção: rode harness.py passo 3",
                tuple(estrutura),
            )
        try:
            campos[versao.CAMPO] = versao.marcar(raiz, None, perfil, ajuste=com_ajuste)
        except (versao.VersaoInvalida, estado.EstadoInvalido) as erro:
            raise PassoRecusado(erro.mensagem) from None
    campos.update(mudancas)
    caminho_backlog = raiz / perfil.caminhos.backlog
    if textos is not None:
        comum.escrever_texto(caminho_backlog, textos[1])
    try:
        estado.definir_varios(status, escrita, perfil, hoje)
    except estado.EstadoInvalido as erro:
        if textos is not None:
            comum.escrever_texto(caminho_backlog, textos[0])
        raise PassoRecusado(erro.mensagem) from None
    artefatos = tuple((gravado, _STATUS_DO_PASSO[numero], hoje) for gravado in textos[2]) if textos is not None else ()
    return Gravado(campos, artefatos[0] if artefatos else None, artefatos, _prova(raiz) if numero == 7 else "", decisao)


def _prova(raiz: Path) -> str:
    """A mensagem do usuário que valeu no passo 7 (spec 4a, §10.3): `mensagem das <hora>: «<trecho>»`, ou sem o
    trecho no formato da 3b; vazio sem `resposta` legível."""
    resposta = versao.ler_resposta(raiz)
    if resposta is None:
        return ""
    return f"mensagem das {resposta.hora}" + (f": «{resposta.trecho}»" if resposta.trecho else "")
