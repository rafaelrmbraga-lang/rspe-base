"""Teste da conferência independente (7.14.5), frente indulto e comutação, com casos hipotéticos montados em dicionário (nomes
fictícios): cumprimento interrompido com a fração já cumprida segue a análise dos incisos (XV sem fração; comutação pelo tempo até
a data); impeditivo e não impeditivo na mesma sentença sem trânsito para a acusação (vedado, não "a verificar"); interrupção por
prisão em outro processo (a custódia do outro processo não conta) x prisão no dia da recaptura desta execução ou somada pelo SEEU
(sem o aviso de custódia por outro processo); fuga anterior à janela homologada depois da publicação (art. 6º a verificar);
impeditivo com sentença posterior ao decreto no rótulo da execução; XII com a matrícula cancelada só depois da saída da unidade;
tráfico privilegiado com pena convertida no Decreto 2022 (art. 8º, I).
Rodar: python teste_conf6_indulto.py (sai com código 1 se algum caso falhar)."""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_decretos as rd
import rspe_ficha as rf
import rspe_scraper as rs
import rspe_view as rv

HOJE = date(2026, 10, 22)
D = rs.to_date
falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def crime(fato, sent, tr, artigo="ART 155: Furto", tipo="CAPUT: Subtrair, para si ou para outrem, coisa alheia móvel, Reclusão: 1 a 4 anos E Multa",
          pena="1 ano(s), 0 mês(es) e 0 dia(s)", lei="2848/40 - Código Penal", proc="0000001-00.2020.8.12.0001", vga="N", hed="N",
          ptp="PENA ORIGINÁRIA", reinc="N"):
    return {"processo_criminal": proc, "vara_condenacao": "1ª Vara Criminal", "data_infracao": fato, "data_sentenca": sent, "transito_mp": tr,
            "transito_processo": tr, "lei": lei, "artigo": artigo, "tipo_penal": tipo, "pena_imposta": pena, "pena_total_processo": ptp,
            "regime_sentenca": "Fechado", "vga": vga, "resultado_morte": "N", "reincidente_comum": reinc, "reincidente_especifico": "N",
            "comando_orcrim": "N", "extinto": "Não", "suspenso": "Não", "hediondo_ou_equiparado": hed}


def ev(d, tipo="PRISÃO/INÍCIO DE CUMPRIMENTO", mot="PRISÃO DEFINITIVA", procs=""):
    return {"tipo": tipo, "motivo": mot, "data": d, "processos": procs}


def inc(tipo, compl, data, ref=None, sit="CONCEDIDO"):
    return {"tipo": tipo, "complemento": compl, "data_decisao": data, "data_referencia": ref or data, "situacao": sit, "processos": ""}


def reg(crimes, eventos, pena_total, cumprida="", incid=None, ger="05/10/2026", regime="Fechado - ATIVO", interr=""):
    return {"nome": "T", "processo_execucao": "X", "pena_total": pena_total, "pena_cumprida": cumprida, "pena_remanescente": "",
            "data_geracao_rspe": ger, "termino_previsao_seeu": "", "data_nascimento": "01/01/1990", "_sexo": "M", "status_execucao": "ATIVO",
            "regime_atual": regime, "_crimes": crimes, "_eventos": eventos, "_incidentes": incid or [], "total_interrupcoes": interr}


ROUBO = dict(artigo="ART 157: Roubo", tipo="§ 2º: A pena aumenta-se, Reclusão: 4 a 10 anos E Multa", vga="S")
RECEPT = dict(artigo="ART 180: Receptação", tipo="CAPUT: Adquirir, receber, Reclusão: 1 a 4 anos E Multa")

