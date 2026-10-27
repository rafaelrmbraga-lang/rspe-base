import sys, ponte, json
S = "/tmp/claude-0/-home-user-rspe-base/883108c0-aece-5660-92ba-781fc4fe86e8/scratchpad"
W, H = map(int, sys.argv[1].split("x")); JS = sys.argv[2]; abas = sys.argv[3].split(",")
api, jan = ponte.criar(S + "/bases2/Comarca_Ficticia.sqlite")
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium"); pg = b.new_page(viewport={"width": W, "height": H})
    pg.on("pageerror", lambda e: print("ERRO", e))
    ponte.abrir(pg, api, jan); pg.wait_for_function("document.querySelector('tbody tr')", timeout=120000); pg.wait_for_timeout(500)
    for a in abas:
        pg.evaluate("id=>ui.irAba(id)", a); pg.wait_for_timeout(700)
        print(a, json.dumps(pg.evaluate(JS), ensure_ascii=False))
    b.close()
