"""O DER físico em tabelas Markdown, o gerador do DDL e do erDiagram, o rastreio contra a camada 2 e o manifesto do
Workbench.

O documento do DER é a fonte: cada subseção `### Tabela` traz a linha `Entidade:` ou `Ligação:` e a tabela das
colunas, com tipos neutros e a coluna Origem (spec 5a, §6). Daqui saem o DDL de cada banco e o bloco `erDiagram`.
"""
from __future__ import annotations

import hashlib
import posixpath
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import checar
import comum
from perfil import Perfil

AJUDA = """\
Gera e confere o DDL e o diagrama do DER físico e grava o manifesto dos prints do Workbench.

O documento vem do argumento, relativo à raiz ou absoluto, ou da chave `[der].documento` do perfil. Sai com 1 e
`perfil sem a seção [der]` quando o perfil não a tem; com `documento fora do projeto: <caminho>` quando o argumento
aponta para fora da raiz; com `documento não encontrado: <caminho>` sem o arquivo; com
`<caminho> é uma pasta; passe o arquivo do DER`; e com `documento ilegível: <caminho> (<motivo>)`. As saídas ficam na
mesma posição, em relação ao documento, que as chaves `[der].sql` e `[der].workbench` dão às pastas delas em
relação ao documento de `[der]`; abaixo, `<sql>` e `<workbench>` são essas pastas.

- `gerar [<documento>]`: grava `<sql>/schema.mysql.sql` (MySQL 8.4, o que o Workbench lê), também
  `<sql>/schema.<dialeto>.sql` quando `[der].dialeto` não é `""` nem `mysql`, e o bloco `erDiagram` do documento,
  entre a linha `%% gerado por harness.py der gerar; não edite` e o fim do bloco. Imprime
  `Gravado: <caminho> (<n> linhas)` por SQL e `Gravado: <documento> (bloco erDiagram)`, e sai com 0. Com o formato
  inválido, sai com 1 e um erro por linha, `<documento>:L<n>: <motivo>`, sem gravar nada. O rastreio contra a
  camada 2 não impede a geração: ele sai no `checar` do documento e no gate.
- `conferir [<documento>]`: gera em memória e compara com o disco. Sai com 0 e `OK: DER em dia`, ou com 1 e uma
  linha por diferença: `<sql>/schema.<banco>.sql ausente; rode harness.py der gerar`, o mesmo com `desatualizado`,
  e `erDiagram editado à mão ou desatualizado; rode harness.py der gerar`.
- `workbench`: depois do passo do Workbench, grava `<workbench>/manifesto.txt` e imprime
  `Gravado: <caminho> (<k> arquivos)`. Recusa, com 1 e sem gravar: o DER desatualizado, a pasta sem print em PNG e
  a falta do `workbench.sql` exportado.

O manifesto cita os caminhos a partir da pasta do documento: na primeira linha,
`sha256:<12 hexadecimais> <sql>/schema.mysql.sql`; na segunda, a data `AAAA-MM-DD`; depois, um por linha e em ordem
alfabética, os `.png` e o `workbench.sql` da pasta do Workbench. O `checar` do documento recusa o manifesto ausente,
o hash de outra versão do DDL e o arquivo listado que não existe.

O `\\r\\n` conta como `\\n` no `conferir`, no hash do manifesto e no rastreio, e o `gerar` mantém a quebra de linha
que o documento já tinha.
"""

MARCADOR = "%% gerado por harness.py der gerar; não edite"
CABECALHO = ("Coluna", "Tipo", "Nulo", "Chave", "Padrão", "Origem")
TECNICA = "técnica"
ENTIDADE_INTEIRA = "(entidade inteira)"

POLITICAS = ("restringir", "cascata", "anular")
OPERADORES = (">=", ">", "<=", "<")
TIPOS_SIMPLES = ("id", "inteiro", "inteiro_grande", "texto_longo", "booleano", "data", "hora", "data_hora", "json",
                 "uuid")
NUMERICOS = ("inteiro", "inteiro_grande")  # mais o decimal(p,e)
LIMITE_DE_NOME = 63  # o do Postgres

_RE_NOME = re.compile(r"[a-z][a-z0-9_]*")
_RE_ROTULO_DE_LISTA = re.compile(r"[*_\s]*(?:índices|restrições)[*_\s]*:?[*_\s]*", re.IGNORECASE)
_RE_ITEM_DE_LISTA = re.compile(r"\s*[-*+]\s")
_RE_TITULO = re.compile(r"### Tabela `([^`]*)`")
_RE_ENTIDADE = re.compile(r"Entidade: ([A-Za-z_][A-Za-z0-9_-]*) \(\[([^\]]+)\]\(([^)\s]+)\)\)")
_RE_LIGACAO = re.compile(r"Ligação: (.+?) \(([A-Za-z_][A-Za-z0-9_-]*) e ([A-Za-z_][A-Za-z0-9_-]*)\)")
_RE_TEXTO = re.compile(r"texto\((\d+)\)")
_RE_DECIMAL = re.compile(r"decimal\((\d+)\s*,\s*(\d+)\)")
_RE_ENUM = re.compile(r"enum\((.*)\)")
_RE_FK = re.compile(r"FK ([a-z][a-z0-9_]*)\.([a-z][a-z0-9_]*) \((restringir|cascata|anular)\)")
_RE_GRUPO = re.compile(r"UK:([a-z][a-z0-9_]*)")
_RE_NUMERO = re.compile(r"-?\d+(?:\.\d+)?")
_RE_INDICE = re.compile(r"- \(([^()]*)\)")
_RE_RESTRICAO = re.compile(r"- ([a-z][a-z0-9_]*) (>=|>|<=|<) (-?\d+(?:\.\d+)?)")
_RE_ENTRE = re.compile(r"- ([a-z][a-z0-9_]*) entre (-?\d+(?:\.\d+)?) e (-?\d+(?:\.\d+)?)")
_RE_NAO_PERSISTIDO = re.compile(r"- ([A-Za-z_][A-Za-z0-9_-]*): (.+?) — (.+)")
_RE_TITULO_DE_SECAO = re.compile(r"#{1,2} ")


class ErroDer(Exception):
    """O DER não pode ser lido ou gerado: perfil sem [der], documento ausente. `mensagem` diz o motivo."""

    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


@dataclass(frozen=True)
class Fk:
    tabela: str
    coluna: str
    politica: str  # restringir, cascata ou anular


@dataclass(frozen=True)
class Coluna:
    nome: str
    tipo: str  # o tipo neutro, na forma canônica: decimal(p,e), texto(n), enum(a, b)
    nulo: bool
    pk: bool
    uk: bool
    grupos: tuple[str, ...]
    fk: Fk | None
    padrao: str  # "" para —
    origem: str
    linha: int


@dataclass(frozen=True)
class Restricao:
    coluna: str
    operador: str  # >=, >, <=, < ou entre
    valores: tuple[str, ...]
    linha: int


@dataclass(frozen=True)
class Tabela:
    nome: str
    linha: int
    entidade: str  # vazio na tabela de ligação
    link: str  # vazio na tabela de ligação
    ligacao: tuple[str, str, str] | None  # (rótulo, A, B)
    colunas: tuple[Coluna, ...]
    indices: tuple[tuple[str, ...], ...]
    restricoes: tuple[Restricao, ...]

    def coluna(self, nome: str) -> Coluna | None:
        return next((coluna for coluna in self.colunas if coluna.nome == nome), None)


@dataclass(frozen=True)
class NaoPersistido:
    entidade: str
    trecho: str  # "" para a entidade inteira
    motivo: str
    linha: int


@dataclass(frozen=True)
class Der:
    tabelas: tuple[Tabela, ...]
    nao_persistidos: tuple[NaoPersistido, ...]

    def tabela(self, nome: str) -> Tabela | None:
        return next((tabela for tabela in self.tabelas if tabela.nome == nome), None)


def valores_do_enum(tipo: str) -> tuple[str, ...]:
    """Os valores de um `enum(a, b)` na forma canônica; tupla vazia para outro tipo."""
    achado = _RE_ENUM.fullmatch(tipo)
    return tuple(valor.strip() for valor in achado.group(1).split(",")) if achado else ()


def numerico(tipo: str) -> bool:
    return tipo in NUMERICOS or tipo.startswith("decimal(")


