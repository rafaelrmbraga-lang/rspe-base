// Propostas para a aba Jurisprudências (demonstração; dados anonimizados). window.JV = 'A' | 'B' | 'C'; window.JREAL = contagens reais
(() => {
const css = `
.jp-bar{display:flex;align-items:center;gap:14px;width:100%;flex-wrap:wrap}
.jp-q{flex:1;min-width:280px;position:relative}.jp-q input{width:100%;height:36px;padding:0 12px 0 36px;border:1px solid var(--fl);border-bottom-color:#8A8A8A;border-radius:4px;background:#fff;font:inherit;font-size:13.5px}
.jp-q svg{position:absolute;left:12px;top:10px;width:16px;height:16px;color:var(--tx3)}
.jp-seg{display:inline-flex;align-items:center;gap:8px;font-size:12.5px;color:var(--tx3)}.jp-seg>span{font-weight:600}
.jp-seg .sg{display:inline-flex;border:1px solid var(--fl);border-radius:4px;background:#fff;padding:2px}
.jp-seg button{padding:4px 10px;border-radius:3px;font-size:12.5px;color:var(--tx)}.jp-seg button small{color:var(--tx3);margin-left:5px;font-size:11.5px}
.jp-seg button.on{background:var(--pri);color:#fff;font-weight:600}.jp-seg button.on small{color:#DDEBE2}
.jp-ord{height:32px;border:1px solid var(--fl);border-radius:4px;background:#fff;padding:0 8px;font:inherit;font-size:12.5px}
.jp{display:grid;height:100%;min-height:0}
.jp-side{border-right:1px solid var(--fl);overflow:auto;padding:12px 8px;background:#FCFCFC}
.jp-side h4{margin:4px 10px 8px;font-size:12px;font-weight:600;color:var(--tx3)}
.jp-t{position:relative;display:flex;align-items:center;gap:8px;height:30px;padding:0 10px 0 12px;border-radius:4px;font-size:13px;color:var(--tx);cursor:pointer}
.jp-t span{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.jp-t b{font-weight:400;font-size:12px;color:var(--tx3);font-variant-numeric:tabular-nums}
.jp-t.on{background:rgba(0,0,0,.055);font-weight:600}.jp-t.on::before{content:"";position:absolute;left:0;top:7px;bottom:7px;width:3px;border-radius:2px;background:var(--pri)}
.jp-head{display:flex;align-items:center;gap:8px;padding:12px 18px 8px;font-size:12.5px;white-space:nowrap;color:var(--tx3);border-bottom:1px solid var(--fl)}.jp-head b{font-size:14px;color:var(--tx)}
.jp-head .ft{display:inline-flex;align-items:center;gap:6px;padding:2px 4px 2px 9px;border:1px solid var(--fl);border-radius:12px;background:#fff;color:var(--tx2);font-size:12px}.jp-head .ft i{font-style:normal;color:var(--tx3);padding:0 4px;cursor:pointer}
mark{background:#FFF1B8;color:inherit;border-radius:2px;padding:0 1px}
.jp-res{font-size:12px;font-weight:600}.jp-res.prov{color:#1F6B3A}.jp-res.mp{color:#334E68}
.jp-temas{font-size:12px;color:var(--tx3)}
.jp-btn{display:inline-flex;align-items:center;gap:6px;height:30px;padding:0 12px;border:1px solid var(--fl);border-bottom-color:#CCC;border-radius:4px;background:#FDFDFD;font-size:12.5px;font-weight:600;color:var(--tx);cursor:pointer;white-space:nowrap}
.jp-btn.pri{background:var(--pri);border-color:var(--pri2);color:#fff}.jp-btn svg{width:14px;height:14px}
.jp-lk{font-size:12.5px;font-weight:600;color:var(--pri);cursor:pointer;white-space:nowrap}
/* A: lista e leitura */
.jpA{grid-template-columns:230px minmax(0,1fr) minmax(0,1.15fr)}
.jpA-list{overflow:auto;border-right:1px solid var(--fl)}
.jpA-it{position:relative;padding:11px 18px 11px 20px;border-bottom:1px solid #EFEFEF;cursor:pointer}
.jpA-it:hover{background:#F7F7F7}.jpA-it.on{background:#F2F6F3}.jpA-it.on::before{content:"";position:absolute;left:0;top:10px;bottom:10px;width:3px;border-radius:2px;background:var(--pri)}
.jpA-l1{display:flex;gap:8px;align-items:baseline;margin-bottom:3px}.jpA-l1 .jp-temas{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.jpA-l1 small{font-size:12px;color:var(--tx3);white-space:nowrap}
.jpA-tt{font-size:13.5px;font-weight:600;line-height:1.4;color:var(--tx);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.jpA-m{margin-top:4px;font-size:12px;color:var(--tx3)}
.jpA-read{overflow:auto;padding:18px 26px 24px;background:#fff}
.jpA-read .jp-temas{margin-bottom:6px}
.jpA-read h2{margin:0 0 8px;font-size:18px;line-height:1.4;font-weight:600;color:var(--tx)}
.jpA-meta{display:grid;grid-template-columns:auto 1fr;gap:3px 14px;font-size:12.5px;margin:10px 0 12px;padding:10px 12px;border:1px solid var(--fl);border-radius:6px;background:#FAFAFA}.jpA-meta dt{color:var(--tx3)}.jpA-meta dd{margin:0;color:var(--tx)}
.jpA-act{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 14px}
.jp-kw{font-size:12px;color:var(--tx2);margin:0 0 10px}.jp-kw b{color:var(--tx3);font-weight:600;margin-right:4px}
.jpA-em p{margin:0 0 9px;font-size:13.5px;line-height:1.6;color:#2B2F2C}.jpA-em h5{margin:12px 0 4px;font-size:12px;letter-spacing:.2px;color:var(--tx3)}
/* B: cartões leves */
.jpB{grid-template-columns:240px minmax(0,1fr)}
.jpB-list{overflow:auto}
.jpB-it{padding:16px 24px 14px;border-bottom:1px solid #EDEDED}
.jpB-l1{display:flex;align-items:center;gap:10px;margin-bottom:5px}.jpB-l1 .jp-temas{flex:1}
.jpB-badge{font-size:11.5px;font-weight:600;padding:1px 8px;border-radius:10px;background:#E6F2EA;color:#1F6B3A}.jpB-badge.mp{background:#E8EDF3;color:#334E68}
.jpB-l1 small{font-size:12px;color:var(--tx3)}
.jpB-tt{font-size:15px;font-weight:600;line-height:1.45;color:var(--tx);margin-bottom:5px}
.jpB-m{font-size:12.5px;color:var(--tx3);margin-bottom:8px}
.jpB-em{font-size:13px;line-height:1.6;color:#3A3F3B;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;margin-bottom:6px}
.jpB-ac{display:flex;align-items:center;gap:8px}.jpB-ac .sp{flex:1}
/* C: tabela */
.jpC{grid-template-columns:230px minmax(0,1fr)}
.jpC-wrap{overflow:auto}
table.jpC-t{width:100%;border-collapse:collapse}
.jpC-t th{position:sticky;top:0;background:#fff;text-align:left;font-size:12px;font-weight:600;color:#616161;padding:9px 10px;border-bottom:1px solid var(--fl);z-index:1}
.jpC-t td{padding:9px 10px;border-bottom:1px solid #F0F0F0;font-size:12.5px;vertical-align:top}
.jpC-t td.tt{font-size:13px;font-weight:600;line-height:1.4}.jpC-t td.tt .jp-temas{display:block;font-weight:400;margin-top:3px}
.jpC-t td.nw{white-space:nowrap;color:var(--tx2)}
.jpC-t tr.ab td{background:#F7FAF8}.jpC-t tr.det td{background:#FBFCFB;padding:4px 14px 14px 22px}
.jpC-det{font-weight:400;border-left:3px solid var(--pri);padding:4px 0 0 14px}.jpC-det p{margin:0 0 8px;font-size:13px;line-height:1.6;max-width:980px}
.jpC-ac{display:flex;gap:6px;flex-wrap:wrap}
`;
document.head.insertAdjacentHTML('beforeend', `<style id="jpcss">${css}</style>`);
const R = window.JREAL || {}; const fmt = n => Number(n||0).toLocaleString('pt-BR');
const I = { cp:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>',
  q:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 7h4v4H7zM13 7h4v4h-4z"/><path d="M7 11c0 3-1 5-3 6M13 11c0 3-1 5-3 6"/></svg>',
  ext:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3h7v7"/><path d="M21 3l-9 9"/><path d="M19 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h5"/></svg>' };
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const Q = () => (window.JQ || '').trim();
const hi = s => { s = esc(s); const q = Q(); if (!q) return s; q.split(/\s+/).filter(w=>w.length>2).forEach(w => { s = s.replace(new RegExp('(' + w.replace(/[.*+?^${}()|[\]\\]/g,'\\$&') + ')', 'ig'), '<mark>$1</mark>'); }); return s; };
const res = x => x.rot ? [x.rot==='Recurso do MP desprovido'?'mp':'prov', x.rot] : ui.tesResultado(x.resultado);
const relat = x => ((x.tribunal||'TJMS')!=='TJMS' ? 'Min. ' : 'Des. ') + x.relator;
const refProc = x => (x.tribunal||'TJMS')!=='TJMS' ? x.proc : (x.classe + ' nº ' + x.proc);
const partes = x => ui.tesPartes(x.ementa || x.tese || '');
const temas = x => (x.temas||[]).join(' · ');
const side = (n) => { const T = ui._teses; const nt = (R.temas)||{}; return `<div class="jp-side"><h4>Temas</h4><div class="jp-t ${!window.JTEMA?'on':''}"><span>Todos</span><b>${fmt(R.total||T.itens.length)}</b></div>${T.temas.map(t=>`<div class="jp-t ${window.JTEMA===t.tema?'on':''}"><span>${esc(t.tema)}</span><b>${fmt(nt[t.tema]||t.n)}</b></div>`).join('')}</div>`; };
const head = (n) => `<div class="jp-head"><b>${fmt(n)}</b> decisões favoráveis à defesa${Q()?` <span class="ft">busca “${esc(Q())}” <i>✕</i></span>`:''}${window.JTEMA?` <span class="ft">tema ${esc(window.JTEMA)} <i>✕</i></span>`:''}<span style="flex:1"></span><select class="jp-ord"><option>Mais recentes</option><option>Mais antigas</option></select></div>`;
const acoes = (x, full) => `<span class="jp-btn" title="Abre o inteiro teor no site do tribunal">${I.ext}Inteiro teor</span><span class="jp-btn">${I.q}Copiar referência</span><span class="jp-btn pri">${I.cp}Copiar ementa</span>`;
ui.renderTeses = function(){
  document.getElementById('subtabs').classList.remove('on');
  const seg = (rot, ops, on) => `<span class="jp-seg"><span>${rot}</span><span class="sg">${ops.map(o=>`<button class="${o[0]===on?'on':''}">${o[0]}${o[1]!=null?`<small>${fmt(o[1])}</small>`:''}</button>`).join('')}</span></span>`;
  document.getElementById('stats').innerHTML = `<div class="jp-bar"><label class="jp-q"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg><input placeholder="Pesquisar tese, ementa, relator ou número (ex.: remição ENEM, falta grave bis in idem)" value="${esc(Q())}"></label>
    ${seg('Tribunal', [['Todos',null],['TJMS',R.TJMS],['STJ',R.STJ],['STF',R.STF]], 'Todos')}${seg('Decisão', [['Todas',null],['Acórdão',R['Acórdão']],['Monocrática',R['Monocrática']]], 'Todas')}</div>`;
  this.tesLista(); };
ui.tesLista = function(){
  const card = document.getElementById('card'); const T = this._teses; let V = T.itens.slice();
  if (window.JTEMA) V = V.filter(x => (x.temas||[]).includes(window.JTEMA));
  const n = window.JN || (window.JTEMA ? (R.temas||{})[window.JTEMA] : R.total) || V.length;
  const v = window.JV || 'A';
  if (v === 'A') { const sel = V[window.JSEL||0]; const P = partes(sel);
    const lista = V.slice(0, 40).map((x,i)=>{ const [rc,rt]=res(x); return `<div class="jpA-it ${i===(window.JSEL||0)?'on':''}"><div class="jpA-l1"><span class="jp-temas">${esc(temas(x))}</span><small>${esc(x.julg||'')}</small></div><div class="jpA-tt">${hi(x.tese)}</div><div class="jpA-m">${esc(x.tribunal||'TJMS')}${x.orgao?' · '+esc(x.orgao):''}${x.tipo==='Monocrática'?' · monocrática':''} · <span class="jp-res ${rc}">${esc(rt)}</span></div></div>`; }).join('');
    const [rc,rt]=res(sel); const corpo = String(P.corpo||'').split('\n').filter(Boolean).map(l=>/^[IVX]+\.\s+[A-ZÁÉÍÓÚ ]+$/.test(l.trim())?`<h5>${esc(l.trim())}</h5>`:`<p>${hi(l)}</p>`).join('');
    const ler = `<div class="jpA-read"><div class="jp-temas">${esc(temas(sel))}</div><h2>${hi(sel.tese)}</h2><div class="jpA-act">${acoes(sel,true)}</div>
      <dl class="jpA-meta"><dt>Resultado</dt><dd><span class="jp-res ${rc}">${esc(rt)}</span></dd><dt>Tribunal</dt><dd>${esc(sel.tribunal||'TJMS')}${sel.orgao?' · '+esc(sel.orgao):''}${sel.tipo==='Monocrática'?' · decisão monocrática':' · acórdão'}</dd><dt>Relator</dt><dd>${esc(relat(sel))}</dd><dt>Processo</dt><dd>${esc(refProc(sel))}${sel.comarca?' · '+esc(sel.comarca):''}</dd><dt>Julgamento</dt><dd>${esc(sel.julg||'—')}${sel.pub?' · publicado em '+esc(sel.pub):''}</dd></dl>
      ${P.kw.length?`<div class="jp-kw"><b>Palavras-chave</b>${P.kw.map(esc).join(' · ')}</div>`:''}<div class="jpA-em">${corpo}</div></div>`;
    card.innerHTML = `<div class="jp jpA">${side()}<div class="jpA-list">${head(n)}${lista}</div>${ler}</div>`; return; }
  if (v === 'B') { const lista = V.slice(0, 30).map(x=>{ const [rc,rt]=res(x); const P=partes(x); return `<div class="jpB-it"><div class="jpB-l1"><span class="jp-temas">${esc(temas(x))}</span><span class="jpB-badge ${rc}">${esc(rt)}</span><small>j. ${esc(x.julg||'')}</small></div>
      <div class="jpB-tt">${hi(x.tese)}</div><div class="jpB-m">${esc(x.tribunal||'TJMS')}${x.orgao?' · '+esc(x.orgao):''} · ${esc(relat(x))} · ${esc(refProc(x))}${x.comarca?' · '+esc(x.comarca):''}</div>
      ${P.kw.length?`<div class="jp-kw"><b>Palavras-chave</b>${P.kw.map(esc).join(' · ')}</div>`:''}<div class="jpB-em">${hi(String(P.corpo||'').replace(/\n+/g,' '))}</div>
      <div class="jpB-ac"><span class="jp-lk">Ler ementa completa ▾</span><span class="sp"></span>${acoes(x)}</div></div>`; }).join('');
    card.innerHTML = `<div class="jp jpB">${side()}<div class="jpB-list">${head(n)}${lista}</div></div>`; return; }
  const ab = window.JSEL||0; const linhas = V.slice(0, 40).map((x,i)=>{ const [rc,rt]=res(x); const P=partes(x);
    return `<tr class="${i===ab?'ab':''}"><td class="tt">${hi(x.tese)}<span class="jp-temas">${esc(temas(x))}</span></td><td class="nw">${esc(x.tribunal||'TJMS')}<br><span class="jp-temas">${esc(x.orgao||(x.tipo==='Monocrática'?'monocrática':''))}</span></td><td class="nw">${esc(x.julg||'')}</td><td class="nw"><span class="jp-res ${rc}">${esc(rt)}</span></td><td class="nw"><span class="jp-lk">${i===ab?'Recolher ▴':'Ementa ▾'}</span></td></tr>`
      + (i===ab?`<tr class="det"><td colspan="5"><div class="jpC-det"><div class="jpB-m">${esc(relat(x))} · ${esc(refProc(x))}${x.comarca?' · '+esc(x.comarca):''}</div>${P.kw.length?`<div class="jp-kw"><b>Palavras-chave</b>${P.kw.map(esc).join(' · ')}</div>`:''}${String(P.corpo||'').split('\n').filter(Boolean).slice(0,4).map(l=>`<p>${hi(l)}</p>`).join('')}<div class="jpC-ac">${acoes(x)}</div></div></td></tr>`:''); }).join('');
  card.innerHTML = `<div class="jp jpC">${side()}<div class="jpC-wrap">${head(n)}<table class="jpC-t"><thead><tr><th>Tese</th><th>Tribunal</th><th>Julgamento</th><th>Resultado</th><th></th></tr></thead><tbody>${linhas}</tbody></table></div></div>`; };
})();
