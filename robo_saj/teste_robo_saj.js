// Teste do robô do SAJ em páginas salvas do painel (Ctrl+S), num Chromium sem rede.
// Uso: node teste_robo_saj.js <painel.html> <editor.html>
//  - painel.html: o Painel de Tarefas na fila "Para peticionar > Intimação"
//  - editor.html: a mesma tela com o editor de uma tarefa aberto (aba Propriedades à vista)
// As páginas salvas têm dados de processos: ficam fora do repositório.
// O teste simula o SAJ: "Continuar" abre o editor salvo com a peça do processo, o "×" fecha.
"use strict";
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const [painelArq, editorArq] = process.argv.slice(2);
if (!painelArq || !editorArq) { console.error("uso: node teste_robo_saj.js <painel.html> <editor.html>"); process.exit(2); }

const limpar = (s) => s.slice(s.indexOf("<body"))
  .replace(/<script[\s\S]*?<\/script>/g, "")
  .replace(/<iframe(?![^>]*tox-edit-area__iframe)[\s\S]*?<\/iframe>/g, "")
  .replace(/<link[^>]*>/g, "");
const painel = limpar(fs.readFileSync(painelArq, "utf8"));
const ed = limpar(fs.readFileSync(editorArq, "utf8"));
const i = ed.indexOf('<div role="presentation" class="MuiDialog-root');
const dialogo = ed.slice(i, ed.lastIndexOf("</body>"));
const robo = fs.readFileSync(path.join(__dirname, "robo_saj.js"), "utf8");

const ASS = "<p>Campo Grande, [Data atual do sistema por extenso]</p><p>[Nome do Defensor responsável]</p><p>Defensor Público</p>";
const peca = (num, ativa, extra) =>
  `<p>EXCELENTÍSSIMO SENHOR JUIZ DO 1º JUIZADO ESPECIAL DA SAÚDE</p><p>Processo nº ${num}</p>` +
  `<p>${ativa}, já qualificada nos autos da ação movida em face do MUNICÍPIO DE CAMPO GRANDE, vem, por intermédio da Defensoria Pública, ` +
  `apresentar IMPUGNAÇÃO à contestação, nos termos do art. 5º, inciso XXXV, da Constituição Federal, pelas razões a seguir expostas. ` +
  `A pretensão encontra amparo na jurisprudência consolidada e nos documentos já juntados aos autos, que comprovam a necessidade do tratamento.</p>` +
  (extra || "") + ASS;

let falhas = 0;
const confere = (nome, cond, info) => { if (cond) console.log("  ok  " + nome); else { falhas++; console.log("  FALHOU " + nome + (info ? " -> " + JSON.stringify(info) : "")); } };

