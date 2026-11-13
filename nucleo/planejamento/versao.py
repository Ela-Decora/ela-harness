"""Hash da versão enviada para aprovação (passo 6 do ciclo): marcar, conferir e limpar.

`marcar` grava o hash do documento em `Versao-aprovacao`, no STATUS.md, e guarda uma cópia em
`PASTA_APROVACAO`, mais uma entrada no histórico das versões marcadas. `conferir` diz se o arquivo mudou depois
disso; sem a cópia, procura a versão marcada nos commits do arquivo. `historico` e `diff_do_historico` mostram as
versões apresentadas. `limpar` desfaz a marcação e apaga cópias e histórico.
"""
from __future__ import annotations

import datetime
import difflib
import hashlib
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import comum
import estado
from perfil import Perfil

AJUDA = """\
Marca, confere e limpa a versão do documento, ou do pacote, enviada para aprovação, e mostra as versões marcadas.

- `marcar`: o documento é o `Documento` do STATUS.md, que vale sem caminho. Copia o arquivo para a pasta das cópias,
  apaga a `resposta` anterior, grava e imprime `Versao-aprovacao = sha256:<12 hexadecimais>`, o hash da cópia, e põe
  a versão no histórico, se ela não é igual à última de lá. Se o STATUS.md recusar o hash, a cópia sai.
- `conferir`: sai com 0 e `OK: <hash> confere` quando o arquivo é o marcado. Sai com 1 com
  `DIVERGE: arquivo mudou desde a marcação (<atual> != <marcado>)` e o diff da cópia para o arquivo, até 20 linhas, e
  quando o STATUS.md aponta para outro documento, não há versão marcada ou o arquivo sumiu. Sem a cópia e com outro
  hash, procura a versão marcada nos 50 commits mais recentes do arquivo e a restaura, com a linha
  `cópia restaurada do commit <commit>`, ou, sem achá-la, dá a linha
  `versão marcada ausente da cópia e dos últimos 50 commits do arquivo`; com o mesmo hash, ou sem o git, avisa
  `cópia ausente, comparado só o hash`.
- `limpar`: volta o campo para `—`, tira o `Ajuste` do STATUS.md e apaga as cópias, o manifesto, a `resposta` e o histórico; a lista do lote fica.
- `resumo`: o esqueleto das mudanças dos documentos em refino contra o HEAD, por documento e seção (`alterada (+a −r)`,
  `nova`, `removida`) e os IDs que entraram, saíram ou mudaram; o documento fora do HEAD é `novo`. Grava o diff de cada
  camada com mudança em `.claude/harness/dossie/diff-camada-<N>.diff` e cria a pasta `.harness-aprovacao/`, com um
  `.gitignore` de `*`, para o resumo escrito em `.harness-aprovacao/resumo.md`, fora do `.claude/`, onde o Claude Code
  pede permissão a cada escrita. `--desde-marcada` compara com a cópia marcada e,
  sem ela, recusa; `--desde-revisada` (exclusiva com a anterior), com a última versão revisada do histórico, sem
  contar as de ajuste, e sem versão revisada recusa. Sem mudança: `nenhuma mudança contra o HEAD`, ou `contra a versão marcada` ou `contra a versão revisada`. Com
  `--conferir <arquivo>`, confere as linhas `Onde: <documento> · <seção>` do resumo escrito contra as seções que
  mudaram: `OK: <M> mudanças cobrem as <N> seções alteradas`, ou `FALTA:` e `SOBRA:`, e sai com 1.
- `ver <documento> [n]`: a `n`-ésima seção alterada do documento em refino (padrão 1; `--desde-marcada` como no
  `resumo`), só com as linhas que mudaram, a trocada palavra a palavra (`~~antigo~~ **novo**`), a acrescentada entre `**`
  e a tirada entre `~~`, e a legenda dos IDs na primeira aparição. Uma linha tirada e uma acrescentada só viram uma
  trocada quando mais da metade das palavras confere, como no `difflib.Differ`; senão, saem cada uma na sua linha.
  Seção nova: `Seção nova, <k> linhas.`; removida: `Seção removida.`.
- `historico`: lista as versões marcadas, por padrão as do `Documento`, da segunda em diante com as linhas
  acrescentadas e tiradas contra a anterior; sem nenhuma, `sem versões marcadas para <documento>`.
- `diff`: o diff unificado entre duas versões, com `--- versao <n>` e `+++ versao <m>`: sem número, a penúltima contra
  a última; com um, `<n>` contra a última; com dois, `<n>` contra `<m>`. Corta em 60 linhas sem `--completo`. Recusa:
  `recusado: menos de duas versões marcadas para <documento>` ou `recusado: versão <x> inexistente; há <k>`.

```text
01  <AAAA-MM-DD HH:MM>  sha256:<12 hexadecimais>
02  <AAAA-MM-DD HH:MM>  sha256:<12 hexadecimais>  +4 -1
03  <AAAA-MM-DD HH:MM>  sha256:<12 hexadecimais>  +1 -0  ajuste
```

A coluna `ajuste` marca a versão que o `passo 6` gravou durante um ajuste, sem revisor. Se o arquivo não muda e a
marcação seguinte é revisada, a entrada de ajuste perde o rótulo.

Com `Pacote` ou `Lote` no STATUS.md, o `marcar` não aceita caminho e marca o pacote ou o lote: a cópia de cada
documento e o manifesto, uma linha `<hash> <caminho>` por documento, na ordem do `Pacote` ou da lista do lote; o hash
gravado é o do manifesto. O `conferir` sem caminho dá `OK: pacote <hash> confere (<N> documentos)` ou
`DIVERGE: <k> de <N> documentos mudaram desde a marcação: <lista>`, com uma linha `OK:` ou `DIVERGE:` por documento;
com um caminho do pacote, confere só ele, e o OK é `OK: <documento> confere (pacote <hash>)`. Sem o manifesto,
ignora o caminho e compara só o hash do pacote: o OK ganha a linha `manifesto ausente, comparado só o hash`, e a
divergência é `DIVERGE: pacote mudou desde a marcação (<atual> != <marcado>)`, com a linha
`manifesto ausente: não dá para dizer qual documento mudou`. Sai com 1 também com
`<documento> fora do Pacote do STATUS.md` e, quando é preciso marcar de novo, com
`o manifesto do pacote não é o da marcação <hash>; marque de novo com harness.py passo 6` ou
`o Pacote do STATUS.md mudou depois da marcação; marque de novo com harness.py passo 6`. No lote, a palavra é
`lote` em todas elas, `<documento> fora do lote` e `a lista do lote mudou depois da marcação; marque de novo com
harness.py passo 6`.

Pasta das cópias, `.claude/harness/aprovacao/`, fora do git: a cópia (`<caminho com / trocado por __>`), o manifesto
(`pacote`), o histórico (`historico/<nome da cópia>/NN-<AAAA-MM-DD>T<HHMM>-<12 hexadecimais>.md`, com `-ajuste` antes
do `.md` na entrada de ajuste) e a `resposta`.
A lista do lote (`lote`) é de outro comando e o `limpar` a deixa. A `resposta` é a linha `<hash marcado> <AAAA-MM-DDTHH:MM:SS> <trecho>`, que a guarda grava a cada mensagem do usuário
com `Passo` 6 e versão marcada, com os 80 primeiros caracteres dela. O `passo 7` recusa sem ela ou com o hash de outra
marcação: ela prova que houve mensagem depois da marcação, não que a mensagem aprova.

Recusas de entrada, com 1: `STATUS.md aponta para <documento>, não para <documento>`, `arquivo não existe: <documento>`
e o caminho passado com pacote ou lote aberto. No `marcar` e no `conferir` sem pacote, o caminho tem de ser o
`Documento` do STATUS.md, gravado antes com `estado set Documento`; com `Documento: nenhum`, com ou sem o caminho, o `marcar` dá
`Documento: nenhum no STATUS.md; abra o documento com harness.py estado set Documento <caminho>` e o `conferir`,
`Documento: nenhum no STATUS.md; não há versão a conferir`. No `historico` e no `diff --documento` sem o caminho, a
recusa é `Documento: nenhum no STATUS.md; passe o caminho do documento`.
"""

