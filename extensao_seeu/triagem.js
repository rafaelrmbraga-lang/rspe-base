// APTO - Triagem da Mesa do Defensor: página da extensão (aba própria). Conduz a leitura e mostra o resultado.
// Os pedidos ao SEEU são feitos pelo content.js, na moldura principal da aba do SEEU aberta e logada (mesma sessão da
// pessoa), e só passam os endereços de leitura de APTO.pedidoTriagemPermitido. O texto dos PDFs é extraído aqui, pelo
// pdf.js embutido na extensão: nada sai do computador.
import * as pdfjsLib from "./pdfjs/pdf.min.mjs";

pdfjsLib.GlobalWorkerOptions.workerSrc = "./pdfjs/pdf.worker.min.mjs";
const T = self.TRIAGEM;
const $ = (id) => document.getElementById(id);

const INTERVALO_MS = 900;          // mínimo entre dois pedidos ao SEEU
const DOCS_MAX = 220;              // textos de documentos guardados (reaproveitados nas próximas triagens)
const DOC_CHARS = 16000;           // tamanho máximo guardado de cada texto
const FALHAS_PARAR = 3;            // falhas seguidas de rede que param a leitura

let estado = { quando: 0, situacao: 1, linhas: [], analises: {} };
let prefs = { abas: ["5", "2"], situacao: "1", faixa: "", faixas: [], defensores: null, ordem: "urgencia" };
let abaSeeu = null;
let rodando = null;
let abertas = new Set();

// ---------------------------------------------------------------- guardar
async function carregarGuardados() {
  const r = await chrome.storage.local.get(["triagemPrefs", "triagemUltima"]);
  if (r.triagemPrefs) prefs = Object.assign(prefs, r.triagemPrefs);
  if (r.triagemUltima && r.triagemUltima.linhas) estado = Object.assign(estado, r.triagemUltima);
}
const guardarPrefs = () => chrome.storage.local.set({ triagemPrefs: prefs });
const guardarEstado = () => chrome.storage.local.set({ triagemUltima: estado }).catch(() => {});
async function docGuardado(chave) {
  const { triagemDocs } = await chrome.storage.local.get("triagemDocs");
  return (triagemDocs || {})[chave] || null;
}
async function guardarDoc(chave, valor) {
  const { triagemDocs } = await chrome.storage.local.get("triagemDocs");
  const d = triagemDocs || {};
  d[chave] = Object.assign({ quando: Date.now() }, valor, { texto: String(valor.texto || "").slice(0, DOC_CHARS) });
  const chaves = Object.keys(d);
  if (chaves.length > DOCS_MAX) chaves.sort((a, b) => d[a].quando - d[b].quando).slice(0, chaves.length - DOCS_MAX).forEach((k) => delete d[k]);
  await chrome.storage.local.set({ triagemDocs: d }).catch(() => {});
}

// ---------------------------------------------------------------- SEEU
async function acharSeeu() {
  const abas = await chrome.tabs.query({ url: "https://seeu.pje.jus.br/*" });
  abas.sort((a, b) => (b.active - a.active) || (b.lastAccessed || 0) - (a.lastAccessed || 0));
  for (const aba of abas) {
    try {
      const r = await chrome.tabs.sendMessage(aba.id, { tipo: "triagemPing" }, { frameId: 0 });
      if (r && r.ok) { abaSeeu = aba; mostrarConexao(true, r.logado); return aba; }
    } catch (e) {}
  }
  abaSeeu = null;
  mostrarConexao(false, false, abas.length > 0);
  return null;
}
function mostrarConexao(ok, logado, haAba) {
  const c = $("conexao");
  c.className = ok && logado ? "ok" : "";
  c.textContent = ok ? (logado ? "SEEU aberto e logado" : "SEEU aberto: faça login") :
    haAba ? "SEEU aberto, mas sem a extensão: recarregue a página do SEEU" : "Abra o SEEU (logado) em outra aba";
}

let ultimoPedido = 0;
class Parada extends Error {}
// pedido ao SEEU pela aba aberta; respeita o intervalo mínimo
async function buscar(url, op) {
  op = op || {};
  if (rodando && rodando.parar) throw new Parada("parado");
  const espera = ultimoPedido + INTERVALO_MS - Date.now();
  if (espera > 0) await new Promise((r) => setTimeout(r, espera));
  ultimoPedido = Date.now();
  if (!abaSeeu && !(await acharSeeu())) throw new Parada("Abra o SEEU logado em outra aba e tente de novo.");
  let r;
  // o PDF do movimento vem do servidor de arquivos do SEEU (Amazon S3), por redirecionamento: depois do primeiro,
  // vai direto pela página da extensão (o pedido feito de dentro do SEEU é barrado pelo navegador)
  if (pdfDireto && /\/seeu\/arquivo\.do\?/.test(url)) return conferirDireto(await buscarDireto(url, op));
  try {
    r = await chrome.tabs.sendMessage(abaSeeu.id, { tipo: "triagemBuscar", url, metodo: op.metodo || "GET", corpo: op.corpo || "", binario: !!op.binario }, { frameId: 0 });
  } catch (e) {
    abaSeeu = null;
    throw new Parada("A aba do SEEU foi fechada ou recarregada. Deixe o SEEU aberto e tente de novo.");
  }
  if (!r) throw new Parada("O SEEU não respondeu (recarregue a página do SEEU).");
  // o navegador barrou o pedido feito de dentro do SEEU (ex.: o PDF vem de outro servidor, por redirecionamento):
  // a própria página da extensão faz o pedido, que pode seguir o redirecionamento
  if (!r.ok && r.rede) {
    r = conferirDireto(await buscarDireto(url, op));
    if (r.pdf && /\/seeu\/arquivo\.do\?/.test(url)) pdfDireto = true;
    return r;
  }
  if (r.login) throw new Parada("Sessão do SEEU expirada: faça login de novo e clique em continuar.");
  if (!r.ok) throw new Error(r.motivo || ("o SEEU respondeu com erro " + r.status));
  return r;
}
let pdfDireto = false;
function conferirDireto(r) {
  // no pedido pela extensão, a tela de login quer dizer que o navegador não mandou a sessão do SEEU junto
  if (r.login) throw new Error("o SEEU não reconheceu a sessão no pedido feito pela extensão (confira se o navegador bloqueia cookies de terceiros para extensões)");
  if (!r.ok) throw new Error(r.motivo || ("o SEEU respondeu com erro " + r.status));
  return r;
}

