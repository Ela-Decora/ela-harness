"""Checagem determinística de um documento de planejamento contra o molde: o passo 4 do ciclo (spec 6.2).

Pastas, placeholders, partes variáveis dos títulos, IDs e adjetivos vagos vêm do perfil do projeto (spec 2a, §5.4), e
as regras do perfil (`[[campos]]`, `[[colunas]]` e `[[pendencia_na_linha]]`) acrescentam verificações aos documentos que casam com elas (spec 6a, §8).
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

import backlog
import comum
from campos import (
    _RE_CODIGO_EM_LINHA, _RE_COMENTARIO_HTML, _RE_ITEM_DE_LISTA, _RE_LINK, _RE_TITULO_DE_SECAO, CERCA, _fora_de_blocos,
    _linhas, _recuo, itens_do_campo, ler_links, linhas_fora_de_blocos, resolver_link, secoes,
)
from perfil import Fase, Perfil

AJUDA = """\
Confere cada documento contra o molde dele, em seis verificações e nas regras do perfil que casam com ele, e sai com 1
se alguma falha, menos `a-confirmar` e `aceite-renumerado`.

Sem argumento, confere os documentos em refino do STATUS.md, o `Pacote` ou o `Documento`; sem nenhum, sai com 1 e
`sem documento: passe o caminho ou abra um no STATUS.md`, e com o STATUS.md inválido, `STATUS.md inválido: <motivo>`.
O molde é o que o `harness.py molde` resolve, e os blocos de código cercados por três crases ficam de fora, no
documento e no molde. Uma linha por verificação, nesta ordem: `<nome>: OK`, ou `<nome>: FALHA: <n> ocorrências`,
com `, primeira em L<linha>` quando há linha; o `--verbose` põe o detalhe de cada ocorrência abaixo.
Com mais de um documento, a linha `== <documento>` abre o bloco de cada um, e a recusa de um não para os outros.

- `placeholders`: sobra no texto um padrão de `moldes.placeholders`. Detalhe: `L<linha>: <trecho>`.
- `titulos`: os títulos de nível 1 a 3 não seguem os do molde, na ordem, já com as trocas de `moldes.trocas_de_nome`;
  o título com uma parte de `moldes.partes_variaveis` aceita o texto no lugar dela e pode se repetir. Detalhe, só da
  primeira divergência: `L<linha>: esperado "<título>", achado "<título>"`, `sem par no documento: <título>` ou
  `L<linha>: título sem par no molde: "<título>"`.
- `ids`: um token com prefixo de `ids.prefixos` fora dos `ids.padroes`, um ID definido duas vezes ou um buraco na
  sequência de um prefixo; o buraco só conta fora dos prefixos de `ids.com_buracos`. O token dentro de código em linha (entre crases, com a abertura e o fechamento do mesmo
  tamanho) não conta como fora do padrão; o ID entre crases ainda conta como citado, em `ids-citados`. Define o ID
  quem o põe no começo de item de lista, de linha de tabela ou de título, ou logo depois da primeira palavra do
  título (`### <palavra> <ID>: ...`), com `**` opcional; o citado no meio do texto não conta. Detalhe:
  `<token> fora do padrão`, `<ID> duplicado`, `falta <ID>` ou `faltam <ID> a <ID>`.
- `ids-citados`: um ID citado sem definição no documento nem num artefato da tabela da fase dele ou de fase anterior;
  fora das pastas de fase, só as definições do próprio documento. Dois IDs do mesmo prefixo separados por ` a `
  formam uma faixa, que vale por cada ID dela; a invertida ou com prefixos diferentes é problema. Detalhe:
  `L<linha>: <ID> citado e não definido`, `L<linha>: faixa invertida: <ID> a <ID>`,
  `L<linha>: faixa com prefixos diferentes: <ID> a <ID>` ou `backlog ilegível: <motivo>`.
- `a-confirmar`: nunca falha; a linha é `a-confirmar: <n>`, a contagem das marcas `[A CONFIRMAR`. Detalhe:
  `L<linha> (<seção>)`.
- `adjetivos-vagos`: um termo de `texto.adjetivos_vagos`, como palavra inteira e sem distinção de maiúsculas; linha
  de citação (`>`) e trecho entre aspas não contam. Detalhe: `L<linha>: <termo>`.

As verificações das regras do perfil vêm depois das seis, cada uma só no documento que casa, pelos `documentos`, com
uma regra dela. Elas rodam também no `checar-aprovados` do `harness.py invariantes`, com o backlog da mesma versão.

- `campos`, das regras `[[campos]]`: em cada seção cujo título começa pelo `titulo` da regra, até o próximo título de
  nível igual ou acima, o campo é o primeiro item de lista que começa pelo rótulo em negrito, com os dois-pontos
  dentro ou fora do negrito. São itens dele o valor na mesma linha e cada item de lista mais recuado abaixo, numerado
  ou não, sem os comentários `<!-- -->`; a linha mais recuada sem marcador continua o item de cima, e a linha em
  branco não corta a lista. Com um campo só, a regra pode pedir de quantos a quantos itens, um ID dos prefixos de
  `cita` em cada item, o `formato` que cada item casa por inteiro e trechos `proibidos`, sem distinção de
  maiúsculas. Detalhe: `L<linha>: seção "<título>" sem o campo <campo>` (ausente ou só com o comentário),
  `L<linha>: <campo> com <k> itens; de <mínimo> a <máximo>` (com `1 item` no singular),
  `L<linha>: item de <campo> sem ID de <prefixos>`, `L<linha>: <campo> fora do formato: <item>` e
  `L<linha>: <campo> com "<proibido>"`. A mesma falha de duas regras sai uma vez.
- `colunas`, das regras `[[colunas]]`: em toda tabela com a `coluna` da regra no cabeçalho, cada linha tem a célula
  dela não vazia e, com `formato`, casando com ele por inteiro. A linha toda vazia fica com o `sobras-de-molde`, a
  célula que falta vale vazia, e a tabela sem a coluna fica de fora. Detalhe: `L<linha>: coluna <coluna> vazia` e
  `L<linha>: coluna <coluna> fora do formato: <célula>`.
- `pendencia-na-linha`, das regras `[[pendencia_na_linha]]`: toda linha fora dos blocos de código e das citações
  (`>`) que tem um dos `termos`, como palavra inteira e sem distinção de maiúsculas, cita uma pendência
  (`ids.prefixo_pendencia`) aberta no backlog; com várias, basta uma. O texto achado entra na mensagem. Detalhe:
  `L<linha>: "<termo>" sem pendência na linha`, `L<linha>: "<termo>" com <pendência>, que não está no backlog`,
  `L<linha>: "<termo>" com <pendência>, que não está aberta: <status>` e, sem linha, `backlog ilegível: <motivo>`,
  só quando alguma linha tem um termo. Fora das pastas de fase, o documento que casa com a regra também lê o
  backlog.

Todo documento de uma pasta de fase, com ou sem `[der]` no perfil, ganha o `links` depois das regras do perfil; na
fase do `[der]`, ele vem entre o `c4` e o `drawio`. O pre-commit não o roda.

- `links`: link relativo fora dos blocos de código e do código em linha, resolvido a partir da pasta do documento,
  sem a âncora `#...` e sem o `?...`, com os `%xx` decodificados; o que começa por `/` parte da raiz, e o que começa
  por `//` é externo. O destino pode vir entre `<...>` e ter um nível de parênteses, como `a(1).md`. A regra é a da
  exportação da passagem, com a caixa de cada parte como no disco: o link que sai da raiz ou não acha o arquivo não
  resolve; o que cai numa chave de `[caminhos]` (`rascunho`, `status`, `decisoes`, `backlog`, `estudos`, `atritos` e
  `leitor_frio`) ou na pasta `.claude`, ou dentro delas, é excluído da passagem; o que cai numa pasta é recusado.
  Detalhe, com o destino como está escrito, sem os `<>`: `L<linha>: link <destino> não resolve`,
  `L<linha>: link <destino> excluído da passagem (<chave>)`, com a chave ou `.claude`, e
  `L<linha>: link <destino> é uma pasta; linke um arquivo`.

