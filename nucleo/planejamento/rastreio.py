"""Rastreio entre os documentos do planejamento (spec 4b, §5 e §11): quem cita cada documento, termo ou ID, e com que
status. Acha quem linka ou cita um documento e os termos que o nomeiam, busca o termo sem acento, liga os IDs de uma
linha à definição e lê o status de cada documento na tabela de artefatos. Base do dossiê e da conferência de
propagação (`harness.py afetados`)."""
from __future__ import annotations

import posixpath
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import backlog
import checar
import comum
from perfil import Perfil

AJUDA = """\
Lista quem cita cada alvo, um ID ou um termo, agrupado pelo status do documento na tabela de artefatos.

O alvo é um ID de requisito (um padrão de `ids.padroes`, `-` e o número), que casa também dentro de uma faixa, um ID
de pendência (`<prefixo>-NN`) ou um termo entre aspas, procurado sem acento e sem maiúscula, como palavra inteira, com
plural em `s` ou `es` e com espaço e hífen tratados como iguais. Procura nos `.md` da pasta do planejamento, fora dos
blocos de código, sem os moldes, o STATUS.md, o backlog, as decisões e o rascunho; nas linhas de Ruling do arquivo de
decisões; e nas pendências abertas do backlog.

Com um ID de pendência, entram também como alvos os IDs de requisito citados na linha dela no backlog, menos a célula
do ID, com as faixas expandidas, depois dos alvos dados e sem repetição. A saída começa por uma linha
`<prefixo>-NN cita: <IDs>` (ou `<prefixo>-NN cita: nenhum ID`) por pendência, na ordem dos alvos, e o resto sai para a
união dos alvos. A pendência que não está no backlog é recusada com `recusado: <prefixo>-NN não está no backlog`,
com 1.

Saída, com 0 mesmo sem citação:

- `<prefixo>-NN cita: <IDs>`, uma por pendência dada;
- `Afetados por <alvos>: <n> linhas em <d> documentos, <r> Rulings, <p> pendências abertas`;
- `Definição: <arquivo>:<linha>`, a linha que define o ID de requisito, ou a da própria pendência;
- os documentos por grupo de status, um `<arquivo>:<linha>` por linha: `aprovado` primeiro, porque pede revisão quando
  o alvo muda, depois `em-revisao`, `rascunho`, os outros status e `fora da tabela`;
- `Rulings (<n>)` e `Pendências abertas (<n>)`, estas com o ID.

Sem `--verbose`, até 20 linhas, e `[20 de <total> linhas; --verbose mostra todas, com o trecho]` quando há mais; com
ele, todas, com a seção e o trecho. Alvo vazio: `recusado: alvo vazio`, com 1.
"""

APROVADO = "aprovado"
ORDEM_DOS_STATUS = (APROVADO, "em-revisao", "rascunho")
FORA_DA_TABELA = "fora da tabela"
SEM_STATUS = "sem status"
LIMITE_TRECHO = 300
LIMITE_DEFINICAO = 200
LIMITE_TELA = 20
MARCA_DE_RULING = "Ruling:"

_RE_TITULO = re.compile(r"#{1,6} +(.*\S)")
_SEPARADOR_DO_TITULO = " — "
_ENTRE_PALAVRAS = r"[\s-]+"


@dataclass(frozen=True)
class Linha:
    """Uma linha achada: o arquivo relativo à raiz, o número a partir de 1, a seção em que ela está e o texto."""

    arquivo: str
    numero: int
    secao: str
    texto: str


def linhas_do_texto(texto: str) -> list[str]:
    """As linhas do texto sem o `\\r` do fim; a posição na lista mais 1 é o número da linha."""
    return [linha.rstrip("\r") for linha in texto.split("\n")]


def ler_ou_none(caminho: Path) -> str | None:
    """O texto em UTF-8, ou None se o arquivo falta ou não se lê."""
    try:
        return comum.ler_texto(caminho)
    except (OSError, UnicodeDecodeError):
        return None


def cortar(texto: str, limite: int) -> str:
    """O texto sem os espaços das pontas, cortado em `limite` caracteres com `...` no fim."""
    texto = texto.strip()
    return texto if len(texto) <= limite else texto[: limite - 3] + "..."


def normalizar(texto: str) -> str:
    """Sem acento e sem maiúscula: a forma em que o termo e a linha se comparam."""
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(letra for letra in decomposto if not unicodedata.combining(letra)).casefold()


