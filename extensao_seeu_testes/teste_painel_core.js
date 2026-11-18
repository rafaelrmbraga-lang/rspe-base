// Painel no SEEU: montagem do HTML (painel_core.js) - estados sem análise, escala de situação, texto sempre escapado.
const C = require("../extensao_seeu/painel/painel_core.js");
const falhas = [];
const ok = (c, m) => { if (!c) falhas.push(m); };
const res = { estado: "confere", base: "Base <teste>", painel: { processo: "9900001-00.2026.8.12.0001", nome: "Fulano", hoje: "12/10/2026",
  base_juridica: "2026-11-11a", motor: "7.32.0", ficha: false, contagem: { crit: 1, urg: 0, med: 1 },
  grupos: [{ nivel: "crit", rotulo: "Agir já", itens: [{ id: "prog", nivel: "crit", titulo: "Progressão <script>x</script>", data: "02/09/2026",
    linha: "Vencido", conferir: "comportamento", conta: ["a & b"], fundamento: "LEP, art. 112" }] },
  { nivel: "med", rotulo: "A conferir", itens: [{ id: "i25", nivel: "med", titulo: "Indulto 2025", data: "tempo ok", linha: "", conferir: "falta grave", conta: [], fundamento: "" }] }],
  nao_cabe: [{ titulo: "Livramento", motivo: "Vedado" }], prazos: [{ rotulo: "Término · SEEU", valor: "10/05/2031", sub: "" }] } };
const h = C.html(res);
ok(h.includes("Confere com o APTO") && h.includes("Base &lt;teste&gt;"), "selo de conferência com a base, escapado");
ok(!h.includes("<script>") && h.includes("Progressão &lt;script&gt;"), "título do cálculo nunca vira HTML");
ok(h.includes("a &amp; b") && h.includes("LEP, art. 112"), "conta e fundamento");
ok(h.includes("◆") && h.includes("●") && h.includes("Agir já") && h.includes("A conferir"), "forma e rótulo da escala (não só cor)");
ok(h.includes("ficha do SIAPEN não importada"), "sem ficha: avisado na fonte");
ok(h.includes("1 hipótese afastada"), "não cabe recolhido, com contagem");
ok(C.html({ estado: "diverge", painel: res.painel }).includes("Diverge do APTO"), "divergência avisada");
ok(C.html({ estado: "sem_apto" }).includes("Abra o APTO"), "sem o APTO: orientação");
ok(C.html({ estado: "fora_da_base", base: "B1" }).includes("Base aberta: B1"), "fora da base: diz qual base");
ok(C.html({ estado: "erro", motivo: "x <y>" }).includes("x &lt;y&gt;"), "erro escapado");
ok(C.html({ estado: "carregando", primeira: true }).includes("primeira vez"), "carregando o motor");
const t = C.resumo(res);
ok(t.includes("AGIR JÁ") && t.includes("a conferir: falta grave") && t.includes("NÃO CABE") && t.includes("Confere com o APTO"), "resumo em texto");
if (falhas.length) { console.log("FALHOU:\n  " + falhas.join("\n  ")); process.exit(1); }
console.log("ok: painel_core (estados, escala, texto escapado, resumo)");
