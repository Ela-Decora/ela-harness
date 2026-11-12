"""Perfil do projeto (spec da fase 2a, §5): tudo o que é do projeto, lido de .claude/perfil.toml e validado."""
from __future__ import annotations

import dataclasses
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import comum
import perfil_comum
from perfil_comum import PerfilComum, PerfilInvalido
from perfil_comum import chaves as _chaves
from perfil_comum import normalizado as _normalizado
from perfil_comum import secao as _secao
from perfil_comum import texto as _texto
from perfil_comum import textos as _textos

AJUDA = """\
Valida o perfil do projeto, `.claude/perfil.toml`, e imprime um resumo dele, ou o bloco "Este projeto" de uma skill.

Sem opção, imprime quatro linhas: `perfil válido: <nome>`, as fases com os gates, os checklists com os itens por
tipo e os prefixos de ID. Todo comando que lê o perfil o valida inteiro; o primeiro problema sai com 1 e
`perfil inválido: <motivo>`.

Com `--para <skill>` (`refinar-documento`, `gate-fase`, `gerar-modulos` ou `assessor`), imprime o bloco que a skill
injeta ao carregar e sai sempre com 0, porque outro código abortaria a skill; o erro vem na primeira linha,
`ERRO: <motivo>`. O bloco acima do teto da skill, de 3.000 caracteres na `gate-fase`, 1.600 na `refinar-documento` e
1.500 nas outras, sai inteiro, depois de `AVISO: bloco com <N> caracteres, acima de <teto>`. Só os da `gate-fase` e da
`gerar-modulos` leem o STATUS.md, para mostrar a fase atual e o gate dela; com ele inválido, a primeira linha é
`ERRO no STATUS.md: <motivo>`. Na fase cujo gate não tem item `ligados`, a `gerar-modulos` dá
`ERRO: <gate> sem item ligados; a skill não se aplica à fase <fase>`.

Seções e chaves, todas obrigatórias, menos `[gates]` e as opcionais:

- `[projeto]`: `nome`; `harness`, opcional, `planejamento` ou `desenvolvimento`, `planejamento` por padrão; o
  perfil de desenvolvimento não vale nos comandos do planejamento. Chave desconhecida é recusada.
- `[caminhos]`, relativos à raiz: `planejamento` (a pasta das fases), `status`, `backlog`, `decisoes`, `rascunho`,
  `atritos`, `estudos` (pasta), `adrs`, `pesquisas` (pasta), `fontes` (pastas em ordem de precedência, ou `[]`),
  `leitor_frio`, opcional (a pasta dos gabaritos do teste do leitor frio), e `legenda`, opcional (a legenda gerada
  por `harness.py legenda`, fora da pasta do planejamento).
- `[moldes]`: `pasta`; `trocas_de_nome` (nome no molde para nome no documento); `placeholders` (regex que não pode
  sobrar no documento); `partes_variaveis` (regex do título do molde para a do documento; o título fica repetível);
  `mapa`, opcional (pares `[padrão, molde]`, relativos à pasta do planejamento e à pasta de moldes); `liberados`,
  opcional (caminho relativo à pasta de moldes para `sha256:` e 12 hexadecimais; o molde acrescentado ou alterado
  com esse hash passa no `moldes-intocados` do `harness.py invariantes`).
- `[[fases]]`, na ordem: `id` (a pasta da fase), `gate` (vira campo do STATUS.md), `regra` (a restrição de escrita);
  `obrigatorios`, opcional (documentos que o gate exige); `fronteira`, opcional (o corte do escopo na fase).
- `[ids]`: `prefixos`; `padroes` (o ID sem o número, começando por um prefixo); `prefixo_pendencia`;
  `prefixo_relato`, opcional, `REL` sem ele; `com_buracos`, opcional (os prefixos de ID que nunca se reusa, em que
  dividir ou tirar um deixa buraco; neles, o `checar` confere o padrão e a duplicata, sem a sequência); `formas`,
  opcional (a forma de cada ID no texto gerado do harness, uma por prefixo e na ordem dos `prefixos`, cada uma
  começando pelo dela; sem a chave, o texto mostra `<padrão>-NN`).
- `[texto]`: `adjetivos_vagos` (regex), `duvidas_de_escopo`, `sistemas_do_cliente`, `nomes_duplos`, `glossario`.
- `[der]`, opcional, com todas as chaves, os caminhos relativos à pasta do planejamento: `documento` (o `.md` do DER
  físico, numa pasta de fase), `sql` (a pasta do DDL gerado), `workbench` (a pasta dos prints e do SQL exportado
  pelo Workbench), `dialeto` (o banco do ADR: `""` até ele, depois `mysql` ou `postgres`), `conceitual` (o documento
  com o `erDiagram` das entidades), `entidades` (a pasta dos documentos delas), `tecnicas` (colunas em snake_case
  que aceitam a Origem `técnica`) e `rotulo_copia` (o texto que marca a relação de cópia, sem FK).
- `[guarda]`, opcional, com chave desconhecida recusada: `proibidos`, opcional (caminhos relativos à raiz que o
  modelo não grava, com `/**` no fim para uma pasta); `segredos_isentos`, opcional (padrões de caminho com a regra
  do `proibidos`, que a guarda e o `sem-segredos` não leem atrás de segredo); e a `[guarda.segredos]`, opcional,
  de nome (`[a-z0-9]+(-[a-z0-9]+)*`) para expressão regular que não casa com texto vazio, somada aos padrões do
  núcleo: `chave-privada`, `chave-aws`, `token-github` e `jwt`.
- `[[campos]]`, opcional, uma tabela por regra da verificação `campos` do `checar`: `documentos` (padrões relativos
  à pasta do planejamento), `titulo` (o começo do título das seções), `campo` (um rótulo, ou uma lista de rótulos,
  só para presença) e, com um rótulo só, os opcionais `itens` (`[mínimo, máximo]`), `cita` (prefixos de
  `ids.prefixos`, ou o da pendência), `formato` (regex que cada item casa por inteiro) e `proibidos` (trechos que
  nenhum item pode ter).
- `[[colunas]]`, opcional, uma tabela por regra da verificação `colunas` do `checar`: `documentos`, `coluna` (o texto
  exato do cabeçalho) e `formato`, opcional (regex que a célula casa por inteiro).
- `[[pendencia_na_linha]]`, opcional, uma tabela por regra da verificação `pendencia-na-linha` do `checar`:
  `documentos` e `termos`, regex de busca procuradas como palavra inteira e sem distinção de maiúsculas.
- `[leitor_frio]`, opcional: `perguntas`, as perguntas-tipo do teste do leitor frio. Cada uma tem `{ficha}` no lugar
  da ficha escolhida, ou não tem marcador, quando é transversal.
- `[passagem]`, opcional: `manifesto`, o caminho a partir da raiz que o `passagem publicar` commita; `areas`, uma
  tabela com `documento` (relativo à pasta do planejamento), `secao` (o texto do título, sem os `#`), `coluna_area`
  e `coluna_pastas`. Sem a seção, o `passagem exportar` recusa.
- `[ci]`, opcional, com chave desconhecida recusada: `ramo`, o ramo em que o `.github/workflows/harness.yml` gerado
  dispara, no push e no pull request; sem a tabela ou sem a chave, `main`. Com espaço, com `..` ou começando por `-`,
  é recusado.
- `[gates.<gate>]`: `marcador_pendencia` e os `[[gates.<gate>.itens]]`, numerados na ordem do arquivo, com `tipo`
  `script` (e `verificacao`, uma das do `harness.py gate`, com os parâmetros como chaves do item), `revisor`,
  `leitor-frio` ou `humano` (e `criterio`); o `leitor-frio` pede `caminhos.leitor_frio`, `[leitor_frio] perguntas`
  e `[passagem]`, e o item de script `areas-cobertas` pede `[passagem]`.

Regras que pegam quem edita:

- Todo caminho, inclusive de `mapa`, `obrigatorios` e dos parâmetros, é relativo e normalizado: sem `./`, `..`,
  `//`, barra no começo nem no fim. `obrigatorios` fica dentro da pasta da própria fase.
- `fases.id` é nome de pasta sem espaço nem barra; `fases.gate` não repete um campo do núcleo do STATUS.md; fase e
  gate não se repetem. `[gates.<gate>]` só para o gate de uma fase, com ao menos um item.
- Todo parâmetro é obrigatório, menos os opcionais da verificação (`definidos_em` e `quando` no `ids-cobertos`), e
  chave que a verificação não pede é recusada. Tipos: texto não vazio; título (de um a seis `#` e um espaço); caminho
  (um caminho normalizado, relativo à pasta do planejamento); padrões (caminhos com `*` dentro de um segmento);
  prefixos (de `ids.prefixos`); quando (tabela com `campo`, texto, e `formato`, regex); grupos (tabela com
  `secao`, título, e `coluna`, texto).
- `moldes.mapa` não repete padrão; `ids.prefixo_relato` não repete outro prefixo.
- Regex: sem flag global (use `(?i:...)`), sem grupo com nome (use `(?:...)`), sem referência a grupo; as de busca
  não casam com texto vazio.

Depois de editar, rode `harness.py perfil`, `harness.py estado` e `harness.py perfil --para <skill>` para cada skill.
Exemplo: `modelo/planejamento/.claude/perfil.toml`, na raiz do plugin.
"""

