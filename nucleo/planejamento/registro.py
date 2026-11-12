"""Registro no ato (spec 4b, §10, e 4a, §9): Ruling, pendência e relato acrescentados no formato de cada arquivo, sem
tirar linha. De uma linha que já existe, só mudam as células de status e de destino de uma pendência aberta (`nota`,
`resolver_pendencia` e `trocar_destino`). O Ruling vai para o arquivo de decisões, a pendência para o arquivo de pendências, e o
relato, ou o status dele, para a seção de informação nova do rascunho. Os registros do passo 7 (spec 6a, §5.1), a
aprovação, a abordagem descartada e o trecho do rascunho processado, vão para as seções deles no arquivo de
decisões."""
from __future__ import annotations

import datetime
import posixpath
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import backlog
import comum
import estado
import lote
from perfil import Perfil

AJUDA = """\
Acrescenta no ato um Ruling ao arquivo de decisões, uma pendência ao backlog.md, uma nota a uma pendência aberta, um
relato ao rascunho ou um registro do passo 7.

Só o `registrar nota` muda uma linha que já existe, e só a célula de status; as outras ações não tiram nem
alteram linha: a linha nova entra no fim da seção ou da tabela, com a quebra de linha do arquivo,
e a saída diz onde. Recusa sai com 1 e `recusado: <motivo>`, sem gravar: texto vazio ou com quebra de linha, arquivo
ausente ou ilegível, arquivo sem a seção ou a tabela.

`registrar ruling` grava a linha na seção de Rulings do arquivo de decisões (`caminhos.decisoes`), do primeiro título
`## ` com "Ruling" até o próximo título de nível 1 ou 2, e imprime `Ruling acrescentado em <arquivo>:<linha>`. Vale o
Ruling mais recente.

`registrar pendencia` grava a pendência aberta, com o número seguinte ao maior, como última linha da tabela de
pendências do backlog.md, e imprime `<prefixo>-NN acrescentada em <arquivo>:<linha>`. O `--causa` é obrigatório, de
uma lista fixa, e é gravado no fim da Origem. Recusa também `|` no texto, na origem ou no destino, e IDs de pendência
com erro, que vêm abaixo como no `harness.py backlog ids`. Ela vem só de uma das três fontes da escada de
`pendencias.md` do núcleo (a resposta "Abrir pendência", o pedido do usuário no modo revisão, o retorno do código);
antes, a nota numa pendência aberta de mesmo destino.

`registrar nota` acrescenta `; <AAAA-MM-DD>: <nota>` ao fim da célula de status de uma pendência aberta, sem mexer no
resto da linha, e imprime `<prefixo>-NN anotada em <arquivo>:<linha>`. O ID casa pelo número, de modo que `<prefixo>-3`
acha a `<prefixo>-03`. Recusa nota vazia, com quebra de linha ou com `|`, pendência fora do backlog ou que não está
aberta, e IDs com erro. O que sobra noutro documento começa a nota por `resta em <documento>: `. A nota `resta em <documento>` de um documento do lote
aberto é recusada: o que resta dele se resolve no ciclo.

```text
- <AAAA-MM-DD> Ruling: <decisão> — <por quê> — <custo se errado>.
| <prefixo>-NN | <pendência> | <nome do arquivo de origem>, <AAAA-MM-DD>, causa: <causa> | <destino> | aberta |
| <prefixo>-NN | ... | ... | <destino> | aberta; <AAAA-MM-DD>: <nota> |
```

`registrar aprovacao`, `registrar descartada` e `registrar trecho` gravam a linha no fim da seção do arquivo de
decisões cujo título `## ` começa por "Aprovações", "Abordagens descartadas" ou "Trechos do rascunho", até o próximo
título de nível 1 ou 2, e imprimem `Aprovação acrescentada em <arquivo>:<linha>`,
`Abordagem descartada acrescentada em <arquivo>:<linha>` ou `Trecho acrescentado em <arquivo>:<linha>`.

```text
- <AAAA-MM-DD> <texto>
```

`registrar medicao` grava a linha no fim da primeira tabela `| Medição | Valor | Data |` da seção do arquivo de
atritos (`caminhos.atritos`) cujo título `## ` começa por "Medições dos ciclos", e imprime
`Medição acrescentada em <arquivo>:<linha>`. Recusa também `|` na medição ou no valor.

```text
| <medição> | <valor> | <AAAA-MM-DD> |
```

`registrar relato` grava na seção `## Informação nova da conversa` do rascunho (`caminhos.rascunho`), criada no fim
quando falta. Com o texto e `--origem`, acrescenta o relato e imprime `<prefixo>-NN acrescentado em <arquivo>:<linha>`;
com `--id` e `--status`, acrescenta uma linha de status, sem mudar a do relato, e imprime
`<prefixo>-NN: <status> (<arquivo>:<linha>)`. As duas formas juntas, ou nenhuma inteira, são uso inválido. O prefixo
é o `ids.prefixo_relato`, `REL` sem ele.

```text
- <AAAA-MM-DD> <prefixo>-NN: <relato> (<nome do arquivo de origem>) — não confirmada
- <AAAA-MM-DD> <prefixo>-NN: incorporada em <nome do documento>
```

- O relato entra `não confirmada`, ou `confirmada` com `--confirmada`, e fica pendente até ser incorporado ou
  descartado.
- O status é `confirmada` (recusado se já está), `incorporada` (pede `--em`, um arquivo do repositório que existe;
  cada documento o incorpora uma vez) ou `descartada` (pede `--motivo`; o relato descartado não muda mais).
- O `--origem` fica dentro da pasta do planejamento. O `--em` é o caminho a partir da raiz, ou só o nome do arquivo,
  quando ele é único entre os arquivos que o git não ignora; fora do repositório, ausente ou ambíguo, é recusado.
"""

