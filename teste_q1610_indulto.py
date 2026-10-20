"""Teste dos quesitos de 16/10/2026 - grupo indulto e comutação (itens 76 a 99, 127, 140 e 158), com casos hipotéticos montados
em dicionário (nomes fictícios).
Rodar: python teste_q1610_indulto.py (sai com código 1 se algum caso falhar)."""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_decretos as rd
import rspe_export as rx
import rspe_ficha as rf
import rspe_indulto_tl as tl
import rspe_scraper as rs

HOJE = date(2026, 10, 16)
falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def crime(fato, sent, tr, artigo="ART 155: Furto", tipo="CAPUT: Subtrair, para si ou para outrem, coisa alheia móvel, Reclusão: 1 a 4 anos E Multa",
          pena="1 ano(s), 0 mês(es) e 0 dia(s)", vara="1ª Vara Criminal", lei="2848/40 - Código Penal", proc="0000001-00.2020.8.12.0001",
          reinc="N"):
    return {"processo_criminal": proc, "vara_condenacao": vara, "data_infracao": fato, "data_sentenca": sent, "transito_mp": tr, "transito_processo": tr,
            "lei": lei, "artigo": artigo, "tipo_penal": tipo, "pena_imposta": pena, "pena_total_processo": "PENA ORIGINÁRIA", "regime_sentenca": "Fechado",
            "vga": "N", "resultado_morte": "N", "reincidente_comum": reinc, "reincidente_especifico": "N", "comando_orcrim": "N", "extinto": "Não"}


def ev(d, tipo="PRISÃO/INÍCIO DE CUMPRIMENTO", mot="PRISÃO DEFINITIVA", procs=""):
    return {"tipo": tipo, "motivo": mot, "data": d, "processos": procs}


def inc(tipo, compl, data, sit="CONCEDIDO", ref=None):
    return {"tipo": tipo, "complemento": compl, "data_decisao": data, "data_referencia": ref or data, "situacao": sit, "processos": ""}


def reg(crimes, eventos, pena_total, cumprida="", incid=None, ger="05/10/2026", nasc="01/01/1980"):
    return {"nome": "T", "processo_execucao": "X", "pena_total": pena_total, "pena_cumprida": cumprida, "pena_remanescente": "",
            "data_geracao_rspe": ger, "termino_previsao_seeu": "", "data_nascimento": nasc, "_sexo": "M", "status_execucao": "ATIVO",
            "regime_atual": "Fechado - ATIVO", "_crimes": crimes, "_eventos": eventos, "_incidentes": incid or []}


def dec(r, ano):
    return next(x for x in rd.avaliar(r, HOJE)["decretos"] if str(x["id"]) == ano)


TRAF = dict(artigo="ART 33: Tráfico de drogas", lei="11343/06 - Lei de Drogas", tipo="CAPUT: Importar, exportar, Reclusão: 5 a 15 anos E Multa")

# ---- 76: teto do inciso no concurso com impeditivo - medido só sobre os não impeditivos, a soma total o excede: a verificar ----
# Decreto 7.420/2010, art. 1º, I (pena até 8 anos, 1/3): tráfico 6 anos + furto 3 anos (soma 9); 2/3 do tráfico e 1/3 do furto cumpridos
c_t = crime("01/01/2004", "01/06/2004", "01/07/2004", pena="6 ano(s), 0 mês(es) e 0 dia(s)", proc="0000002-00.2004.8.12.0001", **TRAF)
c_f = crime("01/01/2004", "01/06/2004", "01/07/2004", pena="3 ano(s), 0 mês(es) e 0 dia(s)", proc="0000003-00.2004.8.12.0001")
x = dec(reg([c_t, c_f], [ev("01/01/2005")], "9a0m0d"), "2010")
# o indulto (teto atendido só sobre os não impeditivos) fica a verificar; a comutação, sem teto, segue cabível com a ressalva
ok(x.get("beneficio") != "Indulto" and "teto" in (x.get("ressalva") or "") + (x.get("mot") or "") and "soma" in (x.get("ressalva") or "") + (x.get("mot") or ""),
   "76 (motor): %s %s %s" % (x["s"], x.get("mot"), x.get("ressalva")))