def _tipo(bruto: str) -> tuple[str, str | None]:
    """(tipo canônico, motivo do erro ou None) de um tipo neutro escrito na tabela."""
    if bruto in TIPOS_SIMPLES:
        return bruto, None
    achado = _RE_TEXTO.fullmatch(bruto)
    if achado:
        return bruto, None if 1 <= int(achado.group(1)) <= 4000 else "texto(n) com n de 1 a 4000"
    achado = _RE_DECIMAL.fullmatch(bruto)
    if achado:
        precisao, escala = int(achado.group(1)), int(achado.group(2))
        canonico = f"decimal({precisao},{escala})"
        if 1 <= precisao <= 65 and 0 <= escala <= 30 and escala <= precisao:
            return canonico, None
        return canonico, "decimal(p,e) com p de 1 a 65 e e de 0 a 30, sem passar de p"
    achado = _RE_ENUM.fullmatch(bruto)
    if achado:
        valores = [valor.strip() for valor in achado.group(1).split(",")]
        canonico = "enum(" + ", ".join(valores) + ")"
        fora = next((valor for valor in valores if valor and not _RE_NOME.fullmatch(valor)), None)
        if fora is not None:
            return canonico, (f"enum com valor fora de snake_case: {fora}; use minúsculas, dígitos e _, começando "
                              f"por letra")
        if len(valores) >= 2 and len(set(valores)) == len(valores) and all(_RE_NOME.fullmatch(v) for v in valores):
            return canonico, None
        return canonico, "enum com dois ou mais valores distintos em snake_case"
    return bruto, f"tipo desconhecido: {bruto}; use um dos tipos neutros"


def _dica_de_padrao(tipo: str) -> str:
    """O que serve de padrão para o tipo, para a mensagem de recusa."""
    if numerico(tipo):
        return "use um número, com ponto decimal"
    if tipo == "booleano":
        return "use verdadeiro ou falso"
    if tipo.startswith("enum("):
        return f"use um dos valores: {', '.join(valores_do_enum(tipo))}"
    achado = _RE_TEXTO.fullmatch(tipo)
    if achado:
        return f"use um texto entre aspas simples, com até {achado.group(1)} caracteres"
    if tipo == "data_hora":
        return "use agora"
    return f"{tipo} não tem padrão: use —"


def _padrao_serve(padrao: str, tipo: str) -> bool:
    if numerico(tipo):
        return bool(_RE_NUMERO.fullmatch(padrao))
    if tipo == "booleano":
        return padrao in ("verdadeiro", "falso")
    if tipo.startswith("enum("):
        return padrao in valores_do_enum(tipo)
    achado = _RE_TEXTO.fullmatch(tipo)
    if achado:
        return len(padrao) >= 2 and padrao[0] == padrao[-1] == "'" and len(padrao) - 2 <= int(achado.group(1))
    if tipo == "data_hora":
        return padrao == "agora"
    return False


