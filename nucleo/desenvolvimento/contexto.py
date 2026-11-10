"""Context Packet (spec 6c, §10): o pacote de leitura de uma ficha, montado da ficha e da cópia da passagem da árvore.

O pacote junta o texto da ficha, os arquivos da passagem que ela cita por link e os trechos dos IDs que ela cita,
pelo manifesto da cópia; o que passa dos limites de fatos e de palavras fica só citado, com o caminho e as linhas.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import campos
import comum
import fichas
import manifesto
from bloco import Recusa
from fichas import Ficha
from manifesto import Definicao, Manifesto

AJUDA = """\
Monta o Context Packet de uma ficha: o pacote de leitura com o texto dela, os arquivos da passagem que ela cita por
link e os trechos dos IDs que ela cita, pela cópia da passagem da árvore (`caminhos.passagem`) e pelo manifesto dela.

- Dois usos. `contexto`, dentro da lane de um bloco, regrava `<blocos>/<pasta do bloco>/contexto.md` da lane, sem
  commit, e imprime o resumo. `contexto <ficha> --imprimir`, em qualquer árvore, imprime o pacote da ficha, sem
  gravar. A ficha vem da cópia da passagem, as FICHA, ou do backlog do código.
- As seções, nesta ordem, e a vazia sai: o título `# Context Packet: <ID> (passagem/vN)`; com o Contexto `sim`, a
  linha `Esta ficha pede contexto além deste pacote: o contexto-leitor completa (fase 6d).`; `## Ficha`, com o texto
  da ficha; `## Para ler`; `## Fatos`; `## Também citados`; `## Pendências abertas citadas`; e
  `## Não achados na passagem`.
- Para ler: até 5 arquivos da passagem que a ficha cita por link, resolvidos a partir do arquivo dela, sem repetir,
  na ordem. O link com esquema, o só de âncora e o que sai da cópia ou não está no manifesto ficam de fora.
- Fatos: os IDs citados que o manifesto define, primeiro os do campo Fonte, na ordem deles, e depois os outros, na
  ordem em que aparecem na ficha. Cada um vem com `### <ID> · <passagem>/<arquivo>:<primeira>-<última>` e o texto do
  trecho. Os títulos do trecho descem abaixo do `### <ID>`: o mais alto vai a `####` e os outros o mesmo tanto, até
  `######`, sem mexer nos blocos de código; o trecho sem título, ou com o mais alto já em `####` ou abaixo, sai igual.
- Corte: até 8 fatos e 1.200 palavras, contadas pelos espaços, sem o texto da ficha. O fato que não cabe vai para
  `## Também citados`, só com o ID, o caminho e as linhas, e o seguinte ainda pode entrar.
- Pendências abertas citadas: os PEND citados que estão nas pendências do manifesto, com o texto de lá; o resolvido
  não aparece. Não achados na passagem: os outros IDs citados que o manifesto não define, menos os das fichas do
  código.
- Resumo: `contexto.md com <f> fatos, <t> também citados e <p> pendências`.
- Recusas, com saída 1: `fora de lane: rode dentro da lane do bloco, ou use harness.py contexto <ficha> --imprimir`;
  `sem a cópia da passagem em <passagem>/; rode harness.py importar`; `<ID> não existe nesta árvore`;
  `fora de um repositório git`; e, como uso inválido, `a ficha vai com --imprimir` e `o --imprimir pede a ficha`.
