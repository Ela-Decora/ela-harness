"""Aceitação do bloco (spec 6c, §12): a seção da spec, o `aceitacao.md`, a conferência das provas por HTTP e a anotação
dos itens manuais.

A seção `## Verificação externa` da spec do bloco traz `nenhuma` ou os itens, cada um com a prova, automática ou
manual, e o momento, antes ou depois do merge. O `aceitacao.md` é a tabela desses itens, com o resultado e a data de
cada um; na tabela, o `|` de uma célula sai como `\\|`.

A prova automática é `<alias> GET|HEAD|POST <caminho> -> <código>`, e o subitem `pedido:` traz, num bloco json, os
`cabecalhos`, o `corpo` e os `campos` esperados na resposta (spec prova-por-post). O marcador `{env.NOME}` é trocado
só na hora da requisição, pelo valor do ambiente do processo ou dos arquivos de env da lane. A conferência lê o pedido
do `spec.md` com o hash aprovado no `estado.md`, e o valor das variáveis não vai para a saída, para o `aceitacao.md`
nem para um commit.
"""
from __future__ import annotations

import dataclasses
import http.client
import json
import re
import socket
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections import ChainMap
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import bloco
import campos
import comum
from perfil_desenvolvimento import RE_MARCADOR

ARQUIVO = bloco.ARQUIVO_DA_ACEITACAO
SECAO = "## Verificação externa"
NENHUMA = "nenhuma"
MANUAL = "manual"
ANTES = "antes"
DEPOIS = "depois"
SEM = "—"
RE_PROVA = re.compile(r"([a-z][a-z0-9-]*)\s+(GET|HEAD|POST)\s+(/\S*)\s*->\s*(\d{3})")
FORMA_DA_PROVA = "<alias> GET|HEAD|POST <caminho> -> <código>"
# O marcador de variável de ambiente, no caminho da prova e nos textos dos `cabecalhos` e do `corpo` do pedido.
RE_ENV = re.compile(r"\{env\.([A-Z_][A-Z0-9_]*)\}")
SEM_VERIFICACAO = "Sem verificação externa."
CABECALHO = ("| # | Item | Prova | Quando | Resultado | Data |", "|---|---|---|---|---|---|")
OK = "ok"
FALHOU = "falhou"

AJUDA = """\
Confere e anota a aceitação do bloco da lane, no `aceitacao.md` da pasta do bloco, que o bloco planejado gera da seção
`## Verificação externa` da spec do bloco. Roda só dentro da lane, reconhecida pelos arquivos.

- `conferir`: confere os itens de antes do merge com prova automática, `<alias> GET|HEAD|POST <caminho> -> <código>`.
  A URL é o alias da prova, de `aceitacao.aliases`, com cada `{porta.<nome>}` trocado pela porta da lane, mais o
  caminho. Com algum item automático do momento, o pedido de cada item vem do subitem `pedido:` do `spec.md` do bloco,
  que tem de ter o hash do `spec` do `estado.md`; diferente, ou sem o `spec.md`, a recusa é
  `aceitacao conferir: spec.md mudou depois da aprovação; rode harness.py bloco replanejar`, sem gravar nada. O pedido
  traz os `cabecalhos`; o `corpo`, só no POST, em JSON, com `Content-Type: application/json` quando os cabeçalhos não
  trazem outro; e os `campos` esperados no JSON da resposta, em que `"*"` quer dizer presente e não nulo. Cada
  `{env.NOME}` do caminho, dos cabeçalhos e do corpo é trocado pelo valor da variável: do ambiente do processo e, sem
  ela, do primeiro arquivo de env da lane que a define, cada `env_copiados` na ordem e depois o `.env` gerado do
  `env_modelo`. O valor não vai para a saída, para o arquivo nem para o commit; no caminho, entra codificado para URL.
  A requisição vai direto, sem o proxy do ambiente, e não segue redirecionamento: o 3xx conta como o código. O tempo
  limite é o `aceitacao.tempo_limite`. O resultado é `ok`, com o código esperado e os campos conferidos,
  `falhou: <código>`, `falhou: sem resposta (<motivo>)`, `falhou: passou de <t> s`, `falhou: sem a variável NOME` ou
  `falhou: variável NOME com quebra de linha`, sem requisição, `falhou: resposta sem JSON`,
  `falhou: sem o campo <caminho>` ou `falhou: campo <caminho> diferente do esperado`. O Resultado e a Data dos itens
  conferidos vão para o arquivo, num commit `chore(<ID>): aceitação` só com ele, que deixa o resto do índice como
  estava; sem mudança no arquivo, não há commit.
- `conferir --depois`: confere os itens de depois do merge, com o mesmo pedido e a mesma recusa da spec mudada, só
  imprimindo, sem gravar nem fazer commit.
- `anotar <n> ok|falhou "<nota>"`: grava `ok: <nota>` ou `falhou: <nota>`, com a nota numa linha, e a Data no item
  manual de antes do merge, com o mesmo commit; a guarda pede a confirmação do usuário. Recusa o item que não existe, o
  de prova automática e o de depois do merge, que se anota no `harness.py lane fechar --manual`.

A saída traz uma linha `<n> <prova>: <resultado>` por item do momento e o veredito na última:
`ACEITACAO OK: <n> item(ns)`; `ACEITACAO MANUAL: <k> de <n> item(ns): <números>`, quando todo item pendente de antes
do merge é manual e ainda sem resultado; ou `ACEITACAO PENDENTE: <k> de <n> item(ns): <números>`. Os manuais de antes
contam pelo Resultado gravado, e o `—` é pendente; no `--depois`, os manuais contam como pendentes. O `conferir` sai
com 0 no OK e com 1 no MANUAL e no PENDENTE; o `anotar` imprime o item anotado e o veredito de antes e sai com 0.

Fora de lane, a recusa é `fora de lane: rode dentro da lane do bloco`; sem o arquivo,
`<blocos>/<pasta>/aceitacao.md não existe; o bloco planejado o gera`; com um alias que saiu do perfil depois da
geração, `item <n>: alias <alias> não está em aceitacao.aliases`, sem gravar nada. No `conferir`, as linhas saem antes
do commit: com ele recusado, a recusa vem depois delas.
"""

