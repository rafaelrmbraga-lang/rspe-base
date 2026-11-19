// APTO - documento offscreen (Chrome/Edge) que guarda o motor do painel carregado: o service worker não roda o Pyodide.
import { analisarRspe, carregar, lerFicha, resumo, resumoPdf } from "./motor.js";

chrome.runtime.onMessage.addListener((msg, sender, responder) => {
  if (!msg || msg.alvo !== "motor" || sender.id !== chrome.runtime.id) return false;
  (async () => {
    try {
      if (msg.tipo === "resumo") return responder(await resumo(msg.processo));
      if (msg.tipo === "resumoPdf") return responder(await resumoPdf(msg.d, msg.canhoto));
      if (msg.tipo === "ficha" || msg.tipo === "rspe") {
        const bin = atob(String(msg.b64 || ""));
        const bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        return responder(msg.tipo === "ficha" ? await lerFicha(bytes, msg.arquivo) : await analisarRspe(bytes, msg.extra));
      }
      if (msg.tipo === "carregar") { const m = await carregar(); return responder({ ok: true, carga: m.carga, info: m.info }); }
      responder({ ok: false, erro: "pedido desconhecido" });
    } catch (e) {
      responder({ ok: false, erro: String((e && e.message) || e) });
    }
  })();
  return true;
});
