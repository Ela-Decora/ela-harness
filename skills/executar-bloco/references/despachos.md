# Despachos do SDD com os agentes do harness

Lida no passo 4. O `superpowers:subagent-driven-development` manda despachar cada papel com um subagente; aqui fica qual agente faz cada papel.

| Papel no SDD | `subagent_type` |
|---|---|
| Implementador de tarefa mecânica: o código está no plano e a tarefa mexe em 1 ou 2 arquivos | `ela-harness:implementador-mecanico` |
| Implementador de tarefa com vários arquivos ou decisão de padrão | `ela-harness:implementador-integracao` |
| Revisor da tarefa (`task-reviewer-prompt.md`) | `ela-harness:revisor-task` |
| Re-revisão (`re-review-prompt.md`) | `ela-harness:re-revisor` |
| Rodadas 4 e 5 do conserto | `ela-harness:corretor-tardio` |

- **Texto.** O texto de cada despacho é o modelo de prompt do próprio SDD; não o reescreva.
- **Modelo e esforço.** O `model` e o `effort` de cada chamada da ferramenta Agent vêm da linha do agente na saída de `harness.py papel --todos`, no lugar da escolha de modelo do SDD. O mod, quando instalado, troca o que vier diferente.
- **Teste primeiro.** Todo implementador invoca o `superpowers:test-driven-development`.
- **Espera.** Despacho que volta sem o resultado, porque o agente roda em segundo plano: termine o turno e espere a notificação dele. Até ela, nenhuma mensagem traz o resultado, o veredito ou um achado do agente, nem o passo do SDD que depende dele.

## Sem os scripts do SDD

Na lane, o Claude Code recusa o `bash <script>` e o `$(...)` que cita git, e os scripts `sdd-workspace`, `task-brief` e `review-package` do SDD não rodam. Faça o trabalho deles assim, com `<plano>` o nome do plano sem o `.md`:

- **Workspace:** `.superpowers/sdd/<plano>/`, com o `plan-path` e o `.superpowers/sdd/.gitignore` (`*`), gravados pelo Write. O `plan-path` traz numa linha o caminho do plano relativo à raiz da lane, como `<bloco>/plano.md`, sem `/` no começo; o `harness.py bloco executado` acha o ledger por ele.
- **Brief:** a seção `### Task N:` do plano, copiada inteira pelo Write em `.superpowers/sdd/<plano>/task-N-brief.md`.
- **Pacote da revisão:** três comandos, um por chamada do Bash, com BASE e HEAD em hashes escritos por extenso e `<pacote>` igual a `.superpowers/sdd/<plano>/review-<BASE>..<HEAD>.diff`:
  - `git log --oneline BASE..HEAD > <pacote>`
  - `git diff --stat BASE..HEAD >> <pacote>`
  - `git diff -U10 BASE..HEAD >> <pacote>`

  O revisor lê o pacote pelo caminho; o diff não passa pelo contexto da sessão.
