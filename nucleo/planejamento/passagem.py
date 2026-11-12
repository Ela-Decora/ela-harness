"""Passagem do planejamento ao código (spec 6b, §6 a §10): exportação, áreas do código, `areas-cobertas`, leitor
frio e publicação.

O `calcular` lê do commit, pelo git, a seleção, o fecho por link e o manifesto, em memória, com os avisos e as
recusas; o `gravar` grava a exportação numa pasta. As áreas vêm da tabela de `[passagem] areas` do perfil; o
`areas-cobertas` confere que todo "Onde vale" das regras de arquitetura cai em áreas da tabela. A mesma função dá a
falha do gate, o aviso do `exportar` e a recusa do `publicar`. O `leitor` exporta o HEAD para uma pasta temporária,
roda nela um `claude -p` preso a ela e grava as respostas no gabarito. O `publicar` commita o manifesto da exportação
do HEAD e cria a tag `passagem/vN`, só na máquina; o `enviar` empurra a tag e fecha as issues de retorno.
"""
from __future__ import annotations

import dataclasses
import json
import os
import posixpath
import re
import shlex
import shutil
import subprocess
import tempfile
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

import ambiente
import backlog
import checar
import comum
import dossie
import estado
import legenda
import manifesto
import rastreio
import regras
from manifesto import Area, Manifesto
from perfil import Perfil

AJUDA = """\
Exporta a passagem do planejamento ao código: `passagem exportar <pasta> [--ref <commit>]`. Pede `[passagem]` e
`caminhos.legenda` no perfil (`erro: perfil sem [passagem]`, `erro: perfil sem caminhos.legenda`).

Tudo vem do commit (`--ref`, ou o HEAD), lido pelo git como bytes do objeto, nunca do disco, e é calculado em memória
antes de gravar. Entram os artefatos da tabela do backlog do commit com status `aprovado`, ou `em-revisao` com linha nas
aprovações do arquivo de decisões, nas pastas das fases; a legenda; o DDL da pasta `[der] sql`, quando o
`[der] documento` está entre eles; e o fecho por link: cada link relativo de um `.md` copiado, sem a âncora, puxa o
destino, e o `.md` puxado é lido também, até não sobrar nada novo. O link com esquema e o só de âncora ficam de fora; o
caminho entre crases fica como texto.

Recusas, com saída 1 e nada gravado: `erro: <pasta> não está vazia`; `erro: git indisponível: <motivo>`;
`erro: <pasta> fica dentro de uma árvore git: <raiz>`; `erro: ref inválida: <ref>`; e, uma por link,
`<arquivo>:<linha>: link para <destino>: <motivo>`, em que o motivo é `fora do repositório`,
`excluído da passagem (<chave>)` (os caminhos de `[caminhos]` `rascunho`, `status`, `decisoes`, `backlog`, `estudos`,
`atritos` e `leitor_frio`, e a pasta `.claude`, ou o que fica dentro deles), `pasta` ou `ausente em <commit curto>`. O
`<destino>` é o texto do link como está escrito.

Avisos, com saída 0, que o `publicar` recusa: o link para um `.md` das pastas das fases fora da seleção, que não é
copiado (`<arquivo>:<linha>: link para <destino>: <status>`, ou `fora da tabela`); o ID definido duas vezes
(`<ID> definido em <a>:<n> e em <b>:<m>; vale o primeiro`, na ordem da tabela e das linhas); as falhas do
`areas-cobertas` (`areas-cobertas: <falha>`); a legenda ausente, recusada ou diferente da que o commit gera
(`legenda desatualizada em <commit curto>: rode harness.py legenda`); o artefato selecionado que falta no commit
(`<caminho> na tabela de artefatos e ausente em <commit curto>`); e o `em-revisao` sem aprovação, que fica de fora
(`<caminho> em revisão sem aprovação: fica de fora`).

A pasta, relativa ao diretório de onde o comando roda, recebe cada arquivo no mesmo caminho a partir da raiz do
repositório e o `manifesto.json`: o formato, a versão (`null` na exportação), a origem (o repositório do `origin`, o
commit, a data dele e o gatilho), o `sha256` de cada arquivo, o arquivo, as linhas e o `sha256` do trecho de cada ID dos
artefatos selecionados, as áreas do código da tabela de `[passagem] areas` e as pendências abertas citadas fora de bloco
de código. O mesmo commit dá os mesmos bytes. Saída: `exportados <n> arquivos, <m> IDs, <k> pendências em <pasta>`,
seguida dos avisos, cada um como `aviso: <aviso>`.

Testa pelo leitor frio: `passagem leitor <gabarito>`, com o gabarito a partir da raiz, ou absoluto. O gabarito fica
direto em `caminhos.leitor_frio`, com o nome `<gate>-<AAAA-MM-DD>.md` de um gate do perfil, e tem a seção
`## Gabarito` com itens numerados, cada um com os subitens `- Resposta:` e `- Fonte:`. Senão, sai com 1 e
`gabarito inválido: <motivo>`, sem rodar nada, com o primeiro destes motivos: `fora de <pasta>: <caminho>`,
`nome fora do formato <gate>-<AAAA-MM-DD>.md: <nome>`, `gate desconhecido: <gate>`, `arquivo ausente: <caminho>`,
`sem a seção ## Gabarito`, `## Gabarito sem itens numerados`, `item <n> sem - Resposta:` ou
`item <n> sem - Fonte:`.

O comando exporta o HEAD para uma pasta nova do `tempfile`, fora do repositório; a recusa da exportação sai com 1, como
`erro: exportação recusada` e uma recusa por linha, e o aviso só é impresso. Depois roda na pasta, com o ambiente sem
`CLAUDE_PROJECT_DIR` e limite de 900 s, o comando
`claude -p --restricted --safe-mode --tools Read,Grep,Glob --no-session-persistence --output-format json "<prompt>"`.
O prompt é uma frase fixa, que cita a legenda de `caminhos.legenda`, e as perguntas numeradas, cada uma com o texto
do item até o subitem `- Resposta:` ou `- Fonte:`, nunca as respostas nem as fontes. Erros, com saída 1 e o gabarito
sem mudar: `erro: claude indisponível: <motivo>`, `erro: leitor passou de 900 s`,
`erro: saída do leitor ilegível: JSON inválido`, `erro: saída do leitor ilegível: falta o campo <campo>` (o
`is_error` ou o `result`) e `erro: leitor falhou: <motivo>`: com `is_error` verdadeiro, o `result` ou o `subtype`,
ou `sem result`; com o `claude` saindo com código diferente de 0 e sem JSON, a primeira linha não vazia do stderr,
ou `claude -p saiu com <código>`.

As respostas saem do `result`: a linha sem recuo `<n>. ` ou `<n>) `, com o número em negrito ou não, de uma pergunta
ainda sem resposta abre a dela, e as outras seguem na aberta; a pergunta sem resposta fica `sem resposta`. O comando
troca a seção `## Resultado` do gabarito, até o próximo título de nível 1 ou 2, ou a acrescenta no fim. Ela tem a
linha `Exportação: <12 do commit> · formato <n> · sha256:<12 do hash da lista de arquivos>`, a linha `Leitor:` e,
por pergunta, `<n>. a corrigir` com a resposta em linhas `   > `; com alguma pergunta sem resposta, termina com a
linha `Saída inteira do leitor:` e o `result` em linhas `> `. A pasta é apagada também nos erros. Saída: os avisos,
como `aviso: <aviso>`, e a linha
`leitor: <s> s, <entrada> tokens de entrada, <saída> tokens de saída, US$ <custo>, <turnos> turnos, <k> negações`,
com cada negação abaixo, como `  <ferramenta>: <entrada em JSON>`.

Publica: `passagem publicar`, só na máquina, sem rede. Recusas, com saída 1, uma linha por recusa, na ordem, parando
no primeiro grupo que recusa: `publicar só na árvore principal: worktree <branch>`;
`publicar pede a árvore limpa: <k> arquivos alterados`, pelo `git status`; `publicar pede o remoto origin`;
`<documentos> em edição (passo <n>)`, com documento ou pacote no STATUS; `<caminho> com status <s>`, para cada artefato
das pastas das fases que não está `aprovado`; `primeira passagem só depois do <gate> aprovado`, sem tag
`passagem/vN` e com o último gate do perfil não aprovado; `nada a publicar: igual a passagem/v<n>`, com o hash da lista
de arquivos da exportação do HEAD igual ao do manifesto da última tag e nenhuma issue `retorno #<issue>` resolvida
desde ela; e as recusas e os avisos da exportação. O backlog ausente na última tag sai com
`erro: backlog ausente em passagem/v<n>`.

Depois, N é o maior `passagem/vN` mais 1, ou 1, e o gatilho é o último gate do perfil, sem tag, ou `revisão`. Na
revisão, as pendências resolvidas são as resolvidas no backlog do HEAD e não no da última tag, pelo número. O comando
grava o manifesto em `[passagem] manifesto`, com a versão, o commit do HEAD como origem, o gatilho e as pendências
resolvidas, e faz o commit só dele, `docs(passagem): passagem/vN (<gatilho>)`, com
`Pendências resolvidas desde passagem/v<N-1>: <IDs>.` no corpo quando há; o pre-commit roda. Na falha, o manifesto
volta ao do HEAD, e a recusa é `commit falhou: <motivo>`. Depois cria a tag anotada `passagem/vN` no commit novo, com o
gatilho, o commit de origem e as pendências resolvidas na mensagem, um parágrafo cada; na falha, a recusa é
`tag falhou: <motivo>; crie-a com git tag -a passagem/vN -m <...> -m <...> -m <...> <commit>`, o comando que cria a
mesma tag. Saída:
`passagem/vN pronta na máquina: commit <commit>, tag passagem/vN`;
`O envio empurra a tag passagem/vN e comenta e fecha: #<issue> (<pendências>), ...`, com as issues citadas como
`retorno #<issue>` em qualquer célula das pendências resolvidas desde a tag anterior, ou de todas as resolvidas na
primeira, uma vez cada, ou `... e não fecha nenhuma issue`, mais
`; só comenta: #<issue> (<pendências>, segue aberta pela <aberta>), ...` quando uma pendência aberta do backlog da
tag também cita a issue; e `Para enviar: harness.py passagem publicar --enviar vN`.

Envia: `passagem publicar --enviar vN`, só depois da confirmação do usuário. Cada recusa sai com 1, sem nada no
origin e sem mexer em issue: `erro: versão fora do formato vN: <valor>`, `passagem/vN não existe na máquina` e
`passagem/vN não é a última tag: passagem/v<m>`; depois, um `git ls-remote` traz as tags do `origin`, e cada tag da
máquina até a vN que está lá com outro sha que o da máquina (`git rev-parse refs/tags/passagem/vK`) dá
`a tag passagem/vK do origin é outra (<12 do origin>; na máquina, <12 da máquina>); confira antes de enviar`; a
falha do `ls-remote` dá `origin não consultado: <motivo>`.

Então, nesta ordem, com cada push por `git push origin refs/tags/passagem/vK`, com 60 s, e só a tag:
- cada vK que falta no origin, com K menor que N, em ordem crescente: primeiro as issues dela, com a tag anterior
  da máquina como base, e depois o push, com `tag passagem/vK enviada ao origin`. Qualquer falha numa vK, de issue
  ou do push, para o comando antes da tag seguinte, e a vK continua faltando no origin;
- a vN: o push, com `tag passagem/vN enviada ao origin`, ou `tag passagem/vN já estava no origin`; a falha é
  `push falhou: <motivo>` e para antes das issues; depois, as issues dela.

As issues de uma tag: uma vez por issue `retorno #N` das pendências resolvidas desde a tag anterior, calculadas
pelos backlogs das duas tags, ou de todas as resolvidas na primeira, cada `gh` na raiz com 30 s:
`gh issue view N --json state,comments`; aberta e sem pendência aberta da tag que a cite,
`gh issue close N --comment "Resolvida na passagem/vN pela <pendência>: <como>"`; aberta e citada por uma pendência
aberta, só `gh issue comment N --body "<corpo>"`, com o corpo `<pendência> resolvida na passagem/vN: <como>.` e
`A issue segue aberta pela <aberta>.`, sem ponto repetido. Com mais de uma pendência, as listas levam `e` antes da
última e o plural (`pelas`, `resolvidas`), e o `<como>` de cada resolvida vai numa linha `<pendência>: <como>`,
depois da frase. A issue fechada dá `#N já estava fechada (<pendências>)`, sem outro `gh`. A que já tem um
comentário igual ao corpo, sem os espaços das pontas e com o `\\r\\n` contado como `\\n`, não ganha outro: a que
fecha passa pelo `gh issue close N`, sem comentário, e dá `#N fechada (<pendências>); já comentada`; a outra dá
`#N já comentada (<pendências>); segue aberta pela <aberta>`, sem outro `gh`. As outras linhas:
`#N comentada e fechada (<pendências>)` e
`#N comentada; segue aberta pela <aberta> (<pendência> resolvida na passagem/vN)`, com as listas separadas por
vírgula; a falha, `#N: gh issue <view | close | comment> falhou: <motivo>`, segue para a próxima issue da tag. Com
alguma falha, sai com 1. Rodar de novo é seguro: a issue fechada e o comentário igual não se repetem, e a vK que
parou no meio volta a ser processada.
"""

