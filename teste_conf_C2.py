"""Conferência manual de 20/10/2026, frente C2 (data-base, detração e coerência dos alertas): detração antes da fração calculada no
bloco (fração) em que o SEEU a descontou, pelos lapsos que ele imprime por fração; fração sobre a pena inteira (sem alerta); data-base
movida depois de soltura; progressão negada depois de regime inicial tardio (Tema 1165); alertas a favor do assistido ou sem efeito
como informação (pena total menor que a soma, unificação que reduziu a pena, nascimento divergente sem efeito, remição tardia
sem efeito no decreto, nascimento lido da ficha); data-base a 1 dia do marco; prisão ligada a vários processos; data-base
calculada (início do cumprimento e nova prisão com crime); livramento revogado aplicado pelo SEEU; saída temporária e progressão
antecipada com livramento a confirmar; frações exibidas; número de processo com dígito errado na ficha; guia sem pena calculada
com ação sem crime. Casos hipotéticos, nomes fictícios. Rodar: python teste_conf_C2.py"""
import copy
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_auditoria as ra
import rspe_ficha as rf
import rspe_scraper as rs
import rspe_view as rv

falhas = []
HOJE = date(2026, 10, 16)


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


AR = "FIXAÇÃO/ALTERAÇÃO DE REGIME"
PR = "PRISÃO/INÍCIO DE CUMPRIMENTO"
P1, P2, P3 = "0000001-11.2022.8.12.0001", "0000002-22.2024.8.12.0001", "0000003-33.2025.8.12.0001"


def inc(tipo, compl, dec, ref, sit="CONCEDIDO", procs=""):
    return {"tipo": tipo, "motivo": "", "complemento": compl, "data": "", "data_decisao": dec, "data_referencia": ref, "processos": procs, "situacao": sit}


def ev(tipo, motivo, data, procs=P1):
    return {"tipo": tipo, "motivo": motivo, "data": data, "processos": procs}


def crime(**kw):
    c = {"processo_criminal": P1, "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto", "pena_total_processo": "",
         "tipo_penal": "CAPUT: Subtrair, Reclusão: 1 a 4 anos", "pena_imposta": "10 ano(s), 0 mês(es) e 0 dia(s)",
         "data_infracao": "10/01/2015", "data_sentenca": "10/06/2015", "transito_mp": "10/07/2015", "transito_processo": "10/07/2015",
         "extinto": "Não", "suspenso": "Não", "vga": "N", "resultado_morte": "N", "reincidente_comum": "N", "reincidente_especifico": "N",
         "comando_orcrim": "N", "fracao_progressao": "1/6 - Comum", "fracao_livramento": "1/3 - Comum"}
    c.update(kw)
    return c


def reg(crimes, incs=(), eventos=(), **kw):
    r = {"nome": "Teste Ficticio", "regime_atual": "Fechado - ATIVO", "pena_total": "10a0m0d", "pena_cumprida": "3a0m0d", "pena_remanescente": "7a0m0d",
         "fracao_progressao_aplicada": "1/6", "data_geracao_rspe": "01/10/2026", "data_base_seeu": "01/03/2024", "_crimes": crimes,
         "_incidentes": list(incs), "_eventos": list(eventos), "data_nascimento": "01/01/1980"}
    r.update(kw)
    return r


def itens(r, tipo=None):
    its = ra.auditar(copy.deepcopy(r), HOJE)["aud_itens"]
    return [i for i in its if tipo is None or i.get("tipo") == tipo]


RI = "regime-inicial-depois-da-primeira-prisao"
# ---- detração antes da fração: diferença no bloco em que o SEEU a descontou (não pela média ponderada) ----
c30 = crime(artigo="ART 121: Matar alguem", pena_imposta="2 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="30/07/2022", vga="S",
            fracao_progressao="30% - Art.112, IV, da LEP")
c40 = crime(processo_criminal=P2, artigo="ART 217-A: Estupro de vulnerável", pena_imposta="10 ano(s), 0 mês(es) e 0 dia(s)",
            data_infracao="01/01/2024", fracao_progressao="40% - Art.112, V, da LEP")
evs = [ev(PR, "PRISÃO EM FLAGRANTE", "30/07/2022"), ev("INTERRUPÇÃO", "LIBERDADE PROVISÓRIA", "31/08/2023", ""),
       ev(PR, "INÍCIO DO CUMPRIMENTO REGIME FECHADO", "05/01/2024", "%s, %s" % (P1, P2))]
