"""Base simulada de cobertura - área "ficha": leitura da Ficha Disciplinar do SIAPEN e confronto RSPE x ficha.
Casos S2001 em diante (processos 99020xx). As fichas vão com "versao_leitura": 0 e o texto bruto dos lançamentos, para o
programa reler tudo (rspe_ficha.atualizar). Gabarito feito pela lei e pelo que o texto da ficha diz, sem olhar o programa.
Uso (a partir de casos_simulados): python3 cobertura/gera_ficha.py"""
import os, re, sys, json
from datetime import timedelta
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from base_casos import (D, F, GER, anos, crime, ev, prisao, interr, inc, rspe, C, AUD, P, caso, REG, proc_crim)

JANELA = (D("12/10/2026"), D("31/03/2027"))
CASOS = []
_k = [2000]
X = "rspe-x-ficha"  # tipo dos itens do confronto RSPE x ficha na Auditoria


def prox():
    _k[0] += 1
    return _k[0]


def _fora_janela(*ds):
    for d in ds:
        if d and JANELA[0] <= D(d) <= JANELA[1]:
            raise SystemExit("data %s cai na janela 12/10/2026-31/03/2027" % d)


def R(k, ini, pena=anos(6), fato="10/01/2022", artigo="ART 155: Furto", tipo="§ 4º: furto qualificado, Reclusão: 2 a 8 anos E Multa",
      eventos=None, incidentes=None, regime="Fechado - ATIVO", crimes=None, prog=None, liv=None, fp="16% - Art.112, I, da LEP",
      fl="1/3 - Comum Primário", ano_proc=2022, **kw):
    """RSPE simples: um furto qualificado, prisão em 'ini' e regime inicial fechado, salvo o que o caso der."""
    pc = proc_crim(k, ano_proc)
    if crimes is None:
        crimes = [crime(pc, artigo, pena, fato, tipo=tipo, fp=fp, fl=fl)]
    if eventos is None:
        eventos = [prisao(ini, pc, "PRISÃO PREVENTIVA")] if ini else []
    if incidentes is None:
        incidentes = [inc(REG, "Fechado - Regime Inicial", "", ini or "")]
    if ini and prog is None:
        prog = F(D(ini) + timedelta(days=int(pena * 0.16)))
        liv = F(D(ini) + timedelta(days=int(pena / 3)))
    _fora_janela(prog, liv)
    return rspe(k, crimes, eventos, incidentes, ini=ini, pena=pena, prog=prog, liv=liv, regime=regime, **kw)


def FICHA(k, evs, unidade="INSTITUTO PENAL DE CAMPO GRANDE", data_entrada="", data_prisao="", conduta="BOA", impressao="02/10/2026",
          cpf=None, nasc="01/01/1975", mae=None, filiacao=None, artigo="ART 155", condenacao="", sexo="M", nome=None):
    """Ficha no formato da tabela fichas, com o texto bruto dos lançamentos (releitura pelo programa)."""
    cpf = cpf or "%011d" % (90000000000 + k)
    cpf = "%s.%s.%s-%s" % (cpf[:3], cpf[3:6], cpf[6:9], cpf[9:])
    mae = mae or "MAE SIMULADA %03d" % k
    # autos citados no texto, como a importação do PDF os grava (a releitura pelos eventos não refaz esta lista)
    autos = []
    for _d, t in evs:
        for a in re.findall(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}", t):
            if a not in autos:
                autos.append(a)
    return {"tipo": "ficha_disciplinar", "versao_leitura": 0, "nome": nome or "SIMULADO CASO %03d" % k, "cpf": cpf, "cpf_em_branco": False,
            "data_nascimento": nasc, "nome_mae": mae, "filiacao": filiacao or (mae + " \\ PAI SIMULADO %03d" % k), "artigo": artigo,
            "data_prisao": data_prisao, "condenacao": condenacao, "unidade": unidade, "data_entrada": data_entrada, "sexo": sexo,
            "conduta": conduta, "data_impressao": impressao, "paginas": 3, "paginas_sem_texto": [], "autos": autos,
            "eventos": [{"data": d.replace("/", "."), "texto": t} for d, t in evs], "historico_oculto": []}


def add(k, aba, titulo, situacao, esperado, conta, r, checks, ficha, **kw):
    c = caso(k, "F-ficha", titulo, conta, r, checks, ficha=ficha, **kw)
    c.update(aba=aba, situacao=situacao, esperado=esperado)
    CASOS.append(c)
    return c


def ent(u, proc):
    return "Entrada na Unidade Penal: %s, Procedente: %s, Conforme OF/CI 1." % (u, proc)


def sai(u, dest, mot):
    return "Saída da Unidade Penal: %s, Destino: %s, Motivo: %s" % (u, dest, mot)


def cela(u, mot="ADEQUAÇÃO", dest="PV2 C05"):
    return "Mudança de Cela: %s, Origem: PV1 C10, Destino: %s, Motivo: %s" % (u, dest, mot)


def ini_trab(setor, doc="CI 10"):
    return "TRABALHO: Iniciou atividade laboral, no setor de trabalho %s, conforme documento %s." % (setor, doc)


def fim_trab(setor, mot, doc="CI 20"):
    return "TRABALHO: Deixa de trabalhar, no setor de trabalho %s, conforme documento %s, Motivo: %s" % (setor, doc, mot)


def trab(ficha, setor, ini, fim=None):
    """regex de uma linha de trabalho na ficha exibida (datas com ponto, como a ficha grava)."""
    f = ('"fim": "%s"' % fim.replace("/", "\\.")) if fim else '"fim": (null|"")'
    return r'"inicio": "%s", %s, "setor": "%s' % (ini.replace("/", "\\."), f, setor)


# =====================================================================================================================
# 2.2 Identificação e vínculo
# =====================================================================================================================
k = prox()
r = R(k, "15/03/2024", anos(5), "10/01/2024", cpf="90000002001", ano_proc=2024)
f = FICHA(k, [("16/03/2024", ent("PTRAN", "DEPAC CENTRO")), ("20/04/2024", ent("IPCG", "PTRAN - CAPITAL")), ("10/09/2026", cela("IPCG"))],
          cpf="90000000201", data_prisao="15/03/2024", data_entrada="20/04/2024")
add(k, "Auditoria", "CPF da ficha com dois dígitos vizinhos trocados",
    "O CPF da ficha (900.000.002-01) é o do RSPE (900.000.020-01) com dois algarismos vizinhos invertidos.",
    "Auditoria: alerta de CPF divergente entre ficha e RSPE, apontando provável erro de digitação (dígitos trocados).",
    "RSPE 900.000.020-01 x ficha 900.000.002-01: os algarismos das posições 8 e 9 (2 e 0) estão invertidos. CPFs de 11 dígitos "
    "diferentes impedem afirmar a identidade sem conferência (LEP, art. 106, identificação na guia); a inversão de vizinhos é o "
    "erro de digitação típico, e o programa promete dizer isso.",
    r, [AUD(X, contem=["CPF", "difere"], nivel="alerta"), AUD(X, contem=["CPF", "digitação"])], f)

k = prox()
r = R(k, "20/06/2023", anos(5), "02/06/2023", nome_mae="MARIA FERNANDA DA SILVA SIMULADA", ano_proc=2023)
f = FICHA(k, [("21/06/2023", ent("PTRAN", "DEPAC CENTRO")), ("01/08/2023", ent("PDIB", "PTRAN - CAPITAL")), ("10/09/2026", cela("PDIB"))],
          mae="MARIA F. DA SILVA SIMULADA", nasc="03/01/1975", unidade="PENITENCIARIA ESTADUAL DE DOIS IRMAOS DO BURITI",
          data_prisao="20/06/2023", data_entrada="01/08/2023")
add(k, "Auditoria", "Mãe abreviada e nascimento dois dias diferente",
    "A mãe vem abreviada na ficha (MARIA F. DA SILVA) e o nascimento difere em 2 dias (01/01/1975 x 03/01/1975), sem mudar marco de idade.",
    "Sem item de mãe (abreviação compatível); nascimento divergente só como informação (nenhum marco de idade muda).",
    "Mãe: 'MARIA F. DA SILVA SIMULADA' é abreviação de 'MARIA FERNANDA DA SILVA SIMULADA' (mesmo primeiro e último nome): é a "
    "mesma pessoa, não há dúvida de identidade. Nascimento: com 01/01/1975 ou 03/01/1975 a pessoa tinha 48 anos no fato "
    "(02/06/2023), e 47, 49 e 50 anos nas datas dos decretos (25/12/2022, 25/12/2024, 25/12/2025): nenhum marco (18, 21, 60 ou "
    "70 anos; CP, art. 115; decretos de indulto) muda; logo, divergência só informativa.",
    r, [AUD(X, presente=False, contem="Mãe na ficha"), AUD(X, contem="Nascimento na ficha", nivel="info"),
        AUD(X, presente=False, contem="Nascimento na ficha", nivel="alerta")], f)

k = prox()
r = R(k, "05/04/2018", anos(9), "10/02/2012", nasc="20/05/1990", ano_proc=2012)
f = FICHA(k, [("06/04/2018", ent("PTRAN", "DEPAC CENTRO")), ("20/05/2018", ent("EPJFC", "PTRAN - CAPITAL")), ("10/09/2026", cela("EPJFC"))],
          nasc="20/05/1991", unidade="ESTABELECIMENTO PENAL JAIR FERREIRA DE CARVALHO", data_prisao="05/04/2018", data_entrada="20/05/2018")
add(k, "Auditoria", "Nascimento divergente que muda a idade de 21 anos no fato",
    "RSPE diz nascimento em 20/05/1990 e a ficha em 20/05/1991; o fato é de 10/02/2012.",
    "Auditoria: alerta de nascimento divergente, porque pela ficha a pessoa tinha menos de 21 anos no fato (prescrição pela metade).",
    "Fato 10/02/2012. Pelo RSPE (20/05/1990): 21 anos e 8 meses no fato. Pela ficha (20/05/1991): 20 anos e 8 meses, menor de 21. "
    "O CP, art. 115, reduz pela metade os prazos de prescrição de quem era menor de 21 anos ao tempo do crime: a divergência muda "
    "um marco legal e prejudica o assistido se a data certa for a da ficha. Alerta.",
    r, [AUD(X, contem=["Nascimento na ficha", "20/05/1991"], nivel="alerta")], f)

# =====================================================================================================================
# 2.3 Unidades e unidade atual
# =====================================================================================================================
k = prox()
r = R(k, "02/02/2023", anos(6), "10/12/2022", ano_proc=2022)
f = FICHA(k, [("03/02/2023", ent("PTRAN", "DEPAC CENTRO")), ("20/03/2023", sai("PTRAN", "PDIB", "Transferência")),
              ("20/03/2023", ent("PDIB", "PTRAN - CAPITAL")), ("05/06/2026", sai("PDIB", "CPAIG", "Transferência")),
              ("05/06/2026", ent("CENTRO PENAL AGROINDUSTRIAL DA GAMELEIRA", "PDIB - CAPITAL")), ("10/09/2026", cela("CPAIG"))],
          unidade="CENTRO PENAL AGROINDUSTRIAL DA GAMELEIRA", data_entrada="05/06/2026", data_prisao="02/02/2023")
add(k, "Auditoria", "RSPE em fechado e a pessoa no semiaberto (Gameleira)",
    "O RSPE está em regime fechado, mas a ficha mostra a pessoa no Centro Penal Agroindustrial da Gameleira desde 05/06/2026.",
    "Auditoria: alerta 'RSPE em regime fechado, mas a ficha indica unidade de semiaberto' (progressão não lançada no SEEU).",
    "A Gameleira (CPAIG) é colônia agroindustrial, estabelecimento do semiaberto (LEP, art. 91; CP, art. 33, § 1º, b). Se a pessoa "
    "foi levada para lá, houve progressão que o SEEU não registra, e o cálculo do RSPE (regime fechado) fica desatualizado, com "
    "data-base e próxima progressão erradas (LEP, art. 112). Alerta.",
    r, [AUD(X, contem=["regime fechado", "semiaberto"], nivel="alerta"), C("ficha", "contem", "GAMELEIRA")], f)

k = prox()
r = R(k, "10/05/2022", anos(6), "20/04/2022", regime="Semiaberto - ATIVO", ano_proc=2022, prog="10/05/2027", liv="10/05/2025",
      incidentes=[inc(REG, "Fechado - Regime Inicial", "", "10/05/2022"), inc("PROGRESSÃO DE REGIME", "Semiaberto", "20/06/2023", "10/05/2023")])
