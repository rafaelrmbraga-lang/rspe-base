"""Casos simulados da aba Auditoria (k 4001-4099). Gabarito pela lei (LEP, CP, súmulas e temas citados em cada caso) e pelas
escolhas de política do INSTRUCAO.md; o capítulo 4 do relatório só serviu como lista do que testar.
Uso: python3 gera_auditoria.py  (grava auditoria.json ao lado)."""
import os, sys, json
from datetime import timedelta
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from base_casos import (D, F, GER, CP, DROGAS, anos, crime, ev, prisao, interr, inc, REG, rspe, C, AUD, caso, proc_crim, pena_cab)

JAN_A, JAN_B = D("12/10/2026"), D("31/03/2027")
CASOS = []
_k = [4000]

# tipos penais usados (máximos reais do CP / Lei 11.343)
FURTO = ("ART 155: Furto", "CAPUT: Subtrair, para si ou para outrem, coisa alheia móvel, Reclusão: 1 a 4 anos E Multa")
FURTO_Q = ("ART 155: Furto", "§ 4º: A pena é de reclusão de dois a oito anos, e multa, se o crime é cometido:, Reclusão: 2 a 8 anos E Multa")
ESTEL = ("ART 171: Estelionato", "CAPUT: Obter, para si ou para outrem, vantagem ilícita, Reclusão: 1 a 5 anos E Multa")
ROUBO = ("ART 157: Roubo", "CAPUT: Subtrair coisa móvel alheia, mediante grave ameaça ou violência, Reclusão: 4 a 10 anos E Multa")
HOMQ = ("ART 121: Matar alguem:", "§ 2º: Se o homicídio é cometido:, Reclusão: 12 a 30 anos")
LATRO = ("ART 157: Roubo", "§ 3º: Se da violência resulta:, II - morte, Reclusão: 20 a 30 anos E Multa")
TRAF = ("ART 33: Importar, exportar, remeter, preparar, produzir", "CAPUT: tráfico de drogas, Reclusão: 5 a 15 anos E Multa")

P16, P20, P25, P30 = "16% - Art.112, I", "20% - Art.112, II", "25% - Art.112, III", "30% - Art.112, IV"
L13, L12, L23, L11 = "1/3 - Comum Primário", "1/2 - Comum Reincidente", "2/3 - Hediondo", "1/1 - Hediondo Reincidente"


def cr(k, tp, dias, fato, n=0, fp=P16, fl=L13, ano=None, **kw):
    ano = ano or D(fato).year
    return crime(proc_crim(k * 10 + n, ano), tp[0], dias, fato, tipo=tp[1], fp=fp, fl=fl, **kw)


def P(c):
    return c["processo_criminal"]


def novo(grupo, titulo, aba, situacao, esperado, conta, r, checks, ficha=None, extra=None, k=None):
    c = caso(k or r["_k"], grupo, titulo, conta, r, checks, ficha=ficha, extra=extra)
    c["rspe"].pop("_k", None)
    for x in c["extra_rspe"]:
        x.pop("_k", None)
    c.update(aba=aba, situacao=situacao, esperado=esperado)
    CASOS.append(c)
    # aviso de prazo na janela 12/10/2026-31/03/2027
    for campo in ("progressao_previsao_seeu", "livramento_previsao_seeu", "termino_previsao_seeu"):
        v = r.get(campo)
        if v and JAN_A <= D(v) <= JAN_B:
            print("AVISO %s: %s=%s na janela" % (c["id"], campo, v))
    return c


def K():
    _k[0] += 1
    return _k[0]


def R(k, crimes, evs=(), incs=(), **kw):
    r = rspe(k, crimes, evs, incs, **kw)
    r["_k"] = k
    return r


def mais(d, n):
    return F(D(d) + timedelta(days=int(n)))


def basico(k, crimes, ini, db=None, prog=None, liv=None, motivo="PRISÃO DEFINITIVA", extra_evs=(), extra_incs=(), **kw):
    procs = ", ".join(P(c) for c in crimes)
    evs = [prisao(ini, procs, motivo)] + list(extra_evs)
    incs = [inc(REG, "Fechado - Regime Inicial", "", ini)] + list(extra_incs)
    return R(k, crimes, evs, incs, ini=ini, db=db or ini, prog=prog, liv=liv, **kw)


# =====================================================================================================================
# A. Dados ausentes e cadastro
# =====================================================================================================================
k = K()
c1 = cr(k, FURTO, anos(3, 6), "10/04/2023")
r = basico(k, [c1], "22/02/2025", prog="09/11/2025", liv="03/03/2026", regime="")
novo("AUD-A cadastro", "Regime atual em branco no RSPE", "Auditoria", "Execução ativa, presa, com o campo Regime Atual em branco.",
     "Auditoria: 'Faltam dados: regime atual' em alerta, com botão Preencher.",
     "Sem o regime atual não há como calcular progressão; dado essencial do cálculo (LEP, arts. 110 e 112). Execução ativa, com prisão lançada "
     "em 22/02/2025: o campo deve vir preenchido. Política: falta de dado essencial = alerta.", r,
     [AUD("faltam-dados-regime_atual", nivel="alerta")])

k = K()
c1 = cr(k, ESTEL, anos(4), "15/06/2023")
r = basico(k, [c1], "03/03/2025", prog="09/10/2025", liv="03/10/2026", term="")
novo("AUD-A cadastro", "Término em branco no RSPE", "Auditoria", "Execução ativa, presa, sem a data de término impressa.",
     "Auditoria: 'Faltam dados: término' em alerta.",
     "Término é dado essencial (extinção, prescrição, art. 75). Execução ativa com prisão desde 03/03/2025 e sem término: deve ser informado.", r,
     [AUD("faltam-dados-termino_previsao_seeu", nivel="alerta")])

k = K()
c1 = cr(k, FURTO_Q, anos(5), "21/09/2022")
r = basico(k, [c1], "14/01/2024", prog="25/10/2024", liv="16/09/2025", nasc="")
novo("AUD-A cadastro", "Data de nascimento ausente", "Auditoria", "RSPE sem data de nascimento.",
     "Auditoria: 'Data de nascimento não consta no RSPE - informar' em verificar.",
     "Sem nascimento não se aferem CP, art. 115 (menor de 21 no fato / maior de 70 na sentença), LEP, art. 117, I, e as hipóteses de idade "
     "dos decretos. Não é erro verificável no RSPE (pode ser só omissão do SEEU): verificar.", r,
     [AUD("nascimento-nao-consta", nivel="verificar")])

k = K()
c1 = cr(k, FURTO_Q, anos(4, 2), "08/02/2024")
r = R(k, [c1], [], [], ini=None, regime="", term="")
novo("AUD-A cadastro", "Pena não iniciada no SEEU", "Auditoria", "Guia com condenação, sem nenhum evento nem incidente lançado.",
     "Auditoria: 'Pena não iniciada no SEEU' em verificar; sem 'Faltam dados' de regime ou término (não se exigem antes do início).",
     "LEP, arts. 105 e 106: transitada a sentença, expede-se a guia e inicia-se a execução. Sem evento algum, não há cálculo; regime e término "
     "não existem ainda, logo a falta deles não é falha de leitura.", r,
     [AUD("pena-nao-iniciada-seeu", nivel="verificar"), AUD("faltam-dados-regime_atual", presente=False),
      AUD("faltam-dados-termino_previsao_seeu", presente=False)])

k = K()
c1, c2 = cr(k, FURTO_Q, anos(3), "11/05/2022", 1), cr(k, ESTEL, anos(2, 6), "02/09/2022", 2)
r = basico(k, [c1, c2], "17/07/2024", pena=0, term="")
novo("AUD-A cadastro", "Guia sem pena calculada (pena total zero)", "Auditoria", "Duas condenações ativas e prisão lançada, mas pena total 0a0m0d.",
     "Auditoria: 'Guia sem pena calculada' em alerta, com a soma 5a6m0d.",
     "3a0m0d + 2a6m0d = 5a6m0d. Sem cálculo, o SEEU não imprime marcos nem término (LEP, arts. 66, III, a, e 111): prejudica o assistido "
     "(nenhum benefício é calculado) e é verificável no RSPE.", r,
     [AUD("guia-sem-pena-calculada-pena-total-com", nivel="alerta"), AUD("guia-sem-pena-calculada-pena-total-com", contem="5a6m0d")])

k = K()
c1 = cr(k, ESTEL, anos(4), "19/03/2022")
r = basico(k, [c1], "06/06/2023", prog="02/12/2023", liv="05/06/2024", status="ARQUIVADO")
novo("AUD-A cadastro", "Execução arquivada com pena por cumprir", "Auditoria", "Status ARQUIVADO, crime não extinto e pena remanescente maior que zero.",
     "Auditoria: 'Execução arquivada no SEEU com pena por cumprir' em verificar.",
     "Arquivamento sem extinção da pena (CP, art. 107; LEP, art. 66, II) e com saldo: ou falta a decisão de extinção, ou a execução foi "
     "arquivada indevidamente (redistribuída?). Depende dos autos: verificar.", r,
     [AUD("execucao-arquivada-com-pena", nivel="verificar")])

k = K()
c1 = cr(k, FURTO, anos(2, 8), "15/03/2021", sentenca="10/01/2021")
r = basico(k, [c1], "04/08/2025", prog="06/01/2026", liv="23/06/2026")
novo("AUD-A cadastro", "Sentença anterior ao fato", "Auditoria", "Crime com sentença (10/01/2021) e trânsito anteriores ao fato (15/03/2021).",
     "Auditoria: 'Data impossível no cadastro' em verificar.",
     "Não há sentença antes do fato. Uma das datas está errada; a do fato decide lei aplicável (CF, art. 5º, XL), reincidência (CP, art. 63) "
     "e prescrição. Qual está errada só os autos dizem: verificar.", r,
     [AUD("data-impossivel-no-cadastro", nivel="verificar")])

