# Camada 3: documentos, DER físico, diagramas e ADRs

Vale para documento na pasta da fase que contém o `documento` da seção `[der]` do perfil. As chaves citadas aqui estão no `.claude/perfil.toml`: os `obrigatorios` da fase, a seção `[der]` e os `caminhos`.

## Documentos e ordem

- Os documentos da fase são os `obrigatorios` dela, e a ordem do perfil é a de produção. Cada um passa sozinho pelos sete passos, com a sua aprovação; o `harness.py proximo` recomenda nessa ordem.
- O ADR do banco vem antes do DER físico. Com ele aprovado, o usuário põe o banco escolhido no `dialeto` do `[der]`, e o DER sai com o DDL MySQL, que o Workbench lê, e o desse banco. Se um ADR novo trocar o banco depois, o DER passa pelo modo revisão ([modo-revisao.md](modo-revisao.md)) para ganhar o DDL novo.
- O índice da fase cobre só os diagramas e vem logo depois deles. Ele mantém os títulos do molde; cada seção traz um resumo de até três linhas e o link do documento da seção; os protótipos de tela entram só como links; a ordem de produção repete a do perfil; os blocos Mermaid de exemplo do molde saem.
- Depois do índice vêm, nesta ordem, que é a dos `obrigatorios`, os contratos externos, a entrega e operação e as fichas. Cada um cita o anterior por ID: o contrato cita os contêineres e a sequência da arquitetura da aplicação; a entrega e operação cita os contratos nos testes e nos objetivos de serviço; a ficha cita os riscos que mitiga. As fichas são o último documento antes do gate da fase. O detalhe de cada um está numa seção abaixo.
- O ID no começo da linha o define: o título, o item de lista, numerado ou não, e a linha de tabela que começam por um ID. O `ids` do `checar` acusa a definição repetida no documento, e o `checar-da-fase` do gate, entre os documentos da fase. O item ou a linha que só cita um ID começa pelo texto: o Aceite da ficha, como `Itens FN-XXX-NN.1 a FN-XXX-NN.3`; o gatilho de volta, com a condição antes do `SLO-NN`; e as tabelas de prova, que começam pelo nível.

## DER físico

O documento tem, na ordem do molde, as seções "Convenções", "Tabelas", com uma subseção por tabela, "Não persistido", "Diagrama", com o bloco gerado, e "Workbench", com os links dos prints e do SQL exportado. Uma subseção de tabela, com nomes de exemplo:

```text
### Tabela `item_pedido`

Entidade: ITEM_PEDIDO ([entidade-item-pedido.md](<caminho relativo do documento da entidade>))

| Coluna | Tipo | Nulo | Chave | Padrão | Origem |
|---|---|---|---|---|---|
| id | id | não | PK | — | técnica |
| pedido_id | id | não | FK pedido.id (cascata), UK:pedido_produto | — | relação: contém |
| produto | texto(60) | não | UK:pedido_produto | — | nome do produto |
| quantidade | inteiro | não | — | 1 | quantidade pedida |

Índices:
- (produto)

Restrições:
- quantidade entre 1 e 999
```

