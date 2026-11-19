"""Guia em PDF da extensão APTO SEEU: instalação no Chrome (ou Edge) e uso. As imagens são do SEEU FICTÍCIO (teste_painel_e2e.js,
nomes e números inventados) e da tela de extensões do Chrome; nenhuma traz dado real.
Uso (via montar.py): python ferramentas/apto_seeu/montar.py saida_dir capturas_dir"""
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FONTES = os.path.join(RAIZ, "extensao_seeu", "painel")
VERDE = colors.HexColor("#1D5A3B")
TX, TX2, LINHA = colors.HexColor("#1E2226"), colors.HexColor("#454B50"), colors.HexColor("#DADDE0")
AMB_BG, AMB = colors.HexColor("#FBF4DD"), colors.HexColor("#6B5300")


def _fontes():
    for nome, arq in (("SS", "SourceSans3-Regular.ttf"), ("SS-B", "SourceSans3-Bold.ttf"), ("SS-SB", "SourceSans3-SemiBold.ttf")):
        if nome not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(nome, os.path.join(FONTES, arq)))
    pdfmetrics.registerFontFamily("SS", normal="SS", bold="SS-B", italic="SS", boldItalic="SS-B")


def _estilos():
    base = dict(fontName="SS", fontSize=10.5, leading=15, textColor=TX, alignment=TA_LEFT)
    return {
        "capa": ParagraphStyle("capa", fontName="SS-B", fontSize=26, leading=31, textColor=VERDE, spaceAfter=4),
        "sub": ParagraphStyle("sub", fontName="SS", fontSize=13, leading=18, textColor=TX2, spaceAfter=14),
        "h1": ParagraphStyle("h1", fontName="SS-B", fontSize=16, leading=21, textColor=VERDE, spaceBefore=6, spaceAfter=8),
        "h2": ParagraphStyle("h2", fontName="SS-B", fontSize=12, leading=16, textColor=TX, spaceBefore=8, spaceAfter=4),
        "p": ParagraphStyle("p", spaceAfter=6, **base),
        "li": ParagraphStyle("li", spaceAfter=2, **base),
        "leg": ParagraphStyle("leg", fontName="SS", fontSize=9, leading=12, textColor=TX2, spaceBefore=3, spaceAfter=10),
        "nota": ParagraphStyle("nota", fontName="SS", fontSize=10, leading=14, textColor=AMB),
    }


def _img(caminho, largura):
    from reportlab.lib.utils import ImageReader
    w, h = ImageReader(caminho).getSize()
    return Image(caminho, width=largura, height=largura * h / w)


def _figura(E, cap, nome, largura, legenda):
    p = os.path.join(cap, nome)
    if not os.path.isfile(p):
        return []
    im = _img(p, largura)
    t = Table([[im]], colWidths=[largura + 2])
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, LINHA), ("LEFTPADDING", (0, 0), (-1, -1), 1), ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                           ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    return [KeepTogether([t, Paragraph(legenda, E["leg"])])]


def _lista(E, itens, numerada=False):
    return ListFlowable([ListItem(Paragraph(t, E["li"]), leftIndent=14) for t in itens], bulletType="1" if numerada else "bullet",
                        start="1" if numerada else None, bulletFontName="SS-B", bulletFontSize=10, leftIndent=16, bulletColor=VERDE)


