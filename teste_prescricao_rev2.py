"""Teste de regressão: 2ª revisão da prescrição (itens A1 a A14 do relatório; casos mínimos montados dos registros reais da base).
Rodar: python teste_prescricao_rev2.py (sai com código 1 se algum caso falhar)."""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_prescricao as rp

HOJE = date(2026, 10, 8)
falhas = []


def confere(cond, msg):
    if not cond:
        falhas.append(msg)


def crime(fato, tr, pena, proc="0000001-00.2015.8.12.0001", artigo="ART 155: Furto", lei="2848/40 - Código Penal",
          tipo="CAPUT: Subtrair, para si ou para outrem, coisa alheia móvel., RECLUSÃO: 1 A 4 ANOS E MULTA", tmp=None, ptp="PENA ORIGINÁRIA",
          den="", sent="", **kw):
    c = {"processo_criminal": proc, "data_infracao": fato, "data_denuncia": den, "data_sentenca": sent, "transito_mp": tr if tmp is None else tmp,
         "transito_processo": tr, "lei": lei, "artigo": artigo, "tipo_penal": tipo, "pena_imposta": pena, "pena_total_processo": "%s - %s" % (pena, ptp),
         "reincidente_comum": "N", "reincidente_especifico": "N", "extinto": "Não"}
    c.update(kw)
    return c


def ev(data, motivo, tipo="PRISÃO/INÍCIO DE CUMPRIMENTO", proc=""):
    return {"tipo": tipo, "motivo": motivo, "data": data, "processos": proc}


def inc(tipo, compl, ref, dec=None, sit="CONCEDIDO"):
    return {"tipo": tipo, "complemento": compl, "data_referencia": ref, "data_decisao": dec or ref, "situacao": sit}


def reg(crimes, eventos=(), incidentes=(), nasc="01/01/1980", **kw):
    r = {"_crimes": list(crimes), "_eventos": list(eventos), "_incidentes": list(incidentes), "data_nascimento": nasc,
         "data_geracao_rspe": "06/10/2026", "situacao_cumprimento": "EM CUMPRIMENTO"}
    r.update(kw)
    return r


def linhas(r, ficha=None):
    return rp.analisar(r, HOJE, ficha=ficha)["presc_linhas"]


def linha(r, proc=None, ficha=None, crime_=None):
    return next(l for l in linhas(r, ficha) if (proc is None or l["proc_crim"] == proc) and (crime_ is None or crime_ in l["crime"]))


def ficha(*evs):
    return {"eventos": [{"data": d, "texto": t} for d, t in evs]}


# A1: novo crime com data do fato posterior à denúncia/sentença daquele processo (erro de cadastro): a data não serve, e o fato real,
# anterior à denúncia, pode ter interrompido o prazo - A VERIFICAR (Wander Miarro Ferreira, 0004414-60.2016 e 0002203-46.2019)
P1, P2 = "0004414-60.2016.8.12.0005", "0002203-46.2019.8.12.0005"
c1 = crime("11/10/2016", "10/12/2018", "1 ano(s), 0 mês(es) e 0 dia(s)", proc=P1, artigo="ART 180: Receptação")
evs1 = [ev("10/04/2023", "RECAPTURA/REINÍCIO DE CUMPRIMENTO", proc=P1)]
confere(linha(reg([c1], evs1), P1)["ppe_cor"] == "vermelho", "A1: sem o novo crime, a liberdade de 2018 a 2023 dá prescrição aparente")
c2 = crime("10/04/2023", "19/10/2021", "1 ano(s), 6 mês(es) e 0 dia(s)", proc=P2, artigo="ART 215-A: Importunação sexual", den="08/07/2019", sent="31/03/2021")
l = linha(reg([c1, c2], evs1), P1)
confere(l["ppe_status"].startswith("A VERIFICAR") and "data do fato incoerente" in l["ppe_status"] and l["ppe_cor"] == "amarelo",
        "A1: novo crime com data incoerente -> A VERIFICAR: %s" % l["ppe_status"])
