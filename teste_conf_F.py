"""Teste de regressão: conferência manual 7.13, frente F (prescrição punitiva e executória). Casos sintéticos, um por causa corrigida.
Rodar: python teste_conf_F.py (sai com código 1 se algum caso falhar)."""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_prescricao as rp

HOJE = date(2026, 10, 20)
falhas = []
FURTO = "CAPUT: Subtrair, para si ou para outrem, coisa alheia móvel., Reclusão: 1 a 4 anos E Multa"


def confere(cond, msg):
    if not cond:
        falhas.append(msg)


def crime(fato, tr, pena, proc="0000001-00.2015.8.12.0001", artigo="ART 155: Furto", lei="2848/40 - Código Penal", tipo=FURTO, tmp=None,
          ptp="PENA ORIGINÁRIA", den="", sent="", **kw):
    c = {"processo_criminal": proc, "data_infracao": fato, "data_denuncia": den, "data_sentenca": sent, "transito_mp": tr if tmp is None else tmp,
         "transito_processo": tr, "lei": lei, "artigo": artigo, "tipo_penal": tipo, "pena_imposta": pena, "pena_total_processo": "%s - %s" % (pena, ptp),
         "reincidente_comum": "N", "reincidente_especifico": "N", "extinto": "Não"}
    c.update(kw)
    return c


def ev(data, motivo, tipo="PRISÃO/INÍCIO DE CUMPRIMENTO", proc="", **kw):
    e = {"tipo": tipo, "motivo": motivo, "data": data, "processos": proc}
    e.update(kw)
    return e


def inc(tipo, compl, ref, dec=None, sit="CONCEDIDO", proc=""):
    return {"tipo": tipo, "complemento": compl, "data_referencia": ref, "data_decisao": dec or ref, "situacao": sit, "processos": proc}


def reg(crimes, eventos=(), incidentes=(), nasc="01/01/1980", **kw):
    r = {"_crimes": list(crimes), "_eventos": list(eventos), "_incidentes": list(incidentes), "data_nascimento": nasc,
         "data_geracao_rspe": "06/10/2026", "situacao_cumprimento": "EM CUMPRIMENTO"}
    r.update(kw)
    return r


def linha(r, proc=None, crime_=None):
    return next(l for l in rp.analisar(r, HOJE)["presc_linhas"] if (proc is None or l["proc_crim"] == proc) and (crime_ is None or crime_ in l["crime"]))


A, B, C = "0000101-11.2018.8.12.0001", "0000202-22.2019.8.12.0001", "0000303-33.2020.8.12.0001"
UM, DOIS, OITO = "1 ano(s), 0 mês(es) e 0 dia(s)", "2 ano(s), 0 mês(es) e 0 dia(s)", "0 ano(s), 8 mês(es) e 0 dia(s)"
ZERO = "0 ano(s), 0 mês(es) e 0 dia(s)"

# 1. intercorrente aparente sem "APELAÇÃO" na pena: um intervalo sentença -> trânsito maior que o prazo pressupõe recurso, e o acórdão
# (mesmo confirmatório) interrompe - A VERIFICAR "conferir a data do acórdão"; passando do dobro, continua aparente
l = linha(reg([crime("01/01/2018", "01/03/2024", DOIS, proc=A, den="01/02/2018", sent="01/06/2019")]))  # 4a9m, prazo 4 anos
confere(l["retro_cor"] == "amarelo" and l["retro_status"].endswith("conferir a data do acórdão"), "1: intercorrente sem acórdão: %s" % l["retro_status"])
confere(not l["pp_fund"], "1: sem fundamentação afirmativa no a verificar")
l = linha(reg([crime("01/01/2010", "01/03/2019", DOIS, proc=A, den="01/02/2010", sent="01/06/2010")]))  # 8a9m: passa do dobro
confere(l["retro_cor"] == "vermelho" and "intercorrente" not in l["retro_status"] and "sentença → trânsito" in l["retro_status"],
        "1: passa do dobro do prazo, continua aparente: %s" % l["retro_status"])

# 2. idade incoerente também na denúncia (fato e denúncia com o mesmo erro de ano): o intervalo denúncia -> sentença usa data em dúvida
l = linha(reg([crime("30/10/2013", "17/11/2025", "3 ano(s), 0 mês(es) e 0 dia(s)", proc=A, den="20/11/2013", sent="12/06/2025")], nasc="17/07/2004"))
confere(l["retro_cor"] == "amarelo" and "datas incoerentes" in l["retro_status"], "2: idade incoerente na denúncia: %s" % l["retro_status"])

