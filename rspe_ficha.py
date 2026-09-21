# -*- coding: utf-8 -*-
"""
Leitura da Ficha Disciplinar do SIAPEN (AGEPEN/MS) e confronto com o RSPE.

Extrai: identificação, conduta, períodos de trabalho (setor/empresa), atestados de trabalho
(dias trabalhados e remidos), faltas disciplinares (registro, PADIC, resultado), regressão/
restabelecimento e recusa de trabalho. Compara os dias remidos atestados com o saldo do RSPE
(LEP, arts. 126 a 128) e a existência de falta grave (LEP, arts. 50 e 83; CP, art. 83, III, b).
"""
import re
from datetime import date, timedelta

import pdfplumber

import rspe_scraper as rs

RE_LINHA = re.compile(r"(?m)^(\d{2}\.\d{2}\.\d{4}) - ")
RE_D = re.compile(r"(\d{2})/(\d{2})/(\d{2,4})")


def _d(txt):
    m = RE_D.search(txt or "")
    if not m:
        return None
    dd, mm, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if yy < 100:
        yy += 2000 if yy < 70 else 1900
    try:
        return date(yy, mm, dd)
    except ValueError:
        return None


def _dp(txt):
    try:
        return date(int(txt[6:10]), int(txt[3:5]), int(txt[0:2]))
    except Exception:
        return None


def _num(txt):
    return float(txt.replace(",", "."))


def texto_pdf(caminho):
    with pdfplumber.open(caminho) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def e_ficha(texto):
    return "FICHA DISCIPLINAR" in texto.upper() and "SIAPEN" in texto.upper()


def _limpar(t):
    # remove cabeçalhos/rodapés repetidos do SIAPEN
    out = []
    for l in t.splitlines():
        u = l.strip()
        if not u:
            continue
        if re.search(r"Confidencial ::|Responsável:|Projeto SIAPEN|^RUA:|^CEP:|^FONE:|^\d{2}:\d{2}:\d{2}$|^RRMB|^\d{2}:\d{2}: ", u):
            continue
        out.append(u)
    return "\n".join(out)


