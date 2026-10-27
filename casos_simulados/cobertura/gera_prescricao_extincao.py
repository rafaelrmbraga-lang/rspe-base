"""Base simulada de cobertura - área "prescricao_extincao" (capítulos 8 e 9 do relatório da 7.14.7).
Casos S8001-S8099 (processos 99080xx). Gabarito calculado à mão pela lei (CP, arts. 107, 109 a 119; LEP, art. 66, II;
Súmulas 220, 415 e 617/STJ; STF, Tema 788), sem olhar o resultado do programa.
Convenções: ano de 365 dias e mês de 30 para a pena; prazo prescricional pelo calendário, dia do começo incluído (CP, art. 10):
o último dia do prazo é a véspera do dia correspondente; dias de custódia contados com o primeiro e o último dia.
Gera cobertura/prescricao_extincao.json."""
import os
import sys
import json
from datetime import timedelta

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from base_casos import (crime, rspe, ev, prisao, interr, inc, C, AUD, P, caso, D, F, anos, mais_anos, pena_cab, amd,  # noqa: E402
                        CP, DROGAS, HOJE, GER, REG)

CASOS = []
FURTO = ("ART 155: Furto", "CAPUT: Subtrair, para si ou para outrem, coisa alheia móvel, Reclusão: 1 a 4 anos E Multa")
FURTOQ = ("ART 155: Furto", "§ 4º: Furto qualificado, Reclusão: 2 a 8 anos E Multa")
ROUBO = ("ART 157: Roubo", "CAPUT: Subtrair coisa móvel alheia, mediante grave ameaça ou violência, Reclusão: 4 a 10 anos E Multa")
TRAF = ("ART 33: Tráfico de drogas", "CAPUT: Importar, exportar, ... drogas, Reclusão: 5 a 15 anos E Multa")
LESAO = ("ART 129: Lesão corporal", "CAPUT: Ofender a integridade corporal ou a saúde de outrem, Detenção: 3 meses a 1 ano")
AMEACA = ("ART 147: Ameaça", "CAPUT: Ameaçar alguém, Detenção: 1 a 6 meses OU Multa")


def proc(k, n=1, ano=2020):
    return "%07d-00.%d.8.12.0001" % (8808000 + (k % 100) * 10 + n, ano)


def cr(k, tipo, pena, fato, n=1, ano=2020, **kw):
    a, t = tipo
    lei = kw.pop("lei", DROGAS if tipo is TRAF else CP)
    return crime(proc(k, n, ano), a, pena, fato, lei=lei, tipo=t, **kw)


def dias(a, b):
    """dias de a até b, contados os dois."""
    return (D(b) - D(a)).days + 1


def mais(d, n):
    return F(D(d) + timedelta(days=n))


def venc(termo, a, m=0):
    return F(mais_anos(D(termo), a, m))


def add(k, aba, situacao, esperado, titulo, conta, r, checks, grupo=None, **kw):
    c = caso(k, grupo or ("C-prescrição" if aba == "Prescrição" else "D-extinção"), titulo, conta, r, checks, **kw)
    c.update({"aba": aba, "situacao": situacao, "esperado": esperado})
    CASOS.append(c)
    return c


def solto(k, crimes, **kw):
    """Execução sem nenhuma custódia (mandado em aberto), regime aberto."""
    kw.setdefault("regime", "Aberto - ATIVO")
    return rspe(k, crimes, **kw)


def hdr(pena, cumprida, **kw):
    """Quadro do RSPE com pena cumprida informada (em dias)."""
    rem = max(0, pena - cumprida)
    d = {"pena_cumprida": pena_cab(min(cumprida, pena)), "pena_remanescente": pena_cab(rem) if rem else "0a0m0d"}
    d.update(kw)
    return d


# =====================================================================================================================
# PRESCRIÇÃO - faixas do art. 109 (executória, pessoa nunca presa, termo no trânsito)
# =====================================================================================================================

def faixa(k, tipo, pena, fato, sentenca, transito, prazo, venc_esp, aparente, inciso, extra_conta="", nasc="01/01/1980", transito_mp=None):
    r = solto(k, [cr(k, tipo, pena, fato, sentenca=sentenca, transito=transito, denuncia=mais(fato, 40), transito_mp=transito_mp)], nasc=nasc)
    termo = transito_mp if transito_mp and D(transito_mp) <= D("12/11/2020") else transito
    st = "aparente em %s" % venc_esp if aparente else "não prescrita (vence em %s)" % venc_esp
    conta = ("Pena %s (%d dias = %.3f anos): art. 109, %s = %s. Nunca preso; termo no trânsito %s. %s + %s, dia do começo incluído: "
             "último dia %s. Em 12/10/2026: %s.%s" % (pena_cab(pena), pena, pena / 365.0, inciso, prazo, termo, termo, prazo, venc_esp, st, extra_conta))
    ch = [P(0, "prazo_ppe", "contem", prazo)]
    if aparente:
        ch += [P(0, "ppe_status", "contem", ["aparente", venc_esp]), C("presc_cor", "eq", "vermelho")]
    else:
        ch += [P(0, "ppe_status", "nao_contem", "aparente"), P(0, "ppe_correndo_ate", "eq", venc_esp)]
    return r, conta, ch, st


k = 8001
r, conta, ch, st = faixa(k, TRAF, anos(13), "01/06/2003", "20/09/2004", "10/03/2005", "20 anos", venc("10/03/2005", 20), True, "I")
add(k, "Prescrição", "Art. 109, I: pena superior a 12 anos prescreve em 20 anos", "Executória aparente em 09/03/2025; prazo 20 anos",
    "Art. 109, I - pena de 13 anos, nunca preso", conta, r, ch)

k = 8002
r, conta, ch, st = faixa(k, TRAF, anos(10), "15/02/2006", "10/12/2007", "01/04/2008", "16 anos", venc("01/04/2008", 16), True, "II")
add(k, "Prescrição", "Art. 109, II: pena de 8 a 12 anos prescreve em 16 anos", "Executória aparente em 31/03/2024; prazo 16 anos",
    "Art. 109, II - pena de 10 anos, nunca preso", conta, r, ch)

k = 8003
r, conta, ch, st = faixa(k, ROUBO, anos(6), "10/01/2015", "20/09/2016", "15/11/2016", "12 anos", venc("15/11/2016", 12), False, "III")
add(k, "Prescrição", "Art. 109, III: pena de 4 a 8 anos prescreve em 12 anos (ainda não venceu)",
    "Executória não prescrita, vence em 14/11/2028; prazo 12 anos", "Art. 109, III - pena de 6 anos, nunca preso", conta, r, ch)

k = 8004
r, conta, ch, st = faixa(k, FURTOQ, anos(3), "05/05/2016", "10/03/2017", "20/05/2017", "8 anos", venc("20/05/2017", 8), True, "IV")
add(k, "Prescrição", "Art. 109, IV: pena de 2 a 4 anos prescreve em 8 anos", "Executória aparente em 19/05/2025; prazo 8 anos",
    "Art. 109, IV - pena de 3 anos, nunca preso", conta, r, ch)

k = 8005
r, conta, ch, st = faixa(k, FURTOQ, anos(4), "02/02/2017", "01/10/2017", "01/12/2017", "8 anos", venc("01/12/2017", 8), True, "IV",
                         " Pena de exatamente 4 anos não é 'superior a 4': inciso IV (8 anos), não III (12 anos, que venceria em 30/11/2029).")
add(k, "Prescrição", "Limite do art. 109, IV: pena de exatamente 4 anos fica no inciso IV (8 anos)",
    "Executória aparente em 30/11/2025; prazo 8 anos (não 12)", "Art. 109 - pena de exatamente 4 anos", conta, r, ch)

k = 8006
r, conta, ch, st = faixa(k, FURTOQ, anos(2, 0, 1), "01/03/2019", "10/12/2019", "10/02/2020", "8 anos", venc("10/02/2020", 8), False, "IV",
                         " 731 dias é superior a 2 anos: inciso IV (8 anos); pelo inciso V (4 anos) teria vencido em 09/02/2024.")
add(k, "Prescrição", "Limite do art. 109: pena de 2 anos e 1 dia já sobe para o inciso IV (8 anos)",
    "Executória não prescrita, vence em 09/02/2028; prazo 8 anos", "Art. 109 - pena de 2 anos e 1 dia", conta, r, ch)

k = 8007
r, conta, ch, st = faixa(k, FURTO, anos(2), "10/08/2020", "05/05/2021", "05/07/2021", "4 anos", venc("05/07/2021", 4), True, "V",
                         " Pena de exatamente 2 anos: 'de 1 a 2 anos', inciso V. Trânsito para ambas as partes no mesmo dia (após 12/11/2020).")
