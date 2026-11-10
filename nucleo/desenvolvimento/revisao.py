"""Revisão do bloco (spec 6d-bloco, §7): o gabarito da lente 1 e os comandos `revisao preparar`, `registrar` e
`dispensar`.

O gabarito é o `gabarito.md` do bloco, em inglês nos títulos: a parte genérica do núcleo, os itens de revisão do
perfil e as regras de arquitetura conferidas na revisão cujo "Onde vale" tem alguma área tocada pelo diff. O
`revisao preparar` o grava, junto com o diff do PR e a marca da revisão em andamento, ambos no diretório do git da
worktree, fora da árvore, e imprime os `args` do workflow da revisão. O `revisao registrar` grava as rodadas do
resultado do workflow no `revisao.md`, e o `revisao dispensar` tira um achado do `## Em aberto` pela palavra do dono.
"""
from __future__ import annotations

import dataclasses
import datetime
import json
import os
import posixpath
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import bloco
import campos
import comum
import fichas
import gerador
import papeis
import regras
import transicoes
from bloco import LaneViva, Recusa, Saida
from manifesto import Manifesto
from regras import Regra

AJUDA = """\
Prepara e registra a revisão do bloco da lane. Roda dentro da lane, com o bloco em `reviewing`; fora de lane, a recusa
é `fora de lane: rode dentro da lane do bloco`, e em outro estado,
`revisao preparar: <ID> está em <estado>; vale só em reviewing`.

- `harness.py revisao preparar [--orientacao "<texto>"]`:
  - a base é o `git merge-base HEAD refs/remotes/origin/<ramo_principal>`, sem fetch, como no diff do PR; sem essa
    ref, ou com o comando falhando, é o `base` do bloco;
  - grava o diff em `<git-dir da worktree>/harness-revisao/<base7>..<head7>.diff`, fora da árvore: a linha
    `commits <base7>..<head7>:`, um `<sha> <assunto>` por commit, o `git diff --stat` e o `git diff -U10` de
    `<base>...HEAD`;
  - as áreas tocadas são as da tabela das áreas da cópia da passagem com algum caminho que casa um arquivo mudado,
    pelos globs das regras geradas, e o bloco é sensível quando algum arquivo mudado casa um padrão de
    `[desenvolvimento.revisao] sensiveis`; nas duas contas, os arquivos sob `<blocos>/` e `<backlog>/`, os do próprio
    bloco e as fichas, não contam como mudados, e o diff fica como está;
  - grava, sem commit, o `<blocos>/<pasta>/gabarito.md`: a parte genérica, os `[desenvolvimento.revisao] itens` do
    perfil, na ordem, e as regras de arquitetura com `revisão` no "Como se confere" e alguma área tocada no "Onde
    vale", em ordem de número, com as áreas e a fonte;
  - a rodada é o número de títulos `## Rodada ` do `revisao.md` mais 1, e os achados do `## Em aberto` dele vão ao
    workflow;
  - grava a marca da revisão em andamento, `<git-dir da worktree>/harness-revisao/em-andamento`, com a hora e a
    rodada, que vale por 4 horas;
  - imprime
    `gabarito.md: <r> regras de <a> áreas e <i> itens do perfil; sensível: sim|não; rodada <n>; em aberto: <e>`
    (no singular com 1) e, na última linha, o JSON dos `args` do workflow: `bloco`, `rodada`, `base`, `head`, `diff`,
    `gabarito`, `spec`, `plano` (os caminhos absolutos), `sensivel`, `consertos_max` (3), `em_aberto` (os objetos com
    `id`, `eixo` (o da tabela da rodada em que o achado apareceu), `severidade`, `arquivo`, `linha`, `problema` e
    `prova`), `orientacao` (o texto com os espaços juntados, ou
    `null`) e `papeis` (o `model` e o `effort` de cada agente do workflow, com o verificador em `opus` no bloco
    sensível).

  Sem a cópia da passagem, a recusa é
  `revisao preparar: sem a cópia da passagem em <passagem>/; rode harness.py importar`; a regra de arquitetura que a
  cópia não confirma sai como `revisao preparar: <motivo>`, uma linha por motivo.
- `harness.py revisao registrar <arquivo>|-`, com o JSON do resultado do workflow no arquivo ou, com `-`, no stdin:
  - confere o esquema do resultado (o `bloco`, o `sensivel`, a `orientacao` e as `rodadas`, cada uma com a `rodada`,
    o `intervalo` e os `achados`), com as rodadas consecutivas a partir da seguinte às do `revisao.md`; o achado novo
    é `R<rodada>-<n>`, e o herdado, só na primeira rodada, é um ID do `## Em aberto`, `CONFIRMED` e com método
    `null`. A recusa é `revisao registrar: resultado inválido: <motivo>`, e o achado do `## Em aberto` que falta,
    `revisao registrar: resultado inválido: falta o achado em aberto <R-ID>`;
  - recusa a linha não vazia do `## Em aberto` que não é um achado na forma, como o item recuado ou numerado, a
    continuação de um item, o texto solto ou um bloco de código, com
    `revisao registrar: ## Em aberto: linha fora da forma: <linha>`, porque a seção é reescrita;
  - o achado pode trazer a chave opcional `absorvidos`, a lista de `{eixo, linha, problema, prova}` do achado do outro
    eixo que a fusão da primeira rodada guardou nele (o `eixo` é `padroes` ou `spec`, e difere do eixo do achado); a
    recusa de um item fora da forma traz o caminho `<achado>.absorvidos[<i>].<chave>`;
  - o achado pode trazer a chave opcional `sem_conserto`, um texto não vazio: o motivo do último conserto, que o
    workflow devolve quando o achado ficou aberto porque a lane não o resolve; fora disso, a recusa é
    `revisao registrar: resultado inválido: <achado>.sem_conserto fora da forma: <valor>`;
  - grava o `<blocos>/<pasta>/revisao.md`: o `# Revisão: <ID>`, o `## Em aberto` e o `## Dispensados` na primeira
    vez; as rodadas da execução logo abaixo do `## Dispensados`, a mais nova em cima, cada uma com a tabela dos
    achados, ou `Sem achados.`, com uma linha por absorvido abaixo da tabela,
    `- <R-ID>, absorvido (<eixo>): <problema> (<arquivo>:<linha do absorvido>)`, e, logo depois dela, uma linha por
    achado com o motivo, `- <R-ID>, sem conserto na lane: <motivo>`, e o placar,
    `Confirmados <c> · Plausíveis <p> · Refutados <r> de <v> verificados · `
    seguido de `Resolvidos <s> de <k> Críticos e Importantes · Menores <m>`, e a primeira com a
    `Orientação do dono: <texto>`, quando há; e o `## Em aberto` reescrito com os Críticos e Importantes confirmados
    que ficaram abertos, um por linha, `- <R-ID> (<severidade>): <problema> (<arquivo>:<linha>)`, com
    ` · prova: ` e o comando entre crases quando há prova;
  - faz o commit `chore(<ID>): revisão, rodada <n>`, ou `rodadas <n> a <m>`, com o `revisao.md` e o `gabarito.md`,
    e apaga a marca da revisão em andamento; com o commit recusado, o `revisao.md` volta ao último commit, e a marca
    fica;
  - imprime `rodadas <n> a <m>: <c> confirmados, <p> plausíveis, <r> refutados; <s> de <k> resolvidos; em aberto: <a>`,
    ou `rodada <n>: ...` com uma rodada só.

  Fora de `reviewing`, a recusa é `revisao registrar: <ID> está em <estado>; vale só em reviewing`.
- `harness.py revisao dispensar <R-ID> "<motivo>"`, só com a palavra do dono, que a guarda confirma:
  - vale em `reviewing`, com o achado no `## Em aberto`; as recusas são
    `revisao dispensar: <R-ID> não está em ## Em aberto`, `revisao dispensar: o motivo não pode ficar vazio` e, fora
    de `reviewing`, `revisao dispensar: <ID> está em <estado>; vale só em reviewing`;
  - tira a linha do `## Em aberto` e a acrescenta ao `## Dispensados`, sem a prova, com
    ` · dispensado por <dono> em <AAAA-MM-DD>: <motivo>`, o motivo com os espaços juntados;
  - faz o commit `chore(<ID>): revisão, dispensa <R-ID>`, só com o `revisao.md`, e imprime
    `<R-ID> dispensado; em aberto: <a>`.
"""

