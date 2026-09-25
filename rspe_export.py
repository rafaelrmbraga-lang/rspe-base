# -*- coding: utf-8 -*-
"""Exportação das abas para Excel e PDF, com o mesmo visual do programa."""

from datetime import datetime

import rspe_scraper as rs
import rspe_view as rv

NAVY = "#1F2937"
PRI = "#00602C"
TX2 = "#475467"
LINE = "#E6E9EF"
ZEBRA = "#F9FAFB"
DOT = {"vermelho": "#E5484D", "laranja": "#F97316", "amarelo": "#F5A524", "vencido": "#E5484D", "verde": "#17B26A", "cinza": "#98A2B3", "azul": "#2563EB"}


def exportar_xlsx(modelos, saida, abas):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    fino = Side(style="thin", color=LINE.lstrip("#"))
    wb = Workbook()
    wb.remove(wb.active)
    for aid in abas:
        if aid == "completo" or aid not in rv.ABA_POR_ID:
            continue
        spec = rv.ABA_POR_ID[aid]
        ws = wb.create_sheet(spec["titulo"].replace("/", "-")[:31])
        cols, modelos_aba = _linhas_export(spec, modelos)
        ws.append([c[1] for c in cols])
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor=NAVY.lstrip("#"))
            cell.alignment = Alignment(wrap_text=True, vertical="center")
        ws.row_dimensions[1].height = 22
        pil = dict(spec["pilulas"], **spec.get("sub_pilulas", {}))
        for m in modelos_aba:
            ws.append([m.get(k + "_full", m.get(k, "")) for k, _, _ in cols])
            cor = m.get(spec["cor"], "") if spec["cor"] else ""
            for cell in ws[ws.max_row]:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
                cell.border = Border(bottom=fino)
                if cor:
                    cell.fill = PatternFill("solid", fgColor=rv.CORES[cor][0].lstrip("#"))
            for k, pk in pil.items():
                if k not in [c[0] for c in cols]:
                    continue
                idx = [c[0] for c in cols].index(k) + 1
                c = m.get(pk, "")
                if c:
                    ws.cell(row=ws.max_row, column=idx).font = Font(bold=True, color=rv.CORES[c][1].lstrip("#"))
        for i, c in enumerate(cols, 1):
            ws.column_dimensions[get_column_letter(i)].width = max(10, min(50, c[2] * 1.5))
        ws.freeze_panes = "B2"
        ws.auto_filter.ref = ws.dimensions
    if "completo" in abas:
        ws = wb.create_sheet("Completo")
        ws.append([rs.TITULOS_BONITOS.get(c, c) for c in rs.COLUNAS])
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor=NAVY.lstrip("#"))
        for m in modelos:
            r = m["_bruto"]
            ws.append([r.get(c, "") for c in rs.COLUNAS])
        ws.freeze_panes = "B2"
    wb.save(saida)


def _com_pedido(spec, modelos):
    """Coluna "Pedido": 'feito em dd/mm/aaaa (observação)' da aba, ou vazio."""
    out = []
    for m in modelos:
        P = (m.get("pedidos") or {}).get(spec["id"])
        d = dict(m)
        d["pedido"] = ("feito em %s%s" % (P.get("data", ""), (" (%s)" % P["obs"]) if P.get("obs") else "")) if P else ""
        out.append(d)
    return out


def _linhas_export(spec, modelos):
    """Abas expansíveis (prescrição) exportam uma linha por crime."""
    modelos = _com_pedido(spec, modelos)
    if not spec.get("sub"):
        return spec["cols"], modelos
    datas = {"fato", "denuncia", "sentenca", "transito", "ppe_termo"}
    cols = [("nome", "Nome", 16), ("proc", "Nº da execução", 14)] + [(k, t, 12 if k in datas else p) for k, t, p in spec["sub_cols"]] + (
        [("pedido", "Pedido", 10)] if any(c[0] == "pedido" for c in spec["cols"]) else [])
    linhas = []
    for m in modelos:
        for s in m.get(spec["sub"], []):
            d = dict(m)
            d.update(s)
            if spec["id"] == "presc":
                d[spec["cor"]] = s.get("ppe_cor") if s.get("ppe_cor") == "vermelho" or s.get("retro_cor") != "vermelho" else s.get("retro_cor")
            elif "cor" in s:
                d[spec["cor"]] = s.get("cor") or ""
            linhas.append(d)
    return cols, linhas


