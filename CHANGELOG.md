# Changelog

## v0.3.0 — 2026-11-10

O plugin passa a vir de um repositório público, e o CI dos projetos, a rodar sem credencial: o `harness.yml` vira arquivo gerado, a stack do projeto se instala no CI pelo perfil, e o harness avisa e explica a ferramenta que falta.

### O que mudou desde a 0.2.7

- O plugin é publicado no repositório público `Ela-Decora/ela-harness`, sob a licença MIT, com o `LICENSE` e o `THIRD-PARTY-NOTICES.md` na raiz. O `Ela-Decora/ElaHarness` segue privado, como origem: cada tag `v*` dele vira, pelo workflow `publicar.yml`, um commit e a mesma tag na distribuição, com o recorte do `.gitattributes`, sem os testes, as specs e a configuração da origem. O `repository` do `plugin.json`, o `repo` do `.claude/settings.json` dos modelos, o README e o `iniciar` apontam a distribuição, e o `iniciar --conferir` dá `plugin: falta` no projeto ainda fixado na origem. O manual fica só com o que serve a quem usa: sai "Evoluir o harness", e entram os guias "Relatar um problema" e "Sair da origem privada".
- O `.github/workflows/harness.yml` passa a ser arquivo gerado nas duas trilhas: o `iniciar` o escreve, e o `harness.py gerar` o mantém, pela `ref` do `.claude/settings.json`. Ele baixa a distribuição nessa tag, sem token, e chama a action do CI do plugin, `ci/<trilha>/action.yml`, que roda as invariantes e, no desenvolvimento, a instalação do CI e as verificações; o job segue com o nome `harness`. O `gerar --check` e a `gerados-em-dia` o conferem byte a byte, a guarda recusa editá-lo com `arquivo gerado: rode harness.py gerar`, e o item `ci` do `iniciar --conferir` diz `ci: falta: .github/workflows/harness.yml igual ao gerado; rode harness.py gerar`. O `gerar` recusa o arquivo com `harness.yml: o plugin carregado é v<versão> e o .claude/settings.json fixa <ref>; reinstale o plugin` ou `harness.yml: o .claude/settings.json não fixa a versão do plugin (<motivo>); rode harness.py iniciar --conferir`. Sem o núcleo baixado, o CI cai com `::error title=harness: plugin não baixado::`, a tag e o que conferir.
- O perfil de desenvolvimento ganha `[desenvolvimento.ci] instalar`, a lista de comandos que instala a stack do projeto no CI, vazia no modelo. O `harness.py ci instalar` os roda um por um, por `sh -c`, na raiz, com 900 s cada, e passa ao seguinte o PATH e as variáveis gravadas no `GITHUB_PATH` e no `GITHUB_ENV`. Só roda com `GITHUB_ACTIONS=true`; fora dele, recusa com `instalação do CI: só roda no CI (GITHUB_ACTIONS=true)`. As linhas são `instalação do CI: nada a instalar`, `instalação do CI: <comando>: ok (<s> s)`, `instalação do CI: <comando> falhou (saída <c>)` e `instalação do CI: <comando> passou de 900 s`, e o primeiro que falha para a lista. O serviço que fica de pé, como o banco, sobe com `docker compose up -d`: o que vai com `&` morre com o grupo de processos do comando.
- O `bloco finalizar` avisa, sem recusar, `aviso: [desenvolvimento.ci] instalar está vazio e <nomes> rodam no CI, que começa sem a stack`, quando a lista está vazia e alguma verificação do momento `finalizar` roda um comando que não é do harness.
- No CI, com `GITHUB_ACTIONS=true`, a verificação que falha lê a saída inteira e, para cada comando não encontrado pelo shell (`sh: <n>: <cmd>: not found` ou `<cmd>: command not found`), diz `<nome>: a saída diz que falta o comando <cmd>; declare a instalação em [desenvolvimento.ci] instalar`. Cada falha, a da instalação do CI inclusive, gera a anotação `::error title=harness: <nome> falhou::<primeira linha>`, que aparece no resumo do PR. Fora do CI, a saída fica como antes.

