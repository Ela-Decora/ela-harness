"""O próximo passo do planejamento (spec 4a, §6), calculado pelo STATUS, pelos artefatos, pelas pendências, pelos
links e pelo ambiente. Lê a tabela de artefatos, as pendências abertas e os links entre os documentos.

Em ordem de precedência: o que consertar, o documento, pacote ou lote em andamento e a fila da fase (a geração dos
documentos do item `ligados`, quando a fase não tem nenhum; módulos, derivados,
rascunhos, obrigatórios, documentos novos que as pendências com o marcador do gate pedem, revisões com o marcador do
gate, pendências com o marcador que nenhum item da fila resolve e o gate). Só lê: não grava nada, e a mesma entrada
dá a mesma saída; a rede só para o retorno, que o hook nunca consulta. A ordem da fila sai das chaves que o perfil
já tem (os itens `ligados` do gate da fase, os `obrigatorios` da fase e o gate); os derivados de cada módulo vêm
do `composicao`. Só o comando, com o gate recomendado, roda os itens de script dele, só lendo, e mostra os FAIL.
"""
from __future__ import annotations

import json
import posixpath
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import ambiente
import backlog
import comum
import composicao
import estado
import estudos
import gate
import lote
import manifesto
import passagem
import rastreio
import registro
import versao
from perfil import Fase, Perfil

AJUDA = """\
Diz o próximo passo do planejamento, pelo STATUS.md, pela tabela de artefatos, pelas pendências e pelos links.

Só lê; a rede só para o retorno, e o hook nunca consulta. A ação recomendada é a primeira que existir, nesta ordem:

1. consertar: no passo 7 com a versão marcada já no HEAD, `harness.py fechar`; nos passos 6 e 7 com o documento
   mudado desde a marcação, `harness.py versao conferir`, que não vale no passo 6 com o `Ajuste` aberto; o documento em refino ausente do disco; o documento ou o
   pacote ou o lote do STATUS, nos passos 0 a 6, todo `aprovado` na tabela e sem pendência aberta que o cite:
   `perguntar ao usuário se o STATUS está velho`, com a volta no motivo; o lote de migração, que mantém os documentos
   `aprovado`, não entra nesse caso. Com o `Lote` no STATUS e a lista dele ausente, ilegível ou fora da conta,
   `a lista do lote falta ou não confere`, com a mensagem do `estado` e o jeito de refazer no motivo, que, com a
   versão marcada, começa por `com a autorização do usuário, harness.py versao limpar`. Num worktree, a ação ganha
   `(na árvore principal)`.
2. o documento, o pacote ou o lote em andamento: `/ela-harness:refinar-documento <documento>`, que retoma do passo
   atual, ou, no passo 7, o commit e o `harness.py fechar`; com "quando o usuário liberar" no `Proximo`, perguntar se o
   usuário libera o commit; sem documento em refino e com "quando o usuário liberar" no `Proximo` (o commit do gate),
   perguntar se o usuário libera o que o `Proximo` diz, e a fila da fase segue abaixo.
3. a fila da fase, sem nada aberto: `/ela-harness:gerar-modulos`, quando o gate da fase tem item `ligados`, nenhum
   documento da fase, no disco ou em refino, casa o `por` dele e todo obrigatório da fase existe e está aprovado, com
   o motivo `nenhum <padrões do por, juntados por " ou "> na fase`; os módulos em rascunho (os documentos que casam com o `por` de um item `ligados`
   do gate); os módulos aprovados com derivados em rascunho; os outros rascunhos, com `; nenhum módulo o compõe`
   no que casa os `documentos` de um item `ligados`; os obrigatórios ausentes ou em rascunho; os documentos novos
   que as pendências abertas com o marcador do gate pedem; os aprovados citados por pendência aberta com o marcador
   do gate; as pendências com o marcador que nenhum item da fila resolve; por último, `/ela-harness:gate-fase <gate>`.
   O documento novo sai do destino da pendência, sem os trechos `antes do`: o caminho com pasta (a partir da raiz, ou
   da pasta do planejamento quando começa pelo id de uma fase) dentro da pasta de uma fase e sem arquivo no disco; o
   nome sem pasta de nenhum `.md` do planejamento, de nenhum arquivo da raiz e de nenhum caminho de estado do perfil,
   na pasta dos `.md` de mesmo prefixo (o nome até o primeiro `-`), ou `<pasta>/<nome>`, com o `<pasta>` literal, sem
   prefixo ou com eles em mais de uma pasta; a pasta dentro da pasta de uma fase, `<pasta citada>/<documento>.md`,
   com o `<documento>` literal. A ação é `/ela-harness:refinar-documento <caminho>`, com o motivo
   `documento novo: <IDs> (<marcador>)`, mais `; a pasta, com o usuário` no `<pasta>` e `; o nome sai da pendência` no
   `<documento>`; o mesmo caminho em duas pendências dá um item só. A pendência com o marcador que nenhum item da fila
   resolve, nem pelos IDs nem pelo nome, no destino, de um documento da fila, de um derivado em rascunho de um
   módulo da fila ou do documento em refino, vira `resolver <ID> com o usuário`, com o motivo
   `nenhum documento da fila a resolve: <destino>`.
   Os derivados de um módulo, os mesmos do bloco "Pacote do módulo" do `harness.py dossie`, menos os documentos em
   refino (com algo em refino, o `proximo` recomenda o andamento), são os documentos da
   fase, não aprovados, que casam os `documentos` de um item `ligados` cujo `por` casa o módulo e que o módulo linka
   fora das exclusões: a seção de nível 2 com "outros módulos" no título; a lista aberta por uma linha que não é item
   e diz "outros módulos" ou "só lê", com essa linha; e a linha com a anotação `(módulo <nome>)` cujo nome, sem
   acento, em minúsculas e com hífens no lugar dos espaços, não está no nome do arquivo do módulo. Um link fora das
   exclusões basta.
   A revisão de um aprovado citado por pendência com `antes do <arquivo>.md` (o arquivo pode vir como link Markdown,
   `[rótulo](caminho.md)`) entra logo antes do item desse arquivo, se ele está na fila como módulo, rascunho,
   obrigatório ou documento novo, ou logo antes do item do módulo de que ele é derivado; com mais de um arquivo
   (`antes do a.md e do b.md`), antes do primeiro deles na fila; senão, vai junto das revisões do marcador. Nenhum
   arquivo depois de um `antes do` conta como citado. A pendência cujo destino cita dois ou mais aprovados (fora os
   em refino) vira um item `lote` só, no lugar das revisões desses documentos e na posição da primeira delas, com a
   ação do refino do primeiro documento, na ordem do lote, e o motivo `lote <ID>: <N> documentos, camadas <a> a <b>`
   (`camada <a>` com uma só); o mesmo vale para as revisões sem o marcador. Com o gate aprovado,
   `harness.py estado set Fase <fase seguinte>`, e as pendências com `antes do` aparecem nas revisões sem o marcador;
   com o da última fase, `planejamento concluído: todos os gates aprovados`.

Pré-checagem, só no comando e com o gate recomendado: os itens de script do gate, os do `harness.py gate`, sem o
leitor frio, que a `gate-fase` roda à parte; só lê. Logo abaixo do motivo, `Pré-checagem do <gate>: <n> FAIL`,
`Pré-checagem do <gate>: sem FAIL` ou `Pré-checagem do <gate>: não rodou: <motivo>`, este com a pré-condição que
recusa ou `<Tipo>: <primeira linha da mensagem>` de outro erro; o gate segue recomendado. Abaixo, até 3 linhas FAIL
`  <item> <verificação>: FAIL: <resumo>` e `  +<k> FAIL: harness.py gate <gate> --verbose` quando há mais; com
`--verbose`, todas, sem o `+<k>`. O INFO não aparece. O hook e o `fechar` não a rodam.

A saída segue o molde "Próximo" do `nucleo/comum/saida.md`; a linha `Atenção` traz o backlog ilegível, os estudos
com decisão por registrar, os relatos não incorporados, os avisos do ambiente, o retorno e, por último, a passagem.
Com `--verbose`, a fila inteira, as revisões por documento, também as sem o marcador (o lote, pelo motivo dele), e
`Retornos com pendência (<n>):`, com uma linha `  #N <título>: <pendências>` por issue, cada pendência resolvida com
` (resolvida)`. STATUS.md inválido sai com 1 e `STATUS.md inválido: <motivo>`.

Com `[passagem]` no perfil:

- Passagem por publicar, sem rede, também no hook, só com o último gate aprovado:
  `passagem: <gate> aprovado e nada publicado; harness.py passagem publicar`, sem tag `passagem/vN`; ou
  `passagem: revisão aprovada depois de passagem/vN; harness.py passagem publicar`, quando o `git diff` da última tag
  ao HEAD toca um artefato aprovado das fases, a legenda ou a pasta `[der] sql`. Num worktree, a ação ganha
  `(na árvore principal)`; a falha do git dá `passagem não conferida: <motivo>`.
- Retorno, só no comando: `gh issue list --label retorno --state open --limit 1000 --json number,title`, na raiz,
  com 10 s. A issue sem pendência, aberta ou resolvida, que cite `retorno #N` em qualquer célula vira
  `retorno sem pendência: #N <título>; registre por harness.py registrar pendencia --causa codigo citando retorno #N`; a com
  pendência sai só no `--verbose`. A falha dá `retorno não consultado: <motivo>`: `gh indisponível: <motivo>`,
  `gh passou de 10 s`, a primeira linha do erro do `gh` ou `saída do gh ilegível`.
"""