_QUANDO = {"antes do merge": ANTES, "depois do merge": DEPOIS}
# O título, com o ID na forma do `id` do `estado.md`.
_RE_TITULO = re.compile(r"# Aceitação: ([A-Z]{2,}-[0-9]{2,})")
_RE_SUBITEM = re.compile(r"(prova|quando|pedido):\s*(.*)")
# Um trecho que começa como marcador: de `{env.` até o primeiro `}`, inclusive, ou até o fim do texto.
_RE_TRECHO_DE_ENV = re.compile(r"\{env\.[^}]*\}?")
# O caminho de um campo: segmentos separados por ponto, cada um com o nome e, opcionalmente, `[]` ou `[<n>]`.
_RE_CAMPO = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*(?:\[\]|\[[0-9]+\])?(?:\.[A-Za-z_][A-Za-z0-9_-]*(?:\[\]|\[[0-9]+\])?)*")
_CHAVES_DO_PEDIDO = ("cabecalhos", "corpo", "campos")
# Um segmento do caminho de um campo: o nome e o `[]` ou o índice.
_RE_SEGMENTO = re.compile(r"([A-Za-z_][A-Za-z0-9_-]*)(\[\]|\[([0-9]+)\])?")
# O esperado que quer dizer presente e não nulo.
PRESENTE = "*"
# O `|` que separa as células: o que não vem depois de `\`.
_RE_SEPARADOR = re.compile(r"(?<!\\)\|")


@dataclass(frozen=True)
class Item:
    """Um item da verificação externa. A `prova` é `manual` ou `<alias> <método> <caminho> -> <código>`, com um espaço
    entre as partes; o `quando`, `antes` ou `depois`."""

    numero: int
    descricao: str
    prova: str
    quando: str
    resultado: str = SEM
    data: str = SEM


@dataclass(frozen=True)
class Tabela:
    """O `aceitacao.md`: o ID do bloco e os itens, na ordem."""

    id: str
    itens: tuple[Item, ...]


@dataclass(frozen=True)
class Pedido:
    """O pedido do item, do subitem `pedido:`: os cabeçalhos e os campos esperados, na ordem do JSON, e o corpo, que
    vale só com `tem_corpo`. Os marcadores `{env.NOME}` ficam como estão; a troca é na hora da requisição."""

    cabecalhos: tuple[tuple[str, str], ...] = ()
    tem_corpo: bool = False
    corpo: object = None
    campos: tuple[tuple[str, object], ...] = ()


@dataclass
class _ItemAberto:
    numero: int
    descricao: str
    prova: str | None = None
    quando: str | None = None
    pedido: Pedido | None = None


def _marcadores(texto: str, numero: int) -> None:
    """Recusa o primeiro trecho `{env.` do texto fora da forma `{env.NOME}`."""
    for trecho in _RE_TRECHO_DE_ENV.findall(texto):
        if not RE_ENV.fullmatch(trecho):
            raise bloco.Recusa(f"item {numero}: marcador fora da forma {{env.NOME}}: {trecho}")


def _textos(valor: object):
    """Os textos de um valor JSON, em qualquer profundidade; as chaves dos objetos ficam de fora."""
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, dict):
        for dentro in valor.values():
            yield from _textos(dentro)
    elif isinstance(valor, list):
        for dentro in valor:
            yield from _textos(dentro)


