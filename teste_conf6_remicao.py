"""Conferência 7.14.4 (70 casos novos), frente remição: atestado de horas-aula lido como documento; atestados sem período da mesma
sequência de trabalho ligados ao trabalho que cobrem; base da perda por falta grave (art. 127) pelo período trabalhado, com o atestado
ainda não declarado; perda em duplicidade sem remição entre as faltas; reflexo da remição anterior à data-base na progressão (só a
fração); textos (conclusão com item vermelho, valor próximo, soma atestado + leitura, número "n 171/21", unidade do atestado e
unidade atual do ofício).
Dados fictícios (sem nomes). Rodar: python teste_conf6_remicao.py"""
import sys
import types
from datetime import date, timedelta

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf
import rspe_auditoria as ra

falhas = []
HOJE = date(2026, 10, 20)
PROC = "0000001-11.2018.8.12.0001"


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def rem(n, dec, ref=None):
    return {"tipo": "REMIÇÃO", "complemento": "%s Dia(s) Remido(s)" % n, "data_decisao": dec, "data_referencia": ref or dec, "situacao": "CONCEDIDO"}


def fgr(d, dec=None):
    return {"tipo": "HOMOLOGAÇÃO DE FALTA GRAVE", "situacao": "CONCEDIDO", "complemento": d, "data_referencia": d, "data_decisao": dec or d}


def perda(n, d, dec=None):
    return {"tipo": "DIAS PERDIDOS NA REMIÇÃO", "situacao": "CONCEDIDO", "complemento": "%d" % n, "data_referencia": d, "data_decisao": dec or d}


