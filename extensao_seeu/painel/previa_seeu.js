// APTO - prévia dos documentos do SEEU ao passar o mouse no link (arquivo.do, ex.: "online.pdf" no detalhe da movimentação): depois
// de um instante sobre o link (ou com o foco do teclado nele), abre um quadro flutuante ao lado, sem nova aba, com o documento que o
// link baixaria. Um GET por arquivo (o mesmo do clique), guardado enquanto a página estiver aberta; nada é gravado.
// O quadro: nome do arquivo, "Expandir" (ocupa a página, sem cobrir o painel, e não fecha ao tirar o mouse; "Reduzir" volta) e
// fechar; Esc fecha; sair do link e do quadro fecha (quando não expandido).
(function () {
  "use strict";
  if (window.__aptoPrevia) return;
  window.__aptoPrevia = true;
  if (window.name === "apto-triagem-oculta") return;
  const ORIGEM = chrome.runtime.getURL("").replace(/\/$/, "");
  const ESPERA_MS = 450, FECHA_MS = 350, MAX_CACHE = 8;
  const largura = () => Math.max(420, Math.min(760, window.innerWidth - (painelAberto() ? 432 : 0) - 48));
  const cache = new Map();
  let host, raiz, quadro, moldura, titulo, expandir, grande = false, pronta = false, fila = null, linkAtual = null, tAbrir = 0, tFechar = 0, ligado = true;

  const ehArquivo = (a) => a && a.tagName === "A" && /\/seeu\/arquivo\.do/i.test(a.getAttribute("href") || "") && !/^javascript:/i.test(a.getAttribute("href") || "");
  const painelAberto = () => !!document.getElementById("apto-painel-reserva");

  function montar() {
    if (host) return;
    host = document.createElement("div");
    host.id = "apto-previa";
    host.style.cssText = "all:initial;position:fixed;top:0;left:0;z-index:2147483001";
    raiz = host.attachShadow({ mode: "open" });
    raiz.innerHTML = `<style>
      :host{all:initial}
      .q{position:fixed;width:720px;height:min(84vh,920px);display:flex;flex-direction:column;background:#fff;border:1px solid #8C9399;border-radius:10px;
        box-shadow:0 12px 32px rgba(0,0,0,.22);overflow:hidden;font:12.5px/1.3 "Source Sans 3","Segoe UI",system-ui,sans-serif;color:#1E2226;
        opacity:0;transform:translateY(4px);transition:opacity .14s ease-out,transform .14s ease-out}
      .q.on{opacity:1;transform:none}
      .q.grande{width:auto;height:auto}
      @media (prefers-reduced-motion:reduce){.q{transition:none}}
      .cab{display:flex;align-items:center;gap:8px;padding:6px 8px 6px 12px;background:#1D5A3B;color:#fff}
      .cab b{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12.5px}
      .cab small{font-weight:600;opacity:.85;margin-left:6px}
      .bt{all:unset;box-sizing:border-box;display:inline-flex;align-items:center;justify-content:center;min-height:28px;padding:0 10px;border-radius:6px;
        background:rgba(255,255,255,.14);color:#fff;font-weight:700;font-size:12px;cursor:pointer}
      .bt:hover{background:rgba(255,255,255,.26)}
      .bt:focus-visible{outline:3px solid #F2B705;outline-offset:1px}
      .x{width:28px;padding:0}
      iframe{flex:1;width:100%;border:0;background:#E9ECEE}
      [hidden]{display:none!important}
    </style>
    <div class="q" role="dialog" aria-label="Prévia do documento" hidden>
      <div class="cab"><b><span id="t"></span><small id="n"></small></b><button type="button" class="bt" id="b" aria-pressed="false">Expandir</button>
        <button type="button" class="bt x" id="x" aria-label="Fechar a prévia (Esc)">✕</button></div>
      <iframe title="Prévia do documento"></iframe>
    </div>`;
    quadro = raiz.querySelector(".q");
    moldura = raiz.querySelector("iframe");
    titulo = raiz.getElementById("t");
    expandir = raiz.getElementById("b");
    moldura.src = chrome.runtime.getURL("painel/previa.html");
    raiz.getElementById("x").addEventListener("click", fechar);
    expandir.addEventListener("click", () => { if (linkAtual) ampliar(!grande); });
    quadro.addEventListener("mouseenter", () => clearTimeout(tFechar));
    quadro.addEventListener("mouseleave", () => { if (!grande) agendarFechar(); });
    document.documentElement.appendChild(host);
  }
  window.addEventListener("message", (ev) => {
    if (ev.origin !== ORIGEM || !moldura || ev.source !== moldura.contentWindow) return;
    if ((ev.data || {}).apto === "previaPronta") { pronta = true; if (fila) { enviar(fila); fila = null; } }
    if ((ev.data || {}).apto === "previaPaginas" && raiz) raiz.getElementById("n").textContent = ev.data.n ? "· " + ev.data.n + (ev.data.n === 1 ? " página" : " páginas") : "";
  });
  function enviar(d) {
    if (!pronta) { fila = d; return; }
    try { moldura.contentWindow.postMessage(Object.assign({ apto: "previa" }, d), ORIGEM, d.bytes ? [d.bytes] : []); } catch (e) { /* segue */ }
  }

  // expandido: ocupa a área da página (sem o painel), com margem; reduzido: volta ao lado do link
  function ampliar(sim) {
    grande = sim;
    quadro.classList.toggle("grande", sim);
    expandir.textContent = sim ? "Reduzir" : "Expandir";
    expandir.setAttribute("aria-pressed", String(sim));
    clearTimeout(tFechar);
    if (linkAtual) posicionar(linkAtual);
    if (moldura.contentWindow) enviar({ redimensionar: true });
  }
  function posicionar(a) {
    const LARG = largura();
    quadro.style.width = grande ? "auto" : LARG + "px";
    if (grande) {
      const dir = (painelAberto() ? 432 : 0) + 16;
      Object.assign(quadro.style, { left: "16px", top: "16px", right: dir + "px", bottom: "16px" });
      return;
    }
    Object.assign(quadro.style, { right: "", bottom: "" });
    const r = a.getBoundingClientRect();
    const limD = window.innerWidth - (painelAberto() ? 432 : 0) - 12;
    const alt = quadro.offsetHeight || Math.min(window.innerHeight * 0.72, 760);
    let x = r.right + 12;
    if (x + LARG > limD) x = r.left - LARG - 12;          // sem espaço à direita: à esquerda do link
    if (x < 12) x = Math.max(12, Math.min(limD - LARG, r.left));
    let y = Math.min(Math.max(12, r.top - 40), window.innerHeight - alt - 12);
    quadro.style.left = x + "px";
    quadro.style.top = Math.max(12, y) + "px";
  }

  // o arquivo.do do SEEU redireciona para o servidor de arquivos (S3), que a página não pode ler: quem busca é a extensão
  async function bytesDe(url) {
    if (cache.has(url)) return cache.get(url);
    const p = (async () => {
      const r = await chrome.runtime.sendMessage({ tipo: "seeuArquivo", url });
      if (!r || !r.ok) throw new Error((r && r.erro) || "a extensão não respondeu");
      const bin = atob(r.b64), b = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) b[i] = bin.charCodeAt(i);
      return { buf: b.buffer, tipo: r.tipo || "" };
    })();
    cache.set(url, p);
    p.catch(() => cache.delete(url));
    if (cache.size > MAX_CACHE) cache.delete(cache.keys().next().value);
    return p;
  }

  async function abrir(a) {
    if (!ligado) return;
    montar();
    linkAtual = a;
    titulo.textContent = (a.textContent || "").replace(/\s+/g, " ").trim() || "Documento";
    raiz.getElementById("n").textContent = "";
    quadro.hidden = false;
    posicionar(a);
    requestAnimationFrame(() => quadro.classList.add("on"));
    enviar({ carregando: true });
    try {
      const { buf, tipo } = await bytesDe(a.href);
      if (linkAtual !== a) return;
      enviar({ bytes: buf.slice(0), tipo });   // cópia: o original fica no cache
    } catch (e) {
      if (linkAtual === a) enviar({ erro: String((e && e.message) || e) });
    }
  }
  function fechar() {
    if (grande) ampliar(false);
    clearTimeout(tAbrir);
    clearTimeout(tFechar);
    linkAtual = null;
    if (quadro) { quadro.classList.remove("on"); quadro.hidden = true; }
  }
  function agendarFechar() {
    clearTimeout(tFechar);
    tFechar = setTimeout(fechar, FECHA_MS);
  }
  function quandoEntra(a) {
    if (grande) return;   // expandido: outro link não troca a prévia
    clearTimeout(tFechar);
    if (linkAtual === a) return;
    clearTimeout(tAbrir);
    tAbrir = setTimeout(() => abrir(a), ESPERA_MS);
  }

  document.addEventListener("mouseover", (e) => { const a = e.target.closest && e.target.closest("a"); if (ehArquivo(a)) quandoEntra(a); }, true);
  document.addEventListener("mouseout", (e) => {
    const a = e.target.closest && e.target.closest("a");
    if (!ehArquivo(a)) return;
    if (e.relatedTarget && a.contains(e.relatedTarget)) return;
    clearTimeout(tAbrir);
    if (linkAtual && !grande) agendarFechar();
  }, true);
  document.addEventListener("focusin", (e) => { if (ehArquivo(e.target)) quandoEntra(e.target); });
  document.addEventListener("focusout", (e) => { if (ehArquivo(e.target)) { clearTimeout(tAbrir); if (linkAtual && !grande) agendarFechar(); } });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && linkAtual) fechar(); });
  window.addEventListener("scroll", () => { if (linkAtual) posicionar(linkAtual); }, { passive: true });
  // opção "abrir os documentos no 2º monitor": o clique no link abre o documento numa janela no outro monitor (a mesma janela
  // é reaproveitada), em vez de baixar ou abrir aba nesta janela
  let monitor2 = false;
  document.addEventListener("click", (e) => {
    if (!monitor2 || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    const a = e.target.closest && e.target.closest("a");
    if (!ehArquivo(a)) return;
    e.preventDefault();
    e.stopPropagation();
    fechar();
    chrome.runtime.sendMessage({ tipo: "seeuAbrirDoc", url: a.href, nome: (a.textContent || "").trim() }).catch(() => {});
  }, true);
  chrome.runtime.sendMessage({ tipo: "cfg" }).then((c) => {
    if (c && (c.painel === false || c.ativo === false)) ligado = false;
    monitor2 = !!(c && c.docMonitor2);
  }).catch(() => {});
  chrome.storage.onChanged.addListener((ch, area) => { if (area === "local" && ch.cfg && ch.cfg.newValue) monitor2 = !!ch.cfg.newValue.docMonitor2; });
})();
