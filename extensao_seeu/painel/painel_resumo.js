// APTO - painel no SEEU: resumo para o assistido (linguagem simples, CNJ). A mesma conferência da janela do APTO (ui.html,
// resumoTela/resumoLer/resumoPdf): cada frase pode ser corrigida ou desmarcada, "+ frase", as providências que a Defensoria
// vai adotar viram frases simples, e o verso (trabalho e estudo da ficha) é opcional. A diferença: antes do PDF, a pessoa
// diz ONDE é o atendimento - na unidade prisional o resumo leva o canhoto (pedido do próximo atendimento); fora dela, não.
// Funções puras (sem Chrome): usadas por painel.js e pelos testes em node. Todo texto passa por esc().
(function (raiz) {
  "use strict";
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  // providência marcada -> frases dos próximos benefícios que deixam de sair (o "vamos pedir" substitui o "a Defensoria vai analisar")
  const PREFIXO = { ped_prog: "Semiaberto|Aberto|Progressão", ped_liv: "Livramento condicional", ped_ind: "Indulto", ped_com: "Comutação" };

  function onde(d) {
    const op = (v, t, s) => `<label class="res-onde${d.onde === v ? " on" : ""}"><input type="radio" name="resOnde" value="${v}" ${d.onde === v ? "checked" : ""}>` +
      `<span><b>${t}</b><small>${s}</small></span></label>`;
    return `<fieldset class="res-bloco"><legend>Onde é este atendimento?</legend>` +
      op("unidade", "Na unidade prisional", "o resumo leva o canhoto para o assistido pedir o próximo atendimento") +
      op("fora", "Fora da unidade", "na Defensoria, no fórum, por telefone ou vídeo: sem o canhoto") +
      (d.onde === "unidade" ? `<div class="res-campos"><label>Data do atendimento<input id="resData" value="${esc(d.data_atend || "")}" placeholder="dd/mm/aaaa" inputmode="numeric"></label>` +
        `<label>Unidade<input id="resUn" value="${esc(d.unidade || "")}" placeholder="unidade prisional"></label></div>` : "") +
      `</fieldset>`;
  }

  function secoes(d) {
    return (d.secoes || []).map((s, i) => {
      if (s.id === "prov") {
        return `<section class="res-bloco"><h3>O que a Defensoria vai fazer <small>marque o que será feito; cada item vira uma frase simples</small></h3>` +
          `<div class="res-provs">${(d.providencias || []).map((p) => `<label title="${esc(p.frase)}"><input type="checkbox" data-prov="${esc(p.id)}" ${p.marcado ? "checked" : ""}> ${esc(p.rot)}</label>`).join("")}</div>` +
          `<textarea id="resOutro" rows="2" placeholder="Outra providência (como vai sair no papel; uma frase por linha)">${esc(d.outro || "")}</textarea></section>`;
      }
      return `<section class="res-bloco"><h3>${esc(s.titulo)}</h3>` +
        (s.itens || []).map((x, k) => `<label class="res-it" data-s="${i}" data-k="${k}"><input type="checkbox" ${(s._off || {})[k] ? "" : "checked"} aria-label="Imprimir esta frase">` +
          `<textarea rows="${Math.max(1, Math.ceil(String(x).length / 48))}">${esc(x)}</textarea></label>`).join("") +
        `<button type="button" class="lnk" data-mais="${i}">+ frase</button></section>`;
    }).join("");
  }

  function verso(d) {
    const V = (d.verso || {}).itens || [];
    if (!V.length) return "";
    const m = d.verso_modo || "";
    const op = (v, t) => `<label class="res-r"><input type="radio" name="resVs" value="${v}" ${m === v ? "checked" : ""}> ${t}</label>`;
    return `<fieldset class="res-bloco" id="resVerso"><legend>Verso (2ª folha): trabalho e estudo da ficha</legend>` +
      op("", "Não imprimir") + op("remicao", "Com os dias descontados da pena") + op("historico", "Só o histórico de trabalho e estudo") +
      (m ? V.map((x) => `<label class="res-r"><input type="checkbox" data-v="${esc(x.id)}" ${x._off ? "" : "checked"}> <b>${x.grupo === "trabalho" ? "Trabalho" : "Estudo"} · ${esc(x.onde)}</b> ${esc(x.per)} <small>${esc(x.sit)}</small></label>`).join("") +
        `<small>Imprima frente e verso.</small>` : "") + `</fieldset>`;
  }

  function tela(d) {
    return `<div class="res">` +
      `<p class="res-intro">Texto em linguagem simples, montado com o cálculo do APTO. Confira, corrija ou desmarque cada frase. ` +
      `Data que ainda está para conferir sai como "a Defensoria está conferindo".${d.barra ? ` Pena cumprida: <b>${esc(d.barra.pct)}%</b>.` : ""}</p>` +
      onde(d) + secoes(d) + verso(d) + `</div>`;
  }

  // lê a tela de volta para o resumo (como ui.resumoLer)
  function ler(d, raizEl) {
    const q = (s) => raizEl.querySelector(s);
    raizEl.querySelectorAll("[data-s]").forEach((el) => {
      const sec = d.secoes[+el.dataset.s], k = +el.dataset.k;
      sec._off = sec._off || {};
      sec.itens[k] = el.querySelector("textarea").value;
      sec._off[k] = !el.querySelector("input").checked;
    });
    (d.providencias || []).forEach((p) => { const el = q(`[data-prov="${p.id}"]`); if (el) p.marcado = el.checked; });
    if (q("#resOutro")) d.outro = q("#resOutro").value;
    if (q("#resUn")) d.unidade = q("#resUn").value;
    if (q("#resData")) d.data_atend = q("#resData").value;
    const o = q("input[name=resOnde]:checked");
    if (o) d.onde = o.value;
    const vs = q("input[name=resVs]:checked");
    if (vs) d.verso_modo = vs.value;
    raizEl.querySelectorAll("[data-v]").forEach((el) => { const x = ((d.verso || {}).itens || []).find((y) => y.id === el.dataset.v); if (x) x._off = !el.checked; });
    return d;
  }

  // providência marcada: as frases do mesmo benefício saem dos "próximos benefícios" (como ui.resumoProv)
  function prov(d, id, on) {
    const pre = PREFIXO[id];
    const S = (d.secoes || []).find((s) => s.id === "direitos");
    if (!pre || !S) return d;
    const rx = new RegExp("^(" + pre + ")");
    S._off = S._off || {};
    S.itens.forEach((x, k) => { if (rx.test(String(x))) S._off[k] = on; });
    return d;
  }

  // o que vai para o gerador do APTO (como ui.resumoPdf): só as frases marcadas; providências em frases com ponto final
  function saida(d) {
    const fr = (t) => { t = String(t || "").trim(); if (!t) return ""; t = t[0].toUpperCase() + t.slice(1); return /[.!?]$/.test(t) ? t : t + "."; };
    const atd = (d.providencias || []).filter((p) => p.marcado).map((p) => p.frase).concat(String(d.outro || "").split(/\n+/).map(fr)).filter(Boolean);
    const out = Object.assign({}, d, {
      secoes: (d.secoes || []).map((s) => ({ id: s.id, titulo: s.titulo, itens: s.id === "prov" ? atd : (s.itens || []).filter((x, k) => !(s._off || {})[k] && String(x).trim()) })),
      verso: Object.assign({}, d.verso || {}, { itens: ((d.verso || {}).itens || []).filter((x) => !x._off) }),
    });
    delete out.onde;
    return out;
  }

  const api = { tela, ler, prov, saida, esc };
  if (typeof module === "object" && module.exports) module.exports = api;
  else raiz.APTO_RESUMO = api;
})(typeof self !== "undefined" ? self : this);
