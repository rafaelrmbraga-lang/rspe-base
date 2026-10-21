"""Leitura da ficha para a vinculação trabalho x atestado (7.14), com lançamentos sintéticos (sem dados pessoais): trabalho escrito em
texto livre na lista de trabalho (início, fim, remanejamento, "volta a trabalhar", "deixa de trabalhar como X e passa a Y"), saída da
unidade nas fichas antigas e o que não é saída (duplicidade de registros, mudança de cela "aguardando transferência"), lançamento
tornado sem efeito, "desconsiderar a função X", liberação do setor, vínculo simultâneo só quando o outro setor já acabou, nomes de
setor (sem "nesta UP", "CI nº", "sendo", "E"; "Fab." abreviado), sinônimos e palavras próprias no singular.
Rodar: python teste_leitura_714.py"""
import sys
import types

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf  # noqa: E402
import rspe_remicao as rrm  # noqa: E402

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)
    return cond


def ficha(evs):
    return rf.atualizar({"versao_leitura": 0, "eventos": [{"data": d, "texto": t} for d, t in evs]})


def trab(f):
    return [(t["inicio"], t.get("fim") or "", t["setor"]) for t in f["trabalho"]]


INI = "TRABALHO: Iniciou atividade laboral, no setor de trabalho %s, conforme documento CI 1/2024."
FIM = "TRABALHO: Deixa de trabalhar, no setor de trabalho %s, conforme documento CI 2/2024, motivo: %s."
SAIDA = "Saída da Unidade Penal: UNIDADE A, Destino: UNIDADE B, Motivo: %s, Conforme Ofício: 1."

ok(rf.VERSAO_LEITURA >= 14, "VERSAO_LEITURA subiu (releitura das fichas gravadas)")

# ---- trabalho em texto livre ----
f = ficha([("24.12.2025", INI % "BARBEIRO"), ("24.12.2025", FIM % ("AUXILIAR ADMINISTRATIVO", "DESLIGADO")),
           ("24.12.2025", "Liberação do Setor de Trabalho - Doc.: N/C Motivo: DESLIGADO"),
           ("24.12.2025", "Passa a Trabalhar na Empresa Alfa Lingerie CI 090/25/ST/UP/AGEPEN/MS."),
           ("19.04.2026", INI % "CELA LIVRE")])
ok(("24.12.2025", "19.04.2026", "BARBEIRO / ALFA LINGERIE") in trab(f), "livre: empresa no mesmo dia do registro do SIAPEN, sem o nº da CI: %s" % trab(f))

f = ficha([("23.02.2012", "PASSA AO TRABALHO EXTERNO-EMPRESA BETA OBRAS/CINº210/PP."),
           ("29.04.2012", "SAÍDA DA CPAIG, Motivo: mandado de prisão preventiva Destino: 7ª DP, Conforme autos nº 1."),
           ("04.08.2016", "Nesta data passa a Trabalhar no Setor de Artesanato nesta UP/CT."),
           ("15.03.2017", "Nesta data deixa de Trabalhar no Setor de Artesanato a pedido do mesmo."),
           ("07.07.2017", "Nesta data volta a Trabalhar no Setor de Artesanato nesta UP/CT."),
           ("27.09.2017", SAIDA % "Transferência de Presidio")])
t = trab(f)
ok(("23.02.2012", "29.04.2012", "EMPRESA BETA OBRAS") in t, "livre: trabalho externo até a 'SAÍDA DA <unidade>' (ficha antiga): %s" % t)
ok(("04.08.2016", "15.03.2017", "ARTESANATO") in t and ("07.07.2017", "27.09.2017", "ARTESANATO") in t,
   "livre: 'passa a trabalhar', 'deixa de trabalhar' e 'volta a trabalhar', sem 'nesta UP': %s" % t)
ok(all(x.get("texto_livre") for x in f["trabalho"]), "livre: vínculos marcados como lidos do texto livre")

f = ficha([("13.05.2021", INI % "BARBEIRO"),
           ("27.06.2022", "TRABALHO- Nesta data deixa de trabalhar como barbeiro e passa a desempenhar a função de Cela livre."),
           ("02.07.2025", SAIDA % "Transferência de Presidio")])
t = trab(f)
ok(t == [("13.05.2021", "27.06.2022", "BARBEIRO"), ("27.06.2022", "02.07.2025", "CELA LIVRE")], "livre: fim e início no mesmo lançamento: %s" % t)