class _Leitor:
    """Junta os erros como (linha, motivo); os sem linha usam 0 e saem sem `L<n>`."""

    def __init__(self):
        self.erros: list[tuple[int, str]] = []

    def erro(self, linha: int, motivo: str) -> None:
        self.erros.append((linha, motivo))

    def coluna(self, tabela: str, numero: int, celulas: list[str]) -> Coluna | None:
        nome, tipo_bruto, nulo_bruto, chave_bruta, padrao_bruto, origem = celulas
        tipo, motivo = _tipo(tipo_bruto)
        if motivo:
            self.erro(numero, f"{tabela}.{nome}: {motivo}")
        if nulo_bruto not in ("sim", "não"):
            self.erro(numero, f"{tabela}.{nome}: Nulo deve ser sim ou não")
        pk = uk = False
        grupos: list[str] = []
        fk: Fk | None = None
        if chave_bruta != "—":
            for parte in (parte.strip() for parte in chave_bruta.split(",")):
                achado_fk = _RE_FK.fullmatch(parte)
                achado_grupo = _RE_GRUPO.fullmatch(parte)
                if parte == "PK":
                    pk = True
                elif parte == "UK":
                    uk = True
                elif achado_grupo:
                    if achado_grupo.group(1) not in grupos:
                        grupos.append(achado_grupo.group(1))
                elif achado_fk and fk is None:
                    fk = Fk(*achado_fk.groups())
                elif achado_fk:
                    self.erro(numero, f"{tabela}.{nome}: mais de uma FK na coluna; deixe uma FK por coluna")
                else:
                    self.erro(numero, f"{tabela}.{nome}: chave desconhecida: {parte}; use PK, UK, UK:<grupo> ou "
                                      f"FK <tabela>.<coluna> (restringir|cascata|anular)")
        nulo = nulo_bruto == "sim"
        if pk and nulo:
            self.erro(numero, f"{tabela}.{nome}: PK não aceita nulo")
        if fk is not None and fk.politica == "anular" and not nulo:
            self.erro(numero, f"{tabela}.{nome}: FK com anular e Nulo não; use Nulo sim ou a ação restringir ou "
                              f"cascata")
        padrao = "" if padrao_bruto == "—" else padrao_bruto
        if padrao and not motivo and not _padrao_serve(padrao, tipo):
            self.erro(numero, f"{tabela}.{nome}: padrão {padrao} não serve para {tipo}; {_dica_de_padrao(tipo)}")
        if not origem:
            self.erro(numero, f"{tabela}.{nome}: sem Origem")
        return Coluna(nome, tipo, nulo, pk, uk, tuple(grupos), fk, padrao, origem, numero)

    def tabela(self, numero: int, titulo: str, linhas: list[tuple[int, str]], vistas: set[str]) -> Tabela | None:
        achado = _RE_TITULO.fullmatch(titulo.strip())
        if not achado:
            self.erro(numero, "título de tabela fora do formato; use ### Tabela `<nome>`")
            return None
        nome = achado.group(1)
        if not _RE_NOME.fullmatch(nome) or len(nome) > LIMITE_DE_NOME:
            self.erro(numero, f"nome de tabela fora de snake_case ou com mais de {LIMITE_DE_NOME} caracteres: {nome}")
        if nome in vistas:
            self.erro(numero, f"tabela {nome} repetida")
        vistas.add(nome)

        entidade = link = ""
        ligacao: tuple[str, str, str] | None = None
        linha_de_dono = next(((n, l.strip()) for n, l in linhas if l.startswith(("Entidade:", "Ligação:"))), None)
        if linha_de_dono is None:
            self.erro(numero, f"tabela {nome} sem a linha Entidade: nem Ligação:")
        elif linha_de_dono[1].startswith("Entidade:"):
            achado = _RE_ENTIDADE.fullmatch(linha_de_dono[1])
            if achado:
                entidade, link = achado.group(1), achado.group(3)
            else:
                self.erro(linha_de_dono[0],
                          "linha Entidade: fora do formato; use Entidade: <NOME_NO_ER> ([<arquivo>](<link>))")
        else:
            achado = _RE_LIGACAO.fullmatch(linha_de_dono[1])
            if achado:
                ligacao = (achado.group(1), achado.group(2), achado.group(3))
            else:
                self.erro(linha_de_dono[0], "linha Ligação: fora do formato; use Ligação: <rótulo> (<A> e <B>)")

        colunas: list[Coluna] = []
        tabela_de_colunas = next((t for t in checar.tabelas(linhas) if tuple(t[1]) == CABECALHO), None)
        if tabela_de_colunas is None:
            self.erro(numero, f"tabela {nome} sem a tabela de colunas | " + " | ".join(CABECALHO) + " |")
        else:
            for numero_da_linha, celulas in tabela_de_colunas[2]:
                if len(celulas) != len(CABECALHO):
                    self.erro(numero_da_linha, f"linha da tabela {nome} com {len(celulas)} células; use as "
                                               f"{len(CABECALHO)} do cabeçalho")
                    continue
                nome_da_coluna = celulas[0]
                if not _RE_NOME.fullmatch(nome_da_coluna) or len(nome_da_coluna) > LIMITE_DE_NOME:
                    self.erro(numero_da_linha, f"nome de coluna fora de snake_case ou com mais de "
                                               f"{LIMITE_DE_NOME} caracteres em {nome}: {nome_da_coluna}")
                if any(coluna.nome == nome_da_coluna for coluna in colunas):
                    self.erro(numero_da_linha, f"coluna {nome_da_coluna} repetida em {nome}")
                    continue
                colunas.append(self.coluna(nome, numero_da_linha, celulas))
            chaves = sum(1 for coluna in colunas if coluna.pk)
            if not tabela_de_colunas[2]:
                self.erro(numero, f"tabela {nome} sem colunas; escreva ao menos a coluna PK")
            elif chaves > 1:
                self.erro(numero, f"tabela {nome} com {chaves} colunas PK; use uma só e junte as outras com "
                                  f"UK:<grupo>")
            elif chaves == 0 and colunas:
                self.erro(numero, f"tabela {nome} sem coluna PK; marque uma coluna com PK")

        indices, restricoes = self.listas(nome, linhas, colunas)
        return Tabela(nome, numero, entidade, link, ligacao, tuple(colunas), tuple(indices), tuple(restricoes))

    def listas(self, tabela: str, linhas: list[tuple[int, str]], colunas: list[Coluna]):
        """Os itens das listas `Índices:` e `Restrições:` da subseção."""
        por_nome = {coluna.nome: coluna for coluna in colunas}
        indices: list[tuple[str, ...]] = []
        restricoes: list[Restricao] = []
        lista = None
        for numero, linha in linhas:
            texto = linha.strip()
            if texto in ("Índices:", "Restrições:"):
                lista = texto
                continue
            if _RE_ROTULO_DE_LISTA.fullmatch(texto):
                self.erro(numero, f"rótulo fora do formato: {texto}; use Índices: ou Restrições:, sem negrito, "
                                  f"sozinho na linha")
                lista = None
                continue
            if not texto or lista is None:
                continue
            if not linha.startswith("-"):
                if _RE_ITEM_DE_LISTA.match(linha):
                    self.erro(numero, f"item de {lista[:-1]} fora do formato; use - no começo da linha, sem recuo")
                    continue
                lista = None
                continue
            if lista == "Índices:":
                achado = _RE_INDICE.fullmatch(texto)
                nomes = [parte.strip() for parte in achado.group(1).split(",")] if achado else []
                if not achado or not all(_RE_NOME.fullmatch(nome) for nome in nomes):
                    self.erro(numero, "índice fora do formato; use - (<coluna>, <coluna>)")
                    continue
                faltando = next((nome for nome in nomes if nome not in por_nome), None)
                if faltando:
                    self.erro(numero, f"índice com a coluna {faltando}, que não existe em {tabela}")
                    continue
                indices.append(tuple(nomes))
                continue
            entre = _RE_ENTRE.fullmatch(texto)
            simples = _RE_RESTRICAO.fullmatch(texto)
            if entre:
                restricao = Restricao(entre.group(1), "entre", (entre.group(2), entre.group(3)), numero)
            elif simples:
                restricao = Restricao(simples.group(1), simples.group(2), (simples.group(3),), numero)
            else:
                self.erro(numero, "restrição fora do formato; use - <coluna> >= <número> ou "
                                  "- <coluna> entre <a> e <b>, com ponto decimal, só em coluna numérica")
                continue
            alvo = por_nome.get(restricao.coluna)
            if alvo is None:
                self.erro(numero, f"restrição com a coluna {restricao.coluna}, que não existe em {tabela}")
                continue
            if not numerico(alvo.tipo):
                self.erro(numero, f"restrição na coluna {restricao.coluna}, que não é numérica")
                continue
            if entre and float(restricao.valores[0]) > float(restricao.valores[1]):
                self.erro(numero, f"restrição entre {restricao.valores[0]} e {restricao.valores[1]} com o primeiro "
                                  f"maior que o segundo")
                continue
            restricoes.append(restricao)
        return indices, restricoes

    def fks(self, tabelas: list[Tabela]) -> None:
        """As FKs apontam para uma coluna PK ou única de tipo igual, numa tabela do documento."""
        por_nome = {tabela.nome: tabela for tabela in tabelas}
        for tabela in tabelas:
            for coluna in tabela.colunas:
                if coluna.fk is None:
                    continue
                destino = f"{coluna.fk.tabela}.{coluna.fk.coluna}"
                alvo_tabela = por_nome.get(coluna.fk.tabela)
                alvo = alvo_tabela.coluna(coluna.fk.coluna) if alvo_tabela else None
                if alvo is None:
                    self.erro(coluna.linha, f"{tabela.nome}.{coluna.nome}: FK para {destino}, que não existe")
                elif not _unica(alvo_tabela, alvo):
                    self.erro(coluna.linha, f"{tabela.nome}.{coluna.nome}: FK para {destino}, que não é PK nem UK")
                elif alvo.tipo != coluna.tipo:
                    self.erro(coluna.linha, f"{tabela.nome}.{coluna.nome}: FK com tipo {coluna.tipo}, e {destino} é "
                                            f"{alvo.tipo}")

    def nao_persistidos(self, texto: str) -> list[NaoPersistido]:
        itens: list[NaoPersistido] = []
        for _, _, linhas in checar.secoes(texto, "## Não persistido"):
            for numero, linha in linhas:
                if not linha.startswith("-") or not linha[1:].strip():
                    continue  # o item vazio é sobra de molde, que o checar acusa
                achado = _RE_NAO_PERSISTIDO.fullmatch(linha.strip())
                if not achado:
                    self.erro(numero, "item de Não persistido fora do formato; use "
                                      "- <NOME_NO_ER>: <trecho> — <motivo>")
                    continue
                trecho = achado.group(2).strip()
                itens.append(NaoPersistido(achado.group(1), "" if trecho == ENTIDADE_INTEIRA else trecho,
                                           achado.group(3).strip(), numero))
        return itens

    def diagrama(self, texto: str) -> None:
        secao = checar.secoes(texto, "## Diagrama")
        if not secao:
            self.erro(0, 'sem a seção "## Diagrama"; copie-a do molde')
            return
        inicio = secao[0][0]
        fim = next((numero for numero, linha in checar.linhas_fora_de_blocos(texto)
                    if numero > inicio and _RE_TITULO_DE_SECAO.match(linha)), None)
        if _bloco_do_diagrama(texto, inicio, fim) is None:
            self.erro(inicio, f"seção Diagrama sem o bloco com a linha {MARCADOR}")


def _unica(tabela: Tabela, coluna: Coluna) -> bool:
    """A coluna é PK, UK sozinha ou a única coluna de um grupo UK."""
    if coluna.pk or coluna.uk:
        return True
    return any(sum(1 for outra in tabela.colunas if grupo in outra.grupos) == 1 for grupo in coluna.grupos)


def _bloco_do_diagrama(texto: str, inicio: int, fim: int | None):
    """(linha da cerca, conteúdo) do bloco da seção Diagrama que tem a linha do marcador, ou None."""
    for cerca, conteudo in checar.blocos_de_codigo(texto):
        dentro = cerca > inicio and (fim is None or cerca < fim)
        if dentro and any(linha.strip() == MARCADOR for _, linha in conteudo):
            return cerca, conteudo
    return None


def ler(texto: str) -> tuple[Der, list[str]]:
    """O modelo e os erros de formato, cada um `L<n>: <motivo>`, na ordem das linhas; os do documento inteiro, sem
    linha, vêm primeiro."""
    leitor = _Leitor()
    tabelas: list[Tabela] = []
    vistas: set[str] = set()
    for numero, titulo, linhas in checar.secoes(texto, "### Tabela"):
        tabela = leitor.tabela(numero, titulo, linhas, vistas)
        if tabela is not None:
            tabelas.append(tabela)
    if not tabelas and not leitor.erros:
        leitor.erro(0, "nenhuma tabela: escreva uma subseção ### Tabela `<nome>` em Tabelas")
    leitor.fks(tabelas)
    ciclo = _ciclo(Der(tuple(tabelas), ()))
    if ciclo:
        leitor.erro(0, f"ciclo de FKs entre as tabelas {comum.juntar(ciclo)}; tire uma das FKs ou ligue as tabelas "
                       f"por uma tabela de ligação")
    nao_persistidos = leitor.nao_persistidos(texto)
    leitor.diagrama(texto)
    erros = [motivo if linha == 0 else f"L{linha}: {motivo}"
             for linha, motivo in sorted(leitor.erros, key=lambda erro: erro[0])]
    return Der(tuple(tabelas), tuple(nao_persistidos)), erros


def nome_curto(nome: str) -> str:
    """O nome como está, até 63 caracteres; acima, os 54 primeiros, `_` e 8 hexadecimais do SHA-1 do nome inteiro."""
    if len(nome) <= LIMITE_DE_NOME:
        return nome
    return nome[:54] + "_" + hashlib.sha1(nome.encode("utf-8")).hexdigest()[:8]


