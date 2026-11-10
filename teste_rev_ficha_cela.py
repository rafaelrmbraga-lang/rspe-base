"""Revisão da aba Ficha (base real, 150 casos): trabalho externo do semiaberto registrado só pela cela ("Mudança de Cela ... Destino:
... SEMIABERTO TRAB EXTERNO/CONVÊNIO - EMPRESA") vira período de trabalho externo, da entrada na cela até a ida para outra cela. Sem
o lançamento "TRABALHO:", o período fica "conferir com a unidade" (o atestado sem período emitido depois pode já cobri-lo), e não
pedido de atestado. Com lançamento de trabalho no mesmo período, vale o lançamento (a cela não cria outro período).
Casos hipotéticos, sem nomes. Rodar: python teste_rev_ficha_cela.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf

falhas = []
HOJE = date(2026, 10, 12)
PROC = "9900704-44.2013.8.12.0001"


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def cela(d, orig, dest):
    return (d, "Mudança de Cela: E.P.M. DE REGIME SEMIABERTO SIMULADO, Motivo: Pedido, Origem: %s, Destino: %s, Nº Termo: 1." % (orig, dest))


try:
    r = {"processo_execucao": PROC, "nome": "SIMULADO CASO 704", "_crimes": [], "_incidentes": [],
         "_eventos": [{"data": "01/02/2013", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}],
         "saldo_remidos": "0 dias (0 dias remidos - 0 dias perdidos)"}
    ev = [("03.03.2016", "Entrada na Unidade Penal: E.P.M. DE REGIME SEMIABERTO SIMULADO, Procedente: PENITENCIÁRIA SIMULADA - INTERIOR, Conforme OF/CI 1/2016."),
          cela("11.04.2016", "PAVILHAO 1/SEMIABERTO INTRAMUROS/INTRAMUROS/03", "PAVILHAO 1/SEMIABERTO TRAB EXTERNO/CONVENIO - CONSTRUTORA SIMULADA/09"),
          cela("09.03.2017", "PAVILHAO 1/SEMIABERTO TRAB EXTERNO/CONVENIO - CONSTRUTORA SIMULADA/09", "PAVILHAO 1/SEMIABERTO INTRAMUROS/AGUARDANDO/01")]
    f = rf.atualizar({"data_impressao": "06/10/2026", "nome": "SIMULADO CASO 704", "eventos": [{"data": d, "texto": t} for d, t in ev]})
    ext = [(t["setor"], t["inicio"], t["fim"]) for t in f["trabalho"] if t.get("externo")]
    ok(ext == [("Trabalho externo - Construtora Simulada", "11.04.2016", "08.03.2017")], "1.1 período pela cela: %s" % ext)
    o = rf.comparativo(r, f, HOJE)
    L = [x for x in o["fd_novo"]["trab"]["linhas"] if "Construtora" in x["local"] or "externo" in x["local"].lower()]
    ok(L and not L[0].get("pedir_dias") and L[0].get("conf_dias", 0) > 80, "1.2 conferir com a unidade, não pedir: %s" % [(x["local"], x.get("pedir_dias"), x.get("conf_dias")) for x in L])
    # com o lançamento de trabalho no mesmo período, a cela não cria outro
    ev2 = ev[:2] + [("11.04.2016", "TRABALHO: Iniciou atividade laboral, no setor de trabalho CONSTRUTORA SIMULADA, conforme documento CI 1/2016.")] + ev[2:]
    f2 = rf.atualizar({"data_impressao": "06/10/2026", "nome": "SIMULADO CASO 704", "eventos": [{"data": d, "texto": t} for d, t in ev2]})
    ok(not any(t.get("cela_externo") for t in f2["trabalho"]), "1.3 lançamento de trabalho prevalece: %s" % f2["trabalho"])
except Exception:
    import traceback
    traceback.print_exc()
    falhas.append("exceção")

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for x in falhas:
        print(" -", x)
    sys.exit(1)
print("ok: revisão da ficha - trabalho externo do semiaberto pela cela (conferir com a unidade; o lançamento de trabalho prevalece)")