# 3. pena abaixo do mínimo cominado que coincide com a exasperação (1/6) da pena de outro crime da mesma ação (concurso formal): com o
# mínimo (1 ano) a retroativa não se completa - A VERIFICAR; furto de 8 meses sozinho (minorante) continua aparente
cor = "CAPUT: Corromper ou facilitar a corrupção de menor de 18 anos, Reclusão: 1 a 4 anos Sem Multa"
crs = [crime("02/09/2010", "02/05/2013", "0 ano(s), 4 mês(es) e 0 dia(s)", proc=A, artigo="ART 244-B: Corrupção de menores", lei="8069/90 - ECA",
             tipo=cor, den="05/11/2010", sent="13/09/2012"),
       crime("02/09/2010", "02/05/2013", DOIS, proc=A, tipo="§ 4º, Reclusão: 2 a 8 anos E Multa", den="05/11/2010", sent="13/09/2012")]
l = linha(reg(crs, nasc="01/01/1991"), crime_="244-B")
confere(l["retro_cor"] == "amarelo" and "abaixo do mínimo" in l["retro_status"], "3: concurso formal lançado como pena: %s" % l["retro_status"])
l = linha(reg([crime("23/06/2024", "09/07/2026", OITO, proc=A, den="08/07/2024", sent="12/03/2026")], nasc="16/09/2003"))
confere(l["retro_cor"] == "vermelho", "3: furto de 8 meses (minorante) continua aparente: %s" % l["retro_status"])

# 4. suspensão condicional do processo (Lei 9.099, art. 89, § 6º): crime que a admite (mínimo de até 1 ano, sem concurso que passe
# de 1 ano - Súmula 243/STJ) com a retroativa aparente entre denúncia e sentença: alerta "conferir"
confere("conferir suspensão condicional do processo" in l["retro_status"], "4: furto simples sem alerta do art. 89: %s" % l["retro_status"])
l = linha(reg([crime("23/06/2024", "09/07/2026", OITO, proc=A, den="08/07/2024", sent="12/03/2026"),
               crime("23/06/2024", "09/07/2026", DOIS, proc=A, tipo="§ 4º, Reclusão: 2 a 8 anos E Multa", den="08/07/2024", sent="12/03/2026")],
              nasc="16/09/2003"), crime_="art. 155 CP")
confere("suspensão condicional" not in l["retro_status"], "4: concurso com mínimo somado acima de 1 ano (Súm. 243): %s" % l["retro_status"])
# "Suspenso: Sim" no SEEU com a executória aparente: A VERIFICAR
l = linha(reg([crime("01/01/2015", "01/03/2016", UM, proc=A, den="01/02/2015", sent="01/06/2015", suspenso="Sim")]))
confere(l["ppe_cor"] == "amarelo" and "suspensa" in l["ppe_status"], "4: Suspenso: Sim na executória: %s" % l["ppe_status"])

# 5. prisão em flagrante com data anterior ao fato da ação que ela lista: a executória aparente fica a verificar
crs = [crime("09/03/2015", "03/07/2017", DOIS, proc=A, den="31/08/2016", sent="31/01/2017"),
       crime("28/09/2019", "01/02/2021", DOIS, proc=B, den="01/10/2019", sent="01/06/2020", artigo="ART 33: Tráfico", lei="11343/06 - Lei de Drogas",
             tipo="CAPUT: Importar, Reclusão: 5 a 15 anos E Multa")]
evs = [ev("28/09/2018", "PRISÃO EM FLAGRANTE", proc="%s, %s" % (A, B)), ev("03/06/2019", "ALVARÁ DE SOLTURA", tipo="INTERRUPÇÃO")]
l = linha(reg(crs, evs), A)
confere(l["ppe_status"].startswith("A VERIFICAR") and "datas incoerentes" in l["ppe_status"]
        and any("28/09/2018" in f for f in l["ppe_faltam"]), "5: flagrante anterior ao fato: %s | %s" % (l["ppe_status"], l["ppe_faltam"]))

# 6. art. 28 sem pena: custódia contínua desde pouco depois do termo - o prazo de 2 anos não se completa em nenhuma hipótese
crs = [crime("01/01/2016", "18/07/2016", ZERO, proc=A, artigo="ART 28: Porte de droga para consumo pessoal", lei="11343/06 - Lei de Drogas",
             tipo="CAPUT: Quem adquirir", den="01/02/2016", sent="01/06/2016"),
       crime("01/03/2016", "01/03/2017", DOIS, proc=B, den="01/04/2016", sent="01/09/2016")]