def nomes(tabela: Tabela, dialeto: str) -> tuple[str, ...]:
    """Os nomes das restrições e dos índices na ordem do DDL (spec 5a, §6.4).

    PK; únicos (os de uma coluna na ordem das colunas, depois os grupos na ordem da primeira coluna); índices; FKs na
    ordem das colunas; restrições na ordem da lista; no `postgres`, os `CHECK` de `enum` na ordem das colunas. Nome
    repetido ganha `_2`, `_3`; o nome longo sai cortado por `nome_curto`.
    """
    t = tabela.nome
    base = [f"pk_{t}"]
    base += [f"uk_{t}_{coluna.nome}" for coluna in tabela.colunas if coluna.uk]
    base += [f"uk_{t}_{grupo}" for grupo in grupos(tabela)]
    base += [f"idx_{t}_" + "_".join(indice) for indice in tabela.indices]
    base += [f"fk_{t}_{coluna.nome}" for coluna in tabela.colunas if coluna.fk is not None]
    base += [f"ck_{t}_{restricao.coluna}" for restricao in tabela.restricoes]
    if dialeto == "postgres":
        base += [f"ck_{t}_{coluna.nome}" for coluna in tabela.colunas if coluna.tipo.startswith("enum(")]
    vistos: dict[str, int] = {}
    saida = []
    for nome in base:
        vistos[nome] = vistos.get(nome, 0) + 1
        saida.append(nome_curto(nome if vistos[nome] == 1 else f"{nome}_{vistos[nome]}"))
    return tuple(saida)


def grupos(tabela: Tabela) -> list[str]:
    """Os grupos `UK:<grupo>` da tabela, na ordem da primeira coluna de cada um."""
    achados: list[str] = []
    for coluna in tabela.colunas:
        for grupo in coluna.grupos:
            if grupo not in achados:
                achados.append(grupo)
    return achados


def _dependencias(tabela: Tabela, nomes_das_tabelas) -> list[str]:
    """As tabelas para que a tabela aponta por FK, na ordem das colunas, sem ela mesma e sem repetição."""
    achadas: list[str] = []
    for coluna in tabela.colunas:
        if coluna.fk and coluna.fk.tabela != tabela.nome and coluna.fk.tabela in nomes_das_tabelas:
            if coluna.fk.tabela not in achadas:
                achadas.append(coluna.fk.tabela)
    return achadas


def _ordem(modelo: Der) -> tuple[list[Tabela], list[Tabela]]:
    """(ordenadas, que sobram): a cada passo entra a primeira tabela, na ordem do documento, cujas FKs já entraram."""
    nomes_das_tabelas = {tabela.nome for tabela in modelo.tabelas}
    feitas: list[Tabela] = []
    restantes = list(modelo.tabelas)
    while restantes:
        prontas = {tabela.nome for tabela in feitas}
        proxima = next((tabela for tabela in restantes
                        if all(d in prontas for d in _dependencias(tabela, nomes_das_tabelas))), None)
        if proxima is None:
            break
        feitas.append(proxima)
        restantes.remove(proxima)
    return feitas, restantes


def ordenar(modelo: Der) -> list[Tabela]:
    """As tabelas em ordem topológica pelas FKs, estável na ordem do documento; a FK para a própria tabela não
    conta.

    Num ciclo, que o `ler` acusa, as tabelas que sobram saem no fim, na ordem do documento.
    """
    feitas, restantes = _ordem(modelo)
    return feitas + restantes


def _ciclo(modelo: Der) -> list[str]:
    """As tabelas de um ciclo de FKs, achado a partir da primeira que sobra na ordenação, na ordem do ciclo."""
    restantes = _ordem(modelo)[1]
    if not restantes:
        return []
    por_nome = {tabela.nome: tabela for tabela in restantes}
    caminho = [restantes[0].nome]
    while True:
        seguinte = _dependencias(por_nome[caminho[-1]], por_nome)[0]
        if seguinte in caminho:
            return caminho[caminho.index(seguinte):]
        caminho.append(seguinte)


_TIPOS_MYSQL = {"id": "BIGINT", "inteiro": "INT", "inteiro_grande": "BIGINT", "texto_longo": "TEXT",
                "booleano": "TINYINT(1)", "data": "DATE", "hora": "TIME", "data_hora": "DATETIME(3)", "json": "JSON",
                "uuid": "CHAR(36)"}
_TIPOS_POSTGRES = {"id": "BIGINT", "inteiro": "INTEGER", "inteiro_grande": "BIGINT", "texto_longo": "TEXT",
                   "booleano": "BOOLEAN", "data": "DATE", "hora": "TIME", "data_hora": "TIMESTAMP(3) WITH TIME ZONE",
                   "json": "JSONB", "uuid": "UUID"}
_POLITICAS_SQL = {"restringir": "RESTRICT", "cascata": "CASCADE", "anular": "SET NULL"}
_BANCOS = {"mysql": "MySQL 8.4", "postgres": "PostgreSQL 18"}


def _literal(texto: str, dialeto: str) -> str:
    """Texto entre aspas simples, com `'` dobrado nos dois bancos e `\\` dobrado só no MySQL."""
    if dialeto == "mysql":
        texto = texto.replace("\\", "\\\\")
    return "'" + texto.replace("'", "''") + "'"


def _tipo_sql(coluna: Coluna, dialeto: str) -> str:
    valores = valores_do_enum(coluna.tipo)
    if valores:
        if dialeto == "mysql":
            return "ENUM(" + ",".join(_literal(valor, dialeto) for valor in valores) + ")"
        return f"VARCHAR({max(len(valor) for valor in valores)})"
    achado = _RE_DECIMAL.fullmatch(coluna.tipo)
    if achado:
        return ("DECIMAL" if dialeto == "mysql" else "NUMERIC") + f"({achado.group(1)},{achado.group(2)})"
    achado = _RE_TEXTO.fullmatch(coluna.tipo)
    if achado:
        return f"VARCHAR({achado.group(1)})"
    return (_TIPOS_MYSQL if dialeto == "mysql" else _TIPOS_POSTGRES)[coluna.tipo]


def _padrao_sql(coluna: Coluna, dialeto: str) -> str:
    padrao = coluna.padrao
    if padrao == "agora":
        return "CURRENT_TIMESTAMP(3)" if dialeto == "mysql" else "CURRENT_TIMESTAMP"
    if coluna.tipo == "booleano":
        verdadeiro = padrao == "verdadeiro"
        return ("1" if verdadeiro else "0") if dialeto == "mysql" else ("TRUE" if verdadeiro else "FALSE")
    if coluna.tipo.startswith("enum("):
        return _literal(padrao, dialeto)
    if coluna.tipo.startswith("texto("):
        return _literal(padrao[1:-1], dialeto)
    return padrao


def _gerada(coluna: Coluna) -> bool:
    """A PK do tipo `id` sem FK é gerada pelo banco."""
    return coluna.pk and coluna.tipo == "id" and coluna.fk is None


def _comentario_da_tabela(tabela: Tabela) -> str:
    if tabela.ligacao:
        rotulo, a, b = tabela.ligacao
        return f"Ligação: {rotulo} ({a} e {b})"
    return f"Entidade: {tabela.entidade}"


