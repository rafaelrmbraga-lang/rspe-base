"""Captura o ui.html REAL (Api real, base fictícia). uso: cap_real.py <pasta_saida> <WxH> [abas]"""
import sys, os, ponte
S = "/tmp/claude-0/-home-user-rspe-base/883108c0-aece-5660-92ba-781fc4fe86e8/scratchpad"
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True); W, H = map(int, sys.argv[2].split("x"))
ABAS = sys.argv[3].split(",") if len(sys.argv) > 3 else ['geral','prog','liv','ind','presc','ext','fd','aud','base','geo','teses','quadro']
api, jan = ponte.criar(S + "/bases2/Comarca_Ficticia.sqlite")
from playwright.sync_api import sync_playwright
erros = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
    pg.on("pageerror", lambda e: erros.append(str(e)))
    ponte.abrir(pg, api, jan); pg.wait_for_function("document.querySelector('tbody tr')", timeout=120000); pg.wait_for_timeout(800)
    for a in ABAS:
        pg.evaluate("id=>ui.irAba(id)", a); pg.wait_for_timeout(1500)
        pg.evaluate("document.getElementById('toast').classList.remove('on')"); pg.wait_for_timeout(200)
        pg.screenshot(path=f"{OUT}/{a}.png")
    pg.evaluate("ui.irAba('geral')"); pg.wait_for_timeout(400)
    i = pg.evaluate("ui.dados.registros[0].id"); pg.evaluate("id=>ui.abrir(id)", i); pg.wait_for_timeout(2000)
    pg.screenshot(path=f"{OUT}/painel.png"); pg.evaluate("ui.fecharDrawer()"); pg.wait_for_timeout(300)
    pg.evaluate("ui.irAba('presc')"); pg.wait_for_timeout(800)
    pid = pg.evaluate("(ui.dados.registros.find(r=>r.presc_ppe_cor==='vermelho')||{}).id")
    if pid: pg.evaluate("id=>ui.expandir(id)", pid); pg.wait_for_timeout(1500); pg.evaluate("document.querySelector('tr.exp').scrollIntoView({block:'start'})"); pg.wait_for_timeout(200); pg.screenshot(path=f"{OUT}/presc_aberto.png")
    pg.evaluate("ui.irAba('prog')"); pg.wait_for_timeout(500); pg.evaluate("ui.ajuda()"); pg.wait_for_timeout(800); pg.screenshot(path=f"{OUT}/legenda.png")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    b.close()
print("erros JS:", erros[:5])
