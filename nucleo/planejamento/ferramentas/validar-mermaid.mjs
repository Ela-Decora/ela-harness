// Valida a sintaxe dos blocos Mermaid dos documentos com o mermaid.parse(), sobre o DOM do jsdom (spec 5a, §7.4).
//
// Uso: node validar-mermaid.mjs <arquivo ou pasta>...
// As pastas são percorridas atrás de .md, sem o node_modules/. Os blocos são os de cerca ```mermaid, contados como no
// checar: toda linha que começa por três crases abre ou fecha um bloco. No primeiro bloco inválido de cada arquivo,
// imprime <arquivo>:L<linha da cerca>: <primeira linha do erro>. Sem erro, imprime OK: <n> blocos em <m> arquivos.
// Sai com 0 ou 1. O harness.py não chama este script; a CI o roda sempre, e a skill quando o Node existe.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { JSDOM } from "jsdom";

const { window } = new JSDOM("<!doctype html><html><body></body></html>", { pretendToBeVisual: true });
globalThis.window = window;
globalThis.document = window.document;
const { default: mermaid } = await import("mermaid");
mermaid.initialize({ startOnLoad: false });

function arquivos(caminho, passado) {
  if (statSync(caminho).isDirectory()) {
    return readdirSync(caminho)
      .filter((nome) => nome !== "node_modules")
      .sort()
      .flatMap((nome) => arquivos(join(caminho, nome), false));
  }
  return passado || caminho.endsWith(".md") ? [caminho] : [];
}

function blocos(texto) {
  const achados = [];
  let atual = null;
  texto.split("\n").forEach((bruta, indice) => {
    const linha = bruta.replace(/\r$/, "");
    if (linha.trimStart().startsWith("```")) {
      if (atual === null) {
        atual = { cerca: indice + 1, mermaid: linha.trim() === "```mermaid", linhas: [] };
        achados.push(atual);
      } else {
        atual = null;
      }
    } else if (atual !== null) {
      atual.linhas.push(linha);
    }
  });
  return achados.filter((bloco) => bloco.mermaid);
}

const caminhos = process.argv.slice(2);
if (caminhos.length === 0) {
  console.error("uso: node validar-mermaid.mjs <arquivo ou pasta>...");
  process.exit(1);
}
let erros = 0;
let total = 0;
const lidos = caminhos.flatMap((caminho) => arquivos(caminho, true));
for (const arquivo of lidos) {
  for (const bloco of blocos(readFileSync(arquivo, "utf8"))) {
    total += 1;
    try {
      await mermaid.parse(bloco.linhas.join("\n"));
    } catch (erro) {
      const mensagem = String(erro && erro.message ? erro.message : erro).split("\n")[0];
      console.log(`${arquivo}:L${bloco.cerca}: ${mensagem}`);
      erros += 1;
      break;
    }
  }
}
if (erros === 0) {
  console.log(`OK: ${total} blocos em ${lidos.length} arquivos`);
}
process.exit(erros === 0 ? 0 : 1);
