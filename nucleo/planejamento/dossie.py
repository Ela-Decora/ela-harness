"""Dossiê de um documento ou de um pacote (spec 4b, §7): as fontes de cada documento, achadas por script, sem LLM e
sem rede. Lê o planejamento e as fontes; grava só o arquivo do dossiê, fora do git, e devolve o resumo."""
from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from pathlib import Path

import backlog
import checar
import comum
import estado
import rastreio
import registro
from perfil import ItemDoGate, Perfil

AJUDA = """\
Monta o dossiê de cada documento, as fontes dele achadas por script, num arquivo fora do git, e imprime um resumo.

Sem argumento, usa os documentos em refino do STATUS.md, o `Pacote` ou o `Documento`. Grava
`.claude/harness/dossie/<nome do primeiro documento>.md`, refeito a cada execução; a mesma entrada dá o mesmo
arquivo. O resumo tem até 20 linhas: o arquivo, uma linha por documento com as contagens (com `Rulings novos` e
`prováveis alvos`, no documento com o item 7) e os itens do gate, os IDs sem cobertura e os avisos. Com `--verbose`,
imprime o arquivo inteiro. Para cada documento, o dossiê junta:

1. o contrato: o molde e os títulos de nível 1 a 3 dele;
2. as linhas dos documentos aprovados que linkam o documento ou citam o nome do arquivo dele;
3. os IDs citados nessas linhas, com a linha da definição;
4. os links que o documento faz para outros documentos do planejamento, com o status de cada destino;
5. os termos do documento (o do título de nível 1 e o do nome do arquivo), procurados sem acento: as linhas do
   arquivo de decisões (os Rulings primeiro), das pendências abertas e do rascunho; nos `.md` e `.txt` dos relatórios
   de pesquisa (só as subpastas `pesquisa-*` de `caminhos.pesquisas`) e das fontes (`caminhos.fontes`), cada arquivo
   como `<arquivo>: <n> linhas`; até 15 itens por bloco, com `- [15 de <total>]` no corte (o bloco do item 7 não tem
   corte);
6. os itens de script que valem para ele no primeiro gate ainda não aprovado no STATUS.md, a partir do da fase
   dele, que tenha algum (sem nenhum, o gate da fase, com zero itens; STATUS ausente ou inválido conta como nenhum
   gate aprovado), e, nos itens `ids-cobertos`, os IDs ainda sem citação;
7. no documento `aprovado` ou `em-revisao` na tabela de artefatos, os Rulings do arquivo de decisões com data maior
   que a da aprovação, `<arquivo>:<linha>: <trecho>`, todos, sem corte, na ordem do arquivo. O Ruling em que casa um
   termo do item 5 ou um ID que o documento define, pela busca do `afetados`, sai como
   `provável alvo (<alvos que casaram>): <arquivo>:<linha>: <trecho>`. No `aprovado`, a data é a da tabela, e sem
   data legível nela sai `sem data na tabela de artefatos`, que também vai como aviso ao resumo. No
   `em-revisao`, a data é a da última linha `- <AAAA-MM-DD> ` da seção de aprovações do arquivo de decisões que cita
   o caminho do documento; sem ela, o documento nunca foi aprovado, e o bloco não sai.

Sai com 0 ao gravar; o molde ausente vira aviso. Sai com 1 sem documento, com `STATUS.md inválido: <motivo>` sem
argumento, ou com documento fora da pasta do planejamento (`documento fora de <pasta>/: <documento>`).
"""

PASTA_DOSSIE = ".claude/harness/dossie"
LIMITE_POR_FONTE = 15
LIMITE_SEM_COBERTURA = 30
LIMITE_RESUMO = 20
EXTENSOES_DE_TEXTO = (".md", ".txt")

TITULO_RULINGS = "Rulings depois da aprovação"
SEM_DATA = "sem data na tabela de artefatos"
ROTULO_RULINGS = "Rulings novos"
ROTULO_PROVAVEIS = "prováveis alvos"

_PREFIXO_DA_PESQUISA = "pesquisa-"
_APROVADO_EM = "aprovado em "
_RE_TITULO_DO_MOLDE = re.compile(r"#{1,3} ")
_RE_DATA = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_RE_LINHA_DATADA = re.compile(r"- ([0-9]{4}-[0-9]{2}-[0-9]{2}) ")
_COM_RULINGS_NOVOS = (rastreio.APROVADO, "em-revisao")


