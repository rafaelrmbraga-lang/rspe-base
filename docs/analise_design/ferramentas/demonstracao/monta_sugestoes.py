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
  "Marca, base, busca e as duas ações principais (Exportar e Importar) numa só faixa. A lista começa mais acima e a busca fica sempre no mesmo lugar.", "pilha", "M"),
 ("Abas agrupadas por tarefa e com nomes por extenso",
  "Hoje as 12 abas têm o mesmo peso. “Ficha” (disciplinar) se confunde com a ficha do assistido, e Extinção fica longe de Progressão e Livramento.",
  ["abas"], ["abas"],
  "Grupos separados por um traço: Geral · Prazos · Decretos · Conferência · Panorama. Nomes completos (“Ficha disciplinar”, “Indulto e comutação”). Em telas menores, as ferramentas vão para “Mais”.", "pilha", "P"),
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
 ("Botões que dizem o que fazem",
  "Hoje o pedido é uma caixinha sem rótulo, e as ações da linha são três ícones cinza-claro, que parecem desabilitados.",
  ["fim_linha"], ["fim_linha"],
  "“Marcar pedido” e “Abrir ›” escritos, sempre no fim da linha, na mesma ordem em todas as abas.", "lado", "P"),
 ("Uma cor, um significado, em todas as abas",
  "Hoje o verde é “vence em até 90 dias” na Progressão (um prazo correndo) e “guia em ordem” na Auditoria. A mesma cor diz coisas opostas.",
  ["cartoes", "cartoes_aud"], ["cartoes_prog", "cartoes_aud"],
  "O verde passa a significar só “em ordem / cabe”. “Até 90 dias” ganha um tom próprio, neutro. Vermelho = agir já, em qualquer aba.", "pilha", "M"),
 ("Legenda por aba, em tabela, com o que fazer",
  "Hoje “Legenda e método” é um bloco corrido que descreve as cores por extenso (“vermelho = …”) e mistura todas as abas.",
  ["legenda_ajuda"], ["legenda_ajuda"],
  "A legenda abre na aba atual: a etiqueta como aparece na tela, o que quer dizer e o que fazer. O método completo continua a um clique.", "lado", "P"),
 ("Painel do assistido: o essencial e o porquê no mesmo lugar",
  "Hoje a linha “Indulto” do painel mostra só os decretos cabíveis. O “a verificar” e a sua fundamentação ficam mais abaixo, em “Cálculos do programa”, com outro nome.",
  ["painel"], ["painel"],
  "Todos os resultados na mesma linha (2022 Possível · 2024 A verificar · 2025 Possível) e, logo abaixo, o motivo do “A verificar” com “Copiar fundamentação”.", "lado", "M"),
 ("Detalhe da linha em passos, com as ações sempre no mesmo lugar",
  "Hoje o detalhe da Prescrição é uma tabela larga, de 12 colunas, que passa da largura da tela e corta o botão “Abrir ficha”.",
  ["presc_detalhe"], ["presc_detalhe"],
  "O cálculo em três passos (prazo, termo inicial, executória) e uma barra fixa de ações: Copiar fundamentação · Ver linha do tempo · Editar dados · Abrir painel.", "pilha", "M"),
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
  "Com cabeçalho em uma faixa, abas agrupadas e cartões compactos, cabem cerca de 5 a 6 assistidos na mesma tela.", "lado", "M"),
]

