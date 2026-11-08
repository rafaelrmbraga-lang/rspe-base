"""Monitor da aba Jurisprudências: como está uma tese (área ou termo), como vota o relator, a câmara/turma e a seção.

Tudo é calculado aqui (a tela só desenha): sentido de cada decisão, órgão (com a turma inferida pelo relator quando o
acervo não traz o órgão), recorte pelos filtros, números, séries dos gráficos e o relatório em PDF.

SENTIDO DA DECISÃO (para a defesa) - campo "sentido" de cada item: "favoravel" | "desfavoravel" | "parcial" | "nao_conhecido".
  1. Se o item já traz "sentido" com um desses valores (a base nova, com as desfavoráveis, deve trazer), vale ele.
  2. Senão, pelo "rot" (rótulo do resultado já do ponto de vista da defesa, gravado na triagem):
     - "Parcialmente provido" / "parcialmente concedida" -> parcial;
     - rótulos de derrota da defesa ("Ordem denegada", "Recurso da defesa desprovido", "Recurso do MP provido",
       "Desfavorável à defesa", "Reclamação improcedente", "Agravo da defesa desprovido"...) -> desfavoravel;
     - os demais rótulos de hoje ("Ordem concedida", "Ordem concedida de ofício", "Recurso do MP desprovido",
       "Favorável à defesa", "Reclamação procedente", "Recurso da defesa provido", "Recurso provido",
       "Reconsideração favorável") -> favoravel. Habeas corpus "não conhecido" com ordem concedida de ofício é favorável.
     Resultado "Parcialmente provido / procedente" -> parcial, mesmo com rótulo favorável (a defesa ganhou em parte).
  3. Sem "rot", pelo "resultado" (recurso da defesa): Provido -> favoravel; Parcialmente provido -> parcial;
     Desprovido/Improcedente -> desfavoravel; Não conhecido / Não identificado -> nao_conhecido.
     ATENÇÃO: "Desprovido" só é desfavorável sem rótulo; com "Recurso do MP desprovido" é vitória da defesa.
  Na base atual (triagem que guardou só as favoráveis) não sai nenhuma "desfavoravel": o monitor mostra volume, não taxa.

ÓRGÃO: câmara/turma (fracionário) ou seção (seção, plenário, corte especial). Órgão vazio (STJ da triagem automática e
monocráticas do STF): turma inferida pelo relator, quando a maioria qualificada (2/3 ou mais) das decisões do mesmo relator,
no mesmo tribunal, com turma informada na própria base é de uma só turma; senão "Órgão não informado". Monocrática conta para o
relator e, no gráfico por órgão, aparece à parte como "<turma> · monocráticas".
"""

import re
from collections import Counter, defaultdict

SENTIDOS = ("favoravel", "parcial", "desfavoravel", "nao_conhecido")
ROT_SENTIDO = {"favoravel": "Favoráveis", "parcial": "Parcialmente favoráveis", "desfavoravel": "Desfavoráveis", "nao_conhecido": "Não conhecidos"}
COR_SENTIDO = {"favoravel": "#2F7A4F", "parcial": "#B38B00", "desfavoravel": "#A33A36", "nao_conhecido": "#9AA0A6"}
SEM_ORGAO = "Órgão não informado"
SEM_RELATOR = "Relator não informado"

# mesmo ministro grafado de dois jeitos no acervo
ALIAS_RELATOR = {"Rogerio Schietti": "Rogerio Schietti Cruz", "Marluce Caldas": "Maria Marluce Caldas"}

_SECAO = re.compile(r"se[cç][aã]o|pleno|plen[aá]rio|corte especial|[oó]rg[aã]o especial", re.I)
_TURMA = re.compile(r"turma|c[aâ]mara", re.I)
_DESF = re.compile(r"denegad|desfavor|improcedente|indeferid|defesa (des|n[aã]o |im)provid|\b(mp|minist[eé]rio p[uú]blico) provid", re.I)


def sentido(x):
    """Sentido da decisão para a defesa (regra no cabeçalho do módulo)."""
    s = (x.get("sentido") or "").strip().lower()
    if s in SENTIDOS:
        return s
    rot = (x.get("rot") or "").strip()
    res = (x.get("resultado") or "").lower()
    if rot:
        if re.search(r"parcial", rot, re.I):
            return "parcial"
        if _DESF.search(rot):
            return "desfavoravel"
        return "parcial" if "parcial" in res else "favoravel"
    if "parcial" in res:
        return "parcial"
    if re.search(r"desprovid|improced|negad|denegad", res):
        return "desfavoravel"
    if re.search(r"provid|proced|concedid", res):
        return "favoravel"
    return "nao_conhecido"