- **Título e linha de cima:** `### Tabela` e o nome entre crases. A linha `Entidade:` traz o nome da entidade como está no `erDiagram` do modelo conceitual e o link do documento dela, o mesmo em todas as tabelas da entidade. Uma entidade pode ter várias tabelas: a lista de um atributo pode virar tabela própria, e a FK dela para a tabela principal leva na Origem o trecho desse atributo. A tabela de ligação de uma relação muitos-para-muitos traz, no lugar, `Ligação: <rótulo> (<ENTIDADE_A> e <ENTIDADE_B>)`.
- **Cabeçalho:** exatamente `| Coluna | Tipo | Nulo | Chave | Padrão | Origem |`. As listas `Índices:` e `Restrições:` são opcionais.
- **Coluna:** `[a-z][a-z0-9_]*`, até 63 caracteres, única na tabela.
- **Tipo:** um dos tipos neutros da lista abaixo; o `enum` tem dois ou mais valores distintos em snake_case, como `enum(ativa, desativada)`. **Nulo:** `sim` ou `não`.
- **Chave:** `—`, ou uma ou mais de `PK`, `UK`, `UK:<grupo>` e `FK <tabela>.<coluna> (restringir|cascata|anular)`, separadas por vírgula. Cada tabela tem exatamente uma coluna `PK`; chave composta se faz com `UK:<grupo>`, que junta as colunas do grupo num índice único. A `PK` do tipo `id` sem FK é gerada pelo banco; com FK, não. A FK aponta para uma coluna `PK`, `UK` ou sozinha num grupo, do mesmo tipo; `anular` pede `Nulo` igual a `sim`.
- **Padrão:** `—`; um número, nos tipos numéricos; `verdadeiro` ou `falso`, no `booleano`; um dos valores, no `enum`; texto entre aspas simples, no `texto(n)`; ou `agora`, só no `data_hora`.
- **Origem:** um trecho literal de um item de "Atributos principais" da entidade da tabela; `<NOME_NO_ER>: <trecho>`, na coluna que copia um atributo de outra entidade numa relação de cópia; `relação: <rótulo>`, na coluna de FK, com o rótulo da relação no modelo conceitual, sem as aspas; ou `técnica`, só nos nomes de `[der].tecnicas`. O trecho casa com um item quando aparece dentro dele, sem diferença de maiúsculas e com os espaços colapsados; os acentos contam. Ele precisa casar com exatamente um item.
- **Índices:** itens `- (<coluna>, <coluna>)`, não únicos. **Restrições:** itens `- <coluna> <op> <número>`, com `>=`, `>`, `<=` ou `<`, ou `- <coluna> entre <a> e <b>`, só em coluna numérica.
- **Não persistido:** `- <NOME_NO_ER>: <trecho> — <motivo>`, com motivo, para o atributo que não vira coluna; `- <NOME_NO_ER>: (entidade inteira) — <motivo>` dispensa a entidade toda.
- **Fora das células:** as células não aceitam `[A CONFIRMAR]`. A inferência de tipo, tamanho, nulo ou padrão vai numa linha livre abaixo da tabela, como `[A CONFIRMAR] produto: texto(60), pelo limite da prosa`, que o `a-confirmar` do `checar` conta. A regra que a coluna não carrega, como o formato de um código ou uma faixa de hora, também vai numa linha abaixo da tabela, porque `Restrições:` é só para coluna numérica.

Tipos neutros, que o `der gerar` traduz para cada banco: `id` (como `PK` sem FK, vira identidade gerada), `inteiro`, `inteiro_grande`, `decimal(p,e)`, `texto(n)`, com n de 1 a 4000, `texto_longo`, `booleano`, `data`, `hora`, `data_hora` (em UTC por convenção), `json`, `uuid` e `enum(a, b)`; o padrão `agora` e as restrições também.

O documento não dá nome a chave, índice nem restrição.

## No passo 3

- Depois de cada mudança nas tabelas, `harness.py der gerar`: ele grava os `schema.*.sql` da pasta `[der].sql` e o bloco `erDiagram` da seção "Diagrama". Com o formato inválido, sai com 1 e um erro por linha, `<documento>:L<n>: <motivo>`, sem gravar; corrija a tabela e gere de novo.
- Os arquivos gerados e o bloco abaixo da linha `%% gerado por harness.py der gerar; não edite` não se editam: a mudança vai nas tabelas. O `harness.py der conferir` diz se estão em dia.

## No passo 4

