// APTO - motor do painel no SEEU: o MESMO código Python do APTO (rspe_painel, rspe_motor e as regras), rodando no Pyodide,
// dentro da extensão (nada sai do computador). Carregado uma vez por sessão do navegador (documento offscreen no Chrome/Edge,
// página de fundo no Firefox). Antes de usar, confere o sha256 de cada arquivo com o motor.json gerado no build
// (ferramentas/motor_extensao/empacotar.py): arquivo alterado = motor recusado.
let pronto = null;

const url = (p) => chrome.runtime.getURL(p);

async function sha256(buf) {
  const h = await crypto.subtle.digest("SHA-256", buf);
  return [...new Uint8Array(h)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function carregar() {
  if (!pronto) {
    pronto = (async () => {
      const t0 = performance.now();
      const info = await (await fetch(url("motor/motor.json"))).json();
      const { loadPyodide } = await import(url("motor/pyodide/pyodide.mjs"));
      const py = await loadPyodide({ indexURL: url("motor/pyodide/") });
      py.FS.mkdirTree("/motor");
      for (const [nome, esperado] of Object.entries(info.arquivos)) {
        const buf = await (await fetch(url("motor/py/" + nome))).arrayBuffer();
        if ((await sha256(buf)) !== esperado) throw new Error("motor recusado: " + nome + " não confere com o motor.json");
        const dir = ("/motor/" + nome).replace(/\/[^/]*$/, "");
        py.FS.mkdirTree(dir);
        py.FS.writeFile("/motor/" + nome, new Uint8Array(buf));
      }
      py.runPython(`import sys
sys.path.insert(0, "/motor")
import rspe_motor, rspe_painel
rspe_motor.VERSAO = ${JSON.stringify(info.versao)}`);
      const rp = py.globals.get("rspe_painel");
      return { py, info, analisar: rp.analisar_abas, lerFicha: rp.ler_ficha, carga: Math.round(performance.now() - t0) };
    })().catch((e) => { pronto = null; throw e; });
  }
  return pronto;
}

// {"abas": {nome: HTML}, "hoje": "dd/mm/aaaa"} em texto -> painel calculado aqui (texto JSON)
export async function analisar(texto) {
  const m = await carregar();
  const t = performance.now();
  const painel = m.analisar(String(texto));
  return { ok: true, painel, info: { versao: m.info.versao, base_juridica: m.info.base_juridica, pyodide: m.info.pyodide }, carga: m.carga,
    ms: Math.round(performance.now() - t) };
}

// ficha disciplinar do SIAPEN (PDF): os caracteres pelo pdf.js (posição e fonte, como o pdfplumber) e o MESMO leitor do APTO
let pdfjs = null;
export async function lerFicha(bytes, arquivo) {
  const m = await carregar();
  if (!pdfjs) {
    pdfjs = await import(url("pdfjs/pdf.min.mjs"));
    pdfjs.GlobalWorkerOptions.workerSrc = url("pdfjs/pdf.worker.min.mjs");
  }
  const { caracteres } = await import(url("painel/pdf_chars.mjs"));
  let paginas;
  try { paginas = await caracteres(pdfjs, bytes); } catch (e) { return { ok: false, erro: "o PDF não abriu (" + String((e && e.message) || e) + ")" }; }
  const r = JSON.parse(m.lerFicha(JSON.stringify({ paginas, arquivo: arquivo || "ficha.pdf" })));
  return r.erro ? { ok: false, erro: r.erro } : { ok: true, ficha: r.ficha, resumo: r.resumo };
}

// resumo para o assistido: o texto proposto (rspe_resumo, a partir da última análise do processo) e o PDF pelo MESMO gerador do
// APTO (rspe_relatorio). O reportlab (Python puro, versão do APTO) e o Pillow (do Pyodide) só carregam quando o resumo é pedido.
let extras = null;
function prepararExtras(m) {
  if (!extras) {
    extras = (async () => {
      for (const [nome, esperado] of Object.entries(m.info.extras || {})) {
        const buf = await (await fetch(url("motor/extra/" + nome))).arrayBuffer();
        if ((await sha256(buf)) !== esperado) throw new Error("resumo recusado: " + nome + " não confere com o motor.json");
        if (nome.startsWith("pillow-")) await m.py.loadPackage(url("motor/extra/" + nome));
        else {   // wheel em Python puro: extraído com o zipfile do próprio Python
          m.py.FS.writeFile("/tmp/" + nome, new Uint8Array(buf));
          m.py.runPython(`import zipfile; zipfile.ZipFile("/tmp/${nome}").extractall("/motor")`);
        }
      }
    })().catch((e) => { extras = null; throw e; });
  }
  return extras;
}
export async function resumo(processo) {
  const m = await carregar();
  const r = JSON.parse(m.py.globals.get("rspe_painel").resumo_assistido(JSON.stringify({ processo })));
  return r.erro ? { ok: false, erro: r.erro } : { ok: true, d: r };
}
export async function resumoPdf(d, canhoto) {
  const m = await carregar();
  await prepararExtras(m);
  const r = JSON.parse(m.py.globals.get("rspe_painel").resumo_pdf(JSON.stringify({ d, canhoto: !!canhoto })));
  const bytes = m.py.FS.readFile(r.caminho);
  let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return { ok: true, b64: btoa(bin), canhoto: r.canhoto, verso: r.verso };
}
