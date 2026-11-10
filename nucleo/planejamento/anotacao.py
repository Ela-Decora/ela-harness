"""Via curta do UserPromptSubmit do planejamento (spec da onda 1, §5.1): grava a resposta da aprovação sem carregar o
harness.py.

O `gancho` a chama no par (planejamento, UserPromptSubmit), antes de importar o `harness`, e a `guarda` delega a ela o
evento `prompt`. Faz o que o `harness.py guarda prompt` faz: lê o payload do stdin, acha a raiz da sessão, carrega o
perfil e grava a `resposta` pelo `versao.anotar_resposta`. Escreve nada, ou o JSON do `systemMessage` de erro, e sai
sempre com 0. Importa só o `comum`, o `versao` e o `perfil`: nem o `harness`, nem a `guarda`, nem o `argparse`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import comum
import versao
from perfil import Perfil, carregar

# A notificação de tarefa em segundo plano chega ao UserPromptSubmit como prompt (sonda 4) e não é mensagem do usuário.
PREFIXO_NOTIFICACAO = "<task-notification>"
# Os começos dos prompts que não são mensagem do usuário (sondas 7 e 8 da 4a): a notificação e o retorno de subagente.
# A mensagem com texto colado também começa por "<" seguido de um nome, e por isso a regra é a lista (sonda 6 da 4a).
PREFIXOS_SINTETICOS = (PREFIXO_NOTIFICACAO, "<agent-message ")


def prompt_sintetico(prompt: str) -> bool:
    """O prompt começa, depois dos espaços, por um de PREFIXOS_SINTETICOS (spec 4a, §10.2)."""
    return prompt.lstrip().startswith(PREFIXOS_SINTETICOS)


def anotar_prompt(payload: dict, raiz: Path, perfil: Perfil) -> None:
    """Prova de mensagem (spec 3b, §7.1, e 4a, §10): grava a `resposta`, com o trecho da mensagem, com `Passo` 6 e
    versão marcada, menos para prompt sintético; um prompt que não é texto grava sem trecho. Lança EstadoInvalido se
    o STATUS.md não serve."""
    prompt = payload.get("prompt")
    if isinstance(prompt, str) and prompt_sintetico(prompt):
        return
    versao.anotar_resposta(raiz, perfil, mensagem=prompt if isinstance(prompt, str) else "")


def motivo_do_erro(erro: BaseException) -> str:
    """`<Tipo>: <mensagem>` do erro, numa linha: o `\\r` e o `\\n` saem escapados."""
    return f"{type(erro).__name__}: {erro}".replace("\r", "\\r").replace("\n", "\\n")


def mensagem_de_erro(erro: BaseException) -> str:
    """O `systemMessage` de um erro ao anotar a resposta, numa linha."""
    return f"guarda do harness com erro ao anotar a resposta: {motivo_do_erro(erro)}"


def rodar(entrada: str) -> str:
    """A saída do hook do prompt para o JSON `entrada`: vazia, ou o JSON com o `systemMessage` de erro.

    O payload que não é um objeto JSON é erro. A raiz é a da sessão, `comum.raiz_projeto()`, e o perfil é o de
    planejamento dela. Nunca lança: qualquer erro vira `systemMessage`, sem decisão.
    """
    try:
        payload = json.loads(entrada)
        if not isinstance(payload, dict):
            raise ValueError("o payload não é um objeto JSON")
        raiz = comum.raiz_projeto()
        anotar_prompt(payload, raiz, carregar(raiz))
    except Exception as erro:  # o hook não pode derrubar o prompt
        return json.dumps({"systemMessage": mensagem_de_erro(erro)}, ensure_ascii=False)
    return ""


def principal() -> int:
    """O hook do prompt: lê o stdin, escreve o `rodar` no stdout e sai sempre com 0. O erro da leitura do stdin vira o
    `systemMessage` de erro, como o `rodar` faz com os outros."""
    comum.forcar_utf8()
    try:
        saida = rodar(comum.ler_entrada())
    except Exception as erro:  # só a leitura do stdin chega aqui; o rodar não lança
        saida = json.dumps({"systemMessage": mensagem_de_erro(erro)}, ensure_ascii=False)
    sys.stdout.write(saida)
    return 0