evs = [ev("01/08/2016", "PRISÃO EM FLAGRANTE", proc=B), ev("01/08/2017", "INÍCIO DO CUMPRIMENTO REGIME FECHADO", proc="%s, %s" % (A, B))]
l = linha(reg(crs, evs), A)
confere(l["ppe_status"].startswith("Não prescrita") and l["ppe_cor"] == "" and not l["ppe_faltam"], "6: art. 28 não prescrito: %s" % l["ppe_status"])

# 7. sem trânsito no RSPE: preso desde antes da sentença e sem liberdade depois -> não prescrita qualquer que seja a data do trânsito;
# e prescrição em qualquer data quando, depois da sentença, nunca mais houve custódia
A14 = "0000101-11.2014.8.12.0001"  # ação de 2014: a regra da distribuição (preso logo depois dela) não se aplica
l = linha(reg([crime("01/01/2016", "", UM, proc=A14, den="01/02/2016", sent="01/06/2016", tmp="")],
              [ev("01/01/2016", "PRISÃO EM FLAGRANTE", proc=A14)]))
confere(l["ppe_status"].startswith("Não prescrita (qualquer que seja a data do trânsito"), "7: não prescrita pelos limites: %s" % l["ppe_status"])
l = linha(reg([crime("01/01/2016", "", "0 ano(s), 6 mês(es) e 0 dia(s)", proc=A, den="01/02/2016", sent="01/06/2016", tmp="")]))
confere(l["ppe_cor"] == "vermelho" and "qualquer que seja a data do trânsito" in l["ppe_status"] and l["retro_cor"] == "amarelo"
        and not l["ppe_fund"], "7: prescrita em qualquer data de trânsito: %s / %s" % (l["ppe_status"], l["retro_status"]))
l = linha(reg([crime("01/01/2016", "", "0 ano(s), 6 mês(es) e 0 dia(s)", proc=A14, den="01/02/2016", sent="01/06/2016", tmp="")],
              [ev("01/01/2016", "PRISÃO EM FLAGRANTE", proc=A14), ev("01/03/2018", "ALVARÁ DE SOLTURA", tipo="INTERRUPÇÃO"),
               ev("01/06/2022", "PRISÃO EM FLAGRANTE", proc=B)]))
confere(l["ppe_cor"] == "cinza", "7: resultado que depende da data do trânsito continua cinza: %s" % l["ppe_status"])

# 8. reincidência comum em branco, mas fração de primário aplicada pelo SEEU: não é dado ausente
crs = [crime("19/04/2017", "21/05/2018", UM, proc=A, den="10/07/2017", sent="12/04/2018", reincidente_comum="",
             fracao_progressao="1/6 - Comum", fracao_livramento="1/3 - Comum Primário")]
l = linha(reg(crs, [ev("21/05/2018", "PRISÃO EM FLAGRANTE", proc=A), ev("04/09/2018", "LIBERDADE PROVISÓRIA", tipo="INTERRUPÇÃO"),
                   ev("10/10/2020", "RECAPTURA/REINÍCIO DE CUMPRIMENTO", proc=A)], nasc="01/01/1998"))
confere("reincidência" not in l["ppe_status"] and l["ppe_cor"] == "vermelho", "8: fração de primário resolve a reincidência: %s" % l["ppe_status"])

# 9. o RSPE marca primário, mas outra condenação transitou antes do fato: a hipótese com o +1/3 muda o resultado - A VERIFICAR
crs = [crime("19/01/2011", "19/05/2014", "12 ano(s), 0 mês(es) e 0 dia(s)", proc=A, artigo="ART 121: Homicídio", den="04/04/2011", sent="14/04/2014",
             tipo="§ 2º, Reclusão: 12 a 30 anos"),
       crime("06/05/2016", "11/12/2018", DOIS, proc=B, artigo="ART 14: Porte ilegal", lei="10826/03", tipo="CAPUT: Portar, Reclusão: 2 a 4 anos E Multa",
             den="20/05/2016", sent="22/05/2017")]
l = linha(reg(crs, [ev("01/06/2023", "RECAPTURA/REINÍCIO DE CUMPRIMENTO", proc=B)]), B)
confere(l["ppe_status"].startswith("A VERIFICAR") and "marca primário" in l["ppe_status"]
        and any("RHC 6.611" in f for f in l["ppe_faltam"]), "9: primário com condenação anterior transitada: %s" % l["ppe_status"])

