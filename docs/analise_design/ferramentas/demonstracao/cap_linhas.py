"""Captura todas as abas de uma linha gráfica. uso: cap_linhas.py temas [WxH] [query extra] [prefixo]"""
import sys
from playwright.sync_api import sync_playwright
F='file:///home/user/rspe-base/docs/analise_design/demonstracao/abas_simuladas.html'
OUT='telas_todas/'
ABAS=['geral','prog','liv','ind','presc','ext','fd','aud','base','geo','teses','quadro']
temas=sys.argv[1].split(','); w,h=map(int,(sys.argv[2] if len(sys.argv)>2 else '1440x860').split('x'))
extra=sys.argv[3] if len(sys.argv)>3 else ''; pref=sys.argv[4] if len(sys.argv)>4 else None
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium'); pg=b.new_page(viewport={'width':w,'height':h},device_scale_factor=1.5)
    pg.on('pageerror',lambda e:print('ERRO',e))
    for t in temas:
        n=pref or f't{t}'
        for a in ABAS:
            pg.goto(F+f'?tema={t}&aba={a}&ordem=urg'+extra); pg.wait_for_timeout(250); pg.screenshot(path=f'{OUT}{n}_{a}.png')
        pg.goto(F+f'?tema={t}&aba=geral&sobre=painel'+extra); pg.wait_for_timeout(250); pg.screenshot(path=f'{OUT}{n}_painel.png')
        print('tema',t,n)
    b.close()
