"""Fechamento do ciclo depois do commit (spec 4a, §7): confere a versão marcada no HEAD e fecha o STATUS.md numa
escrita só. Nessa escrita, o `Documento` volta a `nenhum`, o `Passo` e a `Rodada` voltam a 0, a marcação, o `Pacote`
e o `Lote` saem e o `Proximo` recebe o próximo passo calculado; depois, as cópias da aprovação e a lista do lote são
apagadas.

Com a versão no HEAD, nada se perde, e por isso o fechamento dispensa a autorização do usuário que o `versao limpar`
avulso pede. Toda recusa sai antes de gravar.

Depois de gravar, o `fechar` leva o `STATUS.md` ao commit (spec 6a, §5.2): o amend do commit do documento quando o
HEAD mudou um documento do ciclo e nenhuma outra branch, local ou remota, o contém, ou um commit `chore` nos outros
casos. A falha do commit não desfaz o que foi gravado.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import comum
import dossie
import estado
import proximo
import versao
from perfil import Perfil

AJUDA = """\
Fecha o ciclo do documento, do pacote ou do lote no passo 7, depois do commit, conferindo a versão marcada no HEAD.

Confere que cada documento em refino está no HEAD igual ao disco, pelo `git show` e pelo `git cat-file --filters`,
que aplica o `core.autocrlf`, e que o hash dele, ou o do manifesto refeito no pacote ou no lote, é o
`Versao-aprovacao`; vale noutra máquina, sem as cópias. Então grava numa escrita só `Versao-aprovacao: —`,
`Documento: nenhum`, sem `Pacote` e sem `Lote`, `Passo: 0`, `Rodada: 0` e o `Proximo` (o `--proximo`, ou a ação do
`harness.py proximo`), apaga as cópias da aprovação, a lista do lote e a saída gravada do `afetados` e imprime
`Fechado: <documento> (<hash> no HEAD <commit>)` e `Proximo = <texto>`, com 0. Num pacote, o documento vira
`pacote de <N> documentos`; num lote, `lote <origem> de <N> documentos`. Não pede autorização: com a versão no HEAD,
nada se perde.

Depois, faz o `git add` do `STATUS.md` e o commit dele. Quando o HEAD mudou um documento do ciclo e nenhuma outra
branch, local ou remota (pela referência do último fetch), contém o HEAD, sai o `git commit --amend --no-edit`; nos
outros casos, como o HEAD de outro trabalho, o merge ou o commit já no remoto, sai um commit
`chore: fecha o STATUS.md (<documento>)`. A terceira linha é `STATUS.md no commit <commit> (amend)` ou `(chore)`, com
0. Se o commit falha, o `STATUS.md` fica gravado e no índice, e a terceira linha é
`STATUS.md gravado; o commit falhou: <motivo>; faça o commit à mão`, com 1. O motivo é a primeira linha da saída do
git com `FALHA`, ou, sem ela, a primeira linha não vazia.

