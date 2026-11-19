"""RSPE fictício em PDF (texto no formato do relatório do SEEU, em páginas A4, fonte Helvetica com negrito nos títulos de
quadro), para a paridade da leitura do RSPE no navegador (pdf.js) com a do APTO (pdfplumber)."""
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

TITULOS = ("PROCESSO DE EXECUÇÃO", "CÁLCULOS DA PENA", "PROCESSOS CRIMINAIS", "EVENTOS DE INÍCIO", "INCIDENTES", "Fim do Relatório")


def gerar(caminho, texto, linhas_por_pagina=70):
    c = canvas.Canvas(caminho, pagesize=A4, invariant=1)
    larg, alt = A4
    linhas = texto.split("\n")
    for i in range(0, len(linhas), linhas_por_pagina):
        y = alt - 36
        for ln in linhas[i:i + linhas_por_pagina]:
            negrito = ln.strip().startswith(TITULOS)
            c.setFont("Helvetica-Bold" if negrito else "Helvetica", 8 if negrito else 7.5)
            x = 30
            # rótulo e valor em colunas, como no relatório ("Rótulo:   valor")
            if ":" in ln and not negrito and len(ln) < 120:
                rot, val = ln.split(":", 1)
                c.drawString(x, y, rot + ":")
                c.drawString(x + max(110, c.stringWidth(rot + ": ", "Helvetica", 7.5)), y, val.strip())
            else:
                c.drawString(x, y, ln)
            y -= 10.5
        c.showPage()
    c.save()
    return caminho
