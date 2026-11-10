"""Revisão da aba Ficha (base real, 150 casos): pagamento do trabalho (depósito judicial, pecúlio) lançado na ficha num mês sem nenhum
período de trabalho registrado é indício de trabalho não lançado: ponto amarelo "pedir à unidade o registro e o atestado" (LEP, art. 126).
Com o trabalho registrado no período, nada. Casos hipotéticos, sem nomes. Rodar: python teste_rev_ficha_pagamento.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf

falhas = []
HOJE = date(2026, 10, 12)
PROC = "9900705-55.2024.8.12.0001"


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


try:
    r = {"processo_execucao": PROC, "nome": "SIMULADO CASO 705", "_crimes": [], "_incidentes": [],
         "_eventos": [{"data": "01/03/2024", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}],
         "saldo_remidos": "0 dias (0 dias remidos - 0 dias perdidos)"}
    ent = ("01.03.2024", "Entrada na Unidade Penal: PENITENCIÁRIA SIMULADA, Procedente: DP SIMULADA - INTERIOR, Conforme OF/CI 1/2024.")
    pag = [("14.05.2025", "Depósito Judicial, referente ao pagamento de abril/2025, no valor de R$ 900,00, conforme recibo anexado."),
           ("16.06.2025", "Depósito referente ao pagamento do trabalho do mês de maio-2025.")]
    f = rf.atualizar({"data_impressao": "06/10/2026", "nome": "SIMULADO CASO 705", "eventos": [{"data": d, "texto": t} for d, t in [ent] + pag]})
    N = rf.comparativo(r, f, HOJE)["fd_novo"]
    p = [x for x in N["pontos"] if x["tipo"] == "indicio_trabalho"]
    ok(p and p[0]["cor"] == "amarelo" and "14/05/2025" in p[0]["texto"] and "16/06/2025" in p[0]["texto"], "1 indício: %s" % p)
    trab = [("01.03.2025", "TRABALHO: Iniciou atividade laboral, no setor de trabalho FAXINA SIMULADA, conforme documento CI 1/2025.")]
    f2 = rf.atualizar({"data_impressao": "06/10/2026", "nome": "SIMULADO CASO 705", "eventos": [{"data": d, "texto": t} for d, t in [ent] + trab + pag]})
    N2 = rf.comparativo(r, f2, HOJE)["fd_novo"]
    ok(not [x for x in N2["pontos"] if x["tipo"] == "indicio_trabalho"], "2 com o trabalho registrado, sem indício")
except Exception:
    import traceback
    traceback.print_exc()
    falhas.append("exceção")

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for x in falhas:
        print(" -", x)
    sys.exit(1)
print("ok: revisão da ficha - pagamento de trabalho sem trabalho registrado vira ponto a conferir com a unidade")
