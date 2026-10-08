"""Teste de regressão da leitura da ficha do SIAPEN (rev4 das fichas). Casos dos revisores, em forma sintética: extração pela fonte
(o histórico antigo de 10 pt cortado na impressão não embaralha nem cria lançamentos; rodapé de 7 pt e 2ª linha do nome fora; linha
"RUA:" do lançamento fica; lançamento sem data guardado sem data); cabeçalho (condenação em branco, data da prisão intercalada);
sublançamentos "dd/mm/aa... Nesta data/FOI/DEU ENTRADA"; entrada vinda da delegacia; saída por determinação judicial para presídio;
alvará/fuga só citados; domiciliar; fuga narrada; saídas temporárias; trabalho externo pela empresa; faltas (PADIC na instauração,
"LEI Nº 7.210", data do cometimento, PADIC repetido, PAD em texto livre, erros de digitação, ano de 2 dígitos); estudo encerrado na
saída; matrícula livre de nomes diferentes; isolamentos; siglas de unidade. Rodar: python teste_ficha_rev4.py"""
import os
import sys
import tempfile
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def ficha(evs, **extra):
    f = dict({"eventos": [{"data": d, "texto": t} for d, t in evs], "versao_leitura": 0}, **extra)
    return rf.atualizar(f)


# ---- A1-A4 e A16c/d: extração por fonte num PDF montado como o do SIAPEN ----
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4, landscape
    d = tempfile.mkdtemp()
    cam = os.path.join(d, "ficha.pdf")
    W, H = landscape(A4)
    c = canvas.Canvas(cam, pagesize=(W, H))

    def txt(x, top, s, font="Times-Roman", size=8):
        c.setFont(font, size)
        c.drawString(x, H - top - size, s)
    txt(138, 32, "SISTEMA INTEGRADO DE ADMINISTRAÇÃO PENITENCIÁRIA - SIAPEN", "Times-Bold", 10)
    txt(348, 103, "FICHA DISCIPLINAR (ID: 1 )", "Times-Bold", 12)
    txt(45, 126, "Nome:", "Times-Bold", 10); txt(90, 126, "FULANO DE TAL DA SILVA", size=10); txt(300, 126, "RGI:", "Times-Bold", 10); txt(330, 126, "12345", size=10)
    txt(45, 143, "CPF:", "Times-Bold", 10); txt(80, 143, "012.838.681-99", size=10)
    txt(45, 283, "Data Prisão:", "Times-Bold", 10); txt(120, 283, "10/04/2026", size=10); txt(200, 283, "Procedência:", "Times-Bold", 10)
    txt(280, 283, "DP MIRANDA", size=10); txt(400, 283, "Condenação:", "Times-Bold", 10)
    txt(45, 300, "Data Entrada:", "Times-Bold", 10); txt(120, 300, "16/04/2026", size=10); txt(200, 300, "Unidade Penal:", "Times-Bold", 10)
    txt(280, 300, "PENITENCIÁRIA DE DOIS IRMÃO DO BURITI", size=10)
    txt(332, 358, "HISTÓRICO - CONDUTA: OTIMA", "Times-Bold", 12)
    txt(96, 380, "- CONSELHO DISCIPLINAR: FOI CONCLUSO PROCESSO - PADIC Nº 31/072306/2023, REFERENTE AO FATO OCORRIDO EM 05/10/2023, COMETEU FALTA DISCIPLINAR DE NATUREZA GRAVE.")
    # histórico antigo em 10 pt na mesma altura dos lançamentos (cortado na impressão)
    txt(31, 391, "Em 21/09/10 Classificado conduta disciplinar em ÓTIMA em atendimento ao Mutirão", size=10)
    txt(96, 392.3, "25.10.2010 - SAÍDA DO EPJFC MEDIANTE LIVRAMENTO CONDICIONAL- OF. 5381/10/SJ/EPJFC.")
    txt(96, 406.6, "25.02.2025 - Emitido Atestado de Permanência Carcerária. End.:")
    txt(96, 416, "RUA: ANTONIO GONÇALVES S/N")
    txt(407, 525, "RUA:", size=7); txt(402, 533, "CEP: . - -", size=7); txt(397, 542, "FONE: - Fax: -", size=7)
    txt(36, 552, "Nome:", "Times-Bold", 10); txt(72, 552, "FULANO DE TAL DA SILVA - CARLOS Projeto SIAPEN, Impresso em 05/10/2026 - 14:43:22, Pag. 1/1")
    txt(72, 561.7, "FERNANDES")
    c.showPage(); c.save()
    f = rf.extrair(cam)
    evs = f["eventos"]
    ok(any(e["data"] == "25.10.2010" and e["texto"].startswith("SAÍDA DO EPJFC MEDIANTE LIVRAMENTO") for e in evs), "A1: lançamento perdido no histórico oculto: %s" % evs)
    ok(not any("Mutirão" in e["texto"] or "21/09/10" in e["texto"] for e in evs) and f.get("historico_oculto"), "A1: histórico oculto virou lançamento: %s" % evs)
    ok(evs and evs[0]["data"] == "" and evs[0]["texto"].startswith("CONSELHO DISCIPLINAR: FOI CONCLUSO"), "A2: lançamento sem data perdido: %s" % evs[:1])
    ok(not any("FERNANDES" in e["texto"] for e in evs), "A3: 2ª linha do nome do rodapé colada: %s" % evs[-1:])
    ok(any("RUA: ANTONIO GONÇALVES" in e["texto"] for e in evs), "A4: linha 'RUA:' do lançamento apagada: %s" % evs[-1:])
    ok(f["condenacao"] == "" and f["data_prisao"] == "10/04/2026", "A16c: condenação em branco pegou a linha seguinte: %r" % f["condenacao"])
    ok(any("05/10/2023" in x["data_fato"].replace(".", "/") for x in f["faltas"]), "A2: falta do lançamento sem data: %s" % f["faltas"])
    nota, _parc = rf.leitura_parcial(f)
    ok(any("sem data no SIAPEN" in n for n in nota), "A2: aviso do lançamento sem data: %s" % nota)
