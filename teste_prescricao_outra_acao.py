"""Teste de regressão: prisão por outras ações da mesma execução antes de a ação do crime entrar no cumprimento.
Enquanto a pessoa está presa só pelas outras ações (eventos do RSPE ou entrada na ficha que não citam a ação do crime), a executória
deste crime fica suspensa (CP, art. 116, p. único); o evento que passa a listar a ação, ou o somatório das penas que a inclui, é início
ou continuação do cumprimento (art. 117, V). Vale para qualquer crime, inclusive o art. 28 da Lei 11.343/2006 sem pena no RSPE.
Dados sintéticos. Rodar: python teste_prescricao_outra_acao.py (sai com código 1 se algum caso falhar)."""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_prescricao as rp

HOJE = date(2026, 10, 13)
falhas = []


def confere(cond, msg):
    if not cond:
        falhas.append(msg)


def crime(proc, tr, pena, tmp=None, artigo="ART 155: Furto", lei="2848/40 - Código Penal", fato="01/01/2014", sent="", **kw):
    c = {"processo_criminal": proc, "data_infracao": fato, "data_denuncia": "", "data_sentenca": sent, "transito_mp": tr if tmp is None else tmp,
         "transito_processo": tr, "lei": lei, "artigo": artigo, "tipo_penal": "RECLUSÃO", "pena_imposta": pena,
         "pena_total_processo": "%s - PENA ORIGINÁRIA" % pena, "reincidente_comum": "N", "reincidente_especifico": "N", "extinto": "Não"}
    c.update(kw)
    return c


def ev(data, motivo, tipo="PRISÃO/INÍCIO DE CUMPRIMENTO", proc=""):
    return {"tipo": tipo, "motivo": motivo, "data": data, "processos": proc}


def soma(data, procs):
    return {"tipo": "SOMATÓRIO DAS PENAS", "complemento": "", "data_referencia": data, "data_decisao": data, "processos": procs, "situacao": "CONCEDIDO"}


def reg(crimes, eventos=(), incidentes=()):
    return {"_crimes": list(crimes), "_eventos": list(eventos), "_incidentes": list(incidentes), "data_nascimento": "01/01/1980",
            "data_geracao_rspe": "10/10/2026", "situacao_cumprimento": "EM CUMPRIMENTO", "processo_execucao": "9000000-00.2017.8.12.0001"}


def linha(r, proc, ficha=None):
    return next(l for l in rp.analisar(r, HOJE, ficha=ficha)["presc_linhas"] if l["proc_crim"] == proc)


A, B, C = "9000001-11.2015.8.12.0001", "9000002-22.2017.8.12.0001", "9000003-33.2017.8.12.0110"

# 1. art. 28 sem pena: preso preventivamente por A e B desde antes do trânsito do art. 28 (C) até a interrupção; a recaptura passa a
# listar C. O prazo de 2 anos (art. 30) não terminou em 12/09/2020: ficou suspenso enquanto preso pelas outras ações e só correram
# os 5 dias entre a interrupção e a recaptura
crimes1 = [crime(A, "13/06/2017", "1 ano(s), 0 mês(es) e 0 dia(s)"),
           crime(B, "25/07/2022", "16 ano(s), 0 mês(es) e 0 dia(s)", artigo="ART 121: Matar alguem:"),
           crime(C, "27/02/2019", "0 ano(s), 0 mês(es) e 0 dia(s)", tmp="13/09/2018", artigo="ART 28: Porte de droga para consumo pessoal",
                 lei="11343/06 - Lei de Drogas", fato="01/06/2017", sent="31/08/2018")]
evs1 = [ev("05/08/2017", "PRISÃO PREVENTIVA", proc="%s, %s" % (A, B)),
        ev("01/04/2025", "DESCUMPRIMENTO DAS CONDIÇÕES", tipo="INTERRUPÇÃO"),
        ev("06/04/2025", "RECAPTURA/REINÍCIO DE CUMPRIMENTO", proc="%s, %s, %s" % (A, C, B))]
