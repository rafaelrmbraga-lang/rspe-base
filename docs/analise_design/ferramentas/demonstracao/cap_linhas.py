"""Captura todas as abas de cada linha gráfica (tema) do protótipo, 1440x860, escala 1,5."""
import sys
from playwright.sync_api import sync_playwright
F='file:///home/user/rspe-base/docs/analise_design/demonstracao/abas_simuladas.html'
OUT='telas_todas/'
ABAS=['geral','prog','liv','ind','presc','ext','fd','aud','base','geo','teses','quadro']
temas=sys.argv[1].split(',')
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium'); pg=b.new_page(viewport={'width':1440,'height':860},device_scale_factor=1.5)
    pg.on('pageerror',lambda e:print('ERRO',e))
    for t in temas:
        for a in ABAS:
            pg.goto(F+f'?tema={t}&aba={a}&ordem=urg'); pg.wait_for_timeout(250); pg.screenshot(path=f'{OUT}t{t}_{a}.png')
        pg.goto(F+f'?tema={t}&aba=geral&sobre=painel'); pg.wait_for_timeout(250); pg.screenshot(path=f'{OUT}t{t}_painel.png')
        print('tema',t)
    b.close()
