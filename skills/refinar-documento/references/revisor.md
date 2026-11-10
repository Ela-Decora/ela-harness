# Passo 5: revisão por subagente

Despache o agente `ela-harness:revisor-requisitos` com um dos blocos abaixo preenchido: só caminhos e textos curtos, nunca o conteúdo do documento. A regra da camada, os sistemas do cliente e o arquivo de decisões vêm do bloco "Este projeto" da skill; o molde, de `harness.py molde <documento>`. As regras, o que verificar e o formato de saída vivem no agente (`.claude/harness/nucleo/agents/revisor-requisitos.md`).

O arquivo de princípios sai do título de nível 1 do molde: `# Entidade:` dá `.claude/harness/nucleo/skills/gerar-modulos/references/entidades.md`; `# Tela:`, o `telas.md` da mesma pasta; `# Módulo:`, o `modulos.md`. Outro título dá `não há`.

- Rodada 1: sempre, com o modelo do agente.
- Rodada 2: só se a correção da rodada 1 reescreveu uma seção ou acrescentou ID ou regra; ajuste de redação não conta. Mesmo modelo, bloco "Rodada 2", com os achados anteriores e o `Escopo:` dos trechos alterados.
- Não há rodada 3: o que sobrar vai ao usuário no passo 6.

Despache sempre em segundo plano e avise o usuário em uma linha. Enquanto o revisor roda, faça o que não depende do veredito e não edite o documento revisado. Ao fim de cada rodada, registre os tokens e a duração lidos da notificação do agente por `harness.py registrar medicao "<medição>" "<valor>"`.

Cada achado é hipótese: confira no documento antes de aplicar e discorde com motivo quando ele contrariar decisão do usuário registrada. Relate cada rodada no molde "Relato da revisão" de `.claude/harness/nucleo/nucleo/comum/saida.md`, lido na hora. Correção aplicada: o `checar` roda de novo (item 1 do passo 4), sem mudar o `STATUS.md`; a confirmação só se repete para marcador novo. Rodada 2 nova: `harness.py passo 5 --rodada 2 --proximo "<o que vem>"`. Ao fechar o passo, `harness.py passo 6`, como [aprovacao.md](aprovacao.md) diz.

## Rodada 1

```
Rodada: 1
Documento: {caminho do documento}
Molde de origem: {o caminho que harness.py molde imprime}
Princípios do tipo: {o arquivo de princípios do tipo do documento, ou "não há"}
Trecho do rascunho que o originou: {caminho e linhas, ou "não há"}
Camada: {a fase, pela pasta no caminho do documento}
Regra da camada: {a regra dessa fase, como está em "Este projeto"}
Sistemas do cliente: {a lista de "Este projeto", ou "nenhum"}
Decisões: {caminho do arquivo de decisões}
Cheiros de ambiguidade: .claude/harness/nucleo/skills/refinar-documento/references/cheiros-de-ambiguidade.md
```

No modo revisão, acrescente a linha `Escopo: {os trechos alterados e o texto da pendência}`.

## Rodada 2

```
Rodada: 2
Documento: {caminho do documento}
Molde de origem: {o caminho que harness.py molde imprime}
Princípios do tipo: {o arquivo de princípios do tipo do documento, ou "não há"}
Trecho do rascunho que o originou: {caminho e linhas, ou "não há"}
Camada: {a fase, pela pasta no caminho do documento}
Regra da camada: {a regra dessa fase, como está em "Este projeto"}
Sistemas do cliente: {a lista de "Este projeto", ou "nenhum"}
Decisões: {caminho do arquivo de decisões}
Cheiros de ambiguidade: .claude/harness/nucleo/skills/refinar-documento/references/cheiros-de-ambiguidade.md
Achados anteriores: {lista numerada, uma linha cada}
Escopo: {os trechos alterados desde a rodada 1}
```

## Pacote

Um despacho para o pacote inteiro, com a lista `Documentos:` no lugar do `Documento:`. A rodada 2 traz só os documentos que a correção da rodada 1 reescreveu numa seção ou em que acrescentou ID ou regra, cada um com o seu `Escopo:`. No "mudar <documento>" do passo 6, o despacho é o de documento sozinho, rodada 1, com `Escopo:` dos trechos alterados. No pacote em modo revisão, a rodada 1 também traz um `Escopo:` por documento, e o `Módulo de origem` é "não há".

```
Rodada: 1
Documentos:
- {caminho} (molde: {o caminho que harness.py molde imprime}; princípios: {o arquivo, ou "não há"})
Módulo de origem: {caminho, quando o módulo é aprovado e fica fora do pacote; ou "no pacote"}
Trecho do rascunho que o originou: {caminho e linhas, ou "não há"}
Camada: {a fase}
Regra da camada: {a regra dessa fase, como está em "Este projeto"}
Sistemas do cliente: {a lista de "Este projeto", ou "nenhum"}
Decisões: {caminho do arquivo de decisões}
Cheiros de ambiguidade: .claude/harness/nucleo/skills/refinar-documento/references/cheiros-de-ambiguidade.md
```

```
Rodada: 2
Documentos:
- {caminho} (molde: {o caminho que harness.py molde imprime}; princípios: {o arquivo, ou "não há"})
  Escopo: {os trechos alterados desde a rodada 1}
Módulo de origem: {caminho, ou "no pacote"}
Trecho do rascunho que o originou: {caminho e linhas, ou "não há"}
Camada: {a fase}
Regra da camada: {a regra dessa fase, como está em "Este projeto"}
Sistemas do cliente: {a lista de "Este projeto", ou "nenhum"}
Decisões: {caminho do arquivo de decisões}
Cheiros de ambiguidade: .claude/harness/nucleo/skills/refinar-documento/references/cheiros-de-ambiguidade.md
Achados anteriores: {lista numerada, uma linha cada, com o documento de cada achado}
```
