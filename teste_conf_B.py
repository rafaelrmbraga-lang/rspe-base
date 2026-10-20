"""Teste da conferência manual (frente B - faltas disciplinares): a fuga é uma ocorrência só (regressão cautelar decretada
durante ela e homologação lançada na recaptura não são outras faltas), falta permanente contada da recaptura (12 meses do art.
83, III, b, do CP e prescrição disciplinar), recaptura lida da ficha, sanção (regressão/perda de remidos) que revela falta
reconhecida, crime doloso durante a execução como falta grave no livramento (LEP, art. 52; Súmula 526/STJ), data do SEEU
que é só 12 meses de falta não reconhecida (a verificar), "Responde PADIC" a conferir, falta nos 12 meses contada até hoje,
perda de remidos por falta inferida, número de processo com ponto na ficha e livramento x unidade fechada (sem SV 56).
Casos hipotéticos, nomes fictícios.
Rodar: python teste_conf_B.py"""
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
HOJE = date(2026, 10, 20)


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


AR = "FIXAÇÃO/ALTERAÇÃO DE REGIME"
PR = "PRISÃO/INÍCIO DE CUMPRIMENTO"
IN = "INTERRUPÇÃO"
HF = "HOMOLOGAÇÃO DE FALTA GRAVE"
P1 = "0000001-11.2015.8.12.0001"


def inc(tipo, compl, dec, ref, sit="CONCEDIDO"):
    return {"tipo": tipo, "motivo": "", "complemento": compl, "data": "", "data_decisao": dec, "data_referencia": ref, "processos": P1, "situacao": sit}


def ev(tipo, motivo, data):
    return {"tipo": tipo, "motivo": motivo, "data": data, "processos": P1}


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
         "fracao_progressao_aplicada": "1/6", "data_geracao_rspe": "06/10/2026", "data_base_seeu": "01/03/2024", "_crimes": crimes,
         "_incidentes": list(incs), "_eventos": list(eventos), "saldo_remidos": "0 dias (0 dias remidos - 0 dias perdidos)"}
    r.update(kw)
    return r


def falta(r, hoje=HOJE):
    return rs.faltas(r, r["_eventos"], r["_incidentes"], hoje, r["_crimes"])


def aud_titulos(r):
    return [i["titulo"] for i in ra.auditar(copy.deepcopy(r), HOJE)["aud_itens"]]


# ---- 1. fuga já homologada no RSPE (homologação com referência na recaptura): a regressão cautelar decretada durante a fuga não é
# falta "a apurar", nem a fuga é "informar se houve sanção"; a homologação conta pela fuga inteira ----
evs = [ev(PR, "PRISÃO EM FLAGRANTE", "17/04/2019"), ev(IN, "FUGA", "31/05/2024"), ev(PR, "RECAPTURA/REINÍCIO DE CUMPRIMENTO", "22/03/2025")]
incs = [inc(AR, "Fechado - Regime Inicial", "", "17/04/2019"), inc(AR, "Fechado - Regressão Cautelar", "22/10/2024", "22/10/2024"),
        inc("DIAS PERDIDOS NA REMIÇÃO", "7", "27/05/2025", "22/03/2025"), inc(HF, "22/03/2025", "27/05/2025", "22/03/2025"),
        inc(AR, "Fechado - Regressão", "27/05/2025", "22/03/2025")]
r1 = reg([crime()], incs, evs)
ok(rs.faltas_editaveis(r1["_incidentes"], r1["_eventos"], HOJE) == [], "1 itens a apurar: %s" % rs.faltas_editaveis(r1["_incidentes"], r1["_eventos"], HOJE))
t1 = aud_titulos(r1)
ok(not any(t.startswith(("Falta a apurar", "Fuga em")) for t in t1), "1 auditoria: %s" % t1)
ok(falta(r1)["falta_12m"] == "não consta", "1 falta 12m: %s" % falta(r1))
# art. 6º do Decreto de 2024 (publicação 23/12/2024): a fuga homologada começou na janela - falta reconhecida, não "não homologada"
ff, fv = rs.falta_art6(r1["_incidentes"], date(2024, 12, 25), r1["_eventos"], date(2024, 12, 23))
ok(ff and "homologada" in ff[0] and "não homologada" not in ff[0] and not fv, "1 art. 6º: %s / %s" % (ff, fv))