@dataclass(frozen=True)
class Documento:
    """O dossiê de um documento: as linhas que vão para o arquivo e o que o resumo mostra."""

    relativo: str
    linhas: tuple[str, ...]
    contagens: tuple[tuple[str, int], ...]
    gate: tuple[str, ...]
    sem_cobertura: int
    avisos: tuple[str, ...]


@dataclass(frozen=True)
class Dossie:
    """O arquivo gravado, relativo à raiz, e o dossiê de cada documento, na ordem pedida."""

    caminho: str
    documentos: tuple[Documento, ...]


@dataclass(frozen=True)
class _Fontes:
    """O que todos os documentos do dossiê leem, lido uma vez por execução."""

    texto_backlog: str
    status: dict[str, str]
    aprovados: dict[str, str]
    decisoes: str
    rascunho: str
    pesquisa: tuple[tuple[str, str], ...]
    outras: tuple[tuple[str, str], ...]
    definidos: dict[str, tuple[str, int]]
    gates: dict[str, str]
    datas: dict[str, str]


def _ler_solto(caminho: Path) -> str:
    """O texto de um arquivo das fontes, com o byte que não é UTF-8 trocado; erro do sistema dá texto vazio."""
    try:
        return caminho.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return ""


def _arquivos_de_texto(pasta: Path) -> list[Path]:
    """Os `.md` e `.txt` da pasta e das subpastas, em ordem; pasta ausente dá lista vazia."""
    if not pasta.is_dir():
        return []
    return sorted(
        arquivo for arquivo in pasta.rglob("*") if arquivo.is_file() and arquivo.suffix.lower() in EXTENSOES_DE_TEXTO
    )


def _ler_fontes(raiz: Path, perfil: Perfil) -> _Fontes:
    c = perfil.caminhos
    texto_backlog = rastreio.ler_ou_none(raiz / c.backlog) or ""
    status = rastreio.status_dos_artefatos(texto_backlog, perfil)
    aprovados = {}
    for caminho, situacao in status.items():
        texto = rastreio.ler_ou_none(raiz / caminho) if rastreio.grupo_do_status(situacao) == rastreio.APROVADO else None
        if texto is not None:
            aprovados[caminho] = texto
    pasta = raiz / c.pesquisas
    pastas = []
    if pasta.is_dir():
        pastas = sorted(p for p in pasta.iterdir() if p.is_dir() and p.name.startswith(_PREFIXO_DA_PESQUISA))
    pesquisa = tuple(
        (arquivo.relative_to(raiz).as_posix(), _ler_solto(arquivo)) for p in pastas for arquivo in _arquivos_de_texto(p)
    )
    da_pesquisa = {relativo for relativo, _ in pesquisa}
    outras: dict[str, str] = {}
    for fonte in c.fontes:
        for arquivo in _arquivos_de_texto(raiz / fonte):
            relativo = arquivo.relative_to(raiz).as_posix()
            if relativo not in da_pesquisa and relativo not in outras:
                outras[relativo] = _ler_solto(arquivo)
    return _Fontes(
        texto_backlog,
        status,
        aprovados,
        rastreio.ler_ou_none(raiz / c.decisoes) or "",
        rastreio.ler_ou_none(raiz / c.rascunho) or "",
        pesquisa,
        tuple(sorted(outras.items())),
        checar.ids_definidos_nas_fases(raiz, texto_backlog, perfil, perfil.fases),
        _gates_do_status(raiz, perfil),
        backlog.datas_da_pasta(texto_backlog, c.planejamento),
    )


def _gates_do_status(raiz: Path, perfil: Perfil) -> dict[str, str]:
    """O valor de cada gate no STATUS.md; ausente ou inválido dá nenhum gate."""
    try:
        dados = estado.ler(raiz / perfil.caminhos.status, perfil)
    except estado.EstadoInvalido:
        return {}
    return {fase.gate: dados.get(fase.gate, "") for fase in perfil.fases}


def _bloco(
    titulo: str, itens: list[str], limite: int | None = LIMITE_POR_FONTE, nivel: str = "####"
) -> list[str]:
    """Título com o total e até `limite` itens, ou todos com `limite=None`; o corte vira a linha
    `- [<limite> de <total>]`."""
    saida = ["", f"{nivel} {titulo} ({len(itens)})"]
    saida += [f"- {item}" for item in (itens if limite is None else itens[:limite])]
    if limite is not None and len(itens) > limite:
        saida.append(f"- [{limite} de {len(itens)}]")
    return saida