add(k, "Prescrição", "Art. 109, V: pena de exatamente 2 anos prescreve em 4 anos", "Executória aparente em 04/07/2025; prazo 4 anos",
    "Art. 109, V - pena de exatamente 2 anos", conta, r, ch)

k = 8008
r, conta, ch, st = faixa(k, LESAO, 330, "01/09/2022", "20/04/2023", "20/06/2023", "3 anos", venc("20/06/2023", 3), True, "VI",
                         " Fato posterior à Lei 12.234/2010: inciso VI de 3 anos (com 4 anos venceria só em 19/06/2027).")
add(k, "Prescrição", "Art. 109, VI: pena inferior a 1 ano (11 meses) prescreve em 3 anos", "Executória aparente em 19/06/2026; prazo 3 anos",
    "Art. 109, VI - pena de 11 meses (330 dias)", conta, r, ch)

k = 8009
r, conta, ch, st = faixa(k, LESAO, 240, "01/03/2009", "15/11/2010", "01/03/2011", "2 anos", venc("01/03/2011", 2), True, "VI (redação anterior)",
                         " Fato de 01/03/2009, anterior à Lei 12.234/2010 (vigência em 06/05/2010): o inciso VI tinha 2 anos; a lei nova (3 anos) não retroage (CF, art. 5º, XL).")
add(k, "Prescrição", "Art. 109, VI na redação antiga: fato anterior a 06/05/2010, pena inferior a 1 ano prescreve em 2 anos",
    "Executória aparente em 28/02/2013; prazo 2 anos", "Art. 109, VI antigo - pena de 8 meses, fato de 2009", conta, r, ch)

# ---- art. 115 ------------------------------------------------------------------------------------------------------
k = 8010
r = solto(k, [cr(k, FURTOQ, anos(2, 6), "10/02/2021", sentenca="29/08/2021", transito="28/10/2021")], nasc="15/08/2001")
v = venc("28/10/2021", 4)
add(k, "Prescrição", "Art. 115: menor de 21 anos na data do fato - prazos pela metade",
    "Executória aparente em %s; prazo 4 anos (8 anos pela metade); art. 115 aplicado" % v,
    "Art. 115 - 19 anos no fato", "Nascido em 15/08/2001; fato em 10/02/2021: 19 anos. Pena 2a6m (912 dias) -> art. 109, IV = 8 anos; "
    "metade (CP, art. 115) = 4 anos. Trânsito 28/10/2021 + 4 anos - 1 dia = %s: aparente." % v, r,
    [P(0, "art115", "eq", True), P(0, "prazo_ppe", "contem", "4 anos"), P(0, "ppe_status", "contem", ["aparente", v])])

k = 8011
r = solto(k, [cr(k, FURTOQ, anos(2, 6), "10/02/2021", sentenca="29/08/2021", transito="28/10/2021")], nasc="10/02/2000")
v = venc("28/10/2021", 8)
add(k, "Prescrição", "Art. 115: quem faz 21 anos no próprio dia do fato já não é 'menor de 21' - sem a metade",
    "Executória não prescrita, vence em %s; prazo 8 anos; art. 115 não aplicado" % v,
    "Art. 115 - 21 anos completos no dia do fato", "Nascido em 10/02/2000; fato em 10/02/2021: completa 21 anos nesse dia (já não é menor de 21). "
    "Pena 2a6m -> 8 anos, sem redução. Trânsito 28/10/2021 + 8 anos - 1 = %s: não prescrita." % v, r,
    [P(0, "art115", "eq", False), P(0, "prazo_ppe", "eq", "8 anos"), P(0, "ppe_status", "nao_contem", "aparente"), P(0, "ppe_correndo_ate", "eq", v)])

k = 8012
r = solto(k, [cr(k, FURTOQ, anos(3), "01/02/2021", sentenca="10/06/2022", transito="10/08/2022")], nasc="01/05/1952")
v = venc("10/08/2022", 4)
add(k, "Prescrição", "Art. 115: maior de 70 anos na data da sentença - prazos pela metade",
    "Executória aparente em %s; prazo 4 anos (8 pela metade); art. 115 aplicado" % v,
    "Art. 115 - 70 anos na sentença", "Nascido em 01/05/1952; sentença em 10/06/2022: 70 anos completos (68 no fato). Pena 3 anos -> 8 anos; "
    "metade = 4 anos. Trânsito 10/08/2022 + 4 anos - 1 = %s: aparente (sem a metade, venceria em 09/08/2030)." % v, r,
    [P(0, "art115", "eq", True), P(0, "prazo_ppe", "contem", "4 anos"), P(0, "ppe_status", "contem", ["aparente", v])])

# ---- reincidência ----------------------------------------------------------------------------------------------------
k = 8013
a = cr(k, FURTO, anos(1), "01/03/2014", n=1, ano=2014, sentenca="01/02/2015", transito="01/06/2015", extinto="Sim")
b = cr(k, FURTO, anos(2), "01/03/2019", n=2, ano=2019, sentenca="01/06/2022", transito="01/09/2022", rc="S", fp="20% - Reincidente", fl="1/2 - Comum Reincidente")
r = solto(k, [a, b])
v = venc("01/09/2022", 5, 4)
add(k, "Prescrição", "Reincidência reconhecida na sentença: +1/3 no prazo da executória (CP, art. 110)",
    "Linha do crime de 2019: prazo 5 anos e 4 meses (+1/3); não prescrita, vence em %s (sem o +1/3 já teria vencido em 31/08/2026)" % v,
    "Executória: reincidente, +1/3", "Condenação anterior (furto, fato 01/03/2014, trânsito 01/06/2015, extinta). Novo furto em 01/03/2019, "
    "marcado reincidente: trânsito anterior ao fato (CP, art. 63) e dentro de 5 anos (art. 64, I). Pena 2 anos -> 4 anos; +1/3 (art. 110, caput) = "
    "5 anos e 4 meses. Trânsito 01/09/2022 + 5a4m - 1 = %s: não prescrita. A condenação de 2014 está extinta (não é analisada)." % v, r,
    [P(0, "prazo_ppe", "contem", "5 anos e 4 meses"), P(0, "ppe_status", "nao_contem", "aparente"), P(0, "ppe_correndo_ate", "eq", v)])

k = 8014
a = cr(k, FURTO, anos(1), "01/05/2010", n=1, ano=2010, sentenca="01/12/2011", transito="01/03/2012", extinto="Sim")
b = cr(k, FURTO, anos(1), "01/12/2014", n=2, ano=2015, denuncia="01/02/2015", sentenca="10/03/2019", transito="10/05/2019", rc="S",
       fp="20% - Reincidente", fl="1/2 - Comum Reincidente")
r = solto(k, [a, b])
add(k, "Prescrição", "Súmula 220/STJ: a reincidência não aumenta o prazo da prescrição punitiva",
    "Linha do crime de 2014: prazo da punitiva 4 anos (sem +1/3); retroativa aparente (denúncia -> sentença)",
    "Punitiva: reincidente, sem +1/3 (Súm. 220)", "Reincidente (condenação transitada em 01/03/2012). Pena 1 ano -> 4 anos. Súmula 220/STJ: "
    "o +1/3 não incide na punitiva. Denúncia recebida 01/02/2015 + 4 anos - 1 = 31/01/2019 < sentença 10/03/2019: retroativa aparente. "
    "(Com o +1/3 indevido, 5a4m, venceria em 31/05/2020, depois da sentença.)", r,
    [P(0, "prazo_ppp", "contem", "4 anos"), P(0, "prazo_ppp", "nao_contem", "1/3"), P(0, "retro_status", "contem", "aparente"),
     C("presc_retro", "regex", "aparente")])

# ---- punitiva retroativa e intercorrente ---------------------------------------------------------------------------
k = 8015
r = solto(k, [cr(k, FURTO, anos(2), "01/02/2016", denuncia="05/04/2016", sentenca="20/06/2020", transito="20/08/2020")])
add(k, "Prescrição", "Prescrição retroativa entre o recebimento da denúncia e a sentença",
    "Punitiva retroativa aparente (denúncia -> sentença), vencida em 04/04/2020; cor vermelha",
    "Retroativa: denúncia -> sentença em 4 anos e 2 meses", "Pena 2 anos -> 4 anos (art. 109, V; art. 110, § 1º). Denúncia 05/04/2016 + 4 anos - 1 = "
    "04/04/2020 < sentença 20/06/2020: retroativa aparente.", r,
    [P(0, "retro_status", "contem", "aparente"), P(0, "retro_status", "contem", "sentença"), C("presc_retro", "regex", "aparente"), C("presc_cor", "eq", "vermelho")])