# ---- 2. regressão cautelar seguida da homologação da mesma falta (sem evento de fuga) ----
r2 = reg([crime()], [inc(AR, "Fechado - Regime Inicial", "", "15/03/2012"), inc(AR, "Fechado - Regressão Cautelar", "28/04/2025", "28/04/2025"),
                     inc(HF, "30/04/2025", "30/06/2025", "30/04/2025"), inc(AR, "Fechado - Regressão", "30/06/2025", "30/06/2025")],
         [ev(PR, "PRISÃO DEFINITIVA", "15/03/2012")])
ok(rs.faltas_editaveis(r2["_incidentes"], r2["_eventos"], HOJE) == [], "2 cautelar + homologação: %s" % rs.faltas_editaveis(r2["_incidentes"], r2["_eventos"], HOJE))

# ---- 3. fuga sem homologação, recapturada há menos de 12 meses (começou há mais): falta a apurar, uma ocorrência só, sem
# "pode ser soma de penas"; os 12 meses e a prescrição contam da recaptura ----
evs = [ev(PR, "PRISÃO EM FLAGRANTE", "19/11/2013"), ev(IN, "FUGA", "10/07/2024"), ev(PR, "RECAPTURA/REINÍCIO DE CUMPRIMENTO", "19/11/2025")]
r3 = reg([crime()], [inc(AR, "Fechado - Regime Inicial", "", "19/11/2013"), inc(AR, "Fechado - Regressão Cautelar", "05/08/2024", "05/08/2024")], evs)
f3 = falta(r3)
ok(f3["falta_12m"] == "A APURAR" and "recaptura em 19/11/2025" in f3["falta_12m_detalhe"] and "soma de penas" not in f3["falta_12m_detalhe"]
   and "regressão cautelar da mesma ocorrência em 05/08/2024" in f3["falta_12m_detalhe"], "3 falta 12m: %s" % f3)
fe3 = rs.faltas_editaveis(r3["_incidentes"], r3["_eventos"], HOJE)
ok(len(fe3) == 1 and fe3[0]["recaptura"] == "19/11/2025" and fe3[0]["presc_termo"] == "19/11/2025" and fe3[0]["vinculados"],
   "3 itens: %s" % fe3)
# a data do SEEU (19/11/2026) é só 12 meses da fuga não homologada: a verificar
lf = rs.falta_livramento(r3, date(2026, 11, 19), HOJE)
ok(lf and lf[0] == "apurar" and lf[1] == date(2025, 11, 19), "3 livramento: %s" % (lf,))

# ---- 4. evasão (descumprimento) com regressão definitiva e perda de remidos sem o incidente de homologação: falta reconhecida,
# pela ocorrência; o livramento só 12 meses depois da recaptura ----
evs = [ev(PR, "PRISÃO DEFINITIVA", "27/10/2021"), ev(IN, "DESCUMPRIMENTO DAS CONDIÇÕES", "13/12/2025"),
       ev(PR, "RECAPTURA/REINÍCIO DE CUMPRIMENTO", "26/05/2026")]
r4 = reg([crime()], [inc(AR, "Fechado - Regime Inicial", "", "27/10/2021"), inc(AR, "Fechado - Regressão Cautelar", "14/05/2026", "14/05/2026"),
                     inc("DIAS PERDIDOS NA REMIÇÃO", "5", "18/08/2026", "18/08/2026"), inc(AR, "Fechado - Regressão", "18/08/2026", "18/08/2026")], evs)
