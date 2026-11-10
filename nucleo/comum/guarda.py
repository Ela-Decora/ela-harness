"""Guarda dos hooks do Claude Code (spec 3b, §6, §7.1, §9 e §12): o PreToolUse, a prova de mensagem do
UserPromptSubmit e o Stop. O PreToolUse decide sobre Edit, Write, NotebookEdit e Bash, e o Stop confere as
invariantes da árvore.

Entrada única: `rodar`, chamado por `harness.py guarda <evento>`, que nunca lança e sempre sai com 0; erro vira
`systemMessage`, sem decisão. A guarda devolve `deny`, `ask` ou nada, nunca `allow`.

Árvore de um caminho: o ancestral mais próximo, ele incluído, que tem `.git` (pasta ou arquivo). Duas árvores são a
mesma quando as raízes têm o mesmo dispositivo e inode, porque o macOS aceita a mesma pasta com maiúsculas trocadas.
Caminho protegido é comparado normalizado e relativo à raiz.
"""
from __future__ import annotations

import datetime
import fnmatch
import json
import os
import posixpath
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import anotacao
import bloco
import ci
import comum
import escrita
import estado
import gerador
import invariantes
import perfil_comum
import perfil_desenvolvimento
import segredos
import verificacao
# Os nomes do prompt moram no `anotacao`; ficam acessíveis pela `guarda` para quem os usa daqui.
from anotacao import PREFIXO_NOTIFICACAO, PREFIXOS_SINTETICOS, anotar_prompt, prompt_sintetico  # noqa: F401
from comum import diretorio_comum, mesma_arvore
from perfil import Perfil, carregar as carregar_perfil
from perfil_comum import PerfilComum, PerfilInvalido
from perfil_desenvolvimento import PerfilDesenvolvimento