f = FICHA(k, [("12/05/2022", ent("PENITENCIARIA ESTADUAL DE DOURADOS", "1ª DP DOURADOS - INTERIOR")), ("15/09/2023", cela("PED")),
              ("10/03/2025", cela("PED")), ("10/09/2026", cela("PED"))],
          unidade="PENITENCIARIA ESTADUAL DE DOURADOS", data_entrada="12/05/2022", data_prisao="10/05/2022")
add(k, "Auditoria", "Semiaberto no RSPE e a pessoa na Penitenciária de Dourados",
    "Progressão ao semiaberto concedida em 2023, mas a ficha mantém a pessoa na Penitenciária Estadual de Dourados (regime fechado).",
    "Auditoria: alerta 'RSPE em regime semiaberto, mas a ficha indica unidade de regime fechado' - pedir transferência ou regime menos gravoso.",
    "Penitenciária é estabelecimento do regime fechado (LEP, art. 87). Quem tem o semiaberto não pode cumpri-lo em penitenciária "
    "por falta de vaga (STF, Súmula Vinculante 56 e RE 641.320). Não há nova prisão nem execução suspensa. Alerta.",
    r, [AUD(X, contem=["semiaberto", "regime fechado"], nivel="alerta")], f)

k = prox()
r = R(k, "10/05/2022", anos(6), "20/04/2022", regime="Semiaberto - ATIVO", ano_proc=2022, prog="10/05/2027", liv="10/05/2025",
      incidentes=[inc(REG, "Fechado - Regime Inicial", "", "10/05/2022"), inc("PROGRESSÃO DE REGIME", "Semiaberto", "20/06/2023", "10/05/2023")])
f = FICHA(k, [("12/05/2022", ent("ESTABELECIMENTO PENAL DE NAVIRAI", "DP NAVIRAI - INTERIOR")), ("15/09/2023", cela("EPN")),
              ("10/09/2026", cela("EPN"))],
          unidade="ESTABELECIMENTO PENAL DE NAVIRAI", data_entrada="12/05/2022", data_prisao="10/05/2022")
add(k, "Auditoria", "Semiaberto no RSPE e unidade genérica 'Estabelecimento Penal'",
    "RSPE em semiaberto; ficha com 'ESTABELECIMENTO PENAL DE NAVIRAI', nome que não diz o regime.",
    "Auditoria: 'verificar' (não alerta): a unidade pode ter ala de semiaberto; conferir onde a pessoa cumpre.",
    "'Estabelecimento penal' é o gênero (LEP, art. 82), não diz se é penitenciária (fechado) ou colônia (semiaberto). Sem prova de "
    "que a unidade é de regime fechado, não se afirma o excesso; é dúvida a conferir.",
    r, [AUD(X, contem=["semiaberto", "fechado"], nivel="verificar"), AUD(X, presente=False, contem=["semiaberto", "fechado"], nivel="alerta")], f)

# =====================================================================================================================
# 2.4 Entradas, saídas e custódia
# =====================================================================================================================
k = prox()
pc = proc_crim(k, 2021)
r = R(k, "01/02/2022", anos(8), "10/12/2021", ano_proc=2021, prog="20/08/2027", liv="20/08/2028",
      eventos=[prisao("01/02/2022", pc, "PRISÃO PREVENTIVA"), interr("10/06/2024", "FUGA")], interrompidos=(GER - D("10/06/2024")).days)
f = FICHA(k, [("03/02/2022", ent("PTRAN", "DEPAC CENTRO")), ("10/03/2022", ent("EPJFC", "PTRAN - CAPITAL")),
              ("10/06/2024", sai("EPJFC", "", "FUGA")), ("20/11/2024", ent("PTRAN", "RECAPTURA - CAPITAL")),
              ("15/01/2025", ent("EPJFC", "PTRAN - CAPITAL")), ("10/09/2026", cela("EPJFC"))],
          unidade="ESTABELECIMENTO PENAL JAIR FERREIRA DE CARVALHO", data_prisao="18/11/2024", data_entrada="15/01/2025")
add(k, "Auditoria", "Recaptura só na ficha: reinício omitido no RSPE",
    "RSPE parado na fuga de 10/06/2024; a ficha mostra a recaptura (Data Prisão 18/11/2024, entrada por recaptura em 20/11/2024) e a pessoa presa desde então.",
    "Auditoria: alerta 'Reinício omitido no RSPE: lançado pela ficha em 18/11/2024'; pedir a retificação (reinício/recaptura).",
    "Com a recaptura, o cumprimento recomeça (LEP, art. 111; CP, art. 113: a prescrição deixa de correr com a recaptura, art. 117, V). "
    "A captura é a da Data Prisão do cabeçalho (18/11/2024), dois dias antes da entrada formal na unidade (20/11/2024). Sem o reinício "
    "no SEEU, o tempo preso desde 18/11/2024 não conta e o SEEU não projeta os benefícios. Alerta.",
    r, [AUD(X, contem=["Reinício omitido", "18/11/2024"], nivel="alerta")], f)

# custódia ininterrupta (Decreto 12.790/2025, art. 9º, IV: 15 anos ininterruptos até 25/12/2025, primário)
for interrompida in (False, True):
    k = prox()
    pc1, pc2 = proc_crim(k, 2009), "%07d-00.2016.8.12.0001" % (8700000 + k)
    c1 = crime(pc1, "ART 157: Roubo", anos(20), "01/02/2009", tipo="§ 2º: roubo majorado, Reclusão: 4 a 10 anos E Multa",
               fp="1/6 - Comum", fl="1/3 - Comum Primário")
    c2 = crime(pc2, "ART 129: Lesão corporal", anos(1), "05/06/2016", tipo="CAPUT: lesão corporal, Detenção: 3 meses a 1 ano",
               fp="1/6 - Comum", fl="1/3 - Comum Primário")
    r = R(k, "10/03/2009", anos(21), crimes=[c1, c2], prog="15/06/2028", liv="15/06/2029",
          eventos=[prisao("10/03/2009", pc1, "PRISÃO EM FLAGRANTE"), prisao("15/06/2016", pc2, "PRISÃO EM FLAGRANTE")],
          incidentes=[inc(REG, "Fechado - Regime Inicial", "", "10/03/2009")])
    evs = [("11/03/2009", ent("PTRAN", "DEPAC CENTRO")), ("20/04/2009", ent("EPJFC", "PTRAN - CAPITAL")), ("10/05/2012", cela("EPJFC"))]
    if interrompida:
        evs += [("20/02/2016", sai("EPJFC", "", "ALVARÁ DE SOLTURA")), ("15/06/2016", ent("PTRAN", "2ª DP CAMPO GRANDE")),
                ("20/07/2016", ent("EPJFC", "PTRAN - CAPITAL"))]
    else:
        evs += [("02/05/2016", cela("EPJFC")), ("15/06/2016", "Interno conduzido à delegacia e autuado em flagrante pela lesão corporal "
                                                         "de 05/06/2016 contra outro interno; retornou à unidade na mesma data."),
                ("20/08/2016", cela("EPJFC"))]
    evs += [("10/03/2020", cela("EPJFC")), ("10/06/2025", cela("EPJFC")), ("10/09/2026", cela("EPJFC"))]
    f = FICHA(k, evs, unidade="ESTABELECIMENTO PENAL JAIR FERREIRA DE CARVALHO", data_prisao="15/06/2016" if interrompida else "10/03/2009",
              data_entrada="20/07/2016" if interrompida else "20/04/2009", artigo="ART 157")
    if not interrompida:
        add(k, "Indulto", "Custódia ininterrupta de 15 anos com nova prisão dentro da custódia (inciso IV)",
            "Preso desde 10/03/2009; nova prisão no RSPE em 15/06/2016 por fato cometido dentro da unidade; a ficha mostra custódia sem soltura.",
            "Indulto 2025, inciso IV (15 anos ininterruptos): atendido - a prisão de 2016 ocorreu durante a custódia e não interrompe o período.",
            "Decreto 12.790/2025, art. 9º, IV: 15 anos cumpridos ininterruptamente até 25/12/2025, se não reincidente. De 10/03/2009 a "
            "25/12/2025 = 16 anos, 9 meses e 16 dias, sem soltura, fuga ou evasão na ficha (registros em 2009, 2012, 2016, 2020, 2025, 2026). "
            "A prisão em flagrante de 15/06/2016 foi de quem já estava preso (fato de 05/06/2016 dentro da unidade): não houve liberdade no meio. "
            "Roubo majorado de 2009 não é hediondo (Lei 8.072/90 só passou a incluir o roubo majorado em 2019), nem impeditivo do art. 1º.",
            r, [C("det25", "regex", r"✔ IV:[^\n]*ficha: custodiado"), C("det25", "nao_contem", "houve interrupção")], f)
    else:
        add(k, "Indulto", "Custódia interrompida por soltura que só a ficha registra (inciso IV)",
            "Mesmo quadro, mas a ficha registra alvará de soltura em 20/02/2016 e nova entrada vinda da delegacia em 15/06/2016.",
            "Indulto 2025, inciso IV: não atendido - houve interrupção da custódia em 2016 (só 9 anos e 6 meses contínuos até 25/12/2025).",
            "Decreto 12.790/2025, art. 9º, IV exige 15 anos ininterruptos. A ficha prova liberdade de 20/02/2016 a 15/06/2016. O período "
            "contínuo mais longo até 25/12/2025 é 15/06/2016 a 25/12/2025 = 9 anos, 6 meses e 11 dias; o anterior (10/03/2009 a 20/02/2016) "
            "tem 6 anos e 11 meses. Nenhum chega a 15 anos.",
            r, [C("det25", "regex", r"✘ IV:[^\n]*interrup")], f)

k = prox()
pc = proc_crim(k, 2021)
r = R(k, "05/09/2021", anos(5), "20/08/2021", ano_proc=2021, regime="Aberto - ATIVO", prog="", liv="",
      eventos=[prisao("05/09/2021", pc, "PRISÃO EM FLAGRANTE"), interr("10/03/2025", "PRISÃO EM OUTRO PROCESSO")],
      incidentes=[inc(REG, "Fechado - Regime Inicial", "", "05/09/2021"), inc("PROGRESSÃO DE REGIME", "Semiaberto", "10/10/2022", "05/09/2022"),
                  inc("PROGRESSÃO DE REGIME", "Aberto", "01/09/2024", "20/08/2024")], interrompidos=(GER - D("10/03/2025")).days)
f = FICHA(k, [("06/09/2021", ent("PTRAN", "DEPAC CENTRO")), ("15/10/2022", ent("CENTRO PENAL AGROINDUSTRIAL DA GAMELEIRA", "PTRAN - CAPITAL")),
              ("01/09/2024", sai("CPAIG", "", "PROGRESSÃO PARA O REGIME ABERTO")),
              ("10/03/2025", ent("PTRAN", "3ª DP CAMPO GRANDE")), ("10/03/2025", "Interno recolhido por mandado de prisão preventiva nos autos 0007777-11.2025.8.12.0001."),
              ("15/08/2026", cela("PTRAN"))],
          unidade="PRESIDIO DE TRANSITO DE CAMPO GRANDE", data_prisao="10/03/2025", data_entrada="10/03/2025")
add(k, "Auditoria", "Prisão em outro processo confirmada pela ficha (suspensão)",
    "No aberto, a execução foi interrompida em 10/03/2025 por prisão em outro processo; a ficha mostra a prisão preventiva em outros autos e a pessoa ainda presa.",
    "Auditoria: 'ok' - suspensão confirmada pela ficha (preso desde a interrupção; não corre prescrição). Nenhum reinício lançado.",
    "A ficha mostra entrada vinda da 3ª DP em 10/03/2025 por preventiva nos autos 0007777-11.2025.8.12.0001 (que o RSPE não lista) e "
    "registros até 15/08/2026 sem saída. Preso por outro motivo, a prescrição executória não corre (CP, art. 116, p. único) e a "
    "execução fica suspensa; não é reinício desta pena.",
    r, [AUD(X, contem="Suspensão confirmada", nivel="ok"), AUD(X, presente=False, contem="Reinício omitido")], f)

k = prox()
pc = proc_crim(k, 2021)
r = R(k, "05/05/2021", anos(5), "10/04/2021", ano_proc=2021, regime="Livramento Condicional - ATIVO", prog="", liv="",
      eventos=[prisao("05/05/2021", pc, "PRISÃO EM FLAGRANTE"), interr("20/02/2024", "LIVRAMENTO CONDICIONAL")],
      incidentes=[inc(REG, "Fechado - Regime Inicial", "", "05/05/2021"), inc("LIVRAMENTO CONDICIONAL", "", "15/02/2024", "20/02/2024")],
      interrompidos=(GER - D("20/02/2024")).days)
