"""Utilitários do harness: raiz do projeto, leitura e escrita de texto, datas, motivos de erro, listas em prosa e
caminhos com padrões. São compartilhados pelos módulos do harness de planejamento; os motivos de erro são os do
sistema, e os caminhos com padrões são relativos."""
from __future__ import annotations

import datetime
import errno
import fnmatch
import os
import posixpath
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

import caminho

PASTA_APROVACAO = ".claude/harness/aprovacao"
CAMINHO_PERFIL = ".claude/perfil.toml"
# O link que o lançador do projeto segue até o núcleo do plugin.
LINK_DO_NUCLEO = ".claude/harness/nucleo"
# O prefixo com que o plugin entrega as skills e os agentes: o núcleo imprime `/<prefixo><skill>` e o texto gerado
# manda despachar `<prefixo><agente>`. O workflow `revisao-do-bloco` repete o valor, e um teste confere os dois.
PREFIXO_DAS_SKILLS = "ela-harness:"

_RE_DATA = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")


class RaizNaoEncontrada(FileNotFoundError):
    """Nenhuma pasta acima da pasta atual tem um CLAUDE.md e CLAUDE_PROJECT_DIR não está definida."""


class DiretorioApagado(RaizNaoEncontrada):
    """O diretório atual não existe mais, e a raiz dos comandos não se acha a partir dele."""


def procurar_raiz(inicio: Path) -> Path:
    """Sobe a partir de `inicio` até achar uma pasta com CLAUDE.md."""
    inicio = inicio.resolve()
    for pasta in (inicio, *inicio.parents):
        if (pasta / "CLAUDE.md").is_file():
            return pasta
    raise RaizNaoEncontrada(
        f"raiz do projeto não encontrada: sem CLAUDE.md acima de {inicio}; defina CLAUDE_PROJECT_DIR"
    )


def raiz_projeto() -> Path:
    """Raiz do projeto: `CLAUDE_PROJECT_DIR` se estiver definida; senão, a primeira pasta com CLAUDE.md a partir da
    pasta atual. O núcleo mora no plugin, fora do projeto, e por isso não sobe a partir deste arquivo."""
    definida = os.environ.get("CLAUDE_PROJECT_DIR")
    if definida:
        return Path(definida)
    return procurar_raiz(Path.cwd())


def raiz_do_nucleo() -> Path:
    """Raiz do plugin: a pasta acima de `nucleo/`, com `skills/`, `agents/`, `docs/` e `modelo/`."""
    return caminho.RAIZ_DO_PLUGIN


def raiz_dos_comandos(inicio: Path | None = None) -> Path:
    """Raiz dos comandos rodados pelo terminal: `inicio`, por padrão o diretório atual, ou a primeira pasta acima dele
    com `.claude/perfil.toml`; sem ela, a de `raiz_projeto()`.

    Quando `CLAUDE_PROJECT_DIR` aponta para a mesma pasta achada, vale a grafia da variável, para as mensagens com
    caminho não mudarem com o `/private` que o diretório atual do macOS dá. Os hooks não usam esta regra. O diretório
    atual apagado lança `DiretorioApagado`.
    """
    if inicio is None:
        try:
            inicio = Path.cwd()
        except FileNotFoundError:
            raise DiretorioApagado("o diretório atual não existe mais; rode o comando de uma pasta que existe") from None
    inicio = inicio.absolute()
    for pasta in (inicio, *inicio.parents):
        if (pasta / CAMINHO_PERFIL).is_file():
            definida = os.environ.get("CLAUDE_PROJECT_DIR")
            try:
                if definida and os.path.samefile(definida, pasta):
                    return Path(definida)
            except OSError:
                pass
            return pasta
    return raiz_projeto()


def ler_texto(caminho: Path) -> str:
    """Lê o arquivo em UTF-8, sem converter quebras de linha."""
    with open(caminho, encoding="utf-8", newline="") as arquivo:
        return arquivo.read()