l = linha(reg(crimes1, evs1), C)
st = l["ppe_status"]
confere("terminou" not in st and "12/09/2020" not in st, "1: art. 28 ainda dado como terminado em 2020: %s" % st)
confere("não esgotado" in st and "suspenso de 13/09/2018 a 01/04/2025" in st and "2.392 dias" in st and "art. 116, p. único" in st
        and "correram 5 dias" in st and "06/04/2025" in st and "hoje em cumprimento" in st, "1: status sem a suspensão e os dias: %s" % st)
confere("preso pelos processos %s e %s (prisão preventiva de 05/08/2017), quando esta ação penal ainda não estava em cumprimento" % (A, B)
        in l["ppe_detalhe"], "1: memória sem o período de prisão pelas outras ações: %s" % l["ppe_detalhe"])
confere(l["ppe_cor"] == "amarelo" and l["ppe_faltam"], "1: art. 28 sem pena continua a verificar (pena e cumprimento fora do RSPE)")

# 1b. com o somatório que inclui C (29/08/2022): a suspensão vai até ele, que interrompe (LEP, art. 111; CP, art. 117, V)
l = linha(reg(crimes1, evs1, [soma("29/08/2022", "%s, %s, %s" % (A, C, B))]), C)
st = l["ppe_status"]
confere("suspenso de 13/09/2018 a 29/08/2022" in st and "1.446 dias" in st and "interrompido em 29/08/2022 e 06/04/2025" in st
        and "correram 5 dias" in st, "1b: somatório como início do cumprimento: %s" % st)
confere("incidente de somatório das penas de 29/08/2022 inclui esta ação penal" in l["ppe_detalhe"], "1b: memória sem o somatório")

# 1c. sem a recaptura que lista C e sem somatório: a prisão pelas outras ações segue a regra antiga (cumprimento da execução unificada)
l = linha(reg(crimes1, evs1[:2]), C)
confere("ainda não estava em cumprimento" not in l["ppe_detalhe"], "1c: sem marco de entrada da ação, não há suspensão por outra ação")

# 2. qualquer crime: mesma estrutura com furto (pena de 1 ano, prazo de 4 anos) - suspensão até a recaptura que lista a ação, que
# interrompe; a fuga da prisão pelas outras ações não é evasão desta pena (ela não estava em cumprimento)
D = "9000004-44.2016.8.12.0001"
crimes2 = [crime(A, "13/06/2015", "6 ano(s), 0 mês(es) e 0 dia(s)"), crime(D, "01/03/2016", "1 ano(s), 0 mês(es) e 0 dia(s)")]
evs2 = [ev("01/01/2016", "PRISÃO DEFINITIVA", proc=A), ev("01/03/2024", "FUGA", tipo="INTERRUPÇÃO"),
        ev("01/06/2024", "RECAPTURA/REINÍCIO DE CUMPRIMENTO", proc="%s, %s" % (A, D))]
l = linha(reg(crimes2, evs2, [soma("15/05/2024", "%s, %s" % (A, D))]), D)
confere(l["ppe_cor"] not in ("vermelho", "amarelo") and l["ppe_status"].startswith(("Não prescrita", "Não corre")), "2: furto: %s" % l["ppe_status"])
confere("De 01/03/2016 a 01/03/2024, preso pelo processo %s (prisão definitiva de 01/01/2016), quando esta ação penal ainda não estava em "
        "cumprimento: a prescrição ficou suspensa nesse período, 2.922 dias (CP, art. 116, p. único)." % A in l["ppe_detalhe"],
        "2: memória da suspensão: %s" % l["ppe_detalhe"])
confere("Evasão em 01/03/2024" not in l["ppe_detalhe"] and "Sem cumprimento desta pena de 01/03/2016" in l["ppe_detalhe"],
        "2: fuga da prisão pelas outras ações tratada como evasão desta pena")

