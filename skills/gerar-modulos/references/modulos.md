# Módulos: princípios e escrita

Lido na proposta (passo 2), antes de escrever os módulos (passo 3) e pelo revisor do `refinar-documento`. Cada princípio é um critério: o achado do revisor cita o princípio pelo nome em negrito. De onde vêm: [fontes.md](fontes.md).

## Quantos módulos

- **Os Rulings mandam.** Um Ruling vigente sobre módulos ("um módulo só", "um módulo por área da empresa") decide antes de qualquer heurística abaixo. A proposta o cita em "Por que", e as alternativas que o contrariam vão para "Descartadas", com o Ruling como motivo.
- **A fronteira segue a linguagem.** Onde o mesmo termo muda de sentido, ou um grupo de atores usa vocabulário próprio, há outro módulo.
- **Poucos módulos.** O menor número que respeita as fronteiras; mais um módulo só com motivo dito.
- **Núcleo, suporte ou genérico.** Entra como argumento quando ajuda a decidir se uma parte é módulo próprio: a parte que diferencia o produto é núcleo; a que todo produto parecido resolve igual é genérica.

## O que cada módulo junta

- **Cada entidade tem um dono.** O módulo que a cria e a muda a mantém; os outros só a leem e o dizem, na lista própria.
- **Cada tela fica no módulo da tarefa principal dela.** A tela que serve a dois módulos fica num e é citada no outro, em "Relação com outros módulos".
- **Cada RF em ao menos uma funcionalidade.** A funcionalidade é pequena, independente e testável, com aceite: o critério do revisor do gate.
- **A relação com outros módulos é curta.** O que um consome do outro, por funcionalidade ou por entidade. Com um módulo só, uma linha que o diz, com o Ruling.

## O arquivo

`modulo-<nome>.md`, com `<nome>` em minúsculas, sem acento, palavras separadas por hífen, na pasta do padrão do `por` do item `ligados`. Seção a seção:

- "Propósito do módulo": o que ele entrega e por que agrupa o que agrupa, com o Ruling da proposta e a data.
- "Telas que o compõem": um link por tela que ele mantém, `- [<tela>](../<pasta das telas>/tela-<nome>.md)`.
- "Entidades envolvidas": um link por entidade que ele mantém, `- [<entidade>](../<pasta das entidades>/entidade-<nome>.md)`; depois, a lista "Entidades que este módulo só lê:", com os links, ou "nenhuma". O pacote do `refinar-documento` lê essa lista para deixar de fora o que é de outro módulo.
- "Funcionalidades": `### Funcionalidade FN-<MÓD>-NN: <nome>`, com o código do domínio principal dos RF do módulo e a numeração sequencial. Cada uma com "O que faz", "Para que serve", "Depende de" (as FN por ID, os outros módulos, ou `—`) e "Aceite", de 1 a 5 itens numerados, cada um com a condição, o resultado que se vê ou se mede e o RF ou a RN que ele prova. O RF de outro domínio entra numa funcionalidade do módulo que o atende, com o mesmo código do módulo.
- "Relação com outros módulos": como acima.
- "Stack técnica do módulo": a tabela do molde, com `[A DEFINIR no Avançado]` em toda célula da coluna "Escolha" e o motivo da espera em "Por quê"; a escolha é da camada 3, por ADR.

Os títulos são os do molde, na ordem, sem comentário `<!-- -->` sobrando.
