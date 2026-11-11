"""Invariantes conferidas pelo git (spec 3b, §8; 6c, §6.6, §8.5, §11.3; 6d-gerador, §9): planejamento, cópia, gerados, harness e segredos.
Os moldes ficam intocados, o arquivo de decisões só recebe acréscimos, o STATUS é válido, os documentos aprovados
que mudaram passam no `checar` e nenhuma linha acrescentada tem segredo. Na trilha de desenvolvimento, rodam o
`arquivos-do-harness`, que recusa a cópia da passagem, o `estado.md`, o `aceitacao.md` e o `revisao.md` mudados sem
commit, o `passagem-em-dia`, que confere a cópia da passagem contra o manifesto dela, o `gerados-em-dia`, que confere os
arquivos gerados contra o que o `gerar` escreveria, e o `sem-segredos`. Na trilha de planejamento, o `gerados-em-dia`
também roda, mas só quando o `CLAUDE.md` da versão nova puxa o gerado do planejamento (spec do porte 1, §9.3).

Três modos, chamados do mesmo jeito pelo Stop, pelo pre-commit e pela CI: `arvore` (o disco contra o `HEAD`),
`indice` (o índice contra o `HEAD`) e `base` (o `HEAD` contra a merge-base de uma ref com ele).
"""
from __future__ import annotations

import difflib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import backlog
import bloco
import checar
import comum
import estado
import gerado_planejamento
import gerador
import importacao
import legenda
import manifesto
import perfil_desenvolvimento
import segredos
import versao
from perfil import Perfil
from perfil_comum import PerfilComum, PerfilInvalido
from perfil_desenvolvimento import PerfilDesenvolvimento