CONSERTAR = "consertar"
ANDAMENTO = "andamento"
FASE = "fase"
GERAR = "gerar"
MODULO = "modulo"
DERIVADOS = "derivados"
RASCUNHO = "rascunho"
OBRIGATORIO = "obrigatorio"
REVISAO = "revisao"
REVISAO_ANTES = "revisao-antes"
LOTE = "lote"
NOVO = "novo"
PENDENCIA = "pendencia"
GATE = "gate"
LIMITE_DEPOIS = 3
LIMITE_FILA_NO_HOOK = 2
LIMITE_PRE_CHECAGEM = 3
SUFIXO_WORKTREE = " (na árvore principal)"
TEMPO_LIMITE_GH = 10
LIMITE_DE_ISSUES = 1000

_REFINAR = f"/{comum.PREFIXO_DAS_SKILLS}refinar-documento "
_GERAR = f"/{comum.PREFIXO_DAS_SKILLS}gerar-modulos"
_PREFIXO_CONSERTAR = "consertar: "
_APROVADO_EM = "aprovado em "
_ESPERA = "quando o usuário liberar"
_MIGRACAO = "migração "
_SEPARADOR = " · "
_RE_CAMINHO_DO_DESTINO = re.compile(r"(?<![\w./:-])((?:[\w.-]+/)*[\w.-]+\.md|(?:[\w.-]+/)+)(?![\w/-])")
_A_ESCREVER = (MODULO, RASCUNHO, OBRIGATORIO, NOVO)
_DE_DOCUMENTO = (MODULO, DERIVADOS, RASCUNHO, OBRIGATORIO)


antes_do_arquivo = backlog.antes_do_arquivo


@dataclass(frozen=True)
class Item:
    categoria: str
    acao: str
    motivo: str
    documento: str = ""
    pendencias: tuple[str, ...] = ()


@dataclass(frozen=True)
class PreChecagem:
    """Os itens de script do gate recomendado, pelo `gate.rodar`: o gate, as linhas FAIL (`gate.linha`) e, quando
    ele não rodou, o motivo."""

    gate: str
    falhas: tuple[str, ...] = ()
    nao_rodou: str = ""


@dataclass(frozen=True)
class Proximo:
    """A ação recomendada, a fila da fase sem ela, as revisões sem o marcador do gate (que não seguram o gate), o
    marcador (vazio sem checklist), os itens de atenção, a linha da passagem por publicar, as issues de retorno com
    pendência, estas só para o `--verbose`, e a pré-checagem do gate recomendado, só no comando."""

    recomendado: Item
    fila: tuple[Item, ...]
    revisoes_sem_marcador: tuple[Item, ...]
    marcador: str
    atencao: tuple[str, ...]
    passagem: str = ""
    retornos: tuple[str, ...] = ()
    pre_checagem: PreChecagem | None = None

    @property
    def linha_curta(self) -> str:
        """A ação recomendada sem o motivo, com `consertar: ` antes no consertar, em até estado.LIMITE_PROXIMO."""
        prefixo = _PREFIXO_CONSERTAR if self.recomendado.categoria == CONSERTAR else ""
        return rastreio.cortar(prefixo + self.recomendado.acao, estado.LIMITE_PROXIMO)


