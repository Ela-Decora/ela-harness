# Passo 2: entrevista em rodadas

Modele as decisões em aberto como uma árvore. A fronteira é o conjunto de decisões cujos pré-requisitos já estão resolvidos. Cada rodada pergunta a fronteira inteira, até 4 perguntas, com estas regras:

- Uma rodada é uma chamada da ferramenta de opções (`AskUserQuestion`). Cada pergunta leva: `header` com a seção do molde, abreviada se passar de 12 caracteres (num pacote, o termo do documento, e a `question` diz o documento e a seção); `question` completa, com o porquê em uma frase; de 2 a 4 opções excludentes, a recomendada primeiro, com " (Recommended)" no fim do rótulo e o motivo na descrição. A resposta livre ("Other") a ferramenta já acrescenta: não crie opção "Outra resposta"; "Other" que chega sem texto vira pedido do texto no chat, em uma linha. Não use `multiSelect`: pergunta que pede mais de uma resposta vai em texto.
- Reserva em texto, no molde "Rodada da entrevista" de `.claude/harness/nucleo/nucleo/comum/saida.md`, lido na hora de escrever a rodada, com até 4 perguntas: quando a ferramenta não está disponível, quando o usuário a recusa, ou quando a rodada tem pergunta sem opções naturais. Vale mesmo com o modo caveman ligado.
- Cada pergunta amarrada a uma seção do molde e escrita como pergunta completa; um rótulo como "Fora de escopo" não é pergunta.
- Pergunta que depende de outra ainda aberta vai para a rodada seguinte.
- Fatos são seu trabalho; decisões são do usuário. Pergunte só decisão; fato, busque nas fontes. Se um fato ainda não voltou do subagente, pergunte o resto da fronteira.
- Camada que proíbe termo técnico: perguntas, opções e descrições sem ele, ou com ele explicado em palavras do cliente. Os sistemas que o cliente já usa podem ser citados pelo nome; tecnologia nossa (nuvem, banco, fila, linguagem) não.
- Pergunte só sobre o conteúdo do documento; o processo (se o rascunho vai existir, qual passo seguir) está no `STATUS.md`, nas pendências e no CLAUDE.md.
- Vocabulário: quando um conceito tiver dois nomes (exemplos em "Este projeto"), proponha o canônico, confirme com o usuário e use só ele. O glossário fica onde "Este projeto" diz.
- Pergunta que depende de comparar tecnologias, fornecedores ou abordagens não entra na rodada: sugira `/ela-harness:assessor <tema>` em uma linha; a seção fica com a fonte "estudo pendente".

Ao abrir a rodada 2 e as seguintes, `harness.py passo 2 --rodada <r> --proximo "rodada <r> da entrevista: <temas>"`. Depois da resposta, no chat: a linha "Fica para a próxima" (as decisões que dependem desta rodada, ou "nada") e as linhas do mapa que ganharam fonte. A árvore e o mapa vivem no chat, não em arquivo. Depois de cada rodada, o registro no ato de [pacote.md](pacote.md): a decisão que vale além deste documento vira Ruling, por `harness.py registrar ruling`, e a pergunta que fica aberta vira pendência, por `harness.py registrar pendencia`. Se depois de 3 rodadas a fronteira não esvaziou, liste o que resta e ofereça escrever a versão com `[A CONFIRMAR]` nesses pontos.

Informação nova da conversa vai para o rascunho por `harness.py registrar relato "<texto>" --origem <documento>`, com as palavras do usuário, quando o que ele disse cumpre quatro condições: não responde à pergunta do documento; não é decisão que vale além dele (essa vira Ruling); não é pergunta aberta (essa vira pendência); e não está em nenhum documento nem Ruling, conferido com `harness.py afetados "<termo>"`. Use `--confirmada` quando ele afirmou; deixe sem quando ele hesitou ou quando a informação veio de terceiros. Mostre ao usuário a linha que o comando imprimiu.

A entrevista termina quando a fronteira está vazia e toda seção tem fonte. Diga isso em uma linha e passe ao passo 3, com `harness.py passo 3 --proximo "<o que vem>"`. Não escreva o documento antes disso.