- `harness.py checar`, com a saída colada. Em todo documento da fase, ele confere as sobras do molde (`sobras-de-molde`) e os diagramas (`mermaid`, `c4`, `links` e `drawio`, da seção "Diagramas"). No DER, também o formato (`der-formato`), o rastreio contra a camada 2 (`der-rastreio`), os gerados em dia (`der-em-dia`) e o manifesto do Workbench (`workbench`). Nos documentos com regra no perfil, também o `campos` (os campos de cada seção: presença, número de itens, IDs citados e formato), o `colunas` (as células de uma coluna das tabelas) e o `pendencia-na-linha` (o termo que só aparece com uma pendência aberta na mesma linha).
- No documento com bloco `mermaid`, o validador Mermaid, quando o Node existe, com a saída colada; sem o Node, diga ao usuário que a sintaxe do Mermaid não foi conferida; a CI do projeto só a confere com o workflow do guia "Validar os diagramas no CI".
- No documento da nuvem, peça ao usuário a exportação do `.drawio.svg` e rode o `checar` de novo: o `drawio` passa com o par em dia. Mudança no `.drawio` depois da exportação, inclusive a que o revisor pede no passo 5, pede exportação nova antes do passo 6.
- O passo do Workbench é do usuário nos itens 1 a 3, e o 4 é seu. Crie a pasta `[der].workbench` com `mkdir -p` e passe ao usuário o caminho absoluto do `schema.mysql.sql`, o dessa pasta e estes passos:
  1. No MySQL Workbench 8.0.47, no Windows ou no Mac em que ele abrir, File > Import > Reverse Engineer MySQL Create Script, com o `schema.mysql.sql`. Um erro de importação volta ao passo 3, com a correção nas tabelas do documento.
  2. Arrumar o diagrama EER e salvar nessa pasta os prints em PNG: um geral e recortes de até 2000 pixels no lado maior, para leitura.
  3. File > Export > Forward Engineer SQL CREATE Script, gravando o `workbench.sql` na mesma pasta. O `.mwb` é opcional. O export sai sem os `CHECK`, que o modelo do Workbench não guarda. A CI do projeto só compara o `workbench.sql` com o `schema.mysql.sql` com o workflow do guia "Validar os diagramas no CI", que roda o `bancos.py` com `[der]` no perfil; sem ele, a conferência fica com quem produz a camada 3.
  4. Quando o usuário avisa, você roda `harness.py der workbench`, que grava o `manifesto.txt`, que amarra os prints ao hash do `schema.mysql.sql`. Sem PNG ou sem `workbench.sql`, ele recusa e diz o que falta.

  Depois do `der workbench`, troque os itens vazios da seção "Workbench" do documento pelos links relativos dos prints e do `workbench.sql`. Até lá, o `checar` acusa esses itens no `sobras-de-molde` e o manifesto ausente no `workbench`.

  Mudança nas tabelas depois dos prints, inclusive a que o revisor pede no passo 5, faz o `checar` recusar com `prints do Workbench feitos de outra versão do DDL; refaça o passo do Workbench`: refaça-o antes do passo 6.
- O que fazer com cada recusa do `der-rastreio`:
  - entidade do modelo conceitual sem tabela: crie a tabela com `Entidade: <NOME>`, ou registre `- <NOME>: (entidade inteira) — <motivo>` em "Não persistido";
  - atributo sem coluna: crie a coluna com um trecho do item na Origem, ou registre o atributo em "Não persistido"; o atributo que é a própria relação, como "o pedido a que o item pertence", já coberta pela FK com `relação:`, vai para "Não persistido" com o motivo `é a relação <rótulo>, na FK <tabela>.<coluna>`;
  - origem que não casa com nenhum item: copie o trecho do item como está, com os acentos; origem que casa com mais de um: use um trecho maior;
  - relação sem FK nem tabela de ligação: crie a coluna de FK com `relação: <rótulo>` numa tabela de uma das entidades, apontando para uma tabela da outra, ou a tabela com `Ligação: <rótulo> (<A> e <B>)`;
  - `relação:` que não é uma relação entre as duas entidades: use o rótulo do modelo conceitual; a que é de cópia: tire a FK e copie os atributos com a Origem `<NOME_NO_ER>: <trecho>`;
  - origem de cópia sem relação de cópia entre as entidades, ou entidade que falta no modelo conceitual: a correção é na camada 2; suba a escada de `.claude/harness/nucleo/nucleo/planejamento/pendencias.md`, com `--causa camada-3` se a resposta abrir pendência;
  - `técnica` fora de `[der].tecnicas`: dê à coluna uma Origem de atributo; o link da linha `Entidade:` que não resolve: corrija o caminho.

