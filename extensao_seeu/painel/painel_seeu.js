// APTO - painel no SEEU: roda na página do processo (visualizacaoProcesso.do) e só ACRESCENTA o painel à direita.
// Não clica, não navega, não abre aba nem janela e não muda nada do SEEU: o painel é uma moldura da própria extensão (estilo
// isolado do SEEU e do AZflow) e, aberto, reserva a sua largura na página (nada do SEEU fica coberto). Recolhido, vira uma
// lingueta na borda com a contagem do que é para conferir. O estado (aberto/recolhido) é lembrado.
// Leitura (sem o APTO): o RSPE (Relatório da Situação Processual Executória) que o próprio SEEU gera para este processo - o
// link está na página - é buscado em segundo plano, nesta mesma aba e com a sessão de quem está logado: um único GET, o mesmo
// que o botão do relatório faz, sem abrir nada. O PDF vai para o motor da extensão, que o lê com o leitor do APTO.
(function () {
  "use strict";
  if (window.__aptoPainel) return;
  window.__aptoPainel = true;
  if (window.name === "apto-triagem-oculta") return;            // moldura invisível da Triagem da Mesa
  if (!/visualizacaoProcesso\.do/i.test(location.pathname)) return;
  const A = self.APTO;
  const LARG = 392;
  const ORIGEM = chrome.runtime.getURL("").replace(/\/$/, "");
  // ---------- número do processo
  function processoDaPagina() {
    const campo = document.getElementById("processoNumeroFormatado") || document.querySelector("input[name=processoNumeroFormatado]");
    const fontes = [campo && campo.value, document.title];
    const cab = document.querySelector("#informacoesProcessuais, .tituloProcesso, h1, h2, h3");
    if (cab) fontes.push(cab.textContent);
    if (document.body) fontes.push(document.body.innerText.slice(0, 4000));
    for (const t of fontes) {
      const p = A && A.cnj ? A.cnj(t) : "";
      if (p) return p;
    }
    return "";
  }

  // ---------- leitura do RSPE (só leitura: o relatório que o SEEU emite para o processo aberto)
  function base64(bytes) {
    let t = "";
    for (let i = 0; i < bytes.length; i += 0x8000) t += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    return btoa(t);
  }
  // diagnóstico sem dados pessoais: onde o painel roda, se o link do relatório foi achado, a resposta do SEEU (código, tipo,
  // tamanho) - nunca o número, o nome ou o conteúdo
  let lendo = null;
  async function lerRspe(progresso, novo) {
    if (lendo) return lendo;
    lendo = (async () => {
      const diag = { quadro: window === window.top ? "página" : "moldura", pagina: location.pathname };
      const rs = A.rspeNoHtml(document.documentElement ? document.documentElement.innerHTML : "");
      diag.link_rspe = !!rs;
      if (!rs) return { erro: "sem_link", diag };
      diag.relatorio = rs.report || "(padrão)";
      progresso("Gerando o relatório da situação processual no SEEU");
      let r;
      try { r = await A.buscarRspe(A.urlRspeDoId(rs.id, rs.report), novo); } catch (e) {
        diag.falha = String((e && e.message) || e).slice(0, 80);
        return { erro: "sem_resposta", diag };
      }
      const bytes = r.bytes;
      Object.assign(diag, { status: r.status, tipo: r.tipo.slice(0, 40), tamanho_kb: Math.round(bytes.length / 1024), pdf: A.ehPdf(bytes) });
      if (!r.ok || !A.ehPdf(bytes)) return { erro: r.ok ? "nao_pdf" : "http", diag };
      return { b64: base64(bytes), diag };
    })().finally(() => { lendo = null; });
    return lendo;
  }

  // ---------- chips na página: logo abaixo de "Execução nº" e, ao rolar, numa barra fixa no alto com o nº e o nome (copiar)
  const C = self.APTO_PAINEL_CORE;
  const CSS_CHIPS = `
    :host{all:initial}
    .faixa{display:flex;flex-wrap:wrap;align-items:center;gap:8px;font:13px/1.2 "Source Sans 3","Segoe UI",system-ui,sans-serif;color:#1E2226}
    .seg{display:inline-flex;flex-wrap:wrap;align-items:stretch;background:#fff;border:1px solid #C9CED2;border-radius:10px;overflow:hidden}
    .sg{all:unset;box-sizing:border-box;display:flex;flex-direction:column;justify-content:center;gap:2px;padding:4px 11px;min-height:38px;
      border-right:1px solid #E3E6E8;cursor:pointer}
    .sg:last-child{border-right:0}
    .sg:hover{background:#F2F4F5}
    .sg.reg{cursor:default;background:#EDF5F0}
    .sg.proximo{background:#FBF4DD;box-shadow:inset 0 3px 0 #C99A06}
    .sg.atingida{background:#E8F3EC;box-shadow:inset 0 3px 0 #1D7A4A}
    .sg[aria-expanded="true"]{background:#E6ECF1}
    .rot{font-size:10.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#5C636A;white-space:nowrap}
    .dt{font-size:13.5px;font-weight:700;font-variant-numeric:tabular-nums;white-space:nowrap;display:flex;align-items:center;gap:6px}
    .est{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border-radius:50%}
    .est.proximo{background:#F2E3A9;color:#5E4900}
    .est.atingida{background:#1D7A4A;color:#fff}
    .vh{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
    .bens{display:inline-flex;flex-wrap:wrap;gap:6px}
    .ben{all:unset;box-sizing:border-box;display:inline-flex;align-items:center;gap:6px;min-height:30px;padding:0 10px 0 8px;border-radius:999px;
      font-weight:700;font-size:12px;cursor:pointer;white-space:nowrap;border:1px solid}
    .ben.ok{background:#E8F3EC;color:#145232;border-color:#9FCDB2}
    .ben.ok:hover{background:#D9ECE0}
    .ben.q{background:#FBF4DD;color:#5E4900;border-color:#E0C766}
    .ben.q:hover{background:#F3E6BF}
    .ben:focus-visible{outline:3px solid #F2B705;outline-offset:2px}
    .mk{color:#8A6A00;margin-left:4px}
    .id{display:inline-flex;align-items:center;gap:6px;min-width:0}
    .num{font-weight:700;color:#B00000;font-variant-numeric:tabular-nums;white-space:nowrap}
    .nm{font-weight:600;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .cp,.conf{all:unset;box-sizing:border-box;display:inline-flex;align-items:center;gap:5px;min-height:30px;padding:0 9px;border-radius:8px;
      font-weight:700;font-size:12px;cursor:pointer;white-space:nowrap}
    .cp{border:1px solid #C9CED2;background:#fff;color:#1D5A3B}
    .cp:hover{background:#F0F6F2}
    .conf{border:1px solid #E0C766;background:#F8F0D8;color:#5E4900}
    .conf:hover{background:#F3E6BF}
    .conf b{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border-radius:50%;background:#8A6A00;color:#fff;font-size:11px}
    .sg:focus-visible,.cp:focus-visible,.conf:focus-visible{outline:3px solid #F2B705;outline-offset:2px}
    .det{margin-top:6px;padding:6px 10px;background:#fff;border:1px solid #C9CED2;border-left:3px solid #1D5A3B;border-radius:8px;font:12.5px/1.45 "Source Sans 3","Segoe UI",system-ui,sans-serif;color:#454B50;max-width:760px}
    [hidden]{display:none!important}`;
  let chipsHost = null, chipsRaiz = null, barra = null, dadosC = null, observador = null, fixaVisivel = false;
  function ancoraDosChips() {
    return document.getElementById("barraTituloStatusProcessual") || document.querySelector(".titulo.processo");
  }
  function ligarChips(raizC) {
    raizC.addEventListener("click", async (e) => {
      const sg = e.target.closest("[data-chip]");
      if (sg) {
        const aberto = sg.getAttribute("aria-expanded") === "true";
        raizC.querySelectorAll("[data-chip]").forEach((b) => b.setAttribute("aria-expanded", "false"));
        raizC.querySelectorAll("[data-det]").forEach((x) => { x.hidden = true; });
        if (!aberto) { sg.setAttribute("aria-expanded", "true"); const x = raizC.querySelector(`[data-det="${sg.dataset.chip}"]`); if (x) x.hidden = false; }
        return;
      }
      const cp = e.target.closest("[data-copiar]");
      if (cp && dadosC) {
        const ok = await copiarTexto(cp.dataset.copiar === "nome" ? dadosC.nome : dadosC.processo);
        const sp = cp.querySelector("span"), antes = sp.textContent;
        sp.textContent = ok ? "Copiado" : "Não copiou";
        setTimeout(() => { sp.textContent = antes; }, 1600);
        return;
      }
      const fo = e.target.closest("[data-focar]");
      if (fo) { await abrir(true); paraPainel({ apto: "focar", id: fo.dataset.focar }); return; }
      if (e.target.closest("[data-abrir]")) abrir(true);
    });
  }
  async function copiarTexto(t) {
    try { await navigator.clipboard.writeText(t); return true; } catch (e) { /* cópia de reserva */ }
    const el = document.createElement("textarea");
    el.value = t;
    el.setAttribute("readonly", "");
    el.style.cssText = "position:fixed;left:-9999px;top:0";
    document.body.appendChild(el);
    el.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    el.remove();
    return ok;
  }
  function mostrarFixa(sim) {
    fixaVisivel = sim;
    if (barra) barra.classList.toggle("on", sim && !!dadosC);
    if (barra) barra.inert = !(sim && dadosC);
  }
  function pintarChips(d) {
    dadosC = d && (d.marcos || []).length ? d : null;
    if (!dadosC) {
      if (chipsHost) { chipsHost.remove(); chipsHost = null; }
      if (barra) barra.innerHTML = "";
      mostrarFixa(false);
      return;
    }
    const anc = ancoraDosChips();
    if (anc && !chipsHost) {
      chipsHost = document.createElement("div");
      chipsHost.id = "apto-chips";
      chipsHost.style.cssText = "all:initial;display:block;margin:6px 0 6px";
      chipsRaiz = chipsHost.attachShadow({ mode: "open" });   // o que está nela já está à vista na tela
      ligarChips(chipsRaiz);
      anc.insertAdjacentElement("afterend", chipsHost);
      if (observador) observador.disconnect();
      observador = new IntersectionObserver((ents) => mostrarFixa(!ents[0].isIntersecting), { threshold: 0 });
      observador.observe(chipsHost);
    }
    if (chipsRaiz) chipsRaiz.innerHTML = `<style>${CSS_CHIPS}</style>` + C.chips(dadosC, false);
    desviar();
    if (barra) barra.innerHTML = C.chips(dadosC, true);
    if (!chipsHost) mostrarFixa(window.scrollY > 120);   // sem o cabeçalho do SEEU: a barra fixa aparece ao rolar
    else mostrarFixa(fixaVisivel);
  }
  window.addEventListener("scroll", () => { if (!chipsHost && dadosC) mostrarFixa(window.scrollY > 120); }, { passive: true });
  // a faixa não passa por baixo do que o SEEU posiciona à direita do cabeçalho (o gráfico da pena cumprida): mede e recua
  function desviar() {
    if (!chipsHost || !chipsHost.parentElement) return;
    chipsHost.style.marginRight = "0px";
    const h = chipsHost.getBoundingClientRect();
    let recuo = 0;
    const caixa = chipsHost.parentElement.closest("div,section,td,body") || document.body;
    for (const el of caixa.querySelectorAll("*")) {
      if (el === chipsHost || el.contains(chipsHost)) continue;
      const cs = getComputedStyle(el);
      if (cs.position !== "absolute" && cs.float !== "right") continue;
      const r = el.getBoundingClientRect();
      if (!r.width || r.bottom <= h.top || r.top >= h.bottom + 60 || r.left <= h.left + 200) continue;
      recuo = Math.max(recuo, h.right - r.left + 12);
    }
    if (recuo > 0) chipsHost.style.marginRight = recuo + "px";
  }
  window.addEventListener("resize", () => desviar());

  // ---------- painel (moldura da extensão) e lingueta
  let host, raiz, moldura, lingueta, reserva, contagem = { verde: 0, amarelo: 0 };
  function reservar(sim) {
    if (sim && !reserva) {
      reserva = document.createElement("style");
      reserva.id = "apto-painel-reserva";
      reserva.textContent = "html{margin-right:" + LARG + "px !important}";
      (document.head || document.documentElement).appendChild(reserva);
    } else if (!sim && reserva) {
      reserva.remove();
      reserva = null;
    }
  }
  function montar(processo) {
    host = document.createElement("div");
    host.id = "apto-painel";
    host.style.cssText = "all:initial;position:fixed;top:0;right:0;z-index:2147483000";
    raiz = host.attachShadow({ mode: "closed" });
    raiz.innerHTML = `<style>
      :host{all:initial}
      .moldura{position:fixed;top:0;right:0;height:100vh;width:${LARG}px;border:0;border-left:1px solid #8C9399;background:#F5F6F6;
        box-shadow:-6px 0 18px rgba(0,0,0,.08)}
      .lingueta{position:fixed;right:0;top:38%;width:38px;min-height:44px;background:#1D5A3B;color:#fff;border:0;border-radius:8px 0 0 8px;padding:10px 0;
        display:flex;flex-direction:column;align-items:center;gap:8px;box-shadow:-3px 2px 10px rgba(0,0,0,.18);cursor:pointer;
        font:700 12.5px/1 "Source Sans 3","Segoe UI",system-ui,sans-serif}
      .lingueta:hover{background:#153F2A}
      .lingueta:focus-visible{outline:3px solid #F2B705;outline-offset:2px}
      .selo{display:block;width:30px;height:30px;border-radius:50%;background:#fff}
      .n{background:#F8F0D8;color:#765C00;border-radius:10px;font-size:11.5px;padding:2px 5px;min-width:16px;text-align:center}

      [hidden]{display:none!important}
    </style>
    <iframe class="moldura" title="Análise do APTO" allow="clipboard-write" hidden></iframe>
    <button class="lingueta" type="button" hidden></button>`;
    moldura = raiz.querySelector(".moldura");
    lingueta = raiz.querySelector(".lingueta");
    lingueta.addEventListener("click", () => abrir(true));
    const bh = document.createElement("div");
    bh.id = "apto-barra";
    bh.style.cssText = "all:initial";
    const br = bh.attachShadow({ mode: "open" });
    br.innerHTML = `<style>${CSS_CHIPS}
      .barra{position:fixed;top:0;left:0;right:0;z-index:2147482999;padding:6px 14px;background:rgba(245,246,246,.97);border-bottom:1px solid #C9CED2;
        box-shadow:0 4px 12px rgba(0,0,0,.08);transform:translateY(-115%);transition:transform .18s ease-out;visibility:hidden}
      .barra.on{transform:none;visibility:visible}
      .barra.com-painel{right:${LARG}px}
      @media (prefers-reduced-motion:reduce){.barra{transition:none}}</style>
      <div class="barra" role="region" aria-label="Processo e marcos (APTO)"></div>`;
    barra = br.querySelector(".barra");
    barra.inert = true;
    ligarChips(br);
    document.documentElement.appendChild(bh);
    moldura.src = chrome.runtime.getURL("painel/painel.html") + "#p=" + encodeURIComponent(processo);
    document.documentElement.appendChild(host);
  }
  function pintarLingueta() {
    const a = contagem.amarelo || 0;
    lingueta.innerHTML = `<img class="selo" src="${chrome.runtime.getURL("icones/128.png")}" alt="" width="30" height="30">` + (a ? `<span class="n" aria-hidden="true">!${a}</span>` : "");
    lingueta.setAttribute("aria-label", "Abrir a análise do APTO" + (a ? ": " + a + (a === 1 ? " ponto" : " pontos") + " para conferir" : ""));
  }
  async function abrir(sim) {
    moldura.hidden = !sim;
    lingueta.hidden = sim;
    barra.classList.toggle("com-painel", sim);
    requestAnimationFrame(() => desviar());
    reservar(sim);
    if (!sim) pintarLingueta();
    try { await chrome.storage.local.set({ painelAberto: sim }); } catch (e) { /* segue */ }
    if (!sim) lingueta.focus({ preventScroll: true });
  }
  const paraPainel = (d) => { try { moldura.contentWindow.postMessage(d, ORIGEM); } catch (e) { /* segue */ } };

  // a moldura pede o relatório (ao abrir, sem resultado guardado, ou no "Ler de novo"), recolhe e manda a contagem
  window.addEventListener("message", async (ev) => {
    if (ev.origin !== ORIGEM || !moldura || ev.source !== moldura.contentWindow) return;
    const d = ev.data || {};
    if (d.apto === "recolher") abrir(false);
    if (d.apto === "contagem" && d.c) { contagem = d.c; if (!lingueta.hidden) pintarLingueta(); }
    if (d.apto === "chips") pintarChips(d.d || null);
    if (d.apto === "lerRspe") {
      let x;
      try { x = await lerRspe((etapa) => paraPainel({ apto: "progresso", etapa }), !!d.novo); } catch (e) { x = { erro: "falha", diag: { falha: String((e && e.message) || e).slice(0, 80) } }; }
      paraPainel(Object.assign({ apto: "rspe" }, x));
    }
  });

  async function iniciar() {
    const c = await chrome.runtime.sendMessage({ tipo: "cfg" }).catch(() => null);
    if (c && (c.painel === false || c.ativo === false)) return;
    const processo = processoDaPagina();
    if (!processo) return;   // página sem número de processo (erro, sessão expirada): nada a mostrar
    montar(processo);
    let aberto = true;
    try { const g = await chrome.storage.local.get("painelAberto"); if (g.painelAberto === false) aberto = false; } catch (e) { /* segue */ }
    pintarLingueta();
    abrir(aberto);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar, { once: true });
  else iniciar();
})();
