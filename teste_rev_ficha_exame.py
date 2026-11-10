"""Revisão da aba Ficha (base real, 150 casos): remição de 133 dias decidida logo depois do certificado do ENEM peticionado é do ENEM
(ensino médio inteiro, 100 dias, mais 1/3 da conclusão - LEP, art. 126, § 5º; Res. CNJ 391/2021, art. 3º). O teto sem a conclusão
(100) jogava a remição no trabalho sem atestado mais próximo ("pode já estar remido") e o atestado desse trabalho deixava de ser pedido.
Casos hipotéticos, sem nomes. Rodar: python teste_rev_ficha_exame.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf

falhas = []
HOJE = date(2026, 10, 12)
PROC = "9900703-33.2024.8.12.0001"


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


try:
    r = {"processo_execucao": PROC, "nome": "SIMULADO CASO 703", "_crimes": [],
         "_eventos": [{"data": "10/02/2024", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}],
         "_incidentes": [{"tipo": "REMIÇÃO", "complemento": "133 Dia(s) Remido(s)", "data_decisao": "20/05/2025", "data_referencia": "20/05/2025",
                          "situacao": "CONCEDIDO"}],
         "saldo_remidos": "133 dias (133 dias remidos - 0 dias perdidos)"}
    ev = [("10.02.2024", "Entrada na Unidade Penal: PENITENCIÁRIA SIMULADA, Procedente: DP SIMULADA - INTERIOR, Conforme OF/CI 1/2024."),
          ("03.04.2024", "TRABALHO: Iniciou atividade laboral, no setor de trabalho PRENDEDORES SIMULADOS, conforme documento CI 1/2025."),
          ("28.11.2024", "TRABALHO: Deixa de trabalhar, no setor de trabalho PRENDEDORES SIMULADOS, conforme documento N/C, motivo: TROCA."),
          ("02.05.2025", "EDUCAÇÃO: Peticionado Certificado do ENEM 2024 no Sistema SEEU nos Autos Nº %s." % PROC)]
    f = rf.atualizar({"data_impressao": "06/10/2026", "nome": "SIMULADO CASO 703", "eventos": [{"data": d, "texto": t} for d, t in ev]})
    o = rf.comparativo(r, f, HOJE)
    N = o["fd_novo"]
    g = [x for x in N["ligacao"] if x.get("i") is not None]
    ok(g and g[0]["grau"] == "provavel" and any("ENEM" in c for c in g[0]["docs"]) and not g[0]["trab"],
       "1 a remição de 133 dias é do ENEM: %s" % [(x["grau"], x["docs"], x["trab"]) for x in g])
    ok(N["pedir_dias"] > 40 and o["fd_atestar"] == "Sim", "2 o trabalho sem atestado segue a pedir: %s %s" % (N["pedir_dias"], o["fd_atestar"]))
except Exception:
    import traceback
    traceback.print_exc()
    falhas.append("exceção")

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for x in falhas:
        print(" -", x)
    sys.exit(1)
print("ok: revisão da ficha - exame: remição de 133 dias logo depois do certificado do ENEM fica com o ENEM, e o trabalho sem atestado segue a pedir")
