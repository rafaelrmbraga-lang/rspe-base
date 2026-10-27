"""Base simulada de cobertura - área "progressao" (capítulo 3: progressão, livramento, saída temporária e progressão antecipada).
Casos S3001 a S30xx, independentes da bateria antiga. O gabarito de cada caso vem da lei da data do fato (LEP, art. 112, nas
redações da Lei 10.792/2003, da Lei 8.072/90 com a Lei 11.464/2007, da Lei 13.964/2019 - vigente em 23/01/2020 -, da Lei
14.994/2024 - DOU 10/10/2024 -, da Lei 15.358/2026 - DOU 25/03/2026 - e da Lei 15.402/2026 - DOU 08/05/2026), do CP (arts. 10,
63, 64, 83, 88), da Lei 11.343/06 (art. 44), da LEP (arts. 122 a 124) e das súmulas e temas citados em cada "conta"; nunca do que
o programa mostra. Grava cobertura/progressao.json.
Uso: python3 cobertura/gera_progressao.py (a partir de /home/user/rspe-base/casos_simulados)."""
import json
import os
import sys
from datetime import date, timedelta

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from base_casos import (D, F, anos, crime, rspe, ev, prisao, inc, C, AUD, caso, REG, CP, DROGAS, GER)  # noqa: E402

JAN_INI, JAN_FIM = date(2026, 10, 12), date(2027, 3, 31)  # nada deve vencer aqui (o usuário abre a base depois)
CASOS = []

# tipos penais com as penas cominadas (a pena imposta fica sempre dentro do máximo)
T_FURTO = "CAPUT: Subtrair coisa alheia móvel, Reclusão: 1 a 4 anos E Multa"
T_FURTO_Q = "§ 4º: Furto qualificado, Reclusão: 2 a 8 anos E Multa"
T_ESTEL = "CAPUT: Obter vantagem ilícita, Reclusão: 1 a 5 anos E Multa"
T_ROUBO = "CAPUT: Subtrair coisa móvel mediante grave ameaça ou violência, Reclusão: 4 a 10 anos E Multa"
T_ROUBO_M = "§ 2º, II: se há o concurso de duas ou mais pessoas, Reclusão: 4 a 10 anos E Multa"
T_LATRO = "§ 3º, II: se resulta morte, Reclusão: 20 a 30 anos E Multa"
T_HQ = "§ 2º, IV: à traição, de emboscada, Reclusão: 12 a 30 anos"
T_FEM_A = "CAPUT: Matar mulher por razões da condição do sexo feminino, Reclusão: 20 a 40 anos"
T_FEM_VI = "§ 2º, VI: contra a mulher por razões da condição de sexo feminino, Reclusão: 12 a 30 anos"
T_ESTUPRO = "CAPUT: Constranger alguém, mediante violência ou grave ameaça, Reclusão: 6 a 10 anos"
T_EV = "CAPUT: Ter conjunção carnal ou praticar ato libidinoso com menor de 14 anos, Reclusão: 8 a 15 anos"
T_TRAF = "CAPUT: Importar, exportar, ... vender ... drogas, Reclusão: 5 a 15 anos E Multa"
T_TRAF_P = "§ 4º: Tráfico privilegiado (redução de 1/6 a 2/3), Reclusão: 5 a 15 anos E Multa"
T_ASSOC = "CAPUT: Associarem-se duas ou mais pessoas para praticar os crimes dos arts. 33 e 34, Reclusão: 3 a 10 anos E Multa"
T_ORCRIM = "CAPUT: Promover, constituir, financiar ou integrar organização criminosa, Reclusão: 3 a 8 anos E Multa"
T_MILICIA = "CAPUT: Constituir, organizar, integrar, manter ou custear milícia particular, Reclusão: 4 a 8 anos"
T_DOMINIO = "§ 1º, I: domínio social estruturado - comando da organização criminosa ultraviolenta, Reclusão: 20 a 40 anos"
T_GOLPE = "CAPUT: Tentar, com emprego de violência ou grave ameaça, abolir o Estado Democrático de Direito, Reclusão: 4 a 8 anos"
T_CTB = "CAPUT: Praticar homicídio culposo na direção de veículo automotor, Detenção: 2 a 4 anos"
T_VIAS = "CAPUT: Praticar vias de fato contra alguém, Prisão simples: 15 dias a 3 meses"
T_LESAO = "§ 9º: Lesão praticada contra ... cônjuge ou companheiro, Reclusão: 2 a 5 anos"

UNID_SEMI = "CENTRO PENAL AGROINDUSTRIAL DA GAMELEIRA"


def frac(s):
    """Fração impressa pelo SEEU ("1/6 - Comum", "16% - ...", "1/1 - ...") -> número."""
    s = (s or "").split(" - ")[0].strip()
    if s.endswith("%"):
        return float(s[:-1].replace(",", ".")) / 100
    a, b = s.split("/")
    return int(a) / int(b)


def lapso(crs, chave):
    """Soma, crime a crime (crimes não extintos), de pena x fração do SEEU, cada parcela arredondada para baixo."""
    return sum(int(c["_dias"] * frac(c[chave]) + 1e-9) for c in crs if c.get("extinto") != "Sim" and frac(c[chave]) < 1)


def fora_janela(*ds):
    return all(not (JAN_INI <= d <= JAN_FIM) for d in ds if d)


def anterior(k, artigo, pena, fato, sent, trans, ext, tipo=T_FURTO, lei=CP, ano=2010, **kw):
    """Condenação anterior, de outro processo, já extinta (fica no RSPE para provar a reincidência pelas datas)."""
    return crime("%07d-00.%d.8.12.0001" % (8800000 + k, ano), artigo, pena, fato, sentenca=sent, transito=trans, lei=lei, tipo=tipo,
                 extinto="Sim", data_extincao=ext, regime="Semiaberto", **kw)


def exe(k, crimes, ini=None, db=None, regime="Fechado - ATIVO", incs=None, evs=None, prog_vencida_ok=True, livre_janela=False,
        prog=None, liv=None, **kw):
    """RSPE com previsões do SEEU coerentes: progressão = data-base + lapso (fração do SEEU de cada crime sobre a pena dele);
    livramento = início + lapso do livramento. Sem 'ini', escolhe um início (prisão) tal que nenhuma previsão caia entre
    12/10/2026 e 31/03/2027."""
    ativos = [c for c in crimes if c.get("extinto") != "Sim"]
    lp, ll = lapso(ativos, "fracao_progressao"), lapso(ativos, "fracao_livramento")
    pena = sum(c["_dias"] for c in ativos)
    if ini is None:
        piso = max(D(c["data_infracao"]) for c in ativos)
        d0 = GER - timedelta(days=10)
        while d0 >= piso:
            p0 = d0 + timedelta(days=lp)
            l0 = d0 + timedelta(days=ll) if ll else None
            if fora_janela(p0, l0) or livre_janela:
                break
            d0 -= timedelta(days=15)
        else:
            raise SystemExit("caso %d: sem início possível fora da janela" % k)
        ini = F(d0)
    db = db or ini
    if prog is None:
        prog = F(D(db) + timedelta(days=lp)) if lp else ""
    if liv is None:
        liv = F(D(ini) + timedelta(days=ll)) if ll and pena >= 730 else ""
    if not livre_janela:
        assert fora_janela(D(prog) if prog else None, D(liv) if liv else None), (k, prog, liv)
    trans = min(D(c["transito_processo"]) for c in ativos if c.get("transito_processo"))
    procs = ", ".join(c["processo_criminal"] for c in ativos)
    eventos = list(evs) if evs is not None else [prisao(ini, procs, "PRISÃO DEFINITIVA" if D(ini) >= trans else "PRISÃO EM FLAGRANTE")]
    incidentes = list(incs) if incs is not None else [inc(REG, regime.split(" - ")[0] + " - Regime Inicial", "", ini)]
    kw.setdefault("pena", pena)
    return rspe(k, crimes, eventos, incidentes, ini=ini, db=db, prog=prog, liv=liv, regime=regime, **kw)


def novo(k, aba, situacao, esperado, conta, r, checks, titulo=None, **kw):
    c = caso(k, "P-" + aba, titulo or situacao, conta, r, checks, **kw)
    c.update(aba=aba, situacao=situacao, esperado=esperado)
    CASOS.append(c)
    return c


def P(k, proc_ano=2020):
    return "%07d-00.%d.8.12.0001" % (8800000 + k, proc_ano)


def ficha(k, conduta="BOA", unidade=UNID_SEMI, eventos=(), impressao="01/10/2026", sexo="M"):
    r = "%07d-00.2026.8.12.0001" % (9900000 + k)
    return {"tipo": "ficha_disciplinar", "nome": "SIMULADO CASO %03d" % k, "cpf": "%011d" % (90000000000 + k), "cpf_em_branco": False,
            "data_nascimento": "01/01/1975", "nome_mae": "MAE SIMULADA %03d" % k, "filiacao": "MAE SIMULADA %03d" % k,
            "artigo": "", "data_prisao": "", "condenacao": "CONDENADO", "unidade": unidade, "data_entrada": "", "sexo": sexo,
            "conduta": conduta, "data_impressao": impressao, "paginas": 1, "paginas_sem_texto": [], "autos": [r],
            "eventos": list(eventos), "historico_oculto": []}


DIV, CONF, LDIV = "percentual-de-progressao-diverge", "percentual-de-progressao-confere", "fracao-de-livramento-diverge"

# =====================================================================================================================
# 1. FRAÇÕES DE PROGRESSÃO PELA DATA DO FATO (Auditoria, crime a crime)
# =====================================================================================================================
k = 3001
c1 = crime(P(k, 2018), "ART 155: Furto", anos(3, 4), "10/08/2017", tipo=T_FURTO, fp="1/6 - Comum", fl="1/3 - Comum Primário")
novo(k, "Progressão", "Furto de 2017, primário, sem violência: o SEEU aplica 1/6, mas os 16% da Lei 13.964/2019 retroagem",
     "Auditoria: alerta 'percentual de progressão do SEEU (1/6) maior que o legal (16%)', 8 dias a mais; livramento 1/3 confere.",
     "Fato em 10/08/2017: a redação então vigente do art. 112 dava 1/6. A Lei 13.964/2019 (art. 112, I: 16% ao primário sem "
     "violência) é mais benéfica e retroage (CF, art. 5º, XL; CP, art. 2º, p. ú.); a Lei 15.402/2026, que devolveu 1/6, é mais "
     "gravosa e não alcança o fato (vale a lei intermediária mais benéfica). Pena 3a4m = 1.215 dias: 1/6 = 202,5 dias; 16% = 194,4 "
     "dias; diferença 8 dias contra o assistido. Livramento: primário, crime comum, 1/3 (CP, art. 83, I).",
     exe(k, [c1]), [AUD(DIV, contem=["16%"]), AUD(CONF, False), AUD(LDIV, False)])

