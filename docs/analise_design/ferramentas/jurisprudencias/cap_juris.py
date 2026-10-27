import os, json, base64, ponte
S = "/tmp/claude-0/-home-user-rspe-base/883108c0-aece-5660-92ba-781fc4fe86e8/scratchpad"; OUT = S + "/juris/prints"; os.makedirs(OUT, exist_ok=True)
D = json.load(open(S + "/juris/teses_anon.json")); REAL = D.pop("_contagem_real")
JS = open(S + "/juris/juris_props.js", encoding="utf-8").read()
b64 = lambda f: base64.b64encode(open(S + "/demo/" + f, "rb").read()).decode()
FONTES = {"inter": ("Inter", "inter-latin-%d-normal.woff2"), "plex": ("IBM Plex Sans", "ibm-plex-sans-latin-%d-normal.woff2"), "ss3": ("Source Sans 3", "source-sans-3-latin-%d-normal.woff2")}
def css_fonte(k):
    if k == "arial": return ""
    n, f = FONTES[k]
    ff = "".join(f'@font-face{{font-family:"{n}";font-weight:{w};src:url(data:font/woff2;base64,{b64(f % w)}) format("woff2")}}' for w in (400, 500, 600, 700))
    return ff + f'body,button,input,select,textarea{{font-family:"{n}",Arial,sans-serif!important}}.brand b{{font-family:Cinzel,Georgia,serif!important}}'
api, jan = ponte.criar(S + "/bases2/Comarca_Ficticia.sqlite")
from playwright.sync_api import sync_playwright
erros = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for W, H in [(1440, 860), (1280, 680)]:
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1.5); pg.on("pageerror", lambda e: erros.append(str(e)))
        ponte.abrir(pg, api, jan); pg.wait_for_function("document.querySelector('tbody tr')", timeout=120000); pg.wait_for_timeout(500)
        pg.evaluate("d=>{ui._teses=d; ui._tesIdx=null;}", D); pg.wait_for_timeout(100)
        def shot(n): pg.evaluate("document.getElementById('toast').classList.remove('on')"); pg.wait_for_timeout(250); pg.screenshot(path=f"{OUT}/{n}_{W}.png")
        pg.evaluate("ui.irAba('teses')"); pg.wait_for_timeout(800); shot("hoje")
        # fontes: Progressão e Jurisprudências de hoje em cada fonte
        for k in ["arial", "inter", "plex", "ss3"]:
            pg.evaluate("c=>{let e=document.getElementById('fx'); if(!e){e=document.createElement('style');e.id='fx';document.head.appendChild(e);} e.textContent=c;}", css_fonte(k))
            pg.evaluate("ui.irAba('prog')"); pg.wait_for_timeout(500); shot("fonte_" + k + "_prog")
        pg.evaluate("c=>{document.getElementById('fx').textContent=c}", css_fonte("ss3"))
        pg.evaluate("r=>{window.JREAL=r}", REAL); pg.evaluate(JS); pg.wait_for_timeout(100)
        for v, extra in [("A", "window.JQ='';window.JSEL=0"), ("A2", "window.JQ='detração';window.JSEL=0"), ("B", "window.JQ=''"), ("C", "window.JQ='';window.JSEL=1")]:
            pg.evaluate(f"window.JV='{v[0]}';{extra};ui.irAba('teses')"); pg.wait_for_timeout(500); shot("prop" + v)
        pg.close()
    b.close()
print("erros", erros[:3])