Logo depois do `links`, nos mesmos documentos, vêm as verificações das citações; na fase do `[der]`, elas ficam
entre o `links` e o `drawio`. O pre-commit não as roda.

- `citacao-por-linha`: trecho `<caminho>.md:<n>` ou `<caminho>.md:<n>-<m>` fora dos blocos de código, dentro ou fora
  do código em linha, com o `<caminho>` feito de letras, algarismos, `.`, `_`, `-`, `*` e `/`. Fica de fora o
  `caminhos.decisoes`, ou a parte final dele depois de uma `/`: o arquivo só recebe acréscimos, e as linhas dele não
  andam. Detalhe: `L<linha>: <citação> cita por número de linha; cite o ID ou o título da seção`.
- `aceite-renumerado`, que nunca falha: para cada `<ID>.<n>` que outro documento `aprovado` das pastas de fase cita,
  sozinho ou numa faixa `<ID>.<n> a <ID>.<m>`, compara o item `<n>` da seção `### <palavra> <ID>: <nome>` com o do
  documento no HEAD; o item é a posição na primeira lista numerada da seção. Linha: `aceite-renumerado: OK` ou
  `aceite-renumerado: AVISO: <n> ocorrências, primeira em L<linha>`. Detalhe:
  `L<linha>: <ID>.<n>, citado em <documentos>, virou <ID>.<m> desde o HEAD` ou
  `L<linha>: <ID>.<n>, citado em <documentos>, mudou ou saiu desde o HEAD`. Sem o documento no HEAD, passa.

Com a seção `[der]` no perfil, os documentos da fase que contém o `[der].documento` ganham quatro verificações
extras, depois das seis e das regras do perfil; o pre-commit não as roda:

- `sobras-de-molde`, em todos: item de lista vazio, ou item que termina em `:` ou num rótulo em negrito e ficou
  igual ao do molde, sem o comentário e sem conteúdo mais recuado abaixo; linha de tabela com todas as células
  vazias; bloco de três crases do tipo `text` só com linhas em branco. Detalhe:
  `L<linha>: <sobra>; preencha ou apague`, com a sobra `item de lista vazio`, `linha de tabela vazia` ou
  `bloco text vazio`.
- `mermaid`, em todos: bloco de três crases do tipo `mermaid` cuja primeira linha útil, sem as em branco, os
  comentários `%%` e o frontmatter `---`, não começa por `flowchart`, `graph`, `sequenceDiagram`, `classDiagram`,
  `stateDiagram-v2`, `erDiagram`, `C4Context` ou `C4Container`; ou bloco vazio, só com essa linha, `title` e
  comentários, menos o do DER antes do primeiro `der gerar`; ou bloco sem a cerca que fecha, ou com o frontmatter
  `---` sem o segundo `---`, que tomam o lugar das outras conferências do bloco. Detalhe, na linha da cerca:
  `L<linha>: bloco mermaid de tipo <tipo>; use flowchart, graph, ...`, `L<linha>: bloco mermaid vazio`,
  `L<linha>: cerca sem fechamento; feche o bloco com três crases` ou
  `L<linha>: frontmatter --- sem fechamento; feche com outra linha ---`.
- `c4`, em todos, nos blocos `C4Context` e `C4Container`: `Container`, `ContainerDb` ou `ContainerQueue` sem
  tecnologia ou sem descrição; `Person`, `System`, `System_Ext`, `SystemDb` ou `SystemQueue` sem descrição; `Rel` ou
  `BiRel` sem rótulo; o bloco sem nenhum elemento; o bloco sem a lista `Legenda:` logo depois, com ao menos um item.
  O bloco sem a cerca que fecha fica de fora. Detalhe:
  `L<linha>: <Função>(<alias>) sem tecnologia`, o mesmo com `sem descrição`, `L<linha>: <Rel>(<a>, <b>) sem rótulo`,
  `L<linha>: bloco <tipo> sem nenhum elemento` e `L<linha>: bloco <tipo> sem a lista "Legenda:" logo depois`.
- `drawio`, em todos: cada `.drawio` da pasta do documento, sem as subpastas, com XML válido, as células `0` e `1`
  no arquivo, sem compressão, toda aresta com `source` e `target` que existem na página dela e todo vértice com
  rótulo; ao lado, o `.drawio.svg` exportado com a cópia do diagrama, igual ao `.drawio`, página por página, em
  células, estilos, rótulos, ligações e geometria. A página é a posição do `<diagram>` no arquivo, a partir de 1.
  Detalhe, sem linha: `<arquivo>: XML inválido (<motivo>)`, `<arquivo>: sem as células 0 e 1`,
  `<arquivo>: compressed="true"; grave sem compressão`, `<arquivo>: diagrama compactado; grave sem compressão` (sem
  o atributo), `<arquivo>: aresta <id> com source <x>, que não existe`,
  `<arquivo>: aresta <id> sem source; ligue as duas pontas a vértices` (os dois também com `target`),
  `<arquivo>: vértice <id> sem rótulo`, `<arquivo>.svg ausente; exporte em SVG com "Include a copy of my diagram"`,
  `<arquivo>.svg sem a cópia do diagrama; exporte com "Include a copy of my diagram"` e
  `<arquivo>.svg de outra versão do <arquivo> (<k> células diferem, primeira <id>); exporte de novo`. Com duas
  páginas ou mais, `<arquivo>` vira `<arquivo>, página <n>` nas arestas e nos vértices, e a última mensagem termina
  em `primeira <id> na página <n>); exporte de novo`.
- No próprio documento de `[der]`, as do DER (`harness.py der --help`): `der-formato`, os erros de formato,
  `L<linha>: <motivo>`; `der-rastreio`, as regras de rastreio contra o modelo conceitual e os documentos das
  entidades; `der-em-dia`, o que o `der conferir` acusa; `workbench`, o manifesto ausente, de outra versão do DDL
  ou com arquivo listado que não existe. Com o formato inválido, `der-rastreio` e `der-em-dia` falham com
  `formato do DER inválido; corrija o der-formato antes`.

Uma verificação que entrou numa versão do plugin depois da aprovação só avisa no documento `aprovado` na tabela de
artefatos: a linha é `<nome>: AVISO: <n> ocorrências, verificação da v<x>, posterior à aprovação`, sem sair com 1.
Vale quando nenhuma migração registrada no arquivo de decisões chegou à `v<x>`, ou quando a data da aprovação na
tabela é anterior à da migração que chegou. Fora disso, e em documento que não está `aprovado`, falha como as outras.
Nesta versão, nenhuma verificação entra nessa regra. O `checar-aprovados` do pre-commit a segue.

Recusas do documento, numa linha: `documento fora de <pasta>/: <documento>`, `documento não encontrado: <caminho>`,
`molde não encontrado: <caminho>` e as de arquivo fora de UTF-8 ou ilegível.
"""

AJUDA_MOLDE = """\
Imprime o caminho do molde de um documento, relativo à raiz, e sai com 0; o documento não precisa existir.