## No passo 5

- O `revisor-requisitos` recebe as fontes em texto: o documento, o modelo conceitual e os documentos das entidades das tabelas. Imagens não vão; os prints do Workbench quem confere é o usuário.
- O revisor confere o que o script não decide: o tipo, o nulo e o valor de enum de cada coluna contra a prosa do atributo de origem, por exemplo "até 250 caracteres" virar `texto(250)`.
- Nos documentos de diagramas, o revisor lê os blocos `mermaid` e o `.drawio` como texto; o `.drawio.svg` quem confere é o usuário.
- Nos contratos externos, o revisor recebe também os guias que os links do Exemplo citam e confere que o pedido e a resposta em JSON saíram deles. Na entrega e operação, ele confere a coerência entre a Resposta e o Executa de cada risco. Passe a conferência do documento ao revisor numa linha logo depois do bloco do despacho.

## Diagramas

- Os diagramas ficam em blocos de três crases do tipo `mermaid` no próprio documento, que o GitHub renderiza. A primeira linha útil do bloco é um destes tipos: `flowchart`, `graph`, `sequenceDiagram`, `classDiagram`, `stateDiagram-v2`, `erDiagram`, `C4Context` ou `C4Container`. O bloco só com o tipo, `title` ou comentários `%%` é vazio, e o `checar` o recusa; o bloco gerado do DER antes do primeiro `der gerar` não conta.
- **Fluxos:** um `flowchart` por fluxo que tem ramificação, estado ou troca de ator; o fluxo linear fica no texto. Cada fluxo traz as listas Atores, Telas, com o link do documento de cada tela, e Requisitos, pelos IDs. O `checar` confere os links (`links`) e os IDs (`ids-citados`).
- **Arquitetura da aplicação:** um `C4Context` e um `C4Container`, cada um seguido da linha `Legenda:` e de uma lista com ao menos um item. `Container`, `ContainerDb` e `ContainerQueue` levam tecnologia e descrição; `Person`, `System`, `System_Ext` e `SystemDb`, descrição; `Rel`, rótulo. A tecnologia fica `[A DEFINIR no Avançado]` até o ADR dela. Depois, um `flowchart` com um `subgraph` por camada ou módulo e o `sequenceDiagram` do fluxo principal, com `par` no que corre em paralelo e `alt` nos caminhos alternativos, como demora e recusa. O `checar` confere as chamadas do C4 (`c4`); se a tecnologia tem ADR, o revisor do gate.
- **Estrutura do código:** a árvore de pastas num bloco de três crases do tipo `text` e as regras de dependência numa lista; sem `treeView-beta` e sem imagem gerada. Logo depois das regras de dependência, a tabela das áreas, `| Área | Pastas |`: uma linha por nome de "Onde vale" das regras de arquitetura dos ADRs, "todos" inclusive, com as pastas que ele cobre, entre crases e separadas por vírgula. Nenhum "Onde vale" fica fora da tabela; o `colunas` do `checar` confere a coluna Pastas no passo 4.
- **Nuvem:** o diagrama é um `.drawio` na pasta do documento, que você escreve em XML sem compressão: as células `0` e `1`, um vértice com rótulo por serviço, as arestas com `source` e `target` e as strings de estilo das bibliotecas oficiais do provedor (AWS ou GCP). O usuário abre o arquivo no draw.io web, pelo Safari, ou na extensão do VS Code, ajusta, grava o `.drawio` e exporta o `<nome>.drawio.svg` na mesma pasta, em SVG com "Include a copy of my diagram". Na extensão do VS Code, a exportação é o comando "Draw.io: Export To..." em `.svg`, que já embute a cópia do diagrama; a janela sugere `<nome>.svg`, e o nome tem de ser `<nome>.drawio.svg`. O "Convert To..." troca o `.drawio` pelo SVG e apaga a fonte: não o use. O `checar` confere o XML e compara o `.drawio.svg` com o `.drawio`, célula a célula (`drawio`); o gate repete a comparação (`drawio-em-dia`). Não edite o `.drawio.svg`, nem quando a extensão o abre como diagrama: a edição some na exportação seguinte; edite o `.drawio` e exporte de novo.
- **Sintaxe:** o `checar` não roda o Mermaid. Quando o Node existe (`command -v node`), rode `npm ci --prefix .claude/harness/nucleo/nucleo/planejamento/ferramentas` se `.claude/harness/nucleo/nucleo/planejamento/ferramentas/node_modules/` não existe e, a cada documento, `node .claude/harness/nucleo/nucleo/planejamento/ferramentas/validar-mermaid.mjs <documento>`; ele sai com 0 e `OK: <n> blocos em <m> arquivos`, ou com 1 e `<arquivo>:L<linha da cerca>: <erro>` no primeiro bloco inválido de cada arquivo. O `harness.yml` do projeto não o roda, porque só confere as invariantes (`invariantes --base`); quem o roda é o workflow do guia "Validar os diagramas no CI", quando o projeto o copiou. Sem ele, a sintaxe Mermaid dos documentos do projeto só é conferida aqui, no passo 4.
- **Imagens:** entram no repositório só os prints do Workbench e o `.drawio.svg`. SVG ou PNG de um bloco Mermaid só a pedido do usuário, com `PUPPETEER_CHROME_SKIP_DOWNLOAD=true npx -y -p @mermaid-js/mermaid-cli@12.0.0 -p puppeteer@25.3.0 mmdc -i entrada.mmd -o saida.svg`; o Chrome que ele usa não recebe correção de segurança e serve só para renderizar arquivo local.