k = K()
c1 = cr(k, FURTO_Q, anos(5), "02/11/2023")
r = basico(k, [c1], "20/06/2024", prog="09/04/2025", liv="19/02/2026", ger=D("10/03/2025"))
novo("AUD-A cadastro", "RSPE emitido antes da correção do SEEU (15/05/2025)", "Auditoria", "RSPE gerado em 10/03/2025, antes da correção dos cálculos do SEEU.",
     "Auditoria: 'RSPE emitido antes de correção do SEEU' em verificar (pedir RSPE atualizado).",
     "O próprio SEEU corrigiu o cálculo de penas e frações na versão de 15/05/2025; RSPE anterior pode trazer o erro. Não se sabe se este "
     "foi afetado: verificar e juntar RSPE novo.", r,
     [AUD("rspe-anterior-a-correcao-do-seeu", nivel="verificar")])

k = K()
c1 = cr(k, ROUBO, anos(6), "14/12/2021", fp=P25, vga="S")
r = basico(k, [c1], "07/02/2023", prog="02/08/2024", liv="06/02/2025")
c2 = cr(4099, FURTO_Q, anos(3), "30/01/2024")
r2 = basico(4099, [c2], "05/05/2025", prog="09/11/2025", liv="03/05/2026", cpf=r["cpf"], nome=r["nome"], nasc=r["data_nascimento"])
novo("AUD-A cadastro", "Duas execuções ativas da mesma pessoa", "Auditoria", "Outra execução ativa no SEEU com o mesmo CPF.",
     "Auditoria: 'Mais de uma execução ativa no SEEU para a mesma pessoa' em verificar.",
     "LEP, art. 111: havendo condenações em processos distintos, o regime e os benefícios se calculam sobre a soma (unificação numa só "
     "execução). Duas execuções ativas indicam falta de unificação ou guia redistribuída: verificar.", r,
     [AUD("outras-execucoes-ativas", nivel="verificar")], extra=[r2])

# =====================================================================================================================
# B. Data-base da progressão e do livramento
# =====================================================================================================================
k = K()
c1 = cr(k, ROUBO, anos(7), "02/07/2022", fp=P25, vga="S")
r = basico(k, [c1], "19/07/2022", prog="17/03/2024", liv="17/07/2024", motivo="PRISÃO EM FLAGRANTE")
novo("AUD-B data-base", "Data-base confere com a prisão e o regime inicial", "Auditoria", "Prisão em flagrante e regime inicial no mesmo dia; data-base nesse dia.",
     "Auditoria: 'Data-base confere com o RSPE' (ok); sem inconsistência nem alteração de data-base.",
     "Data-base = início do cumprimento (LEP, art. 112): 19/07/2022, igual à prisão e ao regime inicial. Nada a apontar.", r,
     [AUD("data-base-confere-com-o-rspe", nivel="ok"), AUD("inconsistencia-da-data-base-sem-prisao-alteracao", presente=False),
      AUD("regime-inicial-depois-da-primeira-prisao", presente=False)])

k = K()
c1 = cr(k, ROUBO, anos(9), "29/01/2025", fp=P25, vga="S")
pc = P(c1)
evs = [prisao("03/02/2025", pc, "PRISÃO EM FLAGRANTE")]
incs = [inc(REG, "Fechado - Regime Inicial", "", "28/08/2025")]
r = R(k, [c1], evs, incs, ini="03/02/2025", db="28/08/2025", prog="06/10/2027", liv="05/02/2028")
novo("AUD-B data-base", "Regime inicial lançado depois da primeira prisão (detração antes da fração)", "Auditoria",
     "Preso em flagrante em 03/02/2025 sem soltura; regime inicial e data-base só em 28/08/2025.",
     "Auditoria: 'Regime inicial lançado em 28/08/2025, depois da primeira prisão (03/02/2025)' em alerta; diferença de cerca de 154 dias.",
     "Detração (CP, art. 42) = 03/02/2025 a 27/08/2025 = 206 dias. Pena 9 anos = 3.285 dias, 25% (LEP, art. 112, III). "
     "Conta do SEEU (data-base no regime inicial): (3.285 − 206) × 25% = 769 dias → 06/10/2027. Conta legal: 3.285 × 25% − 206 = 615 dias "
     "a partir de 28/08/2025 (= 821 dias da prisão) → 05/05/2027. Diferença 206 × 75% = 154 dias contra o assistido: alerta.", r,
     [AUD("regime-inicial-depois-da-primeira-prisao", nivel="alerta", contem="28/08/2025")])

k = K()
cs = [cr(k, FURTO_Q, anos(4), f, n) for n, f in ((1, "15/11/2020"), (2, "20/11/2020"), (3, "25/11/2020"))]
pcs = ", ".join(P(c) for c in cs)
evs = [prisao("02/12/2020", pcs, "PRISÃO EM FLAGRANTE"), interr("31/03/2021", "LIBERDADE PROVISÓRIA", pcs),
       prisao("10/09/2025", pcs, "PRISÃO DEFINITIVA")]
incs = [inc(REG, "Fechado - Regime Inicial", "", "02/12/2020")]
fora = (D("10/09/2025") - D("31/03/2021")).days - 1
r = R(k, cs, evs, incs, ini="02/12/2020", interrompidos=fora, db="10/09/2025", prog="18/07/2027", liv="10/09/2029",
      seeu_fracoes_progressao=["Comum primário (16%): 1a10m12d"])
novo("AUD-B data-base", "Nova prisão depois de soltura: data-base na nova prisão e detração antes da fração", "Auditoria",
     "Preso 02/12/2020 a 31/03/2021 (120 dias), solto, preso de novo em 10/09/2025 (data-base); lapso impresso 1a10m12d.",
     "Auditoria: 'Data-base em 10/09/2025, depois da primeira prisão (02/12/2020): detração descontada antes da fração' em alerta (previsão futura).",
     "Pena 3 × 4 anos = 12 anos (144 meses), 16%. Lapso impresso 1a10m12d = (144 − 4 meses) × 16% = 22,4 meses: o SEEU tirou os 120 dias "
     "(4 meses) da pena antes da fração. Conta legal (CP, art. 42 - a detração é pena cumprida): 144 × 16% = 23,04 meses = 1a11m1d, menos "
     "120 dias = 1a7m1d. Diferença 3m11d (≈ 120 × 84%). Previsão do SEEU 18/07/2027 (futura): alerta. Tese: a 5ª Turma do STJ "
     "(AgRg no REsp 2.248.958) admite data-base na última prisão com liberdade intermediária, mas não autoriza tirar a detração da pena antes "
     "da fração.", r,
     [AUD("regime-inicial-depois-da-primeira-prisao", contem="10/09/2025", nivel="alerta")])

k = K()
c1 = cr(k, FURTO_Q, anos(3), "10/04/2021", 1)
c2 = cr(k, ROUBO, anos(6), "05/01/2021", 2, fp=P25, vga="S", transito="14/06/2023")
evs = [prisao("20/04/2021", P(c1), "PRISÃO EM FLAGRANTE"), prisao("05/07/2023", P(c2), "PRISÃO DEFINITIVA")]
incs = [inc(REG, "Fechado - Regime Inicial", "", "20/04/2021")]
r = R(k, [c1, c2], evs, incs, ini="20/04/2021", db="05/07/2023", prog="06/12/2024", liv="19/04/2024")
novo("AUD-B data-base", "Guia nova de quem já estava preso: data-base movida para a prisão definitiva (Tema 1006)", "Auditoria",
     "Preso sem interrupção desde 20/04/2021; a guia nova trouxe 'prisão definitiva' em 05/07/2023, que virou a data-base.",
     "Auditoria: item da data-base movida pelo início da guia nova, em alerta; a data certa é 20/04/2021.",
     "STJ, Tema 1006 (REsp 1.753.509): a superveniência de nova condenação não altera a data-base. A 'prisão definitiva' de 05/07/2023 "
     "é fictícia (já estava preso desde 20/04/2021, sem interrupção); o roubo é de fato anterior à prisão (05/01/2021), não é crime "
     "durante o cumprimento. Política: data-base contrária à lei = Auditoria alerta.", r,
     [AUD("data-base-na-guia-nova-de-quem-ja-estava-preso"), AUD("data-base-na-guia-nova-de-quem-ja-estava-preso", nivel="alerta")])

k = K()
c1 = cr(k, ESTEL, anos(4), "02/03/2021", 1)
c2 = cr(k, ROUBO, anos(5, 4), "16/02/2021", 2, fp=P25, vga="S", transito="21/11/2023")
evs = [prisao("11/03/2021", P(c1), "PRISÃO EM FLAGRANTE"), prisao("18/12/2023", P(c2), "PRISÃO DEFINITIVA")]
incs = [inc(REG, "Fechado - Regime Inicial", "", "11/03/2021"), inc(REG, "Fechado - Regime Inicial", "", "18/12/2023")]
r = R(k, [c1, c2], evs, incs, ini="11/03/2021", db="18/12/2023", prog="19/12/2025", liv="11/03/2024")
novo("AUD-B data-base", "Segundo regime inicial na guia nova, com a pessoa presa", "Auditoria",
     "Preso desde 11/03/2021; nova guia com outro 'regime inicial' em 18/12/2023 (data-base), sem interrupção.",
     "Auditoria: 'Mais de um regime inicial lançado' em alerta; e o item da data-base no início da guia nova (data certa 11/03/2021) em alerta.",
     "Uma execução tem um regime inicial (LEP, art. 111: nova condenação → soma e novo regime pela soma, sem novo marco). STJ, Tema 1006: "
     "a data-base continua 11/03/2021. Política: data-base contrária à lei = alerta.", r,
     [AUD("mais-de-um-regime-inicial", nivel="alerta"), AUD("data-base-no-inicio-da-guia-nova-com-a-pessoa-presa"),
      AUD("data-base-no-inicio-da-guia-nova-com-a-pessoa-presa", nivel="alerta")])