def _create_table(tabela: Tabela, dialeto: str) -> list[str]:
    mysql = dialeto == "mysql"

    def q(nome: str) -> str:
        return f"`{nome}`" if mysql else f'"{nome}"'

    def lista(colunas) -> str:
        return ", ".join(q(nome) for nome in colunas)

    nomes_gerados = iter(nomes(tabela, dialeto))
    partes = []
    for coluna in tabela.colunas:
        parte = f"{q(coluna.nome)} {_tipo_sql(coluna, dialeto)}"
        if not coluna.nulo:
            parte += " NOT NULL"
        if _gerada(coluna):
            parte += " AUTO_INCREMENT" if mysql else " GENERATED ALWAYS AS IDENTITY"
        if coluna.padrao:
            parte += f" DEFAULT {_padrao_sql(coluna, dialeto)}"
        if mysql:
            parte += f" COMMENT {_literal(coluna.origem, dialeto)}"
        partes.append(parte)
    chave = next(coluna for coluna in tabela.colunas if coluna.pk)
    partes.append(f"CONSTRAINT {q(next(nomes_gerados))} PRIMARY KEY ({q(chave.nome)})")
    unicos = [(coluna.nome,) for coluna in tabela.colunas if coluna.uk]
    unicos += [tuple(coluna.nome for coluna in tabela.colunas if grupo in coluna.grupos) for grupo in grupos(tabela)]
    for colunas in unicos:
        nome = q(next(nomes_gerados))
        if mysql:
            partes.append(f"UNIQUE KEY {nome} ({lista(colunas)})")
        else:
            partes.append(f"CONSTRAINT {nome} UNIQUE ({lista(colunas)})")
    indices = [(next(nomes_gerados), indice) for indice in tabela.indices]
    if mysql:
        partes += [f"KEY {q(nome)} ({lista(indice)})" for nome, indice in indices]
    for coluna in tabela.colunas:
        if coluna.fk:
            politica = _POLITICAS_SQL[coluna.fk.politica]
            partes.append(f"CONSTRAINT {q(next(nomes_gerados))} FOREIGN KEY ({q(coluna.nome)}) REFERENCES "
                          f"{q(coluna.fk.tabela)} ({q(coluna.fk.coluna)}) ON DELETE {politica}")
    for restricao in tabela.restricoes:
        if restricao.operador == "entre":
            condicao = f"{q(restricao.coluna)} BETWEEN {restricao.valores[0]} AND {restricao.valores[1]}"
        else:
            condicao = f"{q(restricao.coluna)} {restricao.operador} {restricao.valores[0]}"
        partes.append(f"CONSTRAINT {q(next(nomes_gerados))} CHECK ({condicao})")
    if not mysql:
        for coluna in tabela.colunas:
            valores = valores_do_enum(coluna.tipo)
            if valores:
                em = ",".join(_literal(valor, dialeto) for valor in valores)
                partes.append(f"CONSTRAINT {q(next(nomes_gerados))} CHECK ({q(coluna.nome)} IN ({em}))")
    linhas = [f"CREATE TABLE {q(tabela.nome)} ("]
    linhas += [f"  {parte}," for parte in partes[:-1]] + [f"  {partes[-1]}"]
    comentario = _literal(_comentario_da_tabela(tabela), dialeto)
    if mysql:
        linhas.append(f") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT={comentario};")
        return linhas
    linhas.append(");")
    linhas += [f"CREATE INDEX {q(nome)} ON {q(tabela.nome)} ({lista(indice)});" for nome, indice in indices]
    linhas.append(f"COMMENT ON TABLE {q(tabela.nome)} IS {comentario};")
    linhas += [f"COMMENT ON COLUMN {q(tabela.nome)}.{q(coluna.nome)} IS {_literal(coluna.origem, dialeto)};"
               for coluna in tabela.colunas]
    return linhas


def ddl(modelo: Der, dialeto: str, documento: str) -> str:
    """O DDL inteiro do dialeto (`mysql` ou `postgres`), sem data nem hash, terminado por uma quebra só."""
    linhas = [f"-- Gerado por harness.py der gerar a partir de {documento}; não edite.",
              f"-- Banco: {_BANCOS[dialeto]}", ""]
    if dialeto == "mysql":
        linhas += ["SET NAMES utf8mb4;", ""]
    blocos = ["\n".join(_create_table(tabela, dialeto)) for tabela in ordenar(modelo)]
    return "\n".join(linhas) + "\n" + "\n\n".join(blocos) + "\n"


def _sem_aspas_duplas(texto: str) -> str:
    return texto.replace('"', "'")


def diagrama(modelo: Der) -> list[str]:
    """As linhas do bloco `erDiagram` depois do marcador: as entidades na ordem do documento, depois as relações."""
    linhas: list[str] = []
    for tabela in modelo.tabelas:
        linhas.append(f"    {tabela.nome} {{")
        for coluna in tabela.colunas:
            tipo = "enum" if coluna.tipo.startswith("enum(") else coluna.tipo.replace(" ", "")
            chaves = [chave for chave, tem in (("PK", coluna.pk), ("FK", coluna.fk is not None),
                                               ("UK", coluna.uk or bool(coluna.grupos))) if tem]
            atributo = f"        {tipo} {coluna.nome}"
            if chaves:
                atributo += " " + ", ".join(chaves)
            linhas.append(f'{atributo} "{_sem_aspas_duplas(coluna.origem)}"')
        linhas.append("    }")
    for tabela in modelo.tabelas:
        for coluna in tabela.colunas:
            if coluna.fk is None:
                continue
            pai = "|o" if coluna.nulo else "||"
            filho = "o|" if coluna.pk or coluna.uk else "o{"
            rotulo = coluna.origem[len("relação: "):] if coluna.origem.startswith("relação: ") else coluna.nome
            linhas.append(f'    {coluna.fk.tabela} {pai}--{filho} {tabela.nome} : "{_sem_aspas_duplas(rotulo)}"')
    return linhas


def com_diagrama(texto: str, modelo: Der) -> str:
    """O documento com as linhas entre o marcador e o fim do bloco trocadas pelas de `diagrama`, na quebra de linha
    do documento (`\\r\\n` se ele a tem). Sem o bloco do marcador, o texto volta como está."""
    secao = checar.secoes(texto, "## Diagrama")
    if not secao:
        return texto
    inicio = secao[0][0]
    fim = next((numero for numero, linha in checar.linhas_fora_de_blocos(texto)
                if numero > inicio and _RE_TITULO_DE_SECAO.match(linha)), None)
    bloco = _bloco_do_diagrama(texto, inicio, fim)
    if bloco is None:
        return texto
    marcador = next(numero for numero, linha in bloco[1] if linha.strip() == MARCADOR)
    linhas = texto.split("\n")
    fecho = next((indice for indice in range(marcador, len(linhas))
                  if linhas[indice].rstrip("\r").lstrip().startswith("```")), len(linhas))
    fim_de_linha = "\r" if "\r\n" in texto else ""
    novas = [linha + fim_de_linha for linha in diagrama(modelo)]
    return "\n".join(linhas[:marcador] + novas + linhas[fecho:])


@dataclass(frozen=True)
class Relacao:
    a: str
    b: str
    rotulo: str  # sem as aspas
    copia: bool
    linha: int


@dataclass(frozen=True)
class Conceitual:
    entidades: tuple[str, ...]
    relacoes: tuple[Relacao, ...]


_NOME_NO_ER = r"[A-Za-z_][A-Za-z0-9_-]*"
_CARDINALIDADE_A = r"(\|o|\|\||\}o|\}\|)"
_CARDINALIDADE_B = r"(o\||\|\||o\{|\|\{)"
_RE_RELACAO = re.compile(rf"\s*({_NOME_NO_ER})\s+{_CARDINALIDADE_A}(?:--|\.\.){_CARDINALIDADE_B}\s+({_NOME_NO_ER})"
                         r"\s*:\s*(?:\"([^\"]*)\"|(\S+))\s*")
_RE_SOLTA = re.compile(rf"\s*({_NOME_NO_ER})\s*(\{{)?\s*")
_RE_ITEM = re.compile(r"(?:[-*+]|\d+[.)])(?:\s|$)")
_RE_ORIGEM_DE_COPIA = re.compile(rf"({_NOME_NO_ER}): (.+)")


def conceitual(texto: str, rotulo_copia: str) -> Conceitual:
    """As entidades e as relações do primeiro bloco que começa por `erDiagram`.

    A relação é `<A> <cardinalidade>(--|..)<cardinalidade> <B> : <rótulo>`, com o rótulo entre aspas ou numa
    palavra, que sai sem as aspas; é de cópia quando o rótulo contém `rotulo_copia`. As entidades são as das relações
    e as das linhas soltas com o nome, na ordem em que aparecem; os atributos entre chaves ficam de fora.
    """
    entidades: list[str] = []
    relacoes: list[Relacao] = []
    for _, conteudo in checar.blocos_de_codigo(texto):
        uteis = [(numero, linha) for numero, linha in conteudo if linha.strip()]
        if not uteis or not uteis[0][1].strip().startswith("erDiagram"):
            continue
        dentro = False
        for numero, linha in uteis[1:]:
            texto_da_linha = linha.strip()
            if dentro:
                dentro = not texto_da_linha.startswith("}")
                continue
            achado = _RE_RELACAO.fullmatch(linha)
            if achado:
                a, b = achado.group(1), achado.group(4)
                rotulo = achado.group(5) if achado.group(5) is not None else achado.group(6)
                relacoes.append(Relacao(a, b, rotulo, rotulo_copia in rotulo, numero))
                novas = (a, b)
            else:
                solta = _RE_SOLTA.fullmatch(linha)
                if solta is None or texto_da_linha.startswith("%%"):
                    continue
                dentro = solta.group(2) is not None
                novas = (solta.group(1),)
            entidades += [nome for nome in novas if nome not in entidades and nome not in ("title", "direction")]
        break
    return Conceitual(tuple(entidades), tuple(relacoes))


