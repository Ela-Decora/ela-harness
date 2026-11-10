"""Importação da passagem no repositório de código (spec 6c, §8): a tag conferida, a cópia, o relatório e o PR próprio, ou a cópia direta na montagem.

A tag `passagem/vN` vem do repositório de planejamento por um clone raso numa pasta temporária, que sai no fim. O
manifesto e os arquivos são conferidos antes de qualquer gravação; a cópia leva o manifesto com os bytes da tag e
cada arquivo no caminho que tinha no planejamento.
"""
from __future__ import annotations

import contextlib
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import bloco
import comum
import fichas
import gerador
import iniciar
import manifesto
import perfil_comum
import perfil_desenvolvimento
from bloco import LaneViva, Recusa
from manifesto import Manifesto

AJUDA = """\
Copia a passagem do repositório de planejamento para o repositório de código, conferida, e abre o PR dela; no
repositório sem commit, grava a cópia direto na árvore e faz o primeiro commit.

- Versão: `vN` escolhe a tag `passagem/vN`; sem ela, vale a maior do repositório de planejamento, pelo
  `git ls-remote --tags`. O `passagem.repositorio` do perfil em `org/nome` vira o endereço do GitHub no protocolo do
  `origin`: SSH com o `origin` em SSH, HTTPS nos outros casos, sem a credencial do `origin`; URL e caminho ficam como
  estão. A tag vem por um clone raso numa pasta temporária, que sai no fim.
- Conferência, toda antes de gravar: o manifesto no caminho `passagem.manifesto` da tag, legível; o formato entre os
  que este harness lê; a versão igual a N; cada arquivo do manifesto na tag, com o `sha256` dele; cada `ids[].arquivo`
  em `arquivos`; nenhum ID com o prefixo das fichas do código; e o `gerar` sobre a cópia da tag, que dá os textos dos
  arquivos gerados. Cada problema é uma recusa, com saída 1 e nada gravado, como as de versão:
  `nenhuma passagem/vN em <repositorio>`, `passagem/vN não existe em <repositorio>`,
  `passagem/vN já está no <ramo_principal>` e `passagem/vN é mais velha que a v<m> do <ramo_principal>`. A recusa do
  `gerar` dá uma linha `importar: gerar recusou: <motivo>` por motivo, e a passagem não chega ao ramo principal.
- Montagem, no repositório sem commit: a cópia vai para `caminhos.passagem` na árvore, e a cópia de uma montagem
  anterior sai sem ser lida; os gerados vão com ela, conferidos contra a árvore: o diferente é gravado e o órfão das
  pastas do gerador, apagado do disco e também do índice, pelo `git rm --cached`. Depois vem o primeiro commit,
  `chore(harness): instala o harness e importa a passagem/vN`, pelo pre-commit, com `git add --` explícito: o que o
  `iniciar` deixou (o lançador, o workflow, o `settings.json`, o perfil, os githooks, a CI, o `.gitignore`, o
  `CLAUDE.md` e o `README.md` do backlog), a pasta da cópia e cada gerado, só dos que existem. Antes do add, o
  `git ls-files --others --ignored` sobre esses caminhos: com algum arquivo que o git ignora, o comando para, com saída
  1 e sem commit, na linha
  `o git ignora <k> arquivos (1 arquivo, no singular) que o importar põe no commit, como <primeiro>; ajuste o .gitignore e rode harness.py importar v<N> de novo`,
  com o `<primeiro>` em ordem alfabética; só o link do núcleo, `.claude/harness/nucleo`, que o hook refaz e o
  `.gitignore` ignora de propósito, não conta. O commit recusado dá
  `git commit falhou: <motivo>; rode harness.py importar vN de novo`, com saída 1; a cópia e os gerados ficam na
  árvore, e rodar de novo refaz a montagem.
- Nos outros, o PR próprio: o `git fetch origin +refs/heads/<ramo_principal>:refs/remotes/origin/<ramo_principal>`,
  com o refspec explícito, que não depende do `remote.origin.fetch`; um worktree temporário, fora do repositório, sem
  branch local, a partir do `origin/<ramo_principal>`; a cópia e os gerados, conferidos contra o
  `origin/<ramo_principal>`, com o diferente gravado e o órfão apagado; a mesma parada dos ignorados, com a mesma
  linha, no worktree e antes do add, sem push e sem PR; o commit `docs(passagem): importa passagem/vN`, com os dois e
  o relatório no corpo, que passa pelo pre-commit; o `git push origin HEAD:refs/heads/docs/passagem-vN`; e o
  `gh pr create`, com o relatório no corpo e o `dono.github` como responsável. O worktree temporário sai no fim,
  também na falha; o de uma rodada interrompida por sinal não prende a seguinte, e a árvore em que o comando roda,
  com as branches locais dela, não muda.
- Retomada: o passo que falha dá `<passo> falhou: <motivo>; rode harness.py importar vN de novo`, com saída 1. Rodar
  de novo retoma: com a branch no origin, só abre o PR. Com um PR aberto da branch, a saída é
  `PR #<n> já aberto: <url>`, com 0. Com o PR aberto da `docs/passagem-v<m>`, de outra versão, o comando recusa antes
  do clone, com saída 1 e nada gravado, e com o de menor número quando há mais de um:
  `PR #<n> da passagem/v<m> ainda aberto: <url>; mescle-o ou feche-o antes de importar a v<N>`.
- A saída tem cinco linhas: a conferência (`passagem/vN conferida: formato <f>, <n> arquivos, <k> IDs`); as fichas
  novas, as que saíram e as que mudaram, contra a cópia do `origin/<ramo_principal>`, ou `fichas: nenhuma mudança`;
  os blocos vivos afetados, como `<ID>, na v<N> (<partes>)`, ou `nenhum bloco vivo afetado`; os gerados,
  `gerados: <m> mudaram (<caminhos>), <k> removidos (<caminhos>)`, na ordem da lista do gerador e depois os órfãos,
  sem parênteses no grupo vazio; e `PR #<n> aberto: <url>`. Uma ficha mudou quando o `sha256` do trecho dela no
  manifesto novo difere do antigo. O corpo do commit e o do PR trazem as quatro primeiras, também na retomada.
- Bloco afetado: o `passagem` do `estado.md` é a versão com que o bloco está em dia, o `<N>` da linha; o bloco nela,
  ou numa mais nova que a importada, não é afetado. Nos outros, ele é afetado quando a ficha dele, ou um ID que ela
  cita, mudou ou saiu entre o manifesto dessa versão e o novo. O manifesto da versão é o da cópia da lane, quando ela
  está nessa versão; senão, o do histórico do `<passagem>/manifesto.json` no `origin/<ramo_principal>`; sem nenhum,
  recusa com `lane <ID>: sem o manifesto da passagem/v<N>, nem na cópia da lane nem no origin/<ramo_principal>`. A
  lane sem cópia fica de fora, e a cópia ilegível de uma lane recusa com `lane <ID>: <motivo>`.
- Na montagem, as fichas saem todas como novas, e a linha dos blocos afetados e a do PR viram uma, a última:
  `primeiro commit <sha7>: harness e passagem/vN; rode harness.py iniciar --conferir e faça o push do <ramo_principal>`.
- Com a `[desenvolvimento.linear]` no perfil, a saída que deu certo ganha uma última linha,
  `linear: rode harness.py linear espelhar depois do merge do PR da passagem`; na montagem, a última é
  `linear: rode harness.py linear espelhar depois do push`. Ela vem também depois de `PR #<n> já aberto`, não entra no
  corpo do commit nem no do PR e não sai com a falha de um passo.
- A guarda pede confirmação antes do comando, que abre branch e PR no origin.
"""



