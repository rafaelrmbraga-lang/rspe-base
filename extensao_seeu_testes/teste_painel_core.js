// Painel no SEEU (v2): montagem do HTML (painel_core.js) - duas situações (verde confere / amarelo conferir) sempre com
// ícone e texto, ordem da ficha do assistido (pena, marcos, benefícios, demais), estados sem análise e texto escapado.
const C = require("../extensao_seeu/painel/painel_core.js");
const falhas = [];
const ok = (c, m) => { if (!c) falhas.push(m); };
const it = (id, status, titulo, extra) => Object.assign({ id, status, status_txt: status === "verde" ? "Confere" : "Conferir", titulo, valor: "", motivo: "", conferir: "", conta: [], fundamento: "" }, extra || {});
const res = { estado: "ok", painel: { processo: "9900001-00.2026.8.12.0001", nome: "Fulano", hoje: "12/10/2026", ficha: false,
  pena: { total: "6 anos", cumprida: "2 anos", remanescente: "4 anos", termino: "01/01/2030", pct: 33, regime: "Fechado", aviso: "" },
  secoes: [{ id: "marcos", titulo: "Marcos", itens: [it("prog", "verde", "Progressão <script>x</script>", { valor: "02/09/2026", motivo: "atingida há 2 meses", conta: ["a & b"], fundamento: "LEP, art. 112" })] },
    { id: "beneficios", titulo: "Benefícios", itens: [it("i25", "amarelo", "Indulto 2025", { valor: "tempo atendido", conferir: "falta grave" })] }],
  crimes: [{ texto: "Furto (art. 155 do CP)", pena: "6 anos", hediondo: "" }], nao_cabe: [{ titulo: "Livramento", motivo: "Vedado" }],
  contagem: { verde: 1, amarelo: 1 } } };
const h = C.html(res);
ok(h.indexOf("Pena total") < h.indexOf("Marcos") && h.indexOf("Marcos") < h.indexOf("Benefícios") && h.indexOf("Benefícios") < h.indexOf("Crimes em execução"), "ordem da ficha do assistido");
ok(!h.includes("<script>") && h.includes("Progressão &lt;script&gt;"), "título do cálculo nunca vira HTML");
ok(h.includes("a &amp; b") && h.includes("LEP, art. 112"), "conta e fundamento");
ok(/selo-st verde"><svg[^>]*aria-hidden="true"[\s\S]*?Confere/.test(h) && /selo-st amarelo"><svg[\s\S]*?Conferir/.test(h), "situação com ícone E texto (não só cor)");
ok(!/agir já|◆|▲/i.test(h), "sem 'agir já' e sem escala de urgência");
ok(h.includes("Ficha disciplinar não lida"), "sem ficha: avisado");
ok(h.includes('aria-label="33% da pena cumprida"'), "barra da pena com texto alternativo");
ok(h.includes("1 hipótese afastada"), "não cabe recolhido, com contagem");
ok(C.html({ estado: "sem_dados" }).includes("Não foi possível ler o processo"), "sem dados: orientação");
ok(C.html({ estado: "erro", motivo: "x <y>" }).includes("x &lt;y&gt;"), "erro escapado");
const car = C.html({ estado: "carregando", primeira: true, etapa: "Lendo as abas do processo (2 de 8)" });
ok(car.includes('aria-busy="true"') && car.includes("2 de 8") && car.includes("primeira vez"), "carregando: esqueleto com aria-busy e etapa");
const t = C.resumo(res);
ok(t.includes("MARCOS") && t.includes("[confere] Progressão") && t.includes("[conferir] Indulto 2025") && t.includes("NÃO CABE"), "resumo em texto");
if (falhas.length) { console.log("FALHOU:\n  " + falhas.join("\n  ")); process.exit(1); }
console.log("ok: painel_core v2 (ordem da ficha, verde/amarelo com ícone e texto, estados, texto escapado, resumo)");
