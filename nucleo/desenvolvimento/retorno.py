"""Retorno do código ao planejamento (spec 6c, §16): a issue com o ID contradito e, na lane, o registro no `estado.md`.

O ID vem do manifesto da cópia da passagem da árvore. Fora de lane, só a issue sai; dentro dela, o retorno entra nos
`retornos` do bloco, e o de decisão trava o bloco até a versão da passagem que o resolva.
"""
from __future__ import annotations

import dataclasses
import datetime
import json
import re
import subprocess
from pathlib import Path

import bloco
import comum
import fichas
import importacao
import manifesto
import transicoes
from bloco import EstadoDoBloco, Recusa, Saida

TIPOS = ("fato", "decisao")
ROTULO = "retorno"

_RE_ISSUE = re.compile(r"/issues/([0-9]+)")
_TIPO = {"fato": "fato provado; o bloco segue",
         "decisao": "mudança de decisão; o bloco espera a versão da passagem que a resolva"}

AJUDA = """\
`retorno abrir <ID> --tipo fato|decisao --contradiz "<texto>" --evidencia "<texto>"` abre, no repositório de
planejamento (`passagem.repositorio`), a issue de retorno de um ID da passagem que o código contradiz. O ID é um dos
`ids` do manifesto da cópia da passagem da árvore; fora dele, a recusa é `<ID> não está na passagem/v<N>`, e sem a
cópia, `sem a cópia da passagem em <passagem>/; rode harness.py importar`. O `--contradiz` e o `--evidencia` têm os
espaços juntados e não podem ficar vazios (`--contradiz e --evidencia não podem ficar vazios`).

Os dois tipos:

- `fato`: o código provou um fato diferente do planejado; o bloco segue;
- `decisao`: o código pede outra decisão; o bloco vai a `blocked`, com `bloqueio: retorno` e o motivo
  `retorno #<n>: espera a versão da passagem que o resolva`, e espera a versão da passagem que o resolva. Já em
  `blocked`, só a causa e o motivo mudam.

Com a `[desenvolvimento.linear]` no perfil, o retorno de `decisao` que trava o bloco avisa o Linear depois de imprimir a
linha (`harness.py linear` traz o formato do comentário), e o de `fato`, e o que só muda a causa de um bloco já em
`blocked`, não avisa, porque o estado do bloco não muda. O aviso não muda a saída nem o código de saída.

Antes de criar, o comando procura a issue aberta com o mesmo título e o mesmo corpo, com 30 s de limite:
`gh issue list --repo <repositorio> --state open --label retorno --search "<título> in:title"`, com
`--json number,title,body,url --limit 100`. O título é comparado inteiro, e o corpo, sem os espaços do fim; com mais
de uma issue vale a mais antiga. A falha da busca recusa com `gh issue list falhou: <motivo>`. Achando a issue, o
comando não cria outra: ela entra no bloco como a criada, e rodar o mesmo retorno de novo não abre issue repetida. A
issue de mesmo título e outro corpo, como a de outro tipo ou com outra evidência, não conta, e o comando cria a nova.

A issue nova sai pelo `gh issue create --repo <repositorio> --label retorno --title <título> --body <corpo>`, com 30 s
de limite. O título é `retorno: <ID> no bloco <bloco>`, ou `retorno: <ID>` fora de lane. O corpo tem uma linha por
campo:

- `ID afetado: <ID> (<passagem>/<arquivo>, linhas <i> a <f>)`, o trecho do manifesto;
- `Versão da passagem: passagem/v<N>`;
- `Bloco: <ID do bloco> (<branch>)`, ou `Bloco: nenhum` fora de lane;
- `Tipo: fato provado; o bloco segue` ou `Tipo: mudança de decisão; o bloco espera a versão da passagem que a resolva`;
- `O que contradiz: <texto>`;
- `Evidência: <texto>`.

A falha do `gh` recusa com `gh issue create falhou: <motivo>`. Sem o rótulo `retorno` no repositório, a recusa diz
também como criá-lo: `crie o rótulo: gh label create retorno --repo <repositorio>`.

Fora de lane, nenhum estado muda, e a saída é `issue #<n> aberta: <url>`, ou `issue #<n> já aberta: <url>` quando a
issue já existia. Dentro da lane, o `estado.md` do bloco ganha `#<n> <tipo>` nos `retornos` (sem repetir o que já está
lá), no commit `chore(<ID do bloco>): retorno #<n>`, e o `LANES.md` é regravado; a saída é
`issue #<n> aberta: <url>; <ID do bloco> segue (fato)` ou `issue #<n> aberta: <url>; <ID do bloco> travado (blocked)`,
e `issue #<n> já aberta: <url>; registrada no bloco` com a issue que já existia.

Depois da issue, a falha ao gravar o `estado.md` ou ao fazer o commit sai com 1 e a linha
`issue #<n> aberta, mas <passo> falhou: <motivo>; rode o mesmo retorno abrir de novo`, com `estado.md` ou `git commit`
no lugar do `<passo>`. Rodar o mesmo comando de novo acha a issue e termina o registro no bloco.

Com o bloco em `closing`, recusa com
`retorno abrir: <ID do bloco> está em closing; rode harness.py bloco corrigir antes, ou abra o retorno fora da lane`:
o commit do retorno ficaria depois do PR. A guarda pede a confirmação do usuário.
"""