// pedido feito pela página da extensão (com a sessão do navegador). Mesma lista de endereços permitidos; o
// redirecionamento só pode ir ao SEEU e ao servidor de arquivos do SEEU (permissão e política de segurança da extensão)
let destinoDescoberto = null;
async function buscarDireto(url, op) {
  const abs = new URL(url, "https://seeu.pje.jus.br/seeu/").href;
  const metodo = (op.metodo || "GET").toUpperCase(), corpo = op.corpo || "";
  const recusa = self.APTO.pedidoTriagemPermitido(abs, metodo, corpo);
  if (recusa) return { ok: false, motivo: "pedido recusado pela extensão: " + recusa };
  const o = { credentials: "include", cache: "no-store", method: metodo, redirect: "follow" };
  if (metodo === "POST") { o.body = corpo; o.headers = { "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest" }; }
  let resp;
  try {
    resp = await fetch(abs, o);
  } catch (e) {
    let onde = "";
    if (/\/seeu\/arquivo\.do$/.test(new URL(abs).pathname)) onde = await descobrirDestino(abs);
    return { ok: false, motivo: "o navegador não completou o pedido, nem pelo SEEU nem pela extensão (" + (e && e.message || e) + ")" +
      (onde ? `. O SEEU entrega o arquivo a partir de ${onde}: avise para liberar esse endereço na extensão` : "") };
  }
  const bytes = new Uint8Array(await resp.arrayBuffer());
  const fim = resp.url || abs;
  let host = "";
  try { host = new URL(fim).hostname; } catch (e) {}
  const login = host !== "seeu.pje.jus.br" && !/\.pdf/i.test(fim) && !self.APTO.ehPdf(bytes) ? /login|sso|auth/i.test(fim) : false;
  if (op.binario && self.APTO.ehPdf(bytes)) return { ok: resp.ok, pdf: true, bytes, url: fim, status: resp.status };
  const ct = resp.headers.get("content-type") || "";
  let cs = (/charset=([\w-]+)/i.exec(ct) || /<meta[^>]+charset=["']?([\w-]+)/i.exec(new TextDecoder("latin1").decode(bytes.subarray(0, 4096))) || [, "windows-1252"])[1].toLowerCase();
  if (/^(iso-8859-1|latin1|us-ascii|ascii)$/.test(cs)) cs = "windows-1252";
  let texto;
  try { texto = new TextDecoder(cs).decode(bytes); } catch (e) { texto = new TextDecoder("windows-1252").decode(bytes); }
  return { ok: resp.ok, pdf: false, texto, url: fim, status: resp.status, login: login || /type\s*=\s*["']?password/i.test(texto) };
}

// onde o SEEU entrega o arquivo: o download do próprio navegador segue o redirecionamento e informa o endereço final.
// Feito uma vez; o download é cancelado e apagado na hora (fica fora da pasta vigiada do APTO).
async function descobrirDestino(abs) {
  if (destinoDescoberto !== null) return destinoDescoberto;
  destinoDescoberto = "";
  let id;
  try {
    id = await chrome.downloads.download({ url: abs, filename: "apto_triagem_diagnostico.pdf", conflictAction: "uniquify", saveAs: false });
    for (let i = 0; i < 40; i++) {
      const [it] = await chrome.downloads.search({ id });
      if (it && it.finalUrl && it.finalUrl !== abs) { destinoDescoberto = new URL(it.finalUrl).origin; break; }
      if (!it || it.state !== "in_progress") break;
      await new Promise((r) => setTimeout(r, 250));
    }
  } catch (e) {}
  if (id != null) {
    try { await chrome.downloads.cancel(id); } catch (e) {}
    try { const [it] = await chrome.downloads.search({ id }); if (it && it.state === "complete") await chrome.downloads.removeFile(id); } catch (e) {}
    try { await chrome.downloads.erase({ id }); } catch (e) {}
  }
  return destinoDescoberto;
}

// ---------------------------------------------------------------- PDF
function b64ParaBytes(b64) {
  const bin = atob(b64);
  const u = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
  return u;
}
async function textoDoPdf(dados) {
  const doc = await pdfjsLib.getDocument({ data: typeof dados === "string" ? b64ParaBytes(dados) : dados, isEvalSupported: false, disableFontFace: true, useSystemFonts: false, verbosity: 0 }).promise;
  const partes = [];
  try {
    for (let i = 1; i <= Math.min(doc.numPages, 30); i++) {
      const pg = await doc.getPage(i);
      const c = await pg.getTextContent();
      partes.push(T.itensParaTexto(c.items));
    }
  } finally {
    doc.destroy();
  }
  return partes.join("\n");
}

// ---------------------------------------------------------------- Mesa
const chaveLinha = (l) => l.aba + "|" + l.processo;

async function lerMesa() {
  const abas = [...document.querySelectorAll(".aba:checked")].map((x) => x.value);
  if (!abas.length) return mensagem("Escolha ao menos uma aba da Mesa.", true);
  const situacao = $("situacao").value;
  if (!(await acharSeeu())) return mensagem("Abra o SEEU (logado) em outra aba. Se ele já está aberto, recarregue a página do SEEU.", true);
  iniciar("Lendo a Mesa…");
  const linhas = [];
  const avisos = [];
  try {
    for (const aba of abas) {
      let pagina = 1, total = null, campos = null, falhou = false;
      const vistos = new Set();
      const novosDe = (m) => m.linhas.filter((l) => !vistos.has(l.processo)).length;
      while (pagina <= 40) {
        progresso(0, 0, `Mesa · ${T.ABAS[aba]} · página ${pagina}${total != null ? " · " + total + " registro(s)" : ""}`);
        let url = `/seeu/usuario/mesaDefensor1Grau.do?actionType=listar&finalidadeRemessa=${aba}&situacao=${situacao}&pageNumber=${pagina}`;
        let r = await buscar(url);
        let m = T.lerMesa(r.texto);
        if (pagina > 1 && campos && (m.de === 1 || !novosDe(m))) {
          // o SEEU ignorou a página pedida por GET: pede como o próprio formulário da Mesa (POST, só a lista)
          const corpo = new URLSearchParams(Object.assign({}, campos, { pageNumber: String(pagina), finalidadeRemessa: aba, situacao })).toString();
          r = await buscar(`/seeu/usuario/mesaDefensor1Grau.do?actionType=listar`, { metodo: "POST", corpo });
          m = T.lerMesa(r.texto);
          if (!novosDe(m)) { falhou = true; break; }
        }
        if (pagina === 1) { total = m.total || null; campos = filtrarCampos(m.campos); }
        for (const l of m.linhas) {
          if (vistos.has(l.processo)) continue;
          vistos.add(l.processo);
          linhas.push(Object.assign(l, { aba, situacao: Number(situacao) }));
        }
        // fim da lista: pelo total da Mesa ("N registro(s) encontrado(s)"); sem ele, pela página incompleta
        const fim = !m.linhas.length || (total ? vistos.size >= total : m.linhas.length < (m.pageSize || 20));
        if (fim) break;
        pagina++;
      }
      if (total && vistos.size < total) avisos.push(`${T.ABAS[aba]}: lidos ${vistos.size} de ${total} processos` + (falhou ? " (o SEEU não entregou as páginas seguintes)" : ""));
    }
  } catch (e) {
    terminar();
    return mensagem(e.message || String(e), true);
  }
  // guarda as leituras anteriores dos processos que continuam na Mesa
  const analises = {};
  for (const l of linhas) if (estado.analises[chaveLinha(l)]) analises[chaveLinha(l)] = estado.analises[chaveLinha(l)];
  estado = { quando: Date.now(), situacao: Number(situacao), linhas, analises };
  await guardarEstado();
  terminar();
  desenhar();
  mensagem(`Mesa lida: ${linhas.length} processo(s).` + (avisos.length ? " Atenção: " + avisos.join("; ") + "." : "") +
    " Filtre por defensor ou final do nº e clique em \"2 · Ler processos e decisões\".", avisos.length > 0);
}
function filtrarCampos(c) {
  const ok = ["org.apache.struts.taglib.html.TOKEN", "selectedIcon", "pageSize", "pageNumber", "sortColumn", "sortOrder", "finalidadeRemessa"];
  const r = {};
  for (const k of ok) if (k in c) r[k] = c[k];
  return r;
}

// ---------------------------------------------------------------- processos
async function lerDocumentoDoMovimento(processo, mov) {
  if (!mov) return null;
  const chave = processo + "#" + mov.seq;
  const g = await docGuardado(chave);
  let texto, arq;
  if (g) {
    texto = g.texto; arq = g.arquivo || {};
  } else {
    let arquivos = mov.arquivos || [];
    if (!arquivos.length && mov.ajax) {
      const r = await buscar(mov.ajax, { metodo: "POST", corpo: "tipoLayout=1" });
      arquivos = T.lerArquivos(r.texto);
    }
    arq = T.arquivoPrincipal(arquivos);
    if (!arq) return { semArquivo: true };
    const r = await buscar(arq.url, { binario: true });
    if (r.pdf) {
      try { texto = await textoDoPdf(r.bytes || r.b64); } catch (e) { texto = ""; }
    } else {
      // documento em HTML (texto do próprio SEEU); uma página inteira do SEEU (erro, aviso) não é o documento
      texto = /SEEU - Sistema Eletr|<frameset/i.test(r.texto || "") ? "" : T.texto(r.texto || "");
    }
    await guardarDoc(chave, { texto, arquivo: { ordem: arq.ordem, nome: arq.nome, descricao: arq.descricao, url: arq.url } });
  }
  const doc = T.lerDocumento(texto);
  return Object.assign(doc, { arquivo: arq, texto: String(texto || "").slice(0, DOC_CHARS) });
}

function resumoMov(m) {
  return m ? { seq: m.seq, data: m.data, hora: m.hora, nome: m.nome, complemento: m.complemento, autor: m.autor, cargo: m.cargo, papel: m.papel } : null;
}

// página do processo: 1) pelo nº (como o lote de RSPE); 2) pelo link do nº na Mesa; 3) numa moldura invisível dentro do
// SEEU (o mesmo que clicar no nº). Vale a primeira que trouxer este processo.
let modoProcesso = 0;   // a partir de qual tentativa começar (aprende com a primeira que funcionar)
async function paginaDoProcesso(l) {
  const dig = l.processo.replace(/\D/g, "");
  const tentativas = [
    ["pelo nº", () => buscar("/seeu/visualizacaoProcesso.do?actionType=visualizar&numeroUnico=" + dig)],
    ["pelo link da Mesa", () => buscar(l.url)],
    ["pela moldura", () => moldura(l.url)],
  ];
  const motivos = [];
  for (let i = modoProcesso; i < tentativas.length; i++) {
    const [nome, fazer] = tentativas[i];
    try {
      const r = await fazer();
      const proc = T.lerProcesso(r.texto);
      if (proc.processo === l.processo || (!proc.processo && proc.pendencias.length)) { modoProcesso = i; return proc; }
      motivos.push(nome + ": " + (proc.processo ? "abriu outro processo (" + proc.processo + ")" : "página sem o processo"));
    } catch (e) {
      if (e instanceof Parada) throw e;
      motivos.push(nome + ": " + (e.message || e));
    }
  }
  throw new Error("não abriu a página do processo – " + motivos.join("; "));
}
async function moldura(url) {
  if (rodando && rodando.parar) throw new Parada("parado");
  const espera = ultimoPedido + INTERVALO_MS - Date.now();
  if (espera > 0) await new Promise((r) => setTimeout(r, espera));
  ultimoPedido = Date.now();
  if (!abaSeeu && !(await acharSeeu())) throw new Parada("Abra o SEEU logado em outra aba e tente de novo.");
  let r;
  try {
    r = await chrome.tabs.sendMessage(abaSeeu.id, { tipo: "triagemMoldura", url }, { frameId: 0 });
  } catch (e) {
    abaSeeu = null;
    throw new Parada("A aba do SEEU foi fechada ou recarregada. Deixe o SEEU aberto e tente de novo.");
  }
  if (!r) throw new Error("o SEEU não respondeu (recarregue a página do SEEU)");
  if (r.login) throw new Parada("Sessão do SEEU expirada: faça login de novo e clique em continuar.");
  if (!r.ok) throw new Error(r.motivo || "falha na moldura");
  return r;
}

async function analisarLinha(l) {
  let proc = await paginaDoProcesso(l);
  if (!proc.movimentos.length && proc.temAbaMovimentos) {
    const r2 = await buscar("/seeu/visualizacaoProcesso.do?actionType=visualizar&selectedIcon=tabMovimentacoesProcesso");
    const p2 = T.lerProcesso(r2.texto);
    if (p2.processo === l.processo) proc = Object.assign(p2, { pendencias: proc.pendencias.length ? proc.pendencias : p2.pendencias });
  }
  if (!proc.movimentos.length) throw new Error("movimentações não encontradas na página do processo");
  const e = T.escolher(proc, T.ABAS[l.aba]);
  const ultimoSeq = proc.movimentos.reduce((s, m) => Math.max(s, m.seq), 0);
  const a = {
    status: "ok", quando: Date.now(), ultimoSeq,
    pendencia: e.pendencia, pendencias: proc.pendencias,
    tipoMotivo: T.tipoDoMotivo(e.pendencia ? e.pendencia.movimento : ""),
    motivo: resumoMov(e.motivo), decisao: resumoMov(e.decisao),
    mesma: !!(e.motivo && e.decisao && e.motivo.seq === e.decisao.seq),
  };
  // cada documento falha sozinho: a linha continua com o motivo, a decisão e a movimentação
  const doc = async (m) => {
    try { return await lerDocumentoDoMovimento(l.processo, m); } catch (er) {
      if (er instanceof Parada) throw er;
      return { erro: er.message || String(er), alertas: [], temas: [] };
    }
  };
  if (e.motivo) a.motivo.doc = await doc(e.motivo);
  if (e.decisao) a.decisao.doc = a.mesma ? a.motivo.doc : await doc(e.decisao);
  const alertas = [], temas = [];
  for (const d of [a.motivo && a.motivo.doc, a.decisao && a.decisao.doc]) {
    if (!d) continue;
    for (const x of d.alertas || []) if (!alertas.some((y) => y.txt === x.txt)) alertas.push(x);
    for (const x of d.temas || []) if (!temas.includes(x)) temas.push(x);
  }
  a.alertas = alertas.sort((x, y) => ({ alto: 0, medio: 1, info: 2 })[x.nivel] - ({ alto: 0, medio: 1, info: 2 })[y.nivel]);
  a.temas = temas;
  a.providencia = T.providencia(a, T.ABAS[l.aba]);
  return a;
}

async function lerProcessos() {
  const alvo = filtradas();
  if (!alvo.length) return mensagem("Nenhum processo no filtro atual.", true);
  if (!(await acharSeeu())) return mensagem("Abra o SEEU (logado) em outra aba. Se ele já está aberto, recarregue a página do SEEU.", true);
  const forcar = $("forcar").checked;
  const hoje = new Date().toDateString();
  const fila = alvo.slice().sort((x, y) => T.dataNum(x.ultimoDia) - T.dataNum(y.ultimoDia))
    .filter((l) => forcar || !estado.analises[chaveLinha(l)] || estado.analises[chaveLinha(l)].status !== "ok" || new Date(estado.analises[chaveLinha(l)].quando).toDateString() !== hoje);
  if (!fila.length) return mensagem("Os processos do filtro já foram lidos hoje. Marque \"reler tudo\" para ler de novo.", false);
  iniciar("Lendo processos…");
  let feitos = 0, erros = 0, seguidas = 0, motivoParada = "";
  for (const l of fila) {
    if (rodando.parar) break;
    progresso(feitos, fila.length, `${l.processo} · ${l.executado || ""}`);
    const k = chaveLinha(l);
    estado.analises[k] = Object.assign({}, estado.analises[k], { status: "rodando" });
    desenharLinha(l);
    try {
      estado.analises[k] = await analisarLinha(l);
      seguidas = 0;
    } catch (e) {
      if (e instanceof Parada) {
        estado.analises[k] = Object.assign({}, estado.analises[k], { status: estado.analises[k].ultimoSeq ? "ok" : "fila" });
        motivoParada = e.message === "parado" ? "" : e.message;
        break;
      }
      erros++; seguidas++;
      estado.analises[k] = { status: "erro", erro: e.message || String(e), quando: Date.now() };
      if (seguidas >= FALHAS_PARAR) { motivoParada = `${FALHAS_PARAR} falhas seguidas: a leitura parou. Confira o SEEU (login) e tente de novo.`; break; }
    }
    feitos++;
    await guardarEstado();
    desenharLinha(l);
  }
  await guardarEstado();
  terminar();
  desenhar();
  if (motivoParada) mensagem(motivoParada, true);
  else mensagem(`Leitura concluída: ${feitos} processo(s)` + (erros ? `, ${erros} com erro (veja a coluna Motivo)` : "") + ".", erros > 0);
}

// ---------------------------------------------------------------- filtros e tabela
function defensorDe(l) { return l.defensor || "(sem defensor)"; }
function filtradas() {
  const abas = new Set([...document.querySelectorAll(".aba:checked")].map((x) => x.value));
  const fx = T.faixasFinal($("faixa").value);
  const busca = T.normal($("busca").value);
  const tipo = $("tipo").value;
  const prov = $("prov").value;
  const defs = prefs.defensores;
  return estado.linhas.filter((l) => {
    if (!abas.has(String(l.aba))) return false;
    if (defs && defs.length && !defs.includes(defensorDe(l))) return false;
    if (fx && !fx.has(l.final)) return false;
    const a = estado.analises[chaveLinha(l)];
    if (tipo && (!a || a.tipoMotivo !== tipo)) return false;
    if (prov === "urgente" && !(a && a.providencia && a.providencia.urgente)) return false;
    if (prov && prov !== "urgente" && !(a && a.providencia && a.providencia.tipo === prov)) return false;
    if (busca) {
      const alvo = T.normal([l.processo, l.executado, l.defensor, a && a.pendencia && a.pendencia.texto,
        a && a.motivo && a.motivo.doc && a.motivo.doc.corpo, a && a.decisao && a.decisao.doc && a.decisao.doc.corpo].join(" "));
      if (!alvo.includes(busca) && !alvo.replace(/\D/g, "").includes(busca.replace(/\D/g, "") || "#")) return false;
    }
    return true;
  });
}

function ordenar(linhas) {
  const hoje = hojeBr();
  const v = (l) => {
    const a = estado.analises[chaveLinha(l)];
    switch (prefs.ordem) {
      case "final": return [l.final, T.dataNum(l.ultimoDia)];
      case "processo": return [T.normal(l.executado)];
      case "defensor": return [T.normal(defensorDe(l)), T.dataNum(l.ultimoDia)];
      case "ultimoDia": return [T.dataNum(l.ultimoDia) || 99999999];
      case "motivo": return [a ? a.tipoMotivo : "~", T.dataNum(l.ultimoDia)];
      case "decisao": return [a && a.decisao ? -T.dataNum(a.decisao.data) : 0];
      default: return [T.urgencia(l, a, hoje)];
    }
  };
  return linhas.slice().sort((x, y) => {
    const a = v(x), b = v(y);
    for (let i = 0; i < a.length; i++) { if (a[i] < b[i]) return -1; if (a[i] > b[i]) return 1; }
    return 0;
  });
}
function hojeBr() {
  const d = new Date(), p = (n) => String(n).padStart(2, "0");
  return `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()}`;
}
function diasAte(dataBr) {
  const m = /(\d{2})\/(\d{2})\/(\d{4})/.exec(dataBr || "");
  if (!m) return null;
  const alvo = new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1]));
  const h = new Date(); h.setHours(0, 0, 0, 0);
  return Math.round((alvo - h) / 864e5);
}

function el(tag, attrs, ...filhos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const f of filhos.flat()) if (f != null && f !== false) e.append(f instanceof Node ? f : document.createTextNode(String(f)));
  return e;
}
const tag = (nivel, txt) => el("span", { class: "tag " + nivel }, txt);

