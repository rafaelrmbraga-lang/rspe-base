"""Revisão da aba Ficha (base real, 150 casos): limite de 12 obras de leitura a cada 12 meses (Res. CNJ 391/2021, art. 5º) contado
obra a obra, no mês de referência de cada uma. Antes, todas as obras de um relatório iam para o último mês citado e a janela de 12
meses cortava obra que cabia (relatório de 03 a 07/2025 depois de 12 obras de 03/2024 a 02/2025: perdia 2 obras = 8 dias).
Casos hipotéticos, sem nomes. Rodar: python teste_rev_ficha_leitura.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf

falhas = []
HOJE = date(2026, 10, 12)
PROC = "9900701-11.2024.8.12.0001"


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def R():
    return {"processo_execucao": PROC, "nome": "SIMULADO CASO 701", "_crimes": [], "_incidentes": [],
            "_eventos": [{"data": "01/01/2024", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}],
            "saldo_remidos": "0 dias (0 dias remidos - 0 dias perdidos)"}


def F(eventos):
    return rf.atualizar({"data_impressao": "06/10/2026", "nome": "SIMULADO CASO 701", "eventos": [{"data": d, "texto": t} for d, t in eventos]})


def lei(data, meses):
    return (data, "EDUCAÇÃO: Peticionados os relatórios de leitura, referentes aos %s, no sistema SEEU, Autos Nº %s." % (meses, PROC))


try:
    base = [("01.01.2024", "Entrada na Unidade Penal: PENITENCIÁRIA SIMULADA, Procedente: DP SIMULADA - INTERIOR, Conforme OF/CI 1/2024."),
            lei("15.06.2024", "meses 03, 04 e 05 de 2024"), lei("14.09.2024", "meses 06, 07 e 08 de 2024"),
            lei("13.12.2024", "meses 09, 10 e 11 de 2024"), lei("20.03.2025", "mês 12 de 2024 e meses 01 e 02 de 2025"),
            lei("18.08.2025", "meses 03,04,05,06 e 07 de 2025")]
    o = rf.comparativo(R(), F(base), HOJE)
    N = o["fd_novo"]
    L = [d for d in N["docs"] if d["tipo"] == "Leitura"]
    ok(len(L) == 5, "1.1 cinco relatórios: %s" % [(d["periodo"], d["dias"]) for d in L])
    # 03/2024 a 07/2025: em nenhuma janela de 12 meses passam de 12 obras (08/2024 a 07/2025 = 1 + 3 + 3 + 5 = 12)
    ok(N["leitura"] == 68, "1.2 as 17 obras contam (68 dias): %s" % N["leitura"])
    ok(not any(d.get("contido") for d in L), "1.3 nenhum relatório cortado: %s" % [d.get("contido") for d in L])
    # 13 obras em 12 meses: a obra de 02/2025, já usada a cota, passa do limite
    o2 = rf.comparativo(R(), F(base[:5] + [lei("18.08.2025", "meses 02,03,04,05,06 e 07 de 2025")]), HOJE)
    L2 = [d for d in o2["fd_novo"]["docs"] if d["tipo"] == "Leitura"]
    ult = [d for d in L2 if "07/2025" in (d["periodo"] or "")]
    ok(ult and ult[0].get("contido") and ult[0].get("dias_soma") == 20.0,
       "1.4 relatório de 02 a 07/2025 com 02/2025 já usado: soma 5 de 6 obras: %s" % [(d["periodo"], d.get("dias_soma"), d.get("contido")) for d in ult])
except Exception:
    import traceback
    traceback.print_exc()
    falhas.append("exceção")

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for x in falhas:
        print(" -", x)
    sys.exit(1)
print("ok: revisão da ficha - leitura: limite de 12 obras em 12 meses contado obra a obra, no mês de cada uma")
