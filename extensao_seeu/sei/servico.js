// APTO - leitura do SEI: o "serviço" do painel, na própria página (no NUSPEN era o service worker). Mesmo leitor do NUSPEN
// (lib/nucleo.js, só leitura, na sessão da pessoa), mesma API de sincronização, agora respondida pelo APTO aberto neste computador
// (127.0.0.1:47321, função SEI). O código de pareamento vem sozinho do APTO (GET /sei/token, só para extensões): não há o que
// colar. A leitura corre enquanto esta página estiver aberta. Nunca lê nem guarda cookies do SEI (o navegador os envia sozinho).
import { sincronizar, criarLeitor, ErroNuspen } from "./lib/nucleo.js";
import { adaptadorFicticio } from "./lib/adaptador_ficticio.js";
import { adaptadorSeiReal } from "./lib/adaptador_sei_real.js";
import { adaptadorSeiDpms, HOST as HOST_DPMS } from "./lib/adaptador_sei_dpms.js";
import { ADAPTADOR_REAL_LIGADO, PADROES, VERSAO_EXTENSAO } from "./lib/config.js";
import { mensagemErro } from "./lib/estado.js";

let controle = { pausado: false, cancelado: false };
let rodando = false;
let snapshot = null;
const ouvintes = [];

const lerConfig = async () => {
  const c = { ...PADROES, ...(await chrome.storage.local.get(Object.keys(PADROES).map((k) => "sei_" + k)).then((r) => Object.fromEntries(Object.entries(r).map(([k, v]) => [k.slice(4), v])))) };
  c.baseApp = PADROES.baseApp; // sempre o APTO deste computador
  if (!c.baseSei) c.baseSei = `https://${HOST_DPMS}`;
  baseAtual = c.baseSei;
  return c;
};
// SEI da Defensoria (sei.defensoria.ms.def.br): o leitor calibrado; outro endereço: o SEI fictício do laboratório (o leitor
// genérico do NUSPEN para um SEI real continua desligado em lib/config.js)
let baseAtual = "";
function escolherAdaptador() {
  let host = "";
  try { host = new URL(baseAtual).hostname; } catch { host = ""; }
  if (host === HOST_DPMS) return adaptadorSeiDpms;
  return ADAPTADOR_REAL_LIGADO ? adaptadorSeiReal : adaptadorFicticio;
}
// o ponto de partida do SEI da Defensoria: o Controle de Processos aberto na aba do SEI (endereço assinado, guardado por sei_aba.js)
async function prepararEntrada() {
  const { seiEntrada } = await chrome.storage.session.get("seiEntrada").catch(() => ({}));
  adaptadorSeiDpms.entrada = seiEntrada && seiEntrada.url ? seiEntrada.url : "";
  adaptadorSeiDpms.avisos = [];
}

async function lerToken() {
  try {
    const r = await fetch(`${PADROES.baseApp}/sei/token`, { cache: "no-store" });
    if (!r.ok) return "";
    return (await r.json()).token || "";
  } catch { return ""; }
}
function gravarSnapshot(s) {
  snapshot = s;
  ouvintes.forEach((f) => { try { f(s); } catch (e) { console.error(e); } });
}
async function registrar(e) {
  const { seiRegistro = [] } = await chrome.storage.local.get("seiRegistro");
  seiRegistro.push({ t: Date.now(), ...e });
  await chrome.storage.local.set({ seiRegistro: seiRegistro.slice(-500) });
}