def _quadro(E, texto):
    t = Table([[Paragraph(texto, E["nota"])]], colWidths=[170 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), AMB_BG), ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor("#C99A06")),
                           ("LEFTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return [t, Spacer(1, 8)]


def preparar(cap, e2e):
    """Recortes para o guia: as capturas do teste de ponta a ponta (SEEU fictício, pasta e2e) e a tela de extensões (cap/ext_2.png),
    com o Modo do desenvolvedor e o Carregar sem compactação marcados em vermelho. Grava g_*.png em cap."""
    from PIL import Image, ImageDraw
    im = Image.open(os.path.join(cap, "ext_2.png")).convert("RGB")
    k = im.size[0] / 2560.0
    topo = im.crop((0, 0, im.size[0], int(230 * k))).copy()
    d = ImageDraw.Draw(topo)
    for b in ((2250, 22, 2550, 90), (40, 128, 300, 210)):
        d.rounded_rectangle(tuple(int(x * k) for x in b), radius=14, outline=(214, 40, 40), width=7)
    topo.save(os.path.join(cap, "g_ext_topo.png"))
    im.crop(tuple(int(x * k) for x in (680, 440, 1495, 868))).save(os.path.join(cap, "g_ext_card.png"))
    for src, fr, dst in (("painel_S035.png", (0, 0, 1, 1), "g_visao.png"), ("painel_S141.png", (0, 0.07, 0.71, 0.32), "g_chips.png"),
                         ("chips_checklist_S001.png", (0, 0.08, 0.66, 0.48), "g_checklist.png"), ("chips_barra_fixa.png", (0, 0, 0.71, 0.12), "g_barra.png"),
                         ("painel_S035.png", (0.712, 0, 1, 1), "g_painel.png"), ("painel_ficha.png", (0.712, 0.05, 1, 0.5), "g_ficha.png"),
                         ("movimentacoes.png", (0, 0.42, 0.72, 0.75), "g_movs.png"), ("previa_documento.png", (0, 0, 0.71, 1), "g_previa.png")):
        p = os.path.join(e2e, src)
        if os.path.isfile(p):
            x = Image.open(p).convert("RGB")
            w, h = x.size
            x.crop((int(w * fr[0]), int(h * fr[1]), int(w * fr[2]), int(h * fr[3]))).save(os.path.join(cap, dst))


def _rodape(c, doc):
    c.saveState()
    c.setFont("SS", 8.5)
    c.setFillColor(TX2)
    c.drawString(20 * mm, 12 * mm, "APTO SEEU · guia de instalação e uso")
    c.drawRightString(190 * mm, 12 * mm, "página %d" % doc.page)
    c.restoreState()


def gerar(destino, cap, versao):
    _fontes()
    E = _estilos()
    L = 170 * mm
    s = []
    selo = os.path.join(RAIZ, "extensao_seeu", "icones", "128.png")
    s += [_img(selo, 22 * mm), Spacer(1, 6),
          Paragraph("APTO SEEU", E["capa"]),
          Paragraph("Guia de instalação e uso · versão %s" % versao, E["sub"]),
          Paragraph("A extensão mostra, na própria página do processo no SEEU, a análise da execução com as regras do APTO: os marcos "
                    "(data-base, progressão, livramento, término), os benefícios (indulto, comutação, saída temporária, progressão "
                    "antecipada, prescrição, extinção) e os pontos a conferir, cada um com a conta e o fundamento. Também destaca as "
                    "movimentações pelo conteúdo e mostra os documentos ao passar o mouse.", E["p"]),
          Paragraph("Não é preciso ter o APTO instalado. A extensão só <b>lê</b> o SEEU, com a sua sessão: não clica, não peticiona, não "
                    "junta nem altera nada. Os cálculos rodam no seu computador; nada é enviado a outro lugar.", E["p"])]
    s += _quadro(E, "<b>Ferramenta de apoio.</b> Verde significa que há certeza; amarelo, que é preciso conferir. Confira sempre nos autos "
                    "antes de peticionar.")

    s += [Paragraph("1. Instalar no Chrome", E["h1"]),
          _lista(E, ["Descompacte o arquivo <b>apto_seeu_%s.zip</b> numa pasta que não vá ser apagada (por exemplo, <i>Documentos\\APTO SEEU</i>). "
                     "Dentro dela fica a pasta <b>apto_seeu</b>." % versao,
                     "No Chrome, abra o endereço <b>chrome://extensions</b> (digite na barra de endereços e tecle Enter).",
                     "Ligue o <b>Modo do desenvolvedor</b>, no canto superior direito.",
                     "Clique em <b>Carregar sem compactação</b> e escolha a pasta <b>apto_seeu</b> (a que tem o arquivo manifest.json).",
                     "A extensão aparece na lista. Clique no ícone de quebra-cabeça, ao lado da barra de endereços, e fixe o <b>APTO SEEU</b> "
                     "(alfinete) para deixar o ícone sempre à vista.",
                     "Abra (ou recarregue) a página de um processo no SEEU."], numerada=True),
          Spacer(1, 6)]
    s += _figura(E, cap, "g_ext_topo.png", L, "Tela de extensões do Chrome: o Modo do desenvolvedor (à direita) e o botão Carregar sem compactação "
                                             "(à esquerda). Em português, os nomes aparecem como no texto.")
    s += _figura(E, cap, "g_ext_card.png", 92 * mm, "A extensão carregada. O botão de recarregar (seta circular) atualiza a extensão depois de trocar a pasta por uma versão nova.")
    s += [Paragraph("No <b>Microsoft Edge</b>, o caminho é o mesmo: <b>edge://extensions</b>, ligar o <i>Modo de desenvolvedor</i> e "
                    "<i>Carregar sem pacote</i>.", E["p"]),
          Paragraph("<b>Atualizar:</b> substitua o conteúdo da pasta apto_seeu pelo da versão nova e clique no botão de recarregar (seta circular) da extensão, na tela de extensões. "
                    "<b>Remover:</b> botão Remover na mesma tela.", E["p"])]
    s += _quadro(E, "Se a sua instituição controla o Chrome (\"navegador gerenciado\"), o Modo do desenvolvedor pode estar bloqueado: nesse caso, "
                    "peça ao suporte de TI para liberar a instalação.")

    s += [PageBreak(), Paragraph("2. Na página do processo", E["h1"]),
          Paragraph("Ao abrir um processo, a extensão busca em segundo plano o <b>Relatório da Situação Processual Executória (RSPE)</b> "
                    "que o próprio SEEU gera e o lê com as regras do APTO. A primeira análise depois de abrir o navegador leva alguns "
                    "segundos (o motor de cálculo é carregado uma vez); as seguintes, cerca de um segundo.", E["p"])]
    s += _figura(E, cap, "g_visao.png", L, "Visão geral (SEEU fictício): os chips logo abaixo do número do processo e o painel à direita.")
    s += [Paragraph("Chips abaixo do número do processo", E["h2"]),
          _lista(E, ["<b>Regime e marcos</b>: data-base, progressão, livramento e término. Progressão ou livramento <b>vencido</b> fica em "
                     "vermelho (!); a até 60 dias, em amarelo (relógio). Clique num chip para ver quanto falta e a fração.",
                     "<b>Benefícios</b>: saída temporária, progressão antecipada, indulto, comutação, extinção, prescrição, remição pendente "
                     "e restritiva de direitos. Verde: cabe; amarelo: a conferir. Clique para abrir o cartão no painel.",
                     "Em <b>saída temporária</b> e <b>progressão antecipada</b>, parar o mouse mostra o checklist dos requisitos "
                     "(cada requisito marcado como atendido, não atendido ou a conferir).",
                     "<b>N conferir</b> abre o painel."])]
    s += _figura(E, cap, "g_chips.png", L, "Chips do regime, dos marcos e dos benefícios.")
    s += _figura(E, cap, "g_checklist.png", 130 * mm, "Checklist dos requisitos ao passar o mouse.")
    s += [Paragraph("Barra fixa ao rolar a página", E["h2"]),
          Paragraph("Ao rolar a página, uma barra fixa no alto mantém o número do processo, o nome do assistido e os chips. "
                    "<b>Clique no número ou no nome para copiar.</b>", E["p"])]
    s += _figura(E, cap, "g_barra.png", L, "Barra fixa: clique no número ou no nome para copiar.")

    s += [PageBreak(), Paragraph("3. O painel lateral", E["h1"]),
          _lista(E, ["<b>Para conferir</b>: um cartão por ponto, com o que conferir. <i>Conta e fundamento</i> abre a conta e a base legal.",
                     "<b>Copiar fundamento</b>: copia o texto corrido, pronto para colar na petição, com a base legal no fim.",
                     "<b>Confere</b>: o que tem certeza. <b>Não cabe</b> (recolhido): as hipóteses afastadas, com o motivo.",
                     "Indulto ou comutação <b>já decididos</b> no SEEU não aparecem como pendência.",
                     "<b>Ler de novo</b> (seta circular, no alto do painel) refaz a leitura; a seta para a direita (ou Esc) <b>recolhe</b> o painel numa lingueta na borda, com a contagem do "
                     "que falta conferir. A escolha fica lembrada.",
                     "O resultado fica guardado por 10 minutos, só nesta sessão do navegador: trocar de aba no SEEU não refaz a leitura."])]
    tab = Table([[_img(os.path.join(cap, "g_painel.png"), 62 * mm) if os.path.isfile(os.path.join(cap, "g_painel.png")) else "",
                  _img(os.path.join(cap, "g_ficha.png"), 62 * mm) if os.path.isfile(os.path.join(cap, "g_ficha.png")) else ""]],
                colWidths=[85 * mm, 85 * mm])
    tab.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    s += [tab, Paragraph("À esquerda, o painel; à direita, a ficha disciplinar carregada (linha verde no topo).", E["leg"]),
          Paragraph("Ficha disciplinar do SIAPEN", E["h2"]),
          Paragraph("O que depende da ficha (falta grave, conduta, trabalho) fica <b>a conferir</b> até ela ser lida. Clique em "
                    "<b>Carregar a ficha (PDF)</b> ou arraste o PDF da ficha para o painel. A ficha é lida no seu computador e fica só "
                    "nesta sessão do navegador; ficha de outra pessoa não é usada.", E["p"]),
          Paragraph("Resumo para o assistido", E["h2"]),
          Paragraph("<b>Resumo para o assistido</b> monta o texto em linguagem simples. Escolha onde é o atendimento (na unidade "
                    "prisional, com o canhoto; ou fora, sem canhoto), confira e edite, e clique em <b>Imprimir</b>: o resumo abre numa "
                    "aba e a impressão já é pedida.", E["p"])]

    s += [PageBreak(), Paragraph("4. Movimentações", E["h1"]),
          Paragraph("Na aba <b>Movimentações</b>, cada evento ganha cor e etiqueta pelo <b>conteúdo</b> (o realce do SEEU colore só por "
                    "quem movimentou):", E["p"])]
    cores = [("Decisão", "#1F4E8C", "#fff"), ("Despacho", "#D6E7F7", "#173F6B"), ("MP", "#B3261E", "#fff"), ("DPE", "#1D7A4A", "#fff"),
             ("ADV", "#6B3FA0", "#fff"), ("Depen", "#F2D35B", "#4D3B00"), ("Cartório", "#F6CDAF", "#6B2C05"), ("Audiência", "#0E7490", "#fff")]
    ct = Table([[Paragraph('<font color="%s"><b>%s</b></font>' % (tc, n), ParagraphStyle("c", fontName="SS-B", fontSize=9.5, leading=12,
                                                                                       alignment=1)) for n, _, tc in cores]],
               colWidths=[L / len(cores)] * len(cores))
    ct.setStyle(TableStyle([("BACKGROUND", (i, 0), (i, 0), colors.HexColor(bg)) for i, (_, bg, _) in enumerate(cores)] +
                           [("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                            ("LINEAFTER", (0, 0), (-2, 0), 2, colors.white)]))
    s += [ct, Spacer(1, 8),
          _lista(E, ["Movimentações <b>sem arquivo vinculado</b> ficam esmaecidas; a barra acima da tabela permite <b>ocultá-las</b> ou "
                     "mostrá-las.",
                     "Clique numa categoria (com a contagem) para ver só ela; <b>Mostrar todas</b> desfaz. A escolha fica lembrada."])]
    s += _figura(E, cap, "g_movs.png", L, "Destaques das movimentações e a barra de filtros (SEEU fictício).")
    s += [Paragraph("Prévia dos documentos", E["h2"]),
          Paragraph("Pare o mouse sobre o link de um documento (por exemplo, <i>online.pdf</i> no detalhe da movimentação, aberto pelo "
                    "\"+\"): a prévia abre ao lado, sem nova aba. <b>Expandir</b> amplia a prévia na página; Esc ou o X fecha. Clicar no "
                    "link continua baixando o arquivo, como sempre.", E["p"])]
    s += _figura(E, cap, "g_previa.png", 140 * mm, "Prévia do documento ao passar o mouse no link.")
    s += [Paragraph("Documentos no 2º monitor", E["h2"]),
          Paragraph("No ícone da extensão (ao lado da barra de endereços), ligue <b>Abrir os documentos no 2º monitor</b>: o clique no link "
                    "de um documento passa a abri-lo numa janela no outro monitor, reaproveitada a cada documento.", E["p"])]
    s += _figura(E, cap, "popup.png", 80 * mm, "As opções da extensão.")

    s += [PageBreak(), Paragraph("5. Situações especiais", E["h1"]),
          Paragraph("Restritiva de direitos e demais medidas", E["h2"]),
          Paragraph("Quando a página mostra <b>Medidas Diversas da Prisão (N)</b>, a extensão lê a aba em segundo plano e gera o relatório "
                    "de cada medida (o mesmo do botão <i>Gerar Relatório</i>). Cada condição vira um cartão com o que falta cumprir e "
                    "quanto disso já venceu: <b>prestação pecuniária</b> (parcelas vencidas sem pagamento e pagas a menor) e "
                    "<b>prestação de serviços à comunidade</b> (horas devidas até hoje x cumpridas, meses sem registro). O chip mostra "
                    "<i>Restritiva de direitos</i>.", E["p"]),
          Paragraph("ANPP, transação penal e suspensão condicional do processo", E["h2"]),
          Paragraph("Pelo <b>assunto principal</b> da capa, a extensão reconhece a medida sem condenação: não aponta \"sem condenação\" "
                    "nem \"não iniciou\", e mostra que as condições se acompanham na aba Medidas Diversas da Prisão.", E["p"]),
          Paragraph("6. Privacidade e segurança", E["h1"]),
          _lista(E, ["Só leitura: a extensão faz os mesmos pedidos que você faria ao clicar (o relatório, a aba de medidas, o documento), "
                     "com a sua sessão do SEEU.",
                     "Permissões: o SEEU e o servidor de arquivos do SEEU; guardar as opções; o motor de cálculo; ver os monitores (só "
                     "para a opção do 2º monitor).",
                     "Os resultados e a ficha ficam só na sessão do navegador (somem ao fechá-lo). Nada é enviado a outro servidor."]),
          Paragraph("7. Problemas", E["h1"]),
          _lista(E, ["<b>O painel não aparece</b>: confira se a extensão está ligada (chrome://extensions) e a opção <i>Mostrar o painel</i> "
                     "no ícone; recarregue a página do processo.",
                     "<b>\"Não foi possível ler o processo\"</b>: a sessão do SEEU pode ter expirado; recarregue a página e clique em Ler de novo (seta circular).",
                     "<b>Diagnóstico</b>: no aviso de erro, <i>Copiar o diagnóstico</i> copia só a estrutura da leitura (sem nenhum dado do "
                     "processo ou da pessoa). Envie-o a quem mantém a extensão."])]
    s += _quadro(E, "Os cálculos seguem as regras do APTO e devem ser conferidos nos autos. Em caso de divergência com o SEEU, o painel aponta "
                    "o ponto a conferir - não presume datas nem frações.")

    doc = SimpleDocTemplate(destino, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=20 * mm,
                            title="APTO SEEU - guia de instalação e uso", author="APTO")
    doc.build(s, onFirstPage=_rodape, onLaterPages=_rodape)
    return destino