except ImportError:
    pass
ok(rf.data_prisao_cabecalho("Data Prisão: AVÓ-D0O6L/1O2R/2E0S1)5 Procedência: X") == "06/12/2015", "A16d: data da prisão intercalada")
ok(rf.data_prisao_cabecalho("Data Prisão: COM 29/04/2009 Procedência: X") == "29/04/2009", "A16d: palavra antes da data")

# ---- A5: sublançamentos ----
f = ficha([("08.03.2008", "Deu entrada neste EPC. 14/03/08... Nesta data reingressou neste EPC procedente da DP. 06/08/08... Nesta data foi beneficiado "
                          "com regime Semi-Aberto. Conforme declaração datada de 17/03/2008, foi cancelada a visita."),
           ("30.10.2008", "INICIOU ATIVIDADE LABORAL NO SETOR DE ARTESANATO. 10/03/09 FOI POSTO EM LIBERDADE CONFORME ALVARÁ DE SOLTURA.")])
ds = [e["data"] for e in f["eventos"]]
ok("14.03.2008" in ds and "06.08.2008" in ds and "10.03.2009" in ds and "17.03.2008" not in ds, "A5: sublançamentos: %s" % ds)

# ---- A6: entrada vinda da delegacia ----
for proc in ("1 DP AQUIDAUANA - INTERIOR", "1º DP DE JARDIM - INTERIOR", ".DP MIRANDA - INTERIOR", "1ª DELEGACIA DE POLICIA DE AQUIDAUANA", "DERF - CAPITAL",
             "DEAM - CAPITAL", "DPF DOURADOS - INTERIOR", "POLINTER - CAPITAL", "GARRAS - CAPITAL", "BELA VISTA - DP - INTERIOR", "1ª CIA INDEPENDENTE POLICIA MILITAR"):
    t = "Entrada na Unidade Penal: ESTABELECIMENTO PENAL DE AQUIDAUANA, Procedente: %s, Conforme OF/CI 1." % proc
    ok(rf.RE_ENTRADA_RUA.search(t), "A6: entrada vinda de %r não reconhecida" % proc)
