# O dono diante do achado em aberto

Lida no passo 5 do `/ela-harness:revisar-bloco`, com Crítico ou Importante no `## Em aberto` do `revisao.md` (spec 6d-bloco, §5.4, passo 5). Nos comandos, `harness.py` abrevia `python3 .claude/harness/harness.py`, rodado da raiz da árvore em que a sessão trabalha: a lane, depois do `EnterWorktree`.

## A mensagem ao dono

Mostre cada linha do `## Em aberto` do `revisao.md` como está, sem resumir, e as três saídas:

1. **Orientação.** O dono diz no chat o que fazer; a revisão roda de novo.
2. **Dispensa.** O dono dispensa o achado, com o motivo.
3. **Replanejar ou trabalho novo.** A spec está errada, ou a orientação pede trabalho novo.

## Cada saída

- **Orientação.** Volte ao passo 2 do `/ela-harness:revisar-bloco`, com `--orientacao "<texto do dono>"`.
- **Dispensa.** Rode `harness.py revisao dispensar <R-ID> "<motivo>"`, um achado por vez, só depois da palavra do dono que nomeia o achado e o motivo. A guarda pede a confirmação dele. Sem nenhum achado em aberto, siga para o `bloco revisado` do passo 5.
- **Conflito com a passagem.** O achado que o conserto devolveu como `sem_conserto` por conflito entre a passagem e a ficha ou a spec tem duas saídas: `harness.py retorno abrir <ID> --tipo decisao --contradiz "<texto>" --evidencia "<texto>"`, com o ID da passagem em conflito, que vai ao planejamento, ou `harness.py revisao dispensar <R-ID> "<motivo>"`. O dono escolhe.
- **Replanejar.** Quando o achado mostra que a spec está errada, rode `harness.py bloco replanejar "<motivo>"` e invoque a skill `ela-harness:planejar-bloco` pela ferramenta Skill.
- **Trabalho novo.** Quando a orientação pede trabalho novo, rode `harness.py bloco corrigir` e invoque a skill `ela-harness:executar-bloco` pela ferramenta Skill, com o argumento `correção: <orientação>`.