k = K()
c1 = cr(k, ROUBO, anos(7), "28/12/2021", fp=P25, vga="S")
r = basico(k, [c1], "11/01/2022", db="14/03/2025", prog="20/09/2027", liv="10/05/2024",
           extra_incs=[inc(REG, "Semiaberto - Progressão de Regime", "14/03/2025", "14/03/2025")], regime="Semiaberto - ATIVO")
novo("AUD-B data-base", "Progressão lançada na data da decisão", "Auditoria",
     "Progressão ao semiaberto com data de referência igual à da decisão (14/03/2025), ainda a data-base atual.",
     "Auditoria: 'Progressão lançada na data da decisão (14/03/2025)' em alerta.",
     "STJ, Tema 1165: a decisão de progressão é declaratória; a data-base da progressão seguinte é a do preenchimento dos requisitos. "
     "Lapso 25% de 7 anos (2.555 dias) = 638 dias, atingido em 10/10/2023 contado de 11/01/2022 (dia do começo incluído); lançada na decisão, "
     "perdem-se cerca de 520 dias para o aberto.", r,
     [AUD("progressao-com-data-base-igual-a-data-da-decisao", nivel="alerta")])

k = K()
c1 = cr(k, FURTO_Q, anos(5), "25/01/2021", 1)
c2 = cr(k, ESTEL, anos(3), "10/09/2020", 2, transito="20/06/2023")
r = basico(k, [c1, c2], "03/02/2021", db="18/08/2023", prog="02/12/2024", liv="03/02/2024",
           extra_incs=[inc("SOMATÓRIO DAS PENAS", "", "18/08/2023", "18/08/2023", procs=P(c2)),
                       inc("ALTERAÇÃO DE DATA-BASE", "Nova condenação", "18/08/2023", "18/08/2023")])
novo("AUD-B data-base", "Alteração de data-base por nova condenação, sem falta", "Auditoria",
     "Somatório e 'alteração de data-base - nova condenação' em 18/08/2023, sem falta grave; data-base impressa 18/08/2023.",
     "Auditoria: 'Alteração de data-base em 18/08/2023 sem falta grave homologada' em alerta.",
     "A data-base só muda por falta grave reconhecida (Súmula 534/STJ; LEP, art. 112, § 6º), regressão ou nova prisão após interrupção. "
     "Soma de penas não altera (STJ, Tema 1006). Preso desde 03/02/2021: a data-base deve continuar 03/02/2021.", r,
     [AUD("alteracao-de-data-base-sem-falta-homologada", nivel="alerta")])

k = K()
c1 = cr(k, ROUBO, anos(8), "30/04/2021", fp=P25, vga="S")
r = basico(k, [c1], "12/05/2021", db="15/04/2024", prog="17/04/2026", liv="18/07/2024", interrompidos=72,
           extra_evs=[interr("02/02/2024", "FUGA"), prisao("15/04/2024", P(c1), "RECAPTURA/REINÍCIO DE CUMPRIMENTO")])
novo("AUD-B data-base", "Data-base na recaptura sem falta homologada (Súmula 533)", "Auditoria",
     "Fuga em 02/02/2024, recaptura e data-base em 15/04/2024; nenhuma falta homologada no RSPE.",
     "Auditoria: 'Data-base movida para a recaptura (15/04/2024) sem falta homologada' em verificar; data-base anterior 12/05/2021.",
     "A fuga só move a data-base se reconhecida como falta grave em PAD (Súmula 533/STJ) e homologada (Súmula 534; LEP, art. 118). "
     "Sem homologação, a data-base é 12/05/2021 (o período fora continua descontado). Como a falta pode estar em apuração e o RSPE "
     "pode estar atrasado, não é erro verificável: verificar.", r,
     [AUD("data-base-movida-para-a-recaptura-sem-falta-homo", nivel="verificar")])

k = K()
c1 = cr(k, ROUBO, anos(8), "30/04/2021", fp=P25, vga="S")
r = basico(k, [c1], "12/05/2021", db="15/04/2024", prog="17/04/2026", liv="18/07/2024", interrompidos=72,
           extra_evs=[interr("02/02/2024", "FUGA"), prisao("15/04/2024", P(c1), "RECAPTURA/REINÍCIO DE CUMPRIMENTO")],
           extra_incs=[inc("HOMOLOGAÇÃO DE FALTA GRAVE", "02/02/2024", "10/06/2024", "02/02/2024")])
novo("AUD-B data-base", "Data-base na recaptura com a fuga homologada", "Auditoria",
     "Fuga 02/02/2024 homologada como falta grave em 10/06/2024; recaptura e data-base em 15/04/2024.",
     "Auditoria: sem item de recaptura sem falta e sem inconsistência da data-base.",
     "Fuga é falta permanente; homologada, a data-base é a recaptura (Súmula 534/STJ; LEP, art. 50, II). Data-base correta.", r,
     [AUD("data-base-movida-para-a-recaptura-sem-falta-homo", presente=False),
      AUD("inconsistencia-da-data-base-sem-prisao-alteracao", presente=False)])

k = K()
c1 = cr(k, FURTO_Q, anos(6), "18/05/2021", 1)
c2 = cr(k, ESTEL, anos(3), "05/03/2021", 2, transito="30/04/2025")
r = basico(k, [c1, c2], "06/06/2021", db="22/05/2025", prog="20/07/2027", liv="06/06/2024",
           extra_incs=[inc(REG, "Semiaberto - Progressão de Regime", "20/06/2023", "10/06/2023"),
                       inc("SOMATÓRIO DAS PENAS", "", "22/05/2025", "22/05/2025", procs=P(c2)),
                       inc(REG, "Fechado - Regressão", "22/05/2025", "22/05/2025")])
novo("AUD-B data-base", "Regressão decorrente da soma usada como data-base", "Auditoria",
     "Semiaberto desde 10/06/2023; nova pena somada em 22/05/2025 com regressão ao fechado no mesmo dia, sem falta; data-base 22/05/2025.",
     "Auditoria: 'Data-base (22/05/2025) movida pela regressão decorrente da soma de penas' em alerta.",
     "A regressão pela soma (LEP, art. 111, p. ú., e 118, II) muda o regime, mas a nova condenação não altera a data-base (STJ, Tema 1006). "
     "Sem falta (Súmula 534), a data-base continua a da última progressão (10/06/2023).", r,
     [AUD("data-base-coincide-com-a-soma-unificacao-das-pen", contem="regressão decorrente", nivel="alerta")])

k = K()
c1 = cr(k, FURTO_Q, anos(6), "18/05/2021")
r = basico(k, [c1], "06/06/2021", db="07/03/2025", prog="20/08/2027", liv="06/06/2023",
           extra_incs=[inc(REG, "Semiaberto - Progressão de Regime", "20/06/2023", "10/06/2023"),
                       inc("HOMOLOGAÇÃO DE FALTA GRAVE", "07/03/2025", "20/04/2025", "07/03/2025"),
                       inc(REG, "Fechado - Regressão", "20/04/2025", "20/04/2025")])
novo("AUD-B data-base", "Regressão por falta homologada: data-base na data da falta (Súmula 534)", "Auditoria",
     "Falta grave de 07/03/2025 homologada com regressão em 20/04/2025; data-base 07/03/2025.",
     "Auditoria: 'Regressão registrada' em info; sem inconsistência nem alteração de data-base sem falta.",
     "Súmula 534/STJ: a falta grave interrompe a contagem para a progressão, recomeçando da data da infração. Data-base 07/03/2025 correta.", r,
     [AUD("regressao-registrada-em", nivel="info"), AUD("inconsistencia-da-data-base-sem-prisao-alteracao", presente=False),
      AUD("alteracao-de-data-base-sem-falta-homologada", presente=False)])

k = K()
c1 = cr(k, ROUBO, anos(5, 4), "29/07/2021", 1, fp=P25, vga="S")
c2 = cr(k, FURTO_Q, anos(2, 8), "13/06/2021", 2, transito="01/10/2024")
r = basico(k, [c1, c2], "08/08/2021", db="14/11/2024", prog="10/04/2027", liv="08/08/2024",
           extra_incs=[inc("SOMATÓRIO DAS PENAS", "", "14/11/2024", "14/11/2024", procs=P(c2))])
novo("AUD-B data-base", "Data-base na data da soma das penas", "Auditoria",
     "Preso desde 08/08/2021; somatório em 14/11/2024 e data-base impressa 14/11/2024, sem prisão, regime ou falta nessa data.",
     "Auditoria: 'Data-base (14/11/2024) coincide com a soma/unificação das penas' em alerta.",
     "STJ, Tema 1006: a unificação/soma de penas não altera a data-base. A data certa é 08/08/2021.", r,
     [AUD("data-base-coincide-com-a-soma-unificacao-das-pen", nivel="alerta")])

k = K()
c1 = cr(k, ROUBO, anos(9), "02/10/2020", fp=P25, vga="S")
r = basico(k, [c1], "19/10/2020", db="12/06/2025", prog="19/05/2027", liv="17/10/2023",
           extra_incs=[inc("COMUTAÇÃO", "Decreto 12.338/2024", "12/06/2025", "12/06/2025")])
novo("AUD-B data-base", "Comutação usada como marco de data-base", "Auditoria",
     "Comutação decidida em 12/06/2025 e data-base impressa no mesmo dia, sem falta, regressão ou prisão.",
     "Auditoria: 'Data-base em 12/06/2025, junto com a comutação: indulto ou comutação não criam nova data-base' em alerta.",
     "Os marcos da data-base são prisão, progressão/regressão e falta grave (LEP, art. 112, § 6º; Súmula 534). Comutação reduz a pena, "
     "não reinicia a contagem (decretos não o preveem; STJ, Tema 1006 por analogia). A data certa é 19/10/2020.", r,
     [AUD("data-base-movida-pelo-indulto", nivel="alerta")])