"""

ARQUIVO = "contexto.md"
LIMITE_PARA_LER = 5
LIMITE_DE_FATOS = 8
LIMITE_DE_PALAVRAS = 1200
LINHA_DO_CONTEXTO = "Esta ficha pede contexto além deste pacote: o contexto-leitor completa (fase 6d)."
NIVEL_DO_TRECHO = 4
_RE_TITULO = re.compile(r"(#{1,6}) ")


@dataclass(frozen=True)
class Pacote:
    texto: str
    fatos: int
    tambem: int
    pendencias: int


def ficha_da_arvore(raiz: Path, perfil, id_: str) -> tuple[Ficha, Manifesto]:
    """A ficha do ID, da cópia da passagem ou do backlog do código, e o manifesto da cópia; sem a cópia ou sem a
    ficha, `Recusa`."""
    manifesto_ = fichas.ler_manifesto(raiz, perfil)
    if manifesto_ is None:
        raise Recusa(f"sem a cópia da passagem em {perfil.caminhos.passagem}/; rode harness.py importar")
    todas = fichas.da_passagem(raiz, perfil, manifesto_) + fichas.do_backlog(raiz, perfil)
    ficha = next((ficha for ficha in todas if ficha.id == id_), None)
    if ficha is None:
        raise Recusa(f"{id_} não existe nesta árvore")
    return ficha, manifesto_


def _para_ler(ficha: Ficha, pasta: str, manifesto_: Manifesto) -> list[str]:
    """Os arquivos do manifesto que a ficha cita por link, com o caminho na árvore, sem repetir, na ordem, até o
    limite."""
    da_passagem = {arquivo.caminho for arquivo in manifesto_.arquivos}
    caminhos: list[str] = []
    for _, destino in campos.ler_links(ficha.texto):
        resolvido = campos.resolver_link(destino, ficha.arquivo)
        if resolvido is None or not resolvido.startswith(pasta + "/") or resolvido in caminhos:
            continue
        if resolvido[len(pasta) + 1:] in da_passagem:
            caminhos.append(resolvido)
        if len(caminhos) == LIMITE_PARA_LER:
            break
    return caminhos


def _descer_titulos(texto: str) -> str:
    """O texto com os títulos fora dos blocos de código descidos: o mais alto vai a `####` e os outros o mesmo tanto,
    até `######`. Sem título, ou com o mais alto já em `####` ou abaixo, sai igual."""
    niveis: dict[int, int] = {}
    for numero, linha in campos.linhas_fora_de_blocos(texto):
        titulo = _RE_TITULO.match(linha)
        if titulo:
            niveis[numero] = len(titulo.group(1))
    if not niveis or min(niveis.values()) >= NIVEL_DO_TRECHO:
        return texto
    deslocamento = NIVEL_DO_TRECHO - min(niveis.values())
    linhas = texto.split("\n")
    for numero, nivel in niveis.items():
        linhas[numero - 1] = "#" * (min(nivel + deslocamento, 6) - nivel) + linhas[numero - 1]
    return "\n".join(linhas)


def _trecho(raiz: Path, pasta: str, definicao: Definicao) -> str:
    """O texto do trecho no arquivo da cópia, sem as quebras do fim e com os títulos descidos."""
    arquivo = f"{pasta}/{definicao.arquivo}"
    try:
        texto = comum.ler_texto(raiz / arquivo)
    except (OSError, UnicodeDecodeError):
        raise Recusa(f"falta {arquivo}; a cópia muda só por harness.py importar") from None
    primeira, ultima = definicao.linhas
    return _descer_titulos("\n".join(texto.split("\n")[primeira - 1:ultima]).rstrip("\n"))


def montar(raiz: Path, perfil, ficha: Ficha, manifesto_: Manifesto) -> Pacote:
    """O Context Packet da ficha sobre a cópia da passagem da árvore (spec 6c, §10, e Anexo B.2)."""
    pasta = perfil.caminhos.passagem
    citados = fichas.ids_citados(ficha, fichas.prefixos_citaveis(manifesto_, perfil.prefixo))
    da_fonte: list[str] = []
    for item in fichas.campo(ficha, "Fonte") or []:
        da_fonte += [id_ for id_ in fichas.RE_ID_CITADO.findall(item) if id_ in citados and id_ not in da_fonte]
    definidos = [id_ for id_ in da_fonte + [id_ for id_ in citados if id_ not in da_fonte] if id_ in manifesto_.ids]
    fatos: list[str] = []
    tambem: list[str] = []
    restam = LIMITE_DE_PALAVRAS
    for id_ in definidos:
        definicao = manifesto_.ids[id_]
        onde = f"{pasta}/{definicao.arquivo}:{definicao.linhas[0]}-{definicao.linhas[1]}"
        texto = _trecho(raiz, pasta, definicao)
        palavras = len(texto.split())
        if len(fatos) < LIMITE_DE_FATOS and palavras <= restam:
            fatos.append(f"### {id_} · {onde}\n{texto}")
            restam -= palavras
        else:
            tambem.append(f"- {id_} · {onde}")
    abertas = {pendencia.id: pendencia.texto for pendencia in manifesto_.pendencias}
    pendencias = [f"- {id_}: {abertas[id_]}" for id_ in citados if id_ in abertas]
    sem_trecho = (fichas.PREFIXO_DA_PENDENCIA, perfil.prefixo)
    nao_achados = [f"- {id_}" for id_ in citados
                   if id_ not in manifesto_.ids and id_.split("-", 1)[0] not in sem_trecho]
    blocos = [f"# Context Packet: {ficha.id} ({manifesto.PREFIXO_TAG}{manifesto_.versao})"]
    if [valor.strip() for valor in fichas.campo(ficha, "Contexto") or []] == ["sim"]:
        blocos.append(LINHA_DO_CONTEXTO)
    blocos.append("## Ficha\n" + ficha.texto.rstrip("\n"))
    secoes = (
        ("## Para ler", "\n".join(f"- {caminho}" for caminho in _para_ler(ficha, pasta, manifesto_))),
        ("## Fatos", "\n\n".join(fatos)),
        ("## Também citados", "\n".join(tambem)),
        ("## Pendências abertas citadas", "\n".join(pendencias)),
        ("## Não achados na passagem", "\n".join(nao_achados)),
    )
    blocos += [f"{titulo}\n{corpo}" for titulo, corpo in secoes if corpo]
    return Pacote("\n\n".join(blocos) + "\n", len(fatos), len(tambem), len(pendencias))


def _contagem(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def resumo(pacote: Pacote) -> str:
    """`contexto.md com <f> fatos, <t> também citados e <p> pendências`."""
    return (f"{ARQUIVO} com {_contagem(pacote.fatos, 'fato', 'fatos')}, "
            f"{_contagem(pacote.tambem, 'também citado', 'também citados')} e "
            f"{_contagem(pacote.pendencias, 'pendência', 'pendências')}")
