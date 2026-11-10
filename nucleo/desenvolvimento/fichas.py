"""Fichas do desenvolvimento (spec 6c, §9.1 a §9.3): as da passagem e as do backlog do código, os campos, os IDs citados, a forma e o estado.

As FICHA são os IDs `FICHA-NN` do manifesto da cópia da passagem, com o texto do trecho no arquivo da cópia; as do
código são os arquivos `<prefixo>-NN-<slug>.md` da pasta `caminhos.backlog`, uma por arquivo. Os campos saem pelo
leitor comum (`campos.itens_do_campo`), com os nomes fixos de `CAMPOS_DA_FICHA`.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import bloco
import campos
import comum
import manifesto
from bloco import EstadoDoBloco, LaneViva, Recusa
from manifesto import Manifesto

AJUDA = """\
Lista as fichas da passagem e do backlog do código, uma por linha, com o estado de cada uma; `fichas nova` cria a
ficha do código seguinte.

- De onde vêm: as `FICHA-NN` do `ids` do manifesto da cópia da passagem (`caminhos.passagem`), com o texto do trecho
  no arquivo da cópia, e as fichas do código, uma por arquivo `<prefixo>-NN-<slug>.md` em `caminhos.backlog`. Saem as
  FICHA e depois as do prefixo, cada grupo em ordem de número, com o ID alinhado à esquerda.
- As fichas do código vêm de três fontes, sem repetir o nome do arquivo, nesta ordem: a árvore; a árvore principal,
  quando o comando roda numa lane, com as fichas ainda sem commit; e o `origin/<ramo_principal>`, sem fetch, com as
  que já entraram nele e ainda faltam numa árvore atrás dele.
- O estado vem dos blocos: as lanes vivas, as worktrees do `git worktree list` dentro de `lane.pasta` com um bloco
  cujo `ramo` é a branch delas, e os blocos do `origin/<ramo_principal>`, sem fetch; sem essa ref, como na montagem,
  nenhum.
- As situações, na primeira que vale:
  - `saiu da passagem/vN`: a FICHA de lane viva que o manifesto da cópia não tem mais;
  - `em bloco (<estado>)`: com lane viva;
  - `fechada`: com o bloco em `closing` no ramo principal e sem lane;
  - `bloco sem lane (<estado>)`: com o bloco no ramo principal noutro estado, que só um merge feito fora do harness
    produz;
  - `na lane <ID>; entra no <ramo_principal> com o PR dela`: a ficha do código que só existe na lane do bloco `<ID>`;
  - `fora da forma (<problema>)`: a ficha do código aberta que ainda não tem a forma que o `lane abrir` pede, como a
    criada pelo `fichas nova` e ainda por preencher;
  - `pronta`: aberta, com cada FICHA e ficha do código do Depende fechada e cada PEND fora das pendências do manifesto;
    a ficha do código com `Prioridade: urgente` e pronta leva ` · urgente` no fim da linha;
  - `espera <ID> (<estado>)`: aberta, com o primeiro do Depende que falta, em `aberta no planejamento`,
    `sem a cópia da passagem` (a PEND antes da primeira cópia), `em bloco, <estado>`, `bloco sem lane, <estado>`,
    `na lane <ID>`, `aberta` ou `não existe`.
- Sem ficha nenhuma, `nenhuma ficha`.
- O ID de ficha do código em mais de um arquivo vale pelo primeiro, em ordem do caminho, e sai no fim, depois das
  linhas, como `atenção: <ID> em mais de um arquivo: <caminhos>`, sem mudar a saída 0.
- `fichas nova <slug>`: o slug em minúsculas e algarismos, com hífens. O número é o maior do prefixo, mais 1, entre as
  fichas da árvore, as da árvore principal, as do `origin/<ramo_principal>`, sem fetch, as das lanes vivas e os
  blocos do prefixo, nas lanes e no ramo principal: nenhum número se reusa. Cria `<backlog>/<prefixo>-NN-<slug>.md`
  com o título e os onze campos (Marco, Depende, Tamanho, Prioridade, Contexto, Fonte, Objetivo, Escopo, Fora,
  Restrições e Aceite), cada um com o comentário do molde, e imprime `<caminho> criada; preencha os campos`.
