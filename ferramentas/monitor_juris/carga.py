"""Carrega o acervo (somente leitura) num pickle compacto: textos longos viram começo + fim."""
import os
import sqlite3, pickle, re
S = os.environ.get("APTO_MJ_PASTA", ".")
c = sqlite3.connect("file:%s/acervo/acervo_jurisprudencia.db?mode=ro" % S, uri=True)
termos = {}
for i, t in c.execute("select id_unico, termo from decisao_termos"):
    termos.setdefault(i, []).append(t.strip('"'))
rows = []
for r in c.execute("select id_unico, tribunal, tipo, numero_processo, classe, assunto, orgao_julgador, relator, comarca, data_julgamento, data_publicacao, ano, resultado, votacao, ementa, link from decisoes"):
    r = list(r)
    e = r[14] or ""
    if len(e) > 14000:
        e = e[:7000] + " … " + e[-7000:]
    r[14] = e
    r.append(termos.get(r[0], []))
    rows.append(tuple(r))
pickle.dump(rows, open(S + "/mj/rows.pkl", "wb"), protocol=4)
print(len(rows))