def nivel(orgao):
    """"secao" (seção, pleno, corte especial), "camara" (câmara criminal, turma) ou "" (vazio/outro)."""
    o = orgao or ""
    if not o.strip():
        return ""
    if _SECAO.search(o):
        return "secao"
    if _TURMA.search(o):
        return "camara"
    return ""


def relator(x):
    r = (x.get("relator") or "").strip()
    r = re.sub(r"^(min(istro|istra|\.)?|des(embargador[a]?|\.?\s*ª\.?|ª\.?|\.)?)\s+", "", r, flags=re.I)
    return ALIAS_RELATOR.get(r, r) or SEM_RELATOR


def turmas_por_relator(itens, fracao=2 / 3.0):
    """{(tribunal, relator): turma} quando o relator tem turma inequívoca na própria base: a turma mais frequente entre as
    decisões dele com câmara/turma informada tem ao menos 2/3 delas (só órgãos fracionários contam; seção não)."""
    cont = defaultdict(Counter)
    for x in itens:
        o = (x.get("orgao") or "").strip()
        r = relator(x)
        if o and r != SEM_RELATOR and nivel(o) == "camara":
            cont[((x.get("tribunal") or "TJMS"), r)][o] += 1
    out = {}
    for k, c in cont.items():
        o, n = c.most_common(1)[0]
        if n >= fracao * sum(c.values()):
            out[k] = o
    return out


def _ano(x):
    for k in ("julg", "pub"):
        m = re.search(r"(\d{4})\s*$", x.get(k) or "")
        if m:
            return int(m.group(1))
    return 0


def _data(x):
    p = (x.get("julg") or x.get("pub") or "").split("/")
    return (p[2] + p[1] + p[0]) if len(p) == 3 else ""


def preparar(itens):
    """Linhas leves do monitor (uma por decisão), com sentido, relator, órgão (inferido quando vazio), nível e ano."""
    T = turmas_por_relator(itens)
    out = []
    for x in itens:
        trib = x.get("tribunal") or "TJMS"
        rel = relator(x)
        o = (x.get("orgao") or "").strip()
        inf = False
        if not o:
            o = T.get((trib, rel), "")
            inf = bool(o)
        nv = nivel(o)
        out.append({"id": x.get("id"), "tribunal": trib, "tipo": x.get("tipo") or "Acórdão", "relator": rel, "orgao": o or SEM_ORGAO,
                    "inferido": inf, "nivel": nv, "camara": o if nv == "camara" else "", "secao": o if nv == "secao" else "",
                    "ano": _ano(x), "data": _data(x), "temas": list(x.get("temas") or []), "sentido": sentido(x),
                    "resultado": (x.get("rot") or x.get("resultado") or "Não identificado").strip()})
    return out


# ---- filtros: {tema, termo, tribunal, tipo, relator, camara, secao, ano_de, ano_ate} (vazio = todos) ----
def _passa(L, f, ids_termo, sem=None):
    if f.get("tema") and sem != "tema" and f["tema"] not in L["temas"]:
        return False
    if ids_termo is not None and L["id"] not in ids_termo:
        return False
    if f.get("tribunal") and sem != "tribunal" and L["tribunal"] != f["tribunal"]:
        return False
    if f.get("tipo") and sem != "tipo" and L["tipo"] != f["tipo"]:
        return False
    if f.get("relator") and sem != "relator" and L["relator"] != f["relator"]:
        return False
    if f.get("camara") and sem != "camara" and L["camara"] != f["camara"]:
        return False
    if f.get("secao") and sem != "secao" and L["secao"] != f["secao"]:
        return False
    if sem != "ano":
        a = L["ano"]
        if f.get("ano_de") and (not a or a < int(f["ano_de"])):
            return False
        if f.get("ano_ate") and (not a or a > int(f["ano_ate"])):
            return False
    return True


def filtrar(linhas, f, ids_termo=None):
    f = f or {}
    return [L for L in linhas if _passa(L, f, ids_termo)]


def _cont(sel):
    c = Counter(L["sentido"] for L in sel)
    return {s: c.get(s, 0) for s in SENTIDOS}