_RE_TITULO = re.compile(r"(#{1,6}) (.*)")
_RE_CRASES = re.compile(r"`([^`]+)`")
# A regra de arquitetura no formato do núcleo: `RA-NN: <regra>. Onde vale: <áreas>. Como se confere: <como>.`
_RE_ONDE_VALE = re.compile(r"\bRA-[0-9]{2,}: .*?Onde vale: (.+?)\. Como se confere:")

TEMPO_LIMITE_GIT = 10
_SELECIONADOS = ("aprovado", "em-revisao")

TEMPO_LIMITE_LEITOR = 900
COMANDO_DO_LEITOR = (
    "claude", "-p", "--restricted", "--safe-mode", "--tools", "Read,Grep,Glob", "--no-session-persistence",
    "--output-format", "json",
)
# O `{legenda}` é o trecho da legenda do perfil, ou nada sem ela (`frase_do_leitor`).
FRASE_DO_LEITOR = (
    "Esta pasta é a exportação da passagem de um projeto. O `manifesto.json` diz em que arquivo e linhas está cada "
    "ID{legenda}. Responda só com o que achar nos arquivos desta pasta. Para cada pergunta, comece a linha pelo "
    "número dela e um ponto, dê a resposta e a fonte como `arquivo:linha`; se não achar, escreva `não achei`."
)
SEM_RESPOSTA = "sem resposta"
SAIDA_INTEIRA = "Saída inteira do leitor:"
A_CORRIGIR = "a corrigir"
_RE_NOME_DO_GABARITO = re.compile(r"(.+)-([0-9]{4}-[0-9]{2}-[0-9]{2})\.md")
_RE_NUMERO_DO_ITEM = re.compile(r"\s*([0-9]+)[.)]")
_RE_TITULO_ATE_2 = re.compile(r"#{1,2} ")
_RE_RESPOSTA = re.compile(r"^(\*\*)?([0-9]+)[.)](?(1)\*\*)\s+(.*)$")
_RE_EXPORTACAO = re.compile(r"^Exportação: ([0-9a-f]{12}) · formato ([0-9]+) · sha256:([0-9a-f]{12})$")
_RE_VEREDITO = re.compile(r"([0-9]+)\.\s+([^:]*)")
CERTA = "certa"

TEMPO_LIMITE_COMMIT = 60
TEMPO_LIMITE_PUSH = 60
TEMPO_LIMITE_GH = 30
_RE_TAG = re.compile(re.escape(manifesto.PREFIXO_TAG) + r"([1-9][0-9]*)")
_RE_RETORNO = re.compile(r"\b" + re.escape(manifesto.ROTULO_RETORNO) + r" #([0-9]+)\b")
_PREFIXO_RESOLVIDA = "resolvida"
_HISTORICO = "; histórico:"


class ErroPassagem(Exception):
    """A passagem não pode seguir. `mensagem` cabe numa linha."""

    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


class GabaritoInvalido(ErroPassagem):
    """O gabarito do leitor frio não serve; a mensagem é `gabarito inválido: <motivo>`."""

    def __init__(self, motivo: str):
        super().__init__(f"gabarito inválido: {motivo}")


class ExportacaoRecusada(ErroPassagem):
    """A exportação tem recusas, uma por item de `recusas`."""

    def __init__(self, recusas: tuple[str, ...]):
        super().__init__("exportação recusada")
        self.recusas = tuple(recusas)


def _documento_das_areas(perfil: Perfil) -> str:
    return f"{perfil.caminhos.planejamento.rstrip('/')}/{perfil.passagem.areas.documento}"


def ler_areas(ler: Callable[[str], str | None], perfil: Perfil) -> tuple[Area, ...] | None:
    """As áreas da tabela, na ordem das linhas, com as pastas entre crases da célula; None quando o documento, a
    seção ou a tabela não se acham.

    A seção é o primeiro título fora de bloco de código, de qualquer nível, cujo texto sem os `#` é a `secao`; a
    tabela é a primeira da seção com as duas colunas no cabeçalho.
    """
    areas = perfil.passagem.areas
    texto = ler(_documento_das_areas(perfil))
    if texto is None:
        return None
    linhas = checar.linhas_fora_de_blocos(texto)
    secao: list[tuple[int, str]] | None = None
    nivel = 0
    for numero, linha in linhas:
        titulo = _RE_TITULO.match(linha)
        if secao is None:
            if titulo and titulo.group(2).strip() == areas.secao:
                secao, nivel = [], len(titulo.group(1))
            continue
        if titulo and len(titulo.group(1)) <= nivel:
            break
        secao.append((numero, linha))
    if secao is None:
        return None
    for _, cabecalho, corpo in checar.tabelas(secao):
        if areas.coluna_area in cabecalho and areas.coluna_pastas in cabecalho:
            na_area, nas_pastas = cabecalho.index(areas.coluna_area), cabecalho.index(areas.coluna_pastas)
            return tuple(
                Area(celulas[na_area], tuple(_RE_CRASES.findall(celulas[nas_pastas])))
                for _, celulas in corpo
                if len(celulas) > max(na_area, nas_pastas)
            )
    return None