f = ficha([("08.11.2012", "REMANEJADO PARA O SETOR DE MANUTENÇÃO, CONFORME DETERMINAÇÃO DO SETOR DE TRABALHO."),
           ("08.11.2012", INI % "UP MANUTENÇÃO SERV. GERAIS"),
           ("08.05.2013", "REMANEJADO PARA ATIVIDADE EXTERNA NA EMPREITEIRA GAMA, CONFORME CI Nº746/13."),
           ("11.06.2013", "DESLIGADO DO TRABALHO EXTERNO A PEDIDO DO EMPREGADOR SENDO REMANEJADO PARA A ATIVIDADE INTERNA NA LAVOURA, CONFORME CI 1."),
           ("28.06.2013", INI % "PP - EMP. DELTA")])
t = trab(f)
ok(("08.11.2012", "08.05.2013", "UP MANUTENÇÃO SERV. GERAIS") in t, "livre: remanejamento e registro do SIAPEN do mesmo setor no dia: fica o do SIAPEN: %s" % t)
ok(("08.05.2013", "11.06.2013", "EMPREITEIRA GAMA") in t and ("11.06.2013", "28.06.2013", "LAVOURA") in t,
   "livre: nome sem 'ATIVIDADE EXTERNA/INTERNA NA': %s" % t)

# o que não é trabalho
f = ficha([("01.03.2023", INI % "COZINHA"),
           ("10.03.2023", "Apresentou se e se encontra recolhido a disposição do setor de Disciplina."),
           ("11.03.2023", "Nesta data descumpriu o horário de retorno estabelecido pelo Setor de Trabalho, recolhido até segunda ordem.")])
ok(trab(f) == [("01.03.2023", "", "COZINHA")], "livre: setor de disciplina e 'horário de retorno' não abrem vínculo: %s" % trab(f))

# ---- saída da unidade: o que encerra e o que não encerra ----
for meio in (SAIDA % "Duplicidade de Registros", SAIDA % "Saída Temporária",
             "Mudança de Cela: UNIDADE A, Motivo: AGUARDANDO TRANSFERENCIA, Origem: X, Destino: Y, Conforme Documento: CI 1.",
             "Emitido Parecer da CA-CENTRAL DE ALVARÁ em documento oficial, no carimbo consta: TRANSFERÊNCIA.",
             "Foi escoltado ao Hospital Regional conforme Of. 1, transferência de leito. Sem alteração."):
    f = ficha([("01.03.2023", INI % "COZINHA"), ("10.03.2023", meio), ("20.03.2023", FIM % ("COZINHA", "IMPRODUTIVIDADE"))])
    ok(trab(f) == [("01.03.2023", "20.03.2023", "COZINHA")], "saída: '%s' não encerra o trabalho: %s" % (meio[:40], trab(f)))
for meio in ("TRANSFERIDO PARA UNIDADE B A FIM DE RESGUARDAR SUA INTEGRIDADE FÍSICA - OF Nº 1.",
             "09/03/13 FOI POSTO EM LIBERDADE CONFORME ALVARÁ DE SOLTURA, EXPEDIDO PELO JUÍZO.",
             "ENTRADA NO EPJFC PROCEDENTE DA CPAIG - CI 0282/2012."):
    f = ficha([("01.03.2012", "PASSA A TRABALHAR NO SETOR DE MANUTENÇÃO, CONFORME CI. 49/2012."), ("10.03.2012", meio)])
    ok(trab(f) == [("01.03.2012", "10.03.2012", "MANUTENÇÃO")], "saída: '%s' encerra o trabalho: %s" % (meio[:40], trab(f)))
# entrada na unidade e início no mesmo dia: a entrada não encerra o trabalho que começa nela
f = ficha([("05.05.2015", "PASSA A TRABALHAR NO SETOR DE COZINHA."), ("05.05.2015", "ENTRADA NO IPCG PROCEDENTE DO CT - OF 1.")])
ok(trab(f) == [("05.05.2015", "", "COZINHA")], "saída: entrada no próprio dia do início: %s" % trab(f))