CAMPO = "Versao-aprovacao"
SEM_VERSAO = "—"
LIMITE_DIFF = 20
PASTA_HISTORICO = "historico"
ARQUIVO_RESPOSTA = "resposta"
LIMITE_TRECHO = 80
# Manifesto do pacote marcado (spec 4b, §9.2): uma linha `<hash curto> <caminho>` por documento, na ordem do Pacote.
ARQUIVO_PACOTE = "pacote"
LIMITE_DIFF_HISTORICO = 60

_PREFIXO_HASH = "sha256:"
SUFIXO_AJUSTE = "-ajuste"
_TAMANHO_HASH = 12
_AVISO_SEM_COPIA = "cópia ausente, comparado só o hash"
_COMMITS_PROCURADOS = 50
_TEMPO_LIMITE_GIT = 5
_SEM_VERSAO_NO_GIT = f"versão marcada ausente da cópia e dos últimos {_COMMITS_PROCURADOS} commits do arquivo"
_RE_ENTRADA = re.compile(r"^(\d{2,})-(\d{4}-\d{2}-\d{2})T(\d{2})(\d{2})-([0-9a-f]{12})(-ajuste)?\.md$")
_RE_LINHA_DO_MANIFESTO = re.compile(r"(sha256:[0-9a-f]{12}) (\S+)")
_MARQUE_DE_NOVO = "marque de novo com harness.py passo 6"
_AVISO_SEM_MANIFESTO = "manifesto ausente, comparado só o hash"
_SEM_MANIFESTO_NAO_DA = "manifesto ausente: não dá para dizer qual documento mudou"


class VersaoInvalida(Exception):
    """A entrada não serve: documento fora da raiz, diferente do STATUS.md ou inexistente. `mensagem` diz o motivo."""

    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


class _GitIndisponivel(Exception):
    """O git não respondeu: ausente, com erro do sistema ou fora do tempo."""


def hash_dos_bytes(dados: bytes) -> str:
    """`sha256:` mais os 12 primeiros hexadecimais do SHA-256 dos bytes."""
    return _PREFIXO_HASH + hashlib.sha256(dados).hexdigest()[:_TAMANHO_HASH]


