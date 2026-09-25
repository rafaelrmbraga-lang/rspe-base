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
import rspe_view as rv

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
    return rs.trafico_incerto(c)  # mesma regra da aba


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
        if imp and "fato anterior" in imp[1]:
            return {"selo": "A_VERIFICAR", "motivo": imp[1], "dispositivo": "Decreto %s, art. 1º, %s" % (num, imp[0]),
                    "se_sim": "hediondez na data do decreto (STJ): IMPEDITIVO", "se_nao": "na data do fato (irretroatividade - STF, 2ª T.): NÃO IMPEDITIVO"}
        if imp:
            return {"selo": "IMPEDITIVO", "motivo": imp[1], "dispositivo": "Decreto %s, art. 1º, %s" % (num, imp[0])}
    elif regra == "art7_2022":
        exc = rs.exclusao_art7_2022(c)
        if exc and "fato anterior - tese" in exc:
            return {"selo": "A_VERIFICAR", "motivo": exc.split(":", 1)[-1].strip(), "dispositivo": "Decreto %s, art. 7º, %s" % (num, exc.split(":")[0]),
                    "se_sim": "hediondez na data do decreto (STJ): IMPEDITIVO", "se_nao": "na data do fato (irretroatividade): NÃO IMPEDITIVO"}
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

