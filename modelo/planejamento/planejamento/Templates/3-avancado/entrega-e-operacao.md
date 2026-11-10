# Entrega e operação — {{PROJETO}}

> CAMADA AVANÇADA · depois dos contratos externos e antes das fichas · o que se prova, o que se arrisca e como se opera e se volta.
> Testes concretos, runbooks finais e painéis nascem no desenvolvimento, por ficha.

---

## Estratégia de testes

### Níveis
<!-- Um nível por linha: o que ele prova e onde roda. -->

| Nível | O que prova | Ambiente |
|---|---|---|
|  |  |  |

### Prova dos requisitos não funcionais
<!-- Todo RNF da camada 1 numa linha ao menos, com o nível e o ambiente que o provam. A linha começa pelo nível: a que começa por ID o define. -->

| Nível | RNF | Ambiente | Como se prova |
|---|---|---|---|
|  |  |  |  |

### Prova dos contratos externos
<!-- Todo CTR do contratos-externos.md numa linha ao menos, com o nível e o ambiente que o provam. A linha começa pelo nível. -->

| Nível | Contrato | Ambiente | Como se prova |
|---|---|---|---|
|  |  |  |  |

### Testes de descoberta
<!-- Pendências que só um teste antes da virada responde. -->

| Pendência | O que descobrir | Antes de |
|---|---|---|
|  |  |  |

## Riscos
<!-- Um bloco por risco. A mitigação que é trabalho vira ficha, e a ficha cita o risco na Fonte. -->

### RSC-NN: <!-- nome -->
- **Descrição:**
- **Probabilidade:** <!-- baixa, média ou alta -->
- **Impacto:** <!-- baixo, médio ou alto -->
- **Resposta:** <!-- evitar, mitigar ou aceitar -->
- **Gatilho:** <!-- o que mostra que o risco está acontecendo -->
- **Executa:** <!-- "ficha", PEND-NN ou RA-NN; no aceitar, "aceito por <quem> em <AAAA-MM-DD>" -->

## Ameaças
<!-- STRIDE leve por fronteira de confiança entre os contêineres do C4. -->

### AME-NN: <!-- nome -->
- **Fronteira:** <!-- entre quais contêineres do C4 -->
- **Categoria:** <!-- uma letra do STRIDE: S, T, R, I, D ou E -->
- **Mitigação:**
- **Cobre:** <!-- o RNF-SEC que a cobre -->

### Dados pessoais
<!-- Um dado por linha, amarrado aos RNF-SEC e às colunas do DER físico. -->

| Dado | Onde fica | Prazo | Motivo | RNF |
|---|---|---|---|---|
|  |  |  |  |  |

## Objetivos de serviço
<!-- Um bloco por objetivo, medido pela telemetria do ADR de avisos. -->

### SLO-NN: <!-- nome -->
- **SLI:** <!-- o que se mede e de onde -->
- **Meta:**
- **Janela:**
- **Origem:** <!-- o RNF de que ele sai -->
- **Orçamento de erro:**
- **Alerta:** <!-- limiar, quem recebe da equipe que mantém e o canal -->

## Recuperação
- **RPO:** <!-- quanto dado se pode perder -->
- **RTO:** <!-- em quanto tempo o serviço volta -->
- **Teste de restauração:** <!-- como e quando, com o nível da estratégia de testes -->

## Virada e volta

### Gatilhos de volta
<!-- Uma condição medida por item, que começa pelo texto e cita o SLO-NN depois. -->

-

### Passos de volta
<!-- Da desligada do {{PROJETO}} à situação anterior de volta em operação. -->

1.

### Quem decide
-

### Janela de volta
<!-- Até quando a volta é possível. -->

-
