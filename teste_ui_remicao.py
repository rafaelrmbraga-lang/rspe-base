"""Aba Ficha disciplinar (7.15.3): visão inicial didática - Diagnóstico e "O que pedir"; na visualização detalhada, "Remições do RSPE e
o que cada uma cobre" (com "Fora de qualquer remição"), o vínculo trabalho x atestado e os documentos (✓ Homologado).
Confere (1) as peças da tela no ui.html e (2) a ligação remição -> documentos/períodos que rspe_remicao.comparacao expõe (N["ligacao"]),
num caso fictício: mesmo valor e data (certo), remição sem documento cobrindo o trabalho sem atestado mais próximo (inferido), remição
pequena sem documento (nenhum) e atestado posterior à última decisão (fora de qualquer remição). Dados fictícios. Rodar: python teste_ui_remicao.py"""
import os
import sys
import types

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf
from teste_remicao_714 import R, T, A, F, HOJE

DIR = os.path.dirname(os.path.abspath(__file__))
UI = open(os.path.join(DIR, "ui.html"), encoding="utf-8").read()
falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


try:
    # ---- 1) tela: as três peças e onde cada uma aparece ----
    for f_ in ("fdOQuePedir(r,N)", "fdCobertura(r,N)", "fdAcoes(r,N)"):
        ok(f_ in UI, "ui: função %s" % f_)
    for t_ in ("<b>O que pedir</b>", "<b>Remições do RSPE e o que cada uma cobre</b>", "Vínculos trabalho × atestado", "Documentos da ficha",
               "Fora de qualquer remição", "Nada a pedir nem a conferir agora", "ui.fdFeito(", "'Pedir atestado à unidade'",
               "'Requerer a remição'", "'Conferir a decisão'", "'Acompanhar'", "mesmo valor e data"):
        ok(t_ in UI, "ui: texto %r" % t_)
    simples = "if(!det) return `<div class=\"fdn\">${AV}${DQ}${this.fdOQuePedir(r,N)}${BT}</div>`;"
    ok(simples in UI and "Pendências apontadas</div>" not in UI, "ui: visão simples só com o diagnóstico, \"O que pedir\" e o botão do detalhe")
    q1 = UI.index(simples) + len(simples)
    det = UI[q1:UI.index("fdn-nota", q1)]
    ok("${DQ}${BT}${this.fdCobertura(r,N)}" in det and "${C}" in det and "${D}" in det and "fdOQuePedir" not in det,
       "ui: detalhe com diagnóstico, cobertura, vínculos (C) e documentos (D)")
    ok("Linha do tempo do trabalho" not in UI and "fdLinhaTempo" not in UI, "ui: sem linha do tempo")
    ok("Copiar o texto pronto" not in UI and 'class="fdx-c"' not in UI, "ui: sem botão Copiar em cada ação")
    ok("A) Comparação" not in UI and "E) Remições no RSPE" not in UI, "ui: comparação de totais e lista de remições (repetidas) fora")
    ok("ui.vincAbrir(this" in UI and "ui.fdConferir(" in UI, "ui: Vincular atestado e ✓ Homologado continuam acessíveis")

    # ---- 2) ligação remição -> documentos/períodos num caso fictício ----
    f = F([T("COPA", "01.03.2021", "30.06.2021"), T("MARCENARIA", "03.01.2022", "30.04.2022"), T("COSTURA", "01.02.2026", "30.06.2026")],
          [A("001/2021", "05.07.2021", "01/03/2021", "30/06/2021", 30, 90, "Copa", autos="0000001-11.2020.8.12.0001"),
           A("090/2026", "01.08.2026", "01/02/2026", "30/06/2026", 40, 120, "Costura", autos="0000001-11.2020.8.12.0001")])
    o = rf.comparativo(R((30, "20/07/2021", None), (25, "20/05/2022", "30/04/2022"), (2, "10/01/2023", None)), f, HOJE)
    N = o["fd_novo"]
    G = N.get("ligacao") or []
    ok(len(G) == 3 and all(g["i"] is not None for g in G), "ligação: uma linha por remição do RSPE: %s" % G)
    por = {g["dias"]: g for g in G}
    docs = {d["chave"]: d for d in N["docs"]}
    g30, g25, g2 = por.get(30.0) or {}, por.get(25.0) or {}, por.get(2.0) or {}
    ok(g30.get("grau") == "certo" and [docs[c]["num"] for c in g30.get("docs") or []] == ["001/2021"], "ligação: 30 dias = atestado 001/2021 (certo): %s" % g30)
    ok(abs(sum((docs[c]["dias"] or 0) for c in g30.get("docs") or []) - 30) < 0.01, "ligação: a soma dos documentos fecha com a remição")
    ok(g25.get("grau") == "inferido" and not g25.get("docs") and [t["local"] for t in g25.get("trab") or []] == ["Marcenaria"],
       "ligação: 25 dias sem documento -> trabalho sem atestado na Marcenaria (inferido): %s" % g25)
    s25 = sum(t["dias"] for t in g25.get("trab") or [])
    ok(abs(s25 - 25) <= 1, "ligação: o trabalho coberto soma os 25 dias (≈ %s)" % s25)
    ok(abs(s25 - N["talvez_dias"]) <= 1, "ligação: a mesma conta do \"pode já estar remido\" (%s x %s)" % (s25, N["talvez_dias"]))
    ok(g2.get("grau") == "nenhum" and not g2.get("docs") and not g2.get("trab"), "ligação: 2 dias sem documento, não cobre trabalho: %s" % g2)
    lig = {c for g in G for c in g["docs"]}
    d90 = next(d for d in N["docs"] if d["num"] == "090/2026")
    ok(d90["chave"] not in lig and d90["posterior"] and not docs[g30["docs"][0]]["posterior"],
       "ligação: atestado 090/2026, posterior à última decisão, fora de qualquer remição")
    # a exposição não muda a conta: os totais e a estimativa continuam os mesmos
    ok(N["comp"] == 70 and N["dif"] == 13, "totais: %s %s" % (N["comp"], N["dif"]))
except Exception as e:  # noqa: BLE001
    import traceback
    traceback.print_exc()
    falhas.append("exceção: %r" % e)

if falhas:
    print("FALHAS:")
    for x in falhas:
        print(" -", x)
    sys.exit(1)
print("ok: aba Ficha (7.15.3): visão simples com \"O que pedir\", detalhe com remições x cobertura, vínculos e documentos; ligação remição -> documentos")
