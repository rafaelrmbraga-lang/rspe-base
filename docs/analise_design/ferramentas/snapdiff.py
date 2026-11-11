"""Compara duas fotografias de estilo. Uso: python3 -I snapdiff.py a.json b.json [max_exemplos]"""
import sys, json, collections, re
src = open(__file__.replace("snapdiff.py", "snap.py"), encoding="utf-8").read()
PROPS = eval(re.search(r"PROPS = (\[.*?\])\nJS", src, re.S).group(1)) + ["caixa", "classe"]
A, B = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])); M = int(sys.argv[3]) if len(sys.argv) > 3 else 12
LISTA = []; tot = 0; porprop = collections.Counter(); ex = collections.defaultdict(list)
for cena in sorted(set(A) | set(B)):
    a, b = A.get(cena, {}), B.get(cena, {})
    if not a or not b: print("cena ausente:", cena, bool(a), bool(b)); continue
    ka, kb = set(a), set(b)
    if ka != kb:
        print("[%s] elementos diferentes: -%d +%d" % (cena, len(ka - kb), len(kb - ka)), list(ka - kb)[:3], list(kb - ka)[:3])
    for k in ka & kb:
        if a[k] == b[k]: continue
        va, vb = a[k].split("\u0001"), b[k].split("\u0001")
        for i, (x, y) in enumerate(zip(va, vb)):
            if x != y:
                pr = PROPS[i] if i < len(PROPS) else "?"; porprop[pr] += 1; tot += 1; LISTA.append((cena, k, pr))
                if len(ex[pr]) < M: ex[pr].append("%s %s: %r -> %r" % (cena, k[-70:], x[:80], y[:80]))
print("diferenças:", tot)
for pr, n in porprop.most_common():
    print("  %-28s %d" % (pr, n))
    for e in ex[pr][:M]: print("      ", e)

import os
if os.environ.get("DIFFS_OUT"): json.dump(LISTA, open(os.environ["DIFFS_OUT"], "w"))
