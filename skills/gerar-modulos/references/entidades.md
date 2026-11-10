# Entidades: princípios e escrita

Lido no inventário (passo 1), antes de escrever as entidades (passo 3) e pelo revisor do `refinar-documento`. Cada princípio é um critério: o achado do revisor cita o princípio pelo nome em negrito. De onde vêm: [fontes.md](fontes.md).

## Os testes do inventário

Cada entidade do bloco `erDiagram` do modelo conceitual passa por estes testes antes de virar arquivo. A que falha num deles vira pergunta da rodada do passo 2, nunca arquivo calado nem entidade tirada calada.

1. **Objeto real.** Tem várias instâncias, atributos próprios, e o usuário se importa com ela por si. A instância única tomada por objeto (a organização que usa o sistema, a loja, a sede) não é entidade. Pergunta: "<NOME> é entidade ou a instância única do sistema?", com "tirar" recomendado quando nenhum RF cria nem muda mais de uma.
2. **Relação escrita como atributo.** O atributo que é só o nome ou o ID de outra entidade é relação: vai para "Relações com outras entidades", nunca para "Atributos principais". Vale também quando o texto do modelo conceitual diz que X "guarda" ou "tem" o nome, o número ou o código de Y: é a relação X → Y, e o atributo não entra. Não pede pergunta.
3. **Provisória.** A entidade que nenhuma tarefa de um ator obriga a guardar estado e a ser reaberta fica como pergunta: "<NOME> precisa existir por si, ou é atributo de <outra>?".
4. **Falta no modelo.** A entidade que um RF, uma RN ou um ator pede e o `erDiagram` não tem também vira pergunta, nunca arquivo calado: o modelo conceitual aprovado é a fonte das entidades, e mudá-lo pede uma pendência com destino nele. Pergunta: "<NOME> falta no modelo conceitual: acrescentar ou deixar fora?", com "acrescentar" recomendado só quando um RF ou uma RN guarda dado dele; ser ator não basta.

## Os princípios da escrita

- **Nada especulativo.** Cada atributo, relação, estado e regra rastreia a um RF, uma RN, um ator ou um Ruling, citado no próprio item. O que não rastreia sai, ou fica com `[A CONFIRMAR: motivo]`.
- **Atributo com o tipo do Ruling do modelo lógico.** Com "usar", cada item de "Atributos principais" é `- <nome>: <tipo genérico>, <o que é> (<fonte>)`, com o tipo entre texto, número, data, data e hora, sim ou não e lista de valores (a lista diz os valores). Com "pular", `- <nome>: <o que é> (<fonte>)`, sem tipo. Tipo de coluna, tamanho e chaves ficam para o DER físico, na camada 3.
- **Relação com cardinalidade e papel.** Cada item de "Relações com outras entidades" diz quantos de cada lado e o papel, com o link da outra entidade: `- Um <entidade> tem muitos [<outra>](entidade-<outra>.md) (<fonte>).` A instância tirada no passo 2 não aparece como relação.
- **Verbo preciso.** As ações e as transições usam o verbo do negócio ("aprovar o pedido", "cancelar a inscrição"), não "atualizar" nem "alterar".
- **O tempo.** "Estados e ciclo de vida" diz os estados e o verbo de cada transição, com um bloco `stateDiagram-v2` quando há mais de dois estados; como a entidade nasce; como sai (arquivar, lixeira, apagar de vez ou apagar por exigência legal), com o motivo; e se guarda histórico. Sem estados: `Sem estados: <motivo>`.
- **Um nome por conceito.** O nome do arquivo, o título e o texto usam o termo do glossário de "Este projeto". Termo novo vira pendência com destino no documento do glossário, que está aprovado.
- **Regras são invariantes.** "Regras e restrições" traz o que vale sempre para a entidade (limites, unicidade, o que não pode mudar), com a RN ou o RF; a regra de uma tarefa fica na tela ou na funcionalidade.

## O arquivo

`entidade-<nome>.md`, com `<nome>` em minúsculas, sem acento, palavras separadas por hífen, na pasta do padrão de entidades do item `ligados`. "Papel na solução" diz o que a entidade representa e o RF que a cria. Os títulos são os do molde, na ordem, sem comentário `<!-- -->` sobrando.

O projeto com o molde antigo de entidade, sem "Estados e ciclo de vida" (o `harness.py molde` aponta o molde que vale): o ciclo de vida entra em "Regras e restrições". Os títulos são sempre os do molde, na ordem.