function desenharFiltros() {
  // defensores (contagem na Mesa, nas abas marcadas)
  const abas = new Set([...document.querySelectorAll(".aba:checked")].map((x) => x.value));
  const cont = {};
  for (const l of estado.linhas) if (abas.has(String(l.aba))) cont[defensorDe(l)] = (cont[defensorDe(l)] || 0) + 1;
  const box = $("defensores");
  box.textContent = "";
  const nomes = Object.keys(cont).filter((n) => n !== "(sem defensor)").sort((a, b) => a.localeCompare(b, "pt-BR"));
  const sel = prefs.defensores || [];
  box.append(el("button", { class: "chip" + (!sel.length ? " on" : ""), onclick: () => { prefs.defensores = []; guardarPrefs(); desenhar(); } }, "Todos"));
  for (const n of nomes) {
    box.append(el("button", {
      class: "chip" + (sel.includes(n) ? " on" : ""),
      onclick: () => {
        const s = new Set(prefs.defensores || []);
        s.has(n) ? s.delete(n) : s.add(n);
        prefs.defensores = [...s];
        guardarPrefs(); desenhar();
      },
    }, n, el("span", { class: "n" }, cont[n])));
  }
  // "sem defensor vinculado" sempre à vista (mesmo com 0 na Mesa)
  const SEM = "(sem defensor)";
  box.append(el("button", {
    class: "chip sem" + (sel.includes(SEM) ? " on" : ""),
    title: "Processos da Mesa sem defensor vinculado",
    onclick: () => {
      const s = new Set(prefs.defensores || []);
      s.has(SEM) ? s.delete(SEM) : s.add(SEM);
      prefs.defensores = [...s];
      guardarPrefs(); desenhar();
    },
  }, "Sem defensor vinculado", el("span", { class: "n" }, cont[SEM] || 0)));
  if (!estado.linhas.length) box.append(el("span", { class: "sub" }, "leia a Mesa primeiro"));
  // algarismos do final (0 a 9), ligados ao campo de faixa
  const fxAtual = T.faixasFinal($("faixa").value) || new Set();
  const contF = {};
  for (const l of estado.linhas) if (abas.has(String(l.aba))) contF[l.final] = (contF[l.final] || 0) + 1;
  const dg = $("digitos");
  dg.textContent = "";
  for (let d = 0; d <= 9; d++) {
    dg.append(el("button", {
      class: "chip dig" + (fxAtual.has(d) ? " on" : ""),
      title: `Final ${d}: ${contF[d] || 0} processo(s) na Mesa`,
      onclick: () => {
        const s = T.faixasFinal($("faixa").value) || new Set();
        s.has(d) ? s.delete(d) : s.add(d);
        $("faixa").value = T.faixaTexto(s);
        prefs.faixa = $("faixa").value; guardarPrefs(); desenhar();
      },
    }, String(d)));
  }
  const lst = [...fxAtual].sort((a, b) => a - b);
  $("faixaLeg").textContent = !$("faixa").value.trim() ? "todos os finais" : !lst.length ? "faixa não entendida" :
    "finais " + (lst.length > 1 ? lst.slice(0, -1).join(", ") + " e " + lst[lst.length - 1] : lst[0]);
  // faixas guardadas
  const fx = $("faixas");
  fx.textContent = "";
  for (const f of prefs.faixas || []) {
    fx.append(el("span", { class: "preset" },
      el("button", { title: f.faixa, onclick: () => { $("faixa").value = f.faixa; prefs.faixa = f.faixa; guardarPrefs(); desenhar(); } }, f.nome),
      el("button", { title: "Apagar", onclick: () => { prefs.faixas = prefs.faixas.filter((x) => x !== f); guardarPrefs(); desenharFiltros(); } }, "×")));
  }
  // tipos de motivo
  const tipos = [...new Set(Object.values(estado.analises).map((a) => a && a.tipoMotivo).filter(Boolean))].sort();
  const st = $("tipo"), atual = st.value;
  st.textContent = "";
  st.append(new Option("todos", ""));
  for (const t of tipos) st.append(new Option(t, t));
  st.value = tipos.includes(atual) ? atual : "";
}

