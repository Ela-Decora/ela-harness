// Revisão do bloco em rodadas (spec 6d-bloco, §7.2): a lente 1 acha em dois eixos, padrões e spec e defeitos; a
// lente 2 verifica cada Crítico e Importante, rodando a prova ou lendo o código; e os confirmados em aberto vão ao
// conserto, um por vez, com a re-revisão do intervalo dos consertos na rodada seguinte.
//
// Uso: o /ela-harness:revisar-bloco roda este workflow pelo nome, com os args da última linha do
// `harness.py revisao preparar`: bloco, rodada, base, head, os caminhos absolutos diff, gabarito, spec e plano,
// sensivel, consertos_max, em_aberto, orientacao e papeis (o model e o effort de cada agente). Os achados de em_aberto
// abrem a primeira rodada, com o ID deles e já CONFIRMED, e não entram na fusão. A execução tem até consertos_max
// consertos: o implementador-integracao no primeiro e no segundo, o corretor-tardio do terceiro em diante; a rodada que
// segue o último conserto só acha e verifica. Na calibração (§7.4), os args trazem também a calibracao, uma lista de
// achados prontos, cada um com rotulo, severidade, arquivo, linha, problema, prova e, opcional, eixo (sem ele, spec);
// eles entram na lente 2 depois dos da lente 1, sem fusão, e a execução termina depois da primeira rodada, sem
// conserto. Devolve o resultado do Anexo A.6, que o `harness.py revisao registrar` grava, com a chave sem_conserto (o
// motivo do último conserto) no achado que a lane não resolveu; com a calibracao, também a chave calibracao, com o
// rotulo, o id e o veredito de cada achado plantado. Os prompts dos agentes ficam em inglês.
export const meta = {
  name: "revisao-do-bloco",
  description: "Revisão do bloco em rodadas: lente 1 em dois eixos, lente 2 nos Críticos e Importantes e até 3 consertos, com o resultado para o revisao registrar.",
  phases: [{ title: "Achar" }, { title: "Verificar" }, { title: "Consertar" }],
};

// O plugin entrega os agentes com este prefixo, e o agentType só os acha com ele.
const PREFIXO = "ela-harness:";
const MAXIMO_POR_EIXO = 10;
const DISTANCIA_DA_FUSAO = 3;
const PESO_DA_SEVERIDADE = { critical: 3, important: 2, minor: 1 };
const GRAVES = ["critical", "important"];
const SITUACAO_DO_VEREDITO = { CONFIRMED: "aberto", PLAUSIBLE: "registrado", REFUTED: "descartado" };
const EIXOS_DA_LENTE_1 = {
  padroes: "Axis: standards — judge the diff against the review checklist.",
  spec: "Axis: spec and defects — judge the diff against the spec, the plan and the behavior of the change.",
};
const REGUA = "Severity: critical — data loss, a security hole, or a crash or wrong result on the main path; "
  + "important — behavior that contradicts the spec or the plan, or promised behavior with no test; "
  + "minor — anything else.";
const REGRA_DA_PROVA = "Proof: one shell command that shows the problem in this worktree without writing files, "
  + "or null.";