def corpo(id_: str, arquivo: str, linhas: tuple[int, int], versao: int, bloco_: EstadoDoBloco | None, tipo: str,
          contradiz: str, evidencia: str) -> str:
    """O corpo da issue (spec 6c, Anexo B.1); o `arquivo` já vem com a pasta da passagem."""
    origem = "nenhum" if bloco_ is None else f"{bloco_.id} ({bloco_.ramo})"
    return "\n".join((
        f"ID afetado: {id_} ({arquivo}, linhas {linhas[0]} a {linhas[1]})",
        f"Versão da passagem: {manifesto.PREFIXO_TAG}{versao}",
        f"Bloco: {origem}",
        f"Tipo: {_TIPO[tipo]}",
        f"O que contradiz: {contradiz}",
        f"Evidência: {evidencia}",
    ))


def _gh_issue(perfil, raiz: Path, subcomando: str, argumentos: list[str], executar) -> bytes:
    """O `gh issue <subcomando> --repo <repositorio> <argumentos>` e o stdout, com TEMPO_LIMITE_GH. A falha recusa com
    `gh issue <subcomando> falhou: <motivo>`; sem o rótulo no repositório, a recusa diz também como criá-lo."""
    repositorio = perfil.passagem.repositorio
    feito, motivo = importacao.falha(["gh", "issue", subcomando, "--repo", repositorio, *argumentos],
                                     f"issue {subcomando}", executar, importacao.TEMPO_LIMITE_GH, raiz)
    if motivo is not None:
        erro = b"" if feito is None else feito.stderr or b""
        if f"'{ROTULO}' not found" in erro.decode("utf-8", errors="replace"):
            motivo += f"; crie o rótulo: gh label create {ROTULO} --repo {repositorio}"
        raise Recusa(f"gh issue {subcomando} falhou: {motivo}")
    return feito.stdout


def _issue_aberta(perfil, raiz: Path, titulo: str, texto: str, executar) -> tuple[int, str] | None:
    """O número e a URL da issue aberta com o rótulo `retorno`, o `titulo` inteiro e o corpo igual ao `texto`, pelo
    `gh issue list --search "<título> in:title"`: só a repetição do mesmo retorno reusa a issue. A busca do GitHub é
    aproximada, e o título se compara inteiro; o corpo se compara sem os espaços do fim. Com mais de uma, a mais
    antiga; sem nenhuma, None. A saída que não é uma lista, um `number` que não é inteiro ou um `body` que não é
    texto é ilegível."""
    saida = _gh_issue(perfil, raiz, "list", ["--state", "open", "--label", ROTULO, "--search", f"{titulo} in:title",
                                             "--json", "number,title,body,url", "--limit", "100"], executar)
    try:
        lidas = json.loads(saida.decode("utf-8", errors="replace"))
        validas = isinstance(lidas, list) and all(_inteiro(item["number"]) and isinstance(item["body"], str)
                                                  for item in lidas)
        achadas = [(item["number"], str(item["url"])) for item in lidas
                   if item["title"] == titulo and item["body"].rstrip() == texto.rstrip()] if validas else None
    except (ValueError, TypeError, KeyError):
        achadas = None
    if achadas is None:
        raise Recusa("gh issue list falhou: saída ilegível")
    return min(achadas) if achadas else None


def _inteiro(valor) -> bool:
    """Se o valor do JSON é um inteiro, sem contar o `true` e o `false`."""
    return isinstance(valor, int) and not isinstance(valor, bool)


