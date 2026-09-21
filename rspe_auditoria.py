# -*- coding: utf-8 -*-
"""
Auditoria do RSPE: confronta os dados que o SEEU imprimiu com a legislação e a
jurisprudência da base jurídica (base_juridica.json) e com a coerência interna
do próprio relatório. Não afirma erro: aponta o que "demanda atenção" e o que
deve ser verificado, sempre com o fundamento.

Níveis: 'alerta' (inconsistência objetiva), 'verificar' (depende de dado que o
RSPE não traz) e 'ok' (conferido sem ressalva).
"""

import re
from datetime import date
from fractions import Fraction

import rspe_scraper as rs
import rspe_regras as rg
import rspe_prescricao as rp


def _item(nivel, titulo, detalhe, fundamento=""):
    return {"nivel": nivel, "titulo": titulo, "detalhe": detalhe, "fundamento": fundamento}


def _fr_seeu(txt):
    f = rs.parse_fracao(txt or "")
    return f


def _hediondo_seeu(c):
    return "HEDIONDO" in ((c.get("fracao_progressao") or "") + (c.get("fracao_livramento") or "")).upper()


def _e_hediondo_lei(c):
    """Hediondez pela lei (base jurídica), independente do rótulo do SEEU, respeitada a lei da época do fato."""
    if rs.hediondo_na_epoca(c) is False:
        d, lei = rs.hediondo_desde(c)
        return False, "fato anterior à %s (vigência %s): não era hediondo à época" % (lei or "lei", rs.fmt(d))
    h = rg.hediondos()
    lei, art = rs.num_lei(c.get("lei")), rs.num_art(c.get("artigo"))
    if not art:
        return None, "artigo não informado no RSPE"
    cp = lei in ("2848", "") or ("PENAL" in (c.get("lei") or "").upper() and "MILITAR" not in (c.get("lei") or "").upper())
    if cp:
        if art in h.get("lei_8072_art1_cp_sempre", []):
            return True, ""
        if art in h.get("lei_8072_art1_cp_condicional", {}):
            hc = rs.hediondo_condicional(c)
            if hc is None:
                return None, h["lei_8072_art1_cp_condicional"][art]
            return hc, ""
        return False, ""
    eq = h.get("equiparados", {})
    if lei in eq and art in eq[lei]:
        if lei == "11343" and art == "33" and "§ 4" in (c.get("tipo_penal") or ""):
            return False, "tráfico privilegiado (art. 33, § 4º) não é hediondo (LEP, art. 112, § 5º)"
        return True, ""
    pu = h.get("paragrafo_unico", {})
    if lei in pu:
        regra = pu[lei]
        if isinstance(regra, dict):
            if art in regra:
                return (True, "") if regra[art] == "sempre" else (None, "art. 1º, p. ú., Lei 8.072/90: " + regra[art])
        elif art in regra:
            return True, ""
    return False, ""


def _agrupar_por_crime(itens):
    """Mesmo ponto repetido em vários crimes ('art. 180 CP: X', 'art. 330 CP: X') vira uma linha só: 'X (art. 180 CP; art. 330 CP)'."""
    grupos, ordem = {}, []
    for it in itens:
        m = re.match(r"^(art\. [^:]+|[^:]{1,40}(?:CP|/\d{2})): (.+)$", it["titulo"])
        chave = (it["nivel"], m.group(2), it.get("fundamento", "")) if m else None
        if chave is None:
            ordem.append(it)
            continue
        if chave not in grupos:
            grupos[chave] = {"base": dict(it), "crimes": [], "detalhes": []}
            ordem.append(grupos[chave]["base"])
        g = grupos[chave]
        g["crimes"].append(m.group(1))
        if it["detalhe"] not in g["detalhes"]:
            g["detalhes"].append(it["detalhe"])
    for (nivel, sufixo, _), g in grupos.items():
        b = g["base"]
        if len(g["crimes"]) > 1:
            b["titulo"] = "%s%s (%s)" % (sufixo[0].upper(), sufixo[1:], "; ".join(g["crimes"]))
            b["detalhe"] = " | ".join(g["detalhes"])
    return ordem


FUND_127 = ("LEP, art. 127 (até 1/3; a contagem recomeça da data da infração); STJ, HC 398.850/SP e HC 293.475/SP; "
            "TJMS, AgExec 0046207-54.2017.8.12.0001 e 0000687-22.2014.8.12.0019.")