def _alerta_tempo(c):
    """Lei do tempo: capitulação criada depois do fato ou hediondez posterior ao fato (a vedação do decreto é aferida pelo STJ
    na data do decreto; tese defensiva: irretroatividade)."""
    fato = rs.to_date(c.get("data_infracao") or "")
    if not fato:
        return ""
    dc, lc = rs.tipo_criado_em(c)
    dh, _ = rs.hediondo_desde(c)
    if dc and fato < dc:
        return ("Capitulação criada em %s (%s), depois do fato: cadastro anacrônico - conferir a sentença%s." % (
            rs.fmt(dc), lc.split(" (")[0], ("; não era hediondo no fato (hediondez desde %s)" % rs.fmt(dh)) if (dh and fato < dh) else ""))
    if dh and fato < dh:
        return ("Hediondez desde %s, posterior ao fato: o STJ afere na data do decreto (vedado); tese defensiva - irretroatividade." % rs.fmt(dh))
    return ""


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
                  "natureza": _natureza_txt(c), "reinc": _reinc_txt(c), "selos": {}, "_c": c, "alerta_tempo": _alerta_tempo(c)})
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

    per_seeu = rs.periodos_custodia(eventos)
    lc_seeu = rs.periodos_livramento(eventos, incidentes)
    rem_seeu = [(dt, n) for dt, n, k, _ in remicoes if n > 0]

    def cumprido(ref):
        """Pena cumprida em ref pelo MESMO cálculo da aba (âncora no SEEU: rspe_scraper.cumprido_na_data). Detração e
        remição vêm dos eventos; o cumprimento é o total do SEEU menos elas. A soma pelos eventos fica só para conferência."""
        c = dias.ate(ref)
        rem = sum(n for dt, n, k, _ in remicoes if dt and dt <= ref and n > 0)
        per = -sum(n for dt, n, k, _ in remicoes if dt and dt <= ref and n < 0)
        ev_tot = c["cumprimento"] + c["livramento"] + c["detracao"] + rem - per
        try:
            tot, fonte = rs.cumprido_na_data(r, per_seeu, rem_seeu, ref, lc_seeu)
        except Exception:
            tot, fonte = None, ""
        if tot is None:
            tot, fonte = ev_tot, "soma dos eventos (o SEEU não trouxe a pena cumprida)"
        tot = max(0, int(tot))
        return {"cumprimento": max(0, tot - c["detracao"] - (rem - per)), "detracao": c["detracao"], "remicao": rem, "perda": per,
                "nao_comprovado": c["nao_comprovado"], "total": tot, "fonte": fonte,
                "eventos": max(0, int(ev_tot)), "diferenca": int(ev_tot) - tot}

    em_curso = any(f["aberta"] and f["tipo"] in CONTA for f in faixas)

    def data_atinge(alvo):
        """Data em que o cumprido (mesmo cálculo da aba) alcança 'alvo' dias: no passado, por busca nas datas; no futuro,
        projeção com o cumprimento em curso (1 dia por dia)."""
        if alvo <= 0:
            return ini_exec, False
        agora = cumprido(hoje)["total"]
        if agora >= alvo and ini_exec:
            lo, hi = ini_exec.toordinal(), hoje.toordinal()
            while lo < hi:
                mid = (lo + hi) // 2
                if cumprido(date.fromordinal(mid))["total"] >= alvo:
                    hi = mid
                else:
                    lo = mid + 1
            return date.fromordinal(lo), False
        if em_curso and alvo > agora:
            return hoje + timedelta(days=int(alvo - agora)), True
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
        if i.get("_ficha_falta") and not rs.RE_FALTA_PROPRIA.search(rot) and i.get("_falta") != "nao" and not rs._negado(i):
            # regressão/perda explicada por falta registrada na ficha: falta grave pela data do fato na ficha
            x = _d(i["_ficha_falta"]["data"])
            if x:
                faltas.append({"fato": x, "homol": None, "pendente": False, "texto": "%s - ficha: %s" % (rot, i["_ficha_falta"]["texto"][:80]),
                               "sub": "registrada na ficha (motivou: %s)" % rot.lower()[:40]})
            continue
        if not rs.RE_FALTA_PROPRIA.search(rot) or rs._negado(i) or i.get("_falta") == "nao":
            continue
        fato = rs._data_fato_falta(i)
        conf = i.get("_falta") == "sim"
        pend = rs._pendente(i) and not conf and not i.get("_fuga_ficha")  # fuga (ficha): falta grave por padrão
        homol = _d(i.get("data_decisao")) if not rs._pendente(i) else None
        faltas.append({"fato": fato, "homol": homol, "pendente": pend, "texto": rot + (" (falta grave confirmada pelo operador)" if conf else ""),
                       "sub": "confirmada pelo operador" if conf and not homol else ""})
    for e in eventos:
        tt = " ".join(("%s %s" % (e.get("tipo", ""), e.get("motivo", ""))).split())
        d0 = _d(e.get("data"))
        if d0 and RE_FUGA.search(tt) and e.get("_falta") != "nao" and not any(f["fato"] and abs((f["fato"] - d0).days) <= 1 for f in faltas):
            # fuga: falta grave (LEP, art. 50, II) - a homologação posterior não muda a data do fato (STJ, Tema 1195)
            faltas.append({"fato": d0, "homol": None, "pendente": False, "fuga": True, "texto": tt + " (fuga: falta grave, LEP, art. 50, II)",
                           "sub": "fuga (LEP, art. 50, II)"})

    # ---- decretos ----
    ult_cad = max((D for D in decretos if D.get("cadastrado")), key=lambda D: _d(D.get("referencia")) or date.min, default=None)
    saida_dec = []
    for D in sorted(decretos, key=lambda D: _d(D.get("referencia")) or date.min):
        ref, pub = _d(D.get("referencia")), _d(D.get("publicacao"))
        if not ref or ref > hoje:
            continue
        if ini_exec and ref < ini_exec and not any(_d(x["fato"]) and _d(x["fato"]) <= ref for x in C):
            continue
        saida_dec.append(_decreto(D, ref, pub, C, cumprido, data_atinge, faltas, hoje, D is ult_cad, em_curso, duvidas, r, eventos, incidentes))
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
                       "sub": ("homologada em %s" % _f(f["homol"])) if f["homol"] else (f.get("sub") or "sem homologação no SEEU"), "crimes": ["GERAL"],
                       "efeito": "só pesa no requisito subjetivo, se dentro da janela do decreto; não zera o cumprido",
                       "duvida": f["pendente"], "fuga": bool(f.get("fuga")),
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
    seeu = {"dias": ch["eventos"], "pena": _pena(ch["eventos"]), "fonte": ch["fonte"], "diferenca": ch["diferenca"]}
    barra = {"pena_total": pena_tot, "pena_total_txt": _pena(pena_tot), "pena_seeu": r.get("pena_total") or "", "segmentos": seg, "cumprido": ch,
             "cumprido_txt": {k: _pena(v) for k, v in ch.items() if isinstance(v, int)}, "restante": max(0, pena_tot - ch["total"]), "restante_txt": _pena(max(0, pena_tot - ch["total"])),
             "seeu": seeu, "imputacao": None, "comutacao": None,
             "det": _det("pena cumprida do SEEU (%s); detração e remição pelos eventos" % ch["fonte"], "todos", "%s → hoje" % (_f(ini_exec) or "?"),
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
    return {"nome": rv.nome_proprio(r.get("nome", "")), "proc": r.get("processo_execucao", ""), "hoje": _f(hoje), "inicio": _f(ini_exec),
            "crimes": C, "faixas": sorted(faixas, key=lambda f: _d(f["ini"])), "marcos": marcos, "barra": barra, "decretos": saida_dec,
            "resultado": resultado, "duvidas": duvidas, "em_curso": em_curso,
            "ultimo_decreto": ult_cad["id"] if ult_cad else ""}


def _st_aba(txt):
    """Status da linha do tempo a partir do texto da aba (mesmas cores da tabela)."""
    t = txt or ""
    if t.startswith("prejudicada"):
        return "prejudicada"
    return {"verde": "cabe", "amarelo": "verificar", "azul": "concedido"}.get(rv.cor_texto_indulto(t), "nao")


ICONE = {"✔": "ok", "✓": "ok", "✘": "ko", "✗": "ko", "?": "q", "⚠": "q"}


def _linhas_aba(txt):
    """Linhas com ícone da memória da aba (✔ ? ✘ ⚠ e 'Não atendidos') -> [(estado, texto)]."""
    out = []
    for l in (txt or "").split("\n"):
        l = l.strip()
        m = re.match(r"^([✔✓✘✗?⚠])\s*(.*)$", l)
        if m:
            out.append((ICONE[m.group(1)], m.group(2)))
        elif l.startswith("Não atendidos:"):
            out.append(("ko", l))
    return out


def _decreto(D, ref, pub, C, cumprido, data_atinge, faltas, hoje, ultimo, em_curso, duvidas, r, eventos, incidentes):
    """Cartão do decreto. O resultado, os números e a memória são os da aba Indulto / Comutação (rspe_scraper): a linha do
    tempo só os desenha, para que as duas análises nunca divirjam."""
    ano, num = D.get("id"), D.get("numero", "?")
    k, kc = "indulto_%s" % ano, "comutacao_%s" % ano
    out = {"id": ano, "numero": num, "referencia": _f(ref), "publicacao": _f(pub), "cadastrado": bool(D.get("cadastrado")),
           "fonte": D.get("fonte", ""), "nota": D.get("nota", "")}
    txt_i = r.get(k)
    if not D.get("cadastrado") or txt_i is None:
        txt = "Decreto %s sem análise na aba Indulto / Comutação: resultado A VERIFICAR, sem aplicar por analogia outro decreto." % num
        out["indulto"] = {"status": "verificar", "rotulo": "A VERIFICAR", "checklist": [
            {"item": "Decreto analisado", "estado": "q", "texto": txt, "det": _det("", "", out["referencia"], "", "base_juridica.json → decretos_linha", "", "")}]}
        out["comutacao"] = {"status": "verificar", "rotulo": "A VERIFICAR", "checklist": []}
        duvidas.append({"data": out["referencia"], "crime": "GERAL", "texto": txt})
        return out

    def chk(item, estado, texto, det):
        return {"item": item, "estado": estado, "texto": texto, "det": det}

    # alcance e natureza de cada crime (mesmas funções da aba)
    lim_pub = pub or ref
    alc, fora = [], []
    for x in C:
        c = x["_c"]
        fato, sent = _d(c.get("data_infracao")), _d(c.get("data_sentenca"))
        if fato and fato > ref:
            fora.append((x, "fato posterior à data do decreto (%s)" % _f(ref)))
            x["selos"][ano] = {"selo": "FORA", "motivo": "fato posterior a %s: não alcançado, não impede os demais" % _f(ref), "dispositivo": (D.get("regra_fato") or {}).get("dispositivo", "")}
            continue
        if sent and sent > lim_pub:
            fora.append((x, "sentença posterior à publicação (%s)" % _f(lim_pub)))
            x["selos"][ano] = {"selo": "FORA", "motivo": "sentença posterior à publicação: fora da soma", "dispositivo": (D.get("regra_fato") or {}).get("dispositivo", "")}
            continue
        nat = natureza(c, D, ref)
        x["selos"][ano] = nat
        alc.append((x, nat))
    out["fora"] = [{"crime": x["id"], "motivo": m} for x, m in fora]
    cref = cumprido(ref)
    out["cumprido"] = cref
    out["cumprido_txt"] = {kk: _pena(v) for kk, v in cref.items() if isinstance(v, int)}
    num_i = r.get(k + "_num") or {}
    imp = [(x, n) for x, n in alc if n["selo"] == "IMPEDITIVO"]
    ver = [(x, n) for x, n in alc if n["selo"] == "A_VERIFICAR"]
    liv = [(x, n) for x, n in alc if n["selo"] != "IMPEDITIVO"]

    checklist = []
    # 1) memória da aba (hipóteses do decreto, exigido x cumprido, ressalvas)
    for est, t in _linhas_aba(r.get(k + "_explica") or r.get(k + "_detalhe")):
        hip = bool(re.match(r"^(Inciso |[IVX]+(\s+e\s+[IVX]+)?:|art\. \d|Não atendidos)", t))
        checklist.append(chk("Requisito objetivo / hipótese" if hip else "Ressalva", est, t,
                             _det("memória da análise da aba Indulto / Comutação", ", ".join(x["id"] for x, _ in alc), "até %s" % _f(ref),
                                  "hipótese do decreto" if hip else "ressalva", "Decreto %s" % num, t,
                                  "mesmo cálculo da aba: cumprido %s (%s)" % (_pena(num_i["cumprido"]), num_i.get("fonte", "")) if num_i else "")))
    # 2) natureza
    if imp and not liv:
        est_nat, txt_nat = "ko", "Todos os crimes alcançados são impeditivos: " + "; ".join("%s (%s - %s)" % (x["id"], n["motivo"], n["dispositivo"]) for x, n in imp)
    elif ver:
        est_nat = "q"
        txt_nat = "Natureza a verificar: " + "; ".join("%s - %s%s" % (x["id"], n["motivo"], (" (%s; %s)" % (n["se_sim"], n["se_nao"])) if n.get("se_sim") else "") for x, n in ver)
    elif imp:
        est_nat = "ok"
        txt_nat = "Concurso com impeditivo (%s): os demais só depois da regra do %s." % (", ".join(x["id"] for x, _ in imp), (D.get("concurso_impeditivo") or {}).get("dispositivo", "decreto"))
    else:
        est_nat, txt_nat = "ok", "Nenhum crime alcançado está no rol de vedações."
    checklist.append(chk("Natureza dos crimes (vedações)", est_nat, txt_nat,
                         _det("tipificação, lei e parágrafos do SEEU", ", ".join("%s: %s" % (x["id"], n["selo"].replace("_", " ")) for x, n in alc), "", "impeditivo / não impeditivo",
                              (D.get("vedacoes") or {}).get("dispositivo", ""), "", "crime impeditivo afasta o benefício ou adia os demais")))
    # 3) falta grave (mesma função da aba: rspe_scraper.falta_art6)
    FG = D.get("falta_grave")
    janela, faltas_out = None, []
    if FG:
        j0 = _meses_antes(ref, FG.get("janela_meses", 12))
        j1 = min(ref, pub) if (FG.get("ate") == "publicacao" and pub) else ref
        janela = {"ini": _f(j0), "fim": _f(j1), "meses": FG.get("janela_meses", 12), "dispositivo": FG.get("dispositivo", ""),
                  "informativa": FG.get("exige") is False}
        for f in faltas:
            if not f["fato"]:
                continue
            dentro = j0 <= f["fato"] <= j1
            est = "fora"
            if dentro:
                est = "informativa" if FG.get("exige") is False else ("verificar" if f["pendente"] else "impede")
            faltas_out.append({"fato": _f(f["fato"]), "homol": _f(f["homol"]), "texto": f["texto"], "estado": est})
    out["janela_falta"] = janela
    out["faltas"] = faltas_out
    if not FG:
        est_f, txt_f = "q", "Regra de falta grave deste decreto não cadastrada: conferir no texto do decreto."
    elif FG.get("exige") is False:
        reg = [f for f in faltas_out if f["estado"] == "informativa"]
        est_f = "ok"
        txt_f = "O Decreto %s não exige ausência de falta grave: não afasta o indulto." % num + (
            (" Faltas registradas nos %d meses anteriores (informativo): %s." % (janela["meses"], "; ".join(
                "%s%s" % (f["fato"], (", homologada em %s" % f["homol"]) if f["homol"] else ", sem homologação") for f in reg))) if reg
            else " Nenhuma falta registrada nos %d meses anteriores." % janela["meses"])
    else:
        firmes, verif = (num_i.get("falta_firme"), num_i.get("falta_verif")) if num_i else rs.falta_art6(incidentes, ref, eventos, pub)
        if firmes:
            est_f = "ko"
            txt_f = ("Falta com sanção reconhecida dentro da janela (%s a %s): %s. Não cabe o indulto nem a comutação (%s)." % (
                janela["ini"], janela["fim"], "; ".join(firmes), FG.get("dispositivo", "")))
        elif verif:
            est_f, txt_f = "q", "Falta na janela a verificar (só impede se a sanção for reconhecida em juízo): %s." % "; ".join(verif)
        else:
            est_f, txt_f = "ok", "Nenhuma falta grave dentro da janela de %d meses (%s a %s)." % (janela["meses"], janela["ini"], janela["fim"])
    checklist.append(chk("Requisito subjetivo (falta grave%s)" % (": não exigido" if FG and FG.get("exige") is False else " na janela"), est_f, txt_f,
                         _det("incidentes de falta/sanção e eventos de fuga do SEEU", "GERAL", ("%s → %s" % (janela["ini"], janela["fim"])) if janela else "", "falta grave",
                              ((janela or {}).get("dispositivo", "") + "; STJ, Tema 1195; STJ, Súmula 535").strip("; "), "",
                              "só o requisito subjetivo; o tempo cumprido não se altera")))
    # 4) alcance e trânsito
    checklist.append(chk("Fato anterior ao decreto", "ok",
                         ("Todos os fatos alcançados são anteriores a %s." % _f(ref)) + ((" Fora da soma (não impedem): " + "; ".join("%s - %s" % (x["id"], m) for x, m in fora)) if fora else ""),
                         _det("datas dos fatos e sentenças no SEEU", ", ".join(x["id"] for x, _ in alc), "até %s" % _f(ref), "alcance do decreto",
                              (D.get("regra_fato") or {}).get("dispositivo", ""), "", "crimes posteriores não entram na soma nem impedem os anteriores")))
    semtr = [x for x, _ in alc if not _d(x["transito"]) or _d(x["transito"]) > lim_pub]
    checklist.append(chk("Condenação na data (trânsito/recurso da acusação)", "q" if semtr else "ok",
                         ("Sem trânsito até %s: %s - cabe se não havia recurso da acusação para majorar a pena (%s)." % (
                             _f(lim_pub), ", ".join(x["id"] for x in semtr), (D.get("regra_transito") or {}).get("dispositivo", "decreto")))
                         if semtr else "Todas as condenações alcançadas transitaram até %s." % _f(lim_pub),
                         _det("datas de trânsito no SEEU", ", ".join(x["id"] for x, _ in alc), "", "", (D.get("regra_transito") or {}).get("dispositivo", ""), "", "")))

    # imputação ao impeditivo (números da aba)
    imputacao = None
    ti = r.get(k + "_imp")
    if ti:
        dt_lib, proj = data_atinge(ti["exigido"])
        ids_imp = [x["id"] for x, _ in imp] or [x["id"] for x, _ in ver]
        ids_liv = [x["id"] for x, _ in liv if x["id"] not in ids_imp]
        imputacao = {"fracao": ti["fracao"], "dispositivo": (D.get("concurso_impeditivo") or {}).get("dispositivo", ""), "pena_imp": ti["pena_imp"],
                     "pena_imp_txt": _pena(ti["pena_imp"]), "exigido": ti["exigido"], "exigido_txt": _pena(ti["exigido"]), "data": _f(dt_lib), "projecao": proj,
                     "crimes_imp": ids_imp, "crimes_liv": ids_liv, "imputado_imp": min(ti["cumprido_total"], ti["exigido"]),
                     "imputado_liv": max(0, ti["cumprido_total"] - ti["exigido"]),
                     "sobra_txt": _pena(max(0, ti["cumprido_total"] - ti["exigido"])), "cumprido_total_txt": _pena(ti["cumprido_total"]),
                     "det": _det("pena dos crimes impeditivos: %s" % _pena(ti["pena_imp"]), ", ".join(ids_imp), "%s → %s" % (_f(ref), _f(dt_lib) or "sem data"),
                                 "imputação do cumprido primeiro ao impeditivo", (D.get("concurso_impeditivo") or {}).get("dispositivo", ""),
                                 "%s × %s = %s; cumprido em %s: %s" % (_pena(ti["pena_imp"]), ti["fracao"], _pena(ti["exigido"]), _f(ref), _pena(ti["cumprido_total"])),
                                 ("libera a análise de %s" % ", ".join(ids_liv)) + ((" em %s%s" % (_f(dt_lib), " (projeção)" if proj else "")) if dt_lib else ""))}
    out["imputacao"] = imputacao

    # resultado: o da aba
    st = _st_aba(txt_i)
    rot = rv.curto_indulto(txt_i) or txt_i
    proj = None
    if ultimo and st == "nao" and txt_i.lower().startswith("não atinge") and num_i:
        # projeção pela primeira hipótese cadastrada que se aplica à pena considerada na aba
        for h in (D.get("indulto") or {}).get("hipoteses", []):
            if h.get("vga") is not None and bool(h["vga"]) != bool(num_i.get("vga")):
                continue
            if h.get("pena_max_anos") is not None and num_i["pena"] > h["pena_max_anos"] * rs.DIAS_ANO:
                continue
            fr_h = _fr((h.get("fracao") or {}).get("reincidente" if num_i.get("reinc") else "primario"))
            if not fr_h:
                continue
            exig = int(num_i["pena"] * fr_h * (Fraction(1, 2) if num_i.get("meia") else 1))
            dt, pj = data_atinge(exig + (ti["exigido"] if ti else 0))
            if dt:
                proj = {"data": _f(dt), "projecao": pj, "hipotese": h.get("dispositivo", ""), "exigido_txt": _pena(exig)}
                st = "ainda"
                rot = "Não atinge em %s · %s em %s%s" % (_f(ref), h.get("dispositivo", ""), _f(dt), " (projeção)" if pj else "")
            break
    ind = {"status": st, "rotulo": rot, "texto_aba": txt_i, "checklist": checklist, "projecao": proj}
    if num_i:
        ind.update({"pena_considerada_txt": _pena(num_i["pena"]), "cumprido_txt": _pena(num_i["cumprido"]),
                    "remanescente_txt": _pena(num_i["remanescente"]), "fonte": num_i.get("fonte", ""),
                    "reinc": "reincidente" if num_i.get("reinc") else "primário"})
    out["indulto"] = ind

    # comutação: a da aba
    txt_c = r.get(kc)
    if txt_c is None:
        out["comutacao"] = {"status": "nao", "rotulo": "Decreto sem comutação", "checklist": []}
        ind["fundamentacao"] = _fundamentacao(out, "indulto")
        return out
    st_c = _st_aba(txt_c)
    num_c = r.get(kc + "_num") or {}
    ck = [chk("Requisito objetivo / hipótese" if e != "q" or not t.startswith("FALTA") else "Ressalva", e, t,
              _det("memória da análise da aba Indulto / Comutação", "", "até %s" % _f(ref), "comutação", "Decreto %s, art. 13" % num, t, "mesmo cálculo da aba"))
          for e, t in _linhas_aba(r.get(kc + "_detalhe"))]
    ck += [c for c in checklist if not c["item"].startswith("Requisito objetivo") and c["item"] != "Ressalva"]
    red = None
    if num_c.get("reducao") is not None and st_c in ("cabe", "verificar"):
        red = {"fracao": num_c["prop"], "base": num_c["base"], "base_dias": num_c["base_dias"], "reducao": num_c["reducao"], "reducao_txt": _pena(num_c["reducao"]),
               "antes": num_c["antes"], "antes_txt": _pena(num_c["antes"]), "depois": num_c["depois"], "depois_txt": _pena(num_c["depois"]),
               "crimes": [x["id"] for x, _ in liv],
               "det": _det("pena %s em %s" % (num_c["base"], _f(ref)), ", ".join(x["id"] for x, _ in liv), _f(ref), "comutação", "Decreto %s, art. 13, caput e § 1º" % num,
                           "%s × %s = %s; %s − %s = %s" % (_pena(num_c["base_dias"]), num_c["prop"], _pena(num_c["reducao"]), _pena(num_c["antes"]),
                                                           _pena(num_c["reducao"]), _pena(num_c["depois"])),
                           "a pena remanescente passa de %s para %s e alimenta os demais cálculos" % (_pena(num_c["antes"]), _pena(num_c["depois"])))}
    out["comutacao"] = {"status": st_c, "rotulo": rv.curto_indulto(txt_c) or txt_c, "texto_aba": txt_c, "checklist": ck, "reducao": red,
                        "fracao": num_c.get("fracao", ""), "exigido": num_c.get("exigido"), "exigido_txt": _pena(num_c["exigido"]) if num_c.get("exigido") is not None else ""}
    ind["fundamentacao"] = _fundamentacao(out, "indulto")
    out["comutacao"]["fundamentacao"] = _fundamentacao(out, "comutacao", num_c)
    return out


def _pena_ext(t):
    """'2a5m9d' -> '2 anos, 5 meses e 9 dias' (texto para petição)."""
    m = re.match(r"^(\d+)a(\d+)m(\d+)d$", t or "")
    if not m:
        return t or ""
    a, me, d = (int(x) for x in m.groups())
    p = [("%d ano%s" % (a, "s" if a != 1 else "")) if a else "", ("%d %s" % (me, "meses" if me != 1 else "mês")) if me else "",
         ("%d dia%s" % (d, "s" if d != 1 else "")) if d else ""]
    p = [x for x in p if x]
    return (", ".join(p[:-1]) + " e " + p[-1]) if len(p) > 1 else (p[0] if p else "0 dias")


def _ext_txt(t):
    return re.sub(r"\b\d+a\d+m\d+d\b", lambda m: _pena_ext(m.group(0)), t or "")


def _fund_curto(f):
    """Fundamento do item do checklist, só o dispositivo (sem as notas da base)."""
    f = (f or "").split(";")[0]
    f = re.split(r"\s*\(", f)[0]
    return f.replace(", caput e parágrafo único", "").strip().rstrip(".")


def _hip_txt(t):
    """'Inciso XV: crime patrimonial ... - verificar ... Depende de dado...' -> 'inciso XV (crime patrimonial ...)'."""
    t = re.sub(r"\s*Depende de dado que o RSPE não traz\.?", "", t)
    t = re.sub(r"\s*-\s*verificar ([^.]*)\.?", r"; a conferir: \1.", t)
    t = re.sub(r"\.\s*Exige", "; exige", t)
    m = re.match(r"^Inciso ([IVXL]+(?: e [IVXL]+)?):\s*(.*)$", t.strip(), re.S)
    t = ("inciso %s (%s)" % (m.group(1), m.group(2).strip().rstrip("."))) if m else t.strip().rstrip(".")
    return t[0].lower() + t[1:] if t.startswith("Requisito") else t


def _fundamentacao(out, tipo, num_c=None):
    """Fundamentação pronta para a petição (botão "Copiar fundamentação"), no padrão do programa: título, um parágrafo com
    os fatos e os fundamentos (dispositivo entre parênteses) e o pedido. Usa só o que a aba já concluiu."""
    x = out.get(tipo) or {}
    ind = out.get("indulto") or {}
    num, ref, pub = out.get("numero", ""), out.get("referencia", ""), out.get("publicacao", "")
    dec = "Decreto nº %s" % num
    indulto = tipo == "indulto"
    st = x.get("status")
    red = x.get("reducao")
    tit = "%s - %s%s" % ("DO INDULTO" if indulto else "DA COMUTAÇÃO", dec, (" (data de referência %s)" % ref) if ref else "")
    fatos = []
    if ind.get("cumprido_txt"):
        fatos.append("Na data de referência do %s (%s), o(a) assistido(a)%s cumpria a pena de %s e havia cumprido %s, somados o tempo de "
                     "prisão, a detração (CP, art. 42) e a remição (LEP, art. 128)" % (
                         dec, ref, (", " + ind["reinc"] + ",") if ind.get("reinc") else "", _pena_ext(ind.get("pena_considerada_txt", "")), _pena_ext(ind["cumprido_txt"])))
    hip = [re.sub(r"\s*Não atendidos:.*$", "", c["texto"], flags=re.S) for c in x.get("checklist") or []
           if c["item"].startswith("Requisito objetivo") and c.get("estado") in ("ok", "q")]
    hip = [_hip_txt(_ext_txt(t)) for t in hip if t.strip()]
    if tipo == "comutacao" and num_c and num_c.get("exigido") is not None and not any(h.startswith("Requisito") for h in hip):
        hip.append("o decreto exige %s da pena (%s)" % (num_c.get("fracao", ""), _pena_ext(_pena(num_c["exigido"]))))
    im = out.get("imputacao")
    imp_txt = ""
    if im:
        imp_txt = ("Em concurso com crime impeditivo (%s), %s da pena de %s (%s) imputa-se primeiro ao crime impeditivo%s; o tempo que sobra "
                   "(%s) é o considerado para %s" % (
                       re.sub(r"\s*\((.*)\)$", r"; \1", im.get("dispositivo", "")), "a totalidade" if im["fracao"] == "100%" else im["fracao"], ", ".join(im["crimes_imp"]),
                       _pena_ext(im["exigido_txt"]), (", o que se deu em %s" % im["data"]) if im.get("data") else "",
                       _pena_ext(im.get("sobra_txt", "")), ", ".join(im["crimes_liv"]) or "os demais crimes"))
    # requisitos atendidos, em uma frase cada, com o dispositivo
    req, pend = [], []
    for c in x.get("checklist") or []:
        if c["item"].startswith("Requisito objetivo"):
            continue
        if c["item"] == "Ressalva" and re.match(r"^(FALTA nos|Art\. 6º)", c["texto"]):
            continue
        t = _ext_txt(c["texto"]).strip()
        t = re.sub(r"\s*Não cabe o indulto nem a comutação.*$", "", t, flags=re.S)
        t = re.sub(r"Data da infração: (\S+) \(\1\)", r"fato em \1", t).strip().rstrip(".")
        fnd = _fund_curto((c.get("det") or {}).get("fundamento", ""))
        frase = "%s%s" % (t[0].lower() + t[1:] if t else "", (" (%s)" % fnd) if fnd else "")
        if im and re.match(r"concurso com impeditivo", frase, re.I):
            continue  # já explicado na frase da imputação
        (req if c.get("estado") in ("ok", "info") else pend).append(frase)
    par = []
    if fatos:
        par.append(fatos[0] + ".")
    if hip and st in ("cabe", "verificar", "ainda"):
        par.append("Enquadra-se %s: %s." % ("no art. 9º" if indulto else "no art. 13", "; ".join(hip)))
    if imp_txt:
        par.append(imp_txt + ".")
    if req and st in ("cabe", "verificar", "ainda"):
        par.append("Quanto aos demais requisitos do %s: %s." % (dec, "; ".join(req)))
    corpo = " ".join(par)
    if st == "cabe":
        if indulto:
            ped = "Preenchidos os requisitos, requer-se a concessão do indulto, com a declaração da extinção da punibilidade (CP, art. 107, II; LEP, art. 192)."
        else:
            ped = ("Preenchidos os requisitos, requer-se a comutação da pena%s (LEP, art. 192)." % (
                (": redução de %s da pena %s (%s), passando a pena remanescente de %s para %s" % (
                    red["fracao"], red["base"], _pena_ext(red["reducao_txt"]), _pena_ext(red["antes_txt"]), _pena_ext(red["depois_txt"]))) if red else ""))
    elif st == "ainda" and x.get("projecao"):
        pj = x["projecao"]
        ped = "O requisito objetivo (%s, %s) é atingido em %s%s: o pedido deve ser feito a partir dessa data." % (
            pj.get("hipotese", ""), _pena_ext(pj.get("exigido_txt", "")), pj.get("data", ""), " (projeção, a depender de novo decreto nas mesmas condições)" if pj.get("projecao") else "")
    elif st == "verificar":
        conf = [re.search(r"a conferir: (.+?)(?=; exige|; cumprido|\)$|$)", h).group(1).rstrip(".") for h in hip if "a conferir:" in h]
        ped = "A conferir nos autos: %s. Confirmado, requer-se %s." % (
            "; ".join(pend + conf) if (pend or conf) else _ext_txt(x.get("rotulo", "")).rstrip("."),
            "a concessão do indulto, com a declaração da extinção da punibilidade (CP, art. 107, II; LEP, art. 192)" if indulto else "a comutação da pena (LEP, art. 192)")
    elif st == "prejudicada":
        ped = "Prejudicada: cabível o indulto, que prevalece sobre a comutação (%s, art. 13, § 5º)." % dec
    else:
        ped = "Não cabe %s: %s." % ("o indulto" if indulto else "a comutação", "; ".join(pend) if pend else _ext_txt(x.get("rotulo", "")).rstrip("."))
        corpo = " ".join(par[:1])  # sem pedido: só a situação na data e o motivo
    return "\n".join(p for p in (tit, corpo, ped) if p.strip())


TITULO = {"cabe": "CABE", "nao": "NÃO CABE", "verificar": "A VERIFICAR", "ainda": "AINDA NÃO - PROJEÇÃO", "concedido": "CONCEDIDO NO RSPE",
          "prejudicada": "PREJUDICADA"}


def _consolidado(decs, C):
    """Um cartão por decreto (indulto e comutação), com o resultado da aba e o motivo decisivo."""
    cards = []
    for d in decs:
        for tipo in ("indulto", "comutacao"):
            x = d.get(tipo) or {}
            if not x.get("status") or (tipo == "comutacao" and not x.get("texto_aba")):
                continue
            st = x["status"]
            tit = TITULO.get(st, "")
            if st == "cabe":
                tit = "CABE INDULTO" if tipo == "indulto" else "CABE COMUTAÇÃO"
            linhas = ["Resultado da aba: %s" % x.get("rotulo", "")]
            red = x.get("reducao")
            if red:
                linhas.append("Fração %s sobre a pena %s; remanescente passa de %s para %s." % (red["fracao"], red["base"], red["antes_txt"], red["depois_txt"]))
            if st != "cabe":
                ck = x.get("checklist") or []
                ordem = ("q", "ko") if st == "verificar" else ("ko", "q")
                mot = [c for c in ck if c["estado"] == ordem[0]] + [c for c in ck if c["estado"] == ordem[1]]
                # o motivo decisivo vem primeiro: falta grave do art. 6º e vedação, antes dos incisos não atendidos
                mot.sort(key=lambda c: 0 if (c["texto"].startswith("Art. 6º") or c["item"].startswith("Requisito subjetivo")) else
                         (1 if c["item"].startswith("Natureza") else 2))
                if mot:
                    linhas.append("Motivo: %s" % mot[0]["texto"])
            if x.get("projecao") and x["projecao"].get("data"):
                linhas.append("Atinge o requisito objetivo (%s) em %s." % (x["projecao"].get("hipotese", ""), x["projecao"]["data"]))
            cards.append({"decreto": d["numero"], "tipo": tipo, "status": st, "titulo": tit, "linhas": linhas,
                          "projecao": bool(x.get("projecao") and x["projecao"].get("data"))})
    return cards
