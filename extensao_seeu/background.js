// APTO - RSPE do SEEU: service worker.
// Cuidados: só age no SEEU (https://seeu.pje.jus.br), só no processo que a pessoa abriu, com a sessão dela (nenhuma senha
// ou cookie guardado); um RSPE por processo, base e dia; intervalo mínimo entre downloads e teto por hora; só grava o que
// for PDF de verdade (sessão expirada ou página de erro não viram arquivo); pausa sozinha depois de 3 falhas seguidas;
// nada é enviado para fora do computador (a extensão não tem nenhuma conexão própria além do pedido ao SEEU).
"use strict";
importScripts("comum.js");
const A = self.APTO;

const PADRAO = { ativo: true, raiz: "APTO", base: "", bases: [], avisoNaPagina: true };
const INTERVALO_MS = 4000;      // mínimo entre dois downloads
const TETO_HORA = 40;           // downloads automáticos por hora (ao abrir processos)
const TETO_LOTE_HORA = 300;     // downloads do lote por hora (o lote ainda espera 8 s entre processos)
const FALHAS_PAUSA = 3;         // falhas seguidas que pausam a extensão
const PAUSA_MS = 10 * 60 * 1000;
const LOG_MAX = 40;
const DIAS_HISTORICO = 30;      // chaves de "já baixado" mais antigas são apagadas

async function cfg() {
  const { cfg } = await chrome.storage.local.get("cfg");
  return Object.assign({}, PADRAO, cfg || {});
}
async function estado() {
  const r = await chrome.storage.local.get(["baixados", "log", "falhas", "pausadoAte"]);
  return { baixados: r.baixados || {}, log: r.log || [], falhas: r.falhas || 0, pausadoAte: r.pausadoAte || 0 };
}
async function registrar(item) {
  const st = await estado();
  st.log.unshift(Object.assign({ quando: Date.now() }, item));
  await chrome.storage.local.set({ log: st.log.slice(0, LOG_MAX) });
  await atualizarBadge();
}
async function atualizarBadge() {
  const c = await cfg();
  const st = await estado();
  const hoje = A.hojeISO();
  const n = Object.keys(st.baixados).filter((k) => k.endsWith("|" + hoje)).length;
  const pausado = st.pausadoAte > Date.now();
  await chrome.action.setBadgeText({ text: !c.ativo ? "off" : pausado ? "!" : n ? String(n) : "" });
  await chrome.action.setBadgeBackgroundColor({ color: !c.ativo ? "#8E958F" : pausado ? "#B42318" : "#1D5A3B" });
}
async function limparAntigos() {
  const st = await estado();
  const limite = A.hojeISO(new Date(Date.now() - DIAS_HISTORICO * 864e5));
  const b = {};
  for (const [k, v] of Object.entries(st.baixados)) if (k.split("|")[2] >= limite) b[k] = v;
  await chrome.storage.local.set({ baixados: b });
}
async function falhou(processo, motivo, base) {
  const st = await estado();
  const falhas = st.falhas + 1;
  const pausa = falhas >= FALHAS_PAUSA ? Date.now() + PAUSA_MS : st.pausadoAte;
  await chrome.storage.local.set({ falhas, pausadoAte: pausa });
  await registrar({ processo, base, arquivo: "", status: "erro", msg: motivo + (falhas >= FALHAS_PAUSA ? " - extensão pausada por 10 minutos" : "") });
}

// nomes dos downloads pedidos pela extensão, na ordem (o ouvinte de nome do Chrome confirma cada um)
const proximosNomes = [];

// fila: um download por vez, com intervalo mínimo
let ultimo = 0;
let fila = Promise.resolve();
function enfileirar(fn) {
  const p = fila.then(async () => {
    const espera = ultimo + INTERVALO_MS - Date.now();
    if (espera > 0) await new Promise((r) => setTimeout(r, espera));
    ultimo = Date.now();
    return fn();
  });
  fila = p.catch(() => {});
  return p;
}
async function baixarArquivo(url, arquivo, extra) {
  return enfileirar(async () => {
    proximosNomes.push(arquivo);
    const id = await chrome.downloads.download({ url, filename: arquivo, conflictAction: "uniquify", saveAs: false });
    const pend = (await chrome.storage.session.get("pend")).pend || {};
    pend[id] = Object.assign({ arquivo }, extra || {});
    await chrome.storage.session.set({ pend });
    return id;
  });
}

