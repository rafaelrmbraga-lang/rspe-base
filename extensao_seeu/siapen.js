// APTO - Ficha do SIAPEN: roda nas páginas do SIAPEN (app.siapen.ms.gov.br, sistema em uniGUI/ExtJS).
// Abre direto em app.siapen.ms.gov.br:8390 ou dentro do portal www.siapen.ms.gov.br (moldura).
// 1) Captura: quando a janela "Ficha Disciplinar" carrega o PDF (/cache/.../FichaDisciplinar_*.pdf), busca o mesmo PDF com a
//    sessão aberta e entrega ao service worker, que grava na pasta da base.
// 2) Lote por nomes: na "Consulta Geral de Interno", localiza cada nome, confere homônimos (pelo nome da mãe, se informado),
//    seleciona a linha, clica em "Ficha", espera o PDF ser salvo e fecha a janela da ficha. Um nome por vez, com intervalo.
//    Os comandos na tela do SIAPEN são feitos por siapen_pagina.js (mundo da página, componentes ExtJS do próprio SIAPEN).
// Os ids abaixo são os nomes dos componentes do SIAPEN (fixos entre sessões; os "OD.." mudam a cada login).
(function () {
  "use strict";
  if (window.__aptoSiapen) return;
  window.__aptoSiapen = true;
  const A = self.APTO;
  const ID = {
    consulta: "frmconsultainterno_0",
    selecionado: "frmconsultainterno_unidbtext1_0",
  };
  const RE_FICHA = /\/cache\/[^"']*FichaDisciplinar_[^"']*\.pdf/i;
  const dormir = (ms) => new Promise((r) => setTimeout(r, ms));
  const $id = (id) => document.getElementById(id);
  const norm = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/\s+/g, " ").trim().toUpperCase();

  function base64(bytes) {
    let s = "";
    for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    return btoa(s);
  }

  // ---- 1) captura do PDF da ficha ----
  const capturados = new Set();
  let ultimaCaptura = null; // {src, r} - o lote espera por ela
  async function capturar(src) {
    if (capturados.has(src)) return;
    capturados.add(src);
    const nome = norm(($id(ID.selecionado) || {}).textContent || "");
    let r;
    try {
      const resp = await fetch(src, { credentials: "include", cache: "no-store" });
      const bytes = new Uint8Array(await resp.arrayBuffer());
      if (!resp.ok || !A.ehPdf(bytes)) r = await chrome.runtime.sendMessage({ tipo: "falha", processo: "", motivo: "o SIAPEN não devolveu o PDF da ficha" });
      else r = await chrome.runtime.sendMessage({ tipo: "fichaPdf", nome, b64: base64(bytes), lote: !!lote });
    } catch (e) {
      r = { ok: false, motivo: "o SIAPEN não respondeu" };
    }
    ultimaCaptura = { src, r: r || { ok: false } };
  }
  function procurarFicha(raiz) {
    for (const f of (raiz || document).querySelectorAll("iframe, embed, object")) {
      const src = f.getAttribute("src") || f.getAttribute("data") || "";
      if (RE_FICHA.test(src)) capturar(new URL(src, location.href).href);
    }
  }
  new MutationObserver((ms) => {
    for (const m of ms) {
      if (m.type === "attributes") { if (m.target.matches && m.target.matches("iframe, embed, object")) procurarFicha(m.target.parentNode); }
      else for (const n of m.addedNodes) if (n.nodeType === 1) procurarFicha(n.parentNode || n);
    }
  }).observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ["src", "data"] });

  // ---- 2) lote por nomes (os comandos vão para siapen_pagina.js, que usa os componentes do próprio SIAPEN) ----
  let lote = null;
  let seq = 0;
  const esperas = {};
  document.addEventListener("apto-siapen-resposta", (e) => {
    let q;
    try { q = JSON.parse(e.detail); } catch (x) { return; }
    if (esperas[q.id]) { esperas[q.id](q.r); delete esperas[q.id]; }
  });
  function pagina(op, args) {
    return new Promise((ok) => {
      const id = ++seq;
      esperas[id] = ok;
      setTimeout(() => { if (esperas[id]) { delete esperas[id]; ok({ erro: "a página do SIAPEN não respondeu" }); } }, 5000);
      document.dispatchEvent(new CustomEvent("apto-siapen-pedido", { detail: JSON.stringify({ id, op, args }) }));
    });
  }
  async function esperar(fn, ms, passo) {
    const fim = Date.now() + ms;
    while (Date.now() < fim) { const v = await fn(); if (v) return v; await dormir(passo || 300); }
    return null;
  }
  // espera o SIAPEN terminar de responder (sem pedido em andamento por 0,6 s seguidos)
  async function quieto(ms) {
    let desde = 0;
    return esperar(async () => {
      const e = await pagina("estado");
      if (e.ocupado) { desde = 0; return false; }
      if (!desde) desde = Date.now();
      return Date.now() - desde >= 600;
    }, ms || 20000, 200);
  }

  async function umaFicha(item) {
    const nome = norm(item.nome), mae = norm(item.mae);
    if (nome.split(" ").length < 2) return { status: "erro", msg: "nome incompleto" };
    const pre = await chrome.runtime.sendMessage({ tipo: "podeFicha", nome, lote: true }).catch((e) => ({ ok: false, motivo: String(e) }));
    if (pre && pre.repetido) return { status: "repetido", msg: "já baixada hoje" };
    if (!pre || !pre.ok) return { status: "erro", msg: (pre && pre.motivo) || "extensão indisponível", parar: true };
    const est = await pagina("estado");
    if (!est.consulta) return { status: "erro", msg: "abra Consultas > Consulta Geral de Interno", parar: true };
    if (est.janela) { await pagina("fechar"); await quieto(8000); }
    // localiza o nome (o SIAPEN posiciona no primeiro nome que começa assim e recarrega a grade)
    const c0 = est.cargas;
    const r1 = await pagina("localizar", { nome });
    if (r1.erro) return { status: "erro", msg: "não foi possível digitar o nome: " + r1.erro, parar: true };
    await esperar(async () => (await pagina("estado")).cargas > c0, 15000);
    await quieto();
    const g = await pagina("linhas");
    if (g.erro) return { status: "erro", msg: "não foi possível ler a grade: " + g.erro };
    let cand = g.linhas.filter((x) => norm(x.nome) === nome);
    if (mae && cand.length > 1) cand = cand.filter((x) => norm(x.mae) === mae);
    if (mae && cand.length === 1 && norm(cand[0].mae) && norm(cand[0].mae) !== mae) cand = [];
    if (!cand.length) return { status: "erro", msg: "não encontrado no SIAPEN" + (mae ? " com essa mãe" : "") };
    if (cand.length > 1) return { status: "erro", msg: `homônimos (${cand.length}): informe o nome da mãe na lista` };
    const alvo = cand[0];
    if (alvo.i !== g.atual) {
      const r2 = await pagina("selecionar", { i: alvo.i });
      if (r2.erro) return { status: "erro", msg: "não foi possível selecionar a linha: " + r2.erro };
      await dormir(400);
      await quieto();
    }
    const certo = await esperar(async () => norm((await pagina("estado")).rotulo) === nome, 8000);
    if (!certo) return { status: "erro", msg: "o SIAPEN não selecionou o interno" };
    ultimaCaptura = null;
    const r3 = await pagina("ficha");
    if (r3.erro || r3.ok === false) return { status: "erro", msg: "não foi possível clicar em Ficha: " + (r3.erro || r3.motivo) };
    const cap = await esperar(() => ultimaCaptura, 60000, 400);
    // fecha a janela da ficha (é modal e trava a consulta)
    await esperar(async () => (await pagina("estado")).janela, 5000);
    await pagina("fechar");
    await esperar(async () => !(await pagina("estado")).janela, 8000);
    await quieto(8000);
    if (!cap) return { status: "erro", msg: "a ficha não abriu em 60 s" };
    if (cap.r && cap.r.ok) return { status: "ok", msg: cap.r.arquivo };
    if (cap.r && cap.r.repetido) return { status: "repetido", msg: "já baixada hoje" };
    return { status: "erro", msg: (cap.r && cap.r.motivo) || "falha ao salvar", parar: !!(cap.r && /pausada/.test(cap.r.motivo || "")) };
  }

  async function rodarLote(itens) {
    if (lote) return { ok: false, motivo: "já há um lote em andamento" };
    lote = { parar: false };
    (async () => {
      for (let i = 0; i < itens.length; i++) {
        if (lote.parar) break;
        await chrome.runtime.sendMessage({ tipo: "loteItem", i, status: "rodando" }).catch(() => {});
        let r;
        try { r = await umaFicha(itens[i]); } catch (e) { r = { status: "erro", msg: String(e && e.message || e) }; }
        await chrome.runtime.sendMessage({ tipo: "loteItem", i, status: r.status, msg: r.msg }).catch(() => {});
        if (r.parar) { lote.parar = true; break; }
        if (i < itens.length - 1 && r.status !== "repetido") await dormir(8000);
      }
      const parou = lote.parar;
      lote = null;
      chrome.runtime.sendMessage({ tipo: "loteFim", parou }).catch(() => {});
    })();
    return { ok: true };
  }

  chrome.runtime.onMessage.addListener((msg, _s, responder) => {
    // só responde a moldura onde está a Consulta Geral de Interno
    if (msg.tipo === "loteFichas") { if (!$id(ID.consulta)) return false; rodarLote(msg.itens || []).then(responder); return true; }
    if (msg.tipo === "lotePare") { if (lote) { lote.parar = true; responder({ ok: true }); } return false; }
  });
  procurarFicha(document);
})();
