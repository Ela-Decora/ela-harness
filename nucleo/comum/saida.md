# Moldes de saída do harness

Formato do que o usuário lê no chat: o resumo do pacote, o resumo do lote, o resumo das mudanças, a rodada da entrevista, o relato da revisão, a mensagem de aprovação do pacote, a mensagem de aprovação do lote, a proposta de módulos, a entrega da geração, o checklist do gate, o parecer do assessor, a linha do início da sessão e o próximo passo. O passo que produz uma dessas saídas lê este arquivo na hora de escrever. Vale mesmo com o modo caveman ligado.

## Regras comuns

1. A primeira linha resume, com contagens.
2. O que depende do usuário vem primeiro.
3. Cada grupo traz a contagem no título; grupo vazio não aparece.
4. Uma linha curta por item: **onde** · rótulo; na linha de baixo, o problema → o resultado.
5. Rótulos em minúsculas e sempre os mesmos: `bloqueia`, `atenção`, `sugestão`. Vêm do achado: BLOQUEIA, ATENÇÃO e SUGESTÃO.
6. Todo recusado traz o motivo: `Ruling AAAA-MM-DD`, `fora do escopo da <pendência>`, `contradiz decisão sua` ou `fora da camada`.
7. Sem emoji. Negrito só em onde, nos títulos de grupo e na opção recomendada.
8. Na primeira aparição na mensagem, cada ID e cada sigla vêm com o título ou o significado entre parênteses, pela saída de `harness.py legenda --ids`.
9. Uma ideia por frase; uma frase por linha nos itens.

## Resumo do pacote

Passo 1 de um pacote, antes da chamada da ferramenta de opções com a composição, o resumo e a fronteira.

```
**Pacote <nome do primeiro documento> · <N> documentos** — <s> de <t> seções com fonte; <d> decisões para você

**<documento>** · <s1> de <t1> seções com fonte
Falta decidir: <tema>, <tema> (ou "nada")

**<documento>** · <s2> de <t2> seções com fonte
Falta decidir: <tema> (ou "nada")

**O que eu inferi (<i>)**
- **<documento> · <seção>** — <inferência em uma frase>

**Composição**
Entram: <documento> (<seção do módulo que o cria>), …
Ficam de fora: <documento linkado> (<motivo>), … ou "nada"
```

As seções com fonte saem do mapa de cada documento; "Falta decidir" lista os temas da fronteira da entrevista. O que vier do rascunho ou de resposta anterior do usuário entra no mapa, não em "O que eu inferi". Os IDs e as siglas do resumo levam a legenda (regra 8).

## Resumo do lote

Passo 1 de um lote, antes da chamada da ferramenta de opções, no lugar do resumo do pacote. As camadas e a trava vêm do `harness.py afetados`.

```
**Lote <prefixo>-NN (<título da pendência>) · <N> documentos, camadas <a> a <b>** — <d> decisões para você
**Escopo:** <a mudança pedida, em uma frase>

**Camada <n>**
- <documento> · <seções afetadas>
- <documento> · <seções afetadas>

**Camada <n+1>**
- <documento> · <seções afetadas>

**Ficam de fora (<k>)**
- <documento> · <motivo: vira nota, resta em <destino>>
```

O grupo "Ficam de fora" traz o documento que o `afetados` achou fora do destino, com o motivo `vira nota resta em <destino>`; sem nenhum, o grupo não aparece. Cada decisão para o usuário segue o molde da rodada da entrevista.

## Resumo das mudanças

Arquivo que o modelo escreve em `.harness-aprovacao/resumo.md`, a partir do esqueleto de `harness.py versao resumo`, e mostra ao usuário no passo da aprovação, do pacote e do lote. Uma entrada por mudança, não por seção.

```
**<Lote <prefixo>-NN | Revisão <documento>> · <M> mudanças em <N> documentos**

**1. <o que mudou, uma frase>**
Na prática: <o efeito para quem usa o sistema, uma frase>
Onde: <documento> · <seção>; <documento> · <seção>

**2. <o que mudou, uma frase>**
Na prática: <o efeito, uma frase>
Onde: <documento> · novo
```

