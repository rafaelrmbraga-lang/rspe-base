"""Teste da calculadora de penas (botão "Calculadora" no topo): soma por componente, período entre datas (dia do começo),
término e frações pelo calendário (início + pena - 1 dia; CP, art. 10), remidos antes/depois da fração, interrupção, outra
fração, percentuais da LEP, texto, registros na base e o PDF. Rodar: python teste_calculadora.py"""
import os
import sys
import tempfile
import types
from datetime import date

_wv = types.ModuleType("webview")
_wv.SAVE_DIALOG, _wv.FOLDER_DIALOG, _wv.OPEN_DIALOG = 1, 2, 0
sys.modules["webview"] = _wv
import rspe_app as app  # noqa: E402
import rspe_calc as rc  # noqa: E402

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


F = lambda *ps: [{"s": 1, "p": {"a": a, "m": m, "d": d}} for a, m, d in ps]
# soma por componente: 1a4m + 2a3m + 8a9m = 12a4m (e não 12a3m25d pela conversão em dias)
ok(rc.soma_penas(F((1, 4, 0), (2, 3, 0), (8, 9, 0))) == (12, 4, 0), "soma: %s" % (rc.soma_penas(F((1, 4, 0), (2, 3, 0), (8, 9, 0))),))
ok(rc.soma_penas(F((0, 0, 25), (0, 0, 10))) == (0, 1, 5), "30 dias = 1 mês")
ok(rc.soma_penas(F((2, 0, 0)) + [{"s": -1, "p": {"a": 0, "m": 6, "d": 0}}]) == (1, 6, 0), "subtração")
ok(rc.soma_penas([{"s": -1, "p": {"a": 1}}]) == (0, 0, 0), "sem negativo")
# período: conta o dia do começo
ok(rc.entre(date(2022, 1, 26), date(2022, 8, 5)) == ((0, 6, 11), 192), "período Alex: %s" % (rc.entre(date(2022, 1, 26), date(2022, 8, 5)),))
ok(rc.entre(date(2020, 1, 1), date(2020, 12, 31)) == ((1, 0, 0), 366), "um ano")
ok(rc.entre(date(2020, 5, 2), date(2020, 5, 1)) is None, "período invertido")
# término e frações: início + pena - 1 dia; 1/6 de 6 anos = 1 ano
r = rc.calcular({"fita": F((1, 0, 0)), "inicio": "01/01/2020"})
ok(r["termino"] == "31/12/2020", "término 1 ano: %s" % r.get("termino"))
r = rc.calcular({"fita": F((6, 0, 0)), "inicio": "01/01/2020"})
ok(r["fracoes"][0] == {"rot": "1/6", "q": "1a0m0d", "data": "31/12/2020"}, "1/6: %s" % r["fracoes"][0])
ok([x["rot"] for x in r["percentuais"]] == rc.PERCENTUAIS and r["percentuais"][0]["q"] == "0a11m20d", "16%%: %s" % r["percentuais"][0])
# dia inexistente no mês vai ao último dia
ok(rc.mais(date(2020, 1, 31), 0, 1, 0) == date(2020, 2, 29), "31/01 + 1 mês")
# interrupção e remidos (antes e depois)
r = rc.calcular({"fita": F((1, 0, 0)), "inicio": "01/01/2020", "interr": {"m": 2}, "rem": 10})
ok(r["termino"] == "18/02/2021", "término com interrupção e remidos: %s" % r["termino"])
a = rc.calcular({"fita": F((6, 0, 0)), "inicio": "01/01/2020", "rem": 60, "rem_modo": "antes"})["fracoes"][0]
d = rc.calcular({"fita": F((6, 0, 0)), "inicio": "01/01/2020", "rem": 60, "rem_modo": "depois"})["fracoes"][0]
ok(a["q"] == "0a11m25d" and a["data"] == "25/12/2020" and d["q"] == "1a0m0d" and d["data"] == "01/11/2020", "remidos antes/depois: %s %s" % (a, d))
# outra fração e erros
r = rc.calcular({"fita": F((5, 0, 0)), "inicio": "01/01/2020", "outra": "2/5"})
ok(r["outra"]["q"] == "2a0m0d" and r["outra"]["data"] == "31/12/2021", "2/5: %s" % r.get("outra"))
ok(rc.calcular({"fita": F((5, 0, 0)), "inicio": "01/01/2020", "outra": "55%"})["outra"]["rot"] == "55%", "55%")
r = rc.calcular({"fita": F((5, 0, 0)), "inicio": "31/02/2020", "outra": "x", "p1": "01/01/2020", "p2": "01/01/2019"})
ok(len(r["erros"]) == 2 and "termino" not in r and any("anterior" in x for x in r["erros"]), "erros: %s" % r["erros"])
ok("Término da pena: 31/12/2020" in rc.texto({"fita": F((1, 0, 0)), "inicio": "01/01/2020", "nota": "x"}, rc.calcular({"fita": F((1, 0, 0)), "inicio": "01/01/2020"})), "texto")

# registros na base e PDF, pela Api
TMP = tempfile.mkdtemp(prefix="apto_teste_calc_")
app.pasta_app = lambda: TMP
app.PASTA_BASES = os.path.join(TMP, "bases")
app.CONFIG = os.path.join(TMP, "rspe_config.json")
app._abrir = lambda c: None


class Janela:
    def __init__(self):
        self.fila = []

    def evaluate_js(self, c):
        pass

    def create_file_dialog(self, tipo, **kw):
        return self.fila.pop(0) if self.fila else None


api = app.Api()
api._janela = Janela()
ok("erro" in api.calc_gravar({"fita": F((1, 0, 0)), "inicio": "01/01/2020"}), "sem base: não registra")
api.nova_base("Teste calc")
e = {"fita": F((1, 0, 0)), "inicio": "01/01/2020", "assist": "Fulano · 1", "nota": "obs"}
r = api.calc_gravar(e)
ok(r.get("id") and len(r["itens"]) == 1 and r["itens"][0]["nota"] == "obs" and "término 31/12/2020" in r["itens"][0]["resumo"], "registro: %s" % r)
r2 = api.calc_gravar(dict(e, id=r["id"], nota="obs 2"))
ok(len(r2["itens"]) == 1 and r2["itens"][0]["nota"] == "obs 2" and r2["itens"][0]["dados"]["inicio"] == "01/01/2020", "atualizar: %s" % r2["itens"])
ok("erro" in api.calc_gravar({}), "nada a registrar")
ok(api.calc_excluir(r["id"])["itens"] == [], "excluir")
pdf = os.path.join(TMP, "calc.pdf")
api._janela.fila.append(pdf)
ok((api.calc_pdf(e) or {}).get("caminho") == pdf and open(pdf, "rb").read(4) == b"%PDF", "PDF")

if falhas:
    print("FALHOU (calculadora):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: calculadora (soma, período, término, frações, remidos antes/depois, interrupção, outra fração, erros, registros, PDF)")
