// APTO - documentos do SEEU, lado do service worker (usado pela extensão do APTO e pela APTO SEEU): o arquivo.do do SEEU
// redireciona para o servidor de arquivos (S3), que a página do SEEU não pode ler; a extensão busca com a sessão do SEEU e devolve
// os bytes - para a prévia ao passar o mouse e para a janela do documento no 2º monitor. Só leitura; só o SEEU e o servidor de
// arquivos do SEEU.
"use strict";
self.APTO_DOCS = (() => {
const MAX_DOC = 25 * 1024 * 1024;
function arquivoPermitido(u) {
  try { const x = new URL(u); return x.origin === "https://seeu.pje.jus.br" && /^\/seeu\/arquivo\.do$/i.test(x.pathname); } catch (e) { return false; }
}
async function arquivoSeeu(url) {
  if (!arquivoPermitido(url)) return { ok: false, erro: "endereço fora dos documentos do SEEU" };
  let r;
  try { r = await fetch(url, { credentials: "include", cache: "no-store" }); } catch (e) { return { ok: false, erro: "o SEEU não respondeu" }; }
  const fim = new URL(r.url || url);
  if (!/^(seeu\.pje\.jus\.br|seeu-transfer\.s3(\.sa-east-1)?\.amazonaws\.com)$/.test(fim.hostname)) return { ok: false, erro: "o documento veio de outro endereço" };
  if (!r.ok) return { ok: false, erro: "o SEEU respondeu " + r.status };
  const buf = new Uint8Array(await r.arrayBuffer());
  if (buf.length > MAX_DOC) return { ok: false, erro: "arquivo grande demais para a prévia" };
  let bin = "";
  for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
  return { ok: true, b64: btoa(bin), tipo: r.headers.get("content-type") || "" };
}
// abrir o documento numa janela no 2º monitor (se houver; senão, numa janela à parte): a mesma janela é reaproveitada
async function abrirDocMonitor2(url, nome, sender) {
  if (!arquivoPermitido(url)) return { ok: false };
  const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
  await chrome.storage.session.set({ ["doc:" + id]: { url, nome: String(nome || "").slice(0, 120) } });
  const destino = chrome.runtime.getURL("painel/previa.html#doc=" + id);
  const { docJanela } = await chrome.storage.session.get("docJanela");
  if (docJanela) {
    try {
      const w = await chrome.windows.get(docJanela.janela, { populate: true });
      const t = (w.tabs || [])[0];
      if (t) { await chrome.tabs.update(t.id, { url: destino }); await chrome.windows.update(w.id, { focused: true }); return { ok: true, reaproveitada: true }; }
    } catch (e) { /* a janela foi fechada */ }
  }
  let area = null;
  try {
    if (chrome.system && chrome.system.display) {
      const telas = await chrome.system.display.getInfo();
      const atual = sender.tab ? await chrome.windows.get(sender.tab.windowId) : null;
      const dentro = (t) => atual && atual.left >= t.bounds.left - 50 && atual.left < t.bounds.left + t.bounds.width;
      const outra = telas.find((t) => !dentro(t) && !t.isPrimary) || telas.find((t) => !dentro(t)) || null;
      if (outra) area = outra.workArea;
    }
  } catch (e) { area = null; }
  const op = { url: destino, type: "normal", focused: true };
  if (area) Object.assign(op, { left: area.left, top: area.top, width: area.width, height: area.height });
  const w = await chrome.windows.create(op);
  if (area) { try { await chrome.windows.update(w.id, { state: "maximized" }); } catch (e) { /* segue */ } }
  await chrome.storage.session.set({ docJanela: { janela: w.id } });
  return { ok: true, monitor2: !!area };
}

  return { arquivoSeeu, abrirDocMonitor2, arquivoPermitido };
})();