CAMINHO_PERFIL = comum.CAMINHO_PERFIL
TIPOS_DE_ITEM = ("script", "revisor", "leitor-frio", "humano")
# Tipos de parâmetro de um item de script.
TEXTO = "texto"
TITULO = "título"  # texto que começa por # a ###### e um espaço
PADROES = "padrões"  # lista de caminhos normalizados, relativos à pasta do planejamento
PREFIXOS = "prefixos"  # lista de prefixos de ids.prefixos
CAMINHO = "caminho"  # um caminho normalizado, relativo à pasta do planejamento
QUANDO = "quando"  # tabela com `campo`, texto, e `formato`, regex que um item do campo casa por inteiro
GRUPOS = "grupos"  # tabela com `secao`, título, e `coluna`, texto: a coluna que dá a ordem dos grupos
# Verificações de gate, de nome para {parâmetro: tipo}, presas por teste às funções de gate._VERIFICACOES.
VERIFICACOES: dict[str, dict[str, str]] = {
    "artefatos-da-fase": {},
    "checar-da-fase": {},
    "ids-citados-definidos": {},
    "ids-cobertos": {"documentos": PADROES, "prefixos": PREFIXOS},
    "secoes-com-id": {"documentos": PADROES, "titulo": TITULO, "prefixos": PREFIXOS},
    "coluna-com-texto": {"documentos": PADROES, "secao": TITULO, "coluna": TEXTO, "texto": TEXTO},
    "coluna-sem-texto": {"documentos": PADROES, "secao": TITULO, "coluna": TEXTO, "texto": TEXTO},
    "ligados": {"documentos": PADROES, "por": PADROES},
    "er-sem-atributos": {"documentos": PADROES},
    "der-rastreado": {},
    "der-em-dia": {},
    "workbench-em-dia": {},
    "drawio-em-dia": {},
    "adr-minimos": {"documento": CAMINHO, "secao": TITULO},
    "adr-com-requisito": {"documento": CAMINHO},
    "dependencias": {"documento": CAMINHO, "titulo": TITULO, "campo": TEXTO, "grupo": TEXTO, "grupos": GRUPOS},
    "areas-cobertas": {},
    "pendencias-do-gate": {},
    "versao-limpa": {},
    "a-confirmar": {},
}
# Parâmetros opcionais de cada verificação, de nome para {parâmetro: tipo}; a função de gate dá um valor padrão a cada um.
OPCIONAIS: dict[str, dict[str, str]] = {
    "ids-cobertos": {"definidos_em": PADROES, "quando": QUANDO},
}
# Bancos que a seção [der] aceita em `dialeto`, além do texto vazio, que vale até o ADR do banco.
DIALETOS = ("mysql", "postgres")
# Campos do STATUS.md que são do núcleo; um gate com um desses nomes tornaria o arquivo ilegível.
CAMPOS_DO_NUCLEO = ("Fase", "Documento", "Passo", "Rodada", "Proximo", "Versao-aprovacao", "Atualizado")