def areas_cobertas(ler: Callable[[str], str | None], perfil: Perfil) -> list[str]:
    """As falhas do `areas-cobertas`: a tabela não achada, ou cada regra de arquitetura do arquivo de
    `caminhos.adrs`, fora de bloco de código, com um "Onde vale" que não casa com as áreas da tabela."""
    areas = ler_areas(ler, perfil)
    if areas is None:
        return [f"tabela das áreas não achada: {_documento_das_areas(perfil)} § {perfil.passagem.areas.secao}"]
    adrs = perfil.caminhos.adrs
    texto = ler(adrs)
    if texto is None:
        return []
    nomes = sorted({area.area for area in areas}, key=len, reverse=True)
    falhas = []
    for numero, linha in checar.linhas_fora_de_blocos(texto):
        achado = _RE_ONDE_VALE.search(linha)
        resto = regras.casar(achado.group(1), nomes)[1] if achado else ""
        if resto:
            falhas.append(f"{adrs}:{numero}: área sem linha na tabela das áreas: {resto}")
    return falhas


def _git(raiz: Path, argumentos: list[str], executar, tempo: int = TEMPO_LIMITE_GIT) -> subprocess.CompletedProcess:
    """O git na raiz, com a saída em bytes; a falha ao rodar lança ErroPassagem com `git indisponível: <motivo>`."""
    try:
        return executar(["git", "-C", str(raiz), *argumentos], capture_output=True, timeout=tempo)
    except OSError as erro:
        raise ErroPassagem(f"git indisponível: {comum.motivo_do_sistema(erro)}") from None
    except subprocess.SubprocessError as erro:
        raise ErroPassagem(f"git indisponível: {type(erro).__name__}: {erro}") from None


class _Commit:
    """Leitura de um commit pelo git, como bytes do objeto: o sha, a data, o remoto e os arquivos."""

    def __init__(self, raiz: Path, ref: str, executar):
        self.raiz = raiz
        self._executar = executar
        self._cache: dict[str, bytes | None] = {}
        saida = self._git("rev-parse", "--verify", "-q", f"{ref}^{{commit}}")
        if saida.returncode != 0:
            raise ErroPassagem(f"ref inválida: {ref}")
        self.sha = saida.stdout.decode("utf-8").strip()
        self.curto = self.sha[:12]
        self.data = self._git("log", "-1", "--format=%cs", self.sha).stdout.decode("utf-8").strip()
        nomes = self._git("ls-tree", "-r", "-z", "--name-only", self.sha).stdout.split(b"\0")
        self.arquivos = frozenset(nome.decode("utf-8") for nome in nomes if nome)
        remoto = self._git("remote", "get-url", "origin")
        self.repositorio = (
            manifesto.repositorio_do_remoto(remoto.stdout.decode("utf-8").strip()) if remoto.returncode == 0 else ""
        )

    def _git(self, *argumentos: str) -> subprocess.CompletedProcess:
        return _git(self.raiz, list(argumentos), self._executar)

    def dados(self, caminho: str) -> bytes | None:
        """Os bytes do arquivo no commit; None se ele não está lá."""
        if caminho not in self.arquivos:
            return None
        if caminho not in self._cache:
            saida = self._git("cat-file", "blob", f"{self.sha}:{caminho}")
            self._cache[caminho] = saida.stdout if saida.returncode == 0 else None
        return self._cache[caminho]

    def ler(self, caminho: str) -> str | None:
        """O texto UTF-8 do arquivo no commit; None se ele não está lá ou não é UTF-8."""
        dados = self.dados(caminho)
        try:
            return None if dados is None else dados.decode("utf-8")
        except UnicodeDecodeError:
            return None


@dataclass(frozen=True)
class Exportacao:
    """O que a exportação gravaria: o manifesto, os bytes de cada arquivo pelo caminho a partir da raiz, os avisos e
    as recusas, os dois sem o prefixo."""

    manifesto: Manifesto
    arquivos: dict[str, bytes]
    avisos: list[str]
    recusas: list[str]


def conferir_perfil(perfil: Perfil) -> None:
    """O perfil tem a `[passagem]` e o `caminhos.legenda`, nessa ordem."""
    if perfil.passagem is None:
        raise ErroPassagem("perfil sem [passagem]")
    if not perfil.caminhos.legenda:
        raise ErroPassagem("perfil sem caminhos.legenda")


def conferir_pasta(pasta: Path, executar=subprocess.run) -> None:
    """A pasta não existe ou está vazia e fica fora de toda árvore git. A mensagem mostra a pasta como veio."""
    if pasta.exists() and (not pasta.is_dir() or any(pasta.iterdir())):
        raise ErroPassagem(f"{pasta} não está vazia")
    ancestral = pasta
    while not ancestral.exists() and ancestral != ancestral.parent:
        ancestral = ancestral.parent
    try:
        saida = executar(["git", "-C", str(ancestral), "rev-parse", "--show-toplevel"],
                         capture_output=True, timeout=TEMPO_LIMITE_GIT)
    except (OSError, subprocess.SubprocessError):
        return
    if saida.returncode == 0:
        raise ErroPassagem(f"{pasta} fica dentro de uma árvore git: {saida.stdout.decode('utf-8').strip()}")


def _plural(quantidade: int, singular: str, plural: str) -> str:
    return f"{quantidade} {singular if quantidade == 1 else plural}"


def resumo(exportacao: Exportacao, pasta: Path) -> str:
    """A linha da saída do `exportar`, com o número em concordância."""
    m = exportacao.manifesto
    return (f"exportados {_plural(len(m.arquivos), 'arquivo', 'arquivos')}, {_plural(len(m.ids), 'ID', 'IDs')}, "
            f"{_plural(len(m.pendencias), 'pendência', 'pendências')} em {pasta}")


def _pendencias_citadas(texto_backlog: str, textos: dict[str, str], perfil: Perfil) -> tuple[manifesto.Pendencia, ...]:
    """As pendências abertas do backlog citadas, fora de bloco de código, nos `.md` exportados, pela ordem do
    número; o ID e o texto vêm do backlog, e o número casa com zeros a mais."""
    abertas: dict[int, tuple[str, str]] = {}
    for _, celulas in backlog._pendencias(texto_backlog, perfil):
        numero = re.search(r"([0-9]+)$", celulas[0])
        if len(celulas) > 2 and celulas[-1].startswith(backlog.PREFIXO_ABERTA) and numero:
            abertas.setdefault(int(numero.group(1)), (celulas[0], celulas[1]))
    citacao = re.compile(rf"\b{re.escape(perfil.ids.prefixo_pendencia)}-0*([0-9]+)\b")
    citadas: dict[int, list[str]] = {}
    for caminho in sorted(textos):
        for _, linha in checar.linhas_fora_de_blocos(textos[caminho]):
            for achado in citacao.finditer(linha):
                numero = int(achado.group(1))
                if numero in abertas and caminho not in citadas.setdefault(numero, []):
                    citadas[numero].append(caminho)
    return tuple(
        manifesto.Pendencia(abertas[numero][0], abertas[numero][1], tuple(citadas[numero]))
        for numero in sorted(citadas)
    )


