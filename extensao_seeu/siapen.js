// APTO - Ficha do SIAPEN: roda nas páginas do SIAPEN (app.siapen.ms.gov.br, sistema em uniGUI/ExtJS).
// 1) Captura: quando a janela "Ficha Disciplinar" carrega o PDF (/cache/.../FichaDisciplinar_*.pdf), busca o mesmo PDF com a
//    sessão aberta e entrega ao service worker, que grava na pasta da base.
// 2) Lote por nomes: na "Consulta Geral de Interno", digita cada nome, confere homônimos (pelo nome da mãe, se informado),
//    seleciona a linha, clica em "Ficha", espera o PDF ser salvo e fecha a janela da ficha. Um nome por vez, com intervalo.
// Os ids abaixo são os nomes dos componentes do SIAPEN (fixos entre sessões; os "OD.." mudam a cada login).
(function () {
  "use strict";
  if (window.__aptoSiapen) return;
  window.__aptoSiapen = true;
  const A = self.APTO;
  const ID = {
    consulta: "frmconsultainterno_0",
    localizar: "frmconsultainterno_editlocalizar_0",
    grade: "frmconsultainterno_dbgridconsulta_0",
    selecionado: "frmconsultainterno_unidbtext1_0",
    ficha: "frmconsultainterno_unibitbtnfichadisciplinarinterno_0",
    janelaFicha: "frmvisualizarrelatorio_0",
    quadroFicha: "frmvisualizarrelatorio_uniurlframe1_0",
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
    const cod = (/\((\d+)\)/.exec(decodeURIComponent(src)) || [])[1] || "";
    let r;
    try {
      const resp = await fetch(src, { credentials: "include", cache: "no-store" });
      const bytes = new Uint8Array(await resp.arrayBuffer());
      if (!resp.ok || !A.ehPdf(bytes)) r = await chrome.runtime.sendMessage({ tipo: "falha", processo: "", motivo: "o SIAPEN não devolveu o PDF da ficha" });
      else r = await chrome.runtime.sendMessage({ tipo: "fichaPdf", nome, cod, b64: base64(bytes), lote: !!lote });
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

  // ---- 2) lote por nomes ----
  let lote = null;
  function clicar(el) {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    const o = { bubbles: true, cancelable: true, view: window, clientX: r.left + r.width / 2, clientY: r.top + r.height / 2, button: 0 };
    for (const t of ["pointerdown", "mousedown", "pointerup", "mouseup", "click"]) el.dispatchEvent(new (t.startsWith("pointer") ? PointerEvent : MouseEvent)(t, o));
    return true;
  }
  async function esperar(fn, ms, passo) {
    const fim = Date.now() + ms;
    while (Date.now() < fim) { const v = fn(); if (v) return v; await dormir(passo || 250); }
    return null;
  }
  // linhas visíveis da grade: [{el, nome, prontuario, mae}]
  function linhas() {
    const g = $id(ID.grade);
    if (!g) return [];
    return [...g.querySelectorAll("tr.x-grid-row, tr.x-grid-data-row, table.x-grid-item tr")].map((tr) => {
      const c = [...tr.querySelectorAll("td")].map((td) => td.textContent.trim());
      return { el: tr.querySelector("td") || tr, nome: c[0] || "", prontuario: c[1] || "", mae: c[2] || "" };
    }).filter((x) => x.nome);
  }
  const assinatura = () => linhas().map((x) => x.nome + "|" + x.prontuario).join(";");

  async function umaFicha(item) {
    const nome = norm(item.nome), mae = norm(item.mae);
    if (nome.split(" ").length < 2) return { status: "erro", msg: "nome incompleto" };
    const pre = await chrome.runtime.sendMessage({ tipo: "podeFicha", nome, lote: true }).catch((e) => ({ ok: false, motivo: String(e) }));
    if (pre && pre.repetido) return { status: "repetido", msg: "já baixada hoje" };
    if (!pre || !pre.ok) return { status: "erro", msg: (pre && pre.motivo) || "extensão indisponível", parar: true };
    const campo = $id(ID.localizar + "-inputEl") || ($id(ID.localizar) || document).querySelector("input");
    if (!campo || !$id(ID.consulta)) return { status: "erro", msg: "abra Consultas > Consulta Geral de Interno", parar: true };
    // digita o nome (o SIAPEN filtra depois de 1 s sem digitar)
    const antes = assinatura();
    campo.focus();
    campo.value = nome;
    for (const t of ["input", "keyup", "change"]) campo.dispatchEvent(new Event(t, { bubbles: true }));
    const mudou = await esperar(() => assinatura() !== antes || (linhas().length && norm(linhas()[0].nome).startsWith(nome.split(" ")[0])), 15000);
    await dormir(1200);
    if (!mudou && !linhas().length) return { status: "erro", msg: "não encontrado no SIAPEN" };
    let cand = linhas().filter((x) => norm(x.nome) === nome);
    if (mae && cand.length > 1) cand = cand.filter((x) => norm(x.mae) === mae);
    if (mae && cand.length === 1 && norm(cand[0].mae) && norm(cand[0].mae) !== mae) cand = [];
    if (!cand.length) return { status: "erro", msg: "não encontrado no SIAPEN" + (mae ? " com essa mãe" : "") };
    if (cand.length > 1) return { status: "erro", msg: `homônimos (${cand.length}): informe o nome da mãe na lista` };
    const alvo = cand[0];
    clicar(alvo.el);
    const certo = await esperar(() => norm(($id(ID.selecionado) || {}).textContent) === nome, 8000);
    if (!certo) return { status: "erro", msg: "o SIAPEN não selecionou o interno" };
    ultimaCaptura = null;
    const btn = $id(ID.ficha);
    clicar((btn && (btn.querySelector(".x-btn-inner, .x-btn-button, button, a") || btn)) || null);
    const cap = await esperar(() => ultimaCaptura, 60000, 400);
    // fecha a janela da ficha (é modal e trava a consulta)
    const jan = $id(ID.janelaFicha);
    if (jan) { clicar(jan.querySelector(".x-tool-close, .x-tool-img.x-tool-close, [data-qtip='Fechar']")); await esperar(() => !$id(ID.janelaFicha) || $id(ID.janelaFicha).offsetParent === null, 8000); }
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
