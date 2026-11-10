# DER Físico — {{PROJETO}}

> CAMADA AVANÇADA · fonte do DER físico, uma tabela por subseção (seu Avançado item 1).
> O DDL em SQL/ e o diagrama abaixo saem daqui por `harness.py der gerar`; não edite os gerados.

---

## Convenções
<!-- O que vale para todas as tabelas: chave primária, datas de criação e de mudança,
     soft delete, política padrão de FK, nomes em snake_case sem acento. -->

-

## Tabelas
<!-- Uma subseção por tabela. "Entidade:" traz o nome da entidade no erDiagram do modelo
     conceitual e o link do documento dela; tabela de ligação usa "Ligação: <rótulo> (<A> e <B>)".
     Tipos: id, inteiro, inteiro_grande, decimal(p,e), texto(n), texto_longo, booleano, data, hora,
     data_hora, json, uuid, enum(a, b). Chave: PK, UK, UK:<grupo>, FK <tabela>.<coluna> (restringir,
     cascata ou anular). Origem: trecho de "Atributos principais" da entidade, "relação: <rótulo>"
     ou "técnica". -->

### Tabela <!-- nome -->

Entidade: <!-- NOME_NO_ER ([entidade-<nome>.md](../../../2-intermediario/Entidade/entidade-<nome>.md)) -->

| Coluna | Tipo | Nulo | Chave | Padrão | Origem |
|---|---|---|---|---|---|
| <!-- coluna --> | | | | | |

Índices:
- <!-- (coluna, coluna) -->

Restrições:
- <!-- coluna >= 0, ou coluna entre 1 e 30 -->

## Não persistido
<!-- Atributo da camada 2 que não vira coluna: "- <NOME_NO_ER>: <trecho> — <motivo>". -->

-

## Diagrama
<!-- Gerado por harness.py der gerar a partir das tabelas. -->

```mermaid
erDiagram
    %% gerado por harness.py der gerar; não edite
```

## Workbench
<!-- Depois de importar SQL/schema.mysql.sql no MySQL Workbench: os prints, o SQL exportado
     por ele e a data. MySQLWB/manifesto.txt amarra os prints à versão do DDL. -->

- Prints:
- SQL exportado:
