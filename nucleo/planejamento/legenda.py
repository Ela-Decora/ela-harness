"""Legenda das siglas e dos tipos de ID (spec 6b, §5), gerada a partir dos documentos e conferida no commit.

Três partes: as siglas padrão da engenharia de software e as do harness, listas fixas do núcleo, e os códigos do
projeto, tirados dos títulos de domínio dos artefatos da tabela do backlog. A mesma função gera a legenda a partir da
cópia de trabalho, do índice ou de um commit: só muda o `ler`. A legenda de um repositório de código monta as mesmas
três partes sobre as mesmas listas fixas, com a parte 2 lida de outra legenda e os links movidos de pasta.
"""
from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from typing import Callable

import backlog
import checar
from perfil import Perfil

AJUDA = """\
Gera a legenda das siglas e dos tipos de ID no caminho de `caminhos.legenda`, a partir da cópia de trabalho, e
imprime `Gravado: <caminho> (<n> linhas)`. A primeira linha do arquivo é um comentário que diz que ele é gerado; a
guarda nega a edição à mão.

O arquivo tem três partes, cada uma com uma tabela:

- Siglas padrão da engenharia de software: a lista fixa do núcleo, inteira, usada ou não pelo projeto.
- Códigos do projeto: uma linha por título `<marcadores> <nome> (<prefixo>-<CÓDIGO>)` nos artefatos da tabela do
  backlog, de qualquer status, na ordem da tabela e das linhas; o mesmo código num segundo título fica de fora. O
  prefixo é um de `ids.prefixos` com algum padrão `<prefixo>-...` em `ids.padroes`. A linha de um domínio do RF traz
  também o `FN-<CÓDIGO>-NN`, quando o FN está em `ids.prefixos`, e aponta para o título com a âncora do GitHub.
- Siglas e IDs do harness: a lista fixa do núcleo, mais o gate de cada fase, a pendência (`ids.prefixo_pendencia`) e
  o relato (`ids.prefixo_relato`), em ordem de sigla.

Com `--check`, só compara o arquivo, byte a byte, com o que gravaria: `legenda em dia: <caminho>`, com 0, ou
`legenda desatualizada: rode harness.py legenda`, com 1, também para o arquivo ausente.

Com `--ids "<texto>"`, não grava nada e imprime, no lugar da legenda, uma linha `<ID> (<título>)` por ID do texto e
uma `<SIGLA> (<significado>)` por sigla, na ordem da primeira aparição e sem repetir. O título vem da primeira
definição do ID nos artefatos da tabela, ou da célula Pendência do backlog; o ID sem definição sai com `não definido`.
A citação de item de Aceite (`<ID>.<n>`, ou a faixa `<ID>.<n> a <ID>.<m>`) conta como o ID e leva o título depois da
citação inteira. É para pôr ao lado do ID na primeira aparição de um texto. Não combina com `--check` e não pede `caminhos.legenda`.

Com `--ids-de <arquivo>`, o mesmo, com o texto lido do arquivo, sem passar o Markdown pelo shell; o arquivo ilegível
sai com `recusado: <arquivo> ilegível (<motivo>)` e 1.

Os dois saem com 1, sem gravar, com `tipo de ID sem legenda: <tipo>`, uma linha por tipo: primeiro cada prefixo de
`ids.prefixos` sem entrada no núcleo, na ordem do perfil; depois cada `<prefixo>-<CÓDIGO>` citado com número fora de
bloco de código, nos artefatos da tabela, sem título que o nomeie, na ordem da primeira citação. O código de uma FN
vale com o título do RF de mesmo código. Sem `caminhos.legenda` no perfil, sai com 1 e
`erro: perfil sem caminhos.legenda`.
"""

CABECALHO = "<!-- Arquivo gerado por harness.py legenda. Não edite: rode harness.py legenda. -->"
ONDE_SE_DEFINE = "glossário do harness"
TITULO_DO_PROJETO = "## Códigos do projeto"
CABECALHO_DO_PROJETO = ("| Código | Nome | Tipos de ID | Onde se define |", "|---|---|---|---|")
SEM_CODIGO = "Nenhum código."
# O prefixo dos requisitos funcionais, cujo domínio é também o código de módulo da funcionalidade.
PREFIXO_DOMINIO = "RF"
PREFIXO_FUNCIONALIDADE = "FN"