- A linha `Onde:` fica sozinha na linha, sem marcador de lista e sem negrito: é a que o `harness.py versao resumo --conferir <arquivo>` lê. A seção é o título que o esqueleto traz, sem o ` · alterada (+n −m)`, o ` · nova` ou o ` · removida` que vêm depois dele, e o documento novo como `<documento> · novo`.
- A mesma mudança em vários documentos é uma entrada, com todos no `Onde:`.
- Uma frase por linha, sem repetir o título da seção na frase.
- Cada ID e cada sigla vêm com a legenda na primeira aparição (regra 8).
- Rode `harness.py versao resumo --conferir <arquivo>` até o `OK:` antes de mostrar o resumo; o `FALTA:` e o `SOBRA:` pedem a entrada ou a linha que ficou errada.

## Rodada da entrevista

Reserva em texto da ferramenta de opções: vale quando ela não está disponível, quando o usuário a recusa ou quando a rodada tem pergunta sem opções naturais. Até 4 perguntas por rodada.

```
**Rodada <n> · <k> perguntas** — responda assim: `1a 2c 3b`

**P1 · <seção do molde>**
<pergunta completa>
*Por que importa:* <uma frase>
- **a) <opção> ← recomendo:** <motivo em uma frase>
- b) <opção>
- c) Outra resposta

**P2 · <seção do molde>**
(...)

---
Fica para a próxima: <decisões que dependem desta rodada, ou "nada">
```

A opção recomendada fica no lugar dela na lista, em negrito, com "← recomendo:". "Outra resposta" é sempre a última.

## Relato da revisão

```
**Revisão · rodada <n>** — <N> achados: <c> corrigidos, <r> recusados, <v> para você

**Para você (<v>)**
1. **<onde>** · <rótulo>
   <problema em uma frase>
   - **a) <opção> ← recomendo:** <motivo>
   - b) <opção>

**Corrigidos (<c>)**
- **<onde>** · <rótulo>
  <problema> → <o que mudou>

**Recusados (<r>)**
- **<onde>** · <rótulo>
  <o que o achado pedia> → <motivo>
```

Sem achados: `**Revisão · rodada <n>** — sem lacunas.` Na rodada 2, o resumo vira `<A> achados anteriores: <a> resolvidos, <b> não resolvidos; <N> novos`, e os não resolvidos entram em "Para você" ou "Recusados". Os itens de "Para você" são numerados para a resposta curta ("1: administrador", ou "1a"); cada um traz as opções, e a recomendada fica em negrito, com "← recomendo:".

- Os títulos dos grupos são estes três, com estas palavras: "Para você", "Corrigidos" e "Recusados". A primeira linha usa o travessão e as mesmas palavras.
- O rótulo é só uma das três palavras da regra 5; o tipo do problema vai na linha de baixo, nunca no lugar do rótulo.
- Cada linha "Não verificável" do revisor é um item de "Para você", com o rótulo `atenção`, e conta no `<v>` e no `<N>`; a primeira linha não traz contagem à parte.
- O "Para você" vai sempre no molde, mesmo com um item só, nunca resumido numa frase corrida.
- Num pacote, o onde começa pelo nome do documento (`<documento> · <seção>`), e os achados entre documentos levam `pacote` no lugar dele; num lote, `lote`.

## Mensagem de aprovação do pacote

Passo 6 de um pacote, depois do `harness.py passo 6`. A aprovação é a palavra do usuário escrita no chat, nunca uma opção da ferramenta de opções.

```
Pacote `<nome do primeiro documento>` refinado: <N> documentos.
- `<caminho>`: <s> seções, <m> `[A CONFIRMAR]` (<seção de cada um>)
- `<caminho>`: <s> seções, <m> `[A CONFIRMAR]` (<seção de cada um>)
Revisão do subagente: <veredito>, <K> rodada(s).
Pesquisa pendente: <documento · seção>, ….
Revise os arquivos e responda "aprovado", "mudar <documento>: <o quê>" ou "tirar <documento> do pacote".
A aprovação vale só para os <N> documentos listados, não para o próximo pacote nem para o gate da camada.
```

A frase "Pesquisa pendente" só entra quando alguma seção tem `[A CONFIRMAR: pesquisa pendente]`. Depois de um "mudar", o resumo de `harness.py versao resumo --desde-marcada` vem antes da mensagem.

