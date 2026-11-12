"""Início da sessão (spec 4a, §8.1 e §18): o JSON do hook SessionStart, com o aviso ao usuário e o contexto do
modelo. O aviso é o `systemMessage`, que o usuário vê, e o contexto é o `additionalContext`, que o modelo recebe.

O aviso diz a fase, o documento e o próximo passo numa linha e, só quando o ambiente falha ou avisa, o ambiente numa
segunda; depois de compactar, não sai. O contexto é o bloco do STATUS, as linhas do `proximo` e as do ambiente.
"""
from __future__ import annotations

import json
import posixpath
import subprocess
from pathlib import Path

import ambiente
import comum
import estado
import proximo
import rastreio
from perfil import PerfilInvalido, carregar as carregar_perfil

LIMITE_AVISO = 300
FONTE_PADRAO = "startup"
SEM_AVISO = ("compact",)
_ERRO_NO_INICIO = "Planejamento: erro no início da sessão: "
_SEPARADOR = " · "


def _uma_linha(texto: str) -> str:
    return texto.replace("\r", "\\r").replace("\n", "\\n")


def fonte(entrada: str) -> str:
    """O `source` do payload do SessionStart; FONTE_PADRAO com payload vazio, ilegível, que não é objeto ou sem
    `source` em texto."""
    try:
        dados = json.loads(entrada)
    except ValueError:
        return FONTE_PADRAO
    valor = dados.get("source") if isinstance(dados, dict) else None
    return valor if isinstance(valor, str) and valor else FONTE_PADRAO


def _documento(dados: dict[str, str], raiz: Path) -> str:
    """`nenhum documento`, ou o nome do documento em refino com o passo; com pacote ou lote, quantos mais há nele.
    Lança EstadoInvalido com a lista do lote ilegível."""
    documentos = estado.documentos(dados, raiz)
    if not documentos:
        return "nenhum documento"
    nome = posixpath.basename(documentos[0])
    if len(documentos) > 1:
        grupo = "lote" if estado.CAMPO_LOTE in dados else "pacote"
        nome += f" (+{len(documentos) - 1} no {grupo})"
    return f"{nome} (passo {dados['Passo']})"


def _montar(executar) -> tuple[str, str]:
    """O contexto e o aviso, sem cortar. PerfilInvalido e outras exceções sobem para `rodar`."""
    raiz = comum.raiz_projeto()
    amb = ambiente.conferir(raiz, executar)
    python = amb.itens[0]
    if python.nivel == ambiente.FALHA:
        return python.linha, python.linha
    perfil = carregar_perfil(raiz)
    bloco = estado.bloco_hook(raiz, perfil, executar)
    linhas_do_proximo: list[str] = []
    try:
        dados = estado.ler(raiz / perfil.caminhos.status, perfil)
    except estado.EstadoInvalido as erro:
        primeira = f"Planejamento: STATUS.md inválido: {_uma_linha(erro.mensagem)}"
    else:
        try:
            calculado = proximo.calcular(raiz, perfil, dados, executar, amb)
        except Exception as erro:  # o próximo passo não pode derrubar o resto do início
            primeira = f"Planejamento: erro ao calcular o próximo passo: {type(erro).__name__}: {_uma_linha(str(erro))}"
        else:
            linhas_do_proximo = proximo.linhas_do_hook(calculado)
            try:
                documento = _documento(dados, raiz)
            except estado.EstadoInvalido as erro:
                primeira = f"Planejamento: STATUS.md inválido: {_uma_linha(erro.mensagem)}"
            else:
                primeira = (f"Planejamento{_SEPARADOR}{dados['Fase']}{_SEPARADOR}{documento}{_SEPARADOR}"
                            f"Próximo: {calculado.linha_curta}")
    avisos = [item.linha for item in amb.avisos]
    contexto = "\n".join([bloco.rstrip("\n"), *linhas_do_proximo, *avisos])
    aviso = primeira + (f"\nAmbiente: {_SEPARADOR.join(avisos)}" if avisos else "")
    return contexto, aviso


def rodar(entrada: str, executar=subprocess.run) -> str:
    """O JSON do SessionStart numa linha. Nunca lança: qualquer erro vira `ERRO no hook: ...` no contexto e
    `Planejamento: erro no início da sessão: ...` no aviso."""
    try:
        contexto, aviso = _montar(executar)
    except PerfilInvalido as erro:
        motivo = _uma_linha(erro.mensagem)
        contexto, aviso = f"ERRO no hook: {motivo}", _ERRO_NO_INICIO + motivo
    except Exception as erro:  # o hook não pode derrubar a abertura da sessão
        motivo = f"{type(erro).__name__}: {_uma_linha(str(erro))}"
        contexto, aviso = f"ERRO no hook: {motivo}", _ERRO_NO_INICIO + motivo
    saida: dict = {}
    if fonte(entrada) not in SEM_AVISO:
        saida["systemMessage"] = rastreio.cortar(aviso, LIMITE_AVISO)
    saida["hookSpecificOutput"] = {"hookEventName": "SessionStart", "additionalContext": estado.limitar_hook(contexto)}
    return json.dumps(saida, ensure_ascii=False)