def ler_entrada() -> str:
    """Todo o stdin em UTF-8, sem depender do locale do hook."""
    bruto = getattr(sys.stdin, "buffer", None)
    if bruto is not None:
        return bruto.read().decode("utf-8", errors="replace")
    return sys.stdin.read()


def forcar_utf8() -> None:
    """Põe o stdout em UTF-8: o hook roda fora do terminal, talvez com locale C, e o Python 3.9 quebraria no acento."""
    reconfigurar = getattr(sys.stdout, "reconfigure", None)
    if reconfigurar is None:
        return
    try:
        reconfigurar(encoding="utf-8", errors="replace")
    except (ValueError, OSError):
        pass


def leitor_do_disco(raiz: Path) -> Callable[[str], str | None]:
    """O `ler` sobre o disco: o texto em UTF-8 do caminho relativo à raiz, ou None se ausente ou ilegível."""

    def ler(relativo: str) -> str | None:
        try:
            return ler_texto(raiz / relativo)
        except (OSError, UnicodeDecodeError):
            return None

    return ler


def escrever_texto(caminho: Path, texto: str) -> None:
    """Grava o texto em UTF-8, com quebras de linha `\\n`, criando as pastas que faltarem.

    A gravação é atômica: o texto vai para um temporário na mesma pasta, que substitui o arquivo com
    `os.replace`. Uma falha no meio deixa o arquivo original intacto. Texto que não vira UTF-8 lança
    UnicodeEncodeError antes de qualquer arquivo ser aberto. Arquivo existente mantém a permissão, e
    arquivo somente leitura lança PermissionError sem ser trocado.
    """
    dados = texto.encode("utf-8")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    try:
        modo = stat.S_IMODE(os.stat(caminho).st_mode)
        if not os.access(caminho, os.W_OK):
            # A troca por os.replace passaria por cima de um arquivo somente leitura; recusa como open("w") faria.
            raise PermissionError(errno.EACCES, os.strerror(errno.EACCES), str(caminho))
    except FileNotFoundError:
        mascara = os.umask(0)
        os.umask(mascara)
        modo = 0o666 & ~mascara
    descritor, temporario = tempfile.mkstemp(dir=caminho.parent, prefix=f".{caminho.name}.", suffix=".tmp")
    try:
        with os.fdopen(descritor, "wb") as arquivo:
            arquivo.write(dados)
        os.chmod(temporario, modo)
        os.replace(temporario, caminho)
    except BaseException:
        Path(temporario).unlink(missing_ok=True)
        raise


def data_valida(valor: str) -> bool:
    """`AAAA-MM-DD` com uma data que existe no calendário."""
    partes = _RE_DATA.fullmatch(valor)
    if not partes:
        return False
    try:
        datetime.date(int(partes.group(1)), int(partes.group(2)), int(partes.group(3)))
    except ValueError:
        return False
    return True


def motivo_do_sistema(erro: OSError) -> str:
    """Motivo do erro do sistema, em português para os casos comuns."""
    if isinstance(erro, IsADirectoryError):
        return "é uma pasta"
    if isinstance(erro, NotADirectoryError):
        return "não é uma pasta"
    if isinstance(erro, PermissionError):
        return "sem permissão"
    return erro.strerror or type(erro).__name__


def motivo_do_git(feito: subprocess.CompletedProcess, subcomando: str, programa: str = "git") -> str:
    """A primeira linha com `FALHA` do stderr e do stdout, como a do pre-commit que confere as invariantes; sem ela, a
    primeira linha não vazia; sem nenhuma, `<programa> <subcomando> saiu com <código>`."""
    linhas = [
        linha.strip()
        for saida in (feito.stderr, feito.stdout)
        for linha in (saida or b"").decode("utf-8", errors="replace").splitlines()
        if linha.strip()
    ]
    com_falha = [linha for linha in linhas if "FALHA" in linha]
    if com_falha or linhas:
        return (com_falha or linhas)[0]
    return f"{programa} {subcomando} saiu com {feito.returncode}"