function celulaMotivo(a, l) {
  if (!a) return el("span", { class: "sub" }, "não lido");
  if (a.status === "rodando") return tag("estado", "lendo…");
  if (a.status === "erro") return tag("erro", "erro: " + a.erro);
  if (a.status !== "ok") return el("span", { class: "sub" }, "não lido");
  const p = a.pendencia;
  const d = a.motivo && a.motivo.doc;
  return el("div", {},
    el("div", { class: "mot" }, p ? (p.movimento || p.texto) : "sem pendência no quadro"),
    el("div", { class: "sub" }, [p && p.juntar ? "Juntar " + p.juntar.toLowerCase() : "", a.motivo ? `seq. ${a.motivo.seq} · ${a.motivo.data}` : ""].filter(Boolean).join(" · ")),
    d && !a.mesma ? el("div", { class: "txt" }, d.erro ? "documento não lido: " + d.erro : d.semArquivo ? "(sem arquivo)" : d.semTexto ? "documento sem texto (escaneado): abrir no SEEU" : T.resumir(d.resumo, 260)) : null);
}
function celulaDecisao(a) {
  if (!a || a.status !== "ok") return "";
  if (!a.decisao) return el("span", { class: "sub" }, "nenhum ato do juiz com documento na movimentação");
  const d = a.decisao.doc;
  return el("div", {},
    el("div", { class: "mot" }, a.decisao.nome + (a.mesma ? " (é o motivo)" : "")),
    el("div", { class: "sub" }, `seq. ${a.decisao.seq} · ${a.decisao.data}`),
    d ? el("div", { class: "txt" }, d.erro ? "documento não lido: " + d.erro : d.semArquivo ? "(sem arquivo)" : d.semTexto ? "documento sem texto (escaneado): abrir no SEEU" : T.resumir(d.resumo, 300)) : null);
}
function providenciaDe(a, l) {
  // recalculada sempre: uma regra nova vale também para os processos já lidos
  return a && a.status === "ok" ? T.providencia(a, T.ABAS[l.aba]) : null;
}
function celulaProvidencia(a, l) {
  const p = providenciaDe(a, l);
  const botao = el("button", { class: "btn-pet", type: "button", title: "Escolher um modelo e gerar a petição (PDF ou Word)", onclick: (ev) => { ev.stopPropagation(); abrirPeticao(l); } }, "Gerar petição");
  if (!p) return el("div", {}, botao);
  return el("div", {}, el("div", { class: "prov" + (p.urgente ? " urg" : "") }, p.texto), el("div", { class: "sub" }, p.tipo), botao);
}