AJUDA = """\
Decide, pelos hooks do Claude Code, o que o modelo não pode gravar: lê o payload JSON do stdin e sai sempre com 0.

Os hooks do `.claude/settings.json` chamam `guarda pre-tool` (PreToolUse, em Edit, Write, NotebookEdit e Bash),
`guarda prompt` (UserPromptSubmit) e `guarda stop` (Stop), com 30 s de limite no PreToolUse e no UserPromptSubmit e
900 s no Stop, que no repositório de código roda as verificações do perfil. No planejamento, o UserPromptSubmit vai
pela via curta do `gancho`, que grava a resposta sem carregar o `harness.py`, com a mesma saída.
A guarda recusa (`deny`), pede a confirmação do usuário (`ask`) ou não diz nada; nunca libera o que o `settings.json`
bloqueia. A raiz da sessão é a `CLAUDE_PROJECT_DIR`, ou a pasta com `CLAUDE.md` acima do harness; o prompt usa a raiz.
Árvore é a pasta mais próxima com `.git`, comparada pelo dispositivo e pelo inode. A árvore da sessão, que o PreToolUse
e o Stop usam, é a do `cwd` do payload quando ela é a raiz da sessão ou um worktree do mesmo repositório, pelo diretório
comum do git lido dos arquivos `.git` e `commondir`; senão, a raiz. Documento em aprovação é o `Documento`, ou cada um
do `Pacote`, com `Passo` 6 ou 7.

O perfil sai da árvore da sessão, em duas camadas: a parte comum (`[projeto]` e `[guarda]`), cujo erro vira o aviso
de erro, e o perfil da trilha. Com o da trilha inválido, valem só as regras comuns, de 1 a 6; quando nenhuma decide,
sai o aviso `guarda do harness: perfil inválido: <motivo>; só as regras comuns valem`. As regras 7 e 8 de baixo e os
alvos protegidos do Bash, menos o arquivo de ambiente, os `proibidos` e os do desenvolvimento, são do perfil de
planejamento; o `LANES.md` e os gerados do `gerar` da regra 7, a regra 9, os alvos dela no Bash, a restauração ampla
e o `git push --no-verify`, só do perfil de desenvolvimento.

PreToolUse em Edit, Write e NotebookEdit; vence a primeira regra que casa, nesta ordem:

1. alvo ausente: nada;
2. alvo fora de toda árvore git: nada;
3. alvo noutra árvore git que não a da sessão: recusa, com
   `<alvo> está na árvore <raiz do alvo>, e esta sessão trabalha na <árvore da sessão>` e o pedido de entrar nela
   pelo `EnterWorktree` ou abrir uma sessão lá;
4. segredo no conteúdo: recusa, com `segredo no conteúdo (<nome do padrão>); guarde-o fora do repositório`, sem o
   valor. A guarda procura no `content` do Write, no `new_string` do Edit e no de cada item de `edits`, e no
   `new_source` do NotebookEdit, os padrões do núcleo (`chave-privada`, `chave-aws`, `token-github` e `jwt`) e os de
   `[guarda.segredos]`. O alvo que casa um `segredos_isentos` do perfil fica de fora;
5. arquivo de ambiente, de nome `.env` ou que começa por `.env.` e não termina em `.example`, em qualquer pasta:
   recusa, com `recusado: <relativo> é arquivo de ambiente; no repositório vai só o .env.example`;
6. alvo casa com um dos `proibidos` do perfil (`[guarda]`; `pasta/**` casa com a pasta e com tudo dentro): recusa;
7. alvo é um arquivo gerado, a legenda (`caminhos.legenda`) ou o manifesto da passagem (`passagem.manifesto`):
   recusa, com `arquivo gerado: rode harness.py legenda` ou `arquivo gerado: rode harness.py passagem publicar`; no
   desenvolvimento, o `LANES.md` da raiz de qualquer árvore, sem distinguir maiúsculas: recusa, com
   `arquivo gerado: rode harness.py lanes`; e, também sem distinguir maiúsculas, o `AGENTS.md` da raiz, a legenda
   (`caminhos.legenda`), o `.github/workflows/harness.yml` e qualquer arquivo de `.claude/rules/harness/` e de
   `.claude/harness/gerado/`, que o `harness.py gerar` grava: recusa, com `arquivo gerado: rode harness.py gerar`; no planejamento, vale só a
   pasta `.claude/harness/gerado/`, onde o `gerar` grava o `planejamento.md`, e o `.github/workflows/harness.yml`: o
   alvo igual a eles ou dentro da pasta, sem distinguir maiúsculas, é recusado com a mesma mensagem;
8. alvo é um documento em aprovação: recusa; alvo é o arquivo de decisões (`caminhos.decisoes`), e a edição tira
   ou altera uma linha: recusa; sessão no checkout principal e alvo dentro de `.claude/`: pede confirmação;
9. no perfil de desenvolvimento, sem distinguir maiúsculas, porque o disco do Mac não as distingue: alvo dentro da
   cópia da passagem (`caminhos.passagem`), em qualquer árvore, a principal ou a de uma lane: recusa, com
   `a cópia da passagem muda só por harness.py importar`; alvo `<blocos>/*/aceitacao.md` (`caminhos.blocos`):
   recusa, com `a aceitação muda só por harness.py aceitacao conferir ou anotar`; alvo `<blocos>/*/estado.md`:
   recusa, com `o estado do bloco muda só por harness.py bloco <verbo>`; alvo `<blocos>/*/revisao.md`: recusa, com
   `a revisão muda só por harness.py revisao registrar e revisao dispensar`; alvo `<blocos>/*/gabarito.md`: recusa,
   com `o gabarito muda só por harness.py revisao preparar`; alvo `<blocos>/<pasta>/spec.md` cujo `estado.md`, na
   árvore da sessão, se lê com o estado efetivo (o `estado_anterior` em `blocked`) fora de `planning`: recusa, com
   `a spec aprovada muda só depois de harness.py bloco replanejar`; sem esse `estado.md`, ou com ele ilegível, a spec
   passa. Fora de lane, o alvo que não casa nenhum padrão de `desenvolvimento.fora_da_lane` é recusado com
   `fora de lane, só se grava em <padrões>; abra uma lane com harness.py lane abrir <ficha>`. Lane é a worktree
   dentro de `lane.pasta` com o bloco da branch dela, reconhecida pelos arquivos; a de `estado.md` inválido também
   conta, e o Stop acusa o arquivo.

PreToolUse em Bash: lê os alvos de escrita do comando (redirecionamentos, `tee`, `sed -i`, `rm`, `mv`, `mkdir`, o
destino de `cp`, os subcomandos de git que escrevem e outros), com o `cd`, o `git -C` e o código de `sh -c`, até dois
níveis. Confere, nesta ordem, a outra árvore de cada alvo e de cada diretório de git, o segredo no texto inteiro do
comando, as outras regras de cada alvo, o código de `-c` e as perguntas; a primeira recusa vence:

- recusa: alvo, ou diretório de um git que escreve (`add` e `commit` incluídos), noutra árvore; segredo no texto do
  comando, com o corpo dos heredocs, sem a isenção de `segredos_isentos` (o segredo falso num caminho isento vai pelo
  Write); alvo de arquivo de ambiente; alvo que casa com um dos `proibidos` do perfil, mas não a pasta que só o
  contém; alvo igual a um arquivo gerado (o `git restore` dele conta; o `git add` e o `git commit` passam); alvo que
  sobrepõe a pasta de moldes, o STATUS.md ou um documento em aprovação, também pela pasta que os contém; no perfil de
  desenvolvimento, o `LANES.md`, com a mensagem da regra 7, o alvo que sobrepõe a cópia da passagem, um
  `<blocos>/*/aceitacao.md`, um `<blocos>/*/estado.md`, um `<blocos>/*/revisao.md`, um `<blocos>/*/gabarito.md`, o
  `AGENTS.md` da raiz, o `.github/workflows/harness.yml`, a legenda ou uma das duas pastas do `gerar`
  (`.claude/rules/harness` e
  `.claude/harness/gerado`), também pela pasta que os contém quando ela é a raiz (`.`) ou existe, pelo primeiro nessa
  ordem: o próprio alvo, com a mensagem da regra 9 (a dos gerados é a da regra 7); a pasta que contém a cópia ou um
  arquivo de bloco, com
  `<alvo> contém <primeiro protegido>, que muda só por comando do harness; grave num caminho fora dela`, o protegido
  escrito como nesta lista (a pasta da cópia ou o padrão `<blocos>/*/<arquivo>`); a que contém um gerado, com
  `<alvo> contém arquivos gerados (<primeiro gerado>) e do harness; a pasta não se apaga nem se sobrescreve inteira`.
  Também a spec aprovada, com a mensagem da regra 9, e, fora de lane, o
  alvo fora do `fora_da_lane`; código de `python -c`, `node -e`, `ruby -e` ou `perl -e` que cita um desses, um
  arquivo gerado ou um proibido sem o `/**` do fim;
- passa pela regra 9: a restauração, que volta o arquivo ao índice ou ao HEAD, como o `arquivos-do-harness` pede: o
  `git restore` sem `-s` nem `--source`, em qualquer forma, e o `git checkout` com `--` e só opções antes dele. A de
  dentro da cópia, de um `estado.md`, de um `aceitacao.md`, de um `revisao.md`, de um `gabarito.md`, da spec
  aprovada ou de um gerado do `gerar` passa também fora de lane; as outras passam antes pelo `fora_da_lane`. As
  outras regras valem para ela, menos no `LANES.md`, que segue recusado, e o caminho que o mesmo comando também grava
  de outro jeito não conta como restauração;
- pede confirmação: sessão no checkout principal e alvo em `.claude/`; `git commit --no-verify` ou `-n`; no perfil de
  desenvolvimento, `git push --no-verify`, ou um começo dele, e a restauração ampla, que volta o disco (o
  `git restore` sem `--staged` ou com `--worktree`, e o `git checkout --`) e tem por alvo a raiz ou uma pasta que
  contém a cópia, um `estado.md`, um `aceitacao.md`, um `revisao.md`, um `gabarito.md` ou um gerado do `gerar`, com
  `a restauração de <alvo> apaga as mudanças sem commit de toda a pasta, não só as dos arquivos do harness`; o
  `git restore --staged .` e o de uma pasta sem arquivo da regra 9 passam calados; git que apaga trabalho ou
  reescreve o remoto:
  `git reset --hard`; `git clean` com `-f` ou `--force`, também em grupo, menos com `-n` ou `--dry-run`; `git stash`
  sem caminho (sozinho, com opções, `push` sem caminho ou `save`), `git stash drop` e `git stash clear`; `git push`
  com `--force`, `-f`, também em grupo, `--force-with-lease` ou uma refspec que começa por `+`. Cada um com a
  mensagem dele, terminada em `; confirme só se o usuário pediu`. Depois deles, o `--enviar` do `passagem publicar`
  depois de uma palavra que termina em `harness.py`, em qualquer forma (com `$CLAUDE_PROJECT_DIR`, com
  `--enviar=<v>` ou dentro de `sh -c`), com `confirme: o --enviar empurra a tag passagem/vN e fecha issues no origin`;
  o `importar` depois dessa palavra, também como argumento de outro comando, com
  `confirme: o importar abre branch e PR no origin, fora da montagem`; e o `aceitacao anotar`, com
  `confirme: o aceitacao anotar grava o resultado de um item manual, que só o usuário confere`; o `bloco finalizar`,
  com `confirme: o bloco finalizar empurra a branch e abre o PR`; o `bloco desbloquear`, com
  `confirme: o bloco desbloquear destrava o bloco pela causa do bloqueio, que só o usuário decide`; o
  `bloco planejado`, com `confirme: o bloco planejado registra a aprovação da spec pelo dono`; o `bloco replanejar`,
  com `confirme: o bloco replanejar descarta a aprovação da spec, que o dono dá de novo`; o `revisao dispensar`, com
  `confirme: o revisao dispensar tira o achado do ## Em aberto pela palavra do dono`; o `retorno abrir`, com
  `confirme: o retorno abrir cria uma issue no repositório de planejamento`; e o `lane fechar` com `--manual` ou
  `--abandonar`, com
  `confirme: o lane fechar --manual grava o resultado de itens manuais, que só o usuário confere` e
  `confirme: o lane fechar --abandonar apaga a worktree e a branch da lane sem PR mesclado`. A palavra que começa
  por `--` conta pelo que vem antes do `=`. Com mais de um pedido no comando, as mensagens saem juntas, separadas por
  `; `, com o `; confirme só se o usuário pediu` uma vez só, no fim;
- nada: leitura, o `harness.py`, menos os comandos que pedem confirmação, e o arquivo de decisões, porque `cat >>` é
  acréscimo e o Stop pega a linha tirada.

UserPromptSubmit: com `Passo` 6 e versão marcada, cada mensagem do usuário grava a `resposta` que o `passo 7` exige
(veja `harness.py versao`); a notificação de tarefa e o retorno de subagente não contam.

Stop: roda `invariantes --arvore` na árvore da sessão, com as conferências da trilha do perfil, no fim do turno. Com
falha, segura o turno uma vez e pede que o modelo desfaça com `git restore <arquivo>` ou explique; a falha em molde ou
no STATUS.md, ele pede ao usuário. Na segunda parada do turno (`stop_hook_active`), só avisa. Sem `.git` na árvore,
não decide.

Na trilha de desenvolvimento, o Stop roda as invariantes do `--arvore` e, numa lane reconhecida pelos arquivos, compara
a marca da árvore com a da última verificação aprovada: igual, nada roda; diferente, roda as verificações de `stop`
(veja `harness.py verificar`), que somam até 840 s. A falha de invariante ou de verificação segura o turno uma vez,
com `Corrija e pare de novo.` e, depois de uma quebra, as linhas das verificações que falharam; com `stop_hook_active`,
só avisa. Sem falha, as puladas e as sem tempo vão num aviso, sem segurar o turno. Fora de lane, nenhuma verificação
roda. Na lane, as verificações também não rodam em dois casos, e as invariantes seguem: com o bloco em `planning`, ou
em `blocked` vindo dele, e em `reviewing` com a marca da revisão em andamento de menos de 4 horas (veja
`harness.py revisao preparar`). Nos dois, o Stop não diz nada pelas verificações e não grava a marca da verificação.

```text
pre-tool: {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
           "permissionDecisionReason": "guarda do harness: <motivo>"}}       (ou "ask"; sem decisão, nada)
stop:     {"decision": "block", "reason": "guarda do harness: <falhas>. Desfaça com git restore <arquivo> ..."}
          {"systemMessage": "guarda do harness: <falhas>; o pre-commit vai recusar o commit"}
          {"decision": "block", "reason": "guarda do harness: <falhas>. Corrija e pare de novo.\\n<linhas>"}
          {"systemMessage": "guarda do harness: <falhas>; corrija antes de seguir"}   (as duas, no desenvolvimento)
erro:     {"systemMessage": "guarda do harness com erro, sem decisão: <tipo>: <motivo>"}
          {"systemMessage": "guarda do harness com erro ao anotar a resposta: <tipo>: <motivo>"}   (no prompt)
```

O `settings.json` nega às ferramentas Edit e Write do modelo os moldes (`moldes.pasta`), o STATUS.md
(`caminhos.status`) e os `proibidos` do perfil, repetidos à mão no `deny`, e pede confirmação no rascunho
(`caminhos.rascunho`) e no perfil. Numa recusa, a mensagem diz o caminho certo quando há um, como `harness.py passo 3`
antes de editar o documento em aprovação; a mudança que o usuário quer de propósito ele faz com `!` no prompt, porque
a guarda só olha o modelo.

Limites: a guarda não lê o script executado por arquivo, `eval`, `xargs`, `find -exec`, a substituição de comando nem
o corpo de um heredoc, nos alvos (a regra do segredo lê o texto inteiro do comando, com o corpo), e o Stop cobre o
que passar. Ela falha aberta: um erro vira o aviso de erro, e a ferramenta
segue a permissão normal. Sem `python3`, os hooks somem sem aviso.
"""