def _bloco_json(linhas: list[str], numero_da_linha: int) -> str | None:
    """O texto do bloco ```` ```json ```` logo abaixo da linha `numero_da_linha` (a partir de 1), sem o recuo da cerca
    de abertura e com espaço no fim da cerca aceito, ou None sem ele."""
    if numero_da_linha >= len(linhas) or linhas[numero_da_linha].strip() != f"{campos.CERCA}json":
        return None
    abertura = linhas[numero_da_linha]
    recuo = abertura[:len(abertura) - len(abertura.lstrip())]
    dentro = []
    for linha in linhas[numero_da_linha + 1:]:
        if linha.lstrip().startswith(campos.CERCA):
            return "\n".join(dentro)
        dentro.append(linha[len(recuo):] if linha.startswith(recuo) else linha)
    return None


def _pedido(linhas: list[str], numero_da_linha: int, numero: int) -> Pedido:
    """O pedido do bloco JSON abaixo do subitem, com as checagens que não dependem do método."""
    texto = _bloco_json(linhas, numero_da_linha)
    if texto is None:
        raise bloco.Recusa(f"item {numero}: pedido sem o bloco json logo abaixo")
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as erro:
        raise bloco.Recusa(
            f"item {numero}: pedido com JSON inválido: {erro.msg} (linha {erro.lineno}, coluna {erro.colno})"
        ) from None
    if not isinstance(dados, dict):
        raise bloco.Recusa(f"item {numero}: pedido deve ser um objeto")
    desconhecida = next((chave for chave in dados if chave not in _CHAVES_DO_PEDIDO), None)
    if desconhecida is not None:
        raise bloco.Recusa(f"item {numero}: pedido com chave desconhecida: {desconhecida}")
    cabecalhos = dados.get("cabecalhos", {})
    if not isinstance(cabecalhos, dict) or not all(isinstance(valor, str) for valor in cabecalhos.values()):
        raise bloco.Recusa(f"item {numero}: cabecalhos deve ser um objeto de textos")
    campos_ = dados.get("campos")
    if "campos" in dados and (not isinstance(campos_, dict) or not campos_):
        raise bloco.Recusa(f"item {numero}: campos deve ser um objeto não vazio")
    for caminho in campos_ or {}:
        if not _RE_CAMPO.fullmatch(caminho):
            raise bloco.Recusa(f"item {numero}: campo fora da forma: {caminho}")
    for texto_ in (*cabecalhos.values(), *_textos(dados.get("corpo"))):
        _marcadores(texto_, numero)
    return Pedido(tuple(cabecalhos.items()), "corpo" in dados, dados.get("corpo"), tuple((campos_ or {}).items()))


def _prova(valor: str, numero: int, perfil) -> str:
    """A prova do subitem, sem as crases das pontas, conferida e com um espaço entre as partes."""
    if len(valor) >= 2 and valor.startswith("`") and valor.endswith("`"):
        valor = valor[1:-1].strip()
    if valor == MANUAL:
        return MANUAL
    achado = RE_PROVA.fullmatch(valor)
    if achado is None:
        raise bloco.Recusa(f"item {numero}: prova fora da forma {FORMA_DA_PROVA}: {valor}")
    alias, metodo, caminho, codigo = achado.groups()
    if alias not in dict(perfil.aceitacao.aliases):
        raise bloco.Recusa(f"item {numero}: alias {alias} não está em aceitacao.aliases")
    _marcadores(caminho, numero)
    return f"{alias} {metodo} {caminho} -> {codigo}"


def _subitem(aberto: _ItemAberto, texto: str, perfil, linhas: list[str], numero_da_linha: int) -> None:
    """O subitem da linha `numero_da_linha` (a partir de 1) das `linhas` cruas da spec, onde o `pedido:` busca o
    bloco JSON."""
    achado = _RE_SUBITEM.fullmatch(texto)
    if achado is None or (achado.group(1) == "pedido" and achado.group(2).strip()):
        raise bloco.Recusa(f"item {aberto.numero}: subitem fora da forma: {texto}")
    valor = achado.group(2).strip()
    if achado.group(1) == "pedido":
        if aberto.pedido is not None:
            raise bloco.Recusa(f"item {aberto.numero}: pedido repetido")
        aberto.pedido = _pedido(linhas, numero_da_linha, aberto.numero)
        return
    if achado.group(1) == "prova":
        if aberto.prova is not None:
            raise bloco.Recusa(f"item {aberto.numero}: prova repetida")
        aberto.prova = _prova(valor, aberto.numero, perfil)
        return
    if aberto.quando is not None:
        raise bloco.Recusa(f"item {aberto.numero}: quando repetido")
    if valor not in _QUANDO:
        raise bloco.Recusa(f"item {aberto.numero}: quando ilegível: {valor}")
    aberto.quando = _QUANDO[valor]