Recusas, com 1 e nada gravado, depois de `recusado: `: `Passo <n>; fechar só no passo 7`, `nenhuma versão marcada`,
`a raiz não é um repositório git`, `git indisponível: <motivo>`, `STATUS.md inválido: <motivo>`,
`<documento> tem mudança fora do commit; faça o commit antes`,
`a versão no HEAD não é a marcada (<head> != <marcado>); confira com harness.py versao conferir` e
`índice com arquivos além do STATUS.md; faça o commit deles antes`.
"""


class FechamentoRecusado(Exception):
    """O ciclo não pode fechar. `mensagem` diz o motivo, sem o `recusado: `."""

    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


AMEND = "amend"
CHORE = "chore"
_TEMPO_LIMITE_GIT = 5
_TEMPO_LIMITE_COMMIT = 60


@dataclass(frozen=True)
class Fechado:
    """O que fechou: o caminho do documento, `pacote de <N> documentos` ou `lote <origem> de <N> documentos`; o hash
    marcado; o commit curto do HEAD em que a versão foi conferida; o texto gravado no `Proximo`. Depois, o commit
    curto com o `STATUS.md` e o modo (`amend` ou `chore`), ou, se o commit falhou, o motivo em `falha_do_commit`."""

    descricao: str
    hash: str
    commit: str
    proximo: str
    commit_do_status: str = ""
    modo: str = ""
    falha_do_commit: str = ""


def _git(raiz: Path, argumentos: list[str], executar, tempo: int) -> subprocess.CompletedProcess:
    """Roda o git na raiz, com o tempo limite dado. Exceção e tempo esgotado passam adiante."""
    return executar(["git", "-C", str(raiz), *argumentos], capture_output=True, timeout=tempo)


def _indice_so_com_o_status(raiz: Path, perfil: Perfil, executar) -> None:
    """Recusa o fechamento quando o índice tem outro arquivo além do `STATUS.md`, que iria junto no commit."""
    try:
        indice = _git(raiz, ["diff", "--cached", "--name-only", "-z"], executar, _TEMPO_LIMITE_GIT)
    except (OSError, subprocess.SubprocessError) as erro:
        raise FechamentoRecusado(f"git indisponível: {erro}") from None
    if indice.returncode != 0:
        raise FechamentoRecusado(f"git indisponível: git diff --cached saiu com {indice.returncode}")
    caminhos = [c for c in (indice.stdout or b"").decode("utf-8", errors="replace").split("\0") if c]
    if any(caminho != perfil.caminhos.status for caminho in caminhos):
        raise FechamentoRecusado("índice com arquivos além do STATUS.md; faça o commit deles antes")


def _commit_do_status(
    raiz: Path, perfil: Perfil, documentos: list[str], descricao: str, executar
) -> tuple[str, str, str]:
    """Leva o `STATUS.md` ao commit: o amend do HEAD quando ele mudou um dos `documentos` e nenhuma outra branch, local
    ou remota, o contém; nos outros casos, um commit `chore`. O merge não lista arquivos no `diff-tree` e vai de
    `chore`. Devolve o commit curto, o modo e, se algum passo falhou, o motivo, sem lançar exceção. Se o commit saiu
