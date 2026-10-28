// Teste do robô do SAJ em páginas salvas do painel (Ctrl+S), num Chromium sem rede.
// Uso: node teste_robo_saj.js <painel.html> <editor.html>
//  - painel.html: o Painel de Tarefas na fila "Para peticionar > Intimação"
//  - editor.html: a mesma tela com o editor de uma tarefa aberto (aba Propriedades à vista)
// As páginas salvas têm dados de processos: ficam fora do repositório.
// O teste imita o SAJ: "Continuar" abre o editor salvo; as listas de Movimentação e de certificado abrem
// com opções; Peticionar mostra a caixa verde, fecha o editor e tira a tarefa da fila.
// As listas reais do SAJ não foram salvas: aqui elas seguem o padrão do componente (react-select).
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
const dialogo = ed.slice(ed.indexOf('<div role="presentation" class="MuiDialog-root'), ed.lastIndexOf("</body>"));
const robo = fs.readFileSync(path.join(__dirname, "robo_saj.js"), "utf8");

let falhas = 0;
const confere = (nome, cond, info) => { if (cond) console.log("  ok  " + nome); else { falhas++; console.log("  FALHOU " + nome + (info !== undefined ? " -> " + JSON.stringify(info) : "")); } };

// imitação do SAJ, roda dentro da página
function simularSAJ({ dialogo, semOpcao }) {
  window.__cliques = [];
  window.__peticionados = [];
  const MOV = { "920198": ["920281-ATOS FINALÍSTICOS-", "920198 - Manifestação", "Manifestação do Autor", "9934 - Manifestação da Defensoria -  Autor"],
    "1000150": ["1000000-MOVIMENTAÇÕES DE SISTEMA", "1000150 - Petição Intermediária TJ", "PETIÇÃO", "13 - PETIÇÃO"] };
  const aviso = (txt) => {
    const s = document.createElement("div");
    s.className = "MuiSnackbar-root MuiSnackbar-anchorOriginBottomRight";
    s.innerHTML = `<div role="alert" class="MuiAlert-root">${txt}<button aria-label="Close" type="button">x</button></div>`;
    s.querySelector("button").addEventListener("click", () => s.remove());
    document.body.appendChild(s);
  };
  window.__aviso = aviso;
  aviso("Sua petição está sendo enviada ao tribunal. Aguarde confirmação."); // caixa velha de outra petição
  const numAberto = () => { const c = document.querySelector('[data-testid^="card-"][aria-selected="true"]'); return c ? c.getAttribute("data-testid").slice(5) : ""; };
  const menu = (container, prefixo, grupos, aoEscolher) => {
    container.querySelectorAll(`.${prefixo}__menu`).forEach((m) => m.remove());
    const m = document.createElement("div");
    m.className = `${prefixo}__menu`;
    for (const [pai, ops] of grupos) {
      const g = document.createElement("div");
      g.className = `${prefixo}__group`;
      g.innerHTML = `<div class="${prefixo}__group-heading">${pai}</div>`;
      for (const o of ops) {
        const d = document.createElement("div");
        d.className = `${prefixo}__option`;
        d.textContent = o;
        d.addEventListener("click", () => { aoEscolher(pai, o); m.remove(); });
        g.appendChild(d);
      }
      m.appendChild(g);
    }
    container.appendChild(m);
  };
  document.addEventListener("mousedown", (ev) => {
    const ctl = ev.target.closest && ev.target.closest('[class*="__control"]');
    if (!ctl) return;
    window.__cliques.push("abrirLista");
    const cont = ctl.parentElement;
    if (/movement-type-select__control/.test(ctl.className)) {
      const grupos = [["920281-ATOS FINALÍSTICOS-", ["920198 - Manifestação", "920199 - Manifestação genérica"]]];
      if (!semOpcao.includes(numAberto())) grupos.push(["1000000-MOVIMENTAÇÕES DE SISTEMA", ["1000150 - Petição Intermediária TJ", "1000151 - Petição Inicial TJ"]]);
      menu(cont, "movement-type-select", grupos, (pai, o) => {
        const cod = o.split(" ")[0], v = MOV[cod] || [pai, o, "", ""];
        const raiz = document.querySelector('[data-testid="propriedades-root"]');
        raiz.querySelector('[data-testid="option-parent"]').textContent = v[0];
        raiz.querySelector('[data-testid="option-label"]').textContent = v[1];
        if (MOV[cod]) {
          raiz.querySelector(".select-petition-type__single-value").textContent = v[2];
          raiz.querySelector(".select-tipo-documento__single-value").textContent = v[3];
        }
      });
    }
    if (/certificado__control/.test(ctl.className)) {
      menu(cont, "certificado", [["", ["CAHUE DUARTE E URDIALES:26255213846", "OUTRA PESSOA:111"]]], (pai, o) => {
        const vc = ctl.querySelector(".certificado__value-container");
        const ph = vc.querySelector(".certificado__placeholder");
        if (ph) ph.remove();
        let sv = vc.querySelector(".certificado__single-value");
        if (!sv) { sv = document.createElement("div"); sv.className = "certificado__single-value"; vc.prepend(sv); }
        sv.textContent = o.split(":")[0];
        const b = document.querySelector('[data-testid="action-emissao-expediente-peticionar-btn"]');
        b.disabled = false; b.removeAttribute("disabled"); b.classList.remove("Mui-disabled");
      });
    }
  }, true);
  document.addEventListener("click", (ev) => {
    const b = ev.target.closest && ev.target.closest("button, input");
    if (!b) return;
    const t = b.getAttribute("data-testid") || b.getAttribute("aria-label") || b.name;
    window.__cliques.push(t);
    if (t === "btn-atividade-generic") {
      const cont = b.closest('[data-testid="container-card"]');
      document.querySelectorAll('[data-testid^="card-"][aria-selected]').forEach((c) => c.setAttribute("aria-selected", "false"));
      cont.querySelector('[data-testid^="card-"][aria-selected]').setAttribute("aria-selected", "true");
      setTimeout(() => {
        const w = document.createElement("div");
        w.id = "dlg";
        w.innerHTML = dialogo;
        document.body.appendChild(w);
        const ifr = w.querySelector("iframe.tox-edit-area__iframe");
        ifr.removeAttribute("src");
        ifr.srcdoc = "<html><body><p>Processo nº " + numAberto() + "</p><p>Texto da peça, já pronto, com mais de cinquenta caracteres.</p></body></html>";
      }, 300);
    }
    if (t === "action-emissao-expediente-close-btn") setTimeout(() => document.getElementById("dlg").remove(), 200);
    if (t === "action-emissao-expediente-peticionar-btn") {
      const num = numAberto();
      window.__peticionados.push(num);
      window.__liminarNoEnvio = (window.__liminarNoEnvio || []).concat(document.querySelector('input[name="urgente"]').checked);
      setTimeout(() => {
        aviso("Sua petição está sendo enviada ao tribunal. Aguarde confirmação.");
        document.getElementById("dlg").remove();
        const card = [...document.querySelectorAll('[data-testid="container-card"]')].find((c) => c.querySelector('[data-testid="num-processo-label"]').textContent.trim() === num);
        setTimeout(() => card.remove(), 1500); // a tarefa sai da fila um pouco depois
      }, 1200);
    }
  }, true);
  window.__roboSAJ_teste = true;
}

