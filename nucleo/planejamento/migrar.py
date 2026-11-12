"""As migrações do projeto entre versões do harness: a leitura delas, as correções de forma e o comando `migrar`.

A correção do item de Aceite citado refaz a citação `<ID>.<n>` de um documento aprovado quando outro documento
renumerou os itens da seção: parte do commit da linha que cita (`git blame`), acha o item `n` de então e o item de
texto igual de hoje. A correção só devolve o texto novo; quem grava é o `migrar`, que abre o lote de migração com os
documentos corrigidos, ou registra a migração direto quando não há o que corrigir.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import backlog
import citacoes
import comum
import estado
import registro
import versao
from campos import _fora_de_blocos, _linhas
from perfil import Perfil

AJUDA = """\
Migra os documentos aprovados para a forma da versão do plugin carregado e registra a migração.

Só no planejamento, fora de um ciclo. Os documentos são os da tabela de artefatos, nas pastas de fase, com o status
`aprovado`; cada um tem de estar no HEAD, sem mudança fora do commit. A versão de partida é a `--de`, ou a da última
linha `migração v<de>→v<para>` da seção de aprovações do arquivo de decisões; a de chegada é a do plugin.

Aplica as correções de forma cuja versão está entre as duas, e as que valem sempre. Hoje há uma, `item-de-aceite`: a
citação `<ID>.<n>` (ou a faixa `<ID>.<n> a <ID>.<m>`) do item de Aceite que outro documento renumerou segue o item de
texto igual de hoje. Sem item igual, ou com mais de um, a citação fica e sai um aviso. A citação por número de linha
não tem correção.

Sem correção, grava `- <data> migração v<de>→v<para>: nada a corrigir` na seção de aprovações do arquivo de decisões e
imprime `nada a corrigir; migração v<de>→v<para> registrada`; se a última migração registrada já chega a `v<para>`, não
grava de novo e imprime `nada a corrigir; migração até v<para> já registrada`. Com correção, grava os textos e abre o
lote de migração com os documentos corrigidos: `Lote: migração v<de>→v<para> (<N> documentos)`, `Passo: 3` e
`Proximo: lote de migração: passo 4, harness.py checar`. O ciclo segue pela `/ela-harness:refinar-documento`, com o critério forma no
revisor. Nos passos 5 e 7 a tabela de artefatos não muda: os documentos seguem `aprovado`, com a data de antes. O
passo 7 grava a linha `- <data> migração v<de>→v<para>: <N> documentos` no arquivo de decisões, e o commit é
`docs(planejamento): migração v<de>→v<para>, <N> documentos`, com `1 documento` no singular, também na linha.

Saída, com 0: uma linha `<documento>: <k> correções (<nome da correção>)` por documento corrigido, uma por aviso e,
com o lote aberto, as linhas `Lote = ...`, `Documento = ...`, `Passo = 3`, `Rodada = 0` e `Proximo = ...`.