# Campos opcionais do STATUS.md (spec 4b, §9.1), presos por teste a estado.CAMPOS_OPCIONAIS; também não servem de gate.
CAMPOS_OPCIONAIS_DO_NUCLEO = ("Pacote", "Lote")

_RE_NOME_DE_GATE = re.compile(r"[A-Za-z][A-Za-z0-9-]*")
_RE_ID_DE_FASE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_RE_TITULO = re.compile(r"#{1,6} \S")
_RE_HASH_DO_MOLDE = re.compile(r"sha256:[0-9a-f]{12}")
# Referência a grupo por número (\1 a \99) ou condicional `(?(`, com a barra ou o parêntese fora de escape.
_RE_REFERENCIA_A_GRUPO = re.compile(r"(?<!\\)(?:\\\\)*(?:\\[1-9]|\(\?\()")


@dataclass(frozen=True)
class Caminhos:
    planejamento: str
    status: str
    backlog: str
    decisoes: str
    rascunho: str
    atritos: str
    estudos: str
    adrs: str
    pesquisas: str
    fontes: tuple[str, ...]
    leitor_frio: str = ""
    legenda: str = ""


@dataclass(frozen=True)
class Moldes:
    pasta: str
    trocas_de_nome: dict[str, str]
    placeholders: tuple[str, ...]
    partes_variaveis: dict[str, str]
    # Pares (padrão relativo à pasta do planejamento, molde relativo à pasta de moldes); vence o primeiro que casa.
    mapa: tuple[tuple[str, str], ...] = ()
    # Caminho relativo à pasta de moldes para o hash (`sha256:` e 12 hexadecimais) com que o molde pode mudar.
    liberados: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Fase:
    id: str
    gate: str
    regra: str
    # Caminhos relativos à pasta do planejamento, dentro da pasta da fase, que o gate exige na tabela de artefatos.
    obrigatorios: tuple[str, ...] = ()
    # Onde está a fronteira do MVP que vale nesta camada; vazio, a pergunta de fronteira fica em texto.
    fronteira: str = ""


@dataclass(frozen=True)
class Ids:
    prefixos: tuple[str, ...]
    padroes: tuple[str, ...]
    prefixo_pendencia: str
    prefixo_relato: str = "REL"
    # Prefixos que nunca se reusam: dividir ou tirar um ID deixa buraco, e o `ids` não confere a sequência deles.
    com_buracos: tuple[str, ...] = ()
    # A forma de cada ID no texto gerado do harness, uma por prefixo, na ordem dos prefixos; vazia sem a chave.
    formas: tuple[str, ...] = ()


@dataclass(frozen=True)
class Texto:
    adjetivos_vagos: tuple[str, ...]
    duvidas_de_escopo: tuple[str, ...]
    sistemas_do_cliente: tuple[str, ...]
    nomes_duplos: tuple[str, ...]
    glossario: str


@dataclass(frozen=True)
class ItemDoGate:
    """Item do checklist, numerado pela ordem no perfil. `verificacao` e `parametros` só no tipo script; `criterio`
    nos outros. Os parâmetros de lista viram tuplas."""

    numero: int
    tipo: str
    verificacao: str
    criterio: str
    parametros: dict[str, str | tuple[str, ...] | dict[str, str]] = field(default_factory=dict)


@dataclass(frozen=True)
class Gate:
    nome: str
    marcador_pendencia: str
    itens: tuple[ItemDoGate, ...]


@dataclass(frozen=True)
class SecaoDer:
    """Seção [der]: o documento-fonte do DER físico e as pastas ao lado dele, relativos à pasta do planejamento."""

    documento: str
    sql: str
    workbench: str
    dialeto: str  # "" até o ADR do banco; depois um de DIALETOS
    conceitual: str
    entidades: str
    tecnicas: tuple[str, ...]
    rotulo_copia: str


@dataclass(frozen=True)
class RegraCampos:
    """Regra `[[campos]]`: nos documentos que casam com `documentos`, cada seção cujo título começa por `titulo` tem
    os `campos`. Com um campo só, valem os opcionais: `itens` (mínimo e máximo), `cita` (prefixos de que cada item
    cita um ID), `formato` (regex que cada item casa por inteiro) e `proibidos` (trechos que nenhum item tem)."""

    documentos: tuple[str, ...]
    titulo: str
    campos: tuple[str, ...]
    itens: tuple[int, int] | None = None
    cita: tuple[str, ...] = ()
    formato: str = ""
    proibidos: tuple[str, ...] = ()


@dataclass(frozen=True)
class RegraColuna:
    """Regra `[[colunas]]`: nos documentos que casam com `documentos`, toda tabela com a `coluna` no cabeçalho tem a
    célula dela não vazia em cada linha e, com `formato`, casando por inteiro com ele."""

    documentos: tuple[str, ...]
    coluna: str
    formato: str = ""


@dataclass(frozen=True)
class RegraTermos:
    """Regra `[[pendencia_na_linha]]`: nos documentos que casam com `documentos`, a linha com um dos `termos` (regex
    de busca, como palavra inteira e sem distinção de maiúsculas) cita uma pendência aberta do backlog."""

    documentos: tuple[str, ...]
    termos: tuple[str, ...]


@dataclass(frozen=True)
class AreasDaPassagem:
    """A tabela das áreas do código: o `documento`, relativo à pasta do planejamento, o texto do título da `secao`,
    sem os `#`, e os cabeçalhos das colunas da área e das pastas."""

    documento: str
    secao: str
    coluna_area: str
    coluna_pastas: str


@dataclass(frozen=True)
class SecaoPassagem:
    """Seção [passagem]: o `manifesto`, a partir da raiz, e a tabela das áreas do código."""

    manifesto: str
    areas: AreasDaPassagem


