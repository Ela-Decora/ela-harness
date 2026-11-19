"""A fila das verificações: uma árvore por vez na máquina, por uma trava exclusiva no arquivo do diretório comum do git.

A trava é um `fcntl.flock` no `harness-fila`, que a árvore principal e as lanes dividem. Quem a segura escreve no
arquivo o caminho da árvore dele, que apaga antes de soltar, e marca o ambiente com `HARNESS_NA_FILA=1`, que os
comandos das verificações herdam.
Quem espera tenta a trava a cada meio segundo e avisa uma vez, na saída de erro. A trava cai quando o arquivo fecha,
também com o processo morto; não há arquivo a limpar. Sem o `fcntl`, fora de um repositório git ou com o arquivo que
não abre, não há fila.

Ao lado, a trava do portão (decisão 27): o `bloco executado` e o `bloco finalizar` seguram, do começo ao fim, um
`flock` no `harness-portao` do diretório do git da própria árvore. O segundo portão da mesma árvore espera o primeiro,
sem aviso, e o Stop que a acha tomada não confere nada. Valem as mesmas regras da fila: sem `fcntl`, fora de um
repositório git ou com o arquivo que não abre, não há trava, e ela cai com o processo, sem passar aos filhos.
"""
from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import time
from pathlib import Path

try:
    import fcntl
except ImportError:  # fora do Unix, não há fila
    fcntl = None

import bloco

ARQUIVO = "harness-fila"
ARQUIVO_DO_PORTAO = "harness-portao"
INTERVALO = 0.5
MARCA_DO_AMBIENTE = "HARNESS_NA_FILA"


def arquivo(raiz: Path, executar=subprocess.run) -> Path | None:
    """O arquivo da fila, no diretório comum do git da árvore; fora de um repositório, ou sem o git, None."""
    try:
        feito = bloco.git(raiz, ["rev-parse", "--git-common-dir"], executar)
    except bloco.Recusa:
        return None
    comum_ = os.fsdecode(feito.stdout.strip())
    if feito.returncode != 0 or not comum_:
        return None
    return Path(raiz) / comum_ / ARQUIVO


def arquivo_do_portao(raiz: Path, executar=subprocess.run) -> Path | None:
    """O arquivo da trava do portão, no diretório do git da própria árvore; fora de um repositório, ou sem o git,
    None."""
    try:
        feito = bloco.git(raiz, ["rev-parse", "--absolute-git-dir"], executar)
    except bloco.Recusa:
        return None
    diretorio = os.fsdecode(feito.stdout.strip())
    if feito.returncode != 0 or not diretorio:
        return None
    return Path(diretorio) / ARQUIVO_DO_PORTAO


@contextlib.contextmanager
def portao(arquivo: Path | None):
    """Segura a trava do portão enquanto o bloco roda; o outro portão da mesma árvore espera, sem aviso. Sem arquivo,
    sem `fcntl`, com o arquivo que não abre ou o sistema que não trava, roda sem trava."""
    if arquivo is None or fcntl is None:
        yield
        return
    try:
        aberto = open(arquivo, "a", encoding="utf-8")
    except OSError:
        yield
        return
    try:
        with contextlib.suppress(OSError):
            fcntl.flock(aberto.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        with contextlib.suppress(OSError):
            aberto.close()


def portao_rodando(arquivo: Path | None) -> bool:
    """Se a trava do portão está tomada agora; sem arquivo, sem `fcntl` ou com o arquivo que não abre, False."""
    if arquivo is None or fcntl is None:
        return False
    try:
        with open(arquivo, "a", encoding="utf-8") as aberto:
            return _tentar(aberto) is False  # o fechamento solta a trava tomada aqui
    except OSError:
        return False


def _tentar(aberto) -> bool | None:
    """Tenta a trava sem esperar: True com ela, False com a fila tomada e None quando o sistema não trava."""
    try:
        fcntl.flock(aberto.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    except OSError:
        return None
    return True


def ocupante(arquivo: Path | None) -> str | None:
    """O caminho escrito por quem segura a trava agora; None com a fila livre, sem arquivo ou sem `fcntl`."""
    if arquivo is None or fcntl is None:
        return None
    try:
        with open(arquivo, encoding="utf-8") as aberto:
            if _tentar(aberto) is not False:
                return None  # o fechamento solta a trava tomada aqui
            return aberto.read().strip() or None
    except (OSError, UnicodeDecodeError):
        return None


def _avisar(texto: str) -> None:
    print(texto, file=sys.stderr)


def _quem_segura(aberto) -> str:
    try:
        aberto.seek(0)
        caminho = aberto.read().strip()
    except (OSError, UnicodeDecodeError):
        caminho = ""
    return Path(caminho).name if caminho else "outra árvore"


def _escrever(aberto, caminho: str) -> None:
    """Troca o conteúdo do arquivo da fila pelo caminho; o arquivo que não se escreve não impede a verificação."""
    with contextlib.suppress(OSError):
        aberto.seek(0)
        aberto.truncate()
        aberto.write(caminho)
        aberto.flush()


@contextlib.contextmanager
def vaga(arquivo: Path | None, arvore: Path, prazo: float | None = None, relogio=time.monotonic, dormir=time.sleep,
         avisar=_avisar):
    """A vaga da fila para a árvore: entrega True com a trava, ou sem fila, e False quando o prazo, no relógio dado,
    passa sem ela. Sem prazo, espera o quanto for; o relógio só é lido na espera com prazo. Quem espera avisa uma vez,
    pelo `avisar`. Com a trava, o arquivo recebe o caminho da árvore e o ambiente, a marca; na saída, as duas saem, o
    arquivo esvaziado antes de a trava cair. O arquivo que não se escreve conta como vaga sem dono escrito."""
    if arquivo is None or fcntl is None:
        yield True
        return
    try:
        aberto = open(arquivo, "a+", encoding="utf-8")
    except OSError:
        yield True
        return
    try:
        avisado = False
        while True:
            tomada = _tentar(aberto)
            if tomada is not False:
                break
            if not avisado:
                avisar(f"fila: esperando a verificação de {_quem_segura(aberto)}")
                avisado = True
            if prazo is not None and relogio() >= prazo:
                yield False
                return
            dormir(INTERVALO)
        if tomada is None:  # o sistema de arquivos não trava: sem fila
            yield True
            return
        _escrever(aberto, str(Path(arvore).resolve()))
        os.environ[MARCA_DO_AMBIENTE] = "1"
        try:
            yield True
        finally:
            os.environ.pop(MARCA_DO_AMBIENTE, None)
            _escrever(aberto, "")  # ainda com a trava: o arquivo da fila livre não guarda o dono antigo
    finally:
        with contextlib.suppress(OSError):
            aberto.close()
