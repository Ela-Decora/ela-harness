# O corpo do PR

Este molde substitui o da skill `pr` do mattpocock-skills, que não se invoca. O corpo é escrito em português, com a saída dos testes como saiu, porque o PR é lido pelo dono. O núcleo confere os três títulos letra a letra e acrescenta a aceitação e as verificações.

## O molde

```markdown
## Resumo

<uma a três linhas sobre o que muda e por quê, e o menor esboço que deixa isso claro>

## Evidência

- **<o que o teste prova, numa linha>** (`<arquivo do teste>`)
  - Antes: <a falha esperada, numa linha>
  - Depois: passa.

## Perigo do merge

**Porta:** <de uma via | de duas vias>. <opcional: por quê>

**Raio de impacto:** <uma palavra ou expressão curta>

<opcional: o que pode quebrar depois do merge>
```

## Resumo

As entradas são o Objetivo da ficha, a `spec.md` do bloco e o `git diff <base>...HEAD`, com o `base` do `estado.md` do bloco. Na spec normal, entram o Objetivo e o Desenho; na curta, o Problema, a Causa e a Correção.

O esboço é um só, ou dois quando um não basta, ao lado do texto que ele sustenta, escolhido entre:

- pseudocódigo, para lógica;
- árvore de chamadas, para o fluxo em tempo de execução;
- árvore de arquivos rasa, para a responsabilidade dos arquivos ou uma refatoração ampla;
- `diff` de forma, quando o ponto é o que muda numa estrutura que já existe;
- Mermaid, para a interação entre partes.

Só os nomes, arquivos e estados que a mudança precisa para ser entendida.

O esboço vai só em bloco de código cercado por três crases, sem aninhar e fechado: o núcleo só reconhece a cerca de três crases, e `~~~`, quatro crases ou um bloco aberto dão recusas enganosas.

## Evidência

Para cada promessa da spec que um teste novo prova, um item com o antes e o depois, tirados do bloco "TDD Evidence" dos `task-<N>-report.md` da pasta do SDD do bloco: a pasta de `.superpowers/sdd/*/` cujo arquivo `plan-path` aponta para o `plano.md` do bloco (leia o `plan-path` de cada pasta).

- O antes é a falha do RED, numa linha, como pseudocódigo do teste quando a linha da saída não diz nada sozinha; o depois é o GREEN.
- Os testes da mesma promessa entram juntos, até seis itens, e o resto numa linha, `e mais <n> testes novos`.
- Sem teste novo, ou sem os relatórios, uma linha só: `Sem o antes e o depois: <motivo>`.
- A aceitação e as verificações não entram: o núcleo as acrescenta.

## Perigo do merge

- **Porta.** De uma via é a que não se desfaz com um revert: migração de banco que apaga ou transforma dado, mensagem ou chamada a um sistema de fora, contrato público que outro consumidor já lê, decisão difícil de voltar. O resto é de duas vias.
- **Raio de impacto.** O alcance do que pode quebrar (um módulo, uma tela, a API pública, o banco), pelo diff e pela spec.

## Origem

O molde e as regras das três seções vêm, adaptados, de `skills/engineering/pr/SKILL.md` do mattpocock-skills 1.3.1, commit `4588b32`, traduzidos e reduzidos. O cardápio de visões do Resumo vem da `show-me` do humanlayer/skills, de Dex Horthy, pela `pr`.

Copyright (c) 2026 Matt Pocock

Copyright (c) 2026 HumanLayer

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
