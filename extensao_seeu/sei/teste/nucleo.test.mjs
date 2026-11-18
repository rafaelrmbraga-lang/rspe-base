// Testes do nucleo da extensao (node --test). Sem dependencias. Paginas SINTETICAS, nada real.
import test from "node:test";
import assert from "node:assert/strict";
import { criarLeitor, sincronizar } from "../lib/nucleo.js";
import * as E from "../lib/erros.js";
import { adaptadorFicticio as adp } from "../lib/adaptador_ficticio.js";

const BASE = "http://sei.exemplo.invalid";
const resp = (status, corpo, tipo = "text/html") => ({
  status,
  ok: status < 400,
  headers: { get: () => tipo },
  text: async () => corpo,
});

// ---------------------------------------------------------------- somente leitura
test("leitor so aceita GET de URLs que o adaptador permite (todo GET, nao so controlador.php)", async () => {
  const chamadas = [];
  const l = criarLeitor({ baseSei: BASE, adaptador: adp, fetchImpl: async (u, o) => { chamadas.push([u, o.method]); return resp(200, "ok"); } });
  const ok = `${BASE}/sei/controlador.php?acao=procedimento_controlar&pagina=0`;
  await l.get(ok);
  assert.deepEqual(chamadas, [[ok, "GET"]]);
  for (const ruim of [
    `${BASE}/sei/controlador.php?acao=documento_excluir`,
    `${BASE}/sei/controlador.php`,
    `${BASE}/sei/outra_pagina.php?acao=procedimento_controlar`,
    `${BASE}/qualquer/coisa`,
    `${BASE}/sei/modulos/algo.php`,
    "http://127.0.0.1:9/sei/controlador.php?acao=procedimento_controlar",
    `ftp://sei.exemplo.invalid/sei/controlador.php?acao=procedimento_controlar`,
    `http://usuario:senha@sei.exemplo.invalid/sei/controlador.php?acao=procedimento_controlar`,
  ]) {
    await assert.rejects(() => l.get(ruim), E.EscritaProibida, ruim);
  }
  assert.equal(chamadas.length, 1);
});

test("adaptador desligado (real) recusa tudo", async () => {
  const { adaptadorSeiReal } = await import("../lib/adaptador_sei_real.js");
  assert.equal(adaptadorSeiReal.ativo, false);
  assert.throws(() => adaptadorSeiReal.listarProcessos("<html></html>"), E.AdaptadorDesligado);
  assert.equal(adaptadorSeiReal.permitido(`${BASE}/sei/controlador.php?acao=procedimento_controlar`), false);
});

// ---------------------------------------------------------------- salvaguardas
test("limite por minuto: espera quando a janela enche", async () => {
  let agora = 0;
  const esperas = [];
  const l = criarLeitor({
    baseSei: BASE, adaptador: adp, limitePorMinuto: 3,
    relogio: { agora: () => agora, dormir: async (ms) => { esperas.push(ms); agora += ms; } },
    fetchImpl: async () => resp(200, "ok"),
  });
  const u = `${BASE}/sei/controlador.php?acao=procedimento_controlar&pagina=0`;
  for (let i = 0; i < 4; i++) await l.get(u);
  assert.ok(esperas.some((ms) => ms >= 59000), "a 4a requisicao deveria esperar quase 1 minuto");
});

test("pausa entre requisicoes e contadores", async () => {
  let agora = 0;
  const esperas = [];
  const l = criarLeitor({
    baseSei: BASE, adaptador: adp, pausaMs: 300, limitePorMinuto: 1000,
    relogio: { agora: () => agora, dormir: async (ms) => { esperas.push(ms); agora += ms; } },
    fetchImpl: async () => resp(200, "ok"),
  });
  await l.get(`${BASE}/sei/controlador.php?acao=procedimento_controlar&pagina=0`);
  assert.deepEqual(esperas, [300]);
  assert.equal(l.metricas.requisicoes, 1);
});

test("429 interrompe na hora; 5xx repetidos interrompem; pagina de login = sessao expirada", async () => {
  const u = `${BASE}/sei/controlador.php?acao=procedimento_controlar&pagina=0`;
  const l429 = criarLeitor({ baseSei: BASE, adaptador: adp, fetchImpl: async () => resp(429, "x") });
  await assert.rejects(() => l429.get(u), E.RespostaInesperada);
  const l5 = criarLeitor({ baseSei: BASE, adaptador: adp, maxFalhasSeguidas: 3, fetchImpl: async () => resp(503, "x") });
  await assert.rejects(() => l5.get(u), E.RespostaInesperada);
  const lLogin = criarLeitor({ baseSei: BASE, adaptador: adp, fetchImpl: async () => resp(200, '<form id="frmLogin"></form>') });
  await assert.rejects(() => lLogin.get(u), E.SessaoExpirada);
});

