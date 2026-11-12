"""Backlog do planejamento: IDs e contagem das pendências (spec 5.2 e 6.4), pendências e artefatos do gate (spec 2a, §6.1).

O prefixo das pendências vem do perfil do projeto; o formato das duas tabelas é do núcleo.
"""
from __future__ import annotations

import re
from pathlib import Path

import comum
from perfil import Perfil

AJUDA = """\
Confere os IDs das pendências do backlog.md (`caminhos.backlog`) e conta as abertas e as causas, resolve uma
pendência ou troca o destino dela.

`backlog ids` sai com 0 e `OK: <total> pendências, <abertas> abertas`. Com erro, sai com 1 e um por linha: primeiro
`ID fora do formato <prefixo>-NN em L<n>`, pela linha; depois `ID duplicado: <prefixo>-NN (L<n> e L<m>)` e
`buraco na sequência: faltam <prefixo>-NN a <prefixo>-NN` (ou `falta <prefixo>-NN`), pelo número. O ID tem dois ou
mais algarismos, de 01 ao maior, e `<prefixo>-001` é o mesmo que `<prefixo>-01`; a ordem das linhas não importa.
Backlog ausente ou ilegível: `backlog.md ilegível: <motivo>`, com 1.

`backlog causas` conta as pendências pela causa que o `registrar pendencia` grava no fim da Origem, com `causa:
<causa>` depois da data. Sai com 0 e uma linha `<causa>: <total> (<abertas> abertas)` por causa presente, na ordem das
causas, depois `sem causa` quando houver, e `Total: <total> pendências, <abertas> abertas`. As recusas são as do
`backlog ids`: backlog ausente ou ilegível e IDs com erro, com 1.

`backlog resolver <prefixo>-NN --em <documento> "<como>"` troca só a célula de status da pendência aberta por
`resolvida em <nome do arquivo do documento>, <AAAA-MM-DD>: <como>`, com `; histórico: <status antigo>` no fim
quando o status era `aberta; <nota>`, e imprime `<prefixo>-NN resolvida em <arquivo>:<linha>`, com o ID como está
no backlog. O ID casa pelo número: `<prefixo>-3` acha a `<prefixo>-03`. Recusa sai com 1 e `recusado: <motivo>`, sem gravar: o `como` vazio,
com quebra de linha ou com `|`; o `--em` fora do repositório, que não existe ou ambíguo, com os candidatos abaixo, um
por linha; os IDs com erro, que vêm abaixo como no `backlog ids`; `<prefixo>-NN não está no backlog`;
`<prefixo>-NN não está aberta: <status>`.

`backlog destino <prefixo>-NN "<destino>"` troca só a célula de destino da pendência aberta e acrescenta
`; <AAAA-MM-DD>: destino era <destino antigo>` ao fim do status, para a pendência seguir ao que resta quando parte
dela se resolveu. Imprime `<prefixo>-NN com destino <destino> em <backlog>:<linha>`. O ID casa pelo número. Recusa sai
com 1 e `recusado: <motivo>`, sem gravar: o `destino` vazio, com quebra de linha ou com `|`; o destino novo que perde o
marcador de um gate (`gates.<gate>.marcador_pendencia`) que o antigo tinha, sem distinção de maiúsculas, com
`o destino novo perde "<marcador>", que segura o <gate>`; o destino igual ao atual, com `destino: igual ao atual`; os
IDs com erro, abaixo como no `backlog ids`; `<prefixo>-NN não está no backlog`; `<prefixo>-NN não está aberta:
<status>`; `<prefixo>-NN não tem a célula de destino`.

O `--em` é o caminho a partir da raiz, como `CLAUDE.md` ou `<pasta do planejamento>/<fase>/<documento>.md`, ou só o
nome do arquivo, quando ele é único entre os arquivos que o git não ignora, com commit ou sem.

Formato: duas tabelas lidas por script; o resto do arquivo é livre. O prefixo é o `ids.prefixo_pendencia`.

```text
| ID | Pendência | Origem | Destino | Status |
|---|---|---|---|---|
| <prefixo>-01 | <pendência> | <documento>, <AAAA-MM-DD>, causa: <causa> | <documento ou fase> | aberta |
| <prefixo>-02 | <pendência> | <documento>, <AAAA-MM-DD> | <destino> | resolvida em <documento>, <AAAA-MM-DD>: <como> |

| Caminho | Camada | Status | Data |
|---|---|---|---|
| <pasta do planejamento>/<fase>/<documento>.md | <número da fase> | rascunho | <AAAA-MM-DD> |
```

- A linha de pendência começa exatamente por `| <prefixo>-`; o ID é a primeira célula, o destino a penúltima e o
  status a última. Status que começa por `aberta` conta como aberta; a linha resolvida fica no arquivo.
- A causa é opcional: a linha sem ela segue válida e conta como `sem causa`. Uma causa fora da lista também conta
  como `sem causa`. Os termos do `rastreio` e do `dossie` não casam pela causa.
- A pendência aberta com o marcador do gate (`gates.<gate>.marcador_pendencia`) no destino, sem distinção de
  maiúsculas, bloqueia o gate.
- A tabela de artefatos vai do cabeçalho exato até a primeira linha que não começa por `|`; crases em volta do
  caminho valem. O status é `rascunho`, `em-revisao` ou `aprovado`; o `harness.py passo` grava os dois últimos.
"""