k = 3002
c1 = crime(P(k, 2022), "ART 155: Furto", anos(5), "15/03/2022", tipo=T_FURTO_Q, fp="16% - Art.112, I, da LEP", fl="1/3 - Comum Primário")
novo(k, "Progressão", "Furto qualificado de 2022, primário: 16% (Lei 13.964/2019) confere",
     "Auditoria: 'percentual de progressão confere (16%)'; nenhum alerta de fração.",
     "Fato em 15/03/2022: LEP, art. 112, I (Lei 13.964/2019): 16% ao primário em crime sem violência. A Lei 15.402/2026 (1/6) "
     "é posterior e mais gravosa. Livramento 1/3 (CP, art. 83, I).",
     exe(k, [c1]), [AUD(CONF), AUD(DIV, False), AUD(LDIV, False)])

k = 3003
a = anterior(k, "ART 155: Furto", 365, "10/01/2018", "10/07/2018", "20/08/2018", "20/08/2019", tipo=T_FURTO, ano=2018)
c1 = crime(P(k, 2023), "ART 171: Estelionato", anos(4, 6), "03/02/2023", tipo=T_ESTEL, rc="S", fp="20% - Art.112, II, da LEP",
           fl="1/2 - Comum Reincidente")
novo(k, "Progressão", "Estelionato de 2023, reincidente genérico demonstrado no RSPE: 20% e livramento 1/2 conferem",
     "Auditoria: 'percentual de progressão confere (20%)'; sem alerta de fração de livramento.",
     "Condenação anterior (furto) transitada em 20/08/2018, extinta em 20/08/2019; fato novo em 03/02/2023: trânsito anterior ao "
     "fato e menos de 5 anos desde a extinção (20/08/2024 > fato) - reincidente (CP, arts. 63 e 64, I). Crime sem violência: 20% "
     "(LEP, art. 112, II, Lei 13.964/2019). Livramento: reincidente em crime doloso, 1/2 (CP, art. 83, II).",
     exe(k, [a, c1]), [AUD(CONF), AUD(DIV, False), AUD(LDIV, False)])

k = 3004
a = anterior(k, "ART 155: Furto", 400, "05/02/2014", "05/09/2014", "10/11/2014", "10/12/2015", tipo=T_FURTO, ano=2014)
c1 = crime(P(k, 2018), "ART 171: Estelionato", anos(4), "05/05/2018", tipo=T_ESTEL, rc="S", fp="20% - Art.112, II, da LEP",
           fl="1/2 - Comum Reincidente")
novo(k, "Progressão", "Estelionato de 2018, reincidente: o SEEU aplica 20%, mas a lei do fato dava 1/6 (os 20% não retroagem)",
     "Auditoria: alerta 'percentual de progressão do SEEU (20%) maior que o legal (1/6 = 16,67%)'.",
     "Fato em 05/05/2018: art. 112 da LEP (redação da Lei 10.792/2003) - 1/6 para todos os crimes comuns. A Lei 13.964/2019 deu 20% "
     "ao reincidente (II): mais gravosa, não retroage (CF, art. 5º, XL). Reincidência demonstrada: trânsito anterior em 10/11/2014, "
     "extinção em 10/12/2015 (+5 anos = 10/12/2020 > fato). Pena 4 anos = 1.460 dias: 20% = 292; 1/6 = 243 - 49 dias a mais.",
     exe(k, [a, c1]), [AUD(DIV, contem=["20%"])])

k = 3005
c1 = crime(P(k, 2021), "ART 157: Roubo", anos(6, 8), "20/11/2021", tipo=T_ROUBO_M, vga="S", fp="25% - Art.112, III, da LEP",
           fl="1/3 - Comum Primário")
novo(k, "Progressão", "Roubo majorado pelo concurso de pessoas (2021), primário: 25% confere; não é hediondo",
     "Auditoria: 'percentual de progressão confere (25%)'; sem alerta.",
     "Fato em 20/11/2021, primário, crime com grave ameaça: 25% (LEP, art. 112, III, Lei 13.964/2019). O roubo majorado só pelo "
     "concurso de pessoas (art. 157, § 2º, II) não está no rol da Lei 8.072/90 (art. 1º, II, só alcança a restrição de liberdade, "
     "a arma de fogo e o resultado lesão grave ou morte). Livramento 1/3.",
     exe(k, [c1]), [AUD(CONF), AUD(DIV, False), AUD(LDIV, False)])

k = 3006
a = anterior(k, "ART 157: Roubo", anos(5, 4), "02/02/2015", "02/09/2015", "10/10/2015", "10/02/2021", tipo=T_ROUBO, vga="S", ano=2015)
c1 = crime(P(k, 2022), "ART 157: Roubo", anos(7), "12/06/2022", tipo=T_ROUBO, vga="S", rc="S", fp="30% - Art.112, IV, da LEP",
           fl="1/2 - Comum Reincidente")
novo(k, "Progressão", "Roubo de 2022, reincidente em crime com violência (anterior também roubo): 30% confere",
     "Auditoria: 'percentual de progressão confere (30%)'; sem alerta de livramento (1/2).",
     "Anterior: roubo transitado em 10/10/2015, extinto em 10/02/2021; fato novo em 12/06/2022 - reincidente (CP, arts. 63 e 64, I). "
     "Reincidente em crime com violência: 30% (LEP, art. 112, IV, Lei 13.964/2019). Livramento 1/2 (CP, art. 83, II).",
     exe(k, [a, c1]), [AUD(CONF), AUD(DIV, False), AUD(LDIV, False)])

k = 3007
c1 = crime(P(k, 2019), "ART 157: Roubo", anos(5, 6), "01/03/2019", tipo=T_ROUBO, vga="S", fp="25% - Art.112, III, da LEP",
           fl="1/3 - Comum Primário")
novo(k, "Progressão", "Roubo de 2019 (antes da Lei 13.964/2019), primário: o SEEU aplica 25%, mas a lei do fato dava 1/6",
     "Auditoria: alerta 'percentual de progressão do SEEU (25%) maior que o legal (1/6 = 16,67%)'.",
     "Fato em 01/03/2019: art. 112 da LEP (Lei 10.792/2003) - 1/6, sem distinção da violência. Os 25% da Lei 13.964/2019 (III) e os "
     "da Lei 15.402/2026 (I) são mais gravosos e não retroagem. Pena 5a6m = 2.005 dias: 25% = 501; 1/6 = 334 - 167 dias a mais.",
     exe(k, [c1]), [AUD(DIV, contem=["25%"])])

k = 3008
c1 = crime(P(k, 2018), "ART 121: Homicídio qualificado", anos(14), "15/07/2018", tipo=T_HQ, vga="S", morte="S",
           fp="50% - Art.112, VI, a, da LEP", fl="1/1 - Hediondo com resultado morte")
novo(k, "Progressão", "Homicídio qualificado consumado de 2018, primário: o SEEU aplica 50% e veda o livramento; a lei do fato dava 2/5 e livramento 2/3",
     "Auditoria: alerta de progressão (50% maior que o legal 40%) e alerta de livramento (1/1 maior que o legal 2/3).",
     "Fato em 15/07/2018: Lei 8.072/90, art. 2º, § 2º (Lei 11.464/2007): 2/5 ao primário em hediondo. Os 50% e a vedação do "
     "livramento (LEP, art. 112, VI, a, Lei 13.964/2019) são posteriores e mais gravosos - não retroagem. Livramento: CP, art. 83, V: "
     "2/3 (hediondo, não reincidente específico). Pena 14 anos.",
     exe(k, [c1]), [AUD(DIV, contem=["50%", "40%"]), AUD(LDIV, contem=["1/1", "2/3"])])

k = 3010
c1 = crime(P(k, 2026), "ART 213: Estupro", anos(9), "10/04/2026", sentenca="10/07/2026", transito="20/08/2026", tipo=T_ESTUPRO,
           vga="S", fp="70% - Art.112, V, da LEP", fl="2/3 - Hediondo")
novo(k, "Progressão", "Estupro de 10/04/2026 (Lei 15.358/2026), primário: 70% confere",
     "Auditoria: 'percentual de progressão confere (70%)'; sem alerta de livramento (2/3).",
     "Fato em 10/04/2026, depois de 25/03/2026 (Lei 15.358/2026, DOU 25/03/2026, vigência na publicação): hediondo, primário - 70% "
     "(LEP, art. 112, V). Livramento: 2/3 (CP, art. 83, V; a Lei 15.358/2026 não veda o livramento nesse inciso).",
     exe(k, [c1], ini="10/04/2026"), [AUD(CONF), AUD(DIV, False), AUD(LDIV, False)])

k = 3011
c1 = crime(P(k, 2026), "ART 33: Tráfico de drogas", anos(6, 3), "15/06/2026", sentenca="20/08/2026", transito="25/09/2026",
           lei=DROGAS, tipo=T_TRAF, fp="40% - Hediondo primário", fl="2/3 - Hediondo")
novo(k, "Progressão", "Tráfico de 15/06/2026, primário: o SEEU aplica 40%, menos que os 70% da lei - favorece o assistido, sem alerta",
     "Auditoria: nenhum item de percentual acima do legal (o SEEU aplica menos que a lei; decisão do usuário: não se alerta).",
     "Tráfico (Lei 11.343/06, art. 33, caput) é equiparado a hediondo (CF, art. 5º, XLIII). Fato em 15/06/2026: 70% (LEP, art. 112, V, "
     "Lei 15.358/2026). O SEEU aplica 40%: menor que o legal, favorece o assistido - por decisão do usuário não gera item.",
     exe(k, [c1], ini="15/06/2026"), [AUD(DIV, False), AUD(LDIV, False)])

k = 3012
a = anterior(k, "ART 155: Furto", 500, "01/02/2016", "01/08/2016", "05/09/2016", "15/12/2017", tipo=T_FURTO, ano=2016)
c1 = crime(P(k, 2020), "ART 33: Tráfico de drogas", anos(7), "01/03/2020", lei=DROGAS, tipo=T_TRAF, rc="S",
           fp="60% - Hediondo reincidente", fl="1/1 - Hediondo reincidente")
novo(k, "Progressão", "Tráfico de 2020, reincidente só por furto (genérico): o SEEU aplica 60% e veda o livramento",
     "Auditoria: alerta de progressão (60% maior que o legal 40%) e alerta de livramento (1/1 maior que o legal 2/3).",
     "Anterior: furto (não hediondo) transitado em 05/09/2016, extinto 15/12/2017; fato em 01/03/2020 - reincidente genérico. "
     "Os 60% do art. 112, VII (Lei 13.964/2019) são do reincidente em hediondo; ao reincidente genérico aplica-se 40% (STJ, Tema 1084; "
     "STF, Tema 1169). Livramento: a vedação do CP, art. 83, V, e da Lei 11.343/06, art. 44, p. ú., é do reincidente específico - "
     "aqui 2/3.", exe(k, [a, c1]), [AUD(DIV, contem=["60%", "40%"]), AUD(LDIV, contem=["1/1", "2/3"])])

