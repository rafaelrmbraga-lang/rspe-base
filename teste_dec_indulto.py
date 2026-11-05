"""Teste das decisões de 05/11/2026 sobre os pareceres de indulto e comutação (P30 a P44, P54 e as linhas do P57 dos casos
S6xxx e S7xxx), com casos fictícios montados em dicionário.
Rodar: python teste_dec_indulto.py (sai com código 1 se algum caso falhar)."""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_decretos as rd
import rspe_indulto_tl as tl
import rspe_scraper as rs

HOJE = date(2026, 11, 5)
falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def crime(fato, sent, tr, artigo="ART 155: Furto", tipo="CAPUT: Subtrair, para si ou para outrem, coisa alheia móvel, Reclusão: 1 a 4 anos E Multa",
          pena="1 ano(s), 0 mês(es) e 0 dia(s)", lei="2848/40 - Código Penal", proc="0000001-00.2020.8.12.0001", vga="N", regime="Fechado"):
    return {"processo_criminal": proc, "vara_condenacao": "1ª Vara Criminal", "data_infracao": fato, "data_sentenca": sent, "transito_mp": tr,
            "transito_processo": tr, "lei": lei, "artigo": artigo, "tipo_penal": tipo, "pena_imposta": pena, "pena_total_processo": "PENA ORIGINÁRIA",
            "regime_sentenca": regime, "vga": vga, "resultado_morte": "N", "reincidente_comum": "N", "reincidente_especifico": "N",
            "comando_orcrim": "N", "extinto": "Não"}


def ev(d, tipo="PRISÃO/INÍCIO DE CUMPRIMENTO", mot="PRISÃO DEFINITIVA", procs=""):
    return {"tipo": tipo, "motivo": mot, "data": d, "processos": procs}


def inc(tipo, compl, dec_, ref=None, sit="CONCEDIDO"):
    return {"tipo": tipo, "complemento": compl, "data_decisao": dec_, "data_referencia": ref or dec_, "situacao": sit, "processos": ""}


def reg(crimes, eventos, pena_total, cumprida="", incid=None, ger="05/10/2026", regime="Fechado - ATIVO", sexo="M"):
    return {"nome": "T", "processo_execucao": "X", "pena_total": pena_total, "pena_cumprida": cumprida, "pena_remanescente": "",
            "data_geracao_rspe": ger, "termino_previsao_seeu": "", "data_nascimento": "01/01/1980", "_sexo": sexo, "status_execucao": "ATIVO",
            "regime_atual": regime, "_crimes": crimes, "_eventos": eventos, "_incidentes": incid or []}


def novos(r):
    return rs.analise_decretos(r, r["_crimes"], r["_eventos"], r["_incidentes"], HOJE)


def dec(r, ano):
    return next(x for x in rd.avaliar(r, HOJE)["decretos"] if str(x["id"]) == ano)


ROUBO = dict(artigo="ART 157: Roubo", tipo="CAPUT: Subtrair coisa móvel alheia, mediante grave ameaça ou violência a pessoa, Reclusão: 4 a 10 anos E Multa", vga="S")
PRIV = dict(artigo="ART 33: Tráfico de drogas", lei="11343/06 - Lei de Drogas", tipo="§ 4º: tráfico privilegiado, Reclusão: 5 a 15 anos E Multa")

# ---- P31: falta homologada mais de 6 meses depois do fato - nota de mora estatal, sem mudar o resultado ----
c = crime("01/06/2022", "01/10/2022", "01/11/2022", pena="2 ano(s), 0 mês(es) e 0 dia(s)")
fal = inc("HOMOLOGAÇÃO DE FALTA GRAVE", "01/04/2024", "15/12/2024", ref="01/04/2024")
o = novos(reg([c], [ev("01/01/2023")], "2a0m0d", incid=[fal]))
ok("mora estatal" in o["indulto_2024"] and o["indulto_2024_status"] == "nao", "P31 nota: %s (%s)" % (o["indulto_2024"], o["indulto_2024_status"]))
fal2 = inc("HOMOLOGAÇÃO DE FALTA GRAVE", "01/04/2024", "01/06/2024", ref="01/04/2024")
o = novos(reg([c], [ev("01/01/2023")], "2a0m0d", incid=[fal2]))
ok("mora estatal" not in o["indulto_2024"] and o["indulto_2024_status"] == "nao", "P31 sem nota (2 meses): %s" % o["indulto_2024"])
ok(rs.nota_mora_estatal([fal], ["HOMOLOGAÇÃO DE FALTA GRAVE 01/04/2024"])[0].endswith("(STJ, Tema 1195)"), "P31 função")