base = dict(pena_total="12a0m0d", data_base_seeu="05/01/2024", progressao_previsao_seeu="01/01/2029")
# 398 dias de detração (30/07/2022 a 31/08/2023) descontados só no bloco de 30%: (730 - 398) x 30% = 100 dias = 0a3m10d
r = reg([c30, c40], [inc(AR, "Fechado - Regime Inicial", "", "05/01/2024")], evs,
        seeu_fracoes_progressao=["Hediondo primário (40%): 4a0m0d", "Reincidente com violência ou grave ameaça (30%): 0a3m10d"], **base)
bl = ra._detracao_blocos(r, r["_crimes"], 398)
ok(bl and [b[3] for b in bl if b[3]] == [398] and [str(b[0]) for b in bl if b[3]] == ["3/10"], "bloco da detração: %s" % bl)
x = itens(r, RI)
ok(len(x) == 1 and x[0]["nivel"] == "alerta" and "bloco de 30%" in x[0]["detalhe"] and "9 meses e 9 dias" in x[0]["detalhe"]
   and "média" not in x[0]["detalhe"], "detração no bloco de 30%%: 398 x 0,7 = 279 dias: %s" % x)
# lapsos com a fração sobre a pena inteira de cada bloco: a detração não foi descontada antes da fração - sem alerta
r2 = dict(r, seeu_fracoes_progressao=["Hediondo primário (40%): 4a0m0d", "Reincidente com violência ou grave ameaça (30%): 0a7m9d"])
x = itens(r2, RI)
ok(len(x) == 1 and x[0]["nivel"] == "info" and "pena inteira" in x[0]["titulo"], "fração sobre a pena inteira: %s" % x)
# sem os lapsos por fração (leitura antiga): conta pela média, rotulada como estimativa
x = itens(dict(r, seeu_fracoes_progressao=None), RI)
ok(len(x) == 1 and x[0]["nivel"] == "alerta" and "estimativa" in x[0]["detalhe"], "sem lapsos: estimativa: %s" % x)

