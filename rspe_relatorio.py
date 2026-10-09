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

NAVY = "#0B3B22"   # títulos: verde-escuro do selo
PRI = "#00602C"
TX = "#262B28"     # grafite
TX2 = "#5F6662"
TX3 = "#7B827E"
LINE = "#D5DAD6"
ZEBRA = "#FAFBFA"
COR = {"vermelho": ("#F6E4E3", "#8E2424"), "laranja": ("#F7EADB", "#8A4A12"), "amarelo": ("#F5EDDA", "#7A5410"),
       "vencido": ("#F6E4E3", "#8E2424"), "verde": ("#E3EFE7", "#1F5B39"), "cinza": ("#ECEEEB", "#5F6662"),
       "azul": ("#E6ECF2", "#334E68"), "": ("#FFFFFF", TX)}
AVISO = ("Triagem automatizada a partir do RSPE (SEEU) e da ficha disciplinar (SIAPEN). Não substitui o Atestado de Pena. "
         "Progressão, livramento e término são as datas do SEEU; indulto, comutação, prescrição e remição a requerer são "
         "cálculos do programa e devem ser conferidos.")

# ---------------------------------------------------------------- fontes (acentos e símbolos)
_FONTE = {"n": "Helvetica", "b": "Helvetica-Bold", "sb": "Helvetica-Bold", "serif": "Times-Bold", "serifb": "Times-Bold",
          "marca": "Times-Bold", "unicode": False, "sem_alerta": False}


def _pasta_fontes():
    import sys
    return os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "fontes")


def _fontes():
    if _FONTE.get("ok"):
        return _FONTE
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    pf = _pasta_fontes()
    arqs = {"n": "SourceSans3-Regular.ttf", "sb": "SourceSans3-SemiBold.ttf", "b": "SourceSans3-Bold.ttf",
            "serif": "SourceSerif4-SemiBold.ttf", "serifb": "SourceSerif4-Bold.ttf", "marca": "Cinzel-Bold.ttf"}
    try:
        # identidade dos relatórios: texto em Source Sans, títulos em Source Serif, a marca em Cinzel (fontes do programa)
        for k, arq in arqs.items():
            pdfmetrics.registerFont(TTFont("Apto-" + k, os.path.join(pf, arq)))
        _FONTE.update({k: "Apto-" + k for k in arqs}, unicode=True, sem_alerta=True)  # a Source Sans não tem o "⚠"
    except Exception:
        pares = [(r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
                 ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
                 ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf")]
        for n, b in pares:
            if os.path.exists(n) and os.path.exists(b):
                try:
                    pdfmetrics.registerFont(TTFont("RelN", n))
                    pdfmetrics.registerFont(TTFont("RelB", b))
                    _FONTE.update(n="RelN", b="RelB", sb="RelB", serif="RelB", serifb="RelB", marca="RelB", unicode=True)
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


def _dias(x):
    """Dias inteiros, arredondados (não truncados): 9.165,99 -> "9.166"."""
    return _num(round(float(x or 0)))


def _arred_coluna(vals, alvo=None):
    """Arredonda uma coluna de dias mantendo a soma igual ao total arredondado (maiores restos): a tabela fecha. Com alvo, a
    soma fica igual a ele (o total já exibido em outro quadro do mesmo PDF)."""
    alvo = round(sum(vals)) if alvo is None else int(alvo)
    base = [int(v) for v in vals]
    resto = sorted(range(len(vals)), key=lambda i: -(vals[i] - base[i]))
    for i in resto[:max(0, alvo - sum(base))]:
        base[i] += 1
    for i in reversed(resto):  # alvo abaixo da soma truncada (diferença de centésimos): tira dos menores restos
        if sum(base) <= alvo:
            break
        if base[i] > 0:
            base[i] -= 1
    return base


def _t(txt):
    """Texto seguro para a fonte e para o mini-HTML do Paragraph."""
    s = str(txt if txt is not None else "")
    s = rv.re.sub(r"(-?)\b(\d+)a(\d+)m(\d+)d\b", lambda m: rs.pena_extenso("%sa%sm%sd" % (m.group(2), m.group(3), m.group(4))), s)
    if _FONTE.get("sem_alerta"):
        s = s.replace("⚠", "!")
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
    base = ParagraphStyle("base", fontName=f["n"], fontSize=8.8, leading=12.2, textColor=C(TX))
    return {
        "C": C,
        "tit": ParagraphStyle("tit", parent=base, fontName=f["serifb"], fontSize=18, leading=22, textColor=C(NAVY)),
        "sub": ParagraphStyle("sub", parent=base, fontSize=9, leading=12.5, textColor=C(TX2)),
        "h2": ParagraphStyle("h2", parent=base, fontName=f["serif"], fontSize=11, leading=14.5, textColor=C(NAVY), spaceBefore=14, spaceAfter=6),
        "cel": ParagraphStyle("cel", parent=base, fontSize=8.2, leading=11),
        "neg": ParagraphStyle("neg", parent=base, fontName=f["b"], fontSize=8.2, leading=11),
        "cab": ParagraphStyle("cab", parent=base, fontName=f["sb"], fontSize=7.4, leading=9.2, textColor=C(TX2)),
        "mut": ParagraphStyle("mut", parent=base, fontSize=7.8, leading=10.5, textColor=C(TX3)),
        "rot": ParagraphStyle("rot", parent=base, fontSize=7.6, leading=9.4, textColor=C(TX)),
        "val": ParagraphStyle("val", parent=base, fontName=f["b"], fontSize=10, leading=13),
        "num": ParagraphStyle("num", parent=base, fontName=f["serif"], fontSize=20, leading=23, textColor=C(TX)),
        "p": base,
    }


def _selo(canvas, x, y, lado):
    """Selo do APTO no cabeçalho dos PDFs (apto_selo.png, junto do programa ou do .exe)."""
    import sys
    p = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "apto_selo.png")
    if not os.path.exists(p):
        p = os.path.join(os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)), "apto_selo.png")
    if os.path.exists(p):
        canvas.drawImage(p, x, y, lado, lado, mask="auto")


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
        # cabeçalho: selo, APTO (fonte da marca) e o título; à direita a base e a emissão; filete verde
        _selo(canvas, ML, H - 14.6 * mm, 9.6 * mm)
        canvas.setFillColor(C(PRI))
        canvas.setFont(f["marca"], 11)
        x = ML + 12 * mm
        canvas.saveState()
        to = canvas.beginText(x, H - 11 * mm)
        to.setFont(f["marca"], 11)
        to.setCharSpace(1.6)
        to.textOut("APTO")
        canvas.drawText(to)
        canvas.restoreState()
        x += canvas.stringWidth("APTO", f["marca"], 11) + 4 * 1.6 + 3.2 * mm
        canvas.setFont(f["n"], 8.4)
        canvas.setFillColor(C(TX2))
        canvas.drawString(x, H - 11 * mm, titulo)
        canvas.setFont(f["n"], 7.6)
        canvas.drawRightString(W - ML, H - 9.6 * mm, "Base %s" % nome_base)
        canvas.drawRightString(W - ML, H - 12.8 * mm, "emitido em %s" % gerado)
        canvas.setStrokeColor(C(PRI))
        canvas.setLineWidth(1.1)
        canvas.line(ML, H - 15.8 * mm, W - ML, H - 15.8 * mm)
        # rodapé: filete, aviso em até 3 linhas; "página X de Y" fica com o _CanvasNumerado
        canvas.setStrokeColor(C(LINE))
        canvas.setLineWidth(0.5)
        canvas.line(ML, 14 * mm, W - ML, 14 * mm)
        canvas.setFillColor(C(TX3))
        canvas.setFont(f["n"], 6.6)
        palavras, linhas, atual = rodape.split(), [], ""
        for p in palavras:
            if canvas.stringWidth(atual + " " + p, f["n"], 6.6) > (W - 2 * ML - 28 * mm):
                linhas.append(atual)
                atual = p
            else:
                atual = (atual + " " + p).strip()
        linhas.append(atual)
        for i, l in enumerate(linhas[:3]):
            canvas.drawString(ML, 10.5 * mm - i * 3 * mm, l if f["unicode"] else l.replace("≈", "~"))
        canvas.restoreState()
    return desenhar