MARCA_DA_SECAO = "Ruling"
_TEMPO_LIMITE_GIT = 5
CABECALHO_DE_PENDENCIAS = "| ID | Pendência | Origem | Destino | Status |"
_RE_TITULO_ATE_2 = re.compile(r"#{1,2} ")
_RE_SEPARADORA = re.compile(r"\|[\s:|-]*-[\s:|-]*")


class RegistroRecusado(Exception):
    """O registro não pode ser feito, e nada foi gravado. `mensagem` cabe numa linha; `detalhes` vêm abaixo dela."""

    def __init__(self, mensagem: str, detalhes: tuple[str, ...] = ()):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.detalhes = tuple(detalhes)


def _texto(rotulo: str, valor: str, sem_barra: bool = False) -> str:
    """O valor sem os espaços das pontas; recusa vazio, com quebra de linha e, com `sem_barra`, com `|`."""
    valor = valor.strip()
    if not valor:
        raise RegistroRecusado(f"{rotulo}: vazio")
    if "\n" in valor or "\r" in valor:
        raise RegistroRecusado(f"{rotulo}: quebra de linha")
    if sem_barra and "|" in valor:
        raise RegistroRecusado(f"{rotulo}: tem |, que quebraria a tabela")
    return valor


def _ler(raiz: Path, relativo: str) -> str:
    try:
        return comum.ler_texto(raiz / relativo)
    except FileNotFoundError:
        raise RegistroRecusado(f"arquivo ausente: {relativo}") from None
    except UnicodeDecodeError:
        raise RegistroRecusado(f"arquivo não está em UTF-8: {relativo}") from None
    except OSError as erro:
        raise RegistroRecusado(f"arquivo ilegível: {relativo} ({comum.motivo_do_sistema(erro)})") from None


def _quebra(linha: str) -> str:
    """O `\\r` do fim da linha, para a linha nova seguir as quebras do arquivo."""
    return "\r" if linha.endswith("\r") else ""


def ruling(raiz: Path, perfil: Perfil, oque: str, porque: str, custo: str, hoje: str | None = None) -> int:
    """Acrescenta `- <hoje> Ruling: <o quê> — <por quê> — <custo>.` depois da última linha não vazia da seção de
    Rulings (do primeiro título `## ` com "Ruling" até o próximo título de nível 1 ou 2) e devolve o número da linha
    nova. O ponto final não se repete quando o custo já termina em ponto. Recusa lança RegistroRecusado sem gravar."""
    oque = _texto("decisão", oque)
    porque = _texto("--por", porque)
    custo = _texto("--custo", custo)
    hoje = hoje or datetime.date.today().isoformat()
    relativo = perfil.caminhos.decisoes
    linhas = _ler(raiz, relativo).split("\n")
    inicio = next((i for i, linha in enumerate(linhas) if linha.startswith("## ") and MARCA_DA_SECAO in linha), None)
    if inicio is None:
        raise RegistroRecusado(f"{relativo} sem a seção de Rulings (um título ## com Ruling)")
    fim = next((i for i in range(inicio + 1, len(linhas)) if _RE_TITULO_ATE_2.match(linhas[i])), len(linhas))
    ultima = max(i for i in range(inicio, fim) if linhas[i].strip())
    quebra = _quebra(linhas[ultima])
    final = "" if custo.endswith(".") else "."
    novas = [f"- {hoje} Ruling: {oque} — {porque} — {custo}{final}{quebra}"]
    if ultima == inicio:
        novas.insert(0, quebra)
    linhas[ultima + 1:ultima + 1] = novas
    comum.escrever_texto(raiz / relativo, "\n".join(linhas))
    return ultima + 1 + len(novas)


def _fim_da_tabela(linhas: list[str], inicio: int) -> int:
    """O índice da última linha da tabela que tem a linha `inicio`: as linhas seguidas que começam por `|`, parando
    antes do cabeçalho da tabela de artefatos."""
    fim = inicio
    while (
        fim + 1 < len(linhas)
        and linhas[fim + 1].strip().startswith("|")
        and tuple(backlog.celulas(linhas[fim + 1])) != backlog.CABECALHO_ARTEFATOS
    ):
        fim += 1
    return fim


