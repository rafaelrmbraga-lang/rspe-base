// Painel no SEEU (v2): montagem do HTML (painel_core.js) - duas situações (verde confere / amarelo conferir) sempre com
// ícone e texto, ordem da ficha do assistido (pena, marcos, benefícios, demais), estados sem análise e texto escapado.
const C = require("../extensao_seeu/painel/painel_core.js");
const falhas = [];
const ok = (c, m) => { if (!c) falhas.push(m); };
const it = (id, status, titulo, extra) => Object.assign({ id, status, status_txt: status === "verde" ? "Confere" : "Conferir", titulo, valor: "", motivo: "", conferir: "", conta: [], fundamento: "" }, extra || {});
const res = { estado: "ok", painel: { processo: "9900001-00.2026.8.12.0001", nome: "Fulano", hoje: "12/10/2026", ficha: false,
  pena: { total: "6a0m0d", cumprida: "2a0m0d", remanescente: "4a0m0d", termino: "01/01/2030", pct: 33, regime: "Fechado", aviso: "" },
  marcos: [{ id: "db", rotulo: "Data-base (progressão)", data: "01/01/2024", quando: "", extra: "prisão", destaque: "", alerta: false, conta: [], fundamento: "Súmula 534" },
    { id: "prog", rotulo: "Progressão <script>x</script>", data: "06/11/2026", quando: "faltam 19 dias", extra: "fração 16%", destaque: "proximo", alerta: false, conta: ["a & b"], fundamento: "LEP, art. 112" },
    { id: "liv", rotulo: "Livramento condicional", data: "01/01/2028", quando: "faltam 1 ano", extra: "", destaque: "", alerta: true, conta: [], fundamento: "" }],
  alertas: [it("i25", "amarelo", "Indulto 2025", { valor: "tempo atendido", conferir: "falta grave" })],
  confere: [it("presc", "verde", "Prescrição executória", { valor: "não aparente" })],
  crimes: [{ texto: "Furto (art. 155 do CP)", pena: "6 anos", hediondo: "" }], nao_cabe: [{ titulo: "Livramento", motivo: "Vedado" }],
  contagem: { verde: 3, amarelo: 1 } } };
const h = C.html(res);
const pos = (t) => h.indexOf(t);
ok(pos("Pena total") < pos("Data-base") && pos("Data-base") < pos("Para conferir") && pos("Para conferir") < pos(">Confere<") && pos(">Confere<") < pos("Crimes em execução"), "hierarquia: pena e marcos, para conferir, confere, crimes");
ok(/<ul class="marcos"/.test(h) && !/class="al"[^>]*>[\s\S]*Data-base/.test(h.split("Para conferir")[1] || ""), "marcos em linhas, não em cartões");
ok(/<li class="on proximo">/.test(h) && h.includes(">Próximo<"), "marco próximo em destaque, com texto");
ok(h.includes("há ponto a conferir"), "marco com dúvida: sinal com texto para leitor de tela");
ok(!h.includes("<script>") && h.includes("Progressão &lt;script&gt;"), "texto do cálculo nunca vira HTML");
ok(h.includes("a &amp; b") && h.includes("LEP, art. 112"), "conta e fundamento do marco ao abrir");
ok(/class="cnt">1</.test(h) && /class="al"/.test(h), "alertas em cartões, com contagem");
ok(!/agir já|◆|▲/i.test(h), "sem 'agir já' e sem escala de urgência");
ok(h.includes("Ficha disciplinar não lida"), "sem ficha: avisado");
ok(h.includes('aria-label="33% da pena cumprida"'), "barra da pena com texto alternativo");
ok(h.includes("1 hipótese afastada"), "não cabe recolhido, com contagem");
ok(C.html({ estado: "ok", painel: Object.assign({}, res.painel, { alertas: [] }) }).includes("Nada para conferir"), "sem alertas: dito");
ok(C.html({ estado: "sem_dados" }).includes("Não foi possível ler o processo"), "sem dados: orientação");
ok(C.html({ estado: "erro", motivo: "x <y>" }).includes("x &lt;y&gt;"), "erro escapado");
const car = C.html({ estado: "carregando", primeira: true, etapa: "Lendo as abas do processo (2 de 8)" });
ok(car.includes('aria-busy="true"') && car.includes("2 de 8") && car.includes("primeira vez"), "carregando: esqueleto com aria-busy e etapa");
// ficha disciplinar: sem ficha, botão para carregar; com ficha, a data e Trocar/Retirar; ficha velha em amarelo
ok(h.includes('data-acao="ficha-carregar"') && h.includes("Carregar a ficha (PDF)") && h.includes("Arraste o PDF"), "sem ficha: botão e arrastar");
const comFicha = (velha, carregada) => C.html({ estado: "ok", fichaCarregada: carregada ? { resumo: {}, arquivo: "f.pdf" } : null,
  painel: Object.assign({}, res.painel, { ficha: true, ficha_info: { nome: "Fulano", impressa: "10/10/2026", dias: velha ? 120 : 2, velha } }) });
const hf = comFicha(false, true);
ok(hf.includes('class="ficha verde"') && hf.includes("impressa em 10/10/2026 (há 2 dias)") && hf.includes("carregada no painel") && hf.includes('data-acao="ficha-retirar"'), "ficha carregada: data, trocar e retirar");
ok(!comFicha(false, false).includes("ficha-retirar") && comFicha(false, false).includes("aberta no SIAPEN"), "ficha do SIAPEN: sem retirar, origem dita");
ok(comFicha(true, true).includes('class="ficha amarelo"'), "ficha velha: amarelo");
const t = C.resumo(res);
ok(t.includes("MARCOS") && t.includes("[próximo]") && t.includes("PARA CONFERIR") && t.includes("Indulto 2025") && t.includes("NÃO CABE"), "resumo em texto");
if (falhas.length) { console.log("FALHOU:\n  " + falhas.join("\n  ")); process.exit(1); }
console.log("ok: painel_core v2.1 (marcos em linhas com destaque do próximo, alertas em destaque, estados, texto escapado, resumo)");
