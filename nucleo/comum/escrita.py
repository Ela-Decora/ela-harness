"""Alvos de escrita de um comando de Bash, para a guarda (spec 3b, §6.2). São os caminhos que ele grava, o diretório
dos subcomandos de git que escrevem, o código passado por `-c` ou `-e`, o commit sem verificação, os comandos de git
que apagam trabalho ou reescrevem o remoto (spec 5c, §11) e as palavras passadas ao `harness.py` (spec 6c, §6.4).

Sem perfil: quem decide se um alvo é protegido é a guarda. A leitura é aproximada, como a de um leitor humano do
comando: script executado por arquivo, `eval`, `xargs`, `find -exec`, substituição de comando e variável que o
ambiente não tem ficam de fora, e o Stop cobre o que passar.
"""
from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

_PONTUACAO = "();<>|&\n"
_SEPARADORES = frozenset(";&|()\n")
_ANTES_DE_PALAVRA = frozenset(" \t\r\n;&|()<>")
_RE_RESERVA = re.compile(r"\n|[;&|()<>]+|[^\s;&|()<>]+")
_RE_VARIAVEL = re.compile(r"\$\{?(\w+)\}?")
_RE_ATRIBUICAO = re.compile(r"[A-Za-z_]\w*=")
_RE_PYTHON = re.compile(r"python(3(\.\d+)?)?")

_REDIRECIONAMENTOS_DE_ESCRITA = frozenset({">", ">>", ">|", "&>", "&>>"})
_REDIRECIONAMENTOS_DE_LEITURA = frozenset({"<", "<<<", "<&", "<>"})
_PALAVRAS_RESERVADAS = frozenset({"!", "{", "}", "if", "then", "else", "elif", "do", "while", "until", "time"})

_TODOS_SAO_ALVO = frozenset({"tee", "rm", "rmdir", "mkdir", "touch", "mv"})
_ULTIMO_E_ALVO = frozenset({"cp", "ln", "install", "rsync"})
_INTERPRETADORES = frozenset({"node", "ruby"})
_SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ksh"})
_SHELL_OPCAO_COM_VALOR = frozenset({"-o", "+o", "-O", "+O", "--rcfile", "--init-file"})
_NIVEIS_DE_SHELL = 2
_GIT_QUE_ESCREVE = frozenset({
    "checkout", "restore", "reset", "stash", "clean", "apply", "merge", "rebase", "pull", "cherry-pick", "am", "rm",
    "mv",
})
_GIT_SO_DIRETORIO = frozenset({"add", "commit"})
_GIT_OPCAO_COM_VALOR = frozenset({"-c", "--git-dir", "--work-tree", "--namespace"})

RESET_HARD = "reset --hard"
CLEAN_FORCADO = "clean -f"
STASH_SEM_CAMINHO = "stash"
STASH_DROP = "stash drop"
STASH_CLEAR = "stash clear"
PUSH_FORCADO = "push forçado"


@dataclass(frozen=True)
class Alvos:
    """O que um comando de Bash grava.

    `caminhos`: absolutos, normalizados por `os.path.normpath`, sem resolver links. `diretorios_git`: onde roda um
    subcomando de git que escreve, `add` e `commit` incluídos. `codigos`: o código de `-c` ou `-e`.
    `sem_verificacao`: `git commit` com `--no-verify` ou `-n`. `destrutivos`: as constantes de `git_destrutivo`
    achadas, sem repetição, na ordem. `harness`: as palavras depois da primeira que termina em `harness.py`, uma
    tupla por comando simples, na ordem. `restauracoes`: os `caminhos` que só um `git restore` sem `--source`, ou um
    `git checkout` com `--` e só opções antes dele, grava, de volta ao índice ou ao HEAD. `push_sem_verificacao`:
    `git push` com `--no-verify`, ou um começo dele, antes do `--`. `restauracoes_no_disco`: as `restauracoes` que
    voltam o arquivo no disco: as do `git checkout --` e as do `git restore` com `-W` ou um começo de `--worktree`, ou
    sem `-S` e sem um começo de `--staged`.
    """

    caminhos: tuple[Path, ...] = ()
    diretorios_git: tuple[Path, ...] = ()
    codigos: tuple[str, ...] = ()
    sem_verificacao: bool = False
    destrutivos: tuple[str, ...] = ()
    harness: tuple[tuple[str, ...], ...] = ()
    restauracoes: tuple[Path, ...] = ()
    push_sem_verificacao: bool = False
    restauracoes_no_disco: tuple[Path, ...] = ()