ok(rf.RE_ENTRADA_RUA.search("ENTRADA NO EPJFC, PROCEDENTE DO DENAR"), "A6: 'ENTRADA NO EPJFC, PROCEDENTE DO DENAR'")
ok(not rf.RE_ENTRADA_RUA.search("Entrada na Unidade Penal: IPCG, Procedente: PEMRFG - CAPITAL, Conforme CI 1."), "A6: entrada vinda de presídio lida como da rua")

# ---- A7/A8: saída em liberdade e fuga ----
nao = ["Saída da Unidade Penal: ESTABELECIMENTO PENAL REGIME SEMIABERTO E ABERTO AQUIDAUANA, Destino: Estabelecimento Penal de Aquidauana, Motivo: Determinação Judicial, Conforme Ofício: 1.",
       "Saída da Unidade Penal: UNIDADE MISTA DE MONITORAMENTO VIRTUAL, Destino: PDIB, Motivo: Determinação Judicial, Conforme Ofício: 1.",
       "Nesta data tomou ciência do Alvará de Soltura nos autos 1. Não foi colocado em liberdade devido pendência.",
       "Mudança de Cela: EPA, Motivo: AGUARDANDO CONSULTA DE ALVARÁ DE SOLTURA, Origem: 1, Destino: 2",
       "Emitido Parecer da CA-CENTRAL DE ALVARÁ referente aos autos 1",
       "NESTA DATA FOI PRESO POR EVASÃO, CONFORME OF 1",
       "ENTRADA NO EPJFC PROCEDENTE DA DEPAC, MOTIVO: EVASÃO DO EPRACA",
       "REAPRESENTAÇÃO: RETORNOU DE EVASÃO NESTA DATA"]
for t in nao:
    ok(not rf.RE_SAIDA_LIVRE.search(t), "A7: lido como saída em liberdade: %s" % t[:70])
ok(rf.RE_SAIDA_LIVRE.search("Saída da Unidade Penal: EPA, Destino: , Motivo: Regime Domiciliar, Conforme Ofício: 1."), "A7c: domiciliar")
ok(rf.RE_SAIDA_LIVRE.search("Saída da Unidade Penal: EPA, Destino: RESIDÊNCIA, Motivo: Determinação Judicial, Conforme Ofício: 1."), "A7: determinação judicial sem presídio")
for t in ("RECEBIMENTO DO TERMO DE ASSENTADA: Reconheço a prática de falta grave - evasão - ocorrida no dia 24.12.2019",
          "REGRESSÃO DE REGIME: Tomou ciência da DECISÃO que regrediu o regime pois evadiu",
          "FOI FLAGRADO PLANEJANDO PARA FUGIR, MAS NÃO TEVE CORAGEM PARA EXECUTAR A FUGA",
          "Advertido que se incorrer em nova falta será considerado Evasão"):
    ok(not rf.RE_FUGA_FICHA.search(t), "A8: fuga narrada lida como fuga: %s" % t[:60])
ok(rf.RE_FUGA_FICHA.search("Saída da Unidade Penal: CPAIG, Destino: , Motivo: Evasão, Conforme CI 1."), "A8: evasão estruturada")