def taxa(c):
    """% favorável (favoráveis + parciais) sobre as decisões de mérito (favoráveis, parciais e desfavoráveis); None sem desfavorável."""
    if not c.get("desfavoravel"):
        return None
    den = c["favoravel"] + c["parcial"] + c["desfavoravel"]
    return round(100.0 * (c["favoravel"] + c["parcial"]) / den, 1) if den else None


def taxa_integral(c):
    if not c.get("desfavoravel"):
        return None
    den = c["favoravel"] + c["parcial"] + c["desfavoravel"]
    return round(100.0 * c["favoravel"] / den, 1) if den else None


def _grupo(sel, chave, top=None, varios=False):
    g = defaultdict(list)
    for L in sel:
        for k in (chave(L) if varios else [chave(L)]):
            if k:
                g[k].append(L)
    linhas = []
    for k, ls in g.items():
        c = _cont(ls)
        linhas.append(dict(c, nome=k, n=len(ls), taxa=taxa(c)))
    linhas.sort(key=lambda z: (-z["n"], z["nome"]))
    return linhas[:top] if top else linhas


def _rot_orgao(L):
    if L["orgao"] == SEM_ORGAO:
        return SEM_ORGAO + (" · monocráticas" if L["tipo"] == "Monocrática" else "")
    return L["orgao"] + (" · monocráticas" if L["tipo"] == "Monocrática" else "")


def facetas(linhas, f, ids_termo):
    """Opções dos filtros com a contagem no recorte (cada filtro conta com os outros aplicados, não com ele mesmo)."""
    f = f or {}
    out = {}
    dims = ("tribunal", "tipo", "relator", "camara", "secao", "tema", "ano")
    C = {d: Counter() for d in dims}
    tri = {}
    a0, a1 = int(f.get("ano_de") or 0), int(f.get("ano_ate") or 0)
    for L in linhas:  # uma passada: a linha conta na faceta d se só o filtro d (ou nenhum) a exclui
        if ids_termo is not None and L["id"] not in ids_termo:
            continue
        falha = []
        if f.get("tema") and f["tema"] not in L["temas"]:
            falha.append("tema")
        for d in ("tribunal", "tipo", "relator", "camara", "secao"):
            if f.get(d) and L[d] != f[d]:
                falha.append(d)
        if (a0 and (not L["ano"] or L["ano"] < a0)) or (a1 and (not L["ano"] or L["ano"] > a1)):
            falha.append("ano")
        if len(falha) > 1:
            continue
        for d in (falha or dims):
            if d == "tema":
                for t in L["temas"]:
                    C[d][t] += 1
            elif d == "ano":
                if L["ano"]:
                    C[d][L["ano"]] += 1
            elif L[d]:
                C[d][L[d]] += 1
                tri[(d, L[d])] = L["tribunal"]
    for dim in dims:
        c = C[dim]
        if dim == "ano":
            out[dim] = sorted(c)
        else:
            out[dim] = [{"v": k, "n": n, "tribunal": tri.get((dim, k), "")} for k, n in sorted(c.items(), key=lambda z: (-z[1], str(z[0])))]
    return out


def agregar(sel):
    """Números e séries dos gráficos de um recorte."""
    c = _cont(sel)
    anos = sorted({L["ano"] for L in sel if L["ano"]})
    por_ano = []
    if anos:
        da = defaultdict(list)
        for L in sel:
            if L["ano"]:
                da[L["ano"]].append(L)
        for a in range(anos[0], anos[-1] + 1):
            cc = _cont(da.get(a, []))
            por_ano.append(dict(cc, nome=str(a), n=len(da.get(a, [])), taxa=taxa(cc)))
    rel = _grupo([L for L in sel if L["relator"] != SEM_RELATOR], lambda L: L["relator"])
    trib_rel = {}
    for L in sel:
        trib_rel.setdefault(L["relator"], L["tribunal"])
    for r in rel:
        r["tribunal"] = trib_rel.get(r["nome"], "")
    orgaos = _grupo(sel, _rot_orgao)
    niv = {}
    for L in sel:
        niv.setdefault(_rot_orgao(L), (L["nivel"], L["inferido"], L["tribunal"]))
    for o in orgaos:
        o["nivel"], o["inferido"], o["tribunal"] = niv.get(o["nome"], ("", False, ""))
    ordem_niv = {"camara": 0, "secao": 1, "": 2}
    orgaos.sort(key=lambda z: (ordem_niv.get(z["nivel"], 2), z["nome"].endswith("monocráticas"), -z["n"], z["nome"]))
    n_inf = sum(1 for L in sel if L["inferido"])
    numeros = dict(c, total=len(sel), taxa=taxa(c), taxa_integral=taxa_integral(c), tem_desfavoravel=bool(c["desfavoravel"]),
                   relatores=len({L["relator"] for L in sel if L["relator"] != SEM_RELATOR}),
                   ano_de=anos[0] if anos else None, ano_ate=anos[-1] if anos else None,
                   acordaos=sum(1 for L in sel if L["tipo"] != "Monocrática"), monocraticas=sum(1 for L in sel if L["tipo"] == "Monocrática"),
                   orgao_inferido=n_inf, orgao_vazio=sum(1 for L in sel if L["orgao"] == SEM_ORGAO),
                   tribunais=dict(Counter(L["tribunal"] for L in sel)))
    return {"numeros": numeros,
            "series": {"ano": por_ano, "relator": rel[:15], "relator_total": len(rel), "orgao": orgaos,
                       "resultado": _grupo(sel, lambda L: L["resultado"]),
                       "tema": _grupo(sel, lambda L: L["temas"], top=12, varios=True)}}