def tokens(comando: str) -> list[str]:
    """Os tokens do comando, com os operadores (`;`, `&&`, `|`, `>`, `>>`, quebra de linha...) como tokens próprios.

    Pelo `shlex`, com o `#` como letra qualquer (os comentários saem antes, sem engolir a quebra de linha); com aspas
    sem par, pela reserva por expressão regular, que tira as aspas das pontas de cada token.
    """
    leitor = shlex.shlex(comando, posix=True, punctuation_chars=_PONTUACAO)
    leitor.whitespace = " \t\r"
    leitor.whitespace_split = True
    leitor.commenters = ""
    try:
        return list(leitor)
    except ValueError:
        return [token.strip("'\"") for token in _RE_RESERVA.findall(comando)]


def _separador(token: str) -> bool:
    return token != "" and all(letra in _SEPARADORES for letra in token)


def _quebra(token: str) -> bool:
    return _separador(token) and "\n" in token


def _sem_comentarios(comando: str) -> str:
    """O comando sem os comentários: de um `#` no começo de palavra, fora de aspas e sem barra antes, até a quebra de
    linha, que fica. Com aspas sem par, o comando como veio."""
    saida: list[str] = []
    aspa = ""
    posicao = 0
    while posicao < len(comando):
        letra = comando[posicao]
        if aspa == "'":
            aspa = "" if letra == "'" else aspa
        elif letra == "\\":
            saida.append(comando[posicao:posicao + 2])
            posicao += 2
            continue
        elif aspa == '"':
            aspa = "" if letra == '"' else aspa
        elif letra in "'\"":
            aspa = letra
        elif letra == "#" and (posicao == 0 or comando[posicao - 1] in _ANTES_DE_PALAVRA):
            fim = comando.find("\n", posicao)
            posicao = len(comando) if fim < 0 else fim
            continue
        saida.append(letra)
        posicao += 1
    return comando if aspa else "".join(saida)


def _depois_do_delimitador(lista: list[str], posicao: int, delimitador: str) -> int:
    """A posição logo depois da linha que é só o delimitador; o fim da lista se ela não vier."""
    while posicao < len(lista):
        fim = posicao
        while fim < len(lista) and not _quebra(lista[fim]):
            fim += 1
        linha = lista[posicao:fim]
        posicao = fim + 1
        if linha == [delimitador]:
            break
    return min(posicao, len(lista))


def _sem_heredocs(lista: list[str]) -> list[str]:
    """Tira o operador `<<` (ou `<<-`), o delimitador e o corpo de cada heredoc: o corpo é texto, não comando."""
    saida: list[str] = []
    pendentes: list[str] = []
    posicao = 0
    while posicao < len(lista):
        token = lista[posicao]
        posicao += 1
        if token in ("<<", "<<-") and posicao < len(lista):
            delimitador = lista[posicao]
            posicao += 1
            if token == "<<" and delimitador == "-" and posicao < len(lista):
                delimitador = lista[posicao]
                posicao += 1
            elif token == "<<" and delimitador.startswith("-"):
                # O shlex separa `<<-EOF` em `<<` e `-EOF`.
                delimitador = delimitador[1:]
            pendentes.append(delimitador)
            continue
        saida.append(token)
        if pendentes and _quebra(token):
            for delimitador in pendentes:
                posicao = _depois_do_delimitador(lista, posicao, delimitador)
            pendentes = []
    return saida