# ---- A9: saídas temporárias (formatos inequívocos; saída e retorno contam uma vez) ----
ev = [{"data": "20.12.2016", "texto": "Saída confirmada do benefício de: SAÍDA TEMPORÁRIA DE NATAL, NUM.PORTARIA: 1/2016"},
      {"data": "27.12.2016", "texto": "Retorno confirmado do benefício de: SAÍDA TEMPORÁRIA DE NATAL, NUM.PORTARIA: 1/2016"},
      {"data": "29.12.2016", "texto": "Saída confirmada do benefício de: SAÍDA TEMPORÁRIA DE ANO NOVO, NUM.PORTARIA: 2/2016"},
      {"data": "08.05.2017", "texto": "Saída da Unidade Penal: EPA, Destino: RESIDÊNCIA, Motivo: Saída Temporária, Conforme Ofício: 1."},
      {"data": "15.08.2017", "texto": "RETORNOU DE SAÍDA TEMPORÁRIA PELO PRAZO DE 7 DIAS."},
      {"data": "10.10.2017", "texto": "Nesta data saiu da UP em saída temporária de 07 dias"},
      {"data": "12.12.2017", "texto": "BENEFICIADO COM SAÍDA TEMPORÁRIA PELO PRAZO DE 7 DIAS - OF. 1"},
      {"data": "20.12.2017", "texto": "O interno foi lançado como saída temporária, porém não pode sair por motivos financeiros"}]
ok(len(rf.saidas_temporarias(ev)) == 5, "A9: saídas temporárias: %s" % rf.saidas_temporarias(ev))

# ---- A10: trabalho externo pela empresa ----
f = ficha([("22.10.2013", "TRABALHO: Iniciou atividade laboral, no setor de trabalho A1 - LAVOURA-CPAIG, conforme documento ."),
           ("22.10.2013", "INICIA ATIVIDADE LABORAL EXTERNA NA EMBRAPA, CONFORME CI 1"),
           ("22.10.2013", "TRABALHO: Iniciou atividade laboral, no setor de trabalho CC - EMBRAPA, conforme documento ."),
           ("11.01.2017", "TRABALHO: Iniciou atividade laboral, no setor de trabalho TRABALHO EXTERNO, conforme documento ."),
           ("27.11.2024", "INICIA ATIVIDADE LABORAL EXTERNA NA EMPRESA FE FREITAS VALDEZ CONSTRUÇÕES CONVENIADA A AGEPEN CUMPRINDO CARGA HORÁRIA"),
           ("28.11.2024", "Saída da Unidade Penal: CPAIG, Destino: , Motivo: Evasão, Conforme CI 1.")])
ext = {t["setor"]: t.get("externo") for t in f["trabalho"]}
ok(ext.get("CC - EMBRAPA") and not ext.get("A1 - LAVOURA-CPAIG") and ext.get("TRABALHO EXTERNO"), "A10: externo no vínculo certo: %s" % ext)
ok(any(t.get("externo") and "FREITAS" in t["setor"] for t in f["trabalho"]), "A10: externo sem vínculo estruturado: %s" % ext)

# ---- A11-A14: faltas ----
f = ficha([("26.02.2025", "CONSELHO DISCIPLINAR: REGISTRO DE FALTA DISCIPLINAR COM FULCRO NO ART. 60 DA LEP, POR TER INFRINGINDO EM TESE O ART 50, INCISO VI DA LEP. RESPONDE PROCESSO - PADIC/PDIB."),
           ("13.06.2025", "CONSELHO DISCIPLINAR: INSTAURAÇÃO PROCESSO - PADIC / PDIB Nº 31.140.239-2025 , POR TER INFRINGINDO EM TESE: ART 50, REFERENTE A LANÇAMENTO DE FALTA DISCIPLINAR COMETIDA EM 26/02/2025.")])
ok(f["faltas"] and f["faltas"][0].get("padic") == "31.140.239-2025", "A11: PADIC da instauração: %s" % f["faltas"])
f = ficha([("12.11.2021", "CONSELHO DISCIPLINAR: REGISTRO DE FALTA DISCIPLINAR COM FULCRO NO ART. 60 DA LEI Nº 7.210 DE 11 DE JULHO DE 1984, POR TER INFRINGINDO EM TESE O ART 33 DA LEI 11.343 DE 2006, "
                          "O ART 52 CAPUT E ART 50 INCISO III E VII DA LEI Nº 7.210 DE 11 DE JULHO DE 1984. RESPONDE PROCESSO - PADIC/EPRSAAAQ.")])
