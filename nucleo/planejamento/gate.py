"""Gate de fase (spec 2a, §6.1): pré-condição e itens de script e de leitor frio do checklist, com as verificações do
núcleo."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import backlog
import checar
import comum
import der
import diagramas
import estado
import passagem
from perfil import Fase, Gate, Perfil

AJUDA = """\
Roda os itens de script do checklist de um gate, na ordem do perfil, e assina o que o revisor do gate vai ler.

Pré-condições, cada uma com uma linha de recusa e saída 1, sem assinatura: o STATUS.md válido; o gate no perfil
(`gate desconhecido: <gate>; os do perfil: <gates>`), com checklist; a `Fase` atual igual à que o gate fecha
(`<gate> fecha a fase <fase>, e a Fase atual é <fase>`); o gate ainda não aprovado.

Saída: uma linha por item de script ou de leitor frio, `<item> <verificação>: PASS`,
`FAIL: <primeiro problema> (e mais <k>)` ou `INFO: <dado>`, com cada problema abaixo no `--verbose`; depois,
`revisor: itens <itens>; humano: item <item>`, os itens que o script não roda; por último, sempre,
`Assinatura: sha256:<12 hexadecimais>`, o hash dos itens do gate, de cada artefato da fase na ordem da tabela
(caminho e conteúdo, ou `ausente`), do arquivo de decisões, do `CLAUDE.md` da raiz e, com o item de leitor frio, do
gabarito que ele avalia (caminho e conteúdo, ou `sem gabarito`). Sai com 0 só sem FAIL. Abaixo, `<c>` é o caminho de um artefato e `<n>`, uma linha.

- `artefatos-da-fase`: todo `.md` da pasta da fase, fora das subpastas com o nome da pasta de moldes, está na tabela
  de artefatos com status `aprovado` e existe no disco, e todo obrigatório da fase está na tabela. Falha, entre
  outras: `<c> com status <s> (L<n>)`, `<c> fora da tabela de artefatos`, `<c> obrigatório e fora da tabela`.
- `checar-da-fase`: o `checar` passa em todo artefato da fase, e nenhum ID é definido em dois documentos.
- `ids-citados-definidos`: todo ID citado nos artefatos da fase é definido num artefato da fase ou de fase anterior
  (`<c>:<n>: <ID> citado e não definido`).
- `drawio-em-dia`: todo `.drawio` da pasta da fase, fora das subpastas com o nome da pasta de moldes, tem ao lado o
  `.drawio.svg` da mesma versão, como confere a verificação `drawio` do `checar`
  (`<arquivo>.svg de outra versão do <arquivo> (<k> células diferem, primeira <id>); exporte de novo`).
- `pendencias-do-gate`: nenhuma pendência aberta tem o marcador do gate no destino.
- `versao-limpa`: o `Versao-aprovacao` está `—`.
- `a-confirmar`: nunca falha; sai como `INFO`, com a contagem de `[A CONFIRMAR` por artefato.

Do DER físico, com a seção `[der]` do perfil; sem ela, falham com `perfil sem a seção [der]`, e com o documento de
`[der]` ausente ou com o formato inválido, com `<c>: arquivo ausente` ou
`formato do DER inválido (<k> problemas); rode harness.py checar <c>`:

- `der-rastreado`: as colunas, as tabelas e o "Não persistido" cobrem o modelo conceitual e os atributos das
  entidades, pelas regras do `der-rastreio` do `checar`.
- `der-em-dia`: o DDL e o bloco `erDiagram` estão como o `der gerar` os deixaria (`harness.py der conferir`).
- `workbench-em-dia`: o manifesto do Workbench existe, é da versão atual do DDL e lista só arquivos que existem.

Com parâmetros, chaves do próprio item; `documentos` e `por` são padrões relativos à pasta do planejamento, que casam
com os artefatos da fase na tabela:

- `ids-cobertos` (`documentos`, `prefixos` e os opcionais `definidos_em` e `quando`): todo ID dos `prefixos` definido
  em fase anterior é citado, direto ou numa faixa, num artefato que casa com `documentos`
  (`<ID> sem citação em <documentos> (definido em <c>:<n>)`). Com `definidos_em`, padrões como os de `documentos`, os
  IDs vêm dos artefatos da tabela que casam com eles, de qualquer fase e status, e sem nenhum o item falha com
  `nenhum artefato da tabela casa com <padrões>`. Com `quando` (`{ campo = "<rótulo>", formato = "<regex>" }`), só
  conta o ID definido num título cuja seção tem o campo com um item que casa por inteiro com `formato`.
- `secoes-com-id` (`documentos`, `titulo`, `prefixos`): toda seção cujo título começa por `titulo` cita um ID dos
  `prefixos` antes do próximo título de nível igual ou acima (`<c>:<n>: "<título>" sem ID de <prefixos>`).
- `coluna-com-texto` (`documentos`, `secao`, `coluna`, `texto`): a seção `secao` tem uma tabela com a coluna
  `coluna` e ao menos uma linha, e a célula dessa coluna é `texto` em todas.
- `coluna-sem-texto` (`documentos`, `secao`, `coluna`, `texto`): a mesma tabela, e nenhuma célula da coluna contém
  `texto` (`<c>:<n>: "<texto>" na coluna "<coluna>"; troque pelo valor decidido`); seção e tabela ausentes dão as
  recusas da `coluna-com-texto`. Ao contrário dos outros itens, `documentos` vale para os artefatos de todas as
  fases, para o gate de uma fase cobrar documentos de outra.
- `ligados` (`documentos`, `por`): todo artefato que casa com `documentos` é destino de um link, sem a âncora, de um
  que casa com `por`; o link externo ou que sai da raiz não conta (`<c> sem link vindo de <por>`).
- `er-sem-atributos` (`documentos`): o artefato tem um bloco de código que começa por `erDiagram`, sem `{` nem `PK`
  ou `FK` como palavra; os marcadores de cardinalidade não contam.
