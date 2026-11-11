---
name: iniciar
description: Inicia um projeto de planejamento ou um repositório de código a partir do modelo do plugin: o modelo da trilha, o lançador, os githooks e os plugins da trilha. Use com /ela-harness:iniciar <trilha> [nome do projeto].
argument-hint: "<trilha> [nome do projeto]"
disable-model-invocation: true
allowed-tools: Bash(python3 "${CLAUDE_PLUGIN_ROOT}/nucleo/comum/harness.py" iniciar *), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/nucleo/comum/harness.py iniciar *)
---

# Iniciar um projeto

Pedido: `$ARGUMENTS`. A primeira palavra é a trilha, `planejamento` ou `desenvolvimento`; o resto, se houver, é o nome
do projeto. Sem a trilha, pergunte qual é, numa linha, e espere a resposta.

1. Na raiz do repositório, rode `python3 "${CLAUDE_PLUGIN_ROOT}/nucleo/comum/harness.py" iniciar <trilha> .`, com
   `--nome "<nome>"` no fim quando o pedido traz o nome, e mostre a saída.
2. Com uma recusa (`não é a raiz de um repositório git`, `já tem o harness`, `sem o modelo` ou a do
   `.claude/settings.json` que não se lê como objeto JSON), não apague nem mova nada: diga a recusa ao usuário e espere.
3. Com as linhas `mantido:`, diga que esses arquivos ficaram como estavam; na do `CLAUDE.md`, repita as linhas que ela
   manda acrescentar. Com a linha `mesclado: .claude/settings.json`, diga que o arquivo da instalação ganhou do modelo
   o que faltava, como as permissões, e manteve o resto. Com uma linha `falta:`, repita o comando que ela traz.
4. Repita a linha `próximo:`. Não faça commit sem o usuário pedir.