async function conexao() {
  const cfg = await lerConfig();
  const token = await lerToken();
  let appOk = false, pareado = false, conhecidos = { processos: 0, documentos: 0 };
  try {
    const r = await fetch(`${cfg.baseApp}/api/sync/ping/`, { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" });
    appOk = true;
    if (r.ok) { const d = await r.json(); pareado = true; conhecidos = d.conhecidos || conhecidos; }
  } catch { appOk = false; }
  return { appOk, pareado: pareado && Boolean(token), ficticio: escolherAdaptador().nome === "sei-ficticio", expira: null, conhecidos, baseSei: cfg.baseSei, token };
}

async function sessaoSei() {
  const cfg = await lerConfig();
  if (!cfg.baseSei) return null;
  const adaptador = escolherAdaptador();
  await prepararEntrada();
  if (!adaptador.ativo) return null;
  try {
    const origin = new URL(cfg.baseSei).origin;
    if (!(await chrome.permissions.contains({ origins: [`${origin}/*`] }))) return null;
    const leitor = criarLeitor({ baseSei: cfg.baseSei, adaptador, limitePorMinuto: 5 });
    await leitor.get(adaptador.urlLista(cfg.baseSei, 0));
    return true;
  } catch (e) {
    return e?.codigo === "sessao_expirada" || e?.codigo === "sessao_ausente" ? false : null;
  }
}

async function iniciar(msg) {
  if (rodando) return { ok: false, erro: "já há uma leitura em andamento" };
  const cfg = await lerConfig();
  const adaptador = escolherAdaptador();
  const token = await lerToken();
  await prepararEntrada();
  controle = { pausado: false, cancelado: false };
  rodando = true;
  const base = { fase: "iniciando", modo: msg.modo, processos: 0, documentosLidos: 0, documentosPulados: 0, falhas: 0, indisponiveis: 0, novos: 0, modificados: 0, adaptador: `${adaptador.nome}@${adaptador.versao}`, versaoExtensao: VERSAO_EXTENSAO, iniciadoEm: Date.now() };
  gravarSnapshot(base);
  try {
    const leitor = criarLeitor({ baseSei: cfg.baseSei, adaptador, pausaMs: cfg.pausaMs, limitePorMinuto: cfg.limitePorMinuto, maxFalhasSeguidas: cfg.maxFalhasSeguidas, controle });
    const r = await sincronizar({
      adaptador, leitor,
      app: { base: cfg.baseApp, baseSei: cfg.baseSei, token },
      opcoes: { modo: msg.modo, selecionados: msg.selecionados || [], retomar: msg.retomar || null, tetoProcessos: cfg.tetoProcessos > 0 ? cfg.tetoProcessos : null },
      progresso: (p) => gravarSnapshot({ ...base, ...p, pausado: controle.pausado }),
      registro: registrar,
    });
    gravarSnapshot({ ...base, ...r, fase: r.parada ? "parada" : "concluida", pausado: false, finalizadoEm: Date.now(), avisos: (adaptador.avisos || []).slice() });
    return { ok: true };
  } catch (e) {
    const codigo = e instanceof ErroNuspen ? e.codigo : "desconhecido";
    gravarSnapshot({ ...base, fase: "parada", erro: codigo, mensagem: mensagemErro(codigo).titulo, finalizadoEm: Date.now() });
    return { ok: false, erro: codigo };
  } finally {
    rodando = false;
  }
}

// mesma conversa que o painel do NUSPEN tinha com o service worker
export async function enviar(msg) {
  switch (msg?.tipo) {
    case "estado": {
      const c = await conexao();
      const sessao = c.pareado ? await sessaoSei() : null;
      const a = escolherAdaptador();
      delete c.token;
      return { ok: true, conexao: c, sessao, snapshot, config: await lerConfig(), adaptador: { nome: a.nome, versao: a.versao, ativo: a.ativo }, versaoExtensao: VERSAO_EXTENSAO, rodando };
    }
    case "config": {
      const permitidas = {};
      for (const k of Object.keys(PADROES)) if (k !== "baseApp" && k in msg.config) permitidas["sei_" + k] = msg.config[k];
      await chrome.storage.local.set(permitidas);
      return { ok: true };
    }
    case "parear": return { ok: true }; // o APTO entrega o código sozinho
    case "revogar": {
      const token = await lerToken();
      try { await fetch(`${PADROES.baseApp}/api/sync/token/revogar/`, { method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }, body: "{}" }); } catch { /* APTO fechado */ }
      return { ok: true };
    }
    case "iniciar": iniciar(msg); return { ok: true };
    case "pausar": controle.pausado = true; return { ok: true };
    case "continuar": controle.pausado = false; return { ok: true };
    case "cancelar": controle.cancelado = true; controle.pausado = false; return { ok: true };
    case "registro": return { ok: true, registro: (await chrome.storage.local.get("seiRegistro")).seiRegistro || [] };
    default: return { ok: false };
  }
}
export function aoSnapshot(f) { ouvintes.push(f); }
