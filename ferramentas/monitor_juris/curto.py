"""Visão curta para conferir escopo: python3 curto.py 'expr' N seed"""
import os
import pickle, json, sys, random, re
S = os.environ.get("APTO_MJ_PASTA", ".")
sys.path.insert(0, S + "/mj")
import classif as C
rows = pickle.load(open(S + "/mj/rows.pkl", "rb")); res = pickle.load(open(S + "/mj/class.pkl", "rb"))
fav = json.load(open(S + "/mj/fav.json"))
expr, n = sys.argv[1], int(sys.argv[2])
random.seed(int(sys.argv[3]) if len(sys.argv) > 3 else 1)
L = [r for r in rows if eval(expr, {"re": re, "C": C}, {"r": r, "d": res[r[0]], "f": fav.get(r[0])})]
print("casos:", len(L))
for r in random.sample(L, min(n, len(L))):
    d = res[r[0]]
    rg = C.regioes(r)
    foco = (rg["cap"][:350] or rg["ini"][:500])
    print("--", r[0][:8], r[1], r[4][:22], d["mot"], d.get("sentido"), "|", foco)