PREFIXO = "guarda do harness: "
DENY = "deny"
ASK = "ask"

EVENTO_PRE_TOOL = "pre-tool"
EVENTO_PROMPT = "prompt"
EVENTO_STOP = "stop"
EVENTOS = (EVENTO_PRE_TOOL, EVENTO_PROMPT, EVENTO_STOP)

_PASSOS_EM_APROVACAO = ("6", "7")
_SO_O_USUARIO_DESFAZ = (invariantes.MOLDES_INTOCADOS, invariantes.STATUS_VALIDO)
_PASTA_DO_HARNESS = ".claude"
_ALVO_POR_FERRAMENTA = {"Edit": "file_path", "Write": "file_path", "NotebookEdit": "notebook_path"}
_CONFIRME = "; confirme só se o usuário pediu"
_MENSAGEM_SEM_VERIFICACAO = "git commit --no-verify pula o pre-commit do harness" + _CONFIRME
_MENSAGEM_PUSH_SEM_VERIFICACAO = "git push --no-verify pula o pre-push do harness" + _CONFIRME
_MENSAGENS_DESTRUTIVAS = {
    escrita.RESET_HARD: "git reset --hard apaga as mudanças sem commit",
    escrita.CLEAN_FORCADO: "git clean -f apaga os arquivos que o git não acompanha",
    escrita.STASH_SEM_CAMINHO: "git stash sem caminho leva todas as mudanças para a pilha de stash, que as outras "
                               "árvores dividem",
    escrita.STASH_DROP: "git stash drop apaga uma entrada da pilha de stash",
    escrita.STASH_CLEAR: "git stash clear apaga a pilha de stash inteira",
    escrita.PUSH_FORCADO: "git push forçado reescreve o histórico do remoto",
}
# As palavras que, todas depois do `harness.py`, pedem confirmação, com a mensagem; o `--enviar=<v>` conta como
# `--enviar`.
_PERGUNTAS_DO_HARNESS: tuple[tuple[frozenset[str], str], ...] = (
    (frozenset({"passagem", "publicar", "--enviar"}),
     "confirme: o --enviar empurra a tag passagem/vN e fecha issues no origin"),
    (frozenset({"importar"}), "confirme: o importar abre branch e PR no origin, fora da montagem"),
    (frozenset({"aceitacao", "anotar"}),
     "confirme: o aceitacao anotar grava o resultado de um item manual, que só o usuário confere"),
    (frozenset({"bloco", "finalizar"}), "confirme: o bloco finalizar empurra a branch e abre o PR"),
    (frozenset({"bloco", "desbloquear"}),
     "confirme: o bloco desbloquear destrava o bloco pela causa do bloqueio, que só o usuário decide"),
    (frozenset({"bloco", "planejado"}), "confirme: o bloco planejado registra a aprovação da spec pelo dono"),
    (frozenset({"bloco", "replanejar"}),
     "confirme: o bloco replanejar descarta a aprovação da spec, que o dono dá de novo"),
    (frozenset({"revisao", "dispensar"}),
     "confirme: o revisao dispensar tira o achado do ## Em aberto pela palavra do dono"),
    (frozenset({"retorno", "abrir"}), "confirme: o retorno abrir cria uma issue no repositório de planejamento"),
    (frozenset({"lane", "fechar", "--manual"}),
     "confirme: o lane fechar --manual grava o resultado de itens manuais, que só o usuário confere"),
    (frozenset({"lane", "fechar", "--abandonar"}),
     "confirme: o lane fechar --abandonar apaga a worktree e a branch da lane sem PR mesclado"),
)
_MENSAGEM_COPIA = "a cópia da passagem muda só por harness.py importar"
_MENSAGEM_ACEITACAO = "a aceitação muda só por harness.py aceitacao conferir ou anotar"
_MENSAGEM_ESTADO = "o estado do bloco muda só por harness.py bloco <verbo>"
_MENSAGEM_SPEC = "a spec aprovada muda só depois de harness.py bloco replanejar"
_MENSAGEM_REVISAO = "a revisão muda só por harness.py revisao registrar e revisao dispensar"
_MENSAGEM_GABARITO = "o gabarito muda só por harness.py revisao preparar"
_MENSAGEM_PASTA = "{} contém {}, que muda só por comando do harness; grave num caminho fora dela"
_MENSAGEM_LANES = "arquivo gerado: rode harness.py lanes"
_MENSAGEM_GERADO_DO_CODIGO = "arquivo gerado: rode harness.py gerar"
_MENSAGEM_PASTA_COM_GERADOS = ("{} contém arquivos gerados ({}) e do harness; a pasta não se apaga nem se sobrescreve "
                               "inteira")