f4 = falta(r4)
ok(f4["falta_12m"] == "SIM" and "reconhecida em juízo" in f4["falta_12m_detalhe"] and "soma de penas" not in f4["falta_12m_detalhe"], "4 falta: %s" % f4)
lf = rs.falta_livramento(r4, date(2025, 12, 3), HOJE)
ok(lf and lf[0] == "firme" and lf[1] == date(2027, 5, 26), "4 livramento: %s" % (lf,))
t4 = aud_titulos(r4)
ok(any("falta grave reconhecida em juízo" in t for t in t4) and not any(t.startswith("Falta a apurar em 14/05/2026") for t in t4), "4 auditoria: %s" % t4)

# ---- 5. crime doloso cometido no aberto (custódia em curso), com condenação transitada: falta grave (LEP, art. 52) no campo de
# falta e no livramento; sem trânsito, a apurar ----
evs = [ev(PR, "PRISÃO EM FLAGRANTE", "15/01/2015"), ev(PR, "PRISÃO EM FLAGRANTE", "03/01/2026")]
novo = crime(artigo="ART 157: Roubo", tipo_penal="CAPUT: Subtrair coisa móvel alheia, mediante grave ameaça", data_infracao="03/01/2026",
             data_sentenca="17/04/2026", transito_mp="27/04/2026", transito_processo="04/05/2026", processo_criminal="0900351-27.2026.8.12.0001")
r5 = reg([crime(), novo], [inc(AR, "Fechado - Regime Inicial", "", "15/01/2015"), inc(AR, "Aberto - Progressão de Regime", "09/07/2025", "09/07/2025")], evs)
f5 = falta(r5)
ok(f5["falta_12m"] == "SIM" and "Súmula 526" in f5["falta_12m_detalhe"], "5 falta: %s" % f5)
lf = rs.falta_livramento(r5, date(2024, 1, 13), HOJE)
ok(lf and lf[0] == "firme" and lf[1] == date(2027, 1, 3), "5 livramento: %s" % (lf,))
r5b = reg([crime(), dict(novo, transito_mp="", transito_processo="")], r5["_incidentes"], evs)
ok(falta(r5b)["falta_12m"] == "A APURAR", "5 sem trânsito: %s" % falta(r5b))
# o crime que é a própria falta homologada (flagrante na mesma data) não vira outra falta
r5c = reg([crime(), dict(novo, transito_mp="", transito_processo="")], r5["_incidentes"] + [inc(HF, "03/01/2026", "20/02/2026", "03/01/2026")], evs)
ok("durante a execução" not in falta(r5c)["falta_12m_detalhe"], "5 crime = falta homologada: %s" % falta(r5c))

# ---- 6. data futura do SEEU que é 12 meses de falta pendente (ficha, PADIC) - a verificar; com a falta homologada, nada muda ----
r6 = reg([crime()], [inc(AR, "Fechado - Regime Inicial", "", "14/11/2012"),
                     dict(inc("FALTA GRAVE NA FICHA DISCIPLINAR (SIAPEN)", "Data da infração: 10/11/2025 - PADIC instaurado", "", "10/11/2025", "PENDENTE"), _ficha=True)],
         [ev(PR, "PRISÃO PREVENTIVA", "14/11/2012")])
lf = rs.falta_livramento(r6, date(2026, 11, 10), HOJE)
ok(lf and lf[0] == "apurar", "6 livramento: %s" % (lf,))
r6b = reg([crime()], [inc(AR, "Fechado - Regime Inicial", "", "14/11/2012"), inc(HF, "10/11/2025", "10/01/2026", "10/11/2025")],
          [ev(PR, "PRISÃO PREVENTIVA", "14/11/2012")])
ok(rs.falta_livramento(r6b, date(2026, 11, 10), HOJE) is None, "6 homologada: %s" % (rs.falta_livramento(r6b, date(2026, 11, 10), HOJE),))