PREFIXO_ABERTA = "aberta"
CAUSAS = (
    "entrevista", "pesquisa", "pesquisa-sem-fonte", "revisor", "ruling", "cascata", "gerar-modulos", "camada-3", "gate",
    "leitor-frio", "harness", "triagem", "prototipo", "pedido", "codigo", "outro",
)
_ROTULOS_DAS_CAUSAS = "|".join(re.escape(rotulo) for rotulo in CAUSAS)
_CAUSA_NO_FIM = re.compile(r"(\d{4}-\d{2}-\d{2}), causa: (" + _ROTULOS_DAS_CAUSAS + r")\s*$")
_CAUSA_DEPOIS_DA_DATA = re.compile(r"(\d{4}-\d{2}-\d{2}), causa: (?:" + _ROTULOS_DAS_CAUSAS + r")(?=\s*\|)")
SEM_CAUSA = "sem causa"
CABECALHO_ARTEFATOS = ("Caminho", "Camada", "Status", "Data")


class SemTabelaDeArtefatos(Exception):
    """O backlog não tem a tabela de artefatos. `mensagem` diz isso."""

    def __init__(self):
        mensagem = "backlog sem a tabela de artefatos (| Caminho | Camada | Status | Data |)"
        super().__init__(mensagem)
        self.mensagem = mensagem


class BacklogIlegivel(Exception):
    """O backlog.md não pôde ser lido: ausente, fora de UTF-8 ou com erro do sistema. `mensagem` diz o motivo."""

    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


def ler(caminho: Path) -> str:
    """Lê o backlog em UTF-8, sem converter quebras de linha. Falha de leitura vira BacklogIlegivel."""
    try:
        return comum.ler_texto(caminho)
    except FileNotFoundError:
        raise BacklogIlegivel(f"arquivo ausente: {caminho}") from None
    except UnicodeDecodeError:
        raise BacklogIlegivel(f"arquivo não está em UTF-8: {caminho}") from None
    except OSError as erro:
        raise BacklogIlegivel(f"arquivo ilegível: {caminho} ({erro.strerror or type(erro).__name__})") from None


def celulas(linha: str) -> list[str]:
    """Células da linha de tabela, sem as barras das pontas e sem espaços nas bordas de cada uma."""
    miolo = linha.strip()
    if miolo.startswith("|"):
        miolo = miolo[1:]
    if miolo.endswith("|"):
        miolo = miolo[:-1]
    return [celula.strip() for celula in miolo.split("|")]


def _pendencias(texto: str, perfil: Perfil) -> list[tuple[int, list[str]]]:
    """(número da linha a partir de 1, células) de cada linha que começa com `| <prefixo>-`."""
    inicio = f"| {perfil.ids.prefixo_pendencia}-"
    achadas = []
    for numero, linha in enumerate(texto.split("\n"), start=1):
        linha = linha.rstrip("\r")
        if linha.startswith(inicio):
            achadas.append((numero, celulas(linha)))
    return achadas


def linhas_de_pendencia(texto: str, perfil: Perfil) -> list[tuple[int, str, str]]:
    """Cada linha que começa com `| <prefixo>-`: (número da linha a partir de 1, ID, célula de status).

    O ID é a primeira célula; o status é a última, de modo que uma barra a mais no meio da linha não o desloca.
    Linha só com o ID tem status vazio.
    """
    return [
        (numero, celulas[0], celulas[-1] if len(celulas) > 1 else "")
        for numero, celulas in _pendencias(texto, perfil)
    ]


