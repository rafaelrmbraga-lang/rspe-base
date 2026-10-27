"""Casos da área "remicao" (remição e aba Ficha): k 5001 a 5099. Gera cobertura/remicao.json.
Gabarito feito à mão pela lei (LEP, arts. 126 a 130; Res. CNJ 391/2021; STJ, Tema 1.120; decretos) e pelas escolhas de política
declaradas na instrução; contas de dias com função própria (segunda a sábado, sem domingos e feriados), sem usar o código do APTO.
Rodar: python3 cobertura/gera_remicao.py (a partir de casos_simulados)."""
import os, sys, json
from datetime import date, timedelta
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from base_casos import crime, rspe, ev, prisao, interr, inc, C, AUD, caso, proc_crim, anos, D, F, CP

# ----------------------------------------------------------------- calendário próprio do gabarito
def pascoa(a):
    g = a % 19; c = a // 100; h = (c - c // 4 - (8 * c + 13) // 25 + 19 * g + 15) % 30
    i = h - (h // 28) * (1 - (h // 28) * (29 // (h + 1)) * ((21 - g) // 11))
    j = (a + a // 4 + i + 2 - c + c // 4) % 7
    m = 3 + (i - j + 40) // 44
    return date(a, m, i - j + 28 - 31 * ((m // 4)))


def feriados(a):
    """Feriados: nacionais (Lei 662/1949, Lei 6.802/1980; 20/11 pela Lei 14.759/2023, desde 2024), Sexta-feira Santa (Lei 9.093/1995,
    feriado religioso municipal em Campo Grande) e 11/10 (criação do Estado de MS)."""
    fs = {date(a, 1, 1), date(a, 4, 21), date(a, 5, 1), date(a, 9, 7), date(a, 10, 12), date(a, 11, 2), date(a, 11, 15), date(a, 12, 25),
          date(a, 10, 11), pascoa(a) - timedelta(days=2)}
    if a >= 2024:
        fs.add(date(a, 11, 20))
    return fs


def uteis(i, f, dias=(0, 1, 2, 3, 4, 5), fer=True, fora=()):
    """Dias de trabalho de i a f (inclusive): segunda a sábado por padrão, sem feriados."""
    i, f = D(i), D(f)
    n = 0
    d = i
    while d <= f:
        if d.weekday() in dias and not (fer and d in feriados(d.year)) and not any(D(a) <= d <= D(b) for a, b in fora):
            n += 1
        d += timedelta(days=1)
    return n


def recua(fim, n):
    """Primeiro dia da sequência de n dias de trabalho (segunda a sábado, sem feriados) que termina em fim."""
    d = D(fim)
    while True:
        if d.weekday() < 6 and d not in feriados(d.year):
            n -= 1
            if n == 0:
                return F(d)
        d -= timedelta(days=1)


def nf(x):
    s = ("%.2f" % x).rstrip("0").rstrip(".")
    return s.replace(".", ",")


def letivos(i, f):
    """Dias letivos (segunda a sexta, sem feriados e sem recesso escolar: janeiro, 16 a 31/07, 20 a 31/12)."""
    i, f = D(i), D(f)
    n, d = 0, i
    while d <= f:
        rec = d.month == 1 or (d.month == 7 and d.day >= 16) or (d.month == 12 and d.day >= 20)
        if d.weekday() < 5 and d not in feriados(d.year) and not rec:
            n += 1
        d += timedelta(days=1)
    return n


# ----------------------------------------------------------------- construtores locais
UN = "ESTABELECIMENTO PENAL SIMULADO DE CAMPO GRANDE"
IMP = "05/10/2026"


def pid(k):
    return "%07d-00.2026.8.12.0001" % (9900000 + k)


def ficha(k, eventos, entrada="02.01.2023", unidade=UN, imp=IMP, autos=None):
    evs = [{"data": entrada, "texto": "Entrada na Unidade Penal: %s, Procedente: DEPAC, Conforme OF 1/%s." % (unidade, entrada[-4:])}]
    evs += [{"data": d, "texto": t} for d, t in eventos]
    evs.sort(key=lambda e: (e["data"][6:], e["data"][3:5], e["data"][:2]))
    return {"tipo": "ficha_disciplinar", "nome": "SIMULADO CASO %03d" % k, "cpf": "%011d" % (90000000000 + k), "cpf_em_branco": False,
            "data_nascimento": "01/01/1985", "nome_mae": "MAE SIMULADA %03d" % k, "filiacao": "MAE SIMULADA %03d" % k, "artigo": "ART 157",
            "data_prisao": entrada.replace(".", "/"), "condenacao": "CONDENADO", "unidade": unidade, "data_entrada": entrada.replace(".", "/"),
            "sexo": "M", "conduta": "BOA", "data_impressao": imp, "paginas": 2, "paginas_sem_texto": [],
            "autos": autos if autos is not None else [pid(k)], "eventos": evs, "historico_oculto": []}


def REM(dias, dec, ref=None, sit="CONCEDIDO"):
    return inc("REMIÇÃO", "%s Dia(s)" % nf(dias), dec, ref or dec, sit=sit)


def PERDA(dias, dec):
    return inc("DIAS REMIDOS PERDIDOS", "%s Dia(s)" % nf(dias), dec, dec)


def FALTA(fato, dec):
    return inc("FALTA GRAVE", "Data do fato: %s" % fato, dec, fato)


def RS(k, incs=(), ini="02/01/2023", pena=None, crimes=None, eventos=None, perdidos=0, **kw):
    crimes = crimes or [crime(proc_crim(k, 2022), "ART 157: Roubo", anos(8), "15/03/2022", tipo="CAPUT: tipo simulado, Reclusão: 4 a 10 anos E Multa",
                              fp="25% - Primário com violência", sentenca="20/10/2022", transito="20/12/2022")]
    eventos = eventos or [prisao(ini, crimes[0]["processo_criminal"], "PRISÃO DEFINITIVA")]
    rem = sum(float(i["complemento"].split()[0].replace(",", ".")) for i in incs
              if i["tipo"].startswith("REMI") and i.get("situacao") == "CONCEDIDO")
    r = rspe(k, crimes, eventos, list(incs), ini=ini, pena=pena, remidos=int(rem - perdidos), **kw)
    r["saldo_remidos"] = "%s dias (%s dias remidos - %s dias perdidos)" % (nf(rem - perdidos), nf(rem), nf(perdidos))
    return r


INI = lambda setor, ci: "TRABALHO: Iniciou atividade laboral, no setor de trabalho %s, conforme documento CI %s." % (setor, ci)
FIM = lambda setor, ci, mot="a pedido": "TRABALHO: Deixa de trabalhar, no setor de trabalho %s, conforme documento CI %s, motivo: %s." % (setor, ci, mot)


def AT(num, ini, fim, trab, rem, extra=""):
    if trab > uteis(ini, fim) + 2:
        print("AVISO capacidade: atestado %s com %d trabalhados para %d dias de segunda a sábado" % (num, trab, uteis(ini, fim)))
    return "FOI EMITIDO ATESTADO DE TRABALHO Nº %s, PERÍODO DE %s A %s, %d DIAS TRABALHADOS E %s DIAS REMIDOS%s." % (num, ini, fim, trab, nf(rem), extra)


PET = ", PETICIONADO NO SISTEMA SEEU"
CASOS = []


def add(k, titulo, situacao, esperado, conta, r, checks, f=None, aba="Ficha/Remição", acoes=None, nota=None, decisao=False):
    c = caso(k, "R-remicao", titulo, conta, r, checks, ficha=f, acoes=acoes)
    c.update(aba=aba, situacao=situacao, esperado=esperado)
    if nota:
        c["nota"] = nota
    if decisao:
        c["decisao"] = True
    CASOS.append(c)


# ================================================================= 1. Atestado de trabalho: 3 x 1, peticionamento, situação
k = 5001
t = uteis("03/03/2025", "30/08/2025")
add(k, "Atestado peticionado e remido 90 dias depois, mesmo valor: Em ordem",
    "Atestado já remido: o RSPE tem remição do mesmo valor decidida 90 dias depois da emissão",
    "Situação 'Em ordem' (verde); ficha 50 / RSPE 50; atestado 'Provavelmente remido em 04/12/2025'.",
    "Horta de 03/03/2025 a 30/08/2025 (%d dias de segunda a sábado possíveis). Atestado nº 061/2025, emitido e peticionado em 05/09/2025: "
    "150 trabalhados -> 150 ÷ 3 = 50 dias (LEP, art. 126, § 1º, II). RSPE: remição de 50 dias decidida em 04/12/2025 (90 dias depois). "
    "Diferença 50 - 50 = 0. Política: mesmo valor decidido até 180 dias = 'provavelmente remido'." % t,
    RS(k, [REM(50, "04/12/2025", "30/08/2025")]),
    [C("fd_sit", "eq", "Em ordem"), C("fd_cor", "eq", "verde"), C("fd_remidos", "eq", "50 / 50"),
     C("fd_novo", "contem", "Provavelmente remido em 04/12/2025")],
    ficha(k, [("03.03.2025", INI("HORTA", "10/2025")), ("30.08.2025", FIM("HORTA", "21/2025")),
              ("05.09.2025", AT("061/2025", "03/03/2025", "30/08/2025", 150, 50, PET))]))

k = 5002
add(k, "Atestado 3x1 (96 trabalhados = 32 remidos), peticionado, sem remição no RSPE",
    "Conta do trabalho: 1 dia remido a cada 3 trabalhados; RSPE sem nenhuma remição",
    "Ficha 32 / RSPE 0; situação 'Verificar remição' (amarelo); documento 'Sem remição no RSPE'.",
    "Atestado nº 071/2026 (02/02 a 30/05/2026, 96 dias trabalhados, 32 remidos), peticionado em 10/06/2026. 96 ÷ 3 = 32 (LEP, art. 126, "
    "§ 1º, II). O RSPE não tem remição: 32 dias comprovados e não apreciados (diferença +32).",
    RS(k),
    [C("fd_remidos", "eq", "32 / 0"), C("fd_sit", "contem", "Verificar remição"), C("fd_cor", "eq", "amarelo"),
     C("fd_novo", "contem", "Sem remição no RSPE")],
    ficha(k, [("02.02.2026", INI("COSTURA", "3/2026")), ("30.05.2026", FIM("COSTURA", "40/2026")),
              ("10.06.2026", AT("071/2026", "02/02/2026", "30/05/2026", 96, 32, PET))]))

k = 5003
add(k, "Atestado sem peticionamento, posterior à última remição: vermelho",
    "Remição pendente: atestado com dias, sem registro de peticionamento, emitido depois da última decisão de remição",
    "Situação 'Atestado sem peticionamento' (vermelho); ficha 80 / RSPE 30; o atestado de 50 dias entra no pedido.",
    "RSPE: remição de 30 dias em 10/02/2025 (atestado nº 010/2025, peticionado, 90 trabalhados). Atestado nº 088/2026, emitido em 15/08/2026, "
    "01/02 a 31/07/2026, 150 trabalhados -> 50 dias, sem registro de peticionamento. Depois da última decisão (10/02/2025) nada foi apreciado: "
    "o atestado de 50 dias é remição pendente certa (LEP, arts. 126, § 8º, e 129). Total 30 + 50 = 80 x 30.",
    RS(k, [REM(30, "10/02/2025", "31/12/2024")]),
    [C("fd_sit", "contem", "Atestado sem peticionamento"), C("fd_cor", "eq", "vermelho"), C("fd_remidos", "eq", "80 / 30"),
     C("fd_fund", "contem", "088/2026")],
    ficha(k, [("01.09.2024", INI("CERAMICA", "5/2024")), ("31.12.2024", FIM("CERAMICA", "9/2024")),
              ("10.01.2025", AT("010/2025", "01/09/2024", "31/12/2024", 90, 30, PET)),
              ("01.02.2026", INI("CERAMICA", "2/2026")), ("31.07.2026", FIM("CERAMICA", "30/2026")),
              ("15.08.2026", AT("088/2026", "01/02/2026", "31/07/2026", 150, 50))]))

k = 5004
add(k, "Atestado com remição abaixo de 1/3 (150 trabalhados, 40 remidos): pede-se a proporção legal",
    "Atestado que declara menos que 1/3 dos dias trabalhados",
    "Ponto 'abaixo de 1/3'; a fundamentação pede 50 dias (150 ÷ 3), não 40.",
    "Atestado nº 090/2026 (02/03 a 29/08/2026), 150 trabalhados e 40 remidos, peticionado. A lei dá 1 dia por 3 trabalhados: 150 ÷ 3 = 50 "
    "(LEP, art. 126, § 1º, II). O atestado declara 10 a menos; não há falta nem jornada reduzida registrada: requer-se 50.",
    RS(k),
    [C("fd_novo", "contem", "abaixo de 1/3"), C("fd_fund", "contem", "50 dias")],
    ficha(k, [("02.03.2026", INI("PADARIA", "4/2026")), ("29.08.2026", FIM("PADARIA", "9/2026")),
              ("02.09.2026", AT("090/2026", "02/03/2026", "29/08/2026", 150, 40, PET))]))

k = 5005
add(k, "Atestado com remição acima de 1/3 (75 trabalhados, 40 remidos): aviso",
    "Atestado que declara mais que 1/3 dos dias trabalhados",
    "Aviso 'acima de 1/3' para conferir (horas extras ou erro de digitação).",
    "Atestado nº 091/2026, 75 trabalhados e 40 remidos. 75 ÷ 3 = 25 (LEP, art. 126, § 1º, II); 40 só se justifica com horas além da "
    "jornada (LEP, art. 33; o STJ admite computar as horas excedentes). Conferir o atestado.",
    RS(k),
    [C("fd_novo", "contem", "acima de 1/3")],
    ficha(k, [("01.06.2026", INI("LIMPEZA", "4/2026")), ("31.08.2026", FIM("LIMPEZA", "9/2026")),
              ("05.09.2026", AT("091/2026", "01/06/2026", "31/08/2026", 75, 40, PET))]))

# ================================================================= 2. Jornada: contagem dos dias sem atestado
k = 5006
t = uteis("01/07/2026", "31/07/2026", dias=(0, 1, 2, 3, 4))
add(k, "Trabalho sem atestado com jornada de segunda a sexta: %d dias" % t,
    "Jornada registrada 'segunda a sexta': o dia de sábado não entra na estimativa",
    "Pedir atestado: Limpeza, 01/07 a 31/07/2026, ≈ %d dias trabalhados (≈ %s de remição)." % (t, nf(t / 3)),
    "Julho/2026, segunda a sexta, sem feriado no mês: %d dias -> %d ÷ 3 = %s (LEP, art. 126, § 1º, II; art. 33)." % (t, t, nf(t / 3)),
    RS(k),
    [C("fd_sit", "contem", "Pedir atestado"), C("fd_atestar", "eq", "Sim"), C("fd_novo", "contem", "≈ %s" % nf(t / 3))],
    ficha(k, [("01.07.2026", INI("LIMPEZA", "5/2026") + " Jornada de segunda a sexta-feira."), ("31.07.2026", FIM("LIMPEZA", "6/2026"))]))

k = 5007
t = len([d for d in range(1, 32, 2)])
add(k, "Trabalho sem atestado em escala 12x36: %d dias" % t,
    "Jornada 12x36: dia sim, dia não, a partir do início",
    "Pedir atestado: Portaria, 01/07 a 31/07/2026, ≈ %d dias trabalhados (≈ %s de remição)." % (t, nf(t / 3)),
    "Escala 12x36 de 01/07 a 31/07/2026: dias 1, 3, 5, ..., 31 = %d plantões -> %d ÷ 3 = %s (LEP, art. 126, § 1º, II)." % (t, t, nf(t / 3)),
    RS(k),
    [C("fd_sit", "contem", "Pedir atestado"), C("fd_novo", "contem", "≈ %s" % nf(t / 3))],
    ficha(k, [("01.07.2026", INI("PORTARIA", "7/2026") + " Escala de 12x36."), ("31.07.2026", FIM("PORTARIA", "8/2026"))]))

k = 5008
t = uteis("01/08/2026", "31/08/2026")
add(k, "Trabalho sem atestado sem jornada registrada (segunda a sábado): %d dias" % t,
    "Sem jornada na ficha: estimativa de segunda a sábado",
    "Pedir atestado: Horta, 01/08 a 31/08/2026, ≈ %d dias trabalhados (≈ %s de remição)." % (t, nf(t / 3)),
    "Agosto/2026: 31 dias - 5 domingos = %d (sem feriado) -> %s (LEP, art. 126, § 1º, II; art. 33: descanso aos domingos)." % (t, nf(t / 3)),
    RS(k),
    [C("fd_sit", "contem", "Pedir atestado"), C("fd_novo", "contem", "≈ %s" % nf(t / 3))],
    ficha(k, [("01.08.2026", INI("HORTA", "8/2026")), ("31.08.2026", FIM("HORTA", "9/2026"))]))

k = 5009
t = uteis("03/08/2026", "29/08/2026", fora=[("10/08/2026", "19/08/2026")])
add(k, "Isolamento de 10 dias descontado do trabalho sem atestado",
    "Dias de isolamento em cela disciplinar não são dias de trabalho",
    "Pedir atestado: Lavanderia, ≈ %d dias trabalhados (≈ %s de remição)." % (t, nf(t / 3)),
    "Lavanderia de 03/08 a 29/08/2026: %d dias de segunda a sábado; isolamento de 10 dias desde 10/08 (10 a 19/08, %d dias úteis) -> %d "
    "-> %s." % (uteis("03/08/2026", "29/08/2026"), uteis("10/08/2026", "19/08/2026"), t, nf(t / 3)),
    RS(k),
    [C("fd_novo", "contem", "≈ %s" % nf(t / 3))],
    ficha(k, [("03.08.2026", INI("LAVANDERIA", "11/2026")), ("10.08.2026", "CONSELHO DISCIPLINAR: ISOLADO PREVENTIVAMENTE EM CELA DISCIPLINAR, POR 10 DIAS."),
              ("29.08.2026", FIM("LAVANDERIA", "12/2026"))]))

k = 5010
t = uteis("06/04/2026", "30/05/2026")
add(k, "Pedir atestado: trabalho encerrado sem atestado e sem remição no RSPE",
    "Pedir atestado à unidade (LEP, art. 129)",
    "Situação 'Pedir atestado' (amarelo); trabalho a atestar 'Sim'; ≈ %d dias trabalhados (≈ %s de remição)." % (t, nf(t / 3)),
    "Marcenaria de 06/04 a 30/05/2026: segunda a sábado sem 21/04 e 01/05 = %d -> %s. O RSPE não tem remição que o explique." % (t, nf(t / 3)),
    RS(k),
    [C("fd_sit", "contem", "Pedir atestado"), C("fd_cor", "eq", "amarelo"), C("fd_atestar", "eq", "Sim"), C("fd_novo", "contem", "≈ %s" % nf(t / 3))],
    ficha(k, [("06.04.2026", INI("MARCENARIA", "13/2026")), ("30.05.2026", FIM("MARCENARIA", "14/2026"))]))

# ================================================================= 3. Saldo de remição sem documento: do mais próximo ao mais antigo
k = 5011
ini_cob = recua("30/11/2025", 60)
resto = uteis("01/07/2025", "%s" % F(D(ini_cob) - timedelta(days=1)))
add(k, "Remição sem documento cobre o trabalho mais próximo dela; o resto é pedido",
    "Remição do RSPE sem atestado na ficha cobre primeiro o trabalho mais próximo",
    "'Pode já estar remido': Lavanderia, %s a 29/11/2025 (30/11 é domingo; ≈ 60 dias trabalhados, 20 de remição); 'Pedir atestado': 01/07/2025 a %s "
    "(≈ %d dias, ≈ %s de remição)." % (ini_cob, F(D(ini_cob) - timedelta(days=1)), resto, nf(resto / 3)),
    "Lavanderia 01/07 a 30/11/2025, sem atestado. RSPE: 20 dias (decisão 15/12/2025, referência 30/11/2025), sem documento: 20 x 3 = 60 dias "
    "de trabalho contados para trás desde 30/11/2025 (segunda a sábado; sem 11/10, 15/11 e 20/11) -> começa em %s. Sobram %d dias "
    "(01/07 a %s) -> %s. Política: cobre primeiro o trabalho mais próximo." % (ini_cob, resto, F(D(ini_cob) - timedelta(days=1)), nf(resto / 3)),
    RS(k, [REM(20, "15/12/2025", "30/11/2025")]),
    [C("fd_novo", "contem", ["Pode já estar remido", "%s a 29/11/2025" % ini_cob]), C("fd_novo", "contem", "≈ %s" % nf(resto / 3)),
     C("fd_sit", "contem", "Pedir atestado")],
    ficha(k, [("01.07.2025", INI("LAVANDERIA", "20/2025")), ("30.11.2025", FIM("LAVANDERIA", "31/2025"))]))

k = 5012
pad = uteis("01/10/2025", "31/12/2025")
fax = uteis("04/08/2025", "30/09/2025")
add(k, "Dois trabalhos sem atestado: a remição sem documento cobre o mais recente (Padaria); a Faxina é pedida",
    "Remição sem documento: cobre o vínculo mais próximo da referência, não o mais antigo",
    "Padaria (01/10 a 31/12/2025) 'pode já estar remido'; Faxina (04/08 a 30/09/2025) em 'Pedir atestado', ≈ %d dias (≈ %s)." % (fax, nf(fax / 3)),
    "RSPE: 25 dias sem documento (decisão 20/01/2026, referência 31/12/2025) -> 75 dias de trabalho para trás. Padaria, segunda a sábado "
    "sem 11/10, 15/11, 20/11 e 25/12: %d dias = cobre a Padaria inteira. Faxina: %d dias -> %s, a pedir." % (pad, fax, nf(fax / 3)),
    RS(k, [REM(25, "20/01/2026", "31/12/2025")]),
    [C("fd_novo", "contem", ["Pode já estar remido", "Padaria"]), C("fd_novo", "regex", r"Pedir atestado[^\"]*Faxina"),
     C("fd_novo", "contem", "≈ %s" % nf(fax / 3))],
    ficha(k, [("04.08.2025", INI("FAXINA", "21/2025")), ("30.09.2025", FIM("FAXINA", "22/2025")),
              ("01.10.2025", INI("PADARIA", "23/2025")), ("31.12.2025", FIM("PADARIA", "24/2025"))]))

# ================================================================= 4. Vínculos: sem baixa, em curso, acompanhar
k = 5013
add(k, "Vínculo sem baixa: trabalho encerrado só pela transferência",
    "Trabalho que a ficha só encerra pela saída da unidade, depois do último atestado",
    "Trecho de 01/09/2024 a 30/06/2025 em 'Vínculo sem baixa: conferir' (não 'Pedir atestado').",
    "Horta de 02/03/2024 até a transferência em 30/06/2025, sem baixa no setor. Atestado nº 041/2024 (02/03 a 31/08/2024, 150 trab., 50) "
    "remido em 15/10/2024. Depois de 31/08/2024 não há prova de que o trabalho seguiu (LEP, art. 129): conferir com a unidade antes de pedir.",
    RS(k, [REM(50, "15/10/2024", "31/08/2024")]),
    [C("fd_novo", "contem", "Vínculo sem baixa"), C("fd_novo", "nao_contem", "Pedir atestado: trabalho em Horta")],
    ficha(k, [("02.03.2024", INI("HORTA", "1/2024")), ("10.09.2024", AT("041/2024", "02/03/2024", "31/08/2024", 150, 50, PET)),
              ("30.06.2025", "Saída da Unidade Penal: %s, Destino: PRESIDIO SIMULADO DE DOURADOS, motivo: TRANSFERÊNCIA." % UN)]))

k = 5014
t = uteis("03/08/2026", "05/10/2026")
add(k, "Trabalho em curso há 70 dias, sem atestado: acompanhar",
    "Trabalho iniciado há menos de 90 dias, em curso: acompanhar (o atestado é periódico)",
    "Situação 'Acompanhar atestado' (cinza); não entra no pedido. Muda com o tempo: a partir de 01/11/2026 (90 dias) passa a 'Pedir atestado'.",
    "Padaria desde 03/08/2026, em curso na impressão (05/10/2026). Hoje 12/10/2026: 71 dias desde o início. Até a impressão: %d dias "
    "(segunda a sábado, sem 07/09) -> %s. Prática de atestados periódicos: acompanhar." % (t, nf(t / 3)),
    RS(k),
    [C("fd_sit", "eq", "Acompanhar atestado"), C("fd_cor", "eq", "cinza")],
    ficha(k, [("03.08.2026", INI("PADARIA", "30/2026"))]))

k = 5015
t = uteis("02/03/2026", "05/10/2026")
add(k, "Trabalho em curso há mais de 90 dias sem atestado: pedir",
    "Trabalho em curso desde março: pedir o atestado até a impressão da ficha",
    "Situação 'Pedir atestado' (amarelo); texto 'em curso'; ≈ %d dias trabalhados até 05/10/2026 (≈ %s)." % (t, nf(t / 3)),
    "Cozinha desde 02/03/2026, em curso. Segunda a sábado de 02/03 a 05/10/2026, sem 03/04, 21/04, 01/05 e 07/09: %d -> %s (LEP, art. 129)." % (t, nf(t / 3)),
    RS(k),
    [C("fd_sit", "contem", "Pedir atestado"), C("fd_novo", "contem", "em curso"), C("fd_novo", "contem", "≈ %s" % nf(t / 3))],
    ficha(k, [("02.03.2026", INI("COZINHA", "12/2026"))]))

# ================================================================= 5. Atestado × RSPE: provável, mesmo valor, sem correspondência
def caso_valor(k, emis, dec, titulo, sit, esp, chk, conta_extra):
    add(k, titulo, sit, esp,
        "Atestado nº 0%d/2023 (01/06 a 30/11/2023, 150 trab., 50 remidos), emitido e peticionado em %s. RSPE: remição de 50 dias decidida em "
        "%s (%d dias depois da emissão). %s" % (k - 5000, emis, dec, (D(dec) - D(emis)).days, conta_extra),
        RS(k, [REM(50, dec, dec)]), chk,
        ficha(k, [("01.06.2023", INI("HORTA", "5/2023")), ("30.11.2023", FIM("HORTA", "9/2023")),
                  (emis.replace("/", "."), AT("0%d/2023" % (k - 5000), "01/06/2023", "30/11/2023", 150, 50, PET))]))


caso_valor(5016, "05/12/2023", F(D("05/12/2023") + timedelta(days=180)), "Mesmo valor decidido 180 dias depois: provavelmente remido",
           "Limite de 180 dias da indicação 'provavelmente remido' (dia 180)",
           "Documento 'Provavelmente remido em 02/06/2024 (mesmo valor): conferir'; situação 'Em ordem'.",
           [C("fd_novo", "contem", "Provavelmente remido em 02/06/2024"), C("fd_sit", "eq", "Em ordem")],
           "Política: até 180 dias = provavelmente remido.")
caso_valor(5017, "05/12/2023", F(D("05/12/2023") + timedelta(days=181)), "Mesmo valor decidido 181 dias depois: 'mesmo valor decidido em ...: conferir'",
           "Passou de 180 dias: não é mais 'provavelmente remido'",
           "Documento 'Mesmo valor decidido em 03/06/2024 (mais de 180 dias depois da emissão): conferir'; sem 'Provavelmente remido'.",
           [C("fd_novo", "contem", "Mesmo valor decidido em 03/06/2024"), C("fd_novo", "nao_contem", "Provavelmente remido em 03/06/2024")],
           "Política: de 180 dias a 3 anos = 'mesmo valor decidido em ...: conferir'.")
caso_valor(5018, "05/12/2023", "20/10/2025", "Mesmo valor decidido quase 2 anos depois: 'mesmo valor ... conferir'",
           "Mesmo valor decidido entre 180 dias e 3 anos",
           "Documento 'Mesmo valor decidido em 20/10/2025 (mais de 180 dias depois da emissão): conferir'.",
           [C("fd_novo", "contem", "Mesmo valor decidido em 20/10/2025")],
           "685 dias: entre 180 dias e 3 anos.")
caso_valor(5019, "05/12/2023", "01/10/2026",
           "Mesmo valor decidido mais de 1.000 dias depois mas antes de 3 anos",
           "Mesmo valor decidido perto do limite de 3 anos (1.031 dias)",
           "Documento 'Mesmo valor decidido em 01/10/2026 (mais de 180 dias depois da emissão): conferir'.",
           [C("fd_novo", "contem", "Mesmo valor decidido em 01/10/2026")],
           "1.031 dias <= 1.095 (3 anos).")

k = 5020
add(k, "Atestado sem correspondência: RSPE com valor diferente, ficha a mais",
    "Atestado peticionado sem remição correspondente no RSPE (valores diferentes)",
    "Situação 'Verificar remição' (amarelo); ficha 50 / RSPE 25 (diferença +25, a conferir nos autos); sem 'Provavelmente remido'.",
    "Atestado nº 033/2024 (01/07/2023 a 31/12/2023, 150 trab., 50 remidos), peticionado em 10/01/2024. RSPE: uma remição de 25 dias em "
    "15/06/2024. Nenhuma remição de 50. Diferença 50 - 25 = +25 > 3: verificar se o atestado foi apreciado (LEP, art. 126, § 8º).",
    RS(k, [REM(25, "15/06/2024", "15/06/2024")]),
    [C("fd_sit", "contem", "Verificar remição"), C("fd_remidos", "eq", "50 / 25"), C("fd_novo", "nao_contem", "Provavelmente remido")],
    ficha(k, [("01.07.2023", INI("COZINHA", "7/2023")), ("31.12.2023", FIM("COZINHA", "9/2023")),
              ("10.01.2024", AT("033/2024", "01/07/2023", "31/12/2023", 150, 50, PET))]))

k = 5021
add(k, "Soma de dois atestados decidida numa remição só",
    "Dois atestados apreciados juntos: remição = soma",
    "Os dois atestados 'Provavelmente remido em 15/07/2025 (soma ...)'; situação 'Em ordem'; ficha 49 / RSPE 49.",
    "Atestados nº 020/2025 (72 trab., 24 dias, emitido 10/03/2025) e nº 044/2025 (25 dias, emitido 05/06/2025), peticionados. RSPE: 49 dias em "
    "15/07/2025 = 24 + 25. Totais iguais.",
    RS(k, [REM(49, "15/07/2025", "15/07/2025")]),
    [C("fd_novo", "contem", "soma com"), C("fd_sit", "eq", "Em ordem"), C("fd_remidos", "eq", "49 / 49")],
    ficha(k, [("01.12.2024", INI("ARTESANATO", "1/2024")), ("31.05.2025", FIM("ARTESANATO", "9/2025")),
              ("10.03.2025", AT("020/2025", "01/12/2024", "28/02/2025", 72, 24, PET)),
              ("05.06.2025", AT("044/2025", "01/03/2025", "31/05/2025", 75, 25, PET))]))

k = 5022
add(k, "Atestado cumulativo contém o anterior: não se soma em dobro",
    "Atestado do ano inteiro repete o do semestre (mesmo trabalho)",
    "Ficha 100 / RSPE 100 (o atestado do semestre não se soma); situação 'Em ordem'; documento 'Contido no atestado nº 015/2026'.",
    "Atestados nº 060/2025 (02/01 a 30/06/2025, 50) e nº 015/2026 (02/01 a 31/12/2025, 100), do mesmo setor. O segundo inclui o primeiro: "
    "o mesmo dia não remite duas vezes (LEP, art. 126, § 1º, II). Comprovado 100; RSPE 100 (10/03/2026).",
    RS(k, [REM(100, "10/03/2026", "31/12/2025")]),
    [C("fd_remidos", "eq", "100 / 100"), C("fd_sit", "eq", "Em ordem"), C("fd_novo", "contem", "Contido no atestado nº 015/2026")],
    ficha(k, [("02.01.2025", INI("FABRICA DE BOLAS", "1/2025")), ("31.12.2025", FIM("FABRICA DE BOLAS", "50/2025")),
              ("10.07.2025", AT("060/2025", "02/01/2025", "30/06/2025", 150, 50, PET)),
              ("10.01.2026", AT("015/2026", "02/01/2025", "31/12/2025", 300, 100, PET))]))

k = 5023
add(k, "Atestado protocolado dias depois da emissão: peticionado (não vermelho)",
    "Peticionamento registrado em lançamento posterior com o mesmo número",
    "Documento 'peticionado em 02/09/2026'; situação 'Verificar remição' (amarelo), não vermelho; ficha 30 / RSPE 0.",
    "Atestado nº 077/2026 emitido em 25/08/2026 sem menção de protocolo; em 02/09/2026 a ficha registra 'ATESTADO Nº 077/2026 PROTOCOLADO NO SEEU'. "
    "O documento foi levado aos autos (LEP, art. 129) e é posterior à última remição: provável pendência, não falta de peticionamento.",
    RS(k),
    [C("fd_novo", "contem", "peticionado em 02/09/2026"), C("fd_cor", "eq", "amarelo"), C("fd_remidos", "eq", "30 / 0")],
    ficha(k, [("04.05.2026", INI("JARDINAGEM", "5/2026")), ("15.08.2026", FIM("JARDINAGEM", "9/2026")),
              ("25.08.2026", AT("077/2026", "04/05/2026", "15/08/2026", 90, 30)),
              ("02.09.2026", "ATESTADO DE TRABALHO Nº 077/2026 PROTOCOLADO NO SEEU.")]))

k = 5024
add(k, "Atestado enviado à Defensoria, sem protocolo, anterior à última remição",
    "Atestado encaminhado à Defensoria sem registro de protocolo nos autos",
    "Ponto 'enviado à Defensoria, sem registro de protocolo'; situação amarela 'Verificar remição' (ficha 40 / RSPE 30).",
    "Atestado nº 051/2025 (40 dias) 'encaminhado à Defensoria Pública' em 10/02/2025; RSPE: remição de 30 dias em 10/06/2025 (valor "
    "diferente). Diferença +10: conferir se a Defensoria juntou o atestado (LEP, art. 129).",
    RS(k, [REM(30, "10/06/2025", "10/06/2025")]),
    [C("fd_novo", "contem", "Defensoria"), C("fd_sit", "contem", "Verificar remição")],
    ficha(k, [("02.09.2024", INI("MANUTENCAO", "3/2024")), ("31.01.2025", FIM("MANUTENCAO", "1/2025")),
              ("10.02.2025", AT("051/2025", "02/09/2024", "31/01/2025", 120, 40, ", ENCAMINHADO À DEFENSORIA PÚBLICA"))]))

k = 5025
add(k, "RSPE maior que a ficha",
    "O RSPE concedeu mais do que a ficha comprova",
    "Situação 'RSPE maior que a ficha (75 × 25)' (cinza); nada a requerer pela diferença.",
    "Ficha: atestado nº 012/2024 (75 trab., 25 dias), remido. RSPE: 25 + 50 = 75 dias (a remição de 50 pode vir de estudo ou de atestado fora da "
    "ficha). 25 - 75 = -50: nada a pedir por esta conta.",
    RS(k, [REM(25, "20/03/2024", "29/02/2024"), REM(50, "20/09/2025", "20/09/2025")]),
    [C("fd_sit", "contem", "RSPE maior que a ficha (75 × 25)"), C("fd_cor", "eq", "cinza")],
    ficha(k, [("01.12.2023", INI("COZINHA", "1/2023")), ("29.02.2024", FIM("COZINHA", "2/2024")),
              ("05.03.2024", AT("012/2024", "01/12/2023", "29/02/2024", 75, 25, PET))]))

k = 5026
add(k, "Sem ficha importada", "Assistido sem ficha do SIAPEN",
    "Situação 'Sem ficha' (cinza).", "Sem ficha não há comparação.",
    RS(k, [REM(40, "10/05/2025", "30/04/2025")]),
    [C("fd_sit", "eq", "Sem ficha"), C("fd_cor", "eq", "cinza")], None)

k = 5027
add(k, "Remição indeferida no RSPE não conta como concedida",
    "Incidente de remição indeferido",
    "Ficha 20 / RSPE 20 (a remição indeferida de 40 dias não entra); situação 'Em ordem'.",
    "RSPE: remição de 40 dias INDEFERIDA (10/03/2025) e de 20 dias concedida (10/06/2025). Só a declarada pelo juiz é remição (LEP, "
    "art. 126, § 8º). Atestado nº 030/2025 (60 trab., 20) emitido em 20/05/2025, peticionado.",
    RS(k, [REM(40, "10/03/2025", "10/03/2025", sit="INDEFERIDO"), REM(20, "10/06/2025", "30/04/2025")]),
    [C("fd_remidos", "eq", "20 / 20"), C("fd_sit", "eq", "Em ordem")],
    ficha(k, [("01.02.2025", INI("HORTA", "2/2025")), ("30.04.2025", FIM("HORTA", "3/2025")),
              ("20.05.2025", AT("030/2025", "01/02/2025", "30/04/2025", 60, 20, PET))]))

k = 5028
add(k, "Homologado marcado na conferência: o atestado sai dos pontos e continua no total",
    "✓ Homologado: o defensor confere nos autos e marca o documento",
    "Depois da marca: a linha deixa de ser vermelha; ficha 49 / RSPE 0 continua; documento 'Homologado (marcado na conferência)'.",
    "Atestado nº 099/2026 (147 trab., 49 dias), sem peticionamento, posterior (vermelho). O operador confere a decisão nos autos e marca ✓: deixa de ser "
    "pendência, mas continua comprovado.",
    RS(k),
    [C("fd_cor", "nao_contem", "vermelho"), C("fd_novo", "contem", "Homologado"), C("fd_remidos", "eq", "49 / 0")],
    ficha(k, [("05.01.2026", INI("CONFECCAO", "1/2026")), ("30.06.2026", FIM("CONFECCAO", "2/2026")),
              ("10.07.2026", AT("099/2026", "05/01/2026", "30/06/2026", 147, 49))]),
    acoes=[{"metodo": "fd_conferir", "args": [pid(k), "fd:at:099/2026:10.07.2026", True]}])

k = 5029
add(k, "Remição no período do atestado pendente: pede-se só a diferença",
    "Atestado anual pendente e o RSPE com remição sem documento de parte do mesmo período",
    "Ponto 'Remição no período'; pedir ≈ 39 (99 - 60), conferindo a remição de 20/08/2025 antes.",
    "Atestado nº 050/2026 (02/01 a 31/12/2025, 297 trab., 99 remidos), peticionado em 20/01/2026. RSPE: 60 dias em 20/08/2025, ref. "
    "30/06/2025, sem documento na ficha (provável atestado do 1º semestre). O mesmo dia não remite duas vezes: pedir 99 - 60 = 39.",
    RS(k, [REM(60, "20/08/2025", "30/06/2025")]),
    [C("fd_novo", "contem", "39"), C("fd_novo", "contem", "Remição no período")],
    ficha(k, [("02.01.2025", INI("FABRICA", "1/2025")), ("31.12.2025", FIM("FABRICA", "70/2025")),
              ("20.01.2026", AT("050/2026", "02/01/2025", "31/12/2025", 297, 99, PET))]))

# ================================================================= 6. Estudo
k = 5030
add(k, "Atestado de horas-aula (180 h): 15 dias",
    "Estudo: 12 horas = 1 dia",
    "Ficha 15 / RSPE 0; estudo a requerer 'Sim'.",
    "Atestado de horas-aula nº 12/2026, remir 180 horas: 180 ÷ 12 = 15 dias (LEP, art. 126, § 1º, I). Sem remição no RSPE.",
    RS(k),
    [C("fd_remidos", "eq", "15 / 0"), C("fd_estudo", "eq", "Sim")],
    ficha(k, [("10.07.2026", "Nesta data foi emitido atestado de horas aulas nº 12/2026, remir (180) cento e oitenta horas aulas, peticionado no SEEU.")]))

k = 5031
add(k, "Certidão de frequência sem carga horária: fora da soma",
    "Matrícula e certidão do semestre peticionada, sem horas no texto",
    "Certidão 'Sem valor na ficha (fora da comparação)'; ficha 0 / RSPE 0; estudo a requerer 'Sim' (certidão posterior à última remição).",
    "Matrícula EJA de 03/02/2025 a 30/06/2025; certidão do 1º semestre de 2025 peticionada em 05/08/2025, sem carga horária. Sem as horas "
    "não há valor certo (LEP, art. 126, § 1º, I: 12 h = 1 dia).",
    RS(k),
    [C("fd_novo", "contem", "Sem valor na ficha"), C("fd_remidos", "eq", "0 / 0"), C("fd_estudo", "eq", "Sim")],
    ficha(k, [("03.02.2025", "EDUCAÇÃO: Matrículou-se na Série: EJA ENSINO FUNDAMENTAL Turma: B Período: Vespertino"),
              ("30.06.2025", "EDUCAÇÃO: Nesta data o interno deixa de estudar por opção própria."),
              ("05.08.2025", "EDUCAÇÃO: Peticionado Certidão de Frequência Escolar referente ao 1º semestre de 2025, no Sistema SEEU nos Autos Nº %s." % pid(k))]))

k = 5032
t = letivos("03/08/2026", "30/09/2026")
add(k, "Estudo sem certidão: estimativa de %d dias letivos x 4 h ÷ 12" % t,
    "Matrícula com frequência e sem certidão: estimar e pedir a certidão",
    "Ponto 'Estudo sem certidão' com ≈ %d dias letivos × 4 h = %d h ≈ %s dias; estudo a requerer 'Sim'." % (t, t * 4, nf(t * 4 / 12)),
    "Matrícula EJA de 03/08/2026 a 30/09/2026 (deixou de estudar). Segunda a sexta sem 07/09: %d dias letivos. Média de 4 h por dia (LDB, "
    "art. 24, I: 800 h em 200 dias) -> %d h ÷ 12 = %s dias (LEP, art. 126, § 1º, I). Estimativa: pedir a certidão." % (t, t * 4, nf(t * 4 / 12)),
    RS(k),
    [C("fd_novo", "contem", "%d h" % (t * 4)), C("fd_estudo", "eq", "Sim")],
    ficha(k, [("03.08.2026", "EDUCAÇÃO: Matrículou-se na Série: EJA ENSINO MÉDIO Turma: A Período: Matutino"),
              ("30.09.2026", "EDUCAÇÃO: Nesta data o interno deixa de estudar por opção própria.")]))

k = 5033
add(k, "Matrícula cancelada sem matrícula registrada, na saída da unidade",
    "Cancelamento de matrícula sem a matrícula na ficha",
    "Ponto 'Estudo a conferir': pedir a certidão de frequência escolar à unidade de origem.",
    "A ficha registra 'Cancelamento de matrícula - saída do presídio' em 12/03/2025, no dia da transferência, sem a matrícula. Houve estudo "
    "que a ficha não mostra: pedir a certidão (LEP, art. 126, § 1º, I; art. 129).",
    RS(k),
    [C("fd_novo", "contem", "certidão de frequência escolar")],
    ficha(k, [("12.03.2025", "EDUCAÇÃO: Cancelamento de matrícula - saída do presídio."),
              ("12.03.2025", "Saída da Unidade Penal: %s, Destino: PRESIDIO SIMULADO DE DOURADOS, motivo: TRANSFERÊNCIA." % UN)]))

k = 5034
add(k, "Matrícula aberta há mais de 1 ano sem registro escolar: não estima",
    "Matrícula sem nenhum registro de frequência depois",
    "Sem estimativa de estudo; estudo a requerer 'Não'.",
    "Única anotação: matrícula em 03/03/2025. Sem frequência registrada em 19 meses não há prova de estudo (LEP, art. 126, § 1º, I exige "
    "frequência): não se estima remição.",
    RS(k),
    [C("fd_estudo", "eq", "Não"), C("fd_novo", "nao_contem", "Estudo sem certidão")],
    ficha(k, [("03.03.2025", "EDUCAÇÃO: Matrículou-se na Série: EJA ENSINO FUNDAMENTAL Turma: C Período: Noturno")]))

k = 5035
add(k, "Certidões de dois semestres e uma remição pequena: provável pendência",
    "Duas certidões peticionadas e uma só remição de valor bem menor",
    "Ponto amarelo 'Provável pendência' de certidão; situação 'Conferir pontos' (amarelo).",
    "Matrícula desde 03/02/2025; certidões do 1º semestre (05/08/2025) e do 2º semestre de 2025 (10/02/2026). Cada semestre tem ~100 dias "
    "letivos (≈ 33 dias de remição a 4 h/dia). RSPE: uma remição de 15 dias em 25/02/2026 - menos que um semestre: provavelmente uma "
    "certidão não foi apreciada.",
    RS(k, [REM(15, "25/02/2026", "25/02/2026")]),
    [C("fd_novo", "contem", "Provável pendência"), C("fd_cor", "eq", "amarelo")],
    ficha(k, [("03.02.2025", "EDUCAÇÃO: Matrículou-se na Série: EJA ENSINO MÉDIO Turma: A Período: Matutino"),
              ("05.08.2025", "EDUCAÇÃO: Peticionado Certidão de Frequência Escolar referente ao 1º semestre de 2025, no Sistema SEEU."),
              ("10.02.2026", "EDUCAÇÃO: Peticionado Certidão de Frequência Escolar referente ao 2º semestre de 2025, no Sistema SEEU."),
              ("01.10.2026", "EDUCAÇÃO: Frequência escolar regular no mês de setembro de 2026.")]))

# ================================================================= 7. Exames
k = 5036
add(k, "ENCCEJA com conclusão do fundamental certificada e remição de 177 dias",
    "Exame com conclusão de etapa: 1.600 h ÷ 12 = 133,33 + 1/3 = 177,78",
    "Documento 'Possivelmente remido em 15/06/2025' (exame ligado à remição de 177 dias); conclusão certificada reconhecida.",
    "ENCCEJA 2024, certificado de conclusão do ensino fundamental registrado em 15/04/2025. Res. CNJ 391/2021, art. 3º, p. ú.: 1.600 h ÷ 12 "
    "= 133,33; com a conclusão, + 1/3 (LEP, art. 126, § 5º) = 177,78. RSPE: 177 dias em 15/06/2025 (61 dias depois).",
    RS(k, [REM(177, "15/06/2025", "15/06/2025")]),
    [C("fd_novo", "contem", "Possivelmente remido em 15/06/2025"), C("fd_novo", "regex", r"conclus\w+ certificad")],
    ficha(k, [("15.04.2025", "CERTIFICADO DE CONCLUSÃO DO ENSINO FUNDAMENTAL - ENCCEJA 2024.")]))

k = 5037
add(k, "ENCCEJA: certificado de conclusão registrado como peticionado",
    "Conclusão certificada (+1/3) também quando o lançamento diz que o certificado foi peticionado",
    "Exame ENCCEJA 2024 com conclusão certificada; documento 'Possivelmente remido em 10/07/2025'.",
    "'Peticionado o certificado de conclusão do ensino fundamental - ENCCEJA 2024' (20/05/2025): o texto registra o certificado de conclusão; "
    "o peticionamento não o desfaz (LEP, art. 126, § 5º). RSPE: 177 dias em 10/07/2025.",
    RS(k, [REM(177, "10/07/2025", "10/07/2025")]),
    [C("fd_novo", "contem", "Possivelmente remido em 10/07/2025"), C("fd_novo", "regex", r"conclus\w+ certificad")],
    ficha(k, [("20.05.2025", "EDUCAÇÃO: Peticionado o certificado de conclusão do ensino fundamental - ENCCEJA 2024, no sistema SEEU.")]))

k = 5038
add(k, "ENEM com remição de 40 dias (2 áreas)",
    "ENEM: 1.200 h ÷ 12 = 100 dias, 20 por área",
    "Documento 'Possivelmente remido em 20/03/2026 (40 dias): conferir as áreas'; situação sem amarelo pelo exame.",
    "ENEM 2025 peticionado em 20/02/2026. Res. CNJ 391/2021, art. 3º: ensino médio 1.200 h ÷ 12 = 100 dias, 5 áreas = 20 por área. "
    "RSPE: 40 dias em 20/03/2026 = 2 áreas.",
    RS(k, [REM(40, "20/03/2026", "20/03/2026")]),
    [C("fd_novo", "contem", "Possivelmente remido em 20/03/2026")],
    ficha(k, [("20.02.2026", "PETICIONADO CERTIFICADO DO ENEM 2025 NO SISTEMA SEEU")]))

k = 5039
add(k, "ENEM peticionado sem remição no RSPE",
    "Exame sem decisão: conferir se foi remido e com quantas áreas",
    "Ponto amarelo 'A conferir' do exame; estudo a requerer 'Sim'; situação 'Conferir pontos'.",
    "ENEM 2025 peticionado em 15/03/2026; o RSPE não tem remição. Valor depende das áreas aprovadas (Res. CNJ 391/2021, art. 3º).",
    RS(k),
    [C("fd_estudo", "eq", "Sim"), C("fd_sit", "contem", "Conferir pontos"), C("fd_novo", "contem", "ENEM 2025")],
    ficha(k, [("15.03.2026", "PETICIONADO CERTIFICADO DO ENEM 2025 NO SISTEMA SEEU")]))

# ================================================================= 8. Leitura
k = 5040
add(k, "Leitura de 3 obras peticionada: 12 dias",
    "Leitura: 4 dias por obra",
    "Ficha 12 / RSPE 0; estudo a requerer 'Sim'.",
    "Relatórios de 06, 07 e 08/2026 peticionados em 10/09/2026, um livro por mês: 3 obras x 4 = 12 dias (Res. CNJ 391/2021, art. 5º).",
    RS(k),
    [C("fd_remidos", "eq", "12 / 0"), C("fd_estudo", "eq", "Sim")],
    ficha(k, [("10.09.2026", "EDUCAÇÃO: Peticionado relatório de leitura referente aos meses 06, 07 e 08 de 2026, no sistema SEEU.")]))

k = 5041
add(k, "Leitura remida a menor (2 obras, RSPE 4 dias)",
    "Leitura de 8 dias e remição seguinte de 4",
    "Aviso 'remida a menor?' (RSPE 4 dias em 25/04/2026).",
    "Relatório de 01 e 02/2026, livros 'A' e 'B', peticionado em 01/04/2026: 2 x 4 = 8 dias (Res. CNJ 391/2021, art. 5º). RSPE: 4 dias em "
    "25/04/2026 - metade.",
    RS(k, [REM(4, "25/04/2026", "25/04/2026")]),
    [C("fd_novo", "contem", "a menor")],
    ficha(k, [("01.04.2026", "EDUCAÇÃO: Peticionado relatório de leitura referente aos meses 01 e 02 de 2026. LIVROS: Iracema e Senhora.")]))

k = 5042
add(k, "Leitura: 4 livros em 2 meses contam 2 obras",
    "Limite de uma obra por período de leitura (21 a 30 dias)",
    "Ficha 8 / RSPE 0 (2 obras), não 16.",
    "Relatório dos meses 01 e 02/2026 listando 4 livros. Cada obra exige de 21 a 30 dias de leitura (Res. CNJ 391/2021, art. 5º): em 2 "
    "meses cabem 2 obras -> 8 dias.",
    RS(k),
    [C("fd_remidos", "eq", "8 / 0")],
    ficha(k, [("10.03.2026", "EDUCAÇÃO: Peticionado relatório de leitura referente aos meses 01 e 02 de 2026. LIVROS: Dom Casmurro, Iracema, O Cortiço e Senhora.")]))

k = 5043
evs = []
for i, (mm, aa) in enumerate([(10, 2025), (11, 2025), (12, 2025)] + [(m, 2026) for m in range(1, 10)]):
    pm, pa = (mm % 12) + 1, aa + (1 if mm == 12 else 0)
    evs.append(("05.%02d.%d" % (pm, pa) if (pm, pa) != (10, 2026) else "02.10.2026",
                "EDUCAÇÃO: Peticionado relatório de leitura referente ao mês %02d de %d, título do livro: Obra Simulada %d, no sistema SEEU." % (mm, aa, i + 1)))
evs.append(("28.09.2026", "EDUCAÇÃO: Peticionado relatório de leitura referente ao mês 09 de 2026, título do livro: Obra Simulada 13, no sistema SEEU."))
add(k, "Leitura: 13 obras em 12 meses - limite anual de 12",
    "Limite de 12 obras a cada 12 meses",
    "Ficha 48 / RSPE 0 (12 obras x 4), não 52.",
    "Relatórios mensais de 10/2025 a 09/2026 (12 obras) e mais uma obra em 09/2026: 13 obras em 12 meses. Res. CNJ 391/2021, art. 5º: até "
    "12 obras por ano, 4 dias cada -> 48 dias.",
    RS(k),
    [C("fd_remidos", "eq", "48 / 0")],
    ficha(k, evs))

# ================================================================= 9. Perda de dias remidos (LEP, art. 127)
k = 5044
add(k, "Perda de 1/3 exato da remição anterior à falta: regular",
    "Perda dentro do limite de 1/3",
    "Sem alerta de perda acima de 1/3 na Auditoria.",
    "Remições 60 (10/03/2025) + 30 (10/06/2025) = 90 até a falta de 01/08/2025. Perda de 30 = 90 ÷ 3 (LEP, art. 127): regular.",
    RS(k, [REM(60, "10/03/2025", "28/02/2025"), REM(30, "10/06/2025", "31/05/2025"), FALTA("01/08/2025", "15/09/2025"), PERDA(30, "15/09/2025")],
       perdidos=30),
    [AUD("perda-de-dias-remidos-acima-de-1-3-falta-de", presente=False)], None, aba="Auditoria")

k = 5045
add(k, "Trabalho anterior à falta, remido depois dela, entra na base do 1/3",
    "Dias trabalhados antes da falta, declarados só depois, também se sujeitam à perda",
    "Sem alerta de perda acima de 1/3 (base 80, limite 26,67, perda 25).",
    "Remição de 30 (10/01/2025). Atestado de 01/01 a 30/06/2025 (150 trab., 50) peticionado em 10/07/2025; falta grave de 15/07/2025; a remição "
    "de 50 desse trabalho foi decidida em 10/09/2025. Perda de 25 em 01/10/2025. O trabalho é anterior à falta: base 30 + 50 = 80; 1/3 = 26,67 "
    ">= 25 (LEP, art. 127; STJ: os dias trabalhados antes da falta, ainda que não declarados, sujeitam-se à perda).",
    RS(k, [REM(30, "10/01/2025", "31/12/2024"), FALTA("15/07/2025", "01/09/2025"), REM(50, "10/09/2025", "30/06/2025"), PERDA(25, "01/10/2025")],
       perdidos=25),
    [AUD("perda-de-dias-remidos-acima-de-1-3-falta-de", presente=False),
     C("fd_novo", "nao_contem", "acima de 1/3")],
    ficha(k, [("01.09.2024", INI("HORTA", "2/2024")), ("31.12.2024", FIM("HORTA", "3/2024")),
              ("05.01.2025", AT("002/2025", "01/09/2024", "31/12/2024", 90, 30, PET)),
              ("02.01.2025", INI("HORTA", "1/2025")), ("30.06.2025", FIM("HORTA", "20/2025")),
              ("10.07.2025", AT("070/2025", "02/01/2025", "30/06/2025", 150, 50, PET)),
              ("15.07.2025", "CONSELHO DISCIPLINAR: ISOLADO PREVENTIVAMENTE EM CELA DISCIPLINAR, POR 10 DIAS, REFERENTE A FALTA DISCIPLINAR COMETIDA EM 15/07/2025.")]),
    aba="Auditoria")

k = 5046
add(k, "Perda acima de 1/3 da remição anterior à falta",
    "Perda de 40 dias com base de 90",
    "Alerta na Auditoria: perda acima de 1/3 (limite 30, perdidos 40, excesso 10).",
    "Remições 45 (10/02/2025) + 45 (10/05/2025) = 90 antes da falta de 01/07/2025. Limite 90 ÷ 3 = 30 (LEP, art. 127). Perda decretada: "
    "40 -> excesso de 10 dias.",
    RS(k, [REM(45, "10/02/2025", "31/01/2025"), REM(45, "10/05/2025", "30/04/2025"), FALTA("01/07/2025", "20/08/2025"), PERDA(40, "20/08/2025")],
       perdidos=40),
    [AUD("perda-de-dias-remidos-acima-de-1-3-falta-de", presente=True, contem="30")], None, aba="Auditoria")

# ================================================================= 10. Reflexos: progressão, decretos, prioridade
k = 5047
crs = [crime(proc_crim(k, 2017), "ART 157: Roubo", anos(9), "15/03/2017", tipo="CAPUT: tipo simulado, Reclusão: 4 a 10 anos E Multa",
             sentenca="20/10/2017", transito="20/12/2017")]
add(k, "Reflexo na progressão: remição de trabalho posterior à data-base conta inteira",
    "Remição pendente reduz a data da progressão",
    "Fundamentação: a progressão passa de 01/09/2027 para 13/07/2027 (50 dias).",
    "Data-base 01/01/2026; progressão do SEEU em 01/09/2027; atestado de 05/01 a 30/06/2026 (150 trab., 50), posterior à data-base. A "
    "remição é pena cumprida (LEP, art. 128): 01/09/2027 - 50 dias = 13/07/2027.",
    RS(k, crimes=crs, ini="02/01/2023", prog="01/09/2027", db="01/01/2026", fp="1/6", fracao_progressao_aplicada="1/6"),
    [C("fd_fund", "contem", "13/07/2027")],
    ficha(k, [("05.01.2026", INI("COZINHA", "1/2026")), ("30.06.2026", FIM("COZINHA", "8/2026")),
              ("10.07.2026", AT("072/2026", "05/01/2026", "30/06/2026", 150, 50, PET))]), aba="Progressão")

k = 5048
crs = [crime(proc_crim(k, 2017), "ART 157: Roubo", anos(9), "15/03/2017", tipo="CAPUT: tipo simulado, Reclusão: 4 a 10 anos E Multa",
             sentenca="20/10/2017", transito="20/12/2017")]
add(k, "Reflexo na progressão: trabalho anterior à data-base reduz só a fração (1/6)",
    "Remição de período anterior à data-base reduz a pena remanescente; a progressão recua só 1/6 dos dias",
    "Fundamentação: a progressão passa de 01/09/2027 para 24/08/2027 (48 ÷ 6 = 8 dias).",
    "Data-base 01/07/2026; fração 1/6; progressão SEEU 01/09/2027. Atestado de 05/01 a 30/06/2026 (144 trab., 48), todo anterior à data-base: "
    "reduz a pena remanescente nela em 48 dias; o requisito (1/6 do remanescente) cai 48 ÷ 6 = 8 dias (LEP, arts. 112 e 128) -> 24/08/2027.",
    RS(k, crimes=crs, ini="02/01/2023", prog="01/09/2027", db="01/07/2026", fp="1/6", fracao_progressao_aplicada="1/6"),
    [C("fd_fund", "contem", "24/08/2027")],
    ficha(k, [("05.01.2026", INI("COZINHA", "1/2026")), ("30.06.2026", FIM("COZINHA", "8/2026")),
              ("10.07.2026", AT("073/2026", "05/01/2026", "30/06/2026", 144, 48, PET))]), aba="Progressão")

k = 5049
crs = [crime(proc_crim(k, 2023), "ART 297: Falsificação de documento público", anos(5), "10/06/2023", tipo="CAPUT: tipo simulado, Reclusão: 2 a 6 anos E Multa",
             sentenca="20/11/2023", transito="19/01/2024")]
cust = (D("25/12/2024") - D("20/01/2024")).days + 1
add(k, "Indulto 2024: remição pendente cobre os dias que faltavam",
    "Decreto 12.338/2024, art. 9º, I: faltavam %d dias para 1/5; atestado pendente de 70 dias de período anterior a 25/12/2024" % (365 - cust),
    "Indulto 2024: 'A VERIFICAR (remição pendente)'.",
    "Falsificação de documento público (CP, art. 297), pena 5 anos (1.825 dias), primário, sem violência, crime não patrimonial (afasta o art. 9º, XV) e não impeditivo (art. 1º): art. 9º, I, do Decreto 12.338/2024 exige 1/5 = 365 dias até "
    "25/12/2024. Preso em 20/01/2024: %d dias até 25/12/2024; faltavam %d. Atestado nº 120/2024 (01/02 a 30/11/2024, 210 trab., 70), "
    "emitido em 10/12/2024 e sem decisão: 70 >= %d. O decreto manda computar a remição (art. 5º; LEP, art. 128)." % (cust, 365 - cust, 365 - cust),
    RS(k, crimes=crs, ini="20/01/2024", pena=anos(5)),
    [C("dec", "regex", r'"2024"[^{}]*remição pendente')],
    ficha(k, [("01.02.2024", INI("HORTA", "2/2024")), ("30.11.2024", FIM("HORTA", "40/2024")),
              ("10.12.2024", AT("120/2024", "01/02/2024", "30/11/2024", 210, 70, PET))], entrada="20.01.2024"), aba="Indulto")

k = 5050
crs = [crime(proc_crim(k, 2025), "ART 155, § 4º: Furto qualificado", anos(4), "10/01/2025", tipo="§ 4º: tipo simulado, Reclusão: 2 a 8 anos E Multa",
             sentenca="20/01/2026", transito="10/03/2026", fp="16% - Primário sem violência")]
tt = uteis("17/03/2026", "31/08/2026")
add(k, "Prioridade: remição pendente que já dá a progressão",
    "Progressão prevista para 05/11/2026; remição pendente de %d dias a antecipa para antes de hoje" % (tt // 3),
    "Ícone de prioridade (rem_prio) com a progressão. Depende da data: depois de 05/11/2026 a progressão deixa de ser futura.",
    "Furto qualificado, pena 4 anos, 16%% (LEP, art. 112, I). Progressão do SEEU: 05/11/2026. Atestado nº 101/2026 (17/03 a 31/08/2026, %d "
    "trab., %d), sem decisão: 05/11/2026 - %d = %s <= 12/10/2026 -> o tempo já estaria cumprido (LEP, art. 128)." % (
        tt, tt // 3, tt // 3, F(D("05/11/2026") - timedelta(days=tt // 3))),
    RS(k, crimes=crs, ini="16/03/2026", pena=anos(4), prog="05/11/2026", fp="16%", fracao_progressao_aplicada="16%"),
    [C("rem_prio", "nao_vazio")],
    ficha(k, [("17.03.2026", INI("COZINHA", "3/2026")), ("31.08.2026", FIM("COZINHA", "30/2026")),
              ("05.09.2026", AT("101/2026", "17/03/2026", "31/08/2026", tt, tt // 3, PET))], entrada="16.03.2026"), aba="Progressão")

# ================================================================= 11. Afastamento, outra unidade, à parte
k = 5051
crs = [crime(proc_crim(k, 2018), "ART 157: Roubo", anos(12), "15/01/2018", tipo="§ 2º: tipo simulado, Reclusão: 4 a 10 anos E Multa",
             sentenca="20/10/2018", transito="20/12/2018")]
add(k, "Trabalho suspenso pela pandemia: remição ficta (STJ, Tema 1.120)",
    "Trabalho interrompido pela suspensão das atividades na pandemia de COVID-19",
    "Ponto 'Remição ficta' do trabalho na Cozinha a partir de 21/03/2020 (STJ, Tema 1.120).",
    "Cozinha de 01/08/2019 a 20/03/2020, encerrada por 'suspensão das atividades - pandemia COVID-19', sem retorno. O STJ (Tema 1.120) reconhece "
    "a remição ficta a quem trabalhava e foi impedido pela pandemia. Termo final: fim da emergência sanitária (Portaria GM/MS 913, de "
    "22/04/2022, em vigor 30 dias depois). Atestado do período trabalhado já remido.",
    RS(k, [REM(65, "20/05/2020", "20/03/2020")], crimes=crs, ini="10/06/2019"),
    [C("fd_novo", "contem", "Tema 1.120"), C("fd_novo", "contem", "21/03/2020")],
    ficha(k, [("01.08.2019", INI("COZINHA", "8/2019")), ("20.03.2020", FIM("COZINHA", "9/2020", "suspensão das atividades - pandemia COVID-19")),
              ("25.03.2020", AT("030/2020", "01/08/2019", "20/03/2020", 195, 65, PET))], entrada="10.06.2019"))

k = 5052
t = uteis("02/02/2026", "15/05/2026")
add(k, "Afastamento por acidente de trabalho: continuidade da remição",
    "Acidente de trabalho (LEP, art. 126, § 4º)",
    "Ponto 'A conferir' de afastamento por acidente: conferir o período e requerer a continuidade (art. 126, § 4º).",
    "Marcenaria de 02/02 a 15/05/2026, encerrada por 'acidente de trabalho'. O preso impossibilitado por acidente continua a beneficiar-se "
    "da remição (LEP, art. 126, § 4º). Atestado do período trabalhado, peticionado e remido.",
    RS(k, [REM(28, "20/07/2026", "15/05/2026")]),
    [C("fd_novo", "contem", "acidente"), C("fd_novo", "contem", "§ 4º")],
    ficha(k, [("02.02.2026", INI("MARCENARIA", "1/2026")), ("15.05.2026", FIM("MARCENARIA", "9/2026", "acidente de trabalho")),
              ("25.05.2026", AT("060/2026", "02/02/2026", "15/05/2026", 84, 28, PET))]))

k = 5053
add(k, "Afastamento por internação hospitalar: sem continuidade (só o acidente a tem)",
    "Afastamento por saúde que não é acidente",
    "Aviso cinza: a continuidade da remição só vale no acidente (art. 126, § 4º); nada a requerer pela internação.",
    "Serralheria de 02/02 a 15/05/2026, encerrada por 'internação hospitalar'. O § 4º do art. 126 da LEP só garante a continuidade no "
    "acidente; doença não gera remição ficta.",
    RS(k, [REM(28, "20/07/2026", "15/05/2026")]),
    [C("fd_novo", "contem", "acidente"), C("fd_novo", "nao_contem", "requerer a continuidade")],
    ficha(k, [("02.02.2026", INI("SERRALHERIA", "1/2026")), ("15.05.2026", FIM("SERRALHERIA", "9/2026", "internação hospitalar")),
              ("25.05.2026", AT("061/2026", "02/02/2026", "15/05/2026", 84, 28, PET))]))

k = 5054
add(k, "Atestado que cita outra unidade, sem trabalho na ficha",
    "Atestado com sigla de outra unidade penal; a ficha mostra o assistido na própria unidade sem trabalho",
    "Aviso cinza: o atestado cita EPRSAA, mas a ficha mostra o assistido em outra unidade, sem trabalho: conferir se é deste assistido.",
    "Atestado nº 24/2024/ST/EPRSAA (01/02 a 30/04/2024, 72 trab., 24); a ficha mostra o assistido no estabelecimento de Campo Grande desde "
    "2023, sem trabalho no período. Conferir a autoria do documento.",
    RS(k, [REM(24, "10/07/2024", "30/04/2024")]),
    [C("fd_novo", "contem", "EPRSAA")],
    ficha(k, [("10.05.2024", "Nesta data foi emitido ATESTADO DE TRABALHO PRISIONAL Nº 24/2024/ST/EPRSAA-A/AGEPEN-MS, correspondente ao período de "
                             "01/02/2024 a 30/04/2024, com 72 dias trabalhados e 24 dias remidos, PETICIONADO NO SEEU.")]))

k = 5055
add(k, "Atestado dirigido a outros autos: à parte",
    "Atestado que cita processo que não está no RSPE",
    "Documento 'À parte: dirigido a outros autos'; ficha 0 / RSPE 0; fora da conta.",
    "Atestado emitido para os autos 0000002-22.2023.8.12.0001, que não constam do RSPE. A remição é declarada no processo em que a pessoa "
    "cumpre a pena (LEP, art. 66, III, 'c'); sem remição correspondente aqui.",
    RS(k),
    [C("fd_novo", "contem", "À parte"), C("fd_remidos", "eq", "0 / 0")],
    ficha(k, [("01.02.2026", INI("HORTA", "1/2026")), ("30.04.2026", FIM("HORTA", "2/2026")),
              ("10.05.2026", "Emitido ATESTADO DE TRABALHO 248/2026/ST/UP para os autos nº 0000002-22.2023.8.12.0001 de 01/02/2026 a 30/04/2026, "
                             "75 dias trabalhados e 25 dias remidos, peticionado no SEEU.")]))

k = 5056
add(k, "Atestado anterior ao início da execução: à parte",
    "Trabalho e atestado de 2022, antes da prisão desta execução (02/01/2023)",
    "Documento 'À parte: anterior ao início desta execução'; ficha 0 / RSPE 0.",
    "Execução iniciada em 02/01/2023. Atestado nº 090/2022 (01/03 a 31/08/2022), de custódia anterior, por outro processo: não é desta execução.",
    RS(k),
    [C("fd_novo", "contem", "anterior ao início"), C("fd_remidos", "eq", "0 / 0")],
    ficha(k, [("01.03.2022", INI("HORTA", "3/2022")), ("31.08.2022", FIM("HORTA", "9/2022")),
              ("10.09.2022", AT("090/2022", "01/03/2022", "31/08/2022", 150, 50, PET))], entrada="10.02.2022"))

k = 5057
evs_i = [prisao("02/01/2023", proc_crim(k, 2022), "PRISÃO DEFINITIVA"), interr("01/03/2025", "LIBERDADE PROVISÓRIA"),
         ev("PRISÃO", "RECAPTURA", "01/07/2025")]
add(k, "Trabalho em período em que esta execução estava interrompida: à parte",
    "Execução interrompida por liberdade; a ficha mostra a pessoa presa (outro processo) e trabalhando",
    "Trabalho na Horta de 20/04 a 30/06/2025 'À parte' (fora do pedido); trabalho a atestar 'Não'.",
    "Interrupção por liberdade provisória de 01/03 a 30/06/2025. A ficha registra entrada em 15/04/2025 e trabalho de 20/04 a 30/06/2025: "
    "a custódia era por outro processo; a remição é daquela execução (LEP, art. 126, caput).",
    RS(k, eventos=evs_i, interrompidos=122),
    [C("fd_novo", "contem", "interrompida"), C("fd_atestar", "eq", "Não")],
    ficha(k, [("01.03.2025", "Saída da Unidade Penal: %s, motivo: ALVARÁ DE SOLTURA." % UN),
              ("15.04.2025", "Entrada na Unidade Penal: %s, Procedente: DEPAC, Conforme OF 9/2025." % UN),
              ("20.04.2025", INI("HORTA", "5/2025")), ("30.06.2025", FIM("HORTA", "9/2025"))]))

k = 5058
r58 = RS(k, [REM(40, "10/05/2025", "30/04/2025")], tribunal="TJSP", vara="TJSP - 1ª VARA DAS EXECUÇÕES CRIMINAIS", comarca="SÃO PAULO")
add(k, "RSPE de outro tribunal associado à ficha de MS",
    "RSPE do TJSP ligado a ficha do SIAPEN que cita outro processo",
    "Faixa 'RSPE de outra execução?' (o RSPE é do TJSP e a ficha é de unidade de MS).",
    "A ficha do SIAPEN é de MS e cita só o processo 0000003-33.2022.8.12.0001; o RSPE é do TJSP. Conferir se é o RSPE desta execução.",
    r58,
    [C("fd_novo", "contem", "RSPE de outra execução")],
    ficha(k, [("01.02.2025", INI("HORTA", "1/2025")), ("30.04.2025", FIM("HORTA", "2/2025")),
              ("10.05.2025", AT("033/2025", "01/02/2025", "30/04/2025", 75, 25, " PARA OS AUTOS Nº 0000003-33.2022.8.12.0001, PETICIONADO NO SEEU"))],
          autos=["0000003-33.2022.8.12.0001"]))

NOTAS = {
    "S5035": "Divergência: o programa liga a remição de 15 dias à certidão do 2º semestre e deixa a do 1º semestre (peticionada em 05/08/2025, "
             "sem nenhuma decisão de remição nos 180 dias seguintes nem depois) só como 'Peticionado · conferir a decisão' em cinza, porque o "
             "RSPE fica 'maior' que a ficha (certidões sem horas valem 0). Situação 'Conferir (informativo)', cinza. Uma certidão peticionada sem "
             "decisão é a pendência típica (LEP, arts. 126, § 8º, e 129); o estudo de 2026 sem certidão (≈ 53 dias) também sai cinza.",
    "S5043": "Divergência: o programa soma as 13 obras (52 dias). A Res. CNJ 391/2021, art. 5º, limita a remição pela leitura a 12 obras em "
             "12 meses (48 dias); a 13ª obra (segunda do mês 09/2026) não remite.",
    "S5049": "Divergência: o programa marca o Decreto 12.338/2024 como 'A VERIFICAR: art. 9º, § 2º, II a VI (metade do lapso)' (condições "
             "pessoais não informadas) e não aponta que a remição pendente de 70 dias, de trabalho até 30/11/2024, cobre os 24 dias que "
             "faltavam pelo art. 9º, I, sem depender de condição pessoal (art. 5º do decreto; LEP, art. 128). A regra da remição pendente só "
             "é aplicada quando o resultado seria 'não atinge'. A coluna mostra 'Verificar' nos dois casos, mas o motivo indicado não é o objetivo.",
    "S5057": "Divergência: o ponto diz que o trabalho é 'À parte' (execução interrompida, custódia por outro processo) e não entra na "
             "estimativa, mas a coluna 'Trabalho a atestar' mostra 'Sim'. Nada há a atestar nesta execução (LEP, art. 126, caput).",
}
for c in CASOS:
    if c["id"] in NOTAS:
        c["nota"] = NOTAS[c["id"]]

if __name__ == "__main__":
    json.dump(CASOS, open(os.path.join(AQUI, "remicao.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(CASOS), "casos")