async function rodada(pg, modo, n, autorizar) {
  await pg.evaluate(({ modo, n, autorizar }) => {
    const s = document.getElementById("robo-saj-host").shadowRoot;
    const sel = s.querySelector("select"); sel.value = modo; sel.dispatchEvent(new Event("change"));
    s.querySelector('input[type="number"]').value = String(n);
    if (autorizar) { const a = [...s.querySelectorAll("label")].find((l) => /Autorizo/.test(l.textContent)).querySelector("input"); a.checked = true; a.dispatchEvent(new Event("change")); }
    window.__roboSAJ.estado.resultados.length = 0;
    [...s.querySelectorAll("button")].find((b) => b.textContent === "Iniciar").click();
  }, { modo, n, autorizar });
  await pg.waitForTimeout(300);
  await pg.waitForFunction(() => !window.__roboSAJ.estado.rodando, null, { timeout: 240000 });
  return pg.evaluate(() => window.__roboSAJ.estado.resultados.map((r) => ({ ...r })));
}
const avisoRobo = (pg) => pg.evaluate(() => document.getElementById("robo-saj-host").shadowRoot.querySelector(".a").textContent);

(async () => {
  const nav = await chromium.launch();
  const pg = await nav.newPage({ viewport: { width: 1500, height: 850 } });
  pg.on("pageerror", (e) => { falhas++; console.log("  ERRO NA PÁGINA " + e.message); });
  await pg.setContent("<!doctype html><html><head><meta charset='utf-8'></head>" + painel + "</html>");
  const cards = await pg.$$eval('[data-testid="num-processo-label"]', (e) => e.map((x) => x.textContent.trim()));
  const ep = cards.filter((n) => n[0] === "5"), saj = cards.filter((n) => n[0] === "0");
  console.log(`cards: ${cards.length} (${ep.length} EPROC, ${saj.length} SAJ)`);
  const semOpcao = [ep[3]]; // nesse a lista não tem a 1000150: tem de pular, sem chutar outra
  await pg.evaluate(simularSAJ, { dialogo, semOpcao });
  await pg.addScriptTag({ content: robo });

  console.log("menu e categorias");
  confere("fila Para peticionar > Intimação reconhecida", (await pg.evaluate(() => window.__roboSAJ.filaSelecionada())).ok);
  const cat = await pg.evaluate(() => ["IMPUG - INSUMOS - GENÉRICA", "ADV PARTICULAR - DEVOLVER", "REITERAR SEQUESTRO", "CIÊNCIA"].map(window.__roboSAJ.categoria));
  confere("categorias", JSON.stringify(cat) === JSON.stringify(["Impugnação", "Adv. particular", "Cumprimento/bloqueio", "Ciência"]), cat);

  console.log("modo Conferir (4 tarefas)");
  let res = await rodada(pg, "conferir", 4);
  confere("4 conferidas", res.length === 4 && res.every((r) => r.resultado === "CONFERIDA"), res.map((r) => r.resultado));
  const rB = res.find((r) => r.perfil === "B");
  confere("EPROC: faria trocar a Movimentação para 1000150", rB && rB.feito.some((f) => /^Movimentação → 1000150/.test(f)), rB && rB.feito);
  let cl = await pg.evaluate(() => window.__cliques.splice(0));
  confere("conferir: só abre, aba Propriedades e fecha", cl.every((t) => ["btn-atividade-generic", "action-emissao-expediente-close-btn", "action-menu-propriedades"].includes(t)), [...new Set(cl)]);

  console.log("modo Peticionar sem autorização");
  await pg.evaluate(() => { const s = document.getElementById("robo-saj-host").shadowRoot; const sel = s.querySelector("select"); sel.value = "peticionar"; sel.dispatchEvent(new Event("change")); [...s.querySelectorAll("button")].find((b) => b.textContent === "Iniciar").click(); });
  await pg.waitForTimeout(300);
  confere("recusa sem marcar Autorizo", /Autorizo peticionar/.test(await avisoRobo(pg)));
  confere("nenhum clique", (await pg.evaluate(() => window.__cliques.splice(0))).length === 0);

  console.log("modo Preparar (3 tarefas)");
  res = await rodada(pg, "preparar", 3);
  confere("3 preparadas", res.length === 3 && res.every((r) => r.resultado.startsWith("PREPARADA")), res.map((r) => r.resultado));
  const prepB = res.filter((r) => r.perfil === "B");
  confere("preparar EPROC: Movimentação acertada + certificado", prepB.length > 0 && prepB.every((r) => r.feito.includes("Movimentação acertada") && r.feito.includes("certificado escolhido")), prepB.map((r) => r.feito));
  cl = await pg.evaluate(() => window.__cliques.splice(0));
  confere("preparar: nunca clica em Peticionar", !cl.includes("action-emissao-expediente-peticionar-btn"));
  cl.length = 0;

  console.log("modo Peticionar (8 tarefas)");
  res = await rodada(pg, "peticionar", 8, true);
  for (const r of res) console.log("     " + r.num + " " + r.perfil + " → " + r.resultado);
  const pet = res.filter((r) => r.resultado === "PETICIONADO");
  const sim = await pg.evaluate(() => window.__peticionados);
  confere("peticionou as que deviam", pet.length === 7, pet.length);
  confere("a sem a opção 1000150 foi pulada", res.some((r) => r.num === semOpcao[0] && /não consegui pôr a Movimentação.*não aparece/.test(r.resultado)), res.find((r) => r.num === semOpcao[0]));
  confere("um clique em Peticionar por tarefa", sim.length === pet.length && new Set(sim).size === sim.length, sim);
  confere("o que o SAJ recebeu = o que o robô diz", JSON.stringify([...sim].sort()) === JSON.stringify(pet.map((r) => r.num).sort()));
  cl = await pg.evaluate(() => window.__cliques.splice(0));
  confere("fechou as caixas verdes (a velha e as novas)", cl.filter((t) => t === "Close").length >= pet.length + 1, cl.filter((t) => t === "Close").length);
  confere("nenhum aviso sobrando na tela", await pg.evaluate(() => !document.querySelector(".MuiSnackbar-root")));
  confere("nunca mexe em Liminar/Redistribuir", !cl.some((t) => /Liminar|Redistribuir|urgente|redistribuir/.test(String(t))), cl.filter((t) => /Liminar|Redistribuir/.test(String(t))));
  confere("Liminar chegou ao envio como veio (marcada)", (await pg.evaluate(() => window.__liminarNoEnvio)).every(Boolean));
  const proib = cl.filter((t) => !["btn-atividade-generic", "action-emissao-expediente-close-btn", "action-menu-propriedades", "action-emissao-expediente-peticionar-btn", "Close", "abrirLista", undefined, null].includes(t));
  confere("só cliques permitidos", proib.length === 0, proib);

  console.log("erro do SAJ depois de Peticionar");
  await pg.evaluate(() => {
    // próxima petição: o SAJ responde com erro em vez da caixa verde
    document.addEventListener("click", (ev) => {
      const b = ev.target.closest && ev.target.closest("button");
      if (b && b.getAttribute("data-testid") === "action-emissao-expediente-peticionar-btn") {
        ev.stopImmediatePropagation();
        window.__cliques.push("peticionar-com-erro");
        setTimeout(() => window.__aviso("Erro ao enviar a petição: certificado expirado"), 800);
      }
    }, true);
  });
  res = await rodada(pg, "peticionar", 3, true);
  const parados = res.filter((r) => r.resultado.startsWith("PARADO"));
  confere("para na primeira com erro, sem seguir", parados.length === 1 && res[res.length - 1] === parados[0] && /o SAJ avisou: erro/.test(parados[0].resultado), res.map((r) => r.resultado));
  const aind = await pg.evaluate(() => window.__cliques.filter((t) => t === "peticionar-com-erro").length);
  confere("um único clique em Peticionar", aind === 1, aind);

  const rel = await pg.evaluate(() => window.__roboSAJ.relatorioTexto());
  if (process.env.COMPLETO) console.log("\n" + rel);
  await nav.close();
  console.log(falhas ? `\n${falhas} FALHA(S)` : "\ntudo certo");
  process.exit(falhas ? 1 : 0);
})();