(async () => {
  const nav = await chromium.launch();
  const pg = await nav.newPage({ viewport: { width: 1500, height: 850 } });
  await pg.route("**/*", (r) => (r.request().url().startsWith("data:") ? r.continue() : r.abort()));
  await pg.setContent("<!doctype html><html><head><meta charset='utf-8'></head>" + painel + "</html>");

  const cards = await pg.$$eval('[data-testid="num-processo-label"]', (e) => e.map((x) => x.textContent.trim()));
  console.log("cards na página:", cards.length);

  // corpo de cada peça: a 1ª SAJ fica boa; as demais com um defeito cada
  await pg.evaluate(({ dialogo, cards, pecaSrc, ASS }) => {
    const peca = new Function("ASS", "return " + pecaSrc)(ASS);
    const ativaDe = (num) => {
      const c = [...document.querySelectorAll('[data-testid="container-card"]')].find((x) => x.querySelector('[data-testid="num-processo-label"]').textContent.trim() === num);
      return c.querySelector('[data-testid="wrapper-parte-ativa"]').getAttribute("aria-label").replace(/^Parte ativa:\s*/, "").replace(/\.\s*Clique para copiar\.?$/, "");
    };
    const saj = cards.filter((n) => n[0] === "0"), ep = cards.filter((n) => n[0] === "5");
    const corpos = {};
    cards.forEach((n) => (corpos[n] = peca(n, ativaDe(n))));
    window.__esperado = {};
    if (saj[1]) { corpos[saj[1]] = peca(saj[1], ativaDe(saj[1]), "<p>Ver também o processo 0800001-11.2025.8.12.0001.</p>"); window.__esperado[saj[1]] = "outro nº"; }
    if (saj[2]) { corpos[saj[2]] = peca(saj[2], ativaDe(saj[2]), "<p>Valor: R$ XXX.</p>"); window.__esperado[saj[2]] = "rascunho"; }
    if (saj[3]) { corpos[saj[3]] = peca(saj[3], ativaDe(saj[3]), "<p>Segue anexo o laudo.</p>"); window.__esperado[saj[3]] = "anexo"; }
    if (saj[4]) { corpos[saj[4]] = peca(saj[4], ativaDe(saj[4]), "<p><span style='background-color:yellow'>conferir valor</span></p>"); window.__esperado[saj[4]] = "destaque"; }
    if (saj[5]) { corpos[saj[5]] = peca(saj[5], ativaDe(saj[5]), "<p>[INSERIR DATA DA PERÍCIA]</p>"); window.__esperado[saj[5]] = "colchetes"; }
    if (saj[0]) window.__esperado[saj[0]] = "OK";
    ep.forEach((n) => (window.__esperado[n] = "propriedades do perfil A num processo B"));
    window.__corpos = corpos;
    window.__cliques = [];
    document.addEventListener("click", (ev) => {
      const b = ev.target.closest("button");
      if (!b) return;
      const t = b.getAttribute("data-testid");
      window.__cliques.push(t);
      if (t === "btn-atividade-generic") {
        const cont = b.closest('[data-testid="container-card"]');
        const num = cont.querySelector('[data-testid="num-processo-label"]').textContent.trim();
        document.querySelectorAll('[data-testid^="card-"][aria-selected]').forEach((c) => c.setAttribute("aria-selected", "false"));
        cont.querySelector('[data-testid^="card-"][aria-selected]').setAttribute("aria-selected", "true");
        setTimeout(() => {
          const w = document.createElement("div");
          w.id = "dlg";
          w.innerHTML = dialogo;
          document.body.appendChild(w);
          const ifr = w.querySelector("iframe.tox-edit-area__iframe");
          ifr.removeAttribute("src");
          ifr.srcdoc = "<html><body>" + corpos[num] + "</body></html>";
        }, 300);
      }
      if (t === "action-emissao-expediente-close-btn") setTimeout(() => document.getElementById("dlg").remove(), 200);
    }, true);
    window.__roboSAJ_teste = true;
  }, { dialogo, cards, pecaSrc: peca.toString(), ASS });

  await pg.addScriptTag({ content: robo });

  console.log("fila e menu");
  const fila = await pg.evaluate(() => window.__roboSAJ.filaSelecionada());
  confere("fila Para peticionar > Intimação reconhecida", fila.ok, fila);
  const cont = await pg.evaluate(() => window.__roboSAJ.contagens());
  confere("contagens lidas", cont.intimacao !== "?" && cont.falhas !== "?" && cont.emProcessamento !== "?", cont);
  const lc = await pg.evaluate(() => window.__roboSAJ.lerCards()[0]);
  confere("card: nome completo da parte ativa", lc.ativa && !/Clique/.test(lc.ativa), lc.ativa);
  confere("card: tarjas", lc.tarjas.length >= 2, lc.tarjas);

  console.log("categorias");
  const cat = await pg.evaluate(() => ["IMPUG - VAGA HOSPITALAR", "CIÊNCIA", "Manifestação genérica", "CONTRARRAZÕES", "EMBARGOS DE DECLARAÇÃO"].map(window.__roboSAJ.categoria));
  confere("títulos -> categorias", JSON.stringify(cat) === JSON.stringify(["Impugnação", "Ciência", "Manifestação", "Contrarrazões", "Outros"]), cat);

  console.log("rodada simulada (15 tarefas)");
  const sh = await pg.evaluateHandle(() => document.getElementById("robo-saj-host").shadowRoot);
  await pg.evaluate((s) => { s.querySelector("input").value = "15"; [...s.querySelectorAll("button")].find((b) => b.textContent === "Iniciar").click(); }, sh);
  await pg.waitForFunction(() => !window.__roboSAJ.estado.rodando && window.__roboSAJ.estado.resultados.length > 0, null, { timeout: 180000 });
  const res = await pg.evaluate(() => window.__roboSAJ.estado.resultados);
  const esp = await pg.evaluate(() => window.__esperado);
  for (const r of res) {
    const e = esp[r.num];
    const bate = e === "OK" ? r.resultado.startsWith("OK")
      : e === "outro nº" ? /outro nº/.test(r.resultado)
      : e === "rascunho" ? /rascunho/.test(r.resultado)
      : e === "anexo" ? /anexo/.test(r.resultado)
      : e === "destaque" ? /fundo colorido/.test(r.resultado)
      : e === "colchetes" ? /colchetes/.test(r.resultado)
      : /Movimentação interna|Evento|Tipo de documento/.test(r.resultado);
    confere(`${r.num} (${e})`, bate, r.resultado);
  }
  confere("tarefa OK pede desmarcar Liminar e escolher certificado", res.filter((r) => r.resultado.startsWith("OK")).every((r) => r.ajustes.includes("desmarcar Liminar") && r.ajustes.includes("escolher o certificado")));
  const cliques = await pg.evaluate(() => window.__cliques);
  const proib = cliques.filter((t) => !["btn-atividade-generic", "action-menu-propriedades", "action-emissao-expediente-close-btn"].includes(t));
  confere("só cliques permitidos", proib.length === 0, proib);
  confere("nenhum clique em Peticionar", !cliques.includes("action-emissao-expediente-peticionar-btn"));
  confere("todas as 15 conferidas", res.length === cards.length, res.length);
  if (process.env.FOTO) await pg.screenshot({ path: process.env.FOTO });
  const rel = await pg.evaluate(() => window.__roboSAJ.relatorioTexto());
  console.log("\n" + (process.env.COMPLETO ? rel : rel.split("\n").slice(-3).join("\n")));
  await nav.close();
  console.log(falhas ? `\n${falhas} FALHA(S)` : "\ntudo certo");
  process.exit(falhas ? 1 : 0);
})();