def exportar_pdf(modelos, saida, nome_base, abas):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak

    W, H = landscape(A4)
    ML = 14 * mm
    gerado = datetime.now().strftime("%d/%m/%Y %H:%M")
    C = colors.HexColor

    def moldura(canvas, doc):
        canvas.saveState()
        # marca + título discreto no topo
        canvas.setFillColor(C(PRI))
        canvas.roundRect(ML, H - 13 * mm, 7 * mm, 7 * mm, 1.8 * mm, stroke=0, fill=1)
        canvas.setStrokeColor(colors.white)
        canvas.setLineWidth(1.1)
        for i, w in enumerate((3.6, 3.6, 2.4)):
            y = H - 8.2 * mm - i * 1.6 * mm
            canvas.line(ML + 1.7 * mm, y, ML + 1.7 * mm + w * mm, y)
        canvas.setFillColor(C(NAVY))
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(ML + 9.5 * mm, H - 11 * mm, "RSPE Base")
        canvas.setFont("Helvetica", 8.5)
        canvas.setFillColor(C(TX2))
        canvas.drawString(ML + 31 * mm, H - 11 * mm, "Execução penal · SEEU")
        canvas.drawRightString(W - ML, H - 11 * mm, "%s   ·   %s" % (nome_base, gerado))
        canvas.setStrokeColor(C(LINE))
        canvas.setLineWidth(0.6)
        canvas.line(ML, H - 15.5 * mm, W - ML, H - 15.5 * mm)
        # rodapé
        canvas.setFillColor(C("#98A2B3"))
        canvas.setFont("Helvetica", 7.2)
        canvas.drawString(ML, 7.5 * mm, "Datas conforme o SEEU (RSPE); indulto, comutação e prescrição calculados pelo programa.  "
                                        "Falta (12 meses) = indícios no RSPE, conferir o PAD.  Indulto: Decretos 11.302/2022, 12.338/2024 e 12.790/2025.")
        canvas.drawRightString(W - ML, 7.5 * mm, "página %d" % doc.page)
        canvas.restoreState()

    doc = SimpleDocTemplate(saida, pagesize=landscape(A4), leftMargin=ML, rightMargin=ML,
                            topMargin=21 * mm, bottomMargin=14 * mm, title="RSPE Base - %s" % nome_base, author="RSPE Base")
    st_cel = ParagraphStyle("cel", fontName="Helvetica", fontSize=7.6, leading=9.4, textColor=C("#101828"))
    st_neg = ParagraphStyle("neg", parent=st_cel, fontName="Helvetica-Bold")
    st_mut = ParagraphStyle("mut", parent=st_cel, textColor=C("#98A2B3"))
    st_cab = ParagraphStyle("cab", fontName="Helvetica-Bold", fontSize=6.9, leading=8.5, textColor=C(TX2))
    st_tit = ParagraphStyle("tit", fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=C(NAVY))
    st_sub = ParagraphStyle("sub", fontName="Helvetica", fontSize=8.5, leading=11, textColor=C(TX2))
    largura = W - 2 * ML
    el = []
    primeiro = True
    for aid in abas:
        if aid not in rv.ABA_POR_ID:
            continue
        spec = rv.ABA_POR_ID[aid]
        cols, modelos_aba = _linhas_export(spec, modelos)
        pil = dict(spec["pilulas"], **spec.get("sub_pilulas", {}))
        if not primeiro:
            el.append(PageBreak())
        primeiro = False
        el.append(Paragraph(spec["titulo"], st_tit))
        el.append(Paragraph("%s  ·  referência: hoje, %s" % (rs.pl(len(modelos), "assistido", "assistidos"), rv.HOJE.strftime("%d/%m/%Y")), st_sub))
        el.append(Spacer(1, 6))

        # cartões de resumo
        rot = rv.ROTULO[spec["legenda"]]
        if spec["cor"]:
            cont = {}
            for m in modelos:
                c = m.get(spec["cor"], "")
                cont[c] = cont.get(c, 0) + 1
            cel, larg, est = [], [], [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 6),
                                     ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 8)]
            for i, (c, nome) in enumerate(rot.items()):
                if aid in ("ind",) and c == "":
                    continue
                texto = '<font color="%s">●</font>  <b>%d</b>  <font color="%s">%s</font>' % (DOT.get(c, "#CBD5E1"), cont.get(c, 0), TX2, nome)
                cel.append(Paragraph(texto, ParagraphStyle("st", parent=st_cel, fontSize=9, leading=11)))
                larg.append(largura / max(4, len(rot)) - 2 * mm)
                est += [("BOX", (i, 0), (i, 0), 0.5, C(LINE)), ("BACKGROUND", (i, 0), (i, 0), colors.white)]
            t = Table([cel], colWidths=larg, hAlign="LEFT", spaceAfter=8)
            t.setStyle(TableStyle(est))
            el.append(t)

        # tabela
        pesos = [c[2] + (6 if c[0] == "proc" else 3 if c[0] == "regime" else 0) for c in cols]
        larguras = [largura * p / sum(pesos) for p in pesos]
        dados = [[Paragraph(c[1].upper(), st_cab) for c in cols]]
        estilo = [
            ("BACKGROUND", (0, 0), (-1, 0), C("#F2F4F7")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, C("#D0D5DD")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 1), (-1, -1), 0.4, C(LINE)),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ]
        for i, m in enumerate(modelos_aba, 1):
            linha = []
            cor = m.get(spec["cor"], "") if spec["cor"] else ""
            for j, (k, _, _) in enumerate(cols):
                v = str(m.get(k + "_full", m.get(k, "")) or "")
                v = v.replace("&", "&amp;").replace("<", "&lt;")
                pk = pil.get(k)
                if pk and v:
                    pc = ("vermelho" if v.startswith("Sim") else "verde") if k == "imp" else m.get(pk, "")
                    v = '<font color="%s">●</font> <b><font color="%s">%s</font></b>' % (DOT.get(pc, "#CBD5E1"), rv.CORES[pc][1], v)
                elif k == "falta" and m.get("falta_sim"):
                    v = '<b><font color="%s">%s</font></b>' % (rv.CORES["vermelho"][1], v)
                elif k == "falta" and m.get("falta_apurar"):
                    v = '<b><font color="%s">%s</font></b>' % (rv.CORES["amarelo"][1], v)
                elif not v:
                    v = '<font color="#98A2B3">—</font>'
                linha.append(Paragraph(v, st_neg if j == 0 else st_cel))
            dados.append(linha)
            if cor:
                estilo.append(("BACKGROUND", (0, i), (-1, i), C(rv.CORES[cor][0])))
                estilo.append(("LINEBEFORE", (0, i), (0, i), 2.2, C(DOT[cor])))
            elif i % 2 == 0:
                estilo.append(("BACKGROUND", (0, i), (-1, i), C(ZEBRA)))
        t = Table(dados, colWidths=larguras, repeatRows=1)
        t.setStyle(TableStyle(estilo))
        el.append(t)

        # legenda
        el.append(Spacer(1, 8))
        leg = "     ".join('<font color="%s">●</font> <font color="%s">%s</font>' % (DOT[c], TX2, n) for c, n in rot.items() if c)
        el.append(Paragraph(leg, ParagraphStyle("leg", parent=st_cel, fontSize=8)))
    doc.build(el, onFirstPage=moldura, onLaterPages=moldura)


