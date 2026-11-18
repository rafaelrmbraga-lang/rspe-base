"""Barra fixa das funções (7.19.0): APTO | Execução | SEI | Atendimentos | Quadro, sempre visível no topo. Execução mostra o APTO
das bases (tela inicial, cabeçalho e abas); as outras funções escondem a Execução e mostram a página da função. Ctrl+1 a Ctrl+4
trocam de função. Confere o texto do ui.html. Rodar: python teste_ui_funcoes.py"""
import os
import re
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
UI = open(os.path.join(DIR, "ui.html"), encoding="utf-8").read()
CSS = re.search(r"<style>(.*?)</style>", UI, re.S).group(1)
falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


ok('<body class="fn-exec">' in UI, "abre na Execução (body.fn-exec)")
bar = re.search(r'<nav class="fnbar" id="fnbar"[^>]*>(.*?)</nav>', UI, re.S)
ok(bar, "barra das funções ausente")
if bar:
    nomes = re.findall(r'<button class="fn[^"]*" role="tab" id="fn_(\w+)"[^>]*>.*?</svg>([^<]+)</button>', bar.group(1), re.S)
    ok(nomes == [("exec", "Execução"), ("sei", "SEI"), ("atend", "Atendimentos"), ("quadro", "Quadro")], "ordem das funções: %s" % nomes)
    ok(UI.index('id="fnbar"') < UI.index('<div class="top">'), "a barra vem antes do cabeçalho da Execução")
for sel in ("body:not(.fn-exec) .top", "body:not(.fn-exec) .corpo", "body:not(.fn-exec) .welcome.on", "body:not(.fn-exec) .fnpag"):
    ok(sel in CSS, "CSS: %s" % sel)
ok(re.search(r"\.welcome,\.loading\{top:var\(--fn-h\)\}", CSS), "tela inicial e de carregamento abaixo da barra")
ok("ui.funcao=function(id)" in UI and "ui.FUNCOES={" in UI, "ui.funcao / ui.FUNCOES")
for k in ("sei", "atend", "quadro"):
    ok(re.search(r"\b%s:\{titulo:'[^']+', html:" % k, UI), "página da função %s" % k)
ok("['exec','sei','atend','quadro'][+e.key-1]" in UI, "atalhos Ctrl+1 a Ctrl+4")
ok("carregando(txt){ if(this.fn!=='exec') this.funcao('exec');" in UI, "abrir/importar base volta para a Execução")
if falhas:
    print("FALHA: " + "; ".join(falhas))
    sys.exit(1)
print("ok: barra fixa APTO | Execução | SEI | Atendimentos | Quadro, Execução com o APTO das bases, Ctrl+1 a Ctrl+4")
