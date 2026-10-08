"""Teste de regressão: erros confirmados na revisão da prescrição e da extinção (casos mínimos montados dos registros reais da base).
Rodar: python teste_prescricao_revisao.py (sai com código 1 se algum caso falhar)."""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_prescricao as rp
import rspe_view as rv

HOJE = date(2026, 10, 7)
rv.HOJE = HOJE
falhas = []


def confere(cond, msg):
    if not cond:
        falhas.append(msg)


def crime(fato, tr, pena, proc="0000001-00.2015.8.12.0001", artigo="ART 155: Furto", lei="2848/40 - Código Penal",
          tipo="CAPUT: Subtrair, para si ou para outrem, coisa alheia móvel., RECLUSÃO: 1 A 4 ANOS E MULTA", tmp=None, ptp="PENA ORIGINÁRIA"):
    return {"processo_criminal": proc, "data_infracao": fato, "data_denuncia": "", "data_sentenca": "", "transito_mp": tr if tmp is None else tmp,
            "transito_processo": tr, "lei": lei, "artigo": artigo, "tipo_penal": tipo, "pena_imposta": pena, "pena_total_processo": "%s - %s" % (pena, ptp),
            "reincidente_comum": "N", "reincidente_especifico": "N", "extinto": "Não"}


def ev(data, motivo, tipo="PRISÃO/INÍCIO DE CUMPRIMENTO", proc=""):
    return {"tipo": tipo, "motivo": motivo, "data": data, "processos": proc}


def inc(tipo, compl, ref, dec=None, sit="CONCEDIDO"):
    return {"tipo": tipo, "complemento": compl, "data_referencia": ref, "data_decisao": dec or ref, "situacao": sit}


def reg(crimes, eventos=(), incidentes=(), nasc="01/01/1980", **kw):
    r = {"_crimes": list(crimes), "_eventos": list(eventos), "_incidentes": list(incidentes), "data_nascimento": nasc,
         "data_geracao_rspe": "02/10/2026", "situacao_cumprimento": "EM CUMPRIMENTO"}
    r.update(kw)
    return r


def linha(r, proc=None):
    ls = rp.analisar(r, HOJE)["presc_linhas"]
    return next(l for l in ls if proc is None or l["proc_crim"] == proc)


# A1: SEEU sem cálculo (cumprida zero, remanescente = total) e custódia da ficha que já alcança a pena: término não é futuro e a
# extinção fica a verificar (Davi Antonio Vigil, 0000323-40.2021: pena 1m26d, preso desde 29/04/2025)
r = reg([crime("11/04/2021", "23/04/2025", "0 ano(s), 1 mês(es) e 26 dia(s)", artigo="ART 147: Ameaça")],
        [dict(ev("29/04/2025", "ENTRADA NO SISTEMA PRISIONAL (lançada pela ficha SIAPEN)", tipo="PRISÃO"), _ficha=True)],
        pena_total="0a1m26d", pena_cumprida="0a0m0d", pena_remanescente="0a1m26d")
confere(rv.termino_calc(r) == date(2025, 6, 24), "A1: término com a custódia deveria ser 24/06/2025: %s" % rv.termino_calc(r))
ex = rv.extincao(r, rp.analisar(r, HOJE), False)
confere(ex["ext_cor"] == "amarelo" and ex["ext_sit"] == "Extinção a verificar" and "LEP, art. 66, II" in ex["ext_hipoteses"]
        and "outro" in ex["ext_hipoteses"], "A1: extinção pelo cumprimento a verificar: %s" % ex)

# A2: término pelo calendário (anos e meses, depois dias), como o SEEU
r = reg([crime("01/01/2023", "01/06/2024", "3 ano(s), 1 mês(es) e 10 dia(s)")], [ev("01/06/2024", "PRISÃO DEFINITIVA")],
        pena_total="3a1m10d", pena_cumprida="2a0m0d", pena_remanescente="1a1m10d", data_geracao_rspe="10/01/2026")