_MENSAGEM_RESTAURACAO_AMPLA = ("a restauração de {} apaga as mudanças sem commit de toda a pasta, não só as dos "
                               "arquivos do harness" + _CONFIRME)
# O quadro das lanes, que o `harness.py lanes` grava na raiz da árvore principal; a guarda não importa o `lanes.py`.
_LANES = "LANES.md"
# Os alcances de um alvo sobre um protegido da regra 9: o protegido ou algo nele, ou uma pasta que o contém.
_DENTRO = "dentro"
_PASTA = "pasta"


@dataclass(frozen=True)
class Decisao:
    """`tipo` é `deny` ou `ask`; `mensagem` já vem com o PREFIXO."""

    tipo: str
    mensagem: str


def _negar(mensagem: str) -> Decisao:
    return Decisao(DENY, PREFIXO + mensagem)


def _perguntar(mensagem: str) -> Decisao:
    return Decisao(ASK, PREFIXO + mensagem)


def raiz_da_arvore(caminho: Path) -> Path | None:
    """A pasta com `.git` mais próxima, subindo do próprio caminho ou do ancestral existente mais próximo; None se
    não houver. Não resolve links nem muda maiúsculas."""
    atual = caminho
    while not os.path.lexists(atual):
        if atual.parent == atual:
            return None
        atual = atual.parent
    for pasta in (atual, *atual.parents):
        if os.path.lexists(pasta / ".git"):
            return pasta
    return None


def mesmo_repositorio(a: Path, b: Path) -> bool:
    """As duas árvores têm diretórios comuns do git que existem e são a mesma pasta."""
    comum_a, comum_b = diretorio_comum(a), diretorio_comum(b)
    return comum_a is not None and comum_b is not None and mesma_arvore(comum_a, comum_b)


def arvore_da_sessao(cwd: object, raiz: Path) -> Path:
    """A árvore do `cwd` do payload quando ele é um texto absoluto numa árvore git que é a da raiz da sessão ou um
    worktree do mesmo repositório; senão, a raiz."""
    if not isinstance(cwd, str) or not os.path.isabs(cwd):
        return raiz
    arvore = raiz_da_arvore(Path(os.path.normpath(cwd)))
    if arvore is not None and (mesma_arvore(arvore, raiz) or mesmo_repositorio(arvore, raiz)):
        return arvore
    return raiz


def no_checkout_principal(raiz: Path) -> bool:
    """No checkout principal o `.git` é pasta; num worktree, arquivo."""
    return (raiz / ".git").is_dir()


def relativo_na_arvore(caminho: Path) -> tuple[Path, str] | None:
    """A raiz da árvore do caminho e o caminho relativo a ela, em posix e normalizado (a raiz inteira dá `.`)."""
    raiz = raiz_da_arvore(caminho)
    if raiz is None:
        return None
    return raiz, posixpath.normpath(caminho.relative_to(raiz).as_posix())


def sobrepoe(relativo: str, protegido: str) -> bool:
    """Um é o outro ou está dentro do outro; a raiz inteira (`.`) sobrepõe tudo."""
    protegido = posixpath.normpath(protegido)
    return (
        relativo == "."
        or relativo == protegido
        or relativo.startswith(protegido + "/")
        or protegido.startswith(relativo + "/")
    )


def proibido(relativo: str, padroes: tuple[str, ...]) -> str | None:
    """O primeiro padrão de `[guarda] proibidos` que casa com o caminho relativo à raiz, ou None, pelo
    `comum.padrao_que_casa`."""
    return comum.padrao_que_casa(relativo, padroes)


def conteudos(tool_name: str, tool_input: dict) -> list[str]:
    """Os textos que a ferramenta grava, onde a guarda procura segredo: o `content` do Write; o `new_string` do Edit
    e o de cada item de `edits`, quando é uma lista; o `new_source` do NotebookEdit. O que não é texto fica de
    fora."""
    if tool_name == "Write":
        brutos = [tool_input.get("content")]
    elif tool_name == "Edit":
        brutos = [tool_input.get("new_string")]
        edits = tool_input.get("edits")
        if isinstance(edits, list):
            brutos += [item.get("new_string") for item in edits if isinstance(item, dict)]
    elif tool_name == "NotebookEdit":
        brutos = [tool_input.get("new_source")]
    else:
        brutos = []
    return [bruto for bruto in brutos if isinstance(bruto, str)]


def arquivo_de_ambiente(relativo: str) -> bool:
    """O nome é `.env`, ou começa por `.env.` e não termina em `.example`, em qualquer pasta."""
    nome = posixpath.basename(relativo)
    return nome == ".env" or (nome.startswith(".env.") and not nome.endswith(".example"))


def _parte_fixa(padrao: str) -> str:
    """O padrão sem o `/**` do fim: o que o código de `python -c` e afins cita."""
    return padrao[: -len("/**")] if padrao.endswith("/**") else padrao


def _comum(perfil: Perfil | PerfilDesenvolvimento | PerfilComum) -> PerfilComum:
    return perfil if isinstance(perfil, PerfilComum) else perfil.comum


@dataclass(frozen=True)
class _Sessao:
    raiz: Path
    arvore: Path
    principal: bool
    # As regras do planejamento valem só com o `Perfil`; com os outros dois, só as comuns.
    perfil: Perfil | PerfilDesenvolvimento | PerfilComum
    # Os documentos em refino (o `Pacote`, ou o `Documento`) e o passo, só com versão em aprovação; vazio e None com
    # STATUS ilegível ou fora dos passos 6 e 7.
    documentos: tuple[str, ...]
    passo: str | None
    # Só no desenvolvimento: a árvore da sessão é uma lane, pelos arquivos; a de bloco ilegível também conta.
    na_lane: bool = False


def _na_lane(arvore: Path, perfil: PerfilDesenvolvimento) -> bool:
    """A lane pelo `bloco.lane_pelos_arquivos`; a árvore cujo bloco da branch não se lê também conta (decisão 2 do
    plano do PR 4 da 6c)."""
    try:
        return bloco.lane_pelos_arquivos(arvore, perfil) is not None
    except (bloco.Recusa, OSError, UnicodeDecodeError):
        return True


def _sessao(raiz: Path, perfil: Perfil | PerfilDesenvolvimento | PerfilComum) -> _Sessao:
    documentos: tuple[str, ...] = ()
    passo = None
    dados: dict = {}
    if isinstance(perfil, Perfil):
        try:
            dados = estado.ler(raiz / perfil.caminhos.status, perfil)
        except estado.EstadoInvalido:
            pass
    if dados.get("Passo") in _PASSOS_EM_APROVACAO:
        documentos = tuple(posixpath.normpath(documento) for documento in estado.documentos(dados))
        passo = dados["Passo"] if documentos else None
    arvore = raiz_da_arvore(raiz) or raiz
    na_lane = isinstance(perfil, PerfilDesenvolvimento) and _na_lane(arvore, perfil)
    return _Sessao(raiz, arvore, no_checkout_principal(raiz), perfil, documentos, passo, na_lane)


def _outra_arvore(alvo: Path, raiz_alvo: Path, sessao: _Sessao) -> Decisao:
    return _negar(
        f"{alvo} está na árvore {raiz_alvo}, e esta sessão trabalha na {sessao.raiz}; entre nela pelo EnterWorktree "
        "ou abra uma sessão lá"
    )


