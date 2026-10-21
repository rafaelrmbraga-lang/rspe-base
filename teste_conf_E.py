"""Teste da conferência manual de 20/10/2026 - frente E (indulto e comutação), com casos hipotéticos montados em dicionário
(nomes fictícios): fração do impeditivo só com o tempo posterior ao fato dele, fuga sem homologação a verificar, reincidência
pelas datas do RSPE, comutação anterior não descontada, formato anos/meses/dias, cumprimento interrompido x não iniciado, art. 76
do CP no Decreto 2022, comutação prejudicada só com indulto cabível, crime sem pena privativa, XV na tese da hediondez
superveniente e comutação sem as penas do XV.
Rodar: python teste_conf_E.py (sai com código 1 se algum caso falhar)."""
import re
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_decretos as rd
import rspe_scraper as rs

HOJE = date(2026, 10, 20)
falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def crime(fato, sent, tr, artigo="ART 155: Furto", tipo="CAPUT: Subtrair, para si ou para outrem, coisa alheia móvel, Reclusão: 1 a 4 anos E Multa",
          pena="1 ano(s), 0 mês(es) e 0 dia(s)", lei="2848/40 - Código Penal", proc="0000001-00.2020.8.12.0001", reinc="N", vga="N",
          extinto="Não", hed="N"):
    return {"processo_criminal": proc, "vara_condenacao": "1ª Vara Criminal", "data_infracao": fato, "data_sentenca": sent, "transito_mp": tr,
            "transito_processo": tr, "lei": lei, "artigo": artigo, "tipo_penal": tipo, "pena_imposta": pena, "pena_total_processo": "PENA ORIGINÁRIA",
            "regime_sentenca": "Fechado", "vga": vga, "resultado_morte": "N", "reincidente_comum": reinc, "reincidente_especifico": "N",
            "comando_orcrim": "N", "extinto": extinto, "suspenso": "Não", "hediondo_ou_equiparado": hed}


def ev(d, tipo="PRISÃO/INÍCIO DE CUMPRIMENTO", mot="PRISÃO DEFINITIVA", procs=""):
    return {"tipo": tipo, "motivo": mot, "data": d, "processos": procs}


def inc(tipo, compl, data, sit="CONCEDIDO", ref=None):
    return {"tipo": tipo, "complemento": compl, "data_decisao": data, "data_referencia": ref or data, "situacao": sit, "processos": ""}


def reg(crimes, eventos, pena_total, cumprida="", incid=None, ger="05/10/2026", regime="Fechado - ATIVO"):
    return {"nome": "T", "processo_execucao": "X", "pena_total": pena_total, "pena_cumprida": cumprida, "pena_remanescente": "",
            "data_geracao_rspe": ger, "termino_previsao_seeu": "", "data_nascimento": "01/01/1980", "_sexo": "M", "status_execucao": "ATIVO",
            "regime_atual": regime, "_crimes": crimes, "_eventos": eventos, "_incidentes": incid or []}


def dec(r, ano):
    return next(x for x in rd.avaliar(r, HOJE)["decretos"] if str(x["id"]) == ano)


TRAF = dict(artigo="ART 33: Tráfico de drogas", lei="11343/06 - Lei de Drogas", tipo="CAPUT: Importar, exportar, Reclusão: 5 a 15 anos E Multa", hed="S")

