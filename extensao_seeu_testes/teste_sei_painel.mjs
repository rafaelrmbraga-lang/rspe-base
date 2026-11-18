// Painel do SEI (sei_painel_core.js + sei_painel.js): o motor no node e o painel no Chromium (Playwright), numa página SINTÉTICA
// com o formato do Controle de Processos (sei_controle.html), servida no endereço do SEI da Defensoria, sem rede.
// Uso: node extensao_seeu_testes/teste_sei_painel.mjs [pasta-para-o-print]
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const AQUI = path.dirname(fileURLToPath(import.meta.url));
const EXT = path.join(AQUI, "..", "extensao_seeu");
const C = require(path.join(EXT, "sei_painel_core.js"));
const HOJE = new Date(2026, 10, 18, 12);
let falhas = 0;
const t = (nome, fn) => { try { fn(); } catch (e) { falhas++; console.log("FALHA:", nome, "-", e.message); } };

// ---------- motor ----------
t("busca sem acento e sem pontuação", () => {
  assert.equal(C.norm("Execução  Penal 7000101-11.2026"), "execucao penal 7000101112026");
});
t("dica do SEI com aspas escapadas", () => {
  assert.deepEqual(C.argsDica("return infraTooltipMostrar('Ofício d\\'água','Ofício');"), ["Ofício d'água", "Ofício"]);
});
t("prazo: ATÉ data = vencimento, com nível", () => {
  const p = C.prazoDe([{ texto: "Prazo LEP ATÉ 17/11/2026 - manifestar", origem: "marcador" }], HOJE);
  assert.deepEqual([p.tipo, p.dias, p.nivel, p.rotulo], ["vence", -1, "vencido", "vencido há 1 d"]);
  assert.equal(C.prazoDe([{ texto: "ate 20/11/2026", origem: "marcador" }], HOJE).nivel, "critico");
  assert.equal(C.prazoDe([{ texto: "vence 22/11/2026", origem: "marcador" }], HOJE).nivel, "alerta");
  assert.equal(C.prazoDe([{ texto: "vence 22/11/2026", origem: "marcador" }], HOJE, { alertaDias: 3 }).nivel, "ok");
  assert.equal(C.prazoDe([{ texto: "ATÉ 18/11/2026", origem: "marcador" }], HOJE).rotulo, "vence hoje");
  assert.equal(C.prazoDe([{ texto: "até 20/11", origem: "anotacao" }], HOJE).data, "20/11/2026");
});
t("prazo: só a data no marcador = parado desde; vale o vencimento mais próximo", () => {
  const p = C.prazoDe([{ texto: "Inspeção 10/11/2026", origem: "marcador" }], HOJE);
  assert.deepEqual([p.tipo, p.dias, p.rotulo], ["desde", 8, "há 8 d"]);
  const q = C.prazoDe([{ texto: "ATE 30/11/2026", origem: "marcador" }, { texto: "responder até 25/11/2026", origem: "anotacao" }], HOJE);
  assert.equal(q.data, "25/11/2026");
  assert.equal(C.prazoDe([{ texto: "Prazo", origem: "prazo" }], HOJE), null);
  assert.equal(C.prazoDe([{ texto: "31/02/2026", origem: "marcador" }], HOJE), null, "data impossível");
  assert.equal(C.prazoDe([{ texto: "Controle de prazo: 01/12/2026", origem: "prazo" }], HOJE).dias, 13);
});
t("categoria: regra da pessoa antes da do APTO", () => {
  assert.equal(C.categoria({ tipo: "Execução Penal - Indulto" }).id, "execucao");
  assert.equal(C.categoria({ tipo: "Inspeção - Unidade Prisional" }).id, "prisional");
  assert.equal(C.categoria({ tipo: "Ofício" }).id, "oficio");
  assert.equal(C.categoria({ tipo: "Qualquer coisa" }).id, "geral");
  assert.equal(C.categoria({ tipo: "Ofício", especificacao: "Ofício à AGEPEN" }).id, "oficio", "o tipo decide antes da especificação");
  assert.equal(C.categoria({ tipo: "Diversos", especificacao: "inspeção no presídio" }).id, "prisional", "sem pista no tipo, vale a especificação");
  const r = C.regrasDoTexto("indulto: #ff0000\nlinha ruim\n remição = teal ");
  assert.deepEqual(r, [{ palavra: "indulto", cor: "#ff0000" }, { palavra: "remição", cor: "teal" }]);
  const c = C.categoria({ tipo: "Execução Penal - Indulto" }, r);
  assert.deepEqual([c.cor, c.regra], ["#ff0000", true]);
});
t("filtros, busca e resumo", () => {
  const ps = C.enriquecer([
    { numero: "1", tipo: "Ofício", especificacao: "URGENTE resposta", atribuicao: "", marcadores: [], naoVisualizado: true },
    { numero: "2", tipo: "Execução Penal", especificacao: "Progressão", atribuicao: "ana", marcadores: [{ nome: "LEP", texto: "ATE 17/11/2026" }], anotacao: "ver cálculo" },
  ], { hoje: HOJE, monitorados: { 2: {} } });
  const R = C.resumo(ps);
  assert.deepEqual([R.total, R.naoVisualizados, R.vencidos, R.urgentes, R.semAtribuicao, R.monitorados, R.comAnotacao], [2, 1, 1, 1, 1, 1, 1]);
  assert.deepEqual(R.porMarcador, [["LEP", 1]]);
  assert.equal(ps.filter((p) => C.passa(p, { campo: "rapido", valor: "vencidos" }, "")).length, 1);
  assert.equal(ps.filter((p) => C.passa(p, null, "calculo")).length, 1, "busca acha a anotação sem acento");
  assert.equal(ps.filter((p) => C.passa(p, null, "ca")).length, 2, "menos de 3 letras não filtra");
  assert.equal(ps.filter((p) => C.passa(p, { campo: "atribuicao", valor: "" }, "")).length, 1);
  assert.ok(C.chavePrazo(ps[1]) < C.chavePrazo(ps[0]), "vencido antes de sem prazo");
  const csv = C.csv(ps);
  assert.ok(csv.startsWith("﻿Processo;Tipo;"), "planilha com BOM e ;");
  assert.match(csv, /2;Execução Penal;Progressão;ana;;LEP;ver cálculo;vencido há 1 d;17\/11\/2026;Execução penal;;/);
});
t("histórico: o mais recente no topo, sem repetir, até 60", () => {
  let h = [];
  for (let i = 0; i < 70; i++) h = C.registrarVisita(h, { numero: String(i % 65) }, i);
  assert.equal(h.length, 60);
  assert.equal(h[0].numero, "4");
  assert.equal(new Set(h.map((x) => x.numero)).size, 60);
});