@dataclass(frozen=True)
class Sigla:
    """Uma linha das partes 1 e 3. `formato` sem crases, vazio na sigla sem ID; `prefixo` é o do tipo de ID a que a
    linha dá legenda, vazio na sigla sem ID."""

    sigla: str
    nome: str
    formato: str
    verbete: str
    prefixo: str = ""


PARTE_1 = (
    Sigla("ADR", "registro de decisão de arquitetura", "", "Registro de decisão de arquitetura"),
    Sigla("API", "interface de programação de aplicações", "", "Interface de programação"),
    Sigla("C4", "modelo C4 (contexto, contêineres, componentes e código)", "", "Modelo C4"),
    Sigla("DDL", "linguagem de definição de dados", "", "Linguagem de definição de dados"),
    Sigla("DER", "diagrama entidade-relacionamento", "", "Diagrama entidade-relacionamento"),
    Sigla("MVP", "produto mínimo viável", "", "Produto mínimo viável"),
    Sigla("RF", "requisito funcional", "RF-<DOMÍNIO>-NN", "Requisito funcional", "RF"),
    Sigla("RN", "regra de negócio", "RN-NN", "Regra de negócio", "RN"),
    Sigla("RNF", "requisito não funcional", "RNF-<CATEGORIA>-NN", "Requisito não funcional", "RNF"),
    Sigla("SLO", "objetivo de nível de serviço", "SLO-NN", "Objetivo de serviço", "SLO"),
    Sigla("SQL", "linguagem de consulta estruturada", "", "Linguagem de consulta estruturada"),
    Sigla("UML", "linguagem de modelagem unificada", "", "Linguagem de modelagem unificada"),
)
PARTE_3 = (
    Sigla("AME", "ameaça", "AME-NN", "Ameaça", "AME"),
    Sigla("CTR", "contrato externo", "CTR-NN", "Contrato externo", "CTR"),
    Sigla("FICHA", "ficha", "FICHA-NN", "Ficha", "FICHA"),
    Sigla("FN", "funcionalidade", "FN-<MÓDULO>-NN", "Funcionalidade", "FN"),
    Sigla("RA", "regra de arquitetura", "RA-NN", "Regra de arquitetura", "RA"),
    Sigla("RSC", "risco", "RSC-NN", "Risco", "RSC"),
)
VERBETE_GATE = "Gate"
VERBETE_PENDENCIA = "Pendência"
VERBETE_RELATO = "Relato"
VERBETES: tuple[str, ...] = tuple(sigla.verbete for sigla in PARTE_1 + PARTE_3) + (
    VERBETE_GATE, VERBETE_PENDENCIA, VERBETE_RELATO
)


class LegendaRecusada(Exception):
    """Algum tipo de ID ficaria sem legenda. `motivos` traz um `tipo de ID sem legenda: <tipo>` por tipo."""

    def __init__(self, motivos: tuple[str, ...]):
        super().__init__("\n".join(motivos))
        self.motivos = motivos


_RE_TITULO = re.compile(r"#{1,6} (.*)")
_RE_LINK = re.compile(r"\]\(([^)\s]*)\)")
_RE_ESQUEMA = re.compile(r"[a-z][a-z0-9+.-]*:", re.IGNORECASE)


def slug(titulo: str) -> str:
    """A âncora do GitHub para o título: minúsculas, só letras, algarismos, hífen e espaço, e o espaço vira hífen."""
    return "".join(c for c in titulo.lower() if c.isalnum() or c in "- ").replace(" ", "-")


def slugs(texto: str) -> dict[int, str]:
    """A âncora de cada título fora de bloco de código, pela linha, com `-1`, `-2` nos repetidos do arquivo."""
    vistos: dict[str, int] = {}
    ancoras = {}
    for numero, linha in checar.linhas_fora_de_blocos(texto):
        titulo = _RE_TITULO.match(linha)
        if titulo is None:
            continue
        base = slug(titulo.group(1).strip())
        repeticoes = vistos.get(base, 0)
        ancoras[numero] = base if repeticoes == 0 else f"{base}-{repeticoes}"
        vistos[base] = repeticoes + 1
    return ancoras


def _artefatos(ler: Callable[[str], str | None], perfil: Perfil) -> list[tuple[str, str]]:
    """(caminho, texto) dos artefatos da tabela do backlog nas pastas das fases, de qualquer status, pela linha na
    tabela. O artefato que o `ler` não acha fica de fora."""
    texto_backlog = ler(perfil.caminhos.backlog)
    if texto_backlog is None:
        return []
    pasta = perfil.caminhos.planejamento.rstrip("/")
    linhas = sorted(
        (linha, caminho)
        for fase in perfil.fases
        for linha, caminho, _ in backlog.artefatos_da_pasta(texto_backlog, f"{pasta}/{fase.id}")
    )
    artefatos = []
    for _, caminho in linhas:
        texto = ler(caminho)
        if texto is not None:
            artefatos.append((caminho, texto))
    return artefatos


