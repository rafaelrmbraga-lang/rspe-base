"""Decretos de indulto e comutação de 2000 em diante, num motor só (aba Indulto).

Cada decreto é uma ficha de dados na base jurídica (chave "decretos_fichas"): data de referência, hipóteses de indulto
(pena máxima, fração ou anos cumpridos por reincidência, violência ou grave ameaça, regime), comutação, crimes
impeditivos e janela da falta grave. O motor lê qualquer ficha; corrigir ou acrescentar um decreto é editar a base.
Os decretos de 2022, 2024 e 2025 seguem com a análise detalhada que o programa já fazia (rspe_scraper), e os
benefícios já decididos no RSPE (incidente de indulto ou comutação que cita o decreto) prevalecem sobre o cálculo.

Resultado por decreto: cabe | nao | imp (crime impeditivo) | conc (concedido) | indef (indeferido) |
fora (não alcançado: execução posterior ou sem condenação até o decreto) | ver (falta dado no RSPE: só quando sem ele a conta
não fecha)."""
import re
from datetime import date, timedelta
from fractions import Fraction

import rspe_scraper as rs

# análise detalhada já existente no programa (rspe_scraper): o motor só traduz o resultado
DETALHADOS = {"2022": ("11.302", "indulto_2022", None), "2024": ("12.338", "indulto_2024", "comutacao_2024"),
              "2025": ("12.790", "indulto_2025", "comutacao_2025")}
# datas de referência dos decretos detalhados (rs.DECRETOS só traz 2024 e 2025, os do rol do art. 1º)
_REF_DET = {"2022": date(2022, 12, 25), "2024": date(2024, 12, 25), "2025": date(2025, 12, 25)}
MAPA_STATUS = {"possivel": "cabe", "nao": "nao", "vedado": "imp", "verificar": "ver"}


def fichas():
    """Fichas dos decretos na base jurídica (lista), ordenadas por data de referência."""
    try:
        import rspe_regras as rg
        lst = (rg.carregar() or {}).get("decretos_fichas") or []
    except Exception:
        lst = []
    return sorted([f for f in lst if rs.to_date(f.get("data_referencia") or "")], key=lambda f: rs.to_date(f["data_referencia"]))


def _fr(t):
    try:
        return Fraction(str(t).strip()) if t else None
    except (ValueError, ZeroDivisionError):
        return None


def _dias_txt(n):
    return rs.dias_para_pena(n) if n >= 365 else rs.pl(n, "dia", "dias")


def inicio_cumprimento(r):
    """Início do cumprimento informado no RSPE: a primeira prisão ou início de cumprimento dos eventos; sem eventos, o
    primeiro trânsito em julgado. Não usa o número do processo."""
    per = rs.periodos_custodia(r.get("_eventos") or [])
    ds = [a for a, _b in per if a]
    if ds:
        return min(ds)
    trs = [rs.to_date(c.get("transito_processo") or c.get("transito_mp") or "") for c in r.get("_crimes") or []]
    trs = [d for d in trs if d]
    return min(trs) if trs else None


def decididos(r):
    """{(ano, 'indulto'|'comutacao'): (situacao, data, numero)} pelos incidentes do RSPE que citam o decreto."""
    out = {}
    for i in r.get("_incidentes") or []:
        tipo = (i.get("tipo") or "").upper()
        if not re.search(r"INDULTO|COMUTA", tipo):
            continue
        txt = rs._sem_acento((i.get("complemento") or "") + " " + tipo).upper()
        m = re.search(r"DECRETO\s*(?:N[ºO°.]*\s*)?([\d.]+)?.*?(?:DE\s+)?(\d{4})", txt)
        anos = re.findall(r"\b(20\d\d|199\d)\b", txt)
        if not anos:
            continue
        ano = anos[-1]
        num = (m.group(1) or "").strip(".") if m else ""
        if re.search(r"MAES|DIA DAS M", txt) or num.replace(".", "") == "9370":
            ano += "_maes"  # Dia das Mães (2017 s/n e 2018, nº 9.370): não se confunde com o natalino do mesmo ano
        sit = (i.get("situacao") or "").upper()
        s = "indef" if re.search(r"N[AÃ]O CONCEDID|INDEFERID|NEGAD", rs._sem_acento(sit)) else ("conc" if "CONCEDID" in sit else "")
        if not s:
            continue
        out[(ano, "indulto" if "INDULTO" in tipo else "comutacao")] = (s, i.get("data_decisao") or i.get("data_referencia") or "", num)
    return out


def _regime_em(r, ref):
    """Regime na data (última fixação/alteração de regime até ref), em minúsculas sem acento; '' se o RSPE não informa."""
    ult = None
    for i in r.get("_incidentes") or []:
        if "REGIME" not in (i.get("tipo") or "").upper() or (i.get("situacao") or "").upper() != "CONCEDIDO":
            continue
        d = rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "")
        if d and d <= ref and (ult is None or d >= ult[0]):
            ult = (d, rs._sem_acento(i.get("complemento") or "").lower())
    if not ult:
        return ""
    for nome in ("semiaberto", "aberto", "fechado"):
        if nome in ult[1]:
            return nome
    return ""


def _regime_inicial(r, crimes, ref):
    """Sem nenhum incidente de regime até a data, vale o regime fixado na sentença (se todos os crimes o têm e é o mesmo)."""
    if any("REGIME" in (i.get("tipo") or "").upper() and (rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "") or date.max) <= ref
           for i in r.get("_incidentes") or []):
        return ""
    regs = set()
    for c in crimes:
        t = rs._sem_acento(c.get("regime_sentenca") or "").lower()
        nome = next((n for n in ("semiaberto", "aberto", "fechado") if n in t), "")
        if not nome:
            return ""
        regs.add(nome)
    return regs.pop() if len(regs) == 1 else ""


def _em_execucao(c, ref):
    """Pena em execução na data do decreto: crime não extinto, ou extinto DEPOIS dela (a extinção posterior não tira a pena
    do alcance do decreto). Extinto sem data no RSPE: fica fora, como antes."""
    if not (c.get("extinto") or "").upper().startswith("S"):
        return True
    d = rs.to_date(c.get("data_extincao") or "")
    return bool(d and d > ref)


def _alcancados(r, ref, pub):
    """Crimes que o decreto alcança: fato até a data de referência, sentença até a publicação e pena em execução na data."""
    return [c for c in (r.get("_crimes") or []) if _em_execucao(c, ref)
            and (rs.to_date(c.get("data_infracao") or "") or date.min) <= ref
            and (rs.to_date(c.get("data_sentenca") or "") or date.min) <= pub]


def _fora_do_decreto(r, ref, pub):
    """Nenhuma condenação alcançada pelo decreto: todo crime tem fato posterior à data, sentença posterior à publicação ou
    extinção registrada até a data. Extinto sem data no RSPE não decide (pode ter sido extinto depois)."""
    def fora(c):
        ext = (c.get("extinto") or "").upper().startswith("S")
        d_ext = rs.to_date(c.get("data_extincao") or "")
        return ((rs.to_date(c.get("data_infracao") or "") or date.min) > ref or (rs.to_date(c.get("data_sentenca") or "") or date.min) > pub
                or bool(ext and d_ext and d_ext <= ref))
    return bool(r.get("_crimes")) and all(fora(c) for c in r.get("_crimes") or [])


