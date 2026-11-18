"""O corpo do PR do bloco: a leitura do arquivo do `--corpo`, a conferência das três seções do molde e a montagem com a
aceitação e as verificações.

O arquivo traz `## Resumo`, `## Evidência` e `## Perigo do merge`, nessa ordem; o núcleo acrescenta, no fim da
Evidência, as subseções `### Aceitação` e `### Verificações`. Os títulos se contam só fora dos blocos de código. O texto
é normalizado como o `git commit` faz com a mensagem, para o corpo do commit e o do PR saírem iguais.
"""
from __future__ import annotations

from pathlib import Path

import aceitacao
import campos
import comum
from bloco import Recusa

TITULOS = ("Resumo", "Evidência", "Perigo do merge")
DO_NUCLEO = ("Aceitação", "Verificações")

_PREFIXO = "bloco finalizar: "


def _recusa(mensagem: str) -> Recusa:
    return Recusa(_PREFIXO + mensagem)


def ler(raiz: Path, caminho: str | None) -> str:
    """O texto do arquivo do `--corpo`, relativo à raiz ou absoluto; a falta, a ausência (uma pasta conta) e o que não se
    lê como UTF-8 (o BOM sai) são recusa."""
    if caminho is None:
        raise _recusa(f"falta o --corpo <arquivo>; rode o /{comum.PREFIXO_DAS_SKILLS}finalizar-bloco")
    arquivo = Path(raiz) / caminho
    try:
        dados = arquivo.read_bytes() if arquivo.is_file() else None
    except OSError:
        dados = None
    if dados is None:
        raise _recusa(f"{caminho} não existe")
    try:
        return dados.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise _recusa(f"{caminho} não se lê como UTF-8") from None


def normalizar(texto: str) -> str:
    """O texto como o `git commit` o deixa: `\\r\\n` vira `\\n`, as linhas perdem os espaços do fim, as linhas em branco
    seguidas viram uma, e as do começo e do fim saem, sem `\\n` no fim."""
    linhas: list[str] = []
    for linha in texto.replace("\r\n", "\n").split("\n"):
        linha = linha.rstrip(" \t\r")
        if linha or (linhas and linhas[-1]):
            linhas.append(linha)
    while linhas and not linhas[-1]:
        linhas.pop()
    return "\n".join(linhas)


def _titulos(texto: str, marca: str) -> list[tuple[int, str]]:
    """(número da linha, título sem a marca) de cada título da marca, fora dos blocos de código."""
    return [(numero, linha[len(marca):].rstrip())
            for numero, linha in campos.linhas_fora_de_blocos(texto) if linha.startswith(marca)]


def conferir(texto: str) -> None:
    """Recusa pela primeira regra que falha: seção que falta, fora do molde, fora da ordem ou vazia, texto antes do
    `## Resumo`, ou `### Aceitação` e `### Verificações` já no texto."""
    secoes = _titulos(texto, "## ")
    nomes = [nome for _, nome in secoes]
    for titulo in TITULOS:
        if titulo not in nomes:
            raise _recusa(f"o corpo não tem a seção ## {titulo}")
    vistos: list[str] = []
    for nome in nomes:
        if nome not in TITULOS or nome in vistos:
            raise _recusa(f"o corpo tem a seção ## {nome}, fora do molde")
        vistos.append(nome)
    if nomes != list(TITULOS):
        raise _recusa(f"as seções do corpo estão fora da ordem {comum.juntar(TITULOS)}")
    linhas = texto.split("\n")
    inicios = [numero for numero, _ in secoes]
    fins = inicios[1:] + [len(linhas) + 1]
    for titulo, inicio, fim in zip(TITULOS, inicios, fins):
        if not any(linha.strip() for linha in linhas[inicio:fim - 1]):
            raise _recusa(f"a seção ## {titulo} está vazia")
    if any(linha.strip() for linha in linhas[:inicios[0] - 1]):
        raise _recusa("o corpo tem texto antes do ## Resumo")
    for _, nome in _titulos(texto, "### "):
        if nome in DO_NUCLEO:
            raise _recusa(f"o corpo já tem ### {nome}; o núcleo o acrescenta")


def montar(texto: str, tabela: aceitacao.Tabela, linhas: tuple[str, ...]) -> str:
    """O texto com `### Aceitação` e `### Verificações` entre a Evidência e o `## Perigo do merge`, normalizado."""
    texto = normalizar(texto)
    todas = texto.split("\n")
    perigo = [numero for numero, nome in _titulos(texto, "## ") if nome == TITULOS[-1]][0] - 1
    antes = todas[:perigo]
    while antes and not antes[-1]:
        antes.pop()
    da_tabela = aceitacao.para_texto(tabela).rstrip("\n").split("\n")[2:]
    entra = ["", "### Aceitação", "", *da_tabela, "", "### Verificações", "", *[f"- {linha}" for linha in linhas], ""]
    return normalizar("\n".join([*antes, *entra, *todas[perigo:]]))