k = 8016
r = solto(k, [cr(k, FURTO, anos(2), "01/02/2016", denuncia="05/04/2016", sentenca="04/04/2020", transito="01/12/2023", transito_mp="01/12/2023")])
v = venc("01/12/2023", 4)
add(k, "Prescrição", "Retroativa: sentença publicada no último dia do prazo interrompe a tempo (não há prescrição)",
    "Punitiva não configurada; executória não prescrita (vence em %s)" % v,
    "Retroativa: sentença no último dia do prazo", "Pena 2 anos -> 4 anos. Denúncia 05/04/2016: último dia 04/04/2020 = data da sentença, que interrompe "
    "(art. 117, IV) antes de a prescrição se consumar (consuma-se no dia seguinte). Sentença -> trânsito (04/04/2020 a 01/12/2023 = 3a7m) < 4 anos. "
    "Executória: trânsito para ambas 01/12/2023 (Tema 788) + 4 anos - 1 = %s." % v, r,
    [P(0, "retro_status", "nao_contem", "aparente"), P(0, "ppe_status", "nao_contem", "aparente"), P(0, "ppe_correndo_ate", "eq", v)])

k = 8017
r = solto(k, [cr(k, FURTO, anos(1), "01/06/2011", denuncia="01/08/2011", sentenca="01/03/2012", transito_mp="12/03/2012", transito="01/06/2020")])
add(k, "Prescrição", "Prescrição intercorrente: entre a sentença e o trânsito final passou mais que o dobro do prazo",
    "Punitiva intercorrente aparente (sentença -> trânsito); cor vermelha",
    "Intercorrente: sentença 2012, trânsito 2020", "Pena 1 ano -> 4 anos. Sentença 01/03/2012; trânsito final 01/06/2020 = 8 anos e 3 meses. "
    "Mesmo que um acórdão confirmatório tenha interrompido no meio (STF, HC 176.473), um dos dois trechos passou de 4 anos: intercorrente "
    "consumada (CP, art. 110, § 1º).", r,
    [P(0, "retro_status", "contem", "aparente"), P(0, "retro_status", "regex", "tr[aâ]nsito|intercorrente"), C("presc_retro", "regex", "aparente")])

# ---- termo inicial da executória -----------------------------------------------------------------------------------
k = 8018
r = solto(k, [cr(k, FURTO, anos(1, 6), "01/01/2020", denuncia="01/02/2020", sentenca="01/08/2020", transito_mp="20/09/2020", transito="10/10/2023")])
v = venc("20/09/2020", 4)
add(k, "Prescrição", "Termo inicial da executória: trânsito para a acusação até 12/11/2020 (modulação do Tema 788)",
    "Executória aparente em %s (contada do trânsito para a acusação)" % v,
    "Executória: trânsito para a acusação em 20/09/2020", "Pena 1a6m -> 4 anos. Trânsito para a acusação 20/09/2020, antes de 12/11/2020: termo é ele "
    "(CP, art. 112, I; STF, ARE 848.107, modulação). 20/09/2020 + 4 anos - 1 = %s: aparente. Contado do trânsito final (10/10/2023), venceria em "
    "09/10/2027. Intercorrente: 01/08/2020 a 10/10/2023 = 3a2m < 4 anos." % v, r,
    [P(0, "ppe_status", "contem", ["aparente", v])])

k = 8019
r = solto(k, [cr(k, FURTO, anos(1, 6), "01/01/2020", denuncia="01/02/2020", sentenca="01/11/2020", transito_mp="10/12/2020", transito="01/10/2023")])
v = venc("01/10/2023", 4)
add(k, "Prescrição", "Tema 788/STF: trânsito para a acusação depois de 12/11/2020 - termo é o trânsito para ambas as partes",
    "Executória não prescrita, vence em %s" % v,
    "Executória: Tema 788, trânsito para a acusação em 10/12/2020", "Trânsito para a acusação 10/12/2020 (depois de 12/11/2020): termo no trânsito "
    "para ambas, 01/10/2023 (Tema 788). 01/10/2023 + 4 anos - 1 = %s: não prescrita (pelo trânsito da acusação venceria em 09/12/2024)." % v, r,
    [P(0, "ppe_status", "nao_contem", "aparente"), P(0, "ppe_correndo_ate", "eq", v)])

k = 8020
r = solto(k, [cr(k, FURTO, anos(1), "01/04/2018", denuncia="01/05/2018", sentenca="10/01/2019", transito="01/03/2019", transito_mp="")])
v = venc("01/03/2019", 4)
add(k, "Prescrição", "Só o trânsito final consta (antes de 12/11/2020): o da acusação é anterior, e a prescrição já se consumou de qualquer modo",
    "Executória aparente, vencida no máximo em %s" % v,
    "Executória: sem trânsito para a acusação, trânsito final 2019", "Pena 1 ano -> 4 anos. Sem a data do trânsito para a acusação; ele é igual "
    "ou anterior ao trânsito final 01/03/2019 (antes de 12/11/2020). Contando do trânsito final (a hipótese menos favorável), o prazo terminou "
    "em %s - aparente em qualquer hipótese." % v, r,
    [P(0, "ppe_status", "contem", "aparente"), C("presc_cor", "eq", "vermelho")])

# ---- interrupções (art. 117, V) -------------------------------------------------------------------------------------
k = 8021
c = cr(k, FURTOQ, anos(3), "01/03/2016", sentenca="01/02/2017", transito="01/04/2017")
r = rspe(k, [c], [prisao("15/03/2025", c["processo_criminal"], "PRISÃO DEFINITIVA")],
         [inc(REG, "Fechado - Regime Inicial", "15/03/2025", "15/03/2025")], ini="15/03/2025")
add(k, "Prescrição", "Início do cumprimento antes do fim do prazo interrompe a executória (art. 117, V)",
    "Executória: não corre (em cumprimento desde 15/03/2025); nada aparente",
    "Interrupção: prisão 16 dias antes do vencimento", "Pena 3 anos -> 8 anos. Trânsito 01/04/2017 + 8 anos - 1 = 31/03/2025. Prisão definitiva em "
    "15/03/2025, antes desse dia: interrompe (art. 117, V) e, preso, o prazo não corre (art. 116, p. único). Não prescrita.", r,
    [P(0, "ppe_status", "nao_contem", "aparente"), C("presc_cor", "nao_contem", "vermelho")])

k = 8022
c = cr(k, FURTOQ, anos(3), "01/03/2016", sentenca="01/02/2017", transito="01/04/2017")
r = rspe(k, [c], [prisao("01/04/2025", c["processo_criminal"], "PRISÃO DEFINITIVA")],
         [inc(REG, "Fechado - Regime Inicial", "01/04/2025", "01/04/2025")], ini="01/04/2025")
add(k, "Prescrição", "Prisão um dia depois do fim do prazo: a executória já se consumara (prisão indevida)",
    "Executória aparente em 31/03/2025; cor vermelha",
    "Interrupção tardia: prisão no dia seguinte ao vencimento", "Pena 3 anos -> 8 anos. 01/04/2017 + 8 anos - 1 = 31/03/2025 (último dia). A prisão de "
    "01/04/2025 veio no dia em que a prescrição já estava consumada: não interrompe (CP, art. 117, V, pressupõe prazo em curso). Aparente.", r,
    [P(0, "ppe_status", "contem", ["aparente", "31/03/2025"]), C("presc_cor", "eq", "vermelho")])

# ---- fuga e saldo (art. 113) ----------------------------------------------------------------------------------------
k = 8023
c = cr(k, FURTOQ, anos(3), "01/03/2016", sentenca="01/11/2016", transito="10/01/2017")
cump = dias("20/01/2017", "10/04/2019")
saldo = anos(3) - cump
v = venc("10/04/2019", 3)
r = rspe(k, [c], [prisao("20/01/2017", c["processo_criminal"], "PRISÃO DEFINITIVA"), interr("10/04/2019", "FUGA")],
         [inc(REG, "Fechado - Regime Inicial", "20/01/2017", "20/01/2017")], ini="20/01/2017", interrompidos=dias("20/01/2017", "05/10/2026") - cump,
         situacao_cumprimento="PENA INTERROMPIDA (sem evento de reinício)", **hdr(anos(3), cump))
add(k, "Prescrição", "Fuga em aberto: prazo pelo saldo da pena (art. 113), saldo inferior a 1 ano",
    "Executória aparente em %s; prazo 3 anos pelo saldo (%d dias)" % (v, saldo),
    "Fuga: saldo de %d dias -> 3 anos" % saldo, "Pena 3 anos (1.095 dias). Preso 20/01/2017 a 10/04/2019 = %d dias (os dois contados). Saldo = %d dias "
    "(< 1 ano) -> art. 109, VI = 3 anos (art. 113). Prazo da fuga: 10/04/2019 + 3 anos - 1 = %s: aparente (pela pena inteira, 8 anos, venceria em 2027)."
    % (cump, saldo, v), r,
    [P(0, "prazo_ppe", "contem", "3 anos"), P(0, "ppe_status", "contem", ["aparente", v])])

