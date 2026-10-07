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
from datetime import datetime, date, timedelta

import rspe_scraper as rs
import rspe_view as rv
import rspe_prescricao as rp

NAVY = "#1F2937"
PRI = "#00602C"
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
    i = "{:,}".format(int(x)).replace(",", ".")  # milhar com ponto: 50331 -> "50.331"
    return i if x == int(x) else i + ("%.2f" % (abs(x) % 1))[1:].rstrip("0").replace(".", ",")


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


def _moldura(titulo, nome_base, rodape=AVISO, pagina=None):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    W, H = pagina or A4
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


def _tabela(dados, larguras, st, cab=True, cores_linha=None, zebra=True, pad=6):
    """dados: lista de linhas (strings ou Paragraph). cores_linha: {indice: cor} para faixa lateral."""
    from reportlab.platypus import Table, TableStyle, Paragraph
    C = st["C"]
    linhas = []
    for i, l in enumerate(dados):
        linhas.append([x if not isinstance(x, str) else Paragraph(_t(x), st["cab"] if (cab and i == 0) else st["cel"]) for x in l])
    t = Table(linhas, colWidths=larguras, repeatRows=1 if cab else 0)
    est = [("VALIGN", (0, 0), (-1, -1), "TOP"),
           ("LEFTPADDING", (0, 0), (-1, -1), pad), ("RIGHTPADDING", (0, 0), (-1, -1), pad),
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
            "Não atinge": ("Não cabe", "cinza"), "Não alcançado": ("Não alcançado", "cinza"), "Concedido": ("Concedido", "azul"), "Indeferido": ("Indeferido", "vermelho"),
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
    inc = re.sub(r"\s*\((?:sem execução na data|fatos posteriores|sem condenação até [\d/]+|sem pena em cumprimento em [\d/]+|não iniciou o cumprimento em [\d/]+|cumprimento interrompido em [\d/]+)\)", "", inc)
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
          "outro_motivo": ("#B692F6", "#B692F6"), "encerrada": ("#475467", "#EAECF0"), "liberdade": ("#D0D5DD", "#EEF0F3"), "livramento": ("#84CAFF", "#84CAFF"), "duvida": ("#F79009", "#FEF4D6")}
TL_ROT = {"provisoria": "prisão provisória (detração)", "cumprimento": "cumprimento da pena", "evasao": "fuga / evasão", "interrupcao": "interrupção (motivo a conferir)",
          "outro_motivo": "suspensão (preso por outro motivo)", "encerrada": "execução encerrada", "liberdade": "liberdade sem evasão", "livramento": "livramento", "duvida": "atribuição não comprovada"}


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
        marcos.append((D(L.get("ppe_termo")), "Trânsito (termo)", "#2563EB"))
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
        reinc = {"S/S": "específico", "S/N": "genérico", "N/S": "específico", "N/N": "primário"}.get(c.get("reinc") or "", c.get("reinc") or "")
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
        D = m.get("fd_rem_det")
        if D and (D["total"] >= 1 or D["em_curso"]["itens"] or D["lacunas"]["itens"]):
            import rspe_ficha as rf
            el.append(Spacer(1, 5))
            el.append(Paragraph(_t("A remir por origem: %s%s" % (rs.pl(int(D["total"]), "dia", "dias") if D["total"] == int(D["total"]) else _num(D["total"]) + " dias",
                                                                  (" (+ ≈ %s do trabalho em curso)" % rs.pl(D["em_curso"]["dias"], "dia", "dias")) if D["em_curso"]["dias"] else "")), st["neg"]))
            lin = [["Origem", "Dias", "De onde vem", "Providência"]]
            for k, r_, p_ in rf.ORIGENS_REMICAO + [("lacunas", "Lacuna entre atestados", "verificar com a unidade se houve trabalho")]:
                its = D[k]["itens"]
                if its:
                    est = k in ("sem_atestado", "em_curso") or (k == "estudo" and any(i["estimado"] for i in its))
                    lin.append([r_, ("≈ " if est else "") + _num(D[k]["dias"]) if D[k]["dias"] else "—",
                                "; ".join("%s, %s, %s%s" % (i["ref"], i.get("unidade") or "—", i["per"], (" (%s%s)" % ("≈ " if i["estimado"] else "", _num(i["dias"]))) if i["dias"] else "") for i in its), p_])
            el.append(_tabela(lin, [W * 0.22, W * 0.08, W * 0.46, W * 0.24], st))
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
    # 8) prescrição executória por crime (sem a figura da linha do tempo): detração, saldo na fuga e prazo dos crimes com
    #    evasão, prescrição aparente ou a verificar; todos os números vêm de ppe_linha_tempo / ppe_saldos
    pres = [L for L in m.get("presc_linhas", []) if L.get("ppe_linha_tempo") and L.get("ppe_saldos") and (
        L.get("ppe_cor") in ("vermelho", "amarelo") or any(x.get("tipo") in ("evasao", "interrupcao") for x in L["ppe_linha_tempo"]))]
    if pres:
        cabeca_secao = [Paragraph("Prescrição executória: cálculo por crime", st["h2"]),
                        Paragraph(_t("Para cada crime com fuga, prescrição aparente ou a verificar: detração, saldo da pena na fuga (CP, art. 113) e prazo. "
                                     "Com mais de uma condenação, o saldo fica entre dois limites, conforme a imputação do tempo cumprido."), st["mut"])]
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
            el.append(KeepTogether(cabeca_secao + [cab_crime]))
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
    """Título do alerta sem os dados do caso (processo, crime, datas, números), para agrupar os iguais."""
    t = re.sub(r"^.*?·\s*", "", t) if "·" in t.split(":")[0] else t
    t = re.sub(r"^[^:]*?art\. [^:]+?: ", "", t)
    while re.search(r"\([^()]*\)", t):
        t = re.sub(r"\s*\([^()]*\)", "", t)
    t = t.replace("(", "").replace(")", "")
    t = t.split(":")[0]
    t = re.sub(r"\s*,?\s*\b(em|de|desde|até|a partir de)\s+\d{2}/\d{2}/\d{4}", "", t)
    t = re.sub(r"\b\d{2}/\d{2}/\d{4}\b|(?<![/\d])\b\d+(?:[.,]\d+)?%?(?![/\d])", "", t)
    t = re.sub(r"\s+([,.;])", r"\1", re.sub(r"\s{2,}", " ", t)).replace(" em sem ", " sem ").strip(" ,;-")
    t = re.sub(r"\s+(em|de|há|acima de|a|e)$", "", t)
    return (t[:1].upper() + t[1:])[:80]


def _rotulo_regime(t):
    """'FECHADO - ATIVO' / 'Fechado' -> 'Fechado' (o mesmo regime não aparece duas vezes por causa da caixa)."""
    t = (t or "").split(" -")[0].strip()
    if not re.search(r"[A-Za-zÀ-ÿ]{3}", t):
        return "não consta"
    u = rs._sem_acento(t).upper()
    for k, rot in (("SEMI", "Semiaberto"), ("ABERTO", "Aberto"), ("FECHADO", "Fechado"), ("LIVRAMENTO", "Livramento condicional"),
                   ("RESTRITIVA", "Restritiva de direitos"), ("SURSIS", "Sursis"), ("MEDIDA", "Medida de segurança")):
        if k in u:
            return rot
    return t[:1].upper() + t[1:].lower()


def _rotulo_unidade(t):
    t = re.sub(r"\s+", " ", (t or "").strip())
    if not t:
        return "não informada"
    t = " ".join(w if w in ("CPAIG", "PTRAN", "EPJFC", "IPCG") or w[:1].isdigit() else w.lower() if w.upper() in ("DE", "DO", "DA", "DOS", "DAS", "E")
                 else w.title() for w in t.split())
    if len(t) > 50:
        t = re.sub(r"\bde Campo Grande\b", "de CG", t)  # nome longo: a cidade não pode sumir no corte ("...de Campo Gra")
    return t if len(t) <= 56 else t[:40].rstrip() + "… " + t[-14:].lstrip()


def _rotulo_vara(t):
    """Nome da vara encurtado e em caixa normal: '1ª VARA DE EXECUÇÃO PENAL DA COMARCA DE CAMPO GRANDE' -> '1ª VEP - Campo Grande'."""
    t = re.sub(r"\s+", " ", (t or "").strip())
    if not t:
        return "não consta"
    t = re.sub(r"^TJ[A-Z]{2}\s*-\s*", "", t, flags=re.I)
    t = re.sub(r"VARA DE EXECU[ÇC][ÃA]O PENAL", "VEP", t, flags=re.I)
    t = re.sub(r"VARA DE EXECU[ÇC][ÃA]O", "Vara de Execução", t, flags=re.I)
    t = re.sub(r"\s+(DA COMARCA DE|DE)\s+([A-ZÀ-Ü ]+)$", lambda m: " - " + m.group(2).title(), t)
    t = " ".join(w if (w in ("VEP", "TJMS") or w[:1].isdigit()) else w.lower() if w.upper() in ("DE", "DO", "DA", "DOS", "DAS") else
                 w.title() if w.isupper() else w for w in t.split())
    return t[:60]


def _dias_entre(a, b):
    a, b = rs.to_date(a or ""), rs.to_date(b or "")
    return (b - a).days if (a and b) else None


