"""Lanes dos blocos (spec 6c, §15): o `abrir` pelo portão, o `conferir` contra o origin e o `fechar` com o PR mesclado.

O portão roda na árvore principal e confere tudo antes de mudar qualquer coisa. Depois dele, a lane nasce como worktree
em `lane.pasta`, com o `.env` das portas dela, o `instalar`, a ficha do código nova e o primeiro commit do bloco; a
falha no meio deixa a lane pela metade, que o `lane fechar --abandonar` desfaz.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import aceitacao
import bloco
import comum
import contexto
import fichas
import importacao
import lanes
import perfil_desenvolvimento
import transicoes
import verificacao
from bloco import Aviso, EstadoDoBloco, Recusa, Saida
from fichas import Ficha

TEMPO_DOS_COMANDOS = 900
PLANO = "plano.md"

_RE_LINHA_DO_PLANO = re.compile(r"\s*- (?:Create|Modify|Test|Delete):(.*)")
_RE_CRASE = re.compile(r"`([^`]+)`")
_RE_LINHAS_DO_CAMINHO = re.compile(r":[0-9]+(?:-[0-9]+)?$")
_RE_RESOLVIDA = re.compile(r"Resolvida na passagem/v([1-9][0-9]*)")
_RE_SHA = re.compile(r"[0-9a-f]{40}")
_RE_NUMERO = re.compile(r"[1-9]")  # a lane é de 1 a 9, como o `estado.md`

AJUDA = """\
Abre, confere e fecha as lanes dos blocos. A lane é uma worktree em `<lane.pasta>/<ID>-<slug>`, na branch
`<tipo>/<ID>-<slug>`, com as portas da lane `k` e o bloco em `<blocos>/<ID>-<slug>/`.

`lane abrir <ficha> [--tipo <tipo>]` abre a lane da ficha. O tipo é um de `feat`, `fix`, `chore`, `refactor`, `infra`,
`cicd` e `docs`, `feat` por padrão; ele vai à branch e ao título do PR. O comando roda de qualquer árvore do
repositório e age na árvore principal.

O portão confere tudo antes de mudar qualquer coisa; a recusa é `portão recusou: <motivo>`, com saída 1:

1. o `git fetch` do ramo principal (`origin não consultado: <motivo>`); a árvore principal no ramo principal
   (`a árvore principal não está no <ramo_principal>`) e igual ao origin
   (`<ramo_principal> local à frente do origin; leve os commits por PR` e
   `<ramo_principal> local atrás do origin; rode git pull`). As alterações sem commit da árvore principal não impedem;
2. a ficha: a FICHA na cópia da passagem, a do código no backlog, também sem commit na árvore principal
   (`<ID> não existe`), sem bloco vivo (`<ID> já tem bloco (<estado>)`) nem fechado (`<ID> já fechada`), fora de outra
   lane (`<ID> está na lane de <ID da lane>; entra no <ramo_principal> com o PR dela`), num arquivo só
   (`<ID> em mais de um arquivo: <caminhos>`) e, na FICHA, com o slug do título na forma do `estado.md`
   (`<ID>: slug fora da forma: <slug>`);
3. a forma da ficha do código (`<ID>: <problema>`), a do `fichas`;
4. as dependências (`<ID> espera <dependência> (<estado>)`);
5. uma lane livre de 1 ao `lane.limite` (`<n> lanes vivas; o limite é <limite>`);
6. a branch livre na máquina e no origin (`a branch <branch> já existe`), pelo nome exato, e a pasta da lane
   (`a pasta <pasta> já existe`);
7. o `env_modelo`, quando o perfil o tem, no `origin/<ramo_principal>` (`<env_modelo> não existe no <ramo_principal>`),
   só com os marcadores `{porta.<nome>}`, `{n}`, `{id}` e `{slug}` (`<env_modelo> cita {<marcador>}, que não existe`);
8. o `.env` que o `env_modelo` gera (ele sem o `.example`) e cada `env_copiados` ignorados pelo git, pelo
   `git check-ignore` na árvore principal (`<arquivo> não é ignorado pelo git; ponha-o no .gitignore`).

Depois do portão, em ordem: o `git worktree add --no-track -b <branch> <pasta> origin/<ramo_principal>`, que recusa
com `git worktree add falhou: <motivo>`; o número da lane, no arquivo `harness-lane` do diretório do git da
worktree (`<repositório>/.git/worktrees/<pasta>/`), com uma quebra, para o `--abandonar` achá-lo sem o `estado.md`; o
`.env` do `env_modelo`, com os marcadores trocados; a cópia dos `env_copiados` da árvore principal; cada comando do
`instalar` por `sh -c` na lane, com os marcadores e o `{pasta}`, a pasta absoluta da lane, e 900 s cada; a ficha do
código nova, sem commit na árvore principal, movida para a lane; o `estado.md`, em `planning`, com a lane `k`, a `base`
no `origin/<ramo_principal>` e a `passagem` na versão da cópia; o `contexto.md`; o commit `chore(<ID>): abre a lane`; e
o `LANES.md`.

A saída:

- `portão ok: <ramo_principal> igual ao origin; <ID> aberta; <dependências>; lanes <n> de <limite>`, com as fichas do
  Depende em `<a e b> fechadas` e as pendências em `<a e b> resolvidas`, ou `sem dependências`;
- `lane <ID> aberta em <pasta>`;
- `  branch <branch>; lane <k>: <nome> <porta>, ...`;
- `  .env gerado do <env_modelo>; copiado <arquivos>; instalar ok`, só com as partes que valem;
- `  env_copiados: <arquivo> não existe na árvore principal; pulado`, uma por arquivo que falta;
- `  estado planning; Context Packet com <n> fatos`;
- `Para entrar: EnterWorktree com path <pasta>`.

Lane pela metade: a falha depois do `git worktree add` devolve à árvore principal a ficha do código que já tinha ido à
lane e dá `lane pela metade: <passo> falhou (<motivo>); desfaça com harness.py lane fechar <ID> --abandonar`, com
saída 1. O passo é `harness-lane`, `.env`, `env_copiados`, `instalar`, `ficha`, `estado.md`, `contexto.md` ou
`git commit`; a falha do
`instalar` é `<comando>: saída <código>` ou `<comando>: passou de 900 s`.

`lane conferir` confere as lanes contra o origin. Usa a rede: o `git fetch` do ramo principal, cuja falha é a única
recusa (`origin não consultado: <motivo>`), e, conforme o caso, o `gh pr list` e o `gh issue view`; por isso não roda
em hook. Sai com 0 e imprime, nesta ordem:

- as linhas das worktrees do `lanes`: a pasta sumida, a worktree sem bloco, o `estado.md` inválido e a branch de bloco
  sem worktree;
