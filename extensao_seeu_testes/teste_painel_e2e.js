// Painel no SEEU, de ponta a ponta: Chromium com a extensão carregada, página do processo do SEEU fictícia (rota do
// Playwright, nada vai ao SEEU real) e o APTO de teste (servidor_painel.py, já no ar em 127.0.0.1:47321).
// Confere: o painel aparece na própria aba (nenhuma aba nova), o motor da extensão chega ao MESMO resultado do APTO
// ("Confere com o APTO"), recolher/abrir pela lingueta, e o estado é lembrado. Uso: node teste_painel_e2e.js [saida_dir]
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const os = require("os");

const EXT = path.join(__dirname, "..", "extensao_seeu");
const SAIDA = process.argv[2] || path.join(__dirname, "saida_painel");
const CASOS = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "casos_simulados", "casos.json"), "utf-8"));
const PAGINA = fs.readFileSync(path.join(__dirname, "seeu_processo_painel.html"), "utf-8");
const falhas = [];
const ok = (c, m) => { if (!c) falhas.push(m); };

(async () => {
  fs.mkdirSync(SAIDA, { recursive: true });
  const perfil = fs.mkdtempSync(path.join(os.tmpdir(), "apto-painel-"));
  const ctx = await chromium.launchPersistentContext(perfil, {
    headless: true, channel: "chromium", viewport: { width: 1366, height: 860 }, deviceScaleFactor: 2,
    args: [`--disable-extensions-except=${EXT}`, `--load-extension=${EXT}`],
  });
  await ctx.route("https://seeu.pje.jus.br/**", (rota) => {
    const u = new URL(rota.request().url());
    const dig = u.searchParams.get("numeroUnico") || "";
    const c = CASOS.find((x) => x.processo.replace(/\D/g, "") === dig);
    const proc = c ? c.processo : dig.replace(/^(\d{7})(\d{2})(\d{4})(\d)(\d{2})(\d{4})$/, "$1-$2.$3.$4.$5.$6");
    return rota.fulfill({ contentType: "text/html; charset=utf-8", body: PAGINA.replace(/__PROC__/g, proc).replace(/__NOME__/g, c ? c.rspe.nome : "Pessoa Fora da Base") });
  });
  let sw = ctx.serviceWorkers()[0] || await ctx.waitForEvent("serviceworker", { timeout: 15000 });
  ok(!!sw, "service worker da extensão no ar");
  const pg = ctx.pages()[0] || await ctx.newPage();
  const abasAntes = ctx.pages().length;
  const ids = (process.env.CASOS != null ? process.env.CASOS : "S001,S141,S093").split(",").filter(Boolean);
  for (const id of ids) {
    const c = CASOS.find((x) => x.id === id);
    const t0 = Date.now();
    await pg.goto("https://seeu.pje.jus.br/seeu/visualizacaoProcesso.do?actionType=visualizar&numeroUnico=" + c.processo.replace(/\D/g, ""));
    const fr = await (await pg.waitForSelector("#apto-painel", { state: "attached", timeout: 15000 })).evaluate(() => true);
    ok(fr, id + ": painel na página");
    const moldura = pg.frames().find((f) => f.url().includes("/painel/painel.html")) ||
      await new Promise((res) => { const i = setInterval(() => { const f = pg.frames().find((x) => x.url().includes("/painel/painel.html")); if (f) { clearInterval(i); res(f); } }, 100); });
    await moldura.waitForSelector(".selo, .aviso", { timeout: 60000 });
    const selo = await moldura.textContent(".selo, .aviso");
    console.log(id, "·", selo.replace(/\s+/g, " ").trim().slice(0, 110), "·", Date.now() - t0, "ms");
    ok(/Confere com o APTO/.test(selo), id + ": esperava 'Confere com o APTO', veio: " + selo);
    const margem = await pg.evaluate(() => getComputedStyle(document.documentElement).marginRight);
    ok(margem === "392px", id + ": a página reserva a largura do painel (" + margem + ")");
    await pg.screenshot({ path: path.join(SAIDA, `painel_${id}.png`) });
  }
  // processo que não está na base aberta (ou, com SEM_APTO=1, o APTO fechado): o painel orienta, sem resultado
  const fora = process.env.SEM_APTO ? "sem_apto" : "fora_da_base";
  await pg.goto("https://seeu.pje.jus.br/seeu/visualizacaoProcesso.do?actionType=visualizar&numeroUnico=00000010020268120001");
  await pg.waitForTimeout(500);
  const mf = await new Promise((res) => { const i = setInterval(() => { const f = pg.frames().find((x) => x.url().includes("/painel/painel.html")); if (f) { clearInterval(i); res(f); } }, 100); });
  await mf.waitForSelector(".aviso, .selo", { timeout: 30000 });
  const av = (await mf.textContent(".aviso, .selo")).replace(/\s+/g, " ");
  console.log("aviso ·", av.slice(0, 120));
  ok(fora === "sem_apto" ? /Abra o APTO/.test(av) : /fora da base/.test(av), "aviso de " + fora + ": " + av);
  await pg.screenshot({ path: path.join(SAIDA, "painel_" + fora + ".png") });
  ok(ctx.pages().length === abasAntes, "nenhuma aba nova aberta (" + ctx.pages().length + " x " + abasAntes + ")");
  // recolher pela moldura e reabrir pela lingueta
  const moldura = pg.frames().find((f) => f.url().includes("/painel/painel.html"));
  await moldura.waitForSelector("#recolher");
  await moldura.click("#recolher");
  await pg.waitForTimeout(300);
  ok(await pg.evaluate(() => getComputedStyle(document.documentElement).marginRight) === "0px", "recolhido: a página volta à largura toda");
  await pg.screenshot({ path: path.join(SAIDA, "painel_recolhido.png") });
  await pg.reload();
  await pg.waitForTimeout(1500);
  ok(await pg.evaluate(() => getComputedStyle(document.documentElement).marginRight) === "0px", "recolhido continua recolhido depois de recarregar");
  await ctx.close();
  if (falhas.length) { console.log("FALHOU:\n  " + falhas.join("\n  ")); process.exit(1); }
  console.log("ok: painel no SEEU (" + ids.length + " processos)");
})().catch((e) => { console.error(e); process.exit(1); });
