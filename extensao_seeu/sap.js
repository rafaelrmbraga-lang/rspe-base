// APTO - lote do SAP da Defensoria (capital.defensoria.ms.def.br/sap): para cada nome da lista, acha o nº do processo
// (CNJ) no atendimento mais recente do NUSPEN. Roda numa moldura oculta da aba do SAP aberta e logada, com a sessão da
// pessoa, e clica só no que a pessoa clicaria para LER: Buscar, a lupa "Visualizar Assistido" (designar=0), a aba
// Designações, o botão Histórico e a seta de cada atendimento. Não clica em "Designar", "Atendimentos", relatórios nem em
// nada que grave. O que acha volta para o painel da extensão; nada é enviado para fora do computador.
(function () {
  "use strict";
  if (window.__aptoSap || window !== window.top) return;
  window.__aptoSap = true;
  const A = self.APTO;
  const BUSCA = "/sap/atendente/tabela_assistidos.jsf?cleanAssisRemarcar=true";
  const ID = {
    nome: "form_assistido:assistido",
    buscar: "form_assistido:btnSubmit",
    lista: "form_assistido:listaAssistidos",
    abas: "form_assistido:tabView",
    designacoes: "form_assistido:tabView:listaAtendimentos",
    fatos: "form_dialogAtendimentoFato:tbFatoAtendimento",
  };
  const INTERVALO_MS = 8000;
  const dormir = (ms) => new Promise((r) => setTimeout(r, ms));
  const norm = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/\s+/g, " ").trim().toUpperCase();
  // nome sem as anotações entre parênteses que o SAP às vezes traz, ex.: "(USAR ESSE)"
  const semNota = (s) => norm(s).replace(/\([^)]*\)/g, " ").replace(/\s+/g, " ").trim();
  const dig = (s) => String(s || "").replace(/\D/g, "");
  // "15/09/2026 14:48[:41]" -> número comparável
  const quando = (s) => {
    const m = /(\d{2})\/(\d{2})\/(\d{4})(?:\s+(\d{2}):(\d{2}))?/.exec(String(s || ""));
    return m ? Number(m[3] + m[2] + m[1] + (m[4] || "00") + (m[5] || "00")) : 0;
  };
  const dataDe = (s) => (/\d{2}\/\d{2}\/\d{4}/.exec(String(s || "")) || [""])[0];

  let quadro = null;
  const doc = () => quadro && quadro.contentDocument;
  const $ = (id) => (doc() ? doc().getElementById(id) : null);

  function proximaCarga(ms) {
    return new Promise((ok) => {
      const t = setTimeout(() => ok(false), ms || 40000);
      quadro.addEventListener("load", () => { clearTimeout(t); ok(true); }, { once: true });
    });
  }
  async function abrir(url) {
    if (!quadro) {
      quadro = document.createElement("iframe");
      quadro.id = "apto-sap-lote";
      quadro.setAttribute("aria-hidden", "true");
      quadro.tabIndex = -1;
      quadro.style.cssText = "position:fixed;left:-30000px;top:0;width:1400px;height:900px;border:0;visibility:hidden";
      document.body.appendChild(quadro);
    }
    const c = proximaCarga();
    quadro.src = url;
    return c;
  }
  function fechar() {
    if (quadro) { quadro.remove(); quadro = null; }
  }
  async function esperar(fn, ms, passo) {
    const fim = Date.now() + ms;
    while (Date.now() < fim) {
      let v = null;
      try { v = fn(); } catch (e) { v = null; }
      if (v) return v;
      await dormir(passo || 250);
    }
    return null;
  }
  // espera o conteúdo parar de mudar (o SAP às vezes responde em mais de um pedido)
  async function estavel(sig, ms) {
    let ultimo = null, desde = Date.now();
    const fim = Date.now() + (ms || 15000);
    while (Date.now() < fim) {
      let s = "";
      try { s = sig(); } catch (e) { s = ""; }
      if (s !== ultimo) { ultimo = s; desde = Date.now(); }
      else if (Date.now() - desde >= 1000) return true;
      await dormir(200);
    }
    return false;
  }
  const naLogin = () => {
    try { return /login/i.test(quadro.contentWindow.location.pathname) || !!(doc() && doc().querySelector("input[type=password]")); } catch (e) { return false; }
  };
  // colunas de uma tabela do PrimeFaces pelo título
  function colunas(tabelaId, nomes) {
    const t = $(tabelaId);
    const r = {};
    if (!t) return r;
    const ths = [...t.querySelectorAll("thead th")];
    ths.forEach((th, i) => {
      const tx = norm(th.textContent);
      for (const [k, re] of Object.entries(nomes)) if (r[k] == null && re.test(tx)) r[k] = i;
    });
    return r;
  }
  const celula = (tr, i) => (i != null && tr.children[i] ? tr.children[i].textContent.replace(/\s+/g, " ").trim() : "");

  async function buscar(p) {
    if (!(await abrir(BUSCA))) return { erro: "o SAP não abriu a busca de assistidos" };
    if (naLogin()) return { erro: "sessão do SAP expirada: faça login e rode de novo", parar: true };
    const campo = $(ID.nome), botao = $(ID.buscar);
    if (!campo || !botao) return { erro: "a tela de busca do SAP mudou (campo Assistido não achado)", parar: true };
    const corpo = () => $(ID.lista + "_data");
    const antes = corpo() ? corpo().innerHTML : "";
    campo.value = p.nome;
    botao.click();
    await esperar(() => corpo() && corpo().innerHTML !== antes, 20000);
    await estavel(() => (corpo() ? corpo().innerHTML : ""), 15000);
    if (naLogin()) return { erro: "sessão do SAP expirada: faça login e rode de novo", parar: true };
    const c = colunas(ID.lista, { id: /^ID$/, nome: /^ASSISTIDO$/, mae: /^MAE$/, cpf: /^(N. )?CPF$/ });
    const linhas = corpo() ? [...corpo().querySelectorAll(":scope > tr[data-ri]")] : [];
    return {
      linhas: linhas.map((tr) => ({
        tr, id: celula(tr, c.id != null ? c.id : 0), nome: celula(tr, c.nome != null ? c.nome : 2),
        mae: celula(tr, c.mae != null ? c.mae : 4), cpf: dig(celula(tr, c.cpf != null ? c.cpf : 7)),
      })),
    };
  }

  // escolhe o assistido certo; homônimos só com a mãe, o CPF ou o ID da lista (ou a anotação "USAR ESSE" do SAP)
  function escolher(p, linhas) {
    const nome = semNota(p.nome);
    let cand = linhas.filter((x) => semNota(x.nome) === nome);
    if (!cand.length) return { erro: "não encontrado no SAP" };
    if (p.mae) {
      const m = cand.filter((x) => semNota(x.mae) === semNota(p.mae));
      if (!m.length) return { erro: "não encontrado no SAP com essa mãe" };
      cand = m;
    }
    if (cand.length > 1 && p.cpf) cand = cand.filter((x) => x.cpf === dig(p.cpf));
    if (cand.length > 1 && p.num) cand = cand.filter((x) => dig(x.id) === dig(p.num));
    if (cand.length > 1) {
      const usar = cand.filter((x) => /USAR ESSE/.test(norm(x.nome)));
      if (usar.length === 1) cand = usar;
    }
    if (!cand.length) return { erro: "não encontrado no SAP com esse CPF/ID" };
    if (cand.length > 1) {
      return { erro: `homônimos (${cand.length}) no SAP: informe a mãe, o CPF ou o ID na lista (mães: ${cand.map((x) => x.mae || "?").join("; ")})` };
    }
    return { alvo: cand[0] };
  }

  async function designacoesNuspen() {
    const link = doc().querySelector('a[href="#' + ID.abas + ':tabDesignacoes"]');
    if (!link) return { erro: "a tela do assistido no SAP mudou (aba Designações não achada)", parar: true };
    link.click();
    const painel = () => $(ID.abas + ":tabDesignacoes");
    await esperar(() => $(ID.designacoes + "_data") || (painel() && /registro/i.test(painel().textContent)), 20000);
    await estavel(() => (painel() ? painel().innerHTML.length : 0), 10000);
    const corpo = $(ID.designacoes + "_data");
    if (!corpo) return { erro: "sem designações no SAP" };
    const c = colunas(ID.designacoes, { nucleo: /^NUCLEO$/, data: /^DATA ATENDIMENTO$/ });
    const linhas = [...corpo.querySelectorAll(":scope > tr[data-ri]")].map((tr) => ({
      tr, nucleo: celula(tr, c.nucleo != null ? c.nucleo : 1), data: celula(tr, c.data != null ? c.data : 8),
      historico: [...tr.querySelectorAll("button")].find((b) => /hist/i.test(norm(b.textContent))),
    }));
    const nus = linhas.filter((x) => /NUSPEN/.test(norm(x.nucleo)) && x.historico).sort((a, b) => quando(b.data) - quando(a.data));
    if (!nus.length) return { erro: "sem atendimento do NUSPEN no SAP" };
    return { nus };
  }

  // abre o Histórico (Fato Narrado) e lê os atendimentos do mais recente para o mais antigo, até achar nº de processo
  async function procurarNoHistorico(d, jaDesceu) {
    const corpo = () => $(ID.fatos + "_data");
    const antes = corpo();
    const antesHtml = antes ? antes.innerHTML : null;
    d.historico.click();
    await esperar(() => corpo() && (corpo() !== antes || corpo().innerHTML !== antesHtml), 20000);
    await estavel(() => (corpo() ? corpo().innerHTML : ""), 10000);
    if (!corpo()) return { erro: "o Histórico do SAP não abriu" };
    const c = colunas(ID.fatos, { data: /^DATA CADASTRO$/ });
    const linhas = [...corpo().querySelectorAll(":scope > tr[data-ri]")]
      .map((tr) => ({ tr, data: celula(tr, c.data != null ? c.data : 1) }))
      .sort((a, b) => quando(b.data) - quando(a.data))
      .slice(0, 40);
    for (let k = 0; k < linhas.length; k++) {
      const { tr, data } = linhas[k];
      const seta = tr.querySelector(".ui-row-toggler");
      if (!seta) continue;
      const aberto = () => tr.nextElementSibling && tr.nextElementSibling.classList.contains("ui-expanded-row-content") ? tr.nextElementSibling : null;
      if (!aberto()) {
        seta.click();
        await esperar(aberto, 15000);
        await dormir(300);
      }
      const det = aberto();
      if (!det) continue;
      const texto = det.textContent.replace(/\s+/g, " ");
      const nums = A.cnjsNoTexto(texto);
      if (nums.length) return { processos: nums, data: dataDe(data), desceu: jaDesceu || k > 0 };
    }
    return { nenhum: true, total: linhas.length };
  }

  async function umAssistido(p) {
    const b = await buscar(p);
    if (b.erro) return { status: "erro", msg: b.erro, parar: b.parar };
    const e = escolher(p, b.linhas);
    if (e.erro) return { status: "erro", msg: e.erro };
    const alvo = e.alvo;
    // a lupa "Visualizar Assistido" (designar=0); nunca o botão "Designar Assistido"
    const lupa = [...alvo.tr.querySelectorAll("button")].find((x) => x.classList.contains("bt-pesquisar") &&
      /'designar'\s*:\s*'0'/.test(x.getAttribute("onclick") || ""));
    if (!lupa) return { status: "erro", msg: "a lupa Visualizar Assistido não foi reconhecida (o SAP mudou?)", parar: true };
    const carga = proximaCarga();
    lupa.click();
    if (!(await carga)) return { status: "erro", msg: "o SAP não abriu o assistido" };
    if (naLogin()) return { status: "erro", msg: "sessão do SAP expirada: faça login e rode de novo", parar: true };
    if (!$(ID.abas)) return { status: "erro", msg: "o SAP não abriu o cadastro do assistido" };
    const d = await designacoesNuspen();
    if (d.erro) return { status: "erro", msg: d.erro, parar: d.parar, sapId: alvo.id };
    for (let i = 0; i < d.nus.length; i++) {
      const r = await procurarNoHistorico(d.nus[i], i > 0);
      if (r.erro) return { status: "erro", msg: r.erro, sapId: alvo.id };
      if (r.processos) {
        return {
          status: "ok", processos: r.processos, data: r.data, sapId: alvo.id, nomeSap: alvo.nome, mae: alvo.mae,
          msg: r.processos.join(", ") + " · atendimento de " + r.data + (r.desceu ? " (o mais recente não tinha nº)" : ""),
        };
      }
    }
    return { status: "erro", msg: "sem nº de processo nos atendimentos do NUSPEN", sapId: alvo.id };
  }

  let lote = null;
  async function rodarLote(itens) {
    if (lote) return { ok: false, motivo: "já há um lote em andamento nesta aba" };
    lote = { parar: false };
    (async () => {
      for (let i = 0; i < itens.length; i++) {
        if (lote.parar) break;
        await chrome.runtime.sendMessage({ tipo: "loteItem", i, status: "rodando" }).catch(() => {});
        let r;
        try { r = await umAssistido(itens[i]); } catch (e) { r = { status: "erro", msg: String((e && e.message) || e) }; }
        await chrome.runtime.sendMessage({ tipo: "loteItem", i, status: r.status, msg: r.msg,
          extra: { processos: r.processos || [], data: r.data || "", sapId: r.sapId || "", nomeSap: r.nomeSap || "", mae: r.mae || "" } }).catch(() => {});
        if (r.parar) { lote.parar = true; break; }
        if (i < itens.length - 1) await dormir(INTERVALO_MS);
      }
      const parou = lote.parar;
      lote = null;
      fechar();
      chrome.runtime.sendMessage({ tipo: "loteFim", parou }).catch(() => {});
    })();
    return { ok: true };
  }

  chrome.runtime.onMessage.addListener((msg, _s, responder) => {
    if (msg.tipo === "loteSap") { rodarLote(msg.itens || []).then(responder); return true; }
    if (msg.tipo === "lotePare") { if (lote) lote.parar = true; responder({ ok: true }); return false; }
  });
})();
