# -*- coding: utf-8 -*-
"""
Linha do tempo de indulto e comutação (aba Indulto / Comutação, opção "Verificar indulto/comutação").

Uma linha só por assistido (LEP, art. 111: penas somadas ou unificadas); cada crime recebe uma etiqueta (C1, C2...)
que acompanha os marcos, as faixas e as contas. A linha é a própria memória de cálculo: tudo o que o resultado usa
vem daqui, com o evento do SEEU, o período, o tratamento, o fundamento e a conta de cada dado.

Regras fixas desta aba (não parametrizáveis):
- falta grave não interrompe o prazo para indulto e comutação (STJ, Súmula 535): o tempo cumprido nunca é zerado
  nem reiniciado aqui; a falta só pesa no requisito subjetivo, dentro da janela do decreto;
- nada se presume: natureza do crime, homologação da falta, atribuição de prisão, reincidência e decreto não
  cadastrado viram "A VERIFICAR" no ponto exato da linha.

Frações, janelas, vedações, limites e datas de cada decreto vêm da base jurídica (decretos_linha); decreto sem
cadastro dá "A VERIFICAR", nunca aplicação por analogia com outro decreto.
"""

from datetime import date, timedelta
from fractions import Fraction
import re

import rspe_scraper as rs
import rspe_regras as rg
import rspe_prescricao as rp

CORES = ["#2563EB", "#D97706", "#7C3AED", "#059669", "#DB2777", "#0891B2", "#65A30D", "#B42318", "#475467", "#9E77ED"]
RE_PROV = re.compile(r"FLAGRANTE|PREVENTIV|TEMPOR|PROVIS", re.I)
RE_FUGA = re.compile(r"FUGA|EVAS|ABANDON|FORAGID|N[ÃA]O RETORN", re.I)
RE_UNIF = re.compile(r"UNIFICA|SOMA DE PENA|SOMA DAS PENAS", re.I)
RE_REGIME = re.compile(r"REGIME", re.I)


def _f(d):
    return rs.fmt(d) if d else ""


def _d(t):
    """dd/mm/aaaa (SEEU) ou aaaa-mm-dd (base jurídica) -> date."""
    if not t:
        return None
    if re.match(r"\d{4}-\d{2}-\d{2}$", str(t)):
        return rg.d(t)
    return rs.to_date(t)


def _pena(n):
    """'2a8m0d' (convenção do SEEU: ano 365, mês 30)."""
    return rs.dias_para_pena(max(0, int(n or 0)))


def _fr(txt):
    return rg.fr(txt) if txt else None


def _meses_antes(d, meses):
    y, m = divmod(d.month - 1 - int(meses), 12)
    y += d.year
    m += 1
    import calendar
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _det(evento="", crime="", periodo="", tratamento="", fundamento="", calculo="", efeito=""):
    """Bloco do "Como cheguei aqui?"."""
    return {"evento": evento, "crime": crime, "periodo": periodo, "tratamento": tratamento,
            "fundamento": fundamento, "calculo": calculo, "efeito": efeito}


def _tipificacao(c):
    art = rs.num_art(c.get("artigo")) or "n/i"
    par = rs.paragrafo_texto(c) if hasattr(rs, "paragrafo_texto") else ""
    return "Art. %s%s, %s" % (art, (" " + par) if par else "", rs.lei_curta(c.get("lei")) or "CP")


def _nome(c):
    try:
        return rs.nome_crime(c) or ""
    except Exception:
        return ""


# --------------------------------------------------------------------------- #
# natureza do crime diante de cada decreto
# --------------------------------------------------------------------------- #

def _trafico_incerto(c):
    """Tráfico (art. 33 da Lei 11.343) sem indicação de caput/§ 1º nem dos §§ 2º a 4º: não se classifica por presunção."""
    if rs.num_lei(c.get("lei")) != "11343" or rs.num_art(c.get("artigo")) != "33":
        return False
    txt = " ".join(str(c.get(k) or "") for k in ("tipo_penal", "artigo", "artigo_rspe"))
    if re.search(r"§\s*[234](?!\d)|PRIVILEGI", txt, re.I):
        return False
    if re.match(r"\s*(CAPUT|§\s*1)", c.get("tipo_penal") or "", re.I):
        return False
    return True


def natureza(c, D, ref):
    """{selo: IMPEDITIVO | NAO_IMPEDITIVO | A_VERIFICAR, motivo, dispositivo} do crime diante do decreto D."""
    regra = (D.get("vedacoes") or {}).get("regra")
    num = D.get("numero", "")
    if regra in ("art1_2024_2025", "art7_2022") and _trafico_incerto(c):
        return {"selo": "A_VERIFICAR", "motivo": "tráfico (art. 33 da Lei 11.343/06) sem indicação, no SEEU, de caput/§ 1º ou do § 4º (tráfico privilegiado)",
                "dispositivo": "Decreto %s, %s (só caput e § 1º; § 4º fora - STJ, Tema 1336; STF, Tema 1400)" % (num, "art. 1º, XVIII" if regra == "art1_2024_2025" else "art. 7º, I e VI"),
                "se_sim": "caput ou § 1º: IMPEDITIVO", "se_nao": "§ 4º (privilegiado): NÃO IMPEDITIVO"}
    if regra == "art1_2024_2025":
        imp = rs.impeditivo_decreto(c, ref)
        if imp:
            return {"selo": "IMPEDITIVO", "motivo": imp[1], "dispositivo": "Decreto %s, art. 1º, %s" % (num, imp[0])}
    elif regra == "art7_2022":
        exc = rs.exclusao_art7_2022(c)
        if exc:
            return {"selo": "IMPEDITIVO", "motivo": exc.split(":", 1)[-1].strip(), "dispositivo": "Decreto %s, art. 7º, %s" % (num, exc.split(":")[0])}
        if (c.get("vga") or "") not in ("S", "N"):
            return {"selo": "A_VERIFICAR", "motivo": "o SEEU não informa se houve violência ou grave ameaça",
                    "dispositivo": "Decreto %s, art. 7º, II" % num, "se_sim": "com VGA: IMPEDITIVO", "se_nao": "sem VGA: NÃO IMPEDITIVO"}
    else:
        return {"selo": "A_VERIFICAR", "motivo": "vedações do decreto não cadastradas", "dispositivo": "Decreto %s" % (num or "?")}
    lei, art = rs.num_lei(c.get("lei")), rs.num_art(c.get("artigo"))
    if lei in ("2848", "") and art in rs.HEDIONDOS_CONDICIONAIS and rs.hediondo_condicional(c) is None and not rs.e_hediondo(c, ref):
        return {"selo": "A_VERIFICAR", "motivo": "a hediondez do art. %s depende de parágrafo, inciso ou majorante que o SEEU não informa" % art,
                "dispositivo": "Lei 8.072/90, art. 1º; Decreto %s (vedação ao hediondo)" % num,
                "se_sim": "forma hedionda: IMPEDITIVO", "se_nao": "forma simples: NÃO IMPEDITIVO"}
    v = rs.impeditivo_verificar(c)
    if v:
        return {"selo": "A_VERIFICAR", "motivo": v, "dispositivo": "Decreto %s" % num}
    return {"selo": "NAO_IMPEDITIVO", "motivo": "não consta do rol de vedações", "dispositivo": "Decreto %s, %s" % (num, (D.get("vedacoes") or {}).get("dispositivo", ""))}