@dataclass(frozen=True)
class Perfil:
    nome: str
    caminhos: Caminhos
    moldes: Moldes
    fases: tuple[Fase, ...]
    ids: Ids
    texto: Texto
    gates: dict[str, Gate]
    der: SecaoDer | None = None
    proibidos: tuple[str, ...] = ()
    campos: tuple[RegraCampos, ...] = ()
    colunas: tuple[RegraColuna, ...] = ()
    pendencia_na_linha: tuple[RegraTermos, ...] = ()
    perguntas_leitor_frio: tuple[str, ...] = ()
    passagem: SecaoPassagem | None = None
    segredos: tuple[tuple[str, str], ...] = ()
    segredos_isentos: tuple[str, ...] = ()
    ramo_do_ci: str = "main"

    @property
    def comum(self) -> PerfilComum:
        """A parte comum do perfil, como a guarda e o `sem-segredos` a leem."""
        return PerfilComum(self.nome, perfil_comum.PLANEJAMENTO, self.proibidos, self.segredos, self.segredos_isentos)

    @property
    def ids_das_fases(self) -> tuple[str, ...]:
        return tuple(fase.id for fase in self.fases)

    @property
    def nomes_dos_gates(self) -> tuple[str, ...]:
        """Um gate por fase, na ordem das fases: é a ordem da linha dos gates no STATUS.md."""
        return tuple(fase.gate for fase in self.fases)

    def fase_por_id(self, id_: str) -> Fase | None:
        return next((fase for fase in self.fases if fase.id == id_), None)

    def fase_do_gate(self, gate: str) -> Fase | None:
        return next((fase for fase in self.fases if fase.gate == gate), None)

    def fase_do_documento(self, documento: str) -> Fase | None:
        """Fase da pasta em que o documento está (`<planejamento>/<id da fase>/...`), ou None fora delas."""
        prefixo = self.caminhos.planejamento.rstrip("/") + "/"
        if not documento.startswith(prefixo):
            return None
        partes = documento[len(prefixo):].split("/")
        return self.fase_por_id(partes[0]) if len(partes) > 1 else None


def _pares(tabela: dict, chave: str, onde: str) -> dict[str, str]:
    if chave not in tabela:
        raise PerfilInvalido(f"falta a chave {onde}.{chave}")
    valor = tabela[chave]
    if not isinstance(valor, dict) or not all(isinstance(v, str) and v for v in valor.values()):
        raise PerfilInvalido(f"{onde}.{chave} deve ser uma tabela de textos")
    return dict(valor)


def _compila(padrao: str, onde: str, busca: bool = False) -> None:
    """Confere o padrão sozinho e como o núcleo o usa: numa alternação com os outros, dentro de grupos seus.

    Lá dentro quebram a flag global, como `(?i)`, que só vale no começo da regex inteira; o grupo com nome, que se
    repetiria ou bateria com os nomes do núcleo; e a referência a grupo, que passaria a apontar para outro. O padrão
    de busca no texto também não pode casar com texto vazio: acharia ocorrência em toda posição.
    """
    inicio = f"regex inválida em {onde}: {padrao}"
    try:
        compilado = re.compile(padrao)
    except re.error as erro:
        raise PerfilInvalido(f"{inicio} ({erro})") from None
    # Antes do 3.11, a flag global fora do começo só avisa (DeprecationWarning); aqui o aviso conta como erro.
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            re.compile("(?:)" + padrao)
    except (re.error, DeprecationWarning):
        raise PerfilInvalido(f"{inicio} (flag global; use a forma com escopo, como (?i:...))") from None
    if compilado.groupindex:
        raise PerfilInvalido(f"{inicio} (grupo com nome; use (?:...))")
    if _RE_REFERENCIA_A_GRUPO.search(padrao):
        raise PerfilInvalido(f"{inicio} (referência a grupo)")
    if busca and compilado.search("") is not None:
        raise PerfilInvalido(f"{inicio} (casa com texto vazio)")


def _mapa(moldes: dict) -> tuple[tuple[str, str], ...]:
    """`moldes.mapa`, opcional: lista de pares [padrão, molde], os dois normalizados, sem padrão repetido."""
    bruto = moldes.get("mapa", [])
    if not isinstance(bruto, list) or not all(
        isinstance(par, list) and len(par) == 2 and all(isinstance(parte, str) and parte for parte in par)
        for par in bruto
    ):
        raise PerfilInvalido("moldes.mapa deve ser uma lista de pares [padrão, molde]")
    for padrao, molde in bruto:
        _normalizado(padrao, "moldes.mapa")
        _normalizado(molde, "moldes.mapa")
    _sem_repeticao([padrao for padrao, _ in bruto], "padrão repetido em moldes.mapa")
    return tuple((padrao, molde) for padrao, molde in bruto)


def _comeca_pelo_prefixo(texto: str, prefixo: str) -> bool:
    """O padrão ou a forma de um ID começa pelo prefixo: é o próprio prefixo ou ele seguido de `-`."""
    return texto == prefixo or texto.startswith(prefixo + "-")


def _sem_repeticao(valores: list[str], rotulo: str) -> None:
    vistos: set[str] = set()
    for valor in valores:
        if valor in vistos:
            raise PerfilInvalido(f"{rotulo}: {valor}")
        vistos.add(valor)


