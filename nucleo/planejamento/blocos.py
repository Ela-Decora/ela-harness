"""Textos tirados do perfil: o resumo do comando `perfil` e o bloco "Este projeto" de cada skill (spec 2a, §5.3 e §5.5)."""
from __future__ import annotations

from pathlib import Path

import estado
from comum import juntar
from perfil import TIPOS_DE_ITEM, Perfil

LIMITE = 1500  # o teto padrão do bloco de uma skill, em caracteres
# As skills com outro teto: o checklist do gate e as regras da camada não cabem no padrão.
LIMITES: dict[str, int] = {"gate-fase": 3000, "refinar-documento": 1600}


def limite(skill: str) -> int:
    """O teto do bloco da skill, em caracteres."""
    return LIMITES.get(skill, LIMITE)


class SkillDesconhecida(Exception):
    """Nenhum bloco para a skill pedida. `mensagem` diz quais existem."""

    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


class ForaDaFase(Exception):
    """A skill não se aplica à fase atual. `mensagem` diz o gate e a fase."""

    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


def _texto(linhas: list[str]) -> str:
    return "".join(linha + "\n" for linha in linhas)


def resumo(perfil: Perfil) -> str:
    """O que `harness.py perfil` imprime: poucas linhas sobre o perfil já validado."""
    checklists = []
    for gate in perfil.gates.values():
        contagens = {tipo: sum(1 for item in gate.itens if item.tipo == tipo) for tipo in TIPOS_DE_ITEM}
        checklists.append(f"{gate.nome} com {len(gate.itens)} itens (" + ", ".join(
            f"{contagem} {tipo}" for tipo, contagem in contagens.items() if contagem or tipo != "leitor-frio"
        ) + ")")
    return _texto([
        f"perfil válido: {perfil.nome}",
        "fases: " + ", ".join(f"{fase.id} ({fase.gate})" for fase in perfil.fases),
        "checklists: " + ("; ".join(checklists) or "nenhum"),
        f"ids: {', '.join(perfil.ids.prefixos)}; pendências {perfil.ids.prefixo_pendencia}-NN",
    ])


def _regras(perfil: Perfil) -> list[str]:
    return [f"- {fase.id} ({fase.gate}): {fase.regra}" for fase in perfil.fases]


def _refinar_documento(perfil: Perfil) -> str:
    c = perfil.caminhos
    trocas = "; ".join(f"{antigo} → {novo}" for antigo, novo in perfil.moldes.trocas_de_nome.items())
    return _texto([
        f"Projeto: {perfil.nome}. Trocas de nome do molde para o documento: {trocas or 'nenhuma'}.",
        f"Pasta do planejamento: {c.planejamento}/. Moldes: {perfil.moldes.pasta}/. Estado: {c.status}. "
        f"Pendências: {c.backlog}. Decisões: {c.decisoes}. Rascunho: {c.rascunho}. Atritos do harness: {c.atritos}.",
        "Precedência das fontes, da mais forte à mais fraca: "
        + ", ".join(["decisões registradas e CLAUDE.md", "rascunho", *(f"{fonte}/" for fonte in c.fontes)]) + ".",
        "Regra de cada camada (a pasta da fase no caminho):",
        *_regras(perfil),
        "IDs: " + ", ".join(f"{padrao}-NN" for padrao in perfil.ids.padroes)
        + f"; pendências {perfil.ids.prefixo_pendencia}-NN.",
        "Dúvidas que mudam o escopo: " + (", ".join(perfil.texto.duvidas_de_escopo) or "nenhuma listada") + ".",
        "Sistemas do cliente, citáveis em qualquer camada: "
        + (", ".join(perfil.texto.sistemas_do_cliente) or "nenhum listado") + ".",
        "Nomes duplos já vistos: " + ("; ".join(perfil.texto.nomes_duplos) or "nenhum") + ".",
        f"Glossário: {perfil.texto.glossario}.",
        *_fronteiras(perfil),
        f"Relatórios de pesquisa: {c.pesquisas}/pesquisa-<documento>-<data>/.",
    ])


def _fronteiras(perfil: Perfil) -> list[str]:
    """Uma linha por texto de fronteira distinto, na ordem das fases, com as camadas que o têm."""
    por_texto: dict[str, list[str]] = {}
    for fase in perfil.fases:
        if fase.fronteira:
            por_texto.setdefault(fase.fronteira, []).append(fase.id)
    return [
        f"Fronteira do MVP, {'na camada' if len(ids) == 1 else 'nas camadas'} {juntar(ids)}: {texto}."
        for texto, ids in por_texto.items()
    ]


def _gate_fase(perfil: Perfil, raiz: Path) -> str:
    """Só a fase atual do STATUS.md, com a regra e o checklist dela. STATUS ilegível: EstadoInvalido sobe."""
    c = perfil.caminhos
    fase = perfil.fase_por_id(estado.ler(raiz / c.status, perfil)["Fase"])
    linhas = [
        f"Projeto: {perfil.nome}.",
        f"Pasta do planejamento: {c.planejamento}/. Estado: {c.status}. Pendências: {c.backlog}. "
        f"Decisões: {c.decisoes}. Atritos do harness: {c.atritos}.",
        f"Fase atual: {fase.id} ({fase.gate}): {fase.regra}",
    ]
    gate = perfil.gates.get(fase.gate)
    if gate is None:
        linhas.append(f"Sem checklist no perfil: {fase.gate}.")
    else:
        linhas.append(f'Checklist do {gate.nome} (pendência com "{gate.marcador_pendencia}" no destino bloqueia):')
        scripts = [f"{item.numero} {item.verificacao}" for item in gate.itens if item.tipo == "script"]
        if scripts:
            linhas.append("Itens de script: " + ", ".join(scripts) + ".")
        linhas += [f"{item.numero}. {item.tipo}: {item.criterio}" for item in gate.itens if item.tipo != "script"]
    linhas.append(
        "Sistemas do cliente, citáveis em qualquer camada: "
        + (", ".join(perfil.texto.sistemas_do_cliente) or "nenhum listado") + "."
    )
    return _texto(linhas)