def _comandos(lista: list[str]) -> list[list[str]]:
    """Os comandos simples, separados pelos tokens feitos só de `;`, `&`, `|`, `(`, `)` e quebra de linha."""
    comandos: list[list[str]] = [[]]
    for token in lista:
        if _separador(token):
            comandos.append([])
        else:
            comandos[-1].append(token)
    return [comando for comando in comandos if comando]


def _expandir(token: str, ambiente: Mapping[str, str]) -> str:
    trocado = _RE_VARIAVEL.sub(lambda achado: ambiente.get(achado.group(1), achado.group(0)), token)
    return os.path.expanduser(trocado)


def _resolver(token: str, diretorio: Path | None) -> Path | None:
    """O caminho absoluto e normalizado do token; None se for vazio ou relativo a um diretório desconhecido."""
    if not token:
        return None
    if os.path.isabs(token):
        return Path(os.path.normpath(token))
    if diretorio is None:
        return None
    return Path(os.path.normpath(os.path.join(str(diretorio), token)))


def _nao_opcoes(argumentos: list[str]) -> list[str]:
    """Os argumentos que não começam com `-`; depois de `--`, todos."""
    saida: list[str] = []
    depois = False
    for argumento in argumentos:
        if depois or not argumento.startswith("-"):
            saida.append(argumento)
        elif argumento == "--":
            depois = True
    return saida


class _Coletor:
    def __init__(self) -> None:
        self.caminhos: list[Path] = []
        self.diretorios_git: list[Path] = []
        self.codigos: list[str] = []
        self.sem_verificacao = False
        self.destrutivos: list[str] = []
        self.harness: list[tuple[str, ...]] = []
        self.restaurados: list[Path] = []
        self.no_disco: list[Path] = []
        self.escritos: list[Path] = []
        self.push_sem_verificacao = False

    def caminho(self, token: str, diretorio: Path | None, restauracao: bool = False, no_disco: bool = False) -> None:
        alvo = _resolver(token, diretorio)
        if alvo is None:
            return
        if alvo not in self.caminhos:
            self.caminhos.append(alvo)
        (self.restaurados if restauracao else self.escritos).append(alvo)
        if restauracao and no_disco:
            self.no_disco.append(alvo)

    def diretorio_git(self, diretorio: Path | None) -> None:
        if diretorio is not None and diretorio not in self.diretorios_git:
            self.diretorios_git.append(diretorio)

    def destrutivo(self, constante: str | None) -> None:
        if constante is not None and constante not in self.destrutivos:
            self.destrutivos.append(constante)

    def alvos(self) -> Alvos:
        restauracoes = tuple(dict.fromkeys(alvo for alvo in self.restaurados if alvo not in self.escritos))
        return Alvos(tuple(self.caminhos), tuple(self.diretorios_git), tuple(self.codigos), self.sem_verificacao,
                     tuple(self.destrutivos), tuple(self.harness), restauracoes, self.push_sem_verificacao,
                     tuple(alvo for alvo in restauracoes if alvo in self.no_disco))


def _sem_redirecionamentos(palavras: list[str], diretorio: Path | None, coletor: _Coletor) -> list[str]:
    """Tira os redirecionamentos e os seus operandos; o arquivo de um redirecionamento de escrita é alvo."""
    argumentos: list[str] = []
    posicao = 0
    while posicao < len(palavras):
        token = palavras[posicao]
        posicao += 1
        escrita = token in _REDIRECIONAMENTOS_DE_ESCRITA or token == ">&"
        if not escrita and token not in _REDIRECIONAMENTOS_DE_LEITURA:
            argumentos.append(token)
            continue
        if escrita and argumentos and argumentos[-1].isdigit():
            argumentos.pop()
        if posicao >= len(palavras):
            break
        operando = palavras[posicao]
        posicao += 1
        if not escrita or operando == "/dev/null":
            continue
        if token == ">&" and (operando.isdigit() or operando == "-"):
            continue
        coletor.caminho(operando, diretorio)
    return argumentos