def _vd(c):
    """Violência contra a mulher pelo RSPE (rs.violencia_domestica), sem tomar o art. 129, §§ 9º a 11, como certa: o rótulo
    "Violência Doméstica" do tipo é o do próprio § 9º, cuja vítima pode ser de qualquer sexo - fica provável (confirmar a vítima)."""
    v = rs.violencia_domestica(c)
    if v and v[0] == "sim" and v[1].startswith("tipo penal") and rs.num_art(c.get("artigo")) == "129":
        m = re.match(r"\s*§\s*(\d+)", c.get("tipo_penal") or "")
        if m and m.group(1) in ("9", "10", "11"):
            return ("provavel", "art. 129, § %sº (violência doméstica): a vítima pode ser de qualquer sexo - confirmar se é mulher" % m.group(1))
    return v


def _cumprido(r, ctx, ref):
    """Pena cumprida na data (rs.cumprido_na_data, ancorada no SEEU). RSPE com a pena total zerada (execução extinta depois da
    data, caso dos crimes extintos após o decreto, ou cálculo ausente no SEEU): a âncora não vale - soma custódia, livramento e
    remições até a data."""
    if not rs.pena_para_dias(r.get("pena_total")):
        todos = rs.uniao_periodos(list(ctx["periodos"]) + list(ctx["lc"]))
        return rs.dias_cumpridos_ate(todos, ctx["rem"], ref), "custódia e livramento + remições até a data (o RSPE traz a pena zerada)"
    return rs.cumprido_na_data(r, ctx["periodos"], ctx["rem"], ref, ctx["lc"])


def _lc_duvida(r, ctx, ref):
    """Livramento condicional em curso na data, sem custódia, com indício no RSPE de suspensão ou revogação (mesma checagem de
    2024/2025, rs.duvidas_livramento, a partir do deferimento): texto do 'a verificar', ou ''."""
    if rs.em_custodia(ctx["periodos"], ref):
        return ""
    per = [(a, b) for a, b in ctx["lc"] if a <= ref and (b is None or b >= ref)]
    if not per:
        return ""
    a, b = max(per)
    if b is None and r.get("_lc_confirmado"):
        return ""  # livramento atual confirmado pelo operador (baixa na Auditoria)
    duv = rs.duvidas_livramento(r, r.get("_eventos") or [], r.get("_incidentes") or [], dl=a)
    if not duv:
        return ""
    return ("livramento condicional desde %s com situação incerta no RSPE (%s): conferir se estava em curso em %s e não foi revogado - "
            "revogado, o tempo do livramento não conta como pena cumprida (CP, art. 88)" % (rs.fmt(a), "; ".join(duv[:3]), rs.fmt(ref)))


_HED_CACHE = {}  # hediondez na data do fato, por crime (a mesma em todos os decretos); limpo a cada avaliar()


def _impeditivos(f, crimes, ref, pena_total=None, ver=None, contexto=None):
    """Crimes da soma que o decreto veda (hediondos e equiparados na data do fato, tortura, terrorismo, tráfico e a lista
    própria do decreto). ver (lista): recebe os crimes que só são impeditivos conforme dado que o RSPE não traz (violência
    contra a mulher provável ou pelo contexto da execução); contexto: crimes da execução para esse contexto."""
    I = f.get("impeditivos") or {}
    out = []
    lim = I.get("nao_aplica_pena_ate_anos")
    if lim and pena_total is not None and pena_total <= rs.dias_anos(lim, ref):
        return []  # ex.: 2002, art. 7º, § 2º - as restrições não se aplicam à pena aplicada de até 4 anos
    for c in crimes:
        lei, art = rs.num_lei(c.get("lei")), rs.num_art(c.get("artigo"))
        rot = rs.crimes_curto([c]).strip()
        pi = rs.paragrafo_inciso(c) or ("", "")
        par = re.match(r"\d*", pi[0]).group(0)
        # tráfico equiparado a hediondo: art. 12 (e 13) da Lei 6.368 e art. 33, caput e § 1º, da Lei 11.343. Fora: associação
        # (art. 14 / art. 35 - o STJ não a equipara), os §§ 2º e 3º do art. 33 (induzimento e uso compartilhado) e o § 4º
        # (privilegiado - STF, HC 118.533), salvo vedação expressa do decreto (trafico_privilegiado_ressalvado = false)
        trafico = (lei == "6368" and art in ("12", "13")) or (lei == "11343" and art == "33" and par not in ("2", "3", "4"))
        priv = _priv(c)
        priv_vedado = priv and I.get("trafico_privilegiado_ressalvado") is False
        # hediondos, tortura, tráfico e terrorismo: vedados pela própria lei (CF, art. 5º, XLIII; Lei 8.072, art. 2º, I), ainda
        # que o decreto não os liste (ex.: Dia das Mães 2017 e 2018)
        if True:
            fato = rs.to_date(c.get("data_infracao") or "")
            # hediondez aferida na data do FATO: a superveniente não alcança o fato anterior (os decretos falam em "crime
            # hediondo praticado após" a Lei 8.072/1990 e as que ampliaram o rol). Tráfico: equiparado desde 25/07/1990
            if id(c) not in _HED_CACHE:
                _HED_CACHE[id(c)] = (c, rs.e_hediondo(c, None))
            if priv_vedado or (not priv and (_HED_CACHE[id(c)][1] or (trafico and (fato or ref) >= date(1990, 7, 25)))):
                out.append("%s: %s%s" % (rot, "tráfico privilegiado vedado pelo decreto" if priv_vedado else "hediondo ou equiparado na data do fato",
                                         (" (%s)" % rs.fmt(fato)) if fato and not priv_vedado else ""))
                continue
        for o in I.get("outros") or []:
            lt = str(o.get("lei") or "")
            if re.search(r"\bCPM\b|MILITAR", lt, re.I):
                continue  # Código Penal Militar: crimes que o SEEU estadual não executa
            if re.search(r"viol[eê]ncia contra a mulher", o.get("descricao") or "", re.I):
                # vedação pelo contexto (Lei 11.340 e crimes do CP contra a mulher), não pelo número da lei do crime
                v = _vd(c)
                if v and v[0] == "sim":
                    out.append("%s: %s (%s)" % (rot, o["descricao"], v[1]))
                    break
                mot = v[1] if v else rs.vd_contexto(c, contexto or crimes)
                if mot and ver is not None:
                    ver.append("%s: %s" % (rot, mot))
                continue
            leis = rs.num_lei(lt) if lt and not re.search(r"\bCP\b|PENAL", lt, re.I) else "2848"
            if not (lei == leis or (leis == "2848" and lei in ("", "2848"))):
                continue
            if o.get("exceto_pena_ate_anos") and (rs.pena_para_dias(c.get("pena_imposta") or c.get("pena_total_processo")) or 0) <= rs.dias_anos(o["exceto_pena_ate_anos"], ref):
                continue  # "exceto quando a pena aplicada não for superior a quatro anos" (ex.: 2023, art. 1º, III, V, IX e X)
            arts = o.get("artigos") or []
            if not arts and rs.num_lei(lt) and leis != "2848":
                arts = [art]  # lei inteira vedada (ex.: tortura, terrorismo, lavagem)
            if priv and not priv_vedado:
                # privilegiado: só a vedação que cite o § 4º expressamente o alcança
                arts = [a for a in arts if re.search(r"§\s*4", str(a))]
            if art and any(_artigo_vedado(a, art, c) for a in arts):
                out.append("%s: %s" % (rot, o.get("descricao") or "vedado pelo decreto"))
                break
    return list(dict.fromkeys(out))


