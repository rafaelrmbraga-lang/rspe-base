"""Conferência manual de 420 casos (frente A - leitura do RSPE, eventos e custódia), com casos hipotéticos (nomes e números
fictícios): eventos do mesmo dia impressos fora de ordem (soltura antes da prisão, recaptura antes da interrupção), recaptura no
dia da fuga, número de processo com erro de digitação ou sem pontos na ficha, custódia da ficha por outro processo, prisão civil,
custódia que serviu a outra execução, liberdade provisória sem soltura na ficha, livramento com a pena da época e substituído por
nova alteração de regime, livramento cujas penas já se extinguiram, prisão em outro processo que alcança o remanescente, execução
arquivada com pena ativa, condenação por fato posterior à custódia, soma das penas por componente, duas causas de extinção do
mesmo processo, saída temporária com a pena cumprida do SEEU zerada.
Rodar: python teste_conf_A.py"""
import os
import sys
import types
from datetime import date, timedelta

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
wv = types.ModuleType("webview")
wv.SAVE_DIALOG, wv.FOLDER_DIALOG, wv.OPEN_DIALOG = 1, 2, 0
sys.modules.setdefault("webview", wv)
import rspe_scraper as rs  # noqa: E402
import rspe_view as rv  # noqa: E402
import rspe_ficha as rf  # noqa: E402

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)
    return cond


HOJE = date(2026, 10, 20)
rv.HOJE = HOJE
P1, P2, P3 = "8800001-11.2019.8.12.0001", "8800002-22.2020.8.12.0001", "8800003-33.2021.8.12.0001"
OUTRO = "9900009-99.2025.8.12.0800"
EXEC = "7700001-00.2022.8.12.0001"


def crime(proc=P1, art="ART 155: Furto", pena="2 ano(s), 0 mês(es) e 0 dia(s)", fato="10/01/2019", **kw):
    c = {"processo_criminal": proc, "processo_situacao": "", "tipo_processo": "ACAO PENAL", "lei": "2848/40 - Código Penal", "artigo": art,
         "tipo_penal": "", "pena_imposta": pena, "pena_total_processo": "PENA ORIGINÁRIA", "data_infracao": fato,
         "data_sentenca": "10/06/2019", "transito_processo": "10/08/2019", "transito_mp": "", "regime_sentenca": "Semiaberto", "vga": "N",
         "resultado_morte": "N", "reincidente_comum": "N", "reincidente_especifico": "N", "comando_orcrim": "N",
         "fracao_progressao": "16%", "fracao_livramento": "1/3", "extinto": "Não", "suspenso": "Não"}
    c.update(kw)
    return c


def ev(data, tipo="PRISÃO/INÍCIO DE CUMPRIMENTO", motivo="PRISÃO EM FLAGRANTE", procs="", **kw):
    e = {"tipo": tipo, "motivo": motivo, "complemento": "", "data": data, "data_decisao": "", "data_referencia": "", "processos": procs}
    e.update(kw)
    return e


def it(data, tipo, comp="", sit="CONCEDIDO", procs=""):
    return {"tipo": tipo, "complemento": comp, "data_decisao": data, "data_referencia": data, "situacao": sit, "processos": procs}


def reg(crimes, eventos, incidentes=None, **kw):
    r = {"versao_leitura_rspe": rs.VERSAO_LEITURA_RSPE, "nome": "FULANO DE TESTE", "processo_execucao": EXEC, "status_execucao": "ATIVO",
         "data_geracao_rspe": "15/10/2026", "pena_total": "2a0m0d", "pena_cumprida": "1a0m0d", "pena_remanescente": "1a0m0d",
         "regime_atual": "Semiaberto", "data_nascimento": "01/01/1990", "cpf": "", "nome_mae": "MAE DE TESTE", "arquivo": "x.pdf",
         "_crimes": crimes, "_eventos": eventos, "_incidentes": incidentes or [], "_acoes_sem_crime": []}
    r.update(kw)
    return rs.reprocessar(r)


INT = "INTERRUPÇÃO"
d = rs.to_date