def _moldura_capa(rodape=AVISO):
    """Página de capa: só o aviso no rodapé, sem o cabeçalho."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm

    def desenhar(canvas, doc):
        f = _fontes()
        W = A4[0]
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor(LINE))
        canvas.setLineWidth(0.5)
        canvas.line(16 * mm, 14 * mm, W - 16 * mm, 14 * mm)
        canvas.setFont(f["n"], 6.6)
        canvas.setFillColor(colors.HexColor(TX3))
        canvas.drawString(16 * mm, 10.5 * mm, "Triagem automatizada a partir do RSPE (SEEU) e da ficha disciplinar (SIAPEN). Não substitui o Atestado de Pena.")
        canvas.restoreState()
    return desenhar


def _capa(titulo, nome_base, linhas, W, st):
    """Capa: selo, APTO, nome por extenso, filete, título, base e dados do lote; a página seguinte começa o corpo."""
    import sys
    from reportlab.platypus import Spacer, Paragraph, Image, PageBreak, Flowable
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    f = _fontes()
    C = st["C"]

    class _Marca(Flowable):
        def __init__(self, larg):
            Flowable.__init__(self)
            self.width, self.height = larg, 16 * mm

        def draw(self):
            to = self.canv.beginText()
            to.setFont(f["marca"], 34)
            to.setCharSpace(9)
            larg = self.canv.stringWidth("APTO", f["marca"], 34) + 3 * 9
            to.setTextOrigin((self.width - larg) / 2.0, 3 * mm)
            to.setFillColor(C(PRI))
            to.textOut("APTO")
            self.canv.saveState()
            self.canv.drawText(to)
            self.canv.restoreState()

    class _Filete(Flowable):
        def __init__(self, larg):
            Flowable.__init__(self)
            self.width, self.height = larg, 2

        def draw(self):
            self.canv.setStrokeColor(C(PRI))
            self.canv.setLineWidth(1.2)
            self.canv.line(self.width / 2.0 - 12 * mm, 1, self.width / 2.0 + 12 * mm, 1)
    centro = lambda nome, **k: ParagraphStyle(nome, parent=st["p"], alignment=1, **k)
    el = [Spacer(1, 42 * mm)]
    p = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "apto_selo.png")
    if os.path.exists(p):
        el.append(Image(p, 40 * mm, 40 * mm))
    el += [Spacer(1, 7 * mm), _Marca(W),
           Paragraph("Auditoria de Prazos e Tempo de Cumprimento Organizada", centro("cs", fontSize=10.5, leading=14, textColor=C(TX2))),
           Spacer(1, 14 * mm), _Filete(W), Spacer(1, 10 * mm),
           Paragraph(_t(titulo), centro("ct", fontName=f["serifb"], fontSize=24, leading=29, textColor=C(NAVY))),
           Paragraph(_t(nome_base), centro("cb", fontName=f["serif"], fontSize=15, leading=20, textColor=C(TX))),
           Spacer(1, 9 * mm)]
    el += [Paragraph(_t(l), centro("cl", fontSize=10, leading=16, textColor=C(TX2))) for l in linhas]
    el.append(PageBreak())
    return el


def _canvas_numerado():
    """Canvas que guarda as páginas e, ao fechar, escreve "página X de Y" no rodapé de cada uma."""
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    class _CanvasNumerado(Canvas):
        def __init__(self, *a, **k):
            Canvas.__init__(self, *a, **k)
            self._paginas = []

        def showPage(self):
            self._paginas.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            n = len(self._paginas)
            f = _fontes()
            for estado in self._paginas:
                self.__dict__.update(estado)
                W = self._pagesize[0]
                self.setFont(f["n"], 7.2)
                self.setFillColor(colors.HexColor(TX3))
                self.drawRightString(W - 16 * mm, 10.5 * mm, "página %d de %d" % (self._pageNumber, n))
                Canvas.showPage(self)
            Canvas.save(self)
    return _CanvasNumerado


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
        est += [("LINEBELOW", (0, 0), (-1, 0), 1.1, C(PRI))]
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
    # complemento da situação da tela ("Vencido há 16 dias · sem pedido no RSPE - requerer"): vai para a observação
    resto = s.split(" · ", 1)[1].strip() if " · " in s else ""
    if sl.startswith("extinção cabível"):
        return ("Extinção cabível", "vermelho", s if "verificar" in sl else resto)
    if sl.startswith("vencid") or sl.startswith("lapso"):
        return ("Vencido", "vermelho", s if "verificar" in sl else resto)
    if sl.startswith("a verificar") or sl.startswith("extinção a verificar"):
        return ("A verificar", "amarelo", s if sl.startswith("a verificar") else "")
    if sl.startswith("em cumprimento") or sl.startswith("em ") or sl.startswith("vence") or sl.startswith("término"):
        if dias is not None and 0 <= dias <= 90:
            return ("Vence hoje" if dias == 0 else "Vence em %s" % rs.pl(dias, "dia", "dias"), cor if cor in ("laranja", "amarelo", "verde") else "amarelo", "")
        if dias is not None and dias > 90:
            return ("Em cumprimento", "", "faltam %s" % rs.pl(dias, "dia", "dias"))
        return ("Em cumprimento", "", "")
    if sl.startswith("pena interrompida") or sl.startswith("pena suspensa"):
        return (s.split(" (")[0], "cinza", "")
    if sl.startswith("não se aplica") or sl.startswith("não consta") or sl.startswith("não iniciou"):
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
            "Não atinge": ("Não atinge", "cinza"), "Não alcançado": ("Não alcançado", "cinza"), "Concedido": ("Concedido", "azul"), "Indeferido": ("Indeferido", "vermelho"),
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
    frase = re.sub(r"\s+([,.;:])", r"\1", frase)  # o parêntese sai do meio da frase: "decisão (14/05/2024), não" -> "decisão, não"
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
TL_COR = {"provisoria": ("#AEB5B0", "#FFFFFF"), "cumprimento": ("#2F7A4F", "#2F7A4F"), "evasao": ("#A33A36", "#F6E4E3"), "interrupcao": ("#A33A36", "#F6E4E3"),
          "outro_motivo": ("#B3A8C9", "#B3A8C9"), "encerrada": ("#5F6662", "#E7E9E5"), "liberdade": ("#CDD2CC", "#ECEEEB"), "livramento": ("#A9BDD0", "#A9BDD0"), "duvida": ("#B5651D", "#F5EDDA")}
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
    g.add(Line(PL, yy(Y0), PL + Wx, yy(Y0), strokeColor=C("#CDD2CC"), strokeWidth=1.2))
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
            _hachura(g, x1, yy(Y0 + 7), x2 - x1, 14, "#A33A36")
        elif tipo == "duvida":
            _hachura(g, x1, yy(Y0 + 7), x2 - x1, 14, "#B5651D")
            g.add(String((x1 + x2) / 2, yy(Y0 + 2.5), "?", fontName=FB, fontSize=8, fillColor=C("#7A5410"), textAnchor="middle"))
        elif tipo == "provisoria":
            t = 0.0
            while t < x2 - x1:
                g.add(Line(x1 + t, yy(Y0 + 7), x1 + t, yy(Y0 - 7), strokeColor=C("#AEB5B0"), strokeWidth=1.2))
                t += 3.0
        if x2 - x1 > 34:
            g.add(String((x1 + x2) / 2, yy(Y0 + 20), _tl_dias((b - a).days), fontName=FN, fontSize=5.5, fillColor=C("#5F6662"), textAnchor="middle"))
    # marcos
    marcos = [(D(L.get("fato")) or D(L.get("ppe_termo")) or hoje, "Fato", "#5F6662")]
    if D(L.get("sentenca")):
        marcos.append((D(L.get("sentenca")), "Sentença", "#5F6662"))
    if D(L.get("ppe_termo")):
        marcos.append((D(L.get("ppe_termo")), "Trânsito (termo)", "#4A6A8A"))
    for a, b, tipo, p in faixas:
        if tipo in ("evasao", "interrupcao"):
            marcos.append((a, "Fuga" if tipo == "evasao" else "Interrupção", "#8E2424"))
            marcos.append((b, "Recaptura" if p.get("fim") else "Hoje", "#1F5B39"))
    marcos.append((hoje, "Situação atual", "#262B28"))
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
        g.add(String(cx, yy(ty + 6.5), rs.fmt(d), fontName=FN, fontSize=5.4, fillColor=C("#5F6662"), textAnchor=anchor))
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
        cor = {"prescrita": "#8E2424", "a verificar": "#7A5410"}.get(s.get("resultado"), "#1F5B39")
        rot = ("revogação do livramento" if s.get("revogacao") else ("interrupção" if s.get("e_evasao") is False else "fuga")) + " de " + s.get("evasao", "")
        g.add(Line(xa, yy(Y0), xa, yy(yc), strokeColor=C("#8E2424"), strokeWidth=0.5, strokeDashArray=[1.5, 1.5]))
        g.add(Line(xa, yy(yc), min(xb, x(lim) if lim else xb), yy(yc), strokeColor=C(cor), strokeWidth=2.6, strokeLineCap=1))
        ax = xa > PL + Wx - 190
        g.add(String(PL + Wx if ax else xa, yy(yc - 7), "contagem da prescrição pelo saldo (art. 113) · " + rot, fontName=FB, fontSize=5.4, fillColor=C(cor), textAnchor="end" if ax else "start"))
        rotulos = []
        if limn and x(limn) < xb:
            rotulos.append((x(limn), "#8E2424", "venceria %s (saldo mín.)" % s["limite_min"], 1.0, False))
        vistos = {s.get("limite_min"), s.get("limite_max")}
        for fx in s.get("faixas") or []:
            if fx.get("limite") and fx.get("prescrita") and fx["limite"] not in vistos:
                vistos.add(fx["limite"])
                rotulos.append((x(D(fx["limite"])), "#8E2424", "venceria %s se o saldo fosse %s" % (fx["limite"], fx.get("rotulo") or ""), 1.0, True))
        if lim:
            rotulos.append((x(lim), "#5F6662", "venceria %s (saldo máx.)" % s["limite_max"], 1.0, False))
        rotulos.append((xb, "#1F5B39", ("recaptura %s → interrompe (art. 117, V)" % s["fim"]) if (s.get("fim") and s.get("fim") != "hoje") else "hoje", 1.6, False))
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
            g.add(String(cxx + 5, yy(cy + 18 + j * 8.6), ra + ":", fontName=FN, fontSize=5.4, fillColor=C("#5F6662")))
            g.add(String(cxx + cw - 5, yy(cy + 18 + j * 8.6), rb, fontName=FB, fontSize=5.4, fillColor=C("#262B28"), textAnchor="end"))
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
    term_calc = str(m.get("termino") or "").endswith("*")  # o SEEU não imprimiu o término: data calculada pelo programa
    def caixa(rot, val):
        return [Paragraph(_t(rot), st["rot"]), Paragraph(_t(val or "—"), st["val"])]
    q = [("Regime atual", m.get("regime") + ((" · " + m["motivo_exec"]) if m.get("motivo_exec") else "")), ("Pena total", m.get("pena_total")),
         ("Cumprida", m.get("pena_cumprida")), ("Remanescente", m.get("pena_rem")),
         ("Dias remidos (saldo do RSPE)", (m.get("remidos") or "").split(" (")[0]), ("Data-base", m.get("dbase")),
         ("Término (calculado*)" if term_calc else "Término (SEEU)", m.get("termino") if m.get("termino") not in (None, "", "—") else (m.get("termino_motivo") or "—")),
         ("Conduta (ficha disciplinar)", m.get("conduta"))]
    grade = [[caixa(*x) for x in q[i:i + 4]] for i in range(0, len(q), 4)]
    tq = Table(grade, colWidths=[W / 4.0] * 4)
    tq.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.6, C(LINE)),
                            ("INNERGRID", (0, 0), (-1, -1), 0.6, C(LINE)), ("BACKGROUND", (0, 0), (-1, -1), C(ZEBRA)),
                            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    el.append(tq)
    if term_calc:
        nota = (m.get("calc_notas") or {}).get("termino") or "; ".join((m.get("calc_notas") or {}).values())
        el.append(Paragraph(_t(nota or "Término*: calculado pelo programa - o SEEU não imprimiu o término."), st["mut"]))

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
    if not dm("prog") and not obs and (m.get("prog_motivo") or "").split(" (")[0] != rot:
        obs = m.get("prog_motivo") or ""
    if m.get("ped_prog"):
        obs = (obs + " · " if obs else "") + "pedido no RSPE: " + m["ped_prog"]
    add("Progressão", dm("prog") and (dm("prog") + " · " + (m.get("frac_prog") or "")), rot, cor, obs)
    rot, cor, obs = _etiqueta_prazo(m.get("liv_sit"), m.get("liv_cor"), m.get("liv_dias"))
    fl = m.get("frac_liv") or ""
    fl = "livramento vedado (1/1)" if fl.strip() in ("1", "1/1") else fl
    add("Livramento condicional", dm("liv") and (dm("liv") + " · " + fl), rot, cor,
        obs or (m.get("liv_motivo") or "" if not dm("liv") and (m.get("liv_motivo") or "").split(" (")[0] != rot else ""))
    rot, cor, obs = _etiqueta_prazo(m.get("ext_sit"), m.get("ext_cor"), m.get("ext_dias"))
    hip = m.get("ext_hipoteses") if m.get("ext_hipoteses") not in (None, "", "—") else ""
    add("Término da pena", dm("termino") and (dm("termino") + (" (calculado)" if term_calc else "")), rot, cor,
        hip.split(";")[0] if m.get("ext_cor") in ("vermelho", "amarelo") and hip else (obs if cor == "vermelho" else ""))
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
    if m.get("presc_retro_cor") in ("vermelho", "amarelo"):
        # "A verificar": aparente pelas datas do RSPE, mas depende de marco que ele não traz (pronúncia, acórdão, datas incoerentes)
        add("Prescrição punitiva", "", "Aparente" if m["presc_retro_cor"] == "vermelho" else "A verificar", m["presc_retro_cor"],
            re.sub(r"^(Aparente|A verificar)\s*:\s*", "", m.get("presc_retro_full") or ""))
    if m.get("presc_ppe_cor") in ("vermelho", "amarelo"):
        # o rótulo é o da tela: "Iminente" só quando a prescrição está mesmo próxima; o mais comum é "A verificar"
        add("Prescrição executória", "", "Aparente" if m["presc_ppe_cor"] == "vermelho" else (pe or "A verificar"), m["presc_ppe_cor"],
            re.sub(r"^(Aparente|Iminente|A verificar|Possível)\s*[:-]\s*", "", m.get("presc_ppe_full") or "", flags=re.I))
    elif pe and pe not in ("Não prescrita", "Sem dados"):
        add("Prescrição executória", "", pe, m.get("presc_ppe_cor") or "", "")
    el.append(_tabela(ben, [W * 0.22, W * 0.18, W * 0.16, W * 0.44], st, cores_linha=cores))
    el.append(Paragraph(_t("Progressão, livramento e término: datas do SEEU impressas no RSPE%s. Indulto, comutação, prescrição e falta: cálculo do programa, a conferir. " % (
        " (o término marcado com * foi calculado pelo programa, porque o RSPE não o imprime)" if term_calc else "")) + _t(
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
        if D and (D["total"] >= 1 or D["em_curso"]["itens"] or D.get("a_conferir", {}).get("itens") or D["lacunas"]["itens"]):
            import rspe_ficha as rf
            el.append(Spacer(1, 5))
            el.append(Paragraph(_t("A remir por origem: %s%s" % (rs.pl(int(D["total"]), "dia", "dias") if D["total"] == int(D["total"]) else _num(D["total"]) + " dias",
                                                                  (" (+ ≈ %s do trabalho em curso)" % rs.pl(D["em_curso"]["dias"], "dia", "dias")) if D["em_curso"]["dias"] else "")), st["neg"]))
            lin = [["Origem", "Dias", "De onde vem", "Providência"]]
            for k, r_, p_ in rf.ORIGENS_REMICAO + [("lacunas", "Lacuna entre atestados", "verificar com a unidade se houve trabalho")]:
                its = D[k]["itens"]
                if its:
                    est = k in ("sem_atestado", "em_curso", "a_conferir") or (k == "estudo" and any(i["estimado"] for i in its))
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
                th.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (0, 0), 0.5, C("#CDD2CC")), ("BOX", (1, 0), (1, 0), 0.5, C("#CDD2CC")),
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
                            title="Relatório individual - %s" % m.get("nome"), author="APTO")
    fr_ = _moldura("Relatório individual", nome_base)
    doc.build(el, onFirstPage=fr_, onLaterPages=fr_, canvasmaker=_canvas_numerado())
    return caminho


def nome_arquivo(m):
    nome = re.sub(r"[^\w\- ]", "", rv.re.sub(r"\s+", " ", (m.get("nome") or "assistido"))).strip()
    return "%s - %s.pdf" % (m.get("proc") or "sem numero", nome[:60])


# ---------------------------------------------------------------- relatório geral: agregação
def _faixa_pena(dias):
    if not dias:
        return "Sem pena no RSPE"
    a = dias / float(rs.DIAS_ANO)
    for lim, rot in ((4, "Até 4 anos"), (8, "4 a 8 anos"), (12, "8 a 12 anos"), (20, "12 a 20 anos")):
        if a <= lim:
            return rot
    return "Mais de 20 anos"


def _prazo(d):
    if d is None:
        return None
    if d < 0:  # vence hoje (0 dia) fica em "até 30 dias", como na tela ("Vence hoje", laranja) e no filtro "Vencidas"
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
        return "Não consta no RSPE"
    u = rs._sem_acento(t).upper()
    for k, rot in (("SEMI", "Semiaberto"), ("ABERTO", "Aberto"), ("FECHADO", "Fechado"), ("LIVRAMENTO", "Livramento condicional"),
                   ("RESTRITIVA", "Restritiva de direitos"), ("SURSIS", "Sursis"), ("MEDIDA", "Medida de segurança")):
        if k in u:
            return rot
    return t[:1].upper() + t[1:].lower()


def _rotulo_unidade(t):
    t = re.sub(r"\s+", " ", (t or "").strip())
    if not t:
        return "Não informada"
    t = " ".join(w if w in ("CPAIG", "PTRAN", "EPJFC", "IPCG") or w[:1].isdigit() else w.lower() if w.upper() in ("DE", "DO", "DA", "DOS", "DAS", "E")
                 else w.title() for w in t.split())
    if len(t) > 50:
        t = re.sub(r"\bde Campo Grande\b", "de CG", t)  # nome longo: a cidade não pode sumir no corte ("...de Campo Gra")
    return t if len(t) <= 56 else t[:40].rstrip() + "… " + t[-14:].lstrip()


def _rotulo_vara(t):
    """Nome da vara encurtado e em caixa normal: '1ª VARA DE EXECUÇÃO PENAL DA COMARCA DE CAMPO GRANDE' -> '1ª VEP - Campo Grande'."""
    t = re.sub(r"\s+", " ", (t or "").strip())
    if not t:
        return "Não consta"
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
            fx_id["Sem data de nascimento"] += 1
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
        # estuda = matrícula ativa na ficha (estudo em curso), como "trabalha" = trabalho em curso; "Estudo a requerer"
        # (fd_estudo) é outra coisa: horas de estudo pendentes de remição
        estudo += any((L.get("emp") or "").startswith("Estudo") and "matrícula ativa" in (L.get("per") or "") for L in (m.get("fd_linhas") or []))
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
        if m.get("interrompida") or re.search(r"interrompid|suspens", (m.get(campo_sit) or "").lower()):
            return "interrompida"
        return "sem data no RSPE"
    E["faixas"] = {}
    E["venc"] = {}
    for rot, kd, ks, kp, cor in (("Progressão", "prog_dias", "prog_sit", "prog", "prog_cor"), ("Livramento condicional", "liv_dias", "liv_sit", "liv", "liv_cor")):
        E["faixas"][rot] = Counter(faixa(m, kd, ks) for m in modelos)
        v = [m for m in modelos if m.get(cor) == "vencido" or (m.get(kd) is not None and m.get(kd) < 0 and not m.get("estado_exec"))]
        E["venc"][rot] = {"total": len(v),
                          "sem_pedido": sum(1 for m in v if "sem pedido" in (m.get(ks) or "") and not (m.get("pedidos") or {}).get(kp)),
                          "pendente": sum(1 for m in v if "pendente" in (m.get(ks) or "")),
                          "indeferido": sum(1 for m in v if "indeferido" in (m.get(ks) or "")),
                          "marcado": sum(1 for m in v if (m.get("pedidos") or {}).get(kp))}
    def faixa_term(m):
        # término: a mesma leitura da aba Extinção (cor e situação), para o quadro 3.2 bater com o 3.4
        c, d = m.get("ext_cor"), m.get("ext_dias")
        if c == "vermelho":
            return "vencido"  # extinção cabível
        if c == "azul":
            return "não se aplica"  # extinta (registrada)
        if (m.get("ext_sit") or "").startswith("Extinção a verificar"):
            return "a verificar"
        if d is not None:
            return "até 30 dias" if d < 0 else (_prazo(d) or "mais de 180 dias")
        if m.get("interrompida") and not m.get("estado_exec"):
            return "interrompida"
        return "não se aplica" if m.get("estado_exec") in SEM else "sem data no RSPE"
    E["faixas"]["Término da pena"] = Counter(faixa_term(m) for m in modelos)
    E["venc_assist"] = sum(1 for m in modelos if m.get("prog_cor") == "vencido" or m.get("liv_cor") == "vencido")
    E["venc_sem_pedido"] = sum(1 for m in modelos if any(m.get(c) == "vencido" and "sem pedido" in (m.get(s_) or "") and not (m.get("pedidos") or {}).get(k)
                                                          for c, s_, k in (("prog_cor", "prog_sit", "prog"), ("liv_cor", "liv_sit", "liv"))))

    # ---- faltas graves: RSPE (incidentes) e ficha disciplinar (PADIC) ----
    lim12 = hoje - timedelta(days=365)
    F = {"firme12": 0, "apurar12": 0, "rspe_hom": 0, "rspe_pend": 0, "rspe_neg": 0, "rspe_hom12": 0, "rspe_pend12": 0, "assist_pend": 0,
         "regr12": 0, "perda12": 0, "pend_dias": [], "ficha_sem_seeu": 0, "ficha_sem_seeu_ass": 0}
    for m in modelos:
        F["firme12"] += bool(m.get("falta_sim"))
        F["apurar12"] += bool(m.get("falta_apurar"))
        tem_pend = False
        tem_ficha = False
        for i in (m.get("_bruto") or {}).get("_incidentes") or []:
            if i.get("_ficha"):
                # falta grave ou fuga da ficha (SIAPEN) que o RSPE não traz: não é incidente do SEEU - conta à parte
                F["ficha_sem_seeu"] += 1
                tem_ficha = True
                continue
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
        F["ficha_sem_seeu_ass"] += tem_ficha
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
                          "sem dados" if m.get("presc_ppe_cor") == "cinza" else "extinta" if m.get("presc_ppe_cor") == "azul" else "não prescrita")
                         for m in modelos)
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
CAT = ["#0B3B22", "#3E8E62", "#C9A55C", "#7FB894", "#8A5D0E", "#4A6A8A", "#B08497", "#A33A36"]
CINZA_OUTROS = "#C6CBC6"


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
    cinzas = {"Outros", "não consta", "Não consta", "Não consta no RSPE", "Sem data de nascimento", "Não informada", "não informada", "Sem pena no RSPE", "Sem dados no RSPE"}
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
    d.add(Line(leg_x, y - 3, leg_x + leg_w - 2, y - 3, strokeColor=colors.HexColor("#CDD2CC"), strokeWidth=0.5))
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
        d.add(Line(0, yy, largura, yy, strokeColor=colors.HexColor("#ECEEEB"), strokeWidth=0.4))
    d.add(Line(0, y0, largura, y0, strokeColor=colors.HexColor("#CDD2CC"), strokeWidth=0.6))
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
    st_parte = ParagraphStyle("parte", parent=st["tit"], fontSize=15, leading=19, textColor=C(NAVY), spaceBefore=4)
    RW = W / 2.0 - 10

    def numeros(lista, cores=None):
        cel = []
        for k, it in enumerate(lista):
            v, rot = it[0], it[1]
            det = it[2] if len(it) > 2 else ""
            cor = (cores or {}).get(k)
            num = Paragraph(_t(str(v)), st["num"])  # número em grafite: a cor fica para as etiquetas, não para o destaque
            cel.append([num, Paragraph(_t(rot), st["rot"])] + ([Paragraph(_t(det), st["mut"])] if det else []))
        t = Table([cel], colWidths=[W / len(lista)] * len(lista))
        t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.6, C(LINE)), ("LINEBELOW", (0, 0), (-1, 0), 0.6, C(LINE)),
                               ("LINEAFTER", (0, 0), (-2, 0), 0.6, C(LINE)), ("TOPPADDING", (0, 0), (-1, -1), 6),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 7), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t

    def parte(num, titulo, sub=""):
        el.append(CondPageBreak(110 * mm))  # o título da parte não fica sozinho no pé da página
        el.append(Spacer(1, 6))
        el.append(Paragraph('<font color="%s">%s</font>&nbsp;&nbsp;%s' % (PRI, num, _t(titulo)), st_parte))
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

    # ------------------------------------------------------------ capa
    p0, p1 = E["periodo"]
    el += _capa("Relatório geral da base", nome_base, [
        "%s · %d com ficha disciplinar (SIAPEN)" % (rs.pl(E["n"], "assistido", "assistidos"), nf),
        "RSPEs gerados entre %s e %s" % (rs.fmt(p0) or "?", rs.fmt(p1) or "?"),
        "Emitido em %s" % datetime.now().strftime("%d/%m/%Y")], W, st)
    # ------------------------------------------------------------ cabeçalho
    el.append(Paragraph(_t("Relatório geral da base · %s" % nome_base), st["tit"]))
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
    ordem_id = ["18 a 24 anos", "25 a 29 anos", "30 a 39 anos", "40 a 49 anos", "50 a 59 anos", "60 anos ou mais", "Sem data de nascimento"]
    ordem_pena = ["Até 4 anos", "4 a 8 anos", "8 a 12 anos", "12 a 20 anos", "Mais de 20 anos", "Sem pena no RSPE"]
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
                       (E["estudo"], "estudam", (pct(E["estudo"], nf) + " dos com ficha · matrícula ativa") if nf else "matrícula ativa na ficha"),
                       (P.get("PADIC instaurado", 0), "faltas com PADIC instaurado", "sem resultado lançado na ficha"),
                       (F["ficha_sem_seeu"], "faltas graves e fugas da ficha sem registro no SEEU", rs.pl(F["ficha_sem_seeu_ass"], "assistido", "assistidos")),
                       (F["firme12"], "assistidos com falta grave nos últimos 12 meses", "sanção reconhecida em juízo")],
                      {2: "amarelo", 3: "amarelo", 4: "laranja"}))
    el.append(Spacer(1, 10))
    ordem_c = ["Excelente", "Ótima", "Boa", "Neutra", "Regular", "Má", "Péssima", "Sem lapso", "Responde PADIC", "Outra anotação", "Não informada"]
    cores_c = {"Excelente": "#0B3B22", "Ótima": "#1F6B43", "Boa": "#3E8E62", "Neutra": "#6B5B8A", "Regular": "#C9A55C", "Má": "#8A5D0E", "Péssima": "#8E2424",
               "Sem lapso": "#AEB5B0", "Responde PADIC": "#C9A55C", "Outra anotação": "#CDD2CC"}
    lado(_rosca("2.1 Conduta carcerária", [(k, E["conduta"].get(k, 0)) for k in ordem_c], RW, st, "com ficha", max_fatias=8, cores=cores_c, ordenar=False),
         _rosca("2.2 Situação laboral", [(k, E["trabalho"].get(k, 0)) for k in ("Trabalha (interno)", "Trabalha (externo)", "Não trabalha")], RW, st, "com ficha",
                cores={"Trabalha (interno)": "#1F6B43", "Trabalha (externo)": "#7FB894", "Não trabalha": "#AEB5B0"}, ordenar=False))
    resp = ("Tempo de resposta do PADIC (do fato à decisão): mediana de %s. " % rs.pl(F["padic_resp_mediana"], "dia", "dias")) if F["padic_resp_mediana"] is not None else ""
    mp = sorted(F["pend_dias"])
    lado(_rosca("2.3 Faltas na ficha: situação do PADIC", [("Registrada, sem PADIC instaurado", P.get("registrada", 0)), ("PADIC instaurado, sem resultado na ficha", P.get("PADIC instaurado", 0)),
                                                          ("Julgada: sanção aplicada", P.get("homologada/punida", 0)), ("Julgada: arquivada ou absolvido", P.get("arquivada", 0))],
                RW, st, "faltas", ordenar=False,
                cores={"Registrada, sem PADIC instaurado": "#AEB5B0", "PADIC instaurado, sem resultado na ficha": "#C9A55C", "Julgada: sanção aplicada": "#0B3B22",
                       "Julgada: arquivada ou absolvido": "#7FB894"},
                nota=resp + "%s sem julgamento há mais de 60 dias do fato." % rs.pl(F["padic_abertos60"], "falta", "faltas")),
         _rosca("2.4 Faltas graves no RSPE: decisão judicial", [("Homologadas", F["rspe_hom"]), ("Sem decisão (pendentes)", F["rspe_pend"]),
                                                                ("Não homologadas ou afastadas", F["rspe_neg"])], RW, st, "faltas", ordenar=False,
                cores={"Homologadas": "#0B3B22", "Sem decisão (pendentes)": "#C9A55C", "Não homologadas ou afastadas": "#7FB894"},
                nota=(("A falta pendente mais antiga aguarda decisão há %s do fato. " % rs.pl(mp[-1], "dia", "dias")) if mp else "") +
                     ("Fora do quadro: %s da ficha sem registro no SEEU." % rs.pl(F["ficha_sem_seeu"], "falta grave ou fuga", "faltas graves ou fugas")
                      if F["ficha_sem_seeu"] else "")))
    secao("2.5 Remição: pendências", "Pela ficha disciplinar x RSPE: dias que ainda não viraram remição no RSPE, pela origem. "
          "O detalhe por assistido e por unidade está no relatório \"Remição detalhada\".")
    O = E["rem_orig"]
    # as três parcelas fecham o total: atestados (peticionados, só emitidos e diferença), trabalho sem atestado, estudo e leitura
    el.append(numeros([(O["ass"], "assistidos com remição a requerer (com a estimativa)",
                        # mesma contagem do cartão vermelho "Remição a requerer" da aba Ficha disciplinar (a diferença de dias, amarela
                        # na aba como "Conferir remição", não entra)
                        "%s em vermelho na aba Ficha (remição a requerer / atestado não lançado) · %s sem nenhuma remição no RSPE (toda a base)" % (E["rem_req"], E["rem_zero"])),
                       (_num(O["r_total"]), "dias a remir (todas as origens)"),
                       (_num(O["r"]["nao_lancado"] + O["r"]["emitido"] + O["r"]["divergencia"]), "dias de atestados sem remição ou com remição menor",
                        "%s peticionados · %s só emitidos · %s de diferença" % (_num(O["r"]["nao_lancado"]), _num(O["r"]["emitido"]), _num(O["r"]["divergencia"]))),
                       (_num(O["r"]["sem_atestado"]), "dias de trabalho sem atestado (estimativa)", rs.pl(O["n"]["sem_atestado"], "assistido", "assistidos")),
                       (_num(O["r"]["estudo"] + O["r"]["leitura"]), "dias de estudo (≈) e leitura sem remição",
                        "%s de estudo · %s de leitura (exatos)" % (_num(O["r"]["estudo"]), _num(O["r"]["leitura"])))],
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
                                    [("% da base", [round(100.0 * x[2] / n) for x in indic], "#3E8E62")], W, st, altura=105, sufixo="%",
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
    grupos = [("Vencido", ["vencido"]), ("A verificar", ["a verificar"]), ("Até 90 dias", ["até 30 dias", "até 60 dias", "até 90 dias"]), ("91 a 180 dias", ["até 180 dias"]),
              ("Mais de 180 dias", ["mais de 180 dias"]), ("Pena parada", ["interrompida"]), ("Não se aplica", ["não se aplica"]), ("Sem data no RSPE", ["sem data no RSPE"])]
    cor_g = {"Vencido": "#A33A36", "A verificar": "#E0C27A", "Até 90 dias": "#C9A55C", "91 a 180 dias": "#3E8E62", "Mais de 180 dias": "#1F6B43", "Pena parada": "#6B5B8A",
             "Não se aplica": "#AEB5B0", "Sem data no RSPE": "#CDD2CC"}
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
    fx = ["vencido", "a verificar", "até 30 dias", "até 60 dias", "até 90 dias", "até 180 dias", "mais de 180 dias", "interrompida", "não se aplica", "sem data no RSPE"]
    cab = ["", "Vencido", "A verificar", "≤ 30 dias", "31 a 60", "61 a 90", "91 a 180", "> 180 dias", "Pena parada", "Não se aplica", "Sem data"]
    tb = [cab]
    for rot in ("Progressão", "Livramento condicional", "Término da pena"):
        c = E["faixas"].get(rot, Counter())
        tb.append([Paragraph(_t(rot), st["neg"])] + [str(c.get(k, 0)) for k in fx])
    el.append(KeepTogether([_tabela(tb, [W * 0.18] + [W * 0.082] * 10, st, pad=4)]))
    el.append(Paragraph(_t("Vencido: a data prevista já passou (a que vence hoje entra em \"≤ 30 dias\", como na tela); no término, é a extinção cabível "
                           "da aba Extinção. A verificar: extinção a verificar (custódia ou detração que pode alcançar a pena). "
                           "Pena parada: foragido (interrompida) ou preso por outro processo (suspensa). Não se aplica: em livramento, já no regime aberto, "
                           "pena cumprida ou extinta, ou cumprimento não iniciado."), st["mut"]))

    secao("3.3 Indulto e comutação por decreto",
          "Assistidos por decreto; cada assistido conta uma vez por decreto, pelo melhor resultado (indulto ou comutação). Gráfico do decreto mais "
          "antigo ao mais recente; quadro do mais recente ao mais antigo, com o filete verde quando algum assistido tem o benefício cabível e "
          "amarelo quando só há casos a verificar.")
    com_alc = [r for r in E["decretos"] if r["cabe"] + r["ver"] + r["nao"] + r["imp"] + r["conc"] + r["indef"]]
    graf = [r for r in reversed(com_alc) if r["cabe"] + r["ver"] + r["conc"]]
    if graf:
        el.append(KeepTogether(_colunas("Assistidos com indulto ou comutação cabível, a verificar ou concedido, por decreto",
                                        [("%s%s" % (r["ano"], " Mães" if "maes" in str(r["id"]) else "")) for r in graf],
                                        [("Cabe", [r["cabe"] for r in graf], "#1F6B43"), ("A verificar", [r["ver"] for r in graf], "#C9A55C"),
                                         ("Concedido (RSPE)", [r["conc"] for r in graf], "#3E8E62")], W, st, altura=100)))
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
    # os do Dia das Mães são só para mulheres: sem assistida alcançada, o motivo é esse, e não a data da execução
    sem = [str(r["ano"]) for r in E["decretos"] if r not in com_alc and "maes" not in str(r["id"])]
    sem_m = [str(r["ano"]) for r in E["decretos"] if r not in com_alc and "maes" in str(r["id"])]
    if sem:
        el.append(Paragraph(_t("Decretos que não alcançam nenhum assistido (execução iniciada depois ou sem condenação até o decreto): %s." % ", ".join(sem)), st["mut"]))
    if sem_m:
        el.append(Paragraph(_t("Decretos do Dia das Mães (só para mulheres) sem nenhuma assistida alcançada: %s." % ", ".join(sem_m)), st["mut"]))

    secao("3.4 Prescrição e extinção da pena")
    ret = Counter()
    for m in modelos:
        c_ = m.get("presc_retro_cor")
        ret["Aparente" if c_ == "vermelho" else "A verificar" if c_ == "amarelo" else "Sem dados no RSPE" if c_ == "cinza" else
            "Já extinta (RSPE)" if c_ == "azul" else "Não configurada"] += 1
    cor_p = {"Aparente": "#A33A36", "Iminente ou a verificar": "#C9A55C", "A verificar": "#C9A55C", "Não prescrita": "#1F6B43", "Não configurada": "#1F6B43",
             "Já extinta (RSPE)": "#4A6A8A"}
    demais = max(0, E["n"] - E["ext_cabivel"] - E["ext_verificar"] - E["ext_registrada"])
    W3 = W / 3.0 - 8
    trio = [_rosca("Pretensão executória", [("Aparente", pres.get("aparente", 0)), ("Iminente ou a verificar", pres.get("iminente / a verificar", 0)),
                                            ("Não prescrita", pres.get("não prescrita", 0)), ("Sem dados no RSPE", pres.get("sem dados", 0)),
                                            ("Já extinta (RSPE)", pres.get("extinta", 0))],
                   W3, st, "assistidos", cores=cor_p, ordenar=False, abaixo=True),
            _rosca("Pretensão punitiva", [("Aparente", ret.get("Aparente", 0)), ("A verificar", ret.get("A verificar", 0)), ("Não configurada", ret.get("Não configurada", 0)),
                                          ("Sem dados no RSPE", ret.get("Sem dados no RSPE", 0)), ("Já extinta (RSPE)", ret.get("Já extinta (RSPE)", 0))], W3, st, "assistidos", cores=cor_p, ordenar=False, abaixo=True),
            _rosca("Extinção da pena", [("Extinção cabível", E["ext_cabivel"]), ("Até 60 dias ou a verificar", E["ext_verificar"]),
                                        ("Já extinta (RSPE)", E["ext_registrada"]), ("Em cumprimento ou sem previsão", demais)],
                   W3, st, "assistidos", ordenar=False, abaixo=True,
                   cores={"Extinção cabível": "#A33A36", "Até 60 dias ou a verificar": "#C9A55C", "Já extinta (RSPE)": "#3E8E62",
                          "Em cumprimento ou sem previsão": "#1F6B43"})]
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
                            title="Relatório geral - %s" % nome_base, author="APTO")
    fr = _moldura("Relatório geral", nome_base)
    doc.build(el, onFirstPage=_moldura_capa(), onLaterPages=fr, canvasmaker=_canvas_numerado())
    return caminho


def gerar(modelos, pasta, nome_base, individual=True, geral=True, nominal=True, individuais=None, remicao=False):
    """Cria <pasta>/Relatorios <data hora>/ com o geral e a subpasta Individuais. O geral e a estatística usam
    'modelos'; os PDFs individuais, 'individuais' (quando informado, os assistidos escolhidos).
    Devolve (pasta, n_individuais, erros)."""
    # pasta nova a cada geração: duas gerações no mesmo minuto não se misturam (a 2ª vai para "... (2)")
    base_dest = os.path.join(pasta, "Relatorios %s" % datetime.now().strftime("%Y-%m-%d %Hh%M"))
    destino, n = base_dest, 1
    while True:
        try:
            os.makedirs(destino)
            break
        except FileExistsError:
            n += 1
            destino = "%s (%d)" % (base_dest, n)
    erros, n = [], 0
    if geral:
        try:
            relatorio_geral(modelos, os.path.join(destino, "Relatorio geral - %s.pdf" % re.sub(r"[^\w\- ]", "", nome_base)), nome_base, nominal)
        except Exception as e:
            erros.append("relatório geral: %s" % e)
    if remicao:
        nb = re.sub(r"[^\w\- ]", "", nome_base)
        for nome, fn in (("remição detalhada", lambda: relatorio_remicao(modelos, os.path.join(destino, "Remicao detalhada - %s.pdf" % nb), nome_base, nominal)),
                         ("planilha de conferência (Excel)", lambda: planilha_remicao_xlsx(modelos, os.path.join(destino, "Conferencia da remicao - %s.xlsx" % nb), nome_base)),
                         ("planilha de conferência (PDF)", lambda: planilha_remicao_pdf(modelos, os.path.join(destino, "Conferencia da remicao - %s.pdf" % nb), nome_base))):
            try:
                fn()
            except Exception as e:
                erros.append("%s: %s" % (nome, e))
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
    O = {"dias": {k: 0 for k in ks}, "n": {k: 0 for k in ks}, "itens": {k: 0 for k in ks}, "ass": 0, "ass_exatos": 0, "total": 0, "com_ficha": 0}
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
        # com dias exatos: o mesmo critério do vermelho da aba Ficha (atestado sem remição no RSPE, inclusive o sem os dias na ficha,
        # leitura peticionada sem remição, estudo com horas declaradas) - a diferença de dias é amarela ("Conferir remição") e não entra
        O["ass_exatos"] += m.get("fd_cor") == "vermelho"
        O["total"] += D["total"]
    # dias inteiros para exibir: cada origem arredondada, com a soma igual ao total exibido (o quadro fecha)
    dentro = [k for k in ks if k != "lacunas" and k not in rf.FORA_DO_TOTAL]
    O["r"] = dict(zip(dentro, _arred_coluna([O["dias"][k] for k in dentro])))
    O["r"].update({k: round(O["dias"][k]) for k in ks if k not in O["r"]})
    O["r_total"] = sum(O["r"][k] for k in dentro)
    return O


def nome_rel(m):
    """Nome do assistido nos relatórios de remição: o do RSPE (SEEU) e, quando a ficha (SIAPEN) traz outra grafia, também o da
    ficha - é por ele que o arquivo costuma estar nomeado; execução arquivada no SEEU vem marcada."""
    n = m.get("nome") or ""
    fn = ((m.get("ficha") or {}).get("nome") or "").strip()
    norm = lambda t: re.sub(r"[^A-Z]", "", rs._sem_acento(t).upper())
    if fn and norm(fn) != norm(n):
        n += " (na ficha: %s)" % fn.title()
    if "ARQUIV" in (m.get("status_exec") or ""):
        n += " [execução ARQUIVADA no SEEU]"
    elif m.get("estado_exec") in ("extinta", "cumprida"):
        n += " [pena EXTINTA no RSPE]"
    return n


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
    COMO = {"nao_lancado": "dias remidos do próprio atestado; a ficha registra o peticionamento no SEEU",
            "emitido": "dias remidos do próprio atestado; a ficha registra só a emissão (a juntada se confere nos autos)", "divergencia": "dias do atestado (sem a fração) menos os da remição lançada",
            "sem_atestado": "estimativa: dias seg.-sáb. do vínculo sem atestado, sem feriados, ÷ 3 (LEP, art. 126, § 1º, II). Atestado juntado no SEEU e não "
                            "lançado na ficha não é visto pelo programa: este número tende a ser maior que o real (lance o atestado em \"Adicionar atestado\" na aba Ficha)",
            "estudo": "12 horas de frequência = 1 dia (LEP, art. 126, § 1º, I); horas declaradas ou estimadas",
            "leitura": "4 dias por obra (Res. CNJ 391/2021, art. 5º)", "em_curso": "estimativa, como no trabalho sem atestado",
            "a_conferir": "sem dias no total: vínculo aberto sem baixa na ficha (registro duplicado ou baixa esquecida); a estimativa só vale se a unidade confirmar o trabalho"}
    O = remicao_por_origem(modelos)
    com = [m for m in modelos if m.get("ficha_tem") and m.get("fd_rem_det")]
    pend = sorted([m for m in com if m["fd_rem_det"]["total"] >= 1 or any(m["fd_rem_det"][k]["itens"] for k in ("em_curso", "a_conferir", "lacunas"))],
                  key=lambda m: rs._sem_acento(m.get("nome") or "").upper())
    el = [Paragraph("Remição detalhada", st["tit"]),
          Paragraph(_t("%s · origem de cada dia a remir, pela ficha disciplinar (SIAPEN) x RSPE · %s com ficha de %s na seleção" % (
              nome_base, rs.pl(O["com_ficha"], "assistido", "assistidos"), len(modelos))), st["sub"]), Spacer(1, 10)]
    nums = [(O["ass"], "assistidos com remição a requerer (com a estimativa; %s em vermelho na aba Ficha: atestado, leitura ou estudo com horas "
                       "declaradas sem remição no RSPE)" % O["ass_exatos"]),
            (_num(O["r_total"]), "dias a remir (sem o trabalho em curso)"),
            (_num(O["r"]["nao_lancado"] + O["r"]["emitido"] + O["r"]["divergencia"]), "de atestados sem remição ou com remição menor"),
            (_num(O["r"]["sem_atestado"]), "de trabalho sem atestado (estimativa)"),
            (_num(O["r"]["estudo"] + O["r"]["leitura"]), "de estudo (≈) e leitura sem remição")]
    cel = [[Paragraph(_t(str(n)), st["num"]) for n, _ in nums], [Paragraph(_t(r), st["rot"]) for _, r in nums]]
    tb = Table(cel, colWidths=[W / len(nums)] * len(nums))
    tb.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, C(LINE)), ("INNERGRID", (0, 0), (-1, -1), 0.6, C(LINE)),
                            ("BACKGROUND", (0, 0), (-1, -1), C(ZEBRA)), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                            ("TOPPADDING", (0, 0), (-1, 0), 7), ("BOTTOMPADDING", (0, 1), (-1, 1), 7), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    el.append(tb)
    # execução arquivada ou com a pena extinta (registrada no RSPE), com dias a remir: a remição vai para outro processo ou perdeu o objeto
    arqv = [m for m in pend if ("ARQUIV" in (m.get("status_exec") or "") or m.get("estado_exec") in ("extinta", "cumprida"))
            and (m.get("fd_rem_det") or {}).get("total", 0) >= 1]
    difn = [m for m in pend if "(na ficha:" in nome_rel(m)]
    if arqv or difn:
        el.append(Spacer(1, 6))
    if arqv:
        el.append(Paragraph(_t("Atenção: %s com execução ARQUIVADA no SEEU ou com a pena EXTINTA registrada no RSPE, com %s dias no total acima: %s. "
                               "A remição deve ser pedida no processo em que a pena está em execução (transferência de comarca, unificação ou nova "
                               "guia); com a pena extinta, só se houver outra execução - conferir no SEEU. Estão marcadas pelo nome." % (
                                   rs.pl(len(arqv), "assistido", "assistidos"), _dias(sum(m["fd_rem_det"]["total"] for m in arqv)),
                                   ", ".join(m.get("nome") or "" for m in arqv))), st["mut"]))
    if difn:
        el.append(Paragraph(_t("%s com o nome no RSPE (SEEU) diferente do nome na ficha (SIAPEN), vinculados pelo CPF ou pelos autos: o nome da "
                               "ficha vem entre parênteses, pois o arquivo costuma estar nomeado por ele." % rs.pl(len(difn), "assistido", "assistidos")), st["mut"]))

    # 1) por origem
    el.append(Paragraph("1. Por origem", st["h2"]))
    dados = [["Origem", "Assistidos", "Itens", "Dias a remir", "Como foi calculado", "Providência"]]
    for k, r, p_ in ORI:
        dados.append([Paragraph(_t(r), peqn), Paragraph(str(O["n"][k]), dir_), Paragraph(str(O["itens"][k]), dir_),
                      Paragraph(_t(_num(O["r"][k]) + (" (fora do total)" if k in rf.FORA_DO_TOTAL else "")), dirn), Paragraph(_t(COMO[k]), peq), Paragraph(_t(p_), peq)])
    dados.append([Paragraph("Lacuna entre atestados", peqn), Paragraph(str(O["n"]["lacunas"]), dir_), Paragraph(str(O["itens"]["lacunas"]), dir_),
                  Paragraph("—", dir_), Paragraph("período sem vínculo comprovado: não há como estimar dias", peq), Paragraph("verificar com a unidade se houve trabalho", peq)])
    dados.append([Paragraph("Total", peqn), Paragraph(str(O["ass"]), dirn), "", Paragraph(_t(_num(O["r_total"])), dirn), "", ""])
    el.append(_tabela(dados, [58 * mm, 20 * mm, 14 * mm, 26 * mm, 80 * mm, W - 198 * mm], st, zebra=True))
    el.append(Spacer(1, 4))
    el.append(Paragraph(_t("Atestados: dias exatos do documento. Trabalho sem atestado, em curso e estudo sem horas declaradas: estimativa do programa "
                           "(o número exato sai do atestado ou da certidão a expedir). Vínculos simultâneos não contam o mesmo dia duas vezes. "
                           "Remição já lançada no RSPE e atestados anteriores a esta execução ficam de fora."), st["mut"]))

    # 2) por unidade prisional: onde o trabalho, o estudo ou a leitura aconteceu (entradas em unidade penal da ficha)
    ks = [k for k, _r, _p in ORI if k not in rf.FORA_DO_TOTAL]
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
    # dias inteiros por coluna, com a soma de cada coluna igual ao total da origem no quadro 1 (a tabela fecha)
    _uns = list(por_un)
    for k in ks:
        _v = [por_un[u][k] for u in _uns]
        # mesma soma do quadro 1 quando as unidades cobrem a origem inteira (sem isso, 6.112 lá e 6.111 aqui)
        for u, v in zip(_uns, _arred_coluna(_v, O["r"][k] if abs(sum(_v) - O["dias"][k]) < 1 else None)):
            por_un[u]["r_" + k] = v
    for u in _uns:
        por_un[u]["r_total"] = sum(por_un[u]["r_" + k] for k in ks)
    if por_un:
        el.append(CondPageBreak(40 * mm))
        el.append(Paragraph("2. Por unidade prisional (onde o trabalho, o estudo ou a leitura aconteceu)", st["h2"]))
        el.append(Paragraph(_t("A unidade de cada período vem das entradas em unidade penal registradas na ficha; o período que atravessa uma "
                               "transferência é dividido entre as unidades. Atestado: unidade em que o período atestado terminou. "
                               "\"Unidade não identificada\": período anterior à primeira entrada registrada na ficha."), st["mut"]))
        el.append(Spacer(1, 4))
        cab = ["Unidade", "Assistidos", "Atestado peticionado sem remição", "Atestado só emitido", "Diferença", "Trabalho sem atestado", "Estudo", "Leitura", "Total"]
        dados = [cab]
        for u, x in sorted(por_un.items(), key=lambda kv: (kv[0] == rf.SEM_UNIDADE, -kv[1]["total"])):
            dados.append([Paragraph(_t(u), peqn), Paragraph(str(len(x["ass"])), dir_)] + [Paragraph(_t(_num(x["r_" + k])), dir_) for k in ks] +
                         [Paragraph(_t(_num(x["r_total"])), dirn)])
        dados.append([Paragraph("Total", peqn), Paragraph("", dir_)] + [Paragraph(_t(_num(sum(x["r_" + k] for x in por_un.values()))), dirn) for k in ks] +
                     [Paragraph(_t(_num(sum(x["r_total"] for x in por_un.values()))), dirn)])
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
                    if k in rf.FORA_DO_TOTAL:
                        continue
                    for i in D[k]["itens"]:
                        if i["unidade"] == u and i["dias"]:
                            linhas.append((m, r_, i))
            if not linhas:
                continue
            tit = Paragraph("<b>%s</b> · %s · %s" % (_t(u), rs.pl(len(x["ass"]), "assistido", "assistidos"), _t("%s dias a remir" % _num(x["r_total"]))),
                            ParagraphStyle("pu", parent=st["cel"], fontSize=8.8, leading=12, textColor=C(NAVY)))
            dados = [["Assistido", "Nº da execução", "Origem", "Referência", "Período", "Dias", "Pedir"]]
            ant = None
            for m, r_, i in linhas:
                novo = m.get("id") != ant
                ant = m.get("id")
                dados.append([Paragraph(_t(nome_rel(m)), peqn) if novo else "", Paragraph(_t(m.get("proc") or m.get("id") or ""), peq) if novo else "",
                              Paragraph(_t(r_), peq), Paragraph(_t(i["ref"] + ((" · " + i["data"]) if i.get("data") else "")), peq), Paragraph(_t(i["per"]), peq),
                              Paragraph(_t(("≈ " if i.get("estimado") else "") + _num(i["dias"])), dir_),
                              Paragraph(_t({"sem_atestado": "atestado de trabalho", "estudo": "certidão de frequência", "leitura": "conferir homologação",
                                            "nao_lancado": "requerer a apreciação", "emitido": "verificar a juntada / peticionamento", "divergencia": "requerer a diferença"}.get(
                                  next(k for k, rr, _pp in ORI if rr == r_), "")), peq)])
            el.append(KeepTogether([Spacer(1, 8), tit, Spacer(1, 3), _tabela(dados[:5], larg3, st, zebra=False)]))
            if len(dados) > 5:
                el.append(_tabela([dados[0]] + dados[5:], larg3, st, zebra=False))

    # 4) por assistido: a conferência ficha x RSPE (o que já está no processo e o que não está) e o que falta remir
    conf = sorted([m for m in com if (m.get("fd_conc") or {}).get("tabela") or m["fd_rem_det"]["total"] >= 1
                   or any(m["fd_rem_det"][k]["itens"] for k in ("em_curso", "a_conferir", "lacunas"))],
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
        rot_st = {"CONCILIADO": "No processo", "NAO_LANCADO": "Sem remição no RSPE", "DIVERGENCIA": "No processo, dias diferentes"}
        for m in conf:
            D = m["fd_rem_det"]
            T = (m.get("fd_conc") or {}).get("tabela") or []
            un = _rotulo_unidade((m.get("ficha") or {}).get("unidade") or "") or "unidade não informada"
            tit = Paragraph("<b>%s</b> · %s · hoje em %s · <b>%s %s a remir</b>%s" % (
                _t(nome_rel(m)), _t(m.get("proc") or m.get("id") or ""), _t(un), _num(D["total"]), "dia" if D["total"] == 1 else "dias",
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
                fora = sum(_n(t["rem"]) for t in T if t["status"] == "NAO_LANCADO" and t.get("cor") != "cinza")
                nr = [t for t in T if t["atestado"].startswith("Atestado não registrado")]
                n_v = sum(1 for t in T if t["status"] == "NAO_LANCADO" and t.get("cor") != "cinza")
                n_r = sum(1 for t in T if t["status"] in ("CONCILIADO", "DIVERGENCIA") and t not in nr)
                res_ = Paragraph("%s · %s · %s%s · RSPE: %s" % (
                    _t("Ficha: %s em atestados desta execução" % ("%s dias remidos" % _num(fic))),
                    '<font color="%s"><b>%s</b></font>' % (COR["verde"][1], _t("no processo: %s dias (%s)" % (_num(dentro), rs.pl(n_r, "atestado", "atestados")))),
                    '<font color="%s"><b>%s</b></font>' % (COR["vermelho"][1], _t("sem remição no RSPE: %s dias (%s)" % (_num(fora), rs.pl(n_v, "atestado", "atestados")))),
                    (' · <font color="%s"><b>%s</b></font>' % (COR["azul"][1], _t("no RSPE sem atestado na ficha: %s dias (%s)" % (
                        _num(sum(_n(t["rem"]) for t in nr)), rs.pl(len(nr), "remição", "remições"))))) if nr else "",
                    _t((m.get("remidos") or "—"))), ParagraphStyle("rs", parent=st["cel"], fontSize=7.9, leading=10.5))
                dc = [["Atestado", "Unidade", "Período", "Dias trab.", "Remidos (ficha)", "Remição no RSPE", "Situação"]]
                cores = {}
                for t in T:
                    fora_ficha = t["atestado"].startswith("Atestado não registrado")
                    cor = "azul" if fora_ficha else "cinza" if t.get("cor") == "cinza" else cor_st.get(t["status"], "cinza")
                    sit = "No processo, sem atestado na ficha" if fora_ficha else t["rot"] if t.get("cor") == "cinza" else rot_st.get(t["status"], t.get("rot") or "")
                    if t["status"] == "NAO_LANCADO" and t.get("cor") != "cinza":
                        sit += " · peticionado em %s, aguardando decisão" % t["peticionado"] if t.get("peticionado") else " · só emitido (sem peticionamento na ficha)"
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
                                  Paragraph(_t(i["ref"] + ((" · emitido em %s" % i["data"]) if i.get("data") and k in ("nao_lancado", "emitido", "divergencia") else "")), peq),
                                  Paragraph(_t(i["per"]), peq), Paragraph(_t(i.get("base") or "—"), peq),
                                  Paragraph(_t(("≈ " if i.get("estimado") else "") + _num(i["dias"]) if i["dias"] else "—"), dir_),
                                  Paragraph(_t(p_ if n_ == 0 else ""), peq)])
                if len(its) > 1 and D[k]["dias"] and k != "lacunas":
                    dados.append(["", "", "", "", Paragraph(_t("subtotal" + (" (sem contar duas vezes os dias simultâneos)" if D[k].get("sobreposicao") else "")), peq),
                                  Paragraph(_t(("≈ " if k in ("sem_atestado", "em_curso", "a_conferir", "estudo") else "") + _num(D[k]["dias"])), dirn), ""])
            if len(dados) > 1:
                el.append(Spacer(1, 4))
                el.append(_tabela(dados, larg, st, zebra=False))
            else:
                el.append(Paragraph(_t("Nada a remir além do que já está no processo."), st["mut"]))
    doc = SimpleDocTemplate(caminho, pagesize=PG, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=21 * mm, bottomMargin=20 * mm,
                            title="Remição detalhada", author="APTO")
    fr = _moldura("Remição detalhada", nome_base,
                           "Triagem pela ficha disciplinar e pelo RSPE: atestados com dias exatos; trabalho sem atestado e estudo, estimativa. Conferir nos autos (SEEU) antes do pedido.", pagina=PG)
    doc.build(el, onFirstPage=fr, onLaterPages=fr, canvasmaker=_canvas_numerado())
    return caminho


# ---------------------------------------------------------------- planilha de conferência da remição (xlsx e pdf)
# situação de cada linha: (rótulo, cor da faixa no PDF, cor de fundo no Excel)
SIT_REM = {
    "processo": ("No processo", "verde", "DDF5E7"),
    "processo_dif": ("No processo, remição menor que o atestado", "amarelo", "FEF4D6"),
    "processo_maior": ("No processo, remição igual ou maior que o atestado", "verde", "DDF5E7"),
    "rspe_sem_ficha": ("No RSPE, sem atestado na ficha", "azul", "DBEAFE"),
    "peticionado": ("Peticionado no SEEU, sem remição no RSPE", "vermelho", "FDE8E8"),
    "emitido": ("Emitido, sem peticionamento na ficha", "laranja", "FFEAD5"),
    "sem_atestado": ("Trabalho sem atestado na ficha nem remição", "laranja", "FFEAD5"),
    "estudo": ("Estudo sem remição", "amarelo", "FEF4D6"),
    "leitura": ("Leitura sem remição", "amarelo", "FEF4D6"),
    "em_curso": ("Em curso (até 90 dias)", "cinza", "EEF0F3"),
    "a_conferir": ("A conferir (sem dias no total)", "cinza", "EEF0F3"),
    "lacunas": ("Lacuna entre atestados", "cinza", "EEF0F3"),
}
MOTIVOS_DIVERGENCIA = ["Atestado juntado nos autos e não lançado na ficha", "Peticionado e aguardando decisão", "Remição já declarada no processo",
                       "Vínculo duplicado ou sem baixa", "Período não trabalhado", "Diferença no número de dias", "Atestado de outros autos",
                       "Erro de leitura da ficha", "Outro (descrever na observação)"]
COLS_REM = ["Assistido", "Nº da execução", "Unidade atual", "Situação", "Unidade onde ocorreu", "Setor / curso / documento", "Início", "Fim",
            "Atestado nº", "Emitido em", "Peticionado em", "Autos do peticionamento", "Dias trabalhados / horas", "Remidos na ficha", "Remição no RSPE", "Dias a remir",
            "Estimativa", "Providência", "Trecho da ficha"]


def _n_br(x):
    try:
        return float(str(x).replace(".", "").replace(",", ".")) if isinstance(x, str) else float(x or 0)
    except Exception:
        return 0.0


def linhas_conferencia(modelos):
    """Uma linha por atestado da ficha (no processo ou não) e por período ou documento pendente, com a situação, a unidade,
    as datas, os dias e o trecho da ficha que comprova: base da planilha de conferência (Excel e PDF)."""
    import rspe_ficha as rf
    prov = dict((k, p_) for k, _r, p_ in rf.ORIGENS_REMICAO)
    prov["lacunas"] = "verificar com a unidade se houve trabalho"
    out = []
    com = sorted([m for m in modelos if m.get("ficha_tem") and m.get("fd_rem_det")], key=lambda m: rs._sem_acento(m.get("nome") or "").upper())
    for m in com:
        D = m["fd_rem_det"]
        base = {"Assistido": nome_rel(m), "Nº da execução": m.get("proc") or m.get("id") or "",
                "Unidade atual": _rotulo_unidade((m.get("ficha") or {}).get("unidade") or "")}
        # dias a remir de cada atestado: os mesmos da remição detalhada (parte fora do período já remido, teto do possível, diferença)
        valor = {}
        for k_ in ("nao_lancado", "emitido", "divergencia"):
            for i in D[k_]["itens"]:
                valor.setdefault((i["ref"], i.get("data") or ""), []).append(i["dias"])
        for t in (m.get("fd_conc") or {}).get("tabela") or []:
            if t["status"] == "ANTERIOR":
                continue
            fora = t["atestado"].startswith("Atestado não registrado")
            ref_ = t["atestado"].replace(" (informado por você)", "")
            vs = valor.get((ref_, t.get("emissao") or ""))
            v_ = vs.pop(0) if vs else None
            k = "rspe_sem_ficha" if fora else {"CONCILIADO": "processo", "DIVERGENCIA": "processo_dif" if v_ else "processo_maior"}.get(t["status"]) or (
                "peticionado" if t.get("peticionado") else "emitido")
            datas = [x for sg in t["segs"] for x in re.findall(r"\d{2}/\d{2}/\d{4}", sg["per"])]
            num = re.sub(r"^Atestado (?:nº )?", "", t["atestado"]).replace("(informado por você)", "").strip()
            arem = (v_ or 0) if k in ("peticionado", "emitido", "processo_dif") else 0
            out.append(dict(base, **{"_k": k, "Situação": SIT_REM[k][0], "Unidade onde ocorreu": t.get("unidade") or "",
                                     "Setor / curso / documento": "; ".join(dict.fromkeys(sg["setor"] for sg in t["segs"])),
                                     "Início": min(datas, key=lambda d: d[6:] + d[3:5] + d[:2]) if datas else "",
                                     "Fim": max(datas, key=lambda d: d[6:] + d[3:5] + d[:2]) if datas else "",
                                     "Atestado nº": "" if fora else num, "Emitido em": t.get("emissao") or "", "Peticionado em": t.get("peticionado") or "",
                                     "Autos do peticionamento": ((t.get("autos") or "") + (" (outros autos - não esta execução)" if t.get("autos_outros") else "")) if t.get("autos")
                                     else ("autos não indicados na ficha" if t.get("peticionado") and not str(t.get("peticionado")).startswith("nos autos") else ""),
                                     "Dias trabalhados / horas": t.get("trab") or "", "Remidos na ficha": "" if fora or t["rem"] in ("—", "") else _n_br(t["rem"]),
                                     "Remição no RSPE": ("%s · decisão %s" % (t["rspe"], t["decisao"])) if t["rspe"] not in ("—", "") else "",
                                     "Dias a remir": arem or "", "Estimativa": "",
                                     "Providência": ("conferir: a ficha registra o peticionamento em outros autos (%s)" % t.get("autos")) if k == "peticionado" and t.get("autos_outros") else
                                     ("conferir nos autos se foi juntado (a ficha não indica os autos) e requerer a apreciação" if k == "peticionado" and not t.get("autos") else
                                      {"peticionado": prov["nao_lancado"], "emitido": prov["emitido"], "processo_dif": prov["divergencia"]}.get(k, "")),
                                     "Trecho da ficha": t.get("texto") or ""}))
        for k in ("sem_atestado", "em_curso", "a_conferir", "estudo", "leitura", "lacunas"):
            for i in D[k]["itens"]:
                datas = re.findall(r"\d{2}/\d{2}/\d{4}", i["per"])
                out.append(dict(base, **{"_k": k, "Situação": SIT_REM[k][0], "Unidade onde ocorreu": i.get("unidade") or "",
                                         "Setor / curso / documento": i["ref"], "Início": datas[0] if datas else "",
                                         "Fim": (datas[1] if len(datas) > 1 else ("hoje (em curso)" if "em curso" in i["per"] or "ativa" in i["per"] else "")),
                                         "Atestado nº": "", "Emitido em": "", "Peticionado em": i.get("data") if k == "leitura" or "peticionado" in i["per"] else "",
                                         "Autos do peticionamento": "",
                                         "Dias trabalhados / horas": i.get("base") or "", "Remidos na ficha": "", "Remição no RSPE": "",
                                         "Dias a remir": ("(≈ %s, fora do total)" % _num(i["dias"]) if i["dias"] else "") if k in rf.FORA_DO_TOTAL else (i["dias"] or ""),
                                         "Estimativa": "≈" if i.get("estimado") and k not in rf.FORA_DO_TOTAL else "",
                                         "Providência": prov.get(k, ""), "Trecho da ficha": i.get("texto") or i["per"]}))
    return out


def _amostra(linhas, frac=0.1, semente=2026):
    """10% dos assistidos com pendência (sorteio fixo, para a mesma base dar a mesma amostra)."""
    import random
    pend = sorted({L["Nº da execução"] for L in linhas if L["_k"] not in ("processo", "processo_maior", "rspe_sem_ficha", "processo_dif")})
    n = max(1, int(round(len(pend) * frac))) if pend else 0
    sel = set(random.Random(semente).sample(pend, n)) if n else set()
    return [L for L in linhas if L["Nº da execução"] in sel]


# ---------------------------------------------------------------- prioridade das remições
PRIO_REM = {1: ("Crítica", "vermelho", "a remição já alcança o término da pena (extinção / liberdade)"),
            2: ("Muito alta", "laranja", "a remição antecipa para já a progressão ou o livramento"),
            3: ("Alta", "amarelo", "atestados prontos sem remição (dias exatos), 30 dias ou mais"),
            4: ("Média", "verde", "trabalho sem atestado (estimativa), 30 dias ou mais"),
            5: ("Baixa", "cinza", "menos de 30 dias, ou só estudo e leitura")}


def livramento_travado_por_falta(m):
    """Data do livramento do SEEU fixada pela falta grave nos últimos 12 meses (CP, art. 83, III, "b"): o SEEU imprime "(Existe
    falta grave nos últimos 12 meses em d)" e a previsão é d + 12 meses. Reconhece pelo texto ou pela coincidência da previsão
    com a falta homologada (data de referência) ou com a recaptura/interrupção de 12 meses antes. A remição não antecipa essa data."""
    r = m.get("_bruto") or {}
    if re.search(r"FALTA GRAVE NOS", rs._sem_acento(r.get("livramento_obs_seeu") or "").upper()):
        return True
    d = rs.to_date(r.get("livramento_previsao_seeu") or "") or rs.to_date(m.get("liv") or "")
    if not d:
        return False
    try:
        d0 = d.replace(year=d.year - 1)
    except ValueError:
        d0 = d - timedelta(days=365)
    datas = {rs.to_date(r.get("data_base_seeu") or "")}  # a falta também reinicia a data-base da progressão
    for i in r.get("_incidentes") or []:
        if "FALTA GRAVE" in rs._sem_acento(i.get("tipo") or "").upper() and i.get("situacao") in ("CONCEDIDO", "PENDENTE"):
            datas |= {rs.to_date(i.get(k) or "") for k in ("data_referencia", "complemento")}
    for e in r.get("_eventos") or []:
        if re.search(r"RECAPTURA|FUGA|EVAS|DESCUMPRIMENTO", rs._sem_acento((e.get("motivo") or "") + " " + (e.get("tipo") or "")).upper()):
            datas.add(rs.to_date(e.get("data") or ""))
    return d0 in datas


def prioridade_remicao(m):
    """(nível, efeito, dias exatos, estimados, educação, total) da remição a requerer de um assistido; None se não há o que remir."""
    D = m.get("fd_rem_det") or {}
    if not isinstance(D, dict) or not D:
        return None
    g = lambda k: float((D.get(k) or {}).get("dias") or 0)
    exatos = g("nao_lancado") + g("emitido") + g("divergencia")
    estim = g("sem_atestado")
    edu = g("estudo") + g("leitura")
    total = float(D.get("total") or 0)
    if total < 1:
        return None
    ativo = not m.get("estado_exec")
    alvos = []
    if m.get("ext_dias") is not None and m["ext_dias"] > 0:
        alvos.append(("término", m["ext_dias"]))
    travado = False
    if ativo:
        for k, rot in (("prog_dias", "progressão"), ("liv_dias", "livramento")):
            if m.get(k) is not None and m[k] > 0:
                if rot == "livramento" and livramento_travado_por_falta(m):
                    travado = True  # a data do livramento é a do fim da quarentena da falta grave: a remição não a antecipa
                    continue
                alvos.append((rot, m[k]))
    efeito, nivel = [], None
    for rot, d in alvos:
        fem = rot == "progressão"  # "a progressão" x "o livramento", "o término"
        if exatos >= d:
            efeito.append("%s em %d dias: os atestados prontos (%s dias) já %s alcançam" % (rot, d, _dias(exatos), "a" if fem else "o"))
        elif total >= d:
            efeito.append("%s em %d dias: %s com a estimativa (%s dias), se confirmado o trabalho" % (rot, d, "alcançada" if fem else "alcançado", _dias(total)))
        else:
            continue
        nivel = min(nivel or 9, 1 if rot == "término" else 2)
    if nivel is None:
        nivel = 3 if exatos >= 30 else 4 if estim >= 30 else 5
        prox = min(alvos, key=lambda x: x[1]) if alvos else None
        if prox:
            efeito.append("antecipa a %s (em %d dias) em até %s dias" % (prox[0], prox[1], _dias(total)))
    if travado:
        efeito.append("livramento (em %d dias) travado pela falta grave nos últimos 12 meses: a remição não o antecipa" % m["liv_dias"])
    certo = any("atestados prontos" in e for e in efeito) or (nivel == 3)
    return nivel, "; ".join(efeito), exatos, estim, edu, total, certo


def relatorio_prioridade_remicao(modelos, caminho, nome_base):
    """PDF: assistidos com remição a requerer, do mais grave ao mais simples (efeito sobre término, progressão e livramento;
    depois o volume de dias exatos e estimados)."""
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    st = _estilos()
    st["h2"].keepWithNext = 1
    W = landscape(A4)[0] - 28 * mm
    linhas, fora = [], []
    for m in modelos:
        p = prioridade_remicao(m)
        if not p:
            continue
        if m.get("estado_exec") == "extinta" or "ARQUIV" in (m.get("status_exec") or ""):
            fora.append((m, p))
        else:
            linhas.append((m, p))
    linhas.sort(key=lambda x: (x[1][0], 0 if x[1][6] else 1, -x[1][5], rs._sem_acento(x[0].get("nome") or "").upper()))
    cont = Counter(p[0] for _, p in linhas)
    el = [Paragraph("Prioridade das remições", st["tit"]),
          Paragraph(_t("%s · %s com remição a requerer, do mais grave ao mais simples · gerado em %s" % (
              nome_base, rs.pl(len(linhas), "assistido", "assistidos"), datetime.now().strftime("%d/%m/%Y %H:%M"))), st["sub"]), Spacer(1, 8)]
    dados = [["Nível", "Critério", "Assistidos", "Dias a remir"]]
    for n, (rot, cor, crit) in PRIO_REM.items():
        dados.append([_pilula("%d · %s" % (n, rot), cor, st), crit, str(cont.get(n, 0)),
                      _dias(sum(p[5] for _, p in linhas if p[0] == n))])
    el.append(_tabela(dados, [32 * mm, W - 92 * mm, 26 * mm, 34 * mm], st))
    el.append(Spacer(1, 4))
    el.append(Paragraph(_t("Dias exatos: atestados peticionados ou emitidos sem remição no RSPE (e a diferença de remição menor). Estimativa: "
                           "trabalho sem atestado na ficha (seg.-sáb. ÷ 3). Educação: estudo e leitura. A remição conta como pena cumprida (LEP, "
                           "art. 128): os dias a remir reduzem o tempo até o término e até os benefícios. Dentro de cada nível, o maior volume "
                           "de dias vem primeiro. Conferir nos autos (SEEU) antes do pedido."), st["mut"]))
    for n, (rot, cor, crit) in PRIO_REM.items():
        L = [(m, p) for m, p in linhas if p[0] == n]
        if not L:
            continue
        el.append(Paragraph("%d · %s - %s (%s)" % (n, rot, crit, rs.pl(len(L), "assistido", "assistidos")), st["h2"]))
        dados = [["Assistido", "Execução", "Regime", "Exatos", "Estimativa", "Educação", "Total", "Efeito sobre os prazos"]]
        for m, p in L:
            dados.append([Paragraph(_t(nome_rel(m)), st["neg"]), Paragraph(_t(m.get("proc") or m.get("id") or ""), st["cel"]),
                          m.get("regime") or "—", _dias(p[2]) if p[2] else "—", ("≈ " + _dias(p[3])) if p[3] else "—",
                          ("≈ " + _dias(p[4])) if p[4] else "—", _dias(p[5]), Paragraph(_t(p[1] or "—"), st["cel"])])
        el.append(_tabela(dados, [46 * mm, 49 * mm, 18 * mm, 15 * mm, 21 * mm, 20 * mm, 15 * mm, W - 184 * mm], st,
                          cores_linha={i + 1: cor for i in range(len(L))}))
    if fora:
        el.append(Paragraph("Execução extinta ou arquivada no SEEU (%s)" % rs.pl(len(fora), "assistido", "assistidos"), st["h2"]))
        el.append(Paragraph(_t("A remição deve ser pedida no processo em que a pena está em execução (transferência, unificação ou nova guia) - "
                               "conferir no SEEU."), st["mut"]))
        dados = [["Assistido", "Execução", "Situação", "Total"]]
        for m, p in sorted(fora, key=lambda x: -x[1][5]):
            dados.append([Paragraph(_t(nome_rel(m)), st["neg"]), m.get("proc") or "", (m.get("status_exec") or "").title(), _dias(p[5])])
        el.append(_tabela(dados, [90 * mm, 50 * mm, 50 * mm, W - 190 * mm], st))
    doc = SimpleDocTemplate(caminho, pagesize=landscape(A4), leftMargin=14 * mm, rightMargin=14 * mm, topMargin=21 * mm, bottomMargin=16 * mm,
                            title="Prioridade das remições", author="APTO")
    fr = _moldura("Prioridade das remições", nome_base, rodape="Triagem pela ficha disciplinar e pelo RSPE: atestados com dias exatos; "
                  "trabalho sem atestado e estudo, estimativa. Conferir nos autos (SEEU) antes do pedido.", pagina=landscape(A4))
    doc.build(el, onFirstPage=fr, onLaterPages=fr, canvasmaker=_canvas_numerado())


def planilha_remicao_xlsx(modelos, caminho, nome_base):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    L = linhas_conferencia(modelos)
    wb = Workbook()
    neg, cab_fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="00602C")
    larg = {"Assistido": 30, "Nº da execução": 26, "Unidade atual": 28, "Situação": 30, "Unidade onde ocorreu": 32, "Setor / curso / documento": 28,
            "Início": 11, "Fim": 14, "Atestado nº": 13, "Emitido em": 11, "Peticionado em": 13, "Autos do peticionamento": 30, "Dias trabalhados / horas": 26, "Remidos na ficha": 10,
            "Remição no RSPE": 24, "Dias a remir": 10, "Estimativa": 9, "Providência": 40, "Trecho da ficha": 90}

    def aba(ws, linhas, extra=()):
        cols = COLS_REM + list(extra)
        ws.append(cols)
        for c in range(1, len(cols) + 1):
            x = ws.cell(row=1, column=c)
            x.font, x.fill, x.alignment = neg, cab_fill, Alignment(wrap_text=True, vertical="top")
        for Ln in linhas:
            ws.append([Ln.get(c, "") for c in COLS_REM] + ["" for _ in extra])
            cor = SIT_REM[Ln["_k"]][2]
            ws.cell(row=ws.max_row, column=4).fill = PatternFill("solid", fgColor=cor)
        for i, c in enumerate(cols, 1):
            ws.column_dimensions[get_column_letter(i)].width = larg.get(c, 16)
        ws.freeze_panes = "B2"
        ws.auto_filter.ref = "A1:%s%d" % (get_column_letter(len(cols)), max(1, ws.max_row))

    # resumo
    ws = wb.active
    ws.title = "Resumo"
    ws.append(["Conferência da remição - %s" % nome_base])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append(["Fontes: ficha disciplinar (SIAPEN) e RSPE (SEEU). Gerado em %s. Uma linha por atestado ou período; a coluna "
               "\"Trecho da ficha\" traz o lançamento que a comprova." % datetime.now().strftime("%d/%m/%Y %H:%M")])
    ws.append([])
    ws.append(["Situação", "Linhas", "Assistidos", "Dias a remir"])
    for c in range(1, 5):
        ws.cell(row=ws.max_row, column=c).font, ws.cell(row=ws.max_row, column=c).fill = neg, cab_fill
    O = remicao_por_origem(modelos)  # o mesmo total do relatório: dias simultâneos contam uma vez
    chave = {"peticionado": "nao_lancado", "emitido": "emitido", "processo_dif": "divergencia", "sem_atestado": "sem_atestado", "estudo": "estudo",
             "leitura": "leitura", "em_curso": "em_curso", "a_conferir": "a_conferir"}
    for k, (rot, _c, cor) in SIT_REM.items():
        ls = [x for x in L if x["_k"] == k]
        d = round(O["dias"][chave[k]], 2) if k in chave else 0
        ws.append([rot, len(ls), len({x["Nº da execução"] for x in ls}), ("(%s, fora do total)" % _num(d)) if k in ("em_curso", "a_conferir") else d])
        ws.cell(row=ws.max_row, column=1).fill = PatternFill("solid", fgColor=cor)
    ws.append(["Total a remir", "", O["ass"], round(O["total"], 2)])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    ws.append(["Períodos simultâneos (dois setores no mesmo dia) contam uma vez no total; por isso a soma das linhas da aba Conferência pode ser maior. "
               "No trabalho sem atestado, cada linha arredonda o seu período (÷ 3) e os trechos de 1 ou 2 dias no corte de uma transferência "
               "só entram no total da unidade: a soma das linhas pode ficar um pouco abaixo do total."])
    ws.append(["As linhas e os itens são os mesmos do relatório \"Remição detalhada\": atestado lançado na ficha sem os dias e atestado cujo "
               "período já foi remido entram com 0 dias (para conferir), e \"No processo, remição igual ou maior\" não tem dias a remir."])
    ws.append([])
    ws.append(["Unidade onde ocorreu", "Assistidos com pendência", "Dias a remir (sem em curso e a conferir)"])
    for c in range(1, 4):
        ws.cell(row=ws.max_row, column=c).font, ws.cell(row=ws.max_row, column=c).fill = neg, cab_fill
    import rspe_ficha as rf
    por = {}
    for m in modelos:
        D = m.get("fd_rem_det") if m.get("ficha_tem") else None
        for k in [k for k, _r, _p in rf.ORIGENS_REMICAO if k not in rf.FORA_DO_TOTAL] if D else []:
            for un, v in D[k]["por_un"].items():
                if v:
                    u = por.setdefault(un, [set(), 0])
                    u[0].add(m.get("id"))
                    u[1] += v
    for u, (a, d) in sorted(por.items(), key=lambda kv: -kv[1][1]):
        ws.append([u, len(a), round(d, 2)])
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width, ws.column_dimensions["C"].width, ws.column_dimensions["D"].width = 60, 16, 22, 14
    aba(wb.create_sheet("Conferência"), L)
    # amostra: a equipe marca se conferiu, se confere e, quando não, o motivo padronizado - a aba "Taxa de acerto" calcula sozinha
    am = wb.create_sheet("Amostra 10%")
    extra = ("Conferido nos autos (S/N)", "Resultado", "Motivo da divergência", "Observação")
    aba(am, _amostra(L), extra)
    from openpyxl.worksheet.datavalidation import DataValidation
    n0 = len(COLS_REM)
    cS, cR, cM = (get_column_letter(n0 + i) for i in (1, 2, 3))
    ult = max(2, am.max_row)
    ls = wb.create_sheet("Listas")  # opções das listas de seleção (o Excel limita a lista digitada a 255 caracteres)
    for mv in MOTIVOS_DIVERGENCIA:
        ls.append([mv])
    ls.sheet_state = "hidden"
    for col, lista in ((cS, '"S,N"'), (cR, '"Confere,Não confere"'), (cM, "Listas!$A$1:$A$%d" % len(MOTIVOS_DIVERGENCIA))):
        dv = DataValidation(type="list", formula1=lista, allow_blank=True)
        am.add_data_validation(dv)
        dv.add("%s2:%s%d" % (col, col, ult + 200))
    for i, c in enumerate(extra, 1):
        am.column_dimensions[get_column_letter(n0 + i)].width = (40 if c.startswith("Motivo") else 30 if c == "Observação" else 16)
    tx = wb.create_sheet("Taxa de acerto")
    tx.append(["Taxa de acerto da ferramenta na amostra (preenchida pela equipe na aba \"Amostra 10%\")"])
    tx["A1"].font = Font(bold=True, size=12)
    tx.append(["A amostra foi sorteada entre assistidos com pendência: mede se o que a ferramenta aponta está certo (precisão), não se ela deixa casos de fora."])
    tx.append([])
    tx.append(["Situação apontada", "Linhas na amostra", "Conferidas (S)", "Confere", "Não confere", "Taxa de acerto"])
    for c in range(1, 7):
        tx.cell(row=tx.max_row, column=c).font, tx.cell(row=tx.max_row, column=c).fill = neg, cab_fill
    rng = lambda col: "'Amostra 10%%'!$%s$2:$%s$%d" % (col, col, ult + 200)
    for k, (rot, _c, cor) in SIT_REM.items():
        r_ = tx.max_row + 1
        tx.append([rot, '=COUNTIF(%s,A%d)' % (rng("D"), r_), '=COUNTIFS(%s,A%d,%s,"S")' % (rng("D"), r_, rng(cS)),
                   '=COUNTIFS(%s,A%d,%s,"Confere")' % (rng("D"), r_, rng(cR)), '=COUNTIFS(%s,A%d,%s,"Não confere")' % (rng("D"), r_, rng(cR)),
                   '=IF((D%d+E%d)>0,D%d/(D%d+E%d),"")' % (r_, r_, r_, r_, r_)])
        tx.cell(row=r_, column=1).fill = PatternFill("solid", fgColor=cor)
        tx.cell(row=r_, column=6).number_format = "0.0%"
    r_ = tx.max_row + 1
    tx.append(["Total", "=SUM(B5:B%d)" % (r_ - 1), "=SUM(C5:C%d)" % (r_ - 1), "=SUM(D5:D%d)" % (r_ - 1), "=SUM(E5:E%d)" % (r_ - 1),
               '=IF((D%d+E%d)>0,D%d/(D%d+E%d),"")' % (r_, r_, r_, r_, r_)])
    tx.cell(row=r_, column=1).font = Font(bold=True)
    tx.cell(row=r_, column=6).number_format = "0.0%"
    tx.append([])
    tx.append(["Motivo da divergência", "Ocorrências"])
    for c in range(1, 3):
        tx.cell(row=tx.max_row, column=c).font, tx.cell(row=tx.max_row, column=c).fill = neg, cab_fill
    for mv in MOTIVOS_DIVERGENCIA:
        r_ = tx.max_row + 1
        tx.append([mv, '=COUNTIF(%s,A%d)' % (rng(cM), r_)])
    tx.column_dimensions["A"].width, tx.column_dimensions["F"].width = 58, 14
    for c in "BCDE":
        tx.column_dimensions[c].width = 16
    lg = wb.create_sheet("Legenda")
    for k, (rot, _c, cor) in SIT_REM.items():
        lg.append([rot])
        lg.cell(row=lg.max_row, column=1).fill = PatternFill("solid", fgColor=cor)
    lg.append([])
    for t in ("Atestado: dias exatos do documento. \"≈\" = estimativa do programa (trabalho sem atestado: dias seg.-sáb., sem feriados, ÷ 3; estudo: 12 h = 1 dia).",
              "\"A conferir\": vínculo ou matrícula sem baixa na ficha e com registro posterior que indica que terminou - não entra no total.",
              "\"Emitido, sem peticionamento na ficha\": a ficha registra só a emissão; a juntada se confere nos autos.",
              "Amostra 10%: assistidos sorteados entre os que têm pendência (sorteio fixo), para conferência nos autos. Preencha S/N, Resultado e, quando "
              "não confere, o Motivo (listas de seleção); a aba \"Taxa de acerto\" calcula sozinha o acerto por situação e conta os motivos.",
              "A amostra mede se o que a ferramenta aponta está certo (precisão); não mede o que ela deixa de fora.",
              "Atestado juntado no SEEU e não lançado na ficha não é visto pelo programa: lance-o em \"+ Adicionar atestado\" na aba Ficha e gere de novo."):
        lg.append([t])
    lg.column_dimensions["A"].width = 140
    wb.save(caminho)
    return caminho


def planilha_remicao_pdf(modelos, caminho, nome_base):
    """A mesma planilha em PDF (paisagem): por assistido, cada linha com a situação em cor e o trecho da ficha."""
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether
    st = _estilos()
    PG = landscape(A4)
    W = PG[0] - 24 * mm
    L = linhas_conferencia(modelos)
    peq = ParagraphStyle("pq", parent=st["cel"], fontSize=7, leading=8.8)
    tr = ParagraphStyle("tr", parent=peq, fontSize=6.3, leading=7.6, textColor=st["C"](TX3))
    dir_ = ParagraphStyle("pqd", parent=peq, alignment=2)
    el = [Paragraph("Conferência da remição", st["tit"]),
          Paragraph(_t("%s · ficha disciplinar (SIAPEN) x RSPE (SEEU) · %d linhas · gerado em %s" % (nome_base, len(L), datetime.now().strftime("%d/%m/%Y %H:%M"))), st["sub"]),
          Spacer(1, 6),
          Paragraph(_t("Cores: " + " · ".join(v[0] for v in SIT_REM.values()) + ". \"≈\" = estimativa do programa. A última coluna traz o lançamento da ficha."), st["mut"])]
    cols = ["Situação", "Unidade onde ocorreu", "Setor / curso / documento", "Início", "Fim", "Atestado nº", "Peticionado em", "Remidos na ficha",
            "Remição no RSPE", "Dias a remir", "Trecho da ficha"]
    larg = [32 * mm, 30 * mm, 28 * mm, 20 * mm, 20 * mm, 17 * mm, 20 * mm, 14 * mm, 26 * mm, 17 * mm]
    larg.append(W - sum(larg))
    atual, grupo = None, []

    def fecha():
        if not grupo:
            return
        g0 = grupo[0]
        tit = Paragraph("<b>%s</b> · %s · %s" % (_t(g0["Assistido"]), _t(g0["Nº da execução"]), _t(g0["Unidade atual"])),
                        ParagraphStyle("pt", parent=st["cel"], fontSize=8.2, leading=11))
        dados = [cols]
        cores = {}
        for x in grupo:
            dados.append([_pilula(x["Situação"], SIT_REM[x["_k"]][1], st)] + [Paragraph(_t(str(x[c])), peq) for c in cols[1:7]] +
                         [Paragraph(_t(_num(x["Remidos na ficha"]) if x["Remidos na ficha"] != "" else ""), dir_), Paragraph(_t(x["Remição no RSPE"]), peq),
                          Paragraph(_t((x["Estimativa"] + " " if x["Estimativa"] else "") + (_num(x["Dias a remir"]) if isinstance(x["Dias a remir"], (int, float)) else str(x["Dias a remir"]))), dir_),
                          Paragraph(_t(str(x["Trecho da ficha"])[:260]), tr)])
            cores[len(dados) - 1] = SIT_REM[x["_k"]][1]
        el.append(KeepTogether([Spacer(1, 7), tit, Spacer(1, 2), _tabela(dados[:4], larg, st, zebra=False, cores_linha={k: v for k, v in cores.items() if k < 4}, pad=4)]))
        if len(dados) > 4:
            el.append(_tabela([dados[0]] + dados[4:], larg, st, zebra=False, cores_linha={k - 3: v for k, v in cores.items() if k >= 4}, pad=4))
    for x in L:
        if x["Nº da execução"] != atual:
            fecha()
            atual, grupo = x["Nº da execução"], []
        grupo.append(x)
    fecha()
    doc = SimpleDocTemplate(caminho, pagesize=PG, leftMargin=12 * mm, rightMargin=12 * mm, topMargin=21 * mm, bottomMargin=18 * mm,
                            title="Conferência da remição", author="APTO")
    fr = _moldura("Conferência da remição", nome_base, "Ficha disciplinar (SIAPEN) x RSPE (SEEU): atestados com dias exatos; \"≈\" = estimativa. "
                  "Conferir nos autos antes do pedido.", pagina=PG)
    doc.build(el, onFirstPage=fr, onLaterPages=fr, canvasmaker=_canvas_numerado())
    return caminho


# ---------------------------------------------------------------- relatório de providências
TIPOS_PROV = [("Pedido nos autos", "#00602C", "pedidos nos autos"), ("Ofício à unidade prisional", "#5B7C9C", "ofícios à unidade prisional"),
              ("Outra providência", "#AEB5B0", "outras providências")]
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
                            title=titulo, author="APTO")
    fr = _moldura("Relatório de providências", nome_base, rodape="Providências registradas no APTO (coluna Pedido). Conferir nos autos e no SAP.")
    doc.build(el, onFirstPage=fr, onLaterPages=fr, canvasmaker=_canvas_numerado())
    return caminho



def relatorio_falhas(d, caminho, nome_base):
    """PDF do registro da importação: resumo do lote, falhas (o que não entrou, o que não foi lido, o que não pôde ser analisado,
    com a causa) e o registro completo, arquivo a arquivo (resultado, leitura completa ou parcial e o que pode ter ocorrido)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    st = _estilos()
    W = A4[0] - 32 * mm
    reg = d.get("registro") or []
    el = [Paragraph(_t("Registro da importação"), st["tit"]),
          Paragraph(_t("%s · lote importado em %s · %s lidos" % (nome_base, d.get("quando", ""), rs.pl(d.get("arquivos", 0), "arquivo", "arquivos"))), st["sub"]),
          Spacer(1, 8)]
    n_pes = sum(len(p["itens"]) for p in d["pessoas"])
    faltam = d.get("faltam") or []
    if reg:
        cr = Counter(x["resultado"] for x in reg)
        cl = Counter(x["leitura"] for x in reg)
        el.append(_tabela([["Arquivos", "RSPE", "Fichas", "Leitura completa", "Leitura parcial", "Não lidos"],
                           [str(len(reg)), str(sum(1 for x in reg if x["tipo"] == "RSPE")), str(sum(1 for x in reg if x["tipo"] == "Ficha")),
                            str(cl.get("completa", 0)), str(cl.get("parcial", 0)), str(cl.get("falhou", 0))]], [W / 6] * 6, st, zebra=False))
        el.append(Spacer(1, 4))
        el.append(Paragraph(_t("Resultado: " + " · ".join("%s %d" % (k, v) for k, v in cr.most_common())), st["mut"]))
        el.append(Spacer(1, 6))
    el.append(_tabela([["Arquivos não importados", "Assistidos com dado não lido", "Ignorados", "Falhas na análise"],
                       [str(len(d["erros"])), str(len(faltam)), str(len(d["ignorados"])), str(n_pes)]],
                      [W / 4] * 4, st, zebra=False))
    if faltam:
        cont = Counter(c for x in faltam for c in x["campos"])
        el.append(Spacer(1, 4))
        el.append(Paragraph(_t("Dados não lidos, por campo: " + " · ".join("%s %d" % (k, v) for k, v in cont.most_common())), st["mut"]))

    def causa_arquivo(msg):
        u = msg.upper()
        if "NÃO PARECE UM RSPE" in u or "NÃO É UM RSPE" in u:
            return "O PDF não tem o cabeçalho do RSPE do SEEU nem o da Ficha Disciplinar do SIAPEN (outro documento, digitalização ou PDF protegido)."
        if "NÚMERO DA EXECUÇÃO" in u:
            return "A 1ª página falta ou o número do processo de execução está ilegível: gerar o RSPE de novo no SEEU."
        if "PASSWORD" in u or "ENCRYPT" in u or "SENHA" in u:
            return "PDF protegido por senha."
        # a mensagem já chega traduzida (rspe_app._msg_erro_pdf); os termos em inglês ficam para mensagens não traduzidas
        if "CORROMPIDO" in u or "INCOMPLETO" in u or "EOF" in u or "PDFSYNTAX" in u or "STARTXREF" in u:
            return "Arquivo corrompido ou baixado pela metade: baixar ou gerar o PDF de novo."
        if "NÃO É PDF VÁLIDO" in u or "ROOT OBJECT" in u or "REALLY A PDF" in u:
            return "O arquivo não é um PDF válido (vazio ou de outro tipo com a extensão .pdf): gerar o PDF de novo no SEEU."
        if "SEM PERMISSÃO" in u or "PERMISSION" in u:
            return "Arquivo aberto em outro programa ou sem permissão de leitura: fechar o programa e importar de novo."
        if "NÃO ENCONTRADO" in u:
            return "O arquivo foi movido ou apagado durante a importação: importar de novo."
        if "SEM TEXTO" in u:
            return "PDF digitalizado (imagem, sem texto): gerar o PDF direto do SEEU/SIAPEN, não escaneado."
        if "FICHA DISCIPLINAR" in u and "FALHA NA LEITURA" in u:
            return "Ficha disciplinar com falha na leitura: enviar o PDF para correção."
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
    n_sec = 5 if d["ignorados"] else 4
    LEIT = {"completa": "ok", "parcial": "PARCIAL", "falhou": "NÃO LIDO"}

    def linhas(regs):
        dados = [["Arquivo", "Assistido", "Resultado", "Leitura", "Observações e causa provável"]]
        for x in regs:
            obs = list(x["obs"])
            if x["leitura"] == "falhou":
                obs = obs + [causa_arquivo(obs[0] if obs else "")]
            dados.append([Paragraph(_t(x["arquivo"]), st["cel"]),
                          Paragraph(_t(x["nome"] or "—") + ("<br/>" + _t(x["proc"]) if x["proc"] else ""), st["cel"]),
                          Paragraph(_t("%s · %s" % (x["tipo"] if x["tipo"] != "?" else "arquivo", x["resultado"])), st["cel"]),
                          LEIT.get(x["leitura"], x["leitura"]), Paragraph(_t("; ".join(obs) or "—"), st["cel"])])
        return _tabela(dados, [36 * mm, 42 * mm, 22 * mm, 20 * mm, W - 120 * mm], st)
    com_obs = [x for x in reg if x["obs"] or x["leitura"] != "completa"]
    el.append(Paragraph("%d. Leitura parcial e observações" % n_sec, st["h2"]))
    if com_obs:
        el.append(Paragraph(_t("Arquivos com algum campo ou página não lido (PARCIAL), não lidos, ou com observação sem efeito na leitura "
                               "(campo que o próprio SEEU ou SIAPEN deixa em branco, ficha à espera do RSPE)."), st["mut"]))
        el.append(Spacer(1, 4))
        el.append(linhas(sorted(com_obs, key=lambda x: ({"falhou": 0, "parcial": 1}.get(x["leitura"], 2), x["arquivo"].lower()))))
    else:
        el.append(Paragraph("Nenhum.", st["mut"]))
    el.append(Paragraph("%d. Registro completo, arquivo a arquivo" % (n_sec + 1), st["h2"]))
    if reg:
        el.append(Paragraph(_t("Leitura ok: todos os campos esperados foram lidos. PARCIAL: algum campo ou página não foi lido (a causa provável "
                               "vem ao lado). NÃO LIDO: o arquivo não entrou."), st["mut"]))
        el.append(Spacer(1, 4))
        el.append(linhas(reg))
    else:
        el.append(Paragraph("Registro por arquivo indisponível (lote importado em versão anterior do programa).", st["mut"]))
    doc = SimpleDocTemplate(caminho, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=21 * mm, bottomMargin=20 * mm,
                            title="Registro da importação", author="APTO")
    fr = _moldura("Registro da importação", nome_base, rodape="Registro da importação do lote. Enviar este PDF com os arquivos citados para a correção da leitura.")
    doc.build(el, onFirstPage=fr, onLaterPages=fr, canvasmaker=_canvas_numerado())