def _priv(c):
    """Tráfico privilegiado (Lei 11.343, art. 33, § 4º), pelo parágrafo lido do tipo penal."""
    if rs.num_lei(c.get("lei")) != "11343" or rs.num_art(c.get("artigo")) != "33":
        return False
    pi = rs.paragrafo_inciso(c)
    return bool((pi and pi[0] == "4") or "§ 4" in (c.get("tipo_penal") or ""))


def _art_num(t):
    """'217-A' -> (217, 'A'); '33' -> (33, '')."""
    m = re.match(r"\s*(\d+)(?:\s*-\s*([A-Z]))?", t or "", re.I)
    return (int(m.group(1)), (m.group(2) or "").upper()) if m else None


def _artigo_vedado(entrada, art, c):
    """Se o crime (art do RSPE, ex.: '217-A', e parágrafo do tipo penal) está na entrada da lista de vedações do decreto:
    '33', '217-A', '239 a 244-B' (intervalo), '33 caput', '33, §1º', '157, §2º, I', '1º § 2º'. Entrada com 'ressalvado'
    não veda. Com parágrafo indicado, o crime precisa estar nele (o 'caput' vale para o crime sem parágrafo)."""
    e = str(entrada)
    if re.search(r"ressalv", e, re.I):
        return False
    alvo = _art_num(art)
    if not alvo:
        return False
    m = re.match(r"\s*(\d+\s*(?:-\s*[A-Z])?)\s*[ºo°]?\s*a\s*(\d+\s*(?:-\s*[A-Z])?)", e, re.I)
    if m:  # intervalo de artigos
        lo, hi = _art_num(m.group(1)), _art_num(m.group(2))
        return bool(lo and hi and lo <= alvo <= (hi if hi[1] else (hi[0], "Z")))  # (359, "I") <= (359, "K") <= (359, "R")
    base = _art_num(e)
    if not base or base != alvo:
        return False
    resto = re.sub(r"^\s*\d+\s*(?:-\s*[A-Z](?![a-z]))?\s*[ºo°]?", "", e, flags=re.I)
    pars = set(re.findall(r"§\s*(\d+)", resto))
    caput = bool(re.search(r"caput", resto, re.I))
    if not pars and not caput:
        return True  # artigo inteiro
    pi = rs.paragrafo_inciso(c)
    par = re.match(r"\d+", pi[0]).group(0) if pi and pi[0] and pi[0][0].isdigit() else ""
    if not pi:
        return caput  # parágrafo ilegível: a vedação do caput alcança; a de parágrafo, não
    if not par:
        return caput
    if par not in pars:
        return False
    # inciso indicado na vedação (ex.: "157, §2º, I"): o crime precisa estar nele, se o RSPE o informar
    incs = set(x.upper() for x in re.findall(r"§\s*%s\s*[ºo°]?\s*,?\s*((?:[IVXL]+)(?:\s*(?:,|e)\s*[IVXL]+)*)\b" % par, resto) for x in re.findall(r"[IVXL]+", x))
    return not (incs and pi[1] and pi[1].upper() not in incs)


def _regra_concurso(f):
    """Fração da pena do crime impeditivo que precisa estar cumprida para o benefício alcançar os demais crimes (concurso),
    lida do texto da ficha: 2/3 (2009 em diante) ou a pena inteira (2006 a 2008). None se o decreto não prevê."""
    t = rs._sem_acento(" ".join([str((f.get("impeditivos") or {}).get("texto") or "")] + [str(x) for x in (f.get("observacoes") or [])])).lower()
    for frase in re.split(r"(?<=[.;])\s+", t):
        if not re.search(r"concurso|crimes? impeditiv|crimes? referidos? no", frase):
            continue
        if re.search(r"dois tercos|2/3", frase):
            return Fraction(2, 3)
        if re.search(r"integral|cumprida a pena|cumprido a pena|cumprimento da pena do", frase):
            return Fraction(1)
    return None


def _ctx(r):
    eventos, incidentes = r.get("_eventos") or [], r.get("_incidentes") or []
    rem = []
    for i in incidentes:
        if rs.e_remicao_concedida(i):
            n = rs.dias_de(i.get("complemento", ""))
            if n is not None:
                rem.append((rs.to_date(i.get("data_referencia") or i.get("data_decisao") or ""), n))
    return {"periodos": rs.periodos_custodia(eventos), "lc": rs.periodos_livramento(eventos, incidentes), "rem": rem}


def avaliar_ficha(f, r, ctx, ini, hoje):
    """Avalia o decreto; com o cumprimento interrompido na data (fuga, soltura), o resultado favorável vira A VERIFICAR: o decreto
    exige a fração cumprida ATÉ a data, não a custódia NA data, e a interrupção pode ter sido punida como falta grave."""
    x = _avaliar_ficha(f, r, ctx, ini, hoje)
    vd_ver = x.pop("_vd_ver", None) or []
    if x.pop("_interr", False):
        ref_t = x.get("ref") or ""
        if x.get("s") == "cabe":
            x.update(s="ver", mot="%s; o cumprimento estava interrompido em %s (não estava preso nem em livramento): o decreto exige a fração "
                                  "cumprida até a data, não a custódia na data - conferir se a interrupção (fuga) foi punida como falta grave"
                                  % (x.get("mot") or "", ref_t))
        elif x.get("s") == "nao":
            x["mot"] = "cumprimento interrompido em %s (não estava preso nem em livramento); %s" % (ref_t, x.get("mot") or "")
    if x.get("s") == "cabe":
        tr = transito_pendente(f, r)
        if tr:
            x.update(s="ver", mot="%s; %s" % (x.get("mot") or "", tr) if x.get("mot") else tr)
    if x.get("s") == "cabe" and vd_ver:
        # violência contra a mulher que o RSPE não confirma (vítima, vara): se houve, o crime é impeditivo
        x.update(s="ver", mot="%s; A VERIFICAR - conferir se houve violência contra a mulher (vedação do %s): %s" % (
            x.get("mot") or "", (f.get("impeditivos") or {}).get("dispositivo") or "decreto", "; ".join(vd_ver)))
    if x.get("s") == "cabe":
        lcd = _lc_duvida(r, ctx, rs.to_date(f["data_referencia"]))
        if lcd:
            x.update(s="ver", mot="%s; A VERIFICAR - %s" % (x.get("mot") or "", lcd))
    return x


# condenação sem trânsito em julgado para a acusação até a publicação do decreto: o STJ e o TJMS aferem o requisito objetivo
# na data da publicação e exigem o trânsito ao menos para a acusação (ou a ausência de recurso dela, nos termos de cada decreto)
STJ_TRANSITO = ("STJ: o requisito se afere na publicação e exige o trânsito ao menos para a acusação (AgRg no HC 633.240, 6ª T., 15/06/2021; "
                "AgRg no HC 864.086, 5ª T., 18/12/2023; AgRg nos EDcl no HC 991.402, 6ª T., 29/04/2026)")


