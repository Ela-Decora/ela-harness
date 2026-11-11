"""Ponto de entrada do harness: monta os comandos pela trilha do perfil e despacha cada um para o módulo de uma das
três pastas do núcleo."""
from __future__ import annotations

import caminho

caminho.no_caminho()

import argparse
import datetime
import importlib
import json
import os
import re
import shutil
import sys
import types
from pathlib import Path

import aceitacao
import backlog
import bloco
import checar
import comum
import contexto
import der
import estado
import estudos
import fichas
import gerador
import guarda
import importacao
import iniciar
import instalacao_ci
import invariantes
import lane
import lanes
import legenda
import linear
import papeis
import perfil_comum
import perfil_desenvolvimento
import prepush
import retorno
import revisao
import transicoes
import verificacao
import versao
# O módulo `perfil` entra pelos nomes: `perfil` é o nome da variável do perfil carregado nas funções abaixo.
from perfil import AJUDA as AJUDA_DO_PERFIL, Perfil, PerfilInvalido, carregar as carregar_perfil


def _do_planejamento(nome: str) -> types.ModuleType | None:
    """Carrega um módulo só do planejamento. Sem o arquivo na pasta (o repositório de código não o recebe), devolve
    `None`; a falta de outro módulo, dentro dele, sobe."""
    try:
        return importlib.import_module(nome)
    except ModuleNotFoundError as erro:
        if erro.name == nome:
            return None
        raise


ambiente = _do_planejamento("ambiente")
blocos = _do_planejamento("blocos")
dossie = _do_planejamento("dossie")
fechamento = _do_planejamento("fechamento")
gate = _do_planejamento("gate")
passagem = _do_planejamento("passagem")
passo = _do_planejamento("passo")
proximo = _do_planejamento("proximo")
rastreio = _do_planejamento("rastreio")
referencia = _do_planejamento("referencia")
registro = _do_planejamento("registro")
sessao = _do_planejamento("sessao")


class UsoInvalido(Exception):
    """Erro de uso da linha de comando, no lugar da saída com código 2 e várias linhas do argparse."""


class _Formatador(argparse.RawDescriptionHelpFormatter):
    """Formatador da ajuda: mantém as quebras da descrição e abre o uso com `uso: `."""

    def add_usage(self, usage, actions, groups, prefix=None):
        # O argparse passa `""` ao montar o `prog` dos subparsers; esse fica como está.
        super().add_usage(usage, actions, groups, "uso: " if prefix is None else prefix)