@dataclass(frozen=True)
class _Fontes:
    """O que as regras leem: a raiz, o perfil, o status de cada documento da tabela (na ordem dela), as pendências
    abertas (linha, ID, destino) e o texto do backlog."""

    raiz: Path
    perfil: Perfil
    status: dict[str, str]
    pendencias: list[tuple[int, str, str]]
    texto_backlog: str = ""

    def aprovado(self, documento: str) -> bool:
        return rastreio.grupo_do_status(self.status.get(documento)) == rastreio.APROVADO

    def citantes(
        self, documento: str, marcador: str | None = None, com_marcador: bool = True, antes: bool | None = None
    ) -> list[str]:
        """Os IDs das pendências abertas cujo destino, sem os trechos `antes do <arquivo>.md`, cita o documento pelo
        nome do arquivo. Com `marcador`, só as que o trazem (`com_marcador`) ou só as que não o trazem; marcador vazio
        conta como ausente em todas. `antes`: True só as com o trecho, False só as sem ele, None todas."""
        nome = rastreio.padrao_do_nome(documento)
        ids = []
        for _, id_, destino in self.pendencias:
            trechos, resto = antes_do_arquivo(destino)
            if not nome.search(resto) or (antes is not None and bool(trechos) != antes):
                continue
            if marcador is not None:
                tem = bool(marcador) and marcador.casefold() in destino.casefold()
                if tem != com_marcador:
                    continue
            ids.append(id_)
        return ids


def _lista_quebrada(dados: dict[str, str], em_refino: list[str], mensagem: str) -> Item:
    """O `consertar` do `Lote` sem a lista, ou com a lista que não confere: o motivo é a mensagem do `estado` e o jeito
    de refazer, que no lote de migração é restaurar os documentos e rodar o `migrar` de novo. Com a versão marcada,
    os dois jeitos são recusados, e o texto começa pelo `versao limpar`, com a autorização do usuário."""
    origem = estado.origem_do_lote(dados[estado.CAMPO_LOTE])
    if origem.startswith(_MIGRACAO):
        refazer = ("restaure os documentos (git restore), feche com harness.py estado set Documento nenhum e rode "
                   "harness.py migrar de novo")
    else:
        refazer = f"refaça com harness.py estado lote {origem} <caminhos do destino>"
    if dados[versao.CAMPO] != versao.SEM_VERSAO:
        refazer = f"com a autorização do usuário, harness.py versao limpar; {refazer}"
    return Item(CONSERTAR, "a lista do lote falta ou não confere", f"{mensagem}; {refazer}",
                em_refino[0] if em_refino else "")


def _consertar(f: _Fontes, dados: dict[str, str], em_refino: list[str], executar) -> Item | None:
    """O que vem antes de tudo (§6.2, item 1), ou None."""
    passo = int(dados["Passo"])
    marcado = dados[versao.CAMPO]
    if passo == 7 and marcado != versao.SEM_VERSAO and em_refino:
        try:
            head = versao.no_head(f.raiz, em_refino, executar, grupo=versao.em_grupo(dados))
        except versao.VersaoInvalida:
            head = None
        if head is not None and not head.fora_do_commit and head.hash_head == marcado:
            if len(em_refino) == 1:
                alvo = f"de {posixpath.basename(em_refino[0])}"
            else:
                alvo = f"do {_grupo(dados)} de {len(em_refino)}"
            return Item(CONSERTAR, "harness.py fechar",
                        f"passo 7 {alvo} com {marcado} no HEAD {head.commit}; fecha sem pedir autorização", em_refino[0])
    no_disco = [(f.raiz / documento).is_file() for documento in em_refino]
    ajuste_aberto = passo == 6 and estado.CAMPO_AJUSTE in dados
    if passo in (6, 7) and marcado != versao.SEM_VERSAO and em_refino and all(no_disco) and not ajuste_aberto:
        try:
            atual = versao.hash_da_versao([(documento, (f.raiz / documento).read_bytes()) for documento in em_refino],
                                          versao.em_grupo(dados))
        except OSError:
            atual = marcado
        if atual != marcado:
            return Item(CONSERTAR, "harness.py versao conferir",
                        f"o documento mudou desde a marcação ({atual} != {marcado})", em_refino[0])
    ausente = next((documento for documento, existe in zip(em_refino, no_disco) if not existe), None)
    if ausente is not None and passo > 0:
        return Item(CONSERTAR, f"o documento em refino não existe: {ausente}",
                    f"passo {passo}; recupere o arquivo (git restore) ou feche o ciclo com o usuário", ausente)
    return _status_velho(f, dados, em_refino)


def _grupo(dados: dict[str, str]) -> str:
    """`lote` com `Lote` no STATUS, senão `pacote`."""
    return "lote" if estado.CAMPO_LOTE in dados else "pacote"


def _status_velho(f: _Fontes, dados: dict[str, str], em_refino: list[str]) -> Item | None:
    """O quarto caso do consertar (spec da onda 6, bloco D, §7.1): o documento ou pacote do STATUS, nos passos 0 a 6, todo aprovado na
    tabela e sem pendência aberta que o cite. O STATUS provavelmente está velho: a ação é perguntar ao usuário."""
    passo = int(dados["Passo"])
    if not em_refino or not 0 <= passo <= 6:
        return None
    if estado.origem_do_lote(dados.get(estado.CAMPO_LOTE, "")).startswith(_MIGRACAO):
        return None
    if not all(f.aprovado(documento) and not f.citantes(documento) for documento in em_refino):
        return None
    alvo = posixpath.basename(em_refino[0]) if len(em_refino) == 1 else f"o {_grupo(dados)} de {len(em_refino)}"
    volta = 'harness.py estado set Documento nenhum && harness.py passo 0 --proximo "<o que vem>"'
    if dados[versao.CAMPO] != versao.SEM_VERSAO:
        volta = f"com a autorização do usuário, harness.py versao limpar && {volta}"
    return Item(CONSERTAR, "perguntar ao usuário se o STATUS está velho",
                f"o STATUS aponta {alvo} (passo {passo}), aprovado no backlog e sem pendência aberta; "
                f"se está velho, {volta}", em_refino[0])