k = 3013
a = anterior(k, "ART 213: Estupro", anos(6, 6), "10/05/2012", "10/12/2012", "20/02/2013", "10/08/2019", tipo=T_ESTUPRO, vga="S", ano=2012)
c1 = crime(P(k, 2024), "ART 217-A: Estupro de vulnerável", anos(10), "18/02/2024", tipo=T_EV, rc="S", re_="S",
           fp="60% - Hediondo reincidente", fl="1/1 - Hediondo reincidente")
novo(k, "Progressão", "Estupro de vulnerável de 2024, reincidente específico em hediondo (estupro anterior): 60% e livramento vedado conferem",
     "Auditoria: 'reincidência específica confere com o RSPE' e 'percentual de progressão confere (60%)'; sem alerta de livramento.",
     "Anterior: estupro (hediondo) transitado em 20/02/2013, extinto em 10/08/2019 (+5 anos = 10/08/2024 > fato de 18/02/2024): "
     "reincidente específico em hediondo. 60% (LEP, art. 112, VII, Lei 13.964/2019). Livramento vedado (CP, art. 83, V).",
     exe(k, [a, c1]), [AUD(CONF), AUD(DIV, False), AUD(LDIV, False), AUD("reincidencia-especifica-confere-com-o-rspe")])

k = 3014
c1 = crime(P(k, 2021), "ART 157: Latrocínio", anos(22), "30/06/2021", tipo=T_LATRO, vga="S", morte="S",
           fp="50% - Art.112, VI, a, da LEP", fl="1/1 - Hediondo com resultado morte")
novo(k, "Progressão", "Latrocínio de 2021, primário: 50% e livramento vedado conferem",
     "Auditoria: 'percentual de progressão confere (50%)'; livramento vedado só como informação (sem alerta).",
     "Hediondo com resultado morte (Lei 8.072/90, art. 1º, II, c), fato em 30/06/2021, primário: 50% e livramento vedado "
     "(LEP, art. 112, VI, a, Lei 13.964/2019).", exe(k, [c1]), [AUD(CONF), AUD(DIV, False), AUD(LDIV, False)])

k = 3015
c1 = crime(P(k, 2026), "ART 157: Latrocínio", anos(24), "05/04/2026", sentenca="25/07/2026", transito="31/08/2026", tipo=T_LATRO,
           vga="S", morte="S", fp="75% - Art.112, VI, a, da LEP", fl="1/1 - Hediondo com resultado morte")
novo(k, "Progressão", "Latrocínio de 05/04/2026 (Lei 15.358/2026), primário: 75% e livramento vedado conferem",
     "Auditoria: 'percentual de progressão confere (75%)'; sem alerta.",
     "Fato em 05/04/2026: LEP, art. 112, VI, a (Lei 15.358/2026): 75% ao primário em hediondo com resultado morte, vedado o "
     "livramento.", exe(k, [c1], ini="05/04/2026"), [AUD(CONF), AUD(DIV, False), AUD(LDIV, False)])

k = 3016
a = anterior(k, "ART 155: Furto", 420, "03/03/2017", "03/10/2017", "10/11/2017", "15/01/2019", tipo=T_FURTO, ano=2017)
c1 = crime(P(k, 2022), "ART 121: Homicídio qualificado", anos(16), "08/08/2022", tipo=T_HQ, vga="S", morte="S", rc="S",
           fp="70% - Art.112, VIII, da LEP", fl="1/1 - Hediondo com resultado morte")
novo(k, "Progressão", "Homicídio qualificado consumado de 2022, reincidente genérico (anterior: furto): o SEEU aplica 70%",
     "Auditoria: alerta 'percentual de progressão do SEEU (70%) maior que o legal (50%)'.",
     "Anterior: furto transitado em 10/11/2017, extinto em 15/01/2019; fato em 08/08/2022 - reincidente, mas não em hediondo. "
     "Os 70% (art. 112, VIII) são do reincidente em hediondo com morte; ao reincidente genérico aplica-se o VI, a: 50% (STJ, Tema "
     "1196). Pena 16 anos = 5.840 dias: 70% = 4.088; 50% = 2.920.", exe(k, [a, c1]), [AUD(DIV, contem=["70%", "50%"])])

k = 3017
a = anterior(k, "ART 121: Homicídio qualificado", anos(12), "10/02/2008", "10/12/2009", "15/03/2010", "01/06/2021", tipo=T_HQ,
             vga="S", morte="S", ano=2008)
c1 = crime(P(k, 2023), "ART 121: Homicídio qualificado", anos(18), "22/05/2023", tipo=T_HQ, vga="S", morte="S", rc="S", re_="S",
           fp="70% - Art.112, VIII, da LEP", fl="1/1 - Hediondo reincidente")
novo(k, "Progressão", "Homicídio qualificado de 2023, reincidente específico em hediondo com morte: 70% e livramento vedado conferem",
     "Auditoria: 'percentual de progressão confere (70%)'; sem alerta de livramento.",
     "Anterior: homicídio qualificado transitado em 15/03/2010, extinto em 01/06/2021 (+5 anos = 01/06/2026 > fato de 22/05/2023): "
     "reincidente em hediondo com morte - 70% e livramento vedado (LEP, art. 112, VIII, Lei 13.964/2019).",
     exe(k, [a, c1]), [AUD(CONF), AUD(DIV, False), AUD(LDIV, False)])

# feminicídio
k = 3018
c1 = crime(P(k, 2025), "ART 121-A: Feminicídio", anos(24), "20/01/2025", tipo=T_FEM_A, vga="S", morte="S",
           fp="55% - Art.112, VI-A, da LEP", fl="1/1 - Feminicídio")
novo(k, "Progressão", "Feminicídio (art. 121-A) de 20/01/2025, primário: 55% e livramento vedado conferem",
     "Auditoria: 'percentual de progressão confere (55%)'; sem alerta de livramento.",
     "Fato em 20/01/2025, entre a Lei 14.994/2024 (DOU 10/10/2024) e a Lei 15.358/2026: LEP, art. 112, VI-A - 55% ao primário "
     "condenado por feminicídio, vedado o livramento.", exe(k, [c1]), [AUD(CONF), AUD(DIV, False), AUD(LDIV, False)])

k = 3019
c1 = crime(P(k, 2026), "ART 121-A: Feminicídio", anos(26), "20/04/2026", sentenca="20/07/2026", transito="28/08/2026",
           tipo=T_FEM_A, vga="S", morte="S", fp="75% - Art.112, VI, d, da LEP", fl="1/1 - Feminicídio")
novo(k, "Progressão", "Feminicídio de 20/04/2026 (Lei 15.358/2026), primário: 75% e livramento vedado conferem",
     "Auditoria: 'percentual de progressão confere (75%)'; sem alerta.",
     "Fato em 20/04/2026: LEP, art. 112, VI, d (Lei 15.358/2026) - 75%, vedado o livramento.",
     exe(k, [c1], ini="20/04/2026"), [AUD(CONF), AUD(DIV, False), AUD(LDIV, False)])

k = 3020
c1 = crime(P(k, 2023), "ART 121: Homicídio qualificado", anos(15), "11/11/2023", tipo=T_FEM_VI, vga="S", morte="S",
           fp="55% - Art.112, VI-A, da LEP", fl="1/1 - Feminicídio")
novo(k, "Progressão", "Feminicídio pelo antigo art. 121, § 2º, VI (fato de 2023, antes da Lei 14.994/2024): o SEEU aplica os 55% da lei nova",
     "Auditoria: alerta 'percentual de progressão do SEEU (55%) maior que o legal (50%)'; livramento vedado confere.",
     "Fato em 11/11/2023, antes da Lei 14.994/2024: feminicídio era homicídio qualificado (hediondo) - com resultado morte, primário: "
     "50% e livramento vedado (LEP, art. 112, VI, a, Lei 13.964/2019). Os 55% do VI-A (Lei 14.994/2024) não retroagem. Pena 15 anos "
     "= 5.475 dias: 55% = 3.011; 50% = 2.737.", exe(k, [c1]), [AUD(DIV, contem=["55%", "50%"]), AUD(LDIV, False)])

# organização criminosa e milícia
k = 3021
c1 = crime(P(k, 2021), "ART 2: Organização criminosa", anos(5), "14/04/2021", lei="12850/13 - Organizações Criminosas", tipo=T_ORCRIM,
           orcrim="S", fp="50% - Art.112, VI, b, da LEP", fl="1/3 - Comum Primário")
novo(k, "Progressão", "Comando de organização criminosa (Lei 12.850/2013), fato de 2021: 50% confere, livramento 1/3",
     "Auditoria: 'percentual de progressão confere (50%)'; sem alerta.",
     "Fato em 14/04/2021, condenação por exercer o comando de organização criminosa: 50% (LEP, art. 112, VI, b, Lei 13.964/2019), "
     "sem vedação do livramento nessa redação. Crime não hediondo - livramento 1/3 (CP, art. 83, I).",
     exe(k, [c1]), [AUD(CONF), AUD(DIV, False), AUD(LDIV, False)])

k = 3022
c1 = crime(P(k, 2026), "ART 288-A: Constituição de milícia privada", anos(6), "01/06/2026", sentenca="10/08/2026", transito="20/09/2026",
           tipo=T_MILICIA, fp="75% - Art.112, VI, c, da LEP", fl="1/3 - Comum Primário")
novo(k, "Progressão", "Milícia privada (art. 288-A), fato de 01/06/2026: 75% confere; livramento 1/3 (sem vedação)",
     "Auditoria: 'percentual de progressão confere (75%)'; sem alerta de livramento.",
     "Fato em 01/06/2026: LEP, art. 112, VI, c, com o caput do inciso VI na redação da Lei 15.358/2026: 75%. A alínea c não veda o "
     "livramento; o art. 288-A não é hediondo - 1/3 (CP, art. 83, I).",
     exe(k, [c1], ini="01/06/2026"), [AUD(CONF), AUD(DIV, False), AUD(LDIV, False)])

k = 3023
c1 = crime(P(k, 2026), "ART 2: Domínio social estruturado", anos(26, 8), "02/05/2026", sentenca="20/08/2026", transito="30/09/2026",
           lei="15358/26 - Marco Legal do Combate ao Crime Organizado", tipo=T_DOMINIO, vga="S", orcrim="S",
           fp="75% - Art.112, VI, b, da LEP", fl="1/1 - Comando de organização ultraviolenta")
