"""Teste de regressão do indicador de progressão antecipada (ícone ao lado do nome): regime fechado ou semiaberto em curso,
progressão em 1 a 60 dias, crimes sem violência nem grave ameaça, conduta Boa/Ótima sem falta, trabalho (externo conta);
amarelo com ficha de mais de 90 dias, sem ficha ou crime sem a marcação. Rodar: python teste_progressao_antecipada.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_view as rv

HOJE = date(2026, 10, 8)
falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def crime(vga="N", ext="Não"):
    return {"data_infracao": "10/05/2019", "vga": vga, "extinto": ext, "tipo_processo": "ACAO PENAL", "artigo": "ART 155: Furto"}


def rspe(**kw):
    r = {"regime_atual": "Fechado - ATIVO", "status_execucao": "ATIVO", "falta_12m": "não consta", "_crimes": [crime()]}
    r.update(kw)
    return r


def ficha(**kw):
    f = {"conduta": "OTIMA", "data_impressao": "01.10.2026", "eventos": [], "trabalho": []}
    f.update(kw)
    return f


def pa(r, f, dias=48, trab="Cozinha desde 14.08.2025", est=None, interr=False):
    return rv.progressao_antecipada(r, f, {"prog_dias": dias, "prog": "25/11/2026", "fd_trab": trab}, est, interr, HOJE)


x = pa(rspe(), ficha())
ok(x["pa_ok"] and not x["pa_quase"], "elegível: %s" % x)
ok(pa(rspe(regime_atual="Semiaberto - ATIVO"), ficha())["pa_ok"], "semiaberto")
ok(not pa(rspe(regime_atual="Aberto - ATIVO"), ficha())["pa_ok"], "aberto")
ok(not pa(rspe(), ficha(), interr=True)["pa_ok"], "interrompida")
ok(not pa(rspe(), ficha(), est=("lc", "Em livramento"))["pa_ok"], "em livramento")
# janela de 1 a 60 dias
ok(pa(rspe(), ficha(), dias=60)["pa_ok"] and pa(rspe(), ficha(), dias=1)["pa_ok"], "60 e 1 dia")
for d in (61, 0, -10, None):
    x = pa(rspe(), ficha(), dias=d)
    ok(not x["pa_ok"] and not x["pa_quase"], "fora da janela (%s): %s" % (d, x))
# violência ou grave ameaça; extinto não conta; sem marcação = amarelo
ok(not pa(rspe(_crimes=[crime(), crime(vga="S")]), ficha())["pa_ok"], "crime com violência")
ok(pa(rspe(_crimes=[crime(), crime(vga="S", ext="Sim")]), ficha())["pa_ok"], "violento extinto não conta")
x = pa(rspe(_crimes=[crime(vga="")]), ficha())
ok(not x["pa_ok"] and x["pa_quase"], "sem marcação = amarelo: %s" % x)
# conduta, falta, trabalho
ok(not pa(rspe(), ficha(conduta="RESPONDE PADIC/PDIB"))["pa_ok"], "PADIC")
ok(pa(rspe(), ficha(conduta="BOA"))["pa_ok"], "conduta boa")
ok(not pa(rspe(falta_12m="SIM"), ficha())["pa_ok"], "falta")
ok(not pa(rspe(), ficha(), trab="sem trabalho em curso")["pa_ok"], "sem trabalho")
ok(pa(rspe(), ficha(trabalho=[{"inicio": "01.06.2026", "fim": "", "setor": "EMPRESA X", "externo": True}]), trab="sem trabalho em curso")["pa_ok"],
   "trabalho externo")
# amarelo
x = pa(rspe(), ficha(data_impressao="01.05.2026"))
ok(not x["pa_ok"] and x["pa_quase"], "ficha antiga = amarelo")
x = pa(rspe(), None)
ok(not x["pa_ok"] and x["pa_quase"], "sem ficha = amarelo")
ok(not pa(rspe(_crimes=[crime(vga="S")]), None)["pa_quase"], "violento sem ficha não fica amarelo")

if falhas:
    print("FALHOU (progressão antecipada):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: progressão antecipada (regime, janela de 60 dias, violência, conduta, trabalho, amarelo)")
