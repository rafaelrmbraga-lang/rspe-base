// APTO - painel no SEEU: montagem do HTML a partir do resultado (funções puras, sem Chrome; usadas por painel.js e pelos
// testes em node). Todo texto vindo do cálculo passa por esc(): nada do SEEU ou do APTO vira HTML.
(function (raiz) {
  "use strict";
  const FORMA = { crit: "◆", urg: "▲", med: "●", prox: "○", ok: "✓", info: "■", neutro: "—" };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function selo(res) {
    const p = res.painel || {};
    const meta = p.hoje ? `Referência ${esc(p.hoje)} · base jurídica ${esc(p.base_juridica || "?")} · motor ${esc(p.motor || "?")}` : "";
    if (res.estado === "confere") {
      return `<div class="selo ok" role="status"><b>✓ Confere com o APTO</b>, mesmo resultado da base aberta${res.base ? " (" + esc(res.base) + ")" : ""}` +
        `<div class="meta">${meta}</div></div>`;
    }
    if (res.estado === "diverge") {
      return `<div class="selo crit" role="alert"><b>◆ Diverge do APTO</b>: a extensão chegou a outro resultado com a mesma entrada. ` +
        `Use o APTO e avise para a extensão ser corrigida.<div class="meta">${meta}</div></div>`;
    }
    return "";
  }

  function fonte(res) {
    const p = res.painel || {};
    return `<div class="fonte">Fonte: <span class="chip">dados do APTO${res.base ? " · " + esc(res.base) : ""}</span>` +
      (p.ficha ? `<span class="chip">ficha do SIAPEN na análise</span>` : `<span class="chip med">● ficha do SIAPEN não importada</span>`) + `</div>`;
  }

  function item(it) {
    const conta = (it.conta || []).length || it.fundamento
      ? `<details><summary>Ver a conta e o fundamento</summary>${(it.conta || []).length ? `<div class="conta">${it.conta.map(esc).join("<br>")}</div>` : ""}` +
        `${it.fundamento ? `<div class="fund">${esc(it.fundamento)}</div>` : ""}</details>` : "";
    return `<div class="item ${esc(it.nivel)}"><div class="l1"><span class="ic" aria-hidden="true">${FORMA[it.nivel] || ""}</span>` +
      `<span class="t">${esc(it.titulo)}</span>${it.data ? `<span class="d">${esc(it.data)}</span>` : ""}</div>` +
      `${it.linha ? `<div class="l2">${esc(it.linha)}</div>` : ""}` +
      `${it.conferir ? `<div class="conf"><b>A conferir:</b> ${esc(it.conferir)}</div>` : ""}${conta}</div>`;
  }

  function corpo(res) {
    const p = res.painel || {};
    let h = "";
    for (const g of p.grupos || []) {
      h += `<h2 class="grupo">${esc(g.rotulo)}</h2>` + g.itens.map(item).join("");
    }
    if (!(p.grupos || []).length) h += `<p class="vazio">Nada pede atenção neste processo.</p>`;
    h += `<h2 class="grupo">Penas e prazos</h2><div class="duas">` + (p.prazos || []).map((x) =>
      `<div class="mini"><div class="r">${esc(x.rotulo)}</div><div class="v">${esc(x.valor)}</div><div class="s">${esc(x.sub)}</div></div>`).join("") + `</div>`;
    if ((p.nao_cabe || []).length) {
      h += `<h2 class="grupo">Não cabe</h2><details class="naocabe"><summary>${p.nao_cabe.length} ${p.nao_cabe.length === 1 ? "hipótese afastada" : "hipóteses afastadas"} (ver motivos)</summary><ul>` +
        p.nao_cabe.map((x) => `<li><b>${esc(x.titulo)}</b>: ${esc(x.motivo)}</li>`).join("") + `</ul></details>`;
    }
    return h;
  }

  // mensagem para os estados sem análise
  const AVISO = {
    sem_apto: ["Abra o APTO neste computador", "O painel usa os dados e as regras do APTO aberto. Com o APTO aberto, clique em Atualizar."],
    fora_da_base: ["Processo fora da base aberta no APTO", "Abra o RSPE deste processo no APTO (a extensão já salva o RSPE ao abrir o processo, se o automático estiver ligado) e clique em Atualizar."],
    erro: ["Não foi possível montar a análise", ""],
  };

  function html(res) {
    if (!res || res.estado === "carregando") {
      return `<div class="carregando" role="status"><div class="barra"></div><div class="barra curta"></div><div class="barra"></div>` +
        `<p>Calculando com o motor do APTO${res && res.primeira ? " (a primeira vez leva alguns segundos)" : ""}…</p></div>`;
    }
    if (AVISO[res.estado]) {
      const [t, d] = AVISO[res.estado];
      const extra = res.estado === "fora_da_base" && res.base ? ` Base aberta: ${esc(res.base)}.` : "";
      return `<div class="aviso" role="status"><b>${esc(t)}</b><p>${esc(res.motivo && res.estado === "erro" ? res.motivo : d)}${extra}</p></div>`;
    }
    return selo(res) + fonte(res) + `<div class="lista">${corpo(res)}</div>`;
  }

  // resumo em texto (botão Copiar resumo)
  function resumo(res) {
    const p = res.painel || {};
    const L = [`APTO · ${p.processo || ""} · ${p.nome || ""} · referência ${p.hoje || ""}`];
    for (const g of p.grupos || []) {
      L.push("", g.rotulo.toUpperCase());
      for (const it of g.itens) L.push(`${FORMA[it.nivel] || "-"} ${it.titulo}${it.data ? " (" + it.data + ")" : ""}${it.linha ? ": " + it.linha : ""}${it.conferir ? " · a conferir: " + it.conferir : ""}`);
    }
    if ((p.nao_cabe || []).length) {
      L.push("", "NÃO CABE");
      for (const x of p.nao_cabe) L.push(`- ${x.titulo}: ${x.motivo}`);
    }
    L.push("", res.estado === "confere" ? "Confere com o APTO (mesmo resultado)." : "Atenção: conferir no APTO.");
    return L.join("\n");
  }

  const api = { esc, html, resumo, FORMA };
  if (typeof module === "object" && module.exports) module.exports = api;
  else raiz.APTO_PAINEL_CORE = api;
})(typeof self !== "undefined" ? self : this);
