# Pacote, registro no ato e conferência de propagação

Um pacote é um módulo com as entidades e telas que ele cria ou compõe: passam juntos pelos sete passos, com uma checagem, um revisor e uma aprovação para todos. Os passos e as duas regras sem exceção continuam os do `SKILL.md`; aqui fica só o que muda. Documento sozinho (um da primeira camada, um sem derivados, um da última) segue sem `Pacote`. Os documentos aprovados que uma mesma pendência cita no destino não são pacote: são o lote, em [lote.md](lote.md). Um pacote aberto por vez; os documentos são escritos por você, nunca por subagente.

## Passo 0: composição

1. `harness.py dossie <módulo>` lista, em "Links que o documento faz", os documentos do planejamento que o módulo linka, com a seção do link e o status de cada um.
2. Módulo em `rascunho`: o pacote é o módulo e os documentos em `rascunho` que ele cria ou compõe. Módulo `aprovado`: só esses derivados, e o módulo vira fonte; se uma pendência aberta tem destino no módulo (`grep` do caminho no arquivo de pendências), pergunte pela ferramenta de opções se é o modo revisão do módulo ou o pacote dos derivados. Sobrando um derivado, ele segue sozinho, sem `Pacote`, com o módulo como fonte; nenhum, diga ao usuário que os linkados em rascunho são de outro módulo, com o caminho de cada um para abrir direto, e pare.
3. No pacote de módulo, quem o módulo cria ou compõe sai do trecho de cada link, não só do título da seção: leia a seção, a frase que abre a lista em que o link está e a anotação da própria linha, como "(módulo X)". Entram as telas e as entidades que o próprio módulo mantém. Ficam de fora o link na seção de relação com outros módulos e o que a lista declara de outro módulo ("Telas de outros módulos que usam o que este módulo mantém") ou que o módulo só lê ("Entidades que este módulo só lê"): são de outro módulo, que só usa ou lê os dados deste.
4. Até 6 documentos; acima disso, proponha dividir em dois pacotes, por exemplo as entidades num e as telas no outro.
5. No pacote de módulo, a ordem da lista é a ordem de escrita: o módulo, quando está no pacote, depois as entidades, depois as telas; entre dois do mesmo tipo, a ordem dos links no módulo.
6. Grave: `harness.py estado set Pacote "<caminhos separados por um espaço>" && harness.py passo 0 --proximo "<o que vem>"`. O primeiro da lista vira o `Documento`. Documento sem arquivo vem do molde. Corrigir a lista é um `estado set Pacote` novo, aceito enquanto não há versão marcada.
7. `harness.py dossie`, sem argumento, monta as fontes do pacote. Leia o molde de cada tipo de documento, o arquivo do dossiê e o módulo de origem inteiro; do rascunho e dos relatórios de pesquisa, só as linhas que o dossiê aponta. Monte o mapa "seção do molde → fonte" de cada documento; os itens de "O que o gate vai cobrar" entram no mapa como exigência da seção.
8. Os fatos que faltam disparam um despacho do `ela-harness:pesquisador-fatos` para o pacote, como [subagentes.md](subagentes.md) diz.

## Passos 1 a 5

- Passo 1: uma mensagem para o pacote, no molde "Resumo do pacote" de `.claude/harness/nucleo/nucleo/comum/saida.md`, e uma chamada da ferramenta de opções com até quatro perguntas: `header` "Composição", "A composição do pacote confere?"; `header` "Resumo", "O resumo e os mapas conferem?"; e a fronteira do MVP, uma vez para o pacote, como [preparacao.md](preparacao.md) diz.
- Passo 2: a fronteira das decisões do pacote inteiro; a mesma decisão em dois documentos vira uma pergunta só. O `header` traz o termo do documento, e a `question`, o documento e a seção. Depois de cada rodada, o registro no ato (abaixo).
- Passo 3: todos os documentos, na ordem da lista. Cada frase cita a fonte (ID, link, decisão com data, relatório de pesquisa) ou leva `[A CONFIRMAR: motivo]`.
- Passo 4: `harness.py checar`, sem argumento, confere a lista. A confirmação dos marcadores do pacote vai em chamadas de até 4 perguntas, com o `header` no termo do documento.
- Passo 5: um despacho do `ela-harness:revisor-requisitos` para o pacote, no bloco "Pacote" de [revisor.md](revisor.md).

## Passo 6: aprovação do pacote

