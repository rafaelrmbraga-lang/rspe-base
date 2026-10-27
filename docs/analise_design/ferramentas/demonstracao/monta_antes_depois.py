"""PDF antes × depois da 7.15.0 (programa real, base fictícia)."""
import os, io, base64
from PIL import Image
from playwright.sync_api import sync_playwright
S = "/tmp/claude-0/-home-user-rspe-base/883108c0-aece-5660-92ba-781fc4fe86e8/scratchpad"; R = S + "/real"; DEMO = S + "/demo"
OUT = "/home/user/rspe-base/docs/analise_design/APTO_7.15_antes_depois.pdf"
def img(p, larg=1300):
    im = Image.open(p).convert("RGB")
    if im.width > larg: im = im.resize((larg, round(im.height * larg / im.width)), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "JPEG", quality=78, optimize=True); return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
f64 = lambda n: base64.b64encode(open(os.path.join(DEMO, n + ".woff2"), "rb").read()).decode()
PARES = [("Progressão", "prog"), ("Indulto e comutação", "ind"), ("Prescrição", "presc"), ("Prescrição: detalhe do crime", "presc_aberto"),
         ("Ficha disciplinar", "fd"), ("Auditoria", "aud"), ("Extinção", "ext"), ("Geral", "geral"), ("Painel do assistido", "painel"), ("Legenda e método", "legenda")]
EST = [("Importar ▾", "importar_menu"), ("Combinar filtros", "filtros"), ("Importando", "importando"), ("Resumo da importação", "resumo"),
       ("Aviso com Desfazer", "aviso_ok"), ("Aviso de erro (fica até fechar)", "aviso_erro"), ("Busca sem resultado", "vazio"), ("Menu expandido em notebook", "menu_trocado")]
css = f"""@font-face{{font-family:S;font-weight:400;src:url(data:font/woff2;base64,{f64('inter-latin-400-normal')})}}@font-face{{font-family:S;font-weight:700;src:url(data:font/woff2;base64,{f64('inter-latin-700-normal')})}}
@page{{size:A4 landscape;margin:11mm 13mm 12mm}}*{{box-sizing:border-box}}body{{margin:0;font:9.6pt/1.45 S,sans-serif;color:#1C211E}}
.pg{{height:186mm;break-after:page;display:flex;flex-direction:column;overflow:hidden}}.pg:last-child{{break-after:auto}}
.k{{font-size:9pt;font-weight:700;color:#1D5A3B}}h1{{font:700 24pt S;margin:4pt 0}}h2{{font:700 14pt S;margin:2pt 0 6pt}}
.par{{display:grid;grid-template-columns:1fr 1fr;gap:5mm;flex:1;min-height:0}}.par figure,.g4 figure{{margin:0;min-width:0}}.par img,.g4 img{{width:100%;display:block;border:.7pt solid #C9CEC8;border-radius:3pt}}
figcaption{{font-weight:700;font-size:9pt;margin-bottom:2pt}}.a figcaption{{color:#7A3B36}}.d figcaption{{color:#1D5A3B}}
.g4{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:3mm 6mm;max-width:238mm;margin:0 auto}}.g4 figcaption{{margin:1pt 0 0}}
.um{{margin:4pt auto 0;max-width:262mm}}.um img{{width:100%;max-height:172mm;object-fit:contain;object-position:left top;display:block;border:.7pt solid #C9CEC8;border-radius:3pt}}.um figcaption{{font-size:11pt}}
.capa{{justify-content:center}}.capa p{{max-width:225mm;font-size:12pt;color:#2E3531}}"""
pg = [f'''<div class="pg capa"><div class="k">APTO 7.15.0</div><h1>Antes e depois: a linha E aplicada ao programa</h1>
<p>Telas do programa real (a mesma classe Api do APTO), com a base fictícia de 144 casos (“Simulado Caso NNN”), em monitor (1440 × 860, menu expandido) e em notebook (1280 × 680, menu recolhido). Nenhuma regra, cálculo ou texto jurídico mudou; nenhuma função saiu da tela. Os 81 testes de regressão passam.</p></div>''']
for tam, ant, dep in [("Monitor (1440 × 860)", "antes_1440", "fim_1440"), ("Notebook (1280 × 680)", "antes_1280", "fim_1280")]:
    for t, n in PARES:
        for rot, cls, pasta in [("Antes (7.14.7)", "a", ant), ("Depois (7.15.0)", "d", dep)]:
            pg.append(f'<div class="pg"><div class="k">{tam} · {t}</div><figure class="um {cls}"><figcaption>{rot}</figcaption><img src="{img(f"{R}/{pasta}/{n}.png", 1700)}"></figure></div>')
for k in range(0, len(EST), 4):
    cel = "".join(f'<figure><img src="{img(f"{R}/fim_e1280/{n}.png", 1100)}"><figcaption>{t}</figcaption></figure>' for t, n in EST[k:k + 4])
    pg.append(f'<div class="pg"><div class="k">Notebook (1280 × 680) · novidades</div><div class="g4">{cel}</div></div>')
html = f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><style>{css}</style></head><body>{''.join(pg)}</body></html>"
tmp = S + "/aprov/antes_depois.html"; open(tmp, "w", encoding="utf-8").write(html)
rod = '<div style="font:7pt Arial;color:#5F6762;width:100%;padding:0 13mm;display:flex;justify-content:space-between"><span>APTO 7.15.0 · antes e depois · dados fictícios</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>'
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium"); q = b.new_page(); q.goto("file://" + tmp); q.wait_for_timeout(600)
    q.pdf(path=OUT, format="A4", landscape=True, print_background=True, display_header_footer=True, header_template="<div></div>", footer_template=rod, margin={"top": "11mm", "bottom": "12mm", "left": "13mm", "right": "13mm"}); b.close()
print(OUT, os.path.getsize(OUT) // 1024, "KB")
