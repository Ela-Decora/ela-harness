"""O espelho só de ida das fichas no Linear, com a chave do ambiente (spec 6d-repositorio, §9).

Este módulo traz o cliente da API GraphQL e as operações que o espelho usa. A chave pessoal vem do `LINEAR_API_KEY` do
ambiente de quem roda o comando, nunca do repositório, e vai no cabeçalho `Authorization`, sem `Bearer`. Só a biblioteca
padrão (`urllib` e `json`). O endereço da API é uma constante, lida a cada chamada, para que os testes a troquem por um
servidor local. Toda operação tem nome e passa todo valor por variável, e toda conexão aninhada leva um `first:`
explícito, porque a API recusa a consulta cuja complexidade passa de 10.000.

Depois delas, sem rede, fica a issue que cada ficha deve ter (§9.2 a §9.4): o status pela situação e pelo bloco, o
prazo do marco, a descrição e a comparação dela com a que o Linear devolve, que o Linear re-renderiza. O `espelhar`
(§9.6) compara essas issues com as do projeto e grava a diferença. No fim, o `avisar` (§9.5) manda ao Linear a transição
que um comando de bloco, de lane ou de retorno acabou de gravar, e nunca lança.
"""
from __future__ import annotations

import contextlib
import dataclasses
import datetime
import http.client
import json
import os
import re
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import bloco
import campos
import comum
import fichas
import perfil_desenvolvimento

AJUDA = """\
`harness.py linear espelhar [--seco]` refaz, a partir do repositório, o espelho só de ida das fichas no Linear: uma
issue por ficha da passagem (`FICHA-NN`) e do backlog do código, no projeto do `[desenvolvimento.linear]` do perfil,
sem duplicar nada. A ficha muda pelo repositório, e o que alguém muda à mão na issue o espelho refaz. Rode-o depois do
merge do PR da passagem, que a última linha do `importar` lembra, e sempre que o aviso de uma transição falhou.

A chave pessoal vem do `LINEAR_API_KEY` do ambiente de quem roda o comando, nunca do repositório. O `projeto` e os dois
rótulos do perfil precisam existir no time, e o comando não os cria. A issue de uma ficha é achada pelo ID no começo do
título ou na primeira linha da descrição, entre as issues do projeto com o `rotulo`.

A ordem, com tudo lido e conferido antes da primeira gravação:

1. lê o time, o projeto, os rótulos, os status e as milestones; as issues do projeto com o rótulo, de página em página;
   e o quadro das fichas do repositório;
2. recusa o ID com duas issues: `duas issues para <ID> no Linear: <a> e <b>; apague uma`, com os identificadores do
   Linear;
3. cria as milestones que faltam, com o prazo do marco quando ele é uma data `AAAA-MM-DD`; a data de uma milestone que
   já existe não muda;
4. cria cada issue que falta e acerta as outras: o título `<ID>: <slug>`, a descrição, com a primeira linha
   `Espelho de <ID> (<caminho>); muda pelo repositório, não aqui.` e depois o texto da ficha, os rótulos, a milestone,
   o status e o responsável;
5. cria as relações `blocked by` do Depende, depois de todas as issues existirem, e apaga as que saíram do Depende; a
   relação com a ficha citada que ficou `fora da forma`, e já tem issue, fica; a PEND do Depende fica só na descrição;
6. manda para o status `saiu` a issue de uma ficha da passagem que a cópia não tem mais.

O que o espelho faz em cada campo:

- **Status:** só avança, na ordem `espera`, `pronta`, `andamento`, `revisao`, `fechada`, e nunca recua: a ficha que ele
  vê `pronta` e o Linear mostra `andamento` pode estar numa lane de outra máquina, e o recuo vem só do aviso da
  transição que o causa. Um status do Linear que não é um desses vale como abaixo de `espera`. O `saiu` vale sempre,
  menos para a issue que já saiu. No avanço para `andamento`, `revisao` ou `fechada`, o comentário é
  `estado acertado pelo espelho: <estado> (<atualizado_em>)`, com o estado e a hora do bloco, porque o aviso daquela
  transição se perdeu; de `espera` a `pronta` não há comentário.
- **Rótulos:** põe o `rotulo_bloqueio` enquanto o bloco está em `blocked`, com o comentário `bloqueado: <motivo>`, e o
  tira depois; um rótulo posto à mão no Linear fica. Com o bloco em `blocked`, o status é o do `estado_anterior`.
- **Descrição:** a descrição do repositório substitui a do Linear só quando as duas diferem depois de apagar o que o
  Linear re-renderiza (o `* ` do item, a linha em branco depois do título, o `<>` e o percent-encoding do alvo do link e
  a quebra do fim). O comentário é `mudou na passagem/v<N>: <partes>`, ou `mudou no backlog do código: <partes>`, com os
  campos da ficha cujo texto mudou, na ordem do molde, e sem a parte quando só o texto de fora dos campos mudou.
- **Milestone:** a do `Marco` da ficha, achada pelo nome. A ficha que perde o `Marco` mantém a milestone que a issue
  tem: o espelho não tira milestone, como não muda a data de uma que já existe.
- **Responsável:** só preenche o vazio, com o usuário do e-mail do `git config user.email` da raiz, e só na ficha cuja
  lane está nesta máquina; sem usuário com esse e-mail, a issue fica sem responsável.
- **A ficha que saiu:** a issue com o `rotulo` e um ID `FICHA-NN` que a cópia da passagem não tem vai a `saiu`, com o
  comentário `saiu da passagem/v<N>`. A issue de uma ficha do código sem arquivo dá a linha
  `<ID>: no Linear e fora do repositório; nada muda`.

A saída tem uma linha por issue que mudou, `<ID>: <partes>`, com as partes separadas por `; ` e nesta ordem:
`criada (<status>[, <milestone>])`, `título`, `descrição`, `rótulo <nome> +`, `rótulo <nome> -`, `milestone <nome>`,
`status <de> → <para>`, `responsável <e-mail>`, `blocked by +<ID>` e `blocked by -<ID>`. Os status saem com o nome do
Linear, e a ficha que saiu traz `status <de> → <para> (saiu da passagem/v<N>)`. A milestone criada dá a linha
`milestone <nome>: criada`; a ficha que não vai ao Linear (`fora da forma`, ou só numa lane) dá
`<ID>: não espelha (<situação>)`. O resumo é `linear: <c> criadas, <a> acertadas, <s> sem mudança`, e as linhas
`não espelha` e `no Linear e fora do repositório` ficam fora da conta.

- **`--seco`:** lê o Linear e o repositório e imprime as mesmas linhas e o mesmo resumo, sem gravar nada.
- **Recusas, com saída 1:** `sem [desenvolvimento.linear] no perfil`, olhada antes da chave;
  `sem LINEAR_API_KEY no ambiente`; `duas issues para <ID> no Linear: <a> e <b>; apague uma`; e `linear: <motivo>` para
  a chamada que não deu certo (a mensagem do Linear, `HTTP <código>`, `tempo esgotado`, `sem conexão (<motivo>)` ou
  `resposta ilegível`) e para o que o time não tem (`time <time> não existe no Linear`,
  `projeto <nome> não existe no time <time>`, `rótulo <nome> não existe no time <time>` e
  `status <nome> não existe no time <time>`). O redirecionamento que a API devolva não é seguido, para que a chave não
  vá a outro endereço, e dá `linear: HTTP <código>`.
- **A falha no meio da gravação:** a chamada que falha depois da primeira gravação que deu certo sai com 1 e mostra,
  antes do `linear: <motivo>` que fecha a saída, as linhas do que já gravou, no formato de sempre: as milestones
  criadas e, de cada ficha, o que se gravou nela, sem o resumo e sem as linhas que só aparecem na saída. A falha antes
  da primeira gravação (o contexto, as issues, o status que o time não tem) mostra só o `linear: <motivo>`, e a
  recusa das duas issues, só ela, sem o `linear: `. Rodar de novo faz o que faltou, sem duplicar issue, relação nem
  milestone, com uma exceção: se a gravação parar entre a de uma issue, criada ou acertada, e a do comentário dela,
  esse comentário se perde, porque a rodada seguinte já vê a issue sem mudança.

O aviso da transição (spec 6d-repositorio, §9.5) é de outro comando: com a `[desenvolvimento.linear]` no perfil, cada
comando que muda o estado de uma ficha com um commit (`lane abrir`, os `bloco` `planejado`, `executando`, `executado`,
`revisando`, `revisado`, `corrigir`, `finalizar`, `bloquear`, `desbloquear` e `replanejar`, o `lane conferir` que
trava um bloco, o `retorno abrir` de decisão e o `lane fechar`, com ou sem `--abandonar`) avisa o Linear depois de
imprimir as linhas dele. O aviso, com 10 s no total:

- põe a issue da ficha no status do estado novo, e este pode recuar (`bloco corrigir`, `bloco replanejar`,
  `lane fechar --abandonar`); põe ou tira o `rotulo_bloqueio`, e grava como responsável o usuário do e-mail do
  `git config user.email` da árvore, quando ele existe no Linear, senão o responsável não muda;
- cria a issue, pelo caminho do espelho, quando a ficha ainda não tem;
- grava o comentário `<ID> · <de> → <para> · <e-mail> · <atualizado_em> · <ramo>@<commit curto>`; o bloco em `blocked`
  acrescenta ` · motivo: <motivo>`, e o link do PR, quando há, vem por último, depois de ` · `; sem o e-mail, vale
  `sem e-mail`. No `lane fechar` o ramo e o commit são os da árvore principal e a hora é a do comando; o `--abandonar`
  diz `<estado> → pronta (lane abandonada)`; o `finalizar` que só retoma diz `closing → closing`, só quando traz o
  link do PR, e o `retorno abrir` de `fato` não avisa, porque o bloco segue.

O aviso nunca muda as linhas nem o código de saída do comando. Se não vai, uma linha a mais:
`linear: aviso não enviado (<motivo>); rode harness.py linear espelhar`, ou, sem a chave no ambiente,
`linear: sem LINEAR_API_KEY no ambiente; aviso não enviado`. Sem a `[desenvolvimento.linear]`, o comando não avisa e não
diz nada.
"""

