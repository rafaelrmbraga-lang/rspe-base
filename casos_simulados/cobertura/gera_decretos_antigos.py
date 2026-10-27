"""Casos simulados da área "decretos_antigos": indulto e comutação pelos decretos de 2000 a 2021 e de 2023 (aba Indulto,
tabela de decretos). Faixa k = 7001 a 7099. Gabarito calculado pelo texto de cada decreto (conferido no Planalto, salvo onde
o caso diz "texto não confirmado"), com a convenção do SEEU (ano de 365 dias, mês de 30, dia do começo incluído, fração em
dias arredondada para baixo). Uso: python3 gera_decretos_antigos.py  (grava decretos_antigos.json ao lado)."""
import os, sys, json
from datetime import timedelta
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from base_casos import *  # noqa

LEI_6368 = "6368/76 - Lei de Tóxicos"
LAVAGEM = "9613/98 - Lavagem de Dinheiro"

# publicação e referência de cada decreto (id do programa)
DEC = {"2000": ("22/11/2000", "25/12/2000"), "2001": ("14/11/2001", "25/12/2001"), "2002": ("05/12/2002", "25/12/2002"),
       "2003": ("02/12/2003", "25/12/2003"), "2004": ("03/12/2004", "25/12/2004"), "2005": ("16/12/2005", "25/12/2005"),
       "2006": ("20/12/2006", "25/12/2006"), "2007": ("12/12/2007", "25/12/2007"), "2008": ("23/12/2008", "25/12/2008"),
       "2009": ("23/12/2009", "25/12/2009"), "2010": ("31/12/2010", "25/12/2010"), "2011": ("22/12/2011", "25/12/2011"),
       "2012": ("26/12/2012", "25/12/2012"), "2013": ("24/12/2013", "25/12/2013"), "2014": ("24/12/2014", "25/12/2014"),
       "2015": ("24/12/2015", "25/12/2015"), "2016": ("23/12/2016", "25/12/2016"), "2017_maes": ("13/04/2017", "14/05/2017"),
       "2017": ("22/12/2017", "25/12/2017"), "2018_maes": ("11/05/2018", "13/05/2018"), "2019": ("24/12/2019", "25/12/2019"),
       "2020": ("24/12/2020", "25/12/2020"), "2021": ("24/12/2021", "25/12/2021"), "2023": ("22/12/2023", "25/12/2023")}

ROTULO = {"cabe": "Cabe", "ver": "A verificar", "nao": "Não cabe", "imp": "Impeditivo", "fora": "Não alcançado",
          "conc": "Concedido", "indef": "Indeferido"}


def T(n):
    a, m, d = amd(n)
    return "%da%dm%dd" % (a, m, d)


def cump(ini, ref):
    """dias de custódia contínua de ini a ref, os dois incluídos (CP, art. 10)."""
    return (D(ref) - D(ini)).days + 1


def _item(did):
    return '"id": "%s", "ano"' % did


_DENTRO = '(?:(?!"id": ")[\\s\\S])*?'


def DECR(did, s=None, contem=(), sem=(), nota="", decisao=False):
    """Verificação de um decreto na tabela da aba Indulto (campo "dec"): situação (s) e textos do próprio item."""
    p = _item(did)
    if s:
        p += '(?=%s"s": "(?:%s)")' % (_DENTRO, s)
    for t in ([contem] if isinstance(contem, str) else contem):
        p += "(?=%s%s)" % (_DENTRO, _re_lit(t))
    for t in ([sem] if isinstance(sem, str) else sem):
        p += '(?!(?:(?!"id": ")[\\s\\S])*?%s)' % _re_lit(t)
    ch = C("dec", "regex", p, nota)
    if decisao:
        ch["decisao"] = True
    return ch


def _re_lit(t):
    import re
    return re.escape(t).replace("\\ ", " ")


def sent(fato, dias=150):
    return F(D(fato) + timedelta(days=dias))


def montar(k, crimes, ini, fuga=None, ev_extra=(), inc=(), interrompidos=0, **kw):
    """RSPE com custódia contínua desde ini. Se a pena já estaria quase toda cumprida em 05/10/2026, lança uma fuga na data
    `fuga` (sempre depois da publicação do último decreto testado) e a recaptura calculada para restar 180 a 400 dias de pena
    em 05/10/2026 (término depois de 31/03/2027)."""
    pena = sum(c["_dias"] for c in crimes)
    procs = ", ".join(sorted({c["processo_criminal"] for c in crimes}))
    evs = [prisao(ini, procs)] + list(ev_extra)
    if fuga is None:
        assert pena - (cump(ini, F(GER)) - interrompidos) >= 200, ("caso %d precisa de fuga" % k)
    else:
        ate_fuga = cump(ini, fuga)
        resto = min(400, pena - ate_fuga - 10)
        assert resto >= 180, ("caso %d: pena restante curta na fuga (%d)" % (k, resto))
        depois = pena - resto - ate_fuga
        R = GER - timedelta(days=depois - 1)
        assert R > D(fuga)
        interrompidos = (R - D(fuga)).days - 1
        evs += [interr(fuga, "FUGA", procs), prisao(F(R), procs, "RECAPTURA/REINÍCIO DE CUMPRIMENTO")]
    for c in crimes:  # sentença e trânsito coerentes
        assert D(c["data_sentenca"]) >= D(c["data_infracao"])
    return rspe(k, crimes, evs, list(inc), ini=ini, interrompidos=interrompidos, **kw)


CASOS = []


def novo(k, situacao, esperado, conta, r, checks, manuais=None, titulo=None):
    c = caso(k, "K-decretos antigos", titulo or situacao, conta, r, checks, manuais=manuais)
    c["aba"] = "Indulto"
    c["situacao"] = situacao
    c["esperado"] = esperado
    CASOS.append(c)
    return c


def falta(fato, dec):
    return inc_("HOMOLOGAÇÃO DE FALTA GRAVE", fato, dec, fato)


def inc_(tipo, compl, dec, ref, sit="CONCEDIDO", procs=""):
    return {"tipo": tipo, "motivo": "", "complemento": compl, "data": "", "data_decisao": dec, "data_referencia": ref,
            "processos": procs, "situacao": sit}


def regime(compl, data):
    return inc_(REG, compl, data, data)


FURTO_Q = dict(artigo="155, § 4º, I", tipo="§ 4º, I: furto qualificado, Reclusão: 2 a 8 anos E Multa")
FURTO = dict(artigo="155, caput", tipo="CAPUT: furto, Reclusão: 1 a 4 anos E Multa")
ESTEL = dict(artigo="171, caput", tipo="CAPUT: estelionato, Reclusão: 1 a 5 anos E Multa")
ROUBO = dict(artigo="157, caput", tipo="CAPUT: roubo, Reclusão: 4 a 10 anos E Multa", vga="S")
ROUBO_CONC = dict(artigo="157, § 2º, II", tipo="§ 2º, II: roubo majorado pelo concurso de pessoas, Reclusão: 4 a 10 anos E Multa", vga="S")
TRAF = dict(artigo="33, caput", tipo="CAPUT: tráfico de drogas, Reclusão: 5 a 15 anos E Multa", lei=DROGAS, fp="2/5 - Hediondo", fl="2/3 - Hediondo")
TRAF_PRIV = dict(artigo="33, § 4º", tipo="§ 4º: tráfico privilegiado, Reclusão: 5 a 15 anos E Multa", lei=DROGAS)
ASSOC = dict(artigo="35, caput", tipo="CAPUT: associação para o tráfico, Reclusão: 3 a 10 anos E Multa", lei=DROGAS)
HOMIC = dict(artigo="121, caput", tipo="CAPUT: homicídio simples, Reclusão: 6 a 20 anos", vga="S")


def cr(k, n, pena, fato, ano=None, **kw):
    """crime n do caso k: sentença 150 dias depois do fato e trânsito 60 dias depois da sentença (o construtor), salvo kw."""
    proc = "%07d-00.%s.8.12.0001" % (8800000 + k * 10 + n, ano or D(fato).year)
    kw.setdefault("sentenca", sent(fato))
    return crime(proc, pena_dias=pena, fato=fato, **kw)


def checa_transito(c, did):
    pub = D(DEC[did][0])
    for x in c["rspe"]["_crimes"]:
        if D(x["data_infracao"]) <= D(DEC[did][1]) and D(x["data_sentenca"]) <= pub:
            assert D(x["transito_mp"]) <= pub, (c["id"], did, "trânsito depois da publicação")


# ---------------------------------------------------------------------------------------------------------------------------
# Decreto 3.667/2000
k = 7001
c1 = cr(k, 1, anos(3), "10/02/1999", **FURTO_Q)
n = cump("10/02/1999", "25/12/2000")
novo(k, "Decreto 3.667/2000, art. 1º, I: furto qualificado de 3 anos, primário, 1/3 cumprido",
     "2000: Cabe o indulto (art. 1º, I), cumpriu %s, exigido 1a0m0d" % T(n),
     "Pena 3 anos = 1.095 dias, não superior a 4 anos (art. 1º, I). Preso em 10/02/1999 sem interrupção: em 25/12/2000 "
     "cumpriu %d dias (%s). Exigido 1/3 = 365 dias (1a0m0d). Sem falta, crime não vedado (art. 10). Fundamento: Decreto "
     "3.667/2000, art. 1º, I (texto conferido no Planalto)." % (n, T(n)),
     montar(k, [c1], "10/02/1999", fuga="10/02/2001"),
     [DECR("2000", "cabe", ["Indulto", "exigido 1a0m0d"])])