def estatisticas(modelos, hoje=None):
    hoje = hoje or date.today()
    n = len(modelos)
    E = {"n": n, "hoje": hoje}
    ger = [rs.to_date(m.get("geracao") or "") for m in modelos]
    ger = [g for g in ger if g]
    E["periodo"] = (min(ger), max(ger)) if ger else (None, None)
    E["incompletos"] = sum(1 for m in modelos if rs.campos_faltantes(m.get("_bruto") or {}))
    E["com_ficha"] = sum(1 for m in modelos if m.get("ficha_tem"))
    E["regime"] = Counter(_rotulo_regime(m.get("regime_rspe") or m.get("regime") or "") for m in modelos)
    E["vara"] = Counter(_rotulo_vara((m.get("_bruto") or {}).get("vara") or m.get("vara") or "") for m in modelos)
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
    # idade (data de nascimento do RSPE ou da ficha)
    fx_id, idades = Counter(), []
    for m in modelos:
        nasc = rs.to_date((m.get("_bruto") or {}).get("data_nascimento") or "")
        if not nasc:
            fx_id["sem data de nascimento"] += 1
            continue
        i = hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))
        idades.append(i)
        fx_id[next(r for lim, r in ((24, "18 a 24 anos"), (29, "25 a 29 anos"), (39, "30 a 39 anos"), (49, "40 a 49 anos"), (59, "50 a 59 anos"), (999, "60 anos ou mais")) if i <= lim)] += 1
    E["idade"], E["idade_media"] = fx_id, (sum(idades) / float(len(idades)) if idades else None)
    # conduta, trabalho e estudo (ficha disciplinar)
    cond, trab = Counter(), Counter()
    estudo = 0
    for m in modelos:
        if not m.get("ficha_tem"):
            continue
        c = rs._sem_acento(((m.get("ficha") or {}).get("conduta") or m.get("fd_conduta") or "").strip()).upper()
        # classificações do regulamento; sem classificação, o motivo da ficha (sem lapso, PADIC); vazio = "Não informada"
        # a ficha sem classificação traz o motivo: "SEM LAPSO" (sem tempo para avaliação) ou "RESPONDE PADIC/<unidade>"
        cond[{"OTIMA": "Ótima", "EXCELENTE": "Excelente", "BOA": "Boa", "REGULAR": "Regular", "MA": "Má", "PESSIMA": "Péssima", "RUIM": "Má",
              "NEUTRA": "Neutra"}.get(c) or ("Sem lapso" if c.startswith("SEM LAPSO") else "Responde PADIC" if "PADIC" in c
                                             else "Não informada" if not c else "Outra anotação")] += 1
        em_curso = [L for L in (m.get("fd_linhas") or []) if "em curso" in (L.get("per") or "")]
        if any("(externo)" in (L.get("emp") or "").lower() for L in em_curso):
            trab["Trabalha (externo)"] += 1
        elif em_curso:
            trab["Trabalha (interno)"] += 1
        else:
            trab["Não trabalha"] += 1
        estudo += not str(m.get("fd_estudo") or "Não").strip().lower().startswith("não")
    E["conduta"], E["trabalho"], E["estudo"] = cond, trab, estudo
    E["unidade"] = Counter(_rotulo_unidade(((m.get("ficha") or {}).get("unidade") or "")) for m in modelos if m.get("ficha_tem"))
    # remição: o que está pendente (assistidos e dias), pela ficha
    E["rem_ass_pend"] = E["rem_ass_sem_at"] = 0
    for m in modelos:
        if not m.get("ficha_tem"):
            continue
        mm_ = re.match(r"\s*([\d,]+)\s*/\s*([\d,]+)", m.get("fd_remidos") or "")
        if mm_ and float(mm_.group(1).replace(",", ".")) - float(mm_.group(2).replace(",", ".")) >= 1:
            E["rem_ass_pend"] += 1
        E["rem_ass_sem_at"] += bool(int(m.get("fd_sem_n") or 0))
        E["rem_sem_desc"] = E.get("rem_sem_desc", 0) + int(m.get("fd_sem_pend") or 0)

    # ---- benefícios: prazos do SEEU e, nos vencidos, o que o RSPE mostra depois da data ----
    SEM = {"lc": "em livramento", "aberto": "já no aberto", "cumprida": "pena cumprida", "extinta": "pena extinta", "nao_iniciou": "não iniciou",
           "lc_duvida": "livramento a verificar"}

    def faixa(m, campo_dias, campo_sit):
        d = m.get(campo_dias)
        if d is not None:
            return _prazo(d) or "mais de 180 dias"
        est = (m.get("estado_exec") or "")
        if est in SEM:
            return "não se aplica"
        if re.search(r"interrompid|suspens", (m.get(campo_sit) or "").lower()):
            return "interrompida"
        return "sem data no RSPE"
    E["faixas"] = {}
    E["venc"] = {}
    for rot, kd, ks, kp, cor in (("Progressão", "prog_dias", "prog_sit", "prog", "prog_cor"), ("Livramento condicional", "liv_dias", "liv_sit", "liv", "liv_cor")):
        E["faixas"][rot] = Counter(faixa(m, kd, ks) for m in modelos)
        v = [m for m in modelos if m.get(cor) == "vencido" or (m.get(kd) is not None and m.get(kd) <= 0 and not m.get("estado_exec"))]
        E["venc"][rot] = {"total": len(v),
                          "sem_pedido": sum(1 for m in v if "sem pedido" in (m.get(ks) or "") and not (m.get("pedidos") or {}).get(kp)),
                          "pendente": sum(1 for m in v if "pendente" in (m.get(ks) or "")),
                          "indeferido": sum(1 for m in v if "indeferido" in (m.get(ks) or "")),
                          "marcado": sum(1 for m in v if (m.get("pedidos") or {}).get(kp))}
    E["faixas"]["Término da pena"] = Counter((_prazo(m.get("ext_dias")) or "mais de 180 dias") if m.get("ext_dias") is not None else
                                             ("não se aplica" if m.get("estado_exec") in SEM else "sem data no RSPE") for m in modelos)
    E["venc_assist"] = sum(1 for m in modelos if m.get("prog_cor") == "vencido" or m.get("liv_cor") == "vencido")
    E["venc_sem_pedido"] = sum(1 for m in modelos if any(m.get(c) == "vencido" and "sem pedido" in (m.get(s_) or "") and not (m.get("pedidos") or {}).get(k)
                                                          for c, s_, k in (("prog_cor", "prog_sit", "prog"), ("liv_cor", "liv_sit", "liv"))))

    # ---- faltas graves: RSPE (incidentes) e ficha disciplinar (PADIC) ----
    lim12 = hoje - timedelta(days=365)
    F = {"firme12": 0, "apurar12": 0, "rspe_hom": 0, "rspe_pend": 0, "rspe_neg": 0, "rspe_hom12": 0, "rspe_pend12": 0, "assist_pend": 0,
         "regr12": 0, "perda12": 0, "pend_dias": []}
    for m in modelos:
        F["firme12"] += bool(m.get("falta_sim"))
        F["apurar12"] += bool(m.get("falta_apurar"))
        tem_pend = False
        for i in (m.get("_bruto") or {}).get("_incidentes") or []:
            rot = rs._rotulo_incidente(i)
            d = rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "")
            if rs.RE_FALTA_PROPRIA.search(rot):
                df = rs._data_fato_falta(i) or d
                if rs._negado(i):
                    F["rspe_neg"] += 1
                elif rs._pendente(i):
                    F["rspe_pend"] += 1
                    tem_pend = True
                    F["rspe_pend12"] += bool(df and df >= lim12)
                    if df:
                        F["pend_dias"].append((hoje - df).days)
                else:
                    F["rspe_hom"] += 1
                    F["rspe_hom12"] += bool(df and df >= lim12)
            elif d and d >= lim12 and not rs._negado(i) and not rs._pendente(i):
                if re.search(r"REGRESS", rot, re.I):
                    F["regr12"] += 1
                elif re.search(r"PERD", rot, re.I) and re.search(r"REMI", rot, re.I):
                    F["perda12"] += 1
        F["assist_pend"] += tem_pend
    P = {"registrada": 0, "PADIC instaurado": 0, "homologada/punida": 0, "arquivada": 0}
    P_ass = Counter()
    resp, abertos60, graves = [], 0, 0
    for m in modelos:
        fa = ((m.get("ficha") or {}).get("faltas")) or []
        sit_m = set()
        for x in fa:
            sit = x.get("situacao") or "registrada"
            P[sit] = P.get(sit, 0) + 1
            sit_m.add(sit)
            graves += bool(x.get("grave"))
            if sit in ("homologada/punida", "arquivada"):
                dd = _dias_entre(x.get("data_fato") or x.get("data_registro"), x.get("data_resultado"))
                if dd is not None and dd >= 0:
                    resp.append(dd)
            else:
                dd = _dias_entre(x.get("data_fato") or x.get("data_registro"), rs.fmt(hoje))
                abertos60 += bool(dd is not None and dd > 60)
        for sit in sit_m:
            P_ass[sit] += 1
    resp.sort()
    F["padic"], F["padic_ass"], F["padic_graves"] = P, P_ass, graves
    F["padic_resp_mediana"] = resp[len(resp) // 2] if resp else None
    F["padic_resp_n"] = len(resp)
    F["padic_abertos60"] = abertos60
    E["faltas"] = F

    # ---- indulto e comutação: todos os decretos do sistema ----
    D = {}
    ind_algum = ind_sem_ped = 0
    for m in modelos:
        peds = m.get("pedidos") or {}
        algum = sem = False
        for x in ((m.get("dec") or {}).get("decretos") or []):
            k = x.get("id")
            row = D.setdefault(k, {"id": k, "ano": x.get("ano"), "numero": x.get("numero") or "", "ref": x.get("ref") or "", "tipo": x.get("tipo") or "",
                                   "cabe": 0, "ver": 0, "nao": 0, "imp": 0, "conc": 0, "indef": 0, "fora": 0, "ped": 0, "cabe_sem_ped": 0})
            sx = x.get("s") or "fora"
            sx = "fora" if sx == "futuro" else sx
            row[sx] = row.get(sx, 0) + 1
            if peds.get("ind_" + str(k)):
                row["ped"] += 1
            if sx == "cabe":
                algum = True
                if not peds.get("ind_" + str(k)) and not peds.get("ind"):
                    row["cabe_sem_ped"] += 1
                    sem = True
        ind_algum += algum
        ind_sem_ped += sem
    E["decretos"] = sorted(D.values(), key=lambda r: (-(r["ano"] or 0), r["id"]))
    E["ind_algum"], E["ind_sem_ped"] = ind_algum, ind_sem_ped
    E["ind_ver"] = sum(1 for m in modelos if any(x.get("s") == "ver" for x in ((m.get("dec") or {}).get("decretos") or [])))

    # ---- prescrição e extinção ----
    E["presc"] = Counter(("aparente" if m.get("presc_ppe_cor") == "vermelho" else "iminente / a verificar" if m.get("presc_ppe_cor") == "amarelo" else
                          "sem dados" if m.get("presc_ppe_cor") == "cinza" else "não prescrita") for m in modelos)
    E["presc_punitiva"] = sum(1 for m in modelos if m.get("presc_retro_cor") == "vermelho")
    E["presc_crimes"] = sum(1 for m in modelos for L in (m.get("presc_linhas") or []) if L.get("ppe_cor") == "vermelho")
    E["ext_cabivel"] = sum(1 for m in modelos if m.get("ext_cor") == "vermelho")
    E["ext_verificar"] = sum(1 for m in modelos if m.get("ext_cor") == "amarelo")
    E["term_calc"] = sum(1 for m in modelos if (m.get("ext_termino") or "").endswith("*"))
    E["ext_registrada"] = sum(1 for m in modelos if m.get("ext_cor") == "azul")

    # ---- remição ----
    rem = [rs.saldo_remidos_num((m.get("_bruto") or {}).get("saldo_remidos"))[0] or 0 for m in modelos]
    E["rem_total"], E["rem_media"], E["rem_zero"] = sum(rem), (sum(rem) / float(n) if n else 0), sum(1 for x in rem if not x)
    rp = tr = es = 0
    rem_req = 0
    for m in modelos:
        if not m.get("ficha_tem"):
            continue
        mm = re.match(r"\s*([\d,]+)\s*/\s*([\d,]+)", m.get("fd_remidos") or "")
        rp += max(0.0, float(mm.group(1).replace(",", ".")) - float(mm.group(2).replace(",", "."))) if mm else 0
        tr += int(m.get("fd_sem_n") or 0)
        me = re.search(r"≈ (\d+) dias?\b", m.get("fd_estudo") or "")
        es += int(me.group(1)) if me else 0
        rem_req += m.get("fd_cor") == "vermelho"
    E["rem_pend"], E["rem_trab"], E["rem_est"], E["rem_req"] = rp, tr, es, rem_req
    E["rem_orig"] = remicao_por_origem(modelos)

    # ---- Auditoria ----
    cat, catv = Counter(), Counter()
    for m in modelos:
        for i in m.get("aud_itens", []):
            if i.get("baixado"):
                continue
            if i["nivel"] == "alerta":
                cat[_categoria_alerta(i["titulo"])] += 1
            elif i["nivel"] == "verificar":
                catv[_categoria_alerta(i["titulo"])] += 1
    E["alertas"], E["verificar"] = cat, catv
    E["com_alerta"] = sum(1 for m in modelos if m.get("aud_alertas"))
    E["n_alertas"], E["n_verificar"] = sum(cat.values()), sum(catv.values())
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
        peds = m.get("pedidos") or {}
        cab = [x for x in ((m.get("dec") or {}).get("decretos") or []) if x.get("s") == "cabe" and not peds.get("ind_" + str(x.get("id"))) and not peds.get("ind")]
        if cab:
            mot.append((3, "Indulto/comutação cabível sem pedido: %s" % ", ".join("%s (%s)" % (x.get("beneficio") or "benefício", x.get("ano")) for x in cab), ""))
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


# paleta categórica (ordem fixa, validada: CVD e visão normal) e cinza reservado para "Outros"/"sem dado"
CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
CINZA_OUTROS = "#C4C9D2"


def _rosca(titulo, pares, largura, st, total_rot="", max_fatias=6, cores=None, nota="", ordenar=True, abaixo=False):
    """Gráfico de rosca com o total no centro e o percentual escrito em cada fatia de 8% ou mais; ao lado, a legenda em
    colunas alinhadas (categoria | quantidade | %). Até 6 fatias (8 com max_fatias) na ordem fixa da paleta, do maior ao menor;
    o resto vai para "Outros" (cinza). Com uma só categoria, o gráfico sai inteiro (100%)."""
    from reportlab.graphics.shapes import Drawing, Wedge, String, Rect, Circle, Line
    from reportlab.lib import colors
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.platypus import Paragraph
    import math
    f = _fontes()
    pares = [(r, v) for r, v in pares if v]
    cinzas = {"Outros", "não consta", "sem data de nascimento", "Não informada", "não informada", "sem pena no RSPE", "Sem dados no RSPE"}
    fixos = [p for p in pares if p[0] in cinzas]
    pares = [p for p in pares if p[0] not in cinzas]
    if ordenar:
        pares.sort(key=lambda p: -p[1])
    if len(pares) > max_fatias:
        resto = sum(v for _, v in pares[max_fatias - 1:])
        pares = pares[:max_fatias - 1] + [("Outros", resto)]
    pares += fixos
    tot = sum(v for _, v in pares)
    corpo = [Paragraph(_t(titulo), st["neg"])]
    if not tot:
        corpo.append(Paragraph("Sem dados.", st["mut"]))
        return corpo
    D = (32 if largura > 300 else 27) * 2.835
    gap = 10
    leg_x = D + gap
    leg_w = largura - leg_x
    if abaixo:  # rosca em cima, centralizada; legenda embaixo, na largura toda
        D = min(30 * 2.835, largura * 0.62)
        leg_x, leg_w = 0, largura
    col_n, col_p = leg_w - 30, leg_w - 2  # posições (direita) das colunas Nº e %

    def quebra(rot, larg):
        ls, atual = [], ""
        for p in rot.split():
            if stringWidth((atual + " " + p).strip(), f["n"], 7.4) > larg and atual:
                ls.append(atual)
                atual = p
            else:
                atual = (atual + " " + p).strip()
        ls.append(atual)
        if len(ls) > 3:
            ls = ls[:2] + [" ".join(ls[2:])]
            while stringWidth(ls[2] + "...", f["n"], 7.4) > larg and len(ls[2]) > 4:
                ls[2] = ls[2][:-1]
            ls[2] = ls[2].rstrip() + ("…" if f["unicode"] else "...")
        return ls
    rot_larg = col_n - 22 - 11
    rotulos = [quebra(r, rot_larg) for r, _ in pares]
    alt_leg = 12 + sum(4 + 9.5 * len(ls) for ls in rotulos)
    h = (D + 10 + alt_leg + 4) if abaixo else max(D + 8, alt_leg + 4)
    d = Drawing(largura, h)
    cx, cy, r = (largura / 2.0 if abaixo else D / 2.0 + 2), h - D / 2.0 - 4, D / 2.0
    ri = r * 0.56
    ang = 90.0
    cor_de, k = {}, 0
    for rot, v in pares:
        if (cores or {}).get(rot):
            cor = cores[rot]
            k += rot not in cinzas
        elif rot in cinzas:
            cor = CINZA_OUTROS
        else:
            cor = CAT[k % len(CAT)]
            k += 1
        cor_de[rot] = cor
        ext = 360.0 * v / tot
        if ext >= 359.99:
            d.add(Circle(cx, cy, r, fillColor=colors.HexColor(cor), strokeColor=None))
        else:
            d.add(Wedge(cx, cy, r, ang - ext, ang, fillColor=colors.HexColor(cor), strokeColor=colors.white, strokeWidth=1.5))
        if v / float(tot) >= 0.08:
            meio = math.radians(ang - ext / 2.0)
            rm = (r + ri) / 2.0
            pt = "%d%%" % round(100.0 * v / tot)
            d.add(String(cx + rm * math.cos(meio) - stringWidth(pt, f["b"], 7) / 2.0, cy + rm * math.sin(meio) - 2.5, pt,
                         fontName=f["b"], fontSize=7, fillColor=colors.white))
        ang -= ext
    d.add(Circle(cx, cy, ri, fillColor=colors.white, strokeColor=None))
    tt = str(tot)
    d.add(String(cx - stringWidth(tt, f["b"], 13) / 2.0, cy - 1, tt, fontName=f["b"], fontSize=13, fillColor=colors.HexColor(TX)))
    if total_rot:
        d.add(String(cx - stringWidth(total_rot, f["n"], 6.4) / 2.0, cy - 10, total_rot, fontName=f["n"], fontSize=6.4, fillColor=colors.HexColor(TX2)))
    # legenda em colunas: cabeçalho, linhas com fio fino
    y = (h - D - 16) if abaixo else (h - 9)
    for txt, xr in (("Nº", col_n), ("%", col_p)):
        d.add(String(leg_x + xr - stringWidth(txt, f["b"], 6.6), y, txt, fontName=f["b"], fontSize=6.6, fillColor=colors.HexColor(TX2)))
    d.add(Line(leg_x, y - 3, leg_x + leg_w - 2, y - 3, strokeColor=colors.HexColor("#D0D5DD"), strokeWidth=0.5))
    y -= 13
    for (rot, v), ls in zip(pares, rotulos):
        d.add(Rect(leg_x, y, 7, 7, fillColor=colors.HexColor(cor_de[rot]), strokeColor=None, rx=1.5, ry=1.5))
        for j, l in enumerate(ls):
            d.add(String(leg_x + 11, y + 0.5 - 9.5 * j, l, fontName=f["n"], fontSize=7.4, fillColor=colors.HexColor(TX)))
        for txt, xr, fn in ((str(v), col_n, f["b"]), ("%d%%" % round(100.0 * v / tot), col_p, f["n"])):
            d.add(String(leg_x + xr - stringWidth(txt, fn, 7.4), y + 0.5, txt, fontName=fn, fontSize=7.4, fillColor=colors.HexColor(TX)))
        yl = y - 9.5 * (len(ls) - 1) - 3.5
        d.add(Line(leg_x, yl, leg_x + leg_w - 2, yl, strokeColor=colors.HexColor(LINE), strokeWidth=0.4))
        y -= 4 + 9.5 * len(ls)
    corpo.append(d)
    if nota:
        corpo.append(Paragraph(_t(nota), st["mut"]))
    return corpo


def _colunas(titulo, categorias, series, largura, st, altura=120, sufixo="", nota=""):
    """Colunas verticais: categorias no eixo x; series = [(nome, [valores], cor)], empilhadas quando mais de uma.
    Valor escrito sobre cada coluna (o total, se empilhada); grade recessiva; legenda acima quando há mais de uma série."""
    from reportlab.graphics.shapes import Drawing, Rect, String, Line
    from reportlab.lib import colors
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.platypus import Paragraph
    f = _fontes()
    corpo = [Paragraph(_t(titulo), st["neg"])]
    tots = [sum(s_[1][i] for s_ in series) for i in range(len(categorias))]
    if not categorias or not any(tots):
        corpo.append(Paragraph("Sem dados.", st["mut"]))
        return corpo
    mx = max(tots) or 1
    leg_h = 14 if len(series) > 1 else 0

    def quebra(t, larg):
        ls, at = [], ""
        for p in t.split():
            if stringWidth((at + " " + p).strip(), f["n"], 6.8) > larg and at:
                ls.append(at)
                at = p
            else:
                at = (at + " " + p).strip()
        return ls + [at]
    passo = (largura - 6) / float(len(categorias))
    rots = [quebra(c, passo - 4) for c in categorias]
    rot_h = 9 * max(len(r) for r in rots) + 4
    h = altura + rot_h + leg_h + 14
    d = Drawing(largura, h)
    y0 = rot_h + 2
    alt = altura - 6
    for k in range(1, 5):  # grade recessiva
        yy = y0 + alt * k / 4.0
        d.add(Line(0, yy, largura, yy, strokeColor=colors.HexColor("#EEF0F3"), strokeWidth=0.4))
    d.add(Line(0, y0, largura, y0, strokeColor=colors.HexColor("#D0D5DD"), strokeWidth=0.6))
    bw = min(passo * 0.56, 34)
    for i, cat in enumerate(categorias):
        x = 3 + passo * i + (passo - bw) / 2.0
        yb = y0
        for nome, vals, cor in series:
            v = vals[i]
            hh = alt * v / float(mx)
            if v:
                d.add(Rect(x, yb, bw, hh, fillColor=colors.HexColor(cor), strokeColor=colors.white, strokeWidth=1, rx=1.5, ry=1.5))
            yb += hh
        tv = "%s%s" % (tots[i], sufixo)
        d.add(String(x + bw / 2.0 - stringWidth(tv, f["b"], 7.2) / 2.0, yb + 3, tv, fontName=f["b"], fontSize=7.2, fillColor=colors.HexColor(TX)))
        for j, l in enumerate(rots[i]):
            d.add(String(3 + passo * i + passo / 2.0 - stringWidth(l, f["n"], 6.8) / 2.0, y0 - 9 - 9 * j, l, fontName=f["n"], fontSize=6.8,
                         fillColor=colors.HexColor(TX2)))
    if leg_h:
        x = 0
        for nome, _, cor in series:
            d.add(Rect(x, h - 9, 7, 7, fillColor=colors.HexColor(cor), strokeColor=None, rx=1.5, ry=1.5))
            d.add(String(x + 10, h - 8.5, nome, fontName=f["n"], fontSize=7.2, fillColor=colors.HexColor(TX)))
            x += 18 + stringWidth(nome, f["n"], 7.2)
    corpo.append(d)
    if nota:
        corpo.append(Paragraph(_t(nota), st["mut"]))
    return corpo


def relatorio_geral(modelos, caminho, nome_base, nominal=True):
    """Relatório geral (diagnóstico da base): dados crus da população, sem o controle de pedidos do programa.
    1. Perfil da população; 2. Trabalho, conduta e disciplina; 3. Situação jurídico-executória; 4. Inconsistências do cálculo."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, CondPageBreak
    st = _estilos()
    C = st["C"]
    W = A4[0] - 32 * mm
    E = estatisticas(modelos)
    F = E["faltas"]
    n = E["n"] or 1
    nf = E["com_ficha"]
    el = []
    pct = lambda x, base=n: ("%d%%" % round(100.0 * x / base)) if base else "—"
    st_parte = ParagraphStyle("parte", parent=st["tit"], fontSize=13, leading=17, textColor=C(PRI), spaceBefore=4)
    RW = W / 2.0 - 10

    def numeros(lista, cores=None):
        cel = []
        for k, it in enumerate(lista):
            v, rot = it[0], it[1]
            det = it[2] if len(it) > 2 else ""
            cor = (cores or {}).get(k)
            num = Paragraph('<font color="%s">%s</font>' % (COR[cor][1], _t(str(v))) if cor else _t(str(v)), st["num"])
            cel.append([num, Paragraph(_t(rot), st["rot"])] + ([Paragraph(_t(det), st["mut"])] if det else []))
        t = Table([cel], colWidths=[W / len(lista)] * len(lista))
        t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.6, C(LINE)), ("LINEBELOW", (0, 0), (-1, 0), 0.6, C(LINE)),
                               ("LINEAFTER", (0, 0), (-2, 0), 0.6, C(LINE)), ("TOPPADDING", (0, 0), (-1, -1), 6),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 7), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t

    def parte(num, titulo, sub=""):
        el.append(CondPageBreak(110 * mm))  # o título da parte não fica sozinho no pé da página
        el.append(Spacer(1, 6))
        el.append(Paragraph(_t("%s. %s" % (num, titulo)), st_parte))
        if sub:
            el.append(Paragraph(_t(sub), st["mut"]))
        el.append(Spacer(1, 6))

    def secao(titulo, sub=""):
        el.append(CondPageBreak(45 * mm))
        el.append(Paragraph(_t(titulo), st["h2"]))
        if sub:
            el.append(Paragraph(_t(sub), st["mut"]))
            el.append(Spacer(1, 3))

    def lado(c1, c2):
        t = Table([[c1, c2]], colWidths=[W / 2.0, W / 2.0])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                               ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 12)]))
        el.append(t)

    # ------------------------------------------------------------ cabeçalho
    el.append(Paragraph(_t("Relatório geral da base · %s" % nome_base), st["tit"]))
    p0, p1 = E["periodo"]
    el.append(Paragraph(_t("Diagnóstico de %s · RSPEs gerados entre %s e %s · %d com ficha disciplinar (SIAPEN) · emitido em %s" % (
        rs.pl(E["n"], "assistido", "assistidos"), rs.fmt(p0) or "?", rs.fmt(p1) or "?", nf, datetime.now().strftime("%d/%m/%Y"))), st["sub"]))

    # ============================================================ 1. perfil
    parte(1, "Perfil da população")
    el.append(numeros([(E["n"], "assistidos na base"),
                       (("%.0f" % E["idade_media"]) if E["idade_media"] is not None else "—", "anos de idade, em média"),
                       (pct(E["hed"]), "com crime hediondo ou equiparado"),
                       (pct(E["vga"]), "com crime cometido com violência ou grave ameaça"),
                       (pct(E["reinc"]), "reincidentes, segundo o RSPE")]))
    el.append(Spacer(1, 10))
    ordem_id = ["18 a 24 anos", "25 a 29 anos", "30 a 39 anos", "40 a 49 anos", "50 a 59 anos", "60 anos ou mais", "sem data de nascimento"]
    ordem_pena = ["até 4 anos", "4 a 8 anos", "8 a 12 anos", "12 a 20 anos", "mais de 20 anos", "sem pena no RSPE"]
    lado(_rosca("1.1 Faixa etária", [(k, E["idade"].get(k, 0)) for k in ordem_id], RW, st, "assistidos", max_fatias=7, ordenar=False),
         _rosca("1.2 Regime de cumprimento", E["regime"].most_common(), RW, st, "assistidos"))
    lado(_rosca("1.3 Pena total aplicada", [(k, E["pena"].get(k, 0)) for k in ordem_pena], RW, st, "assistidos", ordenar=False),
         _rosca("1.4 Juízo da execução", E["vara"].most_common(), RW, st, "assistidos"))
    if nf:
        el.append(KeepTogether(_rosca("1.5 Unidade prisional (ficha disciplinar)", E["unidade"].most_common(), W, st, "com ficha", max_fatias=8)))
        el.append(Spacer(1, 10))
    el.append(KeepTogether(_rosca("%s Incidência penal: crimes em execução" % ("1.6" if nf else "1.5"), E["artigos"].most_common(), W, st, "crimes", max_fatias=8)))

    # ============================================================ 2. trabalho, conduta e disciplina
    parte(2, "Trabalho, conduta e disciplina",
          "Conduta, trabalho, estudo e PADIC: ficha disciplinar (SIAPEN), %s. Faltas com decisão judicial: RSPE, toda a base." % rs.pl(nf, "assistido com ficha", "assistidos com ficha"))
    P = F["padic"]
    trab_n = E["trabalho"].get("Trabalha (interno)", 0) + E["trabalho"].get("Trabalha (externo)", 0)
    el.append(numeros([(trab_n, "trabalham", (pct(trab_n, nf) + " dos com ficha") if nf else ""),
                       (E["estudo"], "estudam", (pct(E["estudo"], nf) + " dos com ficha") if nf else ""),
                       (P.get("PADIC instaurado", 0), "PADICs em trâmite", "sem julgamento na unidade"),
                       (F["rspe_pend"], "faltas graves sem decisão judicial", rs.pl(F["assist_pend"], "assistido", "assistidos")),
                       (F["firme12"], "assistidos com falta grave nos últimos 12 meses", "sanção reconhecida em juízo")],
                      {2: "amarelo", 3: "amarelo", 4: "laranja"}))
    el.append(Spacer(1, 10))
    ordem_c = ["Excelente", "Ótima", "Boa", "Neutra", "Regular", "Má", "Péssima", "Sem lapso", "Responde PADIC", "Outra anotação", "Não informada"]
    cores_c = {"Excelente": "#008300", "Ótima": "#1baf7a", "Boa": "#2a78d6", "Neutra": "#4a3aa7", "Regular": "#eda100", "Má": "#eb6834", "Péssima": "#e34948",
               "Sem lapso": "#98a2b3", "Responde PADIC": "#b42318", "Outra anotação": "#d0d5dd"}
    lado(_rosca("2.1 Conduta carcerária", [(k, E["conduta"].get(k, 0)) for k in ordem_c], RW, st, "com ficha", max_fatias=8, cores=cores_c, ordenar=False),
         _rosca("2.2 Situação laboral", [(k, E["trabalho"].get(k, 0)) for k in ("Trabalha (interno)", "Trabalha (externo)", "Não trabalha")], RW, st, "com ficha",
                cores={"Trabalha (interno)": "#2a78d6", "Trabalha (externo)": "#1baf7a", "Não trabalha": "#eb6834"}, ordenar=False))
    resp = ("Tempo de resposta do PADIC (do fato à decisão): mediana de %s. " % rs.pl(F["padic_resp_mediana"], "dia", "dias")) if F["padic_resp_mediana"] is not None else ""
    mp = sorted(F["pend_dias"])
    lado(_rosca("2.3 Faltas na ficha: situação do PADIC", [("Registrada, sem PADIC instaurado", P.get("registrada", 0)), ("PADIC em trâmite", P.get("PADIC instaurado", 0)),
                                                          ("Julgada: sanção aplicada", P.get("homologada/punida", 0)), ("Julgada: arquivada ou absolvido", P.get("arquivada", 0))],
                RW, st, "faltas", ordenar=False,
                cores={"Registrada, sem PADIC instaurado": "#eda100", "PADIC em trâmite": "#eb6834", "Julgada: sanção aplicada": "#2a78d6",
                       "Julgada: arquivada ou absolvido": "#1baf7a"},
                nota=resp + "%s sem julgamento há mais de 60 dias do fato." % rs.pl(F["padic_abertos60"], "falta", "faltas")),
         _rosca("2.4 Faltas graves no RSPE: decisão judicial", [("Homologadas", F["rspe_hom"]), ("Sem decisão (pendentes)", F["rspe_pend"]),
                                                                ("Não homologadas ou afastadas", F["rspe_neg"])], RW, st, "faltas", ordenar=False,
                cores={"Homologadas": "#2a78d6", "Sem decisão (pendentes)": "#eb6834", "Não homologadas ou afastadas": "#1baf7a"},
                nota=("A falta pendente mais antiga aguarda decisão há %s." % rs.pl(mp[-1], "dia", "dias")) if mp else ""))
    secao("2.5 Remição: pendências", "Pela ficha disciplinar x RSPE: dias que ainda não viraram remição no RSPE, pela origem. "
          "O detalhe por assistido e por unidade está no relatório \"Remição detalhada\".")
    O = E["rem_orig"]
    el.append(numeros([(O["ass"], "assistidos com remição a requerer", "%s sem nenhuma remição no RSPE (toda a base)" % E["rem_zero"]),
                       (_num(int(O["total"])), "dias a remir (todas as origens)"),
                       (_num(int(O["dias"]["nao_lancado"])), "dias de atestados emitidos sem remição no RSPE", rs.pl(O["n"]["nao_lancado"], "assistido", "assistidos")),
                       (_num(int(O["dias"]["sem_atestado"])), "dias de trabalho sem atestado (estimativa)", rs.pl(O["n"]["sem_atestado"], "assistido", "assistidos")),
                       (_num(int(O["dias"]["estudo"])), "dias de estudo sem remição (≈)", rs.pl(O["n"]["estudo"], "assistido", "assistidos"))],
                      {0: "amarelo", 1: "amarelo", 2: "vermelho", 3: "amarelo", 4: "amarelo"}))

    # ============================================================ 3. situação jurídico-executória
    parte(3, "Situação jurídico-executória",
          "Progressão, livramento e término: datas do SEEU. Indulto, comutação, prescrição e extinção: cálculo do programa sobre os dados do RSPE.")
    pres = E["presc"]
    indic = [("vermelho", "Prescrição da pretensão executória aparente", pres.get("aparente", 0), rs.pl(E["presc_crimes"], "condenação", "condenações")),
             ("vermelho", "Prescrição da pretensão punitiva aparente", E["presc_punitiva"], ""),
             ("vermelho", "Extinção da pena pelo cumprimento cabível", E["ext_cabivel"], ""),
             ("vencido", "Progressão de regime com lapso vencido", E["venc"]["Progressão"]["total"], ""),
             ("vencido", "Livramento condicional com lapso vencido", E["venc"]["Livramento condicional"]["total"], ""),
             ("verde", "Indulto ou comutação cabível em ao menos um decreto", E["ind_algum"], ""),
             ("amarelo", "Indulto ou comutação a verificar", E["ind_ver"], "")]
    curtos = ["Prescrição executória", "Prescrição punitiva", "Extinção cabível", "Progressão vencida", "Livramento vencido",
              "Indulto/comutação cabível", "Indulto/comutação a verificar"]
    el.append(KeepTogether(_colunas("3.1 Indicadores: assistidos em cada situação (% da base)", curtos,
                                    [("% da base", [round(100.0 * x[2] / n) for x in indic], "#2a78d6")], W, st, altura=105, sufixo="%",
                                    nota="Um mesmo assistido pode estar em mais de um indicador.")))
    el.append(Spacer(1, 6))
    tb = [["Indicador", "Assistidos", "% da base", "Observação"]]
    cores = {}
    for k, (cor, rot, v, det) in enumerate(indic, 1):
        tb.append([Paragraph(_t(rot), st["neg"]), str(v), pct(v), det])
        if v:
            cores[k] = cor
    el.append(_tabela(tb, [W * 0.5, W * 0.13, W * 0.13, W * 0.24], st, cores_linha=cores))

    secao("3.2 Prazos de progressão, livramento e término", "Assistidos por faixa de prazo, de hoje até a data prevista no SEEU.")
    grupos = [("Vencido", ["vencido"]), ("Até 90 dias", ["até 30 dias", "até 60 dias", "até 90 dias"]), ("91 a 180 dias", ["até 180 dias"]),
              ("Mais de 180 dias", ["mais de 180 dias"]), ("Pena parada", ["interrompida"]), ("Não se aplica", ["não se aplica"]), ("Sem data no RSPE", ["sem data no RSPE"])]
    cor_g = {"Vencido": "#e34948", "Até 90 dias": "#eda100", "91 a 180 dias": "#2a78d6", "Mais de 180 dias": "#1baf7a", "Pena parada": "#4a3aa7",
             "Não se aplica": "#98A2B3", "Sem data no RSPE": "#D0D5DD"}
    W3 = W / 3.0 - 8
    trio = []
    for rot in ("Progressão", "Livramento condicional", "Término da pena"):
        c = E["faixas"].get(rot, Counter())
        trio.append(_rosca(rot, [(g, sum(c.get(k, 0) for k in ks)) for g, ks in grupos], W3, st, "assistidos", max_fatias=8,
                           cores=cor_g, ordenar=False, abaixo=True))
    t3 = Table([trio], colWidths=[W / 3.0] * 3)
    t3.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 8)]))
    el.append(t3)
    el.append(Spacer(1, 6))
    fx = ["vencido", "até 30 dias", "até 60 dias", "até 90 dias", "até 180 dias", "mais de 180 dias", "interrompida", "não se aplica", "sem data no RSPE"]
    cab = ["", "Vencido", "≤ 30 dias", "31 a 60", "61 a 90", "91 a 180", "> 180 dias", "Pena parada", "Não se aplica", "Sem data"]
    tb = [cab]
    for rot in ("Progressão", "Livramento condicional", "Término da pena"):
        c = E["faixas"].get(rot, Counter())
        tb.append([Paragraph(_t(rot), st["neg"])] + [str(c.get(k, 0)) for k in fx])
    el.append(KeepTogether([_tabela(tb, [W * 0.19] + [W * 0.09] * 9, st, pad=4)]))
    el.append(Paragraph(_t("Pena parada: foragido (interrompida) ou preso por outro processo (suspensa). Não se aplica: em livramento, já no regime aberto, "
                           "pena cumprida ou extinta, ou cumprimento não iniciado."), st["mut"]))

    secao("3.3 Indulto e comutação por decreto",
          "Assistidos por decreto, do mais recente ao mais antigo; cada assistido conta uma vez por decreto, pelo melhor resultado (indulto ou comutação).")
    com_alc = [r for r in E["decretos"] if r["cabe"] + r["ver"] + r["nao"] + r["imp"] + r["conc"] + r["indef"]]
    graf = [r for r in reversed(com_alc) if r["cabe"] + r["ver"] + r["conc"]]
    if graf:
        el.append(KeepTogether(_colunas("Assistidos com indulto ou comutação cabível, a verificar ou concedido, por decreto",
                                        [("%s%s" % (r["ano"], " Mães" if "maes" in str(r["id"]) else "")) for r in graf],
                                        [("Cabe", [r["cabe"] for r in graf], "#1baf7a"), ("A verificar", [r["ver"] for r in graf], "#eda100"),
                                         ("Concedido (RSPE)", [r["conc"] for r in graf], "#2a78d6")], W, st, altura=100)))
        el.append(Spacer(1, 6))
    # quadro resumido: uma linha por decreto com algum resultado favorável ou decisão no RSPE; os demais, numa linha só
    rel = [r for r in com_alc if r["cabe"] + r["ver"] + r["conc"] + r["indef"]]
    resto = [r for r in com_alc if r not in rel]
    tb = [["Decreto", "Cabe", "A verificar", "Concedido (RSPE)", "Indeferido (RSPE)", "Não cabe ou vedado"]]
    cores = {}
    for r in rel:
        nome = "%s%s" % (r["ano"], " (Dia das Mães)" if "maes" in str(r["id"]) else "")
        tb.append([Paragraph("<b>%s</b> · Decreto %s" % (_t(nome), _t(r["numero"])), st["cel"]), str(r["cabe"]), str(r["ver"]), str(r["conc"]),
                   str(r["indef"]), str(r["nao"] + r["imp"])])
        cores[len(tb) - 1] = "verde" if r["cabe"] else ("amarelo" if r["ver"] else "")
    if resto:
        anos = sorted(r["ano"] for r in resto if r["ano"])
        tb.append([Paragraph(_t("Demais %s (%s)" % (rs.pl(len(resto), "decreto", "decretos"), ("%s a %s" % (anos[0], anos[-1])) if anos else "")), st["cel"]),
                   "0", "0", "0", "0", str(sum(r["nao"] + r["imp"] for r in resto))])
    el.append(_tabela(tb, [W * 0.3, W * 0.12, W * 0.13, W * 0.15, W * 0.15, W * 0.15], st, cores_linha=cores, pad=4))
    sem = [("%s%s" % (r["ano"], " (Dia das Mães)" if "maes" in str(r["id"]) else "")) for r in E["decretos"] if r not in com_alc]
    if sem:
        el.append(Paragraph(_t("Decretos que não alcançam nenhum assistido (execução iniciada depois): %s." % ", ".join(sem)), st["mut"]))

    secao("3.4 Prescrição e extinção da pena")
    ret = Counter()
    for m in modelos:
        c_ = m.get("presc_retro_cor")
        ret["Aparente" if c_ == "vermelho" else "Sem dados no RSPE" if c_ == "cinza" else "Não configurada"] += 1
    cor_p = {"Aparente": "#e34948", "Iminente ou a verificar": "#eda100", "Não prescrita": "#1baf7a", "Não configurada": "#1baf7a"}
    demais = max(0, E["n"] - E["ext_cabivel"] - E["ext_verificar"] - E["ext_registrada"])
    W3 = W / 3.0 - 8
    trio = [_rosca("Pretensão executória", [("Aparente", pres.get("aparente", 0)), ("Iminente ou a verificar", pres.get("iminente / a verificar", 0)),
                                            ("Não prescrita", pres.get("não prescrita", 0)), ("Sem dados no RSPE", pres.get("sem dados", 0))],
                   W3, st, "assistidos", cores=cor_p, ordenar=False, abaixo=True),
            _rosca("Pretensão punitiva", [("Aparente", ret.get("Aparente", 0)), ("Não configurada", ret.get("Não configurada", 0)),
                                          ("Sem dados no RSPE", ret.get("Sem dados no RSPE", 0))], W3, st, "assistidos", cores=cor_p, ordenar=False, abaixo=True),
            _rosca("Extinção da pena", [("Extinção cabível", E["ext_cabivel"]), ("Até 60 dias ou a verificar", E["ext_verificar"]),
                                        ("Já extinta (RSPE)", E["ext_registrada"]), ("Em cumprimento ou sem previsão", demais)],
                   W3, st, "assistidos", ordenar=False, abaixo=True,
                   cores={"Extinção cabível": "#e34948", "Até 60 dias ou a verificar": "#eda100", "Já extinta (RSPE)": "#2a78d6",
                          "Em cumprimento ou sem previsão": "#1baf7a"})]
    t3 = Table([trio], colWidths=[W / 3.0] * 3)
    t3.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 8)]))
    el.append(t3)
    el.append(Spacer(1, 6))
    tb = [["Prescrição e extinção", "Assistidos", "% da base"],
          ["Prescrição da pretensão executória aparente", str(pres.get("aparente", 0)), pct(pres.get("aparente", 0))],
          ["Prescrição da pretensão executória iminente ou a verificar", str(pres.get("iminente / a verificar", 0)), pct(pres.get("iminente / a verificar", 0))],
          ["Prescrição da pretensão punitiva aparente", str(E["presc_punitiva"]), pct(E["presc_punitiva"])],
          ["Extinção pelo cumprimento cabível", str(E["ext_cabivel"]), pct(E["ext_cabivel"])],
          ["Término em até 60 dias ou extinção a verificar", str(E["ext_verificar"]), pct(E["ext_verificar"])],
          ["Extinção já registrada no RSPE", str(E["ext_registrada"]), pct(E["ext_registrada"])],
          ["Término calculado pelo programa (o SEEU não imprime o término)", str(E["term_calc"]), pct(E["term_calc"])]]
    el.append(KeepTogether([_tabela(tb, [W * 0.66, W * 0.17, W * 0.17], st,
                                    cores_linha={1: "vermelho" if pres.get("aparente") else "", 3: "vermelho" if E["presc_punitiva"] else "",
                                                 4: "vermelho" if E["ext_cabivel"] else ""})]))

    # ============================================================ 4. inconsistências
    parte(4, "Inconsistências do cálculo (Auditoria)", "Divergências do RSPE que prejudicam o assistido (alertas) e pontos que dependem de conferência nos autos.")
    el.append(numeros([(E["n_alertas"], "alertas", rs.pl(E["com_alerta"], "assistido", "assistidos")), (E["n_verificar"], "pontos a verificar"),
                       (E["incompletos"], "assistidos com dados incompletos no RSPE")], {0: "vermelho", 1: "amarelo"}))
    el.append(Spacer(1, 6))
    tb = [["Alertas mais frequentes", "Ocorrências"]] + [[k, str(v)] for k, v in E["alertas"].most_common(8)]
    if len(tb) > 1:
        el.append(KeepTogether([_tabela(tb, [W * 0.85, W * 0.15], st)]))
    doc = SimpleDocTemplate(caminho, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=21 * mm, bottomMargin=20 * mm,
                            title="Relatório geral - %s" % nome_base, author="RSPE Base")
    fr = _moldura("Relatório geral", nome_base)
    doc.build(el, onFirstPage=fr, onLaterPages=fr)
    return caminho


def gerar(modelos, pasta, nome_base, individual=True, geral=True, nominal=True, individuais=None, remicao=False):
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
    if remicao:
        try:
            relatorio_remicao(modelos, os.path.join(destino, "Remicao detalhada - %s.pdf" % re.sub(r"[^\w\- ]", "", nome_base)), nome_base, nominal)
        except Exception as e:
            erros.append("remição detalhada: %s" % e)
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


# ---------------------------------------------------------------- remição detalhada
def remicao_por_origem(modelos):
    """Totais da remição pendente por origem (rspe_ficha.remicao_detalhada de cada assistido com ficha)."""
    import rspe_ficha as rf
    ks = [k for k, _r, _p in rf.ORIGENS_REMICAO] + ["lacunas"]
    O = {"dias": {k: 0 for k in ks}, "n": {k: 0 for k in ks}, "itens": {k: 0 for k in ks}, "ass": 0, "total": 0, "com_ficha": 0}
    for m in modelos:
        D = m.get("fd_rem_det")
        if not m.get("ficha_tem") or not D:
            continue
        O["com_ficha"] += 1
        for k in ks:
            if D[k]["itens"]:
                O["n"][k] += 1
                O["itens"][k] += len(D[k]["itens"])
                O["dias"][k] += D[k]["dias"]
        O["ass"] += D["total"] >= 1
        O["total"] += D["total"]
    return O


def relatorio_remicao(modelos, caminho, nome_base, nominal=True):
    """PDF da remição detalhada: de onde vem cada dia a remir (atestado emitido e não lançado, diferença, trabalho sem
    atestado, estudo, leitura), por origem, por unidade prisional em que o trabalho ou o estudo aconteceu (com os assistidos
    de cada unidade, para o ofício) e por assistido - base do pedido de providências."""
    import rspe_ficha as rf
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, CondPageBreak
    st = _estilos()
    C = st["C"]
    PG = landscape(A4)
    W = PG[0] - 32 * mm
    peq = ParagraphStyle("peq", parent=st["cel"], fontSize=7.6, leading=10)
    peqn = ParagraphStyle("peqn", parent=peq, fontName=_FONTE["b"])
    dir_ = ParagraphStyle("dir", parent=peq, alignment=2)
    dirn = ParagraphStyle("dirn", parent=peqn, alignment=2)
    ORI = rf.ORIGENS_REMICAO
    rot = dict((k, r) for k, r, _p in ORI)
    prov = dict((k, p_) for k, _r, p_ in ORI)
    COMO = {"nao_lancado": "dias remidos do próprio atestado", "divergencia": "dias do atestado (sem a fração) menos os da remição lançada",
            "sem_atestado": "estimativa: dias seg.-sáb. do vínculo sem atestado, sem feriados, ÷ 3 (LEP, art. 126, § 1º, II)",
            "estudo": "12 horas de frequência = 1 dia (LEP, art. 126, § 1º, I); horas declaradas ou estimadas",
            "leitura": "4 dias por obra (Res. CNJ 391/2021, art. 5º)", "em_curso": "estimativa, como no trabalho sem atestado"}
    O = remicao_por_origem(modelos)
    com = [m for m in modelos if m.get("ficha_tem") and m.get("fd_rem_det")]
    pend = sorted([m for m in com if m["fd_rem_det"]["total"] >= 1 or any(m["fd_rem_det"][k]["itens"] for k in ("em_curso", "lacunas"))],
                  key=lambda m: rs._sem_acento(m.get("nome") or "").upper())
    el = [Paragraph("Remição detalhada", st["tit"]),
          Paragraph(_t("%s · origem de cada dia a remir, pela ficha disciplinar (SIAPEN) x RSPE · %s com ficha de %s na seleção" % (
              nome_base, rs.pl(O["com_ficha"], "assistido", "assistidos"), len(modelos))), st["sub"]), Spacer(1, 10)]
    nums = [(O["ass"], "assistidos com remição a requerer"), (_num(int(O["total"])), "dias a remir (sem o trabalho em curso)"),
            (_num(int(O["dias"]["nao_lancado"])), "de atestados emitidos sem remição"), (_num(int(O["dias"]["sem_atestado"])), "de trabalho sem atestado (estimativa)"),
            (_num(int(O["dias"]["estudo"])), "de estudo sem remição (≈)")]
    cel = [[Paragraph(_t(str(n)), st["num"]) for n, _ in nums], [Paragraph(_t(r), st["rot"]) for _, r in nums]]
    tb = Table(cel, colWidths=[W / len(nums)] * len(nums))
    tb.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, C(LINE)), ("INNERGRID", (0, 0), (-1, -1), 0.6, C(LINE)),
                            ("BACKGROUND", (0, 0), (-1, -1), C(ZEBRA)), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                            ("TOPPADDING", (0, 0), (-1, 0), 7), ("BOTTOMPADDING", (0, 1), (-1, 1), 7), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    el.append(tb)

    # 1) por origem
    el.append(Paragraph("1. Por origem", st["h2"]))
    dados = [["Origem", "Assistidos", "Itens", "Dias a remir", "Como foi calculado", "Providência"]]
    for k, r, p_ in ORI:
        dados.append([Paragraph(_t(r), peqn), Paragraph(str(O["n"][k]), dir_), Paragraph(str(O["itens"][k]), dir_),
                      Paragraph(_t(_num(int(O["dias"][k])) + (" (fora do total)" if k == "em_curso" else "")), dirn), Paragraph(_t(COMO[k]), peq), Paragraph(_t(p_), peq)])
    dados.append([Paragraph("Lacuna entre atestados", peqn), Paragraph(str(O["n"]["lacunas"]), dir_), Paragraph(str(O["itens"]["lacunas"]), dir_),
                  Paragraph("—", dir_), Paragraph("período sem vínculo comprovado: não há como estimar dias", peq), Paragraph("verificar com a unidade se houve trabalho", peq)])
    dados.append([Paragraph("Total", peqn), Paragraph(str(O["ass"]), dirn), "", Paragraph(_t(_num(int(O["total"]))), dirn), "", ""])
    el.append(_tabela(dados, [58 * mm, 20 * mm, 14 * mm, 26 * mm, 80 * mm, W - 198 * mm], st, zebra=True))
    el.append(Spacer(1, 4))
    el.append(Paragraph(_t("Atestados: dias exatos do documento. Trabalho sem atestado, em curso e estudo sem horas declaradas: estimativa do programa "
                           "(o número exato sai do atestado ou da certidão a expedir). Vínculos simultâneos não contam o mesmo dia duas vezes. "
                           "Remição já lançada no RSPE e atestados anteriores a esta execução ficam de fora."), st["mut"]))

    # 2) por unidade prisional: onde o trabalho, o estudo ou a leitura aconteceu (entradas em unidade penal da ficha)
    ks = [k for k, _r, _p in ORI if k != "em_curso"]
    por_un = {}
    for m in com:
        D = m["fd_rem_det"]
        for k in ks:
            for u, v in D[k]["por_un"].items():
                if v:
                    x = por_un.setdefault(u, {"ass": set(), "total": 0, **{kk: 0 for kk in ks}})
                    x["ass"].add(m.get("id"))
                    x[k] += v
                    x["total"] += v
    if por_un:
        el.append(CondPageBreak(40 * mm))
        el.append(Paragraph("2. Por unidade prisional (onde o trabalho, o estudo ou a leitura aconteceu)", st["h2"]))
        el.append(Paragraph(_t("A unidade de cada período vem das entradas em unidade penal registradas na ficha; o período que atravessa uma "
                               "transferência é dividido entre as unidades. Atestado: unidade em que o período atestado terminou. "
                               "\"Unidade não identificada\": período anterior à primeira entrada registrada na ficha."), st["mut"]))
        el.append(Spacer(1, 4))
        cab = ["Unidade", "Assistidos", "Atestado sem remição", "Diferença", "Trabalho sem atestado", "Estudo", "Leitura", "Total"]
        dados = [cab]
        for u, x in sorted(por_un.items(), key=lambda kv: (kv[0] == rf.SEM_UNIDADE, -kv[1]["total"])):
            dados.append([Paragraph(_t(u), peqn), Paragraph(str(len(x["ass"])), dir_)] + [Paragraph(_t(_num(int(x[k]))), dir_) for k in ks] +
                         [Paragraph(_t(_num(int(x["total"]))), dirn)])
        lw = (W - 80 * mm - 20 * mm) / (len(ks) + 1)
        el.append(_tabela(dados, [80 * mm, 20 * mm] + [lw] * (len(ks) + 1), st))

    # 3) por unidade: assistidos e itens (base do ofício a cada unidade)
    if nominal and por_un:
        el.append(CondPageBreak(60 * mm))
        el.append(Paragraph("3. Por unidade prisional: assistidos e o que pedir a cada uma", st["h2"]))
        larg3 = [52 * mm, 44 * mm, 40 * mm, 46 * mm, 44 * mm, 16 * mm, W - 242 * mm]
        for u, x in sorted(por_un.items(), key=lambda kv: (kv[0] == rf.SEM_UNIDADE, -kv[1]["total"])):
            linhas = []
            for m in sorted(com, key=lambda m: rs._sem_acento(m.get("nome") or "").upper()):
                D = m["fd_rem_det"]
                for k, r_, _p in ORI:
                    if k == "em_curso":
                        continue
                    for i in D[k]["itens"]:
                        if i["unidade"] == u and i["dias"]:
                            linhas.append((m, r_, i))
            if not linhas:
                continue
            tit = Paragraph("<b>%s</b> · %s · %s" % (_t(u), rs.pl(len(x["ass"]), "assistido", "assistidos"), _t("%s dias a remir" % _num(int(x["total"])))),
                            ParagraphStyle("pu", parent=st["cel"], fontSize=8.8, leading=12, textColor=C(NAVY)))
            dados = [["Assistido", "Nº da execução", "Origem", "Referência", "Período", "Dias", "Pedir"]]
            ant = None
            for m, r_, i in linhas:
                novo = m.get("id") != ant
                ant = m.get("id")
                dados.append([Paragraph(_t(m.get("nome") or ""), peqn) if novo else "", Paragraph(_t(m.get("proc") or m.get("id") or ""), peq) if novo else "",
                              Paragraph(_t(r_), peq), Paragraph(_t(i["ref"] + ((" · " + i["data"]) if i.get("data") else "")), peq), Paragraph(_t(i["per"]), peq),
                              Paragraph(_t(("≈ " if i.get("estimado") else "") + _num(i["dias"])), dir_),
                              Paragraph(_t({"sem_atestado": "atestado de trabalho", "estudo": "certidão de frequência", "leitura": "conferir homologação",
                                            "nao_lancado": "verificar peticionamento", "divergencia": "requerer a diferença"}.get(
                                  next(k for k, rr, _pp in ORI if rr == r_), "")), peq)])
            el.append(KeepTogether([Spacer(1, 8), tit, Spacer(1, 3), _tabela(dados[:5], larg3, st, zebra=False)]))
            if len(dados) > 5:
                el.append(_tabela([dados[0]] + dados[5:], larg3, st, zebra=False))

    # 4) por assistido: a conferência ficha x RSPE (o que já está no processo e o que não está) e o que falta remir
    conf = sorted([m for m in com if (m.get("fd_conc") or {}).get("tabela") or m["fd_rem_det"]["total"] >= 1
                   or any(m["fd_rem_det"][k]["itens"] for k in ("em_curso", "lacunas"))],
                  key=lambda m: rs._sem_acento(m.get("nome") or "").upper())
    if nominal and conf:
        el.append(CondPageBreak(60 * mm))
        el.append(Paragraph("4. Por assistido (ordem alfabética): conferência ficha x RSPE e o que falta remir", st["h2"]))
        el.append(Paragraph(_t("Primeiro quadro: cada atestado da ficha e a remição correspondente no RSPE. Verde = já está no processo (remição "
                               "lançada no RSPE); vermelho = atestado emitido sem remição no RSPE; amarelo = lançado com dias diferentes; azul = remição "
                               "no RSPE sem atestado registrado na ficha. Segundo quadro: o que ainda falta remir, por origem e unidade. "
                               "\"≈\" = estimativa do programa."), st["mut"]))
        larg = [40 * mm, 48 * mm, 40 * mm, 44 * mm, 40 * mm, 16 * mm, W - 228 * mm]
        largc = [40 * mm, 52 * mm, 48 * mm, 20 * mm, 22 * mm, 38 * mm, W - 220 * mm]
        cor_st = {"CONCILIADO": "verde", "NAO_LANCADO": "vermelho", "DIVERGENCIA": "amarelo"}
        rot_st = {"CONCILIADO": "No processo", "NAO_LANCADO": "Não está no processo", "DIVERGENCIA": "No processo, dias diferentes"}
        for m in conf:
            D = m["fd_rem_det"]
            T = (m.get("fd_conc") or {}).get("tabela") or []
            un = _rotulo_unidade((m.get("ficha") or {}).get("unidade") or "") or "unidade não informada"
            tit = Paragraph("<b>%s</b> · %s · hoje em %s · <b>%s %s a remir</b>%s" % (
                _t(m.get("nome") or ""), _t(m.get("proc") or m.get("id") or ""), _t(un), _num(D["total"]), "dia" if D["total"] == 1 else "dias",
                _t(" (+ ≈ %s do trabalho em curso)" % rs.pl(int(D["em_curso"]["dias"]), "dia", "dias")) if D["em_curso"]["dias"] else ""),
                ParagraphStyle("pt", parent=st["cel"], fontSize=8.4, leading=11.5))
            blocos = [Spacer(1, 9), tit]
            if T:
                def _n(x):
                    try:
                        return float(str(x).replace(".", "").replace(",", "."))
                    except Exception:
                        return 0.0
                fic = sum(_n(t["rem"]) for t in T if t["status"] != "ANTERIOR" and not t["atestado"].startswith("Atestado não registrado"))
                dentro = sum(_n(t["rem"]) for t in T if t["status"] in ("CONCILIADO", "DIVERGENCIA") and not t["atestado"].startswith("Atestado não registrado"))
                fora = sum(_n(t["rem"]) for t in T if t["status"] == "NAO_LANCADO")
                nr = [t for t in T if t["atestado"].startswith("Atestado não registrado")]
                n_v = sum(1 for t in T if t["status"] == "NAO_LANCADO")
                n_r = sum(1 for t in T if t["status"] in ("CONCILIADO", "DIVERGENCIA") and t not in nr)
                res_ = Paragraph("%s · %s · %s%s · RSPE: %s" % (
                    _t("Ficha: %s em atestados desta execução" % ("%s dias remidos" % _num(fic))),
                    '<font color="%s"><b>%s</b></font>' % (COR["verde"][1], _t("no processo: %s dias (%s)" % (_num(dentro), rs.pl(n_r, "atestado", "atestados")))),
                    '<font color="%s"><b>%s</b></font>' % (COR["vermelho"][1], _t("fora do processo: %s dias (%s)" % (_num(fora), rs.pl(n_v, "atestado", "atestados")))),
                    (' · <font color="%s"><b>%s</b></font>' % (COR["azul"][1], _t("no RSPE sem atestado na ficha: %s dias (%s)" % (
                        _num(sum(_n(t["rem"]) for t in nr)), rs.pl(len(nr), "remição", "remições"))))) if nr else "",
                    _t((m.get("remidos") or "—"))), ParagraphStyle("rs", parent=st["cel"], fontSize=7.9, leading=10.5))
                dc = [["Atestado", "Unidade", "Período", "Dias trab.", "Remidos (ficha)", "Remição no RSPE", "Situação"]]
                cores = {}
                for t in T:
                    fora_ficha = t["atestado"].startswith("Atestado não registrado")
                    cor = "azul" if fora_ficha else cor_st.get(t["status"], "cinza")
                    sit = "No processo, sem atestado na ficha" if fora_ficha else rot_st.get(t["status"], t.get("rot") or "")
                    dc.append([Paragraph(_t(t["atestado"] + ((" · " + t["emissao"]) if t.get("emissao") else "")), peq),
                               Paragraph(_t(t.get("unidade") or "—"), peq),
                               Paragraph(_t("; ".join(x["per"] for x in t["segs"]) or "—"), peq),
                               Paragraph(_t(str(t["trab"] or "—")), dir_), Paragraph(_t(t["rem"]), dir_),
                               Paragraph(_t(("%s · decisão %s" % (t["rspe"], t["decisao"])) if t["rspe"] not in ("—", "") else "—"), peq),
                               _pilula(sit, cor, st)])
                    cores[len(dc) - 1] = cor
                blocos += [Spacer(1, 2), res_, Spacer(1, 3), _tabela(dc[:5], largc, st, zebra=False, cores_linha={k: v for k, v in cores.items() if k < 5})]
                resto_c = [dc[0]] + dc[5:]
                cores_r = {k - 4: v for k, v in cores.items() if k >= 5}
            else:
                blocos += [Spacer(1, 2), Paragraph(_t("Nenhum atestado de trabalho desta execução na ficha."), st["mut"])]
                resto_c, cores_r = None, {}
            el.append(KeepTogether(blocos))
            if resto_c and len(resto_c) > 1:
                el.append(_tabela(resto_c, largc, st, zebra=False, cores_linha=cores_r))
            dados = [["Falta remir: origem", "Unidade", "Referência", "Período", "Base do cálculo", "Dias", "Providência"]]
            for k, r, p_ in ORI + [("lacunas", "Lacuna entre atestados", "verificar com a unidade se houve trabalho")]:
                its = D[k]["itens"]
                for n_, i in enumerate(its):
                    dados.append([Paragraph(_t(r), peqn) if n_ == 0 else "", Paragraph(_t(i.get("unidade") or "—"), peq),
                                  Paragraph(_t(i["ref"] + ((" · emitido em %s" % i["data"]) if i.get("data") and k in ("nao_lancado", "divergencia") else "")), peq),
                                  Paragraph(_t(i["per"]), peq), Paragraph(_t(i.get("base") or "—"), peq),
                                  Paragraph(_t(("≈ " if i.get("estimado") else "") + _num(i["dias"]) if i["dias"] else "—"), dir_),
                                  Paragraph(_t(p_ if n_ == 0 else ""), peq)])
                if len(its) > 1 and D[k]["dias"] and k != "lacunas":
                    dados.append(["", "", "", "", Paragraph(_t("subtotal" + (" (sem contar duas vezes os dias simultâneos)" if D[k].get("sobreposicao") else "")), peq),
                                  Paragraph(_t(("≈ " if k in ("sem_atestado", "em_curso", "estudo") else "") + _num(D[k]["dias"])), dirn), ""])
            if len(dados) > 1:
                el.append(Spacer(1, 4))
                el.append(_tabela(dados, larg, st, zebra=False))
            else:
                el.append(Paragraph(_t("Nada a remir além do que já está no processo."), st["mut"]))
    doc = SimpleDocTemplate(caminho, pagesize=PG, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=21 * mm, bottomMargin=20 * mm,
                            title="Remição detalhada", author="RSPE Base")
    fr = _moldura("Remição detalhada", nome_base,
                           "Triagem pela ficha disciplinar e pelo RSPE: atestados com dias exatos; trabalho sem atestado e estudo, estimativa. Conferir nos autos (SEEU) antes do pedido.", pagina=PG)
    doc.build(el, onFirstPage=fr, onLaterPages=fr)
    return caminho


# ---------------------------------------------------------------- relatório de providências
TIPOS_PROV = [("Pedido nos autos", "#00602C", "pedidos nos autos"), ("Ofício à unidade prisional", "#0BA5EC", "ofícios à unidade prisional"),
              ("Outra providência", "#98A2B3", "outras providências")]
_MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def _graf_ranking(linhas, largura, f):
    """Barras horizontais: benefícios com mais providências, cada barra dividida pelo tipo de providência."""
    from reportlab.graphics.shapes import Drawing, Rect, String, Line
    from reportlab.lib import colors
    C = colors.HexColor
    ass = {}
    for L in linhas:
        ass.setdefault(L.get("assunto", ""), []).append(L)
    orden = sorted(ass.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    rotw, barh, gap = 150, 14, 9
    h = len(orden) * (barh + gap) + 34
    d = Drawing(largura, h)
    mx = max(len(v) for _, v in orden) if orden else 1
    area = largura - rotw - 40
    y = h - 8 - barh
    for nome, ls in orden:
        d.add(String(rotw - 8, y + 3.5, _t(nome).replace("&amp;", "&"), fontName=f["n"], fontSize=8.4, fillColor=C(TX), textAnchor="end"))
        x = rotw
        for t, cor, _ in TIPOS_PROV:
            n = sum(1 for L in ls if L.get("tipo") == t)
            if n:
                w = area * n / mx
                d.add(Rect(x, y, w, barh, fillColor=C(cor), strokeColor=None))
                if w > 14:
                    d.add(String(x + w / 2, y + 3.8, str(n), fontName=f["b"], fontSize=7.6, fillColor=colors.white, textAnchor="middle"))
                x += w
        d.add(String(x + 5, y + 3.5, str(len(ls)), fontName=f["b"], fontSize=8.4, fillColor=C(NAVY)))
        y -= barh + gap
    lx = rotw
    for t, cor, rot in TIPOS_PROV:
        d.add(Rect(lx, 4, 8, 8, fillColor=C(cor), strokeColor=None))
        d.add(String(lx + 11, 5, rot, fontName=f["n"], fontSize=7.6, fillColor=C(TX2)))
        from reportlab.pdfbase.pdfmetrics import stringWidth
        lx += 11 + stringWidth(rot, f["n"], 7.6) + 16
    return d


def _graf_meses(todas, mes_sel, largura, f):
    """Colunas: providências por mês (até 12 meses, terminando no mais recente), com o mês do relatório destacado."""
    from reportlab.graphics.shapes import Drawing, Rect, String, Line
    from reportlab.lib import colors
    C = colors.HexColor
    cont = {}
    for L in todas:
        m = (L.get("data") or "")[3:]
        if len(m) == 7:
            cont[m] = cont.get(m, 0) + 1
    if not cont:
        return None
    chave = lambda m: (int(m[3:]), int(m[:2]))
    ult = max(cont, key=chave)
    a, mm_ = chave(ult)
    meses = []
    for _ in range(12):
        meses.append("%02d/%d" % (mm_, a))
        mm_ -= 1
        if mm_ == 0:
            mm_, a = 12, a - 1
    meses = [m for m in reversed(meses) if chave(m) >= chave(min(cont, key=chave))] or [ult]
    h = 120
    d = Drawing(largura, h)
    base_y, topo = 22, h - 16
    mx = max(cont.get(m, 0) for m in meses) or 1
    passo = largura / len(meses)
    bw = min(34, passo * 0.62)
    d.add(Line(0, base_y, largura, base_y, strokeColor=C(LINE), strokeWidth=0.8))
    for i, m in enumerate(meses):
        n = cont.get(m, 0)
        hh = (topo - base_y - 10) * n / mx
        x = i * passo + (passo - bw) / 2
        cor = PRI if m == mes_sel else "#B7D7C2"
        if n:
            d.add(Rect(x, base_y, bw, hh, fillColor=C(cor), strokeColor=None))
            d.add(String(x + bw / 2, base_y + hh + 3, str(n), fontName=f["b"], fontSize=7.6, fillColor=C(NAVY), textAnchor="middle"))
        d.add(String(x + bw / 2, base_y - 10, "%s/%s" % (_MESES[int(m[:2]) - 1], m[5:]), fontName=f["n"], fontSize=7, fillColor=C(TX2), textAnchor="middle"))
    return d


def relatorio_providencias(linhas, todas, mes_sel, caminho, titulo, nome_base):
    """PDF do relatório de providências: totais, gráfico dos benefícios com mais providências, providências por mês e a lista."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    st = _estilos()
    f = _fontes()
    C = st["C"]
    W = A4[0] - 32 * mm
    el = [Paragraph(_t(titulo), st["tit"]),
          Paragraph(_t("%s · pedidos e ofícios marcados na coluna Pedido, pela data da providência · base inteira, sem separar por pessoa" % nome_base), st["sub"]),
          Spacer(1, 10)]
    # totais
    nums = [(len(linhas), "providências")] + [(sum(1 for L in linhas if L.get("tipo") == t), rot) for t, _, rot in TIPOS_PROV] + \
           [(len({L.get("proc") for L in linhas}), "assistidos")]
    cel = [[Paragraph(str(n), st["num"]) for n, _ in nums], [Paragraph(_t(r), st["rot"]) for _, r in nums]]
    tb = Table(cel, colWidths=[W / len(nums)] * len(nums))
    tb.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, C(LINE)), ("INNERGRID", (0, 0), (-1, -1), 0.6, C(LINE)),
                            ("BACKGROUND", (0, 0), (-1, -1), C(ZEBRA)), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                            ("TOPPADDING", (0, 0), (-1, 0), 7), ("BOTTOMPADDING", (0, 1), (-1, 1), 7), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    el += [tb]
    if linhas:
        el += [Paragraph("Benefícios com mais providências", st["h2"]), _graf_ranking(linhas, W, f)]
    gm = _graf_meses(todas, mes_sel, W, f)
    if gm is not None:
        el += [Paragraph("Providências por mês", st["h2"]), gm]
    el += [Paragraph("Lista", st["h2"])]
    if linhas:
        from reportlab.lib.styles import ParagraphStyle
        peq = ParagraphStyle("peq", parent=st["cel"], fontSize=7.4, leading=10)
        dados = [["Data", "Assistido", "Nº da execução", "Benefício", "Providência", "Observação"]]
        for L in linhas:
            dados.append([Paragraph(_t(L.get("data", "")), peq), L.get("nome", ""), Paragraph(_t(L.get("proc", "")), peq),
                          L.get("assunto", ""), L.get("tipo", ""), L.get("obs", "")])
        el.append(_tabela(dados, [21 * mm, 32 * mm, 46 * mm, 25 * mm, 25 * mm, W - 149 * mm], st))
    else:
        el.append(Paragraph("Nenhuma providência no período.", st["mut"]))
    doc = SimpleDocTemplate(caminho, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=21 * mm, bottomMargin=20 * mm,
                            title=titulo, author="RSPE Base")
    fr = _moldura("Relatório de providências", nome_base, rodape="Providências registradas no RSPE Base (coluna Pedido). Conferir nos autos e no SAP.")
    doc.build(el, onFirstPage=fr, onLaterPages=fr)
    return caminho