// ---------------------------------------------------------------- petições (modelos da pasta "modelos")
const PET = self.PETICAO;
let petLinha = null;
let fontesPdf = null;
async function bytesDaExtensao(caminho) {
  const r = await fetch(chrome.runtime.getURL(caminho));
  if (!r.ok) throw new Error("arquivo da extensão não encontrado: " + caminho);
  return new Uint8Array(await r.arrayBuffer());
}
async function inflar(b) {
  const s = new Blob([b]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
  return new Uint8Array(await new Response(s).arrayBuffer());
}
function abrirPeticao(l) {
  petLinha = l;
  const a = estado.analises[chaveLinha(l)];
  const prov = providenciaDe(a, l);
  const sug = PET.modeloSugerido(prov, a);
  $("petSub").textContent = `${l.processo} · ${l.executado || ""}` + (prov ? ` · providência sugerida: ${prov.texto}` : "");
  $("petProc").value = l.processo;
  $("petNome").value = PET.nomeProprio(l.executado || "");
  $("petData").value = PET.dataPorExtenso(new Date());
  $("petMsg").textContent = ""; $("petMsg").className = "";
  const ul = $("petLista");
  ul.textContent = "";
  const ordem = PET.MODELOS.slice().sort((x, y) => (y.id === sug) - (x.id === sug));
  for (const m of ordem) {
    const botoes = m.formato === "pdf"
      ? [el("button", { class: "pri", type: "button", onclick: () => gerarPeticao(m, "pdf") }, "PDF"), el("button", { type: "button", onclick: () => gerarPeticao(m, "docx") }, "Word")]
      : [el("button", { class: "pri", type: "button", onclick: () => gerarPeticao(m, "docx") }, "Word")];
    ul.append(el("li", { class: m.id === sug ? "sug" : "" },
      el("span", { class: "nm" }, m.nome, m.id === sug ? el("span", { class: "sugtag" }, "sugerido") : null,
        el("small", {}, m.formato === "pdf" ? "pronto: nº, data e assinatura preenchidos" : "pede dados do caso: sai em Word, com os pontos a completar em amarelo")),
      ...botoes));
  }
  $("petFundo").className = "on";
  mostrarDestino();
  $("petNome").focus();
}
function fecharPeticao() { $("petFundo").className = ""; petLinha = null; }
async function gerarPeticao(m, formato) {
  const msg = $("petMsg");
  msg.className = ""; msg.textContent = "Gerando…";
  try {
    const campos = { processo: $("petProc").value.trim(), nome: $("petNome").value.trim(), data: $("petData").value.trim() };
    const modelo = await bytesDaExtensao("modelos/" + m.arquivo);
    let bytes, tipo;
    if (formato === "pdf") {
      if (!fontesPdf) {
        const f = (n) => bytesDaExtensao("fontes_pdf/carlito-latin-" + n + ".woff");
        fontesPdf = { r: await f("400-normal"), b: await f("700-normal"), i: await f("400-italic"), bi: await f("700-italic") };
      }
      bytes = await PET.gerarPdf(modelo, campos, { inflar, PDFLib: self.PDFLib, fontkit: self.fontkit, fontes: fontesPdf, titulo: m.nome + " " + campos.processo, autor: "Cahuê Duarte e Urdiales" });
      tipo = "application/pdf";
    } else {
      bytes = await PET.gerarDocx(modelo, campos, inflar);
      tipo = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    }
    const nome = PET.nomeArquivo(m.nome, campos.processo, formato);
    const onde = await salvarPeticao(bytes, tipo, nome, formato);
    if (!onde) { msg.textContent = "Cancelado."; return; }
    msg.textContent = `Salvo em ${onde}` + (formato === "docx" && m.formato === "docx" ? " (complete os trechos em amarelo)" : "");
  } catch (e) {
    msg.className = "erro";
    msg.textContent = "Não foi possível gerar: " + (e && e.message || e);
  }
}
$("petFechar").onclick = fecharPeticao;
$("petPasta").onclick = escolherPasta;
$("petLimparPasta").onclick = async () => { await guardarPasta(null); mostrarDestino(); mensagemPet("As petições voltam a ir para Downloads."); };
$("petPerguntar").onchange = () => { prefs.perguntarDestino = $("petPerguntar").checked; guardarPrefs(); mostrarDestino(); };
$("petFundo").addEventListener("click", (ev) => { if (ev.target.id === "petFundo") fecharPeticao(); });
document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && petLinha) fecharPeticao(); });

