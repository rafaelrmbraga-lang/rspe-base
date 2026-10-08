"""Teste de regressão do indicador de saída temporária (aba Geral, ícone ao lado do nome): regime e unidade de semiaberto, fato
anterior à Lei 14.843/2024 (crime posterior não impede), hediondo com resultado morte, 1/6 ou 1/4 da pena, conduta e falta,
trabalho (externo conta), 45 dias do retorno (sem retorno: 7 dias da saída), ficha com mais de 90 dias e limite anual em amarelo.
Rodar: python teste_saida_temporaria.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_view as rv

HOJE = date(2026, 10, 8)
falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def crime(data, hed="N", morte="N", vga="N", ext="Não"):
    return {"data_infracao": data, "hediondo_ou_equiparado": hed, "resultado_morte": morte, "vga": vga, "extinto": ext,
            "tipo_processo": "ACAO PENAL", "artigo": "ART 157: Roubo", "reincidente_comum": "N", "reincidente_especifico": "N"}


def rspe(**kw):
    r = {"regime_atual": "Semiaberto - ATIVO", "status_execucao": "ATIVO", "reincidente": "N", "pena_cumprida": "2a0m0d",
         "pena_total": "8a0m0d", "falta_12m": "não consta", "_crimes": [crime("10/05/2019")]}
    r.update(kw)
    return r


def ficha(**kw):
    f = {"unidade": "CENTRO PENAL AGROINDUSTRIAL DA GAMELEIRA", "conduta": "OTIMA", "data_impressao": "01.10.2026", "eventos": [], "trabalho": []}
    f.update(kw)
    return f


M = {"fd_trab": "Cozinha desde 01.03.2026"}


def st(r, f, m=M):
    return rv.saida_temporaria(r, f, m, None, False, HOJE)


# elegível
x = st(rspe(), ficha())
ok(x["st_ok"] and not x["st_quase"], "elegível: %s" % x)
# regime fechado / unidade do fechado
ok(not st(rspe(regime_atual="Fechado - ATIVO"), ficha())["st_ok"], "regime fechado")
x = st(rspe(), ficha(unidade="PENITENCIARIA ESTADUAL DE DOURADOS"))
ok(not x["st_ok"] and not x["st_quase"], "unidade do fechado não é elegível nem amarela: %s" % x)
ok(not rv.saida_temporaria(rspe(), ficha(), M, None, True, HOJE)["st_ok"], "pena interrompida")
# só crimes posteriores à Lei 14.843/2024
ok(not st(rspe(_crimes=[crime("10/05/2024")]), ficha())["st_ok"], "só fato posterior a 11/04/2024")
# crime novo violento junto com o antigo: não impede
x = st(rspe(_crimes=[crime("10/05/2019"), crime("10/07/2025", hed="S", vga="S")]), ficha())
ok(x["st_ok"], "crime novo não impede: %s" % x)
# hediondo com resultado morte depois de 23/01/2020: vedado; antes: não
ok(not st(rspe(_crimes=[crime("10/03/2021", hed="S", morte="S")]), ficha())["st_ok"], "hediondo com morte de 2021 vedado")
ok(st(rspe(_crimes=[crime("10/03/2019", hed="S", morte="S")]), ficha())["st_ok"], "hediondo com morte de 2019 não vedado")
# frações
ok(not st(rspe(pena_cumprida="1a0m0d", pena_total="8a0m0d"), ficha())["st_ok"], "1/6 não atingido")
ok(st(rspe(pena_cumprida="1a5m0d", pena_total="8a0m0d"), ficha())["st_ok"], "1/6 atingido")
ok(not st(rspe(reincidente="S", pena_cumprida="1a5m0d", pena_total="8a0m0d"), ficha())["st_ok"], "reincidente exige 1/4")
# conduta e falta
ok(not st(rspe(), ficha(conduta="SEM LAPSO"))["st_ok"], "conduta sem lapso")
ok(st(rspe(), ficha(conduta="BOA"))["st_ok"], "conduta boa")
ok(not st(rspe(falta_12m="SIM"), ficha())["st_ok"], "falta nos 12 meses")
# trabalho: sem trabalho não; externo aberto conta
ok(not st(rspe(), ficha(), {"fd_trab": "sem trabalho em curso"})["st_ok"], "sem trabalho")
x = st(rspe(), ficha(trabalho=[{"inicio": "01.06.2026", "fim": "", "setor": "EMPRESA X", "externo": True}]), {"fd_trab": "sem trabalho em curso"})
ok(x["st_ok"], "trabalho externo conta: %s" % x)
# 45 dias do retorno
sai = lambda d: {"data": d, "texto": "Saída confirmada do benefício de: SAÍDA TEMPORÁRIA"}
ret = lambda d: {"data": d, "texto": "Retorno confirmado do benefício de: SAÍDA TEMPORÁRIA"}
ok(not st(rspe(), ficha(eventos=[sai("20.08.2026"), ret("27.08.2026")]))["st_ok"], "retorno há 42 dias")
ok(st(rspe(), ficha(eventos=[sai("10.08.2026"), ret("17.08.2026")]))["st_ok"], "retorno há 52 dias")
x = st(rspe(), ficha(eventos=[sai("10.08.2026")]))
ok(x["st_ok"] and "7 dias" in " ".join(i["txt"] for i in x["st_itens"]), "sem retorno: 7 dias da saída: %s" % x)
ok(not st(rspe(), ficha(eventos=[sai("20.08.2026")]))["st_ok"], "sem retorno, saída recente")
# fato em 11/04/2024 (dia da vigência) já é da lei nova: sozinho, impede; com condenação antiga em cumprimento, não impede
x = st(rspe(_crimes=[crime("11/04/2024")]), ficha())
ok(not x["st_ok"] and not x["st_quase"] and "vedada pela Lei 14.843" in " ".join(i["txt"] for i in x["st_itens"]), "fato em 11/04/2024 sozinho: %s" % x)
ok(st(rspe(_crimes=[crime("10/04/2024")]), ficha())["st_ok"], "fato em 10/04/2024 é anterior")
ok(st(rspe(_crimes=[crime("10/05/2019"), crime("11/04/2024")]), ficha())["st_ok"], "novo com antigo em cumprimento")
ok(not st(rspe(_crimes=[crime("10/05/2019", ext="Sim"), crime("11/04/2024")]), ficha())["st_ok"], "antigo extinto: o novo fica sozinho")
# 45 dias exatos do retorno ao pedido: cabe; 44: não, com a data do novo pedido
ok(st(rspe(), ficha(eventos=[sai("17.08.2026"), ret("24.08.2026")]))["st_ok"], "retorno há 45 dias")
x = st(rspe(), ficha(eventos=[sai("18.08.2026"), ret("25.08.2026")]))
ok(not x["st_ok"] and not x["st_quase"] and "a partir de 09/10/2026" in " ".join(i["txt"] for i in x["st_itens"]), "retorno há 44 dias: %s" % x)
x = st(rspe(), ficha(eventos=[sai("20.08.2026")]))
ok(not x["st_ok"] and not x["st_quase"], "sem retorno, saída recente: não aparece (nem amarelo): %s" % x)
# amarelo: ficha com mais de 90 dias; sem ficha; limite anual
x = st(rspe(), ficha(data_impressao="01.05.2026"))
ok(not x["st_ok"] and x["st_quase"], "ficha antiga = amarelo: %s" % x)
x = st(rspe(), None)
ok(not x["st_ok"] and x["st_quase"], "sem ficha = amarelo")
evs = []
for mth in ("01", "03", "05", "07", "08"):
    evs += [sai("01.%s.2026" % mth), ret("06.%s.2026" % mth)]
x = st(rspe(), ficha(eventos=evs))
ok(not x["st_ok"] and x["st_quase"], "5 saídas no ano = amarelo: %s" % x)
# amarelo não encobre requisito que falha
ok(not st(rspe(regime_atual="Fechado - ATIVO"), ficha(data_impressao="01.05.2026"))["st_quase"], "fechado com ficha antiga não fica amarelo")

if falhas:
    print("FALHOU (saída temporária):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: saída temporária (regime, unidade, Lei 14.843, resultado morte, frações, conduta, trabalho, 45 dias, amarelo)")