def _andamento(dados: dict[str, str], em_refino: list[str]) -> Item:
    passo = int(dados["Passo"])
    grupo = _grupo(dados) if estado.CAMPO_LOTE in dados or estado.CAMPO_PACOTE in dados else None
    primeiro = em_refino[0]
    nome = posixpath.basename(primeiro)
    if passo == 7:
        commit = f"commit do {grupo} de {nome}" if grupo else f"commit de {nome}"
        if _ESPERA in dados["Proximo"]:
            return Item(ANDAMENTO, f"perguntar ao usuário se libera o {commit}",
                        "passo 7 gravado; o usuário pediu para esperar o commit", primeiro)
        return Item(ANDAMENTO, f"{commit} e harness.py fechar", "passo 7 gravado; depois do commit, harness.py fechar",
                    primeiro)
    acao = f"{_REFINAR}{primeiro} (retoma do passo {passo})" + (f" ({grupo} de {len(em_refino)})" if grupo else "")
    return Item(ANDAMENTO, acao, dados["Proximo"], primeiro)


def _documentos_da_fase(f: _Fontes, fase: Fase, fora: list[str]) -> list[str]:
    """Os documentos da pasta da fase no disco: os da tabela, na ordem dela, e depois os de fora, por caminho; sem os
    de `fora`."""
    no_disco = [
        documento for documento in rastreio.documentos_do_planejamento(f.raiz, f.perfil)
        if documento not in fora and getattr(f.perfil.fase_do_documento(documento), "id", None) == fase.id
    ]
    da_tabela = [documento for documento in f.status if documento in no_disco]
    return da_tabela + [documento for documento in no_disco if documento not in f.status]


def _novo_do_caminho(f: _Fontes, citado: str, ocupados: list[str], documentos: list[str]) -> tuple[str, str] | None:
    """`(caminho, sufixo do motivo)` do documento novo que o caminho citado num destino pede, ou None: o caminho com
    pasta (a partir da raiz, ou da pasta do planejamento quando começa pelo id de uma fase) dentro da pasta de uma fase
    e sem arquivo no disco; a pasta dentro da pasta de uma fase; ou o nome sem pasta de nenhum `.md` do planejamento,
    de nenhum arquivo da raiz e de nenhum caminho de estado do perfil, na pasta dos irmãos de mesmo prefixo.
    `documentos`: os `.md` do planejamento, do `rastreio.documentos_do_planejamento`."""
    perfil = f.perfil
    pasta = perfil.caminhos.planejamento.rstrip("/")
    das_fases = tuple(f"{pasta}/{fase.id}/" for fase in perfil.fases)
    if "/" not in citado:
        if citado in {posixpath.basename(documento) for documento in ocupados}:
            return None
        c = perfil.caminhos
        estado_do_perfil = {posixpath.basename(caminho) for caminho in (c.status, c.backlog, c.decisoes, c.rascunho,
                                                                         c.legenda) if caminho}
        if (citado in {posixpath.basename(documento) for documento in documentos} or citado in estado_do_perfil
                or (f.raiz / citado).is_file()):
            return None
        prefixo = citado[:citado.index("-") + 1] if "-" in citado else ""
        irmaos = {posixpath.dirname(documento) for documento in documentos
                  if prefixo and posixpath.basename(documento).startswith(prefixo)}
        if len(irmaos) != 1:
            return f"<pasta>/{citado}", "; a pasta, com o usuário"
        caminho = f"{irmaos.pop()}/{citado}"
        return (caminho, "") if caminho.startswith(das_fases) else None
    if citado.split("/", 1)[0] in {fase.id for fase in perfil.fases}:
        citado = f"{pasta}/{citado}"
    caminho = posixpath.normpath(citado)
    if citado.endswith("/"):
        caminho += "/"
        dentro = caminho.startswith(das_fases) and caminho not in das_fases
        return (f"{caminho}<documento>.md", "; o nome sai da pendência") if dentro else None
    if not caminho.startswith(das_fases) or caminho in ocupados or (f.raiz / caminho).is_file():
        return None
    return caminho, ""


def _novos(f: _Fontes, marcador: str, ocupados: list[str]) -> list[Item]:
    """Os documentos novos que as pendências abertas com o marcador do gate pedem (spec da onda 3, §4.1), na ordem das
    pendências e, dentro de uma, na do destino; o mesmo caminho em mais de uma dá um item só, com os IDs juntos.
    `ocupados`: os documentos da fila e os em refino, que não viram item novo."""
    if not marcador:
        return []
    documentos = rastreio.documentos_do_planejamento(f.raiz, f.perfil)
    achados: dict[str, tuple[list[str], str]] = {}
    for _, id_, destino in f.pendencias:
        if marcador.casefold() not in destino.casefold():
            continue
        resto = antes_do_arquivo(destino)[1].replace("`", " ")
        for citado in _RE_CAMINHO_DO_DESTINO.findall(resto):
            novo = _novo_do_caminho(f, citado, ocupados, documentos)
            if novo is None:
                continue
            ids, _ = achados.setdefault(novo[0], ([], novo[1]))
            if id_ not in ids:
                ids.append(id_)
    return [Item(NOVO, _REFINAR + caminho, f"documento novo: {comum.juntar(ids)} ({marcador}){sufixo}", caminho,
                 tuple(ids))
            for caminho, (ids, sufixo) in achados.items()]


def _pendencias_sem_documento(
    f: _Fontes, marcador: str, fila: list[Item], em_refino: list[str], linkados: list[str]
) -> list[Item]:
    """As pendências abertas com o marcador do gate que nenhum item da fila cobre (spec da onda 3, §4.2), na ordem do
    backlog. Cobre a pendência o item que a traz nas `pendencias`, o item de documento (módulo, derivados, rascunho,
    obrigatório) cujo nome o destino dela cita, sem os trechos `antes do`, e, citados assim, o documento em refino e
    os `linkados`: os derivados em rascunho que o pacote de um módulo da fila refina."""
    if not marcador:
        return []
    cobertas = {id_ for item in fila for id_ in item.pendencias}
    nomes = [rastreio.padrao_do_nome(documento)
             for documento in [item.documento for item in fila if item.categoria in _DE_DOCUMENTO] + em_refino
             + linkados]
    itens = []
    for _, id_, destino in f.pendencias:
        if marcador.casefold() not in destino.casefold() or id_ in cobertas:
            continue
        resto = antes_do_arquivo(destino)[1]
        if any(nome.search(resto) for nome in nomes):
            continue
        itens.append(Item(PENDENCIA, f"resolver {id_} com o usuário", f"nenhum documento da fila a resolve: {destino}",
                          "", (id_,)))
    return itens


