// Nucleo da extensao NUSPEN: sincronizacao incremental SOMENTE LEITURA (ADR-015/016).
//
// - Le o SEI com a sessao da propria pessoa (cookies do navegador; a extensao NUNCA os le nem
//   os guarda). Todas as leituras sao GET, da mesma origem, de URLs que o ADAPTADOR permite.
// - Entrega ao aplicativo local (127.0.0.1) com um codigo de pareamento (nao e credencial do SEI).
// - Incremental (id + versao + hash), retomavel por cursor, com salvaguardas: limite por minuto,
//   pausa entre requisicoes, teto de processos, parada diante de 429, 5xx repetidos, pagina de
//   login ou estrutura inesperada. Degradacao segura: nunca grava processo incompleto.
// - Sem dependencias externas; roda igual no Node (testes) e no service worker.

import {
  AppIndisponivel, Cancelado, ErroNuspen, EscritaProibida, EstruturaInesperada, Interrompido,
  NaoPareado, RespostaInesperada, SessaoAusente, SessaoExpirada,
} from "./erros.js";

export * from "./erros.js";

const RELOGIO = {
  agora: () => Date.now(),
  dormir: (ms) => new Promise((r) => setTimeout(r, ms)),
};

export function criarLeitor({
  baseSei, adaptador, fetchImpl = fetch, pausaMs = 0, limitePorMinuto = 30, maxFalhasSeguidas = 5,
  tentativas = 3, cabecalhos = {}, controle = { pausado: false, cancelado: false }, relogio = RELOGIO,
}) {
  const origem = new URL(baseSei).origin;
  const metricas = { requisicoes: 0, falhas: 0 };
  // controle de velocidade: falhas aumentam a pausa (ate 8 s); sucessos a reduzem de volta
  const ritmo = { pausaMs, base: pausaMs, sucessos: 0 };
  let janela = [];
  let seguidas = 0;

  function validar(url) {
    let u;
    try { u = new URL(url, baseSei); } catch { throw new EscritaProibida("endereço inválido"); }
    if (!["http:", "https:"].includes(u.protocol)) throw new EscritaProibida("protocolo não permitido");
    if (u.username || u.password) throw new EscritaProibida("endereço com credenciais");
    if (u.origin !== origem) throw new EscritaProibida("origem não permitida");
    u.hash = "";
    let ok = false;
    try { ok = Boolean(adaptador.ativo) && adaptador.permitido(u.href); } catch { ok = false; }
    if (!ok) throw new EscritaProibida("ação fora da lista de leitura");
    return u;
  }

  async function aguardarControle() {
    while (controle.pausado && !controle.cancelado) await relogio.dormir(250);
    if (controle.cancelado) throw new Cancelado();
  }

  async function limitar() {
    for (;;) {
      const agora = relogio.agora();
      janela = janela.filter((t) => t > agora - 60000);
      if (janela.length < limitePorMinuto) break;
      await relogio.dormir(janela[0] + 60000 - agora + 1);
      await aguardarControle();
    }
    janela.push(relogio.agora());
  }

  async function get(url) {
    const u = validar(url);
    let ultimo;
    for (let t = 1; t <= tentativas; t++) {
      await aguardarControle();
      await limitar();
      if (ritmo.pausaMs) await relogio.dormir(ritmo.pausaMs);
      metricas.requisicoes++;
      try {
        const r = await fetchImpl(u.href, { method: "GET", credentials: "include", redirect: "follow", headers: cabecalhos });
        if (r.status === 429) throw new RespostaInesperada("o SEI pediu para reduzir o ritmo (429)");
        if (r.status >= 500) {
          ultimo = new Error(`HTTP ${r.status}`);
          metricas.falhas++;
          seguidas++;
          ritmo.sucessos = 0;
          ritmo.pausaMs = Math.min(8000, Math.max(ritmo.pausaMs * 2, 200));
          if (seguidas >= maxFalhasSeguidas) throw new RespostaInesperada("erros repetidos do SEI");
          continue;
        }
        const tipo = (r.headers && r.headers.get && r.headers.get("content-type")) || "text/html";
        if (!/html|text|xml/i.test(tipo)) throw new RespostaInesperada("tipo de conteúdo inesperado");
        seguidas = 0;
        if (++ritmo.sucessos % 10 === 0 && ritmo.pausaMs > ritmo.base) ritmo.pausaMs = Math.max(ritmo.base, Math.floor(ritmo.pausaMs / 2));
        const texto = await textoDaResposta(r, tipo);
        if (adaptador.ehLogin(texto)) throw new SessaoExpirada();
        return { status: r.status, texto, url: u.href };
      } catch (e) {
        if (e instanceof ErroNuspen) throw e;
        ultimo = e;
        metricas.falhas++;
        seguidas++;
        if (seguidas >= maxFalhasSeguidas) throw new RespostaInesperada("falhas de rede repetidas");
      }
    }
    throw ultimo;
  }
  return { get, metricas, controle, ritmo };
}