def atributos(texto: str) -> list[tuple[int, str]]:
    """(linha, texto) de cada item sob `## Atributos principais`, em qualquer nível.

    O texto do item junta as linhas que o continuam, recuadas e sem marcador de lista; o subitem é um item por si,
    com as linhas que o continuam, e fica de fora do texto do item de cima.
    """
    itens: list[tuple[int, str]] = []
    for _, _, linhas in checar.secoes(texto, "## Atributos principais"):
        atual: list[str] | None = None
        for numero, linha in linhas[1:]:
            if not linha.strip():
                continue
            if linha[0] in "-*+" and _RE_ITEM.match(linha):
                atual = [linha[1:].strip()]
                itens.append((numero, ""))
            elif linha[0].isspace() and atual is not None and _RE_ITEM.match(linha.strip()):
                marcador = _RE_ITEM.match(linha.strip())
                atual = [linha.strip()[marcador.end():].strip()]
                itens.append((numero, ""))
            elif linha[0].isspace() and atual is not None:
                atual.append(linha.strip())
            else:
                atual = None
                continue
            itens[-1] = (itens[-1][0], " ".join(atual))
        break
    return itens


def _normal(texto: str) -> str:
    return " ".join(unicodedata.normalize("NFC", texto).lower().split())


def casa(trecho: str, item: str) -> bool:
    """O trecho aparece dentro do item, sem diferença de maiúsculas, com os espaços colapsados e os dois lados em
    NFC; os acentos contam."""
    return bool(_normal(trecho)) and _normal(trecho) in _normal(item)


def _inicio(item: str) -> str:
    """O item sem a pontuação do fim; acima de 40 caracteres, os 40 primeiros cortados no último espaço e ` ...`."""
    texto = item.rstrip(";.,: ")
    if len(texto) <= 40:
        return texto
    corte = texto[:40]
    if " " in corte:
        corte = corte[:corte.rindex(" ")]
    return corte.rstrip(",;: ") + " ..."


@dataclass
class _Fonte:
    """O documento de uma entidade: caminho relativo à raiz e itens de "Atributos principais"."""

    caminho: str
    itens: list[tuple[int, str]]

    @property
    def nome(self) -> str:
        return posixpath.basename(self.caminho)


def _ler_fonte(raiz: Path, relativo: str, problemas: list[str]) -> str | None:
    try:
        return comum.ler_texto(raiz / relativo).replace("\r\n", "\n")
    except FileNotFoundError:
        problemas.append(f"{relativo}: arquivo ausente")
    except UnicodeDecodeError:
        problemas.append(f"{relativo}: não está em UTF-8")
    except OSError as erro:
        problemas.append(f"{relativo}: arquivo ilegível ({erro.strerror or type(erro).__name__})")
    return None


class _Rastreio:
    def __init__(self, raiz: Path, perfil: Perfil, modelo: Der, documento: str, conceitual_: Conceitual):
        secao = perfil.der
        self.raiz = raiz
        self.secao = secao
        self.modelo = modelo
        self.documento = documento
        self.conceitual = conceitual_
        self.caminho_conceitual = f"{perfil.caminhos.planejamento}/{secao.conceitual}"
        self.pasta_entidades = f"{perfil.caminhos.planejamento}/{secao.entidades}"
        self.problemas: list[str] = []
        self.fontes: dict[str, _Fonte] = {}
        self.cobertos: dict[str, set[int]] = {}
        dispensadas = {item.entidade for item in modelo.nao_persistidos if not item.trecho}
        com_tabela = {tabela.entidade for tabela in modelo.tabelas if tabela.entidade}
        self.dispensadas = dispensadas - com_tabela

    def entidade_de(self, nome_da_tabela: str) -> str:
        tabela = self.modelo.tabela(nome_da_tabela)
        return tabela.entidade if tabela else ""

    def fonte_das_tabelas(self) -> None:
        """Regra 7, parte do link, e o documento de cada entidade, pelo link da primeira tabela dela (decisão 1)."""
        primeiro_link: dict[str, str] = {}
        pasta = posixpath.dirname(self.documento)
        for tabela in self.modelo.tabelas:
            if not tabela.entidade:
                continue
            if tabela.entidade not in self.conceitual.entidades:
                self.problemas.append(f"tabela {tabela.nome}: entidade {tabela.entidade} não está no modelo "
                                      f"conceitual ({self.caminho_conceitual})")
            if tabela.entidade in primeiro_link:
                if tabela.link != primeiro_link[tabela.entidade]:
                    self.problemas.append(f"tabela {tabela.nome}: o link {tabela.link} difere do da primeira tabela "
                                          f"de {tabela.entidade}, {primeiro_link[tabela.entidade]}; use o mesmo link")
                continue
            primeiro_link[tabela.entidade] = tabela.link
            resolvido = posixpath.normpath(posixpath.join(pasta, tabela.link))
            if not resolvido.startswith(self.pasta_entidades + "/"):
                certo = posixpath.join(posixpath.relpath(self.pasta_entidades, pasta), posixpath.basename(tabela.link))
                self.problemas.append(f"tabela {tabela.nome}: o link {tabela.link} não aponta para um documento de "
                                      f"{self.pasta_entidades}; use {certo}")
                continue
            if not (self.raiz / resolvido).is_file():
                self.problemas.append(f"tabela {tabela.nome}: o link {tabela.link} não resolve")
                continue
            texto = _ler_fonte(self.raiz, resolvido, self.problemas)
            if texto is None:
                continue
            if not checar.secoes(texto, "## Atributos principais"):
                self.problemas.append(f'{posixpath.basename(resolvido)}: sem a seção "## Atributos principais"')
                continue
            self.fontes[tabela.entidade] = _Fonte(resolvido, atributos(texto))
            self.cobertos[tabela.entidade] = set()

    def casar(self, onde: str, entidade: str, trecho: str, citado: str) -> int | None:
        """Regra 5: o índice do único item da entidade com que o trecho casa, ou None, com o problema anotado."""
        fonte = self.fontes.get(entidade)
        if fonte is None:
            return None
        achados = [indice for indice, (_, item) in enumerate(fonte.itens) if casa(trecho, item)]
        if not achados:
            self.problemas.append(f'{onde}: origem "{citado}" não casa com nenhum item de {entidade} ({fonte.nome}); '
                                  f'copie um trecho de "Atributos principais"')
            return None
        if len(achados) > 1:
            self.problemas.append(f'{onde}: origem "{citado}" casa com {len(achados)} itens de {entidade}; use um '
                                  f'trecho maior')
            return None
        return achados[0]

    def relacao(self, rotulo: str, a: str, b: str) -> Relacao | None:
        return next((r for r in self.conceitual.relacoes if r.rotulo == rotulo and {r.a, r.b} == {a, b}), None)

    def copia_entre(self, a: str, b: str) -> bool:
        return any(r.copia and {r.a, r.b} == {a, b} for r in self.conceitual.relacoes)

    def sem_documento(self, entidade: str) -> bool:
        if entidade in self.fontes:
            return False
        if not any(tabela.entidade == entidade for tabela in self.modelo.tabelas):
            self.problemas.append(f'{entidade} sem tabela no DER: a origem "{entidade}: ..." precisa do documento '
                                  f'dela pela linha Entidade:')
        return True

    def coluna(self, tabela: Tabela, coluna: Coluna) -> None:
        onde = f"{tabela.nome}.{coluna.nome}"
        origem = coluna.origem
        if origem == TECNICA:
            if coluna.nome not in self.secao.tecnicas:
                self.problemas.append(f'{onde}: Origem "técnica" só vale para {comum.juntar(self.secao.tecnicas)}; '
                                      f'nas outras colunas, use o trecho de um atributo da entidade ou, na FK, '
                                      f'"relação: <rótulo>"')
            return
        if coluna.fk is not None and self.modelo.tabela(coluna.fk.tabela) is None:
            return  # FK para tabela que não existe: o der-formato já acusa
        if tabela.ligacao:
            rotulo = tabela.ligacao[0]
            if coluna.fk is None or origem != f"relação: {rotulo}":
                self.problemas.append(f'{onde}: tabela de ligação só tem colunas de FK, com "relação: {rotulo}", '
                                      f'e técnicas')
            return
        if origem.startswith("relação:"):
            rotulo = origem[len("relação:"):].strip()
            if coluna.fk is None:
                self.problemas.append(f'{onde}: Origem "relação:" só em coluna de FK')
                return
            alvo = self.entidade_de(coluna.fk.tabela)
            relacao = self.relacao(rotulo, tabela.entidade, alvo)
            if relacao is not None and relacao.copia:
                self.problemas.append(f'{onde}: "relação: {rotulo}" é de cópia; tire a FK e copie os atributos')
            elif relacao is None:
                self.problemas.append(f'{onde}: "relação: {rotulo}" não é uma relação entre {tabela.entidade} e '
                                      f'{alvo} no modelo conceitual')
            return
        copia = _RE_ORIGEM_DE_COPIA.fullmatch(origem)
        if copia and copia.group(1) in self.conceitual.entidades:
            outra = copia.group(1)
            if coluna.fk is not None:
                self.problemas.append(f'{onde}: origem "{origem}" é de cópia, e cópia não tem FK; tire a FK')
            elif not self.copia_entre(tabela.entidade, outra):
                self.problemas.append(f'{onde}: origem "{origem}" sem relação de cópia entre {tabela.entidade} e '
                                      f'{outra}')
            elif not self.sem_documento(outra):
                self.casar(onde, outra, copia.group(2), origem)
            return
        if coluna.fk is not None:
            alvo = self.entidade_de(coluna.fk.tabela)
            if alvo != tabela.entidade:
                self.problemas.append(f'{onde}: FK para {coluna.fk.tabela} ({alvo}) com Origem "{origem}"; use '
                                      f'"relação: <rótulo>"')
                return
        indice = self.casar(onde, tabela.entidade, origem, origem)
        if indice is not None:
            self.cobertos[tabela.entidade].add(indice)

    def ligacao(self, tabela: Tabela) -> None:
        rotulo, a, b = tabela.ligacao
        relacao = self.relacao(rotulo, a, b)
        if relacao is None or relacao.copia:
            self.problemas.append(f'tabela {tabela.nome}: Ligação "{rotulo}" não é uma relação entre {a} e {b} '
                                  f'no modelo conceitual')
        alvos = [self.entidade_de(coluna.fk.tabela) for coluna in tabela.colunas
                 if coluna.fk is not None and coluna.origem == f"relação: {rotulo}"]
        for entidade in dict.fromkeys((a, b)):
            precisa = 2 if a == b else 1
            if alvos.count(entidade) < precisa:
                self.problemas.append(f"tabela {tabela.nome}: Ligação sem FK para uma tabela de {entidade}")

    def nao_persistidos(self) -> None:
        for item in self.modelo.nao_persistidos:
            if item.entidade not in self.conceitual.entidades:
                self.problemas.append(f"Não persistido: entidade {item.entidade} não está no modelo conceitual "
                                      f"({self.caminho_conceitual})")
                continue
            if not item.trecho or self.sem_documento(item.entidade):
                continue
            citado = f"{item.entidade}: {item.trecho}"
            indice = self.casar(f"Não persistido L{item.linha}", item.entidade, item.trecho, citado)
            if indice is not None:
                self.cobertos[item.entidade].add(indice)

    def entidades(self) -> None:
        """Regras 1 e 4."""
        com_tabela = {tabela.entidade for tabela in self.modelo.tabelas if tabela.entidade}
        for entidade in self.conceitual.entidades:
            if entidade not in com_tabela and entidade not in self.dispensadas:
                self.problemas.append(
                    f'entidade {entidade} do modelo conceitual sem tabela: crie a tabela com "Entidade: {entidade} '
                    f'(...)" ou registre "- {entidade}: {ENTIDADE_INTEIRA} — <motivo>" em Não persistido')
        for entidade, fonte in self.fontes.items():
            for indice, (linha, item) in enumerate(fonte.itens):
                if indice not in self.cobertos[entidade]:
                    self.problemas.append(f'entidade {entidade}: atributo sem coluna ({fonte.nome}:L{linha}, '
                                          f'"{_inicio(item)}"): crie a coluna ou registre em Não persistido')

    def relacoes(self) -> None:
        """Regra 2: toda relação sem cópia vira FK com `relação: <rótulo>` ou tabela de ligação."""
        for relacao in self.conceitual.relacoes:
            if relacao.copia or relacao.a in self.dispensadas or relacao.b in self.dispensadas:
                continue
            if any(self.cobre(tabela, relacao) for tabela in self.modelo.tabelas):
                continue
            a, b, r = relacao.a, relacao.b, relacao.rotulo
            self.problemas.append(f'relação "{r}" entre {a} e {b} sem FK nem tabela de ligação: crie a coluna com '
                                  f'a Origem "relação: {r}" ou a tabela com "Ligação: {r} ({a} e {b})"')

    def cobre(self, tabela: Tabela, relacao: Relacao) -> bool:
        par = {relacao.a, relacao.b}
        if tabela.ligacao:
            return tabela.ligacao[0] == relacao.rotulo and {tabela.ligacao[1], tabela.ligacao[2]} == par
        return any(coluna.fk is not None and coluna.origem == f"relação: {relacao.rotulo}"
                   and {tabela.entidade, self.entidade_de(coluna.fk.tabela)} == par for coluna in tabela.colunas)


