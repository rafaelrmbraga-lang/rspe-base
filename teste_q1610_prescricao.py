"""Teste de regressão dos quesitos de 16/10/2026 do grupo prescrição e extinção (itens 60, 62, 64, 65, 66, 67, 68, 70, 71, 72,
73, 74 e 75). Casos hipotéticos, com nomes e números fictícios. Rodar: python teste_q1610_prescricao.py (sai com 1 se algum falhar)."""
import sys
import types
from datetime import date, timedelta

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_prescricao as rp
import rspe_view as rv
import rspe_app as app

HOJE = date(2026, 10, 16)
EXEC = "0000999-99.2015.8.12.0001"
P, Q = "9100001-11.2015.8.12.0001", "9100002-22.2014.8.12.0001"
falhas = []


def confere(cond, msg):
    if not cond:
        falhas.append(msg)


def crime(**k):
    c = {"processo_criminal": P, "vara_condenacao": "1ª Vara Criminal", "data_infracao": "01/01/2009", "data_denuncia": "01/02/2009",
         "data_sentenca": "01/06/2011", "transito_mp": "10/01/2012", "transito_processo": "10/01/2012",
         "pena_total_processo": "1a0m0d - PENA ORIGINÁRIA", "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto",
         "tipo_penal": "CAPUT: Subtrair..., Reclusão: 1 a 4 anos E Multa", "pena_imposta": "1 ano(s), 0 mês(es) e 0 dia(s)",
         "reincidente_comum": "N", "reincidente_especifico": "N", "extinto": "Não", "fracao_progressao": "1/6 - Comum"}
    c.update(k)
    return c


def reg(crimes, eventos=(), inc=(), **k):
    r = {"data_nascimento": "01/01/1970", "pena_total": "1a0m0d", "pena_cumprida": "0a0m0d", "pena_remanescente": "1a0m0d",
         "data_geracao_rspe": "10/10/2026", "processo_execucao": EXEC, "situacao_cumprimento": "EM CUMPRIMENTO",
         "_crimes": list(crimes), "_eventos": list(eventos), "_incidentes": list(inc)}
    r.update(k)
    return r


def ev(tipo, motivo, data, proc=""):
    return {"tipo": tipo, "motivo": motivo, "complemento": "", "data": data, "data_decisao": "", "data_referencia": "", "processos": proc}


def inc(tipo, compl, data, sit="CONCEDIDO"):
    return {"tipo": tipo, "complemento": compl, "situacao": sit, "data_decisao": data, "data_referencia": data}


PRI, INT = "PRISÃO/INÍCIO DE CUMPRIMENTO", "INTERRUPÇÃO"


def aj(r, valores, idx=0):
    ch = rp.chave_ajuste(r["_crimes"][idx], {})
    r["_presc_ajustes"] = {ch: {"valores": valores, "_data": "16/10/2026"}}
    return r


def run(r, idx=0, hoje=HOJE):
    return rp.analisar(r, hoje)["presc_linhas"][idx]


# ---------- 60: reincidência marcada sem base, no tráfico privilegiado: descartada sem dúvida ----------
def traf(par):
    return crime(lei="11343/06 - Lei de Drogas", artigo="ART 33: Tráfico", tipo_penal="%s: Importar..., Reclusão: 5 a 15 anos E Multa" % par,
                 pena_imposta="1 ano(s), 8 mês(es) e 0 dia(s)", pena_total_processo="1a8m0d - PENA ORIGINÁRIA", data_infracao="01/03/2019",
                 data_denuncia="01/04/2019", data_sentenca="01/06/2020", transito_mp="01/08/2021", transito_processo="01/08/2021",
                 reincidente_comum="S")
L = run(reg([traf("§ 4º")]))
confere(not L["reinc"] and "(+1/3" not in L["prazo_ppe"] and L["ppe_cor"] == "vermelho" and "tráfico privilegiado" in (L.get("ppe_reinc_aviso") or ""),
        "60: privilegiado com reincidência sem base deveria ser calculado sem o +1/3, sem dúvida: %s | %s" % (L["prazo_ppe"], L["ppe_status"]))
L = run(reg([traf("CAPUT")]))
confere(L["reinc"] and L["ppe_status"].startswith("A VERIFICAR"), "60: fora do privilegiado, a reincidência sem base continua a verificar: %s" % L["ppe_status"])

