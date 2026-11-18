// Telas da gestão do NUSPEN (ver teste_ui_nuspen.py: o Python de verdade responde em argv[2]). Sem Playwright, avisa e sai.
const path = require("path");
let chromium;
try { ({ chromium } = require("playwright")); } catch (e) { console.log("ok: (sem Playwright: telas da gestão do NUSPEN não testadas)"); process.exit(0); }
const URL_PY = process.argv[2];
const SHOTS = process.env.APTO_CAPTURAS || "";
(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage({ viewport: process.env.APTO_TELA === "notebook" ? { width: 1366, height: 768 } : { width: 1400, height: 900 } });
  const erros = [];
  pg.on("pageerror", (e) => erros.push(String(e)));
  await pg.addInitScript((u) => {
    const py = (m, a) => fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ m, a }) }).then((r) => r.json());
    const L = {
      listar: () => ({ sem_base: true, recentes: [], registros: [] }),
      nus: (m, a) => py("nus", [m, a]),
      sei_resumo: () => py("sei_resumo", []),
      sei_processo: (n) => py("sei_processo", [n]),
      sei_estado: () => py("sei_estado", []),
      sei_importar_pdf: (q) => py("sei_importar_pdf", [q]),
    };
    window.__mockApi = new Proxy(L, { get: (t, k) => t[k] || (() => ({})) });
    try { localStorage.removeItem("apto_quem"); } catch (e) { /* */ }
  }, URL_PY);
  await pg.goto("file://" + path.join(__dirname, "..", "ui.html"));
  await pg.waitForTimeout(400);
  const falhas = [];
  const ok = (c, m) => { if (!c) falhas.push(m); };
  const aba = async (nome) => {
    if (nome === "Cadastros") await pg.click('#nusCabW button:has-text("Cadastros")');
    else if (nome === "Prazos" || nome === "Comunicações") { await pg.click('#seiPag .fx-vistas button:has-text("Providências")'); await pg.waitForTimeout(400);
      await pg.click(`#nusVista .nus-sub button:has-text("${nome === "Prazos" ? "Prazos e calendário" : "Ofícios"}")`); }
    else await pg.click(`#seiPag .fx-vistas button:has-text("${nome}")`);
    await pg.waitForTimeout(500);
    if (SHOTS) await pg.screenshot({ path: path.join(SHOTS, "aba_" + nome.replace(/\W+/g, "_") + "_" + (++nFoto) + ".png") }); };
  let nFoto = 0;
  const form = async (campos, botao) => {
    await pg.waitForSelector("#modal.on form", { timeout: 5000 });
    for (const [k, v] of Object.entries(campos)) {
      const el = await pg.$(`#modal [name="${k}"]`);
      const tag = await el.evaluate((x) => x.tagName);
      if (tag === "SELECT") await el.selectOption(String(v)); else await el.fill(String(v));
    }
    await pg.click(`#modal button[type=submit]${botao ? `:has-text("${botao}")` : ""}`);
    await pg.waitForTimeout(600);
  };
  await pg.click("#fn_sei");
  await pg.waitForTimeout(500);
  ok((await pg.$$eval("#seiPag .fx-vistas button", (x) => x.map((b) => b.textContent))).join("|") === "Visão geral|Processos|Providências|Demandas|Inspeções|Histórico e relatório",
    "seis abas na função SEI (prazos e ofícios dentro de Providências; Cadastros num botão)");
  ok((await pg.textContent("#seiPag h1")) === "SEI", "o nome é só SEI");
  // abas pelo teclado (setas): só a ativa entra no Tab
  await pg.focus('#seiPag .fx-vistas button[aria-selected="true"]');
  await pg.keyboard.press("ArrowRight");
  await pg.waitForTimeout(400);
  ok((await pg.evaluate(() => document.activeElement && document.activeElement.textContent)) === "Processos" &&
     (await pg.getAttribute('#seiPag .fx-vistas button:has-text("Processos")', "aria-selected")) === "true", "seta → leva à próxima aba, com o foco nela");
  ok((await pg.$$eval('#seiPag .fx-vistas button[tabindex="0"]', (x) => x.length)) === 1, "só a aba ativa na ordem do Tab");
  await pg.keyboard.press("ArrowLeft");
  await pg.waitForTimeout(400);
  // Cadastros: Quem
  await aba("Cadastros");
  await pg.fill("#ql", "Servidora Fictícia\nCoordenador Fictício");
  await pg.click('#nusVista button:has-text("Gravar a lista")');
  await pg.waitForTimeout(500);
  // sem Quem não registra
  await aba("Providências");
  await pg.click('#nusVista .nus-sub button:has-text("Lista")');
  await pg.waitForTimeout(300);
  await pg.click('#nusVista button:has-text("Registrar providência")');
  await form({ descricao: "Cobrar o fornecimento de água (fictício)", processo: "99/000123/2026" });
  ok(/Escolha quem/.test(await pg.textContent("#nfMsg")), "sem Quem, a janela pede quem registra");
  await pg.click('#modal button:has-text("Cancelar")');
  await pg.selectOption("#nusQuem", "Servidora Fictícia");
  await pg.click('#nusVista button:has-text("Registrar providência")');
  await form({ descricao: "Cobrar o fornecimento de água (fictício)", processo: "99/000123/2026", destinatario: "Direção do Presídio Fictício", fonte: "visita fictícia" });
  ok((await pg.$$eval("#nusVista .fx-proc", (x) => x.length)) === 1, "providência registrada aparece na lista");
  ok(/Aguardando início/.test(await pg.textContent("#nusDet")), "providência aberta: Aguardando início");
  // prazo expresso com data no documento, validado
  await pg.click('#nusDet button:has-text("Registrar prazo")');
  const amanha = new Date(Date.now() + 2 * 864e5).toLocaleDateString("pt-BR");
  await form({ natureza: "expresso", quantidade: "10", vencimento: amanha, fonte: "ofício fictício: responder até a data" });
  await pg.click('#nusDet button:has-text("Validar prazo")');
  await pg.waitForTimeout(600);
  ok(/Vence em .*faltam 2 dias/.test(await pg.textContent("#nusDet")), "prazo validado com vencimento do documento: " + (await pg.textContent("#nusDet .fx-lista li")).slice(0, 120));
  // ofício: registrar, enviar, resposta
  await pg.click('#nusDet button:has-text("Registrar ofício")');
  await form({ assunto: "Ofício fictício sobre a água" });
  ok(/Aguardando envio/.test(await pg.textContent("#nusDet")), "ofício registrado: aguardando envio");
  await pg.click('#nusDet button:has-text("Registrar envio")');
  await form({});
  ok(/Aguardando resposta/.test(await pg.textContent("#nusDet")), "enviado: aguardando resposta");
  await pg.click('#nusDet button:has-text("Resposta recebida")');
  await form({ o: "resposta parcial (fictícia)" });
  ok(/Resposta recebida/.test(await pg.textContent("#nusDet .fx-tag")) || /Resposta recebida/.test(await pg.textContent("#nusDet")), "resposta recebida");
  ok(/Cumprimento: Não avaliada/.test(await pg.textContent("#nusDet")), "resposta não é cumprimento");
  // cumprimento avaliado e validado
  await pg.click('#nusDet button:has-text("Avaliar o cumprimento")');
  await form({ res: "parcial", fonte: "vistoria fictícia" });
  await pg.click('#nusDet .nus-item button:has-text("Validar")');
  await pg.waitForTimeout(600);
  ok(/Cumprida parcialmente/.test(await pg.textContent("#nusDet")) && /Cumprimento: Parcialmente cumprida/.test(await pg.textContent("#nusDet")), "avaliação validada muda o cumprimento");
  // minuta
  await pg.click('#nusDet button:has-text("Gerar minuta")');
  await form({ m: "despacho-v1" });
  await pg.waitForSelector("#modal.on textarea", { timeout: 5000 });
  const nFr = await pg.$$eval("#modal textarea", (x) => x.length);
  ok(nFr >= 5 && /Fonte:/.test(await pg.textContent("#modal")), "minuta com frases e fontes: " + nFr);
  await pg.fill("#modal textarea >> nth=1", "");
  await pg.click('#modal button:has-text("Salvar como nova versão")');
  await pg.waitForTimeout(700);
  ok(/versão 2/.test(await pg.textContent("#modal h2")) && (await pg.$$eval("#modal textarea", (x) => x.length)) === nFr - 1, "nova versão sem a frase apagada");
  if (SHOTS) await pg.screenshot({ path: path.join(SHOTS, "nus_minuta.png") });
  await pg.click('#modal button[aria-label="Fechar"]');
  if (SHOTS) await pg.screenshot({ path: path.join(SHOTS, "nus_prov.png"), fullPage: true });
  // demanda com a providência
  await aba("Demandas");
  await pg.click('#nusVista button:has-text("Nova demanda")');
  await form({ assunto: "Água no Presídio Fictício", processos: "99/000123/2026\n99/000999/2026" });
  ok(/99\/000999\/2026/.test(await pg.textContent("#nusVista")), "demanda com dois processos");
  await pg.click('#nusVista button:has-text("Vincular providência")');
  await form({});
  ok(/Cobrar o fornecimento/.test(await pg.textContent("#nusVista .fx-detp")), "providência vinculada à demanda");
  // inspeção, achado, providência
  await aba("Inspeções");
  await pg.click('#nusVista button:has-text("Nova inspeção")');
  await form({ estabelecimento: "Presídio Fictício", data: new Date().toLocaleDateString("pt-BR") });
  await pg.click('#nusVista button:has-text("Registrar achado")');
  await form({ descricao: "Falta de colchões (fictício)", gravidade: "alta", recomendacao: "Fornecer colchões" });
  ok(/Falta de colchões/.test(await pg.textContent("#nusVista")) && /gravidade Alta/.test(await pg.textContent("#nusVista")), "achado registrado");
  await pg.click('#nusVista button:has-text("Gerar providência da recomendação")');
  await pg.waitForTimeout(800);
  ok(/Fornecer colchões/.test(await pg.textContent("#nusDet h2")), "a recomendação vira providência e abre");
  // prazos e visão geral
  await aba("Prazos");
  ok(/faltam 2 dias/.test(await pg.textContent("#nusVista table.fx-tabsei")), "painel de prazos");
  await aba("Visão geral");
  await pg.waitForTimeout(500);
  ok(/Vencem em até 7 dias/.test(await pg.textContent("#seiPag")) && (await pg.$$eval("#seiPag .fx-at", (x) => x.length)) === 1, "Visão geral única: um Atenção hoje só");
  const ordem = await pg.$$eval("#atHoje .fx-atc", (x) => x.map((b) => [Number(getComputedStyle(b).order), b.querySelector("span").textContent]).sort((p, q) => p[0] - q[0]).map((p) => p[1]));
  ok(ordem[0] === "Prazos vencidos" && ordem[1] === "Vencem em até 7 dias", "Atenção hoje começa pelos prazos: " + ordem.slice(0, 3));
  ok((await pg.$$eval("#atHoje .fx-atc.zero", (x) => x.length)) >= 1, "contador zerado fica discreto");
  // histórico e relatório
  await aba("Histórico e relatório");
  const h = await pg.textContent("#nusVista");
  ok(/Servidora Fictícia/.test(h) && /Providências validadas: 2/.test(h) && /Inspeções: 1/.test(h), "histórico com Quem e relatório de gestão");
  // busca
  await pg.fill("#nusBusca", "colchoes");
  await pg.click('#nusCabW button:has-text("Buscar")');
  await pg.waitForTimeout(600);
  ok(/Providência/.test(await pg.textContent("#modal")) && /Achado/.test(await pg.textContent("#modal")), "busca sem acento");
  if (SHOTS) await pg.screenshot({ path: path.join(SHOTS, "nus_busca.png") });
  await pg.keyboard.press("Escape");
  // calendário dos prazos
  await aba("Prazos");
  ok((await pg.$$eval("#nusVista .nus-cal .nus-calp", (x) => x.length)) >= 1, "calendário com o prazo validado");
  // importar o PDF do processo (fictício do NUSPEN) pelo menu Importar único
  await pg.click("#btnImp");
  await pg.click('#mImp button:has-text("PDF de processo do SEI")');
  await pg.waitForSelector("#modal.on", { timeout: 15000 });
  ok(/18 página\(s\), 16 documento\(s\)/.test(await pg.textContent("#modal")) && /sem o rodapé/.test(await pg.textContent("#modal")), "PDF importado, com aviso: " + (await pg.textContent("#modal")).slice(0, 200));
  await pg.keyboard.press("Escape");
  await aba("Visão geral");
  await pg.waitForTimeout(800);
  const vg = await pg.textContent("#nusGeral2");
  ok(/O que mudou nas leituras/.test(vg) && /Resposta recebida/.test(vg) && /Desde a sua última visita/.test(vg), "o que mudou e novidades na Visão geral");
  await pg.click('#nusGeral2 button:has-text("aguardam decisão do coordenador")');
  await pg.waitForSelector("#modal.on", { timeout: 5000 });
  ok(/Sem evidência suficiente|·/.test(await pg.textContent("#modal")), "pergunta pronta responde");
  await pg.keyboard.press("Escape");
  await pg.click('#nusGeral2 button:has-text("Marcar como visto")');
  await pg.waitForTimeout(700);
  ok(/Nada novo/.test(await pg.textContent("#nusGeral2")), "marcar como visto zera o que mudou");
  // lote: marcar as sugestões do PDF e validar com prévia
  await aba("Providências");
  await pg.click('#nusVista .fx-cont button:has-text("Identificada")');
  await pg.waitForTimeout(500);
  const nSug = await pg.$$eval("#nusVista .nus-sel", (x) => x.length);
  for (const c of await pg.$$("#nusVista .nus-sel")) await c.check();
  await pg.click('#nusVista button:has-text("Validar"):not(.pri)');
  await pg.waitForSelector("#modal.on", { timeout: 5000 });
  ok(/Prévia/.test(await pg.textContent("#modal")) && (await pg.$$eval("#modal .nus-alt li", (x) => x.length)) === nSug, "prévia do lote");
  await pg.click('#modal button[type=submit]');
  await pg.waitForTimeout(1200);
  ok(nSug >= 5 && !(await pg.$('#nusVista .fx-cont button:has-text("Identificada")')), "lote validou as " + nSug + " sugestões do PDF");
  if (SHOTS) await pg.screenshot({ path: path.join(SHOTS, "nus_lote.png"), fullPage: true });
  if (erros.length) falhas.push("erros na página: " + erros.join(" | "));
  await b.close();
  if (falhas.length) { console.log("FALHA: " + falhas.join("; ")); process.exit(1); }
  console.log("ok: telas da gestão do NUSPEN (Quem, providência, prazo, ofício, resposta ≠ cumprimento, minuta com versões, demanda, inspeção, prazos, visão geral, histórico, relatório, busca), com o Python de verdade");
})();