CONSERTOS_MAX = 3
SECAO_DISPENSADOS = "## Dispensados"
CONFERENCIA_DA_REVISAO = "revisão"
_TITULO_DA_RODADA = "## Rodada "
_GENERICO = (
    "1. The change does what the spec and the plan ask, and nothing else.",
    "2. Behavior is covered by tests at public seams; the tests would fail without the change.",
    "3. Errors at boundaries are handled; nothing is swallowed silently.",
    "4. No secret, no debug leftover, no commented-out code.",
    "5. The area rules below are followed.",
)
_NAO_E_ACHADO = ("Not a finding: style the linter checks; a problem that existed before this block (report it as "
                 "`pre-existing`).")
_SEM_ITENS = "None."
# A linha do `## Em aberto`: o `(<arquivo>:<linha>)` é o dos últimos parênteses, antes do fim ou do ` · prova:`.
_RE_EM_ABERTO = re.compile(r"- (R[0-9]+-[0-9]+) \(([a-z]+)\): (.+) \(([^()]+):([0-9]+)\)(?: · prova: `(.*)`)?")
_RE_TITULO = re.compile(r"#{1,6} ")
_RE_QUEBRA = re.compile(r"\r\n|\r|\n")
_SEM_CONVERSAO = ["--no-ext-diff", "--no-textconv", "--no-color"]


@dataclass(frozen=True)
class Aberto:
    """Um achado do `## Em aberto`: Crítico ou Importante confirmado que ficou aberto."""

    id: str
    severidade: str
    problema: str
    arquivo: str
    linha: int
    prova: str | None


def _uma_linha(texto: str) -> str:
    """O texto com cada quebra de linha trocada por um espaço."""
    return _RE_QUEBRA.sub(" ", texto)


def ler_em_aberto(texto: str) -> list[Aberto]:
    """Os achados da seção `## Em aberto` do `revisao.md`, fora dos blocos de código, na ordem: as linhas
    `- <ID> (<severidade>): <problema> (<arquivo>:<linha>)`, com ` · prova: `<comando>`` quando há prova. O
    `arquivo:linha` sai dos últimos parênteses, e o problema fica inteiro."""
    abertos: list[Aberto] = []
    na_secao = False
    for _, linha in campos.linhas_fora_de_blocos(texto):
        if _RE_TITULO.match(linha):
            if na_secao:
                break
            na_secao = linha.rstrip() == transicoes.SECAO_EM_ABERTO
            continue
        achado = _RE_EM_ABERTO.fullmatch(linha.rstrip()) if na_secao else None
        if achado is not None:
            abertos.append(Aberto(achado.group(1), achado.group(2), achado.group(3), achado.group(4),
                                  int(achado.group(5)), achado.group(6)))
    return abertos