# ---------------- 1: eventos do mesmo dia impressos fora de ordem ----------------
# solto na véspera, "liberdade provisória" impressa antes do flagrante do mesmo dia: um dia de custódia, não prisão aberta até a
# soltura seguinte
evs = [ev("03/11/2018", INT, "LIBERDADE PROVISÓRIA"), ev("03/11/2018"), ev("23/04/2019"), ev("26/07/2019", INT, "LIBERDADE PROVISÓRIA")]
ok(rs.periodos_custodia(evs) == [(d("03/11/2018"), d("03/11/2018")), (d("23/04/2019"), d("26/07/2019"))],
   "1: soltura impressa antes da prisão do mesmo dia: %s" % rs.periodos_custodia(evs))
ok([e["tipo"] for e in rs.eventos_cronologicos(evs)[:2]] == ["PRISÃO/INÍCIO DE CUMPRIMENTO", INT], "1: ordem do dia refeita (prisão, soltura)")
# preso na véspera, recaptura impressa antes da interrupção do mesmo dia: cumprimento contínuo, sem "dias sem cômputo"
evs = [ev("25/06/2015", motivo="PRISÃO PREVENTIVA"), ev("04/12/2025", motivo="RECAPTURA/REINÍCIO DE CUMPRIMENTO"),
       ev("04/12/2025", INT, "DESCUMPRIMENTO DAS CONDIÇÕES")]
ok(rs.uniao_periodos(rs.periodos_custodia(evs)) == [(d("25/06/2015"), None)], "1: recaptura antes da interrupção: %s" % rs.periodos_custodia(evs))
ok("INTERRUP" not in rs.eventos_cronologicos(evs)[-1]["tipo"], "1: o último evento é a recaptura, não a interrupção")
# preso, prisão definitiva (só o título) e fuga no mesmo dia: vale a ordem do PDF (a fuga fecha a custódia)
evs = [ev("28/08/2012", motivo="PRISÃO DEFINITIVA"), ev("20/09/2012", motivo="PRISÃO DEFINITIVA"), ev("20/09/2012", INT, "FUGA")]
ok(rs.periodos_custodia(evs) == [(d("28/08/2012"), d("20/09/2012"))], "1: prisão definitiva + fuga do mesmo dia: %s" % rs.periodos_custodia(evs))
# recaptura no mesmo dia da fuga: a prescrição disciplinar corre desse dia (não "sem recaptura registrada")
evs = [ev("08/12/2022"), ev("01/04/2026", INT, "FUGA"), ev("01/04/2026", motivo="RECAPTURA/REINÍCIO DE CUMPRIMENTO")]
ok(rs.prescricao_disciplinar(d("01/04/2026"), True, evs)[0] == d("01/04/2026"), "1: recaptura no dia da fuga: %s" % (rs.prescricao_disciplinar(d("01/04/2026"), True, evs),))
ok(rs.prescricao_disciplinar(d("01/04/2026"), True, evs[:2]) == (None, None), "1: sem recaptura, a fuga é permanente")

# ---------------- 2: número de processo grafado com erro ou sem pontos ----------------
ok(rs.processos_no_texto("Alvará: AUTOS0801005-11.2019.8.12.0014; 00107745720158120001; 0052142-562009.8.12.0001; Nº.09000036-28.2024.8.12.0014") ==
   ["0801005-11.2019.8.12.0014", "0010774-57.2015.8.12.0001", "0052142-56.2009.8.12.0001", "9000036-28.2024.8.12.0014"],
   "2: números sem pontos: %s" % rs.processos_no_texto("AUTOS0801005-11.2019.8.12.0014"))
ok(rs.processo_parecido("0004790-48.2020.8.12.0001", "0004790-48.2022.8.12.0001"), "2: ano trocado é o mesmo processo")
ok(rs.processo_parecido("9000036-28.2024.8.12.0014", "0900036-28.2024.8.12.0014"), "2: dígitos invertidos são o mesmo processo")
ok(not rs.processo_parecido("0004790-48.2020.8.12.0001", "0004791-49.2021.8.12.0001"), "2: três dígitos diferentes: outro processo")
ok(not rs.processo_parecido("0004790-48.2020.8.12.0001", "0004790-48.2020.8.12.0002"), "2: outra origem: outro processo")
r = reg([crime(P1, fato="22/12/2023")], [ev("17/08/2025")])
f = {"eventos": [{"data": "29.12.2023", "texto": "Entrada na Unidade Penal: PDIB, Procedente: DP MARACAJU - INTERIOR, Conforme OF/CI 1/2023."},
                 {"data": "15.08.2024", "texto": "Saída da Unidade Penal: EPJFC, Destino: , Motivo: Alvará de Soltura, Conforme Alvará: Nº.0%s.." %
                  P1.replace("8800001", "8000001")}], "autos": [P1.replace("8800001", "8000001")]}
