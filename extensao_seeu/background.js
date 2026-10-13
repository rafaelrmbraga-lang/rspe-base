// APTO - RSPE do SEEU: service worker.
// Cuidados: só age no SEEU (https://seeu.pje.jus.br), só no processo que a pessoa abriu, com a sessão dela (nenhuma senha
// guardada); um RSPE por processo, base e dia; intervalo mínimo entre downloads e teto por hora; confere se veio mesmo um
// PDF (senão apaga o arquivo e avisa - sessão expirada ou página de erro); pausa sozinha depois de 3 falhas seguidas;
// nada é enviado para fora do computador (a extensão não faz nenhuma requisição além do download pedido ao SEEU).
"use strict";
importScripts("comum.js");
const A = self.APTO;

const PADRAO = { ativo: true, raiz: "APTO", base: "", bases: [], avisoNaPagina: true };
const INTERVALO_MS = 4000;      // mínimo entre dois downloads
const TETO_HORA = 40;           // downloads automáticos por hora
const FALHAS_PAUSA = 3;         // falhas seguidas que pausam a extensão
const PAUSA_MS = 10 * 60 * 1000;
const LOG_MAX = 40;
const DIAS_HISTORICO = 30;      // chaves de "já baixado" mais antigas são apagadas

async function cfg() {
  const { cfg } = await chrome.storage.local.get("cfg");
  return Object.assign({}, PADRAO, cfg || {});
}
async function estado() {
  const r = await chrome.storage.local.get(["baixados", "log", "falhas", "pausadoAte"]);
  return { baixados: r.baixados || {}, log: r.log || [], falhas: r.falhas || 0, pausadoAte: r.pausadoAte || 0 };
}
async function registrar(item) {
  const st = await estado();
  st.log.unshift(Object.assign({ quando: Date.now() }, item));
  await chrome.storage.local.set({ log: st.log.slice(0, LOG_MAX) });
  await atualizarBadge();
}
async function atualizarBadge() {
  const c = await cfg();
  const st = await estado();
  const hoje = A.hojeISO();
  const n = Object.keys(st.baixados).filter((k) => k.endsWith("|" + hoje)).length;
  const pausado = st.pausadoAte > Date.now();
  await chrome.action.setBadgeText({ text: !c.ativo ? "off" : pausado ? "!" : n ? String(n) : "" });
  await chrome.action.setBadgeBackgroundColor({ color: !c.ativo ? "#8E958F" : pausado ? "#B42318" : "#1D5A3B" });
}
async function limparAntigos() {
  const st = await estado();
  const limite = A.hojeISO(new Date(Date.now() - DIAS_HISTORICO * 864e5));
  const b = {};
  for (const [k, v] of Object.entries(st.baixados)) if (k.split("|")[2] >= limite) b[k] = v;
  await chrome.storage.local.set({ baixados: b });
}

// fila: um download por vez, com intervalo mínimo
let ultimo = 0;
let fila = Promise.resolve();
function enfileirar(fn) {
  fila = fila.then(async () => {
    const espera = ultimo + INTERVALO_MS - Date.now();
    if (espera > 0) await new Promise((r) => setTimeout(r, espera));
    ultimo = Date.now();
    return fn();
  }).catch(() => {});
  return fila;
}