def rastrear(raiz: Path, perfil: Perfil, modelo: Der, documento: str) -> list[str]:
    """Os problemas das sete regras de spec 5a, §6.7, contra o modelo conceitual e os documentos das entidades.

    Na ordem das tabelas e das colunas, depois os das entidades e das relações. `documento` é relativo à raiz;
    arquivo ausente ou ilegível vira problema, e toda leitura troca `\\r\\n` por `\\n`.
    """
    problemas: list[str] = []
    caminho = f"{perfil.caminhos.planejamento}/{perfil.der.conceitual}"
    texto = _ler_fonte(raiz, caminho, problemas)
    if texto is None:
        return problemas
    rastreio = _Rastreio(raiz, perfil, modelo, documento, conceitual(texto, perfil.der.rotulo_copia))
    rastreio.fonte_das_tabelas()
    for tabela in modelo.tabelas:
        for coluna in tabela.colunas:
            rastreio.coluna(tabela, coluna)
        if tabela.ligacao:
            rastreio.ligacao(tabela)
    rastreio.nao_persistidos()
    rastreio.entidades()
    rastreio.relacoes()
    return rastreio.problemas


def documento_do_perfil(perfil: Perfil) -> str:
    """O documento de `[der]`, relativo à raiz: `<planejamento>/<der.documento>`."""
    if perfil.der is None:
        raise ErroDer("perfil sem a seção [der]")
    return f"{perfil.caminhos.planejamento}/{perfil.der.documento}"


def _pasta_ao_lado(perfil: Perfil, documento: str, chave: str) -> str:
    """A pasta de `[der].<chave>` na mesma posição, em relação a `documento`, que o perfil dá a ela em relação ao
    documento de `[der]` (decisão 9 do plano da 5a)."""
    pasta_do_perfil = posixpath.dirname(documento_do_perfil(perfil))
    alvo = f"{perfil.caminhos.planejamento}/{getattr(perfil.der, chave)}"
    relativo = posixpath.relpath(alvo, pasta_do_perfil)
    return posixpath.normpath(posixpath.join(posixpath.dirname(documento), relativo))


def _do_documento(documento: str, caminho: str) -> str:
    """O caminho relativo à pasta do documento, como as mensagens e o manifesto o citam."""
    return posixpath.relpath(caminho, posixpath.dirname(documento))


def _sem_cr(texto: str) -> str:
    return texto.replace("\r\n", "\n")


def _ler_documento(raiz: Path, documento: str) -> str:
    try:
        return comum.ler_texto(raiz / documento)
    except FileNotFoundError:
        raise ErroDer(f"documento não encontrado: {documento}") from None
    except UnicodeDecodeError:
        raise ErroDer(f"documento não está em UTF-8: {documento}") from None
    except IsADirectoryError:
        raise ErroDer(f"{documento} é uma pasta; passe o arquivo do DER") from None
    except OSError as erro:
        raise ErroDer(f"documento ilegível: {documento} ({erro.strerror or type(erro).__name__})") from None


