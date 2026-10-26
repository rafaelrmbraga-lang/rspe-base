import json
from playwright.sync_api import sync_playwright
F = 'file:///home/user/rspe-base/docs/analise_design/demonstracao/abas_simuladas.html'
OUT = '/tmp/claude-0/-home-user-rspe-base/883108c0-aece-5660-92ba-781fc4fe86e8/scratchpad/sug/prop/'
def bb(pg, s): return pg.locator(s).first.bounding_box()
def clip(pg, n, x, y, w, h): pg.screenshot(path=OUT+n+'.png', clip={'x':x,'y':y,'width':w,'height':h}); print(n)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = b.new_page(viewport={'width':1440,'height':860}, device_scale_factor=1.5); pg.on('pageerror', lambda e: print('ERRO', e))
    def ir(q): pg.goto(F+'?'+q); pg.wait_for_timeout(450)
    ir('aba=prog&ordem=urg')
    pg.screenshot(path=OUT+'prog_inteira.png')
    caixas = pg.evaluate("""()=>{const q=s=>{const r=document.querySelector(s).getBoundingClientRect();return [r.x,r.y,r.width,r.height]};
      return {topo:q('.topo'),abas:q('.abas'),cab:q('.cab h1'),ordem:q('.ordem'),cartoes:q('.cartoes'),grupo:q('tr.grupo'),sit:q('tbody tr.l .sit'),ped:q('tbody tr.l .ped'),abrir:q('tbody tr.l .abrir')}}""")
    json.dump(caixas, open(OUT+'caixas.json','w'))
    a = bb(pg, '.abas'); clip(pg, 'cabecalho', 0, 0, 1440, a['y']+a['height']+4)
    clip(pg, 'abas', 0, a['y']-4, 1440, a['height']+10)
    c = bb(pg, '.cartoes'); clip(pg, 'cartoes', 0, c['y']-6, 1440, c['height']+12)
    l = bb(pg, '.lista'); clip(pg, 'lista_urg', l['x'], l['y'], l['width'], 330)
    th = pg.evaluate("[...document.querySelectorAll('thead th')].map(e=>{const r=e.getBoundingClientRect();return [e.textContent.trim(),r.x,r.width]})")
    sit = [x for x in th if x[0].startswith('Situa')][0]; clip(pg, 'situacao', l['x'], l['y'], sit[1]+sit[2]-l['x']+4, 330)
    clip(pg, 'fim_linha', l['x']+l['width']-560, l['y'], 560, 200)
    ir('aba=prog&ordem=alfa'); l = bb(pg, '.lista'); clip(pg, 'nome_tags', l['x'], l['y']+38, 760, 160)
    l = bb(pg, '.lista'); th = pg.evaluate("[...document.querySelectorAll('thead th')].map(e=>{const r=e.getBoundingClientRect();return [e.textContent.trim(),r.x,r.width]})")
    sit = [x for x in th if x[0].startswith('Situa')][0]; clip(pg, 'situacao', l['x'], l['y'], sit[1]+sit[2]-l['x']+4, 300)
    clip(pg, 'fim_linha', l['x']+l['width']-560, l['y'], 560, 200)
    ir('aba=ind&ordem=urg'); l = bb(pg, '.lista'); clip(pg, 'indulto', l['x'], l['y']-4, l['width'], 380)
    ir('aba=geral&sobre=painel'); d = bb(pg, '.painel'); clip(pg, 'painel', d['x'], 0, d['width'], 860)
    ir('aba=presc&ordem=urg&expande=9900001-00.2026.8.12.0001'); r = bb(pg, 'tr.exp'); clip(pg, 'presc_detalhe', 28, r['y']-50, 1384, r['height']+54)
    ir('aba=prog&ordem=urg&sobre=avisos'); t = bb(pg, '.toasts'); clip(pg, 'aviso', t['x']-120, t['y']-20, t['width']+240, t['height']+40)
    ir('aba=geral&sobre=importando'); t = bb(pg, '.prog-imp'); clip(pg, 'importando', t['x']-500, t['y']-30, t['width']+540, t['height']+60)
    ir('aba=geral&sobre=importacao'); m = bb(pg, '.modal'); clip(pg, 'importacao', m['x'], m['y'], m['width'], m['height'])
    ir('aba=prog&ordem=urg&sobre=legenda'); m = bb(pg, '.modal'); clip(pg, 'legenda_ajuda', m['x'], m['y'], m['width'], m['height'])
    ir('aba=prog&ordem=urg&q=zzzz%20inexistente'); l = bb(pg, '.lista'); clip(pg, 'vazio', 0, 0, 1440, l['y']+260)
    for a2 in ['ind','presc','fd']:
        ir('aba='+a2+'&ordem=urg'); pg.screenshot(path=OUT+'aba_'+a2+'.png'); print('aba', a2)
    pg2 = b.new_page(viewport={'width':1280,'height':680}, device_scale_factor=1.5); pg2.goto(F+'?aba=prog&ordem=urg'); pg2.wait_for_timeout(450); pg2.screenshot(path=OUT+'escala150.png'); print('escala150')
    pg3 = b.new_page(viewport={'width':1440,'height':860}, device_scale_factor=1.5)
    for a3 in ['prog','aud']:
        pg3.goto(F+'?ordem=urg&aba='+a3); pg3.wait_for_timeout(400); c = pg3.locator('.cartoes').bounding_box()
        pg3.screenshot(path=OUT+'cartoes_'+a3+'.png', clip={'x':0,'y':c['y']-6,'width':1440,'height':c['height']+12}); print('cartoes', a3)
