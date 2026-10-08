# -*- coding: utf-8 -*-
"""Exportação das abas para Excel e PDF, com o mesmo visual do programa."""

from datetime import datetime

import rspe_scraper as rs
import rspe_view as rv

NAVY = "#0B3B22"
PRI = "#00602C"
TX2 = "#5F6662"
LINE = "#D5DAD6"
ZEBRA = "#FAFBFA"
DOT = {"vermelho": "#A33A36", "laranja": "#B5651D", "amarelo": "#C49A3A", "vencido": "#A33A36", "verde": "#2F7A4F", "cinza": "#AEB5B0", "azul": "#4A6A8A"}


def _sem_formula(ws):
    """O openpyxl grava como fórmula todo texto que começa com "=": nome, crime, motivo (do PDF) ou observação digitada
    viraria fórmula no Excel. A última linha da folha fica toda como texto."""
    for cell in ws[ws.max_row]:
        if isinstance(cell.value, str) and cell.value.startswith("="):
            cell.data_type = "s"


def exportar_xlsx(modelos, saida, abas):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    fino = Side(style="thin", color=LINE.lstrip("#"))
    wb = Workbook()
    wb.remove(wb.active)
    for spec in [sp for aid in abas if aid != "completo" for sp in specs_export(aid)]:
        ws = wb.create_sheet((spec.get("folha") or spec["titulo"]).replace("/", "-")[:31])
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
            _sem_formula(ws)
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
            _sem_formula(ws)
        ws.freeze_panes = "B2"
    wb.save(saida)


def specs_export(aid):
    """Abas como a tela as mostra. A Prescrição sai em duas, uma por pretensão (executória e punitiva), com a cor, os cartões
    e as colunas de cada uma - a tela também mostra uma pretensão por vez; a cor da aba (presc_cor) mistura as duas."""
    if aid not in rv.ABA_POR_ID:
        return []
    a = rv.ABA_POR_ID[aid]
    if aid != "presc":
        return [a]
    base = [c for c in a["cols"] if c[0] in ("nome", "proc")]
    ped = [c for c in a["cols"] if c[0] == "pedido"]
    sub_base = [c for c in a["sub_cols"] if c[0] in ("crime", "proc_crim", "pena", "fato", "denuncia", "sentenca", "transito")]
    pe = dict(a, id="presc", aba="presc", titulo="Prescrição - pretensão executória", folha="Prescrição executória", cor="presc_ppe_cor", legenda="presc",
              cols=base + [("presc_ppe", "Pretensão executória", 16), ("presc_prox", "Prescrição em", 10)] + ped,
              pilulas={"presc_ppe": "presc_ppe_cor"}, sub_cor="ppe_cor",
              sub_cols=sub_base + [c for c in a["sub_cols"] if c[0] in ("prazo_ppe", "ppe_termo", "ppe_status")], sub_pilulas={"ppe_status": "ppe_cor"})
    pp = dict(a, id="presc", aba="presc", titulo="Prescrição - pretensão punitiva", folha="Prescrição punitiva", cor="presc_retro_cor", legenda="presc_pp",
              cols=base + [("presc_retro", "Pretensão punitiva", 16)] + ped,
              pilulas={"presc_retro": "presc_retro_cor"}, sub_cor="retro_cor",
              sub_cols=sub_base + [c for c in a["sub_cols"] if c[0] in ("prazo_ppp", "retro_status")], sub_pilulas={"retro_status": "retro_cor"})
    return [pe, pp]


def _ped_ref(m, aba):
    """Mesma referência da tela (ui.pedRef): o pedido marcado vale enquanto a situação da aba não mudar."""
    return {"prog": m.get("prog"), "liv": m.get("liv"), "ind": "|".join(str(m.get(k) or "") for k in ("i22", "i24", "c24", "i25", "c25")),
            "presc": (m.get("presc_ppe") or "") + "|" + (m.get("presc_prox") or ""), "ext": m.get("ext_termino"), "fd": m.get("fd_sit")}.get(aba) or ""