def _fechar(aberto: _ItemAberto) -> Item:
    """O item, com as checagens do pedido que dependem do método da prova."""
    if aberto.prova is None:
        raise bloco.Recusa(f"item {aberto.numero} sem prova")
    pedido = aberto.pedido
    if pedido is not None:
        if aberto.prova == MANUAL:
            raise bloco.Recusa(f"item {aberto.numero}: pedido na prova manual")
        metodo = aberto.prova.split()[1]
        if pedido.tem_corpo and metodo != "POST":
            raise bloco.Recusa(f"item {aberto.numero}: corpo vale só no POST")
        if pedido.campos and metodo == "HEAD":
            raise bloco.Recusa(f"item {aberto.numero}: campos não vale no HEAD")
    return Item(aberto.numero, aberto.descricao, aberto.prova, aberto.quando or ANTES)


def itens_da_spec(texto: str, perfil) -> tuple[Item, ...]:
    """Os itens da seção `## Verificação externa` da spec do bloco, com os aliases do perfil; `nenhuma` dá `()`.

    Nas linhas não vazias da seção, cada uma é o item de primeiro nível, sem recuo; o subitem, item de lista recuado;
    ou a continuação da descrição, linha recuada logo depois dela ou de outra continuação. A recusa,
    `Recusa(<motivo>)`, sai no primeiro problema, na ordem das linhas, e a falta da prova e as checagens do pedido que
    dependem do método, no fim do item."""
    return _ler_secao(texto, perfil)[0]


def pedidos_da_spec(texto: str, perfil) -> dict[int, Pedido]:
    """Os pedidos dos itens da seção `## Verificação externa` que têm o subitem `pedido:`, pelo número do item, com as
    mesmas recusas do `itens_da_spec`."""
    return _ler_secao(texto, perfil)[1]


def _ler_secao(texto: str, perfil) -> tuple[tuple[Item, ...], dict[int, Pedido]]:
    secao = next((linhas for _, titulo, linhas in campos.secoes(texto, SECAO) if titulo == SECAO), None)
    if secao is None:
        raise bloco.Recusa(f"spec.md sem a seção {SECAO}")
    linhas = [(numero, linha) for numero, linha in secao[1:] if linha.strip()]
    if not linhas:
        raise bloco.Recusa(f"{SECAO} vazia: escreva {NENHUMA} ou os itens")
    if len(linhas) == 1 and linhas[0][1].strip() == NENHUMA:
        return (), {}
    cruas = campos._linhas(texto)
    itens: list[Item] = []
    pedidos: dict[int, Pedido] = {}
    aberto: _ItemAberto | None = None
    na_descricao = False

    def fechar(aberto: _ItemAberto) -> None:
        itens.append(_fechar(aberto))
        if aberto.pedido is not None:
            pedidos[aberto.numero] = aberto.pedido

    for numero, linha in linhas:
        item = campos._RE_ITEM_DE_LISTA.fullmatch(linha)
        recuado = linha[:1].isspace()
        if item and not recuado:
            if aberto is not None:
                fechar(aberto)
            aberto = _ItemAberto(len(itens) + 1, (item.group(2) or "").strip())
            na_descricao = True
        elif item and aberto is not None:
            _subitem(aberto, (item.group(2) or "").strip(), perfil, cruas, numero)
            na_descricao = False
        elif recuado and na_descricao:
            aberto.descricao = f"{aberto.descricao} {linha.strip()}"
        else:
            raise bloco.Recusa(f"{SECAO}: linha fora da forma: {linha.strip()}")
    fechar(aberto)
    return tuple(itens), pedidos


def _celula(texto: str) -> str:
    return texto.replace("|", "\\|")


def para_texto(tabela: Tabela) -> str:
    """O `aceitacao.md` da tabela: o título e a tabela dos itens, ou a linha `Sem verificação externa.`"""
    linhas = [f"# Aceitação: {tabela.id}", ""]
    if not tabela.itens:
        linhas.append(SEM_VERIFICACAO)
    else:
        linhas.extend(CABECALHO)
        for item in tabela.itens:
            celulas = (str(item.numero), item.descricao, item.prova, item.quando, item.resultado, item.data)
            linhas.append("| " + " | ".join(_celula(celula) for celula in celulas) + " |")
    return "\n".join(linhas) + "\n"


def gerar(texto_da_spec: str, id_: str, perfil) -> str:
    """O `aceitacao.md` dos itens da spec do bloco, com `—` no Resultado e na Data."""
    return para_texto(Tabela(id_, itens_da_spec(texto_da_spec, perfil)))


def _celulas(linha: str) -> list[str] | None:
    """As células da linha da tabela, com o `\\|` de volta a `|`, ou None fora da forma de seis células."""
    partes = _RE_SEPARADOR.split(linha.strip())
    if len(partes) != 8 or partes[0] or partes[-1]:
        return None
    return [parte.strip().replace("\\|", "|") for parte in partes[1:-1]]


