"""Teste de regressão: 3ª revisão da prescrição (relatorios3/prescricao.md, A1 a A8) e 4ª revisão, leitura do código (relatorios4/
codigo_prescricao.md, A1 a A13), mais o incidente "ALTERAÇÃO DE DATA-BASE" que não é progressão. Casos sintéticos montados pelos
revisores (r3_presc, r4_presc) e dos registros reais da base. Rodar: python teste_prescricao_rev4.py (sai com 1 se algum falhar)."""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_prescricao as rp
import rspe_view as rv

HOJE = date(2026, 10, 8)
EXEC = "0000999-99.2012.8.12.0001"
P = "0000100-10.2009.8.12.0001"
falhas = []


def confere(cond, msg):
    if not cond:
        falhas.append(msg)


def crime(**k):
    c = {"processo_criminal": P, "vara_condenacao": "1ª Vara Criminal", "data_denuncia": "01/02/2009", "data_sentenca": "01/06/2011",
         "transito_mp": "10/01/2012", "transito_processo": "10/01/2012", "pena_total_processo": "1a0m0d - PENA ORIGINÁRIA", "lei": "2848/40 - Código Penal",
         "artigo": "ART 155: Furto", "tipo_penal": "CAPUT: Subtrair..., Reclusão: 1 a 4 anos E Multa", "pena_imposta": "1 ano(s), 0 mês(es) e 0 dia(s)",
         "data_infracao": "01/01/2009", "reincidente_comum": "N", "reincidente_especifico": "N", "extinto": "Não", "fracao_progressao": "1/6 - Comum"}
    c.update(k)
    return c


def reg(crimes, eventos=(), inc=(), **k):
    r = {"data_nascimento": "01/01/1970", "pena_total": "1a0m0d", "pena_cumprida": "0a0m0d", "pena_remanescente": "1a0m0d",
         "data_geracao_rspe": "06/10/2026", "processo_execucao": EXEC, "situacao_cumprimento": "EM CUMPRIMENTO",
         "_crimes": list(crimes), "_eventos": list(eventos), "_incidentes": list(inc)}
    r.update(k)
    return r


def ev(tipo, motivo, data, proc=""):
    return {"tipo": tipo, "motivo": motivo, "complemento": "", "data": data, "data_decisao": "", "data_referencia": "", "processos": proc}


PRI, INT = "PRISÃO/INÍCIO DE CUMPRIMENTO", "INTERRUPÇÃO"


def aj(r, valores, idx=0):
    ch = rp.chave_ajuste(r["_crimes"][idx], {})
    r["_presc_ajustes"] = {ch: {"valores": valores, "_data": "08/10/2026"}}
    return r


def ficha(*evs):
    return {"eventos": [{"data": d, "texto": t} for d, t in evs]}


def run(r, f=None, idx=0):
    return rp.analisar(r, HOJE, f)["presc_linhas"][idx]


# ---------------- 3ª revisão ----------------
# A1: a fuga do RSPE encerra a custódia da ficha (a ficha não registrou a saída): a fuga é analisada, não vira "preso por outro motivo"
c3 = crime(pena_imposta="3 ano(s), 0 mês(es) e 0 dia(s)", pena_total_processo="3a0m0d - PENA ORIGINÁRIA", transito_mp="01/01/2015",
           transito_processo="01/01/2015", data_infracao="01/01/2013", data_denuncia="01/02/2013", data_sentenca="01/06/2014")
evs3 = [ev(PRI, "PRISÃO DEFINITIVA", "01/02/2015", P), ev(INT, "FUGA", "01/02/2016"), ev(PRI, "RECAPTURA", "01/02/2022", P)]
L = run(reg([c3], evs3), ficha(("01.02.2015", "Entrada na Unidade Penal: IPCG, Procedente: DP")))
confere(L["ppe_saldos"] and L["ppe_saldos"][0]["evasao"] == "01/02/2016" and not any(p["tipo"] == "outro_motivo" for p in L["ppe_linha_tempo"]),
        "R3-A1: fuga do RSPE apagada pela custódia aberta da ficha: %s" % L["ppe_status"])