ENDERECO = "https://api.linear.app/graphql"
TEMPO_LIMITE = 10
# O que a ficha ganha do espelho no começo do título (`<ID>:`) e na primeira linha da descrição (`Espelho de <ID> `); o
# ID é o mesmo que o `fichas` lê nos textos.
_RE_ID_NO_TITULO = re.compile(rf"({fichas.CORPO_DO_ID}):")
_RE_ID_NA_DESCRICAO = re.compile(rf"Espelho de ({fichas.CORPO_DO_ID}) ")


class FalhaDoLinear(Exception):
    """Uma chamada que não deu certo. A `mensagem` é uma de: `HTTP <código>`, a primeira mensagem do `errors` da
    resposta, `tempo esgotado`, `sem conexão (<motivo>)` ou `resposta ilegível`."""

    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


def chave_do_ambiente(ambiente: Mapping[str, str] = os.environ) -> str | None:
    """O `LINEAR_API_KEY` sem os espaços das pontas; sem ele, ou vazio, `None`."""
    return (ambiente.get("LINEAR_API_KEY") or "").strip() or None


def _primeira_mensagem(erros: object) -> str | None:
    """A mensagem do primeiro item de uma lista `errors` da resposta; sem uma legível, `None`."""
    if isinstance(erros, list) and erros and isinstance(erros[0], dict):
        mensagem = erros[0].get("message")
        if isinstance(mensagem, str) and mensagem.strip():
            return mensagem.strip()
    return None


def _motivo(erro: object) -> str:
    """O motivo de uma falha de rede, em poucas palavras: o texto do sistema, ou o da exceção, ou o nome dela."""
    return getattr(erro, "strerror", None) or str(erro) or type(erro).__name__


