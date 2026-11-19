// APTO - destaques da aba Movimentações do SEEU. O realce do próprio SEEU colore por QUEM movimentou; aqui, a classificação é pelo
// CONTEÚDO do evento (APTO_PAINEL_CORE.classificarMov): decisões, despachos, MP, Defensoria, unidade prisional, audiências e partes
// ganham cor e etiqueta (decisão azul, despacho azul claro, MP vermelho, Defensoria verde, advogado roxo, Depen amarelo, cartório
// laranja); o que não tem arquivo vinculado fica esmaecido - ou oculto, se a pessoa escolher. Uma barra acima da tabela filtra por
// categoria, com as contagens. Só acrescenta classes e a barra: não muda o conteúdo, os links nem os filtros do SEEU. A escolha fica lembrada.
(function () {
  "use strict";
  if (window.__aptoMovs) return;
  window.__aptoMovs = true;
  if (window.name === "apto-triagem-oculta") return;
  if (!/visualizacaoProcesso\.do/i.test(location.pathname)) return;
  const C = self.APTO_PAINEL_CORE;
  if (!C || !C.classificarMov) return;

  const COR = {   // barra à esquerda, fundo da linha, etiqueta (fundo, texto), nome
    decisao: ["#1F4E8C", "#E8F0FB", "#1F4E8C", "#fff", "Decisão"],
    despacho: ["#5B9BD5", "#F1F7FD", "#D6E7F7", "#173F6B", "Despacho"],
    mp: ["#B3261E", "#FCEDEC", "#B3261E", "#fff", "MP"],
    defensoria: ["#1D7A4A", "#EAF6EF", "#1D7A4A", "#fff", "DPE"],
    advogado: ["#6B3FA0", "#F4EFFB", "#6B3FA0", "#fff", "ADV"],
    unidade: ["#C99A06", "#FFF8DC", "#F2D35B", "#4D3B00", "Depen"],
    cartorio: ["#D9661F", "#FDF1E8", "#F6CDAF", "#6B2C05", "Cartório"],
    audiencia: ["#0E7490", "#EAF6F9", "#0E7490", "#fff", "Audiência"],
    pericia: ["#7A5230", "#F7F0E9", "#7A5230", "#fff", "Perícia"],
  };
  // a linha e o seu detalhe (o "+" abre os documentos numa linha logo abaixo): a mesma cor
  const css = Object.entries(COR).map(([k, [bar, bg, tb, tc]]) =>
    `tr[data-apto-mov="${k}"]>td:first-child,tr[data-apto-det="${k}"]>td:first-child{box-shadow:inset 4px 0 0 ${bar}}` +
    (bg ? `tr[data-apto-mov="${k}"]>td,tr[data-apto-det="${k}"]>td{background-color:${bg}!important}` : "") +
    `tr[data-apto-mov="${k}"] .apto-tag{background:${tb};color:${tc}}`).join("\n") + `
    .apto-tag{display:inline-block;margin:0 6px 2px 0;padding:1px 7px;border-radius:999px;font:700 10.5px/1.5 "Source Sans 3","Segoe UI",system-ui,sans-serif;
      letter-spacing:.02em;vertical-align:1px;white-space:nowrap}
    table.apto-movs.apto-esmaecer tr[data-apto-arq="0"]>td{opacity:.45}
    tr[data-apto-det]>td .extendedinfo,tr[data-apto-det]>td table{background:transparent!important}
    table.apto-movs.apto-esmaecer tr[data-apto-arq="0"]:hover>td{opacity:1}
    table.apto-movs tr.apto-oculta,table.apto-movs tr.apto-oculta+tr[id^="rowmov"]{display:none!important}`;

  const ROT = Object.fromEntries(C.CAT_MOV);
  let pref = { so: [], rotina: "esmaecer" };   // so: categorias escolhidas (vazio = todas); rotina (sem arquivo vinculado): esmaecer | ocultar | mostrar

  function linhas(tab) {
    return [...tab.querySelectorAll("tbody > tr[id^='mov']")];
  }
  function classificar(tab) {
    const n = {};
    for (const tr of linhas(tab)) {
      const grupos = tr.id.split(",").map((x) => x.trim()).filter(Boolean).slice(1);
      const tds = tr.children;
      const b = tds[3] && tds[3].querySelector("b");
      const titulo = b ? b.textContent.replace(/\s+/g, " ").trim() : "";
      const cargo = (tds[5] && tds[5].querySelector("font b") || {}).textContent || "";
      const cat = C.classificarMov(grupos, titulo, cargo);
      tr.dataset.aptoMov = cat;
      const det = tr.nextElementSibling;
      if (det && /^rowmov/i.test(det.id || "")) det.dataset.aptoDet = cat;
      // arquivo vinculado: o "+" que abre os documentos (o SEEU marca SEMARQUIVO no id da linha quando não há)
      const temArq = !grupos.map((x) => x.toUpperCase()).includes("SEMARQUIVO") && !!tr.querySelector("img[onclick*='showDetail'], a[class^='linkArquivos'], a[href*='arquivo.do']");
      tr.dataset.aptoArq = temArq ? "1" : "0";
      n._sem = (n._sem || 0) + (temArq ? 0 : 1);
      n[cat] = (n[cat] || 0) + 1;
      if (COR[cat] && b && !b.querySelector(".apto-tag")) {
        const t = document.createElement("span");
        t.className = "apto-tag";
        t.textContent = COR[cat][4];
        const alvo = b.querySelector("div") || b;   // no SEEU, o título fica num div dentro do negrito: a etiqueta vai na mesma linha
        alvo.insertBefore(t, alvo.firstChild);
      }
    }
    return n;
  }
  function aplicar(tab) {
    tab.classList.toggle("apto-esmaecer", pref.rotina === "esmaecer");
    for (const tr of linhas(tab)) {
      const c = tr.dataset.aptoMov;
      const fora = (tr.dataset.aptoArq === "0" && pref.rotina === "ocultar") || (pref.so.length > 0 && !pref.so.includes(c));
      tr.classList.toggle("apto-oculta", fora);
    }
  }

  function barra(tab, n) {
    const host = document.createElement("div");
    host.id = "apto-movs";
    // contain: a barra não alarga a célula da tabela do SEEU onde ela fica (as categorias quebram em linhas, não esticam a página)
    host.style.cssText = "all:initial;display:block;margin:8px 0;width:100%;max-width:100%;box-sizing:border-box;contain:inline-size";
    const raiz = host.attachShadow({ mode: "open" });
    const total = Object.entries(n).filter(([k]) => k !== "_sem").reduce((a, [, b]) => a + b, 0);
    const chips = C.CAT_MOV.filter(([k]) => n[k]).map(([k, r]) => {
      const cor = COR[k] ? COR[k][0] : "#5C636A";
      return `<button type="button" class="ch" data-cat="${k}" aria-pressed="false" style="--c:${cor}"><i aria-hidden="true"></i>${r}<b>${n[k]}</b></button>`;
    }).join("");
    raiz.innerHTML = `<style>
      :host{all:initial}
      .bx{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:8px 10px;background:#fff;border:1px solid #C9CED2;border-radius:10px;
        font:12.5px/1.2 "Source Sans 3","Segoe UI",system-ui,sans-serif;color:#1E2226}
      .t{font-weight:700;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:#1D5A3B;margin-right:2px}
      .ch{all:unset;box-sizing:border-box;display:inline-flex;align-items:center;gap:6px;min-height:28px;padding:0 10px;border-radius:999px;
        border:1px solid #C9CED2;background:#fff;cursor:pointer;font-weight:600;white-space:nowrap}
      .ch i{width:10px;height:10px;border-radius:50%;background:var(--c)}
      .ch b{font-variant-numeric:tabular-nums;color:#5C636A;font-weight:700}
      .ch:hover{background:#F2F4F5}
      .ch[aria-pressed="true"]{background:var(--c);border-color:var(--c);color:#fff}
      .ch[aria-pressed="true"] b{color:#fff}
      .sep{width:1px;align-self:stretch;background:#E3E6E8;margin:0 2px}
      .seg{display:inline-flex;border:1px solid #C9CED2;border-radius:8px;overflow:hidden}
      .seg button{all:unset;box-sizing:border-box;min-height:28px;padding:0 10px;cursor:pointer;font-weight:600;border-right:1px solid #E3E6E8}
      .seg button:last-child{border-right:0}
      .seg button[aria-pressed="true"]{background:#1D5A3B;color:#fff}
      .ch:focus-visible,.seg button:focus-visible,.lim:focus-visible{outline:3px solid #F2B705;outline-offset:2px}
      .r{color:#5C636A}
      .lim{all:unset;cursor:pointer;color:#1D5A3B;font-weight:700;text-decoration:underline;margin-left:auto}
      .vh{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
      [hidden]{display:none!important}
    </style>
    <div class="bx" role="group" aria-label="Destaques do APTO nas movimentações">
      <span class="t">Destaques do APTO</span>${chips}
      <span class="sep" aria-hidden="true"></span>
      <span class="r" id="rl">Sem arquivo vinculado (${n._sem || 0} de ${total}):</span>
      <span class="seg" role="group" aria-labelledby="rl">
        <button type="button" data-rot="esmaecer">Esmaecer</button><button type="button" data-rot="ocultar">Ocultar</button><button type="button" data-rot="mostrar">Mostrar</button>
      </span>
      <button type="button" class="lim" data-limpar="1" hidden>Mostrar todas</button>
      <span class="vh" role="status" aria-live="polite" id="st"></span>
    </div>`;
    const pintar = () => {
      raiz.querySelectorAll("[data-cat]").forEach((b) => b.setAttribute("aria-pressed", String(pref.so.includes(b.dataset.cat))));
      raiz.querySelectorAll("[data-rot]").forEach((b) => b.setAttribute("aria-pressed", String(pref.rotina === b.dataset.rot)));
      raiz.querySelector("[data-limpar]").hidden = !pref.so.length;
      aplicar(tab);
      const vis = linhas(tab).filter((tr) => !tr.classList.contains("apto-oculta")).length;
      raiz.getElementById("st").textContent = vis + " de " + total + " movimentações à vista";
    };
    raiz.addEventListener("click", (e) => {
      const c = e.target.closest("[data-cat]"), r = e.target.closest("[data-rot]"), l = e.target.closest("[data-limpar]");
      if (c) { const k = c.dataset.cat; pref.so = pref.so.includes(k) ? pref.so.filter((x) => x !== k) : pref.so.concat(k); }
      else if (r) pref.rotina = r.dataset.rot;
      else if (l) pref.so = [];
      else return;
      pintar();
      try { chrome.storage.local.set({ movDestaques: pref }); } catch (x) { /* segue */ }
    });
    pintar();
    return host;
  }

  async function iniciar() {
    const tab = document.querySelector("table.resultTable");
    if (!tab || !tab.querySelector("tbody > tr[id^='mov']") || tab.classList.contains("apto-movs")) return;
    const c = await chrome.runtime.sendMessage({ tipo: "cfg" }).catch(() => null);
    if (c && (c.painel === false || c.ativo === false)) return;
    try { const g = await chrome.storage.local.get("movDestaques"); if (g.movDestaques) pref = Object.assign(pref, g.movDestaques); } catch (e) { /* segue */ }
    const st = document.createElement("style");
    st.id = "apto-movs-estilo";
    st.textContent = css;
    (document.head || document.documentElement).appendChild(st);
    tab.classList.add("apto-movs");
    const n = classificar(tab);
    tab.parentNode.insertBefore(barra(tab, n), tab);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar, { once: true });
  else iniciar();
})();