// ---------- painel no navegador ----------
let chromium = null;
try { ({ chromium } = require("playwright")); } catch (e) { console.log("(sem Playwright: só o motor foi testado)"); }
if (chromium) {
  const html = fs.readFileSync(path.join(AQUI, "sei_controle.html"), "utf-8");
  const scripts = ["sei_painel_core.js", "sei_painel.js"].map((f) => fs.readFileSync(path.join(EXT, f), "utf-8"));
  const URL0 = "https://sei.defensoria.ms.def.br/sei/controlador.php?acao=procedimento_controlar&infra_hash=aaaa";
  const browser = await chromium.launch();
  const saida = process.argv[2];
  async function abrir(estado, largura) {
    const page = await browser.newPage({ viewport: { width: largura || 1360, height: 1000 }, deviceScaleFactor: saida ? 2 : 1 });
    await page.clock.setFixedTime(HOJE);
    await page.route("**/*", (r) => (r.request().url().startsWith(URL0) ? r.fulfill({ contentType: "text/html; charset=utf-8", body: html }) : r.fulfill({ status: 204, body: "" })));
    // chrome.storage de mentira (o da extensão), com o estado inicial do teste
    await page.addInitScript((ini) => {
      const dados = JSON.parse(ini);
      window.__gravado = dados;
      window.chrome = { storage: { local: {
        get: async (k) => { const r = {}; for (const x of [].concat(k)) if (x in dados) r[x] = JSON.parse(JSON.stringify(dados[x])); return r; },
        set: async (o) => { Object.assign(dados, JSON.parse(JSON.stringify(o))); },
      } } };
    }, JSON.stringify(estado || {}));
    await page.goto(URL0);
    for (const s of scripts) await page.addScriptTag({ content: s });
    await page.waitForSelector("#apto-sei-painel");
    return page;
  }
  const sombra = (page, sel) => page.locator("#apto-sei-painel").locator(sel);
  try {
    const page = await abrir({ seiMonitorados: { "7000102-22.2026.8.12.0001": { tipo: "Execução Penal - Livramento Condicional", quando: 1 } },
      seiHistorico: [{ numero: "7000104-44.2026.8.12.0001", tipo: "Ofício", especificacao: "Ofício à AGEPEN sobre transferência", quando: HOJE.getTime() - 3600e3 }] });
    const procs = await page.evaluate(() => window.__aptoSeiPainelProcs());
    t("lê as 10 linhas das duas tabelas", () => assert.equal(procs.length, 10));
    const p1 = procs.find((p) => p.numero === "7000101-11.2026.8.12.0001");
    t("linha: tipo, especificação, atribuição, interessado, marcador e prazo", () => {
      assert.equal(p1.tipo, "Execução Penal - Progressão de Regime");
      assert.equal(p1.especificacao, "Pedido de progressão ao semiaberto");
      assert.equal(p1.atribuicao, "ana.souza");
      assert.deepEqual(p1.interessados, ["Fulano de Tal Exemplo"]);
      assert.deepEqual(p1.marcadores.map((m) => m.nome), ["Prazo LEP"]);
      assert.equal(p1.prazo.nivel, "vencido");
    });
    t("anotação (com prioridade) e urgente", () => {
      const p3 = procs.find((p) => p.numero.startsWith("7000103"));
      assert.match(p3.anotacao, /mutirão/);
      assert.equal(p3.anotacaoPrioridade, true);
      assert.equal(p3.urgente, true);
    });
    const n = async (f) => Number(await sombra(page, `.card[data-valor="${f}"] .n`).textContent());
    const cart = { todos: await n("todos"), naoVisualizados: await n("naoVisualizados"), vencidos: await n("vencidos"), vencendo: await n("vencendo"),
      urgentes: await n("urgentes"), semAtribuicao: await n("semAtribuicao"), comAnotacao: await n("comAnotacao"), monitorados: await n("monitorados") };
    t("cartões com as contas da página", () => assert.deepEqual(cart, { todos: 10, naoVisualizados: 3, vencidos: 1, vencendo: 2, urgentes: 1, semAtribuicao: 3, comAnotacao: 3, monitorados: 1 }));
    const titulo = await page.title();
    t("título da aba com os não visualizados", () => assert.equal(titulo, "(3) SEI - Controle de Processos"));
    const visiveis = async () => page.locator("tr[id^='P']:not(.apto-oculto)").count();
    await sombra(page, '.card[data-valor="vencendo"]').click();
    const v1 = await visiveis();
    t("clicar num cartão filtra a lista", () => assert.equal(v1, 2));
    await sombra(page, '.card[data-valor="vencendo"]').click();
    const v2 = await visiveis();
    t("clicar de novo tira o filtro", () => assert.equal(v2, 10));
    await sombra(page, "input").fill("agepen");
    const v3 = await visiveis();
    t("busca rápida", () => assert.equal(v3, 1));
    await sombra(page, "input").fill("");
    await sombra(page, '.barra[data-campo="categoria"][data-valor="prisional"]').click();
    const v4 = await visiveis();
    t("barra de categoria filtra", () => assert.equal(v4, 2));
    await sombra(page, 'button[data-acao="limpar"]').click();
    await page.locator("#P104 .apto-deco .mon").click();
    await page.waitForTimeout(50);
    const mon = await page.evaluate(() => Object.keys(window.__gravado.seiMonitorados || {}));
    t("monitorar guarda no navegador", () => assert.ok(mon.includes("7000104-44.2026.8.12.0001")));
    await sombra(page, 'button[data-acao="ordem"]').click();
    const ordem = await page.locator("#tblProcessosRecebidos tr[id^='P']").evaluateAll((l) => l.map((x) => x.id));
    t("ordenar por prazo: vencido, vence hoje/amanhã, … sem prazo no fim", () => assert.deepEqual(ordem.slice(0, 3), ["P101", "P106", "P102"]));
    await sombra(page, 'button[data-acao="ordem"]').click();
    const atalhos = await sombra(page, ".links a").allTextContents();
    t("atalhos do menu do SEI", () => assert.deepEqual(atalhos, ["Pesquisa", "Blocos de assinatura", "Acompanhamento especial", "Retorno programado", "Marcadores", "Estatísticas"]));
    const pedidos = [];
    page.on("request", (r) => pedidos.push(r.url()));
    await sombra(page, '.card[data-valor="urgentes"]').click();
    await sombra(page, '.card[data-valor="urgentes"]').click();
    t("o painel não faz nenhum pedido ao SEI", () => assert.deepEqual(pedidos, []));
    if (saida) {
      fs.mkdirSync(saida, { recursive: true });
      await page.screenshot({ path: path.join(saida, "painel_sei.png"), fullPage: true });
      await sombra(page, 'button[data-acao="tema"]').click();
      await page.screenshot({ path: path.join(saida, "painel_sei_escuro.png"), fullPage: true });
    }
    await page.close();
    // desligado no painel da extensão: nada aparece
    const p2 = await browser.newPage();
    await p2.route("**/*", (r) => r.fulfill({ contentType: "text/html; charset=utf-8", body: html }));
    await p2.addInitScript(() => { window.chrome = { storage: { local: { get: async () => ({ seiPainel: { ligado: false } }), set: async () => {} } } }; });
    await p2.goto(URL0);
    for (const s of scripts) await p2.addScriptTag({ content: s });
    await p2.waitForTimeout(150);
    const nada = await p2.locator("#apto-sei-painel, .apto-deco").count();
    t("painel desligado: a página fica como o SEI entregou", () => assert.equal(nada, 0));
  } finally {
    await browser.close();
  }
}
if (falhas) { console.log(`${falhas} falha(s)`); process.exit(1); }
console.log("painel do SEI: ok");
