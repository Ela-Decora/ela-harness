"""Verificações do perfil (spec 6c, §11.1 e §11.2): os mudados, a seleção pelo momento, a execução com tempo limite e a
marca da última aprovada.

Os mudados vêm do git, contra a base do bloco da lane ou, fora dela, contra a merge-base com o ramo principal do origin;
sem base, todo arquivo da árvore conta. Cada verificação roda pelo `sh -c`, num grupo de processos próprio, que morre
inteiro no fim, também no tempo limite e na interrupção. A marca é o resumo do HEAD, do diff e dos não rastreados,
gravado no diretório do git da lane quando o Stop aprova; marca igual dispensa rodar de novo.
"""
from __future__ import annotations

import contextlib
import hashlib
import os
import re
import signal
import subprocess
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import bloco
import comum
import invariantes
import perfil_desenvolvimento
from bloco import LaneViva
from perfil_desenvolvimento import Verificacao

STOP, FINALIZAR = perfil_desenvolvimento.MOMENTOS
TETO_DO_STOP = 840
LINHAS_DA_SAIDA = 30
NO_CI = "GITHUB_ACTIONS"
_FALTA_DO_DASH = re.compile(r"(?:.*: )?\d+: ([^\s:]+): not found")
_FALTA_DO_BASH = re.compile(r"(?:.*: )?([^\s:]+): command not found")
ARQUIVO_DA_MARCA = "harness-verificado"

OK = "ok"
FALHOU = "falhou"
PULADA = "pulada"
SEM_TEMPO = "sem tempo"

AJUDA = """\
Roda as verificações do perfil (`[[desenvolvimento.verificacoes]]`) na árvore atual, a lane ou a árvore principal, para
um dos dois momentos do `--momento`:

- `stop`: as que têm `stop` em `momentos` e um padrão de `caminhos` que casa com um arquivo mudado; com `caminhos`
  vazio, basta qualquer mudado. Sem mudado, nenhuma roda.
- `finalizar`: todas as que têm `finalizar` em `momentos`, mudado ou não.

Mudados são os arquivos do `git diff --name-only <base>...HEAD` e os do `git status`, sem commit e não rastreados. Numa
lane reconhecida pelos arquivos, a base é o `base` do `estado.md` do bloco, se o commit existe; fora de lane, a
merge-base do HEAD com o ramo principal do origin. Sem HEAD ou sem essa base, todo arquivo da árvore conta: os
rastreados e os não rastreados, sem os ignorados.

Antes de rodar, cada caminho de `requer` precisa existir na raiz. Faltando um, o `stop` dá
`<nome>: pulada; falta <caminho>`, sem falha, e o `finalizar` dá `<nome>: falta <caminho>`, com falha.

Cada verificação roda por `sh -c "<comando>"`, na raiz da árvore, com o ambiente herdado, a entrada fechada e a saída
de erro junto da saída, num grupo de processos próprio. Ela acaba quando o `sh` sai, sem esperar o processo em segundo
plano que segure a saída. No fim, pela saída do `sh`, pelo `tempo_limite`, pelo Ctrl-C, pelo SIGTERM ou pelo SIGHUP, o
grupo inteiro morre, os processos em segundo plano inclusive. As linhas:

- `<nome>: ok (<s> s)`, com o tempo numa casa decimal;
- `<nome>: falhou (saída <c>)`, seguida das últimas 30 linhas da saída, com recuo de 2;
- `<nome>: passou de <t> s`, que conta como falha, seguida das últimas 30 linhas da saída;
- sem nenhuma a rodar: `nada a verificar`.

Com `GITHUB_ACTIONS=true`, a falha, a que passou do tempo e a de `requer` ganham mais duas coisas:

- logo abaixo da linha da falha, uma linha
  `<nome>: a saída diz que falta o comando <cmd>; declare a instalação em [desenvolvimento.ci] instalar`
  para cada comando que a saída inteira, não só as 30 linhas, diz que falta, pelas linhas
  `sh: <n>: <cmd>: not found` ou `<cmd>: command not found`, sem repetir e na ordem;
- depois das 30 linhas, a anotação `::error title=harness: <nome> falhou::<primeira linha>`, com a primeira linha da
  falta ou, sem ela, a linha da falha.

O comando sai com 0 sem falha e com 1 com alguma. A pulada não é falha.

Numa lane, o `--momento stop` sem falha grava a marca da árvore, o resumo do HEAD, do `git diff HEAD --binary`, sem o
diff externo nem o textconv da configuração do usuário, e da lista e do conteúdo dos não rastreados, em
`harness-verificado`, no diretório do git da lane. O Stop da lane compara a marca antes de rodar: igual à gravada,
nada roda. O `finalizar` e a árvore principal não gravam marca.

No Stop, as verificações somam até 840 s, abaixo do tempo limite do hook: cada uma roda com o menor entre o
`tempo_limite` dela e o que resta, e a que não cabe, por não começar ou por ser interrompida no teto, dá
`<nome>: sem tempo no Stop; rode harness.py verificar --momento stop`, sem falha e sem gravar a marca. Pelo terminal,
o `verificar` não tem esse teto.
"""