def _cd(argumentos: list[str], diretorio: Path | None) -> Path | None:
    if len(argumentos) != 1 or argumentos[0] == "-":
        return None
    return _resolver(argumentos[0], diretorio)


def _truncate(argumentos: list[str]) -> list[str]:
    alvos: list[str] = []
    posicao = 0
    while posicao < len(argumentos):
        argumento = argumentos[posicao]
        posicao += 1
        if argumento in ("-s", "-r", "--size", "--reference"):
            posicao += 1
        elif not argumento.startswith("-"):
            alvos.append(argumento)
    return alvos


def _sed(argumentos: list[str]) -> list[str]:
    no_lugar = False
    tem_script = False
    arquivos: list[str] = []
    depois = False
    posicao = 0
    while posicao < len(argumentos):
        argumento = argumentos[posicao]
        posicao += 1
        if depois or not argumento.startswith("-"):
            arquivos.append(argumento)
        elif argumento == "--":
            depois = True
        elif argumento.startswith("--"):
            if argumento == "--in-place" or argumento.startswith("--in-place="):
                no_lugar = True
            elif argumento in ("--expression", "--file"):
                tem_script = True
                posicao += 1
            elif argumento.startswith(("--expression=", "--file=")):
                tem_script = True
        else:
            grupo = argumento[1:]
            for indice, letra in enumerate(grupo):
                ultima = indice == len(grupo) - 1
                if letra == "i":
                    no_lugar = True
                    if ultima and posicao < len(argumentos) and argumentos[posicao] == "":
                        # `sed -i ''` do macOS: o sufixo vazio vem como token próprio.
                        posicao += 1
                    break
                if letra in "ef":
                    tem_script = True
                    if ultima:
                        posicao += 1
                    break
    if not no_lugar:
        return []
    return arquivos if tem_script else arquivos[1:]


def _perl(argumentos: list[str], coletor: _Coletor) -> list[str]:
    no_lugar = False
    tem_codigo = False
    arquivos: list[str] = []
    depois = False
    posicao = 0
    while posicao < len(argumentos):
        argumento = argumentos[posicao]
        posicao += 1
        if depois or not argumento.startswith("-"):
            arquivos.append(argumento)
        elif argumento == "--":
            depois = True
        elif not argumento.startswith("--"):
            grupo = argumento[1:]
            for indice, letra in enumerate(grupo):
                if letra == "i":
                    no_lugar = True
                    break
                if letra in "eE":
                    tem_codigo = True
                    resto = grupo[indice + 1:]
                    if resto:
                        coletor.codigos.append(resto)
                    elif posicao < len(argumentos):
                        coletor.codigos.append(argumentos[posicao])
                        posicao += 1
                    break
    if not no_lugar:
        return []
    return arquivos if tem_codigo else arquivos[1:]


def _codigos(argumentos: list[str], coletor: _Coletor) -> None:
    for posicao, argumento in enumerate(argumentos[:-1]):
        if argumento in ("-c", "-e"):
            coletor.codigos.append(argumentos[posicao + 1])


def _commit_sem_verificacao(argumentos: list[str]) -> bool:
    """`--no-verify`, ou um grupo de opções curtas em que `n` vem antes de qualquer letra de `mFCct`."""
    posicao = 0
    while posicao < len(argumentos):
        argumento = argumentos[posicao]
        posicao += 1
        if argumento == "--":
            break
        if argumento == "--no-verify":
            return True
        if not argumento.startswith("-") or argumento.startswith("--"):
            continue
        grupo = argumento[1:]
        for indice, letra in enumerate(grupo):
            if letra == "n":
                return True
            if letra in "mFCct":
                if indice == len(grupo) - 1:
                    # O valor vem no token seguinte, que pode começar com `-`.
                    posicao += 1
                break
    return False