def _documento_em_aprovacao(documento: str, sessao: _Sessao) -> Decisao:
    return _negar(
        f"{documento} tem versão em aprovação (passo {sessao.passo}); para mudar, rode harness.py passo 3 "
        "(ou passo 2), edite e marque de novo com harness.py passo 6"
    )


def _harness_no_principal(relativo: str) -> Decisao:
    return _perguntar(f"edição do harness ({relativo}) no checkout principal; o trabalho no harness vai num worktree")


def _segredo(nome: str) -> Decisao:
    return _negar(f"segredo no conteúdo ({nome}); guarde-o fora do repositório")


def _ambiente(relativo: str) -> Decisao:
    return _negar(f"recusado: {relativo} é arquivo de ambiente; no repositório vai só o .env.example")


def _proibido(relativo: str) -> Decisao:
    return _negar(f"recusado: {relativo} é proibido neste projeto (perfil, [guarda] proibidos)")


def _gerado(relativo: str, perfil: Perfil) -> Decisao | None:
    """Recusa o alvo igual a um arquivo que o harness gera: a legenda e o manifesto da passagem, quando o perfil os
    tem, e a pasta dos gerados do `gerar` (`.claude/harness/gerado`), ela mesma ou o que está dentro dela, sem
    distinguir maiúsculas (spec do porte 1, §9.3, e decisão 12). O harness grava esses arquivos pelo Python, fora dos
    hooks."""
    if perfil.caminhos.legenda and relativo == perfil.caminhos.legenda:
        return _negar("arquivo gerado: rode harness.py legenda")
    if perfil.passagem is not None and relativo == perfil.passagem.manifesto:
        return _negar("arquivo gerado: rode harness.py passagem publicar")
    if _alcance(relativo, gerador.PASTA_DOS_GERADOS, None) == _DENTRO:
        return _negar(_MENSAGEM_GERADO_DO_CODIGO)
    if _alcance(relativo, ci.CAMINHO, None) == _DENTRO:
        return _negar(_MENSAGEM_GERADO_DO_CODIGO)
    return None


def _moldes(relativo: str, sessao: _Sessao) -> Decisao:
    return _negar(f"{relativo} está na pasta de moldes {sessao.perfil.moldes.pasta}, que não muda")


def _status(sessao: _Sessao) -> Decisao:
    return _negar(f"{sessao.perfil.caminhos.status} muda só pelos comandos do harness.py (estado set, passo, versao)")


def _absoluto(bruto: str, cwd: Path | None) -> Path | None:
    if os.path.isabs(bruto):
        return Path(os.path.normpath(bruto))
    if cwd is None:
        return None
    return Path(os.path.normpath(os.path.join(str(cwd), bruto)))


def _linha_tirada_na_edicao(ferramenta: str, entrada: dict, alvo: Path) -> int | None:
    """A linha do arquivo que a edição tira ou altera; None se ela só acrescenta ou não dá para saber."""
    try:
        texto = comum.ler_texto(alvo)
    except (OSError, UnicodeDecodeError):
        texto = None
    if ferramenta == "Write":
        conteudo = entrada.get("content")
        if texto is None or not isinstance(conteudo, str):
            return None
        return invariantes.linha_tirada(texto, conteudo)
    velho, novo = entrada.get("old_string"), entrada.get("new_string")
    if not isinstance(velho, str) or not isinstance(novo, str):
        return None
    tirada = invariantes.linha_tirada(velho, novo)
    if tirada is None or texto is None or not velho or velho not in texto:
        return tirada
    return texto.count("\n", 0, texto.index(velho)) + tirada


def decidir_edicao(
    tool_name: str, tool_input: dict, cwd: Path | None, raiz: Path, perfil: Perfil | PerfilDesenvolvimento | PerfilComum
) -> Decisao | None:
    """As regras de Edit, Write e NotebookEdit (spec 3b, §6.1, 5a, §11, 6b, §5.4, 6c, §6.5, §8.6 e §18, e 6d-gerador,
    §10), em ordem: fora de árvore, outra árvore, segredo no conteúdo (menos no alvo de `segredos_isentos`), arquivo
    de ambiente, `proibidos` do perfil; só com o perfil de desenvolvimento, o `LANES.md` (regra 7) e, sem distinguir
    maiúsculas, o alvo dentro da cópia da passagem, um `aceitacao.md`, um `estado.md`, um `revisao.md` ou um
    `gabarito.md` dos blocos, a spec aprovada (spec 6d-bloco, §8.6), os gerados do `gerar` (o `AGENTS.md` da raiz,
    a legenda e as duas pastas do gerador, com a mensagem da regra 7) e o `fora_da_lane` fora de lane (regra 9); e,
    só com o de planejamento, arquivo gerado, `Documento` em aprovação, só
    acréscimos nas decisões e `.claude/` no checkout principal. `raiz` é a árvore da sessão. Alvo vazio, ausente ou
    relativo sem `cwd` não decide."""
    chave = _ALVO_POR_FERRAMENTA.get(tool_name)
    bruto = tool_input.get(chave) if chave else None
    if not isinstance(bruto, str) or not bruto:
        return None
    alvo = _absoluto(bruto, cwd)
    achado = relativo_na_arvore(alvo) if alvo is not None else None
    if achado is None:
        return None
    raiz_alvo, relativo = achado
    sessao = _sessao(raiz, perfil)
    if not mesma_arvore(raiz_alvo, sessao.arvore):
        return _outra_arvore(alvo, raiz_alvo, sessao)
    comum_ = _comum(perfil)
    if proibido(relativo, comum_.segredos_isentos) is None:
        padroes = segredos.compilar(comum_.segredos)
        achados = (segredos.achar(texto, padroes) for texto in conteudos(tool_name, tool_input))
        nome = next((achado for achado in achados if achado is not None), None)
        if nome is not None:
            return _segredo(nome)
    if arquivo_de_ambiente(relativo):
        return _ambiente(relativo)
    if proibido(relativo, comum_.proibidos) is not None:
        return _proibido(relativo)
    if isinstance(perfil, PerfilDesenvolvimento):
        if relativo.casefold() == _LANES.casefold():
            return _negar(_MENSAGEM_LANES)
        dentro = next((mensagem for alcance, _, mensagem in _regra_9(relativo, sessao, None) if alcance == _DENTRO),
                      None)
        return _negar(dentro) if dentro is not None else _fora_da_lane(relativo, sessao)
    if not isinstance(perfil, Perfil):
        return None
    gerado = _gerado(relativo, perfil)
    if gerado is not None:
        return gerado
    if relativo in sessao.documentos:
        return _documento_em_aprovacao(relativo, sessao)
    decisoes = posixpath.normpath(perfil.caminhos.decisoes)
    if relativo == decisoes and tool_name in ("Edit", "Write"):
        linha = _linha_tirada_na_edicao(tool_name, tool_input, alvo)
        if linha is not None:
            return _negar(
                f"{decisoes} só aceita acréscimos: a edição tira ou altera a linha {linha}; acrescente uma linha nova"
            )
    if sessao.principal and sobrepoe(relativo, _PASTA_DO_HARNESS):
        return _harness_no_principal(relativo)
    return None


def _outra_arvore_bash(caminho: Path, sessao: _Sessao) -> Decisao | None:
    """A regra 3 para um alvo do Bash: a recusa do alvo noutra árvore."""
    achado = relativo_na_arvore(caminho)
    if achado is None or mesma_arvore(achado[0], sessao.arvore):
        return None
    return _outra_arvore(caminho, achado[0], sessao)