f = FICHA(k, [("06/05/2021", ent("PTRAN", "DEPAC CENTRO")), ("20/02/2024", sai("PTRAN", "", "LIVRAMENTO CONDICIONAL")),
              ("11/08/2026", ent("PTRAN", "2ª DP CAMPO GRANDE")), ("15/09/2026", cela("PTRAN"))],
          unidade="PRESIDIO DE TRANSITO DE CAMPO GRANDE", artigo="PRISÃO CIVIL - PENSÃO ALIMENTÍCIA", data_prisao="10/08/2026",
          data_entrada="11/08/2026")
add(k, "Auditoria", "Prisão civil por alimentos durante o livramento",
    "Em livramento condicional desde 20/02/2024; a ficha registra nova prisão em 10/08/2026 com o artigo 'PRISÃO CIVIL - PENSÃO ALIMENTÍCIA'.",
    "Nenhum reinício lançado; item informativo 'prisão civil' (não é pena nem detração).",
    "A prisão civil do devedor de alimentos (CF, art. 5º, LXVII; CPC, art. 528, § 3º) não é pena nem prisão processual penal: não "
    "reinicia esta execução nem revoga o livramento (CP, art. 86 exige condenação por crime) e não se detrai (CP, art. 42 fala de "
    "prisão provisória no Brasil ou no estrangeiro por processo penal).",
    r, [AUD(X, contem="prisão civil"), AUD(X, presente=False, contem="Reinício omitido")], f)

# =====================================================================================================================
# 2.5 Solturas, prisões e detrações só na ficha
# =====================================================================================================================
k = prox()
pc = proc_crim(k, 2023)
r = R(k, "25/04/2023", anos(6), "01/04/2023", ano_proc=2023, eventos=[prisao("25/04/2023", pc, "PRISÃO EM FLAGRANTE")])
f = FICHA(k, [("04/04/2023", ent("PTRAN", "DEPAC CENTRO")), ("20/05/2023", ent("IPCG", "PTRAN - CAPITAL")), ("10/09/2026", cela("IPCG"))],
          data_prisao="02/04/2023", data_entrada="20/05/2023")
add(k, "Auditoria", "Prisão de 02/04/2023 na ficha; RSPE começa em 25/04/2023",
    "Fato de 01/04/2023; a ficha registra a prisão em 02/04/2023 (entrada no PTRAN em 04/04/2023); o RSPE só registra prisão em 25/04/2023.",
    "Auditoria: alerta 'Prisão em 02/04/2023 na ficha; RSPE só registra início em 25/04/2023 (23 dias sem cômputo)'.",
    "Dias presos e não computados: de 02/04/2023 a 24/04/2023, inclusive = 23 dias (abril: 2 a 24). A prisão é posterior ao fato "
    "desta execução e sem soltura no meio: é detração obrigatória (CP, art. 42).",
    r, [AUD(X, contem=["02/04/2023", "23 dias"], nivel="alerta")], f)

k = prox()
pc = proc_crim(k, 2022)
r = R(k, "03/03/2025", anos(6), "10/01/2022", ano_proc=2022, eventos=[prisao("03/03/2025", pc, "PRISÃO DEFINITIVA")], prog="15/05/2027", liv="15/05/2028")
f = FICHA(k, [("17/01/2022", ent("PTRAN", "1ª DP CAMPO GRANDE")), ("17/01/2022", "Recolhido por prisão preventiva nos autos %s." % pc),
              ("20/05/2022", sai("PTRAN", "", "ALVARÁ DE SOLTURA: %s" % pc)), ("03/03/2025", ent("PTRAN", "DEPAC CENTRO")),
              ("10/04/2025", ent("IPCG", "PTRAN - CAPITAL")), ("10/09/2026", cela("IPCG"))],
          data_prisao="03/03/2025", data_entrada="10/04/2025")
add(k, "Auditoria", "Preventiva de 2022 no próprio processo, solta por alvará: detração",
    "Fato de 10/01/2022; a ficha mostra preventiva de 17/01/2022 a 20/05/2022, encerrada por alvará do próprio processo; o RSPE só começa em 03/03/2025.",
    "Auditoria: alerta 'Detração: prisão de 17/01/2022 a 20/05/2022 na ficha (processo desta execução) sem cômputo no RSPE - 124 dias'.",
    "Dias de 17/01/2022 a 20/05/2022, contando os dois extremos: janeiro 15 (17 a 31) + fevereiro 28 + março 31 + abril 30 + maio 20 = 124. "
    "A prisão provisória pelo mesmo processo da condenação é detração obrigatória (CP, art. 42; LEP, art. 111).",
    r, [AUD(X, contem=["Detração", "17/01/2022", "20/05/2022", "124"], nivel="alerta")], f)

k = prox()
r = R(k, "01/03/2021", anos(8), "10/02/2021", ano_proc=2021, prog="15/08/2027", liv="15/08/2028")
f = FICHA(k, [("02/03/2021", ent("PTRAN", "DEPAC CENTRO")), ("15/04/2023", sai("PTRAN", "", "ALVARÁ DE SOLTURA")),
              ("20/09/2023", ent("PTRAN", "1ª DP CAMPO GRANDE")), ("10/10/2023", ent("IPCG", "PTRAN - CAPITAL")), ("10/09/2026", cela("IPCG"))],
          data_prisao="20/09/2023", data_entrada="10/10/2023")
add(k, "Auditoria", "Soltura que o RSPE não lançou (erro favorável)",
    "RSPE conta custódia contínua desde 01/03/2021; a ficha mostra soltura em 15/04/2023 e nova prisão em 20/09/2023.",
    "Nenhum alerta do confronto ficha x RSPE: o erro (contar como pena 157 dias de liberdade) favorece o assistido.",
    "Política declarada: a Auditoria só alerta o que prejudica o assistido. O RSPE conta como cumprida a liberdade de 15/04/2023 a "
    "20/09/2023; isso favorece o assistido. Nenhum item 'alerta' de origem ficha.",
    r, [AUD(X, presente=False, nivel="alerta")], f)

k = prox()
pc = proc_crim(k, 2021)
r = R(k, "10/01/2022", anos(7), "20/12/2021", ano_proc=2021, prog="10/06/2027", liv="10/06/2028",
      eventos=[prisao("10/01/2022", pc, "PRISÃO PREVENTIVA"), interr("15/06/2022", "LIBERDADE PROVISÓRIA"),
               prisao("15/12/2022", pc, "PRISÃO DEFINITIVA")], interrompidos=183)
f = FICHA(k, [("11/01/2022", ent("PTRAN", "DEPAC CENTRO")), ("15/06/2022", "PARECER: Alvará de soltura nos autos %s com PENDÊNCIA - "
                                                                   "não foi colocado em liberdade." % pc),
              ("20/09/2022", cela("PTRAN")), ("20/01/2023", ent("IPCG", "PTRAN - CAPITAL")), ("10/09/2026", cela("IPCG"))],
          data_prisao="10/01/2022", data_entrada="20/01/2023")
add(k, "Auditoria", "Liberdade provisória com alvará pendente: não foi solto",
    "RSPE interrompe em 15/06/2022 (liberdade provisória) e reinicia em 15/12/2022; a ficha diz que o alvará ficou com pendência e a pessoa não saiu.",
    "Auditoria: alerta 'Interrupção de 15/06/2022 (liberdade provisória) sem soltura na ficha: 182 dias fora da conta até 15/12/2022'.",
    "A pessoa ficou presa entre a interrupção e o reinício. Dias fora da conta, excluídos os dois extremos (que o RSPE já conta): "
    "16/06/2022 a 14/12/2022 = junho 15 + julho 31 + agosto 31 + setembro 30 + outubro 31 + novembro 30 + dezembro 14 = 182. "
    "Custódia que deve ser computada (CP, art. 42; LEP, art. 111). A pendência cita o processo desta execução: alerta.",
    r, [AUD(X, contem=["15/06/2022", "182 dias"], nivel="alerta")], f)

# =====================================================================================================================
# 2.6 Monitoramento eletrônico
# =====================================================================================================================
k = prox()
pc = proc_crim(k, 2021)
r = R(k, "01/03/2022", anos(8), "10/02/2022", ano_proc=2021, regime="Semiaberto - ATIVO", prog="15/06/2027", liv="15/06/2028",
      eventos=[prisao("01/03/2022", pc, "PRISÃO PREVENTIVA"), interr("02/04/2024", "DETERMINAÇÃO JUDICIAL"),
               prisao("01/04/2025", pc, "REINÍCIO DE CUMPRIMENTO")], interrompidos=364,
      incidentes=[inc(REG, "Fechado - Regime Inicial", "", "01/03/2022"), inc("PROGRESSÃO DE REGIME", "Semiaberto", "20/03/2024", "01/03/2024")])
U = "UNIDADE MISTA DE MONITORAMENTO VIRTUAL ESTADUAL"
pid = r["processo_execucao"]
f = FICHA(k, [("02/03/2022", ent("PTRAN", "DEPAC CENTRO")), ("25/03/2024", ent("CENTRO PENAL AGROINDUSTRIAL DA GAMELEIRA", "PTRAN - CAPITAL")),
              ("02/04/2024", sai("CPAIG", U, "DETERMINAÇÃO JUDICIAL")),
              ("03/04/2024", ent(U, "CPAIG - CAPITAL")), ("03/04/2024", "Instalado equipamento de monitoração eletrônica, autos %s." % pid),
              ("20/01/2025", sai(U, "CPAIG", "DETERMINAÇÃO JUDICIAL - RETORNO AO SEMIABERTO")),
              ("01/04/2025", ent("CENTRO PENAL AGROINDUSTRIAL DA GAMELEIRA", "UMMVE - CAPITAL")), ("10/09/2026", cela("CPAIG"))],
          unidade="CENTRO PENAL AGROINDUSTRIAL DA GAMELEIRA", data_prisao="01/03/2022", data_entrada="01/04/2025")
add(k, "Auditoria", "Monitoramento eletrônico desta execução lançado como interrupção",
    "O RSPE trata 02/04/2024 a 01/04/2025 como interrupção; a ficha mostra a pessoa monitorada pelos autos da execução de 03/04/2024 a 20/01/2025.",
    "Auditoria: 'verificar' - monitoramento desta execução de 03/04/2024 a 20/01/2025 tratado como interrupção (293 dias sem cômputo). "
    "A aba Progressão mantém a data do SEEU (15/06/2027), com ressalva.",
    "Monitoramento eletrônico pelos autos da execução é cumprimento de pena (LEP, art. 146-B), não liberdade. De 03/04/2024 a "
    "20/01/2025, contando os dois extremos: abril 28 + maio 31 + junho 30 + julho 31 + agosto 31 + setembro 30 + outubro 31 + "
    "novembro 30 + dezembro 31 + janeiro 20 = 293 dias. Política decidida: a aba mantém a data do SEEU e a Auditoria aponta.",
    r, [AUD(X, contem=["Monitoramento", "03/04/2024", "20/01/2025"]), AUD(X, contem=["Monitoramento", "293"]),
        C("prog", "eq", "15/06/2027")], f)

k = prox()
pc = proc_crim(k, 2021)
r = R(k, "01/03/2022", anos(8), "10/02/2022", ano_proc=2021, regime="Fechado - ATIVO", prog="15/06/2027", liv="15/06/2028",
      eventos=[prisao("01/03/2022", pc, "PRISÃO PREVENTIVA"), interr("02/05/2023", "LIBERDADE PROVISÓRIA"),
               prisao("20/05/2025", pc, "PRISÃO DEFINITIVA")], interrompidos=749)
f = FICHA(k, [("02/03/2022", ent("PTRAN", "DEPAC CENTRO")), ("02/05/2023", sai("PTRAN", "", "ALVARÁ DE SOLTURA: %s" % pc)),
              ("10/02/2024", ent(U, "DEPAC CENTRO")), ("10/02/2024", "Instalado equipamento de monitoração eletrônica, medida cautelar nos autos 0006543-21.2024.8.12.0001."),
              ("10/08/2024", sai(U, "", "RETIRADA DO EQUIPAMENTO - REVOGAÇÃO DA CAUTELAR")),
              ("20/05/2025", ent("PTRAN", "DEPAC CENTRO")), ("20/06/2025", ent("IPCG", "PTRAN - CAPITAL")), ("10/09/2026", cela("IPCG"))],
          data_prisao="20/05/2025", data_entrada="20/06/2025")
add(k, "Auditoria", "Monitoramento cautelar de outro processo durante a liberdade",
    "Em liberdade provisória nesta execução, a pessoa usou tornozeleira de 10/02/2024 a 10/08/2024 por cautelar de outros autos (0006543-21.2024).",
    "Nenhum item de monitoramento: a cautelar de outro processo não é cumprimento desta pena.",
    "O monitoramento só conta para esta execução se foi por ela (cumprimento, LEP, art. 146-B) ou por ação penal dela (detração, "
    "CP, art. 42; STJ, Tema 1155). Cautelar de outro processo não se aproveita aqui (vedada a conta-corrente de pena).",
    r, [AUD(X, presente=False, contem="Monitoramento")], f)

