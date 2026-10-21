"""Conferência 7.14.2, frente remição (grupos R1 a R11): saldo de remição sem documento (soma de atestados, atestado sem
peticionamento apreciado mais tarde, cobertura do trabalho mais próximo para o mais antigo e o resto a pedir), fundamentação com a
mesma lista da tela, atestado contido em outro, remição no período do atestado a pedir, ligação de exame e certidão pela referência,
leitura da ficha (isolamento, saída temporária, setores no mesmo dia, ano digitado errado, estudo com datas invertidas), trabalho
na execução interrompida, atestado sem período que só fecha com o trecho anterior, atestado dirigido a outros autos, frase do RSPE
maior e ficha sem documentos. Dados fictícios (sem nomes). Rodar: python teste_conf3_remicao.py"""
import sys
import types
from datetime import date, timedelta

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf
import rspe_remicao as rrm

falhas = []
HOJE = date(2026, 10, 20)
PROC = "0000001-11.2018.8.12.0001"
EV = [{"data": "01/03/2014", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}]


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def R(*rem, eventos=None):
    """RSPE mínimo: prisão em 2014 e remições [(dias, decisão, referência)]."""
    return {"processo_execucao": PROC, "_crimes": [], "_eventos": eventos or EV,
            "_incidentes": [{"tipo": "REMIÇÃO", "complemento": "%s Dia(s)" % d, "data_decisao": dec, "data_referencia": ref or dec,
                             "situacao": "CONCEDIDO"} for d, dec, ref in rem]}


def T(setor, ini, fim=""):
    return {"setor": setor, "inicio": ini, "fim": fim, "externo": False}


def A(num, data, ini="", fim="", rem=0, trab=0, empresa="", trechos=None, autos=""):
    return {"numero": num, "data": data, "periodo_inicio": ini, "periodo_fim": fim, "dias_remidos": rem, "dias_trabalhados": trab,
            "empresa": empresa, "autos": autos, "trechos": trechos or []}


def F(trabalho=(), atestados=(), eventos=(), **kw):
    f = {"data_impressao": "15.10.2026", "trabalho": list(trabalho), "atestados": list(atestados),
         "eventos": [{"data": d, "texto": t} for d, t in eventos], "leituras": [], "exames": [], "cursos_peticionados": [],
         "certidoes_estudo": [], "estudos": [], "faltas": []}
    f.update(kw)
    return f


def comp(r, f):
    o = rf.comparativo(r, f, HOJE)
    return o, o["fd_novo"]


def linha(N, local):
    return next(L for L in N["trab"]["linhas"] if L["local"].startswith(local))


def doc(N, num):
    return next(d for d in N["docs"] if d["num"] == num)


def tipos(N):
    return {p["tipo"]: p for p in N["pontos"]}


def seg_sab(a, b):
    return sum(1 for i in range((b - a).days + 1) if (a + timedelta(days=i)).weekday() != 6)


