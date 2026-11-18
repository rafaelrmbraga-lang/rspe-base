"""Barra fixa das funções (7.19.0): APTO | Atendimentos | Execução | SEEU | SEI | Quadro | Relatório, sempre visível no topo. Execução mostra o APTO
das bases (tela inicial, cabeçalho e abas); as outras funções escondem a Execução e mostram a página da função. Ctrl+1 a Ctrl+6
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
    nomes = re.findall(r'<button class="fn[^"]*" role="tab" id="fn_(\w+)"[^>]*>.*?</svg>([^<]+)(?:<span class="fnbadge"[^>]*></span>)?</button>', bar.group(1), re.S)
    ok(nomes == [("atend", "Atendimentos"), ("exec", "Execução"), ("seeu", "SEEU"), ("sei", "SEI"), ("quadro", "Quadro"), ("rel", "Relatório"),
                     ("geo", "Dados prisionais"), ("teses", "Jurisprudências")], "ordem das funções: %s" % nomes)
    ok(UI.index('id="fnbar"') < UI.index('<div class="top">'), "a barra vem antes do cabeçalho da Execução")
for sel in ("body:not(.fn-exec) .top", "body:not(.fn-exec) .corpo", "body:not(.fn-exec) .welcome.on", "body:not(.fn-exec) .fnpag"):
    ok(sel in CSS, "CSS: %s" % sel)
ok(re.search(r"\.welcome,\.loading\{top:var\(--fn-h\)\}", CSS), "tela inicial e de carregamento abaixo da barra")
ok("ui.funcao=function(id)" in UI and "ui.FUNCOES={" in UI, "ui.funcao / ui.FUNCOES")
for k in ("seeu", "sei"):
    ok(re.search(r"\b%s:\{titulo:'[^']+', html:" % k, UI), "página da função %s" % k)
for k in ("atend", "quadro", "rel"):
    ok(re.search(r"\b%s:\{titulo:'[^']+', painel:'%s'\}" % (k, k), UI), "função %s abre o painel de atendimentos (moldura)" % k)
ok("M.src='atendimentos/painel.html#'+F.painel" in UI, "moldura do painel")
ok(".fnpag iframe[hidden]{display:none}" in CSS, "moldura escondida não aparece sob SEI/SEEU/Execução")
ok("/^atd_[a-z_]+$/.test(met)" in UI, "a moldura só chama as funções atd_* do Python")
ok("['atend','exec','seeu','sei','quadro','rel','geo','teses'][+e.key-1]" in UI and "/^[1-8]$/" in UI, "atalhos Ctrl+1 a Ctrl+8")
# 7.31: Dados prisionais e Jurisprudências na barra fixa (fora do menu da Execução), funcionando sem base aberta
for k in ("geo", "teses"):
    ok(re.search(r"\b%s:\{titulo:'[^']+', ferramenta:'%s'\}" % (k, k), UI), "função %s na barra" % k)
nav = re.search(r"NAV_GRUPOS:\[(.*?)\]\],\n", UI)
ok(nav and "'geo'" not in nav.group(1) and "'teses'" not in nav.group(1), "Dados prisionais e Jurisprudências saíram do menu da Execução")
for sel in ("body.fn-ferr .welcome.on{display:none}", "body.fn-ferr .top,body.fn-ferr .tabs"):
    ok(sel in CSS, "CSS: %s" % sel)
ok("carregando(txt){ if(this.fn!=='exec') this.funcao('exec');" in UI, "abrir/importar base volta para a Execução")
if falhas:
    print("FALHA: " + "; ".join(falhas))
    sys.exit(1)
print("ok: barra fixa APTO | Atendimentos | Execução | SEEU | SEI | Quadro | Relatório | Dados prisionais | Jurisprudências, Ctrl+1 a Ctrl+8")