@dataclass(frozen=True)
class Execucao:
    """Uma verificação rodada ou pulada: o nome, o estado e as linhas, com a do estado primeiro."""

    nome: str
    estado: str
    linhas: tuple[str, ...]


@dataclass(frozen=True)
class Relatorio:
    """As execuções de um `verificar`, na ordem do perfil."""

    execucoes: tuple[Execucao, ...]

    @property
    def linhas(self) -> tuple[str, ...]:
        """Todas as linhas, ou `nada a verificar` sem execução."""
        if not self.execucoes:
            return ("nada a verificar",)
        return tuple(linha for execucao in self.execucoes for linha in execucao.linhas)

    @property
    def falhou(self) -> bool:
        return any(execucao.estado == FALHOU for execucao in self.execucoes)

    @property
    def cortado(self) -> bool:
        """Alguma verificação ficou sem tempo no Stop."""
        return any(execucao.estado == SEM_TEMPO for execucao in self.execucoes)

    @property
    def resumos(self) -> tuple[str, ...]:
        """A primeira linha de cada falha."""
        return tuple(execucao.linhas[0] for execucao in self.execucoes if execucao.estado == FALHOU)

    @property
    def detalhes(self) -> tuple[str, ...]:
        """Todas as linhas de cada falha."""
        return tuple(linha for execucao in self.execucoes if execucao.estado == FALHOU for linha in execucao.linhas)

    @property
    def avisos(self) -> tuple[str, ...]:
        """A primeira linha de cada pulada e de cada sem tempo."""
        return tuple(execucao.linhas[0] for execucao in self.execucoes if execucao.estado in (PULADA, SEM_TEMPO))


def base_da_arvore(raiz: Path, perfil, lane: LaneViva | None, executar=subprocess.run) -> str | None:
    """A base dos mudados: numa lane, o `base` do bloco, se o commit existe; fora dela, a merge-base do HEAD com o ramo
    principal do origin. Sem HEAD ou sem essa base, None."""
    if lane is not None:
        feito = bloco.git(raiz, ["cat-file", "-e", f"{lane.bloco.base}^{{commit}}"], executar)
        return lane.bloco.base if feito.returncode == 0 else None
    feito = bloco.git(raiz, ["merge-base", f"refs/remotes/origin/{perfil.ramo_principal}", "HEAD"], executar)
    if feito.returncode != 0:
        return None
    return feito.stdout.decode("utf-8", "replace").strip() or None


def _nomes(saida: bytes) -> list[str]:
    return [nome for nome in saida.decode("utf-8", "replace").split("\0") if nome]


def mudados(raiz: Path, base: str | None, executar=subprocess.run) -> list[str]:
    """Os caminhos mudados, relativos à raiz, sem repetir: com base, os do diff contra ela e os do status; sem base,
    ou com esse diff em erro, todos os rastreados e os não rastreados, sem os ignorados."""
    if base is not None:
        diff = bloco.git(raiz, ["diff", "--name-only", "-z", f"{base}...HEAD"], executar)
        if diff.returncode == 0:
            status = bloco.git(raiz, ["status", "--porcelain=v1", "-z", "--untracked-files=all"], executar)
            caminhos = _nomes(diff.stdout) + [caminho for _, caminho in invariantes.ler_status(status.stdout)]
            return list(dict.fromkeys(caminhos))
    feito = bloco.git(raiz, ["ls-files", "-z", "--cached", "--others", "--exclude-standard"], executar)
    if feito.returncode != 0:
        raise bloco.Recusa("fora de um repositório git")
    return list(dict.fromkeys(_nomes(feito.stdout)))


def selecionar(perfil, momento: str, mudados_: list[str]) -> list[Verificacao]:
    """As verificações do momento, na ordem do perfil: no `finalizar`, todas as dele; no `stop`, as que têm um padrão
    de `caminhos` que casa com um mudado, ou `caminhos` vazio e algum mudado."""
    escolhidas = []
    for verificacao in perfil.verificacoes:
        if momento not in verificacao.momentos:
            continue
        if momento == FINALIZAR or (mudados_ and (not verificacao.caminhos or any(
                comum.padrao_que_casa(caminho, verificacao.caminhos) for caminho in mudados_))):
            escolhidas.append(verificacao)
    return escolhidas


