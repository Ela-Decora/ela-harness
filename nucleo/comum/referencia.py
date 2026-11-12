"""Referência do harness gerada pelo núcleo (spec 4c, §7): os comandos pelo parser, as skills e os agentes pelo
frontmatter e o mapa do núcleo.

O gerador percorre o parser que o `harness.py` monta e passa, sem o `format_help()` nem o `format_usage()` do
argparse, e escreve o próprio Markdown: a saída é a mesma em qualquer versão do Python, largura de terminal, locale e
diretório corrente. Só a biblioteca padrão; não lê o perfil nem o STATUS.md.
"""
from __future__ import annotations

import argparse
import ast
import errno
import re
from dataclasses import dataclass
from pathlib import Path

import caminho
import comum

AJUDA = """\
Gera a referência do harness em Markdown e a imprime: os comandos, as skills e os agentes e o mapa do núcleo.

De onde vem cada parte:

- o uso, os argumentos e as opções de cada comando e de cada ação: do parser montado no `harness.py`;
- o texto de cada comando: da constante `AJUDA` do módulo dele, a mesma que o `--help` do comando mostra;
- as skills e os agentes: do frontmatter de `skills/*/SKILL.md` e de `agents/*.md`, na raiz do plugin;
- o mapa do núcleo: da primeira frase da docstring de cada módulo das três pastas de `nucleo/`.

A referência tem as duas trilhas: os comandos do planejamento, com os comuns às duas, e, em
`## Comandos do desenvolvimento`, os que só a trilha de desenvolvimento tem.

Não lê o perfil nem o STATUS.md. A saída não depende da largura do terminal nem da versão do Python.

Com `--gravar`, grava o mesmo texto em `docs/referencia.md`, na raiz do plugin, em UTF-8 e de forma atômica, e
imprime `Gravado: docs/referencia.md (<N> linhas)`. Um teste da suíte compara esse arquivo com a saída do gerador
e, quando não batem, falha com "rode python3 nucleo/comum/harness.py referencia --gravar".

Para um comando novo:

1. escreva a `AJUDA` no módulo do comando;
2. passe a `AJUDA` como `description=` do subparser, no `harness.py`;
3. dê ao subparser um `help=` de uma linha, que é o texto do comando na tabela de comandos;
4. dê um `help=` a cada argumento e a cada opção;
5. acrescente o comando e a `AJUDA` dele à lista de ajudas do teste da referência, na ordem do parser, ou à
   lista da trilha de desenvolvimento, quando o comando é só dela; sem isso, um teste da suíte falha;
6. rode `harness.py referencia --gravar` e ponha o arquivo gerado no mesmo commit.

Sai com 0 ao imprimir ou ao gravar. Fora de um projeto, sai com 1 e `erro: raiz do projeto não encontrada: ...`;
sem conseguir ler ou gravar um arquivo, sai com 1 e `erro de arquivo: ...`.
"""

CAMINHO = "docs/referencia.md"
AVISO = (
    "Gerado por `harness.py referencia --gravar`. Não edite este arquivo: mude a `AJUDA` no módulo do comando e gere "
    "de novo."
)

CONVENCOES = """\
- Saída 0: deu certo. Saída 1: recusa, falha de verificação ou erro de entrada. Nenhum comando sai com 2.
- Toda recusa sai com 1 e diz o motivo na primeira linha, às vezes com detalhes nas linhas de baixo. A maior parte
  começa por um prefixo: `recusado:`, `uso inválido:`, `perfil inválido:`, `erro:` ou `erro de arquivo:`. Saem sem
  ele as recusas de entrada do `checar`, do `molde`, do `dossie` e do `versao`, menos as do `versao diff`, e as
  pré-condições do `gate`; o `estado` sem ação e o `proximo` saem com `STATUS.md inválido: ...`, e o `backlog ids`,
  com `backlog.md ilegível: ...`.
- Saem sempre com 0, porque são injetados e não podem abortar a sessão nem a skill: `estado --hook`,
  `perfil --para` e `guarda`. Neles, o erro vem no texto: `ERRO no hook: ...`, `ERRO: ...` e
  `guarda do harness com erro, sem decisão: ...`.
- A saída é sempre UTF-8, mesmo com o locale `C`.
- Todo caminho de documento é relativo à raiz do projeto, ou absoluto.
- `harness.py` abrevia `python3 .claude/harness/harness.py`, rodado da raiz do projeto.
- Cada comando e cada ação têm `--help`: `harness.py <comando> --help` mostra o uso, os argumentos, as opções e o
  texto do comando, e `harness.py <comando> <ação> --help`, os da ação.
- As mensagens do próprio argparse ficam em inglês depois de `uso inválido:`, como
  `the following arguments are required`.
"""