O molde fica na pasta de moldes (`moldes.pasta`). Vale o primeiro par de `moldes.mapa` cujo padrão casa com o caminho
do documento relativo à pasta do planejamento, com `*`, `?` e `[...]` dentro de um segmento; sem par, o mesmo caminho
relativo dentro da pasta de moldes. Os títulos de nível 1 a 3 do molde são o contrato que o `checar` confere, e os
padrões de `moldes.placeholders` não podem sobrar no documento. Recusas, com 1:
`documento fora de <pasta>/: <documento>`, fora da pasta do planejamento, e `molde não encontrado: <molde>`.
"""

PLACEHOLDERS = "placeholders"
TITULOS = "titulos"
IDS = "ids"
IDS_CITADOS = "ids-citados"
A_CONFIRMAR = "a-confirmar"
ADJETIVOS_VAGOS = "adjetivos-vagos"
CAMPOS = "campos"
COLUNAS = "colunas"
PENDENCIA_NA_LINHA = "pendencia-na-linha"
SOBRAS = "sobras-de-molde"
CITACAO_POR_LINHA = "citacao-por-linha"
ACEITE_RENUMERADO = "aceite-renumerado"

MARCADOR_A_CONFIRMAR = "[A CONFIRMAR"
SEM_TITULO = "sem título"

_RE_TITULO = re.compile(r"#{1,3} ")
_RE_CITACAO = re.compile(r'"[^"]*"|“[^”]*”')
_NUNCA = "(?!)"  # regex que não casa com nada, para lista vazia no perfil
_RE_FAIXA = re.compile(r"\s+a\s+")  # o texto entre dois IDs de uma faixa, como em "RF-CAD-01 a RF-CAD-03"


def _alternativas(padroes) -> str:
    padroes = list(padroes)
    return "|".join(padroes) if padroes else _NUNCA


@dataclass(frozen=True)
class _Padroes:
    """Regex das verificações, montadas a partir do perfil."""

    placeholder: re.Pattern
    id_definido: re.Pattern
    # Todo token que começa como ID; os que não casam com um ID nem com um prefixo de domínio estão fora do padrão.
    token_id: re.Pattern
    id_no_padrao: re.Pattern
    prefixo_de_dominio: re.Pattern
    adjetivo_vago: re.Pattern
    # Os prefixos de `ids.com_buracos`, em que a sequência não é conferida.
    com_buracos: tuple[str, ...] = ()


def _padroes(perfil: Perfil) -> _Padroes:
    ids = perfil.ids
    id_ = r"(?P<prefixo>" + _alternativas(ids.padroes) + r")-(?P<numero>[0-9]{2,})\b"
    dominios = [padrao for padrao in ids.padroes if padrao not in ids.prefixos]
    prefixos = "|".join(re.escape(prefixo) for prefixo in ids.prefixos)
    return _Padroes(
        placeholder=re.compile(_alternativas(perfil.moldes.placeholders)),
        # O marcador de lista, de tabela ou de título; depois dos `#`, uma palavra opcional antes do ID.
        id_definido=re.compile(r"\s*(?:(?:[-*+|]|[0-9]+\.)\s+|#{1,6}\s+(?:\w+\s+)?)?(?:\*\*)?" + id_),
        token_id=re.compile(r"\b(?:" + prefixos + r")-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*"),
        id_no_padrao=re.compile(r"(?:" + _alternativas(ids.padroes) + r")-(?!0+$)[0-9]{2,}"),
        prefixo_de_dominio=re.compile(r"(?:" + _alternativas(dominios) + r")"),
        adjetivo_vago=re.compile(r"\b(" + _alternativas(perfil.texto.adjetivos_vagos) + r")\b", re.IGNORECASE),
        com_buracos=ids.com_buracos,
    )


@dataclass
class Resultado:
    """Uma verificação: `ok` é falso se há problema; `ocorrencias` conta problemas (ou marcas, em a-confirmar)."""

    nome: str
    ok: bool
    ocorrencias: int
    primeira_linha: int | None
    detalhes: list[str]
    aviso: str = ""


class EntradaInvalida(Exception):
    """O documento ou o molde não serve: ausente, fora de planejamento/ ou ilegível. `mensagem` diz o motivo."""

    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


def de_ocorrencias(nome: str, ocorrencias: list[tuple[int, str]]) -> Resultado:
    """Resultado de uma verificação que falha se houver ocorrência; cada detalhe é `L<linha>: <texto>`."""
    return Resultado(
        nome,
        not ocorrencias,
        len(ocorrencias),
        ocorrencias[0][0] if ocorrencias else None,
        [f"L{numero}: {texto}" for numero, texto in ocorrencias],
    )


def _placeholders(uteis: list[tuple[int, str]], padroes: _Padroes) -> Resultado:
    achados = [(numero, achado.group(0)) for numero, linha in uteis for achado in padroes.placeholder.finditer(linha)]
    return de_ocorrencias(PLACEHOLDERS, achados)


def _adjetivos_vagos(uteis: list[tuple[int, str]], padroes: _Padroes) -> Resultado:
    """Adjetivos vagos fora de citação: linhas que começam com `>` e trechos entre aspas não contam."""
    achados = []
    for numero, linha in uteis:
        if linha.lstrip().startswith(">"):
            continue
        sem_citacoes = _RE_CITACAO.sub(" ", linha)
        achados += [(numero, achado.group(0)) for achado in padroes.adjetivo_vago.finditer(sem_citacoes)]
    return de_ocorrencias(ADJETIVOS_VAGOS, achados)


def _a_confirmar(uteis: list[tuple[int, str]]) -> Resultado:
    """Conta as marcas `[A CONFIRMAR`, uma por ocorrência. Nunca falha: é só informação."""
    titulo = SEM_TITULO
    detalhes = []
    primeira_linha = None
    for numero, linha in uteis:
        if _RE_TITULO.match(linha):
            titulo = linha.lstrip("#").strip()
        for _ in range(linha.count(MARCADOR_A_CONFIRMAR)):
            detalhes.append(f"L{numero} ({titulo})")
            if primeira_linha is None:
                primeira_linha = numero
    return Resultado(A_CONFIRMAR, True, len(detalhes), primeira_linha, detalhes)


def _formatar_id(prefixo: str, numero: int) -> str:
    return f"{prefixo}-{numero:02d}"


def _ids(uteis: list[tuple[int, str]], padroes: _Padroes) -> Resultado:
    """IDs fora do padrão em todo o texto, e duplicata e buraco nos IDs das linhas de definição, por prefixo.

    Fora do padrão: token com um dos prefixos do perfil que não é ID (um dos padrões, `-` e número de 01 em
    diante) nem prefixo de domínio (padrão que não é só o prefixo, como `RF-CAD`); os placeholders do molde
    ficam com a verificação `placeholders`, e o token dentro de código em linha não conta. Uma linha de
    definição começa com o ID, depois de `- `, `* `, `+ `, `| `, `1. `, `#` a `######` ou `**` opcionais, ou
    traz o ID logo depois da primeira palavra do título (`### <palavra> <ID>: ...`). ID
    só citado no meio do texto não entra na conferência de duplicata e buraco. O buraco não é conferido no
    prefixo casado que está em `ids.com_buracos` ou começa por um deles e `-`. Os problemas saem na ordem da
    linha em que cada um é apontado.
    """
    problemas: list[tuple[int, str]] = []
    definicoes: dict[str, dict[int, list[int]]] = {}
    for numero_da_linha, linha in uteis:
        sem_codigo = _RE_CODIGO_EM_LINHA.sub(lambda trecho: " " * len(trecho.group(0)), linha)
        for token in padroes.token_id.findall(sem_codigo):
            if not (
                padroes.id_no_padrao.fullmatch(token)
                or padroes.prefixo_de_dominio.fullmatch(token)
                or padroes.placeholder.search(token)
            ):
                problemas.append((numero_da_linha, f"{token} fora do padrão"))
        achado = padroes.id_definido.match(linha)
        if achado:
            linhas_do_id = definicoes.setdefault(achado.group("prefixo"), {}).setdefault(int(achado.group("numero")), [])
            linhas_do_id.append(numero_da_linha)

    for prefixo, linhas_por_numero in definicoes.items():
        for numero, linhas_do_id in linhas_por_numero.items():
            if len(linhas_do_id) > 1:
                problemas.append((linhas_do_id[1], f"{_formatar_id(prefixo, numero)} duplicado"))
        if any(prefixo == livre or prefixo.startswith(livre + "-") for livre in padroes.com_buracos):
            continue
        anterior = 0
        for numero in sorted(linhas_por_numero):
            primeiro_faltante, ultimo_faltante = anterior + 1, numero - 1
            if primeiro_faltante <= ultimo_faltante:
                inicio = _formatar_id(prefixo, primeiro_faltante)
                if primeiro_faltante == ultimo_faltante:
                    mensagem = f"falta {inicio}"
                else:
                    mensagem = f"faltam {inicio} a {_formatar_id(prefixo, ultimo_faltante)}"
                acima = [min(linhas) for n, linhas in linhas_por_numero.items() if n > ultimo_faltante]
                problemas.append((min(acima), mensagem))
            anterior = numero

    problemas.sort(key=lambda problema: problema[0])
    return Resultado(
        IDS, not problemas, len(problemas), problemas[0][0] if problemas else None, [m for _, m in problemas]
    )


def _com_trocas(titulo: str, perfil: Perfil) -> str:
    """O título do molde com as trocas de nome do perfil, como o documento deve tê-lo."""
    for antigo, novo in perfil.moldes.trocas_de_nome.items():
        titulo = titulo.replace(antigo, novo)
    return titulo


def _padrao_do_titulo(titulo: str, perfil: Perfil) -> tuple[re.Pattern, bool]:
    """Padrão do título do molde e se ele é repetível.

    Primeiro valem as trocas de nome do perfil. Depois, cada parte variável do perfil (por exemplo, um comentário
    `<!-- ... -->` que vira `.+`) dá lugar à regex que o documento pode ter ali; o resto é literal. Só o título
    que tem parte variável é repetível.
    """
    titulo = _com_trocas(titulo, perfil)
    variaveis = list(perfil.moldes.partes_variaveis.items())
    if not variaveis:
        return re.compile(re.escape(titulo)), False
    procura = re.compile("|".join(f"(?P<v{indice}>{chave})" for indice, (chave, _) in enumerate(variaveis)))
    padrao, inicio, repetivel = "", 0, False
    for achado in procura.finditer(titulo):
        indice = next(i for i in range(len(variaveis)) if achado.group(f"v{i}") is not None)
        padrao += re.escape(titulo[inicio:achado.start()]) + variaveis[indice][1]
        inicio, repetivel = achado.end(), True
    return re.compile(padrao + re.escape(titulo[inicio:])), repetivel


def _titulos_de(uteis: list[tuple[int, str]]) -> list[tuple[int, str]]:
    return [(numero, linha.rstrip()) for numero, linha in uteis if _RE_TITULO.match(linha)]


def _titulos(
    uteis: list[tuple[int, str]], uteis_do_molde: list[tuple[int, str]], total_de_linhas: int, perfil: Perfil
) -> Resultado:
    """Compara os títulos de nível 1 a 3 do documento com os do molde, em ordem.

    O título repetível do molde casa um ou mais títulos seguidos do documento; o literal casa exatamente um. A
    primeira divergência é a falha, e ela conta como uma ocorrência só.
    """
    doc = _titulos_de(uteis)
    posicao = 0
    for _, titulo_do_molde in _titulos_de(uteis_do_molde):
        padrao, repetivel = _padrao_do_titulo(titulo_do_molde, perfil)
        if posicao >= len(doc):
            detalhe = f"sem par no documento: {_com_trocas(titulo_do_molde, perfil)}"
            return Resultado(TITULOS, False, 1, max(total_de_linhas, 1), [detalhe])
        numero, titulo = doc[posicao]
        if not padrao.fullmatch(titulo):
            return Resultado(
                TITULOS, False, 1, numero,
                [f'L{numero}: esperado "{_com_trocas(titulo_do_molde, perfil)}", achado "{titulo}"'],
            )
        posicao += 1
        while repetivel and posicao < len(doc) and padrao.fullmatch(doc[posicao][1]):
            posicao += 1
    if posicao < len(doc):
        numero, titulo = doc[posicao]
        return Resultado(TITULOS, False, 1, numero, [f'L{numero}: título sem par no molde: "{titulo}"'])
    return Resultado(TITULOS, True, 0, None, [])


def ids_citados(texto: str, perfil: Perfil) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """(linha, ID) de cada ID citado fora dos blocos de código, e (linha, problema) de cada faixa que não vale.

    O número sai normalizado (`RF-CAD-001` vira `RF-CAD-01`). Dois IDs separados só por " a " formam uma faixa, que
    vale por cada ID dela; faixa invertida ou com prefixos diferentes é problema. Placeholder do molde não conta.
    """
    padroes = _padroes(perfil)
    citados: list[tuple[int, str]] = []
    faixas: list[tuple[int, str]] = []
    for numero_da_linha, linha in _fora_de_blocos(_linhas(texto)):
        anterior = None  # (fim do token, prefixo, número) do último ID válido da linha
        for achado in padroes.token_id.finditer(linha):
            token = achado.group(0)
            if not padroes.id_no_padrao.fullmatch(token) or padroes.placeholder.search(token):
                anterior = None
                continue
            prefixo, digitos = token.rsplit("-", 1)
            numero = int(digitos)
            if anterior is not None and _RE_FAIXA.fullmatch(linha[anterior[0]:achado.start()]):
                inicio, fim = _formatar_id(anterior[1], anterior[2]), _formatar_id(prefixo, numero)
                if prefixo != anterior[1]:
                    faixas.append((numero_da_linha, f"faixa com prefixos diferentes: {inicio} a {fim}"))
                elif numero < anterior[2]:
                    faixas.append((numero_da_linha, f"faixa invertida: {inicio} a {fim}"))
                else:
                    citados += [(numero_da_linha, _formatar_id(prefixo, n)) for n in range(anterior[2] + 1, numero)]
            citados.append((numero_da_linha, _formatar_id(prefixo, numero)))
            anterior = (achado.end(), prefixo, numero)
    return citados, faixas


def _ids_citados(texto: str, perfil: Perfil, definidos_fora: frozenset[str], erro_fora: str | None) -> Resultado:
    """ID citado e não definido no próprio texto nem em `definidos_fora`, e faixa que não vale.

    Com `erro_fora` (o backlog não pôde ser lido), falha com uma ocorrência só, sem linha.
    """
    if erro_fora is not None:
        return Resultado(IDS_CITADOS, False, 1, None, [f"backlog ilegível: {erro_fora}"])
    definidos = {id_ for _, id_ in ids_definidos(texto, perfil)} | definidos_fora
    citados, faixas = ids_citados(texto, perfil)
    problemas = [(linha, f"{id_} citado e não definido") for linha, id_ in citados if id_ not in definidos]
    problemas += faixas
    return de_ocorrencias(IDS_CITADOS, problemas)


def checar_textos(
    texto_documento: str,
    texto_molde: str,
    perfil: Perfil,
    definidos_fora: frozenset[str] = frozenset(),
    erro_fora: str | None = None,
) -> list[Resultado]:
    """As seis verificações, na ordem fixa: placeholders, titulos, ids, ids-citados, a-confirmar e adjetivos-vagos.

    `definidos_fora` são os IDs definidos em outros documentos que o texto pode citar; `erro_fora`, o motivo por que
    eles não puderam ser lidos.
    """
    padroes = _padroes(perfil)
    linhas = _linhas(texto_documento)
    uteis = _fora_de_blocos(linhas)
    uteis_do_molde = _fora_de_blocos(_linhas(texto_molde))
    return [
        _placeholders(uteis, padroes),
        _titulos(uteis, uteis_do_molde, len(linhas), perfil),
        _ids(uteis, padroes),
        _ids_citados(texto_documento, perfil, definidos_fora, erro_fora),
        _a_confirmar(uteis),
        _adjetivos_vagos(uteis, padroes),
    ]


def checar_documento(documento: Path, molde: Path, perfil: Perfil) -> list[Resultado]:
    """Lê os dois arquivos em UTF-8 e confere o documento contra o molde. Erro de leitura sobe como veio."""
    return checar_textos(comum.ler_texto(documento), comum.ler_texto(molde), perfil)


def ids_definidos(texto: str, perfil: Perfil) -> list[tuple[int, str]]:
    """(linha, ID) de cada ID definido no texto, fora dos blocos de código, com o número em pelo menos dois algarismos.

    Definido no sentido da verificação `ids`: o ID no começo de item de lista, linha de tabela ou título, ou logo
    depois da primeira palavra do título (`### <palavra> <ID>: ...`).
    """
    padroes = _padroes(perfil)
    definidos = []
    for numero_da_linha, linha in _fora_de_blocos(_linhas(texto)):
        achado = padroes.id_definido.match(linha)
        if achado:
            definidos.append((numero_da_linha, _formatar_id(achado.group("prefixo"), int(achado.group("numero")))))
    return definidos


def ids_definidos_nas_fases(
    raiz: Path, texto_backlog: str, perfil: Perfil, fases: tuple[Fase, ...]
) -> dict[str, tuple[str, int]]:
    """ID para (caminho relativo à raiz, linha) da primeira definição nos artefatos da tabela dentro das pastas de
    `fases`, na ordem da tabela. Artefato ilegível fica de fora."""
    pasta = perfil.caminhos.planejamento.rstrip("/")
    artefatos = sorted(
        (linha, caminho)
        for fase in fases
        for linha, caminho, _ in backlog.artefatos_da_pasta(texto_backlog, f"{pasta}/{fase.id}")
    )
    definidos: dict[str, tuple[str, int]] = {}
    for _, caminho in artefatos:
        try:
            texto = comum.ler_texto(raiz / caminho)
        except (OSError, UnicodeDecodeError):
            continue
        for linha, id_ in ids_definidos(texto, perfil):
            definidos.setdefault(id_, (caminho, linha))
    return definidos


def _passa_no_quando(texto: str, linha: int, quando: dict[str, str]) -> bool:
    """Se a definição da `linha` está num título cuja seção tem o campo `quando["campo"]` com um item que casa por
    inteiro com `quando["formato"]`."""
    titulo = _RE_TITULO_DE_SECAO.match(_linhas(texto)[linha - 1])
    if titulo is None:
        return False
    secao = next((linhas for numero, _, linhas in secoes(texto, titulo.group(1) + " ") if numero == linha), None)
    campo = itens_do_campo(secao, quando["campo"]) if secao is not None else None
    return campo is not None and any(re.fullmatch(quando["formato"], item) for _, item in campo[1])


def ids_a_cobrir(
    raiz: Path,
    texto_backlog: str,
    perfil: Perfil,
    fase: Fase,
    prefixos: tuple[str, ...],
    definidos_em: tuple[str, ...] = (),
    quando: dict[str, str] | None = None,
) -> dict[str, tuple[str, int]]:
    """Cada ID dos `prefixos` que um item `ids-cobertos` cobra, com a primeira definição, (caminho relativo à raiz,
    linha).

    Sem `definidos_em`, os IDs vêm dos artefatos da tabela nas fases antes de `fase`; com ele, dos artefatos da tabela
    de todas as fases, de qualquer status, cujo caminho relativo à pasta do planejamento casa com um dos padrões. Na
    ordem da tabela, vale a primeira definição; com `quando`, a primeira num título cuja seção tem o campo com um item
    que casa por inteiro com o formato. Artefato ilegível fica de fora.
    """
    pasta = perfil.caminhos.planejamento.rstrip("/")
    if definidos_em:
        artefatos = [
            caminho
            for _, caminho, _ in backlog.artefatos_da_pasta(texto_backlog, pasta)
            if any(comum.casa_padrao(padrao, caminho[len(pasta) + 1:]) for padrao in definidos_em)
        ]
    else:
        anteriores = perfil.fases[: perfil.fases.index(fase)]
        artefatos = [
            caminho
            for _, caminho in sorted(
                (linha, caminho)
                for anterior in anteriores
                for linha, caminho, _ in backlog.artefatos_da_pasta(texto_backlog, f"{pasta}/{anterior.id}")
            )
        ]
    a_cobrir: dict[str, tuple[str, int]] = {}
    for caminho in artefatos:
        try:
            texto = comum.ler_texto(raiz / caminho)
        except (OSError, UnicodeDecodeError):
            continue
        for linha, id_ in ids_definidos(texto, perfil):
            if id_ in a_cobrir or not any(id_.startswith(prefixo + "-") for prefixo in prefixos):
                continue
            if quando is None or _passa_no_quando(texto, linha, quando):
                a_cobrir[id_] = (caminho, linha)
    return a_cobrir


_RE_SEPARADOR = re.compile(r"\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?")


def tabelas(linhas: list[tuple[int, str]]) -> list[tuple[int, list[str], list[tuple[int, list[str]]]]]:
    """(linha do cabeçalho, células do cabeçalho, [(linha, células)]) de cada tabela das linhas dadas.

    Tabela: uma linha que começa por `|`, seguida de uma separadora (`|---|---|`) e das linhas seguidas que também
    começam por `|`.
    """
    achadas = []
    posicao = 0
    while posicao + 1 < len(linhas):
        numero, cabecalho = linhas[posicao]
        separadora = linhas[posicao + 1][1].strip()
        if not (cabecalho.strip().startswith("|") and separadora.startswith("|") and _RE_SEPARADOR.fullmatch(separadora)):
            posicao += 1
            continue
        corpo = []
        posicao += 2
        while posicao < len(linhas) and linhas[posicao][1].strip().startswith("|"):
            corpo.append((linhas[posicao][0], backlog.celulas(linhas[posicao][1])))
            posicao += 1
        achadas.append((numero, backlog.celulas(cabecalho), corpo))
    return achadas


def destinos_de_links(texto: str, caminho: str) -> set[str]:
    """Destino de cada link de `ler_links`, resolvido por `resolver_link` a partir da pasta de `caminho`; o vazio,
    o externo e o que sai da raiz ficam de fora."""
    destinos = set()
    for _, destino in ler_links(texto):
        resolvido = resolver_link(destino, caminho)
        if resolvido is not None and resolvido != ".." and not resolvido.startswith("../"):
            destinos.add(resolvido)
    return destinos


# A pasta do harness não entra na passagem, mesmo por link (decisão 5 do plano do PR 1 da 6b).
PASTA_DO_HARNESS = ".claude"
# Chaves de `[caminhos]` que não entram na passagem: o link para elas, ou para dentro delas, é recusado.
EXCLUIDOS = ("rascunho", "status", "decisoes", "backlog", "estudos", "atritos", "leitor_frio")
LINK_FORA = "fora do repositório"
LINK_PASTA = "pasta"
LINK_AUSENTE = "ausente"


def _dentro_ou_igual(caminho: str, pasta: str) -> bool:
    return caminho == pasta or caminho.startswith(pasta + "/")


def excluido_da_passagem(destino: str, perfil: Perfil) -> str | None:
    """A chave de `[caminhos]`, ou a pasta do harness, igual ao destino ou acima dele; None se ele não é excluído."""
    for chave in EXCLUIDOS:
        valor = getattr(perfil.caminhos, chave)
        if valor and _dentro_ou_igual(destino, valor):
            return chave
    return PASTA_DO_HARNESS if _dentro_ou_igual(destino, PASTA_DO_HARNESS) else None


def recusa_do_link(destino: str, perfil: Perfil, arquivo: Callable[[str], bool], pasta: Callable[[str], bool]) -> str:
    """O motivo da recusa do link já resolvido (`resolver_link`), relativo à raiz, nesta ordem: `fora do repositório`;
    `excluído da passagem (<chave>)`; `pasta`; `ausente`. Vazio quando `arquivo(destino)`. Quem chama diz o que é
    arquivo e o que é pasta: o commit na exportação, o disco com a caixa exata no `checar`."""
    if destino == ".." or destino.startswith("../"):
        return LINK_FORA
    excluido = excluido_da_passagem(destino, perfil)
    if excluido is not None:
        return f"excluído da passagem ({excluido})"
    if arquivo(destino):
        return ""
    return LINK_PASTA if pasta(destino) else LINK_AUSENTE


def blocos_de_codigo(texto: str) -> list[tuple[int, list[tuple[int, str]]]]:
    """(linha da cerca de abertura, [(linha, texto)] do conteúdo) de cada bloco cercado por três crases.

    Cerca que não fecha vai até o fim do arquivo, como em `_fora_de_blocos`.
    """
    blocos: list[tuple[int, list[tuple[int, str]]]] = []
    atual: list[tuple[int, str]] | None = None
    for numero, linha in enumerate(_linhas(texto), start=1):
        if linha.lstrip().startswith(CERCA):
            if atual is None:
                atual = []
                blocos.append((numero, atual))
            else:
                atual = None
        elif atual is not None:
            atual.append((numero, linha))
    return blocos


def contar_a_confirmar(texto: str) -> int:
    """Quantas marcas `[A CONFIRMAR` o texto tem fora dos blocos de código, como na verificação `a-confirmar`."""
    return _a_confirmar(_fora_de_blocos(_linhas(texto))).ocorrencias


def mostrar(raiz: Path, caminho: Path) -> str:
    """Caminho relativo à raiz, quando está sob ela; senão, como foi dado."""
    try:
        return caminho.resolve().relative_to(raiz.resolve()).as_posix()
    except ValueError:
        return str(caminho)


def resolver_molde(raiz: Path, documento: Path, perfil: Perfil) -> Path:
    """Molde do documento, dentro da pasta de moldes do perfil.

    Vence o primeiro par do mapa do perfil cujo padrão casa com o caminho do documento relativo à pasta do
    planejamento; sem par, vale o mesmo caminho relativo. O documento é relativo à raiz ou absoluto. Fora da pasta
    do planejamento levanta EntradaInvalida. Não confere se o molde existe.
    """
    pasta = perfil.caminhos.planejamento.rstrip("/")
    absoluto = raiz / documento
    try:
        relativo = absoluto.resolve().relative_to((raiz / pasta).resolve())
    except ValueError:
        raise EntradaInvalida(f"documento fora de {pasta}/: {mostrar(raiz, absoluto)}") from None
    relativo_posix = relativo.as_posix()
    molde = next(
        (molde for padrao, molde in perfil.moldes.mapa if comum.casa_padrao(padrao, relativo_posix)), relativo_posix
    )
    return raiz / perfil.moldes.pasta / molde


def _ler(raiz: Path, caminho: Path, rotulo: str) -> str:
    """Texto do arquivo. Ausente, fora de UTF-8 ou com erro do sistema vira EntradaInvalida, com `rotulo` no motivo."""
    try:
        return comum.ler_texto(caminho)
    except FileNotFoundError:
        raise EntradaInvalida(f"{rotulo} não encontrado: {mostrar(raiz, caminho)}") from None
    except UnicodeDecodeError:
        raise EntradaInvalida(f"{rotulo} não está em UTF-8: {mostrar(raiz, caminho)}") from None
    except OSError as erro:
        motivo = erro.strerror or type(erro).__name__
        raise EntradaInvalida(f"{rotulo} ilegível: {mostrar(raiz, caminho)} ({motivo})") from None


# O nome da verificação nova e a versão do plugin em que ela entrou. Nesta versão, nenhuma entra; as de antes ficam
# fora e falham como sempre.
DESDE: dict[str, str] = {}


def rebaixar_desde(resultados: list[Resultado], status: str | None, data: str | None,
                   migracoes: list) -> list[Resultado]:
    """Os resultados com a falha das verificações do `DESDE` rebaixada a aviso, no documento `aprovado`.

    Só o resultado que falha, cujo nome está no `DESDE`, e só com `status` que começa por `aprovado`, como no
    `migrar` e nas citações. A migração que chegou à versão
    `x` do `DESDE` é a primeira, na ordem de `migracoes`, cujo `para` é `x` ou mais novo. Sem ela, rebaixa; com ela,
    só se a `data` da aprovação é anterior à da migração. O rebaixado fica `ok`, com `aviso` na versão do `DESDE`.
    """
    import migrar  # dentro da função: o `migrar` importa o `citacoes`, que importa o `checar`

    if not (status or "").startswith("aprovado"):
        return resultados
    rebaixados = []
    for resultado in resultados:
        desde = DESDE.get(resultado.nome)
        if resultado.ok or desde is None:
            rebaixados.append(resultado)
            continue
        chegou = next((m for m in migracoes
                       if migrar.numero_da_versao(m.para) >= migrar.numero_da_versao(desde)), None)
        if chegou is None or (data or "") < chegou.data:
            resultado = replace(resultado, ok=True, aviso=desde)
        rebaixados.append(resultado)
    return rebaixados


def rebaixar_do_documento(resultados: list[Resultado], relativo: str, texto_backlog: str | None, perfil: Perfil,
                          ler_decisoes: Callable[[], str | None]) -> list[Resultado]:
    """O `rebaixar_desde` de um documento da tabela de artefatos de `texto_backlog`: o status e a data vêm da linha
    dele, e as migrações, de `ler_decisoes()`, que só roda se o `DESDE` cobre algum resultado que falha. Texto de
    decisões ilegível ou ausente (`None`) vale como sem migração."""
    if texto_backlog is None or not any(not r.ok and r.nome in DESDE for r in resultados):
        return resultados
    pasta = perfil.caminhos.planejamento
    status = next((s for _, caminho, s in backlog.artefatos_da_pasta(texto_backlog, pasta) if caminho == relativo), None)
    data = backlog.datas_da_pasta(texto_backlog, pasta).get(relativo)
    import migrar

    texto = ler_decisoes()
    return rebaixar_desde(resultados, status, data, [] if texto is None else migrar.migracoes(texto))


def checar_arquivo(raiz: Path, documento: Path, perfil: Perfil, executar=subprocess.run) -> list[Resultado]:
    """O que o subcomando `checar` faz: acha o molde do documento, lê os dois e confere.

    O documento é relativo à raiz do projeto (não ao diretório corrente) ou absoluto. Entrada que não serve
    levanta EntradaInvalida. Documento numa pasta de fase pode citar os IDs definidos nos artefatos da tabela do
    backlog da fase dele e das anteriores; fora das pastas de fase, só os dele mesmo. O backlog é lido para o
    documento numa pasta de fase e para o que casa com uma regra `[[pendencia_na_linha]]`.
    """
    molde = resolver_molde(raiz, documento, perfil)
    texto_documento = _ler(raiz, raiz / documento, "documento")
    texto_molde = _ler(raiz, molde, "molde")
    relativo = mostrar(raiz, raiz / documento)
    texto_backlog = None
    erro_backlog = None
    le_o_backlog = perfil.fase_do_documento(relativo) is not None
    if le_o_backlog or _regras_que_casam(perfil.pendencia_na_linha, relativo, perfil):
        try:
            texto_backlog = backlog.ler(raiz / perfil.caminhos.backlog)
        except backlog.BacklogIlegivel as erro:
            erro_backlog = erro.mensagem
    resultados = checar_versao(raiz, relativo, texto_documento, texto_molde, texto_backlog, perfil, erro_backlog)
    resultados += _da_camada(raiz, relativo, texto_documento, texto_molde, texto_backlog, perfil, executar)

    def decisoes() -> str | None:
        try:
            return comum.ler_texto(raiz / perfil.caminhos.decisoes)
        except (OSError, UnicodeDecodeError):
            return None

    return rebaixar_do_documento(resultados, relativo, texto_backlog, perfil, decisoes)


_RE_ITEM_VAZIO = re.compile(r"\s*(?:[-*+]|\d+[.)])\s*")
_RE_ROTULO = re.compile(r"(\s*)(?:[-*+]|\d+[.)])\s+(?:.*:|.*\*\*[^*]*:\*\*)")


def _sem_comentario(linha: str) -> str:
    return _RE_COMENTARIO_HTML.sub("", linha).rstrip()


def _rotulos_do_molde(molde: str) -> set[str]:
    """Os itens do molde que terminam em `:` ou num rótulo em negrito, sem o comentário e sem o recuo."""
    limpas = (_sem_comentario(linha) for _, linha in _fora_de_blocos(_linhas(molde)))
    return {limpa.strip() for limpa in limpas if _RE_ROTULO.fullmatch(limpa)}


def _conteudo_abaixo(linhas: list[str], numero: int, recuo: int) -> bool:
    """Se a próxima linha não vazia depois da linha `numero` (a partir de 1), cerca incluída, tem recuo maior."""
    seguinte = next((linha for linha in linhas[numero:] if linha.strip()), None)
    return seguinte is not None and len(seguinte) - len(seguinte.lstrip()) > recuo


def sobras_de_molde(texto: str, molde: str) -> Resultado:
    """Sobras de molde que não são placeholder (spec 5a, §20, item 10).

    Fora dos blocos de código: o item de lista sem texto; o item que termina em `:` ou num rótulo em negrito, igual a
    um item do molde sem o comentário, sem conteúdo mais recuado abaixo; a linha do corpo de uma tabela com todas as
    células vazias. Dentro: o bloco ```text só com linhas em branco.
    """
    linhas = _linhas(texto)
    uteis = _fora_de_blocos(linhas)
    rotulos = _rotulos_do_molde(molde)
    ocorrencias: list[tuple[int, str]] = []
    for numero, linha in uteis:
        if _RE_ITEM_VAZIO.fullmatch(linha):
            ocorrencias.append((numero, "item de lista vazio"))
            continue
        limpa = _sem_comentario(linha)
        achado = _RE_ROTULO.fullmatch(limpa)
        if achado and limpa.strip() in rotulos and not _conteudo_abaixo(linhas, numero, len(achado.group(1))):
            ocorrencias.append((numero, "item de lista vazio"))
    for _, _, corpo in tabelas(uteis):
        ocorrencias += [(numero, "linha de tabela vazia") for numero, celulas in corpo if not any(celulas)]
    for cerca, conteudo in blocos_de_codigo(texto):
        if linhas[cerca - 1].strip() == CERCA + "text" and not any(linha.strip() for _, linha in conteudo):
            ocorrencias.append((cerca, "bloco text vazio"))
    return de_ocorrencias(SOBRAS, [(numero, f"{sobra}; preencha ou apague") for numero, sobra in sorted(ocorrencias)])


def _da_camada(raiz: Path, relativo: str, texto: str, molde: str, texto_backlog: str | None, perfil: Perfil,
               executar) -> list[Resultado]:
    """As verificações depois das regras do perfil. Fora das pastas das fases, nenhuma. Na fase que contém o documento
    de `[der]`: `sobras-de-molde`, `mermaid`, `c4`, `links`, as das citações e `drawio` em todo documento dela e, no
    próprio documento de `[der]`, as do DER. Nas outras fases, ou sem `[der]`, só o `links` e as das citações."""
    fase_do_documento = perfil.fase_do_documento(relativo)
    if fase_do_documento is None:
        return []
    import der  # o der e o diagramas importam o checar
    import citacoes
    import diagramas

    documento_do_der = der.documento_do_perfil(perfil) if perfil.der is not None else None
    if documento_do_der is None or perfil.fase_do_documento(documento_do_der) != fase_do_documento:
        return [de_ocorrencias("links", diagramas.conferir_links(raiz, relativo, texto, perfil)),
                *citacoes.verificacoes(raiz, relativo, texto, texto_backlog, perfil, executar)]
    resultados = [sobras_de_molde(texto, molde), *diagramas.verificacoes(raiz, perfil, relativo, texto)]
    # as da citação entram logo depois do `links`, antes do `drawio`
    posicao = next(i for i, resultado in enumerate(resultados) if resultado.nome == "links") + 1
    resultados[posicao:posicao] = citacoes.verificacoes(raiz, relativo, texto, texto_backlog, perfil, executar)
    if relativo == documento_do_der:
        resultados += der.verificacoes(raiz, perfil, relativo, texto)
    return resultados


def _regras_que_casam(regras: tuple, relativo: str, perfil: Perfil) -> list:
    """As regras com um padrão de `documentos` que casa com o caminho do documento relativo à pasta do planejamento;
    o `relativo` é relativo à raiz, e fora da pasta do planejamento nenhuma casa."""
    prefixo = perfil.caminhos.planejamento.rstrip("/") + "/"
    if not relativo.startswith(prefixo):
        return []
    dentro = relativo[len(prefixo):]
    return [regra for regra in regras if any(comum.casa_padrao(padrao, dentro) for padrao in regra.documentos)]


def _cita(texto: str, prefixos: tuple[str, ...], perfil: Perfil) -> bool:
    """Se o texto cita um ID de um dos prefixos: os de `ids.prefixos` pelo `ids_citados`, com as faixas, e o da
    pendência pelo número de dois algarismos ou mais."""
    citados = [id_ for _, id_ in ids_citados(texto, perfil)[0]]
    for prefixo in prefixos:
        if prefixo == perfil.ids.prefixo_pendencia:
            if re.search(r"\b" + re.escape(prefixo) + r"-[0-9]{2,}\b", texto):
                return True
        elif any(id_.startswith(prefixo + "-") for id_ in citados):
            return True
    return False


def _campos(texto: str, regras: list, perfil: Perfil) -> Resultado:
    """Os campos de cada seção que uma regra `[[campos]]` do documento pede; a mesma falha de duas regras sai uma vez,
    na ordem da linha e, na mesma linha, do texto."""
    ocorrencias: list[tuple[int, str]] = []
    for regra in regras:
        for linha_do_titulo, titulo, linhas in secoes(texto, regra.titulo):
            for rotulo in regra.campos:
                campo = itens_do_campo(linhas, rotulo)
                if campo is None or not campo[1]:
                    linha = linha_do_titulo if campo is None else campo[0]
                    ocorrencias.append((linha, f'seção "{titulo}" sem o campo {rotulo}'))
                    continue
                linha_do_rotulo, itens = campo
                if regra.itens is not None and not regra.itens[0] <= len(itens) <= regra.itens[1]:
                    quantos = "1 item" if len(itens) == 1 else f"{len(itens)} itens"
                    ocorrencias.append(
                        (linha_do_rotulo, f"{rotulo} com {quantos}; de {regra.itens[0]} a {regra.itens[1]}")
                    )
                for linha, item in itens:
                    if regra.cita and not _cita(item, regra.cita, perfil):
                        ocorrencias.append((linha, f"item de {rotulo} sem ID de {comum.juntar(regra.cita, 'ou')}"))
                    if regra.formato and not re.fullmatch(regra.formato, item):
                        ocorrencias.append((linha, f"{rotulo} fora do formato: {item}"))
                    for proibido in regra.proibidos:
                        if proibido.lower() in item.lower():
                            ocorrencias.append((linha, f'{rotulo} com "{proibido}"'))
    return de_ocorrencias(CAMPOS, sorted(set(ocorrencias)))


def _colunas(texto: str, regras: list) -> Resultado:
    """A célula da coluna de cada regra `[[colunas]]`, em toda tabela fora dos blocos que tem a coluna no cabeçalho:
    vazia, ou fora do `formato`. A linha toda vazia fica com o `sobras-de-molde`, e a célula que falta vale vazia."""
    ocorrencias: list[tuple[int, str]] = []
    for _, cabecalho, corpo in tabelas(linhas_fora_de_blocos(texto)):
        for regra in regras:
            if regra.coluna not in cabecalho:
                continue
            indice = cabecalho.index(regra.coluna)
            for numero, celulas in corpo:
                if not any(celulas):
                    continue
                celula = celulas[indice] if indice < len(celulas) else ""
                if not celula:
                    ocorrencias.append((numero, f"coluna {regra.coluna} vazia"))
                elif regra.formato and not re.fullmatch(regra.formato, celula):
                    ocorrencias.append((numero, f"coluna {regra.coluna} fora do formato: {celula}"))
    return de_ocorrencias(COLUNAS, sorted(set(ocorrencias)))


def _pendencia_na_linha(
    texto: str, regras: list, texto_backlog: str | None, erro_backlog: str | None, perfil: Perfil
) -> Resultado:
    """Cada linha fora dos blocos e das citações com um termo das regras `[[pendencia_na_linha]]` cita uma pendência
    aberta do backlog; com várias, basta uma. Sai uma falha por linha, com o primeiro termo achado e, quando nenhuma
    está aberta, com a primeira pendência da linha. O `backlog ilegível` só sai quando alguma linha tem um termo."""
    termos = re.compile(
        r"\b(?:" + "|".join(f"(?:{termo})" for regra in regras for termo in regra.termos) + r")\b", re.IGNORECASE
    )
    prefixo = perfil.ids.prefixo_pendencia
    pendencia = re.compile(r"\b" + re.escape(prefixo) + r"-([0-9]{2,})\b")
    com_termo: list[tuple[int, str, str]] = []  # (linha, termo achado, texto da linha)
    for numero, linha in linhas_fora_de_blocos(texto):
        achado = None if linha.lstrip().startswith(">") else termos.search(linha)
        if achado:
            com_termo.append((numero, achado.group(0), linha))
    if com_termo and erro_backlog is not None:
        return Resultado(PENDENCIA_NA_LINHA, False, 1, None, [f"backlog ilegível: {erro_backlog}"])
    status: dict[str, str] = {}
    for _, id_, situacao in backlog.linhas_de_pendencia(texto_backlog or "", perfil):
        numero_do_id = pendencia.fullmatch(id_)
        if numero_do_id:
            status.setdefault(_formatar_id(prefixo, int(numero_do_id.group(1))), situacao)
    ocorrencias: list[tuple[int, str]] = []
    for numero, termo, linha in com_termo:
        citadas = [_formatar_id(prefixo, int(n)) for n in pendencia.findall(linha)]
        if not citadas:
            ocorrencias.append((numero, f'"{termo}" sem pendência na linha'))
        elif not any(status.get(id_, "").startswith(backlog.PREFIXO_ABERTA) for id_ in citadas):
            primeira = citadas[0]
            if primeira not in status:
                ocorrencias.append((numero, f'"{termo}" com {primeira}, que não está no backlog'))
            else:
                ocorrencias.append((numero, f'"{termo}" com {primeira}, que não está aberta: {status[primeira]}'))
    return de_ocorrencias(PENDENCIA_NA_LINHA, ocorrencias)


def checar_versao(
    raiz: Path,
    relativo: str,
    texto_documento: str,
    texto_molde: str,
    texto_backlog: str | None,
    perfil: Perfil,
    erro_backlog: str | None = None,
) -> list[Resultado]:
    """As seis verificações sobre textos já lidos, de qualquer versão (disco, índice ou commit), e as das regras do
    perfil que casam com o documento, depois delas: `campos`, `colunas` e `pendencia-na-linha`, esta com as
    pendências de `texto_backlog`.

    Documento numa pasta de fase pode citar os IDs definidos nos artefatos da tabela de `texto_backlog` da fase
    dele e das anteriores, lidos do disco; fora das pastas de fase, só os dele mesmo. `erro_backlog` é o motivo
    por que o backlog não pôde ser lido; sem ele e sem `texto_backlog`, nenhum ID de fora vale.
    """
    definidos_fora: frozenset[str] = frozenset()
    erro_fora = None
    fase = perfil.fase_do_documento(relativo)
    if fase is not None:
        ate_a_fase = perfil.fases[: perfil.fases.index(fase) + 1]
        if erro_backlog is not None:
            erro_fora = erro_backlog
        elif texto_backlog is not None:
            definidos_fora = frozenset(ids_definidos_nas_fases(raiz, texto_backlog, perfil, ate_a_fase))
    resultados = checar_textos(texto_documento, texto_molde, perfil, definidos_fora, erro_fora)
    regras_de_campos = _regras_que_casam(perfil.campos, relativo, perfil)
    if regras_de_campos:
        resultados.append(_campos(texto_documento, regras_de_campos, perfil))
    regras_de_colunas = _regras_que_casam(perfil.colunas, relativo, perfil)
    if regras_de_colunas:
        resultados.append(_colunas(texto_documento, regras_de_colunas))
    regras_de_termos = _regras_que_casam(perfil.pendencia_na_linha, relativo, perfil)
    if regras_de_termos:
        resultados.append(_pendencia_na_linha(texto_documento, regras_de_termos, texto_backlog, erro_backlog, perfil))
    return resultados


def _resumo(resultado: Resultado) -> str:
    if resultado.nome == A_CONFIRMAR:
        return f"{resultado.nome}: {resultado.ocorrencias}"
    aviso = resultado.nome == ACEITE_RENUMERADO and resultado.ocorrencias > 0
    if resultado.aviso:
        plural = "ocorrência" if resultado.ocorrencias == 1 else "ocorrências"
        return (f"{resultado.nome}: AVISO: {resultado.ocorrencias} {plural}, "
                f"verificação da v{resultado.aviso}, posterior à aprovação")
    if resultado.ok and not aviso:
        return f"{resultado.nome}: OK"
    plural = "ocorrência" if resultado.ocorrencias == 1 else "ocorrências"
    primeira = f", primeira em L{resultado.primeira_linha}" if resultado.primeira_linha is not None else ""
    return f"{resultado.nome}: {'AVISO' if aviso else 'FALHA'}: {resultado.ocorrencias} {plural}{primeira}"


def formatar_resultados(resultados: list[Resultado], verbose: bool) -> str:
    """Uma linha de resumo por verificação; com `verbose`, os detalhes vêm abaixo, com dois espaços de recuo."""
    linhas = []
    for resultado in resultados:
        linhas.append(_resumo(resultado))
        if verbose:
            linhas += ["  " + detalhe for detalhe in resultado.detalhes]
    return "".join(linha + "\n" for linha in linhas)