def linha_em_aberto(item: Aberto) -> str:
    """A linha do achado no `## Em aberto`, com as quebras de linha dos textos trocadas por um espaço."""
    linha = f"- {item.id} ({item.severidade}): {_uma_linha(item.problema)} ({_uma_linha(item.arquivo)}:{item.linha})"
    if item.prova:
        linha += f" · prova: `{_uma_linha(item.prova)}`"
    return linha


def rodadas_registradas(texto: str) -> int:
    """Os títulos `## Rodada ` do `revisao.md`, fora dos blocos de código."""
    return sum(1 for _, linha in campos.linhas_fora_de_blocos(texto) if linha.startswith(_TITULO_DA_RODADA))


def _git(raiz: Path, argumentos: list[str], executar) -> bytes:
    """O stdout do git; a falha recusa com `git <subcomando> falhou: <motivo>`."""
    feito = bloco.git(raiz, argumentos, executar)
    if feito.returncode != 0:
        raise Recusa(f"git {argumentos[0]} falhou: {comum.motivo_do_git(feito, argumentos[0])}")
    return feito.stdout


def base_da_revisao(raiz: Path, perfil, lane: LaneViva, executar=subprocess.run) -> str:
    """O `merge-base` do HEAD com o `origin/<ramo_principal>`, sem fetch, como no diff do PR; sem essa ref, ou com o
    comando falhando, o `base` do bloco."""
    feito = bloco.git(raiz, ["merge-base", "HEAD", f"refs/remotes/origin/{perfil.ramo_principal}"], executar)
    base = feito.stdout.decode("utf-8", errors="replace").strip()
    return base if feito.returncode == 0 and base else lane.bloco.base


def areas_tocadas(m: Manifesto, mudados: list[str]) -> tuple[str, ...]:
    """As áreas da tabela com algum caminho que casa um arquivo mudado, pelos globs das regras geradas, na ordem da
    tabela e sem repetir."""
    tocadas: list[str] = []
    for area in m.areas:
        globs = tuple(gerador.globs_da_area(area))
        if area.area not in tocadas and any(comum.padrao_que_casa(caminho, globs) for caminho in mudados):
            tocadas.append(area.area)
    return tuple(tocadas)


def do_trabalho(perfil, mudados: list[str]) -> list[str]:
    """Os mudados sem os arquivos sob `<blocos>/` e `<backlog>/`, os do próprio bloco e as fichas, que não contam nas
    áreas tocadas nem no sensível (spec 6d-bloco, §7.1)."""
    pastas = tuple(f"{posixpath.normpath(pasta)}/" for pasta in (perfil.caminhos.blocos, perfil.caminhos.backlog))
    return [caminho for caminho in mudados if not caminho.startswith(pastas)]


def sensivel(perfil, mudados: list[str]) -> bool:
    """Se algum arquivo mudado casa um padrão de `[desenvolvimento.revisao] sensiveis`."""
    return any(comum.padrao_que_casa(caminho, perfil.revisao.sensiveis) for caminho in mudados)


def gabarito(id_: str, rodada: int, sensivel_: bool, areas: tuple[str, ...], itens: tuple[str, ...],
             regras_: tuple[Regra, ...]) -> str:
    """O texto do `gabarito.md` (spec 6d-bloco, Anexo A.4): o cabeçalho, a parte genérica, os itens do perfil e as
    regras de arquitetura, com `None.` na seção sem nada."""
    linhas = [
        f"# Review checklist: {id_} (round {rodada})", "",
        f"Sensitive block: {'yes' if sensivel_ else 'no'}. Areas touched: {', '.join(areas) if areas else 'none'}.",
        "", "## Generic", *_GENERICO, "", _NAO_E_ACHADO, "", "## Profile items",
    ]
    linhas += [f"{numero}. {_uma_linha(item)}" for numero, item in enumerate(itens, start=1)] or [_SEM_ITENS]
    linhas += ["", "## Architecture rules (review)"]
    for regra in regras_:
        linhas.append(f"- **{regra.id}** ({', '.join(regra.areas)}): {regra.texto}")
        linhas.append(f"  Source: `{regra.fonte.arquivo}:{regra.fonte.linhas[0]}`")
    if not regras_:
        linhas.append(_SEM_ITENS)
    return "\n".join(linhas) + "\n"