k = K()
c1 = cr(k, ROUBO, anos(8), "01/10/2021", fp=P25, vga="S")
r = basico(k, [c1], "15/10/2021", db="03/09/2024", prog="28/06/2026", liv="14/04/2024",
           extra_incs=[inc("HOMOLOGAÇÃO DE FALTA GRAVE", "03/09/2024", "", "03/09/2024", sit="PENDENTE")])
novo("AUD-B data-base", "Data-base na data de falta ainda pendente", "Auditoria",
     "Falta grave de 03/09/2024 com situação PENDENTE; data-base impressa 03/09/2024.",
     "Auditoria: 'Inconsistência da data-base (03/09/2024)' em verificar.",
     "Sem decisão que reconheça a falta (Súmula 533/STJ: PAD obrigatório; Súmula 534: só a falta reconhecida interrompe), a data-base "
     "não se move. Como o RSPE pode só não ter atualizado a homologação: verificar.", r,
     [AUD("inconsistencia-da-data-base-sem-prisao-alteracao", nivel="verificar")])

k = K()
c1 = cr(k, ROUBO, anos(9), "25/02/2022", fp=P25, vga="S")
r = basico(k, [c1], "10/03/2022", db="05/05/2024", prog="22/09/2026", liv="05/05/2027",
           extra_incs=[inc("HOMOLOGAÇÃO DE FALTA GRAVE", "05/05/2024", "01/07/2024", "05/05/2024")],
           livramento_data_base_seeu="05/05/2024")
novo("AUD-B data-base", "Data-base do livramento movida pela falta grave (Súmula 441)", "Auditoria",
     "Falta homologada (fato 05/05/2024); o SEEU moveu também a data-base do livramento para 05/05/2024.",
     "Auditoria: 'Data-base do livramento (05/05/2024) coincide com falta grave homologada' em alerta; correta 10/03/2022.",
     "Súmula 441/STJ: a falta grave não interrompe o prazo para obtenção de livramento condicional. Pena 9 anos, 1/3 = 1.095 dias: "
     "contado de 10/03/2022 → 09/03/2025; contado de 05/05/2024 → 04/05/2027.", r,
     [AUD("data-base-do-livramento-alterada-por-falta-grave", nivel="alerta")])

k = K()
c1 = cr(k, ROUBO, anos(9), "25/02/2022", fp=P25, vga="S")
r = basico(k, [c1], "10/03/2022", db="05/05/2024", prog="22/09/2026", liv="09/03/2025",
           extra_incs=[inc("HOMOLOGAÇÃO DE FALTA GRAVE", "05/05/2024", "01/07/2024", "05/05/2024")])
novo("AUD-B data-base", "Falta move só a data-base da progressão (livramento intacto)", "Auditoria",
     "Falta homologada de 05/05/2024: data-base da progressão 05/05/2024; do livramento, 10/03/2022 (início).",
     "Auditoria: nenhum item de data-base do livramento; data-base da progressão confere.",
     "Súmula 534 (progressão interrompida pela falta) e Súmula 441 (livramento não): exatamente o que o SEEU fez.", r,
     [AUD("data-base-do-livramento-alterada-por-falta-grave", presente=False),
      AUD("data-base-do-livramento-igual-a-da-progressao", presente=False),
      AUD("data-base-confere-com-o-rspe", nivel="ok")])

# =====================================================================================================================
# C. Detração
# =====================================================================================================================
k = K()
c1 = cr(k, ROUBO, anos(8), "22/05/2021", fp=P25, vga="S")
r = basico(k, [c1], "01/06/2021", prog="31/05/2023", liv="01/06/2024")
cust = (GER - D("01/06/2021")).days + 1
cump = cust - 400
r["pena_cumprida"] = pena_cab(cump)
from base_casos import amd
(ta, tm, td), (ca, cm, cd) = amd(anos(8)), amd(cump)
ra_, rm_, rd_ = ta - ca, tm - cm, td - cd
if rd_ < 0:
    rd_ += 30; rm_ -= 1
if rm_ < 0:
    rm_ += 12; ra_ -= 1
r["pena_remanescente"] = "%da%dm%dd" % (ra_, rm_, rd_)
novo("AUD-C detração", "Pena cumprida do SEEU 400 dias menor que a custódia", "Auditoria",
     "Prisão contínua desde 01/06/2021 sem interrupção; a pena cumprida impressa tem 400 dias a menos que a custódia.",
     "Auditoria: 'Pena cumprida do SEEU ... menor que a custódia dos eventos' em verificar.",
     "Custódia 01/06/2021 a 05/10/2026 = %d dias (dia do começo incluído); impresso %s. CP, art. 42: todo o tempo preso conta. A causa "
     "(prisão vinculada a outro processo, indulto parcial) só aparece nos autos: verificar." % (cust, pena_cab(cump)), r,
     [AUD("pena-cumprida-menor-que-custodia", nivel="verificar")])

k = K()
c1 = cr(k, ROUBO, anos(8), "22/05/2021", fp=P25, vga="S")
fora = (GER - D("10/01/2024")).days
r = basico(k, [c1], "01/06/2021", prog="31/05/2023", liv="01/06/2024", interrompidos=fora,
           extra_evs=[interr("10/01/2024", "INTERRUPÇÃO POR PRISÃO EM OUTRO PROCESSO", P(c1))], term="")
r["termino_previsao_seeu"] = ""
novo("AUD-C detração", "Prisão por processo desta execução lançada como interrupção", "Auditoria",
     "Interrupção 'por prisão em outro processo' em 10/01/2024 que cita o próprio processo desta execução; sem reinício.",
     "Auditoria: 'Prisão por processo desta execução lançada como interrupção (10/01/2024)' em alerta.",
     "O processo citado integra esta execução: a pessoa segue presa por ela, e desde 10/01/2024 (%d dias até a emissão) nada é computado. "
     "CP, art. 42, e LEP, art. 111: verificável no próprio RSPE e contra o assistido → alerta." % fora, r,
     [AUD("pena-cumprida-menor-que-custodia", contem="interrupção", nivel="alerta")])

k = K()
c1 = cr(k, FURTO_Q, anos(4), "12/07/2022")
outro = "0004321-11.2023.8.12.0001"
r = basico(k, [c1], "03/03/2025", prog="10/11/2025", liv="02/07/2026",
           extra_evs=[prisao("10/02/2023", outro, "PRISÃO PREVENTIVA"), interr("25/08/2023", "ALVARA DE SOLTURA - ABSOLVICAO", outro)])
r["_eventos"] = sorted(r["_eventos"], key=lambda e: D(e["data"]))
novo("AUD-C detração", "Detração por prisão preventiva em outro processo (absolvido)", "Auditoria",
     "Preventiva de 10/02/2023 a 25/08/2023 em outro processo, encerrada por absolvição; o furto desta execução é de 12/07/2022.",
     "Auditoria: 'Detração por prisão em outro processo ... 197 dias' em verificar.",
     "10/02/2023 a 25/08/2023, os dois dias contados (CP, art. 10) = 197 dias. CP, art. 42, e jurisprudência do STJ: cabe detração em "
     "processo diverso quando o crime da condenação é anterior à prisão cautelar (vedada a 'conta-corrente'). Depende de o tempo não ter "
     "servido a outra pena: verificar.", r,
     [AUD("detracao-prisao-em-outro-processo", nivel="verificar", contem="197")])

k = K()
c1 = cr(k, FURTO_Q, anos(5), "15/01/2023")
r = basico(k, [c1], "06/02/2024", prog="20/09/2024", liv="06/02/2026", remidos=30,
           extra_incs=[inc("REMIÇÃO", "30 Dia(s) Remido(s) - recolhimento noturno (Tema 1155)", "10/03/2024", "06/02/2024")])
novo("AUD-C detração", "Recolhimento noturno lançado como remição (Tema 1155)", "Auditoria",
     "Incidente de remição de 30 dias com complemento 'recolhimento noturno (Tema 1155)'.",
     "Auditoria: 'Detração lançada como remição (10/03/2024)' em alerta.",
     "STJ, Tema 1155: o recolhimento noturno/monitoração cautelar se computa como detração (CP, art. 42), que é pena cumprida e não pode "
     "ser perdida. Como remição, fica exposto à perda de até 1/3 por falta grave (LEP, art. 127). Prejuízo potencial verificável: alerta.", r,
     [AUD("detracao-como-remicao", nivel="alerta")])

# =====================================================================================================================
# D. Faltas
# =====================================================================================================================
def faltas_base(k, incs, db, remidos, saldo, ini="05/01/2021", **kw):
    c1 = cr(k, ROUBO, anos(9), "28/12/2020", fp=P25, vga="S")
    r = basico(k, [c1], ini, db=db, remidos=remidos, extra_incs=incs, **kw)
    r["saldo_remidos"] = saldo
    return r


k = K()
r = faltas_base(k, [inc("REMIÇÃO", "60 Dia(s) Remido(s)", "10/12/2021", "30/11/2021"),
                    inc("HOMOLOGAÇÃO DE FALTA GRAVE", "14/02/2022", "20/05/2025", "14/02/2022"),
                    inc("DIAS PERDIDOS NA REMIÇÃO", "20", "20/05/2025", "20/05/2025")],
                "14/02/2022", 40, "40 dias (60 dias remidos - 20 dias perdidos)", prog="15/10/2027", liv="04/01/2024")
novo("AUD-D faltas", "Falta homologada depois da prescrição disciplinar (3 anos)", "Auditoria",
     "Falta com fato em 14/02/2022 homologada só em 20/05/2025, com perda de 20 dias remidos; data-base na falta.",
     "Auditoria: 'Falta grave de 14/02/2022 homologada depois da prescrição disciplinar' em alerta (prazo até 13/02/2025; perda a restituir); "
     "sem item de perda dentro do limite para essa falta.",
     "Prescrição disciplinar: 3 anos por analogia ao CP, art. 109, VI (redação da Lei 12.234/2010; STJ, AgRg no HC 779.723), contados do "
     "fato com o dia do começo incluído: 14/02/2022 + 3 anos − 1 dia = 13/02/2025. Homologada em 20/05/2025: prescrita; a perda de 20 dias "
     "deve ser restituída e a data-base volta a 05/01/2021.", r,
     [AUD("falta-homologada-apos-prescricao", nivel="alerta", contem="13/02/2025"),
      AUD("perda-de-remidos-pela-falta-grave-de", presente=False)])