AJUDA = """\
Confere pelo git os moldes intocados, as decisões só com acréscimos, o STATUS.md, o `checar` dos aprovados e os
segredos. Na trilha de desenvolvimento, as conferências do planejamento não rodam: rodam o `arquivos-do-harness` no
`--arvore`, o `passagem-em-dia` e o `gerados-em-dia` no `--indice` e no `--base`, e o `sem-segredos`. No planejamento,
o `gerados-em-dia` também roda no `--indice` e no `--base`, só com a linha do gerado no `CLAUDE.md`.

Um modo, e só um, é obrigatório: `--arvore`, o disco contra o HEAD, com os arquivos novos, que o hook de fim de turno
usa; `--indice`, o índice contra o HEAD, que o pre-commit usa; `--base <ref>`, o HEAD contra a merge-base da ref com
ele, que a CI usa. Os alterados vêm do git, com 10 s de limite por chamada; o renomeado conta pelos dois nomes.

- `moldes-intocados`: falha se um arquivo da pasta de moldes foi acrescentado, alterado, apagado ou renomeado. Sem
  nenhum arquivo da pasta na base, o `HEAD` ou a merge-base, a pasta nasce na mudança, e o acrescentado passa, com a
  linha `moldes-intocados: OK`. A outra exceção é o acrescentado ou alterado que o `moldes.liberados` do perfil libera
  com o hash do conteúdo novo, com `\\r\\n` contado como `\\n`; com algum liberado e nenhuma falha, a linha é
  `moldes-intocados: OK (<n> liberados pelo perfil)`. O liberado com outro hash falha, e o `--verbose` diz
  `<arquivo>: hash <do conteúdo>, o perfil libera <do perfil>`.
- `so-acrescimos`: falha se uma linha do arquivo de decisões sumiu ou mudou, inclusive por texto acrescentado dentro
  dela, ou se o arquivo foi apagado; o acréscimo no meio passa, e a troca da quebra de linha do Windows não conta.
- `status-valido`: falha se o STATUS.md da versão nova falta ou não passa na validação do `estado`.
- `status-pelo-harness`, só com `--indice`, logo depois do `status-valido`: compara o STATUS.md do índice com o hash
  que o harness grava a cada mudança dele, no arquivo `harness-status` do diretório do git desta cópia. Nunca falha:
  `status-pelo-harness: OK`, com o STATUS fora dos alterados, acrescentado ou igual ao gravado; senão,
  `status-pelo-harness: AVISO: <status> do commit não é o que o harness gravou por último nesta cópia; confira com
  harness.py proximo`.
- `checar-aprovados`, só com `--indice` e `--base`: falha se um `.md` alterado da pasta do planejamento, `aprovado`
  no backlog da versão nova, falha no `checar`, com o texto e o molde da versão nova.
- `legenda-em-dia`, só com `--indice` e `--base` e só com `caminhos.legenda` no perfil: gera a legenda com os
  arquivos da versão nova, sempre, sem olhar o que mudou, e a compara com a legenda da versão nova. Saídas:
  `legenda-em-dia: OK`; `legenda-em-dia: FALHA: rode harness.py legenda`, com a legenda ausente ou diferente; e
  `legenda-em-dia: FALHA: tipo de ID sem legenda: <tipo>`, quando a geração recusa, com todos os tipos no `--verbose`.
- `passagem-em-dia`, só na trilha de desenvolvimento, com `--indice` e `--base`, quando o que mudou toca a cópia da
  passagem (`caminhos.passagem`): falha se a cópia da versão nova não confere com o manifesto dela, que deve ser
  legível e de um formato que o harness lê, com cada arquivo no `sha256` do manifesto e nenhum a mais nem a menos, e
  com cada `ids[]` no arquivo dele e com o trecho refeito da primeira linha igual ao do manifesto, nas linhas e no
  `sha256`; o `ids[]` de um arquivo que falta ou difere não é conferido, e as `pendencias` ficam de fora. Sem arquivo
  da cópia na versão nova, passa. O resumo traz a primeira falha, na ordem do manifesto, com os `ids` depois dos
  arquivos e os arquivos a mais por último, e o `--verbose` lista todas:
  `<passagem>/<arquivo> difere do manifesto; a cópia muda só por harness.py importar`;
  `<passagem>/<arquivo> sobra na cópia`; `falta <passagem>/<arquivo>`;
  `ids.<ID>: <passagem>/<arquivo> não está em arquivos; a cópia muda só por harness.py importar`;
  `ids.<ID>: o trecho <passagem>/<arquivo>:<primeira>-<última> difere do manifesto; a cópia muda só por harness.py importar`;
  `manifesto ilegível: <motivo>`; e `formato <f>; este harness lê o formato <lista>`.
- `gerados-em-dia`, com `--indice` e `--base`: gera os arquivos como o
  `harness.py gerar` e os compara com os da versão nova, byte a byte, com o perfil (`.claude/perfil.toml`), a cópia da
  passagem e os arquivos das duas pastas do gerador da versão nova, lidos do índice ou do commit, nunca do disco. Falha
  se um arquivo gerado falta (`ausente`), difere (`desatualizado`) ou sobra nas pastas do gerador (`órfão`). Sem o
  perfil, passa calada: não há o que gerar. Sem o manifesto da cópia que ele aponta na versão nova, só o
  `.github/workflows/harness.yml` se confere. Esse arquivo vem do `.claude/settings.json` da versão nova, nas duas
  trilhas, e sem o settings fica de fora; o settings que não fixa a versão do plugin, ou a fixa diferente da do núcleo
  carregado, dá a recusa dele. O resumo traz o
  primeiro problema, na ordem do `gerar`, com `; <n> no total` quando há mais, e termina com `; rode harness.py gerar`:
  `gerados-em-dia: FALHA: desatualizado: <caminho>; rode harness.py gerar`. A recusa do `gerar` vira a falha, sem o
  comando, que ele também recusaria: `gerados-em-dia: FALHA: <recusa>`, com o total. O perfil da versão nova que não
  vale dá `gerados-em-dia: FALHA: .claude/perfil.toml: <motivo>`. O `--verbose` lista cada problema ou cada recusa.
  No planejamento, a conferência entra depois da `legenda-em-dia`: o `harness.yml` sempre se confere, e o
  `.claude/harness/gerado/planejamento.md`, com o perfil do planejamento e a única pasta dele,
  `.claude/harness/gerado/`, só quando o `CLAUDE.md` da versão nova tem uma linha igual a
  `@.claude/harness/gerado/planejamento.md`; as linhas de saída são as mesmas. Sem a linha e sem o settings, a saída é
  a de um repositório sem o gerado.
- `arquivos-do-harness`, só na trilha de desenvolvimento e só com `--arvore`: falha se um arquivo da cópia da
  passagem (`caminhos.passagem`), um `<blocos>/*/estado.md`, um `<blocos>/*/aceitacao.md` ou um
  `<blocos>/*/revisao.md` tem mudança sem commit: os comandos do harness fazem commit na hora, e a mudança sem commit
  veio de fora. O `<blocos>/*/gabarito.md` fica de fora: o `revisao preparar` o grava sem commit. O arquivo
  rastreado, o novo no índice inclusive, dá
  `<caminho> mudou fora de um comando do harness; desfaça com git restore --staged --worktree <caminho>`, e o não
  rastreado, `<caminho> não veio de um comando do harness; peça ao usuário que o apague`. O resumo traz o primeiro
  caminho, em ordem alfabética, com `; <n> no total` quando há mais; o `--verbose` lista todos. Sem HEAD, como na
  montagem, passa.
- `sem-segredos`, nos três modos e nas duas trilhas, por último: falha se uma linha acrescentada contra a base, ou
  contra a árvore vazia sem HEAD, casa um padrão de segredo do núcleo ou de `[guarda.segredos]`; o arquivo renomeado
  ou copiado compara com a origem dele, e uma origem de `segredos_isentos` conta como vazia; no `--arvore`, os
  não rastreados entram inteiros. Ficam de fora os arquivos de `segredos_isentos` e os binários, com um NUL nos
  primeiros 8.000 bytes. O resumo é `sem-segredos: FALHA: <arquivo>:<linha>: segredo (<nome do padrão>)`, o
  primeiro achado, com `; <n> no total` quando há mais; o `--verbose` lista cada um, e o texto nunca aparece.

Saída: uma linha por conferência, `<nome>: OK`, `<nome>: FALHA: <resumo>` ou, no `status-pelo-harness`,
`<nome>: AVISO: <resumo>`, que não muda o código de saída, como
`so-acrescimos: FALHA: linha <n> de <arquivo> tirada ou alterada`. Com `--verbose`, abaixo de cada falha: os arquivos
dos moldes, os erros do STATUS.md ou `<documento>: <verificações que falharam>`. Sem nenhum commit, as conferências
que comparam com a base passam. Sai com 1 se alguma falha, e também com `erro: fora de um repositório git`,
`erro: ref inválida ou sem ancestral comum: <ref>` ou `erro: git indisponível: <motivo>`.
"""

