// APTO - RSPE do SEEU: roda nas páginas do SEEU (todas as molduras). Na página do processo (visualizacaoProcesso.do), acha
// no próprio HTML o endereço do relatório "Situação Carcerária" (RSPE; o SEEU o guarda no script gerarResa), busca o PDF
// com a sessão aberta e entrega ao service worker, que grava na pasta da base. Não clica em nada, não abre janelas e não
// altera a página (salvo o aviso discreto de "salvo"); lê só o nº do processo e o id interno do relatório.
(function () {
  "use strict";
  if (window.__aptoRspe) return;
  window.__aptoRspe = true;
  const A = self.APTO;
  let pedido = false;

  // nº da execução: campo oculto do SEEU, título da página, cabeçalho
  function processoDaPagina() {
    const campo = document.getElementById("processoNumeroFormatado") || document.querySelector("input[name=processoNumeroFormatado]");
    const fontes = [campo && campo.value, document.title];
    const cab = document.querySelector("#informacoesProcessuais, .tituloProcesso, h1, h2, h3");
    if (cab) fontes.push(cab.textContent);
    for (const t of fontes) {
      const p = A.cnj(t);
      if (p) return p;
    }
    return "";
  }

  // endereço do RSPE desta página (null se não for a página de um processo de execução)
  function rspeDaPagina() {
    const r = A.rspeNoHtml(document.documentElement ? document.documentElement.innerHTML : "");
    return r ? A.urlRspeDoId(r.id, r.report) : "";
  }

  function emProcesso() {
    return /visualizacaoProcesso\.do/i.test(location.pathname);
  }

  function aviso(txt, erro) {
    chrome.runtime.sendMessage({ tipo: "cfg" }).then((c) => {
      if (!c || !c.avisoNaPagina || !document.body) return;
      let el = document.getElementById("apto-rspe-aviso");
      if (!el) {
        el = document.createElement("div");
        el.id = "apto-rspe-aviso";
        el.setAttribute("role", "status");
        el.style.cssText = "position:fixed;right:14px;bottom:14px;z-index:2147483000;max-width:360px;padding:8px 12px;border-radius:8px;" +
          "font:12px/1.35 system-ui,Segoe UI,Arial,sans-serif;box-shadow:0 6px 18px rgba(0,0,0,.18);pointer-events:none;transition:opacity .3s";
        document.body.appendChild(el);
      }
      el.style.background = erro ? "#FBEAEA" : "#E8F2EC";
      el.style.color = erro ? "#8E2424" : "#1D5A3B";
      el.style.border = "1px solid " + (erro ? "#E3B4B4" : "#B9D6C4");
      el.textContent = txt;
      el.style.opacity = "1";
      clearTimeout(el._t);
      el._t = setTimeout(() => { el.style.opacity = "0"; }, 6000);
    }).catch(() => {});
  }

  function base64(bytes) {
    let s = "";
    for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    return btoa(s);
  }

  // busca o PDF com a sessão do SEEU e manda ao service worker
  async function baixar(url, processo, forcar) {
    const pre = await chrome.runtime.sendMessage({ tipo: "podeBaixar", processo, forcar: !!forcar }).catch((e) => ({ ok: false, motivo: String(e) }));
    if (!pre || !pre.ok) return pre || { ok: false, motivo: "extensão indisponível" };
    let resp;
    try {
      resp = await fetch(url, { credentials: "include", cache: "no-store" });
    } catch (e) {
      return chrome.runtime.sendMessage({ tipo: "falha", processo, motivo: "o SEEU não respondeu (" + (e && e.message || e) + ")" });
    }
    const bytes = new Uint8Array(await resp.arrayBuffer());
    if (!resp.ok || !A.ehPdf(bytes)) {
      const motivo = !resp.ok ? "o SEEU respondeu com erro " + resp.status : "o SEEU não devolveu um PDF (sessão expirada?)";
      return chrome.runtime.sendMessage({ tipo: "falha", processo, motivo });
    }
    return chrome.runtime.sendMessage({ tipo: "rspePdf", processo, url, b64: base64(bytes), forcar: !!forcar });
  }

  async function procurar(forcar) {
    const processo = processoDaPagina();
    const url = rspeDaPagina();
    if (processo) chrome.runtime.sendMessage({ tipo: "processoVisto", processo, url }).catch(() => {});
    if (!url) return { achou: false, processo };
    if (pedido && !forcar) return { achou: true, processo, pedido: true };
    pedido = true;
    const r = await baixar(url, processo, forcar);
    if (r && r.ok) aviso("APTO: RSPE salvo em Downloads\\" + String(r.arquivo || "").replace(/\//g, "\\"));
    else if (r && !r.repetido && r.motivo !== "desligada") aviso("APTO: " + (r.motivo || "não foi possível salvar o RSPE"), true);
    return Object.assign({ achou: true, processo }, r || {});
  }

  chrome.runtime.onMessage.addListener((msg, _s, responder) => {
    if (msg.tipo === "procurar") {
      // só responde a moldura que tem o RSPE (as demais ficam em silêncio)
      if (!emProcesso() || !rspeDaPagina()) return false;
      procurar(!!msg.forcar).then(responder);
      return true;
    }
    if (msg.tipo === "aviso") aviso(msg.texto, msg.erro);
  });

  // automático: na página do processo, uma vez por carregamento (o SEEU recarrega a página a cada aba; o service worker
  // não repete o mesmo processo no mesmo dia)
  if (emProcesso()) {
    // guarda o nº do processo aberto (o RSPE aberto pelo botão "Situação Carcerária" é salvo com ele)
    const p0 = processoDaPagina();
    if (p0) chrome.runtime.sendMessage({ tipo: "processoVisto", processo: p0, url: rspeDaPagina() }).catch(() => {});
    const tentar = () => { if (rspeDaPagina()) { procurar(false); return true; } return false; };
    if (!tentar()) {
      const obs = new MutationObserver(() => { if (tentar()) obs.disconnect(); });
      obs.observe(document.documentElement, { childList: true, subtree: true });
      setTimeout(() => obs.disconnect(), 20000);
    }
  }
})();