# --------------------------------------------------------------------------- #
# Dados prisionais de MS (Geopresídios/CNJ)
# --------------------------------------------------------------------------- #

def _geo_pop(u):
    if u.get("pop") is not None:
        return u["pop"]
    return sum((u.get(k) or 0) for k in ("provisorios", "fechado", "semiaberto", "aberto", "medida_seguranca", "prisao_civil"))


def _geo_sel(dados, cidade="", cats=None):
    """Estabelecimentos pelos tipos marcados (padrão: unidades penais) e pela cidade."""
    cats = set(cats or (["penal", "delegacia", "militar", "outra"] if dados.get("todas") else ["penal"]))
    U = [u for u in dados.get("unidades") or [] if (u.get("cat") or ("penal" if u.get("penal") else "outra")) in cats]
    return [u for u in U if u.get("cidade") == cidade] if cidade else U


def _geo_tipos(cats):
    import rspe_geopresidios as rgeo
    cats = list(cats or ["penal"])
    return ", ".join(rgeo.CATEGORIAS[c].lower() for c in rgeo.CATEGORIAS if c in cats)


def _geo_nome(n):
    import re as _re
    n = _re.sub(r"(?i)^ESTABELECIMENTO PENAL", "EP", n).title().replace("Ep ", "EP ", 1)
    return _re.sub(r"\b(De|Da|Do|Das|Dos|E|Ao|À|Em)\b", lambda m: m.group(1).lower(), n)


