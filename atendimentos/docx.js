// APTO Atendimentos - monta o relatório do dia em Word (.docx) no mesmo formato do "16.11.docx":
// tabela de 2 colunas, título "ATENDIMENTOS – DD.MM", à esquerda "Nome - processo", à direita o contato e o texto.
// Estilos, tema e margens vêm da pasta modelo_docx (copiados do relatório original). Tudo é feito no navegador.
(function () {
  "use strict";
  const ext = (self.ATD && self.ATD.ext) || globalThis.browser || globalThis.chrome;

  // ---------- ZIP (sem compressão: o Word abre normalmente) ----------
  const TAB_CRC = (() => {
    const t = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      t[n] = c >>> 0;
    }
    return t;
  })();
  function crc32(b) {
    let c = 0xffffffff;
    for (let i = 0; i < b.length; i++) c = TAB_CRC[(c ^ b[i]) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  }
  function zip(arquivos) {
    const enc = new TextEncoder();
    const d = new Date();
    const hora = (d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() >> 1);
    const data = ((d.getFullYear() - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate();
    const partes = [], central = [];
    let pos = 0;
    for (const [nome, conteudo] of arquivos) {
      const n = enc.encode(nome);
      const b = typeof conteudo === "string" ? enc.encode(conteudo) : conteudo;
      const crc = crc32(b);
      const h = new DataView(new ArrayBuffer(30));
      h.setUint32(0, 0x04034b50, true); h.setUint16(4, 20, true); h.setUint16(6, 0x0800, true); h.setUint16(8, 0, true);
      h.setUint16(10, hora, true); h.setUint16(12, data, true); h.setUint32(14, crc, true);
      h.setUint32(18, b.length, true); h.setUint32(22, b.length, true); h.setUint16(26, n.length, true); h.setUint16(28, 0, true);
      partes.push(new Uint8Array(h.buffer), n, b);
      const c = new DataView(new ArrayBuffer(46));
      c.setUint32(0, 0x02014b50, true); c.setUint16(4, 20, true); c.setUint16(6, 20, true); c.setUint16(8, 0x0800, true);
      c.setUint16(10, 0, true); c.setUint16(12, hora, true); c.setUint16(14, data, true); c.setUint32(16, crc, true);
      c.setUint32(20, b.length, true); c.setUint32(24, b.length, true); c.setUint16(28, n.length, true);
      c.setUint32(42, pos, true);
      central.push(new Uint8Array(c.buffer), n);
      pos += 30 + n.length + b.length;
    }
    const tamCentral = central.reduce((s, x) => s + x.length, 0);
    const fim = new DataView(new ArrayBuffer(22));
    fim.setUint32(0, 0x06054b50, true); fim.setUint16(8, arquivos.length, true); fim.setUint16(10, arquivos.length, true);
    fim.setUint32(12, tamCentral, true); fim.setUint32(16, pos, true);
    return new Blob([...partes, ...central, new Uint8Array(fim.buffer)], { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" });
  }

  // ---------- documento ----------
  const esc = (s) => String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const run = (t, rPr) => `<w:r>${rPr ? "<w:rPr>" + rPr + "</w:rPr>" : ""}<w:t xml:space="preserve">${esc(t)}</w:t></w:r>`;
  const par = (runs, pPr) => `<w:p>${pPr ? "<w:pPr>" + pPr + "</w:pPr>" : ""}${runs || ""}</w:p>`;
  const celula = (w, conteudo, extra) => `<w:tc><w:tcPr><w:tcW w:w="${w}" w:type="dxa"/>${extra || ""}</w:tcPr>${conteudo || par("")}</w:tc>`;

  // atendimentos: [{nome, processos[], contato, texto}]
  function documentoXml(titulo, atendimentos) {
    const linhas = [];
    linhas.push(`<w:tr>${celula(8494, par(run(titulo, "<w:b/><w:sz w:val=\"36\"/>"), "<w:jc w:val=\"center\"/><w:rPr><w:b/></w:rPr>"), "<w:gridSpan w:val=\"2\"/>")}</w:tr>`);
    for (const a of atendimentos) {
      const esq = par(run(a.nome + (a.processos.length ? " - " : "")) + (a.processos.length ? run(a.processos.join(" / ")) : ""));
      const textos = String(a.texto || "").split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
      let dir = "";
      if (a.contato) dir += par(run(a.contato)) + par("");
      dir += textos.length ? textos.map((t) => par(run(t))).join("") : par("");
      linhas.push(`<w:tr>${celula(4247, esq)}${celula(4247, dir)}</w:tr>`);
    }
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' +
      '<w:document xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">' +
      "<w:body><w:tbl><w:tblPr><w:tblStyle w:val=\"Tabelacomgrade\"/><w:tblW w:w=\"0\" w:type=\"auto\"/>" +
      "<w:tblLook w:val=\"04A0\" w:firstRow=\"1\" w:lastRow=\"0\" w:firstColumn=\"1\" w:lastColumn=\"0\" w:noHBand=\"0\" w:noVBand=\"1\"/></w:tblPr>" +
      "<w:tblGrid><w:gridCol w:w=\"4247\"/><w:gridCol w:w=\"4247\"/></w:tblGrid>" + linhas.join("") + "</w:tbl><w:p/>" +
      "<w:sectPr><w:pgSz w:w=\"11906\" w:h=\"16838\"/><w:pgMar w:top=\"1417\" w:right=\"1701\" w:bottom=\"1417\" w:left=\"1701\" w:header=\"708\" w:footer=\"708\" w:gutter=\"0\"/>" +
      "<w:cols w:space=\"708\"/><w:docGrid w:linePitch=\"360\"/></w:sectPr></w:body></w:document>";
  }

  const PARTES = [
    ["[Content_Types].xml", "Content_Types.xml"],
    ["_rels/.rels", "_rels__.rels"],
    ["word/_rels/document.xml.rels", "word___rels__document.xml.rels"],
    ["word/styles.xml", "word__styles.xml"],
    ["word/settings.xml", "word__settings.xml"],
    ["word/webSettings.xml", "word__webSettings.xml"],
    ["word/fontTable.xml", "word__fontTable.xml"],
    ["word/theme/theme1.xml", "word__theme__theme1.xml"],
  ];
  async function relatorio(titulo, atendimentos) {
    const arquivos = [];
    for (const [nome, arq] of PARTES) {
      const r = await fetch(ext.runtime.getURL("modelo_docx/" + arq));
      arquivos.push([nome, new Uint8Array(await r.arrayBuffer())]);
    }
    const agora = new Date().toISOString().replace(/\.\d+Z$/, "Z");
    arquivos.push(["word/document.xml", documentoXml(titulo, atendimentos)]);
    arquivos.push(["docProps/core.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">' +
      `<dc:title>${esc(titulo)}</dc:title><dc:creator>APTO Atendimentos</dc:creator><dcterms:created xsi:type="dcterms:W3CDTF">${agora}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">${agora}</dcterms:modified></cp:coreProperties>`]);
    arquivos.push(["docProps/app.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Microsoft Office Word</Application></Properties>']);
    return zip(arquivos);
  }

  self.DOCX = { relatorio, documentoXml, zip };
})();
