"""Teste de regressão da remição (rev9: 3ª revisão da remição e revisão do código). Casos dos revisores, em forma sintética:
ficha antiga (transferência, entrada em outra unidade, evasão, livramento e prisão preventiva encerram o vínculo; a fuga do RSPE não é
retomada); baixa com outra grafia ("Artsanato", "o de cozinha", "Crina"); registro duplicado no mesmo dia; mudança de cela "deixa de
trabalhar"; "retorna a exercer"; transição provada por atestado (mesmo dia); troca de setor só depois de período explícito, até ~1 mês
e nova função até 3 dias; origem de toda data final, com o termo certo; lançamento posterior à impressão; divergência explicada pelo
período anterior à execução; fundamentação com o valor da remição detalhada e sem "(0 dias trabalhados)"; resíduo sem contar a
remição conjunta duas vezes; peticionamento pelo número e ano; Auditoria com a providência da pendência; remanejamento no dia do
início; "trabalho em curso" pelos vínculos; LEP, art. 128; dias por extenso entre parênteses; atestado sem dias nem período; leitura
remida em parte; relatório "Sem remição no RSPE" e execução extinta. Rodar: python teste_remicao_rev9.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf
import rspe_remicao as rrm
import rspe_relatorio as rrel

falhas = []
HOJE = date(2026, 10, 8)


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def F(eventos, impressao="06/10/2026"):
    return {"data_impressao": impressao, "eventos": [{"data": d, "texto": t} for d, t in eventos]}


def rem(dias, dec, ref=None):
    return {"tipo": "REMIÇÃO", "complemento": "%s Dia(s) Remido(s)" % dias, "data_decisao": dec, "data_referencia": ref or dec, "situacao": "CONCEDIDO"}


def R(*incs, ini="01/01/2005", eventos=()):
    return {"_eventos": [{"data": ini, "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}] + list(eventos), "_incidentes": list(incs)}


INI = "TRABALHO: Iniciou atividade laboral, no setor de trabalho %s, conforme documento CI 1."
FIM = "TRABALHO: Deixa de trabalhar, no setor de trabalho %s, conforme documento CI 1, motivo: %s."


def sem(C):
    return [(x["setor"], x["ini"], x["fim"]) for x in C["sem_atestado"] if not x.get("duvida")]


def duv(C):
    return [(x["setor"], x["ini"], x["fim"]) for x in C["sem_atestado"] if x.get("duvida")]


# ---- A1: ficha antiga - transferência, entrada em outra unidade, evasão, livramento, prisão preventiva ----
for txt in ("TRANSFERIDO PARA O PTRAN CONFORME OF 12/2008", "ENTRADA NO EPJFC PROCEDENTE DO PTRAN, CONF. OF 1/13",
            "DEU ENTRADA NO IPCG, PROCEDENTE DA DERF", "NESTA DATA EVADIU-SE DA UNIDADE", "BENEFICIADO COM LIVRAMENTO CONDICIONAL CONFORME ALVARA",
            "ENTRADA NO EPJFC, POR FORÇA DE PRISÃO PREVENTIVA"):
    C = rrm.conciliar(R(), F([("25.09.2008", "INICIOU ATIVIDADES LABORAIS NO SETOR DE ARTESANATO CONFORME CI 1"), ("31.12.2008", txt)]), HOJE)
    vs = C["vinculos"]
    ok(len(vs) == 1 and vs[0]["fim"] == date(2008, 12, 31), "A1: %r não encerrou o vínculo: %s" % (txt, [(v["ini"], v["fim"]) for v in vs]))
# tentativa de fuga não encerra
C = rrm.conciliar(R(), F([("16.07.2012", "INICIOU ATIVIDADES LABORAIS NO SETOR DE LAVOURA CONFORME CI 1"),
                          ("19.02.2013", "FOI FLAGRADO COM SUBSTÂNCIA E TENTATIVA DE FUGA DA UNIDADE")]), HOJE)
ok(C["vinculos"][0]["fim"] is None, "A1: tentativa de fuga encerrou o vínculo")
# fuga do RSPE no meio do vínculo: a vaga não é retomada depois da recaptura
r = R(eventos=[{"data": "03/04/2023", "tipo": "INTERRUPÇÃO", "motivo": "FUGA"},
               {"data": "03/07/2023", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "RECAPTURA"}], ini="02/01/2022")
C = rrm.conciliar(r, F([("02.01.2023", INI % "CORTE DE CABELO")]), date(2023, 12, 30))
ok(sem(C) == [("Corte de Cabelo", date(2023, 1, 2), date(2023, 4, 2))], "A1: fuga do RSPE retomada: %s" % sem(C))
p = [x for x in C["pendencias"] if x["status"] == "SEM_ATESTADO"]
ok(p and "véspera de fuga registrada no RSPE em 03/04/2023" in p[0]["texto"], "A6: fim pela fuga do RSPE sem origem: %s" % [x["texto"] for x in p])

# ---- A2: baixa com outra grafia ----
C = rrm.conciliar(R(), F([("05.04.2016", "passa a Trabalhar no setor de Artsanato nesta UP/CT"),
                          ("06.04.2016", "deixa de trabalhar no Setor de Artesanato por demonstrar falta de interesse")]), HOJE)
ok([(v["ini"], v["fim"]) for v in C["vinculos"]] == [(date(2016, 4, 5), date(2016, 4, 6))], "A2: 'Artsanato' x 'Artesanato': %s" % [(v["setor"], v["fim"]) for v in C["vinculos"]])
C = rrm.conciliar(R(), F([("11.02.2019", "REMANEJADO DO SETOR DE FAXINA PARA O DE COZINHA, CONFORME CI 1"),
                          ("09.04.2019", FIM % ("COZINHA", "OPERACIONAL"))]), HOJE)
vz = [v for v in C["vinculos"] if "ozinha" in v["setor"]]
ok(vz and vz[0]["setor"] == "Cozinha" and vz[0]["fim"] == date(2019, 4, 9), "A2: 'o de cozinha': %s" % [(v["setor"], v["fim"]) for v in C["vinculos"]])
C = rrm.conciliar(R(), F([("01.03.2017", INI % "MANUFATURA DE CRINA DO BRASIL"), ("18.10.2017", "deixa de Trabalhar no Setor de CRINA, encerramento da empresa")]), HOJE)
ok(C["vinculos"][0]["fim"] == date(2017, 10, 18), "A2: 'Setor de CRINA' x 'Manufatura de Crina': %s" % C["vinculos"][0]["fim"])

# ---- A3: registro duplicado no mesmo dia ----
C = rrm.conciliar(R(), F([("19.02.2026", INI % "IPCG ARTESANATO"), ("19.02.2026", "INICIA ATIVIDADE LABORAL NO SETOR DE ARTESANATO, CONFORME CI 2"),
                          ("18.03.2026", FIM % ("IPCG ARTESANATO", "ISOLADO EM CELA DISCIPLINAR")),
                          ("21.08.2026", "Saída da Unidade Penal: IPCG, Destino: PDIB, Motivo: Transferência de Presidio, Conforme CI 3.")]), HOJE)
ok(len(C["vinculos"]) == 1 and C["vinculos"][0]["fim"] == date(2026, 3, 18), "A3: mesmo setor aberto duas vezes no dia: %s" % [(v["setor"], v["fim"]) for v in C["vinculos"]])
C = rrm.conciliar(R(), F([("05.12.2019", INI % "AJUDANTE"), ("05.12.2019", INI % "PRENDEBEM"),
                          ("11.04.2021", FIM % ("PRENDEBEM", "encaminhado para a Disciplinar")),
                          ("13.04.2023", FIM % ("AJUDANTE", "Saida do Presídio"))]), HOJE)
aj = [v for v in C["vinculos"] if v["setor"] == "Ajudante"][0]
ok(aj.get("duvida_desde") == date(2021, 4, 12) and "provável registro duplicado" in aj["duvida"], "A3: duplicado encerrado só pela saída: %s" % aj.get("duvida"))

# ---- A4: mudança de cela "deixa de trabalhar"; "retorna a exercer"; novo início com outro setor no meio; transição no mesmo dia ----
C = rrm.conciliar(R(), F([("12.10.2023", INI % "CANTINA"),
                          ("02.05.2024", "Mudança de Cela: IPCG, Motivo: DEIXA DE TRABALHAR NA CANTINA, Origem: 1, Destino: 2, Conforme Documento: CI 1.")]), HOJE)
ok(C["vinculos"][0]["fim"] == date(2024, 5, 2), "A4: mudança de cela 'deixa de trabalhar na cantina': %s" % C["vinculos"][0]["fim"])
C = rrm.conciliar(R(), F([("02.01.2014", INI % "ARTESANATO"), ("13.10.2014", "CONSELHO DISCIPLINAR: ISOLADO PREVENTIVAMENTE EM CELA DISCIPLINAR, POR 10 DIAS"),
                          ("11.11.2015", "retorna a exercer atividade laboral no setor de Artesanato, conforme CI 9")]), HOJE)
v0 = C["vinculos"][0]
ok(v0.get("duvida_desde") == date(2014, 10, 13), "A4: 'retorna a exercer' sem dúvida desde o isolamento: %s" % v0.get("duvida_desde"))
C = rrm.conciliar(R(), F([("12.10.2023", INI % "CANTINA"), ("07.06.2024", INI % "ARTESANATO"), ("30.09.2024", FIM % ("ARTESANATO", "IMPRODUTIVIDADE")),
                          ("09.10.2025", INI % "CANTINA")]), HOJE)
v0 = C["vinculos"][0]
ok(v0.get("duvida_desde") == date(2024, 6, 7), "A4: novo início no mesmo setor com outro setor no meio: %s" % v0.get("duvida"))
C = rrm.conciliar(R(), F([("11.02.2019", INI % "CELA LIVRE PV 1"),
                          ("21.03.2019", "EMITIDO ATESTADO DE TRABALHO Nº 232/2019, NO SETOR DE CELA LIVRE NO PERÍODO DE 11/02/2019 A 21/03/2019 CALCULADOS 34 DIAS TRABALHADOS E 11 DIAS REMIDOS"),
                          ("21.03.2019", INI % "ARTESANATO PV 1"), ("06.08.2019", FIM % ("ARTESANATO PV 1", "PADIC")),
                          ("08.08.2019", "EMITIDO ATESTADO DE TRABALHO Nº 503/2019, NO SETOR DE ARTESANATO NO PERÍODO DE 21/03/2019 A 06/08/2019 CALCULADOS 99 DIAS TRABALHADOS E 33 DIAS REMIDOS"),
                          ("27.03.2020", FIM % ("CELA LIVRE PV 1", "Saida do Presídio"))]), HOJE)
ok(not [x for x in sem(C) if "Cela" in x[0]], "A4: transição provada pelos atestados (mesmo dia): %s" % sem(C))

# ---- A5: troca de setor - só com período explícito, até ~1 mês, nova função até 3 dias ----
def troca(emissao_txt, baixa, novo):
    return F([("01.06.2025", INI % "PRENDEBEM"), ("15.03.2026", emissao_txt), (baixa, FIM % ("PRENDEBEM", "troca de função")), (novo, INI % "POLIGONAL")])


AT = "EMITIDO ATP Nº 022/2026; PRENDEBEM; DATA INICIAL: 01/06/2025; DATA FINAL: 23/02/2026; TEMPO DE TRABALHO COMPUTADO NO PERÍODO: 210 DIAS TRABALHADOS; TEMPO DE REMIÇÃO: 70 DIAS REMIDOS."
C = rrm.conciliar(R(), troca(AT, "15.03.2026", "17.03.2026"), HOJE)  # 19 dias, nova função 2 dias depois (Geraldo)
ok(any(x[0].startswith("Prendebem") for x in duv(C)) and not any(x[0].startswith("Prendebem") for x in sem(C)), "A5: troca 2 dias depois: %s / %s" % (sem(C), duv(C)))
C = rrm.conciliar(R(), troca(AT, "24.03.2026", "24.03.2026"), HOJE)  # 28 dias
ok(any(x[0].startswith("Prendebem") for x in duv(C)), "A5: troca com 28 dias: %s" % sem(C))
LOTE = "FOI EMITIDO ATESTADO DE TRABALHO Nº 141/PDIB, NO SETOR PRENDEBEM COM 70 DIAS REMIDOS"
C = rrm.conciliar(R(), F([("01.06.2025", INI % "PRENDEBEM"), ("06.07.2026", LOTE), ("20.07.2026", FIM % ("PRENDEBEM", "troca de função")),
                          ("20.07.2026", INI % "POLIGONAL")]), HOJE)  # atestado sem período: a "data final" é a emissão inferida
ok(any(x[0].startswith("Prendebem") and x[1] == date(2026, 7, 7) for x in sem(C)), "A5: atestado sem período não deveria ir a conferir: %s / %s" % (sem(C), duv(C)))

# ---- A6/A7: origem de toda data final, com o termo certo ----
for txt, termo in (("Saída da Unidade Penal: IPCG, Destino: , Motivo: Evasão, Conforme CI 1.", "saída da unidade - motivo: Evasão"),
                   ("DESLIGADO DO SETOR DE MARCENARIA POR FALTA DE INTERESSE", "desligado"),
                   ("Mudança de Cela: IPCG, Motivo: DEIXA DE TRABALHAR NA MARCENARIA, Origem: 1, Destino: 2", "mudança de cela"),
                   ("TRANSFERIDO PARA O PTRAN", "transferência")):
    C = rrm.conciliar(R(), F([("01.02.2022", INI % "MARCENARIA"), ("30.03.2022", txt)]), HOJE)
    p = [x["texto"] for x in C["pendencias"] if x["status"] == "SEM_ATESTADO"]
    ok(p and ("ficha registra " + termo) in p[0], "A7: termo do fim (%s): %s" % (termo, p))
C = rrm.conciliar(R(rem(9, "12/03/2026", "21/04/2024")), F([("04/10/2022", INI % "ARTESANATO"), ("07.06.2024", FIM % ("ARTESANATO", "N/C"))]), HOJE)
p = [x["texto"] for x in C["pendencias"] if x["status"] == "SEM_ATESTADO"]
ok(p and "véspera do período coberto pela remição de 9 dias" in p[0], "A6: fim na véspera de uma cobertura sem origem: %s" % p)

# ---- A8: lançamento posterior à impressão ----
C = rrm.conciliar(R(), F([("04.08.2026", INI % "PAIVA LINGERIE"), ("23.12.2026", FIM % ("PAIVA LINGERIE", "N/C"))], impressao="05/10/2026"), HOJE)
ok(C["vinculos"][0]["fim"] is None and any("posterior à impressão" in a["texto"] for a in C["alertas"]), "A8: baixa com data futura aceita")

# ---- A9: divergência explicada pelo período anterior à execução ----
f = F([("10.11.2022", "Peticionado o Atestado de Trabalho n 399/2022, função Artesanato (01/04/2011 a 29/01/2012) e (02/10/2018 a 08/11/2022) totalizando 792 dias trabalhados e 264 remidos.")])
C = rrm.conciliar(R(rem(190, "24/11/2022", "08/11/2022")), f, HOJE, ini_exec=date(2014, 4, 28))
ok(not [x for x in C["pendencias"] if x["status"] == "DIVERGENCIA"], "A9: divergência pelo período anterior à execução: %s" % [x["texto"] for x in C["pendencias"]])

# ---- código A1/A2/A10: fundamentação com o valor da remição detalhada, sem "(0 dias trabalhados)", LEP art. 128 ----
f = F([("16.08.2018", "Nesta data foi peticionado o Atestado de Trabalho n 110/2018, na função Faxina (10/07/2017 a 16/08/2018), sendo 346 dias trabalhados e 115 remidos."),
       ("17.01.2026", "Peticionado o Atestado de Trabalho n 006/2026, no Sistema SEEU, função Faxina (01/09/2017 a 10/08/2018) 290 dias trabalhados e 96 remidos."),
       ("20.02.2026", "FOI EMITIDO ATESTADO DE TRABALHO Nº 024/2026 COM 29 DIAS REMIDOS")])
o = rf.comparativo(R(rem(115, "16/08/2018")), f, HOJE)
fund = o.get("fd_fund") or ""
ok("006/2026" not in fund, "código A1: atestado zerado no pedido: %s" % fund[:300])
ok("(0 dias trabalhados)" not in fund and "declara" in fund, "código A2: '(0 dias trabalhados)': %s" % fund[:300])
ok("arts. 126, 128 e 129" not in fund and "art. 128" in fund, "código A10: citação do art. 129")

# ---- código A3: resíduo - remição conjunta uma vez só ----
f = F([("10.01.2016", "Peticionado Atestado de Trabalho n 013/2016, função A (01/01/2015 a 30/06/2015) 150 dias trabalhados e 50 remidos."),
       ("12.01.2016", "Peticionado Atestado de Trabalho n 014/2016, função A (01/07/2015 a 31/12/2015) 345 dias trabalhados e 81 remidos.")])
C = rrm.conciliar(R(rem(131, "20/02/2016")), f, HOJE)
ok(C["residuo"] >= 30, "código A3: resíduo com a remição conjunta somada duas vezes: %s" % C["residuo"])

# ---- código A4: peticionamento pelo número e ano ----
f = F([("10.01.2024", "FOI EMITIDO ATESTADO DE TRABALHO Nº 018/2024, PERÍODO DE 01/06/2023 A 31/12/2023, 150 DIAS TRABALHADOS E 50 DIAS REMIDOS"),
       ("10.01.2025", "FOI EMITIDO ATESTADO DE TRABALHO Nº 018/2025, PERÍODO DE 01/06/2024 A 31/12/2024, 150 DIAS TRABALHADOS E 50 DIAS REMIDOS"),
       ("15.01.2025", "PETICIONADO O ATESTADO Nº 018/2025 NO SEEU")])
ats = {a["numero"]: a for a in rrm.atestados(f["eventos"])}
ok(ats["018/2025"]["peticionado"] == "15/01/2025" and not ats["018/2024"]["peticionado"], "código A4: %s" % {k: a["peticionado"] for k, a in ats.items()})

# ---- código A6: item da Auditoria com a providência da pendência ----
its = rf._itens_conciliacao({"pendencias": [{"status": "NAO_LANCADO", "texto": "Atestado 295/2025 de 01/01/2026 (43 remidos)", "acao": "conferir na decisão anterior os dias já remidos (nada a requerer)", "cor": "cinza"}], "alertas": []})
ok(its and its[0]["nivel"] == "verificar" and "nada a requerer" in its[0]["detalhe"], "código A6: %s" % its)

# ---- código A8: remanejamento no dia do início não cria vínculo com fim antes do início ----
vs, _ = rrm.vinculos(F([("30.05.2022", INI % "CARANDA MOUROES"), ("30.05.2022", "REMANEJADO PARA A EMPRESA CARANDA MOUROES, CONFORME CI 1")])["eventos"], HOJE)
ok(all(v["fim"] is None or v["fim"] >= v["ini"] for v in vs), "código A8: fim antes do início: %s" % [(v["ini"], v["fim"]) for v in vs])

# ---- código A9: "trabalho em curso" pelos vínculos da conciliação ----
f = F([("11.06.2019", INI % "ARTESANATO"), ("20.08.2019", "DESLIGADO DO SETOR DE ARTESANATO, CONFORME CI 2")])
f["trabalho"] = [{"inicio": "11.06.2019", "fim": "", "setor": "ARTESANATO"}]
o = rf.comparativo(R(), f, HOJE)
ok(o["fd_trab"] == "sem trabalho em curso", "código A9: trabalho em curso pelo leitor antigo: %s" % o["fd_trab"])

# ---- sistema A14: dias por extenso; atestado sem dias nem período ----
a = rrm.atestados(F([("25.03.2024", "Nesta data foi emitido ATESTADO DE TRABALHO PRISIONAL Nº 24/2024, correspondente ao período de 14/08/2023 a 22/12/2023 "
                                    "Totalizando (oitenta e seis) dias trabalhados e 29 (vinte nove ) dias REMIDOS.")])["eventos"])
ok(a and a[0]["trab"] == 86 and a[0]["rem"] == 29, "sistema A14: dias trabalhados por extenso: %s" % [(x["trab"], x["rem"]) for x in a])
a = rrm.atestados(F([("06.05.2019", "Conforme Of. Nº 287/2019, foi encaminhado Atestado de trabalho prisional nº 004/2019 do reeducando.")])["eventos"])
ok(a and a[0]["rem"] is None and a[0].get("sem_cobertura"), "sistema A14: atestado sem dias nem período não gravado: %s" % a)

# ---- sistema A3: leitura remida em parte fica a conferir (amarela), não "sem remição" ----
fl = dict(F([]), leituras=[{"data": "10.01.2026", "meses": ["01/2025", "02/2025", "03/2025"], "obras": 3}])
o = rf.comparativo(R(rem(8, "20/02/2026")), fl, HOJE)
ok(o["fd_cor"] == "amarelo" and "Conferir remição" in o["fd_sit"] and any(L["emp"].startswith("Leitura") and L["cor"] == "amarelo" for L in o["fd_linhas"]),
   "sistema A3: leitura remida em parte: %s %s" % (o["fd_cor"], o["fd_sit"]))
o = rf.comparativo(R(), fl, HOJE)
ok(o["fd_cor"] == "vermelho" and any(L["emp"].startswith("Leitura") and L["cor"] == "vermelho" for L in o["fd_linhas"]), "sistema A3: leitura sem remição sem linha vermelha")

# ---- relatório: "Sem remição no RSPE"; execução extinta marcada ----
ok("[pena EXTINTA no RSPE]" in rrel.nome_rel({"nome": "X", "estado_exec": "extinta"}), "sistema A11: execução extinta sem marca")
import inspect
src = inspect.getsource(rrel.relatorio_remicao)
ok("Não está no processo" not in src and "fora do processo" not in src, "código A5: rótulo 'Não está no processo'")

if falhas:
    print("FALHOU (remição rev9):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: remição rev9 (ficha antiga e fuga do RSPE, grafia da baixa, registro duplicado, mudança de cela, retorno, transição, troca de setor, "
      "origem e termo da data final, data futura, anterior à execução, fundamentação, resíduo, peticionamento, Auditoria, remanejamento, "
      "trabalho em curso, extenso, atestado sem dias, leitura parcial, relatório)")
