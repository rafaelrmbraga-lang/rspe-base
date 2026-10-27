"""Base de cobertura - área "indulto_novos": indulto e comutação nos Decretos 11.302/2022, 12.338/2024 e 12.790/2025.
Gabarito calculado pelo texto dos decretos (arquivos Decreto_*.pdf do repositório), sem olhar o resultado do programa.
Convenções: dia do começo incluído (CP, art. 10); fração em dias arredondada para baixo; ano de 365 dias e mês de 30 para
penas; anos de cumprimento (incisos IV, V e VI) contados pelo calendário. Faixa de k: 6001-6099.
Uso: python3 gera_indulto_novos.py  (grava indulto_novos.json ao lado)."""
import os, sys, json
from datetime import timedelta, date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base_casos import (D, F, amd, anos, crime, rspe, ev, prisao, interr, inc, C, caso, CP, DROGAS, GER, REG)

R22, R24, R25 = D("25/12/2022"), D("25/12/2024"), D("25/12/2025")
EST = "10826/03 - Estatuto do Desarmamento"


def dd(a, b):
    """dias de custódia de a até b, os dois inclusive."""
    return (b - a).days + 1


def ini_para(ref, dias):
    """data de início que dá 'dias' cumpridos até ref (inclusive)."""
    return ref - timedelta(days=dias - 1)


def fr(p, n, d):
    return p * n // d


def ext(n):
    a, m, d = amd(n)
    return "%da%dm%dd" % (a, m, d)


def proc(k, i=0):
    return "%07d-00.2020.8.12.0001" % (8800000 + (k - 6000) * 10 + i)


# ---- tipos penais simulados ----
def t297(k, i, pena, fato, **kw):
    return crime(proc(k, i), "ART 297: Falsificação de documento público", pena, fato,
                 tipo="CAPUT: Falsificar, no todo ou em parte, documento público, Reclusão: 2 a 6 anos E Multa", **kw)


def t16(k, i, pena, fato, **kw):
    return crime(proc(k, i), "ART 16 - Posse ou porte ilegal de arma de fogo de uso restrito", pena, fato, lei=EST,
                 tipo="CAPUT: Possuir, deter, portar, adquirir, fornecer arma de fogo de uso restrito, Reclusão: 3 a 6 anos E Multa", **kw)


def t14(k, i, pena, fato, **kw):
    return crime(proc(k, i), "ART 14 - Porte ilegal de arma de fogo de uso permitido", pena, fato, lei=EST,
                 tipo="CAPUT: Portar, deter, adquirir, fornecer arma de fogo de uso permitido, Reclusão: 2 a 4 anos E Multa", **kw)


def roubo(k, i, pena, fato, maj=False, **kw):
    tp = ("§ 2º: roubo majorado, Reclusão: 4 a 10 anos E Multa" if maj else
          "CAPUT: Subtrair coisa móvel alheia, para si ou para outrem, mediante grave ameaça ou violência a pessoa, Reclusão: 4 a 10 anos E Multa")
    return crime(proc(k, i), "ART 157: Roubo", pena, fato, tipo=tp, vga="S", **kw)


def furto(k, i, pena, fato, **kw):
    return crime(proc(k, i), "ART 155: Furto", pena, fato,
                 tipo="CAPUT: Subtrair, para si ou para outrem, coisa alheia móvel, Reclusão: 1 a 4 anos E Multa", **kw)


def p_def(data, k, i=0, motivo="PRISÃO DEFINITIVA"):
    return prisao(F(data) if isinstance(data, date) else data, proc(k, i), motivo)


def reg(compl, ref):
    return inc(REG, compl, "", F(ref) if isinstance(ref, date) else ref)


CASOS = []


def novo(k, titulo, situacao, esperado, conta, r, checks, ficha=None, manuais=None):
    c = caso(k, "indulto_novos", titulo, conta, r, checks, ficha=ficha, manuais=manuais)
    c.update(aba="Indulto", situacao=situacao, esperado=esperado)
    CASOS.append(c)
    return c


# ---- verificações ----
def POS(campo, com=(), sem=(), nota=""):
    """Resultado começa por POSSÍVEL; os incisos 'com' estão no primeiro trecho (antes de '|'), os 'sem' não."""
    rx = "^POSSÍVEL" + "".join(r"(?=[^|]*\b%s\b)" % x for x in com) + "".join(r"(?![^|]*\b%s\b)" % x for x in sem)
    return C(campo, "regex", rx, nota)


def RX(campo, rx, nota=""):
    return C(campo, "regex", rx, nota)


def NAO_POS(campo, nota=""):
    return C(campo, "regex", r"^(?!POSS)", nota)


def ficha_sexo(k, nasc, sexo, entrada):
    return {"tipo": "ficha_disciplinar", "nome": "SIMULADO CASO %03d" % k, "cpf": "%011d" % (90000000000 + k), "data_nascimento": nasc,
            "nome_mae": "MAE SIMULADA %03d" % k, "sexo": sexo, "unidade": "ESTABELECIMENTO PENAL FEMININO SIMULADO" if sexo == "F" else "ESTABELECIMENTO PENAL SIMULADO",
            "conduta": "BOA", "data_impressao": "06/10/2026", "autos": ["%07d-00.2026.8.12.0001" % (9900000 + k)],
            "eventos": [{"data": entrada.strftime("%d.%m.%Y"), "texto": "Entrada na Unidade Penal: ESTABELECIMENTO PENAL SIMULADO, Procedente: DEPAC, Conforme OF 1."}]}


