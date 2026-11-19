"""Indulto que exige saídas temporárias (ou trabalho externo): só vai para "a conferir" quando a pessoa podia tê-las, isto é,
quando estava no semiaberto, no aberto ou em livramento na data do decreto. Quem ficou no fechado o período todo não recebe o
"conferir no prontuário": a hipótese é afastada pelo regime (11/2026, pedido do painel do SEEU). Rodar: python teste_indulto_saidas_fechado.py"""
import copy
import json
import os
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_indulto_tl as rtl

AQUI = os.path.dirname(os.path.abspath(__file__))
HOJE = date(2026, 10, 12)
falhas = []


def hip_2023(r):
    L = rtl.linha(copy.deepcopy(r), HOJE)
    for d in L["decretos"]:
        if str(d.get("ano") or d.get("id"))[:4] == "2023":
            for it in (d.get("indulto") or {}).get("checklist") or []:
                if it.get("item") == "Requisito objetivo / hipótese" and "VIII" in (it.get("texto") or ""):
                    return it
    return None


casos = {c["id"]: c for c in json.load(open(os.path.join(AQUI, "casos_simulados", "casos.json"), encoding="utf-8"))}

# 1) no semiaberto em 25/12/2023: requisitos atendidos, saídas temporárias a conferir no prontuário
it = hip_2023(casos["S141"]["rspe"])
if not it or "saídas temporárias" not in it.get("texto", ""):
    falhas.append("S141 (semiaberto em 2023): esperava 'conferir' das saídas temporárias, veio %r" % (it,))

# 2) a mesma pessoa sem nenhuma progressão depois da regressão de 28/02/2023: fechado em 25/12/2023
r = copy.deepcopy(casos["S141"]["rspe"])
r["_incidentes"] = [i for i in r["_incidentes"] if not (
    "FIXAÇÃO" in (i.get("tipo") or "") and (i.get("data_decisao") or "") in ("11/07/2023", "27/03/2024")) and "LIVRAMENTO" not in (i.get("tipo") or "")]
r["regime_atual"] = "Fechado - ATIVO"
it = hip_2023(r)
if not it:
    falhas.append("fechado em 2023: hipótese do art. 2º, VIII não apareceu")
else:
    t = it.get("texto", "")
    if "saídas temporárias" in t or "prontuário" in t:
        falhas.append("fechado em 2023: não devia pedir conferência das saídas temporárias: %r" % t)
    if it.get("estado") != "ko":
        falhas.append("fechado em 2023: esperava não atendida, veio %r" % it.get("estado"))

if falhas:
    print("FALHOU:\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: saídas temporárias só a conferir quando o regime da data permitia")