def ler(texto: str, caminho: str) -> Tabela:
    """A tabela do `aceitacao.md`; fora da forma, `Recusa("<caminho>: aceitacao.md inválido: <motivo>")`."""
    def recusa(motivo: str) -> bloco.Recusa:
        return bloco.Recusa(f"{caminho}: aceitacao.md inválido: {motivo}")

    linhas = [linha.rstrip("\r") for linha in texto.split("\n")]
    titulo = _RE_TITULO.fullmatch(linhas[0])
    if titulo is None:
        raise recusa("sem o título # Aceitação: <ID>")
    resto = [linha.strip() for linha in linhas[1:] if linha.strip()]
    if resto[:1] == [SEM_VERIFICACAO]:
        if len(resto) > 1:
            raise recusa(f"linha fora da forma: {resto[1]}")
        return Tabela(titulo.group(1), ())
    if tuple(resto[:2]) != CABECALHO:
        raise recusa(f"sem a tabela nem a linha {SEM_VERIFICACAO}")
    itens = []
    for esperado, linha in enumerate(resto[2:], start=1):
        celulas = _celulas(linha)
        if celulas is None or not re.fullmatch(r"[0-9]+", celulas[0]):
            raise recusa(f"linha fora da forma: {linha}")
        numero, descricao, prova, quando, resultado, data = celulas
        if int(numero) != esperado:
            raise recusa(f"item {numero} fora de ordem")
        if prova != MANUAL and not RE_PROVA.fullmatch(prova):
            raise recusa(f"prova fora da forma: {prova}")
        if quando not in (ANTES, DEPOIS):
            raise recusa(f"quando fora da forma: {quando}")
        itens.append(Item(esperado, descricao, prova, quando, resultado, data))
    return Tabela(titulo.group(1), tuple(itens))


@dataclass(frozen=True)
class Resultado:
    """A conferência: as linhas `<n> <prova>: <resultado>` dos itens do momento, na ordem, com o veredito na última; a
    tabela a gravar; e se o veredito é OK."""

    linhas: tuple[str, ...]
    tabela: Tabela
    ok: bool


def url(perfil, prova: str, numero_da_lane: int, variaveis: Mapping[str, str] | None = None) -> str:
    """O alias da prova, com cada `{porta.<nome>}` trocado pela porta da lane, mais o caminho, com cada `{env.NOME}`
    trocado pelo valor da variável, codificado para URL sem caractere seguro. Quem chama garante que as variáveis
    existem."""
    alias, _, caminho, _ = RE_PROVA.fullmatch(prova).groups()
    variaveis = {} if variaveis is None else variaveis
    caminho = RE_ENV.sub(lambda marcador: urllib.parse.quote(variaveis[marcador.group(1)], safe=""), caminho)

    def porta(marcador) -> str:
        nome = marcador.group(1)
        if not nome.startswith("porta."):
            return marcador.group(0)
        return str(perfil.lane.porta(nome[len("porta."):], numero_da_lane))

    return RE_MARCADOR.sub(porta, dict(perfil.aceitacao.aliases)[alias]) + caminho


def precisa_da_spec(tabela: Tabela, depois: bool) -> bool:
    """Se algum item do momento tem prova automática: só então a conferência lê o pedido da spec aprovada."""
    momento = DEPOIS if depois else ANTES
    return any(item.quando == momento and item.prova != MANUAL for item in tabela.itens)


def pedidos_aprovados(dados: bytes | None, aprovado: str, perfil, comando: str) -> dict[int, Pedido]:
    """Os pedidos da spec do bloco, pelo `pedidos_da_spec`, com os `dados` do `spec.md` conferidos contra o hash
    `aprovado`, o `spec` do `estado.md`; sem os `dados` ou com outro hash,
    `Recusa("<comando>: spec.md mudou depois da aprovação; rode harness.py bloco replanejar")`."""
    if dados is None or bloco.hash_da_spec(dados) != aprovado:
        raise bloco.Recusa(f"{comando}: spec.md mudou depois da aprovação; rode harness.py bloco replanejar")
    return pedidos_da_spec(dados.decode("utf-8"), perfil)


def ler_env(texto: str) -> dict[str, str]:
    """As variáveis de um arquivo de env: linhas `NOME=valor`, com `export ` opcional na frente. As vazias, as que
    começam por `#`, as sem `=` e as de nome vazio são puladas; o nome e o valor saem sem os espaços das pontas, e as
    aspas, simples ou duplas, só quando as duas pontas do valor têm a mesma. O BOM do começo do arquivo é ignorado.
    Nada mais é interpretado; a última definição de um nome vale."""
    lidas: dict[str, str] = {}
    for linha in texto.removeprefix("\ufeff").split("\n"):
        linha = linha.strip()
        if linha.startswith("#"):
            continue
        if linha.startswith("export "):
            linha = linha[len("export "):]
        nome, igual, valor = linha.partition("=")
        nome, valor = nome.strip(), valor.strip()
        if not igual or not nome:
            continue
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        lidas[nome] = valor
    return lidas