def _por_arquivo(arquivos: tuple[tuple[str, str], ...], padroes: list[re.Pattern]) -> list[str]:
    """`<arquivo>: <n> linha(s)` para cada arquivo com linha em que algum termo casa."""
    itens = []
    for relativo, texto in arquivos:
        achadas = len(rastreio.linhas_com_termos(texto, padroes))
        if achadas:
            itens.append(f"{relativo}: {achadas} linha" + ("" if achadas == 1 else "s"))
    return itens


def _decisoes(texto: str, padroes: list[re.Pattern], caminho: str) -> list[str]:
    """As linhas do arquivo de decisões com algum termo: primeiro as de Ruling, depois as outras."""
    achadas = rastreio.linhas_com_termos(texto, padroes)
    rulings = [par for par in achadas if rastreio.MARCA_DE_RULING in par[1]]
    outras = [par for par in achadas if rastreio.MARCA_DE_RULING not in par[1]]
    return [f"{caminho}:{numero}: {rastreio.cortar(linha, rastreio.LIMITE_TRECHO)}" for numero, linha in rulings + outras]


def _alvos_do_documento(termos: list[str], texto: str | None, perfil: Perfil) -> list[rastreio.Alvo]:
    """Os alvos do documento: os `termos`, depois os IDs que o `texto` define (`checar.ids_definidos`), sem repetição."""
    textos = termos + [id_ for _, id_ in checar.ids_definidos(texto or "", perfil)]
    return [rastreio.alvo(alvo, perfil) for alvo in dict.fromkeys(textos)]


def _rulings_depois(
    decisoes: str, data: str, caminho: str, alvos: list[rastreio.Alvo], perfil: Perfil
) -> tuple[list[str], int]:
    """`<arquivo>:<linha>: <trecho>` de cada Ruling do arquivo de decisões (a linha `- <AAAA-MM-DD> ` com `Ruling:`)
    com data maior que `data`, na ordem do arquivo, e quantos saíram marcados. O Ruling que algum dos `alvos` casa,
    pela busca do `afetados`, sai como `provável alvo (<alvos que casaram>): <arquivo>:<linha>: <trecho>`."""
    ids = rastreio.ids_por_linha(decisoes, perfil)
    itens = []
    marcados = 0
    for numero, linha in enumerate(rastreio.linhas_do_texto(decisoes), start=1):
        datada = _RE_LINHA_DATADA.match(linha)
        if datada and rastreio.MARCA_DE_RULING in linha and datada.group(1) > data:
            item = f"{caminho}:{numero}: {rastreio.cortar(linha, rastreio.LIMITE_TRECHO)}"
            casaram = rastreio.alvos_que_casam(alvos, linha, ids.get(numero, set()), perfil)
            if casaram:
                item = f"provável alvo ({', '.join(alvo.texto for alvo in casaram)}): {item}"
                marcados += 1
            itens.append(item)
    return itens, marcados


def data_da_aprovacao(decisoes: str, relativo: str) -> str:
    """A data da última linha `- <AAAA-MM-DD> ` que contém `relativo` na seção do arquivo de decisões cujo título
    `## ` começa por `registro.SECAO_APROVACOES`, até o próximo título de nível 1 ou 2; sem ela, `""`."""
    data = ""
    na_secao = False
    for linha in rastreio.linhas_do_texto(decisoes):
        if linha.startswith("# ") or linha.startswith("## "):
            na_secao = linha.startswith("## " + registro.SECAO_APROVACOES)
            continue
        datada = _RE_LINHA_DATADA.match(linha)
        if na_secao and datada and relativo in linha:
            data = datada.group(1)
    return data


def _pendencias(texto_backlog: str, padroes: list[re.Pattern], perfil: Perfil) -> list[str]:
    """As pendências abertas com algum termo na linha."""
    do_backlog = rastreio.linhas_do_texto(texto_backlog)
    itens = []
    for numero, id_, situacao in backlog.linhas_de_pendencia(texto_backlog, perfil):
        linha = do_backlog[numero - 1]
        if situacao.startswith(backlog.PREFIXO_ABERTA) and any(p.search(rastreio.normalizar(linha)) for p in padroes):
            itens.append(f"{id_} ({perfil.caminhos.backlog}:{numero}): {rastreio.cortar(linha, rastreio.LIMITE_TRECHO)}")
    return itens


