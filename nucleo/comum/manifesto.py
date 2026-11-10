"""Manifesto da passagem (spec 6b, §6.4 e §6.5): o formato, o trecho que define cada ID e o hash da lista de arquivos.

O manifesto acompanha a exportação e a passagem publicada: o hash de cada arquivo, o arquivo e as linhas de cada ID,
as áreas do código e as pendências abertas citadas. O mesmo commit dá os mesmos bytes.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
from dataclasses import dataclass

import campos
import comum

FORMATO = 1
# Os formatos do manifesto que este harness lê: o `importar`, o `gerar` e a invariante da cópia os conferem.
FORMATOS_LIDOS = (1,)
NOME = "manifesto.json"
PREFIXO_TAG = "passagem/v"
# Rótulo das issues de retorno no repositório de planejamento: é do contrato entre os dois repositórios.
ROTULO_RETORNO = "retorno"
GATILHO_EXPORTACAO = "exportação"
GATILHO_REVISAO = "revisão"


@dataclass(frozen=True)
class Origem:
    repositorio: str  # `<dono>/<repo>` do remoto `origin`, a outra URL como está, ou vazio sem remoto
    commit: str
    data: str  # a data do commit, AAAA-MM-DD
    gatilho: str
    pendencias_resolvidas: tuple[str, ...] = ()


@dataclass(frozen=True)
class Arquivo:
    caminho: str
    sha256: str


@dataclass(frozen=True)
class Definicao:
    arquivo: str
    linhas: tuple[int, int]  # a primeira e a última linha do trecho, a partir de 1
    sha256: str


@dataclass(frozen=True)
class Area:
    area: str
    pastas: tuple[str, ...]


@dataclass(frozen=True)
class Pendencia:
    id: str
    texto: str
    citada_em: tuple[str, ...]


@dataclass(frozen=True)
class Manifesto:
    formato: int
    versao: int | None
    origem: Origem
    arquivos: tuple[Arquivo, ...]
    ids: dict[str, Definicao]
    areas: tuple[Area, ...]
    pendencias: tuple[Pendencia, ...]


class ManifestoInvalido(Exception):
    """O texto não é um manifesto: JSON ilegível ou campo que falta. `motivo` cabe numa linha."""

    def __init__(self, motivo: str):
        super().__init__(motivo)
        self.motivo = motivo


def sha256(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


_RE_REMOTO_GITHUB = re.compile(
    r"(?:git@github\.com:|ssh://git@github\.com/|https://(?:[^@/\s]+@)?github\.com/)([^/\s]+/[^/\s]+?)(?:\.git)?/?"
)


def repositorio_do_remoto(url: str) -> str:
    """`<dono>/<repo>` da URL de um remoto do GitHub, por SSH ou HTTPS, com ou sem `.git`, credenciais e barra no fim.
    Outra URL fica como está, sem o usuário e a senha, que o manifesto não guarda."""
    achado = _RE_REMOTO_GITHUB.fullmatch(url)
    if achado:
        return achado.group(1)
    partes = urllib.parse.urlsplit(url)
    if partes.scheme and "@" in partes.netloc:
        return partes._replace(netloc=partes.netloc.rsplit("@", 1)[1]).geturl()
    return url


def _linhas_com_quebra(texto: str) -> list[str]:
    """As linhas partidas só em `\\n`, cada uma com a sua quebra; a última sem quebra, se houver, também."""
    partes = texto.split("\n")
    linhas = [parte + "\n" for parte in partes[:-1]]
    if partes[-1]:
        linhas.append(partes[-1])
    return linhas


_RE_TITULO = re.compile(r"(#{1,6}) ")


def _dentro_de_bloco(conteudos: list[str]) -> list[bool]:
    """Para cada linha, se ela é uma cerca de três crases ou fica entre duas."""
    marcas = []
    dentro = False
    for conteudo in conteudos:
        if conteudo.lstrip().startswith(campos.CERCA):
            dentro = not dentro
            marcas.append(True)
        else:
            marcas.append(dentro)
    return marcas


def _recuo(conteudo: str) -> int:
    return len(conteudo) - len(conteudo.lstrip())


def _abre_bloco(conteudo: str) -> bool:
    """A linha começa item de lista, título, linha de tabela ou cerca: não é continuação preguiçosa."""
    return bool(campos._RE_ITEM_DE_LISTA.fullmatch(conteudo) or _RE_TITULO.match(conteudo)
                or conteudo.lstrip().startswith(("|", campos.CERCA)))


def trecho(texto: str, linha: int) -> tuple[int, int]:
    """A primeira e a última linha, a partir de 1, do trecho que define o ID da `linha`.

    O título vai até a última linha não vazia antes do próximo título de nível igual ou acima, fora dos blocos de
    código, ou antes do fim, sem as linhas em branco do fim (spec 6b, §6.5, emendado); a linha de tabela é só ela; o
    item de lista leva as linhas de recuo maior e as continuações preguiçosas, e a linha vazia só quando alguma linha
    depois dela entra; qualquer outra linha é só ela.
    """
    conteudos = [bruta.rstrip("\n").rstrip("\r") for bruta in _linhas_com_quebra(texto)]
    atual = conteudos[linha - 1]
    titulo = _RE_TITULO.match(atual)
    if titulo:
        nivel = len(titulo.group(1))
        em_bloco = _dentro_de_bloco(conteudos)
        fim = len(conteudos)
        for numero in range(linha + 1, len(conteudos) + 1):
            outro = _RE_TITULO.match(conteudos[numero - 1])
            if outro and not em_bloco[numero - 1] and len(outro.group(1)) <= nivel:
                fim = numero - 1
                break
        while fim > linha and not conteudos[fim - 1].strip():
            fim -= 1
        return linha, fim
    if atual.lstrip().startswith("|") or not campos._RE_ITEM_DE_LISTA.fullmatch(atual):
        return linha, linha
    recuo = _recuo(atual)
    fim = linha
    for numero in range(linha + 1, len(conteudos) + 1):
        conteudo = conteudos[numero - 1]
        if not conteudo.strip():
            continue
        anterior_no_trecho = numero - 1 == fim
        if _recuo(conteudo) > recuo or (anterior_no_trecho and not _abre_bloco(conteudo)):
            fim = numero
        else:
            break
    return linha, fim


def definicao(caminho: str, texto: str, linha: int) -> Definicao:
    """O trecho do ID da `linha` com o `sha256` dos bytes UTF-8 das linhas dele, cada uma com a sua quebra."""
    inicio, fim = trecho(texto, linha)
    dados = "".join(_linhas_com_quebra(texto)[inicio - 1:fim]).encode("utf-8")
    return Definicao(caminho, (inicio, fim), sha256(dados))


def hash_dos_arquivos(arquivos: tuple[Arquivo, ...]) -> str:
    """O `sha256` da lista de arquivos em JSON, com as chaves ordenadas: não muda com a origem nem com a versão."""
    lista = [{"caminho": arquivo.caminho, "sha256": arquivo.sha256} for arquivo in arquivos]
    return sha256(json.dumps(lista, ensure_ascii=False, sort_keys=True).encode("utf-8"))


def para_json(m: Manifesto) -> str:
    """O manifesto em JSON com as chaves ordenadas, indentação de 2 e a quebra no fim."""
    dados = {
        "formato": m.formato,
        "versao": m.versao,
        "origem": {
            "repositorio": m.origem.repositorio,
            "commit": m.origem.commit,
            "data": m.origem.data,
            "gatilho": m.origem.gatilho,
            "pendencias_resolvidas": list(m.origem.pendencias_resolvidas),
        },
        "arquivos": [{"caminho": a.caminho, "sha256": a.sha256} for a in m.arquivos],
        "ids": {id_: {"arquivo": d.arquivo, "linhas": list(d.linhas), "sha256": d.sha256} for id_, d in m.ids.items()},
        "areas": [{"area": a.area, "pastas": list(a.pastas)} for a in m.areas],
        "pendencias": [{"id": p.id, "texto": p.texto, "citada_em": list(p.citada_em)} for p in m.pendencias],
    }
    return json.dumps(dados, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def formato_lido(formato) -> bool:
    """Se o `formato` é um dos `FORMATOS_LIDOS`; o booleano do JSON não conta como número."""
    return formato in FORMATOS_LIDOS and not isinstance(formato, bool)


def motivo_do_formato(formato) -> str:
    """`formato <f>; este harness lê o formato <lidos>`, com o `formato` em JSON e os lidos juntos por `ou`."""
    lidos = comum.juntar((str(lido) for lido in FORMATOS_LIDOS), "ou")
    return f"formato {json.dumps(formato)}; este harness lê o formato {lidos}"


def _campos(dados, nomes: tuple[str, ...], onde: str = "") -> None:
    """Recusa o primeiro campo de `nomes` que falta em `dados`, na ordem."""
    ausente = next((nome for nome in nomes if not isinstance(dados, dict) or nome not in dados), None)
    if ausente is not None:
        raise ManifestoInvalido(f"falta o campo {onde}{ausente}")


def _tipo(valor, tipo: type, nome: str) -> None:
    """Recusa o campo `nome` cujo valor não é uma lista (`list`) ou um objeto (`dict`) do JSON."""
    if not isinstance(valor, tipo):
        raise ManifestoInvalido(f"o campo {nome} não é {'uma lista' if tipo is list else 'um objeto'}")


def de_json(texto: str) -> Manifesto:
    """O manifesto lido do JSON. Recusa o JSON ilegível, o campo que falta, a lista ou o objeto de outro tipo e o
    `ids[].linhas` que não são dois inteiros com `1 <= primeira <= última`; o valor do `formato` fica com quem lê."""
    try:
        dados = json.loads(texto)
    except ValueError as erro:
        raise ManifestoInvalido(f"JSON ilegível: {erro}") from None
    _campos(dados, ("formato", "versao", "origem"))
    origem = dados["origem"]
    _campos(origem, ("repositorio", "commit", "data", "gatilho", "pendencias_resolvidas"), "origem.")
    _tipo(origem["pendencias_resolvidas"], list, "origem.pendencias_resolvidas")
    _campos(dados, ("arquivos", "ids", "areas", "pendencias"))
    for nome, tipo in (("arquivos", list), ("ids", dict), ("areas", list), ("pendencias", list)):
        _tipo(dados[nome], tipo, nome)
    for arquivo in dados["arquivos"]:
        _campos(arquivo, ("caminho", "sha256"), "arquivos.")
    for id_, definicao_ in dados["ids"].items():
        _campos(definicao_, ("arquivo", "linhas", "sha256"), "ids.")
        _tipo(definicao_["linhas"], list, "ids.linhas")
        linhas = definicao_["linhas"]
        if not (len(linhas) == 2 and all(isinstance(n, int) and not isinstance(n, bool) for n in linhas)
                and 1 <= linhas[0] <= linhas[1]):
            raise ManifestoInvalido(f"o campo ids.linhas de {id_} não é [primeira, última]: {json.dumps(linhas)}")
    for area in dados["areas"]:
        _campos(area, ("area", "pastas"), "areas.")
        _tipo(area["pastas"], list, "areas.pastas")
    for pendencia in dados["pendencias"]:
        _campos(pendencia, ("id", "texto", "citada_em"), "pendencias.")
        _tipo(pendencia["citada_em"], list, "pendencias.citada_em")
    return Manifesto(
        dados["formato"],
        dados["versao"],
        Origem(origem["repositorio"], origem["commit"], origem["data"], origem["gatilho"],
               tuple(origem["pendencias_resolvidas"])),
        tuple(Arquivo(a["caminho"], a["sha256"]) for a in dados["arquivos"]),
        {id_: Definicao(d["arquivo"], tuple(d["linhas"]), d["sha256"]) for id_, d in dados["ids"].items()},
        tuple(Area(a["area"], tuple(a["pastas"])) for a in dados["areas"]),
        tuple(Pendencia(p["id"], p["texto"], tuple(p["citada_em"])) for p in dados["pendencias"]),
    )