novo(k, "Progressão", "Comando de organização criminosa ultraviolenta pelo próprio tipo (Lei 15.358/2026, art. 2º, § 1º, I): 75% e livramento vedado certos",
     "Auditoria: nenhum alerta de fração (75% e 1/1 conferem); a condição de 'ultraviolenta' está no próprio tipo da condenação.",
     "Fato em 02/05/2026. O crime de domínio social estruturado é praticado por integrante de organização criminosa ultraviolenta "
     "(Lei 15.358/2026, art. 2º, caput e § 2º), com o aumento do comando (§ 1º, I); é hediondo (Lei 8.072/90, art. 1º, p. ú., VIII). "
     "LEP, art. 112, VI, b: 75%, vedado o livramento; a própria Lei 15.358/2026, art. 2º, § 4º, III, também veda o livramento.",
     exe(k, [c1], ini="02/05/2026"), [AUD(DIV, False), AUD(LDIV, False)])

# Lei 15.402/2026
k = 3024
c1 = crime(P(k, 2026), "ART 155: Furto", anos(6), "10/06/2026", sentenca="10/08/2026", transito="15/09/2026", tipo=T_FURTO_Q,
           fp="1/6 - Art.112, caput, da LEP", fl="1/3 - Comum Primário")
novo(k, "Progressão", "Furto de 10/06/2026 (Lei 15.402/2026), primário: 1/6 confere",
     "Auditoria: 'percentual de progressão confere (1/6)'; sem alerta.",
     "Fato em 10/06/2026, depois da Lei 15.402/2026 (DOU 08/05/2026): o caput do art. 112 fixa 1/6 e o inciso que dava 16% ao "
     "primário sem violência deixou de existir. Primário sem violência: 1/6. Livramento 1/3.",
     exe(k, [c1], ini="10/06/2026"), [AUD(CONF), AUD(DIV, False), AUD(LDIV, False)])

k = 3025
a = anterior(k, "ART 155: Furto", 380, "10/03/2020", "10/09/2020", "20/10/2020", "20/12/2021", tipo=T_FURTO, ano=2020)
c1 = crime(P(k, 2026), "ART 155: Furto", anos(7), "01/07/2026", sentenca="20/08/2026", transito="25/09/2026", tipo=T_FURTO_Q, rc="S",
           fp="30% - Art.112, II, da LEP", fl="1/2 - Comum Reincidente")
novo(k, "Progressão", "Furto de 01/07/2026, reincidente: o SEEU aplica 30% (inciso II), mas o crime não tem violência - 20% (inciso III)",
     "Auditoria: item de percentual acima do legal: SEEU 30%, legal 20%.",
     "Fato em 01/07/2026 (Lei 15.402/2026). O inciso II (30%) exige condenação atual por crime com violência ou grave ameaça; o "
     "furto não a tem: reincidente 'em crime diverso dos referidos nos incisos I e II' - 20% (III). Reincidência: furto transitado em "
     "20/10/2020, extinto 20/12/2021. Pena 7 anos = 2.555 dias: 30% = 766; 20% = 511.",
     exe(k, [a, c1], ini="01/07/2026"), [AUD(DIV, contem=["30%", "20%"])])

k = 3026
c1 = crime(P(k, 2026), "ART 157: Roubo", anos(6, 9), "20/06/2026", sentenca="20/08/2026", transito="25/09/2026", tipo=T_ROUBO, vga="S",
           fp="30% - Art.112, II, da LEP", fl="1/3 - Comum Primário")
novo(k, "Progressão", "Roubo de 20/06/2026, primário: o SEEU aplica 30% (do reincidente); a lei dá 25%",
     "Auditoria: alerta 'percentual de progressão do SEEU (30%) maior que o legal (25%)'.",
     "Fato em 20/06/2026: LEP, art. 112, I (Lei 15.402/2026): 25% ao primário em crime com violência ou grave ameaça. Sem "
     "condenação anterior no RSPE e sem marcação de reincidência. Pena 6a9m = 2.460 dias: 30% = 738; 25% = 615.",
     exe(k, [c1], ini="20/06/2026"), [AUD(DIV, contem=["30%", "25%"])])

k = 3027
c1 = crime(P(k, 2023), "ART 359-L: Abolição violenta do Estado Democrático de Direito", anos(5, 6), "08/01/2023", tipo=T_GOLPE, vga="S",
           fp="25% - Art.112, III, da LEP", fl="1/3 - Comum Primário")
novo(k, "Progressão", "Crime contra o Estado Democrático de Direito (Título XII do CP), fato de 2023, primário: a Lei 15.402/2026 afasta os 25% e retroage (1/6)",
     "Auditoria: alerta 'percentual de progressão do SEEU (25%) maior que o legal (1/6 = 16,67%)'.",
     "Fato em 08/01/2023: pela Lei 13.964/2019, crime com violência ou grave ameaça, primário - 25%. A Lei 15.402/2026 (DOU 08/05/2026) "
     "excluiu expressamente dos incisos I e II do art. 112 'os crimes previstos no Título XII da Parte Especial' do CP (arts. 359-I a "
     "359-U, crimes contra o Estado Democrático de Direito): o primário fica no caput, 1/6. É lei posterior mais benéfica e retroage "
     "(CF, art. 5º, XL; CP, art. 2º, p. ú.). Pena 5a6m = 2.005 dias: 25% = 501; 1/6 = 334 - 167 dias a mais.",
     exe(k, [c1]), [AUD(DIV, contem=["25%"], nota="O programa não tem regra para a exceção do Título XII da Lei 15.402/2026: confere os 25% da Lei 13.964/2019. Pela lei, 1/6 (retroativo).")])

# hediondo antes de 2007 e entre 2007 e 2020
k = 3028
c1 = crime(P(k, 2005), "ART 213: Estupro", anos(7), "12/09/2005", sentenca="15/06/2006", transito="20/08/2006", tipo=T_ESTUPRO, vga="S",
           fp="2/5 - Hediondo primário", fl="2/3 - Hediondo")
novo(k, "Progressão", "Estupro de 2005 (antes da Lei 11.464/2007): o SEEU aplica 2/5; a lei do fato dava 1/6",
     "Auditoria: alerta 'percentual de progressão do SEEU (40%) maior que o legal (1/6 = 16,67%)'; livramento 2/3 confere.",
     "Fato em 12/09/2005: a vedação de progressão da Lei 8.072/90 foi declarada inconstitucional (STF, HC 82.959) e a Lei 11.464/2007 "
     "(2/5) não retroage: vale 1/6 do art. 112 da LEP (Súmula Vinculante 26/STF; Súmula 471/STJ). Livramento: hediondo, 2/3 "
     "(CP, art. 83, V, desde a Lei 8.072/90). A execução começou em 2021 (prisão tardia).",
     exe(k, [c1]), [AUD(DIV, contem=["40%"]), AUD(LDIV, False)])

k = 3029
a = anterior(k, "ART 155: Furto", 450, "10/01/2009", "10/07/2009", "20/08/2009", "20/11/2010", tipo=T_FURTO, ano=2009)
c1 = crime(P(k, 2012), "ART 217-A: Estupro de vulnerável", anos(9), "05/05/2012", tipo=T_EV, rc="S", fp="3/5 - Hediondo reincidente",
           fl="2/3 - Hediondo")
novo(k, "Progressão", "Estupro de vulnerável de 2012, reincidente genérico (anterior: furto): o SEEU aplica 3/5; a Lei 13.964/2019 retroage com 40%",
     "Auditoria: alerta 'percentual de progressão do SEEU (60%) maior que o legal (40%)'.",
     "Fato em 05/05/2012: Lei 8.072/90, art. 2º, § 2º (Lei 11.464/2007) dava 3/5 ao reincidente. A Lei 13.964/2019 reservou 60% ao "
     "reincidente em hediondo; ao reincidente genérico, 40% (STJ, Tema 1084; STF, Tema 1169) - mais benéfico, retroage. Anterior: furto "
     "transitado em 20/08/2009, extinto 20/11/2010 (+5 = 20/11/2015 > fato).", exe(k, [a, c1]), [AUD(DIV, contem=["60%", "40%"])])

k = 3030
a = anterior(k, "ART 155: Furto", 400, "10/02/2019", "10/08/2019", "20/09/2019", "15/12/2020", tipo=T_FURTO, ano=2019)
c1 = crime(P(k, 2026), "ART 213: Estupro", anos(8), "15/04/2026", sentenca="10/07/2026", transito="20/08/2026", tipo=T_ESTUPRO,
           vga="S", rc="S", fp="80% - Art.112, VII, da LEP", fl="2/3 - Hediondo")
novo(k, "Progressão", "Estupro de 15/04/2026, reincidente genérico (anterior: furto): o SEEU aplica 80%; pela leitura do Tema 1084, 70%",
     "Auditoria: item de percentual acima do legal (80% x 70%) - tese, sem precedente próprio para a Lei 15.358/2026.",
     "Fato em 15/04/2026 (Lei 15.358/2026). O inciso VII (80%) fala do 'reincidente na prática de crime hediondo' - mesma redação que o "
     "STJ (Tema 1084) e o STF (Tema 1169) leram como reincidência específica. Reincidente genérico: 70% (V). Pena 8 anos = 2.920 dias: "
     "80% = 2.336; 70% = 2.044.", exe(k, [a, c1], ini="15/04/2026"),
     [dict(AUD(DIV, contem=["80%", "70%"]), decisao=True)])

k = 3031
c1 = crime(P(k, 2023), "ART 33: Tráfico de drogas", anos(1, 8), "14/02/2023", lei=DROGAS, tipo=T_TRAF_P, fp="40% - Hediondo primário",
           fl="2/3 - Hediondo")
c2 = crime(P(k, 2024), "ART 155: Furto", anos(1, 6), "10/01/2024", tipo=T_FURTO, fp="16% - Art.112, I, da LEP", fl="1/3 - Comum Primário")
novo(k, "Progressão", "Tráfico privilegiado (§ 4º) de 2023 tratado como hediondo pelo SEEU (40% e 2/3)",
     "Auditoria: alerta de progressão (40% maior que o legal 16%) e alerta de livramento (2/3 maior que o legal 1/3).",
     "O tráfico privilegiado não é hediondo nem equiparado (LEP, art. 112, § 5º; STF, HC 118.533). Fato em 14/02/2023, primário: 16% "
     "(art. 112, I, Lei 13.964/2019). Livramento: o art. 44, p. ú., da Lei 11.343/06 e o CP, art. 83, V, não alcançam o privilegiado "
     "- 1/3. Junto, um furto (16%) para a pena total passar de 2 anos.", exe(k, [c1, c2]),
     [AUD(DIV, contem=["40%", "16%"]), AUD(LDIV, contem=["2/3", "1/3"])])

k = 3032
c1 = crime(P(k, 2021), "ART 35: Associação para o tráfico", anos(4), "20/07/2021", lei=DROGAS, tipo=T_ASSOC, fp="16% - Art.112, I, da LEP",
           fl="2/3 - Art. 44 Lei 11.343/06")