# Nova prisão depois de liberdade provisória: a conferir
k = prox()
pc = proc_crim(k, 2022)
r = R(k, "10/09/2022", anos(6), "20/08/2022", ano_proc=2022, prog="", liv="",
      eventos=[prisao("10/09/2022", pc, "PRISÃO PREVENTIVA"), interr("10/05/2023", "LIBERDADE PROVISÓRIA")],
      interrompidos=(GER - D("10/05/2023")).days)
f = FICHA(k, [("11/09/2022", ent("PTRAN", "DEPAC CENTRO")), ("10/05/2023", sai("PTRAN", "", "ALVARÁ DE SOLTURA")),
              ("03/04/2025", ent("PTRAN", "3ª DP CAMPO GRANDE")), ("10/09/2026", cela("PTRAN"))],
          unidade="PRESIDIO DE TRANSITO DE CAMPO GRANDE", data_prisao="03/04/2025", data_entrada="03/04/2025")
add(k, "Auditoria", "Nova prisão depois da liberdade provisória: em que processo?",
    "Solto por liberdade provisória em 10/05/2023; a ficha registra nova entrada vinda da 3ª DP em 03/04/2025, sem citar autos.",
    "Auditoria: 'verificar' - nova prisão na ficha em 03/04/2025, conferir em que processo; nenhum reinício lançado.",
    "A nova prisão pode ser desta execução (reinício: corre o cumprimento, CP, art. 117, V) ou de outro processo (suspensão: "
    "não corre a prescrição, CP, art. 116, p. único). A ficha não cita autos: os efeitos são opostos, então só se pode mandar conferir.",
    r, [AUD(X, contem=["Nova prisão", "03/04/2025"], nivel="verificar"), AUD(X, presente=False, contem="Reinício omitido")], f)

# RSPE sem evento de prisão
k = prox()
r = R(k, None, anos(5), "10/06/2025", ano_proc=2025, prog="", liv="", eventos=[], incidentes=[], regime="Fechado - ATIVO")
f = FICHA(k, [("16/08/2025", ent("PTRAN", "DEPAC CENTRO")), ("20/09/2025", ent("IPCG", "PTRAN - CAPITAL")), ("10/09/2026", cela("IPCG"))],
          data_prisao="14/08/2025", data_entrada="20/09/2025")
add(k, "Auditoria", "RSPE sem evento de prisão; ficha com a prisão",
    "O RSPE não tem nenhum evento; a ficha registra a prisão em 14/08/2025 (Data Prisão) e a entrada no PTRAN em 16/08/2025.",
    "Auditoria: alerta 'RSPE sem evento de prisão: início lançado pela ficha em 14/08/2025'.",
    "Sem o evento de prisão, o SEEU não conta nenhum dia de pena (LEP, arts. 105 e 106). A ficha prova a custódia desde 14/08/2025, "
    "posterior ao fato (10/06/2025): é o início do cumprimento/detração (CP, art. 42).",
    r, [AUD(X, contem=["sem evento de prisão", "14/08/2025"], nivel="alerta")], f)

# Retomada divergente
k = prox()
pc = proc_crim(k, 2021)
r = R(k, "01/02/2022", anos(8), "10/01/2022", ano_proc=2021, prog="20/09/2027", liv="20/09/2028",
      eventos=[prisao("01/02/2022", pc, "PRISÃO PREVENTIVA"), interr("10/05/2024", "FUGA"), prisao("01/12/2024", pc, "RECAPTURA")],
      interrompidos=205)
f = FICHA(k, [("02/02/2022", ent("PTRAN", "DEPAC CENTRO")), ("10/03/2022", ent("PENITENCIARIA ESTADUAL DE DOURADOS", "PTRAN - CAPITAL")),
              ("10/05/2024", sai("PED", "", "EVASÃO")), ("05/09/2024", ent("PENITENCIARIA ESTADUAL DE DOURADOS", "1ª DP DOURADOS - INTERIOR")),
              ("10/09/2026", cela("PED"))],
          unidade="PENITENCIARIA ESTADUAL DE DOURADOS", data_prisao="05/09/2024", data_entrada="05/09/2024")
add(k, "Auditoria", "Recaptura em 05/09/2024 na ficha; RSPE só reinicia em 01/12/2024",
    "Fuga em 10/05/2024; a ficha registra a recaptura (entrada vinda da 1ª DP de Dourados) em 05/09/2024; o RSPE só reinicia em 01/12/2024.",
    "Auditoria: alerta 'Retomada divergente: RSPE reinício em 01/12/2024, ficha entrada em 05/09/2024' - 87 dias de custódia fora da conta.",
    "Dias presos e não contados: 05/09/2024 a 30/11/2024 = setembro 26 (5 a 30) + outubro 31 + novembro 30 = 87. "
    "O cumprimento recomeça com a recaptura (LEP, art. 111; CP, art. 117, V); o tempo preso é pena cumprida.",
    r, [AUD(X, contem=["05/09/2024", "87 dias"], nivel="alerta"), AUD(X, contem=["Retomada divergente", "05/09/2024"])], f)

# Interrupção por fuga desmentida pela ficha: custódia contínua
k = prox()
pc = proc_crim(k, 2022)
r = R(k, "10/08/2022", anos(8), "15/07/2022", ano_proc=2022, prog="", liv="",
      eventos=[prisao("10/08/2022", pc, "PRISÃO PREVENTIVA"), interr("10/07/2025", "FUGA")], interrompidos=(GER - D("10/07/2025")).days)
f = FICHA(k, [("11/08/2022", ent("PTRAN", "DEPAC CENTRO")), ("20/09/2022", ent("PDIB", "PTRAN - CAPITAL")), ("10/06/2025", cela("PDIB")),
              ("15/08/2025", cela("PDIB")), ("20/02/2026", cela("PDIB")), ("10/09/2026", cela("PDIB"))],
          unidade="PENITENCIARIA ESTADUAL DE DOIS IRMAOS DO BURITI", data_prisao="10/08/2022", data_entrada="20/09/2022")
add(k, "Auditoria", "Fuga no RSPE, mas a ficha mostra a pessoa presa o tempo todo",
    "O RSPE interrompe por fuga em 10/07/2025; a ficha não tem fuga nem saída e registra mudanças de cela antes e depois (até 10/09/2026).",
    "Auditoria: alerta 'RSPE indica pena interrompida em 10/07/2025, mas a ficha registra custódia' e 'verificar' 'Fuga no RSPE em 10/07/2025 sem registro na ficha'.",
    "A ficha mostra a pessoa na PDIB em 10/06/2025, 15/08/2025, 20/02/2026 e 10/09/2026, sem saída, fuga ou evasão. A interrupção "
    "suspende a contagem da pena (LEP, art. 111) e a fuga é falta grave (LEP, art. 50, II): se não houve fuga, os dois efeitos "
    "prejudicam o assistido indevidamente.",
    r, [AUD(X, contem=["interrompida", "custódia"], nivel="alerta"), AUD(X, contem=["Fuga no RSPE", "sem registro na ficha"])], f)

# Fuga no RSPE que era soltura por alvará
k = prox()
pc = proc_crim(k, 2022)
r = R(k, "10/08/2022", anos(8), "15/07/2022", ano_proc=2022, prog="20/10/2027", liv="20/10/2028",
      eventos=[prisao("10/08/2022", pc, "PRISÃO PREVENTIVA"), interr("14/07/2025", "FUGA"), prisao("10/01/2026", pc, "RECAPTURA")],
      interrompidos=180)
f = FICHA(k, [("11/08/2022", ent("PTRAN", "DEPAC CENTRO")), ("20/09/2022", ent("PDIB", "PTRAN - CAPITAL")),
              ("14/07/2025", sai("PDIB", "", "ALVARÁ DE SOLTURA")), ("10/01/2026", ent("PTRAN", "DEPAC CENTRO")), ("10/09/2026", cela("PTRAN"))],
          unidade="PRESIDIO DE TRANSITO DE CAMPO GRANDE", data_prisao="10/01/2026", data_entrada="10/01/2026")
add(k, "Auditoria", "Fuga no RSPE no dia em que a ficha registra alvará de soltura",
    "O RSPE lança fuga em 14/07/2025; a ficha registra, no mesmo dia, saída por alvará de soltura.",
    "Auditoria: alerta 'Fuga no RSPE em 14/07/2025, mas a ficha registra saída por alvará de soltura' - pedir a retificação do evento.",
    "Saída por alvará é saída legítima, não fuga (LEP, art. 50, II exige fuga). A fuga lançada indevidamente traz falta grave, nova "
    "data-base e perda de remição (LEP, arts. 118 e 127): prejudica o assistido. Alerta.",
    r, [AUD(X, contem=["Fuga no RSPE", "alvará de soltura"], nivel="alerta")], f)

# =====================================================================================================================
# 2.7 Trabalho
# =====================================================================================================================
TR = dict(unidade="INSTITUTO PENAL DE CAMPO GRANDE", data_prisao="10/02/2024", data_entrada="20/03/2024")
BASE_TR = [("11/02/2024", ent("PTRAN", "DEPAC CENTRO")), ("20/03/2024", ent("IPCG", "PTRAN - CAPITAL"))]


def R_tr(k, **kw):
    return R(k, "10/02/2024", anos(8), "15/01/2024", ano_proc=2024, prog="20/09/2027", liv="20/09/2028", **kw)


k = prox()
r = R_tr(k)
f = FICHA(k, BASE_TR + [("03/02/2025", ini_trab("LAVANDERIA")), ("05/05/2025", ini_trab("PADARIA")),
                        ("30/05/2025", fim_trab("PADARIA", "A PEDIDO")), ("15/07/2025", fim_trab("LAVANDERIA", "IMPRODUTIVIDADE")),
                        ("10/09/2026", cela("IPCG"))], **TR)
add(k, "Ficha/Remição", "Dois setores ao mesmo tempo (lavanderia e padaria)",
    "Lavanderia iniciada em 03/02/2025; padaria iniciada em 05/05/2025 e baixada em 30/05/2025; lavanderia baixada em 15/07/2025.",
    "Lavanderia de 03/02/2025 a 15/07/2025 (simultânea); padaria de 05/05/2025 a 30/05/2025.",
    "A ficha registra a baixa da lavanderia só em 15/07/2025, depois de a padaria já ter acabado: os dois vínculos correram juntos. "
    "Não há baixa da lavanderia em 05/05/2025, logo ela não terminou ali. Os dias contam uma vez (LEP, art. 126).",
    r, [C("ficha", "regex", trab(f, "LAVANDERIA", "03/02/2025", "15/07/2025")), C("ficha", "regex", trab(f, "PADARIA", "05/05/2025", "30/05/2025"))], f)

k = prox()
r = R_tr(k)
f = FICHA(k, BASE_TR + [("10/01/2025", ini_trab("HORTA")), ("01/04/2025", ini_trab("COZINHA")),
                        ("20/06/2025", fim_trab("HORTA", "A PEDIDO")), ("10/09/2026", cela("IPCG"))], **TR)
add(k, "Ficha/Remição", "Baixa tardia: horta baixada com a cozinha ainda em curso",
    "Horta iniciada em 10/01/2025; cozinha iniciada em 01/04/2025 (sem baixa); horta baixada 'a pedido' só em 20/06/2025.",
    "A horta vai de 10/01/2025 a 20/06/2025 (a ficha prova o vínculo até a baixa); a cozinha segue em curso. Tese discutível: o programa "
    "declara encerrar a horta em 01/04/2025 e só anotar a baixa.",
    "A ficha é a prova do vínculo: a horta só foi baixada em 20/06/2025, a pedido (motivo de trabalho, não registro de saída). "
    "Trabalhos simultâneos são possíveis e os dias contam uma vez (LEP, art. 126). Pela leitura mais favorável e literal, a horta "
    "termina na baixa. A data da baixa tem de aparecer em qualquer caso.",
    r, [C("ficha", "contem", "20.06.2025"), dict(C("ficha", "regex", trab(f, "HORTA", "10/01/2025", "20/06/2025")), decisao=True,
                                                 nota="Tese discutível (relatório 2.7, baixa tardia): fim na baixa x fim suposto no início da cozinha.")], f)

