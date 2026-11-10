# O plano

1. Invoque a skill `superpowers:writing-plans` pela ferramenta Skill, escreva o plano em inglês e grave em `<bloco>/plano.md`. Pelas dispensas do `ciclo.md`, não peça revisão do plano nem a escolha do método.
2. O cabeçalho traz a linha `**Spec:**` apontando para `<blocos>/<ID>-<slug>/spec.md`, o caminho da spec do bloco.
3. Cada tarefa é um `### Task N:`, com `**Files:**` e as linhas `- Create:`, `- Modify:` e `- Test:`. IDs e trechos de RA, RF e FN vão sem tradução.
4. Bloco curto: até 3 tarefas. A Task 1 escreve o teste de regressão que reproduz a causa, na costura que a investigação achou; se não há costura certa, a Task 1 registra isso, como a fase 5 do `mattpocock-skills:diagnosing-bugs`.
5. O plano não pede aprovação: sai da spec aprovada.
6. **Fragmento conferido.** Todo fragmento executável que o plano fixa junto com os dados de teste dele (uma regex e as amostras que ela aceita ou recusa, uma string de formato e os valores, um esquema e os exemplos) roda uma vez antes do `harness.py bloco planejado`: um comando por chamada do Bash, como `python3 -c` ou o interpretador do projeto, sem `bash <script>`. Arquivo de apoio fica só em `.superpowers/plano/`, com o `.superpowers/plano/.gitignore` (`*`) gravado pelo Write. Resultado diferente do que o plano diz: corrija o texto do plano, sem deixar a diferença para o implementador.
7. **Aprovação e decisões.** O cabeçalho traz a linha `**Spec approval:** <AAAA-MM-DD>, "<palavra do dono>"`, com a data e as palavras da aprovação do passo 6 do `SKILL.md`. O plano traz a seção `## Owner decisions`, com cada decisão que o dono tomou no chat sobre a spec ou o plano depois da aprovação e que não muda a spec, uma por linha, com a data e as palavras dele, sem tradução; sem decisão, `None.`. A decisão que muda a spec não entra aqui: a que muda a spec volta ao passo 6 do `SKILL.md`, com a spec corrigida antes de uma nova palavra do dono.

## As recusas do `bloco planejado`

Cada recusa e a correção. Corrija e rode `harness.py bloco planejado` de novo.

| Recusa | Correção |
|---|---|
| `bloco planejado: a lane tem alterações sem commit fora do bloco: <até 5 caminhos>; o código muda só na execução` | Desfaça a alteração ou tire o arquivo da lane; no bloco curto, tire a instrumentação `[DEBUG-...]` e a reprodução descartável. Só a pasta do bloco pode ter alteração sem commit. |
| `bloco planejado: plano sem ### Task N` | Escreva as tarefas como `### Task 1:`, `### Task 2:`, fora de bloco de código. |
| `bloco planejado: Task <n> sem a lista Files com Create, Modify ou Test` | Acrescente à Task `<n>` a linha `**Files:**` e ao menos um `- Create:`, `- Modify:` ou `- Test:`. |
| `bloco planejado: o plano não aponta para a spec do bloco na linha **Spec:**` | Ponha a linha `**Spec:** <blocos>/<ID>-<slug>/spec.md` no cabeçalho do plano. |
| `bloco planejado: --curto vale só para ficha <prefixo>` | A ficha não é do código: rode sem `--curto` e escreva a spec normal. |
| `bloco planejado: bloco curto sem ## Causa com a linha Prova:` | Acrescente à `## Causa` da spec a linha `` Prova: `<comando>` ``, com o comando que falha por causa do defeito. |
| `bloco planejado: bloco curto com <n> tarefas; o limite é 3; replaneje como bloco normal` | Reduza o plano a 3 tarefas; se não couber, chame o dono (item 3 de "Quando chamar o dono") e rode `harness.py bloco replanejar`. |
