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


def _anos_pena(n):
    """Teto/piso de pena "não superior a N anos" em dias, na convenção do SEEU em que a pena está (ano de 365 dias, mês de 30),
    como em rspe_scraper.impeditivo_decreto e na análise de 2024/2025 - e não em anos de calendário (8a0m2d passaria por 8 anos)."""
    return int(round(float(n) * rs.DIAS_ANO))


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
        if not rs.e_incidente_regime(i) or (i.get("situacao") or "").upper() != "CONCEDIDO":
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
    if any(rs.e_incidente_regime(i) and (rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "") or date.max) <= ref
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


def _data_extincao(r, c):
    """Data da extinção da pena do crime: a do RSPE ou, sem ela, a do incidente de INDULTO ou EXTINÇÃO concedido que cita o
    processo (o SEEU marca o processo "(Indultada)"/"(Extinta)" sem data). None se nada no RSPE a informa."""
    d = rs.to_date(c.get("data_extincao") or "")
    if d or r is None:
        return d
    ds = []
    for i in r.get("_incidentes") or []:
        t = (i.get("tipo") or "").strip().upper()
        if not re.match(r"INDULTO|EXTIN", t) or (i.get("situacao") or "CONCEDIDO") != "CONCEDIDO":
            continue
        if any(rs.mesmo_processo(c.get("processo_criminal"), p) for p in rs.lista_processos(i.get("processos") or "")):
            ds.append(rs.to_date((i.get("data_decisao") or i.get("data_referencia") or "") if t.startswith("INDULTO")
                                 else (i.get("data_referencia") or i.get("data_decisao") or "")))
    ds = [x for x in ds if x]
    return min(ds) if ds else None


def _em_execucao(c, ref, r=None):
    """Pena em execução na data do decreto: crime não extinto, ou extinto DEPOIS dela (a extinção posterior não tira a pena
    do alcance do decreto). Extinto sem data (nem no RSPE nem no incidente que cita o processo): em execução nos decretos
    anteriores ao RSPE - a verificar (_ext_sem_data), sem tirar a pena da soma."""
    if not (c.get("extinto") or "").upper().startswith("S"):
        return True
    d = _data_extincao(r, c)
    if d:
        return d > ref
    ger = rs.to_date((r or {}).get("data_geracao_rspe") or "")
    return bool(r is not None and ger and ref < ger)


def _ext_sem_data(r, crimes):
    """Crimes da soma extintos sem data no RSPE (considerados em execução na data do decreto)."""
    return [c for c in crimes if (c.get("extinto") or "").upper().startswith("S") and not _data_extincao(r, c)]


def _transito_min(c):
    ts = [d for d in (rs.to_date(c.get("transito_mp") or ""), rs.to_date(c.get("transito_processo") or "")) if d]
    return min(ts) if ts else None


def _sentenca_incoerente(c):
    """Data da sentença posterior ao trânsito em julgado (dado incoerente do SEEU: no júri, o trânsito pode ser o da pronúncia)."""
    s, t = rs.to_date(c.get("data_sentenca") or ""), _transito_min(c)
    return bool(s and t and s > t)


def _alcancados(r, ref, pub):
    """Crimes que o decreto alcança: fato até a data de referência, sentença até a publicação e pena em execução na data.
    Sentença posterior ao trânsito (dado incoerente): vale o trânsito, e o resultado fica a verificar (_sent_incoerente)."""
    return [c for c in (r.get("_crimes") or []) if _em_execucao(c, ref, r)
            and (rs.to_date(c.get("data_infracao") or "") or date.min) <= ref
            and ((rs.to_date(c.get("data_sentenca") or "") or date.min) <= pub or (_sentenca_incoerente(c) and _transito_min(c) <= pub))]


def _fora_do_decreto(r, ref, pub):
    """Nenhuma condenação alcançada pelo decreto: todo crime tem fato posterior à data, sentença posterior à publicação ou
    extinção registrada até a data. Extinto sem data no RSPE não decide (pode ter sido extinto depois)."""
    def fora(c):
        ext = (c.get("extinto") or "").upper().startswith("S")
        d_ext = _data_extincao(r, c)
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


ANCORA_ZERADA = rs.ANCORA_ZERADA
SEM_CALCULO = rs.SEM_CALCULO


def _cumprido_info(r, ctx, ref):
    """Pena cumprida na data pela regra única de todos os decretos (rs.cumprido_decreto_info: âncora do SEEU; pelos eventos
    quando o SEEU não traz o cálculo ou a âncora zera ou fica abaixo da metade deles; teto na pena da execução). Devolve o
    dicionário {dias, fonte, aviso, origem}. Com ctx["_modo"] (avaliar_ficha), a âncora ou os eventos - decisão pelo requisito."""
    x = rs.cumprido_decreto_info(r, ctx["periodos"], ctx["rem"], ref, ctx["lc"], r.get("_crimes") or [], ctx.get("_modo"))
    if x.get("alt"):
        ctx["_alt"] = True
    return x


def _cumprido(r, ctx, ref):
    """(dias, fonte) de _cumprido_info."""
    x = _cumprido_info(r, ctx, ref)
    return x["dias"], x["fonte"]


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


def _rol_xiv_2023(c):
    """Crime do rol do art. 1º, XIV, do Decreto 11.846/2023: os das Leis 11.340/2006, 13.718/2018 (CP, arts. 215-A e 218-C),
    14.192/2021 (Código Eleitoral, art. 326-B), 14.132/2021 (CP, art. 147-A) e 13.641/2018 (Lei 11.340, art. 24-A)."""
    lei, art = rs.num_lei(c.get("lei")), rs.num_art(c.get("artigo"))
    if lei in ("11340", "13718", "14192", "14132", "13641") or (lei == "4737" and art == "326-B"):
        return True
    cp = lei in ("2848", "") or ("PENAL" in (c.get("lei") or "").upper() and "MILITAR" not in (c.get("lei") or "").upper())
    return bool(cp and art in ("147-A", "215-A", "218-C"))


_HED_CACHE = {}  # hediondez na data do fato, por crime (a mesma em todos os decretos); limpo a cada avaliar()


def _impeditivos(f, crimes, ref, pena_total=None, ver=None, contexto=None, incerto=None):
    """Crimes da soma que o decreto veda (hediondos e equiparados na data do fato, tortura, terrorismo, tráfico e a lista
    própria do decreto). ver (lista): recebe os crimes que só são impeditivos conforme dado que o RSPE não traz (violência
    contra a mulher provável ou pelo contexto da execução); contexto: crimes da execução para esse contexto."""
    I = f.get("impeditivos") or {}
    out = []
    lim = I.get("nao_aplica_pena_ate_anos")
    if lim and pena_total is not None and pena_total <= _anos_pena(lim):
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
        if incerto is not None and rs.trafico_incerto(c):
            # art. 33 sem caput/§ 1º nem § 4º legível no RSPE: a natureza não se presume (a mesma regra de 2022, 2024 e 2025)
            incerto.append("%s: tráfico sem indicação do caput/§ 1º nem do § 4º no RSPE - se privilegiado (§ 4º), não é impeditivo; "
                           "conferir na sentença" % rot)
            continue
        hom_selo = incerto is not None and rs.homicidio_simples_selo(c) and not f.get("_hom_selo_imp")
        if hom_selo:
            # a mesma regra da progressão e do livramento: o selo pode ser o do grupo de extermínio (Lei 8.072, art. 1º, I) - não é
            # impeditivo por hediondez, a verificar (as demais vedações do decreto continuam a valer)
            incerto.append("%s: homicídio simples com o selo de hediondo do SEEU - impeditivo só se em atividade típica de grupo de "
                           "extermínio (Lei 8.072/90, art. 1º, I); conferir na sentença" % rot)
        priv_vedado = priv and I.get("trafico_privilegiado_ressalvado") is False
        # hediondos, tortura, tráfico e terrorismo: vedados pela própria lei (CF, art. 5º, XLIII; Lei 8.072, art. 2º, I), ainda
        # que o decreto não os liste (ex.: Dia das Mães 2017 e 2018)
        if True:
            fato = rs.to_date(c.get("data_infracao") or "")
            # hediondez aferida na data do FATO: a superveniente não alcança o fato anterior (os decretos falam em "crime
            # hediondo praticado após" a Lei 8.072/1990 e as que ampliaram o rol). Tráfico: equiparado desde 25/07/1990
            if id(c) not in _HED_CACHE:
                _HED_CACHE[id(c)] = (c, rs.e_hediondo(c, None))
            if priv_vedado or (not priv and ((_HED_CACHE[id(c)][1] and not hom_selo) or (trafico and (fato or ref) >= date(1990, 7, 25)))):
                out.append("%s: %s%s" % (rot, "tráfico privilegiado vedado pelo decreto" if priv_vedado else "hediondo ou equiparado na data do fato",
                                         (" (%s)" % rs.fmt(fato)) if fato and not priv_vedado else ""))
                continue
        for o in I.get("outros") or []:
            lt = str(o.get("lei") or "")
            if re.search(r"\bCPM\b|MILITAR", lt, re.I):
                continue  # Código Penal Militar: crimes que o SEEU estadual não executa
            if o.get("so_pessoa_juridica"):
                continue  # vedação só do crime atribuído a pessoa jurídica (ex.: 2023, art. 1º, XII): o SEEU executa pessoa física
            if re.search(r"viol[eê]ncia contra a mulher", o.get("descricao") or "", re.I):
                # vedação pelo contexto (Lei 11.340 e crimes do CP contra a mulher), não pelo número da lei do crime
                v = _vd(c)
                if v and v[0] == "sim" and str(f.get("id")) == "2023" and not _rol_xiv_2023(c):
                    # 2023, art. 1º, XIV: o rol cita as Leis 11.340, 13.718, 14.192, 14.132 e 13.641 - o crime comum do CP em
                    # contexto doméstico fora delas fica a verificar (a mesma regra do XVII de 2024/2025: norma restritiva)
                    if ver is not None:
                        ver.append("%s: crime fora das leis citadas no art. 1º, XIV, em contexto de violência contra a mulher (%s) - norma "
                                   "restritiva não se amplia por analogia; há leitura que veda todo crime nesse contexto - conferir" % (rot, v[1]))
                    continue
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
            if o.get("exceto_pena_ate_anos") and (rs.pena_para_dias(c.get("pena_imposta") or c.get("pena_total_processo")) or 0) <= _anos_pena(o["exceto_pena_ate_anos"]):
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


FUGA_TRATADA = "tratada como falta grave (LEP, art. 50, II)"  # texto de rs.indicios_falta (fuga_firme) para a fuga sem homologação
FUGA_APURAR = ("em tese falta grave (LEP, art. 50, II); o decreto exige a falta apurada ou homologada - só impede se reconhecida "
               "em juízo (STJ, Tema 1195)")


