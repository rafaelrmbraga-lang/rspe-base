// APTO - Painel do SEI (sei.defensoria.ms.def.br). Ao abrir o Controle de Processos, mostra no topo um painel com os números da
// unidade (não visualizados, prazos vencidos e vencendo, urgentes, sem atribuição, monitorados), a divisão por categoria, tipo,
// marcador e atribuição, busca rápida, atalhos do menu e os processos visitados; e marca cada linha da lista com ícones: categoria,
// prazo, urgente, anotação à vista, monitorar e copiar o número.
// SÓ APARÊNCIA: lê o que a página já mostra; não faz pedido ao SEI, não clica, não digita, não envia nada. Filtrar esconde linhas
// só na tela (recarregar volta tudo). Monitorados, histórico e preferências ficam neste navegador (chrome.storage.local).
// Motor (contas, prazo, categoria, filtros, planilha): sei_painel_core.js.
(function () {
  "use strict";
  if (window.__aptoSeiPainel) return;
  window.__aptoSeiPainel = true;
  const C = globalThis.AptoSeiPainel;
  if (!C) return;

  const st = {
    async get(k) { try { return await chrome.storage.local.get(k); } catch (e) { return {}; } },
    async set(o) { try { await chrome.storage.local.set(o); } catch (e) { /* sem storage: só não guarda */ } },
  };
  const acao = new URL(location.href).searchParams.get("acao") || "";

  // ---------- ícones (SVG próprios, 16x16, traço na cor atual) ----------
  const P = {
    balanca: '<path d="M8 2v12M4 14h8M3 4h10M3 4l-2 5h4zM13 4l-2 5h4z"/><path d="M1 9a2 2 0 0 0 4 0M11 9a2 2 0 0 0 4 0"/>',
    predio: '<path d="M2 14V5l6-3 6 3v9z"/><path d="M5 14V8M8 14V8M11 14V8M1 14h14"/>',
    pessoa: '<circle cx="8" cy="5" r="3"/><path d="M2 15c.6-3.4 3-5 6-5s5.4 1.6 6 5"/>',
    envelope: '<rect x="1.5" y="3.5" width="13" height="9" rx="1"/><path d="M2 4.5l6 4.5 6-4.5"/>',
    pasta: '<path d="M1.5 4.5v8a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1v-6a1 1 0 0 0-1-1H8L6.5 3.5h-4a1 1 0 0 0-1 1z"/>',
    documento: '<path d="M3.5 1.5h6l3 3v10h-9z"/><path d="M9.5 1.5v3h3M5.5 8h5M5.5 11h5"/>',
    etiqueta: '<path d="M1.5 8.5V2.5a1 1 0 0 1 1-1h6l6 6-7 7z"/><circle cx="5" cy="5" r="1.2"/>',
    relogio: '<circle cx="8" cy="8" r="6.5"/><path d="M8 4v4l3 2"/>',
    alvo: '<circle cx="8" cy="8" r="6.5"/><circle cx="8" cy="8" r="3.5"/><circle cx="8" cy="8" r=".8" fill="currentColor"/>',
    alerta: '<path d="M8 1.5l7 12.5H1z"/><path d="M8 6v4M8 12v.5"/>',
    copiar: '<rect x="5" y="5" width="9" height="9" rx="1"/><path d="M11 5V2.5a1 1 0 0 0-1-1H2.5a1 1 0 0 0-1 1V10a1 1 0 0 0 1 1H5"/>',
    nota: '<path d="M2.5 1.5h11v8l-4 4h-7z"/><path d="M13.5 9.5h-4v4M5 5h6M5 7.5h4"/>',
    olho: '<path d="M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5z"/><circle cx="8" cy="8" r="2"/>',
    lista: '<path d="M5 4h9M5 8h9M5 12h9"/><circle cx="2" cy="4" r=".8" fill="currentColor"/><circle cx="2" cy="8" r=".8" fill="currentColor"/><circle cx="2" cy="12" r=".8" fill="currentColor"/>',
    pessoaX: '<circle cx="7" cy="5" r="3"/><path d="M1 15c.6-3.4 3-5 6-5 1.3 0 2.5.3 3.4.9M11 11l4 4M15 11l-4 4"/>',
    seta: '<path d="M4 6l4 4 4-4"/>',
    planilha: '<rect x="1.5" y="2.5" width="13" height="11" rx="1"/><path d="M1.5 6h13M1.5 9.5h13M6 2.5v11"/>',
    ordem: '<path d="M4 2v12M1.5 11.5L4 14l2.5-2.5M10 4h5M10 8h4M10 12h3"/>',
    lua: '<path d="M13.5 10A6 6 0 0 1 6 2.5 6 6 0 1 0 13.5 10z"/>',
    caneta: '<path d="M10.5 2.5l3 3-8 8H2.5v-3z"/>',
    lupa: '<circle cx="7" cy="7" r="5"/><path d="M11 11l3.5 3.5"/>',
    historico: '<path d="M2 8a6 6 0 1 0 1.8-4.3M2 2v3.5h3.5"/><path d="M8 5v3l2 1.5"/>',
  };
  const svg = (n, t) => `<svg viewBox="0 0 16 16" width="${t || 14}" height="${t || 14}" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[n] || P.documento}</svg>`;
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // ---------- tema escuro (todas as páginas e molduras do SEI) ----------
  function aplicarTema(cfg) {
    const id = "apto-sei-tema";
    let s = document.getElementById(id);
    if (!cfg.ligado || !cfg.temaEscuro) { if (s) s.remove(); return; }
    if (!s) {
      s = document.createElement("style");
      s.id = id;
      // inverte a página e desinverte imagens e o painel do APTO (que tem o próprio tema escuro)
      s.textContent = "html{filter:invert(.9) hue-rotate(180deg);background:#fff}img,svg image,video,iframe,#apto-sei-painel,.apto-deco{filter:invert(1) hue-rotate(180deg)}";
      (document.head || document.documentElement).appendChild(s);
    }
  }

  // ---------- leitura da linha do Controle de Processos ----------
  function lerLinha(tr) {
    const a = tr.querySelector("a.processoVisualizado, a.processoNaoVisualizado, a[class*='processoVisualizado'], a[class*='processoNaoVisualizado']");
    if (!a) return null;
    const [espec, tipoDica] = C.argsDica(a.getAttribute("onmouseover") || "");
    const cel = (r) => [...tr.querySelectorAll("td")].find((td) => (td.getAttribute("data-label") || "").trim() === r);
    const sigla = tr.querySelector("a.ancoraSigla, a[class*='ancoraSigla']");
    const p = {
      numero: a.textContent.trim(), href: a.getAttribute("href") || "", naoVisualizado: /processoNaoVisualizado/.test(a.className),
      especificacao: espec || (a.getAttribute("aria-label") || "").split(" / ")[0] || "",
      tipo: (cel("Tipo") ? cel("Tipo").textContent.trim() : "") || tipoDica || "",
      atribuicao: (cel("Atribuição") ? cel("Atribuição").textContent.trim() : "") || (sigla ? (sigla.textContent || "").trim() : ""),
      atribuicaoNome: sigla ? sigla.getAttribute("title") || "" : "",
      interessados: cel("Interessados") ? [...cel("Interessados").querySelectorAll("div")].map((d) => d.textContent.trim()).filter(Boolean) : [],
      marcadores: [], anotacao: "", anotacaoPrioridade: false, prazos: [], retornos: [], dicas: [],
    };
    for (const el of tr.querySelectorAll("[onmouseover], [title]")) {
      if (el === a || el.closest(".apto-deco")) continue;
      const om = el.getAttribute("onmouseover") || "";
      const args = /infraTooltipMostrar/.test(om) ? C.argsDica(om) : [el.getAttribute("title") || ""];
      const [txt, rot] = [args[0] || "", args[1] || ""];
      const img = el.tagName === "IMG" ? el : el.querySelector("img");
      const src = img ? img.getAttribute("src") || "" : "";
      const tudo = (src + " " + rot + " " + txt.slice(0, 20)).toLowerCase();
      if (/marcador/.test(tudo)) {
        const nome = (rot && !/^marcador$/i.test(rot) ? rot : txt).replace(/^marcador:\s*/i, "").trim();
        if (nome) p.marcadores.push({ nome, texto: rot && !/^marcador$/i.test(rot) ? txt : "", src });
      } else if (/anota/.test(tudo)) {
        p.anotacao = txt || rot; p.anotacaoPrioridade = /prioridade/.test(tudo);
      } else if (/prazo/.test(tudo)) p.prazos.push(txt + " " + rot);
      else if (/retorno/.test(tudo)) p.retornos.push(txt + " " + rot);
      else if (txt || rot) p.dicas.push((rot + " " + txt).trim());
    }
    return p;
  }

  // ---------- estilos das linhas (fora do painel, prefixo apto-) ----------
  const CSS_LINHA = `
  tr.apto-oculto{display:none!important}
  tr.apto-urgente>td{background:#FDECEC!important}
  .apto-deco{display:inline-flex;align-items:center;gap:4px;margin-left:6px;vertical-align:middle;font:600 11px/1 "Segoe UI",system-ui,Arial,sans-serif}
  .apto-deco .ic{display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:6px;color:#fff}
  .apto-deco .pz{display:inline-flex;align-items:center;gap:3px;padding:3px 7px;border-radius:10px;white-space:nowrap}
  .apto-deco .pz.vencido{background:#B42318;color:#fff}.apto-deco .pz.critico{background:#F79009;color:#fff}
  .apto-deco .pz.alerta{background:#FEF0C7;color:#93370D}.apto-deco .pz.ok{background:#E8F2EC;color:#1D5A3B}.apto-deco .pz.parado{background:#EEF1EF;color:#5C6660}
  .apto-deco .urg{color:#B42318;animation:aptoPulsa 1.4s ease-in-out infinite}
  @keyframes aptoPulsa{50%{opacity:.35}}
  .apto-deco button{all:unset;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:6px;color:#8E958F}
  .apto-deco button:hover{background:#EEF1EF;color:#1D5A3B}.apto-deco button.on{color:#B42318}
  .apto-deco button:focus-visible{outline:2px solid #1D5A3B}
  .apto-esp{display:block;margin-top:2px;font:12px/1.3 "Segoe UI",system-ui,Arial,sans-serif;color:#5C6660;max-width:520px}
  .apto-nota{display:block;box-sizing:border-box;margin-top:4px;padding:4px 8px 0;max-width:520px;border-left:3px solid #F5B400;background:#FFF8E1;color:#5B4300;border-radius:4px;
    font:12px/1.35 "Segoe UI",system-ui,Arial,sans-serif;white-space:pre-wrap;max-height:calc(2.7em + 4px);overflow:hidden;cursor:pointer}
  .apto-nota.aberta{max-height:none;padding-bottom:4px}.apto-nota.prioridade{border-color:#B42318;background:#FDECEC;color:#7A1A12}
  .apto-copiado{position:fixed;z-index:2147483647;left:50%;bottom:24px;transform:translateX(-50%);background:#1E2A24;color:#fff;padding:8px 14px;border-radius:16px;font:600 12px "Segoe UI",Arial,sans-serif}`;

  // ---------- o painel (Shadow DOM: o estilo do SEI não entra, o do painel não sai) ----------
  const CSS_PAINEL = `
  :host{all:initial;display:block;margin:8px 0 12px}
  *{box-sizing:border-box}
  .p{--pri:#1D5A3B;--tx:#1E2A24;--tx2:#5C6660;--tx3:#8E958F;--ln:#DDE3DD;--bg:#F6F8F6;--card:#fff;font:13px/1.4 "Segoe UI",system-ui,Arial,sans-serif;color:var(--tx);
    background:var(--bg);border:1px solid var(--ln);border-radius:12px;padding:12px 14px}
  .p.escuro{--tx:#E6ECE8;--tx2:#AEB8B2;--tx3:#7F8A84;--ln:#2E3A33;--bg:#141B17;--card:#1C2520}
  header{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
  .marca{display:flex;align-items:center;gap:8px;font-weight:700;color:var(--pri)}
  .p.escuro .marca{color:#7CC69B}
  .marca .sel{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:7px;background:var(--pri);color:#fff}
  .marca small{font-weight:400;color:var(--tx3)}
  .busca{flex:1;min-width:220px;display:flex;align-items:center;gap:6px;background:var(--card);border:1px solid var(--ln);border-radius:8px;padding:0 8px;color:var(--tx3)}
  .busca input{all:unset;flex:1;padding:7px 0;color:var(--tx);font:inherit}
  .acoes{display:flex;gap:4px}
  button{font:inherit;color:var(--tx2);background:var(--card);border:1px solid var(--ln);border-radius:8px;padding:6px 8px;cursor:pointer;display:inline-flex;align-items:center;gap:5px}
  button:hover{color:var(--pri);border-color:var(--pri)}
  button:focus-visible{outline:2px solid var(--pri);outline-offset:1px}
  .acoes button.ativo{background:var(--pri);border-color:var(--pri);color:#fff}
  .corpo{margin-top:12px}
  .p.recolhido .corpo{display:none}
  .cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(118px,1fr));gap:8px}
  .card{all:unset;cursor:pointer;background:var(--card);border:1px solid var(--ln);border-radius:10px;padding:9px 11px;display:flex;flex-direction:column;gap:2px;position:relative;overflow:hidden}
  .card:hover{border-color:var(--c,var(--pri))}
  .card:focus-visible{outline:2px solid var(--pri)}
  .card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--c,var(--pri))}
  .card .n{color:var(--tx);font-size:22px;font-weight:700;line-height:1.1;font-variant-numeric:tabular-nums}
  .card .r{display:flex;align-items:center;gap:5px;color:var(--tx2);font-size:12px}
  .card .r svg{color:var(--c,var(--pri))}
  .card.zero{opacity:.55}
  .card.ativo{background:color-mix(in srgb,var(--c,var(--pri)) 10%,var(--card));border-color:var(--c,var(--pri))}
  .grade{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px;margin-top:10px}
  .bloco{background:var(--card);border:1px solid var(--ln);border-radius:10px;padding:10px 12px;min-width:0}
  .bloco h4{margin:0 0 8px;font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--tx3);display:flex;align-items:center;gap:6px}
  .barra{all:unset;cursor:pointer;display:grid;grid-template-columns:18px 1fr auto;align-items:center;gap:7px;width:100%;padding:3px 4px;border-radius:6px}
  .barra:hover,.barra.ativo{background:var(--bg)}
  .barra:focus-visible{outline:2px solid var(--pri)}
  .barra .ic{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border-radius:5px;color:#fff}
  .barra .nm{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:12px}
  .barra .tr{grid-column:2/4;height:4px;border-radius:2px;background:var(--ln);overflow:hidden;margin-top:-2px}
  .barra .tr i{display:block;height:100%;border-radius:2px}
  .barra .q{font-size:12px;font-weight:600;color:var(--tx2);font-variant-numeric:tabular-nums}
  .vazio{color:var(--tx3);font-size:12px}
  .mais{all:unset;cursor:pointer;color:var(--pri);font-size:12px;margin-top:4px;display:inline-block}
  .links{display:flex;flex-wrap:wrap;gap:6px}
  .links a{display:inline-flex;align-items:center;gap:5px;padding:5px 9px;border:1px solid var(--ln);border-radius:14px;color:var(--tx);text-decoration:none;font-size:12px;background:var(--bg)}
  .links a:hover{border-color:var(--pri);color:var(--pri)}
  .lst{list-style:none;margin:0;padding:0;max-height:150px;overflow:auto}
  .lst li{display:flex;gap:8px;align-items:baseline;padding:4px 0;border-bottom:1px dashed var(--ln);font-size:12px}
  .lst li:last-child{border:0}
  .lst b{font-variant-numeric:tabular-nums;white-space:nowrap}
  .lst span{color:var(--tx2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}
  .lst small{color:var(--tx3);white-space:nowrap}
  .lst a{color:inherit;text-decoration:none}.lst a:hover b{color:var(--pri);text-decoration:underline}
  .filtro{display:flex;align-items:center;gap:8px;margin-top:10px;font-size:12px;color:var(--tx2)}
  .filtro b{color:var(--tx)}
  .filtro[hidden]{display:none}
  .rod{margin-top:10px;font-size:11px;color:var(--tx3)}`;

  const CARDS = [
    { f: "todos", r: "Processos", ic: "lista", c: "#1D5A3B" },
    { f: "naoVisualizados", r: "Não visualizados", ic: "olho", c: "#B42318" },
    { f: "vencidos", r: "Prazo vencido", ic: "alerta", c: "#B42318" },
    { f: "vencendo", r: "Vencendo", ic: "relogio", c: "#F79009" },
    { f: "urgentes", r: "Urgentes", ic: "alerta", c: "#D92D20" },
    { f: "semAtribuicao", r: "Sem atribuição", ic: "pessoaX", c: "#2B5797" },
    { f: "comAnotacao", r: "Com anotação", ic: "nota", c: "#C88A00" },
    { f: "monitorados", r: "Monitorados", ic: "alvo", c: "#6B3FA0" },
  ];
  const ATALHOS = [
    [/bloco[s]? de assinatura/i, "Blocos de assinatura", "caneta"], [/retorno programado/i, "Retorno programado", "relogio"],
    [/acompanhamento especial/i, "Acompanhamento especial", "alvo"], [/^marcadores$/i, "Marcadores", "etiqueta"],
    [/controle de prazos?/i, "Controle de prazos", "relogio"], [/^pesquisa$/i, "Pesquisa", "lupa"], [/estat[ií]sticas/i, "Estatísticas", "planilha"],
  ];

  async function controle(cfg, monitorados, historico) {
    const form = document.getElementById("frmProcedimentoControlar");
    if (!form || document.getElementById("apto-sei-painel")) return;
    const estilo = document.createElement("style");
    estilo.id = "apto-sei-estilo";
    estilo.textContent = CSS_LINHA;
    document.head.appendChild(estilo);

    const linhas = [...document.querySelectorAll("tr[id^='P']")].filter((tr) => /^P\d+$/.test(tr.id));
    const lidos = [];
    linhas.forEach((tr, i) => { const p = lerLinha(tr); if (p) { p.tr = tr; p.ordem = i; lidos.push(p); } });
    const regras = C.regrasDoTexto(cfg.regrasTexto);
    let procs = C.enriquecer(lidos, { ...cfg, regras, monitorados });
    lidos.forEach((p, i) => { procs[i].tr = p.tr; });

    // contador de não visualizados no título da aba
    const tituloOrig = document.title;
    const contador = () => {
      const n = procs.filter((p) => p.naoVisualizado).length;
      document.title = cfg.contadorAba && n ? `(${n}) ${tituloOrig}` : tituloOrig;
    };
    contador();

    // marcas em cada linha
    function decorar(p) {
      const tr = p.tr;
      tr.querySelectorAll(".apto-deco, .apto-esp, .apto-nota").forEach((e) => e.remove());
      tr.classList.toggle("apto-urgente", p.urgente);
      const a = tr.querySelector("a.processoVisualizado, a.processoNaoVisualizado, a[class*='processoVisualizado'], a[class*='processoNaoVisualizado']");
      const d = document.createElement("span");
      d.className = "apto-deco";
      const c = p.categoria;
      let h = `<span class="ic" style="background:${esc(c.cor)}" title="${esc(c.rotulo)}">${svg(c.icone, 13)}</span>`;
      if (p.urgente) h += `<span class="urg" title="Urgente">${svg("alerta", 15)}</span>`;
      if (p.prazo) h += `<span class="pz ${p.prazo.nivel}" title="${esc((p.prazo.tipo === "vence" ? "Prazo: " : "Parado desde ") + p.prazo.data)}">${svg("relogio", 11)}${esc(p.prazo.rotulo)}</span>`;
      h += `<button type="button" class="mon${p.monitorado ? " on" : ""}" title="${p.monitorado ? "Parar de monitorar" : "Monitorar este processo"}" aria-pressed="${p.monitorado}">${svg("alvo", 14)}</button>`;
      h += `<button type="button" class="cp" title="Copiar o número do processo">${svg("copiar", 14)}</button>`;
      d.innerHTML = h;
      a.after(d);
      d.querySelector(".cp").addEventListener("click", (e) => { e.preventDefault(); copiar(p.numero); });
      d.querySelector(".mon").addEventListener("click", async (e) => {
        e.preventDefault();
        if (monitorados[p.numero]) delete monitorados[p.numero];
        else monitorados[p.numero] = { tipo: p.tipo, especificacao: p.especificacao, href: p.href, quando: Date.now() };
        await st.set({ seiMonitorados: monitorados });
        p.monitorado = !!monitorados[p.numero];
        decorar(p); desenhar();
      });
      const cel = a.parentElement;
      if (cfg.mostrarEspecificacao && p.especificacao) {
        const s = document.createElement("span"); s.className = "apto-esp"; s.textContent = p.especificacao; cel.appendChild(s);
      }
      if (cfg.mostrarAnotacao && p.anotacao) {
        const n = document.createElement("span");
        n.className = "apto-nota" + (p.anotacaoPrioridade ? " prioridade" : "");
        n.textContent = p.anotacao; n.title = "Anotação (clique para abrir ou recolher)";
        n.addEventListener("click", () => n.classList.toggle("aberta"));
        cel.appendChild(n);
      }
      // guarda o processo clicado: a página do processo usa para o título da aba e o histórico
      a.addEventListener("click", () => { try { sessionStorage.setItem("aptoSeiUltimo", JSON.stringify({ numero: p.numero, tipo: p.tipo, especificacao: p.especificacao })); } catch (e) { /* */ } }, { once: false });
    }
    procs.forEach(decorar);

    function copiar(t) {
      const ok = () => { const b = document.createElement("div"); b.className = "apto-copiado"; b.textContent = `Copiado: ${t}`; document.body.appendChild(b); setTimeout(() => b.remove(), 1600); };
      if (navigator.clipboard) navigator.clipboard.writeText(t).then(ok, ok); else ok();
    }

    // painel
    const host = document.createElement("div");
    host.id = "apto-sei-painel";
    form.parentNode.insertBefore(host, form);
    const raizP = host.attachShadow({ mode: "open" });
    let filtro = null;
    let busca = "";
    let ordenado = false;
    const abertos = {};

    function aplicarFiltro() {
      let n = 0;
      for (const p of procs) { const v = C.passa(p, filtro, busca); p.tr.classList.toggle("apto-oculto", !v); if (v) n++; }
      return n;
    }
    function ordenar(porPrazo) {
      const grupos = new Map();
      for (const p of procs) { const pai = p.tr.parentNode; if (!grupos.has(pai)) grupos.set(pai, []); grupos.get(pai).push(p); }
      for (const [pai, ps] of grupos) {
        ps.slice().sort((a, b) => (porPrazo ? C.chavePrazo(a) - C.chavePrazo(b) : 0) || a.ordem - b.ordem).forEach((p) => pai.appendChild(p.tr));
      }
    }
    const rotFiltro = () => {
      if (!filtro) return "";
      if (filtro.campo === "rapido") return (CARDS.find((c) => c.f === filtro.valor) || {}).r || filtro.valor;
      if (filtro.campo === "categoria") return "Categoria: " + ((C.CATEGORIAS.find((c) => c.id === filtro.valor) || {}).rotulo || (procs.find((p) => p.categoria.id === filtro.valor) || { categoria: {} }).categoria.rotulo || "Outros");
      return ({ tipo: "Tipo", atribuicao: "Atribuição", marcador: "Marcador" }[filtro.campo] || "") + ": " + (filtro.valor || "(sem atribuição)");
    };
    const mesmo = (f) => filtro && f && filtro.campo === f.campo && filtro.valor === f.valor;

    function blocoBarras(titulo, ic, itens, campo, chave) {
      const max = Math.max(1, ...itens.map((x) => x.q));
      const lim = abertos[campo] ? itens.length : 6;
      const h = itens.slice(0, lim).map((x) => {
        const f = { campo, valor: x.valor };
        return `<button class="barra${mesmo(f) ? " ativo" : ""}" data-campo="${esc(campo)}" data-valor="${esc(x.valor)}" title="${esc(x.nome)}: ${x.q}">
          <span class="ic" style="background:${esc(x.cor || "#8E958F")}">${svg(x.icone || ic, 11)}</span><span class="nm">${esc(x.nome)}</span><span class="q">${x.q}</span>
          <span class="tr"><i style="width:${Math.round((x.q / max) * 100)}%;background:${esc(x.cor || "#1D5A3B")}"></i></span></button>`;
      }).join("");
      const mais = itens.length > 6 ? `<button class="mais" data-mais="${esc(campo)}">${abertos[campo] ? "mostrar menos" : `mais ${itens.length - 6}`}</button>` : "";
      return `<div class="bloco"><h4>${svg(ic, 12)}${esc(titulo)}</h4>${h || '<div class="vazio">Nada nesta página.</div>'}${mais}</div>`;
    }

    function atalhos() {
      const vistos = new Set();
      const r = [];
      for (const a of document.querySelectorAll("a[href*='controlador.php?acao=']")) {
        if (a.closest("#apto-sei-painel, tr[id^='P']")) continue;
        const t = (a.textContent || "").trim();
        for (const [re, rot, ic] of ATALHOS) if (re.test(t) && !vistos.has(rot)) { vistos.add(rot); r.push({ rot, ic, href: a.href }); }
      }
      return r;
    }
    const linksMenu = atalhos();

    function desenhar() {
      const R = C.resumo(procs);
      const vis = aplicarFiltro();
      const quando = (t) => { const d = new Date(t); return `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; };
      const mon = Object.entries(monitorados).sort((a, b) => b[1].quando - a[1].quando);
      const naLista = new Map(procs.map((p) => [p.numero, p]));
      const linkProc = (num, href) => { const p = naLista.get(num); const h = (p && p.href) || href; return h ? `<a href="${esc(h)}"><b>${esc(num)}</b></a>` : `<b>${esc(num)}</b>`; };
      raizP.innerHTML = `<style>${CSS_PAINEL}</style>
      <section class="p${cfg.temaEscuro ? " escuro" : ""}${cfg.recolhido ? " recolhido" : ""}" aria-label="Painel do APTO no SEI">
        <header>
          <div class="marca"><span class="sel">${svg("balanca", 15)}</span>APTO <small>Painel do SEI</small></div>
          <label class="busca" title="Busca rápida: 3 letras ou mais, sem acento; todas as palavras precisam aparecer">${svg("lupa", 14)}<input type="search" placeholder="Busca rápida: número, tipo, especificação, interessado, marcador, anotação…" value="${esc(busca)}" aria-label="Busca rápida"></label>
          <div class="acoes">
            <button data-acao="ordem" class="${ordenado ? "ativo" : ""}" title="Ordenar a lista pelo prazo (vencidos primeiro)">${svg("ordem", 14)}Prazo</button>
            <button data-acao="csv" title="Baixar os processos visíveis em planilha (CSV)">${svg("planilha", 14)}</button>
            <button data-acao="tema" class="${cfg.temaEscuro ? "ativo" : ""}" title="Tema escuro no SEI">${svg("lua", 14)}</button>
            <button data-acao="recolher" title="${cfg.recolhido ? "Abrir o painel" : "Recolher o painel"}" aria-expanded="${!cfg.recolhido}"><span style="display:inline-flex;transform:rotate(${cfg.recolhido ? -90 : 0}deg)">${svg("seta", 14)}</span></button>
          </div>
        </header>
        <div class="corpo">
          <div class="cards">${CARDS.map((k) => {
            const n = k.f === "todos" ? R.total : R[k.f];
            const f = { campo: "rapido", valor: k.f };
            const at = k.f === "todos" ? !filtro : mesmo(f);
            return `<button class="card${n ? "" : " zero"}${at ? " ativo" : ""}" style="--c:${k.c}" data-campo="rapido" data-valor="${k.f}" aria-pressed="${at}">
              <span class="n">${n}</span><span class="r">${svg(k.ic, 13)}${k.r}</span></button>`;
          }).join("")}</div>
          <div class="filtro" ${filtro || C.norm(busca).length >= 3 ? "" : "hidden"}>Mostrando <b>${vis}</b> de ${R.total}${filtro ? ` · <b>${esc(rotFiltro())}</b>` : ""}${C.norm(busca).length >= 3 ? ` · busca "<b>${esc(busca)}</b>"` : ""}
            <button data-acao="limpar">Limpar</button></div>
          <div class="grade">
            ${blocoBarras("Categorias", "etiqueta", R.porCategoria.map((x) => ({ nome: x.rotulo, valor: x.id, q: x.q, cor: x.cor, icone: x.icone })), "categoria")}
            ${blocoBarras("Tipos de processo", "documento", R.porTipo.map(([n, q]) => ({ nome: n, valor: n === "(sem tipo)" ? "" : n, q, cor: "#1D5A3B" })), "tipo")}
            ${blocoBarras("Marcadores", "etiqueta", R.porMarcador.map(([n, q]) => ({ nome: n, valor: n, q, cor: "#C88A00" })), "marcador")}
            ${blocoBarras("Atribuição", "pessoa", R.porAtribuicao.map(([n, q]) => ({ nome: n || "(sem atribuição)", valor: n, q, cor: n ? "#2B5797" : "#8E958F", icone: n ? "pessoa" : "pessoaX" })), "atribuicao")}
          </div>
          <div class="grade">
            <div class="bloco"><h4>${svg("alvo", 12)}Monitorados</h4>${mon.length ? `<ul class="lst">${mon.map(([n, m]) => `<li>${linkProc(n, m.href)}<span>${esc(m.tipo)}${m.especificacao ? " · " + esc(m.especificacao) : ""}</span><small>${naLista.has(n) ? "nesta lista" : "fora da lista"}</small></li>`).join("")}</ul>` : '<div class="vazio">Clique no alvo ao lado do número para acompanhar um processo.</div>'}</div>
            <div class="bloco"><h4>${svg("historico", 12)}Visitados recentemente</h4>${historico.length ? `<ul class="lst">${historico.slice(0, 15).map((h) => `<li>${linkProc(h.numero)}<span>${esc(h.tipo)}${h.especificacao ? " · " + esc(h.especificacao) : ""}</span><small>${quando(h.quando)}</small></li>`).join("")}</ul>` : '<div class="vazio">Os processos que você abrir aparecem aqui.</div>'}</div>
            <div class="bloco"><h4>${svg("seta", 12)}Atalhos</h4>${linksMenu.length ? `<div class="links">${linksMenu.map((l) => `<a href="${esc(l.href)}">${svg(l.ic, 13)}${esc(l.rot)}</a>`).join("")}</div>` : '<div class="vazio">Nenhum atalho do menu encontrado nesta página.</div>'}</div>
          </div>
          <div class="rod">Só aparência: o APTO lê o que esta página já mostra e não altera nada no SEI. Prazo: data no marcador ("ATÉ 20/11/2026" = vencimento; só a data = parado desde), na anotação, no retorno programado ou no controle de prazo.</div>
        </div>
      </section>`;
      const inp = raizP.querySelector("input");
      inp.addEventListener("input", () => {
        busca = inp.value;
        const pos = inp.selectionStart;
        desenhar();
        const n = raizP.querySelector("input"); n.focus(); try { n.setSelectionRange(pos, pos); } catch (e) { /* */ }
      });
      inp.addEventListener("keydown", (e) => { if (e.key === "Escape") { busca = ""; desenhar(); raizP.querySelector("input").focus(); } });
      raizP.querySelectorAll("[data-campo]").forEach((b) => b.addEventListener("click", () => {
        const f = { campo: b.dataset.campo, valor: b.dataset.valor };
        filtro = f.campo === "rapido" && f.valor === "todos" ? null : mesmo(f) ? null : f;
        desenhar();
      }));
      raizP.querySelectorAll("[data-mais]").forEach((b) => b.addEventListener("click", () => { abertos[b.dataset.mais] = !abertos[b.dataset.mais]; desenhar(); }));
      raizP.querySelectorAll("[data-acao]").forEach((b) => b.addEventListener("click", async () => {
        const a = b.dataset.acao;
        if (a === "limpar") { filtro = null; busca = ""; }
        if (a === "ordem") { ordenado = !ordenado; ordenar(ordenado); }
        if (a === "tema") { cfg.temaEscuro = !cfg.temaEscuro; aplicarTema(cfg); await st.set({ seiPainel: cfg }); }
        if (a === "recolher") { cfg.recolhido = !cfg.recolhido; await st.set({ seiPainel: cfg }); }
        if (a === "csv") baixarCsv();
        desenhar();
      }));
    }
    function baixarCsv() {
      const vis = procs.filter((p) => !p.tr.classList.contains("apto-oculto"));
      const url = URL.createObjectURL(new Blob([C.csv(vis)], { type: "text/csv;charset=utf-8" }));
      const a = document.createElement("a");
      const d = new Date();
      a.href = url; a.download = `SEI_processos_${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}.csv`;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    }
    desenhar();
    window.__aptoSeiPainelProcs = () => procs.map(({ tr, ...p }) => p); // para os testes
  }

  // página do processo: título da aba com o número e o histórico de visitados
  async function processo(historico) {
    let u = null;
    try { u = JSON.parse(sessionStorage.getItem("aptoSeiUltimo") || "null"); } catch (e) { /* */ }
    if (!u || !u.numero) return;
    const id = new URL(location.href).searchParams.get("id_procedimento");
    if (id) { try { sessionStorage.removeItem("aptoSeiUltimo"); } catch (e) { /* */ } }
    document.title = `${u.numero}${u.tipo ? " · " + u.tipo : ""} - SEI`;
    await st.set({ seiHistorico: C.registrarVisita(historico, u) });
  }

  async function iniciar() {
    const r = await st.get(["seiPainel", "seiMonitorados", "seiHistorico", "cfg"]);
    const cfg = { ...C.PADRAO, ...(r.seiPainel || {}) };
    if ((r.cfg && r.cfg.ativo === false) || !cfg.ligado) return;
    aplicarTema(cfg);
    if (window !== window.top) return; // nas molduras (árvore, documento): só o tema
    if (acao === "procedimento_controlar" || document.getElementById("frmProcedimentoControlar")) await controle(cfg, r.seiMonitorados || {}, r.seiHistorico || []);
    else if (acao === "procedimento_trabalhar") await processo(r.seiHistorico || []);
  }
  iniciar();
})();