k = 8024
c = cr(k, FURTOQ, anos(2, 6), "01/06/2015", sentenca="01/12/2015", transito="15/02/2016")
c1, c2 = dias("01/03/2016", "28/02/2017"), dias("01/02/2021", "30/04/2021")
s1, s2 = anos(2, 6) - c1, anos(2, 6) - c1 - c2
v1, v2 = venc("28/02/2017", 4), venc("30/04/2021", 4)
interr_tot = dias("01/03/2016", "05/10/2026") - c1 - c2
r = rspe(k, [c], [prisao("01/03/2016", c["processo_criminal"], "PRISÃO DEFINITIVA"), interr("28/02/2017", "FUGA"),
                  prisao("01/02/2021", c["processo_criminal"], "RECAPTURA/REINÍCIO DE CUMPRIMENTO"), interr("30/04/2021", "FUGA")],
         [inc(REG, "Fechado - Regime Inicial", "01/03/2016", "01/03/2016")], ini="01/03/2016", interrompidos=interr_tot,
         situacao_cumprimento="PENA INTERROMPIDA (sem evento de reinício)", **hdr(anos(2, 6), c1 + c2))
add(k, "Prescrição", "Recaptura antes do vencimento interrompe; a nova fuga abre novo prazo pelo novo saldo",
    "Executória aparente em %s (contada da 2ª fuga), não em %s" % (v2, v1),
    "Fuga, recaptura a tempo e nova fuga", "Pena 2a6m (912 d). 1º período 01/03/2016-28/02/2017 = %d d; saldo %d (1 a 2 anos) -> 4 anos: venceria em %s. "
    "Recaptura em 01/02/2021, antes: interrompe (art. 117, V). 2º período 01/02/2021-30/04/2021 = %d d; saldo %d -> 4 anos; 2ª fuga 30/04/2021 + 4 anos - 1 "
    "= %s: aparente." % (c1, s1, v1, c2, s2, v2), r,
    [P(0, "ppe_status", "contem", ["aparente", v2]), P(0, "prazo_ppe", "contem", "4 anos")])

k = 8025
c = cr(k, ROUBO, anos(5), "01/05/2014", sentenca="01/01/2015", transito="01/03/2015")
cl = dias("10/03/2015", "10/06/2018")
saldo = anos(5) - cl
v = venc("10/09/2019", 4)
r = rspe(k, [c], [prisao("10/03/2015", c["processo_criminal"], "PRISÃO DEFINITIVA"), interr("10/06/2018", "LIVRAMENTO CONDICIONAL")],
         [inc(REG, "Fechado - Regime Inicial", "10/03/2015", "10/03/2015"),
          inc("LIVRAMENTO CONDICIONAL", "10/06/2018", "01/06/2018", "10/06/2018"),
          inc("REVOGAÇÃO DE LIVRAMENTO CONDICIONAL", "", "10/09/2019", "10/09/2019", procs=c["processo_criminal"])],
         ini="10/03/2015", interrompidos=dias("10/03/2015", "05/10/2026") - cl, regime="Fechado - ATIVO",
         situacao_cumprimento="PENA INTERROMPIDA (sem evento de reinício)", **hdr(anos(5), cl))
add(k, "Prescrição", "Revogação do livramento: prazo pelo saldo (art. 113), sem descontar o tempo solto no período de prova (art. 88)",
    "Executória aparente em %s; prazo 4 anos pelo saldo de %d dias" % (v, saldo),
    "Revogação do livramento, sem recaptura", "Pena 5 anos (1.825 d). Preso 10/03/2015 a 10/06/2018 = %d d; livramento de 10/06/2018 revogado em 10/09/2019 "
    "(descumprimento, não crime anterior): o tempo solto não conta (CP, art. 88). Saldo %d d (1 a 2 anos) -> 4 anos (art. 113), contado da revogação: "
    "10/09/2019 + 4 anos - 1 = %s: aparente. (Se o período de prova contasse, saldo ~180 d -> 3 anos, venceria em 09/09/2022.)" % (cl, saldo, v), r,
    [P(0, "ppe_status", "contem", ["aparente", v]), P(0, "prazo_ppe", "contem", "4 anos")])

k = 8026
c = cr(k, FURTO, anos(1), "31/01/2019", sentenca="10/05/2019", transito="01/07/2019")
pv = dias("01/02/2019", "30/04/2019")
cu = dias("01/08/2019", "10/05/2020")
r = rspe(k, [c], [prisao("01/02/2019", c["processo_criminal"]), interr("30/04/2019", "LIBERDADE PROVISÓRIA"),
                  prisao("01/08/2019", c["processo_criminal"], "PRISÃO DEFINITIVA"), interr("10/05/2020", "FUGA")],
         [inc(REG, "Fechado - Regime Inicial", "01/08/2019", "01/08/2019")], ini="01/08/2019", regime="Fechado - ATIVO",
         situacao_cumprimento="PENA INTERROMPIDA (sem evento de reinício)", total_interrupcoes=pena_cab(dias("11/05/2020", "05/10/2026")), term="",
         **hdr(anos(1), pv + cu))
fim = mais("01/08/2019", anos(1) - pv - 1)
add(k, "Extinção", "Pena integralmente cumprida antes da fuga (detração + cumprimento = pena): saldo zero",
    "Extinção cabível (pena cumprida); na Prescrição nada a prescrever (sem 'aparente')",
    "Saldo zero na fuga: pena cumprida antes de fugir", "Pena 1 ano (365 d). Flagrante 01/02/2019 a 30/04/2019 = %d d (detração, CP, art. 42). "
    "Cumprimento desde 01/08/2019: faltavam %d d, esgotados em %s. Fuga lançada em 10/05/2020 (%d dias de cumprimento): saldo 365 - %d - %d < 0 = zero. "
    "A pena já estava cumprida: extinção (LEP, art. 66, II); não há saldo a prescrever (art. 113)." % (pv, anos(1) - pv, fim, cu, pv, cu), r,
    [C("ext_sit", "eq", "Extinção cabível"), C("ext_cor", "eq", "vermelho"), P(0, "ppe_status", "nao_contem", "aparente")])

k = 8027
c = cr(k, FURTO, anos(1), "31/01/2019", sentenca="10/05/2019", transito="01/07/2019")
r = rspe(k, [c], [prisao("01/02/2019", c["processo_criminal"]), interr("30/04/2019", "LIBERDADE PROVISÓRIA"),
                  prisao("01/08/2019", c["processo_criminal"], "PRISÃO DEFINITIVA"), interr("10/05/2020", "FUGA")],
         [inc(REG, "Fechado - Regime Inicial", "01/08/2019", "01/08/2019")], ini="01/08/2019", regime="Fechado - ATIVO",
         situacao_cumprimento="PENA INTERROMPIDA (sem evento de reinício)", total_interrupcoes=pena_cab(dias("11/05/2020", "05/10/2026")), term="",
         **hdr(anos(1), cu))
add(k, "Prescrição", "Saldo zero na fuga quando o SEEU não lançou a detração (remanescente impresso > 0)",
    "Prescrição: nada a prescrever pelo saldo (sem 'aparente'); Extinção: hipótese de pena cumprida na fuga (a verificar ou cabível)",
    "Saldo zero na fuga com detração não lançada no SEEU", "Mesmos fatos do S8026, mas o quadro do SEEU traz só o cumprimento (%d d) e remanescente "
    "%d d (sem a detração de %d d do flagrante). Pela lei a detração é obrigatória (CP, art. 42): saldo zero, pena cumprida em %s, antes da fuga. "
    "O caminho correto é a extinção pelo cumprimento (LEP, art. 66, II), não a prescrição pelo remanescente do SEEU (que daria 3 anos, 09/05/2023)."
    % (cu, anos(1) - cu, pv, fim), r,
    [P(0, "ppe_status", "nao_contem", "aparente"), C("ext_sit", "regex", "Extinção (cabível|a verificar)"), C("ext_hipoteses", "regex", "fuga|cumprid")])