novo(k, "Livramento", "Associação para o tráfico (art. 35) de 2021, primário: progressão 16% (não é hediondo) e livramento 2/3 (Lei de Drogas, art. 44)",
     "Auditoria: 'percentual de progressão confere (16%)' e nenhum alerta de livramento.",
     "A associação para o tráfico não está no rol dos hediondos/equiparados (STJ): progressão de primário sem violência, 16% (LEP, "
     "art. 112, I, Lei 13.964/2019). Livramento: a Lei 11.343/06, art. 44, p. ú., manda 2/3 nos crimes dos arts. 33, caput e § 1º, e "
     "34 a 37 - o art. 35 está incluído.", exe(k, [c1]), [AUD(CONF), AUD(DIV, False), AUD(LDIV, False)])

# mulher (art. 112, § 3º)
k = 3033
c1 = crime(P(k, 2023), "ART 155: Furto", anos(4), "05/04/2023", tipo=T_FURTO_Q, fp="16% - Art.112, I, da LEP", fl="1/3 - Comum Primário")
novo(k, "Progressão", "Mulher primária, furto sem violência, SEEU 16%: a progressão especial de 1/8 (art. 112, § 3º) deve ser lembrada",
     "Auditoria: informação 'Progressão especial da mulher (1/8): a verificar' (gestante, mãe ou responsável por criança ou pessoa com "
     "deficiência - dado que o RSPE não traz).",
     "LEP, art. 112, § 3º: mulher gestante, mãe ou responsável por criança ou pessoa com deficiência - 1/8 da pena, se o crime não teve "
     "violência ou grave ameaça, não foi contra filho ou dependente, é primária com bom comportamento e não integrou organização "
     "criminosa. Pena 4 anos = 1.460 dias: 16% = 233; 1/8 = 182. Sexo informado na ficha (F).",
     exe(k, [c1]), [AUD("progressao-especial-da-mulher-1-8-a-verificar")], ficha=ficha(k, unidade="ESTABELECIMENTO PENAL FEMININO SIMULADO", sexo="F"))

k = 3034
c1 = crime(P(k, 2022), "ART 33: Tráfico de drogas", anos(5, 10), "18/08/2022", lei=DROGAS, tipo=T_TRAF, fp="40% - Hediondo primário",
           fl="2/3 - Hediondo")
novo(k, "Progressão", "Mulher primária condenada por tráfico (equiparado a hediondo, sem violência): a hipótese de 1/8 também vale",
     "Auditoria: informação 'Progressão especial da mulher (1/8): a verificar'; 40% confere.",
     "O art. 112, § 3º, da LEP não exclui hediondos nem equiparados: exige só ausência de violência ou grave ameaça, crime não contra "
     "filho ou dependente, primariedade, bom comportamento e não integrar organização criminosa (STJ, HC 522.651/SP). Tráfico sem "
     "violência: cabe a hipótese. Pena 5a10m = 2.125 dias: 40% = 850; 1/8 = 265.",
     exe(k, [c1]), [AUD("progressao-especial-da-mulher-1-8-a-verificar"), AUD(CONF)], manuais={"sexo": "F"})

# =====================================================================================================================
# 2. REINCIDÊNCIA PELAS DATAS (CP, arts. 63 e 64, I)
# =====================================================================================================================
k = 3035
a = anterior(k, "ART 155: Furto", 300, "05/03/2014", "05/09/2014", "20/10/2014", "10/02/2017", tipo=T_FURTO, ano=2014)
c1 = crime(P(k, 2022), "ART 155: Furto", anos(5), "15/03/2022", tipo=T_FURTO_Q, rc="S", fp="20% - Art.112, II, da LEP",
           fl="1/2 - Comum Reincidente")
novo(k, "Progressão", "Condenação anterior extinta há mais de 5 anos do fato novo (depurada): o SEEU marca reincidente e aplica 20% e 1/2",
     "Auditoria: item que aponta 16% (primário) no lugar dos 20% e 1/3 no lugar de 1/2.",
     "Anterior extinta em 10/02/2017; fato novo em 15/03/2022: passaram mais de 5 anos (10/02/2022 < fato) - a condenação não gera "
     "reincidência (CP, art. 64, I). Primário: 16% (LEP, art. 112, I) e livramento 1/3 (CP, art. 83, I; maus antecedentes não "
     "elevam a fração do livramento). Pena 5 anos = 1.825 dias: 20% = 365; 16% = 292.", exe(k, [a, c1]),
     [AUD("percentual-reincidencia-a-conferir", contem=["20%", "primário: 16%"]), AUD("fracao-livramento-reincidencia-a-conferir", contem=["1/2", "1/3"])])

k = 3037
a = crime(P(k, 2019), "ART 155: Furto", 365, "01/02/2019", sentenca="10/05/2021", transito="10/09/2021", tipo=T_FURTO,
          extinto="Sim", data_extincao="10/09/2022", regime="Aberto")
c1 = crime(P(k, 2021), "ART 155: Furto", anos(4, 6), "15/05/2021", tipo=T_FURTO_Q, rc="S", fp="20% - Art.112, II, da LEP",
           fl="1/2 - Comum Reincidente")
novo(k, "Progressão", "A condenação anterior transitou depois do fato novo: não há reincidência",
     "Auditoria: item que aponta 16% (primário) no lugar dos 20% e 1/3 no lugar de 1/2.",
     "Reincidência exige trânsito em julgado da condenação anterior ANTES do novo fato (CP, art. 63). Anterior: trânsito em "
     "10/09/2021; fato novo em 15/05/2021 - primário. 16% (LEP, art. 112, I) e 1/3. Pena 4a6m = 1.640 dias: 20% = 328; 16% = 262.",
     exe(k, [a, c1]), [AUD("percentual-reincidencia-a-conferir", contem=["20%", "primário: 16%"]), AUD("fracao-livramento-reincidencia-a-conferir", contem=["1/2", "1/3"])])

k = 3038
a = anterior(k, "ART 21: Vias de fato", 60, "10/01/2018", "10/06/2018", "20/07/2018", "20/09/2018",
             lei="3688/41 - Lei das Contravenções Penais", tipo=T_VIAS, ano=2018)
c1 = crime(P(k, 2022), "ART 155: Furto", anos(4), "10/10/2022", tipo=T_FURTO_Q, rc="S", fp="20% - Art.112, II, da LEP",
           fl="1/2 - Comum Reincidente")
novo(k, "Progressão", "Condenação anterior só por contravenção: o crime novo não é reincidente",
     "Auditoria: item que aponta 16% (primário) no lugar dos 20% e 1/3 no lugar de 1/2.",
     "CP, art. 63: reincidência é cometer CRIME depois do trânsito de condenação por CRIME. A contravenção anterior não torna "
     "reincidente quem comete crime (LCP, art. 7º, só trata de contravenção após contravenção). Primário: 16% e 1/3. Pena 4 anos = "
     "1.460 dias: 20% = 292; 16% = 233.", exe(k, [a, c1]), [AUD("percentual-reincidencia-a-conferir", contem=["20%", "primário: 16%"]), AUD("fracao-livramento-reincidencia-a-conferir", contem=["1/2", "1/3"])])

# =====================================================================================================================
# 3. ABA PROGRESSÃO: data refeita, unificação pendente, data-base (Temas 1006 e 1165), detração
# =====================================================================================================================
k = 3039
c1 = crime(P(k, 2022), "ART 155: Furto", anos(6), "20/01/2022", tipo=T_FURTO_Q, fp="16% - Art.112, I, da LEP", fl="1/3 - Comum Primário")
r = exe(k, [c1], ini="01/03/2025", db="01/09/2025", prog="18/07/2026", liv="",
        incs=[inc(REG, "Fechado - Regime Inicial", "", "01/03/2025"), inc("ALTERAÇÃO DE DATA-BASE", "", "01/09/2025", "01/09/2025")])
novo(k, "Progressão", "Data-base informada pelo operador (01/03/2025, início da prisão) refaz a progressão",
     "Aba Progressão: 14/02/2026* (recalculada pela data-base informada; SEEU: 18/07/2026).",
     "Pena 6 anos = 2.190 dias; furto de 2022, primário: 16%. Preso desde 01/03/2025, sem nada cumprido antes - remanescente na nova "
     "data-base = 2.190. Lapso = 2.190 x 16% = 350,4 -> 350 dias. Contando o dia do começo (CP, art. 10), os 350 dias vão de "
     "01/03/2025 a 13/02/2026; a progressão é devida em 14/02/2026 (data-base + lapso, a mesma convenção do SEEU). O SEEU contou de "
     "01/09/2025 (alteração de data-base sem fundamento): 2.190 - 184 = 2.006 x 16% = 320 -> 18/07/2026.",
     r, [C("prog", "eq", "14/02/2026*")], manuais={"data_base": "01/03/2025|início da prisão (alteração de data-base sem falta)"})

k = 3040
c1 = crime(P(k, 2019), "ART 155: Furto", anos(6), "10/10/2018", tipo=T_FURTO_Q, fp="1/6 - Comum", fl="1/3 - Comum Primário")
r = exe(k, [c1], ini="01/03/2025", db="01/09/2025", prog="01/08/2026", liv="",
        incs=[inc(REG, "Fechado - Regime Inicial", "", "01/03/2025"), inc("ALTERAÇÃO DE DATA-BASE", "", "01/09/2025", "01/09/2025")])
novo(k, "Progressão", "Data-base informada, furto de 2018 com 1/6 no SEEU: a data refeita deve usar os 16% retroativos",
     "Aba Progressão: 14/02/2026* (16% sobre 2.190 dias = 350 dias desde 01/03/2025); não 01/03/2026 (1/6).",
     "Mesmo quadro do caso anterior, com fato em 10/10/2018: a lei do fato dava 1/6, mas os 16% da Lei 13.964/2019 retroagem (CF, "
     "art. 5º, XL) - a Auditoria do próprio programa os aponta. Lapso 2.190 x 16% = 350 -> 14/02/2026. Com 1/6 seriam 365 dias -> "
     "01/03/2026. SEEU (1/6 desde 01/09/2025): 2.006 / 6 = 334,3 -> 334 -> 01/08/2026.",
     r, [C("prog", "eq", "14/02/2026*", nota="A data refeita usa o 1/6 do SEEU para fato anterior a 23/01/2020, embora a própria Auditoria diga que os 16% retroagem: 15 dias a mais contra o assistido.")], manuais={"data_base": "01/03/2025|início da prisão"})

k = 3041
c1 = crime(P(k, 2021), "ART 155: Furto", anos(2), "10/06/2021", sentenca="10/01/2022", transito="10/03/2022", tipo=T_FURTO,
           regime="Semiaberto", fp="16% - Art.112, I, da LEP", fl="1/3 - Comum Primário")