def _ultima_da_tabela(linhas: list[str], pendencias: list[tuple[int, str, str]]) -> int | None:
    """O índice da última linha da tabela de pendências: a que tem as linhas de pendência; sem nenhuma, a primeira
    tabela de cinco colunas cujo cabeçalho começa por ID. None sem tabela."""
    if pendencias:
        return _fim_da_tabela(linhas, pendencias[-1][0] - 1)
    for indice, linha in enumerate(linhas[:-1]):
        celulas = backlog.celulas(linha)
        if (linha.strip().startswith("|") and len(celulas) == 5 and celulas[0] == "ID"
                and _RE_SEPARADORA.fullmatch(linhas[indice + 1].strip())):
            return _fim_da_tabela(linhas, indice + 1)
    return None


def pendencia(
    raiz: Path, perfil: Perfil, texto: str, origem: str, destino: str, causa: str, hoje: str | None = None
) -> tuple[str, int]:
    """Acrescenta `| <prefixo>-<NN> | <texto> | <nome do arquivo de origem>, <hoje>, causa: <causa> | <destino> | aberta |`
    depois da
    última linha da tabela de pendências, com o número seguinte ao maior, e devolve o ID e o número da linha nova.

    Recusa lança RegistroRecusado sem gravar: texto, origem ou destino vazio, com quebra de linha ou com `|`; IDs com
    erro, os mesmos que `harness.py backlog ids` acusa, que vão nos detalhes; arquivo sem a tabela de pendências. A causa
    fora de `backlog.CAUSAS` também é recusada."""
    texto = _texto("pendência", texto, sem_barra=True)
    origem = _texto("--origem", origem, sem_barra=True)
    destino = _texto("--destino", destino, sem_barra=True)
    if causa not in backlog.CAUSAS:
        raise RegistroRecusado(f"--causa: {causa} não está na lista")
    hoje = hoje or datetime.date.today().isoformat()
    relativo = perfil.caminhos.backlog
    conteudo = _ler(raiz, relativo)
    erros = backlog.conferir_ids(conteudo, perfil)
    if erros:
        raise RegistroRecusado(
            "os IDs das pendências têm erro; corrija antes de acrescentar (harness.py backlog ids)", tuple(erros)
        )
    pendencias = backlog.linhas_de_pendencia(conteudo, perfil)
    linhas = conteudo.split("\n")
    ultima = _ultima_da_tabela(linhas, pendencias)
    if ultima is None:
        raise RegistroRecusado(f"{relativo} sem a tabela de pendências ({CABECALHO_DE_PENDENCIAS})")
    numero = max((int(id_.rsplit("-", 1)[1]) for _, id_, _ in pendencias), default=0) + 1
    id_ = f"{perfil.ids.prefixo_pendencia}-{numero:02d}"
    nome = posixpath.basename(origem.replace("\\", "/"))
    nova = (f"| {id_} | {texto} | {nome}, {hoje}, causa: {causa} | {destino} | {backlog.PREFIXO_ABERTA} |"
            f"{_quebra(linhas[ultima])}")
    linhas.insert(ultima + 1, nova)
    comum.escrever_texto(raiz / relativo, "\n".join(linhas))
    return id_, ultima + 2


def resolver_pendencia(
    raiz: Path, perfil: Perfil, id_: str, em: str, como: str, hoje: str | None = None, executar=subprocess.run
) -> tuple[int, str]:
    """Troca a célula de status da pendência aberta `id_` por `resolvida em <nome do arquivo de em>, <hoje>: <como>`
    e devolve o número da linha dela e o ID como está no backlog. O `id_` casa pelo número, de modo que
    `<prefixo>-3` e `<prefixo>-003` acham a `<prefixo>-03`. A nota de um status `aberta; <nota>` vai ao fim, depois
    de `; histórico: `, com o status antigo inteiro. O resto da linha fica igual, e a barra final só volta se a
    linha a tinha.

    Recusa lança RegistroRecusado sem gravar: `como` vazio, com quebra de linha ou com `|`; `em` fora do
    repositório, que não existe ou ambíguo (`_no_repositorio`, que usa o `executar` para o git); IDs com erro, nos
    detalhes; pendência fora do backlog ou que não está aberta."""
    como = _texto("como", como, sem_barra=True)
    normal = _no_repositorio(raiz, em, executar)
    hoje = hoje or datetime.date.today().isoformat()
    relativo = perfil.caminhos.backlog
    conteudo = _ler(raiz, relativo)
    numero, id_, status = _pendencia_aberta(conteudo, perfil, id_, "resolver")
    novo_status = f"resolvida em {posixpath.basename(normal)}, {hoje}: {como}"
    if status.strip() != backlog.PREFIXO_ABERTA:
        novo_status += f"; histórico: {status.strip()}"
    linhas = conteudo.split("\n")
    linhas[numero - 1] = _trocar_celulas(linhas[numero - 1], None, novo_status)
    comum.escrever_texto(raiz / relativo, "\n".join(linhas))
    return numero, id_