css = f"""
@font-face{{font-family:Serif;font-weight:600;src:url(data:font/woff2;base64,{f64('SourceSerif4-SemiBold')})}}
@font-face{{font-family:Sans;font-weight:400;src:url(data:font/woff2;base64,{f64('SourceSans3-Regular')})}}
@font-face{{font-family:Sans;font-weight:600;src:url(data:font/woff2;base64,{f64('SourceSans3-SemiBold')})}}
@font-face{{font-family:Sans;font-weight:700;src:url(data:font/woff2;base64,{f64('SourceSans3-Bold')})}}
@font-face{{font-family:Marca;font-weight:700;src:url(data:font/woff2;base64,{f64('Cinzel-Bold')})}}
@page{{size:A4 landscape;margin:11mm 13mm 12mm}}
*{{box-sizing:border-box}}
body{{margin:0;font:10.5pt/1.42 Sans,Arial,sans-serif;color:#1C211E}}
.pg{{height:186mm;break-after:page;display:flex;flex-direction:column;overflow:hidden}}.pg:last-child{{break-after:auto}}
.k{{font-size:8.5pt;font-weight:700;letter-spacing:.8pt;text-transform:uppercase;color:#1D5A3B}}
h1{{font:600 26pt Serif,serif;color:#123824;margin:4pt 0}}
h2{{font:600 17pt Serif,serif;color:#123824;margin:2pt 0 3pt}}
.pq{{color:#4A514C;margin:0 0 6pt;max-width:255mm}}
.faixa{{height:3pt;background:linear-gradient(90deg,#1D5A3B 0 82%,#B8975A 82% 100%);margin:6pt 0 10pt}}
.paineis{{flex:1;min-height:0;display:flex;gap:6mm}}
.paineis.pilha{{flex-direction:column;gap:4mm}}
.col{{flex:1;min-width:0;min-height:0;display:flex;flex-direction:column}}
.rot{{font-size:8.5pt;font-weight:700;letter-spacing:.6pt;text-transform:uppercase;margin-bottom:2pt}}
.rot.h{{color:#7A3B36}}.rot.p{{color:#1D5A3B}}
.quadro{{flex:1;min-height:0;display:flex;gap:3mm;align-items:flex-start}}
.quadro img{{max-width:100%;max-height:100%;object-fit:contain;object-position:left top;border:.7pt solid #C9CEC8;border-radius:3pt}}
.col.h .quadro img{{border-color:#D9C4C1}}.col.p .quadro img{{border-color:#9DBBA8}}
.quadro.vert{{flex-direction:column}}
.ganho{{margin-top:5pt;padding:6pt 10pt;background:#E9F0EB;border-left:3pt solid #1D5A3B;border-radius:0 4pt 4pt 0;font-size:10.5pt}}
.ganho b{{color:#123824}}
.num{{font:600 30pt Serif,serif;color:#B8975A;line-height:1;margin-right:8pt}}
.tit{{display:flex;align-items:flex-end}}
.capa{{justify-content:center;padding-left:6mm}}
.capa .m{{font:700 36pt Marca,serif;letter-spacing:7pt;color:#123824}}
.capa h1{{font-size:28pt;margin-top:10pt}}
.capa .pr{{margin-top:14pt;max-width:210mm;font-size:13pt;color:#2E3531;border-left:3pt solid #B8975A;padding-left:10pt}}
.capa .pe{{margin-top:22pt;font-size:9.5pt;color:#5F6762}}
.regras{{display:grid;grid-template-columns:96mm 1fr;gap:8mm;flex:1;min-height:0}}
.regras ol{{margin:0;padding:0;list-style:none;counter-reset:r}}
.regras li{{counter-increment:r;position:relative;padding:0 0 9pt 26pt;font-size:10.5pt}}
.regras li::before{{content:counter(r);position:absolute;left:0;top:-1pt;width:17pt;height:17pt;border-radius:50%;background:#1D5A3B;color:#fff;font:700 9.5pt Sans;display:grid;place-items:center}}
.regras li b{{display:block;color:#123824}}
.anot{{position:relative;align-self:start}}.anot img{{width:100%;display:block;border:.7pt solid #C9CEC8;border-radius:3pt}}
.anot i{{position:absolute;width:17pt;height:17pt;margin:-8.5pt 0 0 -8.5pt;border-radius:50%;background:#B8975A;color:#fff;font:700 9.5pt Sans;font-style:normal;display:grid;place-items:center;box-shadow:0 0 0 2pt #fff}}
table.res{{width:100%;border-collapse:collapse;font-size:8.9pt;line-height:1.3}}
table.res th{{text-align:left;font-size:8.5pt;letter-spacing:.5pt;text-transform:uppercase;color:#4A514C;border-bottom:1.2pt solid #1D5A3B;padding:3pt 5pt}}
table.res td{{padding:2.2pt 5pt;border-bottom:.5pt solid #E1E4DF;vertical-align:top}}
table.res td:first-child{{font:600 11pt Serif;color:#B8975A;width:9mm}}
table.res td.e{{text-align:center;font-weight:700;color:#1D5A3B;width:16mm}}
.nota{{font-size:9pt;color:#5F6762;margin-top:6pt}}
.grade5{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6mm 5mm}}
.grade5 figure{{margin:0;min-width:0}}.grade5 img{{width:100%;border:.7pt solid #C9CEC8;border-radius:3pt;display:block}}
.grade5 figcaption{{font-size:9.5pt;margin-top:2pt}}.grade5 figcaption b{{font:600 11pt Serif;color:#123824}}
.linha{{display:grid;grid-template-columns:minmax(0,63fr) minmax(0,37fr);gap:6mm;flex:1;min-height:0}}
.linha>div{{min-width:0;min-height:0}}
.linha .g img{{width:100%;border:.7pt solid #C9CEC8;border-radius:3pt;display:block}}
.linha .d{{display:flex;flex-direction:column;gap:3mm}}
.linha .d img{{width:100%;max-height:47%;object-fit:contain;object-position:left top;border:.7pt solid #C9CEC8;border-radius:3pt;display:block}}
.linha ul{{margin:5pt 0 0;padding-left:14pt;font-size:10pt}}.linha li{{margin:1.5pt 0}}
.linha .ind{{font-size:10pt;background:#F4F5F2;border-left:3pt solid #B8975A;padding:5pt 8pt;margin-top:5pt}}
.g4{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:3mm 6mm;max-width:238mm;margin:4mm auto 0}}.g4 figure{{margin:0;min-width:0}}.g4 img{{width:100%;display:block;border:.7pt solid #C9CEC8;border-radius:3pt}}.g4 figcaption{{font:600 10pt Serif;color:#123824;margin-top:1.5pt}}
.parte{{justify-content:center}}.parte h1{{font-size:30pt}}.parte p{{max-width:220mm;font-size:12pt;color:#4A514C}}
"""