## Mensagem de aprovação do lote

Passo 6 de um lote, depois do `harness.py passo 6`. A aprovação é a palavra do usuário escrita no chat, nunca uma opção da ferramenta de opções.

```
Lote <prefixo>-NN (<título da pendência>) revisado: <N> documentos em <c> camadas.
Revisão do subagente: <veredito>, <K> rodada(s) por camada.
Responda "aprovado", "mudar <documento>: <o quê>", "tirar <documento> do lote" ou "ver <documento>", para o diff seção por seção.
A aprovação vale só para os <N> documentos deste lote.
```

O resumo das mudanças vem antes da mensagem. O "ver <documento>" roda `harness.py versao ver <documento>`. Depois de um "mudar", o resumo de `harness.py versao resumo --desde-marcada` vem antes da mensagem.

## Proposta de módulos

Passo 2 da `gerar-modulos`, antes da rodada: a proposta vai sempre ao usuário, também sem dúvida.

```
**Proposta · <M> módulos** — <r> RF, <e> entidades, <t> telas; <d> dúvidas para você

**Por que <M>:** <o Ruling, a linguagem do domínio ou o tamanho, em uma frase>

**<módulo>** · <n> RF: <IDs>
Mantém: <entidades>
Só lê: <entidades, ou "nada">
Telas: <telas>

**Descartadas (<k>)**
- <alternativa> — <motivo em uma frase>
```

## Entrega da geração

Passo 5 da `gerar-modulos`. Os rascunhos ficam sem commit: entram no git com a aprovação do pacote.

```
**Geração · <M> módulos, <N> documentos em rascunho** — <c> [A CONFIRMAR]; <r> Rulings e <p> pendências registrados

**<módulo>** · pacote de <n> documentos (ou "dividido em <k> pacotes")
- <caminho> · <c1> [A CONFIRMAR]: <motivos, ou "nenhum">

**Recomendadas sem pergunta (<s>)**
- <decisão> · Ruling <AAAA-MM-DD>

**Registrados (<r + p>)**
- Ruling: <o quê>
- <ID da pendência>: <texto> → <destino>

Próximo: /ela-harness:refinar-documento <primeiro módulo>
```

Grupo vazio não aparece.

## Checklist do gate

```
**Gate <Gn> · <fase>** — <T> itens: <p> passam, <a> atenção, <b> bloqueiam

**Bloqueiam (<b>)**
- **<n> · <item curto>** — <evidência> (`<arquivo:linha>`)
  - <segundo problema do mesmo item> (`<arquivo:linha>`)

**Atenção (<a>)**
- **<n> · <item curto>** — <evidência> (`<arquivo:linha>`)

**Passam (<p>)**
- **<n> · <item curto>**

**Informativo**
- **<n> · [A CONFIRMAR]** — <documento> <contagem>, …
- **Travam a próxima camada** — <arquivo:linha — motivo>, … ou "nenhum"
- **Não verificável** — <o que depende de outro artefato ou de resposta do cliente>

---
Veredito: <PASS | CONCERNS | FAIL>. Responda "aprovado", ou "dispenso o N: motivo" para cada item que bloqueia.
```

`<T>` soma `<p>`, `<a>` e `<b>`: os itens de script, de revisor e de leitor frio com veredito. O item informativo e o humano ficam fora das contagens. Script: PASS passa, FAIL bloqueia, INFO é informativo. Revisor: PASS passa, CONCERNS é atenção, FAIL bloqueia. Leitor frio: PASS passa e FAIL bloqueia sem dispensa; a evidência é a linha dele na saída do `harness.py gate`. Item de script sem `arquivo:linha` leva a evidência da saída do `harness.py gate`.

Item com mais de um problema (o revisor devolve uma linha por problema, com o mesmo número) fica numa entrada só: o primeiro problema na linha do item, os demais em sub-itens, cada um com a própria evidência; o grupo é o do pior veredito. As duas linhas extras do revisor, `[A CONFIRMAR] que travam a próxima camada` e `Não verificável`, entram em Informativo, uma entrada cada, e não contam em `<T>`; a de "Travam" fica fora quando o revisor diz "nenhum".