# ---- art. 366 do CPP -------------------------------------------------------------------------------------------------
k = 8028
c = cr(k, FURTO, anos(1), "01/03/2012", denuncia="01/04/2012", sentenca="01/12/2016", transito="01/02/2017")
sus = dias("01/08/2012", "31/07/2014")
v0 = venc("01/04/2012", 4)
vs = mais(v0, sus)
r = solto(k, [c])
CH8028 = "%s|art. 155 CP|1" % c["processo_criminal"]
add(k, "Prescrição", "Suspensão do art. 366 do CPP com início e fim informados: os dias suspensos se somam ao prazo da punitiva",
    "Punitiva não configurada: denúncia -> sentença com prazo de 4 anos + %d dias suspensos, vence em %s (depois da sentença de 01/12/2016)" % (sus, vs),
    "Art. 366 do CPP com data de fim", "Pena 1 ano -> 4 anos. Denúncia 01/04/2012 + 4 anos - 1 = %s. Processo suspenso (CPP, art. 366) de 01/08/2012 a "
    "31/07/2014 = %d dias (teto: prazo da pena máxima de 4 anos = 8 anos, Súmula 415/STJ, não alcançado). Vencimento + %d dias = %s > sentença 01/12/2016: "
    "não configurada. Sem a suspensão, seria aparente. (Executória: trânsito 01/02/2017 + 4 anos venceu em 31/01/2021 - fora do foco.)" % (v0, sus, sus, vs), r,
    [P(0, "retro_status", "nao_contem", "aparente")],
    acoes=[{"metodo": "presc_ajuste", "args": [r["processo_execucao"], CH8028, {"valores": {"susp366_ini": "01/08/2012", "susp366_fim": "31/07/2014"}}]}])

k = 8029
c = cr(k, AMEACA, 90, "01/03/2012", denuncia="01/05/2012", sentenca="01/08/2019", transito="01/10/2019")
v0 = venc("01/05/2012", 3)
teto = dias("01/08/2012", venc("01/08/2012", 3))
vt = mais(v0, teto)
r = solto(k, [c])
CH8029 = "%s|art. 147 CP|1" % c["processo_criminal"]
add(k, "Prescrição", "Suspensão do art. 366 sem data de fim: limitada ao prazo da pena máxima (Súmula 415/STJ); prescrição mesmo com a suspensão máxima",
    "Punitiva aparente (denúncia -> sentença): mesmo somando a suspensão máxima de 3 anos, o prazo venceu em %s, antes da sentença" % vt,
    "Art. 366 do CPP sem data de fim (teto da Súmula 415)", "Ameaça (detenção de 1 a 6 meses ou multa), pena 3 meses -> art. 109, VI = 3 anos. "
    "Pena máxima 6 meses -> 3 anos: teto da suspensão (Súmula 415/STJ). Suspenso desde 01/08/2012, fim não informado; no máximo até %s (%d dias). "
    "Denúncia 01/05/2012 + 3 anos - 1 = %s + %d = %s < sentença 01/08/2019: aparente qualquer que seja o fim da suspensão."
    % (venc("01/08/2012", 3), teto, v0, teto, vt), r,
    [P(0, "retro_status", "contem", "aparente")],
    acoes=[{"metodo": "presc_ajuste", "args": [r["processo_execucao"], CH8029, {"valores": {"susp366_ini": "01/08/2012"}}]}])

# ---- multa -----------------------------------------------------------------------------------------------------------
k = 8030
r = solto(k, [cr(k, FURTO, anos(1, 6), "01/07/2021", sentenca="01/03/2022", transito="01/05/2022")])
v = venc("01/05/2022", 4)
add(k, "Prescrição", "Multa cumulada com a pena privativa: prescreve no mesmo prazo da privativa (CP, art. 114, II)",
    "Executória da privativa aparente em %s (4 anos); a memória registra que a multa cumulada segue o mesmo prazo" % v,
    "Multa cumulada - mesmo prazo da privativa", "Furto (reclusão e multa), pena 1a6m -> 4 anos. Art. 114, II: a multa cumulativamente aplicada "
    "prescreve no mesmo prazo da privativa. 01/05/2022 + 4 anos - 1 = %s: aparente." % v, r,
    [P(0, "ppe_status", "contem", ["aparente", v]), P(0, "ppe_detalhe", "regex", "multa")])

k = 8031
c = cr(k, AMEACA, 0, "01/02/2021", sentenca="01/12/2021", transito="01/03/2022", pena_total_processo="0a0m0d - MULTA: 10 DIAS-MULTA")
r = solto(k, [c], pena=0)
v = venc("01/03/2022", 2)
add(k, "Prescrição", "Multa como única pena aplicada: prescreve em 2 anos (CP, art. 114, I)",
    "Executória aparente em %s (prazo de 2 anos do art. 114, I)" % v,
    "Multa isolada - 2 anos", "Ameaça (detenção OU multa); aplicada só a multa (10 dias-multa). CP, art. 114, I: a multa, quando é a única aplicada, "
    "prescreve em 2 anos. Trânsito 01/03/2022 + 2 anos - 1 = %s: aparente." % v, r,
    [P(0, "prazo_ppe", "contem", "2 anos"), P(0, "ppe_status", "contem", "aparente")])

# ---- concurso (art. 119) ---------------------------------------------------------------------------------------------
k = 8032
pc = proc(k, 1, 2020)
a = crime(pc, FURTOQ[0], anos(2, 6), "01/03/2020", tipo=FURTOQ[1], sentenca="01/06/2021", transito="01/09/2021", pena_total_processo="3a6m0d - PENA ORIGINÁRIA")
b = crime(pc, AMEACA[0], anos(1), "01/03/2020", tipo="§ 1º: tipo simulado, Reclusão: 1 a 4 anos", sentenca="01/06/2021", transito="01/09/2021",
          pena_total_processo="3a6m0d - PENA ORIGINÁRIA")
b["artigo"] = "ART 180: Receptação"
b["tipo_penal"] = "CAPUT: Adquirir, receber ... coisa que sabe ser produto de crime, Reclusão: 1 a 4 anos E Multa"
r = solto(k, [a, b])
va, vb = venc("01/09/2021", 8), venc("01/09/2021", 4)
add(k, "Prescrição", "Concurso de crimes na mesma ação: cada pena prescreve isoladamente (CP, art. 119), não pela soma",
    "Furto qualificado (2a6m): não prescrito, vence em %s; receptação (1 ano): aparente em %s" % (va, vb),
    "Art. 119 - dois crimes, prazos separados", "Mesma ação: furto qualificado 2a6m (8 anos) e receptação 1 ano (4 anos); soma 3a6m daria 8 anos para "
    "tudo, mas o art. 119 manda olhar cada pena. Trânsito 01/09/2021: furto vence %s; receptação venceu %s - aparente." % (va, vb), r,
    [P(0, "prazo_ppe", "eq", "8 anos"), P(0, "ppe_status", "nao_contem", "aparente"), P(1, "prazo_ppe", "contem", "4 anos"),
     P(1, "ppe_status", "contem", ["aparente", vb]), C("presc_cor", "eq", "vermelho")])

# ---- prescrição iminente ---------------------------------------------------------------------------------------------
k = 8033
r = solto(k, [cr(k, FURTO, anos(1), "01/03/2022", sentenca="20/11/2022", transito="15/01/2023")])
v = venc("15/01/2023", 4)
add(k, "Prescrição", "Executória iminente (vence em menos de 180 dias)",
    "Executória em %s (faltam 94 dias): 'Iminente', amarelo. ATENÇÃO: muda com o tempo - a partir de 15/01/2027 passa a aparente (vermelho)" % v,
    "Iminente: vence em 94 dias", "Pena 1 ano -> 4 anos. Trânsito para ambas 15/01/2023 + 4 anos - 1 = %s; de 12/10/2026 até lá: 94 dias (< 180)." % v, r,
    [P(0, "ppe_previsao", "eq", v), P(0, "ppe_status", "nao_contem", "aparente"), C("presc_ppe", "eq", "Iminente"), C("presc_cor", "eq", "amarelo")])

k = 8034
r = solto(k, [cr(k, FURTO, anos(1, 3), "01/06/2022", sentenca="10/02/2023", transito="10/04/2023")])
v = venc("10/04/2023", 4)
add(k, "Prescrição", "Executória iminente no limite (179 dias)",
    "Executória em %s (faltam 179 dias): 'Iminente', amarelo. ATENÇÃO: muda com o tempo - aparente a partir de 10/04/2027" % v,
    "Iminente: vence em 179 dias", "Pena 1a3m -> 4 anos. 10/04/2023 + 4 anos - 1 = %s: 179 dias depois de 12/10/2026 (dentro de 180)." % v, r,
    [P(0, "ppe_previsao", "eq", v), C("presc_ppe", "eq", "Iminente"), C("presc_cor", "eq", "amarelo")])

# =====================================================================================================================
# EXTINÇÃO
# =====================================================================================================================
k = 8040
c = cr(k, FURTOQ, anos(2), "01/01/2024", sentenca="10/06/2024", transito="20/08/2024")
r = rspe(k, [c], [prisao("01/09/2024", c["processo_criminal"], "PRISÃO DEFINITIVA")],
         [inc(REG, "Fechado - Regime Inicial", "01/09/2024", "01/09/2024")], ini="01/09/2024")