def hash_curto(caminho: Path) -> str:
    """`sha256:` mais os 12 primeiros hexadecimais do SHA-256 dos bytes do arquivo."""
    return hash_dos_bytes(caminho.read_bytes())


def _git(raiz: Path, argumentos: list[str], executar) -> subprocess.CompletedProcess:
    """Roda o git na raiz, com tempo limite. Exceção e tempo esgotado viram _GitIndisponivel."""
    try:
        return executar(["git", "-C", str(raiz), *argumentos], capture_output=True, timeout=_TEMPO_LIMITE_GIT)
    except (OSError, subprocess.SubprocessError) as erro:
        raise _GitIndisponivel(str(erro)) from None


def _versao_no_git(raiz: Path, relativo: str, marcado: str, executar) -> tuple[str, bytes] | None:
    """(commit, bytes) do commit mais recente, entre os últimos do arquivo, cujo conteúdo tem o hash marcado.

    None se nenhum tem. Lança _GitIndisponivel se o git não responde ou o `log` falha.
    """
    log = _git(raiz, ["log", "--format=%H", "-n", str(_COMMITS_PROCURADOS), "--", relativo], executar)
    if log.returncode != 0:
        raise _GitIndisponivel(f"git log saiu com {log.returncode}")
    for commit in (log.stdout or b"").decode("utf-8", errors="replace").split():
        mostrado = _git(raiz, ["show", f"{commit}:./{relativo}"], executar)
        if mostrado.returncode == 0 and hash_dos_bytes(mostrado.stdout) == marcado:
            return commit, mostrado.stdout
    return None


@dataclass(frozen=True)
class Entrada:
    """Uma versão marcada no histórico: `data_hora` em `AAAA-MM-DD HH:MM` e `hash` em `sha256:<12 hex>`."""

    numero: int
    data_hora: str
    hash: str
    caminho: Path
    ajuste: bool = False


def nome_da_copia(documento_relativo: str) -> str:
    """Nome do arquivo da cópia: as barras do caminho relativo viram `__`."""
    return documento_relativo.replace("/", "__")


def _relativo(raiz: Path, documento: Path) -> str:
    """Caminho do documento relativo à raiz, em formato posix. O documento é relativo à raiz ou absoluto."""
    try:
        return (raiz / documento).resolve().relative_to(raiz.resolve()).as_posix()
    except ValueError:
        raise VersaoInvalida(f"documento fora da raiz do projeto: {documento}") from None


def _aponta_para_outro(no_status: str, relativo: str) -> str:
    return f"STATUS.md aponta para {no_status}, não para {relativo}"


def _diff(copia: Path, arquivo: Path) -> list[str]:
    """Diff unificado da cópia marcada para o arquivo atual, com no máximo LIMITE_DIFF linhas."""
    marcada = copia.read_bytes().decode("utf-8", errors="replace").split("\n")
    atual = arquivo.read_bytes().decode("utf-8", errors="replace").split("\n")
    linhas = list(difflib.unified_diff(marcada, atual, fromfile="marcada", tofile="atual", lineterm=""))
    if len(linhas) > LIMITE_DIFF:
        return linhas[:LIMITE_DIFF] + [f"[diff cortado em {LIMITE_DIFF} linhas]"]
    return linhas


def nome_da_entrada(numero: int, agora: datetime.datetime, hash_marcado: str, ajuste: bool = False) -> str:
    """`NN-AAAA-MM-DDTHHMM-<12 hex>.md`, com `-ajuste` antes do `.md` na marcação de ajuste, mais dígitos no número a
    partir de 100 e sem `:`, por causa do Windows."""
    sufixo = SUFIXO_AJUSTE if ajuste else ""
    return f"{numero:02d}-{agora:%Y-%m-%dT%H%M}-{hash_marcado[len(_PREFIXO_HASH):]}{sufixo}.md"


def _pasta_do_historico(raiz: Path, relativo: str) -> Path:
    return raiz / comum.PASTA_APROVACAO / PASTA_HISTORICO / nome_da_copia(relativo)


def _entradas(pasta: Path) -> list[Entrada]:
    """Entradas da pasta do histórico em ordem de número; arquivo com nome fora do padrão fica de fora."""
    if not pasta.is_dir():
        return []
    entradas = []
    for arquivo in pasta.iterdir():
        achado = _RE_ENTRADA.match(arquivo.name)
        if achado and arquivo.is_file():
            numero, data, hora, minuto, digitos, sufixo = achado.groups()
            entradas.append(
                Entrada(int(numero), f"{data} {hora}:{minuto}", _PREFIXO_HASH + digitos, arquivo, sufixo is not None)
            )
    return sorted(entradas, key=lambda entrada: entrada.numero)


def ultima_revisada(raiz: Path, relativo: str) -> Entrada | None:
    """A última entrada do histórico do documento que não é de ajuste; None sem histórico ou só com ajustes."""
    revisadas = [entrada for entrada in _entradas(_pasta_do_historico(raiz, relativo)) if not entrada.ajuste]
    return revisadas[-1] if revisadas else None