def _protegidos(perfil: PerfilDesenvolvimento) -> tuple[tuple[str, str], ...]:
    """Os protegidos da regra 9, em ordem, com a mensagem: a cópia da passagem, os padrões `<blocos>/*/aceitacao.md`,
    `<blocos>/*/estado.md`, `<blocos>/*/revisao.md` e `<blocos>/*/gabarito.md` e, no fim, os quatro alvos do `gerar`
    (regra 7): o `AGENTS.md` da raiz, a legenda (`caminhos.legenda`) e as duas pastas do gerador. A spec aprovada,
    que depende do `estado.md`, fica com o `_regra_9`."""
    blocos = posixpath.normpath(perfil.caminhos.blocos)
    return ((posixpath.normpath(perfil.caminhos.passagem), _MENSAGEM_COPIA),
            (f"{blocos}/*/{bloco.ARQUIVO_DA_ACEITACAO}", _MENSAGEM_ACEITACAO),
            (f"{blocos}/*/{bloco.ARQUIVO}", _MENSAGEM_ESTADO),
            (f"{blocos}/*/{bloco.ARQUIVO_DA_REVISAO}", _MENSAGEM_REVISAO),
            (f"{blocos}/*/{bloco.ARQUIVO_DO_GABARITO}", _MENSAGEM_GABARITO),
            (gerador.AGENTS, _MENSAGEM_GERADO_DO_CODIGO),
            (ci.CAMINHO, _MENSAGEM_GERADO_DO_CODIGO),
            (posixpath.normpath(perfil.caminhos.legenda), _MENSAGEM_GERADO_DO_CODIGO),
            (gerador.PASTA_DAS_REGRAS, _MENSAGEM_GERADO_DO_CODIGO),
            (gerador.PASTA_DOS_GERADOS, _MENSAGEM_GERADO_DO_CODIGO))


def _alcance(relativo: str, protegido: str, alvo: Path | None) -> str | None:
    """O alcance do alvo sobre o protegido, sem distinguir maiúsculas: `_DENTRO`, o protegido ou algo nele (na cópia)
    ou o arquivo do padrão; `_PASTA`, a raiz (`.`) ou uma pasta que existe e o contém (os segmentos do começo do
    padrão, cada um pelo `fnmatchcase`); ou None. Sem o `alvo` no disco, só o `_DENTRO` vale."""
    if relativo == ".":
        return _PASTA
    segmentos, partes = relativo.casefold().split("/"), protegido.casefold().split("/")
    casam = all(fnmatch.fnmatchcase(segmento, parte) for segmento, parte in zip(segmentos, partes))
    if casam and (len(segmentos) == len(partes) or ("*" not in protegido and len(segmentos) > len(partes))):
        return _DENTRO
    if casam and len(segmentos) < len(partes) and alvo is not None and alvo.is_dir():
        return _PASTA
    return None


def _spec_aprovada(relativo: str, sessao: _Sessao) -> bool:
    """O alvo é a `<blocos>/<pasta>/spec.md`, sem distinguir maiúsculas, e o `estado.md` dessa pasta, na árvore da
    sessão, se lê com o estado efetivo fora de `planning` (spec 6d-bloco, §8.6). Sem o `estado.md`, ou com ele
    ilegível, a spec não conta como aprovada."""
    padrao = f"{posixpath.normpath(sessao.perfil.caminhos.blocos)}/*/{bloco.ARQUIVO_DA_SPEC}"
    if _alcance(relativo, padrao, None) != _DENTRO:
        return False
    estado_md = sessao.arvore / posixpath.dirname(relativo) / bloco.ARQUIVO
    try:
        lido = bloco.ler_estado(comum.ler_texto(estado_md), str(estado_md))
    except (bloco.Recusa, OSError, UnicodeDecodeError):
        return False
    return lido.efetivo != "planning"


def _regra_9(relativo: str, sessao: _Sessao, alvo: Path | None) -> list[tuple[str, str, str]]:
    """Os alcances do alvo sobre os protegidos da regra 9 e dos gerados do `gerar`, na ordem deles, com o protegido
    como a lista o escreve e a mensagem de cada um; no fim, a spec aprovada, que só tem o alcance `_DENTRO`."""
    achados = [(_alcance(relativo, protegido, alvo), protegido, mensagem)
               for protegido, mensagem in _protegidos(sessao.perfil)]
    if _spec_aprovada(relativo, sessao):
        achados.append((_DENTRO, relativo, _MENSAGEM_SPEC))
    return [achado for achado in achados if achado[0] is not None]


def _fora_da_lane(relativo: str, sessao: _Sessao) -> Decisao | None:
    """Fora de lane, nega o alvo que não casa nenhum padrão do `fora_da_lane`."""
    padroes = sessao.perfil.fora_da_lane
    if sessao.na_lane or comum.padrao_que_casa(relativo, padroes) is not None:
        return None
    return _negar(f"fora de lane, só se grava em {comum.juntar(padroes)}; abra uma lane com harness.py lane abrir "
                  "<ficha>")


def _regras_do_desenvolvimento_bash(caminho: Path, relativo: str, sessao: _Sessao, restauracao: bool,
                                    no_disco: bool) -> Decisao | None:
    """As regras 7 e 9 do desenvolvimento para um alvo do Bash. O `LANES.md` é negado também na restauração. Fora
    dela, o alvo com alcance é negado pelo primeiro: a pasta que contém a cópia ou um arquivo de bloco, com a
    mensagem da pasta (spec 6d-bloco, §12, item 6), e o resto com a mensagem do protegido; o alvo sem alcance passa
    pelo `fora_da_lane`. A pasta que contém um gerado do `gerar` (a raiz, `.claude` ou `.claude/harness`, por
    exemplo) conta como alcance quando existe, como a que contém a cópia, e leva a mensagem da pasta com gerados. A
    restauração de dentro de um protegido, um gerado inclusive, passa; as outras passam pelo `fora_da_lane` e, a de
    uma pasta que contém um protegido e volta o disco, pergunta."""
    if relativo.casefold() == _LANES.casefold():
        return _negar(_MENSAGEM_LANES)
    alcances = _regra_9(relativo, sessao, caminho)
    if not restauracao:
        if not alcances:
            return _fora_da_lane(relativo, sessao)
        alcance, protegido, mensagem = alcances[0]
        if alcance == _PASTA:
            modelo = _MENSAGEM_PASTA_COM_GERADOS if mensagem == _MENSAGEM_GERADO_DO_CODIGO else _MENSAGEM_PASTA
            return _negar(modelo.format(relativo, protegido))
        return _negar(mensagem)
    if any(alcance == _DENTRO for alcance, _, _ in alcances):
        return None
    fora = _fora_da_lane(relativo, sessao)
    if fora is not None:
        return fora
    if no_disco and alcances:
        return _perguntar(_MENSAGEM_RESTAURACAO_AMPLA.format(relativo))
    return None