# Uma linha da tabela por termo: a linha do Markdown é longa, e a do código fica em até 120 caracteres.
CONCEITOS = (
    "| Termo | O que é |\n"
    "|---|---|\n"
    "| **Fase** ou **camada** | Um nível do planejamento, com uma pasta própria dentro da pasta do planejamento "
    "(`caminhos.planejamento`), com o nome do `id` da fase, e uma regra de escrita. As fases ficam em `fases` no "
    "perfil, na ordem; a atual, no campo `Fase` do STATUS.md. |\n"
    "| **Gate** | Ponto de aprovação que fecha uma fase: o `gate` da fase no perfil. O checklist fica em "
    "`gates.<gate>.itens`, com itens de script, de revisor, de leitor frio e humanos; a situação de cada gate, na linha dos gates "
    "do STATUS.md. |\n"
    "| **Regra da camada** | A restrição de escrita da fase, na chave `regra` dela no perfil. O bloco \"Este projeto\" "
    "das skills a mostra. |\n"
    "| **Documento** | Um arquivo `.md` de planejamento dentro da pasta de uma fase. O STATUS.md acompanha um "
    "documento ou um pacote por vez, no campo `Documento`. |\n"
    "| **Pacote** | Documentos que passam juntos pelo ciclo, com uma checagem, um revisor e uma aprovação para todos. "
    "A lista fica no campo `Pacote` do STATUS.md, e o `Documento` é o primeiro dela. |\n"
    "| **Molde** | O arquivo da pasta de moldes (`moldes.pasta`) que dá a forma do documento. Vale o primeiro par do "
    "`mapa` do perfil (`moldes.mapa`) cujo padrão casa com o caminho do documento relativo à pasta do planejamento; "
    "sem par, o do mesmo caminho relativo. Os títulos do molde são o contrato do documento. |\n"
    "| **Ciclo** | Os oito passos, de 0 a 7, por que passa cada documento ou pacote; o 0 é a preparação. O passo "
    "atual fica no campo `Passo` do STATUS.md. |\n"
    "| **Rodada** | Uma volta de perguntas da entrevista (passo 2), até 4 perguntas numa chamada da ferramenta de "
    "opções, ou uma volta do revisor (passo 5), no máximo 2. Fica no campo `Rodada` e recomeça em 1 no passo 5. |\n"
    "| **Fonte** | De onde vem o conteúdo, em ordem de precedência: as decisões registradas e o `CLAUDE.md`, depois "
    "o rascunho, depois as pastas de `caminhos.fontes`, na ordem do perfil. |\n"
    "| **`[A CONFIRMAR: motivo]`** | Marca de inferência do modelo. No passo 4, cada uma vira pergunta da ferramenta "
    "de opções: confirmada, a marca sai e o texto fica; \"tirar\", o trecho sai; corrigida, o trecho é reescrito "
    "sem marca. Ficam de fora as que citam uma pendência, \"pesquisa pendente\" ou \"pergunta aberta\". O `checar` conta as marcas, mas "
    "não falha por elas. |\n"
    "| **Ruling** | Decisão que vale além de um documento, registrada no arquivo de decisões (`caminhos.decisoes`) "
    "como `Ruling: o quê — por quê — custo se errado`, por `harness.py registrar ruling`. |\n"
    "| **Pendência** | Linha `<prefixo>-NN` da tabela de pendências do backlog.md (`caminhos.backlog`), com origem, "
    "destino e status; o prefixo é o `ids.prefixo_pendencia`. A pendência aberta com o marcador do gate no destino "
    "(`gates.<gate>.marcador_pendencia`) bloqueia o gate. |\n"
    "| **Relato** | Informação nova que surge na conversa, acrescentada por `harness.py registrar relato` à seção de "
    "informação nova do rascunho (`caminhos.rascunho`) como `<prefixo>-NN`, com o prefixo de `ids.prefixo_relato`. "
    "Entra confirmada ou não confirmada e fica pendente até ser incorporada a um documento ou descartada. |\n"
    "| **Artefato** | Linha da tabela de artefatos do backlog.md: caminho, camada, status (`rascunho`, `em-revisao` "
    "ou `aprovado`) e data. O gate exige todos os documentos da fase como `aprovado`. |\n"
    "| **Versão em aprovação** | Hash `sha256:` de 12 dígitos do documento apresentado no passo 6, ou do manifesto "
    "do pacote, gravado no campo `Versao-aprovacao`. Protege a versão aprovada até o commit. |\n"
    "| **Estudo** | Arquivo do assessor que compara opções de uma decisão, com critérios, fontes, recomendação e a "
    "decisão do usuário, na pasta `caminhos.estudos`. |\n"
    "| **Modo revisão** | O ciclo de um documento já `aprovado` que volta para correção: os mesmos passos, cada um "
    "só no escopo da pendência ou do pedido. O `Proximo` de cada passo começa por `modo revisão:`. |\n"
    "| **Relatório de pesquisa** | O que o agente `pesquisador-fatos` devolve, guardado numa pasta "
    "`pesquisa-<documento>-<AAAA-MM-DD>/` dentro de `caminhos.pesquisas`. Antes de um despacho novo, o modelo "
    "procura relatório que já responda. Entra no commit do documento. |\n"
    "| **Atrito** | Falha ou incômodo observado no uso do harness, registrado no arquivo de atritos "
    "(`caminhos.atritos`). É o que justifica uma peça nova. |\n"
)