k = prox()
r = R_tr(k)
f = FICHA(k, BASE_TR + [("03/03/2025", ini_trab("MARCENARIA")), ("03/03/2025", ini_trab("SERRALHERIA", "CI 11")),
                        ("05/05/2025", fim_trab("SERRALHERIA", "A PEDIDO")), ("10/08/2025", sai("IPCG", "EPJFC", "Transferência")),
                        ("10/08/2025", ent("EPJFC", "IPCG - CAPITAL")), ("10/09/2026", cela("EPJFC"))],
          unidade="ESTABELECIMENTO PENAL JAIR FERREIRA DE CARVALHO", data_prisao="10/02/2024", data_entrada="10/08/2025")
add(k, "Ficha/Remição", "Dois setores abertos no mesmo dia; só um baixado",
    "Marcenaria e serralheria iniciadas em 03/03/2025; serralheria baixada a pedido em 05/05/2025; transferência para o EPJFC em 10/08/2025.",
    "Serralheria de 03/03/2025 a 05/05/2025; marcenaria de 03/03/2025 a 10/08/2025 (transferência).",
    "São setores diferentes: a baixa da serralheria não encerra a marcenaria. Sem baixa própria, a marcenaria termina na saída da "
    "unidade (transferência de 10/08/2025), que encerra o trabalho daquela unidade.",
    r, [C("ficha", "regex", trab(f, "SERRALHERIA", "03/03/2025", "05/05/2025")), C("ficha", "regex", trab(f, "MARCENARIA", "03/03/2025", "10/08/2025"))], f)

k = prox()
r = R_tr(k, regime="Semiaberto - ATIVO", incidentes=[inc(REG, "Fechado - Regime Inicial", "", "10/02/2024"),
                                                    inc("PROGRESSÃO DE REGIME", "Semiaberto", "20/12/2024", "01/12/2024")])
f = FICHA(k, BASE_TR + [("20/12/2024", ent("CENTRO PENAL AGROINDUSTRIAL DA GAMELEIRA", "IPCG - CAPITAL")),
                        ("03/02/2025", ini_trab("CONSTRUTORA GAMA")),
                        ("03/02/2025", "Interno inicia atividade laboral externa na empresa CONSTRUTORA GAMA, conveniada, de segunda a sexta."),
                        ("10/09/2026", cela("CPAIG"))],
          unidade="CENTRO PENAL AGROINDUSTRIAL DA GAMELEIRA", data_prisao="10/02/2024", data_entrada="20/12/2024")
add(k, "Ficha/Remição", "Trabalho externo na empresa conveniada",
    "No semiaberto, início na CONSTRUTORA GAMA em 03/02/2025, com o lançamento 'inicia atividade laboral externa na empresa CONSTRUTORA GAMA'.",
    "Vínculo CONSTRUTORA GAMA desde 03/02/2025, em curso, marcado como trabalho externo.",
    "O lançamento do mesmo dia diz que a atividade é externa (LEP, arts. 36 e 37): o vínculo é de trabalho externo, o que importa "
    "para o inciso XI dos decretos de indulto (12 meses de trabalho externo).",
    r, [C("ficha", "regex", r'"inicio": "03\.02\.2025"[^}]*"setor": "CONSTRUTORA GAMA", "externo": true')], f)

k = prox()
r = R_tr(k)
f = FICHA(k, BASE_TR + [("05/02/2025", "Interno passa a trabalhar no setor de SERVIÇOS GERAIS, conforme CI 30/2025."),
                        ("10/04/2025", "Interno foi remanejado para o setor de ARTESANATO, conforme CI 41/2025."),
                        ("30/07/2025", fim_trab("IPCG ARTESANATO", "TÉRMINO DO CONTRATO")), ("10/09/2026", cela("IPCG"))], **TR)
add(k, "Ficha/Remição", "Trabalho em texto livre, remanejamento e grafia do setor",
    "'Passa a trabalhar no setor de SERVIÇOS GERAIS' (05/02/2025); 'remanejado para o setor de ARTESANATO' (10/04/2025); baixa do setor 'IPCG ARTESANATO' (30/07/2025).",
    "Serviços gerais de 05/02/2025 a 10/04/2025 (remanejado); artesanato de 10/04/2025 a 30/07/2025 (a baixa do 'IPCG ARTESANATO' é do mesmo setor).",
    "O remanejamento encerra o setor anterior e abre o novo na mesma data. 'IPCG ARTESANATO' é o artesanato do IPCG (sigla da "
    "unidade + nome do setor): a baixa encerra esse vínculo.",
    r, [C("ficha", "regex", r'"inicio": "05\.02\.2025", "fim": "10\.04\.2025", "setor": "[^"]*SERVI'),
        C("ficha", "regex", r'"inicio": "10\.04\.2025", "fim": "30\.07\.2025", "setor": "[^"]*ARTESANATO')], f)

k = prox()
r = R_tr(k)
f = FICHA(k, BASE_TR + [("06/01/2025", ini_trab("FAXINA")), ("06/01/2025", "Desconsiderar a função Faxina, interno trabalha na PRENDEBEM."),
                        ("10/09/2026", cela("IPCG"))], **TR)
add(k, "Ficha/Remição", "Correção da unidade: 'desconsiderar a função faxina'",
    "Em 06/01/2025: início na FAXINA e, no mesmo dia, 'Desconsiderar a função Faxina, interno trabalha na PRENDEBEM'.",
    "Só o vínculo PRENDEBEM, desde 06/01/2025, em curso; nenhuma faxina.",
    "A própria unidade corrigiu o lançamento: o vínculo da faxina não existiu e o trabalho é na Prendebem desde aquele dia.",
    r, [C("ficha", "regex", r'"inicio": "06\.01\.2025"[^}]*"setor": "[^"]*PRENDEBEM'), C("ficha", "nao_contem", '"setor": "FAXINA"')], f)

# =====================================================================================================================
# 2.8 Atestados de trabalho
# =====================================================================================================================
k = prox()
r = R_tr(k)
f = FICHA(k, BASE_TR + [("03/02/2025", ini_trab("LAVANDERIA")), ("30/04/2025", fim_trab("LAVANDERIA", "TÉRMINO")),
                        ("12/05/2025", "Emitido ATESTADO DE TRABALHO Nº 37/2025, função LAVANDERIA (03/02/2025 a 30/04/2025), totalizando "
                                       "75 (setenta e cinco) dias trabalhados e 25 (vinte e cinco) dias remidos."),
                        ("10/09/2026", cela("IPCG"))], **TR)
add(k, "Ficha/Remição", "Atestado com número curto e dias por extenso entre parênteses",
    "Atestado 'Nº 37/2025', lavanderia de 03/02/2025 a 30/04/2025, '75 (setenta e cinco) dias trabalhados e 25 (vinte e cinco) dias remidos'.",
    "Atestado 037/2025: 75 dias trabalhados, 25 remidos, período 03/02/2025 a 30/04/2025.",
    "O extenso entre parênteses só repete o algarismo. 75 dias trabalhados ÷ 3 = 25 dias remidos (LEP, art. 126, § 1º, II).",
    r, [C("ficha", "regex", r'"numero": "037/2025", "dias_trabalhados": 75, "dias_remidos": 25(\.0)?, "periodo_inicio": "03/02/2025", "periodo_fim": "30/04/2025"')], f)

k = prox()
r = R_tr(k)
f = FICHA(k, BASE_TR + [("01/03/2025", ini_trab("HORTA")), ("02/05/2025", ini_trab("COZINHA")), ("30/06/2025", fim_trab("COZINHA", "TÉRMINO")),
                        ("10/07/2025", "ATESTADO DE TRABALHO PRISIONAL Nº 052/2025 função HORTA (01/03/2025 A 30/04/2025) e função COZINHA "
                                       "(02/05/2025 A 30/06/2025) totalizando 96 dias trabalhados e 32 dias remidos."),
                        ("10/09/2026", cela("IPCG"))], **TR)
add(k, "Ficha/Remição", "Atestado com dois trechos (horta e cozinha)",
    "Atestado 052/2025: horta de 01/03/2025 a 30/04/2025 e cozinha de 02/05/2025 a 30/06/2025, total de 96 dias trabalhados e 32 remidos.",
    "Atestado 052/2025 com dois trechos, período 01/03/2025 a 30/06/2025, 96 trabalhados e 32 remidos.",
    "Cada setor com período é um trecho; o total (96 ÷ 3 = 32) vale para o atestado inteiro (LEP, art. 126).",
    r, [C("ficha", "regex", r'"numero": "052/2025", "dias_trabalhados": 96, "dias_remidos": 32(\.0)?, "periodo_inicio": "01/03/2025", "periodo_fim": "30/06/2025"'),
        C("ficha", "regex", r'"numero": "052/2025"[^\]]*"trechos": \[\{[^\]]*01/03/2025[^\]]*30/04/2025[^\]]*02/05/2025[^\]]*30/06/2025')], f)

for aberto in (False, True):
    k = prox()
    r = R_tr(k)
    evs = BASE_TR + [("01/08/2024", ini_trab("FAXINA"))]
    if not aberto:
        evs.append(("15/11/2024", fim_trab("FAXINA", "A PEDIDO")))
    evs += [("10/11/2024", "Emitido ATESTADO DE TRABALHO Nº 088/2024, função FAXINA (01/08/2025 A 31/10/2024), totalizando 78 dias "
                           "trabalhados e 26 dias remidos."), ("10/09/2026", cela("IPCG"))]
    f = FICHA(k, evs, **TR)
    tit = ("Ano digitado errado no atestado, com o trabalho já baixado" if not aberto else
           "Ano digitado errado no atestado, com o trabalho ainda sem baixa")
    add(k, "Ficha/Remição", tit,
        "Faxina desde 01/08/2024%s; atestado 088/2024 com o trecho '(01/08/2025 A 31/10/2024)', emitido em 10/11/2024."
        % (" (baixa em 15/11/2024)" if not aberto else " (sem baixa: em curso)"),
        "Atestado 088/2024 lido como 01/08/2024 a 31/10/2024 (ano corrigido, a conferir), 78 trabalhados e 26 remidos; a ficha mantém o "
        "trabalho%s." % ("" if not aberto else ", o atestado e o restante da leitura (o trabalho em curso não pode derrubar a análise)"),
        "O trecho '01/08/2025 a 31/10/2024' é impossível (início depois do fim) e o atestado foi emitido em 10/11/2024: 2025 é erro "
        "material evidente; o trabalho na faxina começou em 01/08/2024. 01/08/2024 a 31/10/2024 = 92 dias corridos, compatível com 78 "
        "dias trabalhados (segunda a sábado). 78 ÷ 3 = 26 (LEP, art. 126).",
        r, [C("ficha", "regex", r'"ano_corrigido": "[^"]+"[^}]*"numero": "088/2024"[^}]*"periodo_inicio": "01/08/2024", "periodo_fim": "31/10/2024"'),
            C("ficha", "regex", trab(f, "FAXINA", "01/08/2024", None if aberto else "15/11/2024"))], f)

k = prox()
r = R_tr(k)
f = FICHA(k, BASE_TR + [("01/02/2025", ini_trab("PADARIA")),
                        ("05/03/2025", "Foi encaminhado Atestado de trabalho prisional nº 019/2025."),
                        ("10/07/2025", "ATESTADO DE TRABALHO PRISIONAL Nº 124/2025 - DE 01/02/2025 - 30/06/2025"),
                        ("10/09/2026", cela("IPCG"))], **TR)
add(k, "Ficha/Remição", "Atestado sem dias e sem período; atestado só com o período",
    "'Foi encaminhado Atestado de trabalho prisional nº 019/2025' (sem dias nem período) e 'ATESTADO ... Nº 124/2025 - DE 01/02/2025 - 30/06/2025' (sem dias).",
    "Dois atestados: 019/2025 sem dias e sem período; 124/2025 cobrindo 01/02/2025 a 30/06/2025, dias desconhecidos.",
    "O texto não traz os dias: não se inventa número de dias (LEP, art. 126 exige a prova do trabalho). O 124/2025 tem o período; "
    "o 019/2025 nem isso.",
    r, [C("ficha", "regex", r'"numero": "019/2025", "dias_trabalhados": (0|null), "dias_remidos": (0|0\.0|null), "periodo_inicio": (""|null)'),
        C("ficha", "regex", r'"numero": "124/2025", "dias_trabalhados": (0|null)[^}]*"periodo_inicio": "01/02/2025", "periodo_fim": "30/06/2025"')], f)

k = prox()
r = R_tr(k)
pid = r["processo_execucao"]
f = FICHA(k, BASE_TR + [("02/02/2025", ini_trab("COZINHA")), ("30/05/2025", fim_trab("COZINHA", "TÉRMINO")),
                        ("05/06/2025", "Emitido ATESTADO DE TRABALHO Nº 061/2025, função COZINHA (02/02/2025 a 30/05/2025), totalizando "
                                       "90 dias trabalhados e 30 dias remidos."),
                        ("10/06/2025", "Atestado de Trabalho nº 61/2025 enviado via ESAJ nos autos %s." % pid), ("10/09/2026", cela("IPCG"))], **TR)