- `adr-minimos` (`documento`, `secao`): cada item `- [ ] <texto>` da seção `secao` do molde do documento está na
  mesma seção do documento como `- [x] <texto> — <ligação>`, e a ligação é o título de um `### Decisão: <título>`
  do documento ou `não se aplica: <motivo>` (`<c>:<n>: item mínimo "<item>" sem [x]`, `... sem ligação; ...`,
  `... ligado a "<título>", que não é uma decisão do documento`, `<c>: item mínimo "<item>" ausente; ...`).
- `adr-com-requisito` (`documento`): cada `### Decisão:` do documento tem `- **Status:**` (`proposto`, `aceito` ou
  `substituído por <título>` de outra decisão dele), `- **Data:**` em `AAAA-MM-DD` e uma Justificativa (o item
  `- **Justificativa:**` e as linhas que o continuam) que cita um ID definido nas fases até a atual
  (`<c>:<n>: decisão "<título>" sem ...`); sem nenhuma decisão, `<c>: nenhuma decisão ### Decisão:`.
- `dependencias` (`documento`, `titulo`, `campo`, `grupo`, `grupos`): em cada seção cujo título começa por `titulo`
  e cita um ID, as dependências, os IDs e as pendências que os itens do campo `campo` citam, são seções do
  documento ou pendências do backlog, de qualquer status; o grupo, o primeiro item do campo `grupo`, está na coluna
  da tabela de `grupos` (`{ secao = "<título>", coluna = "<coluna>" }`, a primeira tabela da seção com a coluna),
  cuja ordem é a dos grupos; nenhuma seção depende de outra de grupo posterior; e não há ciclo
  (`<c>:<n>: <ID> depende de <ID>, que não é uma seção do documento`,
  `<c>:<n>: <ID> depende de <pendência>, que não está no backlog`, `<c>:<n>: grupo "<valor>" fora da tabela <secao>`,
  `<c>:<n>: <ID> depende de <ID>, do grupo posterior "<grupo>"` e, no fim, `<c>: ciclo: <ID> → ... → <ID>`, um por
  ciclo). Sem a tabela, falha com `<c>: sem a seção "<secao>"` ou
  `<c>:<n>: seção "<secao>" sem tabela com a coluna "<coluna>"`, e as conferências de grupo param.

`documento` é um caminho relativo à pasta do planejamento, e o molde dele é o que o `harness.py molde` resolve.

Da passagem, com a seção `[passagem]` do perfil, que o item pede:

- `areas-cobertas`: todo "Onde vale" das regras de arquitetura (`RA-NN: ... Onde vale: <valor>. Como se confere:`)
  do arquivo de `caminhos.adrs`, fora de bloco de código, casa com os nomes da coluna da área da tabela de
  `[passagem] areas`, do mais longo para o mais curto, separados por `, ` ou ` e `
  (`<adrs>:<n>: área sem linha na tabela das áreas: <resto>`); sem a tabela, falha só com
  `tabela das áreas não achada: <documento> § <seção>`.

Do leitor frio, o item do tipo `leitor-frio` (a verificação `leitor-frio`): o gabarito do gate de data mais recente
em `caminhos.leitor_frio`, de nome `<gate>-<AAAA-MM-DD>.md` com data válida, passa só com a seção `## Resultado` do
`harness.py passagem leitor`, todo item do Gabarito `certa`, o formato da linha `Exportação:` igual ao atual e o
`sha256` dela igual ao da exportação do HEAD, refeita em memória. Falha com a primeira causa, nesta ordem:
`sem gabarito de <gate> em <pasta>`, `<g>: gabarito inválido: <motivo>`, `<g>: sem Resultado`,
`<g>: linha Exportação fora do formato`, `<g>: formato <n>, atual <m>`, `<g>: exportação falhou: <mensagem>`,
`<g>: exportação recusada: <primeira recusa>`, `<g>: exportação desatualizada; rode harness.py passagem leitor <g>`
e `<g>: item <n> não certo` ou `<g>: itens <n> e <m> não certos`, em que `<g>` é o caminho do gabarito. Os avisos
da exportação não contam.