# ---- data-base movida para a nova prisão depois de soltura (regime inicial na primeira prisão): mesmo mecanismo ----
c13 = crime(pena_imposta="13 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="06/03/2017", fracao_progressao="2/5 - Hediondo Primário")
evs3 = [ev(PR, "PRISÃO EM FLAGRANTE", "31/05/2017"), ev("INTERRUPÇÃO", "LIBERDADE PROVISÓRIA", "18/07/2017", ""), ev(PR, "PRISÃO PREVENTIVA", "26/11/2018")]
r3 = reg([c13], [inc(AR, "Fechado - Regime Inicial", "", "31/05/2017")], evs3, pena_total="13a0m0d", data_base_seeu="26/11/2018",
         progressao_previsao_seeu="10/02/2023", seeu_fracoes_progressao=["Hediondo primário (2/5): 5a1m23d"])
x = [i for i in itens(r3, RI) if "Data-base em 26/11/2018" in i["titulo"]]
ok(len(x) == 1 and x[0]["nivel"] == "info" and "29 dias" in x[0]["detalhe"] and "1165" in x[0]["detalhe"], "data-base movida, lapso já atingido: %s" % x)
ok(not [i for i in itens(dict(r3, progressao_previsao_seeu="10/02/2030"), RI) if i["nivel"] == "info" and "Data-base em" in i["titulo"]],
   "lapso futuro: alerta, não info")
# falta, fuga ou crime durante o cumprimento antes da data-base: o lapso sobre a remanescente é o legal - sem o item
r3f = copy.deepcopy(r3)
r3f["_crimes"].append(crime(processo_criminal=P2, pena_imposta="1 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="20/11/2018"))
ok(not [i for i in itens(r3f, RI) if "Data-base em" in i["titulo"]], "crime durante o cumprimento: sem o item")

# ---- regime inicial tardio, progressão negada e depois concedida: a verificar (Tema 1165); sem negativa, superado (item 48) ----
evs4 = [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2015")]
incs4 = [inc(AR, "Fechado - Regime Inicial", "", "10/06/2015"), inc(AR, "Semiaberto - Progressão de Regime", "10/03/2017", "01/03/2017")]
r4 = reg([crime()], incs4 + [inc(AR, "Semiaberto - Progressão de Regime", "05/01/2017", "20/12/2016", sit="NÃO CONCEDIDO")], evs4,
         data_base_seeu="01/03/2017", regime_atual="Semiaberto - ATIVO")
x = itens(r4, RI)
ok(len(x) == 1 and x[0]["nivel"] == "verificar" and "negada" in x[0]["titulo"] and "1165" in x[0]["detalhe"], "progressão negada: %s" % x)
x = itens(dict(r4, _incidentes=incs4), RI)
ok(len(x) == 1 and x[0]["nivel"] == "info" and "superado" in x[0]["titulo"], "sem negativa: superado: %s" % x)

# ---- divergências a favor do assistido ou sem efeito: informação ----
ca = crime(pena_total_processo="5a0m0d - PENA ORIGINÁRIA", pena_imposta="5 ano(s), 0 mês(es) e 0 dia(s)")
cb = crime(processo_criminal=P2, pena_total_processo="3a0m0d - PENA ORIGINÁRIA", pena_imposta="3 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="10/01/2024")
dv = [i for i in ra.divergencias_fonte(reg([ca, cb], pena_total="6a0m0d")) if i["tipo"] == "divergencia-seeu-pena-total"]
ok(dv and dv[0]["nivel"] == "info" and "favorece" in dv[0]["detalhe"], "pena total menor que a soma: info: %s" % dv)
fic = {"data_nascimento": "01.02.1980", "cpf": "", "data_prisao": "10.09.2019"}
dv = [i for i in ra.divergencias_fonte(reg([ca]), fic) if i["tipo"] == "divergencia-siapen-nascimento"]
ok(dv and dv[0]["nivel"] == "info" and "sem efeito" in dv[0]["titulo"], "nascimento sem efeito: info: %s" % dv)
dv = [i for i in ra.divergencias_fonte(reg([ca], _nasc_alt="01/02/1980"), fic) if i["tipo"] == "divergencia-siapen-nascimento"]
ok(dv and dv[0]["nivel"] == "verificar", "nascimento que muda marco: verificar: %s" % dv)
m = rv.modelo(copy.deepcopy(reg([ca, cb], pena_total="6a0m0d")), {}, None, [])
ok(not m["div_seeu"], "divergência informativa não põe o \"!\": %s" % m["div_seeu"])
# unificação que fixou pena menor que a soma dos processos: favorável, sem pedido
cu1 = crime(pena_total_processo="1a8m0d - PENA ORIGINÁRIA", pena_imposta="1 ano(s), 8 mês(es) e 0 dia(s)")
cu2 = crime(processo_criminal=P2, pena_total_processo="1a1m10d - PENA ORIGINÁRIA", pena_imposta="1 ano(s), 1 mês(es) e 10 dia(s)", data_infracao="10/01/2019")
un = inc("UNIFICAÇÃO", "1a8m0d", "18/12/2023", "18/12/2023", procs="%s, %s" % (P1, P2))
x = itens(reg([cu1, cu2], [un], [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2023")], pena_total="1a8m0d"), "unificacao-como-soma")
ok(len(x) == 1 and x[0]["nivel"] == "info" and "favorável" in x[0]["titulo"], "unificação favorável: %s" % x)
x = itens(reg([cu1, cu2], [dict(un, complemento="3a0m0d")], [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2023")], pena_total="3a0m0d"), "unificacao-como-soma")
ok(len(x) == 1 and x[0]["nivel"] == "alerta", "unificação que não reduz: alerta: %s" % x)
# nascimento lido da ficha: nada a verificar
x = itens(reg([crime()], _nasc_fonte="lida da ficha disciplinar do SIAPEN"), "nascimento-nao-consta")
ok(len(x) == 1 and x[0]["nivel"] == "info", "nascimento lido da ficha: info: %s" % x)
# remição tardia: o decreto que ela não alcança não gera alerta
rr = {"indulto_2022": "não atinge: pena dos crimes impeditivos não cumprida até 25/12/2022 (art. 11, p. ú.)", "indulto_2022_status": "nao",
      "indulto_2022_imp": {"exigido": 8760, "cumprido_total": 1904}}
ok(rf._marco_sem_efeito(rr, (date(2022, 12, 25), "do decreto de 25/12/2022"), 54), "remição sem efeito no decreto")
ok(not rf._marco_sem_efeito(dict(rr, indulto_2022_imp={"exigido": 1930, "cumprido_total": 1904}), (date(2022, 12, 25), "do decreto de 25/12/2022"), 54),
   "remição que alcança o impeditivo: com efeito")
ok(not rf._marco_sem_efeito(dict(rr, indulto_2022="POSSÍVEL: art. 5º", indulto_2022_status="possivel"), (date(2022, 12, 25), "do decreto de 25/12/2022"), 54),
   "decreto possível: com efeito")

# ---- data-base a 1 dia do marco: não é "confere" ----
r5 = reg([crime(data_infracao="19/03/2024")], [inc(AR, "Fechado - Regime Inicial", "", "18/03/2024")], [ev(PR, "PRISÃO PREVENTIVA", "18/03/2024")],
         data_base_seeu="19/03/2024")
x = itens(r5, "data-base-confere-com-o-rspe")
ok(len(x) == 1 and x[0]["nivel"] == "info" and "a 1 dia" in x[0]["titulo"] and "data do fato" in x[0]["detalhe"], "data-base a 1 dia: %s" % x)
x = itens(dict(r5, data_base_seeu="18/03/2024"), "data-base-confere-com-o-rspe")
ok(len(x) == 1 and x[0]["nivel"] == "ok", "data-base exata: confere: %s" % x)

# ---- prisão ligada a vários processos: basta um com fato anterior ----
cp1 = crime(pena_total_processo="5a0m0d - PENA ORIGINÁRIA", pena_imposta="5 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="27/12/2006")
cp2 = crime(processo_criminal=P2, pena_total_processo="3a0m0d - PENA ORIGINÁRIA", pena_imposta="3 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="11/08/2014")
T4 = "divergencia-seeu-prisao-antes-do-fato"
ok(not [i for i in ra.divergencias_fonte(reg([cp1, cp2], pena_total="8a0m0d", _eventos=[ev(PR, "PRISÃO PROVISÓRIA", "18/07/2013", "%s, %s" % (P1, P2))])) if i["tipo"] == T4],
   "prisão de vários processos, um com fato anterior: sem item")
ok([i for i in ra.divergencias_fonte(reg([cp1, cp2], pena_total="8a0m0d", _eventos=[ev(PR, "PRISÃO PROVISÓRIA", "18/07/2013", P2)])) if i["tipo"] == T4],
   "prisão só do processo de fato posterior: verificar")

# ---- data-base calculada (o SEEU não imprime) ----
r6 = reg([crime(data_infracao="24/07/2025")], [], [ev(PR, "PRISÃO EM FLAGRANTE", "04/03/2015"), ev("INTERRUPÇÃO", "LIBERDADE PROVISÓRIA", "20/07/2015", ""),
                                                   ev(PR, "PRISÃO EM FLAGRANTE", "24/07/2025")], data_base_seeu="", data_base="04/03/2015")
d, f = rv.data_base_calculada(r6)
ok(d == "24/07/2025" and "nova prisão" in f, "nova prisão com crime: %s %s" % (d, f))
d, f = rv.data_base_calculada(dict(r6, _crimes=[crime(data_infracao="10/01/2014")]))
ok(d == "04/03/2015" and f == "última alteração de regime", "nova prisão sem crime no período: mantém: %s %s" % (d, f))
r7 = reg([crime()], [], [ev(PR, "ENTRADA NO SISTEMA PRISIONAL", "10/10/2025")], data_base_seeu="", data_base="09/05/2024", pena_cumprida="0a0m0d")
d, f = rv.data_base_calculada(r7)
ok(d == "10/10/2025" and "início do cumprimento" in f, "início do cumprimento depois da sentença: %s %s" % (d, f))
dbi = rv.data_base_info(r7, [])
ok(dbi["db"] == "10/10/2025" and "calculada pelo programa" in dbi["db_motivo"], "caixa da data-base: %s" % dbi)

# ---- livramento revogado aplicado pelo SEEU (1/1 "com revogação L.C." sem crime 1/1) ----
lc = inc("LIVRAMENTO CONDICIONAL", "", "15/03/2013", "15/03/2013")
r8 = reg([crime(fracao_livramento="1/2 - Comum Reincidente")], [lc], [], livramento_obs_seeu="", livramento_previsao_seeu="06/01/2040",
         seeu_fracoes_livramento=["Comum Reincidente (1/2): 5a0m0d", "Hediondo reincidente ou com revogação L.C. (1/1): 17a6m0d"])
ok(rs.livramento_em_curso(r8, r8["_incidentes"])[0] is False, "livramento revogado pelo cálculo do SEEU")
ok(rs.livramento_em_curso(dict(r8, seeu_fracoes_livramento=["Comum Reincidente (1/2): 5a0m0d"]), r8["_incidentes"])[0] is True,
   "sem a fração de revogação: segue o livramento")

# ---- saída temporária e progressão antecipada com livramento a confirmar, preso ----
r9 = reg([crime(vga="S")], progressao_previsao_seeu="25/11/2030", status_execucao="ATIVO")
est = ("lc_duvida", "Livramento a confirmar (24/08/2022) · ver Auditoria")
pa = rv.progressao_antecipada(r9, None, {"prog_dias": None, "prog": "—"}, est=est, hoje=HOJE)
ok(pa["pa_itens"][0]["ok"] is None and "livramento antigo a confirmar" in pa["pa_itens"][0]["txt"]
   and "cumprimento não está em curso" not in pa["pa_itens"][0]["txt"], "progressão antecipada, regime: %s" % pa["pa_itens"][0])
ok("25/11/2030" in pa["pa_itens"][1]["txt"] and "sem data" not in pa["pa_itens"][1]["txt"], "progressão antecipada, data do RSPE: %s" % pa["pa_itens"][1])
st = rv.saida_temporaria(r9, None, {}, est=est, hoje=HOJE)
ok("cumprimento não está em curso" not in st["st_itens"][0]["txt"], "saída temporária, regime: %s" % st["st_itens"][0])

# ---- frações exibidas ----
r10 = reg([crime(pena_imposta="0 ano(s), 0 mês(es) e 0 dia(s)", fracao_livramento="1/3 - Comum Primário"),
           crime(processo_criminal=P2, fracao_livramento="1/2 - Comum Reincidente")])
ok(rv.fracoes_texto(r10, "fracao_livramento") == "1/2", "crime sem pena fora das frações: %s" % rv.fracoes_texto(r10, "fracao_livramento"))
r11 = reg([crime(), crime(processo_criminal=P2, fracao_progressao="40% - Art.112, V, da LEP")], seeu_fracoes_progressao=["Comum (1/6): 1a0m0d"])
ok(rv.fracoes_texto(r11, "fracao_progressao") == "16,67%", "só as frações que o SEEU aplicou: %s" % rv.fracoes_texto(r11, "fracao_progressao"))
r12 = reg([crime()], _acoes_sem_crime=[{"processo_criminal": P3, "pena_total_processo": "7a0m0d - PENA ORIGINÁRIA"}])
ok("sem crime cadastrado" in rv.fracoes_texto(r12, "fracao_progressao"), "ação sem crime: fração a conferir")

# ---- número de processo da ficha com dígito verificador diferente: erro de digitação ----
x = rf._processos_x_ficha({"_crimes": [], "processo_execucao": "0000961-93.2018.8.12.0035"},
                          {"autos": ["0000961-63.2018.8.12.0035", "0000272-33.2023.8.12.0016"]})
ok(len(x) == 1 and x[0]["titulo"].endswith(": 1") and "digitação" in x[0]["detalhe"], "processo com dígito errado: %s" % x)

# ---- guia sem pena calculada: a ação sem crime cadastrado entra na soma ----
r13 = reg([crime(pena_imposta="5 ano(s), 5 mês(es) e 15 dia(s)")], [inc(AR, "Fechado - Regime Inicial", "", "10/01/2025")],
          [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2025")], pena_total="0a0m0d", regime_atual="",
          _acoes_sem_crime=[{"processo_criminal": P3, "pena_total_processo": "7a0m0d - PENA ORIGINÁRIA"}])
x = itens(r13, "guia-sem-pena-calculada-pena-total-com")
ok(len(x) == 1 and "12a5m15d" in x[0]["detalhe"] and P3 in x[0]["detalhe"], "guia sem pena: soma com a ação sem crime: %s" % x)

if falhas:
    print("FALHOU (conferência 20/10, frente C2):")
    for f_ in falhas:
        print("  " + f_)
    sys.exit(1)
print("ok: conferência 20/10 - frente C2 (detração por bloco, data-base, alertas a favor do assistido como informação, coerência das abas)")