# 2024: tráfico 7 anos + porte de arma 6 anos (soma 13): I (até 8) e II (até 12) só sobre os não impeditivos - a verificar
c_t2 = crime("01/01/2017", "01/06/2017", "01/07/2017", pena="7 ano(s), 0 mês(es) e 0 dia(s)", proc="0000004-00.2017.8.12.0001", **TRAF)
c_f2 = crime("01/01/2017", "01/06/2017", "01/07/2017", pena="6 ano(s), 0 mês(es) e 0 dia(s)", proc="0000005-00.2017.8.12.0001",
             artigo="ART 16: Posse ou porte ilegal de arma de fogo de uso restrito", lei="10826/03 - Estatuto do Desarmamento",
             tipo="CAPUT: Possuir, deter, portar arma de fogo de uso restrito, Reclusão: 3 a 6 anos E Multa")
r = reg([c_t2, c_f2], [ev("01/01/2017")], "13a0m0d", "9a9m15d")
o = rs.analise_decretos(r, r["_crimes"], r["_eventos"], [], HOJE)
ok(o["indulto_2024_status"] != "possivel" and "sobre a soma total" in (o.get("indulto_2024_detalhe") or ""), "76 (2024): %s" % o["indulto_2024"])

# ---- 77: prisão provisória registrada para outro processo dentro do período contado: a verificar ----
c77 = crime("01/01/2015", "01/06/2015", "01/07/2015", pena="4 ano(s), 0 mês(es) e 0 dia(s)", proc="0000006-00.2015.8.12.0001")
r = reg([c77], [ev("01/01/2016", mot="PRISÃO EM FLAGRANTE", procs="0000999-00.2016.8.12.0001")], "4a0m0d")
ok("outro processo" in rd.custodia_outro_processo(r, date(2017, 12, 25), [c77]), "77: custódia por outro processo não detectada")
r2 = reg([c77], [ev("01/01/2016", mot="PRISÃO EM FLAGRANTE", procs="0000006-00.2015.8.12.0001")], "4a0m0d")
ok(rd.custodia_outro_processo(r2, date(2017, 12, 25), [c77]) == "", "77: prisão pelo próprio processo virou dúvida")
x = dec(r, "2017")
ok(x["s"] != "cabe", "77 (2017): custódia de outro processo deu cabe: %s %s" % (x["s"], x.get("mot")))

# ---- 78: Decreto 6.706/2008 - tráfico privilegiado ressalvado "desde que não configurada a mercancia": a verificar ----
c78 = crime("01/01/2007", "01/06/2007", "01/07/2007", pena="1 ano(s), 8 mês(es) e 0 dia(s)", proc="0000007-00.2007.8.12.0001",
            artigo="ART 33: Tráfico de drogas", lei="11343/06 - Lei de Drogas", tipo="§ 4º: tráfico privilegiado, Reclusão: 5 a 15 anos E Multa")
x = dec(reg([c78], [ev("01/01/2008")], "1a8m0d"), "2008")
ok(x["s"] == "ver" and "mercancia" in (x.get("mot") or ""), "78: %s %s" % (x["s"], x.get("mot")))

# ---- 79: comutação de decreto anterior não decidida: tese a verificar no decreto que a concede "independentemente de pedido" ----
out = [{"id": "2011", "ano": 2011, "ref": "25/12/2011", "s": "cabe", "beneficio": "Comutação"},
       {"id": "2013", "ano": 2013, "numero": "8.172", "ref": "25/12/2013", "s": "nao", "mot": "x"}]
rd._tese_comutacoes_anteriores(out, {f["id"]: f for f in rd.fichas()}, {})
ok("tese (a verificar)" in (out[1].get("ressalva") or "") and "2011" in out[1]["ressalva"] and out[1]["s"] == "nao", "79: %s" % out[1])
out[1].pop("ressalva", None)
rd._tese_comutacoes_anteriores(out, {f["id"]: f for f in rd.fichas()}, {("2011", "comutacao"): ("conc", "01/01/2012", "")})
ok(not out[1].get("ressalva"), "79: comutação já decidida entrou na tese")

# ---- 80: pena abaixo do mínimo cominado do tipo cadastrado (art. 306 do CP com 7 meses) - 2022 a verificar, não "não atinge" ----
c80 = crime("01/01/2020", "01/06/2020", "01/07/2020", artigo="ART 306: Fraude de lei sobre estrangeiro", pena="0 ano(s), 7 mês(es) e 0 dia(s)",
            tipo="CAPUT: Usar o estrangeiro, para entrar ou permanecer no território nacional, nome que não é o seu, Reclusão: 2 a 6 anos E Multa")
