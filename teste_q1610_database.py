"""Teste dos quesitos de 16/10/2026, grupo "data-base" (itens 45, 47, 48, 50, 51, 52, 53, 57, 58, 59, 145, 147, 148, 149, 150, 155
e 156): data-base na data do fato (durante o cumprimento x em liberdade), adequação de pena com o somatório, data-base do livramento
x regressão/recaptura/falta, regime inicial superado pela progressão, guia suspensa no total, nova prisão depois de liberdade
provisória (verificar, sem reinício), recaptura sem falta homologada (verificar, PAD pendente), prisão antes do fato (detração
entre processos: verificar), PADIC extinto por prescrição, art. 75 (término calculado; fatos dos dois lados de 23/01/2020),
unidade incerta (SV 56), art. 115 no acórdão, falta "a apurar" e conduta "sem lapso" a conferir, semiaberto em unidade do fechado,
detração por prisão em outro processo com fato anterior. Casos hipotéticos, nomes fictícios.
Rodar: python teste_q1610_database.py"""
import copy
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_auditoria as ra
import rspe_ficha as rf
import rspe_prescricao as rp
import rspe_view as rv

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


AR = "FIXAÇÃO/ALTERAÇÃO DE REGIME"
PR = "PRISÃO/INÍCIO DE CUMPRIMENTO"
P1, P2 = "0000001-11.2015.8.12.0001", "0000002-22.2021.8.12.0001"


def inc(tipo, compl, dec, ref, sit="CONCEDIDO", procs=""):
    return {"tipo": tipo, "motivo": "", "complemento": compl, "data": "", "data_decisao": dec, "data_referencia": ref, "processos": procs, "situacao": sit}


def ev(tipo, motivo, data, procs=P1):
    return {"tipo": tipo, "motivo": motivo, "data": data, "processos": procs}


def crime(**kw):
    c = {"processo_criminal": P1, "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto",
         "tipo_penal": "CAPUT: Subtrair, Reclusão: 1 a 4 anos", "pena_imposta": "10 ano(s), 0 mês(es) e 0 dia(s)",
         "data_infracao": "10/01/2015", "data_sentenca": "10/06/2015", "transito_mp": "10/07/2015", "transito_processo": "10/07/2015",
         "extinto": "Não", "suspenso": "Não", "vga": "N", "resultado_morte": "N", "reincidente_comum": "N", "reincidente_especifico": "N",
         "comando_orcrim": "N", "fracao_progressao": "1/6 - Comum", "fracao_livramento": "1/3 - Comum"}
    c.update(kw)
    return c


def reg(crimes, incs=(), eventos=(), **kw):
    r = {"nome": "Teste Ficticio", "regime_atual": "Fechado - ATIVO", "pena_total": "10a0m0d", "pena_cumprida": "3a0m0d", "pena_remanescente": "7a0m0d",
         "fracao_progressao_aplicada": "1/6", "data_geracao_rspe": "01/10/2026", "data_base_seeu": "01/03/2024", "_crimes": crimes,
         "_incidentes": list(incs), "_eventos": list(eventos)}
    r.update(kw)
    return r


def itens(r, tipo=None):
    its = ra.auditar(copy.deepcopy(r), date(2026, 10, 16))["aud_itens"]
    return [i for i in its if tipo is None or i.get("tipo") == tipo]


