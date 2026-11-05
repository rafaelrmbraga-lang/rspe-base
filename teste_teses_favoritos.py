"""Jurisprudências: favoritos guardados na configuração deste computador (Api.teses_favoritos / Api.tese_favoritar) e a seção
"Favoritos" na aba (filtro, estrela no cartão)."""
import os, sys, tempfile, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
wv = types.ModuleType("webview"); wv.SAVE_DIALOG = 1; wv.FOLDER_DIALOG = 2; wv.OPEN_DIALOG = 0; sys.modules["webview"] = wv
import rspe_app as app
tmp = tempfile.mkdtemp(); app.CONFIG = os.path.join(tmp, "c.json")
api = app.Api()
falhas = []
def ok(c, m):
    if not c: falhas.append(m)
ok(api.teses_favoritos() == [], "começa sem favoritos")
ok(api.tese_favoritar("a1") == ["a1"], "marca um")
ok(api.tese_favoritar(7) == ["a1", "7"], "marca outro (id numérico vira texto)")
ok(api.tese_favoritar("a1") == ["a1", "7"], "não duplica")
ok(api.tese_favoritar("a1", False) == ["7"], "desmarca")
ok(app.Api().teses_favoritos() == ["7"], "fica gravado na configuração")
h = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui.html"), encoding="utf-8").read()
for t in ("tesFavoritar", "tesVerFav", "Favoritos", "☆ Favoritar", "★ Favorito", "Nenhum favorito ainda", "API().teses_favoritos()"):
    ok(t in h, "ui.html: " + t)
if falhas:
    print("FALHOU (favoritos): " + "; ".join(falhas)); sys.exit(1)
print("ok: jurisprudências favoritas (gravar, desmarcar, filtro e estrela na aba)")