AVISO_SO_FAVORAVEIS = ("A base atual tem só decisões favoráveis à defesa: os números mostram volume, não taxa de acolhimento.")


def monitor(linhas, f, ids_termo=None, limite_lista=3000):
    """{numeros, series, facetas, ids (mais recentes primeiro, até limite_lista), lista ([id, sentido, órgão, inferido]),
    total, aviso}."""
    sel = filtrar(linhas, f, ids_termo)
    r = agregar(sel)
    sel.sort(key=lambda L: L["data"], reverse=True)
    r["ids"] = [L["id"] for L in sel[:limite_lista]]
    r["lista"] = [[L["id"], L["sentido"], L["orgao"], 1 if L["inferido"] else 0] for L in sel[:limite_lista]]
    r["total"] = len(sel)
    r["facetas"] = facetas(linhas, f, ids_termo)
    r["aviso"] = "" if r["numeros"]["tem_desfavoravel"] or not sel else AVISO_SO_FAVORAVEIS
    return r


def descrever(f, n_termo=None):
    """Recorte em texto ("Remição · STJ · Relator: X · 2021 a 2026")."""
    f = f or {}
    p = []
    if f.get("tema"):
        p.append("Área: " + f["tema"])
    if f.get("termo"):
        p.append("Termo: “%s”" % f["termo"])
    if not p:
        p.append("Todas as áreas")
    for k, rot in (("tribunal", ""), ("tipo", ""), ("relator", "Relator: "), ("camara", "Câmara/Turma: "), ("secao", "Seção: ")):
        if f.get(k):
            p.append(rot + str(f[k]) + ("s" if k == "tipo" else ""))
    if f.get("ano_de") or f.get("ano_ate"):
        p.append("%s a %s" % (f.get("ano_de") or "início", f.get("ano_ate") or "hoje"))
    return " · ".join(p)


# ---------------------------------------------------------------- relatório em PDF
def _curto(t, n):
    t = " ".join((t or "").split())
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _barras_sentido(titulo, linhas, largura, st, nota="", mostrar_taxa=False, max_itens=15):
    """Barras horizontais empilhadas por sentido (rótulo à esquerda, total e taxa à direita)."""
    import rspe_relatorio as rr
    from reportlab.graphics.shapes import Drawing, Rect, String
    from reportlab.lib import colors
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.platypus import Paragraph
    f = rr._fontes()
    corpo = [Paragraph(rr._t(titulo), st["neg"])]
    linhas = [z for z in linhas if z["n"]][:max_itens]
    if not linhas:
        return corpo + [Paragraph("Sem dados.", st["mut"])]
    rot_w = largura * 0.36
    dir_w = 64 if mostrar_taxa else 34
    h_l = 13
    d = Drawing(largura, h_l * len(linhas) + 16)
    mx = max(z["n"] for z in linhas) or 1
    y = d.height - 16
    sents = [s for s in SENTIDOS if any(z[s] for z in linhas)]
    x = 0
    for s in sents:
        d.add(Rect(x, d.height - 8, 7, 7, fillColor=colors.HexColor(COR_SENTIDO[s]), strokeColor=None))
        d.add(String(x + 10, d.height - 7.5, ROT_SENTIDO[s], fontName=f["n"], fontSize=7, fillColor=colors.HexColor(rr.TX)))
        x += 20 + stringWidth(ROT_SENTIDO[s], f["n"], 7)
    for z in linhas:
        y -= h_l
        nome = z["nome"]
        while stringWidth(nome, f["n"], 7.2) > rot_w - 6 and len(nome) > 4:
            nome = nome[:-2]
        if nome != z["nome"]:
            nome = nome.rstrip() + "…"
        d.add(String(0, y + 3, nome, fontName=f["n"], fontSize=7.2, fillColor=colors.HexColor(rr.TX2)))
        xb = rot_w
        for s in SENTIDOS:
            if z[s]:
                w = (largura - rot_w - dir_w) * z[s] / float(mx)
                d.add(Rect(xb, y + 1.5, max(w, 0.8), 9, fillColor=colors.HexColor(COR_SENTIDO[s]), strokeColor=colors.white, strokeWidth=0.5))
                xb += w
        tx = str(z["n"]) + (("  %s%%" % str(z["taxa"]).replace(".", ",")) if mostrar_taxa and z.get("taxa") is not None else "")
        d.add(String(xb + 4, y + 3, tx, fontName=f["b"], fontSize=7.2, fillColor=colors.HexColor(rr.TX)))
    corpo.append(d)
    if nota:
        corpo.append(Paragraph(rr._t(nota), st["mut"]))
    return corpo


