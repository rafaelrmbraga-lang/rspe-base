import ponte
S = "/tmp/claude-0/-home-user-rspe-base/883108c0-aece-5660-92ba-781fc4fe86e8/scratchpad"
OUT = S + "/demo/telas_todas/t0_"
api, jan = ponte.criar(S + "/bases/Comarca_Ficticia.sqlite")
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page(viewport={"width": 1440, "height": 860})
    ponte.abrir(pg, api, jan); pg.wait_for_function("document.querySelector('tbody tr')", timeout=120000); pg.wait_for_timeout(800)
    for a in ['geral','prog','liv','ind','presc','ext','fd','aud','base','geo','teses','quadro']:
        pg.evaluate("id=>ui.irAba(id)", a); pg.wait_for_timeout(1800)
        pg.evaluate("document.getElementById('toast').classList.remove('on')"); pg.wait_for_timeout(300)
        pg.screenshot(path=OUT + a + ".png"); print(a)
    pg.evaluate("ui.irAba('geral')"); pg.wait_for_timeout(500)
    i = pg.evaluate("ui.dados.registros[0].id"); pg.evaluate("id=>ui.abrir(id)", i); pg.wait_for_timeout(2500)
    pg.screenshot(path=OUT + "painel.png"); print("painel")
