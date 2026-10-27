"""Inventário de controles (botões, links, campos, títulos) da tela: uso inv2.py <ui.html> <saida.json>"""
import sys, os, json, ponte
S = "/tmp/claude-0/-home-user-rspe-base/883108c0-aece-5660-92ba-781fc4fe86e8/scratchpad"
UIH, OUT = sys.argv[1], sys.argv[2]
api, jan = ponte.criar(S + "/bases2/Comarca_Ficticia.sqlite")
from playwright.sync_api import sync_playwright
JS = """()=>{ const vis=e=>{const r=e.getBoundingClientRect(); const s=getComputedStyle(e); return r.width>0&&r.height>0&&s.visibility!=='hidden'};
 const out=[]; document.querySelectorAll('button,[onclick],summary,select,option,input,th,label').forEach(e=>{ if(e.tagName!=='OPTION'&&!vis(e)) return; if(e.closest('.legado')) return; let t=(e.tagName==='OPTION'?e.textContent:(e.innerText||e.value||e.title||e.getAttribute('aria-label')||e.placeholder||'')).trim().replace(/\\s+/g,' ').slice(0,70); if(!t) t='['+(e.title||e.getAttribute('aria-label')||String(e.className))+']'; out.push(t)});
 return [...new Set(out)];}"""
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium"); pg = b.new_page(viewport={"width": 1440, "height": 860})
    ponte.ligar(pg, api, jan); pg.goto("file://" + os.path.abspath(UIH)); pg.wait_for_function("document.querySelector('tbody tr')", timeout=120000); pg.wait_for_timeout(800)
    R = {}
    def pega(k): R[k] = sorted(set(R.get(k, [])) | set(pg.evaluate(JS)))
    for a in ['geral','prog','liv','ind','presc','ext','fd','aud','base','geo','teses','quadro']:
        pg.evaluate("id=>ui.irAba(id)", a); pg.wait_for_timeout(900); pega(a)
        for m in ['mBase','mExp','mImp']:
            if pg.evaluate("id=>!!document.getElementById(id)", m) and a == 'geral':
                pg.evaluate("id=>document.getElementById(id).classList.add('on')", m); pg.wait_for_timeout(150); pega('menus'); pg.evaluate("id=>document.getElementById(id).classList.remove('on')", m)
        if pg.evaluate("!!document.getElementById('fpan')"):
            pg.evaluate("ui._fpOpen=true;ui.render()"); pg.wait_for_timeout(200); pega(a); pg.evaluate("ui._fpOpen=false;ui.render()")
    ids = pg.evaluate("ui.dados.registros.map(r=>r.id)")
    for a, f in [('presc', "r=>r.presc_ppe_cor==='vermelho'"), ('aud', "r=>r.aud_cor==='vermelho'"), ('fd', "r=>r.fd_cor==='vermelho'")]:
        pg.evaluate("id=>ui.irAba(id)", a); pg.wait_for_timeout(600); i = pg.evaluate("ui.dados.registros.find(%s).id" % f)
        pg.evaluate("id=>ui.expandir(id)", i); pg.wait_for_timeout(1500); pega('aberta_' + a)
    pg.evaluate("ui.irAba('geral')"); pg.wait_for_timeout(400); pg.evaluate("id=>ui.abrir(id)", ids[0]); pg.wait_for_timeout(2500)
    pg.evaluate("document.querySelectorAll('#drawer details').forEach(d=>d.open=true)"); pg.wait_for_timeout(300); pega('painel')
    json.dump(R, open(OUT, "w"), ensure_ascii=False, indent=1)
    b.close()
print("ok", {k: len(v) for k, v in R.items()})
