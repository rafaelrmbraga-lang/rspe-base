// APTO - painel no SEEU, lado do service worker (Chrome/Edge) ou da página de fundo (Firefox). Não depende do APTO:
// recebe da página do painel o HTML das abas do processo (lido na própria aba do SEEU) e o entrega ao motor da extensão
// (os mesmos .py do APTO no Pyodide). O resultado fica guardado só na sessão do navegador (chrome.storage.session, some ao
// fechar o navegador) por 10 minutos, porque o SEEU recarrega a página a cada aba: trocar de aba não refaz a leitura.
// Ficha disciplinar: a carregada no painel (por processo) e as abertas no SIAPEN nesta sessão (com a ficha automática ligada)
// são lidas pelo motor (pdf.js + o leitor do APTO) e entram na análise; o motor só usa a ficha que for desta pessoa.
// A ficha fica só na sessão do navegador.
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
  async function motor(tipo, texto, extra) {
    if (chrome.offscreen) {
      await garantirOffscreen();
      return chrome.runtime.sendMessage(Object.assign({ alvo: "motor", tipo, texto }, extra || {}));
    }
    const m = await import(chrome.runtime.getURL("painel/motor.js"));
    if (tipo === "carregar") return m.carregar().then((x) => ({ ok: true, carga: x.carga, info: x.info }));
    if (tipo === "resumo") return m.resumo(extra.processo);
    if (tipo === "resumoPdf") return m.resumoPdf(extra.d, extra.canhoto);
    if (tipo === "ficha") {
      const bin = atob(extra.b64), bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      return m.lerFicha(bytes, extra.arquivo);
    }
    return m.analisar(texto);
  }

  // ---------- fichas disciplinares (só na sessão)
  const MAX_FICHAS_SIAPEN = 20;
  async function versaoFichas() { return (await chrome.storage.session.get("fichasVersao")).fichasVersao || 0; }
  async function mudouFichas() { await chrome.storage.session.set({ fichasVersao: (await versaoFichas()) + 1 }); }
  async function fichasPara(dig) {
    const g = await chrome.storage.session.get(["painelFicha:" + dig, "fichasSiapen"]);
    const doPainel = g["painelFicha:" + dig];
    return { doPainel, lista: [doPainel && doPainel.ficha, ...((g.fichasSiapen || []).map((x) => x.ficha))].filter(Boolean) };
  }
  async function carregarFicha(processo, b64, arquivo) {
    const dig = digitos(processo);
    if (dig.length !== 20) return { ok: false, erro: "número de processo não identificado" };
    let r;
    try { r = await motor("ficha", "", { b64, arquivo }); } catch (e) { r = { ok: false, erro: String((e && e.message) || e) }; }
    if (!r || !r.ok) return { ok: false, erro: (r && r.erro) || "a ficha não foi lida" };
    await chrome.storage.session.set({ ["painelFicha:" + dig]: { ficha: r.ficha, resumo: r.resumo, arquivo: arquivo || "", quando: Date.now() } });
    await mudouFichas();
    return { ok: true, resumo: r.resumo };
  }
  async function retirarFicha(processo) {
    await chrome.storage.session.remove("painelFicha:" + digitos(processo));
    await mudouFichas();
    return { ok: true };
  }
  // ficha aberta no SIAPEN (siapen.js -> background "fichaPdf"): lida em segundo plano, para o painel de qualquer processo
  async function fichaDoSiapen(b64, arquivo) {
    let r;
    try { r = await motor("ficha", "", { b64, arquivo }); } catch (e) { return; }
    if (!r || !r.ok) return;
    const { fichasSiapen } = await chrome.storage.session.get("fichasSiapen");
    const ch = (r.resumo.nome || "") + "|" + (r.resumo.cpf || "") + "|" + (r.resumo.impressa || "");
    const L = (fichasSiapen || []).filter((x) => x.chave !== ch);
    L.unshift({ chave: ch, ficha: r.ficha, resumo: r.resumo, quando: Date.now() });
    await chrome.storage.session.set({ fichasSiapen: L.slice(0, MAX_FICHAS_SIAPEN) });
    await mudouFichas();
  }

  function hojeBR() {
    const d = new Date();
    return String(d.getDate()).padStart(2, "0") + "/" + String(d.getMonth() + 1).padStart(2, "0") + "/" + d.getFullYear();
  }

  async function guardado(processo) {
    const ch = "painel:" + digitos(processo);
    const g = (await chrome.storage.session.get(ch))[ch];
    return g && Date.now() - g.quando < VALIDADE_MS && g.hoje === hojeBR() && g.fichas === (await versaoFichas())
      ? Object.assign({}, g.resultado, { guardado: true }) : null;
  }

  async function analisar(processo, abas) {
    const dig = digitos(processo);
    if (dig.length !== 20) return { estado: "erro", motivo: "número de processo não identificado na página" };
    if (!abas || !abas.capa) return { estado: "sem_dados" };
    const fic = await fichasPara(dig);
    let m;
    try { m = await motor("analisar", JSON.stringify({ abas, hoje: hojeBR(), fichas: fic.lista })); } catch (e) { m = { ok: false, erro: String((e && e.message) || e) }; }
    if (!m || !m.ok) return { estado: "erro", motivo: "o motor da extensão falhou: " + ((m && m.erro) || "sem resposta") };
    const painel = JSON.parse(m.painel);
    if (painel.erro) return { estado: "sem_dados", faltou: painel.faltou || [], diag: painel.diag || null };
    if (digitos(painel.processo) !== dig) return { estado: "erro", motivo: "as abas lidas são de outro processo (" + painel.processo + "): recarregue a página do SEEU" };
    const resultado = { estado: "ok", painel, motor: m.info, ms: m.ms, carga: m.carga, quando: Date.now(),
      fichaCarregada: fic.doPainel ? { resumo: fic.doPainel.resumo, arquivo: fic.doPainel.arquivo } : null };
    await chrome.storage.session.set({ ["painel:" + dig]: { quando: Date.now(), hoje: hojeBR(), fichas: await versaoFichas(), resultado } });
    return resultado;
  }

  // mensagens da página do painel (moldura da extensão dentro da aba do processo)
  function daPainel(sender) {
    return sender && sender.id === chrome.runtime.id && String(sender.url || "").startsWith(chrome.runtime.getURL("painel/painel.html"));
  }
  async function mensagem(msg) {
    if (msg.tipo === "painelGuardado") return (await guardado(msg.processo)) || null;
    if (msg.tipo === "painelAnalisar") return analisar(msg.processo, msg.abas);
    if (msg.tipo === "painelResumo") {
      try { return await motor("resumo", "", { processo: digitos(msg.processo) }); } catch (e) { return { ok: false, erro: String(e) }; }
    }
    if (msg.tipo === "painelResumoPdf") {
      try { return await motor("resumoPdf", "", { d: msg.d, canhoto: !!msg.canhoto }); } catch (e) { return { ok: false, erro: String(e) }; }
    }
    if (msg.tipo === "painelFicha") return carregarFicha(msg.processo, msg.b64, msg.arquivo);
    if (msg.tipo === "painelFichaRetirar") return retirarFicha(msg.processo);
    if (msg.tipo === "painelPreparar") { try { return await motor("carregar"); } catch (e) { return { ok: false, erro: String(e) }; } }
    return { ok: false };
  }
  return { daPainel, mensagem, analisar, fichaDoSiapen };
})();