const doSeeu = (u) => /^https:\/\/seeu\.pje\.jus\.br\//.test(u || "");
const doSiapen = (u) => /^https:\/\/app\.siapen\.ms\.gov\.br(:\d+)?\//.test(u || "");

// pode baixar a ficha do SIAPEN deste nome agora?
async function podeFicha(nome, lote) {
  const c = await cfg();
  const st = await estado();
  if (!c.ativo) return { ok: false, motivo: "desligada" };
  if (st.pausadoAte > Date.now()) return { ok: false, motivo: "pausada depois de falhas seguidas; faça login e clique em \"retomar\" no ícone do APTO" };
  const chave = A.chaveFicha(c, nome, A.hojeISO());
  if (nome && lote && st.baixados[chave]) return { ok: false, motivo: "já baixada hoje", repetido: true };
  const naHora = st.log.filter((x) => x.quando > Date.now() - 3600e3 && x.lote).length;
  if (lote && naHora >= TETO_LOTE_HORA) return { ok: false, motivo: `limite de ${TETO_LOTE_HORA} downloads do lote por hora - pausada` };
  return { ok: true, chave, cfg: c };
}

// PDF da ficha (buscado pela página do SIAPEN): grava na pasta da base
async function gravarFicha(msg, sender) {
  const nome = String(msg.nome || "").toUpperCase().replace(/\s+/g, " ").trim();
  const p = await podeFicha(nome, msg.lote);
  if (!p.ok) return p;
  if (!msg.b64 || msg.b64.length < 2000 || !msg.b64.startsWith("JVBER")) {
    await falhou(nome, "o arquivo da ficha não é PDF", p.cfg.base);
    return { ok: false, motivo: "o arquivo da ficha não é PDF" };
  }
  const arquivo = A.caminhoFicha(p.cfg, nome || (msg.cod ? "cod_" + msg.cod : ""), A.hojeISO());
  try {
    await baixarArquivo("data:application/pdf;base64," + msg.b64, arquivo,
      { processo: nome ? "Ficha " + nome : "Ficha", chave: nome ? p.chave : "", base: p.cfg.base, lote: !!msg.lote, manual: !msg.lote, tab: sender.tab && sender.tab.id, frame: sender.frameId });
  } catch (e) {
    await falhou(nome, "o Chrome recusou gravar a ficha: " + (e && e.message || e), p.cfg.base);
    return { ok: false, motivo: "o Chrome recusou gravar a ficha" };
  }
  return { ok: true, arquivo };
}

// pode baixar o RSPE deste processo agora?
async function podeBaixar(processo, forcar, lote) {
  const c = await cfg();
  const st = await estado();
  if (!c.ativo) return { ok: false, motivo: "desligada" };
  if (st.pausadoAte > Date.now()) return { ok: false, motivo: "pausada depois de falhas seguidas; faça login no SEEU e clique em \"retomar\" no ícone do APTO" };
  if (!processo) return { ok: false, motivo: "nº do processo não encontrado na página" };
  const chave = A.chaveDia(c, processo, A.hojeISO());
  if (st.baixados[chave] && !forcar) return { ok: false, motivo: "já baixado hoje", repetido: true };
  const naHora = st.log.filter((x) => x.quando > Date.now() - 3600e3 && (lote ? x.lote : x.auto)).length;
  const teto = lote ? TETO_LOTE_HORA : TETO_HORA;
  if (naHora >= teto && !forcar) return { ok: false, motivo: `limite de ${teto} downloads ${lote ? "do lote" : "automáticos"} por hora - pausada` };
  return { ok: true, chave, cfg: c };
}