k = 7002
c1 = cr(k, 1, anos(7), "01/03/1998", **ESTEL)
n = cump("01/03/1998", "25/12/2000")
red = anos(7) // 4
novo(k, "Decreto 3.667/2000, art. 2º: comutação de 1/4 da pena (estelionato de 7 anos, primário)",
     "2000: Cabe a comutação (art. 2º), exigido 1a9m3d; redução de 1/4 da pena = %s" % T(red),
     "Pena 7 anos = 2.555 dias: acima do teto de 4 anos do art. 1º, I; sem 60 anos (nascido em 1975); sem 20 anos de prisão. "
     "Indulto não cabe. Comutação (art. 2º): 1/4 cumprido = 638 dias (1a9m3d); cumpriu %d dias (%s) em 25/12/2000. "
     "Redução: o art. 2º diz que o condenado 'terá comutada a pena' de 1/4; só o parágrafo único manda calcular sobre o "
     "remanescente para quem já teve comutação anterior - logo, para o primeiro benefício, a base é a pena: 2.555/4 = %d dias "
     "(%s). Fundamento: Decreto 3.667/2000, art. 2º e p. ú. (conferido no Planalto)." % (n, T(n), red, T(red)),
     montar(k, [c1], "01/03/1998", fuga="10/02/2001"),
     [DECR("2000", "cabe", "Comutação"),
      DECR("2000", None, "redução de %s" % T(red), nota="base = pena total, pela letra do art. 2º (tese: há quem calcule sobre o remanescente)", decisao=True)])

k = 7003
c1 = cr(k, 1, anos(5), "05/05/1999", **ROUBO_CONC)
novo(k, "Roubo majorado pelo concurso de pessoas: vedado em 2000 (art. 10, III: roubo qualificado), não vedado em 2001 (só com arma de fogo)",
     "2000: Impeditivo. 2001: não é impeditivo; indulto do art. 1º, I a verificar (condições pessoais do § 1º, crime violento) "
     "ou comutação cabível",
     "Decreto 3.667/2000, art. 10, III: veda o roubo qualificado (CP, art. 157, § 2º) - inclui o inciso II. Decreto 4.011/2001, "
     "art. 10, III: veda só o 'roubo qualificado com o emprego de arma de fogo' (§ 2º, I). Em 2001: pena 5 anos (1.825 dias) "
     "até 6 anos; 1/3 = 608 dias; cumpriu %d dias em 25/12/2001. Como o crime tem violência, o indulto depende de o juiz "
     "constatar condições pessoais favoráveis (art. 1º, § 1º): a verificar. Comutação (art. 2º): 1/4 = 456 dias, atendida. "
     "(Textos conferidos no Planalto.)" % cump("05/05/1999", "25/12/2001"),
     montar(k, [c1], "05/05/1999", fuga="10/02/2002"),
     [DECR("2000", "imp"), DECR("2001", "cabe|ver"), DECR("2001", None, sem='"s": "imp"')])

# Decreto 4.011/2001
k = 7004
c1 = cr(k, 1, anos(6), "01/06/1999", **FURTO_Q)
n = cump("01/06/1999", "25/12/2001")
novo(k, "Decreto 4.011/2001, art. 1º, I: furto qualificado de 6 anos (no teto), primário",
     "2001: Cabe o indulto (art. 1º, I), cumpriu %s, exigido 2a0m0d" % T(n),
     "Pena 6 anos = 2.190 dias, 'não superior a seis anos' (art. 1º, I). Exigido 1/3 = 730 dias (2a0m0d). Cumpriu %d dias (%s) "
     "em 25/12/2001. Fundamento: Decreto 4.011/2001, art. 1º, I (conferido no Planalto)." % (n, T(n)),
     montar(k, [c1], "01/06/1999", fuga="10/02/2002"),
     [DECR("2001", "cabe", ["Indulto", "exigido 2a0m0d"])])

# Decreto 4.495/2002
k = 7005
c1 = cr(k, 1, anos(5), "10/01/2000", **ROUBO)
n = cump("10/01/2000", "25/12/2002")
red = anos(5) // 4
novo(k, "Decreto 4.495/2002: roubo (crime violento) com falta grave 18 meses antes da publicação: indulto barrado (2 anos), comutação cabe",
     "2002: Cabe a comutação (art. 2º), redução de 1/4 da pena = %s; indulto não cabe pela falta nos 2 anos (art. 1º, § 1º, I)" % T(red),
     "Roubo simples, 5 anos (1.825 dias), primário, preso em 10/01/2000. Falta grave homologada, praticada em 10/06/2001. "
     "Publicação em 05/12/2002: a janela de 12 meses (art. 3º, I) começa em 05/12/2001 - a falta fica fora; a de 2 anos do "
     "crime violento (art. 1º, § 1º, I) começa em 05/12/2000 - a falta fica dentro, e ela vale só para o indulto. Indulto: "
     "barrado. Comutação (art. 2º): 1/4 = 456 dias; cumpriu %d dias; redução de 1/4 da pena = %d dias (%s). (Conferido no Planalto.)"
     % (n, red, T(red)),
     montar(k, [c1], "10/01/2000", fuga="10/02/2003", inc=[falta("10/06/2001", "10/08/2001")]),
     [DECR("2002", "cabe", "Comutação")])

k = 7006
c1 = cr(k, 1, anos(9), "10/01/2000", **ROUBO)
novo(k, "Decreto 4.495/2002: roubo com falta grave homologada 5 meses antes da publicação: nem indulto nem comutação (art. 3º, I)",
     "2002: Não cabe (falta grave nos 12 meses, art. 3º, I, que vale para indulto e comutação). 2003: Não cabe (falta nos 24 meses do crime violento, art. 3º, I)",
     "Roubo simples, 9 anos, primário, preso em 10/01/2000; falta grave praticada em 10/07/2002, homologada em 10/09/2002. "
     "Decreto 4.495/2002, art. 3º, I: inexistência de sanção por falta grave nos 12 meses anteriores à publicação "
     "(05/12/2001 a 05/12/2002) é requisito do indulto E da comutação; a janela maior de 2 anos do art. 1º, § 1º, I "
     "acrescenta exigência ao indulto do crime violento, não tira a do art. 3º da comutação. Logo a comutação (1/4 = 821 dias; "
     "cumpridos %d) também cai. Decreto 4.904/2003, art. 3º, I: crime violento, janela de 24 meses da publicação "
     "(02/12/2001 a 02/12/2003), para os dois benefícios: falta dentro. (Conferido no Planalto.)" % cump("10/01/2000", "25/12/2002"),
     montar(k, [c1], "10/01/2000", fuga="10/02/2004", inc=[falta("10/07/2002", "10/09/2002")]),
     [DECR("2002", "nao", "falta"), DECR("2003", "nao", "falta")])

k = 7007
c1 = cr(k, 1, anos(3), "10/03/2001", artigo="12, caput", tipo="CAPUT: tráfico de entorpecentes, Reclusão: 3 a 15 anos E Multa", lei=LEI_6368)
novo(k, "Decreto 4.495/2002, art. 7º, § 2º: tráfico (Lei 6.368, art. 12) com pena de 3 anos - a vedação legal ao indulto do tráfico continua",
     "2002: não cabe o indulto: Impeditivo (Lei 8.072/1990, art. 2º, I); no mínimo, não pode aparecer 'Cabe'",
     "O § 2º do art. 7º do Decreto 4.495/2002 afasta 'as restrições deste artigo' para pena até 4 anos. Mas a proibição de "
     "indulto ao tráfico vem da Lei 8.072/1990, art. 2º, I (e da CF, art. 5º, XLIII), que o decreto não pode afastar. Cumpriu "
     "%d dias de 1.095 (1/3 = 365 atendido), mas o crime é impeditivo por lei." % cump("10/03/2001", "25/12/2002"),
     montar(k, [c1], "10/03/2001", fuga="10/02/2003"),
     [DECR("2002", "imp|nao|ver"),
      DECR("2002", "imp", nota="Lei 8.072/90, art. 2º, I prevalece sobre o art. 7º, § 2º do decreto", decisao=True)])

