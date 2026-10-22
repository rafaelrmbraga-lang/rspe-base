import os
"""Monta bases FICTÍCIAS a partir de casos_simulados/casos.json (144 casos).
Uso: python monta_base.py <destino.sqlite> <n_copias>
Cada cópia troca o nº da execução e o nome (SIMULADO CASO 001 -> SIMULADO CASO 001 B...), sem tocar nas contas."""
import sys, os, json, types, re
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, REPO); sys.path.insert(0, os.path.join(REPO, "casos_simulados"))
wv = types.ModuleType("webview"); wv.SAVE_DIALOG = 1; wv.FOLDER_DIALOG = 2; wv.OPEN_DIALOG = 0; sys.modules["webview"] = wv
import roda_casos as rc

destino, n = sys.argv[1], int(sys.argv[2])
casos = json.load(open(os.path.join(REPO, "casos_simulados", "casos.json"), encoding="utf-8"))
SUF = ["", " B", " C", " D", " E", " F", " G", " H"]
todos = []
for k in range(n):
    for c in casos:
        if k == 0:
            todos.append(c); continue
        p = c["processo"]
        novo = "%07d%s" % (int(p[:7]) + 10000 * k, p[7:])
        s = json.dumps(c, ensure_ascii=False).replace(p, novo)
        s = s.replace('"nome": "SIMULADO CASO %s"' % c["id"][1:], '"nome": "SIMULADO CASO %s%s"' % (c["id"][1:], SUF[k]))
        s = re.sub(r'"cpf": "9(\d{10})"', lambda m: '"cpf": "%d%s"' % (9 - k, m.group(1)), s)
        s = s.replace("MAE SIMULADA %s" % c["id"][1:], "MAE SIMULADA %s%s" % (c["id"][1:], SUF[k]))
        todos.append(json.loads(s))
caminho = rc.preparar(todos, True)
os.replace(caminho, destino)
print(destino, len(todos))