# =====================================================================================================================
# ART. 9º, INCISO I
# =====================================================================================================================
k = 6001
P = anos(5); ini = D("01/10/2023"); c24 = dd(ini, R24)
assert fr(P, 1, 5) <= c24 < fr(P, 1, 3)
novo(k, "Indulto 2024, art. 9º, I: falsificação de 5 anos, 1/5 cumprido",
     "Inciso I do Decreto 12.338/2024 (pena até 8 anos sem violência, 1/5 para primário)",
     "Indulto 2024 POSSÍVEL pelo art. 9º, I (não pelo II); comutação 2024 prejudicada (art. 13, § 5º); o XVI aparece só como 'a verificar'",
     f"Falsificação de documento público (CP, art. 297), 5a = {P} dias, primário, sem violência. Preso desde {F(ini)}: até 25/12/2024 = {c24} dias "
     f"({ext(c24)}). Inciso I: 1/5 = {fr(P,1,5)} dias - atendido. Inciso II: 1/3 = {fr(P,1,3)} - não atendido. Decreto 12.338/2024, art. 9º, I e II; "
     "comutação prejudicada pelo indulto cabível (art. 13, § 5º).",
     rspe(k, [t297(k, 0, P, "10/03/2023", sentenca="10/07/2023")], [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [POS("ind24", ["I"], ["II"]), RX("com24", "^prejudicada"), C("det24", "contem", "XVI")])

k = 6002
P = anos(4, 6); f = fr(P, 1, 3); ini = ini_para(R25, f)
novo(k, "Indulto 2025, art. 9º, I: reincidente com 1/3 exato",
     "Inciso I do Decreto 12.790/2025 para reincidente (1/3), no limite exato",
     "Indulto 2025 POSSÍVEL pelo art. 9º, I (não pelo II); comutação 2025 prejudicada",
     f"CP, art. 297, pena 4a6m = {P} dias, reincidente. 1/3 de {P} = {f} dias (arredondado para baixo). Preso desde {F(ini)}: até 25/12/2025 = "
     f"{dd(ini,R25)} dias = 1/3 exato. II (reincidente, 1/2 = {fr(P,1,2)}) não. Decreto 12.790/2025, art. 9º, I; art. 13, § 5º.",
     rspe(k, [t297(k, 0, P, "10/06/2023", rc="S")], [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [POS("ind25", ["I"], ["II"]), RX("com25", "^prejudicada")])

k = 6003
P = anos(4, 6); ini = ini_para(R25, fr(P, 1, 3) - 1); c25 = dd(ini, R25)
assert c25 == fr(P, 1, 3) - 1 and c25 >= fr(P, 1, 4)
novo(k, "Indulto 2025, art. 9º, I: reincidente a 1 dia do 1/3; comutação 1/4 atendida",
     "Inciso I não atingido por 1 dia (reincidente) e comutação do art. 13 com 1/4",
     "Inciso I não atendido (falta 1 dia); indulto sem inciso atendido (fica no máximo 'a verificar' pelo estudo/curso, XII e XIII, que o RSPE não mostra); "
     "comutação 2025 cabível pelo art. 13 (1/4 cumprido), condicionada ao indulto não couber",
     f"CP, art. 297, 4a6m = {P} dias, reincidente. Cumprido até 25/12/2025: {c25} dias. I exige 1/3 = {fr(P,1,3)}: falta 1 dia. "
     f"Comutação (art. 13): reincidente 1/4 = {fr(P,1,4)} dias - atendido. XII (1/5 reincidente em 2025 = {fr(P,1,5)}) e XIII (1/4) dependem de estudo/curso: a verificar.",
     rspe(k, [t297(k, 0, P, "10/06/2023", rc="S")], [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [RX("det25", r"✘ I:"), C("ind25", "regex", r"^(?!POSS)"), RX("com25", r"^(POSSÍVEL|A VERIFICAR)[^|]*art\. 13")])

# =====================================================================================================================
# INCISO II
# =====================================================================================================================
k = 6004
P = anos(10); c = 1300; ini = ini_para(R24, c)
assert fr(P, 1, 3) <= c < fr(P, 1, 2)
novo(k, "Indulto 2024, art. 9º, II: duas falsificações somando 10 anos, 1/3 cumprido",
     "Inciso II do Decreto 12.338/2024 (pena até 12 anos sem violência, 1/3) com pena acima do teto do inciso I",
     "Indulto 2024 POSSÍVEL pelo art. 9º, II (o I não, pena acima de 8 anos); comutação prejudicada",
     f"Duas condenações do CP, art. 297, 5a + 5a = {P} dias (art. 7º: penas somadas). Primário. Preso desde {F(ini)}: {c} dias até 25/12/2024. "
     f"I: teto de 8 anos excedido. II: 1/3 = {fr(P,1,3)} - atendido.",
     rspe(k, [t297(k, 0, anos(5), "10/02/2021"), t297(k, 1, anos(5), "20/03/2021")], [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [POS("ind24", ["II"], ["I"]), RX("com24", "^prejudicada")])

k = 6005
P = anos(9); c = 1700; ini = ini_para(R25, c)
assert fr(P, 1, 2) <= c
novo(k, "Indulto 2025, art. 9º, II: reincidente com metade da pena de 9 anos",
     "Inciso II do Decreto 12.790/2025 para reincidente (1/2); inciso XIII só a verificar",
     "Indulto 2025 POSSÍVEL pelo art. 9º, II; o XIII aparece como 'a verificar' (curso concluído não consta no RSPE)",
     f"CP, art. 297 (5a) + Lei 10.826, art. 16 (4a) = {P} dias, reincidente. Preso desde {F(ini)}: {c} dias até 25/12/2025. "
     f"II (reincidente): 1/2 = {fr(P,1,2)} - atendido. I: pena acima de 8 anos. XIII (reincidente, 1/4 = {fr(P,1,4)}) depende de curso concluído.",
     rspe(k, [t297(k, 0, anos(5), "10/02/2020", rc="S"), t16(k, 1, anos(4), "10/02/2020", rc="S")], [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [POS("ind25", ["II"], ["I"]), C("det25", "contem", "XIII")])

# =====================================================================================================================
# INCISO III
# =====================================================================================================================
k = 6006
P = anos(4); c = 500; ini = ini_para(R24, c)
novo(k, "Indulto 2024, art. 9º, III: roubo de 4 anos, 1/3 cumprido",
     "Inciso III do Decreto 12.338/2024 (com violência, pena até 4 anos, 1/3)",
     "Indulto 2024 POSSÍVEL pelo art. 9º, III; comutação prejudicada",
     f"Roubo simples (CP, art. 157), 4a = {P} dias, com grave ameaça, primário. Preso desde {F(ini)}: {c} dias até 25/12/2024. "
     f"III: pena não superior a 4 anos, 1/3 = {fr(P,1,3)} - atendido. I e II exigem crime sem violência.",
     rspe(k, [roubo(k, 0, P, "01/03/2023")], [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [POS("ind24", ["III"]), RX("com24", "^prejudicada")])

k = 6007
P = anos(3, 6); c = 650; ini = ini_para(R25, c)
assert fr(P, 1, 2) <= c
novo(k, "Indulto 2025, art. 9º, III: roubo de 3a6m, reincidente com metade",
     "Inciso III do Decreto 12.790/2025 para reincidente (1/2)",
     "Indulto 2025 POSSÍVEL pelo art. 9º, III",
     f"Roubo, 3a6m = {P} dias, reincidente. Preso desde {F(ini)}: {c} dias até 25/12/2025. III reincidente: 1/2 = {fr(P,1,2)} - atendido.",
     rspe(k, [roubo(k, 0, P, "01/06/2023", rc="S")], [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [POS("ind25", ["III"])])

k = 6008
P = anos(4, 1); c = 700; ini = ini_para(R25, c)
novo(k, "Indulto 2025: roubo de 4a1m não cabe no inciso III; comutação pelo art. 13",
     "Teto de 4 anos do inciso III excedido; comutação de primário (1/5) atendida",
     "Inciso III não atendido (pena acima de 4 anos); indulto não é 'possível' (no máximo 'a verificar' pelo estudo/curso, XII e XIII); "
     "comutação 2025 cabível pelo art. 13",
     f"Roubo, 4a1m = {P} dias (> 1.460), primário. Cumprido até 25/12/2025: {c} dias. III: teto excedido. Comutação: 1/5 = {fr(P,1,5)} - atendido; "
     f"redução de 1/5 do remanescente ({P - c} dias).",
     rspe(k, [roubo(k, 0, P, "01/06/2023")], [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [C("ind25", "regex", r"^(?!POSS)"), RX("det25", "✘ III"), RX("com25", r"^(POSSÍVEL|A VERIFICAR)[^|]*art\. 13")])

# =====================================================================================================================
# INCISO IV
# =====================================================================================================================
k = 6009
P = anos(24); ini = D("10/11/2009")
assert ini <= D("25/12/2009")
novo(k, "Indulto 2024 e 2025, art. 9º, IV: 15 anos ininterruptos (primário)",
     "Inciso IV (15 anos de cumprimento ininterrupto, primário), sem teto de pena",
     "Indulto 2024 e 2025 POSSÍVEL pelo art. 9º, IV; comutação 2024 prejudicada",
     f"Dois roubos majorados (12a + 12a = {P} dias), primário. Preso sem interrupção desde {F(ini)}; 15 anos pelo calendário até 25/12/2024 "
     f"começam em 25/12/2009: atendido ({dd(ini, R24)} dias). Incisos I a III não (violência; pena acima de 4 anos).",
     rspe(k, [roubo(k, 0, anos(12), "01/09/2009", maj=True, sentenca="01/03/2010"), roubo(k, 1, anos(12), "01/09/2009", maj=True, sentenca="01/03/2010")],
          [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [POS("ind24", ["IV"]), POS("ind25", ["IV"]), RX("com24", "^prejudicada")])

k = 6010
P = anos(20); ini = D("01/04/2018"); c24 = dd(ini, R24); red = fr(P - c24, 2, 3)
novo(k, "Indulto 2025, art. 9º, IV com § 2º, I (65 anos): 7a6m ininterruptos; comutação 2024 de 2/3",
     "Inciso IV pela metade (§ 2º, I: maior de 60 anos) e comutação na proporção de 2/3 (art. 13, § 4º)",
     "2025: indulto POSSÍVEL pelo art. 9º, IV (metade: 7a6m). 2024: IV não (6a8m de 7a6m); comutação 2024 cabível com redução de 2/3 do remanescente",
     f"Roubo majorado 20a = {P} dias, primário, nascido em 01/01/1960 (64 anos em 25/12/2024, 65 em 25/12/2025). Preso desde {F(ini)}. "
     f"IV com § 2º, I: 15/2 = 7a6m pelo calendário; até 25/12/2025 começa em 25/06/2018 - atendido; em 2024 começaria em 25/06/2017 - não. "
     f"Comutação 2024: 1/5 = {fr(P,1,5)}, cumprido {c24} - atendido; § 4º: 2/3 do remanescente ({P - c24}) = {red} dias = {ext(red)} "
     "(o cumprido é menor que o remanescente, então a base é o remanescente). XII não tem o lapso reduzido (§ 2º só vale para I a XI).",
     rspe(k, [roubo(k, 0, P, "01/01/2018", maj=True)], [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini), nasc="01/01/1960"),
     [POS("ind25", ["IV"]), C("ind24", "regex", r"^(?!POSS)"), RX("com24", r"^(POSSÍVEL|A VERIFICAR)[^|]*art\. 13"),
      C("cdet24", "contem", ["2/3", ext(red)])])

# =====================================================================================================================
# INCISO V
# =====================================================================================================================
k = 6012
P = anos(40); a1, f1, a2 = D("01/02/2003"), D("31/12/2013"), D("01/06/2014")
lib = (a2 - f1).days - 1; tot = dd(a1, f1) + dd(a2, R24)
assert tot >= dd(D("26/12/2004"), R24) and lib <= 730 and dd(a2, R24) < dd(D("26/12/2009"), R24)
novo(k, "Indulto 2024 e 2025, art. 9º, V: 20 anos não ininterruptos com 151 dias em liberdade",
     "Inciso V (20 anos não ininterruptos, liberdade de até 2 anos)",
     "Indulto 2024 e 2025 POSSÍVEL pelo art. 9º, V (IV não: o período contínuo atual tem cerca de 10 anos)",
     f"Dois roubos majorados (20a + 20a), primário. Custódia de {F(a1)} a {F(f1)} ({dd(a1,f1)} dias), fuga, recaptura em {F(a2)}: {lib} dias em liberdade "
     f"(até 2 anos). Total até 25/12/2024: {tot} dias, acima de 20 anos pelo calendário (7.305 dias). IV: desde {F(a2)} são {dd(a2,R24)} dias, menos de 15 anos.",
     rspe(k, [roubo(k, 0, anos(20), "01/06/2002", maj=True, sentenca="01/12/2002"), roubo(k, 1, anos(20), "01/06/2002", maj=True, sentenca="01/12/2002")],
          [p_def(a1, k), interr(F(f1), "FUGA"), p_def(a2, k, motivo="RECAPTURA/REINÍCIO DE CUMPRIMENTO")], [reg("Fechado - Regime Inicial", a1)],
          ini=F(a1), interrompidos=lib),
     [POS("ind24", ["V"]), POS("ind25", ["V"])])

# =====================================================================================================================
# INCISO VI e X
# =====================================================================================================================
k = 6014
P = anos(20); ini, semi = D("01/03/2011"), D("10/11/2014")
novo(k, "Indulto 2024 e 2025, art. 9º, VI: 10 anos ininterruptos no semiaberto",
     "Inciso VI (10 anos no semiaberto) e inciso X apenas 'a verificar' (monitoramento pela SV 56)",
     "Indulto 2024 e 2025 POSSÍVEL pelo art. 9º, VI; o X aparece como 'a verificar' (semiaberto há mais de 3 anos)",
     f"Dois roubos majorados (10a + 10a = {P} dias), primário. Preso desde {F(ini)}; semiaberto desde {F(semi)} sem regressão: até 25/12/2024 são 10 anos "
     "pelo calendário (desde 25/12/2014) - VI atendido. IV: custódia desde 2011, menos de 15 anos. X exige monitoramento eletrônico pela SV 56 - não consta.",
     rspe(k, [roubo(k, 0, anos(10), "01/06/2010", maj=True), roubo(k, 1, anos(10), "01/06/2010", maj=True)], [p_def(ini, k)],
          [reg("Fechado - Regime Inicial", ini), reg("Semiaberto - Progressão de Regime", semi)], ini=F(ini), regime="Semiaberto - ATIVO"),
     [POS("ind24", ["VI"]), POS("ind25", ["VI"]), C("det24", "contem", "? X")])

k = 6015
P = anos(24); ini, semi = D("01/06/2010"), D("01/12/2013")
novo(k, "Indulto 2025: reincidente com 12 anos de semiaberto (VI exige 15); X a verificar",
     "Inciso VI de reincidente não atingido; inciso X do Decreto 12.790/2025 'a verificar'",
     "Indulto 2025 A VERIFICAR só pelo art. 9º, X (monitoramento SV 56 não consta no RSPE); VI não atendido; comutação 2025 cabível (1/4)",
     f"Dois roubos majorados (12a + 12a = {P} dias), reincidente. Semiaberto desde {F(semi)}: 12 anos até 25/12/2025 (VI reincidente exige 15). "
     f"IV reincidente (20 anos) e V (25) não. XI, XII e XIII: pena acima de 12 anos. X: semiaberto há mais de 3 anos - depende de monitoramento (SV 56). "
     f"Comutação: 1/4 = {fr(P,1,4)}; cumprido {dd(ini,R25)} - atendido.",
     rspe(k, [roubo(k, 0, anos(12), "01/01/2010", maj=True, rc="S"), roubo(k, 1, anos(12), "01/01/2010", maj=True, rc="S")], [p_def(ini, k)],
          [reg("Fechado - Regime Inicial", ini), reg("Semiaberto - Progressão de Regime", semi)], ini=F(ini), regime="Semiaberto - ATIVO"),
     [RX("ind25", r"^A VERIFICAR[^|]*\bX\b"), RX("det25", "✘ VI"), RX("com25", r"art\. 13")])

# =====================================================================================================================
# INCISO VII e IX
# =====================================================================================================================
k = 6016
P = anos(9); ini, ab = D("01/11/2022"), D("01/09/2024"); c24 = dd(ini, R24)
assert fr(P, 1, 6) <= c24 < fr(P, 1, 3) and P - c24 > anos(6)
novo(k, "Indulto 2024, art. 9º, VII: regime aberto com 1/6, remanescente acima de 6 anos",
     "Inciso VII (aberto, 1/6) sem o VIII (remanescente acima de 6 anos); IX a verificar",
     "Indulto 2024 POSSÍVEL pelo art. 9º, VII (VIII não); o IX aparece como 'a verificar'",
     f"Duas condenações do CP, art. 297 (4a6m + 4a6m = {P} dias), primário. Preso desde {F(ini)}, aberto desde {F(ab)}. Até 25/12/2024: {c24} dias. "
     f"VII: 1/6 = {fr(P,1,6)} - atendido. VIII: remanescente {P - c24} dias > 6 anos (2.190) - não. I: pena acima de 8 anos. II: 1/3 = {fr(P,1,3)} - não. "
     "IX depende de programa de egressos (não consta).",
     rspe(k, [t297(k, 0, anos(4, 6), "01/03/2022", sentenca="01/09/2022", transito="01/10/2022"),
              t297(k, 1, anos(4, 6), "01/03/2022", sentenca="01/09/2022", transito="01/10/2022")], [p_def(ini, k)],
          [reg("Semiaberto - Regime Inicial", ini), reg("Aberto - Progressão de Regime", ab)], ini=F(ini), regime="Aberto - ATIVO"),
     [POS("ind24", ["VII"], ["VIII"]), C("det24", "contem", "? IX")])

k = 6017
P = anos(2); c = 130; ini = ini_para(R25, c)
assert fr(P, 1, 6) <= c < fr(P, 1, 5)
novo(k, "Indulto 2025, art. 9º, VII: pena substituída por restritiva de direitos, 1/6 cumprido",
     "Inciso VII pela pena restritiva de direitos (art. 3º, I) entre 1/6 e 1/5; IX a verificar",
     "Indulto 2025 POSSÍVEL pelo art. 9º, VII (o I não: falta chegar a 1/5); IX 'a verificar'",
     f"CP, art. 297, 2a = {P} dias substituída por restritivas de direitos, primário; cumprimento desde {F(ini)}: {c} dias até 25/12/2025. "
     f"VII: 1/6 = {fr(P,1,6)} - atendido. I: 1/5 = {fr(P,1,5)} - não. Decreto 12.790/2025, arts. 3º, I, e 9º, VII.",
     rspe(k, [t297(k, 0, P, "01/02/2024", regime="Aberto")], [ev("PRISÃO/INÍCIO DE CUMPRIMENTO", "INÍCIO DE CUMPRIMENTO - PENA RESTRITIVA DE DIREITOS", F(ini), proc(k))],
          [reg("Restritiva de Direitos - Substituição", ini)], ini=F(ini), regime="Restritiva de Direitos - ATIVO"),
     [POS("ind25", ["VII"], ["I"]), C("det25", "contem", "? IX")])

# =====================================================================================================================
# INCISO VIII
# =====================================================================================================================
k = 6018
P = anos(12); ini, lc = D("01/03/2018"), D("01/07/2023"); c24 = dd(ini, R24)
assert P - c24 <= anos(6)
novo(k, "Indulto 2024 e 2025, art. 9º, VIII: livramento com remanescente até 6 anos",
     "Inciso VIII (livramento condicional, primário, remanescente até 6 anos); IX a verificar",
     "Indulto 2024 e 2025 POSSÍVEL pelo art. 9º, VIII; comutação 2024 prejudicada",
     f"Roubo majorado 12a = {P} dias, primário. Preso desde {F(ini)}, livramento desde {F(lc)} (período de prova conta como pena cumprida). "
     f"Até 25/12/2024: {c24} dias; remanescente {P - c24} dias, até 6 anos (2.190) - VIII atendido; em 2025 o remanescente é menor ainda.",
     rspe(k, [roubo(k, 0, P, "01/10/2017", maj=True)], [p_def(ini, k), interr(F(lc), "LIVRAMENTO CONDICIONAL")],
          [reg("Fechado - Regime Inicial", ini), reg("Semiaberto - Progressão de Regime", D("01/06/2020")),
           inc("LIVRAMENTO CONDICIONAL", F(lc), "20/06/2023", F(lc))], ini=F(ini), regime="Livramento Condicional - ATIVO"),
     [POS("ind24", ["VIII"]), POS("ind25", ["VIII"]), RX("com24", "^prejudicada"), C("det24", "contem", "? IX")])

k = 6019
P = anos(15); c = 3550; ini = ini_para(R25, c); lc = D("01/03/2025")
assert P - c > anos(4)
novo(k, "Indulto 2025: reincidente em livramento com remanescente acima de 4 anos (VIII não); IX a verificar",
     "Inciso VIII de reincidente não atendido; inciso IX do Decreto 12.790/2025 'a verificar'",
     "Indulto 2025 A VERIFICAR só pelo art. 9º, IX (programa de egressos); comutação 2025 cabível (1/4)",
     f"Roubo majorado 15a = {P} dias, reincidente, livramento desde {F(lc)}. Cumprido até 25/12/2025: {c}; remanescente {P - c} > 4 anos (1.460) - VIII não. "
     f"XII e XIII: pena acima de 12 anos. Comutação: 1/4 = {fr(P,1,4)} - atendido.",
     rspe(k, [roubo(k, 0, P, "01/01/2016", maj=True, rc="S")], [p_def(ini, k), interr(F(lc), "LIVRAMENTO CONDICIONAL")],
          [reg("Fechado - Regime Inicial", ini), inc("LIVRAMENTO CONDICIONAL", F(lc), "20/02/2025", F(lc))], ini=F(ini), regime="Livramento Condicional - ATIVO"),
     [RX("ind25", r"^A VERIFICAR[^|]*\bIX\b"), RX("det25", "✘ VIII"), RX("com25", r"art\. 13")])

# =====================================================================================================================
# INCISO XI
# =====================================================================================================================
k = 6021
P = anos(9); ini, semi = D("01/06/2021"), D("01/01/2023"); c24 = dd(ini, R24)
assert c24 >= fr(P, 1, 3)
sts = ["01/04/2023", "01/07/2023", "01/10/2023", "20/12/2023", "01/04/2024"]
novo(k, "Indulto 2024 e 2025, art. 9º, XI: semiaberto, 1/3 e cinco saídas temporárias",
     "Inciso XI (pena até 12 anos, semiaberto, 1/3 e 5 saídas temporárias)",
     "Indulto 2024 e 2025 POSSÍVEL pelo art. 9º, XI",
     f"Roubo majorado 9a = {P} dias, primário. Preso desde {F(ini)}, semiaberto desde {F(semi)}; 5 saídas temporárias concedidas ({', '.join(sts)}). "
     f"Até 25/12/2024: {c24} dias; 1/3 = {fr(P,1,3)} - atendido. I a III não (violência; pena acima de 4 anos). As saídas continuam valendo em 2025.",
     rspe(k, [roubo(k, 0, P, "10/01/2020", maj=True)], [p_def(ini, k)],
          [reg("Fechado - Regime Inicial", ini), reg("Semiaberto - Progressão de Regime", semi)] + [inc("SAÍDA TEMPORÁRIA", "", s, s) for s in sts],
          ini=F(ini), regime="Semiaberto - ATIVO"),
     [POS("ind24", ["XI"]), POS("ind25", ["XI"])])

# =====================================================================================================================
# INCISOS XII e XIII
# =====================================================================================================================
k = 6023
P = anos(6); c = 450; ini = ini_para(R24, c)
novo(k, "Indulto 2024, art. 9º, XII e XIII: roubo de 6 anos com 1/5 - estudo e curso a verificar",
     "Incisos XII e XIII do Decreto 12.338/2024 (1/5 para primário) sem a ficha: a verificar",
     "Indulto 2024 A VERIFICAR pelos incisos XII e XIII; comutação 2024 cabível (1/5), se o indulto não couber",
     f"Roubo 6a = {P} dias, primário. Cumprido até 25/12/2024: {c}. XII e XIII (2024): 1/5 = {fr(P,1,5)} - atendido, mas estudo de 12 meses e "
     f"curso concluído não constam no RSPE. III: pena acima de 4 anos. Comutação: 1/5 - atendido.",
     rspe(k, [roubo(k, 0, P, "01/03/2023")], [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [RX("ind24", r"^A VERIFICAR(?=[^|]*\bXII\b)(?=[^|]*\bXIII\b)"), RX("com24", r"art\. 13")])

k = 6024
P = anos(6); c = 400; ini = ini_para(R25, c)
assert fr(P, 1, 6) <= c < fr(P, 1, 5)
novo(k, "Indulto 2025, art. 9º, XII com 1/6 (XIII exige 1/5)",
     "Fração do inciso XII no Decreto 12.790/2025 (1/6 para primário), diferente do XIII (1/5)",
     "Indulto 2025 A VERIFICAR pelo XII (estudo não consta); o XIII não (falta 1/5); comutação 2025 não atinge (1/5)",
     f"Roubo 6a = {P} dias, primário. Cumprido até 25/12/2025: {c}. XII (2025): 1/6 = {fr(P,1,6)} - atendido, estudo a verificar. "
     f"XIII: 1/5 = {fr(P,1,5)} - não. Comutação: 1/5 = {fr(P,1,5)} - não.",
     rspe(k, [roubo(k, 0, P, "01/03/2024")], [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [RX("ind25", r"^A VERIFICAR(?=[^|]*\bXII\b)(?![^|]*\bXIII\b)"), RX("com25", "^não atinge")])

# =====================================================================================================================
# INCISOS XIV e XV
# =====================================================================================================================
k = 6025
P = anos(3); c = 55; ini = ini_para(R24, c)
novo(k, "Indulto 2024, art. 9º, XV: estelionato com 55 dias (XIV exige 3 meses)",
     "Inciso XV (patrimônio sem violência, reparação dispensada para assistido da Defensoria) sem o XIV",
     "Indulto 2024 POSSÍVEL pelo art. 9º, XV (o XIV não: menos de 3 meses cumpridos); comutação prejudicada",
     f"Estelionato (CP, art. 171), 3a = {P} dias, primário. Cumprido até 25/12/2024: {c} dias. XV: crime patrimonial sem violência; a reparação é dispensada "
     "nas hipóteses do art. 12, § 2º (I: representado pela Defensoria). XIV: exige 90 dias - não. I: 1/5 = %d - não." % fr(P, 1, 5),
     rspe(k, [crime(proc(k), "ART 171: Estelionato", P, "01/01/2024", tipo="CAPUT: Obter, para si ou para outrem, vantagem ilícita, Reclusão: 1 a 5 anos E Multa")],
          [p_def(ini, k)], [reg("Semiaberto - Regime Inicial", ini)], ini=F(ini), regime="Semiaberto - ATIVO"),
     [POS("ind24", ["XV"], ["XIV", "I"]), RX("com24", "^prejudicada")])

k = 6026
P = anos(2); c = 100; ini = ini_para(R25, c)
novo(k, "Indulto 2025, art. 9º, XIV: furto com 100 dias - valor do bem a verificar; XV possível",
     "Inciso XIV (3 meses cumpridos; valor do bem até 1 salário mínimo não consta) junto do XV",
     "Indulto 2025 POSSÍVEL pelo art. 9º, XV; o XIV aparece como 'a verificar' (valor do bem)",
     f"Furto simples, 2a = {P} dias, primário. Cumprido até 25/12/2025: {c} dias (mais de 90). XIV depende do valor do bem (não consta). XV atendido. "
     f"I: 1/5 = {fr(P,1,5)} - não.",
     rspe(k, [furto(k, 0, P, "01/02/2025", sentenca="01/08/2025")], [p_def(ini, k)], [reg("Semiaberto - Regime Inicial", ini)], ini=F(ini), regime="Semiaberto - ATIVO"),
     [POS("ind25", ["XV"], ["I"]), RX("det25", r"\? XIV")])

k = 6027
c = dd(D("01/09/2025"), R25); ini = D("01/09/2025"); P = anos(8)
assert c < fr(P, 1, 5) and c < fr(anos(6), 1, 5)
novo(k, "Indulto 2025, art. 9º, XV só para o furto, em concurso com roubo; comutação não atinge",
     "Inciso XV parcial (alcança só a pena patrimonial sem violência) e comutação sobre o restante",
     "Indulto 2025 POSSÍVEL pelo art. 9º, XV apenas quanto ao furto (o roubo segue); comutação 2025 não atinge",
     f"Furto simples 2a + roubo 6a = {P} dias, primário. Preso desde {F(ini)}: {c} dias até 25/12/2025. XV alcança o furto (patrimonial sem violência). "
     f"Roubo não é crime do art. 1º (sem a regra dos 2/3). Comutação: 1/5 da soma = {fr(P,1,5)} (ou 1/5 só do roubo = {fr(anos(6),1,5)}) - não atinge.",
     rspe(k, [furto(k, 0, anos(2), "01/01/2025", sentenca="01/06/2025"), roubo(k, 1, anos(6), "01/01/2025", sentenca="01/06/2025")],
          [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [POS("ind25", ["XV"]), RX("com25", "^não atinge")])

# =====================================================================================================================
# INCISO XVI
# =====================================================================================================================
k = 6028
P = anos(10); c = 100; ini = ini_para(R25, c)
novo(k, "Indulto 2025: nenhum inciso atingido; XVI (saúde) só como 'a verificar'",
     "Inciso XVI (saúde e deficiência) não aferível pelo RSPE e que não decide o resultado",
     "Indulto 2025 'não atinge'; o XVI aparece no detalhamento como 'a verificar' (laudo); comutação 2025 não atinge",
     f"Roubo 10a = {P} dias, primário, {c} dias cumpridos até 25/12/2025. Nenhuma fração atingida (XII 1/6 = {fr(P,1,6)}; comutação 1/5 = {fr(P,1,5)}). "
     "XVI depende de laudo médico.",
     rspe(k, [roubo(k, 0, P, "01/03/2025", maj=True, sentenca="01/08/2025")], [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [RX("ind25", "^não atinge"), C("det25", "contem", "XVI"), RX("com25", "^não atinge")])

# =====================================================================================================================
# § 2º (idade e condição pessoal)
# =====================================================================================================================
k = 6029
P = anos(5); c = 200; ini = ini_para(R25, c)
assert fr(P, 1, 10) <= c < fr(P, 1, 6)
novo(k, "Indulto 2025, art. 9º, I com § 2º, I: 61 anos, 1/10 cumprido",
     "Metade do lapso pela idade (maior de 60 anos) no inciso I",
     "Indulto 2025 POSSÍVEL pelo art. 9º, I (1/10); o II não (1/6); comutação prejudicada",
     f"CP, art. 297, 5a = {P} dias, primário, nascido em 01/06/1964 (61 anos em 25/12/2025). Cumprido: {c}. I com § 2º, I: 1/10 = {fr(P,1,10)} - atendido. "
     f"II com § 2º: 1/6 = {fr(P,1,6)} - não.",
     rspe(k, [t297(k, 0, P, "01/03/2024")], [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini), nasc="01/06/1964"),
     [POS("ind25", ["I"], ["II"]), RX("com25", "^prejudicada")])

k = 6030
P = anos(5); c = 200; ini = ini_para(R25, c)
novo(k, "Indulto 2025: completa 60 anos em 26/12/2025 - sem a metade pela idade",
     "Idade na data do decreto: 59 anos em 25/12/2025 (§ 2º, I não se aplica); metade por condição pessoal (§ 2º, II a VI) só a verificar",
     "Sem a metade pela idade: inciso I não atendido; indulto 2025 A VERIFICAR apenas pelo § 2º, II a VI (filhos, deficiência etc. não constam); comutação não atinge",
     f"CP, art. 297, 5a = {P} dias, primário, nascido em 26/12/1965: 59 anos em 25/12/2025. Cumprido {c}. I exige 1/5 = {fr(P,1,5)} - não. "
     f"Pela metade (§ 2º, II a VI, condições que o RSPE não mostra) seria {fr(P,1,10)} - a verificar. Comutação: 1/5 - não (o § 2º não reduz o requisito da comutação).",
     rspe(k, [t297(k, 0, P, "01/03/2024")], [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini), nasc="26/12/1965"),
     [RX("ind25", r"^A VERIFICAR[^|]*§ 2º"), C("det25", "nao_contem", "60 anos"), RX("com25", "^não atinge")])

k = 6031
P = anos(3); c = 150; ini = ini_para(R24, c)
assert fr(P, 1, 10) <= c < fr(P, 1, 5)
novo(k, "Indulto 2024: metade do lapso por condição pessoal (§ 2º, II a VI) - a verificar",
     "§ 2º, II a VI do Decreto 12.338/2024: o lapso pela metade alcançaria o inciso I",
     "Indulto 2024 A VERIFICAR pelo § 2º (mãe/pai responsável, deficiência, justiça restaurativa - não constam no RSPE); comutação 2024 não atinge",
     f"Porte de arma (Lei 10.826, art. 14), 3a = {P} dias, primário, 44 anos. Cumprido até 25/12/2024: {c}. I: 1/5 = {fr(P,1,5)} - não; metade = {fr(P,1,10)} - "
     "atingida se houver condição do § 2º, II a VI. Comutação: 1/5 - não.",
     rspe(k, [t14(k, 0, P, "01/01/2024", sentenca="01/06/2024")], [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini), nasc="01/01/1980"),
     [RX("ind24", r"^A VERIFICAR[^|]*§ 2º"), RX("com24", "^não atinge")])

# =====================================================================================================================
# ART. 10 (mulheres)
# =====================================================================================================================
k = 6032
P = anos(6); c = 400; ini = ini_para(R24, c)
assert fr(P, 1, 6) <= c < fr(P, 1, 5)
novo(k, "Indulto 2024, art. 10, III, c: mulher de 20 anos com 1/6",
     "Indulto especial das mulheres presas (Decreto 12.338/2024, art. 10): menor de 21 anos, 1/6",
     "Indulto 2024 POSSÍVEL pelo art. 10, III, c (o art. 9º, I não: falta 1/5); comutação prejudicada",
     f"Mulher (ficha: sexo F), nascida em 01/06/2004 (20 anos em 25/12/2024), presa, CP art. 297, 6a = {P} dias, sem falta grave. Cumprido {c}. "
     f"Art. 10, III, c (2024): 1/6 = {fr(P,1,6)} - atendido. Art. 9º, I: 1/5 = {fr(P,1,5)} - não.",
     rspe(k, [t297(k, 0, P, "01/03/2023")], [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini), nasc="01/06/2004"),
     [RX("ind24", r"^POSSÍVEL[^|]*art\. 10"), RX("com24", "^prejudicada")], ficha=ficha_sexo(k, "01/06/2004", "F", ini))

k = 6033
P = anos(4); c = 200; ini = ini_para(R25, c)
assert fr(P, 1, 8) <= c < fr(P, 1, 6)
novo(k, "Indulto 2025, art. 10, III, c: mulher de 20 anos com 1/8",
     "Indulto especial das mulheres presas (Decreto 12.790/2025, art. 10): fração de 1/8",
     "Indulto 2025 POSSÍVEL pelo art. 10, III, c (o art. 9º, I não)",
     f"Mulher (ficha: sexo F), nascida em 01/03/2005 (20 anos em 25/12/2025), presa, CP art. 297, 4a = {P} dias. Cumprido {c}. "
     f"Art. 10, III, c (2025): 1/8 = {fr(P,1,8)} - atendido. Art. 9º, I: 1/5 = {fr(P,1,5)} - não.",
     rspe(k, [t297(k, 0, P, "01/03/2024")], [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini), nasc="01/03/2005"),
     [RX("ind25", r"^POSSÍVEL[^|]*art\. 10")], ficha=ficha_sexo(k, "01/03/2005", "F", ini))

# =====================================================================================================================
# VEDAÇÕES (art. 1º)
# =====================================================================================================================
k = 6034
P = anos(12); ini = D("01/03/2016")
novo(k, "Indulto 2024 e 2025: homicídio qualificado (hediondo) vedado",
     "Vedação do art. 1º, I (crime hediondo) para indulto e comutação",
     "Indulto VEDADO e comutação VEDADA em 2024 e 2025",
     f"Homicídio qualificado (CP, art. 121, § 2º), hediondo (Lei 8.072, art. 1º, I). Pena 12a, preso desde {F(ini)}. Decretos 2024/2025, art. 1º, I.",
     rspe(k, [crime(proc(k), "ART 121: Homicídio", P, "01/10/2015", tipo="§ 2º: homicídio qualificado, Reclusão: 12 a 30 anos", vga="S", morte="S")],
          [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [RX("ind24", "^VEDADO"), RX("com24", "^VEDADA"), RX("ind25", "^VEDADO"), RX("com25", "^VEDADA")])

k = 6035
P = anos(7); ini = D("01/12/2021")
novo(k, "Tráfico (art. 33, caput): excluído em 2022, vedado em 2024 e 2025",
     "Tráfico de drogas do caput: exclusão do art. 7º, VI (2022) e vedação do art. 1º, XVIII (2024 e 2025)",
     "Decreto 2022: excluído (art. 7º); 2024 e 2025: indulto VEDADO e comutação VEDADA",
     f"Tráfico (Lei 11.343, art. 33, caput), 7a, fato 10/03/2021, sentença e trânsito em 2021, preso desde {F(ini)}. Decreto 11.302/2022, art. 7º, VI; "
     "Decretos 12.338/2024 e 12.790/2025, art. 1º, XVIII.",
     rspe(k, [crime(proc(k), "ART 33: Tráfico de drogas", P, "10/03/2021", lei=DROGAS, tipo="CAPUT: Importar, exportar, remeter, preparar, Reclusão: 5 a 15 anos E Multa")],
          [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [RX("ind22", "^excluído"), RX("ind24", "^VEDADO"), RX("com24", "^VEDADA"), RX("ind25", "^VEDADO")])

k = 6036
P = anos(3, 4); ini = D("01/11/2024"); c25 = dd(ini, R25)
novo(k, "Indulto 2025: tráfico privilegiado (§ 4º) não é impeditivo",
     "Tráfico privilegiado fora do rol do art. 1º, XVIII (só caput e § 1º)",
     "Indulto 2025 POSSÍVEL pelo art. 9º, I e II; rótulo de crime impeditivo 'Não'",
     f"Tráfico privilegiado (Lei 11.343, art. 33, § 4º), 3a4m = {P} dias, primário. Preso desde {F(ini)}: {c25} dias até 25/12/2025. "
     f"I: 1/5 = {fr(P,1,5)}; II: 1/3 = {fr(P,1,3)} - atendidos. Art. 1º, XVIII só veda o caput e o § 1º.",
     rspe(k, [crime(proc(k), "ART 33: Tráfico de drogas", P, "01/02/2024", lei=DROGAS, tipo="§ 4º: tráfico privilegiado, Reclusão: 5 a 15 anos E Multa",
                    sentenca="19/08/2024")], [p_def(ini, k)], [reg("Semiaberto - Regime Inicial", ini)], ini=F(ini), regime="Semiaberto - ATIVO"),
     [POS("ind25", ["I", "II"]), C("imp", "nao_contem", "Sim")])

k = 6037
P = anos(6); ini = D("01/06/2022")
novo(k, "Indulto 2024 e 2025: organização criminosa (Lei 12.850) vedada",
     "Vedação do art. 1º, IV (Lei 12.850/2013)",
     "Indulto VEDADO e comutação VEDADA em 2024 e 2025",
     f"Integrar organização criminosa (Lei 12.850, art. 2º), 6a, preso desde {F(ini)} (mais de 1/5 cumprido). Decretos 2024/2025, art. 1º, IV.",
     rspe(k, [crime(proc(k), "ART 2º - Promover, constituir, financiar ou integrar organização criminosa", P, "01/01/2022", lei="12850/13 - Organização Criminosa",
                    tipo="CAPUT: Promover, constituir, financiar ou integrar organização criminosa, Reclusão: 3 a 8 anos E Multa")],
          [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [RX("ind24", "^VEDADO"), RX("com24", "^VEDADA"), RX("ind25", "^VEDADO"), RX("com25", "^VEDADA")])

k = 6038
P = anos(6); c = 600; ini = ini_para(R24, c)
novo(k, "Comando de organização criminosa: 2024 veda só o indulto; 2025 veda indulto e comutação",
     "Art. 1º, § 3º, I: liderança de facção (2024: só o indulto coletivo; 2025: indulto e comutação)",
     "2024: indulto VEDADO e comutação POSSÍVEL (art. 13); 2025: indulto VEDADO e comutação VEDADA",
     f"CP, art. 297, 6a = {P} dias, com a marca de comando de organização criminosa. Cumprido até 25/12/2024: {c} (I: 1/5 = {fr(P,1,5)}; comutação 1/5 atendida). "
     "Decreto 12.338/2024, art. 1º, § 3º ('O indulto coletivo ... não alcança'); Decreto 12.790/2025, art. 1º, § 3º ('O indulto e a comutação ... não alcançam').",
     rspe(k, [t297(k, 0, P, "01/03/2023", orcrim="S")], [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [RX("ind24", "^VEDADO"), RX("com24", r"^POSSÍVEL[^|]*art\. 13"), RX("ind25", "^VEDADO"), RX("com25", "^VEDADA")])

k = 6039
P = anos(4, 6); ini = D("01/03/2024")
novo(k, "Indulto 2025: peculato com pena acima de 4 anos vedado",
     "Vedação do art. 1º, XII (CP, arts. 312 a 319 e 333) com pena aplicada superior a 4 anos",
     "Indulto 2025 VEDADO e comutação VEDADA",
     f"Peculato (CP, art. 312), 4a6m (> 4 anos), preso desde {F(ini)} ({dd(ini,R25)} dias em 25/12/2025, mais de 1/5). Decreto 12.790/2025, art. 1º, XII.",
     rspe(k, [crime(proc(k), "ART 312: Peculato", P, "01/06/2023", tipo="CAPUT: Apropriar-se o funcionário público de dinheiro, Reclusão: 2 a 12 anos E Multa")],
          [p_def(ini, k)], [reg("Semiaberto - Regime Inicial", ini)], ini=F(ini), regime="Semiaberto - ATIVO"),
     [RX("ind25", "^VEDADO"), RX("com25", "^VEDADA")])

k = 6041
P = anos(4); c = 300; ini = ini_para(R25, c)
assert c >= fr(P, 1, 5)
novo(k, "Indulto 2025: lavagem com pena de exatamente 4 anos não é vedada",
     "Exceção do art. 1º, III (lavagem com pena aplicada não superior a 4 anos), no limite",
     "Indulto 2025 POSSÍVEL pelo art. 9º, I",
     f"Lavagem de dinheiro (Lei 9.613, art. 1º), pena aplicada 4a = {P} dias (não superior a 4 anos: fora da vedação). Primário. Cumprido {c}; I: 1/5 = {fr(P,1,5)}.",
     rspe(k, [crime(proc(k), "ART 1º - Ocultar ou dissimular a natureza, origem de bens", P, "01/03/2024", lei="9613/98 - Lavagem de Dinheiro",
                    tipo="CAPUT: Ocultar ou dissimular a natureza, origem, localização, Reclusão: 3 a 10 anos E Multa")],
          [p_def(ini, k)], [reg("Semiaberto - Regime Inicial", ini)], ini=F(ini), regime="Semiaberto - ATIVO"),
     [POS("ind25", ["I"])])

k = 6042
P = anos(3); c = 300; ini = ini_para(R25, c)
novo(k, "Indulto 2025: crime ambiental (Lei 9.605) vedado qualquer que seja a pena",
     "Vedação do art. 1º, XIV (Lei 9.605/1998)",
     "Indulto 2025 VEDADO e comutação VEDADA",
     f"Poluição (Lei 9.605, art. 54), 3a, cumprido {c} dias (mais de 1/5 e de 1/3). Decreto 12.790/2025, art. 1º, XIV, sem exceção de pena.",
     rspe(k, [crime(proc(k), "ART 54 - Causar poluição", P, "01/03/2024", lei="9605/98 - Crimes Ambientais",
                    tipo="CAPUT: Causar poluição de qualquer natureza, Reclusão: 1 a 4 anos E Multa")],
          [p_def(ini, k)], [reg("Semiaberto - Regime Inicial", ini)], ini=F(ini), regime="Semiaberto - ATIVO"),
     [RX("ind25", "^VEDADO"), RX("com25", "^VEDADA")])

k = 6043
P = anos(2); c = 200; ini = ini_para(R25, c)
novo(k, "Indulto 2025: descumprimento de medida protetiva (Lei 11.340) vedado",
     "Vedação do art. 1º, XVII (crimes da Lei 11.340/2006)",
     "Indulto 2025 VEDADO e comutação VEDADA",
     f"Descumprimento de medida protetiva de urgência (Lei 11.340, art. 24-A), 2a, cumprido {c} dias (mais de 1/5). Decreto 12.790/2025, art. 1º, XVII.",
     rspe(k, [crime(proc(k), "ART 24-A - Descumprir decisão judicial que defere medidas protetivas", P, "01/03/2024", lei="11340/06 - Lei Maria da Penha",
                    tipo="CAPUT: Descumprir decisão judicial que defere medidas protetivas de urgência, Detenção: 3 meses a 2 anos")],
          [p_def(ini, k)], [reg("Semiaberto - Regime Inicial", ini)], ini=F(ini), regime="Semiaberto - ATIVO"),
     [RX("ind25", "^VEDADO"), RX("com25", "^VEDADA")])

# =====================================================================================================================
# CONCURSO COM CRIME IMPEDITIVO (art. 7º, parágrafo único)
# =====================================================================================================================
k = 6044
Pt, Pp = anos(6), anos(2); ini = D("01/03/2021"); c24, c25 = dd(ini, R24), dd(ini, R25); dois = fr(Pt, 2, 3)
assert c24 < dois <= c25
sobra = c25 - dois
assert sobra >= fr(Pp, 1, 3)
novo(k, "Concurso tráfico + porte: 2024 vedado (faltam os 2/3); 2025 possível só para o porte",
     "Regra dos 2/3 do crime impeditivo (art. 7º, p. ú.) antes e depois de cumpridos",
     "2024: indulto VEDADO e comutação VEDADA (faltam %d dias para os 2/3 do tráfico); 2025: indulto POSSÍVEL pelos incisos I e II quanto ao porte" % (dois - c24),
     f"Tráfico (art. 33, caput) 6a = {Pt} dias + porte (Lei 10.826, art. 14) 2a = {Pp}, mesmo fato (01/02/2021), primário, preso desde {F(ini)}. "
     f"2/3 do tráfico = {dois}. Em 25/12/2024: {c24} - faltam {dois - c24}. Em 25/12/2025: {c25}; sobram {sobra} para o porte: I 1/5 = {fr(Pp,1,5)}, "
     f"II 1/3 = {fr(Pp,1,3)} - atendidos. Soma total 8a: dentro do teto do I.",
     rspe(k, [crime(proc(k, 0), "ART 33: Tráfico de drogas", Pt, "01/02/2021", lei=DROGAS, tipo="CAPUT: Importar, exportar, remeter, preparar, Reclusão: 5 a 15 anos E Multa",
                    sentenca="01/08/2021"), t14(k, 1, Pp, "01/02/2021", sentenca="01/08/2021")],
          [prisao(F(ini), proc(k, 0) + ", " + proc(k, 1))], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [RX("ind24", "^VEDADO"), RX("com24", "^VEDADA"), POS("ind25", ["I", "II"])])

k = 6045
Pp, Pt = anos(3), anos(5); ini, ft = D("01/03/2020"), D("10/07/2022"); dois = fr(Pt, 2, 3)
pos24, pos25, c25 = dd(ft, R24), dd(ft, R25), dd(ini, R25)
assert dd(ini, R24) >= dois > pos24 and pos25 >= dois
porte = c25 - dois
assert porte >= fr(Pp, 1, 3) and porte < Pp
novo(k, "Concurso: só o tempo posterior ao fato do tráfico conta para os 2/3",
     "Tempo anterior ao fato do crime impeditivo não se imputa a ele (2/3 contados do fato)",
     "2024: indulto VEDADO (do fato do tráfico até 25/12/2024 só %d dias, faltam %d para os 2/3, embora o total cumprido passe dos 2/3); "
     "2025: indulto POSSÍVEL pelo art. 9º, I quanto ao porte" % (pos24, dois - pos24),
     f"Porte (Lei 10.826, art. 14) 3a = {Pp}, preso desde {F(ini)}; tráfico (caput) 5a = {Pt} praticado em {F(ft)} na prisão. Sem reincidência (o porte transitou "
     f"depois do fato do tráfico). 2/3 do tráfico = {dois}. 2024: total {dd(ini,R24)}, mas do fato em diante só {pos24}. 2025: do fato {pos25} >= {dois}; ao porte ficam "
     f"{c25} - {dois} = {porte} dias: I (1/5 = {fr(Pp,1,5)}) e II (1/3 = {fr(Pp,1,3)}) atendidos. Pena só se cumpre por crime já praticado (LEP, art. 111, p. ú.).",
     rspe(k, [t14(k, 0, Pp, "01/01/2020", sentenca="15/08/2020", transito="20/08/2022"),
              crime(proc(k, 1), "ART 33: Tráfico de drogas", Pt, F(ft), lei=DROGAS, tipo="CAPUT: Importar, exportar, remeter, preparar, Reclusão: 5 a 15 anos E Multa",
                    sentenca="10/02/2023")],
          [prisao(F(ini), proc(k, 0))], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [RX("ind24", "^VEDADO"), POS("ind25", ["I"])])

# =====================================================================================================================
# REINCIDÊNCIA PELAS DATAS
# =====================================================================================================================
k = 6046
P = anos(5); c = 451; ini = ini_para(R25, c)
assert fr(P, 1, 5) <= c < fr(P, 1, 3) and c < fr(P, 1, 4)
novo(k, "Indulto 2025: RSPE não marca reincidência, mas o 2º crime é posterior ao trânsito do 1º",
     "Reincidência pelas datas (CP, arts. 63 e 64, I) com o RSPE marcando primário",
     "Não é 'possível' com segurança: como reincidente o inciso I exige 1/3 (não atingido) e a comutação 1/4 (não atingida); "
     "o resultado não pode afirmar o indulto pelo I como primário",
     f"CP, art. 297: crime A 2a (fato 01/03/2019, trânsito 01/03/2020) e crime B 3a (fato 01/06/2021), nenhum marcado reincidente. B foi praticado depois do "
     f"trânsito de A: reincidente (CP, art. 63; Decreto 12.790/2025, art. 14). Pena {P}, cumprido {c}. Primário: I 1/5 = {fr(P,1,5)} (atingiria). "
     f"Reincidente: I 1/3 = {fr(P,1,3)}, comutação 1/4 = {fr(P,1,4)} - não atingidos.",
     rspe(k, [t297(k, 0, anos(2), "01/03/2019", sentenca="01/09/2019", transito="01/03/2020"), t297(k, 1, anos(3), "01/06/2021", sentenca="01/12/2021")],
          [p_def(ini, k, 1)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [NAO_POS("ind25"), C("ind25", "contem", "reincid"), NAO_POS("com25")])

# =====================================================================================================================
# FALTA GRAVE (art. 6º)
# =====================================================================================================================
FALTA = "HOMOLOGAÇÃO DE FALTA GRAVE"

k = 6047
P = anos(5); ini = D("01/01/2023"); c24, c25 = dd(ini, R24), dd(ini, R25)
assert c25 >= fr(P, 1, 3)
novo(k, "Falta grave homologada na janela de 2024: não cabe em 2024; cabe em 2025",
     "Art. 6º: falta grave com sanção reconhecida nos 12 meses anteriores a 25/12/2024; fora da janela de 2025",
     "2024: indulto e comutação NÃO CABEM (art. 6º); 2025: indulto POSSÍVEL pelos incisos I e II",
     f"CP, art. 297, 5a = {P}, preso desde {F(ini)}. Falta grave com fato em 15/08/2024, homologada em 20/10/2024: dentro de 25/12/2023 a 23/12/2024. "
     f"2025: janela de 25/12/2024 a 23/12/2025 - a falta fica fora. Cumprido em 2025: {c25}; I 1/5 = {fr(P,1,5)}, II 1/3 = {fr(P,1,3)}.",
     rspe(k, [t297(k, 0, P, "01/06/2022", sentenca="01/09/2022")], [p_def(ini, k)],
          [reg("Fechado - Regime Inicial", ini), inc(FALTA, "15/08/2024", "20/10/2024", "15/08/2024")], ini=F(ini)),
     [RX("ind24", "^NÃO CABE"), RX("com24", "^NÃO CABE"), POS("ind25", ["I", "II"])])

k = 6048
P = anos(5); ini = D("01/01/2024"); c25 = dd(ini, R25)
novo(k, "Indulto 2025: falta grave pendente de homologação na janela",
     "Art. 6º: falta da janela ainda não reconhecida em juízo (só impede se a sanção for reconhecida)",
     "Indulto 2025 não é 'cabe' firme nem 'não cabe': fica A VERIFICAR (ou 'possível com falta a verificar', em âmbar)",
     f"CP, art. 297, 5a, preso desde {F(ini)}: {c25} dias em 25/12/2025 (I: 1/5 = {fr(P,1,5)}). Falta com fato em 10/05/2025 pendente de homologação. "
     "O art. 6º condiciona a declaração à inexistência de sanção reconhecida em juízo; a homologação posterior impediria (STJ, Tema 1195).",
     rspe(k, [t297(k, 0, P, "01/06/2023")], [p_def(ini, k)],
          [reg("Fechado - Regime Inicial", ini), inc(FALTA, "10/05/2025", "", "10/05/2025", sit="PENDENTE")], ini=F(ini)),
     [RX("ind25", r"^A VERIFICAR|falta a verificar"), C("i25", "nao_contem", "Sim")])

k = 6049
P = anos(5); ini = D("01/01/2024"); c25 = dd(ini, R25)
novo(k, "Indulto 2025: falta grave praticada depois da publicação do decreto não impede",
     "Art. 6º, parágrafo único: falta com fato em 24/12/2025 (publicação em 23/12/2025)",
     "Indulto 2025 POSSÍVEL pelo art. 9º, I, sem ressalva de falta",
     f"CP, art. 297, 5a, preso desde {F(ini)}: {c25} dias (I: 1/5 = {fr(P,1,5)}). Falta com fato em 24/12/2025, homologada em 10/02/2026: posterior à "
     "publicação (23/12/2025) - não suspende nem impede (art. 6º, p. ú.).",
     rspe(k, [t297(k, 0, P, "01/06/2023")], [p_def(ini, k)],
          [reg("Fechado - Regime Inicial", ini), inc(FALTA, "24/12/2025", "10/02/2026", "24/12/2025")], ini=F(ini)),
     [POS("ind25", ["I"]), C("ind25", "nao_contem", "falta a verificar")])

k = 6050
P = anos(5); ini, fu, rc_ = D("01/01/2023"), D("01/06/2024"), D("01/08/2024")
it = (rc_ - fu).days - 1; c24 = dd(ini, fu) + dd(rc_, R24)
assert c24 >= fr(P, 1, 5)
novo(k, "Indulto 2024: fuga na janela sem homologação",
     "Art. 6º: fuga só registrada como evento, sem sanção reconhecida em juízo",
     "Indulto 2024 A VERIFICAR (ou 'possível com falta a verificar'): a fuga só impede se a falta for reconhecida em juízo; não é 'NÃO CABE'",
     f"CP, art. 297, 5a, preso desde {F(ini)}, fuga em {F(fu)}, recaptura em {F(rc_)} ({it} dias fora). Cumprido até 25/12/2024: {c24} (I: 1/5 = {fr(P,1,5)}). "
     "Fuga é falta grave em tese (LEP, art. 50, II), sem homologação registrada.",
     rspe(k, [t297(k, 0, P, "01/06/2022", sentenca="01/09/2022")], [p_def(ini, k), interr(F(fu), "FUGA"), p_def(rc_, k, motivo="RECAPTURA/REINÍCIO DE CUMPRIMENTO")],
          [reg("Fechado - Regime Inicial", ini)], ini=F(ini), interrompidos=it),
     [RX("ind24", r"^A VERIFICAR|falta a verificar"), C("ind24", "regex", r"^(?!NÃO CABE)")])

k = 6051
P = anos(5); ini, fu, rc_ = D("01/01/2024"), D("01/04/2025"), D("01/05/2025")
it = (rc_ - fu).days - 1; c25 = dd(ini, fu) + dd(rc_, R25)
novo(k, "Indulto 2025: fuga na janela homologada só em 2026 impede",
     "Art. 6º com a homologação posterior ao decreto (STJ, Tema 1195)",
     "Indulto e comutação 2025 NÃO CABEM (art. 6º)",
     f"CP, art. 297, 5a, preso desde {F(ini)}; fuga em {F(fu)} (dentro de 25/12/2024 a 23/12/2025), recaptura em {F(rc_)}; falta homologada em 15/03/2026. "
     f"Cumprido {c25}: atenderia o I, mas a sanção reconhecida (ainda que depois) por falta cometida na janela impede (STJ, Tema 1195).",
     rspe(k, [t297(k, 0, P, "01/06/2023")], [p_def(ini, k), interr(F(fu), "FUGA"), p_def(rc_, k, motivo="RECAPTURA/REINÍCIO DE CUMPRIMENTO")],
          [reg("Fechado - Regime Inicial", ini), inc(FALTA, "01/04/2025", "15/03/2026", "01/04/2025")], ini=F(ini), interrompidos=it),
     [RX("ind25", "^NÃO CABE"), RX("com25", "^NÃO CABE")])

# =====================================================================================================================
# PRISÃO CAUTELAR COMO PENA CUMPRIDA (art. 5º)
# =====================================================================================================================
k = 6054
P = anos(3); a, b, d2 = D("01/02/2024"), D("30/06/2024"), D("01/10/2025")
it = (d2 - b).days - 1; c25 = dd(a, b) + dd(d2, R25)
assert fr(P, 1, 5) <= c25 < fr(P, 1, 3) and dd(d2, R25) < fr(P, 1, 5)
novo(k, "Indulto 2025: preventiva anterior soma ao cumprimento atual (art. 5º)",
     "Art. 5º: prisão cautelar computada como pena cumprida para o requisito temporal",
     "Indulto 2025 POSSÍVEL pelo art. 9º, I (com a preventiva); o II não",
     f"CP, art. 297, 3a = {P}. Preventiva de {F(a)} a {F(b)} ({dd(a,b)} dias), liberdade provisória; prisão definitiva desde {F(d2)} ({dd(d2,R25)} dias até 25/12/2025). "
     f"Total {c25} >= 1/5 ({fr(P,1,5)}); sem a cautelar, não atingiria. II: 1/3 = {fr(P,1,3)} - não.",
     rspe(k, [t297(k, 0, P, "01/12/2023", sentenca="01/03/2025", transito="01/05/2025")],
          [prisao(F(a), proc(k), "PRISÃO PREVENTIVA"), interr(F(b), "LIBERDADE PROVISÓRIA"), p_def(d2, k)],
          [reg("Fechado - Regime Inicial", d2)], ini=F(a), interrompidos=it),
     [POS("ind25", ["I"], ["II"])])

k = 6055
P = anos(2); a, b = D("01/03/2024"), D("30/07/2024"); cc = dd(a, b); it = (GER - b).days
assert cc >= fr(P, 1, 5)
novo(k, "Indulto 2024: só prisão em flagrante (152 dias), solto na data do decreto - art. 5º",
     "Art. 5º do Decreto 12.338/2024 para quem teve só prisão cautelar e não estava preso em 25/12/2024",
     "Pelo texto do art. 5º, os 152 dias de prisão cautelar contam como pena cumprida: 1/5 (146) atingido - indulto 2024 POSSÍVEL pelo art. 9º, I "
     "(tese: parte da jurisprudência exige o início do cumprimento)",
     f"CP, art. 297, 2a = {P}. Flagrante em {F(a)}, liberdade provisória em {F(b)}: {cc} dias. Sentença 01/08/2024, trânsito 01/10/2024, sem prisão depois. "
     f"Art. 5º: 'deverá ser computada como pena cumprida ... o período cumprido em prisão cautelar'. I: 1/5 = {fr(P,1,5)} - atendido. O decreto não exige "
     "estar preso na data (art. 9º: 'tenham cumprido, até 25 de dezembro').",
     rspe(k, [t297(k, 0, P, "15/02/2024", sentenca="01/08/2024", transito="01/10/2024", regime="Semiaberto")],
          [prisao(F(a), proc(k), "PRISÃO EM FLAGRANTE"), interr(F(b), "LIBERDADE PROVISÓRIA")],
          [reg("Semiaberto - Regime Inicial", D("01/10/2024"))], ini=F(a), interrompidos=it, regime="Semiaberto - ATIVO"),
     [dict(POS("ind24", ["I"], nota="Art. 5º do decreto conta a prisão cautelar sem exigir custódia na data; o programa exige início do cumprimento "
                                    "(STJ, AgRg no HC 1.042.931) - tese discutível."), decisao=True)])

# =====================================================================================================================
# COMUTAÇÃO
# =====================================================================================================================
k = 6056
P = anos(7); c = 1500; ini = ini_para(R25, c); red = c // 5; novo_rem = (P - c) - red
assert c > P - c
novo(k, "Comutação 2025 calculada sobre o cumprido (art. 13, § 1º)",
     "Base de cálculo da comutação: o cumprido, quando maior que o remanescente",
     "Comutação 2025 cabível (art. 13), redução de 1/5 do cumprido = %d dias (%s); remanescente passa de %s para %s" % (red, ext(red), ext(P - c), ext(novo_rem)),
     f"Roubo 7a = {P}, primário, cumprido {c} até 25/12/2025; remanescente {P - c} < cumprido: base = cumprido (art. 13, § 1º). 1/5 de {c} = {red}; "
     f"novo remanescente {P - c} - {red} = {novo_rem}. Indulto: III não (pena > 4); XII/XIII só a verificar.",
     rspe(k, [roubo(k, 0, P, "01/06/2021")], [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [RX("com25", r"art\. 13"), C("cdet25", "contem", [ext(red), ext(novo_rem)])])

k = 6057
ini = D("01/01/2022"); Pa, Pb, com = anos(6), anos(20), 300; P = Pa + Pb - com; c25 = dd(ini, R25)
assert c25 < fr(P, 1, 5)
novo(k, "Comutação 2025 com comutação anterior: requisito temporal dispensado (art. 13, § 2º)",
     "Art. 13, § 2º: quem já teve a pena comutada não precisa de novo requisito temporal",
     "Comutação 2025 POSSÍVEL (requisito temporal dispensado pela comutação do Decreto 11.846/2023 concedida em 10/04/2024)",
     f"Roubo 6a + roubo majorado 20a, menos 300 dias da comutação de 2023 (concedida em 10/04/2024): pena total {P} dias. Cumprido em 25/12/2025: {c25}, "
     f"abaixo de 1/5 ({fr(P,1,5)}), mas o § 2º dispensa novo requisito temporal. Indulto: violência, pena acima de 12 anos - não atinge.",
     rspe(k, [roubo(k, 0, Pa, "01/06/2021"), roubo(k, 1, Pb, "10/06/2021", maj=True, sentenca="10/06/2024")], [p_def(ini, k)],
          [reg("Fechado - Regime Inicial", ini), inc("COMUTAÇÃO", "Decreto 11.846/2023", "10/04/2024", "25/12/2023", procs=proc(k, 0))], ini=F(ini), pena=P),
     [RX("com25", r"^POSSÍVEL[^|]*art\. 13"), C("cdet25", "contem", "§ 2º")])

# =====================================================================================================================
# PENA CUMPRIDA E EXECUÇÃO UNIFICADA
# =====================================================================================================================
k = 6058
P = anos(1); ini = D("01/03/2023"); fim = ini + timedelta(days=P - 1)
novo(k, "Pena integralmente cumprida antes de 25/12/2024: extinção, não indulto",
     "Pena considerada já cumprida na data do decreto (LEP, art. 66, II)",
     "Indulto 2024 não é 'possível': sem pena a indultar - pedir a extinção pelo cumprimento; comutação sem objeto",
     f"CP, art. 297, 1a = {P} dias, preso de {F(ini)} a {F(fim)} (término do SEEU). Em 25/12/2024 não havia pena remanescente: o caminho é a extinção "
     "pelo cumprimento (LEP, art. 66, II), não o indulto nem a comutação.",
     rspe(k, [t297(k, 0, P, "01/06/2022", sentenca="18/12/2022")], [p_def(ini, k), interr(F(fim), "CUMPRIMENTO DA PENA")],
          [reg("Fechado - Regime Inicial", ini)], ini=F(ini), term=F(fim)),
     [RX("ind24", r"^não se aplica: sem pena remanescente"), NAO_POS("com24"),
      C("ind24", "contem", "extinção", nota="O resultado não orienta pedir a extinção pelo cumprimento (LEP, art. 66, II)."),
      C("ind25", "nao_contem", "falta a verificar", nota="A soltura por cumprimento (28/02/2024) não é fuga e fica fora da janela de 2025 (25/12/2024 a 23/12/2025).")])

k = 6059
ini = D("01/02/2023"); c24 = dd(ini, R24)
novo(k, "Execução unificada: pena alcançada coberta pelo tempo, mas sem sugerir extinção isolada",
     "Execução unificada com outra pena (fato posterior ao decreto) em cumprimento",
     "Indulto 2024 POSSÍVEL (pena de 2022 alcançada), sem 'pedir a extinção pelo cumprimento' (política: não se sugere extinção de pena isolada na execução unificada)",
     f"CP, art. 297: crime A 1a (fato 2022) e crime B 4a (fato 01/03/2025, fora do Decreto 12.338/2024). Preso desde {F(ini)}: {c24} dias em 25/12/2024, mais que a "
     "pena de A; como a execução é unificada (LEP, art. 111) e B segue em cumprimento, fica o indulto da pena alcançada (decisão do usuário).",
     rspe(k, [t297(k, 0, anos(1), "01/06/2022", sentenca="18/12/2022"), t297(k, 1, anos(4), "01/03/2025", sentenca="01/09/2025")],
          [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [RX("ind24", "^POSSÍVEL"), C("ind24", "nao_contem", "extinção pelo cumprimento")])

# =====================================================================================================================
# DECRETO 11.302/2022
# =====================================================================================================================
k = 6060
P = anos(1, 8); ini = D("01/06/2026")
novo(k, "Decreto 2022: tráfico privilegiado e o art. 5º (pena máxima em abstrato)",
     "Tráfico privilegiado no Decreto 11.302/2022 (art. 7º, VI ressalva o § 4º, mas o art. 5º exige pena máxima até 5 anos)",
     "Pelo texto: o art. 7º, VI só tira o § 4º das exclusões; a pena máxima do tráfico privilegiado (15 anos reduzidos de 1/6 = 12a6m) passa de 5 anos, "
     "então o art. 5º não alcança - indulto 2022 não é 'possível' (tese contrária: STJ, 6ª Turma)",
     "Tráfico privilegiado (Lei 11.343, art. 33, § 4º), 1a8m, fato 01/03/2021, sentença 01/08/2022, trânsito 01/10/2022, início do cumprimento em 01/06/2026. Decreto 11.302/2022, art. 5º "
     "(pena máxima em abstrato não superior a 5 anos) e art. 7º, VI.",
     rspe(k, [crime(proc(k), "ART 33: Tráfico de drogas", P, "01/03/2021", lei=DROGAS, tipo="§ 4º: tráfico privilegiado, Reclusão: 5 a 15 anos E Multa",
                    sentenca="01/08/2022", transito="01/10/2022")], [p_def(ini, k)], [reg("Semiaberto - Regime Inicial", ini)], ini=F(ini), regime="Semiaberto - ATIVO"),
     [dict(NAO_POS("ind22", nota="Leitura literal do art. 5º; o STJ (6ª Turma, AgRg no HC 818.978) admite o indulto do privilegiado pelo art. 5º c/c art. 7º, VI."),
           decisao=True)])

k = 6061
P = anos(2); ini = D("15/10/2022")
novo(k, "Decreto 2022, art. 5º: furto simples (máximo 4 anos); falta grave não afasta",
     "Art. 5º (pena máxima em abstrato até 5 anos, sem tempo cumprido) e ausência de requisito disciplinar no Decreto 2022",
     "Indulto 2022 POSSÍVEL pelo art. 5º, mesmo com falta grave homologada em 2022",
     "Três furtos simples (CP, art. 155, caput: 1 a 4 anos), 2a cada, fato 01/03/2021, sentença 01/08/2022, trânsito 01/10/2022. Art. 5º não exige tempo cumprido. "
     "Falta grave com fato em 01/11/2022, homologada em 01/12/2022: o Decreto 11.302/2022 não tem requisito disciplinar.",
     rspe(k, [furto(k, i, P, "01/03/2021", sentenca="01/08/2022", transito="01/10/2022") for i in range(3)], [p_def(ini, k)],
          [reg("Fechado - Regime Inicial", ini), inc(FALTA, "01/11/2022", "01/12/2022", "01/11/2022")], ini=F(ini)),
     [RX("ind22", r"^POSSÍVEL[^|]*art\. 5º")])

k = 6062
ini = D("15/10/2022")
novo(k, "Decreto 2022, art. 5º crime a crime: furto alcançado, receptação qualificada não",
     "Art. 5º, parágrafo único: pena máxima aferida em cada crime (indulto parcial)",
     "Indulto 2022 POSSÍVEL pelo art. 5º só quanto ao furto (máximo 4 anos); a receptação qualificada (máximo 8 anos) não é alcançada e não impede",
     "Furto simples (1 a 4 anos), 2a, e receptação qualificada (CP, art. 180, § 1º: 3 a 8 anos), 4a, ambos de 2021, sentenças de 2022. "
     "Art. 5º, p. ú.: em concurso, a pena máxima de cada infração. Receptação não é crime do art. 7º (sem o art. 11, p. ú.).",
     rspe(k, [furto(k, 0, anos(2), "01/03/2021", sentenca="01/08/2022", transito="01/10/2022"),
              crime(proc(k, 1), "ART 180: Receptação", anos(4), "01/03/2021", tipo="§ 1º: receptação qualificada, Reclusão: 3 a 8 anos E Multa",
                    sentenca="01/08/2022", transito="01/10/2022")], [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [RX("ind22", r"^POSSÍVEL[^|]*art\. 5º"), RX("det22", r"✗[^\n]*180")])

k = 6063
P = anos(8); ini = D("01/12/2019"); c22 = dd(ini, R22)
assert c22 >= P / 3
novo(k, "Decreto 2022, art. 4º: 72 anos com 1/3 cumprido",
     "Art. 4º do Decreto 11.302/2022 (maiores de 70 anos, 1/3 da pena)",
     "Indulto 2022 POSSÍVEL pelo art. 4º (o art. 5º não: máximo do art. 297 é 6 anos)",
     f"Duas condenações do CP, art. 297 (2 a 6 anos), 6a + 2a = {P} dias, nascido em 01/01/1950 (72 anos em 25/12/2022). Preso desde {F(ini)}: {c22} dias; 1/3 = {P // 3} - atendido.",
     rspe(k, [t297(k, 0, anos(6), "01/11/2019", sentenca="01/09/2020", transito="01/11/2020"), t297(k, 1, anos(2), "01/11/2019", sentenca="01/09/2020", transito="01/11/2020")],
          [prisao(F(ini), proc(k, 0) + ", " + proc(k, 1))], [reg("Fechado - Regime Inicial", ini)], ini=F(ini), nasc="01/01/1950"),
     [RX("ind22", r"^POSSÍVEL[^|]*art\. 4º")])

k = 6065
ini = D("01/01/2020"); c22 = dd(ini, R22); Pr = anos(7)
assert c22 < Pr
novo(k, "Decreto 2022: furto em concurso com roubo - só depois de cumprida a pena inteira do roubo",
     "Art. 7º, II (violência) e art. 11, parágrafo único (pena integral do crime impeditivo)",
     "Indulto 2022 não atinge: o roubo é excluído e o furto só seria indultado depois de cumprida toda a pena do roubo",
     f"Furto simples 1a e roubo 7a = {Pr} dias, ambos de 2019, preso desde {F(ini)}: {c22} dias em 25/12/2022, menos que a pena do roubo. "
     "Decreto 11.302/2022, arts. 7º, II, e 11, p. ú.",
     rspe(k, [furto(k, 0, anos(1), "01/06/2019"), roubo(k, 1, Pr, "01/06/2019")], [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [RX("ind22", "^não atinge")])

k = 6066
ini = D("01/06/2026")
novo(k, "Decreto 2022: trânsito para a acusação só depois da publicação",
     "Art. 9º do Decreto 11.302/2022: condenação sem trânsito para a acusação em 23/12/2022",
     "Indulto 2022 A VERIFICAR (controvérsia: o STJ exige o trânsito para a acusação na publicação; a leitura literal do art. 9º, p. ú., só barra recurso "
     "da acusação após o 2º grau)",
     "Furto simples (1 a 4 anos), 2a, fato 10/01/2022, sentença 10/11/2022, trânsito para a acusação e final em 15/01/2023; cumprimento iniciado em 01/06/2026. Art. 5º alcançaria o crime.",
     rspe(k, [furto(k, 0, anos(2), "10/01/2022", sentenca="10/11/2022", transito="15/01/2023")], [p_def(ini, k)],
          [reg("Semiaberto - Regime Inicial", ini)], ini=F(ini), regime="Semiaberto - ATIVO"),
     [RX("ind22", "^A VERIFICAR")])

k = 6067
ini = D("01/06/2026")
novo(k, "Decreto 2022: pena substituída por restritiva de direitos (art. 8º, I)",
     "Art. 8º, I do Decreto 11.302/2022: o indulto não se estende às penas restritivas de direitos",
     "Indulto 2022 não é 'possível': a pena era restritiva de direitos em 25/12/2022 (art. 8º, I)",
     "Furto simples, 2a, substituída por prestação de serviços (sentença 01/08/2022, trânsito 01/10/2022): em 25/12/2022 a pena era restritiva de direitos; cumprimento iniciado em 01/06/2026.",
     rspe(k, [furto(k, 0, anos(2), "01/03/2021", sentenca="01/08/2022", transito="01/10/2022", regime="Aberto",
                    pena_total_processo="2a0m0d - PENA ORIGINÁRIA - CONVERTIDA EM RESTRITIVA DE DIREITOS")],
          [ev("PRISÃO/INÍCIO DE CUMPRIMENTO", "INÍCIO DE CUMPRIMENTO - PENA RESTRITIVA DE DIREITOS", F(ini), proc(k))],
          [reg("Restritiva de Direitos - Substituição", ini)], ini=F(ini), regime="Restritiva de Direitos - ATIVO"),
     [NAO_POS("ind22")])

# =====================================================================================================================
# DECISÕES REGISTRADAS NO RSPE
# =====================================================================================================================
k = 6069
P = anos(5); ini = D("01/01/2023")
novo(k, "Indulto 2024 concedido no RSPE prevalece sobre a triagem",
     "Decisão de concessão do indulto do Decreto 12.338/2024 registrada no RSPE",
     "Indulto 2024: CONCEDIDO no RSPE; comutação 2024 prejudicada (indulto concedido)",
     f"CP, art. 297, 5a, preso desde {F(ini)} ({dd(ini,R24)} dias em 25/12/2024, 1/5 = {fr(P,1,5)}). Incidente INDULTO (Decreto 12.338/2024) CONCEDIDO em 15/04/2025.",
     rspe(k, [t297(k, 0, P, "01/06/2022", sentenca="01/09/2022")], [p_def(ini, k)],
          [reg("Fechado - Regime Inicial", ini), inc("INDULTO", "Decreto 12.338/2024", "15/04/2025", "15/04/2025")], ini=F(ini)),
     [RX("ind24", "^CONCEDIDO"), RX("com24", "prejudicada")])

k = 6070
P = anos(5); ini = D("01/01/2024")
novo(k, "Indulto 2025 indeferido no RSPE: a comutação volta a ser analisada",
     "Indeferimento do indulto do Decreto 12.790/2025 registrado; comutação não decidida",
     "Indulto 2025: INDEFERIDO no RSPE; comutação 2025 não fica prejudicada: art. 13 (1/5 atendido), a conferir o motivo do indeferimento",
     f"CP, art. 297, 5a, preso desde {F(ini)} ({dd(ini,R25)} dias em 25/12/2025; comutação 1/5 = {fr(P,1,5)}). Incidente INDULTO (Decreto 12.790/2025) NÃO CONCEDIDO em "
     "10/03/2026. Sem indulto, o art. 13, § 5º não prejudica a comutação.",
     rspe(k, [t297(k, 0, P, "01/06/2023")], [p_def(ini, k)],
          [reg("Fechado - Regime Inicial", ini), inc("INDULTO", "Decreto 12.790/2025", "10/03/2026", "10/03/2026", sit="NÃO CONCEDIDO")], ini=F(ini)),
     [RX("ind25", "^INDEFERIDO"), RX("com25", r"art\. 13"), C("com25", "regex", r"^(?!prejudicada)")])

# =====================================================================================================================
# ÂNCORA DO SEEU × EVENTOS
# =====================================================================================================================
k = 6072
P = anos(5); ini = D("01/03/2023"); ev24 = dd(ini, R24); falta_seeu = 400
assert ev24 >= fr(P, 1, 5) > ev24 - falta_seeu
novo(k, "Indulto 2024: SEEU conta 400 dias a menos do que os eventos mostram",
     "Divergência entre o cálculo do SEEU (âncora) e os eventos de custódia: favorável só pelos eventos",
     "Indulto 2024 A VERIFICAR com o inciso I (pelos eventos atende; pelo SEEU, não) - conferir o tempo cumprido",
     f"CP, art. 297, 5a = {P}. Eventos: preso desde {F(ini)} sem interrupção = {ev24} dias em 25/12/2024 (I: 1/5 = {fr(P,1,5)} atendido). O SEEU registra "
     f"{falta_seeu} dias de interrupção que os eventos não mostram: pelo cálculo dele, {ev24 - falta_seeu} dias. Dado conflitante: não se pode afirmar nem negar.",
     rspe(k, [t297(k, 0, P, "01/06/2022", sentenca="01/09/2022")], [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini), interrompidos=falta_seeu),
     [RX("ind24", r"^A VERIFICAR[^|]*\bI\b", nota="Pelos eventos o inciso I é atendido (666 dias >= 365); a comutação do mesmo decreto usa os eventos, o indulto não.")])

k = 6073
P = anos(6); c24e = 400; ini = ini_para(R24, c24e)
r_ = rspe(k, [roubo(k, 0, P, "01/06/2023")], [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini), remidos=100)
r_["saldo_remidos"] = "0 dias (0 dias remidos - 0 dias perdidos)"  # o SEEU conta 100 dias a mais, sem remição registrada
assert c24e < fr(P, 1, 5) <= c24e + 100
NOTA73 = ("Tempo sem data: o gabarito pede conferência (pode ser detração anterior ao decreto); se o programa usar só os eventos e negar, "
          "a escolha é de prudência discutível, contra o assistido.")
novo(k, "Comutação 2024: SEEU conta 100 dias a mais que os eventos, sem data (detração de outro período)",
     "Tempo a mais do SEEU, sem data, que pode ser anterior ao decreto (âncora acima dos eventos)",
     "Comutação 2024 e indulto 2024 (XII/XIII) A VERIFICAR: pelos eventos %d dias (abaixo de 1/5 = %d); com os 100 dias do SEEU, %d (atingiria). "
     "Sem a data do tempo a mais, não se pode negar nem afirmar" % (c24e, fr(P, 1, 5), c24e + 100),
     f"Roubo 6a = {P} dias, primário (sem o § 2º: o III não cabe, pena acima de 4 anos). Eventos: preso desde {F(ini)} = {c24e} dias em 25/12/2024. "
     "O cálculo do SEEU tem 100 dias a mais (término antecipado), sem remição nem evento que os date - típico de detração de prisão anterior "
     "(CP, art. 42), que contaria antes do decreto. Comutação e XII/XIII exigem 1/5 = %d." % fr(P, 1, 5),
     r_, [dict(RX("com24", "^(A VERIFICAR|POSSÍVEL)"), nota=NOTA73, decisao=True),
          dict(RX("ind24", r"^A VERIFICAR[^|]*\bXII\b"), nota=NOTA73, decisao=True)])

# =====================================================================================================================
# REMIÇÃO
# =====================================================================================================================
k = 6074
P = anos(10); req = fr(P, 1, 4); c = req - 20; ini = ini_para(R24, c)
fic = ficha_sexo(k, "01/01/1975", "M", ini)
fic["eventos"] += [{"data": "01.02.2024", "texto": "TRABALHO: Iniciou atividade laboral, no setor de trabalho HORTA, conforme documento CI 1/2024."},
                   {"data": "30.05.2024", "texto": "TRABALHO: Deixa de trabalhar, no setor de trabalho HORTA, conforme documento CI 2/2024, motivo: a pedido."},
                   {"data": "10.07.2024", "texto": "Emitido Atestado de Trabalho Prisional 7/2024. Horta - 01.02.2024 a 30.05.2024 120 dias trabalhados 40 dias remidos"}]
novo(k, "Comutação 2024 de reincidente: faltam 20 dias e há 40 dias de remição pendente (ficha)",
     "Remição de trabalho anterior ao decreto, atestada na ficha e não declarada no RSPE",
     "Comutação 2024 A VERIFICAR (remição pendente): os 40 dias de remição do trabalho de 2024 cobrem os 20 dias que faltavam - pedir a declaração da remição e a comutação",
     f"Roubo majorado 10a = {P}, reincidente. Comutação exige 1/4 = {req}; cumprido em 25/12/2024 = {c}; faltam 20. Ficha: trabalho de 01/02/2024 a 30/05/2024, "
     "atestado de 120 dias = 40 remidos (LEP, art. 126: 1 dia por 3), sem remição no RSPE. Remição é pena cumprida (LEP, art. 128; Decreto, art. 5º).",
     rspe(k, [roubo(k, 0, P, "01/01/2022", maj=True, rc="S")], [p_def(ini, k)], [reg("Fechado - Regime Inicial", ini)], ini=F(ini)),
     [RX("com24", "^A VERIFICAR")], ficha=fic)

k = 6075
P = anos(10); req = fr(P, 1, 4); c = req - 20; ini = ini_para(R24, c)
novo(k, "Comutação 2024 de reincidente: faltam 20 dias e há 40 dias de remição decidida em 2025",
     "Remição homologada depois do decreto, sem o período do trabalho identificado",
     "Comutação 2024 A VERIFICAR (remição homologada depois): se o trabalho for anterior a 25/12/2024, os 40 dias cobrem os 20 que faltavam",
     f"Roubo majorado 10a = {P}, reincidente. 1/4 = {req}; custódia até 25/12/2024 = {c} (faltam 20). Remição de 40 dias decidida em 10/03/2025, com a mesma "
     "data de referência, sem o período do trabalho. A remição é pena cumprida (LEP, art. 128): conferir o período.",
     rspe(k, [roubo(k, 0, P, "01/01/2022", maj=True, rc="S")], [p_def(ini, k)],
          [reg("Fechado - Regime Inicial", ini), inc("REMIÇÃO", "40 Dia(s) Remido(s)", "10/03/2025", "10/03/2025")], ini=F(ini), remidos=40),
     [RX("com24", "^A VERIFICAR")])


if __name__ == "__main__":
    ids = [c["id"] for c in CASOS]
    assert len(ids) == len(set(ids)) and all(6001 <= int(i[1:]) <= 6099 for i in ids)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "indulto_novos.json")
    json.dump(CASOS, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("%d casos gravados em %s" % (len(CASOS), out))
