// Resumo para o assistido no painel (painel_resumo.js): a pergunta "onde é o atendimento" (na unidade = com o canhoto; fora =
// sem), a conferência frase a frase, as providências e a saída para o gerador do APTO (como a janela do APTO).
const R = require("../extensao_seeu/painel/painel_resumo.js");
const falhas = [];
const ok = (c, m) => { if (!c) falhas.push(m); };
const base = () => ({ nome: "Fulano <b>", onde: "", unidade: "Penitenciária X", data_atend: "19/11/2026", barra: { pct: 46 },
  secoes: [{ id: "pena", titulo: "Sua pena hoje", itens: [] },
    { id: "direitos", titulo: "Seus próximos benefícios", itens: ["Semiaberto: já tem o tempo.", "Livramento condicional: dia 01/01/2028.", "Indulto 2025: possível."] },
    { id: "prov", titulo: "O que a Defensoria vai fazer", itens: [] }],
  providencias: [{ id: "ped_prog", rot: "Pedir a progressão", frase: "Vamos pedir a progressão ao juiz.", marcado: false },
    { id: "ofi_atest", rot: "Ofício: atestados", frase: "Vamos pedir os atestados.", marcado: false }], outro: "", verso: { itens: [] } });
let d = base();
let h = R.tela(d);
ok(h.includes("Onde é este atendimento?") && h.includes('value="unidade"') && h.includes('value="fora"'), "pergunta do local do atendimento");
ok(!/name="resOnde" value="(unidade|fora)" checked/.test(h), "nenhuma opção marcada de saída: a pessoa escolhe");
ok(!h.includes('id="resUn"'), "sem escolha: sem os campos do canhoto");
d.onde = "unidade";
h = R.tela(d);
ok(h.includes('id="resUn"') && h.includes("Penitenciária X") && h.includes('id="resData"'), "na unidade: data e unidade do canhoto");
d.onde = "fora";
ok(!R.tela(d).includes('id="resUn"'), "fora da unidade: sem os campos do canhoto");
ok(!h.includes("<b>\"") && R.tela(Object.assign(base(), { secoes: [{ id: "x", titulo: "<script>", itens: ["<img>"] }] })).includes("&lt;script&gt;"), "texto escapado");
// providência marcada tira a frase do mesmo benefício
d = R.prov(base(), "ped_prog", true);
ok(d.secoes[1]._off[0] === true && !d.secoes[1]._off[1], "pedir a progressão: a frase do semiaberto sai, a do livramento fica");
// saída para o gerador: só as frases marcadas; providências marcadas e "outro" viram frases com ponto final
d = base();
d.secoes[1]._off = { 2: true };
d.providencias[1].marcado = true;
d.outro = "vamos visitar a unidade\n";
d.onde = "fora";
const s = R.saida(d);
ok(s.secoes[1].itens.length === 2 && !s.secoes[1].itens.some((x) => /Indulto/.test(x)), "frase desmarcada não vai para o PDF");
ok(JSON.stringify(s.secoes[2].itens) === JSON.stringify(["Vamos pedir os atestados.", "Vamos visitar a unidade."]), "providências em frases: " + JSON.stringify(s.secoes[2].itens));
ok(!("onde" in s), "a escolha do local não vai para o gerador (vira o canhoto sim/não)");
if (falhas.length) { console.log("FALHOU:\n  " + falhas.join("\n  ")); process.exit(1); }
console.log("ok: resumo para o assistido no painel (local do atendimento e canhoto, conferência, providências, saída)");
