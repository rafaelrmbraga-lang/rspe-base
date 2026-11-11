"""Tela 7.18.0: CSS consolidado (uma paleta, escalas de letra, canto e sombra, um bloco @media por condição) e as propostas
de interface (contadores numa linha, Indulto que cabe na tela, Quadro, dica de Dados prisionais, busca, subnavegação,
título único nas abas de painel, ficha do assistido com as ações no topo, ícones desenhados, algarismos alinhados).
Confere o texto do ui.html; o visual foi conferido com a base fictícia (docs/analise_design). Rodar: python teste_ui_718.py"""
import os
import re
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
UI = open(os.path.join(DIR, "ui.html"), encoding="utf-8").read()
CSS = re.search(r"<style>(.*?)</style>", UI, re.S).group(1)
JS = UI.replace(CSS, "")
falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


# ---------- consolidação do CSS ----------
sem_fontes = re.sub(r"@font-face\s*\{[^}]*\}", "", CSS)
regras = re.findall(r"([^{}]+)\{([^{}]*)\}", re.sub(r"/\*.*?\*/", "", sem_fontes, flags=re.S))
fora_root = [(s.strip(), d) for s, d in regras if s.strip() != ":root"]
hex_fora = [s for s, d in fora_root if re.search(r"#[0-9a-fA-F]{3,6}\b", re.sub(r"url\([^)]*\)|\"[^\"]*\"|'[^']*'", "", d))]
ok(not hex_fora, "CSS: cor escrita direto fora do :root em %s" % hex_fora[:5])
fs_lit = [s for s, d in fora_root for v in re.findall(r"font-size:\s*([\d.]+)px", d) if float(v) < 28]
ok(not fs_lit, "CSS: tamanho de letra fora da escala em %s" % fs_lit[:5])
for t in ("--fs-11:11px", "--fs-12:12px", "--fs-13:13px", "--fs-14:14px", "--fs-16:16px", "--fs-20:20px", "--fs-24:24px",
          "--r-1:4px", "--r-2:8px", "--r-3:12px", "--r-pill:999px", "--sh-1:", "--sh-2:", "--sh-3:", "--anel-foco:"):
    ok(t in CSS, "CSS: escala %s" % t)
raio_lit = [s for s, d in fora_root for v in re.findall(r"border-radius:\s*([^;}]+)", d) if re.search(r"\b(?!0\b)\d+px", v)]
ok(not raio_lit, "CSS: canto fora da escala em %s" % raio_lit[:5])
medias = re.findall(r"@media\s*([^{]+)\{", CSS)
ok(len(medias) == len({re.sub(r"\s+", "", m) for m in medias}), "CSS: um bloco @media por condição (%s)" % medias)
ok(CSS.count("!important") <= 210, "CSS: !important voltou a crescer (%d)" % CSS.count("!important"))

# ---------- propostas ----------
ok("out.verificar='Verificar'" in JS, "A2: contador 'Verificar' (cabe numa linha)")
ok(re.search(r"\.stats:has\(> ?\.stat\)\{flex-wrap:nowrap", CSS) is not None and "-webkit-line-clamp:2" in CSS, "A2: contadores numa linha, rótulo em até duas")
ok(">Verificar indulto/comutação<" not in JS and 'ui.indTL(${jsa(r.id)})">Linha do tempo</span>' in JS, "A3: botão 'Linha do tempo' no Indulto")
ok('class="dleg"' not in JS and "['cabe','nao','imp','conc','indef','ver','fora','ped']" in JS, "A3: legenda só no rodapé, com 'Não alcançado'")
ok(".qd-col{flex:1 1 220px" in CSS and "O quadro está vazio." in JS, "A4: colunas do Quadro cabem; quadro vazio orienta")
ok("geo:'Dados do Geopresídios (CNJ)" in JS, "A5: dica própria de Dados prisionais")
ok('placeholder="Buscar (Ctrl+K)"' in JS, "A6: busca legível no notebook")
ok('<div class="seg" role="group" aria-label="Pretensão">' in JS and ".seg,.seg2,.mon-alt{" in CSS, "B1: segmentado único para alternar a vista")
ok("bdMarca(id)" in JS and 'data-bd="${id}"' in JS and ".bd-nav span.on{" in CSS, "B1: seções de Dados da base marcam a que está à vista")
ok('<div class="geo-head"><div><b>' not in JS and JS.count('<div class="geo-head"><div><span class="muted">') == 2, "B2: um título só nas abas de painel")
ok('<div class="fx-acts">' in JS and "ui.menu('mFicha')" in JS and 'class="perigo" onclick="ui.confirmarRemocao(' in JS, "B3: ações da ficha no topo e remover no menu Mais")
ok('class="mini pre" onclick="ui.abrirSAP' not in JS, "B3: Registro para o SAP sem o verde de ação principal")
ok("r.pena_total_dias" in JS and "% da pena cumprida" in JS, "B3: barra de cumprimento pelos dias do RSPE")
ok("Conduta ${esc(rot.charAt(0).toLowerCase()" in JS, "B3: conduta em etiqueta")
ok("  ICO:{x:" in JS, "B4: ícones desenhados")
ok(re.search(r"\.tabs \.tab\{[^}]*border-bottom:0", CSS) is not None, "A1: sem o filete da antiga barra de abas sob a aba ativa")
for g in ("✕</button>", "⧉ ", "✎ ", "🗄", "<span class=\"chev\">▶</span>", "<span class=\"car\">▾</span>", "✔ NÃO IMPEDITIVO", "'★':'☆'"):
    ok(g not in JS, "B4: caractere usado como ícone ainda na tela: %r" % g)
ok(re.search(r"/\^\(\[✓✔✘✗…\?⚠\]\)\\s\*/", JS) is not None, "B4: os marcadores de dado (✓ ✔ ✘ no texto do programa) continuam reconhecidos")
ok("font-variant-numeric:tabular-nums" in CSS and "tbody td,.stat b" in CSS, "B5: algarismos alinhados nas colunas")

if falhas:
    print("FALHOU teste_ui_718:\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: tela 7.18.0 (CSS consolidado: paleta, escalas, um @media por condição; propostas A2-A6 e B1-B5)")
