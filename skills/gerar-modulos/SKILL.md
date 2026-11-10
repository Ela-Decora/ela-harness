---
name: gerar-modulos
description: Gera em rascunho as entidades, as telas e os módulos da camada a partir do escopo aprovado, com o usuário só nas dúvidas, quando o harness.py proximo a recomenda; cada módulo segue depois para o refinar-documento.
disable-model-invocation: true
allowed-tools: Bash(python3 "${CLAUDE_PROJECT_DIR}"/.claude/harness/harness.py perfil *), Bash(python3 .claude/harness/harness.py perfil *)
---

# Gerar os módulos, as entidades e as telas

## Este projeto

!`python3 "${CLAUDE_PROJECT_DIR}"/.claude/harness/harness.py perfil --para gerar-modulos`

Se o bloco acima veio como `[shell command execution disabled by policy]` ou começa por `ERRO`, rode `python3 .claude/harness/harness.py perfil --para gerar-modulos` pelo Bash antes do passo 0; com o `ERRO` ainda, diga o erro ao usuário e pare.

A skill lê o que já foi aprovado e escreve, em rascunho, as entidades, as telas e, por último, os módulos que juntam umas e outras, nos padrões do item `ligados` de "Este projeto". Ela não aprova nada: cada módulo passa depois pelo pacote do `/ela-harness:refinar-documento`, com a checagem, o revisor e a aprovação do usuário. Nos exemplos, `harness.py` abrevia `python3 .claude/harness/harness.py`: escreva cada comando por extenso, com esse caminho, sem variável de shell nem laço `for`, que o Claude Code não confere antes de rodar e nega. Um `afetados` por termo e um `Read` por arquivo.

## Os passos e quando cada um termina

| Passo | Termina quando |
|---|---|
| 0 Preparação | condições conferidas; fontes lidas; rascunhos já existentes nas pastas dos `documentos` listados |
| 1 Inventário | entidades, telas e requisitos listados no chat, cada item com a fonte |
| 2 Proposta e entrevista | proposta de módulos aprovada pelo usuário; dúvidas respondidas ou marcadas; Rulings e pendências registrados |
| 3 Escrita | todos os arquivos escritos pelos moldes: as entidades, as telas e, por último, os módulos |
| 4 Autoconferência | `harness.py checar` rodado e saída colada, sem falha; cobertura conferida |
| 5 Entrega | relato com os arquivos, os pacotes e o comando seguinte |

Três regras sem exceção:

1. Nenhum arquivo é escrito nas pastas do item `ligados` nem do `por` antes de o usuário aprovar a proposta de módulos, com a palavra dele no chat ou, na retomada, o Ruling `Proposta de módulos:` já registrado. A proposta vai sempre a ele, também sem dúvida nenhuma e também quando ele pede para não ser perguntado.
2. Sem commit, sem `harness.py passo` e sem `harness.py estado set`: os rascunhos entram no git com a aprovação do pacote, no passo 7 do `refinar-documento`. A memória da skill é o Ruling da proposta.
3. Decisões e pendências entram por `harness.py registrar`, nunca por Edit no arquivo de decisões nem no de pendências.

## Passo 0: preparação

As condições, nesta ordem; a que falha vira uma mensagem ao usuário e a parada:

1. O bloco tem a linha do item `ligados` (senão, o `ERRO` do bloco já disse, e a skill para).
2. Os obrigatórios da fase estão aprovados na tabela de artefatos do arquivo de pendências: senão, aponte `/ela-harness:refinar-documento <obrigatório>` e pare.
3. Procure, com Grep no arquivo de decisões, o Ruling `Proposta de módulos:` e, com Glob, os documentos que casam o padrão do `por`:
   - nem Ruling nem documento: execução nova; siga;
   - o Ruling, com algum caminho dele ausente no disco: retomada (abaixo);
   - senão (documento do `por` sem o Ruling, ou todos os caminhos do Ruling no disco): diga que os módulos já existem, mande rodar `harness.py proximo` e pare.

Retomada: a execução anterior parou depois da proposta. Leia o Ruling da proposta, os Rulings e as pendências registrados depois dele e os arquivos que ele lista. Não refaça a proposta nem a rodada, não reescreva nem edite os arquivos que já existem, e siga do passo 3, escrevendo só os arquivos do Ruling que faltam no disco; o passo 5 diz o que foi retomado.

As fontes: os obrigatórios aprovados das fases até a atual, lidos inteiros; os Rulings vigentes do arquivo de decisões; as pendências abertas com o marcador do gate (`grep` do marcador no arquivo de pendências), que podem pedir um módulo ou uma entidade pelo nome; e, do rascunho, só os trechos que `harness.py afetados "<termo>"` acha para cada entidade e cada ator. Os arquivos que já existem nas pastas dos `documentos` entram no inventário como estão, e a skill não os reescreve sem perguntar.

## Passo 1: inventário

No chat, três listas, cada item com a fonte (o ID, o nome no `erDiagram`, o ator ou o Ruling):

