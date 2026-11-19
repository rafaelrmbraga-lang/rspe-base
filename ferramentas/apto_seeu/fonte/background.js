// APTO SEEU - service worker: só o que o painel do processo no SEEU usa (sem SIAPEN, SEI, SAP nem download do RSPE).
// Motor do painel (painel/painel_bg.js), documentos do SEEU (painel/docs_bg.js) e as opções (painel e 2º monitor).
"use strict";
importScripts("comum.js", "painel/painel_bg.js", "painel/docs_bg.js");

const PADRAO = { ativo: true, painel: true, docMonitor2: false };
async function cfg() {
  const { cfg } = await chrome.storage.local.get("cfg");
  return Object.assign({}, PADRAO, cfg || {});
}
const doSeeu = (u) => /^https:\/\/seeu\.pje\.jus\.br\//.test(u || "");
const daExtensao = (sender, pagina) => sender.id === chrome.runtime.id && String(sender.url || "").startsWith(chrome.runtime.getURL(pagina));

chrome.runtime.onMessage.addListener((msg, sender, responder) => {
  (async () => {
    try {
      if (!msg || msg.alvo === "motor") return;   // pedido ao documento offscreen do motor
      if (/^painel[A-Z]/.test(String(msg.tipo || "")) && self.APTO_PAINEL.daPainel(sender)) return responder(await self.APTO_PAINEL.mensagem(msg));
      if (msg.tipo === "cfg") return responder(await cfg());
      if (msg.tipo === "salvarCfg" && daExtensao(sender, "popup.html")) {
        const c = Object.assign(await cfg(), { painel: !!msg.cfg.painel, docMonitor2: !!msg.cfg.docMonitor2, ativo: msg.cfg.ativo !== false });
        await chrome.storage.local.set({ cfg: c });
        return responder(c);
      }
      if (sender.tab && doSeeu(sender.url) && msg.tipo === "seeuArquivo") return responder(await self.APTO_DOCS.arquivoSeeu(msg.url));
      if (sender.tab && doSeeu(sender.url) && msg.tipo === "seeuAbrirDoc") return responder(await self.APTO_DOCS.abrirDocMonitor2(msg.url, msg.nome, sender));
      if (daExtensao(sender, "painel/previa.html") && msg.tipo === "docBytes") {
        const d = (await chrome.storage.session.get("doc:" + msg.id))["doc:" + msg.id];
        return responder(d ? Object.assign(await self.APTO_DOCS.arquivoSeeu(d.url), { nome: d.nome }) : { ok: false, erro: "documento não encontrado" });
      }
      responder({ ok: false });
    } catch (e) {
      responder({ ok: false, erro: String((e && e.message) || e) });
    }
  })();
  return true;
});
