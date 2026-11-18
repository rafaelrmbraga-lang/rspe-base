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
        py.FS.writeFile("/motor/" + nome, new Uint8Array(buf));
      }
      py.runPython(`import sys
sys.path.insert(0, "/motor")
import rspe_motor, rspe_painel
rspe_motor.VERSAO = ${JSON.stringify(info.versao)}`);
      const analisar = py.globals.get("rspe_painel").analisar_dossie;
      return { py, info, analisar, carga: Math.round(performance.now() - t0) };
    })().catch((e) => { pronto = null; throw e; });
  }
  return pronto;
}

// texto do dossiê do APTO, exatamente como chegou -> painel calculado aqui (texto JSON)
export async function analisar(texto) {
  const m = await carregar();
  const t = performance.now();
  const painel = m.analisar(String(texto));
  return { ok: true, painel, info: { versao: m.info.versao, base_juridica: m.info.base_juridica, pyodide: m.info.pyodide }, carga: m.carga,
    ms: Math.round(performance.now() - t) };
}