def extrair(caminho):
    t = texto_pdf(caminho)
    if not e_ficha(t):
        raise ValueError("não é uma Ficha Disciplinar do SIAPEN")
    t = _limpar(t)
    f = {"arquivo": caminho, "tipo": "ficha_disciplinar"}
    cab = t.split("HISTÓRICO")[0]
    f["nome"] = (re.search(r"Nome:\s*(.+?)\s+RGI:", cab) or [None, ""])[1].strip() if re.search(r"Nome:\s*(.+?)\s+RGI:", cab) else ""
    f["rgi"] = (re.search(r"RGI:\s*(\d+)", cab) or [None, ""])[1]
    f["cpf"] = (re.search(r"CPF:\s*(\d+)", cab) or [None, ""])[1]
    f["data_nascimento"] = (re.search(r"Data Nascimento:\s*(\d{2}/\d{2}/\d{4})", cab) or [None, ""])[1]
    f["artigo"] = (re.search(r"Artigo:\s*(.+)", cab) or [None, ""])[1].strip()
    f["data_prisao"] = (re.search(r"Data Prisão:\s*(\d{2}/\d{2}/\d{4})", cab) or [None, ""])[1]
    f["condenacao"] = (re.search(r"Condenação:\s*(.+)", cab) or [None, ""])[1].strip()
    f["unidade"] = (re.search(r"Unidade Penal:\s*(.+)", cab) or [None, ""])[1].strip()
    f["data_entrada"] = (re.search(r"Data Entrada:\s*(\d{2}/\d{2}/\d{4})", cab) or [None, ""])[1]
    f["conduta"] = (re.search(r"CONDUTA:\s*([A-ZÇÃÕÁÉÍÓÚ ]+)", t) or [None, ""])[1].strip()
    f["data_impressao"] = (re.search(r"Impresso em (\d{2}/\d{2}/\d{4})", texto_pdf(caminho)) or [None, ""])[1]
    autos = sorted(set(re.findall(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}", t)))
    f["autos"] = autos

    # ---- eventos do histórico ----
    hist = t.split("HISTÓRICO", 1)[1] if "HISTÓRICO" in t else t
    partes = RE_LINHA.split(hist)
    eventos = []
    for i in range(1, len(partes) - 1, 2):
        d, txt = partes[i], " ".join(partes[i + 1].split())
        eventos.append({"data": d, "d": _dp(d), "texto": txt})
    f["eventos"] = [{"data": e["data"], "texto": e["texto"]} for e in eventos]

    # ---- trabalho ----
    trabalho, aberto = [], None
    for e in eventos:
        u = e["texto"].upper()
        m = re.search(r"TRABALHO:\s*INICIOU ATIVIDADE LABORAL,?\s*NO SETOR DE TRABALHO\s*(.+?)(?:,\s*CONFORME|$)", u)
        if m:
            if aberto:
                trabalho.append(aberto)
            aberto = {"inicio": e["data"], "fim": "", "setor": m.group(1).strip(" ,."), "externo": False}
            continue
        m = re.search(r"TRABALHO:\s*DEIXA DE TRABALHAR,?\s*NO SETOR DE TRABALHO\s*(.+?)(?:,\s*CONFORME|$)", u)
        if m:
            if aberto:
                aberto["fim"] = e["data"]
                mm = re.search(r"MOTIVO:\s*(.+)$", u)
                aberto["motivo_fim"] = (mm.group(1).strip(" .") if mm else "")
                trabalho.append(aberto)
                aberto = None
            continue
        if "ATIVIDADE LABORAL EXTERNA" in u and aberto:
            aberto["externo"] = True
            me = re.search(r"EMPRESA\s+(.+?)\s+CONVENIADA", u)
            if me:
                aberto["empresa"] = me.group(1).strip()
    if aberto:
        trabalho.append(aberto)
    f["trabalho"] = trabalho

    # ---- atestados de trabalho (dias trabalhados / remidos) ----
    atest = []
    for e in eventos:
        u = e["texto"].upper()
        if "ATESTADO DE TRABALHO" not in u:
            continue
        m = re.search(r"(\d+)\s*DIAS TRABALHADOS E\s*([\d.,]+)\s*DIAS REMIDOS", u)
        if not m:
            continue
        n = re.search(r"ATESTADO DE TRABALHO(?: PRISIONAL)?\s*N[ºO°]?\s*([\w./-]+)", u)
        per = re.search(r"(?:PER[IÍ]ODO(?: TRABALHADO)?\s*(?:DE|NA EMPRESA[^\d]*)?)\s*(\d{2}/\d{2}/\d{2,4})\s*(?:A|-)?\s*(\d{2}/\d{2}/\d{2,4})", u)
        if not per:
            per = re.search(r"(\d{2}/\d{2}/\d{2,4})\s+(?:A\s+)?(\d{2}/\d{2}/\d{2,4})", u)
        emp = re.search(r"NA EMPRESA[,:]?\s*(.+?)\s+(?:\(|DE\s+\d|\d{2}/\d{2})", u)
        atest.append({
            "data": e["data"], "numero": n.group(1) if n else "",
            "dias_trabalhados": int(m.group(1)), "dias_remidos": _num(m.group(2)),
            "periodo_inicio": per.group(1) if per else "", "periodo_fim": per.group(2) if per else "",
            "empresa": emp.group(1).strip(" ,-") if emp else "",
            "autos": (re.search(r"AUTOS N[ºO°]?\s*([\d.-]+)", u) or [None, ""])[1],
        })
    f["atestados"] = atest
    f["dias_trabalhados_atestados"] = sum(a["dias_trabalhados"] for a in atest)
    f["dias_remidos_atestados"] = round(sum(a["dias_remidos"] for a in atest), 2)

    # ---- faltas disciplinares ----
    faltas = []
    for e in eventos:
        u = e["texto"].upper()
        if "CONSELHO DISCIPLINAR" not in u and "FALTA DISCIPLINAR" not in u and "FALTA GRAVE" not in u:
            continue
        if re.search(r"REGISTRO DE FALTA|LAN[ÇC]AMENTO DE FALTA|FALTA GRAVE", u) and "ARQUIV" not in u and "INSTAURA" not in u and "ISOLADO" not in u:
            art = re.search(r"INFRING\w*\s*(?:EM TESE)?\s*O?\s*ART\.?\s*(\d+)[, ]*\s*(?:INCISO|INC\.?)?\s*([IVXL]+)?", u) or re.search(r"ART\.?\s*(\d+)[, ]*\s*(?:INCISO|INC\.?)?\s*([IVXL]+)?", u)
            cometida = re.search(r"COMETIDA EM\s*(\d{2}/\d{2}/\d{4})", u)
            faltas.append({"data_registro": e["data"], "data_fato": cometida.group(1) if cometida else e["data"],
                           "artigo": ("art. %s%s da LEP" % (art.group(1), (", " + art.group(2)) if art.group(2) else "")) if art else "",
                           "grave": bool(art and art.group(1) in ("50", "52")) or "FALTA GRAVE" in u,
                           "texto": e["texto"], "situacao": "registrada", "padic": "", "resultado": ""})
    for e in eventos:
        u = e["texto"].upper()
        m = re.search(r"OCORRIDO EM\s*(\d{2}/\d{2}/\d{4})|COMETIDA EM\s*(\d{2}/\d{2}/\d{4})", u)
        alvo = None
        if m:
            dt = m.group(1) or m.group(2)
            alvo = next((x for x in faltas if x["data_fato"] == dt), None)
        if alvo is None and faltas and ("PADIC" in u or "ARQUIV" in u or "HOMOLOG" in u):
            alvo = min(faltas, key=lambda x: abs((_dp(e["data"]) - _dp(x["data_registro"])).days) if _dp(e["data"]) and _dp(x["data_registro"]) else 9999)
        if not alvo:
            continue
        mp = re.search(r"PADIC\s*/?\s*\w*\s*N[ºO°]?\s*([\d./-]+)", u)
        if "INSTAURA" in u:
            alvo["situacao"] = "PADIC instaurado"
            if mp:
                alvo["padic"] = mp.group(1)
        if "ARQUIV" in u:
            alvo["situacao"] = "arquivada"
            alvo["resultado"] = e["texto"]
            alvo["data_resultado"] = e["data"]
        elif re.search(r"HOMOLOG|RECONHEC|PUNI[ÇC][ÃA]O|SAN[ÇC][ÃA]O", u):
            alvo["situacao"] = "homologada/punida"
            alvo["resultado"] = e["texto"]
            alvo["data_resultado"] = e["data"]
    f["faltas"] = faltas

    # ---- outros marcos relevantes ----
    f["regressoes"] = [e["data"] + " - " + e["texto"] for e in eventos if re.search(r"REGRESS", e["texto"], re.I)]
    f["restabelecimentos"] = [e["data"] + " - " + e["texto"] for e in eventos if re.search(r"RESTABELEC", e["texto"], re.I)]
    f["recusa_trabalho"] = [e["data"] + " - " + e["texto"] for e in eventos if re.search(r"RECUSOU VAGA|RECUSA DE TRABALHO", e["texto"], re.I)]
    f["isolamentos"] = [e["data"] + " - " + e["texto"] for e in eventos if re.search(r"ISOLADO|ISOLAMENTO|CELA DISCIPLINAR", e["texto"], re.I)]
    f["estudo"] = [e["data"] + " - " + e["texto"] for e in eventos if re.search(r"ESTUD|LEITURA|CURSO|ESCOLA", e["texto"], re.I) and "TRABALHO" not in e["texto"].upper()]
    return f


# ---------------------------------------------------------------- confronto com o RSPE

def confrontar(r, f, hoje=None):
    """Compara ficha (f) com o registro do RSPE (r). Devolve lista de itens no formato da auditoria:
    {nivel, titulo, detalhe, fundamento}."""
    hoje = hoje or date.today()
    itens = []
    if not f:
        return itens
    saldo = rs.saldo_remidos_num(r.get("saldo_remidos"))
    remidos_rspe, perdidos_rspe = saldo
    inc_rem = []
    for i in r.get("_incidentes", []):
        if "REMI" in (i.get("tipo") or "").upper():
            m = re.search(r"([\d.,]+)\s*Dia", i.get("complemento", ""), re.I)
            if m:
                inc_rem.append((i.get("data_decisao") or i.get("data_referencia") or "", _num(m.group(1))))
    homologados = sum(v for _, v in inc_rem) if inc_rem else (remidos_rspe or 0)
    atestados = f.get("dias_remidos_atestados") or 0
    dif = round(atestados - homologados, 2)

    # 1) remição atestada x homologada
    if atestados and dif > 1:
        ult = max((a["data"] for a in f.get("atestados", [])), key=lambda x: _dp(x) or date.min, default="")
        itens.append({"nivel": "alerta",
                      "titulo": "Remição: %s dias atestados pela unidade, %s homologados no RSPE (faltam %s)" % (_fmtn(atestados), _fmtn(homologados), _fmtn(dif)),
                      "detalhe": "Atestados de trabalho na ficha: " + "; ".join(
                          "nº %s (%s): %s dias trabalhados, %s remidos%s" % (a["numero"] or "s/n", a["data"], a["dias_trabalhados"], _fmtn(a["dias_remidos"]),
                                                                            (" - " + a["periodo_inicio"] + " a " + a["periodo_fim"]) if a["periodo_inicio"] else "")
                          for a in f.get("atestados", [])) + ". Remições no RSPE: " + ("; ".join("%s dias em %s" % (_fmtn(v), d) for d, v in inc_rem) or "nenhum incidente") +
                      ". Último atestado em %s. Conferir se há pedido de remição pendente ou atestado não juntado." % ult,
                      "fundamento": "LEP, arts. 126 (1 dia a cada 3 trabalhados) e 126, § 8º (declaração da unidade); Súmula 562 STJ (remição pelo trabalho antes de recolhimento)."})
    elif atestados:
        itens.append({"nivel": "ok", "titulo": "Remição: dias atestados (%s) já homologados no RSPE (%s)" % (_fmtn(atestados), _fmtn(homologados)), "detalhe": "", "fundamento": ""})
    # 2) proporção 1/3 nos atestados
    for a in f.get("atestados", []):
        esperado = a["dias_trabalhados"] / 3.0
        if a["dias_trabalhados"] and abs(esperado - a["dias_remidos"]) > 1:
            itens.append({"nivel": "verificar", "titulo": "Atestado %s: %s dias trabalhados dariam %s remidos, consta %s" % (a["numero"] or a["data"], a["dias_trabalhados"], _fmtn(esperado), _fmtn(a["dias_remidos"])),
                          "detalhe": "Proporção legal: 1 dia de pena a cada 3 dias de trabalho.", "fundamento": "LEP, art. 126, § 1º, II."})
    # 3) trabalho em curso sem atestado
    trab = f.get("trabalho", [])
    em_curso = [x for x in trab if not x.get("fim")]
    ult_at = max((_d(a["periodo_fim"]) for a in f.get("atestados", []) if _d(a["periodo_fim"])), default=None)
    if em_curso:
        x = em_curso[-1]
        ini = _dp(x["inicio"])
        desde = max(ini, ult_at + timedelta(days=1)) if (ini and ult_at and ult_at >= ini) else ini
        if desde:
            dias = (hoje - desde).days
            if dias >= 30:
                itens.append({"nivel": "verificar",
                              "titulo": "Trabalhando em %s desde %s sem atestado: cerca de %d dias trabalhados (≈ %d remidos) a atestar" % (
                                  x.get("empresa") or x.get("setor") or "?", rs.fmt(desde), dias, dias // 3),
                              "detalhe": "Estimativa em dias corridos desde o fim do último atestado (%s); a unidade atesta apenas os dias efetivamente trabalhados. Cabe requerer a expedição de novo atestado e a remição." % (rs.fmt(ult_at) if ult_at else "sem atestado anterior"),
                              "fundamento": "LEP, arts. 126 e 129 (declaração mensal/trimestral da unidade)."})
    # 4) faltas disciplinares
    for fa in f.get("faltas", []):
        dfato = _dp(fa["data_fato"]) or _dp(fa["data_registro"])
        rec = dfato and (hoje - dfato).days <= 365
        if fa["situacao"] == "arquivada":
            itens.append({"nivel": "verificar" if rec else "info",
                          "titulo": "Falta disciplinar de %s (%s) ARQUIVADA em %s" % (fa["data_fato"], fa["artigo"] or "art. n/i", fa.get("data_resultado", "?")),
                          "detalhe": (fa.get("resultado") or "") + (" | O RSPE deve refletir: sem falta grave, sem perda de remidos e sem regressão/alteração da data-base por este fato." if rec else ""),
                          "fundamento": "LEP, arts. 59 e 118; STJ, Súmula 533 (PAD obrigatório)."})
        elif fa["situacao"] == "homologada/punida" or fa["grave"]:
            itens.append({"nivel": "alerta" if rec else "info",
                          "titulo": "Falta %s de %s (%s): %s" % ("grave" if fa["grave"] else "disciplinar", fa["data_fato"], fa["artigo"] or "art. n/i", fa["situacao"]),
                          "detalhe": fa.get("resultado") or fa.get("texto", ""),
                          "fundamento": "LEP, arts. 50, 118, I, e 127; CP, art. 83, III, b; Decretos de indulto, art. 6º (12 meses)."})
    # 5) regressão x restabelecimento
    if f.get("restabelecimentos"):
        itens.append({"nivel": "verificar", "titulo": "Regime restabelecido por decisão judicial (ficha)", "detalhe": " | ".join(f["restabelecimentos"]),
                      "detalhe_": "", "fundamento": "Conferir se a regressão cautelar foi cancelada no RSPE e se a data-base não foi alterada indevidamente (STJ, Tema 1006/1165)."})
    if f.get("recusa_trabalho"):
        itens.append({"nivel": "info", "titulo": "Recusa de vaga de trabalho registrada", "detalhe": " | ".join(f["recusa_trabalho"]), "fundamento": "LEP, arts. 31 e 39, V (dever de trabalho); relevante para exame de mérito."})
    # 6) identidade
    if f.get("autos") and r.get("processo_execucao") and r["processo_execucao"] not in f["autos"]:
        itens.append({"nivel": "verificar", "titulo": "Ficha cita autos %s; RSPE é %s" % (", ".join(f["autos"]), r["processo_execucao"]), "detalhe": "Conferir se a ficha é do mesmo apenado/execução.", "fundamento": ""})
    for it in itens:
        it.pop("detalhe_", None)
        it["origem"] = "ficha"
    return itens


def resumo(f):
    if not f:
        return ""
    trab = f.get("trabalho", [])
    em = [x for x in trab if not x.get("fim")]
    faltas = f.get("faltas", [])
    return "Conduta %s · %s atestado(s), %s dias remidos · %s · %d falta(s)%s" % (
        f.get("conduta") or "?", len(f.get("atestados", [])), _fmtn(f.get("dias_remidos_atestados") or 0),
        ("trabalhando em " + (em[-1].get("empresa") or em[-1].get("setor") or "?") + " desde " + em[-1]["inicio"]) if em else "sem trabalho em curso",
        len(faltas), (" (" + ", ".join(x["situacao"] for x in faltas) + ")") if faltas else "")


def _fmtn(v):
    v = float(v)
    return ("%d" % v) if abs(v - round(v)) < 0.01 else ("%.2f" % v)


# ---------------------------------------------------------------- aba "Ficha disciplinar" (comparativo)

def comparativo(r, f, hoje=None):
    """Campos da aba Ficha disciplinar: colunas resumidas + linhas do comparativo Ficha x RSPE."""
    hoje = hoje or date.today()
    out = {"fd_tem": bool(f), "fd_cor": "cinza", "fd_sit": "Sem ficha", "fd_conduta": "", "fd_trab": "", "fd_remidos": "",
           "fd_atestar": "", "fd_faltas": "", "fd_linhas": [], "fd_dias": None}
    if not f:
        out["fd_linhas"] = [{"item": "Ficha disciplinar", "ficha": "não importada", "rspe": "", "sit": "Importe o PDF da Ficha Disciplinar (SIAPEN) pelo botão Importar PDFs", "cor": "cinza"}]
        return out
    L = []
    def add(item, ficha, rspe, sit, cor=""):
        L.append({"item": item, "ficha": ficha or "—", "rspe": rspe or "—", "sit": sit, "cor": cor})

    remidos_rspe, perdidos_rspe = rs.saldo_remidos_num(r.get("saldo_remidos"))
    inc_rem = []
    for i in r.get("_incidentes", []):
        if "REMI" in (i.get("tipo") or "").upper():
            m = re.search(r"([\d.,]+)\s*Dia", i.get("complemento", ""), re.I)
            if m:
                inc_rem.append((i.get("data_decisao") or i.get("data_referencia") or "", _num(m.group(1))))
    homolog = sum(v for _, v in inc_rem) if inc_rem else float(remidos_rspe or 0)
    atest = float(f.get("dias_remidos_atestados") or 0)
    dif = round(atest - homolog, 2)
    cor_geral, sit_geral = "verde", "Em ordem"
    # remição
    if atest and dif > 1:
        add("Dias remidos", "%s atestados (%d atestados)" % (_fmtn(atest), len(f.get("atestados", []))),
            "%s homologados%s" % (_fmtn(homolog), (" (%s)" % "; ".join("%s em %s" % (_fmtn(v), d) for d, v in inc_rem)) if inc_rem else ""),
            "Faltam homologar %s dias - requerer remição (LEP, art. 126)" % _fmtn(dif), "vermelho")
        cor_geral, sit_geral = "vermelho", "Remição pendente (%s dias)" % _fmtn(dif)
    elif atest:
        add("Dias remidos", "%s atestados" % _fmtn(atest), "%s homologados" % _fmtn(homolog), "Conferem", "verde")
    else:
        add("Dias remidos", "nenhum atestado na ficha", "%s homologados" % _fmtn(homolog), "Sem atestados na ficha", "")
    out["fd_remidos"] = ("%s / %s" % (_fmtn(atest), _fmtn(homolog))) + ((" · +%s" % _fmtn(dif)) if dif > 1 else "")
    # perdidos
    if perdidos_rspe:
        add("Dias remidos perdidos", "", "%d perdidos" % perdidos_rspe, "Conferir a falta grave que motivou (LEP, art. 127: até 1/3)", "amarelo")
    # dias trabalhados
    dt = f.get("dias_trabalhados_atestados") or 0
    if dt:
        add("Dias trabalhados", "%d (atestados)" % dt, "", "Proporção 1 para 3: %s remidos esperados" % _fmtn(dt / 3.0),
            "amarelo" if abs(dt / 3.0 - atest) > 2 else "verde")
    # atestados individuais: a homologação cobre os atestados em ordem cronológica (soma acumulada ≤ homologado)
    acum = 0.0
    for a in sorted(f.get("atestados", []), key=lambda a: _dp(a["data"]) or date.min):
        esperado = a["dias_trabalhados"] / 3.0
        ok = abs(esperado - a["dias_remidos"]) <= 1
        acum += a["dias_remidos"]
        homologado = acum <= homolog + 1.5
        add("Atestado %s (%s)" % ((a["numero"] or "s/n").split("/ST")[0], a["data"]),
            "%d trabalhados · %s remidos%s%s" % (a["dias_trabalhados"], _fmtn(a["dias_remidos"]), (" · " + a["periodo_inicio"] + " a " + a["periodo_fim"]) if a["periodo_inicio"] else "", (" · " + a["empresa"]) if a.get("empresa") else ""),
            "homologado" if homologado else "sem incidente de remição correspondente",
            ("" if ok else "proporção 1/3 não confere · ") + ("ok" if homologado else "requerer"), "verde" if (homologado and ok) else ("vermelho" if not homologado else "amarelo"))
    # trabalho em curso
    trab = f.get("trabalho", [])
    em = [x for x in trab if not x.get("fim")]
    ult_at = max((_d(a["periodo_fim"]) for a in f.get("atestados", []) if _d(a["periodo_fim"])), default=None)
    if em:
        x = em[-1]
        ini = _dp(x["inicio"])
        desde = max(ini, ult_at + timedelta(days=1)) if (ini and ult_at and ult_at >= ini) else ini
        dias = (hoje - desde).days if desde else 0
        out["fd_trab"] = "%s desde %s%s" % (x.get("empresa") or x.get("setor") or "?", x["inicio"], " (externo)" if x.get("externo") else "")
        out["fd_atestar"] = ("≈ %d dias (≈ %d remidos) desde %s" % (dias, dias // 3, rs.fmt(desde))) if dias >= 30 else "atestado em dia"
        add("Trabalho atual", out["fd_trab"], "", ("Sem atestado desde %s: ≈ %d dias trabalhados, ≈ %d remidos a requerer" % (rs.fmt(desde), dias, dias // 3)) if dias >= 30 else "Atestado em dia",
            "amarelo" if dias >= 30 else "verde")
        if dias >= 30 and cor_geral != "vermelho":
            cor_geral, sit_geral = "amarelo", "A atestar (≈ %d dias)" % dias
    else:
        out["fd_trab"] = "sem trabalho em curso"
        add("Trabalho atual", "sem trabalho em curso" + ((" (último: %s até %s)" % (trab[-1].get("empresa") or trab[-1].get("setor"), trab[-1].get("fim"))) if trab else ""), "", "", "")
    hist = "; ".join("%s a %s: %s" % (t["inicio"], t.get("fim") or "em curso", t.get("empresa") or t.get("setor")) for t in trab)
    if hist:
        add("Histórico de trabalho", hist, "", "%d período(s)" % len(trab), "")
    # faltas
    faltas = f.get("faltas", [])
    rec = []
    for fa in faltas:
        dfato = _dp(fa["data_fato"]) or _dp(fa["data_registro"])
        r12 = bool(dfato and (hoje - dfato).days <= 365)
        txt = "%s · %s · %s%s" % (fa["data_fato"], fa["artigo"] or "art. n/i", fa["situacao"], (" · PADIC " + fa["padic"]) if fa.get("padic") else "")
        if fa["situacao"] == "arquivada":
            add("Falta disciplinar", txt, r.get("falta_12m_detalhe") or "sem indício de falta", "Arquivada: não pode gerar regressão, perda de remidos nem contar nos 12 meses", "verde" if not r12 else "amarelo")
            if r12:
                rec.append(fa)
        else:
            add("Falta disciplinar", txt, r.get("falta_12m_detalhe") or "sem indício de falta",
                ("Nos últimos 12 meses: impede livramento (art. 83, III, b) e indulto (art. 6º) e pode regredir/alterar data-base" if r12 else "Há mais de 12 meses") if fa["grave"] else "Falta média/leve",
                "vermelho" if (r12 and fa["grave"]) else "amarelo")
            if r12 and fa["grave"]:
                rec.append(fa)
                cor_geral, sit_geral = "vermelho", "Falta grave nos 12 meses"
    if not faltas:
        add("Faltas disciplinares", "nenhuma na ficha", r.get("falta_12m_detalhe") or "sem indício", "Sem falta", "verde")
    out["fd_faltas"] = ("%d (%s)" % (len(faltas), ", ".join(x["situacao"] for x in faltas))) if faltas else "nenhuma"
    if r.get("falta_12m") == "SIM" and not any(fa["situacao"] != "arquivada" for fa in faltas):
        add("Indício de falta no RSPE", "nenhuma falta vigente na ficha", r.get("falta_12m_detalhe", ""), "RSPE sugere falta (regressão/perda de remidos), mas a ficha não confirma - conferir", "amarelo")
    # regressão / restabelecimento
    for x in f.get("restabelecimentos", []):
        add("Restabelecimento de regime", x, "regime atual: " + (r.get("regime_atual") or "?").replace(" - ATIVO", ""), "Conferir se a regressão cautelar foi baixada no RSPE e a data-base preservada", "amarelo")
    for x in f.get("regressoes", []):
        add("Regressão (ficha)", x, "", "", "")
    for x in f.get("recusa_trabalho", []):
        add("Recusa de trabalho", x, "", "Relevante para o exame de mérito", "")
    add("Conduta", f.get("conduta") or "—", "", "", "verde" if (f.get("conduta") or "").startswith(("OT", "BO")) else "")
    add("Unidade / entrada", "%s · %s" % (f.get("unidade") or "?", f.get("data_entrada") or "?"), (r.get("vara") or ""), "", "")
    add("Ficha impressa em", f.get("data_impressao") or "?", "RSPE de " + (r.get("data_geracao_rspe") or "?"), "", "")
    out.update(fd_cor=cor_geral, fd_sit=sit_geral, fd_conduta=f.get("conduta") or "", fd_linhas=L)
    return out