## ADRs

- Cada decisão é um bloco `### Decisão: <título>` do arquivo dos ADRs (`caminhos.adrs`), com os campos do molde e mais duas linhas: `- **Status:**`, com `proposto`, `aceito` ou `substituído por <título de outra decisão>`, e `- **Data:**`, com `AAAA-MM-DD`.
- A Justificativa cita pelo menos um ID de requisito definido, com um dos prefixos de `ids.prefixos` do perfil.
- O campo Regras de arquitetura, entre Alternativas descartadas e Status, tem um item aninhado por regra, no imperativo: `RA-NN: <regra>. Onde vale: <módulo, processo ou todos>. Como se confere: <modos>.`, com os modos `teste`, `lint` e `revisão`, um ou mais, separados por `, `. Sem regra, vai o item único `nenhuma: <motivo>`. O ID da regra nunca se reusa: a regra tirada deixa buraco, e a de um ADR substituído fica no texto, como histórico. O `campos` do `checar` confere o formato no passo 4.
- Na seção dos itens mínimos, cada item do molde fica `[x]` e termina com ` — <título de uma decisão do documento>` ou ` — não se aplica: <motivo>`.
- ADR além dos mínimos só entra se valerem os três critérios:
  1. difícil de reverter: mudar de ideia depois custa caro;
  2. surpreendente sem contexto: quem ler depois vai perguntar por que foi feito assim;
  3. resultado de um trade-off real: havia alternativas de verdade, e uma foi escolhida por motivos específicos.

  Decisão fácil de reverter, óbvia ou sem alternativa não vira ADR. Costumam passar: a forma da arquitetura, a integração entre partes do sistema, a tecnologia que prende (banco, fila, autenticação, onde roda), as fronteiras de escopo, o desvio deliberado do caminho óbvio, a restrição que o código não mostra e a alternativa recusada por motivo que não é óbvio.
