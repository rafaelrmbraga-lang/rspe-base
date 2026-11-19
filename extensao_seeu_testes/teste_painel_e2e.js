// Painel no SEEU, de ponta a ponta e SEM o APTO: Chromium com a extensão carregada e as páginas do SEEU fictício (no visual
// das capturas oficiais) servidas por rota do Playwright - nada vai ao SEEU real. Confere: o painel aparece na própria aba
// (nenhuma aba nova), a extensão lê as abas em segundo plano só com GET de endereços de leitura, chega ao MESMO resultado que
// o Python do APTO (assinatura), a página reserva a largura do painel, recolher/abrir pela lingueta e o estado é lembrado;
// trocar de aba no SEEU não refaz a leitura (resultado guardado na sessão).
// Uso: python paginas_painel.py S035,S141,S006 paginas.json && node teste_painel_e2e.js paginas.json [saida_dir]
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const os = require("os");

const EXT = path.join(__dirname, "..", "extensao_seeu");
const DADOS = JSON.parse(fs.readFileSync(process.argv[2], "utf-8"));
const SAIDA = process.argv[3] || path.join(__dirname, "saida_painel");
const falhas = [];
const ok = (c, m) => { if (!c) falhas.push(m); };

(async () => {
  fs.mkdirSync(SAIDA, { recursive: true });
  const perfil = fs.mkdtempSync(path.join(os.tmpdir(), "apto-painel-"));
  const ctx = await chromium.launchPersistentContext(perfil, {
    headless: true, channel: "chromium", viewport: { width: 1366, height: 860 }, deviceScaleFactor: 2,
    args: [`--disable-extensions-except=${EXT}`, `--load-extension=${EXT}`],
  });
  let atual = null;            // o SEEU guarda o processo aberto na sessão: as abas vêm sem o número
  const pedidos = [];
  await ctx.route("https://seeu.pje.jus.br/**", (rota) => {
    const rq = rota.request();
    const u = new URL(rq.url());
    pedidos.push({ metodo: rq.method(), url: u.pathname + u.search });
    const dig = u.searchParams.get("numeroUnico");
    if (dig) atual = Object.values(DADOS).find((c) => c.processo.replace(/\D/g, "") === dig) || null;
    if (!atual) return rota.fulfill({ status: 404, body: "" });
    const chave = dig ? "/seeu/visualizacaoProcesso.do?actionType=visualizar&selectedIcon=tabInformacoesAdicionais" : u.pathname + u.search;
    const html = atual.paginas[chave];
    return html ? rota.fulfill({ contentType: "text/html; charset=utf-8", body: html }) : rota.fulfill({ status: 404, body: "" });
  });
  const sw = ctx.serviceWorkers()[0] || await ctx.waitForEvent("serviceworker", { timeout: 15000 });
  ok(!!sw, "service worker da extensão no ar");
  const pg = ctx.pages()[0] || await ctx.newPage();
  const abasAntes = ctx.pages().length;
  const moldura = async () => {
    for (let i = 0; i < 100; i++) { const f = pg.frames().find((x) => x.url().includes("/painel/painel.html")); if (f) return f; await pg.waitForTimeout(100); }
    throw new Error("moldura do painel não apareceu");
  };
  for (const [id, c] of Object.entries(DADOS)) {
    const t0 = Date.now();
    const antes = pedidos.length;
    await pg.goto("https://seeu.pje.jus.br/seeu/visualizacaoProcesso.do?actionType=visualizar&numeroUnico=" + c.processo.replace(/\D/g, ""));
    const f = await moldura();
    await f.waitForSelector(".pena, .aviso", { timeout: 90000 });
    const leg = (await f.textContent(".leg")).replace(/\s+/g, " ").trim();
    const meus = pedidos.slice(antes);
    console.log(id, "·", leg, "·", meus.length - 1, "pedidos de leitura ·", Date.now() - t0, "ms");
    ok(leg.includes(c.esperado.contagem.verde + " confere") && leg.includes(c.esperado.contagem.amarelo + " conferir"),
      id + ": contagem diferente do Python do APTO (" + leg + " x " + JSON.stringify(c.esperado.contagem) + ")");
    const assin = await sw.evaluate(async (dig) => { const g = await chrome.storage.session.get("painel:" + dig); return g["painel:" + dig] && g["painel:" + dig].resultado.painel.assinatura; }, c.processo.replace(/\D/g, ""));
    ok(assin === c.esperado.assinatura, id + ": assinatura da extensão diferente da do Python do APTO");
    ok(meus.every((p) => p.metodo === "GET"), id + ": só GET ao SEEU");
    ok(meus.every((p) => !/preAnalise|leitura|dispensar|assinar|juntar|salvar|excluir|alterar/i.test(p.url)), id + ": só endereços de leitura");
    ok(meus.some((p) => /processoCriminal\.do/.test(p.url)), id + ": leu as páginas dos processos criminais");
    ok(await pg.evaluate(() => getComputedStyle(document.documentElement).marginRight) === "392px", id + ": a página reserva a largura do painel");
    await pg.screenshot({ path: path.join(SAIDA, `painel_${id}.png`) });
    // trocar de aba no SEEU (a página recarrega): o painel volta pelo resultado guardado, sem ler as abas de novo
    const n0 = pedidos.length;
    await pg.goto("https://seeu.pje.jus.br/seeu/visualizacaoProcesso.do?actionType=visualizar&selectedIcon=tabEventos");
    const f2 = await moldura();
    await f2.waitForSelector(".pena", { timeout: 30000 });
    ok(pedidos.length - n0 === 1, id + ": trocar de aba não deve refazer a leitura (" + (pedidos.length - n0 - 1) + " pedidos a mais)");
  }
  // ficha disciplinar: carregar o PDF pelo botão do painel (a ficha é lida no navegador: pdf.js + o leitor do APTO)
  {
    const [id, c] = Object.entries(DADOS)[0];
    await pg.goto("https://seeu.pje.jus.br/seeu/visualizacaoProcesso.do?actionType=visualizar&numeroUnico=" + c.processo.replace(/\D/g, ""));
    const f = await moldura();
    await f.waitForSelector(".pena", { timeout: 60000 });
    await f.setInputFiles("#arquivoFicha", c.ficha_pdf);
    await f.waitForSelector(".ficha.verde", { timeout: 60000 });
    const txt = (await f.textContent(".ficha")).replace(/\s+/g, " ");
    console.log(id, "· ficha ·", txt.slice(0, 90));
    const assin = await sw.evaluate(async (dig) => { const g = await chrome.storage.session.get("painel:" + dig); return g["painel:" + dig] && g["painel:" + dig].resultado.painel.assinatura; }, c.processo.replace(/\D/g, ""));
    ok(c.esperado_ficha.ficha === true, id + ": a ficha gerada devia ser desta pessoa");
    ok(assin === c.esperado_ficha.assinatura, id + ": com a ficha, assinatura da extensão diferente da do Python do APTO");
    ok(/carregada no painel/.test(txt), id + ": origem da ficha dita");
    await pg.screenshot({ path: path.join(SAIDA, "painel_ficha.png") });
    await f.click('[data-acao="ficha-retirar"]');
    await f.waitForSelector(".ficha.amarelo", { timeout: 60000 });
  }
  ok(ctx.pages().length === abasAntes, "nenhuma aba nova aberta (" + ctx.pages().length + " x " + abasAntes + ")");
  const f = await moldura();
  await f.click("#recolher");
  await pg.waitForTimeout(300);
  ok(await pg.evaluate(() => getComputedStyle(document.documentElement).marginRight) === "0px", "recolhido: a página volta à largura toda");
  await pg.screenshot({ path: path.join(SAIDA, "painel_recolhido.png") });
  await pg.reload();
  await pg.waitForTimeout(1500);
  ok(await pg.evaluate(() => getComputedStyle(document.documentElement).marginRight) === "0px", "recolhido continua recolhido depois de recarregar");
  await ctx.close();
  if (falhas.length) { console.log("FALHOU:\n  " + falhas.join("\n  ")); process.exit(1); }
  console.log("ok: painel no SEEU sem o APTO (" + Object.keys(DADOS).length + " processos)");
})().catch((e) => { console.error(e); process.exit(1); });