o = rs.analise_decreto_2022({"pena_total": "0a7m0d"}, [c80], [], [])
ok(o["indulto_2022_status"] == "verificar" and "mínimo cominado" in o["indulto_2022_detalhe"], "80: %s" % o["indulto_2022"])
ok(rs.pena_minima_abstrata(c80) == 2 * 365, "80: mínimo lido %s" % rs.pena_minima_abstrata(c80))

# ---- 82: art. 1º, XVII (2024/2025) - só os crimes das leis citadas; ameaça em contexto doméstico fica a verificar ----
c82 = crime("01/01/2019", "01/06/2019", "01/07/2019", artigo="ART 147: Ameaça", tipo="CAPUT: Ameaçar alguém, Detenção: 1 a 6 meses",
            pena="0 ano(s), 3 mês(es) e 0 dia(s)", vara="Vara de Violência Doméstica e Familiar contra a Mulher")
ok(rs.impeditivo_decreto(c82, date(2024, 12, 25)) is None and rs.vd_fora_xvii(c82), "82: ameaça em contexto doméstico vedada")
c82b = crime("01/01/2019", "01/06/2019", "01/07/2019", artigo="ART 24-A: Descumprimento de medida protetiva", lei="11340/06 - Lei Maria da Penha",
             tipo="CAPUT: Descumprir decisão judicial, Detenção: 3 meses a 2 anos", pena="0 ano(s), 3 mês(es) e 0 dia(s)")
ok(rs.impeditivo_decreto(c82b, date(2024, 12, 25)) and rs.impeditivo_decreto(c82b, date(2024, 12, 25))[0] == "XVII", "82: crime da Lei 11.340 deixou de ser vedado")
r = reg([c82], [ev("01/01/2023")], "0a3m0d", "0a3m0d")
o = rs.analise_decretos(r, r["_crimes"], r["_eventos"], [], HOJE)
ok(not o["indulto_2024"].startswith("VEDAD") and o["indulto_2024_status"] in ("verificar", "nao"), "82 (2024): %s" % o["indulto_2024"])

# ---- 83: art. 2º, II - cabe quanto aos crimes com trânsito; o sem trânsito para a acusação fica a conferir ----
c83a = crime("01/01/2018", "01/06/2018", "01/07/2018", pena="2 ano(s), 0 mês(es) e 0 dia(s)", proc="0000008-00.2018.8.12.0001")
# (fato anterior ao trânsito de c83a: sem reincidência pelas datas, que deixaria o "possível" a verificar - 7.13.0)
c83b = crime("01/03/2018", "01/06/2024", "01/02/2025", pena="1 ano(s), 0 mês(es) e 0 dia(s)", proc="0000009-00.2023.8.12.0001")
r = reg([c83a, c83b], [ev("01/01/2019")], "3a0m0d", "3a0m0d")
o = rs.analise_decretos(r, r["_crimes"], r["_eventos"], [], HOJE)
ok(o["indulto_2024"].startswith("POSSÍVEL (crimes com trânsito") and o["indulto_2024_status"] == "possivel", "83: %s" % o["indulto_2024"])

# ---- 87: comutação concedida e indulto do mesmo decreto (2000 a 2023) cabível: o indulto aparece como pedido possível ----
c87 = crime("01/01/2014", "01/06/2014", "01/07/2014", pena="6 ano(s), 0 mês(es) e 0 dia(s)", proc="0000010-00.2014.8.12.0001")
base87 = reg([c87], [ev("01/01/2015")], "6a0m0d")
x0 = dec(base87, "2017")
x = dec(dict(base87, _incidentes=[inc("COMUTAÇÃO", "DECRETO Nº 9.246, DE 21 DE DEZEMBRO DE 2017", "01/03/2018")]), "2017")
ok(x0["s"] != "cabe" or (x["s"] == "cabe" and x.get("beneficio") == "Indulto" and "comutação concedida" in (x.get("ressalva") or "")),
   "87: indulto escondido pela comutação concedida: %s / sem decisão %s" % (x, x0.get("s")))

# ---- 88: inciso XIII - só a conclusão certificada expressa ----
ok(rf.conclusao_certificada("CERTIFICADO DE CONCLUSÃO DO ENSINO FUNDAMENTAL - ENCCEJA 2024"), "88: conclusão certificada não reconhecida")
ok(not rf.conclusao_certificada("PETICIONADO CERTIFICADO DO ENCCEJA 2024 NO SISTEMA SEEU"), "88: petição contada como conclusão")
ok(not rf.conclusao_certificada("DECLARAÇÃO PARCIAL DE PROFICIÊNCIA - ENCCEJA 2024 - CERTIFICADO DE CONCLUSÃO NA ÁREA"), "88: parcial contada como conclusão")