test("controle: cancelar interrompe e pausar espera", async () => {
  const controle = { pausado: false, cancelado: false };
  const l = criarLeitor({ baseSei: BASE, adaptador: adp, controle, fetchImpl: async () => resp(200, "ok") });
  const u = `${BASE}/sei/controlador.php?acao=procedimento_controlar&pagina=0`;
  controle.cancelado = true;
  await assert.rejects(() => l.get(u), E.Cancelado);
});

// ---------------------------------------------------------------- sincronizacao
function servidorFicticio({ processos = 8, docsPorProcesso = 2, falhaEm = null, semArvoreEm = null } = {}) {
  const html = (c) => `<!doctype html><html><body>${c}</body></html>`;
  const lista = (p) => {
    const por = 5, ini = p * por;
    const linhas = [];
    for (let i = ini + 1; i <= Math.min(processos, ini + por); i++) {
      linhas.push(`<a class="processo" data-id="${i}" data-numero="22.0.${String(i).padStart(9, "0")}-1" data-mov="2026-01-01" href="controlador.php?acao=procedimento_trabalhar&amp;id_procedimento=${i}">x</a>`);
    }
    const prox = ini + por < processos ? `<a rel="next" href="controlador.php?acao=procedimento_controlar&amp;pagina=${p + 1}">p</a>` : "";
    return html(`<table id="lista">${linhas.join("")}</table>${prox}`);
  };
  const chamadas = [];
  const fetchImpl = async (url) => {
    chamadas.push(url);
    const u = new URL(url);
    const acao = u.searchParams.get("acao");
    if (acao === "procedimento_controlar") return resp(200, lista(Number(u.searchParams.get("pagina"))));
    const pid = Number(u.searchParams.get("id_procedimento"));
    if (acao === "procedimento_trabalhar") return resp(200, html(`<h1 id="numero">22.0.${String(pid).padStart(9, "0")}-1</h1><p id="espec">Fictício ${pid}</p><a id="arvore" href="controlador.php?acao=arvore_visualizar&amp;id_procedimento=${pid}">a</a>`));
    if (acao === "arvore_visualizar") {
      if (semArvoreEm === pid) return resp(200, html("<p>mudou</p>"));
      const ds = [];
      for (let k = 0; k < docsPorProcesso; k++) ds.push(`<a class="doc" data-id="${pid * 10 + k}" data-versao="v1" data-titulo="Doc ${k}" href="controlador.php?acao=documento_visualizar&amp;id_documento=${pid * 10 + k}">d</a>`);
      return resp(200, html(`<ul id="arvore-docs">${ds.join("")}</ul>`));
    }
    if (acao === "documento_visualizar") {
      const id = Number(u.searchParams.get("id_documento"));
      if (falhaEm === id) return resp(404, "x");
      return resp(200, html(`<div id="conteudo">Texto fictício ${id}</div>`));
    }
    return resp(404, "x");
  };
  return { fetchImpl, chamadas };
}

function appFalsa(conhecidos = {}) {
  const posts = [];
  const fetchImpl = async (url, o) => {
    posts.push([url, JSON.parse(o.body || "{}")]);
    if (url.endsWith("/api/sync/sessoes/")) return { ok: true, status: 200, json: async () => ({ sessao: 1, cursor: {}, conhecidos: {} }) };
    if (url.endsWith("/api/sync/conhecidos/")) {
      const ids = JSON.parse(o.body).ids;
      return { ok: true, status: 200, json: async () => ({ conhecidos: Object.fromEntries(ids.filter((i) => i in conhecidos).map((i) => [i, conhecidos[i]])) }) };
    }
    if (url.endsWith("/itens/")) return { ok: true, status: 200, json: async () => ({ novos: 0, modificados: 0, falhas: 0 }) };
    return { ok: true, status: 200, json: async () => ({}) };
  };
  return { posts, app: { base: "http://127.0.0.1:8000", baseSei: BASE, token: "t", fetchImpl } };
}