MOLDES_INTOCADOS = "moldes-intocados"
SO_ACRESCIMOS = "so-acrescimos"
STATUS_VALIDO = "status-valido"
STATUS_PELO_HARNESS = "status-pelo-harness"
CHECAR_APROVADOS = "checar-aprovados"
LEGENDA_EM_DIA = "legenda-em-dia"
PASSAGEM_EM_DIA = "passagem-em-dia"
GERADOS_EM_DIA = "gerados-em-dia"
ARQUIVOS_DO_HARNESS = "arquivos-do-harness"
SEM_SEGREDOS = "sem-segredos"

ARVORE = "arvore"
INDICE = "indice"
BASE = "base"
MODOS = (ARVORE, INDICE, BASE)

TEMPO_LIMITE_GIT = 10
# Os bytes do começo do arquivo em que um NUL o marca como binário, como o git faz.
BYTES_DO_BINARIO = 8000

_STATUS_APROVADO = "aprovado"


@dataclass(frozen=True)
class Conferencia:
    """Resultado de uma conferência: `resumo` é a linha da saída; `detalhes`, o que o `--verbose` mostra abaixo."""

    nome: str
    ok: bool
    resumo: str
    detalhes: tuple[str, ...] = ()


class ErroGit(Exception):
    """O git não respondeu, a raiz não é repositório ou a ref não serve. `mensagem` diz o motivo."""

    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


def _linhas(texto: str) -> list[str]:
    """Linhas do texto sem o `\\r` final e sem a linha vazia que o `\\n` final deixaria."""
    linhas = texto.split("\n")
    if linhas[-1] == "":
        linhas.pop()
    return [linha.rstrip("\r") for linha in linhas]


def linha_tirada(antigo: str, novo: str) -> int | None:
    """Número, a partir de 1, da primeira linha de `antigo` tirada ou alterada em `novo`; None se só houve acréscimo.

    Acrescentar texto no meio de uma linha existente altera a linha. A troca de `\\r\\n` por `\\n` não conta.
    """
    comparacao = difflib.SequenceMatcher(None, _linhas(antigo), _linhas(novo), autojunk=False)
    for operacao, i1, _, _, _ in comparacao.get_opcodes():
        if operacao not in ("equal", "insert"):
            return i1 + 1
    return None


def linhas_acrescentadas(antigo: str | None, novo: str) -> list[tuple[int, str]]:
    """(número a partir de 1, texto) das linhas de `novo` que o `difflib.SequenceMatcher` marca como inseridas ou
    trocadas contra `antigo`; com `antigo` None, todas. A troca de `\\r\\n` por `\\n` não conta.

    O `autojunk` fica no padrão: sem ele, um arquivo de linhas muito repetidas leva segundos e estoura o Stop. Com
    ele, a linha repetida pode sair como acrescentada, mas a linha de texto novo nunca sai como igual."""
    linhas_novas = _linhas(novo)
    if antigo is None:
        return list(enumerate(linhas_novas, start=1))
    comparacao = difflib.SequenceMatcher(None, _linhas(antigo), linhas_novas)
    return [
        (j + 1, linhas_novas[j])
        for operacao, _, _, j1, j2 in comparacao.get_opcodes() if operacao in ("insert", "replace")
        for j in range(j1, j2)
    ]


def binario(dados: bytes) -> bool:
    """Um NUL nos primeiros 8.000 bytes."""
    return b"\0" in dados[:BYTES_DO_BINARIO]


def _ok(nome: str) -> Conferencia:
    return Conferencia(nome, True, f"{nome}: OK")


def _plural(quantidade: int, singular: str) -> str:
    return f"{quantidade} {singular}" if quantidade == 1 else f"{quantidade} {singular}s"


def ler_status(saida: bytes) -> list[tuple[str, str]]:
    """O código de duas letras e o caminho de cada entrada do `git status --porcelain=v1 -z`; o renomeado e o copiado
    dão duas entradas com o mesmo código, o nome novo primeiro."""
    entradas = saida.decode("utf-8", errors="replace").split("\0")
    lidas: list[tuple[str, str]] = []
    posicao = 0
    while posicao < len(entradas):
        entrada = entradas[posicao]
        posicao += 1
        if len(entrada) < 4:
            continue
        codigo, caminho = entrada[:2], entrada[3:]
        lidas.append((codigo, caminho))
        if "R" in codigo or "C" in codigo:
            if posicao < len(entradas) and entradas[posicao]:
                lidas.append((codigo, entradas[posicao]))
            posicao += 1
    return lidas