# ---- P35: roubo e furto no concurso - nota do STJ (não se fraciona a execução nos incisos I e II) ----
c1 = crime("01/06/2022", "01/10/2022", "01/11/2022", pena="4 ano(s), 0 mês(es) e 0 dia(s)", proc="0000002-00.2022.8.12.0001", **ROUBO)
c2 = crime("01/06/2022", "01/10/2022", "01/11/2022", pena="1 ano(s), 0 mês(es) e 0 dia(s)", proc="0000003-00.2022.8.12.0001")
o = novos(reg([c1, c2], [ev("01/01/2023")], "5a0m0d"))
ok("1.010.942" in (o.get("indulto_2024_detalhe") or "") and "1.006.334" in (o.get("indulto_2024_detalhe") or ""), "P35 nota: %s" % o.get("indulto_2024_detalhe"))
o = novos(reg([c1], [ev("01/01/2023")], "4a0m0d"))
ok("1.010.942" not in (o.get("indulto_2024_detalhe") or ""), "P35: nota sem concurso")

# ---- P36: comutação do Decreto 11.846/2023 concedida depois de 25/12/2024 - tese do § 2º, a verificar ----
c = crime("01/06/2022", "01/10/2022", "01/11/2022", pena="8 ano(s), 0 mês(es) e 0 dia(s)", artigo="ART 297: Falsificação de documento público",
          tipo="CAPUT: Falsificar, no todo ou em parte, documento público, Reclusão: 2 a 6 anos E Multa")
com23 = inc("COMUTAÇÃO DE PENA", "Decreto 11.846/2023", "10/03/2025")
o = novos(reg([c], [ev("01/09/2024")], "8a0m0d", incid=[com23]))
ok(o["comutacao_2024"].startswith("A VERIFICAR (tese): art. 13, § 2º"), "P36: %s" % o["comutacao_2024"])
o = novos(reg([c], [ev("01/09/2024")], "8a0m0d"))
ok(o["comutacao_2024"].startswith("não atinge"), "P36 sem comutação anterior: %s" % o["comutacao_2024"])
com25 = inc("COMUTAÇÃO DE PENA", "Decreto 12.790/2025", "10/03/2026")
o = novos(reg([c], [ev("01/09/2024")], "8a0m0d", incid=[com25]))
ok(o["comutacao_2024"].startswith("não atinge"), "P36: comutação de decreto posterior não serve: %s" % o["comutacao_2024"])

# ---- P37: aberto como regime inicial e o VIII como único inciso atendido - a verificar (a 6ª Turma aplica o VII) ----
c = crime("01/01/2024", "01/06/2024", "01/07/2024", pena="5 ano(s), 0 mês(es) e 0 dia(s)", artigo="ART 297: Falsificação de documento público",
          tipo="CAPUT: Falsificar, no todo ou em parte, documento público, Reclusão: 2 a 6 anos E Multa", regime="Aberto")