def juntar(itens, conjuncao: str = "e") -> str:
    """`a`, `a e b` ou `a, b e c`; sem itens, texto vazio."""
    itens = list(itens)
    if len(itens) <= 1:
        return "".join(itens)
    return ", ".join(itens[:-1]) + f" {conjuncao} " + itens[-1]


def caminho_normalizado(caminho: str) -> bool:
    """Caminho relativo em posix igual ao próprio `normpath`: sem `./`, `..`, `//`, barra no fim nem no começo."""
    if not caminho or caminho.startswith("/") or caminho != posixpath.normpath(caminho):
        return False
    return all(segmento not in (".", "..") for segmento in caminho.split("/"))


def padrao_que_casa(relativo: str, padroes: tuple[str, ...]) -> str | None:
    """O primeiro padrão de caminho que casa com o caminho relativo à raiz, ou None. O padrão terminado em `/**` casa
    com a pasta e com tudo dentro dela; os outros, por `casa_padrao`. A pasta que só contém o alvo não casa."""
    segmentos = relativo.split("/")
    for padrao in padroes:
        if padrao.endswith("/**"):
            base = padrao[: -len("/**")].split("/")
            if len(segmentos) >= len(base) and casa_padrao("/".join(base), "/".join(segmentos[: len(base)])):
                return padrao
        elif casa_padrao(padrao, relativo):
            return padrao
    return None


def casa_padrao(padrao: str, caminho: str) -> bool:
    """O caminho casa com o padrão segmento a segmento: `*`, `?` e `[...]` nunca atravessam `/`; maiúsculas contam."""
    segmentos_do_padrao = padrao.split("/")
    segmentos = caminho.split("/")
    if len(segmentos_do_padrao) != len(segmentos):
        return False
    return all(fnmatch.fnmatchcase(segmento, parte) for parte, segmento in zip(segmentos_do_padrao, segmentos))


def mesma_arvore(a: Path, b: Path) -> bool:
    """Mesmo dispositivo e mesmo inode; erro do sistema é False."""
    try:
        estado_a, estado_b = os.stat(a), os.stat(b)
    except OSError:
        return False
    return (estado_a.st_dev, estado_a.st_ino) == (estado_b.st_dev, estado_b.st_ino)


def diretorio_do_git(arvore: Path) -> Path | None:
    """O diretório do git da árvore, pelos arquivos, sem rodar o git: a pasta `.git`, ou o `<x>` do arquivo `.git` com
    `gitdir: <x>`, relativo à árvore quando não é absoluto; fora disso, None."""
    git = arvore / ".git"
    if git.is_dir():
        return git
    try:
        linha = ler_texto(git).strip()
    except (OSError, UnicodeDecodeError):
        return None
    if not linha.startswith("gitdir:"):
        return None
    gitdir = Path(linha[len("gitdir:"):].strip())
    return gitdir if gitdir.is_absolute() else arvore / gitdir


def diretorio_comum(arvore: Path) -> Path | None:
    """O diretório comum do git da árvore, pelos arquivos, sem rodar o git: a pasta `.git` é ela mesma; o arquivo
    `.git` com `gitdir: <x>` dá o `<x>`, relativo à árvore quando não é absoluto, ou, com `<x>/commondir`, o caminho
    que ele dá, relativo ao `<x>`; fora disso, None."""
    gitdir = diretorio_do_git(arvore)
    if gitdir is None or (arvore / ".git").is_dir():
        return gitdir
    try:
        commondir = Path(ler_texto(gitdir / "commondir").strip())
    except (OSError, UnicodeDecodeError):
        return gitdir
    return Path(os.path.normpath(commondir if commondir.is_absolute() else gitdir / commondir))