def _formatar_id(prefixo: str, numero: int) -> str:
    return f"{prefixo}-{numero:02d}"


def _juntar_linhas(numeros: list[int]) -> str:
    """`L12`, `L12 e L15` ou `L12, L15 e L18`."""
    return comum.juntar(f"L{numero}" for numero in numeros)


def conferir_ids(texto: str, perfil: Perfil) -> list[str]:
    """Erros nos IDs: formato, duplicata e buraco. Lista vazia se está tudo certo.

    O formato é o prefixo do perfil, `-` e dois ou mais algarismos, de 01 em diante. A sequência é por número,
    de 01 até o maior ID, sem falta e sem repetição; `PEND-001` e `PEND-01` são o mesmo número. A ordem das
    linhas no arquivo não importa. Os erros saem na ordem: formato (pela linha), duplicata e buraco (pelo
    número). Um buraco de vários IDs vira uma linha só (`faltam PEND-02 a PEND-04`).
    """
    prefixo = perfil.ids.prefixo_pendencia
    padrao = re.compile(re.escape(prefixo) + r"-([0-9]{2,})")
    erros = []
    linhas_por_numero: dict[int, list[int]] = {}
    for linha, id_, _ in linhas_de_pendencia(texto, perfil):
        achado = padrao.fullmatch(id_)
        numero = int(achado.group(1)) if achado else 0
        if numero < 1:
            erros.append(f"ID fora do formato {prefixo}-NN em L{linha}")
            continue
        linhas_por_numero.setdefault(numero, []).append(linha)

    for numero in sorted(linhas_por_numero):
        linhas = linhas_por_numero[numero]
        if len(linhas) > 1:
            erros.append(f"ID duplicado: {_formatar_id(prefixo, numero)} ({_juntar_linhas(linhas)})")

    anterior = 0
    for numero in sorted(linhas_por_numero):
        primeiro_faltante, ultimo_faltante = anterior + 1, numero - 1
        if primeiro_faltante == ultimo_faltante:
            erros.append(f"buraco na sequência: falta {_formatar_id(prefixo, primeiro_faltante)}")
        elif primeiro_faltante < ultimo_faltante:
            erros.append(
                f"buraco na sequência: faltam {_formatar_id(prefixo, primeiro_faltante)}"
                f" a {_formatar_id(prefixo, ultimo_faltante)}"
            )
        anterior = numero
    return erros


def contar_abertas(texto: str, perfil: Perfil) -> int:
    """Quantas linhas de pendência têm status que começa com `aberta`. Não valida os IDs."""
    return sum(1 for _, _, status in linhas_de_pendencia(texto, perfil) if status.startswith(PREFIXO_ABERTA))


def abertas_com_marcador(texto: str, perfil: Perfil, marcador: str) -> list[tuple[int, str]]:
    """(linha, ID) de cada pendência `aberta` com `marcador` no destino, sem distinção de maiúsculas.

    O destino é a penúltima célula e o status, a última: `| ID | Pendência | Origem | Destino | Status |`.
    """
    procurado = marcador.casefold()
    return [
        (numero, celulas[0])
        for numero, celulas in _pendencias(texto, perfil)
        if len(celulas) > 2 and celulas[-1].startswith(PREFIXO_ABERTA) and procurado in celulas[-2].casefold()
    ]


def causa(linha: str) -> str | None:
    """A causa no fim da célula de Origem, a antepenúltima, de uma linha com 5 células ou mais; None sem ela ou com
    uma causa fora da `CAUSAS`."""
    partes = celulas(linha)
    if len(partes) < 5:
        return None
    achada = _CAUSA_NO_FIM.search(partes[-3])
    return achada.group(2) if achada else None


def sem_causa(linha: str) -> str:
    """A linha sem o `, causa: <causa>` que vem depois da data, para o termo não casar pela causa."""
    return _CAUSA_DEPOIS_DA_DATA.sub(r"\1", linha)


