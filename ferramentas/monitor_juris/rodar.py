"""Classifica o acervo inteiro e grava mj/class.pkl: {id: dict}."""
import os
import pickle, json, collections, sys, importlib
S = os.environ.get("APTO_MJ_PASTA", ".")
sys.path.insert(0, S + "/mj")
import classif as C
from multiprocessing import Pool

rows = None


def um(r):
    rg = C.regioes(r)
    ok, mot = C.escopo(r, rg)
    d = {"esc": ok, "mot": mot}
    if ok:
        desf, jan, trecho = C.dispositivo(rg, r[4] or "", r[2])
        part, pista = C.parte(rg, r[4] or "", r[2], desf)
        s, rot = C.sentido(r[4] or "", part, desf, rg, trecho, pista)
        if desf and C.escopo_disp(trecho[max(0, (C.achados(trecho) or [(0,)])[0][0]):]):
            return r[0], {"esc": False, "mot": "dispositivo da ação penal"}
        d.update(desf=desf, jan=jan, part=part, pista=pista, sentido=s, rot=rot, temas=C.temas(rg))
    return r[0], d


def ini(p):
    global rows


if __name__ == "__main__" and len(sys.argv) < 2:
    rows = pickle.load(open(S + "/mj/rows.pkl", "rb"))
    with Pool(8) as p:
        res = dict(p.map(um, rows, chunksize=500))
    pickle.dump(res, open(S + "/mj/class.pkl", "wb"))
    fav = json.load(open(S + "/mj/fav.json"))
    by = {r[0]: r for r in rows}
    cont = collections.Counter()
    for i, d in res.items():
        r = by[i]
        cont[(r[1], "escopo" if d["esc"] else "fora")] += 1
        if d["esc"]:
            cont[(r[1], d["sentido"] or "sem")] += 1
    for k in sorted(cont):
        print(k, cont[k])
    # recall nas favoráveis curadas/triadas
    rc = collections.Counter()
    for i, f in fav.items():
        d = res.get(i)
        if d is None: continue
        r = by[i]
        rc[(r[1], "cur" if f["cur"] else "auto", "esc" if d["esc"] else "fora", d.get("sentido", "-"))] += 1
    for k in sorted(rc):
        print("FAV", k, rc[k])

if __name__ == "__main__" and len(sys.argv) >= 2 and sys.argv[1] == "so_fav":
    rows = pickle.load(open(S + "/mj/rows.pkl", "rb")); res = pickle.load(open(S + "/mj/class.pkl", "rb"))
