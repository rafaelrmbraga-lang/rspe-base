"""Mede estouros e linhas visíveis por tamanho de tela. uso: chk_tam.py temas abas WxH[,WxH] [extra-query] [png]"""
import sys
from playwright.sync_api import sync_playwright
F='file:///home/user/rspe-base/docs/analise_design/demonstracao/abas_simuladas.html'
temas=sys.argv[1].split(','); abas=sys.argv[2].split(','); tams=[tuple(map(int,t.split('x'))) for t in sys.argv[3].split(',')]
extra=sys.argv[4] if len(sys.argv)>4 else ''; png=len(sys.argv)>5
JS="""()=>{const W=innerWidth,H=innerHeight;const r=[];for(const s of ['.topo','.abas','.lista table','.cab','.cartoes','.layind','.rod']){const e=document.querySelector(s);if(!e||!e.offsetParent&&getComputedStyle(e).position!=='fixed')continue;const x=e.getBoundingClientRect();const sw=e.scrollWidth-e.clientWidth, sh=e.scrollHeight-e.clientHeight;if(x.right>W+1||sw>1||(s=='.abas'&&sh>1))r.push(s+' '+Math.round(x.right-W)+'/'+sw+(s=='.abas'?'/h'+sh:''))}
const l=document.querySelector('.lista');let n=0;if(l&&l.offsetParent){const b=l.getBoundingClientRect();document.querySelectorAll('tbody tr.l').forEach(t=>{const q=t.getBoundingClientRect();if(q.top>=b.top&&q.bottom<=b.bottom)n++})}
return r.join(' ')+' | linhas='+n}"""
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    for w,h in tams:
        pg=b.new_page(viewport={'width':w,'height':h}); pg.on('pageerror',lambda e:print('ERRO',e))
        for t in temas:
            for a in abas:
                pg.goto(F+f'?tema={t}&aba={a}&ordem=urg'+extra); pg.wait_for_timeout(250)
                print(f'{w}x{h}',t,a,pg.evaluate(JS))
                if png: pg.screenshot(path=f'chk/n{t}_{a}_{w}.png')
        pg.close()
    b.close()