def pedido_pendente(m, aba):
    """Como na tela (ui.pedPendente): sem pedido marcado, ou a situação mudou depois dele."""
    P = m.get("pedidos") or {}
    if aba == "ind" and any(k.startswith("ind_") for k in P):
        return False
    p = P.get(aba)
    return (not p) or bool(p.get("ref") and p.get("ref") != _ped_ref(m, aba))


def contagem_cartoes(spec, modelos):
    """Cartões de resumo da aba, contados como na tela: por cor; quem já teve o pedido marcado (e a situação não mudou) sai da
    cor e entra em "Feito"."""
    tem_ped = any(c[0] == "pedido" for c in spec["cols"])
    cont = {}
    for m in modelos:
        if tem_ped and not pedido_pendente(m, spec["id"]):
            cont["__ped"] = cont.get("__ped", 0) + 1
            continue
        c = m.get(spec["cor"], "")
        cont[c] = cont.get(c, 0) + 1
    return cont


def nome_pedido(k):
    """Nome legível da providência: 'ind_2025' -> 'Indulto/comutação 2025'."""
    if k.startswith("ind_"):
        return "Indulto/comutação %s" % k[4:]
    return {"prog": "Progressão", "liv": "Livramento condicional", "ind": "Indulto/comutação", "presc": "Prescrição", "ext": "Extinção da pena",
            "fd": "Remição", "st": "Saída temporária"}.get(k, k)


def _txt_pedido(P):
    return "feito em %s%s" % (P.get("data", ""), (" (%s)" % P["obs"]) if P.get("obs") else "")


def _com_pedido(spec, modelos):
    """Coluna "Pedido": 'feito em dd/mm/aaaa (observação)' da aba, ou vazio. No indulto, o pedido é marcado por decreto
    (ind_<ano>): sai um por decreto, com o ano."""
    out = []
    for m in modelos:
        PP = m.get("pedidos") or {}
        P = PP.get(spec["id"])
        d = dict(m)
        txt = [_txt_pedido(P)] if P else []
        if spec["id"] == "ind":
            txt += ["%s: %s" % (nome_pedido(k), _txt_pedido(PP[k])) for k in sorted((k for k in PP if k.startswith("ind_") and PP[k]), reverse=True)]
        d["pedido"] = "; ".join(txt)
        out.append(d)
    return out


def _linhas_export(spec, modelos):
    """Abas expansíveis (prescrição) exportam uma linha por crime."""
    modelos = _com_pedido(spec, modelos)
    if not spec.get("sub"):
        return spec["cols"], modelos
    datas = {"fato", "denuncia", "sentenca", "transito", "ppe_termo"}
    # Ficha disciplinar: como na aba, as colunas do assistido (trabalho a atestar, estudo a requerer, situação) com a cor da
    # situação dele, e uma linha também para quem não tem item (em ordem, sem ficha); a cor do item fica na pílula da coluna
    fd = spec["id"] == "fd"
    pai = [c for c in spec["cols"] if c[0] in ("fd_atestar", "fd_estudo", "fd_sit")] if fd else []
    cols = [("nome", "Nome", 16), ("proc", "Nº da execução", 14)] + pai + [(k, t, 12 if k in datas else p) for k, t, p in spec["sub_cols"]] + (
        [("pedido", "Pedido", 10)] if any(c[0] == "pedido" for c in spec["cols"]) else [])
    linhas = []
    for m in modelos:
        subs = m.get(spec["sub"]) or []
        for s in subs:
            d = dict(m)
            d.update(s)
            if fd:
                pass  # a cor da linha é a da situação do assistido (fd_cor), como na aba
            elif spec.get("sub_cor"):
                d[spec["cor"]] = s.get(spec["sub_cor"]) or ""
            elif "cor" in s:
                d[spec["cor"]] = s.get("cor") or ""
            linhas.append(d)
        if fd and not subs:
            linhas.append(dict(m))
    return cols, linhas