def exportar_providencias(linhas, saida, titulo):
    """Relatório de providências (pedidos e ofícios marcados na coluna Pedido) em Excel: resumo e lista."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Providências"
    ws.append([titulo])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append(["Gerado em %s · %d providência(s)" % (datetime.now().strftime("%d/%m/%Y %H:%M"), len(linhas))])
    ws.append([])
    cab = ["Data", "Assistido", "Nº da execução", "Benefício / assunto", "Providência", "Observação", "Registrado em"]
    ws.append(cab)
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=NAVY.lstrip("#"))
        cell.alignment = Alignment(vertical="center")
    for L in linhas:
        ws.append([L.get("data", ""), L.get("nome", ""), L.get("proc", ""), L.get("assunto", ""), L.get("tipo", ""), L.get("obs", ""), L.get("registrado", "")])
    for col, w in zip("ABCDEFG", (12, 34, 28, 26, 26, 40, 17)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A5"
    # resumo: providência x assunto
    rs_ = wb.create_sheet("Resumo")
    rs_.append(["Benefício / assunto", "Pedido nos autos", "Ofício à unidade prisional", "Outra providência", "Total"])
    for cell in rs_[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=NAVY.lstrip("#"))
    tipos = ["Pedido nos autos", "Ofício à unidade prisional", "Outra providência"]
    assuntos = []
    for L in linhas:
        if L.get("assunto") not in assuntos:
            assuntos.append(L.get("assunto"))
    for a in assuntos:
        q = [sum(1 for L in linhas if L.get("assunto") == a and L.get("tipo") == t) for t in tipos]
        rs_.append([a] + q + [sum(q)])
    q = [sum(1 for L in linhas if L.get("tipo") == t) for t in tipos]
    rs_.append(["Total"] + q + [sum(q)])
    for cell in rs_[rs_.max_row]:
        cell.font = Font(bold=True)
    for col, w in zip("ABCDE", (28, 18, 26, 18, 10)):
        rs_.column_dimensions[col].width = w
    wb.save(saida)