TAMANHO_DO_TITULO = 60
_RE_LINK_DE_TEXTO = re.compile(r"\[([^\]]*)\]\([^)]*\)")


def _titulo_do_id(resto: str) -> str:
    """O título do que vem depois do ID: sem os `:`, `—`, `-` e `**` do começo, os `**`, as crases e os links, cortado
    em `TAMANHO_DO_TITULO` caracteres com `…`, ou `SEM_TITULO` se sobra nada."""
    resto = _RE_LINK_DE_TEXTO.sub(r"\1", resto.lstrip(" :—-*")).replace("**", "").replace("`", "")
    resto = " ".join(resto.split())
    if not resto:
        return checar.SEM_TITULO
    return resto if len(resto) <= TAMANHO_DO_TITULO else resto[:TAMANHO_DO_TITULO - 1] + "…"


def titulos(ler: Callable[[str], str | None], perfil: Perfil) -> dict[str, str]:
    """O ID para o título, da primeira definição dele nos artefatos da tabela, na ordem da tabela: o texto da linha
    depois do ID, ou, na linha de tabela, a célula seguinte à do ID. As pendências trazem a célula Pendência do
    backlog. O ID de relato fica de fora."""
    padroes = checar._padroes(perfil)
    achados: dict[str, str] = {}
    for _, texto in _artefatos(ler, perfil):
        for _, linha in checar.linhas_fora_de_blocos(texto):
            achado = padroes.id_definido.match(linha)
            if achado is None:
                continue
            id_ = f"{achado.group('prefixo')}-{achado.group('numero')}"
            if id_ in achados or not padroes.id_no_padrao.fullmatch(id_):
                continue
            if linha.lstrip().startswith("|"):
                celulas = backlog.celulas(linha)
                posicao = next((i for i, celula in enumerate(celulas) if id_ in celula), -1)
                achados[id_] = _titulo_do_id(celulas[posicao + 1] if 0 <= posicao < len(celulas) - 1 else "")
            else:
                achados[id_] = _titulo_do_id(linha[achado.end():])
    texto_backlog = ler(perfil.caminhos.backlog)
    if texto_backlog is not None:
        for _, celulas in backlog._pendencias(texto_backlog, perfil):
            if len(celulas) > 1:
                achados.setdefault(celulas[0], _titulo_do_id(celulas[1]))
    return achados


def _regex_de_ids(perfil: Perfil) -> str:
    pendencia = re.escape(perfil.ids.prefixo_pendencia)
    # O `(?!0+$)` do padrão vale para o token inteiro; no meio do texto, o fim do ID é a borda que não é letra.
    padrao = checar._padroes(perfil).id_no_padrao.pattern.replace("(?!0+$)", r"(?!0+(?![\w-]))")
    return "(?:" + padrao + "|" + pendencia + "-[0-9]+)"


def _regex_da_citacao(perfil: Perfil) -> str:
    """O ID no grupo `id`, com a citação de item de Aceite que vier junto: `<ID>.<n>` ou a faixa `<ID>.<n> a <ID>.<m>`.
    O ID seguido de `.<dígito>` só casa com a citação inteira, para a legenda não entrar no meio dela."""
    return rf"(?P<id>{_regex_de_ids(perfil)})(?:\.[0-9]+(?:\s+a\s+(?P=id)\.[0-9]+)?)?(?!\.[0-9])"


def _significados(perfil: Perfil) -> dict[str, str]:
    significados = {sigla.sigla: sigla.nome for sigla in PARTE_1 + PARTE_3}
    for fase in perfil.fases:
        significados[fase.gate] = f"gate da camada {fase.id}"
    significados[perfil.ids.prefixo_pendencia] = "pendência"
    return significados