# 3. a ação já estava no somatório no termo inicial: a prisão já era cumprimento da pena unificada (LEP, art. 111) - nada muda
l = linha(reg(crimes2, evs2, [soma("01/03/2016", "%s, %s" % (A, D))]), D)
confere("ainda não estava em cumprimento" not in l["ppe_detalhe"] and "Evasão em 01/03/2024" in l["ppe_detalhe"],
        "3: ação já no somatório antes da prisão: %s" % l["ppe_detalhe"])

# 4. sem somatório no RSPE e com resultado mais favorável se a ação já estivesse na execução: A VERIFICAR (não se tira a hipótese)
E = "9000005-55.2015.8.12.0001"
crimes4 = [crime(A, "13/06/2014", "10 ano(s), 0 mês(es) e 0 dia(s)"), crime(E, "01/01/2015", "3 ano(s), 0 mês(es) e 0 dia(s)")]
evs4 = [ev("01/06/2014", "PRISÃO DEFINITIVA", proc=A), ev("01/01/2016", "FUGA", tipo="INTERRUPÇÃO"),
        ev("01/01/2022", "RECAPTURA/REINÍCIO DE CUMPRIMENTO", proc="%s, %s" % (A, E))]
l = linha(reg(crimes4, evs4), E)
confere(l["ppe_status"] == "A VERIFICAR: o resultado depende de quando esta ação penal entrou no cumprimento da execução"
        and "somatório ou unificação das penas" in (l["ppe_faltam"] or [""])[0], "4: sem somatório: %s | %s" % (l["ppe_status"], l["ppe_faltam"]))
# com o somatório depois da fuga, a data de entrada da ação está provada: não prescrita (prazo de 8 anos pela pena, sem saldo)
l = linha(reg(crimes4, evs4, [soma("01/06/2021", "%s, %s" % (A, E))]), E)
confere(l["ppe_status"].startswith(("Não prescrita", "Não corre")), "4: com somatório depois da fuga: %s" % l["ppe_status"])

# 5. ficha SIAPEN: entrada "para cumprimento de pena" só nos autos de outra ação, antes de a ação do crime entrar no cumprimento,
# suspende (art. 116, p. único) em vez de valer como cumprimento desta pena
F = "9000006-66.2016.8.12.0001"
crimes5 = [crime(A, "13/06/2014", "8 ano(s), 0 mês(es) e 0 dia(s)"), crime(F, "01/03/2017", "1 ano(s), 0 mês(es) e 0 dia(s)")]
evs5 = [ev("01/02/2023", "RECAPTURA/REINÍCIO DE CUMPRIMENTO", proc="%s, %s" % (A, F))]
fi = {"eventos": [{"data": "01.06.2018", "texto": "Entrada na Unidade Penal: PRESIDIO X, Procedente: FORUM, Conforme AUT.%s, para cumprimento de pena." % A},
                  {"data": "01.06.2021", "texto": "Saída da Unidade Penal: PRESIDIO X, Destino: RUA, Motivo: Alvará de Soltura."}]}
l = linha(reg(crimes5, evs5, [soma("15/01/2023", "%s, %s" % (A, F))]), F, ficha=fi)
confere("Ficha SIAPEN: entrada em 01/06/2018 até 01/06/2021, pelo processo %s, quando esta ação penal ainda não estava em cumprimento" % A
        in l["ppe_detalhe"], "5: ficha por outra ação: %s" % l["ppe_detalhe"])

if falhas:
    print("FALHOU (prescrição - prisão por outras ações da execução):")
    for f in falhas:
        print("  " + f)
    sys.exit(1)
print("ok: prescrição - prisão por outras ações da execução (art. 116, p. único, até o evento ou somatório que inclui a ação; art. 28 sem pena; "
      "qualquer crime; somatório anterior; sem somatório a verificar; ficha)")