# ---------- 62: restritiva - prisão por outro processo depois do último comparecimento suspende (não interrompe) ----------
cB = crime(processo_criminal=Q, data_infracao="01/01/2014", data_denuncia="01/02/2014", data_sentenca="01/06/2014", transito_mp="01/09/2014",
           transito_processo="01/09/2014", pena_imposta="3 ano(s), 0 mês(es) e 0 dia(s)", pena_total_processo="3a0m0d - PENA ORIGINÁRIA")
cA = crime(data_infracao="01/01/2015", data_denuncia="01/02/2015", data_sentenca="01/06/2015", transito_mp="01/09/2015", transito_processo="01/09/2015")
evs62 = [ev(PRI, "PRISÃO DEFINITIVA", "01/06/2020", Q), ev(INT, "ALVARÁ DE SOLTURA", "01/06/2021")]
r62 = aj(reg([cA, cB], evs62), {"modalidade": "PRD", "inicio_prd": "01/10/2015", "ultimo_comparecimento": "01/01/2020"})
L = run(r62)
confere(L["ppe_cor"] == "vermelho" and (L.get("ppe_susp_dias") or 0) > 300,
        "62: prisão por outro processo depois do último comparecimento deveria suspender (prazo vencido com os dias somados): %s | %s" % (
            L["ppe_status"], L.get("ppe_susp_dias")))
confere("salvo conversão desta pena" in L["ppe_detalhe"] or "art. 116, p. único" in L["ppe_detalhe"], "62: memória sem a suspensão")
# a mesma prisão lançada nesta ação penal: execução nesta guia, interrompe
evs62b = [ev(PRI, "PRISÃO DEFINITIVA", "01/06/2020", P), ev(INT, "ALVARÁ DE SOLTURA", "01/06/2021")]
L = run(aj(reg([cA, cB], evs62b), {"modalidade": "PRD", "inicio_prd": "01/10/2015", "ultimo_comparecimento": "01/01/2020"}))
confere(L["ppe_cor"] != "vermelho", "62: prisão nesta ação penal deveria interromper: %s" % L["ppe_status"])

# ---------- 64: livramento com interrupção e sem revogação: hipótese da Súmula 617 também na aba Extinção ----------
r64 = reg([crime(pena_imposta="2 ano(s), 0 mês(es) e 0 dia(s)", pena_total_processo="2a0m0d - PENA ORIGINÁRIA")],
          [ev(PRI, "PRISÃO DEFINITIVA", "10/01/2012", P), ev(INT, "FUGA", "01/03/2013")],
          [inc("LIVRAMENTO CONDICIONAL", "", "01/10/2012")], pena_total="2a0m0d", pena_cumprida="0a9m0d", pena_remanescente="1a3m0d")
ex = rv.extincao(r64, {"presc_linhas": []}, True)
confere("Súmula 617/STJ" in ex["ext_hipoteses"] and ex["ext_hipoteses"].startswith("A verificar") and "art. 89" in ex["ext_hipoteses"]
        and ex["ext_cor"] == "amarelo" and ex["ext_sit"] == "Extinção a verificar",
        "64: hipótese da Súmula 617 não apareceu na Extinção: %s | %s | %s" % (ex["ext_hipoteses"], ex["ext_cor"], ex["ext_sit"]))

# ---------- 65: os três critérios de imputação concordam: conclui-se por eles ----------
A_, E_ = "9100003-33.2014.8.12.0001", "9100004-44.2015.8.12.0001"
def r65(tr_e):
    cs = [crime(processo_criminal=A_, data_infracao="01/01/2013", data_denuncia="01/02/2013", data_sentenca="01/03/2014", transito_mp="13/06/2014",
                transito_processo="13/06/2014", pena_imposta="10 ano(s), 0 mês(es) e 0 dia(s)", pena_total_processo="10a0m0d - PENA ORIGINÁRIA"),
          crime(processo_criminal=E_, data_infracao="01/01/2014", data_denuncia="01/02/2014", data_sentenca="01/03/2014", transito_mp=tr_e,
                transito_processo=tr_e, pena_imposta="3 ano(s), 0 mês(es) e 0 dia(s)", pena_total_processo="3a0m0d - PENA ORIGINÁRIA")]
    evs = [ev(PRI, "PRISÃO DEFINITIVA", "01/06/2014", "%s, %s" % (A_, E_)), ev(INT, "FUGA", "01/01/2016"),
           ev(PRI, "RECAPTURA", "01/01/2022", "%s, %s" % (A_, E_))]
    return reg(cs, evs, pena_total="13a0m0d")