def _links(texto: str, relativo: str, perfil: Perfil, status: dict[str, str]) -> list[tuple[str, str, str, int]]:
    """(destino, grupo do status, seção, linha) de cada documento do planejamento que o texto linka, uma vez por par
    destino e seção, na ordem das linhas; moldes e o próprio documento ficam de fora."""
    pasta = perfil.caminhos.planejamento.rstrip("/") + "/"
    moldes = perfil.moldes.pasta.rstrip("/") + "/"
    vistos: set[tuple[str, str]] = set()
    links = []
    for numero, secao, linha in rastreio.linhas_com_secao(texto):
        for destino in sorted(checar.destinos_de_links(linha, relativo)):
            if (not destino.startswith(pasta) or destino.startswith(moldes) or not destino.endswith(".md")
                    or destino == relativo or (destino, secao) in vistos):
                continue
            vistos.add((destino, secao))
            links.append((destino, rastreio.grupo_do_status(status.get(destino)), secao, numero))
    return links


def _pasta(padrao: str) -> str:
    """`2-intermediario/Modulo/*.md` vira `2-intermediario/Modulo/`; outro padrão fica como está."""
    return padrao[: -len("*.md")] if padrao.endswith("/*.md") else padrao


def frase_do_item(item: ItemDoGate) -> str:
    """O que o item de script do gate cobra do documento, numa frase."""
    p = item.parametros
    if item.verificacao == "ligados":
        return "precisa ser linkado por um documento de " + comum.juntar([_pasta(x) for x in p["por"]], "ou")
    if item.verificacao == "coluna-com-texto":
        return f"a coluna {p['coluna']} da seção {p['secao'].lstrip('#').strip()} leva {p['texto']}"
    if item.verificacao == "coluna-sem-texto":
        return f"a coluna {p['coluna']} da seção {p['secao'].lstrip('#').strip()} não leva {p['texto']}"
    if item.verificacao == "secoes-com-id":
        return f"cada seção \"{p['titulo'].lstrip('#').strip()}\" cita um ID de {comum.juntar(p['prefixos'], 'ou')}"
    if item.verificacao == "ids-cobertos":
        origem = ("de " + comum.juntar([_pasta(x) for x in p["definidos_em"]], "ou") if "definidos_em" in p
                  else "das camadas anteriores")
        condicao = f", com {p['quando']['campo']} {p['quando']['formato']}," if "quando" in p else ""
        return (f"os IDs de {comum.juntar(p['prefixos'], 'ou')} {origem}{condicao} precisam ser citados por um "
                f"documento de {comum.juntar([_pasta(x) for x in p['documentos']], 'ou')}")
    if item.verificacao == "er-sem-atributos":
        return "o diagrama erDiagram não leva atributos"
    return item.verificacao


def _dentro_do_planejamento(relativo: str, perfil: Perfil) -> str:
    return relativo[len(perfil.caminhos.planejamento.rstrip("/")) + 1:]


def itens_do_gate(perfil: Perfil, relativo: str, gates: dict[str, str]) -> tuple[str, list[ItemDoGate]]:
    """O nome do gate e os itens de script dele cujo padrão de `documentos` casa com o documento.

    Vale o primeiro gate, do da fase da pasta do documento em diante, na ordem das fases, cujo valor em `gates` não
    começa por `aprovado em ` e que tem algum item para ele. Sem nenhum, o gate da fase, com zero itens; fora das
    fases, `—`.
    """
    fase = perfil.fase_do_documento(relativo)
    if fase is None:
        return "—", []
    dentro = _dentro_do_planejamento(relativo, perfil)
    for seguinte in perfil.fases[perfil.fases.index(fase):]:
        gate = perfil.gates.get(seguinte.gate)
        if gate is None or gates.get(seguinte.gate, "").startswith(_APROVADO_EM):
            continue
        itens = [
            item
            for item in gate.itens
            if item.tipo == "script"
            and any(comum.casa_padrao(padrao, dentro) for padrao in item.parametros.get("documentos", ()))
        ]
        if itens:
            return seguinte.gate, itens
    return fase.gate, []