add(k, "Ficha/Remição", "Atestado enviado pelo ESAJ conta como peticionado",
    "Atestado 061/2025 (90 trabalhados, 30 remidos) emitido em 05/06/2025 e, em 10/06/2025, 'enviado via ESAJ nos autos' da execução. RSPE sem remição.",
    "Um só atestado (061/2025), peticionado em 10/06/2025 (envio pelo ESAJ); a comparação mostra 30 dias da ficha e 0 no RSPE, "
    "documento já peticionado aguardando decisão (não 'sem peticionamento').",
    "O envio ao juízo pelo ESAJ é peticionamento (LEP, art. 129: a unidade encaminha os dias trabalhados ao juízo). O lançamento "
    "do envio não é outro atestado.",
    r, [C("ficha", "regex", r'"numero": "061/2025"'), C("ficha", "nao_contem", '"numero": "061/2025", "dias_trabalhados": 0'),
        C("fd_remidos", "eq", "30 / 0"), C("fd_sit", "nao_contem", "sem peticionamento")], f)

k = prox()
r = R_tr(k)
f = FICHA(k, BASE_TR + [("02/01/2025", ini_trab("HORTA")), ("31/03/2025", fim_trab("HORTA", "TÉRMINO")),
                        ("05/04/2025", "Emitido ATESTADO DE TRABALHO Nº 022/2025, função HORTA (02/01/2025 a 31/03/2025), totalizando "
                                       "75 dias trabalhados e 25 dias remidos."),
                        ("20/04/2025", "ATESTADO DE TRABALHO Nº 022/2025 RETIFICADO, função HORTA (02/01/2025 a 31/03/2025), totalizando "
                                       "66 dias trabalhados e 22 dias remidos."),
                        ("10/09/2026", cela("IPCG"))], **TR)
add(k, "Ficha/Remição", "Atestado retificado substitui o anterior de mesmo número",
    "Atestado 022/2025 com 75/25 e, depois, o mesmo 022/2025 'RETIFICADO' com 66 trabalhados e 22 remidos.",
    "Um só atestado 022/2025, com 66 trabalhados e 22 remidos (não soma 47).",
    "A retificação corrige o documento; somar os dois contaria o mesmo trabalho duas vezes. Vale o retificado: 66 ÷ 3 = 22.",
    r, [C("ficha", "regex", r'"numero": "022/2025", "dias_trabalhados": 66, "dias_remidos": 22'),
        C("ficha", "nao_contem", '"dias_trabalhados": 75'), C("ficha", "regex", r'"dias_remidos_atestados": 22(\.0)?\b')], f)

k = prox()
r = R_tr(k)
f = FICHA(k, BASE_TR + [("02/01/2025", ini_trab("HORTA")), ("31/03/2025", fim_trab("HORTA", "TÉRMINO")),
                        ("05/04/2025", "Emitido ATESTADO DE TRABALHO Nº 030/2025, função HORTA (02/01/2025 a 31/03/2025), totalizando "
                                       "75 dias trabalhados e 25 dias remidos."),
                        ("22/04/2025", "O atestado nº 030/2025 deverá ser substituído pelo atestado nº 045/2025, função HORTA (02/01/2025 a "
                                       "31/03/2025), totalizando 69 dias trabalhados e 23 dias remidos."),
                        ("10/09/2026", cela("IPCG"))], **TR)
add(k, "Ficha/Remição", "Atestado substituído por outro de número diferente",
    "Atestado 030/2025 (75/25) e, depois, 'o atestado nº 030/2025 deverá ser substituído pelo atestado nº 045/2025' com 69/23.",
    "Só o atestado 045/2025, com 69 trabalhados e 23 remidos; o 030/2025 sai da lista.",
    "O substituído deixa de valer; contar os dois dobraria o mesmo período (02/01 a 31/03/2025).",
    r, [C("ficha", "regex", r'"numero": "045/2025", "dias_trabalhados": 69, "dias_remidos": 23'), C("ficha", "nao_contem", '"numero": "030/2025"')], f)

# =====================================================================================================================
# 2.9 a 2.12 Estudo, leitura, exames e saídas temporárias
# =====================================================================================================================
k = prox()
r = R_tr(k)
f = FICHA(k, BASE_TR + [("03/02/2025", "EDUCAÇÃO: Matriculou-se na Série: 1ª ETAPA EJA MÉDIO Turma: A Período: MATUTINO"),
                        ("30/06/2025", "EDUCAÇÃO: Interno foi desligado da Escola a próprio pedido."),
                        ("10/07/2025", "Atestado de estudo ATP Nº 15/2025 Tipo: Estudante; Data Inicial: 03/02/2025; Data Final: 30/06/2025; "
                                       "Tempo de Estudo: 240 h/a, com 20 dias a serem remidos."),
                        ("10/09/2026", cela("IPCG"))], **TR)
add(k, "Ficha/Remição", "Matrícula, desligamento da escola e atestado de estudo",
    "Matrícula na 1ª etapa da EJA médio em 03/02/2025; desligado da escola a pedido em 30/06/2025; atestado de estudo de 240 horas-aula (20 dias).",
    "Estudo de 03/02/2025 a 30/06/2025 (desligado da escola); atestado de estudo com 240 h e 20 dias a remir; RSPE sem remição: 20 dias a conferir.",
    "LEP, art. 126, § 1º, I: 1 dia de pena a cada 12 horas de frequência escolar. 240 ÷ 12 = 20 dias.",
    r, [C("fd_novo", "regex", r"EJA[^\"]*03/02/2025 a 30/06/2025"), C("fd_novo", "regex", r"[Ee]studo[^\"]*20|20[^\"]*[Ee]studo"),
        C("fd_remidos", "regex", r"^20 / 0")], f)

k = prox()
r = R(k, "10/04/2019", anos(12), "15/03/2019", ano_proc=2019, prog="10/04/2028", liv="10/04/2029")
f = FICHA(k, [("11/04/2019", ent("PTRAN", "DEPAC CENTRO")), ("20/05/2019", ent("IPCG", "PTRAN - CAPITAL")),
              ("15/12/2020", "Atestado de Remição por Leitura nº 71/2020 - CICLO Nº 03/2020 - obra lida: O ALIENISTA, relatório aprovado."),
              ("10/09/2026", cela("IPCG"))], data_prisao="10/04/2019", data_entrada="20/05/2019")
add(k, "Ficha/Remição", "Leitura por ciclo grafado 'CICLO Nº 03/2020'",
    "Atestado de remição por leitura nº 71/2020, 'CICLO Nº 03/2020', uma obra (O Alienista), relatório aprovado; RSPE sem remição.",
    "Leitura reconhecida: 1 obra, 4 dias na comparação da remição (não 'sem o número de obras').",
    "Uma obra lida com relatório aprovado = 4 dias de remição (Recomendação CNJ 44/2013, art. 1º, V, vigente em 2020; hoje Resolução "
    "CNJ 391/2021, art. 5º). O 'Nº' antes do número do ciclo não muda o sentido.",
    r, [C("fd_novo", "regex", r"[Ll]eitura[^\"]*1 obra"), C("fd_novo", "nao_contem", "sem o número de obras"), C("fd_remidos", "regex", r"^4 / 0")], f)

k = prox()
r = R_tr(k)
f = FICHA(k, BASE_TR + [("20/05/2025", "Peticionado Relatórios de Leitura referentes aos meses 03 e 04 de 2025, LIVROS: O PRIMO BASÍLIO E "
                                       "MEMÓRIAS PÓSTUMAS DE BRÁS CUBAS, nos autos %s." % r["processo_execucao"]),
                        ("10/09/2026", cela("IPCG"))], **TR)
add(k, "Ficha/Remição", "Relatórios de leitura de dois meses com dois livros",
    "Peticionados relatórios de leitura dos meses 03 e 04 de 2025, livros O Primo Basílio e Memórias Póstumas de Brás Cubas; RSPE sem remição.",
    "Leitura de 2 obras = 8 dias na comparação (peticionada, a decidir).",
    "Resolução CNJ 391/2021, art. 5º: 4 dias por obra lida, até 12 obras por ano. 2 × 4 = 8 dias.",
    r, [C("fd_novo", "regex", r"[Ll]eitura[^\"]*2 obras"), C("fd_remidos", "regex", r"^8 / 0")], f)

# exames: ENCCEJA certificado x ENEM (Decreto 12.790/2025, art. 9º, XIII)
for exame in ("ENCCEJA", "ENEM"):
    k = prox()
    r = R(k, "10/02/2023", anos(6), "20/01/2023", ano_proc=2023, prog="10/05/2027", liv="10/05/2028")
    txt = ("Certificado de conclusão do ensino fundamental - ENCCEJA 2024 - certificado de conclusão emitido pela Secretaria de Educação."
           if exame == "ENCCEJA" else "Peticionado certificado do ENEM 2024 nos autos %s." % r["processo_execucao"])
    f = FICHA(k, [("11/02/2023", ent("PTRAN", "DEPAC CENTRO")), ("20/03/2023", ent("IPCG", "PTRAN - CAPITAL")), ("10/04/2025", txt),
                  ("10/09/2026", cela("IPCG"))], data_prisao="10/02/2023", data_entrada="20/03/2023")
    if exame == "ENCCEJA":
        add(k, "Indulto", "ENCCEJA com certificado de conclusão (inciso XIII)",
            "Certificado de conclusão do ensino fundamental pelo ENCCEJA 2024, registrado em 10/04/2025, durante a execução (presa desde 10/02/2023).",
            "Indulto 2025, inciso XIII: requisito da conclusão de curso atendido pela ficha (ENCCEJA certificado em 10/04/2025).",
            "Decreto 12.790/2025, art. 9º, XIII: pena ≤ 12 anos (6), 1/5 cumprido até 25/12/2025 (1/5 de 6 anos = 438 dias; de 10/02/2023 a "
            "25/12/2025 = 1.050 dias), primário, e curso fundamental concluído e certificado durante a execução nos 3 anos anteriores a "
            "25/12/2025 (desde 26/12/2022): o certificado é de 10/04/2025. Furto qualificado não é impeditivo (art. 1º).",
            r, [C("det25", "regex", r"✔ XIII:[^\n]*ENCCEJA")], f)
    else:
        add(k, "Indulto", "ENEM peticionado não é conclusão certificada (inciso XIII)",
            "Só 'Peticionado certificado do ENEM 2024' (10/04/2025).",
            "Indulto 2025, inciso XIII: a verificar (o ENEM não certifica a conclusão do ensino médio desde 2017; a petição não prova certificado).",
            "O inciso XIII exige curso concluído e certificado por autoridade educacional. Desde 2017 o ENEM não certifica o ensino médio "
            "(Portaria MEC/INEP; a certificação passou ao ENCCEJA), e a mera petição não demonstra o certificado. Fica a conferir, não atendido de plano.",
            r, [C("det25", "regex", r"\? XIII:[^\n]*ENEM")], f)

# saídas temporárias (inciso XI)
k = prox()
pc = proc_crim(k, 2018)
r = R(k, "10/02/2019", anos(10), "20/01/2019", ano_proc=2018, regime="Semiaberto - ATIVO", prog="10/06/2027", liv="10/06/2028",
      incidentes=[inc(REG, "Fechado - Regime Inicial", "", "10/02/2019"), inc("PROGRESSÃO DE REGIME", "Semiaberto", "10/02/2022", "10/01/2022")])
G = "CENTRO PENAL AGROINDUSTRIAL DA GAMELEIRA"
evs = [("11/02/2019", ent("PTRAN", "DEPAC CENTRO")), ("10/02/2022", ent(G, "PTRAN - CAPITAL"))]
for s, v in (("20/12/2023", "27/12/2023"), ("02/04/2024", "08/04/2024"), ("08/08/2024", "14/08/2024"), ("19/12/2024", "26/12/2024"),
             ("15/04/2025", "21/04/2025")):
    evs += [(s, "Saída confirmada do benefício de: SAÍDA TEMPORÁRIA"), (v, "Retorno confirmado do benefício de: SAÍDA TEMPORÁRIA")]