def _pendencia_aberta(conteudo: str, perfil: Perfil, id_: str, acao: str) -> tuple[int, str, str]:
    """Acha a pendência `id_` no backlog e devolve o número da linha dela (contado de 1), o ID como está no backlog
    e o status. O `id_` casa pelo número, sem importar caixa nem zeros. Recusa IDs com erro (nos detalhes, com a
    `acao` na mensagem), pendência fora do backlog e pendência que não está aberta."""
    erros = backlog.conferir_ids(conteudo, perfil)
    if erros:
        raise RegistroRecusado(
            f"os IDs das pendências têm erro; corrija antes de {acao} (harness.py backlog ids)", tuple(erros)
        )
    procurado = _numero_da_pendencia(id_, perfil)
    achada = next(((numero, outro, status) for numero, outro, status in backlog.linhas_de_pendencia(conteudo, perfil)
                   if procurado is not None and _numero_da_pendencia(outro, perfil) == procurado), None)
    if achada is None:
        raise RegistroRecusado(f"{id_} não está no backlog")
    numero, id_, status = achada
    if not status.startswith(backlog.PREFIXO_ABERTA):
        raise RegistroRecusado(f"{id_} não está aberta: {status}")
    return numero, id_, status


def _trocar_celulas(linha: str, destino: str | None, status: str) -> str:
    """A linha da pendência com a célula de status trocada por `status` e, se `destino` não é None, a de destino
    também. O resto fica igual: a quebra `\\r` do fim e a barra final, que só volta se a linha a tinha."""
    quebra = _quebra(linha)
    corpo = linha.rstrip()
    barra_final = corpo.endswith("|")
    if barra_final:
        corpo = corpo[:-1].rstrip()
    antes = corpo[:corpo.rindex("|") + 1]
    if destino is not None:
        antes = antes[:antes.rindex("|")]
        antes = f"{antes[:antes.rindex('|') + 1]} {destino} |"
    return f"{antes} {status}{' |' if barra_final else ''}{quebra}"


def _documentos_do_lote(raiz: Path, perfil: Perfil) -> list[str]:
    """Os documentos do lote aberto, na ordem dele. Vazio sem `Lote` e com o STATUS.md ou a lista inválidos: nesse caso
    a trava do lote não vale."""
    try:
        dados = estado.ler(raiz / perfil.caminhos.status, perfil)
        if estado.CAMPO_LOTE not in dados:
            return []
        return estado.documentos(dados, raiz)
    except (estado.EstadoInvalido, OSError):
        return []


def _recusa_do_lote(documento: str) -> RegistroRecusado:
    return RegistroRecusado(f"{posixpath.basename(documento)} está no lote aberto; o que resta dele se resolve neste ciclo")


_RE_RESTA_EM = re.compile(r"resta em `?([^\s:`]+\.md)`?")


def nota(raiz: Path, perfil: Perfil, id_: str, texto: str, hoje: str | None = None) -> tuple[int, str]:
    """Acrescenta `<hoje>: <texto>` ao fim da célula de status da pendência aberta `id_`, depois de `; `, e devolve o
    número da linha dela e o ID como está no backlog. O resto da linha fica igual.

    Recusa lança RegistroRecusado sem gravar: `texto` vazio, com quebra de linha ou com `|`; IDs com erro, nos
    detalhes; pendência fora do backlog ou que não está aberta; nota `resta em <documento>` de um documento do lote
    aberto."""
    texto = _texto("nota", texto, sem_barra=True)
    hoje = hoje or datetime.date.today().isoformat()
    relativo = perfil.caminhos.backlog
    conteudo = _ler(raiz, relativo)
    numero, id_, status = _pendencia_aberta(conteudo, perfil, id_, "anotar")
    achado = _RE_RESTA_EM.match(texto) if texto.startswith("resta em ") else None
    if achado:
        nome = achado.group(1)
        for documento in _documentos_do_lote(raiz, perfil):
            if posixpath.basename(documento) == posixpath.basename(nome):
                raise _recusa_do_lote(documento)
    linhas = conteudo.split("\n")
    linhas[numero - 1] = _trocar_celulas(linhas[numero - 1], None, f"{status.strip()}; {hoje}: {texto}")
    comum.escrever_texto(raiz / relativo, "\n".join(linhas))
    return numero, id_


