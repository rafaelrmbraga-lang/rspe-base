# -*- coding: utf-8 -*-
"""
Prescrição, crime a crime, a partir dos dados do RSPE (arts. 109 a 119 do CP).

Pretensão punitiva (retroativa e intercorrente) - art. 110, § 1º:
  prazo pela pena aplicada (art. 109), reduzido de metade se < 21 anos no fato ou > 70 na
  sentença (art. 115); intervalos: fato-denúncia (só para fatos anteriores a 05/05/2010,
  Lei 12.234/2010), denúncia-sentença e sentença-trânsito. O acórdão confirmatório também
  interrompe (art. 117, IV; STF HC 176.473), mas o RSPE não traz sua data - anotado.
Pretensão executória - art. 110, caput:
  prazo pela pena aplicada, +1/3 se reincidente, metade pelo art. 115; termo inicial no
  trânsito em julgado para ambas as partes (STF, Tema 788), ou para a acusação (art. 112, I)
  quando esse trânsito é anterior a 12/11/2020 (modulação); interrompe-se pelo início ou
  continuação do cumprimento (art. 117, V) e não corre enquanto preso (art. 116, p. único);
  na evasão ou revogação do livramento, regula-se pelo tempo restante da pena (art. 113).
Penas mais leves prescrevem com as mais graves (art. 118); cada crime isoladamente (art. 119).
"""

from datetime import date, timedelta
from fractions import Fraction

import rspe_scraper as rs
import rspe_regras as rg


def prazo_base_anos(pena_dias):
    """Art. 109 pela pena (aplicada), em anos (tabela da base jurídica)."""
    return rg.prazo_art109_anos(pena_dias)


def periodos_cumprimento(r, hoje):
    """Períodos em que a pena esteve em cumprimento (custódia, regime aberto, livramento condicional):
    a prescrição executória não corre nesses períodos (arts. 116, p. ú., e 117, V, CP).
    Devolve (periodos, avisos)."""
    avisos = []
    eventos = r.get("_eventos", [])
    incidentes = r.get("_incidentes", [])
    per = list(rs.periodos_custodia(eventos))
    # livramento condicional concedido conta como cumprimento (período de prova) até revogação
    for i in incidentes:
        if i.get("situacao") == "CONCEDIDO" and rs.e_incidente_livramento(i):
            ini = rs.to_date(i.get("data_referencia") or i.get("data_decisao") or i.get("complemento") or "")
            if not ini:
                continue
            fim = None
            for j in incidentes:
                if "REVOG" in ((j.get("tipo") or "") + " " + (j.get("complemento") or "")).upper():
                    dj = rs.to_date(j.get("data_referencia") or j.get("data_decisao") or "")
                    if dj and dj > ini and (fim is None or dj < fim):
                        fim = dj
            per.append((ini, fim))
    # RSPE diz "em cumprimento" (último evento não é interrupção) mas não há período aberto: abre a partir da última alteração de regime
    em_cumpr = "INTERROMPIDA" not in (r.get("situacao_cumprimento") or "")
    if em_cumpr and not any(f is None for _, f in per):
        datas = [rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "") for i in incidentes if "REGIME" in (i.get("tipo") or "").upper()]
        datas = [x for x in datas if x]
        ini = max(datas) if datas else None
        if ini:
            per.append((ini, None))
            avisos.append("cumprimento em curso inferido a partir de %s (última alteração de regime); RSPE sem evento de início correspondente" % rs.fmt(ini))
    # normaliza e funde sobreposições
    per = sorted([(a, b) for a, b in per if a], key=lambda x: x[0])
    fund = []
    for a, b in per:
        if fund and (fund[-1][1] is None or a <= fund[-1][1]):
            pa, pb = fund[-1]
            fund[-1] = (pa, None if (pb is None or b is None) else max(pb, b))
        else:
            fund.append((a, b))
    return fund, avisos