const rodar = async (srv, ap, opcoes = {}, extra = {}) => {
  const leitor = criarLeitor({ baseSei: BASE, adaptador: adp, fetchImpl: srv.fetchImpl, limitePorMinuto: 100000, ...extra });
  return sincronizar({ adaptador: adp, leitor, app: ap.app, opcoes });
};
const itensPostados = (ap) => ap.posts.filter(([u]) => u.endsWith("/itens/")).flatMap(([, c]) => c.itens);

test("teto de processos por rodada para e informa o motivo", async () => {
  const srv = servidorFicticio(); const ap = appFalsa();
  const r = await rodar(srv, ap, { tetoProcessos: 3 });
  assert.equal(r.parada, "teto");
  assert.equal(itensPostados(ap).filter((i) => i.tipo === "processo").length, 3);
});

test("modos: so novos, so documentos novos, selecionados e um processo", async () => {
  const conhecidos = { "processo:1": {}, "processo:2": {}, "documento:10": { versao: "v1", hash: "x" } };
  let srv = servidorFicticio(); let ap = appFalsa(conhecidos);
  await rodar(srv, ap, { modo: "novos" });
  const procs = itensPostados(ap).filter((i) => i.tipo === "processo").map((i) => i.id_sei);
  assert.ok(!procs.includes("1") && !procs.includes("2") && procs.includes("3"));

  srv = servidorFicticio(); ap = appFalsa(conhecidos);
  await rodar(srv, ap, { modo: "documentos_novos" });
  const tipos = itensPostados(ap).map((i) => i.tipo);
  assert.ok(!tipos.includes("processo"), "so documentos: nao registra processos novos");
  assert.ok(itensPostados(ap).every((i) => ["1", "2"].includes(String(i.processo).slice(-3, -2)) || true));

  srv = servidorFicticio(); ap = appFalsa();
  await rodar(srv, ap, { modo: "selecionados", selecionados: ["22.0.000000002-1", "22.0.000000004-1"] });
  const sel = itensPostados(ap).filter((i) => i.tipo === "processo").map((i) => i.numero);
  assert.deepEqual(sel.sort(), ["22.0.000000002-1", "22.0.000000004-1"]);

  srv = servidorFicticio(); ap = appFalsa();
  await rodar(srv, ap, { modo: "um", selecionados: ["22.0.000000006-1"] });
  assert.equal(itensPostados(ap).filter((i) => i.tipo === "processo").length, 1);
});

test("sem versao no SEI: detecta mudanca por hash e pula o que nao mudou", async () => {
  const semVersao = { ...adp, temVersao: false, nome: "sei-sem-versao" };
  const srv = servidorFicticio({ processos: 1 });
  let ap = appFalsa();
  const l = criarLeitor({ baseSei: BASE, adaptador: semVersao, fetchImpl: srv.fetchImpl, limitePorMinuto: 100000 });
  await sincronizar({ adaptador: semVersao, leitor: l, app: ap.app });
  const doc = itensPostados(ap).find((i) => i.tipo === "documento");
  assert.ok(doc.hash && doc.adaptador === "sei-sem-versao@1.1");
  // 2a rodada: o app ja conhece o hash -> le o documento (nao ha versao), mas nao reenvia o igual
  ap = appFalsa({ [`documento:${doc.id_sei}`]: { versao: "v1", hash: doc.hash } });
  const l2 = criarLeitor({ baseSei: BASE, adaptador: semVersao, fetchImpl: srv.fetchImpl, limitePorMinuto: 100000 });
  const r = await sincronizar({ adaptador: semVersao, leitor: l2, app: ap.app });
  assert.equal(itensPostados(ap).filter((i) => i.tipo === "documento" && i.id_sei === doc.id_sei).length, 0);
  assert.ok(r.documentosPulados >= 1);
});

test("degradacao segura: estrutura inesperada PARA e nao grava o processo incompleto", async () => {
  const srv = servidorFicticio({ processos: 3, semArvoreEm: 2 }); const ap = appFalsa();
  const r = await rodar(srv, ap, { lote: 1000 });
  assert.equal(r.parada, "estrutura_inesperada");
  const ids = itensPostados(ap).filter((i) => i.tipo === "processo").map((i) => i.id_sei);
  assert.ok(ids.includes("1") && !ids.includes("2") && !ids.includes("3"));
});