def _acrescentar_ao_historico(
    raiz: Path, relativo: str, copia: Path, marcado: str, agora: datetime.datetime, ajuste: bool = False
) -> None:
    """Copia a versão marcada para o histórico, a menos que a última entrada tenha o mesmo hash. Nesse caso, uma
    última entrada de ajuste ganha o nome sem o sufixo quando a marcação é revisada: o ajuste foi revisado."""
    pasta = _pasta_do_historico(raiz, relativo)
    entradas = _entradas(pasta)
    if entradas and entradas[-1].hash == marcado:
        ultima = entradas[-1]
        if ultima.ajuste and not ajuste:
            ultima.caminho.rename(pasta / nome_da_entrada(ultima.numero, _hora_da_entrada(ultima), marcado))
        return
    pasta.mkdir(parents=True, exist_ok=True)
    numero = entradas[-1].numero + 1 if entradas else 1
    shutil.copyfile(copia, pasta / nome_da_entrada(numero, agora, marcado, ajuste))


def _hora_da_entrada(entrada: Entrada) -> datetime.datetime:
    return datetime.datetime.strptime(entrada.data_hora, "%Y-%m-%d %H:%M")


RECUSA_MARCAR_NENHUM = "Documento: nenhum no STATUS.md; abra o documento com harness.py estado set Documento <caminho>"
RECUSA_CONFERIR_NENHUM = "Documento: nenhum no STATUS.md; não há versão a conferir"


def _documento_do_status(dados: dict[str, str]) -> Path:
    """O `Documento` do STATUS.md, para os comandos chamados sem o caminho; `nenhum` lança VersaoInvalida."""
    if dados["Documento"] == estado.SEM_DOCUMENTO:
        raise VersaoInvalida("Documento: nenhum no STATUS.md; passe o caminho do documento")
    return Path(dados["Documento"])


def _texto_do_manifesto(itens: list[tuple[str, str]]) -> str:
    return "".join(f"{hash_} {relativo}\n" for hash_, relativo in itens)


def hash_da_versao(conteudos: list[tuple[str, bytes]], grupo: bool = False) -> str:
    """O hash que o `passo 6` marcaria para estes conteúdos, (caminho relativo, bytes) na ordem do pacote: com
    `grupo` (`Pacote` ou `Lote` no STATUS.md) ou com dois ou mais itens, o hash do texto do manifesto; senão, o hash
    dos bytes do único item."""
    if len(conteudos) == 1 and not grupo:
        return hash_dos_bytes(conteudos[0][1])
    texto = _texto_do_manifesto([(hash_dos_bytes(dados), relativo) for relativo, dados in conteudos])
    return hash_dos_bytes(texto.encode("utf-8"))


@dataclass(frozen=True)
class NoHead:
    """A versão dos documentos no HEAD (spec 4a, §7.2): os 7 primeiros hexadecimais do commit (vazio sem commit), o
    hash que o `passo 6` marcaria para o disco quando ele é o conteúdo do HEAD, cru ou com os filtros do git (None com
    algum documento fora do commit) e os documentos ausentes do HEAD ou com o disco diferente dele, na ordem pedida."""

    commit: str
    hash_head: str | None
    fora_do_commit: tuple[str, ...]


def _formas_no_head(raiz: Path, relativo: str, executar) -> list[bytes]:
    """O documento no HEAD como está no blob e como o git o poria no disco, com os filtros e a conversão de quebras
    (`core.autocrlf` do Git for Windows deixa CRLF no disco e LF no blob); vazio quando ele não está no HEAD."""
    formas: list[bytes] = []
    for argumentos in (["show", f"HEAD:./{relativo}"], ["cat-file", "--filters", f"HEAD:./{relativo}"]):
        saida = _git(raiz, argumentos, executar)
        if saida.returncode == 0:
            formas.append(saida.stdout)
    return formas


def no_head(raiz: Path, documentos: list[str], executar=subprocess.run, grupo: bool = False) -> NoHead:
    """Confere os documentos no HEAD pelo git, sem a pasta das cópias, de modo que vale noutra máquina; `grupo` é o do
    `hash_da_versao`. Sem `.git` na raiz, ou com o git indisponível, lança VersaoInvalida."""
    if not os.path.lexists(raiz / ".git"):
        raise VersaoInvalida("a raiz não é um repositório git")
    try:
        head = _git(raiz, ["rev-parse", "--verify", "-q", "HEAD"], executar)
        if head.returncode != 0:
            return NoHead("", None, tuple(documentos))
        commit = (head.stdout or b"").decode("utf-8", errors="replace").strip()[:7]
        conteudos: list[tuple[str, bytes]] = []
        fora: list[str] = []
        for relativo in documentos:
            try:
                disco = (raiz / relativo).read_bytes()
            except OSError:
                disco = None
            if disco is not None and any(disco == forma for forma in _formas_no_head(raiz, relativo, executar)):
                conteudos.append((relativo, disco))
            else:
                fora.append(relativo)
    except _GitIndisponivel as erro:
        raise VersaoInvalida(f"git indisponível: {erro}") from None
    return NoHead(commit, None if fora else hash_da_versao(conteudos, grupo), tuple(fora))


def _rotulo(dados: dict[str, str]) -> str:
    """A palavra das mensagens do ciclo em grupo: `lote` com `Lote` no STATUS.md, senão `pacote`."""
    return "lote" if estado.CAMPO_LOTE in dados else "pacote"