FORMATOS_LIDOS = manifesto.FORMATOS_LIDOS
PREFIXO_DA_BRANCH = "docs/passagem-v"
TEMPO_LIMITE_CLONE = 120
TEMPO_LIMITE_REDE = 60
TEMPO_LIMITE_GH = 30
TEMPO_LIMITE_COMMIT = 60

_RE_TAG = re.compile(rf"refs/tags/{re.escape(manifesto.PREFIXO_TAG)}([1-9][0-9]*)")
_RE_BRANCH = re.compile(re.escape(PREFIXO_DA_BRANCH) + "([1-9][0-9]*)")
_RE_FICHA = re.compile(rf"{fichas.PREFIXO_DA_PASSAGEM}-[0-9]{{2,}}")


@dataclass(frozen=True)
class Tag:
    versao: int
    pasta: Path  # o checkout da tag, que some no fim do `buscar`
    manifesto: Manifesto
    dados: bytes  # os bytes do manifesto da tag


@dataclass(frozen=True)
class Afetado:
    lane: LaneViva
    mudaram: tuple[str, ...]
    sairam: tuple[str, ...]


@dataclass(frozen=True)
class PR:
    numero: int
    estado: str  # OPEN, CLOSED ou MERGED
    head: str  # o sha do último commit da branch no PR
    base: str
    url: str


@dataclass(frozen=True)
class Importacao:
    linhas: tuple[str, ...]  # a saída do comando, uma linha por item
    falhou: bool = False  # um passo depois da conferência falhou; o comando sai com 1


def _motivo(feito: subprocess.CompletedProcess, subcomando: str, programa: str = "git") -> str:
    """A primeira linha do stderr que começa por `fatal: `; sem ela, a do `comum.motivo_do_git`."""
    for linha in (feito.stderr or b"").decode("utf-8", errors="replace").splitlines():
        if linha.startswith("fatal: "):
            return linha.strip()
    return comum.motivo_do_git(feito, subcomando, programa)


def _rodar(argv: list[str], executar, tempo: int, cwd: Path | None = None
           ) -> tuple[subprocess.CompletedProcess | None, str | None]:
    """O comando com a saída em bytes: (o resultado, None), ou (None, o motivo) quando ele não roda ou passa do
    tempo. O código de saída fica com quem chama."""
    opcoes = {"cwd": str(cwd)} if cwd is not None else {}
    try:
        return executar(argv, capture_output=True, timeout=tempo, **opcoes), None
    except subprocess.TimeoutExpired:
        return None, f"passou de {tempo} s"
    except OSError as erro:
        return None, comum.motivo_do_sistema(erro)


def falha(argv: list[str], subcomando: str, executar, tempo: int, cwd: Path | None = None
          ) -> tuple[subprocess.CompletedProcess | None, str | None]:
    """Como o `_rodar`, com o código diferente de 0 também como motivo, pelo `_motivo` do `subcomando`."""
    feito, motivo = _rodar(argv, executar, tempo, cwd)
    if feito is not None and feito.returncode != 0:
        return feito, _motivo(feito, subcomando, argv[0])
    return feito, motivo


def url_do_repositorio(repositorio: str, origin: str | None) -> str:
    """O endereço do repositório de planejamento: a URL com esquema e o caminho absoluto ficam como estão; o `org/nome`
    vira `git@github.com:<org/nome>.git` com o `origin` em SSH e `https://github.com/<org/nome>.git` nos outros
    casos, sem a credencial do `origin`."""
    if "://" in repositorio or repositorio.startswith("/"):
        return repositorio
    if origin is not None and origin.startswith(("git@", "ssh://")):
        return f"git@github.com:{repositorio}.git"
    return f"https://github.com/{repositorio}.git"