PASTAS: tuple[tuple[str, str], ...] = (
    (
        "aprovacao/",
        "as cópias das versões marcadas no passo 6, o manifesto do pacote, o histórico e a resposta; fora do git",
    ),
    ("dossie/", "o dossiê do documento ou do pacote, refeito a cada `harness.py dossie`; fora do git"),
    (
        "nucleo/planejamento/ferramentas/",
        "o que roda fora do `harness.py`: o validador Mermaid em Node, na CI e local, e o DDL nos bancos, só na CI",
    ),
)
SAIDA = "nucleo/comum/saida.md"
SAIDA_MD = "os moldes do que o usuário lê no chat; o passo que produz cada saída lê este arquivo na hora de escrever"

_SEM_VALOR = "—"
_RE_FERRAMENTA = re.compile(r"(\w+)(?:\(([^)]*)\))?")
_HARNESS = "harness.py"


@dataclass(frozen=True)
class Componente:
    """Uma skill ou um agente, pelo frontmatter. Campo ausente fica `""`, ou `()` em `pode_usar`."""

    nome: str
    tipo: str  # "skill" ou "agente"
    quando: str
    argumento: str
    pode_usar: tuple[str, ...]
    modelo: str


def subcomandos(parser: argparse.ArgumentParser) -> list[tuple[str, str, argparse.ArgumentParser]]:
    """Nome, ajuda de uma linha (o `help` do comando, ou `""`) e parser de cada comando ou ação, na ordem do
    `choices`; sem `_SubParsersAction`, a lista vazia."""
    for acao in parser._actions:
        if isinstance(acao, argparse._SubParsersAction):
            ajudas = {escolha.dest: escolha.help or "" for escolha in acao._choices_actions}
            return [(nome, ajudas.get(nome, ""), filho) for nome, filho in acao.choices.items()]
    return []


def _nome(acao: argparse.Action) -> str:
    """`<metavar>` ou `<dest>`; o `metavar` que já vem entre `<` e `>` entra como está."""
    nome = acao.metavar if acao.metavar is not None else acao.dest
    return nome if nome.startswith("<") and nome.endswith(">") else f"<{nome}>"


def _valor(acao: argparse.Action) -> str:
    """As escolhas, como `{a,b}`, ou o nome."""
    if acao.choices is not None:
        return "{" + ",".join(str(escolha) for escolha in acao.choices) + "}"
    return _nome(acao)


def _forma(acao: argparse.Action) -> str:
    """O argumento ou a opção como no uso, sem os colchetes de opcional."""
    if acao.option_strings:
        opcao = next((texto for texto in acao.option_strings if texto.startswith("--")), acao.option_strings[0])
        return opcao if acao.nargs == 0 else f"{opcao} {_valor(acao)}"
    return _valor(acao) + ("..." if acao.nargs in ("*", "+") else "")


