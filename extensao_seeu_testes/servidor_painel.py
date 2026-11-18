"""APTO de teste para o painel no SEEU: base com os casos simulados, aberta pela Api do APTO, e o servidor local da
extensão (127.0.0.1:47321) no ar. Usado por teste_painel_e2e.js (Chromium com a extensão carregada).
Uso: python extensao_seeu_testes/servidor_painel.py  (fica no ar até ser encerrado)"""
import json
import os
import sys
import tempfile
import time
import types
from datetime import date, datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "casos_simulados"))
wv = types.ModuleType("webview")
wv.SAVE_DIALOG, wv.FOLDER_DIALOG, wv.OPEN_DIALOG = 1, 2, 0
sys.modules.setdefault("webview", wv)
TMP = tempfile.mkdtemp()
os.environ.setdefault("APTO_SIM_DESTINO", os.path.join(TMP, "base_painel.sqlite"))
import roda_casos as rc  # noqa: E402

HOJE = date(2026, 10, 12)


class _DT(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(HOJE.year, HOJE.month, HOJE.day, 12, 0, 0)


app = rc.app
app.datetime = _DT
casos = json.load(open(os.path.join(RAIZ, "casos_simulados", "casos.json"), encoding="utf-8"))
caminho = rc.preparar(casos, True)
app.pasta_app = lambda: TMP
app.CONFIG = os.path.join(TMP, "c.json")
app._abrir = lambda c: None
api = app.Api()
api._js = lambda *a: print("ui:", a[0][:120], flush=True)
api._pasta_dados = os.path.join(TMP, "dados")
os.makedirs(api._pasta_dados, exist_ok=True)
api.abrir_base(caminho)
srv = api._extensao_servidor()
print("APTO de teste no ar" if srv else "porta 47321 ocupada", flush=True)
while srv:
    time.sleep(1)
