// Paridade navegador x APTO, lado da extensão: carrega o Pyodide e os arquivos do motor DO PACOTE da extensão
// (extensao_seeu/motor), lê as MESMAS abas de cada caso e compara a assinatura com a do CPython. Uma diferença = falha (o
// build não segue). Uso: node ferramentas/motor_extensao/paridade_pyodide.mjs esperado.json
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const RAIZ = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const MOTOR = join(RAIZ, "extensao_seeu", "motor");
const esperado = JSON.parse(readFileSync(process.argv[2], "utf-8"));
const { loadPyodide } = await import(pathToFileURL(join(MOTOR, "pyodide", "pyodide.mjs")).href);
const t0 = Date.now();
const py = await loadPyodide({ indexURL: join(MOTOR, "pyodide") + "/" });
const t1 = Date.now();
py.FS.mkdirTree("/motor");
const info = JSON.parse(readFileSync(join(MOTOR, "motor.json"), "utf-8"));
for (const a of Object.keys(info.arquivos)) {   // os arquivos do pacote, como a extensão os carrega (com subpastas)
  py.FS.mkdirTree(("/motor/" + a).replace(/\/[^/]*$/, ""));
  py.FS.writeFile("/motor/" + a, readFileSync(join(MOTOR, "py", a)));
}
if (esperado.motor !== info.versao) { console.log(`motor do pacote (${info.versao}) diferente do APTO (${esperado.motor}): rode empacotar.py`); process.exit(1); }
py.runPython(`import sys; sys.path.insert(0, "/motor")
import rspe_motor, rspe_painel
rspe_motor.VERSAO = ${JSON.stringify(info.versao)}`);
const t2 = Date.now();
const analisar = py.globals.get("rspe_painel").analisar_abas;
const ids = Object.keys(esperado.casos);
let difs = 0;
for (const id of ids) {
  const e = esperado.casos[id];
  const p = JSON.parse(analisar(e.entrada));   // a mesma entrada, em texto, que a extensão entrega ao motor
  if (p.assinatura !== e.assinatura || p.chave !== e.chave) {
    difs++;
    if (difs <= 5) console.log("DIFERENTE", id, e.assinatura, p.assinatura, e.chave === p.chave ? "(mesma entrada)" : "(entrada diferente)");
  }
}
// resumo para o assistido: os extras (reportlab, Pillow) como a extensão os carrega, e o MESMO PDF (bytes) que o APTO gerou
let rdif = 0;
const R = Object.entries(esperado.resumos || {});
if (R.length) {
  const { createHash } = await import("node:crypto");
  for (const [nome, sha] of Object.entries(info.extras || {})) {
    const buf = readFileSync(join(MOTOR, "extra", nome));
    if (createHash("sha256").update(buf).digest("hex") !== sha) { console.log("extra fora do motor.json:", nome); process.exit(1); }
    if (nome.startsWith("pillow-")) await py.loadPackage(join(MOTOR, "extra", nome));
    else { py.FS.writeFile("/tmp/" + nome, new Uint8Array(buf)); py.runPython(`import zipfile; zipfile.ZipFile("/tmp/${nome}").extractall("/motor")`); }
  }
  py.runPython("import reportlab.rl_config as _c; _c.invariant = 1");
  const rpy = py.globals.get("rspe_painel");
  for (const [id, e] of R) {
    // a análise do processo primeiro (o resumo parte dela), como na extensão
    const caso = esperado.casos[id.replace(/_\d$/, "")];
    analisar(caso.entrada);
    const d = JSON.parse(rpy.resumo_assistido(JSON.stringify({ processo: e.processo })));
    if (JSON.stringify(d) !== JSON.stringify(e.d)) { rdif++; console.log("RESUMO (texto) DIFERENTE", id); continue; }
    const r = JSON.parse(rpy.resumo_pdf(JSON.stringify({ d: e.d, canhoto: e.canhoto })));
    const sha = createHash("sha256").update(py.FS.readFile(r.caminho)).digest("hex");
    if (sha !== e.sha) { rdif++; console.log("RESUMO (PDF) DIFERENTE", id); }
  }
  console.log(`resumo para o assistido: ${R.length - rdif}/${R.length} PDFs idênticos ao do APTO (com e sem o canhoto)`);
}
const versao = py.runPython("import sys; sys.version.split()[0]");
console.log(`Pyodide ${info.pyodide} (Python ${versao}): ${ids.length - difs}/${ids.length} processos com o mesmo resultado do CPython` +
  ` · carga ${t1 - t0} ms, motor ${t2 - t1} ms, cálculo ${Date.now() - t2} ms (${Math.round((Date.now() - t2) / ids.length)} ms por processo)`);
process.exit(difs || rdif ? 1 : 0);