# ---- 1. fração do impeditivo: só o tempo posterior ao fato dele (art. 7º, p. ú.; LEP, art. 111, p. ú.) ----
d = rs.to_date
per = [(d("01/01/2015"), None)]
c_t = crime("01/07/2024", "01/10/2024", "01/11/2024", pena="6 ano(s), 0 mês(es) e 0 dia(s)", proc="0000002-00.2024.8.12.0001", **TRAF)
cimp, nota = rs.cumprido_imputavel_impeditivos([c_t], 4000, per, [], d("25/12/2025"))
ok(cimp == (d("25/12/2025") - d("01/07/2024")).days + 1 and "só conta o tempo posterior ao fato" in nota, "1: imputável %s | %s" % (cimp, nota))
# remição concedida depois do fato conta; a perda de remidos posterior ao fato sai dele até o remido contado (7.14.1, conferência:
# antes a perda não saía)
cimp2, _n = rs.cumprido_imputavel_impeditivos([c_t], 4000, per, [(d("01/03/2025"), 30), (d("02/03/2025"), -20)], d("25/12/2025"))
ok(cimp2 == cimp + 10, "1: remição posterior ao fato: %s x %s" % (cimp2, cimp))
# impeditivo de fato anterior ao início da custódia: nada muda
c_ant = dict(c_t, data_infracao="01/07/2014")
ok(rs.cumprido_imputavel_impeditivos([c_ant], 4000, per, [], d("25/12/2025")) == (4000, ""), "1: fato anterior à custódia mudou o cumprido")
# dois impeditivos: o antigo já cumprido e o novo sem tempo - o que falta é só o do novo
c_t0 = crime("01/01/2014", "01/06/2014", "01/07/2014", pena="5 ano(s), 0 mês(es) e 0 dia(s)", proc="0000003-00.2014.8.12.0001", **TRAF)
cimp3, _n = rs.cumprido_imputavel_impeditivos([c_t0, c_t], 4000, per, [], d("25/12/2025"))
exig = rs._dois_tercos(rs.pena_para_dias("5a0m0d") + rs.pena_para_dias("6a0m0d"))
ok(exig - cimp3 == rs._dois_tercos(rs.pena_para_dias("6a0m0d")) - cimp, "1: dois impeditivos: falta %s" % (exig - cimp3))

# análise de 2025: furto de 2014 + tráfico de 01/07/2024, presos desde 2015 - o "faltam" é o do tráfico novo
c_f = crime("01/01/2014", "01/06/2014", "01/07/2014", pena="3 ano(s), 0 mês(es) e 0 dia(s)", proc="0000004-00.2014.8.12.0001")
r = reg([c_f, c_t], [ev("01/01/2015")], "9a0m0d", "11a0m0d")
o = rs.analise_decretos(r, r["_crimes"], r["_eventos"], [], HOJE)
falta = rs._dois_tercos(rs.pena_para_dias("6a0m0d")) - cimp
ok(o["indulto_2025"].startswith("VEDADO") and ("faltam %s" % rs.dias_para_pena(falta)) in o["indulto_2025"]
   and "só conta o tempo posterior ao fato" in o.get("indulto_2025_detalhe", ""), "1 (2025): %s" % o["indulto_2025"])
ok(o["indulto_2025_imp"]["cumprido_imputavel"] == cimp, "1 (2025): imputável %s" % o.get("indulto_2025_imp"))

# ---- 2. fuga sem homologação na janela do art. 6º: a verificar (2023, 2024 e 2025) ----
evf = [ev("01/01/2023", mot="PRISÃO EM FLAGRANTE"), ev("10/06/2025", "INTERRUPÇÃO", "FUGA")]
firmes, verif = rs.falta_art6([], date(2025, 12, 25), evf, date(2025, 12, 23))
ok(not firmes and verif and "só impede se reconhecida" in verif[0], "2: fuga no indulto: %s | %s" % (firmes, verif))
F = {f["id"]: f for f in rd.fichas()}
ok(not rd.fuga_impede(F["2023"]) and rd.fuga_impede(F["2016"]), "2: regra da fuga por decreto")
cf = crime("01/01/2017", "01/06/2017", "01/07/2017", pena="4 ano(s), 0 mês(es) e 0 dia(s)")
x = dec(reg([cf], [ev("01/01/2018"), ev("01/06/2023", "INTERRUPÇÃO", "FUGA"), ev("10/06/2023", "REINÍCIO", "RECAPTURA")], "4a0m0d"), "2023")
ok(x["s"] != "nao" and "tratada como falta grave" not in (x.get("mot") or ""), "2: 2023 fuga sem homologação: %s %s" % (x["s"], x.get("mot")))

