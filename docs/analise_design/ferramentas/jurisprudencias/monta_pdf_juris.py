"""PDF: fonte do programa e propostas para a aba Jurisprudências (dados anonimizados)."""
import os, io, base64
from PIL import Image
from playwright.sync_api import sync_playwright
S = "/tmp/claude-0/-home-user-rspe-base/883108c0-aece-5660-92ba-781fc4fe86e8/scratchpad"; P = S + "/juris/prints"; DEMO = S + "/demo"
OUT = "/home/user/rspe-base/docs/analise_design/APTO_jurisprudencias_e_fonte.pdf"
def img(n, larg=1700):
    im = Image.open(os.path.join(P, n + ".png")).convert("RGB")
    if im.width > larg: im = im.resize((larg, round(im.height * larg / im.width)), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "JPEG", quality=80, optimize=True); return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
f64 = lambda n: base64.b64encode(open(os.path.join(DEMO, n + ".woff2"), "rb").read()).decode()
css = f"""@font-face{{font-family:S;font-weight:400;src:url(data:font/woff2;base64,{f64('source-sans-3-latin-400-normal')})}}@font-face{{font-family:S;font-weight:600;src:url(data:font/woff2;base64,{f64('source-sans-3-latin-600-normal')})}}@font-face{{font-family:S;font-weight:700;src:url(data:font/woff2;base64,{f64('source-sans-3-latin-700-normal')})}}
@page{{size:A4 landscape;margin:11mm 13mm 12mm}}*{{box-sizing:border-box}}body{{margin:0;font:10.5pt/1.45 S,sans-serif;color:#1C211E}}
.pg{{height:186mm;break-after:page;display:flex;flex-direction:column;overflow:hidden}}.pg:last-child{{break-after:auto}}
.k{{font-size:9.5pt;font-weight:700;color:#1D5A3B}}h1{{font:700 26pt S;margin:4pt 0}}h2{{font:700 16pt S;margin:1pt 0 4pt}}
.lead{{font-size:11pt;color:#2E3531;max-width:250mm;margin:0 0 6pt}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:4mm 7mm}}figure{{margin:0;min-width:0}}figure img{{width:100%;display:block;border:.7pt solid #C9CEC8;border-radius:3pt}}
figcaption{{font-size:9.5pt;color:#4A514C;margin-top:2pt}}figcaption b{{color:#1C211E;font-size:10.5pt}}
.lado{{display:grid;grid-template-columns:minmax(0,1fr) 68mm;gap:7mm;flex:1;min-height:0}}.lado img{{width:100%;max-height:168mm;object-fit:contain;object-position:left top;border:.7pt solid #C9CEC8;border-radius:3pt}}
ul{{margin:4pt 0 0;padding-left:13pt}}li{{margin:0 0 4pt}}.rec{{background:#EEF4F0;border-radius:4pt;padding:7pt 10pt;margin-top:6pt}}
table{{border-collapse:collapse;width:100%;font-size:10pt;margin-top:4pt}}th{{text-align:left;border-bottom:1pt solid #1C211E;padding:3pt 5pt}}td{{padding:3pt 5pt;border-bottom:.5pt solid #E1E4DF;vertical-align:top}}
.capa{{justify-content:center}}"""
pg = []
pg.append("""<div class="pg capa"><div class="k">APTO · sugestões</div><h1>Fonte do programa e aba Jurisprudências</h1>
<p class="lead">Duas coisas deixam a tela com ar rústico: a letra Arial, imposta a todo o programa, e a aba Jurisprudências, que mostra cada decisão como um cartão pesado (barra colorida, etiquetas de várias cores, palavras-chave em caixinhas, três botões grandes), com só três decisões por tela.</p>
<p class="lead">Este documento mostra quatro letras lado a lado e três formas de reorganizar a aba, sem tirar nenhuma informação nem botão. As decisões são as da base do programa, com número do processo, relator, comarca e nomes citados nas ementas trocados por fictícios.</p></div>""")
# fonte
pg.append(f"""<div class="pg"><div class="k">1 · A fonte</div><h2>A mesma tela em quatro letras</h2>
<p class="lead">Hoje o programa força a Arial (a do SEEU e do PJe) em tudo. Ela foi desenhada para impressão nos anos 1980: letras largas, espaçamento irregular nos números e acentos pesados. Isso cansa a leitura de tabelas longas e dá o ar de sistema antigo.</p>
<div class="g2"><figure><img src="{img('crop_arial',1100)}"><figcaption><b>Arial</b> · hoje</figcaption></figure><figure><img src="{img('crop_ss3',1100)}"><figcaption><b>Source Sans 3</b> · recomendada</figcaption></figure>
<figure><img src="{img('crop_inter',1100)}"><figcaption><b>Inter</b></figcaption></figure><figure><img src="{img('crop_plex',1100)}"><figcaption><b>IBM Plex Sans</b></figcaption></figure></div></div>""")
pg.append("""<div class="pg"><div class="k">1 · A fonte</div><h2>Comparação e recomendação</h2>
<table><tr><th>Letra</th><th>Como é</th><th>Na tabela</th><th>Custo no programa</th></tr>
<tr><td><b>Arial</b> (hoje)</td><td>Neutra, antiga, letras largas; números com espaços irregulares</td><td>Ocupa mais largura que a Source Sans 3</td><td>Nenhum (já vem no Windows)</td></tr>
<tr><td><b>Source Sans 3</b></td><td>Humanista, clara e sóbria; feita pela Adobe para telas; muito usada em sites de governo; acentos bem desenhados</td><td>A mais estreita: cabe mais texto por linha, bom para notebook</td><td>Cerca de 80 KB embutidos no ui.html, funciona sem internet (licença livre, OFL)</td></tr>
<tr><td><b>Inter</b></td><td>Moderna e muito legível em tamanho pequeno</td><td>A mais larga: mais quebras de linha</td><td>Cerca de 95 KB, OFL. É a letra padrão de muitos aplicativos atuais e de telas geradas por IA, justamente o ar que se quer evitar</td></tr>
<tr><td><b>IBM Plex Sans</b></td><td>Técnica, com personalidade de empresa de tecnologia</td><td>Largura parecida com a Arial</td><td>Cerca of 90 KB, OFL</td></tr>
<tr><td><b>Segoe UI</b></td><td>A letra do próprio Windows 11, na qual a linha E foi pensada</td><td>Parecida com a Arial em largura</td><td>Nenhum: já vem no Windows. Não dá para mostrar aqui (o servidor não tem a letra)</td></tr></table>
<div class="rec"><b>Recomendação: Source Sans 3</b>, embutida no ui.html (offline, arquivo único). É sóbria e institucional, sem o ar genérico de aplicativo, e por ser mais estreita deixa as tabelas mais arejadas no notebook. Os títulos usam a mesma família em peso maior; o nome APTO continua em Cinzel. Se preferirem não embutir nada, a segunda opção é a Segoe UI, a do Windows.</div></div>""".replace("Cerca of", "Cerca de"))
# juris hoje
pg.append(f"""<div class="pg"><div class="k">2 · Jurisprudências · hoje</div><h2>Onde está o peso</h2><div class="lado"><img src="{img('hoje_1440')}"><div><ul>
<li>Cada decisão é um cartão grande, com barra lateral colorida: <b>três por tela</b>.</li><li>Temas em etiquetas de cores diferentes (vermelho, rosa, verde): competem com o resultado e com a tese.</li>
<li>Palavras-chave em dezenas de caixinhas cinza.</li><li>Ícones antes de cada dado (câmara, relator, processo, comarca).</li><li>Três botões grandes repetidos em toda decisão.</li>
<li>Barra de temas com bolinhas coloridas; filtros de tribunal e decisão espremidos em letra pequena.</li></ul>
<p style="font-size:9.5pt;color:#5F6762">Tela do programa com a amostra anonimizada (por isso os contadores mostram 49).</p></div></div></div>""")
PROP = [("A", "Lista e leitura lado a lado", "propA_1440", ["Lista enxuta no meio: tema, data, a tese em duas linhas e tribunal · câmara · resultado. <b>Sete a oito decisões por tela.</b>", "Ao clicar, a decisão abre à direita: tese, os três botões, um quadro com resultado, tribunal, relator, processo e datas, as palavras-chave em texto corrido e a ementa inteira, em parágrafos.", "Não precisa “Ler ementa completa”: a leitura já está aberta.", "Barra de temas neutra (sem bolinhas), igual ao menu lateral; filtros de tribunal e decisão como botões com a contagem."], "uso diário: procurar, ler e copiar sem rolar a página"),
        ("A", "Lista e leitura · com busca", "propA2_1440", ["A palavra buscada fica realçada na lista e na ementa.", "A busca e o tema escolhido aparecem como etiquetas com ✕ ao lado da contagem.", "A ordem (mais recentes / mais antigas) fica junto da contagem."], ""),
        ("B", "Cartões leves", "propB_1440", ["A mesma lista de hoje, uma decisão embaixo da outra, com o peso tirado: sem barra colorida, temas em texto cinza, resultado num selo discreto.", "Tese em destaque; tribunal, câmara, relator, processo e comarca numa linha só, sem ícones.", "Palavras-chave em texto corrido; ementa em três linhas; botões alinhados à direita.", "Cabem duas decisões e meia por tela."], "quem gosta da tela de hoje e quer só limpá-la"),
        ("C", "Tabela de pesquisa", "propC_1440", ["Cada decisão numa linha: tese (com os temas embaixo), tribunal e câmara, julgamento e resultado.", "Clicar abre a ementa embaixo da linha, com relator, processo, palavras-chave e os três botões.", "Lembra a pesquisa de jurisprudência dos tribunais; cabem cinco a seis decisões fechadas por tela."], "pesquisa rápida por tese, comparando várias decisões")]