confere(L["ppe_status"].startswith("Prescrição executória aparente"), "R3-A1: fuga de 6 anos com saldo de 2 anos: %s" % L["ppe_status"])
# outras redações de saída na ficha
pf = rp._periodos_ficha(ficha(("01.01.2020", "Deu entrada no EPMC, procedente da DP-Coxim/MS"),
                              ("01.02.2020", "Deu Saída da Unidade Penal: EPJFC, Motivo: Transferência de Presidio Destino: IPCG"),
                              ("01.03.2020", "Deu saida do EPMC, por Revogação de Preventiva em cumprimento ao Alvará de Soltura"),
                              ("01.04.2020", "Entrada na Unidade Penal: CPAIG, Procedente: DP"),
                              ("01.05.2020", "EVASÃO DA CPA- OF. 415/20."),
                              ("01.06.2020", "Entrada na Unidade Penal: CPAIG, Procedente: DP"),
                              ("01.07.2020", "NÃO RETORNOU DO TRABALHO EXTERNO NA EMPRESA X"),
                              ("01.08.2020", "Entrada na Unidade Penal: IPCG, Procedente: DP"),
                              ("01.09.2020", "Deu saida do EPMRSAAC, dando cumprimento a Decisão Judicial de Prisão Domiciliar")))
confere([(p["ini"], p["fim"]) for p in pf] == [(date(2020, 1, 1), date(2020, 3, 1)), (date(2020, 4, 1), date(2020, 5, 1)),
                                               (date(2020, 6, 1), date(2020, 7, 1)), (date(2020, 8, 1), date(2020, 9, 1))],
        "R3-A1: redações de saída da ficha: %s" % [(p["ini"], p["fim"]) for p in pf])
confere(pf[1]["aberta"], "R3-A1: CPAIG (semiaberto) não reconhecida como unidade de cumprimento")
# entrada nos autos da própria execução, durante a fuga: cumprimento desta pena (indício de retomada), não "outro processo"
evs3b = [ev(PRI, "PRISÃO DEFINITIVA", "01/02/2015", P), ev(INT, "FUGA", "01/02/2016")]
L = run(reg([c3], evs3b), ficha(("10.02.2016", "Deu entrada no EPMC, procedente da DP, Mandado de Prisão contido nos Autos nº %s" % EXEC)))
confere(not any(p["tipo"] == "outro_motivo" for p in L["ppe_linha_tempo"]) and any("autos da própria execução" in p["fonte"] for p in L["ppe_linha_tempo"]),
        "R3-A1: entrada nos autos da execução tratada como outro processo")
confere(L["ppe_status"].startswith("A VERIFICAR: prescrição executória aparente, mas há indício de retomada"), "R3-A1: retomada pela ficha: %s" % L["ppe_status"])
# monitoramento sem processo: cumprimento; monitoramento por OUTRO processo: segue como suspensão (dúvida B1, do usuário)
L = run(reg([c3], evs3b), ficha(("10.02.2016", "Entrada na Unidade Penal: UNIDADE MISTA DE MONITORAMENTO VIRTUAL, Procedente: DP")))
confere(not any(p["tipo"] == "outro_motivo" for p in L["ppe_linha_tempo"]), "R3-A1: monitoramento sem outro processo tratado como prisão por outro processo")
L = run(reg([c3], evs3b), ficha(("10.02.2016", "Entrada na Unidade Penal: UNIDADE MISTA DE MONITORAMENTO VIRTUAL, Conforme Ofício: 0005555-55.2016.8.12.0001")))
confere(L["ppe_status"].startswith("Não corre (preso por outro processo desde 10/02/2016"), "R3-A1/B1: monitoramento por outro processo: %s" % L["ppe_status"])
# o texto mostra a data real da entrada, não o início do recorte
L = run(reg([crime()], []), ficha(("01.05.2011", "Deu entrada no EPMC, procedente da DP, Autos nº 0007777-77.2011.8.12.0001"),
                                  ("01.03.2012", "Deu saida do EPMC, por Alvará de Soltura, Autos nº 0007777-77.2011.8.12.0001")))
