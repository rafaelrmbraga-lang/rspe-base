// APTO - painel no SEEU, lado do service worker (Chrome/Edge) ou da página de fundo (Firefox).
// Pede ao APTO aberto (só neste computador, 127.0.0.1) o dossiê do processo: registro, fatia do contexto (ficha, ajustes
// manuais), data de referência, base jurídica em uso e o resultado do APTO. O motor da extensão refaz a conta com o mesmo
// código e a mesma entrada; o painel só diz "confere com o APTO" quando a assinatura dos dois resultados é a mesma.
// O dossiê vai ao motor em TEXTO, como chegou (relido em JavaScript, 5.0 viraria 5 e mudaria a impressão digital).
// Nada é guardado fora da sessão do navegador (chrome.storage.session: some ao fechar o navegador).
"use strict";
self.APTO_PAINEL = (() => {
  const RAIZ = "http://127.0.0.1:47321";
  const VALIDADE_MS = 10 * 60 * 1000; // resultado guardado na sessão: o SEEU recarrega a página a cada aba

  function digitos(p) {
    return String(p || "").replace(/\D/g, "");
  }

  async function comPrazo(url, op, ms) {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), ms);
    try { return await fetch(url, Object.assign({ cache: "no-store", signal: ctl.signal }, op)); } finally { clearTimeout(t); }
  }

  async function token() {
    try {
      const r = await comPrazo(RAIZ + "/sei/token", {}, 3000);
      return r.ok ? ((await r.json()).token || "") : "";
    } catch (e) { return ""; }
  }

  async function aptoPost(caminho, corpo, ms) {
    const tk = await token();
    if (!tk) return { estado: "sem_apto" };
    let r;
    try {
      r = await comPrazo(RAIZ + caminho, { method: "POST", headers: { "Content-Type": "application/json", Authorization: "Bearer " + tk },
        body: JSON.stringify(corpo) }, ms || 30000);
    } catch (e) { return { estado: "sem_apto" }; }
    if (r.status === 401) return { estado: "sem_apto", motivo: "o APTO recusou o pedido (token)" };
    if (!r.ok) return { estado: "erro", motivo: "o APTO respondeu " + r.status };
    return { estado: "ok", texto: await r.text() };
  }

  // motor: documento offscreen no Chrome/Edge; no Firefox, a própria página de fundo
  let criando = null;
  async function garantirOffscreen() {
    if (await chrome.offscreen.hasDocument()) return;
    if (!criando) {
      criando = chrome.offscreen.createDocument({ url: "painel/motor.html", reasons: ["WORKERS"],
        justification: "Roda o motor de cálculo do APTO (Python no navegador) para o painel do processo no SEEU." })
        .finally(() => { criando = null; });
    }
    await criando;
  }
  async function motor(tipo, texto) {
    if (chrome.offscreen) {
      await garantirOffscreen();
      return chrome.runtime.sendMessage({ alvo: "motor", tipo, texto });
    }
    const m = await import(chrome.runtime.getURL("painel/motor.js"));
    return tipo === "carregar" ? m.carregar().then((x) => ({ ok: true, carga: x.carga, info: x.info })) : m.analisar(texto);
  }

  async function analisar(processo, forcar) {
    const dig = digitos(processo);
    if (dig.length !== 20) return { estado: "erro", motivo: "número de processo não identificado na página" };
    const chave = "painel:" + dig;
    if (!forcar) {
      const g = (await chrome.storage.session.get(chave))[chave];
      if (g && Date.now() - g.quando < VALIDADE_MS) return Object.assign({}, g.resultado, { guardado: true });
    }
    const d = await aptoPost("/painel/dossie", { processo: dig });
    if (d.estado !== "ok") return d;
    let apto;
    try { apto = JSON.parse(d.texto); } catch (e) { return { estado: "erro", motivo: "resposta do APTO ilegível" }; }
    if (apto.__status || apto.erro) return { estado: "erro", motivo: apto.erro || "erro no APTO" };
    if (!apto.tem) return { estado: "fora_da_base", motivo: apto.motivo || "", base: apto.base || "" };
    let m;
    try { m = await motor("analisar", d.texto); } catch (e) { m = { ok: false, erro: String((e && e.message) || e) }; }
    if (!m || !m.ok) return { estado: "erro", motivo: "o motor da extensão falhou: " + ((m && m.erro) || "sem resposta"), apto: apto.painel, base: apto.base };
    const painel = JSON.parse(m.painel);
    const confere = painel.assinatura === apto.painel.assinatura && painel.chave === apto.painel.chave;
    const resultado = { estado: confere ? "confere" : "diverge", painel, apto: confere ? null : apto.painel, base: apto.base,
      motor: m.info, ms: m.ms, carga: m.carga, quando: Date.now() };
    await chrome.storage.session.set({ [chave]: { quando: Date.now(), resultado } });
    return resultado;
  }

  async function abrirNoApto(processo) {
    const d = await aptoPost("/painel/abrir", { processo: digitos(processo) }, 5000);
    return { ok: d.estado === "ok" };
  }

  // mensagens da página do painel (iframe da extensão dentro da aba do processo)
  function daPainel(sender) {
    return sender && sender.id === chrome.runtime.id && String(sender.url || "").startsWith(chrome.runtime.getURL("painel/painel.html"));
  }
  async function mensagem(msg) {
    if (msg.tipo === "painelAnalisar") return analisar(msg.processo, !!msg.forcar);
    if (msg.tipo === "painelAbrirApto") return abrirNoApto(msg.processo);
    if (msg.tipo === "painelPreparar") { try { return await motor("carregar"); } catch (e) { return { ok: false, erro: String(e) }; } }
    return { ok: false };
  }
  return { daPainel, mensagem, analisar };
})();
