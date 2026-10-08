"""Teste de regressão da revisão da remição (rev6, 07.10): vínculo encerrado pela saída não é reaberto; fuga, soltura, livramento
e regime aberto do RSPE cortam a estimativa; casamento por trabalhados / 3, arredondamento e soma; atestado substituído;
atestado sobreposto a período já remido; atestado sem período que não cabe nos setores citados; decisão em várias linhas;
data de referência; leitura ("06 e07") e remição parcial; isolamento; estudo sem feriados e em curso; itens sem dias
repetidos. Rodar: python teste_remicao_rev6.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf
import rspe_remicao as rrm

falhas = []
HOJE = date(2026, 10, 7)


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def F(eventos, impressao="06/10/2026"):
    return {"data_impressao": impressao, "eventos": [{"data": d, "texto": t} for d, t in eventos]}


def rem(dias, dec, ref=None):
    return {"tipo": "REMIÇÃO", "complemento": "%s Dia(s) Remido(s)" % dias, "data_decisao": dec, "data_referencia": ref or dec, "situacao": "CONCEDIDO"}


def st(C):
    return {a["numero"]: (a["status"], a["remicao"]["dias"] if a.get("remicao") else None) for a in C["atestados"] if a["numero"]}


# ---- E1: a baixa anos depois da saída ("motivo: saída do presídio") não reabre o vínculo ----
f = F([("10.07.2013", "TRABALHO: Iniciou atividade laboral, no setor de trabalho IPCG ARTESANATO, conforme documento CI 1."),
       ("05.11.2013", "Saída da Unidade Penal: INSTITUTO PENAL DE CAMPO GRANDE, Destino: , Motivo: Alvará de Soltura"),
       ("30.03.2024", "TRABALHO: Deixa de trabalhar, no setor de trabalho IPCG ARTESANATO, conforme documento , motivo: Saída do Presídio.")])
vs, _ = rrm.vinculos(f["eventos"], HOJE)
ok(len(vs) == 1 and vs[0]["fim"] == date(2013, 11, 5), "E1: vínculo reaberto pela baixa tardia: %s" % [(v["ini"], v["fim"]) for v in vs])

# ---- E1: fuga do RSPE (sem evasão na ficha) corta a estimativa ----
f = F([("02.01.2023", "TRABALHO: Iniciou atividade laboral, no setor de trabalho CORTE DE CABELO, conforme documento CI 1.")])
r = {"_eventos": [{"data": "02/01/2022", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO EM FLAGRANTE"},
                  {"data": "03/04/2023", "tipo": "INTERRUPÇÃO", "motivo": "FUGA"},
                  {"data": "03/07/2023", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "RECAPTURA/REINÍCIO DE CUMPRIMENTO"}], "_incidentes": []}
C = rrm.conciliar(r, f, date(2023, 12, 30))
per = [(x["ini"], x["fim"]) for x in C["sem_atestado"]]
# (rev9: depois da recaptura a mesma vaga não é retomada sem novo início na ficha - o vínculo termina na véspera da fuga)
ok(per == [(date(2023, 1, 2), date(2023, 4, 2))], "E1: fuga não cortou a estimativa: %s" % per)
# interrupção por prisão em outro processo: o preso segue na unidade (sem corte)
r["_eventos"][1]["motivo"] = "INTERRUPÇÃO POR PRISÃO EM OUTRO PROCESSO"
ok(len(rrm.conciliar(r, f, date(2023, 12, 30))["sem_atestado"]) == 1, "E1: interrupção por prisão em outro processo não corta")

# ---- E10: regime aberto (no Patronato) corta; a volta a unidade fechada encerra o corte ----
f = F([("01.03.2024", "Entrada na Unidade Penal: PATRONATO PENITENCIÁRIO DE PONTA PORÃ, Procedente: PDIB, Conforme OF 1."),
       ("10.12.2024", "TRABALHO: Iniciou atividade laboral, no setor de trabalho AUTONOMO, conforme documento 1."),
       ("20.03.2026", "TRABALHO: Deixa de trabalhar, no setor de trabalho AUTONOMO, conforme documento 1, motivo: N/C."),
       ("21.03.2026", "Entrada na Unidade Penal: PENITENCIÁRIA DE DOIS IRMÃO DO BURITI, Procedente: PATRONATO, Conforme OF 2."),
       ("05.05.2026", "TRABALHO: Iniciou atividade laboral, no setor de trabalho RECICLAGEM, conforme documento 2."),
       ("11.08.2026", "TRABALHO: Deixa de trabalhar, no setor de trabalho RECICLAGEM, conforme documento 2, motivo: N/C.")])
r = {"_eventos": [{"data": "21/08/2015", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO EM FLAGRANTE"}],
     "_incidentes": [{"tipo": "FIXAÇÃO/ALTERAÇÃO DE REGIME", "complemento": "Aberto - Progressão de Regime", "situacao": "CONCEDIDO",
                      "data_referencia": "27/03/2024", "data_decisao": "27/03/2024"}]}
C = rrm.conciliar(r, f, HOJE)
ok([x["setor"] for x in C["sem_atestado"]] == ["Reciclagem"], "E10: aberto no Patronato cortado, unidade fechada não: %s" % [x["setor"] for x in C["sem_atestado"]])

# ---- E2: soma por trabalhados / 3 (86 + 103 = 189; o juízo concedeu 571 / 3 = 190) ----
f = F([("23.07.2018", "Emitido Atestado de Trabalho nº 293/2018, período de 12/04/2016 a 08/02/2017, 260 dias trabalhados e 86 dias remidos."),
       ("24.07.2018", "Emitido Atestado de Trabalho nº 348/2018, período de 09/03/2017 a 11/07/2018, 311 dias trabalhados e 103 dias remidos.")])
C = rrm.conciliar({"_incidentes": [rem(190, "23/08/2018")]}, f, HOJE)
ok(st(C).get("293/2018") == ("CONCILIADO", 190.0) and st(C).get("348/2018") == ("CONCILIADO", 190.0), "E2: soma por trabalhados/3: %s" % st(C))
# remidos digitados abaixo de 1/3: o RSPE concede trabalhados / 3
f = F([("13.11.2023", "Emitido Atestado de Trabalho nº 189/2023, período de 02/06/2022 a 12/11/2023, 341 dias trabalhados e 83,65 dias remidos.")])
C = rrm.conciliar({"_incidentes": [rem(113, "01/03/2024")]}, f, HOJE)
a = C["atestados"][0]
ok(a["status"] == "CONCILIADO" and abs(a["rem"] - 113.67) < 0.01 and a.get("rem_ficha") == 83.65, "E2: remidos abaixo de 1/3: %s %s" % (a["status"], a["rem"]))
# arredondamento: 39,99 x 40 é conciliado
f = F([("13.11.2023", "Emitido Atestado de Trabalho nº 190/2023, período de 01/06/2023 a 12/11/2023, 120 dias trabalhados e 39,99 dias remidos.")])
ok(st(rrm.conciliar({"_incidentes": [rem(40, "01/12/2023")]}, f, HOJE)).get("190/2023") == ("CONCILIADO", 40.0), "E2/E12: 39,99 x 40")

# ---- E3: atestado substituído por outro de número diferente ----
f = F([("03.12.2014", "Emitido Atestado de Trabalho nº 649/2014, período de 01/01/2013 a 30/11/2014, 600 dias trabalhados e 200 dias remidos."),
       ("30.01.2015", "Foi emitido o ATESTADO DE TRABALHO Nº 095/2015/ST/IPCG, período de 01/01/2013 a 30/11/2014, 603 dias trabalhados e 201 dias remidos, "
                      "EM SUBSTITUIÇÃO AO ATESTADO DE TRABALHO ANTERIOR Nº 649/2014/ST/IPCG/AGEPEN/MS.")])
ok([a["numero"] for a in rrm.atestados(f["eventos"])] == ["095/2015"], "E3: atestado substituído continua contando")

# ---- E4: atestado sem remição cobrindo período já remido: só a parte não coberta fica pendente ----
f = F([("02.01.2021", "Emitido Atestado de Trabalho nº 001/2021, período de 01/01/2020 a 31/12/2020, 300 dias trabalhados e 100 dias remidos."),
       ("01.04.2021", "Emitido Atestado de Trabalho nº 050/2021, período de 01/01/2020 a 31/03/2021, 375 dias trabalhados e 125 dias remidos.")])
C = rrm.conciliar({"_incidentes": [rem(100, "10/02/2021")]}, f, HOJE)
a = next(a for a in C["atestados"] if a["numero"] == "050/2021")
ok(a["status"] == "NAO_LANCADO" and 20 <= a.get("rem_pend", 999) <= 30, "E4: sobreposto deveria ficar ≈ 25: %s" % a.get("rem_pend"))

# ---- E5: atestado sem período que não cabe nos setores citados cobre os outros vínculos do intervalo ----
f = F([("03.11.2025", "TRABALHO: Iniciou atividade laboral, no setor de trabalho COZINHA, conforme documento 1."),
       ("29.01.2026", "TRABALHO: Deixa de trabalhar, no setor de trabalho COZINHA, conforme documento 1, motivo: N/C."),
       ("31.03.2026", "TRABALHO: Iniciou atividade laboral, no setor de trabalho FAXINA LTDA, conforme documento 2."),
       ("01.04.2026", "TRABALHO: Deixa de trabalhar, no setor de trabalho FAXINA LTDA, conforme documento 2, motivo: N/C."),
       ("01.04.2026", "TRABALHO: Iniciou atividade laboral, no setor de trabalho CELA LIVRE, conforme documento 3."),
       ("13.07.2026", "TRABALHO: Deixa de trabalhar, no setor de trabalho CELA LIVRE, conforme documento 3, motivo: N/C."),
       ("14.07.2026", "TRABALHO: Iniciou atividade laboral, no setor de trabalho PRENDE BEM, conforme documento 4."),
       ("20.07.2026", "TRABALHO, nesta data foi emitido atestado de trabalho nº235/PDIB/AGEPEN/MS setor de PRENDE BEM E FAXINA LTDA com 56 dias de remição.")])
C = rrm.conciliar({"_incidentes": [rem(56, "24/07/2026", "20/07/2026")]}, f, date(2026, 7, 21))
ok(not [x for x in C["sem_atestado"] if x["setor"] in ("Cozinha", "Cela Livre")], "E5: Cozinha/Cela Livre estimadas de novo: %s" % [(x["setor"], x["ini"]) for x in C["sem_atestado"]])

# ---- E6: a mesma decisão em várias linhas do RSPE ----
f = F([("16.05.2024", "Emitido Atestado de Trabalho nº 262/2024, período de 28/06/2022 a 16/05/2024, 474 dias trabalhados e 158 dias remidos.")])
C = rrm.conciliar({"_incidentes": [rem(23, "03/06/2024", "05/10/2022"), rem(6, "03/06/2024", "02/11/2022"), rem(128, "03/06/2024", "16/05/2024")]}, f, HOJE)
a = C["atestados"][0]
ok(a["status"] == "DIVERGENCIA" and a["remicao"]["dias"] == 157 and len(C["atestados"]) == 1, "E6: linhas da mesma decisão não somadas: %s" % st(C))

# ---- E7: a remição com referência no fim do atestado é dele ----
f = F([("12.01.2022", "Emitido Atestado de Trabalho nº 042/2022, período de 18/08/2021 a 11/01/2022, 126 dias trabalhados e 42 dias remidos."),
       ("12.06.2023", "Emitido Atestado de Trabalho nº 140/2023, período de 15/01/2023 a 12/06/2023, 128 dias trabalhados e 42 dias remidos.")])
s7 = st(rrm.conciliar({"_incidentes": [rem(42, "11/10/2023", "12/06/2023")]}, f, HOJE))
ok(s7.get("140/2023", ("",))[0] == "CONCILIADO" and s7.get("042/2022", ("",))[0] == "NAO_LANCADO", "E7: %s" % s7)

# ---- E8: leitura "meses 02,03,04,05, 06 e07 de 2026" e remição parcial (obra não aprovada) ----
fl = F([("18.08.2026", "EDUCAÇÃO: Peticionado os relatórios de leitura, referentes aos meses 02,03,04,05, 06 e07 de 2026, no sistema SEEU, Autos Nº1."),
        ("24.02.2026", "EDUCAÇÃO: Peticionados os relatórios de leitura, referentes aos meses 11 e 12 de 2025 e mês 01 de 2026, no sistema SEEU, Autos Nº 1.")])
rf.atualizar(fl)
lei = {x["data"]: x["meses"] for x in fl["leituras"]}
ok(len(lei.get("18.08.2026", [])) == 6, "E8: meses lidos: %s" % lei.get("18.08.2026"))
r = {"_eventos": [{"data": "01/01/2020", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}],
     "_incidentes": [rem(24, "28/08/2026"), rem(8, "11/03/2026")]}
_L, res = rf.quadro_trabalho(r, fl, HOJE)
D = res["rem_det"]
# (rev9: a leitura remida em parte fica a conferir na decisão, fora do total - não é "sem remição")
ok(D["leitura"]["dias"] == 0 and sum(i["dias"] for i in D["a_conferir"]["itens"] if i["ref"].startswith("Leitura")) == 4 and not res["conc"]["atestados"],
   "E8: leitura parcial (12 x 8) e 24 da leitura: leitura %s, a conferir %s, trabalho %s" % (
    D["leitura"]["dias"], D["a_conferir"]["itens"], [a["rem"] for a in res["conc"]["atestados"]]))

# ---- E9: isolamento dentro do trabalho sem atestado sai da estimativa ----
ev = [("01.02.2019", "TRABALHO: Iniciou atividade laboral, no setor de trabalho QUALLY PELES, conforme documento 1."),
      ("31.03.2019", "TRABALHO: Deixa de trabalhar, no setor de trabalho QUALLY PELES, conforme documento 1, motivo: N/C.")]
n0 = rrm.conciliar({}, F(ev), HOJE)["sem_atestado"][0]["est"]
n1 = rrm.conciliar({}, F(ev + [("28.02.2019", "CONSELHO DISCIPLINAR: ISOLADO PREVENTIVAMENTE EM CELA DISCIPLINAR, POR 10 DIAS, REFERENTE A FALTA.")]), HOJE)["sem_atestado"][0]["est"]
ok(n0 - n1 == 9, "E9: isolamento de 10 dias (9 de seg. a sáb.) não descontado: %s -> %s" % (n0, n1))

# ---- E11: estudo sem feriados; matrícula aberta há até 90 dias fora do total ----
ok(rf._dias_uteis(date(2026, 9, 7), date(2026, 9, 11)) == 4, "E11: 7 de setembro contado como dia letivo")
fe = F([("01.09.2026", "Nesta data o interno iniciou no setor Escolar.")])
rf.atualizar(fe)
ok(len(fe.get("estudos") or []) == 1, "E11: matrícula não lida")
_L, res = rf.quadro_trabalho({"_eventos": [{"data": "01/01/2020", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}], "_incidentes": []}, fe, HOJE)
ok(res["rem_det"]["estudo"]["dias"] == 0 and res["rem_det"]["em_curso"]["dias"] > 0 and res["rem_det"]["total"] == 0,
   "E11: matrícula recente no total: %s" % {k: res["rem_det"][k]["dias"] for k in ("estudo", "em_curso")})

# ---- E12: vínculos simultâneos sem dias repetidos nos itens; "verificar peticionamento" só sem registro ----
f = F([("01.02.2025", "TRABALHO: Iniciou atividade laboral, no setor de trabalho ARTESANATO, conforme documento 1."),
       ("01.02.2025", "TRABALHO: Iniciou atividade laboral, no setor de trabalho FAXINA, conforme documento 2."),
       ("30.06.2025", "TRABALHO: Deixa de trabalhar, no setor de trabalho ARTESANATO, conforme documento 1, motivo: N/C."),
       ("30.06.2025", "TRABALHO: Deixa de trabalhar, no setor de trabalho FAXINA, conforme documento 2, motivo: N/C."),
       ("10.07.2025", "Peticionado o Atestado de Trabalho nº 300/2025, no Sistema SEEU, função Cozinha (01/07/2024 a 31/12/2024) totalizando 150 dias trabalhados e 50 dias remidos.")])
L, res = rf.quadro_trabalho({"_eventos": [{"data": "01/01/2020", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}], "_incidentes": []}, f, HOJE)
D = res["rem_det"]
ok(sum(i["dias"] for i in D["sem_atestado"]["itens"]) <= D["sem_atestado"]["dias"] + 1, "E12: itens simultâneos com dias repetidos: %s x %s" % (
    [i["dias"] for i in D["sem_atestado"]["itens"]], D["sem_atestado"]["dias"]))
ok(any("peticionado em" in (x.get("sit") or "") and "verificar peticionamento" not in x["sit"] for x in L), "E12: atestado peticionado com 'verificar peticionamento'")

if falhas:
    print("FALHOU (remição rev6):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: remição rev6 (saída, interrupções e aberto, trabalhados/3, substituição, sobreposição, lote, linhas, referência, leitura, isolamento, estudo, itens)")