// PDF já buscado pela página (com a sessão do SEEU): grava na pasta da base
async function gravarPdf(msg, sender) {
  const processo = A.cnj(msg.processo);
  const p = await podeBaixar(processo, msg.forcar, msg.lote);
  if (!p.ok) return p;
  if (!msg.b64 || msg.b64.length < 2000 || !msg.b64.startsWith("JVBER")) { // "%PDF" em base64
    await falhou(processo, "o arquivo recebido não é PDF", p.cfg.base);
    return { ok: false, motivo: "o arquivo recebido não é PDF" };
  }
  const arquivo = A.caminhoArquivo(p.cfg, processo, A.hojeISO());
  try {
    await baixarArquivo("data:application/pdf;base64," + msg.b64, arquivo,
      { processo, chave: p.chave, base: p.cfg.base, auto: !msg.forcar && !msg.lote, lote: !!msg.lote, tab: sender.tab && sender.tab.id, frame: sender.frameId });
  } catch (e) {
    await falhou(processo, "o Chrome recusou gravar o arquivo: " + (e && e.message || e), p.cfg.base);
    return { ok: false, motivo: "o Chrome recusou gravar o arquivo" };
  }
  return { ok: true, arquivo };
}

// cria a pasta mãe (e a de cada base) com um LEIA-ME, para a pasta vigiada do APTO achá-la desde já
async function criarPastas() {
  const c = await cfg();
  const leia = (base) => "data:text/plain;charset=utf-8," + encodeURIComponent(
    "Pasta criada pela extensão \"APTO - RSPE do SEEU\".\r\n" +
    (base ? `Os RSPE salvos aqui entram na base "${base}" do APTO (pasta vigiada).\r\n`
          : "Cada subpasta é uma base do APTO. No APTO, a pasta vigiada é esta pasta (Downloads\\" + c.raiz + ").\r\n"));
  const alvos = [""].concat(c.bases || []);
  const feitos = (await chrome.storage.local.get("pastasCriadas")).pastasCriadas || {};
  for (const b of alvos) {
    const chave = c.raiz + "|" + b;
    if (feitos[chave]) continue;
    const arq = b ? `${c.raiz}/${b}/LEIA-ME.txt` : `${c.raiz}/LEIA-ME.txt`;
    try {
      proximosNomes.push(arq);
      const id = await chrome.downloads.download({ url: leia(b), filename: arq, conflictAction: "overwrite", saveAs: false });
      feitos[chave] = Date.now();
      setTimeout(() => chrome.downloads.erase({ id }).catch(() => {}), 3000); // tira da lista de downloads; o arquivo fica
    } catch (e) {}
  }
  await chrome.storage.local.set({ pastasCriadas: feitos });
}

// nome de cada download
chrome.downloads.onDeterminingFilename.addListener((item, sugerir) => {
  if (item.byExtensionId === chrome.runtime.id) {
    const arq = proximosNomes.shift();
    arq ? sugerir({ filename: arq, conflictAction: /LEIA-ME\.txt$/.test(arq) ? "overwrite" : "uniquify" }) : sugerir();
    return true;
  }
  // RSPE salvo pela própria pessoa no visualizador do SEEU (botão de download do PDF): vai para a pasta da base
  const u = item.finalUrl || item.url || "";
  if (!doSeeu(u) || !A.urlRspeValida(u)) return false;
  (async () => {
    const c = await cfg();
    if (!c.ativo) return sugerir();
    const proc = await processoDoRspe(u);
    const arquivo = A.caminhoArquivo(c, proc, A.hojeISO());
    const pend = (await chrome.storage.session.get("pend")).pend || {};
    pend[item.id] = { processo: proc, chave: proc ? A.chaveDia(c, proc, A.hojeISO()) : "", arquivo, base: c.base, manual: true };
    await chrome.storage.session.set({ pend });
    sugerir({ filename: arquivo, conflictAction: "uniquify" });
  })();
  return true;
});