# ---- 45: data-base na data do fato de condenação desta execução ----
c2 = crime(processo_criminal=P2, data_infracao="05/05/2021", pena_imposta="2 ano(s), 0 mês(es) e 0 dia(s)")
evs = [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2016")]
r = reg([crime(), c2], [inc(AR, "Fechado - Regime Inicial", "", "10/01/2016")], evs, data_base_seeu="05/05/2021", pena_total="12a0m0d")
x = itens(r, "data-base-na-data-do-fato-de-condenacao")
ok(len(x) == 1 and x[0]["nivel"] == "info" and "durante o cumprimento" in x[0]["titulo"], "45 durante o cumprimento: %s" % x)
# fato em liberdade (depois da soltura)
evs2 = [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2016"), ev("INTERRUPÇÃO", "LIVRAMENTO CONDICIONAL", "10/01/2020", ""),
        ev(PR, "PRISÃO EM FLAGRANTE", "05/06/2021", P2)]
r2 = reg([crime(), c2], [inc(AR, "Fechado - Regime Inicial", "", "10/01/2016")], evs2, data_base_seeu="05/05/2021", pena_total="12a0m0d")
x = itens(r2, "data-base-na-data-do-fato-de-condenacao")
ok(len(x) == 1 and x[0]["nivel"] == "verificar" and "liberdade" in x[0]["detalhe"], "45 em liberdade: %s" % x)

# ---- 145: adequação de pena decidida no mesmo dia do somatório, na data do fato, sem falta ----
incs = [inc(AR, "Fechado - Regime Inicial", "", "10/01/2016"), inc(AR, "Semiaberto - Progressão de Regime", "02/12/2019", "14/10/2019"),
        inc(AR, "Fechado - Adequação de Pena", "28/09/2025", "05/05/2021"), inc("SOMATÓRIO DAS PENAS", "", "28/09/2025", "28/09/2025")]
r = reg([crime(), c2], incs, evs, data_base_seeu="05/05/2021", pena_total="12a0m0d")
x = itens(r, "data-base-na-data-do-fato-de-condenacao")
ok(len(x) == 1 and x[0]["nivel"] == "verificar" and "adequação de pena" in x[0]["titulo"], "145: %s" % x)
ok(not itens(r, "data-base-confere-com-o-rspe"), "145: sem 'confere'")

# ---- 47: data-base do livramento x regressão / recaptura / falta homologada ----
evs = [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2016"), ev("INTERRUPÇÃO", "FUGA", "01/02/2022", ""), ev(PR, "RECAPTURA", "01/05/2022")]
incs = [inc(AR, "Fechado - Regime Inicial", "", "10/01/2016"), inc("HOMOLOGAÇÃO DE FALTA GRAVE", "01/02/2022", "10/06/2022", "01/02/2022")]
r = reg([crime()], incs, evs, data_base_seeu="01/05/2022", livramento_data_base_seeu="01/05/2022")
x = itens(r, "data-base-do-livramento-alterada-por-falta-grave")
ok(len(x) == 1 and x[0]["nivel"] == "alerta" and "recaptura" in x[0]["titulo"] and "441" in x[0]["fundamento"], "47 recaptura: %s" % x)
incs = [inc(AR, "Fechado - Regime Inicial", "", "10/01/2016"), inc(AR, "Fechado - Regressão", "20/03/2023", "15/03/2023")]
r = reg([crime()], incs, [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2016"), ev("INTERRUPÇÃO", "DESCUMPRIMENTO DAS CONDIÇÕES", "01/01/2023", ""),
                          ev(PR, "PRISÃO", "02/01/2023")], data_base_seeu="15/03/2023", livramento_data_base_seeu="15/03/2023")
x = itens(r, "data-base-do-livramento-alterada-por-falta-grave")
ok(len(x) == 1 and "regressão" in x[0]["titulo"], "47 regressão: %s" % x)
# primeira prisão: correta, sem alerta; recaptura depois de liberdade provisória não é marco da Súmula 441
r = reg([crime()], [inc(AR, "Fechado - Regime Inicial", "", "10/01/2016")], [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2016"),
        ev("INTERRUPÇÃO", "LIBERDADE PROVISÓRIA", "10/03/2016", ""), ev(PR, "RECAPTURA/REINÍCIO DE CUMPRIMENTO", "10/06/2016")],
        data_base_seeu="10/06/2016", livramento_data_base_seeu="10/06/2016")
ok(not itens(r, "data-base-do-livramento-alterada-por-falta-grave"), "47 liberdade provisória: %s" % itens(r, "data-base-do-livramento-alterada-por-falta-grave"))

# ---- 48: regime inicial lançado depois da primeira prisão, já superado por progressão ----
evs = [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2015")]
incs = [inc(AR, "Fechado - Regime Inicial", "", "10/06/2015"), inc(AR, "Semiaberto - Progressão de Regime", "10/03/2017", "01/03/2017")]
r = reg([crime()], incs, evs, data_base_seeu="01/03/2017", regime_atual="Semiaberto - ATIVO")
x = itens(r, "regime-inicial-depois-da-primeira-prisao")
ok(len(x) == 1 and x[0]["nivel"] == "info" and "superado pela progressão de 01/03/2017" in x[0]["titulo"], "48: %s" % x)

# ---- 50: pena total que inclui a guia suspensa ----
cs = crime(processo_criminal=P2, data_infracao="05/05/2021", pena_imposta="1 ano(s), 0 mês(es) e 0 dia(s)", suspenso="Sim")
r = reg([crime(), cs], [inc(AR, "Fechado - Regime Inicial", "", "10/01/2016")], [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2016")],
        pena_total="11a0m0d", data_base_seeu="10/01/2016")
x = itens(r, "guia-suspensa-somada-na-pena-total")
ok(len(x) == 1 and x[0]["nivel"] == "verificar" and "10a0m0d" in x[0]["detalhe"], "50: %s" % x)
ok(not itens(r, "soma-das-penas-confere-com-a-pena-total"), "50: sem 'confere'")
r = reg([crime(), cs], [inc(AR, "Fechado - Regime Inicial", "", "10/01/2016")], [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2016")],
        pena_total="10a0m0d", data_base_seeu="10/01/2016")
ok(itens(r, "soma-das-penas-confere-com-a-pena-total") and not itens(r, "guia-suspensa-somada-na-pena-total"), "50: total sem a suspensa confere")

# ---- 51: nova prisão na ficha depois de liberdade provisória: verificar, sem reinício lançado ----
E = "Entrada na Unidade Penal: PENITENCIÁRIA ESTADUAL DE DOURADOS, Procedente: DP DOURADOS - INTERIOR, Conforme OF 1/2026."
f = {"data_prisao": "", "unidade": "PENITENCIÁRIA ESTADUAL DE DOURADOS", "eventos": [{"data": "05.05.2026", "texto": E}]}
for mot, lanca in (("LIBERDADE PROVISÓRIA", False), ("SENTENÇA - REGIME ABERTO", False), ("FUGA", True)):
    r = reg([crime()], [], [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2016"), ev("INTERRUPÇÃO", mot, "10/01/2026", "")])
    av = rf.reconciliar_eventos(r, f)
    r["_reconc_ficha"] = av
    tem = any(e.get("_ficha") for e in r["_eventos"])
    ok(tem == lanca, "51 %s: reinício lançado=%s" % (mot, tem))
    its = rf._interrupcao_x_ficha(r, f)
    if lanca:
        ok(any(i["nivel"] == "alerta" and "Reinício omitido" in i["titulo"] for i in its), "51 fuga: %s" % its)
    else:
        ok(len(its) == 1 and its[0]["nivel"] == "verificar" and "em que processo" in its[0]["titulo"], "51 %s: %s" % (mot, its))

# ---- 52 e 147: data-base movida para a recaptura sem falta homologada: verificar (PAD pendente no título) ----
evs = [ev(PR, "INÍCIO DO CUMPRIMENTO REGIME SEMIABERTO", "01/08/2025"), ev("INTERRUPÇÃO", "FUGA", "01/02/2026", ""), ev(PR, "RECAPTURA", "01/05/2026")]
r = reg([crime()], [inc(AR, "Semiaberto - Regime Inicial", "", "01/08/2025")], evs, data_base_seeu="01/05/2026")
x = itens(r, "data-base-movida-para-a-recaptura-sem-falta-homo")
ok(len(x) == 1 and x[0]["nivel"] == "verificar" and "PAD" not in x[0]["titulo"], "147: %s" % x)
r["_incidentes"].append(inc("HOMOLOGAÇÃO DE FALTA GRAVE", "01/02/2026", "", "01/02/2026", sit="PENDENTE"))
x = itens(r, "data-base-movida-para-a-recaptura-sem-falta-homo")
ok(len(x) == 1 and x[0]["nivel"] == "verificar" and "PAD pendente" in x[0]["titulo"] and "aguardar" in x[0]["detalhe"], "52: %s" % x)

# ---- 53: prisão anterior ao fato da ação vinculada: verificar, nunca alerta contra a detração ----
r = reg([crime(data_infracao="10/03/2019")], [], [ev(PR, "PRISÃO EM FLAGRANTE", "01/01/2019")])
x = [i for i in ra.divergencias_fonte(r) if i["tipo"] == "divergencia-seeu-prisao-antes-do-fato"]
ok(len(x) == 1 and x[0]["nivel"] == "verificar" and "detração entre processos" in x[0]["detalhe"], "53: %s" % x)

# ---- 57: PADIC extinto/arquivado por prescrição não produz efeito ----
ficha = {"versao_leitura": 0, "eventos": [
    {"data": "26.03.2022", "texto": "CONSELHO DISCIPLINAR: REGISTRO DE FALTA DISCIPLINAR COM FULCRO NO ART. 60 DA LEP, POR TER INFRINGINDO EM TESE O ART 50, INCISO VI DA LEP. RESPONDE PROCESSO - PADIC/PDIB."},
    {"data": "13.03.2023", "texto": "CONSELHO DISCIPLINAR: TOMOU CIÊNCIA DO RESULTADO PROCESSO - PADIC / PDIB Nº 31/025.964/2022 , REFERENTE AO FATO OCORRIDO EM 26/03/2022, "
                                    "CONFORME DECISÃO DO CONSELHO DISCIPLINAR, RECONHECIDA A PRESCRIÇÃO DA PRETENSÃO DISCIPLINAR."}]}
fx = rf.atualizar(ficha)
fl = [x for x in fx.get("faltas", []) if x.get("data_fato") == "26.03.2022"]
ok(fl and fl[0]["situacao"] == "arquivada" and fl[0].get("resultado_tipo") == "extinto", "57: %s" % fl)

# ---- 58: término além do limite de 30 anos: término calculado pelo programa na coluna ----
c30 = [crime(pena_imposta="25 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="10/01/2015"),
       crime(processo_criminal=P2, pena_imposta="20 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="12/01/2015")]
r = reg(c30, [inc(AR, "Fechado - Regime Inicial", "", "15/01/2015")], [ev(PR, "PRISÃO EM FLAGRANTE", "15/01/2015")],
        pena_total="45a0m0d", termino_previsao_seeu="15/01/2060", data_base_seeu="15/01/2015")
x = itens(r, "limite-de-cumprimento-art-75")
ok(len(x) == 1 and x[0]["nivel"] == "alerta" and x[0].get("termino_limite") == "14/01/2045", "58 alerta: %s" % x)
m = rv.modelo(copy.deepcopy(r), {}, None, [])
ok(m["termino"] == "14/01/2045*" and "calculado pelo programa" in m["calc_notas"].get("termino", "") and "15/01/2060" in m["termino_motivo"],
   "58 coluna: %s | %s" % (m["termino"], m.get("calc_notas")))

# ---- 156: fatos antes e depois de 23/01/2020, penas dos anteriores acima de 30 anos: verificar ----
cm = [crime(pena_imposta="32 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="10/01/2015"),
      crime(processo_criminal=P2, pena_imposta="4 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="10/03/2020")]
r = reg(cm, [inc(AR, "Fechado - Regime Inicial", "", "15/03/2020")], [ev(PR, "PRISÃO EM FLAGRANTE", "15/03/2020")],
        pena_total="36a0m0d", termino_previsao_seeu="14/03/2056", data_base_seeu="15/03/2020")
x = itens(r, "limite-de-cumprimento-art-75")
ok(len(x) == 1 and x[0]["nivel"] == "verificar" and "30 anos" in x[0]["titulo"] and "XL" in x[0]["detalhe"] and not x[0].get("termino_limite"), "156: %s" % x)

# ---- 59: unidade incerta (estabelecimento penal genérico) -> verificar; penitenciária -> alerta ----
ok(rf.unidade_incerta("ESTABELECIMENTO PENAL DE NAVIRAÍ") and not rf.unidade_incerta("PENITENCIÁRIA ESTADUAL DE DOURADOS"), "59 classificação")
for un, niv in (("ESTABELECIMENTO PENAL DE NAVIRAÍ", "verificar"), ("PENITENCIÁRIA ESTADUAL DE DOURADOS", "alerta")):
    x = rf._unidade_x_ficha(reg([crime()], [], [ev(PR, "PRISÃO", "10/01/2016")], regime_atual="Semiaberto - ATIVO"), {"unidade": un})
    ok(len(x) == 1 and x[0]["nivel"] == niv and "Vinculante 56" in x[0]["detalhe"], "59 %s: %s" % (un, x))

# ---- 147: art. 115 no acórdão (pena fixada em grau de recurso) ----
r = reg([crime(data_infracao="10/01/2015", data_sentenca="10/06/2015", transito_mp="10/07/2016", transito_processo="10/07/2016",
               pena_total_processo="10a0m0d - APELAÇÃO CRIMINAL")], [], [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2016")],
        data_nascimento="01/01/1946")
pr = rp.analisar(copy.deepcopy(r), date(2026, 10, 16))
av = " | ".join(a for l in pr["presc_linhas"] for a in l.get("avisos", []))
ok("art. 115 a verificar" in av and "grau de recurso" in av, "147 art. 115: %s" % av)

# ---- 148 e 150: falta "a apurar" e conduta "sem lapso" a conferir (amarelo); falta reconhecida não atende ----
for cond, fal, esp in (("ÓTIMA", "A APURAR", None), ("SEM LAPSO", "NÃO", None), ("ÓTIMA", "SIM", False), ("MÁ", "NÃO", False), ("BOA", "NÃO", True)):
    out = []
    rv._conduta_requisito(lambda o, t: out.append((o, t)), {"conduta": cond}, fal)
    ok(out[0][0] is esp, "148/150 %s/%s: %s" % (cond, fal, out))
    if cond == "SEM LAPSO":
        ok("atestado de conduta" in out[0][1], "150 texto: %s" % out)
    if fal == "A APURAR":
        ok("533" in out[0][1], "148 texto: %s" % out)
r = reg([crime()], [], [ev(PR, "PRISÃO", "10/01/2016")], regime_atual="Fechado - ATIVO", falta_12m="A APURAR", status_execucao="ATIVO")
pa = rv.progressao_antecipada(r, {"conduta": "ÓTIMA", "data_impressao": "10/10/2026"}, {"prog_dias": 25, "prog": "10/11/2026"}, hoje=date(2026, 10, 16))
ok(pa["pa_quase"] and not pa["pa_ok"], "148 progressão antecipada amarela: %s" % pa)

# ---- 149: semiaberto no RSPE e ficha do monitoramento: amarelo ----
r = reg([crime()], [], [ev(PR, "PRISÃO", "10/01/2016")], regime_atual="Semiaberto - ATIVO", pena_cumprida="5a0m0d", status_execucao="ATIVO")
fi = {"unidade": "UNIDADE MISTA DE MONITORAMENTO VIRTUAL ESTADUAL", "conduta": "BOA", "data_impressao": "10/10/2026", "eventos": [], "trabalho": []}
st = rv.saida_temporaria(r, fi, {}, None, False, date(2026, 10, 16))
ui = [i for i in st["st_itens"] if "monitoramento" in i["txt"]]
ok(ui and ui[0]["ok"] is None and "Vinculante 56" in ui[0]["txt"], "149: %s" % st["st_itens"])

# ---- 155: prisão cautelar em outro processo, com fato anterior, encerrada por absolvição: verificar (e extinção a verificar) ----
r = reg([crime(processo_criminal="8800071-00.2022.8.12.0001", data_infracao="01/06/2022", pena_imposta="1 ano(s), 0 mês(es) e 0 dia(s)")], [],
        [ev(PR, "PRISÃO PREVENTIVA", "01/01/2023", "8800671-00.2023.8.12.0001"),
         ev("INTERRUPÇÃO", "ALVARA DE SOLTURA - ABSOLVICAO", "31/03/2024", "8800671-00.2023.8.12.0001")],
        pena_total="1a0m0d", pena_cumprida="0a0m0d", pena_remanescente="1a0m0d", regime_atual="Aberto - ATIVO", data_base_seeu="")
x = itens(r, "detracao-prisao-em-outro-processo")
ok(len(x) == 1 and x[0]["nivel"] == "verificar" and "01/01/2023 a 31/03/2024" in x[0]["titulo"] and "extinção" in x[0]["detalhe"], "155: %s" % x)
# processo da prisão desta execução, ou fato posterior à prisão: nada
r2 = copy.deepcopy(r); r2["_crimes"][0]["data_infracao"] = "01/06/2024"
ok(not itens(r2, "detracao-prisao-em-outro-processo"), "155: fato posterior à prisão")

if falhas:
    print("FALHOU (quesitos 16/10, data-base):")
    for f_ in falhas:
        print("  " + f_)
    sys.exit(1)
print("ok: quesitos 16/10 - data-base (itens 45, 47, 48, 50, 51, 52, 53, 57, 58, 59, 145, 147, 148, 149, 150, 155, 156)")