def _posicional_opcional(acao: argparse.Action) -> bool:
    # O argparse do 3.9 marca o `*` como obrigatório; vale o `nargs`.
    return acao.nargs in ("?", "*")


def _grupos(parser: argparse.ArgumentParser) -> dict[argparse.Action, argparse._MutuallyExclusiveGroup]:
    """O grupo exclusivo de cada ação que está num."""
    return {acao: grupo for grupo in parser._mutually_exclusive_groups for acao in grupo._group_actions}


def uso(prefixo: str, parser: argparse.ArgumentParser) -> str:
    """O uso montado na ordem em que o parser define argumentos e opções (spec 4c, §7.4), sem o `-h`.

    O grupo exclusivo entra na posição do primeiro membro, entre `(` e `)` se obrigatório, entre `[` e `]` se não; o
    `_SubParsersAction` vira `<ação>`, ou `[<ação>]` quando a ação é opcional.
    """
    grupos = _grupos(parser)
    partes = [prefixo]
    vistos = set()
    for acao in parser._actions:
        if isinstance(acao, argparse._HelpAction):
            continue
        grupo = grupos.get(acao)
        if grupo is not None:
            if grupo in vistos:
                continue
            vistos.add(grupo)
            membros = " | ".join(_forma(membro) for membro in grupo._group_actions)
            partes.append(f"({membros})" if grupo.required else f"[{membros}]")
        elif isinstance(acao, argparse._SubParsersAction):
            partes.append(_nome(acao) if acao.required else f"[{_nome(acao)}]")
        elif acao.option_strings:
            partes.append(_forma(acao) if acao.required else f"[{_forma(acao)}]")
        else:
            partes.append(f"[{_forma(acao)}]" if _posicional_opcional(acao) else _forma(acao))
    return " ".join(partes)


def linhas_da_tabela(parser: argparse.ArgumentParser) -> list[tuple[str, str, str]]:
    """Nome como no uso, sem colchetes; `sim`, `não` ou `um do grupo`; e o `help`, ou `""`. Sem o `-h` e sem a ação,
    que tem seção própria."""
    grupos = _grupos(parser)
    linhas = []
    for acao in parser._actions:
        if isinstance(acao, (argparse._HelpAction, argparse._SubParsersAction)):
            continue
        grupo = grupos.get(acao)
        if grupo is not None:
            obrigatorio = "um do grupo" if grupo.required else "não"
        elif acao.option_strings:
            obrigatorio = "sim" if acao.required else "não"
        else:
            obrigatorio = "não" if _posicional_opcional(acao) else "sim"
        linhas.append((_forma(acao), obrigatorio, acao.help or ""))
    return linhas


def frontmatter(texto: str) -> dict[str, str]:
    """As linhas `chave: valor` entre a primeira linha `---` e a próxima, partidas no primeiro `": "`, sem as aspas
    iguais em volta do valor. As outras linhas ficam de fora; sem `---` na primeira linha, o dicionário vazio."""
    linhas = [linha.rstrip("\r") for linha in texto.split("\n")]
    if linhas[0] != "---":
        return {}
    dados = {}
    for linha in linhas[1:]:
        if linha == "---":
            break
        if ": " not in linha:
            continue
        chave, valor = linha.split(": ", 1)
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        dados[chave] = valor
    return dados


def _pode_usar_da_skill(ferramentas: str) -> tuple[str, ...]:
    """Os itens do `allowed-tools`: `harness.py <comando>` para o Bash do harness, a primeira palavra para outro Bash
    e o nome para as outras ferramentas; sem repetição, na ordem em que aparecem."""
    itens: list[str] = []
    for achado in _RE_FERRAMENTA.finditer(ferramentas):
        nome, dentro = achado.group(1), achado.group(2)
        if nome == "Bash" and dentro is not None and _HARNESS in dentro:
            palavras = dentro.split(_HARNESS, 1)[1].split()
            item = f"{_HARNESS} {palavras[0]}" if palavras else _HARNESS
        elif nome == "Bash" and dentro is not None and dentro.split():
            item = dentro.split()[0]
        else:
            item = nome
        if item not in itens:
            itens.append(item)
    return tuple(itens)


