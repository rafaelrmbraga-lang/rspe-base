// Teste da leitura do SAP para a função Atendimentos do APTO (atd_sap.js), numa imitação da tela do SAP com dados fictícios
// (sap_fila.html). O chrome.runtime é trocado por um registro: confere o que iria para o APTO (fila, Fato Narrado, andamento) e
// que os pedidos do APTO (Chamar, Ler a fila) agem na página só lendo (nunca "Salvar" nem "Cancelar").
// Rodar: node extensao_seeu_testes/teste_atd_sap.js   (precisa do Playwright; sem ele, o teste avisa e sai sem falhar)
const path = require("path");
let chromium;
try { ({ chromium } = require("playwright")); } catch (e) { console.log("ok: (sem Playwright: teste da leitura do SAP não executado)"); process.exit(0); }
const EXT = path.join(__dirname, "..", "extensao_seeu");
(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage();
  const erros = [];
  pg.on("pageerror", (e) => erros.push(String(e)));
  await pg.addInitScript(() => {
    window.__msgs = []; window.__cmds = [];
    const ouv = [];
    window.chrome = {
      storage: { local: { get: async () => ({}), set: async () => {} }, onChanged: { addListener() {} } },
      runtime: {
        getURL: (p) => p, onMessage: { addListener: (f) => ouv.push(f) },
        sendMessage: async (m) => {
          window.__msgs.push(JSON.parse(JSON.stringify(m)));
          if (m.tipo === "atdComando") return { cmd: window.__cmds.shift() || null };
          if (m.tipo === "atdFila") return { ok: true, novos: (m.itens || []).length, resumo: { total: 3, lidos: 0, presentes: 1 } };
          if (m.tipo === "atdFato") return { ok: true, resumo: { total: 3, lidos: 1, presentes: 1 } };
          return { ok: true };
        },
      },
    };
  });
  await pg.goto("file://" + path.join(__dirname, "sap_fila.html"));
  await pg.addScriptTag({ path: path.join(EXT, "atd_comum.js") });
  await pg.addScriptTag({ path: path.join(EXT, "atd_sap.js") });
  await pg.waitForTimeout(1500);
  const falhas = [];
  const ok = (c, m) => { if (!c) falhas.push(m); };
  let msgs = await pg.evaluate(() => window.__msgs);
  const fila = msgs.find((m) => m.tipo === "atdFila");
  ok(fila && fila.itens.length === 3, "a fila lida vai para o APTO: " + JSON.stringify(fila));
  if (fila) {
    const c = fila.itens.find((x) => x.rk === "103"), v = fila.itens.find((x) => x.rk === "102");
    ok(c && c.chegada === "08:41" && /PRESENTE/.test(c.statusSap) && c.forma === "presencial" && c.hora === "09:30", "presente com a chegada: " + JSON.stringify(c));
    ok(v && v.forma === "virtual" && v.nome.includes("BELTRANA"), "virtual pela letra V da fila");
  }
  ok(await pg.evaluate(() => /APTO: 3 hoje/.test(document.getElementById("apto-atd-selo").textContent)), "selo mostra o resumo do APTO");
  // pedido do APTO: Chamar
  await pg.evaluate(() => window.__cmds.push({ id: 7, tipo: "chamarSap", nome: "CICLANO FICTICIO", rk: "103" }));
  await pg.waitForTimeout(3500);
  msgs = await pg.evaluate(() => window.__msgs);
  const resp = msgs.find((m) => m.tipo === "atdResposta" && m.id === 7);
  ok(resp && resp.resposta.ok, "Chamar respondido: " + JSON.stringify(resp));
  ok((await pg.evaluate(() => window.chamados)).join() === "103", "Chamar seleciona o assistido e usa o Chamar do SAP");
  ok(msgs.some((m) => m.tipo === "atdFocar"), "a aba do SAP vem para a frente depois de chamar");
  // pedido do APTO: Ler a fila (todos os de hoje: seleciona, abre o Fato Narrado, lê e fecha pelo X)
  await pg.evaluate(() => window.__cmds.push({ id: 8, tipo: "lerFilaSap", todos: false }));
  await pg.waitForFunction(() => window.__msgs.some((m) => m.tipo === "atdResposta" && m.id === 8), null, { timeout: 60000 });
  msgs = await pg.evaluate(() => window.__msgs);
  const r8 = msgs.find((m) => m.tipo === "atdResposta" && m.id === 8);
  ok(r8.resposta.ok && r8.resposta.lidos === 3 && r8.resposta.total === 3, "Ler a fila: 3 de 3: " + JSON.stringify(r8.resposta));
  const fatos = msgs.filter((m) => m.tipo === "atdFato");
  const f1 = fatos.find((m) => m.nome === "FULANO DE TAL FICTICIO");
  ok(f1 && f1.fato && f1.fato.processos[0] === "0000001-11.2024.8.12.0001" && f1.fato.quem === "genitora" && /99999-0001/.test(f1.fato.contato), "Fato Narrado interpretado: " + JSON.stringify(f1 && f1.fato));
  const f2 = fatos.find((m) => /BELTRANA/.test(m.nome));
  ok(f2 && f2.fato && f2.fato.contato === "(67) 98888-0002" && f2.fato.virtual && f2.fato.processos.length === 2,
    "telefone sem a palavra \"telefone\" (1ª linha, via plataforma), sem confundir com os nºs de processo: " + JSON.stringify(f2 && f2.fato));
  const f3 = fatos.find((m) => m.nome === "CICLANO FICTICIO");
  ok(f3 && f3.fato === null, "sem Fato Narrado no SAP: vai como lido, vazio");
  ok(msgs.some((m) => m.tipo === "atdLeitura" && m.lendo) && msgs.filter((m) => m.tipo === "atdLeitura").pop().lendo === false, "andamento da leitura para a tela do APTO");
  ok(!(await pg.evaluate(() => window.__salvou || window.__cancelou)), "nunca Salvar nem Cancelar no SAP");
  ok(!(await pg.isVisible("#form_dialogFato\\:dialogFato")), "a janela do Fato Narrado fica fechada no fim");
  ok(!erros.length, "erros na página: " + erros.join(" | "));
  await b.close();
  if (falhas.length) { console.log("FALHA: " + falhas.join("; ")); process.exit(1); }
  console.log("ok: leitura do SAP para o APTO (fila com presente/virtual, selo, Chamar, Ler a fila com Fato Narrado, andamento; nunca Salvar/Cancelar)");
})().catch((e) => { console.log("FALHA: " + e); process.exit(1); });