k = K()
r = faltas_base(k, [inc("HOMOLOGAÇÃO DE FALTA GRAVE", "10/01/2022", "20/03/2026", "10/01/2022")], "05/06/2023", 0,
                "0 dias (0 dias remidos - 0 dias perdidos)", prog="12/11/2027", liv="04/01/2024", interrompidos=510,
                extra_evs=[interr("10/01/2022", "FUGA"), prisao("05/06/2023", "", "RECAPTURA/REINÍCIO DE CUMPRIMENTO")])
for e in r["_eventos"]:
    if not e["processos"]:
        e["processos"] = r["_crimes"][0]["processo_criminal"]
novo("AUD-D faltas", "Fuga: prescrição disciplinar contada da recaptura", "Auditoria",
     "Fuga em 10/01/2022, recaptura em 05/06/2023, falta homologada em 20/03/2026.",
     "Auditoria: sem alerta de prescrição disciplinar (prazo até 04/06/2026).",
     "Fuga é infração permanente: a prescrição disciplinar corre da recaptura (STJ, HC 527.625). 05/06/2023 + 3 anos − 1 dia = 04/06/2026; "
     "homologação em 20/03/2026 dentro do prazo. (Contada do fato, teria prescrito em 09/01/2025 - não é o caso.)", r,
     [AUD("falta-homologada-apos-prescricao", presente=False)])

k = K()
r = faltas_base(k, [inc("REMIÇÃO", "75 Dia(s) Remido(s)", "10/01/2024", "30/11/2023"),
                    inc("HOMOLOGAÇÃO DE FALTA GRAVE", "08/04/2024", "20/06/2024", "08/04/2024"),
                    inc("DIAS PERDIDOS NA REMIÇÃO", "30", "20/06/2024", "20/06/2024")],
                "08/04/2024", 45, "45 dias (75 dias remidos - 30 dias perdidos)", prog="06/05/2026", liv="04/01/2024")
novo("AUD-D faltas", "Perda de remidos acima de 1/3 (LEP, art. 127)", "Auditoria",
     "75 dias remidos antes da falta de 08/04/2024; perda decretada de 30 dias.",
     "Auditoria: 'Perda de dias remidos acima de 1/3 (falta de 08/04/2024)' em alerta, excesso de 5 dias.",
     "LEP, art. 127: perda de até 1/3 do tempo remido. 75 ÷ 3 = 25; perdidos 30 → 5 dias além do limite legal.", r,
     [AUD("perda-de-dias-remidos-acima-de-1-3-falta-de", nivel="alerta", contem="5")])

k = K()
r = faltas_base(k, [inc("REMIÇÃO", "75 Dia(s) Remido(s)", "10/01/2024", "30/11/2023"),
                    inc("HOMOLOGAÇÃO DE FALTA GRAVE", "08/04/2024", "20/06/2024", "08/04/2024"),
                    inc("DIAS PERDIDOS NA REMIÇÃO", "25", "20/06/2024", "20/06/2024")],
                "08/04/2024", 50, "50 dias (75 dias remidos - 25 dias perdidos)", prog="06/05/2026", liv="04/01/2024")
novo("AUD-D faltas", "Perda de remidos dentro de 1/3", "Auditoria", "75 dias remidos; perda de 25 dias pela falta de 08/04/2024.",
     "Auditoria: 'Perda de 25 remidos pela falta grave' em info; sem alerta de 1/3.",
     "75 ÷ 3 = 25: perda no limite do art. 127 da LEP.", r,
     [AUD("perda-de-remidos-pela-falta-grave-de", nivel="info"), AUD("perda-de-dias-remidos-acima-de-1-3-falta-de", presente=False)])

k = K()
r = faltas_base(k, [inc("REMIÇÃO", "90 Dia(s) Remido(s)", "30/04/2022", "31/03/2022"),
                    inc("HOMOLOGAÇÃO DE FALTA GRAVE", "10/08/2022", "15/10/2022", "10/08/2022"),
                    inc("DIAS PERDIDOS NA REMIÇÃO", "30", "15/10/2022", "15/10/2022"),
                    inc("HOMOLOGAÇÃO DE FALTA GRAVE", "12/05/2023", "20/07/2023", "12/05/2023"),
                    inc("DIAS PERDIDOS NA REMIÇÃO", "20", "20/07/2023", "20/07/2023")],
                "12/05/2023", 40, "40 dias (90 dias remidos - 50 dias perdidos)", prog="10/07/2025", liv="04/01/2024")
novo("AUD-D faltas", "Segunda perda sobre a mesma remição (duplicidade)", "Auditoria",
     "90 remidos até 03/2022; falta de 10/08/2022 com perda de 30; falta de 12/05/2023 com perda de 20, sem remição nova entre as faltas.",
     "Auditoria: 'Perda de dias remidos em duplicidade (falta de 12/05/2023)' em verificar.",
     "LEP, art. 127: a perda recomeça a contagem a partir da data da infração; a remição anterior à primeira falta já sofreu o corte de 1/3 "
     "(30 de 90). A segunda falta só alcança remição adquirida depois de 10/08/2022 - e não há nenhuma no RSPE. Pode haver remição declarada "
     "depois por trabalho do intervalo (dado fora do RSPE): verificar. Tese defensiva (a jurisprudência não é uniforme).", r,
     [AUD("perda-de-dias-remidos-em-duplicidade-falta-de", nivel="verificar")])

k = K()
r = faltas_base(k, [inc("REMIÇÃO", "45 Dia(s) Remido(s)", "10/05/2024", "30/04/2024"),
                    inc("REMIÇÃO", "45 Dia(s) Remido(s)", "10/05/2024", "30/04/2024")],
                "05/01/2021", 90, "90 dias (90 dias remidos - 0 dias perdidos)", prog="12/01/2023", liv="04/01/2024")
novo("AUD-D faltas", "Mesma remição lançada duas vezes (a favor do assistido)", "Auditoria",
     "Dois incidentes iguais de 45 dias remidos (mesma referência e decisão) e saldo de 90.",
     "Auditoria: nenhum alerta (no máximo informação): o lançamento em dobro favorece o assistido.",
     "Política: a Auditoria só alerta o que prejudica o assistido. A remição dobrada aumenta a pena cumprida (LEP, art. 128) - erro "
     "favorável; não cabe à Defensoria pedir a correção. Achado se aparecer como alerta.", r,
     [AUD("remicao-lancada-em-duplicidade", presente=False, nivel="alerta")])

k = K()
r = faltas_base(k, [inc("REMIÇÃO", "40 Dia(s) Remido(s)", "10/02/2024", "31/01/2024"),
                    inc("REMIÇÃO", "30 Dia(s) Remido(s)", "10/08/2024", "31/07/2024")],
                "05/01/2021", 60, "60 dias (60 dias remidos - 0 dias perdidos)", prog="12/01/2023", liv="04/01/2024")
novo("AUD-D faltas", "Remições concedidas somam mais que o saldo", "Auditoria", "Remições de 40 e 30 dias (70) e saldo impresso de 60 remidos.",
     "Auditoria: 'Dias remidos: incidentes não fecham com o saldo' em alerta.",
     "40 + 30 = 70 dias declarados (LEP, arts. 126 e 128: o tempo remido conta como pena cumprida); o saldo tem 60. 10 dias a menos no "
     "cálculo, contra o assistido.", r,
     [AUD("dias-remidos-incidentes-nao-fecham-com-o-saldo", nivel="alerta")])

k = K()
r = faltas_base(k, [inc("REMIÇÃO", "60 Dia(s) Remido(s)", "10/02/2025", "31/01/2025"),
                    inc("DIAS PERDIDOS NA REMIÇÃO", "20", "10/09/2025", "10/09/2025")],
                "05/01/2021", 40, "40 dias (60 dias remidos - 20 dias perdidos)", prog="12/01/2023", liv="04/01/2024")
novo("AUD-D faltas", "Perda de remidos sem falta grave datada", "Auditoria", "Perda de 20 dias em 10/09/2025 sem nenhuma homologação de falta no RSPE.",
     "Auditoria: 'Perda de 20 remidos sem falta grave datada no RSPE' em verificar.",
     "A perda de remidos pressupõe falta grave reconhecida em PAD e homologada (LEP, art. 127; Súmula 533/STJ; STF, Tema 941). O RSPE não "
     "mostra a falta: pode ser omissão de lançamento: verificar.", r,
     [AUD("perda-de-remidos-sem-falta-grave-datada-no-rspe", nivel="verificar")])

# =====================================================================================================================
# E. Frações divergentes
# =====================================================================================================================
k = K()
c1 = cr(k, ROUBO, anos(6), "17/08/2021", fp=P30, vga="S")
r = basico(k, [c1], "30/08/2021", prog="30/06/2023", liv="30/08/2023")
novo("AUD-E frações", "Roubo de primário com 30% (legal 25%)", "Auditoria", "Roubo de 2021, primário, SEEU 30%.",
     "Auditoria: 'percentual de progressão do SEEU (30%) maior que o legal (25%)' em alerta.",
     "LEP, art. 112, III (Lei 13.964/2019): primário com violência = 25%. 30% é do reincidente em crime violento (inciso IV). Pena 6 anos: "
     "657 contra 547 dias - 110 dias a mais.", r,
     [AUD("percentual-de-progressao-diverge", nivel="alerta", contem="25%")])