evs += [("10/08/2025", "Beneficiado com saída temporária, devendo retornar em 16/08/2025."), ("10/09/2026", cela("CPAIG"))]
f = FICHA(k, evs, unidade=G, data_prisao="10/02/2019", data_entrada="10/02/2022")
add(k, "Indulto", "Cinco saídas temporárias usufruídas (inciso XI) e uma concessão sem registro",
    "No semiaberto, cinco saídas temporárias com saída e retorno confirmados (12/2023 a 04/2025) e uma concessão de 10/08/2025 sem registro de saída ou retorno.",
    "Indulto 2025, inciso XI: as 5 saídas temporárias usufruídas atendem o requisito das saídas (a concessão de 08/2025 é duvidosa e não conta).",
    "Decreto 12.790/2025, art. 9º, XI: pena ≤ 12 anos (10), 1/3 cumprido até 25/12/2025 (1/3 de 10 anos = 1.216 dias; de 10/02/2019 a "
    "25/12/2025 = 2.511 dias), em semiaberto, com no mínimo cinco saídas temporárias usufruídas (LEP, art. 122). Cinco pares saída/"
    "retorno confirmados = 5 saídas. A concessão sem saída nem retorno não prova o usufruto.",
    r, [C("det25", "regex", r"✔ XI:[^\n]*5 sa[ií]das")], f)

# =====================================================================================================================
# 2.13 Faltas disciplinares
# =====================================================================================================================
FT = dict(unidade="INSTITUTO PENAL DE CAMPO GRANDE", data_prisao="10/02/2024", data_entrada="20/03/2024")


def R_ft(k, **kw):
    kw.setdefault("prog", "20/09/2027")
    kw.setdefault("liv", "20/09/2028")
    return R(k, "10/02/2024", anos(8), "15/01/2024", ano_proc=2024, **kw)


REG_F = ("CONSELHO DISCIPLINAR: REGISTRO DE FALTA DISCIPLINAR COM FULCRO NO ART. 60 DA LEP, POR TER INFRINGINDO EM TESE O ART 50, "
         "INCISO VI DA LEP, COMETIDA EM %s. RESPONDE PROCESSO - PADIC/IPCG.")

k = prox()
r = R_ft(k)
f = FICHA(k, BASE_TR + [("03/03/2025", REG_F % "02/03/2025"),
                        ("10/03/2025", "CONSELHO DISCIPLINAR: INSTAURAÇÃO PROCESSO - PADIC / IPCG Nº 31/700.100/2025, REFERENTE A LANÇAMENTO DE "
                                       "FALTA DISCIPLINAR COMETIDA EM 02/03/2025."),
                        ("20/04/2025", "CONSELHO DISCIPLINAR: TOMOU CIÊNCIA DO RESULTADO PROCESSO - PADIC / IPCG Nº 31/700.100/2025, REFERENTE "
                                       "AO FATO OCORRIDO EM 02/03/2025, SANCIONADO COM FALTA DISCIPLINAR DE NATUREZA GRAVE."),
                        ("10/09/2026", cela("IPCG"))], **FT)
add(k, "Geral", "Falta grave com PADIC sancionado pelo Conselho, ausente do RSPE",
    "Registro de falta (art. 50, VI, fato de 02/03/2025), PADIC 31/700.100/2025 instaurado e resultado 'sancionado com falta de natureza grave'. O RSPE não tem a falta.",
    "Uma falta só na ficha: fato 02/03/2025, art. 50, VI, grave, homologada/punida pelo Conselho; entra como falta grave a apurar (incidente pendente 'FALTA GRAVE NA FICHA DISCIPLINAR' na lista de faltas).",
    "Registro, instauração e resultado são o mesmo fato (mesma data, mesmo PADIC): uma falta. A sanção do Conselho não é o "
    "reconhecimento judicial que produz os efeitos da falta grave (LEP, art. 118, § 2º; Súmula 533/STJ exige PAD, e os efeitos "
    "de regressão/data-base dependem do juiz): a falta fica a apurar, não homologada. Fato em 02/03/2025, dentro dos 12 meses do "
    "Decreto 12.790/2025, art. 6º.",
    r, [C("ficha", "regex", r'"faltas": \[\{[^\]]*02/03/2025[^\]]*\}\]'), C("ficha", "regex", r'"faltas": \[\{[^{\]]*\}\]'),
        C("faltas_itens", "regex", r"FALTA GRAVE NA FICHA[^\"]*02/03/2025[^}]*\"padrao\": \"apurar\"")], f)

k = prox()
r = R_ft(k)
f = FICHA(k, BASE_TR + [("06/05/2025", REG_F % "05/05/2025"),
                        ("15/06/2025", "CONSELHO DISCIPLINAR: TOMOU CIÊNCIA DO RESULTADO PROCESSO - PADIC / IPCG Nº 31/700.200/2025, REFERENTE "
                                       "AO FATO OCORRIDO EM 05/05/2025, SANCIONADO COM FALTA DISCIPLINAR DE NATUREZA MÉDIA."),
                        ("10/09/2026", cela("IPCG"))], **FT)
add(k, "Geral", "PADIC desclassifica a falta para média",
    "Registro de falta do art. 50, VI (fato 05/05/2025); o Conselho conclui por falta de natureza MÉDIA.",
    "Falta de 05/05/2025 de natureza média (não grave); não entra como falta grave a apurar.",
    "A natureza fixada no resultado prevalece sobre a capitulação inicial do registro. Falta média não produz os efeitos do art. 118 "
    "da LEP nem impede o indulto (Decreto 12.790/2025, art. 6º fala só em falta grave).",
    r, [C("ficha", "regex", r'"faltas": \[\{[^\]]*05\.05\.2025'), C("faltas_itens", "nao_contem", "05/05/2025")], f)

for justificada in (False, True):
    k = prox()
    r = R_ft(k, regime="Semiaberto - ATIVO", incidentes=[inc(REG, "Fechado - Regime Inicial", "", "10/02/2024"),
                                                         inc("PROGRESSÃO DE REGIME", "Semiaberto", "20/12/2024", "01/12/2024")])
    res = ("03-ACATADA A JUSTIFICATIVA, FALTA JUSTIFICADA - ARQUIVADO." if justificada else
           "03-SANCIONADO ADMINISTRATIVAMENTE COM FALTA DE NATUREZA GRAVE.")
    f = FICHA(k, BASE_TR + [("20/12/2024", ent(G, "IPCG - CAPITAL")),
                            ("16/05/2025", "01-FALTOU AO PERNOITE DO DIA 14/05/2025 02-INSTAURADA CDS Nº 22/2025 " + res),
                            ("10/09/2026", cela("CPAIG"))], unidade=G, data_prisao="10/02/2024", data_entrada="20/12/2024")
    if not justificada:
        add(k, "Geral", "CD simplificada do semiaberto: falta ao pernoite sancionada como grave",
            "Lançamento de 16/05/2025: '01-FALTOU AO PERNOITE DO DIA 14/05/2025 02-INSTAURADA CDS Nº 22/2025 03-SANCIONADO ... NATUREZA GRAVE'.",
            "Falta grave de 14/05/2025 (CDS 22/2025), sancionada; sem registro no RSPE: falta grave a apurar.",
            "A data do fato é a do pernoite descumprido (14/05/2025), não a do lançamento. Sancionada como grave pela comissão; sem "
            "decisão judicial no RSPE, fica a apurar (LEP, arts. 50 e 118).",
            r, [C("ficha", "regex", r'"faltas": \[\{[^\]]*"data_fato": "14\.05\.2025"'), C("faltas_itens", "regex", r"FALTA GRAVE NA FICHA[^\"]*14/05/2025[^}]*\"padrao\": \"apurar\"")], f)
    else:
        add(k, "Geral", "CD simplificada com falta justificada (arquivada)",
            "Mesmo lançamento, mas com '03-ACATADA A JUSTIFICATIVA, FALTA JUSTIFICADA - ARQUIVADO'.",
            "Falta de 14/05/2025 arquivada, sem efeito; nada a apurar.",
            "Falta justificada não é falta: não há infração disciplinar a punir nem efeito (LEP, art. 59: só se aplica sanção após "
            "apuração; justificada, arquiva-se).",
            r, [C("faltas_itens", "nao_contem", "14/05/2025")], f)

k = prox()
r = R_ft(k)
f = FICHA(k, BASE_TR + [("12/06/2025", "CONSELHO DISCIPLINAR: ISOLADO PREVENTIVAMENTE EM CELA DISCIPLINAR - LANÇAMENTO DE FALTA DISCIPLINAR "
                                       "COMETIDA EM 30/12/1899 - RESPONDE PADIC/IPCG."),
                        ("10/09/2026", cela("IPCG"))], **FT)
add(k, "Geral", "Isolamento preventivo com data de fato nula (30/12/1899)",
    "'ISOLADO PREVENTIVAMENTE EM CELA DISCIPLINAR - ... FALTA ... COMETIDA EM 30/12/1899 - RESPONDE PADIC' em 12/06/2025, sem outro registro.",
    "Falta de 12/06/2025 (data do lançamento), PADIC instaurado, indício de falta grave a apurar; não uma falta de 1899.",
    "30/12/1899 é a data nula do sistema, não o fato. O isolamento preventivo (LEP, art. 60) só cabe na apuração de falta grave: "
    "há indício de falta grave em 12/06/2025, a apurar até o resultado.",
    r, [C("ficha", "regex", r'"faltas": \[\{[^\]]*"data_fato": "12\.06\.2025"'), C("faltas_itens", "regex", r"FALTA GRAVE NA FICHA[^\"]*12/06/2025[^}]*\"padrao\": \"apurar\"")], f)

k = prox()
r = R_ft(k)
f = FICHA(k, BASE_TR + [("18/08/2025", cela("IPCG", "SANCIONADO - CI 12/2025", "CELA DISCIPLINAR 1")),
                        ("18/08/2025", "Deixa de estudar por estar sancionado, respondendo por falta disciplinar."),
                        ("10/09/2026", cela("IPCG"))], **FT)
add(k, "Geral", "Sanção em cela disciplinar sem o lançamento da falta",
    "Em 18/08/2025: mudança para a cela disciplinar 'Motivo: SANCIONADO - CI 12/2025' e 'deixa de estudar por estar sancionado, respondendo por falta disciplinar'; nenhum registro da falta.",
    "Falta de 18/08/2025 inferida da sanção (isolamento indica falta grave), natureza e homologação não informadas; a apurar.",
    "O isolamento em cela disciplinar só se aplica à falta grave (LEP, art. 53, IV, e art. 57, p. único). Há sanção sem o registro "
    "da falta: fato a apurar na data do lançamento.",
    r, [C("ficha", "regex", r'"faltas": \[\{[^\]]*"data_fato": "18\.08\.2025", [^\]]*"grave": true'), C("faltas_itens", "regex", r"FALTA GRAVE NA FICHA[^\"]*18/08/2025[^}]*\"padrao\": \"apurar\"")], f)

for com_palavra in (True, False):
    k = prox()
    r = R_ft(k, regime="Semiaberto - ATIVO", incidentes=[inc(REG, "Fechado - Regime Inicial", "", "10/02/2024"),
                                                         inc("PROGRESSÃO DE REGIME", "Semiaberto", "20/12/2024", "01/12/2024")])
    reg = ("REGRESSÃO DE REGIME: decisão judicial reconhece a falta grave pela evasão de 05/02/2025 e regride o interno ao regime fechado."
           if com_palavra else "REGRESSÃO DE REGIME: decisão judicial regride o interno ao regime fechado em razão da evasão de 05/02/2025.")
    f = FICHA(k, BASE_TR + [("20/12/2024", ent(G, "IPCG - CAPITAL")), ("05/02/2025", sai("CPAIG", "", "EVASÃO")),
                            ("20/03/2025", ent("PTRAN", "RECAPTURA - CAPITAL")), ("10/04/2025", ent("PDIB", "PTRAN - CAPITAL")),
                            ("10/05/2025", reg), ("10/09/2026", cela("PDIB"))],
              unidade="PENITENCIARIA ESTADUAL DE DOIS IRMAOS DO BURITI", data_prisao="20/03/2025", data_entrada="10/04/2025")
    add(k, "Geral", "Regressão judicial pela evasão %s a palavra 'falta'" % ("com" if com_palavra else "sem"),
        "Evasão do semiaberto em 05/02/2025, recaptura em 20/03/2025 e, em 10/05/2025, '%s'. O RSPE não tem fuga nem regressão." % reg,
        "Falta grave de 05/02/2025 reconhecida pelo juízo (homologada) na lista da ficha; Auditoria: alerta 'Regressão registrada na ficha em 10/05/2025 e ausente no RSPE'.",
        "A decisão que regride pela evasão reconhece a falta grave do art. 50, II, da LEP (LEP, art. 118, I), com ou sem a palavra "
        "'falta' no lançamento. A regressão não lançada no SEEU deixa o cálculo em regime errado: alerta.",
        r, [C("ficha", "regex", r'"faltas": \[\{[^\]]*"data_fato": "05\.02\.2025"[^\]]*homolog'), AUD(X, contem=["Regressão", "10/05/2025"]),
            AUD(X, presente=False, contem=["semiaberto", "regime fechado"], nivel="alerta")], f)