k = 7008
c1 = cr(k, 1, anos(4), "10/01/2000", **FURTO_Q)
c2 = cr(k, 2, anos(3), "10/01/2000", **ESTEL)
n = cump("10/01/2000", "25/12/2002")
novo(k, "Decreto 4.495/2002, art. 1º, III: pena acima de 6 anos e menor de 21 anos ao tempo do crime",
     "2002: Cabe o indulto (art. 1º, III), exigido 2a4m1d",
     "Furto qualificado (4 anos) + estelionato (3 anos) = 7 anos = 2.555 dias, primário, nascido em 01/05/1981: tinha 18 anos "
     "nos fatos (10/01/2000). Art. 1º, III: pena superior a 6 anos, menos de 21 anos ao tempo do crime, 1/3 cumprido = 851 dias "
     "(2a4m1d). Cumpriu %d dias (%s) em 25/12/2002. (Conferido no Planalto.)" % (n, T(n)),
     montar(k, [c1, c2], "10/01/2000", fuga="10/02/2003", nasc="01/05/1981"),
     [DECR("2002", "cabe", ["Indulto", "III"])])

# Decreto 4.904/2003
k = 7009
c1 = cr(k, 1, anos(10), "01/06/2000", rc="S", **ESTEL)
n = cump("01/06/2000", "25/12/2003")
red = (anos(10) - n) // 5
novo(k, "Decreto 4.904/2003, art. 2º: comutação do reincidente (1/3 cumprido; redução de 1/5 do remanescente)",
     "2003: Cabe a comutação, exigido 3a4m1d; redução de %s; remanescente passa de %s para %s" % (T(red), T(anos(10) - n), T(anos(10) - n - red)),
     "Estelionato, 10 anos (3.650 dias), reincidente, preso em 01/06/2000. Indulto: pena acima de 6 anos (I), sem 60 anos (II), "
     "sem 20 anos (III). Comutação (art. 2º): 1/3 = 1.216 dias (3a4m1d); cumpriu %d dias (%s). Redução de 1/5 da pena "
     "remanescente: (3.650 - %d) / 5 = %d dias (%s). (Conferido no Planalto.)" % (n, T(n), n, red, T(red)),
     montar(k, [c1], "01/06/2000", fuga="10/02/2004"),
     [DECR("2003", "cabe", ["Comutação", "exigido 3a4m1d", "redução de %s" % T(red)])])

k = 7010
c1 = cr(k, 1, anos(6), "10/01/2001", **ROUBO)
novo(k, "Decreto 4.904/2003: roubo com falta grave 20 meses antes da publicação: janela de 24 meses do crime violento",
     "2003: Não cabe (falta grave nos 24 meses, art. 3º, I)",
     "Roubo simples, 6 anos, primário, preso em 10/01/2001; cumpriu %d dias em 25/12/2003 (1/3 = 730). Falta grave homologada, "
     "praticada em 10/04/2002. Art. 3º, I do Decreto 4.904/2003: para crime com violência a janela é de 24 meses contados da "
     "publicação (02/12/2001 a 02/12/2003), para indulto e comutação. (Conferido no Planalto.)" % cump("10/01/2001", "25/12/2003"),
     montar(k, [c1], "10/01/2001", fuga="10/02/2004", inc=[falta("10/04/2002", "10/06/2002")]),
     [DECR("2003", "nao", "falta")])

# Decreto 5.295/2004
k = 7011
c1 = cr(k, 1, anos(4), "15/03/2003", sentenca="01/09/2004", transito="01/11/2004", **FURTO_Q)
gap = (D("10/03/2026") - D("20/10/2004")).days - 1
det = cump("15/03/2003", "20/10/2004")
r = montar(k, [c1], "15/03/2003", interrompidos=gap,
           ev_extra=[interr("20/10/2004", "LIBERDADE PROVISÓRIA", c1["processo_criminal"]),
                     prisao("10/03/2026", c1["processo_criminal"], "PRISÃO DEFINITIVA")])
novo(k, "Decreto 5.295/2004, art. 3º: só prisão provisória até a data - a detração conta no requisito temporal",
     "2004: Cabe o indulto (art. 1º, I), com a prisão provisória contada como pena cumprida (%s; exigido 1a4m1d)" % T(det),
     "Furto qualificado, 4 anos (1.460 dias), primário. Flagrante de 15/03/2003 a 20/10/2004 (liberdade provisória), sentença "
     "01/09/2004, trânsito 01/11/2004, prisão definitiva só em 10/03/2026. Art. 3º do Decreto 5.295/2004: o tempo de detração "
     "(CP, art. 42) é computado para o requisito temporal. %d dias (%s) >= 1/3 = 486 dias (1a4m1d). (Conferido no Planalto.)" % (det, T(det)),
     r, [DECR("2004", "cabe", ["Indulto", "exigido 1a4m1d"])])

# Decreto 5.620/2005 (texto não buscado no Planalto: art. 1º, I e art. 8º iguais aos de 2004 e 2006, pelo que se sabe do decreto)
k = 7012
c1 = cr(k, 1, anos(5), "01/03/2004", **ROUBO)
n = cump("01/03/2004", "25/12/2005")
novo(k, "Decreto 5.620/2005, art. 1º, I: roubo simples de 5 anos - o crime violento não tem mais a cláusula das condições pessoais",
     "2005: Cabe o indulto (art. 1º, I), cumpriu %s, exigido 1a8m3d" % T(n),
     "Roubo simples (sem majorante), 5 anos (1.825 dias), primário, preso em 01/03/2004. Pena até 6 anos; 1/3 = 608 dias "
     "(1a8m3d); cumpriu %d dias (%s) em 25/12/2005. O roubo simples não está no rol de vedações (tortura, terrorismo, tráfico, "
     "hediondos) e o decreto não condiciona o crime violento a exame de condições pessoais. Texto do Decreto 5.620/2005 não "
     "confirmado no Planalto (mesma redação dos Decretos 5.295/2004 e 5.993/2006, conferidos)." % (n, T(n)),
     montar(k, [c1], "01/03/2004", fuga="10/02/2006"),
     [DECR("2005", "cabe", ["Indulto", "exigido 1a8m3d"])])

# Decreto 5.993/2006
k = 7013
c1 = cr(k, 1, anos(11), "01/02/2002", rc="S", **FURTO_Q)
c2 = cr(k, 2, anos(8), "10/01/2002", sentenca="10/06/2006", transito="10/08/2006", rc="S", **ESTEL)
n = cump("01/02/2002", "25/12/2006")
novo(k, "Decreto 5.993/2006, art. 2º, p. ú.: comutação anterior (2005) concedida - nova comutação sem novo requisito temporal",
     "2005: Concedido (comutação, incidente). 2006: Cabe a comutação, sem exigir 1/3 da nova soma (comutação anterior)",
     "Furto qualificado 11 anos + estelionato 8 anos (sentença de 10/06/2006, somado em 2006) = 19 anos (6.935 dias), "
     "reincidente, preso desde 01/02/2002. Comutação do Decreto 5.620/2005 concedida em 10/03/2006. Em 25/12/2006 cumpriu %d "
     "dias, abaixo de 1/3 da soma (2.311). O art. 2º, p. ú. do Decreto 5.993/2006 manda calcular a nova comutação de quem já "
     "teve comutação 'sem necessidade de novo requisito temporal': cabe, redução de 1/5 do remanescente (descontada a "
     "comutação anterior, que o RSPE não quantifica). Indulto: pena acima de 6 anos, sem 60 anos nem 15 anos. (Conferido no Planalto.)" % n,
     montar(k, [c1, c2], "01/02/2002",
            inc=[inc_("COMUTAÇÃO DE PENA", "Decreto 5.620/2005", "10/03/2006", "25/12/2005")]),
     [DECR("2005", "conc"), DECR("2006", "cabe", "Comutação")])

k = 7014
c1 = cr(k, 1, anos(5), "01/02/2005", **FURTO_Q)
n = cump("01/02/2005", "25/12/2006")
novo(k, "Decreto 5.993/2006, art. 1º, I: sursis concedido no RSPE sem processo indicado",
     "2006: A verificar (o art. 1º, I exige pena sem sursis; conferir a que pena o sursis se refere)",
     "Furto qualificado, 5 anos, primário, preso em 01/02/2005; cumpriu %d dias em 25/12/2006 (1/3 = 608). O RSPE traz "
     "'suspensão condicional da pena' concedida em 15/04/2003, sem os processos. O art. 1º, I (e o art. 2º) exige pena que não "
     "tenha obtido suspensão condicional; se a pena suspensa integra a soma, o requisito e a conta mudam. Não se pode afirmar o "
     "benefício sem conferir. (Conferido no Planalto.)" % n,
     montar(k, [c1], "01/02/2005", fuga="10/02/2007",
            inc=[inc_("SUSPENSÃO CONDICIONAL DA PENA", "Sursis - 2 anos", "15/04/2003", "15/04/2003")]),
     [DECR("2006", "ver", "sursis")])

