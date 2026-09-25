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
import rspe_prescricao as rp

NAVY = "#1F2937"
PRI = "#4F46E5"
TX = "#101828"
TX2 = "#475467"
TX3 = "#98A2B3"
LINE = "#E6E9EF"
ZEBRA = "#F9FAFB"
COR = {"vermelho": ("#FDE8E8", "#B42318"), "laranja": ("#FFEAD5", "#C4320A"), "amarelo": ("#FEF4D6", "#B54708"),
       "vencido": ("#FDE8E8", "#B42318"), "verde": ("#DDF5E7", "#067647"), "cinza": ("#EEF0F3", "#5B6470"),
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


def _num(x):
    """60 -> "60"; 60.5 -> "60,5" (dias remidos fracionados: 1 dia a cada 3 trabalhados ou 12 horas)."""
    x = round(float(x or 0), 2)
    return ("%d" % x) if x == int(x) else ("%.2f" % x).rstrip("0").replace(".", ",")


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


def _penas_no_texto(txt):
    """Troca cada '2a0m0d' do texto pelo extenso ('2 anos'), mantendo o resto."""
    return re.sub(r"(-?)\b(\d+)a(\d+)m(\d+)d\b", lambda m: m.group(1) + rs.pena_extenso(m.group(0).lstrip("-")), txt or "")


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
# ---------------------------------------------------------------- etiquetas
def _etiqueta_prazo(sit, cor, dias, ped=""):
    """Progressão/livramento/término -> (rótulo curto, cor, observação curta)."""
    s = (sit or "").strip()
    sl = s.lower()
    if not s or s in ("—",):
        return ("Não consta no RSPE", "cinza", "")
    if sl.startswith("vencid") or sl.startswith("lapso") or sl.startswith("extinção cabível"):
        return ("Vencido", "vermelho", s if "verificar" in sl else "")
    if sl.startswith("a verificar"):
        return ("A verificar", "amarelo", s)
    if sl.startswith("em cumprimento") or sl.startswith("em ") or sl.startswith("vence") or sl.startswith("término"):
        if dias is not None and 0 <= dias <= 90:
            return ("Vence em %s" % rs.pl(dias, "dia", "dias"), cor if cor in ("laranja", "amarelo", "verde") else "amarelo", "")
        if dias is not None and dias > 90:
            return ("Em cumprimento", "", "faltam %s" % rs.pl(dias, "dia", "dias"))
        return ("Em cumprimento", "", "")
    if sl.startswith("não se aplica") or sl.startswith("não consta") or sl.startswith("pena interrompida") or sl.startswith("não iniciou"):
        return (s.split(" (")[0], "cinza", "")
    if sl.startswith("pena extinta"):
        return ("Extinta", "azul", "")
    return (s, cor or "", "")


def _etiqueta_indulto(celula, cor):
    """Sim/Verificar/Falta/Não atinge... -> (rótulo, cor)."""
    c = (celula or "").strip()
    if not c:
        return ("—", "")
    mapa = {"Sim": ("Cabível", "verde"), "Verificar": ("A verificar", "amarelo"), "Falta": ("Falta grave", "vermelho"),
            "Não atinge": ("Não cabe", "cinza"), "Concedido": ("Concedido", "azul"), "Indeferido": ("Indeferido", "vermelho"),
            "Prejudicada": ("Prejudicada", "cinza"), "Fato posterior": ("Fato posterior", "cinza"), "Não se aplica": ("Não se aplica", "cinza")}
    if c in mapa:
        return mapa[c]
    if c.startswith("Vedado"):
        return (c, "vermelho")
    return (c, cor or "")


def _obs_indulto(full):
    """Observação curta a partir do texto completo: os incisos e a ressalva, sem fundamento."""
    t = (full or "").split(" | ")
    base, aviso = t[0], (t[1] if len(t) > 1 else "")
    m = re.match(r"^(?:Possível|A verificar|Não atinge)(?: \([^)]*\))?\s*·\s*(.*)$", base)
    inc = m.group(1) if m else ""
    inc = re.sub(r"\s*\((?:sem execução na data|fatos posteriores)\)", "", inc)
    inc = inc.replace("art. 9º, ", "").replace(" · tese: hed. superveniente", " · tese: hediondez superveniente")
    partes = [p for p in (inc.strip(" ·"), aviso.strip()) if p]
    return " · ".join(partes)


# ---------------------------------------------------------------- texto dos alertas
def _desaninhar(txt):
    """Parênteses aninhados viram travessões: 'a (b (c) d)' -> 'a (b – c – d)'."""
    out, depth = [], 0
    for ch in txt or "":
        if ch == "(":
            depth += 1
            out.append("(" if depth == 1 else " – ")
        elif ch == ")":
            if depth > 1:
                out.append(" –")
            elif depth == 1:
                out.append(")")
            depth = max(0, depth - 1)
        else:
            out.append(ch)
    s = "".join(out)
    s = re.sub(r"\s*–\s*–\s*", " – ", s)
    s = re.sub(r"\s+–\)", ")", s)
    s = re.sub(r"\(\s*–\s*", "(", s)
    return re.sub(r"\s{2,}", " ", s).strip()


def _titulo_alerta(titulo):
    """Divide o título: prefixo (processo · crime), frase principal sem parênteses, e as linhas de dados."""
    t = titulo or ""
    pref = ""
    m = re.match(r"^((?:Proc\. [^·]+·\s*)?art\. [^:]+?):\s+(.*)$", t)
    if m:
        pref, t = m.group(1).strip(), m.group(2)
    # parênteses de 1º nível viram linhas "rótulo: conteúdo"
    dados, corpo, depth, buf, lab = [], [], 0, "", ""
    for ch in t:
        if ch == "(":
            if depth == 0:
                palavras = "".join(corpo).strip().split()
                lab = palavras[-1] if palavras else ""
                buf = ""
            depth += 1
            if depth > 1:
                buf += ch
            continue
        if ch == ")":
            depth -= 1
            if depth == 0:
                dados.append((lab, _desaninhar(buf)))
            else:
                buf += ch
            continue
        if depth == 0:
            corpo.append(ch)
        else:
            buf += ch
    frase = re.sub(r"\s{2,}", " ", "".join(corpo)).strip(" -–:;,")
    linhas = []
    for lab, val in dados:
        lab = lab.strip(",;:").lower()
        lab = {"seeu": "No RSPE", "legal": "Esperado pela lei", "esperado": "Esperado", "esperada": "Esperado", "rspe": "No RSPE"}.get(lab, "")
        linhas.append(("%s: %s" % (lab, val)) if lab else val)
    return pref, frase[:1].upper() + frase[1:], linhas


def _frases(txt, limite=8):
    """Detalhe em frases curtas, uma por linha, com os parênteses desaninhados."""
    t = _desaninhar((txt or "").replace("\n", " "))
    ABREV = ("art.", "arts.", "p.", "ú.", "inc.", "n.", "nº.", "Min.", "Rel.", "j.", "c/c.", "s.", "v.", "fl.", "fls.", "Dr.", "Dra.", "Sr.", "Sra.", "ex.", "cf.", "obs.")
    cand = re.split(r"(?<=[.;])\s+(?=[A-ZÀ-Ú0-9“\"'(])", t)
    out = []
    for p in cand:
        p = p.strip()
        if not p:
            continue
        if out and (out[-1].endswith(ABREV) or out[-1].count("(") > out[-1].count(")") or re.search(r"\b\d+\.$", out[-1])):
            out[-1] = out[-1] + " " + p
        else:
            out.append(p)
    return out[:limite]


def _leis(fund):
    """'CP, arts. 63 e 83, V; LEP, art. 112, VII; Lei 11.343/06, art. 44, p. ú.; STJ Tema 1084' -> lista."""
    f = (fund or "").strip()
    itens, depth, buf = [], 0, ""
    i = 0
    while i < len(f):
        ch = f[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if depth == 0 and (ch == ";" or (ch == "." and re.match(r"\.\s+(STF|STJ|TJ[A-Z]{2}|CP|LEP|Lei|Decreto|Súmula|CF)\b", f[i:]))):
            itens.append(buf.strip(" .;"))
            buf = ""
        else:
            buf += ch
        i += 1
    itens.append(buf.strip(" .;"))
    return [_desaninhar(x) for x in itens if x]


# ---------------------------------------------------------------- linha do tempo separada
def _eventos(r):
    out = []
    for e in r.get("_eventos", []):
        d = rs.to_date(e.get("data") or "")
        if not d:
            continue
        tipo = (e.get("tipo") or "").upper()
        cor = "vermelho" if "INTERRUP" in tipo else "verde"
        rot = "Interrupção" if "INTERRUP" in tipo else "Prisão / início"
        out.append((d, rot, (e.get("motivo") or "").capitalize(), e.get("processos") or "", cor))
    return sorted(out, key=lambda x: x[0])


def _incidentes(r):
    out = []
    for i in r.get("_incidentes", []):
        t = (i.get("tipo") or "").upper()
        if not re.search(r"REGIME|PROGRESS|REGRESS|LIVRAMENTO|FALTA GRAVE|INDULTO|COMUTA|EXTIN|REVOGA|SUSPENS|REMI|DATA-BASE", t):
            continue
        d = rs.to_date(i.get("data_decisao") or i.get("data_referencia") or "")
        if not d:
            continue
        sit = (i.get("situacao") or "").lower()
        cor = {"concedido": "verde", "não concedido": "vermelho", "pendente": "amarelo"}.get(sit, "")
        out.append((d, (i.get("tipo") or "").capitalize(), (i.get("complemento") or "").strip(), sit, cor))
    return sorted(out, key=lambda x: x[0])


# ---------------------------------------------------------------- linha do tempo visual da prescrição executória (figura estática)
TL_COR = {"provisoria": ("#98A2B3", "#FFFFFF"), "cumprimento": ("#34A853", "#34A853"), "evasao": ("#F04438", "#FDE8E8"), "interrupcao": ("#F04438", "#FDE8E8"),
          "outro_motivo": ("#B692F6", "#B692F6"), "liberdade": ("#D0D5DD", "#EEF0F3"), "livramento": ("#84CAFF", "#84CAFF"), "duvida": ("#F79009", "#FEF4D6")}
TL_ROT = {"provisoria": "prisão provisória (detração)", "cumprimento": "cumprimento da pena", "evasao": "fuga / evasão", "interrupcao": "interrupção (motivo a conferir)",
          "outro_motivo": "suspensão (preso por outro motivo)", "liberdade": "liberdade sem evasão", "livramento": "livramento", "duvida": "atribuição não comprovada"}


def _tl_tipo(p):
    return "duvida" if (p.get("tipo") == "cumprimento" and p.get("atribuicao") == "nao_comprovada") else p.get("tipo")


def _tl_dias(n):
    n = int(round(n or 0))
    return "{:,}".format(n).replace(",", ".") + (" dia" if n == 1 else " dias")


def _tl_amd(n):
    n = max(0, int(round(n or 0)))
    a, r = divmod(n, 365)
    m = min(r // 30, 11)
    d = r - 30 * m
    p = []
    if a:
        p.append(rs.pl(a, "ano", "anos"))
    if m:
        p.append(rs.pl(m, "mês", "meses"))
    if d or not p:
        p.append(_tl_dias(d))
    return ", ".join(p)


def _hachura(g, x, y, w, h, cor, passo=4.0):
    """Linhas a 45° dentro do retângulo (padrão de fuga / atribuição não comprovada)."""
    from reportlab.graphics.shapes import Line
    from reportlab.lib import colors
    t = -h
    while t < w:
        u0, u1 = max(0.0, -t), min(h, w - t)
        if u1 > u0:
            g.add(Line(x + t + u0, y + u0, x + t + u1, y + u1, strokeColor=colors.HexColor(cor), strokeWidth=0.9))
        t += passo


def figura_prescricao(L, W, hoje=None):
    """Figura da linha do tempo da prescrição executória de um crime (ReportLab Drawing): eixo do fato a hoje, faixas
    classificadas, marcos, linha de contagem e cartão por fuga. Todos os números vêm de ppe_linha_tempo / ppe_saldos."""
    from reportlab.graphics.shapes import Drawing, Line, Rect, Circle, String, Group
    from reportlab.lib import colors
    from datetime import date
    f = _fontes()
    FN, FB = f["n"], f["b"]
    C = colors.HexColor
    hoje = hoje or date.today()
    D = lambda s: rs.to_date(s) if s else None
    lt = L.get("ppe_linha_tempo") or []
    sal = L.get("ppe_saldos") or []
    inicios = [D(p.get("inicio")) for p in lt if D(p.get("inicio"))]
    t0 = min([D(L.get("fato")) or D(L.get("ppe_termo")) or hoje] + inicios)
    t1 = hoje
    span = max(1, (t1 - t0).days)
    PL, PR = 18.0, 18.0
    Wx = W - PL - PR
    x = lambda d: PL + Wx * (min(max(0.0, (d - t0).days / float(span)), 1.0))
    Y0 = 78.0                       # eixo (a partir do topo)
    H = 150 + 118 * len(sal)
    dr = Drawing(W, H)
    g = Group()
    dr.add(g)
    yy = lambda y: H - y            # coordenadas de cima para baixo
    # eixo
    g.add(Line(PL, yy(Y0), PL + Wx, yy(Y0), strokeColor=C("#D0D5DD"), strokeWidth=1.2))
    # faixas
    faixas = []
    for p in lt:
        a, b = D(p.get("inicio")), D(p.get("fim")) or hoje
        if not a:
            continue
        faixas.append((a, b, _tl_tipo(p), p))
    for a, b, tipo, p in faixas:
        cor, fill = TL_COR.get(tipo, TL_COR["liberdade"])
        x1, x2 = x(a), max(x(b), x(a) + 1.5)
        g.add(Rect(x1, yy(Y0 + 7), x2 - x1, 14, fillColor=C(fill), strokeColor=C(cor), strokeWidth=0.6, rx=1.5, ry=1.5))
        if tipo in ("evasao", "interrupcao"):
            _hachura(g, x1, yy(Y0 + 7), x2 - x1, 14, "#F04438")
        elif tipo == "duvida":
            _hachura(g, x1, yy(Y0 + 7), x2 - x1, 14, "#F79009")
            g.add(String((x1 + x2) / 2, yy(Y0 + 2.5), "?", fontName=FB, fontSize=8, fillColor=C("#B54708"), textAnchor="middle"))
        elif tipo == "provisoria":
            t = 0.0
            while t < x2 - x1:
                g.add(Line(x1 + t, yy(Y0 + 7), x1 + t, yy(Y0 - 7), strokeColor=C("#98A2B3"), strokeWidth=1.2))
                t += 3.0
        if x2 - x1 > 34:
            g.add(String((x1 + x2) / 2, yy(Y0 + 20), _tl_dias((b - a).days), fontName=FN, fontSize=5.5, fillColor=C("#475467"), textAnchor="middle"))
    # marcos
    marcos = [(D(L.get("fato")) or D(L.get("ppe_termo")) or hoje, "Fato", "#475467")]
    if D(L.get("sentenca")):
        marcos.append((D(L.get("sentenca")), "Sentença", "#475467"))
    if D(L.get("ppe_termo")):
        marcos.append((D(L.get("ppe_termo")), "Trânsito (termo)", "#4F46E5"))
    for a, b, tipo, p in faixas:
        if tipo in ("evasao", "interrupcao"):
            marcos.append((a, "Fuga" if tipo == "evasao" else "Interrupção", "#B42318"))
            marcos.append((b, "Recaptura" if p.get("fim") else "Hoje", "#067647"))
    marcos.append((hoje, "Situação atual", "#101828"))
    marcos.sort(key=lambda m: m[0])
    tiers = [-999.0, -999.0, -999.0]
    for d, rot, cor in marcos:
        cx = x(d)
        tier = next((i for i, v in enumerate(tiers) if cx - v >= 58), 2)
        tiers[tier] = cx
        ty = Y0 - 16 - tier * 15
        g.add(Line(cx, yy(ty + 6), cx, yy(Y0 - 4), strokeColor=C(cor), strokeWidth=0.5, strokeDashArray=[1, 1]))
        g.add(Circle(cx, yy(Y0), 3, fillColor=colors.white, strokeColor=C(cor), strokeWidth=1.3))
        anchor = "start" if cx < PL + 20 else ("end" if cx > PL + Wx - 20 else "middle")
        g.add(String(cx, yy(ty), rot, fontName=FB, fontSize=5.6, fillColor=C(cor), textAnchor=anchor))
        g.add(String(cx, yy(ty + 6.5), rs.fmt(d), fontName=FN, fontSize=5.4, fillColor=C("#475467"), textAnchor=anchor))
    # linha de contagem e cartão por fuga
    yc = Y0 + 46
    for s in sal:
        a = D(s.get("evasao"))
        b = D(s.get("fim")) if s.get("fim") and s.get("fim") != "hoje" else hoje
        if not a:
            continue
        xa, xb = x(a), x(b)
        lim = D(s.get("limite_max")) if s.get("limite_max") else None
        limn = D(s.get("limite_min")) if s.get("limite_min") else None
        cor = {"prescrita": "#B42318", "a verificar": "#B54708"}.get(s.get("resultado"), "#067647")
        rot = ("revogação do livramento" if s.get("revogacao") else ("interrupção" if s.get("e_evasao") is False else "fuga")) + " de " + s.get("evasao", "")
        g.add(Line(xa, yy(Y0), xa, yy(yc), strokeColor=C("#B42318"), strokeWidth=0.5, strokeDashArray=[1.5, 1.5]))
        g.add(Line(xa, yy(yc), min(xb, x(lim) if lim else xb), yy(yc), strokeColor=C(cor), strokeWidth=2.6, strokeLineCap=1))
        ax = xa > PL + Wx - 190
        g.add(String(PL + Wx if ax else xa, yy(yc - 7), "contagem da prescrição pelo saldo (art. 113) · " + rot, fontName=FB, fontSize=5.4, fillColor=C(cor), textAnchor="end" if ax else "start"))
        rotulos = []
        if limn and x(limn) < xb:
            rotulos.append((x(limn), "#B42318", "venceria %s (saldo mín.)" % s["limite_min"], 1.0, False))
        vistos = {s.get("limite_min"), s.get("limite_max")}
        for fx in s.get("faixas") or []:
            if fx.get("limite") and fx.get("prescrita") and fx["limite"] not in vistos:
                vistos.add(fx["limite"])
                rotulos.append((x(D(fx["limite"])), "#B42318", "venceria %s se o saldo fosse %s" % (fx["limite"], fx.get("rotulo") or ""), 1.0, True))
        if lim:
            rotulos.append((x(lim), "#475467", "venceria %s (saldo máx.)" % s["limite_max"], 1.0, False))
        rotulos.append((xb, "#067647", ("recaptura %s → interrompe (art. 117, V)" % s["fim"]) if (s.get("fim") and s.get("fim") != "hoje") else "hoje", 1.6, False))
        rotulos.sort(key=lambda t: t[0])
        lx, dy = -9999.0, 11.0
        for tx, tcor, txt, tw, dash in rotulos:
            dy = dy + 7 if tx - lx < 130 else 11.0
            lx = tx
            anchor = "end" if tx > PL + Wx - 70 else ("start" if tx < PL + 70 else "middle")
            g.add(Line(tx, yy(yc - 4), tx, yy(yc + 4), strokeColor=C(tcor), strokeWidth=tw, strokeDashArray=[1.5, 1] if dash else None))
            g.add(String(tx, yy(yc + dy), txt, fontName=FN, fontSize=5.2, fillColor=C(tcor), textAnchor=anchor))
        # cartão do saldo
        cw, ch = 192.0, 66.0
        cxx = min(max(xa, PL), PL + Wx - cw)
        cy = yc + 36
        g.add(Rect(cxx, yy(cy + ch), cw, ch, fillColor=colors.white, strokeColor=C(cor), strokeWidth=0.8, rx=3, ry=3))
        g.add(String(cxx + 5, yy(cy + 9), rot.upper(), fontName=FB, fontSize=5.8, fillColor=C(cor)))
        lims = []
        for fx in s.get("faixas") or []:
            if fx.get("limite") and fx["limite"] not in lims:
                lims.append(fx["limite"])
        venc = (lims[0] + " a " + lims[-1]) if len(lims) > 1 else (lims[0] if lims else (s.get("limite_max") or "—"))
        smin, smax = s.get("saldo_min", 0), s.get("saldo_max", 0)
        li = [("Pena aplicada", _tl_amd(smax + s.get("cumprido_min", 0))),
              ("Cumprido (execução)", _tl_dias(s.get("cumprido_desde_termo", 0)) + ((" + %s remidos" % s["remicao"]) if s.get("remicao") else "")),
              ("Imputável ao crime", _tl_amd(s.get("cumprido_max", 0)) if smin == smax else "de %s até %s" % (_tl_amd(s.get("cumprido_min", 0)), _tl_amd(s.get("cumprido_max", 0)))),
              ("Saldo na fuga", _tl_amd(smax) if smin == smax else "%s a %s" % (_tl_amd(smin), _tl_amd(smax))),
              ("Prazo (art. 113)", ("%s a %s" % (s["prazo_min"], s["prazo_max"])) if (s.get("prazo_min") and s.get("prazo_min") != s.get("prazo_max")) else (s.get("prazo_max") or "nada a prescrever")),
              ("Vencimento", venc)]
        for j, (ra, rb) in enumerate(li):
            g.add(String(cxx + 5, yy(cy + 18 + j * 8.6), ra + ":", fontName=FN, fontSize=5.4, fillColor=C("#475467")))
            g.add(String(cxx + cw - 5, yy(cy + 18 + j * 8.6), rb, fontName=FB, fontSize=5.4, fillColor=C("#101828"), textAnchor="end"))
        yc += 118
    return dr


def legenda_prescricao(W, st):
    """Legenda das faixas da figura (tabela de uma linha)."""
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.graphics.shapes import Drawing, Rect
    from reportlab.lib import colors
    C = st["C"]
    itens = [("cumprimento", "cumprimento da pena"), ("evasao", "fuga / evasão"), ("provisoria", "prisão provisória (detração)"), ("outro_motivo", "suspensão (preso por outro motivo)"),
             ("liberdade", "liberdade sem evasão"), ("livramento", "livramento"), ("duvida", "atribuição não comprovada")]
    cels = []
    for tipo, rot in itens:
        cor, fill = TL_COR[tipo]
        d = Drawing(14, 7)
        d.add(Rect(0, 0, 14, 7, fillColor=C(fill), strokeColor=C(cor), strokeWidth=0.5))
        if tipo in ("evasao", "duvida"):
            _hachura(d, 0, 0, 14, 7, cor, 3.0)
        cels += [d, Paragraph(_t(rot), st["mut"])]
    linhas = [cels[:8], cels[8:] + [""] * (8 - len(cels[8:]))]
    t = Table(linhas, colWidths=[16, W / 4.0 - 16] * 4, hAlign="LEFT")
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 1), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                           ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    return t


# ---------------------------------------------------------------- relatório
def relatorio_individual(m, caminho, nome_base):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
    st = _estilos()
    C = st["C"]
    f = _fontes()
    st["h3"] = ParagraphStyle("h3", parent=st["p"], fontName=f["b"], fontSize=9, leading=12, textColor=C(NAVY), spaceBefore=6, spaceAfter=3)
    st["chip"] = ParagraphStyle("chip", parent=st["cel"], fontName=f["b"], fontSize=7.6, leading=10)
    st["lei"] = ParagraphStyle("lei", parent=st["cel"], fontSize=7.8, leading=10.5, textColor=C(TX2))
    r = m.get("_bruto") or {}
    W = A4[0] - 32 * mm
    el = []

    def chip(txt, cor):
        fundo, frente = COR.get(cor or "", COR[""])
        t = Table([[Paragraph('<font color="%s">%s</font>' % (frente, _t(txt)), st["chip"])]])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), C(fundo)), ("LEFTPADDING", (0, 0), (-1, -1), 6),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                               ("ROUNDEDCORNERS", [4, 4, 4, 4])]))
        return t

    # 1) cabeçalho
    el.append(Paragraph(_t(m.get("nome")), st["tit"]))
    cab = ["Execução nº %s" % m.get("proc"), r.get("vara") or m.get("vara") or "", r.get("comarca") or ""]
    el.append(Paragraph(_t(" · ".join(x for x in cab if x)), st["sub"]))
    el.append(Paragraph(_t("CPF %s · RSPE de %s · relatório emitido em %s" % (r.get("cpf") or "não consta", m.get("geracao") or "?", datetime.now().strftime("%d/%m/%Y"))), st["sub"]))
    el.append(Spacer(1, 10))

    # 2) bloco visual da pena
    def caixa(rot, val):
        return [Paragraph(_t(rot), st["rot"]), Paragraph(_t(val or "—"), st["val"])]
    q = [("Regime atual", m.get("regime") + ((" · " + m["motivo_exec"]) if m.get("motivo_exec") else "")), ("Pena total", m.get("pena_total")),
         ("Cumprida", m.get("pena_cumprida")), ("Remanescente", m.get("pena_rem")),
         ("Dias remidos (saldo do RSPE)", (m.get("remidos") or "").split(" (")[0]), ("Data-base", m.get("dbase")),
         ("Término (SEEU)", m.get("termino") if m.get("termino") not in (None, "", "—") else (m.get("termino_motivo") or "—")),
         ("Conduta (ficha disciplinar)", m.get("conduta"))]
    grade = [[caixa(*x) for x in q[i:i + 4]] for i in range(0, len(q), 4)]
    tq = Table(grade, colWidths=[W / 4.0] * 4)
    tq.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.6, C(LINE)),
                            ("INNERGRID", (0, 0), (-1, -1), 0.6, C(LINE)), ("BACKGROUND", (0, 0), (-1, -1), C(ZEBRA)),
                            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    el.append(tq)

    # 3) benefícios: tabela enxuta com etiquetas
    el.append(Paragraph("Benefícios", st["h2"]))
    ben = [["Benefício", "Data (SEEU) / base", "Situação", "Observação"]]
    cores = {}

    def add(nome, data, rot, cor, obs):
        ben.append([Paragraph(_t(nome), st["neg"]), Paragraph(_t(data or "—"), st["cel"] if data else st["mut"]), chip(rot, cor), Paragraph(_t(obs or ""), st["cel"])])
        cores[len(ben) - 1] = cor

    def dm(k):
        v = m.get(k)
        return v if v and v != "—" else ""

    rot, cor, obs = _etiqueta_prazo(m.get("prog_sit"), m.get("prog_cor"), m.get("prog_dias"))
    if not dm("prog") and not obs:
        obs = m.get("prog_motivo") or ""
    if m.get("ped_prog"):
        obs = (obs + " · " if obs else "") + "pedido no RSPE: " + m["ped_prog"]
    add("Progressão", dm("prog") and (dm("prog") + " · " + (m.get("frac_prog") or "")), rot, cor, obs)
    rot, cor, obs = _etiqueta_prazo(m.get("liv_sit"), m.get("liv_cor"), m.get("liv_dias"))
    fl = m.get("frac_liv") or ""
    fl = "livramento vedado (1/1)" if fl.strip() in ("1", "1/1") else fl
    add("Livramento condicional", dm("liv") and (dm("liv") + " · " + fl), rot, cor, obs or (m.get("liv_motivo") or "" if not dm("liv") else ""))
    rot, cor, obs = _etiqueta_prazo(m.get("ext_sit"), m.get("ext_cor"), m.get("ext_dias"))
    add("Término da pena", dm("termino"), rot, cor, (m.get("ext_hipoteses") or "").split(";")[0] if m.get("ext_cor") == "vermelho" else "")
    if m.get("falta") and m.get("falta") not in ("Não consta", "—"):
        fc = "vermelho" if m["falta"].startswith("Sim") else "amarelo"
        add("Falta grave (12 meses)", "", "Sim" if fc == "vermelho" else "A apurar", fc, (m.get("falta_full") or m.get("falta") or "").split(" · ", 1)[-1][:120])
    dec = {"2022": "Decreto 11.302/2022", "2024": "Decreto 12.338/2024", "2025": "Decreto 12.790/2025"}
    for ano, ki, kc in (("2022", "i22", None), ("2024", "i24", "c24"), ("2025", "i25", "c25")):
        rot, cor = _etiqueta_indulto(m.get(ki), m.get(ki + "_cor"))
        add("Indulto %s" % ano, dec[ano], rot, cor, _obs_indulto(m.get(ki + "_full")))
        if kc:
            rot, cor = _etiqueta_indulto(m.get(kc), m.get(kc + "_cor"))
            add("Comutação %s" % ano, dec[ano] + ", art. 13", rot, cor, _obs_indulto(m.get(kc + "_full")))
    pr, pe = m.get("presc_retro"), m.get("presc_ppe")
    if m.get("presc_retro_cor") == "vermelho":
        add("Prescrição punitiva", "", "Aparente", "vermelho", (m.get("presc_retro_full") or "").replace("Aparente: ", ""))
    if m.get("presc_ppe_cor") in ("vermelho", "amarelo"):
        add("Prescrição executória", "", "Aparente" if m["presc_ppe_cor"] == "vermelho" else "Iminente", m["presc_ppe_cor"],
            re.sub(r"^(Aparente|Iminente): ", "", m.get("presc_ppe_full") or ""))
    elif pe and pe not in ("Não prescrita", "Sem dados"):
        add("Prescrição executória", "", pe, m.get("presc_ppe_cor") or "", "")
    el.append(_tabela(ben, [W * 0.22, W * 0.18, W * 0.16, W * 0.44], st, cores_linha=cores))
    el.append(Paragraph(_t("Progressão, livramento e término: datas do SEEU impressas no RSPE. Indulto, comutação, prescrição e falta: cálculo do programa, a conferir. "
                           "Fundamentos e memória de cálculo: no programa, na ficha do assistido."), st["mut"]))

    # 4) condenações
    el.append(Paragraph("Condenações", st["h2"]))
    cd = [["Crime", "Pena", "Fato", "Hediondo", "VGA", "Reincid.", "Progressão", "Livramento"]]
    for c in m.get("crimes_det", []):
        ext = str(c.get("extinto") or "").upper().startswith("S")
        reinc = {"S/S": "específico", "S/N": "comum", "N/S": "específico", "N/N": "primário"}.get(c.get("reinc") or "", c.get("reinc") or "")
        fp = (c.get("frac_prog") or "—").split(" - ")[0]
        fl = (c.get("frac_liv") or "—").split(" - ")[0]
        cd.append([Paragraph("<b>%s</b> <font color='%s'>%s</font>%s" % (_t(c.get("nome_crime")), TX2, _t(c.get("dispositivo")), " <font color='%s'>· extinto</font>" % TX3 if ext else ""), st["cel"]),
                   c.get("pena") or "—", c.get("fato") or "—", "sim" if c.get("hediondo") == "S" else "não",
                   "sim" if c.get("vga") == "S" else "não", reinc, fp, "vedado" if fl.strip() in ("1", "1/1") else fl])
    el.append(_tabela(cd, [W * 0.3, W * 0.12, W * 0.1, W * 0.08, W * 0.06, W * 0.1, W * 0.12, W * 0.12], st))

    # 5) linha do tempo, separada
    ev, inc = _eventos(r), _incidentes(r)
    if ev:
        el.append(Paragraph("Eventos de cumprimento da pena (prisões e interrupções)", st["h2"]))
        linhas = [["Data", "Evento", "Motivo", "Processos"]] + [[rs.fmt(d), Paragraph(_t(a), st["neg"]), b, Paragraph(_t(p), st["mut"])] for d, a, b, p, _ in ev]
        el.append(_tabela(linhas, [W * 0.12, W * 0.16, W * 0.3, W * 0.42], st, cores_linha={i + 1: e[4] for i, e in enumerate(ev)}))
    if inc:
        el.append(Paragraph("Incidentes (regime, livramento, indulto e comutação, faltas, remição)", st["h2"]))
        linhas = [["Data", "Incidente", "Complemento", "Situação"]] + [[rs.fmt(d), a, b, chip(s or "—", cor)] for d, a, b, s, cor in inc]
        el.append(_tabela(linhas, [W * 0.12, W * 0.3, W * 0.4, W * 0.18], st))

    # 6) remição
    el.append(Paragraph("Remição (ficha disciplinar)", st["h2"]))
    if m.get("ficha_tem"):
        el.append(Paragraph(_t((m.get("fd_resumo_exec") or "") + ". Situação: " + (m.get("fd_sit") or "")), st["p"]))
        ln = [L for L in m.get("fd_linhas", []) if L.get("cor") in ("vermelho", "amarelo")]
        if ln:
            el.append(Spacer(1, 5))
            el.append(_tabela([["Trabalho / estudo", "Unidade", "Período", "Atestado / horas", "Providência"]] +
                              [[L["emp"], L.get("un") or "—", L["per"], L["at"], _pilula(L["sit"], L["cor"], st)] for L in ln],
                              [W * 0.2, W * 0.1, W * 0.2, W * 0.24, W * 0.26], st, cores_linha={i + 1: L["cor"] for i, L in enumerate(ln)}))
        else:
            el.append(Paragraph("Nada pendente de remição na ficha.", st["mut"]))
    else:
        el.append(Paragraph("Ficha disciplinar não importada: sem conferência de remição e conduta.", st["mut"]))

    # 7) alertas e pontos a verificar: um bloco por item
    al = [i for i in m.get("aud_itens", []) if not i.get("baixado") and i["nivel"] in ("alerta", "verificar")]
    el.append(Paragraph("Alertas e pontos a verificar", st["h2"]))
    if not al:
        el.append(Paragraph("Nenhum alerta pendente.", st["mut"]))
    for i in al:
        cor = "vermelho" if i["nivel"] == "alerta" else "amarelo"
        pref, frase, dados = _titulo_alerta(i["titulo"])
        corpo = []
        cab_ = Table([[chip("Alerta" if i["nivel"] == "alerta" else "Verificar", cor), Paragraph("<b>%s</b>%s" % (_t(frase), ("<br/><font color='%s'>%s</font>" % (TX2, _t(pref))) if pref else ""), st["cel"])]],
                     colWidths=[W * 0.12, W * 0.86])
        cab_.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        corpo.append(cab_)
        linhas = [Paragraph("• " + _t(d), st["cel"]) for d in dados]
        linhas += [Paragraph("• " + _t(fr), st["cel"]) for fr in _frases(i.get("detalhe"))]
        if i.get("fundamento"):
            leis = _leis(i["fundamento"])
            linhas.append(Paragraph("<b>Fundamento</b>", st["h3"]))
            linhas += [Paragraph("– " + _t(x), st["lei"]) for x in leis]
        t = Table([[x] for x in linhas], colWidths=[W - 10])
        t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
        corpo.append(t)
        bloco = Table([[x] for x in corpo], colWidths=[W])
        bloco.setStyle(TableStyle([("LINEBEFORE", (0, 0), (0, -1), 2.4, C(COR[cor][1])), ("BACKGROUND", (0, 0), (-1, -1), C(ZEBRA)),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        el.append(KeepTogether(bloco))
        el.append(Spacer(1, 6))
    # 8) prescrição executória por crime: figura da linha do tempo (memória de cálculo visual) dos crimes com evasão,
    #    prescrição aparente ou a verificar; todos os números vêm de ppe_linha_tempo / ppe_saldos
    pres = [L for L in m.get("presc_linhas", []) if L.get("ppe_linha_tempo") and L.get("ppe_saldos") and (
        L.get("ppe_cor") in ("vermelho", "amarelo") or any(x.get("tipo") in ("evasao", "interrupcao") for x in L["ppe_linha_tempo"]))]
    if pres:
        cabeca_secao = [Paragraph("Prescrição executória: linha do tempo por crime", st["h2"]),
                        Paragraph(_t("Eixo do fato à situação atual com cada período dos eventos do RSPE classificado em relação ao crime; abaixo, a contagem da "
                                     "prescrição pelo saldo em cada fuga (CP, art. 113) e o cartão com a pena aplicada, o cumprido, o saldo, o prazo e o vencimento. "
                                     "Com mais de uma condenação, o saldo fica entre dois limites, conforme a imputação do tempo cumprido."), st["mut"]),
                        legenda_prescricao(W, st)]
        hoje_rel = rv.HOJE
        for L in pres:
            sal = L.get("ppe_saldos") or []
            ref_s = next((S for S in sal if S.get("resultado") == "a verificar"), None) or next((S for S in sal if S.get("resultado") == "prescrita"), None) or (sal[-1] if sal else {})
            stt = L.get("ppe_status") or ""
            res = ("amarelo", "A VERIFICAR") if stt.startswith("A VERIFICAR") else (("vermelho", "PRESCRITO") if "aparente" in stt.lower() else ("verde", "Não reconhecida"))
            cab_crime = Table([[chip(res[1], res[0]), Paragraph("<b>%s</b> · pena %s · fato %s · trânsito %s" % (_t(L.get("rotulo") or L.get("crime")), _t(_pena(L.get("pena"))),
                                                                                                                  _t(L.get("fato") or "—"), _t(L.get("ppe_termo") or "—")), st["cel"])]],
                              colWidths=[W * 0.14, W * 0.84])
            cab_crime.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
            el.append(KeepTogether(cabeca_secao + [cab_crime, figura_prescricao(L, W, hoje_rel)]))
            cabeca_secao = []
            smin, smax = ref_s.get("saldo_min", 0), ref_s.get("saldo_max", 0)
            saldo_txt = _tl_amd(smax) if smin == smax else "entre %s e %s" % (_tl_amd(smin), _tl_amd(smax))
            prazo_txt = ("%s a %s" % (ref_s["prazo_min"], ref_s["prazo_max"])) if (ref_s.get("prazo_min") and ref_s.get("prazo_min") != ref_s.get("prazo_max")) else (ref_s.get("prazo_max") or "nada a prescrever")
            fl = [[Paragraph("<b>1 · TEMPO DE PRISÃO / DETRAÇÃO</b><br/>Prisão provisória antes do trânsito: <b>%s</b> (CP, art. 42). Não entra no prazo." % _tl_dias(L.get("ppe_detracao_dias") or 0), st["cel"]),
                   Paragraph("→", st["cel"]),
                   Paragraph("<b>2 · SALDO DA PENA NA FUGA</b><br/>Pena de %s menos o cumprimento imputável a esta condenação: %s (na fuga de %s)." % (_t(_pena(L.get("pena"))), _t(saldo_txt), _t(ref_s.get("evasao") or "—")), st["cel"]),
                   Paragraph("→", st["cel"]),
                   Paragraph("<b>3 · PRAZO DE PRESCRIÇÃO</b><br/>Art. 109 sobre o saldo, +1/3 reincidência, ½ art. 115: %s." % _t(prazo_txt), st["cel"])]]
            tf = Table(fl, colWidths=[W * 0.31, W * 0.035, W * 0.31, W * 0.035, W * 0.31])
            tf.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (0, 0), 0.5, C(LINE)), ("BOX", (2, 0), (2, 0), 0.5, C(LINE)), ("BOX", (4, 0), (4, 0), 0.5, C(LINE)),
                                    ("BACKGROUND", (0, 0), (0, 0), C(ZEBRA)), ("BACKGROUND", (2, 0), (2, 0), C(ZEBRA)), ("BACKGROUND", (4, 0), (4, 0), C(ZEBRA)),
                                    ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
            el.append(tf)
            h76, hcr = ref_s.get("art76"), ref_s.get("cronologica")
            if h76 and hcr:
                hp = [[Paragraph("<b>Hipótese 1 · CP, art. 76 (pena mais grave primeiro)</b><br/>Este crime seria o %dº de %d em execução. Saldo na fuga: %s · prazo %s%s → <b>%s</b>" % (
                                     h76["posicao"], h76["de"], _tl_amd(h76["saldo"]), _t(h76.get("prazo") or "—"), (" · venceria em " + h76["limite"]) if h76.get("limite") else "", _t(h76["resultado"])), st["cel"]),
                       Paragraph("<b>Hipótese 2 · ordem cronológica do trânsito</b><br/>Este crime seria o %dº de %d. Saldo na fuga: %s · %s → <b>%s</b>" % (
                                     hcr["posicao"], hcr["de"], _tl_amd(hcr["saldo"]), ("prazo %s · venceria em %s" % (_t(hcr["prazo"]), hcr["limite"])) if hcr.get("prazo") else "nada a prescrever", _t(hcr["resultado"])), st["cel"])]]
                th = Table(hp, colWidths=[W * 0.49, W * 0.49], hAlign="LEFT")
                th.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (0, 0), 0.5, C("#D0D5DD")), ("BOX", (1, 0), (1, 0), 0.5, C("#D0D5DD")),
                                        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
                el.append(Spacer(1, 4))
                el.append(th)
            motivo = ("não foi possível determinar, com os dados do SEEU, o saldo de pena atribuído a esta condenação na data da fuga" if res[1] == "A VERIFICAR"
                      else (_penas_no_texto(stt) if res[1] == "PRESCRITO" else ("a recaptura ocorreu antes do vencimento calculado em todas as hipóteses de saldo"
                                                                                if (ref_s.get("fim") and ref_s.get("fim") != "hoje") else "o prazo ainda não venceu em nenhuma das hipóteses de saldo")))
            corpo_res = [Paragraph("<b>PRESCRIÇÃO: %s</b><br/>Motivo: %s." % (res[1], _t(motivo)), st["cel"])]
            if L.get("ppe_faltam"):
                corpo_res.append(Paragraph("<b>Falta para concluir:</b> %s." % _t("; ".join(L["ppe_faltam"])), st["cel"]))
            tr_ = Table([[x_] for x_ in corpo_res], colWidths=[W])
            tr_.setStyle(TableStyle([("LINEBEFORE", (0, 0), (0, -1), 2.4, C(COR[res[0]][1])), ("BACKGROUND", (0, 0), (-1, -1), C(COR[res[0]][0])),
                                     ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
            el.append(Spacer(1, 4))
            el.append(tr_)
            el.append(Spacer(1, 10))
    faltam = rs.campos_faltantes(r) if r else []
    if faltam:
        el.append(Paragraph(_t("Campos ausentes no RSPE: %s." % ", ".join(faltam)), st["mut"]))
    doc = SimpleDocTemplate(caminho, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=21 * mm, bottomMargin=20 * mm,
                            title="Relatório individual - %s" % m.get("nome"), author="RSPE Base")
    fr_ = _moldura("Relatório individual", nome_base)
    doc.build(el, onFirstPage=fr_, onLaterPages=fr_)
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
            return "até %s" % rs.pl(lim, "dia", "dias")
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
        # fd_remidos = "remidos pela ficha / homologados no RSPE": a diferença positiva está pendente de homologação
        mm = re.match(r"\s*([\d,]+)\s*/\s*([\d,]+)", m.get("fd_remidos") or "")
        rp += max(0.0, float(mm.group(1).replace(",", ".")) - float(mm.group(2).replace(",", "."))) if mm else 0
        tr += int(m.get("fd_sem_n") or 0)
        me = re.search(r"≈ (\d+) dias?\b", m.get("fd_estudo") or "")  # "≈ 1 dia" e "≈ 3 dias"
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
        # cada pretensão com a sua cor; a data (presc_prox) é só da executória
        if m.get("presc_retro_cor") == "vermelho":
            mot.append((1, "Prescrição da pretensão punitiva aparente", ""))
        if m.get("presc_ppe_cor") == "vermelho":
            mot.append((1, "Prescrição executória aparente", m.get("presc_prox")))
        elif m.get("presc_ppe_cor") == "amarelo":
            mot.append((1, "Prescrição executória iminente", m.get("presc_prox")))
        if m.get("prog_cor") == "vencido":
            mot.append((2, "Progressão vencida (%s)" % (m.get("prog_sit") or "").split(" ·")[0], m.get("prog")))
        if m.get("liv_cor") == "vencido":
            mot.append((2, "Livramento vencido (%s)" % (m.get("liv_sit") or "").split(" ·")[0], m.get("liv")))
        for rot, k in (("Indulto 2024", "i24"), ("Indulto 2025", "i25"), ("Comutação 2024", "c24"), ("Comutação 2025", "c25")):
            if m.get(k + "_cor") == "verde":
                mot.append((3, "%s possível (%s)" % (rot, m.get(k + "_txt") or m.get(k) or ""), ""))
        if m.get("fd_cor") == "vermelho":
            mot.append((3, m.get("fd_sit"), ""))
        elif m.get("ficha_tem") and m.get("fd_cor") == "amarelo":
            mot.append((4, m.get("fd_sit"), ""))
        for campo, rot in (("prog_dias", "Progressão"), ("liv_dias", "Livramento")):
            d = m.get(campo)
            if d is not None and 0 < d <= 30 and not m.get("estado_exec"):
                mot.append((4, "%s em %s" % (rot, rs.pl(d, "dia", "dias")), m.get("prog" if campo == "prog_dias" else "liv")))
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
    el.append(Paragraph(_t("%s · RSPEs gerados entre %s e %s · %d com ficha disciplinar · emitido em %s" % (
        rs.pl(E["n"], "assistido", "assistidos"), rs.fmt(p0) or "?", rs.fmt(p1) or "?", E["com_ficha"], datetime.now().strftime("%d/%m/%Y"))), st["sub"]))
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
        el.append(cartoes([("dias atestados sem homologação", _num(E["rem_pend"])), ("períodos de trabalho sem atestado", "%d" % E["rem_trab"]),
                           ("remidos estimados de estudo a requerer", "≈ %d" % E["rem_est"])]))
        tot = E["rem_pend"] + E["rem_est"]
        el.append(Paragraph(_t("Dias de pena em jogo pela remição (atestados sem homologação e estudo; só assistidos com ficha): ≈ %s. Os períodos sem atestado dependem do atestado para serem contados." % _num(tot)), st["p"]))
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