def _fases(dados: dict) -> tuple[Fase, ...]:
    brutas = dados.get("fases")
    if brutas is None:
        raise PerfilInvalido("falta [[fases]]")
    if not isinstance(brutas, list) or not brutas or not all(isinstance(fase, dict) for fase in brutas):
        raise PerfilInvalido("[[fases]] precisa de ao menos uma fase")
    fases = []
    for numero, bruta in enumerate(brutas, start=1):
        onde = f"fases[{numero}]"
        fase = Fase(_texto(bruta, "id", onde), _texto(bruta, "gate", onde), _texto(bruta, "regra", onde))
        if not _RE_ID_DE_FASE.fullmatch(fase.id):
            raise PerfilInvalido(f"{onde}.id deve ser um nome de pasta sem espaço nem barra: {fase.id}")
        if not _RE_NOME_DE_GATE.fullmatch(fase.gate) or fase.gate in CAMPOS_DO_NUCLEO + CAMPOS_OPCIONAIS_DO_NUCLEO:
            raise PerfilInvalido(f"{onde}.gate não serve como campo do STATUS.md: {fase.gate}")
        obrigatorios: tuple[str, ...] = ()
        if "obrigatorios" in bruta:
            obrigatorios = _textos(bruta, "obrigatorios", onde)
            for caminho in obrigatorios:
                _normalizado(caminho, f"{onde}.obrigatorios")
                if not caminho.startswith(fase.id + "/"):
                    raise PerfilInvalido(f"{onde}.obrigatorios fora da pasta da fase: {caminho}")
        fronteira = _texto(bruta, "fronteira", onde) if "fronteira" in bruta else ""
        fases.append(dataclasses.replace(fase, obrigatorios=obrigatorios, fronteira=fronteira))
    _sem_repeticao([fase.id for fase in fases], "fase repetida")
    _sem_repeticao([fase.gate for fase in fases], "gate repetido")
    return tuple(fases)


def _tabela(onde: str, nome: str, valor, chaves: tuple[str, str]) -> dict[str, str]:
    """O parâmetro em tabela: exatamente as duas `chaves`, as duas com texto não vazio."""
    if not (isinstance(valor, dict) and set(valor) == set(chaves)
            and all(isinstance(v, str) and v.strip() for v in valor.values())):
        raise PerfilInvalido(
            f"{onde}: {nome} deve ser uma tabela com {chaves[0]} e {chaves[1]}, os dois textos não vazios"
        )
    return {chave: valor[chave] for chave in chaves}


def _parametros(
    onde: str, verificacao: str, bruto: dict, ids: Ids
) -> dict[str, str | tuple[str, ...] | dict[str, str]]:
    """Parâmetros do item de script, conferidos contra os de VERIFICACOES[verificacao] e os opcionais de
    OPCIONAIS[verificacao]: primeiro os obrigatórios, depois os opcionais presentes."""
    obrigatorios = VERIFICACOES[verificacao]
    opcionais = OPCIONAIS.get(verificacao, {})
    desconhecida = next(
        (chave for chave in bruto
         if chave not in ("tipo", "verificacao") and chave not in obrigatorios and chave not in opcionais),
        None,
    )
    if desconhecida is not None:
        raise PerfilInvalido(f"{onde} com chave desconhecida: {desconhecida}")
    ausente = next((nome for nome in obrigatorios if nome not in bruto), None)
    if ausente is not None:
        raise PerfilInvalido(f"{onde} sem o parâmetro {ausente}")
    aceitos = {**obrigatorios, **{nome: tipo for nome, tipo in opcionais.items() if nome in bruto}}
    parametros: dict[str, str | tuple[str, ...] | dict[str, str]] = {}
    for nome, tipo in aceitos.items():
        valor = bruto[nome]
        if tipo == QUANDO:
            parametros[nome] = _tabela(onde, nome, valor, ("campo", "formato"))
            _compila(parametros[nome]["formato"], f"{onde}, quando.formato")
            continue
        if tipo == GRUPOS:
            parametros[nome] = _tabela(onde, nome, valor, ("secao", "coluna"))
            if not _RE_TITULO.match(parametros[nome]["secao"]):
                raise PerfilInvalido(
                    f"{onde}: {nome}.secao deve começar por # a ###### e um espaço: {parametros[nome]['secao']}"
                )
            continue
        if tipo in (TEXTO, TITULO, CAMINHO):
            if not isinstance(valor, str) or not valor.strip():
                raise PerfilInvalido(f"{onde}: {nome} deve ser um texto não vazio")
            if tipo == TITULO and not _RE_TITULO.match(valor):
                raise PerfilInvalido(f"{onde}: {nome} deve começar por # a ###### e um espaço: {valor}")
            if tipo == CAMINHO and not comum.caminho_normalizado(valor):
                raise PerfilInvalido(f"{onde}: caminho não normalizado em {nome}: {valor}")
            parametros[nome] = valor
            continue
        if not isinstance(valor, list) or not valor or not all(isinstance(v, str) and v.strip() for v in valor):
            raise PerfilInvalido(f"{onde}: {nome} deve ser uma lista não vazia de textos não vazios")
        for item in valor:
            if tipo == PADROES and not comum.caminho_normalizado(item):
                raise PerfilInvalido(f"{onde}: caminho não normalizado em {nome}: {item}")
            if tipo == PREFIXOS and item not in ids.prefixos:
                raise PerfilInvalido(f"{onde}: prefixo fora de ids.prefixos em {nome}: {item}")
        parametros[nome] = tuple(valor)
    return parametros


def _item(
    gate: str, numero: int, bruto: dict, ids: Ids, leitor_frio: str, perguntas: tuple[str, ...], com_passagem: bool
) -> ItemDoGate:
    onde = f"item {numero} de gates.{gate}"
    tipo = bruto.get("tipo")
    if tipo is None:
        raise PerfilInvalido(f"{onde} sem tipo")
    if tipo not in TIPOS_DE_ITEM:
        raise PerfilInvalido(f"{onde} com tipo desconhecido: {tipo}")
    if tipo == "script":
        verificacao = bruto.get("verificacao")
        if verificacao is None:
            raise PerfilInvalido(f"{onde} sem verificacao")
        if verificacao not in VERIFICACOES:
            raise PerfilInvalido(f"{onde} com verificação desconhecida: {verificacao}")
        if verificacao == "areas-cobertas" and not com_passagem:
            raise PerfilInvalido(f"{onde} com a verificação areas-cobertas pede [passagem]")
        return ItemDoGate(numero, tipo, verificacao, "", _parametros(onde, verificacao, bruto, ids))
    criterio = bruto.get("criterio")
    if not isinstance(criterio, str) or not criterio.strip():
        raise PerfilInvalido(f"{onde} sem criterio")
    if tipo == "leitor-frio" and not leitor_frio:
        raise PerfilInvalido(f"{onde} do tipo leitor-frio pede caminhos.leitor_frio")
    if tipo == "leitor-frio" and not perguntas:
        raise PerfilInvalido(f"{onde} do tipo leitor-frio pede [leitor_frio] perguntas")
    if tipo == "leitor-frio" and not com_passagem:
        raise PerfilInvalido(f"{onde} do tipo leitor-frio pede [passagem]")
    return ItemDoGate(numero, tipo, "", criterio)