Artefato ilegível vira problema (`<c>: arquivo ausente`, `<c>: não está em UTF-8`). Backlog ilegível faz falhar o
item que o lê, com `backlog ilegível: <motivo>`, menos o `a-confirmar`, que sai como `INFO`.
"""

PASS = "PASS"
FAIL = "FAIL"
INFO = "INFO"
STATUS_APROVADO = "aprovado"
_APROVADO_EM = "aprovado em "
_SEM_VERSAO = "—"
# Marcadores de cardinalidade do mermaid (`||--o{`, `}o..||`); a chave deles não é atributo.
_RE_CARDINALIDADE = re.compile(r"(?:\|o|\|\||\}o|\}\|)(?:--|\.\.)(?:o\||\|\||o\{|\|\{)")
_RE_CHAVE = re.compile(r"\b(?:PK|FK)\b")


class PreCondicao(Exception):
    """O gate não pode rodar agora. `mensagem` diz o motivo, numa linha."""

    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


@dataclass(frozen=True)
class Resultado:
    """Um item de script. `situacao` é PASS, FAIL ou INFO; `resumo` é a evidência curta (FAIL) ou o dado (INFO)."""

    numero: int
    verificacao: str
    situacao: str
    resumo: str
    detalhes: tuple[str, ...]


@dataclass(frozen=True)
class _Contexto:
    raiz: Path
    perfil: Perfil
    fase: Fase
    gate: Gate
    status: dict[str, str]

    @property
    def pasta(self) -> str:
        """Pasta da fase, relativa à raiz: `<planejamento>/<id da fase>`."""
        return f"{self.perfil.caminhos.planejamento.rstrip('/')}/{self.fase.id}"


def conferir_precondicao(raiz: Path, perfil: Perfil, nome: str) -> _Contexto:
    """STATUS.md válido, gate com checklist no perfil, `Fase` atual igual à que o gate fecha e gate não aprovado."""
    try:
        status = estado.ler(raiz / perfil.caminhos.status, perfil)
    except estado.EstadoInvalido as erro:
        raise PreCondicao(f"STATUS.md inválido: {erro.mensagem}") from None
    fase = perfil.fase_do_gate(nome)
    if fase is None:
        raise PreCondicao(f"gate desconhecido: {nome}; os do perfil: {comum.juntar(perfil.nomes_dos_gates)}")
    gate = perfil.gates.get(nome)
    if gate is None:
        raise PreCondicao(f"{nome} sem checklist no perfil")
    if status["Fase"] != fase.id:
        raise PreCondicao(f"{nome} fecha a fase {fase.id}, e a Fase atual é {status['Fase']}")
    if status[nome].startswith(_APROVADO_EM):
        raise PreCondicao(f"{nome} já está {status[nome]}")
    return _Contexto(raiz, perfil, fase, gate, status)


def _resumir(problemas: list[str]) -> str:
    return problemas[0] + (f" (e mais {len(problemas) - 1})" if len(problemas) > 1 else "")


def _resultado(problemas: list[str]) -> tuple[str, str, list[str]]:
    return (FAIL, _resumir(problemas), problemas) if problemas else (PASS, "", [])


def _artefatos(ctx: _Contexto) -> list[tuple[int, str, str]]:
    return backlog.artefatos_da_pasta(backlog.ler(ctx.raiz / ctx.perfil.caminhos.backlog), ctx.pasta)


def _arquivos_da_pasta(ctx: _Contexto, padrao: str) -> list[str]:
    """Caminhos, relativos à raiz, dos arquivos da pasta da fase que casam com `padrao`, fora das subpastas com o nome
    da pasta de moldes."""
    pasta = ctx.raiz / ctx.pasta
    moldes = Path(ctx.perfil.moldes.pasta).name
    if not pasta.is_dir():
        return []
    return sorted(
        arquivo.relative_to(ctx.raiz).as_posix()
        for arquivo in pasta.rglob(padrao)
        if arquivo.is_file() and moldes not in arquivo.relative_to(pasta).parts[:-1]
    )


def _documentos_da_pasta(ctx: _Contexto) -> list[str]:
    """Caminhos, relativos à raiz, dos `.md` da pasta da fase, fora das subpastas com o nome da pasta de moldes."""
    return _arquivos_da_pasta(ctx, "*.md")


def _artefatos_da_fase(ctx: _Contexto) -> tuple[str, str, list[str]]:
    linhas = _artefatos(ctx)
    problemas = [] if linhas else [f"nenhum artefato de {ctx.pasta}/ na tabela de artefatos"]
    for linha, caminho, status in linhas:
        if not status.startswith(STATUS_APROVADO):
            problemas.append(f"{caminho} com status {status or 'vazio'} (L{linha})")
        if not (ctx.raiz / caminho).is_file():
            problemas.append(f"{caminho} na tabela e ausente do disco (L{linha})")
    na_tabela = {caminho for _, caminho, _ in linhas}
    planejamento = ctx.perfil.caminhos.planejamento.rstrip("/")
    obrigatorios = [f"{planejamento}/{caminho}" for caminho in ctx.fase.obrigatorios]
    problemas += [
        f"{caminho} fora da tabela de artefatos"
        for caminho in _documentos_da_pasta(ctx)
        if caminho not in na_tabela and caminho not in obrigatorios
    ]
    for caminho in obrigatorios:
        if caminho not in na_tabela:
            problemas.append(f"{caminho} obrigatório e fora da tabela")
            if not (ctx.raiz / caminho).is_file():
                problemas.append(f"{caminho} obrigatório e ausente do disco")
    return (FAIL, _resumir(problemas), problemas) if problemas else (PASS, "", [])


def _checar_da_fase(ctx: _Contexto) -> tuple[str, str, list[str]]:
    problemas: list[str] = []
    detalhes: list[str] = []
    definicoes: dict[str, list[tuple[str, int]]] = {}
    for _, caminho, _ in _artefatos(ctx):
        try:
            resultados = checar.checar_arquivo(ctx.raiz, Path(caminho), ctx.perfil)
            texto = comum.ler_texto(ctx.raiz / caminho)
        except checar.EntradaInvalida as erro:
            problemas.append(f"{caminho}: {erro.mensagem}")
            detalhes.append(problemas[-1])
            continue
        for resultado in resultados:
            if not resultado.ok:
                problemas.append(f"{caminho}: {checar.formatar_resultados([resultado], False).strip()}")
                detalhes += [problemas[-1]] + ["  " + detalhe for detalhe in resultado.detalhes]
        for linha, id_ in checar.ids_definidos(texto, ctx.perfil):
            definicoes.setdefault(id_, []).append((caminho, linha))
    for id_, onde in definicoes.items():
        if len({caminho for caminho, _ in onde}) > 1:
            problemas.append(f"{id_} definido em {comum.juntar(f'{caminho}:{linha}' for caminho, linha in onde)}")
            detalhes.append(problemas[-1])
    return (FAIL, _resumir(problemas), detalhes) if problemas else (PASS, "", [])


def _artefatos_que_casam(ctx: _Contexto, padroes: tuple[str, ...], todas_as_fases: bool = False) -> list[str]:
    """Artefatos da fase, ou de todas com `todas_as_fases`, na ordem da tabela, cujo caminho relativo à pasta do
    planejamento casa com um padrão."""
    planejamento = ctx.perfil.caminhos.planejamento.rstrip("/")
    artefatos = (backlog.artefatos_da_pasta(backlog.ler(ctx.raiz / ctx.perfil.caminhos.backlog), planejamento)
                 if todas_as_fases else _artefatos(ctx))
    return [
        caminho
        for _, caminho, _ in artefatos
        if any(comum.casa_padrao(padrao, caminho[len(planejamento) + 1:]) for padrao in padroes)
    ]


def _textos_dos_artefatos(ctx: _Contexto, caminhos: list[str]) -> tuple[dict[str, str], list[str]]:
    """O texto de cada artefato legível e um problema por artefato ilegível."""
    textos: dict[str, str] = {}
    problemas: list[str] = []
    for caminho in caminhos:
        try:
            textos[caminho] = comum.ler_texto(ctx.raiz / caminho)
        except FileNotFoundError:
            problemas.append(f"{caminho}: arquivo ausente")
        except UnicodeDecodeError:
            problemas.append(f"{caminho}: não está em UTF-8")
        except OSError as erro:
            problemas.append(f"{caminho}: ilegível ({comum.motivo_do_sistema(erro)})")
    return textos, problemas


def _definidos(ctx: _Contexto, ate_a_atual: bool) -> dict[str, tuple[str, int]]:
    """IDs definidos nos artefatos das fases anteriores à atual, e também na atual com `ate_a_atual`."""
    indice = ctx.perfil.fases.index(ctx.fase) + (1 if ate_a_atual else 0)
    texto_backlog = backlog.ler(ctx.raiz / ctx.perfil.caminhos.backlog)
    return checar.ids_definidos_nas_fases(ctx.raiz, texto_backlog, ctx.perfil, ctx.perfil.fases[:indice])


def _ids_citados_definidos(ctx: _Contexto) -> tuple[str, str, list[str]]:
    definidos = _definidos(ctx, ate_a_atual=True)
    textos, problemas = _textos_dos_artefatos(ctx, [caminho for _, caminho, _ in _artefatos(ctx)])
    for caminho, texto in textos.items():
        citados, faixas = checar.ids_citados(texto, ctx.perfil)
        problemas += [f"{caminho}:{linha}: {id_} citado e não definido" for linha, id_ in citados if id_ not in definidos]
        problemas += [f"{caminho}:{linha}: {problema}" for linha, problema in faixas]
    return _resultado(problemas)


def _ids_cobertos(
    ctx: _Contexto,
    documentos: tuple[str, ...],
    prefixos: tuple[str, ...],
    definidos_em: tuple[str, ...] = (),
    quando: dict[str, str] | None = None,
) -> tuple[str, str, list[str]]:
    if definidos_em and not _artefatos_que_casam(ctx, definidos_em, todas_as_fases=True):
        return _resultado([f"nenhum artefato da tabela casa com {comum.juntar(definidos_em, 'ou')}"])
    texto_backlog = backlog.ler(ctx.raiz / ctx.perfil.caminhos.backlog)
    a_cobrir = checar.ids_a_cobrir(ctx.raiz, texto_backlog, ctx.perfil, ctx.fase, prefixos, definidos_em, quando)
    if not a_cobrir:
        return PASS, "", []
    textos, problemas = _textos_dos_artefatos(ctx, _artefatos_que_casam(ctx, documentos))
    citados = {id_ for texto in textos.values() for _, id_ in checar.ids_citados(texto, ctx.perfil)[0]}
    problemas += [
        f"{id_} sem citação em {comum.juntar(documentos, 'ou')} (definido em {caminho}:{linha})"
        for id_, (caminho, linha) in a_cobrir.items()
        if id_ not in citados
    ]
    return _resultado(problemas)


def _secoes_com_id(
    ctx: _Contexto, documentos: tuple[str, ...], titulo: str, prefixos: tuple[str, ...]
) -> tuple[str, str, list[str]]:
    textos, problemas = _textos_dos_artefatos(ctx, _artefatos_que_casam(ctx, documentos))
    for caminho, texto in textos.items():
        citados = checar.ids_citados(texto, ctx.perfil)[0]
        for linha_do_titulo, titulo_da_secao, linhas in checar.secoes(texto, titulo):
            numeros = {numero for numero, _ in linhas}
            if not any(
                linha in numeros and id_.startswith(prefixo + "-") for linha, id_ in citados for prefixo in prefixos
            ):
                problemas.append(
                    f'{caminho}:{linha_do_titulo}: "{titulo_da_secao}" sem ID de {comum.juntar(prefixos, "ou")}'
                )
    return _resultado(problemas)


def _conferir_coluna(
    ctx: _Contexto, documentos: tuple[str, ...], secao: str, coluna: str, problema_da_celula,
    todas_as_fases: bool = False,
) -> tuple[str, str, list[str]]:
    """Acha, em cada artefato, a tabela da seção `secao` com a coluna `coluna` e passa cada célula dela a
    `problema_da_celula(caminho, linha, célula)`, que devolve o problema ou None. Seção ausente, tabela sem a coluna e
    tabela sem linhas são recusadas aqui."""
    textos, problemas = _textos_dos_artefatos(ctx, _artefatos_que_casam(ctx, documentos, todas_as_fases))
    for caminho, conteudo in textos.items():
        achadas = checar.secoes(conteudo, secao)
        if not achadas:
            problemas.append(f'{caminho}: sem a seção "{secao}"')
            continue
        linha_do_titulo, _, linhas = achadas[0]
        tabela = next(((n, cab, corpo) for n, cab, corpo in checar.tabelas(linhas) if coluna in cab), None)
        if tabela is None:
            problemas.append(f'{caminho}:{linha_do_titulo}: seção "{secao}" sem tabela com a coluna "{coluna}"')
            continue
        linha_do_cabecalho, cabecalho, corpo = tabela
        if not corpo:
            problemas.append(f'{caminho}:{linha_do_cabecalho}: tabela da seção "{secao}" sem linhas')
            continue
        indice = cabecalho.index(coluna)
        for numero, celulas in corpo:
            problema = problema_da_celula(caminho, numero, celulas[indice] if indice < len(celulas) else "")
            if problema is not None:
                problemas.append(problema)
    return _resultado(problemas)


def _coluna_com_texto(
    ctx: _Contexto, documentos: tuple[str, ...], secao: str, coluna: str, texto: str
) -> tuple[str, str, list[str]]:
    return _conferir_coluna(
        ctx, documentos, secao, coluna,
        lambda caminho, numero, celula: None if celula == texto
        else f'{caminho}:{numero}: "{celula}" na coluna "{coluna}", esperado "{texto}"',
    )


def _coluna_sem_texto(
    ctx: _Contexto, documentos: tuple[str, ...], secao: str, coluna: str, texto: str
) -> tuple[str, str, list[str]]:
    return _conferir_coluna(
        ctx, documentos, secao, coluna,
        lambda caminho, numero, celula: None if texto not in celula
        else f'{caminho}:{numero}: "{texto}" na coluna "{coluna}"; troque pelo valor decidido',
        todas_as_fases=True,
    )


def _ligados(ctx: _Contexto, documentos: tuple[str, ...], por: tuple[str, ...]) -> tuple[str, str, list[str]]:
    textos, problemas = _textos_dos_artefatos(ctx, _artefatos_que_casam(ctx, por))
    destinos = {destino for caminho, texto in textos.items() for destino in checar.destinos_de_links(texto, caminho)}
    problemas += [
        f"{caminho} sem link vindo de {comum.juntar(por, 'ou')}"
        for caminho in _artefatos_que_casam(ctx, documentos)
        if caminho not in destinos
    ]
    return _resultado(problemas)


def _er_sem_atributos(ctx: _Contexto, documentos: tuple[str, ...]) -> tuple[str, str, list[str]]:
    textos, problemas = _textos_dos_artefatos(ctx, _artefatos_que_casam(ctx, documentos))
    for caminho, texto in textos.items():
        diagramas = [
            linhas for _, linhas in checar.blocos_de_codigo(texto)
            if next((linha.strip() for _, linha in linhas if linha.strip()), "") == "erDiagram"
        ]
        if not diagramas:
            problemas.append(f"{caminho}: sem bloco erDiagram")
            continue
        for linhas in diagramas:
            for numero, linha in linhas:
                sem_cardinalidade = _RE_CARDINALIDADE.sub(" ", linha)
                if "{" in sem_cardinalidade or _RE_CHAVE.search(sem_cardinalidade):
                    problemas.append(f"{caminho}:{numero}: atributo no erDiagram: {linha.strip()}")
    return _resultado(problemas)


def _der_lido(ctx: _Contexto):
    """(documento, modelo, None) do DER do perfil, ou (None, None, resultado de FAIL): perfil sem `[der]`, documento
    ausente ou ilegível, formato inválido."""
    try:
        documento = der.documento_do_perfil(ctx.perfil)
    except der.ErroDer as erro:
        return None, None, _resultado([erro.mensagem])
    textos, problemas = _textos_dos_artefatos(ctx, [documento])
    if problemas:
        return None, None, _resultado(problemas)
    modelo, erros = der.ler(textos[documento])
    if erros:
        contagem = f"{len(erros)} {'problema' if len(erros) == 1 else 'problemas'}"
        return None, None, _resultado([f"formato do DER inválido ({contagem}); rode harness.py checar {documento}"])
    return documento, modelo, None


def _der_rastreado(ctx: _Contexto) -> tuple[str, str, list[str]]:
    documento, modelo, falha = _der_lido(ctx)
    return falha or _resultado(der.rastrear(ctx.raiz, ctx.perfil, modelo, documento))


def _der_em_dia(ctx: _Contexto) -> tuple[str, str, list[str]]:
    documento, _, falha = _der_lido(ctx)
    return falha or _resultado(der.conferir(ctx.raiz, ctx.perfil, documento))


def _workbench_em_dia(ctx: _Contexto) -> tuple[str, str, list[str]]:
    _, _, falha = _der_lido(ctx)
    return falha or _resultado(der.conferir_manifesto(ctx.raiz, ctx.perfil))


def _drawio_em_dia(ctx: _Contexto) -> tuple[str, str, list[str]]:
    return _resultado([problema for caminho in _arquivos_da_pasta(ctx, "*.drawio")
                       for problema in diagramas.svg_em_dia(ctx.raiz, caminho)])


_RE_ITEM_MINIMO = re.compile(r"- \[([ xX])\] (.*)")
_LIGACAO = " — "
_NAO_SE_APLICA = "não se aplica:"
_TITULO_DE_DECISAO = "### Decisão:"
_RE_DATA = re.compile(r"\d{4}-\d{2}-\d{2}")
_RE_SUBSTITUIDO = re.compile(r"substituído por (.+)")


def _decisoes(texto: str) -> list[tuple[int, str, list[tuple[int, str]]]]:
    """(linha do título, título, linhas) de cada seção `### Decisão: <título>`."""
    return [(numero, titulo[len(_TITULO_DE_DECISAO):].strip(), linhas)
            for numero, titulo, linhas in checar.secoes(texto, _TITULO_DE_DECISAO)]


def _adr_minimos(ctx: _Contexto, documento: str, secao: str) -> tuple[str, str, list[str]]:
    caminho = f"{ctx.perfil.caminhos.planejamento}/{documento}"
    molde = checar.mostrar(ctx.raiz, checar.resolver_molde(ctx.raiz, Path(caminho), ctx.perfil))
    textos, problemas = _textos_dos_artefatos(ctx, [caminho, molde])
    if problemas:
        return _resultado(problemas)
    secoes_do_molde = checar.secoes(textos[molde], secao)
    secoes_do_documento = checar.secoes(textos[caminho], secao)
    if not secoes_do_molde:
        problemas.append(f'{molde}: sem a seção "{secao}"')
    if not secoes_do_documento:
        problemas.append(f'{caminho}: sem a seção "{secao}"')
    if problemas:
        return _resultado(problemas)
    minimos = [achado.group(2).strip() for _, linha in secoes_do_molde[0][2]
               for achado in [_RE_ITEM_MINIMO.fullmatch(linha.strip())] if achado]
    marcados = [(numero, achado.group(1), achado.group(2).strip()) for numero, linha in secoes_do_documento[0][2]
                for achado in [_RE_ITEM_MINIMO.fullmatch(linha.strip())] if achado]
    titulos = {titulo for _, titulo, _ in _decisoes(textos[caminho])}
    for item in minimos:
        achado = next(((numero, marca, resto) for numero, marca, resto in marcados
                       if resto == item or resto.startswith(item + _LIGACAO)), None)
        if achado is None:
            problemas.append(f'{caminho}: item mínimo "{item}" ausente; copie-o do molde como - [x] {item} — '
                             f'<título da decisão>')
            continue
        numero, marca, resto = achado
        onde = f'{caminho}:{numero}: item mínimo "{item}"'
        if marca == " ":
            problemas.append(f"{onde} sem [x]")
            continue
        ligacao = resto[len(item) + len(_LIGACAO):].strip() if resto != item else ""
        motivo = ligacao[len(_NAO_SE_APLICA):].strip() if ligacao.startswith(_NAO_SE_APLICA) else None
        if not ligacao or motivo == "":
            problemas.append(f'{onde} sem ligação; termine com " — <título de uma decisão>" ou '
                             f'" — não se aplica: <motivo>"')
        elif motivo is None and ligacao not in titulos:
            problemas.append(f'{onde} ligado a "{ligacao}", que não é uma decisão do documento')
    return _resultado(problemas)


def _campo(linhas: list[tuple[int, str]], nome: str) -> str | None:
    """O valor do item `- **<nome>:**` de primeiro nível, ou None sem ele."""
    inicio = f"- **{nome}:**"
    return next((linha[len(inicio):].strip() for _, linha in linhas if linha.startswith(inicio)), None)


def _justificativa(linhas: list[tuple[int, str]]) -> str:
    """O item `- **Justificativa:**` e as linhas que o continuam, até o próximo item de primeiro nível."""
    partes: list[str] = []
    dentro = False
    for _, linha in linhas[1:]:
        if linha.startswith("- "):
            dentro = linha.startswith("- **Justificativa:**")
        if dentro:
            partes.append(linha)
    return "\n".join(partes)


def _adr_com_requisito(ctx: _Contexto, documento: str) -> tuple[str, str, list[str]]:
    caminho = f"{ctx.perfil.caminhos.planejamento}/{documento}"
    textos, problemas = _textos_dos_artefatos(ctx, [caminho])
    if problemas:
        return _resultado(problemas)
    decisoes = _decisoes(textos[caminho])
    if not decisoes:
        return _resultado([f"{caminho}: nenhuma decisão {_TITULO_DE_DECISAO}"])
    titulos = {titulo for _, titulo, _ in decisoes}
    definidos = _definidos(ctx, ate_a_atual=True)
    prefixos = comum.juntar(ctx.perfil.ids.prefixos, "ou")
    for numero, titulo, linhas in decisoes:
        onde = f'{caminho}:{numero}: decisão "{titulo}"'
        status = _campo(linhas, "Status")
        substituida = _RE_SUBSTITUIDO.fullmatch(status or "")
        if status is None:
            problemas.append(f"{onde} sem Status; use - **Status:** proposto, aceito ou substituído por <título>")
        elif substituida and substituida.group(1).strip() not in titulos:
            problemas.append(f'{onde} substituída por "{substituida.group(1).strip()}", que não é uma decisão do '
                             f'documento')
        elif status not in ("proposto", "aceito") and not substituida:
            problemas.append(f"{onde} com Status inválido: {status}")
        if not _RE_DATA.fullmatch(_campo(linhas, "Data") or ""):
            problemas.append(f"{onde} sem Data em AAAA-MM-DD")
        citados, _ = checar.ids_citados(_justificativa(linhas), ctx.perfil)
        if not any(id_ in definidos for _, id_ in citados):
            problemas.append(f"{onde} sem Justificativa que cite um ID definido de {prefixos}; cite o requisito que "
                             f"motiva a decisão")
    return _resultado(problemas)


def _ids_do_item(item: str, pendencia: re.Pattern, perfil: Perfil) -> list[str]:
    """Os IDs que o item cita, na ordem do texto: os de `ids.prefixos` pelo `checar.ids_citados`, com as faixas, e as
    pendências pelo padrão `pendencia`, todos com o número normalizado."""
    ids: list[str] = []
    inicio = 0
    for achado in pendencia.finditer(item):
        ids += [id_ for _, id_ in checar.ids_citados(item[inicio:achado.start()], perfil)[0]]
        ids.append(f"{perfil.ids.prefixo_pendencia}-{int(achado.group(1)):02d}")
        inicio = achado.end()
    return ids + [id_ for _, id_ in checar.ids_citados(item[inicio:], perfil)[0]]


def _ciclos(arestas: dict[str, list[str]]) -> list[list[str]]:
    """Um ciclo por componente fortemente ligado que tem um, na ordem das chaves de `arestas`: o caminho parte do
    primeiro nó do componente e segue a primeira aresta que fica nele até repetir um nó."""
    def alcance(inicio: str) -> set[str]:
        vistos: set[str] = set()
        pilha = list(arestas[inicio])
        while pilha:
            atual = pilha.pop()
            if atual not in vistos:
                vistos.add(atual)
                pilha += arestas[atual]
        return vistos

    alcances = {no: alcance(no) for no in arestas}
    ciclos: list[list[str]] = []
    vistos: set[str] = set()
    for no in arestas:
        if no in vistos or no not in alcances[no]:
            continue
        componente = {no} | {outro for outro in alcances[no] if no in alcances[outro]}
        vistos |= componente
        caminho = [no]
        while True:
            proximo = next(destino for destino in arestas[caminho[-1]] if destino in componente)
            if proximo in caminho:
                ciclos.append(caminho[caminho.index(proximo):] + [proximo])
                break
            caminho.append(proximo)
    return ciclos


def _dependencias(
    ctx: _Contexto, documento: str, titulo: str, campo: str, grupo: str, grupos: dict[str, str]
) -> tuple[str, str, list[str]]:
    texto_backlog = backlog.ler(ctx.raiz / ctx.perfil.caminhos.backlog)
    caminho = f"{ctx.perfil.caminhos.planejamento.rstrip('/')}/{documento}"
    textos, problemas = _textos_dos_artefatos(ctx, [caminho])
    if caminho not in textos:
        return _resultado(problemas)
    texto = textos[caminho]
    prefixo = ctx.perfil.ids.prefixo_pendencia
    pendencia = re.compile(r"\b" + re.escape(prefixo) + r"-([0-9]{2,})\b")
    no_backlog: set[str] = set()
    for _, id_, _ in backlog.linhas_de_pendencia(texto_backlog, ctx.perfil):
        achado = pendencia.fullmatch(id_)
        if achado:
            no_backlog.add(f"{prefixo}-{int(achado.group(1)):02d}")

    secao, coluna = grupos["secao"], grupos["coluna"]
    ordem = None  # posição de cada grupo na coluna; None sem a tabela, e as conferências de grupo param
    achadas = checar.secoes(texto, secao)
    if not achadas:
        problemas.append(f'{caminho}: sem a seção "{secao}"')
    else:
        linha_do_titulo, _, linhas = achadas[0]
        tabela = next(((cab, corpo) for _, cab, corpo in checar.tabelas(linhas) if coluna in cab), None)
        if tabela is None:
            problemas.append(f'{caminho}:{linha_do_titulo}: seção "{secao}" sem tabela com a coluna "{coluna}"')
        else:
            cabecalho, corpo = tabela
            indice = cabecalho.index(coluna)
            ordem = {}
            for _, celulas in corpo:
                if indice < len(celulas) and celulas[indice]:
                    ordem.setdefault(celulas[indice], len(ordem))

    # (ID, (linha, grupo) ou None, [(linha, dependência)]) de cada seção com ID no título, na ordem do documento.
    secoes = []
    for _, titulo_da_secao, linhas in checar.secoes(texto, titulo):
        ids_do_titulo = checar.ids_citados(titulo_da_secao, ctx.perfil)[0]
        if not ids_do_titulo:
            continue
        do_grupo = checar.itens_do_campo(linhas, grupo)
        do_campo = checar.itens_do_campo(linhas, campo)
        dependencias = [(linha, id_) for linha, item in (do_campo[1] if do_campo else [])
                        for id_ in _ids_do_item(item, pendencia, ctx.perfil)]
        secoes.append((ids_do_titulo[0][1], do_grupo[1][0] if do_grupo and do_grupo[1] else None, dependencias))
    grupo_de: dict[str, tuple[int, str] | None] = {}
    for id_, grupo_da_secao, _ in secoes:
        grupo_de.setdefault(id_, grupo_da_secao)

    for id_, grupo_da_secao, dependencias in secoes:
        if ordem is not None and grupo_da_secao is not None and grupo_da_secao[1] not in ordem:
            problemas.append(f'{caminho}:{grupo_da_secao[0]}: grupo "{grupo_da_secao[1]}" fora da tabela {secao}')
        for linha, dependencia in dependencias:
            if pendencia.fullmatch(dependencia):
                if dependencia not in no_backlog:
                    problemas.append(f"{caminho}:{linha}: {id_} depende de {dependencia}, que não está no backlog")
                continue
            if dependencia not in grupo_de:
                problemas.append(
                    f"{caminho}:{linha}: {id_} depende de {dependencia}, que não é uma seção do documento"
                )
                continue
            outro = grupo_de[dependencia]
            if (ordem is not None and grupo_da_secao is not None and outro is not None
                    and grupo_da_secao[1] in ordem and outro[1] in ordem
                    and ordem[outro[1]] > ordem[grupo_da_secao[1]]):
                problemas.append(f'{caminho}:{linha}: {id_} depende de {dependencia}, do grupo posterior "{outro[1]}"')

    arestas: dict[str, list[str]] = {id_: [] for id_, _, _ in secoes}
    for id_, _, dependencias in secoes:
        arestas[id_] += [dependencia for _, dependencia in dependencias if dependencia in arestas]
    problemas += [f"{caminho}: ciclo: {' → '.join(ciclo)}" for ciclo in _ciclos(arestas)]
    return _resultado(problemas)


def _pendencias_do_gate(ctx: _Contexto) -> tuple[str, str, list[str]]:
    texto = backlog.ler(ctx.raiz / ctx.perfil.caminhos.backlog)
    abertas = backlog.abertas_com_marcador(texto, ctx.perfil, ctx.gate.marcador_pendencia)
    if not abertas:
        return PASS, "", []
    ids = [id_ for _, id_ in abertas]
    aberta = "aberta" if len(ids) == 1 else "abertas"
    resumo = f'{comum.juntar(ids)} {aberta} com "{ctx.gate.marcador_pendencia}" no destino'
    return FAIL, resumo, [f"{id_} (L{linha})" for linha, id_ in abertas]


def _versao_limpa(ctx: _Contexto) -> tuple[str, str, list[str]]:
    marcada = ctx.status["Versao-aprovacao"]
    if marcada == _SEM_VERSAO:
        return PASS, "", []
    if estado.CAMPO_PACOTE in ctx.status:
        pacote = comum.juntar(estado.documentos(ctx.status))
        return FAIL, f"Versao-aprovacao {marcada} marcada para o pacote {pacote}", []
    return FAIL, f"Versao-aprovacao {marcada} marcada para {ctx.status['Documento']}", []


def _a_confirmar(ctx: _Contexto) -> tuple[str, str, list[str]]:
    """Nunca falha: informa a contagem de `[A CONFIRMAR` em cada artefato da fase."""
    try:
        linhas = _artefatos(ctx)
    except backlog.BacklogIlegivel as erro:
        return INFO, f"backlog ilegível: {erro.mensagem}", []
    contagens = []
    for _, caminho, _ in linhas:
        nome = caminho[len(ctx.pasta) + 1:]
        try:
            contagens.append(f"{nome} {checar.contar_a_confirmar(comum.ler_texto(ctx.raiz / caminho))}")
        except (OSError, UnicodeDecodeError):
            contagens.append(f"{nome} ilegível")
    return INFO, ", ".join(contagens) or "nenhum artefato na tabela", []


def _areas_cobertas(ctx: _Contexto) -> tuple[str, str, list[str]]:
    return _resultado(passagem.areas_cobertas(comum.leitor_do_disco(ctx.raiz), ctx.perfil))


_VERIFICACOES = {
    "artefatos-da-fase": _artefatos_da_fase,
    "checar-da-fase": _checar_da_fase,
    "ids-citados-definidos": _ids_citados_definidos,
    "ids-cobertos": _ids_cobertos,
    "secoes-com-id": _secoes_com_id,
    "coluna-com-texto": _coluna_com_texto,
    "coluna-sem-texto": _coluna_sem_texto,
    "ligados": _ligados,
    "er-sem-atributos": _er_sem_atributos,
    "der-rastreado": _der_rastreado,
    "der-em-dia": _der_em_dia,
    "workbench-em-dia": _workbench_em_dia,
    "drawio-em-dia": _drawio_em_dia,
    "adr-minimos": _adr_minimos,
    "adr-com-requisito": _adr_com_requisito,
    "dependencias": _dependencias,
    "areas-cobertas": _areas_cobertas,
    "pendencias-do-gate": _pendencias_do_gate,
    "versao-limpa": _versao_limpa,
    "a-confirmar": _a_confirmar,
}


def rodar(
    raiz: Path, perfil: Perfil, nome: str, executar=subprocess.run, so_script: bool = False
) -> list[Resultado]:
    """Confere a pré-condição e roda os itens de script e de leitor frio do gate, na ordem do perfil. O `executar`
    roda o git da exportação do leitor frio; com `so_script`, o item de leitor frio fica de fora, sem exportação.
    Lança PreCondicao."""
    ctx = conferir_precondicao(raiz, perfil, nome)
    resultados = []
    for item in ctx.gate.itens:
        if item.tipo == "leitor-frio" and not so_script:
            falha = passagem.falha_do_leitor(raiz, perfil, nome, executar)
            resultados.append(Resultado(item.numero, "leitor-frio", FAIL if falha else PASS, falha, ()))
            continue
        if item.tipo != "script":
            continue
        try:
            situacao, resumo, detalhes = _VERIFICACOES[item.verificacao](ctx, **item.parametros)
        except backlog.BacklogIlegivel as erro:
            situacao, resumo, detalhes = FAIL, f"backlog ilegível: {erro.mensagem}", []
        resultados.append(Resultado(item.numero, item.verificacao, situacao, resumo, tuple(detalhes)))
    return resultados


def _bytes_ou_ausente(caminho: Path) -> bytes:
    try:
        return caminho.read_bytes()
    except OSError:
        return b"ausente"


def assinatura(raiz: Path, perfil: Perfil, nome: str) -> str:
    """`sha256:` e 12 hexadecimais sobre o que o revisor do gate lê: os itens do gate, os artefatos da fase na ordem
    da tabela (caminho e conteúdo, ou `ausente`), o arquivo de decisões, o CLAUDE.md da raiz e, com o item de leitor
    frio, o gabarito mais recente do gate (caminho e conteúdo, ou a parte fixa `sem gabarito`).

    Cada parte entra no hash como `<tamanho em bytes>:` seguido dela. Backlog ilegível entra como a parte fixa
    `backlog ilegivel`, no lugar dos artefatos.
    """
    partes = [
        json.dumps([item.tipo, item.verificacao, item.criterio, item.parametros], ensure_ascii=False, sort_keys=True)
        .encode("utf-8")
        for item in perfil.gates[nome].itens
    ]
    fase = perfil.fase_do_gate(nome)
    pasta = f"{perfil.caminhos.planejamento.rstrip('/')}/{fase.id}"
    try:
        artefatos = backlog.artefatos_da_pasta(backlog.ler(raiz / perfil.caminhos.backlog), pasta)
    except backlog.BacklogIlegivel:
        partes.append(b"backlog ilegivel")
    else:
        for _, caminho, _ in artefatos:
            partes += [caminho.encode("utf-8"), _bytes_ou_ausente(raiz / caminho)]
    partes += [_bytes_ou_ausente(raiz / perfil.caminhos.decisoes), _bytes_ou_ausente(raiz / "CLAUDE.md")]
    if any(item.tipo == "leitor-frio" for item in perfil.gates[nome].itens):
        gabarito = passagem.gabarito_mais_recente(raiz, perfil, nome)
        partes += ([b"sem gabarito"] if gabarito is None
                   else [gabarito.encode("utf-8"), _bytes_ou_ausente(raiz / gabarito)])
    resumo = hashlib.sha256()
    for parte in partes:
        resumo.update(f"{len(parte)}:".encode("ascii") + parte)
    return "sha256:" + resumo.hexdigest()[:12]


def _numeros(numeros: list[int]) -> str:
    if not numeros:
        return "nenhum"
    return ("item " if len(numeros) == 1 else "itens ") + comum.juntar(str(numero) for numero in numeros)


def linha(resultado: Resultado) -> str:
    """A linha do item na saída do gate: `<item> <verificação>: <situação>`, com `: <resumo>` quando há resumo."""
    texto = f"{resultado.numero} {resultado.verificacao}: {resultado.situacao}"
    return texto + (f": {resultado.resumo}" if resultado.resumo else "")


def formatar(resultados: list[Resultado], gate: Gate, verbose: bool) -> str:
    """Uma linha por item de script e de leitor frio e, por último, os números dos itens de revisor e humano."""
    linhas = []
    for resultado in resultados:
        linhas.append(linha(resultado))
        if verbose:
            linhas += ["  " + detalhe for detalhe in resultado.detalhes]
    revisor = [item.numero for item in gate.itens if item.tipo == "revisor"]
    humano = [item.numero for item in gate.itens if item.tipo == "humano"]
    linhas.append(f"revisor: {_numeros(revisor)}; humano: {_numeros(humano)}")
    return "".join(linha + "\n" for linha in linhas)