def trocar_destino(
    raiz: Path, perfil: Perfil, id_: str, destino: str, hoje: str | None = None, dispensa: str | None = None
) -> tuple[int, str]:
    """Troca a célula de destino da pendência aberta `id_` por `destino` e acrescenta `; <hoje>: destino era <antigo>`
    ao fim do status. Devolve o número da linha dela e o ID como está no backlog. O `id_` casa pelo número, e o resto
    da linha fica igual.

    Recusa lança RegistroRecusado sem gravar: `destino` vazio, com quebra de linha ou com `|`; destino novo que perde
    o marcador de um gate que o antigo tinha, sem distinção de maiúsculas; destino igual ao atual; linha sem a célula
    de destino; IDs com erro, nos detalhes; pendência fora do backlog ou que não está aberta; destino novo que cita um
    documento do lote aberto (o primeiro, na ordem do lote).

    Com `dispensa` (o motivo, sem `|`), o destino novo pode perder o marcador do primeiro gate, na ordem do perfil,
    que o antigo tinha, e o status ganha `; <hoje>: dispensada no <gate>: <dispensa>; destino era <antigo>`. A
    `dispensa` sem marcador perdido é recusada."""
    destino = _texto("destino", destino, sem_barra=True)
    if dispensa is not None:
        dispensa = _texto("dispensa", dispensa, sem_barra=True)
    hoje = hoje or datetime.date.today().isoformat()
    relativo = perfil.caminhos.backlog
    conteudo = _ler(raiz, relativo)
    numero, id_, status = _pendencia_aberta(conteudo, perfil, id_, "trocar o destino")
    linhas = conteudo.split("\n")
    celulas = backlog.celulas(linhas[numero - 1])
    if len(celulas) < 3:
        raise RegistroRecusado(f"{id_} não tem a célula de destino")
    antigo = celulas[-2]
    if destino.strip() == antigo.strip():
        raise RegistroRecusado("destino: igual ao atual")
    perdido = next((gate for gate in perfil.gates.values()
                    if gate.marcador_pendencia.casefold() in antigo.casefold()
                    and gate.marcador_pendencia.casefold() not in destino.casefold()), None)
    if perdido is not None and dispensa is None:
        raise RegistroRecusado(
            f'o destino novo perde "{perdido.marcador_pendencia}", que segura o {perdido.nome}; '
            'na dispensa do gate, use --dispensa "<motivo>"'
        )
    if perdido is None and dispensa is not None:
        raise RegistroRecusado("--dispensa só vale quando o destino novo perde o marcador de um gate")
    for documento in _documentos_do_lote(raiz, perfil):
        if lote.cita(destino, documento):
            raise _recusa_do_lote(documento)
    anotacao = f"dispensada no {perdido.nome}: {dispensa}; " if perdido is not None else ""
    linhas[numero - 1] = _trocar_celulas(
        linhas[numero - 1], destino, f"{status.strip()}; {hoje}: {anotacao}destino era {antigo}"
    )
    comum.escrever_texto(raiz / relativo, "\n".join(linhas))
    return numero, id_


def _numero_da_pendencia(id_: str, perfil: Perfil) -> int | None:
    achado = re.fullmatch(re.escape(perfil.ids.prefixo_pendencia) + r"-([0-9]+)", id_.strip(), re.IGNORECASE)
    return int(achado.group(1)) if achado else None


TITULO_DOS_RELATOS = "## Informação nova da conversa (só acréscimos, por harness.py registrar relato)"
INICIO_DOS_RELATOS = "## Informação nova da conversa"
CONFIRMADA = "confirmada"
INCORPORADA = "incorporada"
DESCARTADA = "descartada"


@dataclass(frozen=True)
class Relato:
    """Um relato da seção de informação nova do rascunho: o ID, a linha da entrada (contada de 1), se o usuário o
    confirmou, os nomes dos documentos em que foi incorporado e se foi descartado."""

    id: str
    linha: int
    confirmada: bool
    incorporada_em: tuple[str, ...]
    descartada: bool

    @property
    def pendente(self) -> bool:
        return not self.incorporada_em and not self.descartada


def _expressoes(prefixo: str) -> tuple[re.Pattern, re.Pattern]:
    """A linha de entrada e a de status dos relatos com o prefixo dado."""
    p = re.escape(prefixo)
    entrada = re.compile(
        rf"^- (\d{{4}}-\d{{2}}-\d{{2}}) ({p}-\d{{2,}}): (.+) \(([^()]+)\) — (não {CONFIRMADA}|{CONFIRMADA})$"
    )
    status = re.compile(
        rf"^- (\d{{4}}-\d{{2}}-\d{{2}}) ({p}-\d{{2,}}): ({CONFIRMADA}|{INCORPORADA} em (.+)|{DESCARTADA}: (.+))$"
    )
    return entrada, status


def _secao_dos_relatos(linhas: list[str]) -> tuple[int, int] | None:
    """O índice do título da seção de relatos e o do fim dela (o próximo título de nível 1 ou 2, ou o fim do
    arquivo); None sem a seção."""
    inicio = next((i for i, linha in enumerate(linhas) if linha.startswith(INICIO_DOS_RELATOS)), None)
    if inicio is None:
        return None
    fim = next((i for i in range(inicio + 1, len(linhas)) if _RE_TITULO_ATE_2.match(linhas[i])), len(linhas))
    return inicio, fim