def _sem_cobertura(raiz: Path, perfil: Perfil, fontes: _Fontes, relativo: str, itens: list[ItemDoGate]) -> list[str]:
    """Para cada item `ids-cobertos` do documento, os IDs que o item cobra (`checar.ids_a_cobrir`, com o
    `definidos_em` e o `quando` dele) que nenhum documento aprovado que casa com o padrão do item cita:
    `<ID> (<arquivo>:<linha>)`."""
    fase = perfil.fase_do_documento(relativo)
    cobertos = [item for item in itens if item.verificacao == "ids-cobertos"]
    if fase is None or not cobertos:
        return []
    faltam: list[str] = []
    for item in cobertos:
        definidos = checar.ids_a_cobrir(
            raiz, fontes.texto_backlog, perfil, fase, item.parametros["prefixos"],
            item.parametros.get("definidos_em", ()), item.parametros.get("quando"),
        )
        citados = {
            id_
            for caminho, texto in fontes.aprovados.items()
            if any(comum.casa_padrao(p, _dentro_do_planejamento(caminho, perfil)) for p in item.parametros["documentos"])
            for _, id_ in checar.ids_citados(texto, perfil)[0]
        }
        faltam += [f"{id_} ({caminho}:{linha})" for id_, (caminho, linha) in definidos.items() if id_ not in citados]
    return list(dict.fromkeys(faltam))


def _documento(raiz: Path, perfil: Perfil, fontes: _Fontes, relativo: str, cache: dict[str, list[str]]) -> Documento:
    saida = [f"## {relativo}", "", "### Contrato"]
    avisos: list[str] = []
    molde = checar.mostrar(raiz, checar.resolver_molde(raiz, Path(relativo), perfil))
    texto_molde = rastreio.ler_ou_none(raiz / molde)
    if texto_molde is None:
        avisos.append(f"molde não encontrado: {molde}")
        saida.append(f"Molde não encontrado: {molde}")
    else:
        saida.append(f"Molde: {molde}")
        saida += [
            f"- {linha.strip()}"
            for _, linha in checar.linhas_fora_de_blocos(texto_molde)
            if _RE_TITULO_DO_MOLDE.match(linha)
        ]

    citacoes = rastreio.citacoes(relativo, fontes.aprovados)
    saida += ["", f"### Citações em documentos aprovados ({len(citacoes)})"]
    saida += [
        f"- {linha.arquivo}:{linha.numero} · {linha.secao} · {rastreio.cortar(linha.texto, rastreio.LIMITE_TRECHO)}"
        for linha in citacoes
    ]

    ids = rastreio.ids_das_linhas(citacoes, perfil)
    saida += ["", f"### IDs citados nessas linhas ({len(ids)})"]
    for id_ in ids:
        onde = fontes.definidos.get(id_)
        if onde is None:
            saida.append(f"- {id_}: definição não encontrada")
            continue
        caminho, numero = onde
        if caminho not in cache:
            cache[caminho] = rastreio.linhas_do_texto(rastreio.ler_ou_none(raiz / caminho) or "")
        definicao = cache[caminho][numero - 1] if numero <= len(cache[caminho]) else ""
        saida.append(f"- {id_}: {caminho}:{numero}: {rastreio.cortar(definicao, rastreio.LIMITE_DEFINICAO)}")

    texto = rastreio.ler_ou_none(raiz / relativo)
    links = _links(texto, relativo, perfil, fontes.status) if texto is not None else []
    saida += ["", f"### Links que o documento faz ({len(links)})"]
    saida += [f"- {destino} · {grupo} · {secao} (L{numero})" for destino, grupo, secao, numero in links]

    termos = rastreio.termos_do_documento(relativo, texto)
    padroes = [rastreio.padrao_do_termo(termo) for termo in termos]
    decisoes = _decisoes(fontes.decisoes, padroes, perfil.caminhos.decisoes)
    pendencias = _pendencias(fontes.texto_backlog, padroes, perfil)
    rascunho = [
        f"{perfil.caminhos.rascunho}:{numero}: {rastreio.cortar(linha, rastreio.LIMITE_TRECHO)}"
        for numero, linha in rastreio.linhas_com_termos(fontes.rascunho, padroes)
    ]
    pesquisa = _por_arquivo(fontes.pesquisa, padroes)
    outras = _por_arquivo(fontes.outras, padroes)
    saida += ["", "### Termos: " + ", ".join(f'"{termo}"' for termo in termos)]
    saida += _bloco("Decisões", decisoes) + _bloco("Pendências abertas", pendencias) + _bloco("Rascunho", rascunho)
    saida += _bloco("Pesquisa", pesquisa) + _bloco("Outras fontes", outras)

    nome_do_gate, itens = itens_do_gate(perfil, relativo, fontes.gates)
    saida += ["", f"### O que o gate {nome_do_gate} vai cobrar ({len(itens)})"]
    saida += [f"- {item.verificacao}: {frase_do_item(item)}" for item in itens]
    faltam = _sem_cobertura(raiz, perfil, fontes, relativo, itens)
    if faltam:
        saida += _bloco("IDs sem cobertura", faltam, LIMITE_SEM_COBERTURA, "###")

    contagens = (
        ("citações", len(citacoes)), ("IDs", len(ids)), ("decisões", len(decisoes)),
        ("pendências", len(pendencias)), ("pesquisa", len(pesquisa)), ("rascunho", len(rascunho)),
    )
    grupo = rastreio.grupo_do_status(fontes.status.get(relativo))
    # No em-revisao, a data é a da última aprovação; o documento nunca aprovado fica sem o bloco e sem o aviso.
    em_revisao = grupo == "em-revisao"
    data = data_da_aprovacao(fontes.decisoes, relativo) if em_revisao else fontes.datas.get(relativo, "")
    if grupo in _COM_RULINGS_NOVOS and (data or not em_revisao):
        if _RE_DATA.fullmatch(data):
            rulings, marcados = _rulings_depois(
                fontes.decisoes, data, perfil.caminhos.decisoes, _alvos_do_documento(termos, texto, perfil), perfil
            )
            saida += _bloco(f"{TITULO_RULINGS} de {data}", rulings, None, "###")
            contagens += ((ROTULO_RULINGS, len(rulings)), (ROTULO_PROVAVEIS, marcados))
        else:
            saida += ["", f"### {TITULO_RULINGS}", SEM_DATA]
            avisos.append(f"{SEM_DATA}: {relativo}")
    return Documento(
        relativo, tuple(saida), contagens, tuple(item.verificacao for item in itens), len(faltam), tuple(avisos)
    )


