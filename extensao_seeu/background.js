// APTO - RSPE do SEEU: service worker.
// Cuidados: só age no SEEU (https://seeu.pje.jus.br), só no processo que a pessoa abriu, com a sessão dela (nenhuma senha
// ou cookie guardado); um RSPE por processo, base e dia; intervalo mínimo entre downloads e teto por hora; só grava o que
// for PDF de verdade (sessão expirada ou página de erro não viram arquivo); pausa sozinha depois de 3 falhas seguidas;
// nada é enviado para fora do computador (a extensão não tem nenhuma conexão própria além do pedido ao SEEU).
"use strict";
importScripts("comum.js");
const A = self.APTO;

const AUTO = "@apto";            // base de destino = a base aberta no APTO
// rspeAuto: baixa o RSPE sozinho ao abrir um processo (e ao abrir "Situação Carcerária"); desligado, só o botão do painel e o lote baixam
const PADRAO = { ativo: true, rspeAuto: true, raiz: "APTO", base: AUTO, bases: [], avisoNaPagina: true };
const APTO_URL = "http://127.0.0.1:47321/apto"; // o APTO aberto informa as bases e a base aberta (só neste computador)
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
// bases do APTO (o APTO cria Downloads\\APTO\\<base> para cada uma e vigia essa pasta sozinho)
async function lerApto(forcar) {
  const { apto } = await chrome.storage.local.get("apto");
  if (!forcar && apto && Date.now() - apto.quando < 10000) return apto;
  let novo;
  try {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), 1500);
    const r = await fetch(APTO_URL, { signal: ctl.signal, cache: "no-store" });
    clearTimeout(t);
    const j = await r.json();
    novo = { ok: true, quando: Date.now(), bases: (j.bases || []).map(A.pastaSegura).filter(Boolean), aberta: A.pastaSegura(j.aberta || "") };
  } catch (e) {
    novo = Object.assign({ bases: [], aberta: "" }, apto || {}, { ok: false, quando: Date.now() });
  }
  await chrome.storage.local.set({ apto: novo });
  return novo;
}
// configuração com a base de destino resolvida (automático: a base aberta no APTO)
// (no lote, vale a base do início do lote, mesmo que outra base seja aberta no APTO no meio dele)
async function cfgDestino(doLote) {
  const c = await cfg();
  if (doLote) {
    const { lote } = await chrome.storage.local.get("lote");
    if (lote && lote.rodando && lote.base) return Object.assign({}, c, { base: lote.base });
  }
  if (c.base !== AUTO) return c;
  const ap = await lerApto();
  return Object.assign({}, c, { base: ap.aberta || "" });
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
const doSap = (u) => /^https:\/\/[\w-]+\.defensoria\.ms\.def\.br\/sap\//.test(u || "");

// pode baixar a ficha do SIAPEN deste nome agora?
async function podeFicha(nome, lote) {
  const c = await cfgDestino(lote);
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
  const c = await cfgDestino(lote);
  const st = await estado();
  if (!c.ativo) return { ok: false, motivo: "desligada" };
  if (!c.rspeAuto && !forcar && !lote) return { ok: false, motivo: "rspe automático desligado" };
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
  const alvos = [""].concat((c.bases || []).filter((b) => b !== AUTO));
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
    const c = await cfgDestino();
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
    const c = await cfgDestino();
    return !c.ativo ? { ok: false, motivo: "desligada" } : !c.rspeAuto ? { ok: false, motivo: "rspe automático desligado" } : { ok: true, chave: "", cfg: c };
  })();
  if (!p.ok) {
    if (!p.repetido && p.motivo !== "desligada" && p.motivo !== "rspe automático desligado") await registrar({ processo, base: (await cfgDestino()).base, status: "erro", msg: p.motivo });
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

// começa um lote na aba indicada (a aba ativa, quando vem do painel)
async function iniciarLote(msg, abaS) {
  const c = await cfgDestino();
  if (!c.ativo) return { ok: false, motivo: "A extensão está desligada." };
  // SAP da Defensoria: nomes -> nº do processo do último atendimento do NUSPEN (não baixa arquivo; não precisa de base)
  if (abaS && doSap(abaS.url)) {
    const pessoas = A.pessoasDaLista(msg.texto);
    if (!pessoas.length) return { ok: false, motivo: "Nenhum nome na lista (um por linha; pode ter mãe, CPF ou ID do SAP em outras colunas)." };
    const lote = { tab: abaS.id, sistema: "sap", inicio: Date.now(), rodando: true, itens: pessoas.map((x) => ({ n: x.nome, p: x, status: "fila", msg: "" })) };
    await chrome.storage.local.set({ lote });
    let r;
    try { r = await chrome.tabs.sendMessage(abaS.id, { tipo: "loteSap", itens: pessoas }, { frameId: 0 }); } catch (e) { r = null; }
    if (!r || !r.ok) {
      lote.rodando = false;
      await chrome.storage.local.set({ lote });
      return { ok: false, motivo: (r && r.motivo) || "Recarregue a página do SAP (se a extensão acabou de ser atualizada) e tente de novo." };
    }
    return { ok: true, total: pessoas.length };
  }
  if (!c.base) return { ok: false, motivo: "Sem base de destino: abra uma base no APTO (ou escolha a base acima) antes de rodar o lote." };

  // lista sem nº de processo = nomes (SIAPEN). O SIAPEN pode estar dentro do portal www.siapen.ms.gov.br (moldura),
  // por isso a aba não é reconhecida pelo endereço: o pedido vai a todas as molduras e só a da consulta responde
  if (abaS && !(msg.numeros || []).length) {
    // SIAPEN: uma linha por pessoa - nome e, se houver, mãe e prontuário (em qualquer coluna)
    const itens = A.pessoasDaLista(msg.texto).map((x) => ({ nome: x.nome, mae: x.mae, prontuario: x.num }));
    if (!itens.length) return { ok: false, motivo: "Nenhum nome na lista (um por linha; \"NOME ; MÃE\" para separar homônimos)." };
    const lote = { tab: abaS.id, sistema: "siapen", base: c.base, inicio: Date.now(), rodando: true, itens: itens.map((x) => ({ n: x.nome + (x.mae ? " (mãe: " + x.mae + ")" : ""), status: "fila", msg: "" })) };
    await chrome.storage.local.set({ lote });
    let r;
    try { r = await chrome.tabs.sendMessage(abaS.id, { tipo: "loteFichas", itens }); } catch (e) { r = null; }
    if (!r || !r.ok) {
      lote.rodando = false;
      await chrome.storage.local.set({ lote });
      return { ok: false, motivo: (r && r.motivo) || "Nomes (SIAPEN): deixe aberta nesta aba a tela Consultas > Consulta Geral de Interno (se a extensão acabou de ser atualizada, recarregue a página do SIAPEN). Processos (SEEU): cole os nºs de processo." };
    }
    return { ok: true, total: itens.length };
  }
  const numeros = [...new Set((msg.numeros || []).map((x) => String(x).replace(/\D/g, "")).filter((x) => x.length === 20))];
  if (!numeros.length) return { ok: false, motivo: "Nenhum nº de processo válido (20 dígitos) na lista." };
  const aba = abaS;
  if (!aba || !doSeeu(aba.url)) return { ok: false, motivo: "Deixe o SEEU aberto e logado nesta aba." };
  const lote = { tab: aba.id, base: c.base, inicio: Date.now(), rodando: true, itens: numeros.map((n) => ({ n: A.cnj(n), status: "fila", msg: "" })) };
  await chrome.storage.local.set({ lote });
  let r;
  try { r = await chrome.tabs.sendMessage(aba.id, { tipo: "lote", numeros }, { frameId: 0 }); } catch (e) { r = null; }
  if (!r || !r.ok) {
    lote.rodando = false;
    await chrome.storage.local.set({ lote });
    return { ok: false, motivo: (r && r.motivo) || "Recarregue a página do SEEU e tente de novo." };
  }
  return { ok: true, total: numeros.length };
}

// nºs achados no último lote do SAP -> lote do SEEU (na aba do SEEU aberta); guarda nome de cada nº para o aviso final
async function sapParaSeeu() {
  const { ultimoSap } = await chrome.storage.local.get("ultimoSap");
  if (!ultimoSap) return { ok: false, motivo: "Rode antes o lote no SAP." };
  const nomes = {};
  for (const x of ultimoSap.itens) {
    for (const n of (x.extra && x.extra.processos) || []) {
      if (!nomes[n]) nomes[n] = x.n;
      else if (!nomes[n].split(" / ").includes(x.n)) nomes[n] += " / " + x.n;
    }
  }
  const numeros = Object.keys(nomes);
  if (!numeros.length) return { ok: false, motivo: "O lote do SAP não achou nenhum nº de processo." };
  const [seeu] = await chrome.tabs.query({ url: "https://seeu.pje.jus.br/*" });
  if (!seeu) return { ok: false, motivo: "Abra o SEEU (logado) em outra aba e clique de novo." };
  await chrome.storage.local.set({ sapNomes: nomes });
  return iniciarLote({ numeros, texto: numeros.join("\n") }, seeu);
}

// planilha (CSV para o Excel) com o resultado do último lote do SAP, em Downloads\\<raiz> (a pasta vigiada ignora CSV)
async function sapPlanilha() {
  const { ultimoSap, lote, sapNomes } = await chrome.storage.local.get(["ultimoSap", "lote", "sapNomes"]);
  if (!ultimoSap) return { ok: false, motivo: "Rode antes o lote no SAP." };
  const c = await cfg();
  // depois do lote do SEEU com os nºs do SAP: o que o SEEU achou ou não
  const noSeeu = {};
  if (lote && lote.sistema !== "sap" && sapNomes && Object.keys(sapNomes).length) {
    for (const x of lote.itens) {
      noSeeu[x.n] = x.status === "ok" || x.status === "repetido" ? "RSPE baixado"
        : x.status === "fila" || x.status === "rodando" ? "não verificado" : /não encontrado/.test(x.msg || "") ? "NÃO ENCONTRADO" : x.msg;
    }
  }
  const temSeeu = Object.keys(noSeeu).length > 0;
  const cel = (v) => '"' + String(v == null ? "" : v).replace(/"/g, '""') + '"';
  // uma linha por cadastro do SAP (homônimos em linhas separadas); nome não achado no SAP também entra
  const dataNum = (d) => { const m = /(\d{2})\/(\d{2})\/(\d{4})/.exec(d || ""); return m ? Number(m[3] + m[2] + m[1]) : 0; };
  const reg = [];
  for (const x of ultimoSap.itens) {
    const cads = (x.extra && x.extra.cadastros) || [];
    if (!cads.length) reg.push({ lista: x.n, nomeSap: "", mae: "", sapId: "", ultimo: "", processos: [], data: "", situacao: x.status === "fila" ? "não processado" : x.msg || "" });
    for (const c0 of cads) {
      // o mesmo cadastro do SAP vindo de duas linhas da lista (ex.: só o nome e nome com a mãe) sai uma vez
      if (c0.sapId && reg.some((r) => r.sapId === c0.sapId)) continue;
      reg.push(Object.assign({ lista: x.n }, c0));
    }
  }
  // prioridade de atendimento: 1º sem atendimento registrado; depois do último atendimento mais antigo ao mais recente;
  // por último o que não pôde ser verificado (erro de tela, sessão, não processado)
  const semAtend = (r) => !r.ultimo && /^(não encontrado no SAP|sem atendimento do NUSPEN no SAP|sem designações no SAP)$/.test(r.situacao || "");
  const grupo = (r) => (semAtend(r) ? 0 : r.ultimo ? 1 : 2);
  reg.sort((p1, p2) => grupo(p1) - grupo(p2) || dataNum(p1.ultimo) - dataNum(p2.ultimo) || p1.lista.localeCompare(p2.lista, "pt-BR"));
  const cab = ["Prioridade", "Nome (lista)", "Nome no SAP", "Mãe", "ID SAP", "Último atendimento NUSPEN", "Processo(s)", "Atendimento com o nº", "Situação"]
    .concat(temSeeu ? ["No SEEU"] : []);
  const linhas = [cab.map(cel).join(";")];
  reg.forEach((r, i) => {
    const procs = r.processos || [];
    linhas.push([i + 1, r.lista, r.nomeSap, r.mae, r.sapId, r.ultimo || (semAtend(r) ? "sem atendimento registrado" : ""), procs.join(" / "), r.data,
      r.situacao === "ok" ? "ok" : r.situacao]
      .concat(temSeeu ? [procs.map((n) => n + ": " + (noSeeu[n] || "não verificado")).join(" / ")] : []).map(cel).join(";"));
  });
  const agora = new Date();
  const hm = String(agora.getHours()).padStart(2, "0") + String(agora.getMinutes()).padStart(2, "0");
  const arquivo = (A.pastaSegura(c.raiz) || "APTO") + "/SAP_processos_" + A.hojeISO() + "_" + hm + ".csv";
  const csv = "\ufeff" + linhas.join("\r\n");
  proximosNomes.push(arquivo);
  await chrome.downloads.download({ url: "data:text/csv;charset=utf-8," + encodeURIComponent(csv), filename: arquivo, conflictAction: "uniquify", saveAs: false });
  return { ok: true, arquivo };
}

chrome.runtime.onMessage.addListener((msg, sender, responder) => {
  (async () => {
    try {
      const daPagina = sender.tab && (doSeeu(sender.url) || doSiapen(sender.url) || doSap(sender.url));
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
        await falhou(A.cnj(msg.processo), msg.motivo || "falha", (await cfgDestino()).base);
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
          if (msg.extra) lote.itens[msg.i].extra = msg.extra;
          await chrome.storage.local.set({ lote });
        }
        return responder({ ok: true });
      }
      if (daPagina && msg.tipo === "loteFim") {
        const { lote } = await chrome.storage.local.get("lote");
        if (lote) {
          lote.rodando = false; lote.fim = Date.now(); lote.parou = !!msg.parou;
          await chrome.storage.local.set(lote.sistema === "sap" ? { lote, ultimoSap: lote } : { lote });
        }
        return responder({ ok: true });
      }
      // o resto só das páginas da própria extensão (o painel)
      if (sender.id !== chrome.runtime.id || !String(sender.url || "").startsWith(chrome.runtime.getURL(""))) return responder({ ok: false });
      if (msg.tipo === "loteIniciar") {
        const [abaS] = await chrome.tabs.query({ active: true, currentWindow: true });
        await chrome.storage.local.remove("sapNomes"); // lote colado à mão: os nºs não vêm do SAP
        return responder(await iniciarLote(msg, abaS));
      }
      if (msg.tipo === "loteParar") {
        const { lote } = await chrome.storage.local.get("lote");
        if (lote && lote.tab != null) await chrome.tabs.sendMessage(lote.tab, { tipo: "lotePare" }, lote.sistema === "siapen" ? {} : { frameId: 0 }).catch(() => {});
        return responder({ ok: true });
      }
      if (msg.tipo === "loteEstado") {
        const r = await chrome.storage.local.get(["lote", "sapNomes", "ultimoSap"]);
        return responder(r.lote ? Object.assign({}, r.lote, { sapNomes: r.sapNomes || {}, temSap: !!r.ultimoSap }) : null);
      }
      if (msg.tipo === "sapParaSeeu") return responder(await sapParaSeeu());
      if (msg.tipo === "sapPlanilha") return responder(await sapPlanilha());
      if (msg.tipo === "estado") {
        const st = await estado();
        return responder({ cfg: await cfg(), apto: await lerApto(true), log: st.log, pausadoAte: st.pausadoAte, hoje: Object.keys(st.baixados).filter((k) => k.endsWith("|" + A.hojeISO())).length });
      }
      if (msg.tipo === "salvarCfg") {
        const c = Object.assign(await cfg(), msg.cfg || {});
        c.raiz = A.pastaSegura(c.raiz) || "APTO";
        c.bases = [...new Set((c.bases || []).map(A.pastaSegura).filter((b) => b && b !== AUTO))].sort((a, b) => a.localeCompare(b, "pt-BR"));
        c.base = c.base === AUTO ? AUTO : A.pastaSegura(c.base);
        const doApto = ((await chrome.storage.local.get("apto")).apto || {}).bases || [];
        if (c.base && c.base !== AUTO && !c.bases.includes(c.base) && !doApto.includes(c.base)) c.bases.push(c.base);
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

chrome.runtime.onInstalled.addListener(async () => {
  // 1.4: a base de destino passa a ser, por padrão, a base aberta no APTO
  const { cfg: c0, migrado14 } = await chrome.storage.local.get(["cfg", "migrado14"]);
  if (c0 && !migrado14) await chrome.storage.local.set({ cfg: Object.assign({}, c0, { base: AUTO }) });
  await chrome.storage.local.set({ migrado14: true });
  await limparAntigos(); await criarPastas(); await lerApto(true); await atualizarBadge();
});
chrome.runtime.onStartup.addListener(async () => { await limparAntigos(); await criarPastas(); await atualizarBadge(); });