def _natureza_txt(c):
    if rs.e_hediondo(c):
        return "hediondo ou equiparado"
    if (c.get("vga") or "") == "S":
        return "com violência ou grave ameaça"
    if (c.get("vga") or "") == "N":
        return "sem violência ou grave ameaça"
    return "violência/grave ameaça não informada"


def _reinc_txt(c):
    if c.get("reincidente_especifico") == "S":
        return "reincidente específico"
    if c.get("reincidente_comum") == "S":
        return "reincidente"
    if c.get("reincidente_comum") == "N":
        return "primário"
    return "reincidência não informada"


# --------------------------------------------------------------------------- #
# dias da execução classificados (um dia conta uma vez só)
# --------------------------------------------------------------------------- #

PRIORIDADE = {"cumprimento": 4, "detracao": 4, "livramento": 3, "nao_comprovado": 1}
CONTA = ("cumprimento", "detracao", "livramento")


class Dias:
    """Mapa dia -> (tipo, fonte, crimes). Cumprimento e detração contam; livramento conta; não comprovado não soma."""

    def __init__(self):
        self.m = {}

    def marcar(self, a, b, tipo, fonte, crimes):
        d = a
        while d <= b:
            o = d.toordinal()
            atual = self.m.get(o)
            if not atual or PRIORIDADE[tipo] > PRIORIDADE[atual[0]]:
                self.m[o] = (tipo, fonte, crimes)
            d += timedelta(days=1)

    def ate(self, ref):
        """{tipo: dias} contados até ref (inclusive)."""
        o = ref.toordinal()
        out = {"cumprimento": 0, "detracao": 0, "livramento": 0, "nao_comprovado": 0}
        for k, v in self.m.items():
            if k <= o:
                out[v[0]] += 1
        return out

    def faixas(self):
        """Dias consecutivos de mesmo tipo e fonte viram faixas [(ini, fim, tipo, fonte, crimes)]."""
        out = []
        for o in sorted(self.m):
            t, f, cr = self.m[o]
            if out and out[-1][2] == t and out[-1][3] == f and out[-1][1] == o - 1:
                out[-1][1] = o
            else:
                out.append([o, o, t, f, cr])
        return [(date.fromordinal(a), date.fromordinal(b), t, f, cr) for a, b, t, f, cr in out]


# --------------------------------------------------------------------------- #
# montagem
# --------------------------------------------------------------------------- #