def perdas_por_falta(incidentes):
    """Para cada falta grave homologada no RSPE com perda de dias remidos: a perda, as parcelas e a remição
    sobre a qual cada parcela incidiu (parcela = 1/3 da remição, arredondado), a falta anterior e a janela de
    remição entre a falta anterior e a atual (LEP, art. 127: a contagem recomeça da data da infração)."""
    def dt(i):
        return rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "")
    def qtd(i):
        m = rs.re.search(r"(\d+)", i.get("complemento") or "")
        return int(m.group(1)) if m else 0
    faltas = sorted(set(d for d in (dt(i) for i in incidentes if "FALTA GRAVE" in (i.get("tipo") or "").upper() and i.get("situacao") == "CONCEDIDO") if d))
    perdas = [(dt(i), qtd(i)) for i in incidentes if "PERDIDOS" in (i.get("tipo") or "").upper()]
    remicoes = []
    for i in incidentes:
        t = (i.get("tipo") or "").upper()
        if "REMI" in t and "PERDIDOS" not in t and i.get("situacao") == "CONCEDIDO":
            m = rs.re.search(r"(\d+)\s*Dia", i.get("complemento", ""), rs.re.I)
            if m:
                remicoes.append({"d": dt(i), "data": i.get("data_decisao") or i.get("data_referencia") or "", "n": int(m.group(1))})
    out = []
    resid = {id(x): x["n"] for x in remicoes}  # saldo de cada remição depois das perdas anteriores
    for k, f in enumerate(faltas):
        prox = faltas[k + 1] if k + 1 < len(faltas) else None
        prev = faltas[k - 1] if k else None
        pf = sorted([q for d, q in perdas if d and d >= f and (prox is None or d < prox)], reverse=True)
        if not pf:
            continue
        usadas, parcelas = set(), []
        def bate(q, n):
            return n > 0 and q in (n // 3, -(-n // 3), round(n / 3))
        for q in pf:
            cand = [x for x in remicoes if id(x) not in usadas and (bate(q, x["n"]) or bate(q, resid[id(x)]))]
            cand.sort(key=lambda x: (x["d"] is None or x["d"] > f, -(x["d"] or date.min).toordinal()))
            rem = cand[0] if cand else None
            if rem:
                usadas.add(id(rem))
            parcelas.append((q, rem))
        for q, rem in parcelas:
            if rem:
                resid[id(rem)] = max(0, resid[id(rem)] - q)
        janela = sum(x["n"] for x in remicoes if x["d"] and x["d"] <= f and (prev is None or x["d"] > prev))
        out.append({"falta": f, "prev": prev, "perda": sum(pf), "parcelas": parcelas, "janela": janela,
                    "remido_ate": sum(x["n"] for x in remicoes if x["d"] and x["d"] <= f)})
    return out, faltas, perdas


def _perda_remidos(incidentes, perdidos):
    """LEP, art. 127: a falta grave permite revogar ATÉ 1/3 do tempo remido, e a contagem recomeça da data da
    infração - nova falta só alcança a remição adquirida depois da falta anterior (vedado o desconto em duplicidade)."""
    res, faltas, perdas = perdas_por_falta(incidentes)
    if not faltas or not perdas:
        return [_item("verificar", "Perda de %d dias remidos sem falta grave datada no RSPE" % perdidos,
                      "O saldo registra dias perdidos, mas não há incidente de homologação de falta grave com data: conferir a decisão e o PAD.",
                      "LEP, art. 127.")]
    itens = []
    for x in res:
        f, prev = x["falta"], x["prev"]
        dup = [(q, rem) for q, rem in x["parcelas"] if prev and rem and rem["d"] and rem["d"] <= prev]
        if dup:
            itens.append(_item("alerta", "Perda de dias remidos em duplicidade (falta de %s)" % rs.fmt(f),
                               "A perda de %d dias pela falta de %s incidiu sobre remição anterior à falta de %s: %s. A contagem recomeçou em %s; "
                               "a nova perda só pode alcançar a remição adquirida entre as duas faltas (%d dias; limite de 1/3: %d). Cabe impugnar o cálculo." % (
                                   x["perda"], rs.fmt(f), rs.fmt(prev),
                                   "; ".join("%d dias sobre a remição de %d dias de %s" % (q, rem["n"], rem["data"]) for q, rem in dup),
                                   rs.fmt(prev), x["janela"], x["janela"] // 3), FUND_127))
        base = x["janela"]
        limite = base // 3
        if base and x["perda"] > limite:
            itens.append(_item("alerta", "Perda de dias remidos acima de 1/3 (falta de %s)" % rs.fmt(f),
                               "Remição %s: %d dias; limite de 1/3: %d dias; perdidos: %d (excesso de %d dia(s)).%s" % (
                                   ("adquirida entre a falta de %s e esta" % rs.fmt(prev)) if prev else "até a falta",
                                   base, limite, x["perda"], x["perda"] - limite,
                                   " Parcelas: %s - o arredondamento para cima de cada parcela ultrapassa o teto legal." % ", ".join(
                                       "%d (sobre %s)" % (q, rem["n"] if rem else "?") for q, rem in x["parcelas"]) if (len(x["parcelas"]) > 1 and not dup) else ""),
                               FUND_127 + " STF, RE 638.239."))
        elif not dup:
            itens.append(_item("info", "Perda de %d dias remidos pela falta grave de %s" % (x["perda"], rs.fmt(f)),
                               "Dentro do limite de 1/3 (remição %s: %d dias)." % (("entre a falta de %s e esta" % rs.fmt(prev)) if prev else "até a falta", base), "LEP, art. 127."))
    return itens


def auditar(r, hoje=None):
    hoje = hoje or date.today()
    itens = []
    crimes = r.get("_crimes", [])
    ativos = [c for c in crimes if not c.get("extinto", "").upper().startswith("S")]
    incidentes = r.get("_incidentes", [])
    eventos = r.get("_eventos", [])
    nasc = rs.to_date(r.get("data_nascimento") or "")
    pena_total = rs.pena_para_dias(r.get("pena_total"))
    cumprida = rs.pena_para_dias(r.get("pena_cumprida"))
    reman = rs.pena_para_dias(r.get("pena_remanescente"))

    faltam = rs.campos_faltantes(r)
    if faltam:
        itens.append(_item("verificar", "Dados ausentes no RSPE: %s" % ", ".join(faltam),
                           "O SEEU não imprimiu esses dados (guia sem cálculo, pena interrompida) ou o programa não conseguiu lê-los. Os cálculos deste assistido podem ficar incompletos; conferir o PDF.",
                           ""))
    # ---------------- 0. extinções registradas em incidentes / cabeçalho ----------------
    if r.get("execucao_extinta"):
        itens.append(_item("alerta", "Execução extinta segundo incidente do RSPE (%s)" % r["execucao_extinta"],
                           "Há incidente de EXTINÇÃO sem processo selecionado: alcança a execução. Conferir se a guia deve ser baixada/arquivada.", "LEP, arts. 66, II, e 109; CP, art. 107."))
    for c in r.get("_crimes", []):
        if c.get("extincao_fonte") and not (c.get("extinto_rspe") or "").upper().startswith("S"):
            itens.append(_item("info", "%s: extinção registrada (%s), mas a linha do crime diz \"Extinto: %s\"" % (
                rs.crimes_curto([c]), c["extincao_fonte"], c.get("extinto_rspe") or "?"),
                "O programa tratou o crime como extinto (não entra na soma das penas, nas frações nem na prescrição). Conferir se o SEEU precisa ser atualizado.",
                "LEP, art. 66, II; CP, art. 107."))
    if not pena_total and ativos:
        soma_at = sum(rs.pena_para_dias(c.get("pena_imposta")) or 0 for c in ativos)
        itens.append(_item("alerta", "Guia sem pena calculada: pena total %s com %d condenação(ões) ativa(s)" % (r.get("pena_total") or "em branco", len(ativos)),
                           "As condenações ativas somam %s%s. Sem cálculo de pena, regime atual, marcos e término não constam; conferir se as guias foram unificadas/calculadas no SEEU." % (
                               rs.dias_para_pena(soma_at), "" if r.get("regime_atual") else "; Regime Atual em branco"),
                           "LEP, arts. 66, III, a, e 111."))

    # ---------------- 1. coerência aritmética do RSPE ----------------
    soma = sum(rs.pena_para_dias(c.get("pena_imposta")) or 0 for c in ativos)
    _amds = [rs.pena_amd(c.get("pena_imposta")) for c in ativos]
    _tot = rs.pena_amd(r.get("pena_total"))
    if pena_total and soma and _tot and all(_amds):
        _comut = [i for i in incidentes if "COMUTA" in (i.get("tipo") or "").upper() and i.get("situacao") == "CONCEDIDO"]
        _comutados = any("COMUTAD" in (c.get("processo_situacao") or "").upper() for c in ativos)
        if rs.amd_normal(sum(x[0] for x in _amds), sum(x[1] for x in _amds), sum(x[2] for x in _amds)) != rs.amd_normal(*_tot) and (_comut or _comutados) and soma > pena_total:
            itens.append(_item("info", "Soma das penas maior que a pena total: compatível com comutação",
                               "Soma das penas originais: %s; pena total impressa: %s. Há %d comutação(ões) concedida(s)%s - a pena total já considera a redução." % (
                                   rs.dias_para_pena(soma), r.get("pena_total"), len(_comut), " e processos marcados \"(Comutada)\"" if _comutados else ""),
                               "Decretos de comutação; LEP, art. 192."))
        elif rs.amd_normal(sum(x[0] for x in _amds), sum(x[1] for x in _amds), sum(x[2] for x in _amds)) != rs.amd_normal(*_tot):
            itens.append(_item("alerta", "Soma das penas difere da pena total",
                               "Soma das penas dos crimes não extintos: %s; pena total impressa: %s (diferença %s)." % (
                                   rs.dias_para_pena(soma), rs.dias_para_pena(pena_total), rs.dias_para_pena(abs(soma - pena_total))),
                               "LEP, art. 111 (soma/unificação); possível pena extinta, comutada, detração ou unificação não refletida nos crimes."))
        else:
            itens.append(_item("ok", "Soma das penas confere com a pena total", "Soma das penas = total %s." % r.get("pena_total")))
    _t, _c, _r = rs.pena_amd(r.get("pena_total")), rs.pena_amd(r.get("pena_cumprida")), rs.pena_amd(r.get("pena_remanescente"))
    if _t and _c and _r:
        # conferência em anos/meses/dias, como o SEEU soma (não em dias corridos)
        if rs.amd_normal(_c[0] + _r[0], _c[1] + _r[1], _c[2] + _r[2]) != rs.amd_normal(*_t):
            itens.append(_item("alerta", "Cumprida + remanescente ≠ pena total",
                               "%s + %s = %s, mas a pena total é %s." % (rs.dias_para_pena(cumprida), rs.dias_para_pena(reman), rs.dias_para_pena(cumprida + reman), rs.dias_para_pena(pena_total)),
                               "Coerência interna do atestado; pedir recálculo/atestado atualizado."))
    # remições
    rem_inc = 0
    for i in incidentes:
        if "REMI" in (i.get("tipo") or "").upper() and i.get("situacao") == "CONCEDIDO":
            m = rs.re.search(r"(\d+)\s*Dia", i.get("complemento", ""), rs.re.I)
            if m:
                rem_inc += int(m.group(1))
    m = rs.re.search(r"\((\d+)\s*dias remidos\s*-\s*(\d+)\s*dias perdidos\)", r.get("saldo_remidos", ""), rs.re.I)
    if m:
        remidos, perdidos = int(m.group(1)), int(m.group(2))
        if rem_inc and rem_inc != remidos:
            itens.append(_item("alerta", "Dias remidos: incidentes não fecham com o saldo",
                               "Incidentes de remição somam %d dias; o resumo diz %d remidos (%d perdidos)." % (rem_inc, remidos, perdidos),
                               "LEP, arts. 126 e 127."))
        if perdidos:
            itens.extend(_perda_remidos(incidentes, perdidos))
    # pena integralmente cumprida
    if pena_total and cumprida is not None and cumprida >= pena_total and "ATIVO" in (r.get("status_execucao") or "").upper():
        itens.append(_item("alerta", "Pena integralmente cumprida com execução ativa",
                           "Cumprida %s ≥ total %s: cabe extinção da pena." % (rs.dias_para_pena(cumprida), rs.dias_para_pena(pena_total)), "LEP, art. 109; CP, art. 107."))

    reinc_sem_base = []
    # ---------------- 2. crime a crime: hediondez, VGA, frações ----------------
    for c in ativos:
        nome = rs.crimes_curto([c])
        art = rs.num_art(c.get("artigo"))
        lei = rs.num_lei(c.get("lei"))
        fato = rs.to_date(c.get("data_infracao") or "")
        reinc = c.get("reincidente_comum") == "S" or c.get("reincidente_especifico") == "S"
        # reincidência efetiva: a linha pode dizer "N" havendo condenação anterior transitada antes do fato (CP, art. 63)
        _ant = [o for o in crimes if o is not c and fato and rs.to_date(o.get("transito_processo") or o.get("transito_mp") or "")
                and rs.to_date(o.get("transito_processo") or o.get("transito_mp")) < fato]
        reinc_ef = reinc or bool(_ant)
        reinc_esp = c.get("reincidente_especifico") == "S"
        vga = c.get("vga") == "S"
        morte = c.get("resultado_morte") == "S"
        hed_seeu = _hediondo_seeu(c)
        hed_lei, obs_h = _e_hediondo_lei(c)
        # dados ausentes
        if not art:
            itens.append(_item("info", "%s: artigo não informado" % nome, "O SEEU não registrou o artigo; a descrição do tipo é: %s" % (c.get("tipo_penal") or "-")[:120], "Sem o artigo, hediondez, VGA e frações ficam sem conferência."))
        if not fato:
            itens.append(_item("info", "%s: data do fato ausente" % nome, "Sem a data do fato não se aplica a lei do tempo (frações de progressão, art. 115 CP).", "CF, art. 5º, XL; STJ Tema 1354."))
        if not c.get("transito_processo") and not c.get("transito_mp"):
            itens.append(_item("info", "%s: trânsito em julgado não informado" % nome, "Sem trânsito o RSPE pode estar em execução provisória; afeta prescrição executória e indulto.", "CP, art. 112, I; STF Tema 788."))
        # hediondez
        if hed_lei is True and not hed_seeu:
            itens.append(_item("info", "%s: hediondo/equiparado pela lei, mas o SEEU aplicou fração comum (favorece o apenado)" % nome,
                               "Frações no RSPE: progressão %s; livramento %s." % (c.get("fracao_progressao"), c.get("fracao_livramento")), "Lei 8.072/90, art. 1º; LEP, art. 112; CP, art. 83, V."))
        elif hed_seeu and rs.hediondo_na_epoca(c) is False:
            _d, _lei = rs.hediondo_desde(c)
            itens.append(_item("alerta", "%s: SEEU tratou como hediondo, mas o fato (%s) é anterior à lei que o tornou hediondo (%s, vigência %s)" % (
                nome, rs.fmt(fato) if fato else "?", _lei or "?", rs.fmt(_d)),
                "A hediondez se rege pela lei da data do fato (irretroatividade da lei penal mais gravosa). Reflete na fração de progressão (comum, não 2/5-3/5 ou 70%%+), no livramento (1/3-1/2, não 2/3) e no indulto (art. 1º dos decretos). Frações no RSPE: %s / %s." % (
                    c.get("fracao_progressao"), c.get("fracao_livramento")),
                "CF, art. 5º, XL; CP, art. 2º; Lei 8.072/90 e alterações; STJ, Temas 1084 e 1196."))
        elif hed_lei is False and hed_seeu and ("HEDIONDO" in (c.get("fracao_progressao") or "").upper() or not (lei == "11343" and art in ("33", "34", "35", "36", "37"))):
            itens.append(_item("alerta", "%s: SEEU tratou como hediondo, mas o tipo não consta do rol" % nome,
                               (obs_h or "Verificar a capitulação (qualificadora/§) que justifique a hediondez.") + " Frações no RSPE: %s / %s." % (c.get("fracao_progressao"), c.get("fracao_livramento")),
                               "Lei 8.072/90, art. 1º; LEP, art. 112, § 5º."))
        elif hed_lei is None and art:
            itens.append(_item("info", "%s: hediondez depende do parágrafo/inciso" % nome, "Hediondo apenas se: %s. SEEU aplicou %s." % (obs_h, "fração de hediondo" if hed_seeu else "fração comum"), "Lei 8.072/90, art. 1º."))
        # VGA
        esperado = rg.vga_esperado(art) if art else None
        if esperado and c.get("vga") and esperado != c.get("vga"):
            itens.append(_item("alerta" if c.get("vga") == "S" else "info", "%s: marcação de violência/grave ameaça diverge do tipo" % nome,
                               "RSPE: VGA = %s; pelo tipo penal esperava-se %s. Reflete nas frações de progressão e no indulto (arts. 9º, I a III dos decretos)." % (c.get("vga"), esperado),
                               "LEP, art. 112, I e II; Decretos 12.338/2024 e 12.790/2025."))
        # fração de progressão
        f_seeu = _fr_seeu(c.get("fracao_progressao"))
        hed = hed_lei if hed_lei is not None else hed_seeu
        f_esp, rot, obs = rg.fracao_mais_benefica(fato, hed, morte, vga, reinc)
        if reinc and not reinc_esp and hed:
            for _dref in ([fato, date(2020, 1, 23)] if fato and fato < date(2020, 1, 23) else [fato]):
                f_esp2, rot2, obs2 = rg.fracao_progressao_esperada(_dref, hed, morte, vga, reinc, reinc_especifico=False)
                if f_esp2 is not None and (f_esp is None or f_esp2 < f_esp):
                    f_esp, rot, obs = f_esp2, rot2, obs + obs2 + (["retroatividade da lei mais benéfica (Lei 13.964/2019; STJ Tema 1084)"] if _dref != fato else [])
        if f_seeu is not None and f_esp is not None:
            if abs(float(f_seeu) - float(f_esp)) > 0.01:
                itens.append(_item("alerta" if float(f_seeu) > float(f_esp) else "info",
                               ("%s: fração de progressão do SEEU (%s) maior que a legal (%s)" if float(f_seeu) > float(f_esp) else "%s: fração de progressão do SEEU (%s) menor que a esperada (%s) - favorece o apenado") % (nome, c.get("fracao_progressao"), rot),
                               "Fato em %s; %s; %s; %s. %s" % (rs.fmt(fato) if fato else "?", "reincidente" if reinc else "primário", "com VGA" if vga else "sem VGA",
                                                               "hediondo" if hed else "comum", " ".join(obs)),
                               "LEP, art. 112 (redação vigente na data do fato; lei posterior só retroage se mais benéfica - CF, art. 5º, XL; STJ Temas 1084, 1196 e 1354; STF Tema 1169)."))
            else:
                nota = " ".join(obs) or "Conforme a lei da data do fato."
                if abs(float(f_seeu) - float(f_esp)) > 0.001:
                    nota += " (diferença marginal 1/6 x 16%: STJ Tema 1354 admite o percentual mais benéfico)"
                itens.append(_item("ok", "%s: fração de progressão confere (%s)" % (nome, c.get("fracao_progressao")), nota, "LEP, art. 112."))
        # fração de livramento
        if pena_total and pena_total < rg.carregar().get("livramento", {}).get("pena_minima_anos", 2) * rs.DIAS_ANO and c.get("fracao_livramento"):
            itens.append(_item("info", "%s: livramento condicional com pena total inferior a 2 anos" % nome,
                               "O RSPE calcula fração de livramento (%s), mas o benefício exige pena igual ou superior a 2 anos (pena total %s)." % (c.get("fracao_livramento"), rs.dias_para_pena(pena_total)),
                               "CP, art. 83, caput."))
        fl_seeu = _fr_seeu(c.get("fracao_livramento"))
        trafico = lei == "11343" and art in ("33", "34", "35", "36", "37") and not (art == "33" and "§ 4" in (c.get("tipo_penal") or ""))
        fl_esp, rotl = rg.fracao_livramento_esperada(hed, reinc_ef, trafico)
        if fl_seeu is not None and abs(float(fl_seeu) - float(fl_esp)) > 0.005:
            itens.append(_item("alerta" if float(fl_seeu) > float(fl_esp) else "info",
                               ("%s: fração de livramento do SEEU (%s) maior que a legal (%s)" if float(fl_seeu) > float(fl_esp) else "%s: fração de livramento do SEEU (%s) menor que a esperada (%s) - favorece o apenado") % (nome, c.get("fracao_livramento"), rotl),
                               "%s; %s." % ("reincidente" if reinc_ef else "primário", "hediondo/equiparado" if hed else ("art. 44, p. ú., Lei 11.343/06" if trafico else "comum")), "CP, art. 83; Lei 11.343/06, art. 44, p. ú."))
        if hed and reinc_esp:
            itens.append(_item("alerta", "%s: reincidente específico em hediondo - livramento vedado" % nome, "O RSPE prevê fração de livramento %s." % c.get("fracao_livramento"), "CP, art. 83, V."))
        j = rg.regime_progressao(fato) if fato else None
        if j and j.get("vedado_lc") and hed and morte:
            itens.append(_item("verificar", "%s: hediondo com resultado morte - vedação de livramento" % nome,
                               "Para fatos a partir de 25/03/2026 o livramento é vedado (LEP, art. 112, VI/VIII); para fatos anteriores, STF Tema 1319 afasta a vedação ao aplicar retroativamente o 50%%.", "LEP, art. 112; STF Tema 1319."))
        # reincidência: precisa de condenação anterior transitada antes do fato (consolidado após o laço)
        if reinc and fato:
            anteriores = [o for o in crimes if o is not c and rs.to_date(o.get("transito_processo") or o.get("transito_mp") or "") and rs.to_date(o.get("transito_processo") or o.get("transito_mp")) < fato]
            if not anteriores:
                reinc_sem_base.append(fato)
        # idade
        if nasc:
            i_fato = fato.year - nasc.year - ((fato.month, fato.day) < (nasc.month, nasc.day)) if fato else None
            if i_fato is not None and i_fato < 21:
                itens.append(_item("verificar", "%s: menor de 21 anos no fato (%d) - prescrição pela metade" % (nome, i_fato), "Conferir se o SEEU/juízo considerou o art. 115 nos cálculos de prescrição.", "CP, art. 115."))

    if reinc_sem_base:
        itens.append(_item("verificar", "Marcado reincidente sem condenação anterior transitada no RSPE",
                           "Nenhum processo deste RSPE transitou em julgado antes dos fatos (%s). A reincidência pode vir de condenação não listada aqui: "
                           "conferir a certidão de antecedentes e o período depurador de 5 anos (art. 64, I). Afeta frações de progressão, livramento e indulto." % (
                               rs.fmt(min(reinc_sem_base)) if len(set(reinc_sem_base)) == 1 else "de %s a %s" % (rs.fmt(min(reinc_sem_base)), rs.fmt(max(reinc_sem_base)))),
                           "CP, arts. 63 e 64, I."))
    # ---------------- 3. data-base e faltas ----------------
    regs = [i for i in incidentes if "REGIME" in (i.get("tipo") or "").upper() and i.get("situacao") == "CONCEDIDO"
            and rs.re.search(r"PROGRESS|REGRESS", i.get("complemento") or "", rs.re.I)]
    ult = None
    for i in regs:
        d = rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "")
        if d and (ult is None or d > ult[0]):
            ult = (d, i)
    for i in regs:
        if "PROGRESS" in (i.get("complemento") or "").upper() and i.get("data_decisao") and i.get("data_decisao") == i.get("data_referencia"):
            itens.append(_item("info", "Progressão com data-base igual à data da decisão (%s)" % i.get("data_decisao"),
                               "A data-base da progressão seguinte deve ser a data em que os requisitos foram preenchidos, não a da decisão que a deferiu; se o lapso já estava vencido antes, a data-base pode ser anterior.",
                               "STJ, Tema 1165 (REsp 1.973.589)."))
            break
    db_seeu = rs.to_date(r.get("data_base_seeu") or "")
    if db_seeu and ult and db_seeu < ult[0]:
        itens.append(_item("alerta", "Data-base de progressão anterior à última alteração de regime",
                           "Data-base impressa: %s; última alteração de regime: %s (%s)." % (rs.fmt(db_seeu), rs.fmt(ult[0]), ult[1].get("complemento")),
                           "LEP, art. 112, § 6º (falta grave reinicia pela remanescente); STJ Tema 1006 (a unificação de penas não altera a data-base); STJ Tema 1165 (data-base é a do preenchimento dos requisitos, não a da decisão)."))
    if ult and "REGRESS" in (ult[1].get("complemento") or "").upper():
        itens.append(_item("info", "Regressão registrada em %s" % rs.fmt(ult[0]),
                           "Se decorreu de falta grave, a data-base da progressão é a data da falta e o requisito recomeça sobre a pena remanescente; a falta também impede LC (12 meses) e indulto (art. 6º dos decretos).",
                           "LEP, arts. 112, § 6º, 118 e 127; CP, art. 83, III, b."))
    idade = None
    if nasc:
        idade = hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))
        if idade >= 70:
            itens.append(_item("verificar", "Idade %d anos: prescrição pela metade e prisão domiciliar" % idade, "Art. 115 do CP (maior de 70 na sentença) e art. 117, I, da LEP (regime aberto em residência).", "CP, art. 115; LEP, art. 117."))
        elif idade >= 60:
            itens.append(_item("verificar", "Idade %d anos: lapsos de indulto pela metade" % idade, "Decretos 12.338/2024 e 12.790/2025, art. 9º, § 2º, I.", ""))

    # regime impresso no RSPE x livramento em curso
    _lc, _dl = rs.livramento_em_curso(r, incidentes)
    if _lc:
        _duv = rs.duvidas_livramento(r, eventos, incidentes, _dl)
        if _duv:
            itens.append(_item("alerta", "Livramento condicional%s com situação incerta no RSPE" % ((" deferido em %s" % rs.fmt(_dl)) if _dl else ""),
                "O SEEU imprime o livramento como vigente, mas o RSPE registra: %s. Conferir nos autos se o livramento foi suspenso ou revogado "
                "(CP, arts. 86 a 88; LEP, arts. 140 a 145) ou se o período de prova se esgotou sem revogação, caso em que a pena está extinta (CP, art. 90). "
                "Enquanto isso, progressão, livramento, indulto e extinção ficam como 'a verificar'." % "; ".join(_duv),
                "CP, arts. 86 a 90; LEP, arts. 140 a 145."))
    # ---------------- 4. marcos vencidos e prescrição ----------------
    import rspe_view as _rv
    _est = _rv.estado_execucao(r)
    _est = _est[0] if _est else ""
    for chave, nome_marco in (("progressao_previsao_seeu", "Progressão"), ("livramento_previsao_seeu", "Livramento condicional")):
        d = rs.to_date(r.get(chave) or "")
        # pena cumprida / em livramento dispensam os dois marcos; regime aberto dispensa a progressão
        if _est in ("cumprida", "lc") or (_est == "aberto" and chave.startswith("prog")):
            continue
        if d and d <= hoje:
            palavra = "PROGRESS" if chave.startswith("prog") else "LIVRAMENTO"
            pedidos_pos = [i for i in incidentes if palavra in ((i.get("tipo") or "") + " " + (i.get("complemento") or "")).upper()
                           and (rs.to_date(i.get("data_decisao") or "") or date.min) >= d]
            if not pedidos_pos:
                itens.append(_item("alerta", "%s vencida em %s sem decisão posterior no RSPE" % (nome_marco, rs.fmt(d)),
                                   "Lapso atingido há %d dias e nenhum incidente decidido depois dessa data." % (hoje - d).days, "LEP, art. 112; CP, art. 83."))
    presc = rp.analisar(r, hoje)
    for l in presc["presc_linhas"]:
        if (l.get("ppe_status") or "").startswith("Pena cumprida por detração"):
            itens.append(_item("alerta", "%s: pena cumprida por detração" % l["crime"], l.get("ppe_detalhe", ""), "CP, art. 42; LEP, art. 66, II."))
        elif l.get("ppe_cor") == "vermelho":
            itens.append(_item("alerta", "%s: prescrição da pretensão executória aparente (%s)" % (l["crime"], l.get("ppe_previsao")), l.get("ppe_status", ""), "CP, arts. 110, 112, 113 e 117, V; STF Tema 788."))
        if l.get("retro_cor") == "vermelho":
            itens.append(_item("alerta", "%s: prescrição da pretensão punitiva aparente" % l["crime"], l.get("retro_status", ""), "CP, arts. 109, 110, § 1º, e 117."))
        if l.get("ppe_cor") == "amarelo":
            # só interessa quando o prazo está próximo (até 1 ano); antes disso é informativo
            perto = l.get("ppe_dias") is not None and l["ppe_dias"] <= 365
            itens.append(_item("verificar" if perto else "info", "%s: prescrição executória em curso" % l["crime"], l.get("ppe_status", ""), "CP, arts. 112, II, e 113."))

    # ---------------- 5. indulto / comutação sem registro ----------------
    if True:  # 2022 tem exclusões próprias (art. 7º); 2024/2025 vêm "vedado" quando há impeditivo
        for ano in ("2022", "2024", "2025"):
            st = r.get("indulto_%s_status" % ano)
            if st == "possivel" and not rs.decisoes_decreto(incidentes, ano, "INDULTO"):
                itens.append(_item("alerta", "Indulto %s possível sem incidente no RSPE" % ano, r.get("indulto_%s" % ano, ""), "Decreto %s." % {"2022": "11.302/2022, arts. 4º e 5º", "2024": "12.338/2024, art. 9º", "2025": "12.790/2025, art. 9º"}[ano]))
            elif st == "verificar":
                itens.append(_item("info", "Indulto %s: hipóteses a verificar" % ano, r.get("indulto_%s" % ano, ""), "Depende de dado que o RSPE não traz (programa de egressos, estudo, saídas, valor do bem, saúde)."))
        for ano, dec in (("2024", "12.338/2024"), ("2025", "12.790/2025")):
            if (r.get("comutacao_%s" % ano) or "").startswith("POSSÍVEL") and not rs.decisoes_decreto(incidentes, ano, "COMUTA"):
                itens.append(_item("alerta", "Comutação %s possível sem incidente no RSPE" % ano, r.get("comutacao_%s" % ano, ""), "Decreto %s, art. 13." % dec))
    # hediondez superveniente: impeditivo pelo STJ (data do decreto), mas há tese defensiva no STF
    sup = [c for c in ativos if rs.e_hediondo(c, date(2024, 12, 25)) and not rs.e_hediondo(c)]
    if sup:
        itens.append(_item("verificar", "Hediondez posterior ao fato: indulto/comutação vedados pelo STJ, com tese defensiva (%s)" % rs.crimes_curto(sup),
                           "O crime não era hediondo na data do fato, mas é na data do decreto. O STJ afere na data do decreto e veda o benefício. "
                           "A favor da defesa (irretroatividade da hediondez posterior ao fato): STF, 2ª Turma, RHC 267.297 AgR (16/03/2026) e HC 273.296 AgR (06/08/2026); "
                           "decisões monocráticas do STF concedendo indulto/comutação: RE 1.572.734 (Fux, 10/10/2025), HC 258.516 (Mendonça, 14/07/2025), "
                           "RHC 269.076 (Cármen Lúcia, 06/03/2026), HC 271.716 (Fux, 05/05/2026), RE 1.607.670 (Cármen Lúcia, 10/06/2026). "
                           "TJMS dividido: a 2ª Câmara Criminal afasta o óbice (AgExec 1602006-93.2026.8.12.0000, 15/06/2026; 1602467-65.2026.8.12.0000, 03/08/2026; "
                           "1603697-45.2026.8.12.0000, 20/08/2026); a 1ª e a 3ª Câmaras seguem o STJ (ex.: 1602236-38.2026.8.12.0000, 03/09/2026; 1604099-29.2026.8.12.0000, 27/08/2026). "
                           "As frações de progressão seguem a data do fato.",
                           "Decretos de indulto, art. 1º, I; CF, art. 5º, XL; CP, art. 2º."))
    # violência doméstica: art. 129 §§ 9º-11 sem sinal de que a vítima é mulher
    for c in ativos:
        vd = rs.violencia_domestica(c)
        if vd and vd[0] == "provavel":
            itens.append(_item("verificar", "%s: violência doméstica - confirmar se a vítima é mulher" % rs.crimes_curto([c]),
                               "Se a vítima for mulher, o crime é impeditivo de indulto e comutação (art. 1º, XVII, dos Decretos 12.338/2024 e 12.790/2025; "
                               "art. 7º, III, c, do Decreto 11.302/2022). Enquanto não confirmado, o indulto fica \"a verificar\".",
                               "Decretos de indulto, art. 1º; Lei 11.340/06."))
    # presunção de hipossuficiência (Defensoria): multa e reparação do dano nunca bloqueiam benefício no programa
    crimes_ativos = [c for c in crimes if not c.get("extinto", "").upper().startswith("S")]
    if any(re.search(r"\b[Ee]\s+Multa", c.get("tipo_penal") or "") for c in crimes_ativos):
        itens.append(_item("info", "Pena de multa cominada: hipossuficiência presumida",
                           "A multa não é tratada como óbice à extinção, ao livramento ou ao indulto; instruir a petição com a assistência pela Defensoria e a ausência de bens.",
                           "STJ Tema 931 (rev. 28/02/2024); STF ADI 7.032; Decretos 12.338/2024 e 12.790/2025, art. 12, § 2º, I."))
    if any(rs.crime_patrimonial(c) and c.get("vga") != "S" for c in crimes_ativos):
        itens.append(_item("info", "Crime patrimonial sem VGA: reparação do dano presumida impossível",
                           "Livramento (CP, art. 83, IV) e indulto (art. 9º, XV) não são bloqueados pela ausência de reparação; a impossibilidade econômica é presumida para o assistido da Defensoria.",
                           "CP, art. 83, IV ('salvo efetiva impossibilidade'); Decretos 12.338/2024 e 12.790/2025, art. 9º, XV c/c art. 12, § 2º, I."))
    if r.get("falta_12m") == "SIM":
        itens.append(_item("verificar", "Indício de falta nos últimos 12 meses", r.get("falta_12m_detalhe", ""), "Reflexo em LC (CP, art. 83, III, b), indulto (art. 6º dos decretos) e progressão (LEP, art. 112, §§ 6º e 7º)."))

    # ---------------- 6. eventos / detração ----------------
    periodos = rs.periodos_custodia(eventos)
    if not periodos and (cumprida or 0) > 0:
        itens.append(_item("verificar", "Pena cumprida sem evento de prisão no RSPE", "O relatório indica %s cumpridos, mas não lista eventos de início de cumprimento." % rs.dias_para_pena(cumprida), "Conferir a guia e a detração (CP, art. 42)."))
    if "INTERROMPIDA" in (r.get("situacao_cumprimento") or ""):
        itens.append(_item("info", "Cumprimento interrompido (último evento é interrupção)", "Verificar se há prisão posterior não lançada ou se o apenado está foragido/em liberdade; a prescrição executória corre pela pena restante.", "CP, arts. 112, II, e 113."))

    itens = _agrupar_por_crime(itens)
    n_alerta = sum(1 for i in itens if i["nivel"] == "alerta")
    n_verif = sum(1 for i in itens if i["nivel"] == "verificar")
    status = "atencao" if n_alerta else ("verificar" if n_verif else "ok")
    ordem = {"alerta": 0, "verificar": 1, "info": 2, "ok": 3}
    itens.sort(key=lambda i: ordem[i["nivel"]])
    return {"aud_status": status, "aud_itens": itens, "aud_alertas": n_alerta, "aud_verificar": n_verif,
            "aud_resumo": "Guia demanda atenção: %d alerta(s), %d a verificar" % (n_alerta, n_verif) if n_alerta else
                          ("%d ponto(s) a verificar" % n_verif if n_verif else "Sem inconsistências detectadas"),
            "aud_base": "base jurídica %s" % rg.versao()}