## Gabarito do leitor frio

O arquivo fica em `<caminhos.leitor_frio>/<gate>-<AAAA-MM-DD>.md`, fora da pasta do planejamento. As perguntas saem das `[leitor_frio] perguntas` do perfil: as que têm `{ficha}` valem para uma ficha de cada marco, e as sem marcador, uma vez só. O Gabarito é escrito antes do leitor e confirmado pelo usuário; o Resultado entra depois, na mesma numeração.

```
# Leitor frio · <gate> · <AAAA-MM-DD>

## Gabarito
1. <pergunta>
   - Resposta: <resposta>
   - Fonte: `<arquivo:linha>`

## Resultado
Exportação: <commit> · formato <n> · sha256:<12 hexadecimais>
Leitor: <s> s, <saída> tokens de saída, US$ <custo>, <turnos> turnos, <k> negações
1. <a corrigir | certa | errada: <motivo> | não achou: <motivo>>
   > <resposta do leitor, linha a linha>
Saída inteira do leitor:
> <só com alguma pergunta sem resposta: a saída do leitor, linha a linha>
```

O `harness.py passagem leitor <gabarito>` grava o Resultado com `a corrigir` em cada item; o modelo propõe o veredito, e o usuário confirma. Com a pergunta `sem resposta`, o modelo procura a resposta dela na saída inteira do leitor antes de propor `não achou`.

## Parecer do assessor

```
**Assessor · <tema>** — <k> opções, recomendo a <letra>; decisão entra em <camada>, como <Ruling | ADR>

**Para você**
<pergunta de decisão em uma frase>

**Opções**
- **a) <opção> ← recomendo:** <motivo em uma frase>
  prós: <uma linha> · contras: <uma linha> · custo: <uma linha>
- b) <opção>
  prós: <uma linha> · contras: <uma linha> · custo: <uma linha>

**Custo de errar a recomendada:** <uma frase>
**Depende de você:** <o que o estudo não decide, uma linha cada, ou "nada">
**Sem fonte:** <fatos sem fonte, ou "nenhum">

Estudo: <caminho>. Responda com a letra, ou "adiar".
```

A opção recomendada fica no lugar dela, em negrito, com "← recomendo:". Pesquisa que não chegou no prazo entra em "Sem fonte" como `pesquisa em andamento`. O parecer pode usar termo técnico em qualquer camada: quem o lê é o usuário.

## Linha do início da sessão

```
Planejamento · <Fase> · <nome do arquivo do documento, ou "nenhum documento"> [(passo N)] · Próximo: <linha curta>
Ambiente: <FALHA ou AVISO do harness.py ambiente> · ...
```

É o `systemMessage` do hook do início da sessão: até 2 linhas e 300 caracteres, e não sai depois de compactar. Num pacote, o documento é o primeiro, com `(+<N> no pacote)`. A segunda linha só aparece quando o ambiente falha ou avisa.

## Próximo

```
Próximo: [consertar: ]<ação recomendada>
  <motivo>
Pré-checagem do <gate>: <n> FAIL | sem FAIL | não rodou: <motivo>
  <item> <verificação>: FAIL: <resumo>   ← até 3
  +<k> FAIL: harness.py gate <gate> --verbose
Depois:
  <ação>  (<motivo>)                      ← até 3
  <o resto resumido>
Revisões <marcador>: <n> pendências em <m> documentos aprovados (--verbose)
Atenção: <item> · <item>
```

É a saída do `harness.py proximo`: até 12 linhas sem `--verbose`. Consertar vem antes de tudo: enquanto houver o que consertar, ele é o recomendado. Na fase sem nenhum documento do `por` do item `ligados` e com os obrigatórios aprovados, o recomendado é `/ela-harness:gerar-modulos`. O resto resumido conta os módulos e os rascunhos, traz o obrigatório, a revisão antes de um arquivo e o documento novo como `<nome> (<motivo>)`, e a pendência sem documento e o gate pela ação. A pré-checagem só sai no comando, com o gate recomendado: os itens de script dele, sem o leitor frio, com os FAIL, até 3 e o `+<k>`, ou todos com `--verbose`; o hook e o `fechar` não a rodam. Grupo vazio não aparece.
