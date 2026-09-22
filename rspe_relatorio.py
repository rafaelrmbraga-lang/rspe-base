# -*- coding: utf-8 -*-
"""
Módulo de relatórios em PDF (ReportLab):
- relatório individual: um PDF por assistido, com a situação executória lida do RSPE, os cálculos do
  programa (indulto, comutação, prescrição, remição a requerer) e os pontos da Auditoria;
- relatório geral: um PDF da base, com os números do lote e a fila de prioridade.

Nada é inventado: datas de progressão, livramento e término são as do SEEU (RSPE); o que o programa
calcula sai identificado como cálculo do programa, sujeito a conferência com o Atestado de Pena.
"""
import os
import re
from collections import Counter
from datetime import datetime, date

import rspe_scraper as rs
import rspe_view as rv

NAVY = "#1F2937"
PRI = "#4F46E5"
TX = "#101828"
TX2 = "#475467"
TX3 = "#98A2B3"
LINE = "#E6E9EF"
ZEBRA = "#F9FAFB"
COR = {"vermelho": ("#FDE8E8", "#B42318"), "laranja": ("#FFEAD5", "#C4320A"), "amarelo": ("#FEF4D6", "#B54708"),
       "vencido": ("#FEF4D6", "#B54708"), "verde": ("#DDF5E7", "#067647"), "cinza": ("#EEF0F3", "#5B6470"),
       "azul": ("#DBEAFE", "#1D4ED8"), "": ("#FFFFFF", TX)}
AVISO = ("Triagem automatizada a partir do RSPE (SEEU) e da ficha disciplinar (SIAPEN). Não substitui o Atestado de Pena. "
         "Progressão, livramento e término são as datas do SEEU; indulto, comutação, prescrição e remição a requerer são "
         "cálculos do programa e devem ser conferidos.")

# ---------------------------------------------------------------- fontes (acentos e símbolos)
_FONTE = {"n": "Helvetica", "b": "Helvetica-Bold", "unicode": False}


