"""Teste dos quesitos de 16/10/2026 - remição (itens 100, 101, 104, 107, 108, 109, 112, 114, 116, 117, 118, 119, 120, 136 e 146): atestado
em outros autos fora do total; exame só com dias compatíveis; liberdade provisória x ficha "a verificar"; baixa "Saída do Presídio" com
outro setor no meio; lacuna entre atestados "a conferir"; ressalva do art. 127 (estimativa, remição detalhada, prioridade e ícone); remição
sem atestado limitada a 12 meses; múltipla de 4 só é leitura com projeto na ficha; divergência acima de 3 dias (retificação ou agravo);
remição ficta da pandemia (Tema 1.120); afastamento por acidente ou saúde (art. 126, § 4º); recomeço da contagem só com perda decretada
(art. 127); remidos acima de 1/3 sem corte; atestado sem período fora do total; atestado abaixo de 1/3 como diferença; interrupção do RSPE
com a ficha mostrando a custódia; recesso escolar no estudo. Casos hipotéticos, nomes fictícios. Rodar: python teste_q1610_remicao.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_auditoria as ra
import rspe_ficha as rf
import rspe_relatorio as rrel
import rspe_remicao as rrm

falhas = []
HOJE = date(2026, 10, 16)
INI = "TRABALHO: Iniciou atividade laboral, no setor de trabalho %s, conforme documento 1."
FIM = "TRABALHO: Deixa de trabalhar, no setor de trabalho %s, conforme documento 1, motivo: %s."


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def F(eventos, impressao="10/10/2026"):
    return {"data_impressao": impressao, "eventos": [{"data": d, "texto": t} for d, t in eventos]}


def rem(dias, dec, ref=None):
    return {"tipo": "REMIÇÃO", "complemento": "%s Dia(s) Remido(s)" % dias, "data_decisao": dec, "data_referencia": ref or dec, "situacao": "CONCEDIDO"}


def R(*incs, eventos=(), proc="0001111-22.2019.8.12.0001"):
    return {"processo_execucao": proc, "_eventos": [{"data": "01/01/2015", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}] + list(eventos),
            "_incidentes": list(incs)}


def pend(C, st=None):
    return [p for p in C["pendencias"] if st is None or p["status"] == st]


# ---- 100: atestado peticionado em outros autos sai do total desta execução e fica listado à parte ----
f = F([("01.01.2024", INI % "FAXINA"),
       ("05.07.2024", "Peticionado o Atestado de trabalho n 050/2024, no Sistema SEEU, Autos 0009999-11.2020.8.12.0001, função Faxina (01/01/2024 a "
                      "30/06/2024) totalizando 150 dias trabalhados e 50 dias remidos."),
       ("30.06.2024", FIM % ("FAXINA", "N/C"))])
r = R()
C = rrm.conciliar(r, f, HOJE)
p = pend(C, "OUTROS_AUTOS")
ok(p and "0009999-11.2020.8.12.0001" in p[0]["texto"] and p[0]["cor"] == "cinza" and not pend(C, "NAO_LANCADO"), "100: pendência de outros autos: %s" % C["pendencias"])
t = next(t for t in C["tabela"] if "050/2024" in t["atestado"])
ok(t["cor"] == "cinza" and t["autos_outros"] and "outros autos" in t["rot"], "100: linha da tabela: %s" % t["rot"])
_L, res = rf.quadro_trabalho(r, f, HOJE)
it = res["rem_det"]["nao_lancado"]["itens"]
ok(res["pendentes"] == 0 and it and it[0]["dias"] == 0 and it[0].get("outros_autos") and res["rem_det"]["total"] == 0,
   "100: dias de outros autos no total: %s %s" % (res["pendentes"], [(i["dias"], i["base"]) for i in it]))
# o mesmo atestado peticionado nestes autos segue no total
_L, res = rf.quadro_trabalho(R(proc="0009999-11.2020.8.12.0001"), f, HOJE)
ok(res["pendentes"] == 50, "100: atestado destes autos fora do total: %s" % res["pendentes"])

# ---- 101: remição atribuída a exame só com dias compatíveis com a carga horária ----
ok(rrm.dias_compativeis_exame(133) and rrm.dias_compativeis_exame(100) and rrm.dias_compativeis_exame(25) and not rrm.dias_compativeis_exame(60)
   and not rrm.dias_compativeis_exame(310), "101: faixas do exame")
f = F([("01.03.2025", "Peticionado certificado de aprovação no ENCCEJA 2024.")])
f["exames"] = [{"exame": "ENCCEJA 2024", "data": "01.03.2025", "certificado": True}]
C = rrm.conciliar(R(rem(60, "01/05/2025")), f, HOJE)
ok(not any("atribuídas a exame" in a["texto"] for a in C["alertas"]), "101: 60 dias atribuídos ao exame")
C = rrm.conciliar(R(rem(100, "01/05/2025")), f, HOJE)
ok(any("atribuídas a exame" in a["texto"] and "100 dias" in a["texto"] for a in C["alertas"]), "101: 100 dias não atribuídos ao exame")

# ---- 104: liberdade provisória no RSPE e ficha com a pessoa trabalhando: a verificar, sem dias e sem alterar a custódia ----
f = F([("01.01.2024", INI % "FAXINA"), ("30.06.2024", FIM % ("FAXINA", "N/C"))])
ev = [{"data": "01/03/2024", "tipo": "INTERRUPÇÃO", "motivo": "LIBERDADE PROVISÓRIA"}, {"data": "01/05/2024", "tipo": "REINÍCIO", "motivo": "PRISÃO"}]
C = rrm.conciliar(R(eventos=ev), f, HOJE)
pc = [p for p in pend(C, "A_CONFERIR") if "liberdade provisória" in p["texto"]]
ok(pc and pc[0]["texto"].startswith("Faxina, 01/03/2024 a 30/04/2024"), "104: período da liberdade provisória não ficou a verificar: %s" % C["pendencias"])
ok(any(x["ini"] == date(2024, 5, 1) and not x.get("duvida") for x in C["sem_atestado"]), "104: trabalho depois da interrupção sem estimativa: %s" % C["sem_atestado"])
ok(rrm.fora_da_unidade(R(eventos=ev), HOJE, f) == [(date(2024, 3, 1), date(2024, 4, 30), "liberdade provisória")], "104: custódia alterada")
# fuga no meio do vínculo: o trabalho termina na véspera, com a ressalva do art. 127 (item 109)
ev2 = [{"data": "01/03/2024", "tipo": "INTERRUPÇÃO", "motivo": "FUGA"}, {"data": "01/05/2024", "tipo": "RECAPTURA", "motivo": "RECAPTURA"}]
C = rrm.conciliar(R(eventos=ev2), f, HOJE)
ps = pend(C, "SEM_ATESTADO")
ok(ps and ps[0]["texto"].startswith("Faxina, 01/01/2024 a 29/02/2024") and "salvo perda de até 1/3" in ps[0]["texto"], "109: estimativa até a evasão sem ressalva: %s" % ps)

# ---- 146 (2): interrupção do RSPE e a ficha registra a entrada em unidade de custódia: trabalho a verificar ----
f = F([("01.04.2024", "Entrada na Unidade Penal: INSTITUTO PENAL DE CAMPO GRANDE, Procedente de: DELEGACIA"),
       ("10.04.2024", INI % "COZINHA"), ("30.09.2024", FIM % ("COZINHA", "N/C"))])
ev3 = [{"data": "01/02/2024", "tipo": "INTERRUPÇÃO", "motivo": "FUGA"}, {"data": "01/08/2024", "tipo": "RECAPTURA", "motivo": "RECAPTURA"}]
C = rrm.conciliar(R(eventos=ev3), f, HOJE)
pc = [p for p in pend(C, "A_CONFERIR") if "custódia interrompida" in p["texto"]]
ok(pc and pc[0]["texto"].startswith("Cozinha, 10/04/2024 a 31/07/2024"), "146: trabalho durante a interrupção estimado: %s" % C["pendencias"])
ok(any(x["ini"] == date(2024, 8, 1) and not x.get("duvida") for x in C["sem_atestado"]), "146: trabalho depois da interrupção: %s" % C["sem_atestado"])

# ---- 107: baixa "Saída do Presídio" em vínculo longo com outro setor iniciado e baixado no meio: a conferir desde esse início ----
f = F([("01.01.2023", INI % "PRENDEBEM"), ("01.03.2023", INI % "FAXINA"), ("30.04.2023", FIM % ("FAXINA", "N/C")),
       ("30.06.2024", FIM % ("PRENDEBEM", "Saida do Presídio"))])
V, _av = rrm.vinculos(f["eventos"], HOJE)
v = next(v for v in V if v["setor"].startswith("Prendebem"))
ok(v.get("duvida_desde") == date(2023, 3, 1) and "saída do presídio" in (v.get("duvida") or ""), "107: sem dúvida: %s" % v.get("duvida"))

# ---- 108: intervalo entre atestados com período explícito: lacuna a conferir, sem "Pedir atestado" ----
f = F([("01.01.2023", INI % "COZINHA"),
       ("05.04.2023", "Peticionado o Atestado de trabalho n 001/2023, no Sistema SEEU, função Cozinha (01/01/2023 a 31/03/2023) totalizando 75 dias trabalhados e 25 dias remidos."),
       ("05.01.2024", "Peticionado o Atestado de trabalho n 002/2023, no Sistema SEEU, função Cozinha (01/06/2023 a 31/12/2023) totalizando 180 dias trabalhados e 60 dias remidos."),
       ("31.12.2023", FIM % ("COZINHA", "N/C"))])
C = rrm.conciliar(R(), f, HOJE)
ok(not pend(C, "SEM_ATESTADO") and any("lacuna entre os atestados 001/2023 e 002/2023" in p["texto"] for p in pend(C, "A_CONFERIR"))
   and pend(C, "LACUNA"), "108: lacuna com pedido de atestado: %s" % C["pendencias"])

# ---- 109: falta grave posterior ao período - ressalva na remição detalhada, na prioridade e no ícone ----
f = F([("01.01.2025", INI % "FAXINA"),
       ("05.07.2025", "Peticionado o Atestado de trabalho n 070/2025, no Sistema SEEU, função Faxina (01/01/2025 a 30/06/2025) totalizando 150 dias trabalhados e 50 dias remidos."),
       ("30.06.2025", FIM % ("FAXINA", "N/C"))])
fg = {"tipo": "FALTA GRAVE", "situacao": "CONCEDIDO", "complemento": "Falta cometida em 10/10/2025", "data_referencia": "10/10/2025", "data_decisao": "10/12/2025"}
r = R(fg)
_L, res = rf.quadro_trabalho(r, f, HOJE)
D = res["rem_det"]
ok(D.get("ressalva_127") and "art. 127" in D["nao_lancado"]["itens"][0]["base"], "109: remição detalhada sem ressalva: %s" % D.get("ressalva_127"))
p = rrel.prioridade_remicao({"fd_rem_det": D, "ext_dias": 20})
ok(p and "salvo perda de até 1/3" in p[1], "109: prioridade sem ressalva: %s" % (p,))
_L, res0 = rf.quadro_trabalho(R(), f, HOJE)
p0 = rrel.prioridade_remicao({"fd_rem_det": res0["rem_det"], "ext_dias": 20})
ok(not res0["rem_det"].get("ressalva_127") and p0 and "salvo" not in p0[1], "109: ressalva sem falta grave: %s" % (p0,))
import rspe_view as rv
r["_rem_pend"] = rf.remicao_pendente({"fd_rem_det": D})
ic = rv.prioridade_remicao({"prog": "01/11/2026", "fd_rem_det": D}, r, HOJE)
ok(ic and "salvo perda de até 1/3" in ic[-1], "109: ícone sem ressalva: %s" % ic)

# ---- 112: remição sem atestado só alcança os 12 meses anteriores à referência; o trabalho mais antigo que cobriria fica a conferir ----
f = F([("01.01.2020", INI % "FAXINA"), ("31.12.2023", FIM % ("FAXINA", "N/C"))])
C = rrm.conciliar(R(rem(120, "01/03/2024", "31/12/2023")), f, HOJE)
nr = next(a for a in C["atestados"] if a["origem"] == "rspe")
ok(min(s["ini"] for s in nr["segs"]) >= date(2022, 12, 31), "112: cobertura além de 12 meses: %s" % [(s["ini"], s["fim"]) for s in nr["segs"]])
ok(any("12 meses" in p["texto"] for p in pend(C, "A_CONFERIR")) and any(a["tipo"] == "capacidade" and "12 meses" in a["texto"] for a in C["alertas"]),
   "112: trabalho antigo sem 'a conferir': %s" % C["pendencias"])
ok(pend(C, "SEM_ATESTADO") and all(date(2022, 12, 31) > p["data"] for p in pend(C, "SEM_ATESTADO")), "112: estimativa do trabalho antigo")

# ---- 114: múltipla de 4 é leitura só com projeto de leitura na ficha; sem ele, a origem e o trabalho ficam a conferir ----
ev = [("01.01.2024", INI % "CANTINA"), ("31.05.2024", FIM % ("CANTINA", "N/C"))]
C = rrm.conciliar(R(rem(8, "01/06/2024")), F(ev), HOJE)
ok(any("múltipla de 4" in p["texto"] for p in pend(C, "A_CONFERIR")) and any("sem projeto de leitura" in a["texto"] for a in C["alertas"]),
   "114: múltipla de 4 sem projeto de leitura: %s" % C["pendencias"])
C = rrm.conciliar(R(rem(8, "01/06/2024")), F(ev + [("10.05.2024", "Peticionado relatório de leitura referente aos meses 03 e 04 de 2024.")]), HOJE)
ok(not any("múltipla de 4" in p["texto"] for p in C["pendencias"]) and any("padrão da leitura" in a["texto"] for a in C["alertas"]),
   "114: leitura registrada não reconhecida: %s" % [a["texto"] for a in C["alertas"]])

# ---- 116: remição menor que o atestado - acima de 3 dias, retificação (erro material) ou agravo em execução (5 dias) ----
f = F([("01.01.2024", INI % "FAXINA"),
       ("05.07.2024", "Peticionado o Atestado de trabalho n 060/2024, no Sistema SEEU, função Faxina (01/01/2024 a 30/06/2024) totalizando 150 dias trabalhados e 50 dias remidos."),
       ("30.06.2024", FIM % ("FAXINA", "N/C"))])
C = rrm.conciliar(R(rem(40, "01/08/2024")), f, HOJE)
pd = pend(C, "DIVERGENCIA")
ok(pd and "agravo em execução" in pd[0]["acao"] and "Súmula 700" in pd[0]["acao"] and "retificação" in pd[0]["acao"], "116: texto da divergência: %s" % pd)
C = rrm.conciliar(R(rem(48, "01/08/2024")), f, HOJE)
pd = pend(C, "DIVERGENCIA")
ok(pd and pd[0]["acao"] == "conferir a decisão e requerer a diferença", "116: diferença de 2 dias: %s" % pd)

# ---- 117: baixa pela pandemia com o vínculo ativo - remição ficta a requerer (Tema 1.120), com estimativa ----
f = F([("01.06.2019", INI % "ARTESANATO"), ("19.03.2020", FIM % ("ARTESANATO", "SUSPENSÃO DAS ATIVIDADES EM RAZÃO DA COVID19")),
       ("16.11.2020", INI % "ARTESANATO"), ("30.06.2021", FIM % ("ARTESANATO", "N/C"))])
r = R()
C = rrm.conciliar(r, f, HOJE)
pf = pend(C, "FICTA")
ok(pf and pf[0]["texto"].startswith("Artesanato, 20/03/2020 a 15/11/2020") and "Tema 1.120" in pf[0]["acao"], "117: sem remição ficta: %s" % C["pendencias"])
_L, res = rf.quadro_trabalho(r, f, HOJE)
ok(60 <= res["rem_det"]["ficta"]["dias"] <= 70 and res["rem_det"]["total"] >= res["rem_det"]["ficta"]["dias"], "117: ficta fora do total: %s" % res["rem_det"]["ficta"]["dias"])

# ---- 118: afastamento por acidente (continuidade a requerer) ou por saúde (só a conferir), sem dias no total ----
f = F([("01.01.2024", INI % "PEDREIRO"), ("10.05.2024", FIM % ("PEDREIRO", "ACIDENTE DE TRABALHO")), ("10.07.2024", INI % "PEDREIRO"),
       ("30.09.2024", FIM % ("PEDREIRO", "N/C"))])
C = rrm.conciliar(R(), f, HOJE)
pa = [p for p in pend(C, "A_CONFERIR") if "126, § 4º" in p["texto"]]
ok(pa and "acidente" in pa[0]["texto"] and "continuidade" in pa[0]["acao"] and pa[0]["texto"].startswith("Pedreiro, 11/05/2024 a 09/07/2024"),
   "118: acidente: %s" % C["pendencias"])
f = F([("01.01.2024", INI % "PEDREIRO"), ("10.05.2024", FIM % ("PEDREIRO", "INTERNAÇÃO HOSPITALAR")), ("10.07.2024", INI % "PEDREIRO"),
       ("30.09.2024", FIM % ("PEDREIRO", "N/C"))])
C = rrm.conciliar(R(), f, HOJE)
pa = [p for p in pend(C, "A_CONFERIR") if "126, § 4º" in p["texto"]]
ok(pa and "só no acidente" in pa[0]["texto"] and not any(x.get("ficta") for x in C["sem_atestado"]), "118: saúde: %s" % C["pendencias"])

# ---- 119: a contagem só recomeça na falta anterior com perda de dias decretada ----
def fgr(d):
    return {"tipo": "FALTA GRAVE", "situacao": "CONCEDIDO", "complemento": "Falta cometida em %s" % d, "data_referencia": d, "data_decisao": d}


def perda(n, d):
    return {"tipo": "DIAS REMIDOS PERDIDOS", "situacao": "CONCEDIDO", "complemento": "%d Dia(s)" % n, "data_referencia": d, "data_decisao": d}


incs = [rem(30, "01/01/2019"), fgr("10/05/2019"), rem(30, "01/01/2020"), fgr("15/06/2021"), perda(10, "20/07/2021")]
res, _f, _p = ra.perdas_por_falta(incs)
ok(len(res) == 1 and res[0]["prev"] is None and res[0]["janela"] == 60, "119: falta sem perda reiniciou a contagem: %s" % [(x["falta"], x["prev"]) for x in res])
res, _f, _p = ra.perdas_por_falta(incs + [perda(10, "20/06/2019")])
x = next(x for x in res if x["falta"] == date(2021, 6, 15))
ok(x["prev"] == date(2019, 5, 10) and x["janela"] == 30, "119: falta com perda não reiniciou: %s" % (x["prev"],))

# ---- 120: remidos acima de 1/3 - só alerta (horas além da jornada); corte só no erro evidente de digitação ----
f = F([("05.07.2024", "Peticionado o Atestado de trabalho n 080/2024, no Sistema SEEU, função Faxina (01/01/2024 a 30/06/2024) totalizando 150 dias trabalhados e 70 dias remidos.")])
C = rrm.conciliar(R(), f, HOJE)
a = C["atestados"][0]
ok(a["rem"] == 70 and any("horas além da jornada" in x["texto"] for x in C["alertas"]), "120: corte dos remidos acima de 1/3: %s" % a["rem"])
f = F([("05.07.2024", "Peticionado o Atestado de trabalho n 081/2024, no Sistema SEEU, função Faxina (01/01/2024 a 30/06/2024) totalizando 150 dias trabalhados e 150 dias remidos.")])
C = rrm.conciliar(R(), f, HOJE)
ok(abs(C["atestados"][0]["rem"] - 50) < 0.01 and any("erro evidente" in x["texto"] for x in C["alertas"]), "120: erro evidente sem corte")

# ---- 136: atestado sem período - fora do total e da prioridade, listado "a conferir" ----
f = F([("01.01.2025", INI % "PRENDE BEM"), ("20.06.2025", "TRABALHO, nesta data foi emitido atestado de trabalho nº 115 setor de PRENDE BEM com 40 dias de remição.")])
r = R()
C = rrm.conciliar(r, f, HOJE)
ps = pend(C, "SEM_PERIODO")
ok(ps and ps[0]["cor"] == "amarelo" and "há dias a requerer" in ps[0]["acao"] and not pend(C, "NAO_LANCADO"), "136: pendência: %s" % C["pendencias"])
ok(next(t for t in C["tabela"] if "115" in t["atestado"])["rot"].startswith("Sem período"), "136: linha da tabela")
_L, res = rf.quadro_trabalho(r, f, HOJE)
it = res["rem_det"]["emitido"]["itens"]
ok(res["pendentes"] == 0 and it and it[0]["dias"] == 0 and it[0].get("sem_periodo") and not rf.remicao_pendente({"fd_rem_det": res["rem_det"]}),
   "136: dias no total: %s" % [(i["dias"], i["base"]) for i in it])

# ---- 146 (1): atestado abaixo de 1/3, conciliado com remição do mesmo valor - diferença a pedir ----
f = F([("01.01.2023", INI % "FAXINA"),
       ("05.07.2023", "Peticionado o Atestado de trabalho n 048/2023, no Sistema SEEU, função Faxina (01/01/2023 a 30/06/2023) totalizando 150 dias trabalhados e 40 dias remidos."),
       ("30.06.2023", FIM % ("FAXINA", "N/C"))])
r = R(rem(40, "01/08/2023"))
C = rrm.conciliar(r, f, HOJE)
pd = pend(C, "DIVERGENCIA")
ok(pd and "dariam 50" in pd[0]["texto"] and "retificação do atestado" in pd[0]["acao"], "146: abaixo de 1/3 conciliado: %s" % C["pendencias"])
_L, res = rf.quadro_trabalho(r, f, HOJE)
ok(res["rem_det"]["divergencia"]["dias"] == 10, "146: diferença até 1/3: %s" % res["rem_det"]["divergencia"]["dias"])
# digitação provável nos trabalhados ("1174 trabalhados e 58 remidos"): sem diferença a pedir
f2 = F([("16.09.2024", "TRABALHO- emitido atestado de trabalho nº 134/2024 sendo de 1174 dias trabalhados e 58 dias remidos.")])
C = rrm.conciliar(R(rem(58, "01/10/2024")), f2, HOJE)
ok(not pend(C, "DIVERGENCIA"), "146: diferença pedida sobre digitação provável: %s" % C["pendencias"])

# ---- 146 (3): recesso escolar descontado da estimativa do estudo ----
ok(rf._dias_uteis(date(2025, 1, 1), date(2025, 1, 31)) == 0 and rf._dias_uteis(date(2025, 3, 3), date(2025, 3, 7)) == 5
   and rf.em_recesso(date(2025, 7, 20)) and rf.em_recesso(date(2025, 12, 22)) and not rf.em_recesso(date(2025, 7, 10)), "146: recesso escolar")
h, _decl = rf.horas_estudo({"inicio": "01.01.2025", "fim": "31.12.2025"})
ok(195 * 4 <= h <= 220 * 4, "146: estudo de um ano fora de ~200 dias letivos: %s h" % h)

if falhas:
    print("FALHOU (quesitos 16/10 - remição):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: quesitos 16/10 - remição (outros autos, exame, liberdade provisória x ficha, saída do presídio, lacuna, art. 127, 12 meses, leitura, "
      "divergência, remição ficta, afastamento, recomeço da contagem, horas extras, sem período, abaixo de 1/3, interrupção x ficha, recesso)")
