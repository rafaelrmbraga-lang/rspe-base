"""Avisos do Python para a tela (7.16.2): o Python chama "window.ui && ui.geoProgresso(...)" (andamento dos dados prisionais),
ui.carregando, ui.trabalho e a nova tentativa automática. Com "const ui" sem "window.ui = ui", window.ui não existia e todos
esses avisos se perdiam (o botão ficava em "Atualizando… 0%" até o fim). Abre o ui.html no Chromium e manda os avisos exatamente
como o rspe_app os monta. Rodar: python teste_ui_avisos.py"""
import os
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
falhas = []
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ok: (sem Playwright neste computador; teste não executado)")
    sys.exit(0)
with sync_playwright() as p:
    try:
        b = p.chromium.launch()
    except Exception:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.goto("file://" + os.path.join(DIR, "ui.html"))
    pg.wait_for_timeout(300)
    if not pg.evaluate("typeof window.ui === 'object' && window.ui !== null"):
        falhas.append("window.ui não existe na tela")
    else:
        pg.evaluate("ui._geoBaixando=true; ui.aba='geo'; document.body.insertAdjacentHTML('beforeend','<button id=\"geoBt\">x</button>')")
        pg.evaluate('window.ui && ui.geoProgresso && ui.geoProgresso(37, "relatórios: 10 de 560")')
        t = pg.evaluate("document.getElementById('geoBt').textContent")
        if "37%" not in t:
            falhas.append("andamento não chegou ao botão: %r" % t)
        if pg.evaluate("ui._geoPct") != 37:
            falhas.append("porcentagem não guardada")
    b.close()
if falhas:
    print("FALHA: " + "; ".join(falhas))
    sys.exit(1)
print("ok: avisos do Python chegam à tela (window.ui; andamento dos dados prisionais em 37%)")