def _terminar(numero: int, _quadro) -> None:
    raise SystemExit(128 + numero)


def rodar_comando(comando: str, raiz: Path, tempo: float,
                  ambiente: Mapping[str, str] | None = None) -> tuple[int | None, str]:
    """Roda o comando por `sh -c` na raiz, com a entrada fechada, a saída de erro na saída, num arquivo temporário, e
    um grupo de processos próprio. Devolve o código de saída do `sh` e a saída; no tempo esgotado, None e o que saiu.

    A volta não espera um processo em segundo plano que segure a saída. No fim, pela saída do `sh`, pelo tempo, pelo
    Ctrl-C, pelo SIGTERM ou pelo SIGHUP, que viram `SystemExit` enquanto o comando roda, o grupo inteiro morre.
    O `ambiente`, se dado, é o ambiente do comando; sem ele, vale o herdado."""
    anteriores = {}
    with contextlib.suppress(ValueError):  # fora da linha principal, os sinais ficam como estão
        for sinal in (signal.SIGTERM, signal.SIGHUP):
            anteriores[sinal] = signal.signal(sinal, _terminar)
    try:
        with tempfile.TemporaryFile() as arquivo:
            processo = subprocess.Popen(
                ["sh", "-c", comando], cwd=raiz, stdin=subprocess.DEVNULL, stdout=arquivo, stderr=subprocess.STDOUT,
                start_new_session=True,
                env=None if ambiente is None else dict(ambiente),
            )
            codigo: int | None
            try:
                codigo = processo.wait(timeout=tempo)
            except subprocess.TimeoutExpired:
                codigo = None
            finally:
                with contextlib.suppress(OSError):
                    os.killpg(processo.pid, signal.SIGKILL)
                processo.wait()
            arquivo.seek(0)
            saida = arquivo.read()
    finally:
        for sinal, anterior in anteriores.items():  # None é o tratador que não veio do Python: volta o padrão
            signal.signal(sinal, signal.SIG_DFL if anterior is None else anterior)
    return codigo, saida.decode("utf-8", errors="replace")


def _segundos(valor: float) -> str:
    return f"{valor:.1f}".replace(".", ",")


def _sem_tempo(nome: str) -> Execucao:
    return Execucao(nome, SEM_TEMPO, (f"{nome}: sem tempo no Stop; rode harness.py verificar --momento {STOP}",))


def no_ci(ambiente: Mapping[str, str]) -> bool:
    """Se o ambiente é o do GitHub Actions."""
    return ambiente.get(NO_CI) == "true"


def comandos_que_faltam(saida: str) -> list[str]:
    """Os comandos que o shell diz não achar na saída inteira, sem repetir e na ordem em que aparecem."""
    achados: list[str] = []
    for linha in saida.splitlines():
        achado = _FALTA_DO_DASH.fullmatch(linha.rstrip()) or _FALTA_DO_BASH.fullmatch(linha.rstrip())
        if achado and achado.group(1) not in achados:
            achados.append(achado.group(1))
    return achados


def linhas_da_falta(nome: str, saida: str) -> tuple[str, ...]:
    """Uma linha por comando que falta na saída."""
    return tuple(
        f"{nome}: a saída diz que falta o comando {comando}; declare a instalação em [desenvolvimento.ci] instalar"
        for comando in comandos_que_faltam(saida)
    )


def _escapar(texto: str) -> str:
    return texto.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def anotacao(nome: str, primeira: str) -> str:
    """A anotação de erro do GitHub Actions; no título, o nome também escapa `:` e `,`."""
    titulo = _escapar(nome).replace(":", "%3A").replace(",", "%2C")
    return f"::error title=harness: {titulo} falhou::{_escapar(primeira)}"


def linhas_da_falha(nome: str, falha: str, saida: str, ultimas: tuple[str, ...],
                    ambiente: Mapping[str, str]) -> tuple[str, ...]:
    """As linhas de uma falha: a da falha e as últimas; no CI, com as da falta logo depois da falha e a anotação no fim."""
    if not no_ci(ambiente):
        return (falha, *ultimas)
    falta = linhas_da_falta(nome, saida)
    return (falha, *falta, *ultimas, anotacao(nome, falta[0] if falta else falha))