def _geo_mapa(U, mapa, larg, f, C, sel=""):
    """Mapa de MS: um círculo verde-escuro por cidade (tamanho pelo número de presos); municípios com estabelecimento tingidos."""
    import math
    import re as _re
    from reportlab.graphics.shapes import Drawing, Polygon, Circle, String
    P = mapa["proj"]
    esc = larg / P["W"]
    H = P["H"] * esc
    d = Drawing(P["W"] * esc, H)
    cid, com = {}, set()
    for u in U:
        if u.get("ibge"):
            com.add(u["ibge"])
        if u.get("cidade"):
            cid[u["cidade"]] = cid.get(u["cidade"], 0) + _geo_pop(u)
    pos = {m["nome"]: m["c"] for m in mapa["municipios"].values()}
    for k, m in mapa["municipios"].items():
        for anel in _re.findall(r"M([^Z]+)Z", m["d"]):
            xy = [float(v) for v in _re.findall(r"-?\d+(?:\.\d+)?", anel)]
            pts = []
            for i in range(0, len(xy) - 1, 2):
                pts += [xy[i] * esc, H - xy[i + 1] * esc]
            d.add(Polygon(pts, fillColor=C("#D5E2D9" if k in com else "#E9ECEA"), strokeColor=C("#FFFFFF"), strokeWidth=0.5))
    mx = max(list(cid.values()) + [1])
    bol = []
    for nome, pop in sorted(cid.items(), key=lambda x: -x[1]):
        if nome not in pos:
            continue
        x, y = pos[nome]
        bol.append((nome, x * esc, H - y * esc, (7 + 26 * math.sqrt(pop / mx)) * esc))
    for nome, x, y, r in bol:
        d.add(Circle(x, y, r, fillColor=C("#0B2E1C" if (sel and nome == sel) else "#1D5A3B"), strokeColor=C("#FFFFFF"), strokeWidth=0.8))
    # nomes das maiores cidades (e da escolhida): direita, esquerda, acima ou abaixo, sem cobrir outro nome nem outro círculo
    from reportlab.pdfbase.pdfmetrics import stringWidth
    caixas = []
    cruza = lambda a, b: a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]
    for i, (nome, x, y, r) in enumerate(bol):
        if i >= 9 and not (sel and nome == sel):
            continue
        w, h = stringWidth(nome, f["b"], 6.5) + 2, 8
        for bx, by, anc in ((x + r + 2, y - 3, "start"), (x - r - 2 - w, y - 3, "end"), (x - w / 2, y + r + 1.5, "middle"), (x - w / 2, y - r - 1.5 - h, "middle")):
            caixa = (bx, by, w, h)
            if bx < 0 or bx + w > P["W"] * esc or by < 0 or by + h > H:
                continue
            if any(cruza(caixa, c) for c in caixas) or any(cruza(caixa, (x2 - r2, y2 - r2, 2 * r2, 2 * r2)) for n2, x2, y2, r2 in bol if n2 != nome):
                continue
            caixas.append(caixa)
            tx = bx if anc == "start" else bx + w if anc == "end" else bx + w / 2
            d.add(String(tx, by + 2, nome, fontName=f["b"], fontSize=6.5, fillColor=C(TX), textAnchor=anc))
            break
    return d