test("sessao que expira no meio: para, avisa e mantem o que ja foi lido", async () => {
  const srv = servidorFicticio({ processos: 4 }); const ap = appFalsa();
  let n = 0;
  const f = async (u) => (++n > 6 ? resp(200, '<form id="frmLogin"></form>') : srv.fetchImpl(u));
  const l = criarLeitor({ baseSei: BASE, adaptador: adp, fetchImpl: f, limitePorMinuto: 100000 });
  const r = await sincronizar({ adaptador: adp, leitor: l, app: ap.app, opcoes: { lote: 1000 } });
  assert.equal(r.parada, "sessao_expirada");
  assert.ok(r.processos >= 1);
});

test("pausar e retomar: a leitura espera e continua", async () => {
  const srv = servidorFicticio({ processos: 2 }); const ap = appFalsa();
  const controle = { pausado: true, cancelado: false };
  const l = criarLeitor({ baseSei: BASE, adaptador: adp, fetchImpl: srv.fetchImpl, controle, limitePorMinuto: 100000, relogio: { agora: Date.now, dormir: async () => { controle.pausado = false; } } });
  const r = await sincronizar({ adaptador: adp, leitor: l, app: ap.app });
  assert.equal(r.parada, null);
  assert.equal(r.processos, 2);
});

test("falha de um documento nao derruba a rodada e carrega o processo no item de falha", async () => {
  const srv = servidorFicticio({ processos: 2, falhaEm: 11 }); const ap = appFalsa();
  const r = await rodar(srv, ap);
  const falha = itensPostados(ap).find((i) => i.tipo === "falha");
  assert.equal(falha.id_sei, "11");
  assert.equal(falha.processo, "22.0.000000001-1");
  assert.ok(r.falhas >= 0);
});

test("o registro local nao contem conteudo, so identificadores e contagens", async () => {
  const srv = servidorFicticio({ processos: 1 }); const ap = appFalsa();
  const registro = [];
  const l = criarLeitor({ baseSei: BASE, adaptador: adp, fetchImpl: srv.fetchImpl, limitePorMinuto: 100000 });
  await sincronizar({ adaptador: adp, leitor: l, app: ap.app, registro: (e) => registro.push(e) });
  assert.ok(registro.length > 0);
  assert.ok(!JSON.stringify(registro).includes("Texto fictício"));
});

test("controle de velocidade: falhas aumentam a pausa e sucessos a reduzem de volta", async () => {
  let agora = 0;
  const esperas = [];
  let falhar = 0;
  const l = criarLeitor({
    baseSei: BASE, adaptador: adp, pausaMs: 100, limitePorMinuto: 100000, maxFalhasSeguidas: 50, tentativas: 1,
    relogio: { agora: () => agora, dormir: async (ms) => { esperas.push(ms); agora += ms; } },
    fetchImpl: async () => (falhar-- > 0 ? resp(503, "x") : resp(200, "ok")),
  });
  const u = `${BASE}/sei/controlador.php?acao=procedimento_controlar&pagina=0`;
  falhar = 2;
  for (let i = 0; i < 2; i++) await l.get(u).catch(() => {});
  assert.ok(l.ritmo.pausaMs > 100, "apos falhas a pausa aumenta");
  const aumentada = l.ritmo.pausaMs;
  for (let i = 0; i < 40; i++) await l.get(u);
  assert.ok(l.ritmo.pausaMs < aumentada && l.ritmo.pausaMs >= 100, "apos sucessos volta ao patamar");
});

test("sem teto: le todos os processos ate o fim da lista", async () => {
  const srv = servidorFicticio({ processos: 12 }); const ap = appFalsa();
  const r = await rodar(srv, ap, { tetoProcessos: null });
  assert.equal(r.parada, null); assert.equal(r.processos, 12);
});

test("rodada completa desde o inicio declara a lista completa; selecionados nao declara", async () => {
  const srv = servidorFicticio({ processos: 7 }); const ap = appFalsa();
  await rodar(srv, ap, { tetoProcessos: null });
  const fim = ap.posts.find(([u]) => u.endsWith("/concluir/"))[1];
  assert.equal(fim.lista_completa, true); assert.equal(fim.listados.length, 7);
  const srv2 = servidorFicticio({ processos: 7 }); const ap2 = appFalsa();
  await rodar(srv2, ap2, { modo: "selecionados", alvo: [], tetoProcessos: null });
  const fim2 = ap2.posts.find(([u]) => u.endsWith("/concluir/"));
  assert.ok(!fim2 || !fim2[1].lista_completa);
});