- por lane, na ordem das fichas:
  - no bloco em `closing`, o PR mesclado no ramo principal: `<ID>: PR #<n> mesclado; rode harness.py lane fechar <ID>`;
  - o bloco afetado pela versão da cópia do `origin/<ramo_principal>`, pelo estado dele: de `planning` a
    `ready_for_closure`, o bloco é travado, com `bloqueio: passagem` e o `motivo` `passagem/v<N> mudou <IDs>`, no
    commit `chore(<ID>): blocked` da lane, e a linha é `<ID>: passagem/v<N> mudou <IDs>; bloco travado (blocked)`, ou
    `<ID>: não travado: <motivo>` quando a trava falha; em `closing`, sem o PR mesclado,
    `<ID>: passagem/v<N> mudou <IDs>; em closing, o bloco não é travado: decida antes do merge`, e, com ele, nada; em
    `blocked`, `<ID>: passagem/v<N> mudou <IDs>; o bloco já está travado (<bloqueio>)`, que não sai quando o bloco já
    foi travado pela mesma versão;
  - no bloco em `blocked` por `retorno`, cada retorno de decisão cuja issue, no repositório da passagem, está fechada
    com um comentário `Resolvida na passagem/v<N>`:
    `<ID>: retorno #<n> resolvido na passagem/v<N>; traga o <ramo_principal> e rode harness.py bloco desbloquear --replanejar`,
    ou `<ID>: retorno #<n> não consultado: <motivo>`;
- os planos que se cruzam, um par de lanes por linha: `<ID> e <ID>: os dois planos mexem em <caminhos>`, pelos
  caminhos entre crases das linhas `- Create:`, `- Modify:`, `- Test:` e `- Delete:` do `plano.md` de cada bloco, sem
  o `:N` ou `:N-M` do fim.

Sem nada a apontar, `lanes em ordem`. No fim, regrava o `LANES.md`.

`lane fechar <ficha> [--manual <n>=ok|falhou ...]` fecha a lane do bloco em `closing` depois do merge do PR. Roda de
fora da lane que fecha (`lane fechar: rode fora da lane <ID>`) e de uma sessão que não foi aberta nela, a de
`CLAUDE_PROJECT_DIR` fora da lane; com a sessão aberta dentro, recusa:
`lane fechar: a sessão foi aberta dentro da lane <ID>; feche a lane de uma sessão aberta na árvore principal, ou pelo terminal como última ação`.
Usa a rede: o `git fetch` do ramo principal, que vem primeiro, o `gh pr list`, o `gh pr view` e o `gh pr comment`. Em
ordem:

1. as recusas, sem mudar nada: `lane fechar: <ID> não tem lane`, `<ID> está em <estado>; lane fechar vale só em closing`
   e `a lane tem alterações sem commit; faça o commit ou descarte antes`. Com a pasta da lane sumida, o `estado.md` e
   o `aceitacao.md` vêm do commit da branch, o commit do PR é a ponta dela, e as alterações sem commit não se
   conferem;
2. o PR da branch, pela precedência: um aberto recusa (`PR #<n> ainda aberto; mescle antes`); senão, vale o mesclado
   de maior número com base no ramo principal, e o resto não conta; sem ele, a recusa é
   `<branch> sem PR; rode harness.py bloco finalizar na lane`. O commit do PR é o HEAD da lane; um commit anterior dá
   a recusa `a lane tem <k> commit(s) depois do PR #<n>, que já foi mesclado; ...`, que termina no
   `git reset --hard <sha>` de volta ao commit do PR, e um commit fora da lane,
   `o PR #<n> foi mesclado com <sha>, que não está na lane; confira antes de fechar`;
3. a aceitação de depois do merge: as provas automáticas de depois, como no `aceitacao conferir --depois`, e os itens
   manuais de depois pelo `--manual <n>=ok|falhou`, repetível. Antes de qualquer prova, o `--manual` recusa
   `item <n> não existe`, `item <n> é de antes do merge; anote com harness.py aceitacao anotar na lane` e
   `item <n> tem prova automática; o lane fechar a confere`. Com efeito externo, o veredito pendente deixa a lane como
   está e dá `ACEITACAO PENDENTE: ...; a lane fica; rode de novo quando o deploy terminar`, com saída 1;
4. o comentário no PR, com `Aceitação depois do merge:`, as linhas dos itens e o veredito, uma por linha, só quando
   nenhum comentário do PR tem o mesmo corpo. A falha do `gh pr view` ou do `gh pr comment` deixa a lane e dá
   `gh pr comment falhou: <motivo>; a lane fica; rode harness.py lane fechar <ID> de novo`, com o comando que falhou,
   e saída 1;
5. o `desmontar`: cada comando por `sh -c` na lane, com os marcadores e o `{pasta}`, e 900 s cada; todos rodam, e
   os que falham viram aviso e não param o fechamento;
6. a remoção: `git worktree remove <pasta>`, que aceita os arquivos ignorados, e `git branch -D <branch>`, cujas falhas
   recusam com `git worktree remove falhou: <motivo>` e `git branch -D falhou: <motivo>`; e o `LANES.md`.

A saída do fechamento:

- `PR #<n> mesclado, com o mesmo commit da lane`;
- `aceitação depois do merge: <linhas dos itens>`, com as linhas separadas por `; `, ou `nenhum item`;
- o veredito, com `; comentado no PR #<n>` ou `; já comentado no PR #<n>`;
- `desmontar ok; worktree e branch removidas`, `desmontar falhou: <comando> (saída <c>); worktree e branch removidas`,
  com `(passou de 900 s)` no tempo esgotado e as falhas juntadas por `e`, ou, sem `desmontar`,
  `worktree e branch removidas`; com a pasta sumida, o `desmontar` não roda, e a linha é
  `desmontar pulado: a pasta da lane sumiu; worktree e branch removidas`.

`lane fechar <ficha> --abandonar` remove a lane sem PR mesclado, em qualquer estado, também a lane pela metade e a de
pasta sumida; não combina com o `--manual`. A lane é a worktree em `lane.pasta` cuja pasta começa por `<ID>-`.
Recusa a lane em que a sessão foi aberta, como o `lane fechar` (`a sessão foi aberta dentro da lane <ID>`). Pula a
aceitação e o comentário e confere só duas coisas:

- a lane sem alteração sem commit; na lane pela metade, a de `estado.md` sem commit ou sem ele, não contam o
  `estado.md`, o `contexto.md` e a ficha do código do bloco, novos;
- nenhum PR da branch aberto (`PR #<n> aberto; feche-o antes de abandonar`), que recusa primeiro, nem mesclado no ramo
  principal (`PR #<n> já mesclado; feche a lane com harness.py lane fechar <ID>`).

A ficha do código do bloco que está na lane e não está nem na árvore principal nem no `origin/<ramo_principal>` volta
à árvore principal, sem commit; com a pasta sumida, a do commit da branch, se ele a tem. Depois vêm o `desmontar`, que
não roda com a pasta sumida, a remoção, com o `--force` na lane pela metade, e o `LANES.md`. A saída é
`lane <ID> abandonada; a ficha fica <estado>`, com o estado do `fichas`, ou `lane <ID> abandonada; a ficha não existe`,
quando o ID não tem ficha, lane nem bloco, depois de `desmontar falhou: <comando> (saída <c>)` ou de
`desmontar pulado: sem o estado.md, a lane não tem número`, quando valem. O `desmontar` usa o número do `estado.md` da
lane; sem ele legível, o do `harness-lane`, que o `lane abrir` grava e que sobra mesmo com o commit dele recusado, e o
slug da pasta; o `pulado` é para a lane sem nenhum dos dois, ou com o do arquivo fora de 1 ao `lane.limite`. O estado
da ficha se calcula sem a outra lane
cujo `estado.md` está fora do formato ou não se lê, e cada uma dessas vira, depois da linha da ficha, uma linha
`atenção: <caminho>: estado.md inválido: <motivo>` ou `atenção: <caminho>: estado.md ilegível: <motivo>`; o abandono
conclui com 0.