def _geo_pizzas_unidade(u, larg, f, C):
    """Duas pizzas da última inspeção: presos por regime e provisórios x condenados."""
    from reportlab.graphics.shapes import Drawing, Rect, String
    from reportlab.graphics.charts.piecharts import Pie
    S = u.get("serie") or []
    x = S[-1] if S else ({"pop": _geo_pop(u), "provisorios": u.get("provisorios"), "fechado": u.get("fechado"), "semiaberto": u.get("semiaberto"),
                          "aberto": u.get("aberto"), "ciclo": (u.get("inspecao") or {}).get("ciclo", "")} if u.get("inspecao") else None)
    if not x or not x.get("pop"):
        return None
    fmt = lambda n: "{:,}".format(int(n or 0)).replace(",", ".")
    soma = sum((x.get(k) or 0) for k in ("provisorios", "fechado", "semiaberto", "aberto"))
    cap = u.get("capacidade") or 0
    grupos = [("Por regime", [("Provisórios", x.get("provisorios"), "#9CBFA9"), ("Fechado", x.get("fechado"), "#1D5A3B"), ("Semiaberto", x.get("semiaberto"), "#4E8C66"),
                              ("Aberto", x.get("aberto"), "#C9DDD0"), ("Outros", max(0, x["pop"] - soma), "#7C8C82")]),
              ("Provisórios", [("Provisórios", x.get("provisorios"), "#A3201D"), ("Condenados", max(0, x["pop"] - (x.get("provisorios") or 0)), "#1D5A3B")])]
    W, H = larg, 52 * 2.835
    d = Drawing(W, H)
    col = W / len(grupos)
    for gi, (tit, fat) in enumerate(grupos):
        fat = [(n, v or 0, c) for n, v, c in fat if (v or 0) > 0]
        tot = sum(v for _, v, _ in fat) or 1
        x0 = gi * col
        d.add(String(x0 + 4, H - 9, tit, fontName=f["b"], fontSize=7.5, fillColor=C(NAVY)))
        pie = Pie()
        pie.x, pie.y, pie.width, pie.height = x0 + 6, H - 82, 66, 66
        pie.data = [v for _, v, _ in fat]
        pie.labels = None
        pie.slices.strokeColor = C("#FFFFFF")
        pie.slices.strokeWidth = 0.8
        for i, (_, _, c) in enumerate(fat):
            pie.slices[i].fillColor = C(c)
        d.add(pie)
        for i, (n, v, c) in enumerate(fat):
            yy = H - 22 - i * 11
            d.add(Rect(x0 + 80, yy, 6, 6, fillColor=C(c), strokeColor=None))
            d.add(String(x0 + 89, yy + 0.5, "%s: %s (%d%%)" % (n, fmt(v), round(100 * v / tot)), fontName=f["n"], fontSize=6.5, fillColor=C(TX)))
    d.add(String(4, 4, "Inspeção de %s · %s presos%s" % (x.get("ciclo") or "", fmt(x["pop"]), (" · %s vagas" % fmt(cap)) if cap else ""),
                 fontName=f["n"], fontSize=6.5, fillColor=C("#767C82")))
    return d


