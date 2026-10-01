"""Decretos de indulto e comutação de 2000 em diante, num motor só (aba Indulto).

Cada decreto é uma ficha de dados na base jurídica (chave "decretos_fichas"): data de referência, hipóteses de indulto
(pena máxima, fração ou anos cumpridos por reincidência, violência ou grave ameaça, regime), comutação, crimes
impeditivos e janela da falta grave. O motor lê qualquer ficha; corrigir ou acrescentar um decreto é editar a base.
Os decretos de 2022, 2024 e 2025 seguem com a análise detalhada que o programa já fazia (rspe_scraper), e os
benefícios já decididos no RSPE (incidente de indulto ou comutação que cita o decreto) prevalecem sobre o cálculo.

Resultado por decreto: cabe | nao | imp (crime impeditivo) | conc (concedido) | indef (indeferido) |
fora (execução posterior) | ver (falta dado no RSPE: só quando sem ele a conta não fecha)."""
import re
from datetime import date, timedelta
from fractions import Fraction

import rspe_scraper as rs

# análise detalhada já existente no programa (rspe_scraper): o motor só traduz o resultado
DETALHADOS = {"2022": ("11.302", "indulto_2022", None), "2024": ("12.338", "indulto_2024", "comutacao_2024"),
              "2025": ("12.790", "indulto_2025", "comutacao_2025")}
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


