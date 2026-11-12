"""Leitura, validação e formatação do STATUS.md (formato fixo, spec 5.1) e bloco do hook SessionStart (spec 6.1).

Os gates, as fases e a pasta do planejamento vêm do perfil do projeto (spec 2a, §5.4).
"""
from __future__ import annotations

import datetime
import hashlib
import re
import subprocess
from pathlib import Path

import backlog
import comum
import estudos
from perfil import Perfil

ARQUIVO_DA_GRAVACAO = "harness-status"

AJUDA = """\
Valida e imprime o STATUS.md, o estado curto do planejamento (`caminhos.status`), e muda um campo dele por vez.

Sem ação, imprime o arquivo em texto canônico e sai com 0; espaço no fim da linha, linha em branco e quebra de linha
do Windows passam. Arquivo inválido sai com 1 e `STATUS.md inválido: <erro>; <erro>`. O formato é o título fixo e um
campo por linha, nesta ordem, em até 2.000 caracteres; os gates do perfil ficam numa linha só, na ordem das fases, e o
`Pacote` e o `Lote`, opcionais, vêm logo depois do `Documento`, nessa ordem. Um projeto novo começa assim:

```text
# Status do planejamento
Fase: <fase>
Documento: nenhum
Passo: 0
Rodada: 0
Proximo: <o que vem a seguir, numa linha>
<gate>: pendente | <gate>: —
Versao-aprovacao: —
Atualizado: <AAAA-MM-DD>
```

`estado set <campo> <valor>` valida, grava de forma atômica, atualiza o `Atualizado` e imprime `<campo> = <valor>`,
com cada mudança automática numa linha a mais. Recusa sai com 1 e `recusado: <motivo>`, sem tocar o arquivo.

| Campo | Valor aceito |
|---|---|
| `Fase` | o `id` de uma fase do perfil |
| `Documento` | `nenhum`, ou um `.md` dentro da pasta do planejamento, com caminho normalizado e sem espaço |
| `Pacote` | de 2 a 6 caminhos como o do `Documento`, separados por um espaço, sem repetição; `—` tira a linha |
| `Lote` | `<prefixo de pendência>-NN (<N> documentos)` ou `migração v<de>→v<para> (<N> documentos)`, com `(1 documento)` no singular; só pelo `estado lote`, pelo `migrar` e pelo `fechar` |
| `Passo` | inteiro de 0 a 7 |
| `Rodada` | inteiro maior ou igual a 0 |
| `Proximo` | uma linha, até 200 caracteres |
| `<gate>` | `pendente`, `—` ou `aprovado em AAAA-MM-DD` |
| `Versao-aprovacao` | `—` ou `sha256:` e 12 hexadecimais; só pelo `versao`, pelo `passo 6` e pelo `fechar` |
| `Atualizado` | automático; o `set` recusa |

- A `Fase` não pula fase nem avança sem o gate atual `aprovado em ...`; voltar é aceito. O gate `—` da fase nova
  vira `pendente` na mesma gravação.
- `Documento` de fase posterior à `Fase` é recusado, com o pedido de aprovar o gate ou de avançar a `Fase`. Trocar o
  `Documento` ou o `Pacote` com versão marcada é recusado até `versao limpar`.
- O `Pacote` grava também o `Documento`, o primeiro da lista, e a trava de fase vale para cada documento dele.
  `Documento nenhum` tira o `Pacote`; outro `Documento` com pacote aberto é recusado.
- A lista dos documentos do `Lote` fica fora do STATUS.md, no arquivo `lote` da pasta da aprovação
  (`.claude/harness/aprovacao/lote`), um caminho por linha, e o `Documento` é o primeiro dela. O `Lote` e o `Pacote`
  não se abrem juntos. `Documento nenhum` tira também o `Lote` e deixa o arquivo, que sem o campo ninguém lê.
- O `set` do `Lote` é recusado com `recusado: Lote muda só por estado lote, migrar ou fechar`.
- `estado lote <prefixo>-NN <caminho>...` abre o lote da pendência aberta: confere que o destino dela cita cada
  caminho pelo nome do arquivo, sem os trechos `antes do`, e recusa, de uma vez, os que ele não cita, com
  `<caminho> não está no destino da <ID>`, e os que não estão aprovados na tabela de artefatos, com `<caminho> não
  está aprovado; o lote só revisa aprovados`, uma linha `recusado:` cada. Os caminhos entram em ordem de camada e, na
  camada, na ordem do destino, qualquer que seja a ordem passada; o que o destino não cita não entra. Grava a lista, o
  `Lote` e o `Documento` (o primeiro) e imprime o `Lote`, o `Documento` e um caminho por linha. `estado lote --tirar
  <caminho>` tira um documento do lote aberto, e o lote seguinte nunca fica vazio.
- O `set` do `Versao-aprovacao` é recusado com
  `recusado: Versao-aprovacao muda só por versao marcar, versao limpar, passo 6 ou fechar`.
- Valor vazio, com espaço no fim ou com quebra de linha é recusado; o que começa por `-` vai depois de `--`. Valor
  inválido noutro campo não impede a mudança, e os inválidos se corrigem um `set` por vez.
- Estrutura quebrada (título, campo ausente, repetido ou fora de ordem, linha dos gates) é recusada com
  `corrija à mão`: quem corrige é uma pessoa, porque o modelo não edita o arquivo.
- Cada `set` regrava o arquivo inteiro: encadeie vários com `&&`, nunca em chamadas paralelas.
- Cada gravação do STATUS.md pelo harness (`estado set`, `passo`, `versao` e `fechar`) grava também o
  `sha256:<hash>` do texto gravado no arquivo `harness-status` do diretório do git da cópia, que o
  `status-pelo-harness` do pre-commit compara; a falha nessa gravação não muda o resultado do comando.

Com `--hook`, imprime numa linha o JSON do início da sessão e sai sempre com 0; o `source` do payload no stdin diz de
onde a sessão vem. O `systemMessage` é o aviso ao usuário, no formato do molde "Linha do início da sessão" do
`nucleo/comum/saida.md`, e não sai depois de compactar. O `additionalContext` é o contexto do modelo, em até
2.000 caracteres, com:

1. o STATUS.md em texto canônico; num pacote, a linha do `Documento` ganha `(+<N> no pacote)`, e num lote,
   `(+<N> no lote)`; com a lista do lote ilegível, vem logo depois dele a linha `ERRO na lista do lote: <motivo>`;
2. `Pendências abertas: <n> (<backlog>)`, com `—` quando o backlog falta ou não se lê;
3. `[A CONFIRMAR] no documento atual: <n>`, ou `[A CONFIRMAR] no pacote: <n>` ou `no lote: <n>`, com `—` sem
   documento legível;
4. `Estudos com decisão por registrar: <n> (<pasta>)`, com os ilegíveis, só quando há algum;
5. `Últimos commits:` e as três linhas do `git log --oneline`, ou `Últimos commits: indisponível`;
6. `Próximo: <ação> (<motivo>)`, como no `harness.py proximo`, e `Depois:` com até duas ações da fila;
7. as linhas `FALHA` e `AVISO` do `harness.py ambiente`, só quando há.

Com o STATUS.md inválido, o contexto começa por `ERRO no STATUS.md: <motivo>.` e a correção, o `estado set` ou
`Peça ao usuário para corrigir o arquivo à mão`, seguidos do texto bruto, e o aviso é
`Planejamento: STATUS.md inválido: <motivo>`. Com o item do Python em `FALHA` no `ambiente`, como sem leitor de TOML,
o contexto e o aviso são a linha dele: `FALHA: Python <versão> sem leitor de TOML: pip3 install --user tomli`. Com
perfil inválido ou erro inesperado, o contexto é `ERRO no hook: <motivo>`, e o aviso,
`Planejamento: erro no início da sessão: <motivo>`.
"""