const ACHADOS = {
  type: "object",
  properties: {
    achados: {
      type: "array",
      maxItems: MAXIMO_POR_EIXO,
      items: {
        type: "object",
        properties: {
          severidade: { type: "string", enum: ["critical", "important", "minor"] },
          arquivo: { type: "string", minLength: 1 },
          linha: { type: "integer", minimum: 1 },
          problema: { type: "string", minLength: 1 },
          prova: { type: ["string", "null"] },
        },
        required: ["severidade", "arquivo", "linha", "problema", "prova"],
      },
    },
  },
  required: ["achados"],
};
const COM_PROVA = {
  type: "object",
  properties: {
    veredito: { type: "string", enum: ["CONFIRMED", "REFUTED"] },
    saida: { type: "string" },
  },
  required: ["veredito", "saida"],
};
const SEM_PROVA = {
  type: "object",
  properties: {
    veredito: { type: "string", enum: ["CONFIRMED", "PLAUSIBLE", "REFUTED"] },
    evidencia: { type: "string" },
  },
  required: ["veredito", "evidencia"],
};
const CONSERTO = {
  type: "object",
  properties: {
    situacao: { type: "string", enum: ["corrigido", "recusado", "sem_conserto"] },
    sha: { type: ["string", "null"] },
    motivo: { type: ["string", "null"] },
  },
  required: ["situacao", "sha", "motivo"],
};
const RE_REVISAO = {
  type: "object",
  properties: {
    consertos: {
      type: "array",
      items: {
        type: "object",
        properties: { id: { type: "string" }, resolvido: { type: "boolean" } },
        required: ["id", "resolvido"],
      },
    },
    recusas: {
      type: "array",
      items: {
        type: "object",
        properties: { id: { type: "string" }, aceita: { type: "boolean" } },
        required: ["id", "aceita"],
      },
    },
    achados: ACHADOS.properties.achados,
  },
  required: ["consertos", "recusas", "achados"],
};
const FORMA_DO_SHA = /^[0-9a-f]{7,40}$/;

// O model e o effort do agente, dos args.papeis.
function papel(agente) {
  const escolhido = (args.papeis ?? {})[agente];
  if (!escolhido) {
    throw new Error(`args.papeis sem ${agente}`);
  }
  return { model: escolhido.model, effort: escolhido.effort };
}

// Um agent() com o papel dos args; o agente que não devolve nada falha o workflow.
async function chamar(label, fase, agente, prompt, esquema) {
  const resposta = await agent(prompt, {
    label, phase: fase, agentType: PREFIXO + agente, schema: esquema, ...papel(agente),
  });
  if (resposta === null || resposta === undefined) {
    throw new Error(`${label}: o agente não devolveu resultado`);
  }
  return resposta;
}

// Os pedidos ({ label, fase, agente, prompt, esquema }) pelo parallel, que troca a falha por null; o primeiro null
// falha o workflow com a label dele.
async function emParalelo(pedidos) {
  const respostas = await parallel(pedidos.map((pedido) => () => chamar(pedido.label, pedido.fase, pedido.agente,
    pedido.prompt, pedido.esquema)));
  respostas.forEach((resposta, indice) => {
    if (resposta === null) {
      throw new Error(`${pedidos[indice].label}: o agente não devolveu resultado`);
    }
  });
  return respostas;
}

function provaOuNull(prova) {
  return typeof prova === "string" && prova.trim() ? prova : null;
}

// Os achados de um eixo, com a prova vazia como null, sem os que não têm arquivo:linha e até 10, com um log para o
// que fica de fora.
function normalizar(eixo, label, lista) {
  const validos = [];
  for (const item of lista) {
    const arquivo = typeof item.arquivo === "string" ? item.arquivo : "";
    if (!arquivo.trim() || !Number.isInteger(item.linha) || item.linha < 1) {
      log(`${label}: achado sem arquivo:linha ficou de fora: ${item.problema}`);
      continue;
    }
    validos.push({
      eixo,
      severidade: item.severidade,
      arquivo,
      linha: item.linha,
      problema: item.problema,
      prova: provaOuNull(item.prova),
      absorvidos: [],
    });
  }
  const alem = validos.length - MAXIMO_POR_EIXO;
  if (alem === 1) {
    log(`${label}: 1 achado além dos ${MAXIMO_POR_EIXO} ficou de fora`);
  } else if (alem > 1) {
    log(`${label}: ${alem} achados além dos ${MAXIMO_POR_EIXO} ficaram de fora`);
  }
  return validos.slice(0, MAXIMO_POR_EIXO);
}