Passo de migração dos projetos gerados da `v0.2.1` à `v0.2.7`, que baixam o núcleo do `Ela-Decora/ElaHarness` com o segredo `ELA_HARNESS_TOKEN`: o guia [Sair da origem privada](docs/guias.md#sair-da-origem-privada), à mão e uma vez. Ele troca o marketplace pela distribuição e reinstala o plugin, roda o `harness.py gerar`, declara a stack em `[desenvolvimento.ci] instalar` e commita; depois, o segredo pode sair. Quem não migra segue na origem, com o token.

Aviso: as actions do `harness.yml` vão fixadas por SHA, que sobe com a versão do plugin, e o PR do Dependabot nesse arquivo fica vermelho com `desatualizado: .github/workflows/harness.yml; rode harness.py gerar`. Feche-o, ou tire o arquivo do Dependabot pelo `exclude-paths`, como diz o guia: quem atualiza o `harness.yml` é o `harness.py gerar`.

## v0.2.7 — 2026-11-09

A camada 2 do planejamento ganha a skill `/ela-harness:gerar-modulos`, que gera em rascunho as entidades, as telas e os módulos a partir do escopo aprovado, e o `proximo` que a recomenda.

### O que mudou desde a 0.2.6

- A skill `/ela-harness:gerar-modulos` lista as entidades, as telas e os requisitos do escopo aprovado, cada um com a fonte, e abre uma rodada só, com a proposta de módulos, o uso das entidades como modelo lógico e as dúvidas; cada resposta vira Ruling ou pendência na hora. Depois escreve em rascunho, sem commit, as entidades, as telas e, por último, os módulos, e roda o `harness.py checar`. O relato traz os arquivos, os `[A CONFIRMAR]` e o pacote seguinte, que segue no `/ela-harness:refinar-documento`. A sessão que cai no meio retoma do Ruling da proposta e grava só o que falta. Só o usuário a invoca.
- O `proximo` recomenda a `gerar-modulos`: o item `gerar` vai primeiro na fila, com o motivo `nenhum <padrões do por, juntados por " ou "> na fase`, quando a fase tem item `ligados` no gate, nenhum documento do `por` está no disco nem em refino, e os obrigatórios da fase já estão aprovados. O módulo em refino segura o item, e a pendência do gate que pede um módulo pelo nome, sem módulo no disco, traz o `gerar` antes do documento novo.
- Os moldes de tela e de entidade ganham o que a skill preenche: a tela, os estados e a navegação; a entidade, o ciclo de vida.
- O `harness.py perfil --para gerar-modulos` dá o bloco "Este projeto" da skill: a fase, os itens `ligados` e `ids-cobertos` do gate, o molde de cada padrão e as fontes aprovadas. Na fase sem item `ligados`, imprime `ERRO: <gate> sem item ligados; a skill não se aplica à fase <fase>`.
- O revisor do `refinar-documento` confere a entidade, a tela e o módulo pelos princípios da `gerar-modulos`, com o arquivo de princípios do tipo no prompt de despacho.
- O CLAUDE.md gerado do projeto de planejamento ganha a linha da `gerar-modulos`, só quando o perfil tem item `ligados`, e o manual ganha o guia "Gerar os módulos".

Passo de migração do projeto de planejamento:

1. `harness.py gerar`, para a linha nova do texto gerado; até ele, o `gerados-em-dia` acusa.
2. Só com a camada 2 sem tela nem entidade aprovada: no terminal, na raiz do projeto, o trecho abaixo, com o nome do projeto, o mesmo do título dos moldes que o projeto tem, e a `[moldes].pasta` do perfil no lugar de `planejamento/Templates`, se for outra; as duas linhas que ele imprime vão para `[moldes.liberados]` do `.claude/perfil.toml`, com a seção criada se faltar, e o commit sai sem `--no-verify`. Com tela ou entidade aprovada, fique com os moldes antigos: a skill escreve no molde que o projeto tem. Os rascunhos de tela e de entidade já escritos no molde antigo falham no `checar` depois da cópia: ganham os títulos novos no `/ela-harness:refinar-documento`, ou se apagam e a skill os gera de novo.

```bash
python3 - "<nome do projeto>" <<'PY'
import hashlib, sys
from pathlib import Path
origem = Path(".claude/harness/nucleo/modelo/planejamento/planejamento/Templates/2-intermediario/Templates")
destino = Path("planejamento/Templates/2-intermediario/Templates")
for nome in ("_modelo-tela.md", "_modelo-entidade.md"):
    dados = (origem / nome).read_text(encoding="utf-8").replace("{{PROJETO}}", sys.argv[1]).encode("utf-8")
    (destino / nome).write_bytes(dados)
    print(f'"2-intermediario/Templates/{nome}" = "sha256:{hashlib.sha256(dados).hexdigest()[:12]}"')
PY
```

## v0.2.6 — 2026-11-09

Os três defeitos que travaram a camada 2 do planejamento: o título da funcionalidade, que o perfil do modelo não casava, as pendências que pedem um documento novo e o gate recomendado sem conferir se passa, e a regra de link da passagem, que só o leitor frio do gate aplicava.

### O que mudou desde a 0.2.5

- O perfil do modelo de planejamento casa os títulos dos moldes: as `partes_variaveis` ganham `'<MÓD>' = '[A-Z]+'` e `'-NN\b' = '-[0-9]{2,}'` e perdem a `'Funcionalidade:$'`, e o `secoes-com-id` do G2 passa a procurar `titulo = "### Funcionalidade"`, que acha também a funcionalidade escrita sem o ID. Antes, o `checar` reprovava todo módulo pelo `<MÓD>` e pelo `NN` literais, e o `secoes-com-id` passava sem conferir nada.
- O `proximo` põe na fila o documento novo que uma pendência aberta do gate pede: um item da categoria `novo`, com a ação `/ela-harness:refinar-documento <caminho>`, depois dos obrigatórios e antes das revisões. O motivo é `documento novo: <IDs> (<marcador>)`, com `; o nome sai da pendência` quando o destino é uma pasta, e `; a pasta, com o usuário` quando o destino é um nome sem irmãos, ou com irmãos em mais de uma pasta, e o caminho leva a `<pasta>` literal. A revisão com `antes do <arquivo>.md` entra antes do item novo desse arquivo.
- O `proximo` põe antes do gate a pendência que nenhum documento da fila resolve: `resolver <ID> com o usuário`, com o motivo `nenhum documento da fila a resolve: <destino>`. O módulo, o item de derivados, o rascunho, o obrigatório, o documento em refino e o derivado em rascunho de um módulo da fila cobrem a pendência que cita o nome deles; o documento novo e as revisões cobrem a que trazem pelos IDs. Antes, o gate era recomendado com `fila da fase vazia` e reprovava depois, no `pendencias-do-gate`.
- O `harness.py proximo` roda, com o gate como recomendado, os itens de script dele, sem o leitor frio, e mostra logo abaixo do motivo a linha `Pré-checagem do <gate>: <n> FAIL`, com até 3 linhas FAIL e `  +<k> FAIL: harness.py gate <gate> --verbose` quando há mais; `Pré-checagem do <gate>: sem FAIL`; ou `Pré-checagem do <gate>: não rodou: <motivo>`, quando a pré-condição do gate recusa, e `não rodou: <Tipo>: <primeira linha da mensagem>`, quando outro erro sai do gate, sem derrubar o `proximo`. Com `--verbose`, todas as linhas FAIL. O hook e o `fechar` não a rodam, e o `proximo` segue só lendo.
- O `links` do `checar` roda em todo documento de uma pasta de fase, com ou sem `[der]`, e aplica a regra de link da passagem: além do `link <destino> não resolve`, passa a dar `link <destino> é uma pasta; linke um arquivo` e `link <destino> excluído da passagem (<chave>)`, para o destino em `rascunho`, `status`, `decisoes`, `backlog`, `estudos`, `atritos`, `leitor_frio` ou na pasta `.claude`. O `checar-da-fase` dos gates passa a ver o link de toda fase. As recusas da exportação da passagem não mudam.

Passo de migração do projeto de planejamento: no `.claude/perfil.toml`, troque a linha das `partes_variaveis` por

```toml
partes_variaveis = { '<!--.*?-->' = '.+', 'XXX' = '[A-Z]+', '<MÓD>' = '[A-Z]+', '-NN\b' = '-[0-9]{2,}' }
```

sem a `'Funcionalidade:$'`, e ponha `titulo = "### Funcionalidade"` no `secoes-com-id` do G2.

Aviso: o `checar` passa a conferir os links de todo documento das pastas das fases, e o documento aprovado com link para uma pasta ou para um caminho excluído da passagem falha na próxima revisão e no `checar-da-fase` do gate. Troque o link por um arquivo.

## v0.2.5 — 2026-11-08

Os Minor das revisões da 6c e da 6d-repositorio: a guarda de segredos que acusava o renomeado, o `--enviar` que repetia comentário e consultas, o trecho do Context Packet com título do tamanho do fato, o `passagem-em-dia` que não olhava os `ids` e o `importar` que deixava passar o PR de outra versão, o órfão no índice e o arquivo ignorado.

### O que mudou desde a 0.2.4

- O `sem-segredos` compara o arquivo renomeado ou copiado com o arquivo de origem dele, e não com o vazio: só o segredo que o renomeado acrescenta é achado, e o segredo antigo, que já estava no arquivo, não é mais acusado. No `mv` sem `git add`, no modo `arvore` do hook `Stop`, o git não pareia os nomes, e o arquivo segue comparado com o vazio. O arquivo que sai de uma pasta de `segredos_isentos`, renomeado ou copiado, é conferido contra o vazio: a origem isenta nunca foi conferida, e o segredo dela não conta como já na base.
- O `passagem publicar --enviar` conta como igual o comentário da issue com `\r\n`, e a issue que já tem o comentário não ganha outro. As tags do `origin` vêm de um `git ls-remote` só, no lugar de um por tag; a tag de nome parecido, como `passagem/v2x`, fica de fora.
- Os títulos do trecho de um fato no Context Packet descem abaixo do `### <ID>`: o mais alto vai a `####` e os outros o mesmo tanto, até `######`, sem mexer nos blocos de código. O trecho sem título, ou com o mais alto já em `####` ou abaixo, sai igual.
- O `passagem-em-dia` confere os `ids` do manifesto: o `arquivo` de cada `ids[]` tem de estar em `arquivos`, e o trecho refeito a partir da primeira linha dele tem de ter as linhas e o `sha256` do manifesto. Duas linhas novas no resumo: `ids.<ID>: <passagem>/<arquivo> não está em arquivos; a cópia muda só por harness.py importar` e `ids.<ID>: o trecho <passagem>/<arquivo>:<primeira>-<última> difere do manifesto; a cópia muda só por harness.py importar`. O `ids[]` de um arquivo que falta ou difere não é conferido, e as `pendencias` ficam de fora.
- O `importar` recusa, antes do clone e sem gravar nada, com o PR aberto da `docs/passagem-v<m>`, de outra versão (o de menor número, quando há mais de um): `PR #<n> da passagem/v<m> ainda aberto: <url>; mescle-o ou feche-o antes de importar a v<N>`. O gerado órfão que o `importar` apaga sai também do índice, pelo `git rm --cached`, e não volta ao primeiro commit.
- O `importar` para, sem commit e com saída 1, com o arquivo que o git ignora entre os que ele põe no commit: `o git ignora <k> arquivos (1 arquivo, no singular) que o importar põe no commit, como <primeiro>; ajuste o .gitignore e rode harness.py importar v<N> de novo`. Vale no primeiro commit e no worktree do PR, antes do `git add`. O link do núcleo, `.claude/harness/nucleo`, que o hook refaz e o `.gitignore` ignora de propósito, não conta.

Não há passo de migração: o `contexto.md` novo sai no próximo `harness.py contexto`.

## v0.2.4 — 2026-11-08

O ciclo do bloco se protege pelo próprio texto nos pontos em que as skills de terceiros falharam no uso: a spec que não leu o código, o plano que não rodou o que fixa, a sessão compactada, o teste que gravou fora do worktree e o item manual que chegava ao dono sem conferência.

### O que mudou desde a 0.2.3

- Spec e plano do bloco: a spec cita com `arquivo:linha` o código de que o desenho depende, também na `## Correção` da spec curta; o plano roda uma vez, antes do `bloco planejado`, os fragmentos que fixa com os dados de teste, e grava a aprovação na linha `**Spec approval:**` e as decisões do dono na seção `## Owner decisions`.
- A linha de sessão nova: com a sessão compactada ou o pedido do dono de outra sessão, o `planejar-bloco`, o `executar-bloco` e o `revisar-bloco` entregam a linha pronta para colar numa sessão aberta na árvore principal, na forma da `## Retomada` do `ciclo.md`, no lugar de invocar a skill seguinte.
- Os agentes `implementador-mecanico`, `implementador-integracao` e `corretor-tardio`: nenhum teste roda um programa externo real que grava fora do worktree e da pasta temporária do teste, e o relato diz que os arquivos dele ficaram sem mudança.
- O item manual de antes do merge: a sessão confere sem o dono as pré-condições que um comando confere, invoca o `wizard` pela ferramenta Skill só com o que sobrou para uma pessoa e grava o script pelo Write em `.superpowers/wizard/`, sem rodar `bash` na lane. O `ciclo.md` dispensa o `cp`, o `bash -n` e o `chmod` do `wizard`.
- As mensagens que mandam rodar o `lane fechar` (a linha `closing` do `bloco status`, as recusas do `bloco finalizar` e do `bloco corrigir` com o PR mesclado e o fim do `finalizar-bloco`) passam a dizer `de uma sessão aberta na árvore principal, ou pelo terminal como última ação`, no lugar de `fora da lane`.

Passo de migração: rode `harness.py gerar` no projeto de desenvolvimento, para o `ciclo.md` novo.

## v0.2.3 — 2026-11-07

O ciclo do planejamento deixa de cair em três pontos: a aprovação que o hook do prompt não anotava, o `--em` preso à pasta do planejamento e o dossiê que cortava os Rulings.

### O que mudou desde a 0.2.2

- O hook do prompt (`UserPromptSubmit`) passa a responder pela via curta, sem carregar o `harness.py`: a mediana caiu de 164 ms, pela `main`, para 70 ms, pela via curta, no ensaio, no Python 3.12.3, com 4 CPUs. O `PreToolUse` e o `UserPromptSubmit` sobem o `timeout` de 10 s para 30 s, para dar folga em máquina lenta: o hook que estoura é cancelado, o prompt perde a `resposta` e o `PreToolUse` deixa a ferramenta passar sem a guarda.
- O `--em` aceita o caminho a partir da raiz do repositório ou o nome curto, quando ele é único entre os arquivos que o git não ignora, com commit ou sem. O `--origem` não muda.
- O dossiê traz o bloco de Rulings completo, com os prováveis alvos, e o resumo ganha a contagem `prováveis alvos`.

Não há passo de migração: o limite novo dos hooks chega com a troca de versão do plugin.

## v0.2.2 — 2026-11-06

O plugin deixa de trazer o produto de um cliente: as fixtures, os testes e os exemplos passam a um produto fictício, e o texto gerado do planejamento fica neutro.

### O que mudou desde a 0.2.1

- O texto gerado do planejamento troca quatro frases que só valiam para um projeto: a dos atritos, a do commit, a do pacote e a do aviso do hook. A do commit passa a dizer "o commit convencional do projeto": o `CLAUDE.md` do projeto, na parte que o projeto escreve, passa a dizer a própria convenção de commit.
- As fixtures e os testes usam o produto fictício das fixtures da trilha de desenvolvimento, uma biblioteca, no perfil, no DER, nas fixtures do `checar` e dos diagramas e nas strings dos testes. Sai a fixture do `CLAUDE.md` da tag do porte.
- Os exemplos das referências `spec-curta.md` e `spec-normal.md` do `planejar-bloco` e o exemplo do molde `requisitos-negocio.md` usam o mesmo produto fictício.

Não há passo de migração: o texto gerado muda no próximo `harness.py gerar`.

## v0.2.1 — 2026-11-06

A trilha de desenvolvimento fica pronta para a prova de um serviço chamado por POST, com corpo, cabeçalho e segredo no endereço.

### O que mudou desde a 0.2.0

- A prova por POST na `## Verificação externa` da spec do bloco: a linha da prova passa a ser `<alias> GET|HEAD|POST <caminho> -> <código>`, e o item ganha o subitem opcional `pedido:`, com um bloco JSON de `cabecalhos` (nos três métodos), `corpo` (só no POST) e `campos` (no GET e no POST, na notação `itens[].situacao`, com `"*"` para presente e não nulo). O segredo entra pelo marcador `{env.NOME}`, no caminho, nos cabeçalhos e nos textos do corpo: o valor vem do ambiente do processo ou dos arquivos de env da lane, e nunca vai para a saída, para o `aceitacao.md` nem para um commit. A falha de campo não mostra valores. A conferência lê o pedido da spec aprovada, na lane e no `lane fechar`, e recusa a spec que mudou depois da aprovação.
- O `lane fechar` recusa remover a lane em que a sessão do Claude Code foi aberta (`CLAUDE_PROJECT_DIR`), mesmo quando o comando roda da árvore principal.

Não há passo de migração: as provas GET e HEAD de hoje seguem valendo.

## v0.2.0 — 2026-11-05

O harness inteiro no plugin, nas duas trilhas, com o núcleo das fases 5 e 6 do projeto em que ele nasceu. O plugin passa a se chamar `ela-harness`.

### O que mudou desde a 0.1.0

- O plugin `harness` vira `ela-harness` (`ela-harness@ela-harness`). As skills passam a `/ela-harness:<skill>` e os agentes a `ela-harness:<agente>`, no lugar de `/harness:<skill>`.
- Duas trilhas, que o `[projeto] harness` do perfil escolhe: `planejamento`, que ganha a camada 3 e o G3, a passagem e o gerador, e `desenvolvimento`, que conduz blocos de código por lanes, revisões e PR. Sem a chave, vale o planejamento.
- O núcleo sai de `harness/` e vai para três pastas: `nucleo/comum/`, `nucleo/planejamento/` (com as `ferramentas/`: o validador Mermaid e o `bancos.py`) e `nucleo/desenvolvimento/`. O `harness/gancho.py` do 0.1.0 é hoje o `nucleo/comum/gancho.py`.
- Oito skills (`iniciar`, `refinar-documento`, `gate-fase`, `assessor`, `planejar-bloco`, `executar-bloco`, `revisar-bloco` e `finalizar-bloco`), doze agentes e o workflow `revisao-do-bloco`. O plugin `ela-harness-papeis`, segundo plugin do marketplace, traz o mod que troca o modelo e o esforço dos agentes do ciclo do bloco.
- Os hooks (`SessionStart`, `PreToolUse`, `UserPromptSubmit` e `Stop`) vêm do `hooks/hooks.json` e rodam o comando da trilha. Ficam calados em projeto sem `.claude/perfil.toml`. O gancho refaz, a cada sessão, o link `.claude/harness/nucleo` para a raiz do plugin.
- O lançador `.claude/harness/harness.py` acha o núcleo pela `HARNESS_NUCLEO`, pelo link, pelo link da árvore principal (numa lane, que é uma worktree) e pelo registro de plugins. Sem núcleo, sai com 3 e mostra como instalar.
- O `iniciar` é `harness.py iniciar <trilha> [<pasta>] [--nome <nome>]`, e a skill é `/ela-harness:iniciar <trilha> [nome]`. Copia o modelo da trilha e o lançador sem sobrescrever (o que já existe fica, com `mantido:`), troca `{{PROJETO}}`, `{{DATA}}` e `{{ramo_principal}}`, liga o `core.hooksPath`, instala os plugins com `--scope project` e, no planejamento, roda o `gerar`. Não copia mais o núcleo, as skills, os agentes nem o mod. O `iniciar --conferir` confere a instalação.
- O texto do ciclo do planejamento é gerado: o `gerar` grava `.claude/harness/gerado/planejamento.md` a partir do perfil, e o `CLAUDE.md` do projeto o puxa pela linha `@.claude/harness/gerado/planejamento.md`. A guarda recusa a edição à mão dessa pasta. O `[ids]` do perfil ganha a chave opcional `formas`.
- Os modelos são `modelo/planejamento/` e `modelo/desenvolvimento/`. O `.claude/settings.json` deles fixa o marketplace na tag da versão e liga os plugins; os hooks saem dele.
- O manual vai para `docs/`, com a pesquisa, as specs, os planos, os atritos e o glossário em `docs/harness-planejamento/`. O `docs/pesquisa/` do 0.1.0 sai, e o histórico dele fica no git.
- Num projeto cujo `.claude/settings.json` já existe (o `claude plugin install --scope project` o cria), o `iniciar` mescla o que falta do modelo e diz `mesclado: .claude/settings.json`, sem tirar nada.
- O `moldes-intocados` aceita o molde acrescentado quando a base não tem arquivo na pasta de moldes, o que deixa o primeiro commit do repositório montado passar.

A instalação `--scope project` vale por pasta: cada clone novo roda uma vez o `claude plugin install <id> --scope project` de cada plugin da trilha (o lançador mostra o comando).

### Migrar um projeto de planejamento

Para levar à 0.2.0 um projeto que roda o núcleo copiado em `.claude/`:

1. Troque o `.claude/harness/*.py` pelo lançador: apague de `.claude/harness/` os módulos, as `ferramentas/`, os `tests/`, o `modelo/`, o `desenvolvimento/` e o `saida.md`, e copie o `modelo/lancador.py` para `.claude/harness/harness.py`. Os comandos `python3 .claude/harness/harness.py ...` seguem os mesmos. A `aprovacao/` e o `dossie/` ficam.
2. Tire de `.claude/` as skills, os agentes e o manual: `.claude/skills/`, `.claude/agents/`, `.claude/README.md` e `.claude/docs/`.
3. Tire os hooks do `.claude/settings.json`: eles vêm do plugin. As permissões (`deny` e `ask`) e o `skillOverrides` ficam.
4. Fixe o marketplace e o plugin: no `.claude/settings.json`, acrescente o `extraKnownMarketplaces.ela-harness` (fonte `github`, repositório `Ela-Decora/ElaHarness`, `ref` `v0.2.0`) e o `enabledPlugins` com `ela-harness@ela-harness`, como em `modelo/planejamento/`, e rode os comandos de instalação do [README](README.md#instalar). Ponha `.claude/harness/nucleo` e `.harness-nucleo/` no `.gitignore`.
5. Puxe o gerado no `CLAUDE.md`: acrescente a linha `@.claude/harness/gerado/planejamento.md`, tire do texto o que o gerado já traz (o mapa do harness, o ciclo, os IDs e os marcadores, o que não fazer no ciclo, os gatilhos e o que preservar ao compactar) e troque os nomes das skills por `/ela-harness:<skill>`. Rode `harness.py gerar`.
6. Ajuste a CI: o workflow de `modelo/planejamento/.github/workflows/harness.yml` baixa o plugin na versão fixada, define a `HARNESS_NUCLEO` e roda o `harness.py invariantes --base`. Saem do workflow do projeto o job que rodava a suíte de `.claude/harness/tests/` (`harness (3.9)` e `harness (3.12)`) e o job `diagramas`, que usava o `npm ci --prefix .claude/harness/ferramentas`, o `validar-mermaid.mjs`, as fixtures de `tests/` e o `ferramentas/bancos.py`, todos apagados no passo 1: pelo §11.1 da spec do porte, o validador Mermaid e o `bancos.py` rodam na CI do plugin, sobre as fixtures dele. No projeto, o Mermaid de cada documento se valida com Node, local, pelo `validar-mermaid.mjs` do plugin (o reference `camada-3.md` traz o comando).

### Histórico

O histórico anterior à `v0.2.0` fica no repositório de origem.

## v0.1.0 — 2026-10-14

Primeira versão como plugin, extraída do projeto em que o harness nasceu (fases 1 a 4c).

- O núcleo (`harness/`), as skills e os agentes passam a morar no plugin `harness`, do marketplace `ela-harness`.
- Os hooks vêm do `hooks/hooks.json` do plugin, pelo `harness/gancho.py`, calados em projeto sem `.claude/perfil.toml`.
- O projeto guarda só o lançador `.claude/harness/harness.py`, que acha o núcleo pela `HARNESS_NUCLEO`, pelo link
  `.claude/harness/nucleo` ou pelo registro de plugins; os comandos `python3 .claude/harness/harness.py ...` seguem os
  mesmos.
- Comando `iniciar` e skill `/harness:iniciar`: criam o projeto a partir do `modelo/`.
- A raiz do projeto, sem `CLAUDE_PROJECT_DIR`, é procurada a partir da pasta atual, não mais do arquivo do núcleo.
- As skills passam a ser `/harness:refinar-documento`, `/harness:gate-fase` e `/harness:assessor`.

Para levar um projeto que tinha o núcleo copiado: apague `.claude/harness/*.py` e `tests/`, `.claude/skills/`,
`.claude/agents/`, `.claude/README.md` e `.claude/docs/`; copie o lançador, o pre-commit, o workflow e as linhas do
`.gitignore` do `modelo/`; tire os hooks do `.claude/settings.json` e acrescente `extraKnownMarketplaces` e
`enabledPlugins` como no modelo; troque os nomes das skills no `CLAUDE.md`.