TITULO = "# Status do planejamento"
# Os gates do perfil ficam entre os dois grupos, numa linha só.
CAMPOS_ANTES_DOS_GATES = ("Fase", "Documento", "Passo", "Rodada", "Proximo")
CAMPOS_DEPOIS_DOS_GATES = ("Versao-aprovacao", "Atualizado")
# Campo opcional, logo depois do `Documento`, só enquanto um pacote está aberto (spec 4b, §9.1): sem ele, o STATUS.md
# vale como antes da 4b.
CAMPO_PACOTE = "Pacote"
# O `Lote` vem depois do `Pacote`: os dois não se abrem juntos. A lista dos documentos dele fica fora do STATUS.md, no
# arquivo `ARQUIVO_LOTE` da pasta da aprovação.
CAMPO_LOTE = "Lote"
CAMPOS_OPCIONAIS = (CAMPO_PACOTE, CAMPO_LOTE)
ARQUIVO_LOTE = "lote"
LIMITE_PACOTE = 6
SEM_PACOTE = "—"
SEM_DOCUMENTO = "nenhum"
LIMITE_ARQUIVO = 2000
LIMITE_PROXIMO = 200
LIMITE_HOOK = 2000

_SEPARADOR_GATES = " | "
_LETRAS_DO_FORMATO = "xyzwvutsrqponmlkjihgfedcba"
_RE_LINHA = re.compile(r"([A-Za-z][A-Za-z0-9-]*): (.+)")
_RE_NUMERO = re.compile(r"[0-9]+")
_RE_VERSAO = re.compile(r"sha256:[0-9a-f]{12}")
_RE_CONTAGEM_DO_LOTE = re.compile(r" \(([0-9]+) documentos?\)")
_PREFIXO_DA_MIGRACAO = "migração v"
_TRAVESSAO = "—"
_PREFIXO_A_CONFIRMAR = "[A CONFIRMAR"
_COMANDO_GIT = ["git", "log", "--oneline", "-3"]
_TEMPO_LIMITE_GIT = 5
_COMANDO_CORRECAO = "python3 .claude/harness/harness.py estado set <campo> <valor>"


