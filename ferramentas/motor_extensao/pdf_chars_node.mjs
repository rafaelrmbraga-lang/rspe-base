// Caracteres de PDFs pelo pdf.js da extensão (extensao_seeu/painel/pdf_chars.mjs), em node, para a paridade da leitura da
// ficha com o pdfplumber do APTO. Uso: node pdf_chars_node.mjs entrada1.pdf saida1.json [entrada2.pdf saida2.json ...]
import { readFileSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const RAIZ = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const EXT = join(RAIZ, "extensao_seeu");
const avisos = console.warn, log = console.log;
console.warn = () => {};                       // o pdf.js avisa que não há canvas em node: irrelevante para o texto
const pdfjs = await import(pathToFileURL(join(EXT, "pdfjs", "pdf.min.mjs")).href);
pdfjs.GlobalWorkerOptions.workerSrc = pathToFileURL(join(EXT, "pdfjs", "pdf.worker.min.mjs")).href;
const { caracteres } = await import(pathToFileURL(join(EXT, "painel", "pdf_chars.mjs")).href);
const args = process.argv.slice(2);
for (let i = 0; i < args.length; i += 2) {
  const pags = await caracteres(pdfjs, new Uint8Array(readFileSync(args[i])));
  writeFileSync(args[i + 1], JSON.stringify(pags));
}
console.warn = avisos;
log("pdf.js: %d PDF(s)", args.length / 2);
