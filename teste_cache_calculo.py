"""Cache dos cálculos (7.16.2): o resultado de cada assistido é guardado pela impressão digital de tudo o que entra no
cálculo e reaproveitado se nada mudou. Confere, com casos fictícios da bateria simulada, que a lista e os registros são
idênticos ao cálculo do zero: na remontagem da sessão, na reabertura (cache em disco) e depois de alterar dados (fixar,
pedido). Rodar: python teste_cache_calculo.py"""
import json
import os
import sys
import tempfile
import time
import types

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "casos_simulados"))
sys.modules.setdefault("webview", types.ModuleType("webview"))
tmp = tempfile.mkdtemp()
os.environ["APTO_SIM_DESTINO"] = os.path.join(tmp, "b.sqlite")
import roda_casos as rc  # noqa: E402 (fixa a data de hoje)
import rspe_app as app  # noqa: E402

casos = json.load(open(os.path.join(AQUI, "casos_simulados", "casos.json"), encoding="utf-8"))[:30]
base = rc.preparar(casos, True)
app.pasta_app = lambda: tmp
app.CONFIG = os.path.join(tmp, "c.json")
app._abrir = lambda c: None
norm = lambda o: json.loads(json.dumps(o, ensure_ascii=False, sort_keys=True, default=str))
falhas = []


def foto(api, L):
    L = dict(L)
    L.pop("copia", None)
    return norm({"l": L, "j": {m["id"]: api._json_de(m) for m in (api._modelos or []) + (api._ocultos or [])}})


api = app.Api()
api._js = lambda *a: None
F0 = foto(api, api.abrir_base(base))
if not api._calc_mem or not api._calc_mem[1]:
    falhas.append("cache não preenchido")
if foto(api, api.listar()) != F0:
    falhas.append("remontagem com cache difere do cálculo do zero")
time.sleep(1.5)
api2 = app.Api()
api2._js = lambda *a: None
if foto(api2, api2.abrir_base(base)) != F0:
    falhas.append("reabertura com o cache em disco difere")
ids = [m["id"] for m in api._modelos][:3]
api.fixar(ids[0], True)
api.pedido(ids[1], "prog", "01/10/2026", "teste", "")
F1 = foto(api, api.listar())
api._cache_calc_limpar()
F2 = foto(api, api.listar())
if F1 != F2:
    falhas.append("depois de alterar dados, a lista com cache difere da do zero")
if F1 == F0:
    falhas.append("a alteração não apareceu na lista")
if falhas:
    print("FALHA: " + "; ".join(falhas))
    sys.exit(1)
print("ok: cache dos cálculos idêntico ao cálculo do zero (remontagem, reabertura e depois de alterar dados)")