def contar_por_causa(texto: str, perfil: Perfil) -> list[tuple[str, int, int]]:
    """`(causa, total, abertas)` das pendências, na ordem da `CAUSAS` e só das presentes; depois `("sem causa", ...)`
    quando houver linha sem causa ou com causa fora da lista."""
    totais: dict[str, list[int]] = {}
    linhas = texto.split("\n")
    for numero, partes in _pendencias(texto, perfil):
        rotulo = causa(linhas[numero - 1].rstrip("\r")) or SEM_CAUSA
        contagem = totais.setdefault(rotulo, [0, 0])
        contagem[0] += 1
        contagem[1] += partes[-1].startswith(PREFIXO_ABERTA)
    ordem = [rotulo for rotulo in CAUSAS if rotulo in totais] + ([SEM_CAUSA] if SEM_CAUSA in totais else [])
    return [(rotulo, totais[rotulo][0], totais[rotulo][1]) for rotulo in ordem]


def pendencias_abertas(texto: str, perfil: Perfil) -> list[tuple[int, str, str]]:
    """(linha, ID, destino) de cada pendência `aberta`. O destino é a penúltima célula, como em `abertas_com_marcador`;
    linha com menos de 3 células fica de fora."""
    return [
        (numero, celulas[0], celulas[-2])
        for numero, celulas in _pendencias(texto, perfil)
        if len(celulas) > 2 and celulas[-1].startswith(PREFIXO_ABERTA)
    ]


def _artefatos(texto: str, pasta: str) -> list[tuple[int, str, list[str]]]:
    """(linha, caminho sem crases, células) de cada artefato da tabela de artefatos dentro de `pasta`."""
    dentro_da_pasta = pasta.rstrip("/") + "/"
    achados = []
    na_tabela = False
    for numero, linha in enumerate(texto.split("\n"), start=1):
        linha = linha.strip()
        if not na_tabela:
            na_tabela = linha.startswith("|") and tuple(celulas(linha)) == CABECALHO_ARTEFATOS
            continue
        if not linha.startswith("|"):
            break
        da_linha = celulas(linha)
        caminho = da_linha[0].strip("`")
        if caminho.startswith(dentro_da_pasta):
            achados.append((numero, caminho, da_linha))
    return achados


def artefatos_da_pasta(texto: str, pasta: str) -> list[tuple[int, str, str]]:
    """(linha, caminho, status) de cada artefato da tabela `| Caminho | Camada | Status | Data |` dentro de `pasta`.

    A tabela vai do cabeçalho até a primeira linha que não começa com `|`; a linha separadora fica de fora e as
    crases em volta do caminho saem. Sem a tabela, lista vazia.
    """
    return [
        (numero, caminho, da_linha[2] if len(da_linha) > 2 else "")
        for numero, caminho, da_linha in _artefatos(texto, pasta)
    ]


def datas_da_pasta(texto: str, pasta: str) -> dict[str, str]:
    """A célula Data de cada artefato da tabela de artefatos dentro de `pasta`, pelo caminho sem crases; a linha sem
    a quarta célula dá texto vazio."""
    return {
        caminho: da_linha[3] if len(da_linha) > 3 else ""
        for _, caminho, da_linha in _artefatos(texto, pasta)
    }


def gravar_artefato(texto: str, caminho: str, camada: str, status: str, data: str) -> str:
    """Texto do backlog com o artefato `caminho` em `status` e `data` na tabela de artefatos.

    A primeira linha cujo caminho, sem crases, é `caminho` mantém as duas primeiras células e o `\\r` do fim;
    sem linha, uma nova `| <caminho> | <camada> | <status> | <data> |` entra logo depois da última linha da
    tabela, com a quebra de linha dela. Sem a tabela, lança SemTabelaDeArtefatos.
    """
    linhas = texto.split("\n")
    cabecalho = next(
        (i for i, linha in enumerate(linhas)
         if linha.strip().startswith("|") and tuple(celulas(linha)) == CABECALHO_ARTEFATOS),
        None,
    )
    if cabecalho is None:
        raise SemTabelaDeArtefatos()
    ultima = cabecalho
    while ultima + 1 < len(linhas) and linhas[ultima + 1].strip().startswith("|"):
        ultima += 1
        da_linha = celulas(linhas[ultima])
        if da_linha[0].strip("`") == caminho:
            quebra = "\r" if linhas[ultima].endswith("\r") else ""
            segunda = da_linha[1] if len(da_linha) > 1 else camada
            linhas[ultima] = f"| {da_linha[0]} | {segunda} | {status} | {data} |{quebra}"
            return "\n".join(linhas)
    quebra = "\r" if linhas[ultima].endswith("\r") else ""
    linhas.insert(ultima + 1, f"| {caminho} | {camada} | {status} | {data} |{quebra}")
    return "\n".join(linhas)
