"""Teste de regressão das redações da Ficha Disciplinar do SIAPEN (auditoria de 08.10): atestados de trabalho em várias redações
(só remidos, "e/ou", parênteses, "DT/DR", só o período, vários períodos), ATP com período, atestado de estudo/leitura, faltas no
formato antigo, CD simplificada, isolamento com data nula, pareceres e regressão, artigo da falta, leitura, estudo, vínculos de
trabalho em texto livre, falsas fugas e divisão de lançamentos. Rodar: python teste_ficha_redacoes.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf
import rspe_remicao as rrm

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def at1(data, texto):
    """(trabalhados, remidos, trechos) do único atestado lido no lançamento; None se não for lido."""
    ats = rrm.atestados([{"data": data, "texto": texto}])
    return (ats[0]["trab"], ats[0]["rem"], ats[0]["segs"]) if len(ats) == 1 else None


def ficha(eventos):
    f = {"eventos": [{"data": d, "texto": t} for d, t in eventos]}
    rf.atualizar(f)
    return f


# ---- E1: atestados de trabalho em redações não cobertas ----
casos = [
    ("21.07.2026", "TRABALHO; NESTA DATA FOI EMITIDO AT Nº253/PDIB COM 51 DIAS REMIDOS, POLIGONAL.", None, 51.0),
    ("09.08.2022", "Emitido Atestado de Trabalho Prisional, n. 258/2022 - Prendedores de roupas - Data Inicial: 06/04/2022; Data Final: 09/08/2022; "
                   "Tempo de trabalho computado no período: 108 dias trabalhados; Tempo de Remissão: 36 dias.", 108, 36.0),
    ("04.11.2020", "Emitido Atestado de Trabalho Prisional 241/2020. Artesanato - 03.03.2020 a 03.11.2020 211 dias trabalhados 70 dias remidos", 211, 70.0),
    ("10.05.2019", "-Nesta data foi emitido ATESTADO DE TRABALHO PRISIONAL Nº 032/2019, correspondente ao período de 11/03/2019 a 29/03/2019. "
                   "Totalizando 15 (quinze) dias trabalhados e 05 (cinco) dia REMIDOS. Ag. Silene Félix/EPRSAA/A.", 15, 5.0),
    ("26.05.2021", "ATESTADO DE TRABALHO Nº 123/2021 emitido, sendo 51 dias trabalhados e/ou 17 dias remidos, enviado a x@gmail.com em 27/05/2021.", 51, 17.0),
    ("15.09.2025", "Nesta data foi emitido o atestado de trabalho 574/2025/ST/PED/AGEPEN/MS,contabilizando (180) dias trabalhados, sendo (60) dias remidos.", 180, 60.0),
    ("22.04.2013", "Nesta data foi emitido Atestado de Trabalho Nº 20/2013, onde consta 241 dias Trabalhados e 80 dias a Remir, referente ao Período de "
                   "15/07/2012 a 22/04/2013 em que o mesmo Trabalhou nesta UP/CT no Setor de Artesanato. (Of. Barbosa)", 241, 80.0),
    ("30.11.2021", "Nesta data foi elaborado o Atestado de Trabalho nº 222/21, referente a 102 dias trabalhados , totalizando 34 dias remidos.", 102, 34.0),
    ("12.01.2021", "Emitido ATP 29/2021: artesanato - 05.02.2020 a 12.01.2021 294 dias trabalhados 98 dias remidos", 294, 98.0),
    ("22.04.2025", "EMITIDO ATESTADO DE TRABALHO 157/2025 - 234DT / 78DR", 234, 78.0),
    ("21.01.2023", "Peticionado Atestado de Trabalho n 006/2023 no Sistema SEEU, autos 0011174-97.2017.8.12.0002, função Cela Livre (17/09/2022 a 21/01/2023) "
                   "totalizando 108 trabalhados e 36 remidos.", 108, 36.0),
]
for d, t, tr, rm in casos:
    r = at1(d, t)
    ok(r is not None and r[0] == tr and r[1] == rm, "atestado não lido ou lido errado (%s): %s" % (r and r[:2], t[:60]))
r = at1("23.10.2025", "ATESTADO DE TRABALHO PRISIONAL Nº 124/2025 - DE 14/12/2024 - 02/05/2025")
ok(r is not None and r[1] is None and r[2][0]["ini"] == date(2024, 12, 14) and r[2][0]["fim"] == date(2025, 5, 2) and not r[2][0]["inferido"],
   "atestado só com o período: reconhecido, com o período e dias desconhecidos")

# ---- E2: vários períodos com um total só (sem "erro de ano") ----
t = ("Nesta data foi emitido ATESTADO DE TRABALHO PRISIONAL Nº 040/2020/ST/EPRSAA-A/AGEPEN-MS, correspondente ao período de 01/11/2019 a "
     "24/12/2019, e correspondente ao período de 14/04/2020 a 30/06/2020. Totalizando 90 (noventa) dias trabalhados e 30 (trinta) dias REMIDOS.")
r = at1("08.07.2020", t)
ok(r is not None and r[:2] == (90, 30.0) and len(r[2]) == 2 and r[2][1]["ini"] == date(2020, 4, 14), "atestado com dois períodos vira dois trechos")
C = rrm.conciliar({"_incidentes": []}, {"eventos": [{"data": "08.07.2020", "texto": t}]}, date(2026, 10, 7))
ok(not any(a["tipo"] == "erro de ano" for a in C["alertas"]) and C["atestados"][0]["segs"][0]["ini"] == date(2019, 11, 1),
   "vários períodos: sem falso 'erro de ano' e sem corrigir o início")
r = at1("15.03.2026", "Peticionado o Atestado de trabalho n 039/2026, no Sistema SEEU, Autos 6000051-17.2024.8.12.0014, função Auxiliar Administrativo "
                      "(24/02/2025 a 23/12/2025) e função Paiva Lingerie (24/12/2025 a 04/03/2026) totalizando 309 dias trabalhados e 103 dias remidos.")
ok(r is not None and r[:2] == (309, 103.0) and len(r[2]) == 2, "duas funções e um total: dois trechos, total do atestado")

# ---- E3: trecho de função sem "dias" ou sem o "e" ----
r = at1("26.05.2024", "Peticionado o Atestado de Trabalho n 084/2024, função Horta (01/06/2023 a 26/01/2024) totalizando 206 dias trabalhados 68,66 remidos; "
                      "função Poligonal (27/01/2024 a 26/05/2024) totalizando 84 dias trabalhados e 28 remidos.")
ok(r is not None and len(r[2]) == 2 and r[1] == 96.66, "dois trechos de função lidos (sem o 'e')")
r = at1("13.11.2023", "Peticionado o Atestado de Trabalho n 189/2023, função Prendedores (01/01/2023 a 30/03/2023) 55 trabalhados e 18,33 remidos.")
ok(r is not None and r[:2] == (55, 18.33), "trecho sem a palavra 'dias'")

# ---- E4: ATP com período explícito ----
r = at1("12.01.2022", "EMITIDO ATP Nº 042/2022 REFERENTE AO TEMPO DE TRABALHO DE 18.08.2021 A 11.01.2022 126 DIAS TRABALHADOS 42 DIAS REMIDOS")
ok(r is not None and not r[2][0]["inferido"] and r[2][0]["ini"] == date(2021, 8, 18), "ATP com período explícito não é lote")

# ---- E5: leitura e estudo não são trabalho; atestado de estudo entra como estudo ----
ok(at1("27.05.2021", "ATESTADO DE REMIÇÃO POR LEITURA - Nesta data foi PROTOCOLADO o Atestado de Remição Por Leitura n°71/2020 - CICLO n°03/2020. "
                     "Titulo do livro: O SEGREDO, no qual a comissão de remição recomenda a validação de 04 (quatro) dias de remição.") is None,
   "atestado de leitura não é trabalho")
ok(at1("12.09.2022", "Emitido ATP Nº 283/2022, referente a frequência escolar no 1º semestre de 2022, totalizando 400 h/a e 33 dias remidos.") is None,
   "ATP de frequência escolar não é trabalho")
t = ("Nesta data, foi enviado, via Esaj, Atestado de Trabalho prisional do interno; Tipo: Estudante; Data Inicial: 17.08.2017; Data Final: 22.12.2017; "
     "Tempo de Estudo: 329/h/a; Tempo de Remissão: 27 dias.")
ok(at1("21.03.2018", t) is None, "atestado de estudante não é trabalho")
f = ficha([("21.03.2018", t)])
ok([(e["inicio"], e["fim"], e["horas"]) for e in f["estudos"]] == [("17.08.2017", "22.12.2017", 329)], "atestado de estudante vira período de estudo")

# ---- E6, E7, E9: faltas no formato antigo, isolamento com data nula, CD simplificada, proposta de regressão ----
f = ficha([("15.08.2012", "Tomou ciencia da decisão do Conselho Disciplinar nº 31/633.005/2012, sendo imputado o cometimento de falta disciplinar GRAVE, "
                          "referente ao fato ocorrido em 10/01/2012, confirmando o isolamento previamenter aplicado"),
           ("04.04.2018", "Tomou ciência do PADIC Nº31/608.142/2017,o interno praticou falta de natureza grave, sendo aplicado sanção de 20(vinte) dias de "
                          "isolamento de Cela Disciplinar, e sua conduta rebaixada para MÁ pelo período de 12(doze) meses, a contar da data do fato.18/09/2017."),
           ("27.08.2025", "CONSELHO DISCIPLINAR: ISOLADO PREVENTIVAMENTE EM CELA DISCIPLINAR, POR 10 DIAS, REFERENTE A LANÇAMENTO DE FALTA DISCIPLINAR "
                          "COMETIDA EM 30/12/1899 - RESPONDE PADIC/PDIB."),
           ("04.04.2017", "01-FALTOU AO PERNOITE DO DIA 04/04/2017 02INSTAURADA CDS Nº 205/2017 no dia 06/04/2017 03- SANCIONADO ADMINISTRATIVAMENTE COM 90 "
                          "DIAS SEM VISITA AO LAR AOS DOMINGOS E FERIADOS"),
           ("06.04.2017", "01-FALTOU AO PERNOITE DO DIA 04/04/201702-INSTAURADA CDS Nº 205/201703-SANCIONADO ADMINISTRATIVAMENTE COM 90 DIAS"),
           ("15.10.2014", "CONSELHO DISCIPLINAR: TOMOU CIÊNCIA DO RESULTADO PROCESSO - PADIC / EPMR Nº 31/622.515/2014 , REFERENTE AO FATO OCORRIDO EM "
                          "13/10/2014, QUE CONFORME DECISÃO DO CONSELHO DISCIPLINAR, FOI PROPOSTA DE REGRESSÃO DE REGIME."),
           ("03.02.2015", "Foi emitido para fins de Progressão de Regime Parecer Disciplinar nº 004/2015, com a Conduta Carcerária sendo classificado como "
                          "MÁ, por ter cometido falta grave no dia 13 de outubro de 2014.")])
fal = {x["data_fato"].replace("/", "."): x for x in f["faltas"]}
ok(fal.get("10.01.2012", {}).get("situacao") == "homologada/punida" and fal["10.01.2012"]["grave"], "decisão antiga do Conselho vira falta julgada grave")
ok(fal.get("18.09.2017", {}).get("situacao") == "homologada/punida" and fal["18.09.2017"].get("natureza") == "grave", "'praticou falta de natureza grave'")
ok(fal.get("27.08.2025", {}).get("situacao") == "PADIC instaurado", "isolamento com data 30/12/1899: falta do dia do lançamento, com PADIC")
ok(fal.get("04.04.2017", {}).get("situacao") == "homologada/punida", "CD simplificada sancionada administrativamente")
ok(fal.get("13.10.2014", {}).get("situacao") == "homologada/punida", "proposta de regressão é resultado sancionado")
ok(len(f["faltas"]) == 5, "faltas: %d (esperado 5: a CDS lançada duas vezes e o parecer não são falta nova)" % len(f["faltas"]))

# ---- E8: resumo da ficha e regressão judicial não são falta nova ----
f = ficha([("11.04.2013", "REGISTRO DE FALTA DISCIPLINAR: FALTA GRAVE, ART. 50, INCISO VII DA LEP."),
           ("26.09.2017", "Em sua Ficha consta envolvimento com tráfico de droga dentro da Unidade Penal no dia 11/04/2013, e ainda na mesma data foi flagrado "
                          "com 01 (um) aparelho de celular, respondendo PADIC, diante disso cometeu 02 (duas) faltas graves conforme o artigo 134 do RIBUP"),
           ("12.07.2019", "Saída do Regime Semiaberto da Unidade Penal: ESTABELECIMENTO PENAL DE NAVIRAÍ, Motivo: Evasão, conforme art. 4º da Portaria"),
           ("11.03.2021", "REGRESSÃO DE REGIME: Tomou ciência da DECISÃO: \"... cumprindo pena em regime SEMIABERTO, evadiu. Nesses termos, devidamente "
                          "comprovado ter o sentenciado cometido falta grave, nos termos do artigo 118, I da LEP, REGRIDO o regime\". Juiz em 09/03/2021.")])
ok(sorted(x["data_fato"] for x in f["faltas"]) == ["11.04.2013", "12.07.2019"], "resumo não é falta nova; regressão por evasão fica com a data da evasão")

# ---- E10: artigo da falta (LEP x RIBUP) ----
u = ("CONSELHO DISCIPLINAR: REGISTRO DE FALTA DISCIPLINAR COM FULCRO NO ART. 60 DA LEI Nº 7.210, POR TER INFRINGINDO EM TESE O ART 79, INCISOS I, III, "
     "XV E XVI; 102, INCISO XXII, E 103, INCISO III E XXXVII DO RIBUP E ARTIGOS 39, INCISOS I E VI E 50, INCISO VI E VII, DA LEP.. RESPONDE PROCESSO")
ok(rf._artigo_falta(u) == "art. 50, VI e VII, da LEP", "artigo da LEP citado depois do RIBUP: %s" % rf._artigo_falta(u))
ok(rf._artigo_falta("POR TER INFRINGINDO EM TESE O ART 103, XXVII DO RIBUP/MS. RESPONDE") == "art. 103, XXVII, do RIBUP", "artigo do RIBUP com o nome certo")

# ---- E11: leitura ----
f = ficha([("18.08.2026", "EDUCAÇÃO: Peticionado relatório de leitura referente aos meses 02,03,04 e 05de 2026."),
           ("15.05.2024", "REALIZOU PROJETO REMIÇÃO PELA LEITURA: referente aos meses: março e abril, dos livros o cortiço e vidas secas."),
           ("31.08.2022", "EDUCAÇÃO: Participou no mês de Julho 2022 da Remição pela Leitura sendo aprovado em sua resenha após correção."),
           ("09.05.2024", "REALIZOU PROJETO REMIÇÃO PELA LEITURA: referente aos livros: a hora da estrela; a volta ao mundo em 80 dias"),
           ("23.05.2023", "REALIZOU PROJETO REMIÇÃO PELA LEITURA OF Nº481/23/EPMR/AGEPEN/MS; REFERENTE AO MES DE ABRIL; LIVRO: VIDAS SECAS; AUTOS: 1."),
           ("24.05.2023", "REALIZOU PROJETO REMIÇÃO PELA LEITURA OF Nº481/23/EPMR/AGEPEN/MS; REFERENTE AO MES DE ABRIL; LIVROS: VIDAS SECAS; AUTOS: 1.")])
le = {x["data"]: x for x in f["leituras"]}
ok(le.get("18.08.2026", {}).get("meses") == ["02/2026", "03/2026", "04/2026", "05/2026"], "meses numéricos colados ao 'de'")
ok(le.get("15.05.2024", {}).get("meses") == ["03/2024", "04/2024"], "meses sem ano: o ano do lançamento")
ok(le.get("31.08.2022", {}).get("meses") == ["07/2022"], "'mês de Julho 2022'")
ok(le.get("09.05.2024", {}).get("obras") == 2, "lista de livros separada por ';'")
ok(len([x for x in f["leituras"] if x.get("oficio") == "481/23"]) == 1, "o mesmo relatório (ofício) conta uma vez")

# ---- E12: estudo ----
f = ficha([("25.07.2014", "EDUCAÇÃO: Matrículou-se na Série: DESISTENTE Turma: Período:"),
           ("10.03.2020", "EDUCAÇÃO: Matriculou –se no curso IFMS de VENDEDOR, carga horária de 180 horas. Início 10 de março de 2020."),
           ("13.08.2025", "EDUCAÇÃO: CORTE E COSTURA BÁSICO realizado em Bataguassu, MS, no período de 29/07/2024 a 01/08/2024 com carga horária de 32 horas.")])
es = [(e["curso"], e["inicio"], e["fim"], e["horas"]) for e in f["estudos"]]
ok(not any("DESISTENTE" in e[0] for e in es), "'série: DESISTENTE' não é período de estudo")
ok(("CORTE E COSTURA BÁSICO", "29.07.2024", "01.08.2024", 32) in es, "curso sem a palavra CURSO, com período dd/mm/aaaa")
ve = next((e for e in f["estudos"] if e["horas"] == 180), None)
ok(ve is not None and ve["motivo_fim"] == "carga horária declarada", "curso com carga declarada e sem período")

# ---- E13: vínculos de trabalho em texto livre ----
vs, _ = rrm.vinculos([{"data": "26.01.2023", "texto": "COMEÇA NO TRABALHO DE SERVIÇOS GERAIS CONFORME O DOCUMENTO Nº 091/PEMRFGII-TRAB/AGEPEN"},
                      {"data": "02.03.2020", "texto": "Foi ingressado nas atividades laborais da EMPRESA PRENDE BEM,nesta Penitenciária."},
                      {"data": "01.01.2018", "texto": "INICIOU SUAS ATIVIDADES LABORAIS NO SETOR DE ECOFLAKE, CONFORME CI."},
                      {"data": "22.09.2020", "texto": "Nesta data o sentenciado pediu desligamento da empresa Ecoflake Ind. Reciclados Ltda."},
                      {"data": "02.01.2019", "texto": "REINICIOU SUAS ATIVIDADES LABORAIS NO RECOLHIMENTO DE MARMITAS, CONFORME DETERMINAÇÃO DO SETOR DE TRABALHO AG VEGA - IPCG."},
                      {"data": "29.07.2013", "texto": "RETORNOU DO TRABALHO EXTERNO NA EMPRESA BAROLI EM VISÍVEL ESTADO DE EMBRIAGUEZ - CI 683/13."}], date(2026, 10, 7))
nomes = {v["setor"]: v for v in vs}
ok("Servicos Gerais" in nomes and "Prendebem (prendedores)" in nomes, "inícios em texto livre ('começa no trabalho', 'foi ingressado')")
ok(nomes.get("Ecoflake", {}).get("fim") == date(2020, 9, 22), "'pediu desligamento da empresa' encerra o vínculo")
ok("Recolhimento de Marmitas" in nomes and not any("Vega" in s for s in nomes), "o setor é a função, não o agente que assina")
ok(not any("Baroli" in s for s in nomes), "retorno do trabalho embriagado não abre vínculo")

# ---- E14: falsas fugas/solturas ----
for t in ["Mudança de Cela: PENITENCIÁRIA JAIR FERREIRA DE CARVALHO, Motivo: TENTATIVA FUGA, Origem: 03/UNICO/UNICO/101",
          "informado ainda que não poderá incorrer em nova falta sob pena de evasão imediata.",
          "foi escoltado pela PM até o HOSPITAL MUNICIPAL CRISTO REI, para CONSULTA MÉDICA e até o termino do plantão NÃO RETORNOU."]:
    ok(not rf.RE_FUGA_FICHA.search(t) and not rf.RE_SAIDA_LIVRE.search(t), "não é fuga: %s" % t[:50])
ok(not rf.RE_SAIDA_LIVRE.search("Saída da Unidade Penal: EPA, Destino: EPRSA, Motivo: Alvará de Transferência, Conforme Autos: 1."), "alvará de transferência não é liberdade")
ok(rf.RE_FUGA_FICHA.search("Saída da Unidade Penal: CPAIG, Destino: EVASÃO, Motivo: Fuga, Conforme Ofício: 274/15."), "fuga verdadeira continua lida")

# ---- E15: resumo com a mesma leitura de atestados da remição ----
f = ficha([("21.07.2026", "TRABALHO; NESTA DATA FOI EMITIDO AT Nº253/PDIB COM 51 DIAS REMIDOS, POLIGONAL.")])
ok(rf.resumo(dict(f, trabalho=[])).startswith("1 atestado, 51 dias remidos"), "resumo: %s" % rf.resumo(dict(f, trabalho=[])))

# ---- E16: divisão de lançamentos ----
ev = rf._dividir([{"data": "24.05.2002", "texto": "INICIOU ATIVIDADE LABORAL NO SETOR DE MANUTENÇÃO. Em 11/03/04 Nesta data iniciou trabalho no setor da faxina."},
                  {"data": "10.10.2017", "texto": "Mudança de Cela: EPMR, Conforme Documento: CI 266/17. 12.12.2017 - Nesta data interno foi escoltado."},
                  {"data": "01.02.2023", "texto": "Atestado n. 051/2023 - de 22/03/2022 à 05/07/2022; de 15.09.2022 à 01.02.2023 - Tempo de trabalho: 211 dias"}])
ok([e["data"] for e in ev] == ["24.05.2002", "11.03.2004", "10.10.2017", "12.12.2017", "01.02.2023"], "lançamentos divididos: %s" % [e["data"] for e in ev])

if falhas:
    print("FALHOU (redações da ficha):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: redações da ficha (atestados, faltas, leitura, estudo, vínculos, fugas e divisão de lançamentos)")
