"""Perfil de desenvolvimento: a tabela `[desenvolvimento]` do repositório de código, sobre a parte comum do perfil.

Toda subtabela recusa chave desconhecida, e a chave obrigatória ausente dá `falta a chave desenvolvimento.<caminho>`.
Os marcadores `{<nome>}` dos aliases, do `instalar` e do `desmontar` são conferidos aqui; o `${...}` é do shell e
fica como está. A tabela opcional `[desenvolvimento.ci]` traz o `instalar`, a lista de comandos que instalam a stack no
CI; ausente ou vazia, dá `ci_instalar` vazio.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import comum
import papeis
import perfil_comum
import regras
from perfil_comum import (
    PerfilComum, PerfilInvalido, chaves, normalizado, padroes_de_caminho, secao, sem_desconhecida, subtabela, texto,
    textos,
)

MOMENTOS = ("stop", "finalizar")
PREFIXOS_DO_PLANEJAMENTO = ("FICHA", "PEND")
# Um marcador `{<nome>}`, fora do `${...}` do shell.
RE_MARCADOR = re.compile(r"(?<!\$)\{([a-z][a-z0-9.-]*)\}")
PORTA_MAXIMA = 65535
# O fim do nome do `env_modelo`; o arquivo que ele gera tem o mesmo nome sem ele.
SUFIXO_DO_MODELO = ".example"
# Os seis status da ficha no Linear, com o nome que o Linear dá a cada um em todo time (spec 6d-repositorio, §9.1).
CHAVES_DO_STATUS = ("espera", "pronta", "andamento", "revisao", "fechada", "saiu")
STATUS_PADRAO = (("espera", "Backlog"), ("pronta", "Todo"), ("andamento", "In Progress"), ("revisao", "In Review"),
                 ("fechada", "Done"), ("saiu", "Canceled"))

_TABELAS = ("projeto", "guarda", "desenvolvimento")
_CHAVES = ("ramo_principal", "caminhos", "passagem", "dono", "verificacoes", "modelos", "revisao", "registro", "ci", "lane",
           "guarda", "aceitacao", "fichas", "codex", "linear")
_CHAVES_DA_VERIFICACAO = ("nome", "comando", "caminhos", "momentos", "requer", "tempo_limite")
_CHAVES_DA_LANE = ("limite", "pasta", "env_modelo", "env_copiados", "instalar", "desmontar", "portas")
_CHAVES_DO_LINEAR = ("time", "projeto", "rotulo", "rotulo_bloqueio", "status")
# Os marcadores do `instalar` e do `desmontar`, além do `porta.<nome>`.
_MARCADORES_DA_LANE = ("n", "id", "slug", "pasta")
_RE_NOME = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
_RE_ALIAS = re.compile(r"[a-z][a-z0-9-]*")
_RE_PREFIXO = re.compile(r"[A-Z]{2,}")
_RE_REPOSITORIO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
_RE_ESQUEMA = re.compile(r"[a-z][a-z0-9+.-]*://")
_RE_GITHUB = re.compile(r"[A-Za-z0-9-]+")
_RE_URL = re.compile(r"https?://\S+")


@dataclass(frozen=True)
class CaminhosDoCodigo:
    blocos: str
    backlog: str
    passagem: str
    legenda: str


@dataclass(frozen=True)
class OrigemDaPassagem:
    repositorio: str
    manifesto: str = "passagem/manifesto.json"
    legenda: str = ""


@dataclass(frozen=True)
class Dono:
    nome: str
    github: str


@dataclass(frozen=True)
class Verificacao:
    nome: str
    comando: str
    caminhos: tuple[str, ...]
    momentos: tuple[str, ...]
    requer: tuple[str, ...] = ()
    tempo_limite: int = 600


@dataclass(frozen=True)
class Modelo:
    model: str
    effort: str


@dataclass(frozen=True)
class Revisao:
    sensiveis: tuple[str, ...] = ()
    itens: tuple[str, ...] = ()


@dataclass(frozen=True)
class Registro:
    severidade_padrao: str = "major"


@dataclass(frozen=True)
class Porta:
    base: int
    passo: int


@dataclass(frozen=True)
class Lane:
    limite: int
    portas: tuple[tuple[str, Porta], ...]
    pasta: str = ".claude/worktrees"
    env_modelo: str = ""
    env_copiados: tuple[str, ...] = ()
    instalar: tuple[str, ...] = ()
    desmontar: tuple[str, ...] = ()

    def porta(self, nome: str, numero: int) -> int:
        """A porta `nome` na lane `numero`: `base + numero × passo`; o número 0 é a árvore principal."""
        porta = dict(self.portas)[nome]
        return porta.base + numero * porta.passo

    @property
    def arquivos_de_env(self) -> tuple[str, ...]:
        """Os arquivos de env da lane, na ordem em que um deles define a variável: cada `env_copiados`, na ordem, e
        depois o `env_modelo` sem o sufixo, o `.env` gerado, quando há `env_modelo`."""
        gerado = (self.env_modelo[:-len(SUFIXO_DO_MODELO)],) if self.env_modelo else ()
        return self.env_copiados + gerado


@dataclass(frozen=True)
class Aceitacao:
    tempo_limite: int = 30
    aliases: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Linear:
    time: str
    projeto: str
    rotulo: str = "ficha"
    rotulo_bloqueio: str = "bloqueado"
    status: tuple[tuple[str, str], ...] = STATUS_PADRAO

    def nome_do_status(self, chave: str) -> str:
        """O nome, no Linear, do status `chave` (uma de `CHAVES_DO_STATUS`)."""
        return dict(self.status)[chave]


@dataclass(frozen=True)
class PerfilDesenvolvimento:
    comum: PerfilComum
    ramo_principal: str
    caminhos: CaminhosDoCodigo
    passagem: OrigemDaPassagem
    dono: Dono
    verificacoes: tuple[Verificacao, ...]
    lane: Lane
    fora_da_lane: tuple[str, ...]
    prefixo: str
    modelos: tuple[tuple[str, Modelo], ...] = ()
    revisao: Revisao = Revisao()
    aceitacao: Aceitacao = Aceitacao()
    codex: bool = False
    registro: Registro = Registro()
    linear: Linear | None = None
    ci_instalar: tuple[str, ...] = ()

    @property
    def nome(self) -> str:
        return self.comum.nome


def marcadores(texto_: str) -> list[str]:
    """Os nomes dos marcadores `{<nome>}` do texto, na ordem, sem os de `${...}`."""
    return RE_MARCADOR.findall(texto_)


def _inteiro(tabela: dict, chave: str, onde: str, minimo: int, maximo: int, padrao: int | None = None) -> int:
    """O inteiro de `minimo` a `maximo`; o booleano, que o Python conta como inteiro, é recusado. Ausente, dá o
    `padrao`, ou recusa sem ele."""
    if chave not in tabela:
        if padrao is None:
            raise PerfilInvalido(f"falta a chave {onde}.{chave}")
        return padrao
    valor = tabela[chave]
    if not isinstance(valor, int) or isinstance(valor, bool) or not minimo <= valor <= maximo:
        raise PerfilInvalido(f"{onde}.{chave} deve ser um inteiro de {minimo} a {maximo}")
    return valor


def _caminhos_normalizados(tabela: dict, chave: str, onde: str) -> tuple[str, ...]:
    """A lista opcional de caminhos relativos à raiz, cada um normalizado; ausente, vazia."""
    if chave not in tabela:
        return ()
    caminhos = textos(tabela, chave, onde)
    for caminho in caminhos:
        normalizado(caminho, f"{onde}.{chave}")
    return caminhos


def _sobrepoem(a: str, b: str) -> bool:
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def _ramo_principal(desenvolvimento: dict) -> str:
    ramo = texto(desenvolvimento, "ramo_principal", "desenvolvimento")
    if re.search(r"\s", ramo) or ".." in ramo or ramo.startswith("-"):
        raise PerfilInvalido(f"desenvolvimento.ramo_principal fora do formato de branch: {ramo}")
    return ramo


def _caminhos(desenvolvimento: dict) -> CaminhosDoCodigo:
    onde = "desenvolvimento.caminhos"
    tabela = subtabela(desenvolvimento, "caminhos", "desenvolvimento")
    nomes = ("blocos", "backlog", "passagem", "legenda")
    chaves(tabela, nomes, onde)
    valores = [texto(tabela, chave, onde) for chave in nomes]
    for chave, valor in zip(nomes, valores):
        normalizado(valor, f"{onde}.{chave}")
    for i, a in enumerate(valores):
        for b in valores[i + 1:]:
            if _sobrepoem(a, b):
                raise PerfilInvalido(f"{onde}: {a} e {b} se sobrepõem")
    return CaminhosDoCodigo(*valores)


def _passagem(desenvolvimento: dict) -> OrigemDaPassagem:
    onde = "desenvolvimento.passagem"
    tabela = subtabela(desenvolvimento, "passagem", "desenvolvimento")
    sem_desconhecida(tabela, ("repositorio", "manifesto", "legenda"), onde)
    repositorio = texto(tabela, "repositorio", onde)
    if not (_RE_REPOSITORIO.fullmatch(repositorio) or _RE_ESQUEMA.match(repositorio) or repositorio.startswith("/")):
        raise PerfilInvalido(f"{onde}.repositorio fora do formato org/nome, URL ou caminho absoluto: {repositorio}")
    campos = {}
    for chave in ("manifesto", "legenda"):
        if chave in tabela:
            campos[chave] = texto(tabela, chave, onde)
            normalizado(campos[chave], f"{onde}.{chave}")
    return OrigemDaPassagem(repositorio, **campos)


def _dono(desenvolvimento: dict) -> Dono:
    onde = "desenvolvimento.dono"
    tabela = subtabela(desenvolvimento, "dono", "desenvolvimento")
    chaves(tabela, ("nome", "github"), onde)
    nome = texto(tabela, "nome", onde)
    github = texto(tabela, "github", onde)
    if not _RE_GITHUB.fullmatch(github):
        raise PerfilInvalido(f"{onde}.github fora do formato de usuário do GitHub: {github}")
    return Dono(nome, github)


def _verificacao(bruta: dict, onde: str) -> Verificacao:
    sem_desconhecida(bruta, _CHAVES_DA_VERIFICACAO, onde)
    nome = texto(bruta, "nome", onde)
    if not _RE_NOME.fullmatch(nome):
        raise PerfilInvalido(f"{onde}.nome fora do formato {_RE_NOME.pattern}: {nome}")
    comando = texto(bruta, "comando", onde)
    if "caminhos" not in bruta:
        raise PerfilInvalido(f"falta a chave {onde}.caminhos")
    caminhos = padroes_de_caminho(bruta, "caminhos", onde)
    momentos = textos(bruta, "momentos", onde, vazia=False)
    fora = next((momento for momento in momentos if momento not in MOMENTOS), None)
    if fora is not None:
        raise PerfilInvalido(f"{onde}.momentos: {fora}; use {comum.juntar(MOMENTOS, 'ou')}")
    requer = _caminhos_normalizados(bruta, "requer", onde)
    tempo_limite = _inteiro(bruta, "tempo_limite", onde, 1, 3600, 600)
    return Verificacao(nome, comando, caminhos, momentos, requer, tempo_limite)


def _verificacoes(desenvolvimento: dict) -> tuple[Verificacao, ...]:
    onde = "desenvolvimento.verificacoes"
    if "verificacoes" not in desenvolvimento:
        raise PerfilInvalido(f"falta a chave {onde}")
    brutas = desenvolvimento["verificacoes"]
    if not isinstance(brutas, list) or not all(isinstance(bruta, dict) for bruta in brutas):
        raise PerfilInvalido(f"{onde} deve ser uma lista de tabelas")
    if not brutas:
        raise PerfilInvalido(f"{onde} não pode ser uma lista vazia")
    verificacoes = []
    vistos: set[str] = set()
    for numero, bruta in enumerate(brutas, start=1):
        verificacao = _verificacao(bruta, f"{onde}.{numero}")
        if verificacao.nome in vistos:
            raise PerfilInvalido(f"{onde} com nome repetido: {verificacao.nome}")
        vistos.add(verificacao.nome)
        verificacoes.append(verificacao)
    return tuple(verificacoes)


def _modelos(desenvolvimento: dict) -> tuple[tuple[str, Modelo], ...]:
    onde = "desenvolvimento.modelos"
    tabela = subtabela(desenvolvimento, "modelos", "desenvolvimento", obrigatoria=False) or {}
    modelos = []
    for nome in tabela:
        if nome in papeis.SKILLS_DO_CICLO:
            raise PerfilInvalido(f"{onde}.{nome} é uma skill; a troca vale só para agentes")
        if nome not in papeis.NOMES:
            raise PerfilInvalido(f"{onde}.{nome} não é um agente do harness")
        bruta = subtabela(tabela, nome, onde)
        chaves(bruta, ("model", "effort"), f"{onde}.{nome}")
        model = texto(bruta, "model", f"{onde}.{nome}")
        effort = texto(bruta, "effort", f"{onde}.{nome}")
        if model not in papeis.MODELOS and not model.startswith(papeis.PREFIXO_DO_ID):
            raise PerfilInvalido(
                f"{onde}.{nome}.model {model} não é {', '.join(papeis.MODELOS)} nem um ID que começa por "
                f"{papeis.PREFIXO_DO_ID}"
            )
        if effort not in papeis.ESFORCOS:
            raise PerfilInvalido(
                f"{onde}.{nome}.effort {effort} fora de {comum.juntar(papeis.ESFORCOS)}"
            )
        modelos.append((nome, Modelo(model, effort)))
    return tuple(modelos)


def _revisao(desenvolvimento: dict) -> Revisao:
    onde = "desenvolvimento.revisao"
    tabela = subtabela(desenvolvimento, "revisao", "desenvolvimento", obrigatoria=False)
    if tabela is None:
        return Revisao()
    sem_desconhecida(tabela, ("sensiveis", "itens"), onde)
    itens = textos(tabela, "itens", onde) if "itens" in tabela else ()
    return Revisao(padroes_de_caminho(tabela, "sensiveis", onde), itens)


def _registro(desenvolvimento: dict) -> Registro:
    onde = "desenvolvimento.registro"
    tabela = subtabela(desenvolvimento, "registro", "desenvolvimento", obrigatoria=False)
    if tabela is None:
        return Registro()
    sem_desconhecida(tabela, ("severidade_padrao",), onde)
    if "severidade_padrao" not in tabela:
        return Registro()
    severidade = texto(tabela, "severidade_padrao", onde)
    if severidade not in regras.SEVERIDADES:
        raise PerfilInvalido(
            f"{onde}.severidade_padrao {severidade} fora da escala {comum.juntar(regras.SEVERIDADES)}"
        )
    return Registro(severidade)


def _conferir_marcadores(valores: tuple[str, ...], onde: str, portas: tuple[str, ...],
                         outros: tuple[str, ...]) -> None:
    """Recusa o marcador que não é `porta.<nome>` nem um dos `outros`, e a porta fora de `portas`."""
    for valor in valores:
        for marcador in marcadores(valor):
            if marcador.startswith("porta.") and len(marcador) > len("porta."):
                nome = marcador[len("porta."):]
                if nome not in portas:
                    raise PerfilInvalido(f"{onde} cita a porta {nome}, que não está em lane.portas")
            elif marcador not in outros:
                raise PerfilInvalido(f"{onde} cita {{{marcador}}}, que não existe")


def _portas(lane: dict, limite: int) -> tuple[tuple[str, Porta], ...]:
    """As portas na ordem do arquivo; cada nome, da árvore principal (0) à lane `limite`, não repete a porta de outro
    nem passa de 65535."""
    onde = "desenvolvimento.lane.portas"
    tabela = subtabela(lane, "portas", "desenvolvimento.lane")
    portas = []
    for nome in tabela:
        bruta = subtabela(tabela, nome, onde)
        chaves(bruta, ("base", "passo"), f"{onde}.{nome}")
        for chave in ("base", "passo"):
            valor = bruta[chave]
            if not isinstance(valor, int) or isinstance(valor, bool) or valor < 1:
                raise PerfilInvalido(f"{onde}.{nome}.{chave} deve ser um inteiro positivo")
        portas.append((nome, Porta(bruta["base"], bruta["passo"])))
    vistas: dict[int, str] = {}
    for nome, porta in portas:
        for numero in range(limite + 1):
            onde_esta = f"{nome} na árvore principal" if numero == 0 else f"{nome} na lane {numero}"
            valor = porta.base + numero * porta.passo
            if valor > PORTA_MAXIMA:
                raise PerfilInvalido(f"{onde}: {onde_esta} dá a porta {valor}, acima de {PORTA_MAXIMA}")
            if valor in vistas:
                raise PerfilInvalido(f"{onde}: {vistas[valor]} e {onde_esta} dão a porta {valor}")
            vistas[valor] = onde_esta
    return tuple(portas)


def _lane(desenvolvimento: dict) -> Lane:
    onde = "desenvolvimento.lane"
    tabela = subtabela(desenvolvimento, "lane", "desenvolvimento")
    sem_desconhecida(tabela, _CHAVES_DA_LANE, onde)
    limite = _inteiro(tabela, "limite", onde, 1, 9)
    pasta = Lane.pasta
    if "pasta" in tabela:
        pasta = texto(tabela, "pasta", onde)
        normalizado(pasta, f"{onde}.pasta")
    env_modelo = ""
    if "env_modelo" in tabela:
        env_modelo = texto(tabela, "env_modelo", onde)
        normalizado(env_modelo, f"{onde}.env_modelo")
        if not env_modelo.endswith(SUFIXO_DO_MODELO):
            raise PerfilInvalido(f"{onde}.env_modelo deve terminar em .example: {env_modelo}")
    env_copiados = _caminhos_normalizados(tabela, "env_copiados", onde)
    portas = _portas(tabela, limite)
    nomes = tuple(nome for nome, _ in portas)
    comandos = {}
    for chave in ("instalar", "desmontar"):
        comandos[chave] = textos(tabela, chave, onde) if chave in tabela else ()
        _conferir_marcadores(comandos[chave], f"{onde}.{chave}", nomes, _MARCADORES_DA_LANE)
    return Lane(limite, portas, pasta, env_modelo, env_copiados, comandos["instalar"], comandos["desmontar"])


def _ci_instalar(desenvolvimento: dict) -> tuple[str, ...]:
    onde = "desenvolvimento.ci"
    tabela = subtabela(desenvolvimento, "ci", "desenvolvimento", obrigatoria=False)
    if tabela is None:
        return ()
    sem_desconhecida(tabela, ("instalar",), onde)
    return textos(tabela, "instalar", onde) if "instalar" in tabela else ()


def _fora_da_lane(desenvolvimento: dict) -> tuple[str, ...]:
    onde = "desenvolvimento.guarda"
    tabela = subtabela(desenvolvimento, "guarda", "desenvolvimento")
    sem_desconhecida(tabela, ("fora_da_lane",), onde)
    if "fora_da_lane" not in tabela:
        raise PerfilInvalido(f"falta a chave {onde}.fora_da_lane")
    return padroes_de_caminho(tabela, "fora_da_lane", onde)


def _aceitacao(desenvolvimento: dict, portas: tuple[str, ...]) -> Aceitacao:
    onde = "desenvolvimento.aceitacao"
    tabela = subtabela(desenvolvimento, "aceitacao", "desenvolvimento", obrigatoria=False)
    if tabela is None:
        return Aceitacao()
    sem_desconhecida(tabela, ("tempo_limite", "aliases"), onde)
    tempo_limite = _inteiro(tabela, "tempo_limite", onde, 1, 300, 30)
    brutos = subtabela(tabela, "aliases", onde, obrigatoria=False) or {}
    aliases = []
    for nome, url in brutos.items():
        if not _RE_ALIAS.fullmatch(nome):
            raise PerfilInvalido(f"{onde}.aliases: nome fora do formato {_RE_ALIAS.pattern}: {nome}")
        if not isinstance(url, str) or not _RE_URL.fullmatch(url) or url.endswith("/"):
            raise PerfilInvalido(f"{onde}.aliases.{nome} deve ser uma URL http:// ou https:// sem barra no fim: {url}")
        _conferir_marcadores((url,), f"{onde}.aliases.{nome}", portas, ())
        aliases.append((nome, url))
    return Aceitacao(tempo_limite, tuple(aliases))


def _prefixo(desenvolvimento: dict) -> str:
    onde = "desenvolvimento.fichas"
    tabela = subtabela(desenvolvimento, "fichas", "desenvolvimento")
    sem_desconhecida(tabela, ("prefixo",), onde)
    prefixo = texto(tabela, "prefixo", onde)
    if not _RE_PREFIXO.fullmatch(prefixo):
        raise PerfilInvalido(f"{onde}.prefixo fora do formato {_RE_PREFIXO.pattern}: {prefixo}")
    if prefixo in PREFIXOS_DO_PLANEJAMENTO:
        raise PerfilInvalido(f"{onde}.prefixo: {prefixo} é do planejamento")
    return prefixo


def _codex(desenvolvimento: dict) -> bool:
    onde = "desenvolvimento.codex"
    tabela = subtabela(desenvolvimento, "codex", "desenvolvimento", obrigatoria=False)
    if tabela is None:
        return False
    sem_desconhecida(tabela, ("ligado",), onde)
    ligado = tabela.get("ligado", False)
    if not isinstance(ligado, bool):
        raise PerfilInvalido(f"{onde}.ligado deve ser true ou false")
    return ligado


def _status_do_linear(tabela: dict, onde: str) -> tuple[tuple[str, str], ...]:
    """Os seis status na ordem de `CHAVES_DO_STATUS`, com o nome da tabela onde houver e o padrão onde não; dois
    status com o mesmo nome são recusados."""
    bruto = subtabela(tabela, "status", onde, obrigatoria=False)
    if bruto is None:
        return STATUS_PADRAO
    onde_status = f"{onde}.status"
    sem_desconhecida(bruto, CHAVES_DO_STATUS, onde_status)
    padrao = dict(STATUS_PADRAO)
    status = tuple((chave, texto(bruto, chave, onde_status) if chave in bruto else padrao[chave])
                   for chave in CHAVES_DO_STATUS)
    for i, (a, nome_a) in enumerate(status):
        for b, nome_b in status[i + 1:]:
            if nome_a == nome_b:
                raise PerfilInvalido(f"{onde_status}: {a} e {b} com o mesmo status {nome_a}")
    return status


def _linear(desenvolvimento: dict) -> Linear | None:
    onde = "desenvolvimento.linear"
    tabela = subtabela(desenvolvimento, "linear", "desenvolvimento", obrigatoria=False)
    if tabela is None:
        return None
    sem_desconhecida(tabela, _CHAVES_DO_LINEAR, onde)
    time = texto(tabela, "time", onde)
    projeto = texto(tabela, "projeto", onde)
    rotulo = texto(tabela, "rotulo", onde) if "rotulo" in tabela else Linear.rotulo
    rotulo_bloqueio = (texto(tabela, "rotulo_bloqueio", onde) if "rotulo_bloqueio" in tabela
                       else Linear.rotulo_bloqueio)
    if rotulo == rotulo_bloqueio:
        raise PerfilInvalido(f"{onde}: rotulo e rotulo_bloqueio iguais: {rotulo}")
    return Linear(time, projeto, rotulo, rotulo_bloqueio, _status_do_linear(tabela, onde))


def validar(dados: dict) -> PerfilDesenvolvimento:
    """Confere o perfil de desenvolvimento já lido do TOML. Lança PerfilInvalido no primeiro problema.

    A ordem: a parte comum, pelo `perfil_comum`; a trilha, que recusa o perfil de planejamento; a tabela de primeiro
    nível desconhecida; e o `[desenvolvimento]`, nas chaves da ordem do perfil de exemplo: ramo_principal, caminhos,
    passagem, dono, verificacoes, modelos, revisao, registro, ci, lane, guarda, aceitacao, fichas, codex e linear.
    """
    comum_ = perfil_comum.validar(dados)
    if comum_.harness != perfil_comum.DESENVOLVIMENTO:
        raise PerfilInvalido(
            "perfil de planejamento ([projeto] harness); os comandos do desenvolvimento não valem aqui"
        )
    outra = next((tabela for tabela in dados if tabela not in _TABELAS), None)
    if outra is not None:
        raise PerfilInvalido(f"perfil de desenvolvimento com a tabela [{outra}]")
    desenvolvimento = secao(dados, "desenvolvimento")
    sem_desconhecida(desenvolvimento, _CHAVES, "desenvolvimento")
    ramo_principal = _ramo_principal(desenvolvimento)
    caminhos = _caminhos(desenvolvimento)
    passagem = _passagem(desenvolvimento)
    dono = _dono(desenvolvimento)
    verificacoes = _verificacoes(desenvolvimento)
    modelos = _modelos(desenvolvimento)
    revisao = _revisao(desenvolvimento)
    registro = _registro(desenvolvimento)
    lane = _lane(desenvolvimento)
    fora_da_lane = _fora_da_lane(desenvolvimento)
    aceitacao = _aceitacao(desenvolvimento, tuple(nome for nome, _ in lane.portas))
    prefixo = _prefixo(desenvolvimento)
    return PerfilDesenvolvimento(
        comum_, ramo_principal, caminhos, passagem, dono, verificacoes, lane, fora_da_lane, prefixo,
        modelos=modelos, revisao=revisao, aceitacao=aceitacao, codex=_codex(desenvolvimento),
        registro=registro, linear=_linear(desenvolvimento), ci_instalar=_ci_instalar(desenvolvimento),
    )


def carregar(raiz: Path) -> PerfilDesenvolvimento:
    """O perfil de desenvolvimento em `<raiz>/.claude/perfil.toml`, validado."""
    return validar(perfil_comum.ler_dados(raiz / comum.CAMINHO_PERFIL))


def do_texto(conteudo: str) -> PerfilDesenvolvimento:
    """O perfil de desenvolvimento do texto de um `.claude/perfil.toml`, validado; o TOML malformado cita o caminho
    do perfil."""
    return validar(perfil_comum.dados_do_texto(conteudo, comum.CAMINHO_PERFIL))