_f = [p for p in L["ppe_linha_tempo"] if "ficha SIAPEN" in p["fonte"]]
confere(_f and "entrada em 01/05/2011, considerada a partir de 10/01/2012" in _f[0]["fonte"] and _f[0]["fim"] == "01/03/2012",
        "R3-A1/R4-A8: texto da prisão da ficha: %s" % (_f and _f[0]))

# A2: a punitiva "a verificar" aparece na prioridade e tem rótulo
n, mot, _ = rv.prioridade({"presc_retro_cor": "amarelo"})
confere("prescrição punitiva a verificar" in mot, "R3-A2: prioridade sem a punitiva a verificar: %s" % mot)
confere(rv.ROTULO["presc_pp"].get("amarelo") == "A verificar", "R3-A2: rótulo amarelo da punitiva")

# A3: pela pena aplicada, a data sai dos números: novo crime e suspensão no resumo, no quadro e na fundamentação (Wanderson)
Q = "0000200-20.2021.8.12.0001"
cw = crime(pena_imposta="2 ano(s), 0 mês(es) e 0 dia(s)", pena_total_processo="2a0m0d - PENA ORIGINÁRIA", data_infracao="09/03/2015",
           data_denuncia="01/05/2015", data_sentenca="01/03/2017", transito_mp="03/07/2017", transito_processo="03/07/2017")
cq = crime(processo_criminal=Q, data_infracao="18/06/2021", data_denuncia="01/08/2021", data_sentenca="01/02/2022", transito_mp="01/05/2022",
           transito_processo="01/05/2022")
L = run(reg([cw, cq], [ev(PRI, "PRISÃO DEFINITIVA", "01/01/2018", P), ev(INT, "LIBERDADE PROVISÓRIA", "03/06/2020"),
                      ev(PRI, "PRISÃO EM FLAGRANTE", "05/07/2021", Q), ev(INT, "LIBERDADE PROVISÓRIA", "16/09/2021")]))
confere(L["ppe_status"] == "Prescrição executória aparente em 30/08/2025", "R3-A3: data: %s" % L["ppe_status"])
confere("novo crime de 18/06/2021" in L["ppe_resumo"] and "74 dias" in L["ppe_resumo"], "R3-A3: resumo: %s" % L["ppe_resumo"])
confere("74 dias" in L["ppe_quadro"]["prazo"] and "18/06/2021" in L["ppe_quadro"]["periodo"], "R3-A3: quadro: %s" % L["ppe_quadro"])
confere("somados 74 dias" in L["ppe_fund"] and "sem outra causa interruptiva" in L["ppe_fund"], "R3-A3: fundamentação sem a suspensão")

# A4: o intervalo passa do dobro do prazo: o acórdão (data não consta) não muda a intercorrente (Clemilson)
def intercorrente(tr):
    c = crime(pena_imposta="0 ano(s), 6 mês(es) e 0 dia(s)", pena_total_processo="0a6m0d - APELAÇÃO CRIMINAL", data_infracao="01/06/2019",
              data_denuncia="01/08/2019", data_sentenca="01/06/2020", transito_mp=tr, transito_processo=tr)
    return run(reg([c], [], data_nascimento="01/01/2001"))
L = intercorrente("23/04/2024")
confere(L["retro_cor"] == "vermelho" and "dobro do prazo" in L["pp_fund"], "R3-A4: intercorrente firme: %s" % L["retro_status"])
L = intercorrente("01/06/2022")
confere(L["retro_cor"] == "amarelo", "R3-A4: até o dobro, segue a verificar: %s" % L["retro_status"])