# ---- mudança de cela "deixa de trabalhar", sem efeito, desconsiderar, liberação ----
f = ficha([("12.10.2023", INI % "CANTINA"),
           ("02.05.2024", "Mudança de Cela: UNIDADE A, Motivo: DEIXA DE TRABALHAR NA CANTINA, Origem: C07, Destino: C08, Conforme Documento: CI 30."),
           ("07.06.2024", INI % "ARTESANATO"), ("09.10.2025", FIM % ("CANTINA", "N/C"))])
ok(("12.10.2023", "02.05.2024", "CANTINA") in trab(f), "cela: 'deixa de trabalhar na Cantina' encerra; a baixa tardia não reabre: %s" % trab(f))

f = ficha([("20.05.2011", "AFASTADO DO TRABALHO, POR FALTA DE PRODUTIVIDADE."),
           ("14.06.2011", "REINICIOU SUAS ATIVIDADES LABORAIS NO SETOR DE OFICINA DE CRINAS, CONFORME CI 110/11."),
           ("15.06.2011", "EM TEMPO: TORNAR SEM EFEITO O LANÇAMENTO DO DIA 14/06/11, REFERENTE AO SETOR DE TRABALHO, CONFORME DETERMINAÇÃO."),
           ("21.10.2011", "REINICIOU SUAS ATIVIDADES LABORAIS NO SETOR DE OFICINA DE CRINAS, CONFORME CI 222/11.")])
ok(trab(f) == [("21.10.2011", "", "OFICINA DE CRINAS")], "sem efeito: o lançamento do dia anulado não conta: %s" % trab(f))

f = ficha([("16.04.2025", INI % "PRENDEBEM/UP"), ("18.01.2026", FIM % ("PRENDEBEM/UP", "N/C")), ("18.01.2026", INI % "FAXINA"),
           ("18.01.2026", "Desconsiderar Faxina, interno Trabalho Prendedores Prendebem")])
ok(trab(f) == [("16.04.2025", "", "PRENDEBEM/UP")], "desconsiderar: Faxina não existiu e Prendebem segue: %s" % trab(f))
f = ficha([("13.01.2026", INI % "PRENDEBEM/UP"),
           ("13.01.2026", "Setor de Trabalho: desconsiderar a função trabalho Prendebem, reconsiderar a função de Trabalho Auxiliar Juridico."),
           ("20.02.2026", FIM % ("PRENDEBEM/UP", "IMPRODUTIVIDADE"))])
ok(trab(f) == [("13.01.2026", "20.02.2026", "PRENDEBEM/UP")], "desconsiderar: com baixa posterior por improdutividade, o vínculo fica: %s" % trab(f))
f = ficha([("19.02.2025", INI % "EMPRESA OMEGA"),
           ("19.02.2025", FIM % ("EMPRESA OMEGA", "DESCONSIDERAR CADASTRO DE TRABALHO, POIS INTERNO ESTA CADASTRADO NO SETOR EDUCAÇÃO"))])
ok(trab(f) == [], "desconsiderar: baixa 'desconsiderar o cadastro' no dia do início: %s" % trab(f))

f = ficha([("01.02.2024", INI % "COZINHA"), ("01.03.2024", "Liberação do Setor de Trabalho - Doc.: CI 9 Motivo: OPERACIONAL")])
ok(trab(f) == [("01.02.2024", "01.03.2024", "COZINHA")], "liberação sem baixa no dia encerra: %s" % trab(f))

# ---- vínculo simultâneo (baixa tardia) ----
f = ficha([("04.04.2025", INI % "PRENDEBEM/UP"), ("15.09.2025", INI % "CELA LIVRE"),
           ("03.11.2025", FIM % ("PRENDEBEM/UP", "Saida do Presídio")), ("03.11.2025", SAIDA % "Transferência de Presidio")])
ok(trab(f) == [("04.04.2025", "15.09.2025", "PRENDEBEM/UP"), ("15.09.2025", "03.11.2025", "CELA LIVRE")],
   "simultâneo: a baixa 'saída do presídio' com o outro setor em curso não reabre: %s" % trab(f))
f = ficha([("01.06.2023", INI % "HORTA"), ("27.01.2024", INI % "OBRAS SIGMA"), ("07.11.2024", FIM % ("HORTA", "N/C"))])
ok(("01.06.2023", "27.01.2024", "HORTA") in trab(f) and not any(x.get("simultaneo") for x in f["trabalho"]),
   "simultâneo: o outro setor ainda em curso na baixa tardia: não reabre: %s" % trab(f))