def linha(r, hoje=None):
    hoje = hoje or date.today()
    crimes_all = r.get("_crimes", []) or []
    eventos = r.get("_eventos", []) or []
    incidentes = r.get("_incidentes", []) or []
    ativos = [c for c in crimes_all if not (c.get("extinto") or "").upper().startswith("S")]
    decretos = rg.decretos_linha()
    duvidas = []

    # ---- crimes (etiquetas) ----
    C = []
    for i, c in enumerate(ativos):
        C.append({"id": "C%d" % (i + 1), "cor": CORES[i % len(CORES)], "proc": c.get("processo_criminal") or "",
                  "tipificacao": _tipificacao(c), "nome": _nome(c), "fato": c.get("data_infracao") or "",
                  "sentenca": c.get("data_sentenca") or "", "transito": c.get("transito_processo") or c.get("transito_mp") or "",
                  "pena": _pena(rs.pena_para_dias(c.get("pena_imposta")) or 0), "pena_dias": rs.pena_para_dias(c.get("pena_imposta")) or 0,
                  "natureza": _natureza_txt(c), "reinc": _reinc_txt(c), "selos": {}, "_c": c})
    por_proc = {}
    for x in C:
        por_proc.setdefault(rs.chave_processo(x["proc"]), []).append(x["id"])

    def crimes_de(procs):
        lst = rs.lista_processos(procs)
        if not lst:
            return []
        ids = []
        for p in lst:
            for x in C:
                if rp._mesmo_processo(x["proc"], p):
                    ids.append(x["id"])
        return list(dict.fromkeys(ids))

    def termo_de(ids):
        ts = [_d(x["transito"]) for x in C if x["id"] in ids and _d(x["transito"])] if ids else \
             [_d(x["transito"]) for x in C if _d(x["transito"])]
        return min(ts) if ts else None

    # ---- períodos ----
    dias = Dias()
    marcos = []
    for (a, b, motivo, procs) in rs.periodos_custodia_detalhe(eventos):
        fim = (b or hoje)
        ids = crimes_de(procs)
        liga = (not rs.lista_processos(procs)) or bool(ids)
        rot_ids = ids or ["GERAL"]
        mot = (motivo or "prisão").strip()
        fonte = "%s de %s%s" % (mot.lower(), _f(a), (" (processo %s)" % procs) if procs else " (sem processo indicado)")
        if not liga:
            dias.marcar(a, fim, "nao_comprovado", fonte, [])
            duvidas.append({"data": _f(a), "crime": "GERAL", "texto": "O SEEU registra %s de %s a %s pelo processo %s, que não é nenhuma das condenações desta execução. "
                            "Não foi somado: conferir se esse tempo foi computado aqui (detração, LEP, art. 111)." % (mot.lower(), _f(a), _f(b) or "hoje", procs)})
            continue
        prov = RE_PROV.search(mot) is not None
        t = termo_de(ids)
        if prov and t and a < t:
            dias.marcar(a, min(fim, t - timedelta(days=1)), "detracao", fonte, rot_ids)
            if fim >= t:
                dias.marcar(t, fim, "cumprimento", fonte + ", depois do trânsito em %s" % _f(t), rot_ids)
        elif prov and not t:
            dias.marcar(a, fim, "detracao", fonte + " - trânsito não consta", rot_ids)
        else:
            dias.marcar(a, fim, "cumprimento", fonte, rot_ids)
        marcos.append({"data": _f(a), "tipo": "prisao", "rotulo": ("Prisão provisória" if prov else "Início/reinício do cumprimento"),
                       "sub": mot.lower(), "crimes": rot_ids,
                       "efeito": "conta como pena cumprida (detração, CP, art. 42)" if prov else "conta como pena cumprida",
                       "det": _det("%s em %s%s" % (mot, _f(a), (" - processos: " + procs) if procs else ""), ", ".join(rot_ids),
                                   "%s → %s" % (_f(a), _f(b) or "hoje"), "detração" if prov else "cumprimento",
                                   "CP, art. 42; LEP, art. 111" if prov else "LEP, arts. 66, III, a, e 111",
                                   "%s dias até %s" % ((fim - a).days + 1, _f(b) or "hoje"),
                                   "soma no tempo cumprido para indulto/comutação")})
    for (a, b) in rs.periodos_livramento(eventos, incidentes):
        dias.marcar(a, b or hoje, "livramento", "livramento condicional de %s" % _f(a), ["GERAL"])
        marcos.append({"data": _f(a), "tipo": "livramento", "rotulo": "Livramento condicional", "sub": "período de prova", "crimes": ["GERAL"],
                       "efeito": "o período de prova conta como pena cumprida",
                       "det": _det("livramento condicional concedido em %s" % _f(a), "GERAL", "%s → %s" % (_f(a), _f(b) or "hoje"), "cumprimento (período de prova)",
                                   "CP, arts. 83 e 89; LEP, art. 146; decretos 2024/2025, art. 2º, III", "", "soma no tempo cumprido")})

    # interrupções: fuga/evasão (não conta) e demais
    faixas_dias = dias.faixas()
    ini_exec = min((a for a, _, t, _, _ in faixas_dias if t in CONTA), default=None)
    gaps = []
    if ini_exec:
        contam = [(a, b) for a, b, t, _, _ in faixas_dias if t in CONTA]
        cur = ini_exec
        for a, b in sorted(contam):
            if a > cur + timedelta(days=1):
                gaps.append((cur + timedelta(days=1), a - timedelta(days=1)))
            cur = max(cur, b)
        if cur < hoje:
            gaps.append((cur + timedelta(days=1), hoje))
    faixas = []
    for a, b, t, f, cr in faixas_dias:
        trat = {"cumprimento": "cumprimento", "detracao": "prisão provisória / detração", "livramento": "cumprimento (livramento)",
                "nao_comprovado": "período não comprovado"}[t]
        fund = {"cumprimento": "LEP, art. 111 (execução unificada)", "detracao": "CP, art. 42 (detração); decretos 2024/2025, art. 5º",
                "livramento": "CP, art. 89; LEP, art. 146", "nao_comprovado": "LEP, art. 111 - atribuição não comprovada no SEEU"}[t]
        n = (b - a).days + 1
        faixas.append({"tipo": t, "ini": _f(a), "fim": _f(b), "aberta": b >= hoje and t != "nao_comprovado", "crimes": cr, "dias": n,
                       "det": _det(f, ", ".join(cr) or "-", "%s → %s" % (_f(a), _f(b)), trat, fund, "%s → %s = %d dias (contagem do SEEU: inclui o 1º e o último dia)" % (_f(a), _f(b), n),
                                   "não soma no cumprido" if t == "nao_comprovado" else "soma %d dias no cumprido" % n)})
    for g0, g1 in gaps:
        mot = rp._motivo_interrupcao(eventos, incidentes, g0 - timedelta(days=1)) or rp._motivo_interrupcao(eventos, incidentes, g0)
        fuga = bool(mot and RE_FUGA.search(mot))
        n = (g1 - g0).days + 1
        faixas.append({"tipo": "fuga" if fuga else "liberdade", "ini": _f(g0), "fim": _f(g1), "aberta": g1 >= hoje, "crimes": ["GERAL"], "dias": n,
                       "det": _det("interrupção em %s (%s)" % (_f(g0 - timedelta(days=1)), (mot or "motivo não consta").lower()), "GERAL",
                                   "%s → %s" % (_f(g0), "hoje" if g1 >= hoje else _f(g1)), "fuga / evasão" if fuga else "fora do cumprimento",
                                   "LEP, art. 50, II; o tempo fora não é pena cumprida", "%d dias fora do cumprimento" % n, "não soma no cumprido")})
        if fuga or not mot:
            marcos.append({"data": _f(g0 - timedelta(days=1)), "tipo": "fuga", "rotulo": "Fuga / evasão" if fuga else "Interrupção", "sub": (mot or "motivo não consta").lower(),
                           "crimes": ["GERAL"], "efeito": "o tempo fora não conta; não zera o cumprido (Súmula 535/STJ)",
                           "det": _det("interrupção do cumprimento em %s (%s)" % (_f(g0 - timedelta(days=1)), (mot or "motivo não consta").lower()), "GERAL",
                                       "%s → %s" % (_f(g0), "hoje" if g1 >= hoje else _f(g1)), "fuga / evasão",
                                       "STJ, Súmula 535 (a falta não interrompe o prazo do indulto e da comutação)", "", "o período fora não soma")})
            if g1 < hoje:
                marcos.append({"data": _f(g1 + timedelta(days=1)), "tipo": "recaptura", "rotulo": "Recaptura / reinício", "sub": "", "crimes": ["GERAL"],
                               "efeito": "o cumprimento volta a contar", "det": _det("reinício em %s" % _f(g1 + timedelta(days=1)), "GERAL", "", "cumprimento", "LEP, art. 111", "", "volta a somar")})

    # ---- remições e perdas ----
    remicoes = []
    for i in incidentes:
        dt = _d(i.get("data_referencia") or i.get("data_decisao"))
        t = (i.get("tipo") or "").upper()
        if rs.e_remicao_concedida(i):
            n = rs.dias_de(i.get("complemento", ""))
            if n is None:
                duvidas.append({"data": _f(dt), "crime": "GERAL", "texto": "Remição concedida em %s sem quantidade de dias legível no SEEU: não somada." % (_f(dt) or "?")})
                continue
            remicoes.append((dt, n, "remicao", i))
        elif re.search(r"PERD", t) and re.search(r"REMI", t) and (i.get("situacao") or "CONCEDIDO") == "CONCEDIDO":
            n = rs.dias_de(i.get("complemento", "")) or rs.dias_de(i.get("complemento", ""), r"dias?")
            if n:
                remicoes.append((dt, -n, "perda", i))
    for dt, n, k, i in remicoes:
        marcos.append({"data": _f(dt), "tipo": "remicao" if n > 0 else "perda", "rotulo": ("Remição +%s" if n > 0 else "Perda de remidos %s") % rs.pl(abs(int(n)), "dia", "dias"),
                       "sub": "", "crimes": ["GERAL"], "efeito": "soma no cumprido (LEP, art. 128)" if n > 0 else "reduz a remição (LEP, art. 127)",
                       "det": _det("%s - %s (decisão de %s)" % (i.get("tipo") or "", i.get("complemento") or "", i.get("data_decisao") or "?"), "GERAL", _f(dt),
                                   "remição" if n > 0 else "perda de dias remidos", "LEP, art. 128 (remição é pena cumprida)" if n > 0 else "LEP, art. 127",
                                   "%+g dias" % n, "entra no cumprido a partir de %s" % _f(dt))})

    def cumprido(ref):
        c = dias.ate(ref)
        rem = sum(n for dt, n, k, _ in remicoes if dt and dt <= ref and n > 0)
        per = -sum(n for dt, n, k, _ in remicoes if dt and dt <= ref and n < 0)
        tot = c["cumprimento"] + c["livramento"] + c["detracao"] + rem - per
        return {"cumprimento": c["cumprimento"] + c["livramento"], "detracao": c["detracao"], "remicao": rem, "perda": per,
                "nao_comprovado": c["nao_comprovado"], "total": max(0, int(tot))}

    em_curso = any(f["aberta"] and f["tipo"] in CONTA for f in faixas)

    def data_atinge(alvo):
        """Data em que o cumprido alcança 'alvo' dias: real (passado) ou projeção (cumprimento em curso, 1 dia por dia)."""
        if alvo <= 0:
            return ini_exec, False
        extra = sorted([(dt, n) for dt, n, _, _ in remicoes if dt])
        tot = 0
        ords = sorted(o for o, v in dias.m.items() if v[0] in CONTA)
        ri = 0
        for o in ords:
            d = date.fromordinal(o)
            while ri < len(extra) and extra[ri][0] <= d:
                tot += extra[ri][1]
                ri += 1
            tot += 1
            if tot >= alvo:
                return d, d > hoje
        falta = alvo - cumprido(hoje)["total"]
        if em_curso and falta > 0:
            return hoje + timedelta(days=int(falta)), True
        return None, False

    # ---- fatos, sentenças, trânsitos, unificações, regimes, faltas ----
    for x in C:
        c = x["_c"]
        for campo, tipo, rot in (("data_infracao", "fato", "Fato"), ("data_sentenca", "sentenca", "Sentença"), ("transito_processo", "transito", "Trânsito em julgado")):
            dt = _d(c.get(campo))
            if not dt and campo == "transito_processo":
                dt = _d(c.get("transito_mp"))
            if dt:
                marcos.append({"data": _f(dt), "tipo": tipo, "rotulo": "%s %s" % (rot, x["id"]), "sub": x["tipificacao"], "crimes": [x["id"]],
                               "efeito": {"fato": "o decreto só alcança fato anterior à sua data", "sentenca": "condenação posterior à publicação fica fora da soma",
                                          "transito": "prisão anterior a esta data é provisória (detração)"}[tipo],
                               "det": _det("%s - processo %s" % (rot, x["proc"]), "%s · %s" % (x["id"], x["proc"]), _f(dt), rot.lower(), "", "", "")})
    for i in incidentes:
        t = (i.get("tipo") or "")
        dt = _d(i.get("data_referencia") or i.get("data_decisao"))
        if not dt or (i.get("situacao") or "CONCEDIDO") != "CONCEDIDO":
            continue
        if RE_UNIF.search(t + " " + (i.get("complemento") or "")):
            marcos.append({"data": _f(dt), "tipo": "unificacao", "rotulo": "Unificação/soma de penas", "sub": (i.get("complemento") or "")[:60], "crimes": ["GERAL"],
                           "efeito": "penas somadas (LEP, art. 111): uma execução só",
                           "det": _det("%s (decisão %s)" % (t, i.get("data_decisao") or "?"), "GERAL", _f(dt), "unificação", "LEP, art. 111", "", "a pena considerada é a soma")})
    faltas = []
    for i in incidentes:
        rot = rs._rotulo_incidente(i)
        if not rs.RE_FALTA_PROPRIA.search(rot) or rs._negado(i):
            continue
        fato = rs._data_fato_falta(i)
        homol = _d(i.get("data_decisao")) if not rs._pendente(i) else None
        faltas.append({"fato": fato, "homol": homol, "pendente": rs._pendente(i), "texto": rot})
    for e in eventos:
        tt = " ".join(("%s %s" % (e.get("tipo", ""), e.get("motivo", ""))).split())
        d0 = _d(e.get("data"))
        if d0 and RE_FUGA.search(tt) and not any(f["fato"] and abs((f["fato"] - d0).days) <= 1 for f in faltas):
            faltas.append({"fato": d0, "homol": None, "pendente": True, "texto": tt + " (registrada só como evento; falta a apurar)"})

    # ---- decretos ----
    ult_cad = max((D for D in decretos if D.get("cadastrado")), key=lambda D: _d(D.get("referencia")) or date.min, default=None)
    saida_dec = []
    for D in sorted(decretos, key=lambda D: _d(D.get("referencia")) or date.min):
        ref, pub = _d(D.get("referencia")), _d(D.get("publicacao"))
        if not ref or ref > hoje:
            continue
        if ini_exec and ref < ini_exec and not any(_d(x["fato"]) and _d(x["fato"]) <= ref for x in C):
            continue
        saida_dec.append(_decreto(D, ref, pub, C, cumprido, data_atinge, faltas, hoje, D is ult_cad, em_curso, duvidas))
    for dd in saida_dec:
        marcos.append({"data": dd["referencia"], "tipo": "decreto", "rotulo": "Decreto %s" % dd["numero"], "sub": "data de referência", "crimes": ["GERAL"],
                       "efeito": dd["indulto"]["rotulo"], "decreto": dd["id"],
                       "det": _det("Decreto %s - publicação %s, data de referência %s" % (dd["numero"], dd["publicacao"] or "não cadastrada", dd["referencia"]), "GERAL",
                                   dd["referencia"], "data de referência do decreto", dd.get("fonte", ""), "", dd["indulto"]["rotulo"])})
        if dd.get("publicacao") and dd["publicacao"] != dd["referencia"]:
            marcos.append({"data": dd["publicacao"], "tipo": "publicacao", "rotulo": "Publicação %s" % dd["numero"], "sub": "", "crimes": ["GERAL"],
                           "efeito": "falta posterior à publicação não impede; sentença posterior fica fora da soma", "decreto": dd["id"],
                           "det": _det("publicação no DOU", "GERAL", dd["publicacao"], "publicação", "", "", "")})
    for f in faltas:
        if not f["fato"]:
            continue
        marcos.append({"data": _f(f["fato"]), "tipo": "falta", "rotulo": "Falta grave" if not f["pendente"] else "Falta (não homologada)",
                       "sub": ("homologada em %s" % _f(f["homol"])) if f["homol"] else "sem homologação no SEEU", "crimes": ["GERAL"],
                       "efeito": "só pesa no requisito subjetivo, se dentro da janela do decreto; não zera o cumprido",
                       "duvida": not f["homol"],
                       "det": _det(f["texto"], "GERAL", _f(f["fato"]), "falta grave", "STJ, Súmula 535; decretos 2024/2025, art. 6º; STJ, Tema 1195 (vale a data do fato)",
                                   "", "sem efeito no tempo cumprido")})
    marcos.append({"data": _f(hoje), "tipo": "hoje", "rotulo": "Hoje", "sub": "", "crimes": ["GERAL"], "efeito": "",
                   "det": _det("data da consulta", "GERAL", _f(hoje), "", "", "", "")})
    marcos.sort(key=lambda m: (_d(m["data"]) or date.min))

    # ---- barra da pena unificada (hoje) ----
    ch = cumprido(hoje)
    pena_tot = sum(x["pena_dias"] for x in C)
    selo_ult = {x["id"]: (x["selos"].get(ult_cad["id"]) if ult_cad else None) for x in C}
    imp_ids = [k for k, v in selo_ult.items() if v and v["selo"] == "IMPEDITIVO"]
    seg = [{"crime": x["id"], "cor": x["cor"], "dias": x["pena_dias"], "pena": x["pena"], "impeditivo": x["id"] in imp_ids,
            "duvida": bool(selo_ult.get(x["id"]) and selo_ult[x["id"]]["selo"] == "A_VERIFICAR")} for x in C]
    seeu = None
    try:
        per = rs.periodos_custodia(eventos)
        rem_seeu = [(dt, n) for dt, n, k, _ in remicoes if n > 0]
        v, fonte = rs.cumprido_na_data(r, per, rem_seeu, hoje, rs.periodos_livramento(eventos, incidentes))
        seeu = {"dias": v, "pena": _pena(v), "fonte": fonte, "diferenca": ch["total"] - v}
    except Exception:
        pass
    barra = {"pena_total": pena_tot, "pena_total_txt": _pena(pena_tot), "pena_seeu": r.get("pena_total") or "", "segmentos": seg, "cumprido": ch,
             "cumprido_txt": {k: _pena(v) for k, v in ch.items()}, "restante": max(0, pena_tot - ch["total"]), "restante_txt": _pena(max(0, pena_tot - ch["total"])),
             "seeu": seeu, "imputacao": None, "comutacao": None,
             "det": _det("eventos de início/interrupção, livramento e remições do SEEU", "todos", "%s → hoje" % (_f(ini_exec) or "?"),
                         "cumprimento + detração + remição, sem interrupção por falta grave", "LEP, arts. 111 e 128; CP, art. 42; STJ, Súmula 535",
                         "%s (cumprimento) + %s (detração) + %s (remição)%s = %s" % (_pena(ch["cumprimento"]), _pena(ch["detracao"]), _pena(ch["remicao"]),
                                                                                    (" − %s (perda)" % _pena(ch["perda"])) if ch["perda"] else "", _pena(ch["total"])),
                         "base de todas as frações dos decretos")}
    if ult_cad:
        dl = next((d for d in saida_dec if d["id"] == ult_cad["id"]), None)
        if dl and dl.get("imputacao"):
            barra["imputacao"] = dl["imputacao"]
        if dl and dl["comutacao"].get("reducao"):
            barra["comutacao"] = dict(dl["comutacao"]["reducao"], decreto=dl["numero"])
    for x in C:
        x.pop("_c", None)

    resultado = _consolidado(saida_dec, C)
    return {"nome": r.get("nome", ""), "proc": r.get("processo_execucao", ""), "hoje": _f(hoje), "inicio": _f(ini_exec),
            "crimes": C, "faixas": sorted(faixas, key=lambda f: _d(f["ini"])), "marcos": marcos, "barra": barra, "decretos": saida_dec,
            "resultado": resultado, "duvidas": duvidas, "em_curso": em_curso,
            "ultimo_decreto": ult_cad["id"] if ult_cad else ""}


