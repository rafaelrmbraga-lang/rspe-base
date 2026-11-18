// APTO - SEI da Defensoria (sei.defensoria.ms.def.br), na aba do SEI já logada pela pessoa:
//  1. guarda o endereço do Controle de Processos (cada link do SEI é assinado na sessão; a leitura começa dele);
//  2. atende o botão "Ler o SEI" do APTO: pergunta ao APTO a cada 3 s se há pedido e, quando há, lê o SEI DAQUI (mesma sessão,
//     mesma origem), com o leitor do NUSPEN (sei/lib/nucleo.js + adaptador_sei_dpms.js: só as quatro leituras, só GET). O que lê
//     vai para o APTO pelo service worker (o APTO deste computador, 127.0.0.1). Nada é clicado, digitado ou enviado ao SEI.
// Enquanto lê: deixe esta aba aberta e não navegue nela (a leitura para; o botão do APTO continua de onde parou).
(function () {
  "use strict";
  if (window.__aptoSeiAba || window !== window.top) return;
  window.__aptoSeiAba = true;
  const enviar = (m) => chrome.runtime.sendMessage(m).catch(() => null);
  const u = new URL(location.href);
  if (u.pathname === "/sei/controlador.php" && u.searchParams.get("acao") === "procedimento_controlar" && u.searchParams.get("infra_hash") &&
      document.getElementById("frmProcedimentoControlar")) {
    enviar({ tipo: "seiEntrada", url: location.href });
  }
  // só numa página do SEI com a sessão aberta (barra do sistema com "Sair")
  if (!document.getElementById("lnkInfraSairSistema") && !document.getElementById("frmProcedimentoControlar")) return;

  let lendo = null;
  let ultAviso = 0;
  function andamento(a, forcar) {
    const agora = Date.now();
    if (!forcar && agora - ultAviso < 1000) return;
    ultAviso = agora;
    enviar({ tipo: "seiAndamento", andamento: a });
  }
  function selo(txt) {
    let s = document.getElementById("apto-sei-selo");
    if (!s) {
      s = document.createElement("div");
      s.id = "apto-sei-selo";
      s.setAttribute("role", "status");
      s.style.cssText = "position:fixed;left:12px;bottom:12px;z-index:2147483646;background:#1D5A3B;color:#fff;font:600 12px/1.3 Segoe UI,Arial,sans-serif;" +
        "padding:7px 12px;border-radius:16px;box-shadow:0 2px 8px rgba(0,0,0,.25);max-width:520px";
      document.body.appendChild(s);
    }
    s.textContent = txt;
    s.hidden = !txt;
  }

  async function ler(cmd) {
    const base = chrome.runtime.getURL("sei/lib/");
    const N = await import(base + "nucleo.js");
    const { adaptadorSeiDpms: A } = await import(base + "adaptador_sei_dpms.js");
    const ent = await enviar({ tipo: "seiEntradaLer" });
    A.entrada = (ent && ent.url) || "";
    A.avisos = [];
    const cfg = (await enviar({ tipo: "seiConfig" })) || {};
    const controle = { pausado: false, cancelado: false };
    lendo = controle;
    // o "aplicativo" do NUSPEN é o APTO, alcançado pelo service worker (que põe o código de pareamento)
    const appFetch = async (url, op = {}) => {
      const r = await enviar({ tipo: "seiApp", caminho: String(url).replace(/^apto:/, ""), metodo: op.method || "GET", corpo: op.body || "" });
      if (!r || r.erro) throw new Error((r && r.erro) || "APTO indisponível");
      return { status: r.status, ok: r.status < 400, json: async () => r.json };
    };
    const leitor = N.criarLeitor({ baseSei: location.origin, adaptador: A, pausaMs: cfg.pausaMs ?? 600, limitePorMinuto: cfg.limitePorMinuto || 30,
      maxFalhasSeguidas: cfg.maxFalhasSeguidas || 3, controle });
    const base0 = { fase: "lendo", modo: cmd.modo || "todos", processos: 0, documentosLidos: 0, documentosPulados: 0, falhas: 0, novos: 0, modificados: 0, iniciadoEm: Date.now() };
    andamento(base0, true);
    selo("APTO: lendo o SEI… não navegue nesta aba até terminar");
    try {
      const r = await N.sincronizar({
        adaptador: A, leitor, app: { base: "apto:", baseSei: location.origin, token: "extensao", fetchImpl: appFetch },
        opcoes: { modo: cmd.modo || "todos", retomar: cmd.retomar || null },
        progresso: (p) => { andamento({ ...base0, ...p, fase: "lendo" }); selo(`APTO: lendo o SEI · ${p.processos || 0} processo(s), ${p.documentosLidos || 0} documento(s)… não navegue nesta aba`); },
      });
      andamento({ ...base0, ...r, fase: r.parada ? "parada" : "concluida", avisos: A.avisos.slice(), finalizadoEm: Date.now() }, true);
      selo(r.parada ? "APTO: leitura do SEI parou (" + (r.mensagemParada || r.parada) + ")" : `APTO: SEI lido · ${r.processos} processo(s), ${r.documentosLidos} documento(s) novo(s) ou alterado(s)`);
    } catch (e) {
      andamento({ ...base0, fase: "parada", erro: e.codigo || "desconhecido", mensagem: String(e.message || e), finalizadoEm: Date.now() }, true);
      selo("APTO: leitura do SEI parou: " + (e.message || e));
    } finally {
      lendo = null;
      setTimeout(() => selo(""), 15000);
    }
  }

  async function perguntar() {
    const r = await enviar({ tipo: "seiComando" });
    const c = r && r.cmd;
    if (!c) return;
    let resp;
    if (c.tipo === "pararSei") {
      if (lendo) lendo.cancelado = true;
      resp = { ok: true };
    } else if (c.tipo === "lerSei") {
      if (lendo) resp = { erro: "a leitura do SEI já está em andamento" };
      else {
        const ent = await enviar({ tipo: "seiEntradaLer" });
        if (!ent || !ent.url) resp = { erro: "abra o Controle de Processos no SEI (nesta aba) e clique de novo" };
        else { resp = { ok: true, iniciado: true }; setTimeout(() => ler(c), 0); }
      }
    } else resp = { erro: "pedido desconhecido" };
    await enviar({ tipo: "seiResposta", id: c.id, resposta: resp });
  }
  setInterval(perguntar, 3000);
  perguntar();
})();
