"""Texto gerado do harness de planejamento (spec do porte 1, §9.1): as partes do `CLAUDE.md` que são do harness, com
os valores do perfil.

O `texto` devolve o corpo de `.claude/harness/gerado/planejamento.md`, sem o cabeçalho de gerado, que é do `gerador`.
São seis seções, na ordem do `CLAUDE.md` do projeto de origem: o mapa do harness, o ciclo, os IDs e os marcadores, o
que não fazer no ciclo, os gatilhos e o que preservar ao compactar. O texto fixo é o daquele `CLAUDE.md`, palavra por
palavra; do perfil vêm as fases e os gates, os caminhos, os moldes, o prefixo da pendência, as formas dos IDs e o
último gate, e as skills levam o prefixo do plugin. A linha da legenda só sai com `caminhos.legenda`, e as do
manifesto e do `passagem publicar`, só com `[passagem]`. As linhas do trabalho no próprio harness (spec do porte 1,
§9.4) ficam de fora. O `CLAUDE.md` do projeto puxa o arquivo pela `LINHA_DO_CLAUDE_MD`.
"""
from __future__ import annotations

import posixpath

import comum
from perfil import Perfil

LINHA_DO_CLAUDE_MD = "@.claude/harness/gerado/planejamento.md"

_POR_EXTENSO = ("uma", "duas", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez")


def por_extenso(n: int) -> str:
    """O número no feminino, de `uma` a `dez`; fora disso, o próprio número."""
    return _POR_EXTENSO[n - 1] if 1 <= n <= len(_POR_EXTENSO) else str(n)


def _skill(nome: str) -> str:
    return f"/{comum.PREFIXO_DAS_SKILLS}{nome}"


def _arquivo(caminho: str) -> str:
    """No texto do ciclo, só o nome do arquivo, sem a pasta."""
    return posixpath.basename(caminho)


def _camadas(perfil: Perfil) -> str:
    fases = perfil.fases
    pastas = " → ".join(
        [f"`{perfil.caminhos.planejamento}/{fases[0].id}/`"] + [f"`{fase.id}/`" for fase in fases[1:]]
    )
    if len(fases) == 1:
        return f"- {pastas}: uma camada, fechada pelo gate {fases[0].gate}."
    gates = comum.juntar(fase.gate for fase in fases)
    return f"- {pastas}: {por_extenso(len(fases))} camadas, nesta ordem, fechadas pelos gates {gates}."


def _formas(perfil: Perfil) -> tuple[str, ...]:
    """As `ids.formas`; sem elas, `<padrão>-NN` por padrão, que é `<prefixo>-NN` quando o padrão é o prefixo."""
    return perfil.ids.formas or tuple(f"{padrao}-NN" for padrao in perfil.ids.padroes)


def _mapa(perfil: Perfil) -> list[str]:
    caminhos = perfil.caminhos
    linhas = [
        _camadas(perfil),
        f"- `{perfil.moldes.pasta}/`: moldes; `harness.py molde <alvo>` diz qual copiar.",
        f"- `{caminhos.rascunho}`: rascunho bruto do autor, arquivo único. É entrada, não estado. Leia só o trecho "
        "pertinente ao documento em edição. A seção de informação nova recebe acréscimos por "
        "`harness.py registrar relato`.",
        f"- `{caminhos.status}`: estado curto do planejamento (fase, documento, passo, rodada, próximo passo, gates, "
        "versão em aprovação), injetado no início da sessão pelo hook. Muda só por "
        "`python3 .claude/harness/harness.py passo <n>`, ao fechar cada passo do ciclo, e por `harness.py estado set` "
        "para documento, pacote, fase, gates e a espera do commit no próximo passo.",
        f"- `{caminhos.backlog}`: pendências `{perfil.ids.prefixo_pendencia}-NN` e status dos artefatos. Leia por "
        "`grep`, não inteiro. Pendência nova entra por `harness.py registrar pendencia`.",
    ]
    if caminhos.legenda:
        linhas.append(f"- `{caminhos.legenda}`: as siglas e os tipos de ID, gerada por `harness.py legenda`; não se "
                      "edita à mão.")
    if perfil.passagem is not None:
        linhas.append(f"- `{perfil.passagem.manifesto}`: o manifesto da última passagem, gravado e commitado por "
                      "`harness.py passagem publicar`.")
    linhas += [
        f"- `{caminhos.decisoes}`: decisões (`Ruling:`), aprovações, abordagens descartadas e trechos do rascunho "
        "processados. Só acréscimos. Leia por `grep`, não inteiro. Ruling novo entra por `harness.py registrar ruling`.",
        f"- `{caminhos.atritos}`: atritos e medições do harness. Numa sessão de planejamento, só se grava ali a seção "
        "Medições, quando uma skill manda; o resto do arquivo não se edita numa sessão de planejamento.",
        f"- `{caminhos.estudos}/`: estudos do assessor, um por tema, com a decisão do usuário e onde ela foi "
        "registrada. A linha `Decisão:` de cada um é lida por `python3 .claude/harness/harness.py estudos`.",
        "- Recusa da guarda, do pre-commit ou da CI: rode o comando que a mensagem indica.",
        f"- `{comum.CAMINHO_PERFIL}`: o que o harness sabe deste projeto (caminhos, fases e gates, padrões de ID, "
        "checklists dos gates). Scripts e skills leem dele.",
    ]
    return linhas


def _ciclo(perfil: Perfil) -> list[str]:
    status = _arquivo(perfil.caminhos.status)
    decisoes = _arquivo(perfil.caminhos.decisoes)
    return [
        f"0. Preparação: o alvo gravado no `{status}`, o arquivo copiado do molde, o dossiê lido e, do "
        f"`{_arquivo(perfil.caminhos.rascunho)}` em que o autor escreve, só o trecho pertinente.",
        "1. Entendimento devolvido: o resumo \"dito × inferido\" e a fronteira do MVP, confirmados ou corrigidos pelo "
        "usuário.",
        "2. Entrevista em rodadas: até 4 perguntas por rodada, pela ferramenta de opções, na fronteira das decisões, "
        "com uma resposta recomendada por pergunta; termina com a fronteira vazia e toda seção do molde com fonte.",
        "3. Versão refinada: escrita no arquivo do molde já copiado; toda inferência sua marcada `[A CONFIRMAR]`; "
        "nenhum placeholder do molde sobra.",
        "4. Checagem e confirmação: `python3 .claude/harness/harness.py checar`, sem argumento para o pacote ou o "
        "documento do STATUS, saída colada; cada `[A CONFIRMAR]` confirmado, tirado ou corrigido pelo usuário antes "
        "do revisor.",
        "5. Revisão por subagente somente leitura: aponta lacunas, não estilo. Até 2 rodadas; termina com \"Sem "
        "lacunas\" ou com cada achado corrigido, recusado com motivo ou levado ao usuário.",
        "6. Aprovação humana: `harness.py passo 6` marca a versão antes de pedir. Só o usuário aprova.",
        f"7. Registro: `harness.py passo 7` confere a versão e grava `aprovado` no "
        f"`{_arquivo(perfil.caminhos.backlog)}`; pendências e `{decisoes}`; a aprovação vale como pedido de commit: "
        "o commit convencional do projeto sai sem nova pergunta, seguido de `harness.py fechar`, a menos que o "
        "usuário peça para esperar.",
        "",
        "Pacote: um documento e os que ele cria passam juntos pelos sete passos, com uma checagem, um revisor e "
        f"uma aprovação para todos; o `{status}` traz a lista na linha `Pacote`. O lote é a revisão, num ciclo só, "
        f"dos aprovados que o destino de uma pendência cita; o `{status}` traz a origem dele na linha `Lote`.",
        "",
        "A aprovação de um documento ou de um pacote autoriza só o commit dele, não o próximo nem o gate.",
    ]


def _como_escrever(perfil: Perfil) -> list[str]:
    ids = comum.juntar(f"`{forma}`" for forma in _formas(perfil))
    return [
        f"- IDs: {ids}, como nos moldes. Datas em `AAAA-MM-DD`.",
        "- Marcadores: `[A CONFIRMAR]` para inferência sua; o que o usuário confirma sai do texto, sem marcador.",
        "- Dúvida que muda o escopo ou a ideia principal: pare e pergunte. Dúvida menor: escreva e marque "
        "`[A CONFIRMAR]`.",
    ]


def _o_que_nao_fazer() -> list[str]:
    return [
        "- Documento de planejamento passa pelo ciclo acima, também quando o usuário pede `brainstorming`, "
        "`writing-plans` ou `domain-modeling`.",
        "- `brainstorming`, `writing-plans`, `domain-modeling` e `research` rodam só quando o usuário os pede pelo "
        "nome. O `skillOverrides` não age sobre skills de plugin; esta regra vale acima do lembrete do superpowers de "
        "invocar skill a qualquer indício.",
        "- Documento aprovado e gate aberto só com a palavra do usuário no chat.",
    ]


def _gatilhos(perfil: Perfil) -> list[str]:
    linhas = [
        f"- Ao começar ou retomar um documento de planejamento: `{_skill('refinar-documento')} <caminho do "
        "documento>` (só o usuário invoca).",
    ]
    if any(i.tipo == "script" and i.verificacao == "ligados" for g in perfil.gates.values() for i in g.itens):
        linhas.append(
            f"- Quando o `harness.py proximo` recomendar `{_skill('gerar-modulos')}` (só o usuário invoca): ela gera "
            "em rascunho os documentos do item `ligados` do gate e os que os ligam, prontos para o "
            f"`{_skill('refinar-documento')}`.")
    linhas += [
        f"- Ao fechar uma camada: `{_skill('gate-fase')} <Gn>` (só o usuário invoca): checklist por script e "
        "revisor, aprovação só com a palavra do usuário, registrada em "
        f"`{_arquivo(perfil.caminhos.decisoes)}` e no gate.",
        "- Ao comparar tecnologias, fornecedores ou abordagens numa decisão: "
        f"`{_skill('assessor')} <tema>` (só o usuário invoca): opções com trade-offs e estudo gravado; a decisão é "
        "do usuário e entra pelo ciclo.",
    ]
    if perfil.passagem is not None:
        linhas.append(f"- Depois do {perfil.fases[-1].gate} ou de uma revisão aprovada, só a pedido do usuário: "
                      "`harness.py passagem publicar`; o `--enviar` depois da confirmação dele.")
    linhas += [
        "- Sem saber o próximo passo: `python3 .claude/harness/harness.py proximo`.",
        "- Na primeira resposta da sessão: repita a linha `Próximo:` calculada do bloco do início (a que vem depois "
        "dos últimos commits, não o `Proximo:` do STATUS), porque nem todo cliente do Claude Code mostra ao usuário "
        "o aviso do hook.",
    ]
    return linhas


def texto(perfil: Perfil) -> str:
    """O corpo do texto gerado do harness de planejamento, sem o cabeçalho de gerado, terminado em fim de linha."""
    secoes = (
        ("Mapa do harness", _mapa(perfil)),
        ("Ciclo por documento ou pacote (preparação e 7 passos)", _ciclo(perfil)),
        ("Como escrever: IDs e marcadores", _como_escrever(perfil)),
        ("O que não fazer no ciclo", _o_que_nao_fazer()),
        ("Gatilhos", _gatilhos(perfil)),
        ("Ao compactar, preserve", [
            "Fase atual, documento em edição e passo do ciclo em que parou, decisões que o usuário tomou nesta "
            "sessão, dúvidas abertas, o que já foi aprovado e o hash de `Versao-aprovacao`, se houver.",
        ]),
    )
    return "\n\n".join(f"## {titulo}\n\n" + "\n".join(linhas) for titulo, linhas in secoes) + "\n"
