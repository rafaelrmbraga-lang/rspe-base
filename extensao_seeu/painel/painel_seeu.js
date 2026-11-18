// APTO - painel no SEEU: roda na página do processo (visualizacaoProcesso.do) e só acrescenta o painel à direita.
// Não clica, não navega, não abre aba nem janela e não muda nada do SEEU: o painel é uma moldura da própria extensão (estilo
// isolado do SEEU e do AZflow) e, aberto, reserva a sua largura na página (nada do SEEU fica coberto). Recolhido, vira
// uma lingueta na borda com a contagem do que pede atenção. O estado (aberto/recolhido) é lembrado.
(function () {
  "use strict";
  if (window.__aptoPainel) return;
  window.__aptoPainel = true;
  if (window.name === "apto-triagem-oculta") return;            // moldura invisível da Triagem da Mesa
  if (!/visualizacaoProcesso\.do/i.test(location.pathname)) return;
  const A = self.APTO;
  const LARG = 392;
  const ORIGEM = chrome.runtime.getURL("").replace(/\/$/, "");

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

  let host, raiz, moldura, lingueta, reserva, contagem = { crit: 0, urg: 0, med: 0 };

  function reservar(sim) {
    // a página do SEEU encolhe para dar lugar ao painel (nada dela fica embaixo dele)
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
      .lingueta{position:fixed;right:0;top:38%;width:38px;background:#1D5A3B;color:#fff;border:0;border-radius:8px 0 0 8px;padding:10px 0;
        display:flex;flex-direction:column;align-items:center;gap:8px;box-shadow:-3px 2px 10px rgba(0,0,0,.18);cursor:pointer;
        font:700 12.5px/1 "Source Sans 3","Segoe UI",system-ui,sans-serif}
      .lingueta:focus-visible{outline:3px solid #F2B705;outline-offset:2px}
      .v{writing-mode:vertical-rl;transform:rotate(180deg);letter-spacing:.12em}
      .n{background:#fff;border-radius:10px;font-size:11.5px;padding:2px 5px;min-width:16px;text-align:center}
      .c{color:#A3201D}.u{color:#9A4600}.m{color:#765C00}
      [hidden]{display:none!important}
      @media (prefers-reduced-motion:no-preference){.moldura{transition:transform .18s ease-out}}
    </style>
    <iframe class="moldura" title="Análise do APTO" hidden></iframe>
    <button class="lingueta" type="button" hidden></button>`;
    moldura = raiz.querySelector(".moldura");
    lingueta = raiz.querySelector(".lingueta");
    lingueta.addEventListener("click", () => abrir(true));
    moldura.src = chrome.runtime.getURL("painel/painel.html") + "#p=" + encodeURIComponent(processo);
    document.documentElement.appendChild(host);
  }

  function pintarLingueta() {
    const c = contagem;
    const partes = [["c", "◆", c.crit, "agir já"], ["u", "▲", c.urg, "em até 30 dias"], ["m", "●", c.med, "a conferir"]].filter((x) => x[2]);
    lingueta.innerHTML = `<span class="v">APTO</span>` + partes.map((x) => `<span class="n ${x[0]}" aria-hidden="true">${x[1]}${x[2]}</span>`).join("");
    lingueta.setAttribute("aria-label", "Abrir a análise do APTO" + (partes.length ? ": " + partes.map((x) => x[2] + " " + x[3]).join(", ") : ""));
  }

  async function abrir(sim) {
    moldura.hidden = !sim;
    lingueta.hidden = sim;
    reservar(sim);
    if (!sim) pintarLingueta();
    try { await chrome.storage.local.set({ painelAberto: sim }); } catch (e) { /* segue */ }
    if (!sim) lingueta.focus({ preventScroll: true });
  }

  // a moldura do painel (página da extensão) avisa: recolher e contagem para a lingueta
  window.addEventListener("message", (ev) => {
    if (ev.origin !== ORIGEM || !moldura || ev.source !== moldura.contentWindow) return;
    const d = ev.data || {};
    if (d.apto === "recolher") abrir(false);
    if (d.apto === "contagem" && d.c) { contagem = d.c; if (!lingueta.hidden) pintarLingueta(); }
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
