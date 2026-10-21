"""Teste dos quesitos de 16/10/2026 - remição (itens 100, 101, 104, 107, 108, 109, 112, 114, 116, 117, 118, 119, 120, 136 e 146): atestado
em outros autos fora do total; exame só com dias compatíveis; liberdade provisória x ficha "a verificar"; baixa "Saída do Presídio" com
outro setor no meio; lacuna entre atestados "a conferir"; ressalva do art. 127 (estimativa, remição detalhada, prioridade e ícone); remição
sem atestado limitada a 12 meses; múltipla de 4 só é leitura com projeto na ficha; divergência acima de 3 dias (retificação ou agravo);
remição ficta da pandemia (Tema 1.120); afastamento por acidente ou saúde (art. 126, § 4º); recomeço da contagem só com perda decretada
(art. 127); remidos acima de 1/3 sem corte; atestado sem período fora do total; atestado abaixo de 1/3 como diferença; interrupção do RSPE
com a ficha mostrando a custódia; recesso escolar no estudo. (7.14: sem a conciliação atestado x remição, saíram os itens 101 - exame pelos dias -, 108, 112, 114 e 116, que
dependiam de ligar remição a atestado; os demais passam ao modelo novo.) Casos hipotéticos, nomes fictícios. Rodar: python teste_q1610_remicao.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_auditoria as ra
import rspe_ficha as rf
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


def N_(r, f):
    rf.atualizar(f)
    return rf.comparativo(r, f, HOJE)


def pts(o, tipo):
    return [p for p in o["fd_novo"]["pontos"] if p["tipo"] == tipo]


# ---- 100: atestado peticionado em outros autos fica à parte (fora da comparação desta execução) ----
f = F([("01.01.2024", INI % "FAXINA"),
       ("05.07.2024", "Peticionado o Atestado de trabalho n 050/2024, no Sistema SEEU, Autos 0009999-11.2020.8.12.0001, função Faxina (01/01/2024 a "
                      "30/06/2024) totalizando 150 dias trabalhados e 50 dias remidos."),
       ("30.06.2024", FIM % ("FAXINA", "N/C"))])
o = N_(R(), f)
d = o["fd_novo"]["docs"][0]
ok(d["fora"].startswith("dirigido a outros autos (0009999-11.2020.8.12.0001)") and o["fd_novo"]["comp"] == 0 and not o["fd_novo"]["fatos"],
   "100: outros autos: %s" % d)
# o mesmo atestado peticionado nestes autos entra na comparação
ok(N_(R(proc="0009999-11.2020.8.12.0001"), f)["fd_novo"]["comp"] == 50, "100: atestado destes autos fora da comparação")

# ---- 101: exame - o valor depende das áreas e do nível: ponto a conferir, fora da comparação ----
f = F([("01.03.2025", "Peticionado certificado de aprovação no ENCCEJA 2024.")])
o = N_(R(rem(100, "01/05/2025")), f)
ok(pts(o, "exame") and o["fd_novo"]["comp"] == 0, "101: exame: %s" % o["fd_novo"]["pontos"])

# ---- 104: liberdade provisória no RSPE: fora da custódia (sem estimativa de trabalho nesse período) ----
f = F([("01.01.2024", INI % "FAXINA"), ("30.06.2024", FIM % ("FAXINA", "N/C"))])
ev = [{"data": "01/03/2024", "tipo": "INTERRUPÇÃO", "motivo": "LIBERDADE PROVISÓRIA"}, {"data": "01/05/2024", "tipo": "REINÍCIO", "motivo": "PRISÃO"}]
ok(rrm.fora_da_unidade(R(eventos=ev), HOJE, f) == [(date(2024, 3, 1), date(2024, 4, 30), "liberdade provisória")], "104: custódia alterada")
o = N_(R(eventos=ev), f)
esp = (rf.dias_trabalho(date(2024, 1, 1), date(2024, 2, 29)) + rf.dias_trabalho(date(2024, 5, 1), date(2024, 6, 30))) / 3.0
ok(abs(o["fd_novo"]["pedir_dias"] - esp) < 0.01, "104: estimativa com a liberdade provisória: %s x %s" % (o["fd_novo"]["pedir_dias"], esp))

# ---- 107: baixa "Saída do Presídio" em vínculo longo com outro setor iniciado e baixado no meio: a conferir desde esse início ----
f = F([("01.01.2023", INI % "PRENDEBEM"), ("01.03.2023", INI % "FAXINA"), ("30.04.2023", FIM % ("FAXINA", "N/C")),
       ("30.06.2024", FIM % ("PRENDEBEM", "Saida do Presídio"))])
V, _av = rrm.vinculos(f["eventos"], HOJE)
v = next(v for v in V if v["setor"].startswith("Prendebem"))
ok(v.get("duvida_desde") == date(2023, 3, 1) and "saída do presídio" in (v.get("duvida") or ""), "107: sem dúvida: %s" % v.get("duvida"))

# ---- 109: falta grave posterior ao documento - ressalva do art. 127 na remição possivelmente pendente e no ícone ----
f = F([("01.01.2025", INI % "FAXINA"),
       ("05.07.2025", "Peticionado o Atestado de trabalho n 070/2025, no Sistema SEEU, função Faxina (01/01/2025 a 30/06/2025) totalizando 150 dias trabalhados e 50 dias remidos."),
       ("30.06.2025", FIM % ("FAXINA", "N/C"))])
fg = {"tipo": "FALTA GRAVE", "situacao": "CONCEDIDO", "complemento": "Falta cometida em 10/10/2025", "data_referencia": "10/10/2025", "data_decisao": "10/12/2025"}
r = R(fg)
o = N_(r, f)
ok("salvo perda de até 1/3" in o["fd_novo"]["ressalva_127"] and o["fd_novo"]["fatos_dias"] == 50, "109: ressalva: %s" % o["fd_novo"]["ressalva_127"])
ok(not N_(R(), f)["fd_novo"]["ressalva_127"], "109: ressalva sem falta grave")
import rspe_view as rv
r["_rem_pend"] = rf.remicao_pendente(o)
ic = rv.prioridade_remicao({"prog": "01/11/2026", "fd_novo": o["fd_novo"]}, r, HOJE)
ok(ic and "salvo perda de até 1/3" in ic[-1], "109: ícone sem ressalva: %s" % ic)

# ---- 117: baixa pela pandemia com o vínculo ativo - remição ficta (Tema 1.120), com estimativa ----
f = F([("01.06.2019", INI % "ARTESANATO"), ("19.03.2020", FIM % ("ARTESANATO", "SUSPENSÃO DAS ATIVIDADES EM RAZÃO DA COVID19")),
       ("16.11.2020", INI % "ARTESANATO"), ("30.06.2021", FIM % ("ARTESANATO", "N/C"))])
pf = pts(N_(R(), f), "ficta")
ok(pf and "20/03/2020 a 15/11/2020" in pf[0]["texto"] and "Tema 1.120" in pf[0]["texto"], "117: sem remição ficta: %s" % pf)

# ---- 118: afastamento por acidente (continuidade) ou por saúde (só no acidente) ----
f = F([("01.01.2024", INI % "PEDREIRO"), ("10.05.2024", FIM % ("PEDREIRO", "ACIDENTE DE TRABALHO")), ("10.07.2024", INI % "PEDREIRO"),
       ("30.09.2024", FIM % ("PEDREIRO", "N/C"))])
pa = pts(N_(R(), f), "acidente")
ok(pa and "126, § 4º" in pa[0]["texto"] and "continuidade" in pa[0]["texto"] and "10/05/2024" in pa[0]["texto"], "118: acidente: %s" % pa)
f = F([("01.01.2024", INI % "PEDREIRO"), ("10.05.2024", FIM % ("PEDREIRO", "INTERNAÇÃO HOSPITALAR")), ("10.07.2024", INI % "PEDREIRO"),
       ("30.09.2024", FIM % ("PEDREIRO", "N/C"))])
o = N_(R(), f)
ok(pts(o, "saude") and "só no acidente" in pts(o, "saude")[0]["texto"] and not pts(o, "ficta"), "118: saúde: %s" % o["fd_novo"]["pontos"])

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

# ---- 120: remidos acima de 1/3 - só aviso (horas além da jornada); a comparação usa o que o atestado declara ----
f = F([("05.07.2024", "Peticionado o Atestado de trabalho n 080/2024, no Sistema SEEU, função Faxina (01/01/2024 a 30/06/2024) totalizando 150 dias trabalhados e 70 dias remidos.")])
o = N_(R(), f)
ok(o["fd_novo"]["comp"] == 70 and pts(o, "terco_acima") and "horas além da" in pts(o, "terco_acima")[0]["texto"], "120: acima de 1/3: %s" % o["fd_novo"]["pontos"])

# ---- 136: atestado sem período entra na comparação; documento posterior à última remição, a conferir ----
f = F([("01.01.2025", INI % "PRENDE BEM"), ("20.06.2025", "TRABALHO, nesta data foi emitido atestado de trabalho nº 115 setor de PRENDE BEM com 40 dias de remição.")])
o = N_(R(), f)
d = o["fd_novo"]["docs"][0]
ok(o["fd_novo"]["comp"] == 40 and d["periodo"] == "sem período no texto" and o["fd_cor"] == "vermelho" and rf.remicao_pendente(o)[0][2] == 40.0,
   "136: atestado sem período: %s %s" % (o["fd_novo"]["comp"], o["fd_sit"]))

# ---- 146 (1): atestado abaixo de 1/3 com os dias trabalhados plausíveis - a conferir; com digitação provável, nada ----
f = F([("01.01.2023", INI % "FAXINA"),
       ("05.07.2023", "Peticionado o Atestado de trabalho n 048/2023, no Sistema SEEU, função Faxina (01/01/2023 a 30/06/2023) totalizando 150 dias trabalhados e 40 dias remidos."),
       ("30.06.2023", FIM % ("FAXINA", "N/C"))])
o = N_(R(rem(40, "01/08/2023")), f)
ok(pts(o, "terco_abaixo") and "abaixo de 1/3 (50)" in pts(o, "terco_abaixo")[0]["texto"] and o["fd_novo"]["dif"] == 0, "146: abaixo de 1/3: %s" % o["fd_novo"]["pontos"])
f2 = F([("16.09.2024", "TRABALHO- emitido atestado de trabalho nº 134/2024 sendo de 1174 dias trabalhados e 58 dias remidos.")])
ok(not pts(N_(R(rem(58, "01/10/2024")), f2), "terco_abaixo"), "146: diferença sobre digitação provável")

# ---- 146 (3): recesso escolar fora da estimativa do estudo ----
ok(not [d for d in rf.dias_jornada_set(date(2025, 1, 1), date(2025, 1, 31), "seg-sex") if not rf.em_recesso(d)]
   and rf.em_recesso(date(2025, 7, 20)) and rf.em_recesso(date(2025, 12, 22)) and not rf.em_recesso(date(2025, 7, 10)), "146: recesso escolar")

if falhas:
    print("FALHOU (quesitos 16/10 - remição):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: quesitos 16/10 - remição (7.14: outros autos, exame, liberdade provisória, saída do presídio, art. 127, remição ficta, afastamento, "
      "recomeço da contagem, 1/3 do atestado, sem período, recesso)")