c2 = crime(P(k, 2023), "ART 157: Roubo", anos(9), "05/08/2023", sentenca="10/03/2026", transito="20/04/2026", tipo=T_ROUBO, vga="S",
           regime="Fechado", fp="25% - Art.112, III, da LEP", fl="1/3 - Comum Primário")
r = rspe(k, [c1, c2], [prisao("15/01/2026", P(k, 2023), "PRISÃO PREVENTIVA")],
         [inc(REG, "Semiaberto - Regime Inicial", "05/05/2022", "05/05/2022")], ini="15/01/2026", regime="Semiaberto - ATIVO",
         prog="", liv="", pena_cumprida="0a0m0d")
r["pena_cumprida"] = "0a0m0d"
novo(k, "Progressão", "Nova condenação em regime fechado não unificada (semiaberto atual): unificação pendente",
     "Aba Progressão: data estimada 09/08/2028* com a ressalva 'a verificar: unificação pendente' (início da custódia, 15/01/2026, + 937 dias); regime 'a verificar'.",
     "Regime atual semiaberto; roubo sentenciado em 10/03/2026 em regime fechado, sem soma/unificação decidida depois: a pena nova "
     "deve ser somada ao restante para fixar o regime (LEP, arts. 111, p. ú., e 118, II) - pena total 11 anos, regime fechado. "
     "Lapso pelas frações de cada crime: furto 730 x 16% = 116,8 -> 116; roubo 3.285 x 25% = 821,25 -> 821; total 937 dias. Contando o "
     "dia do começo (CP, art. 10), os 937 dias vão de 15/01/2026 a 08/08/2028; a progressão é devida em 09/08/2028 (início + lapso, "
     "a mesma convenção do SEEU para a data prevista).",
     r, [C("prog", "contem", "unificação pendente"), dict(C("prog", "regex", r"^09/08/2028\*", nota="O programa estima início + lapso - 1 (08/08/2028), ao passo que a progressão refeita pela data-base informada usa data-base + lapso (convenção do SEEU). Diferença de 1 dia; convenção."), decisao=True)])

k = 3042
c1 = crime(P(k, 2020), "ART 155: Furto", anos(4), "10/02/2020", tipo=T_FURTO_Q, fp="16% - Art.112, I, da LEP", fl="1/3 - Comum Primário")
c2 = crime(P(k, 2023), "ART 171: Estelionato", anos(5), "10/05/2023", sentenca="10/12/2025", transito="10/02/2026", tipo=T_ESTEL,
           fp="16% - Art.112, I, da LEP", fl="1/3 - Comum Primário")
r = rspe(k, [c1, c2], [prisao("01/04/2024", P(k, 2020), "PRISÃO DEFINITIVA")],
         [inc(REG, "Fechado - Regime Inicial", "", "01/04/2024"), inc("SOMATÓRIO DAS PENAS", "", "20/03/2026", "20/03/2026")],
         ini="01/04/2024", db="20/03/2026", prog=F(D("20/03/2026") + timedelta(days=int((3285 - 718) * 0.16) + int(0))), liv="")
novo(k, "Progressão", "Tema 1006/STJ: data-base movida para a data do somatório das penas, com a pessoa presa sem interrupção desde 2024",
     "Auditoria: alerta - data-base na soma/unificação de penas (a unificação não altera a data-base; a data certa é a última prisão, "
     "01/04/2024, ou o último marco legal).",
     "STJ, Tema 1006 (REsp 1.753.509): a superveniência de nova condenação no curso da execução não altera a data-base para a "
     "progressão; a soma das penas (LEP, art. 111) só refaz o cálculo sobre a pena total. Presa desde 01/04/2024, sem falta nem "
     "regressão; o SEEU usa 20/03/2026 (data do somatório): pena 9 anos = 3.285 dias, cumpridos 718 até 19/03/2026, 2.567 x 16% = 410 "
     "-> 03/05/2027. Pela data-base legal (01/04/2024): 3.285 x 16% = 525 -> 08/09/2025 (já vencida).",
     r, [AUD("data-base-coincide-com-a-soma-unificacao-das-pen", contem=["20/03/2026"])])

k = 3043
c1 = crime(P(k, 2021), "ART 157: Roubo", anos(10), "10/09/2021", tipo=T_ROUBO, vga="S", fp="25% - Art.112, III, da LEP",
           fl="1/3 - Comum Primário")
r = rspe(k, [c1], [prisao("10/09/2021", P(k, 2021), "PRISÃO EM FLAGRANTE")],
         [inc(REG, "Fechado - Regime Inicial", "", "10/09/2021"),
          inc(REG, "Semiaberto - Progressão de Regime", "15/09/2026", "15/09/2026")],
         ini="10/09/2021", db="15/09/2026", prog="", liv="", regime="Semiaberto - ATIVO")
r["progressao_previsao_seeu"] = F(D("15/09/2026") + timedelta(days=int((3650 - ((D("15/09/2026") - D("10/09/2021")).days)) * 0.25)))
novo(k, "Progressão", "Tema 1165/STJ: progressão ao semiaberto lançada na data da decisão (15/09/2026), não na do preenchimento dos requisitos",
     "Auditoria: alerta 'Progressão lançada na data da decisão (15/09/2026)' - a data-base da próxima progressão é a do preenchimento "
     "dos requisitos.",
     "STJ, Tema 1165 (REsp 1.972.187): a data-base para a progressão seguinte é a data em que o apenado preencheu os requisitos do art. "
     "112 da LEP, não a da decisão (que é declaratória). Pena 10 anos = 3.650 dias, 25%: 912 dias desde 10/09/2021 = 10/03/2024. O "
     "SEEU lançou a progressão com referência igual à decisão (15/09/2026).",
     r, [AUD("progressao-com-data-base-igual-a-data-da-decisao", contem=["15/09/2026"])])

k = 3044
c1 = crime(P(k, 2023), "ART 155: Furto", anos(6), "10/02/2023", sentenca="10/10/2023", transito="10/12/2023", tipo=T_FURTO_Q,
           fp="16% - Art.112, I, da LEP", fl="1/3 - Comum Primário")
r = rspe(k, [c1], [prisao("10/02/2023", P(k, 2023), "PRISÃO EM FLAGRANTE")],
         [inc(REG, "Fechado - Regime Inicial", "", "10/02/2024")],
         ini="10/02/2023", db="10/02/2024", prog=F(D("10/02/2024") + timedelta(days=int((2190 - 365) * 0.16))), liv="")
novo(k, "Progressão", "Detração: regime inicial lançado um ano depois da prisão em flagrante (a fração passa a incidir sobre a pena menos a detração)",
     "Auditoria: alerta 'Regime inicial lançado em 10/02/2024, depois da primeira prisão (10/02/2023)', diferença de cerca de 307 dias.",
     "Preso em flagrante em 10/02/2023 e sem soltura; o regime inicial foi lançado em 10/02/2024. Correto (CP, art. 42; LEP, art. "
     "112): fração sobre a pena total, contada da prisão - 2.190 x 16% = 350 dias desde 10/02/2023 = 26/01/2024. O SEEU fez "
     "(2.190 - 365) x 16% = 292 dias desde 10/02/2024 = 28/11/2024 - 307 dias mais tarde (365 x 84% = 306,6).",
     r, [AUD("regime-inicial-depois-da-primeira-prisao", contem=["10/02/2024", "10/02/2023"])])

# =====================================================================================================================
# 4. FALTA GRAVE NOS 12 MESES
# =====================================================================================================================
k = 3045
c1 = crime(P(k, 2022), "ART 157: Roubo", anos(9), "12/12/2022", tipo=T_ROUBO, vga="S", fp="25% - Art.112, III, da LEP", fl="1/3 - Comum Primário")
r = rspe(k, [c1], [prisao("10/06/2023", P(k, 2022), "PRISÃO DEFINITIVA")],
         [inc(REG, "Fechado - Regime Inicial", "", "10/06/2023"), inc("HOMOLOGAÇÃO DE FALTA GRAVE", "01/05/2026", "15/06/2026", "01/05/2026")],
         ini="10/06/2023", db="01/05/2026", prog=F(D("01/05/2026") + timedelta(days=int((3285 - 1056) * 0.25))),
         liv=F(D("10/06/2023") + timedelta(days=int(3285 / 3))))
novo(k, "Livramento", "Falta grave homologada dentro dos 12 meses: coluna Falta 'Sim' e livramento empurrado para 12 meses depois da falta",
     "Coluna Falta: 'Sim' (falta de 01/05/2026, homologada em 15/06/2026). Livramento: o SEEU imprime 09/06/2026; pela falta, só a "
     "partir de 01/05/2027 (CP, art. 83, III, b).",
     "RSPE de 05/10/2026: janela de 12 meses de 06/10/2025 a 05/10/2026; falta grave com fato em 01/05/2026, homologada - dentro "
     "(LEP, arts. 50 e 118). Livramento: pena 9 anos = 3.285 dias, 1/3 = 1.095 dias desde 10/06/2023 = 09/06/2026 (Súmula 441/STJ: a "
     "falta não interrompe esse prazo). Mas o CP, art. 83, III, b (Lei 13.964/2019), exige não ter cometido falta grave nos últimos "
     "12 meses: a falta de 01/05/2026 só deixa a janela em 01/05/2027.",
     r, [C("falta", "contem", "Sim"), C("liv", "regex", r"^0[12]/05/2027")])

k = 3046
c1 = crime(P(k, 2022), "ART 157: Roubo", anos(9), "12/12/2022", tipo=T_ROUBO, vga="S", fp="25% - Art.112, III, da LEP", fl="1/3 - Comum Primário")
r = rspe(k, [c1], [prisao("10/06/2023", P(k, 2022), "PRISÃO DEFINITIVA")],
         [inc(REG, "Fechado - Regime Inicial", "", "10/06/2023"), inc("HOMOLOGAÇÃO DE FALTA GRAVE", "20/09/2025", "15/11/2025", "20/09/2025")],
         ini="10/06/2023", db="20/09/2025", prog=F(D("20/09/2025") + timedelta(days=int((3285 - 833) * 0.25))),
         liv=F(D("10/06/2023") + timedelta(days=int(3285 / 3))))
novo(k, "Livramento", "Falta grave com fato fora dos 12 meses do RSPE (20/09/2025), mas dentro dos 12 meses anteriores à data do livramento do SEEU",
     "Coluna Falta: 'Não consta'. Livramento: o SEEU imprime 09/06/2026; pela falta de 20/09/2025, só a partir de 20/09/2026 (data "
     "já passada - livramento vencido).",
     "Janela da coluna Falta (12 meses antes do RSPE de 05/10/2026): de 06/10/2025 a 05/10/2026 - a falta de 20/09/2025 está fora. "
     "Livramento: 1/3 de 3.285 = 1.095 dias desde 10/06/2023 = 09/06/2026; nessa data a falta tinha menos de 12 meses (CP, art. 83, "
     "III, b): o livramento só cabia a partir de 20/09/2026.",
     r, [C("falta", "eq", "Não consta"), C("liv", "regex", r"^2[01]/09/2026")])