def relatorio_falhas(d, caminho, nome_base):
    """PDF das falhas da importação: o que não entrou, o que não foi lido e o que não pôde ser analisado, com a causa."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    st = _estilos()
    W = A4[0] - 32 * mm
    el = [Paragraph(_t("Falhas da importação"), st["tit"]),
          Paragraph(_t("%s · lote importado em %s · %s lidos" % (nome_base, d.get("quando", ""), rs.pl(d.get("arquivos", 0), "arquivo", "arquivos"))), st["sub"]),
          Spacer(1, 8)]
    n_pes = sum(len(p["itens"]) for p in d["pessoas"])
    faltam = d.get("faltam") or []
    el.append(_tabela([["Arquivos não importados", "Assistidos com dado não lido", "Ignorados", "Falhas na análise"],
                       [str(len(d["erros"])), str(len(faltam)), str(len(d["ignorados"])), str(n_pes)]],
                      [W / 4] * 4, st, zebra=False))
    if faltam:
        cont = Counter(c for x in faltam for c in x["campos"])
        el.append(Spacer(1, 4))
        el.append(Paragraph(_t("Dados não lidos, por campo: " + " · ".join("%s %d" % (k, v) for k, v in cont.most_common())), st["mut"]))

    def causa_arquivo(msg):
        u = msg.upper()
        if "NÃO PARECE UM RSPE" in u:
            return "O PDF não tem o cabeçalho do RSPE do SEEU nem o da Ficha Disciplinar do SIAPEN (outro documento, digitalização ou PDF protegido)."
        if "NÚMERO DA EXECUÇÃO" in u:
            return "A 1ª página falta ou o número do processo de execução está ilegível: gerar o RSPE de novo no SEEU."
        if "PASSWORD" in u or "ENCRYPT" in u:
            return "PDF protegido por senha."
        if "EOF" in u or "PDFSYNTAX" in u or "STARTXREF" in u or "ROOT OBJECT" in u or "REALLY A PDF" in u:
            return "Arquivo corrompido ou baixado pela metade: baixar de novo."
        return "Erro na leitura do arquivo: enviar o PDF para análise."

    el.append(Paragraph("1. Arquivos não importados", st["h2"]))
    if d["erros"]:
        dados = [["Arquivo", "Mensagem", "Causa provável"]]
        for e in d["erros"]:
            arq, _, msg = e.partition(": ")
            dados.append([arq, msg, causa_arquivo(msg)])
        el.append(_tabela(dados, [50 * mm, 60 * mm, W - 110 * mm], st))
    else:
        el.append(Paragraph("Nenhum.", st["mut"]))
    el.append(Paragraph("2. Dados não lidos do RSPE", st["h2"]))
    if faltam:
        dados = [["Assistido", "Arquivo", "Campos não lidos"]]
        for x in sorted(faltam, key=lambda x: x["nome"]):
            dados.append([Paragraph(_t(x["nome"]) + "<br/>" + _t(x["proc"]), st["cel"]), x.get("arquivo") or "—", ", ".join(x["campos"])])
        el.append(_tabela(dados, [62 * mm, 55 * mm, W - 117 * mm], st))
        el.append(Spacer(1, 4))
        el.append(Paragraph(_t("Causa: o campo não está onde o layout do RSPE o traz - em branco no SEEU, página faltando ou texto quebrado na "
                               "extração. Não entram aqui os casos em que o SEEU deixa o campo em branco de propósito (pena não iniciada, pena "
                               "interrompida por fuga ou evasão, execução extinta ou arquivada): esses têm aviso próprio na Auditoria. Cada assistido "
                               "da lista tem o alerta \u201cFaltam dados\u201d na Auditoria, onde o dado pode ser informado."), st["mut"]))
    else:
        el.append(Paragraph("Nenhum.", st["mut"]))
    if d["ignorados"]:
        el.append(Paragraph("3. Arquivos ignorados", st["h2"]))
        dados = [["Arquivo", "Motivo"]] + [list(e.partition(": ")[::2]) for e in d["ignorados"]]
        el.append(_tabela(dados, [60 * mm, W - 60 * mm], st))
    el.append(Paragraph("%d. Falhas na análise dos assistidos do lote" % (4 if d["ignorados"] else 3), st["h2"]))  # erro do programa, não dado faltando
    if d["pessoas"]:
        dados = [["Assistido", "Falha", "Causa / detalhe"]]
        for p in d["pessoas"]:
            for tit, det in p["itens"]:
                dados.append([Paragraph(_t(p["nome"]) + "<br/>" + _t(p["proc"]), st["cel"]), tit, det])
        el.append(_tabela(dados, [45 * mm, 55 * mm, W - 100 * mm], st))
    else:
        el.append(Paragraph("Nenhuma.", st["mut"]))
    doc = SimpleDocTemplate(caminho, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=21 * mm, bottomMargin=20 * mm,
                            title="Falhas da importação", author="RSPE Base")
    fr = _moldura("Falhas da importação", nome_base, rodape="Falhas registradas na importação do lote. Enviar este PDF com os arquivos citados para a correção da leitura.")
    doc.build(el, onFirstPage=fr, onLaterPages=fr)
