"""Aplica os DDLs do DER num MySQL e num Postgres de verdade e compara o export do Workbench com o DDL gerado; roda na
CI, com os clientes `mysql` e `psql`.

Uso: `python nucleo/planejamento/ferramentas/bancos.py [raiz]`. Entradas, só as que existem: com `[der]` no perfil da
raiz, os `schema.*.sql` de `[der].sql` e o par do `schema.mysql.sql` com o `workbench.sql` de `[der].workbench`; e, em
`<raiz>/tests/fixtures/der/`, as saídas de referência do gerador (`esperado/`) e o par de `workbench/`, que só a
origem do plugin tem. Sem `.claude/perfil.toml` na raiz, só as fixtures; o
que existir nesse caminho e não for um perfil válido, inclusive pasta ou link quebrado, dá ERRO. Sem nenhuma
entrada, não imprime nada e sai com 0.

Cada SQL roda num banco novo (`harness_<n>`). O `workbench.sql` também, e vale o schema que ele criar, se criar um,
apagado depois da leitura. A comparação lê o `information_schema` dos dois lados: tabelas, colunas com tipo, nulo,
padrão e comentário, chave primária, únicos, FKs com colunas, tabela apontada e regra do `ON DELETE` e índices pelas
colunas. Ela ignora o nome dos índices e das restrições, o nome do schema e o índice não único cujas colunas são as de
uma FK da tabela, que o Workbench escreve e o InnoDB cria sozinho. Os `CHECK` ficam de fora: o modelo do Workbench não
os guarda, e o export sai sem eles; quem os confere é o `schema.mysql.sql` aplicado no MySQL.

Conexão pelas variáveis `MYSQL_HOST`, `MYSQL_TCP_PORT` e `MYSQL_PWD`, com o usuário `root`, e `PGHOST`, `PGUSER` e
`PGPASSWORD`. Uma linha por resultado (`OK:`, `ERRO:` ou `DIFERE:`); sai com 1 se houver ERRO ou DIFERE. Só a
biblioteca padrão; o perfil vem do `perfil.py` do núcleo.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "comum"))

import caminho  # noqa: E402

caminho.no_caminho()

import comum  # noqa: E402
import perfil  # noqa: E402

FIXTURES = Path("tests/fixtures/der")
MYSQL = "schema.mysql.sql"
POSTGRES = "schema.postgres.sql"
WORKBENCH = "workbench.sql"
USUARIO_MYSQL = "root"
VERSAO_MYSQL = "MySQL 8.4"
VERSAO_POSTGRES = "PostgreSQL 18"

# Cada consulta devolve um array JSON, ou NULL sem linhas; `{schema}` é um literal SQL.
CONSULTA_SCHEMAS = "SELECT JSON_ARRAYAGG(SCHEMA_NAME) FROM information_schema.SCHEMATA"
CONSULTA_TABELAS = (
    "SELECT JSON_ARRAYAGG(JSON_OBJECT('tabela', TABLE_NAME, 'comentario', TABLE_COMMENT)) "
    "FROM information_schema.TABLES WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = {schema}"
)
CONSULTA_COLUNAS = (
    "SELECT JSON_ARRAYAGG(JSON_OBJECT('tabela', TABLE_NAME, 'coluna', COLUMN_NAME, 'ordem', ORDINAL_POSITION, "
    "'tipo', COLUMN_TYPE, 'nulo', IS_NULLABLE, 'padrao', COLUMN_DEFAULT, 'comentario', COLUMN_COMMENT)) "
    "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = {schema}"
)
CONSULTA_CHAVES = (
    "SELECT JSON_ARRAYAGG(JSON_OBJECT('tabela', TABLE_NAME, 'coluna', COLUMN_NAME, 'ordem', ORDINAL_POSITION)) "
    "FROM information_schema.KEY_COLUMN_USAGE WHERE CONSTRAINT_NAME = 'PRIMARY' AND TABLE_SCHEMA = {schema}"
)
CONSULTA_UNICOS = (
    "SELECT JSON_ARRAYAGG(JSON_OBJECT('tabela', TABLE_NAME, 'nome', INDEX_NAME, 'coluna', COLUMN_NAME, "
    "'ordem', SEQ_IN_INDEX)) "
    "FROM information_schema.STATISTICS WHERE NON_UNIQUE = 0 AND INDEX_NAME <> 'PRIMARY' AND TABLE_SCHEMA = {schema}"
)
CONSULTA_FKS = (
    "SELECT JSON_ARRAYAGG(JSON_OBJECT('tabela', k.TABLE_NAME, 'nome', k.CONSTRAINT_NAME, 'coluna', k.COLUMN_NAME, "
    "'ordem', k.ORDINAL_POSITION, 'apontada', k.REFERENCED_TABLE_NAME, "
    "'coluna_apontada', k.REFERENCED_COLUMN_NAME, 'regra', r.DELETE_RULE)) "
    "FROM information_schema.KEY_COLUMN_USAGE k JOIN information_schema.REFERENTIAL_CONSTRAINTS r "
    "ON r.CONSTRAINT_SCHEMA = k.CONSTRAINT_SCHEMA AND r.CONSTRAINT_NAME = k.CONSTRAINT_NAME "
    "WHERE k.REFERENCED_TABLE_NAME IS NOT NULL AND k.TABLE_SCHEMA = {schema}"
)
CONSULTA_INDICES = (
    "SELECT JSON_ARRAYAGG(JSON_OBJECT('tabela', TABLE_NAME, 'nome', INDEX_NAME, 'coluna', COLUMN_NAME, "
    "'ordem', SEQ_IN_INDEX)) "
    "FROM information_schema.STATISTICS WHERE NON_UNIQUE = 1 AND TABLE_SCHEMA = {schema}"
)
_PARTES = (
    ("tabelas", CONSULTA_TABELAS),
    ("colunas", CONSULTA_COLUNAS),
    ("chaves", CONSULTA_CHAVES),
    ("unicos", CONSULTA_UNICOS),
    ("fks", CONSULTA_FKS),
    ("indices", CONSULTA_INDICES),
)
_CAMPOS_DA_COLUNA = (("tipo", False), ("nulo", False), ("padrão", True), ("comentário", True))


@dataclass(frozen=True)
class Esquema:
    """O que a comparação vê de um schema, sem os nomes de índice e de restrição."""

    tabelas: dict[str, str]  # comentário
    colunas: dict[tuple[str, str], tuple[str, str, str | None, str]]  # tipo, nulo, padrão, comentário
    chaves: dict[str, tuple[str, ...]]
    unicos: dict[str, frozenset[tuple[str, ...]]]
    fks: dict[str, frozenset[tuple[tuple[str, ...], str, tuple[str, ...], str]]]  # colunas, tabela, apontadas, regra
    indices: dict[str, frozenset[tuple[str, ...]]]  # não únicos, sem os que repetem as colunas de uma FK


class ErroDoCliente(Exception):
    """O `mysql` ou o `psql` saiu com erro; a mensagem é o stderr numa linha."""


def _grupos(linhas: list[dict], campos: tuple[str, ...]) -> dict[tuple, list[dict]]:
    """As linhas agrupadas pelos campos, cada grupo na ordem do campo `ordem`."""
    grupos: dict[tuple, list[dict]] = {}
    for linha in linhas:
        grupos.setdefault(tuple(linha[campo] for campo in campos), []).append(linha)
    return {chave: sorted(grupo, key=lambda linha: linha["ordem"]) for chave, grupo in grupos.items()}


def _membros(linhas: list[dict], campos: tuple[str, ...]) -> dict[tuple, tuple[str, ...]]:
    return {chave: tuple(linha["coluna"] for linha in grupo) for chave, grupo in _grupos(linhas, campos).items()}


def _por_tabela(itens: list[tuple[str, object]]) -> dict[str, frozenset]:
    saida: dict[str, set] = {}
    for tabela, item in itens:
        saida.setdefault(tabela, set()).add(item)
    return {tabela: frozenset(conjunto) for tabela, conjunto in saida.items()}


def montar(linhas: Mapping[str, list[dict]]) -> Esquema:
    """O Esquema a partir das linhas de cada consulta, pelo nome da parte (`tabelas`, `colunas`, `chaves`, `unicos`,
    `fks` e `indices`)."""
    colunas = {
        (linha["tabela"], linha["coluna"]): (linha["tipo"], linha["nulo"], linha["padrao"], linha["comentario"])
        for linha in sorted(linhas["colunas"], key=lambda linha: (linha["tabela"], linha["ordem"]))
    }
    fks = _por_tabela([
        (tabela, (tuple(parte["coluna"] for parte in partes), partes[0]["apontada"],
                  tuple(parte["coluna_apontada"] for parte in partes), partes[0]["regra"]))
        for (tabela, _), partes in _grupos(linhas["fks"], ("tabela", "nome")).items()
    ])
    colunas_de_fk = {(tabela, fk[0]) for tabela, conjunto in fks.items() for fk in conjunto}
    indices = [(tabela, membros) for (tabela, _), membros in _membros(linhas["indices"], ("tabela", "nome")).items()]
    return Esquema(
        tabelas={linha["tabela"]: linha["comentario"] for linha in linhas["tabelas"]},
        colunas=colunas,
        chaves={tabela: membros for (tabela,), membros in _membros(linhas["chaves"], ("tabela",)).items()},
        unicos=_por_tabela([(tabela, membros) for (tabela, _), membros in
                            _membros(linhas["unicos"], ("tabela", "nome")).items()]),
        fks=fks,
        indices=_por_tabela([item for item in indices if item not in colunas_de_fk]),
    )


def _entre_aspas(valor: str | None) -> str:
    return "nenhum" if valor is None else f'"{valor}"'


def _lista(colunas: tuple[str, ...]) -> str:
    return "(" + ", ".join(colunas) + ")"


def _conjunto(tabela: str, rotulo: str, gerado: frozenset, workbench: frozenset) -> list[str]:
    """`tabela <t>: <rótulo> <item> só no gerado`, depois os só no Workbench."""
    return [f"tabela {tabela}: {rotulo} {_lista(item)} só no gerado" for item in sorted(gerado - workbench)] + [
        f"tabela {tabela}: {rotulo} {_lista(item)} só no Workbench" for item in sorted(workbench - gerado)
    ]


def _colunas(gerado: Esquema, workbench: Esquema, tabela: str) -> list[str]:
    nomes = [coluna for (dona, coluna) in gerado.colunas if dona == tabela]
    nomes += [coluna for (dona, coluna) in workbench.colunas if dona == tabela and coluna not in nomes]
    diferencas = []
    for coluna in nomes:
        a, b = gerado.colunas.get((tabela, coluna)), workbench.colunas.get((tabela, coluna))
        if a is None or b is None:
            diferencas.append(f"coluna {tabela}.{coluna} só no {'Workbench' if a is None else 'gerado'}")
            continue
        for (campo, aspas), valor_a, valor_b in zip(_CAMPOS_DA_COLUNA, a, b):
            if valor_a != valor_b:
                mostrar = _entre_aspas if aspas else str
                diferencas.append(
                    f"coluna {tabela}.{coluna}: {campo} {mostrar(valor_a)} no gerado e {mostrar(valor_b)} no Workbench"
                )
    return diferencas


def _fks(gerado: Esquema, workbench: Esquema, tabela: str) -> list[str]:
    """As FKs casadas pelas colunas: a tabela e as colunas apontadas e a regra."""
    de_a = {fk[0]: fk for fk in gerado.fks.get(tabela, frozenset())}
    de_b = {fk[0]: fk for fk in workbench.fks.get(tabela, frozenset())}
    diferencas = []
    for colunas in sorted(de_a.keys() | de_b.keys()):
        nome = f"FK de {tabela}." + (colunas[0] if len(colunas) == 1 else _lista(colunas))
        if colunas not in de_a or colunas not in de_b:
            diferencas.append(f"{nome} só no {'Workbench' if colunas not in de_a else 'gerado'}")
            continue
        _, apontada_a, apontadas_a, regra_a = de_a[colunas]
        _, apontada_b, apontadas_b, regra_b = de_b[colunas]
        if (apontada_a, apontadas_a) != (apontada_b, apontadas_b):
            diferencas.append(
                f"{nome}: aponta para {apontada_a}{_lista(apontadas_a)} no gerado e "
                f"{apontada_b}{_lista(apontadas_b)} no Workbench"
            )
        if regra_a != regra_b:
            diferencas.append(f"{nome}: regra {regra_a} no gerado e {regra_b} no Workbench")
    return diferencas


def comparar(gerado: Esquema, workbench: Esquema) -> list[str]:
    """Uma linha por diferença, tabela a tabela em ordem do nome: a tabela de um lado só, o comentário, as colunas, a
    chave primária, os únicos, as FKs e os índices."""
    diferencas = []
    for tabela in sorted(gerado.tabelas.keys() | workbench.tabelas.keys()):
        if tabela not in gerado.tabelas or tabela not in workbench.tabelas:
            diferencas.append(f"tabela {tabela} só no {'Workbench' if tabela not in gerado.tabelas else 'gerado'}")
            continue
        if gerado.tabelas[tabela] != workbench.tabelas[tabela]:
            diferencas.append(
                f"tabela {tabela}: comentário {_entre_aspas(gerado.tabelas[tabela])} no gerado e "
                f"{_entre_aspas(workbench.tabelas[tabela])} no Workbench"
            )
        diferencas += _colunas(gerado, workbench, tabela)
        chave_a, chave_b = gerado.chaves.get(tabela, ()), workbench.chaves.get(tabela, ())
        if chave_a != chave_b:
            diferencas.append(
                f"tabela {tabela}: chave primária {_lista(chave_a)} no gerado e {_lista(chave_b)} no Workbench"
            )
        vazio: frozenset = frozenset()
        diferencas += _conjunto(tabela, "único", gerado.unicos.get(tabela, vazio), workbench.unicos.get(tabela, vazio))
        diferencas += _fks(gerado, workbench, tabela)
        diferencas += _conjunto(
            tabela, "índice", gerado.indices.get(tabela, vazio), workbench.indices.get(tabela, vazio)
        )
    return diferencas


def entradas(raiz: Path) -> tuple[list[Path], list[Path], list[tuple[Path, Path]]]:
    """Os SQL do MySQL, os do Postgres e os pares (`schema.mysql.sql`, `workbench.sql`), só os que existem: os das
    fixtures do gerador primeiro, depois, com `[der]` no perfil, os do planejamento. Sem nada no caminho do perfil, só
    as fixtures. Lança PerfilInvalido com o que existir ali e não for um perfil válido, inclusive pasta ou link
    quebrado."""
    projeto = perfil.carregar(raiz) if os.path.lexists(raiz / perfil.CAMINHO_PERFIL) else None
    fixtures = raiz / FIXTURES
    pastas = [fixtures / "esperado"]
    pares = [(fixtures / "workbench" / MYSQL, fixtures / "workbench" / WORKBENCH)]
    if projeto is not None and projeto.der is not None:
        planejamento = raiz / projeto.caminhos.planejamento
        pastas.append(planejamento / projeto.der.sql)
        pares.append((planejamento / projeto.der.sql / MYSQL, planejamento / projeto.der.workbench / WORKBENCH))
    return (
        [pasta / MYSQL for pasta in pastas if (pasta / MYSQL).is_file()],
        [pasta / POSTGRES for pasta in pastas if (pasta / POSTGRES).is_file()],
        [(sql, workbench) for sql, workbench in pares if sql.is_file() and workbench.is_file()],
    )


def _numa_linha(texto: str) -> str:
    return " ".join(linha.strip() for linha in texto.splitlines() if linha.strip())


def _literal(nome: str) -> str:
    return "'" + nome.replace("\\", "\\\\").replace("'", "''") + "'"


def _identificador(nome: str) -> str:
    return "`" + nome.replace("`", "``") + "`"


class _Clientes:
    """O `mysql` e o `psql` com o ambiente da conexão, e a contagem dos bancos novos."""

    def __init__(self, executar: Callable, ambiente: Mapping[str, str]):
        self.executar = executar
        self.ambiente = dict(ambiente)
        self.contagem = 0

    def banco_novo(self) -> str:
        self.contagem += 1
        return f"harness_{self.contagem}"

    def mysql(self, *argumentos: str, entrada: str | None = None) -> str:
        comando = ["mysql", f"--user={USUARIO_MYSQL}", "--default-character-set=utf8mb4", *argumentos]
        return self._rodar(comando, entrada)

    def psql(self, *argumentos: str, entrada: str | None = None) -> str:
        return self._rodar(["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", *argumentos], entrada)

    def consultar(self, consulta: str) -> list:
        saida = self.mysql("--batch", "--raw", "--skip-column-names", f"--execute={consulta}").strip()
        return [] if saida in ("", "NULL") else json.loads(saida)

    def _rodar(self, comando: list[str], entrada: str | None) -> str:
        try:
            resultado = self.executar(comando, input=entrada, capture_output=True, encoding="utf-8", env=self.ambiente)
        except OSError as erro:
            raise ErroDoCliente(f"{comando[0]}: {erro}") from erro
        if resultado.returncode != 0:
            raise ErroDoCliente(_numa_linha(resultado.stderr) or f"{comando[0]} saiu com {resultado.returncode}")
        return resultado.stdout


def ler_esquema(clientes: _Clientes, schema: str) -> Esquema:
    literal = _literal(schema)
    return montar({parte: clientes.consultar(consulta.format(schema=literal)) for parte, consulta in _PARTES})


def _aplicar_mysql(clientes: _Clientes, caminho: Path) -> str:
    """Roda o SQL num banco MySQL novo e devolve o nome dele."""
    banco = clientes.banco_novo()
    clientes.mysql(f"--execute=CREATE DATABASE {banco}")
    clientes.mysql(f"--database={banco}", entrada=caminho.read_text(encoding="utf-8"))
    return banco


def _aplicar_postgres(clientes: _Clientes, caminho: Path) -> str:
    banco = clientes.banco_novo()
    clientes.psql("-d", "postgres", "-c", f"CREATE DATABASE {banco}")
    clientes.psql("-d", banco, "-f", "-", entrada=caminho.read_text(encoding="utf-8"))
    return banco


def _aplicar(clientes: _Clientes, raiz: Path, caminho: Path, aplicar: Callable, versao: str) -> str:
    nome = caminho.relative_to(raiz).as_posix()
    try:
        aplicar(clientes, caminho)
    except ErroDoCliente as erro:
        return f"ERRO: {nome}: {erro}"
    return f"OK: {nome} no {versao}"


def _comparar_par(clientes: _Clientes, raiz: Path, sql: Path, workbench: Path) -> list[str]:
    nome_sql, nome_workbench = sql.relative_to(raiz).as_posix(), workbench.relative_to(raiz).as_posix()
    try:
        gerado = ler_esquema(clientes, _aplicar_mysql(clientes, sql))
    except ErroDoCliente as erro:
        return [f"ERRO: {nome_sql}: {erro}"]
    try:
        antes = set(clientes.consultar(CONSULTA_SCHEMAS))
        banco = _aplicar_mysql(clientes, workbench)
        criados = sorted(set(clientes.consultar(CONSULTA_SCHEMAS)) - antes - {banco})
        lido = ler_esquema(clientes, criados[0] if criados else banco)
        for criado in criados:
            clientes.mysql(f"--execute=DROP DATABASE {_identificador(criado)}")
    except ErroDoCliente as erro:
        return [f"ERRO: {nome_workbench}: {erro}"]
    diferencas = comparar(gerado, lido)
    if not diferencas:
        return [f"OK: {nome_workbench} igual ao {nome_sql}, sem os CHECK, que o Workbench não guarda"]
    return [f"DIFERE: {nome_workbench}: {diferenca}" for diferenca in diferencas]


def _resultados(clientes: _Clientes, raiz: Path) -> Iterator[str]:
    try:
        mysql, postgres, pares = entradas(raiz)
    except perfil.PerfilInvalido as erro:
        yield f"ERRO: {perfil.CAMINHO_PERFIL}: {erro}"
        return
    for caminho in mysql:
        yield _aplicar(clientes, raiz, caminho, _aplicar_mysql, VERSAO_MYSQL)
    for caminho in postgres:
        yield _aplicar(clientes, raiz, caminho, _aplicar_postgres, VERSAO_POSTGRES)
    for sql, workbench in pares:
        yield from _comparar_par(clientes, raiz, sql, workbench)


def principal(
    argv: list[str] | None = None, executar: Callable = subprocess.run, ambiente: Mapping[str, str] = os.environ
) -> int:
    """Aplica as entradas e compara os pares, uma linha por resultado; 1 se houver ERRO ou DIFERE."""
    parser = argparse.ArgumentParser(
        prog="bancos.py", description="Aplica os DDLs do DER nos bancos e compara o export do Workbench."
    )
    parser.add_argument("raiz", nargs="?", type=Path, help="raiz do projeto; sem ela, a do harness")
    raiz = parser.parse_args(argv).raiz or comum.raiz_projeto()
    falhou = False
    for linha in _resultados(_Clientes(executar, ambiente), raiz):
        print(linha, flush=True)
        falhou = falhou or not linha.startswith("OK: ")
    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(principal())
