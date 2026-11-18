// APTO - ponte do painel de Atendimentos dentro do APTO. O painel foi escrito para a extensão (storage.local do navegador, abas do
// navegador, pasta escolhida no navegador); dentro do APTO ele roda numa moldura da aba e tudo isso passa pela janela do APTO
// (postMessage), que fala com o Python: a base do gabinete guarda os dados; a extensão, na aba do SAP, executa os pedidos.
// Tem de vir antes do comum.js (que usa globalThis.browser quando existe).
(function () {
  "use strict";
  if (window.parent === window) return; // aberto sozinho (teste): o comum.js imita o storage com o localStorage
  document.documentElement.dataset.theme = "light"; // o APTO é claro: o painel acompanha
  document.documentElement.classList.add("no-apto");

  let seq = 0;
  const esperando = new Map();
  function pedir(metodo, ...args) {
    return new Promise((ok, erro) => {
      const id = ++seq;
      esperando.set(id, { ok, erro });
      parent.postMessage({ apto: "atd", id, metodo, args }, "*");
    });
  }

  // cópia local dos dados (o Python avisa o que mudou: fila e Fato Narrado lidos no SAP)
  const COLS = ["atendimentos", "pecas"];
  let cache = null, carregando = null;
  const ouvintes = [];
  const clone = (x) => (x == null ? x : JSON.parse(JSON.stringify(x)));
  async function carregar() {
    if (cache) return cache;
    if (!carregando) carregando = pedir("atd_tudo").then((d) => { cache = d || {}; if (cache.sap) avisarSap(cache.sap); return cache; });
    return carregando;
  }
  function aplicar(d, notificar) {
    if (!cache || !d) return;
    const mud = {};
    for (const c of COLS) {
      if (!d[c]) continue;
      let L = cache[c] || (cache[c] = []);
      for (const r of d[c].upsert || []) {
        const i = L.findIndex((x) => x.id === r.id);
        if (i >= 0) L[i] = r; else L.push(r);
      }
      if (d[c].remover && d[c].remover.length) { const s = new Set(d[c].remover); L = cache[c] = L.filter((x) => !s.has(x.id)); }
      mud[c] = { newValue: clone(L) };
    }
    for (const k of ["ajustes", "modelos", "config"]) if (k in d) { cache[k] = clone(d[k]); mud[k] = { newValue: clone(d[k]) }; }
    if (notificar && Object.keys(mud).length) ouvintes.forEach((f) => { try { f(mud, "local"); } catch (e) { console.error(e); } });
  }

  let sapEstado = null;
  function avisarSap(est) { sapEstado = est; if (window.__atdSap) window.__atdSap(est); }

  window.addEventListener("message", (e) => {
    if (e.source !== parent) return;
    const m = e.data || {};
    if (m.apto !== "atd") return;
    if (m.id && esperando.has(m.id)) {
      const p = esperando.get(m.id);
      esperando.delete(m.id);
      if (m.erro) p.erro(new Error(m.erro)); else p.ok(m.r);
      return;
    }
    if (m.evento === "mudou") aplicar(m.dados, true);
    if (m.evento === "sap") avisarSap(m.dados);
    if (m.evento === "aba" && window.__atdAba) window.__atdAba(m.grupo, m.aba);
  });

  window.browser = {
    apto: true,
    storage: {
      local: {
        get: async (ks) => {
          const c = await carregar();
          const r = {};
          for (const k of [].concat(ks)) if (c[k] !== undefined && c[k] !== null) r[k] = clone(c[k]);
          return r;
        },
        // grava só o que mudou (cada atendimento e pendência é uma linha na base do gabinete)
        set: async (o) => {
          const c = await carregar();
          const diff = {};
          for (const k of Object.keys(o)) {
            if (COLS.includes(k)) {
              const antes = new Map((c[k] || []).map((x) => [x.id, JSON.stringify(x)]));
              const novos = o[k] || [];
              const ids = new Set(novos.map((x) => x.id));
              const d = { upsert: novos.filter((x) => antes.get(x.id) !== JSON.stringify(x)), remover: [...antes.keys()].filter((id) => !ids.has(id)) };
              if (d.upsert.length || d.remover.length) diff[k] = d;
            } else diff[k] = o[k];
          }
          if (!Object.keys(diff).length) return;
          aplicar(clone(diff), true);
          const r = await pedir("atd_mudar", diff);
          if (r && r.erro) throw new Error(r.erro);
        },
      },
      onChanged: { addListener: (f) => ouvintes.push(f) },
    },
    runtime: { id: "apto", getURL: (p) => "apto-arq:" + p, sendMessage: async () => null, onMessage: { addListener() {} } },
    tabs: { getCurrent: async () => null },
  };

  // arquivos do painel (modelo do Word, fontes, modelos de petição): fetch("apto-arq:...") vem do Python
  const fetch0 = window.fetch.bind(window);
  window.fetch = async (u, op) => {
    const s = String(u && u.url ? u.url : u);
    if (!s.startsWith("apto-arq:")) return fetch0(u, op);
    const r = await pedir("atd_arquivo", s.slice(9));
    if (!r || r.erro) return new Response(null, { status: 404, statusText: (r && r.erro) || "não encontrado" });
    const bin = atob(r.b64);
    const b = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) b[i] = bin.charCodeAt(i);
    return new Response(b, { status: 200 });
  };
  const paraB64 = (blob) => new Promise((ok, erro) => {
    const fr = new FileReader();
    fr.onload = () => ok(String(fr.result).split(",")[1] || "");
    fr.onerror = () => erro(fr.error);
    fr.readAsDataURL(blob);
  });

  window.ATD_APTO = {
    pedir,
    sap: () => sapEstado,
    // grava um arquivo pelo APTO; tipo "relatorio" (pasta do mês), "peticao" (pasta das petições) ou "" (pergunta onde salvar)
    async salvar(blob, nome, tipo, mes) {
      const b64 = await paraB64(blob);
      let r = await pedir("atd_salvar_arquivo", nome, b64, tipo || "", mes == null ? null : mes, false);
      if (r && r.existe) {
        if (confirm(`Já existe ${r.caminho}. Substituir?`)) r = await pedir("atd_salvar_arquivo", nome, b64, tipo || "", mes == null ? null : mes, true);
        else r = await pedir("atd_salvar_arquivo", nome.replace(/(\.\w+)$/, ` (${new Date().toTimeString().slice(0, 5).replace(":", "h")})$1`), b64, tipo || "", mes == null ? null : mes, false);
      }
      if (r && r.erro) throw new Error(r.erro);
      return r && r.ok ? r.caminho : "";
    },
    abrirLink: (url) => pedir("atd_abrir_link", url),
    ui: (acao, ...a) => pedir("ui:" + acao, ...a),
  };
})();