// O SEI da DPMS entrega ISO-8859-1 (content-type ou <meta charset>); r.text() leria como UTF-8 e trocaria cada acento por "\uFFFD"
// ("Of\uFFFDcio"). Decodifica pelo charset declarado; sem declaração, UTF-8, e volta a windows-1252 se o UTF-8 não fechar.
function charsetDe(tipo, bytes) {
  const m = /charset\s*=\s*["']?([\w-]+)/i.exec(tipo || "");
  if (m) return m[1].toLowerCase();
  const ini = new TextDecoder("latin1").decode(bytes.subarray(0, 4096));
  const n = /<meta[^>]+charset\s*=\s*["']?([\w-]+)/i.exec(ini);
  return n ? n[1].toLowerCase() : "";
}
async function textoDaResposta(r, tipo) {
  if (typeof r.arrayBuffer !== "function") return r.text();
  const bytes = new Uint8Array(await r.arrayBuffer());
  const cs = charsetDe(tipo, bytes);
  if (cs && !/^utf-?8$/.test(cs)) {
    try { return new TextDecoder(/^(iso-8859-1|latin1|us-ascii)$/.test(cs) ? "windows-1252" : cs).decode(bytes); } catch (e) { /* charset desconhecido: segue */ }
  }
  try { return new TextDecoder("utf-8", { fatal: true }).decode(bytes); } catch (e) {
    return cs ? new TextDecoder("utf-8").decode(bytes) : new TextDecoder("windows-1252").decode(bytes);
  }
}

async function sha256(texto) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(texto));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function clienteApp({ base, token, fetchImpl = fetch }) {
  const metricas = { requisicoes: 0 };
  async function chamar(caminho, corpo, metodo = "POST") {
    if (!token) throw new NaoPareado();
    metricas.requisicoes++;
    let r;
    try {
      r = await fetchImpl(`${base}${caminho}`, {
        method: metodo,
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: metodo === "POST" ? JSON.stringify(corpo ?? {}) : undefined,
      });
    } catch {
      throw new AppIndisponivel();
    }
    if (r.status === 401) throw new NaoPareado("o código de pareamento expirou ou foi revogado");
    if (r.status === 413) throw new RespostaInesperada("lote grande demais para o aplicativo");
    if (!r.ok) throw new AppIndisponivel(`o aplicativo respondeu ${r.status}`);
    return r.json();
  }
  return { chamar, metricas };
}

export const MODOS = ["todos", "novos", "documentos_novos", "selecionados", "um"];

export async function sincronizar({ adaptador, leitor, app, opcoes = {}, progresso = () => {}, registro = () => {} }) {
  const {
    modo = "todos", lote = 25, retomar = null, interromperApos = null,
    tetoProcessos = null, selecionados = [],
  } = opcoes;
  const inicio = Date.now();
  const cli = clienteApp(app);
  const ident = `${adaptador.nome}@${adaptador.versao}`;
  let lista0;
  try {
    lista0 = await leitor.get(adaptador.urlLista(app.baseSei, 0));
  } catch (e) {
    if (e instanceof SessaoExpirada) throw new SessaoAusente();
    throw e;
  }

  const ini = await cli.chamar("/api/sync/sessoes/", { modo, retomar });
  const sessao = ini.sessao;
  // escala: o registro inteiro NAO vem na abertura; pergunta-se por lotes de ids (cache local da rodada)
  const conhecidos = { ...(ini.conhecidos || {}) };
  const consultados = new Set(Object.keys(conhecidos));
  async function carregarConhecidos(chaves) {
    const faltam = chaves.filter((c) => !consultados.has(c));
    for (let i = 0; i < faltam.length; i += 1000) {
      const lote = faltam.slice(i, i + 1000);
      const r = await cli.chamar("/api/sync/conhecidos/", { ids: lote });
      Object.assign(conhecidos, r.conhecidos || {});
      lote.forEach((c) => consultados.add(c));
    }
  }
  let pagina = ini.cursor?.pagina ?? 0;
  let indice = ini.cursor?.indice ?? 0;
  const alvo = new Set(selecionados.map(String));
  const achados = new Set();
  const listados = [];
  const retrato = []; // o que a lista mostrou (atribuição, marcadores...), também dos processos não relidos nesta rodada
  const comecouDoInicio = pagina === 0 && indice === 0 && !ini.cursor?.pagina;
  const res = {
    sessao, parada: null, processos: 0, processosPulados: 0, documentosLidos: 0, documentosPulados: 0,
    falhas: 0, indisponiveis: 0, novos: 0, modificados: 0, adaptador: ident,
  };
  let buffer = [];
  let docsBuscados = 0;
  let cursorLimpo = { pagina, indice };

  const emitir = (fase) => progresso({ ...res, fase, decorridoMs: Date.now() - inicio });

  async function descarregar(cursor) {
    if (!buffer.length && !cursor) return;
    const r = await cli.chamar(`/api/sync/sessoes/${sessao}/itens/`, { itens: buffer, cursor });
    res.novos += r.novos;
    res.modificados += r.modificados;
    buffer = [];
    emitir("lendo");
  }

  async function lerProcesso(p, pg, i) {
    const locais = [];
    const vistos = [];
    const conhecidoP = conhecidos[`processo:${p.id}`];
    const pr = await leitor.get(new URL(p.href, pg.url).href);
    if (pr.status === 403 || pr.status === 404) {
      res.indisponiveis++;
      registro({ evento: "indisponivel", tipo: "processo", id: p.id, codigo: pr.status });
      return [{ tipo: "indisponivel", id_sei: p.id, motivo: `HTTP ${pr.status}` }];
    }
    const info = adaptador.lerProcesso(pr.texto);
    const numero = info.numero || p.numero;
    if (modo !== "documentos_novos") {
      locais.push({ tipo: "processo", id_sei: p.id, numero, especificacao: info.especificacao, ultima_movimentacao: p.mov, adaptador: ident, unidade: info.unidade || "", documentos_vistos: vistos });
    }
    if (info.arvore) {
      const ar = await leitor.get(new URL(info.arvore, pr.url).href);
      const docsDaArvore = adaptador.listarDocumentos(ar.texto);
      await carregarConhecidos(docsDaArvore.map((d) => `documento:${d.id}`));
      vistos.push(...docsDaArvore.map((d) => d.id));
      for (const d of docsDaArvore) {
        const k = conhecidos[`documento:${d.id}`];
        if (k && adaptador.temVersao && k.versao === d.versao) {
          res.documentosPulados++;
          continue;
        }
        if (interromperApos !== null && docsBuscados >= interromperApos) {
          const e = new Interrompido("interrompido (simulação de queda)");
          e.sessao = sessao;
          throw e;
        }
        docsBuscados++;
        try {
          const dr = await leitor.get(new URL(d.href, ar.url).href);
          if (dr.status !== 200) throw new Error(`HTTP ${dr.status}`);
          const conteudo = adaptador.lerDocumento(dr.texto);
          if (conteudo === null) throw new EstruturaInesperada("conteúdo do documento não encontrado");
          const hash = await sha256(conteudo);
          if (k && k.hash === hash) {
            res.documentosPulados++;
            continue;
          }
          locais.push({ tipo: "documento", id_sei: d.id, processo: numero, titulo: d.titulo, versao: d.versao, conteudo, hash, adaptador: ident });
          res.documentosLidos++;
          registro({ evento: "lido", tipo: "documento", id: d.id });
        } catch (e) {
          if (e instanceof ErroNuspen) throw e;
          res.falhas++;
          registro({ evento: "falha", tipo: "documento", id: d.id });
          locais.push({ tipo: "falha", id_sei: d.id, processo: numero, motivo: String(e.message).slice(0, 120) });
        }
      }
    }
    return locais;
  }

  try {
    let pg = lista0;
    if (pagina > 0) pg = await leitor.get(adaptador.urlLista(app.baseSei, pagina));
    laco: for (;;) {
      const { itens, proxima } = adaptador.listarProcessos(pg.texto);
      for (const p of itens) { listados.push(String(p.id)); if (p.extra) retrato.push({ id: String(p.id), numero: p.numero, ...p.extra }); }
      await carregarConhecidos(itens.map((p) => `processo:${p.id}`));
      for (let i = indice; i < itens.length; i++) {
        const p = itens[i];
        if (modo === "novos" && conhecidos[`processo:${p.id}`]) { res.processosPulados++; continue; }
        if (modo === "documentos_novos" && !conhecidos[`processo:${p.id}`]) { res.processosPulados++; continue; }
        if (modo === "selecionados" || modo === "um") {
          if (!alvo.has(String(p.numero)) && !alvo.has(String(p.id))) { res.processosPulados++; continue; }
        }
        if (tetoProcessos !== null && res.processos >= tetoProcessos) { res.parada = "teto"; break laco; }
        const locais = await lerProcesso(p, pg, i);
        buffer.push(...locais);
        res.processos++;
        achados.add(String(p.numero)); achados.add(String(p.id));
        cursorLimpo = { pagina, indice: i + 1 };
        emitir("lendo");
        if (buffer.length >= lote) await descarregar(cursorLimpo);
        if ((modo === "selecionados" || modo === "um") && [...alvo].every((a) => achados.has(a))) { res.parada = null; await descarregar(cursorLimpo); break laco; }
      }
      cursorLimpo = proxima ? { pagina: pagina + 1, indice: 0 } : { pagina, indice: itens.length };
      await descarregar(cursorLimpo);
      if (!proxima) break;
      pagina += 1;
      indice = 0;
      pg = await leitor.get(new URL(proxima, pg.url).href);
    }
  } catch (e) {
    if (e instanceof Interrompido) throw e;
    if (e instanceof ErroNuspen && ["sessao_expirada", "estrutura_inesperada", "resposta_inesperada", "cancelado", "fora_da_lista"].includes(e.codigo)) {
      res.parada = e.codigo;
      res.mensagemParada = e.message;
      try { await descarregar(cursorLimpo); } catch { /* o aplicativo pode estar fora; o cursor fica no ultimo envio */ }
      emitir("parada");
      return { ...res, requisicoesSei: leitor.metricas.requisicoes, falhasRede: leitor.metricas.falhas, requisicoesApp: cli.metricas.requisicoes, duracaoS: (Date.now() - inicio) / 1000 };
    }
    throw e;
  }
  await descarregar(cursorLimpo);
  const duracao = (Date.now() - inicio) / 1000;
  // lista completa so se a rodada percorreu a lista inteira desde o inicio, sem salto e sem parada
  const listaCompleta = comecouDoInicio && res.parada === null && (modo === "todos" || modo === "novos");
  if (res.parada === null || res.parada === "teto") {
    await cli.chamar(`/api/sync/sessoes/${sessao}/concluir/`, { requisicoes: leitor.metricas.requisicoes, duracao_s: duracao, ...(retrato.length ? { retrato } : {}), ...(listaCompleta ? { lista_completa: true, listados } : {}) });
  }
  emitir("concluida");
  return { ...res, requisicoesSei: leitor.metricas.requisicoes, falhasRede: leitor.metricas.falhas, requisicoesApp: cli.metricas.requisicoes, duracaoS: duracao };
}