# ---- atestados: nomes e períodos ----
f = ficha([("10.07.2019", "Nesta data foi peticionado o Atestado de Trabalho n 059/2019, nos Autos 0000001-11.2018.8.12.0014, sendo Serviços Gerais "
                          "(20/01/2017 a 19/04/2017) 77 dias trabalhados e 25 remidos, na função Artesanato (08/01/2019 a 04/04/2019), totalizando "
                          "63 dias trabalhados e 21 remidos."),
           ("18.09.2024", "EMITIDO ATP Nº 217/2024;PREN ROUPAS; DATA INICIAL: 13/03/2024; DATA FINAL: 16/05/2024; E CELA LIVRE DATA INICIAL 17/05/2024 ; "
                          "DATA FINAL 18/08/2024 TEMPO DE TRABALHO COMPUTADO NO PERÍODO: 165 DIAS TRABALHADOS; TEMPO DE REMIÇÃO: 55 DIAS REMIDOS."),
           ("25.04.2025", "EMITIDO ATP Nº 66/2025; DATA INICIAL: 19/09/2024; DATA FINAL: 25/04/2025; TEMPO DE TRABALHO COMPUTADO NO PERÍODO: 188 DIAS "
                          "TRABALHADOS; TEMPO DE REMIÇÃO: 62,66 DIAS REMIDOS."),
           ("07.08.2026", "Emitido ATESTADO DE TRABALHO 248/2026/ST/UP para os autos nº6000001-08.2021.8.12.0001 de 01/03/2024 a 03/06/2024 calculado 067 dias "
                          "trabalhados na Fab. Prendebem; de 06/06/2024 a 07/10/2024 calculado 106 dias trabalhados na pintor; Totalizando 173 dias trabalhados "
                          "e 57 dias remidos.")])
A = {a["numero"]: a for a in f["atestados"]}
ok([x["setor"] for x in A["059/2019"]["trechos"]] == ["Servicos Gerais", "Artesanato"], "atestado: 'sendo' não é nome: %s" % A["059/2019"]["trechos"])
ok([x["setor"] for x in A["217/2024"]["trechos"]] == ["Pren Roupas", "Cela Livre"], "ATP: '; E CELA LIVRE': %s" % A["217/2024"]["trechos"])
ok(A["066/2025"]["empresa"] == "" and A["066/2025"]["periodo_inicio"] == "19/09/2024", "ATP sem setor: 'DATA INICIAL' não é setor: %r" % A["066/2025"]["empresa"])
ok(A["248/2026"]["trechos"][0]["setor"] == "Prendebem (prendedores)", "atestado: 'Fab.' abreviado não corta o nome: %s" % A["248/2026"]["trechos"])

# ---- nomes de setor ----
P = rrm.palavra_comum
ok(P("Confecção de Bolas Freegol", "COSTURA DE BOLA") and P("Pren Roupas", "PRENDEDORES DE ROUPA"), "nome: singular x plural")
ok(P("Kapa", "R1 - FUNDIÇÃO KAPA"), "nome: nome de 4 letras dentro do outro")
ok(not P("FÁBRICA PRENDEBEM/EPJFC", "CELA LIVRE PV 1 / EPJFC") and not P("CONVENIO PREFEITURA DE ALFAVILLE", "CONVENIO PREFEITURA DE BETAPOLIS"),
   "nome: sigla da unidade e 'prefeitura/convênio' não identificam o setor")
ok(P("CELA LIVRE", "CELA LIVRE PV 1 / EPJFC") and P("SETOR JURIDICO", "Auxiliar Juridico"), "nome: palavras próprias continuam valendo")
ok(rrm.setor_chave("FABRICA")[0] == rrm.setor_chave("Paica Lingerie")[0] == rrm.setor_chave("Paiva Lingerie")[0] == "PAIVA"
   and rrm.setor_chave("PRENDEDOR DE ROUPAS")[0] == "PRENDEBEM", "sinônimos: grafias de Paiva e Prendedor")
ok(rrm.setor_chave("ATIVIDADE EXTERNA NA EMPREITEIRA GAMA")[0] == "GAMA", "setor_chave sem 'atividade externa na empreiteira'")

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for x in falhas:
        print(" -", x)
    sys.exit(1)
print("teste_leitura_714: ok")
