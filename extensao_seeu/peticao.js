// APTO - Petições da triagem: abre um modelo .docx da pasta "modelos", preenche os campos ({{processo}}, {{nome}},
// {{data}}) e entrega o .docx preenchido ou um PDF montado a partir do próprio modelo (página, margens, timbre do
// cabeçalho, rodapé, parágrafos, recuos, negrito/itálico, citações, imagens e notas de rodapé). Sem Word e sem
// servidor: tudo no navegador. Usado pela página da triagem e pelos testes (node).
(function (raiz) {
  "use strict";

  const TW = 1 / 20;          // twip -> ponto
  const EMU = 1 / 12700;      // EMU -> ponto
  const ALTURA_LINHA = 1.2207; // Calibri/Carlito: (ascendente + descendente) / em
  const BASE_LINHA = 0.952 / ALTURA_LINHA;

  // ---------------------------------------------------------------- zip
  // lê um .docx: {nome: Uint8Array}; inflar(Uint8Array) -> Promise<Uint8Array> (deflate "cru")
  async function lerZip(bytes, inflar) {
    const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    let fim = -1;
    for (let i = bytes.length - 22; i >= Math.max(0, bytes.length - 70000); i--) if (dv.getUint32(i, true) === 0x06054b50) { fim = i; break; }
    if (fim < 0) throw new Error("o modelo não é um .docx válido");
    const n = dv.getUint16(fim + 10, true);
    let p = dv.getUint32(fim + 16, true);
    const dec = new TextDecoder("utf-8");
    const r = {};
    for (let k = 0; k < n; k++) {
      if (dv.getUint32(p, true) !== 0x02014b50) throw new Error("zip corrompido");
      const metodo = dv.getUint16(p + 10, true), tam = dv.getUint32(p + 20, true);
      const ln = dv.getUint16(p + 28, true), le = dv.getUint16(p + 30, true), lc = dv.getUint16(p + 32, true);
      const loc = dv.getUint32(p + 42, true);
      const nome = dec.decode(bytes.subarray(p + 46, p + 46 + ln));
      p += 46 + ln + le + lc;
      const ini = loc + 30 + dv.getUint16(loc + 26, true) + dv.getUint16(loc + 28, true);
      const dados = bytes.subarray(ini, ini + tam);
      if (nome.endsWith("/")) continue;
      r[nome] = metodo === 0 ? dados.slice() : metodo === 8 ? await inflar(dados) : null;
      if (!r[nome]) throw new Error("compressão não suportada no modelo: " + nome);
    }
    return r;
  }
  let TAB = null;
  function crc32(b) {
    if (!TAB) { TAB = new Uint32Array(256); for (let i = 0; i < 256; i++) { let c = i; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; TAB[i] = c >>> 0; } }
    let c = 0xffffffff;
    for (let i = 0; i < b.length; i++) c = TAB[(c ^ b[i]) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  }
  // grava {nome: Uint8Array} sem compressão ([Content_Types].xml primeiro, como o Word)
  function gravarZip(arquivos) {
    const enc = new TextEncoder();
    const nomes = Object.keys(arquivos).sort((a, b) => (a === "[Content_Types].xml" ? -1 : b === "[Content_Types].xml" ? 1 : 0));
    const partes = [], central = [];
    let pos = 0;
    const u16 = (v) => [v & 0xff, (v >>> 8) & 0xff], u32 = (v) => [v & 0xff, (v >>> 8) & 0xff, (v >>> 16) & 0xff, (v >>> 24) & 0xff];
    for (const nm of nomes) {
      const nome = enc.encode(nm), d = arquivos[nm], crc = crc32(d);
      const loc = Uint8Array.from([].concat(u32(0x04034b50), u16(20), u16(0x0800), u16(0), u16(0), u16(0x21), u32(crc), u32(d.length), u32(d.length), u16(nome.length), u16(0)));
      partes.push(loc, nome, d);
      central.push(Uint8Array.from([].concat(u32(0x02014b50), u16(20), u16(20), u16(0x0800), u16(0), u16(0), u16(0x21), u32(crc), u32(d.length), u32(d.length), u16(nome.length), u16(0), u16(0), u16(0), u16(0), u32(0), u32(pos))), nome);
      pos += loc.length + nome.length + d.length;
    }
    const tc = central.reduce((s, x) => s + x.length, 0);
    const tudo = partes.concat(central, [Uint8Array.from([].concat(u32(0x06054b50), u16(0), u16(0), u16(nomes.length), u16(nomes.length), u32(tc), u32(pos), u16(0)))]);
    const r = new Uint8Array(tudo.reduce((s, x) => s + x.length, 0));
    let o = 0;
    for (const x of tudo) { r.set(x, o); o += x.length; }
    return r;
  }

  // ---------------------------------------------------------------- campos
  const xmlEsc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
  function dataPorExtenso(d) {
    d = d || new Date();
    return `${d.getDate()} de ${MESES[d.getMonth()]} de ${d.getFullYear()}`;
  }
  // "EDGAR CENTURION CACERES" -> "Edgar Centurion Caceres" (nomes já com minúsculas ficam como estão)
  function nomeProprio(nome) {
    const s = String(nome || "").replace(/\s+/g, " ").trim();
    if (!s || s !== s.toUpperCase()) return s;
    return s.toLowerCase().split(" ").map((w, i) => (i > 0 && /^(de|da|do|das|dos|e|di|du|del)$/.test(w) ? w : w.charAt(0).toUpperCase() + w.slice(1))).join(" ");
  }
  // nome do arquivo: "1. Ciência 6003870" (os 7 primeiros dígitos do nº)
  function nomeArquivo(modelo, processo, ext) {
    const sete = String(processo || "").replace(/\D/g, "").slice(0, 7);
    return (modelo + (sete ? " " + sete : "")).replace(/[\\/:*?"<>|]/g, " ").replace(/\s+/g, " ").trim() + "." + ext;
  }
  // troca {{campo}} nas partes de texto do .docx (o modelo preparado tem cada campo inteiro num só trecho)
  function preencherPartes(partes, campos) {
    const r = Object.assign({}, partes);
    const dec = new TextDecoder("utf-8"), enc = new TextEncoder();
    for (const nome of Object.keys(partes)) {
      if (!/^word\/(document|header\d*|footer\d*|footnotes|endnotes)\.xml$/.test(nome)) continue;
      let x = dec.decode(partes[nome]);
      const antes = x;
      x = x.replace(/\{\{(\w+)\}\}/g, (m, k) => (Object.prototype.hasOwnProperty.call(campos, k) ? xmlEsc(campos[k]) : m));
      if (x !== antes) r[nome] = enc.encode(x);
    }
    return r;
  }
  // .docx preenchido
  async function gerarDocx(bytesModelo, campos, inflar) {
    return gravarZip(preencherPartes(await lerZip(bytesModelo, inflar), campos));
  }

  // ---------------------------------------------------------------- leitura do .docx (o necessário para o PDF)
  const at = (tag, nome) => { const m = new RegExp("\\b" + nome + '="([^"]*)"').exec(tag || ""); return m ? m[1] : null; };
  const ent = (s) => s.replace(/&(lt|gt|amp|quot|apos|#\d+|#x[0-9a-f]+);/gi, (m, e) => ({ lt: "<", gt: ">", amp: "&", quot: '"', apos: "'" })[e.toLowerCase()] ||
    String.fromCodePoint(e[1] === "x" || e[1] === "X" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10)));
  const liga = (rpr, nome) => { const m = new RegExp("<w:" + nome + "(\\s[^>]*)?/>").exec(rpr || ""); if (!m) return null; const v = at(m[0], "w:val"); return !(v === "0" || v === "false" || v === "none"); };

  function propsRun(rpr) {
    const p = {};
    const b = liga(rpr, "b"); if (b !== null) p.b = b;
    const i = liga(rpr, "i"); if (i !== null) p.i = i;
    const u = /<w:u\s[^>]*w:val="(?!none)[^"]+"/.test(rpr || ""); if (u) p.u = true;
    const sz = /<w:sz\s+w:val="(\d+)"/.exec(rpr || ""); if (sz) p.sz = Number(sz[1]);
    const cor = /<w:color\s+w:val="([0-9A-Fa-f]{6})"/.exec(rpr || ""); if (cor) p.cor = cor[1];
    if (/<w:vertAlign\s+w:val="superscript"/.test(rpr || "")) p.sup = true;
    if (/<w:caps\/>|<w:caps\s+w:val="(1|true)"/.test(rpr || "")) p.caps = true;
    return p;
  }
  function propsPar(ppr) {
    const p = {};
    const jc = /<w:jc\s+w:val="(\w+)"/.exec(ppr || ""); if (jc) p.jc = jc[1];
    const sp = /<w:spacing\s[^>]*\/>/.exec(ppr || "");
    if (sp) {
      const a = at(sp[0], "w:before"), d = at(sp[0], "w:after"), l = at(sp[0], "w:line"), r = at(sp[0], "w:lineRule");
      if (a !== null) p.antes = Number(a); if (d !== null) p.depois = Number(d);
      if (l !== null) { p.linha = Number(l); p.regra = r || "auto"; }
    }
    const ind = /<w:ind\s[^>]*\/>/.exec(ppr || "");
    if (ind) {
      const e = at(ind[0], "w:left") || at(ind[0], "w:start"), d = at(ind[0], "w:right") || at(ind[0], "w:end");
      const f = at(ind[0], "w:firstLine"), h = at(ind[0], "w:hanging");
      if (e !== null) p.esq = Number(e); if (d !== null) p.dir = Number(d);
      if (f !== null) p.primeira = Number(f); if (h !== null) p.primeira = -Number(h);
    }
    const est = /<w:pStyle\s+w:val="([^"]+)"/.exec(ppr || ""); if (est) p.estilo = est[1];
    if (/<w:pageBreakBefore\/>/.test(ppr || "")) p.quebraAntes = true;
    return p;
  }
  function lerEstilos(xml) {
    const r = { padraoRun: {}, padraoPar: {}, estilos: {}, normal: null };
    const dd = /<w:docDefaults>([\s\S]*?)<\/w:docDefaults>/.exec(xml || "");
    if (dd) {
      r.padraoRun = propsRun((/<w:rPrDefault>([\s\S]*?)<\/w:rPrDefault>/.exec(dd[1]) || [])[1]);
      r.padraoPar = propsPar((/<w:pPrDefault>([\s\S]*?)<\/w:pPrDefault>/.exec(dd[1]) || [])[1]);
    }
    for (const m of (xml || "").matchAll(/<w:style\s([^>]*)>([\s\S]*?)<\/w:style>/g)) {
      const id = at(m[1], "w:styleId");
      if (!id) continue;
      const base = /<w:basedOn\s+w:val="([^"]+)"/.exec(m[2]);
      r.estilos[id] = {
        tipo: at(m[1], "w:type"), base: base ? base[1] : null,
        run: propsRun((/<w:rPr>([\s\S]*?)<\/w:rPr>/.exec(m[2]) || [])[1]),
        par: propsPar((/<w:pPr>([\s\S]*?)<\/w:pPr>/.exec(m[2]) || [])[1]),
      };
      if (at(m[1], "w:default") === "1" && at(m[1], "w:type") === "paragraph") r.normal = id;
    }
    return r;
  }
  function cadeia(estilos, id, campo) {
    const lista = [];
    let k = 0;
    while (id && estilos.estilos[id] && k++ < 10) { lista.unshift(estilos.estilos[id][campo]); id = estilos.estilos[id].base; }
    return Object.assign({}, ...lista);
  }
  function lerRels(xml) {
    const r = {};
    for (const m of (xml || "").matchAll(/<Relationship\s([^>]*)\/?>/g)) r[at(m[1], "Id")] = { alvo: at(m[1], "Target"), tipo: at(m[1], "Type") };
    return r;
  }
  // parágrafos de uma parte (corpo, cabeçalho, rodapé, nota): [{par:{...}, runs:[...]}]
  function lerParagrafos(xml, estilos, rels, pasta) {
    const r = [];
    for (const m of (xml || "").matchAll(/<w:p(?:\s[^>]*)?>([\s\S]*?)<\/w:p>/g)) {
      const conteudo = m[1];
      const ppr = (/<w:pPr>([\s\S]*?)<\/w:pPr>/.exec(conteudo) || [])[1] || "";
      const parDireto = propsPar(ppr);
      const idEst = parDireto.estilo || estilos.normal;
      const par = Object.assign({}, estilos.padraoPar, cadeia(estilos, idEst, "par"), parDireto);
      const runBase = Object.assign({}, estilos.padraoRun, cadeia(estilos, idEst, "run"));
      const marca = Object.assign({}, runBase, propsRun((/<w:rPr>([\s\S]*?)<\/w:rPr>/.exec(ppr) || [])[1]));
      const resto = conteudo.replace(/<w:pPr>[\s\S]*?<\/w:pPr>/, "");
      const runs = [];
      let campo = 0; // 0 normal, 1 instrução do campo, 2 resultado do campo
      for (const rm of resto.matchAll(/<w:r(?:\s[^>]*)?>([\s\S]*?)<\/w:r>/g)) {
        const rc = rm[1];
        const rpr = (/<w:rPr>([\s\S]*?)<\/w:rPr>/.exec(rc) || [])[1] || "";
        const est = /<w:rStyle\s+w:val="([^"]+)"/.exec(rpr);
        const props = Object.assign({}, runBase, est ? cadeia(estilos, est[1], "run") : {}, propsRun(rpr));
        for (const el of rc.replace(/<w:rPr>[\s\S]*?<\/w:rPr>/, "").matchAll(/<w:(t|tab|br|cr|drawing|footnoteReference|footnoteRef|fldChar|instrText|noBreakHyphen|softHyphen|sym)\b([^>]*?)(?:\/>|>([\s\S]*?)<\/w:\1>)/g)) {
          const [, tag, atr, dentro] = el;
          if (tag === "fldChar") { const t = at(atr, "w:fldCharType"); campo = t === "begin" ? 1 : t === "separate" ? 2 : 0; continue; }
          if (campo === 1 || tag === "instrText") continue;
          if (tag === "t") runs.push(Object.assign({ t: ent(dentro || "") }, props));
          else if (tag === "tab") runs.push(Object.assign({ tab: true }, props));
          else if (tag === "br" || tag === "cr") runs.push(Object.assign({ br: at(atr, "w:type") === "page" ? "pagina" : "linha" }, props));
          else if (tag === "noBreakHyphen") runs.push(Object.assign({ t: "\u2011" }, props));
          else if (tag === "footnoteReference") runs.push(Object.assign({ nota: at(atr, "w:id"), sup: true }, props));
          else if (tag === "footnoteRef") runs.push(Object.assign({ notaNumero: true, sup: true }, props));
          else if (tag === "drawing") {
            const ext = /<wp:extent\s+cx="(\d+)"\s+cy="(\d+)"/.exec(dentro || ""), blip = /<a:blip\s[^>]*r:embed="([^"]+)"/.exec(dentro || "");
            if (ext && blip && rels[blip[1]]) runs.push(Object.assign({ img: { arquivo: caminho(pasta, rels[blip[1]].alvo), w: Number(ext[1]) * EMU, h: Number(ext[2]) * EMU } }, props));
          }
        }
      }
      r.push({ par, marca, runs });
    }
    return r;
  }
  const caminho = (pasta, alvo) => (alvo.startsWith("/") ? alvo.slice(1) : (pasta + alvo)).replace(/[^/]+\/\.\.\//g, "");

  // modelo pronto para o PDF: página, cabeçalho, rodapé, corpo, notas e imagens
  function lerModelo(partes) {
    const dec = new TextDecoder("utf-8");
    const txt = (n) => (partes[n] ? dec.decode(partes[n]) : "");
    const estilos = lerEstilos(txt("word/styles.xml"));
    const doc = txt("word/document.xml");
    const relsDoc = lerRels(txt("word/_rels/document.xml.rels"));
    const sect = (doc.match(/<w:sectPr[\s\S]*?<\/w:sectPr>/g) || []).pop() || "";
    const pgSz = /<w:pgSz\s[^>]*\/>/.exec(sect), pgMar = /<w:pgMar\s[^>]*\/>/.exec(sect);
    const n = (tag, a, pad) => { const v = at(tag ? tag[0] : "", a); return v === null ? pad : Number(v); };
    const pagina = {
      w: n(pgSz, "w:w", 11906) * TW, h: n(pgSz, "w:h", 16838) * TW,
      sup: n(pgMar, "w:top", 1440) * TW, inf: n(pgMar, "w:bottom", 1440) * TW, esq: n(pgMar, "w:left", 1440) * TW, dir: n(pgMar, "w:right", 1440) * TW,
      cab: n(pgMar, "w:header", 708) * TW, rod: n(pgMar, "w:footer", 708) * TW,
    };
    const parte = (tipoRef) => {
      const ref = new RegExp("<w:" + tipoRef + 'Reference\\s[^>]*w:type="default"[^>]*/>').exec(sect) || new RegExp("<w:" + tipoRef + "Reference\\s[^>]*/>").exec(sect);
      const rel = ref && relsDoc[at(ref[0], "r:id")];
      if (!rel) return [];
      const arq = caminho("word/", rel.alvo);
      return lerParagrafos(txt(arq), estilos, lerRels(txt(arq.replace(/([^/]+)$/, "_rels/$1.rels"))), "word/");
    };
    const notas = {};
    const fx = txt("word/footnotes.xml");
    const relsNotas = lerRels(txt("word/_rels/footnotes.xml.rels"));
    for (const m of fx.matchAll(/<w:footnote\s([^>]*)>([\s\S]*?)<\/w:footnote>/g)) {
      if (at(m[1], "w:type")) continue; // separadores
      notas[at(m[1], "w:id")] = lerParagrafos(m[2], estilos, relsNotas, "word/");
    }
    const corpoXml = doc.slice(doc.indexOf("<w:body>"), doc.lastIndexOf("<w:sectPr"));
    return { pagina, cabecalho: parte("header"), rodape: parte("footer"), corpo: lerParagrafos(corpoXml, estilos, relsDoc, "word/"), notas, partes };
  }

  // ---------------------------------------------------------------- PDF
  // fontes: {r, b, i, bi} (bytes de fontes métricas da Calibri, ex.: Carlito); PDFLib e fontkit: as bibliotecas
  async function gerarPdf(bytesModelo, campos, op) {
    const partes = preencherPartes(await lerZip(bytesModelo, op.inflar), campos);
    const mod = lerModelo(partes);
    const { PDFDocument, rgb } = op.PDFLib;
    const pdf = await PDFDocument.create();
    pdf.registerFontkit(op.fontkit);
    pdf.setTitle(op.titulo || "Petição");
    pdf.setAuthor(op.autor || "Defensoria Pública");
    pdf.setCreator("APTO - Triagem da Mesa");
    pdf.setProducer("APTO");
    const F = {};
    for (const k of ["r", "b", "i", "bi"]) F[k] = await pdf.embedFont(op.fontes[k] || op.fontes.r, { subset: true });
    const fonte = (p) => F[p.b && p.i ? "bi" : p.b ? "b" : p.i ? "i" : "r"];
    const imagens = {};
    const imagem = async (arq) => {
      if (imagens[arq]) return imagens[arq];
      const b = partes[arq];
      if (!b) return null;
      imagens[arq] = b[0] === 0x89 && b[1] === 0x50 ? await pdf.embedPng(b) : (b[0] === 0xff && b[1] === 0xd8 ? await pdf.embedJpg(b) : null);
      return imagens[arq];
    };
    const P = mod.pagina;
    const tam = (p) => (p.sz || 22) / 2;
    const cor = (p) => { const c = p.cor && p.cor !== "auto" ? p.cor : "000000"; return rgb(parseInt(c.slice(0, 2), 16) / 255, parseInt(c.slice(2, 4), 16) / 255, parseInt(c.slice(4, 6), 16) / 255); };
    // numeração das notas na ordem em que aparecem
    const numNota = {};
    let contNota = 0;

    // quebra um parágrafo em linhas: [{itens:[{tipo, texto, w, props, img}], largura, h, base, ultima}]
    function linhas(par, largura) {
      const itens = [];
      const add = (o) => itens.push(o);
      for (const r of par.runs) {
        if (r.img) { add({ tipo: "img", w: r.img.w, h: r.img.h, img: r.img, props: r }); continue; }
        if (r.br) { add({ tipo: "br", pagina: r.br === "pagina", props: r }); continue; }
        if (r.tab) { add({ tipo: "tab", w: 0, props: r }); continue; }
        if (r.nota || r.notaNumero) {
          if (r.nota && !numNota[r.nota]) numNota[r.nota] = ++contNota;
          const t = String(r.nota ? numNota[r.nota] : r.notaNumero);
          const s = tam(r) * 0.65;
          add({ tipo: "txt", texto: t, w: fonte(r).widthOfTextAtSize(t, s), props: Object.assign({}, r, { szReal: s }), sup: true });
          continue;
        }
        const texto = r.caps ? r.t.toUpperCase() : r.t;
        for (const pedaco of texto.split(/( +)/)) {
          if (!pedaco) continue;
          const sz = tam(r), f = fonte(r);
          add({ tipo: pedaco.trim() ? "txt" : "esp", texto: pedaco, w: f.widthOfTextAtSize(pedaco, sz), props: r });
        }
      }
      const fator = par.par.regra === "auto" || !par.par.regra ? (par.par.linha || 240) / 240 : null;
      const altura = (sz) => (fator !== null ? sz * ALTURA_LINHA * fator : par.par.regra === "exact" ? par.par.linha * TW : Math.max(par.par.linha * TW, sz * ALTURA_LINHA));
      const res = [];
      let atual = [], larg = 0, primeira = true;
      const recuo = () => (primeira ? (par.par.primeira || 0) * TW : 0);
      const fechar = (ultima, quebra) => {
        while (atual.length && atual[atual.length - 1].tipo === "esp") larg -= atual.pop().w;
        let szMax = 0, imgMax = 0;
        for (const it of atual) {
          if (it.tipo === "img") imgMax = Math.max(imgMax, it.h);
          else if (!it.sup) szMax = Math.max(szMax, tam(it.props));
        }
        if (!szMax) szMax = tam(par.marca);
        const hTexto = altura(szMax);
        const h = Math.max(hTexto, imgMax);
        res.push({ itens: atual, largura: larg, h, base: imgMax > hTexto ? imgMax : hTexto * BASE_LINHA + (fator !== null ? 0 : 0), szMax, ultima, recuo: recuo(), quebra });
        atual = []; larg = 0; primeira = false;
      };
      for (const it of itens) {
        if (it.tipo === "br") { fechar(true, it.pagina); continue; }
        if (it.tipo === "tab") {
          const pos = recuo() + larg, passo = 36;
          it.w = Math.max(4, Math.ceil((pos + 0.01) / passo) * passo - pos);
        }
        const disponivel = largura - recuo();
        if (it.tipo !== "esp" && larg + it.w > disponivel && atual.some((x) => x.tipo !== "esp")) {
          fechar(false);
        }
        if (it.tipo === "esp" && !atual.length) continue;
        atual.push(it); larg += it.w;
        // palavra maior que a linha: corta por caracteres
        if (it.tipo === "txt" && it.w > largura - recuo() && !it.sup) {
          atual.pop(); larg -= it.w;
          let buf = "";
          const f = fonte(it.props), sz = tam(it.props);
          for (const ch of it.texto) {
            if (f.widthOfTextAtSize(buf + ch, sz) > largura - recuo() - larg && buf) {
              atual.push({ tipo: "txt", texto: buf, w: f.widthOfTextAtSize(buf, sz), props: it.props }); fechar(false); buf = "";
            }
            buf += ch;
          }
          if (buf) { const w = f.widthOfTextAtSize(buf, sz); atual.push({ tipo: "txt", texto: buf, w, props: it.props }); larg += w; }
        }
      }
      if (atual.length || !res.length) fechar(true);
      return res;
    }

    // desenha linhas de um parágrafo a partir de y (topo); devolve o novo y
    function desenharLinha(pg, par, ln, x0, largura, yTopo) {
      const jc = par.par.jc || "left";
      const xIni = x0 + ln.recuo;
      const livre = largura - ln.recuo - ln.largura;
      let x = xIni, extra = 0;
      if (jc === "center") x = xIni + livre / 2;
      else if (jc === "right" || jc === "end") x = xIni + livre;
      else if ((jc === "both" || jc === "distribute") && !ln.ultima) {
        const espacos = ln.itens.filter((it) => it.tipo === "esp").length;
        if (espacos) extra = livre / espacos;
      }
      const yBase = yTopo + ln.base;
      for (const it of ln.itens) {
        if (it.tipo === "esp") { x += it.w + extra; continue; }
        if (it.tipo === "tab") { x += it.w; continue; }
        if (it.tipo === "img") {
          const im = imagens[it.img.arquivo];
          if (im) pg.drawImage(im, { x, y: P.h - (yTopo + ln.base), width: it.w, height: it.h });
          x += it.w; continue;
        }
        const sz = it.sup ? it.props.szReal : tam(it.props);
        const dy = it.sup ? tam(it.props) * 0.33 : 0;
        pg.drawText(it.texto, { x, y: P.h - yBase + dy, size: sz, font: fonte(it.props), color: cor(it.props) });
        if (it.props.u) pg.drawLine({ start: { x, y: P.h - yBase - 1.2 }, end: { x: x + it.w, y: P.h - yBase - 1.2 }, thickness: 0.5, color: cor(it.props) });
        x += it.w;
      }
    }

    // pré-carrega as imagens
    for (const grupo of [mod.cabecalho, mod.rodape, mod.corpo, ...Object.values(mod.notas)]) for (const p of grupo) for (const r of p.runs) if (r.img) await imagem(r.img.arquivo);

    const largura = P.w - P.esq - P.dir;
    const alturaBloco = (pars) => pars.reduce((s, p) => s + ((p.par.antes || 0) + (p.par.depois || 0)) * TW + linhas(p, largura).reduce((t, l) => t + l.h, 0), 0);
    // cabeçalho e rodapé (numeração de nota não muda aqui)
    const salvaNum = Object.assign({}, numNota), salvaCont = contNota;
    const hCab = alturaBloco(mod.cabecalho), hRod = alturaBloco(mod.rodape);
    Object.keys(numNota).forEach((k) => delete numNota[k]); Object.assign(numNota, salvaNum); contNota = salvaCont;
    const topo = Math.max(P.sup, P.cab + hCab);
    const fundo = Math.min(P.h - P.inf, P.h - P.rod - hRod);

    const paginas = [];
    let pg = null, y = 0, notasPg = [];
    const desenharBloco = (pagina, pars, yIni) => {
      let yy = yIni;
      for (const p of pars) {
        yy += (p.par.antes || 0) * TW;
        for (const ln of linhas(p, largura)) { desenharLinha(pagina, p, ln, P.esq + (p.par.esq || 0) * TW, largura - ((p.par.esq || 0) + (p.par.dir || 0)) * TW, yy); yy += ln.h; }
        yy += (p.par.depois || 0) * TW;
      }
      return yy;
    };
    const fecharPagina = () => {
      if (!pg) return;
      // notas de rodapé desta página, acima do rodapé
      if (notasPg.length) {
        const hN = notasPg.reduce((s, n) => s + alturaNota(n), 0) + 8;
        let yy = fundo - hN;
        pg.drawLine({ start: { x: P.esq, y: P.h - yy - 2 }, end: { x: P.esq + 144, y: P.h - yy - 2 }, thickness: 0.5, color: rgb(0, 0, 0) });
        yy += 6;
        for (const n of notasPg) yy = desenharNota(pg, n, yy);
      }
    };
    const novaPagina = () => {
      fecharPagina();
      pg = pdf.addPage([P.w, P.h]);
      paginas.push(pg);
      desenharBloco(pg, mod.cabecalho, P.cab);
      let yr = P.h - P.rod - hRod;
      desenharBloco(pg, mod.rodape, yr);
      y = topo; notasPg = [];
    };
    const parsNota = (id) => (mod.notas[id] || []).map((p) => ({ par: p.par, marca: p.marca, runs: p.runs.map((r) => (r.notaNumero ? Object.assign({}, r, { notaNumero: numNota[id] }) : r)) }));
    const alturaNota = (id) => alturaBloco(parsNota(id));
    const desenharNota = (pagina, id, yy) => desenharBloco(pagina, parsNota(id), yy);
    const limite = () => fundo - (notasPg.length ? notasPg.reduce((s, n) => s + alturaNota(n), 0) + 8 : 0);

    novaPagina();
    for (const p of mod.corpo) {
      if (p.par.quebraAntes && y > topo) novaPagina();
      const esq = (p.par.esq || 0) * TW, dir = (p.par.dir || 0) * TW;
      const larg = largura - esq - dir;
      y += y > topo ? (p.par.antes || 0) * TW : 0;
      for (const ln of linhas(p, larg)) {
        const notasLinha = ln.itens.filter((it) => it.props && it.props.nota).map((it) => it.props.nota);
        const hNotasNovas = notasLinha.filter((n) => !notasPg.includes(n)).reduce((s, n) => s + alturaNota(n), 0) + (notasLinha.length && !notasPg.length ? 8 : 0);
        if (y + ln.h > limite() - hNotasNovas && y > topo) novaPagina();
        for (const n of notasLinha) if (!notasPg.includes(n)) notasPg.push(n);
        desenharLinha(pg, p, ln, P.esq + esq, larg, y);
        y += ln.h;
        if (ln.quebra) novaPagina();
      }
      y += (p.par.depois || 0) * TW;
    }
    fecharPagina();
    return await pdf.save();
  }

  // ---------------------------------------------------------------- catálogo
  // modelos da pasta "modelos" (preparados a partir dos da Defensoria). formato: "pdf" = sai em PDF (com opção de
  // Word); "docx" = pede dados do caso, sai em Word com os pontos a completar em amarelo
  const MODELOS = [
    { id: "ciencia", nome: "1. Ciência", arquivo: "ciencia.docx", formato: "pdf" },
    { id: "nao_opor_mp", nome: "1. Não Opor - MP", arquivo: "nao_opor_mp.docx", formato: "pdf" },
    { id: "advogado_particular", nome: "1. Advogado Particular", arquivo: "advogado_particular.docx", formato: "pdf" },
    { id: "esgotamento_previo", nome: "1. Esgotamento Prévio", arquivo: "esgotamento_previo.docx", formato: "pdf" },
    { id: "aud_justificacao", nome: "1. Aud Justificação", arquivo: "aud_justificacao.docx", formato: "pdf" },
    { id: "justificativa_primeira_falta", nome: "1. Justificativa - primeira falta", arquivo: "justificativa_primeira_falta.docx", formato: "docx" },
    { id: "extincao_punibilidade", nome: "1. Extinção Punibilidade", arquivo: "extincao_punibilidade.docx", formato: "docx" },
    { id: "livramento_condicional", nome: "1. LC", arquivo: "livramento_condicional.docx", formato: "docx" },
    { id: "progressao_aberto", nome: "1. Progressão Aberto", arquivo: "progressao_aberto.docx", formato: "docx" },
  ];
  // sugestão (só destaque na lista; quem escolhe é o defensor)
  function modeloSugerido(providencia, analise) {
    if (!providencia) return null;
    const t = providencia.texto || "";
    if (providencia.tipo === "Ciência") return "ciencia";
    if (providencia.tipo === "Parecer do MP") return "nao_opor_mp";
    if (/endereço atualizado|localiza/i.test(t)) return "esgotamento_previo";
    if (/prisão noticiada/i.test(t)) return "aud_justificacao";
    void analise;
    return null;
  }

  const api = { lerZip, gravarZip, crc32, dataPorExtenso, nomeProprio, nomeArquivo, preencherPartes, gerarDocx, lerModelo, lerEstilos, lerParagrafos, gerarPdf, MODELOS, modeloSugerido };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else raiz.PETICAO = api;
})(typeof self !== "undefined" ? self : this);