def soma_meses(d, meses):
    meses = int(meses)
    y, m = divmod(d.month - 1 + meses, 12)
    y += d.year
    m += 1
    dia = min(d.day, [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    return date(y, m, dia)


def fmt_prazo(meses):
    if int(meses) <= 0:
        return "0 meses"
    a, m = divmod(int(meses), 12)
    return ("%d ano%s" % (a, "s" if a != 1 else "") if a else "") + (" e " if a and m else "") + ("%d mes%s" % (m, "es" if m != 1 else "") if m else "")


def _idade(nasc, ref):
    if not nasc or not ref:
        return None
    return ref.year - nasc.year - ((ref.month, ref.day) < (nasc.month, nasc.day))


def _pena_processo(r, c):
    """Soma das penas dos crimes ativos da mesma condenação (processo criminal) do crime c."""
    proc = c.get("processo_criminal") or ""
    mesmos = [x for x in r.get("_crimes", []) if (x.get("processo_criminal") or "") == proc and not (x.get("extinto") or "").upper().startswith("S")] if proc else [c]
    return sum(rs.pena_para_dias(x.get("pena_imposta")) or 0 for x in mesmos)


def _custodia_previa(periodos_det, proc, termo):
    """Dias de custódia anteriores ao termo inicial ligados a este processo (ou sem processo indicado): detração."""
    total = 0
    for a, b, motivo, procs in periodos_det:
        if procs and proc not in procs:
            continue
        f = min(b or termo, termo)
        if a < f:
            total += (f - a).days
    return total


def _gaps_sem_custodia(inicio, fim, periodos):
    """Trechos entre inicio e fim em que não há custódia. Devolve [(g0, g1)]."""
    ps = sorted([(a, b or fim) for a, b in periodos if (b or fim) > inicio])
    gaps, cursor = [], inicio
    for a, b in ps:
        if a > cursor:
            gaps.append((cursor, min(a, fim)))
        cursor = max(cursor, b)
        if cursor >= fim:
            break
    if cursor < fim:
        gaps.append((cursor, fim))
    return [(a, b) for a, b in gaps if b > a]


def analisar(r, hoje=None):
    """r = registro extraído (rspe_scraper.extrair). Devolve dict com linhas por crime e resumo."""
    hoje = hoje or date.today()
    nasc = rs.to_date(r.get("data_nascimento") or "")
    pena_total = rs.pena_para_dias(r.get("pena_total")) or 0
    eventos = r.get("_eventos", [])
    incidentes = r.get("_incidentes", [])
    periodos, avisos_gerais = periodos_cumprimento(r, hoje)
    periodos_det = rs.periodos_custodia_detalhe(eventos)
    remicoes = []
    for i in incidentes:
        if "REMI" in (i.get("tipo") or "").upper():
            m = rs.re.search(r"(\d+)\s*Dia", i.get("complemento", ""), rs.re.I)
            if m:
                remicoes.append((rs.to_date(i.get("data_referencia") or i.get("data_decisao") or ""), int(m.group(1))))
    em_custodia = any(a <= hoje and (b is None or b > hoje) for a, b in periodos)
    inicio_def = [rs.to_date(e.get("data", "")) for e in eventos
                  if rs.re.search(r"DEFINITIV|CUMPRIMENTO", (e.get("motivo") or "") + " " + (e.get("tipo") or ""), rs.re.I)
                  and "INTERRUP" not in (e.get("tipo") or "").upper()]
    inicio_def = sorted(x for x in inicio_def if x)
    menor21, maior70, arts_sexuais = rg.art115()
    LEI_12234 = rg.data_lei_12234()
    TEMA_788 = rg.data_tema_788()
    ACRESC = rg.acrescimo_reincidencia()
    cumprido_hoje = rs.dias_cumpridos_ate(periodos, remicoes, hoje)
    pena_cumprida_toda = pena_total and cumprido_hoje >= pena_total

    linhas = []
    for c in r.get("_crimes", []):
        if c.get("extinto", "").upper().startswith("S"):
            continue  # só crimes ativos
        L = {
            "crime": rs.crimes_curto([c]),
            "descricao": c.get("tipo_penal", ""),
            "proc_crim": c.get("processo_criminal", ""),
            "fato": c.get("data_infracao", ""),
            "denuncia": c.get("data_denuncia", ""),
            "sentenca": c.get("data_sentenca", ""),
            "transito_mp": c.get("transito_mp", ""),
            "transito": c.get("transito_processo", ""),
            "pena": rs.pena_extenso(rs.pena_curta(c.get("pena_imposta") or c.get("pena_total_processo"))),
            "reinc": c.get("reincidente_comum") == "S" or c.get("reincidente_especifico") == "S",
            "avisos": list(avisos_gerais),
        }
        pena = rs.pena_para_dias(c.get("pena_imposta") or c.get("pena_total_processo"))
        if "CONVERTIDA" in (c.get("pena_total_processo") or "").upper():
            L["avisos"].append("pena originalmente substituída por restritiva de direitos (CONVERTIDA): o período de cumprimento da PRD não consta no RSPE e também suspende/interrompe a executória - conferir")
        fato, den, sent = (rs.to_date(x or "") for x in (L["fato"], L["denuncia"], L["sentenca"]))
        tmp, tpr = rs.to_date(L["transito_mp"] or ""), rs.to_date(L["transito"] or "")
        extinto = c.get("extinto", "").upper().startswith("S")

        # art. 115
        meia = False
        art_cp = rs.num_art(c.get("artigo"))
        sexual = (rs.num_lei(c.get("lei")) in ("2848", "") and art_cp in arts_sexuais)
        if nasc:
            i_fato, i_sent = _idade(nasc, fato), _idade(nasc, sent)
            if i_fato is not None and i_fato < menor21:
                meia = True
                L["avisos"].append("art. 115: menor de %d anos na data do fato (%d anos) - prazos pela metade" % (menor21, i_fato))
            if i_sent is not None and i_sent > maior70:
                meia = True
                L["avisos"].append("art. 115: maior de %d anos na sentença (%d anos) - prazos pela metade" % (maior70, i_sent))
            if meia and sexual:
                LEI_15160 = rg.data_lei_15160()
                if fato and LEI_15160 and fato < LEI_15160:
                    L["avisos"].append("art. 115 mantido: a exceção de violência sexual contra a mulher (Lei 15.160/2025) só alcança fatos a partir de %s (irretroatividade da lei mais gravosa)" % rs.fmt(LEI_15160))
                else:
                    meia = False
                    L["avisos"].append("art. 115 NÃO aplicado: exceção de violência sexual contra a mulher (Lei 15.160/2025, art. %s) - conferir a vítima" % art_cp)
        else:
            L["avisos"].append("sem data de nascimento: art. 115 não aferido")
        L["art115"] = meia

        if not pena:
            L.update(retro_status="sem pena no RSPE", retro_cor="cinza", ppe_status="sem pena no RSPE", ppe_cor="cinza",
                     prazo_ppp="", prazo_ppe="", ppe_termo="", ppe_previsao="", retro_detalhe="", ppe_detalhe="")
            linhas.append(L)
            continue
        if extinto:
            _mot = (c.get("extincao_motivo") or "").strip()
            _dt = c.get("data_extincao") or ""
            _txt = "Extinta" + ((" · " + _mot.lower()) if _mot else "") + ((" em " + _dt) if _dt else "")
            L.update(retro_status=_txt, retro_cor="cinza", ppe_status=_txt, ppe_cor="cinza",
                     prazo_ppp="", prazo_ppe="", ppe_termo="", ppe_previsao="",
                     retro_detalhe="Punibilidade já extinta segundo o RSPE" + ((" (" + c["extincao_fonte"] + ")") if c.get("extincao_fonte") else "") + ".", ppe_detalhe="")
            linhas.append(L)
            continue

        base_meses = prazo_base_anos(pena) * 12
        # ---------------- pretensão punitiva (retroativa / intercorrente) ----------------
        ppp_meses = Fraction(base_meses) * (Fraction(1, 2) if meia else 1)
        L["prazo_ppp"] = fmt_prazo(ppp_meses)
        intervalos = []
        if fato and den and fato < LEI_12234:
            intervalos.append(("fato → denúncia", fato, den))
        if den and sent:
            intervalos.append(("denúncia → sentença", den, sent))
        transito_inferido = None  # o programa não presume datas: sem trânsito no RSPE, verificar na ação penal
        if sent and (tpr or tmp):
            intervalos.append(("sentença → trânsito", sent, tmp or tpr))
        det = []
        pior = None
        for nome, a, b in intervalos:
            limite = soma_meses(a, ppp_meses)
            ok = b >= limite
            det.append("%s%s: %s a %s = %s (prazo %s, vence %s)" % ("✘ " if ok else "✔ ", nome, rs.fmt(a), rs.fmt(b), fmt_prazo(_meses(a, b)), L["prazo_ppp"], rs.fmt(limite)))
            if ok and (pior is None or True):
                pior = nome
        faltando = [n for n, v in (("data do fato", fato), ("recebimento da denúncia", den), ("sentença", sent), ("trânsito em julgado", tpr or tmp)) if not v]
        if faltando:
            L["avisos"].append("não consta no RSPE: %s - verificar na ação penal (o programa não presume datas)" % ", ".join(faltando))
            det.append("Não consta no RSPE: %s. Verificar na ação penal; nenhuma data foi presumida." % ", ".join(faltando))
        if pior:
            L["retro_status"] = "Prescrição da pretensão punitiva aparente (%s)" % pior
            L["retro_cor"] = "vermelho"
        elif not intervalos or faltando:
            L["retro_status"] = "Verificar na ação penal: falta " + ", ".join(faltando) if faltando else "Verificar na ação penal"
            L["retro_cor"] = "cinza"
        else:
            L["retro_status"] = "não configurada"
            L["retro_cor"] = ""
        if sent and (tpr or tmp) and (tpr or tmp) > sent:
            det.append("Obs.: eventual acórdão confirmatório entre a sentença e o trânsito interrompe o prazo (art. 117, IV; STF HC 176.473) - data não consta no RSPE.")
        if tmp and tpr and tmp != tpr:
            det.append("Trânsito para a acusação em %s; para o processo em %s. A retroativa exige trânsito para a acusação (art. 110, § 1º)." % (rs.fmt(tmp), rs.fmt(tpr)))
        L["retro_detalhe"] = "\n".join(det)

        # ---------------- pretensão executória ----------------
        fator = (1 + ACRESC) if L["reinc"] else Fraction(1)
        if meia:
            fator *= Fraction(1, 2)
        ppe_meses = Fraction(base_meses) * fator
        L["prazo_ppe"] = fmt_prazo(ppe_meses) + (" (+1/3 reincidência)" if L["reinc"] else "") + (" (½ art. 115)" if meia else "")
        if tmp and tmp <= TEMA_788:
            termo, termo_txt = tmp, "trânsito para a acusação %s (art. 112, I; modulação do Tema 788)" % rs.fmt(tmp)
        elif tpr:
            termo, termo_txt = tpr, "trânsito para ambas as partes %s (STF, Tema 788)" % rs.fmt(tpr)
        elif tmp:
            termo, termo_txt = tmp, "trânsito para a acusação %s (trânsito do processo não informado)" % rs.fmt(tmp)
        elif transito_inferido:
            termo, termo_txt = transito_inferido, "início do cumprimento %s (trânsito não informado; data usada como limite)" % rs.fmt(transito_inferido)
        else:
            termo, termo_txt = None, ""
        L["ppe_termo"] = rs.fmt(termo) if termo else ""
        L["ppe_previsao"] = ""
        L["ppe_dias"] = None
        det = []
        if not termo:
            L["ppe_status"] = "Verificar na ação penal: trânsito em julgado não consta no RSPE"
            L["ppe_cor"] = "cinza"
            det.append("Sem data de trânsito no RSPE: verificar na ação penal. Se a execução for provisória, a prescrição executória ainda não corre.")
        elif pena_cumprida_toda:
            L["ppe_status"] = "pena cumprida"
            L["ppe_cor"] = "cinza"
        elif pena and _pena_processo(r, c) and _custodia_previa(periodos_det, c.get("processo_criminal") or "", termo) >= _pena_processo(r, c):
            # a detração abate a pena do PROCESSO (todos os crimes da mesma condenação), não a de um crime isolado
            _cp = _custodia_previa(periodos_det, c.get("processo_criminal") or "", termo)
            _pp = _pena_processo(r, c)
            L["ppe_status"] = "Pena cumprida por detração (custódia provisória de %s ≥ pena do processo)" % rs.dias_para_pena(_cp)
            L["ppe_cor"] = "vermelho"
            L["ppe_detalhe"] = ("Custódia anterior ao trânsito (%s) igual ou superior à pena de todo o processo %s (%s): a pena está integralmente cumprida por detração "
                                "(CP, art. 42) e cabe extinção pelo cumprimento (LEP, art. 66, II); a prescrição executória não se coloca." % (
                                    rs.dias_para_pena(_cp), c.get("processo_criminal") or "", rs.dias_para_pena(_pp)))
            linhas.append(L)
            continue
        else:
            det.append("Termo inicial: " + termo_txt + ". Prazo: " + L["prazo_ppe"] + ".")
            # custódia provisória (flagrante/preventiva/temporária) de OUTRO processo, sem menção a este,
            # não é "início ou continuação do cumprimento" desta pena (art. 117, V): não interrompe a executória
            periodos_crime, suspensoes = [], []
            proc_x = c.get("processo_criminal") or ""
            for (a, b, motivo, procs) in periodos_det:
                provisoria = rs.re.search(r"FLAGRANTE|PREVENTIV|TEMPOR|PROVIS", motivo or "", rs.re.I) is not None
                de_outro = bool(procs) and proc_x not in procs
                if provisoria and de_outro and (b or hoje) > termo:
                    # não é cumprimento desta pena (não interrompe - art. 117, V), mas preso por outro motivo a prescrição
                    # executória não corre (art. 116, p. único): o prazo fica suspenso nesse período
                    det.append("Custódia de %s a %s (%s, processo %s): preso por outro motivo - a prescrição fica suspensa nesse período (art. 116, p. único), sem interromper." % (
                        rs.fmt(a), rs.fmt(b) if b else "hoje", (motivo or "").lower(), procs))
                    suspensoes.append((a, b or hoje))
                    continue
                periodos_crime.append((a, b))
            periodos_crime += [pp for pp in periodos if pp not in [(a, b) for a, b, _, _ in periodos_det]]  # livramento/inferidos
            gaps = _gaps_sem_custodia(termo, hoje, periodos_crime)
            prescrita = None
            correndo = None
            if not gaps:
                det.append("Em cumprimento (custódia, regime aberto ou livramento) desde o trânsito: a prescrição não corre (arts. 116, p. único, e 117, V).")
            # só o cumprimento posterior ao termo inicial reduz a pena-base do prazo (art. 113); a prisão provisória
            # anterior ao trânsito é detração, que não altera o prazo prescricional (STJ)
            periodos_exec = [(max(a, termo), b) for a, b in periodos_crime if (b or hoje) > termo]
            for g0, g1 in gaps:
                cumprido_g0 = rs.dias_cumpridos_ate(periodos_exec, remicoes, g0)
                if cumprido_g0 > 0:
                    rem = max(0, pena - cumprido_g0) if not pena_total or pena_total < pena else max(0, min(pena, pena_total - cumprido_g0))
                    meses = Fraction(prazo_base_anos(max(rem, 1)) * 12) * fator
                    base_txt = "pena restante %s em %s, contada da última interrupção do cumprimento (arts. 112, II, 113 e 117, V)" % (rs.dias_para_pena(rem), rs.fmt(g0))
                else:
                    meses = ppe_meses
                    base_txt = "pena integral %s (nunca iniciou o cumprimento)" % L["pena"]
                limite = soma_meses(g0, meses)
                # suspensão (art. 116, p. único): os dias preso por outro motivo não contam no prazo
                susp_d = 0
                for s0, s1 in sorted(suspensoes):
                    if s0 >= limite or s1 <= g0:
                        continue
                    dias_s = (min(s1, g1) - max(s0, g0)).days
                    if dias_s > 0:
                        susp_d += dias_s
                        limite = limite + timedelta(days=dias_s)
                if susp_d and susp_d >= (g1 - g0).days - 1:
                    det.append("✔ De %s a %s preso por outro motivo: a prescrição executória não corre (art. 116, p. único)." % (rs.fmt(g0), "hoje" if g1 >= hoje else rs.fmt(g1)))
                    continue
                if susp_d:
                    base_txt += "; %d dia(s) de suspensão por prisão por outro motivo (art. 116, p. único)" % susp_d
                aberto = g1 >= hoje and not em_custodia
                if limite <= g1:
                    prescrita = (g0, limite, base_txt, meses)
                    det.append("✘ Sem custódia de %s a %s: prazo de %s pela %s venceu em %s." % (
                        rs.fmt(g0), "hoje" if aberto else rs.fmt(g1), fmt_prazo(meses), base_txt, rs.fmt(limite)))
                    break
                elif aberto:
                    correndo = (g0, limite, base_txt, meses)
                    det.append("… Corre desde %s (%s): prazo de %s, prescreve em %s." % (rs.fmt(g0), base_txt, fmt_prazo(meses), rs.fmt(limite)))
                else:
                    det.append("✔ Sem custódia de %s a %s (%s): prazo de %s não se completou (venceria em %s); retomada do cumprimento interrompeu (art. 117, V)." % (
                        rs.fmt(g0), rs.fmt(g1), base_txt, fmt_prazo(meses), rs.fmt(limite)))
            if prescrita:
                L["ppe_status"] = "Prescrição executória aparente em %s" % rs.fmt(prescrita[1])
                L["ppe_cor"] = "vermelho"
                L["ppe_previsao"] = rs.fmt(prescrita[1])
                L["ppe_dias"] = (prescrita[1] - hoje).days
            elif correndo:
                # prazo correndo: só interessa quando a prescrição se consumar (não é exibido como alerta)
                L["ppe_status"] = "Não prescrita"
                L["ppe_cor"] = ""
                L["ppe_correndo_ate"] = rs.fmt(correndo[1])
            else:
                L["ppe_status"] = "Não corre (em cumprimento)"
                L["ppe_cor"] = ""
            if L["reinc"]:
                det.append("Reincidência do RSPE aplicada (+1/3, art. 110, caput). Nova condenação posterior também interrompe (art. 117, VI) - não aferível.")
        L["ppe_detalhe"] = "\n".join(det)
        linhas.append(L)

    # resumo por sentenciado
    cores = [l.get("retro_cor", "") for l in linhas] + [l.get("ppe_cor", "") for l in linhas]
    if "vermelho" in cores:
        cor = "vermelho"
    elif linhas and all(c in ("cinza",) for c in cores):
        cor = "cinza"
    else:
        cor = ""
    previsoes = [l["ppe_previsao"] for l in linhas if l.get("ppe_previsao")]
    prox = min(previsoes, key=lambda s: rs.to_date(s) or date.max) if previsoes else ""
    retro = [l for l in linhas if l.get("retro_cor") == "vermelho"]
    ppe_red = [l for l in linhas if l.get("ppe_cor") == "vermelho"]
    ppe_amb = [l for l in linhas if l.get("ppe_cor") == "amarelo"]
    resumo_retro = ("Aparente: " + "; ".join(l["crime"] for l in retro)) if retro else ("não configurada" if linhas else "")
    if ppe_red:
        resumo_ppe = "Aparente: " + "; ".join("%s (%s)" % (l["crime"], l["ppe_previsao"]) for l in ppe_red)
    elif linhas:
        resumo_ppe = "Não prescrita" if any(l.get("ppe_cor") != "cinza" for l in linhas) else "; ".join(sorted(set(l["ppe_status"] for l in linhas)))
    else:
        resumo_ppe = ""
    dias = [l["ppe_dias"] for l in linhas if l.get("ppe_dias") is not None]
    return {
        "presc_linhas": linhas,
        "presc_cor": cor,
        "presc_retro": resumo_retro,
        "presc_ppe": resumo_ppe,
        "presc_prox": prox,
        "presc_dias": min(dias) if dias else None,
        "presc_obs": "; ".join(sorted(set(a for l in linhas for a in l["avisos"]))),
    }


def _meses(a, b):
    m = (b.year - a.year) * 12 + (b.month - a.month)
    if b.day < a.day:
        m -= 1
    return m