# Decretos 6.294/2007, 6.706/2008, 7.046/2009: tráfico privilegiado
k = 7015
c1 = cr(k, 1, anos(4), "10/03/2007", **TRAF_PRIV)
n08, n09 = cump("10/03/2007", "25/12/2008"), cump("10/03/2007", "25/12/2009")
novo(k, "Tráfico privilegiado em 2007 (vedado), 2008 (ressalva da mercancia) e 2009 (não vedado)",
     "2007: Impeditivo. 2008: A verificar (conferir se a conduta configurou mercancia). 2009: Cabe o indulto (art. 1º, I)",
     "Tráfico privilegiado (art. 33, § 4º), 4 anos (1.460 dias), primário, preso em 10/03/2007; 1/3 = 486 dias. Decreto "
     "6.294/2007, art. 8º, I: veda o tráfico do art. 33 'excetuadas as hipóteses dos §§ 2º e 3º' - o § 4º fica vedado pela letra. "
     "Decreto 6.706/2008, art. 8º, I: ressalva os §§ 2º a 4º 'desde que a conduta típica não tenha configurado a prática da "
     "mercancia' (cumpriu %d dias: o tempo basta, falta conferir a mercancia). Decreto 7.046/2009, art. 8º, I: veda só o art. "
     "33, caput e § 1º, e arts. 34 a 37 - o privilegiado não é vedado; cumpriu %d dias. (Textos conferidos no Planalto.)" % (n08, n09),
     montar(k, [c1], "10/03/2007", fuga="10/02/2010"),
     [DECR("2007", "imp"), DECR("2008", "ver", "mercancia"), DECR("2009", "cabe", "Indulto")])

k = 7016
c1 = cr(k, 1, anos(8), "01/03/2006", **ESTEL)
n = cump("01/03/2006", "25/12/2008")
novo(k, "Decreto 6.706/2008, art. 1º, I: pena de exatamente 8 anos está no teto ('não superior a oito anos')",
     "2008: Cabe o indulto (art. 1º, I), exigido 2a8m3d",
     "Estelionato, 8 anos = 2.920 dias, primário, preso em 01/03/2006. 1/3 = 973 dias (2a8m3d); cumpriu %d dias (%s) em "
     "25/12/2008. (Conferido no Planalto.)" % (n, T(n)),
     montar(k, [c1], "01/03/2006"),
     [DECR("2008", "cabe", ["Indulto", "exigido 2a8m3d"])])

k = 7017
c1 = cr(k, 1, anos(6), "01/03/2006", **ESTEL)
c2 = cr(k, 2, anos(2, 0, 2), "01/03/2006", **FURTO_Q)
n = cump("01/03/2006", "25/12/2008")
red = (2922 - n) // 4
novo(k, "Decreto 6.706/2008: soma de 8a0m2d passa do teto de 8 anos - cabe só a comutação",
     "2008: Cabe a comutação (art. 2º), redução de 1/4 do remanescente = %s" % T(red),
     "Estelionato 6 anos + furto qualificado 2a0m2d = 8a0m2d = 2.922 dias (acima de 2.920). Indulto I: pena acima de 8 anos; "
     "II: sem 60 anos; III: sem 15 anos. Comutação: 1/4 = 730 dias; cumpriu %d dias; redução de 1/4 do remanescente "
     "(2.922 - %d = %d) = %d dias (%s). (Conferido no Planalto.)" % (n, n, 2922 - n, red, T(red)),
     montar(k, [c1, c2], "01/03/2006"),
     [DECR("2008", "cabe", ["Comutação", "redução de %s" % T(red)])])

# Decreto 7.046/2009
k = 7018
c1 = cr(k, 1, anos(3), "10/01/2008", **ASSOC)
novo(k, "Decreto 7.046/2009, art. 8º, I: associação para o tráfico (art. 35) é vedada",
     "2009: Impeditivo",
     "Associação para o tráfico (Lei 11.343, art. 35), 3 anos, preso em 10/01/2008; cumpriu %d dias (1/3 = 365). O art. 8º, I "
     "do Decreto 7.046/2009 veda o tráfico 'nos termos do art. 33, caput e § 1º, e dos arts. 34 a 37'. (Conferido no Planalto.)"
     % cump("10/01/2008", "25/12/2009"),
     montar(k, [c1], "10/01/2008", fuga="10/02/2010"),
     [DECR("2009", "imp")])

k = 7019
c1 = cr(k, 1, anos(5), "10/01/2007", **TRAF)
c2 = cr(k, 2, anos(1, 6), "10/01/2007", **FURTO)
n09, n10 = cump("10/01/2007", "25/12/2009"), cump("10/01/2007", "25/12/2010")
exi = anos(5) * 2 // 3
sobra = n10 - exi
novo(k, "Concurso com crime impeditivo (2/3 da pena do tráfico): 2009 não atingido, 2010 atingido - indulto do furto",
     "2009: Impeditivo (faltavam %s para 2/3 do tráfico). 2010: Cabe o indulto (art. 1º, I) sobre o furto" % T(exi - n09),
     "Tráfico (art. 33, caput) 5 anos (1.825 dias) + furto simples 1a6m (545 dias), fatos e prisão em 10/01/2007, primário. "
     "Decretos 7.046/2009 e 7.420/2010, art. 7º, p. ú.: o crime não impeditivo só é beneficiado depois de cumpridos 2/3 da pena "
     "do impeditivo = 1.216 dias. 2009: cumpriu %d dias - faltavam %d. 2010: cumpriu %d dias; sobram %d dias para o furto; "
     "art. 1º, I: 1/3 de 545 = 181 dias - atendido. (Conferido no Planalto.)" % (n09, exi - n09, n10, sobra),
     montar(k, [c1, c2], "10/01/2007", fuga="10/02/2011"),
     [DECR("2009", "imp"), DECR("2010", "cabe", "Indulto")])

