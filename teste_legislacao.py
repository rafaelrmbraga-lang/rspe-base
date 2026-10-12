"""Vigilância de legislação (rspe_legislacao): alterações posteriores à base jurídica e decreto de indulto novo, com respostas
simuladas da API do Senado (sem internet). Rodar: python teste_legislacao.py"""
import json
import os
import sys
import tempfile
from datetime import date

import rspe_legislacao as L

falhas = []


def ok(c, m):
    if not c:
        falhas.append(m)


LISTA = "<ListaDocumento><documentos><documento id='%s'><numero>%s</numero></documento></documentos></ListaDocumento>"
DET = ("<DetalheDocumento><documentos><documento><disps>"
       "<disp><nomeDispositivo>Art. 112 [Lei]</nomeDispositivo><refs>"
       "<ref><dispositivo>Lei nº 15.402 de 08/05/2026</dispositivo><comentario>Alteração (Declaração)</comentario><codNormaPosterior>9</codNormaPosterior></ref>"
       "<ref><dispositivo>Lei nº 13.964 de 24/12/2019</dispositivo><comentario>Alteração (Declaração)</comentario><codNormaPosterior>8</codNormaPosterior></ref>"
       "</refs></disp><disp><nomeDispositivo>Art. 199 [Lei]</nomeDispositivo><refs>"
       "<ref><dispositivo>Decreto nº 9.999 de 01/06/2026</dispositivo><comentario>Regulamentado (Declaração)</comentario><codNormaPosterior>7</codNormaPosterior></ref>"
       "</refs></disp></disps></documento></documentos></DetalheDocumento>")
DECS = ("<ListaDocumento><documentos>"
        "<documento id='51'><numero>12790</numero><normaNome>Decreto nº 12.790 de 22/12/2025</normaNome><ementa>Concede indulto natalino.</ementa></documento>"
        "<documento id='52'><numero>13100</numero><normaNome>Decreto nº 13.100 de 23/12/2026</normaNome><ementa>Concede indulto natalino e comutação.</ementa></documento>"
        "<documento id='53'><numero>13101</numero><normaNome>Decreto nº 13.101 de 23/12/2026</normaNome><ementa>Dispõe sobre outra coisa.</ementa></documento>"
        "</documentos></ListaDocumento>")


def get(url):
    if "/lista?tipo=DEC" in url:
        return DECS.encode()
    if "/lista?" in url:
        return (LISTA % ("1", "7210")).encode() if "numero=7210" in url else b"<ListaDocumento/>"
    return DET.encode()


r = L.verificar("2026-01-10i", ["11.846", "12.790/2025"], date(2026, 12, 28), get)
t = [x["titulo"] for x in r["itens"]]
ok(any("15.402" in x and "Execução Penal" in x for x in t), "lei posterior à base: %s" % t)
ok(not any("13.964" in x for x in t), "lei anterior à base não é aviso: %s" % t)
ok(not any("9.999" in x for x in t), "regulamentação não é alteração: %s" % t)
ok(any("13.100" in x for x in t) and not any("12.790" in x for x in t) and not any("13.101" in x for x in t), "decretos: %s" % t)
ok(not L.verificar("2026-10-08", ["12790", "13.100"], date(2026, 12, 28), get)["itens"] or
   all("15.402" not in x["titulo"] for x in L.verificar("2026-10-08", ["12790", "13.100"], date(2026, 12, 28), get)["itens"]),
   "base jurídica posterior: sem aviso")


def sem_rede(url):
    raise OSError("sem rede")


d = tempfile.mkdtemp()
arq = os.path.join(d, "c.json")
ok(L.com_cache(arq, "2026-01-10", [], date(2026, 12, 28), sem_rede)["itens"] == [], "sem rede e sem cache: nada")
L.com_cache(arq, "2026-01-10", [], date(2026, 12, 27), get)
c = json.load(open(arq, encoding="utf-8"))
ok(c["itens"] and c["dia"] == "2026-12-27", "cache gravado")
ok(L.com_cache(arq, "2026-01-10", [], date(2026, 12, 28), sem_rede)["itens"], "sem rede: vale a última consulta")
if falhas:
    print("FALHOU (legislação):")
    for f in falhas:
        print("  " + f)
    sys.exit(1)
print("ok: vigilância de legislação (lei posterior à base, regulamentação ignorada, decreto de indulto novo, cache e sem rede)")