e só a leitura do HEAD falhou, o commit volta como `HEAD`, sem motivo, para ninguém refazer um commit feito."""
    try:
        adicionado = _git(raiz, ["add", "--", perfil.caminhos.status], executar, _TEMPO_LIMITE_GIT)
        if adicionado.returncode != 0:
            return "", "", comum.motivo_do_git(adicionado, "add")
        mudados = _git(
            raiz,
            ["diff-tree", "--root", "--no-commit-id", "--name-only", "-r", "-z", "HEAD"],
            executar,
            _TEMPO_LIMITE_GIT,
        )
        if mudados.returncode != 0:
            return "", "", comum.motivo_do_git(mudados, "diff-tree")
        # `%(HEAD)` dá `*` na branch atual e um espaço nas outras referências que contêm o HEAD.
        referencias = _git(
            raiz,
            ["for-each-ref", "--contains", "HEAD", "--format=%(HEAD)", "refs/heads", "refs/remotes"],
            executar,
            _TEMPO_LIMITE_GIT,
        )
        if referencias.returncode != 0:
            return "", "", comum.motivo_do_git(referencias, "for-each-ref")
        do_ciclo = set(documentos) & set((mudados.stdout or b"").decode("utf-8", errors="replace").split("\0"))
        marcas = (referencias.stdout or b"").decode("utf-8", errors="replace").splitlines()
        outras = [marca for marca in marcas if marca.strip() != "*"]
        if do_ciclo and not outras:
            modo, argumentos = AMEND, ["commit", "-q", "--amend", "--no-edit"]
        else:
            modo, argumentos = CHORE, ["commit", "-q", "-m", f"chore: fecha o STATUS.md ({descricao})"]
        feito = _git(raiz, argumentos, executar, _TEMPO_LIMITE_COMMIT)
        if feito.returncode != 0:
            return "", "", comum.motivo_do_git(feito, "commit")
        head = _git(raiz, ["rev-parse", "--verify", "-q", "HEAD"], executar, _TEMPO_LIMITE_GIT)
        if head.returncode != 0:
            return "HEAD", modo, ""
    except (OSError, subprocess.SubprocessError) as erro:
        return "", "", str(erro)
    return (head.stdout or b"").decode("utf-8", errors="replace").strip()[:7], modo, ""


def fechar(
    raiz: Path,
    perfil: Perfil,
    proximo_texto: str | None = None,
    executar=subprocess.run,
    hoje: str | None = None,
) -> Fechado:
    """Fecha o ciclo no passo 7 com a versão marcada no HEAD. Lança FechamentoRecusado, sem gravar nada, com o STATUS
    inválido, fora do passo 7, sem versão marcada, sem git, com documento fora do commit ou com outra versão no HEAD.
    Sem `proximo_texto`, o `Proximo` é a linha curta do `proximo` calculado sobre o STATUS já fechado."""
    caminho = raiz / perfil.caminhos.status
    try:
        dados = estado.ler(caminho, perfil)
    except estado.EstadoInvalido as erro:
        raise FechamentoRecusado(f"STATUS.md inválido: {erro.mensagem}") from None
    if dados["Passo"] != "7":
        raise FechamentoRecusado(f"Passo {dados['Passo']}; fechar só no passo 7")
    marcado = dados[versao.CAMPO]
    if marcado == versao.SEM_VERSAO:
        raise FechamentoRecusado("nenhuma versão marcada")
    try:
        documentos = estado.documentos(dados, raiz)
    except estado.EstadoInvalido as erro:
        raise FechamentoRecusado(f"STATUS.md inválido: {erro.mensagem}") from None
    try:
        head = versao.no_head(raiz, documentos, executar, grupo=versao.em_grupo(dados))
    except versao.VersaoInvalida as erro:
        raise FechamentoRecusado(erro.mensagem) from None
    if head.fora_do_commit:
        verbo = "tem" if len(head.fora_do_commit) == 1 else "têm"
        raise FechamentoRecusado(
            f"{comum.juntar(head.fora_do_commit)} {verbo} mudança fora do commit; faça o commit antes"
        )
    if head.hash_head != marcado:
        raise FechamentoRecusado(
            f"a versão no HEAD não é a marcada ({head.hash_head} != {marcado}); confira com harness.py versao conferir"
        )
    _indice_so_com_o_status(raiz, perfil, executar)

    fechados = {campo: valor for campo, valor in dados.items() if campo not in estado.CAMPOS_OPCIONAIS}
    fechados.update({"Documento": estado.SEM_DOCUMENTO, "Passo": "0", "Rodada": "0", versao.CAMPO: versao.SEM_VERSAO})
    if proximo_texto is None:
        proximo_texto = proximo.calcular(raiz, perfil, dados=fechados, executar=executar).linha_curta
    mudancas = {
        versao.CAMPO: versao.SEM_VERSAO,
        "Documento": estado.SEM_DOCUMENTO,
        estado.CAMPO_PACOTE: estado.SEM_PACOTE,
        estado.CAMPO_LOTE: estado.SEM_PACOTE,
        "Passo": "0",
        "Rodada": "0",
        "Proximo": proximo_texto,
    }
    try:
        estado.definir_varios(caminho, mudancas, perfil, hoje)
    except estado.EstadoInvalido as erro:
        raise FechamentoRecusado(erro.mensagem) from None
    versao.apagar_copias(raiz)
    estado.apagar_lista_do_lote(raiz)
    (raiz / dossie.ARQUIVO_AFETADOS).unlink(missing_ok=True)
    if estado.CAMPO_LOTE in dados:
        origem = estado.origem_do_lote(dados[estado.CAMPO_LOTE])
        descricao = f"lote {origem} de {len(documentos)} documento" + ("" if len(documentos) == 1 else "s")
    else:
        descricao = documentos[0] if len(documentos) == 1 else f"pacote de {len(documentos)} documentos"
    commit_do_status, modo, falha = _commit_do_status(raiz, perfil, documentos, descricao, executar)
    return Fechado(descricao, marcado, head.commit, proximo_texto, commit_do_status, modo, falha)