def R(*incs, ini="01/07/2008", **kw):
    r = {"processo_execucao": PROC, "_crimes": [], "_eventos": [{"data": ini, "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}],
         "_incidentes": list(incs)}
    rr = sum(float(i["complemento"].split()[0]) for i in incs if i["tipo"] == "REMIÇÃO")
    pp = sum(float(i["complemento"]) for i in incs if i["tipo"].startswith("DIAS PERDIDOS"))
    r["saldo_remidos"] = "%g dias (%g dias remidos - %g dias perdidos)" % (rr - pp, rr, pp)
    r.update(kw)
    return r


def F(eventos, impressao="06/10/2026"):
    f = rf.atualizar({"data_impressao": impressao, "eventos": [{"data": d, "texto": t} for d, t in eventos]})
    for k in ("leituras", "exames", "cursos_peticionados", "certidoes_estudo"):
        f.setdefault(k, [])
    return f


def N_(r, f):
    o = rf.comparativo(r, f, HOJE)
    return o, o["fd_novo"]


def doc(N, num=None, tipo=None):
    return next((d for d in N["docs"] if (num is None or d["num"] == num) and (tipo is None or d["tipo"] == tipo)), None)


def perdas(N):
    return [p["texto"] for p in N["pontos"] if p["tipo"] == "perda"]


INI = "TRABALHO: Iniciou atividade laboral, no setor de trabalho %s, conforme documento CI 1."
FIM = "TRABALHO: Deixa de trabalhar, no setor de trabalho %s, conforme documento , motivo: %s."
ENT = "Entrada na Unidade Penal: %s, Procedente: %s, Conforme OF/CI 1."

try:
    # ---- 1) "atestado de horas aulas, remir (180) cento e oitenta horas aulas": atestado de estudo de 15 dias (180 h ÷ 12), documento da
    # comparação, provavelmente remido pela remição de 15 dias; sem "nº" vazio nem período de um dia só ----
    f = F([("02.07.2008", ENT % ("ESTABELECIMENTO PENAL DE AMAMBAI", "DP")),
           ("09.01.2013", "EMITIDO ATESTADO DE HORAS AULAS, REMIR (180) CENTO E OITENTA HORAS AULAS DA PENA.")])
    o, N = N_(R(rem(15, "26/02/2013")), f)
    d = doc(N, tipo="Atestado de estudo")
    ok(d and d["dias"] == 15 and d.get("provavel") == "26/02/2013" and not d["periodo"], "1: horas-aula: %s" % d)
    ok(N["est_comp"] == 15 and N["comp"] == 15, "1: entra na comparação: %s %s" % (N["est_comp"], N["comp"]))
    ok(not any("nº  (" in p["texto"] or "nº (" in p["texto"] for p in N["pontos"]), "1: nº vazio: %s" % [p["texto"] for p in N["pontos"]])

    # ---- 2) atestados sem período nem setor emitidos durante o mesmo trabalho, depois do atestado anterior: cobrem o trabalho do
    # intervalo (sugerido), e não "pedir atestado" / "pode ter sido remido com atestado que a ficha não registra" ----
    ev2 = [("02.07.2008", ENT % ("ESTABELECIMENTO PENAL DE AMAMBAI", "DP")), ("22.08.2012", INI % "OFICINA DE CRINA"),
           ("10.09.2013", "EMITIDO ATESTADO DE TRABALHO PRISIONAL Nº 026/2013. REMIR (109) CENTO E NOVE DIAS DA PENA."),
           ("12.03.2014", "EMITIDO ATESTADO DE TRABALHO PRISIONAL Nº 051/2014. REMIR (26) VINTE E SEIS DIAS DA PENA."),
           ("02.10.2014", "NESTA DATA FOI EMITIDO ATESTADO DE TRABALHO PRISIONAL Nº159/2014. REMIR (43) QUARENTA E TRES DIAS DE PENA."),
           ("18.11.2014", FIM % ("OFICINA DE CRINA", "Saida do Presídio"))]
    o, N = N_(R(rem(109, "09/10/2013"), rem(43, "31/10/2014")), F(ev2))
    ls = {L["at"]: L for L in N["trab"]["linhas"] if L["at"]}
    ok({"026/2013", "051/2014", "159/2014"} <= set(ls) and all(ls[k]["st"] == "provavel" for k in ("051/2014", "159/2014")),
       "2: atestados da sequência ligados: %s" % [(L["periodo"], L["at"], L["st"]) for L in N["trab"]["linhas"]])
    sem_ = sum(L["dias"] for L in N["trab"]["linhas"] if L["st"] == "sem")
    ok(sem_ < 130, "2: lacuna sem atestado reduzida: %s dias" % sem_)

    # ---- 3) base da perda (art. 127) pelo período trabalhado: a remição decidida depois da falta, por atestado de trabalho anterior a
    # ela, entra na base (sem o falso "excesso"); com ela, a falta seguinte só alcança a parte do trabalho posterior ----
    r3 = R(rem(65, "12/07/2012"), rem(15, "26/02/2013"), rem(17, "01/07/2013"), rem(109, "09/10/2013"), rem(43, "27/05/2014"),
           rem(43, "31/10/2014"), fgr("15/08/2014", "17/03/2015"), perda(37, "15/08/2014", "17/03/2015"),
           perda(12, "15/08/2014", "17/03/2015"), perda(37, "15/08/2014", "17/03/2015"))
    o, N = N_(r3, F(ev2))
    ok(not any("15/08/2014" in t and "acima de 1/3" in t for t in perdas(N)), "3: sem excesso pela data da decisão: %s" % perdas(N))
    # sem a ficha (Auditoria), a base continua pela data das decisões: 249, excesso de 3 (o teste de lei não muda)
    res, _fa, _pe = ra.perdas_por_falta(r3["_incidentes"])
    ok(res and res[0]["janela"] == 249, "3: Auditoria pela data: %s" % [x["janela"] for x in res])

    # ---- 4) atestado ainda não declarado com trabalho anterior à falta entra na base; texto diz qual ----
    ev4 = [("02.07.2018", ENT % ("PENITENCIÁRIA DE DOIS IRMÃO DO BURITI", "DP")), ("01.03.2022", INI % "PRENDEBEM"),
           ("18.06.2023", "Peticionado o Atestado de trabalho n 108/2023, no Sistema SEEU, Autos %s, função Prendebem (01/03/2022 a 18/06/2023) "
                          "totalizando 333 dias trabalhados e 111 remidos." % PROC),
           ("14.08.2024", "Peticionado o Atestado de Trabalho n 128/2024, no Sistema SEEU, Autos %s, função Prendebem (19/06/2023 a 07/06/2024) "
                          "totalizando 254 dias trabalhados e 84,66 remidos." % PROC),
           ("07.06.2024", FIM % ("PRENDEBEM", "N/C"))]
    r4 = R(rem(100, "10/11/2020"), fgr("29/01/2022", "12/07/2022"), perda(30, "29/01/2022", "12/07/2022"), rem(111, "11/10/2023"),
           fgr("28/01/2026", "12/03/2026"), perda(92, "28/01/2026", "12/03/2026"), ini="01/07/2018")
    o, N = N_(r4, F(ev4))
    t4 = [t for t in perdas(N) if "28/01/2026" in t]
    ok(t4 and "excesso de 27 dias" in t4[0] and "128/2024" in t4[0] and "ainda não declarad" in t4[0], "4: base com o 128/2024: %s" % t4)

    # ---- 5) perda em duplicidade: nenhuma remição entre a falta anterior (com perda) e esta ----
    r5 = R(rem(178, "08/09/2014"), fgr("11/08/2017"), perda(33, "11/08/2017", "26/06/2018"), fgr("02/07/2019", "23/04/2020"),
           perda(48, "02/07/2019", "23/04/2020"), ini="01/07/2008")
    its = ra._perda_remidos(r5["_incidentes"], 81)
    d5 = [i for i in its if "duplicidade" in i["titulo"] and "02/07/2019" in i["titulo"]]
    ok(d5 and d5[0]["nivel"] == "verificar" and "não há remição adquirida" in d5[0]["detalhe"], "5: duplicidade sem remição entre as faltas: %s" % its)
    ok(not any(i["nivel"] == "info" and "02/07/2019" in i["titulo"] for i in its), "5: sem 'dentro do limite' com base zero: %s" % its)
    ev5 = [("02.07.2008", ENT % ("INSTITUTO PENAL DE CAMPO GRANDE", "DP")), ("29.10.2018", INI % "ARTESANATO"),
           ("02.07.2019", FIM % ("ARTESANATO", "Foi encaminhado para a Disciplinar"))]
    o, N = N_(r5, F(ev5))
    t5 = [t for t in perdas(N) if "duplicidade" in t and "02/07/2019" in t]
    ok(t5 and "trabalho sem atestado no intervalo" in t5[0], "5: ficha: atividade no intervalo: %s" % t5)

    # ---- 6) reflexo na progressão: trabalho anterior à data-base reduz só a fração (1/6) do lapso ----
    prog = HOJE + timedelta(days=500)
    res6 = {"atestados_pendentes": [{"numero": "128/2024", "data": "14.08.2024", "periodo_inicio": "19/06/2023", "periodo_fim": "07/06/2024",
                                     "dias_trabalhados": 254, "dias_remidos": 84.66}], "unidades_f": ["Penitenciária de Dois Irmãos do Buriti"]}
    txt = rf.fundamentacao_remicao(res6, {"progressao_previsao_seeu": prog.strftime("%d/%m/%Y"), "data_base_seeu": "28/01/2026",
                                          "fracao_progressao_aplicada": "1/6"})
    esperado = (prog - timedelta(days=14)).strftime("%d/%m/%Y")
    ok("por volta de %s" % esperado in txt and "anterior à data-base (28/01/2026)" in txt, "6: reflexo pela fração: %s" % txt[-400:])
    # trabalho depois da data-base: os dias inteiros
    txt = rf.fundamentacao_remicao(res6, {"progressao_previsao_seeu": prog.strftime("%d/%m/%Y"), "data_base_seeu": "01/01/2023",
                                          "fracao_progressao_aplicada": "1/6"})
    ok("por volta de %s" % (prog - timedelta(days=84)).strftime("%d/%m/%Y") in txt, "6: depois da data-base: %s" % txt[-300:])

    # ---- 7) textos ----
    # 7a) conclusão "RSPE maior" com atestado posterior à última remição: não diz "nada a requerer"
    ev7 = [("02.07.2018", ENT % ("PENITENCIÁRIA DE DOIS IRMÃO DO BURITI", "DP")), ("09.07.2025", INI % "CONFECCAO"),
           ("07.07.2026", "EMITIDO ATESTADO DE TRABALHO Nº 182/PDIB, SETOR CONFECCAO COM 104 DIAS DE REMIÇÃO.")]
    o, N = N_(R(rem(100, "20/02/2025"), rem(46, "18/11/2025"), ini="01/07/2018"), F(ev7))
    ok("Nada a requerer" not in N["concl"] and "182/PDIB" in N["concl"], "7a: conclusão: %s" % N["concl"])
    # 7b) valor próximo (51 no RSPE, 50 no atestado) não é "mesmo valor"; a fração truncada (47 x 47,66) continua "mesmo valor"
    ev7b = [("02.07.2018", ENT % ("PENITENCIÁRIA DE DOIS IRMÃO DO BURITI", "DP")),
            ("14.07.2026", "EMITIDO ATESTADO DE TRABALHO Nº 227/PDIB COM 50 DIAS DE REMIÇÃO."),
            ("07.11.2024", "Peticionado o Atestado de trabalho n 237/2024, no Sistema SEEU, função Jardim (25/05/2024 a 07/11/2024) totalizando 143 "
                           "dias trabalhados e 47,66 remidos.")]
    o, N = N_(R(rem(51, "16/07/2026"), rem(47, "07/01/2025"), ini="01/07/2018"), F(ev7b))
    ok("valor próximo: 51 dias no RSPE, 50 no documento" in doc(N, "227/PDIB")["sit"], "7b: %s" % doc(N, "227/PDIB")["sit"])
    ok("(mesmo valor)" in doc(N, "237/2024")["sit"], "7b: fração: %s" % doc(N, "237/2024")["sit"])
    # 7c) atestado + leitura = remição (53,33 + 8 = 61): provavelmente remidos juntos
    ev7c = [("02.07.2018", ENT % ("ESTABELECIMENTO PENAL DE JARDIM", "DP")),
            ("24.05.2024", "Peticionado o Atestado de trabalho n 106/2024, no Sistema SEEU, função Jardim (21/11/2023 a 24/05/2024) totalizando 160 "
                           "dias trabalhados e 53,33 remidos.")]
    f7c = F(ev7c)
    f7c["leituras"] = [{"data": "15/05/2024", "obras": 2, "meses": ["03/2024", "04/2024"]}]
    o, N = N_(R(rem(61, "03/09/2024", "24/05/2024"), ini="01/07/2018"), f7c)
    ok(doc(N, "106/2024").get("provavel") == "03/09/2024" and doc(N, tipo="Leitura").get("provavel") == "03/09/2024"
       and "a leitura (2 obras)" in doc(N, "106/2024")["sit"], "7c: soma com a leitura: %s / %s" % (doc(N, "106/2024")["sit"], doc(N, tipo="Leitura")["sit"]))
    # 7d) "Atestado e Trabalho n 171/21": o número
    ev7d = [("02.07.2018", ENT % ("PENITENCIÁRIA DE DOIS IRMÃO DO BURITI", "DP")),
            ("18.08.2021", "Peticionado Atestado e Trabalho n 171/21, no Sistema SEEU, função Faxina (30/04/2021 a 18/08/2021) totalizando 95 "
                           "dias trabalhados e 31,66 remidos.")]
    o, N = N_(R(ini="01/07/2018"), F(ev7d))
    ok(doc(N, "171/21"), "7d: número: %s" % [d["num"] for d in N["docs"]])
    # 7e) unidade do atestado: a do trabalho (período), não a da emissão; ofício à unidade atual (última entrada, ainda que já visitada)
    ev7e = [("02.07.2018", ENT % ("PENITENCIÁRIA DE DOIS IRMÃO DO BURITI", "DP")),
            ("05.01.2021", ENT % ("ESTABELECIMENTO PENAL DE AQUIDAUANA", "PDIB")), ("06.01.2021", INI % "FAXINA"),
            ("10.08.2021", FIM % ("FAXINA", "Saida do Presídio")),
            ("10.08.2021", ENT % ("PENITENCIÁRIA DE DOIS IRMÃO DO BURITI", "EPA")),
            ("14.10.2021", "EMITIDO ATESTADO DE TRABALHO 743/2021/ST/EPA PARA OS AUTOS: %s 06/01/2021 À 09/08/2021 NA CELA, COMPUTADOS 180 "
                           "DIAS TRABALHADOS E 60 DIAS REMIDOS." % PROC)]
    o, N = N_(R(ini="01/07/2018"), F(ev7e))
    d7e = next((d for d in N["docs"] if d["num"].startswith("743")), None)
    ok(d7e and "Aquidauana" in d7e.get("un", ""), "7e: unidade do atestado: %s" % (d7e and d7e.get("un")))
    ok("unidade Penitenciária de Dois Irmãos do Buriti para que" in (o.get("fd_fund") or ""), "7e: ofício à unidade atual: %s" % (o.get("fd_fund") or "")[-900:])
except Exception as e:  # noqa
    import traceback
    traceback.print_exc()
    falhas.append("exceção: %s" % e)

if falhas:
    print("FALHOU teste_conf6_remicao:\n - " + "\n - ".join(falhas))
    sys.exit(1)
print("ok: conferência 7.14.4, remição (horas-aula, atestados sem período da sequência, base do art. 127 pelo período, atestado não "
      "declarado, duplicidade sem remição entre as faltas, reflexo pela fração, textos e unidades)")