# =====================================================================================================================
# 5. LIVRAMENTO CONDICIONAL
# =====================================================================================================================
k = 3048
a = anterior(k, "ART 12: Tráfico ilícito de entorpecentes", anos(4), "10/03/2004", "10/10/2004", "20/12/2004", "20/12/2018",
             lei="6368/76 - Lei de Tóxicos", tipo="CAPUT: Importar ou exportar, ... vender ... substância entorpecente, Reclusão: 3 a 15 anos E Multa",
             ano=2004)
c1 = crime(P(k, 2022), "ART 33: Tráfico de drogas", anos(6), "05/07/2022", lei=DROGAS, tipo=T_TRAF, rc="S", re_="S",
           fp="60% - Hediondo reincidente", fl="1/1 - Hediondo reincidente")
novo(k, "Livramento", "Tráfico de 2022, reincidente específico (anterior pela Lei 6.368/76, art. 12): livramento vedado e 60% conferem",
     "Auditoria: sem alerta de fração de livramento (vedado confere) nem de progressão (60%).",
     "Anterior: tráfico (Lei 6.368/76, art. 12, equiparado a hediondo) transitado em 20/12/2004, extinto em 20/12/2018 (+5 anos = "
     "20/12/2023 > fato de 05/07/2022). Reincidente específico em tráfico: livramento vedado (Lei 11.343/06, art. 44, p. ú.; CP, art. "
     "83, V); progressão 60% (LEP, art. 112, VII, Lei 13.964/2019).", exe(k, [a, c1]),
     [AUD(LDIV, False), AUD(DIV, False), AUD("reincidencia-especifica-confere-com-o-rspe")])

k = 3049
a = anterior(k, "ART 155: Furto", 400, "10/01/2018", "10/07/2018", "20/08/2018", "20/10/2019", tipo=T_FURTO, ano=2018)
c1 = crime(P(k, 2022), "ART 302: Homicídio culposo na direção de veículo", anos(3, 6), "10/06/2022", lei="9503/97 - Código de Trânsito",
           tipo=T_CTB, rc="S", fp="20% - Art.112, II, da LEP", fl="1/2 - Comum Reincidente", regime="Semiaberto")
novo(k, "Livramento", "Crime atual culposo (homicídio no trânsito) de quem tem condenação anterior por furto: livramento 1/3, não 1/2",
     "Auditoria: item de livramento (1/2 do SEEU x 1/3 - o crime atual é culposo).",
     "CP, art. 83, II: 1/2 ao 'reincidente em crime doloso'. O crime atual (CTB, art. 302) é culposo: a fração do reincidente em "
     "crime doloso não se aplica - 1/3 (art. 83, I). Progressão: reincidente em crime sem violência, 20% (confere).", exe(k, [a, c1]),
     [AUD("livramento-reincidencia-em-crime-culposo", contem=["1/2", "1/3"]), AUD(CONF)])

k = 3050
a = anterior(k, "ART 21: Vias de fato", 45, "10/01/2019", "10/05/2019", "20/06/2019", "20/08/2019",
             lei="3688/41 - Lei das Contravenções Penais", tipo=T_VIAS, ano=2019)
c0 = crime(P(k, 2022), "ART 155: Furto", anos(2, 6), "10/03/2022", tipo=T_FURTO_Q, fp="16% - Art.112, I, da LEP", fl="1/3 - Comum Primário")
c1 = crime(P(k, 2023), "ART 21: Vias de fato", 90, "10/04/2023", lei="3688/41 - Lei das Contravenções Penais", tipo=T_VIAS, rc="S",
           fp="1/6 - Comum", fl="1/2 - Comum Reincidente", regime="Semiaberto")
novo(k, "Livramento", "Contravenção (vias de fato) com fração de livramento 1/2 no SEEU",
     "Auditoria: item de livramento da contravenção (1/2 do SEEU x 1/3).",
     "CP, art. 83, II: o 1/2 é do 'reincidente em crime doloso'; contravenção não é crime (LCP, art. 1º; Lei de Introdução ao CP, "
     "art. 1º). Para a contravenção, 1/3 (art. 83, I). O furto junto faz a pena total passar de 2 anos (CP, art. 83, caput).",
     exe(k, [a, c0, c1]), [AUD("livramento-contravencao-fracao", contem=["1/2", "1/3"])])

k = 3051
c1 = crime(P(k, 2020), "ART 157: Roubo", anos(8), "10/02/2021", tipo=T_ROUBO, vga="S", fp="25% - Art.112, III, da LEP", fl="1/3 - Comum Primário")
r = rspe(k, [c1], [prisao("10/03/2022", P(k, 2020), "PRISÃO DEFINITIVA")],
         [inc(REG, "Fechado - Regime Inicial", "", "10/03/2022"), inc("HOMOLOGAÇÃO DE FALTA GRAVE", "15/08/2024", "30/09/2024", "15/08/2024"),
          inc(REG, "Fechado - Regressão", "30/09/2024", "15/08/2024")],
         ini="10/03/2022", db="15/08/2024", prog=F(D("15/08/2024") + timedelta(days=int((2920 - 889) * 0.25))),
         liv=F(D("15/08/2024") + timedelta(days=int(2920 / 3))))
r["livramento_data_base_seeu"] = "15/08/2024"
novo(k, "Livramento", "Súmula 441/STJ: o SEEU moveu a data-base do livramento para a falta grave",
     "Auditoria: alerta 'Data-base do livramento (15/08/2024) coincide com falta grave' - a data certa é o início, 10/03/2022.",
     "Súmula 441/STJ: a falta grave não interrompe o prazo para o livramento condicional. Início do cumprimento em 10/03/2022, sem "
     "interrupção: 1/3 de 2.920 = 973 dias -> 07/11/2024 (já passada; a falta de 15/08/2024 tem mais de 12 meses - CP, art. 83, "
     "III, b, atendido desde 15/08/2025). O SEEU contou de 15/08/2024: 15/04/2027.",
     r, [AUD("data-base-do-livramento-alterada-por-falta-grave", contem=["15/08/2024"])])

k = 3052
c1 = crime(P(k, 2018), "ART 155: Furto", anos(6), "10/05/2018", tipo=T_FURTO_Q, fp="1/6 - Comum", fl="1/3 - Comum Primário")
c2 = crime(P(k, 2024), "ART 157: Roubo", anos(5, 4), "15/12/2024", sentenca="10/06/2025", transito="20/07/2025", tipo=T_ROUBO, vga="S",
           fp="25% - Art.112, III, da LEP", fl="1/3 - Comum Primário")
evs = [prisao("10/01/2021", P(k, 2018), "PRISÃO DEFINITIVA"), ev("INTERRUPÇÃO", "LIVRAMENTO CONDICIONAL", "01/02/2024"),
       prisao("10/03/2025", P(k, 2018) + ", " + P(k, 2024), "RECAPTURA/REINÍCIO DE CUMPRIMENTO")]
incs = [inc(REG, "Fechado - Regime Inicial", "", "10/01/2021"), inc("LIVRAMENTO CONDICIONAL", "01/02/2024", "25/01/2024", "01/02/2024", procs=P(k, 2018)),
        inc("REVOGAÇÃO DE LIVRAMENTO CONDICIONAL", "", "10/03/2025", "10/03/2025", procs=P(k, 2018))]
r = rspe(k, [c1, c2], evs, incs, ini="10/01/2021", db="10/03/2025", prog="20/09/2027", liv="", interrompidos=403)
novo(k, "Livramento", "Livramento revogado por crime cometido durante o período de prova (CP, art. 88)",
     "Auditoria: alerta 'Livramento revogado com crime cometido durante o período de prova (art. 88)'.",
     "Livramento de 01/02/2024, revogado em 10/03/2025; roubo com fato em 15/12/2024, dentro do período de prova. CP, art. 88: "
     "revogado o livramento por crime cometido na vigência dele, não se desconta o tempo em que esteve solto e não se concede novo "
     "livramento quanto à mesma pena (LEP, art. 142; CP, art. 86, I).",
     r, [AUD("livramento-revogado-art-88")])

k = 3053
c1 = crime(P(k, 2024), "ART 155: Furto", anos(1, 8), "10/03/2024", tipo=T_FURTO, fp="16% - Art.112, I, da LEP", fl="1/3 - Comum Primário")
r = exe(k, [c1], liv="")
novo(k, "Livramento", "Pena total de 1 ano e 8 meses: livramento não cabe (exige pena igual ou superior a 2 anos)",
     "Aba Livramento: 'Não cabível: pena < 2 anos (art. 83 CP)'.",
     "CP, art. 83, caput: o livramento só cabe à pena privativa de liberdade igual ou superior a 2 anos. Pena total 1a8m.",
     r, [C("liv_sit", "contem", "Não cabível")])

# =====================================================================================================================
# 6. SAÍDA TEMPORÁRIA (LEP, arts. 122 a 124)
# =====================================================================================================================
SEMI = "Semiaberto - ATIVO"


def st_rspe(k, crimes, ini, regime=SEMI, **kw):
    incs = [inc(REG, "Fechado - Regime Inicial", "", ini), inc(REG, "Semiaberto - Progressão de Regime", "10/03/2026", "01/03/2026")]
    return exe(k, crimes, ini=ini, db="01/03/2026", regime=regime, incs=incs, livre_janela=True, **kw)


k = 3054
c1 = crime(P(k, 2019), "ART 157: Roubo", anos(8), "10/05/2019", tipo=T_ROUBO, vga="S", fp="1/6 - Comum", fl="1/3 - Comum Primário")
novo(k, "Saída temporária", "Semiaberto, roubo de 2019, primário, 1/6 cumprido, conduta boa, unidade do semiaberto: saída temporária cabível",
     "Saída temporária: todos os requisitos atendidos (ícone cheio).",
     "LEP, art. 122 (redação anterior à Lei 14.843/2024, que rege o fato de 2019 - CF, art. 5º, XL): semiaberto; art. 123: "
     "comportamento adequado, 1/6 da pena (primário) - pena 8 anos = 2.920 dias, 1/6 = 486; preso desde 10/01/2024: cumpridos 1.000 "
     "dias; compatibilidade com os objetivos da pena. Roubo sem resultado morte (art. 122, § 2º, Lei 13.964/2019, não alcança).",
     st_rspe(k, [c1], "10/01/2024", prog="10/03/2027"), [C("st_ok", "eq", True)], ficha=ficha(k, "BOA"))