k = K()
c1 = cr(k, ROUBO, anos(6), "17/08/2021", fp=P16, vga="S")
r = basico(k, [c1], "30/08/2021", prog="20/01/2023", liv="30/08/2023")
novo("AUD-E frações", "Roubo de primário com 16% (menor que o legal)", "Auditoria", "Roubo de 2021, primário, SEEU 16% (legal 25%).",
     "Auditoria: nenhum item de percentual divergente (erro favorável).",
     "Legal 25% (LEP, art. 112, III). O SEEU aplica menos: favorece o assistido; política = sem alerta.", r,
     [AUD("percentual-de-progressao-diverge", presente=False)])

k = K()
c1 = cr(k, ESTEL, anos(5), "12/05/2021", fp="1/6 - Comum")
r = basico(k, [c1], "24/05/2023", prog="23/03/2024", liv="21/01/2025")
novo("AUD-E frações", "1/6 no lugar de 16% (estelionato, pena 5 anos)", "Auditoria", "Estelionato de 2021, primário, SEEU 1/6.",
     "Auditoria: alerta '1/6 = 16,67% maior que o legal (16%) - 12 dias a mais'.",
     "LEP, art. 112, I (Lei 13.964/2019): 16%. Pena 1.825 dias: 1/6 = 304,17; 16% = 292,0; diferença 12,17 → 12 dias.", r,
     [AUD("percentual-de-progressao-diverge", nivel="alerta", contem="12 dias")])

k = K()
c1 = cr(k, FURTO_Q, anos(6), "09/06/2022", fl=L12)
r = basico(k, [c1], "21/06/2022", prog="13/02/2023", liv="20/06/2025")
novo("AUD-E frações", "Livramento 1/2 para primário (legal 1/3)", "Auditoria", "Furto qualificado, primário, SEEU livramento 1/2.",
     "Auditoria: 'fração de livramento do SEEU (1/2) maior que a legal (1/3)' em alerta.",
     "CP, art. 83, I: primário (não reincidente em crime doloso) = mais de 1/3. 1/2 é do reincidente (inciso II). Pena 6 anos: 3 anos "
     "contra 2 anos.", r,
     [AUD("fracao-de-livramento-diverge", nivel="alerta", contem="1/3")])

# =====================================================================================================================
# F. Reincidência no cadastro
# =====================================================================================================================
k = K()
c1 = cr(k, FURTO_Q, anos(5), "20/06/2021", fp=P20, fl=L12, rc="S")
r = basico(k, [c1], "02/07/2023", prog="01/07/2024", liv="30/12/2025", nasc="15/05/2003")
novo("AUD-F reincidência", "Marcado reincidente, mas tinha 18 anos no fato", "Auditoria",
     "Nascido em 15/05/2003, fato em 20/06/2021 (18 anos e 36 dias), marcado reincidente, SEEU 20% e 1/2.",
     "Auditoria: 'marcado reincidente, mas não é reincidente pelas datas' em alerta; percentual (16%) e livramento (1/3) em alerta.",
     "Reincidência exige condenação transitada antes do fato (CP, art. 63); antes dos 18 não há condenação penal (CP, art. 27). Em 36 dias "
     "de maioridade não há como haver crime, processo e trânsito. Primário: 16% (LEP, art. 112, I) e 1/3 (CP, art. 83, I).", r,
     [AUD("marcado-reincidente-desmentido-pelas-datas", nivel="alerta"), AUD("percentual-de-progressao-diverge", nivel="alerta"),
      AUD("fracao-de-livramento-diverge", nivel="alerta")])

k = K()
c1 = cr(k, FURTO_Q, anos(5), "14/03/2022", fp=P20, fl=L12, rc="S")
r = basico(k, [c1], "28/03/2023", prog="27/03/2024", liv="25/09/2025")
novo("AUD-F reincidência", "Marcado reincidente sem condenação anterior no RSPE", "Auditoria",
     "Único crime, marcado reincidente, SEEU 20% e 1/2; nenhuma outra condenação no RSPE.",
     "Auditoria: 'Marcado reincidente sem condenação anterior transitada no RSPE' em verificar; percentual de reincidente 'certo só se "
     "confirmada; primário 16%' em verificar.",
     "CP, arts. 63 e 64, I. A condenação anterior pode existir fora deste RSPE (outra comarca): não é erro verificável. Verificar.", r,
     [AUD("marcado-reincidente-sem-condenacao-anterior-tran", nivel="verificar"),
      AUD("percentual-reincidencia-a-conferir", nivel="verificar")])

k = K()
c1 = cr(k, FURTO, anos(2), "10/02/2018", 1, transito="20/08/2019")
c2 = cr(k, FURTO_Q, anos(4), "15/03/2022", 2)
r = basico(k, [c1, c2], "25/03/2022", prog="27/11/2022", liv="23/03/2024")
novo("AUD-F reincidência", "Reincidente pela lei, sem a marcação (favorável)", "Auditoria",
     "Furto transitado em 20/08/2019; novo furto em 15/03/2022 não marcado reincidente; SEEU 16% e 1/3.",
     "Auditoria: 'reincidente pela lei, mas o RSPE não marca' só como info; sem alerta de fração.",
     "Pelo CP, art. 63, é reincidente (trânsito anterior ao fato, menos de 5 anos). O SEEU aplica as frações do primário: favorece; "
     "política = não se impugna.", r,
     [AUD("reincidente-pela-lei-sem-marcacao", nivel="info"), AUD("percentual-de-progressao-diverge", presente=False),
      AUD("fracao-de-livramento-diverge", presente=False)])

k = K()
c1 = cr(k, FURTO, anos(1, 6), "03/03/2019", 1, transito="10/02/2020")
c2 = crime(proc_crim(k * 10 + 2, 2022), TRAF[0], anos(7), "11/08/2022", lei=DROGAS, tipo=TRAF[1], fp="60% - Art.112, VII", fl=L11,
           rc="S", re_="S")
r = basico(k, [c1, c2], "23/08/2022", prog="05/05/2027", liv="")
novo("AUD-F reincidência", "Reincidência específica sem anterior hedionda (tráfico)", "Auditoria",
     "Tráfico de 2022 marcado reincidente específico (60% e livramento vedado); única anterior: furto transitado em 2020.",
     "Auditoria: 'reincidência específica não demonstrada no RSPE' em alerta (devido 40% e livramento 2/3).",
     "Reincidência específica em hediondo/equiparado exige condenação anterior por hediondo/equiparado (LEP, art. 112, VII; STJ, Tema 1084: "
     "reincidente genérico em hediondo = 40%). No tráfico, o livramento só é vedado ao reincidente específico em crime da Lei de Drogas "
     "(Lei 11.343/06, art. 44, p. ú.; CP, art. 83, V): devido 2/3.", r,
     [AUD("reincidencia-especifica-nao-demonstrada-no-rspe", nivel="alerta")])

# =====================================================================================================================
# G. Unificação e soma das penas
# =====================================================================================================================
k = K()
c1, c2 = cr(k, FURTO_Q, anos(4), "02/02/2022", 1), cr(k, FURTO_Q, anos(3, 6), "14/04/2022", 2)
r = basico(k, [c1, c2], "27/04/2022", pena=anos(8), prog="16/08/2023", liv="25/04/2025")
novo("AUD-G soma", "Pena total maior que a soma das penas", "Auditoria", "Penas de 4a e 3a6m (soma 7a6m0d) e pena total impressa 8a0m0d.",
     "Auditoria: 'Soma das penas difere da pena total' em alerta, diferença 0a6m0d.",
     "4a0m0d + 3a6m0d = 7a6m0d (LEP, art. 111). Total 8a0m0d: 6 meses a mais adiam progressão, livramento e término.", r,
     [AUD("soma-das-penas-difere-da-pena-total", nivel="alerta", contem="0a6m0d")])

k = K()
c1, c2 = cr(k, FURTO_Q, anos(4), "02/02/2022", 1), cr(k, FURTO_Q, anos(3, 6), "14/04/2022", 2)
r = basico(k, [c1, c2], "27/04/2022", pena=anos(6), prog="18/02/2023", liv="25/04/2024")
novo("AUD-G soma", "Pena total menor que a soma (favorável)", "Auditoria", "Soma 7a6m0d e pena total impressa 6a0m0d, sem unificação.",
     "Auditoria: sem alerta de soma (no máximo informação: a correção aumentaria a pena).",
     "Erro favorável ao assistido; política: sem alerta.", r,
     [AUD("soma-das-penas-difere-da-pena-total", presente=False)])

k = K()
c1, c2 = cr(k, FURTO_Q, anos(4), "02/02/2022", 1), cr(k, FURTO_Q, anos(3, 6), "14/04/2022", 2)
r = basico(k, [c1, c2], "27/04/2022", prog="16/04/2023", liv="25/04/2025",
           extra_incs=[inc("UNIFICAÇÃO", "7a6m0d", "05/09/2023", "05/09/2023", procs="%s, %s" % (P(c1), P(c2)))])
novo("AUD-G soma", "Incidente de unificação usado para somar penas", "Auditoria",
     "Incidente UNIFICAÇÃO com pena 7a6m0d (a soma simples), sem concurso formal ou crime continuado.",
     "Auditoria: 'Incidente de unificação usado para somar penas (05/09/2023)' em alerta.",
     "Unificação (CP, arts. 70 e 71; LEP, art. 66, III, a) serve ao concurso formal e ao crime continuado; a soma de penas de processos "
     "distintos é somatório (LEP, art. 111). Pena 7a6m0d = soma: é somatório lançado como unificação, que o SEEU trata como pena única "
     "(perde-se a fração e a ordem de cada condenação - STJ, REsp 2.037.377/SC).", r,
     [AUD("unificacao-como-soma", nivel="alerta")])

