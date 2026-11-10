"""Os oito agentes do ciclo do bloco: o frontmatter de cada um, as trocas do perfil por cima e o comando `papel`.

O `model` e o `effort` de cada agente vêm do frontmatter da pasta `agents/` da raiz do plugin; o
`[desenvolvimento.modelos]` do perfil troca os dois, e a subida do verificador em bloco sensível não muda pelo perfil.
A lista dos agentes, a ordem e o texto da coluna Papel moram aqui; o conferidor do perfil importa este módulo, e este
só importa o `bloco`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import bloco
import comum


# Os agentes moram em `<raiz do plugin>/agents`; o repositório de código não os recebe (spec do porte 1, §7.5).
PASTA_DOS_AGENTES = comum.raiz_do_nucleo() / "agents"

# O nome e o papel de cada agente, na ordem da tabela da spec 6d-bloco, §6.1.
AGENTES: tuple[tuple[str, str], ...] = (
    ("implementador-mecanico", "tarefa do plano com o código pronto, em 1 ou 2 arquivos"),
    ("implementador-integracao",
     "tarefa com vários arquivos ou decisão de padrão; o primeiro e o segundo conserto da revisão"),
    ("corretor-tardio", "consertos nas rodadas 4 e 5 do SDD e o terceiro conserto da revisão"),
    ("revisor-task", "revisão de cada tarefa no SDD, de spec e de qualidade"),
    ("re-revisor", "nova revisão só do conserto, no SDD e na revisão do bloco"),
    ("revisor-bloco", "lente 1, um despacho por eixo"),
    ("verificador-achado", "lente 2, um por achado: roda a prova ou lê o código"),
    ("contexto-leitor", "completa o Context Packet, um domínio por despacho"),
)
NOMES: tuple[str, ...] = tuple(nome for nome, _ in AGENTES)
SKILLS_DO_CICLO = ("planejar-bloco", "executar-bloco", "revisar-bloco", "finalizar-bloco")
# As skills de terceiros de que o ciclo depende: o plugin, a versão como o `ciclo.md` a escreve e as skills.
TERCEIROS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("superpowers", "7.0.0 (marketplace claude-plugins-official, commit bb92a77)",
     ("brainstorming", "writing-plans", "subagent-driven-development", "test-driven-development",
      "receiving-code-review", "verification-before-completion", "finishing-a-development-branch")),
    ("mattpocock-skills", "1.3.1", ("diagnosing-bugs", "codebase-design", "prototype", "research", "wizard")),
)
MODELOS = ("opus", "sonnet", "haiku", "fable")
PREFIXO_DO_ID = "claude-"
ESFORCOS = ("low", "medium", "high", "xhigh", "max")
AGENTE_SENSIVEL = "verificador-achado"
MODELO_SENSIVEL = "opus"
DO_WORKFLOW = ("revisor-bloco", "verificador-achado", "implementador-integracao", "corretor-tardio", "re-revisor")
ORIGENS = ("agente", "perfil")

AJUDA = """\
Diz o modelo e o esforço de cada agente do ciclo do bloco. O `model` e o `effort` vêm do frontmatter do agente, na pasta
`agents/` do plugin, e o `[desenvolvimento.modelos]` do perfil troca os dois.

- `harness.py papel <agente>`: `<agente>: model <m>, effort <e>`, com ` (perfil)` no fim quando o valor vem do perfil.
  A linha do `verificador-achado` termina em `; em bloco sensível, model opus`, e essa subida o perfil não muda.
- `harness.py papel --todos`: uma linha por agente, na ordem da tabela dos agentes.
- `--json`, nos dois: `{"agente": ..., "model": ..., "effort": ..., "origem": "agente"|"perfil"}`, com
  `"model_sensivel": "opus"` no `verificador-achado`, ou a lista, no `--todos`.

