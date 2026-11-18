// Telas SEEU e SEI do APTO no navegador (ver teste_ui_sei_seeu.py, que gera os dados fictícios). Sem Playwright, avisa e sai.
const fs = require("fs");
const path = require("path");
let chromium;
try { ({ chromium } = require("playwright")); } catch (e) { console.log("ok: (sem Playwright: telas SEEU e SEI não testadas)"); process.exit(0); }
const FX = JSON.parse(fs.readFileSync(process.argv[2], "utf-8"));
const SHOTS = process.env.APTO_CAPTURAS || "";
(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage({ viewport: { width: 1400, height: 900 } });
  const erros = [];
  pg.on("pageerror", (e) => erros.push(String(e)));
  await pg.addInitScript((fx) => {
    window.__chamadas = [];
    const reg = [{ id: "r1", nome: "FULANO DE TAL FICTICIO", proc: "7000117-54.2016.8.12.0001" }];
    const L = {
      listar: () => ({ sem_base: true, recentes: [], hoje: "18/11/2026", registros: [] }),
      seeu_triagem: () => fx.triagem,
      sei_resumo: () => fx.resumo,
      sei_processo: (n) => fx.processos[n],
      sei_decidir: (id, st, m) => { window.__chamadas.push(["decidir", id, st, m]); const o = Object.values(fx.processos).flatMap((p) => p.obrigacoes).find((x) => x.id === id); if (o) o.status = st; return { ok: true }; },
      sei_para_quadro: (id) => { window.__chamadas.push(["quadroSei", id]); return { ok: true }; },
      seeu_para_quadro: (...a) => { window.__chamadas.push(["quadroSeeu", ...a]); return { ok: true }; },
      abrir_seeu: (u) => { window.__chamadas.push(["abrir", u]); return { ok: true }; },
    };
    window.__mockApi = new Proxy(L, { get: (t, k) => t[k] || (() => ({})) });
    window.__reg = reg;
  }, FX);
  pg.on("dialog", (d) => d.accept(d.type() === "prompt" ? "não é obrigação do núcleo" : undefined));
  await pg.goto("file://" + path.join(__dirname, "..", "ui.html"));
  await pg.waitForTimeout(500);
  await pg.evaluate(() => { ui.dados.registros = window.__reg; ui.dados.base = "Base fictícia"; ui.abrir = (id) => window.__chamadas.push(["ficha", id]); });
  const falhas = [];
  const ok = (c, m) => { if (!c) falhas.push(m); };
  // ---- SEEU ----
  await pg.click("#fn_seeu");
  await pg.waitForTimeout(400);
  ok((await pg.$$eval("#seeuPag .fx-l", (x) => x.length)) === 2, "SEEU: duas linhas da Mesa");
  const prazo1 = await pg.textContent("#seeuPag .fx-l:first-child .fx-prazo");
  ok(/Resposta até/.test(prazo1) && /▲/.test(prazo1) && /faltam 1 d/.test(prazo1), "prazo com rótulo, forma e texto: " + prazo1);
  ok(await pg.isVisible("#seeuPag .fx-base"), "ligado ao assistido da base aberta");
  await pg.click("#seeuPag .fx-base");
  ok((await pg.evaluate(() => window.__chamadas)).some((c) => c[0] === "ficha" && c[1] === "r1"), "abre a ficha do assistido");
  await pg.click('#seeuPag .fx-cont button:has-text("providência urgente")');
  ok((await pg.$$eval("#seeuPag .fx-l", (x) => x.length)) === 1 && (await pg.getAttribute('#seeuPag .fx-cont button:has-text("providência urgente")', "aria-pressed")) === "true", "contador filtra (aria-pressed)");
  await pg.focus("#seeuPag .fx-l");
  await pg.keyboard.press("Enter");
  await pg.waitForTimeout(200);
  ok(await pg.isVisible("#seeuPag .fx-det"), "linha abre pelo teclado (Enter)");
  if (SHOTS) await pg.screenshot({ path: path.join(SHOTS, "seeu.png") });
  await pg.click('#seeuPag .fx-det button:has-text("Enviar ao Quadro")');
  await pg.waitForTimeout(200);
  ok((await pg.evaluate(() => window.__chamadas)).some((c) => c[0] === "quadroSeeu" && c[1] === "7000117-54.2016.8.12.0001"), "providência vai ao Quadro");
  await pg.click('#seeuPag .fx-det button:has-text("Abrir no SEEU")');
  ok((await pg.evaluate(() => window.__chamadas)).some((c) => c[0] === "abrir"), "abre o processo no SEEU pelo navegador");
  // ---- SEI ----
  await pg.click("#fn_sei");
  await pg.waitForTimeout(400);
  ok((await pg.$$eval("#seiPag .fx-proc", (x) => x.length)) === 2, "SEI: dois processos");
  ok(/a validar/.test(await pg.textContent("#seiPag .fx-proc")), "processo mostra quantas obrigações a validar");
  await pg.click("#seiPag .fx-proc");
  await pg.waitForTimeout(400);
  const n = await pg.$$eval("#seiDet .fx-obr", (x) => x.length);
  ok(n >= 2, "obrigações sugeridas do processo: " + n);
  const t = await pg.textContent("#seiDet");
  ok(/prazo no documento: 30 dias/.test(t) && /vencimento não calculado/.test(t), "prazo expresso sem vencimento");
  ok(/“[^”]*Determino[^”]*”/.test(t), "frase de origem (fonte)");
  if (SHOTS) await pg.screenshot({ path: path.join(SHOTS, "sei.png") });
  await pg.click('#seiDet .fx-obr button:has-text("Validar")');
  await pg.waitForTimeout(400);
  ok((await pg.evaluate(() => window.__chamadas)).some((c) => c[0] === "decidir" && c[2] === "validada"), "validar");
  await pg.click('#seiDet .fx-obr button:has-text("Rejeitar")');
  await pg.waitForTimeout(400);
  ok((await pg.evaluate(() => window.__chamadas)).some((c) => c[0] === "decidir" && c[2] === "rejeitada" && c[3]), "rejeitar com motivo");
  await pg.click('#seiDet .fx-obr button:has-text("Enviar ao Quadro")');
  await pg.waitForTimeout(300);
  ok((await pg.evaluate(() => window.__chamadas)).some((c) => c[0] === "quadroSei"), "obrigação ao Quadro");
  await pg.click("#seiDet .fx-docb");
  await pg.waitForTimeout(200);
  ok(await pg.isVisible("#seiDet .fx-pre"), "texto do documento abre");
  ok(!erros.length, "erros na página: " + erros.join(" | "));
  await b.close();
  if (falhas.length) { console.log("FALHA: " + falhas.join("; ")); process.exit(1); }
  console.log("ok: telas SEEU (prazo com forma e texto, filtro, teclado, ficha da base, Quadro, abrir no SEEU) e SEI (obrigações com fonte, prazo sem vencimento, validar/rejeitar, Quadro, documento)");
})().catch((e) => { console.log("FALHA: " + e); process.exit(1); });
