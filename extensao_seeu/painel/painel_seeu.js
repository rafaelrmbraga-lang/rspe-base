// APTO - painel no SEEU: roda na página do processo (visualizacaoProcesso.do) e só ACRESCENTA o painel à direita.
// Não clica, não navega, não abre aba nem janela e não muda nada do SEEU: o painel é uma moldura da própria extensão (estilo
// isolado do SEEU e do AZflow) e, aberto, reserva a sua largura na página (nada do SEEU fica coberto). Recolhido, vira uma
// lingueta na borda com a contagem do que é para conferir. O estado (aberto/recolhido) é lembrado.
// Leitura (sem o APTO): as abas do processo são buscadas em segundo plano, nesta mesma aba e com a sessão de quem está
// logado - só GET, só endereços de leitura do SEEU, um pedido por vez com intervalo - e o HTML vai para o motor da extensão.
(function () {
  "use strict";
  if (window.__aptoPainel) return;
  window.__aptoPainel = true;
  if (window.name === "apto-triagem-oculta") return;            // moldura invisível da Triagem da Mesa
  if (!/visualizacaoProcesso\.do/i.test(location.pathname)) return;
  const A = self.APTO;
  const LARG = 392;
  const ORIGEM = chrome.runtime.getURL("").replace(/\/$/, "");
  const INTERVALO_MS = 350;   // entre dois pedidos ao SEEU
  const MAX_CRIM = 30;        // páginas de processo criminal por leitura

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

  // ---------- leitura das abas (só leitura)
  const ABAS = { gerais: /^Informa[çc][õo]es Gerais/i, adicionais: /^Informa[çc][õo]es Adicionais/i, partes: /^Partes\b/i,
    criminais: /^Processos Criminais/i, eventos: /^Eventos\b/i, concedidos: /^Incidentes Concedidos/i,
    nao_concedidos: /^Incidentes N[ãa]o.?Concedidos/i, pendentes: /^Incidentes Pendentes/i };
  const BLOQUEADO = /preAnalise|leitura|dispensar|assinar|movimentar|peticion|juntar|salvar|excluir|remover|alterar|atualizar|cadastr|enviar|devolver|descartar|arquivar/i;

  function permitido(url) {
    try {
      const u = new URL(url, location.href);
      return u.origin === location.origin && u.pathname.startsWith("/seeu/") && /\.do$/i.test(u.pathname) && !BLOQUEADO.test(u.pathname + u.search);
    } catch (e) { return false; }
  }
  // endereço de uma aba a partir do próprio link da página (href, ou o endereço dentro do onclick, ou o id "tabXxx")
  function urlDoLink(a) {
    const h = a.getAttribute("href") || "";
    if (h && !/^(#|javascript:)/i.test(h)) return new URL(h, location.href).href;
    const oc = a.getAttribute("onclick") || "";
    const m = /['"]([^'"]*\.do\?[^'"]*)['"]/.exec(oc);
    if (m) return new URL(m[1], location.href).href;
    const id = (a.id || a.getAttribute("data-tab") || (/(tab[A-Z]\w+)/.exec(oc + " " + h) || [])[1] || "");
    if (/^tab[A-Z]\w+$/.test(id)) return new URL("/seeu/visualizacaoProcesso.do?actionType=visualizar&selectedIcon=" + id, location.href).href;
    return "";
  }
  function linksDasAbas(doc) {
    const out = {};
    for (const a of doc.querySelectorAll("a")) {
      const t = (a.textContent || "").replace(/\s+/g, " ").trim();
      for (const [k, rx] of Object.entries(ABAS)) if (!out[k] && rx.test(t)) { const u = urlDoLink(a); if (u && permitido(u)) out[k] = u; }
    }
    return out;
  }
  const espera = (ms) => new Promise((r) => setTimeout(r, ms));
  async function buscar(url) {
    if (!permitido(url)) throw new Error("endereço fora da leitura permitida");
    const r = await fetch(url, { credentials: "include", cache: "no-store" });
    if (!r.ok) throw new Error("o SEEU respondeu " + r.status);
    const buf = await r.arrayBuffer();
    const cs = (/charset=([\w-]+)/i.exec(r.headers.get("content-type") || "") || [])[1];
    try { return new TextDecoder(cs || "utf-8", { fatal: !cs }).decode(buf); } catch (e) { return new TextDecoder("windows-1252").decode(buf); }
  }
  let lendo = null;
  async function lerAbas(progresso) {
    if (lendo) return lendo;
    lendo = (async () => {
      const abas = { capa: document.documentElement.outerHTML };
      const links = linksDasAbas(document);
      const chaves = Object.keys(ABAS).filter((k) => links[k]);
      let n = 0;
      for (const k of chaves) {
        progresso("Lendo as abas do processo (" + (++n) + " de " + chaves.length + ")");
        try { abas[k] = await buscar(links[k]); } catch (e) { /* aba que falhou fica de fora: o leitor diz o que faltou */ }
        await espera(INTERVALO_MS);
      }
      if (abas.criminais) {
        const doc = new DOMParser().parseFromString(abas.criminais, "text/html");
        const urls = [...doc.querySelectorAll("a")].filter((a) => /^Processo Criminal\b/i.test((a.textContent || "").trim()))
          .map(urlDoLink).filter((u) => u && permitido(u)).slice(0, MAX_CRIM);
        let i = 0;
        for (const u of urls) {
          progresso("Lendo os processos criminais (" + (i + 1) + " de " + urls.length + ")");
          try { abas["crim:" + (++i)] = await buscar(u); } catch (e) { /* processo que falhou fica de fora */ }
          await espera(INTERVALO_MS);
        }
      }
      return abas;
    })().finally(() => { lendo = null; });
    return lendo;
  }

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
      .v{writing-mode:vertical-rl;transform:rotate(180deg);letter-spacing:.12em}
      .n{background:#F8F0D8;color:#765C00;border-radius:10px;font-size:11.5px;padding:2px 5px;min-width:16px;text-align:center}
      [hidden]{display:none!important}
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
    const a = contagem.amarelo || 0;
    lingueta.innerHTML = `<span class="v">APTO</span>` + (a ? `<span class="n" aria-hidden="true">!${a}</span>` : "");
    lingueta.setAttribute("aria-label", "Abrir a análise do APTO" + (a ? ": " + a + (a === 1 ? " ponto" : " pontos") + " para conferir" : ""));
  }
  async function abrir(sim) {
    moldura.hidden = !sim;
    lingueta.hidden = sim;
    reservar(sim);
    if (!sim) pintarLingueta();
    try { await chrome.storage.local.set({ painelAberto: sim }); } catch (e) { /* segue */ }
    if (!sim) lingueta.focus({ preventScroll: true });
  }
  const paraPainel = (d) => { try { moldura.contentWindow.postMessage(d, ORIGEM); } catch (e) { /* segue */ } };

  // a moldura pede as abas (ao abrir, sem resultado guardado, ou no "Ler de novo"), recolhe e manda a contagem
  window.addEventListener("message", async (ev) => {
    if (ev.origin !== ORIGEM || !moldura || ev.source !== moldura.contentWindow) return;
    const d = ev.data || {};
    if (d.apto === "recolher") abrir(false);
    if (d.apto === "contagem" && d.c) { contagem = d.c; if (!lingueta.hidden) pintarLingueta(); }
    if (d.apto === "lerAbas") {
      try {
        const abas = await lerAbas((etapa) => paraPainel({ apto: "progresso", etapa }));
        paraPainel({ apto: "abas", abas });
      } catch (e) {
        paraPainel({ apto: "abas", abas: null, erro: String((e && e.message) || e) });
      }
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