class _Git:
    """Leitura do repositório para um modo: a lista de alterados e o conteúdo da base e da versão nova."""

    def __init__(self, raiz: Path, modo: str, ref: str | None, executar):
        self.raiz = raiz
        self.modo = modo
        self.executar = executar
        self._origens: dict[str, str] = {}
        if self.rodar("rev-parse", "--show-toplevel").returncode != 0:
            raise ErroGit("fora de um repositório git")
        self.base_rev: str | None = None
        if modo == BASE:
            invalida = ErroGit(f"ref inválida ou sem ancestral comum: {ref}")
            if self.rodar("rev-parse", "--verify", "-q", f"{ref}^{{commit}}").returncode != 0:
                raise invalida
            merge_base = self.rodar("merge-base", str(ref), "HEAD")
            if merge_base.returncode != 0:
                raise invalida
            self.base_rev = self.texto(merge_base.stdout).strip()
        elif self.rodar("rev-parse", "--verify", "-q", "HEAD").returncode == 0:
            self.base_rev = "HEAD"

    def rodar(self, *argumentos: str) -> subprocess.CompletedProcess:
        try:
            return self.executar(
                ["git", "-C", str(self.raiz), *argumentos], capture_output=True, timeout=TEMPO_LIMITE_GIT
            )
        except OSError as erro:
            raise ErroGit(f"git indisponível: {comum.motivo_do_sistema(erro)}") from None
        except subprocess.SubprocessError as erro:
            raise ErroGit(f"git indisponível: {type(erro).__name__}: {erro}") from None

    @staticmethod
    def texto(dados: bytes) -> str:
        return dados.decode("utf-8", errors="replace")

    @property
    def tem_base(self) -> bool:
        return self.base_rev is not None

    def entradas_do_status(self) -> list[tuple[str, str]]:
        """As entradas do `git status --porcelain=v1 -z --untracked-files=all`, pelo `ler_status`."""
        return ler_status(self.rodar("status", "--porcelain=v1", "-z", "--untracked-files=all").stdout)

    def alterados(self) -> list[str]:
        """Caminhos alterados em relação à base, relativos à raiz, sem repetição; renomeado conta pelos dois nomes.
        Guarda o par de cada renomeado ou copiado, o nome novo e a origem, para o `origem`."""
        self._origens = {}
        if self.modo == ARVORE:
            entradas_do_status = self.entradas_do_status()
            caminhos = [caminho for _, caminho in entradas_do_status]
            posicao = 0
            while posicao < len(entradas_do_status):
                codigo, caminho = entradas_do_status[posicao]
                posicao += 1
                if ("R" in codigo or "C" in codigo) and posicao < len(entradas_do_status):
                    self._origens[caminho] = entradas_do_status[posicao][1]
                    posicao += 1
        else:
            if self.modo == INDICE:
                saida = self.rodar("diff", "--cached", "--name-status", "-z")
            else:
                saida = self.rodar("diff", "--name-status", "-z", str(self.base_rev), "HEAD")
            entradas = self.texto(saida.stdout).split("\0")
            caminhos = []
            posicao = 0
            while posicao < len(entradas):
                codigo = entradas[posicao]
                posicao += 1
                if not codigo:
                    continue
                quantos = 2 if codigo[0] in "RC" else 1
                nomes = [c for c in entradas[posicao:posicao + quantos] if c]
                caminhos += nomes
                if quantos == 2 and len(nomes) == 2:
                    self._origens[nomes[1]] = nomes[0]
                posicao += quantos
        return list(dict.fromkeys(caminhos))

    def origem(self, caminho: str) -> str:
        """O caminho de origem do renomeado ou copiado, pelo par que o `alterados` leu; o próprio caminho nos outros.
        O que o git não pareia, como o `mv` sem `git add`, também fica com o próprio caminho."""
        return self._origens.get(caminho, caminho)

    def arquivos(self, pasta: str) -> list[str]:
        """Os arquivos da versão nova dentro da pasta, relativos à raiz: o índice no modo `indice`, o `HEAD` no
        `base`."""
        if self.modo == INDICE:
            saida = self.rodar("ls-files", "-z", "--", pasta)
        else:
            saida = self.rodar("ls-tree", "-r", "-z", "--name-only", "HEAD", "--", pasta)
        return [caminho for caminho in self.texto(saida.stdout).split("\0") if caminho]

    def base_tem_arquivo_em(self, pasta: str) -> bool:
        """Se a base tem algum arquivo dentro da pasta: o `HEAD` no `arvore` e no `indice`, a merge-base no `base`."""
        if self.base_rev is None:
            return False
        saida = self.rodar("ls-tree", "-r", "-z", "--name-only", self.base_rev, "--", pasta)
        return any(caminho for caminho in self.texto(saida.stdout).split("\0"))

    def mostrar_dados(self, rev: str, caminho: str) -> bytes | None:
        saida = self.rodar("show", f"{rev}:./{caminho}")
        return saida.stdout if saida.returncode == 0 else None

    def mostrar(self, rev: str, caminho: str) -> str | None:
        dados = self.mostrar_dados(rev, caminho)
        return None if dados is None else self.texto(dados)

    def da_base(self, caminho: str) -> str | None:
        """Conteúdo na base; None se o arquivo não existe lá ou se não há base."""
        return self.mostrar(self.base_rev, caminho) if self.base_rev is not None else None

    def dados_novos(self, caminho: str) -> bytes | None:
        """Bytes da versão nova: o disco, o índice ou o `HEAD`, conforme o modo; None se o arquivo não existe."""
        if self.modo == ARVORE:
            try:
                return (self.raiz / caminho).read_bytes()
            except OSError:
                return None
        return self.mostrar_dados("" if self.modo == INDICE else "HEAD", caminho)

    def novo(self, caminho: str) -> str | None:
        """Conteúdo da versão nova, como o `dados_novos`, em texto."""
        dados = self.dados_novos(caminho)
        return None if dados is None else self.texto(dados)


def _dentro(caminho: str, pasta: str) -> bool:
    return caminho.startswith(pasta.rstrip("/") + "/")


def hash_do_molde(dados: bytes) -> str:
    """O hash curto do `versao` com `\\r\\n` contado como `\\n`: o disco com CRLF bate com o índice com LF."""
    return versao.hash_dos_bytes(dados.replace(b"\r\n", b"\n"))