# Decreto 7.420/2010
k = 7020
c1 = cr(k, 1, anos(10), "01/06/2008", **ESTEL)
n = cump("01/06/2008", "25/12/2010")
novo(k, "Decreto 7.420/2010, art. 1º, IV: 70 anos completos, 1/4 da pena",
     "2010: Cabe o indulto (art. 1º, IV), exigido 2a6m0d",
     "Estelionato, 10 anos (3.650 dias), primário, nascido em 10/01/1940 (70 anos em 25/12/2010), preso em 01/06/2008. "
     "I (até 8 anos) e III (60 anos, 1/3 = 1.216) não atendidos; IV: 70 anos, sem teto, 1/4 = 912 dias (2a6m0d... 912 = "
     "2a6m2d). Cumpriu %d dias (%s). (Conferido no Planalto.)" % (n, T(n)),
     montar(k, [c1], "01/06/2008", nasc="10/01/1940"),
     [DECR("2010", "cabe", ["Indulto", "IV", "exigido %s" % T(anos(10) // 4)])])
CASOS[-1]["esperado"] = "2010: Cabe o indulto (art. 1º, IV), exigido %s" % T(anos(10) // 4)
CASOS[-1]["conta"] = CASOS[-1]["conta"].replace("(2a6m0d... 912 = 2a6m2d)", "(%s)" % T(912))

k = 7021
c1 = cr(k, 1, anos(11), "01/03/2007", **ESTEL)
n = cump("01/03/2007", "25/12/2010")
novo(k, "Decreto 7.420/2010, art. 1º, II: pena entre 8 e 12 anos, crime sem violência",
     "2010: Cabe o indulto (art. 1º, II), exigido %s" % T(anos(11) // 3),
     "Estelionato, 11 anos (4.015 dias), primário, preso em 01/03/2007. Art. 1º, II: pena superior a 8 e até 12 anos, sem "
     "violência; 1/3 = %d dias (%s). Cumpriu %d dias (%s). (Conferido no Planalto.)" % (anos(11) // 3, T(anos(11) // 3), n, T(n)),
     montar(k, [c1], "01/03/2007"),
     [DECR("2010", "cabe", ["Indulto", "II"])])

k = 7022
c1 = cr(k, 1, anos(14), "01/03/2007", **FURTO_Q)
novo(k, "Comutação do Decreto 7.420/2010 concedida no RSPE: a decisão prevalece",
     "2010: Concedido (comutação concedida em 15/04/2011, incidente do RSPE)",
     "Furto qualificado, 14 anos, primário; em 25/12/2010 cumpriu %d dias (1/4 = 1.277): a comutação cabia pela conta e foi "
     "concedida. A decisão do juízo prevalece sobre o cálculo." % cump("01/03/2007", "25/12/2010"),
     montar(k, [c1], "01/03/2007", inc=[inc_("COMUTAÇÃO DE PENA", "Decreto 7.420/2010", "15/04/2011", "25/12/2010")]),
     [DECR("2010", "conc")])

# Regime aberto (2011, 2012), livramento (2023), aberto (2015)
k = 7023
c1 = cr(k, 1, anos(9), "01/03/2007", **ROUBO)
n11, n12 = cump("01/03/2007", "25/12/2011"), cump("01/03/2007", "25/12/2012")
novo(k, "Regime aberto: Decretos 7.648/2011 e 7.873/2012, art. 1º, XIV (remanescente até 8 anos, 1/4), sem exigir crime sem violência",
     "2011 e 2012: Cabe o indulto (art. 1º, XIV)",
     "Roubo simples, 9 anos (3.285 dias), primário, preso em 01/03/2007; semiaberto em 10/03/2009, aberto em 10/06/2011. "
     "I: pena acima de 8 anos; II: crime violento. XIV: em regime aberto na data, remanescente até 8 anos, 1/4 = 821 dias. "
     "2011: cumpriu %d, remanescente %d dias (%s). 2012: cumpriu %d, remanescente %d (%s). O XIV não exige crime sem "
     "violência (só o II e o XV a exigem). Evadiu-se do aberto em 10/03/2013 (depois dos dois decretos). (Conferido no Planalto.)"
     % (n11, anos(9) - n11, T(anos(9) - n11), n12, anos(9) - n12, T(anos(9) - n12)),
     montar(k, [c1], "01/03/2007", fuga="10/03/2013",
            inc=[regime("Semiaberto - Progressão de regime", "10/03/2009"), regime("Aberto - Progressão de regime", "10/06/2011")]),
     [DECR("2011", "cabe", ["Indulto", "XIV"]), DECR("2012", "cabe", ["Indulto", "XIV"])])

k = 7024
c1 = cr(k, 1, anos(12), "01/02/2017", **ROUBO)
lc = "01/09/2023"
n = cump("01/02/2017", "25/12/2023")
novo(k, "Decreto 11.846/2023, art. 2º, XIV: em livramento condicional (última decisão de regime: semiaberto)",
     "2023: Cabe o indulto (art. 2º, XIV), exigido 3a0m0d",
     "Roubo simples, 12 anos (4.380 dias), primário, preso em 01/02/2017; semiaberto em 01/06/2021; livramento condicional "
     "desde 01/09/2023. Em 25/12/2023: cumpriu %d dias (custódia + livramento, CP art. 88 a contrario), remanescente %d dias "
     "(%s) <= 8 anos; 1/4 = 1.095 dias (3a0m0d). O XIV pede 'livramento condicional ou regime aberto' - o livramento em curso "
     "basta, qualquer que tenha sido o regime anterior; o XIV não exige crime sem violência. (Conferido no Planalto.)"
     % (n, anos(12) - n, T(anos(12) - n)),
     montar(k, [c1], "01/02/2017", regime="Livramento Condicional - ATIVO",
            ev_extra=[interr(lc, "LIVRAMENTO CONDICIONAL", c1["processo_criminal"])],
            inc=[regime("Semiaberto - Progressão de regime", "01/06/2021"),
                 inc_("LIVRAMENTO CONDICIONAL", "Concessão de livramento condicional", lc, lc)],
            livramento_obs_seeu="(Em livramento condicional deferido em %s)" % lc),
     [DECR("2023", "cabe", ["Indulto", "XIV"])])

k = 7025
c1 = cr(k, 1, anos(8, 6), "01/03/2009", **ROUBO)
n = cump("01/03/2009", "25/12/2015")
novo(k, "Decreto 8.615/2015, art. 1º, XVI: regime aberto, remanescente até 8 anos, roubo de 8a6m",
     "2015: Cabe o indulto (art. 1º, XVI)",
     "Roubo simples, 8a6m (3.100 dias), primário, preso em 01/03/2009; semiaberto 10/05/2011; aberto 10/03/2014. I: acima de 8 "
     "anos; II: violento. XVI: aberto, remanescente %d dias (%s) <= 8 anos; 1/4 = 775 dias; cumpriu %d. Evadiu-se em 10/02/2016. "
     "(Conferido no Planalto.)" % (3100 - n, T(3100 - n), n),
     montar(k, [c1], "01/03/2009", fuga="10/02/2016",
            inc=[regime("Semiaberto - Progressão de regime", "10/05/2011"), regime("Aberto - Progressão de regime", "10/03/2014")]),
     [DECR("2015", "cabe", ["Indulto", "XVI"])])

# Patrimoniais
k = 7026
c1 = cr(k, 1, anos(8), "01/01/2008", rc="S", **FURTO_Q)
c2 = cr(k, 2, anos(5), "01/01/2008", rc="S", **ESTEL)
n = cump("01/01/2008", "25/12/2011")
novo(k, "Decreto 7.648/2011, art. 1º, XV: crime contra o patrimônio sem violência - depende da reparação do dano",
     "2011: A verificar (art. 1º, XV: tempo atendido, conferir a reparação do dano ou a incapacidade econômica)",
     "Furto qualificado 8 anos + estelionato 5 anos = 13 anos (4.745 dias), reincidente, preso em 01/01/2008. I e II: pena "
     "acima de 12 anos. XV: 1/4 (reincidente) = 1.186 dias; cumpriu %d. Falta a reparação do dano até 25/12/2011 (ou prova de "
     "incapacidade econômica), que o RSPE não mostra. Comutação: 1/3 = 1.581, não atingido. (Conferido no Planalto.)" % n,
     montar(k, [c1, c2], "01/01/2008"),
     [DECR("2011", "ver", "XV")])

k = 7027
c1 = cr(k, 1, anos(1, 2), "10/08/2012", sentenca="10/10/2012", transito="20/11/2012", rc="S", **FURTO)
n = cump("10/08/2012", "25/12/2012")
novo(k, "Decreto 7.873/2012, art. 1º, XVI (pequeno valor): pena de 1a2m não supera o piso de 18 meses - a hipótese não se aplica",
     "2012: A verificar só pelo XV (reparação); o XVI não deve aparecer (pena não é superior a 18 meses)",
     "Furto simples, 1a2m (425 dias), reincidente, preso em 10/08/2012; cumpriu %d dias em 25/12/2012. I: 1/2 = 212, não. "
     "XV: 1/4 = 106, atendido - depende da reparação. XVI: exige pena 'superior a dezoito meses e não superior a quatro anos' - "
     "1a2m está abaixo, a hipótese não alcança o caso. Comutação: 1/3 = 141 dias, não atingido. (Conferido no Planalto.)" % n,
     montar(k, [c1], "10/08/2012", fuga="10/02/2013"),
     [DECR("2012", "ver", "XV"), DECR("2012", None, sem="XVI", nota="piso de 18 meses do art. 1º, XVI")])

k = 7028
c1 = cr(k, 1, anos(2), "01/08/2015", sentenca="01/10/2015", transito="10/11/2015", **FURTO)
n = cump("01/08/2015", "25/12/2015")
novo(k, "Decreto 8.615/2015, art. 1º, XVIII: furto de 2 anos (acima de 18 meses), 3 meses cumpridos - pequeno valor e depósito",
     "2015: A verificar (XVII: reparação; XVIII: valor até um salário mínimo e depósito do prejuízo)",
     "Furto simples, 2 anos (730 dias), primário, preso em 01/08/2015; cumpriu %d dias em 25/12/2015. I: 1/3 = 243, não. "
     "XVII: 1/6 = 121, atendido, depende da reparação. XVIII: pena superior a 18 meses e até 4 anos, 3 meses cumpridos "
     "(atendido), depende do valor do prejuízo e do depósito judicial. Comutação: 1/4 = 182, não. (Conferido no Planalto.)" % n,
     montar(k, [c1], "01/08/2015", fuga="10/02/2016"),
     [DECR("2015", "ver", "XVIII")])

# Decreto 8.172/2013: 15 anos ininterruptos e tese das comutações anteriores
k = 7029
c1 = cr(k, 1, anos(20), "10/05/1997", **HOMIC)
c2 = cr(k, 2, anos(10), "10/05/1997", **ROUBO)
n = cump("10/05/1997", "25/12/2013")
novo(k, "Decreto 8.172/2013, art. 1º, V: 15 anos cumpridos ininterruptamente (homicídio simples e roubo, fatos de 1997)",
     "2013: Cabe o indulto (art. 1º, V), com a ressalva da tese do art. 3º (comutações anteriores não obtidas)",
     "Homicídio simples 20 anos + roubo simples 10 anos = 30 anos, primário, preso desde 10/05/1997 sem interrupção. Até "
     "25/12/2013: %d dias contínuos; 15 anos pelo calendário (25/12/1998 a 25/12/2013) = 5.479 dias. O V não exige regime nem "
     "crime sem violência; homicídio simples fora de grupo de extermínio não é hediondo. Art. 3º do decreto: concede as "
     "comutações dos decretos anteriores a quem não as obteve - o RSPE não registra nenhuma. (Conferido no Planalto.)" % n,
     montar(k, [c1, c2], "10/05/1997"),
     [DECR("2013", "cabe", ["Indulto", "V"]), DECR("2013", None, "comutação dos decretos anteriores")])

k = 7030
c1 = cr(k, 1, anos(7), "01/03/2011", **ESTEL)
novo(k, "Decreto 8.172/2013, art. 5º: falta grave reconhecida em audiência, praticada 6 meses antes da publicação",
     "2013: Não cabe (falta grave nos 12 meses anteriores à publicação)",
     "Estelionato, 7 anos, primário, preso em 01/03/2011; cumpriu %d dias em 25/12/2013 (1/3 = 851: o art. 1º, I caberia). "
     "Falta grave praticada em 10/06/2013 e reconhecida em 10/08/2013: dentro da janela de 24/12/2012 a 24/12/2013. Art. 5º "
     "barra indulto e comutação. (Conferido no Planalto.)" % cump("01/03/2011", "25/12/2013"),
     montar(k, [c1], "01/03/2011", inc=[falta("10/06/2013", "10/08/2013")]),
     [DECR("2013", "nao", "falta")])

# Decreto 8.380/2014
k = 7031
c1 = cr(k, 1, anos(8), "01/03/2006", **ESTEL)
c2 = cr(k, 2, anos(6), "01/03/2006", **FURTO_Q)
n = cump("01/03/2006", "25/12/2014")
rem = anos(14) - n
red = max(n, rem) // 4
novo(k, "Decreto 8.380/2014, art. 2º, § 1º: comutação sobre o período cumprido, maior que o remanescente",
     "2014: Cabe a comutação, redução de 1/4 do período cumprido = %s (indulto patrimonial XVI a verificar)" % T(red),
     "Estelionato 8 anos + furto qualificado 6 anos = 14 anos (5.110 dias), primário, preso em 01/03/2006. I e II: acima de "
     "12 anos; V: sem 15 anos. XVI (patrimonial): 1/6 atendido, depende da reparação - a verificar. Comutação: 1/4 = 1.277; "
     "cumpriu %d dias (%s), remanescente %d (%s). Como o cumprido é maior, a base é o cumprido (§ 1º): %d/4 = %d dias (%s). "
     "(Conferido no Planalto.)" % (n, T(n), rem, T(rem), n, red, T(red)),
     montar(k, [c1, c2], "01/03/2006"),
     [DECR("2014", "cabe", ["Comutação", "redução de %s" % T(red)])])

k = 7032
c1 = cr(k, 1, anos(6), "01/02/2013", **FURTO_Q)
n = cump("01/02/2013", "25/12/2015")
novo(k, "Falta grave praticada em 20/12/2014: dentro da janela de 2014 (publicação) e fora da de 2015 (contada de 25/12/2015)",
     "2014: Não cabe (falta grave). 2015: Cabe o indulto (art. 1º, I)",
     "Furto qualificado, 6 anos, primário, preso em 01/02/2013. Falta grave praticada em 20/12/2014, reconhecida em 20/02/2015. "
     "Decreto 8.380/2014, art. 5º: 12 meses contados da publicação (24/12/2013 a 24/12/2014) - dentro. Decreto 8.615/2015, "
     "art. 5º: 12 meses 'contados retroativamente a 25 de dezembro de 2015' (25/12/2014 a 25/12/2015) - fora. Em 2015 cumpriu "
     "%d dias (1/3 = 730). (Conferido no Planalto.)" % n,
     montar(k, [c1], "01/02/2013", fuga="10/02/2016", inc=[falta("20/12/2014", "20/02/2015")]),
     [DECR("2014", "nao", "falta"), DECR("2015", "cabe", "Indulto")])

# Hediondez superveniente: 2015 (praticado após) e 2016
k = 7034
c1 = cr(k, 1, anos(5), "01/03/2014", artigo="218-B, caput",
        tipo="CAPUT: favorecimento da prostituição de vulnerável, Reclusão: 4 a 10 anos")
n15, n16 = cump("01/03/2014", "25/12/2015"), cump("01/03/2014", "25/12/2016")
novo(k, "Hediondez superveniente: art. 218-B com fato antes da Lei 12.978/2014 - Decreto 8.615/2015 e Decreto 8.940/2016",
     "2015: Cabe o indulto (art. 1º, I). 2016: A verificar (hediondez posterior ao fato: STJ x STF)",
     "Favorecimento da prostituição de vulnerável (CP, art. 218-B), fato em 01/03/2014; o tipo só se tornou hediondo pela Lei "
     "12.978, de 21/05/2014. Pena 5 anos (1.825 dias), primário, preso em 01/03/2014. 2015: o art. 9º veda o hediondo "
     "'praticado após' as leis - na data do fato não era hediondo; I: 1/3 = 608, cumpriu %d. 2016: o art. 2º, III veda "
     "hediondos 'praticados após a publicação da Lei 8.072/1990' com as alterações posteriores; art. 3º, I: 1/4 = 456, cumpriu "
     "%d. A natureza na data do decreto (STJ) e a irretroatividade (STF, 2ª Turma) dão respostas opostas: a verificar. "
     "(Conferido no Planalto.)" % (n15, n16),
     montar(k, [c1], "01/03/2014", fuga="10/02/2017"),
     [DECR("2015", "cabe", "Indulto"), DECR("2016", "ver", "hediond")])

k = 7035
c1 = cr(k, 1, anos(6), "01/03/2013", **ROUBO)
n = cump("01/03/2013", "25/12/2016")
novo(k, "Decreto 8.940/2016, art. 5º, II, a: roubo de 6 anos (violência, pena de 4 a 8 anos), metade cumprida",
     "2016: Cabe o indulto (art. 5º, II, a), exigido 3a0m0d",
     "Roubo simples, 6 anos (2.190 dias), primário, preso em 01/03/2013. Art. 5º, II, a: crime com violência, pena superior a "
     "4 e até 8 anos, 1/2 = 1.095 dias (3a0m0d); cumpriu %d dias (%s). (Conferido no Planalto.)" % (n, T(n)),
     montar(k, [c1], "01/03/2013", fuga="10/02/2017"),
     [DECR("2016", "cabe", ["Indulto", "exigido 3a0m0d"])])

k = 7036
c1 = cr(k, 1, anos(6), "01/02/2014", **FURTO_Q)
p = c1["processo_criminal"]
n = cump("01/02/2014", "10/05/2016") + cump("20/05/2016", "25/12/2016")
gap = (D("20/05/2016") - D("10/05/2016")).days - 1
novo(k, "Decreto 8.940/2016, art. 9º: fuga na janela, sem apuração - a declaração fica suspensa até a apuração",
     "2016: A verificar (falta não apurada: art. 9º, p. ú. suspende a declaração; não é 'não cabe' firme)",
     "Furto qualificado, 6 anos, primário, preso em 01/02/2014; fuga em 10/05/2016, recapturado em 20/05/2016, sem "
     "homologação de falta. Art. 3º, I: 1/4 = 547 dias; cumpriu %d. O art. 9º exige ausência de falta grave nos 12 meses "
     "anteriores à publicação e, no parágrafo único, manda suspender a declaração do indulto até a apuração da falta não "
     "submetida ao juízo. Sem a apuração, o resultado depende dela. (Conferido no Planalto.)" % n,
     rspe(k, [c1], [prisao("01/02/2014", p), interr("10/05/2016", "FUGA", p), prisao("20/05/2016", p, "RECAPTURA/REINÍCIO DE CUMPRIMENTO"),
                    interr("10/02/2017", "FUGA", p), prisao("01/04/2026", p, "RECAPTURA/REINÍCIO DE CUMPRIMENTO")], [],
          ini="01/02/2014", interrompidos=gap + (D("01/04/2026") - D("10/02/2017")).days - 1),
     [DECR("2016", "ver")])

k = 7037
c1 = cr(k, 1, anos(3), "01/03/2016", **TRAF_PRIV)
n16, n17 = cump("01/03/2016", "25/12/2016"), cump("01/03/2016", "25/12/2017")
novo(k, "Tráfico privilegiado (homem): 2016 só para as pessoas do art. 1º, § 1º; 2017 art. 1º, IV (1/4 para homens)",
     "2016: A verificar (o art. 4º depende de condição do art. 1º, § 1º que o RSPE não mostra). 2017: Cabe o indulto (art. 1º, IV)",
     "Tráfico privilegiado, 3 anos (1.095 dias), sexo masculino informado, preso em 01/03/2016. 2016 (Decreto 8.940): o art. 4º "
     "indulta o privilegiado só de quem está numa das situações do art. 1º, § 1º (gestante, 70 anos, filho menor de 12, estudo "
     "ou trabalho, doença), com 1/4 = 273 dias; cumpriu %d. As condições não aparecem no RSPE: não se pode afirmar nem negar. "
     "2017 (Decreto 9.246): art. 1º, IV, 1/4 para homens = 273; cumpriu %d. (Conferido no Planalto.)" % (n16, n17),
     montar(k, [c1], "01/03/2016", fuga="10/02/2018"),
     [DECR("2016", "ver", nota="art. 4º depende do art. 1º, § 1º: o resultado firme 'não cabe' esconde a hipótese", decisao=True),
      DECR("2017", "cabe", ["Indulto", "IV"])],
     manuais={"sexo": "M"})

# Dia das Mães 2017 e 2018
k = 7038
c1 = cr(k, 1, anos(5), "01/03/2015", rc="S", **TRAF)
n17, n18 = cump("01/03/2015", "14/05/2017"), cump("01/03/2015", "13/05/2018")
novo(k, "Dia das Mães 2017 e 2018: mulher reincidente, tráfico comum (art. 33, caput) - a comutação também é vedada por lei",
     "Dia das Mães 2017 e 2018: Impeditivo (nem indulto nem comutação: Lei 8.072/1990, art. 2º, I)",
     "Mulher, tráfico (art. 33, caput), 5 anos (1.825 dias), reincidente, presa em 01/03/2015. Pela conta, a comutação do art. "
     "2º, I (reincidente, sem violência, 1/3 = 608 dias) estaria atendida (cumpriu %d dias até 14/05/2017 e %d até 13/05/2018). "
     "Mas o tráfico é equiparado a hediondo: a Lei 8.072/1990, art. 2º, I (e a CF, art. 5º, XLIII) proíbe o indulto, e a "
     "comutação é indulto parcial (STF). Os decretos do Dia das Mães não têm rol de vedações, mas não podem afastar a lei. "
     "(Decreto 9.370/2018 conferido no Planalto; texto do decreto s/nº de 12/04/2017 não confirmado.)" % (n17, n18),
     montar(k, [c1], "01/03/2015", fuga="10/06/2018"),
     [DECR("2017_maes", "imp|nao"), DECR("2018_maes", "imp|nao")],
     manuais={"sexo": "F"})

k = 7039
c1 = cr(k, 1, anos(2), "10/12/2017", sentenca="10/03/2018", transito="10/04/2018", **TRAF_PRIV)
n = cump("10/12/2017", "13/05/2018")
novo(k, "Decreto 9.370/2018 (Dia das Mães), art. 1º, II, g: mulher, tráfico privilegiado, 1/6 cumprido",
     "Dia das Mães 2018: Cabe o indulto (art. 1º, II, g), exigido 0a4m1d",
     "Mulher, tráfico privilegiado, 2 anos (730 dias), presa em 10/12/2017, sentença 10/03/2018 com o redutor do § 4º. Alínea "
     "g: até 8 anos, 1/6 = 121 dias (0a4m1d); cumpriu %d dias em 13/05/2018. Sem falta grave. (Conferido no Planalto.)" % n,
     montar(k, [c1], "10/12/2017", fuga="10/06/2018"),
     [DECR("2018_maes", "cabe", ["Indulto", "exigido 0a4m1d"])],
     manuais={"sexo": "F"})

k = 7040
c1 = cr(k, 1, anos(3), "01/06/2017", **FURTO)
novo(k, "Decreto 9.370/2018 (Dia das Mães): homem não é alcançado",
     "Dia das Mães 2018: Não alcançado (decreto só para mulheres)",
     "Sexo masculino informado. O Decreto 9.370/2018 concede indulto e comutação a mulheres (e, art. 4º, a mulheres "
     "transexuais). Furto de 3 anos, preso em 01/06/2017. (Conferido no Planalto.)",
     montar(k, [c1], "01/06/2017", fuga="10/06/2018"),
     [DECR("2018_maes", "fora", "mulheres")],
     manuais={"sexo": "M"})

k = 7041
c1 = cr(k, 1, anos(3), "01/08/2016", **FURTO)
n = cump("01/08/2016", "14/05/2017")
novo(k, "Dia das Mães 2017 (decreto s/nº de 12/04/2017), art. 1º, III, g/h: mulher, furto de 3 anos, 1/4 cumprido",
     "Dia das Mães 2017: Cabe o indulto (art. 1º, III, alíneas g/h), exigido 0a9m3d",
     "Mulher, furto simples, 3 anos (1.095 dias), primária, presa em 01/08/2016. Pena até 8 anos, sem violência, 1/4 = 273 dias "
     "(0a9m3d); cumpriu %d dias em 14/05/2017. Sem falta. (Texto do decreto s/nº de 12/04/2017 não confirmado no Planalto; "
     "pelo que se sabe do decreto, alínea de não reincidente: 1/4.)" % n,
     montar(k, [c1], "01/08/2016", fuga="10/06/2017"),
     [DECR("2017_maes", "cabe", ["Indulto", "exigido 0a9m3d"])],
     manuais={"sexo": "F"})

# Decreto 9.246/2017
k = 7043
c1 = cr(k, 1, anos(2), "01/08/2017", sentenca="01/10/2017", transito="10/11/2017", **TRAF_PRIV)
n = cump("01/08/2017", "25/12/2017")
novo(k, "Decreto 9.246/2017, art. 1º, IV: tráfico privilegiado, mulher - 1/6 basta",
     "2017: Cabe o indulto (art. 1º, IV - mulheres), exigido 0a4m1d",
     "Mulher, tráfico privilegiado, 2 anos (730 dias), presa em 01/08/2017; cumpriu %d dias em 25/12/2017. Art. 1º, IV: 1/4 "
     "para homens (182 dias) e 1/6 para mulheres (121 dias = 0a4m1d). (Conferido no Planalto.)" % n,
     montar(k, [c1], "01/08/2017", fuga="10/02/2018"),
     [DECR("2017", "cabe", ["Indulto", "IV"])],
     manuais={"sexo": "F"})

k = 7044
c1 = cr(k, 1, anos(2), "01/08/2017", sentenca="01/10/2017", transito="10/11/2017", **TRAF_PRIV)
novo(k, "Decreto 9.246/2017, art. 1º, IV: mesmo caso, sem o sexo informado - o resultado depende do sexo",
     "2017: A verificar (cabe se mulher - 1/6; não cabe se homem - faltam dias para 1/4); conferir o sexo",
     "Igual ao caso S7043, sem o sexo no RSPE, na ficha ou na tela. Cumpriu %d dias: atende 1/6 (121) e não 1/4 (182). O "
     "resultado depende de dado que falta - não deveria ser 'não cabe' firme." % cump("01/08/2017", "25/12/2017"),
     montar(k, [c1], "01/08/2017", fuga="10/02/2018"),
     [DECR("2017", "ver", nota="sexo não informado: a hipótese das mulheres fica sem resposta", decisao=True)])

k = 7045
c1 = cr(k, 1, anos(10), "01/04/2016", **ESTEL)
n = cump("01/04/2016", "25/12/2017")
novo(k, "Decreto 9.246/2017, art. 2º, § 1º, I: pessoa com 70 anos ou mais - 1/6 em vez de 1/5",
     "2017: Cabe o indulto (art. 1º, I c/c art. 2º, § 1º, I), exigido 1a8m3d",
     "Estelionato, 10 anos (3.650 dias), primário, nascido em 10/03/1946 (71 anos em 25/12/2017), preso em 01/04/2016; "
     "cumpriu %d dias (%s). Art. 1º, I exige 1/5 = 730 (não atingido); para maiores de 70 anos o art. 2º, § 1º, I reduz a 1/6 = "
     "608 dias (1a8m3d) - atingido. (Conferido no Planalto.)" % (n, T(n)),
     montar(k, [c1], "01/04/2016", nasc="10/03/1946"),
     [DECR("2017", "cabe", "Indulto")])

k = 7046
c1 = cr(k, 1, anos(7), "01/03/2010", **FURTO_Q)
n = cump("01/03/2010", "25/12/2012")
novo(k, "Indulto do Decreto 7.873/2012 indeferido no RSPE; comutação não decidida",
     "2012: o indeferimento do indulto aparece; a comutação (não decidida) fica a verificar - conferir o fundamento do indeferimento",
     "Furto qualificado, 7 anos (2.555 dias), primário, preso em 01/03/2010; cumpriu %d dias em 25/12/2012 - pela conta o "
     "art. 1º, I (1/3 = 851) caberia, mas o juízo indeferiu o indulto em 10/05/2013. A decisão prevalece para o indulto. A "
     "comutação (1/4 = 638 atendido) não foi decidida: pode ser pedida, salvo se o indeferimento teve fundamento que também a "
     "afasta (falta, crime impeditivo)." % n,
     montar(k, [c1], "01/03/2010", inc=[inc_("INDULTO", "Decreto 7.873/2012", "10/05/2013", "25/12/2012", sit="NÃO CONCEDIDO")]),
     [DECR("2012", "ver|indef", "indeferid")])

# Decretos restritos 2019-2021
k = 7047
c1 = cr(k, 1, anos(6), "01/02/2018", **FURTO_Q)
novo(k, "Decretos 10.189/2019, 10.590/2020 e 10.913/2021: só doença, deficiência, agentes de segurança e militares",
     "2019, 2020 e 2021: Não cabe (decreto restrito: nenhuma hipótese para condenado comum)",
     "Furto qualificado, 6 anos, primário, preso desde 01/02/2018. Os três decretos só indultam doentes graves, pessoas com "
     "deficiência, agentes de segurança (excesso culposo; crime culposo) e militares em GLO; não há comutação. Nada do RSPE "
     "permite enquadrar. (Decreto 10.189/2019 conferido no Planalto; 10.590/2020 e 10.913/2021 de mesma estrutura - texto não "
     "confirmado.)",
     montar(k, [c1], "01/02/2018", fuga="10/02/2022"),
     [DECR("2019", "nao"), DECR("2020", "nao"), DECR("2021", "nao")])

k = 7048
c1 = cr(k, 1, anos(5), "01/03/2020", **FURTO_Q)
novo(k, "Decreto 10.189/2019: fato e prisão posteriores à data de referência",
     "2019: Não alcançado (sem condenação até o decreto / execução posterior)",
     "Furto qualificado, fato e prisão em 01/03/2020, depois de 25/12/2019: o decreto não alcança a condenação.",
     montar(k, [c1], "01/03/2020"),
     [DECR("2019", "fora")])

# Decreto 11.846/2023
k = 7049
c1 = cr(k, 1, anos(5), "01/03/2022", **FURTO_Q)
n = cump("01/03/2022", "25/12/2023")
novo(k, "Decreto 11.846/2023, art. 2º, I: furto qualificado de 5 anos, primário, 1/4 cumprido",
     "2023: Cabe o indulto (art. 2º, I), exigido 1a3m1d",
     "Furto qualificado, 5 anos (1.825 dias), primário, preso em 01/03/2022. Art. 2º, I: sem violência, até 8 anos, 1/4 = 456 "
     "dias (1a3m1d); cumpriu %d dias (%s). (Conferido no Planalto.)" % (n, T(n)),
     montar(k, [c1], "01/03/2022"),
     [DECR("2023", "cabe", ["Indulto", "exigido 1a3m1d"])])

k = 7050
c1 = cr(k, 1, anos(4), "10/01/2022", sentenca="10/05/2023", transito="10/07/2023", **FURTO_Q)
det = cump("10/01/2022", "20/01/2023")
gap = (D("10/04/2026") - D("20/01/2023")).days - 1
novo(k, "Decreto 11.846/2023, art. 5º: só prisão provisória até a data - detração no requisito temporal",
     "2023: Cabe o indulto (art. 2º, I), com a prisão provisória contada (%s; exigido 1a0m0d)" % T(det),
     "Furto qualificado, 4 anos (1.460 dias), primário. Flagrante de 10/01/2022 a 20/01/2023 (liberdade provisória), sentença "
     "10/05/2023, trânsito 10/07/2023, prisão definitiva em 10/04/2026. Art. 5º: a detração (CP, art. 42; CPP, art. 387, § 2º) "
     "conta para o requisito temporal: %d dias >= 1/4 = 365 (1a0m0d). (Conferido no Planalto.)" % det,
     montar(k, [c1], "10/01/2022", interrompidos=gap,
            ev_extra=[interr("20/01/2023", "LIBERDADE PROVISÓRIA", c1["processo_criminal"]),
                      prisao("10/04/2026", c1["processo_criminal"], "PRISÃO DEFINITIVA")]),
     [DECR("2023", "cabe", ["Indulto", "exigido 1a0m0d"])])

k = 7051
c1 = cr(k, 1, anos(12), "01/03/2020", rc="S", **FURTO_Q)
n = cump("01/03/2020", "25/12/2023")
rem = anos(12) - n
red = max(rem, n) // 3
novo(k, "Decreto 11.846/2023, art. 3º, § 3º, I: comutação de maior de 65 anos (reincidente: 1/3)",
     "2023: Cabe a comutação do art. 3º, § 3º, I, redução de 1/3 = %s (o indulto patrimonial XV fica a verificar)" % T(red),
     "Furto qualificado, 12 anos (4.380 dias), reincidente, nascido em 01/06/1957 (66 anos em 25/12/2023), preso em 01/03/2020; "
     "cumpriu %d dias (%s), remanescente %d (%s). Indulto: I (até 8 anos) não; II: 1/2 = 2.190 não; III (60 anos, 1/2) não; "
     "IV (70 anos) não; XV (patrimonial, 1/4 = 1.095) atendido, depende da reparação. Comutação, art. 3º, § 3º, I: maior de "
     "65 anos, crime sem violência, reincidente: 1/3 da pena remanescente (o remanescente é maior que o cumprido) = %d dias (%s); "
     "o caput (1/4 cumprido = 1.095) também está atendido. (Conferido no Planalto.)" % (n, T(n), rem, T(rem), red, T(red)),
     montar(k, [c1], "01/03/2020", nasc="01/06/1957"),
     [DECR("2023", "cabe", ["Comutação", "redução de %s" % T(red)])])

k = 7052
c1 = cr(k, 1, anos(5), "01/02/2021", artigo="1º, caput", tipo="CAPUT: lavagem de dinheiro, Reclusão: 3 a 10 anos E Multa", lei=LAVAGEM)
novo(k, "Decreto 11.846/2023, art. 1º, III: lavagem com pena acima de 4 anos é vedada",
     "2023: Impeditivo",
     "Lavagem (Lei 9.613/1998, art. 1º), 5 anos, preso em 01/02/2021. O art. 1º, III veda a lavagem 'exceto quando a pena "
     "aplicada não for superior a quatro anos' - 5 anos é superior. (Conferido no Planalto.)",
     montar(k, [c1], "01/02/2021"),
     [DECR("2023", "imp")])

k = 7053
c1 = cr(k, 1, anos(3), "01/03/2022", artigo="1º, caput", tipo="CAPUT: lavagem de dinheiro, Reclusão: 3 a 10 anos E Multa", lei=LAVAGEM)
n = cump("01/03/2022", "25/12/2023")
novo(k, "Decreto 11.846/2023, art. 1º, III: lavagem com pena de 3 anos não é vedada",
     "2023: Cabe o indulto (art. 2º, I), exigido 0a9m3d",
     "Lavagem, 3 anos (1.095 dias), primário, preso em 01/03/2022. Pena aplicada não superior a 4 anos: fora da vedação. "
     "Art. 2º, I: 1/4 = 273 dias (0a9m3d); cumpriu %d dias. (Conferido no Planalto.)" % n,
     montar(k, [c1], "01/03/2022", fuga="10/02/2024"),
     [DECR("2023", "cabe", ["Indulto", "exigido 0a9m3d"])])

k = 7054
c1 = cr(k, 1, anos(5), "01/02/2019", **TRAF)
c2 = cr(k, 2, anos(2), "01/02/2019", **FURTO)
n = cump("01/02/2019", "25/12/2023")
exi = anos(5) * 2 // 3
novo(k, "Decreto 11.846/2023, art. 9º, p. ú.: 2/3 da pena do tráfico cumpridos - indulto sobre o furto",
     "2023: Cabe o indulto (art. 2º, I) sobre o furto, depois dos 2/3 do tráfico",
     "Tráfico (art. 33, caput) 5 anos (1.825) + furto simples 2 anos (730), primário, presos desde 01/02/2019. 2/3 do tráfico = "
     "1.216 dias. Em 25/12/2023 cumpriu %d dias; sobram %d para o furto; art. 2º, I: 1/4 de 730 = 182 dias - atendido. "
     "(Conferido no Planalto.)" % (n, n - exi),
     montar(k, [c1, c2], "01/02/2019", fuga="10/02/2024"),
     [DECR("2023", "cabe", "Indulto")])

k = 7055
c1 = cr(k, 1, anos(6), "01/02/2022", **FURTO_Q)
novo(k, "Decreto 11.846/2023, art. 6º: fuga na janela, sem audiência de justificação",
     "2023: A verificar (falta não reconhecida em juízo: o art. 6º exige sanção reconhecida em audiência de justificação)",
     "Furto qualificado, 6 anos, primário, preso em 01/02/2022; fuga em 10/06/2023, recapturado em 20/06/2023, sem homologação. "
     "Cumpriu %d dias em 25/12/2023 (1/4 = 547). O art. 6º só impede com sanção reconhecida em audiência de justificação, por "
     "falta cometida nos 12 meses anteriores a 25/12/2023: pendente a apuração, não se afirma nem se nega. (Conferido no Planalto.)"
     % (cump("01/02/2022", "10/06/2023") + cump("20/06/2023", "25/12/2023")),
     rspe(k, [c1], [prisao("01/02/2022", c1["processo_criminal"]), interr("10/06/2023", "FUGA", c1["processo_criminal"]),
                    prisao("20/06/2023", c1["processo_criminal"], "RECAPTURA/REINÍCIO DE CUMPRIMENTO")], [],
          ini="01/02/2022", interrompidos=(D("20/06/2023") - D("10/06/2023")).days - 1),
     [DECR("2023", "ver")])

k = 7056
c1 = cr(k, 1, anos(9), "01/03/2009", **ESTEL)
n = cump("01/03/2009", "25/12/2009")
novo(k, "Decreto 7.046/2009, art. 1º, I: faltam dias para 1/3 - não cabe; comutação também não (1/4)",
     "2009: Não cabe (faltavam para a fração)",
     "Estelionato, 9 anos (3.285 dias), primário, preso em 01/03/2009; cumpriu %d dias em 25/12/2009. Indulto: pena acima de 8 "
     "anos (I) e sem 60 anos (II); comutação 1/4 = 821 - não atingido. (Conferido no Planalto.)" % n,
     montar(k, [c1], "01/03/2009"),
     [DECR("2009", "nao")])

for c in CASOS:  # trânsito até a publicação dos decretos verificados
    for ch in c["checks"]:
        did = ch["v"].split('"')[3]
        checa_transito(c, did)

json.dump(CASOS, open(os.path.join(AQUI, "decretos_antigos.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(CASOS), "casos")