def _definir_lotes(f: _Fontes, em_refino: list[str]) -> dict[str, list[str]]:
    """Os lotes: a pendência aberta cujo destino cita dois ou mais aprovados (fora os em refino) dá o lote, com os
    documentos na ordem do lote. As pendências seguem a ordem do backlog, e o documento de um lote não entra em
    outro."""
    aprovados = [documento for documento in f.status if f.aprovado(documento) and documento not in em_refino]
    lotes: dict[str, list[str]] = {}
    tomados: set[str] = set()
    for _, id_, destino in f.pendencias:
        documentos = [documento for documento in lote.documentos_do_destino(destino, aprovados, f.perfil)
                      if documento not in tomados]
        if len(documentos) >= 2 and id_ not in lotes:
            lotes[id_] = documentos
            tomados.update(documentos)
    return lotes


def _item_do_lote(f: _Fontes, id_: str, documentos: list[str]) -> Item:
    """O item `lote`: a ação é o refino do primeiro documento, e o motivo traz o número de documentos e as camadas
    (a posição da fase na ordem das fases)."""
    fases = f.perfil.fases
    camadas = [fases.index(fase) + 1 if fase is not None else len(fases) + 1
               for fase in (f.perfil.fase_do_documento(documento) for documento in documentos)]
    primeira, ultima = min(camadas), max(camadas)
    faixa = f"camada {primeira}" if primeira == ultima else f"camadas {primeira} a {ultima}"
    return Item(LOTE, _REFINAR + documentos[0], f"lote {id_}: {len(documentos)} documentos, {faixa}", documentos[0],
                (id_,))


def _fila(f: _Fontes, dados: dict[str, str], em_refino: list[str], marcador: str) -> list[Item]:
    """A fila da fase (§6.2, item 3), do item 0 ao gate."""
    perfil = f.perfil
    fase = perfil.fase_por_id(dados["Fase"])
    valor_do_gate = dados.get(fase.gate, "")
    if valor_do_gate.startswith(_APROVADO_EM):
        posicao = perfil.fases.index(fase)
        if posicao + 1 < len(perfil.fases):
            acao = f"harness.py estado set Fase {perfil.fases[posicao + 1].id}"
        else:
            acao = "planejamento concluído: todos os gates aprovados"
        return [Item(FASE, acao, f"{fase.gate} {valor_do_gate}")]

    pasta = perfil.caminhos.planejamento.rstrip("/")
    checklist = perfil.gates.get(fase.gate)
    ligados = [item for item in (checklist.itens if checklist else ()) if item.verificacao == "ligados"]

    def casa(padroes, documento: str) -> bool:
        interno = documento[len(pasta) + 1:]
        return any(comum.casa_padrao(padrao, interno) for padrao in padroes)

    da_fase = _documentos_da_fase(f, fase, em_refino)
    modulos = [documento for documento in da_fase if any(casa(item.parametros["por"], documento) for item in ligados)]
    derivados: dict[str, list[str]] = {}
    for modulo in modulos:
        texto = rastreio.ler_ou_none(f.raiz / modulo)
        derivados[modulo] = (composicao.derivados(perfil, modulo, texto, da_fase, f.aprovado)
                             if texto is not None else [])
    linkados = {documento for lista in derivados.values() for documento in lista}
    obrigatorios = [f"{pasta}/{obrigatorio}" for obrigatorio in fase.obrigatorios]

    fila: list[Item] = []
    if (ligados and not modulos and not any(casa(item.parametros["por"], documento) for item in ligados
                                            for documento in em_refino)
            and all((f.raiz / caminho).is_file() and f.aprovado(caminho) for caminho in obrigatorios)):
        padroes = list(dict.fromkeys(padrao for item in ligados for padrao in item.parametros["por"]))
        fila.append(Item(GERAR, _GERAR, "nenhum " + " ou ".join(padroes) + " na fase"))
    for modulo in modulos:
        if f.aprovado(modulo):
            continue
        motivo = "módulo em rascunho"
        if derivados[modulo]:
            motivo += f"; linka {len(derivados[modulo])} em rascunho"
        ids = f.citantes(modulo)
        if ids:
            motivo += f"; pendências nele: {comum.juntar(ids)}"
        fila.append(Item(MODULO, _REFINAR + modulo, motivo, modulo))
    for modulo in modulos:
        if not f.aprovado(modulo) or not derivados[modulo]:
            continue
        motivo = f"derivados: {len(derivados[modulo])} em rascunho"
        ids = f.citantes(modulo)
        if ids:
            abertas = "aberta" if len(ids) == 1 else "abertas"
            motivo += f"; {comum.juntar(ids)} {abertas}: a skill pergunta revisão ou pacote"
        fila.append(Item(DERIVADOS, _REFINAR + modulo, motivo, modulo))
    for documento in da_fase:
        if f.aprovado(documento) or documento in modulos or documento in linkados or documento in obrigatorios:
            continue
        motivo = "em rascunho"
        if any(casa(item.parametros["documentos"], documento) for item in ligados):
            motivo += "; nenhum módulo o compõe"
        fila.append(Item(RASCUNHO, _REFINAR + documento, motivo, documento))
    for caminho in obrigatorios:
        if caminho in em_refino:
            continue
        if not (f.raiz / caminho).is_file():
            fila.append(Item(OBRIGATORIO, _REFINAR + caminho, "obrigatório, ausente", caminho))
        elif not f.aprovado(caminho):
            fila.append(Item(OBRIGATORIO, _REFINAR + caminho, "obrigatório, em rascunho", caminho))
    fila += _novos(f, marcador, [item.documento for item in fila] + em_refino)
    na_fila = {item.documento for item in fila}
    revisoes: list[Item] = []
    lotes = _definir_lotes(f, em_refino)
    emitidos: set[str] = set()

    def revisao(documento: str, fora: list[str]) -> tuple[Item, int | None] | None:
        """A revisão do aprovado, sem as pendências em `fora`, e o lugar dela na fila (None: com as revisões do
        marcador)."""
        com_antes = [id_ for id_ in f.citantes(documento, antes=True) if id_ not in fora]
        do_gate = [id_ for id_ in (f.citantes(documento, marcador, com_marcador=True) if marcador else [])
                   if id_ not in fora]
        ids = [id_ for _, id_, _ in f.pendencias if id_ in com_antes or id_ in do_gate]
        if not ids:
            return None
        rotulos = {}
        for _, id_, destino in f.pendencias:
            if id_ in com_antes:
                for arquivo, rotulo in antes_do_arquivo(destino)[0]:
                    rotulos.setdefault(arquivo, rotulo)
        def no_alvo(item: Item) -> bool:
            if item.categoria in _A_ESCREVER and posixpath.basename(item.documento) in rotulos:
                return True
            return (item.categoria in (MODULO, DERIVADOS)
                    and any(posixpath.basename(derivado) in rotulos for derivado in derivados.get(item.documento, ())))

        posicao = next((indice for indice, item in enumerate(fila) if no_alvo(item)), None)
        if posicao is not None:
            return Item(REVISAO_ANTES, _REFINAR + documento,
                        f"revisão: {comum.juntar(ids)} ({comum.juntar(rotulos.values())})",
                        documento, tuple(ids)), posicao
        marcas = list(rotulos.values()) + ([marcador] if set(do_gate) - set(com_antes) else [])
        return Item(REVISAO, _REFINAR + documento, f"revisão: {comum.juntar(ids)} ({comum.juntar(marcas)})",
                    documento, tuple(ids)), None

    for documento in f.status:
        if not f.aprovado(documento) or documento in na_fila or documento in em_refino:
            continue
        completa = revisao(documento, [])
        if completa is None:
            continue
        do_lote = [id_ for id_ in completa[0].pendencias if documento in lotes.get(id_, ())]
        novos = [id_ for id_ in do_lote if id_ not in emitidos]
        for deslocamento, id_ in enumerate(novos):
            if completa[1] is None:
                revisoes.append(_item_do_lote(f, id_, lotes[id_]))
            else:
                fila.insert(completa[1] + deslocamento, _item_do_lote(f, id_, lotes[id_]))
            emitidos.add(id_)
        final = revisao(documento, do_lote) if do_lote else completa
        if final is None:
            continue
        if final[1] is None:
            revisoes.append(final[0])
        else:
            fila.insert(final[1], final[0])
    fila += revisoes
    fila += _pendencias_sem_documento(f, marcador, fila, em_refino, sorted(linkados))
    fila.append(Item(GATE, f"/{comum.PREFIXO_DAS_SKILLS}gate-fase {fase.gate}",
                     "depois do resto da fila" if fila else "fila da fase vazia"))
    return fila