- Recusas, com saída 1: `fora de um repositório git`; `slug inválido: <slug>`; `<caminho> já existe`;
  `<caminho>: estado.md inválido: <motivo>`; `<passagem>/manifesto.json: manifesto ilegível: <motivo>`; e
  `falta <arquivo>; a cópia muda só por harness.py importar`.
"""

CAMPOS_DA_FICHA = ("Marco", "Depende", "Tamanho", "Prioridade", "Contexto", "Fonte", "Objetivo", "Escopo", "Fora",
                   "Restrições", "Aceite")
PREFIXO_DA_PASSAGEM = "FICHA"
PREFIXO_DA_PENDENCIA = "PEND"
# O corpo do ID de uma ficha ou de uma pendência (`FICHA-01`, `PEND-07`, `DEV-12`), sem as bordas de palavra.
CORPO_DO_ID = r"[A-Z]{2,}(?:-[A-Z]+)*-[0-9]{2,}"
RE_ID_CITADO = re.compile(rf"\b{CORPO_DO_ID}\b")
RE_SLUG = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
# O comentário de cada campo no molde da ficha do código; `<prefixo>` vira o prefixo do perfil.
COMENTARIOS = {
    "Marco": '<!-- um marco da passagem, ou "—" -->',
    "Depende": '<!-- FICHA-NN, PEND-NN e <prefixo>-NN de que ela precisa, separados por vírgula; "—" para nenhuma -->',
    "Tamanho": '<!-- P, M ou "G: <motivo>" -->',
    "Prioridade": "<!-- urgente ou normal; urgente para a correção que não espera a fila -->",
    "Contexto": "<!-- sim, quando o Context Packet não basta, ou não -->",
    "Fonte": "<!-- os IDs da passagem e das fichas de que ela vem; os arquivos por link -->",
    "Objetivo": "<!-- o resultado, não a solução, em até duas frases -->",
    "Escopo": "<!-- o que entra, um item por linha -->",
    "Fora": '<!-- o que fica para outra ficha, com o ID dela; "—" para nada -->',
    "Restrições": "<!-- as regras e os requisitos não funcionais da passagem que valem aqui, por ID -->",
    "Aceite": "<!-- um item por condição, com o resultado; nenhum item começa por ID -->",
}

_RE_FICHA_DA_PASSAGEM = re.compile(rf"{PREFIXO_DA_PASSAGEM}-[0-9]{{2,}}")
_RE_TAMANHO = re.compile(r"P|M|G: .+")
PRIORIDADES = ("urgente", "normal")


@dataclass(frozen=True)
class Ficha:
    id: str
    slug: str
    arquivo: str  # relativo à raiz da árvore
    linha: int  # a linha do título, a partir de 1
    texto: str  # o trecho, com a quebra de cada linha


def numero(id_: str) -> int:
    """O número depois do último hífen do ID."""
    return int(id_.rsplit("-", 1)[1])


def _linhas_com_quebra(texto: str) -> list[str]:
    partes = texto.split("\n")
    return [parte + "\n" for parte in partes[:-1]] + ([partes[-1]] if partes[-1] else [])


def _slug_do_titulo(linha: str) -> str:
    return linha.split(": ", 1)[1].strip() if ": " in linha else ""


def texto_da_ficha_nova(id_: str, slug: str, prefixo: str) -> str:
    """O molde da ficha do código: o título `### <ID>: <slug>` e uma linha por campo, com o comentário dele."""
    linhas = [f"### {id_}: {slug}"]
    linhas += [f"- **{campo}:** {COMENTARIOS[campo].replace('<prefixo>', prefixo)}" for campo in CAMPOS_DA_FICHA]
    return "".join(linha + "\n" for linha in linhas)


def ler_manifesto(raiz: Path, perfil) -> Manifesto | None:
    """O `<passagem>/manifesto.json` da árvore; None sem ele; ilegível, `Recusa`."""
    relativo = f"{perfil.caminhos.passagem}/{manifesto.NOME}"
    try:
        dados = (raiz / relativo).read_bytes()
    except FileNotFoundError:
        return None
    except OSError as erro:
        raise Recusa(f"{relativo}: manifesto ilegível: {comum.motivo_do_sistema(erro)}") from None
    try:
        return manifesto.de_json(dados.decode("utf-8"))
    except UnicodeDecodeError:
        raise Recusa(f"{relativo}: manifesto ilegível: fora do UTF-8") from None
    except manifesto.ManifestoInvalido as erro:
        raise Recusa(f"{relativo}: manifesto ilegível: {erro.motivo}") from None


def da_passagem(raiz: Path, perfil, manifesto_: Manifesto) -> list[Ficha]:
    """As FICHA do manifesto da cópia, em ordem de número; o arquivo da cópia que falta dá `Recusa`."""
    pasta = perfil.caminhos.passagem
    lidas = []
    for id_, definicao in manifesto_.ids.items():
        if not _RE_FICHA_DA_PASSAGEM.fullmatch(id_):
            continue
        arquivo = f"{pasta}/{definicao.arquivo}"
        try:
            texto = comum.ler_texto(raiz / arquivo)
        except (OSError, UnicodeDecodeError):
            raise Recusa(f"falta {arquivo}; a cópia muda só por harness.py importar") from None
        primeira, ultima = definicao.linhas
        trecho = "".join(_linhas_com_quebra(texto)[primeira - 1:ultima])
        lidas.append(Ficha(id_, _slug_do_titulo(trecho.split("\n", 1)[0]), arquivo, primeira, trecho))
    return sorted(lidas, key=lambda ficha: numero(ficha.id))


def _re_nome(prefixo: str) -> re.Pattern:
    """O nome do arquivo de uma ficha do código: `<prefixo>-NN-<slug>.md`, com o número e o slug nos grupos."""
    return re.compile(rf"{re.escape(prefixo)}-([0-9]{{2,}})-({RE_SLUG.pattern})\.md")


def _ficha_do_codigo(achado: re.Match, texto: str, perfil) -> Ficha:
    """A ficha do código do arquivo cujo nome casou o `_re_nome`. O texto é o trecho do título `### <ID>` (com `:` ou
    sozinho), o primeiro fora dos blocos de código; sem ele, a linha 1 e o arquivo inteiro."""
    id_ = f"{perfil.prefixo}-{achado.group(1)}"
    titulo = re.compile(rf"### {re.escape(id_)}(:|$)")
    linha = next((n for n, conteudo in campos.linhas_fora_de_blocos(texto) if titulo.match(conteudo)), None)
    if linha is not None:
        primeira, ultima = manifesto.trecho(texto, linha)
        texto = "".join(_linhas_com_quebra(texto)[primeira - 1:ultima])
    return Ficha(id_, achado.group(2), f"{perfil.caminhos.backlog}/{achado.group(0)}", linha or 1, texto)


def do_backlog(raiz: Path, perfil) -> list[Ficha]:
    """As fichas do código, uma por arquivo `<prefixo>-NN-<slug>.md` de `caminhos.backlog`, em ordem de número, com o
    texto do `_ficha_do_codigo`."""
    pasta = raiz / perfil.caminhos.backlog
    if not pasta.is_dir():
        return []
    nome = _re_nome(perfil.prefixo)
    lidas = []
    for arquivo in sorted(pasta.iterdir()):
        achado = nome.fullmatch(arquivo.name)
        if achado and arquivo.is_file():
            lidas.append(_ficha_do_codigo(achado, comum.ler_texto(arquivo), perfil))
    return sorted(lidas, key=lambda ficha: numero(ficha.id))


def do_principal(raiz: Path, perfil, executar=subprocess.run) -> list[Ficha]:
    """As fichas do código do `<backlog>/` do `origin/<ramo_principal>`, sem fetch, em ordem de número; sem essa ref,
    `[]`."""
    return da_ref(raiz, perfil, f"refs/remotes/origin/{perfil.ramo_principal}", executar)


def da_ref(raiz: Path, perfil, ref: str, executar=subprocess.run) -> list[Ficha]:
    """As fichas do código do `<backlog>/` da ref, em ordem de número; sem a ref, `[]`."""
    if bloco.git(raiz, ["rev-parse", "--verify", "-q", ref], executar).returncode != 0:
        return []
    backlog = perfil.caminhos.backlog
    listados = bloco.git(raiz, ["ls-tree", "-z", ref, "--", f"{backlog}/"], executar)
    if listados.returncode != 0:
        raise Recusa(f"git ls-tree falhou: {comum.motivo_do_git(listados, 'ls-tree')}")
    nome = _re_nome(perfil.prefixo)
    lidas = []
    for entrada in listados.stdout.decode("utf-8", errors="replace").split("\0"):
        cabeca, _, caminho = entrada.partition("\t")
        achado = nome.fullmatch(caminho.rsplit("/", 1)[-1])
        if not achado or cabeca.split(" ")[1:2] != ["blob"] or caminho != f"{backlog}/{achado.group(0)}":
            continue
        lido = bloco.git(raiz, ["cat-file", "blob", f"{ref}:{caminho}"], executar)
        if lido.returncode != 0:
            raise Recusa(f"git cat-file falhou: {comum.motivo_do_git(lido, 'cat-file')}")
        lidas.append(_ficha_do_codigo(achado, lido.stdout.decode("utf-8", errors="replace"), perfil))
    return sorted(lidas, key=lambda ficha: numero(ficha.id))


def campo(ficha: Ficha, nome: str) -> list[str] | None:
    """Os textos dos itens do campo da ficha, pelo leitor comum, ou None sem o campo."""
    achado = campos.itens_do_campo(campos.linhas_fora_de_blocos(ficha.texto), nome)
    return None if achado is None else [texto for _, texto in achado[1]]


def _prefixo_do_id(id_: str) -> str:
    return id_.split("-", 1)[0]


def prefixos_citaveis(manifesto_: Manifesto | None, prefixo: str) -> frozenset[str]:
    """Os prefixos que um ID citado pode ter: os dos IDs do manifesto, o das pendências e o das fichas do código."""
    definidos = {_prefixo_do_id(id_) for id_ in manifesto_.ids} if manifesto_ is not None else set()
    return frozenset(definidos | {PREFIXO_DA_PENDENCIA, prefixo})


def ids_citados(ficha: Ficha, prefixos: frozenset[str]) -> list[str]:
    """Os IDs que a ficha cita fora dos comentários, na ordem em que aparecem, sem repetir e sem o dela. O `X-01.1`
    cita o `X-01`."""
    texto = campos._RE_COMENTARIO_HTML.sub("", ficha.texto)
    citados: list[str] = []
    for id_ in RE_ID_CITADO.findall(texto):
        if _prefixo_do_id(id_) in prefixos and id_ != ficha.id and id_ not in citados:
            citados.append(id_)
    return citados


def _tem_comentario(linhas: list[tuple[int, str]], rotulo: str) -> bool:
    """Se a linha do campo, ou uma das linhas mais recuadas logo abaixo dela, tem `<!--`."""
    marca = re.compile(r"(\s*)[-*+]\s+\*\*" + re.escape(rotulo) + r"(?::\*\*|\*\*:)")
    for posicao, (_, linha) in enumerate(linhas):
        achado = marca.match(linha)
        if achado:
            break
    else:
        return False
    recuo = len(achado.group(1))
    trecho = [linha]
    for _, abaixo in linhas[posicao + 1:]:
        if abaixo.strip() and len(abaixo) - len(abaixo.lstrip()) <= recuo:
            break
        trecho.append(abaixo)
    return any("<!--" in linha_ for linha_ in trecho)


def problema_de_forma(ficha: Ficha, prefixo: str) -> str | None:
    """O primeiro problema da forma da ficha do código (spec 6c, §9.1), ou None.

    A ordem: o título `### <ID>: <slug>`; cada campo de CAMPOS_DA_FICHA, na ordem, presente, sem `<!--` e não vazio;
    o Depende, `—` ou IDs de FICHA, PEND e do prefixo separados por `, `; o Tamanho, `P`, `M` ou `G: <motivo>`; a
    Prioridade, `urgente` ou `normal`; e o Contexto, `sim` ou `não`.
    """
    esperado = f"### {ficha.id}: {ficha.slug}"
    if ficha.texto.split("\n", 1)[0].rstrip("\r") != esperado:
        return f"título fora da forma {esperado}"
    linhas = campos.linhas_fora_de_blocos(ficha.texto)
    valores = {}
    for nome in CAMPOS_DA_FICHA:
        itens = campo(ficha, nome)
        if itens is None:
            return f"falta o campo {nome}"
        if _tem_comentario(linhas, nome):
            return f"o campo {nome} tem o comentário do molde"
        if not itens:
            return f"{nome} vazio"
        valores[nome] = itens
    depende = ", ".join(valores["Depende"])
    um_id = rf"(?:{PREFIXO_DA_PASSAGEM}|{PREFIXO_DA_PENDENCIA}|{re.escape(prefixo)})-[0-9]{{2,}}"
    if depende != "—" and not re.fullmatch(rf"{um_id}(?:, {um_id})*", depende):
        return f"Depende fora da forma: {depende}"
    tamanho = " ".join(valores["Tamanho"])
    if not _RE_TAMANHO.fullmatch(tamanho):
        return f"Tamanho fora da forma: {tamanho}"
    prioridade = " ".join(valores["Prioridade"])
    if prioridade not in PRIORIDADES:
        return f"Prioridade fora da forma: {prioridade}"
    contexto = " ".join(valores["Contexto"])
    if contexto not in ("sim", "não"):
        return f"Contexto fora da forma: {contexto}"
    return None


@dataclass(frozen=True)
class Quadro:
    fichas: tuple[Ficha, ...]  # as da árvore: as FICHA e depois as do código
    manifesto: Manifesto | None  # o da cópia da árvore
    lanes: tuple[LaneViva, ...]
    principal: dict[str, EstadoDoBloco]  # os blocos do ramo principal, pelo ID
    so_nas_lanes: dict[str, str]  # a ficha do código que só existe numa lane: o ID do bloco dessa lane
    # O ID das fichas do código em mais de um arquivo: os caminhos, em ordem
    repetidas: dict[str, tuple[str, ...]] = field(default_factory=dict)


def quadro(raiz: Path, perfil, executar=subprocess.run, ilegiveis: list[str] | None = None) -> Quadro:
    """As fichas, o manifesto da cópia da árvore, as lanes vivas e os blocos do ramo principal.

    As fichas do código vêm, sem repetir o nome do arquivo e nesta ordem, da árvore, da árvore principal, quando é
    outra, e do `origin/<ramo_principal>`, sem fetch; ficam em ordem de número e, no mesmo número, do caminho. As
    `so_nas_lanes` são as das lanes que nenhuma dessas fontes tem.

    Um `estado.md` de lane fora do formato ou que não se lê lança `BlocoInvalido`, `UnicodeDecodeError` ou `OSError`;
    com `ilegiveis`, o quadro sai sem essa lane e a lista recebe a linha dela, como o `bloco.lanes_vivas` a escreve.
    """
    manifesto_ = ler_manifesto(raiz, perfil)
    do_codigo = do_backlog(raiz, perfil)
    arvore_principal = bloco.arvore_principal(raiz, executar)
    outras = [] if comum.mesma_arvore(arvore_principal, Path(raiz)) else do_backlog(arvore_principal, perfil)
    for ficha in outras + do_principal(raiz, perfil, executar):
        if all(ficha.arquivo != vista.arquivo for vista in do_codigo):
            do_codigo.append(ficha)
    do_codigo.sort(key=lambda ficha: (numero(ficha.id), ficha.arquivo))
    repetidas: dict[str, tuple[str, ...]] = {}
    for ficha in do_codigo:
        repetidas[ficha.id] = repetidas.get(ficha.id, ()) + (ficha.arquivo,)
    da_arvore = (da_passagem(raiz, perfil, manifesto_) if manifesto_ is not None else []) + do_codigo
    lanes = bloco.lanes_vivas(raiz, perfil, executar, ilegiveis)
    principal = bloco.blocos_do_principal(raiz, perfil, executar)
    ids = {ficha.id for ficha in da_arvore}
    so_nas_lanes: dict[str, str] = {}
    for lane in lanes:
        for ficha in do_backlog(lane.pasta, perfil):
            if ficha.id not in ids:
                so_nas_lanes.setdefault(ficha.id, lane.bloco.id)
    return Quadro(tuple(da_arvore), manifesto_, tuple(lanes), principal, so_nas_lanes,
                  {id_: caminhos for id_, caminhos in repetidas.items() if len(caminhos) > 1})


def avisos(q: Quadro) -> list[str]:
    """Uma linha por ID de ficha do código em mais de um arquivo, em ordem de número."""
    return [f"atenção: {id_} em mais de um arquivo: {comum.juntar(q.repetidas[id_])}"
            for id_ in sorted(q.repetidas, key=numero)]


def _da_passagem(id_: str) -> bool:
    return bool(_RE_FICHA_DA_PASSAGEM.fullmatch(id_))


def dependencias(ficha: Ficha | None, prefixo: str) -> list[str]:
    """Os IDs de FICHA, PEND e do prefixo nos itens do Depende, na ordem, sem repetir."""
    itens = campo(ficha, "Depende") if ficha is not None else None
    achados = re.findall(rf"\b(?:{PREFIXO_DA_PASSAGEM}|{PREFIXO_DA_PENDENCIA}|{re.escape(prefixo)})-[0-9]{{2,}}\b",
                         ", ".join(itens or []))
    return list(dict.fromkeys(achados))


def _o_que_falta(id_: str, q: Quadro) -> str | None:
    """O estado da dependência que ainda falta, ou None quando ela não segura a ficha."""
    if id_.rsplit("-", 1)[0] == PREFIXO_DA_PENDENCIA:
        if q.manifesto is None:
            return "sem a cópia da passagem"
        return "aberta no planejamento" if any(pendencia.id == id_ for pendencia in q.manifesto.pendencias) else None
    lane = next((lane for lane in q.lanes if lane.bloco.id == id_), None)
    if lane is not None:
        return f"em bloco, {lane.bloco.estado}"
    if id_ in q.principal:
        estado = q.principal[id_].estado
        return None if estado == "closing" else f"bloco sem lane, {estado}"
    if id_ in q.so_nas_lanes:
        return f"na lane {q.so_nas_lanes[id_]}"
    return "aberta" if any(ficha.id == id_ for ficha in q.fichas) else "não existe"


def situacao(id_: str, q: Quadro, perfil) -> str:
    """O estado da ficha, como o `fichas` o imprime (spec 6c, §9.2), na primeira regra que vale; o ID sem ficha, lane,
    bloco nem ficha só numa lane dá `não existe` (spec 6d-bloco, §12, item 1)."""
    lane = next((lane for lane in q.lanes if lane.bloco.id == id_), None)
    if lane is not None:
        if _da_passagem(id_) and q.manifesto is not None and id_ not in q.manifesto.ids:
            return f"saiu da passagem/v{q.manifesto.versao}"
        return f"em bloco ({lane.bloco.estado})"
    if id_ in q.principal:
        estado = q.principal[id_].estado
        return "fechada" if estado == "closing" else f"bloco sem lane ({estado})"
    if id_ in q.so_nas_lanes:
        return f"na lane {q.so_nas_lanes[id_]}; entra no {perfil.ramo_principal} com o PR dela"
    ficha = next((ficha for ficha in q.fichas if ficha.id == id_), None)
    if ficha is None:
        return "não existe"
    if not _da_passagem(id_):
        problema = problema_de_forma(ficha, perfil.prefixo)
        if problema is not None:
            return f"fora da forma ({problema})"
    for dependencia in dependencias(ficha, perfil.prefixo):
        falta = _o_que_falta(dependencia, q)
        if falta is not None:
            return f"espera {dependencia} ({falta})"
    return "pronta"


def listar(q: Quadro, perfil) -> list[tuple[str, str]]:
    """(ID, situação) das fichas da árvore, das do código que só existem numa lane e das FICHA de bloco de lane viva
    que saíram da cópia: as FICHA e depois as do prefixo, cada grupo em ordem de número."""
    ids = [ficha.id for ficha in q.fichas] + list(q.so_nas_lanes)
    ids += [lane.bloco.id for lane in q.lanes
            if _da_passagem(lane.bloco.id) and (q.manifesto is None or lane.bloco.id not in q.manifesto.ids)]
    ordem = sorted(dict.fromkeys(ids), key=lambda id_: (not _da_passagem(id_), numero(id_)))
    return [(id_, situacao(id_, q, perfil)) for id_ in ordem]


def urgentes(q: Quadro, perfil) -> frozenset[str]:
    """Os IDs das fichas do código da árvore com `Prioridade: urgente`."""
    return frozenset(ficha.id for ficha in q.fichas
                     if ficha.id.startswith(f"{perfil.prefixo}-") and (campo(ficha, "Prioridade") or []) == ["urgente"])


def formatar(linhas: list[tuple[str, str]], urgentes: frozenset[str] = frozenset()) -> str:
    """Uma linha por ficha, com o ID alinhado à esquerda na largura do maior, dois espaços e a situação; a ficha
    `pronta` e urgente termina em ` · urgente`; sem linhas, `nenhuma ficha`."""
    if not linhas:
        return "nenhuma ficha\n"
    largura = max(len(id_) for id_, _ in linhas)
    marca = {id_: " · urgente" for id_ in urgentes}
    return "".join(f"{id_.ljust(largura)}  {situacao_}{marca.get(id_, '') if situacao_ == 'pronta' else ''}\n"
                   for id_, situacao_ in linhas)


def _numeros_no_backlog(nomes, prefixo: str) -> list[int]:
    nome = _re_nome(prefixo)
    return [int(achado.group(1)) for achado in map(nome.fullmatch, nomes) if achado]


def nova(raiz: Path, perfil, slug: str, executar=subprocess.run) -> str:
    """Cria a ficha do código seguinte com o molde e devolve o caminho, relativo à raiz.

    O número é o maior do prefixo, mais 1, entre os arquivos do backlog da árvore, da árvore principal, do
    `origin/<ramo_principal>` (sem fetch) e das lanes vivas e os IDs dos blocos do prefixo, nas lanes e no ramo
    principal: nenhum número se reusa.
    """
    if not RE_SLUG.fullmatch(slug):
        raise Recusa(f"slug inválido: {slug}")
    backlog = perfil.caminhos.backlog
    lanes = bloco.lanes_vivas(raiz, perfil, executar)
    nomes = [arquivo.name for arquivo in (raiz / backlog).glob("*.md")]
    for lane in lanes:
        nomes += [arquivo.name for arquivo in (lane.pasta / backlog).glob("*.md")]
    principal = bloco.arvore_principal(raiz, executar)
    if principal.resolve() != Path(raiz).resolve():
        nomes += [arquivo.name for arquivo in (principal / backlog).glob("*.md")]
    ref = f"refs/remotes/origin/{perfil.ramo_principal}"
    if bloco.git(raiz, ["rev-parse", "--verify", "-q", ref], executar).returncode == 0:
        listados = bloco.git(raiz, ["ls-tree", "-z", "--name-only", ref, "--", f"{backlog}/"], executar)
        if listados.returncode == 0:
            nomes += [caminho.rsplit("/", 1)[-1] for caminho in listados.stdout.decode("utf-8", "replace").split("\0")]
    numeros = _numeros_no_backlog(nomes, perfil.prefixo)
    blocos = [lane.bloco.id for lane in lanes] + list(bloco.blocos_do_principal(raiz, perfil, executar))
    numeros += [numero(id_) for id_ in blocos if id_.rsplit("-", 1)[0] == perfil.prefixo]
    id_ = f"{perfil.prefixo}-{max(numeros, default=0) + 1:02d}"
    relativo = f"{backlog}/{id_}-{slug}.md"
    destino = raiz / relativo
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(destino, "x", encoding="utf-8", newline="") as arquivo:
            arquivo.write(texto_da_ficha_nova(id_, slug, perfil.prefixo))
    except FileExistsError:
        raise Recusa(f"{relativo} já existe") from None
    return relativo