its = rf._detracao_x_ficha(r, f)
ok(its and "231 dias" in its[0]["titulo"] and P1 in its[0]["titulo"], "2: alvará com número digitado errado ainda liga a prisão: %s" % its)
its = rf._processos_x_ficha(r, f)
ok(len(its) == 1 and "erro de digitação" in its[0]["titulo"], "2: número parecido não vira 'processo que o RSPE não lista': %s" % its)

# ---------------- 3: custódia da ficha (outro processo, prisão civil, outra execução) ----------------
f = {"artigo": "PENSÃO ALIMENTICIA", "condenacao": "", "data_prisao": "25/09/2026", "autos": [],
     "eventos": [{"data": "01.10.2026", "texto": "Entrada na Unidade Penal: PDIB, Procedente: DP MARACAJU - INTERIOR, Conforme OF/CI OF 1."}]}
r = reg([crime()], [], pena_total="0a0m0d", pena_cumprida="0a0m0d", pena_remanescente="0a0m0d")
av = rf.reconciliar_eventos(r, f)
ok(not r["_eventos"] and [a for a in av if a[0] == "custodia-nao-desta" and a[1]["tipo"] == "civil"],
   "3: prisão civil não é lançada como início desta pena: %s / %s" % (r["_eventos"], av))
ok(rv.termino_calc(r) is None, "3: sem início, sem término calculado")
f = {"artigo": "ART.121, 157 \"CAPUT\" C/C 61", "condenacao": "PROCESSADO", "data_prisao": "07/06/2026", "autos": [],
     "eventos": [{"data": "17.06.2026", "texto": "Entrada na Unidade Penal: EPMR, Procedente: PORTO MURTINHO - DP - INTERIOR, Conforme OF/CI OF 271."}]}
r = reg([crime(art="ART 129: Lesão corporal", fato="07/07/2025")], [], status_execucao="SUSPENSO OU SOBRESTADO",
        pena_total="0a0m0d", pena_cumprida="0a0m0d", pena_remanescente="0a0m0d")
av = rf.reconciliar_eventos(r, f)
ok(not r["_eventos"] and [a for a in av if a[0] == "custodia-nao-desta" and a[1]["tipo"] == "outro"],
   "3: execução suspensa e prisão por outros crimes: sem início lançado: %s" % av)
# execução ativa, prisão por outro processo: lança, mas diz que a custódia é de outro processo (não "não indica processo")
f = {"artigo": "ART.33 LEI 11343", "condenacao": "PROCESSADO", "data_prisao": "12/08/2026", "autos": [OUTRO],
     "eventos": [{"data": "18.08.2026", "texto": "Entrada na Unidade Penal: PDIB, Procedente: DP MARACAJU - INTERIOR, Conforme OF/CI %s." % OUTRO}]}
r = reg([crime(art="ART 129: Lesão corporal", fato="12/02/2022", pena="0 ano(s), 3 mês(es) e 0 dia(s)")], [], pena_total="",
        pena_cumprida="", pena_remanescente="")
rf.reconciliar_eventos(r, f)
rs.reprocessar(r)  # como na montagem: a análise refeita com o início lançado pela ficha
cs = rv.custodia_sem_calculo(r)
ok(cs and cs["desde"] == d("12/08/2026") and "outro processo" in cs["duvida_txt"] and OUTRO in cs["duvida_txt"],
   "3: custódia vinculada a outro processo pela ficha: %s" % cs)
ok(rv.termino_calc(r) == d("11/11/2026"), "3: guia com o quadro do cálculo em branco: término pela soma das penas: %s" % rv.termino_calc(r))
# a custódia serviu a outra execução até a extinção dela: esta só começa no dia seguinte
f = {"artigo": "155", "condenacao": "CONDENADO", "data_prisao": "27/11/2023", "autos": [],
     "eventos": [{"data": "30.11.2023", "texto": "Entrada na Unidade Penal: PDIB, Procedente: DP MARACAJU - INTERIOR, Conforme OF/CI 1202."},
                 {"data": "15.10.2025", "texto": "PENA EXTINTA EM 14/10/2025, CONFORME DECISÃO DA 1ª VARA AUTOS DA EXECUÇÃO PENAL Nº 6000076-93.2025.8.12.0014."}]}