def _revisoes_sem_marcador(f: _Fontes, em_refino: list[str], marcador: str, gate_aprovado: bool) -> list[Item]:
    """As revisões dos aprovados citados por pendência sem o marcador; as com `antes do` só com o gate aprovado, porque
    sem ele já estão na fila."""
    itens = []
    lotes = _definir_lotes(f, em_refino)
    emitidos: set[str] = set()
    for documento in f.status:
        if not f.aprovado(documento) or documento in em_refino:
            continue
        ids = f.citantes(documento, marcador, com_marcador=False, antes=None if gate_aprovado else False)
        for id_ in [id_ for id_ in ids if documento in lotes.get(id_, ()) and id_ not in emitidos]:
            itens.append(_item_do_lote(f, id_, lotes[id_]))
            emitidos.add(id_)
        ids = [id_ for id_ in ids if documento not in lotes.get(id_, ())]
        if ids:
            itens.append(Item(REVISAO, _REFINAR + documento, f"revisão: {comum.juntar(ids)}", documento, tuple(ids)))
    return itens


def _atencao(f: _Fontes, backlog_ilegivel: bool, amb: ambiente.Ambiente) -> list[str]:
    itens = []
    if backlog_ilegivel:
        itens.append(f"backlog ausente ou ilegível: {f.perfil.caminhos.backlog}")
    por_registrar, ilegiveis = estudos.contar(f.raiz / f.perfil.caminhos.estudos)
    if por_registrar or ilegiveis:
        itens.append(f"estudos com decisão por registrar: {por_registrar}"
                     + (f"; ilegíveis: {ilegiveis}" if ilegiveis else ""))
    rascunho = f.perfil.caminhos.rascunho
    texto_rascunho = rastreio.ler_ou_none(f.raiz / rascunho) or ""
    pendentes = sum(r.pendente for r in registro.relatos(texto_rascunho, f.perfil.ids.prefixo_relato))
    if pendentes:
        itens.append(f"relatos não incorporados: {pendentes} ({rascunho})")
    itens += [item.linha for item in amb.avisos]
    return itens


def _toca_aprovado(f: _Fontes, caminho: str) -> bool:
    """O caminho é um artefato aprovado das pastas das fases, a legenda ou um arquivo da pasta `[der] sql`."""
    pasta = f.perfil.caminhos.planejamento.rstrip("/")
    if any(caminho.startswith(f"{pasta}/{fase.id}/") for fase in f.perfil.fases) and f.aprovado(caminho):
        return True
    if f.perfil.caminhos.legenda and caminho == f.perfil.caminhos.legenda:
        return True
    return f.perfil.der is not None and caminho.startswith(f"{pasta}/{f.perfil.der.sql.rstrip('/')}/")