def versoes(url: str, executar=subprocess.run) -> list[int]:
    """Os N das tags `passagem/vN` do repositório de planejamento, em ordem, pelo `git ls-remote --tags`."""
    feito, motivo = falha(["git", "ls-remote", "--tags", url, f"refs/tags/{manifesto.PREFIXO_TAG}*"], "ls-remote",
                           executar, TEMPO_LIMITE_GH)
    if motivo is not None:
        raise Recusa(f"repositório de planejamento não consultado: {motivo}")
    numeros = set()
    for linha in feito.stdout.decode("utf-8", errors="replace").splitlines():
        achado = _RE_TAG.fullmatch(linha.partition("\t")[2])
        if achado:
            numeros.add(int(achado.group(1)))
    return sorted(numeros)


def conferir(pasta: Path, versao: int, perfil) -> tuple[Manifesto, bytes]:
    """O manifesto e os bytes dele, conferidos no checkout da tag (spec 6c, §8.1); o primeiro problema dá `Recusa`.

    A ordem: o manifesto no caminho `passagem.manifesto` do perfil, em UTF-8 e legível; o formato e a versão; cada
    arquivo, na ordem, com o caminho normalizado, presente e com o `sha256`; cada `ids[].arquivo` em `arquivos`; e
    nenhum ID com o prefixo das fichas do código.
    """
    rotulo = f"{manifesto.PREFIXO_TAG}{versao}"
    caminho = perfil.passagem.manifesto
    try:
        dados = (pasta / caminho).read_bytes()
    except (FileNotFoundError, IsADirectoryError, NotADirectoryError):
        raise Recusa(f"{rotulo}: sem o manifesto {caminho}") from None
    except OSError as erro:
        raise Recusa(f"{rotulo}: manifesto ilegível: {comum.motivo_do_sistema(erro)}") from None
    try:
        m = manifesto.de_json(dados.decode("utf-8"))
    except UnicodeDecodeError:
        raise Recusa(f"{rotulo}: manifesto ilegível: fora do UTF-8") from None
    except manifesto.ManifestoInvalido as erro:
        raise Recusa(f"{rotulo}: manifesto ilegível: {erro.motivo}") from None
    if not manifesto.formato_lido(m.formato):
        raise Recusa(f"{rotulo}: {manifesto.motivo_do_formato(m.formato)}; atualize o harness")
    if m.versao != versao or isinstance(m.versao, bool):
        raise Recusa(f"{rotulo}: o manifesto diz versão {json.dumps(m.versao)}")
    for arquivo in m.arquivos:
        if not isinstance(arquivo.caminho, str) or not comum.caminho_normalizado(arquivo.caminho) \
                or arquivo.caminho == manifesto.NOME:
            raise Recusa(f"{rotulo}: manifesto ilegível: caminho inválido: {arquivo.caminho}")
        if not (pasta / arquivo.caminho).is_file():
            raise Recusa(f"{rotulo}: {arquivo.caminho} do manifesto falta na tag")
        if manifesto.sha256((pasta / arquivo.caminho).read_bytes()) != arquivo.sha256:
            raise Recusa(f"{rotulo}: {arquivo.caminho} não confere com o manifesto")
    caminhos = {arquivo.caminho for arquivo in m.arquivos}
    for id_, definicao in m.ids.items():
        if definicao.arquivo not in caminhos:
            raise Recusa(f"{rotulo}: manifesto ilegível: {id_} em {definicao.arquivo}, que não está em arquivos")
    if any(id_.split("-", 1)[0] == perfil.prefixo for id_ in m.ids):
        raise Recusa(f"{rotulo}: o manifesto tem IDs com o prefixo {perfil.prefixo} das fichas do código; troque "
                     "desenvolvimento.fichas.prefixo")
    return m, dados


@contextlib.contextmanager
def buscar(url: str, versao: int, perfil, executar=subprocess.run):
    """Clona a tag `passagem/vN` numa pasta temporária, a confere e entrega a `Tag`; a pasta sai no fim, com sucesso ou
    não."""
    pasta = Path(tempfile.mkdtemp(prefix="importar-"))
    try:
        checkout = pasta / "tag"
        _, motivo = falha(["git", "clone", "-q", "--depth", "1", "--branch", f"{manifesto.PREFIXO_TAG}{versao}",
                            "--single-branch", url, str(checkout)], "clone", executar, TEMPO_LIMITE_CLONE)
        if motivo is not None:
            raise Recusa(f"repositório de planejamento não consultado: {motivo}")
        m, dados = conferir(checkout, versao, perfil)
        yield Tag(versao, checkout, m, dados)
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def gravar_copia(tag: Tag, destino: Path) -> None:
    """A cópia da passagem em `destino`: o que havia sai, o `manifesto.json` leva os bytes da tag e cada arquivo do
    manifesto vai no caminho dele, com os mesmos bytes."""
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)
    (destino / manifesto.NOME).write_bytes(tag.dados)
    for arquivo in tag.manifesto.arquivos:
        alvo = destino / arquivo.caminho
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_bytes((tag.pasta / arquivo.caminho).read_bytes())


def leitor_da_tag(tag: Tag, pasta: str) -> Callable[[str], str | None]:
    """O `ler` do `gerador.gerar` sobre a tag, com os caminhos da cópia em `pasta`: o `<pasta>/manifesto.json` dá os
    bytes do manifesto da tag em texto, e cada `<pasta>/<arquivo>` dos arquivos do manifesto, o arquivo do checkout. O
    resto, e o que não se lê em UTF-8, dá None."""
    nome_do_manifesto = f"{pasta}/{manifesto.NOME}"
    arquivos = {f"{pasta}/{arquivo.caminho}": tag.pasta / arquivo.caminho for arquivo in tag.manifesto.arquivos}

    def ler(caminho: str) -> str | None:
        try:
            if caminho == nome_do_manifesto:
                return tag.dados.decode("utf-8")
            origem = arquivos.get(caminho)
            return None if origem is None else origem.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            return None

    return ler