# =====================================================================================================================
# H. Art. 75 do CP
# =====================================================================================================================
k = K()
cs = [cr(k, HOMQ, anos(15), f, n, fp="2/5 - Hediondo", fl=L23, vga="S", morte="S") for n, f in ((1, "10/10/2008"), (2, "24/11/2008"), (3, "05/01/2009"))]
r = basico(k, cs, "15/03/2009", prog="15/03/2027", liv="14/03/2039")
r["progressao_previsao_seeu"] = "10/05/2027"
novo("AUD-H art. 75", "Término além de 30 anos (fatos de 2008-2009)", "Auditoria",
     "Três homicídios qualificados (45 anos) por fatos de 2008-2009; preso sem interrupção desde 15/03/2009; término impresso em %s." % r["termino_previsao_seeu"],
     "Auditoria: 'Término além do limite de 30 anos (CP, art. 75): máximo em 14/03/2039' em alerta.",
     "Fatos anteriores a 23/01/2020: limite de 30 anos (CP, art. 75, redação anterior; CF, art. 5º, XL). 15/03/2009 + 30 anos − 1 dia "
     "(dia do começo incluído) = 14/03/2039. Política: aba mantém o término do SEEU; Auditoria alerta.", r,
     [AUD("limite-de-cumprimento-art-75", nivel="alerta", contem="14/03/2039")])

k = K()
c1 = cr(k, LATRO, anos(25), "28/08/2021", 1, fp="50% - Art.112, VI, a", fl=L11, vga="S", morte="S")
c2 = cr(k, HOMQ, anos(20), "28/08/2021", 2, fp="50% - Art.112, VI, a", fl=L11, vga="S", morte="S")
r = basico(k, [c1, c2], "09/09/2021", prog="10/09/2044", liv="")
novo("AUD-H art. 75", "Término além de 40 anos (fatos de 2021)", "Auditoria",
     "Latrocínio e homicídio qualificado de 2021 (45 anos); preso desde 09/09/2021; término impresso em %s." % r["termino_previsao_seeu"],
     "Auditoria: 'Término além do limite de 40 anos (CP, art. 75): máximo em 08/09/2061' em alerta.",
     "Fatos desde 23/01/2020: 40 anos (CP, art. 75, redação da Lei 13.964/2019). 09/09/2021 + 40 anos − 1 dia = 08/09/2061.", r,
     [AUD("limite-de-cumprimento-art-75", nivel="alerta", contem="08/09/2061")])

# =====================================================================================================================
# I. Monitoramento eletrônico lançado como interrupção (ficha)
# =====================================================================================================================
k = K()
c1 = cr(k, FURTO_Q, anos(7), "21/03/2021")
pe = "%07d-00.2026.8.12.0001" % (9900000 + k)
fora = (D("10/02/2024") - D("01/03/2023")).days - 1
r = basico(k, [c1], "04/04/2021", db="10/02/2024", prog="15/04/2027", liv="",
           interrompidos=fora,
           extra_evs=[interr("01/03/2023", "INTERRUPÇÃO DO CUMPRIMENTO DA PENA", P(c1)),
                      prisao("10/02/2024", P(c1), "RECAPTURA/REINÍCIO DE CUMPRIMENTO")])
r["livramento_previsao_seeu"] = "01/09/2027"
fic = {"tipo": "ficha_disciplinar", "nome": r["nome"], "cpf": r["cpf"], "cpf_em_branco": False, "data_nascimento": r["data_nascimento"],
       "nome_mae": r["nome_mae"], "filiacao": r["nome_mae"], "artigo": "ART 155", "data_prisao": "04/04/2021", "condenacao": "CONDENADO",
       "unidade": "ESTABELECIMENTO PENAL SIMULADO DE CAMPO GRANDE", "data_entrada": "05/04/2021", "sexo": "M", "conduta": "BOA",
       "data_impressao": "06/10/2026", "paginas": 2, "paginas_sem_texto": [], "autos": [pe],
       "eventos": [{"data": "05.04.2021", "texto": "Entrada na Unidade Penal: ESTABELECIMENTO PENAL SIMULADO DE CAMPO GRANDE, Procedente: DEPAC, Conforme OF 1/2021."},
                   {"data": "01.03.2023", "texto": "Saída da Unidade Penal: ESTABELECIMENTO PENAL SIMULADO DE CAMPO GRANDE, Destino: UNIDADE MISTA DE MONITORAMENTO VIRTUAL ESTADUAL, Motivo: Determinação Judicial, Conforme: %s." % pe},
                   {"data": "03.03.2023", "texto": "Entrada na Unidade Penal: UNIDADE MISTA DE MONITORAMENTO VIRTUAL ESTADUAL, Procedente: DECISÃO JUDICIAL, Conforme OF/CI %s." % pe},
                   {"data": "05.02.2024", "texto": "Saída da Unidade Penal: UNIDADE MISTA DE MONITORAMENTO VIRTUAL ESTADUAL, Destino: ESTABELECIMENTO PENAL SIMULADO DE CAMPO GRANDE, Motivo: Regressão de Regime, Conforme: %s." % pe},
                   {"data": "10.02.2024", "texto": "Entrada na Unidade Penal: ESTABELECIMENTO PENAL SIMULADO DE CAMPO GRANDE, Procedente: UMMVE, Conforme OF 2/2024."}],
       "historico_oculto": []}
dm = (D("05/02/2024") - D("03/03/2023")).days + 1
novo("AUD-I monitoramento", "Monitoramento eletrônico da execução lançado como interrupção", "Auditoria",
     "RSPE interrompe o cumprimento de 01/03/2023 a 10/02/2024; a ficha mostra a pessoa na UMMVE pelos autos da execução de 03/03/2023 a 05/02/2024.",
     "Auditoria: item 'Monitoramento eletrônico desta execução de 03/03/2023 a 05/02/2024 na ficha; o RSPE trata o período como interrupção' em alerta.",
     "Monitoramento eletrônico determinado na execução é cumprimento de pena (LEP, arts. 146-B e 112): %d dias (03/03/2023 a 05/02/2024, "
     "inclusive) sem cômputo. Política: aba mantém a data do SEEU com ressalva; Auditoria alerta." % dm, r,
     [AUD("rspe-x-ficha", contem="monitoramento"), AUD("rspe-x-ficha", contem="monitoramento", nivel="alerta")], ficha=fic)

# =====================================================================================================================
# J. Nascimento e idade
# =====================================================================================================================
k = K()
c1 = cr(k, FURTO_Q, anos(4), "20/05/2022")
r = basico(k, [c1], "01/06/2024", prog="19/01/2025", liv="29/09/2025", nasc="10/09/2004")
novo("AUD-J idade", "Menor de 18 anos na data do fato", "Auditoria", "Nascido em 10/09/2004; fato em 20/05/2022 (17 anos).",
     "Auditoria: 'idade de 17 anos no fato - erro de cadastro' em alerta.",
     "CP, art. 27, e CF, art. 228: menor de 18 é penalmente inimputável. Ou a data está errada, ou a condenação é nula: alerta.", r,
     [AUD("idade-no-fato-menor-de-18-erro-de-cadastro", nivel="alerta", contem="17")])

k = K()
c1 = cr(k, ESTEL, anos(4), "05/03/2021")
r = basico(k, [c1], "16/03/2024", prog="", liv="15/07/2025", nasc="02/02/1954", regime="Aberto - ATIVO",
           extra_incs=[inc(REG, "Semiaberto - Progressão de Regime", "10/09/2024", "02/09/2024"),
                       inc(REG, "Aberto - Progressão de Regime", "20/05/2025", "15/05/2025")])
novo("AUD-J idade", "72 anos no regime aberto: prisão domiciliar", "Auditoria", "Nascido em 02/02/1954 (72 anos), no regime aberto.",
     "Auditoria: 'Idade 72 anos no regime aberto: cabe prisão domiciliar (LEP, art. 117, I)' em alerta.",
     "LEP, art. 117, I: o condenado maior de 70 anos no regime aberto pode recolher-se em residência particular.", r,
     [AUD("idade-prisao-domiciliar-no-regime-aberto-lep-art", nivel="alerta")])

# =====================================================================================================================
# K. Confronto com a ficha
# =====================================================================================================================
def ficha_de(r, data_prisao, eventos, autos):
    return {"tipo": "ficha_disciplinar", "nome": r["nome"], "cpf": r["cpf"], "cpf_em_branco": False, "data_nascimento": r["data_nascimento"],
            "nome_mae": r["nome_mae"], "filiacao": r["nome_mae"], "artigo": "ART 155", "data_prisao": data_prisao, "condenacao": "CONDENADO",
            "unidade": "ESTABELECIMENTO PENAL SIMULADO DE CAMPO GRANDE", "data_entrada": eventos[0]["data"].replace(".", "/"), "sexo": "M",
            "conduta": "BOA", "data_impressao": "06/10/2026", "paginas": 2, "paginas_sem_texto": [], "autos": autos, "eventos": eventos,
            "historico_oculto": []}


k = K()
c1 = cr(k, FURTO_Q, anos(5), "20/02/2023")
r = basico(k, [c1], "18/05/2023", prog="18/01/2024", liv="16/05/2025")
fic = ficha_de(r, "02/03/2023", [{"data": "03.03.2023", "texto": "Entrada na Unidade Penal: ESTABELECIMENTO PENAL SIMULADO DE CAMPO GRANDE, Procedente: DEPAC, Conforme OF 7/2023."}],
               [r["processo_execucao"], P(c1)])
novo("AUD-K ficha", "Prisão da ficha anterior ao início no RSPE (sem cômputo)", "Auditoria",
     "Ficha: prisão em 02/03/2023 sem saída; RSPE só registra início em 18/05/2023.",
     "Auditoria: 'Prisão em 02/03/2023 na ficha; RSPE só registra início em 18/05/2023 (77 dias sem cômputo)' em alerta.",
     "CP, art. 42: a prisão provisória se computa. 02/03/2023 a 17/05/2023 = 77 dias (dia do começo incluído), posteriores ao fato de "
     "20/02/2023, sem soltura na ficha.", r,
     [AUD("rspe-x-ficha", contem="77 dias", nivel="alerta")], ficha=fic)