// A fusão sem perda (spec 6d-repositorio, §10): só um achado de padrões e um de spec e defeitos se juntam, no mesmo
// arquivo e a até 3 linhas, um com um. Os pares candidatos se ordenam por (distância, posição em padrões, posição em
// spec) e se aceitam nessa ordem, pulando o que já tem um membro pareado. Do par fica o de severidade maior, inteiro,
// e no empate o de spec; o outro vai para os absorvidos dele, com eixo, linha, problema e prova. A saída traz os de
// padrões e depois os de spec, como vieram, sem os absorvidos. Os herdados não passam por aqui: abrem a rodada.
function fundir(padroes, spec) {
  const candidatos = [];
  padroes.forEach((deles, i) => spec.forEach((dele, j) => {
    const distancia = Math.abs(deles.linha - dele.linha);
    if (deles.arquivo === dele.arquivo && distancia <= DISTANCIA_DA_FUSAO) {
      candidatos.push({ distancia, i, j });
    }
  }));
  candidatos.sort((x, y) => x.distancia - y.distancia || x.i - y.i || x.j - y.j);
  const pareados = { padroes: new Map(), spec: new Map() };
  for (const { i, j } of candidatos) {
    if (!pareados.padroes.has(i) && !pareados.spec.has(j)) {
      pareados.padroes.set(i, j);
      pareados.spec.set(j, i);
    }
  }
  const resumo = ({ eixo, linha, problema, prova }) => ({ eixo, linha, problema, prova });
  const ficam = [];
  padroes.forEach((achado, i) => {
    if (!pareados.padroes.has(i)) {
      ficam.push({ ...achado, absorvidos: [] });
    } else if (PESO_DA_SEVERIDADE[achado.severidade] > PESO_DA_SEVERIDADE[spec[pareados.padroes.get(i)].severidade]) {
      ficam.push({ ...achado, absorvidos: [resumo(spec[pareados.padroes.get(i)])] });
    }
  });
  spec.forEach((achado, j) => {
    if (!pareados.spec.has(j)) {
      ficam.push({ ...achado, absorvidos: [] });
    } else if (PESO_DA_SEVERIDADE[achado.severidade] >= PESO_DA_SEVERIDADE[padroes[pareados.spec.get(j)].severidade]) {
      ficam.push({ ...achado, absorvidos: [resumo(padroes[pareados.spec.get(j)])] });
    }
  });
  return ficam;
}

// Os IDs R<rodada>-<n>, com n de 1 em diante, na ordem da lista.
function numerar(rodada, lista) {
  return lista.map((achado, indice) => ({ id: `R${rodada}-${indice + 1}`, ...achado }));
}

function promptDaLente1(eixo) {
  return [
    `Review the diff of block ${args.bloco}.`,
    EIXOS_DA_LENTE_1[eixo],
    "",
    `Diff: ${args.diff}`,
    `Review checklist: ${args.gabarito}`,
    `Spec: ${args.spec}`,
    `Plan: ${args.plano}`,
    "",
    "Return at most 10 findings. Give each file path relative to the worktree root and the line in the file as it is "
      + "now.",
    REGUA,
    REGRA_DA_PROVA,
  ].join("\n");
}

function promptComProva(achado) {
  return [
    `Verify one finding of the review of block ${args.bloco} by running its proof.`,
    "",
    `Finding: ${achado.problema}`,
    `Severity: ${achado.severidade}`,
    `Location: ${achado.arquivo}:${achado.linha}`,
    `Proof: ${achado.prova}`,
    "",
    "Run the proof command exactly as given, in this worktree, without writing any file. Answer CONFIRMED if the "
      + "output shows the problem and REFUTED if it does not, and return the output in saida.",
  ].join("\n");
}

function promptSemProva(achado) {
  return [
    `Verify one finding of the review of block ${args.bloco} by reading the code.`,
    "",
    `Finding: ${achado.problema}`,
    `Severity: ${achado.severidade}`,
    `File: ${achado.arquivo}`,
    `Line: ${achado.linha}`,
    `Spec: ${args.spec}`,
    "",
    "Read the code at that file and line, and the spec where it bears on the finding. Answer CONFIRMED if the code has "
      + "the problem, PLAUSIBLE if it may have it but the code does not settle it, and REFUTED if it does not have it. "
      + "Answer REFUTED also when that file:line does not exist. Return the evidence in evidencia.",
  ].join("\n");
}