def _impeditivos(f, crimes, ref):
    """Crimes da soma que o decreto veda (hediondos e equiparados na data, tortura, terrorismo, tráfico e a lista própria)."""
    I = f.get("impeditivos") or {}
    out = []
    for c in crimes:
        lei, art = rs.num_lei(c.get("lei")), rs.num_art(c.get("artigo"))
        rot = rs.crimes_curto([c])
        if I.get("hediondos_e_equiparados"):
            trafico = lei in ("11343", "6368") and art in ("33", "12", "34", "13", "35", "14", "36", "37")
            priv = trafico and "§ 4" in (c.get("tipo_penal") or "")
            if priv and I.get("trafico_privilegiado_ressalvado"):
                pass
            # hediondez aferida na data do FATO: a hediondez superveniente não alcança o fato anterior (tese da
            # irretroatividade; os decretos falam em "crime hediondo praticado após a edição da Lei 8.072/1990" e das leis que
            # ampliaram o rol). Tráfico: equiparado desde a Lei 8.072/1990 (25/07/1990)
            elif rs.e_hediondo(c, None) or (trafico and not priv and (rs.to_date(c.get("data_infracao") or "") or ref) >= date(1990, 7, 25)):
                fato = rs.to_date(c.get("data_infracao") or "")
                out.append("%s: hediondo ou equiparado na data do fato%s" % (rot, (" (%s)" % rs.fmt(fato)) if fato else ""))
                continue
        for o in I.get("outros") or []:
            arts = [re.sub(r"\D", "", str(a)) for a in (o.get("artigos") or [])]
            leis = rs.num_lei(o.get("lei") or "") if o.get("lei") and not re.search(r"\bCP\b|PENAL", str(o.get("lei")), re.I) else "2848"
            if art and art in arts and (lei == leis or (leis == "2848" and lei in ("", "2848"))):
                out.append("%s: %s" % (rot, o.get("descricao") or "vedado pelo decreto"))
                break
    return list(dict.fromkeys(out))


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
    ref = rs.to_date(f["data_referencia"])
    pub = rs.to_date(f.get("data_publicacao") or "") or ref
    base = {"id": f["id"], "ano": f.get("ano"), "numero": f.get("numero") or "", "ref": rs.fmt(ref), "tipo": f.get("tipo") or "natalino"}
    if ref > hoje:
        return dict(base, s="futuro", mot="data de referência futura")
    if not ini or ini > ref:
        return dict(base, s="fora", mot="execução posterior ao decreto")
    if (f.get("publico") == "mulheres") and (r.get("_sexo") or "") != "F":
        return dict(base, s="fora", mot="decreto só para mulheres" + ("" if r.get("_sexo") else " (sexo não informado)"))
    crimes = [c for c in (r.get("_crimes") or []) if not (c.get("extinto") or "").upper().startswith("S")
              and (rs.to_date(c.get("data_infracao") or "") or date.min) <= ref
              and (rs.to_date(c.get("data_sentenca") or "") or date.min) <= pub]
    if not crimes:
        return dict(base, s="fora", mot="sem condenação até o decreto")
    pena = sum(rs.pena_para_dias(c.get("pena_imposta") or c.get("pena_total_processo")) or 0 for c in crimes)
    cump, _orig = rs.cumprido_na_data(r, ctx["periodos"], ctx["rem"], ref, ctx["lc"])
    reinc = any(c.get("reincidente_comum") == "S" or c.get("reincidente_especifico") == "S" for c in crimes)
    vga = any(rs.vga_indulto(c) for c in crimes)
    detalhe = {"pena": pena, "cumprido": cump, "reincidente": reinc, "vga": vga, "crimes": [rs.crimes_curto([c]) for c in crimes]}
    imp = _impeditivos(f, crimes, ref)
    nota_conc = ""
    if imp:
        # concurso com crime impeditivo: cumprida a fração exigida da pena dele, o benefício alcança os demais crimes, com o
        # tempo excedente imputado a eles
        frc = _regra_concurso(f)
        imp_cr = [c for c in crimes if any(x.startswith(rs.crimes_curto([c]) + ":") for x in imp)]
        resto = [c for c in crimes if c not in imp_cr]
        if frc is not None and resto:
            pena_imp = sum(rs.pena_para_dias(c.get("pena_imposta") or c.get("pena_total_processo")) or 0 for c in imp_cr)
            exig_imp = int(-(-pena_imp * frc.numerator // frc.denominator))
            if cump >= exig_imp:
                nota_conc = "cumpridos %s da pena do crime impeditivo (%s); benefício sobre os demais crimes" % (str(frc) if frc != 1 else "a íntegra", rs.dias_para_pena(exig_imp))
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
    if F.get("meses"):
        # janela contada para trás a partir da publicação (como dizem os decretos), não da data de referência
        ach = rs.indicios_falta(r.get("_incidentes") or [], pub, dias=int(F["meses"]) * 30, eventos=r.get("_eventos") or [], ate=pub, hoje=pub)  # prescrição da falta aferida na data do decreto
        # decreto que exige a falta apurada/homologada (ex.: "falta sem a devida apuração não impede"): a não homologada
        # (fuga só registrada como evento) não impede - fica como ressalva
        hom = F.get("exige_homologacao")
        falta_firme = [t for t, firme in ach if firme and not (hom and "não homologada" in t)]
        falta_ind = [t for t, firme in ach if not firme or (hom and "não homologada" in t)]
    regime = _regime_em(r, ref)
    em_lc = any(a <= ref and (b is None or b >= ref) for a, b in ctx["lc"])
    continuo = next(((ref - a).days + 1 for a, b in rs.uniao_periodos(ctx["periodos"]) if a <= ref and (b is None or b >= ref)), 0)

    def hip_ok(h):
        """(atende, dias exigidos, motivo se não atende)."""
        o = rs._sem_acento(h.get("outros_requisitos") or "").lower()
        if re.search(r"\bmulher|\bcondenadas?\b(?! a)", o) and (r.get("_sexo") or "") != "F":
            return False, None, "hipótese só para mulheres"
        if re.search(r"\bhomens?\b", o) and (r.get("_sexo") or "") == "F":
            return False, None, "hipótese só para homens"
        if re.search(r"trafico privilegiado|33,? ?§ ?4|§ ?4o? do art\.? 33", o + " " + rs._sem_acento(h.get("texto") or "").lower()) and not all(
                rs.num_lei(c.get("lei")) == "11343" and "§ 4" in (c.get("tipo_penal") or "") for c in crimes):
            return False, None, "hipótese só para o tráfico privilegiado"
        rem_mode = "remanescente" in o
        if rem_mode and h.get("pena_max_anos") is None:
            nums = [int(x) for x in re.findall(r"(\d+)\s*anos", o)]
            if nums:
                h = dict(h, pena_max_anos=(nums[1] if (reinc and len(nums) > 1) else nums[0]))
        if h.get("pena_max_anos") is not None and rem_mode and pena - cump > float(h["pena_max_anos"]) * 365:
            return False, None, "pena remanescente de %s acima de %s anos" % (rs.dias_para_pena(pena - cump), h["pena_max_anos"])
        if h.get("pena_max_anos") is not None and not rem_mode and pena > float(h["pena_max_anos"]) * 365:
            return False, None, "pena total de %s acima de %s anos" % (rs.dias_para_pena(pena), h["pena_max_anos"])
        if h.get("pena_min_anos") is not None and pena <= float(h["pena_min_anos"]) * 365:
            return False, None, "pena total não supera %s anos" % h["pena_min_anos"]
        if (h.get("violencia_grave_ameaca") or "") == "vedada" and vga:
            return False, None, "crime com violência ou grave ameaça"
        if (h.get("violencia_grave_ameaca") or "") == "exigida" and not vga:
            return False, None, "hipótese só para crime com violência ou grave ameaça"
        reg = [rs._sem_acento(x).lower() for x in (h.get("regime") or [])]
        if reg and not regime and not any("livramento" in x for x in reg):
            return False, None, "regime em %s não informado no RSPE (hipótese exige %s)" % (rs.fmt(ref), ", ".join(h["regime"]))
        if reg and any("livramento" in x for x in reg) and not em_lc:
            if not any(regime and (x.startswith(regime) or regime in x) for x in reg if "livramento" not in x):
                return False, None, "não estava em livramento condicional em %s" % rs.fmt(ref)
        elif reg and regime and not any(x.startswith(regime) or regime in x for x in reg):
            return False, None, "regime em %s: %s (exigido %s)" % (rs.fmt(ref), regime, ", ".join(h["regime"]))
        fr = _fr(h.get("fracao_reincidente") if reinc else h.get("fracao_nao_reincidente"))
        anos = h.get("anos_reincidente") if reinc else h.get("anos_nao_reincidente")
        exig = None
        if fr is not None:
            exig = int(-(-pena * fr.numerator // fr.denominator))
        elif anos is not None:
            exig = int(float(anos) * 365)
        base_c = cump
        if h.get("ininterrupto") and anos is not None:
            base_c = continuo  # anos ininterruptos: só a custódia contínua até a data (sem remição)
        if exig is not None and base_c < exig:
            if base_c is not cump:
                return False, exig, "faltavam %s de custódia ininterrupta para %s anos em %s" % (_dias_txt(exig - base_c), anos, rs.fmt(ref))
            return False, exig, "faltavam %s para %s em %s" % (_dias_txt(exig - cump), str(fr) if fr is not None else "%s anos" % anos, rs.fmt(ref))
        return True, exig, ""

    ind, ind_n = None, None   # hipótese atendida / a que chegou mais perto
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
    hips = []  # todas as hipóteses calculadas, para a linha do tempo
    for h in f.get("indulto") or []:
        if not h.get("objetivo") or not _decisiva(h):
            continue
        ok, exig, mot = hip_ok(h)
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
        ok, exig, mot = hip_ok(hh)
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
    if falta_firme and "indulto" in (F.get("afeta") or "indulto e comutação"):
        return dict(res, s="nao", mot="falta grave nos %s meses anteriores: %s" % (F.get("meses"), falta_firme[0]))
    if ind and not imp_ind:
        h, exig = ind
        return dict(res, s="cabe", beneficio="Indulto", dispositivo=h.get("dispositivo") or "", exigido=exig,
                    fracao=(h.get("fracao_reincidente") if reinc else h.get("fracao_nao_reincidente")) or "",
                    mot=("cumpriu %s em %s" % (rs.dias_para_pena(cump), rs.fmt(ref))) + (" (exigido %s)" % rs.dias_para_pena(exig) if exig else ""),
                    ressalva=("falta a apurar na janela: %s" % falta_ind[0]) if falta_ind else "")
    if com and not imp_com:
        h, exig = com
        red = h.get("reducao_reincidente") if reinc else h.get("reducao_nao_reincidente")
        return dict(res, s="cabe", beneficio="Comutação", dispositivo=h.get("dispositivo") or "", exigido=exig,
                    fracao=red or "", reducao=red or "",
                    mot="cumpriu %s em %s%s; comutação de %s do remanescente" % (rs.dias_para_pena(cump), rs.fmt(ref),
                                                                            (" (exigido %s)" % rs.dias_para_pena(exig)) if exig else "", red or "?"),
                    ressalva=("falta a apurar na janela: %s" % falta_ind[0]) if falta_ind else "")
    if imp:
        return dict(res, s="imp", mot="; ".join(imp))
    if ind_n and ind_n[2]:
        return dict(res, s="nao", mot=ind_n[2], exigido=ind_n[1], dispositivo=ind_n[0].get("dispositivo") or "")
    if com_n and com_n[2]:
        return dict(res, s="nao", mot=com_n[2], exigido=com_n[1], dispositivo=com_n[0].get("dispositivo") or "")
    if not any(h.get("objetivo") and _decisiva(h) for h in (f.get("indulto") or [])) and not (f.get("comutacao") or []):
        return dict(res, s="nao", mot="decreto restrito (doença, deficiência, agentes de segurança ou outros grupos): nenhuma hipótese pelos dados do RSPE")
    return dict(res, s="nao", mot="nenhuma hipótese objetiva do decreto alcança o caso")


def _detalhado(ano, r):
    num, ki, kc = DETALHADOS[ano]
    ref = rs.DECRETOS.get(ano)
    out = {"id": ano, "ano": int(ano), "numero": num, "ref": rs.fmt(ref) if ref else "25/12/%s" % ano, "tipo": "natalino", "detalhado": True}
    si = MAPA_STATUS.get(r.get(ki + "_status") or "", "")
    sc = MAPA_STATUS.get(r.get((kc or "") + "_status") or "", "") if kc else ""
    ti, tc = r.get(ki) or "", (r.get(kc) or "") if kc else ""
    if si == "cabe" or (not si and ti.upper().startswith("CABE")):
        return dict(out, s="cabe", beneficio="Indulto", mot=ti)
    if sc == "cabe":
        return dict(out, s="cabe", beneficio="Comutação", mot=tc)
    if "ver" in (si, sc):
        return dict(out, s="ver", mot=ti if si == "ver" else tc)
    if si == "imp":
        return dict(out, s="imp", mot=ti)
    if si == "nao" or sc == "nao":
        return dict(out, s="nao", mot=ti or tc)
    return dict(out, s="nao" if (ti or tc) else "fora", mot=ti or tc or "sem análise")


def avaliar(r, hoje, completo=False):
    """Lista de resultados (do decreto mais antigo ao mais novo) para a aba Indulto. completo=True mantém as hipóteses
    calculadas e as faltas da janela (linha do tempo); sem ele, a lista fica leve."""
    ini = inicio_cumprimento(r)
    ctx = _ctx(r)
    dec = decididos(r)
    out = []
    for f in fichas():
        if f["id"] in DETALHADOS:
            continue
        try:
            x = avaliar_ficha(f, r, ctx, ini, hoje)
        except Exception as e:  # uma ficha com dado ruim não derruba o assistido
            x = {"id": f["id"], "ano": f.get("ano"), "numero": f.get("numero") or "", "ref": f.get("data_referencia"), "s": "ver",
                 "mot": "falha ao avaliar o decreto: %s" % e}
        out.append(x)
    for ano in DETALHADOS:
        ref = rs.DECRETOS.get(ano)
        if ref and ref <= hoje:
            x = _detalhado(ano, r) if (ini and ini <= ref) else {"id": ano, "ano": int(ano), "numero": DETALHADOS[ano][0], "ref": rs.fmt(ref),
                                                                  "s": "fora", "mot": "execução posterior ao decreto", "detalhado": True}
            out.append(x)
    for x in out:
        ano = str(x.get("ano") or "")
        if x.get("s") in ("fora", "futuro"):
            continue
        d = dec.get((ano, "indulto")) or dec.get((ano, "comutacao"))
        if d and (not x.get("tipo") == "dia_das_maes"):
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
