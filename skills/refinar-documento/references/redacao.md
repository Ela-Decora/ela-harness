# Passos 3 e 4: versão refinada, checagem e confirmação

## Passo 3: versão refinada

Prazo da pesquisa: o passo 3 só começa quando o `pesquisador-fatos` despachado para o documento ou o pacote voltou ou foi parado ([subagentes.md](subagentes.md)), ou quando o usuário escolhe, pela ferramenta de opções, entre "Esperar a pesquisa (Recommended)" e "Escrever com a seção marcada". Na segunda, a seção que depende do fato sai com `[A CONFIRMAR: pesquisa pendente]`. Relatório que volta depois da aprovação sobe a escada de `.claude/harness/nucleo/nucleo/planejamento/pendencias.md`, com `--causa pesquisa` se a resposta abrir pendência: o documento aprovado está fora do escopo.

Escreva direto no arquivo alvo, na ordem e com os títulos do molde. Num pacote, todos os documentos, na ordem da lista do `Pacote`; cada frase cita a fonte ou leva `[A CONFIRMAR: motivo]`.

- Ao preencher uma seção, apague o comentário `<!-- -->` dela. Nenhum sobra.
- O que o usuário disse entra sem marcador. O que você inferiu entra como `[A CONFIRMAR: motivo em poucas palavras]`.
- Relato não confirmado do rascunho entra só com `[A CONFIRMAR: relato <ID> não confirmado]`.
- A pergunta que ficou aberta na entrevista e é deste documento entra como `[A CONFIRMAR: pergunta aberta: <a pergunta>]` e fica assim até a aprovação, sem pendência, mesmo quando o revisor a aponta (`.claude/harness/nucleo/nucleo/planejamento/pendencias.md`).
- Síntese, não entrevista: nenhuma pergunta nova no texto.
- IDs nos padrões de "Este projeto", sequenciais e sem buraco, menos os de `ids.com_buracos` do perfil (`.claude/perfil.toml`), que nunca se reusam: neles, o ID tirado deixa buraco. ID de outro documento é só citado, nunca definido de novo; uma faixa se escreve `<ID> a <ID>`, com o mesmo prefixo nas duas pontas.
- Citação a outro documento: pelo ID ou pelo título da seção, nunca pelo número de linha (`<documento>.md:NN`); o `citacao-por-linha` do `checar` a recusa, menos no arquivo de decisões, que só recebe acréscimos.
- Cada requisito tem um sujeito, um comportamento e uma condição; é verificável; não usa adjetivo sem medida (lista em [cheiros-de-ambiguidade.md](cheiros-de-ambiguidade.md)).
- A regra da camada vale no texto inteiro. Datas em `AAAA-MM-DD`.
- Funcionalidade, no módulo:
  - o título é `### Funcionalidade FN-<MÓDULO>-NN: <nome>`, com o código do domínio principal do RF do módulo, e o ID nunca se reusa;
  - o Aceite tem de 1 a 5 itens numerados, cada um uma frase com a condição, o resultado que se vê ou se mede e o RF ou RNF que ele prova; fora do módulo, o item se cita como `FN-XXX-NN.n`; o item citado fora do módulo não muda de número: o item novo entra no fim; mudar ou tirar um item citado de propósito leva a correção ao documento que cita, no mesmo pacote quando ele está nele e, senão, por uma nota `resta em <documento>` na pendência do ciclo, pela escada de `.claude/harness/nucleo/nucleo/planejamento/pendencias.md`, com `--causa cascata` se a resposta abrir pendência; o `aceite-renumerado` do `checar` avisa;
  - divide-se a funcionalidade só quando o Aceite passaria de 5 itens ou quando ela tem dois gatilhos; o texto longo não obriga a dividir;
  - o Depende de traz as FN de que ela precisa, por ID, e os outros módulos, ou `—`, nunca "das anteriores desta lista"; o `campos` do `checar` confere os itens do Aceite, o RF ou RNF de cada um e o Depende de.
- Neste passo, só o arquivo alvo (ou os do pacote) muda.

Ao terminar, `harness.py passo 4 --proximo "<o que vem>"`.

## Passo 4: checagem determinística e confirmação

1. Rode `python3 .claude/harness/harness.py checar` (sem argumento, o documento ou os do pacote, cada um aberto por `== <documento>` quando são vários) e cole a saída antes de qualquer afirmação de "pronto". Esperado: `OK` em `placeholders`, `titulos`, `ids`, `ids-citados`, `adjetivos-vagos` e `citacao-por-linha`, e nas verificações do perfil que valem para o documento (`campos`, `colunas` e `pendencia-na-linha`), e a contagem de `a-confirmar` anotada. Com `aceite-renumerado: AVISO`, devolva o número ao item citado; se ele mudou de propósito, a correção vai ao documento que cita, como diz o item do Aceite no passo 3. As trocas de nome e os blocos que o molde manda repetir já são descontados; `ids-citados` aceita ID definido no próprio documento ou num artefato da tabela da mesma camada ou de camada anterior. Use `--verbose` para ver as linhas de cada ocorrência e a seção de cada `[A CONFIRMAR]`. Depois, por leitura: contradição interna, item que o molde pede e ficou vago, termo com dois nomes. Corrija no ato e rode de novo.
2. Rodada de confirmação, a partir da lista do `checar --verbose`: cada `[A CONFIRMAR: motivo]` cujo motivo não cita uma pendência (`<prefixo de pendência>-NN`) nem "pesquisa pendente" nem "pergunta aberta" vira uma pergunta da ferramenta de opções. `header`: a seção, abreviada se passar de 12 caracteres. `question`: o trecho, encurtado, e o motivo. Opções: "Confirmo (Recommended)" e "Tirar do documento"; a correção vem pela resposta livre ("Other"), e "Other" sem texto vira pedido da correção no chat. Até 4 perguntas por chamada, em chamadas seguidas até acabar. Os marcadores deixados de fora vão numa linha no chat, com o motivo de cada um. Sem a ferramenta, as mesmas perguntas em texto, no molde "Rodada da entrevista".
3. Aplique as respostas: confirmado, o marcador sai e o texto fica; "tirar", o trecho sai, com o texto que dependia dele ajustado; correção, o trecho é reescrito com a resposta, sem marcador. Depois de cada chamada, o registro no ato de [pacote.md](pacote.md) para a resposta que vale além do documento. A resposta sobre um relato grava `harness.py registrar relato --id <ID> --status confirmada` ou `--status descartada --motivo "<motivo>"`; se o usuário corrige a informação, descarte o relato com o motivo e registre um novo com o texto corrigido.
4. Rode o `checar` de novo e cole a saída, com a contagem nova de `a-confirmar`.
5. `harness.py passo 5 --proximo "<o que vem>"`.

Na camada com regra de linguagem do cliente, as perguntas da confirmação seguem a regra.