# ---- 89: inciso XI - concessões sem registro de saída ou retorno que completariam as 5 saídas: a verificar ----
evs = [{"data": "%02d.0%d.2024" % (5, m), "texto": "SAÍDA CONFIRMADA DO BENEFÍCIO DE: SAÍDA TEMPORÁRIA"} for m in (1, 3, 5)]
evs += [{"data": "10.0%d.2024" % m, "texto": "BENEFICIADO COM SAÍDA TEMPORÁRIA, DEVENDO RETORNAR EM 17/0%d/2024" % m} for m in (7, 9)]
r = {"_eventos": [ev("01/01/2020")], "indulto_2024": "A VERIFICAR: art. 9º, XI", "indulto_2024_status": "verificar",
     "indulto_2024_detalhe": "Situação em 25/12/2024: regime semiaberto · primário\n? XI: exige 1/4 e 5 saídas temporárias - verificar na ficha"}
rf.complementar_decretos(r, {"eventos": evs, "exames": [], "trabalho": [], "estudos": []}, HOJE)
lin = [l for l in r["indulto_2024_detalhe"].split("\n") if " XI:" in l]
ok(lin and lin[0].startswith("?") and "sem registro de saída ou retorno" in lin[0], "89: %s" % lin)

# ---- 92: art. 14 da Lei 6.368/76 no art. 1º, XVIII (2024/2025): a verificar, sem vedação automática ----
c92 = crime("01/01/2005", "01/06/2005", "01/07/2005", artigo="ART 14: Associação", lei="6368/76 - Lei de Tóxicos",
            tipo="CAPUT: Associarem-se duas ou mais pessoas, Reclusão: 3 a 10 anos", pena="3 ano(s), 0 mês(es) e 0 dia(s)")
ok(rs.impeditivo_decreto(c92, date(2024, 12, 25)) is None and rs.assoc_6368_xviii(c92), "92: art. 14 da Lei 6.368 vedado ou sem dúvida")
r = reg([c92], [ev("01/01/2023")], "3a0m0d", "1a11m0d")
o = rs.analise_decretos(r, r["_crimes"], r["_eventos"], [], HOJE)
ok(o["indulto_2024_status"] != "possivel" and o["indulto_2024_status"] != "vedado", "92 (2024): %s" % o["indulto_2024"])

# ---- 93: comutação não decidida depois do indulto indeferido: a verificar ----
c93 = crime("01/01/2014", "01/06/2014", "01/07/2014", pena="10 ano(s), 0 mês(es) e 0 dia(s)")
x = dec(reg([c93], [ev("01/01/2015")], "10a0m0d", incid=[inc("INDULTO", "DECRETO Nº 11.846, DE 22 DE DEZEMBRO DE 2023", "06/02/2025", "NÃO CONCEDIDO")]), "2023")
ok(x["s"] == "ver" and x.get("beneficio") == "Comutação" and "fundamento do indeferimento" in x.get("mot", ""), "93: %s" % x)

# ---- 94: lapso ininterrupto - remição dentro do período conta e vale o maior período completo até a data ----
# 2010, art. 1º, V (15 anos ininterruptos): preso de 1994 a 2009 (15 anos menos 30 dias) com 60 dias remidos no período
c94 = crime("01/01/1993", "01/06/1993", "01/07/1993", artigo="ART 121: Homicídio", tipo="CAPUT: Matar alguém, Reclusão: 6 a 20 anos",
            pena="30 ano(s), 0 mês(es) e 0 dia(s)")
r = reg([c94], [ev("01/01/1994"), ev("01/12/2008", "INTERRUPÇÃO", "LIVRAMENTO"), ev("01/06/2010", "REINÍCIO", "RECAPTURA")], "30a0m0d",
        incid=[inc("REMIÇÃO", "60 Dias", "01/06/2008")])
ctx = rd._ctx(r)
_pu = rs.uniao_periodos(ctx["periodos"])
ok(any(a == date(1994, 1, 1) for a, _b in _pu), "94: períodos %s" % _pu)