def fuga_impede(f):
    """A fuga sem homologação na janela impede o benefício só nos decretos sem exigência de falta apurada/homologada. Nos que exigem
    a falta apurada ou a sanção reconhecida em juízo - inclusive o Decreto 11.846/2023, cujo art. 6º tem a mesma redação do art. 6º
    de 2024 e 2025 -, não: fica a verificar até o reconhecimento (decisão do usuário de 20/10/2026; STJ, Tema 1195: a homologação
    posterior impede). A ficha pode fixar a regra (falta_grave.fuga_sem_homologacao_impede)."""
    F = f.get("falta_grave") or {}
    if not F.get("exige_homologacao"):
        return True
    return bool(F.get("fuga_sem_homologacao_impede", False))


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


def _concurso_exclui(f):
    """Decreto que soma as penas excluindo dos benefícios as infrações impeditivas, sem condicionar ao cumprimento da pena delas
    (2000 e 2001, art. 9º): o crime impeditivo sai da soma e não veda a execução toda."""
    t = rs._sem_acento(" ".join(str(x) for x in (f.get("observacoes") or []))).lower()
    return bool(re.search(r"excluindo-se dos beneficios as infrac", t))


def remicoes_ref_decisao(r):
    """Remições concedidas no RSPE com a data de referência igual à da decisão (ou sem ela): a data não diz quando foi o trabalho
    ou o estudo, e o RSPE não diz de qual atestado veio cada uma. [(data da decisão, dias)]."""
    out = []
    for i in r.get("_incidentes") or []:
        if not rs.e_remicao_concedida(i):
            continue
        dd, dr = rs.to_date(i.get("data_decisao") or ""), rs.to_date(i.get("data_referencia") or "")
        n = rs.dias_de(i.get("complemento") or "")
        if not dd or not n or n <= 0 or (dr and dr != dd):
            continue
        out.append((dd, n))
    return out


def _ctx(r):
    eventos, incidentes = r.get("_eventos") or [], r.get("_incidentes") or []
    # remições e perdas de remidos (a mesma conta das colunas 2022-2025); a remição decidida com a referência igual à decisão fica pela
    # decisão - o RSPE não diz de qual atestado ela veio - e, se cobrir o que faltava, o decreto fica a verificar (_rem_posterior)
    rem = rs.remicoes_liquidas(incidentes)
    return {"periodos": rs.periodos_custodia(eventos), "lc": rs.periodos_livramento(eventos, incidentes), "rem": rem}


def _rem_posterior(x, r):
    """Remição decidida depois da data do decreto, com a referência igual à decisão e sem o período do atestado identificado, que
    cobre o que faltava: o trabalho pode ser anterior à data (LEP, art. 128) - o "não atinge" passa a A VERIFICAR. Altera x."""
    ref = rs.to_date(x.get("ref") or "")
    if x.get("s") != "nao" or not ref:
        return
    ger = rs.to_date(r.get("data_geracao_rspe") or "") or date.max
    its = [(d, n) for d, n in remicoes_ref_decisao(r) if ref < d <= ger]
    if not its:
        return
    fl = rs.faltas_remiveis(x.get("mot"))
    tot = sum(n for _d, n in its)
    if fl and tot >= min(fl):
        x.update(s="ver", mot="A VERIFICAR (remição homologada depois): %s; %s" % (x.get("mot") or "", nota_rem_posterior(its, ref)))


def nota_rem_posterior(its, ref):
    return ("%s de remição decidida depois de %s (%s), com a referência igual à data da decisão e sem o período do trabalho identificado "
            "na ficha - se a atividade for anterior a %s, os dias contam como pena cumprida na data (LEP, art. 128): conferir o período no "
            "atestado" % (rs.pl(round(sum(n for _d, n in its)), "dia", "dias"), rs.fmt(ref),
                          "; ".join("%s em %s" % (rs.pl(round(n), "dia", "dias"), rs.fmt(d)) for d, n in its[:4]), rs.fmt(ref)))


def custodia_outro_processo(r, ref, crimes):
    """Prisão provisória (flagrante, preventiva, temporária) que abre período de custódia contado até a data do decreto, registrada
    para processo que não é de nenhum crime alcançado (outro processo, ou o crime novo, de fato posterior à data): a custódia por
    outro processo, não somada, não é cumprimento desta pena - texto do "a verificar", ou ''."""
    achou = []
    for a, b, mot, procs in rs.periodos_custodia_detalhe(r.get("_eventos") or []):
        if not a or a > ref or not procs or not re.search(r"FLAGRANTE|PREVENTIV|TEMPOR|PROVIS", (mot or "").upper()):
            continue
        ps = rs.lista_processos(procs)
        if not ps or any(rs.mesmo_processo(c.get("processo_criminal"), p) for c in crimes for p in ps):
            continue
        novo = [c for c in r.get("_crimes") or [] if (rs.to_date(c.get("data_infracao") or "") or date.min) > ref
                and any(rs.mesmo_processo(c.get("processo_criminal"), p) for p in ps)]
        achou.append("prisão de %s (%s) registrada para %s (%s)%s" % (
            rs.fmt(a), (mot or "").strip().lower(), "o crime novo, de fato posterior à data" if novo else "outro processo", procs,
            "" if (b is None or b >= ref) else ", até %s" % rs.fmt(b)))
    if not achou:
        return ""
    return ("%s: a custódia por outro processo, não somada até a data, suspende esta execução e não é cumprimento desta pena - conferir o "
            "tempo cumprido sem ela" % "; ".join(achou[:3]))


def dias_custodia_outro_processo(r, ref, crimes):
    """Dias, até ref, dos períodos de custódia abertos por prisão provisória registrada para outro processo (os de
    custodia_outro_processo): descontados do cumprido, mostram se a dúvida muda o resultado."""
    tot = 0
    for a, b, mot, procs in rs.periodos_custodia_detalhe(r.get("_eventos") or []):
        if not a or a > ref or not procs or not re.search(r"FLAGRANTE|PREVENTIV|TEMPOR|PROVIS", (mot or "").upper()):
            continue
        ps = rs.lista_processos(procs)
        if not ps or any(rs.mesmo_processo(c.get("processo_criminal"), p) for c in crimes for p in ps):
            continue
        tot += ((min(b, ref) if b else ref) - a).days + 1
    return tot


def outro_processo_decretos(r):
    """Decretos 2024 e 2025 (análise detalhada): o indulto ou a comutação possível com custódia contada até a data que decorre de prisão
    registrada para outro processo ou pelo crime novo passa a A VERIFICAR (custodia_outro_processo). Altera r."""
    for ano in ("2024", "2025"):
        ref = _REF_DET[ano]
        pub = rs.DECRETOS_PUB.get(ano) or ref
        t = custodia_outro_processo(r, ref, _alcancados(r, ref, pub))
        if not t:
            continue
        for k in ("indulto_%s" % ano, "comutacao_%s" % ano):
            v = r.get(k) or ""
            if v.startswith("POSSÍVEL"):
                r[k] = "A VERIFICAR (custódia por outro processo): %s | %s" % (t, v)
                r[k + "_status"] = "verificar"


PENA_CUMPRIDA = "A VERIFICAR (pena cumprida)"


def _txt_pena_cumprida(pena, cump, ref, parcial):
    return ("%s: pedir a extinção%s pelo cumprimento (LEP, art. 66, II) - a pena considerada%s (%s) já estava cumprida em %s (cumpridos %s)%s" % (
        PENA_CUMPRIDA, " parcial" if parcial else "", " dos crimes não impeditivos" if parcial else "", rs.dias_para_pena(pena), rs.fmt(ref),
        rs.dias_para_pena(cump), ("; o tempo além da fração do crime impeditivo cobre a pena dos demais crimes - a execução prossegue quanto ao "
                                  "impeditivo" if parcial else "; conferir o tempo cumprido")))


def pena_cumprida_decretos(r):
    """Decretos 2022, 2024 e 2025 (análise detalhada): o indulto "possível" ou "a verificar" cuja pena considerada já estava cumprida
    na data (no concurso, a dos crimes não impeditivos com o tempo além dos 2/3 do impeditivo) passa a "pena cumprida - pedir a
    extinção", como a petição (LEP, art. 66, II). O caso sem dúvida já sai da análise como "não se aplica". Altera r."""
    for ano, ref in _REF_DET.items():
        k = "indulto_%s" % ano
        v, num = r.get(k) or "", r.get(k + "_num") or {}
        if not v.startswith(("POSSÍVEL", "A VERIFICAR")) or v.startswith(PENA_CUMPRIDA) or not num.get("pena") or num.get("cumprido") is None:
            continue
        if num["cumprido"] < num["pena"]:
            continue
        if "crimes não impeditivos" in v.split(" | ")[0] or (r.get(k + "_imp") and ano != "2022"):
            # concurso com impeditivo: o tempo além dos 2/3 do impeditivo só afere o requisito do art. 7º, p. ú. - não diz que a pena
            # dos demais crimes está extinta (pela ordem legal, CP, arts. 69 e 76, a reclusão se executa antes da detenção, e a pena
            # do impeditivo segue): o pedido seguro é o indulto do inciso atendido; a extinção parcial é tese
            r[k + "_detalhe"] = (r.get(k + "_detalhe") or "") + (
                "\nObs.: o tempo além dos 2/3 do impeditivo (%s) cobre a pena considerada dos demais crimes (%s), mas isso só afere o requisito do "
                "art. 7º, p. ú.; não extingue essa pena pelo cumprimento - o pedido é o indulto do inciso atendido (a extinção parcial pelo "
                "cumprimento é tese)." % (rs.dias_para_pena(num["cumprido"]), rs.dias_para_pena(num["pena"])))
            continue
        r[k] = "%s | %s" % (_txt_pena_cumprida(num["pena"], num["cumprido"], ref, False), v)
        r[k + "_status"] = "verificar"


def _pena_cumprida_aba(out, r):
    """Aba Indulto: o indulto cabível ou a verificar cuja pena considerada já estava cumprida na data passa a "pena cumprida - pedir a
    extinção" (no concurso, extinção parcial), alinhado à petição da linha do tempo. Altera os itens de out."""
    for x in out:
        if x.get("s") not in ("cabe", "ver") or x.get("beneficio") == "Comutação":
            continue
        ref = rs.to_date(x.get("ref") or "")
        if x.get("detalhado"):
            if (x.get("mot") or "").startswith(PENA_CUMPRIDA):
                x.update(s="ver", beneficio="Extinção parcial (pena cumprida)" if "pedir a extinção parcial" in x["mot"] else "Extinção (pena cumprida)")
            continue
        de = x.get("detalhe") or {}
        p, c = de.get("pena_conc", de.get("pena")), de.get("cumprido_conc", de.get("cumprido"))
        if not ref or not p or c is None or c < p:
            continue
        parcial = "pena_conc" in de
        if parcial:
            # concurso com impeditivo: o tempo além da fração do impeditivo só afere o requisito - não extingue a pena dos demais
            # crimes (ver pena_cumprida_decretos); segue o benefício cabível, com a observação
            x["ressalva"] = "; ".join(y for y in (x.get("ressalva") or "", "o tempo além da fração do impeditivo cobre a pena considerada dos demais "
                                                  "crimes, mas só afere o requisito; a extinção parcial pelo cumprimento é tese") if y)
            continue
        x.update(s="ver", beneficio="Extinção parcial (pena cumprida)" if parcial else "Extinção (pena cumprida)",
                 mot="%s; %s" % (_txt_pena_cumprida(p, c, ref, parcial), x.get("mot") or ""), ressalva=x.get("ressalva") or "")


