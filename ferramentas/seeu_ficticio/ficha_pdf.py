"""Ficha disciplinar do SIAPEN fictícia, em PDF, no layout que o leitor do APTO espera (o mesmo do teste_ficha_rev4):
cabeçalho em Times 10 com rótulos em negrito, "HISTÓRICO - CONDUTA" em 12, lançamentos em Times 8, o "histórico antigo" em
Times 10 que vem na camada de texto (e o leitor descarta), rodapé em 7 pt e "Nome: ... Projeto SIAPEN, Impresso em ...".
Várias páginas quando há muitos lançamentos. Nenhum dado real. Serve aos testes de paridade do leitor de ficha no navegador
(pdf.js) com o do APTO (pdfplumber) e ao teste de ponta a ponta do painel.
Uso: python ficha_pdf.py saida.pdf  (gera uma ficha de exemplo)"""
import sys

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas


def gerar(caminho, nome="FULANO DE TAL EXEMPLO", cpf="000.000.000-00", filiacao="MARIA EXEMPLO DA SILVA \\ JOSÉ EXEMPLO",
          nascimento="01/01/1990", prisao="01/03/2024", entrada="02/03/2024", unidade="ESTABELECIMENTO PENAL FICTÍCIO",
          conduta="BOA", eventos=(), impresso="13/10/2026", oculto=True, por_pagina=14):
    W, H = landscape(A4)
    c = canvas.Canvas(caminho, pagesize=(W, H))

    def txt(x, top, s, font="Times-Roman", size=8):
        c.setFont(font, size)
        c.drawString(x, H - top - size, s)

    eventos = list(eventos)
    paginas = [eventos[i:i + por_pagina] for i in range(0, len(eventos), por_pagina)] or [[]]
    for k, evs in enumerate(paginas):
        topo = 120
        if k == 0:
            txt(138, 18, "AGÊNCIA ESTADUAL DE ADMINISTRAÇÃO DO SISTEMA PENITENCIÁRIO - AGEPEN", "Times-Bold", 10)
            txt(138, 32, "SISTEMA INTEGRADO DE ADMINISTRAÇÃO PENITENCIÁRIA - SIAPEN", "Times-Bold", 10)
            txt(348, 103, "FICHA DISCIPLINAR (ID: 1 )", "Times-Bold", 12)
            txt(45, 126, "Nome:", "Times-Bold", 10); txt(90, 126, nome, size=10); txt(420, 126, "RGI:", "Times-Bold", 10); txt(450, 126, "12345", size=10)
            txt(45, 143, "CPF:", "Times-Bold", 10); txt(80, 143, cpf, size=10)
            txt(45, 160, "Filiação:", "Times-Bold", 10); txt(95, 160, filiacao, size=10)
            txt(45, 177, "Data Nascimento:", "Times-Bold", 10); txt(130, 177, nascimento, size=10)
            txt(45, 283, "Data Prisão:", "Times-Bold", 10); txt(120, 283, prisao, size=10); txt(200, 283, "Procedência:", "Times-Bold", 10)
            txt(280, 283, "DP FICTÍCIA", size=10); txt(400, 283, "Condenação:", "Times-Bold", 10); txt(470, 283, "CONDENADO", size=10)
            txt(45, 300, "Data Entrada:", "Times-Bold", 10); txt(120, 300, entrada, size=10); txt(200, 300, "Unidade Penal:", "Times-Bold", 10)
            txt(280, 300, unidade, size=10)
            txt(332, 358, "HISTÓRICO - CONDUTA: %s" % conduta, "Times-Bold", 12)
            topo = 380
            if oculto:
                # histórico antigo em 10 pt na altura dos lançamentos (cortado na impressão; o leitor descarta)
                txt(31, topo + 11, "Em 21/09/10 Classificado conduta disciplinar em ÓTIMA em atendimento ao Mutirão", size=10)
        y = topo
        for d, t in evs:
            txt(96, y, "%s - %s" % (d, t) if d else "- " + t)
            y += 14.3
        txt(407, 525, "RUA: EXEMPLO", size=7); txt(402, 533, "CEP: . - -", size=7); txt(397, 542, "FONE: - Fax: -", size=7)
        txt(36, 552, "Nome:", "Times-Bold", 10)
        txt(72, 552, "%s - DEFENSOR EXEMPLO Projeto SIAPEN, Impresso em %s - 14:43:22, Pag. %d/%d" % (nome, impresso, k + 1, len(paginas)))
        c.showPage()
    c.save()
    return caminho


EXEMPLO = [("02.03.2024", "Entrada na Unidade Penal: ESTABELECIMENTO PENAL FICTÍCIO, Procedente: DP FICTÍCIA, Conforme OF 1/2024."),
           ("10.04.2024", "TRABALHO: Iniciou atividade laboral, no setor de trabalho COZINHA, conforme documento CI 1/2024."),
           ("05.10.2024", "Emitido ATESTADO DE TRABALHO PRISIONAL Nº 105/2024; COZINHA; DATA INICIAL: 10/04/2024; DATA FINAL: 30/09/2024; DIAS TRABALHADOS: 150; DIAS REMIDOS: 50."),
           ("", "CONSELHO DISCIPLINAR: FOI CONCLUSO PROCESSO - PADIC Nº 31/072306/2025, REFERENTE AO FATO OCORRIDO EM 05/03/2025, COMETEU FALTA DISCIPLINAR DE NATUREZA GRAVE."),
           ("20.06.2025", "Classificado conduta disciplinar em BOA.")]

if __name__ == "__main__":
    print(gerar(sys.argv[1], eventos=EXEMPLO))
