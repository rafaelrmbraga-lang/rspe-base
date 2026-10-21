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
  try {
    r = await chrome.tabs.sendMessage(abaSeeu.id, { tipo: "triagemBuscar", url, metodo: op.metodo || "GET", corpo: op.corpo || "", binario: !!op.binario }, { frameId: 0 });
  } catch (e) {
    abaSeeu = null;
    throw new Parada("A aba do SEEU foi fechada ou recarregada. Deixe o SEEU aberto e tente de novo.");
  }
  if (!r) throw new Parada("O SEEU não respondeu (recarregue a página do SEEU).");
  if (r.login) throw new Parada("Sessão do SEEU expirada: faça login de novo e clique em continuar.");
  if (!r.ok) throw new Error(r.motivo || ("o SEEU respondeu com erro " + r.status));
  return r;
}

// ---------------------------------------------------------------- PDF
function b64ParaBytes(b64) {
  const bin = atob(b64);
  const u = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
  return u;
}
async function textoDoPdf(b64) {
  const doc = await pdfjsLib.getDocument({ data: b64ParaBytes(b64), isEvalSupported: false, disableFontFace: true, useSystemFonts: false, verbosity: 0 }).promise;
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
      let pagina = 1, total = null, campos = null;
      while (pagina <= 40) {
        progresso(0, 0, `Mesa · ${T.ABAS[aba]} · página ${pagina}${total != null ? " · " + total + " registro(s)" : ""}`);
        let url = `/seeu/usuario/mesaDefensor1Grau.do?actionType=listar&finalidadeRemessa=${aba}&situacao=${situacao}&pageNumber=${pagina}`;
        let r = await buscar(url);
        let m = T.lerMesa(r.texto);
        if (pagina > 1 && m.de === 1 && campos) {
          // o SEEU ignorou a página pedida por GET: pede como o próprio formulário da Mesa (POST, só a lista)
          const corpo = new URLSearchParams(Object.assign({}, campos, { pageNumber: String(pagina), finalidadeRemessa: aba, situacao })).toString();
          r = await buscar(`/seeu/usuario/mesaDefensor1Grau.do?actionType=listar`, { metodo: "POST", corpo });
          m = T.lerMesa(r.texto);
          if (m.de === 1) { avisos.push(`${T.ABAS[aba]}: só a 1ª página pôde ser lida`); break; }
        }
        if (pagina === 1) { total = m.total; campos = filtrarCampos(m.campos); }
        for (const l of m.linhas) if (!linhas.some((x) => x.aba === aba && x.processo === l.processo)) linhas.push(Object.assign(l, { aba }));
        if (!m.linhas.length || !m.ate || m.ate >= m.total) break;
        pagina++;
      }
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
      try { texto = await textoDoPdf(r.b64); } catch (e) { texto = ""; }
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
  return m ? { seq: m.seq, data: m.data, hora: m.hora, nome: m.nome, complemento: m.complemento, autor: m.autor, cargo: m.cargo } : null;
}

async function analisarLinha(l) {
  const r = await buscar(l.url);
  let proc = T.lerProcesso(r.texto);
  if (proc.processo && proc.processo !== l.processo) throw new Error("o SEEU abriu outro processo (" + proc.processo + ")");
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
    motivo: resumoMov(e.motivo), decisao: resumoMov(e.decisao), merito: resumoMov(e.merito),
    desde: e.desde.map(resumoMov),
    mesma: !!(e.motivo && e.decisao && e.motivo.seq === e.decisao.seq),
  };
  if (e.motivo) a.motivo.doc = await lerDocumentoDoMovimento(l.processo, e.motivo);
  if (e.decisao) a.decisao.doc = a.mesma ? a.motivo.doc : await lerDocumentoDoMovimento(l.processo, e.decisao);
  if (e.merito) a.merito.doc = await lerDocumentoDoMovimento(l.processo, e.merito);
  const alertas = [], temas = [];
  for (const d of [a.motivo && a.motivo.doc, a.decisao && a.decisao.doc, a.merito && a.merito.doc]) {
    if (!d) continue;
    for (const x of d.alertas || []) if (!alertas.some((y) => y.txt === x.txt)) alertas.push(x);
    for (const x of d.temas || []) if (!temas.includes(x)) temas.push(x);
  }
  a.alertas = alertas.sort((x, y) => ({ alto: 0, medio: 1, info: 2 })[x.nivel] - ({ alto: 0, medio: 1, info: 2 })[y.nivel]);
  a.temas = temas;
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
  else mensagem(`Leitura concluída: ${feitos} processo(s)` + (erros ? `, ${erros} com erro (veja a coluna Alertas)` : "") + ".", erros > 0);
}