def _abrevia(argumento: str, opcao: str, letras: int = 3) -> bool:
    """Se o argumento, sem o `=valor`, é a opção longa ou um começo dela com `letras` letras ou mais, como o git
    aceita."""
    nome = argumento.split("=", 1)[0]
    return len(nome) >= 2 + letras and nome.startswith("--") and opcao.startswith(nome)


def _letras_curtas(argumentos: list[str], com_valor: str, longas_com_valor: tuple[str, ...] = ()) -> set[str]:
    """As letras dos grupos de opções curtas, como `-xdf`. Uma letra de `com_valor` termina o grupo: o valor é o resto
    do grupo ou, com a letra no fim, o argumento seguinte, que não conta; o mesmo vale para o argumento depois de uma
    das `longas_com_valor`, ou de um começo dela, sem `=`."""
    letras = set()
    posicao = 0
    while posicao < len(argumentos):
        argumento = argumentos[posicao]
        posicao += 1
        if "=" not in argumento and any(_abrevia(argumento, longa) for longa in longas_com_valor):
            posicao += 1
        elif argumento.startswith("-") and not argumento.startswith("--"):
            for indice, letra in enumerate(argumento[1:], 1):
                letras.add(letra)
                if letra in com_valor:
                    if indice == len(argumento) - 1:
                        posicao += 1
                    break
    return letras


def _stash_com_caminho(argumentos: list[str]) -> bool:
    """Se o `stash push` tem caminho: um argumento que não é opção, fora o valor de `--message` (ou de um começo dela)
    ou de um grupo curto que termina em `m`, como `-m` ou `-um`, ou qualquer coisa depois de `--`."""
    posicao = 0
    while posicao < len(argumentos):
        argumento = argumentos[posicao]
        posicao += 1
        if argumento == "--":
            return posicao < len(argumentos)
        grupo = argumento[1:] if argumento.startswith("-") and not argumento.startswith("--") else ""
        if ("=" not in argumento and _abrevia(argumento, "--message")) or (grupo and grupo.find("m") == len(grupo) - 1):
            posicao += 1
        elif not argumento.startswith("-"):
            return True
    return False


def _stash(argumentos: list[str]) -> str | None:
    """O primeiro argumento que não é opção decide; sem argumento, ou com uma opção primeiro, vale como `push`."""
    if not argumentos or argumentos[0].startswith("-"):
        acao, resto = "push", argumentos
    else:
        acao, resto = argumentos[0], argumentos[1:]
    if acao == "push":
        return None if _stash_com_caminho(resto) else STASH_SEM_CAMINHO
    return {"save": STASH_SEM_CAMINHO, "drop": STASH_DROP, "clear": STASH_CLEAR}.get(acao)


def git_destrutivo(subcomando: str, argumentos: list[str]) -> str | None:
    """A constante do git que apaga trabalho ou reescreve o remoto (spec 5c, §11.1), ou None.

    Vale o que vem antes do `--`: o `reset` com `--hard`; o `clean` com `--force` ou um grupo curto com `f`, menos com
    `--dry-run` ou um grupo curto com `n`; o `stash` sem caminho, o `save`, o `drop` e o `clear`; o `push` com
    `--force`, `--force-with-lease`, com ou sem `=`, um grupo curto com `f` ou um argumento que começa por `+`. O valor
    do `-e` e do `--exclude` no `clean` e o do `-o` no `push` não contam como opção. Cada opção longa vale também por
    um começo dela com 3 letras ou mais, como `--har`, que o git aceita.
    """
    if subcomando == "stash":
        return _stash(argumentos)
    antes = argumentos[:argumentos.index("--")] if "--" in argumentos else argumentos
    if subcomando == "reset":
        return RESET_HARD if any(_abrevia(argumento, "--hard") for argumento in antes) else None
    if subcomando == "clean":
        letras = _letras_curtas(antes, "e", ("--exclude",))
        if "n" in letras or any(_abrevia(argumento, "--dry-run") for argumento in antes):
            return None
        return CLEAN_FORCADO if "f" in letras or any(_abrevia(argumento, "--force") for argumento in antes) else None
    if subcomando == "push":
        forcado = "f" in _letras_curtas(antes, "o") or any(
            _abrevia(argumento, "--force-with-lease") or argumento.startswith("+") for argumento in antes)
        return PUSH_FORCADO if forcado else None
    return None