def _gates(
    dados: dict, fases: tuple[Fase, ...], ids: Ids, leitor_frio: str, perguntas: tuple[str, ...], com_passagem: bool
) -> dict[str, Gate]:
    """Os checklists de `[gates]`; `leitor_frio` e `perguntas` são o `caminhos.leitor_frio` e as `[leitor_frio]
    perguntas`, que o item do tipo leitor-frio pede; `com_passagem` diz se há `[passagem]`, que o item
    `areas-cobertas` pede."""
    brutos = dados.get("gates", {})
    if not isinstance(brutos, dict):
        raise PerfilInvalido("[gates] deve ser uma tabela")
    com_fase = {fase.gate for fase in fases}
    gates = {}
    for nome, bruto in brutos.items():
        if nome not in com_fase:
            raise PerfilInvalido(f"[gates.{nome}] sem fase com esse gate")
        if not isinstance(bruto, dict):
            raise PerfilInvalido(f"[gates.{nome}] deve ser uma tabela")
        marcador = _texto(bruto, "marcador_pendencia", f"gates.{nome}")
        itens = bruto.get("itens")
        if not isinstance(itens, list) or not itens or not all(isinstance(item, dict) for item in itens):
            raise PerfilInvalido(f"[gates.{nome}] precisa de ao menos um [[gates.{nome}.itens]]")
        gates[nome] = Gate(nome, marcador, tuple(
            _item(nome, n, item, ids, leitor_frio, perguntas, com_passagem) for n, item in enumerate(itens, start=1)
        ))
    return gates


_RE_SNAKE_CASE = re.compile(r"[a-z][a-z0-9_]*")


def _der(dados: dict, fases: tuple[Fase, ...]) -> SecaoDer | None:
    """`[der]`, opcional; dentro dela, todas as chaves são obrigatórias, e `dialeto` aceita o texto vazio."""
    if "der" not in dados:
        return None
    bruta = _secao(dados, "der")
    caminhos = {chave: _texto(bruta, chave, "der") for chave in ("documento", "sql", "workbench")}
    if "dialeto" not in bruta:
        raise PerfilInvalido("falta a chave der.dialeto")
    dialeto = bruta["dialeto"]
    if dialeto != "" and dialeto not in DIALETOS:
        raise PerfilInvalido('der.dialeto deve ser "", ' + comum.juntar([f'"{d}"' for d in DIALETOS], "ou"))
    for chave in ("conceitual", "entidades"):
        caminhos[chave] = _texto(bruta, chave, "der")
    tecnicas = _textos(bruta, "tecnicas", "der", vazia=False)
    rotulo_copia = _texto(bruta, "rotulo_copia", "der")
    for chave, caminho in caminhos.items():
        _normalizado(caminho, f"der.{chave}")
    documento = caminhos["documento"]
    if not any(documento.startswith(fase.id + "/") for fase in fases):
        raise PerfilInvalido(f"der.documento fora das pastas de fase: {documento}")
    if not documento.endswith(".md"):
        raise PerfilInvalido(f"der.documento deve ser um .md: {documento}")
    for nome in tecnicas:
        if not _RE_SNAKE_CASE.fullmatch(nome):
            raise PerfilInvalido(f"der.tecnicas com nome fora de snake_case: {nome}")
    return SecaoDer(documento, caminhos["sql"], caminhos["workbench"], dialeto, caminhos["conceitual"],
                    caminhos["entidades"], tecnicas, rotulo_copia)


def _lista_de_regras(dados: dict, secao: str, chaves: tuple[str, ...]) -> list[tuple[str, dict]]:
    """(onde, tabela) de cada regra da lista opcional `[[<secao>]]`, com `onde` igual a `<secao>[<n>]`; recusa a
    lista que não é de tabelas e a chave fora de `chaves`."""
    brutas = dados.get(secao, [])
    if not isinstance(brutas, list) or not all(isinstance(bruta, dict) for bruta in brutas):
        raise PerfilInvalido(f"[[{secao}]] deve ser uma lista de tabelas")
    regras = []
    for numero, bruta in enumerate(brutas, start=1):
        onde = f"{secao}[{numero}]"
        desconhecida = next((chave for chave in bruta if chave not in chaves), None)
        if desconhecida is not None:
            raise PerfilInvalido(f"{onde} com chave desconhecida: {desconhecida}")
        regras.append((onde, bruta))
    return regras


def _documentos(bruta: dict, onde: str) -> tuple[str, ...]:
    """Os padrões de `documentos` da regra: uma lista não vazia de caminhos normalizados."""
    documentos = _textos(bruta, "documentos", onde, vazia=False)
    for padrao in documentos:
        _normalizado(padrao, f"{onde}.documentos")
    return documentos


_CHAVES_DE_CAMPOS = ("documentos", "titulo", "campo", "itens", "cita", "formato", "proibidos")


def _itens(bruta: dict, onde: str) -> tuple[int, int] | None:
    if "itens" not in bruta:
        return None
    valor = bruta["itens"]
    if not (isinstance(valor, list) and len(valor) == 2
            and all(isinstance(n, int) and not isinstance(n, bool) for n in valor) and 1 <= valor[0] <= valor[1]):
        raise PerfilInvalido(f"{onde}.itens deve ser [mínimo, máximo], com 1 ≤ mínimo ≤ máximo")
    return valor[0], valor[1]