# 10. pena remanescente do SEEU vale como saldo na fuga quando o SEEU parou o cálculo nela (depois, só lançamentos da ficha) e a pena total
# da execução é a deste crime
crs = [crime("06/03/2010", "19/07/2017", "5 ano(s), 4 mês(es) e 0 dia(s)", proc=A, artigo="ART 157: Roubo", tipo="§ 2º-A, Reclusão: 4 a 10 anos E Multa",
             den="23/11/2010", sent="19/11/2014"),
       crime("27/06/2018", "19/09/2025", "2 ano(s), 11 mês(es) e 0 dia(s)", proc=B, den="01/08/2018", sent="26/09/2019")]
evs = [ev("25/02/2019", "INÍCIO DO CUMPRIMENTO REGIME FECHADO", proc=A), ev("01/10/2019", "INTERRUPÇÃO DO CUMPRIMENTO DA PENA", tipo="INTERRUPÇÃO"),
       ev("09/10/2025", "RECAPTURA (lançado pela ficha SIAPEN)", tipo="REINÍCIO", _ficha=True)]
l = linha(reg(crs, evs, pena_total="5a4m0d", pena_remanescente="4a8m23d"), A)
confere(l["ppe_status"] == "Não prescrita", "10: pena remanescente do SEEU como saldo na fuga: %s" % l["ppe_status"])

# 11. perda de dias remidos (LEP, art. 127): a remição anterior à perda não reduz o saldo das fugas posteriores
crs = [crime("01/01/2008", "01/03/2009", "3 ano(s), 0 mês(es) e 0 dia(s)", proc=A, den="01/02/2008", sent="01/06/2008")]
evs = [ev("01/03/2009", "INÍCIO DO CUMPRIMENTO REGIME FECHADO", proc=A), ev("01/03/2010", "FUGA", tipo="INTERRUPÇÃO")]
incs = [inc("REMIÇÃO", "100 Dia(s) Remido(s)", "01/06/2009"), inc("DIAS PERDIDOS NA REMIÇÃO", "100", "01/01/2010")]
l = linha(reg(crs, evs, incs))
confere("100 dias de remição" not in l["ppe_detalhe"], "11: remição perdida entrou no saldo: %s" % l["ppe_detalhe"])

# 12. detração: condenação do art. 28 (pena 0) ou extinta por prescrição não recebe a custódia de outra ação
crs = [crime("01/01/2017", "01/06/2018", DOIS, proc=A, den="01/02/2017", sent="01/03/2018"),
       crime("01/06/2016", "01/04/2017", ZERO, proc=B, artigo="ART 28: Porte de droga para consumo pessoal", lei="11343/06 - Lei de Drogas",
             tipo="CAPUT: Quem adquirir", den="01/07/2016", sent="01/09/2016"),
       crime("01/06/2016", "01/05/2017", UM, proc=C, den="01/07/2016", sent="01/09/2016", extinto="Sim", extincao_motivo="PRESCRIÇÃO",
             data_extincao="25/07/2025")]
l = linha(reg(crs, [ev("15/03/2017", "PRISÃO EM FLAGRANTE", proc=A)]), A)
confere("eram cumprimento de outra condenação" not in l["ppe_detalhe"] and "443 dias (detração" in l["ppe_detalhe"],
        "12: detração atribuída a condenação sem pena privativa ou prescrita: %s" % l["ppe_detalhe"])

# 13. suspensão até o início do cumprimento desta pena: o dia da interrupção não conta (03 a 20/02 = 18 dias)
crs = [crime("25/07/2018", "02/10/2023", "2 ano(s), 6 mês(es) e 0 dia(s)", proc=A, den="30/08/2018", sent="02/08/2022", tmp=""),
       crime("01/01/2018", "01/01/2025", DOIS, proc=B, den="01/02/2018", sent="01/06/2018", tmp="")]
evs = [ev("03/02/2025", "INÍCIO DO CUMPRIMENTO REGIME FECHADO", proc=B), ev("21/02/2025", "PRISÃO EM FLAGRANTE", proc="%s, %s" % (A, B))]
l = linha(reg(crs, evs), A)
confere("18 dias de suspensão" in l["ppe_detalhe"] and "19 dias de suspensão" not in l["ppe_detalhe"], "13: dias de suspensão: %s" % l["ppe_detalhe"])

if falhas:
    print("FALHOU (conferência 7.13 - frente F, prescrição):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: conferência 7.13 - frente F (acórdão na intercorrente, idade incoerente na denúncia, pena abaixo do mínimo, suspensão do processo, "
      "\"Suspenso: Sim\", flagrante anterior ao fato, art. 28, trânsito ausente, reincidência, remanescente do SEEU, perda de remição, "
      "detração, dias de suspensão)")
