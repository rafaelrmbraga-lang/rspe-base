// APTO - caracteres de um PDF pelo pdf.js, no formato que o leitor de ficha do APTO usa (rspe_pdf_paginas.paginas):
// [{largura, altura, chars: [[texto, x0, x1, top, bottom, tamanho, fonte], ...]}]. As medidas seguem o pdfminer/pdfplumber:
// caixa do caractere com a altura do corpo da fonte, a partir da linha de base mais o descendente (top = altura - y1).
// Dentro de cada trecho de texto, a largura de cada caractere vem da largura do próprio glifo na fonte (proporcional).
// unicode -> código do caractere na fonte (para achar a largura do glifo)
function mapaCodigos(fo) {
  const m = new Map();
  const tu = fo && fo.toUnicode;
  const arr = tu && (Array.isArray(tu) ? tu : Array.isArray(tu._map) ? tu._map : null);
  if (arr) arr.forEach((u, cod) => { if (typeof u === "string" && !m.has(u)) m.set(u, cod); });
  else if (tu && typeof tu === "object" && tu._map) for (const [cod, u] of Object.entries(tu._map)) if (!m.has(u)) m.set(u, +cod);
  return m;
}

export async function caracteres(pdfjsLib, dados) {
  const doc = await pdfjsLib.getDocument({ data: dados, isEvalSupported: false, disableFontFace: true, useSystemFonts: false, fontExtraProperties: true, verbosity: 0 }).promise;
  const out = [];
  for (let n = 1; n <= doc.numPages; n++) {
    const pg = await doc.getPage(n);
    const vp = pg.getViewport({ scale: 1 });
    await pg.getOperatorList();                       // carrega as fontes (nome, descendente, larguras)
    const tc = await pg.getTextContent({ disableNormalization: true });
    const chars = [];
    for (const it of tc.items) {
      if (!it.str || !it.height) continue;   // espaço que o pdf.js insere entre trechos (altura 0): não existe no PDF
      const [a, b, , d, e, f] = it.transform;
      const size = Math.hypot(a, b) || Math.abs(d);
      let fonte = "", desc = -0.217, larguras = null, codigo = null;
      try {
        const fo = pg.commonObjs.get(it.fontName);
        fonte = String(fo.name || fo.loadedName || "").replace(/^[A-Z]{6}\+/, "");
        if (typeof fo.descent === "number" && fo.descent < 0) desc = fo.descent;
        larguras = fo.widths || null;
        codigo = mapaCodigos(fo);
      } catch (err) { /* fonte não carregada: medidas padrão */ }
      const s = [...it.str];
      // largura de cada glifo pela tabela da fonte (código do caractere); sem ela, partes iguais da largura do trecho
      const pesos = s.map((ch) => {
        const cod = codigo && codigo.has(ch) ? codigo.get(ch) : ch.charCodeAt(0);
        const g = larguras && larguras[cod];
        return g > 0 ? g : 0;
      });
      const soma = pesos.reduce((x, y) => x + y, 0);
      let x = e;
      const y1 = f + desc * size + size;
      const top = vp.height - y1, bottom = top + size;
      s.forEach((ch, i) => {
        const w = soma > 0 ? it.width * (pesos[i] / soma) : it.width / s.length;
        chars.push([ch, x, x + w, top, bottom, size, fonte]);
        x += w;
      });
    }
    out.push({ largura: vp.width, altura: vp.height, chars });
  }
  return out;
}