def calcular(raiz: Path, perfil: Perfil, ref: str = "HEAD", executar=subprocess.run) -> Exportacao:
    """A exportação do commit `ref`, calculada em memória: os artefatos `aprovado` e `em-revisao` das pastas das
    fases, a legenda, o DDL do `[der]` com o documento dele selecionado e o fecho por link. Lança ErroPassagem."""
    conferir_perfil(perfil)
    commit = _Commit(raiz, ref, executar)
    texto_backlog = commit.ler(perfil.caminhos.backlog) or ""
    pasta = perfil.caminhos.planejamento.rstrip("/")
    tabela = sorted(
        (linha, caminho, status)
        for fase in perfil.fases
        for linha, caminho, status in backlog.artefatos_da_pasta(texto_backlog, f"{pasta}/{fase.id}")
    )
    status_na_tabela = {caminho: status for _, caminho, status in reversed(tabela)}
    # O passo 5 grava em-revisao também no documento novo: sem aprovação no arquivo de decisões, ele fica de fora.
    decisoes = commit.ler(perfil.caminhos.decisoes) or ""
    selecionados = []
    ausentes = []
    sem_aprovacao = []
    for _, caminho, status in tabela:
        grupo = rastreio.grupo_do_status(status)
        if grupo not in _SELECIONADOS or caminho in selecionados or caminho in sem_aprovacao:
            continue
        if grupo == "em-revisao" and not dossie.data_da_aprovacao(decisoes, caminho):
            sem_aprovacao.append(caminho)
        else:
            (selecionados if caminho in commit.arquivos else ausentes).append(caminho)
    extras = []
    if perfil.caminhos.legenda in commit.arquivos:
        extras.append(perfil.caminhos.legenda)
    if perfil.der is not None and f"{pasta}/{perfil.der.documento}" in selecionados:
        sql = f"{pasta}/{perfil.der.sql}/"
        extras += [caminho for caminho in commit.arquivos if caminho.startswith(sql)]
    copiados = list(dict.fromkeys(selecionados + sorted(extras)))

    avisos_de_link: list[str] = []
    recusas: list[str] = []
    fila = deque(caminho for caminho in copiados if caminho.endswith(".md"))
    pastas_das_fases = [f"{pasta}/{fase.id}/" for fase in perfil.fases]
    while fila:
        origem = fila.popleft()
        texto = commit.ler(origem)
        if texto is None:
            continue
        for linha, escrito in checar.ler_links(texto):
            destino = checar.resolver_link(escrito, origem)
            if destino is None:
                continue
            inicio = f"{origem}:{linha}: link para {escrito}: "
            recusa = checar.recusa_do_link(destino, perfil, lambda d: d in commit.arquivos,
                                           lambda d: any(a.startswith(d + "/") for a in commit.arquivos))
            if recusa:
                recusas.append(inicio + (f"ausente em {commit.curto}" if recusa == checar.LINK_AUSENTE else recusa))
            elif (destino.endswith(".md") and destino not in copiados
                  and any(destino.startswith(p) for p in pastas_das_fases)):
                avisos_de_link.append(inicio + rastreio.grupo_do_status(status_na_tabela.get(destino)))
            elif destino not in copiados:
                copiados.append(destino)
                if destino.endswith(".md"):
                    fila.append(destino)

    ids: dict[str, manifesto.Definicao] = {}
    onde: dict[str, tuple[str, int]] = {}
    avisos_de_id = []
    for caminho in selecionados:
        texto = commit.ler(caminho)
        if texto is None:
            continue
        for linha, id_ in checar.ids_definidos(texto, perfil):
            if id_ in onde:
                primeiro, n = onde[id_]
                avisos_de_id.append(f"{id_} definido em {primeiro}:{n} e em {caminho}:{linha}; vale o primeiro")
                continue
            onde[id_] = (caminho, linha)
            ids[id_] = manifesto.definicao(caminho, texto, linha)

    areas = ler_areas(commit.ler, perfil) or ()
    avisos_de_area = [f"areas-cobertas: {falha}" for falha in areas_cobertas(commit.ler, perfil)]

    legenda_em_dia = False
    if perfil.caminhos.legenda in commit.arquivos:
        try:
            gerada = legenda.gerar(commit.ler, perfil)
        except legenda.LegendaRecusada:
            gerada = None
        legenda_em_dia = gerada is not None and commit.dados(perfil.caminhos.legenda) == gerada.encode("utf-8")
    aviso_de_legenda = [] if legenda_em_dia else [
        f"legenda desatualizada em {commit.curto}: rode harness.py legenda"
    ]
    avisos_de_ausente = [f"{caminho} na tabela de artefatos e ausente em {commit.curto}" for caminho in ausentes]
    avisos_de_ausente += [f"{caminho} em revisão sem aprovação: fica de fora" for caminho in sem_aprovacao]

    arquivos = {caminho: commit.dados(caminho) for caminho in sorted(copiados)}
    textos = {}
    for caminho in arquivos:
        texto = commit.ler(caminho) if caminho.endswith(".md") else None
        if texto is not None:
            textos[caminho] = texto
    m = Manifesto(
        manifesto.FORMATO,
        None,
        manifesto.Origem(commit.repositorio, commit.sha, commit.data, manifesto.GATILHO_EXPORTACAO),
        tuple(manifesto.Arquivo(caminho, manifesto.sha256(dados)) for caminho, dados in arquivos.items()),
        ids,
        areas,
        _pendencias_citadas(texto_backlog, textos, perfil),
    )
    avisos = avisos_de_link + avisos_de_id + avisos_de_area + aviso_de_legenda + avisos_de_ausente
    return Exportacao(m, arquivos, avisos, recusas)


def gravar(exportacao: Exportacao, pasta: Path) -> None:
    """Cria a pasta e grava cada arquivo no caminho dele a partir da raiz, e o manifesto."""
    pasta.mkdir(parents=True, exist_ok=True)
    for caminho, dados in exportacao.arquivos.items():
        destino = pasta / caminho
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(dados)
    (pasta / manifesto.NOME).write_bytes(manifesto.para_json(exportacao.manifesto).encode("utf-8"))


@dataclass(frozen=True)
class Pergunta:
    numero: int
    texto: str


@dataclass(frozen=True)
class Gabarito:
    """O gabarito do leitor frio: o caminho a partir da raiz, o gate, a data do nome e as perguntas."""

    caminho: str
    gate: str
    data: str
    perguntas: tuple[Pergunta, ...]


@dataclass(frozen=True)
class Leitura:
    """A rodada do leitor: as respostas por número de pergunta e as medições do JSON do `claude`, 0 quando faltam."""

    respostas: dict[int, str]
    segundos: float
    entrada: int
    saida: int
    custo: float
    turnos: int
    negacoes: tuple[str, ...]
    resultado: str = ""


def _secao(texto: str, titulo: str) -> list[tuple[int, str]] | None:
    """As linhas fora de bloco de código da seção com o título exato, até o próximo título de nível 1 ou 2."""
    linhas = checar.linhas_fora_de_blocos(texto)
    for posicao, (_, linha) in enumerate(linhas):
        if linha.rstrip() == titulo:
            fim = next((k for k in range(posicao + 1, len(linhas)) if _RE_TITULO_ATE_2.match(linhas[k][1])),
                       len(linhas))
            return linhas[posicao + 1:fim]
    return None


def _caminho_do_gabarito(raiz: Path, pasta: str, caminho: str) -> str:
    """O caminho a partir da raiz, do relativo ou do absoluto; fora da pasta dos gabaritos lança GabaritoInvalido."""
    bruto = Path(caminho)
    relativo: str | None = posixpath.normpath(bruto.as_posix())
    if bruto.is_absolute():
        try:
            relativo = bruto.resolve().relative_to(raiz.resolve()).as_posix()
        except ValueError:
            relativo = None
    if relativo is None or posixpath.dirname(relativo) != pasta:
        raise GabaritoInvalido(f"fora de {pasta}: {caminho}")
    return relativo


def ler_gabarito(raiz: Path, perfil: Perfil, caminho: str) -> Gabarito:
    """O gabarito do caminho, conferido na ordem do AJUDA; lança GabaritoInvalido, ou ErroPassagem sem
    `caminhos.leitor_frio` no perfil.

    As perguntas são os itens numerados da seção `## Gabarito` no recuo do primeiro; o texto vai até o subitem
    `- Resposta:` ou `- Fonte:`, com as linhas de continuação juntadas por um espaço.
    """
    pasta = perfil.caminhos.leitor_frio.rstrip("/")
    if not pasta:
        raise ErroPassagem("perfil sem caminhos.leitor_frio")
    relativo = _caminho_do_gabarito(raiz, pasta, caminho)
    nome = posixpath.basename(relativo)
    partes = _RE_NOME_DO_GABARITO.fullmatch(nome)
    if not partes or not comum.data_valida(partes.group(2)):
        raise GabaritoInvalido(f"nome fora do formato <gate>-<AAAA-MM-DD>.md: {nome}")
    gate = partes.group(1)
    if gate not in perfil.gates:
        raise GabaritoInvalido(f"gate desconhecido: {gate}")
    try:
        texto = comum.ler_texto(raiz / relativo)
    except (OSError, UnicodeDecodeError):
        raise GabaritoInvalido(f"arquivo ausente: {relativo}") from None
    secao = _secao(texto, "## Gabarito")
    if secao is None:
        raise GabaritoInvalido("sem a seção ## Gabarito")
    itens: list[list] = []  # [número, partes do texto, tem Resposta, tem Fonte, texto fechado]
    base: int | None = None
    for _, linha in secao:
        if not linha.strip():
            continue
        recuo = len(linha) - len(linha.lstrip())
        item = checar._RE_ITEM_DE_LISTA.fullmatch(linha)
        numero = _RE_NUMERO_DO_ITEM.match(linha) if item else None
        if numero and (base is None or recuo <= base):
            base = recuo if base is None else base
            itens.append([int(numero.group(1)), [(item.group(2) or "").strip()], False, False, False])
            continue
        if not itens or base is None or recuo <= base:
            continue
        atual = itens[-1]
        conteudo = (item.group(2) or "").strip() if item and not numero else ""
        if conteudo.startswith("Resposta:"):
            atual[2] = atual[4] = True
        elif conteudo.startswith("Fonte:"):
            atual[3] = atual[4] = True
        elif not atual[4]:
            atual[1].append(linha.strip())
    if not itens:
        raise GabaritoInvalido("## Gabarito sem itens numerados")
    for numero, _, resposta, fonte, _ in itens:
        if not resposta:
            raise GabaritoInvalido(f"item {numero} sem - Resposta:")
        if not fonte:
            raise GabaritoInvalido(f"item {numero} sem - Fonte:")
    perguntas = tuple(Pergunta(numero, " ".join(parte for parte in partes if parte)) for numero, partes, *_ in itens)
    return Gabarito(relativo, gate, partes.group(2), perguntas)


def frase_do_leitor(perfil: Perfil) -> str:
    """A frase fixa do prompt, com a legenda de `caminhos.legenda`, que a exportação leva; sem ela, sem o trecho."""
    legenda = perfil.caminhos.legenda
    trecho = f"; o `{legenda}` expande as siglas e os tipos de ID" if legenda else ""
    return FRASE_DO_LEITOR.format(legenda=trecho)


def prompt(gabarito: Gabarito, perfil: Perfil) -> str:
    """A frase fixa, uma linha vazia e as perguntas, uma por linha, como `<n>. <texto>`."""
    return frase_do_leitor(perfil) + "\n\n" + "\n".join(f"{p.numero}. {p.texto}" for p in gabarito.perguntas)


