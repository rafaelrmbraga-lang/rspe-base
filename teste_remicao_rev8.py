"""Teste de regressão da conferência da remição (rev8, 3ª rodada; ajustado ao modelo da 7.14 - sem a conciliação atestado x remição, os itens
de cobertura, teto, preenchimento, prioridade, lacuna e quadro por origem saíram; ficam a leitura e o modelo novo): a remição sem atestado e o atestado sem período só cobrem o
trabalho que remiram (remidos x 3, com folga); remição com o padrão da leitura não cobre trabalho; planilha com o mesmo valor do
relatório; teto do atestado sem período sem usar a emissão do anterior; substituição "pelo nº X"; atestado só com o período casado
pela referência e listado no relatório; atestado anterior à execução; preenchimento limitado no tempo; nunca início depois do fim;
concordância da prioridade; leitura (modelo "PROTOCOLADO", dias por extenso, "ias", "228T 76R", CPF com espaços, filiação colada,
faltas antigas); texto da lacuna; status da aba Ficha coerente com as linhas; quadro 2.5 fechando o total. Rodar: python teste_remicao_rev8.py"""
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


def R(*incs, ini="01/01/2015"):
    return {"_eventos": [{"data": ini, "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}], "_incidentes": list(incs)}


def N_(r, f, **kw):
    rf.atualizar(f)
    return rf.comparativo(r, f, HOJE, **kw)


INI = "TRABALHO: Iniciou atividade laboral, no setor de trabalho %s, conforme documento 1."
FIM = "TRABALHO: Deixa de trabalhar, no setor de trabalho %s, conforme documento 1, motivo: N/C."

# ---- A2: a planilha de conferência traz o documento com os remidos da ficha e a situação factual (posterior à última remição) ----
f = F([("16.08.2018", "Nesta data foi peticionado o Atestado de Trabalho n 110/2018, na função Faxina (10/07/2017 a 16/08/2018), sendo 346 dias trabalhados e 115 remidos."),
       ("17.01.2026", "Peticionado o Atestado de Trabalho n 005/2026, no Sistema SEEU, função Faxina (17/08/2018 a 29/07/2019) 297 dias trabalhados e 99 remidos; "
                      "função Piva Lingerie (21/05/2023 a 18/01/2025) totalizando 435 dias trabalhados e 145 remidos.")])
r = dict(R(rem(115, "16/08/2018"), rem(87, "19/07/2019")), processo_execucao="0000001-00.2020.8.12.0001", nome="TESTE")
m = dict(N_(r, f), ficha_tem=True, nome="TESTE", proc="0000001-00.2020.8.12.0001", ficha=f)
L = [x for x in rrel.linhas_conferencia([m]) if x["Documento / setor"] == "Atestado de trabalho nº 005/2026"]
# (7.14.2) a remição de 87 dias sem documento tem referência dentro do período do 005/2026: pede-se só a diferença
ok(L and L[0]["Remição na ficha"] == 244 and L[0]["Situação"].startswith("Pedir ≈ 157 (244 − 87)") and not any("Dias a remir" in x for x in L),
   "A2: planilha: %s" % L)

# ---- A4: "o atestado nº 022 deverá ser substituído pelo nº 042" (em "Observação"): fica o 042 ----
f = F([("13.03.2025", "Nesta data foi emitido o ATESTADO DE TRABALHO PRISIONAL Nº 022/2025/CTAL, referente ao trabalho realizado pelo referido Preso no Setor de "
                      "BARBEARIA, pelo período de18/08/2023 a 04/10/2025, perfazendo um total de 41 (quarenta e um) dias trabalhados e 13 (treze) dias remidos."),
       ("13.03.2025", "OBSERVAÇÃO: TORNAR SEM EFEITO O ATESTADO DE TRABALHO PRISIONAL Nº 022/2025/CTAL."),
       ("16.04.2025", "Observação: no item do dia 13/03/2025, o ATESTADO DE TRABALHO PRISIONAL Nº 022/2025/CTAL deverá ser substituído pelo ATESTADO DE "
                      "TRABALHO PRISIONAL Nº 042/2025/CTAL, referente ao trabalho realizado pelo referido Preso no Setor de BARBEARIA, pelo período de18/08/2023 a "
                      "04/10/2023, perfazendo um total de 41 (quarenta e um) dias trabalhados e 13 (treze) dias remidos.")])
a = rrm.atestados(f["eventos"])
ok([(x["numero"], x["rem"]) for x in a] == [("042/2025", 13.0)], "A4: substituição: %s" % [(x["numero"], x["rem"]) for x in a])

# ---- A5: atestado só com o período (sem os dias): sem valor na ficha, fora da comparação, ponto a conferir ----
f = F([("23.10.2025", "Nesta data foi emitido o ATESTADO DE TRABALHO PRISIONAL Nº 071/2025 - DE 18/02/2025 - 17/09/2025")])
N = N_(R(rem(48, "02/10/2025", "17/09/2025")), f)["fd_novo"]
ok(N["comp"] == 0 and any(p["tipo"] == "sem_valor" and "071/2025" in p["texto"] for p in N["pontos"]), "A5: atestado sem dias: %s" % N["pontos"])

# ---- A6: atestado anterior à execução fica à parte (fora da comparação) ----
f = F([("06.09.2013", "Emitido o atestado de trabalho N.º549/13/CPAG, referente ao período de 14/02/2013 a 08/09/2013, com 105 dias trabalhados e 33 dias remidos")])
N = N_(R(rem(33, "08/09/2024", "29/07/2024"), ini="20/04/2015"), f)["fd_novo"]
d = N["docs"][0]
ok(d["fora"].startswith("anterior ao início desta execução") and N["comp"] == 0 and d["sit"].startswith("À parte"), "A6: anterior à execução: %s" % d)

# ---- A7: atestado sem período sugerido só para o trabalho do mesmo nome iniciado até 450 dias antes da emissão ----
f = F([("17.02.2022", INI % "SERVICOS GERAIS"), ("23.02.2022", FIM % "SERVICOS GERAIS"),
       ("10.06.2026", INI % "PRENDEBEM"),
       ("21.07.2026", "Emitido atestado de trabalho nº 249/PDIB setor de PRENDEBEM E FAXINA com 90 dias de remição.")])
L = N_(R(), f)["fd_novo"]["trab"]["linhas"]
ok([(x["st"], x["at"]) for x in L] == [("sem", ""), ("provavel", "249/PDIB"), ("sem", "")] and L[1]["fim"] == date(2026, 7, 21),
   "A7: sugestão: %s" % [(x["periodo"], x["st"], x["at"]) for x in L])

# ---- leitura: modelo "PROTOCOLADO ... Data Inicial ... até Data Final ... REMIÇÃO totalizou" (Fabiano), extenso, "ias", "228T 76R" ----
a = rrm.atestados(F([("10.12.2019", "ATESTADO DE TRABALHO PRISIONAL - Nesta data foi PROTOCOLADO o Atestado de Trabalho Prisional n°377/2019 (Autos n° "
                                    "0000866-14.2018.8.12.0019). Data Inicial 08/07/2019 até Data Final 30/09/2019 no SETOR DE OLARIA, no qual consta um total de "
                                    "60 dias trabalhados, visto que o tempo de REMIÇÃO totalizou 20,00 dias. (Ag. Maciel)"),
                     ("18.11.2020", "ATESTADO DE TRABALHO PRISIONAL - Nesta data foi encaminhado via E-mail ao Defensor Público, o Atestado de Trabalho Prisional "
                                    "n°304/2020 (Autos n°0000866-14.2018.8.12.0019). Data Inicial 02/10/2017 até Data Final 16/10/2017 no SETOR DE OLARIA, Data "
                                    "Inicial 17/10/2017 até Data Final 26/08/2018 no SETOR DE COZINHA e Data Inicial 01/10/2020 até Data Final 16/11/2020 no SETOR "
                                    "DE OLARIA, no qual consta um total de 298 dias trabalhados, visto que o tempo de REMIÇÃO totalizou 99,33 dias.")])["eventos"])
ok([(x["numero"], x["trab"], x["rem"], len(x["segs"])) for x in a] == [("377/2019", 60, 20.0, 1), ("304/2020", 298, 99.33, 3)],
   "leitura PROTOCOLADO: %s" % [(x["numero"], x["trab"], x["rem"], len(x["segs"])) for x in a])
for txt, esp in (("Emitido atestado de trabalho n.060/2013, referente a duzentos e setenta e sete dias remidos.", (None, 277.0)),
                 ("TRABALHO, nesta data foi emitido atestado de trabalho nº164/PDIB/AGEPEN/MS setor de PRENDE BEM com 126 ias de remição.", (None, 126.0)),
                 ("ATESTADO TRABALHO 292/24 228T 76R", (228, 76.0))):
    a = rrm.atestados(F([("09.04.2013", txt)])["eventos"])
    ok(len(a) == 1 and (a[0]["trab"], a[0]["rem"]) == esp, "leitura de dias: %s -> %s" % (txt[-40:], [(x["trab"], x["rem"]) for x in a]))
ok(rf.cpf_cabecalho("CPF: 060 395 731-55 RG: 1") == "060.395.731-55" and rf.cpf_cabecalho("CPF: 701 076 621 59\n") == "701.076.621-59"
   and rf.cpf_cabecalho("CPF: 060.395.731-55") == "060.395.731-55", "CPF com espaços")
ok(rf.filiacao_cabecalho("Filiação: MARIA DE ALBUQUERQUE \\ JOSE ALBUQUERQUENº Pront Saúde: PDIB - 52.281\n") == "MARIA DE ALBUQUERQUE \\ JOSE ALBUQUERQUE",
   "filiação colada ao Nº Pront")
fx = rf.atualizar({"eventos": [
    {"data": "16.07.2014", "texto": "Tomou ciencia da decidsão do Conselho Disciplinar nº 31/633001/2012, sendo imputado no cometimento de falta disciplinar de "
                                    "natureza GRAVE, referente ao fato ocorrido em 24/11/2011, conformando o isolamento previamente aplicado."},
    {"data": "12.04.2012", "texto": "TOMOU CIÊNCIA DA DECISÃO DO PROCESSO DISCIPLINAR 31/602.478/11, REFERENTE A FALTA DISCIPLINAR GRAVE COMETIDA EM 08/10/2011, "
                                    "A QUAL SUGERIU ISOLAMENTO EM CELA DISCIPLINAR POR 15 (QUINZE) DIAS."}], "versao_leitura": 0})
ok(sorted(x["data_fato"] for x in fx["faltas"] if x["grave"]) == ["08.10.2011", "24.11.2011"], "faltas de 2011: %s" % fx["faltas"])

# ---- status da aba Ficha: leitura posterior à última remição = amarelo (a conferir nos autos); estudo estimado = amarelo; atestado que
# repete período já remido entra na soma (a diferença indica onde conferir) e não fica vermelho por estar peticionado ----
fl = dict(F([("10.01.2026", "Peticionado relatórios de leitura referentes aos meses 01, 02 e 03 de 2025")]), leituras=[{"data": "10.01.2026", "meses": ["01/2025", "02/2025", "03/2025"], "obras": 3}])
o = rf.comparativo(R(), fl, HOJE)
ok(o["fd_cor"] == "amarelo" and o["fd_novo"]["fatos_dias"] == 12 and "leitura" in o["fd_sit_det"].lower(), "status com leitura: %s %s" % (o["fd_cor"], o["fd_sit"]))
fe = dict(F([]), estudos=[{"curso": "EJA", "inicio": "01.02.2026", "fim": "30.06.2026", "turma": ""}])
o = rf.comparativo(R(), fe, HOJE)
ok(o["fd_cor"] == "amarelo", "status com estudo estimado: %s %s" % (o["fd_cor"], o["fd_sit"]))
f = F([("16.08.2018", "Nesta data foi peticionado o Atestado de Trabalho n 110/2018, na função Faxina (10/07/2017 a 16/08/2018), sendo 346 dias trabalhados e 115 remidos."),
       ("17.01.2026", "Peticionado o Atestado de Trabalho n 006/2026, no Sistema SEEU, função Faxina (01/09/2017 a 10/08/2018) 290 dias trabalhados e 96 remidos.")])
o = N_(R(rem(115, "16/08/2018")), f)
# (7.14.2) o atestado que repete o período de outro já remido não se soma (contido no outro)
d06 = next(d for d in o["fd_novo"]["docs"] if d["num"] == "006/2026")
ok(o["fd_novo"]["dif"] == 0 and d06["sit"].startswith("Contido no atestado nº 110/2018") and o["fd_cor"] != "vermelho",
   "período já remido: %s %s %s" % (o["fd_cor"], o["fd_sit"], d06["sit"]))

if falhas:
    print("FALHOU (remição rev8):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: remição rev8 (7.14: planilha, substituição, atestado só com período, anterior à execução, sugestão, leitura da ficha, status da aba Ficha)")