confere("anterior a 08/07/2019" in l["ppe_detalhe"], "A1: o limite da data real do fato (a denúncia) deveria constar")
# fato incoerente, mas a denúncia é anterior ao termo: o fato real é anterior ao termo e não interrompe
c2b = dict(c2, data_denuncia="08/07/2018", data_sentenca="01/11/2018", transito_mp="01/12/2018", transito_processo="01/12/2018")
confere(linha(reg([c1, c2b], evs1), P1)["ppe_cor"] == "vermelho", "A1: fato real anterior ao termo não muda o resultado")

# A2: prisão registrada só na ficha SIAPEN dentro do prazo - suspende e entra no vencimento; por processo fora do RSPE, "conferir"
# (Robson Brum Nogueira, 0000491-32.2016; ficha: preso de 01/04/2022 a 29/06/2022, alvará do processo 0000281-68.2022)
P = "0000491-32.2016.8.12.0003"
r2 = reg([crime("01/04/2016", "17/01/2019", "1 ano(s), 2 mês(es) e 6 dia(s)", proc=P)],
         [ev("11/12/2023", "PRISÃO EM FLAGRANTE", proc=P)], processo_execucao="6000030-16.2020.8.12.0003")
confere(linha(r2)["ppe_status"] == "Prescrição executória aparente em 16/01/2023", "A2: sem a ficha: %s" % linha(r2)["ppe_status"])
f2 = ficha(("01.04.2022", "Entrada na Unidade Penal: ESTABELECIMENTO PENAL DE JARDIM, Procedente: BELA VISTA - DP - INTERIOR, Conforme OF/CI 164/2022."),
           ("29.06.2022", "Saída da Unidade Penal: ESTABELECIMENTO PENAL DE JARDIM, Destino: 1ª VARA, Motivo: Alvará de Soltura, Conforme Ofício: 0000281-68.2022.8.12.0003."))
l = linha(r2, ficha=f2)
confere(l["ppe_status"] == "Prescrição possível em 16/04/2023 - conferir a ficha" and l["ppe_cor"] == "amarelo",
        "A2: prisão da ficha por processo fora do RSPE -> possível, conferir: %s" % l["ppe_status"])
confere("0000281-68.2022" in (l["ppe_faltam"] or [""])[0], "A2: o que falta deveria citar o processo da prisão: %s" % l["ppe_faltam"])
r2["_ficha_siapen"] = f2  # a ficha também pode chegar no próprio registro
confere(linha(r2)["ppe_status"].startswith("Prescrição possível"), "A2: ficha em r['_ficha_siapen'] ignorada")
del r2["_ficha_siapen"]
# processo da prisão consta do RSPE (o novo crime já está na conta): só a suspensão entra no vencimento
r2b = dict(r2, _crimes=r2["_crimes"] + [crime("01/03/2022", "01/03/2025", "1 ano(s), 0 mês(es) e 0 dia(s)", proc="0000281-68.2022.8.12.0003")])
l = linha(r2b, P, ficha=f2)
confere(l["ppe_cor"] == "vermelho" or "Prescrição possível" not in l["ppe_status"], "A2: processo conhecido não pede conferência: %s" % l["ppe_status"])
# entrada "para cumprimento de pena" nos autos desta execução, antes do vencimento: indício de retomada -> A VERIFICAR
f2c = ficha(("23.07.2021", "Entrada na Unidade Penal: ESTABELECIMENTO PENAL REGIME SEMIABERTO E ABERTO, Procedente: FORUM - INTERIOR, Conforme OF/CI "
                           "AUT.6000030-16.2020.8.12.0003, para cumprimento de pena em Regime ABERTO."),
            ("19.01.2023", "Saída da Unidade Penal: ESTABELECIMENTO PENAL REGIME SEMIABERTO E ABERTO, Destino: EVASÃO, Motivo: Evasão, Conforme Não Informado."))