def _geo_colunas_unidade(u, larg, f, C):
    """Colunas no tempo, uma por inspeção: crescimento de apenados (por regime, com a variação desde a anterior) e ocupação
    (presos nas vagas e além delas, linha das vagas e taxa de cada mês; vagas da inspeção mais recente)."""
    from reportlab.graphics.shapes import Drawing, Rect, String, Line
    S = [x for x in (u.get("serie") or []) if x.get("pop") is not None]
    if not S:
        return None
    fmt = lambda n: "{:,}".format(int(n or 0)).replace(",", ".")
    cap = u.get("capacidade") or 0
    W, H = larg, 70 * 2.835
    d = Drawing(W, H)
    larg_g = (W - 14) / 2
    yB, yT = 32, H - 40

    def grafico(x0, tit, cols, segs, linha):
        mx = max([c["tot"] for c in cols] + [linha or 0, 1]) * 1.15
        Y = lambda v: yB + (yT - yB) * v / mx
        d.add(String(x0 + 2, H - 9, tit, fontName=f["b"], fontSize=7.5, fillColor=C(NAVY)))
        lx = x0 + 2
        for n, cor in [(n, c) for k, n, c in segs if any((cc["v"].get(k) or 0) > 0 for cc in cols)] + ([("Vagas existentes", None)] if linha else []):
            if cor:
                d.add(Rect(lx, H - 21, 5.5, 5.5, fillColor=C(cor), strokeColor=None))
            else:
                d.add(Line(lx, H - 18.2, lx + 9, H - 18.2, strokeColor=C(TX), strokeWidth=0.9, strokeDashArray=[2.5, 2]))
                lx += 3.5
            d.add(String(lx + 8, H - 20.5, n, fontName=f["n"], fontSize=6.2, fillColor=C(TX)))
            lx += 8 + len(n) * 3.2 + 8
        lp = larg_g - (24 if linha else 0)
        d.add(Line(x0, yB, x0 + lp, yB, strokeColor=C("#7C8C82"), strokeWidth=0.6))
        slot = lp / len(cols)
        bw = min(34, slot * 0.58)
        for i, c in enumerate(cols):
            cx = x0 + slot * (i + 0.5)
            y = yB
            for k, n, cor in segs:
                v = c["v"].get(k) or 0
                if v <= 0:
                    continue
                h = (yT - yB) * v / mx
                d.add(Rect(cx - bw / 2, y, bw, h, fillColor=C(cor), strokeColor=C("#FFFFFF"), strokeWidth=0.6))
                y += h
            d.add(String(cx, Y(c["tot"]) + 3, fmt(c["tot"]), fontName=f["b"], fontSize=6.3, fillColor=C(TX), textAnchor="middle"))
            if c.get("topo"):
                d.add(String(cx, Y(c["tot"]) + 11, c["topo"], fontName=f["n"], fontSize=6, fillColor=C(c.get("cor") or "#4F555A"), textAnchor="middle"))
            d.add(String(cx, yB - 8, c["rot"], fontName=f["n"], fontSize=6, fillColor=C("#4F555A"), textAnchor="middle"))
        if linha:
            d.add(Line(x0, Y(linha), x0 + lp, Y(linha), strokeColor=C(TX), strokeWidth=0.9, strokeDashArray=[2.5, 2]))
            d.add(String(x0 + lp + 3, Y(linha) + 0.5, fmt(linha), fontName=f["b"], fontSize=6.3, fillColor=C(TX)))
            d.add(String(x0 + lp + 3, Y(linha) - 7, "vagas", fontName=f["n"], fontSize=6, fillColor=C(TX)))

    def rot(c):
        m = c.split("/")
        return (m[0][:3] + "/" + m[1][-2:]) if len(m) == 2 else c
    sn = lambda n: ("+" if n > 0 else "") + fmt(n)
    cols = []
    for i, x in enumerate(S):
        so = sum((x.get(k) or 0) for k in ("provisorios", "fechado", "semiaberto", "aberto"))
        dd = None if i == 0 else (x["pop"] or 0) - (S[i - 1]["pop"] or 0)
        cols.append({"rot": rot(x["ciclo"]), "tot": x["pop"] or 0, "topo": "" if dd is None else sn(dd) + " no mês", "cor": "#A3201D" if (dd or 0) > 0 else None,
                     "v": {"provisorios": x.get("provisorios"), "fechado": x.get("fechado"), "semiaberto": x.get("semiaberto"), "aberto": x.get("aberto"),
                           "outros": max(0, (x["pop"] or 0) - so)}})
    grafico(0, "Crescimento de apenados", cols,
            [("provisorios", "Provisórios", "#9CBFA9"), ("fechado", "Fechado", "#1D5A3B"), ("semiaberto", "Semiaberto", "#4E8C66"),
             ("aberto", "Aberto", "#C9DDD0"), ("outros", "Outros", "#7C8C82")], cap or None)
    cols = [{"rot": rot(x["ciclo"]), "tot": x["pop"] or 0, "topo": ("%d%%" % round(100 * (x["pop"] or 0) / cap)) if cap else "",
             "cor": "#A3201D" if cap and (x["pop"] or 0) > cap else None,
             "v": {"dentro": min(x["pop"] or 0, cap), "alem": max(0, (x["pop"] or 0) - cap)} if cap else {"dentro": x["pop"] or 0}} for x in S]
    grafico(larg_g + 14, "Ocupação", cols, [("dentro", "Nas vagas", "#1D5A3B"), ("alem", "Além das vagas", "#A3201D")], cap or None)
    if cap:
        exc = lambda x: max(0, (x["pop"] or 0) - cap)
        d.add(String(2, 9, "Acima das %s vagas existentes (linha tracejada): %s presos em %s e %s em %s." % (fmt(cap), fmt(exc(S[0])), S[0]["ciclo"], fmt(exc(S[-1])), S[-1]["ciclo"])
                     if len(S) > 1 else "Acima das %s vagas existentes (linha tracejada): %s presos." % (fmt(cap), fmt(exc(S[-1]))),
                     fontName=f["b"], fontSize=6.5, fillColor=C(TX)))
    d.add(String(2, 0, "Uma coluna por inspeção. Crescimento: acima, a variação desde a inspeção anterior. Ocupação: acima, a taxa do mês"
                 + ("; vagas da inspeção mais recente." if cap else "; capacidade não informada."),
                 fontName=f["n"], fontSize=6, fillColor=C("#767C82")))
    return d


