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
    <iframe class="moldura" title="Análise do APTO" allow="clipboard-write" hidden></iframe>
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

  // a moldura pede o relatório (ao abrir, sem resultado guardado, ou no "Ler de novo"), recolhe e manda a contagem
  window.addEventListener("message", async (ev) => {
    if (ev.origin !== ORIGEM || !moldura || ev.source !== moldura.contentWindow) return;
    const d = ev.data || {};
    if (d.apto === "recolher") abrir(false);
    if (d.apto === "contagem" && d.c) { contagem = d.c; if (!lingueta.hidden) pintarLingueta(); }
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
