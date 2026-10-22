// Testes das petições da triagem: os 9 modelos da pasta extensao_seeu/modelos geram .docx preenchido e PDF (nº, nome,
// data), sem campos sobrando e sem dados de casos reais; nome do arquivo "1. Ciência 7000117". Rodar: node teste_peticao.js
"use strict";
const fs = require("fs"), path = require("path"), zlib = require("zlib");
const E = path.join(__dirname, "..", "extensao_seeu");
const PET = require(path.join(E, "peticao.js"));
const PDFLib = require(path.join(E, "pdflib", "pdf-lib.min.js"));
const fontkit = require(path.join(E, "pdflib", "fontkit.umd.min.js"));
let falhas = 0;
const ok = (c, m) => { if (!c) { falhas++; console.log("FALHA: " + m); } };
const inflar = async (b) => new Uint8Array(zlib.inflateRawSync(b));
const fonte = (n) => fs.readFileSync(path.join(E, "fontes_pdf", "carlito-latin-" + n + ".woff"));
const fontes = { r: fonte("400-normal"), b: fonte("700-normal"), i: fonte("400-italic"), bi: fonte("700-italic") };

ok(PET.nomeArquivo("1. Ciência", "6003870-64.2025.8.12.0001", "pdf") === "1. Ciência 6003870.pdf", "nome do arquivo com os 7 dígitos");
ok(PET.nomeArquivo("1. Não Opor - MP", "", "docx") === "1. Não Opor - MP.docx", "nome sem nº");
ok(PET.nomeProprio("EDGAR CENTURION CACERES") === "Edgar Centurion Caceres" && PET.nomeProprio("MARIA DA SILVA E SOUZA") === "Maria da Silva e Souza", "nome em maiúsculas -> nome próprio");
ok(PET.nomeProprio("Felipe Batista Pereira") === "Felipe Batista Pereira", "nome já escrito fica como está");
ok(PET.dataPorExtenso(new Date(2026, 9, 2)) === "2 de outubro de 2026", "data por extenso");
ok(PET.MODELOS.length === 10 && PET.MODELOS.filter((m) => m.formato === "docx").map((m) => m.id).sort().join() ===
   "extincao_punibilidade,justificativa_primeira_falta,livramento_condicional,progressao_aberto", "modelos que pedem dados saem em Word");
ok(PET.modeloSugerido({ tipo: "Ciência", texto: "Dar ciência" }) === "ciencia" && PET.modeloSugerido({ tipo: "Parecer do MP", texto: "Manifestar sobre o parecer do MP" }) === "nao_opor_mp" &&
   PET.modeloSugerido({ tipo: "Certidão", texto: "Informar o endereço atualizado do assistido" }) === "esgotamento_previo" && PET.modeloSugerido(null) === null, "sugestão do modelo");
ok(PET.modeloSugerido({ tipo: "Intimação pessoal", texto: "Requerer a intimação pessoal do sentenciado para justificar" }) === "intimacao_pessoal_justificativa", "intimação pessoal sugere o modelo de intimação pessoal");

const campos = { processo: "7000117-54.2016.8.12.0001", nome: "Fulano de Tal Exemplo", data: "22 de outubro de 2026" };
const texto = (xml) => xml.replace(/<w:p[ >]/g, "\n<w:p ").replace(/<[^>]+>/g, "");
(async () => {
  for (const m of PET.MODELOS) {
    const bytes = new Uint8Array(fs.readFileSync(path.join(E, "modelos", m.arquivo)));
    const partes = await PET.lerZip(bytes, inflar);
    const xml = new TextDecoder().decode(partes["word/document.xml"]);
    ok(/\{\{processo\}\}/.test(xml) && /\{\{data\}\}/.test(xml), m.id + ": modelo com {{processo}} e {{data}}");
    ok(!/Estevão|Gildesio|Genilson|em razão da prisão informada|realizou-se uma tentativa|Constatou-se em ev|6001281-65/.test(xml), m.id + ": sem dados de casos reais nem textos retirados");
    if (m.id === "intimacao_pessoal_justificativa") ok(texto(xml).includes("Verificou-se a ocorrência de incidentes no decorrer do cumprimento da pena pelo sentenciado. A apresentação de justificativa sobre os incidentes depende de informações") && texto(xml).includes("art. 186, do CPC"), "intimação pessoal: 1ª frase trocada, resto igual");
    ok(!/template\.main\+xml/.test(new TextDecoder().decode(partes["[Content_Types].xml"])), m.id + ": é documento, não modelo do Word (.dotx)");
    // Word preenchido
    const docx = await PET.gerarDocx(bytes, campos, inflar);
    const xd = new TextDecoder().decode((await PET.lerZip(docx, inflar))["word/document.xml"]);
    ok(xd.includes("Feito nº 7000117-54.2016.8.12.0001") && xd.includes("Campo Grande, 22 de outubro de 2026.") && !/\{\{/.test(xd), m.id + ": Word preenchido");
    if (m.formato === "docx") ok(/<w:highlight w:val="yellow"\/>/.test(xd) && /\[[^\]]+\]/.test(texto(xd)), m.id + ": trechos a completar em amarelo");
    if (/\{\{nome\}\}/.test(xml)) ok(texto(xd).includes("Fulano de Tal Exemplo, já qualificado"), m.id + ": nome do sentenciado");
    // PDF
    const pdf = await PET.gerarPdf(bytes, campos, { inflar, PDFLib, fontkit, fontes, titulo: m.nome });
    ok(pdf[0] === 0x25 && pdf[1] === 0x50 && pdf.length > 50000, m.id + ": PDF gerado (com o timbre)");
    const doc = await PDFLib.PDFDocument.load(pdf);
    ok(doc.getPageCount() >= 1 && doc.getPageCount() <= 3, m.id + ": páginas " + doc.getPageCount());
    if (m.id === "esgotamento_previo") ok(doc.getPageCount() === 2, "esgotamento: 2 páginas, como no Word");
  }
  // texto do PDF (pdftotext, se houver): campos no lugar, rodapé e assinatura
  const { execFileSync } = require("child_process");
  try {
    const tmp = path.join(require("os").tmpdir(), "apto_teste_ciencia.pdf");
    fs.writeFileSync(tmp, await PET.gerarPdf(new Uint8Array(fs.readFileSync(path.join(E, "modelos", "ciencia.docx"))), campos, { inflar, PDFLib, fontkit, fontes }));
    const t = execFileSync("pdftotext", ["-layout", tmp, "-"], { encoding: "utf-8" });
    ok(/Feito nº 7000117-54\.2016\.8\.12\.0001/.test(t) && /A Defensoria Pública manifesta ciência\./.test(t) && /Campo Grande, 22 de outubro de 2026\./.test(t) &&
       /Cahuê Duarte e Urdiales/.test(t) && /Rua Barão do Melgaço/.test(t), "texto do PDF da Ciência: " + t.replace(/\s+/g, " ").slice(0, 200));
    fs.unlinkSync(tmp);
  } catch (e) { if (e.code !== "ENOENT") throw e; }
  if (falhas) { console.log(falhas + " falha(s)"); process.exit(1); }
  console.log("ok: petições (10 modelos em Word e PDF, campos, nome do arquivo, sugestão, sem dados reais)");
})().catch((e) => { console.log("FALHA: " + (e && e.stack || e)); process.exit(1); });