def transito_pendente(f, r):
    """Texto do 'a verificar' quando alguma condenação alcançada pelo decreto (fato até a referência e sentença até a
    publicação) não tinha trânsito para a acusação na publicação; '' se todas tinham. A regra de cada decreto vem da ficha
    (transito.regra): nao_majorar, sem_transito_defesa, pos_2grau, vedado_pos_2grau, nao_trata."""
    ref = rs.to_date(f["data_referencia"])
    pub = rs.to_date(f.get("data_publicacao") or "") or ref
    T = f.get("transito") or {}
    regra, disp = T.get("regra") or "nao_trata", T.get("dispositivo") or ""
    crimes = _alcancados(r, ref, pub)
    pend, sem_dado = [], []
    for c in crimes:
        tm, tp = rs.to_date(c.get("transito_mp") or ""), rs.to_date(c.get("transito_processo") or "")
        if (tm and tm <= pub) or (not tm and tp and tp <= pub):
            continue
        (pend if (tm or tp) else sem_dado).append(c)
    if not pend and not sem_dado:
        return ""
    partes = []
    if sem_dado:
        partes.append("trânsito em julgado não consta no RSPE (%s): conferir se havia trânsito para a acusação em %s" % (rs.crimes_curto(sem_dado), rs.fmt(pub)))
    if pend:
        lst = "; ".join("%s, sentença %s, trânsito para a acusação %s%s" % (
            rs.crimes_curto([c]), c.get("data_sentenca") or "não informada", c.get("transito_mp") or c.get("transito_processo") or "?",
            " (logo após a sentença: a acusação não recorreu)" if rs._sem_recurso_acusacao(c) else "") for c in pend)
        regra_txt = {
            "nao_majorar": "o decreto (%s) admite o benefício com recurso da acusação que não vise majorar a pena - alcança se a acusação não recorreu ou o recurso não buscava aumentar a pena" % disp,
            "sem_transito_defesa": "o decreto (%s) dispensa só o trânsito para a defesa - sem trânsito para a acusação na publicação, não alcança pelo STJ" % disp,
            "pos_2grau": "o decreto (%s) admite o benefício com recurso da acusação após a 2ª instância - alcança se, na publicação, a acusação só recorria aos tribunais superiores" % disp,
            "vedado_pos_2grau": "o decreto (%s) VEDA o indulto se havia recurso da acusação de qualquer natureza após a 2ª instância - conferir se havia recurso da acusação na publicação" % disp,
            "nao_trata": "o decreto não trata do trânsito em julgado nem do recurso da acusação",
        }.get(regra, "")
        partes.append("trânsito para a acusação depois da publicação (%s): %s (%s)" % (rs.fmt(pub), lst, regra_txt))
    return "A VERIFICAR - " + "; ".join(partes) + ". " + STJ_TRANSITO