pags = []
pags.append("""<div class="pg capa"><div class="m">APTO</div><div class="faixa" style="width:150mm"></div>
<h1>Sugestões de visual e experiência</h1>
<div class="pr"><b>O princípio: facilitar.</b> A tela diz o essencial, de forma clara e objetiva. Quem quiser se aprofundar tem os botões para isso. Todas as abas seguem a mesma linha gráfica, pensada para achar a informação rápido e entender as funções sem explicação.</div>
<div class="pe">Parte 1: a versão atual e seis linhas gráficas para avaliar · Parte 2: 15 sugestões de experiência, cada uma com a tela de hoje e a proposta · dados fictícios (“Simulado Caso NNN”), exportados do próprio programa · nenhuma regra, cálculo ou texto jurídico alterado</div></div>""")


# ---------- Parte 1: cinco linhas gráficas ----------
TT = os.path.join(FON, "telas_todas"); CAPS = "/home/user/rspe-base/docs/analise_design/capturas"
LINHAS = [
 ("0", "Versão atual (7.14.4)", "referência para comparar",
  (TT, "t0_prog"), (TT, "t0_painel"), (TT, "t0_ind"),
  ["Arial 13 px, verde da Defensoria, cantos retos", "Ícones ao lado do nome de cada aba; 12 abas numa fila", "Lista em ordem alfabética; situação em texto colorido", "Ícones nas linhas (fixar, saída temporária, quadro, abrir) e caixa sem rótulo para o pedido"],
  "for preciso manter tudo como está; serve de base para comparar as outras seis."),
 ("1", "Sóbria com símbolos", "apresentada antes",
  (TT, "t1_prog"), (TT, "t1_painel"), (TT, "t1_ind"),
  ["Arial, verde da marca e fundo neutro", "Cada situação com uma forma (losango, triângulo, círculo) além da cor", "Abas agrupadas, com o nome do grupo em cima", "Cartões compactos e grupos com títulos em maiúsculas"],
  "a impressão em preto e branco e a leitura por quem não distingue cores forem prioridade."),
 ("2", "Institucional", "verde e dourado",
  (TT, "t2_prog"), (TT, "t2_painel"), (TT, "t2_ind"),
  ["Faixa verde com filete dourado, títulos com a mesma letra serifada dos relatórios em PDF", "Situação em etiqueta com fundo suave; complemento em letra menor", "Cartões grandes de resumo", "Botões escritos: “Marcar pedido”, “Abrir”"],
  "a identidade da Defensoria e a coerência com os relatórios impressos forem prioridade."),
 ("3", "Clara e compacta", "moderna, mais linhas por tela",
  (TT, "t3_prog"), (TT, "t3_painel"), (TT, "t3_ind"),
  ["Fundo claro e um único verde de destaque", "Situação com ponto colorido + texto, sem caixas", "Linhas mais baixas: cabem mais assistidos na tela", "Abas em botões arredondados, numa linha só"],
  "as bases forem grandes e o trabalho for, na maior parte do tempo, percorrer listas."),
 ("4", "Familiar ao SEEU", "clássica, de sistema judicial",
  (TT, "t4_prog"), (TT, "t4_painel"), (TT, "t4_ind"),
  ["Faixa superior verde-escura, Arial, cantos retos", "Abas em fichário, como nos sistemas do Judiciário", "Tabela com grade e linhas alternadas; títulos em maiúsculas", "Situação em texto colorido e negrito"],
  "a equipe preferir uma tela parecida com o SEEU e o PJe, com o menor estranhamento possível."),
 ("5", "Barra lateral", "navegação sempre à vista",
  (TT, "t5_prog"), (TT, "t5_painel"), (TT, "t5_ind"),
  ["Abas numa coluna verde à esquerda, agrupadas por tarefa", "Todas as abas visíveis, sem menu “Mais”", "Cabeçalho só com base, busca e ações", "Conteúdo com os mesmos cartões e etiquetas da proposta 2"],
  "a equipe trocar muito de aba e usar monitores largos."),
 ("6", "Institucional com ícones nas abas", "a linha 2, mantendo os ícones de hoje",
  (TT, "t6_prog"), (TT, "t6_painel"), (TT, "t6_ind"),
  ["Tudo da linha 2 (faixa verde e dourada, títulos serifados, etiquetas, botões escritos)", "Mantém os ícones atuais ao lado do nome de cada aba", "Abas agrupadas por tarefa, todas na mesma linha", "Quem já usa o APTO reconhece as abas pelo ícone"],
  "a equipe já se orienta pelos ícones das abas e não quiser perder essa referência. Os ícones também podem ser levados para as linhas 3, 4 e 5."),
]
ABAS_T = [('geral','Geral'),('prog','Progressão'),('liv','Livramento'),('ind','Indulto e comutação'),('presc','Prescrição'),('ext','Extinção'),('fd','Ficha disciplinar'),('aud','Auditoria'),('base','Dados da base'),('geo','Dados prisionais'),('teses','Jurisprudências'),('quadro','Quadro do usuário')]
parte1 = ['<div class="pg parte"><div class="k">Parte 1</div><h1>Seis linhas gráficas e a versão atual</h1><div class="faixa" style="width:150mm"></div><p>A versão atual (0) e seis propostas (1 a 6): a mesma aba, com os mesmos dados. Todas seguem as regras de facilitar (o que exige ação primeiro, a situação em destaque, ações com nome); muda a aparência. Escolhida a linha, ela vale para todas as abas, para os relatórios em PDF e para a extensão.</p><p><b>Em todas as linhas, como hoje:</b> a aba Indulto com a barra de decretos e o mapa de cabimento por decreto em cada assistido, e os ícones ao lado do nome (saída temporária, progressão antecipada, divergência).</p></div>']
fig = "".join(f'<figure><img src="{img(a[3][0], a[3][1], 1000)}" style="{"border:1.5pt solid #7A3B36" if a[0]=="0" else ""}"><figcaption><b>{a[0]} · {a[1]}</b> — {a[2]}</figcaption></figure>' for a in LINHAS)
parte1.append(f'<div class="pg"><div class="k">Parte 1 · visão geral</div><h2>Atual e propostas lado a lado: aba Progressão</h2><div class="faixa"></div><div class="grade5">{fig}</div></div>')
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
pags.append('<div class="pg parte"><div class="k">Parte 2</div><h1>15 sugestões de experiência</h1><div class="faixa" style="width:150mm"></div><p>O que muda no uso, independentemente da linha escolhida. Cada sugestão traz a tela de hoje e a proposta (ilustrada com a linha 2), e uma frase com o ganho.</p></div>')