add(k, "Extinção", "Pena integralmente cumprida (pena cumprida igual à pena total)",
    "Extinção cabível, vermelho; hipótese de pena integralmente cumprida; término 31/08/2026 já alcançado",
    "Pena cumprida - 2 anos desde 01/09/2024", "Pena 2 anos (730 d). Preso desde 01/09/2024: 01/09/2024 + 730 - 1 = 31/08/2026 (último dia). "
    "Em 05/10/2026 (RSPE) cumprida 2a0m0d = pena total: extinção pelo cumprimento (LEP, art. 66, II).", r,
    [C("ext_sit", "eq", "Extinção cabível"), C("ext_cor", "eq", "vermelho"), C("ext_hipoteses", "regex", "integralmente cumprida")])

k = 8041
c = cr(k, FURTO, anos(1, 6), "01/01/2025", sentenca="10/04/2025", transito="25/05/2025")
term = mais("01/06/2025", anos(1, 6) - 60 - 1)
r = rspe(k, [c], [prisao("01/06/2025", c["processo_criminal"], "PRISÃO DEFINITIVA")],
         [inc(REG, "Semiaberto - Regime Inicial", "01/06/2025", "01/06/2025"), inc("REMIÇÃO", "60 Dia(s) Remido(s)", "10/03/2026", "10/03/2026")],
         ini="01/06/2025", remidos=60, regime="Semiaberto - ATIVO")
add(k, "Extinção", "Pena cumprida com ajuda da remição",
    "Extinção cabível, vermelho (término %s já alcançado; pena cumprida)" % term,
    "Pena cumprida com 60 dias remidos", "Pena 1a6m (545 d). Preso desde 01/06/2025, 60 dias remidos (LEP, art. 128: tempo cumprido). "
    "Término: 01/06/2025 + 545 - 60 - 1 = %s < 12/10/2026: extinção pelo cumprimento." % term, r,
    [C("ext_sit", "eq", "Extinção cabível"), C("ext_cor", "eq", "vermelho")])

k = 8042
c = cr(k, FURTOQ, anos(3), "01/06/2021", sentenca="01/12/2021", transito="20/02/2022")
pres = dias("01/03/2022", "31/08/2023")
fimpp = mais("01/09/2023", anos(3) - pres - 1)
r = rspe(k, [c], [prisao("01/03/2022", c["processo_criminal"], "PRISÃO DEFINITIVA"), interr("01/09/2023", "LIVRAMENTO CONDICIONAL")],
         [inc(REG, "Fechado - Regime Inicial", "01/03/2022", "01/03/2022"), inc("LIVRAMENTO CONDICIONAL", "01/09/2023", "25/08/2023", "01/09/2023")],
         ini="01/03/2022", regime="Livramento Condicional - ATIVO", term=fimpp, livramento_obs_seeu="(Em livramento condicional deferido em 01/09/2023)",
         **hdr(anos(3), anos(3)))
add(k, "Extinção", "Livramento sem revogação nem suspensão, período de prova já encerrado (CP, art. 90; Súmula 617/STJ)",
    "Extinção cabível, vermelho; hipótese de livramento com período de prova expirado sem revogação",
    "Livramento: período de prova terminado sem revogação", "Pena 3 anos (1.095 d). Preso 01/03/2022 a 31/08/2023 = %d d; livramento em 01/09/2023; "
    "restavam %d d: período de prova até %s. Nenhuma suspensão ou revogação até essa data: extinção (CP, art. 90; LEP, art. 146; Súm. 617/STJ)."
    % (pres, anos(3) - pres, fimpp), r,
    [C("ext_sit", "eq", "Extinção cabível"), C("ext_cor", "eq", "vermelho"), C("ext_hipoteses", "regex", "livramento")])

k = 8043
c = cr(k, ROUBO, anos(4), "01/06/2019", sentenca="10/02/2020", transito="20/03/2020")
pres = dias("01/04/2020", "31/03/2022")
fimpp = mais("01/04/2022", anos(4) - pres - 1)
cum_h = pres + dias("20/08/2025", "05/10/2026")
r = rspe(k, [c], [prisao("01/04/2020", c["processo_criminal"], "PRISÃO DEFINITIVA"), interr("01/04/2022", "LIVRAMENTO CONDICIONAL"),
                  prisao("20/08/2025", c["processo_criminal"], "RECAPTURA/REINÍCIO DE CUMPRIMENTO")],
         [inc(REG, "Fechado - Regime Inicial", "01/04/2020", "01/04/2020"), inc("LIVRAMENTO CONDICIONAL", "01/04/2022", "25/03/2022", "01/04/2022"),
          inc("REVOGAÇÃO DE LIVRAMENTO CONDICIONAL", "", "15/08/2024", "15/08/2024", procs=c["processo_criminal"]),
          inc(REG, "Fechado - Regressão", "15/08/2024", "15/08/2024")],
         ini="01/04/2020", term=mais("20/08/2025", anos(4) - pres - 1), db="20/08/2025", **hdr(anos(4), cum_h))
add(k, "Extinção", "Súmula 617/STJ: revogação do livramento decidida depois do fim do período de prova não impede a extinção",
    "Extinção cabível, vermelho; hipótese cita a Súmula 617 (período de prova terminou em %s; revogação só em 15/08/2024)" % fimpp,
    "Livramento revogado tarde demais (Súm. 617)", "Pena 4 anos (1.460 d). Preso 01/04/2020 a 31/03/2022 = %d d; livramento em 01/04/2022; restavam %d d: "
    "período de prova até %s. Revogação (sem suspensão anterior) só em 15/08/2024, depois do fim: a pena estava extinta (CP, art. 90; Súm. 617/STJ). "
    "A recaptura de 20/08/2025 e o novo término do SEEU não valem." % (pres, anos(4) - pres, fimpp), r,
    [C("ext_sit", "eq", "Extinção cabível"), C("ext_hipoteses", "contem", "617")])

k = 8044
c = cr(k, FURTO, anos(1, 6), "09/01/2020", sentenca="01/06/2021", transito="01/12/2021")
dt = dias("10/01/2020", "20/08/2021")
r = rspe(k, [c], [prisao("10/01/2020", c["processo_criminal"]), interr("20/08/2021", "LIBERDADE PROVISÓRIA")], regime="Aberto - ATIVO")
add(k, "Extinção", "Prisão provisória (detração) maior que a pena, processo único: extinção pelo cumprimento",
    "Extinção cabível, vermelho; hipótese de detração que cobre a pena",
    "Detração exclusiva cobre a pena", "Pena 1a6m (545 d). Flagrante 10/01/2020 a liberdade provisória 20/08/2021 = %d d (os dois dias contados) >= 545. "
    "Único processo e o fato (09/01/2020) é anterior à prisão: detração (CP, art. 42) cobre a pena - extinção pelo cumprimento (LEP, art. 66, II)." % dt, r,
    [C("ext_sit", "eq", "Extinção cabível"), C("ext_hipoteses", "regex", "detra|supera a pena|custódia")])

k = 8045
ca = cr(k, FURTO, anos(1), "09/01/2020", n=1, sentenca="01/06/2021", transito="01/12/2021")
cb = cr(k, FURTO, anos(1), "01/06/2019", n=2, ano=2019, sentenca="01/03/2020", transito="01/05/2020")
dt = dias("10/01/2020", "20/08/2021")
r = rspe(k, [ca, cb], [prisao("10/01/2020", ca["processo_criminal"]), interr("20/08/2021", "LIBERDADE PROVISÓRIA")], regime="Aberto - ATIVO")
add(k, "Extinção", "Detração que cobre a pena de um processo, mas outra condenação tem fato anterior à prisão: a mesma custódia pode servir às duas",
    "Extinção a verificar, amarelo (detração não exclusiva); não 'Extinção cabível'",
    "Detração não exclusiva - a verificar", "Prisão de 10/01/2020 a 20/08/2021 = %d d, lançada na ação A (pena 1 ano). A ação B (pena 1 ano) tem fato de "
    "01/06/2019, anterior à prisão, e transitou em 01/05/2020, durante ela: o tempo pode ser imputado a B (CP, art. 42; LEP, art. 111). Pena unificada "
    "730 d > %d: não se pode afirmar a extinção de A isoladamente - a verificar." % (dt, dt), r,
    [C("ext_sit", "eq", "Extinção a verificar"), C("ext_cor", "eq", "amarelo")])

k = 8046
c = cr(k, FURTOQ, anos(2), "01/03/2019", sentenca="01/10/2019", transito="01/12/2019")
pri = mais("01/02/2024", -429)
rem = 300
alc = mais("01/02/2024", rem - 1)
r = rspe(k, [c], [prisao(pri, c["processo_criminal"], "PRISÃO DEFINITIVA"), interr("01/02/2024", "INTERRUPÇÃO POR PRISÃO EM OUTRO PROCESSO")],
         [inc(REG, "Fechado - Regime Inicial", pri, pri)], ini=pri, situacao_cumprimento="PENA SUSPENSA", term="",
         total_interrupcoes=pena_cab(dias("02/02/2024", "05/10/2026")), **hdr(anos(2), 430))