r = reg([c], [ev("01/10/2024")], "5a0m0d", regime="Aberto - ATIVO", incid=[inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Aberto - Regime Inicial", "", ref="01/10/2024")])
o = novos(r)
ok(o["indulto_2024_status"] == "verificar" and "VIII" in o["indulto_2024"], "P37: %s" % o["indulto_2024"])

# ---- P39: resto de 360 a 364 dias com o total em dias ----
ok(tl._pena(364) == "0a11m29d (364 dias)" and tl._pena(359) == "0a11m29d", "P39 _pena: %s / %s" % (tl._pena(364), tl._pena(359)))
ok(tl._pena_ext(tl._pena(729)) == "1 ano, 11 meses e 29 dias (729 dias)", "P39 extenso: %s" % tl._pena_ext(tl._pena(729)))
ok(tl._ext_txt("cumpriu 0a11m25d (360 dias).") == "cumpriu 11 meses e 25 dias (360 dias).", "P39 _ext_txt: %s" % tl._ext_txt("cumpriu 0a11m25d (360 dias)."))

# ---- P41: indulto concedido no RSPE - o dispositivo é o da decisão ----
c = crime("01/06/2010", "01/10/2010", "01/11/2010", pena="2 ano(s), 0 mês(es) e 0 dia(s)")
r = reg([c], [ev("01/01/2011")], "2a0m0d", incid=[inc("INDULTO", "Decreto 7.648/2011", "10/03/2012")])
x = dec(r, "2011")
ok(x["s"] == "conc" and x.get("dispositivo") == "conforme decisão do RSPE", "P41: %s %s" % (x["s"], x.get("dispositivo")))

# ---- P42: Decreto 6.294/2007 veda o art. 33 sem falar do § 4º - tráfico privilegiado a verificar (tese), não vedado ----
c = crime("01/01/2007", "01/03/2007", "01/04/2007", pena="1 ano(s), 8 mês(es) e 0 dia(s)", **PRIV)
x = dec(reg([c], [ev("01/01/2007")], "1a8m0d"), "2007")
ok(x["s"] == "ver" and "Súmula Vinculante 63" in (x.get("mot") or ""), "P42 (2007): %s %s" % (x["s"], x.get("mot")))
x = dec(reg([crime("01/01/2019", "01/03/2019", "01/04/2019", pena="1 ano(s), 8 mês(es) e 0 dia(s)", **PRIV)], [ev("01/01/2019")], "1a8m0d"), "2019")
ok(x["s"] in ("imp", "nao"), "P42: 2019 veda expressamente o privilegiado: %s %s" % (x["s"], x.get("mot")))

# ---- P43: "não cabe" com hipótese não aferida (2016, art. 3º, II: 1/6 nas situações do art. 1º, § 1º) - sinal ----
# furto 3 anos (1.095 dias), preso em 01/09/2016: cumpriu 116 dias em 25/12/2016 - abaixo de 1/4 (273) e de 1/6 (182)? não: usa 200 dias
c = crime("01/05/2016", "01/06/2016", "01/07/2016", pena="3 ano(s), 0 mês(es) e 0 dia(s)")
x = dec(reg([c], [ev("09/06/2016")], "3a0m0d"), "2016")
ok(x["s"] == "nao" and "art. 3º, II" in (x.get("naf") or []) and "não aferida" in (x.get("ressalva") or ""), "P43: %s %s %s" % (x["s"], x.get("naf"), x.get("ressalva")))
# caso S7037: tráfico privilegiado em 2016 (art. 4º só nas situações do art. 1º, § 1º), 1/4 cumprido - a verificar
c = crime("01/03/2016", "29/07/2016", "27/09/2016", pena="3 ano(s), 0 mês(es) e 0 dia(s)", **PRIV)
x = dec(reg([c], [ev("01/03/2016")], "3a0m0d"), "2016")
ok(x["s"] == "ver" and x.get("dispositivo") == "art. 4º", "S7037: %s %s %s" % (x["s"], x.get("dispositivo"), x.get("mot")))

# ---- P44: falta no dia da publicação (2016: "anteriores à publicação") fora da janela; em 2015 ("contados retroativamente"), dentro ----
c = crime("01/01/2015", "01/03/2015", "01/04/2015", pena="2 ano(s), 0 mês(es) e 0 dia(s)")
f16 = inc("HOMOLOGAÇÃO DE FALTA GRAVE", "23/12/2016", "10/01/2017", ref="23/12/2016")
x = dec(reg([c], [ev("01/04/2015")], "2a0m0d", incid=[f16]), "2016")
ok("falta grave" not in (x.get("mot") or "").lower(), "P44 (2016, dia da publicação): %s %s" % (x["s"], x.get("mot")))
f16b = inc("HOMOLOGAÇÃO DE FALTA GRAVE", "22/12/2016", "10/01/2017", ref="22/12/2016")
x = dec(reg([c], [ev("01/04/2015")], "2a0m0d", incid=[f16b]), "2016")
ok(x["s"] == "nao" and "falta grave" in (x.get("mot") or "").lower(), "P44 (2016, véspera): %s %s" % (x["s"], x.get("mot")))
ok(rd.falta_antes_da_publicacao(next(f for f in rd.fichas() if f["id"] == "2016"))
   and not rd.falta_antes_da_publicacao(next(f for f in rd.fichas() if f["id"] == "2014")), "P44: decretos com a redação 'anteriores à publicação'")

# ---- S7007: Decreto 4.495/2002, art. 7º, § 2º - tráfico com pena de até 4 anos continua impeditivo (ADI 2.795 MC) ----
c = crime("10/03/2001", "07/08/2001", "06/10/2001", pena="3 ano(s), 0 mês(es) e 0 dia(s)", lei="6368/76 - Lei de Tóxicos", artigo="ART 12: Tráfico",
          tipo="CAPUT: tráfico de entorpecentes, Reclusão: 3 a 15 anos")
x = dec(reg([c], [ev("10/03/2001")], "3a0m0d"), "2002")
ok(x["s"] == "imp" and "ADI 2.795" in (x.get("mot") or ""), "S7007: %s %s" % (x["s"], x.get("mot")))

# ---- S6073: o SEEU conta 100 dias a mais, sem data - comutação a verificar (pode ser detração anterior), e não negada ----
c = crime("01/06/2023", "18/12/2023", "16/02/2024", pena="6 ano(s), 0 mês(es) e 0 dia(s)", **ROUBO)
r = reg([c], [ev("22/11/2023")], "6a0m0d", cumprida="3a1m24d")
o = novos(r)
ok(o["comutacao_2024"].startswith("A VERIFICAR") and "sem data" in o["comutacao_2024"], "S6073 comutação: %s" % o["comutacao_2024"])
r2 = reg([c], [ev("22/11/2023")], "6a0m0d", cumprida="2a10m15d")  # o SEEU bate com os eventos: não atinge
o = novos(r2)
ok(o["comutacao_2024"].startswith("não atinge"), "S6073 sem tempo a mais: %s" % o["comutacao_2024"])

# ---- P34: fundamentação pronta com a tese da hediondez posterior ao fato (roubo com arma de fogo antes da Lei 13.964/2019) ----
c = crime("01/06/2019", "01/10/2019", "01/11/2019", pena="5 ano(s), 4 mês(es) e 0 dia(s)",
          artigo="ART 157: Roubo", tipo="§ 2º-A, I: emprego de arma de fogo, Reclusão: 4 a 10 anos E Multa", vga="S")
r = reg([c], [ev("01/06/2019")], "5a4m0d")
L = tl.linha(dict(r, **{k: v for k, v in novos(r).items()}), HOJE)
d24 = next((d for d in L.get("decretos") or [] if d.get("id") == "2024"), None)
fund = ((d24 or {}).get("indulto") or {}).get("fundamentacao") or ""
ok("IRRETROATIVIDADE" in fund and "1603891-45.2026" in fund and "subsidiariamente" in fund, "P34: %s" % fund[-600:])

if falhas:
    print("FALHOU: decisões de 05/11/2026 - indulto")
    for f in falhas:
        print("  " + f)
    sys.exit(1)
print("ok: decisões de 05/11/2026 - indulto (mora estatal, concurso com violência, comutação anterior posterior, restos de 360 a 364 dias, "
      "decisão do RSPE, privilegiado em 2007, hipótese não aferida, falta no dia da publicação, 2002 art. 7º, § 2º, tempo sem data do SEEU, "
      "tese da hediondez posterior)")