try:
    # ---- 1. interrupção genérica com 1/5 cumprido: XV (sem fração nem regime) e comutação seguem a análise ----
    cr = crime("03/07/2023", "10/01/2024", "10/02/2024", pena="5 ano(s), 4 mês(es) e 0 dia(s)", proc="0000002-00.2023.8.12.0001", **ROUBO)
    cp = crime("10/05/2022", "25/03/2024", "25/04/2024", pena="1 ano(s), 0 mês(es) e 0 dia(s)", proc="0000003-00.2022.8.12.0001", **RECEPT)
    evs = [ev("03/07/2023", mot="PRISÃO EM FLAGRANTE"),
           ev("31/10/2024", "INTERRUPÇÃO", "INTERRUPÇÃO DO CUMPRIMENTO DA PENA")]
    r = reg([cr, cp], evs, "6a4m0d", "1a3m29d", incid=[inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Semiaberto - Progressão de Regime", "02/11/2024")],
            interr="1a11m5d", regime="Semiaberto - ATIVO")
    o = rs.analise_decretos(r, r["_crimes"], r["_eventos"], r["_incidentes"], HOJE)
    i24, c24 = o.get("indulto_2024") or "", o.get("comutacao_2024") or ""
    ok(i24.startswith("POSSÍVEL") and "XV" in i24.split(" | ")[0] and "cumprimento interrompido" in i24,
       "1: XV com a interrupção como falta a verificar: %s" % i24)
    ok("conferir a fração" not in i24 + c24, "1: não manda conferir a fração já cumprida: %s | %s" % (i24, c24))
    ok("✔ Requisito: 1/5" in (o.get("comutacao_2024_detalhe") or ""), "1: comutação com o requisito cumprido: %s" % o.get("comutacao_2024_detalhe"))
    ok(o.get("indulto_2024_status") == "verificar", "1: falta a verificar deixa a verificar: %s" % o.get("indulto_2024_status"))
    # interrupção por prisão em outro processo não é falta: sem a nota "fuga punida"
    evs_o = [ev("03/07/2023", mot="PRISÃO EM FLAGRANTE"), ev("31/10/2024", "INTERRUPÇÃO", "INTERRUPÇÃO POR PRISÃO EM OUTRO PROCESSO")]
    r = reg([cr, cp], evs_o, "6a4m0d", "1a3m29d", interr="1a11m5d")
    o = rs.analise_decretos(r, r["_crimes"], r["_eventos"], [], HOJE)
    ok("fuga punida" not in (o.get("indulto_2024") or ""), "1: prisão em outro processo não é falta: %s" % o.get("indulto_2024"))

    # ---- 2. impeditivo e não impeditivo na mesma sentença, sem trânsito para a acusação: vedado (indulto e comutação) ----
    HOM = dict(artigo="ART 121: Homicídio", tipo="§ 2º: Se o homicídio é cometido, Reclusão: 12 a 30 anos", vga="S", hed="S",
               pena="15 ano(s), 10 mês(es) e 0 dia(s)", ptp="APELAÇÃO CRIMINAL")
    OC = dict(artigo="ART 211: Destruição, subtração ou ocultação de cadáver", tipo="CAPUT: Destruir, subtrair ou ocultar cadáver, Reclusão: 1 a 3 anos E Multa",
              pena="1 ano(s), 0 mês(es) e 0 dia(s)", ptp="APELAÇÃO CRIMINAL")
    P = "0000004-00.2023.8.12.0001"
    ch = crime("19/11/2023", "14/03/2025", "", proc=P, **HOM)
    co = crime("19/11/2023", "14/03/2025", "", proc=P, **OC)
    r = reg([ch, co], [ev("20/11/2023", mot="PRISÃO EM FLAGRANTE")], "16a10m0d", "2a10m13d")
    o = rs.analise_decretos(r, r["_crimes"], r["_eventos"], [], HOJE)
    ok((o.get("indulto_2025") or "").startswith("VEDADO"), "2: mesma sentença - vedado: %s" % o.get("indulto_2025"))
    ok((o.get("comutacao_2025") or "").startswith("VEDADA"), "2: comutação vedada, não 'sem condenação': %s" % o.get("comutacao_2025"))
    ok("mesma sentença" in (o.get("indulto_2025_detalhe") or ""), "2: detalhe explica a mesma sentença")
    # não impeditivo de OUTRA sentença: continua a verificar (sem o impeditivo sem trânsito, ele pode ser analisado)
    co2 = crime("10/01/2022", "10/06/2022", "10/07/2022", proc="0000005-00.2022.8.12.0001")
    r = reg([ch, co2], [ev("20/11/2023", mot="PRISÃO EM FLAGRANTE")], "16a10m0d", "2a10m13d")
    o = rs.analise_decretos(r, r["_crimes"], r["_eventos"], [], HOJE)
    ok((o.get("indulto_2025") or "").startswith("A VERIFICAR (art. 2º, II)"), "2: outra sentença - a verificar: %s" % o.get("indulto_2025"))

    # ---- 3. interrupção por prisão em outro processo com a preventiva no mesmo dia: a custódia é do outro processo ----
    LES = dict(artigo="ART 129: Lesão corporal", tipo="CAPUT: Ofender a integridade corporal, Detenção: 3 meses a 1 ano", vga="S",
               pena="0 ano(s), 3 mês(es) e 0 dia(s)")
    cl = crime("10/01/2023", "10/06/2024", "10/07/2024", proc="0000006-00.2023.8.12.0001", **LES)
    evs = [ev("17/03/2025", mot="INÍCIO DO CUMPRIMENTO REGIME ABERTO"), ev("07/06/2025", "INTERRUPÇÃO", "INTERRUPÇÃO POR PRISÃO EM OUTRO PROCESSO"),
           ev("07/06/2025", mot="PRISÃO PREVENTIVA", procs="0000009-00.2025.8.12.0001")]
    r = reg([cl], evs, "0a3m0d", "0a2m21d", interr="1a3m29d", regime="Aberto - ATIVO")
    ok(len(rs.eventos_sem_custodia_outro_processo(evs, r)) == 2, "3: a preventiva do dia da interrupção sai da conta")
    ok(rs.eventos_sem_custodia_outro_processo(evs[:1] + evs[2:], r) == evs[:1] + evs[2:], "3: sem a interrupção expressa, nada muda")
    ok(len(rs.eventos_sem_custodia_outro_processo(evs, dict(r, total_interrupcoes=""))) == 3,
       "3: o SEEU não conta a interrupção (Total Interrupções vazio): a custódia segue somada")
    o = rs.analise_decretos(r, r["_crimes"], r["_eventos"], [], HOJE)
    i25 = o.get("indulto_2025") or ""
    ok("extinção" not in i25 and "III" in i25.split(" | ")[0], "3: indulto pelo III, não extinção: %s" % i25)

    # ---- 4. aviso de custódia por outro processo: não quando o SEEU soma o período ----
    PO = "0000007-00.2025.8.12.0001"
    cf = crime("10/01/2019", "10/06/2019", "10/07/2019", pena="8 ano(s), 0 mês(es) e 0 dia(s)")
    evs4 = [ev("22/07/2019"), ev("25/04/2025", "INTERRUPÇÃO", "FUGA"), ev("16/07/2025", mot="PRISÃO EM FLAGRANTE", procs=PO),
            ev("16/07/2025", mot="RECAPTURA/REINÍCIO DE CUMPRIMENTO", procs="0000001-00.2020.8.12.0001")]
    r4 = reg([cf], evs4, "8a0m0d", "", interr="")
    ok(rd.custodia_outro_processo(r4, D("25/12/2025"), [cf]) == "", "4: recaptura no mesmo dia: o tempo é desta pena")
    evs4b = [ev("16/01/2024"), ev("23/10/2024", "INTERRUPÇÃO", "LIBERDADE PROVISÓRIA"), ev("16/11/2024", mot="PRISÃO EM FLAGRANTE", procs=PO)]
    r4b = reg([cf], evs4b, "8a0m0d", "", interr="0a0m24d")
    ok(rd.custodia_outro_processo(r4b, D("25/12/2024"), [cf]) == "", "4: SEEU soma o período (Total Interrupções só cobre o intervalo)")
    r4c = reg([cf], evs4b, "8a0m0d", "", interr="1a10m0d")
    ok(rd.custodia_outro_processo(r4c, D("25/12/2024"), [cf]) != "", "4: SEEU não soma: o aviso continua")

    # ---- 5. fuga anterior à janela, homologada com referência na recaptura depois da publicação: art. 6º a verificar ----
    evs5 = [ev("19/07/2022"), ev("06/04/2023", "INTERRUPÇÃO", "FUGA"), ev("26/04/2025", mot="RECAPTURA/REINÍCIO DE CUMPRIMENTO")]
    inc5 = [inc("HOMOLOGAÇÃO DE FALTA GRAVE", "26/04/2025", "18/07/2025", ref="26/04/2025")]
    firmes, verif = rs.falta_art6(inc5, D("25/12/2024"), evs5, D("23/12/2024"))
    ok(not firmes and any("atravessa os 12 meses" in v for v in verif), "5: fuga que atravessa a janela: %s | %s" % (firmes, verif))

    # ---- 6. impeditivo com sentença posterior ao decreto: "Sim" no rótulo, sem pintar a linha de vermelho ----
    ch6 = crime("07/06/2025", "24/04/2026", "", proc="0000009-00.2025.8.12.0001", **dict(HOM, ptp="PENA ORIGINÁRIA"))
    r6 = reg([cl, ch6], [ev("17/03/2025", mot="INÍCIO DO CUMPRIMENTO REGIME ABERTO")], "16a1m0d", "0a5m0d")
    o = rs.analise_decretos(r6, r6["_crimes"], r6["_eventos"], [], HOJE)
    ok(o.get("indulto_crime_impeditivo") == "SIM" and rs.IMP_FORA_SOMA in (o.get("indulto_crime_impeditivo_detalhe") or ""),
       "6: impeditivo fora da soma: %s | %s" % (o.get("indulto_crime_impeditivo"), o.get("indulto_crime_impeditivo_detalhe")))
    ok("fora da soma" in rv.curto_impeditivo(o), "6: rótulo: %s" % rv.curto_impeditivo(o))
    ok(rv.cor_indulto(dict(o, indulto_2024_status="verificar")) != "vermelho", "6: cor da linha")

    # ---- 7. XII: matrícula encerrada pela saída da unidade e cancelada só depois - "?" e não "✘" ----
    evf = [{"data": "03.03.2021", "texto": "EDUCAÇÃO: MATRÍCULOU-SE NA SÉRIE: MODULO - INTERMEDIARIO TURMA: F PERÍODO: VESPERTINO"},
           {"data": "20.01.2022", "texto": "SAÍDA DA UNIDADE PENAL: UNIDADE A, DESTINO: UNIDADE B, MOTIVO: PROGRESSAO DE REGIME,"},
           {"data": "17.05.2024", "texto": "EDUCAÇÃO: CANCELAMENTO DE MATRÍCULA. SAIDA DO PRESIDIO"}]
    es = rf._estudos(evf)
    ok(es and es[0].get("fim") == "20.01.2022" and es[0].get("fim_cancel") == "17.05.2024", "7: fim alternativo: %s" % es)
    r7 = {"indulto_2025": "A VERIFICAR: art. 9º, XII", "indulto_2025_status": "verificar", "_eventos": [],
          "indulto_2025_detalhe": "Situação em 25/12/2025: regime Fechado · reincidente · sem VGA\n? XII: pena ≤ 12 anos, 1/5 cumprido - verificar estudo"}
    rf.complementar_decretos(r7, {"eventos": evf, "estudos": es, "trabalho": [], "exames": []}, HOJE)
    ok("? XII:" in r7["indulto_2025_detalhe"] and "17/05/2024" in r7["indulto_2025_detalhe"], "7: XII a conferir: %s" % r7["indulto_2025_detalhe"])

    # ---- 8. Decreto 2022: tráfico privilegiado com pena convertida - art. 8º, I, a conferir ----
    TP = dict(artigo="ART 33: Tráfico de drogas", lei="11343/06 - Lei de Drogas", tipo="§ 4º: Nos delitos definidos no caput, Reclusão: 5 a 15 anos E Multa",
              pena="1 ano(s), 8 mês(es) e 0 dia(s)", ptp="1 ano(s), 8 mês(es) e 0 dia(s) - CONVERTIDA")
    ct = crime("10/06/2019", "10/01/2020", "10/02/2020", **TP)
    r8 = reg([ct], [ev("10/03/2022")], "1a8m0d", "0a9m0d", regime="Aberto - ATIVO")
    o8 = rs.analise_decreto_2022(r8, r8["_crimes"], r8["_eventos"], [])
    ok(not (o8.get("indulto_2022") or "").startswith("POSSÍVEL") and "art. 8º, I" in (o8.get("indulto_2022_detalhe") or ""),
       "8: convertida: %s" % o8.get("indulto_2022"))
    ct2 = dict(ct, pena_total_processo="PENA ORIGINÁRIA")
    o8b = rs.analise_decreto_2022(dict(r8, _crimes=[ct2]), [ct2], r8["_eventos"], [])
    ok((o8b.get("indulto_2022") or "").startswith("POSSÍVEL"), "8: sem conversão segue possível: %s" % o8b.get("indulto_2022"))
    # ---- 9. execução unificada (LEP, art. 111): sem "pedir a extinção pelo cumprimento" de pena isolada; só com a pena única ----
    c1 = crime("10/01/1999", "10/06/1999", "10/07/1999", pena="1 ano(s), 0 mês(es) e 0 dia(s)")
    c2 = crime("10/01/2005", "10/06/2005", "10/07/2005", pena="6 ano(s), 0 mês(es) e 0 dia(s)", proc="0000010-00.2005.8.12.0001")
    ok(rd.execucao_unificada(reg([c1, c2], [], "7a0m0d"), 365) and not rd.execucao_unificada(reg([c1], [], "1a0m0d"), 365),
       "9: execução unificada")
    ok(not rd.execucao_unificada(reg([c1, dict(c2, extinto="Sim")], [], "7a0m0d"), 365), "9: as demais penas extintas: não é unificada")
    r9 = reg([c1, c2], [ev("10/07/1999")], "7a0m0d", "", ger="05/10/2001")
    x9 = next(x for x in rd.avaliar(r9, HOJE)["decretos"] if str(x["id"]) == "2000")
    ok("extinção" not in (x9.get("mot") or "") + (x9.get("beneficio") or "") + (x9.get("ressalva") or ""),
       "9: unificada - sem extinção: %s | %s" % (x9.get("s"), x9.get("mot")))
    r9b = reg([c1], [ev("10/07/1999")], "1a0m0d", "", ger="05/10/2001")
    x9b = next(x for x in rd.avaliar(r9b, HOJE)["decretos"] if str(x["id"]) == "2000")
    ok("Extinção" in (x9b.get("beneficio") or ""), "9: pena única cumprida - extinção: %s | %s | %s" % (
        x9b.get("s"), x9b.get("beneficio"), x9b.get("mot")))
except Exception as e:
    import traceback
    traceback.print_exc()
    falhas.append("exceção: %r" % e)

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for f in falhas:
        print(" -", f)
    sys.exit(1)
print("teste_conf6_indulto: OK")