def em_grupo(dados: dict[str, str]) -> bool:
    """Se o STATUS.md tem `Pacote` ou `Lote`: aí o `passo 6` marca o hash do manifesto, mesmo com um documento só."""
    return estado.CAMPO_PACOTE in dados or estado.CAMPO_LOTE in dados


def _marcar_pacote(
    raiz: Path, perfil: Perfil, dados: dict[str, str], agora: datetime.datetime | None, ajuste: bool = False
) -> str:
    """Copia cada documento do pacote, grava o manifesto e o hash dele em `Versao-aprovacao`; devolve o hash.

    Documento ausente lança VersaoInvalida antes de gravar. Se o STATUS.md recusar o hash, as cópias e o manifesto
    recém-gravados são removidos. Com o hash gravado, cada documento entra no próprio histórico, com o rótulo de
    ajuste quando `ajuste`."""
    relativos = estado.documentos(dados, raiz)
    faltando = next((relativo for relativo in relativos if not (raiz / relativo).is_file()), None)
    if faltando is not None:
        raise VersaoInvalida(f"arquivo não existe: {faltando}")
    pasta = raiz / comum.PASTA_APROVACAO
    pasta.mkdir(parents=True, exist_ok=True)
    copias = []
    for relativo in relativos:
        copia = pasta / nome_da_copia(relativo)
        shutil.copyfile(raiz / relativo, copia)
        copias.append((relativo, copia, hash_curto(copia)))
    manifesto = pasta / ARQUIVO_PACOTE
    texto = _texto_do_manifesto([(hash_, relativo) for relativo, _, hash_ in copias])
    comum.escrever_texto(manifesto, texto)
    marcado = hash_dos_bytes(texto.encode("utf-8"))
    (pasta / ARQUIVO_RESPOSTA).unlink(missing_ok=True)
    try:
        estado.definir(raiz / perfil.caminhos.status, CAMPO, marcado, perfil)
    except estado.EstadoInvalido:
        for _, copia, _ in copias:
            copia.unlink(missing_ok=True)
        manifesto.unlink(missing_ok=True)
        raise
    momento = agora or datetime.datetime.now()
    for relativo, copia, hash_ in copias:
        _acrescentar_ao_historico(raiz, relativo, copia, hash_, momento, ajuste)
    return marcado


def marcar(
    raiz: Path, documento: Path | None, perfil: Perfil, agora: datetime.datetime | None = None, ajuste: bool = False
) -> str:
    """Grava a cópia do documento e o hash dela em `Versao-aprovacao`; devolve o hash.

    Com `Pacote` ou `Lote` no STATUS.md, marca o grupo inteiro (spec 4b, §9.2) e recusa o caminho. Sem pacote, o documento
    é relativo à raiz ou absoluto e precisa ser o `Documento` do STATUS.md; sem ele, vale o `Documento`. Lança
    VersaoInvalida com `Documento: nenhum` (com ou sem o caminho), se o caminho não é o `Documento`, se está fora da
    raiz ou se o arquivo não existe, e EstadoInvalido se o STATUS.md não
    serve. Nesses casos nada é gravado. Se o STATUS.md recusar o hash, a cópia recém-gravada é removida. A
    `resposta` da marcação anterior é apagada antes de gravar o hash. Com o hash gravado, a versão entra no histórico
    com a hora `agora` (padrão: a hora local), a menos que seja igual à última de lá; com `ajuste`, a entrada leva o
    sufixo `-ajuste`, e uma marcação revisada igual à última, que é de ajuste, tira o sufixo dela.
    """
    status = raiz / perfil.caminhos.status
    dados = estado.ler(status, perfil)
    if em_grupo(dados):
        if documento is not None:
            rotulo = _rotulo(dados)
            raise VersaoInvalida(
                f"{rotulo.capitalize()} aberto: versao marcar marca o {rotulo} inteiro; rode sem o caminho"
            )
        return _marcar_pacote(raiz, perfil, dados, agora, ajuste)
    if dados["Documento"] == estado.SEM_DOCUMENTO:
        raise VersaoInvalida(RECUSA_MARCAR_NENHUM)
    relativo = _relativo(raiz, documento if documento is not None else _documento_do_status(dados))
    no_status = dados["Documento"]
    if no_status != relativo:
        raise VersaoInvalida(_aponta_para_outro(no_status, relativo))
    arquivo = raiz / relativo
    if not arquivo.is_file():
        raise VersaoInvalida(f"arquivo não existe: {relativo}")

    pasta = raiz / comum.PASTA_APROVACAO
    pasta.mkdir(parents=True, exist_ok=True)
    copia = pasta / nome_da_copia(relativo)
    shutil.copyfile(arquivo, copia)
    # O hash vem da cópia: assim os dois não discordam se o arquivo mudar entre uma leitura e outra.
    marcado = hash_curto(copia)
    # A mensagem do usuário que valia para a marcação anterior não vale para esta.
    (pasta / ARQUIVO_RESPOSTA).unlink(missing_ok=True)
    try:
        estado.definir(status, CAMPO, marcado, perfil)
    except estado.EstadoInvalido:
        copia.unlink()
        raise
    _acrescentar_ao_historico(raiz, relativo, copia, marcado, agora or datetime.datetime.now(), ajuste)
    return marcado


