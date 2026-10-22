// Cabeçalho e abas comuns dos protótipos (dados fictícios). Uso: <div id="casca" data-aba="ind"></div>
(function(){
  const el=document.getElementById('casca'); if(!el) return; const on=el.dataset.aba;
  const t=(id,nome,n)=>`<button class="tab${id===on?' on':''}"${id===on?' aria-current="page"':''}>${nome}${n!=null?`<b>${n}</b>`:''}</button>`;
  el.outerHTML=`<header class="hd">
  <span class="marca"><i><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M6 3h12M6 21h12M7 3c0 5 10 7 10 9s-10 4-10 9M17 3c0 5-10 7-10 9s10 4 10 9"/></svg></i>APTO</span>
  <span class="base">Base <b>Comarca Fictícia</b> · 144 <span aria-hidden="true">▾</span></span>
  <span style="font-size:12px;color:var(--tx-3)">cópia de segurança: hoje 12:00</span><span class="sp"></span>
  <button class="btn pri">+ Importar</button><button class="btn">Exportar ▾</button><button class="btn ghost">Calculadora</button><button class="btn ghost">Legenda</button>
  <label class="busca"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg><input placeholder="Buscar nome, processo ou crime (Ctrl+K)"></label></header>
  <nav class="nav" aria-label="Abas">
  <div class="grp"><small>Visão geral</small><div>${t('geral','Geral')}</div></div><span class="sep"></span>
  <div class="grp"><small>Prazos</small><div>${t('prog','Progressão',13)}${t('liv','Livramento',5)}${t('ext','Extinção',14)}${t('presc','Prescrição',19)}</div></div><span class="sep"></span>
  <div class="grp"><small>Benefícios por decreto</small><div>${t('ind','Indulto e comutação',85)}</div></div><span class="sep"></span>
  <div class="grp"><small>Conferência</small><div>${t('fd','Ficha disciplinar',3)}${t('aud','Auditoria',60)}</div></div><span class="sp"></span>
  <div class="grp extra"><small>Panorama e ferramentas</small><div>${t('base','Dados da base')}${t('geo','Dados prisionais')}${t('teses','Jurisprudências')}${t('quadro','Quadro')}</div></div><div class="grp mais"><small>&nbsp;</small><div><button class="tab">Mais ▾ <span style="color:var(--tx-3)">(dados, jurisprudências, quadro)</span></button></div></div></nav>`;
})();