def _lembrete_do_espelho(perfil, montagem: bool) -> tuple[str, ...]:
    """A última linha da saída que deu certo, com a `[desenvolvimento.linear]` no perfil: o espelho das fichas, que se
    roda depois do push, na montagem, ou do merge do PR da passagem; sem a tabela, nenhuma linha."""
    if perfil.linear is None:
        return ()
    quando = "depois do push" if montagem else "depois do merge do PR da passagem"
    return (f"linear: rode harness.py linear espelhar {quando}",)


def _contagem(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def linha_conferida(m: Manifesto) -> str:
    """`passagem/vN conferida: formato <f>, <n> arquivos, <k> IDs`."""
    return (f"{manifesto.PREFIXO_TAG}{m.versao} conferida: formato {m.formato}, "
            f"{_contagem(len(m.arquivos), 'arquivo', 'arquivos')}, {_contagem(len(m.ids), 'ID', 'IDs')}")


def _fichas_do_manifesto(m: Manifesto | None) -> dict[str, str]:
    """O `sha256` do trecho de cada FICHA do manifesto, pelo ID."""
    if m is None:
        return {}
    return {id_: d.sha256 for id_, d in m.ids.items() if _RE_FICHA.fullmatch(id_)}


def linha_dos_gerados(problemas_: list[tuple[str, str]]) -> str:
    """`gerados: <m> mudaram (<caminhos>), <k> removidos (<caminhos>)`, dos problemas do `gerador.problemas`, com os
    caminhos na ordem deles e sem parênteses no grupo vazio."""
    removidos = [caminho for problema, caminho in problemas_ if problema == gerador.ORFAO]
    mudaram = [caminho for problema, caminho in problemas_ if problema != gerador.ORFAO]
    partes = []
    for caminhos, singular, plural in ((mudaram, "mudou", "mudaram"), (removidos, "removido", "removidos")):
        parte = _contagem(len(caminhos), singular, plural)
        partes.append(f"{parte} ({', '.join(caminhos)})" if caminhos else parte)
    return "gerados: " + ", ".join(partes)


def linha_das_fichas(novo: Manifesto, antigo: Manifesto | None) -> str:
    """As FICHA novas, as que saíram e as de trecho mudado do antigo para o novo, cada lista em ordem de número; sem
    nenhuma, `fichas: nenhuma mudança`."""
    agora, antes = _fichas_do_manifesto(novo), _fichas_do_manifesto(antigo)
    partes = []
    for ids, singular, plural in (
        (set(agora) - set(antes), "nova", "novas"),
        (set(antes) - set(agora), "saiu", "saíram"),
        ({id_ for id_ in agora if id_ in antes and agora[id_] != antes[id_]}, "mudou", "mudaram"),
    ):
        if ids:
            partes.append(f"{_contagem(len(ids), singular, plural)} ({', '.join(sorted(ids, key=fichas.numero))})")
    return "fichas: " + (", ".join(partes) if partes else "nenhuma mudança")


def afetados(raiz: Path, novo: Manifesto, lanes: list[LaneViva], perfil, executar=subprocess.run) -> list[Afetado]:
    """Os blocos de lane viva afetados pelo manifesto novo (spec 6c, §3, item 29), na ordem das fichas: as FICHA e
    depois as do prefixo, cada grupo pelo número.

    O bloco em dia com a versão nova, ou com uma mais nova, não é afetado. A base é o manifesto da versão com que ele
    está em dia: o da cópia da lane, quando ela está nessa versão, ou o do `manifesto_da_versao`; sem base, `Recusa`.
    É afetado o bloco cuja ficha, ou um ID que o texto dela na lane cita, mudou ou saiu entre a base e o novo. A lane
    sem cópia fica de fora, e a `Recusa` da cópia de uma lane sai com o ID dela.
    """
    lista = []
    for lane in lanes:
        bloco_ = lane.bloco
        try:
            da_lane = fichas.ler_manifesto(lane.pasta, perfil)
            if da_lane is None or (isinstance(novo.versao, int) and bloco_.passagem >= novo.versao):
                continue
            base = da_lane if da_lane.versao == bloco_.passagem else None
            todas = fichas.da_passagem(lane.pasta, perfil, da_lane) + fichas.do_backlog(lane.pasta, perfil)
        except Recusa as erro:
            raise Recusa(f"lane {bloco_.id}: {erro.mensagem}") from None
        if base is None:
            base = manifesto_da_versao(raiz, perfil, bloco_.passagem, executar)
        if base is None:
            raise Recusa(f"lane {bloco_.id}: sem o manifesto da {manifesto.PREFIXO_TAG}{bloco_.passagem}, nem na cópia "
                         f"da lane nem no origin/{perfil.ramo_principal}")
        ficha = next((ficha for ficha in todas if ficha.id == bloco_.id), None)
        citados = fichas.ids_citados(ficha, fichas.prefixos_citaveis(base, perfil.prefixo)) if ficha else []
        conferidos = [id_ for id_ in [bloco_.id, *citados] if id_ in base.ids]
        mudaram = tuple(id_ for id_ in conferidos if id_ in novo.ids and novo.ids[id_].sha256 != base.ids[id_].sha256)
        sairam = tuple(id_ for id_ in conferidos if id_ not in novo.ids)
        if mudaram or sairam:
            lista.append(Afetado(lane, mudaram, sairam))
    return sorted(lista, key=lambda a: (a.lane.bloco.id.split("-", 1)[0] != fichas.PREFIXO_DA_PASSAGEM,
                                        fichas.numero(a.lane.bloco.id)))


def linha_dos_afetados(lista: list[Afetado]) -> str:
    """`blocos vivos afetados: <ID>, na v<N> (<partes>); ...`, com a versão com que o bloco está em dia, ou
    `nenhum bloco vivo afetado`."""
    if not lista:
        return "nenhum bloco vivo afetado"
    blocos = []
    for afetado in lista:
        partes = []
        if afetado.mudaram:
            verbo = "mudou" if len(afetado.mudaram) == 1 else "mudaram"
            partes.append(f"{verbo} {comum.juntar(afetado.mudaram)}")
        if afetado.sairam:
            verbo = "saiu" if len(afetado.sairam) == 1 else "saíram"
            partes.append(f"{verbo} {comum.juntar(afetado.sairam)}")
        bloco_ = afetado.lane.bloco
        blocos.append(f"{bloco_.id}, na v{bloco_.passagem} ({', '.join(partes)})")
    return "blocos vivos afetados: " + "; ".join(blocos)


def _git(raiz: Path, argumentos: list[str], executar, tempo: int
         ) -> tuple[subprocess.CompletedProcess | None, str | None]:
    """O `git -C <raiz>` pelo `falha`, com o primeiro argumento como subcomando."""
    return falha(["git", "-C", str(raiz), *argumentos], argumentos[0], executar, tempo)


def buscar_principal(raiz: Path, perfil, executar=subprocess.run) -> None:
    """O `git fetch` do ramo principal com o refspec explícito, que não depende do `remote.origin.fetch`; a falha
    recusa com `origin não consultado: <motivo>`."""
    ramo = perfil.ramo_principal
    _, motivo = _git(raiz, ["fetch", "-q", "origin", f"+refs/heads/{ramo}:refs/remotes/origin/{ramo}"], executar,
                     TEMPO_LIMITE_REDE)
    if motivo is not None:
        raise Recusa(f"origin não consultado: {motivo}")


def _manifesto_do_blob(raiz: Path, objeto: str, executar) -> Manifesto | None:
    """O manifesto do `git cat-file blob <objeto>`; ausente, ilegível ou com versão que não é número, None."""
    feito = bloco.git(raiz, ["cat-file", "blob", objeto], executar)
    if feito.returncode != 0:
        return None
    try:
        m = manifesto.de_json(feito.stdout.decode("utf-8"))
    except (UnicodeDecodeError, manifesto.ManifestoInvalido):
        return None
    return m if isinstance(m.versao, int) and not isinstance(m.versao, bool) else None


def manifesto_do_principal(raiz: Path, perfil, executar=subprocess.run) -> Manifesto | None:
    """O manifesto da cópia no `origin/<ramo_principal>`, sem fetch; ausente, ilegível ou com versão que não é número,
    None."""
    ref = f"refs/remotes/origin/{perfil.ramo_principal}"
    return _manifesto_do_blob(raiz, f"{ref}:{perfil.caminhos.passagem}/{manifesto.NOME}", executar)


def perfil_do_principal(raiz: Path, perfil, executar=subprocess.run):
    """O perfil do `.claude/perfil.toml` no `origin/<ramo_principal>`, sem fetch, que o modo PR usa no lugar do local,
    possivelmente atrasado. O `git ls-tree` diz se o arquivo existe: sem ele no origin, o `perfil` local; o `git` que
    falha, o arquivo ilegível ou o perfil do origin inválido recusam com `perfil do origin/<ramo>: <motivo>`. O do
    origin que muda o `ramo_principal` ou o `caminhos.passagem` também recusa, porque o fetch, o manifesto e o PR
    seguem o perfil local: o checkout precisa ser atualizado."""
    ramo = perfil.ramo_principal
    ref = f"refs/remotes/origin/{ramo}"
    listado, motivo = _git(raiz, ["ls-tree", "--name-only", ref, "--", comum.CAMINHO_PERFIL], executar,
                           bloco.TEMPO_LIMITE_GIT)
    if motivo is None and not listado.stdout.strip():
        return perfil
    if motivo is None:
        feito, motivo = _git(raiz, ["show", f"{ref}:{comum.CAMINHO_PERFIL}"], executar, bloco.TEMPO_LIMITE_GIT)
    if motivo is not None:
        raise Recusa(f"perfil do origin/{ramo}: {motivo}")
    try:
        do_origin = perfil_desenvolvimento.do_texto(feito.stdout.decode("utf-8"))
    except UnicodeDecodeError:
        raise Recusa(f"perfil do origin/{ramo}: o arquivo não está em UTF-8") from None
    except perfil_comum.PerfilInvalido as erro:
        raise Recusa(f"perfil do origin/{ramo}: {erro}") from None
    for chave, local, remoto in (("desenvolvimento.ramo_principal", ramo, do_origin.ramo_principal),
                                 ("desenvolvimento.caminhos.passagem", perfil.caminhos.passagem,
                                  do_origin.caminhos.passagem)):
        if local != remoto:
            raise Recusa(f"perfil do origin/{ramo}: muda {chave}; atualize o checkout e rode harness.py importar de "
                         "novo")
    return do_origin


def manifesto_da_versao(raiz: Path, perfil, versao: int, executar=subprocess.run) -> Manifesto | None:
    """O manifesto da versão no histórico do `<passagem>/manifesto.json` do `origin/<ramo_principal>`, sem fetch: o
    primeiro, do commit mais novo ao mais velho, com essa versão; o ilegível é pulado. Sem a ref ou sem nenhum, None."""
    caminho = f"{perfil.caminhos.passagem}/{manifesto.NOME}"
    feito = bloco.git(raiz, ["log", "--format=%H", f"refs/remotes/origin/{perfil.ramo_principal}", "--", caminho],
                      executar)
    if feito.returncode != 0:
        return None
    for sha in feito.stdout.decode("utf-8", errors="replace").split():
        m = _manifesto_do_blob(raiz, f"{sha}:{caminho}", executar)
        if m is not None and m.versao == versao:
            return m
    return None


def _gerados_no_principal(raiz: Path, perfil, textos: dict[str, str], executar) -> list[tuple[str, str]]:
    """Os problemas dos `textos` contra o `origin/<ramo_principal>`, sem fetch: os bytes pelo `git cat-file blob` e os
    arquivos das pastas do gerador pelo `git ls-tree`. O `ls-tree` que falha recusa com
    `origin não consultado: <motivo>`."""
    ref = f"refs/remotes/origin/{perfil.ramo_principal}"
    feito, motivo = _git(raiz, ["ls-tree", "-r", "-z", "--name-only", ref, "--", *gerador.PASTAS], executar,
                         bloco.TEMPO_LIMITE_GIT)
    if motivo is not None:
        raise Recusa(f"origin não consultado: {motivo}")
    presentes = [caminho for caminho in feito.stdout.decode("utf-8", errors="replace").split("\0") if caminho]

    def dados(caminho: str) -> bytes | None:
        blob = bloco.git(raiz, ["cat-file", "blob", f"{ref}:{caminho}"], executar)
        return blob.stdout if blob.returncode == 0 else None

    return gerador.problemas(textos, dados, presentes)


def _pr_aberto(raiz: Path, versao: int, executar) -> tuple[int, str] | None:
    """O número e a URL do PR aberto da `docs/passagem-v<versao>`, pelo `gh pr list`, ou None. O PR aberto da
    `docs/passagem-v<m>`, de outra versão, é recusa; o de nome que só se parece com a branch não conta."""
    feito, motivo = falha(["gh", "pr", "list", "--state", "open", "--limit", "1000", "--json",
                           "number,url,headRefName"], "pr list", executar, TEMPO_LIMITE_GH, raiz)
    if motivo is not None:
        raise Recusa(f"gh pr list falhou: {motivo}")
    try:
        lista = json.loads(feito.stdout.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        lista = None
    if not isinstance(lista, list) or not all(
            isinstance(pr, dict) and isinstance(pr.get("number"), int) and isinstance(pr.get("url"), str)
            and isinstance(pr.get("headRefName"), str) for pr in lista):
        raise Recusa("gh pr list falhou: saída ilegível")
    de_outras = []
    for pr in lista:
        achou = _RE_BRANCH.fullmatch(pr["headRefName"])
        if achou is None:
            continue
        if achou.group(1) == str(versao):
            return pr["number"], pr["url"]
        de_outras.append((pr["number"], achou.group(1), pr["url"]))
    if de_outras:
        numero, outra, url = min(de_outras, key=lambda pr: pr[0])
        raise Recusa(f"PR #{numero} da {manifesto.PREFIXO_TAG}{outra} ainda aberto: {url}; "
                     f"mescle-o ou feche-o antes de importar a v{versao}")
    return None


_CAMPOS_DO_PR = (("number", int), ("state", str), ("headRefOid", str), ("baseRefName", str), ("url", str))


def prs_da_branch(raiz: Path, ramo: str, executar=subprocess.run) -> list[PR]:
    """Os PRs da branch, em qualquer estado, pelo `gh pr list --head <ramo> --state all`, com TEMPO_LIMITE_GH, no
    `cwd` da raiz; a falha dá `Recusa("gh pr list falhou: <motivo>")`, e a saída que não é uma lista de objetos com os
    cinco campos, nos tipos certos, `Recusa("gh pr list falhou: saída ilegível")`."""
    feito, motivo = falha(["gh", "pr", "list", "--head", ramo, "--state", "all", "--json",
                           ",".join(nome for nome, _ in _CAMPOS_DO_PR)], "pr list", executar, TEMPO_LIMITE_GH, raiz)
    if motivo is not None:
        raise Recusa(f"gh pr list falhou: {motivo}")
    try:
        lista = json.loads(feito.stdout.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        lista = None
    if not isinstance(lista, list) or not all(
            isinstance(pr, dict) and all(isinstance(pr.get(nome), tipo) and not isinstance(pr.get(nome), bool)
                                         for nome, tipo in _CAMPOS_DO_PR)
            for pr in lista):
        raise Recusa("gh pr list falhou: saída ilegível")
    return [PR(*(pr[nome] for nome, _ in _CAMPOS_DO_PR)) for pr in lista]


def _de_novo(passo: str, motivo: str, versao: int) -> str:
    return f"{passo} falhou: {motivo}; rode harness.py importar v{versao} de novo"


def _ignorados(arvore: Path, caminhos: list[str], versao: int, executar) -> str | None:
    """O `git ls-files` dos arquivos que o git ignora entre os `caminhos` do `git add`, que o add não leva: o caminho
    ignorado dado a ele falha, e o de dentro de uma pasta fica de fora calado. O link do próprio núcleo
    (`comum.LINK_DO_NUCLEO`), que o hook refaz e o `.gitignore` do modelo ignora de propósito, fica de fora da lista;
    qualquer outro ignorado conta. Devolve a linha da parada, com a contagem e o primeiro em ordem alfabética; a do
    `ls-files` que falha; ou None, sem nenhum."""
    feito, motivo = _git(arvore, ["ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--", *caminhos],
                         executar, bloco.TEMPO_LIMITE_GIT)
    if motivo is not None:
        return _de_novo("git ls-files", motivo, versao)
    achados = feito.stdout.decode("utf-8", errors="replace").split("\0")
    nomes = sorted({nome for nome in achados if nome and nome != comum.LINK_DO_NUCLEO})
    if not nomes:
        return None
    quantos = "1 arquivo" if len(nomes) == 1 else f"{len(nomes)} arquivos"
    return (f"o git ignora {quantos} que o importar põe no commit, como {nomes[0]}; "
            f"ajuste o .gitignore e rode harness.py importar v{versao} de novo")


def _enviar_branch(raiz: Path, perfil, tag: Tag, branch: str, titulo: str, corpo: str, textos: dict[str, str],
                   problemas_: list[tuple[str, str]], executar) -> str | None:
    """A branch com a cópia e os gerados no origin, por um worktree temporário sem branch local, a partir do
    `origin/<ramo_principal>`, com o commit e o push; o worktree e a pasta saem no fim, também na falha. Os gerados são
    os `textos` gravados e os órfãos apagados, pelos `problemas_` contra o `origin/<ramo_principal>`, e o commit leva
    cada caminho deles, depois da parada com o arquivo que o git ignora entre eles (`_ignorados`). Sem branch local, o
    worktree de uma rodada interrompida por sinal não prende a seguinte. Devolve a linha da falha ou da parada, ou
    None."""
    pasta = Path(tempfile.mkdtemp(prefix="importar-"))
    arvore = pasta / "arvore"

    def passo(nome: str, onde: Path, argumentos: list[str], tempo: int) -> str | None:
        _, motivo = _git(onde, argumentos, executar, tempo)
        return None if motivo is None else _de_novo(nome, motivo, tag.versao)

    try:
        parada = passo("git worktree add", raiz, ["worktree", "add", "-q", "--detach", str(arvore),
                                                  f"refs/remotes/origin/{perfil.ramo_principal}"], TEMPO_LIMITE_COMMIT)
        if parada is not None:
            return parada
        gravar_copia(tag, arvore / perfil.caminhos.passagem)
        gerador.gravar(arvore, textos, problemas_)
        caminhos = [perfil.caminhos.passagem, *(caminho for _, caminho in problemas_)]
        return (_ignorados(arvore, caminhos, tag.versao, executar)
                or passo("git add", arvore, ["add", "-A", "--", *caminhos], bloco.TEMPO_LIMITE_GIT)
                or passo("git commit", arvore, ["commit", "-q", "-m", titulo, "-m", corpo], TEMPO_LIMITE_COMMIT)
                or passo("git push", arvore, ["push", "origin", f"HEAD:refs/heads/{branch}"], TEMPO_LIMITE_REDE))
    finally:
        _git(raiz, ["worktree", "remove", "--force", str(arvore)], executar, bloco.TEMPO_LIMITE_GIT)
        shutil.rmtree(pasta, ignore_errors=True)


def _conferir_ramo_da_montagem(raiz: Path, perfil, executar) -> None:
    """Na montagem, o primeiro commit sai no ramo do `HEAD`: o ramo diferente do `ramo_principal` do perfil recusa,
    antes de gravar qualquer coisa, com o comando que aponta o `HEAD` para ele."""
    ramo = perfil.ramo_principal
    feito, motivo = _git(raiz, ["symbolic-ref", "--short", "HEAD"], executar, bloco.TEMPO_LIMITE_GIT)
    if motivo is not None:
        raise Recusa(f"git symbolic-ref falhou: {motivo}; rode git symbolic-ref HEAD refs/heads/{ramo}")
    atual = feito.stdout.decode("utf-8", errors="replace").strip()
    if atual != ramo:
        raise Recusa(f"o ramo atual é {atual}, e o perfil diz {ramo}; rode git symbolic-ref HEAD refs/heads/{ramo}")


def _primeiro_commit(raiz: Path, perfil, tag: Tag, textos: dict[str, str], linhas: list[str], versao: int,
                     executar) -> Importacao:
    """A montagem, depois da conferência: a cópia e os gerados na árvore, conferidos contra ela; o `git rm --cached`
    dos órfãos que o `gravar` apagou, que o `git add --` não tira do índice; a parada com o arquivo que o git ignora
    entre os caminhos do add (`_ignorados`); o `git add --` dos caminhos do `iniciar`, da cópia e dos gerados que
    existem; e o primeiro commit. A falha de um passo, ou a parada dos ignorados, volta com `falhou`, com a cópia e os
    gerados na árvore. As `linhas` já trazem a conferência e as fichas."""
    problemas_ = gerador.problemas(textos, gerador.dados_do_disco(raiz), gerador.presentes_no_disco(raiz, executar))
    gravar_copia(tag, raiz / perfil.caminhos.passagem)
    gerador.gravar(raiz, textos, problemas_)
    linhas.append(linha_dos_gerados(problemas_))
    gerados = [caminho for caminho in textos if (raiz / caminho).exists()]
    caminhos = [*iniciar.caminhos_do_primeiro_commit(raiz, perfil), perfil.caminhos.passagem, *gerados]
    titulo = f"chore(harness): instala o harness e importa a passagem/v{versao}"
    orfaos = [caminho for problema, caminho in problemas_ if problema == gerador.ORFAO]
    # o `gravar` apagou os órfãos do disco, mas o `git add --` não os tira do índice, onde uma montagem anterior os pôs
    if orfaos:
        _, motivo = _git(raiz, ["rm", "--cached", "-q", "--ignore-unmatch", "--", *orfaos], executar,
                         bloco.TEMPO_LIMITE_GIT)
        if motivo is not None:
            return Importacao((*linhas, _de_novo("git rm", motivo, versao)), True)
    parada = _ignorados(raiz, caminhos, versao, executar)
    if parada is not None:
        return Importacao((*linhas, parada), True)
    for nome, argumentos, tempo in (("git add", ["add", "--", *caminhos], bloco.TEMPO_LIMITE_GIT),
                                    ("git commit", ["commit", "-q", "-m", titulo], TEMPO_LIMITE_COMMIT)):
        _, motivo = _git(raiz, argumentos, executar, tempo)
        if motivo is not None:
            return Importacao((*linhas, _de_novo(nome, motivo, versao)), True)
    feito, motivo = _git(raiz, ["rev-parse", "--short=7", "HEAD"], executar, bloco.TEMPO_LIMITE_GIT)
    if motivo is not None:
        return Importacao((*linhas, _de_novo("git rev-parse", motivo, versao)), True)
    sha = feito.stdout.decode("utf-8", errors="replace").strip()
    linhas.append(f"primeiro commit {sha}: harness e {manifesto.PREFIXO_TAG}{versao}; rode harness.py iniciar "
                  f"--conferir e faça o push do {perfil.ramo_principal}")
    return Importacao((*linhas, *_lembrete_do_espelho(perfil, True)))


def importar(raiz: Path, perfil, versao: int | None, executar=subprocess.run) -> Importacao:
    """Importa a `passagem/vN` (spec 6c, §8): na montagem, a cópia na árvore; nos outros casos, a branch
    `docs/passagem-vN` no origin e o PR dela, cada um com os gerados da cópia (spec 6d-gerador, §11),
    no modo PR pelo perfil do `origin/<ramo_principal>`. Toda recusa, também a do `gerar`, lança `Recusa` antes de
    gravar qualquer coisa; a falha de um passo depois da conferência volta com `falhou`."""
    if bloco.git(raiz, ["rev-parse", "--show-toplevel"], executar).returncode != 0:
        raise Recusa("fora de um repositório git")
    montagem = bloco.git(raiz, ["rev-parse", "--verify", "-q", "HEAD"], executar).returncode != 0
    if montagem:
        _conferir_ramo_da_montagem(raiz, perfil, executar)
    feito = bloco.git(raiz, ["remote", "get-url", "origin"], executar)
    origin = feito.stdout.decode("utf-8", errors="replace").strip() if feito.returncode == 0 else None
    repositorio = perfil.passagem.repositorio
    url = url_do_repositorio(repositorio, origin)
    existentes = versoes(url, executar)
    if versao is None:
        if not existentes:
            raise Recusa(f"nenhuma {manifesto.PREFIXO_TAG}N em {repositorio}")
        versao = existentes[-1]
    elif versao not in existentes:
        raise Recusa(f"{manifesto.PREFIXO_TAG}{versao} não existe em {repositorio}")
    rotulo = f"{manifesto.PREFIXO_TAG}{versao}"
    ramo = perfil.ramo_principal
    branch = f"{PREFIXO_DA_BRANCH}{versao}"
    antigo = None
    perfil_da_copia = perfil  # na montagem não há origin; no modo PR, o do `origin/<ramo>`
    if not montagem:
        buscar_principal(raiz, perfil, executar)
        perfil_da_copia = perfil_do_principal(raiz, perfil, executar)
        antigo = manifesto_do_principal(raiz, perfil, executar)
        if antigo is not None and antigo.versao == versao:
            raise Recusa(f"{rotulo} já está no {ramo}")
        if antigo is not None and antigo.versao > versao:
            raise Recusa(f"{rotulo} é mais velha que a v{antigo.versao} do {ramo}")
        aberto = _pr_aberto(raiz, versao, executar)
        if aberto is not None:
            return Importacao((f"PR #{aberto[0]} já aberto: {aberto[1]}", *_lembrete_do_espelho(perfil, False)))
    with buscar(url, versao, perfil, executar) as tag:
        try:
            textos = gerador.gerar(leitor_da_tag(tag, perfil_da_copia.caminhos.passagem), perfil_da_copia)
        except gerador.GeracaoRecusada as erro:
            raise Recusa("\n".join(f"importar: gerar recusou: {motivo}" for motivo in erro.motivos)) from None
        linhas = [linha_conferida(tag.manifesto), linha_das_fichas(tag.manifesto, antigo)]
        if montagem:
            return _primeiro_commit(raiz, perfil, tag, textos, linhas, versao, executar)
        lanes = bloco.lanes_vivas(raiz, perfil, executar)
        linhas.append(linha_dos_afetados(afetados(raiz, tag.manifesto, lanes, perfil, executar)))
        problemas_ = _gerados_no_principal(raiz, perfil, textos, executar)
        linhas.append(linha_dos_gerados(problemas_))
        feito, motivo = _git(raiz, ["ls-remote", "--heads", "origin", branch], executar, TEMPO_LIMITE_GH)
        if motivo is not None:
            raise Recusa(f"origin não consultado: {motivo}")
        titulo = f"docs(passagem): importa {rotulo}"
        corpo = "\n".join(linhas)
        refs = {linha.split("\t")[-1].strip() for linha in feito.stdout.decode("utf-8", "replace").splitlines()}
        if f"refs/heads/{branch}" not in refs:  # o ls-remote casa pelo fim do nome; vale só o nome exato
            parada = _enviar_branch(raiz, perfil_da_copia, tag, branch, titulo, corpo, textos, problemas_, executar)
            if parada is not None:
                return Importacao((*linhas, parada), True)
    feito, motivo = falha(["gh", "pr", "create", "--base", ramo, "--head", branch, "--title", titulo, "--body", corpo,
                            "--assignee", perfil.dono.github], "pr create", executar, TEMPO_LIMITE_GH, raiz)
    if motivo is not None:
        return Importacao((*linhas, _de_novo("gh pr create", motivo, versao)), True)
    endereco = (feito.stdout.decode("utf-8", errors="replace").strip().splitlines() or [""])[-1]
    achado = re.search(r"/pull/([0-9]+)", endereco)
    return Importacao((*linhas, f"PR #{achado.group(1)} aberto: {endereco}" if achado else f"PR aberto: {endereco}",
                       *_lembrete_do_espelho(perfil, False)))