def _h5(r_):
    hs = [h for h in (rd.avaliar(r_, HOJE, completo=True)["decretos"]) if str(h["id"]) == "2010"][0].get("hips") or []
    return next((h for h in hs if h["dispositivo"] == "art. 1º, V"), None)


# o período anterior encerrado (5.449 dias) mais a remição dentro dele (60) atinge os 15 anos (5.479 dias); antes, só o período em curso
h5 = _h5(r)
ok(h5 and h5["ok"], "94: período anterior com remição não atingiu os 15 anos: %s" % h5)
h5 = _h5(dict(r, _incidentes=[]))
ok(h5 and not h5["ok"] and "custódia ininterrupta" in h5["mot"] and not h5["mot"].startswith("faltavam 14 anos"), "94: sem a remição: %s" % h5)

# ---- 95: Decreto 4.495/2002 - hediondo/tráfico com pena até 4 anos: a verificar (CF, art. 5º, XLIII) ----
c95 = crime("01/01/2001", "01/06/2001", "01/07/2001", pena="3 ano(s), 0 mês(es) e 0 dia(s)", lei="6368/76 - Lei de Tóxicos",
            artigo="ART 12: Tráfico", tipo="CAPUT: Importar ou exportar, Reclusão: 3 a 15 anos")
x = dec(reg([c95], [ev("01/01/2001")], "3a0m0d"), "2002")
ok(x["s"] == "ver" and "XLIII" in (x.get("mot") or ""), "95: %s %s" % (x["s"], x.get("mot")))

# ---- 96: 2022 sem trânsito para a acusação na publicação: a verificar nas duas telas (tese do art. 9º, p. ú., e o STJ) ----
o = rs.analise_decreto_2022({"pena_total": "1a0m0d"}, [crime("10/01/2020", "10/10/2022", "10/01/2023")], [], [])
ok(o["indulto_2022_status"] == "verificar" and "art. 12" not in o["indulto_2022_detalhe"] and "991.402" in o["indulto_2022_detalhe"], "96: %s" % o["indulto_2022"])

# ---- 97: 2022, art. 5º, reincidente: a verificar (Tema 1267/STF) ----
o = rs.analise_decreto_2022({"pena_total": "1a0m0d"}, [crime("10/01/2020", "10/06/2020", "10/07/2020", reinc="S")], [], [])
ok(o["indulto_2022_status"] == "verificar" and "Tema 1267" in o["indulto_2022"], "97: %s" % o["indulto_2022"])
o = rs.analise_decreto_2022({"pena_total": "1a0m0d"}, [crime("10/01/2020", "10/06/2020", "10/07/2020")], [], [])
ok(o["indulto_2022_status"] == "possivel", "97: primário deixou de caber: %s" % o["indulto_2022"])

# ---- 98: Decretos de 2000 e 2001, art. 9º - o crime do art. 10 sai da soma, sem vedar a execução toda ----
c98h = crime("01/01/1998", "01/06/1998", "01/07/1998", artigo="ART 121: Homicídio", tipo="CAPUT: Matar alguém, Reclusão: 6 a 20 anos",
             pena="6 ano(s), 0 mês(es) e 0 dia(s)", proc="0000011-00.1998.8.12.0001")
c98f = crime("01/01/1998", "01/06/1998", "01/07/1998", pena="4 ano(s), 0 mês(es) e 0 dia(s)", proc="0000012-00.1998.8.12.0001")
x = dec(reg([c98h, c98f], [ev("01/01/1999")], "10a0m0d"), "2000")
ok(x["s"] == "ver" and "art. 9º" in (x.get("mot") or ""), "98: %s %s" % (x["s"], x.get("mot")))

# ---- 99: remição decidida depois da data, com referência igual à decisão ----
c99 = crime("01/01/2014", "01/06/2014", "01/07/2014", pena="6 ano(s), 0 mês(es) e 0 dia(s)", proc="0000013-00.2014.8.12.0001")
r = reg([c99], [ev("01/01/2016")], "6a0m0d", incid=[inc("REMIÇÃO", "200 Dias", "01/03/2018")])
its = rd.remicoes_ref_decisao(r)
ok(its == [(date(2018, 3, 1), 200)], "99: %s" % its)
# (7.14: o RSPE não diz de qual atestado veio a remição - ela conta pela decisão, e o decreto que ela cobriria fica a verificar)
ctx = rd._ctx(r)
ok((date(2018, 3, 1), 200) in [(d, n) for d, n in ctx["rem"]], "99: remição contada fora da decisão: %s" % ctx["rem"])