// ---------------------------------------------------------------- filtros e tabela
function defensorDe(l) { return l.defensor || "(sem defensor)"; }
function filtradas() {
  const abas = new Set([...document.querySelectorAll(".aba:checked")].map((x) => x.value));
  const fx = T.faixasFinal($("faixa").value);
  const busca = T.normal($("busca").value);
  const tipo = $("tipo").value;
  const soAlerta = $("soAlerta").checked;
  const defs = prefs.defensores;
  return estado.linhas.filter((l) => {
    if (!abas.has(String(l.aba))) return false;
    if (defs && defs.length && !defs.includes(defensorDe(l))) return false;
    if (fx && !fx.has(l.final)) return false;
    const a = estado.analises[chaveLinha(l)];
    if (tipo && (!a || a.tipoMotivo !== tipo)) return false;
    if (soAlerta && !(a && (a.alertas || []).some((x) => x.nivel === "alto"))) return false;
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
    d && !a.mesma ? el("div", { class: "txt" }, d.semArquivo ? "(sem arquivo)" : d.semTexto ? "documento sem texto (escaneado): abrir no SEEU" : T.resumir(d.resumo, 260)) : null);
}
function celulaDecisao(a) {
  if (!a || a.status !== "ok") return "";
  if (!a.decisao) return el("span", { class: "sub" }, "nenhum ato do juiz com documento na movimentação");
  const d = a.decisao.doc;
  const m = a.merito;
  return el("div", {},
    el("div", { class: "mot" }, a.decisao.nome + (a.mesma ? " (é o motivo)" : "")),
    el("div", { class: "sub" }, `seq. ${a.decisao.seq} · ${a.decisao.data}`),
    d ? el("div", { class: "txt" }, d.semArquivo ? "(sem arquivo)" : d.semTexto ? "documento sem texto (escaneado): abrir no SEEU" : T.resumir(d.resumo, 300)) : null,
    m ? el("div", { class: "sub", style: "margin-top:4px" }, `Mérito anterior: ${m.nome} · seq. ${m.seq} · ${m.data}`) : null);
}
function celulaAlertas(a) {
  if (!a || a.status !== "ok") return "";
  const f = document.createDocumentFragment();
  for (const x of a.alertas || []) f.append(tag(x.nivel, x.txt));
  for (const t of a.temas || []) f.append(tag("tema", t));
  if (!(a.alertas || []).length && !(a.temas || []).length) f.append(el("span", { class: "sub" }, "—"));
  return f;
}

function blocoDoc(titulo, mov, d) {
  if (!mov) return null;
  const corpo = d && !d.semArquivo && !d.semTexto ? (d.corpo || d.texto || "") : "";
  return el("div", { class: "bloco" },
    el("h3", {}, titulo),
    el("div", { class: "meta" }, `seq. ${mov.seq} · ${mov.data} ${mov.hora || ""} · ${mov.nome}` + (mov.autor ? ` · ${mov.autor}` : "") + (mov.complemento ? ` · ${mov.complemento}` : "")),
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
    if (a.merito) blocos.push(blocoDoc("Última decisão de mérito", a.merito, a.merito.doc));
    blocos.push(el("div", { class: "bloco" }, el("h3", {}, "Desde a última decisão"),
      a.desde && a.desde.length ? el("ol", {}, a.desde.map((m) => el("li", {}, `${m.data} · ${m.nome}` + (m.complemento ? ` – ${T.resumir(m.complemento, 140)}` : "") + (a.motivo && m.seq === a.motivo.seq ? "  ← motivo" : ""))))
        : el("div", { class: "sub" }, "Nada relevante depois da decisão.")));
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
      el("div", { class: "nome" }, l.executado || "—"), el("div", { class: "sub" }, T.ABAS[l.aba])),
    el("td", {}, l.defensor || el("span", { class: "sub" }, "sem defensor")),
    el("td", {}, el("div", { class: "vence" + (dias != null && dias <= 2 ? " perto" : "") }, l.ultimoDia || "—"),
      el("div", { class: "sub" }, (l.prazo || "") + (dias != null ? ` · ${dias < 0 ? "venceu" : dias === 0 ? "vence hoje" : "faltam " + dias + "d"}` : "")),
      el("div", { class: "sub" }, "enviado " + (l.dataEnvio || "—"))),
    el("td", {}, celulaMotivo(a, l)),
    el("td", {}, celulaDecisao(a)),
    el("td", {}, celulaAlertas(a)));
  return tr;
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
  const altos = lidos.filter((l) => (estado.analises[chaveLinha(l)].alertas || []).some((x) => x.nivel === "alto")).length;
  const venc = linhas.filter((l) => { const d = diasAte(l.ultimoDia); return d != null && d <= 2; }).length;
  const r = $("resumo");
  r.textContent = "";
  if (estado.linhas.length) {
    r.append(el("span", {}, el("b", {}, linhas.length), ` de ${estado.linhas.length} na Mesa`),
      el("span", {}, el("b", {}, lidos.length), " lidos"),
      el("span", {}, el("b", {}, altos), " com alerta vermelho"),
      el("span", {}, el("b", {}, venc), " vencem em até 2 dias"),
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
    "Última decisão", "Data da decisão", "Resumo da decisão", "Mérito anterior", "Alertas", "Temas", "Desde a decisão"];
  const dados = [cab];
  for (const l of linhas) {
    const a = estado.analises[chaveLinha(l)] || {};
    const md = a.motivo && a.motivo.doc, dd = a.decisao && a.decisao.doc, mm = a.merito && a.merito.doc;
    const txtDoc = (d) => !d ? "" : d.semArquivo ? "(sem arquivo)" : d.semTexto ? "(sem texto: abrir no SEEU)" : d.resumo;
    dados.push([l.final, l.processo, l.executado, l.defensor, T.ABAS[l.aba], l.dataEnvio, l.ultimoDia, l.prazo,
      a.status === "erro" ? "erro: " + a.erro : a.pendencia ? a.pendencia.texto : a.status === "ok" ? "sem pendência" : "não lido",
      a.motivo ? `seq. ${a.motivo.seq} · ${a.motivo.data} · ${a.motivo.nome}` : "",
      a.mesma ? "(é a última decisão)" : txtDoc(md),
      a.decisao ? `seq. ${a.decisao.seq} · ${a.decisao.nome}` : "", a.decisao ? a.decisao.data : "", txtDoc(dd),
      a.merito ? `seq. ${a.merito.seq} · ${a.merito.data} · ${a.merito.nome}: ${txtDoc(mm)}` : "",
      (a.alertas || []).map((x) => x.txt).join("; "), (a.temas || []).join(", "),
      (a.desde || []).map((m) => `${m.data} ${m.nome}`).join("; ")]);
  }
  const bytes = T.xlsx(dados, [5, 26, 28, 24, 13, 11, 11, 15, 46, 36, 60, 34, 11, 70, 50, 40, 26, 50], "Triagem");
  const url = URL.createObjectURL(new Blob([bytes], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }));
  const d = new Date(), p = (n) => String(n).padStart(2, "0");
  const a = el("a", { href: url, download: `Triagem_Mesa_${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}.xlsx` });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
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
$("soAlerta").onchange = () => desenhar();
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