def separar_respostas(resultado: str, numeros: tuple[int, ...]) -> dict[int, str]:
    """A resposta de cada número, na ordem de `numeros`: a linha sem recuo `<n>. ` ou `<n>) `, com o número em
    negrito ou não, de uma pergunta ainda sem resposta abre a dela, e as outras seguem na aberta, sem as vazias do fim;
    as de antes da primeira saem."""
    respostas: dict[int, list[str]] = {}
    aberta: list[str] | None = None
    for linha in resultado.splitlines():
        achado = _RE_RESPOSTA.match(linha)
        if achado and int(achado.group(2)) in numeros and int(achado.group(2)) not in respostas:
            aberta = respostas[int(achado.group(2))] = [achado.group(3)]
        elif aberta is not None:
            aberta.append(linha)
    separadas = {}
    for numero in numeros:
        linhas = respostas.get(numero)
        if linhas is None:
            separadas[numero] = SEM_RESPOSTA
            continue
        while linhas and not linhas[-1].strip():
            linhas.pop()
        separadas[numero] = "\n".join(linhas)
    return separadas


def _numero(dados: dict, chave: str) -> float:
    valor = dados.get(chave)
    return valor if isinstance(valor, (int, float)) and not isinstance(valor, bool) else 0


def consultar_leitor(pasta: Path, texto: str, numeros: tuple[int, ...], executar=subprocess.run,
                     ambiente: Mapping[str, str] | None = None) -> Leitura:
    """Roda o `claude -p` preso à pasta com o prompt e lê o JSON dele; lança ErroPassagem. O processo filho recebe o
    ambiente (o `os.environ`, sem `ambiente`) menos `CLAUDE_PROJECT_DIR`."""
    filho = dict(os.environ if ambiente is None else ambiente)
    filho.pop("CLAUDE_PROJECT_DIR", None)
    try:
        feito = executar([*COMANDO_DO_LEITOR, texto], cwd=str(pasta), env=filho, capture_output=True,
                         timeout=TEMPO_LIMITE_LEITOR)
    except OSError as erro:
        raise ErroPassagem(f"claude indisponível: {comum.motivo_do_sistema(erro)}") from None
    except subprocess.TimeoutExpired:
        raise ErroPassagem(f"leitor passou de {TEMPO_LIMITE_LEITOR} s") from None
    saida = feito.stdout.decode("utf-8", errors="replace") if isinstance(feito.stdout, bytes) else feito.stdout or ""
    try:
        dados = json.loads(saida)
    except ValueError:
        if feito.returncode != 0:
            raise ErroPassagem(f"leitor falhou: {comum.motivo_do_git(feito, '-p', 'claude')}") from None
        raise ErroPassagem("saída do leitor ilegível: JSON inválido") from None
    if not isinstance(dados, dict):
        dados = {}
    if "is_error" not in dados:
        raise ErroPassagem("saída do leitor ilegível: falta o campo is_error")
    if dados["is_error"]:
        motivo = next((dados[chave] for chave in ("result", "subtype")
                       if isinstance(dados.get(chave), str) and dados[chave]), "sem result")
        raise ErroPassagem(f"leitor falhou: {motivo}")
    if "result" not in dados:
        raise ErroPassagem("saída do leitor ilegível: falta o campo result")
    resultado = dados["result"] if isinstance(dados["result"], str) else json.dumps(dados["result"])
    uso = dados.get("usage") if isinstance(dados.get("usage"), dict) else {}
    entrada = sum(int(_numero(uso, chave))
                  for chave in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    negadas = dados.get("permission_denials")
    negacoes = tuple(
        f"{negada.get('tool_name', '')}: {json.dumps(negada.get('tool_input', {}), ensure_ascii=False, sort_keys=True)}"
        for negada in (negadas if isinstance(negadas, list) else []) if isinstance(negada, dict)
    )
    return Leitura(separar_respostas(resultado, numeros), _numero(dados, "duration_ms") / 1000, entrada,
                   int(_numero(uso, "output_tokens")), _numero(dados, "total_cost_usd"), int(_numero(dados, "num_turns")),
                   negacoes, resultado)


def linha_da_exportacao(exportacao: Exportacao) -> str:
    """A linha `Exportação:` do Resultado: o commit, o formato e o hash da lista de arquivos, os dois em 12 dígitos."""
    m = exportacao.manifesto
    return (f"Exportação: {m.origem.commit[:12]} · formato {m.formato} · "
            f"sha256:{manifesto.hash_dos_arquivos(m.arquivos)[:12]}")


def _decimal(valor: float, casas: int) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _medidas(leitura: Leitura, com_entrada: bool) -> str:
    entrada = f"{leitura.entrada} tokens de entrada, " if com_entrada else ""
    return (f"{_decimal(leitura.segundos, 1)} s, {entrada}{leitura.saida} tokens de saída, "
            f"US$ {_decimal(leitura.custo, 4)}, {_plural(leitura.turnos, 'turno', 'turnos')}, "
            f"{_plural(len(leitura.negacoes), 'negação', 'negações')}")


def linha_do_leitor(leitura: Leitura) -> str:
    """A linha `Leitor:` do Resultado, sem os tokens de entrada."""
    return f"Leitor: {_medidas(leitura, False)}"


def formatar_leitura(leitura: Leitura) -> str:
    """A linha `leitor:` da saída do comando e uma linha por negação, com dois espaços, cada uma com a quebra."""
    return f"leitor: {_medidas(leitura, True)}\n" + "".join(f"  {negacao}\n" for negacao in leitura.negacoes)


def secao_resultado(linha_exportacao: str, leitura: Leitura) -> str:
    """A seção `## Resultado` com `a corrigir` em cada pergunta e a resposta em linhas `   > `; com alguma pergunta
    sem resposta, no fim, a saída inteira do leitor em linhas `> `."""
    linhas = ["## Resultado", linha_exportacao, linha_do_leitor(leitura)]
    for numero, resposta in leitura.respostas.items():
        linhas.append(f"{numero}. {A_CORRIGIR}")
        linhas += [f"   > {linha}" if linha.strip() else "   >" for linha in resposta.splitlines() or [""]]
    if SEM_RESPOSTA in leitura.respostas.values() and leitura.resultado:
        linhas.append(SAIDA_INTEIRA)
        linhas += [f"> {linha}" if linha.strip() else ">" for linha in leitura.resultado.splitlines()]
    return "\n".join(linhas) + "\n"


def trocar_resultado(texto: str, secao: str) -> str:
    """O texto com a seção `## Resultado` trocada, do título até o próximo título de nível 1 ou 2, fora de bloco de
    código, ou o fim; sem ela, a seção entra no fim, depois de uma linha vazia."""
    linhas = texto.splitlines(keepends=True)
    fora = checar.linhas_fora_de_blocos(texto)
    inicio = next((numero for numero, linha in fora if linha.rstrip() == "## Resultado"), None)
    if inicio is None:
        return texto.rstrip("\n") + "\n\n" + secao
    fim = next((numero for numero, linha in fora if numero > inicio and _RE_TITULO_ATE_2.match(linha)), None)
    depois = "" if fim is None else "\n" + "".join(linhas[fim - 1:])
    return "".join(linhas[:inicio - 1]) + secao + depois


def leitor(raiz: Path, perfil: Perfil, caminho: str, executar=subprocess.run,
           ambiente: Mapping[str, str] | None = None) -> tuple[Leitura, list[str]]:
    """O teste do leitor frio (spec 6b, §8.1): confere o gabarito, exporta o HEAD para uma pasta temporária, roda o
    leitor nela e troca o Resultado do gabarito. Devolve a leitura e os avisos da exportação; lança
    GabaritoInvalido, ExportacaoRecusada ou ErroPassagem. A pasta é apagada também nos erros."""
    gabarito = ler_gabarito(raiz, perfil, caminho)
    exportacao = calcular(raiz, perfil, "HEAD", executar)
    if exportacao.recusas:
        raise ExportacaoRecusada(tuple(exportacao.recusas))
    pasta = Path(tempfile.mkdtemp(prefix="leitor-frio-"))
    try:
        gravar(exportacao, pasta)
        numeros = tuple(pergunta.numero for pergunta in gabarito.perguntas)
        leitura = consultar_leitor(pasta, prompt(gabarito, perfil), numeros, executar, ambiente)
        destino = raiz / gabarito.caminho
        secao = secao_resultado(linha_da_exportacao(exportacao), leitura)
        comum.escrever_texto(destino, trocar_resultado(comum.ler_texto(destino), secao))
    finally:
        shutil.rmtree(pasta, ignore_errors=True)
    return leitura, list(exportacao.avisos)


def gabarito_mais_recente(raiz: Path, perfil: Perfil, gate: str) -> str | None:
    """O caminho, a partir da raiz, do gabarito do gate de data mais recente em `caminhos.leitor_frio`: os nomes
    `<gate>-<AAAA-MM-DD>.md` com data válida; None sem nenhum, ou sem a pasta."""
    pasta = perfil.caminhos.leitor_frio.rstrip("/")
    padrao = re.compile(re.escape(gate) + r"-([0-9]{4}-[0-9]{2}-[0-9]{2})\.md")
    try:
        nomes = [entrada.name for entrada in (raiz / pasta).iterdir() if entrada.is_file()]
    except OSError:
        return None
    datados = []
    for nome in nomes:
        achado = padrao.fullmatch(nome)
        if achado and comum.data_valida(achado.group(1)):
            datados.append((achado.group(1), nome))
    return f"{pasta}/{max(datados)[1]}" if datados and pasta else None


@dataclass(frozen=True)
class ResultadoDoLeitor:
    """A seção `## Resultado` lida: o commit, o formato e o hash da linha Exportação, e o veredito de cada item."""

    commit: str
    formato: int
    sha: str
    vereditos: dict[int, str]


def ler_resultado(texto: str) -> ResultadoDoLeitor | None:
    """A seção `## Resultado` do gabarito; None sem ela. A primeira linha não vazia é a Exportação, e lança
    ErroPassagem fora do formato. O veredito de cada item é o texto da linha `<n>. ` sem recuo até o primeiro `:`;
    vale a primeira linha de cada número."""
    secao = _secao(texto, "## Resultado")
    if secao is None:
        return None
    linhas = [linha for _, linha in secao if linha.strip()]
    exportacao = _RE_EXPORTACAO.fullmatch(linhas[0].rstrip()) if linhas else None
    if exportacao is None:
        raise ErroPassagem("linha Exportação fora do formato")
    vereditos: dict[int, str] = {}
    for linha in linhas[1:]:
        achado = _RE_VEREDITO.match(linha)
        if achado:
            vereditos.setdefault(int(achado.group(1)), achado.group(2).strip())
    return ResultadoDoLeitor(exportacao.group(1), int(exportacao.group(2)), exportacao.group(3), vereditos)


def falha_do_leitor(raiz: Path, perfil: Perfil, gate: str, executar=subprocess.run) -> str:
    """A primeira falha do item `leitor-frio` do gate, pelo gabarito mais recente, ou vazio no PASS: todo item do
    Gabarito `certa`, o formato atual e a exportação do HEAD igual à do Resultado."""
    caminho = gabarito_mais_recente(raiz, perfil, gate)
    if caminho is None:
        return f"sem gabarito de {gate} em {perfil.caminhos.leitor_frio.rstrip('/')}"
    try:
        gabarito = ler_gabarito(raiz, perfil, caminho)
        resultado = ler_resultado(comum.ler_texto(raiz / caminho))
    except ErroPassagem as erro:
        return f"{caminho}: {erro.mensagem}"
    except (OSError, UnicodeDecodeError):
        return f"{caminho}: {GabaritoInvalido(f'arquivo ausente: {caminho}').mensagem}"
    if resultado is None:
        return f"{caminho}: sem Resultado"
    if resultado.formato != manifesto.FORMATO:
        return f"{caminho}: formato {resultado.formato}, atual {manifesto.FORMATO}"
    try:
        exportacao = calcular(raiz, perfil, "HEAD", executar)
    except ErroPassagem as erro:
        return f"{caminho}: exportação falhou: {erro.mensagem}"
    if exportacao.recusas:
        return f"{caminho}: exportação recusada: {exportacao.recusas[0]}"
    if manifesto.hash_dos_arquivos(exportacao.manifesto.arquivos)[:12] != resultado.sha:
        return f"{caminho}: exportação desatualizada; rode harness.py passagem leitor {caminho}"
    nao_certos = [str(p.numero) for p in gabarito.perguntas if resultado.vereditos.get(p.numero) != CERTA]
    if len(nao_certos) == 1:
        return f"{caminho}: item {nao_certos[0]} não certo"
    if nao_certos:
        return f"{caminho}: itens {comum.juntar(nao_certos)} não certos"
    return ""


@dataclass(frozen=True)
class Retorno:
    """A issue de retorno: as pendências resolvidas que a citam, com o `<como>` do status de cada, e as abertas que
    também a citam."""

    issue: int
    resolvidas: tuple[tuple[str, str], ...]
    abertas: tuple[str, ...] = ()

    @property
    def pendencias(self) -> tuple[str, ...]:
        """Os IDs das resolvidas."""
        return tuple(id_ for id_, _ in self.resolvidas)

    @property
    def fecha(self) -> bool:
        """A issue fecha: nenhuma pendência aberta a cita."""
        return not self.abertas


@dataclass(frozen=True)
class Publicada:
    versao: int
    commit: str
    gatilho: str
    retornos: tuple[Retorno, ...]


class PublicacaoRecusada(ErroPassagem):
    """O `publicar` recusa, com uma linha por recusa em `linhas`."""

    def __init__(self, linhas: tuple[str, ...]):
        super().__init__(linhas[0])
        self.linhas = tuple(linhas)


def tags(raiz: Path, executar=subprocess.run) -> list[int]:
    """Os N das tags `passagem/vN` da máquina, em ordem; lança ErroPassagem."""
    feito = _git(raiz, ["tag", "--list", f"{manifesto.PREFIXO_TAG}*"], executar)
    if feito.returncode != 0:
        raise ErroPassagem(comum.motivo_do_git(feito, "tag"))
    numeros = []
    for linha in (feito.stdout or b"").decode("utf-8", errors="replace").splitlines():
        achado = _RE_TAG.fullmatch(linha.strip())
        if achado:
            numeros.append(int(achado.group(1)))
    return sorted(numeros)


def retornos_citados(linha: str) -> list[int]:
    """As issues citadas como `retorno #N` na linha, pelo número inteiro, na ordem, sem repetir."""
    return list(dict.fromkeys(int(numero) for numero in _RE_RETORNO.findall(linha)))


def _resolvidas(texto: str, perfil: Perfil) -> dict[int, tuple[str, list[str]]]:
    """As pendências com status `resolvida...` pelo número do ID: o ID e as células; vale a primeira linha."""
    resolvidas: dict[int, tuple[str, list[str]]] = {}
    for _, celulas in backlog._pendencias(texto, perfil):
        numero = re.search(r"([0-9]+)$", celulas[0])
        if numero and len(celulas) > 1 and celulas[-1].startswith(_PREFIXO_RESOLVIDA):
            resolvidas.setdefault(int(numero.group(1)), (celulas[0], celulas))
    return resolvidas


def _novas(atual: str, anterior: str | None, perfil: Perfil) -> list[tuple[str, list[str]]]:
    agora = _resolvidas(atual, perfil)
    antes = {} if anterior is None else _resolvidas(anterior, perfil)
    return [agora[numero] for numero in sorted(agora) if numero not in antes]


def resolvidas_desde(atual: str, anterior: str | None, perfil: Perfil) -> list[str]:
    """Os IDs resolvidos no backlog `atual` e não no `anterior`, casados pelo número, na ordem do número; com
    `anterior` None, todos os resolvidos."""
    return [id_ for id_, _ in _novas(atual, anterior, perfil)]


def _como(status: str) -> str:
    """O status depois do primeiro `: `, sem o `; histórico: ...`; sem `: `, o status inteiro."""
    status = status.split(_HISTORICO, 1)[0]
    return (status.split(": ", 1)[1] if ": " in status else status).strip()


def _abertas(texto: str, perfil: Perfil) -> dict[int, list[str]]:
    """As pendências abertas que citam cada issue `retorno #N` em qualquer célula, na ordem do backlog."""
    abertas: dict[int, list[str]] = {}
    for _, celulas in backlog._pendencias(texto, perfil):
        if len(celulas) > 1 and celulas[-1].startswith(backlog.PREFIXO_ABERTA):
            for issue in retornos_citados(" | ".join(celulas)):
                if celulas[0] not in abertas.setdefault(issue, []):
                    abertas[issue].append(celulas[0])
    return abertas


def retornos_resolvidos(atual: str, anterior: str | None, perfil: Perfil) -> tuple[Retorno, ...]:
    """As issues `retorno #N` citadas em qualquer célula das pendências de `resolvidas_desde`, uma por `Retorno`, na
    ordem do número, com as resolvidas que a citam, na ordem da pendência, e as abertas do backlog `atual` que
    também a citam."""
    resolvidas: dict[int, list[tuple[str, str]]] = {}
    for id_, celulas in _novas(atual, anterior, perfil):
        como = _como(celulas[-1])
        for issue in retornos_citados(" | ".join(celulas)):
            resolvidas.setdefault(issue, []).append((id_, como))
    abertas = _abertas(atual, perfil)
    return tuple(Retorno(issue, tuple(resolvidas[issue]), tuple(abertas.get(issue, ())))
                 for issue in sorted(resolvidas))


def _pela(ids: tuple[str, ...], virgulas: bool = False) -> str:
    """`pela <ID>` ou `pelas <IDs>`, com `e` antes do último ou, com `virgulas`, só com vírgulas."""
    lista = ", ".join(ids) if virgulas else comum.juntar(ids)
    return f"pela {lista}" if len(ids) == 1 else f"pelas {lista}"


def corpo_do_retorno(tag: str, retorno: Retorno) -> str:
    """O comentário da issue (spec 6c, §7.1): com uma resolvida, o `<como>` vai na frase; com mais, numa linha
    `<pendência>: <como>` de cada, depois da frase."""
    ids = retorno.pendencias
    if len(ids) == 1 and retorno.fecha:
        return f"Resolvida na {tag} pela {ids[0]}: {retorno.resolvidas[0][1]}"
    if len(ids) == 1:
        frase = f"{ids[0]} resolvida na {tag}: {retorno.resolvidas[0][1].rstrip('.')}."
    elif retorno.fecha:
        frase = f"Resolvida na {tag} {_pela(ids)}."
    else:
        frase = f"{comum.juntar(ids)} resolvidas na {tag}."
    if not retorno.fecha:
        frase += f" A issue segue aberta {_pela(retorno.abertas)}."
    if len(ids) == 1:
        return frase
    return "\n".join([frase, *(f"{id_}: {como}" for id_, como in retorno.resolvidas)])


def _alterados(raiz: Path, executar) -> int:
    """Os arquivos que o `git status` mostra; a origem de uma renomeação não conta de novo."""
    feito = _git(raiz, ["status", "--porcelain=v1", "-z"], executar)
    if feito.returncode != 0:
        raise ErroPassagem(comum.motivo_do_git(feito, "status"))
    entradas = (feito.stdout or b"").split(b"\0")
    alterados = 0
    posicao = 0
    while posicao < len(entradas):
        entrada = entradas[posicao]
        posicao += 1
        if not entrada:
            continue
        alterados += 1
        if entrada[:2].strip(b" ")[:1] in (b"R", b"C"):
            posicao += 1
    return alterados


def _no_commit(raiz: Path, ref: str, caminho: str, executar) -> str | None:
    """O texto do arquivo no commit ou na tag; None se ele não está lá."""
    feito = _git(raiz, ["cat-file", "blob", f"{ref}:{caminho}"], executar)
    return feito.stdout.decode("utf-8", errors="replace") if feito.returncode == 0 else None


def _conferir(raiz: Path, perfil: Perfil, executar) -> tuple[dict[str, str], str, list[int]]:
    """As recusas de 1 a 4 da publicação, na ordem; devolve o STATUS, o backlog e as tags."""
    _, ramo = ambiente.arvore(raiz, executar)
    if ramo is not None:
        raise PublicacaoRecusada((f"publicar só na árvore principal: worktree {ramo}",))
    alterados = _alterados(raiz, executar)
    if alterados:
        quantos = _plural(alterados, "arquivo alterado", "arquivos alterados")
        raise PublicacaoRecusada((f"publicar pede a árvore limpa: {quantos}",))
    if _git(raiz, ["remote", "get-url", "origin"], executar).returncode != 0:
        raise PublicacaoRecusada(("publicar pede o remoto origin",))
    try:
        dados = estado.ler(raiz / perfil.caminhos.status, perfil)
        texto_backlog = backlog.ler(raiz / perfil.caminhos.backlog)
    except estado.EstadoInvalido as erro:
        raise ErroPassagem(f"STATUS.md inválido: {erro.mensagem}") from None
    except backlog.BacklogIlegivel as erro:
        raise ErroPassagem(f"backlog ilegível: {erro.mensagem}") from None
    if dados["Documento"] != "nenhum":
        try:
            documentos = estado.documentos(dados, raiz)
        except estado.EstadoInvalido as erro:
            raise ErroPassagem(f"STATUS.md inválido: {erro.mensagem}") from None
        raise PublicacaoRecusada((f"{comum.juntar(documentos)} em edição (passo {dados['Passo']})",))
    pasta = perfil.caminhos.planejamento.rstrip("/")
    linhas = []
    for fase in perfil.fases:
        for _, caminho, status in backlog.artefatos_da_pasta(texto_backlog, f"{pasta}/{fase.id}"):
            linha = f"{caminho} com status {status}"
            if rastreio.grupo_do_status(status) != "aprovado" and linha not in linhas:
                linhas.append(linha)
    if linhas:
        raise PublicacaoRecusada(tuple(linhas))
    numeros = tags(raiz, executar)
    ultimo = perfil.nomes_dos_gates[-1]
    if not numeros and not dados[ultimo].startswith("aprovado"):
        raise PublicacaoRecusada((f"primeira passagem só depois do {ultimo} aprovado",))
    return dados, texto_backlog, numeros


def _devolver(raiz: Path, relativo: str, original: bytes | None, executar) -> None:
    """Tira o manifesto do índice e o volta ao do HEAD: os bytes de antes, ou nenhum arquivo."""
    try:
        _git(raiz, ["reset", "-q", "--", relativo], executar)
    except ErroPassagem:
        pass
    destino = raiz / relativo
    if original is None:
        destino.unlink(missing_ok=True)
    else:
        destino.write_bytes(original)


def publicar(raiz: Path, perfil: Perfil, executar=subprocess.run) -> Publicada:
    """Commita o manifesto da exportação do HEAD e cria a tag anotada `passagem/vN`, só na máquina (spec 6b, §10.1).
    Lança PublicacaoRecusada, com as linhas, ou ErroPassagem."""
    conferir_perfil(perfil)
    _, texto_backlog, numeros = _conferir(raiz, perfil, executar)
    exportacao = calcular(raiz, perfil, "HEAD", executar)
    anterior = None
    if numeros:
        tag_anterior = f"{manifesto.PREFIXO_TAG}{numeros[-1]}"
        try:
            ultimo = manifesto.de_json(_no_commit(raiz, tag_anterior, perfil.passagem.manifesto, executar) or "")
        except manifesto.ManifestoInvalido:
            ultimo = None
        anterior = _no_commit(raiz, tag_anterior, perfil.caminhos.backlog, executar)
        if anterior is None:
            raise ErroPassagem(f"backlog ausente em {tag_anterior}")
        # A issue de retorno resolvida sem mudar arquivo só fecha por uma versão nova (revisão da branch do PR 2).
        if (ultimo is not None and not retornos_resolvidos(texto_backlog, anterior, perfil)
                and (manifesto.hash_dos_arquivos(ultimo.arquivos)
                     == manifesto.hash_dos_arquivos(exportacao.manifesto.arquivos))):
            raise PublicacaoRecusada((f"nada a publicar: igual a {tag_anterior}",))
    if exportacao.recusas or exportacao.avisos:
        raise PublicacaoRecusada(tuple(exportacao.recusas + exportacao.avisos))

    versao = numeros[-1] + 1 if numeros else 1
    tag = f"{manifesto.PREFIXO_TAG}{versao}"
    gatilho = manifesto.GATILHO_REVISAO if numeros else perfil.nomes_dos_gates[-1]
    resolvidas = resolvidas_desde(texto_backlog, anterior, perfil) if numeros else []
    origem = exportacao.manifesto.origem
    m = dataclasses.replace(exportacao.manifesto, versao=versao, origem=dataclasses.replace(
        origem, gatilho=gatilho, pendencias_resolvidas=tuple(resolvidas)))
    relativo = perfil.passagem.manifesto
    destino = raiz / relativo
    original = destino.read_bytes() if destino.is_file() else None
    comum.escrever_texto(destino, manifesto.para_json(m))

    mensagem = ["-m", f"docs(passagem): {tag} ({gatilho})"]
    if resolvidas:
        mensagem += ["-m", f"Pendências resolvidas desde {manifesto.PREFIXO_TAG}{versao - 1}: {comum.juntar(resolvidas)}."]
    try:
        feito = _git(raiz, ["add", "--", relativo], executar)
        subcomando = "add"
        if feito.returncode == 0:
            feito = _git(raiz, ["commit", "-q", *mensagem, "--", relativo], executar, TEMPO_LIMITE_COMMIT)
            subcomando = "commit"
        motivo = "" if feito.returncode == 0 else comum.motivo_do_git(feito, subcomando)
    except ErroPassagem as erro:
        motivo = erro.mensagem
    if motivo:
        _devolver(raiz, relativo, original, executar)
        raise PublicacaoRecusada((f"commit falhou: {motivo}",))

    cabeca = _git(raiz, ["rev-parse", "--verify", "-q", "HEAD"], executar)
    commit = (cabeca.stdout or b"").decode("utf-8", errors="replace").strip() if cabeca.returncode == 0 else "HEAD"
    paragrafos = (f"{tag} ({gatilho})", f"Origem: {origem.commit}",
                  f"Pendências resolvidas: {comum.juntar(resolvidas) or 'nenhuma'}")
    mensagens = [parte for paragrafo in paragrafos for parte in ("-m", paragrafo)]
    try:
        marcada = _git(raiz, ["tag", "-a", tag, *mensagens, commit], executar)
        motivo = "" if marcada.returncode == 0 else comum.motivo_do_git(marcada, "tag")
    except ErroPassagem as erro:
        motivo = erro.mensagem
    if motivo:
        dica = shlex.join(["git", "tag", "-a", tag, *mensagens, commit[:12]])
        raise PublicacaoRecusada((f"tag falhou: {motivo}; crie-a com {dica}",))
    retornos = retornos_resolvidos(texto_backlog, anterior, perfil)
    return Publicada(versao, commit, gatilho, retornos)


def linhas_da_publicada(publicada: Publicada) -> list[str]:
    """As três linhas da saída do `publicar`: a versão pronta, o que o envio fará e o comando do envio."""
    tag = f"{manifesto.PREFIXO_TAG}{publicada.versao}"
    fecham = ", ".join(f"#{retorno.issue} ({', '.join(retorno.pendencias)})"
                       for retorno in publicada.retornos if retorno.fecha)
    comentadas = ", ".join(
        f"#{retorno.issue} ({', '.join(retorno.pendencias)}, segue aberta {_pela(retorno.abertas, virgulas=True)})"
        for retorno in publicada.retornos if not retorno.fecha
    )
    envio = f"comenta e fecha: {fecham}" if fecham else "não fecha nenhuma issue"
    if comentadas:
        envio += f"; só comenta: {comentadas}"
    return [
        f"{tag} pronta na máquina: commit {publicada.commit[:12]}, tag {tag}",
        f"O envio empurra a tag {tag} e {envio}",
        f"Para enviar: harness.py passagem publicar --enviar v{publicada.versao}",
    ]


@dataclass(frozen=True)
class Envio:
    """O que o envio fez, uma linha por passo, e as falhas, uma linha cada."""

    linhas: tuple[str, ...]
    falhas: tuple[str, ...]


def _gh(raiz: Path, argumentos: list[str], executar) -> tuple[subprocess.CompletedProcess | None, str]:
    """O `gh` na raiz; devolve o processo e, se ele não rodou ou saiu com erro, o motivo."""
    try:
        feito = executar(["gh", *argumentos], cwd=str(raiz), capture_output=True, timeout=TEMPO_LIMITE_GH)
    except OSError as erro:
        return None, comum.motivo_do_sistema(erro)
    except subprocess.TimeoutExpired:
        return None, f"passou de {TEMPO_LIMITE_GH} s"
    if feito.returncode != 0:
        return feito, comum.motivo_do_git(feito, " ".join(argumentos[:2]), "gh")
    return feito, ""


def _tags_na_origem(raiz: Path, executar) -> dict[str, str]:
    """O sha de cada tag `passagem/vN` do `origin`, pelo nome da tag, de um `git ls-remote` só; ficam fora a linha do
    `^{}` e o nome que não é exatamente `passagem/vN`. A falha do `ls-remote` lança ErroPassagem com
    `origin não consultado: <motivo>`."""
    try:
        feito = _git(raiz, ["ls-remote", "--tags", "origin", f"refs/tags/{manifesto.PREFIXO_TAG}*"], executar,
                     TEMPO_LIMITE_GH)
    except ErroPassagem as erro:
        raise ErroPassagem(f"origin não consultado: {erro.mensagem}") from None
    if feito.returncode != 0:
        raise ErroPassagem(f"origin não consultado: {comum.motivo_do_git(feito, 'ls-remote')}")
    shas: dict[str, str] = {}
    for linha in (feito.stdout or b"").decode("utf-8", errors="replace").splitlines():
        sha, separador, nome = linha.partition("\trefs/tags/")
        if separador and _RE_TAG.fullmatch(nome.strip()):
            shas[nome.strip()] = sha.strip()
    return shas


def _sha_local(raiz: Path, tag: str, executar) -> str:
    """O sha da tag na máquina, pelo `git rev-parse refs/tags/<tag>`; a falha lança ErroPassagem."""
    feito = _git(raiz, ["rev-parse", f"refs/tags/{tag}"], executar)
    if feito.returncode != 0:
        raise ErroPassagem(comum.motivo_do_git(feito, "rev-parse"))
    return (feito.stdout or b"").decode("utf-8", errors="replace").strip()


def _tratar_issue(raiz: Path, tag: str, retorno: Retorno, executar) -> tuple[str, str]:
    """A linha ou a falha de uma issue: sem pendência aberta que a cite, fecha a aberta, com o comentário; com ela,
    só a comenta. A fechada só dá a linha. A que já tem o comentário igual, sem os espaços das pontas e com o
    `\\r\\n` contado como `\\n`, não ganha outro: a que fecha é fechada sem comentário, e a outra só dá a linha."""
    numero = str(retorno.issue)
    visto, motivo = _gh(raiz, ["issue", "view", numero, "--json", "state,comments"], executar)
    if motivo:
        return "", f"#{numero}: gh issue view falhou: {motivo}"
    try:
        dados = json.loads((visto.stdout or b"").decode("utf-8", errors="replace"))
        estado_da_issue = dados.get("state")
        comentarios = [comentario.get("body") for comentario in dados.get("comments") or []]
    except (ValueError, AttributeError):
        return "", f"#{numero}: gh issue view falhou: saída do gh ilegível"
    pendencias = ", ".join(retorno.pendencias)
    if estado_da_issue == "CLOSED":
        return f"#{numero} já estava fechada ({pendencias})", ""
    corpo = corpo_do_retorno(tag, retorno)
    segue = "" if retorno.fecha else f"; segue aberta {_pela(retorno.abertas, virgulas=True)}"
    if any(isinstance(texto, str) and texto.replace("\r\n", "\n").strip() == corpo for texto in comentarios):
        if not retorno.fecha:
            return f"#{numero} já comentada ({pendencias}){segue}", ""
        _, motivo = _gh(raiz, ["issue", "close", numero], executar)
        if motivo:
            return "", f"#{numero}: gh issue close falhou: {motivo}"
        return f"#{numero} fechada ({pendencias}); já comentada", ""
    if retorno.fecha:
        _, motivo = _gh(raiz, ["issue", "close", numero, "--comment", corpo], executar)
        if motivo:
            return "", f"#{numero}: gh issue close falhou: {motivo}"
        return f"#{numero} comentada e fechada ({pendencias})", ""
    _, motivo = _gh(raiz, ["issue", "comment", numero, "--body", corpo], executar)
    if motivo:
        return "", f"#{numero}: gh issue comment falhou: {motivo}"
    resolvida = "resolvida" if len(retorno.pendencias) == 1 else "resolvidas"
    return f"#{numero} comentada{segue} ({pendencias} {resolvida} na {tag})", ""


def _issues_da_tag(
    raiz: Path, perfil: Perfil, numeros: list[int], versao: int, executar
) -> tuple[list[str], list[str]]:
    """As linhas e as falhas das issues de retorno da `passagem/v<versao>`, pelos backlogs dela e da tag anterior da
    máquina; a falha de uma issue segue para a próxima."""
    tag = f"{manifesto.PREFIXO_TAG}{versao}"
    atual = _no_commit(raiz, tag, perfil.caminhos.backlog, executar)
    if atual is None:
        return [], [f"backlog ausente em {tag}"]
    anteriores = [numero for numero in numeros if numero < versao]
    anterior = (_no_commit(raiz, f"{manifesto.PREFIXO_TAG}{anteriores[-1]}", perfil.caminhos.backlog, executar)
                if anteriores else None)
    linhas: list[str] = []
    falhas: list[str] = []
    for retorno in retornos_resolvidos(atual, anterior, perfil):
        linha, falha = _tratar_issue(raiz, tag, retorno, executar)
        if linha:
            linhas.append(linha)
        if falha:
            falhas.append(falha)
    return linhas, falhas


def _empurrar(raiz: Path, tag: str, executar) -> str:
    """Empurra só a tag ao `origin`; devolve a falha, ou texto vazio."""
    try:
        empurrado = _git(raiz, ["push", "origin", f"refs/tags/{tag}"], executar, TEMPO_LIMITE_PUSH)
        motivo = "" if empurrado.returncode == 0 else comum.motivo_do_git(empurrado, "push")
    except ErroPassagem as erro:
        motivo = erro.mensagem
    return f"push falhou: {motivo}" if motivo else ""


def enviar(raiz: Path, perfil: Perfil, versao: int, executar=subprocess.run) -> Envio:
    """Empurra ao `origin` as tags `passagem/vK` da máquina que faltam lá, até a vN, e fecha ou comenta as issues de
    retorno resolvidas de cada uma (spec 6b, §10.2, e 6c, §7.3). A tag do origin com outro sha recusa antes de tudo.
    Cada vK que falta, em ordem crescente, tem as issues tratadas antes do push, e qualquer falha nela para o
    comando; a vN vai antes das issues dela. As issues vêm dos backlogs da tag e da anterior; lança ErroPassagem só
    sem git."""
    tag = f"{manifesto.PREFIXO_TAG}{versao}"
    numeros = tags(raiz, executar)
    if versao not in numeros:
        return Envio((), (f"{tag} não existe na máquina",))
    if numeros[-1] != versao:
        return Envio((), (f"{tag} não é a última tag: {manifesto.PREFIXO_TAG}{numeros[-1]}",))
    faltam: list[int] = []
    try:
        na_origem = _tags_na_origem(raiz, executar)
        for numero in numeros:
            outra = f"{manifesto.PREFIXO_TAG}{numero}"
            no_origin = na_origem.get(outra)
            if no_origin is None:
                faltam.append(numero)
                continue
            na_maquina = _sha_local(raiz, outra, executar)
            if no_origin != na_maquina:
                return Envio((), (f"a tag {outra} do origin é outra ({no_origin[:12]}; na máquina, "
                                  f"{na_maquina[:12]}); confira antes de enviar",))
    except ErroPassagem as erro:
        return Envio((), (erro.mensagem,))
    linhas: list[str] = []
    for numero in faltam:
        if numero == versao:
            break
        outra = f"{manifesto.PREFIXO_TAG}{numero}"
        da_tag, falhas = _issues_da_tag(raiz, perfil, numeros, numero, executar)
        linhas += da_tag
        if falhas:
            return Envio(tuple(linhas), tuple(falhas))
        falha = _empurrar(raiz, outra, executar)
        if falha:
            return Envio(tuple(linhas), (falha,))
        linhas.append(f"tag {outra} enviada ao origin")
    if versao in faltam:
        falha = _empurrar(raiz, tag, executar)
        if falha:
            return Envio(tuple(linhas), (falha,))
        linhas.append(f"tag {tag} enviada ao origin")
    else:
        linhas.append(f"tag {tag} já estava no origin")
    da_tag, falhas = _issues_da_tag(raiz, perfil, numeros, versao, executar)
    return Envio(tuple(linhas + da_tag), tuple(falhas))


def mudados_desde(raiz: Path, versao: int, executar=subprocess.run) -> list[str]:
    """Os caminhos que o `git diff` da tag `passagem/v<versao>` ao HEAD mostra; lança ErroPassagem."""
    feito = _git(raiz, ["diff", "--name-only", "-z", f"{manifesto.PREFIXO_TAG}{versao}", "HEAD"], executar)
    if feito.returncode != 0:
        raise ErroPassagem(comum.motivo_do_git(feito, "diff"))
    return [caminho for caminho in (feito.stdout or b"").decode("utf-8", errors="replace").split("\0") if caminho]
