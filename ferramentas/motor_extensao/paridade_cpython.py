"""Paridade APTO x extensão, lado do APTO (CPython): monta uma base com os casos simulados (RSPE, ficha, dados manuais),
abre pela Api do APTO e pede o dossiê de cada processo como a extensão pede (Api._painel_dossie: registro, fatia do
contexto, base jurídica em uso e o resultado do APTO). Grava os dossiês; o lado da extensão (paridade_pyodide.mjs) refaz
a conta no Pyodide, com os MESMOS arquivos do pacote, e tem de chegar à mesma assinatura em todos.
Uso: python ferramentas/motor_extensao/paridade_cpython.py saida.json"""
import json
import os
import sys
import tempfile
import types
from datetime import date, datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "casos_simulados"))
wv = types.ModuleType("webview")
wv.SAVE_DIALOG, wv.FOLDER_DIALOG, wv.OPEN_DIALOG = 1, 2, 0
sys.modules.setdefault("webview", wv)
os.environ.setdefault("APTO_SIM_DESTINO", os.path.join(tempfile.mkdtemp(), "base_paridade.sqlite"))
import roda_casos as rc  # noqa: E402  (monta a base dos casos simulados, como a bateria de casos)

HOJE = date(2026, 10, 12)


class _DT(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(HOJE.year, HOJE.month, HOJE.day, 12, 0, 0)


def main():
    app = rc.app
    app.datetime = _DT  # data de referência fixa (o dossiê usa a data de hoje)
    casos = json.load(open(os.path.join(RAIZ, "casos_simulados", "casos.json"), encoding="utf-8"))
    caminho = rc.preparar(casos, True)
    tmp = tempfile.mkdtemp()
    app.pasta_app = lambda: tmp
    app.CONFIG = os.path.join(tmp, "c.json")
    app._abrir = lambda c: None
    api = app.Api()
    api._js = lambda *a: None
    api.abrir_base(caminho)
    out = {}
    for c in casos:
        d = api._painel_dossie(c["processo"])
        if not d.get("tem"):
            raise SystemExit("dossiê não montado para %s: %s" % (c["id"], d))
        out[c["id"]] = d
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        json.dump({"motor": app.VERSAO, "dossies": out}, f, ensure_ascii=False)
    com_ficha = sum(1 for d in out.values() if d["painel"].get("ficha"))
    print("APTO (CPython %s): %d dossiês, %d com ficha" % (sys.version.split()[0], len(out), com_ficha))


if __name__ == "__main__":
    main()