def _decreto(D, ref, pub, C, cumprido, data_atinge, faltas, hoje, ultimo, em_curso, duvidas):
    num = D.get("numero", "?")
    out = {"id": D.get("id"), "numero": num, "referencia": _f(ref), "publicacao": _f(pub), "cadastrado": bool(D.get("cadastrado")),
           "fonte": D.get("fonte", ""), "nota": D.get("nota", "")}
    if not D.get("cadastrado"):
        txt = "Decreto %s não cadastrado na base jurídica (frações, vedações e janela da falta): resultado A VERIFICAR, sem aplicar por analogia outro decreto." % num
        out["indulto"] = {"status": "verificar", "rotulo": "A VERIFICAR - decreto não cadastrado", "checklist": [
            {"item": "Decreto cadastrado", "estado": "q", "texto": txt, "det": _det("", "", out["referencia"], "", "base_juridica.json → decretos_linha", "", "sem parâmetros, não há cálculo")}]}
        out["comutacao"] = {"status": "verificar", "rotulo": "A VERIFICAR - decreto não cadastrado", "checklist": []}
        for x in C:
            x["selos"][D.get("id")] = {"selo": "A_VERIFICAR", "motivo": "decreto não cadastrado", "dispositivo": "Decreto %s" % num}
        duvidas.append({"data": out["referencia"], "crime": "GERAL", "texto": txt})
        return out
    lim_pub = pub or ref
    alc, fora = [], []
    for x in C:
        c = x["_c"]
        fato, sent = _d(c.get("data_infracao")), _d(c.get("data_sentenca"))
        if fato and fato > ref:
            fora.append((x, "fato posterior à data do decreto (%s)" % _f(ref)))
            x["selos"][D["id"]] = {"selo": "FORA", "motivo": "fato posterior a %s: não alcançado, não impede os demais" % _f(ref), "dispositivo": D.get("regra_fato", {}).get("dispositivo", "")}
            continue
        if sent and sent > lim_pub:
            fora.append((x, "sentença posterior à publicação (%s)" % _f(lim_pub)))
            x["selos"][D["id"]] = {"selo": "FORA", "motivo": "sentença posterior à publicação: fora da soma", "dispositivo": D.get("regra_fato", {}).get("dispositivo", "")}
            continue
        nat = natureza(c, D, ref)
        x["selos"][D["id"]] = nat
        alc.append((x, nat))
    out["fora"] = [{"crime": x["id"], "motivo": m} for x, m in fora]
    cref = cumprido(ref)
    out["cumprido"] = cref
    out["cumprido_txt"] = {k: _pena(v) for k, v in cref.items()}
    if not alc:
        out["indulto"] = {"status": "nao", "rotulo": "NÃO SE APLICA - nenhuma condenação alcançada", "checklist": [
            {"item": "Fato anterior", "estado": "ko", "texto": "; ".join("%s: %s" % (x["id"], m) for x, m in fora), "det": _det()}]}
        out["comutacao"] = {"status": "nao", "rotulo": "NÃO SE APLICA", "checklist": []}
        return out

    imp = [(x, n) for x, n in alc if n["selo"] == "IMPEDITIVO"]
    ver = [(x, n) for x, n in alc if n["selo"] == "A_VERIFICAR"]
    liv = [(x, n) for x, n in alc if n["selo"] != "IMPEDITIVO"]
    reinc_vals = [x["reinc"] for x, _ in alc]
    reinc = any(v.startswith("reincidente") for v in reinc_vals)
    reinc_inc = not reinc and any(v == "reincidência não informada" for v in reinc_vals)
    pena_imp = sum(x["pena_dias"] for x, _ in imp)
    pena_liv = sum(x["pena_dias"] for x, _ in liv)
    pena_alc = pena_imp + pena_liv

    # falta grave (requisito subjetivo)
    FG = D.get("falta_grave")
    janela = None
    faltas_out = []
    if FG:
        j0 = _meses_antes(ref, FG.get("janela_meses", 12))
        j1 = min(ref, pub) if (FG.get("ate") == "publicacao" and pub) else ref
        janela = {"ini": _f(j0), "fim": _f(j1), "meses": FG.get("janela_meses", 12), "dispositivo": FG.get("dispositivo", "")}
        for f in faltas:
            if not f["fato"]:
                continue
            dentro = j0 <= f["fato"] <= j1
            est = "fora"
            if dentro:
                est = "impede" if (f["homol"] or not FG.get("exige_homologacao", True)) and not f["pendente"] else "verificar"
            faltas_out.append({"fato": _f(f["fato"]), "homol": _f(f["homol"]), "texto": f["texto"], "estado": est})
    out["janela_falta"] = janela
    out["faltas"] = faltas_out

    def chk(item, estado, texto, det):
        return {"item": item, "estado": estado, "texto": texto, "det": det}

    comum = []
    # fato anterior
    comum.append(chk("Fato anterior ao decreto", "ok",
                     ("Todos os fatos alcançados são anteriores a %s." % _f(ref)) + ((" Fora da soma (não impedem): " + "; ".join("%s - %s" % (x["id"], m) for x, m in fora)) if fora else ""),
                     _det("datas dos fatos e sentenças no SEEU", ", ".join(x["id"] for x, _ in alc), "até %s" % _f(ref), "alcance do decreto",
                          (D.get("regra_fato") or {}).get("dispositivo", ""), "", "crimes posteriores não entram na soma nem impedem os anteriores")))
    # natureza
    if imp and not liv:
        est_nat, txt_nat = "ko", "Todos os crimes alcançados são impeditivos: " + "; ".join("%s (%s - %s)" % (x["id"], n["motivo"], n["dispositivo"]) for x, n in imp)
    elif ver:
        est_nat = "q"
        txt_nat = "Natureza a verificar: " + "; ".join("%s - %s (%s; %s)" % (x["id"], n["motivo"], n.get("se_sim", ""), n.get("se_nao", "")) for x, n in ver)
    elif imp:
        est_nat = "ok"
        txt_nat = "Concurso com impeditivo (%s): análise dos demais após a regra do %s." % (", ".join(x["id"] for x, _ in imp), (D.get("concurso_impeditivo") or {}).get("dispositivo", "decreto"))
    else:
        est_nat, txt_nat = "ok", "Nenhum crime alcançado está no rol de vedações."
    comum.append(chk("Natureza dos crimes (vedações)", est_nat, txt_nat,
                     _det("tipificação, lei e parágrafos do SEEU", ", ".join("%s: %s" % (x["id"], n["selo"].replace("_", " ")) for x, n in alc), "", "impeditivo / não impeditivo",
                          (D.get("vedacoes") or {}).get("dispositivo", ""), "", "crime impeditivo afasta o benefício ou adia os demais")))
    # falta
    if not FG:
        est_f, txt_f = "q", "Regra de falta grave deste decreto não cadastrada: conferir no texto do decreto."
    else:
        imps = [f for f in faltas_out if f["estado"] == "impede"]
        vers = [f for f in faltas_out if f["estado"] == "verificar"]
        if imps:
            est_f, txt_f = "ko", "Falta grave homologada dentro da janela (%s a %s): %s." % (janela["ini"], janela["fim"], "; ".join("%s, homologada em %s" % (f["fato"], f["homol"] or "?") for f in imps))
        elif vers:
            est_f, txt_f = "q", "Falta na janela sem homologação no SEEU (%s): se homologada, impede; se não, não impede." % "; ".join(f["fato"] for f in vers)
        else:
            est_f, txt_f = "ok", "Nenhuma falta grave dentro da janela de %d meses (%s a %s)." % (janela["meses"], janela["ini"], janela["fim"])
    comum.append(chk("Requisito subjetivo (falta grave na janela)", est_f, txt_f,
                     _det("incidentes de falta/sanção e eventos de fuga do SEEU", "GERAL", ("%s → %s" % (janela["ini"], janela["fim"])) if janela else "", "falta grave",
                          (janela or {}).get("dispositivo", "") + "; STJ, Tema 1195; STJ, Súmula 535", "", "só o requisito subjetivo; o tempo cumprido não se altera")))
    # trânsito / recurso da acusação
    semtr = [x for x, _ in alc if not _d(x["transito"]) or _d(x["transito"]) > lim_pub]
    comum.append(chk("Condenação na data (trânsito/recurso da acusação)", "q" if semtr else "ok",
                     ("Sem trânsito até %s: %s - cabe se não havia recurso da acusação para majorar a pena (%s)." % (_f(lim_pub), ", ".join(x["id"] for x in semtr), (D.get("regra_transito") or {}).get("dispositivo", "decreto")))
                     if semtr else "Todas as condenações alcançadas transitaram até %s." % _f(lim_pub),
                     _det("datas de trânsito no SEEU", ", ".join(x["id"] for x, _ in alc), "", "", (D.get("regra_transito") or {}).get("dispositivo", ""), "", "")))

    # concurso com impeditivo: imputação
    CI = D.get("concurso_impeditivo") or {}
    cumprido_cons, pena_cons, alvo_ids = cref["total"], pena_alc, [x["id"] for x, _ in liv]
    imputacao = None
    liberado = True
    if imp and liv:
        fr_imp = _fr(CI.get("fracao")) or Fraction(1)
        exig_imp = int(pena_imp * fr_imp)
        dt_lib, proj = data_atinge(exig_imp)
        liberado = cref["total"] >= exig_imp
        imputacao = {"fracao": str(fr_imp), "dispositivo": CI.get("dispositivo", ""), "pena_imp": pena_imp, "pena_imp_txt": _pena(pena_imp),
                     "exigido": exig_imp, "exigido_txt": _pena(exig_imp), "data": _f(dt_lib), "projecao": proj, "crimes_imp": [x["id"] for x, _ in imp],
                     "crimes_liv": alvo_ids, "imputado_imp": min(cref["total"], exig_imp), "imputado_liv": max(0, cref["total"] - exig_imp),
                     "det": _det("pena dos crimes impeditivos: " + ", ".join("%s %s" % (x["id"], x["pena"]) for x, _ in imp), ", ".join(x["id"] for x, _ in imp),
                                 "%s → %s" % (_f(ref), _f(dt_lib) or "sem data"), "imputação do cumprido primeiro ao impeditivo", CI.get("dispositivo", ""),
                                 "%s × %s = %s; cumprido em %s: %s" % (_pena(pena_imp), fr_imp, _pena(exig_imp), _f(ref), _pena(cref["total"])),
                                 ("libera a análise de %s" % ", ".join(alvo_ids)) + ((" em %s%s" % (_f(dt_lib), " (projeção)" if proj else "")) if dt_lib else ""))}
        cumprido_cons = max(0, cref["total"] - exig_imp)
        pena_cons = pena_liv
    out["imputacao"] = imputacao

    # ---- indulto: hipótese e requisito objetivo ----
    IND = D.get("indulto") or {}
    vga_vals = [(x["_c"].get("vga") or "") for x, _ in liv]
    vga = "S" if "S" in vga_vals else ("N" if vga_vals and all(v == "N" for v in vga_vals) else "?")
    hip, hip_q = None, []
    for h in IND.get("hipoteses", []):
        if h.get("tipo") == "pena_max_abstrata_por_crime":
            hip = h
            break
        if h.get("vga") is not None:
            want = "S" if h["vga"] else "N"
            if vga == "?":
                hip_q.append(h)
                continue
            if vga != want:
                continue
        if h.get("pena_max_anos") is not None and pena_cons > h["pena_max_anos"] * rs.DIAS_ANO:
            continue
        hip = h
        break
    checklist = list(comum)
    lim_txt = ""
    proj = None
    if hip and hip.get("tipo") == "pena_max_abstrata_por_crime":
        lim = hip.get("anos", 5) * rs.DIAS_ANO
        partes, q, ok_ids = [], False, []
        for x, n in liv:
            pm = rs.pena_maxima_abstrata(x["_c"])
            if pm is None:
                q = True
                partes.append("%s: pena máxima em abstrato não identificada" % x["id"])
            else:
                partes.append("%s: máximo em abstrato %s %s %s" % (x["id"], _pena(pm), "≤" if pm <= lim else ">", _pena(lim)))
                if pm <= lim:
                    ok_ids.append(x["id"])
        est_o = "q" if q and not ok_ids else ("ok" if ok_ids else "ko")
        txt_o = "Sem fração de pena cumprida: basta a pena máxima em abstrato ≤ %s, crime a crime." % _pena(lim)
        if imputacao and not liberado:
            txt_o += " Concurso com impeditivo: os demais só depois de cumprida a pena de %s (%s; atingida em %s)." % (
                ", ".join(imputacao["crimes_imp"]), imputacao["dispositivo"], imputacao["data"] or "data não projetável")
        checklist.insert(0, chk("Requisito objetivo (%s)" % hip.get("dispositivo", ""), "ok" if liberado else "ko", txt_o,
                                _det("tipo penal impresso no SEEU", ", ".join(x["id"] for x, _ in liv), "", "limite de pena", hip.get("dispositivo", ""), "; ".join(partes), "")))
        checklist.insert(1, chk("Limite de pena", est_o, "; ".join(partes), _det("", "", "", "", hip.get("dispositivo", ""), "", "")))
        alvo_ids = ok_ids
        ind = {"hipotese": hip.get("dispositivo", ""), "exigido": 0, "cumprido": cumprido_cons, "pena_considerada": pena_cons}
    elif hip:
        fr_h = _fr((hip.get("fracao") or {}).get("reincidente" if reinc else "primario"))
        fr_alt = _fr((hip.get("fracao") or {}).get("primario")) if reinc_inc else None
        exig = int(pena_cons * fr_h)
        ok = cumprido_cons >= exig and liberado
        conta = "%s × %s = %s" % (_pena(pena_cons), fr_h, _pena(exig))
        est_obj = "ok" if ok else "ko"
        txt_obj = "Exigido %s (%s, %s); cumprido %s em %s." % (_pena(exig), fr_h, "reincidente" if reinc else "primário", _pena(cumprido_cons), _f(ref))
        if reinc_inc:
            exig_alt = int(pena_cons * fr_alt) if fr_alt else exig
            if (cumprido_cons >= exig) != (cumprido_cons >= exig_alt):
                est_obj = "q"
                txt_obj += " Reincidência não informada: como primário (%s) exigiria %s - o resultado muda." % (fr_alt, _pena(exig_alt))
        if imputacao and not liberado:
            txt_obj += " O impeditivo ainda não atingiu a fração que libera os demais (%s)." % imputacao["dispositivo"]
        checklist.insert(0, chk("Requisito objetivo (%s)" % hip.get("dispositivo", ""), est_obj, txt_obj,
                                _det("pena considerada: " + ", ".join("%s %s" % (x["id"], x["pena"]) for x, _ in liv) if imputacao else "pena unificada dos crimes alcançados",
                                     ", ".join(alvo_ids), "início → %s" % _f(ref), "fração sobre a pena", hip.get("dispositivo", "") + ((" c/c " + D.get("regra_reincidencia", {}).get("dispositivo", "")) if D.get("regra_reincidencia") else ""),
                                     conta + ("; cumprido %s − %s imputados ao impeditivo = %s" % (_pena(cref["total"]), imputacao["exigido_txt"], _pena(cumprido_cons)) if imputacao else ""),
                                     "atende" if ok else "não atende em %s" % _f(ref))))
        lim_h = hip.get("pena_max_anos")
        checklist.insert(1, chk("Limite de pena", "ok" if lim_h is None or pena_cons <= lim_h * rs.DIAS_ANO else "ko",
                                ("Pena considerada %s ≤ %s." % (_pena(pena_cons), rs.pl(lim_h, "ano", "anos"))) if lim_h is not None else "Hipótese sem limite de pena.",
                                _det("", "", "", "", hip.get("dispositivo", ""), "", "")))
        ind = {"hipotese": hip.get("dispositivo", ""), "descricao": hip.get("descricao", ""), "fracao": str(fr_h), "exigido": exig, "exigido_txt": _pena(exig),
               "cumprido": cumprido_cons, "cumprido_txt": _pena(cumprido_cons), "pena_considerada": pena_cons, "pena_considerada_txt": _pena(pena_cons)}
        if not ok and ultimo:
            alvo = exig + (imputacao["exigido"] if imputacao else 0)
            dt, pj = data_atinge(alvo)
            proj = {"data": _f(dt), "projecao": pj, "em_curso": em_curso}
    else:
        ind = {"hipotese": "", "exigido": None}
        if hip_q:
            checklist.insert(0, chk("Requisito objetivo", "q", "O SEEU não informa violência/grave ameaça; a hipótese aplicável (%s) depende disso." % ", ".join(h.get("dispositivo", "") for h in hip_q),
                                    _det("campo 'Violência ou grave ameaça' do SEEU", ", ".join(alvo_ids), "", "", "", "", "")))
        else:
            checklist.insert(0, chk("Requisito objetivo", "ko", "Nenhuma hipótese cadastrada alcança a pena considerada (%s). Outras hipóteses do decreto (regime aberto, idade, saúde, mulheres) não estão modeladas nesta linha." % _pena(pena_cons),
                                    _det("", "", "", "", ", ".join(h.get("dispositivo", "") for h in IND.get("hipoteses", [])), "", "")))
    ORDEM = ["Requisito objetivo", "Natureza", "Limite", "Requisito subjetivo", "Fato anterior", "Condenação"]
    checklist.sort(key=lambda c: next((i for i, k in enumerate(ORDEM) if c["item"].startswith(k)), 9))
    estados = [c["estado"] for c in checklist]
    obj_ko = checklist[0]["estado"] == "ko"
    outros_ko = [c for c in checklist[1:] if c["estado"] == "ko"]
    if outros_ko or (imp and not liv):
        st, rot = "nao", "NÃO CABE - " + (outros_ko[0]["item"].lower() if outros_ko else "crime impeditivo")
    elif "q" in estados:
        st, rot = "verificar", "A VERIFICAR"
    elif obj_ko:
        if proj and proj["data"]:
            st, rot = "ainda", "AINDA NÃO - requisito objetivo em %s%s" % (proj["data"], " (projeção)" if proj["projecao"] else "")
        else:
            st, rot = "nao", "NÃO CABE - requisito objetivo não atingido em %s" % _f(ref)
    else:
        st, rot = "cabe", "CABE INDULTO"
    ind.update({"status": st, "rotulo": rot, "checklist": checklist, "alcancados": alvo_ids if st == "cabe" else [],
                "nao_alcancados": [{"crime": x["id"], "motivo": n["motivo"]} for x, n in imp] + [{"crime": x["id"], "motivo": m} for x, m in fora], "projecao": proj})
    out["indulto"] = ind

    # ---- comutação ----
    COM = D.get("comutacao")
    if not COM:
        out["comutacao"] = {"status": "nao", "rotulo": "Decreto sem comutação cadastrada", "checklist": []}
        return out
    if st == "cabe":
        out["comutacao"] = {"status": "prejudicada", "rotulo": "Prejudicada - cabe indulto (%s)" % COM.get("dispositivo_prejudicada", ""), "checklist": []}
        return out
    fr_c = _fr((COM.get("fracao") or {}).get("reincidente" if reinc else "primario"))
    exig_c = int(pena_cons * fr_c)
    ok_c = cumprido_cons >= exig_c and liberado
    ck = [chk("Requisito objetivo (%s)" % COM.get("dispositivo", ""), "ok" if ok_c else "ko",
              "Exigido %s (%s, %s); cumprido %s em %s." % (_pena(exig_c), fr_c, "reincidente" if reinc else "primário", _pena(cumprido_cons), _f(ref)),
              _det("pena considerada", ", ".join(alvo_ids), "início → %s" % _f(ref), "fração sobre a pena", COM.get("dispositivo", ""),
                   "%s × %s = %s" % (_pena(pena_cons), fr_c, _pena(exig_c)), "atende" if ok_c else "não atende"))] + [c for c in comum]
    if reinc_inc:
        fr_alt_c = _fr((COM.get("fracao") or {}).get("reincidente"))
        if fr_alt_c and (cumprido_cons >= int(pena_cons * fr_alt_c)) != ok_c:
            ck[0]["estado"] = "q"
            ck[0]["texto"] += " Reincidência não informada: como reincidente (%s) o resultado muda." % fr_alt_c
    rem = max(0, pena_cons - cumprido_cons)
    red = None
    if ok_c:
        base_v = rem
        base_n = "remanescente"
        if COM.get("base") == "remanescente_ou_cumprido_se_maior" and cumprido_cons > rem:
            base_v, base_n = cumprido_cons, "cumprida"
        fr_red = _fr(COM.get("reducao")) or Fraction(0)
        n_red = int(base_v * fr_red)
        red = {"fracao": str(fr_red), "base": base_n, "base_dias": base_v, "reducao": n_red, "reducao_txt": _pena(n_red), "antes": rem, "antes_txt": _pena(rem),
               "depois": max(0, rem - n_red), "depois_txt": _pena(max(0, rem - n_red)), "crimes": alvo_ids,
               "det": _det("pena %s em %s" % (base_n, _f(ref)), ", ".join(alvo_ids), _f(ref), "comutação", COM.get("dispositivo_reducao", COM.get("dispositivo", "")),
                           "%s × %s = %s; %s − %s = %s" % (_pena(base_v), fr_red, _pena(n_red), _pena(rem), _pena(n_red), _pena(max(0, rem - n_red))),
                           "a pena remanescente passa de %s para %s e alimenta os demais cálculos" % (_pena(rem), _pena(max(0, rem - n_red))))}
    est = [c["estado"] for c in ck]
    ko2 = [c for c in ck[1:] if c["estado"] == "ko"]
    if ko2 or (imp and not liv):
        cst, crot = "nao", "NÃO CABE - " + (ko2[0]["item"].lower() if ko2 else "crime impeditivo")
    elif "q" in est:
        cst, crot = "verificar", "A VERIFICAR"
    elif not ok_c:
        cproj = None
        if ultimo:
            dt, pj = data_atinge(exig_c + (imputacao["exigido"] if imputacao else 0))
            cproj = {"data": _f(dt), "projecao": pj}
        if cproj and cproj["data"]:
            cst, crot = "ainda", "AINDA NÃO - requisito em %s%s" % (cproj["data"], " (projeção)" if cproj["projecao"] else "")
        else:
            cst, crot = "nao", "NÃO CABE - requisito objetivo não atingido em %s" % _f(ref)
    else:
        cst, crot = "cabe", "CABE COMUTAÇÃO - %s de %s" % (red["fracao"], red["base"])
    out["comutacao"] = {"status": cst, "rotulo": crot, "checklist": ck, "reducao": red if cst in ("cabe", "verificar") else None,
                        "fracao": str(fr_c), "exigido": exig_c, "exigido_txt": _pena(exig_c)}
    return out


