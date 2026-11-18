// APTO - documento offscreen (Chrome/Edge) que guarda o motor do painel carregado: o service worker não roda o Pyodide.
import { analisar, carregar } from "./motor.js";

chrome.runtime.onMessage.addListener((msg, sender, responder) => {
  if (!msg || msg.alvo !== "motor" || sender.id !== chrome.runtime.id) return false;
  (async () => {
    try {
      if (msg.tipo === "analisar") return responder(await analisar(msg.texto));
      if (msg.tipo === "carregar") { const m = await carregar(); return responder({ ok: true, carga: m.carga, info: m.info }); }
      responder({ ok: false, erro: "pedido desconhecido" });
    } catch (e) {
      responder({ ok: false, erro: String((e && e.message) || e) });
    }
  })();
  return true;
});
