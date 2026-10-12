"""Calculadora de penas (botão "Calculadora" no topo de todas as abas). Reproduz a Calculadora de penas 2.1 (Guilherme
Benages Alcantara, 2001, distribuição livre): soma e subtração de penas, período entre datas, término e frações, com os dias
remidos descontados antes ou depois da fração; acrescenta os percentuais do art. 112 da LEP.

Convenções (as do SEEU e do resto do programa):
- soma de penas por componente: 30 dias = 1 mês, 12 meses = 1 ano;
- fração sobre a pena em dias (ano de 365, mês de 30 - rspe_scraper.pena_para_dias), arredondada para baixo;
- datas pelo calendário: anos e meses no calendário (dia inexistente no mês vai ao último dia), dias corridos;
- o dia do começo entra na conta (CP, art. 10): o término e as frações caem no último dia (início + pena - 1 dia);
- interrupção soma-se pelo calendário; remidos e detração descontam-se em dias."""
import calendar
import re
from datetime import date, timedelta
from fractions import Fraction

import rspe_scraper as rs

FRACOES = ["1/6", "1/5", "1/4", "1/3", "1/2", "2/3"]
PERCENTUAIS = ["16%", "20%", "25%", "30%", "40%", "50%", "60%", "70%"]


def _int(v):
    try:
        return int(str(v).strip() or 0)
    except ValueError:
        return 0


def amd(p):
    """{'a','m','d'} (strings ou números) -> (a, m, d) inteiros, sem negativos."""
    p = p or {}
    return tuple(max(0, _int(p.get(k))) for k in ("a", "m", "d"))


def normal(total):
    """Total em 'dias de 30' (a*360 + m*30 + d) -> (a, m, d)."""
    total = max(0, total)
    return total // 360, total % 360 // 30, total % 30


def soma_penas(fita):
    """[{'s': 1|-1, 'p': {a,m,d}}] -> (a, m, d): soma por componente, normalizada (30 dias = 1 mês, 12 meses = 1 ano)."""
    t = 0
    for x in fita or []:
        a, m, d = amd(x.get("p"))
        t += (1 if _int(x.get("s", 1)) >= 0 else -1) * (a * 360 + m * 30 + d)
    return normal(t)


def mais(dt, a, m, d, sinal=1):
    """Data + a anos, m meses (calendário; dia inexistente vai ao último do mês) e d dias corridos."""
    y, mo = dt.year + sinal * a, dt.month - 1 + sinal * m
    y, mo = y + mo // 12, mo % 12 + 1
    return date(y, mo, min(dt.day, calendar.monthrange(y, mo)[1])) + timedelta(days=sinal * d)


def entre(a, b):
    """Período de a até b, contando o dia do começo (CP, art. 10): ((anos, meses, dias), dias corridos) ou None."""
    if not a or not b or b < a:
        return None
    fim = b + timedelta(days=1)  # o dia final também conta

    def aniv(y_, m_):
        # dia inexistente no mês de chegada (29/02, 31/04...): o período completa no dia seguinte ao último do mês
        x = mais(a, y_, m_, 0)
        return x + timedelta(days=1) if x.day < a.day else x
    y, m = fim.year - a.year, fim.month - a.month
    if m < 0:
        y, m = y - 1, m + 12
    while (y > 0 or m > 0) and aniv(y, m) > fim:
        m -= 1
        if m < 0:
            y, m = y - 1, m + 12
    d = (fim - aniv(y, m)).days
    return (y, m, d), (b - a).days + 1


def fracao(txt):
    """'1/6', '2/5', '16%', '16,5%' -> Fraction; inválida -> None."""
    t = (txt or "").strip().replace(",", ".")
    m = re.match(r"^(\d+)\s*/\s*(\d+)$", t)
    if m and int(m.group(2)) and 0 < int(m.group(1)) <= int(m.group(2)):
        return Fraction(int(m.group(1)), int(m.group(2)))
    m = re.match(r"^(\d+(?:\.\d+)?)\s*%$", t)
    if m and 0 < float(m.group(1)) <= 100:
        return Fraction(m.group(1)) / 100
    return None


def txt(p):
    return "%da%dm%dd" % p


def extenso(p):
    return rs.pena_extenso(txt(p)) if any(p) else "0 dia"


