"""Documento de sugestões de visual e experiência do APTO: cada sugestão com a tela de hoje e a proposta simulada.
Dados fictícios. Saída: docs/analise_design/APTO_sugestoes_visual_e_experiencia.pdf"""
import os, io, json, base64
from PIL import Image
from playwright.sync_api import sync_playwright

B = os.path.dirname(os.path.abspath(__file__))
H, P = os.path.join(B, "hoje"), os.path.join(B, "prop")
FON = os.path.join(os.path.dirname(B), "demo")
OUT = "/home/user/rspe-base/docs/analise_design/APTO_sugestoes_visual_e_experiencia.pdf"


def img(pasta, nome, larg=1800):
    im = Image.open(os.path.join(pasta, nome + ".png")).convert("RGB")
    if im.width > larg:
        im = im.resize((larg, round(im.height * larg / im.width)), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "JPEG", quality=74, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def f64(n):
    return base64.b64encode(open(os.path.join(FON, n + ".woff2"), "rb").read()).decode()


# (título, por quê, hoje, proposta, ganho, arranjo, esforço)
# arranjo: "pilha" (um sobre o outro: recortes largos), "lado" (lado a lado), "tres" (3 miniaturas por linha)
SUG = [
 ("Uma estrutura igual em todas as abas",
  "Hoje cada aba se organiza de um jeito: a Prescrição tem botões próprios no topo, a Ficha tem outra disposição, a Geral não tem cartões. Quem aprende uma aba precisa reaprender a próxima. A Indulto mantém a barra de decretos e o mapa de cabimento.",
  ["aba_ind", "aba_presc", "aba_fd"], ["aba_ind", "aba_presc", "aba_fd"],
  "Toda aba tem a mesma ordem: título, cartões de resumo, lista e, ao clicar, o detalhe. Aprender uma aba é saber usar todas.", "tres", "G"),
 ("Cabeçalho em uma faixa só",
  "Hoje o topo ocupa três faixas (marca e busca, botões, abas). A busca fica longe dos botões e a lista começa mais abaixo.",
  ["cabecalho"], ["cabecalho"],
  "Marca, base (com a data da cópia de segurança), busca e todos os botões de hoje numa só faixa; o filtro vai para junto da ordem da lista. A lista começa mais acima.", "pilha", "M"),
 ("Abas agrupadas por tarefa e com nomes por extenso",
  "Hoje as 12 abas têm o mesmo peso. “Ficha” (disciplinar) se confunde com a ficha do assistido, e Extinção fica longe de Progressão e Livramento.",
  ["abas"], ["abas"],
  "Grupos separados por um traço: Geral · Prazos · Decretos · Conferência · Panorama. Nomes completos (“Ficha disciplinar”, “Indulto e comutação”), com os ícones e os contadores de hoje. As 12 abas ficam sempre à vista.", "pilha", "P"),
 ("Cartões de resumo que se leem de longe e também filtram",
  "Hoje os contadores são chips pequenos, com uma barrinha de cor de 3 px. O número se perde no texto.",
  ["cartoes"], ["cartoes"],
  "Número grande e rótulo curto embaixo. O vermelho fica só no que exige ação. Clicar no cartão filtra a lista, como hoje.", "pilha", "P"),
 ("A lista abre pelo que exige ação",
  "Hoje as abas de prazo abrem em ordem alfabética. Na Progressão fictícia, o primeiro vencido está na 35ª linha e são 12 telas de rolagem para ver os 13.",
  ["lista_alfa"], ["lista_urg"],
  "Vencidos no topo, do mais atrasado ao menos atrasado: o 1º vencido passa para a 2ª linha e todos cabem em 2 telas. A ordem alfabética continua a um clique, no seletor “Ordem da lista”.", "pilha", "P"),
 ("Situação curta e em destaque; o complemento logo abaixo",
  "Hoje a coluna Situação quebra em até 4 linhas (“Em 66 dias · percentual do / SEEU acima do / legal - ver / Auditoria”) e as linhas ficam com alturas diferentes.",
  ["situacao"], ["situacao"],
  "Primeiro o que importa, em destaque (“Vencido há 649 dias”); embaixo, em letra menor, o complemento do programa. O texto completo continua no painel do assistido.", "pilha", "P"),
 ("Ações da linha mais fáceis de ver",
  "Hoje o pedido é uma caixinha sem rótulo, e os três ícones da linha (ficha, Quadro, abrir) são cinza-claro e parecem desabilitados.",
  ["fim_linha"], ["fim_linha"],
  "Os mesmos ícones, no mesmo lugar e na mesma ordem em todas as abas, com mais contraste e dica ao passar o mouse; a ficha fica verde quando foi importada. A caixa ganha o nome “Marcar pedido”. Nada sai da linha.", "lado", "P"),
 ("Uma cor, um significado, em todas as abas",
  "Hoje o verde é “vence em até 90 dias” na Progressão (um prazo correndo) e “guia em ordem” na Auditoria. A mesma cor diz coisas opostas.",
  ["cartoes", "cartoes_aud"], ["cartoes_prog", "cartoes_aud"],
  "O verde passa a significar só “em ordem / cabe”. “Até 90 dias” ganha um tom próprio, neutro. Vermelho = agir já, em qualquer aba.", "pilha", "M"),
 ("Legenda por aba, em tabela, com o que fazer",
  "Hoje “Legenda e método” é um bloco corrido que descreve as cores por extenso (“vermelho = …”) e mistura todas as abas.",
  ["legenda_ajuda"], ["legenda_ajuda"],
  "A legenda abre na aba atual: a etiqueta como aparece na tela, o que quer dizer e o que fazer. O método completo continua a um clique.", "lado", "P"),
 ("Painel do assistido: só o essencial",
  "Hoje a linha “Indulto” do painel mostra só os decretos cabíveis. O “a verificar” e a sua fundamentação ficam mais abaixo, em “Cálculos do programa”, com outro nome.",
  ["painel"], ["painel"],
  "Todos os resultados do indulto na mesma linha (2022 Possível · 2024 A verificar · 2025 Possível). Os cálculos seguem logo abaixo, com “ver cálculo completo” e “Copiar”; os botões de hoje ficam no topo e no rodapé do painel.", "lado", "M"),
 ("Detalhe da linha em passos, sem perder nada",
  "Hoje o detalhe da Prescrição é uma tabela larga, de 12 colunas, que passa da largura da tela e corta o botão “Abrir ficha”.",
  ["presc_detalhe"], ["presc_detalhe"],
  "As datas do processo numa linha (pena, fato, recebimento da denúncia, sentença, acórdão, trânsito), o cálculo em três passos (prazo, termo inicial, executória) e os botões de hoje: Ver cálculo, Editar dados e Abrir ficha completa.", "pilha", "M"),
 ("Avisos claros: o sucesso com “Desfazer”, o erro que fica",
  "Hoje sucesso e erro usam o mesmo aviso preto, que some em 3,5 segundos. Um erro como “nada foi gravado” pode passar despercebido.",
  ["aviso"], ["aviso"],
  "Sucesso discreto, com “Desfazer”. Erro em destaque, que só some quando o usuário fecha.", "lado", "P"),
 ("Importação: progresso à vista e resumo que separa o que falhou",
  "Hoje o progresso é um texto pequeno no canto do rodapé. No fim, falhas, leituras parciais e duplicados vêm numa lista corrida.",
  ["importando", "importacao"], ["importando", "importacao"],
  "Painel de progresso com falhas ao vivo e “Parar”. No fim, quatro totais (entraram, falharam, com ressalva, ignorados) e as falhas primeiro, com o que fazer.", "importacao", "M"),
 ("Lista vazia que orienta",
  "Hoje, quando a busca não encontra ninguém, a tabela fica em branco, sem dizer por quê nem o que fazer.",
  ["vazio"], ["vazio"],
  "A tela diz o que foi buscado, onde a busca procura e oferece “Limpar busca”.", "pilha", "P"),
 ("Mais lista visível em notebooks (Windows em 150 %)",
  "Com a escala de 150 %, comum em notebooks Full HD, hoje cabem cerca de 2 linhas e meia da tabela.",
  ["escala150"], ["escala150"],
  "Com o cabeçalho em uma faixa e o modo compacto para telas pequenas, cabem 5 a 7 assistidos na mesma tela, sem tirar nenhum botão; com o menu lateral recolhido (linha E), a tabela ganha ainda mais largura.", "lado", "M"),
]

css = f"""
@font-face{{font-family:Sans;font-weight:400;src:url(data:font/woff2;base64,{f64('inter-latin-400-normal')})}}
@font-face{{font-family:Sans;font-weight:600;src:url(data:font/woff2;base64,{f64('inter-latin-600-normal')})}}
@font-face{{font-family:Sans;font-weight:700;src:url(data:font/woff2;base64,{f64('inter-latin-700-normal')})}}
@page{{size:A4 landscape;margin:11mm 13mm 12mm}}
*{{box-sizing:border-box}}
body{{margin:0;font:9.8pt/1.45 Sans,Arial,sans-serif;color:#1C211E}}
.pg{{height:186mm;break-after:page;display:flex;flex-direction:column;overflow:hidden}}.pg:last-child{{break-after:auto}}
.k{{font-size:9pt;font-weight:600;color:#1D5A3B}}
h1{{font:700 24pt Sans,sans-serif;letter-spacing:-.3pt;color:#1C211E;margin:4pt 0}}
h2{{font:700 15.5pt Sans,sans-serif;letter-spacing:-.2pt;color:#1C211E;margin:2pt 0 3pt}}
.pq{{color:#4A514C;margin:0 0 6pt;max-width:255mm}}
.faixa{{height:.8pt;background:#D5D9DE;margin:6pt 0 10pt;width:auto!important}}
.paineis{{flex:1;min-height:0;display:flex;gap:6mm}}
.paineis.pilha{{flex-direction:column;gap:4mm}}
.col{{flex:1;min-width:0;min-height:0;display:flex;flex-direction:column}}
.rot{{font-size:9pt;font-weight:700;margin-bottom:2pt}}
.rot.h{{color:#7A3B36}}.rot.p{{color:#1D5A3B}}
.quadro{{flex:1;min-height:0;display:flex;gap:3mm;align-items:flex-start}}
.quadro img{{max-width:100%;max-height:100%;object-fit:contain;object-position:left top;border:.7pt solid #C9CEC8;border-radius:3pt}}
.col.h .quadro img{{border-color:#D9C4C1}}.col.p .quadro img{{border-color:#9DBBA8}}
.quadro.vert{{flex-direction:column}}
.ganho{{margin-top:5pt;padding:6pt 10pt;background:#F1F3F2;border-radius:4pt;font-size:10pt}}
.ganho b{{color:#123824}}
.num{{font:700 24pt Sans,sans-serif;color:#1D5A3B;line-height:1;margin-right:10pt}}
.tit{{display:flex;align-items:flex-end}}
.capa{{justify-content:center;padding-left:6mm}}
.capa .m{{font:700 30pt Sans;letter-spacing:1pt;color:#1D5A3B}}
.capa h1{{font-size:28pt;margin-top:10pt}}
.capa .pr{{margin-top:14pt;max-width:210mm;font-size:12.5pt;color:#2E3531}}
.capa .pe{{margin-top:22pt;font-size:9.5pt;color:#5F6762}}
.regras{{display:grid;grid-template-columns:96mm 1fr;gap:8mm;flex:1;min-height:0}}
.regras ol{{margin:0;padding:0;list-style:none;counter-reset:r}}
.regras li{{counter-increment:r;position:relative;padding:0 0 9pt 26pt;font-size:10.5pt}}
.regras li::before{{content:counter(r);position:absolute;left:0;top:-1pt;width:17pt;height:17pt;border-radius:50%;background:#1D5A3B;color:#fff;font:700 9.5pt Sans;display:grid;place-items:center}}
.regras li b{{display:block;color:#123824}}
.anot{{position:relative;align-self:start}}.anot img{{width:100%;display:block;border:.7pt solid #C9CEC8;border-radius:3pt}}
.anot i{{position:absolute;width:17pt;height:17pt;margin:-8.5pt 0 0 -8.5pt;border-radius:50%;background:#1D5A3B;color:#fff;font:700 9.5pt Sans;font-style:normal;display:grid;place-items:center;box-shadow:0 0 0 2pt #fff}}
table.res{{width:100%;border-collapse:collapse;font-size:8.9pt;line-height:1.3}}
table.res th{{text-align:left;font-size:8.8pt;color:#4A514C;border-bottom:1pt solid #1C211E;padding:3pt 5pt}}
table.res td{{padding:2.2pt 5pt;border-bottom:.5pt solid #E1E4DF;vertical-align:top}}
table.res td:first-child{{font:700 10pt Sans;color:#1D5A3B;width:9mm}}
table.res td.e{{text-align:center;font-weight:700;color:#1D5A3B;width:16mm}}
.alts{{display:grid;grid-template-columns:1fr 1fr;gap:4mm 7mm;flex:1;min-height:0}}.alts figure{{margin:0;min-width:0;min-height:0;display:flex;flex-direction:column}}.alts img{{max-width:100%;max-height:52mm;object-fit:contain;object-position:left top;border:.7pt solid #9DBBA8;border-radius:3pt;align-self:flex-start}}.alts figcaption{{font-size:9pt;color:#4A514C;margin-top:2pt}}
.tres3{{display:grid;grid-template-columns:repeat(2,minmax(0,108mm));justify-content:center;gap:3mm 8mm;flex:1;min-height:0}}.tres3 .ganho{{align-self:center}}.tres3 figure{{margin:0;min-width:0}}.tres3 img{{width:100%;border:.7pt solid #9DBBA8;border-radius:3pt;display:block}}.tres3 figcaption{{font-size:9pt;color:#4A514C;margin-top:3pt}}
.nbg{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:2mm 5mm;max-width:215mm}}.nbg figure{{margin:0;min-width:0}}.nbg img{{width:100%;border:.7pt solid #C9CEC8;border-radius:3pt;display:block}}.nbg figcaption{{font-size:8.5pt;margin-top:2pt}}
table.res.nb td:first-child{{width:auto;font-size:9.5pt}}
.nota{{font-size:9pt;color:#5F6762;margin-top:6pt}}
.grade5{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6mm 5mm}}
.grade5.g3{{grid-template-columns:repeat(3,minmax(0,1fr));gap:4mm 5mm}}.grade5 figure{{margin:0;min-width:0}}.grade5 img{{width:100%;border:.7pt solid #C9CEC8;border-radius:3pt;display:block}}
.grade5 figcaption{{font-size:9.5pt;margin-top:2pt}}.grade5 figcaption b{{font:700 10.5pt Sans;color:#1C211E}}
.linha{{display:grid;grid-template-columns:minmax(0,63fr) minmax(0,37fr);gap:6mm;flex:1;min-height:0}}
.linha>div{{min-width:0;min-height:0}}
.linha .g img{{width:100%;border:.7pt solid #C9CEC8;border-radius:3pt;display:block}}
.linha .d{{display:flex;flex-direction:column;gap:3mm}}
.linha .d img{{width:100%;max-height:47%;object-fit:contain;object-position:left top;border:.7pt solid #C9CEC8;border-radius:3pt;display:block}}
.linha ul{{margin:5pt 0 0;padding-left:14pt;font-size:10pt}}.linha li{{margin:1.5pt 0}}
.linha .ind{{font-size:9.8pt;background:#F1F3F2;border-radius:4pt;padding:5pt 8pt;margin-top:5pt}}
.g4{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:3mm 6mm;max-width:238mm;margin:4mm auto 0}}.g4 figure{{margin:0;min-width:0}}.g4 img{{width:100%;display:block;border:.7pt solid #C9CEC8;border-radius:3pt}}.g4 figcaption{{font:700 9.5pt Sans;color:#1C211E;margin-top:1.5pt}}
.parte{{justify-content:center}}.parte h1{{font-size:30pt}}.parte p{{max-width:220mm;font-size:12pt;color:#4A514C}}
"""

pags = []
pags.append("""<div class="pg capa"><div class="m">APTO</div>
<h1>Sugestões de visual e experiência</h1>
<div class="pr"><b>O princípio: facilitar.</b> A tela diz o essencial, de forma clara e objetiva. Quem quiser se aprofundar tem os botões de sempre. Nenhuma função sai da tela nem vai para um menu escondido. Todas as abas seguem a mesma linha gráfica.</div>
<div class="pe">Parte 1: a versão atual, cinco linhas gráficas baseadas nas bibliotecas visuais atuais do Python, o menu lateral que recolhe e o uso em notebooks · o que voltou para a tela e por quê · Parte 2: 15 sugestões de experiência, cada uma com a tela de hoje e a proposta · dados fictícios (“Simulado Caso NNN”), exportados do próprio programa · nenhuma regra, cálculo ou texto jurídico alterado</div></div>""")

# ---------- pesquisa ----------
BIB = [
 ("PySide6-Fluent-Widgets (QFluentWidgets)", "1.4.x · 2026", "Fluent 2, o visual do Windows 11", "GPLv3 ou licença comercial", "Exigiria refazer a tela em Qt", "A, E"),
 ("Fluent UI Web Components (Microsoft)", "base FAST", "Fluent 2 para páginas web", "MIT", "Cabe no ui.html; basta seguir as medidas e cores", "A, E"),
 ("Flet 1.0", "15/09/2026", "Material 3 (Flutter)", "Apache 2.0", "Exigiria refazer a tela inteira", "B"),
 ("NiceGUI 3.0", "out/2025", "Quasar (Vue) e Tailwind 4", "MIT", "Exigiria refazer a tela e um servidor local", "C"),
 ("Dash Mantine Components 2.7", "mai/2026 · Mantine 8", "Mantine", "MIT", "Exigiria refazer a tela em Dash", "D"),
 ("Reflex 0.9.7", "jul/2026", "Radix Themes", "Apache 2.0", "Exigiria refazer a tela; visual próximo de D", "—"),
 ("pywebview 6.2.1 (o que o APTO usa)", "abr/2026", "qualquer HTML/CSS", "BSD", "Fica como está", "todas"),
]
lin = "".join(f"<tr><td><b>{a}</b></td><td>{b}</td><td>{c}</td><td>{d}</td><td>{e}</td><td class='e'>{f}</td></tr>" for a, b, c, d, e, f in BIB)
pags.append(f"""<div class="pg"><div class="k">Pesquisa</div><h2>De onde vêm as linhas</h2><div class="faixa"></div>
<p class="pq">Busquei as bibliotecas de interface mais atuais do Python (out/2026). Cada uma traz uma <b>linguagem visual</b> pronta e testada por milhares de sistemas: medidas, cores, letras e componentes. As linhas A a E aplicam essas linguagens ao APTO. Isso evita o visual “inventado” das propostas anteriores.</p>
<table class="res"><tr><th>Biblioteca</th><th>Versão</th><th>Linguagem visual</th><th>Licença</th><th>Para usar no APTO</th><th>Linha</th></tr>{lin}</table>
<div class="ganho" style="margin-top:10pt"><b>Recomendação técnica:</b> manter o pywebview e o ui.html como estão (arquivo único, offline) e adotar só a <b>linguagem visual</b> escolhida, em CSS. Não entra biblioteca nova, nada de CDN, e o <code>testes.py</code> continua valendo. Trocar de biblioteca (Flet, NiceGUI, Dash, Qt) obrigaria a reescrever a tela inteira, sem ganho para quem usa. O QFluentWidgets, além disso, é GPL ou pago.</div>
<div class="nota">Letras: a linha A usa a Segoe UI, que já vem no Windows (nas capturas, a Open Sans faz as vezes dela). As linhas B e C usam Roboto e a D usa Inter: cerca de 90 KB embutidos no ui.html, sem internet. Fontes: pypi.org/project/pyside6-fluent-widgets · learn.microsoft.com/fluent-ui/web-components · byteiota.com (Flet 1.0) · talkpython.fm/525 (NiceGUI 3) · community.plotly.com (DMC 2) · reflex.dev/changelog · archlinux.org (pywebview).</div></div>""")

# ---------- Parte 1 ----------
TT = os.path.join(FON, "telas_todas"); CAPS = "/home/user/rspe-base/docs/analise_design/capturas"
LINHAS = [
 ("0", "Versão atual (7.14.4)", "referência para comparar",
  (TT, "t0_prog"), (TT, "t0_painel"), (TT, "t0_ind"),
  ["Três faixas no topo: marca e busca, botões e filtro, abas", "Ícones ao lado do nome de cada aba; 12 abas numa fila", "Lista em ordem alfabética; situação em texto colorido, que quebra em várias linhas", "Ícones nas linhas (fixar, ficha, Quadro, abrir) e caixa sem rótulo para o pedido"],
  "for preciso manter tudo como está; serve de base para comparar as outras."),
 ("A", "Fluent 2 (Windows 11)", "QFluentWidgets · Fluent UI",
  (TT, "t7_prog"), (TT, "t7_painel"), (TT, "t7_ind"),
  ["Abas numa coluna à esquerda, com ícone, nome e contador, separadas por tarefa (Prazos, Decretos, Conferência, Panorama)", "Visual nativo do Windows 11: letra Segoe UI, cantos de 4 px, botão principal no verde da Defensoria", "Conteúdo numa “folha” clara ao lado da navegação", "Todas as abas e botões à vista"],
  "a equipe quiser que o APTO pareça um programa do próprio Windows, e usar monitores de 1440 px ou mais."),
 ("B", "Material 3", "Flet 1.0 · Flutter",
  (TT, "t8_prog"), (TT, "t8_painel"), (TT, "t8_ind"),
  ["Trilho de navegação à esquerda: ícone em cima, nome embaixo, contador no ícone", "Busca em pílula; botões arredondados; ordem em botão segmentado com ✓", "Cartões em tom verde-claro; cantos de 12 px", "Visual dos aplicativos Android e Google atuais"],
  "a equipe preferir um visual mais suave e arredondado, parecido com o do celular."),
 ("C", "Quasar", "NiceGUI 3",
  (TT, "t9_prog"), (TT, "t9_painel"), (TT, "t9_ind"),
  ["Cabeçalho verde da Defensoria com as abas embaixo: ícone em cima, nome embaixo, contador", "Tabela densa, com sombras leves nos cartões", "Ordem em botões verdes de alternância", "Lembra os sistemas web institucionais"],
  "a identidade da Defensoria (o verde no topo) for prioridade, mantendo as abas no alto como hoje."),
 ("D", "Mantine", "Dash Mantine Components 2 · Mantine 8",
  (TT, "t10_prog"), (TT, "t10_painel"), (TT, "t10_ind"),
  ["Cabeçalho branco em uma faixa; abas logo abaixo, com ícone, nome e contador, como hoje", "Letra Inter; cartões com o rótulo em cima e o número embaixo", "Tabela limpa, com cabeçalho em negrito", "A menor mudança em relação à tela atual"],
  "a equipe quiser modernizar sem reaprender nada: as abas, os ícones e os botões ficam onde estão."),
 ("E", "Menu lateral que recolhe e expande", "Fluent 2 · NavigationView · telas em notebook (1280 × 680)",
  (TT, "tE_prog"), (TT, "tE_painel"), (TT, "tE_ind"),
  ["A linha A com um botão ☰ no alto do menu: expandido mostra ícone, nome e contador; recolhido, só o ícone e o contador", "Recolhido, o menu ocupa 52 px e a tabela ganha cerca de 150 px de largura", "Ao parar o mouse sobre um ícone, aparece o nome da aba", "O programa lembra a escolha; em telas estreitas, o menu expande por cima da lista, sem apertar a tabela", "Telas desta linha em 1280 × 680, o tamanho útil de um notebook Full HD com escala de 150 %"],
  "o APTO for usado em notebooks, ou se a equipe quiser escolher entre ver os nomes das abas ou ganhar espaço para a lista."),
]
ABAS_T = [('geral','Geral'),('prog','Progressão'),('liv','Livramento'),('ind','Indulto e comutação'),('presc','Prescrição'),('ext','Extinção'),('fd','Ficha disciplinar'),('aud','Auditoria'),('base','Dados da base'),('geo','Dados prisionais'),('teses','Jurisprudências'),('quadro','Quadro do usuário')]
parte1 = ['<div class="pg parte"><div class="k">Parte 1</div><h1>A versão atual e cinco linhas gráficas</h1><div class="faixa"></div><p>A versão atual (0) e cinco propostas (A a E), cada uma seguindo a linguagem visual de uma biblioteca atual do Python. É a mesma aba, com os mesmos dados. Escolhida a linha, ela vale para todas as abas, para os relatórios em PDF e para a extensão.</p><p><b>Em todas as linhas, como hoje:</b></p><ul style="font-size:11.5pt;color:#4A514C;max-width:220mm"><li>as 12 abas à vista, com os ícones ao lado do nome e o contador;</li><li>a aba Indulto com a barra de decretos e o mapa de cabimento por decreto em cada assistido;</li><li>os ícones ao lado do nome do assistido (saída temporária, progressão antecipada, divergência);</li><li>na linha: fixar, caixa do pedido, ficha, Quadro e abrir;</li><li>no topo: base, cópia de segurança, busca, Importar PDFs, Importar pasta, Exportar, tamanho da letra, calculadora, Legenda e método;</li><li>o filtro, a ordem da lista e a ordenação pelo título da coluna;</li><li>no rodapé, a legenda dos ícones, “* calculado pelo programa” e a dica da caixa do pedido.</li></ul><p>Nada vai para menu “Mais” ou “⋯”.</p></div>']
fig = "".join(f'<figure><img src="{img(a[3][0], a[3][1], 1000)}" style="{"border:1.5pt solid #7A3B36" if a[0]=="0" else ""}"><figcaption><b>{a[0]} · {a[1]}</b> — {a[2]}</figcaption></figure>' for a in LINHAS)
parte1.append(f'<div class="pg"><div class="k">Parte 1 · visão geral</div><h2>Atual e propostas lado a lado: aba Progressão</h2><div class="faixa"></div><div class="grade5 g3">{fig}</div></div>')
for n, nome, sub, prog, pain, ind, carac, indic in LINHAS:
    li = "".join(f"<li>{c}</li>" for c in carac)
    parte1.append(f'<div class="pg"><div class="tit"><span class="num">{n}</span><div><div class="k">Linha gráfica · {sub}</div><h2>{nome}</h2></div></div><div class="faixa" style="margin:4pt 0 6pt"></div>'
                  f'<div class="linha"><div class="g"><img src="{img(prog[0], prog[1], 1700)}"><ul>{li}</ul><div class="ind"><b>Indicada se</b> {indic}</div></div>'
                  f'<div class="d"><img src="{img(pain[0], pain[1], 1000)}"><img src="{img(ind[0], ind[1], 1000)}"></div></div></div>')
    pref = prog[1].split("_")[0]
    for k in range(0, 12, 4):
        cel = "".join(f'<figure><img src="{img(TT, pref + "_" + a, 1000)}"><figcaption>{rot}</figcaption></figure>' for a, rot in ABAS_T[k:k + 4])
        parte1.append(f'<div class="pg"><div class="k">Linha {n} · {nome} · todas as abas ({k // 4 + 1}/3)</div><div class="g4">{cel}</div></div>')
pags.extend(parte1)
NBD = os.path.join(FON, "notebook"); LJ = json.load(open(os.path.join(NBD, "linhas.json")))
pags.append(f"""<div class="pg"><div class="k">Linha E · menu lateral</div><h2>Três estados do menu: expandido, recolhido e por cima da lista</h2><div class="faixa"></div>
<div class="tres3"><figure><div class="rot p">Expandido</div><img src="{img(NBD, 'E_aberto', 1000)}"><figcaption>Ícone, nome e contador, separados por tarefa. Para monitores largos. O botão ☰ “Recolher o menu” fica no alto.</figcaption></figure>
<figure><div class="rot p">Recolhido</div><img src="{img(NBD, 'E_recolhido', 1000)}"><figcaption>Só o ícone e o contador, em 52 px. Ao parar o mouse, aparece o nome (“Indulto e comutação · 85”). As 12 abas continuam à vista.</figcaption></figure>
<figure><div class="rot p">Expandido por cima da lista</div><img src="{img(NBD, 'E_sobre', 1000)}"><figcaption>Em notebook, o ☰ abre o menu sobre a lista, sem apertar a tabela; escolhida a aba, ele volta a recolher.</figcaption></figure>
<div class="ganho"><b>O que muda:</b> quem tem monitor largo deixa o menu aberto; quem usa notebook recolhe e ganha cerca de 150 px para a tabela. Nenhuma aba some: recolhido, o menu mostra todos os ícones e contadores. O programa guarda a escolha de cada computador.</div></div></div>""")
nbt = "".join(f"<tr><td><b>{n}</b> <span style='font-size:8pt;color:#5F6762'>{d}</span></td><td class='e'>{LJ[n+'_1280']}</td><td class='e'>{LJ[n+'_1366']}</td><td class='e'>{LJ[n+'_1440']}</td></tr>" for n, d in [("A","Fluent 2, menu à esquerda aberto"),("B","Material 3, trilho"),("C","Quasar, abas no cabeçalho verde"),("D","Mantine, abas no alto (como hoje)"),("E","Menu lateral recolhido")])
nbf = "".join(f'<figure><img src="{img(NBD, n + "_1280", 900)}"><figcaption><b>{n}</b> · {LJ[n+"_1280"]} assistidos visíveis</figcaption></figure>' for n in "ABCDE")
pags.append(f"""<div class="pg"><div class="k">Notebooks</div><h2>Em notebook: tudo à vista, mais compacto</h2><div class="faixa"></div>
<p class="pq">Medido na aba Progressão, sem rolar. 1280 × 680 é o espaço útil de um notebook Full HD com escala de 150 % (o padrão do Windows nesses aparelhos); 1366 × 700, de um notebook HD a 100 %. Abaixo de 1400 px, todas as linhas ficam mais compactas (letra 12,5 px, linhas de 36 px, cartões menores) sem tirar nenhum botão. A caixa do pedido fica sem o texto, como hoje, e o título “Pedido” continua na coluna. Nas linhas C e D, as abas passam a ocupar duas fileiras.</p>
<div style="display:flex;gap:6mm;align-items:flex-start"><div class="nbg"><figure><img src="{img(H, 'escala150', 900)}" style="border-color:#7A3B36"><figcaption><b>0 · hoje</b> · cerca de 2 assistidos e meio</figcaption></figure>{nbf}</div>
<table class="res nb" style="width:78mm;flex:none"><tr><th>Linha</th><th>1280</th><th>1366</th><th>1440</th></tr>{nbt}</table></div><div class="nota">Assistidos visíveis por largura de tela (altura útil 680, 700 e 860 px).</div></div>""")
VOLTA = [
 ("Ícones da linha: ficha, Quadro e abrir", "Troquei por “Abrir ›” e um menu “⋯”, para limpar a linha.", "Escondia funções e somava um clique a cada uso.", "Voltam os três ícones, no mesmo lugar, com mais contraste e dica ao passar o mouse; a ficha fica verde quando foi importada."),
 ("Fixar no topo (alfinete)", "Levei para o painel do assistido.", "É usado na própria lista.", "Volta ao lado do nome."),
 ("Filtro “Todas ▾”", "Troquei pelos cartões de resumo.", "Os cartões só filtram a situação; o seletor tem 17 filtros (pedido, saída temporária, divergência…).", "Volta, ao lado da ordem da lista; os cartões também filtram."),
 ("Ordenar pelo título da coluna", "Deixei só “Alfabética / Por situação”.", "A equipe ordena por data, regime e outras colunas.", "Volta em todas as colunas (↕); a ordem atual fica marcada (↑)."),
 ("Ver cálculo, datas do processo e botões do detalhe", "Resumi o detalhe da Prescrição em três passos.", "Sumiram o “Ver cálculo” e parte das datas.", "Voltam todas as datas e os botões de hoje (Ver cálculo, Editar dados, Abrir ficha completa)."),
 ("Abas em telas menores e cópia de segurança", "Em telas estreitas, mandei 3 abas para “Mais” e ocultei a data da cópia.", "Era esconder.", "As 12 abas ficam sempre à vista; a data da cópia fica sob o nome da base."),
 ("Legenda do rodapé", "Não estava no protótipo.", "Explica os ícones e o asterisco.", "Volta: ícones, “* calculado pelo programa” e a dica da caixa do pedido."),
]
lv = "".join(f"<tr><td><b>{a}</b></td><td>{b}</td><td>{c}</td><td>{d}</td></tr>" for a, b, c, d in VOLTA)
pags.append(f"""<div class="pg"><div class="k">O que voltou para a tela</div><h2>Funções que eu tinha tirado ou escondido, e por quê voltaram</h2><div class="faixa"></div>
<p class="pq">Nas propostas anteriores, tirei ou escondi controles para a tela parecer mais limpa. Foi um erro: o APTO é usado todos os dias, e cada função escondida custa cliques e obriga a procurar. Nas linhas A a E, tudo o que existe hoje continua à vista.</p>
<table class="res"><tr><th>Função</th><th>O que eu tinha feito</th><th>Por que não serve</th><th>Agora, nas linhas A a E</th></tr>{lv}</table></div>""")
pags.append(f"""<div class="pg"><div class="k">O que voltou para a tela · alternativas</div><h2>Duas formas de mostrar as ações da linha e o filtro</h2><div class="faixa"></div>
<div class="alts">
<figure><div class="rot p">Ações · alternativa 1: ícones, como hoje</div><img src="{img(P, 'alt_acoes_icones', 1100)}"><figcaption>Os três ícones de hoje, mais escuros (hoje parecem desabilitados), com dica ao passar o mouse. A ficha fica verde quando foi importada. Ocupa pouco espaço.</figcaption></figure>
<figure><div class="rot p">Ações · alternativa 2: ícone e nome</div><img src="{img(P, 'alt_acoes_rotulos', 1100)}"><figcaption>Cada ícone com o nome ao lado (Ficha, Quadro, Abrir). Quem chega ao APTO entende sem passar o mouse; a linha fica mais larga.</figcaption></figure>
<figure><div class="rot p">Filtro · alternativa 1: seletor, como hoje</div><img src="{img(P, 'alt_filtro_a', 1100)}"><figcaption>O mesmo seletor de hoje, agora ao lado da ordem da lista, com os 17 filtros agrupados (Situação, Pedido, Benefícios a conferir, Conferência).</figcaption></figure>
<figure><div class="rot p">Filtro · alternativa 2: combinar filtros</div><img src="{img(P, 'alt_filtro_b', 1100)}"><figcaption>A situação filtra pelos cartões; os demais filtros abrem em caixas de marcar, que podem ser combinadas (ex.: “sem pedido” + “divergência”).</figcaption></figure>
</div></div>""")
pags.append('<div class="pg parte"><div class="k">Parte 2</div><h1>15 sugestões de experiência</h1><div class="faixa" style="width:150mm"></div><p>O que muda no uso, independentemente da linha escolhida. Cada sugestão traz a tela de hoje e a proposta (ilustrada com a linha D, a que menos muda a tela de hoje), e uma frase com o ganho.</p></div>')

# linha gráfica com a tela anotada
cx = json.load(open(os.path.join(P, "caixas.json")))
marc = [("topo", 0.45, 0.5), ("abas", 0.03, 0.5), ("cab", 1.04, 0.5), ("cartoes", 0.005, 0.15), ("grupo", 0.13, 0.55), ("sit", 1.25, 0.5), ("ped", -0.18, 0.5)]
pins = "".join(f'<i style="left:{(cx[k][0] + cx[k][2] * fx) / 1440 * 100:.2f}%;top:{(cx[k][1] + cx[k][3] * fy) / 860 * 100:.2f}%">{n}</i>' for n, (k, fx, fy) in enumerate(marc, 1))
pags.append(f"""<div class="pg"><div class="k">A linha gráfica</div><h2>Sete regras, as mesmas em todas as abas</h2><div class="faixa"></div>
<div class="regras"><ol>
<li><b>Um cabeçalho, sempre igual</b>Marca, base, cópia de segurança, busca e todos os botões de hoje, numa faixa.</li>
<li><b>Abas por tarefa</b>Prazos, decretos, conferência e panorama separados, com ícone, nome por extenso e contador.</li>
<li><b>Título e ordem à vista</b>O usuário sabe em que aba está e como a lista está ordenada.</li>
<li><b>Cartões que contam e filtram</b>O número de cada situação, grande; um clique filtra.</li>
<li><b>Primeiro o que exige ação</b>A lista se agrupa por situação, do mais urgente ao menos urgente.</li>
<li><b>O essencial em destaque</b>A situação curta em evidência; o complemento logo abaixo, menor.</li>
<li><b>Ações no mesmo lugar</b>“Marcar pedido” e os ícones de hoje (ficha, Quadro, abrir) no fim de toda linha.</li>
</ol><div class="anot"><img src="{img(P, 'prog_inteira', 1700)}">{pins}</div></div></div>""")

# quadro-resumo
linhas = "".join(f"<tr><td>{i}</td><td><b>{t}</b></td><td>{g}</td><td class='e'>{e}</td></tr>" for i, (t, _, _, _, g, _, e) in enumerate(SUG, 1))
pags.append(f"""<div class="pg"><div class="k">Resumo</div><h2>As 15 sugestões</h2><div class="faixa"></div>
<table class="res"><tr><th></th><th>Sugestão</th><th>O que muda para quem usa</th><th>Esforço</th></tr>{linhas}</table>
<div class="nota">Esforço: P = até 1 dia · M = 2 a 5 dias · G = mais de uma semana.</div></div>""")

for i, (tit, pq, hoje, prop, ganho, arr, esf) in enumerate(SUG, 1):
    if arr == "tres":
        h = "".join(f'<img src="{img(H, n, 900)}" style="width:32%">' for n in hoje)
        p = "".join(f'<img src="{img(P, n, 900)}" style="width:32%">' for n in prop)
        corpo = f'<div class="paineis pilha"><div class="col h"><div class="rot h">Hoje</div><div class="quadro">{h}</div></div><div class="col p"><div class="rot p">Proposta</div><div class="quadro">{p}</div></div></div>'
    elif arr == "importacao":
        corpo = (f'<div class="paineis"><div class="col h"><div class="rot h">Hoje</div><div class="quadro vert"><img src="{img(H, hoje[0])}"><img src="{img(H, hoje[1])}" style="max-height:62%"></div></div>'
                 f'<div class="col p"><div class="rot p">Proposta</div><div class="quadro vert"><img src="{img(P, prop[0])}" style="max-height:30%"><img src="{img(P, prop[1])}" style="max-height:66%"></div></div></div>')
    else:
        vert = ' vert' if len(hoje) > 1 else ''
        h = "".join(f'<img src="{img(H, n)}">' for n in hoje)
        p = "".join(f'<img src="{img(P, n)}">' for n in prop)
        corpo = f'<div class="paineis {arr}"><div class="col h"><div class="rot h">Hoje</div><div class="quadro{vert}">{h}</div></div><div class="col p"><div class="rot p">Proposta</div><div class="quadro{vert}">{p}</div></div></div>'
    pags.append(f'<div class="pg"><div class="tit"><span class="num">{i:02d}</span><div><div class="k">Sugestão · esforço {esf}</div><h2>{tit}</h2></div></div>'
                f'<p class="pq">{pq}</p>{corpo}<div class="ganho"><b>O que muda:</b> {ganho}</div></div>')

html = f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><title>APTO · Sugestões de visual e experiência</title><style>{css}</style></head><body>{''.join(pags)}</body></html>"
tmp = os.path.join(B, "sugestoes.html"); open(tmp, "w", encoding="utf-8").write(html)
rod = '<div style="font:7pt Arial,sans-serif;color:#5F6762;width:100%;padding:0 13mm;display:flex;justify-content:space-between"><span>APTO · Sugestões de visual e experiência · dados fictícios</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>'
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium"); pg = b.new_page(); pg.goto("file://" + tmp); pg.wait_for_timeout(800)
    pg.pdf(path=OUT, format="A4", landscape=True, print_background=True, display_header_footer=True, header_template="<div></div>", footer_template=rod,
           margin={"top": "11mm", "bottom": "12mm", "left": "13mm", "right": "13mm"}); b.close()
print(OUT, os.path.getsize(OUT) // 1024, "KB")