confere(rv.termino_calc(r) == date(2027, 2, 20), "A2: 10/01/2026 + 1a1m10d pelo calendário = 20/02/2027: %s" % rv.termino_calc(r))

# A3: progressão concedida durante a "fuga" indica retomada - no mínimo A VERIFICAR (Valdecy Samuel Barbier, 0000006-45.2017)
P = "0000006-45.2017.8.12.0052"
base3 = ([crime("13/12/2016", "10/07/2018", "2 ano(s), 0 mês(es) e 0 dia(s)", proc=P)],
         [ev("30/10/2017", "PRISÃO DEFINITIVA", proc=P), ev("26/03/2019", "FUGA", tipo="INTERRUPÇÃO"), ev("18/08/2025", "RECAPTURA", proc=P)])
confere(linha(reg(*base3))["ppe_cor"] == "vermelho", "A3: sem o incidente, a fuga de 2019 a 2025 dá prescrição aparente")
l = linha(reg(*base3, incidentes=[inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Aberto - Progressão de Regime", "14/04/2020")]))
confere(l["ppe_status"].startswith("A VERIFICAR") and l["ppe_cor"] == "amarelo", "A3: progressão durante a fuga -> A VERIFICAR: %s" % l["ppe_status"])

# A4: fuga lançada quando os eventos mostravam a pessoa solta não é ignorada (Hoeder Leguir Fernandes, 0000910-90.2009)
P = "0000910-90.2009.8.12.0005"
l = linha(reg([crime("23/03/2009", "15/02/2016", "3 ano(s), 0 mês(es) e 0 dia(s)", proc=P)],
              [ev("01/01/2017", "PRISÃO DEFINITIVA", proc=P), ev("29/03/2018", "LIBERDADE PROVISÓRIA", tipo="INTERRUPÇÃO"),
               ev("14/02/2020", "FUGA", tipo="INTERRUPÇÃO"), ev("15/10/2025", "RECAPTURA", proc=P)]))
confere(l["ppe_status"].startswith("A VERIFICAR") and "Fuga lançada em 14/02/2020" in l["ppe_detalhe"],
        "A4: fuga de 14/02/2020 com a pessoa solta pelos eventos -> A VERIFICAR: %s" % l["ppe_status"])

# A5: art. 28 da Lei 11.343/2006 prescreve em 2 anos (art. 30) (Lucas Martins Carneiro, 0002273-07.2017)
l = linha(reg([crime("30/06/2017", "29/08/2018", "0 ano(s), 1 mês(es) e 0 dia(s)", lei="11343/06 - Lei de Drogas",
                     artigo="ART 28: Porte de droga para consumo pessoal", tipo="CAPUT: Quem adquirir")]))
confere(l["ppe_status"] == "Prescrição executória aparente em 28/08/2020" and l["prazo_ppp"] == "2 anos",
        "A5: art. 28 em 2 anos: %s / %s" % (l["ppe_status"], l["prazo_ppp"]))

# A6: "em cumprimento desde X" só com X posterior ao fato desta condenação (Lucas Martins Carneiro, 0900497-63.2025)
P = "0900497-63.2025.8.12.0014"
l = linha(reg([crime("10/07/2025", "", "8 ano(s), 2 mês(es) e 0 dia(s)", proc=P, tmp="")],
              [ev("09/09/2021", "INÍCIO DO CUMPRIMENTO REGIME FECHADO", proc="0001143-84.2014.8.12.0014")]))
confere(not l["ppe_status"].startswith("Não corre: em cumprimento"), "A6: cumprimento anterior ao fato: %s" % l["ppe_status"])

# A7: custódia que era cumprimento de outra condenação já transitada não é detração (Willian Oliveira da Silva)
P1, P2 = "0000001-00.2012.8.12.0001", "0000002-00.2016.8.12.0001"
l = linha(reg([crime("01/01/2012", "01/01/2014", "10 ano(s), 0 mês(es) e 0 dia(s)", proc=P1, artigo="ART 121: Matar alguem:"),
               crime("01/01/2016", "11/12/2018", "1 ano(s), 0 mês(es) e 0 dia(s)", proc=P2, artigo="ART 14 - Porte ilegal de arma",
                     lei="10826/03 - Estatuto do Desarmamento")],
              [ev("06/05/2016", "PRISÃO EM FLAGRANTE", proc="%s, %s" % (P1, P2))]), P2)
confere(not l.get("ppe_detracao_dias") and not l.get("ppe_detracao_cobre"), "A7: detração inflada: %s" % l.get("ppe_detracao_dias"))

# A8: livramento revogado - o período de prova não se desconta do saldo (CP, art. 88) (Dalvam Conceição Cruz de Souza). Revisão 2 (A6):
# o art. 88 só se aplica com a revogação registrada; sem ela, o período de prova conta como cumprimento (como no SEEU)
P = "0002175-07.2012.8.12.0011"
_a8 = ([crime("02/07/2012", "26/08/2013", "14 ano(s), 0 mês(es) e 0 dia(s)", proc=P, artigo="ART 121: Matar alguem:")],
       [ev("04/07/2012", "PRISÃO PROVISÓRIA", proc=P), ev("01/08/2024", "INTERRUPÇÃO DO CUMPRIMENTO DA PENA", tipo="INTERRUPÇÃO"),
        ev("28/06/2026", "INÍCIO DO CUMPRIMENTO REGIME SEMIABERTO", proc=P)])
l = linha(reg(*_a8, [inc("LIVRAMENTO CONDICIONAL", "28/12/2020", "28/12/2020", "25/11/2022"),
                     inc("REVOGAÇÃO DE LIVRAMENTO CONDICIONAL", "", "01/08/2024")], nasc="09/06/1992"))
# rev. 4 (A5): com o teto da remição em 2/3 dos dias (mais a leitura), um saldo inferior a 1 ano passa a ser possível nesta fuga
# longa, e o programa pede a pena remanescente (antes, com 1/2, concluía "não prescrita")
confere(l["ppe_status"] in ("Não prescrita", "A VERIFICAR: informe a pena remanescente na fuga de 01/08/2024") and "art. 88" in l["ppe_detalhe"],
        "A8: período de prova fora do saldo: %s" % l["ppe_status"])
l = linha(reg(*_a8, [inc("LIVRAMENTO CONDICIONAL", "28/12/2020", "28/12/2020", "25/11/2022")], nasc="09/06/1992"))
confere("pressupõe a revogação" in l["ppe_detalhe"] and "não se desconta do saldo (CP, art. 88" not in l["ppe_detalhe"],
        "A8: sem revogação registrada, o art. 88 não se aplica: %s" % l["ppe_status"])

# A9: só o trânsito final, anterior a 12/11/2020: sem "Tema 788" como fundamento do termo; aviso de contagem conservadora
l = linha(reg([crime("01/01/2010", "06/09/2012", "8 ano(s), 0 mês(es) e 0 dia(s)", tmp="")], [ev("01/01/2013", "PRISÃO DEFINITIVA")]))
confere("conservadora" in l["ppe_termo_txt"] and "ARE 848.107" not in l["ppe_termo_txt"], "A9: termo: %s" % l["ppe_termo_txt"])

# A10: "Multa cumulada" só na cominação cumulativa ("E MULTA"), não na alternativa ("OU MULTA")
l = linha(reg([crime("01/01/2015", "01/01/2016", "0 ano(s), 2 mês(es) e 0 dia(s)", artigo="ART 147: Ameaça",
                     tipo="CAPUT: Ameaçar alguém, DETENÇÃO: 1 A 6 MESES OU MULTA")], [ev("01/02/2016", "PRISÃO DEFINITIVA")]))
confere("Multa cumulada" not in l["ppe_detalhe"], "A10: multa alternativa tratada como cumulada")
l = linha(reg([crime("01/01/2015", "01/01/2016", "1 ano(s), 0 mês(es) e 0 dia(s)")], [ev("01/02/2016", "PRISÃO DEFINITIVA")]))
confere("Multa cumulada" in l["ppe_detalhe"], "A10: multa cumulada (E MULTA) sem a nota")

# A11: menor de 18 anos no fato é dado incoerente - a prescrição aparente fica A VERIFICAR (Vandiney Dias de Jesus)
l = linha(reg([crime("01/06/2003", "01/01/2006", "1 ano(s), 0 mês(es) e 0 dia(s)", artigo="ART 180: Receptação")], nasc="22/04/1986"))
confere(l["ppe_status"].startswith("A VERIFICAR") and any("17 anos" in a for a in l["avisos"]), "A11: idade de 17 anos no fato: %s" % l["ppe_status"])

# A12: início de aberto de 0 dia registrado só em outro processo não interrompe este crime (Alex Rodrigues de Souza, 0002372-09.2019)
P1, P2 = "0002173-84.2019.8.12.0013", "0002372-09.2019.8.12.0013"
l = linha(reg([crime("05/07/2019", "23/11/2021", "3 ano(s), 6 mês(es) e 20 dia(s)", proc=P1),
               crime("24/06/2019", "18/04/2022", "2 ano(s), 0 mês(es) e 0 dia(s)", proc=P2)],
              [ev("09/05/2022", "INÍCIO DO CUMPRIMENTO REGIME ABERTO", proc=P1), ev("09/05/2022", "INTERRUPÇÃO DO CUMPRIMENTO DA PENA", tipo="INTERRUPÇÃO"),
               ev("02/09/2025", "INÍCIO DO CUMPRIMENTO REGIME SEMIABERTO", proc="%s, %s" % (P2, P1))], nasc="23/10/1999"), P2)
confere(l["ppe_status"] == "Prescrição executória aparente em 17/04/2024", "A12: data do aparente: %s" % l["ppe_status"])
confere(l["ppe_fund"] and "(autos" not in l["ppe_fund"], "texto: \"(ação penal X) (autos X)\" repetido na fundamentação")
confere(rp._fim_txt({"fim": "28/06/2026", "fim_motivo": "início do cumprimento regime semiaberto"}) ==
        "do início do cumprimento regime semiaberto em 28/06/2026", "texto: início de regime chamado de recaptura")

# idade impossível (menor de 18 no fato): sem a metade do art. 115, e a idade vale como desconhecida (Caua Peres Rocha, 9 anos no fato)
l = linha(reg([crime("30/10/2013", "17/11/2025", "3 ano(s), 0 mês(es) e 0 dia(s)")], [ev("11/08/2026", "PRISÃO DEFINITIVA")], nasc="17/07/2004"))
confere(not l["art115"] and l["prazo_ppe"] == "8 anos", "idade de 9 anos no fato: art. 115 não se aplica: %s" % l["prazo_ppe"])

# B3: pena convertida em restritiva de direitos, sem a modalidade informada: A VERIFICAR, não vermelho (Felipe Oliveira Lima)
l = linha(reg([crime("01/01/2015", "01/01/2016", "1 ano(s), 8 mês(es) e 0 dia(s)", ptp="CONVERTIDA")]))
confere(l["ppe_status"].startswith("A VERIFICAR") and l["ppe_cor"] == "amarelo", "B3: pena convertida: %s" % l["ppe_status"])

if falhas:
    print("FALHOU (prescrição - revisão):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: prescrição e extinção - revisão (término com custódia e pelo calendário, retomada na fuga, fuga com a pessoa solta, art. 28, "
      "detração, art. 88, Tema 788, multa, idade, aberto de 0 dia, pena convertida)")
