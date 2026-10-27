import sys
from playwright.sync_api import sync_playwright
F='file:///home/user/rspe-base/docs/analise_design/demonstracao/abas_simuladas.html'
temas=sys.argv[1].split(','); abas=sys.argv[2].split(',') if len(sys.argv)>2 else ['prog']
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium'); pg=b.new_page(viewport={'width':1440,'height':860})
    pg.on('pageerror',lambda e:print('ERRO',e))
    for t in temas:
        for a in abas:
            pg.goto(F+f'?tema={t}&aba={a}&ordem=urg'); pg.wait_for_timeout(300)
            o=pg.evaluate("""()=>{const W=innerWidth;const r=[];for(const s of ['.topo','.abas','.lista table','.cab','.cartoes','.layind']){const e=document.querySelector(s);if(!e)continue;const x=e.getBoundingClientRect();const sw=e.scrollWidth-e.clientWidth;if(x.right>W+1||sw>1)r.push(s+' '+Math.round(x.right-W)+'/'+sw)};const ab=document.querySelector('.abas');return r.join(' ')+' abasH='+Math.round(ab.scrollHeight)}""")
            print(t,a,o); pg.screenshot(path=f'chk/l{t}_{a}.png')
    b.close()