def _consolidado(decs, C):
    cards = []
    for d in decs:
        i, c = d["indulto"], d.get("comutacao") or {}
        k = {"cabe": "CABE INDULTO", "nao": "NÃO CABE", "verificar": "A VERIFICAR", "ainda": "AINDA NÃO - PROJEÇÃO"}.get(i["status"], "")
        linhas = []
        if i["status"] == "cabe":
            linhas.append("Crimes alcançados: %s." % (", ".join(i.get("alcancados") or []) or "-"))
            if i.get("nao_alcancados"):
                linhas.append("Não alcançados: %s." % "; ".join("%s (%s)" % (x["crime"], x["motivo"]) for x in i["nao_alcancados"]))
        else:
            mot = [x for x in i.get("checklist", []) if x["estado"] == "ko"] + [x for x in i.get("checklist", []) if x["estado"] == "q"]
            if mot:
                linhas.append("Motivo: %s" % mot[0]["texto"])
        if i.get("projecao") and i["projecao"].get("data"):
            linhas.append("Atinge o requisito objetivo em %s." % i["projecao"]["data"])
        cards.append({"decreto": d["numero"], "tipo": "indulto", "status": i["status"], "titulo": k, "linhas": linhas,
                      "projecao": bool(i.get("projecao") and i["projecao"].get("data"))})
        if c.get("status") in ("cabe", "verificar", "ainda", "nao"):
            lc = []
            if c.get("reducao"):
                r = c["reducao"]
                lc.append("Fração %s sobre a pena %s de %s." % (r["fracao"], r["base"], ", ".join(r["crimes"]) or "-"))
                lc.append("Pena remanescente passa de %s para %s." % (r["antes_txt"], r["depois_txt"]))
            else:
                mot = [x for x in c.get("checklist", []) if x["estado"] == "ko"] + [x for x in c.get("checklist", []) if x["estado"] == "q"]
                if mot:
                    lc.append("Motivo: %s" % mot[0]["texto"])
            cards.append({"decreto": d["numero"], "tipo": "comutacao", "status": c["status"],
                          "titulo": {"cabe": "CABE COMUTAÇÃO", "nao": "NÃO CABE", "verificar": "A VERIFICAR", "ainda": "AINDA NÃO - PROJEÇÃO"}[c["status"]],
                          "linhas": lc, "projecao": c["status"] == "ainda"})
    return cards