def remicao_posterior_decretos(r):
    """Nos decretos 2022, 2024 e 2025 (análise detalhada, feita antes da ficha), passa a A VERIFICAR o "não atinge" que a remição
    decidida depois da data, com a referência igual à decisão, cobriria: o trabalho ou o estudo pode ser anterior à data (LEP, art. 128)
    e o RSPE não diz de qual atestado veio a remição. Altera r."""
    for ano, ref in _REF_DET.items():
        ger = rs.to_date(r.get("data_geracao_rspe") or "") or date.max
        its = [(d, n) for d, n in remicoes_ref_decisao(r) if ref < d <= ger]
        if not its:
            continue
        tot = sum(n for _d, n in its)
        for k in ("indulto_%s" % ano, "comutacao_%s" % ano):
            v, det = r.get(k) or "", r.get(k + "_detalhe") or ""
            if not v.startswith("não atinge") or v.startswith("não atinge: pena dos crimes impeditivos") or "posterior à publicação" in v:
                continue
            fl = []
            if k.startswith("comutacao"):
                for mm in re.finditer(r"✘ Requisito: \S+ da pena cumprida até [\d/]+ = (\d+a\d+m\d+d); cumprido (\d+a\d+m\d+d)", det):
                    fl.append((rs.pena_para_dias(mm.group(1)) or 0) - (rs.pena_para_dias(mm.group(2)) or 0))
            else:
                for ln in det.split("\n"):
                    mm = re.match(r"✘ ([IVXL]+): .*?exige (\d+)/(\d+) \(cumprido (\d+a\d+m\d+d) de (\d+a\d+m\d+d)\)", ln)
                    if mm and "não se aplica" not in ln:
                        fl.append((rs.pena_para_dias(mm.group(5)) or 0) * int(mm.group(2)) // int(mm.group(3)) - (rs.pena_para_dias(mm.group(4)) or 0))
            fl = [y for y in fl if y > 0]
            if not fl or tot < min(fl):
                continue
            nota = ("%s de remição decidida depois de %s (%s), sem o período do trabalho ou do estudo identificado, cobre os %s "
                    "que faltavam - a remição é pena cumprida (LEP, art. 128): conferir o período e pedir o benefício" % (
                        rs.pl(round(tot), "dia", "dias"), rs.fmt(ref), "; ".join("%s em %s" % (rs.pl(round(n), "dia", "dias"), rs.fmt(d)) for d, n in its[:4]),
                        rs.pl(min(fl), "dia", "dias")))
            r[k] = "A VERIFICAR (remição homologada depois): " + nota
            r[k + "_detalhe"] = det + "\n? Remição homologada depois: " + nota
            r[k + "_status"] = "verificar"


# ordem dos resultados (melhor por último): "imp" abaixo de "nao" - o "faltavam X para 2/3 do impeditivo" pela âncora (que não conta
# o tempo das penas já extintas) não prevalece sobre os eventos que mostram os 2/3 cumpridos e levam à análise dos demais crimes
_RANK_S = {"cabe": 3, "ver": 2, "nao": 1, "imp": 0}


def avaliar_ficha(f, r, ctx, ini, hoje):
    """Avalia o decreto com a decisão pelo requisito (rs.cumprido_decreto_info, modo): pela âncora do SEEU; se ela não dá o
    resultado favorável e os eventos mostram mais tempo, de novo pelos eventos - que valem (a verificar, com o aviso) quando
    dão resultado melhor. Mais pena cumprida no SEEU nunca piora o resultado."""
    if ctx.get("_modo") or "periodos" not in ctx:
        return _avaliar_ficha_um(f, r, ctx, ini, hoje)
    ca = dict(ctx, _modo="ancora")
    xa = _avaliar_ficha_um(f, r, ca, ini, hoje)
    if xa.get("s") == "cabe" and xa.get("beneficio") == "Comutação" and ca.get("_alt"):
        # a âncora dá a comutação, mas os eventos mostram mais tempo: o indulto (mais benéfico) pode caber por eles - testa
        xe = _avaliar_ficha_um(f, r, dict(ctx, _modo="eventos"), ini, hoje)
        if xe.get("s") in ("cabe", "ver") and xe.get("beneficio") == "Indulto":
            return dict(xe, s="ver", ressalva="; ".join(y for y in (xe.get("ressalva") or "", "pela âncora do SEEU cabe a comutação: %s" % (
                xa.get("mot") or "")) if y))
        return xa
    if xa.get("s") == "cabe" or not ca.get("_alt") or (xa.get("mot") or "").startswith("sem pena remanescente"):
        return xa  # (pena já cumprida pela âncora: com o tempo maior dos eventos, também não sobra o que comutar)
    xe = _avaliar_ficha_um(f, r, dict(ctx, _modo="eventos"), ini, hoje)
    if _RANK_S.get(xe.get("s"), 0) > _RANK_S.get(xa.get("s"), 0):
        return xe
    if xe.get("s") == xa.get("s") and xa.get("s") in ("nao", "imp"):
        # o mesmo resultado negativo: o texto mostra o "faltavam" menor (o dos eventos, quando é ele), com a fonte
        fa = rs.falta_menor(xa.get("mot"), xe.get("mot"))
        if fa:
            return dict(xe, mot="%s; %s" % (xe.get("mot") or "", rs.nota_falta_eventos(fa)))
    return xa


def _avaliar_ficha_um(f, r, ctx, ini, hoje):
    """Avalia o decreto; com o cumprimento interrompido na data (fuga, soltura), o resultado favorável vira A VERIFICAR: o decreto
    exige a fração cumprida ATÉ a data, não a custódia NA data, e a interrupção pode ter sido punida como falta grave."""
    x = _avaliar_ficha(f, r, ctx, ini, hoje)
    if any(rs.homicidio_simples_selo(c) for c in r.get("_crimes") or []):
        # homicídio simples com o selo de hediondo: se o resultado cabe mesmo com o selo (impeditivo), o selo não importa; senão,
        # vale a análise sem ele, a verificar (o selo pode ser o do grupo de extermínio - Lei 8.072, art. 1º, I)
        x0 = _avaliar_ficha(dict(f, _hom_selo_imp=True), r, ctx, ini, hoje)
        if x0.get("s") == "cabe" or x.get("s") == x0.get("s"):
            x = x0
    vd_ver = x.pop("_vd_ver", None) or []
    tr_ver = x.pop("_tr_ver", None) or []
    if x.pop("_interr", False):
        ref_t = x.get("ref") or ""
        if x.get("s") == "cabe":
            x.update(s="ver", mot="%s; o cumprimento estava interrompido em %s (não estava preso nem em livramento): o decreto exige a fração "
                                  "cumprida até a data, não a custódia na data - conferir se a interrupção foi fuga e, se foi, se ela foi punida como falta grave"
                                  % (x.get("mot") or "", ref_t))
        elif x.get("s") in ("nao", "ver"):
            x["mot"] = "cumprimento interrompido em %s (não estava preso nem em livramento); %s" % (ref_t, x.get("mot") or "")
    # dados do RSPE que deixam o resultado em dúvida: o favorável vira A VERIFICAR; nos de soma (extinção sem data, sentença
    # incoerente), o desfavorável leva a ressalva - a pena pode não estar na soma -, e o crime impeditivo de sentença incoerente
    # (a condenação pode ser posterior ao decreto) também vira A VERIFICAR
    inc_rot = x.pop("_sent_inc_rot", None) or []
    est = x.pop("_estouro", "")
    if est:
        # eventos que não servem (acima da pena da execução ou sem as interrupções do SEEU): vale a âncora, e o resultado que
        # depende do tempo cumprido (cabe, ou "faltavam" pela âncora) fica A VERIFICAR, sem dar hipótese como atendida
        if x.get("s") == "cabe" or (x.get("s") == "nao" and (x.get("mot") or "").startswith("faltavam")):
            x.update(s="ver", mot="%s; A VERIFICAR - %s" % (x.get("mot") or "", est))
        else:
            x["ressalva"] = "; ".join(y for y in (x.get("ressalva") or "", "conferir o tempo cumprido - " + est) if y)
    fa = x.pop("_falta_ver_afeta", "") or "indulto e comutação"
    if x.get("beneficio") and ("indulto" if x["beneficio"] == "Indulto" else "comuta") not in fa:
        x.pop("_falta_ver", None)  # a falta deste decreto não alcança o benefício cabível (ex.: só o indulto)
    _op_d = x.pop("_outro_proc_dias", None)
    if _op_d is not None and x.get("s") == "cabe" and x.get("exigido") is not None:
        # custódia por outro processo: sem ela o requisito ainda é atendido - a dúvida não muda o resultado (o documento resolve)
        _de = x.get("detalhe") or {}
        _c = _de.get("cumprido_conc", _de.get("cumprido"))
        if _c is not None and _c - _op_d >= (x.get("exigido") or 0):
            x.pop("_outro_proc", None)
    for k in ("_hed_lim", "_conc_exclui", "_teto_amb", "_mercancia", "_outro_proc"):
        # quesitos de 16/10/2026 (2002 com hediondo/tráfico, art. 9º de 2000/2001, teto no concurso, mercancia de 2008, custódia de outro
        # processo): o favorável fica A VERIFICAR, e o "a verificar" leva também este motivo
        t = x.pop(k, "")
        if t and x.get("s") in ("cabe", "ver") and t not in (x.get("mot") or ""):
            x.update(s="ver", mot="%s; A VERIFICAR - %s" % (x.get("mot") or "", t))
    for k, soma in (("_ext_sd", True), ("_sent_inc", True), ("_anc0", False), ("_art52", False), ("_falta_ver", False), ("_descump", False)):
        t = x.pop(k, "")
        if not t:
            continue
        # crime impeditivo de sentença incoerente: só muda algo se houver outro crime a beneficiar (com qualquer das datas, o
        # impeditivo sozinho dá "vedado" ou "sem condenação na data" - ambos negativos)
        if x.get("s") == "cabe" or (k == "_sent_inc" and x.get("s") == "imp" and any(("%s:" % y) in (x.get("mot") or "") for y in inc_rot)
                                    and len(x.get("alc") or []) > len(inc_rot)):
            x.update(s="ver", mot="%s; A VERIFICAR - %s" % (x.get("mot") or "", t))
            fr = (x.get("ressalva") or "").split("; indulto a verificar", 1)
            if fr[0].startswith("falta a apurar na janela: ") and fr[0][len("falta a apurar na janela: "):] in t:
                x["ressalva"] = ("indulto a verificar" + fr[1]) if len(fr) > 1 else ""  # a mesma falta já está no motivo
        elif soma and x.get("s") in ("nao", "imp"):
            x["ressalva"] = "; ".join(y for y in (x.get("ressalva") or "", "A VERIFICAR - " + t) if y)
    if x.get("s") == "cabe":
        tr = transito_pendente(f, r)
        if tr:
            x.update(s="ver", mot="%s; %s" % (x.get("mot") or "", tr) if x.get("mot") else tr)
    _rl = x.pop("_reinc_lei", "")
    if _rl and x.get("s") == "cabe":
        # o RSPE não marca reincidência, mas as datas dele a mostram: não se afirma o "cabe" de primário. Refeita a conta como
        # reincidente: se ainda cabe, vale ela (fração e redução de reincidente: o documento resolve); se não, A VERIFICAR
        xr = _avaliar_ficha(dict(f, _forca_reinc=True), r, ctx, ini, hoje)
        if xr.get("s") == "cabe":
            for k in ("beneficio", "dispositivo", "exigido", "fracao", "reducao", "mot", "reducao_calc", "detalhe"):
                if k in xr:
                    x[k] = xr[k]
                elif k in x and k in ("reducao_calc",):
                    x.pop(k)
            x["ressalva"] = "; ".join(y for y in (x.get("ressalva") or "", "conta feita como reincidente: " + _rl) if y)
        else:
            x.update(s="ver", mot="%s; A VERIFICAR - %s; como reincidente, o benefício não é atingido nesta data" % (x.get("mot") or "", _rl))
    elif _rl and x.get("s") == "ver":
        x["ressalva"] = "; ".join(y for y in (x.get("ressalva") or "", _rl + " - a conta como reincidente exige fração maior") if y)
    if x.get("s") == "cabe" and vd_ver:
        # violência contra a mulher que o RSPE não confirma (vítima, vara): se houve, o crime é impeditivo
        x.update(s="ver", mot="%s; A VERIFICAR - conferir se houve violência contra a mulher (vedação do %s): %s" % (
            x.get("mot") or "", (f.get("impeditivos") or {}).get("dispositivo") or "decreto", "; ".join(vd_ver)))
    if x.get("s") == "cabe" and tr_ver:
        x.update(s="ver", mot="%s; A VERIFICAR - %s" % (x.get("mot") or "", "; ".join(tr_ver)))
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


def _reinc_pelas_datas(crimes, todos):
    """(condenação anterior, crime) quando um crime da soma foi cometido depois do trânsito de outra condenação e antes de 5 anos da
    extinção dela (CP, arts. 63 e 64, I); senão None (rs.reinc_pelas_datas)."""
    return rs.reinc_pelas_datas(crimes, todos)


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
    crimes = crimes0 = _alcancados(r, ref, pub)
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
    sd = _ext_sem_data(r, crimes)
    if sd:
        base["_ext_sd"] = ("pena extinta sem data no RSPE (%s): considerada em execução em %s, anterior ao RSPE - conferir no incidente "
                           "de indulto ou extinção a data em que se extinguiu" % (rs.crimes_curto(sd), rs.fmt(ref)))
    inc = [c for c in crimes if _sentenca_incoerente(c) and rs.to_date(c.get("data_sentenca") or "") > pub]  # na soma só pelo trânsito
    if inc:
        base["_sent_inc_rot"] = [rs.crimes_curto([c]).strip() for c in inc]
        base["_sent_inc"] = ("sentença posterior ao trânsito em julgado no RSPE (%s): dado incoerente - considerada a condenação pelo "
                             "trânsito; conferir as datas da sentença e do trânsito (no júri, o trânsito pode ser o da pronúncia)" % "; ".join(
                                 "%s, sentença %s, trânsito %s" % (rs.crimes_curto([c]), c.get("data_sentenca"), rs.fmt(_transito_min(c))) for c in inc))
    pena = sum(rs.pena_para_dias(c.get("pena_imposta") or c.get("pena_total_processo")) or 0 for c in crimes)
    _ci = _cumprido_info(r, ctx, ref)
    cump, _orig = _ci["dias"], _ci["fonte"]
    if _ci["origem"] in ("ancora", "sem_calculo") and cump:
        base["_anc0"] = _ci["aviso"]
    elif _ci["origem"] == "estouro":
        base["_estouro"] = _ci["aviso"]
    reinc = any(c.get("reincidente_comum") == "S" or c.get("reincidente_especifico") == "S" for c in crimes) or bool(f.get("_forca_reinc"))
    if not reinc:
        # vale a marcação do RSPE (fração de primário, a que o SEEU aplicou); as datas indicam reincidência (condenação anterior
        # transitada antes do fato, sem os 5 anos do art. 64, I, do CP): nota de que o juízo pode recalcular
        _rl = _reinc_pelas_datas(crimes, (r.get("_crimes") or []) + (r.get("_outras_condenacoes") or []))
        if _rl:
            base["_reinc_lei"] = ("o RSPE não marca reincidência, mas %s transitou antes do fato de %s: o juízo pode recalcular como "
                                  "reincidente (CP, arts. 63 e 64, I)" % _rl)
    vga = any(rs.vga_indulto(c) for c in crimes)
    detalhe = {"pena": pena, "cumprido": cump, "fonte": _orig, "reincidente": reinc, "vga": vga, "crimes": [rs.crimes_curto([c]) for c in crimes]}
    vd_ver, tr_ver = [], []
    imp = _impeditivos(f, crimes, ref, pena, ver=vd_ver, incerto=tr_ver)
    base["_vd_ver"] = vd_ver
    base["_tr_ver"] = tr_ver
    nota_conc = ""
    lim = (f.get("impeditivos") or {}).get("nao_aplica_pena_ate_anos")
    sem_lim = (_impeditivos(dict(f, impeditivos=dict(f["impeditivos"], nao_aplica_pena_ate_anos=None)), crimes, ref)
               if lim and pena <= _anos_pena(lim) else [])
    if sem_lim:
        nota_conc = ("restrições do decreto afastadas para pena aplicada de até %s anos (%s)" % (lim, (f.get("impeditivos") or {}).get("dispositivo") or "decreto"))
        hed = [x for x in sem_lim if "hediondo ou equiparado" in x or "tráfico" in x]
        if hed:
            # a vedação a hediondos e tráfico vem da CF (art. 5º, XLIII) e da Lei 8.072/90 (art. 2º, I), que o decreto não afasta (ex.:
            # 2002, art. 7º, § 2º): o favorável fica A VERIFICAR; os demais impeditivos do decreto ficam afastados
            base["_hed_lim"] = ("%s: o %s afasta as restrições do decreto para pena aplicada de até %s anos, mas a vedação a hediondos e tráfico "
                                "vem da CF, art. 5º, XLIII, e da Lei 8.072/90, art. 2º, I, que o decreto não afasta" % (
                                    "; ".join(hed), (f.get("impeditivos") or {}).get("dispositivo") or "decreto", lim))
    pena_tot0, cump_tot0 = pena, cump  # antes do concurso: a soma total (teto do inciso no concurso - hip_ok)
    _op = custodia_outro_processo(r, ref, crimes)
    if _op:
        base["_outro_proc"] = _op  # o favorável fica A VERIFICAR (_avaliar_ficha_um)
        base["_outro_proc_dias"] = dias_custodia_outro_processo(r, ref, crimes)
    _It = (f.get("impeditivos") or {}).get("texto") or ""
    if re.search(r"mercancia", _It, re.I):
        # ex.: Decreto 6.706/2008, art. 8º, I: os §§ 2º a 4º do art. 33 ficam ressalvados "desde que a conduta típica não tenha
        # configurado a prática da mercancia" - o RSPE não diz; o favorável fica A VERIFICAR
        _m = [c for c in crimes if rs.num_lei(c.get("lei")) == "11343" and rs.num_art(c.get("artigo")) == "33"
              and (_priv(c) or re.match(r"\s*§\s*[23](?!\d)", c.get("tipo_penal") or ""))]
        if _m:
            base["_mercancia"] = ("%s: ressalvado pelo %s \"desde que a conduta típica não tenha configurado a prática da mercancia\" - conferir "
                                  "na sentença" % (rs.crimes_curto(_m), "%s do Decreto %s" % ((f.get("impeditivos") or {}).get("dispositivo") or "decreto",
                                                                                             f.get("numero") or "")))
    if imp:
        # concurso com crime impeditivo: cumprida a fração exigida da pena dele, o benefício alcança os demais crimes, com o
        # tempo excedente imputado a eles
        frc = _regra_concurso(f)
        imp_cr = [c for c in crimes if any(x.startswith(rs.crimes_curto([c]).strip() + ":") for x in imp)]
        resto = [c for c in crimes if c not in imp_cr]
        exclui = frc is None and _concurso_exclui(f)
        if exclui and resto:
            # 2000 e 2001, art. 9º: as penas se somam "excluindo-se dos benefícios as infrações do art. 10" - o crime impeditivo sai da
            # soma, sem vedar a execução toda; o decreto não diz a que pena se imputa o tempo cumprido - A VERIFICAR, com a conta dos
            # demais crimes pelo tempo cumprido total
            base["_conc_exclui"] = ("art. 9º: soma das penas excluídas as infrações do art. 10 (%s) - analisados os demais crimes (%s) com o tempo "
                                    "cumprido total; o decreto não diz a que pena se imputa o tempo cumprido - conferir" % (
                                        "; ".join(imp), rs.crimes_curto(resto)))
            frc = Fraction(0)
        if frc is not None and resto:
            pena_imp = sum(rs.pena_para_dias(c.get("pena_imposta") or c.get("pena_total_processo")) or 0 for c in imp_cr)
            exig_imp = int(pena_imp * frc.numerator // frc.denominator)  # fração em dias arredondada para baixo (A2), como no resto do programa
            # a fração do impeditivo só conta o tempo posterior ao fato dele (o anterior foi cumprido por outros crimes)
            cump_imp, nota_imp = (rs.cumprido_imputavel_impeditivos(imp_cr, cump, ctx["periodos"], ctx["rem"], ref, ctx["lc"], frc)
                                  if frc else (cump, ""))
            if cump_imp >= exig_imp:
                nota_conc = ("cumpridos %s da pena do crime impeditivo (%s); benefício sobre os demais crimes - conta pela pena cumprida, "
                             "não pela ordem da linha do tempo do SEEU, que é só informativa (aviso do CNJ no próprio sistema)") % (
                                 str(frc) if frc != 1 else "a íntegra", rs.dias_para_pena(exig_imp)) if not exclui else (
                    "art. 9º: crime do art. 10 excluído da soma; benefício analisado sobre os demais crimes")
                crimes, imp = resto, []
                pena = sum(rs.pena_para_dias(c.get("pena_imposta") or c.get("pena_total_processo")) or 0 for c in crimes)
                cump = cump - exig_imp
                vga = any(rs.vga_indulto(c) for c in crimes)
                # números depois do concurso (os da conta das hipóteses), para a linha do tempo mostrar os mesmos da aba
                detalhe.update(pena_conc=pena, cumprido_conc=cump, exigido_imp=exig_imp)
            else:
                imp = imp + ["faltavam %s para %s da pena do impeditivo (concurso%s)" % (_dias_txt(exig_imp - cump_imp), str(frc) if frc != 1 else "a íntegra",
                                                                                       ("; " + nota_imp) if nota_imp else "")]
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
        ach = rs.indicios_falta(r.get("_incidentes") or [], base_f, dias=dias_f, eventos=r.get("_eventos") or [], ate=min(pub, base_f), hoje=pub,  # prescrição da falta aferida na data do decreto
                                crimes=r.get("_crimes") or [], inicio=ini, fuga_firme=True)
        # decreto que exige a falta apurada/homologada (ex.: "falta sem a devida apuração não impede"): a não homologada
        # (fuga só registrada como evento) não impede - fica como ressalva
        # Decreto 11.846/2023, art. 6º (mesma redação do art. 6º de 2024/2025): a fuga sem homologação na janela impede, como lá
        hom = F.get("exige_homologacao") and not fuga_impede(f)
        falta_firme = [t for t, firme in ach if firme and not (hom and "não homologada" in t)]
        falta_ind = [(t.replace(FUGA_TRATADA, FUGA_APURAR) if hom and "não homologada" in t else t)
                     for t, firme in ach if not firme or (hom and "não homologada" in t)]
        a52 = [t for t in falta_ind if "LEP, art. 52" in t]
        if a52:
            base["_art52"] = "crime doloso na janela da falta grave (%s): %s" % (F.get("dispositivo") or "decreto", "; ".join(a52))
        outras = [t for t in falta_ind if "LEP, art. 52" not in t]
        if outras:
            # critério único (o de 2022 a 2025): falta na janela ainda não reconhecida em juízo - o favorável fica A VERIFICAR
            base["_falta_ver_afeta"] = f_afeta
            base["_falta_ver"] = "falta na janela a verificar (%s; só impede se reconhecida): %s" % (F.get("dispositivo") or "decreto", "; ".join(outras))
    # Decreto 9.246/2017, art. 4º, II a IV: veda a quem passou pelo RDD ou pelo Sistema Penitenciário Federal ou descumpriu as
    # condições da prisão domiciliar ou do livramento, a qualquer tempo - só com indício no RSPE, e como a verificar
    if re.search(r"descumpri\w*\s+(?:as\s+)?condi", F.get("texto") or "", re.I):
        disp_d = re.search(r"\((art\.\s*\d+º?,\s*[IVX]+\s*a\s*[IVX]+)\)", F.get("texto") or "")
        ind_d = ["livramento condicional de %s encerrado em %s (revogação, suspensão, regressão ou nova prisão)" % (rs.fmt(a), rs.fmt(b))
                 for a, b in ctx["lc"] if b and b <= pub]
        ind_d += ["%s em %s" % (" ".join(((e.get("tipo") or "") + " " + (e.get("motivo") or "")).split()).lower(), e.get("data"))
                  for e in r.get("_eventos") or [] if re.search(r"DESCUMPRI|REVOGAD", (e.get("motivo") or "").upper())
                  and (rs.to_date(e.get("data") or "") or date.max) <= pub]
        ind_d += ["%s em %s" % (rs._rotulo_incidente(i), i.get("data_referencia") or i.get("data_decisao"))
                  for i in r.get("_incidentes") or [] if (i.get("situacao") or "") == "CONCEDIDO"
                  and re.search(r"\bRDD\b|DIFERENCIADO|PENITENCIARI[OA] FEDERAL", rs._sem_acento((i.get("tipo") or "") + " " + (i.get("complemento") or "")).upper())
                  and (rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "") or date.max) <= pub]
        if ind_d:
            base["_descump"] = ("%s veda a quem descumpriu as condições do livramento ou da prisão domiciliar ou passou pelo RDD ou pelo Sistema "
                                "Penitenciário Federal, a qualquer tempo - indício no RSPE: %s; conferir" % (
                                    (disp_d.group(1) if disp_d else (F.get("dispositivo") or "o decreto")), "; ".join(list(dict.fromkeys(ind_d))[:3])))
    # comutação concedida por decreto anterior (incidente do RSPE)
    _com_ant_l = sorted(str(k[0])[:4] for k, v in decididos(r).items() if k[1] == "comutacao" and v[0] == "conc" and str(k[0])[:4].isdigit()
                        and int(str(k[0])[:4]) < int(f.get("ano") or 0))
    com_ant = bool(_com_ant_l)
    regime = _regime_em(r, ref) or _regime_inicial(r, crimes, ref)
    em_lc = any(a <= ref and (b is None or b >= ref) for a, b in ctx["lc"])
    _pu = rs.uniao_periodos(ctx["periodos"])
    continuo_atual = next(((ref - a).days + 1 for a, b in _pu if a <= ref and (b is None or b >= ref)), 0)
    # "cumprido ininterruptamente": a regra única de todos os decretos (a de 2024/2025, rspe_scraper, inciso IV) - qualquer período
    # ininterrupto completo até a data (o maior), somadas as remições concedidas dentro dele (LEP, art. 128: o tempo remido é pena
    # cumprida para todos os efeitos), salvo texto em contrário do decreto. Período anterior encerrado por fuga: a verificar
    _pc = max(((a, b if (b and b <= ref) else ref) for a, b in _pu if a <= ref), key=lambda p: (p[1] - p[0]).days, default=None)
    continuo = ((_pc[1] - _pc[0]).days + 1 + sum(n for d, n in ctx["rem"] if d and _pc[0] <= d <= _pc[1])) if _pc else 0
    inint_fuga = ""
    if _pc and _pc[1] < ref and not continuo_atual >= (_pc[1] - _pc[0]).days + 1:
        ev_f = [e for e in r.get("_eventos") or [] if re.search(r"FUGA|EVAS|ABANDON|FORAGID|N[ÃA]O RETORN", ((e.get("tipo") or "") + " " + (e.get("motivo") or "")).upper())
                and rs.to_date(e.get("data") or "") and abs((rs.to_date(e.get("data")) - _pc[1]).days) <= 3]
        if ev_f:
            inint_fuga = ("o período ininterrupto considerado (%s a %s) terminou em fuga (%s): conferir se ele vale para o requisito" % (
                rs.fmt(_pc[0]), rs.fmt(_pc[1]), ev_f[0].get("data")))

    priv_proprio = any(re.search(r"trafico privilegiado", rs._sem_acento(h.get("outros_requisitos") or "").lower()) for h in f.get("indulto") or [])
    amb_com = [""]  # dúvida (teto no concurso, período ininterrupto que terminou em fuga) da última hipótese de comutação atendida

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
        if h.get("pena_max_anos") is not None and rem_mode and pena - cump > _anos_pena(h["pena_max_anos"]):
            return False, None, "pena remanescente de %s acima de %s anos" % (rs.dias_para_pena(pena - cump), h["pena_max_anos"])
        if h.get("pena_max_anos") is not None and not rem_mode and pena > _anos_pena(h["pena_max_anos"]):
            return False, None, "pena total de %s acima de %s anos" % (rs.dias_para_pena(pena), h["pena_max_anos"])
        teto_amb = ""
        if h.get("pena_max_anos") is not None and pena_tot0 != pena:
            # concurso com impeditivo: o teto atendido só sobre os crimes não impeditivos; a cláusula de soma das penas não diz se,
            # no concurso, ele se mede sobre o total - a verificar, com as duas contas
            _v, _v0 = (pena - cump, pena_tot0 - cump_tot0) if rem_mode else (pena, pena_tot0)
            if _v0 > _anos_pena(h["pena_max_anos"]):
                teto_amb = ("%s de %s nos crimes não impeditivos, dentro do teto de %s anos; com o crime impeditivo, a soma (%s) o excede - o decreto "
                            "manda somar as penas e não diz se, no concurso, o teto se mede sobre o total: a verificar" % (
                                "pena remanescente" if rem_mode else "pena", rs.dias_para_pena(_v), h["pena_max_anos"], rs.dias_para_pena(_v0)))
        if h.get("pena_min_anos") is not None and pena <= _anos_pena(h["pena_min_anos"]):
            return False, None, "pena total não supera %s anos" % h["pena_min_anos"]
        if (h.get("violencia_grave_ameaca") or "") == "vedada" and vga:
            return False, None, "crime com violência ou grave ameaça"
        if (h.get("violencia_grave_ameaca") or "") == "exigida" and not vga:
            return False, None, "hipótese só para crime com violência ou grave ameaça"
        reg = [rs._sem_acento(x).lower() for x in (h.get("regime") or [])]
        sem_regime = ""
        if reg and not regime and not any("livramento" in x for x in reg):
            if h.get("ininterrupto") and continuo_atual and all(re.match(r"fechado|semiaberto", x) for x in reg):
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
            # fração da pena em dias arredondada para baixo, o critério do restante do programa (e da projeção da linha do tempo):
            # nunca exige mais do que a fração exata
            exig = int(pena * fr.numerator // fr.denominator)
        elif anos is not None:
            exig = rs.dias_anos(anos, ref)
        if comut and exig and com_ant and re.search(r"novo requisito temporal|independentemente de novo", rs._sem_acento(h.get("texto") or "") + " " + o, re.I):
            exig = 0  # já comutado em decreto anterior: a nova comutação dispensa novo requisito temporal
        base_c = cump
        inint = bool(h.get("ininterrupto") and anos is not None)
        if inint:
            base_c = continuo  # anos ininterruptos: o maior período contínuo até a data, com as remições dentro dele
        if exig is not None and base_c < exig:
            if inint:
                return False, exig, "faltavam %s de custódia ininterrupta para %s anos em %s" % (_dias_txt(exig - base_c), anos, rs.fmt(ref))
            return False, exig, "faltavam %s para %s em %s" % (_dias_txt(exig - cump), str(fr) if fr is not None else "%s anos" % anos, rs.fmt(ref))
        amb_c = "; ".join(x for x in (teto_amb, inint_fuga if inint else "") if x)
        if amb_c and comut and not sem_regime:
            # a comutação não tem o caminho "a verificar" das hipóteses: atende, e a dúvida vai para o resultado (_teto_amb)
            amb_com[0] = amb_c
            return True, exig, ""
        amb = "; ".join(x for x in (sem_regime, amb_c) if x)
        if amb:
            return None, exig, amb
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
        o_obj = rs._sem_acento(h.get("outros_requisitos") or "").lower()
        if ex is None and ok and vga and re.search(r"condicoes pessoais|circunstancias favoraveis|avaliacao judicial", o_obj):
            # crime doloso com violência ou grave ameaça (ex.: 2000 e 2001, art. 1º, § 1º): depende de o juiz constatar condições
            # pessoais favoráveis - a mesma regra da hipótese não objetiva (_extra, "subj")
            ok = None
            mot = ("requisitos de pena, tempo e regime atendidos; como o crime tem violência ou grave ameaça, depende ainda de avaliação "
                   "judicial das condições pessoais (%s)" % (h.get("dispositivo") or "decreto"))
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
    com, com_n, com_amb = None, None, ""
    for h in f.get("comutacao") or []:
        hh = {"pena_max_anos": h.get("pena_max_anos"), "violencia_grave_ameaca": h.get("violencia_grave_ameaca"),
              "fracao_nao_reincidente": h.get("cumprimento_min_nao_reincidente"), "fracao_reincidente": h.get("cumprimento_min_reincidente"),
              "outros_requisitos": h.get("outros_requisitos") or "", "texto": h.get("texto") or ""}
        ex = None
        if not _decisiva(dict(hh, outros_requisitos=h.get("outros_requisitos") or "")):
            # hipótese de idade (ex.: 2023, art. 3º, § 3º, I - maiores de 65 anos): decide-se pela data de nascimento do RSPE
            ex = _extra(hh) if re.search(r"anos de idade completos", rs._sem_acento(hh["outros_requisitos"]).lower()) else None
            if ex is None or ex[1] is None:
                continue
        amb_com[0] = ""
        ok, exig, mot = hip_ok(dict(hh, texto=(h.get("texto") or "")), comut=True)
        ok = bool(ok)
        amb_h = amb_com[0]
        if ex is not None and ex[1] is False:
            ok, mot = False, ex[2]
        if ok and pena and pena - cump <= 0 and _ci["origem"] == "seeu":
            # pena considerada já integralmente cumprida na data (no concurso, a dos demais crimes, pela imputação): nada a comutar
            ok, mot = False, "sem pena remanescente a comutar em %s (cumprido %s de %s)" % (rs.fmt(ref), rs.dias_para_pena(cump), rs.dias_para_pena(pena))
        hips.append({"tipo": "comutacao", "dispositivo": h.get("dispositivo") or "", "ok": ok, "exigido": exig, "mot": mot, "texto": h.get("texto") or "",
                     "fracao": (hh["fracao_reincidente"] if reinc else hh["fracao_nao_reincidente"]) or "",
                     "reducao": (h.get("reducao_reincidente") if reinc else h.get("reducao_nao_reincidente")) or ""})
        if ok:
            if com is None:
                com = (h, exig)
                com_amb = amb_h
            continue
        if com_n is None:
            com_n = (h, exig, mot)
    res = dict(base, detalhe=detalhe, regime=regime, nota=nota_conc, hips=hips, falta_ind=falta_ind, falta_firme=falta_firme,
               alc=[n for n, c in enumerate(r.get("_crimes") or []) if any(c is y for y in crimes0)])
    imp_ind = bool(imp) and "comuta" not in afeta.replace("indulto e comuta", "")
    imp_com = bool(imp) and ("indulto e comuta" in afeta or "só comuta" in afeta or afeta.startswith("so comuta"))
    f_ind = bool(falta_firme) and "indulto" in f_afeta
    f_com = bool(falta_firme) and ("comuta" in f_afeta)
    res["ind_ver"] = bool(ind_ver and not ind and not imp_ind and not f_ind)  # hipótese de indulto a verificar (linha do tempo)
    mot_falta = "falta grave %s: %s" % (("nos %s meses anteriores" % f_meses) if f_meses else "punida até a data", falta_firme[0]) if falta_firme else ""
    if f_ind and (f_com or not (com and not imp_com)):
        return dict(res, s="nao", mot=mot_falta)
    if ind and not imp_ind and not f_ind:
        h, exig = ind
        return dict(res, s="cabe", beneficio="Indulto", dispositivo=h.get("dispositivo") or "", exigido=exig,
                    fracao=(h.get("fracao_reincidente") if reinc else h.get("fracao_nao_reincidente")) or "",
                    mot=("cumpriu %s em %s" % (rs.dias_para_pena(cump), rs.fmt(ref))) + (" (exigido %s)" % rs.dias_para_pena(exig) if exig else ""),
                    ressalva="")
    if ind_ver and not ind and not imp_ind and not f_ind and not (com and not imp_com and not f_com):
        return dict(res, s="ver", mot=ind_ver[2], dispositivo=ind_ver[0].get("dispositivo") or "", exigido=ind_ver[1])
    if com and not imp_com and not f_com:
        h, exig = com
        if com_amb:
            res["_teto_amb"] = com_amb  # o favorável fica A VERIFICAR (_avaliar_ficha_um)
        red = h.get("reducao_reincidente") if reinc else h.get("reducao_nao_reincidente")
        rc = _reducao_comutacao(f, red, pena, cump, bool(com_ant))
        if rc:
            res["reducao_calc"] = rc
            red_txt = "comutação de %s da pena %s (%s), redução de %s; pena remanescente passa de %s para %s" % (
                red, {"cumprido": "cumprida", "pena": "total"}.get(rc["base"], "remanescente"), rs.dias_para_pena(rc["base_dias"]),
                _dias_txt(rc["reducao"]), rs.dias_para_pena(rc["antes"]), rs.dias_para_pena(rc["depois"]))
            if rc.get("regra"):
                red_txt += " (%s)" % rc["regra"]
            if com_ant:
                # a pena considerada é a soma das penas impostas: a comutação anterior concedida não está descontada dela, e o RSPE não
                # traz quanto ela reduziu - a redução e o remanescente reais são menores
                red_txt += (" - valores máximos: a comutação anterior concedida (%s) não está descontada da pena, e o RSPE não traz quanto "
                            "ela reduziu; o remanescente e a redução reais são menores - conferir no SEEU" % ", ".join(dict.fromkeys(_com_ant_l)))
                rc["com_ant_nao_descontada"] = True
        elif pena and pena - cump <= 0:
            red_txt = "comutação de %s - pela conta não sobra pena remanescente a comutar (conferir o tempo cumprido)" % (red or "?")
        else:
            red_txt = "comutação de %s do remanescente" % (red or "?")
        return dict(res, s="cabe", beneficio="Comutação", dispositivo=h.get("dispositivo") or "", exigido=exig,
                    fracao=red or "",
                    # "reducao" é exibida pela aba como "<fração> do remanescente": só quando essa é a base de cálculo do decreto
                    reducao=(red or "") if (not rc or rc["base"] == "remanescente") else "",
                    mot="cumpriu %s em %s%s; %s" % (rs.dias_para_pena(cump), rs.fmt(ref), (" (exigido %s)" % rs.dias_para_pena(exig)) if exig else "", red_txt),
                    ressalva="; ".join(x for x in ("",
                                                   ("indulto a verificar (%s): %s" % (ind_ver[0].get("dispositivo") or "", ind_ver[2]))
                                                   if (ind_ver and not ind and not imp_ind and not f_ind) else "") if x))
    restrito = not any(h.get("objetivo") and _decisiva(h) for h in (f.get("indulto") or [])) and not (f.get("comutacao") or [])
    if imp and restrito:
        # decreto só para grupos (doença, deficiência...): o resultado é o mesmo com ou sem o crime impeditivo - diz o motivo
        # exato, em vez de "vedado"
        return dict(res, s="nao", mot="decreto restrito (doença, deficiência, agentes de segurança ou outros grupos): nenhuma hipótese "
                                      "aferível pelo RSPE; há também crime impeditivo (%s)" % "; ".join(imp))
    if imp:
        return dict(res, s="imp", mot="; ".join(imp))
    sem_rem = next((x for x in hips if x["tipo"] == "comutacao" and (x.get("mot") or "").startswith("sem pena remanescente a comutar")), None)
    if sem_rem:
        # a comutação caiu só porque a pena considerada já estava cumprida na data (o requisito de tempo foi atendido): esse é o
        # motivo, e não o da hipótese de indulto que chegou mais perto
        return dict(res, s="nao", mot=sem_rem["mot"] + ((" - indulto: %s" % ind_n[2]) if (ind_n and ind_n[2]) else ""),
                    exigido=sem_rem.get("exigido"), dispositivo=sem_rem.get("dispositivo") or "")
    if ind_n and ind_n[2]:
        return dict(res, s="nao", mot=ind_n[2], exigido=ind_n[1], dispositivo=ind_n[0].get("dispositivo") or "")
    if com_n and com_n[2]:
        return dict(res, s="nao", mot=com_n[2], exigido=com_n[1], dispositivo=com_n[0].get("dispositivo") or "")
    if restrito:
        return dict(res, s="nao", mot="decreto restrito (doença, deficiência, agentes de segurança ou outros grupos): nenhuma hipótese pelos dados do RSPE")
    return dict(res, s="nao", mot="nenhuma hipótese objetiva do decreto alcança o caso")


def _base_comutacao(f):
    """Base de cálculo da redução que o texto do decreto manda: "maior" (a pena remanescente, ou o período já cumprido quando,
    descontadas as comutações anteriores, for superior a ela - 2009 a 2015 e 2023, art. 2º/3º, § 1º); "pena" (a pena, sem dizer
    remanescente: "terá comutada sua pena" - 2000 a 2002, em que só quem já teve comutação anterior a tem calculada sobre o
    remanescente, parágrafo único); "remanescente" nos demais. Lida do texto de toda a ficha: o § 1º vale para o artigo inteiro,
    inclusive as hipóteses dos §§ seguintes."""
    hs = f.get("comutacao") or []
    t = rs._sem_acento(" ".join("%s %s" % (h.get("texto") or "", h.get("outros_requisitos") or "") for h in hs)).lower()
    if re.search(r"periodo (?:de pena )?(?:ja )?cumprido[^.;]{0,120}superior ao remanescente|periodo (?:ja )?cumprido se (?:este )?(?:\([^)]*\) )?(?:for )?maior"
                 r"|ou (?:o )?periodo cumprido se maior", t):
        return "maior"
    if re.search(r"comutada sua pena", t) and not re.search(r"comutada a pena remanescente|comutacao da (?:pena|ppl) remanescente", t):
        return "pena"
    return "remanescente"


def _reducao_comutacao(f, red, pena, cump, com_ant):
    """Redução da comutação cabível, pela base que o decreto manda (_base_comutacao): {fracao, base ('remanescente' | 'cumprido' |
    'pena'), base_dias, reducao, antes, depois, regra}; None sem fração ou sem pena. Os dias da redução são arredondados para baixo,
    como na análise de 2024/2025 (rspe_scraper, art. 13)."""
    fr = _fr(red)
    if not fr or not pena or pena - cump <= 0:
        return None
    rem = pena - cump
    regra = _base_comutacao(f)
    base, regra_txt = "remanescente", ""
    if regra == "maior" and cump > rem:
        base, regra_txt = "cumprido", "o decreto manda calcular sobre o período cumprido quando superior ao remanescente"
    elif regra == "pena" and not com_ant:
        base, regra_txt = "pena", "o decreto comuta a pena; só a comutação anterior desloca o cálculo para o remanescente"
    bd = {"cumprido": cump, "pena": pena}.get(base, rem)
    n = int(bd * fr.numerator // fr.denominator)
    return {"fracao": str(fr), "base": base, "base_dias": bd, "reducao": n, "antes": rem, "depois": max(0, rem - n), "regra": regra_txt}


def _tese_hediondez(f, r, x):
    """Decreto que veda "hediondos" sem dizer "praticado após" a lei: o STJ afere a hediondez na data do decreto. O motor afere na
    data do fato (tese da irretroatividade - STF, 2ª T.); se o benefício só cabe por ela, o resultado é A VERIFICAR (tese)."""
    if x.get("s") != "cabe" or "praticado após" in ((f.get("impeditivos") or {}).get("texto") or "").lower():
        return x
    ref = rs.to_date(x.get("ref") or f.get("data_referencia") or "")
    if not ref:
        return x
    sup = [c for c in r.get("_crimes") or [] if _em_execucao(c, ref, r)
           and rs.to_date(c.get("data_infracao") or "") and rs.to_date(c.get("data_infracao")) <= ref
           and rs.e_hediondo(c, ref) and not rs.e_hediondo(c, None)]
    # lesão gravíssima/seguida de morte (art. 129, §§ 2º e 3º): hedionda só contra agente (Lei 13.142/2015) - o RSPE não diz a vítima
    les = [c for c in r.get("_crimes") or [] if ref >= date(2015, 7, 7) and _em_execucao(c, ref, r)
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
    # falta do art. 6º a verificar: o favorável fica A VERIFICAR (o mesmo critério das colunas, da linha do tempo e dos relatórios)
    if si == "cabe" and rs.falta_a_verificar(ti):
        si = "ver"
    if sc == "cabe" and rs.falta_a_verificar(tc):
        sc = "ver"
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
        if sc == "cabe" and rs.falta_a_verificar(tc):
            sc = "ver"
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


def _indulto_sem_comutacao(ano, x, r, f, ctx, ini, hoje):
    """Resultado do indulto do decreto (cabe ou a verificar), para quando só a comutação foi indeferida no RSPE; None se não cabe."""
    if x.get("detalhado"):
        ki = DETALHADOS[ano][1]
        ti = r.get(ki) or ""
        si = MAPA_STATUS.get(r.get(ki + "_status") or "", "")
        if si == "cabe" and rs.falta_a_verificar(ti):
            si = "ver"
        if si in ("cabe", "ver"):
            return dict(x, s=si, beneficio="Indulto", mot=ti, ressalva="")
        return None
    if not f or not (f.get("indulto") or []):
        return None
    try:
        y = _tese_hediondez(f, r, avaliar_ficha(dict(f, comutacao=[]), r, ctx, ini, hoje))  # só as hipóteses de indulto
    except Exception:
        return None
    if y.get("s") in ("cabe", "ver"):
        return dict(y, beneficio="Indulto")
    return None


def _sem_objeto(r, x):
    """Execução encerrada (arquivada, extinta ou com todas as penas extintas): o resultado favorável calculado não tem objeto."""
    mot = rs.execucao_encerrada(r)
    if mot and x.get("s") in ("cabe", "ver"):
        x.update(s="nao", mot="não se aplica: %s - sem pena a cumprir (triagem sem o encerramento: %s)" % (mot, x.get("mot") or ""),
                 beneficio="", ressalva="")
    return x


def _frase(t, n=110):
    """Primeira oração (até '; ', ': ', ' | ' ou '. ' fora de parênteses), sem o parêntese final longo, com no máximo n caracteres."""
    t = (t or "").strip()
    prof = 0
    for i, ch in enumerate(t):
        if ch == "(":
            prof += 1
        elif ch == ")":
            prof = max(0, prof - 1)
        elif prof == 0 and i >= 12 and (t[i:i + 2] in ("; ", ": ", ". ") or t[i:i + 3] == " | "):
            if ch == "." and re.search(r"(?:\bart|\binc|\bp|\bn|nº|\bal|\bLei)$", t[:i], re.I):
                continue
            t = t[:i]
            break
    if len(t) > n:
        t = re.sub(r"\s*\([^()]{25,}\)$", "", t)
    if len(t) > n:
        t = t[:n - 1].rsplit(" ", 1)[0].rstrip(",;:(") + "…"
        t += ")" * max(0, t.count("(") - t.count(")"))
    return t[:1].upper() + t[1:]


def motivo_curto(x):
    """Motivo do resultado em uma linha, objetivo: por que cabe ou não cabe (o texto completo fica em x["mot"], na dica e na linha
    do tempo)."""
    s, t = x.get("s"), (x.get("mot") or "").strip()
    if s in ("conc", "indef"):
        return t.replace(" (incidente do RSPE)", "")
    m_c = re.search(r"cumpriu (\d+a\d+m\d+d) em [\d/]+(?: \(exigido (\d+a\d+m\d+d)\))?", t)
    red = re.search(r"redução de (\d+a\d+m\d+d)", t)
    tempo = ("Tempo cumprido: %s%s" % (m_c.group(1), " (exigido %s)" % m_c.group(2) if m_c.group(2) else "")) if m_c else ""
    if s == "cabe":
        if tempo:
            return tempo + ("; redução de %s" % red.group(1) if red else "")
        if t.startswith("POSSÍVEL (") and rs.ROT_ART2 in t.split(" | ")[0]:
            return "Requisitos atendidos quanto aos crimes com trânsito; conferir os demais (art. 2º, II)"
        m = re.match(r"POSSÍVEL( \(crimes não impeditivos[^)]*\))?(?:: ([^|]+))?", t)
        if m:
            disp = (m.group(2) or "").strip()
            return "Requisitos atendidos%s%s" % (" nos crimes não impeditivos" if m.group(1) else "",
                                                 " (%s)" % disp if disp and len(disp) <= 60 and not disp.startswith("art. 5º para") else
                                                 " (art. 5º)" if disp.startswith("art. 5º") else "")
        return _frase(t)
    if s == "ver":
        if t.startswith("A VERIFICAR (remição pendente)"):
            m = re.search(r"a remição de (\d+ dias?)", t)
            return "Remição pendente%s cobre o tempo que faltava: pedir a declaração" % (" de " + m.group(1) if m else "")
        m = (re.search(r"A VERIFICAR - (.+)", t) or re.search(r"A VERIFICAR[^:|]*:\s*art\. 9º[^|]*\|\s*(.+)", t)
             or re.search(r"A VERIFICAR(?: \([^)]*\))?:\s*(.+)", t) or re.search(r"(falta a verificar)", t)
             or re.search(r"o (cumprimento estava interrompido em [\d/]+)", t) or re.search(r"^(cumprimento interrompido em [\d/]+)", t))
        motivo = m.group(1) if m else t
        motivo = re.sub(r"^falta na janela a verificar", "falta na janela do decreto", motivo)
        if motivo.startswith("pela âncora do SEEU"):
            motivo = "o cumprido pelo SEEU fica abaixo do que os eventos mostram"
        motivo = _frase(re.sub(r"\s*\((?:[^()]|\([^()]*\))*;(?:[^()]|\([^()]*\))*\)", "", motivo), 90)
        return ("%s; a verificar: %s" % (tempo, motivo[:1].lower() + motivo[1:])) if tempo and m else "A verificar: " + motivo[:1].lower() + motivo[1:]
    if s == "imp":
        if t.startswith("VEDADO"):
            m = re.match(r"VEDADO \(([^)]+)\)", t)
            return "Crime vedado pelo decreto%s" % (" (%s)" % m.group(1) if m else "")
        crimes, nats = [], []
        for seg in re.split(r"; ", t):
            m = re.match(r"(art\. [^:]+?)(?: \(extinto\))?: (.+)", seg)
            if m:
                crimes.append(m.group(1))
                nats.append("hediondo" if m.group(2).startswith("hediondo") else re.split(r" na data| \(| - |,", m.group(2))[0])
        fa = re.search(r"faltavam (\S+) para (2/3|a íntegra) da pena do impeditivo", t)
        if crimes:
            crimes, nats = list(dict.fromkeys(crimes)), list(dict.fromkeys(nats))
            lst = ", ".join(crimes[:3]) + (" e mais %d" % (len(crimes) - 3) if len(crimes) > 3 else "")
            return "%s: %s%s%s" % ("Crimes impeditivos" if len(crimes) > 1 else "Crime impeditivo", lst, " (%s)" % nats[0] if len(nats) == 1 else "",
                                                 "; faltavam %s para %s da pena impeditiva" % (fa.group(1), fa.group(2)) if fa else "")
        return _frase(t)
    # não cabe
    t2 = re.sub(r"^cumprimento interrompido em [\d/]+ \([^)]*\); ", "", t)
    m = re.search(r"faltavam (\S+(?: dias?)?)( de custódia ininterrupta)? para ([^;|(]+?) em [\d/]+", t2)
    if m:
        return "Tempo insuficiente: faltavam %s%s para %s" % (m.group(1), m.group(2) or "", m.group(3).strip())
    m = re.match(r"(?:NÃO CABE \(art\. \d+º\): )?falta grave (?:com sanção reconhecida )?nos 12 meses(?: anteriores)?", t2)
    if m:
        d = re.search(r"\d{2}/\d{2}/\d{4}", t2)
        return "Falta grave nos 12 meses anteriores ao decreto%s" % (" (%s)" % d.group(0) if d else "")
    if t2.startswith("decreto restrito"):
        return "Decreto restrito (doença, deficiência e outros grupos): nenhuma hipótese aferível pelo RSPE"
    t2 = re.sub(r"^(?:não se aplica|não atinge):\s*", "", t2)
    return _frase(t2)


def _remicao_pendente(x, r):
    """Remição pendente da ficha (dias exatos, período até o decreto) que cobre o que faltava: o "não atinge" passa a A VERIFICAR.
    Os decretos 2022, 2024 e 2025 já vêm do registro com a mesma regra (rspe_ficha.remicao_pendente_decretos). Altera x."""
    ref = rs.to_date(x.get("ref") or "")
    if x.get("s") != "nao" or x.get("detalhado") or not ref or not r.get("_rem_pend"):
        return
    fl = rs.faltas_remiveis(x.get("mot"))
    tot, rots = rs.remicao_pendente_ate(r, ref)
    if fl and tot >= min(fl):
        x.update(s="ver", mot="A VERIFICAR (remição pendente): %s; %s" % (x.get("mot") or "", rs.nota_remicao_pendente(tot, rots, ref)))


RE_COM_ANT = re.compile(r"(art\.? ?\d+º?(?:, p\.? ?u\.?| p\.? ?u\.?)?)[^.;]{0,20}?conced\w* (?:a )?comuta\w* a quem n[ãa]o obteve (?:as )?comuta", re.I)


def _tem_comutacao(fx, y):
    """O decreto do item y concedeu comutação: a ficha tem hipótese de comutação; o Decreto 11.302/2022 (análise detalhada) não
    concedeu comutação (só indulto e, no art. 15, a conversão da prestação de serviços)."""
    if str(y.get("id")) == "2022":
        return False
    fy = fx.get(str(y.get("id")))
    return bool(fy.get("comutacao")) if fy else True


def _tese_comutacoes_anteriores(out, fx, dec):
    """Decretos que concedem a comutação dos decretos anteriores a quem não a obteve, "independentemente de pedido anterior" (2013 a
    2015, art. 3º; 2017, art. 7º, p. ú.; 2023, art. 4º): com comutação cabível ou a verificar num decreto anterior e não decidida no
    RSPE, a tese entra como A VERIFICAR na ressalva - exige reconstruir a pena em cada data, sem usar o mesmo tempo de pena duas vezes
    (2023, art. 4º, p. ú.). Não muda o resultado do decreto. Altera os itens de out."""
    for x in out:
        f = fx.get(str(x.get("id")))
        if not f or x.get("s") in ("fora", "futuro"):
            continue
        txt = " ".join([str(h.get("texto") or "") + " " + str(h.get("outros_requisitos") or "") for h in f.get("comutacao") or []]
                       + [str(o) for o in f.get("observacoes") or []])
        m = RE_COM_ANT.search(txt)
        if not m:
            continue
        ref = rs.to_date(x.get("ref") or "")
        ant = [y for y in out if ref and (rs.to_date(y.get("ref") or "") or date.max) < ref and str(y.get("id")) != str(x.get("id"))
               and (y.get("s") == "ver" or (y.get("s") == "cabe" and y.get("beneficio") == "Comutação"))
               and not dec.get((str(y.get("id")), "comutacao")) and _tem_comutacao(fx, y)]
        if not ant:
            continue
        disp = m.group(1).replace("p.u.", "p. ú.").replace("Art.", "art.")
        t = ("tese (a verificar): o %s do Decreto %s concede a comutação dos decretos anteriores a quem não a obteve, independentemente de "
             "pedido anterior - comutação cabível ou a verificar, não decidida no RSPE: %s; reconstruir a pena em cada data, sem usar o mesmo "
             "tempo de pena duas vezes" % (disp, x.get("numero") or "", ", ".join("%s (%s)" % (y.get("ano") or y.get("id"), "cabe" if y.get("s") == "cabe" else "a verificar")
                                                                                    for y in ant)))
        x["tese_com_ant"] = t
        x["ressalva"] = "; ".join(v for v in (x.get("ressalva") or "", t) if v)


def _incertezas_rspe(f, r, ctx, ini, hoje, x):
    """Resultado que depende de dado incerto do RSPE fica "ver": crime alcançado com pena não informada ("Pena Imposta: 0" - o zero
    favorece o "cabe"), com "Suspenso: Sim" sem a causa ou com medida de segurança (o prazo mínimo não é pena); e o requisito de
    idade que muda com a data de nascimento da ficha do SIAPEN (r["_nasc_alt"], diferente da do RSPE)."""
    if x.get("s") not in ("cabe", "nao") or rs.execucao_encerrada(r) or re.search(r"sem pena a cumprir|não se aplica", x.get("mot") or ""):
        return
    ref = rs.to_date(f.get("data_referencia") or "") or hoje
    alc = [c for c in r.get("_crimes") or [] if not (c.get("extinto") or "").upper().startswith("S")
           and (rs.to_date(c.get("data_infracao") or "") or date.min) <= ref]
    zero = [c for c in alc if c.get("pena_nao_informada")]
    duv = [c for c in alc if c.get("medida_seguranca") or rs.suspenso_rspe(c)]
    mot = ""
    if zero and x.get("s") == "cabe":
        mot = "pena não informada no RSPE (%s: \"Pena Imposta: 0\")" % rs.crimes_curto(zero)
    elif duv and (x.get("s") == "cabe" or rs.pena_decide_txt(x.get("mot") or "")):
        mot = "%s no RSPE (%s): a pena sai das contas só com o sursis, a substituição ou a medida confirmados" % (
            "medida de segurança" if any(c.get("medida_seguranca") for c in duv) else "\"Suspenso: Sim\" sem a causa", rs.crimes_curto(duv))
    elif r.get("_nasc_alt") and rs.to_date(r.get("_nasc_alt")) != rs.to_date(r.get("data_nascimento") or ""):
        try:
            y = avaliar_ficha(f, dict(r, data_nascimento=r["_nasc_alt"]), ctx, ini, hoje)
        except Exception:
            y = {}
        if y.get("s") and y.get("s") != x.get("s"):
            mot = "data de nascimento divergente (RSPE %s, ficha %s): com a da ficha o resultado muda - conferir o documento" % (
                r.get("data_nascimento") or "?", r["_nasc_alt"])
    if mot:
        x["s"] = "ver"
        x["mot"] = "a verificar: %s%s" % (mot, ("; antes: " + x["mot"]) if x.get("mot") else "")


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
            x = _sem_objeto(r, _tese_hediondez(f, r, x))
            _incertezas_rspe(f, r, ctx, ini, hoje, x)
        except Exception as e:  # uma ficha com dado ruim não derruba o assistido
            x = {"id": f["id"], "ano": f.get("ano"), "numero": f.get("numero") or "", "ref": f.get("data_referencia"), "s": "ver",
                 "mot": "falha ao avaliar o decreto: %s" % e}
        out.append(x)
    for ano in DETALHADOS:
        ref = _REF_DET.get(ano)
        if ref and ref <= hoje:
            fora = {"id": ano, "ano": int(ano), "numero": DETALHADOS[ano][0], "ref": rs.fmt(ref), "s": "fora", "detalhado": True}
            pub = rs.DECRETOS_PUB.get(ano) or ref
            x = _sem_objeto(r, _detalhado(ano, r))
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
        # concessão de um dos dois prevalece (o quadro conta o melhor resultado); a de indulto, se houver as duas
        d = next((y for y in (di, dc) if y and y[0] == "conc"), None) or di or dc
        if d and d[0] == "indef" and ano == "2017" and x.get("s") == "cabe":
            # Decreto 9.246/2017: indeferimentos apoiados na cautelar da ADI 5874 (julgada improcedente em 09/05/2019) podem ser renovados
            x["ressalva"] = "indeferido no RSPE em %s; a cautelar da ADI 5874 caiu (ação improcedente, 09/05/2019): o pedido pode ser renovado" % (d[1] or "?")
            continue
        if di and di[0] == "indef" and not dc:
            # indulto indeferido e comutação não decidida: a comutação cabível (ou a verificar) continua a valer
            y = _comutacao_sem_indulto(ano, x, r, fx.get(ano), ctx, ini, hoje)
            if y and _sem_objeto(r, y).get("s") not in ("cabe", "ver"):
                y = None  # execução encerrada: a comutação refeita também não tem objeto
            if y and y.get("s") == "cabe":
                # o indeferimento pode ter fundamento que também afasta a comutação (falta grave, crime impeditivo): a comutação
                # fica A VERIFICAR até a leitura da decisão - se o indulto caiu por requisito só dele (fração, teto de pena), o pedido segue
                y = dict(y, s="ver", mot="%s; A VERIFICAR - indulto indeferido no RSPE%s: conferir o fundamento do indeferimento (se foi falta "
                                         "grave ou crime impeditivo, a comutação cai pelo mesmo motivo; se foi requisito só do indulto, como "
                                         "fração ou teto de pena, o pedido de comutação segue)" % (y.get("mot") or "", (" em " + di[1]) if di[1] else ""))
            if y:
                x.clear()
                x.update(y, ressalva="; ".join(t for t in ("indulto indeferido no RSPE%s; a comutação não foi decidida" % ((" em " + di[1]) if di[1] else ""),
                                                           y.get("ressalva") or "") if t))
                continue
        if dc and dc[0] == "indef" and not di:
            # comutação indeferida e indulto não decidido: o indulto cabível (ou a verificar) continua a valer
            y = _indulto_sem_comutacao(ano, x, r, fx.get(ano), ctx, ini, hoje)
            if y and _sem_objeto(r, y).get("s") not in ("cabe", "ver"):
                y = None  # execução encerrada: o indulto refeito também não tem objeto
            if y:
                x.clear()
                x.update(y, ressalva="; ".join(t for t in ("comutação indeferida no RSPE%s; o indulto não foi decidido" % ((" em " + dc[1]) if dc[1] else ""),
                                                           y.get("ressalva") or "") if t))
                continue
        if dc and dc[0] == "conc" and not di:
            # só a comutação concedida e o indulto não decidido: a concessão não esconde o indulto que a análise (detalhada em 2022,
            # 2024 e 2025; pela ficha nos demais decretos) ainda dá como cabível ou a verificar - o indulto é o benefício mais amplo e
            # pode ser pedido (art. 13, § 5º, dos Decretos 12.338/2024 e 12.790/2025: a comutação não alcança quem preenche o indulto)
            y = _indulto_sem_comutacao(ano, x, r, fx.get(ano), ctx, ini, hoje)
            if y and _sem_objeto(r, dict(y)).get("s") not in ("cabe", "ver"):
                y = None
            if y:
                x.clear()
                x.update(y, ressalva="; ".join(t for t in ("comutação concedida no RSPE%s; o indulto não foi decidido" % ((" em " + dc[1]) if dc[1] else ""),
                                                           y.get("ressalva") or "") if t))
                continue
        if d:
            ben = "Indulto" if d is di else "Comutação"
            outro = dc if d is di else di
            x.update(s=d[0], beneficio=ben, mot="%s %s%s (incidente do RSPE)" % (ben, "concedido" if (d[0] == "conc" and ben == "Indulto") else
                                                                               "concedida" if d[0] == "conc" else
                                                                               "indeferido" if ben == "Indulto" else "indeferida",
                                                                               (" em " + d[1]) if d[1] else ""))
            if outro:
                # a outra decisão do mesmo decreto também consta (ex.: comutação concedida e indulto indeferido)
                x["ressalva"] = "%s no RSPE%s" % (
                    ("comutação concedida" if outro[0] == "conc" else "comutação indeferida") if ben == "Indulto" else
                    ("indulto concedido" if outro[0] == "conc" else "indulto indeferido"), (" em " + outro[1]) if outro[1] else "")
    for x in out:
        _remicao_pendente(x, r)
        if not x.get("detalhado"):
            _rem_posterior(x, r)
    _pena_cumprida_aba(out, r)
    _tese_comutacoes_anteriores(out, fx, dec)
    out.sort(key=lambda x: (rs.to_date(x.get("ref") or "") or date.min))
    for x in out:
        x["mot_c"] = motivo_curto(x) if x.get("mot") else ""
    if not completo:
        for x in out:
            for k in ("hips", "falta_ind", "falta_firme", "alc"):
                x.pop(k, None)
    return {"inicio": rs.fmt(ini) if ini else "", "decretos": out}