// nº do processo de um endereço de RSPE (guardado quando a página do processo abriu)
async function processoDoRspe(url) {
  try {
    const id = new URL(url).searchParams.get("idProcessoExecucaoPenal");
    const { ids } = await chrome.storage.session.get("ids");
    if (ids && ids[id]) return ids[id];
  } catch (e) {}
  const { ultimoProcesso } = await chrome.storage.session.get("ultimoProcesso");
  return ultimoProcesso && Date.now() - ultimoProcesso.quando < 3 * 60e3 ? ultimoProcesso.processo : "";
}

// a pessoa abriu o RSPE pelo botão "Situação Carcerária" (janela "Visualizar Pdf"): salva o mesmo RSPE na pasta da base,
// salvo se o automático já o salvou hoje
chrome.tabs.onUpdated.addListener(async (tabId, info, tab) => {
  const u = info.url || (info.status === "loading" ? tab.url : "");
  if (!u || !doSeeu(u) || !A.urlRspeValida(u)) return;
  const vistos = (await chrome.storage.session.get("abertos")).abertos || {};
  if (vistos[u] && Date.now() - vistos[u] < 60e3) return;
  vistos[u] = Date.now();
  await chrome.storage.session.set({ abertos: vistos });
  const processo = await processoDoRspe(u);
  // sem o nº (página do processo não vista), salva assim mesmo: o APTO lê o nº de dentro do PDF
  const p = processo ? await podeBaixar(processo, false) : await (async () => {
    const c = await cfg();
    return c.ativo ? { ok: true, chave: "", cfg: c } : { ok: false, motivo: "desligada" };
  })();
  if (!p.ok) {
    if (!p.repetido && p.motivo !== "desligada") await registrar({ processo, base: (await cfg()).base, status: "erro", msg: p.motivo });
    return;
  }
  const arquivo = A.caminhoArquivo(p.cfg, processo, A.hojeISO());
  try {
    await baixarArquivo(u, arquivo, { processo, chave: p.chave, base: p.cfg.base, manual: true });
  } catch (e) {
    await falhou(processo, "o Chrome recusou o download: " + (e && e.message || e), p.cfg.base);
  }
});