for v, t, n, bul, ind in PROP:
    pg.append(f"""<div class="pg"><div class="k">2 · Jurisprudências · proposta {v}</div><h2>{t}</h2><div class="lado"><img src="{img(n)}"><div><ul>{''.join(f'<li>{b}</li>' for b in bul)}</ul>{f'<div class="rec"><b>Indicada para</b> {ind}.</div>' if ind else ''}</div></div></div>""")
pg.append(f"""<div class="pg"><div class="k">2 · Jurisprudências · notebook (1280 × 680)</div><h2>Propostas A e B em tela de notebook, com o menu recolhido</h2><div class="g2"><figure><img src="{img('propA_1280',1200)}"><figcaption><b>A</b> · lista e leitura</figcaption></figure><figure><img src="{img('propB_1280',1200)}"><figcaption><b>B</b> · cartões leves</figcaption></figure></div>
<div class="rec" style="margin-top:8pt"><b>Recomendação: proposta A</b>, com a Source Sans 3. Mostra mais decisões por tela e deixa a ementa inteira legível sem abrir nada. Nenhuma informação ou botão de hoje sai: tema, tribunal, câmara, relator, processo, comarca, datas, resultado, palavras-chave, ementa, Inteiro teor, Copiar referência e Copiar ementa.</div></div>""")
html = f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><style>{css}</style></head><body>{''.join(pg)}</body></html>"
tmp = S + "/juris/juris.html"; open(tmp, "w", encoding="utf-8").write(html)
rod = '<div style="font:7pt Arial;color:#5F6762;width:100%;padding:0 13mm;display:flex;justify-content:space-between"><span>APTO · fonte e Jurisprudências · decisões com dados anonimizados</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>'
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium"); q = b.new_page(); q.goto("file://" + tmp); q.wait_for_timeout(600)
    q.pdf(path=OUT, format="A4", landscape=True, print_background=True, display_header_footer=True, header_template="<div></div>", footer_template=rod, margin={"top": "11mm", "bottom": "12mm", "left": "13mm", "right": "13mm"}); b.close()
print(OUT, os.path.getsize(OUT) // 1024, "KB")
