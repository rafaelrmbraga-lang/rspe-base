"""Relatório de pena alternativa fictício em PDF, no leiaute do SEEU (aba Medidas Diversas da Prisão > Gerar Relatório): cabeçalho,
qualificação, a medida (substituição por restritiva de direitos) e as condições com a tabela de cumprimentos. Para a leitura do
relatório no navegador (pdf.js) e no APTO (pdfplumber) e para o teste de ponta a ponta do painel."""
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

EXEMPLO = {
    "processo": "9900001-00.2026.8.12.0001", "nome": "FULANO DE TAL EXEMPLO", "pena": "3a0m0d - PENA ORIGINÁRIA", "inicio": "30/10/2025",
    "pecuniaria": {"valor": 3306.0, "parcelas": [("30/11/2025", "20/11/2025", 330.6, 330.6), ("30/12/2025", "20/12/2025", 330.6, 300.6),
                                                 ("30/01/2026", "", 330.6, None), ("28/02/2026", "", 330.6, None)], "termino": "28/02/2026",
                   "status": "VERIFICAR"},
    "psc": {"horas": 120.0, "mes": 10.0, "meses": [("30/11/2025", "28/11/2025", 10.0, 10.0), ("30/12/2025", "29/12/2025", 10.0, 6.0),
                                                   ("30/01/2026", "", 10.0, None), ("28/02/2027", "", 10.0, None)], "termino": "30/10/2026",
            "status": "ATIVA"},
}


def _br(v):
    return ("{:,.2f}".format(v)).replace(",", "X").replace(".", ",").replace("X", ".")


def linhas(d):
    L = ["PODER JUDICIÁRIO", "TJMS - COMARCA DE CAMPO GRANDE", "2ª VARA DE EXECUÇÃO PENAL DE CAMPO GRANDE",
         "Número Único: %s (ATIVO)" % d["processo"], "Local de Prisão (Sistema):", "QUALIFICAÇÃO", "Código: 0000000", "Nome: %s" % d["nome"],
         "SUBSTITUIÇÃO DE PENA PRIVATIVA POR RESTRITIVA DE DIREITO", "Pena Substituída: %s" % d["pena"], "Incidente:",
         "Data de Início: %s" % d["inicio"], "Data de Término:", "Status: ATIVA", "CONDIÇÕES"]
    pc = d.get("pecuniaria")
    if pc:
        pago = sum(x[3] or 0 for x in pc["parcelas"])
        L += ["Prestação pecuniária", "Status: %s" % pc["status"], "Data Provável de Término: %s Data de Término Efetiva:" % pc["termino"],
              "Observação:", "Valor: %.2f" % pc["valor"], "Nº de Parcelas Previsto: %d" % len(pc["parcelas"]), "Destinatário: Conta Judicial",
              "Controle de Pagamentos:", "Total Previsto: R$ %s" % _br(pc["valor"]), "Total Pago: R$ %s" % _br(pago),
              "Total A Pagar: R$ %s" % _br(pc["valor"] - pago), "Cumprimentos:",
              "Data Prevista de Cumprimento Data de Cumprimento Efetivo Valor Previsto Valor Pago Válido"]
        for prev, efet, vp, vg in pc["parcelas"]:
            L.append(" ".join(x for x in (prev, efet, "R$ " + _br(vp), "%.2f" % vg if vg is not None else "", "" if vg is not None else "Sim") if x))
    ps = d.get("psc")
    if ps:
        feitas = sum(x[3] or 0 for x in ps["meses"])
        L += ["Prestação de serviços à comunidade", "Status: %s" % ps["status"], "Data Provável de Término: %s Data de Término Efetiva:" % ps["termino"],
              "Qtde de Horas: %.2f" % ps["horas"], "Entidade Beneficiada:", "Qtde de Horas por Mês: %.1f" % ps["mes"], "Observação:",
              "Controle de Horas Detalhado:", "Total Previsto: %s" % _br(ps["horas"]), "Total Pago: %s" % _br(feitas),
              "Total A Pagar: %s" % _br(ps["horas"] - feitas), "Cumprimentos:",
              "Data Prevista de Cumprimento Data de Cumprimento Efetivo Horas Previstas Horas Trabalhadas Válido"]
        for prev, efet, hp, ht in ps["meses"]:
            L.append(" ".join(x for x in (prev, efet, "%.2f" % hp, "%.2f" % ht if ht is not None else "", "" if ht is not None else "Sim") if x))
    return L


def gerar(caminho, d=None, por_pagina=60):
    d = d or EXEMPLO
    L = linhas(d)
    c = canvas.Canvas(caminho, pagesize=A4, invariant=1)
    larg, alt = A4
    cab = L[:3]
    corpo = L[3:]
    for i in range(0, len(corpo), por_pagina):
        y = alt - 40
        for ln in cab + corpo[i:i + por_pagina]:
            negrito = ln.isupper() and len(ln) > 8
            c.setFont("Helvetica-Bold" if negrito else "Helvetica", 8)
            c.drawString(36, y, ln)
            y -= 11.5
        c.showPage()
    c.save()
    return caminho