def _campos(dados: dict, ids: Ids) -> tuple[RegraCampos, ...]:
    """`[[campos]]`, opcional: uma regra por tabela; o `campo` em lista só pede presença."""
    regras = []
    for onde, bruta in _lista_de_regras(dados, "campos", _CHAVES_DE_CAMPOS):
        documentos = _documentos(bruta, onde)
        titulo = _texto(bruta, "titulo", onde)
        if not _RE_TITULO.match(titulo):
            raise PerfilInvalido(f"{onde}.titulo deve começar por # a ###### e um espaço: {titulo}")
        if "campo" not in bruta:
            raise PerfilInvalido(f"falta a chave {onde}.campo")
        campo = bruta["campo"]
        if isinstance(campo, str) and campo.strip():
            campos: tuple[str, ...] = (campo,)
        elif isinstance(campo, list) and campo and all(isinstance(c, str) and c.strip() for c in campo):
            campos = tuple(campo)
            if any(chave in bruta for chave in ("itens", "cita", "formato", "proibidos")):
                raise PerfilInvalido(f"{onde}: itens, cita, formato e proibidos pedem um campo só")
        else:
            raise PerfilInvalido(f"{onde}.campo deve ser um texto ou uma lista não vazia de textos não vazios")
        itens = _itens(bruta, onde)
        cita: tuple[str, ...] = ()
        if "cita" in bruta:
            cita = _textos(bruta, "cita", onde, vazia=False)
            fora = next((p for p in cita if p not in ids.prefixos and p != ids.prefixo_pendencia), None)
            if fora is not None:
                raise PerfilInvalido(f"{onde}: prefixo fora de ids.prefixos e de ids.prefixo_pendencia em cita: {fora}")
        formato = ""
        if "formato" in bruta:
            formato = _texto(bruta, "formato", onde)
            _compila(formato, f"{onde}.formato")
        proibidos = _textos(bruta, "proibidos", onde, vazia=False) if "proibidos" in bruta else ()
        regras.append(RegraCampos(documentos, titulo, campos, itens, cita, formato, proibidos))
    return tuple(regras)


def _colunas(dados: dict) -> tuple[RegraColuna, ...]:
    """`[[colunas]]`, opcional: uma regra por tabela, com o `formato` opcional."""
    regras = []
    for onde, bruta in _lista_de_regras(dados, "colunas", ("documentos", "coluna", "formato")):
        documentos = _documentos(bruta, onde)
        coluna = _texto(bruta, "coluna", onde)
        formato = ""
        if "formato" in bruta:
            formato = _texto(bruta, "formato", onde)
            _compila(formato, f"{onde}.formato")
        regras.append(RegraColuna(documentos, coluna, formato))
    return tuple(regras)


def _pendencia_na_linha(dados: dict) -> tuple[RegraTermos, ...]:
    """`[[pendencia_na_linha]]`, opcional: uma regra por tabela, com os `termos` como regex de busca."""
    regras = []
    for onde, bruta in _lista_de_regras(dados, "pendencia_na_linha", ("documentos", "termos")):
        documentos = _documentos(bruta, onde)
        termos = _textos(bruta, "termos", onde, vazia=False)
        for termo in termos:
            _compila(termo, f"{onde}.termos", busca=True)
        regras.append(RegraTermos(documentos, termos))
    return tuple(regras)


_CHAVES_DE_AREAS = ("documento", "secao", "coluna_area", "coluna_pastas")


def _passagem(dados: dict) -> SecaoPassagem | None:
    """`[passagem]`, opcional: a tabela, as chaves desconhecidas, as que faltam, os textos e, por fim, os caminhos."""
    if "passagem" not in dados:
        return None
    bruta = _secao(dados, "passagem")
    _chaves(bruta, ("manifesto", "areas"), "passagem")
    manifesto = _texto(bruta, "manifesto", "passagem")
    areas_brutas = bruta["areas"]
    if not isinstance(areas_brutas, dict):
        raise PerfilInvalido("passagem.areas deve ser uma tabela")
    _chaves(areas_brutas, _CHAVES_DE_AREAS, "passagem.areas")
    areas = AreasDaPassagem(*(_texto(areas_brutas, chave, "passagem.areas") for chave in _CHAVES_DE_AREAS))
    _normalizado(manifesto, "passagem.manifesto")
    _normalizado(areas.documento, "passagem.areas.documento")
    return SecaoPassagem(manifesto, areas)


def _ramo_do_ci(dados: dict) -> str:
    """`[ci]`, opcional: a tabela, a chave desconhecida e o `ramo`, um texto sem espaço, sem `..` e sem `-` no começo.
    Sem a tabela, ou sem o `ramo` nela, `main`."""
    if "ci" not in dados:
        return "main"
    bruta = _secao(dados, "ci")
    perfil_comum.sem_desconhecida(bruta, ("ramo",), "ci")
    if "ramo" not in bruta:
        return "main"
    ramo = _texto(bruta, "ramo", "ci")
    if re.search(r"\s", ramo) or ".." in ramo or ramo.startswith("-"):
        raise PerfilInvalido(f"ci.ramo fora do formato de branch: {ramo}")
    return ramo


