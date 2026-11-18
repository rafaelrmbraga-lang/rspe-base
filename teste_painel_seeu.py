"""Painel do APTO no SEEU (7.32 / extensão 1.15): a análise do painel (rspe_painel) usa o cálculo do APTO sem conta nova e
aplica as regras combinadas em 11/2026 - o que depende da ficha sai "a conferir" sem ela (nunca "cabe"); com a ficha, o que
o APTO apurou; custodiado sem remição decidida há mais de 6 meses: pedir atestado. A mesma entrada dá a mesma chave e a
mesma assinatura (base da conferência APTO x extensão). Também roda o teste da tela do painel (node).
Rodar: python teste_painel_seeu.py"""
import copy
import json
import os
import shutil
import subprocess
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_painel as rp  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
HOJE = date(2026, 10, 12)
falhas = []


def ok(c, m):
    if not c:
        falhas.append(m)


casos = {c["id"]: c for c in json.load(open(os.path.join(AQUI, "casos_simulados", "casos.json"), encoding="utf-8"))}


def itens(p):
    return [it for g in p["grupos"] for it in g["itens"]]


# 1) indulto possível sem ficha: a conferir (falta grave na ficha), nunca "cabe"
p = rp.analisar(casos["S001"]["rspe"], hoje=HOJE)
i25 = next((x for x in itens(p) if x["id"] == "i25"), None)
ok(i25 and i25["nivel"] == "med" and "falta grave" in i25["conferir"] and "ficha" in i25["conferir"], "S001 sem ficha: indulto 2025 a conferir (%r)" % (i25,))
ok(not any(x["nivel"] == "ok" and x["id"][0] in "ic" for x in itens(p)), "sem ficha: nenhum indulto/comutação como 'cabe'")
ok(p["ficha"] is False, "sem ficha: marcado")

# 2) mesma entrada = mesma chave e mesma assinatura; a entrada não é alterada pelo cálculo
r = copy.deepcopy(casos["S141"]["rspe"])
r0 = json.dumps(r, sort_keys=True)
a, b = rp.analisar(r, hoje=HOJE), rp.analisar(r, hoje=HOJE)
ok(a["assinatura"] == b["assinatura"] and a["chave"] == b["chave"], "mesma entrada, mesmo resultado")
ok(json.dumps(r, sort_keys=True) == r0, "o cálculo não altera a entrada")
c = rp.analisar(r, hoje=date(2026, 10, 13))
ok(c["chave"] != a["chave"], "outra data de referência, outra chave")

# 3) atestado: custodiado sem remição decidida há mais de 6 meses -> a conferir; com remição recente, não
r = copy.deepcopy(casos["S001"]["rspe"])
r["_incidentes"] = [i for i in r.get("_incidentes") or [] if "REMI" not in (i.get("tipo") or "").upper()]
p = rp.analisar(r, hoje=HOJE)
at = next((x for x in itens(p) if x["id"] == "atestado"), None)
ok(at and at["nivel"] == "med" and "atestado" in at["conferir"], "sem remição há mais de 6 meses: pedir atestado (%r)" % (at,))
r["_incidentes"].append({"tipo": "REMIÇÃO", "complemento": "10 Dia(s) Remido(s)", "data_decisao": "01/09/2026", "data_referencia": "01/09/2026", "situacao": "CONCEDIDO"})
p = rp.analisar(r, hoje=HOJE)
ok(not any(x["id"] == "atestado" for x in itens(p)), "remição decidida há 1 mês: sem alerta de atestado")

# 4) escala: níveis conhecidos, grupos na ordem, contagem confere
for cid in ("S001", "S006", "S093", "S141"):
    p = rp.analisar(casos[cid]["rspe"], hoje=HOJE)
    niv = [g["nivel"] for g in p["grupos"]]
    ok(niv == sorted(niv, key=lambda n: rp.ORDEM[n]), "%s: grupos na ordem da escala" % cid)
    ok(all(x["nivel"] in rp.ORDEM for x in itens(p)), "%s: nível fora da escala" % cid)
    ok(p["contagem"]["crit"] == sum(1 for x in itens(p) if x["nivel"] == "crit"), "%s: contagem" % cid)

# 5) dossiê em texto (a ponte com a extensão): mesmo resultado que a chamada direta
d = {"r": casos["S093"]["rspe"], "sub": None, "hoje": "12/10/2026"}
p1 = json.loads(rp.analisar_dossie(json.dumps(d, ensure_ascii=False)))
p2 = rp.analisar(casos["S093"]["rspe"], hoje=HOJE)
ok(p1["assinatura"] == p2["assinatura"], "analisar_dossie = analisar")

# 6) a tela do painel (node), se houver node neste computador
if shutil.which("node"):
    ok(subprocess.call(["node", os.path.join(AQUI, "extensao_seeu_testes", "teste_painel_core.js")]) == 0, "teste da tela do painel (node)")

if falhas:
    print("FALHOU:\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: painel do APTO no SEEU (a conferir sem ficha, atestado, mesma entrada = mesmo resultado, escala)")