ok(f["faltas"] and f["faltas"][0]["grave"] and "50" in f["faltas"][0]["artigo"], "A12: 'LEI Nº 7.210': %s" % f["faltas"])
f = ficha([("08.11.2019", "CONSELHO DISCIPLINAR: REGISTRO DE FALTA DISCIPLINAR COM FULCRO NO ART. 60 DA LEP, POR TER INFRINGINDO EM TESE O ART 103 DO RIBUP. RESPONDE PROCESSO - PADIC/CPAIG."),
           ("03.02.2020", "FOI CIENTIFICADO DA CONCLUSÃO DO PAD. Nº 31/620.936/2019 - EMBRIAGUEZ - QUE O MESMO COMETEU FALTA DISCIPLINAR DE NATUREZA MEDIA. A CONTAR DA DATA DO COMETIMENTO DA FALTA (08/11/2019).")])
ok(len(f["faltas"]) == 1, "A13: falta duplicada pela data do cometimento: %s" % [x["data_fato"] for x in f["faltas"]])
f = ficha([("11.11.2022", "CONSELHO DISCIPLINAR: REGISTRO DE FALTA DISCIPLINAR COM FULCRO NO ART. 60 DA LEP, POR TER INFRINGINDO EM TESE O ART. 102 DO RIBUP. RESPONDE PROCESSO - PADIC/PED."),
           ("29.11.2022", "CONSELHO DISCIPLINAR: INSTAURAÇÃO PROCESSO - PADIC / PED Nº 31/090.198/2022 , REFERENTE A LANÇAMENTO DE FALTA DISCIPLINAR COMETIDA EM 11/11/2022."),
           ("18.04.2023", "Tomou ciência da decisão do PADIC n°31/090.198/2022 - PED, em que cometeu falta disciplinar de natureza LEVE, a contar da data do fato: 10/11/2022.")])
ok(len(f["faltas"]) == 1, "A13: o mesmo PADIC em duas faltas: %s" % [x["data_fato"] for x in f["faltas"]])
for t, dfato, grave in (("Tomou ciencia do processo disciplinar nº 31/602.775/10 referente ao ocorriido em 31/10/10 sendo sancionado por 10 (dez) dias em cela diisciplinar.", "31.10.2010", True),
                        ('TOMOU CIÊNCIA DO PROCESSO DISCIPLINAR 31/602331/09, SENDO SANCIONADO COM DEZ DIAS EM CELA DISCIPLINAR, POR COMETER FALTA DISCIPLINAR "GRAVE" , EM 17/02/09', "17.02.2009", True),
                        ("TOMOU CONHECIMENTO DA DECISÃO DO PROCESSO DISCIPLINAR Nº 31/604.027/2012, O QUAL SUGERIU ISOLAMENTO EM CELA DISCIPLINAR PELO PERÍODO DE 20 DIAS, A CONTAR DA DATA DO FATO, OU SEJA, 12/02/2012.", "12.02.2012", True),
                        ("Em 27/09/10 Conforme decisão Processo Disciplinar 31/604.071/2010-PTRAN, referente ao ocorrido em 06/05/10, cometeu falta disciplinar de nateure GRAVE.", "06.05.2010", True),
                        ("TOMOU CIENCIA DA DECISÃO DA PADIC Nº 31/616.001/2015 - EPPAR, ONDE COMETEU FALTA DISCIPLINAR DE NATUREA GRAVE, A CONTAR DA DATA DA FALTA 02/09/2015.", "02.09.2015", True),
                        ("FOI CIENTIFICADO DA CONCLUSÃO DO PAD. Nº 31/620.673/2019 - QUE O MESMO COMETEU FATA DE NATUREZA GRAVE, DATA DA FALTA COMETIDA (14/04/2019).", "14.04.2019", True)):
    f = ficha([("27.01.2020", t)])
    ok(f["faltas"] and f["faltas"][0]["data_fato"] == dfato and f["faltas"][0]["grave"] == grave, "A14: %s -> %s" % (t[:50], [(x["data_fato"], x["grave"]) for x in f["faltas"]]))