def calcular(e):
    """Estado da janela -> resultado. e: {'fita': [...], 'inicio': 'dd/mm/aaaa', 'interr': {a,m,d}, 'rem': dias,
    'rem_modo': 'antes'|'depois', 'outra': '2/5', 'p1': data, 'p2': data}."""
    e = e or {}
    P = soma_penas(e.get("fita"))
    out = {"total": txt(P), "total_ext": extenso(P), "erros": []}
    _bruto = sum((1 if _int(x.get("s", 1)) >= 0 else -1) * (lambda t: t[0] * 360 + t[1] * 30 + t[2])(amd(x.get("p"))) for x in e.get("fita") or [])
    if _bruto < 0:
        out["erros"].append("A subtração deixa a pena negativa: o total foi considerado zero.")
    if (e.get("outra") or "").strip() and fracao(e["outra"]) is None:
        out["erros"].append("Outra fração inválida: use 2/5 ou 55%.")
    p1, p2 = rs.to_date(e.get("p1") or ""), rs.to_date(e.get("p2") or "")
    if e.get("p1") and not p1 or e.get("p2") and not p2:
        out["erros"].append("Data do período inválida: use dd/mm/aaaa.")
    pe = entre(p1, p2)
    if p1 and p2 and not pe:
        out["erros"].append("No período, a data final é anterior à inicial.")
    if pe:
        out["periodo"] = {"amd": txt(pe[0]), "ext": extenso(pe[0]), "dias": pe[1], "a": pe[0][0], "m": pe[0][1], "d": pe[0][2]}
    ini = rs.to_date(e.get("inicio") or "")
    if e.get("inicio") and not ini:
        out["erros"].append("Data de início inválida: use dd/mm/aaaa.")
    I = amd(e.get("interr"))
    rem = max(0, _int(e.get("rem")))
    dias = rs.pena_para_dias(txt(P)) or 0
    if not ini or not dias:
        return out
    out["termino"] = rs.fmt(mais(mais(ini, *P), *I) - timedelta(days=rem + 1))
    out["termino_det"] = "início %s + pena %s%s%s - 1 dia (CP, art. 10)" % (
        rs.fmt(ini), extenso(P), (" + interrupção %s" % extenso(I)) if any(I) else "", (" - %s" % rs.pl(rem, "dia remido/detraído", "dias remidos/detraídos")) if rem else "")
    antes = (e.get("rem_modo") or "antes") != "depois"

    def fr(f):
        base = max(0, dias - rem) if antes else dias
        q = rs.pena_amd(rs.dias_para_pena(int(base * f)))
        dt = mais(mais(ini, *q), *I) - timedelta(days=1 + (0 if antes else rem))
        return {"q": txt(q), "data": rs.fmt(dt)}
    out["fracoes"] = [dict(fr(fracao(r)), rot=r) for r in FRACOES]
    out["percentuais"] = [dict(fr(fracao(r)), rot=r) for r in PERCENTUAIS]
    if (e.get("outra") or "").strip():
        f = fracao(e["outra"])
        if f is not None:
            out["outra"] = dict(fr(f), rot=e["outra"].strip())
    return out


def texto(e, r):
    """Cálculo em texto corrido (botão Copiar e registro)."""
    L = []
    if e.get("assist"):
        L.append("Assistido: %s" % e["assist"])
    pen = [("%s %s" % ("+" if _int(x.get("s", 1)) >= 0 else "-", extenso(amd(x.get("p"))))) for x in e.get("fita") or []]
    L.append("Pena total: %s%s" % (r.get("total_ext", ""), (" (%s)" % ", ".join(pen)) if len(pen) > 1 else ""))
    if e.get("inicio"):
        L.append("Início: %s" % e["inicio"])
    if any(amd(e.get("interr"))):
        L.append("Interrupção: %s" % extenso(amd(e.get("interr"))))
    if _int(e.get("rem")):
        L.append("Remidos/detração: %s, descontados %s da fração" % (rs.pl(_int(e["rem"]), "dia", "dias"), "depois" if e.get("rem_modo") == "depois" else "antes"))
    if r.get("termino"):
        L.append("Término da pena: %s" % r["termino"])
        L.append("Frações (data em que completa): " + "; ".join("%s em %s (%s)" % (x["rot"], x["data"], rs.pena_extenso(x["q"])) for x in r["fracoes"]))
        L.append("Percentuais (LEP, art. 112): " + "; ".join("%s em %s" % (x["rot"], x["data"]) for x in r["percentuais"]))
        if r.get("outra"):
            L.append("Fração %s: %s (%s)" % (r["outra"]["rot"], r["outra"]["data"], rs.pena_extenso(r["outra"]["q"])))
    if r.get("periodo"):
        L.append("Período de %s a %s: %s (%d dias)" % (e.get("p1"), e.get("p2"), r["periodo"]["ext"], r["periodo"]["dias"]))
    if e.get("nota"):
        L.append("Anotação: %s" % e["nota"].strip())
    return "\n".join(L)