def _moldes_intocados(git: _Git, alterados: list[str], perfil: Perfil) -> Conferencia:
    """Falha com os moldes alterados, menos os que o perfil libera com o hash do conteúdo novo. Sem nenhum arquivo da
    pasta de moldes na base, a pasta nasce agora: todo molde da mudança é acrescentado, e passa."""
    if not git.tem_base:
        return _ok(MOLDES_INTOCADOS)
    nos_moldes = sorted(caminho for caminho in alterados if _dentro(caminho, perfil.moldes.pasta))
    if not nos_moldes or not git.base_tem_arquivo_em(perfil.moldes.pasta):
        return _ok(MOLDES_INTOCADOS)
    inicio_relativo = len(perfil.moldes.pasta.rstrip("/")) + 1
    liberados = 0
    falhas: list[str] = []
    detalhes: list[str] = []
    for caminho in nos_moldes:
        do_perfil = perfil.moldes.liberados.get(caminho[inicio_relativo:])
        dados = git.dados_novos(caminho) if do_perfil is not None else None
        if dados is None:
            falhas.append(caminho)
            detalhes.append(caminho)
            continue
        do_conteudo = hash_do_molde(dados)
        if do_conteudo == do_perfil:
            liberados += 1
        else:
            falhas.append(caminho)
            detalhes.append(f"{caminho}: hash {do_conteudo}, o perfil libera {do_perfil}")
    if not falhas:
        resumo = f"{MOLDES_INTOCADOS}: OK ({_plural(liberados, 'liberado')} pelo perfil)"
        return Conferencia(MOLDES_INTOCADOS, True, resumo)
    resumo = f"{MOLDES_INTOCADOS}: FALHA: {_plural(len(falhas), 'arquivo')}, primeiro {falhas[0]}"
    return Conferencia(MOLDES_INTOCADOS, False, resumo, tuple(detalhes))


def _so_acrescimos(git: _Git, alterados: list[str], perfil: Perfil) -> Conferencia:
    decisoes = perfil.caminhos.decisoes
    if not git.tem_base or decisoes not in alterados:
        return _ok(SO_ACRESCIMOS)
    antigo = git.da_base(decisoes)
    if antigo is None:
        return _ok(SO_ACRESCIMOS)
    novo = git.novo(decisoes)
    if novo is None:
        return Conferencia(SO_ACRESCIMOS, False, f"{SO_ACRESCIMOS}: FALHA: {decisoes} apagado")
    linha = linha_tirada(antigo, novo)
    if linha is None:
        return _ok(SO_ACRESCIMOS)
    return Conferencia(SO_ACRESCIMOS, False, f"{SO_ACRESCIMOS}: FALHA: linha {linha} de {decisoes} tirada ou alterada")


def _status_valido(git: _Git, perfil: Perfil) -> Conferencia:
    status = perfil.caminhos.status
    texto = git.novo(status)
    if texto is None:
        return Conferencia(STATUS_VALIDO, False, f"{STATUS_VALIDO}: FALHA: {status} ausente")
    erros = estado.validar(texto, perfil)
    if erros:
        return Conferencia(STATUS_VALIDO, False, f"{STATUS_VALIDO}: FALHA: {erros[0]}", tuple(erros))
    return _ok(STATUS_VALIDO)


def _status_pelo_harness(git: _Git, alterados: list[str], perfil: Perfil) -> Conferencia:
    """Avisa, sem falhar, o STATUS do índice que difere do hash que o harness gravou por último nesta cópia."""
    status = perfil.caminhos.status
    if not git.tem_base or status not in alterados or git.da_base(status) is None:
        return _ok(STATUS_PELO_HARNESS)
    dados = git.dados_novos(status)
    if dados is None:
        return _ok(STATUS_PELO_HARNESS)
    pasta = comum.diretorio_do_git(git.raiz)
    try:
        gravado = None if pasta is None else comum.ler_texto(pasta / estado.ARQUIVO_DA_GRAVACAO).strip()
    except (OSError, UnicodeDecodeError):
        gravado = None
    if gravado == estado.hash_do_status(dados):
        return _ok(STATUS_PELO_HARNESS)
    resumo = (f"{STATUS_PELO_HARNESS}: AVISO: {status} do commit não é o que o harness gravou por último nesta cópia; "
              "confira com harness.py proximo")
    return Conferencia(STATUS_PELO_HARNESS, True, resumo)


def _checar_aprovados(git: _Git, alterados: list[str], perfil: Perfil) -> Conferencia:
    """`checar` de cada `.md` alterado sob o planejamento, fora dos moldes, com status aprovado no backlog novo."""
    if not git.tem_base:
        return _ok(CHECAR_APROVADOS)
    planejamento = perfil.caminhos.planejamento
    texto_backlog = git.novo(perfil.caminhos.backlog)
    aprovados = {
        caminho
        for _, caminho, status in backlog.artefatos_da_pasta(texto_backlog or "", planejamento)
        if status == _STATUS_APROVADO
    }
    detalhes = []
    for caminho in sorted(alterados):
        if not (caminho.endswith(".md") and _dentro(caminho, planejamento) and caminho in aprovados):
            continue
        if _dentro(caminho, perfil.moldes.pasta):
            continue
        texto = git.novo(caminho)
        if texto is None:
            continue
        molde = checar.resolver_molde(git.raiz, Path(caminho), perfil).relative_to(git.raiz).as_posix()
        texto_molde = git.novo(molde)
        if texto_molde is None:
            try:
                texto_molde = comum.ler_texto(git.raiz / molde)
            except (OSError, UnicodeDecodeError):
                detalhes.append(f"{caminho}: molde ausente ({molde})")
                continue
        resultados = checar.checar_versao(git.raiz, caminho, texto, texto_molde, texto_backlog, perfil)
        falhas = [resultado.nome for resultado in resultados if not resultado.ok]
        if falhas:
            detalhes.append(f"{caminho}: {', '.join(falhas)}")
    if not detalhes:
        return _ok(CHECAR_APROVADOS)
    primeiro = detalhes[0].split(": ", 1)[0]
    resumo = f"{CHECAR_APROVADOS}: FALHA: {_plural(len(detalhes), 'documento')}, primeiro {primeiro}"
    return Conferencia(CHECAR_APROVADOS, False, resumo, tuple(detalhes))


