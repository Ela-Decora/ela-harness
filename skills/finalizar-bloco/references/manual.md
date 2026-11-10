# O item manual de antes do merge

Lida no passo 2 do `/ela-harness:finalizar-bloco` (spec 6d-bloco, §5.5, passo 2). Nos comandos, `harness.py` abrevia `python3 .claude/harness/harness.py`, rodado da raiz da árvore em que a sessão trabalha: a lane, depois do `EnterWorktree`.

## Quando vale

O item é manual, de antes do merge, e ainda sem resultado na tabela do `aceitacao.md`. Item de depois do merge não entra aqui: o dono o anota no `harness.py lane fechar --manual`.

## A pré-checagem

Antes de chamar o dono, liste as pré-condições do item e rode, sem ele, cada uma que um comando confere, um comando por chamada do Bash:

- o serviço da lane responde no endereço que o passo abre;
- o arquivo ou o dado que o passo usa existe;
- quando o passo depende do Claude Code carregar algo (um plugin, um hook, uma skill), um `claude -p` na mesma pasta mostra que carrega.

Pré-condição que falha não vai ao dono como passo: corrija o que é da lane, ou chame o dono pelo item 3 de "Quando chamar o dono" do `SKILL.md`, com a saída. Pré-condição cujo comando a sessão não consegue rodar (a ferramenta recusa, ou o `claude -p` não roda de dentro da sessão) vai ao dono como o primeiro passo do guia, com o comando e a recusa. Ao dono, mostre numa linha cada pré-condição conferida.

## O guia

Invoque a skill `mattpocock-skills:wizard` pela ferramenta Skill só com o que sobrou para uma pessoa, um item por vez. Cada passo diz onde ir, o que clicar ou colar, o que deve aparecer, o que fazer e anotar se não aparecer, e o que trazer de volta.

Na lane, a sessão não roda `bash`, como manda o `ciclo.md`:

- leia o `template.sh` do `wizard` pelo Read e grave o script pelo Write em `.superpowers/wizard/<ID>-item-<n>.sh`, com o `.superpowers/wizard/.gitignore` (`*`) gravado pelo Write se ainda não existe;
- sem `cp`, `bash -n` nem `chmod`: a conferência é a leitura estática que o passo 4 do `wizard` pede;
- o primeiro passo entregue ao dono é rodar `bash <caminho do script>` no terminal dele, com o caminho por extenso.

## O resultado

O que o dono relatar entra pelo `harness.py aceitacao anotar <n> ok|falhou "<nota>"`, com `<n>` o número do item e a nota numa linha. Anote só o que o dono disse, sem completar. O comando grava `<resultado>: <nota>` e a data no item, recusa item automático, de depois do merge ou nota vazia, e a guarda pede a confirmação do dono. Com `falhou`, chame o dono antes do passo 3.
