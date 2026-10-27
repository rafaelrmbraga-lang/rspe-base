"""Casos simulados da área "leitura": leitura do RSPE, situação da execução, data-base, término, colunas Falta e Conduta e
divergências impressas na fonte (triângulo). Faixa k 1001-1099. Gabarito calculado à mão pela lei (ver "conta" de cada caso).
Uso: python3 cobertura/gera_leitura.py  (a partir de casos_simulados) -> cobertura/leitura.json"""
import json, os, sys
from datetime import timedelta
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from base_casos import (crime, rspe, ev, prisao, interr, inc, REG, C, AUD, P, caso, D, F, GER, HOJE, anos, pena_cab, proc_crim, DROGAS)

LIM_INI, LIM_FIM = D("12/10/2026"), D("31/03/2027")   # nenhum marco deve cair aqui (salvo caso que o teste)
FURTO = dict(artigo="ART 155: Furto", tipo="§ 4º: furto qualificado, Reclusão: 2 a 8 anos E Multa", fp="16% - Art.112, I, da LEP")
ESTEL = dict(artigo="ART 171: Estelionato", tipo="CAPUT: estelionato, Reclusão: 1 a 5 anos E Multa", fp="16% - Art.112, I, da LEP")
RECEP = dict(artigo="ART 180: Receptação", tipo="CAPUT: receptação, Reclusão: 1 a 4 anos E Multa", fp="16% - Art.112, I, da LEP")
ROUBO = dict(artigo="ART 157: Roubo", tipo="§ 2º: roubo majorado, Reclusão: 4 a 10 anos E Multa", vga="S", fp="25% - Art.112, III, da LEP")
CASOS = []


def fora(*ds):
    for d in ds:
        if d and LIM_INI <= D(d) <= LIM_FIM:
            raise SystemExit("data %s cai no intervalo protegido (k=%d)" % (d, k))


def mk(k, aba, situacao, esperado, conta, r, checks, **kw):
    c = caso(k, "L-leitura", situacao, conta, r, checks, **kw)
    c.update(aba=aba, situacao=situacao, esperado=esperado)
    CASOS.append(c)
    return c


def mais(d, n):
    return F(D(d) + timedelta(days=n))


def regime_ini(ref, rg="Fechado"):
    return inc(REG, "%s - Regime Inicial" % rg, ref, ref)


