// APTO - painel no SEEU (v2.1): montagem do HTML a partir do resultado (funções puras, sem Chrome; usadas por painel.js e
// pelos testes em node). Hierarquia: pena e MARCOS em linhas compactas (só a data e quanto falta; destaque quando está
// próximo ou já foi atingido) -> PARA CONFERIR em cartões (o destaque do painel) -> o que confere, em linhas -> crimes e
// hipóteses afastadas. Duas situações só: verde = confere (há certeza), amarelo = conferir; cor nunca sozinha (ícone + texto).
// Todo texto vindo do cálculo passa por esc(): nada do SEEU vira HTML.
(function (raiz) {
  "use strict";
  const ICO = {
    verde: '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" focusable="false"><path d="M20 6 9 17l-5-5" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    amarelo: '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" focusable="false"><path d="M12 7v6" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/><circle cx="12" cy="17.5" r="1.6" fill="currentColor"/></svg>',
  };
  const DEST = { proximo: "Próximo", atingida: "Atingida" };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function topo(p) {
    return `<div class="fonte" role="note"><span>Regras do APTO sobre os dados das abas do SEEU · referência ${esc(p.hoje || "")}</span>` +
      (p.ficha ? "" : `<span class="chip">${ICO.amarelo}Ficha disciplinar não lida: o que depende dela fica para conferir</span>`) + `</div>`;
  }

  function pena(p) {
    const x = p.pena || {};
    const pct = typeof x.pct === "number" ? x.pct : null;
    return `<div class="kv">` +
      [["Pena total", x.total], ["Cumprida", x.cumprida], ["Remanescente", x.remanescente]]
        .map(([r, v]) => `<div><small>${r}</small><b>${esc(v || "—")}</b></div>`).join("") + `</div>` +
      (pct != null ? `<div class="barra" role="img" aria-label="${pct}% da pena cumprida"><span style="width:${pct}%"></span></div>` +
        `<div class="pct">${pct}% cumprida${x.regime ? " · regime " + esc(x.regime.toLowerCase()) : ""}</div>` : "") +
      (x.aviso ? `<div class="aviso-exec">${esc(x.aviso)}</div>` : "");
  }

  // marcos: uma linha por data (rótulo, data, quanto falta); o detalhe (fração, conta) abre no clique
  function marcos(p) {
    const L = p.marcos || [];
    if (!L.length) return "";
    return `<ul class="marcos" aria-label="Marcos">` + L.map((m) => {
      const det = [m.extra, ...(m.conta || [])].filter(Boolean);
      const resumo = `<span class="mr">${esc(m.rotulo)}${m.alerta ? `<span class="mk" title="Há ponto a conferir neste marco">${ICO.amarelo}<span class="vh">há ponto a conferir</span></span>` : ""}</span>` +
        `<span class="md">${esc(m.data || "—")}</span>` +
        `<span class="mq">${m.destaque ? `<span class="dest ${esc(m.destaque)}">${DEST[m.destaque]}</span> ` : ""}${esc(m.quando || "")}</span>`;
      const cls = m.destaque ? ` class="on ${esc(m.destaque)}"` : "";
      return `<li${cls}>` + (det.length || m.fundamento
        ? `<details><summary>${resumo}</summary><div class="mdet">${det.map(esc).join("<br>")}${m.fundamento ? `<div class="fund">${esc(m.fundamento)}</div>` : ""}</div></details>`
        : `<div class="linha">${resumo}</div>`) + `</li>`;
    }).join("") + `</ul>`;
  }

  // alertas: o destaque do painel, um cartão por ponto a conferir
  function alerta(it) {
    const temConta = (it.conta || []).length || it.fundamento;
    return `<li class="al"><div class="l1"><span class="ic">${ICO.amarelo}</span><span class="t">${esc(it.titulo)}</span>${it.valor ? `<span class="v">${esc(it.valor)}</span>` : ""}</div>` +
      `${it.motivo ? `<div class="m">${esc(it.motivo)}</div>` : ""}` +
      `${it.conferir ? `<div class="conf"><b>Conferir:</b> ${esc(it.conferir)}</div>` : ""}` +
      (temConta ? `<details><summary>Conta e fundamento</summary>${(it.conta || []).length ? `<div class="conta">${it.conta.map(esc).join("<br>")}</div>` : ""}` +
        `${it.fundamento ? `<div class="fund">${esc(it.fundamento)}</div>` : ""}</details>` : "") + `</li>`;
  }

  function corpo(res) {
    const p = res.painel || {};
    let h = topo(p) + `<section class="pena" aria-label="Pena e marcos">${pena(p)}${marcos(p)}</section>`;
    const A = p.alertas || [];
    h += `<section aria-labelledby="s-al"><h2 id="s-al" class="h-al">Para conferir${A.length ? ` <span class="cnt">${A.length}</span>` : ""}</h2>` +
      (A.length ? `<ul class="alertas">${A.map(alerta).join("")}</ul>` : `<p class="vazio">${ICO.verde} Nada para conferir.</p>`) + `</section>`;
    if ((p.confere || []).length) {
      h += `<section aria-labelledby="s-ok"><h2 id="s-ok">Confere</h2><ul class="confere">` +
        p.confere.map((it) => `<li><span class="ic">${ICO.verde}</span><span class="t">${esc(it.titulo)}</span>${it.valor ? `<span class="v">${esc(it.valor)}</span>` : ""}</li>`).join("") + `</ul></section>`;
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
    sem_dados: ["Não foi possível ler o processo", "O SEEU não entregou as abas do processo (sessão expirada ou página diferente). Recarregue a página do SEEU e clique em Ler de novo."],
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
    return corpo(res);
  }

  function resumo(res) {
    const p = res.painel || {};
    const x = p.pena || {};
    const L = [`APTO · ${p.processo || ""} · ${p.nome || ""} · referência ${p.hoje || ""}`,
      `Pena ${x.total || "—"} · cumprida ${x.cumprida || "—"} · remanescente ${x.remanescente || "—"}`, "", "MARCOS"];
    for (const m of p.marcos || []) L.push(`- ${m.rotulo}: ${m.data || "—"}${m.quando ? " (" + m.quando + ")" : ""}${m.destaque ? " [" + DEST[m.destaque].toLowerCase() + "]" : ""}`);
    L.push("", "PARA CONFERIR");
    for (const a of p.alertas || []) L.push(`- ${a.titulo}${a.valor ? ": " + a.valor : ""}${a.motivo ? " (" + a.motivo + ")" : ""}${a.conferir ? " · conferir: " + a.conferir : ""}`);
    if ((p.confere || []).length) { L.push("", "CONFERE"); for (const c of p.confere) L.push(`- ${c.titulo}${c.valor ? ": " + c.valor : ""}`); }
    if ((p.nao_cabe || []).length) { L.push("", "NÃO CABE"); for (const n of p.nao_cabe) L.push(`- ${n.titulo}: ${n.motivo}`); }
    L.push("", "Calculado pelas regras do APTO sobre os dados do SEEU; conferir antes de peticionar.");
    return L.join("\n");
  }

  const api = { esc, html, resumo, ICO };
  if (typeof module === "object" && module.exports) module.exports = api;
  else raiz.APTO_PAINEL_CORE = api;
})(typeof self !== "undefined" ? self : this);