# ---- 7. fuga da ficha com recaptura registrada na ficha no dia seguinte: prescrição disciplinar da recaptura (já consumada) ----
fic = {"eventos": [{"data": "21.10.2022", "texto": "Saída da Unidade Penal: ESTABELECIMENTO PENAL REGIME SEMIABERTO, Destino: EVASÃO, Motivo: Evasão"},
                   {"data": "22.10.2022", "texto": "Entrada na Unidade Penal: ESTABELECIMENTO PENAL DE AQUIDAUANA, Procedente: 1 DP DE AQUIDAUANA - INTERIOR"}],
       "faltas": []}
ok(rs._recaptura_ficha(fic, date(2022, 10, 21)) == date(2022, 10, 22), "7 recaptura da ficha")
r7 = reg([crime(data_infracao="17/06/2015")], [inc(AR, "Fechado - Regime Inicial", "", "19/07/2015")], [ev(PR, "PRISÃO EM FLAGRANTE", "19/07/2015")])
rs.faltas_da_ficha(r7, fic, HOJE)
ok(not any(i.get("_fuga_ficha") for i in r7["_incidentes"]), "7 fuga prescrita entrou: %s" % r7["_incidentes"])
r7b = reg([crime(data_infracao="17/06/2015")], [inc(AR, "Fechado - Regime Inicial", "", "19/07/2015")], [ev(PR, "PRISÃO EM FLAGRANTE", "19/07/2015")])
fic_b = {"eventos": [dict(e, data=e["data"].replace("2022", "2025")) for e in fic["eventos"]], "faltas": []}
rs.faltas_da_ficha(r7b, fic_b, HOJE)
_ff = [i for i in r7b["_incidentes"] if i.get("_fuga_ficha")]
ok(_ff and _ff[0].get("_recaptura") == "22/10/2025", "7 recaptura gravada: %s" % _ff)
# sem evento do RSPE (execução sem cálculo), a fuga da ficha posterior ao fato entra (não é "de outra execução")
r7c = reg([crime(data_infracao="17/05/2018")], [], [])
rs.faltas_da_ficha(r7c, fic_b, HOJE)
ok(any(i.get("_fuga_ficha") for i in r7c["_incidentes"]), "7 sem eventos no RSPE: %s" % r7c["_incidentes"])

# ---- 8. interrupção e prisão em flagrante no mesmo dia: a recaptura é o próprio dia (não "sem recaptura") ----
eps = rs.episodios_evasao([], [ev(PR, "PRISÃO DEFINITIVA", "20/07/2017"), ev(IN, "DESCUMPRIMENTO DAS CONDIÇÕES", "09/09/2021"),
                              ev(PR, "PRISÃO EM FLAGRANTE", "09/09/2021")])
ok(eps and eps[0]["fim"] == date(2021, 9, 9), "8 recaptura no mesmo dia: %s" % eps)

# ---- 9. "Responde PADIC/IPCG": a conferir, não "não atendido" ----
out = []
rv._conduta_requisito(lambda o, t: out.append((o, t)), {"conduta": "RESPONDE PADIC/IPCG"}, "não consta")
ok(out[0][0] is None and "PADIC" in out[0][1], "9 PADIC: %s" % out)
out = []
rv._conduta_requisito(lambda o, t: out.append((o, t)), {"conduta": "RESPONDE PADIC/IPCG"}, "SIM")
ok(out[0][0] is False, "9 PADIC com falta reconhecida: %s" % out)

# ---- 10. falta de 12/10/2025: dentro dos 12 meses na emissão do RSPE (06/10/2026), fora deles hoje (20/10/2026) ----
r10 = reg([crime()], [inc(AR, "Fechado - Regime Inicial", "", "01/03/2016"), inc(HF, "12/10/2025", "20/01/2026", "12/10/2025")],
          [ev(PR, "PRISÃO EM FLAGRANTE", "01/03/2016")])
r10.update(falta(r10, date(2026, 10, 6)))
ok(r10["falta_12m"] == "SIM" and rv.falta_12m_hoje(r10, HOJE) == "não consta", "10 falta hoje: %s / %s" % (r10["falta_12m"], rv.falta_12m_hoje(r10, HOJE)))