def _legenda_em_dia(git: _Git, perfil: Perfil) -> Conferencia:
    """A legenda gerada com os arquivos da versão nova contra a legenda da versão nova, byte a byte."""
    try:
        texto = legenda.gerar(git.novo, perfil)
    except legenda.LegendaRecusada as erro:
        return Conferencia(LEGENDA_EM_DIA, False, f"{LEGENDA_EM_DIA}: FALHA: {erro.motivos[0]}", erro.motivos)
    if git.dados_novos(perfil.caminhos.legenda) != texto.encode("utf-8"):
        return Conferencia(LEGENDA_EM_DIA, False, f"{LEGENDA_EM_DIA}: FALHA: rode harness.py legenda")
    return _ok(LEGENDA_EM_DIA)


def _problemas_da_copia(git: _Git, pasta: str, presentes: list[str]) -> list[str]:
    """Os problemas da cópia da versão nova contra o manifesto dela: o manifesto que falta ou não se lê, sozinho; senão,
    cada arquivo do manifesto ausente ou com outro `sha256`, na ordem; depois cada `ids[]` fora de `arquivos` ou com o
    trecho refeito diferente, na ordem, só quando o arquivo dele confere pelo `sha256`; e por último os arquivos a mais,
    em ordem alfabética."""
    caminho_do_manifesto = f"{pasta}/{manifesto.NOME}"
    dados = git.dados_novos(caminho_do_manifesto)
    if dados is None:
        return [f"falta {caminho_do_manifesto}"]
    try:
        m = manifesto.de_json(dados.decode("utf-8"))
    except UnicodeDecodeError:
        return ["manifesto ilegível: fora do UTF-8"]
    except manifesto.ManifestoInvalido as erro:
        return [f"manifesto ilegível: {erro.motivo}"]
    if m.formato not in importacao.FORMATOS_LIDOS or isinstance(m.formato, bool):
        lidos = comum.juntar((str(formato) for formato in importacao.FORMATOS_LIDOS), "ou")
        return [f"formato {json.dumps(m.formato)}; este harness lê o formato {lidos}"]
    problemas = []
    esperados = {caminho_do_manifesto}
    conferidos = {}
    for arquivo in m.arquivos:
        if not isinstance(arquivo.caminho, str) or not comum.caminho_normalizado(arquivo.caminho) \
                or arquivo.caminho == manifesto.NOME:
            return [f"manifesto ilegível: caminho inválido: {arquivo.caminho}"]
        relativo = f"{pasta}/{arquivo.caminho}"
        esperados.add(relativo)
        conteudo = git.dados_novos(relativo)
        if conteudo is None:
            problemas.append(f"falta {relativo}")
        elif manifesto.sha256(conteudo) != arquivo.sha256:
            problemas.append(f"{relativo} difere do manifesto; a cópia muda só por harness.py importar")
        else:
            conferidos[arquivo.caminho] = git.texto(conteudo)
    caminhos = {arquivo.caminho for arquivo in m.arquivos}
    for id_, definicao in m.ids.items():
        problema = _problema_do_id(pasta, id_, definicao, caminhos, conferidos)
        if problema:
            problemas.append(problema)
    return problemas + [f"{caminho} sobra na cópia" for caminho in sorted(set(presentes) - esperados)]


def _problema_do_id(pasta: str, id_: str, definicao: manifesto.Definicao, caminhos: set[str],
                    conferidos: dict[str, str]) -> str | None:
    """O problema do `ids[]` do manifesto, ou None: o arquivo fora de `arquivos`, ou o trecho refeito, a partir da
    primeira linha, com outras linhas ou outro `sha256`. O arquivo que falta ou difere, fora dos `conferidos`, não tem
    o `ids[]` conferido."""
    arquivo = definicao.arquivo
    if not isinstance(arquivo, str) or arquivo not in caminhos:
        return f"ids.{id_}: {pasta}/{arquivo} não está em arquivos; a cópia muda só por harness.py importar"
    if arquivo not in conferidos:
        return None
    texto = conferidos[arquivo]
    partes = texto.split("\n")
    quantas = len(partes) - 1 + bool(partes[-1])
    primeira, ultima = definicao.linhas
    if primeira > quantas or manifesto.definicao(arquivo, texto, primeira) != definicao:
        return (f"ids.{id_}: o trecho {pasta}/{arquivo}:{primeira}-{ultima} difere do manifesto; "
                "a cópia muda só por harness.py importar")
    return None


def _passagem_em_dia(git: _Git, alterados: list[str], perfil: PerfilDesenvolvimento) -> Conferencia:
    """A cópia da passagem da versão nova igual ao manifesto dela, quando o que mudou a toca e ela existe. O resumo
    traz o primeiro problema; os detalhes, todos."""
    pasta = perfil.caminhos.passagem
    presentes = git.arquivos(pasta)
    if not presentes or not any(_dentro(caminho, pasta) for caminho in alterados):
        return _ok(PASSAGEM_EM_DIA)
    problemas = _problemas_da_copia(git, pasta, presentes)
    if not problemas:
        return _ok(PASSAGEM_EM_DIA)
    return Conferencia(PASSAGEM_EM_DIA, False, f"{PASSAGEM_EM_DIA}: FALHA: {problemas[0]}", tuple(problemas))


