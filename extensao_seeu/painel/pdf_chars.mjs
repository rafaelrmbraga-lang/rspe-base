// APTO - caracteres de um PDF pelo pdf.js, no formato que os leitores do APTO usam (rspe_pdf_paginas.paginas):
// [{largura, altura, chars: [[texto, x0, x1, top, bottom, tamanho, fonte], ...]}].
// Caminho exato (o mesmo do pdfminer, que o pdfplumber do APTO usa): a lista de operações de desenho da página, glifo a
// glifo, com a matriz de texto, o espaçamento entre caracteres e palavras e a escala horizontal - cada caractere desenhado,
// espaços inclusive, vira um caractere com a sua caixa (altura do corpo da fonte a partir da linha de base + o descendente).
// A camada de texto do pdf.js (getTextContent) junta espaços e inventa espaços entre trechos: só fica de reserva, se a lista
// de operações falhar.

const mul = (m, n) => [m[0] * n[0] + m[1] * n[2], m[0] * n[1] + m[1] * n[3], m[2] * n[0] + m[3] * n[2], m[2] * n[1] + m[3] * n[3],
  m[4] * n[0] + m[5] * n[2] + n[4], m[4] * n[1] + m[5] * n[3] + n[5]];
const transl = (m, x, y) => [m[0], m[1], m[2], m[3], x * m[0] + y * m[2] + m[4], x * m[1] + y * m[3] + m[5]];

function nomeFonte(fo) {
  return String((fo && (fo.name || fo.loadedName)) || "").replace(/^[A-Z]{6}\+/, "");
}

async function pelaListaDeOperacoes(pdfjsLib, pg) {
  const O = pdfjsLib.OPS;
  const ops = await pg.getOperatorList();
  const [vx0, vy0, , vy1] = pg.view;              // caixa da página (a origem pode não ser 0)
  const chars = [];
  let ctm = [1, 0, 0, 1, 0, 0];
  const pilha = [];
  let tm = [1, 0, 0, 1, 0, 0], tlm = tm, fo = null, tam = 0, tc = 0, tw = 0, th = 1, tl = 0, rise = 0, fmx = 0.001;
  const fonte = (nome) => { try { return pg.commonObjs.get(nome); } catch (e) { return null; } };
  function glifos(lista) {
    if (!fo) return;
    const desc = typeof fo.descent === "number" && fo.descent < 0 ? fo.descent : 0;
    const nome = nomeFonte(fo);
    for (const g of lista) {
      if (typeof g === "number") { tm = transl(tm, -g * 0.001 * tam * th, 0); continue; }
      if (!g) continue;
      const w0 = (g.width || 0) * fmx;              // largura do glifo em unidades de texto (fontMatrix, em geral 1/1000)
      const esp = tc + (g.isSpace ? tw : 0);
      const m = mul(tm, ctm);
      const [a, b, c, d, e, f] = m;
      const ox = rise * c + e, oy = rise * d + f;   // origem do glifo (linha de base, com a subida do texto)
      const escalaY = Math.hypot(c, d), escalaX = Math.hypot(a, b);
      const size = tam * escalaY;
      const larg = (w0 * tam + esp) * th * escalaX; // avanço em unidades da página
      const txt = g.unicode == null ? "" : String(g.unicode);
      if (txt) {
        const x0 = ox - vx0, y0 = oy - vy0 + desc * size;
        const top = (vy1 - vy0) - (y0 + size);
        chars.push([txt, x0, x0 + w0 * tam * th * escalaX, top, top + size, size, nome]);
      }
      tm = transl(tm, (w0 * tam + esp) * th, 0);
      void larg;
    }
  }
  for (let i = 0; i < ops.fnArray.length; i++) {
    const fn = ops.fnArray[i], a = ops.argsArray[i];
    switch (fn) {
      case O.save: pilha.push([ctm, tm, tlm, fo, tam, tc, tw, th, tl, rise, fmx]); break;
      case O.restore: if (pilha.length) [ctm, tm, tlm, fo, tam, tc, tw, th, tl, rise, fmx] = pilha.pop(); break;
      case O.transform: ctm = mul(a, ctm); break;
      case O.beginText: tm = tlm = [1, 0, 0, 1, 0, 0]; break;
      case O.setFont: fo = fonte(a[0]); tam = a[1]; fmx = (fo && fo.fontMatrix && fo.fontMatrix[0]) || 0.001; break;
      case O.setCharSpacing: tc = a[0]; break;
      case O.setWordSpacing: tw = a[0]; break;
      case O.setHScale: th = a[0] / 100; break;
      case O.setLeading: tl = a[0]; break;
      case O.setTextRise: rise = a[0]; break;
      case O.setTextMatrix: tm = tlm = a.length === 6 ? a.slice() : a[0].slice(); break;
      case O.moveText: tm = tlm = transl(tlm, a[0], a[1]); break;
      case O.setLeadingMoveText: tl = -a[1]; tm = tlm = transl(tlm, a[0], a[1]); break;
      case O.nextLine: tm = tlm = transl(tlm, 0, -tl); break;
      case O.showText: glifos(a[0]); break;
      case O.showSpacedText: glifos(a[0]); break;
      case O.nextLineShowText: tm = tlm = transl(tlm, 0, -tl); glifos(a[0]); break;
      case O.nextLineSetSpacingShowText: tw = a[0]; tc = a[1]; tm = tlm = transl(tlm, 0, -tl); glifos(a[2]); break;
      default: break;
    }
  }
  return { largura: pg.view[2] - pg.view[0], altura: vy1 - vy0, chars };
}

// reserva: a camada de texto (sem os espaços que o pdf.js inventa: altura 0)
async function pelaCamadaDeTexto(pg) {
  const vp = pg.getViewport({ scale: 1 });
  const tc = await pg.getTextContent({ disableNormalization: true });
  const chars = [];
  for (const it of tc.items) {
    if (!it.str || !it.height) continue;
    const [a, b, , d, e, f] = it.transform;
    const size = Math.hypot(a, b) || Math.abs(d);
    let fonte = "", desc = -0.217;
    try { const fo = pg.commonObjs.get(it.fontName); fonte = nomeFonte(fo); if (typeof fo.descent === "number" && fo.descent < 0) desc = fo.descent; } catch (err) { /* segue */ }
    const s = [...it.str];
    const top = vp.height - (f + desc * size + size);
    s.forEach((ch, i) => { const w = it.width / s.length; chars.push([ch, e + i * w, e + (i + 1) * w, top, top + size, size, fonte]); });
  }
  return { largura: vp.width, altura: vp.height, chars };
}

export async function caracteres(pdfjsLib, dados) {
  const doc = await pdfjsLib.getDocument({ data: dados, isEvalSupported: false, disableFontFace: true, useSystemFonts: false, fontExtraProperties: true, verbosity: 0 }).promise;
  const out = [];
  for (let n = 1; n <= doc.numPages; n++) {
    const pg = await doc.getPage(n);
    let p;
    try { p = await pelaListaDeOperacoes(pdfjsLib, pg); } catch (e) { p = null; }
    if (!p || !p.chars.length) p = await pelaCamadaDeTexto(pg);
    out.push(p);
  }
  return out;
}