- O script do gate confere a forma (`adr-minimos` e `adr-com-requisito`); o revisor do gate, os três critérios.

## Contratos externos

- Um contrato por operação externa, numa seção `### CTR-NN <sistema>: <operação>`, na ordem em que a sequência da arquitetura da aplicação chama. Os avisos de mesmo formato que um sistema manda ao produto ficam juntos num contrato só.
- Os nove campos do cabeçalho, um por item: Quem chama; Contêiner, o do C4 que faz ou recebe a chamada; Versão da API; Autenticação, o meio, nunca o segredo; Tempo limite; Novas tentativas; Limite de uso; Recusa e erro; e Exemplo. Em Recusa e erro, a recusa, a resposta que a regra de negócio trata como "não atende", fica separada do erro técnico, com os códigos conhecidos.
- O valor que nenhuma fonte dá fica "desconhecido", com a pendência que o descobre na mesma linha: uma aberta com destino no mesmo teste, ou, pela pergunta da escada de `.claude/harness/nucleo/nucleo/planejamento/pendencias.md`, uma nova, com "Abrir pendência" recomendado e `--causa pesquisa-sem-fonte`, porque o `pendencia-na-linha` exige o ID. A pendência está aberta, tem destino num teste antes da virada e nunca leva o marcador de pendência do gate da fase, que o `pendencias-do-gate` cobraria no gate. O `pendencia-na-linha` a confere no passo 4.
- A tabela dos campos usados tem o nome do campo, o tipo, se é obrigatório, a coluna que liga o campo ao dado do produto e a Fonte. A Fonte de cada linha é um link para a seção do guia do sistema, numa pasta de `caminhos.fontes`, ou para a documentação oficial dele. O `colunas` confere que toda linha tem o link, e o `links`, que o guia existe; a âncora da seção, o `links` não confere: confira-a ao escrever.
- O pedido e a resposta em JSON, nos dois blocos do molde, são copiados da fonte do link do campo Exemplo. Nenhum script lê os blocos; o revisor do ciclo confere que saíram da fonte.
- O contrato fixa a versão usada, e a troca de versão vira um risco `RSC-NN` na entrega e operação. O fato novo que um teste traz corrige o contrato e o guia.
- No passo 0, o `pesquisador-fatos` lê os guias por seção e devolve `arquivo:linha`.
- O contrato interno, o OpenAPI, o JSON Schema, o esquema de validação e o exemplo gravado de verdade nascem no desenvolvimento, por ficha.

## Entrega e operação

