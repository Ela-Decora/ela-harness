# Cheiros de ambiguidade em requisitos

Lista usada no passo 4 (a parte mecânica, por `grep`) e no passo 5 (a parte de leitura, pelo revisor). Um cheiro não é erro por si: é um ponto que precisa de número, ator, limite ou definição antes de o requisito ser verificável.

## Detectáveis por busca de texto

| Cheiro | Exemplos em português | O que falta |
|---|---|---|
| Adjetivo ou advérbio sem medida | rápido, fácil, intuitivo, amigável, robusto, adequado, razoável, eficiente, simples, moderno, confiável, em tempo real | número com unidade e condição: "em até 3 s, no percentil 95, com 50 cotações simultâneas" |
| Quantificador vago | a maioria, geralmente, vários, alguns, muitos, poucos, grande, pequeno, frequente, raro | quantidade, faixa ou percentual |
| Lista aberta | etc., entre outros, e assim por diante, e similares | a lista fechada ou a regra que define o conjunto |
| Conjunção ambígua | e/ou | qual combinação vale: "e", "ou", ou as duas com a regra de prioridade |
| Condição sem limite | conforme necessário, quando apropriado, se possível, sempre que preciso | o gatilho exato e quem decide |

## Detectáveis só por leitura

| Cheiro | Exemplo | O que falta |
|---|---|---|
| Pronome sem referente | "o sistema envia o pedido ao fornecedor e ele confirma; depois ele é atualizado" | nomear o sujeito de cada verbo |
| Voz passiva sem ator | "o peso será validado" | quem valida, em que momento, e o que acontece se falhar |
| Termo não definido ou com dois nomes | pedido e encomenda; cliente e comprador | um termo canônico, definido no glossário |
| Número sem unidade ou sem base | "prazo de 3", "peso mínimo 300" | unidade (dias úteis, gramas) e referência (a partir de quando) |
| Caminho feliz sem o caso contrário | "o fornecedor devolve o preço" | o que acontece quando não devolve, devolve erro ou demora mais que o limite |
| Requisito composto | "o gestor cadastra a tabela e aprova o reajuste" | um requisito por comportamento |
| Solução disfarçada de requisito (camada 1) | "o sistema usa fila para processar pedidos" | a necessidade do cliente, sem a tecnologia |
| Requisito sem fonte | item que não vem do rascunho, do cliente nem de decisão registrada | a origem, ou `[A CONFIRMAR]` |

## Origem

Adaptado de: `atomicity-checklist.md` e `iso-29148-quality-gate.md` da skill `requirements-author` do microsoft/hve-core (CC BY 4.0, Microsoft Corporation; traduzido e reduzido); `ambiguity-detection-in-requirements` de anilamar/sdlc-requirements-skills (MIT); passo "ambiguity detection" de `analyze.md` do github/spec-kit (MIT). As características necessário, não ambíguo, singular e verificável vêm da ISO/IEC/IEEE 29148, pela redação do hve-core.
