# Contexto do bloco

Só com `Contexto: sim` na ficha: o Context Packet não basta, e o `contexto-leitor` lê o resto.

1. Rode `harness.py contexto`, que regrava o `contexto.md` do bloco. Os domínios são os documentos da passagem distintos em `## Para ler` e em `## Também citados` dele; no máximo 4. Com mais, junte os que tratam do mesmo assunto, ou pergunte ao dono quais ficam.
2. Rode `harness.py papel contexto-leitor` e anote o `model` e o `effort`.
3. Despache um Agent `ela-harness:contexto-leitor` por domínio, todos na mesma mensagem, com esse `model` e esse `effort`. O pedido a cada um: os fatos do domínio de que a ficha precisa, cada um com o `arquivo:linha`.
4. Grave `<bloco>/contexto-leitor.md`, com `# Contexto do leitor: <ID>` e um `## <documento>` por domínio, com os fatos e o `arquivo:linha` de cada um.
5. Fato de biblioteca ou API externa: invoque a skill `mattpocock-skills:research` pela ferramenta Skill na própria sessão, porque um subagente não despacha outro. A nota vai para `<bloco>/pesquisa-<tema>.md`.

O `contexto-leitor.md` e as notas `pesquisa-*.md` entram no commit do `bloco planejado`.