def _restauracao(subcomando: str, argumentos: list[str]) -> bool:
    """O `restore` sem `-s` nem `--source`, em qualquer forma, antes do `--`, ou o `checkout` com `--` e só opções
    antes dele: a volta do arquivo ao índice ou ao HEAD."""
    antes = argumentos[:argumentos.index("--")] if "--" in argumentos else argumentos
    if subcomando == "restore":
        # O `--so` já é único entre as opções do `restore`, e o git o aceita como `--source`.
        return "s" not in _letras_curtas(antes, "s", ("--source",)) and not any(
            _abrevia(argumento, "--source", letras=2) for argumento in antes)
    return subcomando == "checkout" and "--" in argumentos and all(argumento.startswith("-") for argumento in antes)


def _no_disco(subcomando: str, argumentos: list[str]) -> bool:
    """A restauração que volta o arquivo no disco: o `checkout --`, ou o `restore` com `-W` ou um começo de
    `--worktree`, ou sem `-S` e sem um começo de `--staged`, antes do `--`."""
    if subcomando != "restore":
        return True
    antes = argumentos[:argumentos.index("--")] if "--" in argumentos else argumentos
    letras = _letras_curtas(antes, "s", ("--source",))
    if "W" in letras or any(_abrevia(argumento, "--worktree", letras=1) for argumento in antes):
        return True
    return "S" not in letras and not any(_abrevia(argumento, "--staged", letras=2) for argumento in antes)


def _git(argumentos: list[str], diretorio: Path | None, coletor: _Coletor) -> None:
    diretorio_git = diretorio
    posicao = 0
    while posicao < len(argumentos) and argumentos[posicao].startswith("-"):
        opcao = argumentos[posicao]
        posicao += 1
        if opcao == "-C" and posicao < len(argumentos):
            diretorio_git = _resolver(argumentos[posicao], diretorio_git)
            posicao += 1
        elif opcao in _GIT_OPCAO_COM_VALOR:
            posicao += 1
    if posicao >= len(argumentos):
        return
    subcomando, resto = argumentos[posicao], argumentos[posicao + 1:]
    coletor.destrutivo(git_destrutivo(subcomando, resto))
    if subcomando == "push":
        antes = resto[:resto.index("--")] if "--" in resto else resto
        if any(_abrevia(argumento, "--no-verify") for argumento in antes):
            coletor.push_sem_verificacao = True
    if subcomando in _GIT_SO_DIRETORIO:
        coletor.diretorio_git(diretorio_git)
        if subcomando == "commit" and _commit_sem_verificacao(resto):
            coletor.sem_verificacao = True
        return
    if subcomando not in _GIT_QUE_ESCREVE:
        return
    coletor.diretorio_git(diretorio_git)
    restauracao = _restauracao(subcomando, resto)
    no_disco = restauracao and _no_disco(subcomando, resto)
    depois = False
    for argumento in resto:
        if depois:
            coletor.caminho(argumento, diretorio_git, restauracao, no_disco)
        elif argumento == "--":
            depois = True
        elif not argumento.startswith("-"):
            caminho = _resolver(argumento, diretorio_git)
            if caminho is not None and os.path.lexists(caminho):
                coletor.caminho(argumento, diretorio_git, restauracao, no_disco)


