"""Terceira rodada de correções (7.14.2), frente progressão, livramento e auditoria: escolta hospitalar não é fuga; baixa
estruturada encerra o trabalho aberto em texto livre; crime anterior ao início efetivo do cumprimento não é falta; unificação
pendente (regime mais grave sem somatório); data-base calculada (não iniciado; regressão = data da falta); textos da execução sem
eventos; saída temporária (trabalho só informação, pena somada, soltura e detração da ficha); notas do SEEU (falta fora dos 12
meses, indeferimento antes do lapso); data-base do SEEU contra a lei como "verificar" na Auditoria (guia nova com a pessoa presa,
livramento movido na soma); detração antes da fração com contas coerentes; 16% x 1/6 com a mesma diferença no título e no
detalhe; "p. ú." sem ponto duplo. Casos hipotéticos, nomes fictícios. Rodar: python teste_conf3_progressao.py"""
import copy
import sys
import types
from datetime import date
from fractions import Fraction

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_auditoria as ra
import rspe_ficha as rf
import rspe_scraper as rs
import rspe_view as rv

falhas = []
HOJE = date(2026, 10, 21)


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


AR = "FIXAÇÃO/ALTERAÇÃO DE REGIME"
PR = "PRISÃO/INÍCIO DE CUMPRIMENTO"
P1, P2 = "0000001-11.2020.8.12.0001", "0000002-22.2025.8.12.0001"


def inc(tipo, compl, dec, ref, sit="CONCEDIDO"):
    return {"tipo": tipo, "motivo": "", "complemento": compl, "data": "", "data_decisao": dec, "data_referencia": ref, "processos": "", "situacao": sit}


def ev(tipo, motivo, data, **kw):
    return dict({"tipo": tipo, "motivo": motivo, "data": data, "processos": P1}, **kw)


def crime(**kw):
    c = {"processo_criminal": P1, "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto", "tipo_penal": "CAPUT: Subtrair",
         "pena_imposta": "2 ano(s), 0 mês(es) e 0 dia(s)", "data_infracao": "10/01/2021", "data_sentenca": "10/06/2021",
         "transito_mp": "10/07/2021", "transito_processo": "10/07/2021", "extinto": "Não", "suspenso": "Não", "vga": "N",
         "resultado_morte": "N", "reincidente_comum": "N", "reincidente_especifico": "N", "comando_orcrim": "N",
         "fracao_progressao": "1/6 - Comum", "fracao_livramento": "1/3 - Comum", "regime_sentenca": "Aberto"}
    c.update(kw)
    return c


def reg(crimes, incs=(), eventos=(), **kw):
    r = {"nome": "Teste Ficticio", "regime_atual": "Fechado - ATIVO", "pena_total": "2a0m0d", "pena_cumprida": "0a6m0d",
         "pena_remanescente": "1a6m0d", "data_geracao_rspe": "01/10/2026", "data_base_seeu": "", "_crimes": crimes,
         "_incidentes": list(incs), "_eventos": list(eventos), "data_nascimento": "01/01/1980", "status_execucao": "ATIVO"}
    r.update(kw)
    return r


def itens(r, tipo=None):
    its = ra.auditar(copy.deepcopy(r), HOJE)["aud_itens"]
    return [i for i in its if tipo is None or i.get("tipo") == tipo]


# ---- P1: escolta hospitalar com "não retornou" do plantão e volta à unidade não é fuga ----
ficha = {"eventos": [
    {"data": "30.03.2022", "texto": "Conforme Of. 62/22/SAU, foi escoltado pela PM até o HOSPITAL MUNICIPAL, para CONSULTA MÉDICA e até o termino do plantão NÃO RETORNOU."},
    {"data": "31.03.2022", "texto": "Mudança de Cela: PENITENCIÁRIA X, Motivo: OF. 62/22/SAU - HOSPITALIZADO, Origem: C03, Destino: TRANSITO."}],
    "faltas": []}