def legendar(texto: str, ler: Callable[[str], str | None], perfil: Perfil) -> list[str]:
    """As linhas `<ID> (<título>)` e `<SIGLA> (<significado>)` do texto, na ordem da primeira aparição, sem repetir.
    O ID sem definição sai com `não definido`. A sigla dentro de um ID não conta."""
    significados = _significados(perfil)
    siglas = "|".join(re.escape(s) for s in sorted(significados, key=len, reverse=True))
    procura = re.compile(rf"(?<![\w-])(?:{_regex_da_citacao(perfil)}|(?P<sigla>{siglas}))(?![\w-])")
    por_id = titulos(ler, perfil)
    linhas: list[str] = []
    for achado in procura.finditer(texto):
        chave = achado.group("id") or achado.group(0)
        descricao = por_id.get(chave, "não definido") if achado.group("id") else significados[chave]
        linha = f"{chave} ({descricao})"
        if linha not in linhas:
            linhas.append(linha)
    return linhas


def com_legenda(texto: str, titulos: dict[str, str], perfil: Perfil) -> str:
    """O texto com ` (<título>)` logo depois da primeira aparição de cada ID que tem título em `titulos`; na citação
    de item de Aceite (`<ID>.<n>`, ou a faixa `<ID>.<n> a <ID>.<m>`), depois da citação inteira."""
    procura = re.compile(rf"(?<![\w-]){_regex_da_citacao(perfil)}(?![\w-])")
    vistos: set[str] = set()

    def juntar(achado: re.Match[str]) -> str:
        id_, citacao = achado.group("id"), achado.group(0)
        if id_ in vistos:
            return citacao
        vistos.add(id_)
        return f"{citacao} ({titulos[id_]})" if id_ in titulos else citacao

    return procura.sub(juntar, texto)


def _linha(celulas: list[str]) -> str:
    return "| " + " | ".join(celulas) + " |"


def _tabela_de_siglas(itens: list[Sigla]) -> list[str]:
    linhas = [_linha(["Sigla", "Nome", "Formato do ID", "Onde se define"]), "|---|---|---|---|"]
    for item in itens:
        formato = f"`{item.formato}`" if item.formato else "—"
        linhas.append(_linha([item.sigla, item.nome, formato, ONDE_SE_DEFINE]))
    return linhas


def _montar(cabecalho: str, projeto: list[str], do_harness: list[Sigla]) -> str:
    """As três partes sob o `cabecalho`: a `PARTE_1`, as linhas do `projeto` sob o cabeçalho da tabela (ou a linha
    de vazio) e as siglas do `do_harness`, em ordem de sigla."""
    linhas = [cabecalho, "# Legenda", "", "## Siglas padrão da engenharia de software", ""]
    linhas += _tabela_de_siglas(list(PARTE_1))
    linhas += ["", TITULO_DO_PROJETO, ""]
    linhas += [*CABECALHO_DO_PROJETO, *projeto] if projeto else [SEM_CODIGO]
    linhas += ["", "## Siglas e IDs do harness", ""]
    linhas += _tabela_de_siglas(sorted(do_harness, key=lambda sigla: sigla.sigla))
    return "\n".join(linhas) + "\n"


def linhas_do_projeto(texto: str) -> list[str] | None:
    """As linhas da tabela da parte 2 de uma legenda gerada, sem as duas do cabeçalho, ou `[]` na parte com a linha de
    vazio. None sem o título da parte 2, ou com ele e nenhuma tabela nem linha de vazio. A tabela é a que vem logo
    abaixo do título, até a primeira linha que não começa por `|`."""
    linhas = texto.splitlines()
    if TITULO_DO_PROJETO not in linhas:
        return None
    abaixo = linhas[linhas.index(TITULO_DO_PROJETO) + 1:]
    while abaixo and not abaixo[0].strip():
        abaixo.pop(0)
    if abaixo and abaixo[0].strip() == SEM_CODIGO:
        return []
    tabela = []
    for linha in abaixo:
        if not linha.startswith("|"):
            break
        tabela.append(linha)
    return tabela[2:] if tabela else None


def mover_links(linha: str, de: str, para: str) -> str:
    """A linha com cada `](<destino>)` relativo resolvido a partir da pasta `de` e escrito relativo à pasta `para`,
    com a âncora igual. O destino com esquema, só de âncora ou absoluto fica como está."""

    def mover(achado: re.Match[str]) -> str:
        destino = achado.group(1)
        caminho, cerquilha, ancora = destino.partition("#")
        if not caminho or caminho.startswith("/") or _RE_ESQUEMA.match(caminho):
            return achado.group(0)
        movido = posixpath.relpath(posixpath.normpath(posixpath.join(de, caminho)), para)
        if caminho.endswith("/"):
            movido += "/"
        return f"]({movido}{cerquilha}{ancora})"

    return _RE_LINK.sub(mover, linha)