def _passagem_por_publicar(f: _Fontes, dados: dict[str, str], executar, amb: ambiente.Ambiente) -> str:
    """A linha de Atenção da passagem por publicar, ou vazio; sem `[passagem]` ou com o último gate não aprovado, vazio,
    sem chamar o git."""
    ultimo = f.perfil.nomes_dos_gates[-1]
    if f.perfil.passagem is None or not dados.get(ultimo, "").startswith(_APROVADO_EM):
        return ""
    acao = "harness.py passagem publicar" + (SUFIXO_WORKTREE if amb.worktree else "")
    try:
        numeros = passagem.tags(f.raiz, executar)
        if not numeros:
            return f"passagem: {ultimo} aprovado e nada publicado; {acao}"
        mudados = passagem.mudados_desde(f.raiz, numeros[-1], executar)
    except passagem.ErroPassagem as erro:
        return f"passagem não conferida: {erro.mensagem}"
    if any(_toca_aprovado(f, caminho) for caminho in mudados):
        return f"passagem: revisão aprovada depois de {manifesto.PREFIXO_TAG}{numeros[-1]}; {acao}"
    return ""


def _issue_legivel(dado) -> bool:
    numero = dado.get("number") if isinstance(dado, dict) else None
    return isinstance(numero, int) and not isinstance(numero, bool) and isinstance(dado.get("title"), str)


def issues_de_retorno(raiz: Path, executar) -> tuple[list[tuple[int, str]], str]:
    """As issues `retorno` abertas (número e título), pelo `gh` na raiz, e o motivo da falha, ou vazio."""
    argv = ["gh", "issue", "list", "--label", manifesto.ROTULO_RETORNO, "--state", "open",
            "--limit", str(LIMITE_DE_ISSUES), "--json", "number,title"]
    try:
        feito = executar(argv, cwd=str(raiz), capture_output=True, timeout=TEMPO_LIMITE_GH)
    except OSError as erro:
        return [], f"gh indisponível: {comum.motivo_do_sistema(erro)}"
    except subprocess.TimeoutExpired:
        return [], f"gh passou de {TEMPO_LIMITE_GH} s"
    if feito.returncode != 0:
        return [], comum.motivo_do_git(feito, "issue list", "gh")
    try:
        dados = json.loads((feito.stdout or b"").decode("utf-8", errors="replace"))
    except ValueError:
        dados = None
    if not isinstance(dados, list) or not all(_issue_legivel(dado) for dado in dados):
        return [], "saída do gh ilegível"
    return [(dado["number"], dado["title"]) for dado in dados], ""


def _retorno(f: _Fontes, executar) -> tuple[list[str], list[str]]:
    """Os itens de Atenção do retorno e as linhas do `--verbose`: cada issue aberta com as pendências, abertas ou
    resolvidas, que a citam como `retorno #N` em qualquer célula."""
    issues, motivo = issues_de_retorno(f.raiz, executar)
    if motivo:
        return [f"retorno não consultado: {motivo}"], []
    citantes: dict[int, list[str]] = {}
    for _, celulas in backlog._pendencias(f.texto_backlog, f.perfil):
        resolvida = len(celulas) > 1 and celulas[-1].startswith("resolvida")
        rotulo = celulas[0] + (" (resolvida)" if resolvida else "")
        for issue in passagem.retornos_citados(" | ".join(celulas)):
            if rotulo not in citantes.setdefault(issue, []):
                citantes[issue].append(rotulo)
    atencao, linhas = [], []
    for numero, titulo in issues:
        if numero in citantes:
            linhas.append(f"#{numero} {titulo}: {comum.juntar(citantes[numero])}")
        else:
            atencao.append(f"retorno sem pendência: #{numero} {titulo}; registre por harness.py registrar pendencia "
                           f"--causa codigo citando retorno #{numero}")
    return atencao, linhas


def _pre_checar(raiz: Path, perfil: Perfil, nome: str, executar) -> PreChecagem:
    """Os itens de script do gate, pelo `gate.rodar` sem o leitor frio, com só as linhas FAIL. A pré-condição que
    recusa dá o motivo dela; outro erro dá `<Tipo>: <primeira linha da mensagem>`, sem derrubar o `proximo`."""
    try:
        resultados = gate.rodar(raiz, perfil, nome, executar, so_script=True)
    except gate.PreCondicao as erro:
        return PreChecagem(nome, nao_rodou=erro.mensagem)
    except Exception as erro:  # a pré-checagem não pode derrubar a recomendação
        primeira = (str(erro).splitlines() or [""])[0]
        return PreChecagem(nome, nao_rodou=f"{type(erro).__name__}: {primeira}")
    return PreChecagem(nome, tuple(gate.linha(resultado) for resultado in resultados
                                   if resultado.situacao == gate.FAIL))


def calcular(
    raiz: Path,
    perfil: Perfil,
    dados: dict[str, str] | None = None,
    executar=subprocess.run,
    amb: ambiente.Ambiente | None = None,
    consultar_retorno: bool = False,
    pre_checar: bool = False,
) -> Proximo:
    """O próximo passo. Sem `dados`, lê o STATUS (o EstadoInvalido sobe); sem `amb`, confere o ambiente da raiz. Só
    com `consultar_retorno` e `[passagem]` no perfil, o `gh` lista as issues de retorno. Só com `pre_checar` e o gate
    recomendado, o `gate.rodar` roda os itens de script dele."""
    if dados is None:
        dados = estado.ler(raiz / perfil.caminhos.status, perfil)
    if amb is None:
        amb = ambiente.conferir(raiz, executar)
    lista_quebrada = None
    try:
        em_refino = estado.documentos(dados, raiz)
    except estado.EstadoInvalido as erro:
        lista_quebrada = erro.mensagem
        em_refino = [] if dados["Documento"] == estado.SEM_DOCUMENTO else [dados["Documento"]]
    texto_backlog = rastreio.ler_ou_none(raiz / perfil.caminhos.backlog)
    f = _Fontes(raiz, perfil, rastreio.status_dos_artefatos(texto_backlog or "", perfil),
                backlog.pendencias_abertas(texto_backlog or "", perfil), texto_backlog or "")
    fase = perfil.fase_por_id(dados["Fase"])
    checklist = perfil.gates.get(fase.gate)
    marcador = checklist.marcador_pendencia if checklist else ""
    gate_aprovado = dados.get(fase.gate, "").startswith(_APROVADO_EM)

    fila = _fila(f, dados, em_refino, marcador)
    if lista_quebrada is not None:
        recomendado = _lista_quebrada(dados, em_refino, lista_quebrada)
    else:
        recomendado = _consertar(f, dados, em_refino, executar)
    if recomendado is not None and amb.worktree:
        recomendado = Item(recomendado.categoria, recomendado.acao + SUFIXO_WORKTREE, recomendado.motivo,
                           recomendado.documento, recomendado.pendencias)
    if recomendado is None and em_refino:
        recomendado = _andamento(dados, em_refino)
    if recomendado is None and _ESPERA in dados["Proximo"]:
        vem = fila[0].acao if fila else "<o que vem>"
        recomendado = Item(ANDAMENTO, f"perguntar ao usuário se libera o {dados['Proximo'].split(' ' + _ESPERA)[0]}",
                           "o usuário pediu para esperar o commit; liberado: "
                           f'harness.py estado set Proximo "{vem}" e o commit')
    if recomendado is None:
        recomendado, fila = fila[0], fila[1:]
    atencao = _atencao(f, texto_backlog is None, amb)
    retornos: list[str] = []
    if consultar_retorno and perfil.passagem is not None:
        itens, retornos = _retorno(f, executar)
        atencao += itens
    pre_checagem = None
    if pre_checar and recomendado.categoria == GATE:
        pre_checagem = _pre_checar(raiz, perfil, fase.gate, executar)
    return Proximo(recomendado, tuple(fila), tuple(_revisoes_sem_marcador(f, em_refino, marcador, gate_aprovado)),
                   marcador, tuple(atencao), _passagem_por_publicar(f, dados, executar, amb), tuple(retornos),
                   pre_checagem)