k = 3055
c1 = crime(P(k, 2024), "ART 157: Roubo", anos(6), "15/06/2024", tipo=T_ROUBO, vga="S", fp="25% - Art.112, III, da LEP", fl="1/3 - Comum Primário")
novo(k, "Saída temporária", "Semiaberto, único crime (roubo) com fato depois da Lei 14.843/2024: saída temporária vedada",
     "Saída temporária: requisito da Lei 14.843/2024 não atendido (vedada); ícone ausente.",
     "Lei 14.843/2024 (DOU 11/04/2024): a saída temporária ficou restrita a curso (art. 122, II) e é vedada ao condenado por crime "
     "hediondo ou com violência ou grave ameaça (art. 122, § 2º). Roubo de 15/06/2024: vedada.",
     st_rspe(k, [c1], "20/09/2024", prog="10/06/2027"), [C("st_ok", "eq", False), C("st_quase", "eq", False)], ficha=ficha(k, "OTIMA"))

k = 3056
c1 = crime(P(k, 2023), "ART 157: Roubo", anos(5, 4), "10/03/2023", tipo=T_ROUBO, vga="S", fp="25% - Art.112, III, da LEP", fl="1/3 - Comum Primário")
c2 = crime(P(k, 2025), "ART 157: Roubo", anos(5, 4), "05/02/2025", sentenca="05/08/2025", transito="10/09/2025", tipo=T_ROUBO, vga="S",
           fp="25% - Art.112, III, da LEP", fl="1/3 - Comum Primário")
novo(k, "Saída temporária", "Semiaberto com um roubo de antes e outro de depois da Lei 14.843/2024: requisito atendido (decisão do usuário)",
     "Saída temporária: requisito da lei atendido ('fato anterior à Lei 14.843/2024 ... a condenação posterior não impede').",
     "Escolha de política da área: com crimes de antes e depois da Lei 14.843/2024, o requisito fica atendido (a lei nova não retroage "
     "para a condenação antiga). Pena 10a8m = 3.890 dias; 1/6 = 648; preso desde 10/09/2023 - cumpridos mais de 1.100 dias.",
     st_rspe(k, [c1, c2], "10/09/2023", prog="15/07/2027"), [C("st_itens", "contem", "14.843"), C("st_ok", "eq", True)],
     ficha=ficha(k, "BOA"))

k = 3058
a = anterior(k, "ART 155: Furto", 400, "10/01/2016", "10/07/2016", "20/08/2016", "20/10/2017", tipo=T_FURTO, ano=2016)
c1 = crime(P(k, 2019), "ART 155: Furto", anos(8), "10/09/2019", tipo=T_FURTO_Q, rc="S", fp="1/6 - Comum", fl="1/2 - Comum Reincidente")
novo(k, "Saída temporária", "Reincidente no semiaberto com mais de 1/6 e menos de 1/4 da pena cumprida: falta o requisito temporal",
     "Saída temporária: '1/4 da pena cumprida (reincidente)' não atendido (cumpridos 640 dias; 1/4 = 730).",
     "LEP, art. 123, II: 1/6 da pena se primário, 1/4 se reincidente (reincidência demonstrada: furto transitado em 20/08/2016, "
     "extinto 20/10/2017). Pena 8 anos = 2.920 dias: 1/4 = 730. Preso desde 04/01/2025: até 05/10/2026, 640 dias. Atinge 1/4 em "
     "04/01/2027 - o resultado muda dentro do período de 12/10/2026 a 31/03/2027 (o caso testa justamente a fração).",
     st_rspe(k, [a, c1], "04/01/2025", prog="10/05/2027"), [C("st_ok", "eq", False), C("st_itens", "contem", "1/4")], ficha=ficha(k, "BOA"))

k = 3059
c1 = crime(P(k, 2021), "ART 121: Homicídio qualificado", anos(13), "10/03/2021", tipo=T_HQ, vga="S", morte="S",
           fp="50% - Art.112, VI, a, da LEP", fl="1/1 - Hediondo com resultado morte")
novo(k, "Saída temporária", "Semiaberto, homicídio qualificado consumado de 2021: saída temporária vedada (art. 122, § 2º, Lei 13.964/2019)",
     "Saída temporária: vedação por hediondo com resultado morte; ícone ausente.",
     "LEP, art. 122, § 2º (Lei 13.964/2019, fato desde 23/01/2020): não terá direito à saída temporária o condenado que cumpre pena "
     "por crime hediondo com resultado morte.",
     st_rspe(k, [c1], "10/03/2021", prog="10/09/2029"), [C("st_ok", "eq", False), C("st_quase", "eq", False)], ficha=ficha(k, "OTIMA"))

k = 3060
c1 = crime(P(k, 2019), "ART 155: Furto", anos(6), "10/06/2019", tipo=T_FURTO_Q, fp="1/6 - Comum", fl="1/3 - Comum Primário")
evs = [{"data": "08.09.2026", "texto": "Saída confirmada do benefício de: SAÍDA TEMPORÁRIA"},
       {"data": "15.09.2026", "texto": "Retorno confirmado do benefício de: SAÍDA TEMPORÁRIA"}]
novo(k, "Saída temporária", "Última saída temporária com retorno em 15/09/2026: menos de 45 dias até 12/10/2026",
     "Saída temporária: intervalo não atendido ('27 dias desde o retorno ... novo pedido a partir de 30/10/2026'). A partir de "
     "30/10/2026 o requisito passa a atendido (o caso testa o intervalo).",
     "LEP, art. 124, § 3º: intervalo mínimo de 45 dias entre uma saída e outra. Retorno em 15/09/2026; em 12/10/2026 são 27 dias; "
     "15/09/2026 + 45 = 30/10/2026.",
     st_rspe(k, [c1], "10/01/2024", prog="10/06/2027"), [C("st_ok", "eq", False), C("st_itens", "contem", "30/10/2026")],
     ficha=ficha(k, "BOA", eventos=evs))

k = 3062
c1 = crime(P(k, 2019), "ART 155: Furto", anos(7), "10/06/2019", tipo=T_FURTO_Q, fp="1/6 - Comum", fl="1/3 - Comum Primário")
incs = [inc(REG, "Fechado - Regime Inicial", "", "10/01/2024"), inc(REG, "Semiaberto - Progressão de Regime", "10/03/2026", "01/03/2026"),
        inc("HOMOLOGAÇÃO DE FALTA GRAVE", "01/05/2026", "20/06/2026", "01/05/2026")]
novo(k, "Saída temporária", "Falta grave homologada com fato em 01/05/2026: saída temporária não cabe até 01/05/2027",
     "Saída temporária: requisito de comportamento/falta não atendido ('falta nos últimos 12 meses: sim').",
     "LEP, art. 123, I (comportamento adequado), lido com o CP, art. 83, III, b, e a LEP, art. 112, § 7º (bom comportamento "
     "readquirido 1 ano após a falta): falta de 01/05/2026 - impede até 01/05/2027 (fora do período de 12/10/2026 a 31/03/2027).",
     exe(k, [c1], ini="10/01/2024", db="01/05/2026", regime=SEMI, incs=incs, livre_janela=True, prog="20/09/2027"),
     [C("st_ok", "eq", False), C("falta", "contem", "Sim")], ficha=ficha(k, "BOA"))

# =====================================================================================================================
# 7. PROGRESSÃO ANTECIPADA (critério da 1ª VEP de Campo Grande: até 90 dias antes)
# =====================================================================================================================
k = 3063
c1 = crime(P(k, 2023), "ART 155: Furto", anos(6), "10/05/2023", tipo=T_FURTO_Q, fp="16% - Art.112, I, da LEP", fl="1/3 - Comum Primário")
r = exe(k, [c1], ini="30/12/2025", prog="15/12/2026", livre_janela=True)
novo(k, "Progressão antecipada", "Fechado, furto sem violência, progressão em 64 dias, conduta boa: antecipação cabível",
     "Progressão antecipada: todos os requisitos atendidos (ícone cheio). O caso depende da data: passa a 'progressão vencida' "
     "depois de 15/12/2026.",
     "Critério do juízo (não é lei): antecipa em até 90 dias a progressão de quem só tem crimes sem violência ou grave ameaça, conduta "
     "boa ou ótima e não integra organização criminosa. Progressão do SEEU em 15/12/2026; em 12/10/2026 faltam 64 dias (1 a 90).",
     r, [C("pa_ok", "eq", True)], ficha=ficha(k, "BOA", unidade="ESTABELECIMENTO PENAL SIMULADO DE CAMPO GRANDE"))

k = 3064
c1 = crime(P(k, 2023), "ART 155: Furto", anos(4), "10/05/2023", tipo=T_FURTO_Q, fp="16% - Art.112, I, da LEP", fl="1/3 - Comum Primário")
c2 = crime(P(k, 2024), "ART 129: Lesão corporal (violência doméstica)", anos(2), "10/01/2024", tipo=T_LESAO, vga="S",
           fp="25% - Art.112, III, da LEP", fl="1/3 - Comum Primário")
r = exe(k, [c1, c2], ini="21/10/2025", livre_janela=True)
novo(k, "Progressão antecipada", "Progressão em 59 dias, mas com lesão corporal em violência doméstica (crime com violência): antecipação não cabe",
     "Progressão antecipada: requisito 'sem crime com violência' não atendido; ícone ausente.",
     "O critério do juízo só alcança quem não tem condenação por crime com violência ou grave ameaça; a lesão corporal (CP, art. 129, "
     "§ 9º) tem violência elementar.",
     r, [C("pa_ok", "eq", False), C("pa_quase", "eq", False)], ficha=ficha(k, "OTIMA", unidade="ESTABELECIMENTO PENAL SIMULADO DE CAMPO GRANDE"))

k = 3065
c1 = crime(P(k, 2023), "ART 155: Furto", anos(8), "10/05/2023", tipo=T_FURTO_Q, fp="16% - Art.112, I, da LEP", fl="1/3 - Comum Primário")
r = exe(k, [c1], ini="03/01/2026")
novo(k, "Progressão antecipada", "Progressão em 185 dias (15/04/2027): fora da janela de 90 dias",
     "Progressão antecipada: requisito da janela de 1 a 90 dias não atendido (só a partir de 15/01/2027).",
     "Critério do juízo: até 90 dias antes da data do SEEU. Em 12/10/2026 faltam 185 dias; a antecipação só pode ser pedida a partir "
     "de 15/01/2027 (o resultado muda dentro do período de 12/10/2026 a 31/03/2027 - o caso testa a janela).",
     r, [C("pa_ok", "eq", False)], ficha=ficha(k, "BOA", unidade="ESTABELECIMENTO PENAL SIMULADO DE CAMPO GRANDE"))


def main():
    ids = [c["id"] for c in CASOS]
    assert len(ids) == len(set(ids))
    assert all(3001 <= int(i[1:]) <= 3099 for i in ids)
    out = os.path.join(AQUI, "progressao.json")
    json.dump(CASOS, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("%d casos gravados em %s" % (len(CASOS), out))


if __name__ == "__main__":
    main()