add(k, "Extinção", "Execução suspensa por prisão em outro processo: o tempo preso já alcançaria a pena restante",
    "Extinção a verificar, amarelo (se o tempo for imputado a esta execução, a remanescente de 300 dias se esgotou em %s)" % alc,
    "Preso em outro processo desde 01/02/2024", "Pena 2 anos; cumpridos 430 d até 01/02/2024, remanescente 300 d. Desde então preso por outro processo "
    "(execução suspensa). O fato desta condenação (2019) é anterior a essa prisão: a detração é possível (CP, art. 42; LEP, art. 111). "
    "01/02/2024 + 300 - 1 = %s, já passado: hipótese de extinção a verificar." % alc, r,
    [C("ext_sit", "eq", "Extinção a verificar"), C("ext_hipoteses", "regex", "outro processo")])

k = 8047
c = cr(k, FURTOQ, anos(2, 6), "01/03/2021", sentenca="01/03/2022", transito="01/06/2022")
po = "0001234-00.2022.8.12.0099"
dp = dias("01/09/2022", "31/03/2025")
r = solto(k, [c], eventos=[prisao("01/09/2022", po, "PRISÃO PREVENTIVA"), interr("31/03/2025", "ALVARA DE SOLTURA - ABSOLVICAO", po)])
add(k, "Extinção", "Prisão preventiva em outro processo (absolvido), posterior ao fato desta condenação, maior que a pena: detração possível",
    "Extinção a verificar, amarelo (detração da prisão no outro processo, %d dias, alcança a pena de 912 dias); Auditoria aponta a detração" % dp,
    "Detração por prisão em outro processo", "Pena 2a6m (912 d), nunca iniciada. Preso preventivamente no processo %s de 01/09/2022 a 31/03/2025 = %d d, "
    "absolvido. O fato desta condenação (01/03/2021) é anterior à prisão: detração admitida (CP, art. 42; STJ). %d >= 912: se imputada, a pena está "
    "cumprida - a verificar." % (po, dp, dp), r,
    [C("ext_sit", "eq", "Extinção a verificar"), C("ext_hipoteses", "regex", "outro processo"), AUD("detracao-prisao-em-outro-processo")])

k = 8048
ca = cr(k, FURTO, anos(1), "01/05/2019", n=1, ano=2019, sentenca="01/12/2019", transito="01/02/2020")
cb = cr(k, ROUBO, anos(5), "01/08/2020", n=2, ano=2020, sentenca="01/03/2021", transito="01/05/2021")
term = mais("01/01/2023", anos(6) - 1)
r = rspe(k, [ca, cb], [prisao("01/01/2023", "%s, %s" % (ca["processo_criminal"], cb["processo_criminal"]), "PRISÃO DEFINITIVA")],
         [inc(REG, "Fechado - Regime Inicial", "01/01/2023", "01/01/2023"),
          inc("SOMATÓRIO DAS PENAS", "", "10/01/2023", "10/01/2023", procs="%s, %s" % (ca["processo_criminal"], cb["processo_criminal"]))],
         ini="01/01/2023")
add(k, "Extinção", "Execução unificada: o tempo cumprido já passa da menor pena, mas não se extingue pena isolada",
    "Em cumprimento (término %s); sem hipótese de extinção; Prescrição sem nada aparente" % term,
    "Unificada: 1 ano + 5 anos, 3 anos e 9 meses cumpridos", "Penas de 1 ano e 5 anos somadas (LEP, art. 111), presos desde 01/01/2023: cumpridos ~1.374 d "
    "> 365 d da pena menor, mas o tempo é da pena unificada (6 anos), término %s. Não cabe extinção da pena de 1 ano isolada (escolha de política "
    "declarada: execução unificada, sem extinção de pena isolada)." % term, r,
    [C("ext_sit", "eq", "Em cumprimento"), C("ext_hipoteses", "nao_contem", "xtin"), C("presc_cor", "nao_contem", "vermelho")])

k = 8049
c = cr(k, ROUBO, anos(50), "01/06/2015", sentenca="01/01/2016", transito="01/03/2016", regime="Fechado")
lim = venc("01/03/2016", 30)
r = rspe(k, [c], [prisao("01/03/2016", c["processo_criminal"], "PRISÃO DEFINITIVA")],
         [inc(REG, "Fechado - Regime Inicial", "01/03/2016", "01/03/2016")], ini="01/03/2016")
add(k, "Extinção", "Limite de 30 anos do art. 75 (fatos anteriores a 23/01/2020): a aba Extinção mantém o término do SEEU com ressalva; a Auditoria alerta",
    "Extinção: término do SEEU (%s) mantido, situação 'Em cumprimento · art. 75 a verificar' (amarelo); Auditoria: alerta do art. 75 com máximo em %s; "
    "coluna Término geral %s*" % (r["termino_previsao_seeu"], lim, lim),
    "Art. 75 - 50 anos, limite de 30", "Pena 50 anos, fato 2015 (antes da Lei 13.964/2019): limite de 30 anos (CP, art. 75, redação anterior). Preso desde "
    "01/03/2016 sem interrupção: 01/03/2016 + 30 anos - 1 = %s. O SEEU imprime término %s (50 anos)." % (lim, r["termino_previsao_seeu"]), r,
    [C("ext_termino", "eq", r["termino_previsao_seeu"]), C("ext_sit", "contem", "art. 75"), C("ext_cor", "eq", "amarelo"),
     AUD("limite-de-cumprimento-art-75", nivel="alerta", contem=lim), C("termino", "eq", lim + "*")])

k = 8050
c = cr(k, ROUBO, anos(45), "01/03/2021", sentenca="01/11/2021", transito="01/02/2022", regime="Fechado")
lim = venc("01/06/2021", 40)
r = rspe(k, [c], [prisao("01/06/2021", c["processo_criminal"]), prisao("01/02/2022", c["processo_criminal"], "PRISÃO DEFINITIVA")],
         [inc(REG, "Fechado - Regime Inicial", "01/02/2022", "01/02/2022")], ini="01/06/2021")
add(k, "Extinção", "Limite de 40 anos do art. 75 (fato posterior a 23/01/2020): término do SEEU mantido com ressalva",
    "Extinção: término do SEEU (%s) mantido, situação com 'art. 75'; Auditoria: alerta com máximo em %s" % (r["termino_previsao_seeu"], lim),
    "Art. 75 - 45 anos, limite de 40", "Pena 45 anos, fato 01/03/2021 (Lei 13.964/2019: 40 anos). Preso desde 01/06/2021 (flagrante, depois definitiva), "
    "sem interrupção: 01/06/2021 + 40 anos - 1 = %s; o SEEU imprime %s." % (lim, r["termino_previsao_seeu"]), r,
    [C("ext_termino", "eq", r["termino_previsao_seeu"]), C("ext_sit", "contem", "art. 75"), AUD("limite-de-cumprimento-art-75", nivel="alerta", contem=lim)])

k = 8051
ca = cr(k, FURTO, anos(1), "01/02/2019", n=1, ano=2019, sentenca="01/09/2019", transito="01/11/2019", extinto="Sim")
cb = cr(k, ROUBO, anos(8), "01/03/2020", n=2, sentenca="01/10/2020", transito="01/12/2020")
ca["processo_criminal"] += " (Indultada)"
r = rspe(k, [ca, cb], [prisao("01/12/2020", "%s, %s" % (proc(k, 1, 2019), cb["processo_criminal"]), "PRISÃO DEFINITIVA")],
         [inc(REG, "Fechado - Regime Inicial", "01/12/2020", "01/12/2020"),
          inc("INDULTO", "Decreto 11.302/2022", "20/04/2023", "22/12/2022", procs=proc(k, 1, 2019))],
         ini="01/12/2020", pena=anos(8))
add(k, "Extinção", "Indulto já concedido e baixado para uma das penas: ela aparece como extinta; a execução segue pela outra",
    "Furto: extinto por indulto, fora das contas (sem linha de prescrição ativa); execução não extinta, roubo em cumprimento, sem hipótese de extinção",
    "Indulto concedido para uma das ações", "Indulto (Decreto 11.302/2022) concedido em 20/04/2023 para a ação do furto, marcada '(Indultada)' e "
    "'Extinto: Sim': pena extinta (CP, art. 107, II). O roubo (8 anos) segue: preso desde 01/12/2020, término %s." % r["termino_previsao_seeu"], r,
    [P(0, "crime", "nao_contem", "155"), C("ext_sit", "nao_contem", "extinta"), C("ext_sit", "eq", "Em cumprimento"), C("ext_hipoteses", "nao_contem", "xtin")])