def validar(dados: dict) -> Perfil:
    """Confere o perfil já lido do TOML e devolve o Perfil. Lança PerfilInvalido no primeiro problema.

    A parte comum vem primeiro, pelo `perfil_comum`: o `[projeto]` e o `[guarda]`; o perfil de desenvolvimento e o
    de planejamento com a tabela `[desenvolvimento]` são recusados. Depois, as seções do planejamento, na ordem do
    arquivo: caminhos, moldes, fases, ids, texto, der, as regras do `checar` (campos, colunas e pendencia_na_linha),
    leitor_frio, passagem, ci e gates.
    """
    comum_ = perfil_comum.validar(dados)
    if comum_.harness != perfil_comum.PLANEJAMENTO:
        raise PerfilInvalido(
            "perfil de desenvolvimento ([projeto] harness); os comandos do planejamento não valem aqui"
        )
    if "desenvolvimento" in dados:
        raise PerfilInvalido("perfil de planejamento com a tabela [desenvolvimento]")
    nome = comum_.nome

    caminhos_brutos = _secao(dados, "caminhos")
    caminhos = Caminhos(
        *(_texto(caminhos_brutos, chave, "caminhos")
          for chave in ("planejamento", "status", "backlog", "decisoes", "rascunho", "atritos", "estudos", "adrs",
                        "pesquisas")),
        _textos(caminhos_brutos, "fontes", "caminhos"),
        # Os opcionais por nome: um pode faltar sem o outro.
        **{chave: _texto(caminhos_brutos, chave, "caminhos")
           for chave in ("leitor_frio", "legenda") if chave in caminhos_brutos},
    )

    moldes_brutos = _secao(dados, "moldes")
    moldes = Moldes(
        _texto(moldes_brutos, "pasta", "moldes"),
        _pares(moldes_brutos, "trocas_de_nome", "moldes"),
        _textos(moldes_brutos, "placeholders", "moldes"),
        _pares(moldes_brutos, "partes_variaveis", "moldes"),
        _mapa(moldes_brutos),
        _pares(moldes_brutos, "liberados", "moldes") if "liberados" in moldes_brutos else {},
    )
    for chave, valor in caminhos_brutos.items():  # na ordem do arquivo; chave que o núcleo não lê fica de fora
        if chave in Caminhos.__dataclass_fields__:
            for caminho in (valor if isinstance(valor, list) else [valor]):
                _normalizado(caminho, f"caminhos.{chave}")
    if caminhos.legenda == caminhos.planejamento or caminhos.legenda.startswith(caminhos.planejamento + "/"):
        raise PerfilInvalido(f"caminhos.legenda dentro da pasta do planejamento: {caminhos.legenda}")
    _normalizado(moldes.pasta, "moldes.pasta")
    for caminho, hash_ in moldes.liberados.items():
        _normalizado(caminho, "moldes.liberados")
        if caminho.startswith(moldes.pasta.rstrip("/") + "/"):
            raise PerfilInvalido(
                f"caminho de moldes.liberados a partir da raiz; escreva-o relativo a {moldes.pasta}: {caminho}"
            )
        if not _RE_HASH_DO_MOLDE.fullmatch(hash_):
            raise PerfilInvalido(f"hash fora do formato sha256:<12 hexadecimais> em moldes.liberados: {hash_}")
    for padrao in moldes.placeholders:
        _compila(padrao, "moldes.placeholders", busca=True)
    for chave, valor in moldes.partes_variaveis.items():
        _compila(chave, "moldes.partes_variaveis", busca=True)
        _compila(valor, "moldes.partes_variaveis")

    fases = _fases(dados)

    ids_brutos = _secao(dados, "ids")
    ids = Ids(
        _textos(ids_brutos, "prefixos", "ids", vazia=False),
        _textos(ids_brutos, "padroes", "ids", vazia=False),
        _texto(ids_brutos, "prefixo_pendencia", "ids"),
        *([_texto(ids_brutos, "prefixo_relato", "ids")] if "prefixo_relato" in ids_brutos else []),
    )
    if ids.prefixo_relato in ids.prefixos or ids.prefixo_relato == ids.prefixo_pendencia:
        raise PerfilInvalido(
            f"ids.prefixo_relato repete um prefixo de ids.prefixos ou o da pendência: {ids.prefixo_relato}"
        )
    if "com_buracos" in ids_brutos:
        com_buracos = _textos(ids_brutos, "com_buracos", "ids")
        fora = next((prefixo for prefixo in com_buracos if prefixo not in ids.prefixos), None)
        if fora is not None:
            raise PerfilInvalido(f"ids.com_buracos com prefixo fora de ids.prefixos: {fora}")
        ids = dataclasses.replace(ids, com_buracos=com_buracos)
    if "formas" in ids_brutos:
        formas = _textos(ids_brutos, "formas", "ids")
        if len(formas) != len(ids.prefixos):
            raise PerfilInvalido(f"ids.formas: {len(formas)} formas para {len(ids.prefixos)} prefixos")
        for forma, prefixo in zip(formas, ids.prefixos):
            if not _comeca_pelo_prefixo(forma, prefixo):
                raise PerfilInvalido(f"ids.formas: {forma} não começa por {prefixo}")
        ids = dataclasses.replace(ids, formas=formas)
    for padrao in ids.padroes:
        _compila(padrao, "ids.padroes")
        if not any(_comeca_pelo_prefixo(padrao, prefixo) for prefixo in ids.prefixos):
            raise PerfilInvalido(f"padrão de ID fora dos prefixos: {padrao}")

    texto_bruto = _secao(dados, "texto")
    texto = Texto(
        _textos(texto_bruto, "adjetivos_vagos", "texto"),
        _textos(texto_bruto, "duvidas_de_escopo", "texto"),
        _textos(texto_bruto, "sistemas_do_cliente", "texto"),
        _textos(texto_bruto, "nomes_duplos", "texto"),
        _texto(texto_bruto, "glossario", "texto"),
    )
    for padrao in texto.adjetivos_vagos:
        _compila(padrao, "texto.adjetivos_vagos", busca=True)

    der = _der(dados, fases)
    campos = _campos(dados, ids)
    colunas = _colunas(dados)
    pendencia_na_linha = _pendencia_na_linha(dados)
    perguntas = (_textos(_secao(dados, "leitor_frio"), "perguntas", "leitor_frio", vazia=False)
                 if "leitor_frio" in dados else ())
    passagem = _passagem(dados)
    ramo_do_ci = _ramo_do_ci(dados)
    return Perfil(
        nome, caminhos, moldes, fases, ids, texto,
        _gates(dados, fases, ids, caminhos.leitor_frio, perguntas, passagem is not None), der, comum_.proibidos,
        campos=campos, colunas=colunas, pendencia_na_linha=pendencia_na_linha,
        perguntas_leitor_frio=perguntas, passagem=passagem,
        segredos=comum_.segredos, segredos_isentos=comum_.segredos_isentos,
        ramo_do_ci=ramo_do_ci,
    )


def ler(caminho: Path) -> Perfil:
    """Lê e valida o perfil em `caminho`. Arquivo ausente, ilegível ou fora do formato vira PerfilInvalido."""
    return validar(perfil_comum.ler_dados(caminho))


def carregar(raiz: Path) -> Perfil:
    """Perfil do projeto: `<raiz>/.claude/perfil.toml`, validado."""
    return ler(raiz / CAMINHO_PERFIL)