# célula muito longa (auditoria com dezenas de alertas): cortada no PDF, para a linha caber numa página. O texto completo
# continua no programa e no Excel.
PDF_MAX_LINHAS = 38
PDF_CORTE = " […] (texto cortado no PDF; completo no programa e no Excel)"


def _cortar_celula(v, larg_pt, fonte=7.8):
    """Corta o texto que passaria de PDF_MAX_LINHAS linhas na coluna (quebras de linha viram espaço no PDF)."""
    limite = max(12, int(larg_pt / (fonte * 0.5))) * PDF_MAX_LINHAS
    if len(v) <= limite:
        return v
    return v[:max(0, limite - len(PDF_CORTE))].rstrip() + PDF_CORTE


def exportar_pdf(modelos, saida, nome_base, abas, progresso=None):
    """progresso(texto, fração) é chamado a cada aba e a cada página montada (a aba Auditoria de uma base grande leva
    perto de um minuto)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak

    W, H = landscape(A4)
    ML = 14 * mm
    gerado = datetime.now().strftime("%d/%m/%Y %H:%M")
    C = colors.HexColor

    import rspe_relatorio as _rr
    _f = _rr._fontes()
    # mesmo cabeçalho e rodapé dos relatórios (selo, APTO, filete verde, "página X de Y")
    moldura = _rr._moldura("Execução penal · SEEU", nome_base, pagina=landscape(A4),
                           rodape="Datas conforme o SEEU (RSPE); indulto, comutação e prescrição calculados pelo programa. Falta (12 meses) = indícios "
                                  "no RSPE, conferir o PAD. Indulto: Decretos 11.302/2022, 12.338/2024 e 12.790/2025.")

    ML = 16 * mm
    doc = SimpleDocTemplate(saida, pagesize=landscape(A4), leftMargin=ML, rightMargin=ML,
                            topMargin=21 * mm, bottomMargin=18 * mm, title="APTO - %s" % nome_base, author="APTO")
    st_cel = ParagraphStyle("cel", fontName=_f["n"], fontSize=7.8, leading=9.6, textColor=C("#262B28"))
    st_neg = ParagraphStyle("neg", parent=st_cel, fontName=_f["b"])
    st_mut = ParagraphStyle("mut", parent=st_cel, textColor=C("#7B827E"))
    st_cab = ParagraphStyle("cab", fontName=_f["sb"], fontSize=7.2, leading=8.8, textColor=C(TX2))
    st_tit = ParagraphStyle("tit", fontName=_f["serifb"], fontSize=18, leading=22, textColor=C(NAVY))
    st_sub = ParagraphStyle("sub", fontName=_f["n"], fontSize=8.6, leading=11, textColor=C(TX2))
    largura = W - 2 * ML
    el = []
    primeiro = True
    abas_ok = [sp for a in abas for sp in specs_export(a)]
    for n_aba, spec in enumerate(abas_ok):
        aid = spec["id"]
        if progresso:
            progresso("Exportando PDF: preparando %s (%d de %d)…" % (spec["titulo"], n_aba + 1, len(abas_ok)), 0.3 * n_aba / max(1, len(abas_ok)))
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
            cont = contagem_cartoes(spec, modelos)
            itens = list(rot.items()) + ([("__ped", "Pedido feito")] if cont.get("__ped") else [])
            cel, larg, est = [], [], [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 6),
                                     ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 8)]
            itens = [x for x in itens if not (aid in ("ind",) and x[0] == "")]
            for i, (c, nome) in enumerate(itens):
                texto = '<font color="%s">●</font>  <b>%d</b>  <font color="%s">%s</font>' % (DOT.get(c, "#4A6A8A" if c == "__ped" else "#C8CEC8"), cont.get(c, 0), TX2, nome)
                cel.append(Paragraph(texto, ParagraphStyle("st", parent=st_cel, fontSize=9, leading=11)))
                larg.append(largura / max(4, len(itens)) - 2 * mm)
                est += [("BOX", (i, 0), (i, 0), 0.5, C(LINE)), ("BACKGROUND", (i, 0), (i, 0), colors.white)]
            t = Table([cel], colWidths=larg, hAlign="LEFT", spaceAfter=8)
            t.setStyle(TableStyle(est))
            el.append(t)

        # tabela
        pesos = [c[2] + (6 if c[0] == "proc" else 3 if c[0] == "regime" else 0) for c in cols]
        larguras = [largura * p / sum(pesos) for p in pesos]
        dados = [[Paragraph(c[1], st_cab) for c in cols]]
        estilo = [
            ("LINEBELOW", (0, 0), (-1, 0), 1.1, C(PRI)),
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
                v = _cortar_celula(str(m.get(k + "_full", m.get(k, "")) or ""), larguras[j] - 10)
                v = v.replace("&", "&amp;").replace("<", "&lt;")
                pk = pil.get(k)
                if pk and v:
                    pc = ("vermelho" if v.startswith("Sim") else "verde") if k == "imp" else m.get(pk, "")
                    v = '<font color="%s">●</font> <b><font color="%s">%s</font></b>' % (DOT.get(pc, "#C8CEC8"), rv.CORES[pc][1], v)
                elif k == "falta" and m.get("falta_sim"):
                    v = '<b><font color="%s">%s</font></b>' % (rv.CORES["vermelho"][1], v)
                elif k == "falta" and m.get("falta_apurar"):
                    v = '<b><font color="%s">%s</font></b>' % (rv.CORES["amarelo"][1], v)
                elif not v:
                    v = '<font color="#AEB5B0">—</font>'
                linha.append(Paragraph(v, st_neg if j == 0 else st_cel))
            dados.append(linha)
            if cor:
                estilo.append(("BACKGROUND", (0, i), (-1, i), C(rv.CORES[cor][0])))
                estilo.append(("LINEBEFORE", (0, i), (0, i), 2.2, C(DOT[cor])))
            elif i % 2 == 0:
                estilo.append(("BACKGROUND", (0, i), (-1, i), C(ZEBRA)))
        try:
            # splitInRow: uma linha mais alta que a página é dividida entre páginas, em vez de derrubar a exportação
            t = Table(dados, colWidths=larguras, repeatRows=1, splitInRow=1)
        except TypeError:  # reportlab antigo, sem splitInRow: o corte das células já faz a linha caber
            t = Table(dados, colWidths=larguras, repeatRows=1)
        t.setStyle(TableStyle(estilo))
        el.append(t)

        # legenda
        el.append(Spacer(1, 8))
        leg = "     ".join('<font color="%s">●</font> <font color="%s">%s</font>' % (DOT[c], TX2, n) for c, n in rot.items() if c)
        el.append(Paragraph(leg, ParagraphStyle("leg", parent=st_cel, fontSize=8)))
    if progresso:
        def _cb(tipo, valor):
            if tipo == "PAGE":
                progresso("Exportando PDF: página %s…" % valor, min(0.97, 0.3 + 0.67 * valor / (valor + 80.0)))
        doc.setProgressCallBack(_cb)
        progresso("Exportando PDF: montando as páginas…", 0.3)
    doc.build(el, onFirstPage=moldura, onLaterPages=moldura, canvasmaker=_rr._canvas_numerado())


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
        _sem_formula(ws)
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
        _sem_formula(rs_)
    q = [sum(1 for L in linhas if L.get("tipo") == t) for t in tipos]
    rs_.append(["Total"] + q + [sum(q)])
    for cell in rs_[rs_.max_row]:
        cell.font = Font(bold=True)
    for col, w in zip("ABCDE", (28, 18, 26, 18, 10)):
        rs_.column_dimensions[col].width = w
    wb.save(saida)