# A5: saldo zero na fuga, única condenação: hipótese de extinção chega à aba Extinção; com condenação sem trânsito, não
evs5 = [ev(PRI, "PRISÃO DEFINITIVA", "10/01/2012", P), ev(INT, "FUGA", "01/06/2013"), ev(PRI, "RECAPTURA", "01/01/2016", P)]
r5 = reg([crime()], evs5)
P5 = rp.analisar(r5, HOJE, None)
confere(P5["presc_linhas"][0].get("ppe_saldo_zero") == "01/06/2013", "R3-A5: saldo zero não registrado")
confere("saldo calculado zero" in rv.extincao(r5, P5, False)["ext_hipoteses"], "R3-A5: hipótese não chegou à aba Extinção")
r5b = reg([crime(), crime(processo_criminal="0000300-30.2012.8.12.0001", data_infracao="01/01/2012", transito_mp="", transito_processo="")], evs5)
confere(not run(r5b).get("ppe_saldo_zero"), "R3-A5: saldo zero com condenação sem trânsito somada")

# A6: preso hoje só pela ficha, ou intervalo inteiro coberto por prisão por outro processo: "não corre"
c6 = crime(pena_imposta="8 ano(s), 0 mês(es) e 0 dia(s)", pena_total_processo="8a0m0d - PENA ORIGINÁRIA", transito_mp="01/01/2015", transito_processo="01/01/2015")
L = run(reg([c6], []), ficha(("01.09.2026", "Deu entrada no EPMC, procedente da DP, Autos nº 0007777-77.2026.8.12.0001")))
confere(L["ppe_status"] == "Não corre (preso por outro processo desde 01/09/2026 - ficha SIAPEN, conferir)", "R3-A6: preso hoje pela ficha: %s" % L["ppe_status"])
L = run(reg([c6], [ev(PRI, "PRISÃO PREVENTIVA", "02/01/2015", "0007777-77.2014.8.12.0001")]))
confere(L["ppe_status"].startswith("Não corre (preso por outro processo desde"), "R3-A6: intervalo coberto por suspensão: %s" % L["ppe_status"])

# A7: quadro de linha a verificar pelo saldo não diz que a recaptura "veio antes e interrompeu" (t_rem)
crem = crime(data_infracao="01/01/2011", data_denuncia="01/02/2011", data_sentenca="01/06/2012", transito_mp="10/01/2013", transito_processo="10/01/2013",
             pena_imposta="3 ano(s), 6 mês(es) e 25 dia(s)", pena_total_processo="3a6m25d - PENA ORIGINÁRIA")
rrem = reg([crem], [ev(PRI, "PRISÃO DEFINITIVA", "10/01/2013"), ev(INT, "FUGA", "03/09/2014"), ev(PRI, "RECAPTURA", "01/06/2018")],
           pena_total="3a6m25d", pena_remanescente="1a11m0d")
L = run(rrem)
confere("interrompeu" not in L["ppe_quadro"]["prazo"] and "a verificar" in L["ppe_quadro"]["prazo"], "R3-A7: quadro: %s" % L["ppe_quadro"]["prazo"])
# R4-A5: remição até 2/3 (mais leitura): saldo inferior a 1 ano é possível - pede a pena remanescente
confere(L["ppe_status"].startswith("A VERIFICAR: informe a pena remanescente"), "R4-A5: teto da remição: %s" % L["ppe_status"])

# A8: sem parênteses aninhados; "conferir a ficha" no rótulo curto
L = run(reg([c6], [ev(PRI, "PRISÃO DEFINITIVA", "01/01/2015", P), ev(INT, "INTERRUPÇÃO POR PRISÃO EM OUTRO PROCESSO", "28/05/2026")]))
confere(L["ppe_status"] == "Não corre (preso em outro processo desde 28/05/2026 - interrupção por prisão em outro processo)", "R3-A8: %s" % L["ppe_status"])
confere(rv.presc_curto("Possível - conferir a ficha: art. 155 CP em 16/04/2023", True) == "Conferir a ficha", "R3-A8: rótulo curto da ficha")