def _comparar(raiz: Path, relativo: str, marcado: str, executar) -> tuple[str | None, list[str]]:
    """O hash atual do arquivo (None se ele não existe) e as linhas que vão abaixo do cabeçalho do `conferir`: o aviso
    de cópia ausente, o diff contra a cópia, ou a cópia restaurada do git e o diff.

    Sem a cópia e com o hash diferente, a versão marcada é procurada nos últimos commits do arquivo; achada, a cópia
    é restaurada e o diff sai como se ela sempre tivesse estado lá. Git ausente, com erro ou lento: o aviso de cópia
    ausente."""
    arquivo = raiz / relativo
    if not arquivo.is_file():
        return None, []
    atual = hash_curto(arquivo)
    copia = raiz / comum.PASTA_APROVACAO / nome_da_copia(relativo)
    if atual == marcado:
        return atual, [] if copia.is_file() else [_AVISO_SEM_COPIA]
    if copia.is_file():
        return atual, _diff(copia, arquivo)
    try:
        achada = _versao_no_git(raiz, relativo, marcado, executar)
    except _GitIndisponivel:
        return atual, [_AVISO_SEM_COPIA]
    if achada is None:
        return atual, [_SEM_VERSAO_NO_GIT]
    commit, conteudo = achada
    copia.parent.mkdir(parents=True, exist_ok=True)
    copia.write_bytes(conteudo)
    return atual, [f"cópia restaurada do commit {commit[:7]}"] + _diff(copia, arquivo)


def _ler_manifesto(raiz: Path) -> list[tuple[str, str]] | None:
    """(hash, caminho) de cada linha do manifesto; None se ele falta, não se lê ou tem linha fora do formato."""
    try:
        texto = comum.ler_texto(raiz / comum.PASTA_APROVACAO / ARQUIVO_PACOTE)
    except (OSError, UnicodeDecodeError):
        return None
    itens = []
    for linha in texto.splitlines():
        achado = _RE_LINHA_DO_MANIFESTO.fullmatch(linha)
        if achado is None:
            return None
        itens.append((achado.group(1), achado.group(2)))
    return itens


def _conferir_pacote(
    raiz: Path, dados: dict[str, str], documento: Path | None, executar
) -> tuple[bool, str]:
    """O `conferir` com pacote (spec 4b, §9.2): o manifesto contra o `Versao-aprovacao` e cada documento, ou só o
    `documento`, contra o hash do manifesto. Sem o manifesto, compara só o hash do manifesto refeito do disco."""
    relativos = estado.documentos(dados, raiz)
    rotulo = _rotulo(dados)
    marcado = dados[CAMPO]
    if marcado == SEM_VERSAO:
        return False, "sem versão marcada no STATUS.md"
    manifesto = _ler_manifesto(raiz)
    if manifesto is None:
        faltando = next((relativo for relativo in relativos if not (raiz / relativo).is_file()), None)
        if faltando is not None:
            return False, f"arquivo não existe: {faltando}"
        atual = hash_dos_bytes(
            _texto_do_manifesto([(hash_curto(raiz / relativo), relativo) for relativo in relativos]).encode("utf-8")
        )
        if atual == marcado:
            return True, f"OK: {rotulo} {marcado} confere ({len(relativos)} documentos)\n{_AVISO_SEM_MANIFESTO}"
        return False, f"DIVERGE: {rotulo} mudou desde a marcação ({atual} != {marcado})\n{_SEM_MANIFESTO_NAO_DA}"
    if hash_dos_bytes(_texto_do_manifesto(manifesto).encode("utf-8")) != marcado:
        return False, f"o manifesto do {rotulo} não é o da marcação {marcado}; {_MARQUE_DE_NOVO}"
    if [relativo for _, relativo in manifesto] != relativos:
        mudou = "a lista do lote" if rotulo == "lote" else "o Pacote do STATUS.md"
        return False, f"{mudou} mudou depois da marcação; {_MARQUE_DE_NOVO}"
    hashes = {relativo: hash_ for hash_, relativo in manifesto}
    alvos = relativos
    if documento is not None:
        relativo = _relativo(raiz, documento)
        if relativo not in hashes:
            fora = "fora do lote" if rotulo == "lote" else "fora do Pacote do STATUS.md"
            return False, f"{relativo} {fora}"
        alvos = [relativo]
    divergentes: list[str] = []
    linhas: list[str] = []
    for relativo in alvos:
        atual, extras = _comparar(raiz, relativo, hashes[relativo], executar)
        if atual is None:
            divergentes.append(relativo)
            linhas.append(f"DIVERGE: {relativo}: arquivo não existe")
        elif atual == hashes[relativo]:
            linhas += [f"OK: {relativo} ({atual})"] + extras
        else:
            divergentes.append(relativo)
            linhas += [f"DIVERGE: {relativo} mudou desde a marcação ({atual} != {hashes[relativo]})"] + extras
    quantos = f"{len(alvos)} documento" + ("" if len(alvos) == 1 else "s")
    if divergentes:
        cabecalho = f"DIVERGE: {len(divergentes)} de {quantos} mudaram desde a marcação: {comum.juntar(divergentes)}"
    else:
        cabecalho = f"OK: {rotulo} {marcado} confere ({quantos})"
        if documento is not None:
            cabecalho = f"OK: {alvos[0]} confere ({rotulo} {marcado})"
    return not divergentes, "\n".join([cabecalho] + linhas)


