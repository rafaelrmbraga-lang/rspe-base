"""Remição 7.14, segunda rodada (análises manuais de remição): "provavelmente remido" por valor e data (só indicação), cinza quando o
RSPE é maior que a ficha, atestado sem período com o período implícito, todo o trabalho sem atestado avaliado, ordem de "Onde",
acompanhar o trabalho em curso, estudo depois do último semestre certificado, corte na última remição sem documento, leitura remida a
menor, setor educacional fora do trabalho, dias implausíveis, peticionamento do exame e aviso de RSPE de outra execução. Dados fictícios
(sem nomes). Rodar: python teste_remicao_714b.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf
import rspe_remicao as rrm
from teste_remicao_714 import R, T, A, F, HOJE

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def comp(r, f, **kw):
    o = rf.comparativo(r, f, HOJE, **kw)
    return o, o["fd_novo"]


def doc(N, num):
    return next(d for d in N["docs"] if d["num"] == num)


def tipos(N):
    return {p["tipo"]: p for p in N["pontos"]}


try:
    # ---- B) provavelmente remido: remição do mesmo valor (até 1 dia) decidida de 0 a 180 dias depois da emissão; cada remição serve a
    # um atestado só (o primeiro por data); só indicação: sem vínculo, sem mudar os totais, sem ✓ ----
    f = F([T("MARCENARIA", "01.03.2024", "30.06.2024")],
          [A("070/2024", "05.07.2024", "01/03/2024", "30/04/2024", 20, 60, "Marcenaria"),
           A("071/2024", "05.08.2024", "01/05/2024", "30/06/2024", 20, 60, "Marcenaria")])
    o, N = comp(R((20.5, "20/09/2024", None)), f)
    d70, d71 = doc(N, "070/2024"), doc(N, "071/2024")
    ok(d70["sit"] == "Provavelmente remido em 20/09/2024 (mesmo valor): conferir" and d70["cor"] == "cinza" and not d70["hom"],
       "B: provavelmente remido: %s" % d70["sit"])
    ok(d71["sit"] == "Sem registro de peticionamento", "B: a remição serve a um atestado só: %s" % d71["sit"])
    ok(N["comp"] == 40 and N["dif"] == 19.5, "B: os totais não mudam: %s %s" % (N["comp"], N["dif"]))
    ok("070/2024" in tipos(N)["provavel_remido"]["texto"] and "070/2024" not in tipos(N)["sem_pet"]["texto"]
       and not any("070/2024" in x["t"] for x in N["onde"]) and any("071/2024" in x["t"] for x in N["onde"]),
       "B: o provável sai do alarme e de Onde: %s" % N["onde"])
    o, N = comp(R((20, "01/03/2025", None)), f)  # decidida mais de 180 dias depois: sem indicação
    ok(doc(N, "070/2024")["sit"] == doc(N, "071/2024")["sit"] == "Sem registro de peticionamento", "B: fora de 180 dias não indica")

    # ---- A2) RSPE maior que a ficha: o amarelo vira cinza, salvo o pedido de atestado (depois da última remição) e o vermelho ----
    f = F([T("MARCENARIA", "01.02.2024", "30.06.2024"), T("COPA", "01.02.2025", "")],
          cursos_peticionados=[{"data": "01.02.2025", "texto": "PETICIONADO CURSO DE QUALIFICAÇÃO", "meses": ["10/2024"], "autos": ""}])
    o, N = comp(R((60, "01/08/2024", "30/06/2024")), f)
    tp = tipos(N)
    ok(N["rspe_maior"] and tp["talvez_remido"]["cor"] == "cinza" and tp["sem_valor"]["cor"] == "cinza" and tp["pedir_atestado"]["cor"] == "amarelo",
       "A2: cores dos pontos: %s" % {k: v["cor"] for k, v in tp.items()})
    ok(o["fd_cor"] == "amarelo" and o["fd_sit"] == "Pedir atestado"
       and [x["c"] for x in N["onde"] if x["t"].startswith("Pedir atestado: trabalho em Copa")] == ["amarelo"]
       and all(x["c"] == "cinza" for x in N["onde"] if not x["t"].startswith("Pedir atestado")), "A2: só o pedido fica amarelo: %s %s" % (o["fd_sit"], N["onde"]))
    ok(any(L["sit"] == "Sem atestado" and L["cor"] == "cinza" for L in o["fd_linhas"]) and any(L["cor"] == "amarelo" for L in o["fd_linhas"]),
       "A2: linhas de trabalho: %s" % [(L["emp"], L["cor"]) for L in o["fd_linhas"]])
    o, N = comp(R((60, "01/08/2024", "30/06/2024")), F([T("MARCENARIA", "01.02.2024", "30.06.2024")]))
    ok(o["fd_cor"] == "cinza" and o["fd_sit"] == "Conferir (informativo)" and all(x["c"] == "cinza" for x in N["onde"]),
       "A2: só cinza: %s %s %s" % (o["fd_cor"], o["fd_sit"], N["onde"]))
    f = F([T("COPA", "01.02.2025", "31.08.2025")], [A("080/2025", "01.09.2025", "01/02/2025", "31/08/2025", 30, 90, "Copa")])
    o, N = comp(R((60, "01/08/2024", "30/06/2024")), f)
    ok(N["rspe_maior"] and o["fd_cor"] == "vermelho" and doc(N, "080/2025")["cor"] == "vermelho" and N["onde"][0]["c"] == "vermelho",
       "A2: o vermelho fica: %s %s" % (o["fd_cor"], N["onde"]))

    # ---- E2) atestado sem período: setores separados por "E", grafia variante; o que só nomeia o setor final cobre o anterior ----
    f = F([T("PAIVA LINGERIE", "01.03.2025", "30.06.2025")], [A("090/PDIB", "05.07.2025", rem=34, empresa="PRENDE BEM E PAIVA LANGERIE")])
    L = rrm.trabalho_x_atestados(f, HOJE, None, None, date(2020, 1, 1))["linhas"]
    ok([(x["st"], x["at"]) for x in L] == [("provavel", "090/PDIB")], "E2: grafia e vários setores: %s" % [(x["local"], x["st"], x["at"]) for x in L])
    wd = rrm._dias_seg_sab(date(2025, 9, 1), date(2025, 10, 20)) + rrm._dias_seg_sab(date(2025, 10, 21), date(2026, 1, 30))
    f = F([T("MANUTENCAO PREDIAL", "01.09.2025", "20.10.2025"), T("PRENDEBEM", "21.10.2025", "30.01.2026")],
          [A("226/PDIB", "02.02.2026", rem=round(wd / 3.0), empresa="PRENDE BEM")])
    T_ = rrm.trabalho_x_atestados(f, HOJE, None, None, date(2020, 1, 1))
    ok([(x["st"], x["at"]) for x in T_["linhas"]] == [("provavel", "226/PDIB")] * 2 and T_["inferidos"]["fd:at:226/PDIB:02.02.2026"]["ini"] == date(2025, 9, 1),
       "E2: só o setor final nomeado, os dias batem com os dois: %s" % [(x["local"], x["st"], x["at"]) for x in T_["linhas"]])

    # ---- E3, E4, E12) todo trabalho sem atestado é avaliado; "Pedir atestado" do mais recente ao mais antigo, com o trecho estimado
    # (a Cozinha começa antes da execução: o trecho estimado começa no primeiro dia útil dela, 02/01/2020) ----
    f = F([T("COZINHA", "01.10.2019", "30.04.2020"), T("MARCENARIA", "01.06.2024", "31.12.2024"), T("COPA", "01.02.2025", "30.04.2025")],
          [A("100/2025", "05.01.2025", "01/06/2024", "31/12/2024", 60, 180, "Marcenaria")], [("05.01.2025", "PETICIONADO ATESTADO DE TRABALHO Nº 100/2025")])
    o, N = comp(R((60, "01/02/2025", "31/12/2024")), f)
    ped = [x["t"] for x in N["onde"] if x["t"].startswith("Pedir atestado")]
    ok(len(ped) == 2 and "Copa de 01/02/2025" in ped[0] and "Cozinha de 02/01/2020 a 30/04/2020" in ped[1],
       "E3/E4/E12: pedir do mais recente, desde o início da execução: %s" % N["onde"])
    ok(any(i["t"].startswith("Pedir atestado (≈") and i["c"] == "amarelo" for i in o["fd_sit_itens"]), "E4: pedir atestado na situação: %s" % o["fd_sit_itens"])

    # ---- E6) estimativa de estudo só depois do último semestre certificado ----
    f = F(estudos=[{"inicio": "01.02.2025", "fim": "", "curso": "EJA", "ult_registro_edu": "01.09.2026"}],
          certidoes_estudo=[{"data": "10.08.2025", "semestre": 1, "ano": 2025, "horas": 400, "texto": "PETICIONADO CERTIDÃO DE FREQUÊNCIA", "autos": ""}])
    o, N = comp(R(), f)
    ok(N["est_estim"] and N["est_estim"][0]["txt"].startswith("Eja, 01/07/2025 a"), "E6: estudo depois do semestre certificado: %s" % N["est_estim"])

    # ---- E8 e E9) corte na última remição sem documento (a de leitura casada não conta); leitura remida a menor ----
    f = F([T("MARCENARIA", "01.06.2024", "31.12.2024"), T("COPA", "01.01.2025", "31.05.2025")],
          [A("120/2025", "05.01.2025", "01/06/2024", "31/12/2024", 60, 180, "Marcenaria")], [("05.01.2025", "PETICIONADO ATESTADO DE TRABALHO Nº 120/2025")],
          leituras=[{"data": "15.05.2025", "obras": 2, "texto": "PETICIONADO RELATÓRIO DE LEITURA"},
                    {"data": "01.07.2025", "obras": 5, "texto": "PETICIONADO RELATÓRIO DE LEITURA"}])
    o, N = comp(R((60, "01/02/2025", None), (30, "01/03/2025", None), (8, "01/06/2025", None), (12, "01/08/2025", None)), f)
    L = next(x for x in N["trab"]["linhas"] if x["local"] == "Copa")
    ok(N["corte"] == date(2025, 3, 1) and L["talvez_fim"] <= date(2025, 3, 1) and L["pedir_ini"] > date(2025, 3, 1),
       "E8: corte na remição sem documento: %s %s" % (N["corte"], {k: L.get(k) for k in ("talvez_fim", "pedir_ini")}))
    tp = tipos(N)
    ok("leitura_menor" in tp and "20 dias" in tp["leitura_menor"]["texto"] and "12 dias" in tp["leitura_menor"]["texto"] and tp["leitura_menor"]["cor"] == "cinza"
       and doc(N, "5 obras")["sit"].startswith("Remida a menor?"), "E9: leitura remida a menor: %s" % list(tp))

    # ---- E10, E11, E1) setor educacional não é trabalho; dias implausíveis; peticionamento do exame pelo lançamento do dia ----
    f = F([T("SETOR EDUCACIONAL", "01.02.2025", ""), T("COPA", "01.06.2025", "30.06.2025")],
          [A("110/2025", "01.07.2025", "01/06/2025", "30/06/2025", 30, 0, "Copa")],
          [("01.07.2025", "PETICIONADO ATESTADO DE TRABALHO Nº 110/2025"), ("20.02.2026", "PETICIONADO CERTIFICADO DO ENEM 2025 NO SISTEMA SEEU")],
          exames=[{"exame": "ENEM 2025", "data": "20.02.2026", "certificado": False, "autos": ""}])
    o, N = comp(R(), f)
    ok([x["local"] for x in N["trab"]["linhas"]] == ["Copa"], "E10: setor educacional: %s" % [x["local"] for x in N["trab"]["linhas"]])
    tp = tipos(N)
    ok("implausivel" in tp and "110/2025" in tp["implausivel"]["texto"] and tp["implausivel"]["cor"] == "cinza", "E11: dias implausíveis: %s" % list(tp))
    ok(doc(N, "ENEM 2025")["pet"] == "peticionado em 20/02/2026", "E1: exame peticionado: %s" % doc(N, "ENEM 2025")["pet"])

    # ---- RSPE de outra execução: tribunal de outro estado, ou a ficha só cita processos de outro tribunal ----
    f = F([T("COPA", "01.06.2025", "30.06.2025")])
    r = R(); r["vara"] = "TJMG - TIMOTEO - EXECUCAO PENAL - REGIME ABERTO"
    o, N = comp(r, f)
    ok("TJMG" in N["outra_exec"] and o["fd_sit_itens"] and "outra execução" in o["fd_sit_itens"][0]["t"], "aviso: outro tribunal: %s" % o["fd_sit_itens"])
    r = R(); r["vara"] = "TJMS - 1ª VARA DE EXECUÇÃO DO INTERIOR"
    ok(not comp(r, f)[1]["outra_exec"], "aviso: TJMS não avisa")
    f2 = dict(f, autos=["4400497-40.2021.8.13.0313"])
    ok("não cita nenhum dos processos" in comp(R(), f2)[1]["outra_exec"], "aviso: a ficha só cita processo de outro tribunal")
    f3 = dict(f, autos=["0043455-75.2018.8.12.0001"])
    ok(not comp(R(), f3)[1]["outra_exec"], "aviso: processo do mesmo tribunal não avisa")
except Exception:
    import traceback
    traceback.print_exc()
    falhas.append("exceção")

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for x in falhas:
        print(" -", x)
    sys.exit(1)
print("ok: remição 7.14, segunda rodada (provavelmente remido, cinza com RSPE maior, atestado sem período, onde, estudo, leitura, aviso de outra execução)")