# ---------------- 4ª revisão ----------------
# A1: restritiva, sursis e medida de segurança com novo crime e prisão por outro processo (t_prd, t_out)
r = aj(reg([crime()]), {"modalidade": "PRD", "inicio_prd": "01/02/2012", "ultimo_comparecimento": "01/03/2015", "novo_crime": "01/03/2017"})
L = run(r)
confere(L["ppe_status"] == "Prescrição executória aparente em 28/02/2021" and L["ppe_novo_crime"] == "01/03/2017", "R4-A1: PRD com novo crime: %s" % L["ppe_status"])
confere("01/03/2017 interrompeu" in L["ppe_fund"] and "sem outra causa" in L["ppe_fund"], "R4-A1: fundamentação da PRD sem o novo crime")
r = aj(reg([crime()], [ev(PRI, "PRISÃO PREVENTIVA", "01/06/2014", "0000300-30.2014.8.12.0001")]),
       {"modalidade": "PRD", "inicio_prd": "01/02/2012", "ultimo_comparecimento": "01/03/2015"})
confere(run(r)["ppe_status"] == "Não corre (preso por outro processo desde 01/06/2014)", "R4-A1: PRD preso por outro processo: %s" % run(r)["ppe_status"])
r = aj(reg([crime()], [ev(PRI, "PRISÃO PREVENTIVA", "01/06/2014", "0000300-30.2014.8.12.0001")]), {"modalidade": "SURSIS", "revogacao_sursis": "01/03/2015"})
confere(run(r)["ppe_status"] == "Não corre (preso por outro processo desde 01/06/2014)", "R4-A1: sursis preso por outro processo: %s" % run(r)["ppe_status"])
r = aj(reg([crime()], [ev(PRI, "PRISÃO PREVENTIVA", "01/06/2016", "0000300-30.2016.8.12.0001"), ev(INT, "LIBERDADE PROVISÓRIA", "01/08/2016")]),
       {"modalidade": "PRD", "inicio_prd": "01/02/2012", "ultimo_comparecimento": "01/03/2015"})
L = run(r)
confere(L["ppe_status"] == "Prescrição executória aparente em 01/05/2019" and "62 dias" in L["ppe_fund"], "R4-A1: PRD com preventiva de 2 meses: %s" % L["ppe_status"])
confere("HC 236.292" not in L["ppe_fund"] and "640.938" in L["ppe_fund"], "R4-A9: citação da restritiva")
# A2: medida de segurança com custódia em curso no trânsito; texto com a data do trânsito
r = aj(reg([crime()], [ev(PRI, "PRISÃO PREVENTIVA", "01/05/2011", P)]), {"modalidade": "MS"})
confere(run(r)["ppe_status"] == "Não corre (medida em cumprimento)", "R4-A2: MS com internação em curso: %s" % run(r)["ppe_status"])
L = run(aj(reg([crime()]), {"modalidade": "MS"}))
confere("transitou em julgado em 10/01/2012." in L["ppe_fund"], "R4-A2: frase da MS: %s" % L["ppe_fund"][:300])
# A3: quadro sem "zero (pena menos N dias de detração)"
L = run(reg([c6], [ev(PRI, "PRISÃO PREVENTIVA", "01/07/2014", P), ev(INT, "LIBERDADE PROVISÓRIA", "01/09/2014")]))
confere(L["pena_dias"] == 2920 and not L["ppe_quadro"]["saldo"].startswith("zero"), "R4-A3: quadro: %s" % L["ppe_quadro"]["saldo"])
# A4: inciso da punitiva pela pena corrigida (t_fund)
cf = crime(data_infracao="01/01/2016", data_denuncia="01/02/2016", data_sentenca="01/06/2020", transito_mp="10/07/2020", transito_processo="10/07/2020",
           pena_imposta="3 ano(s), 0 mês(es) e 0 dia(s)", pena_total_processo="3a0m0d - PENA ORIGINÁRIA")