// A lente 2: cada critical ou important vai a um verificador-achado, todos pelo parallel; o minor fica registrado,
// sem despacho. Devolve os achados com o veredito, o método e a situação.
async function verificar(achados) {
  const graves = achados.filter((achado) => GRAVES.includes(achado.severidade));
  const respostas = await emParalelo(graves.map((achado) => ({
    label: `verificar:${achado.id}`,
    fase: "Verificar",
    agente: "verificador-achado",
    prompt: achado.prova === null ? promptSemProva(achado) : promptComProva(achado),
    esquema: achado.prova === null ? SEM_PROVA : COM_PROVA,
  })));
  const vereditos = new Map(graves.map((achado, indice) => [achado.id, respostas[indice].veredito]));
  return achados.map((achado) => {
    if (!vereditos.has(achado.id)) {
      return { ...achado, veredito: null, metodo: null, situacao: "registrado" };
    }
    const veredito = vereditos.get(achado.id);
    return {
      ...achado,
      veredito,
      metodo: achado.prova === null ? "leitura" : "prova",
      situacao: SITUACAO_DO_VEREDITO[veredito],
    };
  });
}

// Os critical e important CONFIRMED em aberto de todas as rodadas: os critical antes, e cada grupo na ordem das
// rodadas e, dentro de cada uma, na dos IDs.
function emAberto(rodadas) {
  const abertos = rodadas.flatMap((rodada) => rodada.achados).filter((achado) => GRAVES.includes(achado.severidade)
    && achado.veredito === "CONFIRMED" && achado.situacao === "aberto");
  return GRAVES.flatMap((severidade) => abertos.filter((achado) => achado.severidade === severidade));
}

function promptDoConserto(achado) {
  return [
    `Fix finding ${achado.id} of the review of block ${args.bloco}.`,
    "",
    `Severity: ${achado.severidade}`,
    `Location: ${achado.arquivo}:${achado.linha}`,
    `Problem: ${achado.problema}`,
    `Proof: ${achado.prova ?? "none"}`,
    "",
    `Spec: ${args.spec}`,
    `Plan: ${args.plano}`,
    `Review checklist: ${args.gabarito}`,
    ...(args.orientacao ? [`Owner guidance: ${args.orientacao}`] : []),
    "",
    "Use superpowers:receiving-code-review and check the finding against the code before changing anything. If it "
      + "holds, fix it, with a test where the change has a public seam; run the proof, when there is one, and the "
      + `tests; and make one commit "fix(${args.bloco}): <summary>" with the line "Finding: ${achado.id}" in the `
      + "body.",
    "Return situacao corrigido with the full sha of that commit in sha. If the finding does not hold, change nothing "
      + "and return situacao recusado with the reason in motivo.",
    "If the finding holds but the fix needs a change this worktree cannot make (the passagem copy, the approved "
      + "spec, a generated file, or a path the guard denies) or a decision of the owner, change nothing and return "
      + "situacao sem_conserto with the reason in motivo.",
    "If the finding points at a conflict between the passagem (a contract, an ADR or another decision of the "
      + "passagem) and the ficha or the spec, or if checking the finding against the code, the ficha or the "
      + "passagem shows that conflict even when the finding does not name it (for example, a finding that only "
      + "says a new test is out of scope or contradicts the spec, about a test that reads a contract from the "
      + "passagem copy), it is always a decision of the owner: change nothing, not even the part that this lane "
      + "could resolve (deleting the test, changing the assertion or the code to one side), and return "
      + "situacao sem_conserto with the reason in motivo, naming the item of the passagem (for example the "
      + "contract ID) and the side of the ficha or the spec.",
  ].join("\n");
}