def _decidir_caminho_bash(caminho: Path, sessao: _Sessao, restauracao: bool = False,
                          no_disco: bool = False) -> Decisao | None:
    """As regras 5 a 9 para um alvo do Bash na árvore da sessão; o de outra árvore fica com `_outra_arvore_bash`. A
    restauração é o `git restore` ou o `git checkout --` que volta o arquivo ao índice ou ao HEAD; `no_disco`, a que
    volta também o disco. No desenvolvimento, as regras 7 e 9 são as do `_regras_do_desenvolvimento_bash`."""
    achado = relativo_na_arvore(caminho)
    if achado is None or not mesma_arvore(achado[0], sessao.arvore):
        return None
    relativo = achado[1]
    if arquivo_de_ambiente(relativo):
        return _ambiente(relativo)
    if proibido(relativo, _comum(sessao.perfil).proibidos) is not None:
        return _proibido(relativo)
    if isinstance(sessao.perfil, PerfilDesenvolvimento):
        return _regras_do_desenvolvimento_bash(caminho, relativo, sessao, restauracao, no_disco)
    if not isinstance(sessao.perfil, Perfil):
        return None
    gerado = _gerado(relativo, sessao.perfil)
    if gerado is not None:
        return gerado
    if sobrepoe(relativo, sessao.perfil.moldes.pasta):
        return _moldes(relativo, sessao)
    if sobrepoe(relativo, sessao.perfil.caminhos.status):
        return _status(sessao)
    for documento in sessao.documentos:
        if sobrepoe(relativo, documento):
            return _documento_em_aprovacao(documento, sessao)
    if sessao.principal and sobrepoe(relativo, _PASTA_DO_HARNESS):
        return _harness_no_principal(relativo)
    return None


def _decidir_diretorio_git(diretorio: Path, sessao: _Sessao) -> Decisao | None:
    raiz_alvo = raiz_da_arvore(diretorio)
    if raiz_alvo is None or mesma_arvore(raiz_alvo, sessao.arvore):
        return None
    return _outra_arvore(diretorio, raiz_alvo, sessao)


def _decidir_codigo(codigo: str, sessao: _Sessao) -> Decisao | None:
    """O código de `-c` ou `-e` é comparado só com a parte fixa dos `proibidos` do perfil e, com o perfil de
    planejamento, os moldes, o STATUS, os arquivos gerados e os documentos em aprovação (desvio 6 da 3b), pelo texto
    relativo e pelo absoluto."""
    fixas = [_parte_fixa(padrao) for padrao in _comum(sessao.perfil).proibidos]
    protegidos = [(fixa, _proibido(fixa)) for fixa in fixas]
    if not isinstance(sessao.perfil, Perfil):
        return next((decisao for relativo, decisao in protegidos
                     if relativo in codigo or str(sessao.raiz / relativo) in codigo), None)
    protegidos += [
        (sessao.perfil.moldes.pasta, _moldes(sessao.perfil.moldes.pasta, sessao)),
        (sessao.perfil.caminhos.status, _status(sessao)),
    ]
    gerados = [sessao.perfil.caminhos.legenda]
    if sessao.perfil.passagem is not None:
        gerados.append(sessao.perfil.passagem.manifesto)
    protegidos += [(gerado, _gerado(gerado, sessao.perfil)) for gerado in gerados if gerado]
    protegidos += [(documento, _documento_em_aprovacao(documento, sessao)) for documento in sessao.documentos]
    for relativo, decisao in protegidos:
        if relativo in codigo or str(sessao.raiz / relativo) in codigo:
            return decisao
    return None


def decidir_bash(
    comando: str, cwd: Path | None, raiz: Path, perfil: Perfil | PerfilDesenvolvimento | PerfilComum,
    ambiente: Mapping[str, str],
) -> Decisao | None:
    """A decisão sobre o comando (spec 3b, §6.2, e 6c, §6.5), nesta ordem: a outra árvore, para cada alvo e cada
    diretório de git; o segredo no texto inteiro do comando, sem isenção; as regras 5 a 9, para cada alvo; o código
    de `-c`; e as perguntas, as do `harness.py` depois das do git. O primeiro `deny` nessa ordem vence; sem `deny`,
    um `ask` com os motivos de todos, na ordem, sem repetir, separados por `; `, e o
    `; confirme só se o usuário pediu` uma vez só, no fim. O arquivo de decisões não é julgado aqui: `cat >>` é
    acréscimo, e o Stop confere."""
    alvos = escrita.alvos(comando, cwd if cwd is not None else raiz, ambiente)
    sessao = _sessao(raiz, perfil)
    decisoes = [_outra_arvore_bash(caminho, sessao) for caminho in alvos.caminhos]
    decisoes += [_decidir_diretorio_git(diretorio, sessao) for diretorio in alvos.diretorios_git]
    nome = segredos.achar(comando, segredos.compilar(_comum(perfil).segredos))
    decisoes.append(_segredo(nome) if nome is not None else None)
    decisoes += [_decidir_caminho_bash(caminho, sessao, caminho in alvos.restauracoes,
                                       caminho in alvos.restauracoes_no_disco) for caminho in alvos.caminhos]
    decisoes += [_decidir_codigo(codigo, sessao) for codigo in alvos.codigos]
    if alvos.sem_verificacao:
        decisoes.append(_perguntar(_MENSAGEM_SEM_VERIFICACAO))
    if alvos.push_sem_verificacao and isinstance(perfil, PerfilDesenvolvimento):
        decisoes.append(_perguntar(_MENSAGEM_PUSH_SEM_VERIFICACAO))
    decisoes += [_perguntar(_MENSAGENS_DESTRUTIVAS[destrutivo] + _CONFIRME)
                 for destrutivo in alvos.destrutivos]
    for palavras in alvos.harness:
        normais = {palavra.split("=", 1)[0] if palavra.startswith("--") else palavra for palavra in palavras}
        decisoes += [_perguntar(mensagem) for exigidas, mensagem in _PERGUNTAS_DO_HARNESS if exigidas <= normais]
    for decisao in decisoes:
        if decisao is not None and decisao.tipo == DENY:
            return decisao
    motivos = [decisao.mensagem[len(PREFIXO):] for decisao in decisoes if decisao is not None]
    if not motivos:
        return None
    confirme = any(motivo.endswith(_CONFIRME) for motivo in motivos)
    sem_confirme = dict.fromkeys(motivo[:-len(_CONFIRME)] if motivo.endswith(_CONFIRME) else motivo
                                 for motivo in motivos)
    return _perguntar("; ".join(sem_confirme) + (_CONFIRME if confirme else ""))


def saida_pre_tool(decisao: Decisao | None) -> dict | None:
    """O JSON do PreToolUse para a decisão; None sem decisão (stdout vazio)."""
    if decisao is None:
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decisao.tipo,
            "permissionDecisionReason": decisao.mensagem,
        }
    }


def decidir_pre_tool(
    payload: dict, raiz: Path, perfil: Perfil | PerfilDesenvolvimento | PerfilComum, ambiente: Mapping[str, str]
) -> dict | None:
    """A saída do PreToolUse para o payload: Edit, Write e NotebookEdit por `decidir_edicao`, Bash por
    `decidir_bash`; outra ferramenta, ou payload sem `tool_input`, None."""
    entrada = payload.get("tool_input") if isinstance(payload, dict) else None
    if not isinstance(entrada, dict):
        return None
    bruto = payload.get("cwd")
    cwd = Path(bruto) if isinstance(bruto, str) and os.path.isabs(bruto) else None
    ferramenta = payload.get("tool_name")
    if ferramenta in _ALVO_POR_FERRAMENTA:
        return saida_pre_tool(decidir_edicao(ferramenta, entrada, cwd, raiz, perfil))
    comando = entrada.get("command")
    if ferramenta == "Bash" and isinstance(comando, str) and comando:
        return saida_pre_tool(decidir_bash(comando, cwd, raiz, perfil, ambiente))
    return None


