# Correção: tarefas novas no plano

Lida no passo 3, quando a skill chega com o argumento `correção: <orientação>` ou `pr`.

1. **Fonte.** Com `pr`, leia os comentários do PR do ramo da lane: `gh pr view --comments`. Com `correção: <texto>`, a fonte é o texto.
2. **Tarefas.** Acrescente ao fim do `<bloco>/plano.md`, depois da última tarefa, as tarefas da correção, em inglês e no formato do `superpowers:writing-plans` (`### Task N:`, lista Files, passos). Numere a partir da seguinte à última; não toque nas anteriores.
3. **Commit.** Faça o commit `chore(<ID>): plano, correção`, com só o `plano.md`.
4. **Segue.** O passo 4 roda o SDD, que pelo ledger dá as tarefas anteriores como feitas e executa só as novas.