def _quantos(numero: int, singular: str, plural: str) -> str:
    return f"{numero} {singular if numero == 1 else plural}"


def _resto(itens: list[Item]) -> str:
    """O resto da fila agrupado por categoria, juntado por ` · `."""
    partes = []
    for categoria, singular, plural in (
        (MODULO, "módulo em rascunho", "módulos em rascunho"),
        (DERIVADOS, "módulo com derivados", "módulos com derivados"),
        (RASCUNHO, "em rascunho", "em rascunho"),
    ):
        numero = sum(1 for item in itens if item.categoria == categoria)
        if numero:
            partes.append("+" + _quantos(numero, singular, plural))
    partes += [f"{posixpath.basename(item.documento)} ({item.motivo})" for item in itens
               if item.categoria in (OBRIGATORIO, REVISAO_ANTES, NOVO, LOTE)]
    partes += [item.acao for item in itens if item.categoria in (PENDENCIA, GATE)]
    return _SEPARADOR.join(partes)


def _linhas_da_pre_checagem(pre: PreChecagem, verbose: bool) -> list[str]:
    """A linha `Pré-checagem do <gate>: ...` e, abaixo, as linhas FAIL: até LIMITE_PRE_CHECAGEM e o `+<k>` sem
    `verbose`, todas com ele."""
    titulo = f"Pré-checagem do {pre.gate}: "
    if pre.nao_rodou:
        return [f"{titulo}não rodou: {pre.nao_rodou}"]
    if not pre.falhas:
        return [titulo + "sem FAIL"]
    mostradas = pre.falhas if verbose else pre.falhas[:LIMITE_PRE_CHECAGEM]
    linhas = [f"{titulo}{len(pre.falhas)} FAIL", *(f"  {falha}" for falha in mostradas)]
    if len(pre.falhas) > len(mostradas):
        linhas.append(f"  +{len(pre.falhas) - len(mostradas)} FAIL: harness.py gate {pre.gate} --verbose")
    return linhas


def formatar(p: Proximo, verbose: bool = False) -> str:
    """A saída do `harness.py proximo`: até 12 linhas sem `verbose`; com ele, a fila e as revisões inteiras."""
    prefixo = _PREFIXO_CONSERTAR if p.recomendado.categoria == CONSERTAR else ""
    linhas = [f"Próximo: {prefixo}{p.recomendado.acao}", f"  {p.recomendado.motivo}"]
    if p.pre_checagem is not None:
        linhas += _linhas_da_pre_checagem(p.pre_checagem, verbose)
    da_fila = [item for item in p.fila if item.categoria != REVISAO]
    revisoes = [item for item in (p.recomendado, *p.fila) if item.categoria == REVISAO]
    if verbose:
        if da_fila:
            linhas.append(f"Fila ({len(da_fila)}):")
            linhas += [f"  {item.acao}  ({item.motivo})" for item in da_fila]
        for titulo, grupo in ((f"Revisões {p.marcador}", revisoes), ("Revisões sem o marcador", p.revisoes_sem_marcador)):
            if grupo:
                linhas.append(f"{titulo} ({len(grupo)}):")
                linhas += [f"  {item.documento}: "
                           + (item.motivo if item.categoria == LOTE else comum.juntar(item.pendencias))
                           for item in grupo]
        if p.retornos:
            linhas.append(f"Retornos com pendência ({len(p.retornos)}):")
            linhas += [f"  {retorno}" for retorno in p.retornos]
    else:
        if da_fila:
            linhas.append("Depois:")
            linhas += [f"  {item.acao}  ({item.motivo})" for item in da_fila[:LIMITE_DEPOIS]]
            if da_fila[LIMITE_DEPOIS:]:
                linhas.append("  " + _resto(da_fila[LIMITE_DEPOIS:]))
        if revisoes:
            ids = {id_ for item in revisoes for id_ in item.pendencias}
            linhas.append(
                f"Revisões {p.marcador}: {_quantos(len(ids), 'pendência', 'pendências')} em "
                f"{_quantos(len(revisoes), 'documento aprovado', 'documentos aprovados')} (--verbose)"
            )
    atencao = [*p.atencao, p.passagem] if p.passagem else list(p.atencao)
    if atencao:
        linhas.append("Atenção: " + _SEPARADOR.join(atencao))
    return "".join(linha + "\n" for linha in linhas)


def linhas_do_hook(p: Proximo) -> list[str]:
    """As linhas do contexto do início da sessão: a ação recomendada com o motivo, até LIMITE_FILA_NO_HOOK ações da
    fila e a linha da passagem por publicar."""
    linhas = [f"Próximo: {p.linha_curta} ({p.recomendado.motivo})"]
    acoes = [item.acao for item in p.fila if item.categoria != REVISAO][:LIMITE_FILA_NO_HOOK]
    if acoes:
        linhas.append("Depois: " + _SEPARADOR.join(acoes))
    if p.passagem:
        linhas.append("Atenção: " + p.passagem)
    return linhas
