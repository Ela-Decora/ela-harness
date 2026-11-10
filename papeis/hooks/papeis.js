// Troca o modelo e o esforço dos agentes do ciclo do bloco pela tabela do `harness.py papel --todos --json`
// (spec 6d-bloco, §6.3). A tabela vale também sobre o modelo que a chamada passou (§3, item 29); a exceção é o
// agente com `model_sensivel` chamado com esse modelo, que fica com ele. Sem tabela, nada muda e sai um aviso só.
//
// Uso: o Claude Code carrega este mod da pasta `papeis/`; os testes rodam com
// `claude plugin test papeis/`, e a validação, com `claude plugin validate` na mesma pasta.
/**
 * @typedef {{ model: string, effort: NonNullable<import("claude-code").TurnStepInput["effort"]>, model_sensivel?: string }} Papel
 * @typedef {{ tabela: Map<string, Papel>, motivo?: undefined } | { tabela?: undefined, motivo: string }} Leitura
 */

const COMANDO = ["python3", ".claude/harness/harness.py", "papel", "--todos", "--json"];

/** @param {string} motivo */
const aviso = (motivo) =>
  `harness: sem a tabela dos papéis (${motivo}); os subagentes seguem o modelo e o esforço da chamada.`;

/**
 * A primeira linha não vazia do texto, sem os brancos das pontas; `undefined` quando não há.
 * @param {unknown} texto
 */
const primeiraLinha = (texto) =>
  String(texto ?? "")
    .split("\n")
    .map((linha) => linha.trim())
    .find((linha) => linha !== "");

/**
 * O tipo sem o prefixo do plugin: `ela-harness:revisor-task` dá `revisor-task`.
 * @param {unknown} subagentType
 */
const tipoDe = (subagentType) =>
  typeof subagentType === "string" ? subagentType.slice(subagentType.lastIndexOf(":") + 1) : undefined;

/** @param {unknown} valor @returns {valor is string} */
const texto = (valor) => typeof valor === "string";

/**
 * A tabela por agente, ou o motivo de não haver: a saída do comando que falhou, ou `JSON ilegível` quando a saída 0
 * não é uma lista de objetos com `agente`, `model` e `effort` em texto.
 * @param {import("claude-code").ProcessRunResult} saida
 * @returns {Leitura}
 */
function lerTabela({ exitCode, stdout, stderr }) {
  if (exitCode !== 0) {
    return { motivo: primeiraLinha(stdout) ?? primeiraLinha(stderr) ?? `saída ${exitCode}` };
  }
  /** @type {unknown} */
  let lista;
  try {
    lista = JSON.parse(stdout);
  } catch {
    return { motivo: "JSON ilegível" };
  }
  /** @param {any} papel */
  const valida = (papel) =>
    papel !== null && typeof papel === "object" && texto(papel.agente) && texto(papel.model) && texto(papel.effort);
  if (!Array.isArray(lista) || !lista.every(valida)) {
    return { motivo: "JSON ilegível" };
  }
  /** @type {Map<string, Papel>} */
  const tabela = new Map();
  for (const { agente, model, effort, model_sensivel } of lista) {
    tabela.set(agente, texto(model_sensivel) ? { model, effort, model_sensivel } : { model, effort });
  }
  return { tabela };
}

/** @param {import("claude-code").On} on */
export function register(on) {
  /** @type {Map<string, Papel> | null} sem tabela, null */
  let tabela = null;
  /** @type {string | null} o texto do aviso que o próximo agent.spawn mostra */
  let pendente = null;
  /** @type {Map<string, string>} o agentId que o agent.spawn devolveu, para o tipo da tabela */
  const subagentes = new Map();

  on("session.start", async ($, e, next) => {
    const resultado = await next(e);
    /** @type {Leitura} */
    let lida;
    try {
      lida = lerTabela(await $.process.run(COMANDO, { cwd: e.cwd, timeoutMs: 10000 }));
    } catch (erro) {
      lida = { motivo: primeiraLinha(/** @type {any} */ (erro)?.message ?? erro) ?? String(erro) };
    }
    tabela = lida.tabela ?? null;
    pendente = lida.tabela ? null : aviso(lida.motivo);
    return resultado;
  });

  on("agent.spawn", async ($, e, next) => {
    let entrada = e;
    /** @type {string | undefined} */
    let tipo;
    try {
      if (pendente !== null) {
        const mensagem = pendente;
        pendente = null;
        $.ui.toast(mensagem);
      }
      const nome = tipoDe(e.subagentType);
      const papel = nome === undefined ? undefined : tabela?.get(nome);
      if (papel) {
        tipo = nome;
        const fica = papel.model_sensivel !== undefined && e.model === papel.model_sensivel;
        entrada = fica ? e : { ...e, model: papel.model };
      }
    } catch {
      entrada = e;
      tipo = undefined;
    }
    const resultado = await next(entrada);
    if (tipo !== undefined && typeof resultado?.agentId === "string") {
      subagentes.set(resultado.agentId, tipo);
    }
    return resultado;
  });

  on("turn.step", async function* ($, e, next) {
    let entrada = e;
    try {
      const tipo = e.agentId === undefined ? undefined : subagentes.get(e.agentId);
      const papel = tipo === undefined ? undefined : tabela?.get(tipo);
      if (papel) {
        entrada = { ...e, effort: papel.effort };
      }
    } catch {
      entrada = e;
    }
    return yield* next(entrada);
  });
}