function promptDaReRevisao(antes, depois, consertados, recusados) {
  const consertos = consertados.map(({ achado, sha }) => `- ${achado.id}: ${achado.problema} `
    + `(${achado.arquivo}:${achado.linha}), commit ${sha}`);
  const recusas = recusados.map(({ achado, motivo }) => `- ${achado.id}: ${achado.problema} `
    + `(${achado.arquivo}:${achado.linha}); reason: ${motivo}`);
  return [
    `Re-review the fixes of the review of block ${args.bloco}.`,
    "",
    `Interval: ${antes}..${depois}`,
    "Fixes:",
    ...(consertos.length > 0 ? consertos : ["- none"]),
    "Refusals:",
    ...(recusas.length > 0 ? recusas : ["- none"]),
    "",
    "Look only at the changes in the interval; do not review the rest of the block again.",
    "Judge each fix, with resolvido true if its commit resolves the finding, and each refusal, with aceita true only if "
      + "the reason shows that the finding does not hold. Return one judgment for every ID listed above.",
    "In achados, return only the new problems that the fixes introduced, at most 10. Give each file path relative to "
      + "the worktree root and the line in the file as it is now.",
    REGUA,
    REGRA_DA_PROVA,
  ].join("\n");
}

// Um conserto, o de número `numero` na execução: cada achado aberto vai a um agente, um por vez, sem parallel, o
// implementador-integracao no primeiro e no segundo conserto e o corretor-tardio do terceiro em diante. O corrigido
// com sha na forma fica `corrigido <sha7>`; o recusado com motivo, `recusado: <motivo>`; o sem_conserto com motivo
// deixa o achado aberto, com log e com a chave sem_conserto no resultado, e não vai ao re-revisor; sem sha válido ou
// sem motivo, o achado segue aberto, com log. A chave sem_conserto guarda o motivo do último conserto do achado:
// um conserto seguinte que não seja sem_conserto com motivo a tira. Devolve os consertados, com o sha inteiro, na
// ordem dos commits, e os recusados.
async function consertar(abertos, numero) {
  const agente = numero <= 2 ? "implementador-integracao" : "corretor-tardio";
  const consertados = [];
  const recusados = [];
  for (const achado of abertos) {
    delete achado.sem_conserto;
    const resposta = await chamar(`consertar:${achado.id}`, "Consertar", agente, promptDoConserto(achado), CONSERTO);
    if (resposta.situacao === "corrigido") {
      if (typeof resposta.sha === "string" && FORMA_DO_SHA.test(resposta.sha)) {
        achado.situacao = `corrigido ${resposta.sha.slice(0, 7)}`;
        consertados.push({ achado, sha: resposta.sha });
      } else {
        log(`${achado.id}: conserto sem sha válido; o achado segue aberto`);
      }
      continue;
    }
    const motivo = typeof resposta.motivo === "string" ? resposta.motivo.trim().split(/\s+/).join(" ") : "";
    if (motivo && resposta.situacao === "sem_conserto") {
      achado.sem_conserto = motivo;
      log(`${achado.id}: sem conserto na lane: ${motivo}; o achado segue aberto`);
    } else if (motivo) {
      achado.situacao = `recusado: ${motivo}`;
      recusados.push({ achado, motivo });
    } else {
      log(`${achado.id}: recusa sem motivo; o achado segue aberto`);
    }
  }
  return { consertados, recusados };
}

// O achado cujo julgamento falta, ou não traz true na chave, volta a aberto; o julgamento que falta deixa um log.
function julgar(label, itens, julgamentos, chave) {
  for (const { achado } of itens) {
    const julgamento = julgamentos.find((item) => item.id === achado.id);
    if (!julgamento) {
      log(`${label}: sem julgamento de ${achado.id}; o achado volta a aberto`);
    }
    if (julgamento?.[chave] !== true) {
      achado.situacao = "aberto";
    }
  }
}