# ---- 3. reincidência pelas datas do RSPE (marcação "N" com condenação anterior transitada antes do fato) ----
ca = crime("01/01/2005", "01/06/2005", "01/07/2005", pena="2 ano(s), 0 mês(es) e 0 dia(s)", proc="0000005-00.2005.8.12.0001")
cb = crime("01/03/2008", "01/06/2008", "01/07/2008", pena="6 ano(s), 0 mês(es) e 0 dia(s)", proc="0000006-00.2008.8.12.0001")
ok(rs.reinc_pelas_datas([cb], [ca, cb]) is not None and rs.reinc_pelas_datas([ca], [ca, cb]) is None, "3: reincidência pelas datas")
# Decreto 8.172/2013, comutação: 1/4 (primário) ou 1/3 (reincidente) - cumprido entre os dois: não se afirma o "cabe"
r = reg([ca, cb], [ev("01/01/2011")], "8a0m0d", "5a9m0d", ger="05/10/2016")
x = dec(r, "2013")
ok(x["s"] != "cabe" and "reincid" in (x.get("mot") or "") + (x.get("ressalva") or ""), "3: 2013 como primário: %s %s" % (x["s"], x.get("mot")))
# 2024/2025: o "possível" calculado como primário fica a verificar
r = reg([dict(ca, data_infracao="01/01/2019", transito_mp="01/07/2019", transito_processo="01/07/2019", data_sentenca="01/06/2019"),
         dict(cb, data_infracao="01/03/2020", transito_mp="01/07/2020", transito_processo="01/07/2020", data_sentenca="01/06/2020",
              pena="2 ano(s), 0 mês(es) e 0 dia(s)")], [ev("01/01/2021")], "4a0m0d", "5a9m0d")
o = rs.analise_decretos(r, r["_crimes"], r["_eventos"], [], HOJE)
ok(not o["indulto_2024"].startswith("POSSÍVEL") and "transitou antes do fato" in o["indulto_2024"] + o.get("indulto_2024_detalhe", ""),
   "3 (2024): %s" % o["indulto_2024"])

# ---- 4. formato: nunca "11m33d" ----
ok(rs.dias_para_pena(7 * 365 + 363) == "7a11m28d" and rs.dias_para_pena(359) == "0a11m29d" and rs.dias_para_pena(360) == "0a11m25d",
   "4: %s / %s" % (rs.dias_para_pena(7 * 365 + 363), rs.dias_para_pena(360)))
ok(not any(re.search(r"m3\d d|m3\dd", rs.dias_para_pena(n)) for n in range(0, 3 * 365)), "4: sobrou dia acima de 29")

# ---- 4b. comutação anterior concedida: a redução sobre a soma das penas impostas é o valor máximo - o texto avisa ----
c4 = crime("01/01/2010", "01/06/2010", "01/07/2010", artigo="ART 157: Roubo", tipo="CAPUT: Subtrair coisa móvel alheia, mediante grave ameaça",
           pena="20 ano(s), 0 mês(es) e 0 dia(s)", proc="0000007-00.2010.8.12.0001", vga="S")
r = reg([c4], [ev("01/01/2011")], "20a0m0d", "8a9m0d", ger="05/10/2019",
        incid=[inc("COMUTAÇÃO", "DECRETO Nº 8.615, DE 23 DE DEZEMBRO DE 2015", "26/05/2016")])
x = dec(r, "2017")
ok(x.get("beneficio") == "Comutação" and "não está descontada" in (x.get("mot") or ""), "4b: comutação anterior: %s %s" % (x["s"], x.get("mot")))

