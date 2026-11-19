// APTO - prévia de documento do SEEU (moldura da extensão dentro da página): recebe da página os bytes do arquivo que o próprio link
// baixaria (um GET com a sessão de quem está logado) e mostra: PDF desenhado pelo pdf.js da extensão (página a página, até 12),
// HTML num quadro isolado (sem scripts), imagem como imagem. Nada é gravado nem enviado.
const SEEU = "https://seeu.pje.jus.br";
const MAX_PAG = location.hash.includes("doc=") ? 300 : 12;
const $p = document.getElementById("paginas");
let pdfjs = null, atual = 0, ultimo = null, zoom = 1;

function msg(t, d) { $p.innerHTML = `<div class="msg"><b>${t}</b>${d || ""}</div>`; }
const ehPdf = (b) => b.length > 4 && b[0] === 0x25 && b[1] === 0x50 && b[2] === 0x44 && b[3] === 0x46;

async function pdf(bytes, vez) {
  if (!pdfjs) {
    pdfjs = await import(chrome.runtime.getURL("pdfjs/pdf.min.mjs"));
    pdfjs.GlobalWorkerOptions.workerSrc = chrome.runtime.getURL("pdfjs/pdf.worker.min.mjs");
  }
  const doc = await pdfjs.getDocument({ data: bytes, isEvalSupported: false }).promise;
  if (vez !== atual) return;
  $p.innerHTML = "";
  const larg = Math.round(Math.min(document.documentElement.clientWidth - 24, 1400) * zoom);
  try { parent.postMessage({ apto: "previaPaginas", n: doc.numPages }, SEEU); } catch (e) { /* janela: sem moldura */ }
  const n = Math.min(doc.numPages, MAX_PAG);
  for (let i = 1; i <= n; i++) {
    const pg = await doc.getPage(i);
    if (vez !== atual) return;
    const v0 = pg.getViewport({ scale: 1 });
    const esc = larg / v0.width, dpr = Math.min(3, (window.devicePixelRatio || 1) * 1.5);   // nítido também com o zoom
    const vp = pg.getViewport({ scale: esc * dpr });
    const c = document.createElement("canvas");
    c.width = Math.floor(vp.width); c.height = Math.floor(vp.height);
    c.style.width = Math.floor(vp.width / dpr) + "px";
    c.setAttribute("role", "img");
    c.setAttribute("aria-label", "Página " + i + " de " + doc.numPages);
    $p.appendChild(c);
    await pg.render({ canvasContext: c.getContext("2d"), viewport: vp }).promise;
  }
  if (doc.numPages > n) $p.insertAdjacentHTML("beforeend", `<div class="mais">Mostradas ${n} de ${doc.numPages} páginas: baixe o arquivo para ver todas.</div>`);
}

window.addEventListener("message", async (ev) => {
  if (ev.origin !== SEEU || ev.source !== parent) return;
  const d = ev.data || {};
  if (d.apto !== "previa") return;
  if (d.redimensionar) { if (ultimo) setTimeout(() => mostrar(ultimo), 60); return; }
  const vez = ++atual;
  if (d.carregando) { $p.innerHTML = '<div class="sk" aria-hidden="true"></div>'; return; }
  if (d.erro) return msg("Prévia indisponível", d.erro);
  ultimo = { bytes: new Uint8Array(d.bytes || new ArrayBuffer(0)), tipo: String(d.tipo || "").toLowerCase() };
  mostrar(ultimo, vez);
});

async function mostrar(u, vez) {
  vez = vez || ++atual;
  const b = u.bytes.slice(0), tipo = u.tipo;
  try {
    if (ehPdf(b) || /pdf/.test(tipo)) return await pdf(b, vez);
    if (/^image\//.test(tipo)) {
      const u = URL.createObjectURL(new Blob([b], { type: tipo }));
      $p.innerHTML = "";
      const im = document.createElement("img");
      im.alt = "Documento";
      im.src = u;
      return $p.appendChild(im);
    }
    if (/html|text\//.test(tipo)) {
      const cs = (/charset=([\w-]+)/.exec(tipo) || [])[1];
      let txt;
      try { txt = new TextDecoder(cs || "utf-8", { fatal: !cs }).decode(b); } catch (e) { txt = new TextDecoder("windows-1252").decode(b); }
      $p.innerHTML = "";
      const f = document.createElement("iframe");
      f.style.height = "calc(100vh - 24px)";
      f.setAttribute("sandbox", "");   // sem scripts, sem formulários, sem navegação
      f.title = "Documento";
      f.srcdoc = /html/.test(tipo) ? txt : "<pre style='white-space:pre-wrap;font:13px/1.45 system-ui;padding:12px'>" + txt.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])) + "</pre>";
      return $p.appendChild(f);
    }
    msg("Prévia indisponível para este tipo de arquivo", "Clique no link para baixar.");
  } catch (e) {
    msg("Não foi possível mostrar a prévia", "Clique no link para baixar o arquivo.");
  }
}
// zoom: ajustar à largura (padrão), aumentar e diminuir; Ctrl + roda do mouse também
function aplicarZoom(z) {
  zoom = Math.max(0.5, Math.min(3, z));
  document.getElementById("zv").textContent = Math.round(zoom * 100) + "%";
  if (ultimo) mostrar(ultimo);
}
document.getElementById("zm").addEventListener("click", () => aplicarZoom(zoom - 0.25));
document.getElementById("zp").addEventListener("click", () => aplicarZoom(zoom + 0.25));
document.getElementById("za").addEventListener("click", () => aplicarZoom(1));
window.addEventListener("wheel", (e) => { if (!e.ctrlKey) return; e.preventDefault(); aplicarZoom(zoom + (e.deltaY < 0 ? 0.1 : -0.1)); }, { passive: false });
const doc = (location.hash.match(/doc=([\w]+)/) || [])[1];
if (doc) {
  // janela do documento (2º monitor): a extensão busca o arquivo do SEEU e a página o mostra inteiro
  document.documentElement.classList.add("janela");
  (async () => {
    const r = await chrome.runtime.sendMessage({ tipo: "docBytes", id: doc }).catch(() => null);
    if (!r || !r.ok) return msg("Não foi possível abrir o documento", (r && r.erro) || "");
    document.title = (r.nome || "Documento") + " - SEEU";
    const bin = atob(r.b64), b = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) b[i] = bin.charCodeAt(i);
    ultimo = { bytes: b, tipo: String(r.tipo || "").toLowerCase() };
    mostrar(ultimo);
  })();
} else {
  parent.postMessage({ apto: "previaPronta" }, SEEU);
}
