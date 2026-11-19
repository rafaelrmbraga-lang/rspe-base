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

  // origem dos dados e a ficha disciplinar: carregar (botão ou arrastar o PDF), ou a lida (data, trocar, retirar)
  function topo(p, res) {
    const fi = p.ficha_info;
    const carregada = res && res.fichaCarregada;
    let fic;
    if (p.ficha && fi) {
      // uma linha só: a ficha lida, a data e as ações (a origem fica no título, para quem passar o mouse ou o leitor de tela)
      const quando = fi.impressa ? esc(fi.impressa) + (fi.dias == null ? "" : fi.dias <= 0 ? " (hoje)" : " (há " + fi.dias + (fi.dias === 1 ? " dia" : " dias") + ")") : "sem data";
      const origem = carregada ? "carregada no painel" : "aberta no SIAPEN nesta sessão";
      fic = `<div class="ficha curta ${fi.velha ? "amarelo" : "verde"}" title="Ficha ${origem}">${fi.velha ? ICO.amarelo : ICO.verde}` +
        `<span class="ft">Ficha SIAPEN · ${quando}<span class="vh">, ${origem}</span></span>` +
        `<span class="ficha-acoes"><button type="button" class="lnk" data-acao="ficha-carregar">Trocar</button>` +
        (carregada ? `<button type="button" class="lnk" data-acao="ficha-retirar">Retirar</button>` : "") + `</span></div>`;
    } else {
      fic = `<div class="ficha amarelo">${ICO.amarelo}<span>Ficha disciplinar não lida: o que depende dela fica para conferir` +
        `<small>Arraste o PDF da ficha do SIAPEN para cá, ou abra a ficha no SIAPEN.</small></span>` +
        `<span class="ficha-acoes"><button type="button" class="btn-f" data-acao="ficha-carregar">Carregar a ficha (PDF)</button></span></div>`;
    }
    return `<div class="fonte" role="note"><span>Regras do APTO sobre o relatório da situação processual do SEEU · referência ${esc(p.hoje || "")}</span></div>` + fic;
  }

  // alertas: o destaque do painel, um cartão por ponto a conferir; cada um copia o seu fundamento (título, conta e base legal)
  function alerta(it, i) {
    const temConta = (it.conta || []).length || it.fundamento;
    return `<li class="al" data-id="${esc(it.id)}" tabindex="-1"><div class="l1"><span class="ic">${ICO.amarelo}</span><span class="t">${esc(it.titulo)}</span>${it.valor ? `<span class="v">${esc(it.valor)}</span>` : ""}</div>` +
      `${it.motivo ? `<div class="m">${esc(it.motivo)}</div>` : ""}` +
      `${it.conferir ? `<div class="conf"><b>Conferir:</b> ${esc(it.conferir)}</div>` : ""}` +
      `<div class="al-pe">` + (temConta ? `<details><summary>Conta e fundamento</summary>${(it.conta || []).length ? `<div class="conta">${it.conta.map(esc).join("<br>")}</div>` : ""}` +
        `${it.fundamento ? `<div class="fund">${esc(it.fundamento)}</div>` : ""}</details>` : "") +
      `<button type="button" class="lnk copiar-f" data-acao="copiar-fund" data-i="${i}" aria-label="Copiar o fundamento: ${esc(it.titulo)}">Copiar fundamento</button></div></li>`;
  }

  // fundamento de um alerta pronto para colar na petição: a exposição em texto corrido (a conta do APTO, sem as marcas do painel -
  // "Conferir:", numeração, "O que houve:") e, no fim, a base legal; as instruções ("pedir ...") viram o requerimento
  function paraPeticao(t) {
    return String(t || "").trim()
      .replace(/^\d+\)\s*/, "")
      .replace(/\b(O que houve|Por que importa):\s*/g, "")
      .replace(/\bO que pedir:\s*/g, "Requer-se ")
      .replace(/(^|[.:;]\s+)[Pp]edir (que|o|a|os|as)\b/g, (m0, a, b) => a + "requer-se " + b)
      .replace(/\s*-\s*conferir[^.]*$/i, "")
      .replace(/(^|[.!?]\s+)(\p{Ll})/gu, (m0, a, b) => a + b.toUpperCase())   // início de frase em maiúscula
      .replace(/([^.!?])$/, "$1.");
  }
  function fundamento(it) {
    const corpo = ((it.conta || []).length ? it.conta : [it.motivo]).map(paraPeticao).filter((x) => x && x !== ".");
    const base = String(it.fundamento || "").trim().replace(/\.$/, "");
    return corpo.join("\n\n") + (base ? (corpo.length ? "\n\n" : "") + "Fundamento: " + base + "." : "");
  }

  // diagnóstico da leitura (só a estrutura: onde o painel roda, se achou o link do relatório, a resposta do SEEU; nenhum dado
  // do processo ou da pessoa), num campo de texto que dá para selecionar mesmo se o copiar for bloqueado
  function diagnostico(dg, ext) {
    const txt = JSON.stringify({ extensao: ext || "", diagnostico: dg || null }, null, 1);
    return `<div class="diag"><p>Para ajustar a leitura ao SEEU, copie o diagnóstico e envie a quem mantém a extensão. Ele traz só a ` +
      `estrutura da leitura (onde o painel roda, se o link do relatório foi achado e a resposta do SEEU), sem nenhum dado do processo ou da pessoa.</p>` +
      `<textarea readonly rows="5" aria-label="Diagnóstico da leitura" spellcheck="false">${esc(txt)}</textarea>` +
      `<button type="button" class="btn-f" data-acao="copiar-diag">Copiar o diagnóstico</button></div>`;
  }

  function corpo(res) {
    const p = res.painel || {};
    // pena, regime e marcos ficam no SEEU (capa e chips abaixo do nº do processo): aqui, só o aviso da execução, se houver
    const av = (p.pena || {}).aviso;
    let h = topo(p, res) + (av ? `<p class="aviso-exec solto">${esc(av)}</p>` : "");
    const A = p.alertas || [];
    h += `<section aria-labelledby="s-al"><h2 id="s-al" class="h-al">Para conferir${A.length ? ` <span class="cnt">${A.length}</span>` : ""}</h2>` +
      (A.length ? `<ul class="alertas">${A.map((a, i) => alerta(a, i)).join("")}</ul>` : `<p class="vazio">${ICO.verde} Nada para conferir.</p>`) + `</section>`;
    if ((p.confere || []).length) {
      h += `<section aria-labelledby="s-ok"><h2 id="s-ok">Confere</h2><ul class="confere">` +
        p.confere.map((it) => `<li data-id="${esc(it.id)}" tabindex="-1"><span class="ic">${ICO.verde}</span><span class="t">${esc(it.titulo)}</span>${it.valor ? `<span class="v">${esc(it.valor)}</span>` : ""}</li>`).join("") + `</ul></section>`;
    }
    if ((p.crimes || []).length) {
      h += `<section aria-labelledby="s-crimes"><h2 id="s-crimes">Crimes em execução</h2><ul class="crimes">` +
        p.crimes.map((c) => `<li><b>${esc(c.texto)}</b>${c.pena ? ` · ${esc(c.pena)}` : ""}${c.hediondo && /verificar/.test(c.hediondo) ? ` <span class="selo-st amarelo">${ICO.amarelo}hediondo a conferir</span>` : ""}</li>`).join("") + `</ul></section>`;
    }
    if ((p.observacoes || []).length) {
      h += `<details class="naocabe"><summary>Observações de cadastro, sem efeito para o assistido: ${p.observacoes.length}</summary><ul>` +
        p.observacoes.map((x) => `<li><b>${esc(x.titulo)}</b>${(x.conta || []).length ? ": " + esc(x.conta.join(" ")) : ""}</li>`).join("") + `</ul></details>`;
    }
    if ((p.nao_cabe || []).length) {
      h += `<details class="naocabe"><summary>Não cabe: ${p.nao_cabe.length} ${p.nao_cabe.length === 1 ? "hipótese afastada" : "hipóteses afastadas"}</summary><ul>` +
        p.nao_cabe.map((x) => `<li><b>${esc(x.titulo)}</b>: ${esc(x.motivo)}</li>`).join("") + `</ul></details>`;
    }
    return h;
  }

  // sem o relatório lido por inteiro, o painel não conclui nada: só diz o que faltou e como resolver
  const AVISO = {
    sem_dados: ["Não foi possível ler o processo", "O SEEU não entregou o relatório da situação processual. Recarregue a página do SEEU e clique em Ler de novo."],
    sem_rspe: ["Relatório do processo não encontrado", ""],
    nao_rspe: ["O SEEU devolveu outro documento", "O PDF recebido não é o relatório da situação processual executória."],
    erro: ["Não foi possível montar a análise", ""],
  };

  function html(res) {
    if (!res || res.estado === "carregando") {
      return `<div class="carregando" aria-busy="true" role="status"><div class="sk alto"></div><div class="sk"></div><div class="sk"></div><div class="sk curto"></div>` +
        `<p>${res && res.etapa ? esc(res.etapa) : "Lendo as abas do processo"}${res && res.primeira ? " (na primeira vez, o motor do APTO leva alguns segundos para carregar)" : ""}…</p></div>`;
    }
    if (AVISO[res.estado]) {
      const [t, d] = AVISO[res.estado];
      return `<div class="aviso" role="status"><b>${esc(t)}</b><p>${esc(res.motivo || d)}</p>` +
        ((res.faltou || []).length ? `<p class="aviso-f">Não achado: ${res.faltou.map(esc).join("; ")}.</p>` : "") +
        `<p class="aviso-f">Nenhuma conclusão foi tirada: sem o relatório lido, nada é calculado.</p>` +
        (res.diag ? diagnostico(res.diag, res.ext) : "") + `</div>`;
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

  // ---------- chips na página do SEEU (logo abaixo de "Execução nº"; e na barra fixa ao rolar): regime e marcos numa faixa
  // única de segmentos (rótulo pequeno em cima, data embaixo), o que falta conferir e, na barra fixa, o nº e o nome com copiar.
  // Cada segmento é um botão: o detalhe (quanto falta, fração) abre no clique - nada só no mouse. Estado: ícone + texto.
  const CICO = {
    proximo: '<svg viewBox="0 0 24 24" width="12" height="12" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2.6"/><path d="M12 7v5l3 2" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/></svg>',
    vencida: '<svg viewBox="0 0 24 24" width="12" height="12" aria-hidden="true" focusable="false"><path d="M12 5v9" fill="none" stroke="currentColor" stroke-width="3.4" stroke-linecap="round"/><circle cx="12" cy="19" r="2" fill="currentColor"/></svg>',
    copiar: '<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true" focusable="false"><rect x="8" y="8" width="12" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="2.2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3" fill="none" stroke="currentColor" stroke-width="2.2"/></svg>',
  };
  const SVG = (d, extra) => `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"${extra || ""}>${d}</svg>`;
  const BICO = {
    st: SVG('<path d="M14 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4"/><path d="M9 16l-4-4 4-4"/><path d="M5 12h10"/>'),   // saída temporária (APTO)
    pa: SVG('<path d="M3 20h5v-5h5v-5h5V5h3"/>', ' stroke-width="2.4"'),                                       // progressão antecipada (APTO)
    ind: SVG('<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 7.6-1.7"/><circle cx="12" cy="16" r="1.3" fill="currentColor"/>'),  // indulto: cadeado aberto
    com: SVG('<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M8 3v4M16 3v4M3.5 10h17"/><path d="M9 15h6"/>'),   // comutação: menos tempo de pena (calendário com "menos")
    ext: SVG('<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>'),                                          // extinção
    presc: SVG('<path d="M6 3h12M6 21h12"/><path d="M7 3c0 5 10 6 10 9s-10 4-10 9"/><path d="M17 3c0 5-10 6-10 9"/>'),   // prescrição: ampulheta
    rem: '<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" aria-hidden="true" focusable="false"><path d="M3 5.5v13l8.5-6.5zM12.5 5.5v13l8.5-6.5z"/></svg>',  // remição pendente (APTO)
  };
  const CROT = { db: "Data-base", prog: "Progressão", liv: "Livramento", term: "Término" };
  function dadosChips(res) {
    const p = (res && res.painel) || {};
    return { processo: p.processo || "", nome: p.nome || "", regime: p.regime || (p.pena || {}).regime || "", conferir: (p.contagem || {}).amarelo || 0,
      icones: (p.icones || []).map((x) => ({ tipo: x.tipo, rotulo: x.rotulo, estado: x.estado, alvo: x.alvo })),
      marcos: (p.marcos || []).map((m) => ({ id: m.id, rotulo: m.rotulo, data: m.data, quando: m.quando, destaque: m.destaque, alerta: m.alerta,
        detalhe: [m.extra, ...(m.conta || [])].filter(Boolean) })) };
  }
  function chips(d, fixa) {
    const reg = String(d.regime || "").replace(/\s*-\s*ATIVO$/i, "");
    const seg = (d.marcos || []).filter((m) => m.data && m.data !== "—").map((m, i) => {
      const sub = m.id === "prog" && /ao\s+(\S+)/i.test(m.rotulo) ? " · " + /ao\s+(\S+)/i.exec(m.rotulo)[1] : "";
      // progressão/livramento: vencida (data já passou) = vermelho com "!"; a até 60 dias = âmbar com relógio; senão, branco
      const dest = m.destaque === "atingida" ? "vencida" : m.destaque;
      const est = dest ? `<span class="est ${esc(dest)}">${CICO[dest] || ""}<span class="vh">${dest === "proximo" ? "a menos de 60 dias" : "vencida"}</span></span>` : "";
      const nome = `${esc(m.rotulo)}: ${esc(m.data)}${m.quando ? ", " + esc(m.quando) : ""}${m.alerta ? ", com ponto a conferir" : ""}`;
      return `<button type="button" class="sg${dest ? " " + esc(dest) : ""}" data-chip="${i}" aria-expanded="false" aria-label="${nome}">` +
        `<span class="rot">${esc(CROT[m.id] || m.rotulo)}${esc(sub)}${m.alerta ? '<b class="mk" aria-hidden="true">!</b>' : ""}</span>` +
        `<span class="dt">${esc(m.data)}${est}</span></button>`;
    }).join("");
    const det = (d.marcos || []).filter((m) => m.data && m.data !== "—").map((m, i) =>
      `<div class="det" data-det="${i}" hidden><b>${esc(m.rotulo)}</b> · ${esc(m.data)}${m.quando ? " · " + esc(m.quando) : ""}` +
      `${(m.detalhe || []).length ? "<br>" + m.detalhe.map(esc).join(" · ") : ""}</div>`).join("");
    const id = fixa ? `<span class="id"><span class="num">${esc(d.processo)}</span>` +
      `<button type="button" class="cp" data-copiar="processo" aria-label="Copiar o número do processo">${CICO.copiar}<span>Nº</span></button>` +
      `<span class="nm" title="${esc(d.nome)}">${esc(d.nome)}</span>` +
      `<button type="button" class="cp" data-copiar="nome" aria-label="Copiar o nome do assistido">${CICO.copiar}<span>Nome</span></button></span>` :
      `<span class="id"><button type="button" class="cp" data-copiar="processo" aria-label="Copiar o número do processo">${CICO.copiar}<span>Nº</span></button>` +
      `<button type="button" class="cp" data-copiar="nome" aria-label="Copiar o nome do assistido">${CICO.copiar}<span>Nome</span></button></span>`;
    // na barra fixa, o nº e o nome vêm primeiro (é o que se copia); abaixo do nº no SEEU, as datas primeiro e o copiar no fim
    // benefícios: ícone + nome; verde = cabe, âmbar = a conferir (o nome do estado vai para o leitor de tela); o clique abre o cartão no painel
    const bens = (d.icones || []).filter((x) => BICO[x.tipo]).map((x) =>
      `<button type="button" class="ben ${x.estado === "ok" ? "ok" : "q"}" data-focar="${esc(x.alvo)}" aria-label="${esc(x.rotulo)}: ${x.estado === "ok" ? "cabe" : "a conferir"}. Ver no painel">` +
      `${BICO[x.tipo]}<span>${esc(x.rotulo)}</span></button>`).join("");
    const faixa = `<span class="seg">${reg ? `<span class="sg reg"><span class="rot">Regime</span><span class="dt">${esc(reg)}</span></span>` : ""}${seg}</span>` +
      (bens ? `<span class="bens" role="group" aria-label="Benefícios">${bens}</span>` : "") +
      (d.conferir ? `<button type="button" class="conf" data-abrir="1" aria-label="Abrir o painel: ${d.conferir} ${d.conferir === 1 ? "ponto" : "pontos"} para conferir">` +
        `<b aria-hidden="true">!</b>${d.conferir} conferir</button>` : "");
    return `<div class="faixa${fixa ? " fixa" : ""}" role="group" aria-label="Marcos do APTO">${fixa ? id + faixa : faixa + id}</div>${det}`;
  }

  const api = { esc, html, resumo, fundamento, chips, dadosChips, ICO };
  if (typeof module === "object" && module.exports) module.exports = api;
  else raiz.APTO_PAINEL_CORE = api;
})(typeof self !== "undefined" ? self : this);
