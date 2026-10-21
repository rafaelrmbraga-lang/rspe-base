"""Teste de regressão: conferência 7.14.2 (terceira rodada), frente "prescrição e extinção". Casos sintéticos, sem dados reais.
1. (#2) lista do evento cortada pelo SEEU: a ação da execução selecionada em outro incidente (livramento, comutação) conta como
   listada - a custódia depois do trânsito dela é cumprimento dela e sai da detração das demais.
2. (#3) guia sem cálculo: a prisão provisória pelo próprio processo, registrada só na ficha, entra no término calculado.
3. (#4) detração por prisão em outro processo: não se propõe quando outra execução da pessoa estava em curso no período (CP, art. 42).
4. (#20) idade incoerente (art. 115 a verificar) também na contagem com a ação fora do cumprimento: a progressão da execução durante a
   prisão pelas outras ações não neutraliza a variante.
5. (#21) prisão por outro processo depois da fuga, com regressão ou perda de dias remidos nesta execução: cumprimento desde a prisão.
6. (#22) indulto sem a marca "(Indultada)", "Extinto: Não" e pena total que só fecha com essas penas: a verificar (pode ser só a multa),
   sem tirar a pena das contas.
7. (extinção, caso 28) pena remanescente alcançada durante a prisão em outro processo: soma pelo calendário (1m2d de 09/07 = 10/08).
Rodar: python teste_conf3_prescricao.py (sai com código 1 se algum caso falhar)."""
import sys
import types
from datetime import date, timedelta

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_scraper as rs  # noqa: E402
import rspe_prescricao as rp  # noqa: E402
import rspe_view as rv  # noqa: E402
import rspe_auditoria as ra  # noqa: E402
import rspe_ficha as rf  # noqa: E402

HOJE = date(2026, 10, 21)
falhas = []
FURTO = "CAPUT: Subtrair, para si ou para outrem, coisa alheia móvel., Reclusão: 1 a 4 anos E Multa"
P1, P2, P3 = "0000101-11.2003.8.12.0001", "0000202-22.2004.8.12.0001", "0000303-33.2005.8.12.0001"
PRI, INT = "PRISÃO/INÍCIO DE CUMPRIMENTO", "INTERRUPÇÃO"


def confere(cond, msg):
    if not cond:
        falhas.append(msg)


def pena(a, m=0, d=0):
    return "%d ano(s), %d mês(es) e %d dia(s)" % (a, m, d)


def crime(fato, tr, pn, proc=P1, **kw):
    c = {"processo_criminal": proc, "data_infracao": fato, "data_denuncia": "", "data_sentenca": "", "transito_mp": tr,
         "transito_processo": tr, "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto", "tipo_penal": FURTO, "pena_imposta": pn,
         "pena_total_processo": "%s - PENA ORIGINÁRIA" % pn, "reincidente_comum": "N", "reincidente_especifico": "N", "extinto": "Não"}
    c.update(kw)
    return c


def ev(data, motivo, tipo=PRI, proc="", **kw):
    e = {"tipo": tipo, "motivo": motivo, "complemento": "", "data": data, "data_decisao": "", "data_referencia": "", "processos": proc}
    e.update(kw)
    return e


def inc(tipo, data, comp="", procs=""):
    return {"tipo": tipo, "complemento": comp, "data_decisao": data, "data_referencia": data, "situacao": "CONCEDIDO", "processos": procs}


def reg(crimes, eventos=(), incidentes=(), **kw):
    r = {"_crimes": list(crimes), "_eventos": list(eventos), "_incidentes": list(incidentes), "data_nascimento": "01/01/1960",
         "data_geracao_rspe": "06/10/2026", "situacao_cumprimento": "EM CUMPRIMENTO", "processo_execucao": "0009999-99.2003.8.12.0001"}
    r.update(kw)
    return r


def linha(r, proc):
    return next(l for l in rp.analisar(r, HOJE)["presc_linhas"] if l["proc_crim"] == proc)


# ---------------- 1. (#2) lista cortada: ação selecionada em outro incidente ----------------
# P1 (deste crime) transita em 2007; P2, transitada em 01/07/2005 durante a prisão de 01/01/2005 (lista cortada, só P1 impresso)
evs = [ev("01/01/2005", "RECAPTURA/REINÍCIO DE CUMPRIMENTO", proc=P1, processos_incompletos=True), ev("31/12/2005", "FUGA", tipo=INT),
       ev("01/01/2009", "RECAPTURA/REINÍCIO DE CUMPRIMENTO", proc=P1)]
