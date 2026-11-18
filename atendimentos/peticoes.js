// APTO Atendimentos - petições a partir dos modelos do gabinete (pasta "modelos", cópias de "3. Modelos" e
// "3. Modelos\Modelos Fluxo"). Em cada modelo, acha sozinho o nº do processo de exemplo, o nome de exemplo e a data
// ("Campo Grande, 22 de julho de 2026") e troca pelos do atendimento, mesmo que o Word tenha partido o texto em
// pedaços. O resto do modelo (timbre, formatação, citações) fica igual. PDF (pdf-lib, fonte Carlito) só para os
// modelos que não pedem mais nada; os demais saem em Word para completar.
(function () {
  "use strict";
  const A = self.ATD;
  const P = self.PETICAO;
  const ext = A.ext;
  const dec = new TextDecoder("utf-8"), enc = new TextEncoder();

  async function bytesDaExtensao(caminho) {
    const r = await fetch(ext.runtime.getURL(caminho));
    if (!r.ok) throw new Error("arquivo da extensão não encontrado: " + caminho);
    return new Uint8Array(await r.arrayBuffer());
  }
  async function inflar(b) {
    const s = new Blob([b]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
    return new Uint8Array(await new Response(s).arrayBuffer());
  }

  let lista = null;
  async function catalogo() {
    if (!lista) {
      const r = await fetch(ext.runtime.getURL("modelos/lista.json"));
      // sem a pasta, o APTO responde 404 com o motivo (e onde pôr a pasta): não ler um corpo vazio como JSON
      if (!r.ok) throw new Error(r.statusText || "lista dos modelos não encontrada");
      lista = await r.json();
    }
    return lista;
  }
  const esquecer = () => { lista = null; };

  // ---------- texto dos parágrafos, com o mapa de volta para os <w:t> ----------
  const ent = (s) => s.replace(/&(lt|gt|amp|quot|apos|#\d+|#x[0-9a-f]+);/gi, (m, e) => ({ lt: "<", gt: ">", amp: "&", quot: '"', apos: "'" })[e.toLowerCase()] ||
    String.fromCodePoint(e[1] === "x" || e[1] === "X" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10)));
  const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const RE_T = /<w:t(\s[^>]*)?>([^<]*)<\/w:t>|<w:t(\s[^>]*)?\/>/g;
  function textoPar(parXml) {
    let s = "";
    for (const m of parXml.matchAll(RE_T)) s += ent(m[2] || "");
    return s;
  }
  // troca "de" por "para" num parágrafo, mesmo partido em vários <w:t>; devolve o XML novo
  function trocarNoPar(parXml, de, para, flags) {
    const ts = [...parXml.matchAll(RE_T)].map((m) => ({ ini: m.index, fim: m.index + m[0].length, atr: m[1] || "", txt: ent(m[2] || "") }));
    if (!ts.length) return parXml;
    let todo = "";
    const pos = ts.map((t) => { const p = todo.length; todo += t.txt; return p; });
    const re = de instanceof RegExp ? new RegExp(de.source, "g" + (de.flags.includes("i") ? "i" : "")) : new RegExp(de.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "g" + (flags || ""));
    const achados = [...todo.matchAll(re)].map((m) => ({ a: m.index, b: m.index + m[0].length, novo: typeof para === "function" ? para(m) : para }));
    if (!achados.length) return parXml;
    const novos = ts.map((t) => t.txt);
    for (const f of achados.reverse()) {
      // primeiro e último <w:t> tocados
      let i = pos.findIndex((p, k) => f.a >= p && f.a < p + ts[k].txt.length);
      let j = pos.findIndex((p, k) => f.b > p && f.b <= p + ts[k].txt.length);
      if (i < 0 || j < 0) continue;
      const antes = novos[i].slice(0, f.a - pos[i]);
      const depois = novos[j].slice(f.b - pos[j]);
      if (i === j) novos[i] = antes + f.novo + depois;
      else {
        novos[i] = antes + f.novo;
        for (let k = i + 1; k < j; k++) novos[k] = "";
        novos[j] = depois;
      }
    }
    let r = "", ult = 0;
    ts.forEach((t, k) => {
      r += parXml.slice(ult, t.ini);
      r += novos[k] === t.txt ? parXml.slice(t.ini, t.fim) : `<w:t xml:space="preserve">${esc(novos[k])}</w:t>`;
      ult = t.fim;
    });
    return r + parXml.slice(ult);
  }
  const RE_PAR = /<w:p[ >][\s\S]*?<\/w:p>/g;
  const RE_CNJ = /\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}/;

  // ---------- o que trocar em cada modelo ----------
  function analisar(docXml) {
    const pars = (docXml.match(RE_PAR) || []).map(textoPar);
    let processo = "", nome = "", genero = "";
    // nº do processo: o da linha "Feito nº / Execução nº / autos da Execução Penal nº"; senão o 1º do texto
    for (const t of pars) {
      const m = /(Feito|Execução(?: Penal)?|Autos|Processo)\s*(?:n[º°.o]*\.?)\s*(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})/i.exec(t);
      if (m) { processo = m[2]; break; }
    }
    // modelo com marcadores ({{processo}}, {{nome}}, {{data}}), como os da triagem do SEEU
    if (!processo && pars.some((t) => t.includes("{{processo}}"))) processo = "{{processo}}";
    if (!processo) { const t = pars.find((x) => RE_CNJ.test(x)); if (t) processo = RE_CNJ.exec(t)[0]; }
    // modelo com campo em branco: "Feito nº [_______]"
    if (!processo) { for (const t of pars) { const m = /n[º°.]\s*(\[_{3,}\])/.exec(t); if (m) { processo = m[1]; break; } } }
    // nome de exemplo
    for (const t of pars) {
      let m = /em favor d[oa] paciente ([^,]{4,80}),/.exec(t) || /^Agravante:\s*(.{4,80})$/.exec(t.trim());
      if (!m) m = /^\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ\[][^,\d]{3,80}?),\s*(?:já |devidamente )?(?:qualificad|brasileir|já devidamente qualificad)/.exec(t);
      if (!m) m = /^\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ][^,\d]{3,80}?),\s*qualificad/.exec(t);
      if (m && !/Defensoria|Excelent|Ministério/i.test(m[1])) {
        nome = m[1].trim();
        const g = /qualificad([oa])/.exec(t);
        genero = g ? g[1] : "";
        break;
      }
    }
    if (!nome && pars.some((t) => t.includes("{{nome}}"))) nome = "{{nome}}";
    const temData = pars.some((t) => /Campo Grande,\s.*\d{1,2} de [a-zç]+ de \d{4}/i.test(t) || t.includes("{{data}}"));
    return { processo, nome, genero, temData };
  }

  // monta o .docx do atendimento a partir do modelo
  async function preparar(modelo, campos) {
    const partes = await P.lerZip(await bytesDaExtensao("modelos/" + modelo.arquivo), inflar);
    const info = analisar(dec.decode(partes["word/document.xml"]));
    const hoje = P.dataPorExtenso(new Date());
    const nomeNovo = campos.nome;
    for (const arq of Object.keys(partes)) {
      if (!/^word\/(document|header\d*|footer\d*|footnotes)\.xml$/.test(arq)) continue;
      let x = dec.decode(partes[arq]);
      x = x.replace(RE_PAR, (par) => {
        let p = par;
        const t = textoPar(p);
        if (info.processo && campos.processo && t.includes(info.processo)) p = trocarNoPar(p, info.processo, campos.processo);
        if (info.nome && nomeNovo) {
          if (t.includes(info.nome)) p = trocarNoPar(p, info.nome, nomeNovo);
          else if (t.includes(info.nome.toUpperCase())) p = trocarNoPar(p, info.nome.toUpperCase(), nomeNovo.toUpperCase());
          // "já qualificado" / "já qualificada" conforme o atendimento
          if (campos.genero && info.genero && campos.genero !== info.genero && textoPar(p).includes(nomeNovo)) {
            p = trocarNoPar(p, /qualificad[oa]\b/, "qualificad" + campos.genero);
          }
        }
        if (/^\s*Campo Grande,/.test(t)) p = trocarNoPar(p, /\d{1,2} de [a-zç]+ de \d{4}/i, hoje);
        if (textoPar(p).includes("{{data}}")) p = trocarNoPar(p, "{{data}}", hoje);
        return p;
      });
      partes[arq] = enc.encode(x);
    }
    return { bytes: P.gravarZip(partes), info };
  }

  let fontes = null;
  async function gerar(modelo, campos, formato) {
    const { bytes, info } = await preparar(modelo, campos);
    if (formato !== "pdf") return { bytes, tipo: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", info };
    if (!fontes) {
      const f = (n) => bytesDaExtensao("fontes_pdf/carlito-latin-" + n + ".woff");
      fontes = { r: await f("400-normal"), b: await f("700-normal"), i: await f("400-italic"), bi: await f("700-italic") };
    }
    const pdf = await P.gerarPdf(bytes, {}, { inflar, PDFLib: self.PDFLib, fontkit: self.fontkit, fontes, titulo: modelo.nome + " " + campos.processo, autor: "Cahuê Duarte e Urdiales" });
    return { bytes: pdf, tipo: "application/pdf", info };
  }

  self.PETS = { catalogo, esquecer, analisar, preparar, gerar, trocarNoPar, textoPar, nomeArquivo: P.nomeArquivo };
})();