def documento_relativo(raiz: Path, documento: str) -> str:
    """O documento passado ao comando, relativo à raiz, como o `checar` o mostra: o caminho vale a partir da raiz do
    projeto, não do diretório corrente, ou é absoluto. Fora da raiz lança ErroDer."""
    try:
        return (raiz / documento).resolve().relative_to(raiz.resolve()).as_posix()
    except ValueError:
        raise ErroDer(f"documento fora do projeto: {documento}") from None


def arquivos(raiz: Path, perfil: Perfil, documento: str) -> tuple[dict[str, str], list[str]]:
    """O texto esperado de cada saída, por caminho relativo à raiz, e os erros de formato, `<documento>:L<n>: <motivo>`.

    As saídas são `<sql>/schema.mysql.sql`, `<sql>/schema.<dialeto>.sql` quando o dialeto não é `""` nem `mysql`, e
    o próprio documento com o bloco `erDiagram`. Documento ausente lança ErroDer.
    """
    documento_do_perfil(perfil)
    texto = _ler_documento(raiz, documento)
    modelo, erros = ler(texto)
    if erros:
        return {}, [f"{documento}:{erro}" if erro.startswith("L") and erro[1:2].isdigit() else f"{documento}: {erro}"
                    for erro in erros]
    sql = _pasta_ao_lado(perfil, documento, "sql")
    saidas = {f"{sql}/schema.mysql.sql": ddl(modelo, "mysql", documento)}
    if perfil.der.dialeto not in ("", "mysql"):
        saidas[f"{sql}/schema.{perfil.der.dialeto}.sql"] = ddl(modelo, perfil.der.dialeto, documento)
    saidas[documento] = com_diagrama(texto, modelo)
    return saidas, []


def gerar(raiz: Path, perfil: Perfil, documento: str) -> tuple[list[str], list[str]]:
    """Grava as saídas e devolve as linhas `Gravado:`, ou os erros de formato, sem gravar nada."""
    saidas, erros = arquivos(raiz, perfil, documento)
    if erros:
        return [], erros
    linhas = []
    for caminho, texto in saidas.items():
        comum.escrever_texto(raiz / caminho, texto)
        if caminho == documento:
            linhas.append(f"Gravado: {caminho} (bloco erDiagram)")
        else:
            linhas.append(f"Gravado: {caminho} ({texto.count(chr(10))} linhas)")
    return linhas, []


def conferir(raiz: Path, perfil: Perfil, documento: str) -> list[str]:
    """O que difere entre as saídas geradas em memória e o disco, com `\\r\\n` contado como `\\n`; o formato
    inválido devolve os erros de formato."""
    saidas, erros = arquivos(raiz, perfil, documento)
    if erros:
        return erros
    problemas = []
    for caminho, esperado in saidas.items():
        try:
            atual = _sem_cr(comum.ler_texto(raiz / caminho))
        except FileNotFoundError:
            atual = None
        except (UnicodeDecodeError, OSError):
            atual = ""
        if caminho == documento:
            if atual != _sem_cr(esperado):
                problemas.append("erDiagram editado à mão ou desatualizado; rode harness.py der gerar")
        elif atual is None:
            problemas.append(f"{_do_documento(documento, caminho)} ausente; rode harness.py der gerar")
        elif atual != _sem_cr(esperado):
            problemas.append(f"{_do_documento(documento, caminho)} desatualizado; rode harness.py der gerar")
    return problemas


def _resumo_do_sql(raiz: Path, caminho: str) -> str | None:
    """`sha256:<12 hexadecimais>` do SQL com `\\r\\n` trocado por `\\n`, em UTF-8; None se não dá para ler."""
    try:
        texto = _sem_cr(comum.ler_texto(raiz / caminho))
    except (OSError, UnicodeDecodeError):
        return None
    return "sha256:" + hashlib.sha256(texto.encode("utf-8")).hexdigest()[:12]


def gravar_manifesto(raiz: Path, perfil: Perfil, hoje: str) -> list[str]:
    """Grava `<workbench>/manifesto.txt` e devolve `[]`, ou os problemas, sem gravar.

    O manifesto, com os caminhos relativos à pasta do documento: `sha256:<12> <sql>/schema.mysql.sql`, a data e, um
    por linha, em ordem alfabética, os `.png` e o `workbench.sql` da pasta do Workbench.
    """
    documento = documento_do_perfil(perfil)
    workbench = _pasta_ao_lado(perfil, documento, "workbench")
    pasta = _do_documento(documento, workbench)
    problemas = []
    if conferir(raiz, perfil, documento):
        problemas.append("DER desatualizado; rode harness.py der gerar antes do passo do Workbench")
    pngs = sorted(arquivo.name for arquivo in (raiz / workbench).glob("*.png") if arquivo.is_file())
    if not pngs:
        problemas.append(f"{pasta}/ sem print em PNG; salve os prints do diagrama EER do Workbench")
    if not (raiz / workbench / "workbench.sql").is_file():
        problemas.append(f"falta {pasta}/workbench.sql; exporte com File > Export > Forward Engineer SQL CREATE "
                         f"Script")
    if problemas:
        return problemas
    sql = f"{_pasta_ao_lado(perfil, documento, 'sql')}/schema.mysql.sql"
    linhas = [f"{_resumo_do_sql(raiz, sql)} {_do_documento(documento, sql)}", hoje]
    linhas += [f"{pasta}/{nome}" for nome in sorted(pngs + ["workbench.sql"])]
    comum.escrever_texto(raiz / workbench / "manifesto.txt", "\n".join(linhas) + "\n")
    return []


_RE_LINHA_DO_HASH = re.compile(r"(sha256:[0-9a-f]{12}) (\S+)")
_RE_DATA = re.compile(r"\d{4}-\d{2}-\d{2}")


def conferir_manifesto(raiz: Path, perfil: Perfil) -> list[str]:
    """Recusa o manifesto ausente ou fora do formato, o hash diferente do `schema.mysql.sql` atual e o arquivo
    listado que não existe."""
    documento = documento_do_perfil(perfil)
    workbench = _pasta_ao_lado(perfil, documento, "workbench")
    pasta = _do_documento(documento, workbench)
    try:
        linhas = _sem_cr(comum.ler_texto(raiz / workbench / "manifesto.txt")).splitlines()
    except FileNotFoundError:
        return [f"{pasta}/manifesto.txt ausente; faça o passo do Workbench e rode harness.py der workbench"]
    except (OSError, UnicodeDecodeError):
        linhas = []
    hash_ = _RE_LINHA_DO_HASH.fullmatch(linhas[0]) if linhas else None
    if hash_ is None or len(linhas) < 3 or not _RE_DATA.fullmatch(linhas[1]) or not all(linhas[2:]):
        return [f"{pasta}/manifesto.txt fora do formato; rode harness.py der workbench"]
    problemas = []
    pasta_do_documento = posixpath.dirname(documento)
    sql = posixpath.normpath(posixpath.join(pasta_do_documento, hash_.group(2)))
    if _resumo_do_sql(raiz, sql) != hash_.group(1):
        problemas.append("prints do Workbench feitos de outra versão do DDL; refaça o passo do Workbench")
    for listado in linhas[2:]:
        if not (raiz / pasta_do_documento / listado).is_file():
            problemas.append(f"{listado} listado no manifesto e ausente")
    return problemas


FORMATO_INVALIDO = "formato do DER inválido; corrija o der-formato antes"


def _resultado(nome: str, problemas: list[str], primeira_linha: int | None = None) -> checar.Resultado:
    return checar.Resultado(nome, not problemas, len(problemas), primeira_linha if problemas else None, problemas)


def verificacoes(raiz: Path, perfil: Perfil, relativo: str, texto: str) -> list[checar.Resultado]:
    """As verificações do documento de `[der]` no `checar`: `der-formato`, `der-rastreio`, `der-em-dia` e
    `workbench`. Com o formato inválido, `der-rastreio` e `der-em-dia` falham com uma ocorrência só."""
    modelo, erros = ler(texto)
    linhas = [int(erro[1:erro.index(":")]) for erro in erros if re.match(r"L\d+: ", erro)]
    resultados = [_resultado("der-formato", erros, linhas[0] if linhas else None)]
    if erros:
        resultados += [_resultado("der-rastreio", [FORMATO_INVALIDO]), _resultado("der-em-dia", [FORMATO_INVALIDO])]
    else:
        resultados += [_resultado("der-rastreio", rastrear(raiz, perfil, modelo, relativo)),
                       _resultado("der-em-dia", conferir(raiz, perfil, relativo))]
    resultados.append(_resultado("workbench", conferir_manifesto(raiz, perfil)))
    return resultados