class _Parser(argparse.ArgumentParser):
    """Parser com a ajuda em português que lança UsoInvalido em vez de imprimir o uso no stderr e sair com 2."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("formatter_class", _Formatador)
        # Sem abreviação: `--envi` não vira `--enviar` (spec 6c, §6.4); os subparsers herdam pelo `parser_class`.
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, add_help=False, **kwargs)
        self._positionals.title = "argumentos"
        self._optionals.title = "opções"
        self.add_argument(
            "-h", "--help", action="help", default=argparse.SUPPRESS, help="mostra esta ajuda e sai"
        )

    def error(self, message: str):
        raise UsoInvalido(message)


def _uma_linha(texto: str) -> str:
    """Troca quebras de linha por `\\n` e `\\r` escritos, para a saída do script ficar numa linha só."""
    return texto.replace("\r", "\\r").replace("\n", "\\n")


def _projeto() -> tuple[Path, Perfil]:
    """Raiz dos comandos e o perfil validado. RaizNaoEncontrada e PerfilInvalido sobem até `principal`."""
    raiz = comum.raiz_dos_comandos()
    return raiz, carregar_perfil(raiz)


def _projeto_de_codigo() -> tuple[Path, perfil_desenvolvimento.PerfilDesenvolvimento]:
    """Raiz dos comandos e o perfil de desenvolvimento validado. PerfilInvalido sobe até `principal`."""
    raiz = comum.raiz_dos_comandos()
    return raiz, perfil_desenvolvimento.carregar(raiz)


def _documentos_pedidos(raiz: Path, perfil: Perfil, argumentos: list[str]) -> list[str] | None:
    """Os documentos dos argumentos, sem repetição; sem argumento, os em refino do STATUS.md (o `Pacote`, ou o
    `Documento`). Sem documento, imprime o motivo numa linha e devolve None."""
    if argumentos:
        return list(dict.fromkeys(argumentos))
    try:
        documentos = estado.documentos(estado.ler(raiz / perfil.caminhos.status, perfil))
    except estado.EstadoInvalido as erro:
        print("STATUS.md inválido: " + _uma_linha(erro.mensagem))
        return None
    if not documentos:
        print("sem documento: passe o caminho ou abra um no STATUS.md")
        return None
    return documentos


def _comando_estado_hook(args: argparse.Namespace) -> int:
    """Imprime o JSON do SessionStart (spec 4a, §8.1), com o payload do stdin quando ele não é um terminal; sai
    sempre com 0."""
    entrada = ""
    try:
        if sys.stdin is not None and not sys.stdin.isatty():
            entrada = comum.ler_entrada()
    except Exception:  # stdin ilegível vale vazio: a fonte fica startup
        entrada = ""
    sys.stdout.write(sessao.rodar(entrada) + "\n")
    return 0


def _comando_estado(args: argparse.Namespace) -> int:
    """Imprime o STATUS.md validado, em texto canônico; inválido imprime o motivo e sai com 1.

    Com `--hook`, imprime no lugar o JSON do SessionStart (sempre com saída 0).
    """
    if args.hook:
        return _comando_estado_hook(args)
    raiz, perfil = _projeto()
    try:
        dados = estado.ler(raiz / perfil.caminhos.status, perfil)
    except estado.EstadoInvalido as erro:
        print("STATUS.md inválido: " + "; ".join(erro.erros))
        return 1
    sys.stdout.write(estado.formatar(dados, perfil))
    return 0


def _comando_estado_set(args: argparse.Namespace) -> int:
    """Muda um campo do STATUS.md. Recusado imprime o motivo, numa linha, e sai com 1; o arquivo fica intacto.

    `Versao-aprovacao` não muda por aqui: só por `versao marcar`, `versao limpar`, `passo 6` ou `fechar`.
    """
    if args.campo == "Versao-aprovacao":
        print("recusado: Versao-aprovacao muda só por versao marcar, versao limpar, passo 6 ou fechar")
        return 1
    raiz, perfil = _projeto()
    try:
        automaticas = estado.definir(raiz / perfil.caminhos.status, args.campo, args.valor, perfil)
    except estado.EstadoInvalido as erro:
        print("recusado: " + _uma_linha(erro.mensagem))
        return 1
    print(f"{args.campo} = {args.valor}")
    for campo, valor in automaticas.items():
        print(f"{campo} = {valor}")
    return 0


def _comando_backlog_ids(args: argparse.Namespace) -> int:
    """Confere os IDs de pendência do backlog. Sem erro imprime os totais; com erro, um por linha, e sai com 1."""
    raiz, perfil = _projeto()
    try:
        texto = backlog.ler(raiz / perfil.caminhos.backlog)
    except backlog.BacklogIlegivel as erro:
        print("backlog.md ilegível: " + _uma_linha(erro.mensagem))
        return 1
    erros = backlog.conferir_ids(texto, perfil)
    if erros:
        for erro in erros:
            print(erro)
        return 1
    total = len(backlog.linhas_de_pendencia(texto, perfil))
    print(f"OK: {total} pendências, {backlog.contar_abertas(texto, perfil)} abertas")
    return 0


def _comando_backlog_resolver(args: argparse.Namespace) -> int:
    """Marca uma pendência aberta como resolvida, trocando só a célula de status. Recusa sai com 1, sem gravar
    nada."""
    raiz, perfil = _projeto()
    try:
        linha, id_ = registro.resolver_pendencia(raiz, perfil, args.id, args.em, args.como)
    except registro.RegistroRecusado as erro:
        return _recusar_registro(erro)
    except OSError as erro:
        return _recusar_versao(erro)
    print(f"{id_} resolvida em {perfil.caminhos.backlog}:{linha}")
    return 0


def _comando_checar(args: argparse.Namespace) -> int:
    """Confere cada documento contra o molde (passo 4 do ciclo); sem argumento, os em refino do STATUS.md. Com mais de
    um, a linha `== <documento>` abre o bloco de cada um. Sai com 1 se alguma verificação falha, menos `a-confirmar`."""
    raiz, perfil = _projeto()
    documentos = _documentos_pedidos(raiz, perfil, args.documentos)
    if documentos is None:
        return 1
    falhou = False
    for documento in documentos:
        if len(documentos) > 1:
            print(f"== {documento}")
        try:
            resultados = checar.checar_arquivo(raiz, Path(documento), perfil)
        except checar.EntradaInvalida as erro:
            print(_uma_linha(erro.mensagem))
            falhou = True
            continue
        sys.stdout.write(checar.formatar_resultados(resultados, args.verbose))
        falhou = falhou or not all(resultado.ok for resultado in resultados)
    return 1 if falhou else 0


def _comando_molde(args: argparse.Namespace) -> int:
    """Imprime o molde do documento, relativo à raiz, para o passo 0 copiá-lo. Sai com 1 sem molde."""
    raiz, perfil = _projeto()
    try:
        molde = checar.resolver_molde(raiz, Path(args.documento), perfil)
    except checar.EntradaInvalida as erro:
        print(_uma_linha(erro.mensagem))
        return 1
    if not molde.is_file():
        print(_uma_linha(f"molde não encontrado: {checar.mostrar(raiz, molde)}"))
        return 1
    print(_uma_linha(checar.mostrar(raiz, molde)))
    return 0


def _documento_do_der(args: argparse.Namespace, raiz: Path, perfil: Perfil) -> str:
    return der.documento_relativo(raiz, args.documento) if args.documento else der.documento_do_perfil(perfil)


def _comando_der_gerar(args: argparse.Namespace) -> int:
    """Grava o DDL e o bloco erDiagram do DER; com o formato inválido, imprime os erros e sai com 1."""
    raiz, perfil = _projeto()
    try:
        linhas, erros = der.gerar(raiz, perfil, _documento_do_der(args, raiz, perfil))
    except der.ErroDer as erro:
        print(_uma_linha(erro.mensagem))
        return 1
    for linha in linhas or erros:
        print(_uma_linha(linha))
    return 1 if erros else 0


def _comando_der_conferir(args: argparse.Namespace) -> int:
    """Compara o DDL e o bloco gerados em memória com o disco."""
    raiz, perfil = _projeto()
    try:
        problemas = der.conferir(raiz, perfil, _documento_do_der(args, raiz, perfil))
    except der.ErroDer as erro:
        print(_uma_linha(erro.mensagem))
        return 1
    for problema in problemas or ["OK: DER em dia"]:
        print(_uma_linha(problema))
    return 1 if problemas else 0


def _comando_der_workbench(args: argparse.Namespace) -> int:
    """Grava o manifesto do Workbench, que amarra os prints e o SQL exportado à versão do DDL."""
    raiz, perfil = _projeto()
    try:
        problemas = der.gravar_manifesto(raiz, perfil, datetime.date.today().isoformat())
    except der.ErroDer as erro:
        print(_uma_linha(erro.mensagem))
        return 1
    if problemas:
        for problema in problemas:
            print(_uma_linha(problema))
        return 1
    manifesto = f"{perfil.caminhos.planejamento}/{perfil.der.workbench}/manifesto.txt"
    arquivos = len(comum.ler_texto(raiz / manifesto).splitlines()) - 2
    print(f"Gravado: {manifesto} ({arquivos} arquivos)")
    return 0


def _recusar_versao(erro: Exception) -> int:
    """Uma linha de motivo para o que `versao` recusa ou não consegue ler e gravar; sai com 1."""
    if isinstance(erro, estado.EstadoInvalido):
        print("recusado: " + _uma_linha(erro.mensagem))
    elif isinstance(erro, OSError):
        detalhe = erro.strerror or type(erro).__name__
        arquivo = f" ({erro.filename})" if erro.filename else ""
        print("erro de arquivo: " + _uma_linha(detalhe + arquivo))
    else:
        print(_uma_linha(erro.mensagem))
    return 1


def _comando_versao_marcar(args: argparse.Namespace) -> int:
    """Grava o hash da versão em aprovação no STATUS.md e guarda uma cópia. Recusa imprime o motivo e sai com 1."""
    raiz, perfil = _projeto()
    try:
        marcado = versao.marcar(raiz, Path(args.documento) if args.documento is not None else None, perfil)
    except (versao.VersaoInvalida, estado.EstadoInvalido, OSError) as erro:
        return _recusar_versao(erro)
    print(f"{versao.CAMPO} = {marcado}")
    return 0


def _comando_versao_conferir(args: argparse.Namespace) -> int:
    """Diz se o documento ainda é a versão marcada. Sai com 1 se mudou ou se não há como conferir."""
    raiz, perfil = _projeto()
    try:
        confere, mensagem = versao.conferir(raiz, Path(args.documento) if args.documento is not None else None, perfil)
    except (versao.VersaoInvalida, estado.EstadoInvalido, OSError) as erro:
        return _recusar_versao(erro)
    print(mensagem)
    return 0 if confere else 1


def _comando_versao_limpar(args: argparse.Namespace) -> int:
    """Desfaz a marcação: `Versao-aprovacao` volta para `—`, e a cópia e o histórico são apagados."""
    raiz, perfil = _projeto()
    try:
        versao.limpar(raiz, perfil)
    except (estado.EstadoInvalido, OSError) as erro:
        return _recusar_versao(erro)
    print(f"{versao.CAMPO} = {versao.SEM_VERSAO}")
    return 0


def _comando_versao_historico(args: argparse.Namespace) -> int:
    """Lista as versões marcadas do documento (padrão: o do STATUS.md), com a contagem de linhas contra a anterior."""
    raiz, perfil = _projeto()
    documento = Path(args.documento) if args.documento is not None else None
    try:
        relativo, entradas = versao.historico(raiz, perfil, documento)
    except (versao.VersaoInvalida, estado.EstadoInvalido, OSError) as erro:
        return _recusar_versao(erro)
    sys.stdout.write(versao.formatar_historico(relativo, entradas))
    return 0


def _comando_versao_diff(args: argparse.Namespace) -> int:
    """Diff entre duas versões do histórico. Recusa (número inexistente, menos de duas versões) sai com 1."""
    raiz, perfil = _projeto()
    documento = Path(args.documento) if args.documento is not None else None
    try:
        texto = versao.diff_do_historico(raiz, perfil, args.n, args.m, args.completo, documento)
    except versao.VersaoInvalida as erro:
        print("recusado: " + _uma_linha(erro.mensagem))
        return 1
    except (estado.EstadoInvalido, OSError) as erro:
        return _recusar_versao(erro)
    sys.stdout.write(texto)
    return 0


def _comando_passo(args: argparse.Namespace) -> int:
    """Fecha um passo do ciclo: grava o STATUS.md e, nos passos 5 e 7, o status do artefato. Recusa sai com 1."""
    raiz, perfil = _projeto()
    try:
        gravado = passo.fechar(raiz, perfil, args.numero, args.proximo, args.rodada)
    except passo.PassoRecusado as erro:
        print("recusado: " + _uma_linha(erro.mensagem))
        for linha in erro.detalhes:
            print(linha)
        return 1
    except OSError as erro:
        return _recusar_versao(erro)
    print("; ".join(f"{campo} = {valor}" for campo, valor in gravado.campos.items()))
    for caminho, status, data in gravado.artefatos:
        print(f"backlog: {caminho} = {status} em {data}")
    if gravado.prova:
        print(f"prova: {gravado.prova}")
    return 0


def _comando_perfil(args: argparse.Namespace) -> int:
    """Sem `--para`, imprime o resumo do perfil validado; perfil inválido sai com 1 por `principal`.

    Com `--para <skill>`, imprime o bloco "Este projeto" da skill e sai sempre com 0: a skill injeta a saída
    com `!`, e um código diferente de 0 abortaria a invocação. Qualquer erro vira a primeira linha, `ERRO: ...`.
    Bloco acima do teto da skill (`blocos.limite`) sai inteiro, com um aviso na primeira linha.
    """
    if args.para is None:
        _, perfil = _projeto()
        sys.stdout.write(blocos.resumo(perfil))
        return 0
    try:
        raiz, perfil = _projeto()
        texto = blocos.bloco(perfil, args.para, raiz)
    except (comum.RaizNaoEncontrada, PerfilInvalido, blocos.SkillDesconhecida, blocos.ForaDaFase) as erro:
        print("ERRO: " + _uma_linha(str(erro)))
        return 0
    except estado.EstadoInvalido as erro:
        print("ERRO no STATUS.md: " + _uma_linha(erro.mensagem))
        return 0
    except Exception as erro:  # a injeção não pode abortar a invocação da skill
        print(f"ERRO: {type(erro).__name__}: {_uma_linha(str(erro))}")
        return 0
    teto = blocos.limite(args.para)
    if len(texto) > teto:
        print(f"AVISO: bloco com {len(texto)} caracteres, acima de {teto}")
    sys.stdout.write(texto)
    return 0


def _comando_gate(args: argparse.Namespace) -> int:
    """Roda os itens de script do checklist do gate e termina com a assinatura das entradas do revisor.

    Sai com 0 só sem FAIL; pré-condição falha sai com 1, numa linha, sem assinatura.
    """
    raiz, perfil = _projeto()
    try:
        resultados = gate.rodar(raiz, perfil, args.gate)
        assinatura = gate.assinatura(raiz, perfil, args.gate)
    except gate.PreCondicao as erro:
        print(_uma_linha(erro.mensagem))
        return 1
    sys.stdout.write(gate.formatar(resultados, perfil.gates[args.gate], args.verbose))
    print(f"Assinatura: {assinatura}")
    return 1 if any(resultado.situacao == gate.FAIL for resultado in resultados) else 0


def _comando_legenda(args: argparse.Namespace) -> int:
    """Gera a legenda pela cópia de trabalho e a grava; com `--check`, só compara. Recusa e diferença saem com 1."""
    raiz, perfil = _projeto()
    caminho = perfil.caminhos.legenda
    if not caminho:
        print("erro: perfil sem caminhos.legenda")
        return 1
    try:
        texto = legenda.gerar(comum.leitor_do_disco(raiz), perfil)
    except legenda.LegendaRecusada as erro:
        for motivo in erro.motivos:
            print(motivo)
        return 1
    if args.check:
        try:
            igual = (raiz / caminho).read_bytes() == texto.encode("utf-8")
        except OSError:
            igual = False
        if not igual:
            print("legenda desatualizada: rode harness.py legenda")
            return 1
        print(f"legenda em dia: {caminho}")
        return 0
    try:
        comum.escrever_texto(raiz / caminho, texto)
    except OSError as erro:
        return _recusar_versao(erro)
    print(f"Gravado: {caminho} ({len(texto.splitlines())} linhas)")
    return 0


def _comando_passagem_exportar(args: argparse.Namespace) -> int:
    """Exporta a passagem do commit para uma pasta nova ou vazia, fora de árvore git. Recusa sai com 1, sem gravar;
    aviso sai com 0."""
    raiz, perfil = _projeto()
    pasta = Path(args.pasta)
    try:
        passagem.conferir_perfil(perfil)
        passagem.conferir_pasta(pasta)
        exportacao = passagem.calcular(raiz, perfil, args.ref or "HEAD")
    except passagem.ErroPassagem as erro:
        print(f"erro: {_uma_linha(erro.mensagem)}")
        return 1
    if exportacao.recusas:
        for recusa in exportacao.recusas:
            print(recusa)
        return 1
    try:
        passagem.gravar(exportacao, pasta)
    except OSError as erro:
        print(f"erro: {comum.motivo_do_sistema(erro)}")
        return 1
    print(passagem.resumo(exportacao, pasta))
    for aviso in exportacao.avisos:
        print(f"aviso: {aviso}")
    return 0


def _comando_passagem_leitor(args: argparse.Namespace) -> int:
    """Roda o teste do leitor frio sobre a exportação do HEAD e grava as respostas no gabarito. Recusa e erro saem
    com 1, sem mudar o gabarito."""
    raiz, perfil = _projeto()
    try:
        leitura, avisos = passagem.leitor(raiz, perfil, args.gabarito)
    except passagem.GabaritoInvalido as erro:
        print(erro.mensagem)
        return 1
    except passagem.ExportacaoRecusada as erro:
        print(f"erro: {erro.mensagem}")
        for recusa in erro.recusas:
            print(recusa)
        return 1
    except passagem.ErroPassagem as erro:
        print(f"erro: {_uma_linha(erro.mensagem)}")
        return 1
    except OSError as erro:
        print(f"erro: {comum.motivo_do_sistema(erro)}")
        return 1
    for aviso in avisos:
        print(f"aviso: {aviso}")
    print(passagem.formatar_leitura(leitura), end="")
    return 0


def _enviar_passagem(raiz: Path, perfil: Perfil, valor: str) -> int:
    """O `--enviar vN`: as linhas do envio e, depois, as falhas."""
    numero = re.fullmatch(r"v([1-9][0-9]*)", valor)
    if numero is None:
        print(f"erro: versão fora do formato vN: {_uma_linha(valor)}")
        return 1
    try:
        envio = passagem.enviar(raiz, perfil, int(numero.group(1)))
    except passagem.ErroPassagem as erro:
        print(f"erro: {_uma_linha(erro.mensagem)}")
        return 1
    for linha in envio.linhas + envio.falhas:
        print(linha)
    return 1 if envio.falhas else 0


def _comando_passagem_publicar(args: argparse.Namespace) -> int:
    """Commita o manifesto e cria a tag passagem/vN, só na máquina. Recusa sai com 1, uma linha por recusa. Com
    `--enviar vN`, empurra as tags que faltam no origin e fecha ou comenta as issues de retorno; alguma falha sai
    com 1."""
    raiz, perfil = _projeto()
    if args.enviar is not None:
        return _enviar_passagem(raiz, perfil, args.enviar)
    try:
        publicada = passagem.publicar(raiz, perfil)
    except passagem.PublicacaoRecusada as erro:
        for linha in erro.linhas:
            print(linha)
        return 1
    except passagem.ErroPassagem as erro:
        print(f"erro: {_uma_linha(erro.mensagem)}")
        return 1
    except OSError as erro:
        print(f"erro: {comum.motivo_do_sistema(erro)}")
        return 1
    for linha in passagem.linhas_da_publicada(publicada):
        print(linha)
    return 0


def _comando_estudos(args: argparse.Namespace) -> int:
    """Lista os estudos da pasta do perfil com a situação da decisão de cada um. Sai com 0 em tudo que é da pasta."""
    raiz, perfil = _projeto()
    pasta = perfil.caminhos.estudos
    try:
        lista = estudos.listar(raiz / pasta)
    except OSError as erro:
        print(f"pasta de estudos ilegível: {pasta} ({comum.motivo_do_sistema(erro)})")
        return 0
    sys.stdout.write(estudos.formatar(lista, pasta, args.pendentes))
    return 0


def _comando_invariantes(args: argparse.Namespace) -> int:
    """Confere as invariantes da trilha no modo pedido: no planejamento, com o perfil do planejamento; no
    desenvolvimento, com o dele. Sai com 1 se alguma falha ou se o git dá erro."""
    if args.trilha == perfil_comum.DESENVOLVIMENTO:
        raiz = comum.raiz_dos_comandos()
        perfil = perfil_desenvolvimento.carregar(raiz)
    else:
        raiz, perfil = _projeto()
    if args.base is not None:
        modo, ref = invariantes.BASE, args.base
    else:
        modo, ref = (invariantes.ARVORE if args.arvore else invariantes.INDICE), None
    try:
        conferencias = invariantes.conferir(raiz, perfil, modo, ref)
    except invariantes.ErroGit as erro:
        print("erro: " + _uma_linha(erro.mensagem))
        return 1
    sys.stdout.write(invariantes.formatar(conferencias, args.verbose))
    return 0 if all(conferencia.ok for conferencia in conferencias) else 1


def _comando_importar(args: argparse.Namespace) -> int:
    """Importa a passagem conferida e abre o PR dela, ou a grava na árvore na montagem (spec 6c, §8). A falha de um
    passo sai com 1."""
    versao = None
    if args.versao is not None:
        achado = re.fullmatch(r"v([1-9][0-9]*)", args.versao)
        if achado is None:
            print(f"versão fora do formato vN: {args.versao}")
            return 1
        versao = int(achado.group(1))
    raiz, perfil = _projeto_de_codigo()
    resultado = importacao.importar(raiz, perfil, versao)
    for linha in resultado.linhas:
        print(linha)
    return 1 if resultado.falhou else 0


def _comando_iniciar(args: argparse.Namespace) -> int:
    """Inicia o projeto da `<pasta>` na trilha, pelo modelo do plugin, ou, com `--conferir`, diz o que falta no
    repositório da raiz dos comandos; imprime as linhas (spec do porte 1, §7.5, e spec 6d-repositorio, §7). A
    conferência sai com 1 se algum item falta; o arquivo que não se grava ou não se lê, e o fora do UTF-8, saem com 1 e
    uma linha de motivo."""
    if args.conferir == (args.trilha is not None) or (args.conferir and (args.pasta, args.nome) != (None, None)):
        print("uso inválido: iniciar pede a trilha (planejamento ou desenvolvimento) e a pasta, ou --conferir")
        return 1
    if not args.conferir and args.trilha not in iniciar.TRILHAS:
        print(f"uso inválido: trilha desconhecida: {args.trilha}; use planejamento ou desenvolvimento")
        return 1
    try:
        if args.conferir:
            raiz = comum.raiz_dos_comandos()
            recusa = iniciar.recusa_do_planejamento(raiz)
            if recusa is not None:
                print(recusa)
                return 1
            linhas = iniciar.conferir(raiz, shutil.which("claude"))
        else:
            pasta = Path(args.pasta if args.pasta is not None else ".")
            linhas = iniciar.iniciar(pasta, args.trilha, shutil.which("claude"), args.nome)
    except UnicodeDecodeError as erro:
        print(f"erro: {iniciar.motivo_do_utf8(erro)}")
        return 1
    except OSError as erro:
        motivo = comum.motivo_do_sistema(erro)
        print(f"erro: {erro.filename}: {motivo}" if erro.filename else f"erro: {motivo}")
        return 1
    for linha in linhas:
        print(linha)
    if args.conferir:
        return 1 if any(": falta: " in linha for linha in linhas) else 0
    return 0


def _comando_fichas(args: argparse.Namespace) -> int:
    """Lista as fichas com o estado de cada uma (spec 6c, §9.3)."""
    raiz, perfil = _projeto_de_codigo()
    quadro = fichas.quadro(raiz, perfil)
    sys.stdout.write(fichas.formatar(fichas.listar(quadro, perfil), fichas.urgentes(quadro, perfil)))
    for aviso in fichas.avisos(quadro):
        print(aviso)
    return 0


def _comando_contexto(args: argparse.Namespace) -> int:
    """Grava o Context Packet do bloco da lane, ou o imprime para uma ficha com `--imprimir` (spec 6c, §10)."""
    if args.ficha is not None and not args.imprimir:
        print("uso inválido: a ficha vai com --imprimir")
        return 1
    if args.imprimir and args.ficha is None:
        print("uso inválido: o --imprimir pede a ficha")
        return 1
    raiz, perfil = _projeto_de_codigo()
    if args.imprimir:
        ficha, manifesto_ = contexto.ficha_da_arvore(raiz, perfil, args.ficha)
        sys.stdout.write(contexto.montar(raiz, perfil, ficha, manifesto_).texto)
        return 0
    lane = bloco.lane_pelos_arquivos(raiz, perfil)
    if lane is None:
        print("fora de lane: rode dentro da lane do bloco, ou use harness.py contexto <ficha> --imprimir")
        return 1
    ficha, manifesto_ = contexto.ficha_da_arvore(raiz, perfil, lane.bloco.id)
    pacote = contexto.montar(raiz, perfil, ficha, manifesto_)
    comum.escrever_texto(raiz / perfil.caminhos.blocos / lane.bloco.pasta / contexto.ARQUIVO, pacote.texto)
    print(contexto.resumo(pacote))
    return 0


def _comando_verificar(args: argparse.Namespace) -> int:
    """Roda as verificações do perfil para o momento, na árvore atual (spec 6c, §11.1). Na lane, o `stop` grava a marca
    sem falha. Sai com 1 se alguma falha."""
    raiz, perfil = _projeto_de_codigo()
    lane = bloco.lane_pelos_arquivos(raiz, perfil)
    if args.momento == verificacao.STOP and lane is not None:
        relatorio = verificacao.no_stop(raiz, perfil, lane, None, sempre=True)
    else:
        base = verificacao.base_da_arvore(raiz, perfil, lane)
        relatorio = verificacao.verificar(raiz, perfil, args.momento, verificacao.mudados(raiz, base))
    for linha in relatorio.linhas:
        print(linha)
    return 1 if relatorio.falhou else 0


def _comando_ci(args: argparse.Namespace) -> int:
    """Roda no CI os comandos de `[desenvolvimento.ci] instalar` (spec `ci-dos-projetos`, §6.2). Sai com 1 na recusa e
    na primeira falha."""
    raiz, perfil = _projeto_de_codigo()
    codigo, linhas = instalacao_ci.instalar(raiz, perfil, os.environ)
    for linha in linhas:
        print(linha)
    return codigo


def _aceitacao_da_lane() -> tuple[Path, perfil_desenvolvimento.PerfilDesenvolvimento, bloco.LaneViva, str,
                                  aceitacao.Tabela]:
    """A raiz, o perfil, a lane pelos arquivos, o caminho do `aceitacao.md` dela e a tabela; fora de lane ou sem o
    arquivo, a recusa."""
    raiz, perfil = _projeto_de_codigo()
    lane = bloco.lane_pelos_arquivos(raiz, perfil)
    if lane is None:
        raise bloco.Recusa("fora de lane: rode dentro da lane do bloco")
    relativo = f"{perfil.caminhos.blocos}/{lane.bloco.pasta}/{aceitacao.ARQUIVO}"
    if not (raiz / relativo).is_file():
        raise bloco.Recusa(f"{relativo} não existe; o bloco planejado o gera")
    return raiz, perfil, lane, relativo, aceitacao.ler((raiz / relativo).read_text(encoding="utf-8"), relativo)


def _comando_aceitacao_conferir(args: argparse.Namespace) -> int:
    """Confere as provas automáticas do momento (spec 6c, §12.3), com o pedido da spec aprovada e as variáveis da lane
    (spec prova-por-post, §7); sem `--depois`, grava o resultado e faz o commit. Sai com 1 no MANUAL e no PENDENTE."""
    raiz, perfil, lane, relativo, tabela = _aceitacao_da_lane()
    pedidos, variaveis = {}, {}
    if aceitacao.precisa_da_spec(tabela, args.depois):
        spec = raiz / perfil.caminhos.blocos / lane.bloco.pasta / bloco.ARQUIVO_DA_SPEC
        dados = spec.read_bytes() if spec.is_file() else None
        pedidos = aceitacao.pedidos_aprovados(dados, lane.bloco.spec, perfil, "aceitacao conferir")
        variaveis = aceitacao.variaveis(raiz, perfil, os.environ)
    resultado = aceitacao.conferir(tabela, perfil, lane.bloco.lane, args.depois, datetime.date.today().isoformat(),
                                   pedidos, variaveis)
    for linha in resultado.linhas:  # antes do commit, que pode ser recusado
        print(linha)
    if not args.depois:
        comum.escrever_texto(raiz / relativo, aceitacao.para_texto(resultado.tabela))
        aceitacao.commitar(raiz, relativo, lane.bloco.id)
    return 0 if resultado.ok else 1


def _comando_aceitacao_anotar(args: argparse.Namespace) -> int:
    """Anota o item manual de antes do merge e faz o commit (spec 6c, §12.3)."""
    raiz, _, lane, relativo, tabela = _aceitacao_da_lane()
    anotada = aceitacao.anotar(tabela, args.n, args.resultado, args.nota, datetime.date.today().isoformat())
    item = next(item for item in anotada.itens if item.numero == args.n)
    print(f"{item.numero} {item.prova}: {item.resultado}")  # antes do commit, que pode ser recusado
    print(aceitacao.veredito(anotada, False))
    comum.escrever_texto(raiz / relativo, aceitacao.para_texto(anotada))
    aceitacao.commitar(raiz, relativo, lane.bloco.id)
    return 0


def _comando_prepush(args: argparse.Namespace) -> int:
    """Confere as linhas que o git passa no stdin ao hook pre-push (spec 6c, §13); stdin de terminal vale sem linhas, e
    o erro do `isatty()` conta como terminal. Sai com 1 com alguma recusa."""
    _, perfil = _projeto_de_codigo()
    try:
        terminal = sys.stdin is None or sys.stdin.isatty()
    except (OSError, ValueError):
        terminal = True
    linhas = [] if terminal else comum.ler_entrada().splitlines()
    recusas = prepush.conferir(linhas, perfil)
    for recusa in recusas:
        print(recusa)
    return 1 if recusas else 0


def _imprimir_saida(saida: bloco.Saida, perfil=None) -> int:
    """Imprime as linhas da saída de um comando de bloco ou de lane; sai com 1 no `falhou`.

    Com o `perfil`, manda ao Linear, depois das linhas, cada aviso de transição da saída (spec 6d-repositorio, §9.5) e
    imprime a linha a mais que o `linear.avisar` devolver. O aviso não muda as linhas nem o código de saída.
    """
    for linha in saida.linhas:
        print(linha)
    if perfil is not None and saida.avisos:
        sys.stdout.flush()  # o aviso espera a rede, e as linhas do comando aparecem antes dela
        for aviso in saida.avisos:
            linha = linear.avisar(perfil, aviso)
            if linha is not None:
                print(linha)
    return 1 if saida.falhou else 0


def _comando_bloco_status(args: argparse.Namespace) -> int:
    """O estado do bloco da lane e o próximo passo (spec 6d-bloco, §8.5); sai sempre com 0: a falha antes de achar a
    lane vira a linha `bloco status indisponível: <motivo>`."""
    try:
        raiz, perfil = _projeto_de_codigo()
        linhas = transicoes.status(raiz, perfil, args.para)
    except bloco.Recusa as erro:
        motivo = erro.mensagem
    except (PerfilInvalido, comum.RaizNaoEncontrada, comum.DiretorioApagado) as erro:
        motivo = str(erro)
    except UnicodeDecodeError:
        motivo = "arquivo fora do UTF-8"
    except OSError as erro:
        motivo = comum.motivo_do_sistema(erro)
    else:
        for linha in linhas:
            print(linha)
        return 0
    print(f"bloco status indisponível: {_uma_linha(motivo)}")
    return 0


def _comando_bloco(args: argparse.Namespace) -> int:
    """Muda o estado do bloco da lane, um passo por vez (spec 6c, §14)."""
    if args.acao == "status":
        return _comando_bloco_status(args)
    raiz, perfil = _projeto_de_codigo()
    if args.acao == "bloquear":
        return _imprimir_saida(transicoes.bloquear(raiz, perfil, args.motivo), perfil)
    if args.acao == "finalizar":
        return _imprimir_saida(transicoes.finalizar(raiz, perfil, args.resumo), perfil)
    if args.acao == "desbloquear":
        return _imprimir_saida(transicoes.desbloquear(raiz, perfil, args.replanejar, args.seguir), perfil)
    if args.acao == "replanejar":
        return _imprimir_saida(transicoes.replanejar(raiz, perfil, args.motivo), perfil)
    if args.acao == "planejado":
        return _imprimir_saida(transicoes.planejado(raiz, perfil, args.curto), perfil)
    acoes = {"executando": transicoes.executando,
             "executado": transicoes.executado, "revisando": transicoes.revisando, "revisado": transicoes.revisado,
             "corrigir": transicoes.corrigir}
    return _imprimir_saida(acoes[args.acao](raiz, perfil), perfil)


def _comando_lane(args: argparse.Namespace) -> int:
    """Abre, confere e fecha as lanes dos blocos (spec 6c, §15)."""
    raiz, perfil = _projeto_de_codigo()
    if args.acao == "conferir":
        return _imprimir_saida(lane.conferir(raiz, perfil), perfil)
    if args.acao == "fechar":
        return _imprimir_saida(lane.fechar(raiz, perfil, args.ficha, dict(args.manual or []), args.abandonar), perfil)
    return _imprimir_saida(lane.abrir(raiz, perfil, args.ficha, args.tipo), perfil)


def _linhas_do_hook_das_lanes() -> list[str]:
    """As linhas do hook de início de sessão (spec 6c, §17): o stdin só quando não é um terminal, e o erro do
    `isatty()` conta como terminal; o `cwd` do payload, quando é uma pasta absoluta que existe. O que impede o quadro
    vira a linha `Lanes: indisponíveis (<motivo>)`."""
    try:
        try:
            terminal = sys.stdin is None or sys.stdin.isatty()
        except (OSError, ValueError):
            terminal = True
        try:
            payload = None if terminal else json.loads(comum.ler_entrada())
        except ValueError:
            payload = None
        cwd = payload.get("cwd") if isinstance(payload, dict) else None
        inicio = Path(cwd) if isinstance(cwd, str) and Path(cwd).is_absolute() and Path(cwd).is_dir() else None
        raiz = comum.raiz_dos_comandos(inicio)
        perfil = perfil_desenvolvimento.carregar(raiz)
        quadro = lanes.regravar(raiz, perfil)
        prontas, urgentes = lanes.prontas_e_urgentes(quadro.principal, perfil)
        compactado = isinstance(payload, dict) and payload.get("source") == "compact"
        return lanes.linhas_do_hook(quadro, perfil, raiz, prontas, urgentes, compactado)
    except bloco.Recusa as erro:
        motivo = erro.mensagem
    except (PerfilInvalido, comum.RaizNaoEncontrada) as erro:
        motivo = str(erro)
    except UnicodeDecodeError:
        motivo = "arquivo fora do UTF-8"
    except OSError as erro:
        motivo = comum.motivo_do_sistema(erro)
    return [f"Lanes: indisponíveis ({motivo})"]


def _comando_lanes(args: argparse.Namespace) -> int:
    """Imprime o quadro das lanes e regrava o `LANES.md` (spec 6c, §17); com `--hook`, o resumo do início de sessão,
    que sai sempre com 0."""
    if args.hook:
        for linha in _linhas_do_hook_das_lanes():
            print(linha)
        return 0
    raiz, perfil = _projeto_de_codigo()
    momento = datetime.datetime.now()
    quadro = lanes.regravar(raiz, perfil, agora=lambda: momento)
    sys.stdout.write(lanes.texto(quadro, perfil, momento))
    return 0


def _comando_gerar(args: argparse.Namespace) -> int:
    """Gera os arquivos da trilha do perfil e imprime o que gravou e apagou (spec 6d-gerador, §7.1, e do porte 1, §9);
    com `--check`, só confere e sai com 1 se algum difere (§7.2). A recusa imprime um motivo por linha e sai com 1."""
    if args.trilha == perfil_comum.DESENVOLVIMENTO:
        raiz, perfil = _projeto_de_codigo()
    else:
        raiz, perfil = _projeto()
    textos, problemas, recusas = gerador.textos_e_problemas(raiz, perfil)
    if textos or not recusas:
        if args.check:
            for linha in gerador.linhas_do_check(textos, problemas):
                print(linha)
        else:
            gerador.gravar(raiz, textos, problemas)
            for linha in gerador.linhas_da_gravacao(textos, problemas):
                print(linha)
    for recusa in recusas:
        print(recusa)
    return 1 if recusas or (args.check and problemas) else 0


def _comando_papel(args: argparse.Namespace) -> int:
    """Imprime o modelo e o esforço de um agente, ou dos oito com `--todos`, em linhas ou em JSON (spec 6d-bloco,
    §6.2). Sem agente e sem `--todos`, ou com os dois, é uso inválido."""
    if (args.agente is None) != args.todos:
        print("uso inválido: papel pede um agente ou --todos")
        return 1
    _, perfil = _projeto_de_codigo()
    sys.stdout.write(papeis.saida(perfil, args.agente, args.json))
    return 0


def _comando_revisao(args: argparse.Namespace) -> int:
    """Prepara a revisão do bloco da lane: grava o gabarito, o diff e a marca e imprime os `args` do workflow (spec
    6d-bloco, §7.1); ou registra o resultado do workflow no `revisao.md`, lido do arquivo ou, com `-`, do stdin
    (§7.3); ou dispensa um achado do `## Em aberto` pela palavra do dono (§7.5)."""
    raiz, perfil = _projeto_de_codigo()
    if args.acao == "registrar":
        texto = comum.ler_entrada() if args.arquivo == "-" else comum.ler_texto(Path(args.arquivo))
        return _imprimir_saida(revisao.registrar(raiz, perfil, texto))
    if args.acao == "dispensar":
        return _imprimir_saida(revisao.dispensar(raiz, perfil, args.id_achado, " ".join(args.motivo)))
    return _imprimir_saida(revisao.preparar(raiz, perfil, args.orientacao))


def _comando_fichas_nova(args: argparse.Namespace) -> int:
    """Cria a ficha do código seguinte (spec 6c, §9.3)."""
    raiz, perfil = _projeto_de_codigo()
    print(f"{fichas.nova(raiz, perfil, args.slug)} criada; preencha os campos")
    return 0


def _comando_dossie(args: argparse.Namespace) -> int:
    """Monta o dossiê dos documentos (sem argumento, os em refino do STATUS.md), grava o arquivo e imprime o resumo,
    ou o arquivo inteiro com `--verbose`. Sai com 0 sempre que grava; 1 sem documento ou com documento fora do
    planejamento."""
    raiz, perfil = _projeto()
    documentos = _documentos_pedidos(raiz, perfil, args.documentos)
    if documentos is None:
        return 1
    try:
        resultado = dossie.montar(raiz, perfil, documentos)
    except checar.EntradaInvalida as erro:
        print(_uma_linha(erro.mensagem))
        return 1
    except OSError as erro:
        return _recusar_versao(erro)
    sys.stdout.write(comum.ler_texto(raiz / resultado.caminho) if args.verbose else dossie.resumo(resultado))
    return 0


def _comando_afetados(args: argparse.Namespace) -> int:
    """Lista quem cita cada alvo (ID ou termo), agrupado pelo status na tabela de artefatos. Sai com 0 sempre que
    roda, mesmo sem citação; 1 só com alvo vazio."""
    raiz, perfil = _projeto()
    alvos = [alvo.strip() for alvo in args.alvos]
    if not all(alvos):
        print("recusado: alvo vazio")
        return 1
    try:
        resultado = rastreio.afetados(raiz, perfil, alvos)
    except ValueError:  # alvo sem palavra, como "-"
        print("recusado: alvo vazio")
        return 1
    except rastreio.PendenciaForaDoBacklog as erro:
        print("recusado: " + _uma_linha(erro.mensagem))
        return 1
    sys.stdout.write(rastreio.formatar_afetados(resultado, args.verbose))
    return 0


def _recusar_registro(erro: registro.RegistroRecusado) -> int:
    print("recusado: " + _uma_linha(erro.mensagem))
    for linha in erro.detalhes:
        print(linha)
    return 1


def _comando_registrar_ruling(args: argparse.Namespace) -> int:
    """Acrescenta um Ruling à seção de Rulings do arquivo de decisões. Recusa sai com 1, sem gravar nada."""
    raiz, perfil = _projeto()
    try:
        linha = registro.ruling(raiz, perfil, args.oque, args.por, args.custo)
    except registro.RegistroRecusado as erro:
        return _recusar_registro(erro)
    except OSError as erro:
        return _recusar_versao(erro)
    print(f"Ruling acrescentado em {perfil.caminhos.decisoes}:{linha}")
    return 0


def _comando_registrar_pendencia(args: argparse.Namespace) -> int:
    """Acrescenta uma pendência aberta à tabela de pendências. Recusa sai com 1, sem gravar nada."""
    raiz, perfil = _projeto()
    try:
        id_, linha = registro.pendencia(raiz, perfil, args.texto, args.origem, args.destino)
    except registro.RegistroRecusado as erro:
        return _recusar_registro(erro)
    except OSError as erro:
        return _recusar_versao(erro)
    print(f"{id_} acrescentada em {perfil.caminhos.backlog}:{linha}")
    return 0


_NAS_SECOES_DAS_DECISOES = {
    "aprovacao": ("aprovacao", "Aprovação acrescentada"),
    "descartada": ("descartada", "Abordagem descartada acrescentada"),
    "trecho": ("trecho", "Trecho acrescentado"),
}


def _comando_registrar_na_secao(args: argparse.Namespace) -> int:
    """Acrescenta uma aprovação, uma abordagem descartada ou um trecho do rascunho à seção dele no arquivo de
    decisões. Recusa sai com 1, sem gravar nada."""
    raiz, perfil = _projeto()
    nome_da_funcao, saida = _NAS_SECOES_DAS_DECISOES[args.acao]
    funcao = getattr(registro, nome_da_funcao)
    try:
        linha = funcao(raiz, perfil, args.texto)
    except registro.RegistroRecusado as erro:
        return _recusar_registro(erro)
    except OSError as erro:
        return _recusar_versao(erro)
    print(f"{saida} em {perfil.caminhos.decisoes}:{linha}")
    return 0


def _comando_registrar_medicao(args: argparse.Namespace) -> int:
    """Acrescenta uma medição à tabela dos ciclos no arquivo de atritos. Recusa sai com 1, sem gravar nada."""
    raiz, perfil = _projeto()
    try:
        linha = registro.medicao(raiz, perfil, args.medicao, args.valor)
    except registro.RegistroRecusado as erro:
        return _recusar_registro(erro)
    except OSError as erro:
        return _recusar_versao(erro)
    print(f"Medição acrescentada em {perfil.caminhos.atritos}:{linha}")
    return 0


USO_DO_RELATO = "uso inválido: relato pede o texto e --origem, ou --id e --status"


def _comando_registrar_relato(args: argparse.Namespace) -> int:
    """Acrescenta um relato à seção de informação nova do rascunho, ou muda o status de um relato. Recusa sai com 1,
    sem gravar nada."""
    acrescentar = args.texto is not None and args.origem is not None
    mudar = args.id is not None and args.status is not None
    if acrescentar and (args.id or args.status or args.em or args.motivo):
        acrescentar = False
    if mudar and (args.texto is not None or args.origem is not None or args.confirmada):
        mudar = False
    if not acrescentar and not mudar:
        print(USO_DO_RELATO)
        return 1
    raiz, perfil = _projeto()
    try:
        if acrescentar:
            id_, linha = registro.relato(raiz, perfil, args.texto, args.origem, confirmada=args.confirmada)
        else:
            id_ = args.id
            linha = registro.status_do_relato(raiz, perfil, id_, args.status, em=args.em, motivo=args.motivo)
    except registro.RegistroRecusado as erro:
        return _recusar_registro(erro)
    except OSError as erro:
        return _recusar_versao(erro)
    if acrescentar:
        print(f"{id_} acrescentado em {perfil.caminhos.rascunho}:{linha}")
    else:
        print(f"{id_}: {args.status} ({perfil.caminhos.rascunho}:{linha})")
    return 0


def _comando_guarda(args: argparse.Namespace) -> int:
    """Hook do Claude Code: lê o payload do stdin e escreve o JSON da decisão, ou nada. Sai sempre com 0."""
    try:
        saida = guarda.rodar(args.evento, comum.ler_entrada())
    except Exception as erro:  # só a leitura do stdin chega aqui; o rodar não lança
        saida = json.dumps({"systemMessage": guarda.mensagem_de_erro(args.evento, erro)}, ensure_ascii=False)
    sys.stdout.write(saida)
    return 0


def _comando_proximo(args: argparse.Namespace) -> int:
    """Imprime o próximo passo (spec 4a, §6); STATUS inválido imprime o motivo e sai com 1."""
    raiz, perfil = _projeto()
    try:
        calculado = proximo.calcular(raiz, perfil, consultar_retorno=True, pre_checar=True)
    except estado.EstadoInvalido as erro:
        print("STATUS.md inválido: " + _uma_linha(erro.mensagem))
        return 1
    sys.stdout.write(proximo.formatar(calculado, args.verbose))
    return 0


def _comando_fechar(args: argparse.Namespace) -> int:
    """Fecha o ciclo depois do commit (spec 4a, §7). Recusado imprime o motivo, numa linha, e sai com 1."""
    raiz, perfil = _projeto()
    try:
        fechado = fechamento.fechar(raiz, perfil, args.proximo)
    except fechamento.FechamentoRecusado as erro:
        print("recusado: " + _uma_linha(erro.mensagem))
        return 1
    print(f"Fechado: {fechado.descricao} ({fechado.hash} no HEAD {fechado.commit})")
    print(f"Proximo = {fechado.proximo}")
    if fechado.falha_do_commit:
        print(f"STATUS.md gravado; o commit falhou: {_uma_linha(fechado.falha_do_commit)}; faça o commit à mão")
        return 1
    print(f"STATUS.md no commit {fechado.commit_do_status} ({fechado.modo})")
    return 0


def _comando_ambiente(args: argparse.Namespace) -> int:
    """Imprime os itens do ambiente (spec 4a, §8.3), sem carregar o perfil; sai com 1 só com algum FALHA."""
    amb = ambiente.conferir(comum.raiz_dos_comandos())
    sys.stdout.write(ambiente.formatar(amb))
    return 1 if amb.falhou else 0


def _comando_referencia(args: argparse.Namespace) -> int:
    """Imprime a referência gerada pelo parser (spec 4c, §7.1), sem o perfil, com as skills e os agentes da raiz do
    plugin; com `--gravar`, grava em `docs/referencia.md`, na raiz do plugin, e imprime a linha `Gravado:`. Erro de
    arquivo sai com 1; raiz sem CLAUDE.md também, sem gerar nem gravar."""
    raiz = comum.raiz_dos_comandos()
    if not (raiz / "CLAUDE.md").is_file():
        raise comum.RaizNaoEncontrada(f"raiz do projeto não encontrada: sem CLAUDE.md em {raiz}")
    plugin = comum.raiz_do_nucleo()
    try:
        texto = referencia.gerar(plugin, _montar_parser(), _montar_parser(perfil_comum.DESENVOLVIMENTO))
        if args.gravar:
            comum.escrever_texto(plugin / referencia.CAMINHO, texto)
    except OSError as erro:
        return _recusar_versao(erro)
    if args.gravar:
        print(f"Gravado: {referencia.CAMINHO} ({len(texto.splitlines())} linhas)")
    else:
        sys.stdout.write(texto)
    return 0


def _nova_acao(acoes: argparse._SubParsersAction, nome: str, ajuda: str) -> argparse.ArgumentParser:
    """Cria a ação `nome` com a ajuda de uma linha também como descrição: o `--help` da ação a mostra (spec 4c,
    decisão 9)."""
    return acoes.add_parser(nome, help=ajuda, description=ajuda)


def _acrescentar_invariantes(subcomandos: argparse._SubParsersAction) -> None:
    p_invariantes = subcomandos.add_parser(
        "invariantes", help="confere pelo git as invariantes da trilha do perfil, com os segredos",
        description=invariantes.AJUDA,
    )
    modos = p_invariantes.add_mutually_exclusive_group(required=True)
    modos.add_argument("--arvore", action="store_true", help="o disco contra o HEAD (Stop)")
    modos.add_argument("--indice", action="store_true", help="o índice contra o HEAD (pre-commit)")
    modos.add_argument("--base", metavar="<ref>", help="o HEAD contra a merge-base da ref com ele (CI)")
    p_invariantes.add_argument("--verbose", action="store_true", help="mostra os arquivos ou as linhas de cada falha")
    p_invariantes.set_defaults(funcao=_comando_invariantes)


def _acrescentar_guarda(subcomandos: argparse._SubParsersAction) -> None:
    p_guarda = subcomandos.add_parser(
        "guarda", help="hooks PreToolUse, UserPromptSubmit e Stop (payload no stdin)", description=guarda.AJUDA
    )
    p_guarda.add_argument("evento", choices=guarda.EVENTOS, help="o hook que chamou")
    p_guarda.set_defaults(funcao=_comando_guarda)


def _acrescentar_importar(subcomandos: argparse._SubParsersAction) -> None:
    p_importar = subcomandos.add_parser(
        "importar", help="copia a passagem do repositório de planejamento, conferida, e abre o PR dela",
        description=importacao.AJUDA,
    )
    p_importar.add_argument(
        "versao", nargs="?", metavar="vN",
        help="a versão da tag passagem/vN; sem ela, a maior do repositório de planejamento",
    )
    p_importar.set_defaults(funcao=_comando_importar)


def _acrescentar_iniciar(subcomandos: argparse._SubParsersAction) -> None:
    p_iniciar = subcomandos.add_parser(
        "iniciar", help="inicia um projeto de planejamento ou de desenvolvimento pelo modelo do plugin",
        description=iniciar.AJUDA,
    )
    p_iniciar.add_argument("trilha", nargs="?", help="planejamento ou desenvolvimento")
    p_iniciar.add_argument("pasta", nargs="?", help="a raiz do repositório git que recebe o harness; sem ela, a atual")
    p_iniciar.add_argument("--nome", help="o nome do projeto, no lugar do {{PROJETO}}; sem ele, o nome da pasta")
    p_iniciar.add_argument("--conferir", action="store_true",
                           help="diz o que falta no repositório de código para o primeiro bloco")
    p_iniciar.set_defaults(funcao=_comando_iniciar)


def _acrescentar_fichas(subcomandos: argparse._SubParsersAction) -> None:
    p_fichas = subcomandos.add_parser(
        "fichas", help="lista as fichas da passagem e do backlog do código, com o estado de cada uma",
        description=fichas.AJUDA,
    )
    p_fichas.set_defaults(funcao=_comando_fichas)
    acoes = p_fichas.add_subparsers(dest="acao", metavar="<ação>")
    p_nova = _nova_acao(acoes, "nova", "cria a ficha do código seguinte, com os campos do molde")
    p_nova.add_argument("slug", help="o nome curto, em minúsculas, com hífens")
    p_nova.set_defaults(funcao=_comando_fichas_nova)


def _acrescentar_contexto(subcomandos: argparse._SubParsersAction) -> None:
    p_contexto = subcomandos.add_parser(
        "contexto", help="grava o Context Packet do bloco da lane, ou o imprime para uma ficha",
        description=contexto.AJUDA,
    )
    p_contexto.add_argument("ficha", nargs="?", help="o ID da ficha, com --imprimir")
    p_contexto.add_argument("--imprimir", action="store_true", help="imprime o pacote da ficha, sem gravar")
    p_contexto.set_defaults(funcao=_comando_contexto)


def _acrescentar_verificar(subcomandos: argparse._SubParsersAction) -> None:
    p_verificar = subcomandos.add_parser(
        "verificar", help="roda as verificações do perfil para o momento, na árvore atual",
        description=verificacao.AJUDA,
    )
    p_verificar.add_argument(
        "--momento", required=True, choices=(verificacao.STOP, verificacao.FINALIZAR),
        help="stop: as que casam com o que mudou; finalizar: todas as do fim do bloco",
    )
    p_verificar.set_defaults(funcao=_comando_verificar)


def _acrescentar_ci(subcomandos: argparse._SubParsersAction) -> None:
    p_ci = subcomandos.add_parser(
        "ci", help="comandos do CI do projeto, que só rodam no GitHub Actions", description=instalacao_ci.AJUDA,
    )
    acoes = p_ci.add_subparsers(dest="acao", metavar="<ação>", required=True)
    p_instalar = _nova_acao(acoes, "instalar", "roda os comandos de [desenvolvimento.ci] instalar, um por um")
    p_instalar.set_defaults(funcao=_comando_ci)


def _acrescentar_aceitacao(subcomandos: argparse._SubParsersAction) -> None:
    p_aceitacao = subcomandos.add_parser(
        "aceitacao", help="confere e anota a aceitação do bloco da lane", description=aceitacao.AJUDA
    )
    acoes = p_aceitacao.add_subparsers(dest="acao", metavar="<ação>", required=True)
    p_conferir = _nova_acao(acoes, "conferir", "confere os itens com prova automática e grava o resultado")
    p_conferir.add_argument("--depois", action="store_true", help="confere os itens de depois do merge, só imprimindo")
    p_conferir.set_defaults(funcao=_comando_aceitacao_conferir)
    p_anotar = _nova_acao(acoes, "anotar", "anota o resultado de um item manual de antes do merge")
    p_anotar.add_argument("n", type=int, help="o número do item")
    p_anotar.add_argument("resultado", choices=(aceitacao.OK, aceitacao.FALHOU), help="ok ou falhou")
    p_anotar.add_argument("nota", help="o que foi visto, entre aspas")
    p_anotar.set_defaults(funcao=_comando_aceitacao_anotar)


def _acrescentar_prepush(subcomandos: argparse._SubParsersAction) -> None:
    p_prepush = subcomandos.add_parser(
        "prepush", help="recusa o push direto no ramo principal; chamado pelo hook pre-push do git",
        description=prepush.AJUDA,
    )
    p_prepush.add_argument("remoto", nargs="?", help="o nome do remoto, que o git passa")
    p_prepush.add_argument("url", nargs="?", help="o endereço do remoto, que o git passa")
    p_prepush.set_defaults(funcao=_comando_prepush)


def _acrescentar_bloco(subcomandos: argparse._SubParsersAction) -> None:
    p_bloco = subcomandos.add_parser(
        "bloco", help="muda o estado do bloco da lane, um passo por vez", description=transicoes.AJUDA
    )
    acoes = p_bloco.add_subparsers(dest="acao", metavar="<ação>", required=True)
    p_planejado = _nova_acao(
        acoes, "planejado", "planning → ready_for_execution: confere a spec e o plano e gera o aceitacao.md")
    p_planejado.add_argument("--curto", action="store_true",
                             help="bloco curto: a spec com a prova da causa e o plano de até 3 tarefas")
    p_planejado.set_defaults(funcao=_comando_bloco)
    for nome, ajuda in (
        ("executando", "ready_for_execution → executing"),
        ("executado", "executing → ready_for_review, com a lane sem alteração pendente e o ledger do SDD com as "
                      "tarefas feitas"),
        ("revisando", "ready_for_review → reviewing"),
        ("revisado", "reviewing → ready_for_closure, com o revisao.md sem item em aberto"),
        ("corrigir", "reviewing, ou closing sem PR mesclado → executing"),
    ):
        _nova_acao(acoes, nome, ajuda).set_defaults(funcao=_comando_bloco)
    p_finalizar = _nova_acao(acoes, "finalizar", "ready_for_closure → closing: confere, empurra a branch e abre o PR")
    p_finalizar.add_argument("--resumo", metavar="<texto>",
                             help="o título do PR depois do tipo e do ID; o padrão é o slug com espaços")
    p_finalizar.set_defaults(funcao=_comando_bloco)
    p_desbloquear = _nova_acao(acoes, "desbloquear", "destrava o bloco pela causa do bloqueio")
    opcoes = p_desbloquear.add_mutually_exclusive_group()
    opcoes.add_argument("--replanejar", action="store_true",
                        help="volta a planning, com a lane na versão nova da passagem")
    opcoes.add_argument("--seguir", metavar="<ficha>",
                        help="segue na versão antiga, com a diferença na ficha do código dada")
    p_desbloquear.set_defaults(funcao=_comando_bloco)
    p_bloquear = _nova_acao(acoes, "bloquear", "trava o bloco")
    p_bloquear.add_argument("motivo", help="por que o bloco para, entre aspas")
    p_bloquear.set_defaults(funcao=_comando_bloco)
    p_replanejar = _nova_acao(
        acoes, "replanejar", "de ready_for_execution a ready_for_closure → planning: descarta a aprovação da spec")
    p_replanejar.add_argument("motivo", help="por que a spec aprovada muda, entre aspas")
    p_replanejar.set_defaults(funcao=_comando_bloco)
    p_status = _nova_acao(
        acoes, "status", "mostra o estado do bloco e o próximo passo; sai sempre com 0")
    p_status.add_argument("--para", choices=papeis.SKILLS_DO_CICLO,
                          help="a skill que pergunta; diz quando o estado do bloco é de outra")
    p_status.set_defaults(funcao=_comando_bloco)


def _resultado_manual(texto: str) -> tuple[int, str]:
    """O `--manual <n>=ok|falhou` do `lane fechar`."""
    achado = re.fullmatch(r"([1-9][0-9]*)=(ok|falhou)", texto)
    if achado is None:
        raise argparse.ArgumentTypeError(f"use <n>=ok ou <n>=falhou: {texto}")
    return int(achado.group(1)), achado.group(2)


def _acrescentar_lane(subcomandos: argparse._SubParsersAction) -> None:
    p_lane = subcomandos.add_parser("lane", help="abre, confere e fecha as lanes dos blocos", description=lane.AJUDA)
    acoes = p_lane.add_subparsers(dest="acao", metavar="<ação>", required=True)
    p_abrir = _nova_acao(acoes, "abrir", "abre a lane da ficha, depois do portão")
    p_abrir.add_argument("ficha", help="o ID da ficha")
    p_abrir.add_argument("--tipo", choices=bloco.TIPOS, default="feat",
                         help="o tipo da branch e do PR; feat por padrão")
    p_abrir.set_defaults(funcao=_comando_lane)
    _nova_acao(acoes, "conferir", "confere as lanes contra o origin: passagem nova, PRs mesclados, retornos e planos "
                                  "que se cruzam").set_defaults(funcao=_comando_lane)
    p_fechar = _nova_acao(acoes, "fechar", "fecha a lane com o PR mesclado e a aceitação de depois do merge")
    p_fechar.add_argument("ficha", help="o ID da ficha")
    grupo = p_fechar.add_mutually_exclusive_group()
    grupo.add_argument("--manual", type=_resultado_manual, action="append", metavar="<n>=ok|falhou",
                       help="o resultado de um item manual de depois do merge")
    grupo.add_argument("--abandonar", action="store_true", help="remove a lane sem PR mesclado")
    p_fechar.set_defaults(funcao=_comando_lane)


def _comando_retorno(args: argparse.Namespace) -> int:
    """Abre a issue de retorno no repositório de planejamento (spec 6c, §16)."""
    raiz, perfil = _projeto_de_codigo()
    return _imprimir_saida(retorno.abrir(raiz, perfil, args.id, args.tipo, args.contradiz, args.evidencia), perfil)


def _acrescentar_retorno(subcomandos: argparse._SubParsersAction) -> None:
    p_retorno = subcomandos.add_parser("retorno", help="abre a issue de retorno no repositório de planejamento",
                                       description=retorno.AJUDA)
    acoes = p_retorno.add_subparsers(dest="acao", metavar="<ação>", required=True)
    p_abrir = _nova_acao(acoes, "abrir", "abre o retorno de um ID da passagem que o código contradiz")
    p_abrir.add_argument("id", metavar="ID", help="o ID da passagem")
    p_abrir.add_argument("--tipo", required=True, choices=retorno.TIPOS,
                         help="fato: o bloco segue; decisao: o bloco espera a versão que o resolva")
    p_abrir.add_argument("--contradiz", required=True, help="o que o código mostrou de diferente")
    p_abrir.add_argument("--evidencia", required=True, help="a prova, como a resposta de um serviço")
    p_abrir.set_defaults(funcao=_comando_retorno)


def _acrescentar_lanes(subcomandos: argparse._SubParsersAction) -> None:
    p_lanes = subcomandos.add_parser(
        "lanes", help="imprime o quadro das lanes e regrava o LANES.md", description=lanes.AJUDA,
    )
    p_lanes.add_argument("--hook", action="store_true",
                         help="o resumo do início de sessão, sem rede, com o payload no stdin")
    p_lanes.set_defaults(funcao=_comando_lanes)


def _acrescentar_gerar(subcomandos: argparse._SubParsersAction) -> None:
    p_gerar = subcomandos.add_parser(
        "gerar", help="gera os arquivos do harness a partir do perfil e, no código, da passagem",
        description=gerador.AJUDA,
    )
    p_gerar.add_argument("--check", action="store_true", help="só confere, sem gravar, e sai com 1 se algum difere")
    p_gerar.set_defaults(funcao=_comando_gerar)


def _acrescentar_papel(subcomandos: argparse._SubParsersAction) -> None:
    p_papel = subcomandos.add_parser(
        "papel", help="diz o modelo e o esforço de cada agente do ciclo do bloco", description=papeis.AJUDA,
    )
    p_papel.add_argument("agente", nargs="?", help="o agente; sem ele, o --todos")
    p_papel.add_argument("--todos", action="store_true", help="os oito agentes, na ordem da tabela")
    p_papel.add_argument("--json", action="store_true", help="a saída em JSON: o objeto do agente ou a lista dos oito")
    p_papel.set_defaults(funcao=_comando_papel)


def _acrescentar_revisao(subcomandos: argparse._SubParsersAction) -> None:
    p_revisao = subcomandos.add_parser("revisao", help="prepara e registra a revisão do bloco da lane",
                                       description=revisao.AJUDA)
    acoes = p_revisao.add_subparsers(dest="acao", metavar="<ação>", required=True)
    p_preparar = _nova_acao(acoes, "preparar", "grava o gabarito, o diff e a marca da revisão e imprime os args do "
                                               "workflow")
    p_preparar.add_argument("--orientacao", metavar="<texto>",
                            help="a orientação do dono para os consertos, entre aspas")
    p_preparar.set_defaults(funcao=_comando_revisao)
    p_registrar = _nova_acao(acoes, "registrar", "grava as rodadas do resultado do workflow no revisao.md e faz o "
                                                 "commit")
    p_registrar.add_argument("arquivo", metavar="<arquivo>|-", help="o JSON do resultado; com -, o stdin")
    p_registrar.set_defaults(funcao=_comando_revisao)
    p_dispensar = _nova_acao(acoes, "dispensar", "tira o achado do ## Em aberto pela palavra do dono, com o motivo, e "
                                                 "faz o commit")
    p_dispensar.add_argument("id_achado", metavar="<R-ID>", help="o achado do ## Em aberto")
    p_dispensar.add_argument("motivo", nargs="+", metavar="<motivo>", help="por que o dono dispensa, entre aspas")
    p_dispensar.set_defaults(funcao=_comando_revisao)


def _comando_linear(args: argparse.Namespace) -> int:
    """Refaz o espelho das fichas no Linear, ou, com `--seco`, só o diz (spec 6d-repositorio, §9.6). A tabela e a chave
    que faltam, e a falha do Linear, saem com 1."""
    raiz, perfil = _projeto_de_codigo()
    if perfil.linear is None:
        raise bloco.Recusa("sem [desenvolvimento.linear] no perfil")
    chave = linear.chave_do_ambiente()
    if chave is None:
        raise bloco.Recusa("sem LINEAR_API_KEY no ambiente")
    try:
        saida = linear.espelhar(raiz, perfil, linear.Cliente(chave), args.seco)
    except linear.FalhaDoLinear as erro:
        raise bloco.Recusa(f"linear: {erro.mensagem}") from None
    return _imprimir_saida(saida)


def _acrescentar_linear(subcomandos: argparse._SubParsersAction) -> None:
    p_linear = subcomandos.add_parser(
        "linear", help="espelha as fichas, só de ida, no projeto do Linear", description=linear.AJUDA,
    )
    acoes = p_linear.add_subparsers(dest="acao", metavar="<ação>", required=True)
    p_espelhar = _nova_acao(acoes, "espelhar", "refaz o espelho das fichas no Linear, sem duplicar nada")
    p_espelhar.add_argument("--seco", action="store_true",
                            help="lê o Linear e imprime as mesmas linhas e o mesmo resumo, sem gravar nada")
    p_espelhar.set_defaults(funcao=_comando_linear)


def _montar_parser(trilha: str = perfil_comum.PLANEJAMENTO) -> argparse.ArgumentParser:
    """O parser da trilha: no planejamento, todos os comandos; no desenvolvimento, os comuns às duas trilhas, o
    `invariantes`, o `guarda`, o `iniciar` e o `gerar`, e os dele, na ordem das seções da spec 6c, e depois o `papel`,
    o `revisao` e o `linear`, da 6d. O `args.trilha` diz qual."""
    if trilha == perfil_comum.DESENVOLVIMENTO:
        parser = _Parser(prog="harness.py", description="Harness de desenvolvimento.")
        parser.set_defaults(trilha=trilha)
        subcomandos = parser.add_subparsers(dest="comando", metavar="<comando>", required=True)
        _acrescentar_invariantes(subcomandos)
        _acrescentar_guarda(subcomandos)
        _acrescentar_iniciar(subcomandos)
        _acrescentar_gerar(subcomandos)
        _acrescentar_importar(subcomandos)
        _acrescentar_fichas(subcomandos)
        _acrescentar_contexto(subcomandos)
        _acrescentar_verificar(subcomandos)
        _acrescentar_ci(subcomandos)
        _acrescentar_aceitacao(subcomandos)
        _acrescentar_prepush(subcomandos)
        _acrescentar_bloco(subcomandos)
        _acrescentar_lane(subcomandos)
        _acrescentar_retorno(subcomandos)
        _acrescentar_lanes(subcomandos)
        _acrescentar_papel(subcomandos)
        _acrescentar_revisao(subcomandos)
        _acrescentar_linear(subcomandos)
        return parser
    parser = _Parser(prog="harness.py", description="Harness de planejamento.")
    parser.set_defaults(trilha=perfil_comum.PLANEJAMENTO)
    subcomandos = parser.add_subparsers(dest="comando", metavar="<comando>", required=True)

    # `estado` sem ação imprime o STATUS.md. As ações ficam em `acoes`; opções do próprio `estado`
    # (como a do hook) entram em `p_estado`.
    p_estado = subcomandos.add_parser("estado", help="valida e imprime o STATUS.md", description=estado.AJUDA)
    p_estado.set_defaults(funcao=_comando_estado)
    p_estado.add_argument(
        "--hook", action="store_true", help="imprime o bloco do SessionStart (sempre sai com 0); não combina com set"
    )
    acoes = p_estado.add_subparsers(dest="acao", metavar="<ação>")

    p_set = _nova_acao(acoes, "set", "muda um campo do STATUS.md, validando antes de gravar")
    p_set.add_argument("campo", help="nome do campo, como Passo ou um gate")
    p_set.add_argument("valor", help="o valor novo, numa linha")
    p_set.set_defaults(funcao=_comando_estado_set)

    p_backlog = subcomandos.add_parser(
        "backlog", help="confere o backlog do planejamento ou resolve uma pendência", description=backlog.AJUDA
    )
    acoes_backlog = p_backlog.add_subparsers(dest="acao", metavar="<ação>", required=True)
    p_ids = _nova_acao(acoes_backlog, "ids", "confere os IDs das pendências e conta as abertas")
    p_ids.set_defaults(funcao=_comando_backlog_ids)
    p_resolver = _nova_acao(acoes_backlog, "resolver", "marca uma pendência aberta como resolvida, com o documento e como")
    p_resolver.add_argument("id", metavar="pendência", help="o ID, como <prefixo>-NN")
    p_resolver.add_argument(
        "--em", required=True, metavar="documento",
        help="o documento que a resolveu: o caminho a partir da raiz, ou só o nome, se for único",
    )
    p_resolver.add_argument("como", help="como foi resolvida, numa linha, sem |")
    p_resolver.set_defaults(funcao=_comando_backlog_resolver)

    p_checar = subcomandos.add_parser(
        "checar", help="confere documentos de planejamento contra o molde", description=checar.AJUDA
    )
    p_checar.add_argument(
        "documentos", nargs="*", metavar="documento",
        help="caminho do documento, relativo à raiz do projeto; sem nenhum, os em refino do STATUS.md",
    )
    p_checar.add_argument("--verbose", action="store_true", help="mostra o detalhe de cada verificação")
    p_checar.set_defaults(funcao=_comando_checar)

    p_dossie = subcomandos.add_parser(
        "dossie", help="monta as fontes de cada documento num arquivo fora do git", description=dossie.AJUDA
    )
    p_dossie.add_argument(
        "documentos", nargs="*", metavar="documento",
        help="caminho do documento, relativo à raiz do projeto; sem nenhum, os em refino do STATUS.md",
    )
    p_dossie.add_argument("--verbose", action="store_true", help="imprime o arquivo inteiro no lugar do resumo")
    p_dossie.set_defaults(funcao=_comando_dossie)

    p_afetados = subcomandos.add_parser(
        "afetados", help="lista quem cita um ID ou um termo, pelo status do documento",
        description=rastreio.AJUDA,
    )
    p_afetados.add_argument(
        "alvos", nargs="+", metavar="alvo", help="um ID de requisito ou de pendência, ou um termo entre aspas"
    )
    p_afetados.add_argument("--verbose", action="store_true", help="mostra todas as linhas, com o trecho")
    p_afetados.set_defaults(funcao=_comando_afetados)

    p_registrar = subcomandos.add_parser(
        "registrar", help="acrescenta no ato um Ruling, uma pendência, um relato ou um registro do passo 7",
        description=registro.AJUDA,
    )
    acoes_registrar = p_registrar.add_subparsers(dest="acao", metavar="<ação>", required=True)
    p_ruling = _nova_acao(acoes_registrar, "ruling", "acrescenta um Ruling à seção de Rulings das decisões")
    p_ruling.add_argument("oque", metavar="decisão", help="o quê, numa linha")
    p_ruling.add_argument("--por", required=True, help="por quê")
    p_ruling.add_argument("--custo", required=True, help="o custo se estiver errada")
    p_ruling.set_defaults(funcao=_comando_registrar_ruling)
    p_pendencia = _nova_acao(acoes_registrar, "pendencia", "acrescenta uma pendência aberta à tabela de pendências")
    p_pendencia.add_argument("texto", metavar="pendência", help="a pendência, numa linha, sem |")
    p_pendencia.add_argument("--origem", required=True, help="o documento de onde ela veio")
    p_pendencia.add_argument("--destino", required=True, help="o documento ou a camada que a resolve")
    p_pendencia.set_defaults(funcao=_comando_registrar_pendencia)
    p_relato = _nova_acao(
        acoes_registrar, "relato", "acrescenta informação nova da conversa ao rascunho, ou muda o status de um relato"
    )
    p_relato.add_argument("texto", metavar="relato", nargs="?", help="a informação nova, numa linha")
    p_relato.add_argument("--origem", help="o documento em discussão quando ela surgiu")
    p_relato.add_argument("--confirmada", action="store_true", help="o usuário já confirmou")
    p_relato.add_argument("--id", help="o relato cujo status muda")
    p_relato.add_argument(
        "--status", choices=(registro.CONFIRMADA, registro.INCORPORADA, registro.DESCARTADA), help="o status novo"
    )
    p_relato.add_argument(
        "--em", help="o documento em que foi incorporado: o caminho a partir da raiz, ou só o nome, se for único"
    )
    p_relato.add_argument("--motivo", help="por que foi descartado")
    p_relato.set_defaults(funcao=_comando_registrar_relato)
    for nome, metavar, ajuda in (
        ("aprovacao", "aprovação",
         "acrescenta uma aprovação, com a data e quem aprovou, à seção de aprovações das decisões"),
        ("descartada", "abordagem", "acrescenta uma abordagem descartada à seção dela nas decisões"),
        ("trecho", "trecho", "acrescenta um trecho do rascunho já processado à seção dele nas decisões"),
    ):
        p_secao = _nova_acao(acoes_registrar, nome, ajuda)
        p_secao.add_argument("texto", metavar=metavar, help="o texto, numa linha")
        p_secao.set_defaults(funcao=_comando_registrar_na_secao)
    p_medicao = _nova_acao(acoes_registrar, "medicao", "acrescenta uma medição à tabela dos ciclos no arquivo de atritos")
    p_medicao.add_argument("medicao", metavar="medição", help="o que se mediu, numa linha, sem |")
    p_medicao.add_argument("valor", help="o valor medido, numa linha, sem |")
    p_medicao.set_defaults(funcao=_comando_registrar_medicao)

    p_passo = subcomandos.add_parser(
        "passo", help="fecha um passo do ciclo: grava o STATUS.md e o status do artefato", description=passo.AJUDA
    )
    p_passo.add_argument("numero", type=int, help="o passo que começa, de 0 a 7")
    p_passo.add_argument("--proximo", required=True, help="o que vem a seguir, numa linha")
    p_passo.add_argument("--rodada", type=int, help="a rodada; sem ela, 1 nos passos 2 e 5 e 0 nos outros")
    p_passo.set_defaults(funcao=_comando_passo)

    p_molde = subcomandos.add_parser(
        "molde", help="imprime o molde de um documento de planejamento", description=checar.AJUDA_MOLDE
    )
    p_molde.add_argument("documento", help="caminho do documento, relativo à raiz do projeto")
    p_molde.set_defaults(funcao=_comando_molde)

    p_der = subcomandos.add_parser(
        "der", help="gera e confere o DDL e o diagrama do DER físico", description=der.AJUDA
    )
    acoes_der = p_der.add_subparsers(dest="acao", metavar="<ação>", required=True)
    ajuda_do_documento = "caminho do DER, relativo à raiz; sem ele, o documento de [der] do perfil"
    p_der_gerar = _nova_acao(acoes_der, "gerar", "grava o DDL e o bloco erDiagram a partir das tabelas do DER")
    p_der_gerar.add_argument("documento", nargs="?", help=ajuda_do_documento)
    p_der_gerar.set_defaults(funcao=_comando_der_gerar)
    p_der_conferir = _nova_acao(acoes_der, "conferir", "diz se o DDL e o bloco erDiagram estão em dia com as tabelas")
    p_der_conferir.add_argument("documento", nargs="?", help=ajuda_do_documento)
    p_der_conferir.set_defaults(funcao=_comando_der_conferir)
    p_der_workbench = _nova_acao(acoes_der, "workbench", "grava o manifesto dos prints e do SQL exportado do Workbench")
    p_der_workbench.set_defaults(funcao=_comando_der_workbench)

    p_versao = subcomandos.add_parser(
        "versao", help="marca, confere e limpa a versão enviada para aprovação", description=versao.AJUDA
    )
    acoes_versao = p_versao.add_subparsers(dest="acao", metavar="<ação>", required=True)
    p_marcar = _nova_acao(
        acoes_versao, "marcar", "grava o hash da versão em aprovação no STATUS.md e guarda uma cópia"
    )
    p_marcar.add_argument(
        "documento", nargs="?", help="caminho do documento; sem ele, o Documento do STATUS.md; com Pacote, nenhum"
    )
    p_marcar.set_defaults(funcao=_comando_versao_marcar)
    p_conferir = _nova_acao(acoes_versao, "conferir", "diz se o documento ou o pacote mudou depois da marcação")
    p_conferir.add_argument(
        "documento", nargs="?", help="caminho do documento; sem ele, o Documento do STATUS.md ou o pacote inteiro"
    )
    p_conferir.set_defaults(funcao=_comando_versao_conferir)
    p_limpar = _nova_acao(acoes_versao, "limpar", "desfaz a marcação e apaga a cópia e o histórico")
    p_limpar.set_defaults(funcao=_comando_versao_limpar)
    p_historico = _nova_acao(acoes_versao, "historico", "lista as versões marcadas do documento")
    p_historico.add_argument("documento", nargs="?", help="caminho do documento; padrão: o Documento do STATUS.md")
    p_historico.set_defaults(funcao=_comando_versao_historico)
    p_diff = _nova_acao(acoes_versao, "diff", "diff entre duas versões marcadas")
    p_diff.add_argument("n", type=int, nargs="?", help="versão de partida; padrão: a penúltima")
    p_diff.add_argument("m", type=int, nargs="?", help="versão de chegada; padrão: a última")
    p_diff.add_argument("--completo", action="store_true", help="não corta o diff em 60 linhas")
    p_diff.add_argument("--documento", help="caminho do documento; padrão: o Documento do STATUS.md")
    p_diff.set_defaults(funcao=_comando_versao_diff)

    p_perfil = subcomandos.add_parser(
        "perfil", help="valida e resume o perfil do projeto (.claude/perfil.toml)", description=AJUDA_DO_PERFIL
    )
    p_perfil.add_argument(
        "--para", metavar="<skill>", help='imprime o bloco "Este projeto" da skill (sempre sai com 0)'
    )
    p_perfil.set_defaults(funcao=_comando_perfil)

    p_gate = subcomandos.add_parser(
        "gate", help="roda os itens de script do checklist de um gate de fase", description=gate.AJUDA
    )
    p_gate.add_argument("gate", help="nome do gate no perfil")
    p_gate.add_argument("--verbose", action="store_true", help="mostra cada ocorrência abaixo do item")
    p_gate.set_defaults(funcao=_comando_gate)

    p_legenda = subcomandos.add_parser(
        "legenda", help="gera a legenda das siglas e dos tipos de ID a partir dos documentos",
        description=legenda.AJUDA,
    )
    p_legenda.add_argument(
        "--check", action="store_true", help="só compara com o arquivo e sai com 1 se diferir"
    )
    p_legenda.set_defaults(funcao=_comando_legenda)

    p_passagem = subcomandos.add_parser(
        "passagem", help="exporta, testa pelo leitor frio e publica a passagem do planejamento",
        description=passagem.AJUDA,
    )
    acoes_passagem = p_passagem.add_subparsers(dest="acao", metavar="<ação>", required=True)
    p_exportar = _nova_acao(
        acoes_passagem, "exportar", "copia de um commit os aprovados, o que eles citam por link e a legenda, com o manifesto"
    )
    p_exportar.add_argument("pasta", help="pasta nova ou vazia, fora de uma árvore git")
    p_exportar.add_argument("--ref", metavar="<commit>", help="o commit lido; sem ela, o HEAD")
    p_exportar.set_defaults(funcao=_comando_passagem_exportar)
    p_leitor = _nova_acao(
        acoes_passagem, "leitor", "exporta o HEAD, roda o leitor frio sobre ela e grava as respostas no gabarito"
    )
    p_leitor.add_argument("gabarito", help="o gabarito, a partir da raiz, em caminhos.leitor_frio")
    p_leitor.set_defaults(funcao=_comando_passagem_leitor)
    p_publicar = _nova_acao(acoes_passagem, "publicar", "commita o manifesto e cria a tag passagem/vN, só na máquina")
    p_publicar.add_argument(
        "--enviar", metavar="vN",
        help="empurra as tags passagem/vN que faltam no origin e fecha ou comenta as issues retorno resolvidas; só "
             "depois da confirmação do usuário",
    )
    p_publicar.set_defaults(funcao=_comando_passagem_publicar)

    p_estudos = subcomandos.add_parser(
        "estudos", help="lista os estudos do assessor e a situação da decisão de cada um",
        description=estudos.AJUDA,
    )
    p_estudos.add_argument("--pendentes", action="store_true", help="só os estudos com decisão por registrar e os ilegíveis")
    p_estudos.set_defaults(funcao=_comando_estudos)

    _acrescentar_invariantes(subcomandos)

    p_proximo = subcomandos.add_parser(
        "proximo", help="diz o próximo passo pelo estado e pela tabela de artefatos", description=proximo.AJUDA
    )
    p_proximo.add_argument("--verbose", action="store_true", help="mostra a fila inteira e as revisões por documento")
    p_proximo.set_defaults(funcao=_comando_proximo)

    p_fechar = subcomandos.add_parser(
        "fechar", help="fecha o ciclo depois do commit, conferindo a versão no HEAD, e leva o STATUS.md ao commit",
        description=fechamento.AJUDA,
    )
    p_fechar.add_argument("--proximo", help="o texto do Proximo; sem ele, o próximo passo calculado")
    p_fechar.set_defaults(funcao=_comando_fechar)

    p_ambiente = subcomandos.add_parser(
        "ambiente", help="diz o que falta nesta máquina: Python e TOML, pre-commit e árvore",
        description=ambiente.AJUDA,
    )
    p_ambiente.set_defaults(funcao=_comando_ambiente)

    _acrescentar_guarda(subcomandos)
    _acrescentar_iniciar(subcomandos)
    _acrescentar_gerar(subcomandos)

    p_referencia = subcomandos.add_parser(
        "referencia", help="gera a referência dos comandos, das skills e agentes e do núcleo",
        description=referencia.AJUDA,
    )
    p_referencia.add_argument(
        "--gravar", action="store_true", help="grava em docs/referencia.md, na raiz do plugin, em vez de imprimir"
    )
    p_referencia.set_defaults(funcao=_comando_referencia)

    return parser


def principal(argv: list[str] | None = None) -> int:
    comum.forcar_utf8()
    try:
        trilha = perfil_comum.trilha(comum.raiz_dos_comandos())
    except comum.DiretorioApagado as erro:
        print(f"erro: {erro}")
        return 1
    except comum.RaizNaoEncontrada:
        trilha = perfil_comum.PLANEJAMENTO
    try:
        args = _montar_parser(trilha).parse_args(argv)
        if trilha == perfil_comum.PLANEJAMENTO and getattr(args, "hook", False) \
                and args.funcao is not _comando_estado:
            raise UsoInvalido("--hook não combina com set")
    except UsoInvalido as erro:
        print("uso inválido: " + _uma_linha(" ".join(str(erro).split())))
        return 1
    try:
        return args.funcao(args)
    except comum.RaizNaoEncontrada as erro:
        print(f"erro: {erro}")
        return 1
    except OSError as erro:
        if trilha != perfil_comum.DESENVOLVIMENTO:
            raise
        motivo = comum.motivo_do_sistema(erro)
        print(f"erro: {erro.filename}: {motivo}" if erro.filename else f"erro: {motivo}")
        return 1
    except UnicodeDecodeError:
        if trilha != perfil_comum.DESENVOLVIMENTO:
            raise
        print("erro: arquivo fora do UTF-8")
        return 1
    except PerfilInvalido as erro:
        print(erro.mensagem)
        return 1
    except bloco.Recusa as erro:
        print(erro.mensagem)
        return 1


if __name__ == "__main__":
    sys.exit(principal())
