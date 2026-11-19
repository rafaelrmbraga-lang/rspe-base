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
ok(!h.includes("Pena total") && !h.includes('class="barra"') && pos("Para conferir") < pos(">Confere<") && pos(">Confere<") < pos("Crimes em execução"), "sem a pena no painel (está no SEEU); para conferir, confere, crimes");
ok(!/<ul class="marcos"/.test(h) && !h.includes("Data-base (progressão)") && !h.includes("regime fechado"), "marcos e regime fora do painel lateral (estão nos chips da página)");
// chips: regime e marcos numa faixa; próximo/atingida com ícone e texto; detalhe no clique; nº e nome com copiar na barra fixa
const ch = C.chips(C.dadosChips(res), false), chf = C.chips(C.dadosChips(res), true);
ok(ch.includes(">Regime<") && ch.includes(">Fechado<") && ch.includes(">Data-base<") && ch.includes("01/01/2024"), "chips: regime e data-base");
ok(/class="sg proximo"[\s\S]*?<span class="est proximo"><svg[\s\S]*?<\/svg><span class="vh">a menos de 60 dias<\/span><\/span>/.test(ch), "chip próximo: só o ícone à vista (o texto para o leitor de tela)");
const venc = C.chips(C.dadosChips({ painel: Object.assign({}, res.painel, { marcos: [{ id: "prog", rotulo: "Progressão ao aberto", data: "01/01/2026", destaque: "atingida" }] }) }), false);
ok(/class="sg vencida"[\s\S]*?<span class="est vencida"><svg[\s\S]*?<span class="vh">vencida<\/span>/.test(venc), "progressão vencida: vermelho, com ícone e texto para o leitor de tela");
// ícones dos benefícios: cada um abre o seu cartão no painel; estado no nome acessível; indulto e comutação com ícone próprio
const ic = C.chips(C.dadosChips({ painel: Object.assign({}, res.painel, { icones: [{ tipo: "st", rotulo: "Saída temporária", estado: "conferir", alvo: "st" },
  { tipo: "ind", rotulo: "Indulto 2025", estado: "ok", alvo: "i25" }, { tipo: "com", rotulo: "Comutação 2025", estado: "conferir", alvo: "c25" }] }) }), false);
ok(/class="ben q" data-focar="st" aria-label="Saída temporária: a conferir\. Ver no painel"><svg/.test(ic), "chip da saída temporária: ícone, a conferir, abre o cartão");
ok(/class="ben ok" data-focar="i25"[^>]*aria-label="Indulto 2025: cabe/.test(ic) && /data-focar="c25"/.test(ic), "chips de indulto e comutação");
ok(C.html(res).includes('data-id="i25"'), "cartão com o id para o chip levar até ele");
// copiar fundamento: texto corrido para a petição, sem as marcas do painel, com a base legal no fim
const fp = C.fundamento({ titulo: "T", conta: ["1) O que houve: a pena diminuiu. O que pedir: o recálculo da progressão"], fundamento: "LEP, art. 112." });
ok(fp === "A pena diminuiu. Requer-se o recálculo da progressão.\n\nFundamento: LEP, art. 112.", "fundamento pronto para a petição (" + JSON.stringify(fp) + ")");
ok((ch.match(/data-chip=/g) || []).length === (ch.match(/data-det=/g) || []).length && /aria-expanded="false"/.test(ch), "cada chip abre o seu detalhe (botão, sem depender do mouse)");
ok(chf.includes('data-copiar="processo"') && chf.includes('data-copiar="nome"') && chf.includes(res.painel.processo) && chf.includes(res.painel.nome), "barra fixa: nº e nome, com copiar");
ok(/data-abrir="1"[^>]*>[\s\S]*?conferir<\/button>/.test(ch) === !!res.painel.contagem.amarelo, "chip do que falta conferir abre o painel");
ok(!C.chips(C.dadosChips({ painel: Object.assign({}, res.painel, { nome: "<b>x</b>" }) }), true).includes("<b>x</b>"), "chips: texto escapado");
const chm = C.chips(C.dadosChips(res), false);
ok(chm.includes("com ponto a conferir"), "marco com dúvida: sinal com texto para leitor de tela (chip)");
ok(!chm.includes("<script>") && chm.includes("Progressão &lt;script&gt;"), "texto do cálculo nunca vira HTML (chips)");
ok(chm.includes("a &amp; b") && chm.includes("fração 16%"), "conta do marco no detalhe do chip");
ok(/class="cnt">1</.test(h) && /class="al"/.test(h), "alertas em cartões, com contagem");
ok(!/agir já|◆|▲/i.test(h), "sem 'agir já' e sem escala de urgência");
ok(h.includes("Ficha disciplinar não lida"), "sem ficha: avisado");
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
ok(hf.includes('class="ficha curta verde"') && hf.includes("Ficha SIAPEN · 10/10/2026 (há 2 dias)") && hf.includes("carregada no painel") && hf.includes('data-acao="ficha-retirar"'), "ficha carregada: data, trocar e retirar");
ok(!comFicha(false, false).includes("ficha-retirar") && comFicha(false, false).includes("aberta no SIAPEN"), "ficha do SIAPEN: sem retirar, origem dita");
ok(comFicha(true, true).includes('class="ficha curta amarelo"'), "ficha velha: amarelo");
// cada alerta copia o seu fundamento; aviso de cadastro sem efeito fica recolhido
const hc = C.html(res);
ok((hc.match(/data-acao="copiar-fund"/g) || []).length === (res.painel.alertas || []).length, "um Copiar fundamento por alerta");
const a0 = res.painel.alertas[0];
ok(!a0.fundamento || C.fundamento(a0).includes("Fundamento: " + a0.fundamento.replace(/\.$/, "")), "texto do fundamento com a base legal");
const hd = C.html({ estado: "ok", painel: Object.assign({}, res.painel, { observacoes: [{ titulo: "Pena na ficha (x) difere da pena total do RSPE (y)", conta: [] }] }) });
ok(hd.includes("sem efeito para o assistido: 1"), "observações de cadastro recolhidas");
const t = C.resumo(res);
ok(t.includes("MARCOS") && t.includes("[próximo]") && t.includes("PARA CONFERIR") && t.includes("Indulto 2025") && t.includes("NÃO CABE"), "resumo em texto");
if (falhas.length) { console.log("FALHOU:\n  " + falhas.join("\n  ")); process.exit(1); }
console.log("ok: painel_core v2.2 (marcos nos chips da página com destaque do próximo, nº e nome com copiar, alertas em destaque, estados, texto escapado, resumo)");