def relatorio_prisional(dados, mapa, caminho, nome_base, cidade="", cats=None):
    """PDF do sistema prisional de MS pelo Geopresídios: indicadores, mapa (círculo por cidade: tamanho pelos presos, cor pela
    ocupação), ranking de ocupação, condições constatadas nas inspeções e evolução da população nos últimos meses."""
    import math
    import re as _re
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
    from reportlab.graphics.shapes import Drawing, Polygon, Circle, String
    import rspe_geopresidios as rgeo
    st = _estilos()
    f = _fontes()
    C = st["C"]
    W = A4[0] - 32 * mm
    U = _geo_sel(dados, cidade, cats)
    comI = [u for u in U if u.get("inspecao") or u.get("serie")]
    comCap = [u for u in comI if (u.get("capacidade") or 0) > 0]
    pop = sum(_geo_pop(u) for u in comI)
    popC, cap = sum(_geo_pop(u) for u in comCap), sum(u["capacidade"] for u in comCap)
    soma = lambda k: sum((u.get(k) or 0) for u in comI)
    fmt = lambda n: "—" if n is None else "{:,}".format(int(n)).replace(",", ".")
    pct = lambda o: "—" if o is None else "%d%%" % round(o * 100)
    cor_oc = lambda o: "#9AA0A6" if o is None else "#A3201D" if o >= 1.5 else "#C2620A" if o >= 1.0 else "#2B8048"
    titulo = "Sistema prisional de Mato Grosso do Sul" + (" · %s" % cidade if cidade else "")
    el = [Paragraph(_t(titulo), st["tit"]),
          Paragraph(_t("Geopresídios/CNIEP (CNJ): inspeções judiciais mensais de cada unidade · dados baixados em %s · %d unidades%s"
                       % (dados.get("atualizado", "?"), len(U), " (%s)" % _geo_tipos(cats))), st["sub"]),
          Spacer(1, 8)]
    nums = [(fmt(pop), "pessoas presas"), (fmt(cap), "vagas"), (pct(popC / cap if cap else None), "taxa de ocupação"),
            (fmt(max(0, popC - cap)), "déficit de vagas"), (fmt(soma("provisorios")), "provisórios")]
    cel = [[Paragraph(_t(n), st["num"]) for n, _ in nums], [Paragraph(_t(r), st["rot"]) for _, r in nums]]
    tb = Table(cel, colWidths=[W / len(nums)] * len(nums))
    tb.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, C(LINE)), ("INNERGRID", (0, 0), (-1, -1), 0.6, C(LINE)),
                            ("BACKGROUND", (0, 0), (-1, -1), C(ZEBRA)), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                            ("TOPPADDING", (0, 0), (-1, 0), 7), ("BOTTOMPADDING", (0, 1), (-1, 1), 7), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    el += [tb, Paragraph(_t("Regimes: fechado %s · semiaberto %s · aberto %s. A população é a da inspeção mais recente de cada unidade; a capacidade, "
                            "a do tema \"Aspectos gerais\". Unidades sem capacidade informada ficam fora da taxa." % (fmt(soma("fechado")), fmt(soma("semiaberto")), fmt(soma("aberto")))), st["mut"])]
    # mapa
    if mapa:
        el += [Paragraph("Mapa", st["h2"]), _geo_mapa(U if not cidade else _geo_sel(dados, "", cats), mapa, min(W, 120 * mm), f, C, cidade),
               Paragraph(_t("Cada círculo é uma cidade, com o tamanho pelo número de presos%s." % (" (%s em destaque)" % cidade if cidade else "")), st["mut"])]
    # ranking
    from reportlab.lib.styles import ParagraphStyle
    peq = ParagraphStyle("geo_peq", parent=st["cel"], fontSize=7.4, leading=9.6)
    cabp = ParagraphStyle("geo_cab", parent=st["cab"], fontSize=7.4, leading=9.6)

    L = sorted(comI, key=lambda u: -((_geo_pop(u) / u["capacidade"]) if (u.get("capacidade") or 0) > 0 else -1))
    linhas = [["Unidade", "Cidade", "Vagas", "Presos", "Ocupação", "Provis.", "Fechado", "Semiab.", "Aberto", "Dados de"]]
    for u in L:
        oc = _geo_pop(u) / u["capacidade"] if (u.get("capacidade") or 0) > 0 else None
        linhas.append([_geo_nome(u["nome"]), u.get("cidade") or "", fmt(u.get("capacidade")), fmt(_geo_pop(u)),
                       '<font color="%s"><b>%s</b></font>' % (cor_oc(oc), pct(oc)), fmt(u.get("provisorios")), fmt(u.get("fechado")),
                       fmt(u.get("semiaberto")), fmt(u.get("aberto")), u.get("pop_ciclo") or (u.get("inspecao") or {}).get("ciclo", "")])
    linhas = [[Paragraph(_t(c) if not c.startswith("<font") else c, cabp if i == 0 else peq) for c in l] for i, l in enumerate(linhas)]
    el += [Paragraph("Ocupação por unidade", st["h2"]),
           _tabela(linhas, [46 * mm, 23 * mm, 11 * mm, 12 * mm, 14 * mm, 12 * mm, 13 * mm, 13 * mm, 11 * mm, W - 155 * mm], st, pad=4)]
    # condições constatadas nas inspeções
    linhas = [["Constatação nas inspeções", "Unidades", "Tema"]]
    for ch, t, q, rot, ruim in rgeo.INDICADORES:
        if not ruim:
            continue
        com = [u for u in comI if ch in ((u.get("temas") or {}).get(str(t)) or {}).get("ind", {})]
        ruins = [u for u in com if u["temas"][str(t)]["ind"][ch].get("ruim")]
        if ruins:
            linhas.append([rgeo.PROBLEMA.get(ch, rot), "%d de %d" % (len(ruins), len(com)), rgeo.TEMAS[t]])
    if len(linhas) > 1:
        linhas = [linhas[0]] + sorted(linhas[1:], key=lambda l: -int(l[1].split()[0]))
        el += [Paragraph("Condições constatadas", st["h2"]), _tabela(linhas, [W - 70 * mm, 22 * mm, 48 * mm], st),
               Paragraph(_t("Pela última inspeção de cada tema (rodízio mensal), nas unidades que responderam à questão."), st["mut"])]
    # evolução: soma por ciclo de inspeção, só nos ciclos em que ao menos 80% das unidades informaram
    ciclos = {}
    for u in comI:
        for s_ in u.get("serie") or []:
            ciclos.setdefault(s_["ciclo"], {})[u["id"]] = s_["pop"]
    bons = sorted([c for c, v in ciclos.items() if len(v) >= 0.8 * len(comI)], key=rgeo.ordem_ciclo)
    if len(bons) >= 2:
        linhas = [["Ciclo da inspeção", "Unidades com dado", "Presos (soma)"]]
        for c in bons:
            linhas.append([c, str(len(ciclos[c])), fmt(sum(ciclos[c].values()))])
        ids = set(ciclos[bons[0]]) & set(ciclos[bons[-1]])
        a, b = sum(ciclos[bons[0]][i] for i in ids), sum(ciclos[bons[-1]][i] for i in ids)
        el += [KeepTogether([Paragraph("Evolução da população", st["h2"]), _tabela(linhas, [50 * mm, 40 * mm, 40 * mm], st),
                             Paragraph(_t("Nas %d unidades com dado nos dois ciclos: de %s presos em %s para %s em %s (%s%d%%)."
                                          % (len(ids), fmt(a), bons[0], fmt(b), bons[-1], "+" if b >= a else "", round(100 * (b - a) / a) if a else 0)), st["mut"])])]
    doc = SimpleDocTemplate(caminho, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=21 * mm, bottomMargin=20 * mm,
                            title=titulo, author="APTO")
    fr = _moldura("Dados prisionais de MS", nome_base, rodape="Fonte: Geopresídios/CNIEP (CNJ), geopresidios.cnj.jus.br. Dados declarados nas inspeções judiciais mensais.")
    doc.build(el, onFirstPage=fr, onLaterPages=fr, canvasmaker=_canvas_numerado())
    return caminho