L = run(r65("01/01/2015"), 1)
S = L["ppe_saldos"][0] if L["ppe_saldos"] else {}
confere(not L["ppe_status"].startswith("A VERIFICAR") and L["ppe_cor"] != "vermelho" and "três critérios" in (S.get("saldo_rotulo") or ""),
        "65: critérios concordam (não prescrita) e o resultado ficou: %s | %s" % (L["ppe_status"], S.get("saldo_rotulo")))
L = run(r65("01/05/2014"), 1)
confere(L["ppe_status"].startswith("A VERIFICAR"), "65: critérios divergentes deveriam continuar a verificar: %s" % L["ppe_status"])

# ---------- 66: denúncia -> sentença acima do dobro do prazo: a verificar (art. 366 do CPP) ----------
def r66(den, sent):
    return reg([crime(data_infracao="01/06/2010", data_denuncia=den, data_sentenca=sent, transito_mp="01/03/2021", transito_processo="01/03/2021")])
L = run(r66("01/07/2010", "01/07/2016"))  # 6 anos, prazo 4: aparente
confere(L["retro_cor"] == "vermelho", "66: intervalo entre 1 e 2 vezes o prazo continua aparente: %s" % L["retro_status"])
L = run(r66("01/07/2010", "01/07/2020"))  # 10 anos > 2 x 4; com a suspensão máxima (8 anos pela pena máxima de 4) não prescreveria
confere(L["retro_cor"] == "amarelo" and "art. 366" in L["retro_status"], "66: acima do dobro deveria ficar a verificar: %s" % L["retro_status"])
L = run(reg([crime(data_infracao="01/06/2005", data_denuncia="01/07/2005", data_sentenca="01/07/2020", transito_mp="01/03/2021", transito_processo="01/03/2021")]))
confere(L["retro_cor"] == "vermelho" and "mesmo com a suspensão máxima" in L["retro_detalhe"],
        "66: 15 anos passa até da suspensão máxima: %s" % L["retro_status"])
L = run(aj(r66("01/07/2010", "01/07/2020"), {"susp366_ini": "01/01/2011", "susp366_fim": "01/01/2012"}))
confere("conferir suspensão do art. 366" not in L["retro_status"], "66: suspensão informada pelo operador dispensa a ressalva: %s" % L["retro_status"])

# ---------- 67: Lei 15.160/2025 com o sexo da vítima desconhecido: a verificar ----------
def r67(sent, tr):
    return reg([crime(artigo="ART 215-A: Importunação sexual", tipo_penal="CAPUT: Praticar..., Reclusão: 1 a 5 anos", data_infracao="01/08/2025",
                      data_denuncia="01/09/2025", data_sentenca=sent, transito_mp=tr, transito_processo=tr)], data_nascimento="01/01/2006")
H67 = date(2028, 6, 1)
L = run(r67("01/12/2025", "10/01/2026"), hoje=H67)
confere(not L["art115"] and L["ppe_status"].startswith("A VERIFICAR") and "sexo da vítima" in " ".join(L["ppe_faltam"]),
        "67: executória sem o sexo da vítima deveria ficar a verificar: %s | %s" % (L["ppe_status"], L["ppe_faltam"]))
confere(any("art. 115 a verificar" in a for a in L["avisos"]), "67: aviso do art. 115 ainda nega a metade: %s" % L["avisos"])
L = run(r67("01/10/2027", "01/11/2027"), hoje=H67)
confere(L["retro_cor"] == "amarelo" and "sexo da" in L["retro_status"], "67: punitiva com a metade deveria ficar a verificar: %s" % L["retro_status"])
L = run(aj(r67("01/12/2025", "10/01/2026"), {"art115": "nao"}), hoje=H67)
confere(not L["ppe_status"].startswith("A VERIFICAR"), "67: com o art. 115 afastado pelo operador não há dúvida: %s" % L["ppe_status"])

