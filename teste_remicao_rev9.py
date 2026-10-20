"""Teste de regressão da remição (rev9: 3ª revisão da remição e revisão do código; ajustado ao modelo da 7.14 - saíram os itens da conciliação). Casos dos revisores, em forma sintética:
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


# (7.14: a conciliação atestado x remição saiu; os vínculos vêm da leitura - rspe_remicao.vinculos - e o resto do modelo novo)
def V(r, f, hoje):
    return {"vinculos": rrm.vinculos(f["eventos"], hoje, rrm._dt(f.get("data_impressao") or ""))[0]}


# ---- A1: ficha antiga - transferência, entrada em outra unidade, evasão, livramento, prisão preventiva ----
for txt in ("TRANSFERIDO PARA O PTRAN CONFORME OF 12/2008", "ENTRADA NO EPJFC PROCEDENTE DO PTRAN, CONF. OF 1/13",
            "DEU ENTRADA NO IPCG, PROCEDENTE DA DERF", "NESTA DATA EVADIU-SE DA UNIDADE", "BENEFICIADO COM LIVRAMENTO CONDICIONAL CONFORME ALVARA",
            "ENTRADA NO EPJFC, POR FORÇA DE PRISÃO PREVENTIVA"):
    C = V(R(), F([("25.09.2008", "INICIOU ATIVIDADES LABORAIS NO SETOR DE ARTESANATO CONFORME CI 1"), ("31.12.2008", txt)]), HOJE)
    vs = C["vinculos"]
    ok(len(vs) == 1 and vs[0]["fim"] == date(2008, 12, 31), "A1: %r não encerrou o vínculo: %s" % (txt, [(v["ini"], v["fim"]) for v in vs]))
# tentativa de fuga não encerra
C = V(R(), F([("16.07.2012", "INICIOU ATIVIDADES LABORAIS NO SETOR DE LAVOURA CONFORME CI 1"),
                          ("19.02.2013", "FOI FLAGRADO COM SUBSTÂNCIA E TENTATIVA DE FUGA DA UNIDADE")]), HOJE)
ok(C["vinculos"][0]["fim"] is None, "A1: tentativa de fuga encerrou o vínculo")
# ---- A2: baixa com outra grafia ----
C = V(R(), F([("05.04.2016", "passa a Trabalhar no setor de Artsanato nesta UP/CT"),
                          ("06.04.2016", "deixa de trabalhar no Setor de Artesanato por demonstrar falta de interesse")]), HOJE)
ok([(v["ini"], v["fim"]) for v in C["vinculos"]] == [(date(2016, 4, 5), date(2016, 4, 6))], "A2: 'Artsanato' x 'Artesanato': %s" % [(v["setor"], v["fim"]) for v in C["vinculos"]])
C = V(R(), F([("11.02.2019", "REMANEJADO DO SETOR DE FAXINA PARA O DE COZINHA, CONFORME CI 1"),
                          ("09.04.2019", FIM % ("COZINHA", "OPERACIONAL"))]), HOJE)
vz = [v for v in C["vinculos"] if "ozinha" in v["setor"]]
ok(vz and vz[0]["setor"] == "Cozinha" and vz[0]["fim"] == date(2019, 4, 9), "A2: 'o de cozinha': %s" % [(v["setor"], v["fim"]) for v in C["vinculos"]])
C = V(R(), F([("01.03.2017", INI % "MANUFATURA DE CRINA DO BRASIL"), ("18.10.2017", "deixa de Trabalhar no Setor de CRINA, encerramento da empresa")]), HOJE)
ok(C["vinculos"][0]["fim"] == date(2017, 10, 18), "A2: 'Setor de CRINA' x 'Manufatura de Crina': %s" % C["vinculos"][0]["fim"])

# ---- A3: registro duplicado no mesmo dia ----
C = V(R(), F([("19.02.2026", INI % "IPCG ARTESANATO"), ("19.02.2026", "INICIA ATIVIDADE LABORAL NO SETOR DE ARTESANATO, CONFORME CI 2"),
                          ("18.03.2026", FIM % ("IPCG ARTESANATO", "ISOLADO EM CELA DISCIPLINAR")),
                          ("21.08.2026", "Saída da Unidade Penal: IPCG, Destino: PDIB, Motivo: Transferência de Presidio, Conforme CI 3.")]), HOJE)
ok(len(C["vinculos"]) == 1 and C["vinculos"][0]["fim"] == date(2026, 3, 18), "A3: mesmo setor aberto duas vezes no dia: %s" % [(v["setor"], v["fim"]) for v in C["vinculos"]])
C = V(R(), F([("05.12.2019", INI % "AJUDANTE"), ("05.12.2019", INI % "PRENDEBEM"),
                          ("11.04.2021", FIM % ("PRENDEBEM", "encaminhado para a Disciplinar")),
                          ("13.04.2023", FIM % ("AJUDANTE", "Saida do Presídio"))]), HOJE)
aj = [v for v in C["vinculos"] if v["setor"] == "Ajudante"][0]
ok(aj.get("duvida_desde") == date(2021, 4, 12) and "provável registro duplicado" in aj["duvida"], "A3: duplicado encerrado só pela saída: %s" % aj.get("duvida"))

# ---- A4: mudança de cela "deixa de trabalhar"; "retorna a exercer"; novo início com outro setor no meio; transição no mesmo dia ----
C = V(R(), F([("12.10.2023", INI % "CANTINA"),
                          ("02.05.2024", "Mudança de Cela: IPCG, Motivo: DEIXA DE TRABALHAR NA CANTINA, Origem: 1, Destino: 2, Conforme Documento: CI 1.")]), HOJE)
ok(C["vinculos"][0]["fim"] == date(2024, 5, 2), "A4: mudança de cela 'deixa de trabalhar na cantina': %s" % C["vinculos"][0]["fim"])
C = V(R(), F([("02.01.2014", INI % "ARTESANATO"), ("13.10.2014", "CONSELHO DISCIPLINAR: ISOLADO PREVENTIVAMENTE EM CELA DISCIPLINAR, POR 10 DIAS"),
                          ("11.11.2015", "retorna a exercer atividade laboral no setor de Artesanato, conforme CI 9")]), HOJE)
v0 = C["vinculos"][0]
ok(v0.get("duvida_desde") == date(2014, 10, 13), "A4: 'retorna a exercer' sem dúvida desde o isolamento: %s" % v0.get("duvida_desde"))
C = V(R(), F([("12.10.2023", INI % "CANTINA"), ("07.06.2024", INI % "ARTESANATO"), ("30.09.2024", FIM % ("ARTESANATO", "IMPRODUTIVIDADE")),
                          ("09.10.2025", INI % "CANTINA")]), HOJE)
v0 = C["vinculos"][0]
ok(v0.get("duvida_desde") == date(2024, 6, 7), "A4: novo início no mesmo setor com outro setor no meio: %s" % v0.get("duvida"))
# (a transição provada pelos atestados no mesmo dia era inferência da conciliação: saiu)

# ---- A8: lançamento posterior à impressão ----
C = V(R(), F([("04.08.2026", INI % "PAIVA LINGERIE"), ("23.12.2026", FIM % ("PAIVA LINGERIE", "N/C"))], impressao="05/10/2026"), HOJE)
ok(C["vinculos"][0]["fim"] is None, "A8: baixa com data futura aceita")

# ---- código A1/A2/A10: fundamentação com o valor da remição detalhada, sem "(0 dias trabalhados)", LEP art. 128 ----
f = F([("16.08.2018", "Nesta data foi peticionado o Atestado de Trabalho n 110/2018, na função Faxina (10/07/2017 a 16/08/2018), sendo 346 dias trabalhados e 115 remidos."),
       ("17.01.2026", "Peticionado o Atestado de Trabalho n 006/2026, no Sistema SEEU, função Faxina (01/09/2017 a 10/08/2018) 290 dias trabalhados e 96 remidos."),
       # (quesito 136, 16/10/2026: atestado sem período fica fora do total e da fundamentação - o deste caso passa a trazer o período)
       ("20.02.2026", "FOI EMITIDO ATESTADO DE TRABALHO Nº 024/2026, PERÍODO DE 01/09/2025 A 31/12/2025, COM 29 DIAS REMIDOS")])
rf.atualizar(f)
o = rf.comparativo(R(rem(115, "16/08/2018")), f, HOJE)
fund = o.get("fd_fund") or ""
# (7.14: o 006/2026, peticionado depois da última decisão, entra no pedido como fato - o programa não infere que o período já foi remido)
ok("006/2026" in fund and "024/2026" in fund, "código A1: documentos posteriores à última remição no pedido: %s" % fund[:300])
ok("(0 dias trabalhados)" not in fund and "declara" in fund, "código A2: '(0 dias trabalhados)': %s" % fund[:300])
ok("arts. 126, 128 e 129" not in fund and "art. 128" in fund, "código A10: citação do art. 129")

# ---- código A4: peticionamento pelo número e ano ----
f = F([("10.01.2024", "FOI EMITIDO ATESTADO DE TRABALHO Nº 018/2024, PERÍODO DE 01/06/2023 A 31/12/2023, 150 DIAS TRABALHADOS E 50 DIAS REMIDOS"),
       ("10.01.2025", "FOI EMITIDO ATESTADO DE TRABALHO Nº 018/2025, PERÍODO DE 01/06/2024 A 31/12/2024, 150 DIAS TRABALHADOS E 50 DIAS REMIDOS"),
       ("15.01.2025", "PETICIONADO O ATESTADO Nº 018/2025 NO SEEU")])
ats = {a["numero"]: a for a in rrm.atestados(f["eventos"])}
ok(ats["018/2025"]["peticionado"] == "15/01/2025" and not ats["018/2024"]["peticionado"], "código A4: %s" % {k: a["peticionado"] for k, a in ats.items()})

# ---- código A8: remanejamento no dia do início não cria vínculo com fim antes do início ----
vs, _ = rrm.vinculos(F([("30.05.2022", INI % "CARANDA MOUROES"), ("30.05.2022", "REMANEJADO PARA A EMPRESA CARANDA MOUROES, CONFORME CI 1")])["eventos"], HOJE)
ok(all(v["fim"] is None or v["fim"] >= v["ini"] for v in vs), "código A8: fim antes do início: %s" % [(v["ini"], v["fim"]) for v in vs])

# ---- código A9: "trabalho em curso" pela leitura da ficha (o desligamento encerra o vínculo) ----
f = F([("11.06.2019", INI % "ARTESANATO"), ("20.08.2019", "DESLIGADO DO SETOR DE ARTESANATO, CONFORME CI 2")])
rf.atualizar(f)
o = rf.comparativo(R(), f, HOJE)
ok(o["fd_trab"] == "sem trabalho em curso", "código A9: trabalho em curso: %s" % o["fd_trab"])

# ---- sistema A14: dias por extenso; atestado sem dias nem período ----
a = rrm.atestados(F([("25.03.2024", "Nesta data foi emitido ATESTADO DE TRABALHO PRISIONAL Nº 24/2024, correspondente ao período de 14/08/2023 a 22/12/2023 "
                                    "Totalizando (oitenta e seis) dias trabalhados e 29 (vinte nove ) dias REMIDOS.")])["eventos"])
ok(a and a[0]["trab"] == 86 and a[0]["rem"] == 29, "sistema A14: dias trabalhados por extenso: %s" % [(x["trab"], x["rem"]) for x in a])
a = rrm.atestados(F([("06.05.2019", "Conforme Of. Nº 287/2019, foi encaminhado Atestado de trabalho prisional nº 004/2019 do reeducando.")])["eventos"])
ok(a and a[0]["rem"] is None and a[0].get("sem_cobertura"), "sistema A14: atestado sem dias nem período não gravado: %s" % a)

# ---- sistema A3: leitura remida em parte: a diferença (12 x 8) é "verificar remição"; sem remição no RSPE, posterior (a conferir) ----
fl = dict(F([]), leituras=[{"data": "10.01.2026", "meses": ["01/2025", "02/2025", "03/2025"], "obras": 3}])
o = rf.comparativo(R(rem(8, "20/02/2026")), fl, HOJE)
ok(o["fd_cor"] == "amarelo" and "Verificar remição" in o["fd_sit"], "sistema A3: leitura remida em parte: %s %s" % (o["fd_cor"], o["fd_sit"]))
o = rf.comparativo(R(), fl, HOJE)
ok(o["fd_cor"] == "amarelo" and any(L["emp"].startswith("Leitura") and L["cor"] == "amarelo" for L in o["fd_linhas"]), "sistema A3: leitura sem remição: %s" % o["fd_linhas"])

# ---- relatório: "Sem remição no RSPE"; execução extinta marcada ----
ok("[pena EXTINTA no RSPE]" in rrel.nome_rel({"nome": "X", "estado_exec": "extinta"}), "sistema A11: execução extinta sem marca")
import inspect
src = inspect.getsource(rrel.relatorio_remicao)
ok("Não está no processo" not in src and "fora do processo" not in src, "código A5: rótulo 'Não está no processo'")

if falhas:
    print("FALHOU (remição rev9):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: remição rev9 (7.14: vínculos da ficha antiga, grafia da baixa, registro duplicado, mudança de cela, retorno, data futura, "
      "fundamentação, peticionamento, remanejamento, trabalho em curso, extenso, atestado sem dias, leitura parcial, relatório)")