- **Entidades:** uma por entidade do bloco `erDiagram` do modelo conceitual, com o nome do glossário e o arquivo proposto, passada pelos testes de [references/entidades.md](references/entidades.md). A que falha num teste fica marcada como dúvida, com o teste.
- **Telas:** de cada ator e dos RF que ele realiza, agrupados pelo lugar da tarefa, como diz [references/telas.md](references/telas.md).
- **Requisitos:** todos os IDs dos prefixos do item `ids-cobertos`, com o documento que os define.

## Passo 2: proposta e entrevista

Leia [references/modulos.md](references/modulos.md). A proposta sai no molde "Proposta de módulos" de `${CLAUDE_PLUGIN_ROOT}/nucleo/comum/saida.md`, lido na hora de escrever. Logo depois, uma rodada da ferramenta de opções, até 4 perguntas, a recomendada primeiro, com " (Recommended)" no rótulo e o motivo na descrição, nesta ordem:

1. A proposta de módulos: aprovar, ou uma das descartadas.
2. O modelo lógico: usar as entidades como modelo lógico (recomendada), com o tipo genérico em cada atributo, ou pular, com as entidades sem tipo. Fica fora da rodada quando um Ruling já o respondeu.
3. As dúvidas de fronteira que couberem: a entidade que falhou num teste de [references/entidades.md](references/entidades.md), a entidade ou a tela que serve a dois módulos, a entidade sem tela.

Sem a ferramenta, a rodada vai em texto, no molde "Rodada da entrevista" do mesmo `saida.md`, e a mensagem termina nela: espere a resposta. Rodadas seguintes só para o que a resposta abrir, até três ao todo; o que sobra entra no texto como `[A CONFIRMAR: motivo]`.

Com o pedido do usuário para não perguntar, a rodada tem só a pergunta 1, e a mensagem diz que as outras dúvidas seguem com a recomendada. Depois da resposta, cada dúvida que teria entrado na rodada segue com a recomendada e vira Ruling com `recomendada, sem pergunta, a pedido do usuário` no `--por`.

Registro no ato, depois da resposta e antes de escrever qualquer arquivo:

- `harness.py registrar ruling "Proposta de módulos: <módulo> (<caminho>), com <caminhos das entidades e das telas que ele mantém>; ..." --por "<o porquê da proposta>" --custo "<custo se errado>"`, com todos os caminhos que o passo 3 vai escrever. É o que a retomada lê.
- Um Ruling para o modelo lógico e um para cada dúvida respondida que vale além de um documento.
- A entidade do `erDiagram` que a rodada tira não ganha arquivo nem aparece como relação, e a que ela acrescenta ganha arquivo: nos dois casos, um Ruling com o motivo e uma pendência, `harness.py registrar pendencia "<o modelo conceitual ainda lista a entidade tirada, ou não tem a acrescentada>" --origem <modelo conceitual> --destino "<caminho do modelo conceitual>, <marcador do gate>"`, que pede a revisão dele antes do gate.
- A pergunta que fica aberta vira pendência com o marcador do gate no destino.

## Passo 3: escrita

`harness.py molde <caminho>` aponta o molde de cada arquivo; leia-o antes do primeiro arquivo de cada tipo. A ordem: todas as entidades, por [references/entidades.md](references/entidades.md); depois todas as telas, por [references/telas.md](references/telas.md); por último, todos os módulos, em seguida, por [references/modulos.md](references/modulos.md). Enquanto não há módulo, o `harness.py proximo` segue recomendando esta skill, e a execução interrompida volta a ela.

Os títulos saem do molde, na ordem, e nenhum comentário `<!-- -->` sobra. Cada frase cita a fonte (ID, link, Ruling com a data) ou leva `[A CONFIRMAR: motivo]`. ID de outro documento só se cita, no meio ou no fim da frase: o item que começa por `- <ID>:` define o ID, e o `checar` o recusa como repetido. Os princípios das referências entram nas seções que o molde tem. A regra da fase de "Este projeto" vale no texto inteiro.

## Passo 4: autoconferência

`harness.py checar <arquivos escritos>`, com a saída colada, e correção até nenhuma linha com falha. Depois, a cobertura, por leitura, numa lista no chat: cada RF numa funcionalidade de algum módulo; cada tela e cada entidade linkadas por um módulo; cada entidade mostrada por ao menos uma tela, ou com o Ruling de que não precisa. O item `ligados`, o `ids-cobertos` e o `harness.py dossie` não servem aqui: só veem os documentos da tabela de artefatos ou os aprovados.

## Passo 5: entrega

`harness.py proximo`, e o relato no molde "Entrega da geração" de `${CLAUDE_PLUGIN_ROOT}/nucleo/comum/saida.md`: os arquivos por módulo, com os `[A CONFIRMAR]` de cada um; as dúvidas que seguiram com a recomendada; os Rulings e as pendências registrados; os pacotes, o módulo com até 6 documentos ou a divisão que o pacote do `refinar-documento` vai propor; e a linha `Próximo:` igual à do `harness.py proximo`, `/ela-harness:refinar-documento <primeiro módulo>`. Sem commit.

De onde vêm os princípios: [references/fontes.md](references/fontes.md).