# ---------- 68: art. 28 - o +1/3 da reincidência sobre os 2 anos fica a verificar ----------
c28 = crime(lei="11343/06 - Lei de Drogas", artigo="ART 28: Porte de droga para consumo pessoal", tipo_penal="CAPUT: Quem adquirir",
            pena_imposta="0 ano(s), 5 mês(es) e 0 dia(s)", pena_total_processo="0a5m0d - PENA ORIGINÁRIA", data_infracao="01/01/2023",
            data_denuncia="01/02/2023", data_sentenca="01/06/2023", transito_mp="01/03/2024", transito_processo="01/03/2024", reincidente_comum="S")
L = run(reg([c28, cB], pena_total="3a5m0d"))
confere(L["ppe_status"].startswith("A VERIFICAR: o resultado depende do +1/3 da reincidência"),
        "68: art. 28 com +1/3 decisivo deveria ficar a verificar: %s" % L["ppe_status"])

# ---------- 70: progressão ou livramento no intervalo bastam para "não prescrita - conferir"; remição não ----------
def r70(incs):
    return reg([crime(data_infracao="13/12/2016", data_denuncia="01/02/2017", data_sentenca="01/05/2018", transito_mp="10/07/2018",
                      transito_processo="10/07/2018", pena_imposta="2 ano(s), 0 mês(es) e 0 dia(s)", pena_total_processo="2a0m0d - PENA ORIGINÁRIA")],
               [ev(PRI, "PRISÃO DEFINITIVA", "30/10/2017", P), ev(INT, "FUGA", "26/03/2019"), ev(PRI, "RECAPTURA", "18/08/2025", P)], incs, pena_total="2a0m0d")