O agente fora da lista recusa com `papel: <nome> não é um agente do harness; os agentes são <lista>`, e a chamada sem
agente e sem `--todos`, ou com os dois, com `uso inválido: papel pede um agente ou --todos`, as duas com 1.
"""


@dataclass(frozen=True)
class Papel:
    agente: str
    papel: str
    model: str
    effort: str
    origem: str
    model_sensivel: str | None = None


def frontmatter(texto: str) -> dict[str, str]:
    """As linhas `chave: valor` entre os dois primeiros `---`, como o `estado.md`; sem os dois traços, vazio."""
    linhas = texto.split("\n")
    if linhas[0] != "---" or "---" not in linhas[1:]:
        return {}
    dados = {}
    for linha in linhas[1:linhas.index("---", 1)]:
        chave, separador, valor = linha.partition(": ")
        if separador:
            dados[chave] = valor
    return dados


def _do_agente(perfil, nome: str, papel: str, pasta: Path) -> Papel:
    """O papel do agente pelo frontmatter do arquivo dele e as trocas do perfil; o arquivo que falta, que não se lê ou
    sem o `model` ou o `effort` recusa."""
    arquivo = pasta / f"{nome}.md"
    try:
        texto = comum.ler_texto(arquivo) if arquivo.is_file() else None
    except (OSError, UnicodeDecodeError) as erro:
        raise bloco.Recusa(f"papel: {arquivo.name}: {bloco.motivo_da_leitura(erro)}") from None
    if texto is None:
        raise bloco.Recusa(f"papel: falta o agente {nome} em {pasta}")
    dados = frontmatter(texto)
    for chave in ("model", "effort"):
        if not dados.get(chave):
            raise bloco.Recusa(f"papel: {arquivo.name}: falta {chave} no frontmatter")
    sensivel = MODELO_SENSIVEL if nome == AGENTE_SENSIVEL else None
    troca = dict(perfil.modelos).get(nome)
    if troca is not None:
        return Papel(nome, papel, troca.model, troca.effort, "perfil", sensivel)
    return Papel(nome, papel, dados["model"], dados["effort"], "agente", sensivel)


def tabela(perfil, pasta: Path = PASTA_DOS_AGENTES) -> tuple[Papel, ...]:
    """Os oito papéis, na ordem de `AGENTES`, com o `model` e o `effort` do frontmatter e as trocas do
    `perfil.modelos` por cima. O arquivo que falta ou não se lê, ou a chave que falta, recusa."""
    return tuple(_do_agente(perfil, nome, papel, pasta) for nome, papel in AGENTES)


def do_agente(perfil, nome: str, pasta: Path = PASTA_DOS_AGENTES) -> Papel:
    """O papel de um agente; o nome fora da lista recusa."""
    textos = dict(AGENTES)
    if nome not in textos:
        raise bloco.Recusa(
            f"papel: {nome} não é um agente do harness; os agentes são {comum.juntar(NOMES)}"
        )
    return _do_agente(perfil, nome, textos[nome], pasta)


def linha(papel: Papel) -> str:
    """`<agente>: model <m>, effort <e>`, com ` (perfil)` quando a troca é do perfil e, no agente que sobe em bloco
    sensível, `; em bloco sensível, model <m>`."""
    texto = f"{papel.agente}: model {papel.model}, effort {papel.effort}"
    if papel.origem == "perfil":
        texto += " (perfil)"
    if papel.model_sensivel:
        texto += f"; em bloco sensível, model {papel.model_sensivel}"
    return texto


def para_json(papel: Papel) -> dict:
    dados = {"agente": papel.agente, "model": papel.model, "effort": papel.effort, "origem": papel.origem}
    if papel.model_sensivel:
        dados["model_sensivel"] = papel.model_sensivel
    return dados


def para_o_workflow(perfil, sensivel: bool, pasta: Path = PASTA_DOS_AGENTES) -> dict[str, dict[str, str]]:
    """O `model` e o `effort` de cada agente do workflow; o verificador usa o modelo sensível no bloco sensível, mesmo
    com troca do perfil."""
    por_nome = {papel.agente: papel for papel in tabela(perfil, pasta)}
    resultado = {}
    for nome in DO_WORKFLOW:
        papel = por_nome[nome]
        modelo = papel.model_sensivel if sensivel and papel.model_sensivel else papel.model
        resultado[nome] = {"model": modelo, "effort": papel.effort}
    return resultado


def saida(perfil, agente: str | None, como_json: bool) -> str:
    """O texto do comando `papel`: o agente dado, ou os oito, em linhas ou em JSON."""
    papeis = (do_agente(perfil, agente),) if agente is not None else tabela(perfil)
    if como_json:
        dados = [para_json(papel) for papel in papeis]
        return json.dumps(dados[0] if agente is not None else dados, ensure_ascii=False) + "\n"
    return "".join(linha(papel) + "\n" for papel in papeis)