def conferir(raiz: Path, documento: Path | None, perfil: Perfil, executar=subprocess.run) -> tuple[bool, str]:
    """Diz se o documento ainda é a versão marcada: `(confere, mensagem pronta para imprimir)`.

    Com `Pacote` ou `Lote` no STATUS.md, confere o grupo, ou só o `documento` dele (spec 4b, §9.2). Sem pacote, as
    verificações, em ordem: `Documento` do STATUS.md igual ao argumento (sem argumento, vale o `Documento`), versão
    marcada, arquivo existente e, por fim, o hash. Lança VersaoInvalida para documento fora da raiz ou para
    `Documento: nenhum`, com ou sem argumento, e EstadoInvalido se o STATUS.md não serve. `executar` é injetável para teste.
    """
    dados = estado.ler(raiz / perfil.caminhos.status, perfil)
    if em_grupo(dados):
        return _conferir_pacote(raiz, dados, documento, executar)
    if dados["Documento"] == estado.SEM_DOCUMENTO:
        raise VersaoInvalida(RECUSA_CONFERIR_NENHUM)
    relativo = _relativo(raiz, documento if documento is not None else _documento_do_status(dados))
    if dados["Documento"] != relativo:
        return False, _aponta_para_outro(dados["Documento"], relativo)
    marcado = dados[CAMPO]
    if marcado == SEM_VERSAO:
        return False, "sem versão marcada no STATUS.md"
    atual, extras = _comparar(raiz, relativo, marcado, executar)
    if atual is None:
        return False, f"arquivo não existe: {relativo}"
    if atual == marcado:
        return True, "\n".join([f"OK: {atual} confere"] + extras)
    return False, "\n".join([f"DIVERGE: arquivo mudou desde a marcação ({atual} != {marcado})"] + extras)


def trecho_da_mensagem(texto: str) -> str:
    """A mensagem numa linha, com os espaços juntados, cortada em LIMITE_TRECHO caracteres (spec 4a, §10.3)."""
    return " ".join(texto.split())[:LIMITE_TRECHO]


def anotar_resposta(raiz: Path, perfil: Perfil, agora: datetime.datetime | None = None, mensagem: str = "") -> bool:
    """Prova de mensagem (spec 3b, §7.1, e 4a, §10.3): com `Passo` 6 e versão marcada no STATUS.md, grava
    `<hash> <hora>` na `resposta`, mais ` <trecho>` da mensagem quando ele não é vazio, e devolve True; senão não grava
    e devolve False. Lança EstadoInvalido se o STATUS.md não serve."""
    dados = estado.ler(raiz / perfil.caminhos.status, perfil)
    if dados["Passo"] != "6" or dados[CAMPO] == SEM_VERSAO:
        return False
    agora = agora or datetime.datetime.now()
    trecho = trecho_da_mensagem(mensagem)
    linha = f"{dados[CAMPO]} {agora:%Y-%m-%dT%H:%M:%S}" + (f" {trecho}" if trecho else "")
    comum.escrever_texto(raiz / comum.PASTA_APROVACAO / ARQUIVO_RESPOSTA, linha + "\n")
    return True


@dataclass(frozen=True)
class Resposta:
    """A prova de mensagem lida: o hash marcado, a hora em `HH:MM:SS` e o trecho da mensagem, vazio no formato da 3b."""

    hash: str
    hora: str
    trecho: str


def ler_resposta(raiz: Path) -> Resposta | None:
    """A `resposta` gravada; arquivo ausente, vazio ou ilegível dá None."""
    try:
        texto = comum.ler_texto(raiz / comum.PASTA_APROVACAO / ARQUIVO_RESPOSTA)
    except (OSError, UnicodeDecodeError):
        return None
    partes = texto.rstrip("\n").split(" ", 2)
    if len(partes) < 2 or not partes[0]:
        return None
    return Resposta(partes[0], partes[1].rpartition("T")[2], partes[2] if len(partes) > 2 else "")


def resposta_confere(raiz: Path, marcado: str) -> bool:
    """A primeira palavra da `resposta` é o hash `marcado`; arquivo ausente, vazio ou ilegível dá False."""
    try:
        palavras = comum.ler_texto(raiz / comum.PASTA_APROVACAO / ARQUIVO_RESPOSTA).split()
    except (OSError, UnicodeDecodeError):
        return False
    return bool(palavras) and palavras[0] == marcado


def _linhas_do_arquivo(caminho: Path) -> list[str]:
    return caminho.read_bytes().decode("utf-8", errors="replace").split("\n")