def padrao_do_termo(termo: str) -> re.Pattern:
    """A regex do termo para o texto normalizado: começa e termina fora de palavra, aceita "s" ou "es" no fim e trata
    espaço e hífen entre as palavras como iguais. Termo sem palavra lança ValueError."""
    palavras = [re.escape(palavra) for palavra in re.split(_ENTRE_PALAVRAS, normalizar(termo)) if palavra]
    if not palavras:
        raise ValueError(f"termo vazio: {termo!r}")
    return re.compile(r"(?<!\w)" + _ENTRE_PALAVRAS.join(palavras) + r"(?:s|es)?(?!\w)")


def termos_do_documento(relativo: str, texto: str | None) -> list[str]:
    """Os termos que nomeiam o documento (spec 4b, §7.1, item 5): o do título de nível 1, entre o primeiro ": " e o
    " — " seguinte, quando o título já não é o do molde (sem `<!--`); e o do nome do arquivo, sem o prefixo até o
    primeiro hífen e com hífen trocado por espaço. Os dois iguais depois de normalizados valem por um."""
    termos: list[str] = []
    titulo = next((linha for linha in linhas_do_texto(texto or "") if linha.startswith("# ")), "")
    if ": " in titulo and "<!--" not in titulo:
        termo = titulo.split(": ", 1)[1].split(_SEPARADOR_DO_TITULO, 1)[0].strip()
        if termo:
            termos.append(termo)
    nome = posixpath.basename(relativo)
    if nome.endswith(".md"):
        nome = nome[: -len(".md")]
    if "-" in nome:
        nome = nome.split("-", 1)[1]
    nome = nome.replace("-", " ").strip()
    if nome and all(normalizar(nome) != normalizar(termo) for termo in termos):
        termos.append(nome)
    return termos


def linhas_com_secao(texto: str) -> list[tuple[int, str, str]]:
    """(número, seção, texto) de cada linha fora dos blocos de código. A seção é o último título visto; antes do
    primeiro, `checar.SEM_TITULO`."""
    secao = checar.SEM_TITULO
    achadas = []
    for numero, linha in checar.linhas_fora_de_blocos(texto):
        titulo = _RE_TITULO.match(linha)
        if titulo:
            secao = titulo.group(1)
        achadas.append((numero, secao, linha))
    return achadas


def linhas_com_termos(texto: str, padroes: list[re.Pattern]) -> list[tuple[int, str]]:
    """(número, texto) das linhas em que algum padrão de termo casa com a linha normalizada."""
    return [
        (numero, linha)
        for numero, linha in enumerate(linhas_do_texto(texto), start=1)
        if any(padrao.search(normalizar(linha)) for padrao in padroes)
    ]


def status_dos_artefatos(texto_backlog: str, perfil: Perfil) -> dict[str, str]:
    """Caminho relativo à raiz para o status de cada documento da tabela de artefatos, dentro da pasta do
    planejamento."""
    return {
        caminho: status
        for _, caminho, status in backlog.artefatos_da_pasta(texto_backlog, perfil.caminhos.planejamento)
    }


def grupo_do_status(status: str | None) -> str:
    """O grupo do documento: `aprovado`, `em-revisao` ou `rascunho` pelo começo do status; outro status, ele mesmo
    (vazio, SEM_STATUS); fora da tabela (None), FORA_DA_TABELA."""
    if status is None:
        return FORA_DA_TABELA
    return next((grupo for grupo in ORDEM_DOS_STATUS if status.startswith(grupo)), status or SEM_STATUS)


def ordem_do_grupo(grupo: str) -> tuple[int, str]:
    """Chave de ordenação dos grupos: os de ORDEM_DOS_STATUS nessa ordem, os outros status em ordem alfabética e, por
    último, FORA_DA_TABELA."""
    if grupo in ORDEM_DOS_STATUS:
        return ORDEM_DOS_STATUS.index(grupo), ""
    if grupo == FORA_DA_TABELA:
        return len(ORDEM_DOS_STATUS) + 1, ""
    return len(ORDEM_DOS_STATUS), grupo