Recusas, com 1 e nada gravado, depois de `recusado: `: `ciclo aberto (<Documento>); feche-o antes de migrar`,
`ciclo aberto (pacote de <N> documentos)`, `ciclo aberto (lote <origem>)`;
`nenhuma migração registrada; passe --de v<versão da última atualização>`;
`--de: esperado v<maior>.<menor>.<correção>, encontrado "<texto>"`;
`--de v<versão> é posterior à versão do plugin, v<versão>`; `<documento> tem mudança fora do commit; faça o commit
antes` (`<a>, <b> têm ...` com mais de um); `git indisponível: <motivo>`; `STATUS.md inválido: <motivo>`,
`backlog ilegível: <motivo>`, e as do `estado` e do `registrar aprovacao`.
"""

ORIGEM = "migração v{de}→v{para}"

_TEMPO_LIMITE_GIT = 10
_RE_MIGRACAO = re.compile(r"- (\d{4}-\d{2}-\d{2}) migração v(\d+\.\d+\.\d+)→v(\d+\.\d+\.\d+)")
_RE_VERSAO = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")
_RE_ORIGEM = re.compile(r"migração v(\d+\.\d+\.\d+)→v(\d+\.\d+\.\d+)")
_RE_TITULO_ATE_2 = re.compile(r"#{1,2}\s")


class MigracaoRecusada(Exception):
    """A migração que não pode seguir; `mensagem` é o que se diz ao usuário."""

    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


@dataclass(frozen=True)
class Migracao:
    """Uma migração registrada: a data e as versões, sem o `v`."""
    data: str
    de: str
    para: str


def migracoes(texto_das_decisoes: str) -> list[Migracao]:
    """As linhas `- <AAAA-MM-DD> migração v<de>→v<para>...` da seção que começa por `## Aprovações`, na ordem do
    arquivo. A mesma linha fora da seção não conta."""
    achadas = []
    dentro = False
    for linha in _linhas(texto_das_decisoes):
        if _RE_TITULO_ATE_2.match(linha):
            dentro = linha.startswith("## Aprovações")
        elif dentro and (achado := _RE_MIGRACAO.match(linha)):
            achadas.append(Migracao(*achado.groups()))
    return achadas


def numero_da_versao(texto: str) -> tuple[int, int, int]:
    """`(maior, menor, correção)` de `v0.4.1` ou `0.4.1`. Fora do formato, ValueError."""
    achado = _RE_VERSAO.fullmatch(texto.strip())
    if achado is None:
        raise ValueError(f"versão fora do formato: {texto!r}")
    return int(achado.group(1)), int(achado.group(2)), int(achado.group(3))


def _git(raiz: Path, argumentos: list[str], executar) -> subprocess.CompletedProcess:
    try:
        return executar(["git", "-C", str(raiz), *argumentos], capture_output=True, timeout=_TEMPO_LIMITE_GIT)
    except (OSError, subprocess.SubprocessError) as erro:
        raise MigracaoRecusada(f"git indisponível: {erro}") from None


def _commit_da_linha(raiz: Path, documento: str, linha: int, executar) -> str | None:
    """O commit da linha no HEAD, ou None sem blame (linha fora do HEAD, ou ainda sem commit)."""
    feito = _git(raiz, ["blame", "--porcelain", "-L", f"{linha},{linha}", "HEAD", "--", documento], executar)
    if feito.returncode != 0:
        return None
    primeira = feito.stdout.decode("utf-8", errors="replace").split("\n", 1)[0].split()
    if not primeira or set(primeira[0]) == {"0"}:
        return None
    return primeira[0]


def _itens_no_commit(raiz: Path, commit: str, documento: str, id_: str, executar) -> list[tuple[int, str]] | None:
    """Os itens da seção `id_` do documento no commit, ou None sem o documento ali."""
    feito = _git(raiz, ["show", f"{commit}:./{documento}"], executar)
    if feito.returncode != 0:
        return None
    texto = feito.stdout.decode("utf-8", errors="replace").replace("\r", "")
    return citacoes.secoes_com_itens(texto).get(id_, (0, []))[1]


def corrigir_itens_de_aceite(raiz: Path, aprovados: list[str], executar) -> tuple[dict[str, str], dict[str, int],
                                                                                   list[str]]:
    """O texto novo e o número de correções de cada documento aprovado que mudou, e os avisos.

    Cada citação `<ID>.<n>` (ou faixa `<ID>.<n> a <ID>.<m>`) fora de bloco de código segue o item `n` do commit da
    linha que cita até o item de texto igual de hoje no documento dono do ID. Sem item igual, ou com mais de um, a
    citação fica e sai o aviso. A faixa só muda com as duas pontas certas e em ordem. Git que falha lança
    MigracaoRecusada."""
    textos: dict[str, str] = {}
    dono: dict[str, str] = {}
    hoje: dict[str, list[tuple[int, str]]] = {}
    for documento in aprovados:
        try:
            textos[documento] = comum.ler_texto(raiz / documento)
        except (OSError, UnicodeDecodeError):
            continue
        for id_, (_, itens) in citacoes.secoes_com_itens(textos[documento]).items():
            if id_ not in dono:
                dono[id_] = documento
                hoje[id_] = itens
    if not dono:
        return {}, {}, []
    padrao = citacoes.padrao_de_citacoes(list(dono))
    blames: dict[tuple[str, int], str | None] = {}
    antigos: dict[tuple[str, str, str], list[tuple[int, str]] | None] = {}

    def novo_numero(documento: str, linha: int, id_: str, numero: int) -> int | None:
        """O número de hoje do item `numero` de então, ou None sem item igual ou com mais de um."""
        if (documento, linha) not in blames:
            blames[(documento, linha)] = _commit_da_linha(raiz, documento, linha, executar)
        commit = blames[(documento, linha)]
        if commit is None:
            return None
        chave = (commit, dono[id_], id_)
        if chave not in antigos:
            antigos[chave] = _itens_no_commit(raiz, commit, dono[id_], id_, executar)
        itens_de_entao = antigos[chave] or []
        if not 1 <= numero <= len(itens_de_entao):
            return None
        texto_de_entao = itens_de_entao[numero - 1][1]
        iguais = [n for n, (_, texto) in enumerate(hoje[id_], start=1) if texto == texto_de_entao]
        return iguais[0] if len(iguais) == 1 else None

    novos: dict[str, str] = {}
    contagens: dict[str, int] = {}
    avisos: list[str] = []
    for documento in aprovados:
        if documento not in textos:
            continue
        linhas = textos[documento].split("\n")
        feitas = 0
        for numero_da_linha, linha in _fora_de_blocos(_linhas(textos[documento])):
            trocas: list[tuple[int, int, str]] = []
            for achado in padrao.finditer(linha):
                id_ = achado.group(1)
                if dono[id_] == documento:
                    continue
                inicio = int(achado.group(2))
                if achado.group(3) is None:
                    m = novo_numero(documento, numero_da_linha, id_, inicio)
                    if m is None:
                        avisos.append(f"{documento}:L{numero_da_linha}: {achado.group(0)} sem item igual hoje em "
                                      f"{dono[id_]}; confira na revisão dele")
                    elif m != inicio:
                        trocas.append((achado.start(2), achado.end(2), str(m)))
                        feitas += 1
                    continue
                fim = int(achado.group(3))
                m_inicio = novo_numero(documento, numero_da_linha, id_, inicio)
                m_fim = novo_numero(documento, numero_da_linha, id_, fim)
                if m_inicio is None or m_fim is None or m_inicio > m_fim:
                    avisos.append(f"{documento}:L{numero_da_linha}: {achado.group(0)} não se corrige sozinha; "
                                  "confira na revisão dele")
                elif (m_inicio, m_fim) != (inicio, fim):
                    trocas.append((achado.start(2), achado.end(2), str(m_inicio)))
                    trocas.append((achado.start(3), achado.end(3), str(m_fim)))
                    feitas += 1
            if trocas:
                nova = linhas[numero_da_linha - 1]
                for inicio, fim, texto in sorted(trocas, reverse=True):
                    nova = nova[:inicio] + texto + nova[fim:]
                linhas[numero_da_linha - 1] = nova
        if feitas:
            novos[documento] = "\n".join(linhas)
            contagens[documento] = feitas
    return novos, contagens, avisos


@dataclass(frozen=True)
class Correcao:
    """Uma correção de forma: o nome, a versão desde a qual vale (None: vale sempre) e a função que a aplica."""
    nome: str
    desde: str | None
    aplicar: Callable


CORRECOES = (Correcao("item-de-aceite", None, corrigir_itens_de_aceite),)


def migracao_da_origem(origem: str) -> tuple[str, str] | None:
    """`(de, para)` da origem `migração v<de>→v<para>` do campo `Lote`, sem o `v`, ou None em outra origem."""
    achado = _RE_ORIGEM.fullmatch(origem)
    return achado.groups() if achado else None


@dataclass(frozen=True)
class Migrado:
    """O que o `migrar` fez: as versões, as linhas da saída e os documentos do lote (vazio sem correção)."""
    de: str
    para: str
    linhas: tuple[str, ...]
    documentos: tuple[str, ...]


def _ciclo_aberto(raiz: Path, perfil: Perfil) -> str | None:
    """O que o STATUS.md tem aberto (lote, pacote ou documento), para a recusa, ou None sem ciclo."""
    try:
        dados = estado.ler(raiz / perfil.caminhos.status, perfil)
        if estado.CAMPO_LOTE in dados:
            return f"lote {estado.origem_do_lote(dados[estado.CAMPO_LOTE])}"
        if estado.CAMPO_PACOTE in dados:
            quantos = len(estado.documentos(dados, raiz))
            return f"pacote de {quantos} documento{'' if quantos == 1 else 's'}"
    except estado.EstadoInvalido as erro:
        raise MigracaoRecusada(f"STATUS.md inválido: {erro.mensagem}") from None
    return None if dados["Documento"] == estado.SEM_DOCUMENTO else dados["Documento"]


def _de(raiz: Path, perfil: Perfil, de: str | None) -> str:
    """A versão de partida: a `--de`, conferida, ou a da última migração registrada."""
    if de is not None:
        try:
            numero_da_versao(de)
        except ValueError:
            raise MigracaoRecusada(f'--de: esperado v<maior>.<menor>.<correção>, encontrado "{de}"') from None
        return de.strip().removeprefix("v")
    try:
        registradas = migracoes(comum.ler_texto(raiz / perfil.caminhos.decisoes))
    except (OSError, UnicodeDecodeError):
        registradas = []
    if not registradas:
        raise MigracaoRecusada("nenhuma migração registrada; passe --de v<versão da última atualização>")
    return registradas[-1].para


def _registrada_ate(raiz: Path, perfil: Perfil, para: str) -> bool:
    """Se a última migração registrada no arquivo de decisões já chega a `para`."""
    try:
        registradas = migracoes(comum.ler_texto(raiz / perfil.caminhos.decisoes))
    except (OSError, UnicodeDecodeError):
        return False
    return bool(registradas) and registradas[-1].para == para


def _aprovados(raiz: Path, perfil: Perfil) -> list[str]:
    """Os documentos aprovados das pastas de fase, na ordem das fases e da tabela de artefatos."""
    try:
        texto = backlog.ler(raiz / perfil.caminhos.backlog)
    except backlog.BacklogIlegivel as erro:
        raise MigracaoRecusada(f"backlog ilegível: {erro.mensagem}") from None
    achados = []
    for fase in perfil.fases:
        pasta = f"{perfil.caminhos.planejamento.rstrip('/')}/{fase.id}"
        achados += [caminho for _, caminho, status in backlog.artefatos_da_pasta(texto, pasta)
                    if status.startswith("aprovado")]
    return achados


def _plural(quantos: int, singular: str, plural: str) -> str:
    return f"{quantos} {singular if quantos == 1 else plural}"


def migrar(
    raiz: Path, perfil: Perfil, de: str | None, para: str, executar=subprocess.run, hoje: str | None = None
) -> Migrado:
    """Migra os documentos aprovados de `de` (ou da última migração registrada) até `para`.

    Recusa com MigracaoRecusada, sem gravar, o ciclo aberto, a versão de partida ausente, fora do formato ou posterior
    à de chegada, o aprovado com mudança fora do commit e o git indisponível. Aplica as correções do `CORRECOES` cuja
    versão está entre as duas (ou vale sempre) e grava os textos; havendo correção, abre o lote de migração com os
    documentos corrigidos (se o STATUS.md recusar, os textos voltam ao que eram); sem correção, só registra a migração
    no arquivo de decisões."""
    aberto = _ciclo_aberto(raiz, perfil)
    if aberto is not None:
        raise MigracaoRecusada(f"ciclo aberto ({aberto}); feche-o antes de migrar")
    de = _de(raiz, perfil, de)
    if numero_da_versao(de) > numero_da_versao(para):
        raise MigracaoRecusada(f"--de v{de} é posterior à versão do plugin, v{para}")
    aprovados = _aprovados(raiz, perfil)
    try:
        fora = versao.no_head(raiz, aprovados, executar).fora_do_commit
    except versao.VersaoInvalida as erro:
        raise MigracaoRecusada(erro.mensagem) from None
    if fora:
        raise MigracaoRecusada(f"{', '.join(fora)} {'tem' if len(fora) == 1 else 'têm'} mudança fora do commit; "
                               "faça o commit antes")
    novos: dict[str, str] = {}
    nomes: dict[str, list[str]] = {}
    contagens: dict[str, int] = {}
    avisos: list[str] = []
    for correcao in CORRECOES:
        if correcao.desde is not None and not (
            numero_da_versao(de) < numero_da_versao(correcao.desde) <= numero_da_versao(para)
        ):
            continue
        textos, feitas, dos_avisos = correcao.aplicar(raiz, aprovados, executar)
        novos.update(textos)
        for documento, quantas in feitas.items():
            contagens[documento] = contagens.get(documento, 0) + quantas
            nomes.setdefault(documento, []).append(correcao.nome)
        avisos += dos_avisos
    corrigidos = [documento for documento in aprovados if documento in novos]
    linhas = [f"{documento}: {_plural(contagens[documento], 'correção', 'correções')} ({', '.join(nomes[documento])})"
              for documento in corrigidos] + avisos
    origem = ORIGEM.format(de=de, para=para)
    if not corrigidos:
        if _registrada_ate(raiz, perfil, para):
            return Migrado(de, para, (*linhas, f"nada a corrigir; migração até v{para} já registrada"), ())
        try:
            registro.aprovacao(raiz, perfil, f"{origem}: nada a corrigir", hoje)
        except registro.RegistroRecusado as erro:
            raise MigracaoRecusada(erro.mensagem) from None
        return Migrado(de, para, (*linhas, f"nada a corrigir; {origem} registrada"), ())
    antigos = {documento: comum.ler_texto(raiz / documento) for documento in corrigidos}
    try:
        for documento in corrigidos:
            comum.escrever_texto(raiz / documento, novos[documento])
        proximo = "lote de migração: passo 4, harness.py checar"
        estado.definir_lote(raiz / perfil.caminhos.status, raiz, origem, corrigidos, perfil,
                            {"Passo": "3", "Rodada": "0", "Proximo": proximo}, hoje)
    except (estado.EstadoInvalido, OSError) as erro:
        for documento, texto in antigos.items():
            comum.escrever_texto(raiz / documento, texto)
        raise MigracaoRecusada(erro.mensagem if isinstance(erro, estado.EstadoInvalido) else str(erro)) from None
    linhas += [f"{estado.CAMPO_LOTE} = {estado.valor_do_lote(origem, len(corrigidos))}",
               f"Documento = {corrigidos[0]}", "Passo = 3", "Rodada = 0", f"Proximo = {proximo}"]
    return Migrado(de, para, tuple(linhas), tuple(corrigidos))