async function pedirRspe(msg, sender) {
  const c = await cfg();
  const st = await estado();
  if (!c.ativo) return { ok: false, motivo: "desligada" };
  if (st.pausadoAte > Date.now()) return { ok: false, motivo: "pausada depois de falhas seguidas; tente de novo em alguns minutos" };
  if (!sender || !sender.url || !/^https:\/\/seeu\.pje\.jus\.br\//.test(sender.url)) return { ok: false, motivo: "origem não é o SEEU" };
  if (!A.urlRspeValida(msg.url)) return { ok: false, motivo: "endereço do RSPE inválido" };
  const processo = A.cnj(msg.processo);
  if (!processo) return { ok: false, motivo: "nº do processo não encontrado na página" };
  const hoje = A.hojeISO();
  const chave = A.chaveDia(c, processo, hoje);
  if (st.baixados[chave] && !msg.forcar) return { ok: false, motivo: "já baixado hoje", repetido: true };
  const umaHora = Date.now() - 3600e3;
  const naHora = st.log.filter((x) => x.quando > umaHora && x.auto).length;
  if (naHora >= TETO_HORA && !msg.forcar) return { ok: false, motivo: `limite de ${TETO_HORA} downloads automáticos por hora` };

  const arquivo = A.caminhoArquivo(c, processo, hoje);
  let erro = "";
  await enfileirar(async () => {
   try {
    // o nome é confirmado de novo em onDeterminingFilename (com esse ouvinte ativo, o Chrome exige a sugestão)
    const nomes = (await chrome.storage.session.get("nomes")).nomes || {};
    nomes[msg.url] = arquivo;
    await chrome.storage.session.set({ nomes });
    const id = await chrome.downloads.download({ url: msg.url, filename: arquivo, conflictAction: "uniquify", saveAs: false });
    const pend = (await chrome.storage.session.get("pend")).pend || {};
    pend[id] = { processo, chave, arquivo, base: c.base, auto: !msg.forcar, tab: sender.tab && sender.tab.id, frame: sender.frameId };
    await chrome.storage.session.set({ pend });
   } catch (e) {
    erro = String(e && e.message || e);
   }
  });
  if (erro) {
    await registrar({ processo, base: c.base, arquivo: "", status: "erro", msg: "o Chrome recusou o download: " + erro, auto: !msg.forcar });
    return { ok: false, motivo: "o Chrome recusou o download: " + erro };
  }
  return { ok: true, arquivo };
}

// RSPE baixado pelo clique da própria pessoa no SEEU: vai para a pasta da base, com o nº do último processo aberto
chrome.downloads.onDeterminingFilename.addListener((item, sugerir) => {
  if (item.byExtensionId === chrome.runtime.id) {
    // os pedidos pela própria extensão: repete o nome escolhido (sem isso o Chrome usa o nome que o SEEU mandar)
    chrome.storage.session.get("nomes").then(({ nomes }) => {
      nomes = nomes || {};
      const arq = nomes[item.url];
      delete nomes[item.url];
      chrome.storage.session.set({ nomes });
      arq ? sugerir({ filename: arq, conflictAction: "uniquify" }) : sugerir();
    });
    return true;
  }
  const doSeeu = /^https:\/\/seeu\.pje\.jus\.br\//.test(item.finalUrl || item.url || "");
  if (!doSeeu || !(A.RE_RSPE.test(item.finalUrl || item.url || "") || A.RE_RSPE.test(item.filename || ""))) return false;
  (async () => {
    const c = await cfg();
    if (!c.ativo) return sugerir();
    const { ultimoProcesso } = await chrome.storage.session.get("ultimoProcesso");
    // só usa o nº se o processo foi aberto há pouco (senão o nome poderia ser de outro processo; o APTO lê o nº do conteúdo)
    const proc = ultimoProcesso && Date.now() - ultimoProcesso.quando < 3 * 60e3 ? ultimoProcesso.processo : "";
    const hoje = A.hojeISO();
    const arquivo = A.caminhoArquivo(c, proc, hoje);
    const pend = (await chrome.storage.session.get("pend")).pend || {};
    pend[item.id] = { processo: proc, chave: proc ? A.chaveDia(c, proc, hoje) : "", arquivo, base: c.base, auto: false, manual: true };
    await chrome.storage.session.set({ pend });
    sugerir({ filename: arquivo, conflictAction: "uniquify" });
  })();
  return true; // resposta assíncrona
});

// fim do download: confere se é PDF; se não for, apaga e conta falha
chrome.downloads.onChanged.addListener(async (d) => {
  if (!d.state || (d.state.current !== "complete" && d.state.current !== "interrupted")) return;
  const pend = (await chrome.storage.session.get("pend")).pend || {};
  const p = pend[d.id];
  if (!p) return;
  delete pend[d.id];
  await chrome.storage.session.set({ pend });
  const st = await estado();
  const [item] = await chrome.downloads.search({ id: d.id });
  const okPdf = d.state.current === "complete" && item && /pdf/i.test(item.mime || "") && (item.fileSize || item.totalBytes || 0) > 1500;
  if (okPdf) {
    if (p.chave) st.baixados[p.chave] = Date.now();
    await chrome.storage.local.set({ baixados: st.baixados, falhas: 0 });
    await registrar({ processo: p.processo, base: p.base, arquivo: p.arquivo, status: "ok", auto: p.auto, manual: !!p.manual });
    if (p.tab != null) chrome.tabs.sendMessage(p.tab, { tipo: "salvo", arquivo: p.arquivo }, { frameId: p.frame }).catch(() => {});
    return;
  }
  // não veio PDF (sessão expirada, página de erro, download interrompido): não deixa arquivo errado na pasta vigiada
  if (item && item.state === "complete") {
    try { await chrome.downloads.removeFile(d.id); } catch (e) {}
  }
  try { await chrome.downloads.erase({ id: d.id }); } catch (e) {}
  const falhas = st.falhas + 1;
  const pausa = falhas >= FALHAS_PAUSA ? Date.now() + PAUSA_MS : st.pausadoAte;
  await chrome.storage.local.set({ falhas, pausadoAte: pausa });
  const motivo = d.state.current === "interrupted" ? "download interrompido" : "o SEEU não devolveu um PDF (sessão expirada?)";
  await registrar({ processo: p.processo, base: p.base, arquivo: "", status: "erro", msg: motivo + (falhas >= FALHAS_PAUSA ? " - extensão pausada por 10 minutos" : ""), auto: p.auto });
  if (p.tab != null) chrome.tabs.sendMessage(p.tab, { tipo: "erro", msg: motivo }, { frameId: p.frame }).catch(() => {});
});

chrome.runtime.onMessage.addListener((msg, sender, responder) => {
  (async () => {
    try {
      if (msg.tipo === "rspe") return responder(await pedirRspe(msg, sender));
      if (msg.tipo === "processoVisto") {
        const p = A.cnj(msg.processo);
        if (p && sender.url && /^https:\/\/seeu\.pje\.jus\.br\//.test(sender.url)) await chrome.storage.session.set({ ultimoProcesso: { processo: p, quando: Date.now() } });
        return responder({ ok: true });
      }
      if (msg.tipo === "cfg") return responder(await cfg());
      if (sender.id !== chrome.runtime.id || sender.url && /^https?:/.test(sender.url)) return responder({ ok: false }); // o resto só do popup
      if (msg.tipo === "estado") {
        const st = await estado();
        return responder({ cfg: await cfg(), log: st.log, pausadoAte: st.pausadoAte, hoje: Object.keys(st.baixados).filter((k) => k.endsWith("|" + A.hojeISO())).length });
      }
      if (msg.tipo === "salvarCfg") {
        const c = Object.assign(await cfg(), msg.cfg || {});
        c.raiz = A.pastaSegura(c.raiz) || "APTO";
        c.bases = [...new Set((c.bases || []).map(A.pastaSegura).filter(Boolean))].sort((a, b) => a.localeCompare(b, "pt-BR"));
        c.base = A.pastaSegura(c.base);
        if (c.base && !c.bases.includes(c.base)) c.bases.push(c.base);
        await chrome.storage.local.set({ cfg: c });
        await atualizarBadge();
        return responder(c);
      }
      if (msg.tipo === "retomar") { await chrome.storage.local.set({ falhas: 0, pausadoAte: 0 }); await atualizarBadge(); return responder({ ok: true }); }
      if (msg.tipo === "limparHistorico") { await chrome.storage.local.set({ baixados: {}, log: [], falhas: 0, pausadoAte: 0 }); await atualizarBadge(); return responder({ ok: true }); }
      responder({ ok: false });
    } catch (e) {
      responder({ ok: false, motivo: String(e && e.message || e) });
    }
  })();
  return true;
});

chrome.runtime.onInstalled.addListener(async () => { await limparAntigos(); await atualizarBadge(); });
chrome.runtime.onStartup.addListener(async () => { await limparAntigos(); await atualizarBadge(); });