def _contagem(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _regras_da_copia(raiz: Path, perfil) -> tuple[Manifesto, tuple[Regra, ...]]:
    """O manifesto da cópia da passagem e as regras de arquitetura dela; sem a cópia, ou com regra que ela não
    confirma, a recusa."""
    pasta = perfil.caminhos.passagem
    copia = fichas.ler_manifesto(Path(raiz), perfil)
    if copia is None:
        raise Recusa(f"revisao preparar: sem a cópia da passagem em {pasta}/; rode harness.py importar")
    try:
        return copia, regras.da_passagem(copia, comum.leitor_do_disco(Path(raiz)), pasta)
    except regras.RegrasRecusadas as erro:
        raise Recusa("\n".join(f"revisao preparar: {motivo}" for motivo in erro.motivos)) from None


def _diff(raiz: Path, base: str, head: str, executar) -> bytes:
    """O diff da revisão: a linha dos commits, um `<sha> <assunto>` por commit, uma linha em branco, o `--stat`, outra
    em branco e o `git diff -U10` de `<base>...HEAD`."""
    commits = _git(raiz, ["log", *_SEM_CONVERSAO, "--reverse", "--format=%h %s", f"{base}..HEAD"], executar)
    estatistica = _git(raiz, ["diff", *_SEM_CONVERSAO, "--stat", f"{base}...HEAD"], executar)
    diferenca = _git(raiz, ["diff", *_SEM_CONVERSAO, "-U10", f"{base}...HEAD"], executar)
    cabeca = f"commits {base[:7]}..{head[:7]}:\n".encode("utf-8")
    return cabeca + commits + b"\n" + estatistica + b"\n" + diferenca


def eixo_na_tabela(texto: str, id_: str) -> str:
    """O eixo da linha `| <id_> | <eixo> | ...` de uma tabela de rodada do `revisao.md`; sem a linha, `spec`."""
    for linha in _RE_QUEBRA.split(texto):
        celulas = [celula.strip() for celula in linha.split("|")]
        if len(celulas) > 3 and celulas[0] == "" and celulas[1] == id_:
            return celulas[2]
    return "spec"


def _para_json(item: Aberto, eixo: str) -> dict:
    return {"id": item.id, "eixo": eixo, "severidade": item.severidade, "arquivo": item.arquivo, "linha": item.linha,
            "problema": item.problema, "prova": item.prova}


def preparar(raiz: Path, perfil, orientacao: str | None = None, executar=subprocess.run,
             agora=datetime.datetime.now) -> Saida:
    """Em `reviewing`, grava o gabarito, o diff e a marca da revisão em andamento e devolve a linha do resumo e o JSON
    dos `args` do workflow (spec 6d-bloco, §7.1)."""
    lane = transicoes.da_lane(raiz, perfil)
    if lane.bloco.estado != "reviewing":
        raise Recusa(f"revisao preparar: {lane.bloco.id} está em {lane.bloco.estado}; vale só em reviewing")
    copia, todas = _regras_da_copia(raiz, perfil)
    absoluta = Path(os.path.abspath(raiz))
    pasta = transicoes.pasta_do_bloco(perfil, lane.bloco)
    revisao_md = absoluta / pasta / bloco.ARQUIVO_DA_REVISAO
    texto = comum.ler_texto(revisao_md) if revisao_md.is_file() else ""
    rodada = rodadas_registradas(texto) + 1
    em_aberto = ler_em_aberto(texto)
    base = base_da_revisao(raiz, perfil, lane, executar)
    head = _git(raiz, ["rev-parse", "HEAD"], executar).decode("utf-8", errors="replace").strip()
    nomes = _git(raiz, ["diff", *_SEM_CONVERSAO, "--name-only", "-z", f"{base}...HEAD"], executar)
    mudados = do_trabalho(perfil, [nome for nome in nomes.decode("utf-8", errors="replace").split("\0") if nome])
    areas = areas_tocadas(copia, mudados)
    sensivel_ = sensivel(perfil, mudados)
    da_revisao = tuple(regra for regra in todas if CONFERENCIA_DA_REVISAO in regra.conferencia
                       and any(area in areas for area in regra.areas))
    papeis_ = papeis.para_o_workflow(perfil, sensivel_)
    diff = Path(os.path.abspath(bloco.pasta_da_revisao(raiz))) / f"{base[:7]}..{head[:7]}.diff"
    dados_do_diff = _diff(raiz, base, head, executar)
    gabarito_md = absoluta / pasta / bloco.ARQUIVO_DO_GABARITO
    comum.escrever_texto(gabarito_md, gabarito(lane.bloco.id, rodada, sensivel_, areas, perfil.revisao.itens,
                                                da_revisao))
    diff.parent.mkdir(parents=True, exist_ok=True)
    diff.write_bytes(dados_do_diff)
    bloco.gravar_marca_da_revisao(raiz, agora(), rodada)
    orientacao = " ".join((orientacao or "").split()) or None
    args = {
        "bloco": lane.bloco.id, "rodada": rodada, "base": base, "head": head, "diff": str(diff),
        "gabarito": str(gabarito_md), "spec": str(absoluta / pasta / bloco.ARQUIVO_DA_SPEC),
        "plano": str(absoluta / pasta / transicoes.PLANO), "sensivel": sensivel_, "consertos_max": CONSERTOS_MAX,
        "em_aberto": [_para_json(item, eixo_na_tabela(texto, item.id)) for item in em_aberto], "orientacao": orientacao, "papeis": papeis_,
    }
    resumo = (f"{bloco.ARQUIVO_DO_GABARITO}: {_contagem(len(da_revisao), 'regra', 'regras')} de "
              f"{_contagem(len(areas), 'área', 'áreas')} e "
              f"{_contagem(len(perfil.revisao.itens), 'item do perfil', 'itens do perfil')}; "
              f"sensível: {'sim' if sensivel_ else 'não'}; rodada {rodada}; em aberto: {len(em_aberto)}")
    return Saida((resumo, json.dumps(args, ensure_ascii=False)))


NOMES_DA_SEVERIDADE = {"critical": "Crítico", "important": "Importante", "minor": "Menor"}
_EIXOS = ("padroes", "spec", "conserto")
_VEREDITOS = ("CONFIRMED", "PLAUSIBLE", "REFUTED")
_METODOS = ("prova", "leitura")
# A situação final de cada veredito; o `None` é o do `minor`.
_SITUACOES_DO_VEREDITO = {
    None: ("registrado",), "CONFIRMED": ("corrigido", "aberto", "recusado"), "PLAUSIBLE": ("registrado",),
    "REFUTED": ("descartado",),
}
_RE_SITUACAO = re.compile(r"(corrigido) [0-9a-f]{7,40}|(aberto)|(recusado): \S.*|(registrado)|(descartado)", re.S)
_RE_INTERVALO = re.compile(r"[0-9a-f]{7,40}\.\.[0-9a-f]{7,40}")
_RE_ID = re.compile(r"R[1-9][0-9]*-[1-9][0-9]*")
_CABECA_DA_TABELA = ("| # | Eixo | Severidade | Achado | Veredito | Método | Situação |",
                     "|---|---|---|---|---|---|---|")
_SEM_ACHADOS = "Sem achados."


@dataclass(frozen=True)
class Absorvido:
    """O achado do outro eixo que a fusão da primeira rodada guardou dentro do que ficou (spec 6d-repositorio, §10)."""
    eixo: str
    linha: int
    problema: str
    prova: str | None


@dataclass(frozen=True)
class _Achado:
    id: str
    eixo: str
    severidade: str
    arquivo: str
    linha: int
    problema: str
    prova: str | None
    veredito: str | None
    metodo: str | None
    situacao: str
    absorvidos: tuple[Absorvido, ...] = ()
    sem_conserto: str | None = None


@dataclass(frozen=True)
class _Rodada:
    numero: int
    intervalo: str
    achados: tuple[_Achado, ...]


def _invalido(motivo: str) -> Recusa:
    return Recusa(f"revisao registrar: resultado inválido: {motivo}")


def _fora_da_forma(caminho: str, valor) -> Recusa:
    """A recusa do campo com o valor em JSON, numa linha: `"4"` é o texto, e `4`, o número."""
    return _invalido(f"{caminho} fora da forma: {json.dumps(valor, ensure_ascii=False)}")


def _campo(objeto: dict, caminho: str, chave: str, aceito) -> object:
    """O valor da chave, conferido pelo `aceito(valor)`; sem a chave, `falta <campo>`, e fora dela, `fora da forma`."""
    campo = f"{caminho}.{chave}" if caminho else chave
    if chave not in objeto:
        raise _invalido(f"falta {campo}")
    valor = objeto[chave]
    if not aceito(valor):
        raise _fora_da_forma(campo, valor)
    return valor


def _texto(valor) -> bool:
    return isinstance(valor, str) and bool(valor.strip())


def _inteiro(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool) and valor >= 1


def _objeto(valor, caminho: str) -> dict:
    if not isinstance(valor, dict):
        raise _fora_da_forma(caminho, valor)
    return valor


def _absorvidos(objeto: dict, caminho: str, eixo: str) -> tuple[Absorvido, ...]:
    """Os absorvidos do achado, chave opcional: cada item tem o `eixo` (`padroes` ou `spec`, diferente do achado), a
    `linha`, o `problema` e a `prova`; fora disso, a recusa traz o caminho `<achado>.absorvidos[<i>].<chave>`."""
    if "absorvidos" not in objeto:
        return ()
    lista = _campo(objeto, caminho, "absorvidos", lambda v: isinstance(v, list))
    itens = []
    for posicao, valor in enumerate(lista):
        local = f"{caminho}.absorvidos[{posicao}]"
        item = _objeto(valor, local)
        outro = _campo(item, local, "eixo", lambda v: v in ("padroes", "spec") and v != eixo)
        linha = _campo(item, local, "linha", _inteiro)
        problema = _campo(item, local, "problema", _texto)
        prova = _campo(item, local, "prova", lambda v: v is None or _texto(v))
        itens.append(Absorvido(outro, linha, problema, prova))
    return tuple(itens)


def _achado(valor, caminho: str, rodada: int, primeira: bool, herdaveis: set[str]) -> _Achado:
    """O achado conferido: o ID novo é `R<rodada>-<n>`, e o herdado, só na primeira rodada da execução, é um ID do
    `## Em aberto`, `CONFIRMED` e com método `null`; a situação acompanha o veredito (spec 6d-bloco, Anexo A.6)."""
    objeto = _objeto(valor, caminho)
    id_ = _campo(objeto, caminho, "id", lambda v: isinstance(v, str) and _RE_ID.fullmatch(v) is not None)
    eixo = _campo(objeto, caminho, "eixo", lambda v: v in _EIXOS)
    severidade = _campo(objeto, caminho, "severidade", lambda v: v in NOMES_DA_SEVERIDADE)
    arquivo = _campo(objeto, caminho, "arquivo", _texto)
    linha = _campo(objeto, caminho, "linha", _inteiro)
    problema = _campo(objeto, caminho, "problema", _texto)
    prova = _campo(objeto, caminho, "prova", lambda v: v is None or _texto(v))
    veredito = _campo(objeto, caminho, "veredito", lambda v: v is None or v in _VEREDITOS)
    metodo = _campo(objeto, caminho, "metodo", lambda v: v is None or v in _METODOS)
    situacao = _campo(objeto, caminho, "situacao", lambda v: isinstance(v, str) and _RE_SITUACAO.fullmatch(v))
    herdado = not id_.startswith(f"R{rodada}-")
    if herdado and not (primeira and id_ in herdaveis):
        raise _fora_da_forma(f"{caminho}.id", id_)
    if herdado:
        aceitos = (severidade != "minor", veredito == "CONFIRMED", metodo is None)
    elif severidade == "minor":
        aceitos = (True, veredito is None, metodo is None)
    else:
        aceitos = (True, veredito is not None, metodo is not None)
    for chave, valor, aceito in zip(("severidade", "veredito", "metodo"), (severidade, veredito, metodo), aceitos):
        if not aceito:
            raise _fora_da_forma(f"{caminho}.{chave}", valor)
    tipo = next(grupo for grupo in _RE_SITUACAO.fullmatch(situacao).groups() if grupo)
    if tipo not in _SITUACOES_DO_VEREDITO[veredito]:
        nome = "null" if veredito is None else veredito
        raise _invalido(f"{id_}: situação {_uma_linha(situacao)} não cabe no veredito {nome}")
    sem_conserto = _campo(objeto, caminho, "sem_conserto", _texto) if "sem_conserto" in objeto else None
    return _Achado(id_, eixo, severidade, arquivo, linha, problema, prova, veredito, metodo, situacao,
                   _absorvidos(objeto, caminho, eixo), sem_conserto)


def _resultado(texto: str, id_: str, seguinte: int, abertos: list[Aberto]) -> tuple[str | None, list[_Rodada]]:
    """A orientação e as rodadas do resultado do workflow, conferido pelo esquema do Anexo A.6; as rodadas são
    consecutivas a partir da `seguinte`, e todo achado do `## Em aberto` vem na primeira delas."""
    try:
        dados = json.loads(texto)
    except ValueError as erro:
        raise _invalido(f"JSON ilegível: {_uma_linha(str(erro))}") from None
    if not isinstance(dados, dict):
        raise _invalido("falta bloco")
    bloco_ = _campo(dados, "", "bloco", lambda v: isinstance(v, str))
    if bloco_ != id_:
        raise _invalido(f"o bloco é {_uma_linha(bloco_)}, e a lane é {id_}")
    _campo(dados, "", "sensivel", lambda v: isinstance(v, bool))
    orientacao = _campo(dados, "", "orientacao", lambda v: v is None or isinstance(v, str))
    lista = _campo(dados, "", "rodadas", lambda v: isinstance(v, list) and bool(v))
    herdaveis = {item.id for item in abertos}
    vistos: set[str] = set()
    rodadas: list[_Rodada] = []
    for indice, valor in enumerate(lista):
        caminho = f"rodadas[{indice}]"
        objeto = _objeto(valor, caminho)
        numero = _campo(objeto, caminho, "rodada", _inteiro)
        if numero != seguinte + indice:
            raise _invalido(f"{caminho}.rodada é {numero}; a rodada seguinte é {seguinte + indice}")
        intervalo = _campo(objeto, caminho, "intervalo",
                           lambda v: isinstance(v, str) and _RE_INTERVALO.fullmatch(v) is not None)
        itens = _campo(objeto, caminho, "achados", lambda v: isinstance(v, list))
        achados = []
        for posicao, item in enumerate(itens):
            achado = _achado(item, f"{caminho}.achados[{posicao}]", numero, indice == 0, herdaveis)
            if achado.id in vistos:
                raise _fora_da_forma(f"{caminho}.achados[{posicao}].id", achado.id)
            vistos.add(achado.id)
            achados.append(achado)
        rodadas.append(_Rodada(numero, intervalo, tuple(achados)))
    for item in abertos:
        if item.id not in vistos:
            raise _invalido(f"falta o achado em aberto {item.id}")
    orientacao = " ".join((orientacao or "").split()) or None
    return orientacao, rodadas


def _placar(rodada: _Rodada) -> tuple[int, int, int, int, int, int]:
    """Os confirmados, os plausíveis e os refutados entre os verificados da rodada, os resolvidos, os Críticos e
    Importantes confirmados, com os herdados, e os menores."""
    verificados = [achado.veredito for achado in rodada.achados if achado.metodo is not None]
    graves = [achado for achado in rodada.achados
              if achado.severidade != "minor" and achado.veredito == "CONFIRMED"]
    resolvidos = sum(1 for achado in graves if achado.situacao.startswith(("corrigido ", "recusado: ")))
    menores = sum(1 for achado in rodada.achados if achado.severidade == "minor")
    return (verificados.count("CONFIRMED"), verificados.count("PLAUSIBLE"), verificados.count("REFUTED"), resolvidos,
            len(graves), menores)


def _celula(texto: str) -> str:
    """O texto numa célula da tabela: as quebras de linha viram um espaço, e o `|` vira `\\|`."""
    return _uma_linha(texto).replace("|", "\\|")


def _linha_da_tabela(achado: _Achado) -> str:
    situacao = achado.situacao
    if situacao.startswith("corrigido "):
        situacao = f"corrigido `{situacao.split(' ', 1)[1]}`"
    celulas = (achado.id, achado.eixo, NOMES_DA_SEVERIDADE[achado.severidade],
               f"{_celula(achado.problema)} (`{_celula(achado.arquivo)}:{achado.linha}`)",
               achado.veredito or "—", achado.metodo or "—", _celula(situacao))
    return "| " + " | ".join(celulas) + " |"


def _linhas_da_rodada(rodada: _Rodada, data: str, orientacao: str | None) -> list[str]:
    """O título, a orientação do dono, quando há, a tabela dos achados, com os absorvidos e os motivos do
    `sem_conserto` abaixo dela, ou `Sem achados.` e o placar."""
    c, p, r, s, k, m = _placar(rodada)
    linhas = [f"{_TITULO_DA_RODADA}{rodada.numero} · `{rodada.intervalo}` · {data}", ""]
    if orientacao:
        linhas += [f"Orientação do dono: {orientacao}", ""]
    if rodada.achados:
        linhas += [*_CABECA_DA_TABELA, *(_linha_da_tabela(achado) for achado in rodada.achados)]
        absorvidos = [f"- {achado.id}, absorvido ({item.eixo}): {_uma_linha(item.problema)} "
                      f"(`{_uma_linha(achado.arquivo)}:{item.linha}`)"
                      for achado in rodada.achados for item in achado.absorvidos]
        sem_conserto = [f"- {achado.id}, sem conserto na lane: {_uma_linha(achado.sem_conserto)}"
                        for achado in rodada.achados if achado.sem_conserto]
        if absorvidos or sem_conserto:
            linhas += ["", *absorvidos, *sem_conserto]
    else:
        linhas.append(_SEM_ACHADOS)
    linhas += ["", f"Confirmados {c} · Plausíveis {p} · Refutados {r} de {c + p + r} verificados · Resolvidos {s} de "
                   f"{k} Críticos e Importantes · Menores {m}"]
    return linhas


def _linhas_do_texto(texto: str) -> list[str]:
    """As linhas do texto, sem o `\\r` do fim, numeradas como as do `campos.linhas_fora_de_blocos`."""
    linhas = texto.split("\n")
    if linhas[-1] == "":
        linhas.pop()
    return [linha.rstrip("\r") for linha in linhas]


def _secao(texto: str, titulo: str) -> tuple[int, int] | None:
    """O número da linha do título da seção, a partir de 1, e o da linha do próximo título fora dos blocos de código
    (o total de linhas mais 1, sem ele); sem a seção, None."""
    titulos = [(numero, linha) for numero, linha in campos.linhas_fora_de_blocos(texto) if _RE_TITULO.match(linha)]
    for posicao, (numero, linha) in enumerate(titulos):
        if linha.rstrip() == titulo:
            fim = titulos[posicao + 1][0] if posicao + 1 < len(titulos) else len(_linhas_do_texto(texto)) + 1
            return numero, fim
    return None


def _conferir_em_aberto(texto: str, comando: str = "registrar") -> None:
    """Recusa a primeira linha não vazia do `## Em aberto` que o `ler_em_aberto` não lê como achado: o item recuado ou
    numerado, a continuação de um item, o texto solto e as linhas de um bloco de código, cerca inclusive. O `comando`
    (o `registrar` ou o `dispensar`) reescreve a seção e a apagaria."""
    secao = _secao(texto, transicoes.SECAO_EM_ABERTO)
    if secao is None:
        return
    for linha in _linhas_do_texto(texto)[secao[0]:secao[1] - 1]:
        if linha.strip() and _RE_EM_ABERTO.fullmatch(linha.rstrip()) is None:
            raise Recusa(f"revisao {comando}: {transicoes.SECAO_EM_ABERTO}: linha fora da forma: {linha.strip()}")


def _novo_revisao_md(texto: str, id_: str, em_aberto: list[str], rodadas: list[str]) -> str:
    """O `revisao.md` com o `## Em aberto` reescrito e as rodadas novas logo abaixo do `## Dispensados`; sem o arquivo,
    o cabeçalho, o `## Em aberto` e o `## Dispensados`. Sem uma das seções, a recusa."""
    texto = texto or f"# Revisão: {id_}\n\n{transicoes.SECAO_EM_ABERTO}\n\n{SECAO_DISPENSADOS}\n"
    secoes = {}
    for titulo in (transicoes.SECAO_EM_ABERTO, SECAO_DISPENSADOS):
        secao = _secao(texto, titulo)
        if secao is None:
            raise Recusa(f"revisao registrar: {bloco.ARQUIVO_DA_REVISAO} sem a seção {titulo}")
        secoes[titulo] = secao
    linhas = _linhas_do_texto(texto)
    trocas = {}
    inicio, fim = secoes[transicoes.SECAO_EM_ABERTO]
    trocas[inicio] = (fim, ["", *em_aberto, ""] if em_aberto else [""])
    inicio, fim = secoes[SECAO_DISPENSADOS]
    corpo = linhas[inicio:fim - 1]
    while corpo and not corpo[-1].strip():
        corpo.pop()
    trocas[inicio] = (fim, [*corpo, "", *rodadas, *([""] if fim <= len(linhas) else [])])
    for inicio in sorted(trocas, reverse=True):
        fim, novas = trocas[inicio]
        linhas[inicio:fim - 1] = novas
    return "\n".join(linhas) + "\n"


def _intervalo_de_rodadas(rodadas: list[_Rodada]) -> str:
    primeira, ultima = rodadas[0].numero, rodadas[-1].numero
    return f"rodada {primeira}" if primeira == ultima else f"rodadas {primeira} a {ultima}"


def registrar(raiz: Path, perfil, texto: str, executar=subprocess.run, agora=datetime.datetime.now) -> Saida:
    """Em `reviewing`, confere o resultado do workflow, grava as rodadas da execução no `revisao.md`, reescreve o
    `## Em aberto`, faz o commit com o `gabarito.md` e apaga a marca da revisão em andamento (spec 6d-bloco, §7.3)."""
    lane = transicoes.da_lane(raiz, perfil)
    id_ = lane.bloco.id
    if lane.bloco.estado != "reviewing":
        raise Recusa(f"revisao registrar: {id_} está em {lane.bloco.estado}; vale só em reviewing")
    pasta = transicoes.pasta_do_bloco(perfil, lane.bloco)
    revisao_md = f"{pasta}/{bloco.ARQUIVO_DA_REVISAO}"
    arquivo = Path(raiz) / revisao_md
    atual = comum.ler_texto(arquivo) if arquivo.is_file() else ""
    _conferir_em_aberto(atual)
    orientacao, rodadas = _resultado(texto, id_, rodadas_registradas(atual) + 1, ler_em_aberto(atual))
    data = agora().strftime("%Y-%m-%d")
    da_execucao = [_linhas_da_rodada(rodada, data, orientacao if posicao == 0 else None)
                   for posicao, rodada in enumerate(rodadas)]
    novas = [linha for linhas in reversed(da_execucao) for linha in ["", *linhas]][1:]
    abertos = [Aberto(achado.id, achado.severidade, achado.problema, achado.arquivo, achado.linha, achado.prova)
               for rodada in rodadas for achado in rodada.achados
               if achado.severidade != "minor" and achado.veredito == "CONFIRMED" and achado.situacao == "aberto"]
    comum.escrever_texto(arquivo, _novo_revisao_md(atual, id_, [linha_em_aberto(item) for item in abertos], novas))
    intervalo = _intervalo_de_rodadas(rodadas)
    bloco.commitar(raiz, [revisao_md, f"{pasta}/{bloco.ARQUIVO_DO_GABARITO}"], f"chore({id_}): revisão, {intervalo}",
                   [revisao_md], executar)
    bloco.apagar_marca_da_revisao(raiz)
    c, p, r, s, k, _ = (sum(coluna) for coluna in zip(*(_placar(rodada) for rodada in rodadas)))
    return Saida((f"{intervalo}: {c} confirmados, {p} plausíveis, {r} refutados; {s} de {k} resolvidos; "
                  f"em aberto: {len(abertos)}",))


def _sem_o_achado(texto: str, id_: str, linha_nova: str) -> str:
    """O `revisao.md` sem o achado no `## Em aberto` e com `linha_nova` no fim do `## Dispensados`; sem uma das
    seções, a recusa."""
    secoes = {}
    for titulo in (transicoes.SECAO_EM_ABERTO, SECAO_DISPENSADOS):
        secao = _secao(texto, titulo)
        if secao is None:
            raise Recusa(f"revisao dispensar: {bloco.ARQUIVO_DA_REVISAO} sem a seção {titulo}")
        secoes[titulo] = secao
    linhas = _linhas_do_texto(texto)
    resto = [linha_em_aberto(item) for item in ler_em_aberto(texto) if item.id != id_]
    inicio_a, fim_a = secoes[transicoes.SECAO_EM_ABERTO]
    inicio_d, fim_d = secoes[SECAO_DISPENSADOS]
    corpo = linhas[inicio_d:fim_d - 1]
    while corpo and not corpo[-1].strip():
        corpo.pop()
    dispensados = [*(corpo or [""]), linha_nova, *([""] if fim_d <= len(linhas) else [])]
    for inicio, fim, novas in sorted(((inicio_a, fim_a, ["", *resto, ""] if resto else [""]),
                                      (inicio_d, fim_d, dispensados)), reverse=True):
        linhas[inicio:fim - 1] = novas
    return "\n".join(linhas) + "\n"


def dispensar(raiz: Path, perfil, id_achado: str, motivo: str, executar=subprocess.run,
              agora=datetime.datetime.now) -> Saida:
    """Em `reviewing`, tira o achado do `## Em aberto` e o põe no `## Dispensados`, com o dono, a data e o motivo, e faz
    o commit só com o `revisao.md` (spec 6d-bloco, §7.5)."""
    lane = transicoes.da_lane(raiz, perfil)
    id_ = lane.bloco.id
    if lane.bloco.estado != "reviewing":
        raise Recusa(f"revisao dispensar: {id_} está em {lane.bloco.estado}; vale só em reviewing")
    motivo = " ".join(motivo.split())
    if not motivo:
        raise Recusa("revisao dispensar: o motivo não pode ficar vazio")
    revisao_md = f"{transicoes.pasta_do_bloco(perfil, lane.bloco)}/{bloco.ARQUIVO_DA_REVISAO}"
    arquivo = Path(raiz) / revisao_md
    atual = comum.ler_texto(arquivo) if arquivo.is_file() else ""
    _conferir_em_aberto(atual, "dispensar")
    abertos = ler_em_aberto(atual)
    achado = next((item for item in abertos if item.id == id_achado), None)
    if achado is None:
        raise Recusa(f"revisao dispensar: {id_achado} não está em {transicoes.SECAO_EM_ABERTO}")
    data = agora().strftime("%Y-%m-%d")
    linha = linha_em_aberto(dataclasses.replace(achado, prova=None))
    linha += f" · dispensado por {perfil.dono.nome} em {data}: {motivo}"
    comum.escrever_texto(arquivo, _sem_o_achado(atual, id_achado, linha))
    bloco.commitar(raiz, [revisao_md], f"chore({id_}): revisão, dispensa {id_achado}", [revisao_md], executar)
    return Saida((f"{id_achado} dispensado; em aberto: {len(abertos) - 1}",))