def _avaliar_ficha(f, r, ctx, ini, hoje):
    ref = rs.to_date(f["data_referencia"])
    pub = rs.to_date(f.get("data_publicacao") or "") or ref
    base = {"id": f["id"], "ano": f.get("ano"), "numero": f.get("numero") or "", "ref": rs.fmt(ref), "tipo": f.get("tipo") or "natalino"}
    if ref > hoje:
        return dict(base, s="futuro", mot="data de referência futura")
    if not ini or ini > ref:
        return dict(base, s="fora", mot="execução posterior ao decreto")
    if (f.get("publico") == "mulheres") and (r.get("_sexo") or "") != "F":
        return dict(base, s="fora", mot="decreto só para mulheres" + ("" if r.get("_sexo") else " (sexo não informado)"))
    crimes = _alcancados(r, ref, pub)
    if not crimes:
        return dict(base, s="fora", mot="sem condenação até o decreto (sentença posterior à publicação não é alcançada: STJ, AgRg no HC 441.551 e AgRg no HC 919.210)"
                    if any((rs.to_date(c.get("data_sentenca") or "") or date.min) > pub for c in (r.get("_crimes") or [])) else "sem condenação até o decreto")
    # mesma regra da análise detalhada (2022/2024/2025): os requisitos de tempo exigem cumprimento em curso na data -
    # preso ou em livramento condicional; a prisão provisória anterior, encerrada antes da data, só entra como detração
    if not (rs.em_custodia(ctx["periodos"], ref) or any(a <= ref and (b is None or b >= ref) for a, b in ctx["lc"])):
        defin = [e for e in (r.get("_eventos") or []) if re.search(r"PRIS|IN[ÍI]CIO|RECAPTURA", ((e.get("tipo") or "") + " " + (e.get("motivo") or "")).upper())
                 and not re.search(r"FLAGRANTE|PREVENTIV|TEMPOR|PROVIS", (e.get("motivo") or "").upper())
                 and (rs.to_date(e.get("data") or "") or date.max) <= ref]
        # prisão provisória que alcançou o trânsito em julgado virou cumprimento da pena (e a soltura/fuga depois o interrompeu)
        trs = [d for d in (rs.to_date(c.get("transito_processo") or c.get("transito_mp") or "") for c in r.get("_crimes") or []) if d and d <= ref]
        virou = any(a <= t and (b is None or b > t) for a, b in ctx["periodos"] for t in trs)
        if defin or virou:
            interrompido = True
        else:
            return dict(base, s="nao", mot="não se aplica: não iniciou o cumprimento até %s (a prisão anterior foi provisória: conta como detração, "
                                          "não como início do cumprimento da pena)" % rs.fmt(ref))
    else:
        interrompido = False
    base["_interr"] = interrompido
    pena = sum(rs.pena_para_dias(c.get("pena_imposta") or c.get("pena_total_processo")) or 0 for c in crimes)
    cump, _orig = _cumprido(r, ctx, ref)
    reinc = any(c.get("reincidente_comum") == "S" or c.get("reincidente_especifico") == "S" for c in crimes)
    vga = any(rs.vga_indulto(c) for c in crimes)
    detalhe = {"pena": pena, "cumprido": cump, "reincidente": reinc, "vga": vga, "crimes": [rs.crimes_curto([c]) for c in crimes]}
    vd_ver = []
    imp = _impeditivos(f, crimes, ref, pena, ver=vd_ver)
    base["_vd_ver"] = vd_ver
    nota_conc = ""
    lim = (f.get("impeditivos") or {}).get("nao_aplica_pena_ate_anos")
    if lim and pena <= rs.dias_anos(lim, ref) and _impeditivos(dict(f, impeditivos=dict(f["impeditivos"], nao_aplica_pena_ate_anos=None)), crimes, ref):
        nota_conc = ("restrições do decreto afastadas para pena aplicada de até %s anos (%s); para hediondo ou tráfico, ponto controvertido "
                     "diante da CF, art. 5º, XLIII" % (lim, (f.get("impeditivos") or {}).get("dispositivo") or "decreto"))
    if imp:
        # concurso com crime impeditivo: cumprida a fração exigida da pena dele, o benefício alcança os demais crimes, com o
        # tempo excedente imputado a eles
        frc = _regra_concurso(f)
        imp_cr = [c for c in crimes if any(x.startswith(rs.crimes_curto([c]).strip() + ":") for x in imp)]
        resto = [c for c in crimes if c not in imp_cr]
        if frc is not None and resto:
            pena_imp = sum(rs.pena_para_dias(c.get("pena_imposta") or c.get("pena_total_processo")) or 0 for c in imp_cr)
            exig_imp = int(-(-pena_imp * frc.numerator // frc.denominator))
            if cump >= exig_imp:
                nota_conc = ("cumpridos %s da pena do crime impeditivo (%s); benefício sobre os demais crimes - conta pela pena cumprida, "
                             "não pela ordem da linha do tempo do SEEU, que é só informativa (aviso do CNJ no próprio sistema)") % (
                                 str(frc) if frc != 1 else "a íntegra", rs.dias_para_pena(exig_imp))
                crimes, imp = resto, []
                pena = sum(rs.pena_para_dias(c.get("pena_imposta") or c.get("pena_total_processo")) or 0 for c in crimes)
                cump = cump - exig_imp
                vga = any(rs.vga_indulto(c) for c in crimes)
            else:
                imp = imp + ["faltavam %s para %s da pena do impeditivo (concurso)" % (_dias_txt(exig_imp - cump), str(frc) if frc != 1 else "a íntegra")]
    afeta = ((f.get("impeditivos") or {}).get("afeta") or "indulto e comutação").lower()
    # falta grave na janela (até a publicação)
    F = f.get("falta_grave") or {}
    falta_firme = falta_ind = []
    f_meses, f_afeta = F.get("meses"), (F.get("afeta") or "indulto e comutação").lower()
    if F.get("meses_vga") and vga:
        # crime com violência ou grave ameaça: janela maior (2002, art. 1º, § 1º, I; 2003, art. 3º, I - 24 meses)
        f_meses, f_afeta = F["meses_vga"], (F.get("afeta_vga") or f_afeta).lower()
    if f_meses or (F.get("texto") and F.get("meses") is None and re.search(r"punid", F.get("texto") or "", re.I)
                   and not re.search(r"n[ãa]o trata", F.get("texto") or "", re.I)):
        # janela de meses de calendário contada para trás da publicação (ou da data de referência, se o decreto assim
        # disser: 2015, 2023); sem janela fixada (Dia das Mães 2017), qualquer falta punida até a data
        base_f = ref if F.get("contada_de") == "referencia" else pub
        dias_f = rs.dias_anos(float(f_meses) / 12, base_f) if f_meses else 36500
        ach = rs.indicios_falta(r.get("_incidentes") or [], base_f, dias=dias_f, eventos=r.get("_eventos") or [], ate=min(pub, base_f), hoje=pub)  # prescrição da falta aferida na data do decreto
        # decreto que exige a falta apurada/homologada (ex.: "falta sem a devida apuração não impede"): a não homologada
        # (fuga só registrada como evento) não impede - fica como ressalva
        hom = F.get("exige_homologacao")
        falta_firme = [t for t, firme in ach if firme and not (hom and "não homologada" in t)]
        falta_ind = [t for t, firme in ach if not firme or (hom and "não homologada" in t)]
    # comutação concedida por decreto anterior (incidente do RSPE)
    com_ant = any(k[1] == "comutacao" and v[0] == "conc" and str(k[0])[:4].isdigit() and int(str(k[0])[:4]) < int(f.get("ano") or 0)
                  for k, v in decididos(r).items())
    regime = _regime_em(r, ref) or _regime_inicial(r, crimes, ref)
    em_lc = any(a <= ref and (b is None or b >= ref) for a, b in ctx["lc"])
    continuo = next(((ref - a).days + 1 for a, b in rs.uniao_periodos(ctx["periodos"]) if a <= ref and (b is None or b >= ref)), 0)

    priv_proprio = any(re.search(r"trafico privilegiado", rs._sem_acento(h.get("outros_requisitos") or "").lower()) for h in f.get("indulto") or [])

    def hip_ok(h, comut=False):
        """(atende, dias exigidos, motivo se não atende); atende=None: a conta fecha, mas o RSPE não informa o regime."""
        o = rs._sem_acento(h.get("outros_requisitos") or "").lower()
        if re.search(r"\bmulher|\bcondenadas?\b(?! a)", o) and (r.get("_sexo") or "") != "F":
            return False, None, "hipótese só para mulheres"
        if re.search(r"\bhomens?\b", o) and (r.get("_sexo") or "") == "F":
            return False, None, "hipótese só para homens"
        h_priv = bool(re.search(r"trafico privilegiado|33,? ?§ ?4|§ ?4o? do art\.? 33", o + " " + rs._sem_acento(h.get("texto") or "").lower()))
        if h_priv and not all(_priv(c) for c in crimes):
            return False, None, "hipótese só para o tráfico privilegiado"
        if not h_priv and not comut and priv_proprio and any(_priv(c) for c in crimes):
            return False, None, "o tráfico privilegiado tem hipótese própria neste decreto"
        rem_mode = "remanescente" in o and not comut  # na comutação, "remanescente" é a base da redução, não um teto
        if rem_mode and h.get("pena_max_anos") is None:
            nums = [int(x) for x in re.findall(r"(\d+)\s*anos", o)]
            if nums:
                h = dict(h, pena_max_anos=(nums[1] if (reinc and len(nums) > 1) else nums[0]))
        if h.get("pena_max_anos") is not None and rem_mode and pena - cump > rs.dias_anos(h["pena_max_anos"], ref):
            return False, None, "pena remanescente de %s acima de %s anos" % (rs.dias_para_pena(pena - cump), h["pena_max_anos"])
        if h.get("pena_max_anos") is not None and not rem_mode and pena > rs.dias_anos(h["pena_max_anos"], ref):
            return False, None, "pena total de %s acima de %s anos" % (rs.dias_para_pena(pena), h["pena_max_anos"])
        if h.get("pena_min_anos") is not None and pena <= rs.dias_anos(h["pena_min_anos"], ref):
            return False, None, "pena total não supera %s anos" % h["pena_min_anos"]
        if (h.get("violencia_grave_ameaca") or "") == "vedada" and vga:
            return False, None, "crime com violência ou grave ameaça"
        if (h.get("violencia_grave_ameaca") or "") == "exigida" and not vga:
            return False, None, "hipótese só para crime com violência ou grave ameaça"
        reg = [rs._sem_acento(x).lower() for x in (h.get("regime") or [])]
        sem_regime = ""
        if reg and not regime and not any("livramento" in x for x in reg):
            if h.get("ininterrupto") and continuo and all(re.match(r"fechado|semiaberto", x) for x in reg):
                pass  # custódia ininterrupta sem incidente de regime: fechado (o inicial não gera incidente) ou semiaberto
            else:
                sem_regime = "regime em %s não informado no RSPE (hipótese exige %s)" % (rs.fmt(ref), ", ".join(h["regime"]))
        lc_ate = rs.to_date(h.get("regime_ate") or "")
        if lc_ate and any("livramento" in x for x in reg):
            # "beneficiado com livramento condicional até 31 de dezembro de ...", sem revogação até a data de referência
            if not any(a <= lc_ate and (b is None or b >= ref) for a, b in ctx["lc"]):
                return False, None, "livramento condicional não concedido até %s (ou revogado)" % rs.fmt(lc_ate)
        elif reg and any("livramento" in x for x in reg) and not em_lc:
            if not regime and any("livramento" not in x for x in reg):
                sem_regime = "regime em %s não informado no RSPE (hipótese exige %s)" % (rs.fmt(ref), ", ".join(h["regime"]))
            elif not any(regime and x.split()[0] == regime for x in reg if "livramento" not in x):
                return False, None, "não estava em livramento condicional em %s" % rs.fmt(ref)
        elif reg and regime and not any(x.split()[0] == regime for x in reg):
            return False, None, "regime em %s: %s (exigido %s)" % (rs.fmt(ref), regime, ", ".join(h["regime"]))
        fr = _fr(h.get("fracao_reincidente") if reinc else h.get("fracao_nao_reincidente"))
        anos = h.get("anos_reincidente") if reinc else h.get("anos_nao_reincidente")
        fr_o = h.get("fracao_nao_reincidente") if reinc else h.get("fracao_reincidente")
        anos_o = h.get("anos_nao_reincidente") if reinc else h.get("anos_reincidente")
        if fr is None and anos is None and (fr_o or anos_o):
            # a hipótese só traz requisito para a outra condição: não alcança este caso (não é "sem requisito de tempo")
            return False, None, "hipótese só para %s" % ("não reincidentes" if reinc else "reincidentes")
        exig = None
        if fr is not None:
            exig = int(-(-pena * fr.numerator // fr.denominator))
        elif anos is not None:
            exig = rs.dias_anos(anos, ref)
        if comut and exig and com_ant and re.search(r"novo requisito temporal|independentemente de novo", rs._sem_acento(h.get("texto") or "") + " " + o, re.I):
            exig = 0  # já comutado em decreto anterior: a nova comutação dispensa novo requisito temporal
        base_c = cump
        if h.get("ininterrupto") and anos is not None:
            base_c = continuo  # anos ininterruptos: só a custódia contínua até a data (sem remição)
        if exig is not None and base_c < exig:
            if base_c is not cump:
                return False, exig, "faltavam %s de custódia ininterrupta para %s anos em %s" % (_dias_txt(exig - base_c), anos, rs.fmt(ref))
            return False, exig, "faltavam %s para %s em %s" % (_dias_txt(exig - cump), str(fr) if fr is not None else "%s anos" % anos, rs.fmt(ref))
        if sem_regime:
            return None, exig, sem_regime
        return True, exig, ""

    ind, ind_n, ind_ver = None, None, None   # hipótese atendida / a que chegou mais perto / a que depende do regime
    def _decisiva(h):
        # a hipótese só decide se tem algum requisito numérico (pena, fração ou anos); só regime não basta. Requisito positivo
        # que o RSPE não mostra (pena substituída ou sursis, fração cumprida em prisão provisória, saídas, idade, filhos,
        # doença, estudo, reparação do dano, medida de segurança) tira a hipótese da conta automática
        o = rs._sem_acento(h.get("outros_requisitos") or "").lower()
        if re.search(r"(?<!nao )(?<!nao foi )substituida por|\bou sursis|(?<!beneficiadas )(?<!beneficiados )com sursis|prisao provisoria|saidas? tempor|anos de idade|filh|doen|gestan|"
                     r"defici|estud|repara|medida de seguranca|trabalho externo", o):
            return False
        return any(h.get(k) is not None for k in ("pena_max_anos", "pena_min_anos", "fracao_nao_reincidente", "fracao_reincidente",
                                                   "anos_nao_reincidente", "anos_reincidente"))
    nasc = rs.to_date(r.get("data_nascimento") or "")

    def _extra(h):
        """Hipótese não objetiva cujo requisito a mais o RSPE permite decidir: idade (data de nascimento), regime inicial aberto
        (regime da sentença) e saídas temporárias (o RSPE não registra: com o resto atendido, fica a verificar). Devolve
        (h ajustada, requisito: True/False/None, motivo, subjetivo) ou None se a hipótese não for desse tipo."""
        o = rs._sem_acento(h.get("outros_requisitos") or "").lower()
        if re.search(r"filh|neto|doen|gestan|defici|repara|medida de seguranca|multa|laudo|plegia|cegueira|\btea\b|aborto|estud|pessoa do art|prejuizo", o):
            return None
        m_id = re.search(r"(\d+) anos de idade completos", o)
        m_21 = re.search(r"menor de 21 anos ao tempo do crime", o)
        m_ab = re.search(r"regime inicial aberto", o)
        m_sa = re.search(r"saidas? tempor", o)
        if not (m_id or m_21 or m_ab or m_sa):
            return None
        subj = bool(vga and re.search(r"condicoes pessoais|circunstancias favoraveis|avaliacao judicial", o))
        if m_id:
            n = int(m_id.group(1))
            if not nasc:
                return h, None, "data de nascimento não informada (a hipótese exige %d anos completos em %s)" % (n, rs.fmt(ref)), subj
            idade = rs._idade_em(r.get("data_nascimento"), ref)
            if idade < n:
                return h, False, "tinha %d anos em %s (a hipótese exige %d)" % (idade, rs.fmt(ref), n), subj
            return h, True, "%d anos completos em %s" % (idade, rs.fmt(ref)), subj
        if m_21:
            if not nasc:
                return h, None, "data de nascimento não informada (a hipótese exige menos de 21 anos ao tempo do crime)", subj
            ids = [rs._idade_em(r.get("data_nascimento"), rs.to_date(c.get("data_infracao") or "")) if rs.to_date(c.get("data_infracao") or "") else None
                   for c in crimes]
            if any(i is not None and i >= 21 for i in ids):
                return h, False, "tinha %d anos ao tempo do crime (a hipótese exige menos de 21)" % max(i for i in ids if i is not None), subj
            if any(i is None for i in ids):
                return h, None, "data do fato não informada (a hipótese exige menos de 21 anos ao tempo do crime)", subj
            return h, True, "menor de 21 anos ao tempo do crime", subj
        if m_ab:
            regs = [rs._sem_acento(c.get("regime_sentenca") or "").lower() for c in crimes]
            h = dict(h, regime=None)  # o requisito é o regime inicial, não o da data
            if any(x and "aberto" not in x.replace("semiaberto", "") for x in regs):
                return h, False, "regime inicial fixado na sentença não é o aberto", subj
            if any(re.search(r"REGRESS", (i.get("tipo") or "").upper()) and (i.get("situacao") or "").upper() == "CONCEDIDO"
                   and (rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "") or date.max) <= ref for i in r.get("_incidentes") or []):
                return h, False, "houve regressão de regime até %s" % rs.fmt(ref), subj
            if not all(regs):
                return h, None, "regime inicial da sentença não informado no RSPE (a hipótese exige o aberto)", subj
            return h, True, "regime inicial aberto e sem regressão", subj
        return h, None, "faltam no RSPE as saídas temporárias (ou o trabalho externo) que a hipótese exige - conferir no prontuário", False

    hips = []  # todas as hipóteses calculadas, para a linha do tempo
    for h in f.get("indulto") or []:
        ex = None
        if not h.get("objetivo"):
            ex = _extra(h)
            if ex is None:
                continue
            h = ex[0]
        elif not _decisiva(h):
            continue
        ok, exig, mot = hip_ok(h)
        if ex is not None:
            o_ = rs._sem_acento(h.get("outros_requisitos") or "").lower()
            m_dt = re.search(r"cumprida (?:ate|em) (\d{2}/\d{2}/\d{4})", o_)
            d_fr = rs.to_date(m_dt.group(1)) if m_dt else None
            if d_fr and exig is not None and (ok is not False or mot.startswith("faltavam")):
                c2 = _cumprido(r, ctx, d_fr)[0]
                ok, mot = (True, "") if c2 >= exig else (False, "faltavam %s em %s (data própria da hipótese)" % (_dias_txt(exig - c2), rs.fmt(d_fr)))
            _h, req, mreq, subj = ex
            if req is False:  # o requisito especial (idade, regime inicial) falha: é o motivo, mesmo que o tempo também falte
                ok, mot = False, mreq
            elif ok is not False and (req is None or subj or ok is None):
                partes = [x for x in (mot if ok is None else "", mreq if req is not True else "",
                                      "como o crime tem violência ou grave ameaça, depende ainda de avaliação judicial das condições pessoais" if subj else "") if x]
                mot = "requisitos de pena, tempo e regime atendidos; " + "; ".join(partes)
                ind_ver = ind_ver or (h, exig, mot)
                ok = False
            hips.append({"tipo": "indulto", "dispositivo": h.get("dispositivo") or "", "ok": bool(ok), "exigido": exig, "mot": mot or mreq,
                         "texto": h.get("texto") or "", "fracao": (h.get("fracao_reincidente") if reinc else h.get("fracao_nao_reincidente")) or ""})
            if ok and ind is None:
                ind = (h, exig)
            continue  # hipótese especial: não entra como "a que chegou mais perto"
        if ok is None:
            ind_ver = ind_ver or (h, exig, mot)
            ok = False
        hips.append({"tipo": "indulto", "dispositivo": h.get("dispositivo") or "", "ok": ok, "exigido": exig, "mot": mot, "texto": h.get("texto") or "",
                     "fracao": (h.get("fracao_reincidente") if reinc else h.get("fracao_nao_reincidente")) or
                               ("%s anos" % (h.get("anos_reincidente") if reinc else h.get("anos_nao_reincidente")) if (h.get("anos_reincidente") if reinc else h.get("anos_nao_reincidente")) else "")})
        if ok:
            if ind is None:
                ind = (h, exig)
            continue
        if exig is not None and (ind_n is None or ind_n[1] is None or ind_n[1] > exig):
            ind_n = (h, exig, mot)
        elif ind_n is None:
            ind_n = (h, exig, mot)
    com, com_n = None, None
    for h in f.get("comutacao") or []:
        hh = {"pena_max_anos": h.get("pena_max_anos"), "violencia_grave_ameaca": h.get("violencia_grave_ameaca"),
              "fracao_nao_reincidente": h.get("cumprimento_min_nao_reincidente"), "fracao_reincidente": h.get("cumprimento_min_reincidente"),
              "outros_requisitos": h.get("outros_requisitos") or "", "texto": h.get("texto") or ""}
        if not _decisiva(dict(hh, outros_requisitos=h.get("outros_requisitos") or "")):
            continue
        ok, exig, mot = hip_ok(dict(hh, texto=(h.get("texto") or "")), comut=True)
        ok = bool(ok)
        hips.append({"tipo": "comutacao", "dispositivo": h.get("dispositivo") or "", "ok": ok, "exigido": exig, "mot": mot, "texto": h.get("texto") or "",
                     "fracao": (hh["fracao_reincidente"] if reinc else hh["fracao_nao_reincidente"]) or "",
                     "reducao": (h.get("reducao_reincidente") if reinc else h.get("reducao_nao_reincidente")) or ""})
        if ok:
            if com is None:
                com = (h, exig)
            continue
        if com_n is None:
            com_n = (h, exig, mot)
    res = dict(base, detalhe=detalhe, regime=regime, nota=nota_conc, hips=hips, falta_ind=falta_ind, falta_firme=falta_firme)
    imp_ind = bool(imp) and "comuta" not in afeta.replace("indulto e comuta", "")
    imp_com = bool(imp) and ("indulto e comuta" in afeta or "só comuta" in afeta or afeta.startswith("so comuta"))
    f_ind = bool(falta_firme) and "indulto" in f_afeta
    f_com = bool(falta_firme) and ("comuta" in f_afeta)
    mot_falta = "falta grave %s: %s" % (("nos %s meses anteriores" % f_meses) if f_meses else "punida até a data", falta_firme[0]) if falta_firme else ""
    if f_ind and (f_com or not (com and not imp_com)):
        return dict(res, s="nao", mot=mot_falta)
    if ind and not imp_ind and not f_ind:
        h, exig = ind
        return dict(res, s="cabe", beneficio="Indulto", dispositivo=h.get("dispositivo") or "", exigido=exig,
                    fracao=(h.get("fracao_reincidente") if reinc else h.get("fracao_nao_reincidente")) or "",
                    mot=("cumpriu %s em %s" % (rs.dias_para_pena(cump), rs.fmt(ref))) + (" (exigido %s)" % rs.dias_para_pena(exig) if exig else ""),
                    ressalva=("falta a apurar na janela: %s" % falta_ind[0]) if falta_ind else "")
    if ind_ver and not ind and not imp_ind and not f_ind and not (com and not imp_com and not f_com):
        return dict(res, s="ver", mot=ind_ver[2], dispositivo=ind_ver[0].get("dispositivo") or "", exigido=ind_ver[1])
    if com and not imp_com and not f_com:
        h, exig = com
        red = h.get("reducao_reincidente") if reinc else h.get("reducao_nao_reincidente")
        return dict(res, s="cabe", beneficio="Comutação", dispositivo=h.get("dispositivo") or "", exigido=exig,
                    fracao=red or "", reducao=red or "",
                    mot="cumpriu %s em %s%s; comutação de %s do remanescente" % (rs.dias_para_pena(cump), rs.fmt(ref),
                                                                            (" (exigido %s)" % rs.dias_para_pena(exig)) if exig else "", red or "?"),
                    ressalva="; ".join(x for x in (("falta a apurar na janela: %s" % falta_ind[0]) if falta_ind else "",
                                                   ("indulto a verificar (%s): %s" % (ind_ver[0].get("dispositivo") or "", ind_ver[2]))
                                                   if (ind_ver and not ind and not imp_ind and not f_ind) else "") if x))
    if imp:
        return dict(res, s="imp", mot="; ".join(imp))
    if ind_n and ind_n[2]:
        return dict(res, s="nao", mot=ind_n[2], exigido=ind_n[1], dispositivo=ind_n[0].get("dispositivo") or "")
    if com_n and com_n[2]:
        return dict(res, s="nao", mot=com_n[2], exigido=com_n[1], dispositivo=com_n[0].get("dispositivo") or "")
    if not any(h.get("objetivo") and _decisiva(h) for h in (f.get("indulto") or [])) and not (f.get("comutacao") or []):
        return dict(res, s="nao", mot="decreto restrito (doença, deficiência, agentes de segurança ou outros grupos): nenhuma hipótese pelos dados do RSPE")
    return dict(res, s="nao", mot="nenhuma hipótese objetiva do decreto alcança o caso")


def _tese_hediondez(f, r, x):
    """Decreto que veda "hediondos" sem dizer "praticado após" a lei: o STJ afere a hediondez na data do decreto. O motor afere na
    data do fato (tese da irretroatividade - STF, 2ª T.); se o benefício só cabe por ela, o resultado é A VERIFICAR (tese)."""
    if x.get("s") != "cabe" or "praticado após" in ((f.get("impeditivos") or {}).get("texto") or "").lower():
        return x
    ref = rs.to_date(x.get("ref") or f.get("data_referencia") or "")
    if not ref:
        return x
    sup = [c for c in r.get("_crimes") or [] if _em_execucao(c, ref)
           and rs.to_date(c.get("data_infracao") or "") and rs.to_date(c.get("data_infracao")) <= ref
           and rs.e_hediondo(c, ref) and not rs.e_hediondo(c, None)]
    # lesão gravíssima/seguida de morte (art. 129, §§ 2º e 3º): hedionda só contra agente (Lei 13.142/2015) - o RSPE não diz a vítima
    les = [c for c in r.get("_crimes") or [] if ref >= date(2015, 7, 7) and _em_execucao(c, ref)
           and rs.num_art(c.get("artigo")) == "129" and rs.num_lei(c.get("lei")) in ("2848", "") and rs.hediondo_condicional(c) is None
           and (rs.to_date(c.get("data_infracao") or "") or date.min) <= ref]
    if les and not sup:
        return dict(x, s="ver", mot="%s: %s - %s" % (rs.crimes_curto(les), rs.impeditivo_verificar(les[0]), x.get("mot") or ""))
    if not sup:
        return x
    return dict(x, s="ver", mot=("hediondez posterior ao fato (%s): pelo STJ, que a afere na data do decreto, é crime impeditivo; o benefício "
                                 "(%s) só cabe pela tese da irretroatividade (STF, 2ª Turma) - %s" % (rs.crimes_curto(sup), x.get("beneficio") or "", x.get("mot") or "")))


def _detalhado(ano, r):
    num, ki, kc = DETALHADOS[ano]
    ref = _REF_DET.get(ano)
    out = {"id": ano, "ano": int(ano), "numero": num, "ref": rs.fmt(ref) if ref else "25/12/%s" % ano, "tipo": "natalino", "detalhado": True}
    si = MAPA_STATUS.get(r.get(ki + "_status") or "", "")
    sc = MAPA_STATUS.get(r.get((kc or "") + "_status") or "", "") if kc else ""
    ti, tc = r.get(ki) or "", (r.get(kc) or "") if kc else ""
    if kc and not sc and tc:
        # a aba não grava o status da comutação: lê o próprio texto do resultado
        u = tc.upper()
        sc = ("imp" if u.startswith("VEDAD") else "cabe" if u.startswith("POSSÍVEL") else "ver" if u.startswith("A VERIFICAR")
              else "nao" if re.match(r"N[ÃA]O|SEM PENA", u) else "")
    if re.match(r"não se aplica: não iniciou o cumprimento", ti):
        ti += " (a prisão anterior foi provisória: conta como detração, não como início do cumprimento da pena)"
    if si == "cabe" or (not si and ti.upper().startswith("CABE")):
        return dict(out, s="cabe", beneficio="Indulto", mot=ti)
    if sc == "cabe":
        return dict(out, s="cabe", beneficio="Comutação", mot=tc, ressalva=("indulto a verificar: " + ti) if si == "ver" else "")
    if "ver" in (si, sc):
        return dict(out, s="ver", mot=ti if si == "ver" else tc)
    if si == "imp":
        return dict(out, s="imp", mot=ti)
    if si == "nao" or sc == "nao":
        return dict(out, s="nao", mot=ti or tc)
    return dict(out, s="nao" if (ti or tc) else "fora", mot=ti or tc or "sem análise")


def _comutacao_sem_indulto(ano, x, r, f, ctx, ini, hoje):
    """Resultado da comutação do decreto (cabe ou a verificar), para quando o indulto foi indeferido no RSPE; None se não cabe."""
    if x.get("detalhado"):
        kc = DETALHADOS[ano][2]
        tc = (r.get(kc) or "") if kc else ""
        sc = MAPA_STATUS.get(r.get(kc + "_status") or "", "") if kc else ""
        if not sc and tc:
            u = tc.upper()
            sc = "cabe" if u.startswith("POSSÍVEL") else "ver" if u.startswith("A VERIFICAR") else ""
        if sc in ("cabe", "ver") and not tc.upper().startswith("PREJUDICADA"):
            return dict(x, s=sc, beneficio="Comutação", mot=tc, ressalva="")
        return None
    if not f or not (f.get("comutacao") or []):
        return None
    try:
        y = _tese_hediondez(f, r, avaliar_ficha(dict(f, indulto=[]), r, ctx, ini, hoje))  # só as hipóteses de comutação
    except Exception:
        return None
    if y.get("s") in ("cabe", "ver") and (y.get("beneficio") == "Comutação" or y.get("s") == "ver"):
        return dict(y, beneficio="Comutação")
    return None


def avaliar(r, hoje, completo=False):
    """Lista de resultados (do decreto mais antigo ao mais novo) para a aba Indulto. completo=True mantém as hipóteses
    calculadas e as faltas da janela (linha do tempo); sem ele, a lista fica leve."""
    _HED_CACHE.clear()
    ini = inicio_cumprimento(r)
    ctx = _ctx(r)
    dec = decididos(r)
    out = []
    fx = {}  # fichas avaliadas, para refazer a comutação quando o indulto foi indeferido
    for f in fichas():
        if f["id"] in DETALHADOS:
            continue
        fx[f["id"]] = f
        try:
            x = avaliar_ficha(f, r, ctx, ini, hoje)
            x = _tese_hediondez(f, r, x)
        except Exception as e:  # uma ficha com dado ruim não derruba o assistido
            x = {"id": f["id"], "ano": f.get("ano"), "numero": f.get("numero") or "", "ref": f.get("data_referencia"), "s": "ver",
                 "mot": "falha ao avaliar o decreto: %s" % e}
        out.append(x)
    for ano in DETALHADOS:
        ref = _REF_DET.get(ano)
        if ref and ref <= hoje:
            fora = {"id": ano, "ano": int(ano), "numero": DETALHADOS[ano][0], "ref": rs.fmt(ref), "s": "fora", "detalhado": True}
            pub = rs.DECRETOS_PUB.get(ano) or ref
            x = _detalhado(ano, r)
            if (ano, "indulto") in dec or (ano, "comutacao") in dec:
                pass  # decisão registrada no RSPE: prevalece (aplicada abaixo)
            elif _fora_do_decreto(r, ref, pub):
                # sem condenação alcançada (fato até a data, sentença até a publicação, pena em execução na data): não alcançado,
                # como nos demais decretos
                x = dict(fora, mot="sem condenação até o decreto" + (
                    " (sentença posterior à publicação não é alcançada: STJ, AgRg no HC 441.551 e AgRg no HC 919.210)"
                    if any((rs.to_date(c.get("data_sentenca") or "") or date.min) > pub for c in (r.get("_crimes") or [])) else ""))
            elif not (ini and ini <= ref) and x.get("s") not in ("cabe", "ver"):
                # execução posterior: só vale o resultado favorável da análise detalhada que não exige cumprimento na data
                # (2022, art. 5º, com o art. 9º, III; 2024/2025, art. 9º, XV)
                x = dict(fora, mot="execução posterior ao decreto")
            out.append(x)
    for x in out:
        ano = str(x.get("id") or "")
        if x.get("s") == "futuro" or (x.get("s") == "fora" and not dec.get((ano, "indulto")) and not dec.get((ano, "comutacao"))):
            continue
        di, dc = dec.get((ano, "indulto")), dec.get((ano, "comutacao"))
        d = di or dc
        if d and d[0] == "indef" and ano == "2017" and x.get("s") == "cabe":
            # Decreto 9.246/2017: indeferimentos apoiados na cautelar da ADI 5874 (julgada improcedente em 09/05/2019) podem ser renovados
            x["ressalva"] = "indeferido no RSPE em %s; a cautelar da ADI 5874 caiu (ação improcedente, 09/05/2019): o pedido pode ser renovado" % (d[1] or "?")
            continue
        if di and di[0] == "indef" and not dc:
            # indulto indeferido e comutação não decidida: a comutação cabível (ou a verificar) continua a valer
            y = _comutacao_sem_indulto(ano, x, r, fx.get(ano), ctx, ini, hoje)
            if y:
                x.clear()
                x.update(y, ressalva="; ".join(t for t in ("indulto indeferido no RSPE%s; a comutação não foi decidida" % ((" em " + di[1]) if di[1] else ""),
                                                           y.get("ressalva") or "") if t))
                continue
        if d:
            ben = "Indulto" if (ano, "indulto") in dec else "Comutação"
            x.update(s=d[0], beneficio=ben, mot="%s %s%s (incidente do RSPE)" % (ben, "concedido" if (d[0] == "conc" and ben == "Indulto") else
                                                                               "concedida" if d[0] == "conc" else
                                                                               "indeferido" if ben == "Indulto" else "indeferida",
                                                                               (" em " + d[1]) if d[1] else ""))
    out.sort(key=lambda x: (rs.to_date(x.get("ref") or "") or date.min))
    if not completo:
        for x in out:
            for k in ("hips", "falta_ind", "falta_firme"):
                x.pop(k, None)
    return {"inicio": rs.fmt(ini) if ini else "", "decretos": out}
