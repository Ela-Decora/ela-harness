# Fontes dos princípios

De onde veio cada princípio de [entidades.md](entidades.md), [telas.md](telas.md) e [modulos.md](modulos.md). Nenhuma skill de fora é chamada nem é dependência do plugin: cada princípio foi traduzido e adaptado para o português, resumido e reescrito para os moldes da camada, e essa é a nota de cada linha da tabela. Os arquivos e as linhas de cada trecho estão no levantamento de skills de mercado de 2026-11-09, no repositório do harness.

| Repositório | O que entrou | Licença | Copyright |
|---|---|---|---|
| `jamiemill/layers-skills` (`layers-conceptual-model`, `layers-intro`, `layers-domain`, `layers-interaction-flow`, `layers-surface`) | entidades: objeto real, relação escrita como atributo, nada especulativo, provisória, verbo preciso, o tempo; módulos: a fronteira segue a linguagem; telas: destino com nome, estados, nenhuma entidade isolada, o erro que diz como sair | MIT | Copyright (c) 2026 Jamie Mill |
| `mattpocock/skills` (`domain-modeling`) | entidades: um nome por conceito, o do glossário | MIT | Copyright (c) 2026 Matt Pocock |
| `nWave-ai/nWave` (`nw-ddd-strategic`) | módulos: núcleo, suporte ou genérico; a divergência de linguagem como sinal de fronteira; poucos módulos | MIT | Copyright (c) 2026 Alessandro Di Gioia & Michele Brissoni |
| `vercel-labs/web-interface-guidelines` | telas: sem beco sem saída, todos os estados, a ação destrutiva com confirmação ou desfazer, o erro que guia a saída | MIT | Copyright (c) 2025 Vercel Labs |
| `plannotator/effective-html` (`html-prototype`, exemplo `release-readiness`) | telas: a tabela de estados (estado, gatilho, o que aparece, ação disponível) e o estado que não se aplica dito, sem forçar | MIT | Copyright (c) 2026 plannotator |
| `anthropics/knowledge-work-plugins` (`design/design-handoff`) | telas: mostrar todos os estados; não supor o que não foi especificado | Apache 2.0 | o `LICENSE` não traz linha de copyright; autor: Anthropic |
| `pbakaus/impeccable` (`shape`) | telas: o brief que começa pela tarefa e por quem chega, os estados e as decisões em aberto que quem constrói não pode inventar | Apache 2.0 | Copyright 2025 Paul Bakaus |
| `ddd-crew/bounded-context-canvas` | módulos: as ideias de propósito, de classificação estratégica e de comunicação entre contextos, reescritas em português, sem texto copiado | CC BY-SA 4.0 | DDD Crew |

Mudanças em relação às fontes, para a nota que o Apache 2.0 pede: tradução para o português, resumo em uma frase por princípio, troca dos exemplos e encaixe nas seções dos moldes de entidade, de tela e de módulo do harness. Do Bounded Context Canvas, que é CC BY-SA, entram só as ideias, reescritas, com a atribuição acima.

O aviso de permissão das fontes em MIT, que vale para cada linha de copyright em MIT da tabela:

```text
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

As fontes em Apache 2.0 seguem a Licença Apache, versão 2.0: <https://www.apache.org/licenses/LICENSE-2.0>.