def _codigo_do_shell(argumentos: list[str]) -> str | None:
    """O código de `sh -c <código>` e afins: o primeiro argumento que não é opção, quando uma opção curta tem `c`."""
    com_c = False
    posicao = 0
    while posicao < len(argumentos):
        argumento = argumentos[posicao]
        posicao += 1
        if argumento in _SHELL_OPCAO_COM_VALOR:
            posicao += 1
        elif argumento in ("-", "--"):
            return argumentos[posicao] if com_c and posicao < len(argumentos) else None
        elif len(argumento) > 1 and argumento[0] in "-+":
            com_c = com_c or (argumento[0] == "-" and argumento[1] != "-" and "c" in argumento)
        else:
            return argumento if com_c else None
    return None


def _analisar(
    palavras: list[str], diretorio: Path | None, ambiente: Mapping[str, str], coletor: _Coletor, nivel: int
) -> Path | None:
    """Junta ao coletor os alvos de um comando simples; devolve o diretório corrente dos comandos seguintes.

    `nivel` é quantos `sh -c` envolvem o comando: o código de um `sh -c` é lido como comando, num nível abaixo, até
    `_NIVEIS_DE_SHELL`, e o `cd` dele não muda o diretório de fora.
    """
    argumentos = _sem_redirecionamentos(palavras, diretorio, coletor)
    while argumentos and (argumentos[0] in _PALAVRAS_RESERVADAS or _RE_ATRIBUICAO.match(argumentos[0])):
        argumentos = argumentos[1:]
    if not argumentos:
        return diretorio
    for posicao, argumento in enumerate(argumentos):
        if argumento.endswith("harness.py"):
            coletor.harness.append(tuple(argumentos[posicao + 1:]))
            break
    nome, resto = os.path.basename(argumentos[0]), argumentos[1:]
    if nome == "cd":
        return _cd(resto, diretorio)
    if nome in _TODOS_SAO_ALVO:
        alvos = _nao_opcoes(resto)
    elif nome == "truncate":
        alvos = _truncate(resto)
    elif nome in _ULTIMO_E_ALVO:
        alvos = _nao_opcoes(resto)[-1:]
    elif nome == "dd":
        alvos = [argumento[3:] for argumento in resto if argumento.startswith("of=")]
    elif nome == "sed":
        alvos = _sed(resto)
    elif nome == "perl":
        alvos = _perl(resto, coletor)
    elif nome == "git":
        _git(resto, diretorio, coletor)
        alvos = []
    elif nome in _SHELLS:
        codigo = _codigo_do_shell(resto)
        if codigo is not None and nivel < _NIVEIS_DE_SHELL:
            _coletar(codigo, diretorio, ambiente, coletor, nivel + 1)
        alvos = []
    else:
        if _RE_PYTHON.fullmatch(nome) or nome in _INTERPRETADORES:
            _codigos(resto, coletor)
        alvos = []
    for alvo in alvos:
        coletor.caminho(alvo, diretorio)
    return diretorio


def alvos(comando: str, cwd: Path, ambiente: Mapping[str, str]) -> Alvos:
    """Os alvos de escrita do comando, com o diretório corrente começando em `cwd`.

    `$VAR` e `${VAR}` são trocados pelo valor em `ambiente`, não no do processo; variável ausente fica como está.
    `cd <dir>` muda o diretório dos comandos seguintes; `cd` sem argumento, `cd -` ou com mais de um argumento o
    deixa desconhecido, e os caminhos relativos depois dele não entram. O corpo dos heredocs e os comentários não
    são lidos; o código de `sh -c`, `bash -c` e afins é lido como comando.
    """
    coletor = _Coletor()
    _coletar(comando, Path(os.path.normpath(str(cwd))), ambiente, coletor, 0)
    return coletor.alvos()


def _coletar(comando: str, diretorio: Path | None, ambiente: Mapping[str, str], coletor: _Coletor, nivel: int) -> None:
    for comando_simples in _comandos(_sem_heredocs(tokens(_sem_comentarios(comando)))):
        palavras = [_expandir(token, ambiente) for token in comando_simples]
        diretorio = _analisar(palavras, diretorio, ambiente, coletor, nivel)