k = K()
c1 = cr(k, FURTO_Q, anos(6), "10/06/2022")
r = basico(k, [c1], "22/06/2022", db="22/06/2022", prog="10/07/2023", liv="", interrompidos=96,
           extra_evs=[interr("10/03/2024", "FUGA", P(c1)), prisao("15/06/2024", P(c1), "RECAPTURA/REINÍCIO DE CUMPRIMENTO")])
r["livramento_previsao_seeu"] = "26/09/2024"
fic = ficha_de(r, "22/06/2022", [
    {"data": "23.06.2022", "texto": "Entrada na Unidade Penal: ESTABELECIMENTO PENAL SIMULADO DE CAMPO GRANDE, Procedente: DEPAC, Conforme OF 3/2022."},
    {"data": "10.03.2024", "texto": "Saída da Unidade Penal: ESTABELECIMENTO PENAL SIMULADO DE CAMPO GRANDE, Destino: RESIDÊNCIA, Motivo: Alvará de Soltura, Conforme: %s." % P(c1)},
    {"data": "15.06.2024", "texto": "Entrada na Unidade Penal: ESTABELECIMENTO PENAL SIMULADO DE CAMPO GRANDE, Procedente: DEPAC, Conforme OF 9/2024."}],
    [r["processo_execucao"], P(c1)])
novo("AUD-K ficha", "Fuga no RSPE x alvará de soltura na ficha", "Auditoria",
     "RSPE lança fuga em 10/03/2024; a ficha registra saída por alvará de soltura no mesmo dia.",
     "Auditoria: 'Fuga no RSPE em 10/03/2024, mas a ficha registra saída por alvará de soltura' em alerta.",
     "Saída por alvará não é fuga (LEP, art. 50, II): o lançamento como fuga gera indício de falta grave, interrompe a data-base e pode "
     "levar a perda de remidos. Contradição verificável entre os documentos, contra o assistido: alerta.", r,
     [AUD("rspe-x-ficha", contem="alvará", nivel="alerta")], ficha=fic)

# =====================================================================================================================
# L. Fundamentações prontas (texto citado)
# =====================================================================================================================
k = K()
c1 = cr(k, FURTO_Q, anos(6), "03/08/2020", fp="1/6 - Comum")
r = basico(k, [c1], "14/08/2022", prog="13/08/2023", liv="13/08/2024")
novo("AUD-L fundamentação", "Fundamentação do alerta 1/6 x 16%", "Auditoria", "Furto qualificado de 2020, pena 6 anos, SEEU 1/6.",
     "Fundamentação do alerta cita o art. 112, I, da LEP na redação da Lei 13.964/2019, os 16% e pede a retificação; precedentes citados "
     "por inteiro (REsp 2.037.377/SC), sem lista deformada.",
     "LEP, art. 112, I (Lei 13.964/2019): 16%. Pena 2.190 dias: 1/6 = 365; 16% = 350,4 → 14 dias a mais. A citação de precedente deve ser "
     "a do julgado (STJ, REsp 2.037.377/SC), não fragmentos de data ('18, 06 e 2026').", r,
     [AUD("percentual-de-progressao-diverge", nivel="alerta", contem="14 dias"),
      C("aud_itens", "contem", ["art. 112, I", "Lei 13.964/2019", "16%"]),
      C("aud_itens", "nao_contem", ["2.037.377, 18", "18, 06 e 2026"])])

k = K()
c1 = cr(k, ROUBO, anos(7, 6), "12/10/2021", fp=P25, vga="S")
r = basico(k, [c1], "25/10/2021", db="18/11/2023", prog="12/06/2027", liv="",
           extra_incs=[inc("HOMOLOGAÇÃO DE FALTA GRAVE", "18/11/2023", "02/02/2024", "18/11/2023")],
           livramento_data_base_seeu="18/11/2023")
r["livramento_previsao_seeu"] = "17/08/2026"
novo("AUD-L fundamentação", "Fundamentação do alerta da Súmula 441", "Auditoria",
     "Data-base do livramento movida para a falta de 18/11/2023 (início em 25/10/2021).",
     "Alerta de data-base do livramento; fundamentação cita a Súmula 441/STJ e pede a data-base do início (25/10/2021).",
     "Súmula 441/STJ: 'A falta grave não interrompe o prazo para obtenção de livramento condicional.'", r,
     [AUD("data-base-do-livramento-alterada-por-falta-grave", nivel="alerta"), C("aud_itens", "contem", ["Súmula 441", "25/10/2021"])])

k = K()
c1 = cr(k, FURTO_Q, anos(5), "15/01/2023")
r = basico(k, [c1], "06/02/2024", prog="20/09/2024", liv="06/02/2026", remidos=45,
           extra_incs=[inc("REMIÇÃO", "45 Dia(s) Remido(s) - monitoração eletrônica cautelar - detração (Tema 1155)", "22/04/2024", "06/02/2024")])
novo("AUD-L fundamentação", "Fundamentação do alerta de detração lançada como remição", "Auditoria",
     "Remição de 45 dias com complemento 'monitoração eletrônica cautelar - detração (Tema 1155)'.",
     "Alerta 'Detração lançada como remição'; fundamentação cita CP, art. 42, STJ, Tema 1155, e LEP, art. 127, e pede o relançamento como detração.",
     "STJ, Tema 1155: o período de monitoração/recolhimento noturno cautelar é detração (CP, art. 42), imune à perda do art. 127 da LEP.", r,
     [AUD("detracao-como-remicao", nivel="alerta"), C("aud_itens", "contem", ["Tema 1155", "art. 42", "127"])])

k = K()
c1 = cr(k, ROUBO, anos(8), "30/04/2021", fp=P25, vga="S")
r = basico(k, [c1], "19/05/2021", db="22/07/2024", prog="17/08/2027", liv="", interrompidos=81,
           extra_evs=[interr("02/05/2024", "FUGA"), prisao("22/07/2024", P(c1), "RECAPTURA/REINÍCIO DE CUMPRIMENTO")])
r["livramento_previsao_seeu"] = "07/08/2024"
for e in r["_eventos"]:
    e["processos"] = e["processos"] or P(c1)
novo("AUD-L fundamentação", "Fundamentação do ponto de recaptura sem falta homologada", "Auditoria",
     "Fuga em 02/05/2024 e data-base na recaptura (22/07/2024), sem falta homologada.",
     "Item de recaptura sem falta em verificar; fundamentação cita as Súmulas 533 e 534 do STJ e a data-base anterior (19/05/2021).",
     "Súmula 533/STJ (PAD indispensável para reconhecer falta) e Súmula 534/STJ (a falta reconhecida interrompe a contagem). Sem falta "
     "homologada, a data-base é 19/05/2021.", r,
     [AUD("data-base-movida-para-a-recaptura-sem-falta-homo", nivel="verificar"),
      C("aud_itens", "contem", ["533", "534", "19/05/2021"])])

NOTAS = {
 "S4004": [(0, "O programa mostra 'Cumprimento não iniciado no SEEU' em info, não 'Pena não iniciada' em verificar. Guia transitada sem nenhum "
           "lançamento deve ser iniciada (LEP, arts. 105 e 106); mas, se a pessoa está solta, a demora não a prejudica (a executória corre). "
           "Escolha de nível discutível.", True)],
 "S4014": [(2, "Com o segundo regime inicial, o item da data-base na guia nova sai em verificar; sem ele (caso S4013) sai em alerta. Pela "
           "política do usuário (data-base contrária à lei: Auditoria alerta) e pelo Tema 1006/STJ, o nível deveria ser alerta; o alerta de "
           "'mais de um regime inicial' já aparece, mas a data certa (11/03/2021) fica só no item amarelo.", False)],
 "S4027": [(0, "Nenhum item aponta a prisão desta execução lançada como interrupção 'por prisão em outro processo': o programa só "
           "mostra 'Execução suspensa: preso em outro processo' (info). O processo citado integra esta execução; desde 10/01/2024 a pessoa "
           "segue presa por ela e nada é computado (CP, art. 42; LEP, art. 111). O programa parece exigir um evento de prisão no mesmo dia "
           "para enxergar a custódia; o SEEU real lança a interrupção sozinha.", False)],
 "S4034": [(0, "O programa dá alerta; o gabarito diz verificar porque a tese da duplicidade não é pacífica: o art. 127 da LEP fala em "
           "'até 1/3 do tempo remido' e parte da jurisprudência admite que a segunda falta alcance o saldo remanescente. O RSPE é "
           "verificável (não há remição entre as faltas), mas o direito é discutível: nível amarelo seria o coerente com a regra dos níveis.", True)],
 "S4035": [(0, "Alerta para remição lançada em dobro com o saldo também em dobro (90): o erro aumenta a pena cumprida e favorece o "
           "assistido. Pela política (só alerta o que prejudica), deveria ser no máximo info.", False)],
 "S4051": [(1, "O item aparece em verificar (escolha 7.14.6 descrita no relatório). A política fixada para esta base diz que o "
           "monitoramento lançado como interrupção é alerta na Auditoria (aba mantém a data do SEEU com ressalva). Monitoramento por ordem "
           "da execução é cumprimento de pena (LEP, art. 146-B): 340 dias sem cômputo.", False)],
 "S4056": [(2, "A fundamentação pronta sai com 'Nesse sentido: STJ, Temas 1084, 1196, 1354, 2.037.377, 18, 06 e 2026; STF, Tema 1169': "
           "o REsp 2.037.377/SC (3ª Seção, 18/06/2026) foi picado como se fossem temas. Citação errada numa peça.", False)],
}
for c in CASOS:
    for i, nota, dec in NOTAS.get(c["id"], []):
        c["checks"][i]["nota"] = nota
        if dec:
            c["checks"][i]["decisao"] = True
json.dump(CASOS, open(os.path.join(AQUI, "auditoria.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("%d casos gravados" % len(CASOS))