def documentos_do_planejamento(raiz: Path, perfil: Perfil) -> list[str]:
    """Os `.md` da pasta do planejamento, relativos à raiz e em ordem, menos os de subpastas com o nome da pasta de
    moldes e os arquivos de estado, pendências, decisões e rascunho."""
    pasta = raiz / perfil.caminhos.planejamento
    if not pasta.is_dir():
        return []
    moldes = Path(perfil.moldes.pasta).name
    c = perfil.caminhos
    fora = {c.status, c.backlog, c.decisoes, c.rascunho}
    achados = []
    for arquivo in pasta.rglob("*.md"):
        if not arquivo.is_file() or moldes in arquivo.relative_to(pasta).parts[:-1]:
            continue
        relativo = arquivo.relative_to(raiz).as_posix()
        if relativo not in fora:
            achados.append(relativo)
    return sorted(achados)


def padrao_do_nome(relativo: str) -> re.Pattern:
    """A regex do nome do arquivo de `relativo` numa linha: um nome que só termina igual não casa."""
    return re.compile(r"(?<![\w.-])" + re.escape(posixpath.basename(relativo)) + r"(?![\w-])")


def citacoes(relativo: str, textos: dict[str, str]) -> list[Linha]:
    """As linhas de `textos` (caminho relativo à raiz para o texto), fora dos blocos de código, que linkam `relativo`
    ou citam o nome do arquivo dele; na ordem dos caminhos e das linhas, sem o próprio documento."""
    nome = padrao_do_nome(relativo)
    achadas = []
    for caminho in sorted(textos):
        if caminho == relativo:
            continue
        for numero, secao, linha in linhas_com_secao(textos[caminho]):
            if nome.search(linha) or relativo in checar.destinos_de_links(linha, caminho):
                achadas.append(Linha(caminho, numero, secao, linha))
    return achadas


def ids_das_linhas(achadas: list[Linha], perfil: Perfil) -> list[str]:
    """Os IDs citados nas linhas, com as faixas expandidas, sem repetição e na ordem em que aparecem."""
    vistos: list[str] = []
    for linha in achadas:
        for _, id_ in checar.ids_citados(linha.texto, perfil)[0]:
            if id_ not in vistos:
                vistos.append(id_)
    return vistos


@dataclass(frozen=True)
class Alvo:
    """Um alvo do `afetados`: o `texto` como veio e, dele, um ID de requisito (normalizado), o número de uma pendência
    ou a regex de um termo."""

    texto: str
    requisito: str | None
    pendencia: int | None
    termo: re.Pattern | None


def alvo(texto: str, perfil: Perfil) -> Alvo:
    """O alvo do `texto`: ID de requisito, ID de pendência ou, sem um dos dois, termo (spec 4b, §5)."""
    requisito = re.fullmatch(r"(?P<prefixo>" + "|".join(perfil.ids.padroes) + r")-(?P<numero>[0-9]{2,})", texto)
    if requisito:
        return Alvo(texto, f"{requisito.group('prefixo')}-{int(requisito.group('numero')):02d}", None, None)
    pendencia = re.fullmatch(re.escape(perfil.ids.prefixo_pendencia) + r"-([0-9]{2,})", texto)
    if pendencia:
        return Alvo(texto, None, int(pendencia.group(1)), None)
    return Alvo(texto, None, None, padrao_do_termo(texto))


def _pendencias_citadas(texto: str, perfil: Perfil) -> set[int]:
    padrao = re.compile(r"(?<![\w-])" + re.escape(perfil.ids.prefixo_pendencia) + r"-([0-9]{2,})(?!\w)")
    return {int(achado.group(1)) for achado in padrao.finditer(texto)}


def ids_por_linha(texto: str, perfil: Perfil) -> dict[int, set[str]]:
    """Os IDs de requisito citados em cada linha do `texto` (número da linha, de 1, para o conjunto de IDs), com as
    faixas expandidas."""
    por_linha: dict[int, set[str]] = {}
    for numero, id_ in checar.ids_citados(texto, perfil)[0]:
        por_linha.setdefault(numero, set()).add(id_)
    return por_linha


def _casa(alvo: Alvo, linha: str, ids_da_linha: set[str], perfil: Perfil) -> bool:
    if alvo.requisito is not None:
        return alvo.requisito in ids_da_linha
    if alvo.pendencia is not None:
        return alvo.pendencia in _pendencias_citadas(linha, perfil)
    return alvo.termo.search(normalizar(linha)) is not None