r = reg([crime(data_infracao="10/01/2020")], eventos=[ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2020")])
rs.faltas_da_ficha(r, ficha, HOJE)
ok(not [i for i in r["_incidentes"] if i.get("_fuga_ficha")], "P1: escolta hospitalar virou fuga: %s" % r["_incidentes"])
ficha2 = {"eventos": [{"data": "30.03.2022", "texto": "Saída da Unidade Penal: PENITENCIÁRIA X, Destino: , Motivo: Evasão, Conforme Ofício: 1/22."}], "faltas": []}
r = reg([crime(data_infracao="10/01/2020")], eventos=[ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2020")])
rs.faltas_da_ficha(r, ficha2, HOJE)
ok([i for i in r["_incidentes"] if i.get("_fuga_ficha")], "P1: evasão de verdade deixou de ser fuga")

# ---- P1: "Deixa de trabalhar" estruturado encerra o trabalho aberto em texto livre (outra grafia do setor) ----
f = rf.atualizar({"eventos": [
    {"data": "23.06.2021", "texto": "Passa a exercer suas Atividades Laborais na Montagem de Prendedores Prendebem."},
    {"data": "23.10.2021", "texto": "TRABALHO: Deixa de trabalhar, no setor de trabalho PRENDEBEM/PDIB, conforme documento N/C, motivo: Desistência por opção própria."}]})
tr = f.get("trabalho") or []
ok(tr and tr[-1].get("fim") == "23.10.2021", "P1: trabalho em texto livre não encerrado pela baixa: %s" % tr)

# ---- P2a: crime que dá início ao cumprimento (regime inicial fixado sem nenhum evento do SEEU antes) não é falta ----
c_ant = crime(data_infracao="05/12/2022", data_sentenca="09/05/2024", transito_processo="08/01/2025")
c_novo = crime(processo_criminal=P2, artigo="ART 33: Tráfico de drogas", lei="11343/06", data_infracao="10/10/2025", data_sentenca="01/06/2026",
               transito_processo="24/08/2026", regime_sentenca="Fechado", pena_imposta="5 ano(s), 6 mês(es) e 0 dia(s)",
               fracao_progressao="40% - Art.112, V, da LEP")
r = reg([c_ant, c_novo], [inc(AR, "Aberto - Regime Inicial", "", "09/05/2024")],
        [ev("PRISÃO", "ENTRADA NO SISTEMA PRISIONAL (lançada pela ficha SIAPEN)", "10/10/2025", _ficha=True)],
        regime_atual="Aberto - ATIVO", pena_total="7a3m0d", pena_cumprida="0a0m0d", pena_remanescente="7a3m0d")
fx = rs.faltas(r, r["_eventos"], r["_incidentes"], date(2026, 10, 1), r["_crimes"])
ok(fx.get("falta_12m") not in ("SIM",), "P2a: crime anterior ao início efetivo virou falta: %s" % fx)
# com evento do SEEU antes do fato (cumprimento já iniciado), continua falta
r2 = copy.deepcopy(r)
r2["_eventos"].insert(0, ev(PR, "INÍCIO DO CUMPRIMENTO REGIME ABERTO", "20/05/2024"))
fx = rs.faltas(r2, r2["_eventos"], r2["_incidentes"], date(2026, 10, 1), r2["_crimes"])
ok(fx.get("falta_12m") == "SIM", "P2a: crime no cumprimento já iniciado deixou de ser falta: %s" % fx)

# ---- P2b: unificação pendente: regime a verificar e progressão estimada pelo regime mais grave ----
ok(rs.unificacao_pendente(r) is not None, "P2b: unificação pendente não detectada")
ok(rv.estado_execucao(r) is None or rv.estado_execucao(r)[0] != "aberto", "P2b: 'Já no aberto' com unificação pendente: %s" % (rv.estado_execucao(r),))
t, d = rv.data_progressao(r)
# 40% de 2005 dias = 802; 16% (lei mais benéfica) de 730 = 116: 918 dias desde 10/10/2025
ok(d == date(2025, 10, 10) + rv.timedelta(days=802 + 116) and "unificação pendente" in t, "P2b: estimativa: %s %s" % (t, d))
r3 = copy.deepcopy(r)
r3["_incidentes"].append(inc("SOMATÓRIO DAS PENAS", "", "05/09/2026", "05/09/2026"))
ok(rs.unificacao_pendente(r3) is None, "P2b: somatório depois da sentença ainda acusa unificação pendente")
r4 = dict(copy.deepcopy(r), pena_cumprida="1a0m0d")
ok(rv.data_progressao(r4)[1] is None, "P2b: com pena já cumprida não se estima data")

# ---- P3: data-base calculada ----
# execução não iniciada (sem eventos, regime fixado com a pessoa solta): sem data-base
r = reg([crime()], [inc(AR, "Semiaberto - Regime Inicial", "", "24/03/2026")], [], data_base="24/03/2026", pena_cumprida="0a0m0d")
ok(rv.nao_iniciou(r) and rv.data_base_calculada(r)[0] == "", "P3: data-base exibida sem início do cumprimento: %s" % (rv.data_base_calculada(r),))
ok("não começou" in rv.data_base_info(r, [])["db_motivo"], "P3: motivo da data-base sem início")
# regressão lançada na decisão: data-base na data da falta (volta à custódia depois dela)
r = reg([crime(data_infracao="10/01/2014")],
        [inc(AR, "Fechado - Regressão Cautelar", "28/05/2026", "28/05/2026"), inc("HOMOLOGAÇÃO DE FALTA GRAVE", "11/06/2026", "30/09/2026", "11/06/2026"),
         inc(AR, "Fechado - Regressão", "30/09/2026", "30/09/2026")],
        [ev(PR, "PRISÃO EM FLAGRANTE", "18/05/2014"), ev("INTERRUPÇÃO", "DESCUMPRIMENTO DAS CONDIÇÕES", "04/05/2026"),
         ev("REINÍCIO", "RECAPTURA (lançado pela ficha SIAPEN)", "19/06/2026", _ficha=True)], data_base="30/09/2026")
db = rv.data_base_calculada(r)
ok(db[0] == "19/06/2026" and "Súmula 534" in db[1], "P3: data-base da regressão: %s" % (db,))
r["_eventos"] = r["_eventos"][:1]
db = rv.data_base_calculada(r)
ok(db[0] == "11/06/2026", "P3: falta em custódia: data-base na data da falta: %s" % (db,))

# ---- P4: execução sem eventos - suspensa ou não iniciada, não "interrupção (?)" ----
r = reg([crime()], [inc(AR, "Semiaberto - Regime Inicial", "", "24/03/2026")], [], pena_total="2a0m0d", pena_cumprida="0a3m0d",
        regime_atual="", status_execucao="SUSPENSO OU SOBRESTADO", situacao_cumprimento="PENA INTERROMPIDA (sem evento de reinício)",
        situacao_eventos="PENA INTERROMPIDA (sem evento de reinício)")
x = itens(r, "pena-interrompida-seeu")
ok(x and x[0]["titulo"].startswith("Execução suspensa no SEEU") and "(?)" not in x[0]["detalhe"], "P4: execução suspensa: %s" % x)
r["status_execucao"] = "ATIVO"
x = itens(r, "pena-interrompida-seeu")
ok(x and x[0]["titulo"].startswith("Cumprimento não iniciado no SEEU"), "P4: não iniciada: %s" % x)

# ---- P4: tese crime a crime com o crime marcado reincidente sem base: alinhada ao item da reincidência marcada ----
ok("marca este crime como reincidente" in ra._MARC_TXT[True][0] and "correção do cadastro" in ra._MARC_TXT[True][1], "P4: texto da reincidência marcada")

# ---- P5: saída temporária ----
r = reg([crime()], [inc(AR, "Semiaberto - Regime Inicial", "", "10/06/2021")], [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2021")],
        regime_atual="Semiaberto - ATIVO", pena_cumprida="1a0m0d", pena_remanescente="1a0m0d")
fic = {"unidade": "", "conduta": "OTIMA", "eventos": [], "trabalho": [], "data_impressao": "01/10/2026"}
st = rv.saida_temporaria(r, fic, {"fd_trab": "sem trabalho em curso"}, hoje=HOJE)
tb = [i for i in st["st_itens"] if "trabalho" in i["txt"].lower()]
ok(tb and tb[0]["ok"] == "info" and "não é requisito" in tb[0]["txt"], "P5: trabalho como requisito: %s" % tb)
# guia sem cálculo: a pena da ação sem crime cadastrado entra na soma; nada de "0a0m0d de 0a0m0d"
r = reg([crime(pena_imposta="1 ano(s), 0 mês(es) e 0 dia(s)")], [inc(AR, "Fechado - Regime Inicial", "", "10/06/2021")],
        [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2026")], pena_total="0a0m0d", pena_cumprida="0a0m0d", pena_remanescente="0a0m0d",
        _acoes_sem_crime=[{"processo_criminal": P2, "pena_total_processo": "3a0m0d - PENA ORIGINÁRIA"}])
ok(rv.penas_sem_crime(r) == 3 * 365, "P5: pena da ação sem crime")
st = rv.saida_temporaria(r, None, {}, hoje=HOJE)
pc = [i for i in st["st_itens"] if "pena cumprida" in i["txt"]]
ok(pc and "0a0m0d de 0a0m0d" not in pc[0]["txt"] and "4a0m0d" in pc[0]["txt"], "P5: pena somada: %s" % pc)

# ---- L1 e carona: notas do SEEU ----
s = rv._com_nota("Vencido há 10 dias · verificar criminológico, indeferimento ou falta", "Existe falta grave nos últimos 12 meses em 14/10/2022", date(2025, 1, 1), HOJE)
ok("a falta já está fora dos 12 meses" in s, "L1: falta fora da janela: %s" % s)
s = rv._com_nota("Vencido há 10 dias · verificar", "Existe falta grave nos últimos 12 meses em 01/09/2026", date(2025, 1, 1), HOJE)
ok("fora dos 12 meses" not in s, "L1: falta dentro da janela marcada como fora: %s" % s)
s = rv._com_nota("Vencido há 52 dias · sem pedido no RSPE - requerer", "Indeferido em 24/08/2026", date(2026, 8, 30), HOJE)
ok(s == "Vencido há 52 dias · indeferido antes do lapso (RSPE: Indeferido em 24/08/2026): requerer", "carona: indeferido antes do lapso: %s" % s)

# ---- decisão 1: data-base do SEEU no início da guia nova com a pessoa presa - "verificar" com a data certa ----
c1 = crime(data_infracao="25/09/2014", fracao_progressao="20% - Art.112, II, da LEP")
c2 = crime(processo_criminal=P2, data_infracao="08/07/2025", data_sentenca="16/01/2026", transito_processo="02/02/2026",
           fracao_progressao="20% - Art.112, II, da LEP")
r = reg([c1, c2], [inc(AR, "Aberto - Regime Inicial", "", "02/09/2020"), inc(AR, "Semiaberto - Regime Inicial", "", "17/01/2026"),
                   inc("REMIÇÃO", "60 Dia(s) Remido(s)", "10/03/2026", "10/03/2026")],
        [ev(PR, "PRISÃO EM FLAGRANTE", "01/09/2020"), ev("INTERRUPÇÃO", "LIBERDADE PROVISÓRIA", "18/12/2020"),
         ev(PR, "PRISÃO EM FLAGRANTE", "08/07/2025"), ev(PR, "INÍCIO DO CUMPRIMENTO REGIME SEMIARBERTO", "17/01/2026")],
        regime_atual="Semiaberto - ATIVO", pena_total="4a0m0d", data_base_seeu="17/01/2026", progressao_previsao_seeu="07/12/2026")
x = itens(r, "data-base-no-inicio-da-guia-nova-com-a-pessoa-presa")
ok(x and x[0]["nivel"] == "verificar" and "08/07/2025" in x[0]["titulo"] and "Tema 1006" in x[0]["fundamento"] and "60 dias em 10/03/2026" in x[0]["detalhe"],
   "decisão 1: guia nova com a pessoa presa: %s" % x)
ok(not itens(r, "data-base-confere-com-o-rspe"), "decisão 1: ainda diz que a data-base confere")

# ---- L2: data-base do livramento movida na soma das penas ----
r = reg([crime(data_infracao="10/01/2008")], [inc(AR, "Semiaberto - Regime Inicial", "", "10/01/2008"), inc("SOMATÓRIO DAS PENAS", "", "29/10/2013", "29/10/2013"),
                                               inc("ALTERAÇÃO DE DATA-BASE DE PROGRESSÃO DE REGIME/LIVRAMENTO CONDICIONAL", "Livramento Condicional", "29/10/2013", "29/10/2013")],
        [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2008")], livramento_data_base_seeu="29/10/2013", data_base_seeu="10/01/2008")
x = itens(r, "data-base-do-livramento-na-soma-das-penas")
ok(x and x[0]["nivel"] == "verificar" and "10/01/2008" in x[0]["titulo"] and "Súmula 441" in x[0]["fundamento"], "L2: %s" % x)

# ---- carona: detração antes da fração - total e forma favorável coerentes (subtração em anos, meses e dias) ----
t = ra._texto_blocos([[Fraction(16, 100), 1340, 202, 55, [0, 6, 22]], [Fraction(20, 100), 4000, 1280, 0, [3, 6, 0]]])
ok("Lapso total impresso: 4 anos e 22 dias" in t and "3 anos, 11 meses e 6 dias" in t and "1 mês e 16 dias" in t, "carona: contas da detração: %s" % t)
t = ra._texto_blocos([[Fraction(40, 100), 5550, 1964, 626, [5, 4, 24]]])
ok(t.count("5 anos, 4 meses e 24 dias") == 2, "carona: um bloco, dois valores para o mesmo lapso: %s" % t)

# ---- carona: 16% x 1/6 - título e detalhe com a mesma diferença ----
r = reg([crime(data_infracao="10/01/2021", pena_imposta="2 ano(s), 0 mês(es) e 0 dia(s)")], [inc(AR, "Fechado - Regime Inicial", "", "10/06/2021")],
        [ev(PR, "PRISÃO EM FLAGRANTE", "10/06/2021")], data_base_seeu="10/06/2021")
x = [i for i in itens(r, "percentual-de-progressao-diverge") if "16%" in i["titulo"]]
ok(x and "4 dias a mais" in x[0]["titulo"] and "121,7 dias; 16% = 116,8 dias - 4 dias a mais" in x[0]["detalhe"], "carona 16%%: %s" % x)

# ---- carona: "p. ú.." ----
it = ra._item("info", "t", "d", "CP, art. 83; Lei 11.343/06, art. 44, p. ú..")
ok(it["fundamento"].endswith("p. ú.") and not it["fundamento"].endswith(".."), "carona: ponto duplo: %s" % it)

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for x in falhas:
        print(" -", x)
    sys.exit(1)
print("teste_conf3_progressao: ok")
