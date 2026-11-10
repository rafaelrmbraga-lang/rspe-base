"""Revisão da aba Ficha (base real, 150 casos): leitura do estudo.
1) atestado de estudo com "Tempo de Remissão: 25 dias" (sem "dias remidos") entra na comparação com os dias declarados;
2) atestado de trabalho e atestado de estudo no mesmo lançamento ("... 200 dias remidos. E Atestado de Trabalho 07/2018, de estudo,
   totalizando 84 h/a de estudo e 7 dias remidos"): a parte do estudo vira atestado de estudo;
3) início do estudo em texto livre ("deu início às atividades educacionais em ..."): abre a matrícula e entra no "Estudo a requerer".
Casos hipotéticos, sem nomes. Rodar: python teste_rev_ficha_estudo.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf

falhas = []
HOJE = date(2026, 10, 12)
PROC = "9900702-22.2015.8.12.0001"


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def R(ini="10/03/2015"):
    return {"processo_execucao": PROC, "nome": "SIMULADO CASO 702", "_crimes": [], "_incidentes": [],
            "_eventos": [{"data": ini, "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}],
            "saldo_remidos": "0 dias (0 dias remidos - 0 dias perdidos)"}


def F(eventos):
    return rf.atualizar({"data_impressao": "06/10/2026", "nome": "SIMULADO CASO 702", "eventos": [{"data": d, "texto": t} for d, t in eventos]})


try:
    ent = ("10.03.2015", "Entrada na Unidade Penal: PENITENCIÁRIA SIMULADA, Procedente: DP SIMULADA - INTERIOR, Conforme OF/CI 1/2015.")
    f = F([ent,
           ("12.03.2019", "Nesta data foi emitido Atestado de Trabalho 05/2019, na função de faxineiro, totalizando 600 dias trabalhados e "
                          "200 dias remidos. E Atestado de Trabalho 08/2019, de estudo, totalizando 84 h/a de estudo e 7 dias remidos."),
           ("20.04.2019", "Nesta data, foi enviado, via Esaj, Atestado de Trabalho prisional do interno; Tipo: Estudante; Data Inicial: "
                          "04.08.2018; Data Final: 14.12.2018; Tempo de Estudo: 300/h/a; Tempo de Remissão: 25 dias.")])
    ae = [e for e in f["estudos"] if e["curso"].startswith("Atestado de estudo")]
    ok(sorted(e.get("dias_remidos") for e in ae) == [7.0, 25.0], "1/2 atestados de estudo com os dias: %s" % [(e["curso"], e.get("dias_remidos")) for e in ae])
    N = rf.comparativo(R(), f, HOJE)["fd_novo"]
    ok(N["est_comp"] == 32, "1/2 estudo comprovado 7 + 25: %s" % N["est_comp"])
    at = [d for d in N["docs"] if d["tipo"] == "Atestado de trabalho"]
    ok([d["dias"] for d in at] == [200.0], "2 o atestado de trabalho segue com 200 dias: %s" % [(d["num"], d["dias"]) for d in at])
    # 3) início em texto livre
    f3 = F([("05.05.2023", ent[1]), ("14.03.2024", "EDUCAÇÃO. deu início as atividades educacionais em 14/03/2024, no período vespertino."),
            ("20.06.2024", "Saída da Unidade Penal: PENITENCIÁRIA SIMULADA, Destino: PENITENCIÁRIA SIMULADA II, Motivo: Transferência de "
                           "Comarca, Conforme CI: CI.Nº1/2024.")])
    ok([(e["inicio"], e["fim"]) for e in f3["estudos"]] == [("14.03.2024", "20.06.2024")], "3.1 matrícula aberta: %s" % f3["estudos"])
    o3 = rf.comparativo(R("05/05/2023"), f3, HOJE)
    ok(o3["fd_estudo"] == "Sim" and o3["fd_novo"]["est_estim"], "3.2 estudo a requerer: %s %s" % (o3["fd_estudo"], o3["fd_novo"]["est_estim"]))
except Exception:
    import traceback
    traceback.print_exc()
    falhas.append("exceção")

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for x in falhas:
        print(" -", x)
    sys.exit(1)
print("ok: revisão da ficha - estudo: \"Tempo de Remissão\" do atestado de estudo, atestado de estudo no lançamento do de trabalho, "
      "início do estudo em texto livre")