def historico(raiz: Path, perfil: Perfil, documento: Path | None = None) -> tuple[str, list[Entrada]]:
    """O caminho relativo do documento (o argumento ou o `Documento` do STATUS.md) e as entradas do histórico dele.

    Lança VersaoInvalida para documento fora da raiz ou sem argumento com `Documento: nenhum`, e EstadoInvalido se
    o STATUS.md não serve quando é preciso lê-lo.
    """
    if documento is not None:
        relativo = _relativo(raiz, documento)
    else:
        relativo = estado.ler(raiz / perfil.caminhos.status, perfil)["Documento"]
        if relativo == "nenhum":
            raise VersaoInvalida("Documento: nenhum no STATUS.md; passe o caminho do documento")
    return relativo, _entradas(_pasta_do_historico(raiz, relativo))


def _contagem(anterior: Entrada, atual: Entrada) -> tuple[int, int]:
    """Linhas acrescentadas e tiradas no diff unificado de `anterior` para `atual`, sem os cabeçalhos."""
    acrescentadas = tiradas = 0
    diff = difflib.unified_diff(_linhas_do_arquivo(anterior.caminho), _linhas_do_arquivo(atual.caminho), lineterm="")
    for linha in list(diff)[2:]:
        if linha.startswith("+"):
            acrescentadas += 1
        elif linha.startswith("-"):
            tiradas += 1
    return acrescentadas, tiradas


def formatar_historico(relativo: str, entradas: list[Entrada]) -> str:
    """Uma linha por versão, `NN  AAAA-MM-DD HH:MM  sha256:<12>`, e da segunda em diante `  +<a> -<r>` contra a
    anterior, e `  ajuste` no fim da entrada de ajuste. Sem entradas, `sem versões marcadas para <documento>`."""
    if not entradas:
        return f"sem versões marcadas para {relativo}\n"
    linhas = []
    for posicao, entrada in enumerate(entradas):
        linha = f"{entrada.numero:02d}  {entrada.data_hora}  {entrada.hash}"
        if posicao > 0:
            acrescentadas, tiradas = _contagem(entradas[posicao - 1], entrada)
            linha += f"  +{acrescentadas} -{tiradas}"
        if entrada.ajuste:
            linha += "  ajuste"
        linhas.append(linha)
    return "".join(linha + "\n" for linha in linhas)


def diff_do_historico(
    raiz: Path,
    perfil: Perfil,
    n: int | None = None,
    m: int | None = None,
    completo: bool = False,
    documento: Path | None = None,
) -> str:
    """Diff unificado entre duas versões do histórico: sem `n`, a penúltima contra a última; só com `n`, `n` contra
    a última; com os dois, `n` contra `m`. Sem `completo`, corta em LIMITE_DIFF_HISTORICO linhas.

    Lança VersaoInvalida com menos de duas versões ou com número que não existe.
    """
    relativo, entradas = historico(raiz, perfil, documento)
    if len(entradas) < 2:
        raise VersaoInvalida(f"menos de duas versões marcadas para {relativo}")
    por_numero = {entrada.numero: entrada for entrada in entradas}
    for numero in (n, m):
        if numero is not None and numero not in por_numero:
            raise VersaoInvalida(f"versão {numero} inexistente; há {len(entradas)}")
    if n is None:
        anterior, atual = entradas[-2], entradas[-1]
    else:
        anterior, atual = por_numero[n], por_numero[m] if m is not None else entradas[-1]
    linhas = list(difflib.unified_diff(
        _linhas_do_arquivo(anterior.caminho), _linhas_do_arquivo(atual.caminho),
        fromfile=f"versao {anterior.numero}", tofile=f"versao {atual.numero}", lineterm="",
    ))
    if not linhas:
        return f"sem diferença entre a versão {anterior.numero} e a {atual.numero}\n"
    if not completo and len(linhas) > LIMITE_DIFF_HISTORICO:
        linhas = linhas[:LIMITE_DIFF_HISTORICO] + [
            f"[diff cortado em {LIMITE_DIFF_HISTORICO} linhas; --completo mostra tudo]"
        ]
    return "".join(linha + "\n" for linha in linhas)


def limpar(raiz: Path, perfil: Perfil) -> None:
    """Volta `Versao-aprovacao` para `—`, tira o `Ajuste` e apaga todas as cópias de `PASTA_APROVACAO`, a `resposta` e o histórico.

    Só um documento fica marcado por vez; cópia de outro documento é sobra e sai junto. Sem cópias, só o
    campo volta. Lança EstadoInvalido se o STATUS.md não serve.
    """
    status = raiz / perfil.caminhos.status
    estado.ler(status, perfil)
    estado.definir_varios(status, {CAMPO: SEM_VERSAO, estado.CAMPO_AJUSTE: SEM_VERSAO}, perfil)
    apagar_copias(raiz)


def apagar_copias(raiz: Path) -> None:
    """Apaga as cópias de `PASTA_APROVACAO`, o manifesto, a `resposta`, o histórico e o resumo escrito, sem tocar no
    STATUS.md nem na lista do lote."""
    (raiz / comum.ARQUIVO_RESUMO).unlink(missing_ok=True)
    pasta = raiz / comum.PASTA_APROVACAO
    if pasta.is_dir():
        for copia in pasta.iterdir():
            if copia.is_file() and copia.name != estado.ARQUIVO_LOTE:
                copia.unlink()
        if (pasta / PASTA_HISTORICO).is_dir():
            shutil.rmtree(pasta / PASTA_HISTORICO)