def _gerados_em_dia(git: _Git) -> Conferencia:
    """Os arquivos gerados da versão nova iguais ao que o `gerar` escreveria com o perfil e a cópia dela: o perfil, o
    manifesto, a cópia, os gerados e os arquivos das pastas do gerador lidos do índice ou do commit, mais o
    `harness.yml`, que não depende do manifesto. Sem o perfil, passa; sem o manifesto, só o `harness.yml` se confere. A
    recusa do `gerar` e o perfil que não vale são a falha, e o resumo traz a primeira, com o total; os detalhes,
    todas."""
    texto_do_perfil = git.novo(comum.CAMINHO_PERFIL)
    if texto_do_perfil is None:
        return _ok(GERADOS_EM_DIA)
    try:
        perfil = perfil_desenvolvimento.do_texto(texto_do_perfil)
    except PerfilInvalido as erro:
        motivo = f"{comum.CAMINHO_PERFIL}: " + erro.mensagem.removeprefix("perfil inválido: ")
        return Conferencia(GERADOS_EM_DIA, False, f"{GERADOS_EM_DIA}: FALHA: {motivo}", (motivo,))
    textos, recusas = gerador.textos_do_ci(git.novo, perfil)
    presentes: list[str] = []
    if git.dados_novos(f"{perfil.caminhos.passagem}/{manifesto.NOME}") is not None:
        try:
            textos = {**textos, **gerador.gerar(git.novo, perfil)}
        except gerador.GeracaoRecusada as erro:
            recusas = (*erro.motivos, *recusas)
        presentes = [caminho for pasta in gerador.PASTAS for caminho in git.arquivos(pasta)]
    return _conferencia_dos_gerados(textos, git, presentes, recusas)


def _conferencia_dos_gerados(textos: dict[str, str], git: _Git, presentes: list[str],
                             recusas: tuple[str, ...]) -> Conferencia:
    """O `gerados-em-dia` dos `textos` contra o índice ou o commit: com recusas, a primeira vira o resumo, com o total
    quando há mais, e os detalhes são todas; senão OK sem problemas, ou o resumo com o primeiro, o total quando há mais
    e o comando, e os detalhes, um `<problema>: <caminho>` por problema."""
    if recusas:
        total = f"; {len(recusas)} no total" if len(recusas) > 1 else ""
        return Conferencia(GERADOS_EM_DIA, False, f"{GERADOS_EM_DIA}: FALHA: {recusas[0]}{total}", recusas)
    detalhes = tuple(f"{problema}: {caminho}"
                     for problema, caminho in gerador.problemas(textos, git.dados_novos, presentes))
    if not detalhes:
        return _ok(GERADOS_EM_DIA)
    total = f"; {len(detalhes)} no total" if len(detalhes) > 1 else ""
    return Conferencia(GERADOS_EM_DIA, False, f"{GERADOS_EM_DIA}: FALHA: {detalhes[0]}{total}; rode harness.py gerar",
                       detalhes)


def _gerados_em_dia_do_planejamento(git: _Git, perfil: Perfil, com_a_linha: bool) -> Conferencia | None:
    """O `harness.yml` e, com a linha do `CLAUDE.md`, o `planejamento.md` da versão nova iguais ao que o `gerar`
    escreveria com o perfil, com os arquivos da pasta dos gerados lidos do índice ou do commit. As linhas são as do
    `_gerados_em_dia`. Sem a linha e sem nada do CI (sem settings), None: a saída é a de um repositório sem o gerado."""
    textos, recusas = gerador.textos_do_ci(git.novo, perfil)
    presentes: list[str] = []
    if com_a_linha:
        textos = {**textos, **gerador.gerar_na_trilha(git.novo, perfil)}
        presentes = [caminho for pasta in gerador.pastas_da_trilha(perfil) for caminho in git.arquivos(pasta)]
    elif not textos and not recusas:
        return None
    return _conferencia_dos_gerados(textos, git, presentes, recusas)


def _puxa_o_gerado_do_planejamento(git: _Git) -> bool:
    """O `CLAUDE.md` da versão nova tem uma linha igual à `LINHA_DO_CLAUDE_MD` (decisão 11 do porte 1)."""
    texto = git.novo("CLAUDE.md")
    return texto is not None and gerado_planejamento.LINHA_DO_CLAUDE_MD in texto.splitlines()


def _arquivos_do_harness(git: _Git, perfil: PerfilDesenvolvimento) -> Conferencia:
    """Nenhum arquivo da cópia da passagem, `<blocos>/*/estado.md`, `<blocos>/*/aceitacao.md` ou
    `<blocos>/*/revisao.md` mudado sem commit (spec 6d-bloco, §8.7); sem `HEAD`, passa. O não rastreado (`??`) não veio
    de um comando do harness; o resto, o novo no índice inclusive, mudou fora de um. O resumo traz o primeiro caminho,
    em ordem alfabética, com o total; os detalhes, todos."""
    if not git.tem_base:
        return _ok(ARQUIVOS_DO_HARNESS)
    blocos = perfil.caminhos.blocos
    padroes = (f"{blocos}/*/{bloco.ARQUIVO}", f"{blocos}/*/{bloco.ARQUIVO_DA_ACEITACAO}",
               f"{blocos}/*/{bloco.ARQUIVO_DA_REVISAO}")
    problemas: dict[str, str] = {}
    for codigo, caminho in git.entradas_do_status():
        if not _dentro(caminho, perfil.caminhos.passagem) and not any(comum.casa_padrao(p, caminho) for p in padroes):
            continue
        if codigo == "??":
            problemas[caminho] = f"{caminho} não veio de um comando do harness; peça ao usuário que o apague"
        else:
            problemas[caminho] = (f"{caminho} mudou fora de um comando do harness; desfaça com "
                                  f"git restore --staged --worktree {caminho}")
    if not problemas:
        return _ok(ARQUIVOS_DO_HARNESS)
    detalhes = tuple(problemas[caminho] for caminho in sorted(problemas))
    total = f"; {len(detalhes)} no total" if len(detalhes) > 1 else ""
    return Conferencia(ARQUIVOS_DO_HARNESS, False, f"{ARQUIVOS_DO_HARNESS}: FALHA: {detalhes[0]}{total}", detalhes)