# ---- A15: estudo encerrado na saída da unidade; matrícula aberta sem registro não conta até hoje no inciso XII ----
f = ficha([("18.03.2025", "EDUCAÇÃO: Matrículou-se na Série: SETOR ESCOLAR Turma: A Período: Matutino"),
           ("13.06.2025", "Saída da Unidade Penal: PDIB, Destino: UMMVE, Motivo: Alvará de Soltura, Conforme Ofício 1.")])
ok(f["estudos"] and f["estudos"][0]["fim"] == "13.06.2025", "A15: estudo aberto depois da saída: %s" % f["estudos"])
f = ficha([("01.03.2025", "EDUCAÇÃO: Matrículou-se na Série: EJA Turma: A Período: Matutino"),
           ("05.04.2025", "Saída da Unidade Penal: PDIB, Destino: RESIDÊNCIA, Motivo: Saída Temporária, Conforme Ofício 1.")])
ok(f["estudos"] and not f["estudos"][0]["fim"], "A15: saída temporária encerrou o estudo")

# ---- código A7: matrícula livre de cursos diferentes com o mesmo começo ----
f = ficha([("10.03.2022", "EDUCAÇÃO: CURSO DE INFORMATICA BASICA 40H REALIZADO NO PERÍODO DE 01/03/2022 A 10/03/2022"),
           ("10.03.2023", "EDUCAÇÃO: CURSO DE INFORMATICA AVANCADA 60H REALIZADO NO PERÍODO DE 01/03/2023 A 10/03/2023")])
ok(len([e for e in f["estudos"] if e.get("livre")]) == 2, "código A7: curso livre descartado pelo começo do nome: %s" % [e["curso"] for e in f["estudos"]])

# ---- A17: isolamentos ----
f = ficha([("21.05.2015", "Mudança de Cela: PED, Motivo: SDV, Origem: CELA DISCIPLINAR/DISCIPLINAR/13, Destino: CADEIA LINEAR B/B3/14, Conforme Documento: CI 1."),
           ("11.02.2020", "Mudança de Cela: EPA, Motivo: SANCIONADO, Origem: SOLARIO A/CELA 03, Destino: SOLARIO C/CELA Nº. 13 (CORRECIONAL), Conforme Documento: 19.")])
ok(len(f["isolamentos"]) == 1 and "CORRECIONAL" in f["isolamentos"][0], "A17: isolamentos: %s" % f["isolamentos"])

# ---- A16e: siglas das unidades e entradas antigas ----
ok(rf.classificar_unidade("EPRACA")[0] == "aberto" and rf.classificar_unidade("CT")[0] == "provisorio" and rf.classificar_unidade("CPAIG")[0] == "semiaberto",
   "A16e: siglas EPRACA/CT/CPAIG")
tl = rf.linha_unidades({"eventos": [{"data": "20.02.2013", "texto": "ENTRADA NO PTRAN PROCEDENTE DO CPAIG"}, {"data": "20.03.2013", "texto": "DEU ENTRADA NO EPJFC, CONF. OF 1"}]})
ok([u for _d, u in tl] == ["PTRAN", "EPJFC"], "A16e: entradas antigas: %s" % tl)

if falhas:
    print("FALHOU (ficha rev4):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: ficha rev4 (extração por fonte, sem data, rodapé, cabeçalho, sublançamentos, delegacia, saída e fuga, saídas temporárias, externo, "
      "faltas, estudo, isolamentos, unidades)")