l = linha(r2, ficha=f2c)
confere(l["ppe_status"].startswith("A VERIFICAR") and "retomada" in l["ppe_status"], "A2: entrada para cumprimento pela ficha -> A VERIFICAR: %s" % l["ppe_status"])
# transferência entre unidades não é soltura; progressão para o monitoramento encerra a custódia da ficha
pf = rp._periodos_ficha(ficha(("01.01.2020", "Entrada na Unidade Penal: A, Procedente: DP"), ("05.01.2020", "Saída da Unidade Penal: A, Destino: B, Motivo: Transferência de Presidio"),
                              ("05.01.2020", "Entrada na Unidade Penal: B, Procedente: A"), ("03.06.2020", "Saída da Unidade Penal: B, Destino: UMMVE, Motivo: Progressão de Regime"),
                              ("05.07.2021", "Entrada na Unidade Penal: B, Procedente: DP")))
confere([(p["ini"], p["fim"]) for p in pf] == [(date(2020, 1, 1), date(2020, 6, 3)), (date(2021, 7, 5), None)], "A2: períodos da ficha: %s" % pf)

# A3: intercorrente sentença -> trânsito com pena total "APELAÇÃO CRIMINAL": houve acórdão (interrompe) - A VERIFICAR (Clemilson Benites)
P = "0002825-31.2019.8.12.0004"
base3 = dict(fato="10/05/2019", tr="23/04/2024", pena="0 ano(s), 5 mês(es) e 15 dia(s)", proc=P, artigo="ART 147: Ameaça", den="20/06/2019", sent="01/06/2020")
l = linha(reg([crime(**base3, ptp="APELAÇÃO CRIMINAL")]))
confere(l["retro_status"].startswith("A VERIFICAR") and "acórdão" in l["retro_status"] and l["retro_cor"] == "amarelo", "A3: com apelação: %s" % l["retro_status"])
confere(not l["pp_fund"], "A3: sem fundamentação afirmativa no A VERIFICAR")
confere(linha(reg([crime(**base3)]))["retro_cor"] == "vermelho", "A3: sem indício de acórdão continua aparente")

# A4: crime conexo ao do júri (mesmo processo com art. 121): a pronúncia o alcança - A VERIFICAR (Rozildo Donizeti da Silva)
P = "0000930-78.2014.8.12.0014"
r4 = reg([crime("10/05/2014", "10/02/2026", "1 ano(s), 0 mês(es) e 0 dia(s)", proc=P, artigo="ART 211: Destruição, subtração ou ocultação de cadáver",
                den="12/08/2015", sent="18/11/2025"),
          crime("10/05/2014", "10/02/2026", "12 ano(s), 0 mês(es) e 0 dia(s)", proc=P, artigo="ART 121: Matar alguem:", den="12/08/2015", sent="18/11/2025")])
l = linha(r4, crime_="211")
confere(l["retro_status"].startswith("A VERIFICAR") and "conexo" in l["retro_detalhe"], "A4: conexo ao júri: %s" % l["retro_status"])

# A5: condenação extinta (indulto) depois da fuga estava em execução na fuga; condenação sem trânsito não é "única condenação"
# (Antonio José Ribeiro da Penha; Felipe Crispim Ajala)
P1, P2 = "0005085-26.2006.8.12.0008", "0007298-73.2004.8.12.0008"
evs5 = [ev("01/01/2007", "PRISÃO DEFINITIVA", proc=P1), ev("13/02/2008", "FUGA", tipo="INTERRUPÇÃO"), ev("03/03/2008", "RECAPTURA", proc=P1)]
c5 = crime("01/01/2006", "01/12/2006", "7 ano(s), 8 mês(es) e 0 dia(s)", proc=P1, artigo="ART 157: Roubo")
cx = crime("01/01/2004", "01/06/2005", "1 ano(s), 0 mês(es) e 0 dia(s)", proc=P2, extinto="Sim", extincao_motivo="INDULTO", data_extincao="07/06/2023")
l = linha(reg([c5, cx], evs5), P1)
confere(l["ppe_saldos"] and l["ppe_saldos"][0]["outras"] == 1 and "extinta depois da fuga" in l["ppe_detalhe"],
        "A5: extinta depois da fuga entra na conta: %s" % [S["outras"] for S in l["ppe_saldos"]])
