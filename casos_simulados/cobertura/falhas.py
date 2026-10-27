"""Roda a cobertura inteira (8 áreas) e grava a lista de verificações que falham (caso, índice, nota) em JSON.
Uso: python3 falhas.py SAIDA.json [BASE_COMPARACAO.json]  - com a base de comparação, mostra o que passou a falhar e o que passou a acertar."""
import glob, json, os, sys, tempfile
ARGS = sys.argv[1:]
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
AREAS = ["leitura", "ficha", "progressao", "auditoria", "remicao", "indulto_novos", "decretos_antigos", "prescricao_extincao"]
casos = []
for a in AREAS:
    casos += json.load(open(os.path.join(AQUI, a + ".json"), encoding="utf-8"))
tmp = tempfile.mkdtemp()
todos = os.path.join(tmp, "todos.json")
json.dump(casos, open(todos, "w", encoding="utf-8"), ensure_ascii=False)
os.environ["APTO_SIM_DESTINO"] = os.path.join(tmp, "b.sqlite")
import roda_casos as rc
rc.tempfile.mkdtemp = lambda: tmp
sys.argv = ["x", todos, "--vazia"]
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    rc.main()
res = json.load(open(os.path.join(tmp, "resultados.json"), encoding="utf-8"))
f = sorted(["%s#%d%s" % (r["id"], i, " (decisão)" if x.get("decisao") else "") for r in res for i, x in enumerate(r.get("checks", [])) if not x["ok"]]
           + ["%s#montagem" % r["id"] for r in res if r.get("erro")])
json.dump(f, open(ARGS[0], "w"), indent=0)
print(len(res), "casos;", len(f), "verificações falhando")
if len(ARGS) > 1:
    b = set(json.load(open(ARGS[1])))
    novas, corrigidas = sorted(set(f) - b), sorted(b - set(f))
    print("PASSARAM A FALHAR (regressão):", novas or "nenhuma")
    print("passaram a acertar:", corrigidas or "nenhuma")
