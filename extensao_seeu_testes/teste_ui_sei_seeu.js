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
  const RAIZ = path.join(__dirname, "..");
  const salvos = [];
  // os modelos do gabinete (pasta "modelos" ao lado das bases): aqui um modelo fictício da extensão
  await pg.exposeFunction("__arq", (c) => {
    if (c === "modelos/lista.json") return { b64: Buffer.from(JSON.stringify([{ id: "m1", nome: "1. Ciência", grupo: "Fluxo", arquivo: "m1.docx", formato: "docx" }, { id: "m2", nome: "1. Não homologação do cálculo", grupo: "Fluxo", arquivo: "m1.docx", formato: "docx" }])).toString("base64") };
    if (c === "modelos/m1.docx") return { b64: fs.readFileSync(path.join(RAIZ, "extensao_seeu", "modelos", "ciencia.docx")).toString("base64") };
    const p = path.join(RAIZ, "atendimentos", ...c.split("/"));
    return fs.existsSync(p) ? { b64: fs.readFileSync(p).toString("base64") } : { erro: "não encontrado" };
  });
  await pg.exposeFunction("__salvar", (n, b64, t) => { salvos.push({ n, t, b: Buffer.from(b64, "base64") }); return { ok: true, caminho: "C:\\" + n }; });
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
      seeu_ler: (o) => { window.__chamadas.push(["lerMesa", o]); return { ok: true, iniciado: true }; },
      atd_tudo: () => ({ atendimentos: [], pecas: [], ajustes: {}, modelos: null, config: {}, sap: { aberto: false } }),
      atd_mudar: () => ({ ok: true }),
      atd_arquivo: (c) => window.__arq(c),
      atd_salvar_arquivo: (n, b64, t) => window.__salvar(n, b64, t),
      seeu_prefs_gravar: (p) => { window.__chamadas.push(["prefs", p]); return { ok: true }; },
      seeu_planilha: (ks) => { window.__chamadas.push(["planilha", ks]); return { ok: true, caminho: "C:\\x.xlsx" }; },
      seeu_estado: () => fx.triagem.leitura,
      seeu_concluir: (k, pc, dt, ob) => { window.__chamadas.push(["baixa", k, pc, dt, ob]); const it = fx.triagem.itens.find((x) => x.chave === k); if (it) { it.status = "concluido"; it.baixa = { peca: pc, pecaNome: fx.triagem.pecas[pc] || "", data: dt, obs: ob }; } return { ok: true }; },
      seeu_reabrir: (k) => { window.__chamadas.push(["reabrir", k]); return { ok: true, removidas: [] }; },
      sei_estado: () => fx.resumo.leitura,
      sei_ler: (m) => { window.__chamadas.push(["lerSei", m]); return { ok: true }; },
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
  // a moldura de Atendimentos some ao ir para outra função (o display:block do iframe vencia o [hidden])
  await pg.click("#fn_atend");
  await pg.waitForSelector("#atdFrame", { state: "visible", timeout: 10000 });
  await pg.click("#fn_sei");
  await pg.waitForTimeout(200);
  ok(!(await pg.isVisible("#atdFrame")), "Atendimentos fecha ao abrir o SEI");
  await pg.click("#fn_atend");
  await pg.waitForTimeout(200);
  ok(await pg.isVisible("#atdFrame"), "Atendimentos volta");
  // ---- SEEU ----
  await pg.click("#fn_seeu");
  await pg.waitForTimeout(200);
  ok(!(await pg.isVisible("#atdFrame")), "Atendimentos fecha ao abrir o SEEU");
  await pg.waitForTimeout(400);
  ok((await pg.$$eval("#seeuPag .fx-l", (x) => x.length)) === 2, "SEEU: duas linhas da Mesa");
  // trocar de fluxo (situação) zera a lista; voltar traz as do fluxo de novo
  await pg.selectOption("#seeuSit", "1");
  await pg.waitForTimeout(200);
  ok((await pg.$$eval("#seeuPag .fx-l", (x) => x.length)) === 0, "outro fluxo: lista zerada");
  await pg.selectOption("#seeuSit", "2");
  await pg.waitForTimeout(200);
  ok((await pg.$$eval("#seeuPag .fx-l", (x) => x.length)) === 2, "de volta ao fluxo lido: as duas linhas");
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
  ok(await pg.isVisible('#seeuPag .fx-sist.on'), "SEEU aberto (com a extensão)");
  // os controles da triagem no APTO: abas, situação, etapas 1 e 2, reler tudo; defensor, final do nº, motivo, busca, providência
  const txtBarra = await pg.textContent("#seeuPag .fx-mesa");
  ok(/Manifestação/.test(txtBarra) && /Ciência/.test(txtBarra) && /Razões\/Contrarrazões/.test(txtBarra) && /reler tudo/.test(txtBarra), "abas e reler tudo na barra");
  ok(/2 · Ler processos e decisões \(2\)/.test(txtBarra), "etapa 2 com o nº da Mesa nos filtros (2, sem filtro): " + txtBarra.replace(/\s+/g, " ").slice(0, 200));
  await pg.selectOption("#seeuSit", "2");
  await pg.click('#seeuPag .fx-mesa button:has-text("1 · Ler a Mesa")');
  await pg.waitForTimeout(200);
  let lm = (await pg.evaluate(() => window.__chamadas)).filter((c) => c[0] === "lerMesa").pop();
  ok(lm && lm[1].etapa === "1" && lm[1].situacao === "2" && lm[1].abas.join() === "5,2", "1 · Ler a Mesa com as abas e a situação: " + JSON.stringify(lm && lm[1]));
  ok(await pg.isVisible('#seeuPag .fx-tri button:has-text("Sem defensor vinculado")') && (await pg.$$eval('#seeuPag .fx-tri .fx-chip.num', (x) => x.length)) === 10, "defensor e final do nº (0 a 9)");
  await pg.click('#seeuPag .fx-tri .fx-chip:has-text("Outra Defensora")');
  await pg.click('#seeuPag .fx-cont button:has-text("em aberto")');
  await pg.waitForTimeout(200);
  ok((await pg.$$eval("#seeuPag .fx-l", (x) => x.length)) === 1 && /BELTRANA/.test(await pg.textContent("#seeuPag .fx-tab")), "filtro do defensor");
  await pg.click('#seeuPag .fx-tri .fx-chip:has-text("Todos")');
  await pg.click('#seeuPag .fx-tri .fx-chip.num:has-text("1")');
  await pg.waitForTimeout(200);
  ok((await pg.inputValue("#seeuFaixa")) === "1" && (await pg.$$eval("#seeuPag .fx-l", (x) => x.length)) === 2, "final do nº (os dois terminam em 1 no 7º dígito)");
  await pg.click('#seeuPag .fx-tri .fx-chip.num:has-text("1")');
  await pg.selectOption("#seeuProv", "urgente");
  await pg.waitForTimeout(200);
  await pg.click('#seeuPag .fx-mesa button:has-text("2 · Ler processos")');
  await pg.waitForTimeout(200);
  lm = (await pg.evaluate(() => window.__chamadas)).filter((c) => c[0] === "lerMesa").pop();
  ok(lm && lm[1].etapa === "2" && lm[1].prov === "urgente", "2 · Ler processos com os filtros: " + JSON.stringify(lm && lm[1]));
  await pg.waitForTimeout(800);
  ok((await pg.evaluate(() => window.__chamadas)).some((c) => c[0] === "prefs"), "abas, situação e filtros ficam guardados");
  await pg.click('#seeuPag .fx-tri button:has-text("Planilha")');
  await pg.waitForTimeout(200);
  ok((await pg.evaluate(() => window.__chamadas)).some((c) => c[0] === "planilha" && c[1].length === 1), "planilha da lista filtrada");
  const antesDet = await pg.$$eval("#seeuPag .fx-det", (x) => x.length);
  await pg.click('#seeuPag .fx-tri button:has-text("Abrir/fechar")');
  await pg.waitForTimeout(200);
  const depoisDet = await pg.$$eval("#seeuPag .fx-det", (x) => x.length);
  if (!depoisDet) { await pg.click('#seeuPag .fx-tri button:has-text("Abrir/fechar")'); await pg.waitForTimeout(200); }
  ok(antesDet !== depoisDet && await pg.isVisible("#seeuPag .fx-det"), "abrir/fechar detalhes");
  if (SHOTS) await pg.screenshot({ path: path.join(SHOTS, "seeu.png") });
  if (!(await pg.isVisible("#seeuPag .fx-det"))) { await pg.focus("#seeuPag .fx-l"); await pg.keyboard.press("Enter"); await pg.waitForTimeout(200); }
  await pg.selectOption("#seeuProv", "");
  await pg.click('#seeuPag .fx-det button:has-text("Enviar ao Quadro")');
  await pg.waitForTimeout(200);
  ok((await pg.evaluate(() => window.__chamadas)).some((c) => c[0] === "quadroSeeu" && c[1] === "7000117-54.2016.8.12.0001"), "providência vai ao Quadro");
  await pg.click('#seeuPag .fx-det button:has-text("Abrir no SEEU")');
  ok((await pg.evaluate(() => window.__chamadas)).some((c) => c[0] === "abrir"), "abre o processo no SEEU pelo navegador");
  // petição: o MESMO diálogo dos Atendimentos (modelos do gabinete), por cima do SEEU, já com nome e processo
  await pg.click('#seeuPag .fx-det button:has-text("Gerar petição")');
  await pg.waitForSelector("#atdPetFrame:not([hidden])", { timeout: 10000 });
  const pf = pg.frame({ url: /painel\.html#pet/ });
  ok(pf, "moldura da petição");
  await pf.waitForSelector("#petFundo:not([hidden]) #petLista li", { timeout: 10000 });
  ok((await pf.inputValue("#petProc")) === "7000117-54.2016.8.12.0001" && /Fulano/i.test(await pf.inputValue("#petNome")), "processo e assistido da intimação");
  ok(/homologação/.test(await pf.textContent("#petLista li:first-child")), "modelo da peça sugerida no topo: " + (await pf.textContent("#petLista li:first-child")));
  ok(!(await pf.isVisible(".topo")) && !(await pf.isVisible("main .aba:not([hidden])")), "só o diálogo, sem as abas do painel");
  await pf.click('#petLista li:has-text("Ciência") button:has-text("Word")');
  await pf.waitForFunction(() => /Salvo|Não foi possível/.test(document.getElementById("petMsg").textContent), null, { timeout: 30000 });
  const docx = salvos.find((x) => x.n.endsWith(".docx"));
  ok(docx && docx.t === "peticao" && docx.b.slice(0, 2).toString() === "PK" && docx.b.toString("latin1").includes("7000117"), "petição em Word, com o processo, na pasta das petições: " + (docx ? docx.n : await pf.textContent("#petMsg")));
  await pf.click("#petFechar");
  await pg.waitForTimeout(300);
  ok(!(await pg.isVisible("#atdPetFrame")), "fechar devolve a tela do SEEU");
  // baixa: peça sugerida pela providência ("Impugnar o cálculo" -> Manifestações), data de hoje; conclui e sai da lista em aberto
  ok((await pg.inputValue("#seeuPag .fx-baixa select")) === "MANIF", "peça sugerida para a baixa");
  await pg.click('#seeuPag .fx-baixa button:has-text("Registrar baixa")');
  await pg.waitForTimeout(400);
  const bx = (await pg.evaluate(() => window.__chamadas)).find((c) => c[0] === "baixa");
  ok(bx && bx[2] === "MANIF" && /^\d{4}-\d{2}-\d{2}$/.test(bx[3]), "baixa registrada com peça e data: " + JSON.stringify(bx));
  await pg.click('#seeuPag .fx-cont button:has-text("concluídas")');
  await pg.waitForTimeout(200);
  ok(/baixa: Manifestações/.test(await pg.textContent("#seeuPag .fx-tab")), "concluída mostra a baixa (fica no APTO, pode reabrir)");
  // ---- SEI ----
  await pg.click("#fn_sei");
  await pg.waitForTimeout(400);
  ok((await pg.$$eval("#seiPag .fx-proc", (x) => x.length)) === 2, "SEI: dois processos");
  ok(/Leitura concluída: 2 processo/.test(await pg.textContent("#seiPag .fx-andamento")), "andamento da leitura do SEI no APTO");
  await pg.selectOption("#seiModo", "novos");
  await pg.click('#seiPag .fx-ler button:has-text("Ler o SEI")');
  await pg.waitForTimeout(200);
  ok((await pg.evaluate(() => window.__chamadas)).some((c) => c[0] === "lerSei" && c[1] === "novos"), "botão Ler o SEI dentro do APTO, com o modo");
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