class EstadoInvalido(Exception):
    """STATUS.md fora do formato. `mensagem` é o primeiro erro; `erros` é a lista completa."""

    def __init__(self, mensagem: str, erros: list[str] | None = None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.erros = list(erros) if erros else [mensagem]


def campos(perfil: Perfil) -> tuple[str, ...]:
    """Campos obrigatórios do STATUS.md, na ordem do arquivo, com os gates do perfil na ordem das fases."""
    return CAMPOS_ANTES_DOS_GATES + perfil.nomes_dos_gates + CAMPOS_DEPOIS_DOS_GATES


def ordem(perfil: Perfil) -> tuple[str, ...]:
    """Todos os campos do STATUS.md na ordem do arquivo: os de `campos`, e o `Pacote` e o `Lote` logo depois do
    `Documento`."""
    nomes = campos(perfil)
    depois = nomes.index("Documento") + 1
    return nomes[:depois] + CAMPOS_OPCIONAIS + nomes[depois:]


def caminho_da_lista(raiz: Path) -> Path:
    """O arquivo da lista dos documentos do `Lote`, na pasta da aprovação."""
    return raiz / comum.PASTA_APROVACAO / ARQUIVO_LOTE


def valor_do_lote(origem: str, quantos: int) -> str:
    """O valor do campo `Lote`: `<origem> (<N> documentos)`, com `(1 documento)` no singular."""
    return f"{origem} ({quantos} documento{'' if quantos == 1 else 's'})"


def origem_do_lote(valor: str) -> str:
    """O valor do campo `Lote` sem o ` (<N> documentos)`."""
    return _RE_CONTAGEM_DO_LOTE.sub("", valor, count=1)


def _contagem_do_lote(valor: str) -> int:
    encontrada = _RE_CONTAGEM_DO_LOTE.search(valor)
    return int(encontrada.group(1)) if encontrada else 0


def _lista_do_lote(dados: dict[str, str], raiz: Path) -> list[str]:
    """Os caminhos do arquivo da lista do lote, conferidos contra a contagem do campo `Lote`. Lança EstadoInvalido com a
    lista ilegível, com uma linha que não é um `.md` normalizado e sem espaço, ou com outra contagem."""
    relativo = f"{comum.PASTA_APROVACAO}/{ARQUIVO_LOTE}"
    try:
        texto = comum.ler_texto(raiz / relativo)
    except UnicodeDecodeError:
        raise EstadoInvalido(f"lista do lote ilegível: {relativo} (fora de UTF-8)") from None
    except OSError as erro:
        raise EstadoInvalido(f"lista do lote ilegível: {relativo} ({_motivo_do_sistema(erro)})") from None
    linhas = texto.split("\n")
    if linhas[-1] == "":
        linhas.pop()
    for linha in linhas:
        if not (re.fullmatch(r"[^\s]+\.md", linha) and comum.caminho_normalizado(linha)):
            raise EstadoInvalido(f'documento inválido na lista do lote: "{linha}"')
    quantos = _contagem_do_lote(dados[CAMPO_LOTE])
    if len(linhas) != quantos:
        raise EstadoInvalido(f"o Lote diz {quantos} documentos, e a lista do lote tem {len(linhas)}")
    return linhas


def documentos(dados: dict[str, str], raiz: Path) -> list[str]:
    """Os documentos em refino (spec 4b, §9.1): os do `Lote`, lidos da lista dele sob a `raiz`, se houver; os do
    `Pacote`; senão o `Documento`, se não for `nenhum`; senão, nenhum. Quem trava ou confere pelo documento em refino
    usa esta função. Lança EstadoInvalido com a lista do lote ilegível, com linha inválida ou com outra contagem."""
    if dados.get(CAMPO_LOTE, SEM_PACOTE) != SEM_PACOTE:
        return _lista_do_lote(dados, raiz)
    pacote = dados.get(CAMPO_PACOTE, SEM_PACOTE)
    if pacote != SEM_PACOTE:
        return pacote.split(" ")
    documento = dados.get("Documento", SEM_DOCUMENTO)
    return [] if documento == SEM_DOCUMENTO else [documento]


def _formato_dos_gates(gates: tuple[str, ...]) -> str:
    """Exemplo da linha dos gates: `G1: x | G2: y | G3: z`."""
    return _SEPARADOR_GATES.join(f"{gate}: {letra}" for gate, letra in zip(gates, _LETRAS_DO_FORMATO))


def _data_valida(valor: str) -> bool:
    return comum.data_valida(valor)


def _motivo_do_pacote(valor: str, perfil: Perfil) -> str | None:
    """De 2 a LIMITE_PACOTE documentos separados por um espaço, sem repetição, cada um como o `Documento` pede."""
    itens = valor.split(" ")
    if not 2 <= len(itens) <= LIMITE_PACOTE:
        return f"esperado de 2 a {LIMITE_PACOTE} documentos separados por um espaço, encontrado {len(itens)}"
    invalido = next((item for item in itens if item == SEM_DOCUMENTO or validar_valor("Documento", item, perfil)), None)
    if invalido is not None:
        return f'documento inválido no pacote: "{invalido}"'
    repetido = next((item for posicao, item in enumerate(itens) if item in itens[:posicao]), None)
    if repetido is not None:
        return f"documento repetido no pacote: {repetido}"
    return None


def _motivo_do_lote(valor: str, perfil: Perfil) -> str | None:
    """`<prefixo de pendência>-NN (<N> documentos)` ou `migração v<de>→v<para> (<N> documentos)`, com N maior que 0 e
    o singular só em 1."""
    pendencia = re.escape(perfil.ids.prefixo_pendencia) + r"-[0-9]+"
    migracao = r"migração v[0-9]+\.[0-9]+\.[0-9]+→v[0-9]+\.[0-9]+\.[0-9]+"
    encontrada = re.fullmatch(f"(?:{pendencia}|{migracao})" + r" \(([0-9]+) documentos?\)", valor)
    if encontrada:
        quantos = int(encontrada.group(1))
        if quantos > 0 and valor.endswith("documento)") == (quantos == 1):
            return None
    return (f'esperado "{perfil.ids.prefixo_pendencia}-NN (<N> documentos)" ou '
            f'"migração v<de>→v<para> (<N> documentos)", encontrado "{valor}"')


def validar_valor(campo: str, valor: str, perfil: Perfil) -> str | None:
    """Motivo pelo qual `valor` não serve para `campo`, ou None se serve."""
    if campo == "Fase":
        if valor not in perfil.ids_das_fases:
            return f'esperado {comum.juntar(perfil.ids_das_fases, "ou")}, encontrado "{valor}"'
    elif campo == "Documento":
        pasta = perfil.caminhos.planejamento.rstrip("/")
        if valor != "nenhum" and not (
            re.fullmatch(re.escape(pasta) + r"/[^\s]+\.md", valor) and comum.caminho_normalizado(valor)
        ):
            return f'esperado "nenhum" ou {pasta}/<caminho>.md normalizado e sem espaços, encontrado "{valor}"'
    elif campo == CAMPO_PACOTE:
        return _motivo_do_pacote(valor, perfil)
    elif campo == CAMPO_LOTE:
        return _motivo_do_lote(valor, perfil)
    elif campo == "Passo":
        if not _RE_NUMERO.fullmatch(valor):
            return f'esperado inteiro de 0 a 7, encontrado "{valor}"'
        if int(valor) > 7:
            return f"{valor} fora do intervalo de 0 a 7"
    elif campo == "Rodada":
        if not _RE_NUMERO.fullmatch(valor):
            return f'esperado inteiro maior ou igual a 0, encontrado "{valor}"'
    elif campo == "Proximo":
        if "\n" in valor or "\r" in valor:
            return "deve ter uma só linha"
        if len(valor) > LIMITE_PROXIMO:
            return f"{len(valor)} caracteres, limite {LIMITE_PROXIMO}"
    elif campo in perfil.nomes_dos_gates:
        if valor == "pendente" or valor == _TRAVESSAO:
            return None
        if valor.startswith("aprovado em ") and _data_valida(valor[len("aprovado em "):]):
            return None
        return f'esperado "pendente", "{_TRAVESSAO}" ou "aprovado em AAAA-MM-DD", encontrado "{valor}"'
    elif campo == "Versao-aprovacao":
        if valor != _TRAVESSAO and not _RE_VERSAO.fullmatch(valor):
            return f'esperado "{_TRAVESSAO}" ou "sha256:" com 12 hexadecimais minúsculos, encontrado "{valor}"'
    elif campo == "Atualizado":
        if not _data_valida(valor):
            return f'esperado data AAAA-MM-DD, encontrado "{valor}"'
    else:
        return "campo desconhecido"
    return None


class _LinhaInvalida(Exception):
    """Linha do corpo fora do formato; a mensagem diz qual regra quebrou."""


def _separar_campos(linha: str, gates: tuple[str, ...]) -> list[tuple[str, str]]:
    """Lê uma linha `Campo: valor`. Só a linha dos gates traz mais de um campo.

    Na linha dos gates com mais de um campo, os nomes são exatamente os `gates`, nessa ordem.
    Uma linha com um gate só passa por aqui e cai depois no erro de gates em linhas separadas.
    Lança _LinhaInvalida se a linha está fora do formato.
    """
    encontrada = _RE_LINHA.fullmatch(linha)
    if not encontrada:
        raise _LinhaInvalida(f'linha fora do formato "Campo: valor": {_resumo(linha)}')
    if encontrada.group(1) not in gates:
        return [(encontrada.group(1), encontrada.group(2))]
    partes = [_RE_LINHA.fullmatch(trecho) for trecho in linha.split(_SEPARADOR_GATES)]
    pares = [(p.group(1), p.group(2)) for p in partes if p]
    if len(pares) != len(partes) or (len(pares) > 1 and tuple(nome for nome, _ in pares) != gates):
        raise _LinhaInvalida(
            f'linha dos gates fora do formato "{_formato_dos_gates(gates)}": {_resumo(linha)}'
        )
    return pares


def _resumo(linha: str) -> str:
    return linha if len(linha) <= 60 else linha[:57] + "..."


def _erro_de_tamanho(texto: str) -> str | None:
    if len(texto) > LIMITE_ARQUIVO:
        return f"arquivo com {len(texto)} caracteres, limite {LIMITE_ARQUIVO}"
    return None


def _examinar(texto: str, perfil: Perfil) -> tuple[dict[str, str], list[str], list[str]]:
    """Análise que não para nos valores inválidos. Devolve (valores, erros_de_estrutura, erros_de_valor).

    Estrutura: título, formato das linhas, campos ausentes, desconhecidos ou repetidos, ordem e linha dos
    gates. Valor: o que `validar_valor` recusa. O limite de tamanho fica em `_erro_de_tamanho`.
    Linhas em branco, espaços finais e `\\r` são ignorados. `valores` traz o que foi lido, mesmo inválido.
    """
    nomes = campos(perfil)
    todos = ordem(perfil)
    gates = perfil.nomes_dos_gates
    estrutura: list[str] = []
    linhas = [(n, bruta.rstrip()) for n, bruta in enumerate(texto.split("\n"), start=1)]
    linhas = [(n, linha) for n, linha in linhas if linha]

    if not linhas or linhas[0][1] != TITULO:
        estrutura.append(f'título inválido: esperado "{TITULO}"')
    corpo = linhas[1:]

    valores: dict[str, str] = {}
    posicao_na_linha: dict[str, int] = {}
    ordem_no_arquivo: list[str] = []
    for numero, linha in corpo:
        try:
            pares = _separar_campos(linha, gates)
        except _LinhaInvalida as erro:
            estrutura.append(str(erro))
            continue
        for campo, valor in pares:
            if campo not in todos:
                estrutura.append(f"campo desconhecido: {campo}")
            elif campo in valores:
                estrutura.append(f"campo duplicado: {campo}")
            else:
                valores[campo] = valor
                posicao_na_linha[campo] = numero
                ordem_no_arquivo.append(campo)

    for campo in nomes:
        if campo not in valores:
            estrutura.append(f"campo ausente: {campo}")

    for anterior, atual in zip(ordem_no_arquivo, ordem_no_arquivo[1:]):
        if todos.index(atual) < todos.index(anterior):
            estrutura.append(f"ordem errada: {atual} deveria vir antes de {anterior}")

    linhas_dos_gates = {posicao_na_linha[g] for g in gates if g in posicao_na_linha}
    if len(linhas_dos_gates) > 1:
        estrutura.append(
            f"ordem errada: {comum.juntar(gates)} devem ficar na mesma linha, no formato {_formato_dos_gates(gates)}"
        )

    invalidos: list[str] = []
    for campo in todos:
        if campo in valores:
            motivo = validar_valor(campo, valores[campo], perfil)
            if motivo:
                invalidos.append(f"valor inválido em {campo}: {motivo}")
    pacote = valores.get(CAMPO_PACOTE)
    primeiro = pacote.split(" ")[0] if pacote is not None else None
    if primeiro is not None and _motivo_do_pacote(pacote, perfil) is None and primeiro != valores.get("Documento"):
        invalidos.append(f"valor inválido em {CAMPO_PACOTE}: o primeiro do pacote deve ser o Documento")

    return valores, estrutura, invalidos


def analisar(texto: str, perfil: Perfil) -> dict[str, str]:
    """Lê o texto do STATUS.md e devolve os campos, na ordem de `ordem(perfil)`; o `Pacote`, só se está no arquivo.

    Linhas em branco, espaços finais e `\\r` são ignorados. Lança EstadoInvalido,
    com todos os erros em `.erros` e o primeiro como mensagem.
    """
    valores, estrutura, invalidos = _examinar(texto, perfil)
    erros = estrutura + invalidos
    tamanho = _erro_de_tamanho(texto)
    if tamanho:
        erros.append(tamanho)
    if erros:
        raise EstadoInvalido(erros[0], erros)
    return {campo: valores[campo] for campo in ordem(perfil) if campo in valores}


def validar(texto: str, perfil: Perfil) -> list[str]:
    """Lista de erros do texto; vazia se o STATUS.md é válido."""
    try:
        analisar(texto, perfil)
    except EstadoInvalido as erro:
        return erro.erros
    return []


def formatar(dados: dict[str, str], perfil: Perfil) -> str:
    """Texto canônico do STATUS.md: um campo por linha, gates numa linha, uma quebra de linha no fim."""
    nomes = campos(perfil)
    todos = ordem(perfil)
    gates = perfil.nomes_dos_gates
    erros = [f"campo ausente: {c}" for c in nomes if c not in dados]
    erros += [f"campo desconhecido: {c}" for c in dados if c not in todos]
    if erros:
        raise EstadoInvalido(erros[0], erros)
    linhas = [TITULO]
    for campo in todos:
        if campo == gates[0]:
            linhas.append(_SEPARADOR_GATES.join(f"{g}: {dados[g]}" for g in gates))
        elif campo in CAMPOS_OPCIONAIS:
            if dados.get(campo, SEM_PACOTE) != SEM_PACOTE:
                linhas.append(f"{campo}: {dados[campo]}")
        elif campo not in gates:
            linhas.append(f"{campo}: {dados[campo]}")
    return "\n".join(linhas) + "\n"


def _motivo_do_sistema(erro: OSError) -> str:
    """Motivo do erro do sistema, em português para os casos comuns."""
    return comum.motivo_do_sistema(erro)


def _ler_arquivo(caminho: Path) -> str:
    """Texto do arquivo. Arquivo ausente, fora de UTF-8 ou com erro do sistema vira EstadoInvalido."""
    try:
        return comum.ler_texto(caminho)
    except FileNotFoundError:
        raise EstadoInvalido(f"arquivo ausente: {caminho}") from None
    except UnicodeDecodeError:
        raise EstadoInvalido(f"arquivo não está em UTF-8: {caminho}") from None
    except OSError as erro:
        raise EstadoInvalido(f"arquivo ilegível: {caminho} ({_motivo_do_sistema(erro)})") from None


def ler(caminho: Path, perfil: Perfil) -> dict[str, str]:
    """Lê e analisa o arquivo. Arquivo ausente ou ilegível vira EstadoInvalido."""
    return analisar(_ler_arquivo(caminho), perfil)


def _sem_estrutura(motivo: str) -> str:
    return f"estrutura do STATUS.md inválida ({motivo}); corrija à mão"


def _aprovado(valor: str, gate: str, perfil: Perfil) -> bool:
    """O valor do gate é `aprovado em AAAA-MM-DD` válido."""
    return valor.startswith("aprovado em ") and validar_valor(gate, valor, perfil) is None


def _trava_de_fase(campo: str, valor: str, valores: dict[str, str], perfil: Perfil) -> str | None:
    """Motivo para recusar o `set` pelas travas de fase (spec 2a, §6.2), ou None.

    `Documento` de camada posterior à `Fase` é recusado; de camada anterior ou fora das pastas de fase, aceito.
    `Fase` só avança para a fase seguinte, e só com o gate da fase atual aprovado; voltar é aceito. Com a `Fase`
    atual inválida, nenhuma trava vale: o `set` pode ser justamente a correção.
    """
    atual = perfil.fase_por_id(valores.get("Fase", ""))
    if atual is None:
        return None
    indice_atual = perfil.fases.index(atual)
    if campo == "Documento":
        fase = perfil.fase_do_documento(valor)
        if fase is not None and perfil.fases.index(fase) > indice_atual:
            if _aprovado(valores.get(atual.gate, ""), atual.gate, perfil) and indice_atual + 1 < len(perfil.fases):
                seguinte = perfil.fases[indice_atual + 1].id
                return (f"{valor} é da camada {fase.id}; o {atual.gate} já está aprovado; "
                        f"avance a Fase com estado set Fase {seguinte}")
            return (f"{valor} é da camada {fase.id}; "
                    f"aprove antes o {atual.gate} com /{comum.PREFIXO_DAS_SKILLS}gate-fase {atual.gate}")
    elif campo == "Fase":
        indice_novo = perfil.ids_das_fases.index(valor)
        if indice_novo > indice_atual + 1:
            return f"a Fase não pula camada: depois de {atual.id} vem {perfil.fases[indice_atual + 1].id}"
        if indice_novo == indice_atual + 1 and not _aprovado(valores.get(atual.gate, ""), atual.gate, perfil):
            return (f"{atual.gate} não aprovado; a Fase passa de {atual.id} para {valor} "
                    f"só depois de /{comum.PREFIXO_DAS_SKILLS}gate-fase {atual.gate}")
    return None


def _conferir_valor(campo: str, valor: str, perfil: Perfil) -> None:
    """Campo conhecido e valor que serve, sem olhar o arquivo. Lança EstadoInvalido."""
    if campo == "Atualizado":
        raise EstadoInvalido("Atualizado é automático")
    if campo in CAMPOS_OPCIONAIS and valor == SEM_PACOTE:
        return  # `estado set Pacote —` tira a linha
    motivo = validar_valor(campo, valor, perfil)
    if motivo:
        raise EstadoInvalido(f"valor inválido em {campo}: {motivo}")
    if not valor or valor != valor.rstrip():
        # O arquivo não guardaria o valor como foi pedido: a leitura corta o espaço final.
        raise EstadoInvalido(f"valor inválido em {campo}: vazio ou com espaço no fim")
    try:
        valor.encode("utf-8")
    except UnicodeEncodeError:
        raise EstadoInvalido(f"valor inválido em {campo}: caractere que não pode ser gravado em UTF-8") from None


def _mudancas_do_pacote(
    mudancas: dict[str, str], valores: dict[str, str], lote: list[str] | None = None
) -> dict[str, str]:
    """As mudanças automáticas que o `Pacote` e o `Lote` trazem (spec 4b, §9.1). Lança EstadoInvalido para `Documento`
    diferente do primeiro do pacote ou do lote pedido, para outro `Documento` com um pacote ou um lote aberto e para
    um deles aberto com o outro aberto. `lote` traz os documentos do `Lote` que `mudancas` abre."""
    pacote = mudancas.get(CAMPO_PACOTE)
    documento = mudancas.get("Documento")
    atual = valores.get(CAMPO_PACOTE, SEM_PACOTE)
    lote_atual = valores.get(CAMPO_LOTE, SEM_PACOTE)
    novo_lote = mudancas.get(CAMPO_LOTE)
    if novo_lote is not None and novo_lote != SEM_PACOTE:
        if atual != SEM_PACOTE:
            raise EstadoInvalido("Pacote aberto; feche-o com estado set Documento nenhum antes de abrir um lote")
        if lote_atual.startswith(_PREFIXO_DA_MIGRACAO) and not novo_lote.startswith(_PREFIXO_DA_MIGRACAO):
            raise EstadoInvalido("lote de migração aberto; feche-o antes de abrir outro lote")
        if not lote:
            raise EstadoInvalido("Lote muda só por estado lote, migrar ou fechar")
        if documento is not None and documento != lote[0]:
            raise EstadoInvalido(f"o Documento é o primeiro do Lote: {lote[0]}")
        return {"Documento": lote[0]} if lote[0] != valores.get("Documento") else {}
    if pacote is not None and pacote != SEM_PACOTE:
        if lote_atual != SEM_PACOTE:
            raise EstadoInvalido("Lote aberto; feche-o com estado set Documento nenhum antes de abrir um Pacote")
        primeiro = pacote.split(" ")[0]
        if documento is not None and documento != primeiro:
            raise EstadoInvalido(f"o Documento é o primeiro do Pacote: {primeiro}")
        return {"Documento": primeiro} if primeiro != valores.get("Documento") else {}
    if documento is None or pacote is not None:
        return {}
    if lote_atual != SEM_PACOTE:
        if documento == SEM_DOCUMENTO:
            return {CAMPO_LOTE: SEM_PACOTE}
        if documento != valores.get("Documento"):
            raise EstadoInvalido(
                f"Lote aberto com {_contagem_do_lote(lote_atual)} documentos; mude a lista com estado lote ou feche "
                "com estado set Documento nenhum"
            )
        return {}
    if atual == SEM_PACOTE:
        return {}
    if documento == SEM_DOCUMENTO:
        return {CAMPO_PACOTE: SEM_PACOTE}
    if documento != valores.get("Documento"):
        raise EstadoInvalido(
            f"Pacote aberto com {len(atual.split(' '))} documentos; mude a lista com estado set Pacote ou feche com "
            "estado set Documento nenhum"
        )
    return {}


def preparar(
    caminho: Path, mudancas: dict[str, str], perfil: Perfil, hoje: str | None = None, lote: list[str] | None = None
) -> tuple[str, dict[str, str]]:
    """O texto novo do STATUS.md com as `mudancas` e as mudanças automáticas, sem gravar nada.

    `hoje` é a data em AAAA-MM-DD; sem ele, vale a data local. Lança EstadoInvalido se um campo ou valor não
    serve, ou se o arquivo não tem estrutura legível (título, todos os campos, a ordem, o formato das linhas e a
    linha dos gates). Valor inválido em OUTRO campo não impede a mudança, para um STATUS.md com vários valores
    inválidos se corrigir aos poucos. O texto novo, em formato canônico, não pode ter erro que o texto original não
    tinha. Erro do sistema na leitura também vira EstadoInvalido.

    Mudança automática: com a `Fase` mudando, o gate da fase nova que está `—` no arquivo, e não está nas
    `mudancas`, vira `pendente`.

    Pacote (spec 4b, §9.1): `Pacote` com uma lista grava também o `Documento`, o primeiro da lista (mudança
    automática quando ele muda); `Pacote —` tira a linha; `Documento nenhum` tira também o `Pacote` (mudança
    automática `Pacote = —`); outro `Documento` com um pacote aberto é recusado. Trocar ou tirar o `Pacote` com
    versão marcada é recusado, como trocar o `Documento`. A trava de fase vale para cada documento do pacote.

    Lote: as mesmas regras, simétricas, com `lote` a lista de documentos do `Lote` que `mudancas` abre ou muda (o
    `definir_lote` e o `tirar_do_lote` a passam); `Lote` com valor e sem `lote` é recusado. O `Lote` com `Pacote` aberto
    é recusado, e o inverso também; um lote de pendência sobre um lote de migração, também. Abrir ou mudar o `Lote` com
    versão marcada é recusado até `versao limpar`. A trava de fase vale para cada documento do lote.
    """
    todos = ordem(perfil)
    desconhecido = next((campo for campo in mudancas if campo not in todos), None)
    if desconhecido is not None:
        raise EstadoInvalido(f"campo desconhecido: {desconhecido}")
    for campo in (campo for campo in todos if campo in mudancas):
        _conferir_valor(campo, mudancas[campo], perfil)
    if hoje is None:
        hoje = datetime.date.today().isoformat()
    motivo = validar_valor("Atualizado", hoje, perfil)
    if motivo:
        raise EstadoInvalido(f"valor inválido em Atualizado: {motivo}")

    try:
        texto = _ler_arquivo(caminho)
    except EstadoInvalido as erro:
        raise EstadoInvalido(_sem_estrutura(erro.mensagem)) from None
    valores, estrutura, invalidos = _examinar(texto, perfil)
    if estrutura:
        raise EstadoInvalido(_sem_estrutura(estrutura[0]), estrutura)
    automaticas = _mudancas_do_pacote(mudancas, valores, lote)
    efetivas = {**mudancas, **automaticas}
    marcado = efetivas.get("Versao-aprovacao", valores.get("Versao-aprovacao", ""))
    pacote_atual = valores.get(CAMPO_PACOTE, SEM_PACOTE)
    lote_atual = valores.get(CAMPO_LOTE, SEM_PACOTE)
    if pacote_atual != SEM_PACOTE:
        marcado_para = f"o pacote {pacote_atual}"
    elif lote_atual != SEM_PACOTE:
        marcado_para = f"o lote {lote_atual}"
    else:
        marcado_para = valores.get("Documento")
    if lote is not None and _RE_VERSAO.fullmatch(marcado):
        raise EstadoInvalido(
            f"Versao-aprovacao {marcado} está marcada para {marcado_para}; rode versao limpar antes de trocar o Lote"
        )
    documento = efetivas.get("Documento")
    if documento is not None and documento != valores.get("Documento") and _RE_VERSAO.fullmatch(marcado):
        # O hash marcado vale para o Documento atual; trocar sem limpar deixaria o hash apontando para outro arquivo.
        raise EstadoInvalido(
            f"Versao-aprovacao {marcado} está marcada para {marcado_para}; "
            "rode versao limpar antes de trocar o Documento"
        )
    pacote = efetivas.get(CAMPO_PACOTE)
    if pacote is not None and pacote != pacote_atual and _RE_VERSAO.fullmatch(marcado):
        raise EstadoInvalido(
            f"Versao-aprovacao {marcado} está marcada para {marcado_para}; rode versao limpar antes de trocar o Pacote"
        )
    for campo in (campo for campo in todos if campo in efetivas):
        if campo == CAMPO_LOTE:
            pares = [("Documento", item) for item in lote or []]
        elif campo != CAMPO_PACOTE:
            pares = [(campo, efetivas[campo])]
        elif efetivas[campo] == SEM_PACOTE:
            pares = []
        else:
            pares = [("Documento", item) for item in efetivas[campo].split(" ")]
        for alvo, valor in pares:
            trava = _trava_de_fase(alvo, valor, valores, perfil)
            if trava:
                raise EstadoInvalido(trava)

    fase_nova = perfil.fase_por_id(mudancas.get("Fase", ""))
    if (
        fase_nova is not None
        and fase_nova.id != valores.get("Fase")
        and fase_nova.gate not in mudancas
        and valores.get(fase_nova.gate) == _TRAVESSAO
    ):
        automaticas[fase_nova.gate] = "pendente"

    novos = {**valores, **mudancas, **automaticas, "Atualizado": hoje}
    for opcional in CAMPOS_OPCIONAIS:
        if novos.get(opcional) == SEM_PACOTE:
            del novos[opcional]
    novo_texto = formatar(novos, perfil)
    _, estrutura_nova, invalidos_novos = _examinar(novo_texto, perfil)
    erros_novos = [e for e in estrutura_nova + invalidos_novos if e not in invalidos]
    tamanho = _erro_de_tamanho(novo_texto)
    if tamanho and not _erro_de_tamanho(texto):
        erros_novos.append(tamanho)
    if erros_novos:
        raise EstadoInvalido(erros_novos[0], erros_novos)
    return novo_texto, automaticas


def definir_varios(caminho: Path, mudancas: dict[str, str], perfil: Perfil, hoje: str | None = None) -> dict[str, str]:
    """Grava as `mudancas` no STATUS.md numa escrita só, depois de `preparar`, e devolve as mudanças automáticas.

    Nada é gravado se algum campo for recusado. Erro do sistema na gravação vira EstadoInvalido.
    """
    novo_texto, automaticas = preparar(caminho, mudancas, perfil, hoje)
    try:
        comum.escrever_texto(caminho, novo_texto)
    except OSError as erro:
        raise EstadoInvalido(f"não foi possível gravar: {caminho} ({_motivo_do_sistema(erro)})") from None
    _gravar_hash_do_status(caminho, novo_texto, perfil)
    return automaticas


def _na_ordem(mudancas: dict[str, str], perfil: Perfil) -> dict[str, str]:
    """As mudanças na ordem do arquivo."""
    return {campo: mudancas[campo] for campo in ordem(perfil) if campo in mudancas}


def _gravar_lote(
    caminho: Path, raiz: Path, valor: str, documentos: list[str], extras: dict[str, str], perfil: Perfil,
    hoje: str | None,
) -> dict[str, str]:
    """Grava o `Lote` com os `documentos`: a lista e, numa escrita só, o STATUS.md com o `Lote`, o `Documento` (o
    primeiro) e os `extras`. Tudo o que pode recusar roda antes de gravar; se o STATUS.md falha, a lista volta ao texto
    anterior, ou some, se não havia. Devolve as mudanças automáticas e as dos `extras`, na ordem do arquivo."""
    novo_texto, automaticas = preparar(caminho, {CAMPO_LOTE: valor, **extras}, perfil, hoje, lote=documentos)
    lista = caminho_da_lista(raiz)
    try:
        anterior = lista.read_bytes()
    except FileNotFoundError:
        anterior = None
    except OSError as erro:
        raise EstadoInvalido(f"não foi possível ler: {lista} ({_motivo_do_sistema(erro)})") from None
    try:
        comum.escrever_texto(lista, "".join(f"{documento}\n" for documento in documentos))
    except OSError as erro:
        raise EstadoInvalido(f"não foi possível gravar: {lista} ({_motivo_do_sistema(erro)})") from None
    try:
        comum.escrever_texto(caminho, novo_texto)
    except OSError as erro:
        try:
            if anterior is None:
                lista.unlink()
            else:
                lista.write_bytes(anterior)
        except OSError:
            pass
        raise EstadoInvalido(f"não foi possível gravar: {caminho} ({_motivo_do_sistema(erro)})") from None
    _gravar_hash_do_status(caminho, novo_texto, perfil)
    return _na_ordem({**automaticas, **extras}, perfil)


def definir_lote(
    caminho: Path, raiz: Path, origem: str, documentos: list[str], perfil: Perfil,
    extras: dict[str, str] | None = None, hoje: str | None = None,
) -> dict[str, str]:
    """Abre o `Lote` `<origem> (<N> documentos)` com os `documentos`, na ordem dada: grava a lista no arquivo `lote`
    da pasta da aprovação sob a `raiz` e, numa escrita só, o `Lote`, o `Documento` (o primeiro) e os `extras`.

    Nada é gravado se algo for recusado: documento repetido ou fora do formato do `Documento`, `Pacote` aberto,
    lote de migração aberto, versão marcada, trava de fase de qualquer documento ou campo dos `extras`. Devolve as
    mudanças automáticas e as dos `extras`, na ordem do arquivo; o `Documento`, o primeiro, vem sempre. Erro do
    sistema na gravação vira EstadoInvalido."""
    invalido = next((d for d in documentos if d == SEM_DOCUMENTO or validar_valor("Documento", d, perfil)), None)
    if invalido is not None:
        raise EstadoInvalido(f'documento inválido no lote: "{invalido}"')
    repetido = next((d for posicao, d in enumerate(documentos) if d in documentos[:posicao]), None)
    if repetido is not None:
        raise EstadoInvalido(f"documento repetido no lote: {repetido}")
    mudancas = _gravar_lote(
        caminho, raiz, valor_do_lote(origem, len(documentos)), list(documentos), dict(extras or {}), perfil, hoje
    )
    return _na_ordem({"Documento": documentos[0], **mudancas}, perfil)


def tirar_do_lote(
    caminho: Path, raiz: Path, documento: str, perfil: Perfil, hoje: str | None = None
) -> dict[str, str]:
    """Tira o `documento` do `Lote` aberto: regrava a lista e o campo com um a menos, e o `Documento` vira o primeiro
    que resta. Recusa o documento fora da lista, o último que resta e a versão marcada. Devolve as mudanças."""
    dados = ler(caminho, perfil)
    if CAMPO_LOTE not in dados:
        raise EstadoInvalido("sem lote aberto")
    lista = documentos(dados, raiz)
    if documento not in lista:
        raise EstadoInvalido(f"{documento} não está no lote")
    restantes = [item for item in lista if item != documento]
    if not restantes:
        raise EstadoInvalido("o lote ficaria vazio; feche com estado set Documento nenhum")
    valor = valor_do_lote(origem_do_lote(dados[CAMPO_LOTE]), len(restantes))
    mudancas = _gravar_lote(caminho, raiz, valor, restantes, {}, perfil, hoje)
    return _na_ordem({**mudancas, CAMPO_LOTE: valor}, perfil)


def apagar_lista_do_lote(raiz: Path) -> None:
    """Apaga o arquivo da lista do lote; ausente, não faz nada."""
    try:
        caminho_da_lista(raiz).unlink()
    except FileNotFoundError:
        pass


def hash_do_status(dados: bytes) -> str:
    """`sha256:` mais os 64 hexadecimais do SHA-256 dos bytes, com `\\r\\n` contado como `\\n`, como no `hash_do_molde`."""
    return "sha256:" + hashlib.sha256(dados.replace(b"\r\n", b"\n")).hexdigest()


def _raiz_do_status(caminho: Path, perfil: Perfil) -> Path | None:
    """A raiz da cópia: o caminho do STATUS sem as partes de `perfil.caminhos.status`; None se ele não termina nelas."""
    partes = Path(perfil.caminhos.status).parts
    caminho = Path(caminho)
    if not partes or len(caminho.parts) <= len(partes) or caminho.parts[-len(partes):] != partes:
        return None
    return Path(*caminho.parts[: -len(partes)])


def _gravar_hash_do_status(caminho: Path, texto: str, perfil: Perfil) -> None:
    """Grava o hash do texto em `<diretório do git>/harness-status`, só se a raiz e o diretório existem; o erro do
    sistema não sobe."""
    raiz = _raiz_do_status(caminho, perfil)
    pasta = None if raiz is None else comum.diretorio_do_git(raiz)
    if pasta is None or not pasta.is_dir():
        return
    try:
        comum.escrever_texto(pasta / ARQUIVO_DA_GRAVACAO, hash_do_status(texto.encode("utf-8")) + "\n")
    except OSError:
        pass


def definir(caminho: Path, campo: str, valor: str, perfil: Perfil, hoje: str | None = None) -> dict[str, str]:
    """Muda um campo do STATUS.md, como `definir_varios` com um campo só; devolve as mudanças automáticas."""
    return definir_varios(caminho, {campo: valor}, perfil, hoje)


def limitar_hook(texto: str) -> str:
    """Corta o texto para caber em LIMITE_HOOK caracteres, com o aviso `[cortado em 2000 caracteres]` no fim.

    O aviso entra na conta: o resultado cortado tem exatamente LIMITE_HOOK caracteres. Texto que já cabe volta igual.
    """
    if len(texto) <= LIMITE_HOOK:
        return texto
    aviso = f"\n[cortado em {LIMITE_HOOK} caracteres]"
    return texto[: LIMITE_HOOK - len(aviso)] + aviso


def _documento_legivel(texto: str, perfil: Perfil) -> str | None:
    """Valor de `Documento` num STATUS.md que não passou na validação, se a estrutura é legível e o valor é válido."""
    valores, estrutura, _ = _examinar(texto, perfil)
    documento = valores.get("Documento")
    if estrutura or documento is None or validar_valor("Documento", documento, perfil):
        return None
    return documento


def _linha_de_erro(mensagem: str) -> str:
    """Erro de valor se corrige com `estado set`; estrutura, arquivo ausente, ilegível ou grande demais, só à mão."""
    if mensagem.startswith("valor inválido em "):
        return f"ERRO no STATUS.md: {mensagem}. Corrija com {_COMANDO_CORRECAO}\n"
    return f"ERRO no STATUS.md: {mensagem}. Peça ao usuário para corrigir o arquivo à mão\n"


def _inicio_do_bloco(raiz: Path, caminho: Path, perfil: Perfil) -> tuple[str, list[str], str | None]:
    """Começo do bloco do hook, os documentos em refino e o grupo que eles formam (`pacote`, `lote` ou None). O texto
    termina em quebra de linha.

    STATUS.md válido: o texto canônico; com pacote ou lote, a linha do `Documento` ganha ` (+<N> no pacote)` ou
    ` (+<N> no lote)`. Com `Lote` e a lista dele ilegível ou fora da conta: o texto canônico, a linha
    `ERRO na lista do lote: ...` e só o `Documento` na lista. Inválido ou ausente: a linha `ERRO no STATUS.md: ...` e,
    se o arquivo existe e tem conteúdo, o texto bruto dele; o `Documento` vem da análise tolerante quando ela é
    legível, sem grupo.
    """
    try:
        texto = _ler_arquivo(caminho)
    except EstadoInvalido as erro:
        return _linha_de_erro(erro.mensagem), [], None
    try:
        dados = analisar(texto, perfil)
    except EstadoInvalido as erro:
        bruto = texto.rstrip()
        documento = _documento_legivel(texto, perfil)
        lista = [] if documento in (None, SEM_DOCUMENTO) else [documento]
        return _linha_de_erro(erro.mensagem) + (bruto + "\n" if bruto else ""), lista, None
    canonico = formatar(dados, perfil)
    try:
        lista = documentos(dados, raiz)
    except EstadoInvalido as erro:
        documento = dados["Documento"]
        lista = [] if documento == SEM_DOCUMENTO else [documento]
        return canonico + f"ERRO na lista do lote: {erro.mensagem}\n", lista, None
    grupo = CAMPO_LOTE.lower() if CAMPO_LOTE in dados else CAMPO_PACOTE.lower() if CAMPO_PACOTE in dados else None
    if grupo is None:
        return canonico, lista, None
    linha = f"\nDocumento: {dados['Documento']}\n"
    com_conta = f"\nDocumento: {dados['Documento']} (+{len(lista) - 1} no {grupo})\n"
    return canonico.replace(linha, com_conta, 1), lista, grupo


def _linha_pendencias(raiz: Path, perfil: Perfil) -> str:
    caminho = raiz / perfil.caminhos.backlog
    try:
        abertas = backlog.contar_abertas(backlog.ler(caminho), perfil)
    except backlog.BacklogIlegivel:
        situacao = "ilegível" if caminho.exists() else "ausente"
        return f"Pendências abertas: {_TRAVESSAO} ({caminho.name} {situacao})\n"
    return f"Pendências abertas: {abertas} ({perfil.caminhos.backlog})\n"


def _linha_a_confirmar(raiz: Path, lista: list[str], grupo: str | None) -> str:
    """Conta as ocorrências do prefixo `[A CONFIRMAR` no documento atual, ou somadas nos documentos legíveis do
    pacote ou do lote (`grupo`); sem documento legível, mostra travessão."""
    contagens = []
    for documento in lista:
        try:
            contagens.append(comum.ler_texto(raiz / documento).count(_PREFIXO_A_CONFIRMAR))
        except (OSError, UnicodeDecodeError):
            pass
    total = str(sum(contagens)) if contagens else _TRAVESSAO
    return f"[A CONFIRMAR] no {grupo}: {total}\n" if grupo else f"[A CONFIRMAR] no documento atual: {total}\n"


def _linhas_de_commits(raiz: Path, executar_git) -> str:
    """Últimos três commits; qualquer falha do git vira `Últimos commits: indisponível`."""
    indisponivel = "Últimos commits: indisponível\n"
    try:
        resultado = executar_git(
            _COMANDO_GIT,
            cwd=raiz,
            timeout=_TEMPO_LIMITE_GIT,
            capture_output=True,
            text=True,
            # O hook roda fora do terminal, talvez com locale C: sem isto o `text=True` leria em ASCII.
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        return indisponivel
    saida = (resultado.stdout or "").strip()
    if resultado.returncode != 0 or not saida:
        return indisponivel
    return f"Últimos commits:\n{saida}\n"


def _linha_estudos(raiz: Path, perfil: Perfil) -> str:
    """Linha dos estudos com decisão por registrar e dos ilegíveis; vazia quando não há nenhum ou a pasta não se lê."""
    por_registrar, ilegiveis = estudos.contar(raiz / perfil.caminhos.estudos)
    if not por_registrar and not ilegiveis:
        return ""
    sufixo = f"; ilegíveis: {ilegiveis}" if ilegiveis else ""
    return f"Estudos com decisão por registrar: {por_registrar}{sufixo} ({perfil.caminhos.estudos})\n"


def bloco_hook(raiz: Path, perfil: Perfil, executar_git=subprocess.run) -> str:
    """Bloco de texto que o hook SessionStart injeta no começo da sessão (spec 6.1).

    O STATUS.md vem primeiro, depois a contagem de pendências abertas, a contagem de `[A CONFIRMAR]` no documento
    atual, a contagem de estudos com decisão por registrar e de ilegíveis (só quando há) e os três últimos commits.
    O ambiente (o pre-commit entre eles) e o próximo passo, o `sessao.py` acrescenta depois (spec 4a, §8.1).
    O texto termina em quebra de linha e, com ela, cabe em LIMITE_HOOK caracteres, de modo que a saída impressa não
    passa do limite. Nunca lança por falta ou erro de arquivo ou do git; `executar_git` é injetável para teste.
    """
    inicio, lista, grupo = _inicio_do_bloco(raiz, raiz / perfil.caminhos.status, perfil)
    return limitar_hook(
        inicio
        + _linha_pendencias(raiz, perfil)
        + _linha_a_confirmar(raiz, lista, grupo)
        + _linha_estudos(raiz, perfil)
        + _linhas_de_commits(raiz, executar_git)
    )