def relatorio_condicoes_prisional(dados, caminho, nome_base, cidade="", cats=None):
    """PDF das condições constatadas nas inspeções: para cada problema, as unidades em que foi constatado (com o ciclo da
    inspeção); depois, cada unidade com a lista dos seus problemas."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether
    import rspe_geopresidios as rgeo
    st = _estilos()
    W = A4[0] - 32 * mm
    peq = ParagraphStyle("geo_peq2", parent=st["cel"], fontSize=7.6, leading=9.8)
    U = [u for u in _geo_sel(dados, cidade, cats) if u.get("temas")]
    titulo = "Condições constatadas nas inspeções" + (" · %s" % cidade if cidade else "")
    el = [Paragraph(_t(titulo), st["tit"]),
          Paragraph(_t("Geopresídios/CNIEP (CNJ), última inspeção judicial de cada tema · dados baixados em %s · %d estabelecimentos com inspeção (%s)"
                       % (dados.get("atualizado", "?"), len(U), _geo_tipos(cats))), st["sub"]), Spacer(1, 6)]
    probs = []
    for ch, t, q, rot, ruim in rgeo.INDICADORES:
        if not ruim:
            continue
        com = [u for u in U if ch in ((u["temas"].get(str(t)) or {}).get("ind") or {})]
        ruins = [u for u in com if u["temas"][str(t)]["ind"][ch].get("ruim")]
        if ruins:
            probs.append((ch, t, rot, com, ruins))
    probs.sort(key=lambda x: -len(x[4]) / len(x[3]))
    if not probs:
        el.append(Paragraph("Nenhum problema constatado nos indicadores acompanhados.", st["mut"]))
    el.append(Paragraph("Por constatação", st["h2"]))
    for ch, t, rot, com, ruins in probs:
        linhas = [["Unidade", "Cidade", "Resposta", "Inspeção"]]
        for u in sorted(ruins, key=lambda x: (x.get("cidade") or "", x["nome"])):
            T = u["temas"][str(t)]
            linhas.append([Paragraph(_t(_geo_nome(u["nome"])), peq), Paragraph(_t(u.get("cidade") or ""), peq),
                           Paragraph(_t(T["ind"][ch]["v"]), peq), Paragraph(_t(T.get("ciclo") or ""), peq)])
        tab = _tabela(linhas, [72 * mm, 32 * mm, W - 128 * mm, 24 * mm], st, pad=4)
        cab = [Paragraph(_t("%s · %d de %d estabelecimentos" % (rgeo.PROBLEMA.get(ch, rot), len(ruins), len(com))), st["neg"]),
               Paragraph(_t(rgeo.TEMAS[t]), st["mut"])]
        # tabela curta fica inteira com o título; a longa quebra entre páginas (o cabeçalho se repete)
        el += ([KeepTogether(cab + [tab])] if len(linhas) <= 12 else cab + [tab]) + [Spacer(1, 8)]
    el.append(Paragraph("Por estabelecimento", st["h2"]))
    linhas = [["Estabelecimento", "Cidade", "Constatações"]]
    for u in sorted(U, key=lambda x: -sum(1 for p in probs if x in p[4])):
        ps = [rgeo.PROBLEMA.get(p[0], p[2]) for p in probs if u in p[4]]
        linhas.append([Paragraph(_t(_geo_nome(u["nome"])), peq), Paragraph(_t(u.get("cidade") or ""), peq),
                       Paragraph(_t(("%d: " % len(ps) + "; ".join(ps)) if ps else "nenhuma"), peq)])
    el.append(_tabela(linhas, [62 * mm, 28 * mm, W - 90 * mm], st, pad=4))
    el.append(Paragraph(_t("Constatação = resposta do formulário de inspeção que indica o problema (ex.: \"Não\" em \"Cinco refeições diárias\"). "
                           "Pela última inspeção de cada tema (rodízio mensal: habitabilidade, assistências, segurança e saúde)."), st["mut"]))
    doc = SimpleDocTemplate(caminho, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=21 * mm, bottomMargin=20 * mm,
                            title=titulo, author="APTO")
    fr = _moldura("Condições por unidade", nome_base, rodape="Fonte: Geopresídios/CNIEP (CNJ), geopresidios.cnj.jus.br. Dados declarados nas inspeções judiciais mensais.")
    doc.build(el, onFirstPage=fr, onLaterPages=fr, canvasmaker=_canvas_numerado())
    return caminho


def relatorio_unidade_prisional(u, atualizado, assistidos, caminho, nome_base):
    """PDF de uma unidade: identificação, ocupação, situação e perfil, servidores, condições por tema (todas as respostas
    acompanhadas), evolução da população e os assistidos da base custodiados nela."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
    import rspe_geopresidios as rgeo
    st = _estilos()
    C = st["C"]
    W = A4[0] - 32 * mm
    peq = ParagraphStyle("geo_peq3", parent=st["cel"], fontSize=8, leading=10.4)
    fmt = lambda n: "—" if n is None else "{:,}".format(int(n)).replace(",", ".")
    pop = _geo_pop(u)
    oc = pop / u["capacidade"] if (u.get("capacidade") or 0) > 0 else None
    titulo = _geo_nome(u["nome"])
    insp = u.get("inspecao") or {}
    el = [Paragraph(_t(titulo), st["tit"]),
          Paragraph(_t("%s%s · %s · dados do Geopresídios/CNIEP (CNJ) baixados em %s" % (u.get("cidade") or "", (" · " + u["endereco"]) if u.get("endereco") else "",
                                                                                      rgeo.CATEGORIAS.get(u.get("cat") or "penal", ""), atualizado)), st["sub"]), Spacer(1, 6)]
    nums = [(fmt(pop), "pessoas presas" + (" (%s)" % u["pop_ciclo"] if u.get("pop_ciclo") else "")), (fmt(u.get("capacidade")), "vagas"),
            ("—" if oc is None else "%d%%" % round(oc * 100), "taxa de ocupação"), (fmt(u.get("servidores_seguranca")), "agentes de segurança")]
    cel = [[Paragraph(_t(n), st["num"]) for n, _ in nums], [Paragraph(_t(r), st["rot"]) for _, r in nums]]
    tb = Table(cel, colWidths=[W / len(nums)] * len(nums))
    tb.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, C(LINE)), ("INNERGRID", (0, 0), (-1, -1), 0.6, C(LINE)),
                            ("BACKGROUND", (0, 0), (-1, -1), C(ZEBRA)), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                            ("TOPPADDING", (0, 0), (-1, 0), 7), ("BOTTOMPADDING", (0, 1), (-1, 1), 7), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    el.append(tb)
    if insp:
        el.append(Paragraph(_t("Aspectos gerais: inspeção de %s (ciclo %s) · %s · %s%s" % ("/".join(reversed(insp.get("data", "").split("-"))), insp.get("ciclo", ""),
                                                                                       u.get("classificacao") or "", u.get("destinacao") or "",
                                                                                       (" · lotação informada: %s" % u["faixa_lotacao"]) if u.get("faixa_lotacao") else "")), st["mut"]))
    sit = [["Situação", ""], ["Provisórios", fmt(u.get("provisorios"))], ["Regime fechado", fmt(u.get("fechado"))], ["Regime semiaberto", fmt(u.get("semiaberto"))],
           ["Regime aberto", fmt(u.get("aberto"))], ["Medida de segurança", fmt(u.get("medida_seguranca"))], ["Isolamento disciplinar", fmt(u.get("isolamento"))],
           ["Celas de seguro", fmt(u.get("seguro"))], ["RDD", fmt(u.get("rdd"))]]
    per = [["Perfil", ""], ["Homens", fmt(u.get("homens"))], ["Mulheres", fmt(u.get("mulheres"))], ["Mais de 60 anos", fmt(u.get("idosos"))],
           ["Indígenas", fmt(u.get("indigenas"))], ["Migrantes", fmt(u.get("migrantes"))], ["LGBTQIAPN+", fmt(u.get("lgbt"))],
           ["Deficiência física", fmt(u.get("deficiencia_fisica"))], ["Transtorno mental", fmt(u.get("transtorno_mental"))]]
    duas = Table([[_tabela(sit, [50 * mm, 25 * mm], st, pad=4), _tabela(per, [50 * mm, 25 * mm], st, pad=4)]], colWidths=[W / 2, W / 2])
    duas.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    el += [Paragraph("População", st["h2"]), duas,
           Paragraph(_t("Servidores: %s no total, %s na segurança." % (fmt(u.get("servidores")), fmt(u.get("servidores_seguranca")))), st["mut"])]
    for t in ("2", "3", "4", "5"):
        T = (u.get("temas") or {}).get(t)
        if not T:
            continue
        I = T.get("ind") or {}
        linhas = [["Indicador", "Resposta"]]
        for ch, tt, q, rot, ruim in rgeo.INDICADORES:
            if str(tt) == t and ch in I:
                v = I[ch]["v"]
                linhas.append([Paragraph(_t(rot), peq), Paragraph(('<font color="#A3201D"><b>%s</b></font>' % _t(v)) if I[ch].get("ruim") else _t(v), peq)])
        for ch, rot in (("defensores", "Defensores/as que atuam na unidade"), ("trab_remicao", "Trabalhando com cômputo para remição"), ("escola", "Inscritos na educação escolar")):
            if ch in I:
                linhas.append([Paragraph(_t(rot), peq), Paragraph(fmt(I[ch]["n"]), peq)])
        if len(linhas) > 1:
            el.append(KeepTogether([Paragraph(_t("%s · inspeção de %s" % (rgeo.TEMAS[int(t)], T.get("ciclo") or "")), st["h2"]),
                                    _tabela(linhas, [W - 60 * mm, 60 * mm], st, pad=4)]))
    graf = _geo_pizzas_unidade(u, W, _fontes(), C)
    if graf is not None:
        el.append(KeepTogether([Paragraph("Composição na última inspeção", st["h2"]), graf]))
    graf = _geo_colunas_unidade(u, W, _fontes(), C)
    if graf is not None:
        el.append(KeepTogether([Paragraph("Crescimento e ocupação ao longo das inspeções", st["h2"]), graf]))
    S = u.get("serie") or []
    if len(S) > 1 and S[0].get("pop"):
        a, b = S[0], S[-1]
        dlt = (b.get("pop") or 0) - (a.get("pop") or 0)
        var = lambda k: (b.get(k) or 0) - (a.get(k) or 0)
        sinal = lambda n: ("+" if n > 0 else "") + fmt(n)
        el.append(Paragraph(_t("Crescimento de apenados: de %s em %s para %s em %s (%s; %s%d%%). Provisórios %s; fechado %s; semiaberto %s; aberto %s."
                               % (fmt(a["pop"]), a["ciclo"], fmt(b["pop"]), b["ciclo"], sinal(dlt), "+" if dlt >= 0 else "", round(100 * dlt / a["pop"]),
                                  sinal(var("provisorios")), sinal(var("fechado")), sinal(var("semiaberto")), sinal(var("aberto")))), st["neg"]))
    if len(u.get("serie") or []) > 1:
        linhas = [["Ciclo da inspeção", "Presos", "Provisórios", "Fechado", "Semiaberto", "Aberto"]]
        for x in u["serie"]:
            linhas.append([x["ciclo"], fmt(x["pop"]), fmt(x.get("provisorios")), fmt(x.get("fechado")), fmt(x.get("semiaberto")), fmt(x.get("aberto"))])
        el.append(KeepTogether([Paragraph("Evolução da população", st["h2"]), _tabela(linhas, [40 * mm] + [(W - 40 * mm) / 5] * 5, st, pad=4)]))
    if assistidos:
        semi = [a for a in assistidos if a["regime"].upper().startswith(("SEMI", "ABERTO"))]
        el.append(Paragraph(_t("Assistidos da base %s nesta unidade (%d)" % (nome_base, len(assistidos))), st["h2"]))
        if semi and "FECHADO" in (u.get("destinacao") or "").upper():
            el.append(Paragraph(_t("%d no semiaberto ou no aberto pelo RSPE, custodiados em unidade destinada ao regime fechado: conferir o regime "
                                   "adequado (Súmula Vinculante 56)." % len(semi)), st["neg"]))
        linhas = [["Assistido", "Nº da execução", "Regime (RSPE)"]] + [[Paragraph(_t(a["nome"]), peq), Paragraph(_t(a["proc"]), peq), Paragraph(_t(a["regime"]), peq)]
                                                                         for a in assistidos]
        el.append(_tabela(linhas, [W - 90 * mm, 52 * mm, 38 * mm], st, pad=4))
    doc = SimpleDocTemplate(caminho, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=21 * mm, bottomMargin=20 * mm,
                            title=titulo, author="APTO")
    fr = _moldura("Relatório da unidade", nome_base, rodape="Fonte: Geopresídios/CNIEP (CNJ), geopresidios.cnj.jus.br. Dados declarados nas inspeções judiciais mensais.")
    doc.build(el, onFirstPage=fr, onLaterPages=fr, canvasmaker=_canvas_numerado())
    return caminho