try:
    # ---- R1) saldo sem documento: só a remição que nenhum documento explica cobre trabalho sem atestado, do trabalho mais próximo
    # da referência para o mais antigo; o que não couber é "pedir atestado" (e a fundamentação lista só esse) ----
    f = F([T("LAVOURA", "01.02.2021", "30.06.2021"), T("CANTINA", "02.05.2023", "30.06.2023"), T("COZINHA", "01.07.2023", "31.12.2023")],
          [A("050/2024", "05.01.2024", "01/07/2023", "31/12/2023", 50, 150, "Cozinha")], [("05.01.2024", "PETICIONADO ATESTADO DE TRABALHO Nº 050/2024")])
    o, N = comp(R((50, "01/02/2024", None), (17, "10/07/2023", "10/07/2023")), f)
    can, lav = linha(N, "Cantina"), linha(N, "Lavoura")
    ok(can.get("talvez_dias") and not can.get("pedir_dias"), "R1: Cantina coberta pelo saldo de 17 dias: %s" % {k: can.get(k) for k in ("talvez_dias", "pedir_dias")})
    ok(lav.get("pedir_dias") and not lav.get("talvez_dias"), "R1: Lavoura (mais antiga) fora do saldo, pedir: %s" % {k: lav.get(k) for k in ("talvez_dias", "pedir_dias")})
    ok("talvez_remido" in tipos(N) and "17 dias de 10/07/2023" in tipos(N)["talvez_remido"]["texto"], "R1: ponto do saldo: %s" % tipos(N).get("talvez_remido"))
    fu = o["fd_fund"]
    ok("Lavoura, 01/02/2021 a 30/06/2021" in fu and "Cantina" not in fu, "R2: fundamentação com a mesma lista da tela: %s" % fu[:400])
    # saldo maior que o trabalho mais próximo: segue para o mais antigo, que fica parte coberto e parte a pedir (trechos separados)
    o, N = comp(R((50, "01/02/2024", None), (30, "10/07/2023", "10/07/2023")), f)
    lav = linha(N, "Lavoura")
    ok(lav.get("talvez_dias") and lav.get("pedir_dias") and lav["talvez_ini"] > lav["pedir_fim"],
       "R1: o mais antigo cobre a partir do fim: %s" % {k: lav.get(k) for k in ("talvez_ini", "talvez_fim", "pedir_ini", "pedir_fim")})

    # ---- R1) remição explicada pela soma de dois atestados (um sem registro de peticionamento): nenhum saldo; o trabalho sem atestado
    # anterior é "pedir atestado", não "pode já estar remido" ----
    f = F([T("MANUTENCAO", "14.02.2016", "17.05.2016"), T("FAXINA", "01.03.2023", "31.12.2023"), T("HORTA", "01.01.2024", "31.03.2024")],
          [A("060/2024", "05.04.2024", "01/03/2023", "31/12/2023", 89.33, 268, "Faxina"), A("061/2024", "05.04.2024", "01/01/2024", "31/03/2024", 26, 78, "Horta")],
          [("05.04.2024", "PETICIONADO ATESTADO DE TRABALHO Nº 060/2024")])
    o, N = comp(R((115, "20/04/2024", "31/03/2024")), f)
    ok("soma com o nº 060/2024" in doc(N, "061/2024")["sit"] and "soma com o nº 061/2024" in doc(N, "060/2024")["sit"],
       "R1: soma de dois atestados: %s / %s" % (doc(N, "060/2024")["sit"], doc(N, "061/2024")["sit"]))
    m_ = linha(N, "Manutencao")
    ok(m_.get("pedir_dias") and not m_.get("talvez_dias") and "talvez_remido" not in tipos(N), "R1: sem saldo, pedir: %s" % m_)

    # ---- R1) atestado sem registro de peticionamento apreciado mais de 180 dias depois (mesmo valor): explica a remição ----
    f = F([T("COSTURA", "06.07.2022", "07.10.2022"), T("FAXINA", "10.04.2023", "05.05.2023")], [A("052/2022", "23.11.2022", "06/07/2022", "07/10/2022", 26, 78, "Costura")])
    o, N = comp(R((26, "01/03/2024", None)), f)
    ok(doc(N, "052/2022")["sit"].startswith("Provavelmente remido em 01/03/2024") and linha(N, "Faxina").get("pedir_dias")
       and not linha(N, "Faxina").get("talvez_dias"), "R1: atestado apreciado mais tarde: %s %s" % (doc(N, "052/2022")["sit"], linha(N, "Faxina")))

    # ---- R3) atestado contido em outro (o mesmo período em trechos do segundo): não se soma ----
    f = F([T("PRENDEBEM", "22.03.2022", "01.02.2023")],
          [A("275/2022", "09.09.2022", "22/03/2022", "05/07/2022", 30, 90, "Prendebem"),
           A("051/2023", "01.02.2023", "22/03/2022", "01/02/2023", 70, 210, "Prendebem",
             trechos=[{"setor": "Prendebem", "inicio": "22/03/2022", "fim": "05/07/2022"}, {"setor": "Prendebem", "inicio": "15/09/2022", "fim": "01/02/2023"}])])
    o, N = comp(R((100, "01/03/2023", None)), f)
    ok(N["comp"] == 70 and doc(N, "275/2022")["sit"].startswith("Contido no atestado nº 051/2023") and "contido" in tipos(N),
       "R3: contido não se soma: %s %s" % (N["comp"], doc(N, "275/2022")["sit"]))
    # atestado cumulativo (repete dois outros): sai do total
    f = F([T("PEDREIRO", "01.01.2018", "31.12.2021")],
          [A("100/2020", "01.01.2020", "01/01/2018", "31/12/2019", 200, 600), A("200/2022", "05.01.2022", "01/01/2018", "31/12/2021", 400, 1200),
           A("101/2022", "02.01.2022", "01/01/2020", "31/12/2021", 200, 600)])
    o, N = comp(R((200, "01/02/2020", None), (200, "01/03/2022", None)), f)
    ok(N["comp"] == 400 and "Contido nos atestados nº 100/2020 e nº 101/2022" in doc(N, "200/2022")["sit"], "R3: cumulativo: %s %s" % (N["comp"], doc(N, "200/2022")["sit"]))

    # ---- R4) remição sem documento com referência dentro do período do atestado ainda sem decisão: pede-se só a diferença ----
    f = F([T("FAXINA", "17.08.2018", "18.01.2025")], [A("005/2026", "17.01.2026", "17/08/2018", "18/01/2025", 244, 732, "Faxina")],
          [("17.01.2026", "PETICIONADO ATESTADO DE TRABALHO Nº 005/2026")])
    o, N = comp(R((87, "19/07/2019", None)), f)
    d_ = doc(N, "005/2026")
    ok(d_["sit"].startswith("Pedir ≈ 157 (244 − 87): conferir a remição de 19/07/2019") and d_["cor"] != "vermelho", "R4: %s" % d_["sit"])
    ok("declaração da remição de 157 dias" in o["fd_fund"] and "conferir a decisão antes de requerer" in o["fd_fund"], "R4: fundamentação: %s" % o["fd_fund"][:600])
    ok(N["fatos_dias"] == 157, "R4: fatos pendentes com a diferença: %s" % N["fatos_dias"])

    # ---- R5) exame: a remição com referência anterior à prova não é dele; certidão: a remição pequena (1 dia) do semestre curto ----
    f = F(exames=[{"exame": "ENEM 2024", "data": "11.04.2025", "certificado": False, "texto": "PETICIONADO CERTIFICADO DO ENEM 2024"}])
    o, N = comp(R((26, "14/08/2025", "31/07/2023"), (32, "21/08/2025", "17/08/2025")), f)
    ok(doc(N, "ENEM 2024")["sit"].startswith("Possivelmente remido em 21/08/2025 (32 dias)"), "R5a: %s" % doc(N, "ENEM 2024")["sit"])
    f = F(certidoes_estudo=[{"data": "18.11.2025", "semestre": 1, "ano": 2025, "horas": 0, "texto": "PETICIONADA CERTIDÃO DE FREQUÊNCIA", "autos": ""},
                            {"data": "05.03.2026", "semestre": 2, "ano": 2025, "horas": 0, "texto": "PETICIONADA CERTIDÃO DE FREQUÊNCIA", "autos": ""}])
    o, N = comp(R((1, "24/11/2025", "31/07/2025"), (25, "12/03/2026", "22/12/2025")), f)
    c1, c2 = doc(N, "1º semestre de 2025"), doc(N, "2º semestre de 2025")
    ok(c1["sit"].startswith("Possivelmente remido em 24/11/2025 (1 dias)") and c2["sit"].startswith("Possivelmente remido em 12/03/2026 (25 dias)"),
       "R5c: %s / %s" % (c1["sit"], c2["sit"]))
    # ENCCEJA: o valor da tabela do CNJ (100) antes de outro (50), e o atestado com o valor exato (50) fica com a sua remição
    f = F([], [A("255/2023", "23.10.2023", "02/05/2023", "23/10/2023", 50, 150)],
          exames=[{"exame": "ENCCEJA 2024", "data": "02.05.2025", "certificado": False, "texto": "PETICIONADO CERTIFICADO DO ENCCEJA 2024"}])
    o, N = comp(R((100, "23/05/2025", "31/12/2024"), (50, "23/05/2025", "19/04/2025")), f)
    ok(doc(N, "255/2023")["sit"].startswith("Provavelmente remido em 23/05/2025 (mesmo valor)") and "(100 dias)" in doc(N, "ENCCEJA 2024")["sit"],
       "R5b: %s / %s" % (doc(N, "255/2023")["sit"], doc(N, "ENCCEJA 2024")["sit"]))

    # ---- R6) isolamento e saída temporária registrados na ficha não contam como dia trabalhado ----
    f = F([T("PRENDEBEM", "14.03.2025", "19.03.2025")], eventos=[
        ("18.03.2025", "CONSELHO DISCIPLINAR: ISOLADO PREVENTIVAMENTE EM CELA DISCIPLINAR, POR 10 DIAS, REFERENTE A FALTA DISCIPLINAR COMETIDA EM 18/03/2025.")])
    o, N = comp(R(), f)
    ok(linha(N, "Prendebem")["pedir_dias"] == 1.0, "R6: isolamento descontado: %s" % linha(N, "Prendebem").get("pedir_dias"))
    f = F([T("PARQUE", "30.08.2021", "11.09.2021")], eventos=[
        ("31.08.2021", "CONFORME DETERMINAÇÃO JUDICIAL, FOI BENEFICIADO COM SAÍDA TEMPORÁRIA PELO PRAZO DE 7 (SETE) DIAS DEVENDO RETORNAR A ESTA UNIDADE PENAL NA DATA 06/09/2021.")])
    o, N = comp(R(), f)
    esp = rf.dias_jornada_set(date(2021, 8, 30), date(2021, 9, 11)) - {date(2021, 8, 31) + timedelta(days=i) for i in range(6)}
    ok(linha(N, "Parque")["pedir_dias"] == round(len(esp) / 3.0, 2), "R6: saída temporária descontada: %s × %s" % (linha(N, "Parque").get("pedir_dias"), len(esp)))
    # dois setores iniciados no mesmo dia: a baixa só do segundo não encerra o primeiro (só é duplicado o mesmo setor)
    f2 = rf.atualizar({"versao_leitura": 0, "data_impressao": "02.10.2026", "eventos": [
        {"data": "01.04.2026", "texto": "TRABALHO: Iniciou atividade laboral, no setor de trabalho POLIGONAL ENGENHARIA LTDA, conforme documento N/C."},
        {"data": "01.04.2026", "texto": "TRABALHO: Iniciou atividade laboral, no setor de trabalho SERRALHERIA, conforme documento N/C."},
        {"data": "19.06.2026", "texto": "TRABALHO: Deixa de trabalhar, no setor de trabalho SERRALHERIA, conforme documento N/C, motivo: REMANEJAMENTO."}]})
    tr = [(t["setor"], t["inicio"], t.get("fim") or "") for t in f2["trabalho"]]
    ok(("POLIGONAL ENGENHARIA LTDA", "01.04.2026", "") in tr and ("SERRALHERIA", "01.04.2026", "19.06.2026") in tr, "R6: setores no mesmo dia: %s" % tr)
    # ano digitado errado no trecho do atestado (início 01/07/2023, fim 05/10/2022): lido com o ano corrigido
    f3 = rf.atualizar({"versao_leitura": 0, "data_impressao": "02.10.2026", "eventos": [
        {"data": "01.07.2022", "texto": "TRABALHO: Iniciou atividade laboral, no setor de trabalho COZINHA, conforme documento N/C."},
        {"data": "05.10.2022", "texto": "TRABALHO: Deixa de trabalhar, no setor de trabalho COZINHA, conforme documento N/C, motivo: TROCA DE SETOR."},
        {"data": "26.12.2022", "texto": "TRABALHO: Iniciou atividade laboral, no setor de trabalho OLARIA, conforme documento N/C."},
        {"data": "15.07.2023", "texto": "ATESTADO DE TRABALHO PRISIONAL - Nesta data foi PROTOCOLADO o Atestado de Trabalho Prisional n°190/2023 . Data Inicial "
                                        "01/07/2023 até Data Final 05/10/2022 no SETOR DE COZINHA e Data Inicial 26/12/2022 até Data Final 15/07/2023 no SETOR DE "
                                        "OLARIA, no qual consta um total de 250 dias trabalhados, visto que o tempo de REMIÇÃO totalizou 83,3 dias."}]})
    a_ = next(a for a in f3["atestados"] if a["numero"].startswith("190"))
    ok(a_["periodo_inicio"] == "01/07/2022" and "lido como 01/07/2022 a 05/10/2022" in a_.get("ano_corrigido", ""), "R6: ano corrigido: %s" % a_)
    o, N = comp(R((83.3, "29/08/2023", None)), f3)
    ok("ano corrigido" in doc(N, a_["numero"])["sit"] and linha(N, "Cozinha")["st"] == "auto", "R6: ano corrigido na tela: %s" % doc(N, a_["numero"])["sit"])
    # atestado de estudo com as datas invertidas: continua na tela, com "conferir datas"
    f = F(estudos=[{"inicio": "27.04.2015", "fim": "10.02.2015", "curso": "Atestado de estudo nº 028/2016", "horas": 75, "livre": True}])
    o, N = comp(R(), f)
    ok(any("conferir datas" in x["txt"] and x["txt"].startswith("Atestado de estudo nº 028/2016, 10/02/2015 a 27/04/2015") for x in N["est_estim"]),
       "R6: estudo com datas invertidas: %s" % N["est_estim"])

    # ---- R7) trabalho em período em que esta execução estava interrompida (liberdade provisória): à parte, fora da estimativa ----
    ev7 = EV + [{"data": "20/02/2016", "tipo": "INTERRUPÇÃO", "motivo": "LIBERDADE PROVISÓRIA"}, {"data": "04/07/2018", "tipo": "PRISÃO", "motivo": "PRISÃO"}]
    f = F([T("BLOCOBRAS", "18.10.2016", "24.10.2016"), T("ARTESANATO", "01.08.2018", "31.08.2018")])
    orig_fu = rrm.fora_da_unidade
    rrm.fora_da_unidade = lambda *a, **k: []  # a ficha mostra a pessoa numa unidade (outra custódia): o corte de custódia não alcança
    try:
        o, N = comp(R(eventos=ev7), f)
    finally:
        rrm.fora_da_unidade = orig_fu
    ok(not linha(N, "Blocobras").get("pedir_dias") and not linha(N, "Blocobras").get("talvez_dias") and "trabalho_aparte" in tipos(N)
       and linha(N, "Artesanato").get("pedir_dias"), "R7: à parte: %s" % [p["texto"] for p in N["pontos"]])

    # ---- R8) atestado sem período que só fecha com o trecho anterior (separado por mais de 30 dias): o trecho é sugerido ----
    x0, x1, y0, y1 = date(2015, 1, 31), date(2015, 2, 20), date(2015, 5, 5), date(2015, 12, 31)
    rem8 = round((seg_sab(x0, x1) + seg_sab(y0, y1)) / 3.0, 2)
    f = F([T("OFICINA", "01.07.2014", "20.02.2015"), T("MANDIOCA", "05.05.2015", "31.12.2015")],
          [A("001/2015", "30.01.2015", "01/07/2014", "30/01/2015", 60, 180, "Oficina"), A("002/2016", "10.01.2016", rem=rem8)])
    L8 = rrm.trabalho_x_atestados(f, HOJE, None, None, date(2014, 3, 1))["linhas"]
    ok([(L["local"], L["periodo"], L["st"], L["at"]) for L in L8 if L["local"] == "Oficina" and L["ini"] == x0] == [("Oficina", "31/01/2015 a 20/02/2015", "provavel", "002/2016")],
       "R8: trecho anterior sugerido: %s" % [(L["local"], L["periodo"], L["st"], L["at"]) for L in L8])

    # ---- R9) atestado "dirigido a outros autos" com remição do mesmo valor nesta execução, referência na data do atestado ----
    f = F([T("PAIVA", "24.02.2023", "28.02.2024")], [A("034/2024", "28.02.2024", "24/02/2023", "28/02/2024", 87.99, 264, "Paiva", autos="0000002-22.2019.8.12.0001")])
    o, N = comp(R((88, "28/05/2024", "28/02/2024")), f)
    ok(not doc(N, "034/2024")["fora"] and "a ficha cita outros autos" in doc(N, "034/2024")["sit"] and N["comp"] == 87.99, "R9: %s" % doc(N, "034/2024")["sit"])

    # ---- R10) RSPE maior: documentos fora da ficha ou sem valor na ficha, com os sem valor listados ----
    f = F(exames=[{"exame": "ENCCEJA 2025", "data": "20.03.2026", "certificado": False, "texto": "PETICIONADO CERTIFICADO DO ENCCEJA 2025"}])
    o, N = comp(R((167, "01/02/2026", None)), f)
    ok("documentos fora da ficha ou sem valor na ficha" in N["concl"] and "na ficha, sem valor: Exame · ENCCEJA 2025 (20/03/2026)" in N["concl"], "R10: %s" % N["concl"])

    # ---- R11) ficha sem documentos e RSPE com remição: nunca "Em ordem" ----
    o, N = comp(R((124, "07/03/2022", None), (56, "14/02/2023", None)), F())
    ok(o["fd_sit"] == "RSPE maior que a ficha (180 × 0)" and o["fd_cor"] == "cinza" and N["onde"][0]["t"].startswith("RSPE maior que a ficha em 180 dias"),
       "R11: %s %s %s" % (o["fd_sit"], o["fd_cor"], N["onde"]))
except Exception as e:
    import traceback
    traceback.print_exc()
    falhas.append("exceção: %r" % e)

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for x in falhas:
        print(" -", x)
    sys.exit(1)
print("ok: conferência 7.14.2, remição (saldo sem documento, fundamentação, contido, remição no período, exame e certidão, leitura da ficha, "
      "execução interrompida, atestado sem período, outros autos, RSPE maior, ficha sem documentos)")