def do_codigo(cabecalho: str, projeto: list[str], pendencia: str) -> str:
    """O texto da legenda de um repositório de código: o `cabecalho` pronto, a `PARTE_1`, as linhas do `projeto` e a
    `PARTE_3` com a pendência de prefixo `pendencia`, sem os gates nem o relato do planejamento."""
    do_harness = list(PARTE_3)
    do_harness.append(Sigla(pendencia, "pendência", f"{pendencia}-NN", VERBETE_PENDENCIA))
    return _montar(cabecalho, projeto, do_harness)


def gerar(ler: Callable[[str], str | None], perfil: Perfil) -> str:
    """O texto da legenda, com `ler(caminho)` dando o texto do caminho relativo à raiz ou None. Supõe
    `caminhos.legenda` no perfil. Tipo de ID sem legenda lança LegendaRecusada."""
    com_entrada = {sigla.prefixo for sigla in PARTE_1 + PARTE_3 if sigla.prefixo}
    motivos = [f"tipo de ID sem legenda: {prefixo}" for prefixo in perfil.ids.prefixos if prefixo not in com_entrada]

    com_codigo = [p for p in perfil.ids.prefixos if any(padrao.startswith(p + "-") for padrao in perfil.ids.padroes)]
    artefatos = _artefatos(ler, perfil)
    # Código para (prefixo, nome, caminho, linha) do primeiro título que o nomeia.
    titulos: dict[str, tuple[str, str, str, int]] = {}
    nomeados: set[tuple[str, str]] = set()
    citados: list[str] = []
    if com_codigo:
        alternacao = "|".join(re.escape(p) for p in sorted(com_codigo, key=len, reverse=True))
        re_titulo = re.compile(rf"#{{1,6}} (.+?) \(({alternacao})-([A-Z][A-Z0-9]*)\)\s*")
        re_citacao = re.compile(rf"\b({alternacao})-([A-Z][A-Z0-9]*)-[0-9]+\b")
        padroes = {p: [padrao for padrao in perfil.ids.padroes if padrao.startswith(p + "-")] for p in com_codigo}
        for caminho, texto in artefatos:
            for numero, linha in checar.linhas_fora_de_blocos(texto):
                titulo = re_titulo.fullmatch(linha)
                if titulo:
                    nome, prefixo, codigo = titulo.groups()
                    if any(re.fullmatch(padrao, f"{prefixo}-{codigo}") for padrao in padroes[prefixo]):
                        nomeados.add((prefixo, codigo))
                        titulos.setdefault(codigo, (prefixo, nome, caminho, numero))
                for citacao in re_citacao.finditer(linha):
                    tipo = f"{citacao.group(1)}-{citacao.group(2)}"
                    if tipo not in citados:
                        citados.append(tipo)
    for tipo in citados:
        prefixo, codigo = tipo.split("-", 1)
        nomeado = (prefixo, codigo) in nomeados or (
            prefixo == PREFIXO_FUNCIONALIDADE and (PREFIXO_DOMINIO, codigo) in nomeados
        )
        if not nomeado:
            motivos.append(f"tipo de ID sem legenda: {tipo}")
    if motivos:
        raise LegendaRecusada(tuple(motivos))

    pasta_da_legenda = posixpath.dirname(perfil.caminhos.legenda) or "."
    textos = dict(artefatos)
    projeto = []
    for codigo, (prefixo, nome, caminho, numero) in titulos.items():
        tipos = [f"`{prefixo}-{codigo}-NN`"]
        if prefixo == PREFIXO_DOMINIO and PREFIXO_FUNCIONALIDADE in perfil.ids.prefixos:
            tipos.append(f"`{PREFIXO_FUNCIONALIDADE}-{codigo}-NN`")
        destino = posixpath.relpath(caminho, pasta_da_legenda) + "#" + slugs(textos[caminho])[numero]
        onde = f"[{posixpath.basename(caminho)}]({destino})"
        projeto.append(_linha([codigo, nome, ", ".join(tipos), onde]))
    do_harness = list(PARTE_3)
    do_harness += [Sigla(fase.gate, f"gate da camada {fase.id}", "", VERBETE_GATE) for fase in perfil.fases]
    pendencia, relato = perfil.ids.prefixo_pendencia, perfil.ids.prefixo_relato
    do_harness.append(Sigla(pendencia, "pendência", f"{pendencia}-NN", VERBETE_PENDENCIA))
    do_harness.append(Sigla(relato, "relato", f"{relato}-NN", VERBETE_RELATO))
    return _montar(CABECALHO, projeto, do_harness)