k = 8052
c = cr(k, FURTO, anos(2), "01/01/2021", sentenca="01/08/2021", transito="01/10/2021", extinto="Sim")
r = solto(k, [c], incidentes=[inc("INDULTO", "Decreto 11.846/2023", "15/05/2024", "22/12/2023", procs=c["processo_criminal"])],
          status="ARQUIVADO")
add(k, "Extinção", "Indulto concedido para a única pena: execução extinta (registrada)",
    "Pena extinta (registrada), azul; Prescrição: 'Pena extinta'",
    "Indulto da única pena", "Indulto concedido em 15/05/2024 (Decreto 11.846/2023) para o único processo, marcado 'Extinto: Sim': punibilidade extinta "
    "(CP, art. 107, II). Nada a calcular.", r,
    [C("ext_sit", "eq", "Pena extinta (registrada)"), C("ext_cor", "eq", "azul")])

k = 8053
c = cr(k, ROUBO, anos(6), "01/03/2021", sentenca="01/10/2021", transito="01/12/2021")
r = rspe(k, [c], [prisao("01/12/2021", c["processo_criminal"], "PRISÃO DEFINITIVA"), interr("10/07/2026", "ÓBITO")],
         [inc(REG, "Fechado - Regime Inicial", "01/12/2021", "01/12/2021")], ini="01/12/2021",
         interrompidos=dias("11/07/2026", "05/10/2026"), situacao_cumprimento="PENA INTERROMPIDA (sem evento de reinício)", term="")
add(k, "Extinção", "Morte do condenado lançada como interrupção, sem a extinção declarada: cabe declarar extinta a punibilidade (CP, art. 107, I)",
    "Extinção: hipótese de morte do agente (cabível ou a verificar, pedindo a certidão de óbito - CPP, art. 62); Prescrição: não corre (execução encerrada)",
    "Óbito lançado, extinção não declarada", "Interrupção por ÓBITO em 10/07/2026, sem incidente de extinção. A morte extingue a punibilidade "
    "(CP, art. 107, I), declarada à vista da certidão de óbito (CPP, art. 62): a aba deveria apontar a extinção a declarar.", r,
    [C("ext_sit", "regex", "Extinção (cabível|a verificar)"), C("ext_hipoteses", "regex", "[óo]bito|morte"), P(0, "ppe_status", "nao_contem", "aparente")])

k = 8054
c = cr(k, ROUBO, anos(6), "01/03/2021", sentenca="01/10/2021", transito="01/12/2021")
r = rspe(k, [c], [prisao("01/12/2021", c["processo_criminal"], "PRISÃO DEFINITIVA"), interr("10/07/2026", "ÓBITO")],
         [inc(REG, "Fechado - Regime Inicial", "01/12/2021", "01/12/2021"),
          inc("EXTINÇÃO", "MORTE DO AGENTE", "05/08/2026", "10/07/2026", procs=c["processo_criminal"])], ini="01/12/2021",
         interrompidos=dias("11/07/2026", "05/10/2026"), status="ARQUIVADO", term="")
add(k, "Extinção", "Morte do condenado com a extinção já declarada no SEEU",
    "Pena extinta (registrada), azul",
    "Óbito com extinção registrada", "Incidente EXTINÇÃO (morte do agente) concedido em 05/08/2026 para o único processo: punibilidade extinta "
    "(CP, art. 107, I).", r,
    [C("ext_sit", "eq", "Pena extinta (registrada)"), C("ext_cor", "eq", "azul")])

k = 8055
c = cr(k, FURTOQ, anos(3), "01/01/2023", sentenca="01/07/2023", transito="01/09/2023")
r = rspe(k, [c], [prisao("22/09/2023", c["processo_criminal"], "PRISÃO DEFINITIVA")],
         [inc(REG, "Semiaberto - Regime Inicial", "22/09/2023", "22/09/2023")], ini="22/09/2023", regime="Semiaberto - ATIVO")
add(k, "Extinção", "Término do SEEU já alcançado (execução ativa)",
    "Extinção cabível, vermelho; hipótese 'término ... já alcançado' (%s)" % r["termino_previsao_seeu"],
    "Término alcançado em 20/09/2026", "Pena 3 anos (1.095 d), presa desde 22/09/2023: 22/09/2023 + 1.095 - 1 = %s < 12/10/2026: término alcançado - "
    "extinção pelo cumprimento (LEP, art. 66, II)." % r["termino_previsao_seeu"], r,
    [C("ext_sit", "eq", "Extinção cabível"), C("ext_hipoteses", "regex", "alcan|cumprid")])

k = 8056
c = cr(k, ROUBO, anos(5, 4), "01/01/2022", sentenca="01/08/2022", transito="01/10/2022")
r = rspe(k, [c], [prisao("02/10/2022", c["processo_criminal"], "PRISÃO DEFINITIVA")],
         [inc(REG, "Fechado - Regime Inicial", "02/10/2022", "02/10/2022")], ini="02/10/2022", term="")
add(k, "Extinção", "Sem término impresso: o programa calcula o término (data do RSPE + remanescente) e marca com asterisco",
    "Término calculado com asterisco, posterior a 31/03/2027; situação 'Em cumprimento'; sem hipótese de extinção",
    "Término calculado pelo programa", "Pena 5a4m (1.945 d), presa desde 02/10/2022; RSPE de 05/10/2026 sem término. Remanescente impressa = pena - cumprida. "
    "Término = data do RSPE + remanescente (somada como no SEEU) -> por volta de 01/2028, com asterisco: 'Em cumprimento'.", r,
    [C("ext_termino", "regex", r"\*"), C("ext_sit", "eq", "Em cumprimento"), C("ext_hipoteses", "nao_contem", "xtin")])


# ---- achados: divergências mantidas (o gabarito segue a lei; nota explica) ------------------------------------------------
NOTAS = {
    "S8027": {
        0: ("Programa: 'Prescrição executória aparente em 09/05/2023', pelo remanescente impresso pelo SEEU (81 dias -> 3 anos). Os eventos do "
            "próprio RSPE mostram o flagrante de 01/02/2019 a 30/04/2019 neste processo (89 dias), que o SEEU não abateu: pela detração "
            "obrigatória (CP, art. 42) a pena se esgotou em 02/05/2020, antes da fuga. O resultado prático (extinção da punibilidade) é "
            "favorável de qualquer modo; a divergência é o fundamento (prescrição em vez de cumprimento).", True),
        1: ("Programa: 'Pena interrompida', sem hipótese de extinção. Pela lei a pena estava cumprida antes da fuga (detração de 89 dias + "
            "284 dias de cumprimento = 373 >= 365; CP, art. 42; LEP, art. 66, II). O programa confia no remanescente do SEEU e não confere a "
            "detração visível nos eventos.", False),
        2: ("Mesma divergência: nenhuma hipótese de pena cumprida na fuga.", False),
    },
    "S8031": {
        0: ("Programa: linha 'sem pena no RSPE', sem prazo. A multa aplicada isoladamente prescreve em 2 anos (CP, art. 114, I); o programa não "
            "tem conta para a multa. Ressalva: a forma como o SEEU imprime a condenação só à multa foi suposta neste caso (pena 0, 'MULTA: 10 "
            "DIAS-MULTA' na pena total do processo).", False),
        1: ("Programa: 'sem pena no RSPE' (cinza). Pela lei: trânsito 01/03/2022 + 2 anos -> último dia 29/02/2024, aparente.", False),
    },
    "S8053": {
        0: ("Programa: 'Pena interrompida', sem hipótese. A morte do agente extingue a punibilidade (CP, art. 107, I), declarada à vista da "
            "certidão de óbito (CPP, art. 62); a interrupção 'ÓBITO' sem extinção registrada deveria gerar ao menos 'Extinção a verificar'.", False),
        1: ("Programa: hipóteses vazias ('—'); nenhuma menção ao óbito.", False),
    },
}
for _c in CASOS:
    for _i, (_n, _d) in NOTAS.get(_c["id"], {}).items():
        _c["checks"][_i]["nota"] = _n
        if _d:
            _c["checks"][_i]["decisao"] = True
    if _c["id"] in NOTAS:
        _c["nota"] = " ".join(n for n, _ in NOTAS[_c["id"]].values())


if __name__ == "__main__":
    ids = [c["id"] for c in CASOS]
    assert len(ids) == len(set(ids))
    assert all(8001 <= int(i[1:]) <= 8099 for i in ids)
    json.dump(CASOS, open(os.path.join(AQUI, "prescricao_extincao.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("%d casos gravados" % len(CASOS))
