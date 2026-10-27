import os, io, base64
from PIL import Image
from playwright.sync_api import sync_playwright
D = os.path.dirname(os.path.abspath(__file__))
OUT = "/home/user/rspe-base/docs/analise_design/APTO_abas_simuladas.pdf"
P = [
 ("01_geral", "Geral", "Lista em ordem alfabética, cabeçalho institucional e abas agrupadas por tarefa: Prazos · Decretos · Conferência · Panorama."),
 ("02_prog_situacao", "Progressão · por situação", "A lista abre pelo mais urgente: os 13 vencidos no topo, do mais atrasado ao menos atrasado. Cartões contam cada situação."),
 ("03_prog_alfabetica", "Progressão · alfabética", "A mesma lista na ordem de hoje. O seletor “Ordem da lista” alterna entre as duas, a qualquer momento."),
 ("04_liv", "Livramento condicional", "Mesma regra da Progressão: vencidos primeiro, depois os prazos mais curtos."),
 ("05_ind", "Indulto e comutação", "Cada decreto mostra o resultado por extenso (Sim, Verificar, Vedado), com cor. Agrupado por “algum benefício possível”."),
 ("06_presc", "Prescrição", "Prescrições aparentes no topo. A linha aberta mostra o cálculo em três passos e “Copiar fundamentação”."),
 ("07_ext", "Extinção da pena", "Extinções cabíveis no topo; depois os términos mais próximos."),
 ("08_fd", "Ficha disciplinar", "Atestados sem peticionamento no topo; os 130 sem ficha vão para o fim, sem sair da lista."),
 ("09_aud", "Auditoria do cálculo", "Alertas no topo. O alerta aberto traz o fundamento e as ações lado a lado."),
 ("10_painel", "Painel do assistido", "Todos os resultados de indulto na mesma linha, e o motivo do “A verificar” logo abaixo, com “Copiar fundamentação”."),
 ("11_importando", "Importação em andamento", "Painel de progresso visível, com falhas ao vivo, tempo restante e “Parar”."),
 ("12_importacao", "Importação concluída", "Quatro totais e as falhas primeiro, cada grupo com o que fazer."),
]
def img(n):
    im = Image.open(os.path.join(D, "telas", n + ".png")).convert("RGB"); b = io.BytesIO(); im.save(b, "JPEG", quality=86, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
fonte = lambda f: base64.b64encode(open(os.path.join(D, f + ".woff2"), "rb").read()).decode()
css = f"""@font-face{{font-family:S;src:url(data:font/woff2;base64,{fonte('SourceSerif4-SemiBold')})}}@font-face{{font-family:SS;src:url(data:font/woff2;base64,{fonte('SourceSans3-Regular')})}}@font-face{{font-family:C;font-weight:700;src:url(data:font/woff2;base64,{fonte('Cinzel-Bold')})}}
@page{{size:A4 landscape;margin:10mm 12mm}}body{{margin:0;font-family:SS,Arial,sans-serif;color:#1C211E}}
.pg{{break-after:page;height:188mm;display:flex;flex-direction:column}}.pg:last-child{{break-after:auto}}
h2{{font:600 17pt S,serif;color:#123824;margin:0}}p{{margin:2pt 0 5pt;font-size:10.5pt;color:#4A514C}}
.n{{font-size:9pt;color:#5F6762;letter-spacing:.5pt}}img{{width:100%;border:.6pt solid #C9CEC8;display:block}}
.capa{{justify-content:center}}.capa b{{font:700 34pt C,serif;letter-spacing:6pt;color:#123824}}.capa h1{{font:600 22pt S,serif;margin:8pt 0 4pt;color:#123824}}.capa .f{{height:3pt;width:150mm;background:linear-gradient(90deg,#1D5A3B 0 82%,#B8975A 82% 100%);margin:10pt 0}}"""
pags = ['<div class="pg capa"><b>APTO</b><div class="f"></div><h1>Abas simuladas com as propostas</h1><p>12 telas · dados fictícios (“Simulado Caso NNN”) exportados do próprio programa · nenhum cálculo ou texto jurídico alterado</p></div>']
for i, (n, t, d) in enumerate(P, 1):
    pags.append(f'<div class="pg"><div class="n">{i:02d} / {len(P)}</div><h2>{t}</h2><p>{d}</p><img src="{img(n)}"></div>')
html = f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><style>{css}</style></head><body>{''.join(pags)}</body></html>"
tmp = os.path.join(D, "telas.html"); open(tmp, "w", encoding="utf-8").write(html)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium"); pg = b.new_page(); pg.goto("file://" + tmp); pg.wait_for_timeout(600)
    pg.pdf(path=OUT, format="A4", landscape=True, print_background=True, margin={"top":"10mm","bottom":"10mm","left":"12mm","right":"12mm"}); b.close()
print(OUT, os.path.getsize(OUT)//1024, "KB")