# ---- 11. perda de remidos da evasão sem homologação: não se soma à falta homologada anterior (base de 1/3 própria, a verificar) ----
incs = [inc(AR, "Semiaberto - Regime Inicial", "", "20/07/2017"), inc("REMIÇÃO", "23 Dia(s) Remido(s)", "03/12/2014", "03/12/2014"),
        inc(HF, "25/11/2016", "25/11/2016", "25/11/2016"), inc("DIAS PERDIDOS NA REMIÇÃO", "4", "28/03/2017", "28/03/2017"),
        inc("REMIÇÃO", "142 Dia(s) Remido(s)", "21/06/2021", "21/06/2021"),
        inc(AR, "Fechado - Regressão", "01/02/2022", "01/02/2022"), inc("DIAS PERDIDOS NA REMIÇÃO", "53", "01/02/2022", "01/02/2022")]
evs = [ev(PR, "PRISÃO DEFINITIVA", "20/07/2017"), ev(IN, "DESCUMPRIMENTO DAS CONDIÇÕES", "09/09/2021"), ev(PR, "PRISÃO EM FLAGRANTE", "09/09/2021")]
res, fs, _p = ra.perdas_por_falta(incs, evs)
x = [y for y in res if y["falta"] == date(2021, 9, 9)]
ok(x and x[0]["perda"] == 53 and x[0]["janela"] == 142 and x[0]["inferida"], "11 perda pela evasão: %s" % res)
x16 = [y for y in res if y["falta"] == date(2016, 11, 25)]
ok(x16 and x16[0]["perda"] == 4, "11 perda de 2016: %s" % x16)
its = ra._perda_remidos(incs, 57, evs)
ok(any(i["nivel"] == "verificar" and "09/09/2021" in i["titulo"] for i in its), "11 nível: %s" % [(i["nivel"], i["titulo"]) for i in its])

# ---- 12. número de processo escrito com ponto na ficha ----
import re as _re
t = "Mandado de Prisão Preventiva, conforme autos nº 0003115.29.2013.8.12.0013, expedido"
_a = sorted(set(_re.sub(r"^(\d{7})\.", r"\1-", a) for a in _re.findall(r"(?<![\d.])\d{7}[-.]\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}(?![\d])", t)))
ok(_a == ["0003115-29.2013.8.12.0013"], "12 processo com ponto: %s" % _a)
ok("[-.]" in open("rspe_ficha.py", encoding="utf-8").read(), "12 regra na leitura da ficha")

# ---- 13. em livramento condicional e preso em unidade fechada: verificar a suspensão/revogação, não SV 56 ----
r13 = reg([crime()], [inc(AR, "Fechado - Regime Inicial", "", "19/07/2015"), inc("LIVRAMENTO CONDICIONAL", "03/04/2023", "01/03/2023", "03/04/2023")],
          [ev(PR, "PRISÃO EM FLAGRANTE", "19/07/2015")], regime_atual="Livramento Condicional - ATIVO")
u = rf._unidade_x_ficha(r13, {"unidade": "PENITENCIÁRIA DE DOIS IRMÃO DO BURITI", "data_entrada": "06/08/2026"})
ok(u and u[0]["nivel"] == "verificar" and "livramento" in u[0]["titulo"].lower() and "Vinculante 56" not in u[0]["fundamento"], "13 livramento x unidade: %s" % u)

if falhas:
    print("FALHAS (conferência - faltas disciplinares):")
    for f in falhas:
        print("  " + f)
    sys.exit(1)
print("ok: conferência - faltas disciplinares (fuga homologada na recaptura, cautelar da mesma fuga, falta permanente da recaptura, "
      "recaptura da ficha, sanção sem homologação, crime doloso no aberto, data do SEEU por falta a apurar, PADIC, 12 meses até hoje, "
      "perda de remidos, processo com ponto, livramento x unidade)")