function blocoDoc(titulo, mov, d) {
  if (!mov) return null;
  const corpo = d && !d.semArquivo && !d.semTexto ? (d.corpo || d.texto || "") : "";
  return el("div", { class: "bloco" },
    el("h3", {}, titulo),
    el("div", { class: "meta" }, `seq. ${mov.seq} · ${mov.data} ${mov.hora || ""} · ${mov.nome}` + (mov.autor ? ` · ${mov.autor}` : "") + (mov.complemento ? ` · ${mov.complemento}` : "")),
    d && d.erro ? el("div", { class: "sub" }, "Documento não lido: " + d.erro) :
    d && d.semArquivo ? el("div", { class: "sub" }, "Movimento sem arquivo.") :
      d && d.semTexto ? el("div", { class: "sub" }, "Documento sem texto (provavelmente escaneado). Abra no SEEU.") :
        el("pre", {}, corpo || "(texto não lido)"),
    d && d.arquivo && d.arquivo.url ? el("div", { style: "margin-top:6px" }, el("a", { href: d.arquivo.url, target: "_blank", rel: "noopener" }, "abrir o PDF no SEEU" + (d.arquivo.ordem ? ` (${d.arquivo.ordem})` : ""))) : null);
}
function linhaDetalhe(l, a) {
  const blocos = [];
  if (a && a.status === "ok") {
    if (a.pendencias && a.pendencias.length > 1) blocos.push(el("div", { class: "bloco" }, el("h3", {}, "Pendências"), el("ol", {}, a.pendencias.map((p) => el("li", {}, p.texto)))));
    blocos.push(blocoDoc(a.mesma ? "Motivo e última decisão" : "Motivo da intimação", a.motivo, a.motivo && a.motivo.doc));
    if (!a.mesma) blocos.push(blocoDoc("Última decisão", a.decisao, a.decisao && a.decisao.doc));
  } else if (a && a.status === "erro") {
    blocos.push(el("div", { class: "bloco" }, el("h3", {}, "Erro"), el("div", {}, a.erro)));
  } else {
    blocos.push(el("div", { class: "bloco" }, el("div", { class: "sub" }, "Ainda não lido. Use \"2 · Ler processos e decisões\".")));
  }
  blocos.push(el("div", { class: "bloco" }, el("h3", {}, "Na Mesa"),
    el("div", { class: "sub" }, `${T.ABAS[l.aba]} · ${l.classe}${l.assunto ? " (" + l.assunto + ")" : ""} · seq. Mesa ${l.seq}`),
    el("div", { style: "margin-top:6px" }, el("a", { href: l.url, target: "_blank", rel: "noopener" }, "abrir o processo no SEEU"))));
  return el("tr", { class: "det", "data-k": chaveLinha(l) }, el("td", { colspan: 7 }, el("div", { class: "det-g" }, blocos.filter(Boolean))));
}

function linhaTabela(l) {
  const k = chaveLinha(l);
  const a = estado.analises[k];
  const dias = diasAte(l.ultimoDia);
  const tr = el("tr", { class: "l" + (abertas.has(k) ? " aberta" : ""), "data-k": k, onclick: (ev) => {
    if (ev.target.closest("a")) return;
    abertas.has(k) ? abertas.delete(k) : abertas.add(k);
    desenharLinha(l);
  } },
    el("td", { class: "fin" }, l.final),
    el("td", {}, el("div", { class: "proc" }, el("a", { href: l.url, target: "_blank", rel: "noopener", title: "Abrir o processo no SEEU (o mesmo que clicar no nº)" }, l.processo)),
      nomeCopiavel(l.executado), el("div", { class: "sub" }, T.ABAS[l.aba])),
    el("td", {}, l.defensor || el("span", { class: "sub" }, "sem defensor")),
    el("td", {}, celulaPrazo(l, dias)),
    el("td", {}, celulaMotivo(a, l)),
    el("td", {}, celulaDecisao(a)),
    el("td", {}, celulaProvidencia(a, l)));
  return tr;
}

// prazo: em "Recebidas e não lidas" o último dia é o da LEITURA (depois dele a intimação vai para "Lidas e aguardando
// análise" e só então corre o prazo de resposta); nas lidas, é o último dia da RESPOSTA
function celulaPrazo(l, dias) {
  const sit = Number(l.situacao || estado.situacao || 1);
  const falta = dias == null ? "" : dias < 0 ? "venceu" : dias === 0 ? "vence hoje" : "faltam " + dias + "d";
  const rot = sit === 1 ? "Leitura até" : sit === 2 ? "Resposta até" : "Último dia";
  return el("div", {},
    el("div", { class: "sub" }, rot),
    el("div", { class: "vence" + (dias != null && dias <= 2 ? " perto" : "") }, l.ultimoDia || "—"),
    falta ? el("div", { class: "sub" + (dias <= 2 ? " vence perto" : "") }, falta) : null,
    el("div", { class: "sub", title: sit === 1 ? "O prazo de resposta começa a correr depois da leitura (ou quando vence o prazo de leitura e a intimação passa para \"Lidas e aguardando análise\")." : "" },
      sit === 1 ? `Resposta: ${l.prazo || "—"}, após a leitura` : `Resposta: ${l.prazo || "—"}`),
    el("div", { class: "sub" }, "enviado " + (l.dataEnvio || "—")));
}