// fim do download: confere se é PDF; se não for, apaga e conta falha
chrome.downloads.onChanged.addListener(async (d) => {
  if (!d.state || (d.state.current !== "complete" && d.state.current !== "interrupted")) return;
  const pend = (await chrome.storage.session.get("pend")).pend || {};
  const p = pend[d.id];
  if (!p) return;
  delete pend[d.id];
  await chrome.storage.session.set({ pend });
  const [item] = await chrome.downloads.search({ id: d.id });
  const okPdf = d.state.current === "complete" && item && /pdf/i.test(item.mime || "") && (item.fileSize || item.totalBytes || 0) > 1500;
  if (okPdf) {
    const st = await estado();
    if (p.chave) st.baixados[p.chave] = Date.now();
    await chrome.storage.local.set({ baixados: st.baixados, falhas: 0 });
    await registrar({ processo: p.processo, base: p.base, arquivo: p.arquivo, status: "ok", auto: !!p.auto, lote: !!p.lote, manual: !!p.manual });
    if (p.tab != null) chrome.tabs.sendMessage(p.tab, { tipo: "aviso", texto: "APTO: RSPE salvo em Downloads\\" + p.arquivo.replace(/\//g, "\\") }, { frameId: p.frame }).catch(() => {});
    return;
  }
  // não veio PDF (sessão expirada, página de erro, download interrompido): não deixa arquivo errado na pasta vigiada
  if (item && item.state === "complete") {
    try { await chrome.downloads.removeFile(d.id); } catch (e) {}
  }
  try { await chrome.downloads.erase({ id: d.id }); } catch (e) {}
  await falhou(p.processo, d.state.current === "interrupted" ? "download interrompido" : "o SEEU não devolveu um PDF (sessão expirada?)", p.base);
});

chrome.runtime.onMessage.addListener((msg, sender, responder) => {
  (async () => {
    try {
      const daPagina = sender.tab && (doSeeu(sender.url) || doSiapen(sender.url));
      const doSiapenMsg = sender.tab && doSiapen(sender.url);
      if (doSiapenMsg && msg.tipo === "podeFicha") {
        const r = await podeFicha(String(msg.nome || "").toUpperCase(), msg.lote);
        return responder({ ok: r.ok, motivo: r.motivo, repetido: r.repetido });
      }
      if (doSiapenMsg && msg.tipo === "fichaPdf") return responder(await gravarFicha(msg, sender));
      if (msg.tipo === "cfg") return responder(await cfg());
      if (daPagina && msg.tipo === "podeBaixar") {
        const r = await podeBaixar(A.cnj(msg.processo), msg.forcar, msg.lote);
        return responder({ ok: r.ok, motivo: r.motivo, repetido: r.repetido });
      }
      if (daPagina && msg.tipo === "rspePdf") return responder(await gravarPdf(msg, sender));
      if (daPagina && msg.tipo === "falha") {
        await falhou(A.cnj(msg.processo), msg.motivo || "falha", (await cfg()).base);
        return responder({ ok: false, motivo: msg.motivo });
      }
      if (daPagina && msg.tipo === "processoVisto") {
        const p = A.cnj(msg.processo);
        if (p) {
          const ses = await chrome.storage.session.get("ids");
          const ids = ses.ids || {};
          try { const id = new URL(msg.url).searchParams.get("idProcessoExecucaoPenal"); if (id) ids[id] = p; } catch (e) {}
          await chrome.storage.session.set({ ultimoProcesso: { processo: p, quando: Date.now() }, ids });
        }
        return responder({ ok: true });
      }
      if (daPagina && msg.tipo === "loteItem") {
        const { lote } = await chrome.storage.local.get("lote");
        if (lote && lote.itens[msg.i]) {
          lote.itens[msg.i].status = msg.status;
          lote.itens[msg.i].msg = msg.msg || "";
          await chrome.storage.local.set({ lote });
        }
        return responder({ ok: true });
      }
      if (daPagina && msg.tipo === "loteFim") {
        const { lote } = await chrome.storage.local.get("lote");
        if (lote) { lote.rodando = false; lote.fim = Date.now(); lote.parou = !!msg.parou; await chrome.storage.local.set({ lote }); }
        return responder({ ok: true });
      }
      // o resto só das páginas da própria extensão (o painel)
      if (sender.id !== chrome.runtime.id || !String(sender.url || "").startsWith(chrome.runtime.getURL(""))) return responder({ ok: false });
      if (msg.tipo === "loteIniciar") {
        const c = await cfg();
        if (!c.ativo) return responder({ ok: false, motivo: "A extensão está desligada." });
        if (!c.base) return responder({ ok: false, motivo: "Escolha a base de destino antes de rodar o lote." });
        const [abaS] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (abaS && doSiapen(abaS.url)) {
          // SIAPEN: uma linha por pessoa - "NOME" ou "NOME ; MÃE" (também tabulação, como na coluna de uma planilha)
          const itens = [];
          const vistos = new Set();
          for (const l of String(msg.texto || "").split(/\r?\n/)) {
            const [nome, mae] = l.split(/\t|;/).map((x) => String(x || "").replace(/\s+/g, " ").trim().toUpperCase());
            if (!nome || /^\d/.test(nome) || vistos.has(nome + "|" + (mae || ""))) continue;
            vistos.add(nome + "|" + (mae || ""));
            itens.push({ nome, mae: mae || "" });
          }
          if (!itens.length) return responder({ ok: false, motivo: "Nenhum nome na lista (um por linha; \"NOME ; MÃE\" para separar homônimos)." });
          const lote = { tab: abaS.id, sistema: "siapen", base: c.base, inicio: Date.now(), rodando: true, itens: itens.map((x) => ({ n: x.nome + (x.mae ? " (mãe: " + x.mae + ")" : ""), status: "fila", msg: "" })) };
          await chrome.storage.local.set({ lote });
          let r;
          try { r = await chrome.tabs.sendMessage(abaS.id, { tipo: "loteFichas", itens }); } catch (e) { r = null; }
          if (!r || !r.ok) {
            lote.rodando = false;
            await chrome.storage.local.set({ lote });
            return responder({ ok: false, motivo: (r && r.motivo) || "Abra no SIAPEN: Consultas > Consulta Geral de Interno (e recarregue a página se a extensão acabou de ser atualizada)." });
          }
          return responder({ ok: true, total: itens.length });
        }
        const numeros = [...new Set((msg.numeros || []).map((x) => String(x).replace(/\D/g, "")).filter((x) => x.length === 20))];
        if (!numeros.length) return responder({ ok: false, motivo: "Nenhum nº de processo válido (20 dígitos) na lista." });
        const [aba] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!aba || !doSeeu(aba.url)) return responder({ ok: false, motivo: "Deixe o SEEU (processos) ou o SIAPEN (fichas) aberto e logado nesta aba." });
        const lote = { tab: aba.id, base: c.base, inicio: Date.now(), rodando: true, itens: numeros.map((n) => ({ n: A.cnj(n), status: "fila", msg: "" })) };
        await chrome.storage.local.set({ lote });
        let r;
        try { r = await chrome.tabs.sendMessage(aba.id, { tipo: "lote", numeros }, { frameId: 0 }); } catch (e) { r = null; }
        if (!r || !r.ok) {
          lote.rodando = false;
          await chrome.storage.local.set({ lote });
          return responder({ ok: false, motivo: (r && r.motivo) || "Recarregue a página do SEEU e tente de novo." });
        }
        return responder({ ok: true, total: numeros.length });
      }
      if (msg.tipo === "loteParar") {
        const { lote } = await chrome.storage.local.get("lote");
        if (lote && lote.tab != null) await chrome.tabs.sendMessage(lote.tab, { tipo: "lotePare" }, lote.sistema === "siapen" ? {} : { frameId: 0 }).catch(() => {});
        return responder({ ok: true });
      }
      if (msg.tipo === "loteEstado") return responder((await chrome.storage.local.get("lote")).lote || null);
      if (msg.tipo === "estado") {
        const st = await estado();
        return responder({ cfg: await cfg(), log: st.log, pausadoAte: st.pausadoAte, hoje: Object.keys(st.baixados).filter((k) => k.endsWith("|" + A.hojeISO())).length });
      }
      if (msg.tipo === "salvarCfg") {
        const c = Object.assign(await cfg(), msg.cfg || {});
        c.raiz = A.pastaSegura(c.raiz) || "APTO";
        c.bases = [...new Set((c.bases || []).map(A.pastaSegura).filter(Boolean))].sort((a, b) => a.localeCompare(b, "pt-BR"));
        c.base = A.pastaSegura(c.base);
        if (c.base && !c.bases.includes(c.base)) c.bases.push(c.base);
        await chrome.storage.local.set({ cfg: c });
        await criarPastas();
        await atualizarBadge();
        return responder(c);
      }
      if (msg.tipo === "retomar") { await chrome.storage.local.set({ falhas: 0, pausadoAte: 0 }); await atualizarBadge(); return responder({ ok: true }); }
      if (msg.tipo === "limparHistorico") { await chrome.storage.local.set({ baixados: {}, log: [], falhas: 0, pausadoAte: 0 }); await atualizarBadge(); return responder({ ok: true }); }
      responder({ ok: false });
    } catch (e) {
      responder({ ok: false, motivo: String(e && e.message || e) });
    }
  })();
  return true;
});

chrome.runtime.onInstalled.addListener(async () => { await limparAntigos(); await criarPastas(); await atualizarBadge(); });
chrome.runtime.onStartup.addListener(async () => { await limparAntigos(); await atualizarBadge(); });