l = linha(reg([c5, dict(cx, data_extincao="01/01/2008")], evs5), P1)
confere(l["ppe_saldos"] and l["ppe_saldos"][0]["outras"] == 0, "A5: extinta antes da fuga fica fora")
l = linha(reg([c5, crime("01/03/2007", "", "5 ano(s), 0 mês(es) e 0 dia(s)", proc="0031550-68.2021.8.12.0001", tmp="")], evs5), P1)
confere("única condenação transitada em execução" in l["ppe_detalhe"] and "; única condenação em execução" not in l["ppe_detalhe"],
        "A5: condenação sem trânsito: texto 'única condenação'")

# A6: art. 88 só com revogação registrada, e a prisão real dentro do período de prova continua sendo pena cumprida (Antonio José)
P = "0005085-26.2006.8.12.0008"
evs6 = [ev("01/01/2009", "PRISÃO DEFINITIVA", proc=P), ev("30/05/2010", "LIVRAMENTO CONDICIONAL", tipo="INTERRUPÇÃO"),
        ev("01/06/2010", "PRISÃO EM FLAGRANTE", proc=P), ev("07/02/2012", "FUGA", tipo="INTERRUPÇÃO"), ev("18/01/2013", "RECAPTURA", proc=P)]
c6 = crime("01/01/2006", "01/12/2008", "7 ano(s), 8 mês(es) e 0 dia(s)", proc=P, artigo="ART 157: Roubo")
l = linha(reg([c6], evs6, [inc("LIVRAMENTO CONDICIONAL", "", "30/05/2010"), inc("REVOGAÇÃO DE LIVRAMENTO CONDICIONAL", "", "07/02/2012")]))
S6 = next((S for S in l["ppe_saldos"] if S["evasao"] == "07/02/2012"), None)
# rev. 4 (A6): cada período conta o dia da prisão e o da soltura, como o SEEU (antes, 514 + 616)
confere(S6 and S6["cumprido_desde_termo"] == 515 + 617 and "não se desconta do saldo (CP, art. 88" in l["ppe_detalhe"], "A6: prisão real no período de prova apagada: %s" % (S6 and S6["cumprido_desde_termo"]))
l = linha(reg([c6], evs6, [inc("LIVRAMENTO CONDICIONAL", "", "30/05/2010")]))
confere("não se desconta do saldo (CP, art. 88" not in l["ppe_detalhe"], "A6: art. 88 aplicado sem revogação registrada")

# A7: fuga lançada durante prisão registrada para outro processo: a pessoa não estava solta - a prisão era cumprimento desta pena
# (Olair Carvalho da Conceição, fuga de 26/07/2017 da prisão de 07/12/2014 do processo 0008758-02.2014)
P, Q = "0000550-39.2008.8.11.0064", "0008758-02.2014.8.11.0064"
l = linha(reg([crime("06/01/2008", "27/08/2010", "7 ano(s), 0 mês(es) e 0 dia(s)", proc=P, lei="11343/06 - Lei de Drogas", artigo="ART 33: Tráfico de drogas")],
              [ev("24/09/2008", "PRISÃO EM FLAGRANTE", proc=P), ev("06/11/2014", "LIBERDADE PROVISÓRIA", tipo="INTERRUPÇÃO"),
               ev("07/12/2014", "PRISÃO EM FLAGRANTE", proc=Q), ev("26/07/2017", "FUGA", tipo="INTERRUPÇÃO"),
               ev("27/08/2021", "PRISÃO DEFINITIVA", proc=P)]), P)