def _ler(arquivo: Path) -> str:
    """O texto em UTF-8. Fora de UTF-8 vira OSError com o caminho, e o comando sai com `erro de arquivo: ...`."""
    try:
        return arquivo.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise OSError(errno.EILSEQ, "não está em UTF-8", str(arquivo)) from None


def componentes(raiz: Path) -> list[Componente]:
    """As skills de `skills/*/SKILL.md` e os agentes de `agents/*.md` da raiz do plugin, ordenados por nome e tipo.
    Sem `name`, vale o nome da pasta da skill ou do arquivo do agente."""
    achados = []
    for arquivo in sorted((raiz / "skills").glob("*/SKILL.md")):
        dados = frontmatter(_ler(arquivo))
        achados.append(Componente(
            dados.get("name") or arquivo.parent.name, "skill", dados.get("description", ""),
            dados.get("argument-hint", ""), _pode_usar_da_skill(dados.get("allowed-tools", "")), dados.get("model", ""),
        ))
    for arquivo in sorted((raiz / "agents").glob("*.md")):
        dados = frontmatter(_ler(arquivo))
        ferramentas = tuple(item.strip() for item in dados.get("tools", "").split(",") if item.strip())
        achados.append(Componente(
            dados.get("name") or arquivo.stem, "agente", dados.get("description", ""), dados.get("argument-hint", ""),
            ferramentas, dados.get("model", ""),
        ))
    return sorted(achados, key=lambda componente: (componente.nome, componente.tipo))


def primeira_frase(docstring: str) -> str:
    """O primeiro parágrafo, com as quebras trocadas por espaço, até o primeiro `.` seguido de espaço ou do fim; sem
    ponto, o parágrafo inteiro."""
    paragrafo = docstring.split("\n\n", 1)[0].replace("\n", " ")
    achado = re.search(r"\.(?= |$)", paragrafo)
    return paragrafo[: achado.end()] if achado else paragrafo


def mapa(raiz: Path) -> list[tuple[str, str]]:
    """Cada `*.py` das pastas do núcleo da raiz do plugin, em ordem do caminho (`nucleo/comum/harness.py`), com a
    primeira frase da docstring; depois o `saida.md` e as PASTAS."""
    arquivos = [arquivo for pasta in caminho.PASTAS_DO_NUCLEO for arquivo in (raiz / "nucleo" / pasta).glob("*.py")]
    linhas = []
    for arquivo in sorted(arquivos, key=lambda item: item.relative_to(raiz).as_posix()):
        docstring = ast.get_docstring(ast.parse(_ler(arquivo))) or ""
        linhas.append((arquivo.relative_to(raiz).as_posix(), primeira_frase(docstring)))
    return [*linhas, (SAIDA, SAIDA_MD), *PASTAS]


def _texto(texto: str) -> str:
    """Célula de texto ou ajuda de uma linha: `<` vira `&lt;` fora das crases, e `|` vira `\\|`."""
    pedacos = texto.split("`")
    pedacos[::2] = [pedaco.replace("<", "&lt;") for pedaco in pedacos[::2]]
    return "`".join(pedacos).replace("|", "\\|")


def _codigo(texto: str) -> str:
    """Célula entre crases: só o `|` muda."""
    return "`" + texto.replace("|", "\\|") + "`"


def _tabela(cabecalho: tuple[str, ...], linhas: list[tuple[str, ...]]) -> str:
    return "\n".join([
        "| " + " | ".join(cabecalho) + " |",
        "|" + "---|" * len(cabecalho),
        *("| " + " | ".join(celulas) + " |" for celulas in linhas),
    ])


def _tabela_de_argumentos(parser: argparse.ArgumentParser) -> str:
    """A tabela de argumentos e opções, ou `""` sem linhas."""
    linhas = [
        (_codigo(nome), _texto(obrigatorio), _texto(ajuda)) for nome, obrigatorio, ajuda in linhas_da_tabela(parser)
    ]
    return _tabela(("Argumento ou opção", "Obrigatório", "O que é"), linhas) if linhas else ""