cr = [crime("01/01/2004", "01/01/2007", pena(4), proc=P1), crime("01/01/2003", "01/07/2005", pena(3), proc=P2)]
l0 = linha(reg(cr, evs), P1)
lc = inc("LIVRAMENTO CONDICIONAL", "01/06/2010", "01/06/2010", "%s, %s" % (P1, P2))
l1 = linha(reg(cr, evs, [lc]), P1)
confere(l0["ppe_detracao_dias"] == 365, "1: sem outra seleção, a prisão toda é detração de P1: %s" % l0["ppe_detracao_dias"])
confere(l1["ppe_detracao_dias"] == 181, "1: P2 selecionada no livramento - a custódia depois do trânsito dela é cumprimento dela: %s"
        % l1["ppe_detracao_dias"])

# ---------------- 2. (#3) guia sem cálculo + prisão provisória só na ficha ----------------
cr = [crime("01/06/2024", "01/03/2025", pena(1), proc=P1)]
base = dict(pena_total="1a0m0d", pena_cumprida="0a0m0d", pena_remanescente="1a0m0d")
r0 = reg(cr, [ev("01/01/2026", "PRISÃO DEFINITIVA", proc=P1)], **base)
t0 = rv.termino_calc(r0)
r1 = reg(cr, [ev("01/01/2026", "PRISÃO DEFINITIVA", proc=P1)], **base)
f = {"eventos": [{"data": "01.07.2024", "texto": "Entrada na Unidade Penal: PDIB, Procedente: DP MARACAJU - INTERIOR, Conforme OF/CI 1/2024."},
                 {"data": "30.07.2024", "texto": "Saída da Unidade Penal: PDIB, Destino: , Motivo: Alvará de Soltura, Conforme Alvará: %s" % P1}]}
rf.reconciliar_eventos(r1, f)
confere(r1.get("_detracao_ficha") == [("01/07/2024", "30/07/2024", P1)], "2: prisão da ficha pelo próprio processo: %s" % r1.get("_detracao_ficha"))
t1 = rv.termino_calc(r1)
confere(t0 and t1 and (t0 - t1).days == 30, "2: término antecipado em 30 dias pela detração da ficha: %s x %s" % (t0, t1))
confere("ficha SIAPEN" in (rv.custodia_sem_calculo(r1) or {}).get("ficha_txt", ""), "2: a nota do término cita a ficha")
# prisão por processo que não é desta execução: não entra
r2 = reg([crime("01/06/2024", "01/03/2025", pena(1), proc=P2)], [ev("01/01/2026", "PRISÃO DEFINITIVA", proc=P2)], **base)
r2["_detracao_ficha"] = [("01/07/2024", "30/07/2024", P1)]
confere(rv.termino_calc(r2) == t0, "2: prisão por outro processo não entra: %s" % rv.termino_calc(r2))

# ---------------- 3. (#4) detração em outro processo com outra execução em curso ----------------
cr = [crime("19/02/2023", "01/03/2025", pena(0, 1, 14), proc=P1)]
r = reg(cr, [], [], pena_total="0a1m14d", pena_remanescente="0a1m14d",
        _custodias_ficha_outro=[("01/11/2023", "14/12/2023", ["0900842-27.2023.8.12.0005"])])
its = ra._detracao_outro_processo(r, cr, cr, [])
confere(len(its) == 1 and "alcança a pena remanescente" in its[0]["detalhe"], "3: sem outra execução, a hipótese sai: %s" % its)
r["_outras_condenacoes"] = [crime("01/01/2005", "01/01/2006", pena(5), proc=P3, extinto="Sim", data_extincao="04/03/2025",
                                  _execucao="0000891-89.2006.8.12.0005")]
r["_outras_execucoes"] = [{"processo": "0000891-89.2006.8.12.0005", "encerrada": True}]
confere(ra._detracao_outro_processo(r, cr, cr, []) == [], "3: outra execução em curso no período (extinta só em 2025): não se propõe")
r["_outras_condenacoes"][0]["data_extincao"] = "01/10/2023"
confere(len(ra._detracao_outro_processo(r, cr, cr, [])) == 1, "3: a outra execução já extinta antes da prisão: a hipótese volta")

# ---------------- 4. (#20) art. 115 com idade incoerente e ação fora do cumprimento ----------------
# P2: fato com 17 anos pela data do RSPE (incoerente); preso pelo P1 de 02/01/2007 até a fuga de 21/06/2009, livre até 20/08/2011;
# P2 só entra no somatório de 03/09/2017; progressão da execução em 17/12/2008 (durante a prisão pelo P1)
cr = [crime("02/01/2007", "01/06/2007", pena(6), proc=P1),
      crime("04/03/2004", "25/07/2007", pena(1, 8), proc=P2)]
evs = [ev("02/01/2007", "PRISÃO EM FLAGRANTE", proc=P1), ev("21/06/2009", "FUGA", tipo=INT),
       ev("20/08/2011", "RECAPTURA/REINÍCIO DE CUMPRIMENTO", proc=P1)]
