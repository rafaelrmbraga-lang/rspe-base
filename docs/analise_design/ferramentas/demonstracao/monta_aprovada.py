"""PDF da proposta aprovada (linha E com os ajustes) e das decisões, sugestão a sugestão. Dados fictícios."""
import os, io, base64
from PIL import Image
from playwright.sync_api import sync_playwright
DEMO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "demo"); TT = os.path.join(DEMO, "telas_todas")
OUT = "/home/user/rspe-base/docs/analise_design/APTO_linha_E_aprovada.pdf"
def img(n, larg=1500):
    im = Image.open(os.path.join(TT, n + ".png")).convert("RGB")
    if im.width > larg: im = im.resize((larg, round(im.height * larg / im.width)), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "JPEG", quality=76, optimize=True); return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
f64 = lambda n: base64.b64encode(open(os.path.join(DEMO, n + ".woff2"), "rb").read()).decode()
DEC = [
 ("Linha gráfica", "E · menu lateral que recolhe e expande (Fluent 2, visual do Windows 11)", "Aprovada"),
 ("Importar", "Um botão só, “Importar ▾”: Arquivos PDF… · Uma pasta inteira…", "Ajuste pedido"),
 ("Complemento “sem pedido no RSPE - requerer”", "Sai da coluna Situação; ficam os demais complementos do programa (ex.: “verificar criminológico, indeferimento ou falta”)", "Ajuste pedido"),
 ("Ações da linha", "Ícones de hoje (ficha, Quadro, abrir), mais escuros, com dica; ficha verde quando importada", "Ajuste pedido"),
 ("Filtro", "“Combinar filtros ▾”: caixas de marcar em 4 grupos (Situação, Pedido, Benefícios a conferir, Conferência), combináveis", "Ajuste pedido"),
 ("1 · Estrutura igual em todas as abas", "Título, contadores, filtros e ordem, lista, detalhe", "Aprovada"),
 ("2 · Cabeçalho em uma faixa", "Filtro ao lado da ordem da lista", "Aprovada"),
 ("3 · Abas agrupadas por tarefa", "Geral · Prazos · Decretos · Conferência · Panorama e ferramentas; nomes por extenso", "Aprovada"),
 ("4 · Contadores", "Formato 2: número maior, traço de cor, rótulo ao lado. “Até 60 dias” sozinho; “A verificar” em contador e grupo próprios, na cor do RSPE antigo", "Aprovada com ajuste"),
 ("5 · Ordem inicial", "Por situação (vencidos primeiro); alfabética a um clique", "Aprovada"),
 ("6 · Situação curta + complemento embaixo", "Complemento em letra menor, cortado com “…”; texto inteiro na dica e no painel", "Aprovada"),
 ("7 · Caixa do pedido", "Só a caixa, como hoje; título “Pedido” na coluna", "Aprovada (só a caixa)"),
 ("8 · Uma cor, um significado", "Verde só para “em ordem / cabe”; “Até 90 dias” em azul-acinzentado", "Aprovada"),
 ("9 · Legenda por aba, em tabela", "Método completo a um clique", "Aprovada"),
 ("10 · Painel do assistido", "Só o essencial; na linha Indulto, só os decretos cabíveis, como hoje", "Aprovada com ajuste"),
 ("11 · Detalhe da Prescrição em passos", "Datas numa linha, 3 passos, Ver cálculo · Editar dados · Abrir ficha completa", "Aprovada"),
 ("12 · Avisos", "Sucesso discreto com “Desfazer”; erro fica até fechar", "Aprovada"),
 ("13 · Importação", "Progresso à vista com “Parar”; resumo com 4 totais e falhas primeiro", "Aprovada"),
 ("14 · Lista vazia que orienta", "Diz o que foi buscado e oferece “Limpar busca”", "Aprovada"),
 ("15 · Notebooks", "Modo compacto abaixo de 1400 px; menu começa recolhido em notebook, expandido em tela larga; vale a última escolha do usuário", "Aprovada"),
]
ABAS = [('geral','Geral'),('prog','Progressão'),('liv','Livramento'),('ind','Indulto e comutação'),('presc','Prescrição'),('ext','Extinção'),('fd','Ficha disciplinar'),('aud','Auditoria'),('base','Dados da base'),('geo','Dados prisionais'),('teses','Jurisprudências'),('quadro','Quadro do usuário'),('painel','Painel do assistido')]
EXTRA = [('tEx_imp','Importar ▾'),('tEx_filtro','Combinar filtros'),('tEx_dica','Menu recolhido: nome ao parar o mouse'),('tEx_sobre','Menu aberto por cima da lista'),('tEx_presc','Detalhe da Prescrição'),('tEx_legenda','Legenda da aba'),('tEx_avisos','Avisos'),('tEx_importando','Importando'),('tEx_importacao','Resumo da importação'),('tEx_vazio','Busca sem resultado')]
css = f"""@font-face{{font-family:S;font-weight:400;src:url(data:font/woff2;base64,{f64('inter-latin-400-normal')})}}@font-face{{font-family:S;font-weight:700;src:url(data:font/woff2;base64,{f64('inter-latin-700-normal')})}}
@page{{size:A4 landscape;margin:11mm 13mm 12mm}}*{{box-sizing:border-box}}body{{margin:0;font:9.6pt/1.45 S,sans-serif;color:#1C211E}}
.pg{{height:186mm;break-after:page;display:flex;flex-direction:column;overflow:hidden}}.pg:last-child{{break-after:auto}}
.k{{font-size:9pt;font-weight:700;color:#1D5A3B}}h1{{font:700 24pt S;margin:4pt 0}}h2{{font:700 15pt S;margin:2pt 0 8pt}}
table{{width:100%;border-collapse:collapse;font-size:8.8pt}}th{{text-align:left;border-bottom:1pt solid #1C211E;padding:3pt 5pt}}td{{padding:2.6pt 5pt;border-bottom:.5pt solid #E1E4DF;vertical-align:top}}td.s{{white-space:nowrap;color:#1D5A3B;font-weight:700}}
.g4{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:3mm 6mm;max-width:238mm;margin:0 auto}}figure{{margin:0;min-width:0}}figure img{{width:100%;display:block;border:.7pt solid #C9CEC8;border-radius:3pt}}figcaption{{font-weight:700;font-size:9pt;margin-top:1pt}}
.capa{{justify-content:center}}.capa p{{max-width:220mm;font-size:12pt;color:#2E3531}}"""
pg = ['<div class="pg capa"><div class="k">APTO · análise de design</div><h1>Linha E aprovada, com os ajustes</h1><p>Menu lateral que recolhe e expande, no visual do Windows 11, com as decisões tomadas sugestão a sugestão. Nenhuma regra, cálculo ou texto jurídico muda; nenhuma função sai da tela. Dados fictícios (“Simulado Caso NNN”).</p></div>']
pg.append('<div class="pg"><div class="k">Decisões</div><h2>O que foi decidido</h2><table><tr><th>Item</th><th>Como fica</th><th>Decisão</th></tr>' + "".join(f"<tr><td><b>{a}</b></td><td>{b}</td><td class='s'>{c}</td></tr>" for a, b, c in DEC) + '</table></div>')
for pref, tit in [('tEa', 'Monitor (1440 × 860), menu expandido'), ('tEr', 'Notebook (1280 × 680, Full HD a 150 %), menu recolhido')]:
    for k in range(0, 13, 4):
        cel = "".join(f'<figure><img src="{img(pref + "_" + a, 1100)}"><figcaption>{r}</figcaption></figure>' for a, r in ABAS[k:k + 4])
        pg.append(f'<div class="pg"><div class="k">Todas as abas · {tit} ({k // 4 + 1}/4)</div><div class="g4">{cel}</div></div>')
for k in range(0, len(EXTRA), 4):
    cel = "".join(f'<figure><img src="{img(a, 1100)}"><figcaption>{r}</figcaption></figure>' for a, r in EXTRA[k:k + 4])
    pg.append(f'<div class="pg"><div class="k">Detalhes · notebook (1280 × 680)</div><div class="g4">{cel}</div></div>')
html = f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><style>{css}</style></head><body>{''.join(pg)}</body></html>"
tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aprovada.html"); open(tmp, "w", encoding="utf-8").write(html)
rod = '<div style="font:7pt Arial;color:#5F6762;width:100%;padding:0 13mm;display:flex;justify-content:space-between"><span>APTO · Linha E aprovada · dados fictícios</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>'
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium"); q = b.new_page(); q.goto("file://" + tmp); q.wait_for_timeout(600)
    q.pdf(path=OUT, format="A4", landscape=True, print_background=True, display_header_footer=True, header_template="<div></div>", footer_template=rod, margin={"top": "11mm", "bottom": "12mm", "left": "13mm", "right": "13mm"}); b.close()
print(OUT, os.path.getsize(OUT) // 1024, "KB")