def variaveis(pasta: Path | None, perfil, ambiente: Mapping[str, str]) -> Mapping[str, str]:
    """As variáveis que o marcador `{env.NOME}` troca: o `ambiente` primeiro e depois cada arquivo de
    `lane.arquivos_de_env` que existe e se lê na `pasta`, na ordem; a primeira definição vale. Sem `pasta`, só o
    `ambiente`."""
    mapas = [dict(ambiente)]
    if pasta is not None:
        ler = comum.leitor_do_disco(pasta)
        for arquivo in perfil.lane.arquivos_de_env:
            lido = ler(arquivo)
            if lido is not None:
                mapas.append(ler_env(lido))
    return ChainMap(*mapas)


class _SemRedirecionamento(urllib.request.HTTPRedirectHandler):
    """Não segue o redirecionamento: o 3xx sai como `HTTPError`, com o código dele."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def provar(metodo: str, url_: str, esperado: int, tempo: int, cabecalhos: tuple[tuple[str, str], ...] = (),
           corpo: bytes | None = None, campos: tuple[tuple[str, object], ...] = ()) -> str:
    """A requisição `GET`, `HEAD` ou `POST`, com os `cabecalhos` e o `corpo` do pedido, já com as variáveis trocadas,
    sem proxy e sem seguir redirecionamento: `ok` com o código esperado e os `campos` da resposta conferidos; senão,
    `falhou: <código>`, `falhou: sem resposta (<motivo>)`, `falhou: passou de <tempo> s`, `falhou: resposta sem JSON`,
    `falhou: sem o campo <caminho>` ou `falhou: campo <caminho> diferente do esperado`. A exceção da requisição que
    não é de rede sai só com o nome do tipo, porque o texto dela pode trazer o valor de uma variável."""
    abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}), _SemRedirecionamento())
    pedido = urllib.request.Request(url_, data=corpo, headers=dict(cabecalhos), method=metodo)
    try:
        try:
            resposta = abridor.open(pedido, timeout=tempo)
        except urllib.error.HTTPError as erro:
            resposta = erro
        try:
            codigo = resposta.getcode()
            lido = resposta.read() if campos else b""
        finally:
            resposta.close()
    except urllib.error.URLError as erro:
        if isinstance(erro.reason, socket.timeout):
            return f"{FALHOU}: passou de {tempo} s"
        motivo = comum.motivo_do_sistema(erro.reason) if isinstance(erro.reason, OSError) else str(erro.reason)
        return f"{FALHOU}: sem resposta ({motivo})"
    except (ValueError, http.client.HTTPException) as erro:  # inclui a porta que responde, mas não em HTTP
        return f"{FALHOU}: sem resposta ({type(erro).__name__})"
    except socket.timeout:
        return f"{FALHOU}: passou de {tempo} s"
    except OSError as erro:
        return f"{FALHOU}: sem resposta ({comum.motivo_do_sistema(erro)})"
    if codigo != esperado:
        return f"{FALHOU}: {codigo}"
    if not campos:
        return OK
    try:
        dado = json.loads(lido.decode("utf-8"))
    except ValueError:
        return f"{FALHOU}: resposta sem JSON"
    for caminho, valor in campos:
        falha = _campo(dado, caminho, valor)
        if falha is not None:
            return f"{FALHOU}: {falha}"
    return OK


def _igual(obtido: object, esperado: object) -> bool:
    """A igualdade do campo: recursiva; o booleano só é igual a booleano, em qualquer profundidade; o resto, pelo
    `==`, com número igual a número pelo valor."""
    if isinstance(obtido, bool) or isinstance(esperado, bool):
        return isinstance(obtido, bool) and isinstance(esperado, bool) and obtido == esperado
    if isinstance(obtido, dict) and isinstance(esperado, dict):
        return obtido.keys() == esperado.keys() and all(_igual(obtido[chave], esperado[chave]) for chave in obtido)
    if isinstance(obtido, list) and isinstance(esperado, list):
        return len(obtido) == len(esperado) and all(_igual(um, outro) for um, outro in zip(obtido, esperado))
    return obtido == esperado


def _campo(dado: object, caminho: str, esperado: object) -> str | None:
    """A falha do campo no JSON da resposta, `sem o campo <caminho>` ou `campo <caminho> diferente do esperado`, ou
    None quando ele confere. O `[]` vale em cada elemento da lista, que não pode vir vazia, e a primeira falha sai;
    o esperado `*` quer dizer presente e não nulo."""
    segmentos = [_RE_SEGMENTO.fullmatch(segmento).groups() for segmento in caminho.split(".")]

    def conferir_(valor: object, resto: list) -> str | None:
        if not resto:
            if (valor is None) if esperado == PRESENTE else not _igual(valor, esperado):
                return f"campo {caminho} diferente do esperado"
            return None
        (nome, colchetes, indice), resto = resto[0], resto[1:]
        if not isinstance(valor, dict) or nome not in valor:
            return f"sem o campo {caminho}"
        valor = valor[nome]
        if colchetes is None:
            return conferir_(valor, resto)
        if not isinstance(valor, list) or not valor or (indice is not None and int(indice) >= len(valor)):
            return f"sem o campo {caminho}"
        if indice is not None:
            return conferir_(valor[int(indice)], resto)
        return next((falha for falha in (conferir_(elemento, resto) for elemento in valor) if falha is not None), None)

    return conferir_(dado, segmentos)


def _aprovado(item: Item) -> bool:
    return item.resultado == OK or item.resultado.startswith(f"{OK}: ")


def pendentes(tabela: Tabela, depois: bool) -> list[int]:
    """Os números dos itens do momento que não estão aprovados pelo Resultado gravado; no `depois`, os manuais são
    sempre pendentes."""
    momento = DEPOIS if depois else ANTES
    return [item.numero for item in tabela.itens
            if item.quando == momento and (not _aprovado(item) or (depois and item.prova == MANUAL))]


def veredito(tabela: Tabela, depois: bool) -> str:
    """O veredito sobre os itens do momento, pelos `pendentes`. Antes do merge, o `ACEITACAO MANUAL` vale quando todo
    pendente é manual e ainda sem resultado."""
    momento = DEPOIS if depois else ANTES
    itens = [item for item in tabela.itens if item.quando == momento]
    abertos = pendentes(tabela, depois)
    so_manual = not depois and abertos and all(
        item.prova == MANUAL and item.resultado == SEM for item in itens if item.numero in abertos)
    if so_manual:
        return f"ACEITACAO MANUAL: {len(abertos)} de {len(itens)} item(ns): {', '.join(str(n) for n in abertos)}"
    return _veredito(itens, abertos)


def _veredito(itens: list[Item], pendentes_: list[int]) -> str:
    abertos = [str(numero) for numero in pendentes_]
    if not abertos:
        return f"ACEITACAO OK: {len(itens)} item(ns)"
    return f"ACEITACAO PENDENTE: {len(abertos)} de {len(itens)} item(ns): {', '.join(abertos)}"


def _trocado(valor: object, variaveis: Mapping[str, str]) -> object:
    """O valor JSON com cada `{env.NOME}` dos textos trocado pelo valor da variável; as chaves ficam como estão."""
    if isinstance(valor, str):
        return RE_ENV.sub(lambda marcador: variaveis[marcador.group(1)], valor)
    if isinstance(valor, dict):
        return {chave: _trocado(dentro, variaveis) for chave, dentro in valor.items()}
    if isinstance(valor, list):
        return [_trocado(dentro, variaveis) for dentro in valor]
    return valor


def _provado(item: Item, perfil, numero_da_lane: int, hoje: str, pedido: Pedido | None,
             variaveis: Mapping[str, str]) -> Item:
    """O item de prova automática com o Resultado da requisição e a Data. A variável que falta, no caminho, nos
    cabeçalhos ou no corpo, nessa ordem, e a quebra de linha numa variável de cabeçalho dão a falha sem requisição; o
    valor que o UTF-8 não codifica, no caminho ou no corpo, dá `sem resposta (UnicodeEncodeError)`, também sem
    requisição."""
    alias, metodo, caminho, codigo = RE_PROVA.fullmatch(item.prova).groups()
    if alias not in dict(perfil.aceitacao.aliases):  # o perfil mudou depois da geração
        raise bloco.Recusa(f"item {item.numero}: alias {alias} não está em aceitacao.aliases")
    pedido = Pedido() if pedido is None else pedido
    textos = (caminho, *(valor for _, valor in pedido.cabecalhos),
              *(_textos(pedido.corpo) if pedido.tem_corpo else ()))
    nomes = [nome for texto in textos for nome in RE_ENV.findall(texto)]
    nos_cabecalhos = [nome for _, valor in pedido.cabecalhos for nome in RE_ENV.findall(valor)]
    falta = next((nome for nome in nomes if nome not in variaveis), None)
    quebra = next((nome for nome in nos_cabecalhos if {"\r", "\n"} & set(variaveis.get(nome, ""))), None)
    if falta is not None:
        obtido = f"{FALHOU}: sem a variável {falta}"
    elif quebra is not None:
        obtido = f"{FALHOU}: variável {quebra} com quebra de linha"
    else:
        cabecalhos = [(nome, _trocado(valor, variaveis)) for nome, valor in pedido.cabecalhos]
        corpo = None
        try:
            if pedido.tem_corpo:
                corpo = json.dumps(_trocado(pedido.corpo, variaveis), ensure_ascii=False).encode("utf-8")
                if not any(nome.lower() == "content-type" for nome, _ in cabecalhos):
                    cabecalhos.append(("Content-Type", "application/json"))
            endereco = url(perfil, item.prova, numero_da_lane, variaveis)
        except UnicodeEncodeError:  # o valor tem um byte que o UTF-8 não codifica; a mensagem da exceção o traria
            obtido = f"{FALHOU}: sem resposta (UnicodeEncodeError)"
        else:
            obtido = provar(metodo, endereco, int(codigo), perfil.aceitacao.tempo_limite, tuple(cabecalhos), corpo,
                            pedido.campos)
    return dataclasses.replace(item, resultado=obtido, data=hoje)


def conferir(tabela: Tabela, perfil, numero_da_lane: int, depois: bool, hoje: str,
             pedidos: dict[int, Pedido] | None = None, variaveis: Mapping[str, str] | None = None) -> Resultado:
    """Confere as provas automáticas dos itens do momento, com o tempo limite do perfil, o pedido do item, dos
    `pedidos` pelo número, e as `variaveis` que os marcadores `{env.NOME}` trocam. Sem `depois`, a tabela volta com o
    Resultado e a Data delas; com `depois`, volta como veio, e o veredito sai dos resultados novos. As linhas e a
    tabela trazem a prova com o marcador, nunca o valor."""
    momento = DEPOIS if depois else ANTES
    pedidos = {} if pedidos is None else pedidos
    variaveis = {} if variaveis is None else variaveis
    itens = []
    linhas = []
    for item in tabela.itens:
        if item.quando == momento:
            if item.prova != MANUAL:
                item = _provado(item, perfil, numero_da_lane, hoje, pedidos.get(item.numero), variaveis)
            linhas.append(f"{item.numero} {item.prova}: {item.resultado}")
        itens.append(item)
    conferida = Tabela(tabela.id, tuple(itens))
    final = veredito(conferida, depois)
    return Resultado((*linhas, final), tabela if depois else conferida, final.startswith("ACEITACAO OK"))


def depois_do_merge(tabela: Tabela, perfil, numero_da_lane: int, manuais: dict[int, str], hoje: str,
                    pedidos: dict[int, Pedido] | None = None,
                    variaveis: Mapping[str, str] | None = None) -> Resultado:
    """A aceitação do `lane fechar`: os `manuais` (`ok` ou `falhou`) conferidos antes de qualquer prova, as provas
    automáticas de depois do merge, com os `pedidos` e as `variaveis` como no `conferir`, e o veredito com os manuais
    aplicados; a tabela volta como veio."""
    pedidos = {} if pedidos is None else pedidos
    variaveis = {} if variaveis is None else variaveis
    por_numero = {item.numero: item for item in tabela.itens}
    for numero in manuais:
        item = por_numero.get(numero)
        if item is None:
            raise bloco.Recusa(f"item {numero} não existe")
        if item.quando == ANTES:
            raise bloco.Recusa(f"item {numero} é de antes do merge; anote com harness.py aceitacao anotar na lane")
        if item.prova != MANUAL:
            raise bloco.Recusa(f"item {numero} tem prova automática; o lane fechar a confere")
    itens = []
    for item in tabela.itens:
        if item.quando == DEPOIS:
            if item.prova == MANUAL:
                item = dataclasses.replace(item, resultado=manuais.get(item.numero, SEM), data=hoje)
            else:
                item = _provado(item, perfil, numero_da_lane, hoje, pedidos.get(item.numero), variaveis)
            itens.append(item)
    linhas = [f"{item.numero} {item.prova}: {item.resultado}" for item in itens]
    final = _veredito(itens, [item.numero for item in itens if not _aprovado(item)])
    return Resultado((*linhas, final), tabela, final.startswith("ACEITACAO OK"))


def anotar(tabela: Tabela, numero: int, resultado: str, nota: str, hoje: str) -> Tabela:
    """A tabela com o item manual de antes do merge anotado: `<resultado>: <nota>`, com a nota numa linha, e a Data."""
    item = next((item for item in tabela.itens if item.numero == numero), None)
    if item is None:
        raise bloco.Recusa(f"item {numero} não existe")
    if item.prova != MANUAL:
        raise bloco.Recusa(f"item {numero} tem prova automática; rode harness.py aceitacao conferir")
    if item.quando == DEPOIS:
        raise bloco.Recusa(f"item {numero} é de depois do merge; anote no harness.py lane fechar --manual")
    nota = " ".join(nota.split())
    if not nota:
        raise bloco.Recusa("a nota não pode ficar vazia")
    anotado = dataclasses.replace(item, resultado=f"{resultado}: {nota}", data=hoje)
    return Tabela(tabela.id, tuple(anotado if outro.numero == numero else outro for outro in tabela.itens))


def commitar(raiz: Path, relativo: str, id_: str, executar=subprocess.run) -> bool:
    """O commit `chore(<ID>): aceitação` só com o arquivo, pelo `bloco.commitar`: sem mudança no arquivo, nada, e
    False; a falha volta o arquivo ao último commit e dá `Recusa("git commit falhou: <motivo>; <arquivo> voltou ao
    último commit")`, ou só a primeira parte sem a volta."""
    return bloco.commitar(raiz, [relativo], f"chore({id_}): aceitação", [relativo], executar)