def padrao(k, pena, ini, fato="10/03/2022", crime_kw=FURTO, regime="Fechado - ATIVO", eventos=None, incidentes=None, prog=None, liv=None, **kw):
    """Uma condenação (furto qualificado, primário, fração legal 16%), prisão definitiva em ini, regime inicial em ini."""
    pc = proc_crim(k, 2022)
    cr = [crime(pc, pena_dias=pena, fato=fato, **crime_kw)]
    if prog is None:
        prog = mais(ini, int(pena * 0.16))
    if liv is None:
        liv = mais(ini, pena // 3)
    evs = eventos if eventos is not None else [prisao(ini, pc, "PRISÃO DEFINITIVA")]
    incs = incidentes if incidentes is not None else [regime_ini(ini)]
    return rspe(k, cr, evs, incs, ini=ini, prog=prog, liv=liv, regime=regime, fp="16%", fl="1/3", **kw), pc


def ficha(k, conduta="BOA", cpf=None, nasc="01/01/1975", prisao_="01/01/2024", eventos=None, **kw):
    f = {"tipo": "ficha_disciplinar", "nome": "SIMULADO CASO %03d" % k, "cpf": cpf or "", "cpf_em_branco": not cpf, "data_nascimento": nasc,
         "nome_mae": "MAE SIMULADA %03d" % k, "filiacao": "MAE SIMULADA %03d" % k, "artigo": "ART 155", "data_prisao": prisao_,
         "condenacao": "CONDENADO", "unidade": "ESTABELECIMENTO PENAL SIMULADO DE CAMPO GRANDE", "data_entrada": prisao_, "sexo": "M",
         "conduta": conduta, "data_impressao": "06/10/2026", "paginas": 2, "paginas_sem_texto": [],
         "autos": ["%07d-00.2026.8.12.0001" % (9900000 + k)],
         "eventos": eventos if eventos is not None else [{"data": prisao_.replace("/", "."), "texto": "Entrada na Unidade Penal: ESTABELECIMENTO PENAL SIMULADO DE CAMPO GRANDE, Procedente: DEPAC."}],
         "historico_oculto": []}
    f.update(kw)
    return f


def cpf_valido(base9):
    d = [int(x) for x in base9]
    for n in (10, 11):
        s = sum(a * b for a, b in zip(d, range(n, 1, -1)))
        r = s * 10 % 11
        d.append(0 if r == 10 else r)
    return "".join(map(str, d))


def sem_data(campo):
    return C(campo, "regex", r"^[^0-9]*$", "sem data")


# =============================== 1. Situação da execução ===============================
# 1001 - não iniciou: só prisão em flagrante encerrada antes do trânsito
k = 1001
pc = proc_crim(k, 2023)
cr = [crime(pc, pena_dias=anos(2), fato="10/01/2023", sentenca="15/09/2023", transito="20/02/2024", regime="Aberto", **ESTEL)]
r = rspe(k, cr, [prisao("10/01/2023", pc), interr("13/01/2023", "LIBERDADE PROVISÓRIA", pc)], [], regime="Aberto", term="",
         pena_cumprida="0a0m4d", pena_remanescente="1a11m26d", data_base_seeu="", livramento_data_base_seeu="")
mk(k, "Geral", "Só prisão em flagrante (10 a 13/01/2023), solto antes do trânsito (20/02/2024), sem nova prisão: não iniciou o cumprimento",
   "Situação 'Não iniciou o cumprimento'; término 'Não iniciou'; sem data-base; os 4 dias do flagrante são detração.",
   "LEP, art. 105: a execução começa com o trânsito e o recolhimento (guia). Flagrante 10/01 a 13/01/2023 = 4 dias (dia do começo e da "
   "soltura contam, CP, art. 10), encerrado antes do trânsito: é detração (CP, art. 42), não início do cumprimento. Nenhuma prisão depois.",
   r, [C("prog_sit_full", "contem", "Não iniciou"), C("termino_motivo", "contem", "Não iniciou"), sem_data("termino"), sem_data("db"),
       C("cumprimento", "nao_contem", "INTERROMPIDA", "quem nunca começou a cumprir não teve a pena interrompida (LEP, art. 105)")])

# 1002 - sem início no SEEU: crimes, pena total 0, nenhum evento nem incidente
k = 1002
pa, pb = proc_crim(k, 2023), "%07d-00.2024.8.12.0001" % (8800000 + k + 50)
cr = [crime(pa, pena_dias=anos(1, 4), fato="05/04/2023", **ESTEL), crime(pb, pena_dias=anos(1, 2, 20), fato="11/11/2023", **RECEP)]
r = rspe(k, cr, [], [], pena=0, regime="", term="", db="")
r.update(pena_total="0a0m0d", pena_cumprida="0a0m0d", pena_remanescente="0a0m0d", data_base_seeu="", livramento_data_base_seeu="")
mk(k, "Auditoria", "Guia com duas condenações e nenhum evento nem incidente no SEEU (pena total 0a0m0d): cumprimento não iniciado no SEEU",
   "Situação 'SEM INÍCIO DE CUMPRIMENTO NO SEEU'; Auditoria 'verificar' com a soma das penas = 2 anos, 6 meses e 20 dias; sem 'Faltam dados' de regime e término.",
   "Soma por componente (convenção do SEEU, LEP, art. 111): 1a4m0d + 1a2m20d = 2a6m20d. Sem evento de prisão o SEEU não calcula: não é dado faltando (LEP, arts. 105 e 106).",
   r, [C("cumprimento", "contem", "SEM INÍCIO"), AUD("pena-nao-iniciada-seeu", contem="Soma das penas"),
       AUD("pena-nao-iniciada-seeu", contem=["2 anos", "6 meses", "20 dias"]),
       AUD("faltam-dados-regime_atual", presente=False), AUD("faltam-dados-termino_previsao_seeu", presente=False)])

# 1003 - em cumprimento, fechado: dados do SEEU
k = 1003
ini = "15/03/2024"
r, pc = padrao(k, anos(7), ini)
T = r["termino_previsao_seeu"]; fora(T, r["progressao_previsao_seeu"], r["livramento_previsao_seeu"])
mk(k, "Geral", "Preso desde 15/03/2024 em regime fechado, sem interrupção: em cumprimento com os dados impressos pelo SEEU",
   "Situação 'EM CUMPRIMENTO'; regime Fechado; término %s (do SEEU); data-base 15/03/2024 (do SEEU); conduta 'Sem ficha'; falta 'Não consta'." % T,
   "Término do SEEU = 15/03/2024 + 2.555 dias - 1 (dia do começo conta, CP, art. 10) = %s; data-base impressa = prisão definitiva (LEP, art. 112)." % T,
   r, [C("cumprimento", "contem", "EM CUMPRIMENTO"), C("regime", "contem", "Fechado"), C("termino", "eq", T), C("db", "eq", ini),
       C("conduta", "eq", "Sem ficha"), C("falta", "contem", "Não consta")])

# 1004 - semiaberto
k = 1004
ini = "02/02/2023"
incs = [regime_ini(ini), inc(REG, "Semiaberto - Progressão", "28/05/2025", "20/05/2025")]
r, pc = padrao(k, anos(8), ini, regime="Semiaberto - ATIVO", incidentes=incs, db="20/05/2025",
               prog=mais("20/05/2025", int((anos(8) - ((D("20/05/2025") - D(ini)).days)) * 0.16)))
fora(r["termino_previsao_seeu"], r["progressao_previsao_seeu"], r["livramento_previsao_seeu"])
mk(k, "Geral", "Progrediu ao semiaberto (ref. 20/05/2025): regime atual semiaberto, em cumprimento",
   "Regime 'Semiaberto'; situação 'EM CUMPRIMENTO'; data-base 20/05/2025 (do SEEU).",
   "Progressão concedida com referência 20/05/2025 é a nova data-base (LEP, art. 112); o SEEU a imprime.",
   r, [C("regime", "contem", "Semiaberto"), C("cumprimento", "contem", "EM CUMPRIMENTO"), C("db", "eq", "20/05/2025")])

# 1005 - regime aberto
k = 1005
ini = "10/08/2022"
incs = [regime_ini(ini, "Semiaberto"), inc(REG, "Aberto - Progressão", "17/02/2026", "10/02/2026")]
liv = mais(ini, anos(9) // 3)
r, pc = padrao(k, anos(9), ini, regime="Aberto - ATIVO", incidentes=incs, db="10/02/2026", prog="", liv=liv, progressao_obs_seeu="Regime aberto desde 10/02/2026")
fora(r["termino_previsao_seeu"], liv)
mk(k, "Progressão", "No regime aberto desde 10/02/2026: progressão sem objeto, livramento continua",
   "Progressão: 'Já em regime aberto (10/02/2026)', sem data; livramento segue com a data do SEEU %s." % liv,
   "Do aberto não há regime a progredir (LEP, art. 112); o livramento condicional cabe também a quem está no aberto (CP, art. 83). Lapso de "
   "1/3 de 9 anos = 1.095 dias desde 10/08/2022 -> %s." % liv,
   r, [C("prog_sit_full", "contem", "aberto"), C("motivo_exec", "contem", "10/02/2026"), sem_data("prog"), C("liv", "eq", liv), C("regime", "contem", "Aberto")])

# 1006 - foragido: fuga sem recaptura, regime e término não impressos
k = 1006
ini, fuga = "04/07/2023", "20/05/2026"
out = (GER - D(fuga)).days
r, pc = padrao(k, anos(6), ini, regime="", eventos=[prisao(ini, proc_crim(k, 2022), "PRISÃO DEFINITIVA"), interr(fuga, "FUGA")],
               interrompidos=out, term="", prog="", liv="")
mk(k, "Geral", "Fuga em 20/05/2026 sem recaptura; o SEEU não imprime regime nem término",
   "Situação 'PENA INTERROMPIDA'; término sem data; Auditoria 'info' de pena interrompida (não é falha de leitura), sem 'Faltam dados' de "
   "regime e término; coluna Falta 'A apurar' (fuga só como evento, sem sanção reconhecida).",
   "Foragido não cumpre pena (LEP, art. 111; CP, art. 42 só conta a custódia). A fuga é falta grave em tese (LEP, art. 50, II), mas só "
   "conta como 'Sim' depois de reconhecida em juízo (LEP, art. 118, § 2º; STJ, Tema 1195): até lá, 'A apurar'.",
   r, [C("cumprimento", "contem", "INTERROMPIDA"), sem_data("termino"), AUD("pena-interrompida-seeu"),
       AUD("faltam-dados-regime_atual", presente=False), AUD("faltam-dados-termino_previsao_seeu", presente=False), C("falta", "contem", "apurar")])

# 1007 - fuga e recaptura
k = 1007
ini, fuga, rec = "12/12/2022", "10/04/2026", "25/06/2026"
out = (D(rec) - D(fuga)).days - 1
pc = proc_crim(k, 2022)
r, _ = padrao(k, anos(7), ini, eventos=[prisao(ini, pc, "PRISÃO DEFINITIVA"), interr(fuga, "FUGA"), prisao(rec, pc, "RECAPTURA")],
              interrompidos=out, prog=mais(ini, int(anos(7) * 0.16) + out), liv=mais(ini, anos(7) // 3 + out))
fora(r["termino_previsao_seeu"], r["progressao_previsao_seeu"], r["livramento_previsao_seeu"])
mk(k, "Geral", "Fuga em 10/04/2026 e recaptura em 25/06/2026, sem falta homologada",
   "Situação 'EM CUMPRIMENTO'; término do SEEU %s (acrescido dos %d dias fora); data-base do SEEU 12/12/2022 mantida; Falta 'A apurar' "
   "com o período da fuga até a recaptura." % (r["termino_previsao_seeu"], out),
   "Dias fora: 11/04 a 24/06/2026 = %d (os dias da fuga e da recaptura contam como custódia). Sem falta reconhecida não se move a data-base "
   "(Súmula 534/STJ exige a falta grave). Fuga é falta permanente (STJ, HC 527.625), na janela de 12 meses do RSPE (05/10/2026)." % out,
   r, [C("cumprimento", "contem", "EM CUMPRIMENTO"), C("termino", "eq", r["termino_previsao_seeu"]), C("db", "eq", ini),
       C("falta", "contem", "apurar"), C("faltas_itens", "contem", "10/04/2026 a 25/06/2026")])

# 1008 - em livramento condicional
k = 1008
ini, lc = "06/06/2023", "02/03/2026"
pc = proc_crim(k, 2022)
incs = [regime_ini(ini), inc("LIVRAMENTO CONDICIONAL", lc, "25/02/2026", lc)]
r, _ = padrao(k, anos(6), ini, eventos=[prisao(ini, pc, "PRISÃO DEFINITIVA"), interr(lc, "LIVRAMENTO CONDICIONAL")], incidentes=incs,
              prog="", liv="", livramento_obs_seeu="Em livramento condicional deferido em 25/02/2026")
fora(r["termino_previsao_seeu"])
mk(k, "Livramento", "Em livramento condicional desde 02/03/2026 (interrupção 'livramento condicional' no SEEU)",
   "Situação 'EM CUMPRIMENTO (livramento condicional desde 02/03/2026)'; progressão e livramento com o rótulo 'Em livramento condicional'; "
   "término do SEEU %s." % r["termino_previsao_seeu"],
   "O período de prova é cumprimento da pena (CP, arts. 82 e 90; LEP, art. 146): a interrupção lançada para o livramento não é saída da execução.",
   r, [C("cumprimento", "contem", ["EM CUMPRIMENTO", "livramento"]), C("prog_sit_full", "contem", "livramento"), C("liv_sit_full", "contem", "livramento"),
       C("cumprimento", "contem", "02/03/2026", "o período de prova começa na audiência/soltura (LEP, art. 137), 02/03/2026, não na decisão de 25/02/2026"),
       C("termino", "eq", r["termino_previsao_seeu"])])

# 1009 - prisão domiciliar como início do cumprimento
k = 1009
ini = "21/09/2024"
pc = proc_crim(k, 2022)
r, _ = padrao(k, anos(5), ini, regime="Aberto - ATIVO", eventos=[prisao(ini, pc, "PRISÃO DOMICILIAR")], incidentes=[regime_ini(ini, "Aberto")])
fora(r["termino_previsao_seeu"], r["livramento_previsao_seeu"])
mk(k, "Geral", "Início do cumprimento em prisão domiciliar (21/09/2024), regime aberto",
   "Situação 'EM CUMPRIMENTO'; término do SEEU %s." % r["termino_previsao_seeu"],
   "Prisão domiciliar é modalidade de cumprimento (LEP, art. 117): conta como pena cumprida.",
   r, [C("cumprimento", "contem", "EM CUMPRIMENTO"), C("termino", "eq", r["termino_previsao_seeu"])])

# 1010 - monitoramento eletrônico lançado como interrupção
k = 1010
ini, mon = "08/02/2024", "01/04/2026"
pc = proc_crim(k, 2022)
incs = [regime_ini(ini), inc(REG, "Semiaberto - Progressão", "05/09/2025", "29/08/2025")]
out = (GER - D(mon)).days
r, _ = padrao(k, anos(6), ini, regime="Semiaberto - ATIVO", incidentes=incs, db="29/08/2025", interrompidos=out, term="", prog="", liv="",
              eventos=[prisao(ini, pc, "PRISÃO DEFINITIVA"), interr(mon, "PRISÃO DOMICILIAR COM MONITORAMENTO ELETRÔNICO")])
mk(k, "Auditoria", "Semiaberto harmonizado: 'prisão domiciliar com monitoramento eletrônico' lançada como INTERRUPÇÃO em 01/04/2026 (o SEEU parou de contar)",
   "Auditoria aponta que o período em domiciliar monitorada (desde 01/04/2026, %d dias até o RSPE) é cumprimento de pena e deve ser contado; "
   "a tela pode manter os números do SEEU com ressalva, mas a situação não é saída da execução." % out,
   "Domiciliar com monitoramento no lugar do regime sem vaga é cumprimento de pena (STF, SV 56 e RE 641.320; LEP, arts. 117 e 146-B). "
   "Interromper a contagem prejudica o assistido (progressão, livramento e término adiados). Política: a aba mantém a data do SEEU com ressalva; "
   "a Auditoria alerta.",
   r, [C("aud_itens", "regex", r'"nivel": "(alerta|verificar)"[^}]*monitor',
         "Programa: só 'info' (pena interrompida, pedir reinício). Pela SV 56/RE 641.320 e pela política, a Auditoria deve alertar que o "
         "período monitorado é cumprimento e o SEEU parou de contar."),
       dict(C("cumprimento", "nao_contem", "INTERROMPIDA (sem evento"), decisao=True,
            nota="Tese: pela SV 56 a execução segue; a política manda manter o dado do SEEU com ressalva - conferir se o rótulo traz a ressalva")])

# 1011 - incompatibilidade de regime contada pelo SEEU
k = 1011
ini, inc_ = "17/01/2025", "03/02/2026"
pc = proc_crim(k, 2022)
incs = [regime_ini(ini, "Semiaberto")]
r, _ = padrao(k, anos(5), ini, regime="Semiaberto - ATIVO", incidentes=incs,
              eventos=[prisao(ini, pc, "PRISÃO DEFINITIVA"), interr(inc_, "INCOMPATIBILIDADE DE REGIME - AGUARDANDO VAGA")])
fora(r["termino_previsao_seeu"], r["progressao_previsao_seeu"], r["livramento_previsao_seeu"])
mk(k, "Geral", "Interrupção 'incompatibilidade de regime - aguardando vaga' (03/02/2026) com a pena cumprida do SEEU contando o período",
   "Situação 'EM CUMPRIMENTO'; término do SEEU %s; custódia contínua desde 17/01/2025." % r["termino_previsao_seeu"],
   "SV 56/STF: aguardar vaga fora do regime adequado não suspende o cumprimento; o SEEU contou (pena cumprida = 17/01/2025 a 05/10/2026).",
   r, [C("cumprimento", "contem", "EM CUMPRIMENTO"), C("termino", "eq", r["termino_previsao_seeu"])])

# 1012 - incompatibilidade que o SEEU não contou
k = 1012
ini = "03/03/2026"
pc = proc_crim(k, 2022)
r, _ = padrao(k, anos(4), ini, regime="Semiaberto - ATIVO", incidentes=[regime_ini(ini, "Semiaberto")], term="", prog="", liv="",
              eventos=[prisao(ini, pc, "PRISÃO DEFINITIVA"), interr(ini, "INCOMPATIBILIDADE DE REGIME - AGUARDANDO VAGA")],
              interrompidos=(GER - D(ini)).days)
mk(k, "Auditoria", "Prisão e 'incompatibilidade de regime - aguardando vaga' no mesmo dia (03/03/2026); o SEEU contou só 1 dia de pena",
   "A Auditoria deve apontar que o SEEU não conta o período de espera de vaga (03/03 a 05/10/2026 = 217 dias) como cumprimento; "
   "situação em cumprimento (SV 56).",
   "SV 56 e RE 641.320/STF: sem vaga no semiaberto, a pessoa vai à domiciliar/monitoramento e a pena corre. 03/03 a 05/10/2026, dias "
   "inclusivos = 217 dias; o SEEU registra 1 dia. Tratar a pessoa como 'solta sem cumprimento' prejudica o assistido.",
   r, [C("aud_itens", "regex", r'"nivel": "(alerta|verificar)"[^}]*incompatibilidade',
         "Programa: só 'info' (pena interrompida, pedir reinício) e situação 'pena interrompida'. Pela SV 56 a espera de vaga é cumprimento: "
         "a Auditoria deve alertar que o SEEU não contou 217 dias."),
       dict(C("cumprimento", "contem", "EM CUMPRIMENTO"), decisao=True,
            nota="Tese: o programa conclui, pela pena cumprida do SEEU, que a pessoa foi solta; pela SV 56 a pena corre")])

# 1013 - pena suspensa: preso em outro processo
k = 1013
ini, op = "09/09/2023", "14/07/2026"
pc = proc_crim(k, 2022)
r, _ = padrao(k, anos(5), ini, regime="", term="", prog="", liv="", interrompidos=(GER - D(op)).days,
              eventos=[prisao(ini, pc, "PRISÃO DEFINITIVA"), interr(op, "INTERRUPÇÃO POR PRISÃO EM OUTRO PROCESSO")])
mk(k, "Geral", "Interrupção por prisão em outro processo (14/07/2026), sem reinício",
   "Situação 'PENA SUSPENSA (preso em outro processo desde 14/07/2026)', não fuga; progressão e livramento sem data, rótulo de suspensa; Falta 'Não consta'.",
   "A pena desta execução fica suspensa enquanto a pessoa cumpre a outra (LEP, art. 111: depende da soma/unificação). Não é fuga nem liberdade.",
   r, [C("cumprimento", "contem", ["SUSPENSA", "14/07/2026"]), C("prog_sit_full", "contem", "uspens"), C("falta", "contem", "Não consta")])

# 1014 - interrupção por transferência para outra comarca
k = 1014
ini, tr = "11/11/2023", "16/06/2026"
pc = proc_crim(k, 2022)
r, _ = padrao(k, anos(6), ini, regime="Fechado - ATIVO", term="", prog="", liv="", interrompidos=(GER - D(tr)).days,
              eventos=[prisao(ini, pc, "PRISÃO DEFINITIVA"), interr(tr, "TRANSFERÊNCIA PARA OUTRA COMARCA")])
mk(k, "Geral", "Último evento: interrupção por transferência para outra comarca (16/06/2026)",
   "Situação 'EM CUMPRIMENTO (execução seguiu desde 16/06/2026: ... - conferir)', não pena interrompida nem fuga.",
   "A transferência muda o juízo, não interrompe a pena (LEP, art. 66; a execução segue em outra comarca).",
   r, [C("cumprimento", "contem", ["EM CUMPRIMENTO", "16/06/2026", "conferir"])])

# 1015 - pena cumprida, execução ainda ativa
k = 1015
ini = "21/08/2023"
r, pc = padrao(k, anos(3), ini, prog="", liv="")
T = r["termino_previsao_seeu"]
mk(k, "Extinção", "Término do SEEU (%s) já passou e a execução segue ativa, sem extinção" % T,
   "Progressão e livramento com o rótulo 'Pena cumprida em %s'; pede-se a extinção (data passada, estável)." % T,
   "3 anos = 1.095 dias desde 21/08/2023 (dia do começo conta): último dia %s. Cumprida a pena, extingue-se (LEP, art. 66, II; CP, art. 82 c/c art. 90 por analogia)." % T,
   r, [C("motivo_exec", "contem", ["cumprida", T]), C("prog_sit", "contem", "cumprida"), C("liv_sit", "contem", "cumprida")])

# 1016 - execução extinta
k = 1016
ini = "14/02/2022"
pc = proc_crim(k, 2021)
cr = [crime(pc, pena_dias=anos(4), fato="03/05/2021", extinto="Sim", **FURTO)]
r = rspe(k, cr, [prisao(ini, pc, "PRISÃO DEFINITIVA"), interr("13/02/2026", "CUMPRIMENTO DA PENA")],
         [regime_ini(ini), inc("EXTINÇÃO", "CUMPRIMENTO DA PENA", "20/03/2026", "13/02/2026", procs=pc)], ini=ini, regime="Fechado - ATIVO",
         status="ARQUIVADO")
mk(k, "Geral", "Extinção por cumprimento concedida (13/02/2026), crime 'Extinto: Sim'",
   "Situação 'EXTINTA'; sem 'Faltam dados'; progressão e livramento sem data.",
   "Extinção da pena pelo cumprimento (LEP, art. 66, II): nada a calcular.",
   r, [C("cumprimento", "contem", "EXTINTA"), AUD("faltam-dados-termino_previsao_seeu", presente=False), sem_data("prog")])

# 1017 - arquivada com pena por cumprir
k = 1017
ini = "05/05/2024"
r, pc = padrao(k, anos(6), ini, status="ARQUIVADO")
mk(k, "Auditoria", "Execução 'ARQUIVADO' no SEEU com pena remanescente e sem extinção",
   "Situação 'ARQUIVADA'; Auditoria 'verificar': execução arquivada com pena por cumprir.",
   "Arquivamento sem extinção não encerra a pena (LEP, art. 66, II): pena remanescente de cerca de 3 anos e 5 meses.",
   r, [C("cumprimento", "contem", "ARQUIVADA"), AUD("execucao-arquivada-com-pena", nivel="verificar")])

# 1018 - guia sem cálculo, com detração anterior
k = 1018
pc = proc_crim(k, 2025)
cr = [crime(pc, pena_dias=anos(3), fato="20/01/2025", sentenca="10/10/2025", transito="15/12/2025", **RECEP)]
evs = [prisao("01/02/2025", pc), interr("30/03/2025", "LIBERDADE PROVISÓRIA", pc), prisao("10/03/2026", pc, "PRISÃO DEFINITIVA")]
r = rspe(k, cr, evs, [], pena=0, regime="Fechado - ATIVO", term="", db="")
r.update(pena_total="0a0m0d", pena_cumprida="0a0m0d", pena_remanescente="0a0m0d", data_base_seeu="", livramento_data_base_seeu="")
mk(k, "Geral", "Guia sem cálculo (pena total 0a0m0d), receptação de 3 anos, flagrante de 58 dias e prisão definitiva em 10/03/2026",
   "Término calculado '10/01/2029*'; Auditoria alerta guia sem pena calculada.",
   "Detração: 01/02 a 30/03/2025 = 28 + 30 = 58 dias (CP, art. 42). 3 anos pelo calendário desde 10/03/2026 terminam em 09/03/2029 "
   "(CP, art. 10); menos 58 dias = 10/01/2029.",
   r, [C("termino", "contem", "10/01/2029"), C("termino", "contem", "*"), AUD("guia-sem-pena-calculada-pena-total-com")])

# =============================== 2. Ordem dos eventos do mesmo dia ===============================
# 1019 - solto na véspera: liberdade provisória impressa antes do flagrante no mesmo dia
k = 1019
pc = proc_crim(k, 2023)
cr = [crime(pc, pena_dias=anos(1, 8), fato="03/02/2023", sentenca="10/08/2023", transito="30/10/2023", regime="Aberto", **RECEP)]
r = rspe(k, cr, [interr("03/02/2023", "LIBERDADE PROVISÓRIA", pc), prisao("03/02/2023", pc)], [], regime="Aberto", term="",
         pena_cumprida="0a0m1d", pena_remanescente="1a7m29d", data_base_seeu="", livramento_data_base_seeu="")
mk(k, "Geral", "Flagrante e liberdade provisória no mesmo dia (03/02/2023), o PDF imprime a soltura antes da prisão",
   "Um dia de custódia (detração); 'Não iniciou o cumprimento'; término 'Não iniciou' - não 'em cumprimento desde 03/02/2023'.",
   "Quem estava solto na véspera é preso e solto no mesmo dia: 1 dia de detração (CP, art. 42). Sem nova prisão, a execução não começou (LEP, art. 105).",
   r, [C("prog_sit_full", "contem", "Não iniciou"), C("termino_motivo", "contem", "Não iniciou"), sem_data("termino")])

# 1020 - preso na véspera: recaptura impressa antes da interrupção no mesmo dia
k = 1020
ini, dia = "19/12/2022", "07/05/2026"
pc = proc_crim(k, 2022)
r, _ = padrao(k, anos(7), ini, eventos=[prisao(ini, pc, "PRISÃO DEFINITIVA"), prisao(dia, pc, "RECAPTURA"), interr(dia, "DESCUMPRIMENTO DE CONDIÇÕES")])
fora(r["termino_previsao_seeu"], r["progressao_previsao_seeu"], r["livramento_previsao_seeu"])
mk(k, "Geral", "Preso desde 2022; no mesmo dia (07/05/2026) o PDF imprime 'recaptura' antes de 'interrupção - descumprimento'",
   "Situação 'EM CUMPRIMENTO' (custódia contínua; interrupção e reinício no mesmo dia); término do SEEU %s." % r["termino_previsao_seeu"],
   "Preso na véspera: a interrupção vem antes da recaptura; a custódia não se rompe (o dia conta uma vez, CP, art. 10).",
   r, [C("cumprimento", "contem", "EM CUMPRIMENTO"), C("termino", "eq", r["termino_previsao_seeu"])])

# =============================== 3. Data-base ===============================
# 1021 - data-base calculada (SEEU não imprime): somatório, regressão cautelar e progressão negada não movem
k = 1021
ini = "10/12/2021"
incs = [regime_ini(ini), inc(REG, "Semiaberto - Progressão", "22/03/2024", "15/03/2024"),
        inc(REG, "Fechado - Regressão Cautelar", "20/11/2025", "20/11/2025"), inc(REG, "Fechado - Somatório", "10/01/2026", "10/01/2026"),
        inc(REG, "Aberto - Progressão", "30/06/2026", "25/06/2026", sit="NÃO CONCEDIDO")]
r, pc = padrao(k, anos(10), ini, fato="10/06/2021", incidentes=incs, regime="Fechado - ATIVO", prog="", db="")
r["data_base_seeu"] = ""
fora(r["termino_previsao_seeu"], r["livramento_previsao_seeu"])
mk(k, "Progressão", "SEEU sem data-base impressa; incidentes: progressão (ref. 15/03/2024), regressão cautelar, somatório e progressão negada",
   "Data-base 15/03/2024 (calculada, última alteração de regime válida).",
   "Regressão cautelar não é definitiva (LEP, art. 118, § 2º); a soma de nova condenação não altera a data-base (STJ, Tema 1006); "
   "pedido negado não produz efeito. Fica a progressão ao semiaberto, ref. 15/03/2024 (LEP, art. 112).",
   r, [C("db", "contem", "15/03/2024")])

# 1022 - data-base informada pelo operador
k = 1022
ini = "10/06/2024"
pena = anos(6)
incs = [regime_ini("10/06/2025")]
r, pc = padrao(k, pena, ini, incidentes=incs, db="10/06/2025", prog=mais("10/06/2025", int((pena - 365) * 0.16)))
proc = r["processo_execucao"]
mk(k, "Progressão", "Guia única, preso desde 10/06/2024, mas o SEEU lançou o regime inicial (e a data-base) em 10/06/2025; o operador informa 10/06/2024",
   "Data-base exibida 10/06/2024 (informada); progressão refeita para 26/05/2025* (já vencida).",
   "Data-base = início da custódia (LEP, art. 112; CP, art. 42). Lapso 16%% de 6 anos: 0,16 x 2.190 = 350,4 -> 350 dias. "
   "10/06/2024 + 350 dias = 26/05/2025. (SEEU: 10/06/2025 + 16%% de 1.825 = 292 dias = %s.)" % r["progressao_previsao_seeu"],
   r, [C("db", "contem", "10/06/2024"), C("prog", "contem", "26/05/2025")],
   acoes=[{"metodo": "dado_manual", "args": [proc, "data_base", "10/06/2024|preso desde 10/06/2024 pela mesma guia"]}])

# 1023 - data-base do SEEU na data do somatório
k = 1023
ini = "18/04/2022"
pa = proc_crim(k, 2021)
pb = "%07d-00.2025.8.12.0001" % (8800000 + k + 50)
cr = [crime(pa, pena_dias=anos(5), fato="02/02/2021", **FURTO), crime(pb, pena_dias=anos(2), fato="15/01/2022", **ESTEL)]
incs = [regime_ini(ini), inc(REG, "Semiaberto - Progressão", "16/09/2024", "10/09/2024"), inc(REG, "Semiaberto - Somatório", "20/02/2026", "20/02/2026")]
r = rspe(k, cr, [prisao(ini, pa, "PRISÃO DEFINITIVA")], incs, ini=ini, db="20/02/2026", regime="Semiaberto - ATIVO", fp="16%", fl="1/3",
         prog=mais("20/02/2026", 450), liv=mais(ini, anos(7) // 3))
fora(r["termino_previsao_seeu"], r["progressao_previsao_seeu"], r["livramento_previsao_seeu"])
mk(k, "Progressão", "Data-base do SEEU (20/02/2026) igual à data do somatório; a última progressão foi em 10/09/2024",
   "A aba mantém a data-base do SEEU com cor/ressalva; a Auditoria alerta que a soma não altera a data-base (STJ, Tema 1006) e estima pela data legal (10/09/2024).",
   "Fato da nova condenação (15/01/2022) anterior ao início da execução: a soma não interrompe a contagem (STJ, Tema 1006). Data-base legal: 10/09/2024.",
   r, [C("db", "contem", "20/02/2026"), C("db_cor", "nao_vazio"), AUD("data-base-coincide-com-a-soma-unificacao-das-pen")])

# 1024 - data-base pela falta grave (Súmula 534): data do fato, não da decisão
k = 1024
ini = "05/04/2022"
incs = [regime_ini(ini), inc(REG, "Semiaberto - Progressão", "15/03/2024", "10/03/2024"),
        inc("HOMOLOGAÇÃO DE FALTA GRAVE", "18/04/2026", "05/06/2026", "18/04/2026"), inc(REG, "Fechado - Regressão", "05/06/2026", "05/06/2026")]
r, pc = padrao(k, anos(9), ini, fato="01/09/2021", incidentes=incs, prog="", db="")
r["data_base_seeu"] = ""
fora(r["termino_previsao_seeu"], r["livramento_previsao_seeu"])
mk(k, "Progressão", "Falta grave com fato em 18/04/2026 homologada em 05/06/2026 e regressão com referência na decisão; SEEU sem data-base impressa",
   "Data-base 18/04/2026 (data da falta, não da decisão); coluna Falta 'Sim'.",
   "Súmula 534/STJ: a falta grave reinicia a contagem a partir do cometimento (18/04/2026). Fato dentro dos 12 meses do RSPE e falta "
   "reconhecida em juízo -> 'Sim' (CP, art. 83, III, b; LEP, art. 118).",
   r, [C("db", "contem", "18/04/2026"), C("falta", "contem", "Sim")])

# 1025 - recaptura sem falta homologada: data-base fica na última alteração de regime
k = 1025
ini, fuga, rec = "01/09/2023", "01/02/2026", "01/04/2026"
pc = proc_crim(k, 2022)
out = (D(rec) - D(fuga)).days - 1
r, _ = padrao(k, anos(8), ini, eventos=[prisao(ini, pc, "PRISÃO DEFINITIVA"), interr(fuga, "EVASÃO"), prisao(rec, pc, "RECAPTURA")],
              interrompidos=out, prog="", db="", liv=mais(ini, anos(8) // 3 + out))
r["data_base_seeu"] = ""
fora(r["termino_previsao_seeu"], r["livramento_previsao_seeu"])
mk(k, "Progressão", "Evasão (01/02/2026) e recaptura (01/04/2026) sem falta homologada; SEEU sem data-base impressa",
   "Data-base 01/09/2023 (regime inicial), não a recaptura; Falta 'A apurar'.",
   "Sem falta grave reconhecida em juízo, a data-base não se altera (Súmula 534/STJ pressupõe a falta; LEP, art. 118, § 2º: oitiva prévia). "
   "Os 58 dias fora (02/02 a 31/03/2026) só acrescem ao prazo.",
   r, [C("db", "contem", "01/09/2023"), C("falta", "contem", "apurar")])

# =============================== 4. Término ===============================
# 1026 - término calculado pelo remanescente (SEEU não imprimiu)
k = 1026
ini = "22/07/2024"
r, pc = padrao(k, anos(5, 4, 10), ini, term="")
mk(k, "Geral", "Em cumprimento, o SEEU não imprimiu o término; pena remanescente %s" % r["pena_remanescente"],
   "Término calculado (com '*') = geração 05/10/2026 + remanescente, pelo calendário; Auditoria 'Faltam dados: término'.",
   "Remanescente começa em 06/10/2026 (a cumprida do SEEU vai até a geração, inclusive): ver a data na verificação. CP, art. 10; LEP, art. 66.",
   r, [AUD("faltam-dados-termino_previsao_seeu"), C("termino", "contem", "*")])
# conta à mão: o remanescente impresso começa a correr em 06/10/2026; soma anos e meses pelo calendário, depois os dias, menos 1
import re as _re
_ra, _rm, _rd = map(int, _re.match(r"(\d+)a(\d+)m(\d+)d", r["pena_remanescente"]).groups())
_d0 = D("06/10/2026")
_y, _mo = _d0.year + _ra, _d0.month + _rm
_y += (_mo - 1) // 12; _mo = (_mo - 1) % 12 + 1
_T = F(_d0.replace(year=_y, month=_mo) + timedelta(days=_rd - 1))
fora(_T)
CASOS[-1]["checks"].append(C("termino", "contem", _T))
CASOS[-1]["esperado"] += " Término esperado %s*." % _T
CASOS[-1]["conta"] += " Remanescente impresso %s: 06/10/2026 + %d ano(s) e %d mês(es) pelo calendário + %d dia(s) - 1 = %s." % (r["pena_remanescente"], _ra, _rm, _rd, _T)

# 1027 - término informado pelo operador
k = 1027
ini = "13/06/2025"
r, pc = padrao(k, anos(6), ini, term="")
fora(r["progressao_previsao_seeu"], r["livramento_previsao_seeu"])
proc = r["processo_execucao"]
mk(k, "Auditoria", "Término não impresso e informado pelo operador (12/06/2031)",
   "Término 12/06/2031 passa a valer; o alerta 'Faltam dados: término' fica baixado como dado informado.",
   "Pena de 6 anos desde 13/06/2025, pelo calendário (CP, art. 10): último dia 12/06/2031, que o operador digita. O dado informado só "
   "preenche o campo vazio (não substitui o RSPE).",
   r, [C("termino", "contem", "12/06/2031")],
   acoes=[{"metodo": "dado_manual", "args": [proc, "rspe|termino_previsao_seeu", "12/06/2031"]}])

# 1028 - art. 75: 30 anos (fatos antes de 23/01/2020)
k = 1028
ini = "03/05/2014"
pa, pb = proc_crim(k, 2014), "%07d-00.2014.8.12.0002" % (8800000 + k)
cr = [crime(pa, pena_dias=anos(28), fato="10/01/2014", **ROUBO), crime(pb, pena_dias=anos(20), fato="20/03/2014", **ROUBO)]
for c in cr:
    c["fracao_progressao"] = "1/6 - Comum"
T = F(D(ini).replace(year=2062) - timedelta(days=1))
r = rspe(k, cr, [prisao(ini, pa + ", " + pb, "PRISÃO PREVENTIVA")], [regime_ini("10/02/2015")], ini=ini, term="02/05/2062", fp="1/6", fl="1/3",
         prog="", liv="")
mk(k, "Extinção", "Penas somadas de 48 anos, fatos de 2014, preso desde 03/05/2014: término do SEEU 02/05/2062",
   "Aba Geral: término 02/05/2044*; Auditoria alerta limite de 30 anos (máximo em 02/05/2044); aba Extinção mantém 02/05/2062 com 'art. 75 a verificar'.",
   "CP, art. 75 (redação anterior à Lei 13.964/2019, fatos de 2014): 30 anos desde 03/05/2014, dia do começo incluído -> último dia 02/05/2044.",
   r, [C("termino", "contem", "02/05/2044"), AUD("limite-de-cumprimento-art-75", contem="02/05/2044"), C("ext_termino", "contem", "02/05/2062")])

# 1029 - art. 75: 40 anos (fato posterior a 23/01/2020)
k = 1029
ini = "01/03/2021"
pa = proc_crim(k, 2021)
cr = [crime(pa, pena_dias=anos(52), fato="15/02/2021", **ROUBO)]
r = rspe(k, cr, [prisao(ini, pa, "PRISÃO PREVENTIVA")], [regime_ini("20/10/2021")], ini=ini, term="28/02/2073", fp="25%", fl="1/3", prog="", liv="")
mk(k, "Extinção", "Pena de 52 anos por fato de 15/02/2021, preso desde 01/03/2021: término do SEEU 28/02/2073",
   "Aba Geral: término 28/02/2061*; Auditoria alerta o limite de 40 anos (máximo 28/02/2061).",
   "CP, art. 75, com a Lei 13.964/2019 (fato posterior a 23/01/2020): 40 anos desde 01/03/2021 -> último dia 28/02/2061.",
   r, [C("termino", "contem", "28/02/2061"), AUD("limite-de-cumprimento-art-75", contem="28/02/2061")])

# =============================== 5. Coluna Falta ===============================
FALTA_INI = "02/02/2024"


def com_falta(k, incs_extra, evs_extra=(), crimes_extra=(), pena=anos(6), **kw):
    pc = proc_crim(k, 2022)
    cr = [crime(pc, pena_dias=pena, fato="10/03/2022", **FURTO)] + list(crimes_extra)
    evs = [prisao(FALTA_INI, pc, "PRISÃO DEFINITIVA")] + list(evs_extra)
    tot = sum(c["_dias"] for c in cr)
    r = rspe(k, cr, evs, [regime_ini(FALTA_INI)] + list(incs_extra), ini=FALTA_INI, fp="16%", fl="1/3",
             prog=mais(FALTA_INI, int(tot * 0.16)), liv=mais(FALTA_INI, tot // 3), **kw)
    return r


k = 1030
r = com_falta(k, [inc("HOMOLOGAÇÃO DE FALTA GRAVE", "22/04/2026", "18/06/2026", "22/04/2026")])
mk(k, "Livramento", "Falta grave homologada, fato em 22/04/2026 (dentro dos 12 meses do RSPE)",
   "Coluna Falta 'Sim'.", "Janela: 12 meses antes da geração (05/10/2026). Fato 22/04/2026, reconhecido em juízo (LEP, art. 118; CP, art. 83, III, b).",
   r, [C("falta", "contem", "Sim")])

k = 1031
r = com_falta(k, [inc("HOMOLOGAÇÃO DE FALTA GRAVE", "15/07/2025", "02/09/2025", "15/07/2025")])
mk(k, "Livramento", "Falta grave homologada, fato em 15/07/2025 (fora dos 12 meses do RSPE)",
   "Coluna Falta 'Não consta'.", "Fato 15/07/2025 anterior a 06/10/2025 (início da janela de 12 meses até 05/10/2026). CP, art. 83, III, b.",
   r, [C("falta", "contem", "Não consta")])

k = 1032
r = com_falta(k, [inc("HOMOLOGAÇÃO DE FALTA GRAVE", "12/05/2026", "", "12/05/2026", sit="PENDENTE")])
mk(k, "Livramento", "Falta com fato em 12/05/2026 pendente de homologação",
   "Coluna Falta 'A apurar' (não 'Sim').", "Sem decisão, não há falta reconhecida (LEP, art. 118, § 2º; STJ, Tema 1195); indício a apurar.",
   r, [C("falta", "contem", "apurar")])

k = 1033
r = com_falta(k, [inc("HOMOLOGAÇÃO DE FALTA GRAVE", "08/05/2026", "30/06/2026", "08/05/2026", sit="NÃO CONCEDIDO")])
mk(k, "Livramento", "Homologação de falta (fato 08/05/2026) não concedida",
   "Coluna Falta 'Não consta'.", "Falta afastada em juízo não produz efeito.", r, [C("falta", "contem", "Não consta")])

k = 1034
pn = "%07d-00.2026.8.12.0002" % (8800000 + k)
r = com_falta(k, [inc(REG, "Fechado - Somatório", "25/09/2026", "25/09/2026")],
              crimes_extra=[crime(pn, pena_dias=anos(1, 6), fato="10/04/2026", sentenca="10/07/2026", transito="20/08/2026", **RECEP)])
mk(k, "Livramento", "Crime doloso com fato em 10/04/2026, durante a execução, com trânsito em 20/08/2026 (somado na execução)",
   "Coluna Falta 'Sim'.", "Crime doloso no cumprimento da pena é falta grave (LEP, art. 52); condenado com trânsito antes do RSPE, "
   "fato dentro dos 12 meses (CP, art. 83, III, b).", r, [C("falta", "contem", "Sim")])

k = 1035
pn = "%07d-00.2026.8.12.0002" % (8800000 + k)
r = com_falta(k, [], crimes_extra=[crime(pn, pena_dias=anos(1, 3), fato="18/04/2026", sentenca="20/08/2026", transito="", **RECEP)])
mk(k, "Livramento", "Crime doloso com fato em 18/04/2026, durante a execução, condenado em 20/08/2026 sem trânsito",
   "Coluna Falta 'A apurar'.", "Sem trânsito e sem falta reconhecida em procedimento disciplinar, é só indício (CF, art. 5º, LVII; Súmula 526/STJ "
   "dispensa o trânsito, mas exige o reconhecimento da falta).", r, [C("falta", "contem", "apurar")])

k = 1036
fuga, rec = "10/08/2025", "20/04/2026"
out = (D(rec) - D(fuga)).days - 1
r = com_falta(k, [inc("HOMOLOGAÇÃO DE FALTA GRAVE", "10/08/2025", "15/05/2026", "10/08/2025")],
              evs_extra=[interr(fuga, "FUGA"), prisao(rec, proc_crim(k, 2022), "RECAPTURA")], interrompidos=out)
mk(k, "Livramento", "Fuga em 10/08/2025 (antes da janela) com recaptura em 20/04/2026 (dentro) e falta homologada",
   "Coluna Falta 'Sim' (falta permanente: os 12 meses contam da recaptura).",
   "Fuga é falta permanente; cessa na recaptura (STJ, HC 527.625). Recaptura 20/04/2026 dentro de 06/10/2025-05/10/2026; reconhecida em juízo.",
   r, [C("falta", "contem", "Sim", "Programa mostra 'Não consta' e nenhum indício: a homologação com a data da evasão (fora da janela) "
                                   "apaga a fuga, embora a falta permanente tenha durado até a recaptura (20/04/2026), dentro dos 12 meses "
                                   "(STJ, HC 527.625; CP, art. 83, III, b)")])

k = 1037
r = com_falta(k, [], remidos=20)
r["saldo_remidos"] = "20 dias (30 dias remidos - 10 dias perdidos)"
mk(k, "Livramento", "Saldo de remição com 10 dias perdidos, sem incidente de falta datado no RSPE",
   "Coluna Falta 'A apurar' (há perda de dias - logo houve falta grave -, mas sem data não se sabe se está nos 12 meses).",
   "Perda de dias remidos pressupõe falta grave (LEP, art. 127); sem a data, não se afirma 'Sim' nem 'Não consta'.",
   r, [C("falta", "contem", "apurar")])

k = 1038
r = com_falta(k, [], evs_extra=[interr("14/06/2026", "FUGA")], interrompidos=(GER - D("14/06/2026")).days, term="", regime="")
proc = r["processo_execucao"]
mk(k, "Livramento", "Fuga em 14/06/2026 sem recaptura; o operador marca 'não é falta' (ex.: saída autorizada lançada como fuga)",
   "Coluna Falta 'Não consta' depois da decisão do operador.", "Decisão do operador prevalece sobre o indício (o indício não é falta reconhecida).",
   r, [C("falta", "contem", "Não consta")],
   acoes=[{"metodo": "dado_manual", "args": [proc, "falta|14/06/2026|INTERRUPCAOFUGA", "nao"]}])

# =============================== 6. Conduta (ficha) ===============================
for k, cond, esp, ruim in ((1039, "ÓTIMA", "Ótima", False), (1040, "", "Não Informada Na Ficha", False), (1041, "MÁ", "Má", True)):
    r, pc = padrao(k, anos(6), "07/03/2024")
    mk(k, "Progressão", "Ficha do SIAPEN com conduta '%s'" % (cond or "(campo ausente)"),
       "Coluna Conduta '%s'%s." % (esp, "; conduta ruim (requisito subjetivo não atendido)" if ruim else ""),
       "Exibição do campo da ficha (LEP, art. 112, § 1º: boa conduta carcerária).",
       r, [C("conduta", "eq", esp), C("conduta_ruim", "eq", ruim)], ficha=ficha(k, cond, prisao_="07/03/2024"))

k = 1042
r, pc = padrao(k, anos(6), "07/03/2024")
mk(k, "Progressão", "Ficha com conduta 'RESPONDE PADIC' (procedimento disciplinar em curso)",
   "Coluna Conduta 'Responde Padic'; requisito de conduta 'a conferir', não 'conduta ruim'.",
   "Procedimento em curso não é sanção reconhecida (CF, art. 5º, LVII; LEP, arts. 59 e 118, § 2º).",
   r, [C("conduta", "contem", "Responde"),
       dict(C("conduta_ruim", "eq", False), decisao=True, nota="Tese: PADIC em curso não é conduta ruim; o programa pode marcar 'conduta ruim' só como filtro")],
   ficha=ficha(k, "RESPONDE PADIC", prisao_="07/03/2024"))

# =============================== 7. Pena zero, medida de segurança, suspenso ===============================
k = 1043
pc = proc_crim(k, 2022)
cr = [crime(pc, pena_dias=0, fato="10/03/2022", pena_total_processo="2a6m0d - PENA ORIGINÁRIA", **FURTO)]
cr[0]["pena_imposta"] = "0 ano(s), 0 mês(es) e 0 dia(s)"
r = rspe(k, cr, [prisao("19/05/2025", pc, "PRISÃO DEFINITIVA")], [regime_ini("19/05/2025", "Semiaberto")], ini="19/05/2025", pena=anos(2, 6),
         regime="Semiaberto - ATIVO", fp="16%", fl="1/3", prog=mais("19/05/2025", int(anos(2, 6) * .16)), liv="")
fora(r["termino_previsao_seeu"])
mk(k, "Auditoria", "Crime único da ação com 'Pena Imposta: 0' e pena total da ação 2a6m0d",
   "A pena do crime passa a 2a6m0d (da ação); Auditoria 'info' de pena zerada, usada a da ação; nada 'a verificar' de pena não informada.",
   "Ação de um só crime: a pena da ação é a do crime (LEP, art. 66, III, a).",
   r, [C("aud_itens", "nao_contem", "pena não informada"),
       C("aud_itens", "contem", "pena do crime zerada"), P(0, "pena", "regex", r"2 anos.*6 meses|2a6m")])

k = 1044
pc = proc_crim(k, 2022)
cr = [crime(pc, pena_dias=anos(3), fato="10/03/2022", pena_total_processo="5a0m0d - PENA ORIGINÁRIA", **FURTO),
      crime(pc, pena_dias=0, fato="10/03/2022", pena_total_processo="5a0m0d - PENA ORIGINÁRIA", **RECEP)]
cr[1]["pena_imposta"] = "0 ano(s), 0 mês(es) e 0 dia(s)"
r = rspe(k, cr, [prisao("06/06/2024", pc, "PRISÃO DEFINITIVA")], [regime_ini("06/06/2024")], ini="06/06/2024", pena=anos(5), fp="16%", fl="1/3",
         prog=mais("06/06/2024", int(anos(5) * .16)), liv=mais("06/06/2024", anos(5) // 3))
fora(r["termino_previsao_seeu"], r["livramento_previsao_seeu"])
mk(k, "Auditoria", "Ação com dois crimes, um deles com 'Pena Imposta: 0' (pena da ação 5 anos, outro crime 3 anos)",
   "Auditoria 'verificar': pena não informada no RSPE para a receptação (não presumir zero nem 2 anos).",
   "Com dois crimes a pena da ação não diz a de cada um; o zero não é dado (LEP, art. 66, III, a).",
   r, [C("aud_itens", "contem", "pena não informada")])

k = 1045
pc = proc_crim(k, 2023)
cr = [crime(pc, pena_dias=0, fato="02/02/2023", pena_total_processo="1a0m0d - MEDIDA DE SEGURANÇA", regime="Indefinido", **FURTO)]
cr[0]["pena_imposta"] = "0 ano(s), 0 mês(es) e 0 dia(s)"
r = rspe(k, cr, [prisao("15/09/2025", pc, "INTERNAÇÃO")], [], ini="15/09/2025", pena=0, regime="", term="")
r.update(pena_total="0a0m0d", pena_cumprida="0a0m0d", pena_remanescente="0a0m0d")
mk(k, "Auditoria", "Medida de segurança (internação desde 15/09/2025), prazo mínimo de 1 ano",
   "Auditoria 'verificar' de medida de segurança; nenhum término calculado; sem 'Faltam dados' de término.",
   "Medida de segurança por prazo indeterminado, com prazo mínimo (CP, art. 97, § 1º): o prazo mínimo não é pena e não há término.",
   r, [AUD("medida-de-seguranca-na-execucao"), sem_data("termino"),
       AUD("faltam-dados-termino_previsao_seeu", presente=False, nota="Programa pede 'Faltam dados: término': medida de segurança não tem término (CP, art. 97, § 1º)"),
       AUD("faltam-dados-pena_total", presente=False, nota="Programa pede a pena total: o prazo mínimo não é pena"),
       AUD("guia-sem-pena-calculada-pena-total-com", presente=False, nota="Programa alerta 'guia sem pena calculada ... com 0 condenações ativas': não há pena a calcular")])

k = 1046
pa = proc_crim(k, 2022)
pb = "%07d-00.2023.8.12.0002" % (8800000 + k)
cr = [crime(pa, pena_dias=anos(5), fato="10/03/2022", **FURTO), crime(pb, pena_dias=anos(1), fato="10/01/2023", regime="Aberto", suspenso="Sim", **RECEP)]
r = rspe(k, cr, [prisao("12/10/2023", pa, "PRISÃO DEFINITIVA")], [regime_ini("12/10/2023")], ini="12/10/2023", pena=anos(5), fp="16%", fl="1/3",
         prog=mais("12/10/2023", int(anos(5) * .16)), liv=mais("12/10/2023", anos(5) // 3))
fora(r["termino_previsao_seeu"])
mk(k, "Auditoria", "Crime de 1 ano com 'Suspenso: Sim' (fora da pena total de 5 anos)",
   "Auditoria 'verificar': crime suspenso, sem a causa (sursis ou substituição) no RSPE.",
   "Sursis (CP, art. 77) e substituição (CP, art. 44) têm efeitos diferentes; o RSPE não diz qual (LEP, arts. 111 e 156).",
   r, [AUD("crime-suspenso-a-verificar")])

# =============================== 8. Várias guias da mesma pessoa ===============================
k = 1047
r, pc = padrao(k, anos(6), "20/02/2024", eventos=[prisao("20/02/2024", proc_crim(k, 2022), "PRISÃO DEFINITIVA")],
               incidentes=[regime_ini("20/02/2024"), inc(REG, "Semiaberto - Progressão", "15/03/2025", "10/03/2025")], db="10/03/2025",
               regime="Semiaberto - ATIVO", prog=mais("10/03/2025", 300))
fora(r["termino_previsao_seeu"], r["progressao_previsao_seeu"], r["livramento_previsao_seeu"])
pb = "%07d-00.2024.8.12.0003" % (8800000 + k)
e = rspe(k + 50, [crime(pb, pena_dias=anos(2), fato="05/06/2023", **ESTEL)], [], [], pena=anos(2), regime="", term="",
         cpf=r["cpf"], nasc=r["data_nascimento"], ger=D("01/10/2026"))
e.update(nome=r["nome"], nome_mae=r["nome_mae"], processo_execucao="%07d-00.2026.8.12.0001" % (9900000 + k + 50))
mk(k, "Auditoria", "Mesma pessoa (mesmo CPF) com duas execuções ativas: a principal (presa, com eventos) e outra só com a guia",
   "Fica na lista a execução com eventos; Auditoria 'verificar': mais de uma execução ativa - pedir a unificação.",
   "As penas da mesma pessoa devem ser somadas ou unificadas (LEP, arts. 66, III, a, e 111; CP, art. 75).",
   r, [AUD("outras-execucoes-ativas", nivel="verificar")], extra=[e])

k = 1048
r, pc = padrao(k, anos(6), "20/02/2024")
fora(r["termino_previsao_seeu"], r["progressao_previsao_seeu"], r["livramento_previsao_seeu"])
pb = "%07d-00.2016.8.12.0003" % (8800000 + k)
e = rspe(k + 50, [crime(pb, pena_dias=anos(2), fato="05/06/2016", extinto="Sim", **ESTEL)],
         [prisao("10/01/2017", pb, "PRISÃO DEFINITIVA"), interr("09/01/2019", "CUMPRIMENTO DA PENA")],
         [inc("EXTINÇÃO", "CUMPRIMENTO DA PENA", "20/02/2019", "09/01/2019", procs=pb)], ini="10/01/2017", pena=anos(2),
         cpf=r["cpf"], nasc=r["data_nascimento"], status="ARQUIVADO", ger=D("06/10/2026"))
e.update(nome=r["nome"], nome_mae=r["nome_mae"], processo_execucao="%07d-00.2026.8.12.0001" % (9900000 + k + 50))
mk(k, "Auditoria", "Mesma pessoa com outra execução arquivada e extinta (RSPE mais recente que o da ativa)",
   "Fica na lista a execução ativa (não a mais recente); Auditoria 'info': outras execuções da mesma pessoa fora da lista.",
   "A execução encerrada não tem pena a acompanhar (CP, art. 107; LEP, art. 66, II); serve de histórico (reincidência a conferir, CP, art. 63).",
   r, [AUD("outras-execucoes", nivel="info"), AUD("outras-execucoes-ativas", presente=False)], extra=[e])

# =============================== 9. Divergências da fonte (triângulo) ===============================
k = 1049
pa = proc_crim(k, 2021)
pb = "%07d-00.2022.8.12.0002" % (8800000 + k)
cr = [crime(pa, pena_dias=anos(4), fato="10/03/2021", **FURTO), crime(pb, pena_dias=anos(3), fato="10/03/2022", **ESTEL)]
r = rspe(k, cr, [prisao("16/08/2023", pa + ", " + pb, "PRISÃO DEFINITIVA")], [regime_ini("16/08/2023")], ini="16/08/2023", pena=anos(6),
         fp="16%", fl="1/3", prog=mais("16/08/2023", int(anos(6) * .16)), liv=mais("16/08/2023", anos(6) // 3))
fora(r["termino_previsao_seeu"], r["livramento_previsao_seeu"])
mk(k, "Auditoria", "Pena total do RSPE 6a0m0d menor que a soma das ações (4a + 3a = 7a), sem comutação, indulto, suspensão ou extinção",
   "Auditoria 'info' (favorável ao assistido, sem pedido); sem triângulo vermelho.",
   "O documento não fecha, mas a diferença favorece o assistido: nada a pedir. Dado da fonte, não falha de leitura.",
   r, [AUD("divergencia-seeu-pena-total", nivel="info"), C("div_seeu", "vazio")])

k = 1050
pa = proc_crim(k, 2021)
cr = [crime(pa, pena_dias=anos(6), fato="10/03/2021", pena_total_processo="7a0m0d - PENA ORIGINÁRIA", **FURTO)]
r = rspe(k, cr, [prisao("16/08/2023", pa, "PRISÃO DEFINITIVA")], [regime_ini("16/08/2023")], ini="16/08/2023", pena=anos(6),
         fp="16%", fl="1/3", prog=mais("16/08/2023", int(anos(6) * .16)), liv=mais("16/08/2023", anos(6) // 3))
mk(k, "Auditoria", "Ação com pena total 7a0m0d e um único crime de 6a0m0d",
   "Auditoria 'alerta' de pena da ação diferente da soma dos crimes; triângulo vermelho com '7a0m0d x ... 6a0m0d'.",
   "O próprio RSPE não fecha: conferir a sentença nos autos (dado da fonte).",
   r, [AUD("divergencia-seeu-pena-acao", nivel="alerta"), C("div_seeu_txt", "contem", ["7a0m0d", "6a0m0d"])])

k = 1051
pa = proc_crim(k, 2024)
cr = [crime(pa, pena_dias=anos(5), fato="20/08/2024", **FURTO)]
r = rspe(k, cr, [prisao("10/01/2024", pa), interr("12/03/2024", "LIBERDADE PROVISÓRIA", pa), prisao("03/06/2025", pa, "PRISÃO DEFINITIVA")],
         [regime_ini("03/06/2025")], ini="03/06/2025", pena=anos(5), fp="16%", fl="1/3", prog="", liv="")
r["pena_cumprida"] = pena_cab((GER - D("03/06/2025")).days + 1 + 63)
mk(k, "Auditoria", "Prisão em flagrante (10/01/2024) lançada mais de 30 dias antes do fato da ação vinculada (20/08/2024)",
   "Auditoria 'verificar' (não 'alerta' contra a detração): prisão anterior ao fato da ação vinculada; triângulo vermelho.",
   "Prisão antes do fato não pode ser deste crime; pode ser detração de outro processo (CP, art. 42) - conferir nos autos sem pedir retirada.",
   r, [AUD("divergencia-seeu-prisao-antes-do-fato", nivel="verificar"), C("div_seeu", "nao_vazio")])

k = 1052
c1, c2 = cpf_valido("900001052"), cpf_valido("900002052")
r, pc = padrao(k, anos(6), "07/03/2024", cpf=c1)
mk(k, "Auditoria", "CPF da ficha do SIAPEN diferente do CPF do RSPE (os dois válidos)",
   "Auditoria 'alerta' de CPF divergente; triângulo vermelho.", "Dado da fonte: conferir qual cadastro está errado e se a ficha é da pessoa.",
   r, [AUD("divergencia-siapen-cpf", nivel="alerta"), C("div_seeu", "nao_vazio")],
   ficha=ficha(k, "BOA", cpf="%s.%s.%s-%s" % (c2[:3], c2[3:6], c2[6:9], c2[9:]), prisao_="07/03/2024"))

k = 1053
r, pc = padrao(k, anos(6), "07/03/2024", nasc="14/04/1980")
mk(k, "Auditoria", "Nascimento no RSPE (14/04/1980) diferente da ficha (14/04/1981), sem efeito em marcos de idade",
   "Auditoria 'info' ('sem efeito nos marcos'); sem triângulo.", "Fato em 2022 aos 41/42 anos; nenhuma idade de 21, 60 ou 70 anos em jogo (CP, art. 115; decretos).",
   r, [AUD("divergencia-siapen-nascimento", nivel="info"), C("div_seeu", "vazio")],
   ficha=ficha(k, "BOA", nasc="14/04/1981", prisao_="07/03/2024"))

k = 1054
r, pc = padrao(k, anos(6), "07/03/2024", nasc="20/11/1965")
mk(k, "Indulto", "Nascimento no RSPE (20/11/1965: 60 anos em 25/12/2025) diferente da ficha (20/11/1966: 59 anos)",
   "Auditoria 'verificar' (muda requisito de idade do Decreto 12.790/2025); triângulo vermelho.",
   "Em 25/12/2025: 60 anos pelo RSPE, 59 pela ficha; o art. 9º, § 2º, I, do Decreto 12.790/2025 (lapsos pela metade aos 60) depende da data certa.",
   r, [AUD("divergencia-siapen-nascimento", nivel="verificar"), C("div_seeu", "nao_vazio")],
   ficha=ficha(k, "BOA", nasc="20/11/1966", prisao_="07/03/2024"))

k = 1055
pa = proc_crim(k, 2021)
cr = [crime(pa, pena_dias=anos(4), fato="10/03/2021", sentenca="10/09/2021", **FURTO),
      crime(pa, pena_dias=anos(2), fato="15/05/2021", sentenca="20/02/2022", **ESTEL)]
cr[0]["pena_total_processo"] = "4a0m0d - PENA ORIGINÁRIA"
cr[1]["pena_total_processo"] = "2a0m0d - PENA ORIGINÁRIA"
r = rspe(k, cr, [prisao("16/08/2023", pa, "PRISÃO DEFINITIVA")], [regime_ini("16/08/2023")], ini="16/08/2023", pena=anos(6),
         fp="16%", fl="1/3", prog=mais("16/08/2023", int(anos(6) * .16)), liv=mais("16/08/2023", anos(6) // 3))
mk(k, "Auditoria", "Duas ações com o mesmo número no RSPE, com penas e sentenças diferentes",
   "Auditoria 'alerta' de ação duplicada; triângulo vermelho.", "O mesmo número não pode ter duas sentenças: erro de cadastro na fonte (conferir nos autos).",
   r, [AUD("divergencia-seeu-acao-duplicada", nivel="alerta"), C("div_seeu", "nao_vazio")])

# =============================== 10. Cadastro da guia ===============================
k = 1056
r = rspe(k, [], [], [], pena=0, regime="", term="", db="", _rspe_sem_processo=True)
mk(k, "Auditoria", "RSPE só com o cabeçalho: nenhum processo criminal, evento ou incidente",
   "Situação 'SEM CONDENAÇÃO CADASTRADA NO SEEU'; Auditoria 'verificar' de execução sem condenação.",
   "Sem guia cadastrada não há pena a executar (LEP, arts. 105 a 107).",
   r, [C("cumprimento", "contem", "SEM CONDENAÇÃO"), AUD("execucao-sem-condenacao-seeu", nivel="verificar")])

k = 1057
r = rspe(k, [], [prisao("08/08/2025", proc_crim(k, 2024), "PRISÃO DEFINITIVA")], [regime_ini("08/08/2025")], ini="08/08/2025", pena=anos(3),
         regime="Fechado - ATIVO", _rspe_sem_crime=True)
mk(k, "Auditoria", "Processo criminal cadastrado (pena 3 anos) sem nenhum crime lançado",
   "Auditoria 'verificar': condenação sem crime cadastrado no SEEU.", "Sem os crimes não há fração, prescrição nem decretos (LEP, arts. 105 e 106, § 1º).",
   r, [AUD("condenacao-sem-crime-seeu", nivel="verificar")])

k = 1058
r, pc = padrao(k, anos(6), "07/03/2024")
r["_acoes_sem_crime"] = [{"processo_criminal": "%07d-00.2023.8.12.0004" % (8800000 + k), "pena_total_processo": "2a0m0d - PENA ORIGINÁRIA",
                          "regime_sentenca": "Aberto", "data_sentenca": "10/05/2024", "vara_condenacao": "Campo Grande, 2ª Vara", "tipo_processo": "ACAO PENAL"}]
mk(k, "Auditoria", "Ação penal de 2 anos sem tipificação (sem bloco 'Lei:'), ao lado de um crime regular",
   "Auditoria 'alerta': ação penal sem crime cadastrado (pena fora das contas).", "A pena dessa ação não entra nas frações e decretos sem a tipificação (LEP, arts. 66, III, e 111).",
   r, [AUD("acao-penal-sem-crime-cadastrado", nivel="alerta")])

k = 1059
r, pc = padrao(k, anos(6), "07/03/2024", regime="")
mk(k, "Auditoria", "Em cumprimento (preso desde 07/03/2024, sem interrupção) e 'Regime Atual' em branco",
   "Auditoria 'alerta': Faltam dados - regime atual não lido do RSPE - informar.", "Com a pena em curso o SEEU imprime o regime: a falta é dado não lido.",
   r, [AUD("faltam-dados-regime_atual", nivel="alerta")])

json.dump(CASOS, open(os.path.join(AQUI, "leitura.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(CASOS), "casos")
