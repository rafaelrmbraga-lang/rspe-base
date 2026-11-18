// Teste da tela de Atendimentos dentro do APTO (ui.html + moldura atendimentos/painel.html), com dados fictícios e o Python
// imitado (window.__mockApi): as três funções (Atendimentos, Quadro, Relatório) com as suas subabas, a gravação só do que mudou,
// a pendência criada pelo texto, o relatório do dia em Word (.docx válido, com o modelo de estilos), a petição a partir de um modelo
// .docx, o link do WhatsApp pelo APTO, a produção do mês e a soma (opcional) dos pedidos da Execução.
// Rodar: node atendimentos/teste_painel.js   (precisa do Playwright; sem ele, avisa e sai sem falhar)
const fs = require("fs");
const path = require("path");
const os = require("os");
let chromium;
try { ({ chromium } = require("playwright")); } catch (e) { console.log("ok: (sem Playwright: teste da tela de Atendimentos não executado)"); process.exit(0); }
const RAIZ = path.join(__dirname, "..");
const MODELO = path.join(RAIZ, "extensao_seeu_testes", "modelo_ficticio.docx");

(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage({ viewport: { width: 1360, height: 860 } });
  const erros = [];
  pg.on("pageerror", (e) => erros.push(String(e)));
  const salvos = [];
  // o Python imitado: arquivos do painel lidos do disco; o que seria gravado fica aqui
  let semModelos = true; // 7.31.1: a primeira abertura simula a pasta dos modelos ausente
  await pg.exposeFunction("__semModelos", () => { semModelos = false; return { ok: true }; });
  await pg.exposeFunction("__lerArquivo", (c) => {
    if (c === "modelos/lista.json" && semModelos) return { erro: 'Nenhum modelo de petição (.docx) em "C:\\x". Use o botão "Escolher a pasta dos modelos".' };
    if (c === "modelos/lista.json") return { b64: Buffer.from(JSON.stringify([{ id: "m1", nome: "1. Ciência", grupo: "Fluxo", arquivo: "m1.docx", formato: "docx" }])).toString("base64") };
    if (c === "modelos/m1.docx") return { b64: fs.readFileSync(MODELO).toString("base64") };
    const p = path.join(__dirname, ...c.split("/"));
    return fs.existsSync(p) ? { b64: fs.readFileSync(p).toString("base64") } : { erro: "não encontrado" };
  });
  await pg.exposeFunction("__salvar", (nome, b64, tipo, mes) => { salvos.push({ nome, tipo, mes, bytes: Buffer.from(b64, "base64") }); return { ok: true, caminho: "C:\\teste\\" + nome }; });
  await pg.addInitScript(() => {
    const iso = new Date().toISOString().slice(0, 10);
    const dd = iso.split("-").reverse().join("/");
    window.__mud = []; window.__links = []; window.__sap = [];
    const A = [
      { id: "a1", data: iso, hora: "08:30", nome: "Fulano de Tal Ficticio", processos: ["0000001-11.2024.8.12.0001"], contato: "(67) 99999-0001 Maria (mãe)", quem: "genitora", assistida: false,
        forma: "presencial", formaManual: false, abertura: true, corpo: "", status: "presente", chegada: "08:12", origem: "sap", criadoEm: 1, rk: "101",
        fato: { data: "10/11/2026 10:00", defensor: "Defensor Ficticio", texto: "Atendimento solicitado pela genitora.", processos: ["0000001-11.2024.8.12.0001"], contato: "(67) 99999-0001", quem: "genitora", virtual: false, pedido: "saída temporária" }, fatoLido: "x" },
      { id: "a2", data: iso, hora: "09:00", nome: "Beltrana Ficticia", processos: [], contato: "(67) 98888-0002", quem: "", assistida: true, forma: "virtual", formaManual: false, abertura: true, corpo: "", status: "agendado", fato: null, origem: "sap", criadoEm: 2 },
    ];
    const L = {
      listar: () => ({ sem_base: true, recentes: [], hoje: dd, registros: [] }),
      // uma pendência antiga, sem vínculo com o atendimento (como as criadas antes ou trazidas da extensão)
      atd_tudo: () => ({ atendimentos: A, pecas: [{ id: "p0", tipo: "ST", processo: "0000001-11.2024.8.12.0001", nome: "Fulano de Tal Ficticio", data: iso, status: "pendente",
        coluna: "doc", prazo: "", obs: "", origem: "manual", atendimentoId: "", criadoEm: 0 }], ajustes: {}, modelos: null, config: {}, sap: { aberto: true, visto: 0, leitura: null } }),
      atd_mudar: (d) => { window.__mud.push(JSON.parse(JSON.stringify(d))); return { ok: true }; },
      atd_sap: (t, d) => { window.__sap.push([t, d]); return t === "lerFilaSap" ? { ok: true, lidos: 2, total: 2, erros: [] } : { ok: true }; },
      atd_arquivo: (c) => window.__lerArquivo(c),
      atd_salvar_arquivo: (n, b64, t, m) => window.__salvar(n, b64, t, m),
      atd_abrir_link: (u) => { window.__links.push(u); return { ok: true }; },
      atd_escolher_pasta: (t) => (t === "modelos" ? window.__semModelos() : { ok: true }),
      atd_pastas: () => ({ relatorio: { caminho: "" }, peticoes: { caminho: "" } }),
    };
    window.__mockApi = new Proxy(L, { get: (t, k) => t[k] || (() => ({})) });
  });
  pg.on("dialog", (d) => d.accept(d.type() === "prompt" ? d.defaultValue() || "9" : undefined));
  await pg.goto("file://" + path.join(RAIZ, "ui.html"));
  await pg.waitForTimeout(500);
  const falhas = [];
  const ok = (c, m) => { if (!c) falhas.push(m); };

  await pg.click("#fn_atend");
  await pg.waitForTimeout(1500);
  const fr = pg.frame({ url: /painel\.html/ });
  ok(fr, "moldura do painel");
  ok((await fr.$$eval(".abas button:not([hidden])", (x) => x.map((b) => b.dataset.aba))).join() === "dia,fluxo,cfg", "Atendimentos: dia, fluxo e frases");
  ok((await fr.$$eval("#lista .card", (x) => x.length)) === 2, "os dois atendimentos do dia");
  ok(/SAP aberto/.test(await fr.textContent("#sapStatus")), "situação do SAP");
  // Chamar (presente) vai para o APTO, que pede à extensão
  await fr.click('.card[data-id="a1"] .chamarBtn');
  await pg.waitForTimeout(400);
  ok((await pg.evaluate(() => window.__sap)).some(([t, d]) => t === "chamarSap" && d.rk === "101"), "Chamar pedido ao SAP pelo APTO");
  // escrever o atendimento: só o atendimento mudado é gravado; o texto sugere a pendência
  // (Chamar já abre o cartão)
  if ((await fr.getAttribute('.card[data-id="a1"] .linha', "aria-expanded")) !== "true") await fr.click('.card[data-id="a1"] .linha');
  await fr.fill('.card[data-id="a1"] .corpo', "Deseja pedir saída temporária. Solicitou-se que encaminhe a documentação necessária até 25/11.");
  await pg.waitForTimeout(900);
  const mud = await pg.evaluate(() => window.__mud);
  const ult = mud.filter((m) => m.atendimentos).pop();
  ok(ult && ult.atendimentos.upsert.length === 1 && ult.atendimentos.upsert[0].id === "a1" && ult.atendimentos.upsert[0].status === "atendido" && !ult.atendimentos.remover.length,
    "grava só o atendimento mudado (e passa a Atendido): " + JSON.stringify(ult && ult.atendimentos.upsert.map((x) => x.id)));
  ok((await fr.inputValue('.card[data-id="a1"] .pPeca')) === "ST" && (await fr.inputValue('.card[data-id="a1"] .pFila')) === "doc", "pendência sugerida: ST, aguardando documento");
  await fr.click('.card[data-id="a1"] .pAdd');
  await pg.waitForTimeout(300);
  ok((await pg.evaluate(() => window.__mud)).some((m) => m.pecas && m.pecas.upsert.some((p) => p.tipo === "ST" && p.coluna === "doc")), "pendência gravada");
  // WhatsApp pelo APTO
  await fr.click('.card[data-id="a1"] .zap summary');
  await fr.click('.card[data-id="a1"] .zapAbrir');
  await pg.waitForTimeout(300);
  ok((await pg.evaluate(() => window.__links)).some((u) => u.startsWith("https://wa.me/5567999990001?text=")), "WhatsApp aberto pelo APTO");
  // relatório do dia (Word)
  await fr.click("#relatorioBtn");
  await pg.waitForTimeout(1500);
  const rel = salvos.find((s) => s.nome.endsWith(".docx") && s.tipo === "relatorio");
  ok(rel && rel.bytes.slice(0, 2).toString() === "PK" && rel.bytes.includes(Buffer.from("word/styles.xml")) && rel.mes === new Date().getMonth(), "relatório do dia em Word, com o modelo de estilos, na pasta do mês");
  if (rel) fs.writeFileSync(path.join(os.tmpdir(), "apto_teste_relatorio.docx"), rel.bytes);
  // petição a partir do modelo
  await fr.click('.card[data-id="a1"] .gerarPet');
  await pg.waitForTimeout(800);
  // sem a pasta dos modelos: o motivo (não "Unexpected end of input") e o botão para escolher a pasta ali mesmo
  const msgSem = (await fr.textContent("#petMsg")) || "";
  ok(!(await fr.isHidden("#petMsg")) && msgSem.includes("Nenhum modelo de petição") && !/Unexpected|JSON/.test(msgSem), "sem modelos: o motivo, não erro de JSON: " + msgSem);
  const bEsc = await fr.$('#petMsg button');
  ok(bEsc, "sem modelos: botão Escolher a pasta dos modelos");
  if (bEsc) { await bEsc.click(); await pg.waitForTimeout(800); }
  const bWord = await fr.$("#petLista li button:last-child");
  ok(bWord, "lista de modelos de petição");
  if (bWord) { await bWord.click(); await pg.waitForTimeout(2000); }
  const pet = salvos.find((s) => s.tipo === "peticao");
  ok(pet && pet.bytes.slice(0, 2).toString() === "PK" && /0000001-11\.2024\.8\.12\.0001|Ciência/.test(pet.nome), "petição gerada do modelo: " + (pet && pet.nome));
  if (pet) {
    // o modelo da triagem usa {{processo}}: tem de sair preenchido (o .docx é zip; a parte do documento vai sem compressão)
    const z = pet.bytes.toString("latin1");
    ok(!z.includes("{{processo}}") && z.includes("0000001-11.2024.8.12.0001"), "marcador {{processo}} preenchido");
  }
  if (pet) fs.writeFileSync(path.join(os.tmpdir(), "apto_teste_peticao.docx"), pet.bytes);
  await fr.click("#petFechar");
  // Quadro: só as pendências
  await pg.click("#fn_quadro");
  await pg.waitForTimeout(500);
  ok((await fr.$$eval(".abas button:not([hidden])", (x) => x.map((b) => b.dataset.aba))).join() === "pend,agenda", "Quadro: Pendências e Agenda");
  ok((await fr.$$eval(".kcard", (x) => x.length)) === 2, "as pendências no Quadro (a nova e a antiga)");
  ok(!(await fr.$$eval(".kcard", (x) => x.some((k) => /(^|\s)null(\s|$)/.test(k.innerText)))), "nenhum cartão mostra null");
  const antiga = await fr.$('.kanban .c-doc .kcard .knome');
  ok(antiga, "pendência antiga (sem vínculo) acha o atendimento pelo assistido");
  // relato do atendimento que gerou a pendência: clique no nome do cartão
  await fr.click('.kanban .c-fazer .kcard .knome, .kanban .c-doc .kcard:last-child .knome');
  await pg.waitForTimeout(200);
  const relato = await fr.textContent(".kcard .krel[open]");
  ok(await fr.$eval(".kcard .krel[open]", (d) => d.open) && /Atendimento solicitado pela genitora/.test(relato) && /Deseja pedir saída temporária/.test(relato),
    "relato do atendimento no cartão (Fato Narrado e registro): " + relato.slice(0, 120));
  ok((await fr.$$eval(".kcard .knome[aria-expanded=true]", (x) => x.length)) === 1, "nome do cartão diz que abriu");
  await fr.click('.abas button[data-aba="agenda"]');
  await pg.waitForTimeout(400);
  ok(await fr.isVisible("#agCal td.hoje"), "agenda única: calendário do mês");
  await fr.click('.abas button[data-aba="pend"]');
  // Relatório: produção do mês com o atendimento do dia; somar a Execução (sem base: nada)
  await pg.click("#fn_rel");
  await pg.waitForTimeout(500);
  const dia = new Date().getDate();
  const cel = await fr.inputValue(`#controle tbody tr:nth-child(${dia}) td:nth-child(2) input`);
  ok(cel === "1", "produção do mês: 1 atendimento hoje (" + cel + ")");
  await fr.check("#somarExec");
  await pg.waitForTimeout(400);
  ok(/Nenhuma base aberta/.test(await fr.textContent("#somarExecInfo")), "somar Execução sem base aberta: avisa");
  ok(!erros.length, "erros na página: " + erros.join(" | "));
  await b.close();
  if (falhas.length) { console.log("FALHA: " + falhas.join("; ")); process.exit(1); }
  console.log("ok: tela de Atendimentos no APTO (subabas por função, Chamar pelo APTO, gravação só do que mudou, pendência pelo texto, WhatsApp, relatório do dia .docx, petição do modelo, Quadro, produção do mês)");
})().catch((e) => { console.log("FALHA: " + e); process.exit(1); });