L = run(aj(reg([cf]), {"pena": "1a6m0d"}))
confere("art. 109, V, do Código Penal" in L["pp_fund"], "R4-A4: inciso da punitiva: %s" % L["pp_fund"][:300])
# A6: dias contados com o da prisão e o da soltura
confere(rp._dias_uniao([(date(2020, 1, 1), date(2020, 1, 10))], date(2019, 1, 1), date(2021, 1, 1)) == 10, "R4-A6: _dias_uniao")
# A7: fim de mês sem o dia correspondente
confere(rp.ultimo_dia(date(2020, 8, 31), 18) == date(2022, 2, 28) and rp.ultimo_dia(date(2020, 2, 29), 36) == date(2023, 2, 28)
        and rp.ultimo_dia(date(2017, 3, 10), 48) == date(2021, 3, 9), "R4-A7: ultimo_dia no fim do mês")
# A10: conexo ao júri cita o art. 117, § 1º
cj = crime(processo_criminal=Q, artigo="ART 121: Matar alguem:", data_infracao="01/01/2010", data_denuncia="01/02/2010", data_sentenca="01/02/2020",
           transito_mp="01/03/2020", transito_processo="01/03/2020", pena_imposta="12 ano(s), 0 mês(es) e 0 dia(s)")
cx = crime(processo_criminal=Q, artigo="ART 14: Porte", lei="10826/03 - Estatuto do Desarmamento", data_infracao="01/01/2010", data_denuncia="01/02/2010",
           data_sentenca="01/02/2020", transito_mp="01/03/2020", transito_processo="01/03/2020", pena_imposta="2 ano(s), 0 mês(es) e 0 dia(s)")
L = run(reg([cj, cx]), idx=1)
confere("117, § 1º" in L["retro_detalhe"], "R4-A10: conexo sem o art. 117, § 1º")
# A12: erro na fundamentação fica nos avisos
_orig = rp.fundamentacao
rp.fundamentacao = lambda *a: 1 / 0
try:
    L = run(reg([crime()]))
finally:
    rp.fundamentacao = _orig
confere(any("erro ao montar a fundamentação" in a for a in L["avisos"]), "R4-A12: exceção engolida")
# A13: só o trânsito final (posterior a 12/11/2020), sentença anterior: aviso do trânsito para a acusação
L = run(reg([crime(data_sentenca="01/06/2019", transito_mp="", transito_processo="01/03/2021")]))
confere(any("sentença anterior a 12/11/2020" in a for a in L["avisos"]) and "conservadora" in L["ppe_termo_txt"], "R4-A13: aviso do Tema 788")

# "ALTERAÇÃO DE DATA-BASE" (complemento "Progressão de Regime") e incidente não concedido não abrem cumprimento inferido
_inc = [{"tipo": "ALTERAÇÃO DE DATA-BASE DE PROGRESSÃO DE REGIME/LIVRAMENTO CONDICIONAL", "complemento": "Progressão de Regime",
         "data_referencia": "01/03/2020", "data_decisao": "01/03/2020", "situacao": "CONCEDIDO"},
        {"tipo": "PROGRESSÃO DE REGIME", "complemento": "Semiaberto", "data_referencia": "01/04/2020", "data_decisao": "01/04/2020", "situacao": "NÃO CONCEDIDO"}]
per, _av = rp.periodos_cumprimento(reg([crime()], [], _inc), HOJE)
confere(not per, "data-base/não concedido tratados como alteração de regime: %s" % per)

if falhas:
    print("FALHOU (prescrição - revisão 4):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: prescrição rev4 (ficha x fuga, redações de saída, autos da execução, monitoramento, punitiva a verificar, novo crime e suspensão no "
      "texto, dobro do prazo, saldo zero, preso hoje, quadro, parênteses, PRD/sursis/MS, inciso, remição, dias, fim do mês, citações, "
      "exceção, Tema 788, data-base)")
