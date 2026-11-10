"""Entrada dos hooks do plugin (spec do porte 1, §7.1): calada sem perfil; com ele, refaz o link do núcleo e roda o
comando da trilha para o evento.

O `hooks/hooks.json` do plugin chama este arquivo, com o evento no primeiro argumento, em todo projeto em que o plugin
está ligado. Sem `.claude/perfil.toml` na raiz do projeto, sai com 0 sem imprimir nada: o plugin ligado num projeto sem
harness não muda a sessão. Com o perfil, aponta o link `.claude/harness/nucleo` do projeto para a raiz do plugin, que
muda a cada atualização, e lê a trilha. Pelo link, o lançador do projeto, as skills e os subagentes leem os arquivos do
núcleo com um caminho do projeto. Falha ao refazer o link não impede o hook.

O `COMANDOS` diz, para cada par de trilha e evento, os argumentos do `harness.py`. Um par que ele não traz, como o
UserPromptSubmit do desenvolvimento, sai calado. A trilha é a do `perfil_comum.trilha`: sem a chave `[projeto] harness`,
ou com o perfil ilegível, é o planejamento, e o comando dele mostra o erro do perfil, sem traceback.

O UserPromptSubmit do planejamento vai pela via curta do `anotacao`, sem carregar o `harness.py`, com a mesma saída do
`guarda prompt` (spec da onda 1, §5.1): a gravação da resposta não espera o import dos módulos das duas trilhas.
"""
from __future__ import annotations

import caminho

caminho.no_caminho()

import os
import sys
from pathlib import Path

import comum
import perfil_comum

EVENTOS: tuple[str, ...] = ("SessionStart", "PreToolUse", "UserPromptSubmit", "Stop")
COMANDOS: dict[tuple[str, str], tuple[str, ...]] = {
    (perfil_comum.PLANEJAMENTO, "SessionStart"): ("estado", "--hook"),
    (perfil_comum.PLANEJAMENTO, "PreToolUse"): ("guarda", "pre-tool"),
    (perfil_comum.PLANEJAMENTO, "UserPromptSubmit"): ("guarda", "prompt"),
    (perfil_comum.PLANEJAMENTO, "Stop"): ("guarda", "stop"),
    (perfil_comum.DESENVOLVIMENTO, "SessionStart"): ("lanes", "--hook"),
    (perfil_comum.DESENVOLVIMENTO, "PreToolUse"): ("guarda", "pre-tool"),
    (perfil_comum.DESENVOLVIMENTO, "Stop"): ("guarda", "stop"),
}
# O par que o `principal` resolve pelo `anotacao.principal`, atalho do `("guarda", "prompt")` do `COMANDOS`.
VIA_CURTA: tuple[str, str] = (perfil_comum.PLANEJAMENTO, "UserPromptSubmit")


def raiz_com_perfil() -> Path | None:
    """A raiz do projeto, só quando ela tem o perfil; senão, None."""
    try:
        raiz = comum.raiz_projeto()
    except comum.RaizNaoEncontrada:
        return None
    return raiz if (raiz / comum.CAMINHO_PERFIL).is_file() else None


def refazer_link(raiz: Path, nucleo: Path) -> None:
    """Aponta `<raiz>/.claude/harness/nucleo` para `nucleo`. Uma pasta ou arquivo de verdade no lugar fica como está."""
    link = raiz / comum.LINK_DO_NUCLEO
    try:
        if link.is_symlink():
            if Path(os.readlink(link)) == nucleo:
                return
            link.unlink()
        elif link.exists():
            return
        link.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(nucleo, link, target_is_directory=True)
    except OSError:
        pass


def principal(argv: list[str]) -> int:
    """O `argv[0]` é o evento do hook. Sem perfil, sai com 0 e sem saída; com ele, refaz o link e, se o par da trilha e do
    evento tem comando, devolve o código do `harness.principal` desse comando. O par da `VIA_CURTA` devolve o do
    `anotacao.principal`, sem importar o `harness`."""
    raiz = raiz_com_perfil()
    if raiz is None:
        return 0
    refazer_link(raiz, comum.raiz_do_nucleo())
    par = (perfil_comum.trilha(raiz), argv[0] if argv else "")
    comando = COMANDOS.get(par)
    if comando is None:
        return 0
    if par == VIA_CURTA:
        import anotacao

        return anotacao.principal()
    import harness

    return harness.principal(list(comando))


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