// A rodada que segue um conserto, sobre o intervalo dele: o re-revisor julga cada conserto e cada recusa, e os
// achados novos dele entram com o eixo conserto, sem fusão, e passam pela lente 2. Sem conserto nem recusa, a rodada
// sai sem despacho e sem achados.
async function reRevisar(rodada, antes, depois, consertados, recusados) {
  const intervalo = `${antes.slice(0, 7)}..${depois.slice(0, 7)}`;
  if (consertados.length === 0 && recusados.length === 0) {
    return { rodada, intervalo, achados: [] };
  }
  const label = `re-revisar:${rodada}`;
  phase("Achar");
  const resposta = await chamar(label, "Achar", "re-revisor", promptDaReRevisao(antes, depois, consertados, recusados),
    RE_REVISAO);
  julgar(label, consertados, resposta.consertos ?? [], "resolvido");
  julgar(label, recusados, resposta.recusas ?? [], "aceita");
  const novos = numerar(rodada, normalizar("conserto", label, resposta.achados ?? []));
  phase("Verificar");
  return { rodada, intervalo, achados: await verificar(novos) };
}

phase("Achar");
const eixos = Object.keys(EIXOS_DA_LENTE_1);
const lente1 = await emParalelo(eixos.map((eixo) => ({
  label: `lente1:${eixo}`,
  fase: "Achar",
  agente: "revisor-bloco",
  prompt: promptDaLente1(eixo),
  esquema: ACHADOS,
})));
const [dePadroes, deSpec] = eixos.map((eixo, indice) => normalizar(eixo, `lente1:${eixo}`, lente1[indice].achados));
const calibracao = Array.isArray(args.calibracao) ? args.calibracao : null;
const plantados = [];
for (const item of calibracao ?? []) {
  const [achado] = normalizar(item.eixo ?? "spec", "calibracao", [item]);
  if (achado) {
    plantados.push({ rotulo: item.rotulo, achado });
  }
}
const herdados = (args.em_aberto ?? []).map((item) => ({
  id: item.id,
  eixo: item.eixo,
  severidade: item.severidade,
  arquivo: item.arquivo,
  linha: item.linha,
  problema: item.problema,
  prova: provaOuNull(item.prova),
  absorvidos: [],
  veredito: "CONFIRMED",
  metodo: null,
  situacao: "aberto",
}));
const novos = numerar(args.rodada, [
  ...fundir(dePadroes, deSpec),
  ...plantados.map((plantado) => plantado.achado),
]);

phase("Verificar");
const verificados = await verificar(novos);
const rodadas = [{
  rodada: args.rodada,
  intervalo: `${args.base.slice(0, 7)}..${args.head.slice(0, 7)}`,
  achados: [...herdados, ...verificados],
}];
// O laço (spec §7.2, item 4): fechada a rodada, com Crítico ou Importante confirmado em aberto e conserto disponível,
// vem um conserto e a rodada que o re-revisa; o sha do último commit de conserto passa a ser o head.
let head = args.head;
for (let numero = 1; !calibracao && numero <= args.consertos_max; numero += 1) {
  const abertos = emAberto(rodadas);
  if (abertos.length === 0) {
    break;
  }
  phase("Consertar");
  const { consertados, recusados } = await consertar(abertos, numero);
  const antes = head;
  head = consertados.length > 0 ? consertados[consertados.length - 1].sha : head;
  rodadas.push(await reRevisar(rodadas[rodadas.length - 1].rodada + 1, antes, head, consertados, recusados));
}
const resultado = {
  bloco: args.bloco,
  sensivel: args.sensivel,
  orientacao: args.orientacao ?? null,
  rodadas,
};
if (calibracao) {
  const daCalibracao = verificados.slice(verificados.length - plantados.length);
  resultado.calibracao = plantados.map((plantado, indice) => ({
    rotulo: plantado.rotulo,
    id: daCalibracao[indice].id,
    veredito: daCalibracao[indice].veredito,
  }));
}
return resultado;
