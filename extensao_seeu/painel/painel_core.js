// APTO - painel no SEEU (v2): montagem do HTML a partir do resultado (funções puras, sem Chrome; usadas por painel.js e
// pelos testes em node). Duas cores só: verde = confere (há certeza), amarelo = conferir. Cor nunca sozinha: ícone + texto.
// Todo texto vindo do cálculo passa por esc(): nada do SEEU vira HTML.
(function (raiz) {
  "use strict";
  // ícones SVG (traço 2px, 16px): visto (confere), alerta (conferir), seta (abrir a conta)
  const ICO = {
    verde: '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" focusable="false"><path d="M20 6 9 17l-5-5" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    amarelo: '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" focusable="false"><path d="M12 7v6" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/><circle cx="12" cy="17.5" r="1.6" fill="currentColor"/></svg>',
  };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function selo(st) {
    return `<span class="selo-st ${st === "verde" ? "verde" : "amarelo"}">${ICO[st === "verde" ? "verde" : "amarelo"]}${st === "verde" ? "Confere" : "Conferir"}</span>`;
  }

  function topo(res) {
    const p = res.painel || {};
    return `<div class="fonte" role="note"><span>Regras do APTO sobre os dados das abas do SEEU · referência ${esc(p.hoje || "")}</span>` +
      (p.ficha ? "" : `<span class="chip">${ICO.amarelo}Ficha disciplinar não lida: o que depende dela fica para conferir</span>`) + `</div>`;
  }

  function pena(p) {
    const x = p.pena || {};
    const pct = typeof x.pct === "number" ? x.pct : null;
    return `<section class="pena" aria-label="Pena"><div class="kv">` +
      [["Pena total", x.total], ["Cumprida", x.cumprida], ["Remanescente", x.remanescente], ["Término", x.termino]]
        .map(([r, v]) => `<div><small>${r}</small><b>${esc(v || "—")}</b></div>`).join("") + `</div>` +
      (pct != null ? `<div class="barra" role="img" aria-label="${pct}% da pena cumprida"><span style="width:${pct}%"></span></div><div class="pct">${pct}% cumprida${x.regime ? " · regime " + esc(x.regime.toLowerCase()) : ""}</div>` : "") +
      (x.aviso ? `<div class="aviso-exec">${esc(x.aviso)}</div>` : "") + `</section>`;
  }

  function item(it) {
    const temConta = (it.conta || []).length || it.fundamento;
    return `<li class="it ${esc(it.status)}"><div class="l1"><span class="t">${esc(it.titulo)}</span>` +
      `${it.valor ? `<span class="v">${esc(it.valor)}</span>` : ""}${selo(it.status)}</div>` +
      `${it.motivo ? `<div class="m">${esc(it.motivo)}</div>` : ""}` +
      `${it.conferir ? `<div class="conf"><b>Conferir:</b> ${esc(it.conferir)}</div>` : ""}` +
      (temConta ? `<details><summary>Conta e fundamento</summary>${(it.conta || []).length ? `<div class="conta">${it.conta.map(esc).join("<br>")}</div>` : ""}` +
        `${it.fundamento ? `<div class="fund">${esc(it.fundamento)}</div>` : ""}</details>` : "") + `</li>`;
  }

  function corpo(res) {
    const p = res.painel || {};
    let h = pena(p);
    for (const s of p.secoes || []) {
      h += `<section aria-labelledby="s-${esc(s.id)}"><h2 id="s-${esc(s.id)}">${esc(s.titulo)}</h2><ul class="lista">${s.itens.map(item).join("")}</ul></section>`;
    }
    if ((p.crimes || []).length) {
      h += `<section aria-labelledby="s-crimes"><h2 id="s-crimes">Crimes em execução</h2><ul class="crimes">` +
        p.crimes.map((c) => `<li><b>${esc(c.texto)}</b>${c.pena ? ` · ${esc(c.pena)}` : ""}${c.hediondo && /verificar/.test(c.hediondo) ? ` <span class="selo-st amarelo">${ICO.amarelo}hediondo a conferir</span>` : ""}</li>`).join("") + `</ul></section>`;
    }
    if ((p.nao_cabe || []).length) {
      h += `<details class="naocabe"><summary>Não cabe: ${p.nao_cabe.length} ${p.nao_cabe.length === 1 ? "hipótese afastada" : "hipóteses afastadas"}</summary><ul>` +
        p.nao_cabe.map((x) => `<li><b>${esc(x.titulo)}</b>: ${esc(x.motivo)}</li>`).join("") + `</ul></details>`;
    }
    return h;
  }

  const AVISO = {
    sem_dados: ["Não foi possível ler o processo", "O SEEU não entregou as abas do processo (sessão expirada ou página diferente). Recarregue a página do SEEU e clique em Atualizar."],
    erro: ["Não foi possível montar a análise", ""],
  };

  function html(res) {
    if (!res || res.estado === "carregando") {
      return `<div class="carregando" aria-busy="true" role="status"><div class="sk alto"></div><div class="sk"></div><div class="sk"></div><div class="sk curto"></div>` +
        `<p>${res && res.etapa ? esc(res.etapa) : "Lendo as abas do processo"}${res && res.primeira ? " (na primeira vez, o motor do APTO leva alguns segundos para carregar)" : ""}…</p></div>`;
    }
    if (AVISO[res.estado]) {
      const [t, d] = AVISO[res.estado];
      return `<div class="aviso" role="status"><b>${esc(t)}</b><p>${esc(res.motivo || d)}</p></div>`;
    }
    return topo(res) + corpo(res);
  }

  function resumo(res) {
    const p = res.painel || {};
    const x = p.pena || {};
    const L = [`APTO · ${p.processo || ""} · ${p.nome || ""} · referência ${p.hoje || ""}`,
      `Pena ${x.total || "—"} · cumprida ${x.cumprida || "—"} · remanescente ${x.remanescente || "—"} · término ${x.termino || "—"}`];
    for (const s of p.secoes || []) {
      L.push("", s.titulo.toUpperCase());
      for (const it of s.itens) L.push(`[${it.status === "verde" ? "confere" : "conferir"}] ${it.titulo}${it.valor ? ": " + it.valor : ""}${it.motivo ? " (" + it.motivo + ")" : ""}${it.conferir ? " · conferir: " + it.conferir : ""}`);
    }
    if ((p.nao_cabe || []).length) {
      L.push("", "NÃO CABE");
      for (const n of p.nao_cabe) L.push(`- ${n.titulo}: ${n.motivo}`);
    }
    L.push("", "Calculado pelas regras do APTO sobre os dados do SEEU; conferir antes de peticionar.");
    return L.join("\n");
  }

  const api = { esc, html, resumo, ICO };
  if (typeof module === "object" && module.exports) module.exports = api;
  else raiz.APTO_PAINEL_CORE = api;
})(typeof self !== "undefined" ? self : this);
