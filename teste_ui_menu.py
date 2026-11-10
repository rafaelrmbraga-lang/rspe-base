"""Menu lateral recolhido (7.16.2): faixa de ícones com balão escuro (nome, número e atalho) ao passar o mouse, bolinha na aba com
pendência e atalhos Alt+1 ... Alt+0. O menu expandido (com os nomes) continua. Abre o ui.html no Chromium com uma lista fictícia.
Rodar: python teste_ui_menu.py"""
import os
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ok: (sem Playwright neste computador; teste não executado)")
    sys.exit(0)
falhas = []
with sync_playwright() as p:
    try:
        b = p.chromium.launch()
    except Exception:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page(viewport={"width": 1300, "height": 800})
    pg.goto("file://" + os.path.join(DIR, "ui.html"))
    pg.wait_for_timeout(300)
    pg.evaluate("""ui.dados={abas:[{id:'geral',titulo:'Geral'},{id:'prog',titulo:'Progressão',cor:true},{id:'liv',titulo:'Livramento'}],registros:[]};
      ui.ABAS_EXTRA=ui.ABAS_EXTRA||[]; ui.contaCor=()=>7; ui.qdAlertas=()=>0; ui.aba='geral';
      localStorage.setItem('apto_menu','recolhido'); ui.renderNav([])""")
    if not pg.evaluate("document.body.classList.contains('menu-recolhido')"):
        falhas.append("menu não recolheu")
    bt = pg.locator("#tabs .tab[data-nome='Progressão']")
    if bt.get_attribute("title"):
        falhas.append("recolhido não deve ter o title nativo (o balão substitui)")
    bt.hover()
    pg.wait_for_timeout(150)
    t = pg.evaluate("(document.getElementById('navTip')||{}).textContent||''")
    if "Progressão" not in t or "7" not in t or "Alt 2" not in t:
        falhas.append("balão: %r" % t)
    w = pg.evaluate("document.querySelector('#tabs .tab[data-nome=\"Progressão\"]').getBoundingClientRect().width")
    if abs(w - 40) > 1:
        falhas.append("ícone com %s px (esperado 40)" % w)
    pg.evaluate("ui.irAba=id=>{ui._foi=id}")
    pg.keyboard.press("Alt+3")
    if pg.evaluate("ui._foi") != "liv":
        falhas.append("Alt+3 não abriu Livramento")
    pg.evaluate("localStorage.setItem('apto_menu','aberto'); ui.renderNav([])")
    if pg.evaluate("document.body.classList.contains('menu-recolhido')") or not pg.locator("#tabs .tab .tnm").first.is_visible():
        falhas.append("menu expandido (com nomes) não voltou")
    b.close()
if falhas:
    print("FALHA: " + "; ".join(falhas))
    sys.exit(1)
print("ok: menu recolhido com balão (nome, número, Alt 2), ícone de 40 px, Alt+3 abre a aba, expansão mantida")