def relatorio_pdf(res, f, itens_por_id, caminho, nome_base="", limite=300):
    """PDF do Monitor: recorte, números, gráficos (ano, relator, órgão, resultado) e a lista das decisões do recorte."""
    import rspe_relatorio as rr
    from datetime import datetime
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, CondPageBreak, KeepTogether
    st = rr._estilos()
    C = st["C"]
    W = A4[0] - 32 * mm
    N, S = res["numeros"], res["series"]
    rec = descrever(f)
    el = [Paragraph(rr._t("Monitor de jurisprudência"), st["tit"]),
          Paragraph(rr._t(rec), st["sub"]),
          Paragraph(rr._t("Acervo da aba Jurisprudências (TJMS, STJ e STF) · gerado em %s" % datetime.now().strftime("%d/%m/%Y %H:%M")), st["mut"]),
          Spacer(1, 8)]
    per = ("%s-%s" % (N["ano_de"], N["ano_ate"]) if N["ano_de"] != N["ano_ate"] else str(N["ano_de"])) if N.get("ano_de") else "—"
    nums = [(rr._num(N["total"]), "decisões no recorte"), (rr._num(N["favoravel"]), "favoráveis"), (rr._num(N["desfavoravel"]), "desfavoráveis")]
    if N.get("taxa") is not None:
        nums.append(("%s%%" % str(N["taxa"]).replace(".", ","), "de acolhimento (com parciais)"))
    nums += [(rr._num(N["relatores"]), "relatores"), (per, "período (julgamento)")]
    from reportlab.lib.styles import ParagraphStyle
    menor = ParagraphStyle("num_menor", parent=st["num"], fontSize=14, leading=23)  # "2020-2026" cabe na célula
    cel = [[Paragraph(rr._t(str(v)), st["num"] if len(str(v)) <= 7 else menor), Paragraph(rr._t(r), st["rot"])] for v, r in nums]
    t = Table([cel], colWidths=[W / len(cel)] * len(cel))
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.6, C(rr.LINE)), ("LINEBELOW", (0, 0), (-1, 0), 0.6, C(rr.LINE)),
                           ("LINEAFTER", (0, 0), (-2, 0), 0.6, C(rr.LINE)), ("TOPPADDING", (0, 0), (-1, -1), 6),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 7), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    el.append(t)
    det = "%s acórdãos e %s monocráticas; %s · parciais: %s · não conhecidos: %s." % (
        rr._num(N["acordaos"]), rr._num(N["monocraticas"]), ", ".join("%s %s" % (k, rr._num(v)) for k, v in sorted(N["tribunais"].items())) or "—",
        rr._num(N["parcial"]), rr._num(N["nao_conhecido"]))
    el.append(Paragraph(rr._t(det), st["mut"]))
    if res.get("aviso"):
        el += [Spacer(1, 4), Paragraph("<font color='#7A5410'>%s</font>" % rr._t(res["aviso"]), st["p"])]
    mt = N.get("tem_desfavoravel")
    anos = S["ano"]
    el += [CondPageBreak(70 * mm), Paragraph("1. Decisões por ano", st["h2"])]
    sents = [s for s in SENTIDOS if any(a[s] for a in anos)]
    el += rr._colunas("Decisões por ano de julgamento, pelo sentido para a defesa", [a["nome"] for a in anos],
                      [(ROT_SENTIDO[s], [a[s] for a in anos], COR_SENTIDO[s]) for s in sents] or [("Decisões", [0] * len(anos), COR_SENTIDO["favoravel"])],
                      W, st, altura=110)
    sec = [1]

    def h2(t, falta):
        sec[0] += 1
        return [CondPageBreak(falta * mm), Paragraph("%d. %s" % (sec[0], t), st["h2"])]
    if not f.get("relator"):
        el += h2("Como votam os relatores", 80)
        el += _barras_sentido("Decisões por relator (os %d com mais decisões, de %d)%s" % (len(S["relator"]), S["relator_total"], ", com a taxa de acolhimento" if mt else ""),
                          S["relator"], W, st, mostrar_taxa=mt, nota="Só processos da relatoria de cada um (acórdãos e monocráticas).")
    el += h2("Por câmara/turma e seção", 60)
    nota = "Câmaras e turmas primeiro, depois seções e plenário. Monocráticas aparecem à parte."
    if N.get("orgao_inferido"):
        nota += " Em %s decisões o órgão veio vazio e a turma foi inferida pelo relator." % rr._num(N["orgao_inferido"])
    el += _barras_sentido("Decisões por órgão julgador", S["orgao"], W, st, mostrar_taxa=mt, nota=nota, max_itens=24)
    el += h2("Por resultado", 50)
    el += _barras_sentido("Decisões pelo resultado (rótulo do ponto de vista da defesa quando há)", S["resultado"], W, st, max_itens=12)
    el += h2("Decisões do recorte", 50) + [
           Paragraph(rr._t("%s, das mais recentes às mais antigas%s." % (
               rr._num(res["total"]) + (" decisão" if res["total"] == 1 else " decisões"),
               ("; a lista traz as %s mais recentes (para ver todas, restrinja o recorte ou use a tela)" % rr._num(limite)) if res["total"] > limite else "")), st["mut"]), Spacer(1, 4)]
    rot_s = {"favoravel": "Favorável", "parcial": "Parcial", "desfavoravel": "Desfavorável", "nao_conhecido": "Não conhecido"}
    cor_s = {"favoravel": "verde", "parcial": "amarelo", "desfavoravel": "vermelho", "nao_conhecido": "cinza"}
    dados = [["Julg.", "Tribunal · órgão", "Relator", "Processo", "Tese / resultado", "Sentido"]]
    cores = {}
    peq = "<br/><font color='%s' size='6.8'>%%s</font>" % rr.TX3
    for k, s, org, inf in (res.get("lista") or [])[:limite]:
        x = itens_por_id.get(k)
        if not x:
            continue
        trib = x.get("tribunal") or "TJMS"
        dados.append([x.get("julg") or "—",
                      Paragraph(rr._t("%s · %s" % (trib, org)) + (peq % ("turma inferida pelo relator" if inf else "")) * bool(inf)
                                + (peq % "monocrática") * (x.get("tipo") == "Monocrática"), st["cel"]),
                      Paragraph(rr._t(relator(x)), st["cel"]),
                      Paragraph(rr._t(x.get("proc") or "") + ((peq % rr._t(x["classe"])) if trib == "TJMS" and x.get("classe") else ""), st["cel"]),
                      Paragraph(rr._t(_curto(x.get("tese") or "", 170)) + peq % rr._t(x.get("rot") or x.get("resultado") or ""), st["cel"]),
                      rot_s[s]])
        cores[len(dados) - 1] = cor_s[s]
    el.append(rr._tabela(dados, [17 * mm, 27 * mm, 24 * mm, 37 * mm, W - 122 * mm, 17 * mm], st, cores_linha=cores, pad=3, vpad=2.5))
    doc = SimpleDocTemplate(caminho, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=21 * mm, bottomMargin=20 * mm,
                            title="Monitor de jurisprudência", author="APTO")
    fr = rr._moldura("Monitor de jurisprudência", nome_base or "—",
                     rodape="Acervo de jurisprudência da aba Jurisprudências (decisões curadas e triagem automática do STJ). Sentido da decisão pelo "
                            "resultado e pelo rótulo da triagem; turma inferida pelo relator quando o órgão não veio no acervo. Conferir o inteiro teor antes de citar.")
    doc.build(el, onFirstPage=fr, onLaterPages=fr, canvasmaker=rr._canvas_numerado())
    return caminho