`harness.py passo 6` guarda a cópia de cada documento e grava em `Versao-aprovacao` o hash do manifesto, que tem o hash de cada um. A mensagem fixa é a "Mensagem de aprovação do pacote" de `.claude/harness/nucleo/nucleo/comum/saida.md`. Respostas:

- "aprovado": vale para o pacote apresentado; siga para o passo 7.
- "mudar <documento>: <o quê>": `harness.py passo 3` antes de editar; edite só esse documento; `harness.py checar <documento>` e a confirmação dos marcadores novos dele. Então `harness.py versao resumo --desde-marcada`, que compara com a versão apresentada, e o revisor com `Escopo:` só nele. Antes do `passo 6`, escreva o resumo e confira-o com `--desde-marcada --conferir <arquivo>`: depois de marcar de novo, a cópia já é o disco e a comparação não acha mais nada. Então `harness.py passo 6` de novo, e só o hash dele muda, e o resumo antes da mensagem fixa; os outros documentos não precisam ser relidos.
- "tirar <documento> do pacote": a resposta vale como a autorização para `harness.py versao limpar`; depois, `harness.py estado set Pacote "<lista sem ele>" && harness.py passo 6 --proximo "<o que vem>"`. Ele fica fora da aprovação, com o status que o passo 5 deixou no backlog; se o usuário disser o motivo, ele sobe a escada de `.claude/harness/nucleo/nucleo/planejamento/pendencias.md`, valendo como o "Abrir pendência", com `--causa pedido`, quando nenhuma pendência aberta tem destino nele. Sobrando um documento: `harness.py estado set Pacote — && harness.py estado set Documento <ele> && harness.py passo 6 --proximo "<o que vem>"`, para marcar de novo a versão do que ficou, e ele segue sozinho.

Aprovação parcial ("aprovo A e B") não existe: responda com as duas formas acima. Ao retomar no passo 6 ou 7, `harness.py versao conferir`, sem argumento, confere o pacote e diz qual documento divergiu.

## Passo 7: registro do pacote

`harness.py passo 7` confere cada documento e grava `aprovado` em cada um; se um diverge, nada é gravado, e a saída diz qual. Depois, como num documento sozinho: os trechos do rascunho processados, a marcação "resolvida em" das pendências e os estudos do assessor. Commit sem pedido, um por pacote, no formato da primeira aprovação (`docs(planejamento): pacote <módulo> camada <N>`, com o módulo de origem também quando ele fica fora), com a pasta de pesquisa do pacote. Depois do commit, na mesma chamada: `git commit ... && harness.py fechar`, que confere no HEAD cada documento do pacote e também tira o `Pacote`.

## Registro no ato, com ou sem pacote

Rulings, notas e pendências entram na hora, por comando, nunca por Edit; notas e pendências seguem a escada de `.claude/harness/nucleo/nucleo/planejamento/pendencias.md`:

- `harness.py registrar ruling "<o quê>" --por "<por quê>" --custo "<custo se errado>"`: a resposta que vale além do documento, depois de cada rodada da entrevista e de cada chamada da confirmação, pelo critério do passo 7. Depois dele, `harness.py afetados` com os IDs e termos do Ruling, e, para cada documento `aprovado` da lista fora do escopo, uma nota `resta em <documento>: <o quê>` pela escada, com `--causa cascata` se a resposta abrir pendência.
- O fato do relatório de pesquisa que contradiz uma decisão registrada: no documento do ciclo, vira pergunta; fora dele, sobe a escada, com `--causa pesquisa` se a resposta abrir pendência. A pergunta que fica aberta fica na árvore.
- A decisão que muda outra vira um Ruling novo, com "substitui o Ruling de <data>" no "o quê"; nada é apagado, e o `afetados` e as notas seguem o item do `registrar ruling`.

O que vale só para o documento fica no texto dele. Recusa do `registrar`: corrija o texto (uma linha, sem `|` na pendência e na nota); com IDs de pendência em erro, diga ao usuário e pare.

## Conferência de propagação

`harness.py afetados <ID ou "termo">` lista quem cita o alvo, pelo status na tabela de artefatos: `aprovado` primeiro, porque são os que precisam de revisão quando o alvo muda. Com o ID de uma pendência, ele junta aos alvos os IDs que ela cita, e a primeira linha da saída diz quais. Use no registro no ato (acima), no passo 0 do modo revisão ([modo-revisao.md](modo-revisao.md)) e do lote ([lote.md](lote.md)) e quando o usuário pedir. O script lista; julgar se há contradição é seu, e confirmar é do usuário.