def relatos(texto: str, prefixo: str) -> list[Relato]:
    """Os relatos da seção de informação nova, na ordem das entradas, com o status que as linhas seguintes deram a
    cada um. Linha de status de um ID sem entrada não conta."""
    linhas = texto.split("\n")
    secao = _secao_dos_relatos(linhas)
    if secao is None:
        return []
    entrada, status = _expressoes(prefixo)
    achados: dict[str, dict] = {}
    for indice in range(secao[0] + 1, secao[1]):
        linha = linhas[indice].rstrip("\r")
        casou = entrada.match(linha)
        if casou:
            achados.setdefault(casou.group(2), {
                "linha": indice + 1, "confirmada": casou.group(5) == CONFIRMADA, "em": [], "descartada": False,
            })
            continue
        casou = status.match(linha)
        if not casou or casou.group(2) not in achados:
            continue
        relato_ = achados[casou.group(2)]
        if casou.group(3) == CONFIRMADA:
            relato_["confirmada"] = True
        elif casou.group(4) is not None:
            relato_["em"].append(casou.group(4))
        else:
            relato_["descartada"] = True
    return [
        Relato(id_, dados["linha"], dados["confirmada"], tuple(dados["em"]), dados["descartada"])
        for id_, dados in achados.items()
    ]


def _no_planejamento(perfil: Perfil, rotulo: str, caminho: str) -> str:
    """O caminho normalizado do `--origem`, recusado quando fica fora da pasta do planejamento. Só o `--origem` o
    usa; o `--em` passa pelo `_no_repositorio`."""
    pasta = perfil.caminhos.planejamento.rstrip("/")
    normal = posixpath.normpath(caminho.replace("\\", "/"))
    if not normal.startswith(pasta + "/"):
        raise RegistroRecusado(f"{rotulo} fora da pasta do planejamento ({pasta}): {caminho}")
    return normal


def _no_repositorio(raiz: Path, caminho: str, executar=subprocess.run) -> str:
    """O caminho de um arquivo do repositório, relativo à raiz e em posix, para o `--em`. Aceita o caminho a partir
    da raiz (ou o absoluto dentro dela, mesmo por um link que a raiz não usa) e o nome curto: o nome sem pasta que
    não é arquivo na raiz é procurado, pelo nome do arquivo, na lista do `git ls-files --cached --others
    --exclude-standard`, com commit ou sem, e vale quando um só arquivo do disco o tem. Recusa lança
    RegistroRecusado: `--em fora do repositório: <caminho>` (fora da raiz, acima dela ou dentro de `.git/`), `--em
    não existe: <caminho>`, `--em ambíguo: <caminho>; use o caminho` (os candidatos em ordem alfabética nos
    detalhes) e a falha do git."""
    normal = posixpath.normpath(caminho.replace("\\", "/"))
    if Path(normal).is_absolute():
        absoluto = Path(normal)
        resolvida = raiz.resolve()
        # A grafia como veio, contra a raiz como veio e contra a resolvida; e a pasta de cima resolvida, sem seguir o
        # link do próprio arquivo, contra a resolvida (o `--em` por um link que a raiz não usa, como o tmp do macOS).
        tentativas = (
            (absoluto, raiz), (absoluto, resolvida), (absoluto.parent.resolve() / absoluto.name, resolvida),
        )
        for candidato, base in tentativas:
            try:
                normal = candidato.relative_to(base).as_posix()
                break
            except ValueError:
                continue
        else:
            raise RegistroRecusado(f"--em fora do repositório: {caminho}")
    if normal == ".." or normal.startswith("../") or normal == ".git" or normal.startswith(".git/"):
        raise RegistroRecusado(f"--em fora do repositório: {caminho}")
    if (raiz / normal).is_file():
        return normal
    if "/" in normal:
        raise RegistroRecusado(f"--em não existe: {caminho}")
    achados = sorted({
        arquivo for arquivo in _arquivos_do_git(raiz, executar)
        if posixpath.basename(arquivo) == normal and (raiz / arquivo).is_file()
    })
    if not achados:
        raise RegistroRecusado(f"--em não existe: {caminho}")
    if len(achados) > 1:
        raise RegistroRecusado(f"--em ambíguo: {caminho}; use o caminho", tuple(achados))
    return achados[0]


def _arquivos_do_git(raiz: Path, executar) -> list[str]:
    """Os caminhos, relativos à raiz, que o git lista: os do índice e os novos que ele não ignora. O `-z` separa por
    NUL e não escapa o nome com espaço ou acento. Falha do git, ou git que não responde, lança RegistroRecusado."""
    comando = ["git", "-C", str(raiz), "ls-files", "-z", "--cached", "--others", "--exclude-standard"]
    try:
        feito = executar(comando, capture_output=True, timeout=_TEMPO_LIMITE_GIT)
    except (OSError, subprocess.SubprocessError) as erro:
        raise RegistroRecusado(f"git ls-files não respondeu: {type(erro).__name__}") from None
    if feito.returncode != 0:
        raise RegistroRecusado(comum.motivo_do_git(feito, "ls-files"))
    return [item for item in feito.stdout.decode("utf-8", errors="replace").split("\0") if item]