def _issue(perfil, raiz: Path, titulo: str, texto: str, executar) -> tuple[int, str]:
    """Abre a issue e devolve o número e a URL, da última linha do stdout."""
    saida = _gh_issue(perfil, raiz, "create", ["--label", ROTULO, "--title", titulo, "--body", texto], executar)
    linhas = saida.decode("utf-8", errors="replace").strip().splitlines()
    achado = _RE_ISSUE.search(linhas[-1]) if linhas else None
    if achado is None:
        raise Recusa("gh issue create falhou: saída ilegível")
    return int(achado.group(1)), linhas[-1].strip()


def _falhou_depois_da_issue(numero: int, passo: str, motivo: str) -> Saida:
    """A saída 1 da falha depois de a issue existir, com o que fazer: rodar o mesmo comando de novo."""
    return Saida((f"issue #{numero} aberta, mas {passo} falhou: {motivo}; rode o mesmo retorno abrir de novo",), True)


def abrir(raiz: Path, perfil, id_: str, tipo: str, contradiz: str, evidencia: str, executar=subprocess.run,
          agora=datetime.datetime.now) -> Saida:
    """Abre a issue de retorno do ID e, na lane, registra o retorno no bloco (spec 6c, §16)."""
    contradiz, evidencia = " ".join(contradiz.split()), " ".join(evidencia.split())
    if not contradiz or not evidencia:
        raise Recusa("--contradiz e --evidencia não podem ficar vazios")
    lane = bloco.lane_pelos_arquivos(raiz, perfil)
    if lane is not None and lane.bloco.estado == "closing":
        raise Recusa(f"retorno abrir: {lane.bloco.id} está em closing; rode harness.py bloco corrigir antes, ou abra "
                     "o retorno fora da lane")
    copia = fichas.ler_manifesto(raiz, perfil)
    if copia is None:
        raise Recusa(f"sem a cópia da passagem em {perfil.caminhos.passagem}/; rode harness.py importar")
    definicao = copia.ids.get(id_)
    if definicao is None:
        raise Recusa(f"{id_} não está na {manifesto.PREFIXO_TAG}{copia.versao}")
    bloco_ = None if lane is None else lane.bloco
    texto = corpo(id_, f"{perfil.caminhos.passagem}/{definicao.arquivo}", definicao.linhas, copia.versao, bloco_,
                  tipo, contradiz, evidencia)
    titulo = f"retorno: {id_}" if bloco_ is None else f"retorno: {id_} no bloco {bloco_.id}"
    achada = _issue_aberta(perfil, Path(raiz), titulo, texto, executar)
    if achada is None:
        numero, url = _issue(perfil, Path(raiz), titulo, texto, executar)
        aberta = f"issue #{numero} aberta: {url}"
    else:
        numero, url = achada
        aberta = f"issue #{numero} já aberta: {url}"
    if bloco_ is None:
        return Saida((aberta,))
    retornos = bloco_.retornos if (numero, tipo) in bloco_.retornos else (*bloco_.retornos, (numero, tipo))
    if tipo == "fato":
        novo = dataclasses.replace(bloco_, retornos=retornos, atualizado_em=agora().strftime("%Y-%m-%dT%H:%M"))
    else:
        motivo = f"retorno #{numero}: espera a versão da passagem que o resolva"
        if bloco_.estado == "blocked":
            novo = dataclasses.replace(bloco_, bloqueio="retorno", motivo=motivo, retornos=retornos,
                                       atualizado_em=agora().strftime("%Y-%m-%dT%H:%M"))
        else:
            novo = transicoes.mudar(bloco_, "blocked", agora, bloqueio="retorno", motivo=motivo, retornos=retornos)
    try:
        _, *falha = transicoes.gravar_transicao(raiz, perfil, lane, novo, [], [], executar, agora,
                                                mensagem=f"chore({bloco_.id}): retorno #{numero}")
    except OSError as erro:
        return _falhou_depois_da_issue(numero, "estado.md", comum.motivo_do_sistema(erro))
    except Recusa as erro:
        return _falhou_depois_da_issue(numero, "git commit", erro.mensagem.removeprefix("git commit falhou: "))
    if achada is not None:
        efeito = "registrada no bloco"
    else:
        efeito = f"{bloco_.id} segue (fato)" if tipo == "fato" else f"{bloco_.id} travado (blocked)"
    # O Linear sabe só da transição: o retorno de fato, ou o que já estava em `blocked`, não muda o estado do bloco.
    avisos = transicoes.avisos(raiz, perfil, lane, novo) if novo.estado != bloco_.estado else ()
    return Saida((f"{aberta}; {efeito}", *falha), avisos=avisos)