def _json(corpo: bytes) -> object:
    """O JSON do corpo; o que não é UTF-8 nem JSON dá `None`."""
    try:
        return json.loads(corpo.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None


class _SemRedirecionamento(urllib.request.HTTPRedirectHandler):
    """Não segue redirecionamento: o `urllib` copiaria o `Authorization` para o endereço novo, qualquer que fosse o
    servidor, e a chave só vai para o endereço da API. O 3xx vira `HTTPError`, e a falha, `HTTP <código>`."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Cliente:
    """Uma chave e os tempos de uma sequência de chamadas ao Linear.

    Cada chamada espera no máximo o `tempo_limite`, ou o que sobra do `prazo_total` contado da criação do cliente,
    o que for menor; sem sobra, a falha é `tempo esgotado`, sem nem tentar. O atributo `chamadas` conta as tentadas, sem
    essas.

    Uma chave com caractere que o cabeçalho não aceita (como uma quebra de linha) dá `sem conexão (chave com caractere
    inválido)`, sem o valor dela na mensagem nem na cadeia da exceção.
    """

    def __init__(self, chave: str, tempo_limite: float = TEMPO_LIMITE, prazo_total: float | None = None):
        self._chave = chave
        self.tempo_limite = tempo_limite
        self._fim = None if prazo_total is None else time.monotonic() + prazo_total
        self.chamadas = 0

    def _espera(self) -> float:
        """O tempo desta chamada; sem sobra no prazo total, `tempo esgotado`."""
        if self._fim is None:
            return self.tempo_limite
        sobra = self._fim - time.monotonic()
        if sobra <= 0:
            raise FalhaDoLinear("tempo esgotado")
        return min(self.tempo_limite, sobra)

    def consultar(self, operacao: str, documento: str, variaveis: dict) -> dict:
        """Um POST JSON com `query`, `operationName` e `variables`; devolve o `data` da resposta.

        Resposta com `errors`, mesmo num 400, dá a primeira mensagem dela; sem `errors` legível, um código que não é 2xx
        dá `HTTP <código>`, o redirecionamento inclusive: ele não é seguido, para que a chave não vá a outro endereço.
        """
        espera = self._espera()
        corpo = json.dumps({"query": documento, "operationName": operacao, "variables": variaveis}).encode("utf-8")
        pedido = urllib.request.Request(
            ENDERECO, data=corpo, method="POST",
            headers={"Content-Type": "application/json", "Authorization": self._chave},
        )
        self.chamadas += 1
        codigo = 200
        falha = ""
        try:
            # O abridor nasce a cada chamada, para ler o proxy do ambiente de agora.
            with urllib.request.build_opener(_SemRedirecionamento).open(pedido, timeout=espera) as resposta:
                texto = resposta.read()
        except urllib.error.HTTPError as erro:
            try:
                codigo, texto = erro.code, erro.read()
            except (OSError, http.client.HTTPException):
                codigo, texto = erro.code, b""
            finally:
                erro.close()
        except (socket.timeout, TimeoutError):
            falha = "tempo esgotado"
        except urllib.error.URLError as erro:
            if isinstance(erro.reason, (socket.timeout, TimeoutError)):
                falha = "tempo esgotado"
            else:
                falha = f"sem conexão ({_motivo(erro.reason)})"
        except (OSError, http.client.HTTPException) as erro:
            falha = f"sem conexão ({_motivo(erro)})"
        except ValueError:
            # O envio recusa o cabeçalho com quebra de linha, e a mensagem da exceção traz o valor, que é a chave.
            falha = "sem conexão (chave com caractere inválido)"
        if falha:
            # Fora do `except`, para que a exceção original, com a chave, não vá como contexto da falha.
            raise FalhaDoLinear(falha)
        resposta_json = _json(texto)
        mensagem = _primeira_mensagem(resposta_json.get("errors")) if isinstance(resposta_json, dict) else None
        if mensagem:
            raise FalhaDoLinear(mensagem)
        if not 200 <= codigo < 300:
            raise FalhaDoLinear(f"HTTP {codigo}")
        dados = resposta_json.get("data") if isinstance(resposta_json, dict) else None
        if not isinstance(dados, dict):
            raise FalhaDoLinear("resposta ilegível")
        return dados


@dataclass(frozen=True)
class Milestone:
    id: str
    nome: str
    data: str | None


@dataclass(frozen=True)
class ContextoDoLinear:
    """O time, o projeto, os dois rótulos e os estados do time, e as milestones do projeto, tudo pelo nome."""

    time_id: str
    projeto_id: str
    rotulos: dict[str, str]
    estados: dict[str, str]
    milestones: dict[str, Milestone]


@dataclass(frozen=True)
class IssueNoLinear:
    """Uma issue como o Linear a tem. O `responsavel` é o e-mail; o `bloqueada_por` vai do ID da ficha da issue que
    bloqueia ao id da relação; a `ficha` sai do começo do título ou da primeira linha da descrição."""

    id: str
    identificador: str
    ficha: str | None
    titulo: str
    descricao: str
    estado: str
    responsavel: str | None
    rotulos: frozenset[str]
    milestone: str | None
    bloqueada_por: dict[str, str]


# Os campos de cada time achado, repetidos nos dois apelidos do `Contexto`.
_CAMPOS_DO_TIME = """id key name
      states(first: 50) { nodes { id name } }
      labels(first: 10, filter: {name: {in: $rotulos}}) { nodes { id name } }
      projects(first: 1, filter: {name: {eq: $projeto}}) {
        nodes { id name projectMilestones(first: 50) { nodes { id name targetDate } } }
      }"""

# O time sai pela chave ou pelo nome: o filtro `key` não acha o time cujo nome está no perfil, e o `name` acha. Os dois
# apelidos vão numa chamada só, e vale o primeiro que vier com time.
CONTEXTO = """
query Contexto($chave: String!, $nome: String!, $projeto: String!, $rotulos: [String!]) {
  porChave: teams(first: 1, filter: {key: {eq: $chave}}) { nodes { @TIME@ } }
  porNome: teams(first: 1, filter: {name: {eq: $nome}}) { nodes { @TIME@ } }
}
""".replace("@TIME@", _CAMPOS_DO_TIME)

USUARIO = """
query Usuario($email: String!) {
  users(first: 5, filter: {email: {eq: $email}}) { nodes { id name email } }
}
"""

# O `inverseRelations` da issue bloqueada traz, com o tipo `blocks`, a issue que bloqueia. A API recusa a consulta cuja
# complexidade passa de 10.000, e a página de 50 issues multiplica o custo de cada uma por 50: o que segura a conta
# são os `first:` pequenos de `labels` e de `inverseRelations`, perto de 4.000 por página cheia (estimativa; o ensaio
# confere).
_CAMPOS_DA_ISSUE = """id identifier title description
      state { name }
      assignee { email }
      labels(first: 10) { nodes { name } }
      projectMilestone { name }
      inverseRelations(first: 25) { nodes { id type issue { title description } } }"""

ISSUES = """
query Issues($projeto: ID!, $rotulo: String!, $depois: String) {
  issues(first: 50, after: $depois,
         filter: {project: {id: {eq: $projeto}}, labels: {name: {eq: $rotulo}}}) {
    nodes { @ISSUE@ }
    pageInfo { hasNextPage endCursor }
  }
}
""".replace("@ISSUE@", _CAMPOS_DA_ISSUE)

# Pelo começo do título ou pelo da descrição, numa chamada só.
ISSUE_DA_FICHA = """
query IssueDaFicha($projeto: ID!, $rotulo: String!, $titulo: String!, $descricao: String!) {
  peloTitulo: issues(first: 10, filter: {project: {id: {eq: $projeto}}, labels: {name: {eq: $rotulo}},
                                         title: {startsWith: $titulo}}) { nodes { @ISSUE@ } }
  pelaDescricao: issues(first: 10, filter: {project: {id: {eq: $projeto}}, labels: {name: {eq: $rotulo}},
                                            description: {startsWith: $descricao}}) { nodes { @ISSUE@ } }
}
""".replace("@ISSUE@", _CAMPOS_DA_ISSUE)

CRIAR_MILESTONE = """
mutation CriarMilestone($projeto: String!, $nome: String!, $data: TimelessDate) {
  projectMilestoneCreate(input: {projectId: $projeto, name: $nome, targetDate: $data}) {
    success projectMilestone { id name targetDate }
  }
}
"""

CRIAR_ISSUE = """
mutation CriarIssue($input: IssueCreateInput!) {
  issueCreate(input: $input) { success issue { id } }
}
"""

ATUALIZAR_ISSUE = """
mutation AtualizarIssue($id: String!, $input: IssueUpdateInput!) {
  issueUpdate(id: $id, input: $input) { success }
}
"""

COMENTAR = """
mutation Comentar($issue: String!, $texto: String!) {
  commentCreate(input: {issueId: $issue, body: $texto}) { success }
}
"""

# "A está bloqueada por B" é a relação `blocks` com `issueId` B e `relatedIssueId` A.
RELACIONAR = """
mutation Relacionar($issue: String!, $relacionada: String!) {
  issueRelationCreate(input: {issueId: $issue, relatedIssueId: $relacionada, type: blocks}) {
    success issueRelation { id }
  }
}
"""

DESRELACIONAR = """
mutation Desrelacionar($id: String!) { issueRelationDelete(id: $id) { success } }
"""


@contextlib.contextmanager
def _forma_da_resposta():
    """Uma resposta sem a forma que o documento pede dá `resposta ilegível`."""
    try:
        yield
    except (KeyError, IndexError, TypeError, AttributeError):
        raise FalhaDoLinear("resposta ilegível") from None


def _nos(conexao: dict, nome: str) -> list[dict]:
    """Os `nodes` da conexão `nome` do objeto."""
    return conexao[nome]["nodes"]


def ler_contexto(cliente: Cliente, config: perfil_desenvolvimento.Linear) -> ContextoDoLinear:
    """O time, o projeto, os rótulos e os estados numa chamada `Contexto`.

    Recusa, por `FalhaDoLinear`: `time <time> não existe no Linear`, `projeto <nome> não existe no time <time>` e
    `rótulo <nome> não existe no time <time>`, para o `rotulo` e depois o `rotulo_bloqueio`.
    """
    dados = cliente.consultar("Contexto", CONTEXTO, {
        "chave": config.time, "nome": config.time, "projeto": config.projeto,
        "rotulos": [config.rotulo, config.rotulo_bloqueio],
    })
    with _forma_da_resposta():
        times = _nos(dados, "porChave") or _nos(dados, "porNome")
        if not times:
            raise FalhaDoLinear(f"time {config.time} não existe no Linear")
        time_ = times[0]
        projetos = _nos(time_, "projects")
        if not projetos:
            raise FalhaDoLinear(f"projeto {config.projeto} não existe no time {config.time}")
        rotulos = {no["name"]: no["id"] for no in _nos(time_, "labels")}
        for nome in (config.rotulo, config.rotulo_bloqueio):
            if nome not in rotulos:
                raise FalhaDoLinear(f"rótulo {nome} não existe no time {config.time}")
        estados = {no["name"]: no["id"] for no in _nos(time_, "states")}
        milestones = {
            no["name"]: Milestone(no["id"], no["name"], no.get("targetDate"))
            for no in _nos(projetos[0], "projectMilestones")
        }
        return ContextoDoLinear(time_["id"], projetos[0]["id"], rotulos, estados, milestones)


def _ficha_do_texto(titulo: str, descricao: str) -> str | None:
    """O ID da ficha no começo do título ou, sem ele, na primeira linha da descrição."""
    achado = _RE_ID_NO_TITULO.match(titulo) or _RE_ID_NA_DESCRICAO.match(descricao.split("\n", 1)[0])
    return achado.group(1) if achado else None


def _issue(no: dict) -> IssueNoLinear:
    """A issue de um nó da resposta; as relações que não são `blocks`, e as de issue sem ficha, ficam de fora."""
    titulo = no["title"]
    descricao = no.get("description") or ""
    bloqueada_por: dict[str, str] = {}
    for relacao in _nos(no, "inverseRelations"):
        if relacao["type"] != "blocks":
            continue
        ficha = _ficha_do_texto(relacao["issue"]["title"], relacao["issue"].get("description") or "")
        if ficha is not None:
            bloqueada_por[ficha] = relacao["id"]
    return IssueNoLinear(
        id=no["id"], identificador=no["identifier"], ficha=_ficha_do_texto(titulo, descricao), titulo=titulo,
        descricao=descricao, estado=no["state"]["name"],
        responsavel=(no.get("assignee") or {}).get("email"),
        rotulos=frozenset(rotulo["name"] for rotulo in _nos(no, "labels")),
        milestone=(no.get("projectMilestone") or {}).get("name"), bloqueada_por=bloqueada_por,
    )


def issues_do_projeto(cliente: Cliente, ctx: ContextoDoLinear, rotulo: str) -> list[IssueNoLinear]:
    """As issues do projeto com o rótulo, de página em página até o `pageInfo` dizer que acabou."""
    achadas: list[IssueNoLinear] = []
    depois = None
    while True:
        dados = cliente.consultar("Issues", ISSUES, {"projeto": ctx.projeto_id, "rotulo": rotulo, "depois": depois})
        with _forma_da_resposta():
            achadas += [_issue(no) for no in _nos(dados, "issues")]
            pagina = dados["issues"]["pageInfo"]
            if not pagina["hasNextPage"]:
                return achadas
            if not pagina["endCursor"] or pagina["endCursor"] == depois:
                raise FalhaDoLinear("resposta ilegível")  # a página seguinte sem cursor novo repetiria a mesma
            depois = pagina["endCursor"]


def issues_da_ficha(cliente: Cliente, ctx: ContextoDoLinear, rotulo: str, id_: str) -> list[IssueNoLinear]:
    """As issues do projeto com o rótulo cuja ficha é o `id_`, achadas pelo começo do título ou da descrição."""
    dados = cliente.consultar("IssueDaFicha", ISSUE_DA_FICHA, {
        "projeto": ctx.projeto_id, "rotulo": rotulo, "titulo": f"{id_}:", "descricao": f"Espelho de {id_} ",
    })
    with _forma_da_resposta():
        achadas: dict[str, IssueNoLinear] = {}
        for apelido in ("peloTitulo", "pelaDescricao"):
            for no in _nos(dados, apelido):
                issue = _issue(no)
                if issue.ficha == id_:
                    achadas.setdefault(issue.id, issue)
        return list(achadas.values())


def usuario(cliente: Cliente, email: str) -> str | None:
    """O id do usuário com o e-mail; sem ele, `None`."""
    dados = cliente.consultar("Usuario", USUARIO, {"email": email})
    with _forma_da_resposta():
        usuarios = _nos(dados, "users")
        return usuarios[0]["id"] if usuarios else None


def _sucesso(dados: dict, operacao: str) -> dict:
    """O resultado da mutação `operacao`, que deve vir com `success`."""
    with _forma_da_resposta():
        resultado = dados[operacao]
        if resultado["success"] is not True:
            raise FalhaDoLinear("resposta ilegível")
        return resultado


def criar_milestone(cliente: Cliente, ctx: ContextoDoLinear, nome: str, data: str | None) -> Milestone:
    """Cria a milestone no projeto; a `data`, `AAAA-MM-DD`, é opcional e, sem ela, não vai na chamada."""
    variaveis = {"projeto": ctx.projeto_id, "nome": nome}
    if data is not None:
        variaveis["data"] = data  # sem data, a variável fica de fora em vez de ir como `null`
    dados = cliente.consultar("CriarMilestone", CRIAR_MILESTONE, variaveis)
    with _forma_da_resposta():
        no = _sucesso(dados, "projectMilestoneCreate")["projectMilestone"]
        return Milestone(no["id"], no["name"], no.get("targetDate"))


def criar_issue(cliente: Cliente, ctx: ContextoDoLinear, campos: dict) -> str:
    """Cria a issue no time e no projeto do contexto e devolve o id. Os `campos` são os do `IssueCreateInput` do Linear
    (`title`, `description`, `stateId`, `labelIds`, `projectMilestoneId`, `assigneeId`); o `teamId` e o `projectId` vêm
    do contexto."""
    entrada = {"teamId": ctx.time_id, "projectId": ctx.projeto_id, **campos}
    dados = cliente.consultar("CriarIssue", CRIAR_ISSUE, {"input": entrada})
    with _forma_da_resposta():
        return _sucesso(dados, "issueCreate")["issue"]["id"]


def atualizar_issue(cliente: Cliente, issue_id: str, campos: dict) -> None:
    """Muda a issue. Os `campos` são os do `IssueUpdateInput` do Linear (`title`, `description`, `stateId`,
    `assigneeId`, `projectMilestoneId`, `addedLabelIds`, `removedLabelIds`)."""
    _sucesso(cliente.consultar("AtualizarIssue", ATUALIZAR_ISSUE, {"id": issue_id, "input": campos}), "issueUpdate")


def comentar(cliente: Cliente, issue_id: str, texto: str) -> None:
    """Grava o comentário na issue."""
    _sucesso(cliente.consultar("Comentar", COMENTAR, {"issue": issue_id, "texto": texto}), "commentCreate")


def relacionar(cliente: Cliente, bloqueadora_id: str, bloqueada_id: str) -> None:
    """A issue `bloqueada_id` passa a estar bloqueada pela `bloqueadora_id`."""
    dados = cliente.consultar("Relacionar", RELACIONAR, {"issue": bloqueadora_id, "relacionada": bloqueada_id})
    _sucesso(dados, "issueRelationCreate")


def desrelacionar(cliente: Cliente, relacao_id: str) -> None:
    """Apaga a relação, pelo id que o `bloqueada_por` da issue traz."""
    _sucesso(cliente.consultar("Desrelacionar", DESRELACIONAR, {"id": relacao_id}), "issueRelationDelete")


# A ordem dos status que o espelho avança: o Linear só sobe nela, e o que está fora dela (o `saiu` inclusive) vale como
# abaixo da primeira (spec 6d-repositorio, §9.3, decisão 6 do plano do PR 2).
ORDEM_DO_STATUS = ("espera", "pronta", "andamento", "revisao", "fechada")
SAIU = "saiu"
# Os status cujo avanço pelo espelho deixa o comentário `estado acertado pelo espelho`: de `espera` a `pronta` nenhuma
# transição da ficha se perdeu.
COM_COMENTARIO_DE_ESTADO = ("andamento", "revisao", "fechada")
# O status do bloco em cada estado dele; o `blocked` vale o do `estado_anterior`, e o que o `estado_anterior` não diz
# (`—`) vale `andamento`: o bloco existe e a ficha já começou.
_STATUS_DO_ESTADO = {
    "planning": "andamento", "ready_for_execution": "andamento", "executing": "andamento",
    "ready_for_review": "revisao", "reviewing": "revisao", "ready_for_closure": "revisao", "closing": "revisao",
}


def avanca(atual: str | None, novo: str) -> bool:
    """Se o status `novo` está acima do `atual` na `ORDEM_DO_STATUS`. O `atual` fora da ordem, ou `None`, vale como
    abaixo de `espera`; o `saiu` avança de qualquer um, menos de quem já saiu (a mesma coisa não é avanço)."""
    if novo == SAIU:
        return atual != SAIU
    posicao_atual = ORDEM_DO_STATUS.index(atual) if atual in ORDEM_DO_STATUS else -1
    return novo in ORDEM_DO_STATUS and ORDEM_DO_STATUS.index(novo) > posicao_atual


def status_da_ficha(situacao: str, bloco_: bloco.EstadoDoBloco | None) -> tuple[str | None, bool]:
    """A chave do status (§9.3) da ficha com a `situacao` do `fichas`, e se ela está bloqueada: o bloco em `blocked`.

    O bloco em `blocked` vale o status do `estado_anterior`. O `None` quer dizer que a ficha não espelha: a `fora da
    forma` e a que só existe numa lane. A `saiu da passagem/v<N>` traz a marca do bloqueio do bloco vivo dela, que o
    `importar` trava.
    """
    bloqueada = bloco_ is not None and bloco_.estado == "blocked"
    if situacao in ("pronta", "fechada"):
        return situacao, False
    if situacao.startswith("espera "):
        return "espera", False
    if situacao.startswith("saiu da passagem/"):
        return SAIU, bloqueada
    if situacao.startswith(("em bloco (", "bloco sem lane (")) and bloco_ is not None:
        return _STATUS_DO_ESTADO.get(bloco_.efetivo, "andamento"), bloqueada
    return None, False


_RE_DATA = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_RE_SEPARADOR = re.compile(r":?-+:?")


def _celulas(linha: str) -> list[str]:
    """As células da linha de tabela, sem as barras das pontas e sem espaço nas bordas de cada uma."""
    miolo = linha.strip()
    miolo = miolo[1:] if miolo.startswith("|") else miolo
    miolo = miolo[:-1] if miolo.endswith("|") else miolo
    return [celula.strip() for celula in miolo.split("|")]


def marcos(texto: str) -> dict[str, str]:
    """O nome (coluna `Marco`) e o prazo (coluna `Prazo`, como está escrito) de cada linha da primeira tabela da seção
    `## Marcos` do texto; vazio sem a seção, sem a tabela ou sem uma das duas colunas."""
    secoes = campos.secoes(texto, "## Marcos")
    linhas_da_secao = secoes[0][2] if secoes else []
    tabela: list[str] = []
    for _, linha in linhas_da_secao:
        if linha.lstrip().startswith("|"):
            tabela.append(linha)
        elif tabela:
            break
    if len(tabela) < 2 or not all(_RE_SEPARADOR.fullmatch(celula) for celula in _celulas(tabela[1])):
        return {}
    cabecalho = _celulas(tabela[0])
    if "Marco" not in cabecalho or "Prazo" not in cabecalho:
        return {}
    na_coluna_marco, na_coluna_prazo = cabecalho.index("Marco"), cabecalho.index("Prazo")
    achados: dict[str, str] = {}
    for linha in tabela[2:]:
        celulas = _celulas(linha)
        nome = celulas[na_coluna_marco] if na_coluna_marco < len(celulas) else ""
        if nome:
            achados.setdefault(nome, celulas[na_coluna_prazo] if na_coluna_prazo < len(celulas) else "")
    return achados


def _data(prazo: str) -> str | None:
    """O prazo, quando é uma data `AAAA-MM-DD` que existe; senão `None`."""
    if not _RE_DATA.fullmatch(prazo):
        return None
    try:
        datetime.date.fromisoformat(prazo)
    except ValueError:
        return None
    return prazo


def descricao(ficha: fichas.Ficha) -> str:
    """A descrição da issue: `Espelho de <ID> (<arquivo>); muda pelo repositório, não aqui.`, uma linha em branco e o
    texto da ficha como está."""
    return f"Espelho de {ficha.id} ({ficha.arquivo}); muda pelo repositório, não aqui.\n\n{ficha.texto}"


# O que o Linear faz com a descrição que recebe (sonda R3): o `- ` do item vira `* `, também recuado; entra uma linha em
# branco depois do título `### ...`; o alvo do link `(alvo)` vira `(<alvo>)`, com o não ASCII em percent-encoding; a
# quebra do fim sai.
_RE_ITEM_COM_ASTERISCO = re.compile(r"^(\s*)\*(?= |$)")
# O alvo de um link, entre `<>` ou sem eles: o sem `<>` não tem espaço, parêntese nem `<>`.
_RE_ALVO_DO_LINK = re.compile(r"\]\((?:<([^<>\n]*)>|([^<>()\s]*))\)")


def _alvo_decodificado(achado: re.Match) -> str:
    alvo = achado.group(1) if achado.group(1) is not None else achado.group(2)
    return f"]({urllib.parse.unquote(alvo)})"


def _normalizada(texto: str) -> str:
    """O texto sem os espaços do fim de cada linha e sem as linhas em branco, com o item de lista sempre em `- ` e o
    alvo de link sempre sem `<>` e decodificado, com `<>` ou sem eles no texto de origem: a forma em que a descrição
    do repositório e a que o Linear devolve se igualam quando só a re-renderização do Linear as separa."""
    linhas = []
    for linha in texto.split("\n"):
        linha = linha.rstrip()
        if not linha:
            continue
        linha = _RE_ITEM_COM_ASTERISCO.sub(r"\1-", linha)
        linha = _RE_ALVO_DO_LINK.sub(_alvo_decodificado, linha)
        linhas.append(linha)
    return "\n".join(linhas)


def mesma_descricao(a: str, b: str) -> bool:
    """Se as duas descrições são iguais depois da normalização que o Linear pede: os espaços do fim de cada linha, as
    linhas em branco, o `* ` do item como `- ` e o alvo do link, com `<>` ou sem eles, como `(alvo)` decodificado."""
    return _normalizada(a) == _normalizada(b)


def _itens_do_campo(texto_normalizado: str, nome: str) -> list[str] | None:
    """Os textos dos itens do campo no texto, pelo leitor de campos das fichas, ou `None` sem o campo."""
    achado = campos.itens_do_campo(campos.linhas_fora_de_blocos(texto_normalizado), nome)
    return None if achado is None else [item for _, item in achado[1]]


def partes_que_mudaram(antiga: str, nova: str) -> list[str]:
    """Os campos de `fichas.CAMPOS_DA_FICHA` cujo texto difere entre as duas descrições, na ordem dessa tupla. As duas
    passam pela mesma normalização da `mesma_descricao` antes da leitura dos campos."""
    antiga, nova = _normalizada(antiga), _normalizada(nova)
    return [nome for nome in fichas.CAMPOS_DA_FICHA if _itens_do_campo(antiga, nome) != _itens_do_campo(nova, nome)]


@dataclass(frozen=True)
class IssueDesejada:
    """A issue que a ficha deve ter no Linear, antes de olhar o que o Linear já tem.

    O `status` é a chave do §9.3 (`None` quando a ficha não espelha) e o `motivo`, o do bloco bloqueado, ou vazio. O
    `milestone` é o marco da ficha, e o `prazo`, o dele quando é uma data. O `depende` traz só as fichas do Depende que
    também espelham, as que ganham relação; as `citadas` são todas as que o Depende cita, espelhem ou não, e a relação
    que o Linear tem com uma delas não sai (§9.2). O `bloco` é o da lane ou, sem lane, o do ramo principal, e o
    `lane_aqui`, se ele está numa lane desta máquina.
    """

    ficha: str
    titulo: str
    descricao: str
    status: str | None
    bloqueada: bool
    motivo: str
    milestone: str | None
    prazo: str | None
    depende: tuple[str, ...]
    bloco: bloco.EstadoDoBloco | None
    lane_aqui: bool
    situacao: str
    citadas: tuple[str, ...] = ()


def _bloco_da_ficha(id_: str, q: fichas.Quadro) -> tuple[bloco.EstadoDoBloco | None, bool]:
    """O bloco da ficha, da lane ou, sem lane, do ramo principal, e se ele está numa lane do quadro."""
    lane = next((lane for lane in q.lanes if lane.bloco.id == id_), None)
    if lane is not None:
        return lane.bloco, True
    return q.principal.get(id_), False


def _prazos_dos_marcos(raiz: Path, q: fichas.Quadro) -> dict[str, str]:
    """Os prazos da tabela `## Marcos` dos arquivos das FICHA da cópia da passagem; o arquivo ilegível fica de fora."""
    prazos: dict[str, str] = {}
    vistos: set[str] = set()
    for ficha in q.fichas:
        if not ficha.id.startswith(f"{fichas.PREFIXO_DA_PASSAGEM}-") or ficha.arquivo in vistos:
            continue
        vistos.add(ficha.arquivo)
        try:
            texto = comum.ler_texto(Path(raiz) / ficha.arquivo)
        except (OSError, UnicodeDecodeError):
            continue
        for nome, prazo in marcos(texto).items():
            prazos.setdefault(nome, prazo)
    return prazos


def desejadas(perfil, q: fichas.Quadro, raiz: Path) -> list[IssueDesejada]:
    """Uma issue desejada por linha do `fichas.listar`, na ordem dele.

    A `raiz` é a da árvore do quadro: o prazo do marco sai da tabela `## Marcos` do arquivo das FICHA da cópia da
    passagem, que o quadro não carrega. A ficha sem texto no quadro (a que saiu da passagem com a lane viva, ou a que só
    existe numa lane) fica com a descrição vazia e, sem slug no bloco, com o ID como título.
    """
    por_id: dict[str, fichas.Ficha] = {}
    for ficha in q.fichas:
        por_id.setdefault(ficha.id, ficha)
    linhas = []
    for id_, situacao in fichas.listar(q, perfil):
        estado, lane_aqui = _bloco_da_ficha(id_, q)
        chave, bloqueada = status_da_ficha(situacao, estado)
        linhas.append((id_, situacao, estado, lane_aqui, chave, bloqueada))
    espelham = {id_ for id_, _, _, _, chave, _ in linhas if chave is not None}
    prazos = _prazos_dos_marcos(raiz, q)
    desejadas_: list[IssueDesejada] = []
    for id_, situacao, estado, lane_aqui, chave, bloqueada in linhas:
        ficha = por_id.get(id_)
        slug = ficha.slug if ficha is not None else (estado.slug if estado is not None else "")
        marco = ((fichas.campo(ficha, "Marco") or [""])[0]) if ficha is not None else ""
        milestone = None if marco in ("", bloco.SEM) else marco
        citadas = fichas.dependencias(ficha, perfil.prefixo)
        desejadas_.append(IssueDesejada(
            ficha=id_,
            titulo=f"{id_}: {slug}" if slug else id_,
            descricao=descricao(ficha) if ficha is not None else "",
            status=chave,
            bloqueada=bloqueada,
            motivo=estado.motivo if bloqueada and estado.motivo != bloco.SEM else "",
            milestone=milestone,
            prazo=_data(prazos.get(milestone, "")) if milestone is not None else None,
            depende=tuple(dep for dep in citadas if dep in espelham),
            bloco=estado,
            lane_aqui=lane_aqui,
            situacao=situacao,
            citadas=tuple(citadas),
        ))
    return desejadas_


def _da_passagem(id_: str) -> bool:
    """Se o ID é de uma ficha da passagem (`FICHA-NN`), e não do backlog do código."""
    return id_.startswith(f"{fichas.PREFIXO_DA_PASSAGEM}-")


def _chave_do_status(config: perfil_desenvolvimento.Linear, nome: str | None) -> str | None:
    """A chave do status do perfil cujo nome no Linear é `nome`; um nome que o perfil não tem dá `None`."""
    return next((chave for chave, nome_do_linear in config.status if nome_do_linear == nome), None)


def _recusar_duas_issues(existentes: list[IssueNoLinear]) -> None:
    """Recusa o ID de ficha com mais de uma issue no projeto, antes de qualquer gravação."""
    por_ficha: dict[str, list[IssueNoLinear]] = {}
    for issue in existentes:
        if issue.ficha is not None:
            por_ficha.setdefault(issue.ficha, []).append(issue)
    for ficha, issues in por_ficha.items():
        if len(issues) > 1:
            a, b = issues[0].identificador, issues[1].identificador
            raise bloco.Recusa(f"duas issues para {ficha} no Linear: {a} e {b}; apague uma")


def _dono(raiz: Path, cliente: Cliente, executar) -> tuple[str, str] | None:
    """O e-mail do `git config user.email` da raiz e o id do usuário do Linear que o tem; sem um dos dois, `None`."""
    feito = bloco.git(raiz, ["config", "user.email"], executar)
    email = feito.stdout.decode("utf-8", errors="replace").strip() if feito.returncode == 0 else ""
    achado = usuario(cliente, email) if email else None
    return (email, achado) if achado else None


@dataclass
class _Plano:
    """O que o espelho faz por uma ficha, decidido antes de gravar. O `tipo` é `criar`, `acertar` ou `fora` (a linha que
    só aparece na saída). As `partes` são as da linha da saída que se gravam com a issue, e as relações têm as suas
    (`blocked by +<ID>` e `blocked by -<ID>`), que se gravam depois. Os `campos` são os do Linear, menos a milestone,
    que vai pelo nome e só ganha o id depois de criada."""

    ficha: str
    tipo: str
    partes: list[str]
    existente: IssueNoLinear | None = None
    campos: dict = field(default_factory=dict)
    milestone: str | None = None
    comentarios: list[str] = field(default_factory=list)
    relacionar: list[str] = field(default_factory=list)  # as fichas que passam a bloquear esta
    desrelacionar: list[tuple[str, str]] = field(default_factory=list)  # a ficha e o id da relação que sai

    def partes_das_relacoes(self) -> list[str]:
        mais = [f"blocked by +{dep}" for dep in self.relacionar]
        return mais + [f"blocked by -{dep}" for dep, _ in self.desrelacionar]


class _Planejador:
    """Compara cada issue desejada com a do Linear e decide a criação, o acerto ou a saída, sem gravar."""

    def __init__(self, config: perfil_desenvolvimento.Linear, ctx: ContextoDoLinear, q: fichas.Quadro,
                 dono: tuple[str, str] | None, tem_issue: set[str]):
        self.config = config
        self.ctx = ctx
        self.q = q
        self.dono = dono
        self.tem_issue = tem_issue  # as fichas que terão issue no Linear depois do espelho

    def _estado(self, nome: str) -> str:
        if nome not in self.ctx.estados:
            raise FalhaDoLinear(f"status {nome} não existe no time {self.config.time}")
        return self.ctx.estados[nome]

    def _onde(self, ficha: str) -> str:
        if _da_passagem(ficha) and self.q.manifesto is not None:
            return f"na passagem/v{self.q.manifesto.versao}"
        return "no backlog do código"

    def _bloqueio(self, d: IssueDesejada) -> str:
        return f"bloqueado: {d.motivo}" if d.motivo else "bloqueado"

    def _status(self, e: IssueNoLinear, novo: str, situacao: str, bloco_: bloco.EstadoDoBloco | None):
        """O `stateId`, a parte da linha e o comentário do avanço da issue ao status `novo`; sem avanço, `None`."""
        nome = self.config.nome_do_status(novo)
        if nome == e.estado or not avanca(_chave_do_status(self.config, e.estado), novo):
            return None
        parte = f"status {e.estado} → {nome}"
        if novo == SAIU:
            return self._estado(nome), f"{parte} ({situacao})", situacao
        comentario = None
        if novo in COM_COMENTARIO_DE_ESTADO and bloco_ is not None:
            comentario = f"estado acertado pelo espelho: {bloco_.estado} ({bloco_.atualizado_em})"
        return self._estado(nome), parte, comentario

    def criar(self, d: IssueDesejada) -> _Plano:
        nome = self.config.nome_do_status(d.status)
        rotulos = [self.config.rotulo, *([self.config.rotulo_bloqueio] if d.bloqueada else [])]
        campos = {"title": d.titulo, "description": d.descricao, "stateId": self._estado(nome),
                  "labelIds": [self.ctx.rotulos[rotulo] for rotulo in rotulos]}
        partes = [f"criada ({nome}{f', {d.milestone}' if d.milestone else ''})"]
        if d.lane_aqui and self.dono is not None:
            campos["assigneeId"] = self.dono[1]
            partes.append(f"responsável {self.dono[0]}")
        relacionar = [dep for dep in d.depende if dep in self.tem_issue]
        comentarios = [self._bloqueio(d)] if d.bloqueada else []
        return _Plano(d.ficha, "criar", partes, None, campos, d.milestone, comentarios, relacionar)

    def acertar(self, d: IssueDesejada, e: IssueNoLinear) -> _Plano:
        config = self.config
        campos: dict = {}
        partes: list[str] = []
        comentarios: list[str] = []
        if e.titulo != d.titulo:
            campos["title"] = d.titulo
            partes.append("título")
        # A ficha sem texto no quadro (a que saiu com a lane viva) fica com a descrição que o Linear já tem.
        if d.descricao and not mesma_descricao(e.descricao, d.descricao):
            campos["description"] = d.descricao
            partes.append("descrição")
            mudaram = ", ".join(partes_que_mudaram(e.descricao, d.descricao))
            comentarios.append(f"mudou {self._onde(d.ficha)}{f': {mudaram}' if mudaram else ''}")
        queridos = [config.rotulo, *([config.rotulo_bloqueio] if d.bloqueada else [])]
        mais = [rotulo for rotulo in queridos if rotulo not in e.rotulos]
        # Dos rótulos, só o de bloqueio sai: o que alguém pôs à mão no Linear fica.
        menos = [config.rotulo_bloqueio] if not d.bloqueada and config.rotulo_bloqueio in e.rotulos else []
        if mais:
            campos["addedLabelIds"] = [self.ctx.rotulos[rotulo] for rotulo in mais]
        if menos:
            campos["removedLabelIds"] = [self.ctx.rotulos[rotulo] for rotulo in menos]
        partes += [f"rótulo {rotulo} +" for rotulo in mais] + [f"rótulo {rotulo} -" for rotulo in menos]
        milestone = d.milestone if d.milestone is not None and d.milestone != e.milestone else None
        if milestone is not None:
            partes.append(f"milestone {milestone}")
        acerto = self._status(e, d.status, d.situacao, d.bloco)
        if acerto is not None:
            campos["stateId"], parte, comentario = acerto
            partes.append(parte)
            if comentario is not None:
                comentarios.append(comentario)
        if config.rotulo_bloqueio in mais:
            comentarios.append(self._bloqueio(d))
        if e.responsavel is None and d.lane_aqui and self.dono is not None:
            campos["assigneeId"] = self.dono[1]
            partes.append(f"responsável {self.dono[0]}")
        relacionar: list[str] = []
        desrelacionar: list[tuple[str, str]] = []
        if d.descricao:  # sem o texto da ficha o Depende não se sabe, e as relações ficam como estão
            relacionar = [dep for dep in d.depende if dep in self.tem_issue and dep not in e.bloqueada_por]
            desrelacionar = [(dep, relacao) for dep, relacao in e.bloqueada_por.items() if dep not in d.citadas]
        return _Plano(d.ficha, "acertar", partes, e, campos, milestone, comentarios, relacionar, desrelacionar)

    def saiu(self, e: IssueNoLinear, situacao: str) -> _Plano:
        """A issue de uma ficha da passagem que a cópia não tem mais: só o status e o comentário mudam."""
        acerto = self._status(e, SAIU, situacao, None)
        if acerto is None:
            return _Plano(e.ficha, "acertar", [], e)
        estado_id, parte, comentario = acerto
        return _Plano(e.ficha, "acertar", [parte], e, {"stateId": estado_id}, None, [comentario])


class _Gravador:
    """Grava os planos no Linear, ou, com o `seco`, só os percorre, e guarda o que foi gravado ficha por ficha: as
    partes da issue, depois as das relações, na ordem da linha da saída. O `gravou` diz se alguma escrita já deu certo,
    e o `escrito` e as `milestones` são o que a saída mostra se uma chamada falhar no meio."""

    def __init__(self, cliente: Cliente, ctx: ContextoDoLinear, existentes: list[IssueNoLinear], seco: bool):
        self.cliente = cliente
        self.ctx = ctx
        self.seco = seco
        self.marcos = dict(ctx.milestones)
        self.ids = {issue.ficha: issue.id for issue in existentes if issue.ficha is not None}
        self.milestones: list[str] = []
        self.escrito: dict[str, list[str]] = {}
        self.gravou = False

    def milestone(self, nome: str, prazo: str | None) -> None:
        if not self.seco:
            self.marcos[nome] = criar_milestone(self.cliente, self.ctx, nome, prazo)
            self.gravou = True
        self.milestones.append(nome)

    def issue(self, plano: _Plano) -> None:
        """Cria ou atualiza a issue do plano e grava os comentários dela; o id da criada entra em `ids`. A issue conta
        como gravada quando a criação ou a atualização deu certo, e a falha de um comentário depois dela perde esse
        comentário, porque a rodada seguinte vê a issue sem mudança."""
        campos = dict(plano.campos)
        if plano.milestone is not None and not self.seco:
            campos["projectMilestoneId"] = self.marcos[plano.milestone].id
        if not self.seco:
            if plano.existente is None:
                self.ids[plano.ficha] = criar_issue(self.cliente, self.ctx, campos)
                self.gravou = True
            elif campos:
                atualizar_issue(self.cliente, plano.existente.id, campos)
                self.gravou = True
        self.escrito[plano.ficha] = list(plano.partes)
        if not self.seco:
            for texto in plano.comentarios:
                comentar(self.cliente, self.ids[plano.ficha], texto)
                self.gravou = True

    def relacoes(self, plano: _Plano) -> None:
        """Cria as relações que faltam e apaga as que saíram, na ordem das partes da linha."""
        for dependencia in plano.relacionar:
            if not self.seco:
                relacionar(self.cliente, self.ids[dependencia], self.ids[plano.ficha])
                self.gravou = True
            self.escrito.setdefault(plano.ficha, []).append(f"blocked by +{dependencia}")
        for dependencia, relacao in plano.desrelacionar:
            if not self.seco:
                desrelacionar(self.cliente, relacao)
                self.gravou = True
            self.escrito.setdefault(plano.ficha, []).append(f"blocked by -{dependencia}")

    def linhas(self, planos: list[_Plano], com_as_de_fora: bool) -> list[str]:
        """As milestones criadas e uma linha por ficha com algo gravado, na ordem dos planos; as linhas que só aparecem
        na saída (`não espelha` e a issue sem ficha no repositório) entram só na saída completa."""
        linhas = [f"milestone {nome}: criada" for nome in self.milestones]
        for plano in planos:
            if plano.tipo == "fora":
                partes = plano.partes if com_as_de_fora else []
            else:
                partes = self.escrito.get(plano.ficha, [])
            if partes:
                linhas.append(f"{plano.ficha}: {'; '.join(partes)}")
        return linhas


def espelhar(raiz: Path, perfil, cliente: Cliente, seco: bool = False, executar=subprocess.run) -> bloco.Saida:
    """Refaz o espelho das fichas no Linear (§9.6); o `perfil` traz a `[desenvolvimento.linear]`.

    A ordem: o contexto, as issues do projeto e o quadro das fichas; a recusa das duas issues de um ID, antes de
    gravar; as milestones que faltam; cada issue, criada ou acertada; as relações, depois de todas as issues existirem;
    e as que saíram da passagem. A falha do Linear antes da primeira gravação sobe como `FalhaDoLinear`, e a recusa das
    duas issues, como `bloco.Recusa`. A falha depois da primeira gravação sobe como `bloco.Recusa` com as linhas do que
    já foi gravado e, por último, `linear: <motivo>`. Com o `seco`, nada é gravado, e as linhas e o resumo são os mesmos.

    A saída tem as milestones criadas, uma linha por issue que mudou ou que não espelha, e o resumo.
    """
    config = perfil.linear
    ctx = ler_contexto(cliente, config)
    existentes = issues_do_projeto(cliente, ctx, config.rotulo)
    q = fichas.quadro(raiz, perfil, executar)
    desejadas_ = desejadas(perfil, q, raiz)
    _recusar_duas_issues(existentes)
    por_ficha = {issue.ficha: issue for issue in existentes if issue.ficha is not None}
    # A que saiu e nunca foi ao Linear não ganha issue: não há o que cancelar.
    tem_issue = set(por_ficha) | {d.ficha for d in desejadas_ if d.status not in (None, SAIU)}
    precisa_do_dono = any(d.status is not None and d.lane_aqui and (
        d.ficha not in por_ficha or por_ficha[d.ficha].responsavel is None) for d in desejadas_)
    planejador = _Planejador(config, ctx, q, _dono(raiz, cliente, executar) if precisa_do_dono else None, tem_issue)

    planos: list[_Plano] = []
    for d in desejadas_:
        existente = por_ficha.get(d.ficha)
        if d.status is None:
            planos.append(_Plano(d.ficha, "fora", [f"não espelha ({d.situacao})"]))
        elif existente is not None:
            planos.append(planejador.acertar(d, existente))
        elif d.status != SAIU:
            planos.append(planejador.criar(d))
    saidas: list[_Plano] = []  # as issues sem ficha na cópia da passagem nem no backlog do código
    desejadas_ids = {d.ficha for d in desejadas_}
    for issue in existentes:
        if issue.ficha is None or issue.ficha in desejadas_ids:
            continue
        if _da_passagem(issue.ficha) and q.manifesto is not None:
            saidas.append(planejador.saiu(issue, f"saiu da passagem/v{q.manifesto.versao}"))
        else:
            saidas.append(_Plano(issue.ficha, "fora", ["no Linear e fora do repositório; nada muda"]))

    prazos = {d.milestone: d.prazo for d in desejadas_ if d.milestone is not None}
    faltam = list(dict.fromkeys(
        plano.milestone for plano in planos if plano.milestone is not None and plano.milestone not in ctx.milestones))
    todos = planos + saidas
    gravador = _Gravador(cliente, ctx, existentes, seco)
    try:
        for nome in faltam:
            gravador.milestone(nome, prazos.get(nome))
        for plano in planos:
            if plano.tipo != "fora":
                gravador.issue(plano)
        for plano in planos:
            gravador.relacoes(plano)
        for plano in saidas:
            if plano.tipo != "fora":
                gravador.issue(plano)
    except FalhaDoLinear as erro:
        if not gravador.gravou:
            raise  # antes da primeira gravação não há o que mostrar: fica só a mensagem
        linhas = [*gravador.linhas(todos, False), f"linear: {erro.mensagem}"]
        raise bloco.Recusa("\n".join(linhas)) from None
    linhas = gravador.linhas(todos, True)
    criadas = sum(plano.tipo == "criar" for plano in todos)
    acertadas = sum(plano.tipo == "acertar" and bool(plano.partes or plano.partes_das_relacoes()) for plano in todos)
    sem_mudanca = sum(plano.tipo == "acertar" and not (plano.partes or plano.partes_das_relacoes()) for plano in todos)
    linhas.append(f"linear: {criadas} criadas, {acertadas} acertadas, {sem_mudanca} sem mudança")
    return bloco.Saida(tuple(linhas))


# Os comandos que avisam o Linear da transição que gravaram (§9.5), na ordem da spec; uma catraca dos testes confere que
# todo comando que grava o `estado.md` com commit está aqui.
COMANDOS_QUE_AVISAM = (
    "lane abrir", "bloco planejado", "bloco executando", "bloco executado", "bloco revisando", "bloco revisado",
    "bloco corrigir", "bloco finalizar", "bloco bloquear", "bloco desbloquear", "bloco replanejar", "lane conferir",
    "retorno abrir", "lane fechar",
)
TEMPO_DO_AVISO = 10
SEM_EMAIL = "sem e-mail"


def _git_texto(arvore: Path, argumentos: list[str], executar) -> str:
    """A saída do `git -C <arvore>` sem os espaços das pontas; o git que sai com erro dá o texto vazio."""
    feito = bloco.git(arvore, argumentos, executar)
    return feito.stdout.decode("utf-8", errors="replace").strip() if feito.returncode == 0 else ""


def _status_do_aviso(aviso: bloco.Aviso) -> tuple[str, bool]:
    """A chave do status (§9.3) que o estado novo do aviso dá à ficha, e se ela fica bloqueada. O `blocked` vale o
    status do `estado_anterior` do bloco; `pronta` e `fechada` são os da ficha sem bloco; o que vem depois do primeiro
    espaço do `para` (`pronta (lane abandonada)`) é só texto do comentário."""
    estado = aviso.para.split(" ", 1)[0]
    if estado in ("pronta", "fechada"):
        return estado, False
    efetivo = aviso.bloco.estado_anterior if estado == "blocked" and aviso.bloco is not None else estado
    return _STATUS_DO_ESTADO.get(efetivo, "andamento"), estado == "blocked"


def _texto_do_aviso(aviso: bloco.Aviso, email: str, ramo: str, commit: str, agora) -> str:
    """O comentário do aviso: `<ID> · <de> → <para> · <e-mail> · <atualizado_em> · <ramo>@<commit curto>`, com o motivo
    do bloco em `blocked` e, no fim, o link do PR."""
    estado = aviso.bloco
    quando = estado.atualizado_em if estado is not None else agora().strftime("%Y-%m-%dT%H:%M")
    texto = f"{aviso.id} · {aviso.de} → {aviso.para} · {email} · {quando} · {ramo}@{commit}"
    if estado is not None and estado.estado == "blocked" and estado.motivo != bloco.SEM:
        texto += f" · motivo: {estado.motivo}"
    return f"{texto} · {aviso.pr}" if aviso.pr else texto


def _acertar_a_issue(config: perfil_desenvolvimento.Linear, cliente: Cliente, ctx: ContextoDoLinear,
                     existente: IssueNoLinear, nome: str, bloqueada: bool, email: str, dono: str | None) -> None:
    """Põe a issue no status `nome`, com o rótulo de bloqueio só no bloco bloqueado e o dono como responsável. Diferente
    do espelho, o aviso recua o status e troca o responsável."""
    campos: dict = {}
    if existente.estado != nome:
        campos["stateId"] = ctx.estados[nome]
    rotulo = config.rotulo_bloqueio
    if bloqueada and rotulo not in existente.rotulos:
        campos["addedLabelIds"] = [ctx.rotulos[rotulo]]
    if not bloqueada and rotulo in existente.rotulos:
        campos["removedLabelIds"] = [ctx.rotulos[rotulo]]
    if dono is not None and existente.responsavel != email:
        campos["assigneeId"] = dono
    if campos:
        atualizar_issue(cliente, existente.id, campos)


def _criar_a_que_falta(perfil, cliente: Cliente, ctx: ContextoDoLinear, aviso: bloco.Aviso, chave: str,
                       bloqueada: bool, dono: str | None, executar) -> str:
    """Cria a issue da ficha com os campos do §9.2, pelo planejador e pelo gravador do espelho, no status do aviso, com
    a milestone que falta e o `blocked by` de cada ficha do Depende que já tem issue, e devolve o id. O responsável é o
    dono do aviso, mesmo sem lane nesta máquina."""
    config = perfil.linear
    raiz = Path(aviso.arvore)
    q = fichas.quadro(raiz, perfil, executar)
    desejada = next((d for d in desejadas(perfil, q, raiz) if d.ficha == aviso.id), None)
    if desejada is None:
        raise FalhaDoLinear(f"{aviso.id} não está nas fichas do repositório")
    estado = aviso.bloco
    motivo = estado.motivo if bloqueada and estado is not None and estado.motivo != bloco.SEM else ""
    desejada = dataclasses.replace(desejada, status=chave, bloqueada=bloqueada, motivo=motivo)
    dependencias = []
    for dependencia in desejada.depende:
        dependencias += issues_da_ficha(cliente, ctx, config.rotulo, dependencia)[:1]
    plano = _Planejador(config, ctx, q, None, {issue.ficha for issue in dependencias}).criar(desejada)
    plano.comentarios.clear()  # o comentário do aviso já traz o motivo do bloqueio
    if dono is not None:
        plano.campos["assigneeId"] = dono
    gravador = _Gravador(cliente, ctx, dependencias, False)
    if plano.milestone is not None and plano.milestone not in ctx.milestones:
        gravador.milestone(plano.milestone, desejada.prazo)
    gravador.issue(plano)
    gravador.relacoes(plano)
    return gravador.ids[aviso.id]


def _enviar_o_aviso(perfil, cliente: Cliente, aviso: bloco.Aviso, executar, agora) -> None:
    """Acerta a issue da ficha, ou a cria, e grava o comentário do aviso; a falha sobe."""
    config = perfil.linear
    arvore = Path(aviso.arvore)
    email = _git_texto(arvore, ["config", "user.email"], executar) or SEM_EMAIL
    ramo = _git_texto(arvore, ["rev-parse", "--abbrev-ref", "HEAD"], executar) or "sem ramo"
    commit = _git_texto(arvore, ["rev-parse", "--short", "HEAD"], executar) or "sem commit"
    chave, bloqueada = _status_do_aviso(aviso)
    nome = config.nome_do_status(chave)
    ctx = ler_contexto(cliente, config)
    if nome not in ctx.estados:
        raise FalhaDoLinear(f"status {nome} não existe no time {config.time}")
    achadas = issues_da_ficha(cliente, ctx, config.rotulo, aviso.id)
    if len(achadas) > 1:
        raise FalhaDoLinear(
            f"duas issues para {aviso.id} no Linear: {achadas[0].identificador} e {achadas[1].identificador}; "
            "apague uma")
    dono = usuario(cliente, email) if email != SEM_EMAIL else None
    if achadas:
        _acertar_a_issue(config, cliente, ctx, achadas[0], nome, bloqueada, email, dono)
        issue_id = achadas[0].id
    else:
        issue_id = _criar_a_que_falta(perfil, cliente, ctx, aviso, chave, bloqueada, dono, executar)
    comentar(cliente, issue_id, _texto_do_aviso(aviso, email, ramo, commit, agora))


def avisar(perfil, aviso: bloco.Aviso, ambiente: Mapping[str, str] = os.environ, executar=subprocess.run,
           agora=datetime.datetime.now) -> str | None:
    """Manda ao Linear a transição que o comando gravou (§9.5) e devolve a linha a mais da saída, ou `None`.

    Sem a `[desenvolvimento.linear]` no perfil, `None`, sem falar com ninguém; sem a chave no ambiente, a linha da chave
    ausente; na falha, de qualquer tipo, `linear: aviso não enviado (<motivo>); rode harness.py linear espelhar`. A
    função nunca lança, e todas as chamadas dividem os `TEMPO_DO_AVISO` segundos do cliente.
    """
    if perfil.linear is None:
        return None
    chave = chave_do_ambiente(ambiente)
    if chave is None:
        return "linear: sem LINEAR_API_KEY no ambiente; aviso não enviado"
    try:
        _enviar_o_aviso(perfil, Cliente(chave, prazo_total=TEMPO_DO_AVISO), aviso, executar, agora)
    except (FalhaDoLinear, bloco.Recusa) as erro:
        motivo = erro.mensagem
    except UnicodeDecodeError:
        motivo = "arquivo fora do UTF-8"
    except OSError as erro:
        motivo = comum.motivo_do_sistema(erro)
    except Exception as erro:  # o aviso nunca derruba o comando que acabou de gravar a transição
        motivo = type(erro).__name__
    else:
        return None
    return f"linear: aviso não enviado ({' '.join(motivo.split())}); rode harness.py linear espelhar"