def _inserir_depois(linhas: list[str], indice: int, novas: list[str]) -> int:
    """Põe as linhas novas, sem quebra, depois de `linhas[indice]` e devolve o número, contado de 1, da última delas.
    Cada uma leva o `\\r` de `linhas[indice]`. Se `linhas[indice]` é a última do arquivo, sem quebra final, ela ganha
    a quebra do arquivo (`\\r\\n` quando a primeira linha termina em `\\r`), e a última linha nova fica sem quebra."""
    if indice == len(linhas) - 1:
        quebra = _quebra(linhas[0])
        linhas[indice] += quebra
        com_quebra = [f"{nova}{quebra}" for nova in novas[:-1]] + novas[-1:]
    else:
        quebra = _quebra(linhas[indice])
        com_quebra = [f"{nova}{quebra}" for nova in novas]
    linhas[indice + 1:indice + 1] = com_quebra
    return indice + 1 + len(novas)


def _acrescentar_na_secao(linhas: list[str], secao: tuple[int, int], nova: str) -> int:
    """Põe `nova` depois da última linha não vazia da seção, com a quebra do arquivo, e devolve o número da linha
    nova. A seção sem nenhuma linha ganha uma em branco antes."""
    inicio, fim = secao
    ultima = max(i for i in range(inicio, fim) if linhas[i].strip())
    return _inserir_depois(linhas, ultima, ["", nova] if ultima == inicio else [nova])


SECAO_APROVACOES = "Aprovações"
SECAO_DESCARTADAS = "Abordagens descartadas"
SECAO_TRECHOS = "Trechos do rascunho"


def _secao_que_comeca(linhas: list[str], marca: str) -> tuple[int, int] | None:
    """O índice do primeiro título que começa por `## <marca>` e o do fim da seção (o próximo título de nível 1 ou
    2, ou o fim do arquivo); None sem a seção."""
    inicio = next((i for i, linha in enumerate(linhas) if linha.startswith(f"## {marca}")), None)
    if inicio is None:
        return None
    fim = next((i for i in range(inicio + 1, len(linhas)) if _RE_TITULO_ATE_2.match(linhas[i])), len(linhas))
    return inicio, fim


def _sem_secao(relativo: str, marca: str) -> RegistroRecusado:
    return RegistroRecusado(f"{relativo} sem a seção {marca} (um título ## que começa por {marca})")


def _na_secao(raiz: Path, perfil: Perfil, marca: str, rotulo: str, texto: str, hoje: str | None) -> int:
    """Acrescenta `- <hoje> <texto>` como última linha da seção `marca` do arquivo de decisões e devolve o número da
    linha nova. Recusa lança RegistroRecusado sem gravar."""
    texto = _texto(rotulo, texto)
    hoje = hoje or datetime.date.today().isoformat()
    relativo = perfil.caminhos.decisoes
    linhas = _ler(raiz, relativo).split("\n")
    secao = _secao_que_comeca(linhas, marca)
    if secao is None:
        raise _sem_secao(relativo, marca)
    numero_da_linha = _acrescentar_na_secao(linhas, secao, f"- {hoje} {texto}")
    comum.escrever_texto(raiz / relativo, "\n".join(linhas))
    return numero_da_linha


def aprovacao(raiz: Path, perfil: Perfil, texto: str, hoje: str | None = None) -> int:
    """Acrescenta `- <hoje> <texto>` à seção de aprovações do arquivo de decisões e devolve o número da linha nova."""
    return _na_secao(raiz, perfil, SECAO_APROVACOES, "aprovação", texto, hoje)


def descartada(raiz: Path, perfil: Perfil, texto: str, hoje: str | None = None) -> int:
    """Acrescenta `- <hoje> <texto>` à seção de abordagens descartadas e devolve o número da linha nova."""
    return _na_secao(raiz, perfil, SECAO_DESCARTADAS, "abordagem", texto, hoje)


def trecho(raiz: Path, perfil: Perfil, texto: str, hoje: str | None = None) -> int:
    """Acrescenta `- <hoje> <texto>` à seção de trechos do rascunho já processados e devolve o número da linha
    nova."""
    return _na_secao(raiz, perfil, SECAO_TRECHOS, "trecho", texto, hoje)


SECAO_MEDICOES = "Medições dos ciclos"
CABECALHO_DE_MEDICOES = ("Medição", "Valor", "Data")


def medicao(raiz: Path, perfil: Perfil, medicao: str, valor: str, hoje: str | None = None) -> int:
    """Acrescenta `| <medição> | <valor> | <hoje> |` depois da última linha da primeira tabela `| Medição | Valor |
    Data |` da seção de medições dos ciclos (o primeiro título `## ` que começa por "Medições dos ciclos") do arquivo
    de atritos e devolve o número da linha nova. Recusa lança RegistroRecusado sem gravar."""
    medicao = _texto("medição", medicao, sem_barra=True)
    valor = _texto("valor", valor, sem_barra=True)
    hoje = hoje or datetime.date.today().isoformat()
    relativo = perfil.caminhos.atritos
    linhas = _ler(raiz, relativo).split("\n")
    secao = _secao_que_comeca(linhas, SECAO_MEDICOES)
    if secao is None:
        raise _sem_secao(relativo, SECAO_MEDICOES)
    inicio, fim = secao
    cabecalho = next((
        i for i in range(inicio + 1, fim - 1)
        if linhas[i].strip().startswith("|") and tuple(backlog.celulas(linhas[i])) == CABECALHO_DE_MEDICOES
        and _RE_SEPARADORA.fullmatch(linhas[i + 1].strip())
    ), None)
    if cabecalho is None:
        raise RegistroRecusado(
            f"{relativo} sem a tabela de medições na seção {SECAO_MEDICOES} "
            f"(| {' | '.join(CABECALHO_DE_MEDICOES)} |)"
        )
    ultima = cabecalho + 1
    while ultima + 1 < fim and linhas[ultima + 1].strip().startswith("|"):
        ultima += 1
    numero_da_linha = _inserir_depois(linhas, ultima, [f"| {medicao} | {valor} | {hoje} |"])
    comum.escrever_texto(raiz / relativo, "\n".join(linhas))
    return numero_da_linha