r = reg([crime(fato="04/05/2023")], [], pena_total="0a0m0d", pena_cumprida="0a0m0d", pena_remanescente="0a0m0d")
av = rf.reconciliar_eventos(r, f)
ok([e["data"] for e in r["_eventos"]] == ["15/10/2025"] and [a for a in av if a[0] == "custodia-outra-execucao"],
   "3: custódia que serviu a outra execução: início no dia seguinte à extinção: %s" % r["_eventos"])
ok(not rf._prisao_x_ficha(r, f), "3: sem alerta de 'dias sem cômputo' para a custódia de outra execução")
# entrada no monitoramento eletrônico não é prisão; a custódia atual é a que começa depois da última saída
f = {"artigo": "155 § 4", "condenacao": "PROCESSADO", "data_prisao": "10/12/2025", "autos": [],
     "eventos": [{"data": "03.05.2023", "texto": "Entrada na Unidade Penal: UNIDADE MISTA DE MONITORAMENTO VIRTUAL ESTADUAL DE CAMPO GRANDE, Procedente: DP NIOAQUE - INTERIOR, Conforme OF/CI 1."},
                 {"data": "15.01.2024", "texto": "Saída da Unidade Penal: UNIDADE MISTA DE MONITORAMENTO VIRTUAL ESTADUAL DE CAMPO GRANDE, Destino: DECISÃO JUDICIAL, Motivo: Determinação Judicial, Conforme Oficio: 1."},
                 {"data": "16.12.2025", "texto": "Entrada na Unidade Penal: EPMR, Procedente: DP NIOAQUE - INTERIOR, Conforme OF/CI 582."}]}
r = reg([crime(fato="10/01/2019")], [ev("30/03/2022"), ev("31/03/2022", INT, "FUGA")])
av = rf.reconciliar_eventos(r, f)
x = [a[1]["entrada"] for a in av if a[0] in ("reinicio-pela-ficha", "reinicio-a-conferir")]
ok(x == [d("10/12/2025")], "3: monitoramento não é a nova prisão; vale a de 10/12/2025: %s" % av)

# ---------------- 4: liberdade provisória sem soltura na ficha ----------------
r = reg([crime(P1, fato="10/01/2025")], [ev("15/03/2025", procs=P1), ev("28/06/2025", INT, "LIBERDADE PROVISÓRIA"),
                                          ev("06/07/2025", motivo="INÍCIO DO CUMPRIMENTO REGIME SEMIABERTO")])
f = {"eventos": [{"data": "28.06.2025", "texto": "Emitido Parecer da CA em documento oficial, no carimbo consta na linha 01: ALVARA - PENDÊNCIA, na linha 02: EXISTE IMPEDIMENTOS, em observação: Guia de execução nos autos nº %s." % P1},
                 {"data": "06.07.2025", "texto": "Saída da Unidade Penal: PDIB, Destino: EPRSA, Motivo: Progressão de Regime, Conforme Ofício: 1."}]}
its = rf._soltura_x_ficha(r, f)
ok(its and its[0]["nivel"] == "alerta" and "7 dias" in its[0]["titulo"], "4: liberdade provisória com alvará pendente: %s" % its)
f["eventos"][0]["texto"] = "Emitido Parecer: ALVARÁ - LIBERADO, na linha 02: NÃO EXISTE IMPEDIMENTOS"
ok(not rf._soltura_x_ficha(r, f), "4: 'não existe impedimentos' não é pendência")

# ---------------- 5: livramento condicional (pena da época, substituição, penas extintas) ----------------
cr = [crime(P1, pena="3 ano(s), 6 mês(es) e 0 dia(s)", fato="23/07/2010", data_sentenca="10/03/2011"),
      crime(P2, pena="9 ano(s), 7 mês(es) e 12 dia(s)", fato="10/05/2018", data_sentenca="10/05/2019")]