- Estratégia de testes: os níveis, com o que cada um prova e onde roda; a prova de cada RNF, numa linha ao menos, com o nível e o ambiente, que o gate cobra (`ids-cobertos`); a prova de cada contrato externo, numa linha ao menos, que cita o `CTR-NN` e que o revisor do gate cobra; e os testes de descoberta, um por pendência que só um teste antes da virada responde.
- Riscos, um `### RSC-NN: <nome>` por risco, com Descrição, Probabilidade (baixa, média ou alta), Impacto (baixo, médio ou alto), Resposta, Gatilho e Executa. A Resposta é `evitar`, `mitigar` ou `aceitar`. Este documento vem antes das fichas, e por isso o risco não cita ficha. Com `evitar` ou `mitigar`, o Executa diz `ficha` quando a resposta é trabalho de construção, ou começa por uma pendência ou por uma `RA-NN`. Com `aceitar`, ele diz `aceito por <quem> em <AAAA-MM-DD>`. A ficha que faz o trabalho cita o `RSC-NN` na Fonte, e o gate cobra que todo risco com `ficha` esteja numa ficha. O `campos` confere o formato da Resposta e do Executa; a coerência entre os dois fica com o revisor do ciclo.
- Ameaças, um `### AME-NN: <nome>` por ameaça, num STRIDE leve por fronteira de confiança entre os contêineres do C4, com Fronteira, Categoria (uma letra do STRIDE), Mitigação e Cobre. Cobre é o RNF de segurança que a cobre, que o gate cobra (`secoes-com-id`). A tabela de dados pessoais amarra cada dado aos RNF de segurança e às colunas do DER físico.
- Objetivos de serviço, um `### SLO-NN: <nome>` por objetivo, com SLI (o que se mede e de onde), Meta, Janela, Origem, Orçamento de erro e Alerta (o limiar, quem recebe e o canal). A Origem é o RNF de que o objetivo sai, que o gate cobra (`secoes-com-id`).
- Recuperação: o RPO, o RTO e o teste de restauração, com o nível da estratégia de testes.
- Virada e volta: cada gatilho de volta é uma condição medida que cita o `SLO-NN` depois da condição; depois vêm os passos de volta, quem decide e a janela de volta.
- Os testes concretos, os runbooks finais e os painéis nascem no desenvolvimento, por ficha.

## Fichas

- Marcos: a tabela `| Marco | Resultado de negócio | Prazo |`, um marco por linha, na ordem de entrega, com o prazo em dias úteis ou `—`.
- Uma seção `### FICHA-NN: <slug>` por ficha, com os campos um por item:
  - Marco: um só, da tabela;
  - Depende: os `FICHA-NN` e as pendências de que ela precisa, separados por `, `, ou `—`;
  - Tamanho: `P` (até 1 dia de uma pessoa), `M` (até 3 dias) ou `G: <motivo>` (até 5 dias, só quando dividir deixaria uma fatia sem aceite próprio);
  - Contexto: `sim` quando quem constrói a ficha precisa ler do planejamento mais do que as fontes que ela cita por ID, como um fluxo inteiro ou o histórico de uma decisão, e `não` quando essas fontes bastam; o que o `sim` pede ao desenvolvimento fica para o harness de desenvolvimento;
  - Fonte;
  - Objetivo: o resultado, não a solução, em até duas frases;
  - Escopo;
  - Fora: o que das FN citadas fica em outra ficha, com o ID dela, ou `—`;
  - Restrições: as `RA-NN` e os RNF;
  - Aceite.
- Fonte por ID: as FN, os RF, os RNF e as RN, as RA, os contratos, os riscos, as ameaças e os objetivos de serviço que a ficha cobre; as telas e o ADR, por link. A ficha que mitiga um risco cita o `RSC-NN`. A ficha sem FN, como a da esteira ou a da infraestrutura, cita RA ou RNF, porque o `campos` pede um ID na Fonte.
- Aceite: os itens das FN por referência, como `Itens FN-XXX-NN.1 a FN-XXX-NN.3`, mais os itens da fatia, cada um com a condição, o resultado e o RF ou RNF. Nenhum item começa por ID.
- O ID da ficha nunca se reusa: a ficha dividida ou tirada deixa buraco.
- O que o gate cobra: toda FN numa ficha e todo risco com `ficha` numa ficha (`ids-cobertos`); o Depende sem ciclo, sem ficha que não existe, sem ficha de marco posterior e com a pendência no backlog (`dependencias`). O revisor do gate confere que cada ficha atende as FN que cita e que as fichas de cada marco com prazo cabem nele, pelo tamanho.

## Origem

Os três critérios e o Status das decisões vêm, adaptados, de `skills/engineering/domain-modeling/ADR-FORMAT.md` do mattpocock-skills 1.3.1, commit `4588b32`, traduzidos e reduzidos.

Copyright (c) 2026 Matt Pocock

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
