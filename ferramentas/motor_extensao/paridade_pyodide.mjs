// Paridade APTO x extensão, lado da extensão: carrega o Pyodide e os arquivos do motor DO PACOTE da extensão
// (extensao_seeu/motor), roda o painel nos casos simulados e compara cada assinatura com a do CPython. Uma diferença que
// seja = falha (o build não segue). Uso: node ferramentas/motor_extensao/paridade_pyodide.mjs esperado.json
import { readFileSync, readdirSync } from "node:fs";
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
for (const a of readdirSync(join(MOTOR, "py"))) py.FS.writeFile("/motor/" + a, readFileSync(join(MOTOR, "py", a)));
const info = JSON.parse(readFileSync(join(MOTOR, "motor.json"), "utf-8"));
py.runPython(`import sys; sys.path.insert(0, "/motor")
import rspe_motor, rspe_painel
rspe_motor.VERSAO = ${JSON.stringify(info.versao)}`);
const t2 = Date.now();
const analisar = py.globals.get("rspe_painel").analisar_dossie;
if (esperado.motor !== info.versao) { console.log(`motor do pacote (${info.versao}) diferente do APTO (${esperado.motor}): rode empacotar.py`); process.exit(1); }
// cada dossiê vai ao Python em TEXTO, exatamente como o APTO o serializou (como a extensão faz com a resposta do APTO)
py.FS.writeFile("/tmp/dossies.json", readFileSync(process.argv[2]));
py.runPython(`import json
_D = json.load(open("/tmp/dossies.json", encoding="utf-8"))["dossies"]
def _texto(i): return json.dumps(_D[i], ensure_ascii=False)`);
const texto = py.globals.get("_texto");
const ids = Object.keys(esperado.dossies);
let difs = 0;
for (const id of ids) {
  const e = esperado.dossies[id].painel;
  const p = JSON.parse(analisar(texto(id)));
  if (e.assinatura !== p.assinatura || e.chave !== p.chave || e.base_digital !== p.base_digital) {
    difs++;
    if (difs <= 5) console.log("DIFERENTE", id, e.assinatura, p.assinatura, e.chave === p.chave ? "(mesma entrada)" : "(entrada diferente)",
      e.base_digital === p.base_digital ? "" : "(base jurídica diferente)");
  }
}
const casos = ids;
const versao = py.runPython("import sys; sys.version.split()[0]");
console.log(`Pyodide ${info.pyodide} (Python ${versao}): ${casos.length - difs}/${casos.length} casos iguais ao CPython` +
  ` · carga ${t1 - t0} ms, motor ${t2 - t1} ms, cálculo ${Date.now() - t2} ms`);
process.exit(difs ? 1 : 0);