confere("quando os eventos mostravam a pessoa solta" not in l["ppe_detalhe"] and "Fuga desta execução lançada em 26/07/2017 durante a prisão de 07/12/2014"
        in l["ppe_detalhe"], "A7: fuga durante a prisão por outro processo tratada como 'pessoa solta'")
confere(not any("pessoa solta" in a for a in l["avisos"]), "A7: aviso falso de pessoa solta")

# A8: trânsitos no mesmo dia e penas iguais: a ordem de imputação é a mesma para as duas linhas (Hoeder Leguir Fernandes)
PA, PB, PC = "0001088-44.2008.8.12.0047", "0000910-90.2009.8.12.0005", "0000875-67.2008.8.12.0005"
r8 = reg([crime("01/01/2008", "01/01/2010", "2 ano(s), 6 mês(es) e 0 dia(s)", proc=PA),
          crime("01/01/2009", "13/02/2013", "2 ano(s), 4 mês(es) e 0 dia(s)", proc=PB),
          crime("01/01/2008", "13/02/2013", "2 ano(s), 4 mês(es) e 0 dia(s)", proc=PC)],
         [ev("01/01/2010", "PRISÃO DEFINITIVA", proc=PA), ev("14/02/2020", "FUGA", tipo="INTERRUPÇÃO"), ev("15/10/2022", "RECAPTURA", proc=PA)])
ls8 = {l["proc_crim"]: l for l in linhas(r8)}
pos = sorted(ls8[p]["ppe_saldos"][-1]["cronologica"]["posicao"] for p in (PB, PC))
confere(pos == [2, 3], "A8: posições na ordem cronológica das condenações do mesmo dia: %s" % pos)