# linha gráfica com a tela anotada
cx = json.load(open(os.path.join(P, "caixas.json")))
marc = [("topo", 0.45, 0.5), ("abas", 0.03, 0.5), ("cab", 1.04, 0.5), ("cartoes", 0.005, 0.15), ("grupo", 0.13, 0.55), ("sit", 1.25, 0.5), ("ped", -0.18, 0.5)]
pins = "".join(f'<i style="left:{(cx[k][0] + cx[k][2] * fx) / 1440 * 100:.2f}%;top:{(cx[k][1] + cx[k][3] * fy) / 860 * 100:.2f}%">{n}</i>' for n, (k, fx, fy) in enumerate(marc, 1))
pags.append(f"""<div class="pg"><div class="k">A linha gráfica</div><h2>Sete regras, as mesmas em todas as abas</h2><div class="faixa"></div>
<div class="regras"><ol>
<li><b>Um cabeçalho, sempre igual</b>Marca, base aberta, busca e as ações principais no mesmo lugar.</li>
<li><b>Abas por tarefa</b>Prazos, decretos, conferência e panorama separados, com nomes por extenso.</li>
<li><b>Título e ordem à vista</b>O usuário sabe em que aba está e como a lista está ordenada.</li>
<li><b>Cartões que contam e filtram</b>O número de cada situação, grande; um clique filtra.</li>
<li><b>Primeiro o que exige ação</b>A lista se agrupa por situação, do mais urgente ao menos urgente.</li>
<li><b>O essencial em destaque</b>A situação curta em evidência; o complemento logo abaixo, menor.</li>
<li><b>Ações com nome, no mesmo lugar</b>“Marcar pedido” e “Abrir” no fim de toda linha.</li>
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