def _executar(verificacao: Verificacao, raiz: Path, momento: str, prazo: float | None, relogio, rodar,
              ambiente: Mapping[str, str] = os.environ) -> Execucao:
    nome = verificacao.nome
    falta = next((caminho for caminho in verificacao.requer if not (raiz / caminho).exists()), None)
    if falta is not None:
        if momento == STOP:
            return Execucao(nome, PULADA, (f"{nome}: pulada; falta {falta}",))
        return Execucao(nome, FALHOU, linhas_da_falha(nome, f"{nome}: falta {falta}", "", (), ambiente))
    inicio = relogio()
    tempo = float(verificacao.tempo_limite)
    if prazo is not None:
        resta = prazo - inicio
        if resta <= 0:
            return _sem_tempo(nome)
        tempo = min(tempo, resta)
    codigo, saida = rodar(verificacao.comando, raiz, tempo)
    fim = relogio()
    ultimas = tuple("  " + linha for linha in saida.splitlines()[-LINHAS_DA_SAIDA:])
    if codigo is None:
        if tempo < verificacao.tempo_limite:
            return _sem_tempo(nome)
        falha = f"{nome}: passou de {verificacao.tempo_limite} s"
        return Execucao(nome, FALHOU, linhas_da_falha(nome, falha, saida, ultimas, ambiente))
    if codigo != 0:
        falha = f"{nome}: falhou (saída {codigo})"
        return Execucao(nome, FALHOU, linhas_da_falha(nome, falha, saida, ultimas, ambiente))
    return Execucao(nome, OK, (f"{nome}: ok ({_segundos(fim - inicio)} s)",))


def verificar(raiz: Path, perfil, momento: str, mudados_: list[str], prazo: float | None = None,
              relogio=time.monotonic, rodar=rodar_comando,
              ambiente: Mapping[str, str] = os.environ) -> Relatorio:
    """Roda as verificações selecionadas, uma a uma. Com prazo, no relógio dado, cada uma roda com o menor entre o
    `tempo_limite` e o que resta, e a que não cabe fica sem tempo."""
    return Relatorio(tuple(
        _executar(verificacao, raiz, momento, prazo, relogio, rodar, ambiente)
        for verificacao in selecionar(perfil, momento, mudados_)
    ))


def marca(raiz: Path, executar=subprocess.run) -> str:
    """O sha256 do HEAD, do `git diff HEAD --binary`, sem o diff externo, o textconv nem a cor da configuração do
    usuário, e, em ordem, do caminho e do conteúdo de cada não rastreado; o que não se lê entra só pelo caminho."""
    head = bloco.git(raiz, ["rev-parse", "HEAD"], executar).stdout.strip()
    diff = bloco.git(
        raiz, ["diff", "HEAD", "--binary", "--no-ext-diff", "--no-textconv", "--no-color"], executar
    ).stdout
    outros = bloco.git(raiz, ["ls-files", "--others", "--exclude-standard", "-z"], executar).stdout
    resumo = hashlib.sha256(b"HEAD\0" + head + b"\0DIFF\0" + diff)
    for caminho in sorted(nome for nome in outros.split(b"\0") if nome):
        resumo.update(b"\0ARQUIVO\0" + caminho + b"\0")
        with contextlib.suppress(OSError):
            resumo.update((raiz / os.fsdecode(caminho)).read_bytes())
    return resumo.hexdigest()


def _arquivo_da_marca(raiz: Path, executar) -> Path:
    feito = bloco.git(raiz, ["rev-parse", "--absolute-git-dir"], executar)
    if feito.returncode != 0:
        raise bloco.Recusa("fora de um repositório git")
    return Path(os.fsdecode(feito.stdout.strip())) / ARQUIVO_DA_MARCA


def ler_marca(raiz: Path, executar=subprocess.run) -> str | None:
    """A marca gravada no diretório do git da árvore, ou None."""
    try:
        return _arquivo_da_marca(raiz, executar).read_text(encoding="utf-8").strip() or None
    except (OSError, UnicodeDecodeError):
        return None


def gravar_marca(raiz: Path, valor: str, executar=subprocess.run) -> None:
    """Grava a marca, com a quebra no fim, no diretório do git da árvore."""
    comum.escrever_texto(_arquivo_da_marca(raiz, executar), valor + "\n")


def no_stop(raiz: Path, perfil, lane: LaneViva, prazo: float | None, executar=subprocess.run,
            sempre: bool = False) -> Relatorio | None:
    """As verificações do `stop` numa lane. A marca é calculada antes; sem `sempre`, marca igual à gravada dá None,
    sem rodar nada. Sem falha e sem verificação cortada pelo prazo, a marca é gravada."""
    atual = marca(raiz, executar)
    if not sempre and atual == ler_marca(raiz, executar):
        return None
    relatorio = verificar(raiz, perfil, STOP, mudados(raiz, base_da_arvore(raiz, perfil, lane, executar), executar),
                          prazo)
    if not relatorio.falhou and not relatorio.cortado:
        gravar_marca(raiz, atual, executar)
    return relatorio