def montar(raiz: Path, perfil: Perfil, documentos: list[str]) -> Dossie:
    """Monta o dossiê dos documentos (relativos à raiz ou absolutos, sem repetição), grava o arquivo e devolve o
    resultado. Documento fora da pasta do planejamento lança checar.EntradaInvalida antes de gravar. A mesma entrada
    dá o mesmo arquivo."""
    relativos = list(dict.fromkeys(checar.mostrar(raiz, raiz / documento) for documento in documentos))
    for relativo in relativos:
        checar.resolver_molde(raiz, Path(relativo), perfil)
    fontes = _ler_fontes(raiz, perfil)
    cache: dict[str, list[str]] = {}
    resultado = tuple(_documento(raiz, perfil, fontes, relativo, cache) for relativo in relativos)
    nome = posixpath.basename(relativos[0])
    caminho = f"{PASTA_DOSSIE}/{nome[: -len('.md')] if nome.endswith('.md') else nome}.md"
    plural = "documento" if len(relativos) == 1 else "documentos"
    texto = [
        f"# Dossiê: {relativos[0]}",
        "",
        f"Gerado por harness.py dossie para {len(relativos)} {plural}; refeito a cada execução, não edite.",
        "",
    ]
    for documento in resultado:
        texto += list(documento.linhas) + [""]
    comum.escrever_texto(raiz / caminho, "\n".join(texto))
    return Dossie(caminho, resultado)


def resumo(dossie: Dossie) -> str:
    """Até LIMITE_RESUMO linhas: onde está o arquivo, uma linha por documento com as contagens e os itens do gate, e
    as linhas dos IDs sem cobertura e dos avisos."""
    nomes = [posixpath.basename(documento.relativo) for documento in dossie.documentos]
    largura = max(len(nome) for nome in nomes)
    plural = "documento" if len(nomes) == 1 else "documentos"
    saida = [f"Dossiê: {len(nomes)} {plural} em {dossie.caminho}"]
    for nome, documento in zip(nomes, dossie.documentos):
        contagens = " · ".join(f"{rotulo} {valor}" for rotulo, valor in documento.contagens)
        saida.append(f"{nome.ljust(largura)} {contagens} · gate: {', '.join(documento.gate) or '—'}")
    for nome, documento in zip(nomes, dossie.documentos):
        if documento.sem_cobertura:
            saida.append(f"{nome}: {documento.sem_cobertura} IDs sem cobertura, lista no arquivo")
        saida += [f"aviso: {aviso}" for aviso in documento.avisos]
    return "".join(linha + "\n" for linha in saida[:LIMITE_RESUMO])