Com a `[desenvolvimento.linear]` no perfil, o `lane abrir`, o `lane conferir` que trava um bloco e o `lane fechar`, com
ou sem `--abandonar`, avisam o Linear depois de imprimir as linhas (`harness.py linear` traz o formato do comentário).
O `abrir` diz `pronta → planning`; o `conferir`, uma vez por bloco travado, `<estado> → blocked`, com o motivo; o
`fechar`, `closing → fechada`, com o link do PR mesclado, e o `--abandonar`, `<estado> → pronta (lane abandonada)`,
que devolve a ficha ao status `pronta`; a lane pela metade, sem o `estado.md` no commit, não avisa. O `--abandonar` com o
`estado.md` fora do formato ou ilegível não sabe o estado a avisar e diz, depois das outras linhas,
`linear: aviso não enviado (estado.md ilegível); acerte o status da issue à mão`, porque o espelho não recua uma issue.
O aviso não muda a saída nem o código de saída.
"""


def trocar_marcadores(texto: str, perfil, numero: int, id_: str, slug: str, pasta: Path | None = None) -> str:
    """Troca `{porta.<nome>}`, `{n}`, `{id}`, `{slug}` e, com a `pasta`, `{pasta}`; o `${...}` do shell e os outros
    ficam como estão."""
    valores = {"n": str(numero), "id": id_, "slug": slug}
    valores.update({f"porta.{nome}": str(perfil.lane.porta(nome, numero)) for nome, _ in perfil.lane.portas})
    if pasta is not None:
        valores["pasta"] = str(pasta)
    return perfil_desenvolvimento.RE_MARCADOR.sub(lambda achado: valores.get(achado.group(1), achado.group(0)), texto)


@dataclass(frozen=True)
class _Abertura:
    """O que o portão confere e o resto do `abrir` usa."""

    ficha: Ficha
    ramo: str
    pasta: Path
    numero: int
    base: str
    env: str | None  # o texto do `env_modelo` no ramo principal
    linha: str  # a linha `portão ok: ...`


def _env_da_lane(env_modelo: str) -> str:
    return env_modelo[:-len(perfil_desenvolvimento.SUFIXO_DO_MODELO)]


def _da_passagem(id_: str) -> bool:
    return id_.rsplit("-", 1)[0] == fichas.PREFIXO_DA_PASSAGEM


def _contagem(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _no_principal(principal: Path, perfil, executar) -> str:
    """Item 1 do portão: o fetch, a branch e a divergência; devolve o sha do `origin/<ramo_principal>`."""
    ramo = perfil.ramo_principal
    importacao.buscar_principal(principal, perfil, executar)
    cabeca = bloco.git(principal, ["symbolic-ref", "-q", "--short", "HEAD"], executar)
    if cabeca.returncode != 0 or cabeca.stdout.decode("utf-8", errors="replace").strip() != ramo:
        raise Recusa(f"a árvore principal não está no {ramo}")
    contagem = bloco.git(principal, ["rev-list", "--left-right", "--count",
                                     f"refs/heads/{ramo}...refs/remotes/origin/{ramo}"], executar)
    if contagem.returncode != 0:
        raise Recusa(f"git rev-list falhou: {comum.motivo_do_git(contagem, 'rev-list')}")
    frente, atras = (int(valor) for valor in contagem.stdout.decode("utf-8", errors="replace").split())
    if frente:
        raise Recusa(f"{ramo} local à frente do origin; leve os commits por PR")
    if atras:
        raise Recusa(f"{ramo} local atrás do origin; rode git pull")
    base = bloco.git(principal, ["rev-parse", f"refs/remotes/origin/{ramo}"], executar)
    return base.stdout.decode("utf-8", errors="replace").strip()


def _ficha(quadro: fichas.Quadro, perfil, id_: str) -> tuple[Ficha, str]:
    """Itens 2 a 4 do portão: a ficha, o bloco, os repetidos, o slug, a forma e as dependências; devolve a ficha e a
    situação."""
    situacao = fichas.situacao(id_, quadro, perfil)
    for comeco in ("em bloco (", "bloco sem lane ("):
        if situacao.startswith(comeco):
            raise Recusa(f"{id_} já tem bloco ({situacao[len(comeco):-1]})")
    if situacao == "fechada":
        raise Recusa(f"{id_} já fechada")
    if situacao.startswith("na lane "):
        raise Recusa(f"{id_} está na lane de {quadro.so_nas_lanes[id_]}; "
                     f"entra no {perfil.ramo_principal} com o PR dela")
    ficha = next((ficha for ficha in quadro.fichas if ficha.id == id_), None)
    if ficha is None:
        raise Recusa(f"{id_} não existe")
    if id_ in quadro.repetidas:
        raise Recusa(f"{id_} em mais de um arquivo: {comum.juntar(quadro.repetidas[id_])}")
    if _da_passagem(id_):
        if not fichas.RE_SLUG.fullmatch(ficha.slug):
            raise Recusa(f"{id_}: slug fora da forma: {ficha.slug}")
    else:
        problema = fichas.problema_de_forma(ficha, perfil.prefixo)
        if problema is not None:
            raise Recusa(f"{id_}: {problema}")
    if situacao.startswith("espera "):
        raise Recusa(f"{id_} {situacao}")
    return ficha, situacao


def _branch_livre(principal: Path, ramo: str, executar) -> None:
    """Item 6 do portão, a branch: nem na máquina nem no origin, pelo nome exato."""
    ref = f"refs/heads/{ramo}"
    if bloco.git(principal, ["rev-parse", "--verify", "-q", ref], executar).returncode == 0:
        raise Recusa(f"a branch {ramo} já existe")
    feito, motivo = importacao.falha(["git", "-C", str(principal), "ls-remote", "--heads", "origin", ref],
                                     "ls-remote", executar, importacao.TEMPO_LIMITE_GH)
    if motivo is not None:
        raise Recusa(f"git ls-remote falhou: {motivo}")
    if any(linha.split("\t")[-1] == ref for linha in feito.stdout.decode("utf-8", errors="replace").splitlines()):
        raise Recusa(f"a branch {ramo} já existe")


def nao_ignorados(principal: Path, perfil, executar) -> Iterator[str]:
    """Os arquivos da lane que o git não ignora, na ordem do item 8 do portão: o `.env` que o `env_modelo` gera e os
    `env_copiados`. Um por vez, para o portão parar no primeiro; um `check-ignore` que falha de verdade vira `Recusa`."""
    lane_ = perfil.lane
    arquivos = ([_env_da_lane(lane_.env_modelo)] if lane_.env_modelo else []) + list(lane_.env_copiados)
    for arquivo in arquivos:
        feito = bloco.git(principal, ["check-ignore", "-q", "--", arquivo], executar)
        if feito.returncode == 1:
            yield arquivo
        elif feito.returncode != 0:
            raise Recusa(f"git check-ignore falhou: {comum.motivo_do_git(feito, 'check-ignore')}")


def _env(principal: Path, perfil, executar) -> str | None:
    """Itens 7 e 8 do portão: o `env_modelo` no ramo principal, com os marcadores do §5.3, e os arquivos da lane
    ignorados pelo git; devolve o texto do modelo, ou None sem ele."""
    lane_, ramo = perfil.lane, perfil.ramo_principal
    texto = None
    if lane_.env_modelo:
        lido = bloco.git(principal, ["cat-file", "blob", f"refs/remotes/origin/{ramo}:{lane_.env_modelo}"], executar)
        if lido.returncode != 0:
            raise Recusa(f"{lane_.env_modelo} não existe no {ramo}")
        texto = lido.stdout.decode("utf-8", errors="replace")
        validos = {"n", "id", "slug", *(f"porta.{nome}" for nome, _ in lane_.portas)}
        for marcador in perfil_desenvolvimento.marcadores(texto):
            if marcador not in validos:
                raise Recusa(f"{lane_.env_modelo} cita {{{marcador}}}, que não existe")
    for arquivo in nao_ignorados(principal, perfil, executar):
        raise Recusa(f"{arquivo} não é ignorado pelo git; ponha-o no .gitignore")
    return texto


def _portao(principal: Path, perfil, id_: str, tipo: str, executar) -> _Abertura:
    """Os oito itens do portão (spec 6c, §15.1), na ordem; a recusa é a do primeiro que falha."""
    base = _no_principal(principal, perfil, executar)
    quadro = fichas.quadro(principal, perfil, executar)
    ficha, _ = _ficha(quadro, perfil, id_)
    vivas, limite = len(quadro.lanes), perfil.lane.limite
    usadas = {lane_.bloco.lane for lane_ in quadro.lanes}
    numero = next((k for k in range(1, limite + 1) if k not in usadas), None)
    if vivas >= limite or numero is None:
        raise Recusa(f"{_contagem(vivas, 'lane viva', 'lanes vivas')}; o limite é {limite}")
    ramo = f"{tipo}/{id_}-{ficha.slug}"
    _branch_livre(principal, ramo, executar)
    pasta = principal / perfil.lane.pasta / f"{id_}-{ficha.slug}"
    if pasta.exists() or pasta.is_symlink():
        raise Recusa(f"a pasta {pasta.relative_to(principal).as_posix()} já existe")
    env = _env(principal, perfil, executar)
    dependencias = fichas.dependencias(ficha, perfil.prefixo)
    pendencias = [id_dep for id_dep in dependencias if id_dep.rsplit("-", 1)[0] == fichas.PREFIXO_DA_PENDENCIA]
    outras = [id_dep for id_dep in dependencias if id_dep not in pendencias]
    partes = []
    if outras:
        partes.append(f"{comum.juntar(outras)} {'fechada' if len(outras) == 1 else 'fechadas'}")
    if pendencias:
        partes.append(f"{comum.juntar(pendencias)} {'resolvida' if len(pendencias) == 1 else 'resolvidas'}")
    linha = (f"portão ok: {perfil.ramo_principal} igual ao origin; {id_} aberta; "
             f"{'; '.join(partes) or 'sem dependências'}; lanes {vivas} de {limite}")
    return _Abertura(ficha, ramo, pasta, numero, base, env, linha)


class _PassoFalhou(Exception):
    """A falha de um comando do `instalar`, com o motivo."""


def _instalar(perfil, abertura: _Abertura) -> None:
    ficha = abertura.ficha
    for comando in perfil.lane.instalar:
        trocado = trocar_marcadores(comando, perfil, abertura.numero, ficha.id, ficha.slug, abertura.pasta)
        codigo, _ = verificacao.rodar_comando(trocado, abertura.pasta, TEMPO_DOS_COMANDOS)
        if codigo is None:
            raise _PassoFalhou(f"{comando}: passou de {TEMPO_DOS_COMANDOS} s")
        if codigo != 0:
            raise _PassoFalhou(f"{comando}: saída {codigo}")


def _ficha_nova(principal: Path, perfil, ficha: Ficha, executar) -> bool:
    """Se a ficha é do código e não está no `origin/<ramo_principal>`: a nova, sem commit na árvore principal."""
    if _da_passagem(ficha.id) or not (principal / ficha.arquivo).is_file():
        return False
    objeto = f"refs/remotes/origin/{perfil.ramo_principal}:{ficha.arquivo}"
    return bloco.git(principal, ["cat-file", "-e", objeto], executar).returncode != 0


def _gravar_numero(pasta: Path, numero: int) -> None:
    """Grava o número da lane no `harness-lane` do diretório do git da worktree, com uma quebra; sem esse diretório,
    nada."""
    gitdir = comum.diretorio_do_git(pasta)
    if gitdir is not None:
        comum.escrever_texto(gitdir / bloco.ARQUIVO_DA_LANE, f"{numero}\n")


def _numero_gravado(pasta: Path, perfil) -> int | None:
    """O número que o `abrir` gravou no diretório do git da worktree, ou None: sem o arquivo, ilegível, fora da forma
    ou acima do `lane.limite` do perfil."""
    gitdir = comum.diretorio_do_git(pasta)
    if gitdir is None:
        return None
    try:
        texto = comum.ler_texto(gitdir / bloco.ARQUIVO_DA_LANE).strip()
    except (OSError, UnicodeDecodeError):
        return None
    if _RE_NUMERO.fullmatch(texto) is None or int(texto) > perfil.lane.limite:
        return None
    return int(texto)


def _motivo_da_falha(erro: Exception) -> str:
    """O motivo da lane pela metade; a recusa do commit, sem o `git commit falhou: ` que o passo já diz."""
    if isinstance(erro, Recusa):
        comeco = "git commit falhou: "
        return erro.mensagem[len(comeco):] if erro.mensagem.startswith(comeco) else erro.mensagem
    if isinstance(erro, UnicodeDecodeError):
        return "arquivo fora do UTF-8"
    if isinstance(erro, OSError):
        return comum.motivo_do_sistema(erro)
    return str(erro)


def abrir(raiz: Path, perfil, id_: str, tipo: str = "feat", executar=subprocess.run,
          agora=datetime.datetime.now) -> Saida:
    """Abre a lane da ficha depois do portão (spec 6c, §15.1)."""
    principal = bloco.arvore_principal(raiz, executar)
    try:
        abertura = _portao(principal, perfil, id_, tipo, executar)
    except Recusa as erro:
        raise Recusa(f"portão recusou: {erro.mensagem}") from None
    ficha, pasta, numero = abertura.ficha, abertura.pasta, abertura.numero
    _, motivo = importacao.falha(["git", "-C", str(principal), "worktree", "add", "-q", "--no-track", "-b",
                                  abertura.ramo, str(pasta), f"refs/remotes/origin/{perfil.ramo_principal}"],
                                 "worktree add", executar, importacao.TEMPO_LIMITE_COMMIT)
    if motivo is not None:
        raise Recusa(f"git worktree add falhou: {motivo}")
    relativo = pasta.relative_to(principal).as_posix()
    blocos = f"{perfil.caminhos.blocos}/{ficha.id}-{ficha.slug}"
    estado_md, contexto_md = f"{blocos}/{bloco.ARQUIVO}", f"{blocos}/{contexto.ARQUIVO}"
    partes, faltam, movida, passo = [], [], False, "harness-lane"
    try:
        _gravar_numero(pasta, numero)
        passo = ".env"
        if abertura.env is not None:
            gerado = _env_da_lane(perfil.lane.env_modelo)
            comum.escrever_texto(pasta / gerado, trocar_marcadores(abertura.env, perfil, numero, ficha.id, ficha.slug))
            partes.append(f"{gerado} gerado do {perfil.lane.env_modelo}")
        passo = "env_copiados"
        copiados = []
        for arquivo in perfil.lane.env_copiados:
            if not (principal / arquivo).is_file():
                faltam.append(arquivo)
                continue
            (pasta / arquivo).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(principal / arquivo, pasta / arquivo)
            copiados.append(arquivo)
        if copiados:
            partes.append(f"copiado {comum.juntar(copiados)}")
        passo = "instalar"
        _instalar(perfil, abertura)
        if perfil.lane.instalar:
            partes.append("instalar ok")
        passo = "ficha"
        if _ficha_nova(principal, perfil, ficha, executar):
            (pasta / ficha.arquivo).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(principal / ficha.arquivo, pasta / ficha.arquivo)
            movida = True
            (principal / ficha.arquivo).unlink()
        passo = "estado.md"
        copia = fichas.ler_manifesto(pasta, perfil)
        if copia is None:
            raise Recusa(f"sem a cópia da passagem em {perfil.caminhos.passagem}/")
        estado = EstadoDoBloco(
            id=ficha.id, slug=ficha.slug, estado="planning", estado_anterior=bloco.SEM, bloqueio=bloco.SEM,
            motivo=bloco.SEM, efeito_externo=bloco.SEM, passagem=copia.versao, ramo=abertura.ramo, lane=numero,
            base=abertura.base, retornos=(), atualizado_em=agora().strftime("%Y-%m-%dT%H:%M"),
        )
        comum.escrever_texto(pasta / estado_md, bloco.para_texto(estado))
        passo = "contexto.md"
        ficha_da_lane, copia = contexto.ficha_da_arvore(pasta, perfil, ficha.id)
        pacote = contexto.montar(pasta, perfil, ficha_da_lane, copia)
        comum.escrever_texto(pasta / contexto_md, pacote.texto)
        passo = "git commit"
        caminhos = [estado_md, contexto_md, *([ficha.arquivo] if movida else [])]
        bloco.commitar(pasta, caminhos, f"chore({ficha.id}): abre a lane", [estado_md, contexto_md], executar)
    except (Recusa, _PassoFalhou, OSError, UnicodeDecodeError) as erro:
        motivo = _motivo_da_falha(erro)
        if movida and not (principal / ficha.arquivo).exists():
            shutil.copy2(pasta / ficha.arquivo, principal / ficha.arquivo)
        return Saida((abertura.linha, f"lane pela metade: {passo} falhou ({motivo}); desfaça com harness.py lane "
                                      f"fechar {ficha.id} --abandonar"), True)
    linhas = [abertura.linha, f"lane {ficha.id} aberta em {relativo}",
              f"  branch {abertura.ramo}; {lanes.portas(perfil, numero)}"]
    if partes:
        linhas.append("  " + "; ".join(partes))
    linhas += [f"  env_copiados: {arquivo} não existe na árvore principal; pulado" for arquivo in faltam]
    linhas.append(f"  estado planning; Context Packet com {_contagem(pacote.fatos, 'fato', 'fatos')}")
    falha = lanes.linha_do_regravar(principal, perfil, executar, agora)
    linhas += [falha] if falha else []
    linhas.append(f"Para entrar: EnterWorktree com path {relativo}")
    avisos = (Aviso(ficha.id, "pronta", "planning", str(pasta), estado),) if perfil.linear is not None else ()
    return Saida(tuple(linhas), avisos=avisos)


def caminhos_do_plano(texto: str) -> set[str]:
    """Os caminhos entre crases das linhas `- Create:`, `- Modify:`, `- Test:` e `- Delete:` do plano, com recuo ou
    sem ele, sem o `:N` ou `:N-M` do fim."""
    caminhos = set()
    for linha in texto.splitlines():
        achado = _RE_LINHA_DO_PLANO.fullmatch(linha)
        if achado:
            caminhos.update(_RE_LINHAS_DO_CAMINHO.sub("", caminho) for caminho in _RE_CRASE.findall(achado.group(1)))
    return caminhos


def _pr_mesclado(principal: Path, perfil, lane_: bloco.LaneViva, executar) -> tuple[str | None, bool]:
    """A linha do PR mesclado no ramo principal do bloco em `closing`, ou a da falha do `gh`, e se ele foi mesclado."""
    try:
        prs = importacao.prs_da_branch(principal, lane_.ramo, executar)
    except Recusa as erro:
        return f"{lane_.bloco.id}: {erro.mensagem}", False
    mesclados = [pr for pr in prs if pr.estado == "MERGED" and pr.base == perfil.ramo_principal]
    if not mesclados:
        return None, False
    numero = max(pr.numero for pr in mesclados)
    return f"{lane_.bloco.id}: PR #{numero} mesclado; rode harness.py lane fechar {lane_.bloco.id}", True


def _afetado(principal: Path, perfil, lane_: bloco.LaneViva, novo, mesclado: bool, executar, agora,
             avisos: list[Aviso]) -> str | None:
    """A linha do bloco afetado pela versão do ramo principal, pelo estado dele; de `planning` a `ready_for_closure`,
    o bloco é travado por um commit na lane, e o aviso dessa trava entra nos `avisos`."""
    bloco_ = lane_.bloco
    try:
        afetados = importacao.afetados(principal, novo, [lane_], perfil, executar)
    except Recusa as erro:
        return erro.mensagem
    if not afetados:
        return None
    motivo = bloco.motivo_da_passagem(novo.versao, [*afetados[0].mudaram, *afetados[0].sairam])
    if bloco_.estado == "closing":
        return None if mesclado else f"{bloco_.id}: {motivo}; em closing, o bloco não é travado: decida antes do merge"
    if bloco_.estado == "blocked":
        if bloco_.bloqueio == "passagem" and bloco.versao_do_motivo(bloco_.motivo) == novo.versao:
            return None
        return f"{bloco_.id}: {motivo}; o bloco já está travado ({bloco_.bloqueio})"
    travado = transicoes.mudar(bloco_, "blocked", agora, bloqueio="passagem", motivo=motivo)
    try:
        transicoes.gravar_transicao(lane_.pasta, perfil, lane_, travado, [], [], executar, agora)
    except Recusa as erro:
        return f"{bloco_.id}: não travado: {erro.mensagem}"
    except UnicodeDecodeError:
        return f"{bloco_.id}: não travado: arquivo fora do UTF-8"
    except OSError as erro:
        return f"{bloco_.id}: não travado: {comum.motivo_do_sistema(erro)}"
    avisos.extend(transicoes.avisos(lane_.pasta, perfil, lane_, travado))
    return f"{bloco_.id}: {motivo}; bloco travado (blocked)"


def _retornos_resolvidos(perfil, lane_: bloco.LaneViva, executar) -> list[str]:
    """As linhas dos retornos de decisão do bloco em `blocked` por `retorno` que a issue fechada dá como resolvidos."""
    bloco_ = lane_.bloco
    if bloco_.estado != "blocked" or bloco_.bloqueio != "retorno":
        return []
    linhas = []
    for numero, tipo in bloco_.retornos:
        if tipo != "decisao":
            continue
        feito, motivo = importacao.falha(["gh", "issue", "view", str(numero), "--repo", perfil.passagem.repositorio,
                                          "--json", "state,comments"], "issue view", executar,
                                         importacao.TEMPO_LIMITE_GH)
        try:
            issue = json.loads(feito.stdout.decode("utf-8")) if motivo is None else None
        except (UnicodeDecodeError, ValueError):
            issue = None
        if motivo is None and not (isinstance(issue, dict) and isinstance(issue.get("comments"), list)):
            motivo = "saída ilegível"
        if motivo is not None:
            linhas.append(f"{bloco_.id}: retorno #{numero} não consultado: {motivo}")
            continue
        if issue.get("state") != "CLOSED":
            continue
        corpos = [comentario.get("body") for comentario in issue["comments"] if isinstance(comentario, dict)]
        versao = next((achado.group(1) for corpo in corpos if isinstance(corpo, str)
                       for achado in [_RE_RESOLVIDA.search(corpo)] if achado), None)
        if versao is not None:
            linhas.append(f"{bloco_.id}: retorno #{numero} resolvido na passagem/v{versao}; traga o "
                          f"{perfil.ramo_principal} e rode harness.py bloco desbloquear --replanejar")
    return linhas


def _planos_que_se_cruzam(perfil, vivas: tuple[bloco.LaneViva, ...]) -> list[str]:
    """Uma linha por par de lanes, na ordem das fichas, cujos planos mexem nos mesmos caminhos."""
    planos = []
    for lane_ in vivas:
        try:
            texto = comum.ler_texto(lane_.pasta / perfil.caminhos.blocos / lane_.bloco.pasta / PLANO)
        except (OSError, UnicodeDecodeError):
            texto = ""
        planos.append((lane_.bloco.id, caminhos_do_plano(texto)))
    linhas = []
    for posicao, (um, de_um) in enumerate(planos):
        for outro, de_outro in planos[posicao + 1:]:
            comuns = sorted(de_um & de_outro)
            if comuns:
                linhas.append(f"{um} e {outro}: os dois planos mexem em {comum.juntar(comuns)}")
    return linhas


def conferir(raiz: Path, perfil, executar=subprocess.run, agora=datetime.datetime.now) -> Saida:
    """Confere as lanes contra o origin (spec 6c, §15.2): o fetch do ramo principal, que é a única recusa; as linhas
    das worktrees; por lane, o PR mesclado, o afetado e os retornos resolvidos; e os planos que se cruzam. Regrava o
    `LANES.md`. Cada bloco que a passagem nova travou deixa um aviso ao Linear (spec 6d-repositorio, §9.5)."""
    principal = bloco.arvore_principal(raiz, executar)
    importacao.buscar_principal(principal, perfil, executar)
    quadro = lanes.montar(principal, perfil, executar)
    novo = importacao.manifesto_do_principal(principal, perfil, executar)
    linhas = list(quadro.worktrees)
    avisos: list[Aviso] = []
    for lane_ in quadro.lanes:
        mesclado = False
        if lane_.bloco.estado == "closing":
            linha, mesclado = _pr_mesclado(principal, perfil, lane_, executar)
            linhas += [linha] if linha else []
        if novo is not None:
            linha = _afetado(principal, perfil, lane_, novo, mesclado, executar, agora, avisos)
            linhas += [linha] if linha else []
        linhas += _retornos_resolvidos(perfil, lane_, executar)
    linhas += _planos_que_se_cruzam(perfil, quadro.lanes)
    falha = lanes.linha_do_regravar(principal, perfil, executar, agora)
    return Saida(tuple(linhas or ["lanes em ordem"]) + ((falha,) if falha else ()), avisos=tuple(avisos))


def _dentro(raiz: Path, pasta: Path) -> bool:
    try:
        Path(raiz).resolve().relative_to(pasta.resolve())
    except ValueError:
        return False
    return True


def _pr_do_fechamento(principal: Path, perfil, ramo: str, executar) -> importacao.PR:
    """O PR pela precedência: um `OPEN` recusa; senão, o `MERGED` de maior número no ramo principal; senão, a recusa
    do `sem PR`."""
    prs = importacao.prs_da_branch(principal, ramo, executar)
    abertos = [pr.numero for pr in prs if pr.estado == "OPEN"]
    if abertos:
        raise Recusa(f"PR #{max(abertos)} ainda aberto; mescle antes")
    mesclados = [pr for pr in prs if pr.estado == "MERGED" and pr.base == perfil.ramo_principal]
    if not mesclados:
        raise Recusa(f"{ramo} sem PR; rode harness.py bloco finalizar na lane")
    return max(mesclados, key=lambda pr: pr.numero)


def _mesmo_commit(lugar: Path, ponta: str, pr: importacao.PR, executar) -> None:
    """O `headRefOid` do PR é a `ponta` da lane (o HEAD da pasta, ou a branch, com a pasta sumida); um ancestral dela
    dá a recusa dos commits depois do PR, e o resto, a do commit que não está na lane."""
    cabeca = bloco.git(lugar, ["rev-parse", ponta], executar)
    if cabeca.returncode != 0:
        raise Recusa(f"git rev-parse falhou: {comum.motivo_do_git(cabeca, 'rev-parse')}")
    if pr.head == cabeca.stdout.decode("utf-8", errors="replace").strip():
        return
    if _RE_SHA.fullmatch(pr.head) and \
            bloco.git(lugar, ["merge-base", "--is-ancestor", pr.head, ponta], executar).returncode == 0:
        contagem = bloco.git(lugar, ["rev-list", "--count", f"{pr.head}..{ponta}"], executar)
        if contagem.returncode != 0:
            raise Recusa(f"git rev-list falhou: {comum.motivo_do_git(contagem, 'rev-list')}")
        raise Recusa(f"a lane tem {contagem.stdout.decode('utf-8', errors='replace').strip()} commit(s) depois do "
                     f"PR #{pr.numero}, que já foi mesclado; leve o que servir para uma ficha nova e volte a lane ao "
                     f"commit do PR com git reset --hard {pr.head}")
    raise Recusa(f"o PR #{pr.numero} foi mesclado com {pr.head[:12]}, que não está na lane; confira antes de fechar")


def _do_commit(principal: Path, ramo: str, relativo: str, executar) -> str | None:
    """O texto do `relativo` no commit da branch, ou None, sem ele."""
    lido = bloco.git(principal, ["cat-file", "blob", f"refs/heads/{ramo}:{relativo}"], executar)
    return lido.stdout.decode("utf-8") if lido.returncode == 0 else None


def _bloco_da_branch(principal: Path, ramo: str, perfil, executar) -> EstadoDoBloco | None:
    """O bloco da lane de pasta sumida: o `estado.md` de `<blocos>/<último trecho do ramo>/` no commit da branch, com
    o `ramo` igual ao dela, ou None."""
    relativo = f"{perfil.caminhos.blocos}/{bloco.pasta_da_branch(ramo)}/{bloco.ARQUIVO}"
    texto = _do_commit(principal, ramo, relativo, executar)
    if texto is None:
        return None
    estado = bloco.ler_estado(texto, relativo)
    return estado if estado.ramo == ramo else None


def _tabela_da_lane(principal: Path, worktree, perfil, estado: EstadoDoBloco, executar) -> aceitacao.Tabela:
    """O `aceitacao.md` do bloco, da pasta da lane ou, com ela sumida, do commit da branch; sem ele, a tabela vazia, ou
    a recusa do comando `aceitacao` com efeito externo."""
    relativo = f"{perfil.caminhos.blocos}/{estado.pasta}/{aceitacao.ARQUIVO}"
    if worktree.sumida:
        texto = _do_commit(principal, worktree.ramo, relativo, executar)
    else:
        arquivo = worktree.pasta / relativo
        texto = comum.ler_texto(arquivo) if arquivo.is_file() else None
    if texto is None:
        if estado.efeito_externo == "sim":
            raise Recusa(f"{relativo} não existe; o bloco planejado o gera")
        return aceitacao.Tabela(estado.id, ())
    return aceitacao.ler(texto, relativo)


def _pedidos_da_lane(principal: Path, worktree, perfil, estado: EstadoDoBloco, executar) -> dict[int, aceitacao.Pedido]:
    """Os pedidos da spec aprovada do bloco, do `spec.md` da pasta da lane ou, com ela sumida, do commit da branch,
    com a recusa da spec mudada depois da aprovação ou ausente."""
    relativo = f"{perfil.caminhos.blocos}/{estado.pasta}/{bloco.ARQUIVO_DA_SPEC}"
    if worktree.sumida:
        texto = _do_commit(principal, worktree.ramo, relativo, executar)
        dados = None if texto is None else texto.encode("utf-8")
    else:
        arquivo = worktree.pasta / relativo
        dados = arquivo.read_bytes() if arquivo.is_file() else None
    return aceitacao.pedidos_aprovados(dados, estado.spec, perfil, "lane fechar")


def _de_novo(passo: str, motivo: str, id_: str) -> str:
    return f"{passo} falhou: {motivo}; a lane fica; rode harness.py lane fechar {id_} de novo"


def _comentado(principal: Path, numero: int, corpo: str, executar) -> tuple[bool, tuple[str, str] | None]:
    """Comenta o PR, se nenhum comentário tem o mesmo corpo: se já estava comentado, e o comando que falhou com o
    motivo, ou None."""
    feito, motivo = importacao.falha(["gh", "pr", "view", str(numero), "--json", "comments"], "pr view", executar,
                                     importacao.TEMPO_LIMITE_GH, principal)
    try:
        dados = json.loads(feito.stdout.decode("utf-8")) if motivo is None else None
    except (UnicodeDecodeError, ValueError):
        dados = None
    if motivo is None and not (isinstance(dados, dict) and isinstance(dados.get("comments"), list)):
        motivo = "saída ilegível"
    if motivo is not None:
        return False, ("gh pr view", motivo)
    if any(isinstance(comentario, dict) and isinstance(comentario.get("body"), str)
           and comentario["body"].strip() == corpo for comentario in dados["comments"]):
        return True, None
    _, motivo = importacao.falha(["gh", "pr", "comment", str(numero), "--body", corpo], "pr comment", executar,
                                 importacao.TEMPO_LIMITE_GH, principal)
    return False, None if motivo is None else ("gh pr comment", motivo)


def _desmontar(perfil, pasta: Path, numero: int, id_: str, slug: str) -> str | None:
    """Roda todos os comandos do `desmontar` na lane, com os marcadores; os que falham, como `<comando> (saída <c>)` ou
    `<comando> (passou de 900 s)`, juntados por `e`, ou None."""
    falhas = []
    for comando in perfil.lane.desmontar:
        trocado = trocar_marcadores(comando, perfil, numero, id_, slug, pasta)
        codigo, _ = verificacao.rodar_comando(trocado, pasta, TEMPO_DOS_COMANDOS)
        if codigo is None:
            falhas.append(f"{comando} (passou de {TEMPO_DOS_COMANDOS} s)")
        elif codigo != 0:
            falhas.append(f"{comando} (saída {codigo})")
    return comum.juntar(falhas) or None


def _remover(principal: Path, pasta: Path, ramo: str | None, forcar: bool, executar) -> None:
    """O `git worktree remove`, com `--force` na lane pela metade, e o `git branch -D`, quando a branch existe."""
    feito = bloco.git(principal, ["worktree", "remove", *(["--force"] if forcar else []), str(pasta)], executar,
                      TEMPO_DOS_COMANDOS)
    if feito.returncode != 0:
        raise Recusa(f"git worktree remove falhou: {comum.motivo_do_git(feito, 'worktree remove')}")
    if ramo is None or bloco.git(principal, ["rev-parse", "--verify", "-q", f"refs/heads/{ramo}"],
                                 executar).returncode != 0:
        return
    feito = bloco.git(principal, ["branch", "-D", ramo], executar)
    if feito.returncode != 0:
        raise Recusa(f"git branch -D falhou: {comum.motivo_do_git(feito, 'branch')}")


def _com_alteracao(pasta: Path, soltos: set[str], executar) -> bool:
    """O `git status` da lane tem alguma entrada fora dos `soltos` novos (não rastreados ou só no índice)."""
    feito = bloco.git(pasta, ["status", "--porcelain", "-z", "--untracked-files=all"], executar)
    if feito.returncode != 0:
        raise Recusa(f"git status falhou: {comum.motivo_do_git(feito, 'status')}")
    entradas = iter(feito.stdout.decode("utf-8", errors="replace").split("\0"))
    for entrada in entradas:
        if not entrada:
            continue
        if entrada[0] in "RC":
            next(entradas, None)
        if not (entrada[3:] in soltos and entrada[0] in "?A"):
            return True
    return False


def _estado_legivel(arquivo: Path) -> EstadoDoBloco | None:
    try:
        return bloco.ler_estado(comum.ler_texto(arquivo), arquivo.name)
    except (Recusa, OSError, UnicodeDecodeError):
        return None


def _devolver(principal: Path, pasta: Path, arquivo: str, ramo: str | None, executar) -> None:
    """Põe a ficha do código da lane na árvore principal, sem commit: da pasta da lane, ou, com `ramo`, do commit da
    branch, quando a pasta sumiu."""
    if ramo is not None:
        lido = bloco.git(principal, ["cat-file", "blob", f"refs/heads/{ramo}:{arquivo}"], executar)
        if lido.returncode != 0:
            raise Recusa(f"git cat-file falhou: {comum.motivo_do_git(lido, 'cat-file')}")
    (principal / arquivo).parent.mkdir(parents=True, exist_ok=True)
    if ramo is None:
        shutil.copy2(pasta / arquivo, principal / arquivo)
    else:
        (principal / arquivo).write_bytes(lido.stdout)


def _abandonar(principal: Path, perfil, id_: str, worktree, executar, agora) -> Saida:
    """Remove a lane sem PR aberto nem mesclado, também pela metade ou sumida, e devolve a ficha do código que só
    existe nela (spec 6c, §15.3, emendado)."""
    if worktree is None:
        raise Recusa(f"lane fechar: {id_} não tem lane")
    pasta, ramo = worktree.pasta, worktree.ramo
    pasta_do_bloco = f"{perfil.caminhos.blocos}/{pasta.name}"
    estado_md = f"{pasta_do_bloco}/{bloco.ARQUIVO}"
    metade, ficha, estado, ilegivel = False, None, None, False
    if not worktree.sumida:
        metade = bloco.git(pasta, ["cat-file", "-e", f"HEAD:{estado_md}"], executar).returncode != 0
        ficha = next((ficha for ficha in fichas.do_backlog(pasta, perfil) if ficha.id == id_), None)
        soltos = {estado_md, f"{pasta_do_bloco}/{contexto.ARQUIVO}", *([ficha.arquivo] if ficha else [])}
        if _com_alteracao(pasta, soltos if metade else set(), executar):
            raise Recusa("a lane tem alterações sem commit; faça o commit ou descarte antes")
        estado = _estado_legivel(pasta / estado_md)
        ilegivel = estado is None and not metade
    elif ramo is not None:
        ficha = next((ficha for ficha in fichas.da_ref(principal, perfil, f"refs/heads/{ramo}", executar)
                      if ficha.id == id_), None)
        try:
            estado = _bloco_da_branch(principal, ramo, perfil, executar)  # só para o aviso ao Linear
        except (Recusa, UnicodeDecodeError):
            estado, ilegivel = None, True
    if ramo is not None:
        prs = importacao.prs_da_branch(principal, ramo, executar)
        abertos = [pr.numero for pr in prs if pr.estado == "OPEN"]
        if abertos:
            raise Recusa(f"PR #{max(abertos)} aberto; feche-o antes de abandonar")
        mesclados = [pr.numero for pr in prs if pr.estado == "MERGED" and pr.base == perfil.ramo_principal]
        if mesclados:
            raise Recusa(f"PR #{max(mesclados)} já mesclado; feche a lane com harness.py lane fechar {id_}")
    if ficha is not None and not (principal / ficha.arquivo).exists() and bloco.git(
            principal, ["cat-file", "-e", f"refs/remotes/origin/{perfil.ramo_principal}:{ficha.arquivo}"],
            executar).returncode != 0:
        _devolver(principal, pasta, ficha.arquivo, ramo if worktree.sumida else None, executar)
    linhas = []
    if not worktree.sumida and perfil.lane.desmontar:
        numero = estado.lane if estado is not None else _numero_gravado(pasta, perfil)
        slug = estado.slug if estado is not None else pasta.name[len(id_) + 1:]
        if numero is None:
            linhas.append("desmontar pulado: sem o estado.md, a lane não tem número")
        else:
            falha = _desmontar(perfil, pasta, numero, id_, slug)
            linhas += [f"desmontar falhou: {falha}"] if falha else []
    _remover(principal, pasta, ramo, metade, executar)
    falha = lanes.linha_do_regravar(principal, perfil, executar, agora)
    ilegiveis: list[str] = []
    situacao = fichas.situacao(id_, fichas.quadro(principal, perfil, executar, ilegiveis), perfil)
    linhas.append(f"lane {id_} abandonada; a ficha não existe" if situacao == "não existe"
                  else f"lane {id_} abandonada; a ficha fica {situacao}")
    linhas += [f"atenção: {linha}" for linha in ilegiveis]
    # A lane pela metade, sem o `estado.md` no commit, o Linear nunca soube dela: não há o que desfazer lá.
    avisar = perfil.linear is not None and estado is not None and not metade
    avisos = (Aviso(id_, estado.estado, "pronta (lane abandonada)", str(principal)),) if avisar else ()
    if perfil.linear is not None and ilegivel:  # o espelho nunca recua o status: só a pessoa acerta a issue
        linhas.append("linear: aviso não enviado (estado.md ilegível); acerte o status da issue à mão")
    return Saida(tuple(linhas + ([falha] if falha else [])), avisos=avisos)


def fechar(raiz: Path, perfil, id_: str, manuais: dict[int, str] | None = None, abandonar: bool = False,
           executar=subprocess.run, agora=datetime.datetime.now) -> Saida:
    """Fecha a lane do bloco em `closing` com o PR mesclado no mesmo commit e a aceitação de depois do merge, também
    com a pasta sumida, ou, com `abandonar`, remove a lane sem PR mesclado (spec 6c, §15.3, emendado)."""
    principal = bloco.arvore_principal(raiz, executar)
    importacao.buscar_principal(principal, perfil, executar)
    _, worktrees = bloco.worktrees_de_lane(principal, perfil, executar)
    worktree = next((worktree for worktree in worktrees if worktree.pasta.name.startswith(f"{id_}-")), None)
    if worktree is not None and _dentro(raiz, worktree.pasta):
        raise Recusa(f"lane fechar: rode fora da lane {id_}")
    sessao = os.environ.get("CLAUDE_PROJECT_DIR")
    if worktree is not None and sessao and _dentro(Path(sessao), worktree.pasta):
        raise Recusa(f"lane fechar: a sessão foi aberta dentro da lane {id_}; feche a lane {bloco.ONDE_FECHAR_A_LANE}")
    if abandonar:
        return _abandonar(principal, perfil, id_, worktree, executar, agora)
    estado = None
    if worktree is not None and worktree.ramo is not None:
        estado = (_bloco_da_branch(principal, worktree.ramo, perfil, executar) if worktree.sumida
                  else bloco.bloco_da_worktree(worktree.pasta, worktree.ramo, perfil, principal))
    if estado is None or estado.id != id_:
        raise Recusa(f"lane fechar: {id_} não tem lane")
    pasta, sumida = worktree.pasta, worktree.sumida
    if estado.estado != "closing":
        raise Recusa(f"{id_} está em {estado.estado}; lane fechar vale só em closing")
    if not sumida and not transicoes.lane_sem_alteracao(pasta, executar):
        raise Recusa("a lane tem alterações sem commit; faça o commit ou descarte antes")
    pr = _pr_do_fechamento(principal, perfil, worktree.ramo, executar)
    if sumida:
        _mesmo_commit(principal, f"refs/heads/{worktree.ramo}", pr, executar)
    else:
        _mesmo_commit(pasta, "HEAD", pr, executar)
    tabela = _tabela_da_lane(principal, worktree, perfil, estado, executar)
    pedidos, variaveis = {}, {}
    if aceitacao.precisa_da_spec(tabela, True):
        pedidos = _pedidos_da_lane(principal, worktree, perfil, estado, executar)
        variaveis = aceitacao.variaveis(None if sumida else pasta, perfil, os.environ)
    resultado = aceitacao.depois_do_merge(tabela, perfil, estado.lane, manuais or {}, agora().strftime("%Y-%m-%d"),
                                          pedidos, variaveis)
    *itens, veredito = resultado.linhas
    linhas = [f"PR #{pr.numero} mesclado, com o mesmo commit da lane",
              f"aceitação depois do merge: {'; '.join(itens) or 'nenhum item'}"]
    if estado.efeito_externo == "sim" and not resultado.ok:
        return Saida((*linhas, f"{veredito}; a lane fica; rode de novo quando o deploy terminar"), True)
    ja, falha = _comentado(principal, pr.numero, "\n".join(["Aceitação depois do merge:", *itens, veredito]),
                           executar)
    if falha is not None:
        return Saida((*linhas, veredito, _de_novo(*falha, id_)), True)
    linhas.append(f"{veredito}; {'já comentado' if ja else 'comentado'} no PR #{pr.numero}")
    desmontado = None if sumida else _desmontar(perfil, pasta, estado.lane, id_, estado.slug)
    _remover(principal, pasta, worktree.ramo, False, executar)
    if not perfil.lane.desmontar:
        linhas.append("worktree e branch removidas")
    elif sumida:
        linhas.append("desmontar pulado: a pasta da lane sumiu; worktree e branch removidas")
    elif desmontado is not None:
        linhas.append(f"desmontar falhou: {desmontado}; worktree e branch removidas")
    else:
        linhas.append("desmontar ok; worktree e branch removidas")
    falha_do_quadro = lanes.linha_do_regravar(principal, perfil, executar, agora)
    avisos = (Aviso(id_, "closing", "fechada", str(principal), pr=pr.url),) if perfil.linear is not None else ()
    return Saida(tuple(linhas + ([falha_do_quadro] if falha_do_quadro else [])), avisos=avisos)