L = run(r70([inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Aberto - Progressão de Regime", "14/04/2020")]))
confere(L["ppe_status"].startswith("Não prescrita - conferir") and L["ppe_cor"] == "", "70: progressão no intervalo: %s" % L["ppe_status"])
confere("conferir" in (L.get("ppe_quadro") or {}).get("prazo", ""), "70: quadro sem o conferir: %s" % (L.get("ppe_quadro") or {}).get("prazo"))
L = run(r70([inc("REMIÇÃO", "10 Dia(s) Remido(s)", "14/04/2020")]))
confere(L["ppe_status"].startswith("A VERIFICAR"), "70: remição no intervalo continua a verificar: %s" % L["ppe_status"])

# ---------- 71: sursis e a audiência admonitória ----------
c71 = crime(data_infracao="01/01/2015", data_denuncia="01/02/2015", data_sentenca="01/06/2015", transito_mp="01/09/2015", transito_processo="01/09/2015")
L = run(aj(reg([c71]), {"modalidade": "SURSIS"}))
confere(L["ppe_status"] == "A VERIFICAR: data da audiência admonitória do sursis não informada" and "audiência admonitória" in L["ppe_faltam"][0],
        "71: sursis sem audiência deveria ficar a verificar: %s" % L["ppe_status"])
L = run(aj(reg([c71]), {"modalidade": "SURSIS", "audiencia_sursis": "01/11/2015"}))
confere(L["ppe_status"] == "Não corre (período de prova do sursis)", "71: com a audiência, período de prova: %s" % L["ppe_status"])
L = run(aj(reg([c71]), {"modalidade": "SURSIS", "audiencia_sursis": "01/11/2020"}))
confere(L["ppe_cor"] == "vermelho", "71: audiência depois do prazo (4 anos do trânsito): %s" % L["ppe_status"])
L = run(aj(reg([c71]), {"modalidade": "SURSIS", "revogacao_sursis": "01/11/2020"}))
confere(L["ppe_status"].startswith("A VERIFICAR") and "revogação" in L["ppe_faltam"][0], "71: revogado sem audiência, prazo vencido antes: %s" % L["ppe_status"])
L = run(aj(reg([c71]), {"modalidade": "SURSIS", "audiencia_sursis": "01/11/2015", "revogacao_sursis": "01/11/2023"}))
confere(L["ppe_status"].startswith(("Não prescrita", "Prescrição executória em")), "71: audiência e revogação: %s" % L["ppe_status"])
confere(app._validar_presc_ajuste({"valores": {"audiencia_sursis": "01/11/2015"}}) is None, "71: campo da audiência recusado na validação")

# ---------- 72: detração exclusiva aferida pelo início da prisão ----------
D_ = "9100005-55.2018.8.12.0001"
def r72(fato_d):
    return reg([crime(data_infracao="01/12/2017", data_denuncia="01/02/2018", data_sentenca="01/03/2019", transito_mp="01/06/2019",
                      transito_processo="01/06/2019", pena_imposta="0 ano(s), 6 mês(es) e 0 dia(s)", pena_total_processo="0a6m0d - PENA ORIGINÁRIA"),
                crime(processo_criminal=D_, data_infracao=fato_d, data_denuncia="01/02/2019", data_sentenca="01/06/2020", transito_mp="01/09/2020",
                      transito_processo="01/09/2020")],
               [ev(PRI, "PRISÃO PREVENTIVA", "01/01/2018", P), ev(INT, "LIBERDADE PROVISÓRIA", "01/12/2018")], pena_total="1a6m0d")
L = run(r72("01/06/2018"))
confere(L.get("ppe_detracao_cobre") and L.get("ppe_detracao_exclusiva"), "72: fato da outra condenação depois do início da prisão: exclusiva")
L = run(r72("01/11/2017"))
confere(L.get("ppe_detracao_cobre") and not L.get("ppe_detracao_exclusiva"), "72: fato anterior ao início da prisão: não exclusiva")

# ---------- 73: término calculado sem o cálculo do SEEU abate as remições concedidas ----------
def r73(incs):
    return reg([crime(data_infracao="01/06/2024", data_denuncia="01/07/2024", data_sentenca="01/10/2024", transito_mp="01/12/2024",
                      transito_processo="01/12/2024", pena_imposta="2 ano(s), 0 mês(es) e 0 dia(s)", pena_total_processo="2a0m0d - PENA ORIGINÁRIA")],
               [ev(PRI, "PRISÃO DEFINITIVA", "01/01/2025", P)], incs, pena_total="2a0m0d", pena_cumprida="0a0m0d", pena_remanescente="2a0m0d")
t0 = rv.termino_calc(r73([]))
t1 = rv.termino_calc(r73([inc("REMIÇÃO", "30 Dia(s) Remido(s)", "01/06/2025")]))
confere(t0 and t1 and t0 - t1 == timedelta(days=30), "73: término sem cálculo do SEEU não abateu a remição: %s / %s" % (t0, t1))

# ---------- 74: teto da Súmula 415 com e sem a metade do art. 115 ----------
def r74(sent):
    r = reg([crime(data_infracao="01/12/2010", data_denuncia="01/01/2011", data_sentenca=sent, transito_mp="01/03/2021", transito_processo="01/03/2021")],
            data_nascimento="01/01/1991")
    return aj(r, {"susp366_ini": "01/01/2012", "susp366_fim": "01/01/2018"})
L = run(r74("01/06/2018"))
confere(L["retro_cor"] == "amarelo" and "teto da suspensão" in L["retro_status"] and "Conta alternativa" in L["retro_detalhe"],
        "74: contas do teto divergentes deveriam ficar a verificar: %s" % L["retro_status"])
L = run(r74("01/06/2020"))
confere(L["retro_cor"] == "vermelho", "74: as duas contas dão prescrição - sem a verificar: %s" % L["retro_status"])

# ---------- 75: folga de até 30 dias: conferir a data de publicação ----------
def r75(sent):
    return reg([crime(data_infracao="01/06/2010", data_denuncia="01/07/2010", data_sentenca=sent, transito_mp="01/03/2015", transito_processo="01/03/2015")])
L = run(r75("15/07/2014"))
confere(L["retro_cor"] == "vermelho" and L["retro_status"].endswith("conferir a data de publicação da sentença"), "75: folga curta: %s" % L["retro_status"])
L = run(r75("01/12/2014"))
confere(L["retro_cor"] == "vermelho" and "publicação" not in L["retro_status"], "75: folga longa: %s" % L["retro_status"])
L = run(r75("20/06/2014"))
confere(not L["retro_cor"] and "se a publicação foi depois dessa data" in L["retro_detalhe"], "75: sentença pouco antes do fim do prazo: %s" % L["retro_status"])

if falhas:
    print("FALHOU (quesitos de 16/10 - prescrição e extinção):")
    for f in falhas:
        print("  " + f)
    sys.exit(1)
print("ok: quesitos de 16/10 - prescrição e extinção (tráfico privilegiado, prisão por outro processo na restritiva e no sursis, Súmula 617 na "
      "Extinção, critérios de imputação, art. 366, Lei 15.160, art. 28, retomada, audiência admonitória, detração exclusiva, remição no "
      "término, teto da Súmula 415, publicação da sentença)")
