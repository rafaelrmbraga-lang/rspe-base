"""Teste de regressão da revisão da remição (rev6, 07.10; ajustado ao modelo da 7.14, sem a conciliação atestado x remição): vínculo encerrado pela saída não é reaberto; fuga, soltura, livramento
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


# ---- E1: a baixa anos depois da saída ("motivo: saída do presídio") não reabre o vínculo ----
f = F([("10.07.2013", "TRABALHO: Iniciou atividade laboral, no setor de trabalho IPCG ARTESANATO, conforme documento CI 1."),
       ("05.11.2013", "Saída da Unidade Penal: INSTITUTO PENAL DE CAMPO GRANDE, Destino: , Motivo: Alvará de Soltura"),
       ("30.03.2024", "TRABALHO: Deixa de trabalhar, no setor de trabalho IPCG ARTESANATO, conforme documento , motivo: Saída do Presídio.")])
vs, _ = rrm.vinculos(f["eventos"], HOJE)
ok(len(vs) == 1 and vs[0]["fim"] == date(2013, 11, 5), "E1: vínculo reaberto pela baixa tardia: %s" % [(v["ini"], v["fim"]) for v in vs])

# (7.14: a conciliação atestado x remição saiu - E2 soma por trabalhados/3, E4 sobreposição, E6 decisão em várias linhas, E7 referência e
# E9 isolamento eram regras de casamento ou da estimativa da conciliação; ficam a leitura e o que o modelo novo faz com os mesmos dados)
def comp(r, f, hoje=HOJE):
    rf.atualizar(f)
    return rf.comparativo(r, f, hoje)


def pedir(o):
    return next((p for p in o["fd_novo"]["pontos"] if p["tipo"] == "pedir_atestado"), None)


# ---- E1: fuga do RSPE (sem evasão na ficha) fica fora da estimativa do trabalho sem atestado ----
f = F([("02.01.2023", "TRABALHO: Iniciou atividade laboral, no setor de trabalho CORTE DE CABELO, conforme documento CI 1.")])
r = {"_eventos": [{"data": "02/01/2022", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO EM FLAGRANTE"},
                  {"data": "03/04/2023", "tipo": "INTERRUPÇÃO", "motivo": "FUGA"},
                  {"data": "03/07/2023", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "RECAPTURA/REINÍCIO DE CUMPRIMENTO"}], "_incidentes": []}
o = comp(r, f, date(2023, 12, 30))
esperado = (rf.dias_trabalho(date(2023, 1, 2), date(2023, 4, 2)) + rf.dias_trabalho(date(2023, 7, 3), date(2023, 12, 30))) / 3.0
ok(pedir(o) and abs(o["fd_novo"]["pedir_dias"] - esperado) < 0.01, "E1: fuga não saiu da estimativa: %s x %s" % (o["fd_novo"]["pedir_dias"], esperado))
# interrupção por prisão em outro processo: o preso segue na unidade (sem corte)
r["_eventos"][1]["motivo"] = "INTERRUPÇÃO POR PRISÃO EM OUTRO PROCESSO"
o = comp(r, f, date(2023, 12, 30))
ok(abs(o["fd_novo"]["pedir_dias"] - rf.dias_trabalho(date(2023, 1, 2), date(2023, 12, 30)) / 3.0) < 0.01, "E1: interrupção por prisão em outro processo cortou")

# ---- E10: regime aberto (no Patronato) fora da estimativa; a volta a unidade fechada encerra o corte ----
f = F([("01.03.2024", "Entrada na Unidade Penal: PATRONATO PENITENCIÁRIO DE PONTA PORÃ, Procedente: PDIB, Conforme OF 1."),
       ("10.12.2024", "TRABALHO: Iniciou atividade laboral, no setor de trabalho AUTONOMO, conforme documento 1."),
       ("20.03.2026", "TRABALHO: Deixa de trabalhar, no setor de trabalho AUTONOMO, conforme documento 1, motivo: N/C."),
       ("21.03.2026", "Entrada na Unidade Penal: PENITENCIÁRIA DE DOIS IRMÃO DO BURITI, Procedente: PATRONATO, Conforme OF 2."),
       ("05.05.2026", "TRABALHO: Iniciou atividade laboral, no setor de trabalho RECICLAGEM, conforme documento 2."),
       ("11.08.2026", "TRABALHO: Deixa de trabalhar, no setor de trabalho RECICLAGEM, conforme documento 2, motivo: N/C.")])
r = {"_eventos": [{"data": "21/08/2015", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO EM FLAGRANTE"}],
     "_incidentes": [{"tipo": "FIXAÇÃO/ALTERAÇÃO DE REGIME", "complemento": "Aberto - Progressão de Regime", "situacao": "CONCEDIDO",
                      "data_referencia": "27/03/2024", "data_decisao": "27/03/2024"}]}
p_ = pedir(comp(r, f))
ok(p_ and "Reciclagem" in p_["texto"] and "Autonomo" not in p_["texto"], "E10: aberto no Patronato fora, unidade fechada dentro: %s" % (p_ or {}).get("texto"))

# ---- E2/E12: 39,99 x 40 - dentro da tolerância de 3 dias da comparação (arredondamento das frações) ----
f = F([("13.11.2023", "Peticionado Atestado de Trabalho nº 190/2023, período de 01/06/2023 a 12/11/2023, 120 dias trabalhados e 39,99 dias remidos.")])
o = comp({"_eventos": [{"data": "01/01/2020", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}], "_incidentes": [rem(40, "01/12/2023")]}, f)
ok(abs(o["fd_novo"]["dif"] + 0.01) < 0.001 and o["fd_novo"]["concl"].startswith("Sem diferença:"), "E2/E12: 39,99 x 40: %s" % o["fd_novo"]["concl"])

# ---- E3: atestado substituído por outro de número diferente ----
f = F([("03.12.2014", "Emitido Atestado de Trabalho nº 649/2014, período de 01/01/2013 a 30/11/2014, 600 dias trabalhados e 200 dias remidos."),
       ("30.01.2015", "Foi emitido o ATESTADO DE TRABALHO Nº 095/2015/ST/IPCG, período de 01/01/2013 a 30/11/2014, 603 dias trabalhados e 201 dias remidos, "
                      "EM SUBSTITUIÇÃO AO ATESTADO DE TRABALHO ANTERIOR Nº 649/2014/ST/IPCG/AGEPEN/MS.")])
ok([a["numero"] for a in rrm.atestados(f["eventos"])] == ["095/2015"], "E3: atestado substituído continua contando")

# ---- E5: trabalho antes da emissão do último atestado (sem período) não vira "pedir atestado" ----
f = F([("03.11.2025", "TRABALHO: Iniciou atividade laboral, no setor de trabalho COZINHA, conforme documento 1."),
       ("29.01.2026", "TRABALHO: Deixa de trabalhar, no setor de trabalho COZINHA, conforme documento 1, motivo: N/C."),
       ("31.03.2026", "TRABALHO: Iniciou atividade laboral, no setor de trabalho FAXINA LTDA, conforme documento 2."),
       ("01.04.2026", "TRABALHO: Deixa de trabalhar, no setor de trabalho FAXINA LTDA, conforme documento 2, motivo: N/C."),
       ("01.04.2026", "TRABALHO: Iniciou atividade laboral, no setor de trabalho CELA LIVRE, conforme documento 3."),
       ("13.07.2026", "TRABALHO: Deixa de trabalhar, no setor de trabalho CELA LIVRE, conforme documento 3, motivo: N/C."),
       ("14.07.2026", "TRABALHO: Iniciou atividade laboral, no setor de trabalho PRENDE BEM, conforme documento 4."),
       ("20.07.2026", "TRABALHO, nesta data foi emitido atestado de trabalho nº235/PDIB/AGEPEN/MS setor de PRENDE BEM E FAXINA LTDA com 56 dias de remição.")])
o = comp({"_eventos": [{"data": "01/01/2020", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}], "_incidentes": [rem(56, "24/07/2026", "20/07/2026")]},
         f, date(2026, 7, 21))
ok(not pedir(o) and o["fd_novo"]["dif"] == 0, "E5: Cozinha/Cela Livre como 'pedir atestado': %s" % (pedir(o) or {}).get("texto"))

# ---- E8: leitura "meses 02,03,04,05, 06 e07 de 2026" (4 dias por obra, 1 obra por mês) na comparação ----
fl = F([("18.08.2026", "EDUCAÇÃO: Peticionado os relatórios de leitura, referentes aos meses 02,03,04,05, 06 e07 de 2026, no sistema SEEU, Autos Nº1."),
        ("24.02.2026", "EDUCAÇÃO: Peticionados os relatórios de leitura, referentes aos meses 11 e 12 de 2025 e mês 01 de 2026, no sistema SEEU, Autos Nº 1.")])
rf.atualizar(fl)
lei = {x["data"]: x["meses"] for x in fl["leituras"]}
ok(len(lei.get("18.08.2026", [])) == 6, "E8: meses lidos: %s" % lei.get("18.08.2026"))
r = {"_eventos": [{"data": "01/01/2020", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}],
     "_incidentes": [rem(24, "28/08/2026"), rem(8, "11/03/2026")]}
N = rf.comparativo(r, fl, HOJE)["fd_novo"]
ok(N["leitura"] == 36 and N["comp"] == 36 and N["dif"] == 4 and N["concl"].startswith("Verificar remição"), "E8: leitura 9 obras x 32 no RSPE: %s %s" % (N["comp"], N["dif"]))

# ---- E11: estudo sem feriados; matrícula sem certidão é estimativa, fora da comparação ----
ok(len(rf.dias_jornada_set(date(2026, 9, 7), date(2026, 9, 11), "seg-sex")) == 4, "E11: 7 de setembro contado como dia letivo")
fe = F([("01.09.2026", "Nesta data o interno iniciou no setor Escolar.")])
rf.atualizar(fe)
ok(len(fe.get("estudos") or []) == 1, "E11: matrícula não lida")
N = rf.comparativo({"_eventos": [{"data": "01/01/2020", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}], "_incidentes": []}, fe, HOJE)["fd_novo"]
ok(N["comp"] == 0 and N["estim"] > 0 and any(p["tipo"] == "estudo_estimado" for p in N["pontos"]), "E11: estudo estimado: %s %s" % (N["comp"], N["estim"]))

# ---- E12: vínculos simultâneos sem dias repetidos na estimativa; atestado peticionado não fica "sem registro de peticionamento" ----
f = F([("01.02.2025", "TRABALHO: Iniciou atividade laboral, no setor de trabalho ARTESANATO, conforme documento 1."),
       ("01.02.2025", "TRABALHO: Iniciou atividade laboral, no setor de trabalho FAXINA, conforme documento 2."),
       ("30.06.2025", "TRABALHO: Deixa de trabalhar, no setor de trabalho ARTESANATO, conforme documento 1, motivo: N/C."),
       ("30.06.2025", "TRABALHO: Deixa de trabalhar, no setor de trabalho FAXINA, conforme documento 2, motivo: N/C."),
       ("10.07.2025", "Peticionado o Atestado de Trabalho nº 300/2025, no Sistema SEEU, função Cozinha (01/07/2024 a 31/12/2024) totalizando 150 dias trabalhados e 50 dias remidos.")])
o = comp({"_eventos": [{"data": "01/01/2020", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}], "_incidentes": []}, f)
N = o["fd_novo"]
ok(abs(sum(L.get("pedir_dias") or 0 for L in N["trab"]["linhas"]) - N["pedir_dias"]) < 0.01
   and abs(N["pedir_dias"] - rf.dias_trabalho(date(2025, 2, 1), date(2025, 6, 30)) / 3.0) < 0.01, "E12: dias simultâneos repetidos: %s" % N["pedir_dias"])
d300 = next(d for d in N["docs"] if d["num"] == "300/2025")
ok(d300["pet_ok"] and d300["pet"] == "peticionado em 10/07/2025", "E12: atestado peticionado: %s" % d300["pet"])

if falhas:
    print("FALHOU (remição rev6):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: remição rev6 (7.14: saída, fuga e aberto fora da estimativa, tolerância, substituição, último atestado, leitura, estudo, simultâneos)")