r = reg(cr, [ev("20/07/2012")], pena_total="13a1m12d")
pt, nota = rv.pena_na_data(r, d("20/07/2013"))
ok(pt == rs.pena_para_dias("3a6m0d") and "somadas depois" in nota, "5: pena do período de prova = a da época: %s %s" % (pt, nota))
ok(rv.pena_na_data(r, d("20/07/2020"))[0] == rs.pena_para_dias("13a1m12d"), "5: todas as condenações já existiam: pena total do SEEU")
inc = [it("30/05/2010", "LIVRAMENTO CONDICIONAL", "30/05/2010"), it("27/09/2010", "FIXAÇÃO/ALTERAÇÃO DE REGIME", "Fechado - Somatório de Penas")]
r = reg([crime()], [ev("01/06/2009")], inc)
ok(rv.livramento_substituido(r, d("30/05/2010"), d("30/05/2015")), "5: soma de penas com regime fechado substitui o livramento")
ok(not rv.livramento_substituido(r, d("30/05/2010"), d("01/09/2010")), "5: alteração depois do fim do período de prova não substitui")
# livramento cujas penas (as da época) já se extinguiram, com condenações novas ativas: não está mais em livramento
cr = [crime(P1, fato="10/01/2009", data_sentenca="10/06/2010", extinto="Sim", data_extincao="07/06/2022"),
      crime(P2, fato="20/05/2021", data_sentenca="10/06/2022")]
r = reg(cr, [ev("08/06/2022")], [it("25/09/2017", "LIVRAMENTO CONDICIONAL", "25/09/2017")],
        livramento_obs_seeu="(Em livramento condicional deferido em 25/09/2017)")
ok(rs.livramento_em_curso(r, r["_incidentes"])[0] is False, "5: penas do livramento extintas: livramento encerrado")

# ---------------- 6: hipóteses de extinção ----------------
# prisão em outro processo em curso que alcança o remanescente (fatos anteriores a ela)
r = reg([crime(fato="10/01/2015")], [ev("14/05/2026"), ev("09/07/2026", INT, "INTERRUPÇÃO POR PRISÃO EM OUTRO PROCESSO")],
        pena_total="10a8m0d", pena_cumprida="10a6m28d", pena_remanescente="0a1m2d")
ex = rv.extincao(r, {"presc_linhas": []}, True)
ok("preso por outro processo desde 09/07/2026" in ex["ext_hipoteses"] and ex["ext_cor"] == "amarelo", "6: prisão em outro processo: %s" % ex)
# execução arquivada com pena ativa
r = reg([crime(pena="0 ano(s), 2 mês(es) e 0 dia(s)"), crime(P2, extinto="Sim")], [ev("17/03/2021", procs=P2)], status_execucao="ARQUIVADO",
        pena_total="0a0m0d", pena_cumprida="0a0m0d", pena_remanescente="0a0m0d")
ex = rv.extincao(r, {"presc_linhas": []}, False)
ok("arquivada no SEEU" in ex["ext_hipoteses"] and ex["ext_cor"] == "amarelo", "6: arquivada com pena ativa: %s" % ex)
# execução extinta: sem "interrompida" no término
r = reg([crime(extinto="Sim")], [ev("10/01/2018"), ev("10/02/2018", INT, "LIBERDADE PROVISÓRIA")])
ex = rv.extincao(r, {"presc_linhas": []}, True)
ok(ex["ext_cor"] == "azul" and ex["ext_termino"] == "", "6: extinta sem 'Interrompida': %s" % ex["ext_termino"])
# guia sem cálculo com condenação por fato posterior à custódia: a pena nova não absorve a prisão anterior (CP, art. 42)
cr = [crime(P1, pena="5 ano(s), 0 mês(es) e 0 dia(s)", fato="10/01/2005"),
      crime(P2, pena="2 ano(s), 6 mês(es) e 0 dia(s)", fato="15/12/2024")]
r = reg(cr, [ev("05/02/2016", motivo="RECAPTURA/REINÍCIO DE CUMPRIMENTO", procs=P1)], pena_total="0a0m0d", pena_cumprida="0a0m0d",
        pena_remanescente="0a0m0d")
