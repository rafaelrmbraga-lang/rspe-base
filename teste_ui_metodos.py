"""Toda função da tela chamada como ui.X( ou this.X( existe no ui.html (7.30.1: a limpeza do Quadro do Usuário levou junto
fichaIcoHtml e abrirBtnHtml, e a aba Jurisprudências quebrou com "this.fichaIcoHtml is not a function"). Rodar: python teste_ui_metodos.py"""
import os
import re
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
UI = open(os.path.join(DIR, "ui.html"), encoding="utf-8").read()
JS = "\n".join(re.findall(r"<script>(.*?)</script>", UI, re.S))
# definidos: "  nome(…){", "  async nome(", "nome:" (propriedade/função do objeto ui) e "ui.nome=" (fora do objeto)
definidos = set(re.findall(r"^\s*(?:async\s+)?([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{", JS, re.M))
definidos |= set(re.findall(r"^\s*([A-Za-z_$][\w$]*)\s*:", JS, re.M))
definidos |= set(re.findall(r"\bui\.([A-Za-z_$][\w$]*)\s*=(?!=)", JS))
usados = set(re.findall(r"\b(?:ui|this)\.([A-Za-z_$][\w$]*)\s*\(", UI))
nativos = {"toast", "call", "apply", "bind", "hasOwnProperty", "focus", "click", "remove", "querySelector", "querySelectorAll", "getAttribute",
           "setAttribute", "closest", "contains", "push", "split", "map", "filter", "join", "replace", "addEventListener", "postMessage", "xxx"}
faltam = sorted(u for u in usados - definidos - nativos if not u.startswith("_"))
if faltam:
    print("FALHA: chamadas sem definição no ui.html: " + ", ".join(faltam))
    sys.exit(1)
print("ok: toda função da tela chamada (ui.X / this.X) existe (%d)" % len(usados))