def _secao_de_comando(nome: str, ajuda: str, parser: argparse.ArgumentParser) -> list[str]:
    """`## <comando>`: a ajuda de uma linha, o uso, a tabela e a `description`; depois, cada ação em `###`, com a
    ajuda de uma linha, o uso e a tabela."""
    blocos = [
        f"## {nome}", _texto(ajuda), f"`{uso('harness.py ' + nome, parser)}`", _tabela_de_argumentos(parser),
        (parser.description or "").strip(),
    ]
    for acao, ajuda_da_acao, filho in subcomandos(parser):
        blocos += [
            f"### {nome} {acao}", _texto(ajuda_da_acao), f"`{uso(f'harness.py {nome} {acao}', filho)}`",
            _tabela_de_argumentos(filho),
        ]
    return blocos


def _linha_de_componente(componente: Componente) -> tuple[str, ...]:
    if componente.pode_usar:
        pode_usar = ", ".join(_codigo(item) for item in componente.pode_usar)
    else:
        pode_usar = "as da sessão" if componente.tipo == "agente" else _SEM_VALOR
    return (
        _codigo(componente.nome),
        _texto(componente.tipo),
        _texto(componente.quando) if componente.quando else _SEM_VALOR,
        _codigo(componente.argumento) if componente.argumento else _SEM_VALOR,
        pode_usar,
        _texto(componente.modelo) if componente.modelo else "o da sessão",
    )


def _parte_do_desenvolvimento(parser: argparse.ArgumentParser, parser_desenvolvimento: argparse.ArgumentParser
                              ) -> list[str]:
    """`## Comandos do desenvolvimento` (spec 6c, §5.1): a frase com os comandos comuns às duas trilhas, na ordem do
    parser do desenvolvimento, e a tabela e as seções dos que só ele tem, ou `Nenhum comando só desta trilha.`"""
    do_planejamento = {nome for nome, _, _ in subcomandos(parser)}
    comandos = subcomandos(parser_desenvolvimento)
    comuns = [f"[`{nome}`](#{nome})" for nome, _, _ in comandos if nome in do_planejamento]
    so_dele = [(nome, ajuda, filho) for nome, ajuda, filho in comandos if nome not in do_planejamento]
    frase = (
        'Com `harness = "desenvolvimento"` no `[projeto]` do perfil. Valem os comandos comuns às duas trilhas, '
        f"{comum.juntar(comuns)}, e os desta tabela."
    )
    tabela = _tabela(("Comando", "O que faz"), [(f"[`{nome}`](#{nome})", _texto(ajuda)) for nome, ajuda, _ in so_dele])
    blocos = ["## Comandos do desenvolvimento", frase, tabela if so_dele else "Nenhum comando só desta trilha."]
    for nome, ajuda, filho in so_dele:
        blocos += _secao_de_comando(nome, ajuda, filho)
    return blocos


def gerar(raiz: Path, parser: argparse.ArgumentParser, parser_desenvolvimento: argparse.ArgumentParser) -> str:
    """O Markdown da referência (spec 4c, §7.3, e 6c, §5.1): título e aviso, convenções, conceitos, comandos do
    planejamento, comandos do desenvolvimento, skills e agentes e mapa do núcleo, com os blocos separados por uma
    linha em branco e uma quebra de linha no fim."""
    comandos = subcomandos(parser)
    blocos = [
        "# Referência do harness", AVISO,
        "## Convenções", CONVENCOES.strip(),
        "## Conceitos", CONCEITOS.strip(),
        "## Comandos",
        _tabela(("Comando", "O que faz"), [(f"[`{nome}`](#{nome})", _texto(ajuda)) for nome, ajuda, _ in comandos]),
    ]
    for nome, ajuda, filho in comandos:
        blocos += _secao_de_comando(nome, ajuda, filho)
    blocos += _parte_do_desenvolvimento(parser, parser_desenvolvimento)
    linhas = [_linha_de_componente(componente) for componente in componentes(raiz)]
    cabecalho = ("Nome", "Tipo", "Quando usar", "Argumento", "O que pode usar", "Modelo")
    nucleo = [(_codigo(arquivo), _texto(texto)) for arquivo, texto in mapa(caminho.RAIZ_DO_PLUGIN)]
    blocos += [
        "## Skills e agentes", _tabela(cabecalho, linhas) if linhas else "nenhuma",
        "## Mapa do núcleo", _tabela(("Arquivo", "O que é"), nucleo),
    ]
    return "\n\n".join(bloco for bloco in blocos if bloco) + "\n"
