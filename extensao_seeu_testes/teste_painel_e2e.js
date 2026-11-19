// Painel no SEEU, de ponta a ponta e SEM o APTO: Chromium com a extensão carregada e as páginas do SEEU fictício (no visual
// das capturas oficiais) servidas por rota do Playwright - nada vai ao SEEU real. Confere: o painel aparece na própria aba
// (nenhuma aba nova), a extensão busca em segundo plano só o RSPE do processo (um GET, pelo link da página), lê o PDF no
// navegador e chega ao MESMO resultado que o Python do APTO lendo o mesmo PDF (assinatura), a página reserva a largura do painel, recolher/abrir pela lingueta e o estado é lembrado;
// trocar de aba no SEEU não refaz a leitura (resultado guardado na sessão).
// Uso: python paginas_painel.py S035,S141,S006 paginas.json && node teste_painel_e2e.js paginas.json [saida_dir]
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const os = require("os");

const EXT = process.env.APTO_EXT || path.join(__dirname, "..", "extensao_seeu");   // APTO_EXT: outra pasta (ex.: a extensão APTO SEEU)
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
    if (/\/seeu\/arquivo\.do$/.test(u.pathname)) {   // documento juntado: o PDF (aqui, o próprio RSPE do caso)
      return rota.fulfill({ contentType: "application/pdf", headers: { "content-disposition": "attachment; filename=online.pdf" }, body: fs.readFileSync(atual.rspe_pdf) });
    }
    if (/processoExecucaoPenal\.do$/.test(u.pathname) && u.searchParams.get("actionType") === "emitirRelatorioPenaAlternativa") {
      return atual.alt_pdf && u.pathname + u.search === atual.url_alt
        ? rota.fulfill({ contentType: "application/pdf", body: fs.readFileSync(atual.alt_pdf) }) : rota.fulfill({ status: 404, body: "" });
    }
    if (rq.method() === "POST" && /visualizacaoProcesso\.do$/.test(u.pathname)) {   // troca de aba (o mesmo pedido do SEEU)
      const ic = new URLSearchParams(rq.postData() || "").get("selectedIcon") || "";
      const h = atual.paginas["/seeu/visualizacaoProcesso.do?actionType=visualizar&selectedIcon=" + ic];
      return h ? rota.fulfill({ contentType: "text/html; charset=utf-8", body: h }) : rota.fulfill({ status: 404, body: "" });
    }
    if (/processoExecucaoPenal\.do$/.test(u.pathname)) {
      return u.pathname + u.search === atual.url_rspe
        ? rota.fulfill({ contentType: "application/pdf", body: fs.readFileSync(atual.rspe_pdf) }) : rota.fulfill({ status: 404, body: "" });
    }
    const chave = dig ? "/seeu/visualizacaoProcesso.do?actionType=visualizar&selectedIcon=tabInformacoesAdicionais" : u.pathname + u.search;
    const html = atual.paginas[chave];
    return html ? rota.fulfill({ contentType: "text/html; charset=utf-8", body: html }) : rota.fulfill({ status: 404, body: "" });
  });
  await ctx.grantPermissions(["clipboard-read", "clipboard-write"], { origin: "https://seeu.pje.jus.br" });
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
    await f.waitForSelector(".h-al, .aviso", { timeout: 90000 });
    const leg = (await f.textContent(".leg")).replace(/\s+/g, " ").trim();
    const meus = pedidos.slice(antes);
    console.log(id, "·", leg, "·", meus.length - 1, "pedido de leitura ·", Date.now() - t0, "ms");
    ok(leg.includes(c.esperado.contagem.verde + " confere") && leg.includes(c.esperado.contagem.amarelo + " conferir"),
      id + ": contagem diferente do Python do APTO (" + leg + " x " + JSON.stringify(c.esperado.contagem) + ")");
    const assin = await sw.evaluate(async (dig) => { const g = await chrome.storage.session.get("painel:" + dig); return g["painel:" + dig] && g["painel:" + dig].resultado.painel.assinatura; }, c.processo.replace(/\D/g, ""));
    ok(assin === c.esperado.assinatura, id + ": assinatura da extensão diferente da do Python do APTO");
    ok(meus.every((p) => p.metodo === "GET" || (c.prd && p.url === "/seeu/visualizacaoProcesso.do?actionType=visualizar")),
      id + ": só GET ao SEEU (e, com medidas, a leitura da aba Medidas Diversas da Prisão)");
    ok(meus.every((p) => !/preAnalise|leitura|dispensar|assinar|juntar|salvar|excluir|alterar/i.test(p.url)), id + ": só endereços de leitura");
    ok(c.prd ? meus.length === 4 && meus[1].url === c.url_rspe && meus[3].url === c.url_alt
      : meus.length === 2 && meus[1].url === c.url_rspe, id + ": pedidos ao SEEU: a página, o RSPE" + (c.prd ? ", a aba das medidas e o relatório da pena alternativa" : "") +
      " (" + meus.map((p) => p.metodo + " " + p.url.slice(0, 60)).join(" | ") + ")");
    if (c.prd) ok(/Prestação pecuniária: faltam R\$ [\d.,]+ · R\$ [\d.,]+ em atraso/.test(await f.textContent("#corpo")) && /PSC: faltam [\d,]+ h · [\d,]+ h em atraso/.test(await f.textContent("#corpo")),
      id + ": cumprimento da restritiva no painel (o que falta e o que já venceu, pecuniária e PSC)");
    ok(await pg.evaluate(() => getComputedStyle(document.documentElement).marginRight) === "392px", id + ": a página reserva a largura do painel");
    // chips logo abaixo de "Execução nº" (marcos do APTO, na página); ao rolar, a barra fixa com o nº e o nome
    await pg.waitForSelector("#apto-chips .sg", { timeout: 15000 });
    ok(await pg.evaluate(() => document.getElementById("barraTituloStatusProcessual").nextElementSibling.id === "apto-chips"), id + ": chips logo abaixo do nº do processo");
    const nseg = await pg.locator("#apto-chips button.sg").count();
    ok(nseg >= 2, id + ": chips com os marcos (" + nseg + ")");
    // saída temporária / progressão antecipada: o checklist dos requisitos aparece ao passar o mouse
    const comPop = pg.locator("#apto-chips .benw:has(.pop)");
    if (await comPop.count()) {
      await comPop.first().hover();
      ok(await comPop.first().locator(".pop").isVisible(), id + ": checklist dos requisitos ao passar o mouse");
      await pg.screenshot({ path: path.join(SAIDA, `chips_checklist_${id}.png`) });
      await pg.mouse.move(5, 700);
    }
    await pg.screenshot({ path: path.join(SAIDA, `painel_${id}.png`) });
    if (id === Object.keys(DADOS)[0]) {
      await pg.locator("#apto-chips button.sg").first().click();
      ok(await pg.locator("#apto-chips .det:not([hidden])").count() === 1, id + ": o chip abre o seu detalhe no clique");
      // chip de benefício: abre o painel no cartão dele (destacado)
      const ben = pg.locator("#apto-chips button.ben").first();
      ok(await ben.count() === 1, id + ": chips dos benefícios na página");
      const alvo = await ben.getAttribute("data-focar");
      await ben.click();
      await f.waitForSelector(`[data-id="${alvo}"].foco`, { timeout: 5000 }).catch(() => null);
      ok(await f.evaluate((a) => { const el = document.querySelector(`[data-id="${a}"]`); return !!el && document.activeElement === el; }, alvo),
        id + ": o chip " + alvo + " leva ao cartão no painel");
      await pg.screenshot({ path: path.join(SAIDA, "chips_beneficio.png") });
      await pg.evaluate(() => { document.body.style.paddingBottom = "2400px"; window.scrollTo(0, 1200); });
      await pg.waitForSelector("#apto-barra .barra.on", { timeout: 5000 });
      await pg.waitForTimeout(400);   // fim da entrada da barra
      const fx = await pg.locator("#apto-barra .barra").boundingBox();
      ok(fx && fx.y === 0 && Math.round(1366 - (fx.x + fx.width)) === 392, id + ": barra fixa no alto, sem cobrir o painel (" + JSON.stringify(fx) + ")");
      await pg.screenshot({ path: path.join(SAIDA, "chips_barra_fixa.png") });
      for (const [q, esperado] of [["processo", c.processo], ["nome", c.nome]]) {
        await pg.locator(`#apto-barra [data-copiar="${q}"]`).click();
        const t = await pg.evaluate(() => navigator.clipboard.readText()).catch((e) => "erro: " + e);
        ok(t === esperado, id + ": copiar " + q + " (" + t + ")");
      }
      await pg.evaluate(() => { window.scrollTo(0, 0); });
      await pg.waitForFunction(() => !document.querySelector("#apto-barra").shadowRoot.querySelector(".barra.on"), null, { timeout: 5000 });
    }
    // trocar de aba no SEEU (a página recarrega): o painel volta pelo resultado guardado, sem ler as abas de novo
    const n0 = pedidos.length;
    await pg.goto("https://seeu.pje.jus.br/seeu/visualizacaoProcesso.do?actionType=visualizar&selectedIcon=tabEventos");
    const f2 = await moldura();
    await f2.waitForSelector(".h-al", { timeout: 30000 });
    ok(pedidos.length - n0 === 1, id + ": trocar de aba não deve refazer a leitura (" + pedidos.slice(n0 + 1).map((p) => p.url.slice(0, 90)).join(" | ") + ")");
  }
  // destaques da aba Movimentações: pela categoria do evento; rotina esmaecida; filtros na barra acima da tabela
  {
    const [id] = Object.entries(DADOS)[0];
    await pg.goto("https://seeu.pje.jus.br/seeu/visualizacaoProcesso.do?actionType=visualizar&selectedIcon=tabMovimentacoesProcesso");
    await pg.waitForSelector("#apto-movs .ch", { timeout: 15000 });
    const cat = async () => pg.evaluate(() => [...document.querySelectorAll("table.resultTable tbody > tr[id^='mov']")].map((tr) =>
      [tr.dataset.aptoMov, getComputedStyle(tr).display !== "none", getComputedStyle(tr.children[1]).opacity, (tr.querySelector(".apto-tag") || {}).textContent || "",
        tr.dataset.aptoArq, getComputedStyle(tr.children[0]).boxShadow]));
    let L = await cat();
    ok(L[1][0] === "decisao" && L[1][3] === "Decisão" && L[3][0] === "mp" && L[5][0] === "unidade" && L[6][0] === "defensoria" && L[8][0] === "despacho" && L[9][0] === "audiencia",
      id + ": movimentações classificadas pelo conteúdo (" + L.map((x) => x[0]).join(",") + ")");
    ok(L[0][0] === "cartorio" && L[0][3] === "Cartório" && /217, 102, 31/.test(L[0][5]), id + ": cartório em laranja, com etiqueta (" + L[0][5] + ")");
    ok(L[3][0] === "mp" && /179, 38, 30/.test(L[3][5]) && L[6][0] === "defensoria" && L[6][3] === "DPE" && /29, 122, 74/.test(L[6][5]), id + ": MP em vermelho, DPE em verde");
    ok(L.every((x) => (x[4] === "0") === (x[2] === "0.45")), id + ": esmaecido só o que não tem arquivo vinculado (" + L.map((x) => x[4] + ":" + x[2]).join(",") + ")");
    await pg.screenshot({ path: path.join(SAIDA, "movimentacoes.png"), fullPage: true });
    // prévia do documento ao passar o mouse no link (sem nova aba): o quadro abre ao lado, com a 1ª página desenhada
    const nAbas = ctx.pages().length;
    await pg.locator('a[href*="/seeu/arquivo.do"]').first().hover();
    await pg.waitForSelector("#apto-previa .q.on", { timeout: 8000 });
    const pv = pg.frames().find((x) => x.url().includes("/painel/previa.html"));
    await pv.waitForSelector("canvas", { timeout: 20000 });
    ok(await pv.locator("canvas").count() >= 1, id + ": prévia do documento desenhada");
    ok(ctx.pages().length === nAbas, id + ": a prévia não abre aba");
    const caixa = await pg.locator("#apto-previa .q").boundingBox();
    ok(caixa && caixa.x + caixa.width <= 1366 - 392, id + ": a prévia não cobre o painel (" + JSON.stringify(caixa) + ")");
    await pg.screenshot({ path: path.join(SAIDA, "previa_documento.png") });
    await pg.locator("#apto-previa #b").click();   // Expandir: ocupa a página sem cobrir o painel e não fecha ao tirar o mouse
    await pg.mouse.move(5, 5);
    await pg.waitForTimeout(600);
    const gr = await pg.locator("#apto-previa .q").boundingBox();
    ok(gr && gr.width > 800 && gr.x + gr.width <= 1366 - 392 && await pg.locator("#apto-previa .q").isVisible(), id + ": expandir amplia a prévia (" + JSON.stringify(gr) + ")");
    await pg.screenshot({ path: path.join(SAIDA, "previa_expandida.png") });
    await pg.keyboard.press("Escape");
    ok(await pg.locator("#apto-previa .q").isHidden(), id + ": Esc fecha a prévia");
    // opção "abrir os documentos no 2º monitor": o clique no link abre a janela do documento (desenhado pela extensão)
    const cfgDoc = (v) => sw.evaluate(async (x) => { const { cfg } = await chrome.storage.local.get("cfg"); await chrome.storage.local.set({ cfg: Object.assign({}, cfg || {}, { docMonitor2: x }) }); }, v);
    await cfgDoc(true);
    await pg.waitForTimeout(300);
    await pg.mouse.move(5, 5);
    const [janela] = await Promise.all([ctx.waitForEvent("page", { timeout: 15000 }), pg.locator('a[href*="/seeu/arquivo.do"]').first().click()]);
    await janela.waitForSelector("canvas", { timeout: 30000 });
    ok(/\/painel\/previa\.html#doc=/.test(janela.url()) && await janela.locator("canvas").count() >= 1, id + ": 2º monitor: o documento abre na janela da extensão (" + janela.url().slice(-40) + ")");
    await janela.close();
    await cfgDoc(false);
    await pg.bringToFront();
    await pg.locator('#apto-movs [data-rot="ocultar"]').click();
    L = await cat();
    ok(L.filter((x) => x[4] === "0").every((x) => !x[1]) && L.filter((x) => x[4] === "1").every((x) => x[1]), id + ": ocultar só o que não tem arquivo vinculado");
    await pg.locator('#apto-movs [data-cat="mp"]').click();
    L = await cat();
    ok(L.filter((x) => x[1]).every((x) => x[0] === "mp"), id + ": filtro só MP");
    await pg.locator('#apto-movs [data-limpar]').click();
    await pg.locator('#apto-movs [data-rot="esmaecer"]').click();
    await pg.goto("https://seeu.pje.jus.br/seeu/visualizacaoProcesso.do?actionType=visualizar&selectedIcon=tabMovimentacoesProcesso");
    await pg.waitForSelector("#apto-movs .ch", { timeout: 15000 });
    ok(await pg.evaluate(() => document.querySelector("#apto-movs").shadowRoot.querySelector('[data-rot="esmaecer"]').getAttribute("aria-pressed")) === "true", id + ": escolha lembrada");
  }
  // ficha disciplinar: carregar o PDF pelo botão do painel (a ficha é lida no navegador: pdf.js + o leitor do APTO)
  {
    const [id, c] = Object.entries(DADOS)[0];
    await pg.goto("https://seeu.pje.jus.br/seeu/visualizacaoProcesso.do?actionType=visualizar&numeroUnico=" + c.processo.replace(/\D/g, ""));
    const f = await moldura();
    await f.waitForSelector(".h-al", { timeout: 60000 });
    await f.setInputFiles("#arquivoFicha", c.ficha_pdf);
    await f.waitForSelector(".ficha.verde", { timeout: 60000 });
    const txt = (await f.textContent(".ficha")).replace(/\s+/g, " ");
    console.log(id, "· ficha ·", txt.slice(0, 90));
    const assin = await sw.evaluate(async (dig) => { const g = await chrome.storage.session.get("painel:" + dig); return g["painel:" + dig] && g["painel:" + dig].resultado.painel.assinatura; }, c.processo.replace(/\D/g, ""));
    ok(c.esperado_ficha.ficha === true, id + ": a ficha gerada devia ser desta pessoa");
    ok(assin === c.esperado_ficha.assinatura, id + ": com a ficha, assinatura da extensão diferente da do Python do APTO");
    ok(/carregada no painel/.test(txt), id + ": origem da ficha dita");
    ok(/^Ficha SIAPEN · /.test(txt.trim()), id + ": a ficha lida numa linha só (" + txt.trim().slice(0, 60) + ")");
    await pg.screenshot({ path: path.join(SAIDA, "painel_ficha.png") });
    await f.click('[data-acao="ficha-retirar"]');
    await f.waitForSelector(".ficha.amarelo", { timeout: 60000 });
  }
  // resumo para o assistido: abre no painel, só baixa depois de escolher onde é o atendimento; fora da unidade = sem canhoto
  {
    const [id, c] = Object.entries(DADOS)[0];
    const f = await moldura();
    await f.waitForSelector("#resumo:not([disabled])", { timeout: 60000 });
    await f.click("#resumo");
    await f.waitForSelector(".res fieldset legend", { timeout: 90000 });
    ok(await f.isDisabled("#resPdf"), id + ": sem escolher o local, o PDF não sai");
    await pg.screenshot({ path: path.join(SAIDA, "painel_resumo.png") });
    for (const [onde, canhoto] of [["fora", false], ["unidade", true]]) {
      await f.check(`input[name=resOnde][value=${onde}]`);
      await f.waitForSelector("#resPdf:not([disabled])");
      const [aba] = await Promise.all([ctx.waitForEvent("page", { timeout: 90000 }), f.click("#resPdf")]);
      await aba.waitForLoadState();
      ok(/\/painel\/imprimir\.html#/.test(aba.url()), id + ": o resumo abre na página de impressão da extensão (" + aba.url() + ")");
      await aba.waitForFunction(() => document.body.dataset.impressao, null, { timeout: 30000 });
      const pedido = await aba.evaluate(() => document.body.dataset.impressao);
      console.log(id, "· resumo", onde, "· aba de impressão aberta · impressão", pedido, "·", await aba.title());
      ok(pedido === "pedida", id + ": a impressão devia ser pedida ao abrir (" + pedido + ")");
      const b64 = await aba.evaluate(async () => { const u = document.getElementById("pdf").src; const b = new Uint8Array(await (await fetch(u)).arrayBuffer());
        let s = ""; for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode.apply(null, b.subarray(i, i + 0x8000)); return btoa(s); });
      const destino = path.join(SAIDA, `resumo_${onde}.pdf`);
      fs.writeFileSync(destino, Buffer.from(b64, "base64"));
      ok(fs.readFileSync(destino).slice(0, 5).toString() === "%PDF-", id + ": resumo (" + onde + ") não é PDF");
      ok(require("child_process").execFileSync("python3", ["-c", "import sys,pdfplumber;p=pdfplumber.open(sys.argv[1]);print('S' if 'Pedido de atendimento' in ''.join(x.extract_text() or '' for x in p.pages) else 'N')", destino]).toString().trim() === (canhoto ? "S" : "N"),
        id + ": canhoto " + (canhoto ? "devia" : "não devia") + " sair (" + onde + ")");
      await aba.close();
      await pg.bringToFront();   // a aba do SEEU volta a ser a ativa (como quando a pessoa fecha a aba de impressão)
      if (onde === "unidade") await pg.screenshot({ path: path.join(SAIDA, "painel_resumo_unidade.png") });
    }
    ok(ctx.pages().length === abasAntes, id + ": só a aba de impressão abre (e foi fechada)");
    // nada cobre o "Voltar" (o elemento no centro dele é ele mesmo); no Chromium sem tela, depois de fechar a aba de impressão,
    // o clique do mouse simulado não chega à moldura: dispara o clique no próprio botão
    ok(await f.evaluate(() => { const r = document.getElementById("resVoltar").getBoundingClientRect(); return document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2).id === "resVoltar"; }),
      id + ": o botão Voltar está coberto por outro elemento");
    await f.locator("#resVoltar").dispatchEvent("click");
    await f.waitForSelector(".h-al", { timeout: 15000 });
  }
  ok(ctx.pages().length === abasAntes, "nenhuma aba nova aberta (" + ctx.pages().length + " x " + abasAntes + ")");
  const f = await moldura();
  await f.locator("#recolher").dispatchEvent("click");   // ver o Voltar: clique direto no botão no Chromium sem tela
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