def _sem_verificar(raiz: Path, lane: bloco.LaneViva, agora) -> bool:
    """A lane em que o Stop não verifica (spec 6d-bloco, §8.8): no estado efetivo `planning`, ou em `reviewing` com a
    marca da revisão em andamento ainda válida na hora de `agora()`."""
    if lane.bloco.efetivo == "planning":
        return True
    return lane.bloco.estado == "reviewing" and bloco.marca_da_revisao(raiz, agora()) is not None


def _stop_do_desenvolvimento(payload: dict, raiz: Path, perfil: PerfilDesenvolvimento, executar,
                             agora=datetime.datetime.now) -> dict | None:
    """O Stop da trilha de desenvolvimento (spec 6c, §11.2): as invariantes do modo `arvore` e, numa lane reconhecida
    pelos arquivos, as verificações de `stop` pela marca, com o prazo contado daqui. A falha bloqueia uma vez, com as
    linhas das verificações que falharam depois de uma quebra, e só avisa com `stop_hook_active`; sem falha, as
    puladas e as sem tempo vão num aviso. No `_sem_verificar`, as verificações não rodam, e a marca de verificação não
    é gravada (spec 6d-bloco, §8.8)."""
    prazo = time.monotonic() + verificacao.TETO_DO_STOP
    resumos = [conferencia.resumo for conferencia in invariantes.conferir(raiz, perfil, invariantes.ARVORE,
                                                                           executar=executar) if not conferencia.ok]
    detalhes: tuple[str, ...] = ()
    avisos: tuple[str, ...] = ()
    try:
        lane = bloco.lane_pelos_arquivos(raiz, perfil)
    except bloco.Recusa as erro:
        resumos.append(erro.mensagem)
        lane = None
    if lane is not None and not _sem_verificar(raiz, lane, agora):
        relatorio = verificacao.no_stop(raiz, perfil, lane, prazo, executar)
        if relatorio is not None:
            resumos.extend(relatorio.resumos)
            detalhes, avisos = relatorio.detalhes, relatorio.avisos
    if resumos:
        juntos = "; ".join(resumos)
        if payload.get("stop_hook_active"):
            return {"systemMessage": f"{PREFIXO}{juntos}; corrija antes de seguir"}
        return {"decision": "block", "reason": "\n".join((f"{PREFIXO}{juntos}. Corrija e pare de novo.", *detalhes))}
    if avisos:
        return {"systemMessage": PREFIXO + "; ".join(avisos)}
    return None


def decidir_stop(
    payload: dict, raiz: Path, perfil: Perfil | PerfilDesenvolvimento | PerfilComum, executar=subprocess.run,
    agora=datetime.datetime.now,
) -> dict | None:
    """As invariantes da árvore (spec 3b, §9), as da trilha do perfil: sem falha ou sem `.git` na raiz, None; com
    falha, bloqueia o fim do turno uma vez e, com `stop_hook_active`, só avisa. Com o perfil de desenvolvimento, o
    `_stop_do_desenvolvimento`, com o `agora` que conta a idade da marca da revisão. Lança ErroGit se o git não
    responde."""
    if not os.path.lexists(raiz / ".git"):
        return None
    if isinstance(perfil, PerfilDesenvolvimento):
        return _stop_do_desenvolvimento(payload, raiz, perfil, executar, agora)
    falhas = [conferencia for conferencia in invariantes.conferir(raiz, perfil, invariantes.ARVORE, executar=executar)
              if not conferencia.ok]
    if not falhas:
        return None
    resumos = "; ".join(conferencia.resumo for conferencia in falhas)
    if payload.get("stop_hook_active"):
        return {"systemMessage": f"{PREFIXO}{resumos}; o pre-commit vai recusar o commit"}
    motivo = (
        f"{PREFIXO}{resumos}. Desfaça com git restore <arquivo> o que não devia mudar, ou explique ao usuário por que "
        "mudou."
    )
    if any(conferencia.nome in _SO_O_USUARIO_DESFAZ for conferencia in falhas):
        # A guarda recusa ao modelo o git restore e o rm de molde e do STATUS (spec 3b, §6.2).
        motivo += " A guarda não deixa você desfazer mudança em molde nem no STATUS.md: peça ao usuário."
    return {"decision": "block", "reason": motivo}


def mensagem_de_erro(evento: str, erro: BaseException) -> str:
    """O `systemMessage` de um erro da guarda, numa linha; o do prompt é o do `anotacao.mensagem_de_erro`."""
    if evento == EVENTO_PROMPT:
        return anotacao.mensagem_de_erro(erro)
    return f"guarda do harness com erro, sem decisão: {anotacao.motivo_do_erro(erro)}"


def perfil_da_arvore(arvore: Path) -> tuple[Perfil | PerfilDesenvolvimento | PerfilComum, str | None]:
    """O perfil da árvore em duas camadas: a parte comum, cujo erro sobe, e o perfil da trilha. Com o da trilha
    inválido, fica a parte comum e o aviso
    `guarda do harness: perfil inválido: <motivo>; só as regras comuns valem`."""
    comum_ = perfil_comum.carregar(arvore)
    try:
        if comum_.harness == perfil_comum.DESENVOLVIMENTO:
            return perfil_desenvolvimento.carregar(arvore), None
        return carregar_perfil(arvore), None
    except PerfilInvalido as erro:
        return comum_, f"{PREFIXO}{erro.mensagem}; só as regras comuns valem"


def rodar(evento: str, entrada: str, ambiente: Mapping[str, str] | None = None) -> str:
    """A saída do hook `evento` (`pre-tool`, `prompt` ou `stop`) para o JSON `entrada`: o JSON da decisão, ou vazio.

    O prompt vai inteiro ao `anotacao.rodar`, que usa a raiz da sessão, `comum.raiz_projeto()`, e o perfil e o STATUS
    dela. Nos outros, o payload vem primeiro; o PreToolUse e o Stop usam a árvore da sessão, pelo `cwd` do payload
    (`arvore_da_sessao`), e o perfil dela, em duas camadas (`perfil_da_arvore`). O aviso do perfil da trilha inválido
    sai só quando nenhuma regra decide.
    `ambiente`, por padrão o do processo, é o que o Bash expande. Nunca lança: qualquer erro vira `systemMessage`,
    sem decisão.
    """
    if evento == EVENTO_PROMPT:
        return anotacao.rodar(entrada)
    ambiente = os.environ if ambiente is None else ambiente
    try:
        payload = json.loads(entrada)
        if not isinstance(payload, dict):
            raise ValueError("o payload não é um objeto JSON")
        raiz = comum.raiz_projeto()
        if evento in (EVENTO_PRE_TOOL, EVENTO_STOP):
            arvore = arvore_da_sessao(payload.get("cwd"), raiz)
            perfil, aviso = perfil_da_arvore(arvore)
            if evento == EVENTO_PRE_TOOL:
                saida = decidir_pre_tool(payload, arvore, perfil, ambiente)
            else:
                saida = decidir_stop(payload, arvore, perfil)
            if saida is None and aviso is not None:
                saida = {"systemMessage": aviso}
        else:
            raise ValueError(f"evento desconhecido: {evento}")
    except Exception as erro:  # o hook não pode derrubar a ferramenta, o prompt nem o fim do turno
        return json.dumps({"systemMessage": mensagem_de_erro(evento, erro)}, ensure_ascii=False)
    return json.dumps(saida, ensure_ascii=False) if saida is not None else ""