def alvos_que_casam(alvos: Sequence[Alvo], linha: str, ids_da_linha: set[str], perfil: Perfil) -> list[Alvo]:
    """Os `alvos` que a `linha` cita, na ordem dada. `ids_da_linha` são os IDs de requisito da linha, que o
    `ids_por_linha` dá."""
    return [candidato for candidato in alvos if _casa(candidato, linha, ids_da_linha, perfil)]


class PendenciaForaDoBacklog(Exception):
    """Um alvo do `afetados` é uma pendência que não está no backlog. `mensagem` diz qual."""

    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


def ids_da_pendencia(texto_backlog: str, perfil: Perfil, numero: int) -> tuple[str, ...] | None:
    """Os IDs de requisito citados na linha da pendência `numero` no backlog, menos a célula do ID, com as faixas
    expandidas, sem repetição e na ordem do texto; None sem a pendência no backlog."""
    linhas = linhas_do_texto(texto_backlog)
    for numero_da_linha, id_, _ in backlog.linhas_de_pendencia(texto_backlog, perfil):
        if numero in _pendencias_citadas(id_, perfil):
            texto = " | ".join(backlog.celulas(linhas[numero_da_linha - 1])[1:])
            return tuple(dict.fromkeys(id_citado for _, id_citado in checar.ids_citados(texto, perfil)[0]))
    return None


@dataclass(frozen=True)
class Afetados:
    """O que a conferência de propagação acha (spec 4b, §11). `documentos` traz (grupo do status, linha) na ordem da
    saída: por grupo (ordem_do_grupo), arquivo e linha. Nas pendências, a `secao` da linha traz o ID dela. Os
    `alvos` são os dados e os IDs que as pendências dadas citam (spec 6a, §5.3); `ids_das_pendencias` traz, por
    pendência dada, o ID dela e os IDs que ela cita."""

    alvos: tuple[str, ...]
    definicoes: tuple[Linha, ...]
    documentos: tuple[tuple[str, Linha], ...]
    rulings: tuple[Linha, ...]
    pendencias: tuple[Linha, ...]
    ids_das_pendencias: tuple[tuple[str, tuple[str, ...]], ...] = ()


def afetados(raiz: Path, perfil: Perfil, textos_dos_alvos: list[str]) -> Afetados:
    """Quem cita cada alvo: um ID de requisito, com as faixas expandidas; um ID de pendência, que traz como alvos os
    IDs que ela cita; ou um termo, com a busca sem acento. Nos documentos do planejamento, fora dos blocos de código;
    no arquivo de decisões, só as linhas de Ruling; no de pendências, só as abertas. A linha que define um ID de
    requisito, e a linha da própria pendência, saem em `definicoes`. A pendência que não está no backlog lança
    PendenciaForaDoBacklog antes da busca."""
    texto_backlog = ler_ou_none(raiz / perfil.caminhos.backlog) or ""
    ids_das_pendencias: list[tuple[str, tuple[str, ...]]] = []
    for texto in textos_dos_alvos:
        numero = alvo(texto, perfil).pendencia
        if numero is None:
            continue
        id_ = f"{perfil.ids.prefixo_pendencia}-{numero:02d}"
        ids = ids_da_pendencia(texto_backlog, perfil, numero)
        if ids is None:
            raise PendenciaForaDoBacklog(f"{id_} não está no backlog")
        ids_das_pendencias.append((id_, ids))
    textos = list(textos_dos_alvos)
    vistos = {alvo(texto, perfil).requisito or texto for texto in textos}
    for _, ids in ids_das_pendencias:
        for citado in ids:
            if citado not in vistos:
                vistos.add(citado)
                textos.append(citado)
    alvos = [alvo(texto, perfil) for texto in textos]
    status = status_dos_artefatos(texto_backlog, perfil)
    definicoes: list[Linha] = []
    documentos: list[tuple[str, Linha]] = []
    for caminho in documentos_do_planejamento(raiz, perfil):
        texto = ler_ou_none(raiz / caminho)
        if texto is None:
            continue
        citados = ids_por_linha(texto, perfil)
        definidos = dict(checar.ids_definidos(texto, perfil))
        for numero, secao, linha in linhas_com_secao(texto):
            achados = alvos_que_casam(alvos, linha, citados.get(numero, set()), perfil)
            if not achados:
                continue
            item = Linha(caminho, numero, secao, linha)
            if any(alvo.requisito is not None and definidos.get(numero) == alvo.requisito for alvo in achados):
                definicoes.append(item)
            else:
                documentos.append((grupo_do_status(status.get(caminho)), item))
    documentos.sort(key=lambda par: (ordem_do_grupo(par[0]), par[1].arquivo, par[1].numero))

    decisoes = ler_ou_none(raiz / perfil.caminhos.decisoes) or ""
    citados = ids_por_linha(decisoes, perfil)
    rulings = [
        Linha(perfil.caminhos.decisoes, numero, "", linha)
        for numero, linha in enumerate(linhas_do_texto(decisoes), start=1)
        if MARCA_DE_RULING in linha and alvos_que_casam(alvos, linha, citados.get(numero, set()), perfil)
    ]

    pendencias: list[Linha] = []
    do_backlog = linhas_do_texto(texto_backlog)
    citados = ids_por_linha(texto_backlog, perfil)
    for numero, id_, situacao in backlog.linhas_de_pendencia(texto_backlog, perfil):
        item = Linha(perfil.caminhos.backlog, numero, id_, do_backlog[numero - 1])
        if any(alvo.pendencia in _pendencias_citadas(id_, perfil) for alvo in alvos if alvo.pendencia is not None):
            definicoes.append(item)
        elif situacao.startswith(backlog.PREFIXO_ABERTA) and alvos_que_casam(
            alvos, item.texto, citados.get(numero, set()), perfil
        ):
            pendencias.append(item)
    return Afetados(
        tuple(textos), tuple(definicoes), tuple(documentos), tuple(rulings), tuple(pendencias), tuple(ids_das_pendencias)
    )