def _sem_segredos(git: _Git, alterados: list[str], comum_: PerfilComum) -> Conferencia:
    """As linhas acrescentadas de cada arquivo alterado, contra a base ou contra a árvore vazia sem ela, sem os
    isentos, os apagados e os binários; o renomeado ou copiado compara com o arquivo de origem dele, e a origem
    isenta conta como vazia. Cada achado diz o arquivo, a linha e o nome do padrão, nunca o texto."""
    padroes = segredos.compilar(comum_.segredos)
    achados = []
    for caminho in alterados:
        if comum.padrao_que_casa(caminho, comum_.segredos_isentos):
            continue
        dados = git.dados_novos(caminho)
        if dados is None or binario(dados):
            continue
        origem = git.origem(caminho)
        # A origem isenta nunca foi conferida: o que sai dela compara com o vazio, não com o conteúdo antigo.
        antigo = None if comum.padrao_que_casa(origem, comum_.segredos_isentos) else git.da_base(origem)
        for numero, linha in linhas_acrescentadas(antigo, git.texto(dados)):
            nome = segredos.achar(linha, padroes)
            if nome is not None:
                achados.append(f"{caminho}:{numero}: segredo ({nome})")
    if not achados:
        return _ok(SEM_SEGREDOS)
    total = f"; {len(achados)} no total" if len(achados) > 1 else ""
    return Conferencia(SEM_SEGREDOS, False, f"{SEM_SEGREDOS}: FALHA: {achados[0]}{total}", tuple(achados))


def conferir(
    raiz: Path, perfil: Perfil | PerfilComum | PerfilDesenvolvimento, modo: str, ref: str | None = None,
    executar=subprocess.run,
) -> list[Conferencia]:
    """As conferências da trilha do perfil. Com o perfil de planejamento, na ordem `moldes-intocados`,
    `so-acrescimos`, `status-valido`, no modo `indice`, `status-pelo-harness` e, fora do modo `arvore`,
    `checar-aprovados`, com `caminhos.legenda` no perfil,
    `legenda-em-dia` e, com a linha do gerado no `CLAUDE.md` da versão nova, `gerados-em-dia`; por último, nas duas
    trilhas, o `sem-segredos`. Com o perfil de desenvolvimento, antes dele, o
    `arquivos-do-harness` no modo `arvore` e, nos outros, o `passagem-em-dia` e o `gerados-em-dia`; só com a parte
    comum, só o `sem-segredos`.

    Sem `HEAD`, as que comparam com a base passam, o `status-valido` confere a versão nova, e o `sem-segredos`
    compara com a árvore vazia. Lança ErroGit fora de um repositório, com o git indisponível e, no modo `base`, com
    ref inválida ou sem ancestral comum com o `HEAD`. `executar` é injetável para teste.
    """
    if modo not in MODOS:
        raise ValueError(f"modo desconhecido: {modo}")
    git = _Git(raiz, modo, ref, executar)
    alterados = git.alterados()
    conferencias = []
    if isinstance(perfil, Perfil):
        do_planejamento = alterados if git.tem_base else []
        conferencias += [
            _moldes_intocados(git, do_planejamento, perfil),
            _so_acrescimos(git, do_planejamento, perfil),
            _status_valido(git, perfil),
        ]
        if modo == INDICE:
            conferencias.insert(3, _status_pelo_harness(git, do_planejamento, perfil))
        if modo != ARVORE:
            conferencias.append(_checar_aprovados(git, do_planejamento, perfil))
            if perfil.caminhos.legenda:
                conferencias.append(_legenda_em_dia(git, perfil))
            gerados = _gerados_em_dia_do_planejamento(git, perfil, _puxa_o_gerado_do_planejamento(git))
            if gerados is not None:
                conferencias.append(gerados)
    elif isinstance(perfil, PerfilDesenvolvimento):
        if modo == ARVORE:
            conferencias.append(_arquivos_do_harness(git, perfil))
        else:
            conferencias.append(_passagem_em_dia(git, alterados, perfil))
            conferencias.append(_gerados_em_dia(git))
    conferencias.append(_sem_segredos(git, alterados, perfil if isinstance(perfil, PerfilComum) else perfil.comum))
    return conferencias


def formatar(conferencias: list[Conferencia], verbose: bool) -> str:
    """O resumo de cada conferência numa linha; com `verbose`, os detalhes abaixo, com dois espaços de recuo."""
    linhas = []
    for conferencia in conferencias:
        linhas.append(conferencia.resumo)
        if verbose:
            linhas += ["  " + detalhe for detalhe in conferencia.detalhes]
    return "".join(linha + "\n" for linha in linhas)
