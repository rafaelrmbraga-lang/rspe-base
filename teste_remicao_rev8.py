"""Teste de regressão da conferência da remição (rev8, 3ª rodada): a remição sem atestado e o atestado sem período só cobrem o
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


def est(C):
    return sum(x["est"] for x in C["sem_atestado"] if not x.get("duvida"))


INI = "TRABALHO: Iniciou atividade laboral, no setor de trabalho %s, conforme documento 1."
FIM = "TRABALHO: Deixa de trabalhar, no setor de trabalho %s, conforme documento 1, motivo: N/C."

# ---- A1: remição pequena sem atestado não cobre anos de trabalho (Rosemir: 3 dias "cobriam" 2018-2021) ----
f = F([("31.08.2018", INI % "FAXINA"), ("11.01.2021", FIM % "FAXINA")])
C = rrm.conciliar(R(rem(3, "16/10/2023", "23/12/2022")), f, HOJE)
ok(est(C) > 600, "A1: remição de 3 dias escondeu o trabalho: %s dias estimados" % est(C))
nr = [a for a in C["atestados"] if a["origem"] == "rspe"]
ok(nr and sum(len(rrm._dias_set(s["ini"], s["fim"])) for s in nr[0]["segs"]) <= int(9 * 1.3) + 10, "A1: cobertura da remição de 3 dias além de 3 x 3")
# remição do tamanho do trabalho continua cobrindo o período inteiro
C = rrm.conciliar(R(rem(215, "16/10/2023", "23/12/2022")), f, HOJE)
ok(est(C) < 30, "A1: remição que cabe no trabalho deixou estimativa: %s" % est(C))
# atestado em lote (sem período) também cobre só os dias que atesta
f2 = F([("02.01.2020", INI % "COZINHA"), ("10.03.2023", "Emitido atestado de trabalho nº 050/2023 setor de COZINHA com 90 dias trabalhados e 30 dias remidos."),
        ("15.03.2023", FIM % "COZINHA")])
C = rrm.conciliar(R(), f2, HOJE)
ok(est(C) > 500, "A1: atestado em lote de 90 dias cobriu 3 anos: %s" % est(C))
# remição com o padrão da leitura (múltipla de 4, sem número de atestado) não cobre trabalho (Camila: 4, 8 e 12 dias)
C = rrm.conciliar(R(rem(12, "25/09/2024"), rem(8, "01/04/2025")), F([("04.01.2022", INI % "CANTINA"), ("22.03.2025", FIM % "CANTINA")]), HOJE)
ok(not [a for a in C["atestados"] if a["origem"] == "rspe"] and any("padrão da leitura" in al["texto"] for al in C["alertas"]),
   "A1: remição de leitura atribuída ao trabalho")

# ---- A2: a planilha usa o mesmo valor do relatório (parte fora do período já remido; teto) ----
f = F([("16.08.2018", "Nesta data foi peticionado o Atestado de Trabalho n 110/2018, na função Faxina (10/07/2017 a 16/08/2018), sendo 346 dias trabalhados e 115 remidos."),
       ("17.01.2026", "Peticionado o Atestado de Trabalho n 005/2026, no Sistema SEEU, função Faxina (17/08/2018 a 29/07/2019) 297 dias trabalhados e 99 remidos; "
                      "função Piva Lingerie (21/05/2023 a 18/01/2025) totalizando 435 dias trabalhados e 145 remidos.")])
r = dict(R(rem(115, "16/08/2018"), rem(87, "19/07/2019")), processo_execucao="0000001-00.2020.8.12.0001", nome="TESTE")
m = dict(rf.comparativo(r, f, HOJE), ficha_tem=True, nome="TESTE", proc="0000001-00.2020.8.12.0001", ficha=f)
L = [x for x in rrel.linhas_conferencia([m]) if x["Atestado nº"] == "005/2026"]
ok(L and L[0]["Dias a remir"] == 157, "A2: planilha com os remidos do atestado, não a parte pendente: %s" % [x["Dias a remir"] for x in L])

# ---- A3: dois atestados sem período no mesmo intervalo dividem a capacidade; a emissão do 1º não é o fim do que ele cobriu (Baltazar) ----
f = F([("29.01.2019", INI % "CANTINA"), ("04.05.2019", FIM % "CANTINA"), ("04.05.2019", INI % "MANUTENCAO"),
       ("20.08.2019", "Emitido ATP Nº 057/2019; MANUTENCAO; TEMPO DE TRABALHO COMPUTADO NO PERÍODO: 132 DIAS TRABALHADOS; TEMPO DE REMIÇÃO: 44 DIAS REMIDOS"),
       ("03.10.2019", "Emitido ATP Nº 088/2019; MANUTENCAO; TEMPO DE TRABALHO COMPUTADO NO PERÍODO: 81 DIAS TRABALHADOS; TEMPO DE REMIÇÃO: 27 DIAS REMIDOS"),
       ("03.10.2019", FIM % "MANUTENCAO")])
C = rrm.conciliar(R(rem(44, "04/09/2019")), f, HOJE)
a = next(a for a in C["atestados"] if a["numero"] == "088/2019")
ok(a["status"] == "NAO_LANCADO" and a.get("teto") is None, "A3: teto indevido no 088/2019: %s" % a.get("teto"))

# ---- A4: "o atestado nº 022 deverá ser substituído pelo nº 042" (em "Observação"): fica o 042 ----
f = F([("13.03.2025", "Nesta data foi emitido o ATESTADO DE TRABALHO PRISIONAL Nº 022/2025/CTAL, referente ao trabalho realizado pelo referido Preso no Setor de "
                      "BARBEARIA, pelo período de18/08/2023 a 04/10/2025, perfazendo um total de 41 (quarenta e um) dias trabalhados e 13 (treze) dias remidos."),
       ("13.03.2025", "OBSERVAÇÃO: TORNAR SEM EFEITO O ATESTADO DE TRABALHO PRISIONAL Nº 022/2025/CTAL."),
       ("16.04.2025", "Observação: no item do dia 13/03/2025, o ATESTADO DE TRABALHO PRISIONAL Nº 022/2025/CTAL deverá ser substituído pelo ATESTADO DE "
                      "TRABALHO PRISIONAL Nº 042/2025/CTAL, referente ao trabalho realizado pelo referido Preso no Setor de BARBEARIA, pelo período de18/08/2023 a "
                      "04/10/2023, perfazendo um total de 41 (quarenta e um) dias trabalhados e 13 (treze) dias remidos.")])
a = rrm.atestados(f["eventos"])
ok([(x["numero"], x["rem"]) for x in a] == [("042/2025", 13.0)], "A4: substituição: %s" % [(x["numero"], x["rem"]) for x in a])

# ---- A5: atestado só com o período casa pela referência no fim do período, mesmo registrado depois da decisão (Julio) ----
f = F([("23.10.2025", "Nesta data foi emitido o ATESTADO DE TRABALHO PRISIONAL Nº 071/2025 - DE 18/02/2025 - 17/09/2025")])
C = rrm.conciliar(R(rem(48, "02/10/2025", "17/09/2025")), f, HOJE)
ok(next(a for a in C["atestados"] if a["numero"] == "071/2025")["status"] == "CONCILIADO", "A5: atestado só com período sem par")
# sem par, entra no relatório (sem dias) - a planilha e o PDF contam igual
_L, res = rf.quadro_trabalho(R(), f, HOJE)
it = res["rem_det"]["emitido"]["itens"]
ok(len(it) == 1 and it[0]["dias"] == 0 and "não traz os dias" in it[0]["base"], "A5: atestado sem dias fora do relatório: %s" % it)

# ---- A6: atestado anterior à execução não casa com remição atual (Jeferson Valerio, N.º549/13) ----
f = F([("06.09.2013", "Emitido o atestado de trabalho N.º549/13/CPAG, referente ao período de 14/02/2013 a 08/09/2013, com 105 dias trabalhados e 33 dias remidos")])
C = rrm.conciliar(R(rem(33, "08/09/2024", "29/07/2024"), ini="20/04/2015"), f, HOJE, ini_exec=date(2015, 4, 20))
a = next(a for a in C["atestados"] if a["numero"] == "549")
ok(a["status"] == "ANTERIOR" and not a.get("remicao"), "A6: atestado anterior casado: %s" % a["status"])

# ---- A7: o preenchimento do atestado sem período não alcança vínculo de mais de um ano antes (Jucelino) ----
f = F([("17.02.2022", INI % "SERVICOS GERAIS"), ("23.02.2022", FIM % "SERVICOS GERAIS"),
       ("10.06.2026", INI % "PRENDEBEM"),
       ("21.07.2026", "Emitido atestado de trabalho nº 249/PDIB setor de PRENDEBEM E FAXINA com 90 dias de remição.")])
C = rrm.conciliar(R(), f, HOJE)
a = next(a for a in C["atestados"] if a["numero"].startswith("249"))
ok(all(s["ini"] >= date(2025, 7, 21) for s in a["segs"] if s.get("ini")), "A7: preenchimento alcançou 2022: %s" % [(s["setor"], s["ini"]) for s in a["segs"]])

# ---- A8: primeiro vínculo depois da emissão: nunca "início depois do fim" ----
f = F([("08.12.2021", "Emitido atestado de trabalho nº 100/2021 com 222 dias trabalhados e 74 dias remidos."), ("01.11.2023", INI % "COZINHA")])
C = rrm.conciliar(R(), f, HOJE)
ok(all(not (s.get("ini") and s.get("fim") and s["ini"] > s["fim"]) for a in C["atestados"] for s in a["segs"]), "A8: segmento com início depois do fim")

# ---- A9: concordância na prioridade ----
m = {"nome": "T", "liv_dias": 44, "prog_dias": None, "ext_dias": 40, "liv": "", "fd_rem_det": {"emitido": {"dias": 10}, "sem_atestado": {"dias": 100}, "total": 110},
     "_bruto": {}}
p = rrel.prioridade_remicao(m)
ok("livramento em 44 dias: alcançado" in p[1] and "término em 40 dias: alcançado" in p[1], "A9: concordância: %s" % p[1])
m["fd_rem_det"] = {"emitido": {"dias": 100}, "total": 100}
p = rrel.prioridade_remicao(m)
ok("já o alcançam" in p[1] and "já a alcançam" not in p[1], "A9: 'o alcançam': %s" % p[1])

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

# ---- lacuna sem setor: sem "(entre  e )" ----
f = F([("10.03.2022", "Emitido atestado de trabalho nº 064/2022, período de 01/01/2021 a 31/03/2021 e de 01/09/2021 a 28/02/2022, com 200 dias trabalhados e 66 dias remidos.")])
C = rrm.conciliar(R(), f, HOJE)
ok(not any("(entre  e" in al["texto"] or "e )" in al["texto"] for al in C["alertas"]), "lacuna com setores vazios")

# ---- status da aba Ficha: leitura exata acende; estudo estimado = amarelo; linha zerada pela conciliação não fica vermelha ----
fl = dict(F([("10.01.2026", "Peticionado relatórios de leitura referentes aos meses 01, 02 e 03 de 2025")]), leituras=[{"data": "10.01.2026", "meses": ["01/2025", "02/2025", "03/2025"], "obras": 3}])
o = rf.comparativo(R(), fl, HOJE)
ok(o["fd_cor"] == "vermelho" and "leitura" in o["fd_sit_det"].lower(), "status com leitura exata: %s %s" % (o["fd_cor"], o["fd_sit"]))
fe = dict(F([]), estudos=[{"curso": "EJA", "inicio": "01.02.2026", "fim": "30.06.2026", "turma": ""}])
o = rf.comparativo(R(), fe, HOJE)
ok(o["fd_cor"] == "amarelo", "status com estudo estimado: %s %s" % (o["fd_cor"], o["fd_sit"]))
f = F([("16.08.2018", "Nesta data foi peticionado o Atestado de Trabalho n 110/2018, na função Faxina (10/07/2017 a 16/08/2018), sendo 346 dias trabalhados e 115 remidos."),
       ("17.01.2026", "Peticionado o Atestado de Trabalho n 006/2026, no Sistema SEEU, função Faxina (01/09/2017 a 10/08/2018) 290 dias trabalhados e 96 remidos.")])
o = rf.comparativo(R(rem(115, "16/08/2018")), f, HOJE)
lz = [L for L in o["fd_linhas"] if "006/2026" in L["at"]]
ok(lz and lz[0]["cor"] == "cinza" and o["fd_cor"] != "vermelho", "linha zerada: %s %s" % ([L["cor"] for L in lz], o["fd_cor"]))

# ---- quadro 2.5: as parcelas fecham o total (atestados + diferença, trabalho sem atestado, estudo + leitura) ----
D = {"total": 0}
for k, _r, _p in rf.ORIGENS_REMICAO:
    D[k] = {"dias": 0, "itens": [], "por_un": {}}
D["lacunas"] = {"dias": 0, "itens": [], "por_un": {}}
for k, v in (("emitido", 10.5), ("divergencia", 3), ("sem_atestado", 20), ("estudo", 4), ("leitura", 8)):
    D[k] = {"dias": v, "itens": [{"dias": v}], "por_un": {"U": v}}
D["total"] = 45.5
O = rrel.remicao_por_origem([{"ficha_tem": True, "fd_rem_det": D}])
ok(O["r"]["nao_lancado"] + O["r"]["emitido"] + O["r"]["divergencia"] + O["r"]["sem_atestado"] + O["r"]["estudo"] + O["r"]["leitura"] == O["r_total"]
   and O["ass_exatos"] == 1, "quadro 2.5 não fecha: %s" % O["r"])

# ---- feedback do usuário: troca de setor logo depois do atestado (Rodarte) e fim do vínculo explicado (Dilson) ----
f = F([("07.12.2022", INI % "PRENDEBEM"),
       ("23.03.2025", "Peticionado Atestado de Trabalho n 39/2025, no Sistema SEEU, Autos 1, função Prendedor Prendebem (07/12/2022 a 12/03/2025) sendo 591 dias trabalhados e 197 remidos."),
       ("27.03.2025", INI % "ARTESANATO"), ("27.03.2025", FIM % "PRENDEBEM")])
C = rrm.conciliar(R(ini="01/06/2022"), f, HOJE)
pend = [p for p in C["pendencias"] if "Prendebem" in p["texto"] or "PRENDEBEM" in p["texto"].upper()]
ok(pend and all(p["status"] == "A_CONFERIR" for p in pend if "13/03/2025" in p["texto"]),
   "troca de setor: os dias entre o fim do atestado e a baixa administrativa deviam ficar a conferir: %s" % [p["texto"][:90] for p in pend])
f = F([("13.11.2025", INI % "PRENDEDORES DE ROUPA"),
       ("30.06.2026", "EMITIDO ATP Nº 135/2026; PRENDEDORES DE ROUPA: DATA 13/11/2025; DATA FINAL: 30/06/2026; TEMPO DE TRABALHO COMPUTADO NO PERÍODO: 197 DIAS TRABALHADOS; TEMPO DE REMIÇÃO: 65,66 DIAS REMIDOS."),
       ("05.08.2026", "TRABALHO: Deixa de trabalhar, no setor de trabalho PRENDEDORES DE ROUPA, conforme documento CI, motivo: Saída da Unidade Penal.")])
C = rrm.conciliar(R(ini="12/08/2025"), f, HOJE)
pend = [p for p in C["pendencias"] if p["status"] == "SEM_ATESTADO"]
ok(pend and "fim em 05/08/2026" in pend[0]["texto"] and "Saída da Unidade Penal" in pend[0]["texto"],
   "fim do vínculo sem a origem na ficha: %s" % [p["texto"] for p in pend])
nl = [p for p in C["pendencias"] if p["status"] == "NAO_LANCADO"]
ok(nl and "se juntado, requerer a apreciação" in nl[0]["acao"], "atestado não lançado sem a orientação de conferir a juntada")

if falhas:
    print("FALHOU (remição rev8):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: remição rev8 (cobertura limitada ao remido, leitura, planilha = relatório, teto, substituição, atestado só com período, anterior à "
      "execução, preenchimento, início x fim, concordância, leitura da ficha, lacuna, status da aba Ficha, quadro 2.5)")