# ---- 127: pedido de indulto por decreto ----
m = {"pedidos": {"ind_2024": {"data": "01/02/2025", "ref": "cabe", "ref_atual": "cabe"}}, "dec": {"decretos": [{"id": "2024", "s": "cabe"}, {"id": "2025", "s": "cabe"}]}}
ok(rx.pedido_pendente(m, "ind"), "127: pedido de 2024 tirou da contagem o 2025 que cabe")
m["pedidos"]["ind_2025"] = {"data": "01/02/2026", "ref": "cabe", "ref_atual": "cabe"}
ok(not rx.pedido_pendente(m, "ind"), "127: com os dois pedidos, segue pendente")
m["pedidos"]["ind_2025"]["ref_atual"] = "ver"
ok(rx.pedido_pendente(m, "ind"), "127: situação mudou depois do pedido e não voltou à contagem")

# ---- 140: fuga sem homologação na janela - nos decretos que exigem falta apurada/homologada (inclusive 2023, como 2024 e 2025:
# decisão do usuário de 20/10/2026), a verificar; nos que não exigem (2016), impede ----
F = {f["id"]: f for f in rd.fichas()}
ok(not rd.fuga_impede(F["2023"]) and not rd.fuga_impede(F["2015"]) and rd.fuga_impede(F["2016"]), "140: regra da fuga por decreto")
c140 = crime("01/01/2012", "01/06/2012", "01/07/2012", pena="4 ano(s), 0 mês(es) e 0 dia(s)")
r = reg([c140], [ev("01/01/2013"), ev("01/06/2015", "INTERRUPÇÃO", "FUGA"), ev("10/06/2015", "REINÍCIO", "RECAPTURA")], "4a0m0d")
L = tl.linha(r, HOJE)
d15 = next((d for d in L["decretos"] if str(d["id"]) == "2015"), None)
fl = [f for f in (d15 or {}).get("faltas") or [] if f["estado"] != "fora"]
ok(d15 and fl and all(f["estado"] == "verificar" and "tratada como falta grave" not in f["texto"] for f in fl), "140 (linha do tempo): %s" % fl)

# ---- 158: pena considerada já cumprida - "pena cumprida - pedir a extinção" ----
out = [{"id": "2015", "ref": "25/12/2015", "s": "cabe", "beneficio": "Indulto", "mot": "cumpriu", "detalhe": {"pena": 365, "cumprido": 400}},
       {"id": "2016", "ref": "25/12/2016", "s": "cabe", "beneficio": "Indulto", "mot": "cumpriu",
        "detalhe": {"pena": 3000, "cumprido": 2500, "pena_conc": 365, "cumprido_conc": 500}}]
rd._pena_cumprida_aba(out, {})
ok(out[0]["s"] == "ver" and out[0]["beneficio"].startswith("Extinção") and "pedir a extinção pelo" in out[0]["mot"], "158: %s" % out[0])
# (7.13.0: no concurso, o tempo além da fração do impeditivo só afere o requisito - não extingue a pena dos demais: segue o indulto,
# com a extinção parcial como tese na ressalva)
ok(out[1]["s"] == "cabe" and out[1]["beneficio"] == "Indulto" and "extinção parcial pelo cumprimento é tese" in out[1]["ressalva"], "158 (concurso): %s" % out[1])
r = {"indulto_2024": "POSSÍVEL: art. 9º, I", "indulto_2024_status": "possivel", "indulto_2024_num": {"pena": 365, "cumprido": 365}}
rd.pena_cumprida_decretos(r)
ok(r["indulto_2024"].startswith(rd.PENA_CUMPRIDA) and r["indulto_2024_status"] == "verificar", "158 (2024): %s" % r["indulto_2024"])

if falhas:
    print("FALHOU: quesitos 16/10 - indulto")
    for f_ in falhas:
        print("  " + f_)
    sys.exit(1)
print("ok: quesitos 16/10 - indulto e comutação (teto no concurso, custódia de outro processo, mercancia 2008, comutações anteriores, "
      "pena abaixo do mínimo, art. 1º, XVII e XVIII, art. 2º, II, comutação concedida, ENCCEJA, saídas, indeferimento, ininterrupto, 2002, "
      "trânsito e reincidência em 2022, art. 9º de 2000/2001, remição posterior, pedido por decreto, fuga em 2023, pena cumprida)")