def relato(
    raiz: Path, perfil: Perfil, texto: str, origem: str, confirmada: bool = False, hoje: str | None = None
) -> tuple[str, int]:
    """Acrescenta `- <hoje> <prefixo>-<NN>: <texto> (<nome do arquivo de origem>) — não confirmada` (ou
    `— confirmada`) como última linha da seção de informação nova do rascunho, criando a seção no fim do arquivo
    quando falta, e devolve o ID e o número da linha nova. Recusa lança RegistroRecusado sem gravar."""
    texto = _texto("relato", texto)
    _no_planejamento(perfil, "--origem", origem)
    hoje = hoje or datetime.date.today().isoformat()
    relativo = perfil.caminhos.rascunho
    conteudo = _ler(raiz, relativo)
    prefixo = perfil.ids.prefixo_relato
    numero = max((int(r.id.rsplit("-", 1)[1]) for r in relatos(conteudo, prefixo)), default=0) + 1
    id_ = f"{prefixo}-{numero:02d}"
    situacao = CONFIRMADA if confirmada else f"não {CONFIRMADA}"
    nova = f"- {hoje} {id_}: {texto} ({posixpath.basename(origem.replace(chr(92), '/'))}) — {situacao}"
    linhas = conteudo.split("\n")
    secao = _secao_dos_relatos(linhas)
    if secao is not None:
        numero_da_linha = _acrescentar_na_secao(linhas, secao, nova)
        comum.escrever_texto(raiz / relativo, "\n".join(linhas))
        return id_, numero_da_linha
    fim_de_linha = "\r\n" if linhas[0].endswith("\r") else "\n"
    if conteudo and not conteudo.endswith("\n"):
        conteudo += fim_de_linha
    comum.escrever_texto(
        raiz / relativo, f"{conteudo}{fim_de_linha}{TITULO_DOS_RELATOS}{fim_de_linha}{fim_de_linha}{nova}{fim_de_linha}"
    )
    return id_, conteudo.count("\n") + 4


def status_do_relato(
    raiz: Path,
    perfil: Perfil,
    id_: str,
    status: str,
    em: str | None = None,
    motivo: str | None = None,
    hoje: str | None = None,
    executar=subprocess.run,
) -> int:
    """Acrescenta `- <hoje> <ID>: confirmada`, `... incorporada em <nome do documento>` ou `... descartada:
    <motivo>` como última linha da seção de informação nova e devolve o número da linha nova. O `em` da
    incorporação passa pelo `_no_repositorio`, que usa o `executar` para o git. Recusa lança RegistroRecusado sem
    gravar."""
    hoje = hoje or datetime.date.today().isoformat()
    relativo = perfil.caminhos.rascunho
    conteudo = _ler(raiz, relativo)
    achado = next((r for r in relatos(conteudo, perfil.ids.prefixo_relato) if r.id == id_), None)
    if achado is None:
        raise RegistroRecusado(f"{id_} não existe em {relativo}")
    if achado.descartada:
        raise RegistroRecusado(f"{id_} foi descartada; registre um relato novo")
    if status == CONFIRMADA:
        if achado.confirmada:
            raise RegistroRecusado(f"{id_} já está confirmada")
        situacao = CONFIRMADA
    elif status == INCORPORADA:
        if em is None:
            raise RegistroRecusado("incorporada pede --em <documento>")
        normal = _no_repositorio(raiz, em, executar)
        nome = posixpath.basename(normal)
        if nome in achado.incorporada_em:
            raise RegistroRecusado(f"{id_} já foi incorporada em {nome}")
        situacao = f"{INCORPORADA} em {nome}"
    elif status == DESCARTADA:
        if motivo is None:
            raise RegistroRecusado("descartada pede --motivo")
        situacao = f"{DESCARTADA}: {_texto('--motivo', motivo)}"
    else:
        raise RegistroRecusado(f"status desconhecido: {status}")
    linhas = conteudo.split("\n")
    numero_da_linha = _acrescentar_na_secao(linhas, _secao_dos_relatos(linhas), f"- {hoje} {id_}: {situacao}")
    comum.escrever_texto(raiz / relativo, "\n".join(linhas))
    return numero_da_linha
