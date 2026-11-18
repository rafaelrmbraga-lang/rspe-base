// APTO - Atendimentos: leitura do SAP da Defensoria (capital.defensoria.ms.def.br/sap), para a função Atendimentos do APTO.
// Lê a fila "Assistidos em Espera" e o "Fato Narrado". Nunca digita, salva ou registra nada no SAP.
// O que lê vai para o APTO aberto neste computador (127.0.0.1, pelo service worker); com o APTO fechado, fica guardado na
// extensão e é entregue quando ele abrir. Os pedidos da tela do APTO (Chamar, Ver no SAP, Ler a fila) chegam pela mesma via:
// a extensão pergunta ao APTO a cada 2 s, só enquanto a fila está nesta aba.
// "Ler a fila de hoje" faz o mesmo que você faria para LER: seleciona cada linha da fila, clica em "Fato Narrado",
// lê a janela e a fecha pelo X (fechar só para o relógio de salvamento automático do SAP; nada é salvo).
(function () {
  "use strict";
  if (window.__aptoAtd) return;
  window.__aptoAtd = true;
  const A = self.ATD;
  const ext = A.ext;

  const txt = (el) => (el ? (el.innerText || el.textContent || "") : "").replace(/ /g, " ");
  const linha = (s) => String(s || "").replace(/\s+/g, " ").trim();
  const dormir = (ms) => new Promise((r) => setTimeout(r, ms));
  const byId = (id) => document.getElementById(id);
  const visivel = (el) => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length) && getComputedStyle(el).visibility !== "hidden");
  async function esperar(fn, ms, passo) {
    const fim = Date.now() + ms;
    while (Date.now() < fim) {
      let v = null;
      try { v = fn(); } catch (e) { v = null; }
      if (v) return v;
      await dormir(passo || 200);
    }
    return null;
  }
  async function estavel(sig, ms) {
    let ultimo = null, desde = Date.now();
    const fim = Date.now() + (ms || 8000);
    while (Date.now() < fim) {
      let s = "";
      try { s = sig(); } catch (e) { s = ""; }
      if (s !== ultimo) { ultimo = s; desde = Date.now(); } else if (Date.now() - desde >= 700) return true;
      await dormir(150);
    }
    return false;
  }

  // títulos das colunas de uma tabela do PrimeFaces (a tabela rolável tem o cabeçalho numa tabela e as linhas em outra)
  function titulos(raiz) {
    const thead = raiz.querySelector("thead");
    if (!thead) return [];
    return [...thead.querySelectorAll("th")].map((th) => {
      const t = th.querySelector(".ui-column-title");
      return A.norm(t ? t.textContent : th.textContent);
    });
  }

  // ---------- fila (Assistidos em Espera) ----------
  function acharFila() {
    let c = byId("form_espera:listaAssistidoEspera");
    if (!c) {
      for (const dt of document.querySelectorAll(".ui-datatable")) {
        const h = titulos(dt);
        if (h.some((x) => x.startsWith("NOME ASSISTIDO")) && h.some((x) => x.startsWith("DATA DESIG"))) { c = dt; break; }
      }
    }
    if (!c) return null;
    const corpo = c.querySelector("tbody[id$='_data']");
    return corpo ? { c, corpo, h: titulos(c) } : null;
  }
  function lerFila() {
    const f = acharFila();
    if (!f) return null;
    const col = (re, padrao) => { const i = f.h.findIndex((x) => re.test(x)); return i >= 0 ? i : padrao; };
    const c = { nome: col(/^NOME ASSISTIDO/, 0), chegada: col(/^CHEGADA/, 2), unid: 3, status: col(/^STATUS/, 5), desig: col(/^DATA DESIG/, 6) };
    const r = [];
    for (const tr of f.corpo.querySelectorAll(":scope > tr")) {
      if (tr.classList.contains("ui-datatable-empty-message")) continue;
      const td = tr.children;
      if (td.length < 5) continue;
      const span = td[c.nome].querySelector("span");
      let nome = linha(span ? span.textContent : txt(td[c.nome]).replace(/(\s+[PSRVD])+\s*$/, ""));
      const desig = td[c.desig] ? txt(td[c.desig]) : "";
      const data = A.isoDeBr(desig);
      if (!nome || !data) continue;
      const tipo = linha((td[c.nome].querySelector("[id$='idtoolTipoAtendimento']") || {}).textContent || "");
      r.push({
        nome, data, hora: A.horaDe(desig), rk: tr.getAttribute("data-rk") || "",
        forma: tipo === "V" ? "virtual" : tipo === "P" ? "presencial" : "",
        chegada: td[c.chegada] ? A.horaDe(txt(td[c.chegada])) || linha(txt(td[c.chegada])) : "",
        unidade: td[c.unid] ? linha(txt(td[c.unid])) : "",
        statusSap: td[c.status] ? linha(txt(td[c.status])) : "",
      });
    }
    return r;
  }
  function linhaDaFila(rk) {
    const f = acharFila();
    return f ? f.corpo.querySelector(`:scope > tr[data-rk="${CSS.escape(rk)}"]`) : null;
  }

  // ---------- quadro "Registrar Atendimento" ----------
  const nomeRegistrar = () => linha((byId("form_registra:pHeaderFormRegistra") || {}).textContent || "");
  function formaRegistrar() {
    const r = document.querySelector("[id^='form_registra'] input[type=radio][value=VIRTUAL]:checked, [id^='form_registra'] input[type=radio][value=PRESENCIAL]:checked");
    return r ? (r.value === "VIRTUAL" ? "virtual" : "presencial") : "";
  }
  function botaoFato() {
    return [...document.querySelectorAll("[id^='form_registra'] button, button[id^='form_registra']")].find((b) => linha(b.textContent) === "Fato Narrado") || null;
  }

  // ---------- Fato Narrado ----------
  const dialogoFato = () => byId("form_dialogFato:dialogFato");
  function tabelaFato() {
    let t = byId("form_dialogFato:tbFato") || document.querySelector("[id$='tbFatoAtendimento']");
    if (!t) {
      for (const dt of document.querySelectorAll(".ui-datatable")) {
        const h = titulos(dt);
        if (h.includes("FATO NARRADO") && h.some((x) => x.startsWith("DATA CADASTRO"))) { t = dt; break; }
      }
    }
    return t;
  }
  function nomeDoFato(t) {
    const tit = byId("form_dialogFato:dialogFato_title");
    if (tit) {
      const v = [...tit.querySelectorAll("span")].map((s) => linha(s.textContent)).find((s) => s && !/^Assistido:?$/i.test(s));
      if (v) return v;
    }
    const dlg = t && t.closest(".ui-dialog");
    if (dlg) {
      const m = /Assistido:\s*([^\n]+)/i.exec(txt(dlg.querySelector(".ui-dialog-titlebar")));
      if (m) return linha(m[1]);
    }
    return nomeRegistrar();
  }
  const RE_FONE = /\(?\d{2}\)?\s*9?\d{4}[-\s.]?\d{4}/g;
  function interpretarFato(texto) {
    const linhas = String(texto || "").split(/\r?\n/).map(linha).filter(Boolean);
    const tudo = linhas.join("\n");
    let contato = "", quem = "";
    const lt = linhas.find((l) => /telefone|contato|whats/i.test(l) && (RE_FONE.lastIndex = 0, RE_FONE.test(l)));
    RE_FONE.lastIndex = 0;
    if (lt) {
      const resto = lt.replace(/^.*?(telefone( de contato)?|contato|whatsapp)\s*:?\s*/i, "");
      const fones = resto.match(RE_FONE) || [];
      const pessoa = linha(resto.replace(RE_FONE, " ").replace(/\([^)]*\)/g, " ").replace(/[\/–-]+/g, " "));
      // parênteses com letras (o "(67)" do DDD não conta): "(pai - somente ligação)"
      const par = [...resto.matchAll(/\(([^)]*)\)/g)].map((m) => m[1]).filter((x) => /[a-zà-ú]/i.test(x)).join(" ");
      quem = A.parentesco(par) || A.parentesco(pessoa);
      contato = linha(resto);
      if (!contato) contato = fones.map(linha).join(" / ");
    }
    const virtual = /via (telefone|virtual|whats|v[ií]deo|liga|plataforma)/i.test(tudo);
    const pedido = linhas.filter((l) => !/^atendimento solicitado/i.test(l) && l !== lt && !/^processo\s*:/i.test(l)).join(" ");
    return { processos: A.cnjsNoTexto(tudo), contato, quem, virtual, pedido };
  }
  function lerFatos() {
    const t = tabelaFato();
    if (!t) return null;
    const corpo = t.querySelector("tbody[id$='_data']") || t.querySelector("tbody");
    if (!corpo) return null;
    const h = titulos(t);
    const iData = h.findIndex((x) => x.startsWith("DATA CADASTRO"));
    const iDef = h.findIndex((x) => x.startsWith("DEFENSOR"));
    const iFato = h.findIndex((x) => x === "FATO NARRADO");
    const itens = [];
    for (const tr of corpo.querySelectorAll(":scope > tr")) {
      if (tr.classList.contains("ui-expanded-row-content") || tr.classList.contains("ui-datatable-empty-message")) continue;
      const td = tr.children;
      const dataTxt = iData >= 0 && td[iData] ? txt(td[iData]) : "";
      let fato = iFato >= 0 && td[iFato] ? txt(td[iFato]) : "";
      const prox = tr.nextElementSibling;
      if (prox && prox.classList.contains("ui-expanded-row-content")) fato = (fato + "\n" + txt(prox)).trim();
      if (!A.isoDeBr(dataTxt) || !fato.trim()) continue;
      itens.push({ dataTxt: linha(dataTxt), defensor: iDef >= 0 && td[iDef] ? linha(txt(td[iDef])) : "", texto: fato.trim() });
    }
    const nome = nomeDoFato(t);
    if (!nome) return null;
    if (!itens.length) return { nome, fato: null, vazio: corpo.querySelector(".ui-datatable-empty-message") != null };
    const chave = (s) => { const m = /(\d{2})\/(\d{2})\/(\d{4})(?:\s+(\d{2}):(\d{2}))?/.exec(s); return m ? m[3] + m[2] + m[1] + (m[4] || "00") + (m[5] || "00") : ""; };
    itens.sort((a, b) => chave(b.dataTxt).localeCompare(chave(a.dataTxt)));
    const ult = itens[0];
    const fato = Object.assign({ data: ult.dataTxt, defensor: ult.defensor, texto: ult.texto }, interpretarFato(ult.texto));
    if (!fato.processos.length) fato.processos = [...new Set(itens.flatMap((x) => A.cnjsNoTexto(x.texto)))].slice(0, 2);
    return { nome, fato };
  }

  // ---------- gravação (uma de cada vez) ----------
  let filaGrav = Promise.resolve();
  const emSerie = (fn) => (filaGrav = filaGrav.then(fn).catch((e) => console.warn("[APTO Atendimentos]", e)));
  // (o atendimento do Fato Narrado, o de hoje ou o próximo agendado com esse nome, é achado pelo APTO)
  let resumo = null; // {total, lidos, presentes} do dia, como o APTO informa
  async function enviar(tipo, corpo) {
    let r = null;
    try { r = await ext.runtime.sendMessage(Object.assign({ tipo }, corpo)); } catch (e) { r = { ok: false, erro: String(e.message || e) }; }
    if (r && r.resumo) resumo = r.resumo;
    return r || { ok: false };
  }
  const semApto = (r) => (r && r.offline ? `APTO fechado: ${r.pendentes || 1} leitura(s) guardada(s), entregues quando o APTO abrir` : "");
  function gravarFila(f, msg) {
    return emSerie(async () => {
      const r = await enviar("atdFila", { itens: f });
      selo(msg !== undefined ? msg : semApto(r) || (r && r.novos ? `${r.novos} da fila entraram no APTO` : ""), resumo);
    });
  }
  function gravarFato(fa, forma) {
    return emSerie(async () => {
      const r = await enviar("atdFato", { nome: fa.nome, fato: fa.fato || null, forma: forma || "", fatoLido: new Date().toISOString() });
      selo(lendo ? "" : semApto(r) || `Fato Narrado de ${A.nomeProprio(A.chaveNome(fa.nome))} lido`, resumo);
    });
  }

  // ---------- leitura passiva (o que você abre na tela) ----------
  let sigFila = "", sigFato = "";
  function verificar() {
    if (lendo) return;
    const f = lerFila();
    if (f && f.length) {
      const s = JSON.stringify(f);
      if (s !== sigFila) { sigFila = s; gravarFila(f); }
    }
    const dlg = dialogoFato();
    if (!dlg || visivel(dlg)) {
      const fa = lerFatos();
      if (fa && fa.fato) {
        const s = fa.nome + "|" + fa.fato.data + "|" + fa.fato.texto.length;
        if (s !== sigFato) {
          sigFato = s;
          const forma = A.chaveNome(nomeRegistrar()) === A.chaveNome(fa.nome) ? formaRegistrar() : "";
          gravarFato(fa, forma);
        }
      }
    }
  }

  // ---------- "Ler a fila de hoje": todos os Fatos Narrados, um a um ----------
  let lendo = null;
  async function lerTodos(opc) {
    if (lendo) return { ok: false, motivo: "a leitura já está em andamento" };
    const f = lerFila();
    if (!f) return { ok: false, motivo: "a fila Assistidos em Espera não está nesta aba" };
    const hoje = A.hojeISO();
    const alvo = f.filter((x) => x.rk && (opc && opc.todos ? true : x.data === hoje));
    if (!alvo.length) return { ok: false, motivo: "nenhum assistido com Data Desig. de hoje na fila" };
    lendo = { parar: false };
    await gravarFila(f, "");
    const trSel = acharFila().corpo.querySelector(":scope > tr[aria-selected='true']");
    const selecionado = trSel ? trSel.getAttribute("data-rk") || "" : "";
    const erros = [];
    let ok = 0;
    for (let i = 0; i < alvo.length && !lendo.parar; i++) {
      const p = alvo[i];
      selo(`Lendo ${i + 1} de ${alvo.length}: ${A.nomeProprio(A.chaveNome(p.nome))}…`);
      try {
        const r = await lerUm(p);
        if (r.erro) erros.push(`${A.nomeProprio(A.chaveNome(p.nome))}: ${r.erro}`); else ok++;
        if (r.parar) break;
      } catch (e) { erros.push(`${p.nome}: ${e.message || e}`); }
      await dormir(1200);
    }
    // volta para a linha que estava selecionada antes
    if (selecionado && !lendo.parar) {
      const tr = linhaDaFila(selecionado);
      if (tr && tr.getAttribute("aria-selected") !== "true") { tr.children[0].click(); await dormir(1500); }
    }
    const parou = lendo.parar;
    lendo = null;
    await filaGrav;
    selo(`${parou ? "Interrompido: " : ""}${ok} de ${alvo.length} lidos${erros.length ? " · " + erros.length + " com problema (passe o mouse)" : ""}`, resumo, erros.join("\n"));
    return { ok: true, lidos: ok, total: alvo.length, erros };
  }
  async function lerUm(p) {
    const tr = linhaDaFila(p.rk);
    if (!tr) return { erro: "sumiu da fila" };
    const k = A.chaveNome(p.nome);
    // 1. seleciona a linha (o SAP carrega o quadro Registrar Atendimento)
    if (A.chaveNome(nomeRegistrar()) !== k) {
      tr.children[0].click();
      const ok = await esperar(() => A.chaveNome(nomeRegistrar()) === k, 20000);
      if (!ok) return { erro: "o SAP não carregou o assistido" };
      await dormir(400);
    }
    const forma = formaRegistrar() || p.forma;
    // 2. botão Fato Narrado
    const b = botaoFato();
    if (!b) return { erro: "botão Fato Narrado não achado (o SAP mudou?)", parar: true };
    const dlg0 = dialogoFato();
    b.click();
    const dlg = await esperar(() => { const x = dialogoFato(); return x && visivel(x) ? x : null; }, 20000);
    if (!dlg) { await gravarFato({ nome: p.nome, fato: null }, forma); return { erro: "a janela do Fato Narrado não abriu" }; }
    await esperar(() => A.chaveNome(nomeDoFato(tabelaFato())) === k, 10000);
    const corpo = () => { const t = tabelaFato(); const c = t && t.querySelector("tbody[id$='_data']"); return c ? c.innerHTML : ""; };
    await estavel(corpo, 8000);
    const fa = lerFatos();
    // 3. fecha pelo X (o SAP só para o relógio de salvamento automático; nada é salvo)
    const x = dlg.querySelector(".ui-dialog-titlebar-close");
    if (x) x.click();
    await esperar(() => !visivel(dialogoFato()), 10000);
    if (!fa || A.chaveNome(fa.nome) !== k) { await gravarFato({ nome: p.nome, fato: null }, forma); return { erro: "Fato Narrado não conferiu com o nome" }; }
    await gravarFato(fa, forma);
    void dlg0;
    return { ok: true, semFato: !fa.fato };
  }

  // ---------- selo no canto da página ----------
  let caixa = null, rotulo = null, botao = null;
  // andamento da leitura da fila para a tela do APTO (no máximo um aviso por segundo)
  let ultAviso = 0, estavaLendo = false;
  function avisarLeitura(msg) {
    const agora = Date.now();
    if (lendo || estavaLendo) {
      if (!lendo || agora - ultAviso > 1000) { ultAviso = agora; enviar("atdLeitura", { lendo: !!lendo, msg: msg || "" }); }
      estavaLendo = !!lendo;
    }
  }
  function selo(msg, d, dica) {
    if (!caixa) {
      caixa = document.createElement("div");
      caixa.id = "apto-atd-selo";
      caixa.style.cssText = "position:fixed;left:12px;bottom:12px;z-index:2147483646;display:flex;gap:8px;align-items:center;background:#1f5f3f;color:#fff;" +
        "font:600 12px/1.3 Segoe UI,Arial,sans-serif;padding:6px 6px 6px 12px;border-radius:18px;box-shadow:0 2px 8px rgba(0,0,0,.25);max-width:520px";
      rotulo = document.createElement("span");
      rotulo.title = "Os atendimentos vão para o APTO (função Atendimentos)";
      botao = document.createElement("button");
      botao.type = "button";
      botao.style.cssText = "border:0;border-radius:14px;padding:5px 10px;background:#fff;color:#1f5f3f;font:700 12px Segoe UI,Arial,sans-serif;cursor:pointer";
      botao.addEventListener("click", () => {
        if (lendo) { lendo.parar = true; botao.textContent = "Parando…"; return; }
        lerTodos();
      });
      caixa.append(rotulo, botao);
      document.body.appendChild(caixa);
    }
    if (d && typeof d.total === "number") {
      caixa.dataset.total = `APTO: ${d.total} hoje (${d.lidos} lidos no SAP)` + (d.presentes ? ` · ${d.presentes} presente(s)` : "");
    }
    avisarLeitura(msg);
    rotulo.textContent = (msg ? msg + " · " : "") + (caixa.dataset.total || "Atendimentos");
    caixa.title = dica || "";
    botao.textContent = lendo ? "Parar" : "Ler a fila de hoje";
    botao.hidden = !acharFila() && !lendo;
  }

  // ---------- selecionar / chamar um assistido (a pedido, pelo botão do painel) ----------
  // Selecionar = clicar na linha da fila (o SAP carrega o quadro Registrar Atendimento).
  // Chamar = o item "Chamar" do menu do botão direito da fila (form_espera:chamar), sobre a linha selecionada.
  // Nunca aciona "Cancelar".
  async function selecionar(p) {
    const f = acharFila();
    if (!f) return { erro: "a fila Assistidos em Espera não está nesta aba" };
    const k = A.chaveNome(p.nome);
    let tr = p.rk ? linhaDaFila(p.rk) : null;
    if (!tr) tr = [...f.corpo.querySelectorAll(":scope > tr[data-rk]")].find((x) => {
      const s = x.children[0] && x.children[0].querySelector("span");
      return s && A.chaveNome(s.textContent) === k;
    });
    if (!tr) return { erro: "não está na fila do SAP agora (já atendido ou fora do filtro?)" };
    if (A.chaveNome(nomeRegistrar()) !== k || tr.getAttribute("aria-selected") !== "true") {
      tr.children[0].click();
      // o quadro Registrar Atendimento com o nome certo = o SAP selecionou (no servidor) este assistido
      const ok = await esperar(() => A.chaveNome(nomeRegistrar()) === k, 20000);
      if (!ok) return { erro: "o SAP não selecionou o assistido" };
      await dormir(300);
    }
    tr = linhaDaFila(tr.getAttribute("data-rk")) || tr;
    tr.scrollIntoView({ block: "center" });
    return { ok: true, rk: tr.getAttribute("data-rk") };
  }
  async function chamar(p) {
    if (lendo) return { erro: "espere terminar a leitura da fila" };
    const s = await selecionar(p);
    if (s.erro) return s;
    const item = byId("form_espera:chamar");
    if (!item || !/Chamar/i.test(item.textContent)) return { erro: "o item Chamar do SAP não foi achado (o SAP mudou?)" };
    const antes = (acharFila() || {}).corpo;
    item.click();
    // o SAP atualiza a fila depois de chamar
    await esperar(() => { const f = acharFila(); return f && f.corpo !== antes; }, 8000);
    selo(`Chamado: ${A.nomeProprio(A.chaveNome(p.nome))}`);
    return { ok: true };
  }

  ext.runtime.onMessage.addListener((msg, _s, responder) => {
    if (msg && msg.tipo === "selecionarSap") { selecionar(msg).then(responder); return true; }
    if (msg && msg.tipo === "chamarSap") { chamar(msg).then(responder); return true; }
    if (msg && msg.tipo === "lerFilaSap") { lerTodos(msg).then(responder); return true; }
    if (msg && msg.tipo === "pararFilaSap") { if (lendo) lendo.parar = true; responder({ ok: true }); return false; }
  });

  let agendado = null;
  const obs = new MutationObserver(() => { clearTimeout(agendado); agendado = setTimeout(verificar, 700); });
  obs.observe(document.documentElement, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ["style", "class", "aria-hidden"] });
  setTimeout(verificar, 800);
  selo("");

  // ---------- pedidos da tela do APTO (Chamar, Ver no SAP, Ler a fila, Parar) ----------
  let ocupado = false;
  async function executar(c) {
    let r;
    try {
      if (c.tipo === "pararFilaSap") { if (lendo) lendo.parar = true; r = { ok: true }; }
      else if (ocupado) r = { erro: "a aba do SAP está ocupada com outro pedido (espere terminar a leitura da fila)" };
      else {
        ocupado = true;
        try {
          if (c.tipo === "chamarSap") r = await chamar(c);
          else if (c.tipo === "selecionarSap") r = await selecionar(c);
          else if (c.tipo === "lerFilaSap") r = await lerTodos({ todos: !!c.todos });
          else r = { erro: "pedido desconhecido" };
        } finally { ocupado = false; }
        if (r && r.ok && (c.tipo === "chamarSap" || c.tipo === "selecionarSap")) enviar("atdFocar", {});
      }
    } catch (e) { r = { erro: String(e.message || e) }; }
    await enviar("atdResposta", { id: c.id, resposta: r || { erro: "sem resposta" } });
  }
  async function perguntar() {
    if (!acharFila()) return;
    const r = await enviar("atdComando", {});
    if (r && r.cmd) executar(r.cmd);
  }
  setInterval(perguntar, 2000);

  self.__aptoAtdTeste = { lerFila, lerFatos, interpretarFato, lerTodos };
  self.__aptoAtdTeste2 = { selecionar, chamar };
})();
