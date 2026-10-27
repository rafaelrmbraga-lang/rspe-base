"""Junta a análise de design (docs/analise_design) num PDF único para circular. Dados fictícios."""
import os, re, io, base64, markdown
from PIL import Image
from playwright.sync_api import sync_playwright

R = "/home/user/rspe-base/docs/analise_design"
CAP = os.path.join(R, "capturas")
OUT = os.path.join(R, "APTO_analise_de_design.pdf")


def img(nome, larg=1500):
    """captura em JPEG reduzido, embutida (o PDF fica leve e autocontido)"""
    im = Image.open(os.path.join(CAP, nome)).convert("RGB")
    if im.width > larg:
        im = im.resize((larg, round(im.height * larg / im.width)), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "JPEG", quality=80, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def md(arq, tirar_titulo=True):
    t = open(os.path.join(R, arq), encoding="utf-8").read()
    if tirar_titulo:
        t = re.sub(r"^# .*\n", "", t, count=1)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", t)  # links viram texto (no papel não há para onde ir)
    h = markdown.markdown(t, extensions=["tables", "fenced_code", "sane_lists"])
    return h


def fig(nome, leg, larg=1500, cls=""):
    return f'<figure class="{cls}"><img src="{img(nome, larg)}"><figcaption>{leg} <span>· {nome}</span></figcaption></figure>'


PARES = [
    ("Aba Progressão: quem já atingiu o lapso e ainda não tem pedido", "app_aba_prog_1440.png", "depois_progressao_1440.png",
     "Hoje a lista vem em ordem alfabética, com a Situação espremida em 4 linhas. Na proposta, abre por urgência, com forma + cor + texto e o pedido como botão."),
    ("Windows em 150 % (notebook Full HD)", "app_prog_escala150_1280x680.png", "depois_progressao_escala150.png",
     "Hoje cabem 2,5 linhas da tabela. Na proposta, com cabeçalho numa faixa e abas agrupadas, cabem cerca de 7."),
    ("Aba Indulto e comutação: selos dos decretos", "app_aba_ind_1440.png", "depois_indulto_1440.png",
     "Hoje o resultado de cada decreto está só na cor, e 'não cabe' e 'impeditivo' quase não se distinguem. Na proposta, cada selo traz um símbolo (✓ ? ✕ ⊘ ★ –)."),
    ("Ficha do assistido: por que 'A verificar' e copiar a fundamentação", "app_ficha_assistido_topo.png", "depois_ficha_1440.png",
     "Hoje a linha 'Indulto' mostra só os cabíveis. Na proposta, o motivo aparece junto da linha, em passos, com 'Copiar fundamentação' ao lado (o 3º passo do protótipo é ilustrativo)."),
    ("Resumo da importação de 300 PDFs", "app_estado_importacao_concluida.png", "depois_importacao_1440.png",
     "Hoje falhas, leituras parciais e duplicados vêm misturados. Na proposta, 4 totais e grupos, com as falhas primeiro e o que fazer."),
]

GALERIA = [
    ("app_presc_linha_do_tempo.png", "APP-04 · a linha expandida da Prescrição estoura a largura da tabela"),
    ("app_aba_aud_1440.png", "APP-05 · na Auditoria o verde quer dizer 'em ordem'; na Progressão, 'vence em 90 dias'"),
    ("app_modal_ajuda.png", "APP-17 · Legenda e método: cores descritas por extenso, sem amostras"),
    ("app_modal_atendimentos.png", "APP-09 · modal sem véu, colado na tabela"),
    ("app_estado_importando_137_de_300.png", "APP-11 · progresso da importação só no canto do rodapé"),
    ("app_prog_1100x600.png", "APP-03 · janela no tamanho mínimo (1100×600)"),
    ("app_aba_fd_1440.png", "APP-15 e APP-24 · aba 'Ficha' (disciplinar) e seta desalinhada do nome"),
    ("app_modal_relatorios_pdf.png", "APP-20 · 'Remição com o nome dos assistidos' marcado por padrão"),
    ("pdf_negrito_perdido_zoom.png", "PDF-01 · o <b> do parágrafo sai em peso normal"),
    ("pdf_aba_p1_pb.png", "PDF-03 · PDF da aba impresso em tons de cinza: as cores de situação somem"),
    ("pdf_aba_prescricao_zoom.png", "PDF-05 · nº do processo quebrado no meio"),
    ("pdf_aba_indulto_p2.png", "PDF-04 · linha de um assistido partida entre páginas"),
    ("pdf_individual_p1.png", "PDF-02 · título de seção sozinho no pé da página"),
    ("pdf_geral_rosca_zoom.png", "PDF-08 · percentual branco sobre fatias claras"),
    ("excel_impressao_p5_colunas_separadas.png", "XLS-01 e XLS-02 · impressão sem ajuste; datas como texto"),
    ("extensao_popup_inicial_600px.png", "EXT-01 · o que cabe no popup de 600 px: a confirmação fica fora"),
    ("extensao_triagem_800px.png", "EXT-08 · Triagem a 800 px: texto quebrando letra a letra"),
    ("extensao_injetado_seeu_aviso_erro.png", "EXT-10 · aviso de erro no SEEU que some em 6 s"),
    ("conversor_convertendo_lento_vp9.png", "CONV-01 · '0x mais rápido que o tempo real'"),
    ("conversor_erro.png", "CONV-02 · erro bruto da ffmpeg"),
    ("identidade_ico_tamanhos.png", "ID-01 · ícone do programa em 16 a 48 px"),
    ("identidade_extensao_icones.png", "ID-01 · ícone da extensão: o selo claro, ilegível em 16 px"),
    ("peticao_progressao_semiaberto_p2.png", "DOC-03 · página em branco no fim da petição"),
]

CSS = """
@page{size:A4 landscape;margin:14mm 14mm 16mm}
*{box-sizing:border-box}
body{font:9.6pt/1.45 Arial,"Liberation Sans",sans-serif;color:#1E2226;margin:0}
h1{font-size:20pt;color:#153F2A;margin:0 0 8pt;padding-bottom:5pt;border-bottom:2pt solid #1D5A3B;break-after:avoid}
h2{font-size:13pt;color:#153F2A;margin:14pt 0 6pt;break-after:avoid}
h3{font-size:11pt;margin:10pt 0 4pt;break-after:avoid}
p{margin:0 0 6pt}
ul,ol{margin:0 0 6pt;padding-left:18pt}li{margin:1.5pt 0}
table{width:100%;border-collapse:collapse;margin:4pt 0 10pt;font-size:7.4pt;line-height:1.35}
th{background:#EEF1EF;text-align:left;border-bottom:1.2pt solid #1D5A3B;padding:3pt 4pt;vertical-align:bottom}
td{border-bottom:.5pt solid #CDD2D6;padding:3pt 4pt;vertical-align:top}
tr{break-inside:avoid}td:first-child{white-space:nowrap}
code{font:7.6pt Consolas,"Liberation Mono",monospace;background:#F1F3F2;padding:0 2pt;border-radius:2pt;overflow-wrap:anywhere}
pre{background:#F1F3F2;padding:6pt;font-size:8pt;white-space:pre-wrap}
.cap{break-after:page}
.sec{break-before:page}
.capa{height:170mm;display:flex;flex-direction:column;justify-content:center}
.capa .k{font-size:11pt;color:#5C636A;letter-spacing:1.5pt;text-transform:uppercase}
.capa h1{font-size:30pt;border:0;margin:6pt 0}
.capa .sub{font-size:13pt;color:#454B50;max-width:200mm}
.capa .meta{margin-top:18pt;font-size:9.5pt;color:#454B50;border-left:3pt solid #1D5A3B;padding-left:8pt}
.sum{columns:2;column-gap:14mm;font-size:10.5pt}.sum li{margin:3pt 0}
.par{display:grid;grid-template-columns:1fr 1fr;gap:6mm;align-items:start}
.par figure{margin:0}
.ad{break-before:page}.ad h2{margin-top:0}
figure{margin:0 0 6pt;break-inside:avoid}
figure img{width:100%;border:.6pt solid #CDD2D6;display:block}
figcaption{font-size:8.2pt;color:#454B50;margin-top:2pt}figcaption span{color:#7A8188}
.rot{font-weight:700;font-size:9pt;margin-bottom:2pt}
.gal{display:grid;grid-template-columns:1fr 1fr;gap:5mm 6mm}
.galp{break-before:page}.galp:first-child{break-before:auto}
.gal figure{margin:0}.gal figure img{height:66mm;width:auto;max-width:100%;object-fit:contain;object-position:left top}
.galp h1+.gal figure img{height:60mm}
.nota{font-size:8.5pt;color:#454B50;border-left:2pt solid #B9BFC5;padding-left:6pt}
"""

secoes = []
secoes.append(f"""<div class="capa cap">
<div class="k">Defensoria Pública de MS · execução penal</div>
<h1>APTO · Análise de design</h1>
<div class="sub">Diagnóstico de excelência visual e experiência de uso do programa APTO (versão 7.14.4): janela principal, relatórios em PDF, Excel, extensão do Chrome, Conversor de Áudio, identidade visual e modelos de petição. Inclui proposta de sistema de design, antes e depois e roteiro em fases.</div>
<div class="meta">70 achados com evidência (6 críticos, 21 altos) · 117 capturas · nenhuma regra, cálculo ou texto jurídico alterado<br>
Todas as imagens usam <b>dados fictícios</b> ("Simulado Caso NNN"); nenhum nome ou processo real.<br>
Esta etapa é só diagnóstico e proposta: nada foi mudado no programa.</div>
</div>""")
secoes.append("""<div class="cap"><h1>Sumário</h1><ol class="sum">
<li>Resumo executivo: as 10 mudanças de maior impacto</li>
<li>Antes e depois: 5 telas</li>
<li>Roteiro em fases</li>
<li>Perguntas para decidir</li>
<li>Achados: conferência dos indícios e as 70 constatações</li>
<li>Proposta de sistema de design</li>
<li>Tarefas reais: atrito medido</li>
<li>Como a análise foi feita</li>
<li>Anexo: galeria de evidências</li></ol>
<p class="nota" style="margin-top:14pt">Gravidade: <b>crítica</b> = pode levar a decisão errada ou perda de prazo · <b>alta</b> = atrito diário ou barreira de acessibilidade · <b>média</b> = inconsistência que custa tempo · <b>baixa</b> = acabamento. Esforço: <b>P</b> até 1 dia · <b>M</b> 2 a 5 dias · <b>G</b> mais de 1 semana.</p></div>""")
secoes.append('<div class="cap"><h1>1. Resumo executivo</h1>' + md("01_resumo_executivo.md") + "</div>")
ad = ['<h1>2. Antes e depois</h1><p>À esquerda, a versão 7.14.4 com a base fictícia. À direita, protótipo estático da proposta, com os mesmos dados, colunas e textos jurídicos: muda a ordem, a forma e a densidade, sem omitir informação.</p>']
for i, (tit, a, d, txt) in enumerate(PARES):
    bloco = f'<h2>2.{i+1} {tit}</h2><p>{txt}</p><div class="par"><figure><div class="rot">Antes</div><img src="{img(a)}"></figure><figure><div class="rot">Depois</div><img src="{img(d)}"></figure></div>'
    ad.append(bloco if i == 0 else f'<div class="ad">{bloco}</div>')
secoes.append('<div class="cap">' + "".join(ad) + "</div>")
secoes.append('<div class="cap"><h1>3. Roteiro em fases</h1>' + md("05_roteiro.md") + "</div>")
secoes.append('<div class="cap"><h1>4. Perguntas para decidir</h1>' + md("06_perguntas.md") + "</div>")
ach = md("02_achados.md").replace("<h2>2.", "<h2>5.")
secoes.append('<div class="cap"><h1>5. Achados</h1>' + ach + "</div>")
sd = md("03_sistema_de_design.md").replace("<h2>3.", "<h2>6.")
secoes.append('<div class="cap"><h1>6. Proposta de sistema de design</h1>' + sd + "</div>")
secoes.append('<div class="cap"><h1>7. Tarefas reais: atrito medido</h1>' + md("04_tarefas_reais.md") + "</div>")
met = open(os.path.join(R, "README.md"), encoding="utf-8").read()
met = met[met.index("## Como a tela foi executada"):]
met = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", met)
secoes.append('<div class="cap"><h1>8. Como a análise foi feita</h1>' + markdown.markdown(met, extensions=["tables", "fenced_code"]).replace("<h2>", "<h2>8 · ") +
              '<p class="nota">Os arquivos completos (documentos, protótipos navegáveis em HTML, as 117 capturas e os scripts) estão no repositório, na pasta <code>docs/analise_design/</code> do ramo <code>claude/elegant-darwin-a3l6av</code>. Os anexos técnicos detalhados de PDF/Excel e de extensão/conversor estão em <code>docs/analise_design/anexos/</code>.</p></div>')
pags = []
for k in range(0, len(GALERIA), 4):
    figs = "".join(fig(n, leg, 1100) for n, leg in GALERIA[k:k + 4])
    tit = '<h1>9. Anexo: galeria de evidências</h1>' if k == 0 else ''
    pags.append(f'<div class="galp">{tit}<div class="gal">{figs}</div></div>')
secoes.append("".join(pags))

html = f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>APTO · Análise de design</title><style>{CSS}</style></head><body>{"".join(secoes)}</body></html>'
tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analise.html")
open(tmp, "w", encoding="utf-8").write(html)
rod = '<div style="font:7pt Arial,sans-serif;color:#5C636A;width:100%;padding:0 14mm;display:flex;justify-content:space-between"><span>APTO · Análise de design · dados fictícios</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>'
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.goto("file://" + tmp); pg.wait_for_timeout(800)
    pg.pdf(path=OUT, format="A4", landscape=True, print_background=True, display_header_footer=True,
           header_template="<div></div>", footer_template=rod, margin={"top": "14mm", "bottom": "16mm", "left": "14mm", "right": "14mm"})
    b.close()
print(OUT, os.path.getsize(OUT) // 1024, "KB")
