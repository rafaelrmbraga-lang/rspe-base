// APTO - RSPE do SEEU: roda nas páginas do SEEU (todas as molduras). Na página do processo, acha o link do RSPE e pede o
// download ao service worker. Não clica em nada, não altera a página do SEEU (salvo o aviso discreto de "salvo") e não lê
// outros dados além do nº do processo.
(function () {
  "use strict";
  if (window.__aptoRspe) return;
  window.__aptoRspe = true;
  const A = self.APTO;
  let pedido = false;

  // nº do processo aberto: título, cabeçalho e o início do texto da página (o nº da execução vem primeiro no SEEU)
  function processoDaPagina() {
    const fontes = [document.title];
    const cab = document.querySelector("#informacoesProcessuais, .tituloProcesso, h1, h2, h3, fieldset legend");
    if (cab) fontes.push(cab.textContent);
    fontes.push((document.body && document.body.innerText || "").slice(0, 4000));
    for (const t of fontes) {
      const p = A.cnj(t);
      if (p) return p;
    }
    return "";
  }

  // endereços do RSPE na página: href, onclick ou data-* que citem processoExecucaoPenal.do (resolvidos contra a página)
  function urlsRspe() {
    const achados = new Set();
    for (const el of document.querySelectorAll("a[href], [onclick], [data-href], [data-url]")) {
      for (const c of [el.getAttribute("href"), el.getAttribute("data-href"), el.getAttribute("data-url"), el.getAttribute("onclick")]) {
        if (!c || !A.RE_RSPE.test(c)) continue;
        const m = /['"]([^'"]*processoExecucaoPenal\.do[^'"]*)['"]/i.exec(c);
        const bruto = m ? m[1] : c;
        if (/^\s*javascript:/i.test(bruto)) continue;
        try {
          const u = new URL(bruto.replace(/&amp;/g, "&"), location.href).href;
          if (A.urlRspeValida(u)) achados.add(u);
        } catch (e) {}
      }
    }
    return [...achados];
  }
  // um único RSPE na página; com mais de um (lista de processos), o automático não age
  function urlRspe() {
    const u = urlsRspe();
    return u.length === 1 ? u[0] : "";
  }
  // página de processo: esta moldura ou uma acima dela é visualizacaoProcesso.do (mesma origem)
  function emProcesso() {
    let w = window;
    for (let i = 0; i < 5 && w; i++) {
      try { if (/visualizacaoProcesso\.do/i.test(w.location.pathname)) return true; } catch (e) { return false; }
      if (w === w.parent) break;
      w = w.parent;
    }
    return false;
  }

  function aviso(txt, erro) {
    chrome.runtime.sendMessage({ tipo: "cfg" }).then((c) => {
      if (!c || !c.avisoNaPagina) return;
      let el = document.getElementById("apto-rspe-aviso");
      if (!el) {
        el = document.createElement("div");
        el.id = "apto-rspe-aviso";
        el.setAttribute("role", "status");
        el.style.cssText = "position:fixed;right:14px;bottom:14px;z-index:2147483000;max-width:340px;padding:8px 12px;border-radius:8px;" +
          "font:12px/1.35 system-ui,Segoe UI,Arial,sans-serif;box-shadow:0 6px 18px rgba(0,0,0,.18);pointer-events:none;transition:opacity .3s";
        (document.body || document.documentElement).appendChild(el);
      }
      el.style.background = erro ? "#FBEAEA" : "#E8F2EC";
      el.style.color = erro ? "#8E2424" : "#1D5A3B";
      el.style.border = "1px solid " + (erro ? "#E3B4B4" : "#B9D6C4");
      el.textContent = txt;
      el.style.opacity = "1";
      clearTimeout(el._t);
      el._t = setTimeout(() => { el.style.opacity = "0"; }, 5000);
    }).catch(() => {});
  }

  async function procurar(forcar) {
    const url = urlRspe() || (forcar ? (urlsRspe()[0] || "") : "");
    const processo = processoDaPagina();
    if (processo) chrome.runtime.sendMessage({ tipo: "processoVisto", processo }).catch(() => {});
    if (!url) return { achou: false, processo };
    if (pedido && !forcar) return { achou: true, processo, pedido: true };
    pedido = true;
    const r = await chrome.runtime.sendMessage({ tipo: "rspe", url, processo, forcar: !!forcar }).catch((e) => ({ ok: false, motivo: String(e) }));
    if (forcar && r && !r.ok) aviso("APTO: " + (r.motivo || "não foi possível baixar o RSPE"), true);
    return Object.assign({ achou: true, processo }, r || {});
  }

  chrome.runtime.onMessage.addListener((msg, _s, responder) => {
    if (msg.tipo === "salvo") { aviso("APTO: RSPE salvo em Downloads/" + msg.arquivo); return; }
    if (msg.tipo === "erro") { aviso("APTO: " + msg.msg, true); return; }
    if (msg.tipo === "procurar") {
      // só responde a moldura que tem o link do RSPE (as demais ficam em silêncio)
      if (!urlsRspe().length) return false;
      procurar(!!msg.forcar).then(responder);
      return true;
    }
  });

  // automático: só na página de um processo, e só uma vez por carregamento; espera o SEEU montar a página (até 20 s)
  function talvez() {
    if (!emProcesso()) return false;
    if (!urlRspe()) return false;
    procurar(false);
    return true;
  }
  // guarda o nº do processo aberto (nomeia o RSPE baixado pelo botão do próprio SEEU)
  if (emProcesso()) {
    const p0 = processoDaPagina();
    if (p0) chrome.runtime.sendMessage({ tipo: "processoVisto", processo: p0 }).catch(() => {});
  }
  if (!talvez()) {
    const obs = new MutationObserver(() => { if (talvez()) obs.disconnect(); });
    obs.observe(document.documentElement, { childList: true, subtree: true });
    setTimeout(() => obs.disconnect(), 20000);
  }
})();