// nome do sentenciado: passar o mouse mostra "copiar"; clicar no nome (ou no botão) copia
function nomeCopiavel(nome) {
  if (!nome) return el("div", { class: "nome" }, "—");
  const aviso = el("span", { class: "copiado" }, "copiado ✓");
  const copiar = (ev) => {
    ev.stopPropagation();
    // cópia imediata (no próprio clique); a área de transferência assíncrona fica como reserva
    let feito = false;
    try {
      const t = el("textarea", { style: "position:fixed;left:-9999px;top:0" }, nome);
      document.body.append(t); t.select(); feito = document.execCommand("copy"); t.remove();
    } catch (e) {}
    if (!feito && navigator.clipboard) navigator.clipboard.writeText(nome).catch(() => {});
    aviso.classList.add("on");
    setTimeout(() => aviso.classList.remove("on"), 1400);
  };
  return el("div", { class: "nome copiavel", title: "Clique para copiar o nome", onclick: copiar },
    el("span", {}, nome), el("button", { class: "copiar", type: "button", title: "Copiar o nome", onclick: copiar }, "copiar"), aviso);
}
function desenharLinha(l) {
  const k = chaveLinha(l);
  const velha = document.querySelector(`tr.l[data-k="${CSS.escape(k)}"]`);
  if (!velha) return;
  const det = document.querySelector(`tr.det[data-k="${CSS.escape(k)}"]`);
  if (det) det.remove();
  const nova = linhaTabela(l);
  velha.replaceWith(nova);
  if (abertas.has(k)) nova.after(linhaDetalhe(l, estado.analises[k]));
}

function desenhar() {
  desenharFiltros();
  const linhas = ordenar(filtradas());
  const corpo = $("corpo");
  corpo.textContent = "";
  if (!estado.linhas.length) corpo.append(el("tr", {}, el("td", { colspan: 7, class: "vazio" }, "Clique em \"1 · Ler a Mesa\" com o SEEU aberto e logado em outra aba.")));
  else if (!linhas.length) corpo.append(el("tr", {}, el("td", { colspan: 7, class: "vazio" }, "Nenhum processo no filtro atual.")));
  for (const l of linhas) {
    corpo.append(linhaTabela(l));
    if (abertas.has(chaveLinha(l))) corpo.append(linhaDetalhe(l, estado.analises[chaveLinha(l)]));
  }
  const lidos = linhas.filter((l) => (estado.analises[chaveLinha(l)] || {}).status === "ok");
  const altos = lidos.filter((l) => { const p = providenciaDe(estado.analises[chaveLinha(l)], l); return p && p.urgente; }).length;
  const venc = linhas.filter((l) => { const d = diasAte(l.ultimoDia); return d != null && d <= 2; }).length;
  const r = $("resumo");
  r.textContent = "";
  if (estado.linhas.length) {
    r.append(el("span", {}, el("b", {}, linhas.length), ` de ${estado.linhas.length} na Mesa`),
      el("span", {}, el("b", {}, lidos.length), " lidos"),
      el("span", {}, el("b", {}, altos), " com providência urgente"),
      el("span", {}, el("b", {}, venc), estado.situacao === 1 ? " com leitura vencendo em até 2 dias" : " vencem em até 2 dias"),
      el("span", {}, `Mesa lida em ${new Date(estado.quando).toLocaleString("pt-BR")} · ${T.SITUACOES[estado.situacao] || ""}`));
  }
  $("lerProc").disabled = !!rodando || !linhas.length;
  $("lerProc").textContent = `2 · Ler processos e decisões (${linhas.length})`;
  $("xlsx").disabled = $("imprimir").disabled = $("abrirTudo").disabled = !linhas.length;
  document.querySelectorAll("th[data-ord]").forEach((th) => { th.style.color = th.dataset.ord === prefs.ordem ? "var(--pri)" : ""; });
}

// ---------------------------------------------------------------- exportar
function exportarXlsx() {
  const linhas = ordenar(filtradas());
  const cab = ["Final", "Processo", "Assistido", "Defensor", "Aba", "Enviado em", "Último dia", "Prazo", "Motivo (pendência)", "Movimento do motivo", "Resumo do motivo",
    "Última decisão", "Data da decisão", "Resumo da decisão", "Providência sugerida", "Tipo da providência"];
  const dados = [cab];
  for (const l of linhas) {
    const a = estado.analises[chaveLinha(l)] || {};
    const md = a.motivo && a.motivo.doc, dd = a.decisao && a.decisao.doc;
    const pv = providenciaDe(a, l);
    const txtDoc = (d) => !d ? "" : d.erro ? "(não lido: " + d.erro + ")" : d.semArquivo ? "(sem arquivo)" : d.semTexto ? "(sem texto: abrir no SEEU)" : d.resumo;
    dados.push([l.final, l.processo, l.executado, l.defensor, T.ABAS[l.aba], l.dataEnvio, l.ultimoDia, l.prazo,
      a.status === "erro" ? "erro: " + a.erro : a.pendencia ? a.pendencia.texto : a.status === "ok" ? "sem pendência" : "não lido",
      a.motivo ? `seq. ${a.motivo.seq} · ${a.motivo.data} · ${a.motivo.nome}` : "",
      a.mesma ? "(é a última decisão)" : txtDoc(md),
      a.decisao ? `seq. ${a.decisao.seq} · ${a.decisao.nome}` : "", a.decisao ? a.decisao.data : "", txtDoc(dd),
      pv ? pv.texto : "", pv ? pv.tipo + (pv.urgente ? " (urgente)" : "") : ""]);
  }
  const bytes = T.xlsx(dados, [5, 26, 28, 24, 13, 11, 11, 15, 46, 36, 60, 34, 11, 70, 60, 18], "Triagem");
  const d = new Date(), p = (n) => String(n).padStart(2, "0");
  salvarArquivo(bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", `Triagem_Mesa_${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}.xlsx`);
}
// salva em Downloads com o nome dado (fora da pasta vigiada do APTO, que é só para RSPE e ficha). Se o Chrome recusar o
// nome (acentos, em alguns sistemas), salva com o nome sem acento
const semAcento = (s) => s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^\x20-\x7e]/g, "_");
async function salvarArquivo(bytes, tipo, nome) {
  const url = URL.createObjectURL(new Blob([bytes], { type: tipo }));
  try {
    try {
      await chrome.downloads.download({ url, filename: nome, conflictAction: "uniquify", saveAs: false });
      return nome;
    } catch (e) {
      if (!/filename/i.test(String(e && e.message))) throw e;
      await chrome.downloads.download({ url, filename: semAcento(nome), conflictAction: "uniquify", saveAs: false });
      return semAcento(nome);
    }
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  }
}

