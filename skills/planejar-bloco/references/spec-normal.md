# A spec do bloco normal

1. Invoque a skill `superpowers:brainstorming` pela ferramenta Skill para o desenho, com o dono só na aprovação da spec, no passo 6 do `SKILL.md`: o `Quem decide` do `ciclo.md` dispensa as outras paradas dela. No desenho, invoque a skill `mattpocock-skills:codebase-design` pela ferramenta Skill; quando uma dúvida só se resolve vendo, invoque a skill `mattpocock-skills:prototype` pela ferramenta Skill. Antes de pôr no desenho uma função, um script ou um comportamento de ferramenta de que um requisito dependa, leia-o e cite-o no `## Desenho` com `arquivo:linha` e a propriedade usada (o formato da saída, os efeitos colaterais). O que não foi lido não entra no desenho como fato; o fato do `contexto-leitor.md` já vem com `arquivo:linha` e vale como lido.
2. Grave a spec em `<bloco>/spec.md`, com as seções, nesta ordem:
   - `# Spec: <ID> <slug>`, e a linha `Caminho: normal` logo depois;
   - `## Objetivo`;
   - `## Escopo`, com o que fica dentro e o que fica fora;
   - `## Desenho`;
   - `## Testes`;
   - `## Verificação externa`.
3. A `## Verificação externa` tem a forma que o `harness.py aceitacao` lê (docstring do `aceitacao.py`): `nenhuma`, ou os itens, cada um com os subitens:
   - `prova:` é `manual` ou `<alias> GET|HEAD|POST <caminho> -> <código>`, com o alias do `aceitacao.aliases` do perfil;
   - `quando:` é `antes do merge` ou `depois do merge`;
   - `pedido:`, opcional e só na prova automática, sem valor na linha, com o bloco ` ```json ` recuado logo abaixo, sem linha em branco entre os dois, um objeto com as chaves opcionais `cabecalhos`, `corpo` e `campos`:
     - `cabecalhos`: os cabeçalhos da requisição, nome e valor em texto; vale em todo método, e um `Content-Type` seu vence o do `corpo`;
     - `corpo`: o JSON enviado, com `Content-Type: application/json` quando os `cabecalhos` não trazem o seu; vale só no POST;
     - `campos`: os campos esperados no JSON da resposta, do caminho ao valor; vale no GET e no POST, não no HEAD. O caminho é `a.b` para o campo dentro de outro, `lista[]` para cada elemento da lista (a lista vazia falha) e `lista[<n>]` para o elemento de índice `<n>`, a partir de 0. O valor `"*"` quer dizer presente e não nulo, e qualquer outro é comparado por igualdade.

   Sem `quando:`, vale `antes do merge`.

   O marcador `{env.NOME}`, com o `NOME` em maiúsculas, dígitos e `_`, sem começar por dígito, vale no caminho da prova e nos textos dos valores dos `cabecalhos` e do `corpo`. O valor fica no ambiente ou num arquivo de env da lane (um `env_copiados` do perfil ou o `.env` gerado), nunca na spec nem na linha de comando: a spec traz só o marcador, e a conferência o troca na hora da requisição.

   Quando um campo falha, a saída traz o caminho dele, sem o valor esperado nem o recebido.
4. Depois de aprovada, a spec não muda por fora: mudar é `harness.py bloco replanejar`.

## Exemplo

````markdown
# Spec: DEV-07 cache-da-consulta

Caminho: normal

## Objetivo

A consulta de preço repetida em até 60 segundos reaproveita a resposta, sem chamar a distribuidora de novo (RF-COT-04).

## Escopo

Dentro:
- o cache da resposta por origem, destino e peso;
- a chave "sem cache" no perfil da biblioteca.

Fora:
- o cache entre bibliotecas (DEV-12).

## Desenho

Um módulo de cache na borda da consulta, com a chave montada pelos três campos e o prazo de 60 segundos vindo da configuração. A consulta pergunta ao cache antes de chamar a distribuidora e grava a resposta depois. O prazo vem do `ler_configuracao` (`api/configuracao.py:18`), que devolve os segundos como inteiro e não grava nada.

## Testes

- Duas consultas iguais seguidas chamam a distribuidora uma vez.
- A consulta depois do prazo chama de novo.
- Com a chave "sem cache", toda consulta chama.

## Verificação externa

- A API da lane responde à consulta com o cache ligado
  - prova: api GET /saude -> 200
  - quando: antes do merge
- A consulta real de um CEP de teste volta em até 3 segundos
  - prova: manual
  - quando: depois do merge
````

Um item com a prova por POST e o `pedido:`, só com a `## Verificação externa`:

````markdown
## Verificação externa

- A reserva responde com o prazo
  - prova: api POST /retorno/{env.SEGREDO_RETORNO}/reservas -> 200
  - quando: antes do merge
  - pedido:
    ```json
    {
      "cabecalhos": {"X-Leitor": "{env.CHAVE_LEITOR}"},
      "corpo": {"livro": "L-001", "leitor": "R-17"},
      "campos": {"prazo": "*", "itens[].situacao": "reservado"}
    }
    ```
- O leitor vê a reserva na tela do acervo
  - prova: manual
  - quando: depois do merge
````
