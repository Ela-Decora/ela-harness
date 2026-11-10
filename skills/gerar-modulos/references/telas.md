# Telas: princípios e escrita

Lido no inventário (passo 1), antes de escrever as telas (passo 3) e pelo revisor do `refinar-documento`. Cada princípio é um critério: o achado do revisor cita o princípio pelo nome em negrito. De onde vêm: [fontes.md](fontes.md).

## O inventário

Para cada ator, os RF que ele realiza, agrupados pelo lugar onde ele faz a tarefa: uma tela atende a vários RF quando o ator os faz no mesmo lugar, sem sair dele. A consulta que dois atores fazem do mesmo jeito é uma tela só, com a permissão de cada um. Cada tela do inventário leva o ator, os RF e as entidades que mostra ou altera.

## Os princípios

- **Nasce de um ator e de uma tarefa.** "Propósito" diz quem chega, em que situação e o que precisa fazer, em uma ou duas frases, com o RF.
- **Componentes por prioridade.** Em "Componentes de UI", o que o ator precisa ver e fazer primeiro vem primeiro. Cada componente diz o dado que mostra, como atributo de uma entidade, ou a ação que dispara.
- **Toda ação tem destino com nome.** Em "Navegação", um item por ação: `- <ação> → [<tela>](tela-<nome>.md)` ou `- <ação> → fica na tela`. Ação sem destino é decisão por tomar: vira pergunta ou `[A CONFIRMAR: motivo]`.
- **Estados.** A tabela de "Estados" traz vazio, carregando, erro, sucesso, sem permissão e os estados da entidade que a tela mostra, cada um com o gatilho, o que aparece e a ação disponível. O que não se aplica sai da tabela, com o motivo numa linha abaixo dela (`Não se aplica: <estado>, <motivo>.`), sem forçar estado só para cumprir a lista.
- **Sem beco sem saída.** De todo estado há uma ação, na coluna "Ação disponível".
- **A ação destrutiva pede confirmação ou deixa desfazer.** Apagar, cancelar ou marcar algo sem volta diz qual dos dois, na tabela ou no fluxo.
- **O erro diz o que houve, por quê e como sair.** A linha de erro da tabela diz a mensagem pelo sentido, não pelo código.
- **Nenhuma entidade isolada.** Toda entidade aparece em ao menos uma tela, mostrada ou alterada; a que não aparece pede decisão registrada, por Ruling, de que não precisa de tela.
- **Os nomes do glossário, sem stack.** Os rótulos, os estados e o fluxo usam os termos do glossário de "Este projeto". Framework, biblioteca, componente pronto e formato de requisição ficam para a camada 3.

## O arquivo

`tela-<nome>.md`, com `<nome>` em minúsculas, sem acento, palavras separadas por hífen, na pasta do padrão de telas do item `ligados`. As seções, além das acima:

- "Atores que acessam": cada ator, com a permissão dele, pela matriz dos atores.
- "Requisitos atendidos": um item por RF ou RN, com o que a tela faz por ele e o ID entre parênteses no fim: `- <o que a tela faz> (<ID>)`.
- "Fluxo técnico passo a passo": do gesto do ator ao resultado que ele vê, numerado, com o caminho de erro, sem escolher tecnologia.
- "Relação com outras partes": cada entidade que a tela mostra ou altera, por link (`[<entidade>](../<pasta das entidades>/entidade-<nome>.md)`), e o módulo dela, pelo nome.

O projeto com o molde antigo de tela, sem "Estados" e sem "Navegação" (o `harness.py molde` aponta o molde que vale): a tabela de estados entra no fim de "Componentes de UI", e a navegação, em "Relação com outras partes". Os títulos são sempre os do molde, na ordem, sem comentário `<!-- -->` sobrando.