def _quantos(numero: int, singular: str, plural: str) -> str:
    return f"{numero} {singular if numero == 1 else plural}"


def formatar_afetados(resultado: Afetados, verbose: bool) -> str:
    """A saída do `afetados`: a linha das contagens, as definições, os documentos por grupo de status, os Rulings e as
    pendências abertas, um `arquivo:linha` por linha. Sem `verbose`, até LIMITE_TELA dessas linhas, com o total no
    fim; com ele, todas, com o trecho (e a seção, nos documentos)."""
    def trecho(linha: Linha) -> str:
        return f" · {cortar(linha.texto, LIMITE_TRECHO)}" if verbose else ""

    grupos: list[tuple[str, list[str]]] = []
    for grupo in dict.fromkeys(grupo for grupo, _ in resultado.documentos):
        grupos.append((grupo, [
            f"  {linha.arquivo}:{linha.numero}" + (f" · {linha.secao}" if verbose else "") + trecho(linha)
            for outro, linha in resultado.documentos if outro == grupo
        ]))
    if resultado.rulings:
        grupos.append(("Rulings", [f"  {linha.arquivo}:{linha.numero}" + trecho(linha) for linha in resultado.rulings]))
    if resultado.pendencias:
        grupos.append(("Pendências abertas", [
            f"  {linha.secao} {linha.arquivo}:{linha.numero}" + trecho(linha) for linha in resultado.pendencias
        ]))
    arquivos = len({linha.arquivo for _, linha in resultado.documentos})
    saida = [f"{id_} cita: {comum.juntar(ids) if ids else 'nenhum ID'}" for id_, ids in resultado.ids_das_pendencias]
    saida += [
        f"Afetados por {comum.juntar(resultado.alvos)}: {_quantos(len(resultado.documentos), 'linha', 'linhas')} em "
        f"{_quantos(arquivos, 'documento', 'documentos')}, {_quantos(len(resultado.rulings), 'Ruling', 'Rulings')}, "
        f"{_quantos(len(resultado.pendencias), 'pendência aberta', 'pendências abertas')}"
    ]
    saida += [f"Definição: {linha.arquivo}:{linha.numero}" for linha in resultado.definicoes]
    total = sum(len(itens) for _, itens in grupos)
    restantes = total if verbose else LIMITE_TELA
    for titulo, itens in grupos:
        if restantes <= 0:
            break
        saida.append(f"{titulo} ({len(itens)})")
        saida += itens[:restantes]
        restantes -= min(restantes, len(itens))
    if not verbose and total > LIMITE_TELA:
        saida.append(f"[{LIMITE_TELA} de {total} linhas; --verbose mostra todas, com o trecho]")
    return "".join(linha + "\n" for linha in saida)