def _assessor(perfil: Perfil) -> str:
    c = perfil.caminhos
    return _texto([
        f"Projeto: {perfil.nome}.",
        f"Registro da decisão: Ruling em {c.decisoes}; ADR em {c.adrs}. Estudos: {c.estudos}/. "
        f"Atritos do harness: {c.atritos}.",
        "Fontes locais, da mais forte à mais fraca: "
        + ", ".join(["decisões registradas e CLAUDE.md", *(f"{fonte}/" for fonte in c.fontes)]) + ".",
        "Camadas, com o gate e a regra de cada uma (a decisão entra na camada cuja regra a admite):",
        *_regras(perfil),
        "Sistemas do cliente, citáveis no estudo: " + (", ".join(perfil.texto.sistemas_do_cliente) or "nenhum listado") + ".",
        "Nomes duplos já vistos: " + ("; ".join(perfil.texto.nomes_duplos) or "nenhum") + ".",
    ])


def _com_molde(perfil: Perfil, padrao: str) -> str:
    """O padrão, seguido do molde do primeiro par do `mapa` com o padrão igual; sem par, só o padrão."""
    molde = next((molde for par, molde in perfil.moldes.mapa if par == padrao), None)
    return padrao if molde is None else f"{padrao} (molde {molde})"


def _gerar_modulos(perfil: Perfil, raiz: Path) -> str:
    """A fase atual do STATUS.md com os itens `ligados` e `ids-cobertos` do gate. Sem `ligados`: ForaDaFase."""
    c = perfil.caminhos
    fase = perfil.fase_por_id(estado.ler(raiz / c.status, perfil)["Fase"])
    gate = perfil.gates.get(fase.gate)
    itens = [] if gate is None else list(gate.itens)
    ligados = [i for i in itens if i.tipo == "script" and i.verificacao == "ligados"]
    if gate is None or not ligados:
        raise ForaDaFase(f"{fase.gate} sem item ligados; a skill não se aplica à fase {fase.id}")
    cobertos = [i for i in itens if i.tipo == "script" and i.verificacao == "ids-cobertos"]
    trocas = "; ".join(f"{antigo} → {novo}" for antigo, novo in perfil.moldes.trocas_de_nome.items())
    fontes = [
        caminho
        for anterior in perfil.fases[: perfil.ids_das_fases.index(fase.id) + 1]
        for caminho in anterior.obrigatorios
    ]
    return _texto([
        f"Projeto: {perfil.nome}. Trocas de nome do molde para o documento: {trocas or 'nenhuma'}.",
        f"Pasta do planejamento: {c.planejamento}/. Moldes: {perfil.moldes.pasta}/. Estado: {c.status}. "
        f"Pendências: {c.backlog}. Decisões: {c.decisoes}. Rascunho: {c.rascunho}.",
        f"Fase atual: {fase.id} ({fase.gate}): {fase.regra}",
        f'Pendência com "{gate.marcador_pendencia}" no destino bloqueia o {gate.nome}.',
        *(
            f"Item {i.numero} ligados: "
            + juntar(_com_molde(perfil, padrao) for padrao in i.parametros["documentos"])
            + ", cada um linkado por um "
            + juntar((_com_molde(perfil, padrao) for padrao in i.parametros["por"]), "ou")
            + "."
            for i in ligados
        ),
        *(
            f"Item {i.numero} ids-cobertos: todo {juntar(i.parametros['prefixos'])} citado em "
            f"{juntar(i.parametros['documentos'], 'ou')}."
            for i in cobertos
        ),
        "Fontes, aprovadas antes da geração: " + (juntar(fontes) or "nenhuma") + ".",
        f"Glossário: {perfil.texto.glossario}.",
        "Dúvidas que mudam o escopo: " + (", ".join(perfil.texto.duvidas_de_escopo) or "nenhuma listada") + ".",
        "Sistemas do cliente, citáveis em qualquer camada: "
        + (", ".join(perfil.texto.sistemas_do_cliente) or "nenhum listado") + ".",
        "Nomes duplos já vistos: " + ("; ".join(perfil.texto.nomes_duplos) or "nenhum") + ".",
        *([f"Fronteira do MVP na camada: {fase.fronteira}."] if fase.fronteira else []),
    ])


_BLOCOS = {
    "assessor": lambda perfil, raiz: _assessor(perfil),
    "gate-fase": _gate_fase,
    "gerar-modulos": _gerar_modulos,
    "refinar-documento": lambda perfil, raiz: _refinar_documento(perfil),
}


def bloco(perfil: Perfil, skill: str, raiz: Path) -> str:
    """Bloco "Este projeto" da skill, terminado em quebra de linha. Skill sem bloco lança SkillDesconhecida.

    Os da `gate-fase` e da `gerar-modulos` leem o STATUS.md da `raiz`; ilegível, estado.EstadoInvalido sobe.
    Na fase sem item `ligados`, o da `gerar-modulos` lança ForaDaFase.
    """
    montar = _BLOCOS.get(skill)
    if montar is None:
        raise SkillDesconhecida(f"skill sem bloco no perfil: {skill}; as que têm: {juntar(sorted(_BLOCOS))}")
    return montar(perfil, raiz)