FALSAS = [("Tentativa de fuga frustrada pelos agentes; interno contido na muralha e reconduzido à cela.", "tentativa de fuga frustrada"),
          ("Interno beneficiado com saída temporária de 20/12/2025 a 26/12/2025, advertido de que o não retorno no prazo implica sanção, "
           "sob pena de evasão.", "sob pena de evasão"),
          ("Escoltado ao Hospital Regional para consulta; até o término do plantão NÃO RETORNOU.", "escolta hospitalar")]
for txt, rot in FALSAS:
    k = prox()
    r = R_ft(k)
    evs = BASE_TR + [("14/04/2025" if rot != "sob pena de evasão" else "19/12/2025", txt)]
    if rot == "escolta hospitalar":
        evs += [("15/04/2025", "Interno hospitalizado, permanece sob escolta."), ("20/04/2025", "Retornou do hospital à unidade.")]
    if rot == "sob pena de evasão":
        evs += [("20/12/2025", "Saída confirmada do benefício de: SAÍDA TEMPORÁRIA"), ("26/12/2025", "Retorno confirmado do benefício de: SAÍDA TEMPORÁRIA")]
    evs += [("10/09/2026", cela("IPCG"))]
    f = FICHA(k, evs, **FT)
    add(k, "Geral", "Falsa fuga: '%s'" % rot,
        "A ficha diz '%s', sem fuga consumada: a pessoa segue na unidade." % txt,
        "Nenhuma fuga/evasão lida da ficha: sem incidente 'FALTA GRAVE - FUGA/EVASÃO NA FICHA'.",
        {"tentativa de fuga frustrada": "Tentativa frustrada não é fuga: a pessoa não saiu da custódia (não houve interrupção, LEP, art. 111). "
                                        "A tentativa é punida como falta consumada (LEP, art. 49, p. único), mas só com registro e apuração "
                                        "da falta; aqui não há registro. O que se testa é a leitura de 'fuga' onde não houve.",
         "sob pena de evasão": "'Sob pena de evasão' é advertência, e a saída e o retorno estão confirmados: não houve evasão (LEP, art. 50, II).",
         "escolta hospitalar": "O 'não retornou' é do hospital (internação), seguido de 'hospitalizado' e do retorno à unidade: não houve "
                               "fuga (LEP, art. 50, II)."}[rot],
        r, [C("faltas_itens", "nao_contem", "FUGA/EVAS")], f)

k = prox()
r = R(k, "05/06/2021", anos(8), "10/05/2021", ano_proc=2021, prog="20/09/2027", liv="20/09/2028")
f = FICHA(k, [("06/06/2021", ent("PTRAN", "DEPAC CENTRO")), ("20/07/2021", ent("IPCG", "PTRAN - CAPITAL")), ("11/03/2022", REG_F % "10/03/2022"),
              ("20/03/2022", "CONSELHO DISCIPLINAR: INSTAURAÇÃO PROCESSO - PADIC / IPCG Nº 31/650.300/2022, REFERENTE A LANÇAMENTO DE FALTA "
                             "DISCIPLINAR COMETIDA EM 10/03/2022."),
              ("10/09/2026", cela("IPCG"))], data_prisao="05/06/2021", data_entrada="20/07/2021")
add(k, "Geral", "Falta grave de 2022 nunca julgada: prescrita",
    "Falta do art. 50, VI, de 10/03/2022, PADIC instaurado em 20/03/2022 e sem resultado até a impressão (02/10/2026).",
    "Falta prescrita: não entra como falta a apurar.",
    "Prescrição da falta disciplinar: na falta de lei, o STJ aplica o menor prazo do art. 109 do CP, 3 anos (art. 109, VI). Do fato "
    "(10/03/2022) até 09/03/2025 sem decisão: prescrita. Também está fora dos 12 meses do Decreto 12.790/2025, art. 6º.",
    r, [C("faltas_itens", "nao_contem", "FALTA GRAVE NA FICHA")], f)

k = prox()
r = R(k, "05/06/2021", anos(8), "10/05/2021", ano_proc=2021, prog="20/09/2027", liv="20/09/2028")
f = FICHA(k, [("06/06/2021", ent("PTRAN", "DEPAC CENTRO")), ("20/07/2021", ent("IPCG", "PTRAN - CAPITAL")), ("06/05/2023", REG_F % "05/05/2023"),
              ("20/06/2023", "CONSELHO DISCIPLINAR: TOMOU CIÊNCIA DO RESULTADO PROCESSO - PADIC / IPCG Nº 31/660.400/2023, REFERENTE AO FATO "
                             "OCORRIDO EM 05/05/2023, SANCIONADO COM FALTA DISCIPLINAR DE NATUREZA GRAVE."),
              ("10/09/2026", cela("IPCG"))], conduta="MÁ", data_prisao="05/06/2021", data_entrada="20/07/2021")
add(k, "Auditoria", "Conduta 'má' sem falta há mais de 3 anos",
    "Conduta 'MÁ' no cabeçalho da ficha (impressa em 02/10/2026); a última falta é de 05/05/2023.",
    "Auditoria: alerta 'Conduta na ficha: má, sem falta nos últimos 12 meses' - pedir o atestado de conduta atualizado.",
    "A conduta rebaixada pela falta se reabilita com o tempo sem nova falta (RIBUP-MS, art. 133: até 12 meses para a falta grave). "
    "Da falta (05/05/2023) a hoje passaram mais de 3 anos: a conduta 'má' está desatualizada e prejudica o requisito subjetivo da "
    "progressão (LEP, art. 112, § 1º).",
    r, [AUD(X, contem=["Conduta na ficha", "má"], nivel="alerta")], f)

k = prox()
r = R(k, "01/06/2024", anos(6), "10/05/2024", ano_proc=2024, prog="", liv="")
f = FICHA(k, [("10/01/2022", ent("PTRAN", "DEPAC CENTRO")), ("05/03/2022", REG_F % "04/03/2022"),
              ("20/04/2022", "CONSELHO DISCIPLINAR: TOMOU CIÊNCIA DO RESULTADO PROCESSO - PADIC / PTRAN Nº 31/640.500/2022, REFERENTE AO FATO "
                             "OCORRIDO EM 04/03/2022, SANCIONADO COM FALTA DISCIPLINAR DE NATUREZA GRAVE."),
              ("10/10/2022", sai("PTRAN", "", "ALVARÁ DE SOLTURA")), ("02/06/2024", ent("PTRAN", "DEPAC CENTRO")),
              ("10/07/2024", ent("IPCG", "PTRAN - CAPITAL")), ("10/09/2026", cela("IPCG"))], data_prisao="01/06/2024", data_entrada="10/07/2024")
add(k, "Auditoria", "Falta grave de execução anterior (2022)",
    "A ficha (da pessoa) tem falta grave de 04/03/2022, de uma prisão anterior; esta execução começou em 01/06/2024.",
    "Auditoria: item 'info' 'Ficha: 1 falta grave anterior ao início desta execução (01/06/2024) - só informação'; nada a apurar.",
    "A falta é anterior ao fato (10/05/2024) e à prisão desta execução: não interfere nos benefícios desta pena (LEP, art. 112, § 6º "
    "fala da falta no curso da execução) nem na janela do art. 6º do decreto.",
    r, [AUD(X, contem=["anterior", "04/03/2022"], nivel="info"), C("faltas_itens", "nao_contem", "04/03/2022")], f)

# =====================================================================================================================
# 2.16 Processos com dígitos trocados
# =====================================================================================================================
k = prox()
r = R_tr(k)
pc = proc_crim(k, 2024)  # 8802xxx-00.2024.8.12.0001
troc = pc[:5] + pc[6] + pc[5] + pc[7:]
f = FICHA(k, BASE_TR[:1] + [("11/02/2024", "Recolhido por prisão preventiva nos autos %s." % troc), BASE_TR[1],
                            ("15/06/2025", "Requisitado para audiência nos autos 0004321-77.2024.8.12.0002, comarca de Dourados."),
                            ("10/09/2026", cela("IPCG"))], **TR)
add(k, "Auditoria", "Processo da ficha com dois dígitos vizinhos trocados",
    "A ficha cita %s (o da ação penal %s com dois algarismos vizinhos invertidos) e também os autos 0004321-77.2024.8.12.0002, que o RSPE não lista." % (troc, pc),
    "Auditoria (info): 1 processo que o RSPE não lista (0004321-77.2024.8.12.0002) e %s tratado como provável erro de digitação de %s." % (troc, pc),
    "Mesma origem (8.12.0001), mesmo ano e dígito, e os 7 primeiros algarismos diferem só pela inversão de dois vizinhos: erro de "
    "digitação do mesmo processo (Resolução CNJ 65/2008, numeração única). O outro número é de outra comarca e não consta do RSPE: "
    "pode ser outro processo (LEP, art. 111) - informação.",
    r, [AUD(X, contem=["0004321-77.2024.8.12.0002"]), AUD(X, contem=[troc, "digitação"])], f)

# ---- notas das verificações em que o programa diverge do gabarito (achados da rodada de 12/10/2026) ----
NOTAS = {
    ("S2003", 0): ("O programa mostra 'verificar', não 'alerta'. O relatório (2.2) promete alerta quando a diferença muda marco de "
                   "idade; aqui muda o do art. 115 do CP (menor de 21 no fato). Como não se sabe qual data é a certa, 'verificar' é "
                   "defensável: escolha de política.", True),
    ("S2007", 0): ("O programa lança o reinício em 18/11/2024, mas rebaixa o item para 'verificar'. A ficha prova a custódia desde a "
                   "recaptura e o SEEU não a conta (LEP, art. 111; CP, art. 42): prejuízo certo, deveria ser alerta.", False),
    ("S2016", 1): ("O programa diz 292 dias; de 03/04/2024 a 20/01/2025, contando os dois extremos (como o próprio programa conta a "
                   "detração no caso S2013), são 293. Diferença de 1 dia na convenção da contagem.", False),
    ("S2019", 0): ("O programa lança o início pela ficha em 14/08/2025, mas como 'verificar', não 'alerta'. Sem evento de prisão o SEEU "
                   "não conta nenhum dia de pena (LEP, arts. 105 e 106; CP, art. 42): prejuízo certo.", False),
    ("S2032", 0): ("Erro interno (OverflowError na releitura): com o trabalho sem baixa, a correção do ano do trecho soma 3 dias à "
                   "data máxima do calendário e a análise inteira cai; a ficha fica sem atestados, faltas e estudo (relatório 2.20).", False),
    ("S2038", 0): ("'CICLO Nº 03/2020' não é reconhecido como ciclo (o 'º' atrapalha): a leitura fica 'obras não informadas' e "
                   "fora da comparação; com 'CICLO 03/2020' seria 1 obra = 4 dias (relatório 2.20).", False),
    ("S2038", 1): ("Mesmo achado: o documento aparece como 'relatório de leitura sem o número de obras'.", False),
    ("S2038", 2): ("Mesmo achado: a comparação fica 0 / 0 em vez de 4 / 0.", False),
    ("S2049", 2): ("O programa dá alerta de regime mais gravoso (falta de vaga), mas a própria ficha registra a regressão judicial ao "
                   "fechado (LEP, art. 118, I): a pessoa está no regime que o juiz fixou; o RSPE é que está desatualizado.", False),
    ("S2050", 0): ("A regressão judicial pela evasão, sem a palavra 'falta' no lançamento, não chega à leitura das faltas: nenhuma "
                   "falta homologada é criada (relatório 2.20). A evasão entra só como fuga a apurar.", False),
    ("S2050", 2): ("Mesmo achado do S2049: alerta de regime mais gravoso apesar da regressão judicial registrada na ficha.", False),
    ("S2051", 0): ("'Tentativa de fuga frustrada' vira incidente pendente 'FALTA GRAVE - FUGA/EVASÃO NA FICHA' (relatório 2.20: a "
                   "leitura das fugas para as contas não aplica o filtro das falsas fugas).", False),
    ("S2052", 0): ("'Sob pena de evasão' (advertência na concessão da saída, com saída e retorno confirmados) vira incidente pendente "
                   "de fuga em 19/12/2025, dentro dos 12 meses do art. 6º do Decreto 12.790/2025.", False),
}
for c in CASOS:
    for i, ch in enumerate(c["checks"]):
        if (c["id"], i) in NOTAS:
            ch["nota"], dec = NOTAS[(c["id"], i)]
            if dec:
                ch["decisao"] = True

out = os.path.join(AQUI, "ficha.json")
json.dump(CASOS, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("%d casos gravados em %s (S%d a S%d)" % (len(CASOS), out, 2001, _k[0]))