# A9: quadro de um A VERIFICAR vindo de prescrição não diz que o retorno "veio antes e interrompeu" (Valdecy Samuel Barbier)
P = "0000006-45.2017.8.12.0052"
l = linha(reg([crime("13/12/2016", "10/07/2018", "2 ano(s), 0 mês(es) e 0 dia(s)", proc=P)],
              [ev("30/10/2017", "PRISÃO DEFINITIVA", proc=P), ev("26/03/2019", "FUGA", tipo="INTERRUPÇÃO"), ev("18/08/2025", "RECAPTURA", proc=P)],
              [inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Aberto - Progressão de Regime", "14/04/2020")]))
confere(l["ppe_status"].startswith("A VERIFICAR") and "interrompeu" not in l["ppe_quadro"]["prazo"] and "a verificar" in l["ppe_quadro"]["prazo"],
        "A9: quadro contraditório: %s" % l["ppe_quadro"]["prazo"])

# A10: liberdade até hoje, mas preso por outro processo: "Não corre", sem falsa "retomada do cumprimento" (Alex Sandro Cardoso Gabriel)
P = "0000188-72.2022.8.12.0014"
l = linha(reg([crime("01/01/2022", "01/06/2023", "8 ano(s), 0 mês(es) e 0 dia(s)", proc=P, artigo="ART 157: Roubo")],
              [ev("01/02/2025", "PRISÃO EM FLAGRANTE", proc="0000180-61.2025.8.12.0014")]), P)
confere(l["ppe_status"] == "Não corre (preso por outro processo desde 01/02/2025)" and "retomada do cumprimento interrompeu" not in l["ppe_detalhe"],
        "A10: %s" % l["ppe_status"])

# A11: base do prazo com interrupção sem evasão; art. 28 cita o art. 30 da Lei 11.343/2006
P = "0000645-84.2015.8.12.0003"
l = linha(reg([crime("01/01/2015", "03/07/2017", "2 ano(s), 0 mês(es) e 0 dia(s)", proc=P)],
              [ev("28/09/2018", "PRISÃO EM FLAGRANTE", proc=P), ev("03/06/2020", "LIBERDADE PROVISÓRIA", tipo="INTERRUPÇÃO"), ev("24/12/2024", "PRISÃO DEFINITIVA", proc=P)]))
confere("sem fuga ou interrupção" not in l["ppe_base_txt"] and "interrupção sem fuga em 03/06/2020" in l["ppe_base_txt"], "A11: base: %s" % l["ppe_base_txt"])
l = linha(reg([crime("30/06/2017", "29/08/2018", "0 ano(s), 1 mês(es) e 0 dia(s)", lei="11343/06 - Lei de Drogas",
                     artigo="ART 28: Porte de droga para consumo pessoal", tipo="CAPUT: Quem adquirir")]))
confere(any("art. 30 da Lei 11.343/2006" in x for x in l["ppe_explica"]) and not any("(art. 109)" in x for x in l["ppe_explica"]),
        "A11: art. 28: %s" % l["ppe_explica"])

# A12: fuga encerrada por flagrante de novo crime depois da consumação: a fundamentação cita o art. 117, V e VI (Willian Oliveira da Silva)
P, Q = "0000458-07.2016.8.12.0047", "0800570-59.2024.8.12.0047"
l = linha(reg([crime("06/05/2016", "11/12/2018", "2 ano(s), 0 mês(es) e 0 dia(s)", proc=P, artigo="ART 14 - Porte ilegal de arma", lei="10826/03 - Estatuto do Desarmamento"),
               crime("30/05/2024", "", "3 ano(s), 0 mês(es) e 0 dia(s)", proc=Q, tmp="", artigo="ART 304: Uso de documento falso")],
              [ev("11/12/2018", "PRISÃO DEFINITIVA", proc=P), ev("26/06/2019", "FUGA", tipo="INTERRUPÇÃO"), ev("30/05/2024", "PRISÃO EM FLAGRANTE", proc="%s, %s" % (P, Q))]), P)
confere(l["ppe_cor"] == "vermelho" and "art. 117, V e VI" in l["ppe_fund"], "A12: inciso do novo crime: %s / %s" % (l["ppe_status"], l["ppe_fund"][-300:]))

# A13: sem trânsito, preso por prisão registrada só em outro processo: não afirma "em cumprimento" (Cosme Daniel Inçabralde Venega)
P = "0001159-36.2017.8.12.0013"
l = linha(reg([crime("10/03/2017", "", "6 ano(s), 0 mês(es) e 0 dia(s)", proc=P, tmp="", lei="11343/06 - Lei de Drogas", artigo="ART 33: Tráfico de drogas")],
              [ev("15/03/2017", "PRISÃO EM FLAGRANTE", proc="0042043-32.2006.8.12.0001")]), P)
confere(l["ppe_status"].startswith("Não corre: preso desde 15/03/2017") and "outro processo" in l["ppe_status"], "A13: %s" % l["ppe_status"])

# A14: "pena suspensa (preso em outro processo)" não é cumprimento em curso: nada se infere da última alteração de regime
P = "0005085-26.2006.8.12.0008"
l = linha(reg([crime("01/01/2006", "01/12/2008", "7 ano(s), 8 mês(es) e 0 dia(s)", proc=P, artigo="ART 157: Roubo")],
              [ev("01/01/2009", "PRISÃO DEFINITIVA", proc=P), ev("09/07/2026", "PRISÃO EM OUTRO PROCESSO", tipo="INTERRUPÇÃO")],
              [inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Semiaberto - Progressão de Regime", "01/01/2012")],
              situacao_cumprimento="PENA SUSPENSA (preso em outro processo desde 09/07/2026)"))
confere("inferido da última alteração de regime" not in l["ppe_detalhe"] and l["ppe_status"].startswith("Não corre"), "A14: %s" % l["ppe_status"])

if falhas:
    print("FALHOU (prescrição - revisão 2):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: prescrição - revisão 2 (novo crime com data incoerente, prisão da ficha, acórdão na intercorrente, conexo ao júri, condenações "
      "na fuga, art. 88, fuga durante prisão por outro processo, imputação no mesmo dia, textos do quadro, não corre, base do prazo, art. 30, "
      "inciso VI, cumprimento de outro processo, pena suspensa)")