def _fontes():
    if _FONTE.get("ok"):
        return _FONTE
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    pares = [(r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
             ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
             ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf")]
    for n, b in pares:
        if os.path.exists(n) and os.path.exists(b):
            try:
                pdfmetrics.registerFont(TTFont("RelN", n))
                pdfmetrics.registerFont(TTFont("RelB", b))
                _FONTE.update(n="RelN", b="RelB", unicode=True)
                break
            except Exception:
                pass
    _FONTE["ok"] = True
    return _FONTE


def _t(txt):
    """Texto seguro para a fonte e para o mini-HTML do Paragraph."""
    s = str(txt if txt is not None else "")
    s = rv.re.sub(r"(-?)\b(\d+)a(\d+)m(\d+)d\b", lambda m: rs.pena_extenso("%sa%sm%sd" % (m.group(2), m.group(3), m.group(4))), s)
    if not _FONTE.get("unicode"):
        for a, b in (("≈", "~"), ("≥", ">="), ("≤", "<="), ("✓", "ok"), ("✔", "ok"), ("✘", "x"), ("✗", "x"), ("⚠", "!"), ("→", "->"), ("…", "...")):
            s = s.replace(a, b)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _pena(txt):
    return rs.pena_extenso(txt) if txt else "—"


# ---------------------------------------------------------------- estilos
def _estilos():
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    f = _fontes()
    C = colors.HexColor
    base = ParagraphStyle("base", fontName=f["n"], fontSize=8.6, leading=12, textColor=C(TX))
    return {
        "C": C,
        "tit": ParagraphStyle("tit", parent=base, fontName=f["b"], fontSize=17, leading=21, textColor=C(NAVY)),
        "sub": ParagraphStyle("sub", parent=base, fontSize=9, leading=12.5, textColor=C(TX2)),
        "h2": ParagraphStyle("h2", parent=base, fontName=f["b"], fontSize=10.5, leading=14, textColor=C(NAVY), spaceBefore=14, spaceAfter=6),
        "cel": ParagraphStyle("cel", parent=base, fontSize=8.2, leading=11),
        "neg": ParagraphStyle("neg", parent=base, fontName=f["b"], fontSize=8.2, leading=11),
        "cab": ParagraphStyle("cab", parent=base, fontName=f["b"], fontSize=7.2, leading=9, textColor=C(TX2)),
        "mut": ParagraphStyle("mut", parent=base, fontSize=7.8, leading=10.5, textColor=C(TX3)),
        "rot": ParagraphStyle("rot", parent=base, fontSize=7.2, leading=9, textColor=C(TX3)),
        "val": ParagraphStyle("val", parent=base, fontName=f["b"], fontSize=10, leading=13),
        "num": ParagraphStyle("num", parent=base, fontName=f["b"], fontSize=20, leading=23, textColor=C(NAVY)),
        "p": base,
    }


def _moldura(titulo, nome_base, rodape=AVISO):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    W, H = A4
    ML = 16 * mm
    gerado = datetime.now().strftime("%d/%m/%Y %H:%M")
    C = colors.HexColor
    f = _fontes()

    def desenhar(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(C(PRI))
        canvas.roundRect(ML, H - 13 * mm, 7 * mm, 7 * mm, 1.8 * mm, stroke=0, fill=1)
        canvas.setStrokeColor(colors.white)
        canvas.setLineWidth(1.1)
        for i, w in enumerate((3.6, 3.6, 2.4)):
            y = H - 8.2 * mm - i * 1.6 * mm
            canvas.line(ML + 1.7 * mm, y, ML + 1.7 * mm + w * mm, y)
        canvas.setFillColor(C(NAVY))
        canvas.setFont(f["b"], 10.5)
        canvas.drawString(ML + 9.5 * mm, H - 11 * mm, "RSPE Base")
        canvas.setFont(f["n"], 8.2)
        canvas.setFillColor(C(TX2))
        canvas.drawString(ML + 9.5 * mm + canvas.stringWidth("RSPE Base", f["b"], 10.5) + 3 * mm, H - 11 * mm, "· " + titulo)
        canvas.drawRightString(W - ML, H - 11 * mm, "%s · emitido em %s" % (nome_base, gerado))
        canvas.setStrokeColor(C(LINE))
        canvas.setLineWidth(0.6)
        canvas.line(ML, H - 15.5 * mm, W - ML, H - 15.5 * mm)
        canvas.setFillColor(C(TX3))
        canvas.setFont(f["n"], 6.6)
        # rodapé em até 2 linhas
        palavras, linhas, atual = rodape.split(), [], ""
        for p in palavras:
            if canvas.stringWidth(atual + " " + p, f["n"], 6.6) > (W - 2 * ML - 22 * mm):
                linhas.append(atual)
                atual = p
            else:
                atual = (atual + " " + p).strip()
        linhas.append(atual)
        for i, l in enumerate(linhas[:3]):
            canvas.drawString(ML, 10.5 * mm - i * 3 * mm, l if f["unicode"] else l.replace("≈", "~"))
        canvas.drawRightString(W - ML, 10.5 * mm, "página %d" % doc.page)
        canvas.restoreState()
    return desenhar


def _tabela(dados, larguras, st, cab=True, cores_linha=None, zebra=True):
    """dados: lista de linhas (strings ou Paragraph). cores_linha: {indice: cor} para faixa lateral."""
    from reportlab.platypus import Table, TableStyle, Paragraph
    C = st["C"]
    linhas = []
    for i, l in enumerate(dados):
        linhas.append([x if not isinstance(x, str) else Paragraph(_t(x), st["cab"] if (cab and i == 0) else st["cel"]) for x in l])
    t = Table(linhas, colWidths=larguras, repeatRows=1 if cab else 0)
    est = [("VALIGN", (0, 0), (-1, -1), "TOP"),
           ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
           ("LINEBELOW", (0, 0), (-1, -1), 0.4, C(LINE))]
    if cab:
        est += [("BACKGROUND", (0, 0), (-1, 0), C("#F2F4F7")), ("LINEBELOW", (0, 0), (-1, 0), 0.6, C("#D0D5DD"))]
    if zebra:
        for i in range(1 if cab else 0, len(linhas)):
            if (i % 2 == 0) == cab:
                est.append(("BACKGROUND", (0, i), (-1, i), C(ZEBRA)))
    for i, cor in (cores_linha or {}).items():
        if cor and cor in COR:
            est.append(("LINEBEFORE", (0, i), (0, i), 2.4, C(COR[cor][1])))
    t.setStyle(TableStyle(est))
    return t


def _pilula(txt, cor, st):
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle
    if not txt:
        return Paragraph("—", st["mut"])
    fundo, frente = COR.get(cor or "", COR[""])
    return Paragraph('<font color="%s"><b>%s</b></font>' % (frente, _t(txt)), ParagraphStyle("pl", parent=st["cel"], fontName=_FONTE["b"]))


# ---------------------------------------------------------------- relatório individual
def _atencao(m, chaves):
    itens = [i for i in m.get("aud_itens", []) if not i.get("baixado") and i["nivel"] in ("alerta", "verificar")
             and any(k.lower() in i["titulo"].lower() for k in chaves)]
    return "; ".join(i["titulo"] for i in itens)


def _linha_tempo(r):
    out = []
    for e in r.get("_eventos", []):
        d = rs.to_date(e.get("data") or "")
        if d:
            out.append((d, (e.get("tipo") or "").title().replace("/", " / "), " · ".join(x for x in (e.get("motivo"), e.get("processos")) if x)))
    for i in r.get("_incidentes", []):
        t = (i.get("tipo") or "").upper()
        if not re.search(r"REGIME|PROGRESS|REGRESS|LIVRAMENTO|FALTA GRAVE|INDULTO|COMUTA|EXTIN|REVOGA|SUSPENS", t):
            continue
        d = rs.to_date(i.get("data_decisao") or i.get("data_referencia") or "")
        if d:
            out.append((d, (i.get("tipo") or "").capitalize(), " · ".join(x for x in (i.get("complemento"), (i.get("situacao") or "").lower()) if x)))
    out.sort(key=lambda x: x[0])
    return out


def relatorio_individual(m, caminho, nome_base):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether
    st = _estilos()
    r = m.get("_bruto") or {}
    W = A4[0] - 32 * mm
    el = []
    # 1) cabeçalho
    el.append(Paragraph(_t(m.get("nome")), st["tit"]))
    cab = ["Execução nº %s" % m.get("proc"), r.get("vara") or m.get("vara") or "", r.get("comarca") or ""]
    el.append(Paragraph(_t(" · ".join(x for x in cab if x)), st["sub"]))
    el.append(Paragraph(_t("CPF %s · RSPE de %s · relatório emitido em %s" % (r.get("cpf") or "não consta", m.get("geracao") or "?", datetime.now().strftime("%d/%m/%Y"))), st["sub"]))
    el.append(Spacer(1, 10))
    # 2) quadro-resumo
    def caixa(rot, val):
        return [Paragraph(_t(rot), st["rot"]), Paragraph(_t(val or "—"), st["val"])]
    q = [("Regime atual", m.get("regime")), ("Pena total", m.get("pena_total")), ("Cumprida", m.get("pena_cumprida")),
         ("Remanescente", m.get("pena_rem")), ("Dias remidos (saldo do RSPE)", (m.get("remidos") or "").split(" (")[0]),
         ("Data-base", m.get("dbase")), ("Término (SEEU)", m.get("termino")), ("Conduta (ficha disciplinar)", m.get("conduta"))]
    from reportlab.platypus import Table, TableStyle
    C = st["C"]
    grade = []
    for i in range(0, len(q), 4):
        grade.append([caixa(*x) for x in q[i:i + 4]])
    tq = Table(grade, colWidths=[W / 4.0] * 4)
    tq.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.6, C(LINE)),
                            ("INNERGRID", (0, 0), (-1, -1), 0.6, C(LINE)), ("BACKGROUND", (0, 0), (-1, -1), C(ZEBRA)),
                            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                            ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    el.append(tq)
    # 3) benefícios e datas
    el.append(Paragraph("Benefícios e datas", st["h2"]))
    ben = [["Benefício", "Data (SEEU)", "Fração / fundamento", "Situação / resultado", "Ponto de atenção"]]
    cores = {}

    def add(nome, data, fr, sit, cor, aten):
        ben.append([Paragraph(_t(nome), st["neg"]), data if data else Paragraph("—", st["mut"]), fr or "—", _pilula(sit, cor, st), aten or ""])
        cores[len(ben) - 1] = cor

    def fr_lc(x):
        return "1/1 (livramento vedado)" if (x or "").strip() in ("1", "1/1") else x

    add("Progressão", m.get("prog"), m.get("frac_prog"), m.get("prog_sit") or ("Pedidos no RSPE: " + m["ped_prog"] if m.get("ped_prog") else ""), m.get("prog_cor"),
        _atencao(m, ["progressão", "data-base", "falta grave"]))
    add("Livramento condicional", m.get("liv"), fr_lc(m.get("frac_liv")), m.get("liv_sit"), m.get("liv_cor"), _atencao(m, ["livramento"]))
    add("Término da pena", m.get("termino"), "", m.get("ext_sit"), m.get("ext_cor"), m.get("ext_hipoteses") if m.get("ext_cor") in ("vermelho", "amarelo") else "")
    for ano, ki, kc in (("2022", "i22", None), ("2024", "i24", "c24"), ("2025", "i25", "c25")):
        add("Indulto %s" % ano, "", "Decreto %s" % {"2022": "11.302/2022", "2024": "12.338/2024", "2025": "12.790/2025"}[ano],
            m.get(ki + "_full") or m.get(ki), m.get(ki + "_cor"), _atencao(m, ["indulto %s" % ano, "hediondez"]))
        if kc:
            add("Comutação %s" % ano, "", "Decreto %s, art. 13" % {"2024": "12.338/2024", "2025": "12.790/2025"}[ano], m.get(kc + "_full") or m.get(kc), m.get(kc + "_cor"), _atencao(m, ["comutação %s" % ano]))
    if m.get("presc_cor") in ("vermelho", "amarelo"):
        add("Prescrição", "", "CP, arts. 109 a 117", m.get("presc_ppe"), m.get("presc_cor"), "")
    el.append(_tabela(ben, [W * 0.17, W * 0.2, W * 0.2, W * 0.16, W * 0.27], st, cores_linha=cores))
    el.append(Paragraph(_t("Datas de progressão, livramento e término: as do SEEU impressas no RSPE. Indulto, comutação e prescrição: cálculo do programa (estimativa)."), st["mut"]))
    # 4) condenações
    el.append(Paragraph("Condenações", st["h2"]))
    cd = [["Crime", "Pena", "Fato", "Hed.", "VGA / morte", "Reincid.", "Frações (prog. / LC)"]]
    for c in m.get("crimes_det", []):
        ext = str(c.get("extinto") or "").upper().startswith("S")
        reinc = {"S/S": "específico", "S/N": "comum", "N/S": "específico", "N/N": "primário"}.get(c.get("reinc") or "", c.get("reinc") or "")
        cd.append([Paragraph("<b>%s</b> <font color='%s'>(%s)</font>%s" % (_t(c.get("nome_crime")), TX2, _t(c.get("dispositivo")), " <font color='%s'>· extinto</font>" % TX3 if ext else ""), st["cel"]),
                   c.get("pena") or "—", c.get("fato") or "—", "sim" if c.get("hediondo") == "S" else "não",
                   "%s / %s" % ("sim" if c.get("vga") == "S" else "não", "sim" if c.get("morte") == "S" else "não"), reinc,
                   "%s / %s" % (c.get("frac_prog") or "—", c.get("frac_liv") or "—")])
    el.append(_tabela(cd, [W * 0.26, W * 0.11, W * 0.1, W * 0.08, W * 0.09, W * 0.1, W * 0.26], st))
    # 5) linha do tempo
    lt = _linha_tempo(r)
    if lt:
        el.append(Paragraph("Linha do tempo da execução", st["h2"]))
        el.append(_tabela([["Data", "Evento", "Detalhe"]] + [[rs.fmt(d), a, b] for d, a, b in lt], [W * 0.12, W * 0.33, W * 0.55], st))
    # 6) remição (ficha disciplinar)
    el.append(Paragraph("Remição (ficha disciplinar)", st["h2"]))
    if m.get("ficha_tem"):
        el.append(Paragraph(_t((m.get("fd_resumo_exec") or "") + ". Situação: " + (m.get("fd_sit") or "")), st["p"]))
        ln = [L for L in m.get("fd_linhas", []) if L.get("cor") in ("vermelho", "amarelo")]
        if ln:
            el.append(Spacer(1, 5))
            el.append(_tabela([["Trabalho / estudo", "Unidade", "Período", "Atestado / horas", "Remição no RSPE", "Providência"]] +
                              [[L["emp"], L.get("un") or "—", L["per"], L["at"], L["rspe"], _pilula(L["sit"], L["cor"], st)] for L in ln],
                              [W * 0.18, W * 0.1, W * 0.18, W * 0.2, W * 0.14, W * 0.2], st, cores_linha={i + 1: L["cor"] for i, L in enumerate(ln)}))
        else:
            el.append(Paragraph("Nada pendente de remição na ficha.", st["mut"]))
    else:
        el.append(Paragraph("Ficha disciplinar não importada: sem conferência de remição e conduta.", st["mut"]))
    # 7) alertas
    al = [i for i in m.get("aud_itens", []) if not i.get("baixado") and i["nivel"] in ("alerta", "verificar")]
    el.append(Paragraph("Alertas e pontos a verificar", st["h2"]))
    if al:
        el.append(_tabela([["Nível", "Ponto", "O que foi encontrado"]] +
                          [[_pilula("Alerta" if i["nivel"] == "alerta" else "Verificar", "vermelho" if i["nivel"] == "alerta" else "amarelo", st),
                            Paragraph(_t(i["titulo"]), st["neg"]), (i.get("detalhe") or "")[:900]] for i in al],
                          [W * 0.12, W * 0.32, W * 0.56], st, cores_linha={k + 1: ("vermelho" if i["nivel"] == "alerta" else "amarelo") for k, i in enumerate(al)}))
    else:
        el.append(Paragraph("Nenhum alerta pendente.", st["mut"]))
    faltam = rs.campos_faltantes(r) if r else []
    if faltam:
        el.append(Spacer(1, 6))
        el.append(Paragraph(_t("Campos ausentes no RSPE: %s." % ", ".join(faltam)), st["mut"]))
    doc = SimpleDocTemplate(caminho, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=21 * mm, bottomMargin=20 * mm,
                            title="Relatório individual - %s" % m.get("nome"), author="RSPE Base")
    fr = _moldura("Relatório individual", nome_base)
    doc.build(el, onFirstPage=fr, onLaterPages=fr)
    return caminho


def nome_arquivo(m):
    nome = re.sub(r"[^\w\- ]", "", rv.re.sub(r"\s+", " ", (m.get("nome") or "assistido"))).strip()
    return "%s - %s.pdf" % (m.get("proc") or "sem numero", nome[:60])


# ---------------------------------------------------------------- relatório geral: agregação
def _faixa_pena(dias):
    if not dias:
        return "sem pena no RSPE"
    a = dias / float(rs.DIAS_ANO)
    for lim, rot in ((4, "até 4 anos"), (8, "4 a 8 anos"), (12, "8 a 12 anos"), (20, "12 a 20 anos")):
        if a <= lim:
            return rot
    return "mais de 20 anos"


def _prazo(d):
    if d is None:
        return None
    if d <= 0:
        return "vencido"
    for lim in (30, 60, 90, 180):
        if d <= lim:
            return "até %d dias" % lim
    return None


def _categoria_alerta(t):
    t = re.sub(r"\(.*?\)", "", t)
    t = re.sub(r"^[^:]*?art\. [^:]+?: ", "", t)
    t = t.split(":")[0]
    t = re.sub(r"\b\d{2}/\d{2}/\d{4}\b|(?<![/\d])\b\d+(?:[.,]\d+)?\b(?![/\d])", "", t)
    t = re.sub(r"\s{2,}", " ", t).replace(" em sem ", " sem ").strip()
    t = re.sub(r"\s+(em|de|há|acima de)$", "", t)
    return (t[:1].upper() + t[1:])[:70]


def estatisticas(modelos, hoje=None):
    hoje = hoje or date.today()
    n = len(modelos)
    E = {"n": n}
    ger = [rs.to_date(m.get("geracao") or "") for m in modelos]
    ger = [g for g in ger if g]
    E["periodo"] = (min(ger), max(ger)) if ger else (None, None)
    E["incompletos"] = sum(1 for m in modelos if rs.campos_faltantes(m.get("_bruto") or {}))
    E["com_ficha"] = sum(1 for m in modelos if m.get("ficha_tem"))
    E["regime"] = Counter((m.get("regime_rspe") or m.get("regime") or "não consta").split(" -")[0] or "não consta" for m in modelos)
    E["vara"] = Counter(((m.get("_bruto") or {}).get("vara") or m.get("vara") or "não consta")[:60] for m in modelos)
    E["pena"] = Counter(_faixa_pena(rs.pena_para_dias((m.get("_bruto") or {}).get("pena_total"))) for m in modelos)
    arts = Counter()
    hed = reinc = vga = 0
    for m in modelos:
        cs = [c for c in m.get("crimes_det", []) if not str(c.get("extinto") or "").upper().startswith("S")]
        for c in cs:
            dsp = c.get("dispositivo") or ""
            arts[("%s (%s)" % (c["nome_crime"], dsp)) if c.get("nome_crime") else (dsp[:1].upper() + dsp[1:] or "Crime não identificado")] += 1
        hed += any(c.get("hediondo") == "S" for c in cs)
        vga += any(c.get("vga") == "S" for c in cs)
        reinc += any("S" in (c.get("reinc") or "") for c in cs)
    E["artigos"], E["hed"], E["vga"], E["reinc"] = arts, hed, vga, reinc
    E["prog"] = Counter(_prazo(m.get("prog_dias")) for m in modelos if not m.get("estado_exec"))
    E["liv"] = Counter(_prazo(m.get("liv_dias")) for m in modelos if not m.get("estado_exec"))
    E["term"] = Counter(_prazo(m.get("ext_dias")) for m in modelos)
    E["ext_cabivel"] = sum(1 for m in modelos if m.get("ext_cor") == "vermelho")
    E["presc"] = sum(1 for m in modelos if m.get("presc_cor") == "vermelho")
    E["ind_poss"] = {a: sum(1 for m in modelos if (m.get(k + "_cor") == "verde")) for a, k in (("2022", "i22"), ("2024", "i24"), ("2025", "i25"))}
    E["com_poss"] = {a: sum(1 for m in modelos if (m.get(k + "_cor") == "verde")) for a, k in (("2024", "c24"), ("2025", "c25"))}
    rem = [rs.saldo_remidos_num((m.get("_bruto") or {}).get("saldo_remidos"))[0] or 0 for m in modelos]
    E["rem_total"], E["rem_media"], E["rem_zero"] = sum(rem), (sum(rem) / float(n) if n else 0), sum(1 for x in rem if not x)
    # remição a requerer (ficha): dias em jogo
    rp = tr = es = 0
    for m in modelos:
        if not m.get("ficha_tem"):
            continue
        mm = re.search(r"\+([\d.,]+)", m.get("fd_remidos") or "")
        rp += float(mm.group(1).replace(",", ".")) if mm else 0
        mt = re.search(r"≈ (\d+) remidos", m.get("fd_atestar") or "")
        tr += int(mt.group(1)) if mt else 0
        me = re.search(r"≈ (\d+) dias", m.get("fd_estudo") or "")
        es += int(me.group(1)) if me else 0
    E["rem_pend"], E["rem_trab"], E["rem_est"] = rp, tr, es
    # alertas da Auditoria por tipo
    cat = Counter()
    for m in modelos:
        for i in m.get("aud_itens", []):
            if i["nivel"] == "alerta" and not i.get("baixado"):
                cat[_categoria_alerta(i["titulo"])] += 1
    E["alertas"] = cat
    E["com_alerta"] = sum(1 for m in modelos if m.get("aud_alertas"))
    return E


def fila_prioridade(modelos):
    """(prioridade, nome, execução, motivo, data) - ordem de atuação."""
    fila = []
    for m in modelos:
        mot = []
        if m.get("ext_cor") == "vermelho":
            mot.append((1, "Extinção pelo cumprimento cabível", m.get("ext_termino")))
        if m.get("presc_cor") == "vermelho":
            mot.append((1, "Prescrição aparente", m.get("presc_prox")))
        elif m.get("presc_cor") == "amarelo":
            mot.append((1, "Prescrição executória iminente", m.get("presc_prox")))
        if m.get("prog_cor") == "vencido":
            mot.append((2, "Progressão vencida (%s)" % (m.get("prog_sit") or "").split(" ·")[0], m.get("prog")))
        if m.get("liv_cor") == "vencido":
            mot.append((2, "Livramento vencido (%s)" % (m.get("liv_sit") or "").split(" ·")[0], m.get("liv")))
        for rot, k in (("Indulto 2024", "i24"), ("Indulto 2025", "i25"), ("Comutação 2024", "c24"), ("Comutação 2025", "c25")):
            if m.get(k + "_cor") == "verde":
                mot.append((3, "%s possível (%s)" % (rot, m.get(k) or ""), ""))
        if m.get("fd_cor") == "vermelho":
            mot.append((3, m.get("fd_sit"), ""))
        elif m.get("ficha_tem") and m.get("fd_cor") == "amarelo":
            mot.append((4, m.get("fd_sit"), ""))
        for campo, rot in (("prog_dias", "Progressão"), ("liv_dias", "Livramento")):
            d = m.get(campo)
            if d is not None and 0 < d <= 30 and not m.get("estado_exec"):
                mot.append((4, "%s em %d dias" % (rot, d), m.get("prog" if campo == "prog_dias" else "liv")))
        if mot:
            p = min(x[0] for x in mot)
            fila.append((p, m.get("nome"), m.get("proc"), "; ".join(x[1] for x in sorted(mot)), next((x[2] for x in sorted(mot) if x[2]), "")))
    fila.sort(key=lambda x: (x[0], x[1] or ""))
    return fila


# ---------------------------------------------------------------- relatório geral: PDF
def _barras(pares, st, largura, cor=PRI, max_itens=10):
    """Gráfico de barras horizontais simples (ReportLab graphics)."""
    from reportlab.graphics.shapes import Drawing, Rect, String
    f = _fontes()
    pares = [p for p in pares if p[1]][:max_itens]
    if not pares:
        return None
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.lib import colors
    rot_w = largura * 0.42
    # rótulo inteiro, quebrado em linhas (sem reticências)
    linhas_rot = []
    for rot, v in pares:
        palavras, ls, atual = rot.split(), [], ""
        for p in palavras:
            if stringWidth((atual + " " + p).strip(), f["n"], 7.4) > rot_w - 8:
                ls.append(atual)
                atual = p
            else:
                atual = (atual + " " + p).strip()
        ls.append(atual)
        linhas_rot.append(ls)
    alturas = [max(15, 9 * len(ls) + 5) for ls in linhas_rot]
    d = Drawing(largura, sum(alturas) + 4)
    mx = max(v for _, v in pares) or 1
    y_topo = d.height
    for (rot, v), ls, h in zip(pares, linhas_rot, alturas):
        y_topo -= h
        yb = y_topo + (h - 9) / 2.0
        for k, l in enumerate(ls):
            d.add(String(0, y_topo + h - 10 - 9 * k, l, fontName=f["n"], fontSize=7.4, fillColor=colors.HexColor(TX2)))
        w = (largura - rot_w - 30) * v / float(mx)
        d.add(Rect(rot_w, yb, max(w, 1.5), 9, fillColor=colors.HexColor(cor), strokeColor=None, rx=2, ry=2))
        d.add(String(rot_w + w + 4, yb + 1.5, str(v), fontName=f["b"], fontSize=7.4, fillColor=colors.HexColor(TX)))
    return d


def relatorio_geral(modelos, caminho, nome_base, nominal=True):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
    st = _estilos()
    C = st["C"]
    W = A4[0] - 32 * mm
    E = estatisticas(modelos)
    el = []
    el.append(Paragraph(_t("Relatório geral · %s" % nome_base), st["tit"]))
    p0, p1 = E["periodo"]
    el.append(Paragraph(_t("%d assistido(s) · RSPEs gerados entre %s e %s · %d com ficha disciplinar · emitido em %s" % (
        E["n"], rs.fmt(p0) or "?", rs.fmt(p1) or "?", E["com_ficha"], datetime.now().strftime("%d/%m/%Y"))), st["sub"]))
    el.append(Spacer(1, 10))

    def cartoes(lista):
        cel = [[Paragraph(_t(str(v)), st["num"]), Paragraph(_t(r), st["rot"])] for r, v in lista]
        t = Table([cel], colWidths=[W / len(lista)] * len(lista))
        t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, C(LINE)), ("INNERGRID", (0, 0), (-1, -1), 0.6, C(LINE)),
                               ("BACKGROUND", (0, 0), (-1, -1), C(ZEBRA)), ("TOPPADDING", (0, 0), (-1, -1), 8),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 9), ("LEFTPADDING", (0, 0), (-1, -1), 9), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t

    pct = lambda x: ("%d%%" % round(100.0 * x / E["n"])) if E["n"] else "0%"
    el.append(cartoes([("assistidos na base", E["n"]), ("com dados incompletos no RSPE", E["incompletos"]),
                       ("com alerta da Auditoria", E["com_alerta"]), ("com ficha disciplinar", E["com_ficha"])]))

    def bloco(titulo, pares, cor=PRI, nota=""):
        g = _barras(pares, st, W, cor)
        partes = [Paragraph(_t(titulo), st["h2"])]
        partes.append(g if g else Paragraph("Sem dados.", st["mut"]))
        if nota:
            partes.append(Paragraph(_t(nota), st["mut"]))
        el.append(KeepTogether(partes))

    # 2) perfil da população
    bloco("Regime atual", E["regime"].most_common())
    ordem = ["até 4 anos", "4 a 8 anos", "8 a 12 anos", "12 a 20 anos", "mais de 20 anos", "sem pena no RSPE"]
    bloco("Pena total", [(k, E["pena"].get(k, 0)) for k in ordem])
    if len(E["vara"]) > 1:
        bloco("Vara", E["vara"].most_common(8))
    # 3) perfil criminal
    el.append(Paragraph("Perfil criminal", st["h2"]))
    el.append(cartoes([("com crime hediondo ou equiparado", pct(E["hed"])), ("com violência ou grave ameaça", pct(E["vga"])),
                       ("reincidentes (segundo o RSPE)", pct(E["reinc"]))]))
    bloco("Crimes mais frequentes (crimes em execução)", E["artigos"].most_common(10), "#7C6CF6")
    # 4) benefícios
    fx = ["vencido", "até 30 dias", "até 60 dias", "até 90 dias", "até 180 dias"]
    tb = [["", "Vencido", "Até 30 dias", "31 a 60", "61 a 90", "91 a 180"]]
    for rot, cnt in (("Progressão", E["prog"]), ("Livramento condicional", E["liv"]), ("Término da pena", E["term"])):
        tb.append([Paragraph(_t(rot), st["neg"])] + [str(cnt.get(k, 0)) for k in fx])
    el.append(KeepTogether([Paragraph("Situação dos benefícios (datas do SEEU)", st["h2"]), _tabela(tb, [W * 0.3] + [W * 0.14] * 5, st)]))
    el.append(Spacer(1, 6))
    el.append(_tabela([["Cálculos do programa", "Assistidos"],
                       ["Extinção pelo cumprimento cabível", str(E["ext_cabivel"])],
                       ["Prescrição aparente", str(E["presc"])],
                       ["Indulto possível (2022 / 2024 / 2025)", "%d / %d / %d" % (E["ind_poss"]["2022"], E["ind_poss"]["2024"], E["ind_poss"]["2025"])],
                       ["Comutação possível (2024 / 2025)", "%d / %d" % (E["com_poss"]["2024"], E["com_poss"]["2025"])]],
                      [W * 0.7, W * 0.3], st))
    # 5) remição
    el.append(Paragraph("Remição", st["h2"]))
    el.append(cartoes([("dias remidos na base (saldo)", "%d" % E["rem_total"]), ("média por assistido", "%.1f" % E["rem_media"]),
                       ("sem remição no RSPE", E["rem_zero"])]))
    if E["com_ficha"]:
        el.append(Spacer(1, 6))
        el.append(cartoes([("dias atestados sem homologação", "%d" % E["rem_pend"]), ("remidos estimados de trabalho sem atestado", "≈ %d" % E["rem_trab"]),
                           ("remidos estimados de estudo a requerer", "≈ %d" % E["rem_est"])]))
        tot = E["rem_pend"] + E["rem_trab"] + E["rem_est"]
        el.append(Paragraph(_t("Dias de pena potencialmente em jogo pela remição (só assistidos com ficha): ≈ %d." % tot), st["p"]))
    # 6) Auditoria
    bloco("Alertas da Auditoria (divergências que prejudicam o assistido)", E["alertas"].most_common(10), "#E5484D",
          "A Auditoria só aponta divergência do RSPE que prejudica o assistido; o programa não recalcula progressão, livramento ou término.")
    # 7) fila de prioridade
    fila = fila_prioridade(modelos)
    el.append(Paragraph("Fila de prioridade", st["h2"]))
    if not fila:
        el.append(Paragraph("Nenhum caso com providência imediata.", st["mut"]))
    elif nominal:
        el.append(_tabela([["#", "Assistido", "Execução", "Motivo", "Data"]] +
                          [[str(k + 1), Paragraph(_t(f[1]), st["neg"]), f[2], f[3], f[4] or ""] for k, f in enumerate(fila)],
                          [W * 0.05, W * 0.23, W * 0.2, W * 0.39, W * 0.13], st,
                          cores_linha={k + 1: {1: "vermelho", 2: "vencido", 3: "vermelho", 4: "amarelo"}[f[0]] for k, f in enumerate(fila)}))
    else:
        cnt = Counter(f[0] for f in fila)
        el.append(Paragraph(_t("Prioridade 1 (extinção/prescrição): %d · 2 (benefício vencido): %d · 3 (remição ou benefício sem pedido): %d · 4 (a vencer / a requerer): %d" % (
            cnt.get(1, 0), cnt.get(2, 0), cnt.get(3, 0), cnt.get(4, 0))), st["p"]))
    doc = SimpleDocTemplate(caminho, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=21 * mm, bottomMargin=20 * mm,
                            title="Relatório geral - %s" % nome_base, author="RSPE Base")
    fr = _moldura("Relatório geral", nome_base)
    doc.build(el, onFirstPage=fr, onLaterPages=fr)
    return caminho


def gerar(modelos, pasta, nome_base, individual=True, geral=True, nominal=True, individuais=None):
    """Cria <pasta>/Relatorios <data hora>/ com o geral e a subpasta Individuais. O geral e a estatística usam
    'modelos'; os PDFs individuais, 'individuais' (quando informado, os assistidos escolhidos).
    Devolve (pasta, n_individuais, erros)."""
    destino = os.path.join(pasta, "Relatorios %s" % datetime.now().strftime("%Y-%m-%d %Hh%M"))
    os.makedirs(destino, exist_ok=True)
    erros, n = [], 0
    if geral:
        try:
            relatorio_geral(modelos, os.path.join(destino, "Relatorio geral - %s.pdf" % re.sub(r"[^\w\- ]", "", nome_base)), nome_base, nominal)
        except Exception as e:
            erros.append("relatório geral: %s" % e)
    if individual:
        sub = os.path.join(destino, "Individuais")
        os.makedirs(sub, exist_ok=True)
        for m in (modelos if individuais is None else individuais):
            try:
                relatorio_individual(m, os.path.join(sub, nome_arquivo(m)), nome_base)
                n += 1
            except Exception as e:
                erros.append("%s: %s" % (m.get("nome"), e))
    return destino, n, erros