incs = [inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "17/12/2008", "Semiaberto - Progressão de Regime"),
        inc("SOMATÓRIO DAS PENAS", "03/09/2017", "", "%s, %s" % (P1, P2))]
l = linha(reg(cr, evs, incs, data_nascimento="22/04/1986"), P2)
confere(l["ppe_status"].startswith("A VERIFICAR") and "115" in l["ppe_status"], "4: depende do art. 115: %s" % l["ppe_status"])
l = linha(reg(cr, evs, incs, data_nascimento="22/04/1966"), P2)
confere(l["ppe_status"].startswith("Não prescrita"), "4: idade coerente (maior de 21): não prescrita: %s" % l["ppe_status"])

# ---------------- 5. (#21) regressão / perda de remição depois da fuga: cumprimento desde a prisão ----------------
cr = [crime("19/01/2011", "19/05/2014", pena(12), proc=P1), crime("06/05/2016", "11/12/2018", pena(2), proc=P2)]
evs = [ev("28/02/2011", "PRISÃO PROVISÓRIA", proc=P1), ev("29/09/2015", "FUGA", tipo=INT), ev("06/05/2016", "PRISÃO EM FLAGRANTE", proc=P2)]
for t_, c_ in (("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Fechado - Regressão"), ("DIAS PERDIDOS NA REMIÇÃO", "27")):
    l = linha(reg(cr, evs, [inc(t_, "08/09/2016", c_)]), P1)
    lt = l["ppe_linha_tempo"]
    confere(any(x["tipo"] == "cumprimento" and x["inicio"] == "06/05/2016" for x in lt), "5: %s - cumprimento desde a prisão: %s" % (c_, lt))
    confere(not any(x["tipo"] == "outro_motivo" and x["inicio"] == "06/05/2016" for x in lt), "5: %s - não é suspensão" % c_)
# regressão cautelar não prova o retorno
l = linha(reg(cr, evs, [inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "08/09/2016", "Fechado - Regressão Cautelar")]), P1)
confere(any(x["tipo"] == "outro_motivo" and x["inicio"] == "06/05/2016" for x in l["ppe_linha_tempo"]), "5: regressão cautelar: segue suspensão")

# ---------------- 6. (#22) indulto sem baixa no cálculo ----------------
def _ind(pt):
    cs = [crime("01/01/2010", "01/01/2011", pena(3), proc=P1), crime("01/01/2012", "01/01/2013", pena(2), proc=P2),
          crime("01/01/2014", "01/01/2015", pena(1), proc=P3)]
    r = reg(cs, [], [inc("INDULTO", "28/05/2024", "DECRETO Nº 11.302, DE 22 DE DEZEMBRO DE 2022", P1)], pena_total=pt)
    rs.aplicar_extincoes(r, cs, r["_incidentes"])
    return r, cs[0]
r, c = _ind("6a0m0d")
confere(not c["extinto"].startswith("S") and (c.get("indulto_duvida") or {}).get("multa"), "6: pena total com a pena indultada: a verificar: %s" % c)
confere(any(l["proc_crim"] == P1 for l in rp.analisar(r, HOJE)["presc_linhas"]), "6: o processo continua na prescrição")
confere(any(i["tipo"] == "indulto-sem-baixa-pode-ser-so-da-multa" for i in ra.auditar(r, HOJE)["aud_itens"]), "6: item da Auditoria")
r, c = _ind("3a0m0d")
confere(c["extinto"].startswith("S") and not c.get("indulto_duvida"), "6: pena total sem a pena indultada: extinta: %s" % c)
r, c = _ind("6a0m0d")
r["_crimes"][0]["processo_situacao"] = "Indultada"
rs.aplicar_extincoes(r, r["_crimes"], r["_incidentes"])
confere(r["_crimes"][0]["extinto"].startswith("S"), "6: com a marca (Indultada), extinta")

# ---------------- 7. (extinção) remanescente alcançado na prisão em outro processo: pelo calendário ----------------
cr = [crime("01/01/2024", "01/06/2024", pena(1), proc=P1)]
evs = [ev("01/07/2025", "PRISÃO DEFINITIVA", proc=P1), ev("09/07/2026", "INTERRUPÇÃO POR PRISÃO EM OUTRO PROCESSO", tipo=INT)]
r = reg(cr, evs, [], pena_total="1a0m0d", pena_cumprida="0a10m28d", pena_remanescente="0a1m2d")
h = rv.extincao(r, {"presc_linhas": []}, True)["ext_hipoteses"]
if rv.HOJE >= date(2026, 8, 10):
    confere("alcançada em 10/08/2026" in h, "7: 09/07/2026 + 1m2d - 1 = 10/08/2026: %s" % h)

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for x in falhas:
        print(" -", x)
    sys.exit(1)
print("teste_conf3_prescricao: ok")