# ---- 5. cumpriu pena e fugiu: "cumprimento interrompido", não "não iniciou o cumprimento" ----
c5 = crime("01/01/2022", "01/06/2022", "01/07/2022", pena="4 ano(s), 0 mês(es) e 0 dia(s)", proc="0000008-00.2022.8.12.0001")
r = reg([c5], [ev("01/08/2022", mot="PRISÃO EM FLAGRANTE"), ev("01/05/2025", "INTERRUPÇÃO", "FUGA")], "4a0m0d", "2a9m0d",
        incid=[inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Semiaberto - Progressão de Regime", "01/03/2024"),
               inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Fechado - Regressão Cautelar", "02/05/2025")])
o = rs.analise_decretos(r, r["_crimes"], r["_eventos"], r["_incidentes"], HOJE)
ok("não iniciou" not in o["indulto_2025"] and "não iniciou" not in o["comutacao_2025"], "5: %s | %s" % (o["indulto_2025"], o["comutacao_2025"]))

# ---- 6. Decreto 2022, art. 11, p. ú.: impeditivo de detenção e demais de reclusão - a ordem do CP, arts. 69 e 76, põe a detenção
# por último: imputar o tempo primeiro ao impeditivo é tese (a verificar), e o texto não invoca o art. 76 em sentido contrário ----
c6i = crime("01/01/2012", "01/06/2012", "01/07/2012", artigo="ART 150: Violação de domicílio",
            tipo="§ 1º: Se o crime é cometido durante a noite, Detenção: 6 meses a 2 anos", pena="0 ano(s), 8 mês(es) e 0 dia(s)",
            proc="0000009-00.2012.8.12.0001", vga="S")
c6f = [crime("01/01/2012", "01/06/2012", "01/07/2012", pena="4 ano(s), 0 mês(es) e 0 dia(s)", proc="000001%d-00.2012.8.12.0001" % i) for i in range(4)]
r = reg([c6i] + c6f, [ev("01/01/2013")], "16a8m0d", "9a11m0d", ger="05/10/2022")
o = rs.analise_decreto_2022(r, r["_crimes"], r["_eventos"], [])
ok("a pena mais grave se executa primeiro" not in o.get("indulto_2022_detalhe", ""), "6: art. 76 em sentido contrário")
ok(o["indulto_2022_status"] != "possivel" and "arts. 69 e 76" in o.get("indulto_2022_detalhe", ""), "6: %s" % o["indulto_2022"])

# ---- 7. crime sem pena privativa (porte para consumo; LCP, art. 68, caput): não é "pena não informada" nem alcançado pelo art. 5º ----
c28 = crime("01/01/2020", "01/06/2020", "01/07/2020", artigo="ART 28: Porte para consumo", lei="11343/06 - Lei de Drogas",
            tipo="CAPUT: Quem adquirir, guardar", pena="0 ano(s), 0 mês(es) e 0 dia(s)")
c68 = crime("01/01/2020", "01/06/2020", "01/07/2020", artigo="ART 68: Recusa de autoridade", lei="3688/41 - Lei das Contravenções Penais",
            tipo="CAPUT: Revogado, Prisão Simples: 1 a 1 dias Sem Multa", pena="0 ano(s), 0 mês(es) e 0 dia(s)")
ok(rs.sem_pena_privativa(c28) and rs.sem_pena_privativa(c68) and not rs.sem_pena_privativa(c5), "7: sem pena privativa")
cs = [c68, dict(c68, artigo="ART 155: Furto", lei="2848/40 - Código Penal", tipo="CAPUT: Subtrair, Reclusão: 1 a 4 anos")]
rs.penas_dos_crimes(cs)
ok(not cs[0].get("pena_nao_informada"), "7: LCP 68 tratado como pena não informada")
r = reg([c28, crime("01/01/2020", "01/06/2020", "01/07/2020", proc="0000020-00.2020.8.12.0001")], [ev("01/01/2021")], "1a0m0d", "1a0m0d", ger="05/10/2022")
o = rs.analise_decreto_2022(r, r["_crimes"], r["_eventos"], [])
ok(not re.search(r"✓ art\. 28 Lei 11\.343", o.get("indulto_2022_detalhe", "")), "7: art. 28 alcançado pelo art. 5º")

# ---- 8. comutação "prejudicada: indulto cabível" só com o indulto cabível; Decreto 2022 sem comutação a recuperar ----
ok(not rd._tem_comutacao({}, {"id": "2022"}) and rd._tem_comutacao({}, {"id": "2019"}), "8: comutação de 2022")

# ---- 9. hediondez superveniente em concurso: pela tese, o XV do furto (sem fração) não fica travado ----
c9r = crime("01/06/2018", "01/06/2019", "01/07/2019", artigo="ART 157: Roubo",
            tipo="§ 2º-A, I: (Até 22.01.2020) Se a violência ou ameaça é exercida com emprego de arma de fogo, Reclusão: 6 anos e 8 meses a 16 anos e 8 meses E Multa",
            pena="6 ano(s), 0 mês(es) e 0 dia(s)", proc="0000030-00.2012.8.12.0001", vga="S")
c9t = crime("01/01/2012", "01/01/2019", "01/02/2019", pena="5 ano(s), 0 mês(es) e 0 dia(s)", proc="0000031-00.2012.8.12.0001", **TRAF)
c9f = crime("01/01/2012", "01/01/2019", "01/02/2019", pena="2 ano(s), 0 mês(es) e 0 dia(s)", proc="0000032-00.2012.8.12.0001")
r = reg([c9r, c9t, c9f], [ev("01/06/2019")], "13a0m0d", "6a4m5d", ger="05/10/2025")
o = rs.analise_decretos(r, r["_crimes"], r["_eventos"], [], HOJE)
imp_sup = [c for c in r["_crimes"] if rs.impeditivo_decreto(c, date(2024, 12, 25)) and "fato anterior" in rs.impeditivo_decreto(c, date(2024, 12, 25))[1]]
ok(imp_sup and o["indulto_2024"].startswith("A VERIFICAR (tese: hediondez superveniente)"), "9: tese da hediondez superveniente com o XV do furto: %s" % o["indulto_2024"])

# ---- 10. pena considerada: diferença de poucos dias da conversão (365 x 12 meses de 30) - vale a soma das penas impostas ----
c10i = crime("01/01/2013", "01/06/2013", "01/07/2013", pena="14 ano(s), 8 mês(es) e 0 dia(s)", proc="0000040-00.2017.8.12.0001", **TRAF)
c10l = crime("01/01/2017", "01/06/2017", "01/07/2017", artigo="ART 129: Lesão corporal", tipo="CAPUT: Ofender a integridade corporal, Detenção: 3 meses a 1 ano",
             pena="0 ano(s), 4 mês(es) e 0 dia(s)", proc="0000041-00.2017.8.12.0001")
r = reg([c10i, c10l], [ev("01/01/2014")], "15a0m0d", "11a10m0d")
o = rs.analise_decretos(r, r["_crimes"], r["_eventos"], [], HOJE)
ok("pena 0a4m0d" in o.get("indulto_2024_detalhe", "") and "0a4m5d" not in o.get("indulto_2024_detalhe", "") + o.get("comutacao_2024_detalhe", ""),
   "10: pena considerada com os 5 dias da conversão: %s" % o.get("indulto_2024_detalhe", "")[:300])

# ---- 11. concurso: o tempo além dos 2/3 do impeditivo cobre a pena dos demais - não vira "pedir a extinção pelo cumprimento" ----
out = [{"id": "2016", "ref": "25/12/2016", "s": "cabe", "beneficio": "Indulto", "mot": "cumpriu",
        "detalhe": {"pena": 3000, "cumprido": 2500, "pena_conc": 365, "cumprido_conc": 500}}]
rd._pena_cumprida_aba(out, {})
ok(out[0]["s"] == "cabe" and out[0]["beneficio"] == "Indulto", "11: %s" % out[0])
rr = {"indulto_2024": "POSSÍVEL (crimes não impeditivos, art. 7º, p. ú.): art. 9º, I", "indulto_2024_num": {"pena": 410, "cumprido": 900},
      "indulto_2024_imp": {"pena_imp": 2460, "exigido": 1640}}
rd.pena_cumprida_decretos(rr)
ok(rr["indulto_2024"].startswith("POSSÍVEL") and "extinção parcial pelo cumprimento é tese" in rr.get("indulto_2024_detalhe", ""), "11 (2024): %s" % rr["indulto_2024"])

# ---- 12. impeditivo sem trânsito para a acusação na publicação (art. 2º, II): a vedação dos demais depende dele - a verificar,
# sem virar "cabe quanto aos crimes com trânsito" ----
c12t = dict(c_t, data_sentenca="01/10/2025", transito_mp="01/02/2026", transito_processo="01/02/2026")
r = reg([c_f, c12t], [ev("01/01/2015")], "9a0m0d", "11a0m0d")
o = rs.analise_decretos(r, r["_crimes"], r["_eventos"], [], HOJE)
ok(o["indulto_2025"].startswith("A VERIFICAR (art. 2º, II): art. 7º, p. ú.") and o["indulto_2025_status"] == "verificar"
   and o["comutacao_2025"].startswith("A VERIFICAR"), "12: %s | %s" % (o["indulto_2025"], o["comutacao_2025"]))

if falhas:
    print("FALHOU: conferência 20/10 - frente E (indulto e comutação)\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: conferência 20/10 - frente E (fração do impeditivo só com o tempo posterior ao fato, fuga sem homologação a verificar, "
      "reincidência pelas datas, comutação anterior, formato a/m/d, cumprimento interrompido, art. 76 do CP em 2022, crime sem pena "
      "privativa, XV na tese, pena considerada, extinção parcial como tese)")