cs = rv.custodia_sem_calculo(r)
pf = rv.termino_por_fato(r, cs, rv.soma_penas_ativas(r), 0)
ok(pf and pf["antigas"] == rv._soma_pena(d("05/02/2016"), rs.pena_para_dias("5a0m0d")) - timedelta(days=1), "6: penas antigas: %s" % pf)
ok(rv.termino_calc(r) == rv._soma_pena(d("15/12/2024"), rs.pena_para_dias("2a6m0d")) - timedelta(days=1),
   "6: a pena nova corre do fato: %s" % rv.termino_calc(r))
ex = rv.extincao(r, {"presc_linhas": []}, False)
ok("extinção parcial" in ex["ext_hipoteses"] and ex["ext_cor"] == "amarelo", "6: extinção parcial das penas antigas: %s" % ex["ext_hipoteses"])

# ---------------- 7: soma das penas por componente (como o SEEU) ----------------
cr = [crime(P1, pena="8 ano(s), 10 mês(es) e 20 dia(s)"), crime(P2, pena="5 ano(s), 4 mês(es) e 0 dia(s)"),
      crime(P3, pena="1 ano(s), 2 mês(es) e 0 dia(s)"), crime("8800004-44.2021.8.12.0001", pena="5 ano(s), 0 mês(es) e 0 dia(s)")]
r = reg(cr, [ev("09/03/2024")], pena_total="0a0m0d", pena_cumprida="0a0m0d", pena_remanescente="0a0m0d")
ok(rs.dias_para_pena(rv.soma_penas_ativas(r)) == "20a4m20d", "7: soma por componente: %s" % rs.dias_para_pena(rv.soma_penas_ativas(r)))

# ---------------- 8: duas causas de extinção do mesmo processo; data do indulto do processo "(Indultada)" ----------------
cs8 = [crime(P1), crime(P2, processo_situacao="Indultada")]
r8 = {"status_execucao": "ATIVO", "pena_remanescente": "1a0m0d", "versao_leitura_rspe": rs.VERSAO_LEITURA_RSPE}
inc = [it("26/06/2026", "EXTINÇÃO", "PRESCRIÇÃO", procs=P1), it("26/06/2026", "EXTINÇÃO", "ANISTIA, GRAÇA OU INDULTO", procs=P1),
       it("14/05/2024", "INDULTO", "DECRETO Nº 11.302, DE 22 DE DEZEMBRO DE 2022", procs=P2)]
rs.aplicar_extincoes(r8, cs8, inc)
ok("PRESCRI" in cs8[0]["extincao_motivo"].upper() and "INDULTO" in cs8[0]["extincao_motivo"].upper(), "8: duas causas: %s" % cs8[0]["extincao_motivo"])
ok(cs8[1]["extincao_motivo"] == "indulto" and cs8[1].get("data_extincao") == "14/05/2024", "8: data do indulto: %s" % cs8[1])

# ---------------- 9: saída temporária com a pena cumprida do SEEU zerada ----------------
r = reg([crime(pena="4 ano(s), 4 mês(es) e 0 dia(s)", fato="10/01/2024")], [ev("17/08/2025")], pena_total="4a4m0d", pena_cumprida="0a0m0d",
        pena_remanescente="4a4m0d")
st = rv.saida_temporaria(r, None, {}, hoje=HOJE)
x = [i for i in st["st_itens"] if "pena cumprida" in i["txt"]]
ok(x and x[0]["ok"] is None and "custódia" in x[0]["txt"], "9: 1/6 alcançado pela custódia fica a conferir: %s" % x)
add = []
rv._conduta_requisito(lambda o, t: add.append((o, t)), {"conduta": "SOLICITAR RELATÓRIO CIRCUNSTANCIADO NA UMMVE"}, None)
ok(add[0][0] is None, "9: conduta não classificada fica a conferir: %s" % add)
add = []
rv._conduta_requisito(lambda o, t: add.append((o, t)), {"conduta": "MÁ"}, None)
ok(add[0][0] is False, "9: conduta má não atende")

if falhas:
    print("FALHOU (conferência, frente A - RSPE, eventos e custódia):")
    for f_ in falhas:
        print("  " + f_)
    sys.exit(1)
print("ok: conferência 420 casos - frente A (eventos do mesmo dia, custódia da ficha, livramento e hipóteses de extinção)")
