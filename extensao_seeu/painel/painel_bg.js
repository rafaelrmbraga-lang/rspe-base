// APTO - painel no SEEU, lado do service worker (Chrome/Edge) ou da página de fundo (Firefox). Não depende do APTO:
// recebe da página do painel o HTML das abas do processo (lido na própria aba do SEEU) e o entrega ao motor da extensão
// (os mesmos .py do APTO no Pyodide). O resultado fica guardado só na sessão do navegador (chrome.storage.session, some ao
// fechar o navegador) por 10 minutos, porque o SEEU recarrega a página a cada aba: trocar de aba não refaz a leitura.
"use strict";
self.APTO_PAINEL = (() => {
  const VALIDADE_MS = 10 * 60 * 1000;
  const digitos = (p) => String(p || "").replace(/\D/g, "");

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

  function hojeBR() {
    const d = new Date();
    return String(d.getDate()).padStart(2, "0") + "/" + String(d.getMonth() + 1).padStart(2, "0") + "/" + d.getFullYear();
  }

  async function guardado(processo) {
    const ch = "painel:" + digitos(processo);
    const g = (await chrome.storage.session.get(ch))[ch];
    return g && Date.now() - g.quando < VALIDADE_MS && g.hoje === hojeBR() ? Object.assign({}, g.resultado, { guardado: true }) : null;
  }

  async function analisar(processo, abas) {
    const dig = digitos(processo);
    if (dig.length !== 20) return { estado: "erro", motivo: "número de processo não identificado na página" };
    if (!abas || !abas.capa) return { estado: "sem_dados" };
    let m;
    try { m = await motor("analisar", JSON.stringify({ abas, hoje: hojeBR() })); } catch (e) { m = { ok: false, erro: String((e && e.message) || e) }; }
    if (!m || !m.ok) return { estado: "erro", motivo: "o motor da extensão falhou: " + ((m && m.erro) || "sem resposta") };
    const painel = JSON.parse(m.painel);
    if (painel.erro) return { estado: "sem_dados", faltou: painel.faltou || [] };
    if (digitos(painel.processo) !== dig) return { estado: "erro", motivo: "as abas lidas são de outro processo (" + painel.processo + "): recarregue a página do SEEU" };
    const resultado = { estado: "ok", painel, motor: m.info, ms: m.ms, carga: m.carga, quando: Date.now() };
    await chrome.storage.session.set({ ["painel:" + dig]: { quando: Date.now(), hoje: hojeBR(), resultado } });
    return resultado;
  }

  // mensagens da página do painel (moldura da extensão dentro da aba do processo)
  function daPainel(sender) {
    return sender && sender.id === chrome.runtime.id && String(sender.url || "").startsWith(chrome.runtime.getURL("painel/painel.html"));
  }
  async function mensagem(msg) {
    if (msg.tipo === "painelGuardado") return (await guardado(msg.processo)) || null;
    if (msg.tipo === "painelAnalisar") return analisar(msg.processo, msg.abas);
    if (msg.tipo === "painelPreparar") { try { return await motor("carregar"); } catch (e) { return { ok: false, erro: String(e) }; } }
    return { ok: false };
  }
  return { daPainel, mensagem, analisar };
})();