// ---- destino das petições: pasta escolhida pelo usuário (guardada), perguntar a cada vez, ou Downloads
function bancoPastas() {
  return new Promise((ok, erro) => {
    const r = indexedDB.open("apto-triagem", 1);
    r.onupgradeneeded = () => r.result.createObjectStore("pastas");
    r.onsuccess = () => ok(r.result);
    r.onerror = () => erro(r.error);
  });
}
async function pastaGuardada() {
  try {
    const db = await bancoPastas();
    return await new Promise((ok) => { const g = db.transaction("pastas").objectStore("pastas").get("peticoes"); g.onsuccess = () => ok(g.result || null); g.onerror = () => ok(null); });
  } catch (e) { return null; }
}
async function guardarPasta(h) {
  const db = await bancoPastas();
  await new Promise((ok, erro) => { const t = db.transaction("pastas", "readwrite"); h ? t.objectStore("pastas").put(h, "peticoes") : t.objectStore("pastas").delete("peticoes"); t.oncomplete = ok; t.onerror = () => erro(t.error); });
}
async function mostrarDestino() {
  const h = await pastaGuardada();
  $("petDestino").textContent = prefs.perguntarDestino ? "perguntar a cada vez" : h ? "pasta “" + h.name + "”" : "Downloads";
  $("petLimparPasta").style.display = h && !prefs.perguntarDestino ? "" : "none";
  $("petPerguntar").checked = !!prefs.perguntarDestino;
}
async function escolherPasta() {
  if (!self.showDirectoryPicker) return mensagemPet("Este navegador não permite escolher a pasta; as petições vão para Downloads.", true);
  try {
    const h = await self.showDirectoryPicker({ id: "apto-peticoes", mode: "readwrite", startIn: "documents" });
    await guardarPasta(h);
    prefs.perguntarDestino = false; guardarPrefs();
    mostrarDestino();
    mensagemPet("As petições serão salvas na pasta “" + h.name + "”.");
  } catch (e) { if (e && e.name !== "AbortError") mensagemPet("Não foi possível usar a pasta: " + e.message, true); }
}
function mensagemPet(t, erro) { $("petMsg").textContent = t; $("petMsg").className = erro ? "erro" : ""; }
const TIPOS = { pdf: { description: "PDF", accept: { "application/pdf": [".pdf"] } }, docx: { description: "Documento do Word", accept: { "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"] } } };
// devolve onde salvou (texto para a mensagem) ou "" se cancelado
async function salvarPeticao(bytes, tipo, nome, formato) {
  if (prefs.perguntarDestino && self.showSaveFilePicker) {
    try {
      const fh = await self.showSaveFilePicker({ id: "apto-peticoes", suggestedName: nome, types: [TIPOS[formato]] });
      const w = await fh.createWritable(); await w.write(bytes); await w.close();
      return fh.name;
    } catch (e) { if (e && e.name === "AbortError") return ""; throw e; }
  }
  const pasta = await pastaGuardada();
  if (pasta) {
    let perm = await pasta.queryPermission({ mode: "readwrite" });
    if (perm !== "granted") perm = await pasta.requestPermission({ mode: "readwrite" });
    if (perm === "granted") {
      let final = nome;
      for (let k = 2; k < 100; k++) {
        try { await pasta.getFileHandle(final); final = nome.replace(/(\.\w+)$/, ` (${k})$1`); } catch (e) { break; }
      }
      const fh = await pasta.getFileHandle(final, { create: true });
      const w = await fh.createWritable(); await w.write(bytes); await w.close();
      return "“" + pasta.name + "”: " + final;
    }
  }
  return "Downloads: " + (await salvarArquivo(bytes, tipo, nome));
}

// ---------------------------------------------------------------- estado da tela
function mensagem(txt, erro) {
  const m = $("msg");
  m.textContent = txt;
  m.className = erro ? "erro" : "ok";
}
function iniciar(txt) {
  rodando = { parar: false };
  $("lerMesa").disabled = $("lerProc").disabled = true;
  $("parar").disabled = false;
  $("msg").className = "";
  progresso(0, 0, txt);
}
function terminar() {
  rodando = null;
  $("lerMesa").disabled = false;
  $("parar").disabled = true;
  $("progresso").className = "";
  desenhar();
}
function progresso(feitos, total, txt) {
  $("progresso").className = "on";
  $("progBarra").style.width = total ? Math.round((feitos / total) * 100) + "%" : "8%";
  $("progTxt").textContent = (total ? `${feitos} de ${total} · ` : "") + (txt || "");
}

// ---------------------------------------------------------------- eventos
$("lerMesa").onclick = () => lerMesa();
$("lerProc").onclick = () => lerProcessos();
$("parar").onclick = () => { if (rodando) { rodando.parar = true; $("progTxt").textContent += " · parando depois do pedido em andamento…"; } };
$("faixa").oninput = () => { prefs.faixa = $("faixa").value; guardarPrefs(); desenhar(); };
$("salvarFaixa").onclick = () => {
  const f = $("faixa").value.trim();
  if (!T.faixasFinal(f)) return mensagem("Escreva a faixa antes de guardar (ex.: 0-2, 5).", true);
  const nome = (prompt("Nome para esta faixa (ex.: Meus finais):", f) || "").trim();
  if (!nome) return;
  prefs.faixas = (prefs.faixas || []).filter((x) => x.nome !== nome).concat([{ nome, faixa: f }]);
  guardarPrefs(); desenharFiltros();
};
$("busca").oninput = () => desenhar();
$("tipo").onchange = () => desenhar();
$("prov").onchange = () => desenhar();
$("situacao").onchange = () => { prefs.situacao = $("situacao").value; guardarPrefs(); };
document.querySelectorAll(".aba").forEach((c) => { c.onchange = () => { prefs.abas = [...document.querySelectorAll(".aba:checked")].map((x) => x.value); guardarPrefs(); desenhar(); }; });
document.querySelectorAll("th[data-ord]").forEach((th) => { th.onclick = () => { prefs.ordem = prefs.ordem === th.dataset.ord ? "urgencia" : th.dataset.ord; guardarPrefs(); desenhar(); }; });
$("xlsx").onclick = () => exportarXlsx();
$("imprimir").onclick = () => window.print();
$("abrirTudo").onclick = () => {
  const ks = filtradas().map(chaveLinha);
  if (ks.every((k) => abertas.has(k))) ks.forEach((k) => abertas.delete(k)); else ks.forEach((k) => abertas.add(k));
  desenhar();
};
window.addEventListener("focus", () => { if (!rodando) acharSeeu(); });

// altura do cabeçalho fixo (o cabeçalho da tabela fica logo abaixo dele ao rolar)
const ajustarTopo = () => document.documentElement.style.setProperty("--hdr", document.querySelector("header").offsetHeight + "px");
window.addEventListener("resize", ajustarTopo);

(async () => {
  ajustarTopo();
  await carregarGuardados();
  document.querySelectorAll(".aba").forEach((c) => { c.checked = (prefs.abas || []).includes(c.value); });
  $("situacao").value = prefs.situacao || "1";
  $("faixa").value = prefs.faixa || "";
  desenhar();
  await acharSeeu();
})();
