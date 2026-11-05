"""Decisões dos pareceres P08-P21, P55 e P56 (APTO 7.15.3), frente ficha e remição: certificado de conclusão do ENEM (fora das
edições de 2017 a 2024) atende o inciso XIII e eleva o teto do exame; monitoramento cautelar separado em três casos (cumprimento,
recolhimento noturno - Tema 1155 - e só monitoramento, tese defensiva); isolamento preventivo sem a natureza da falta fora das
janelas de 12 meses; perda de 1/3 com aviso de fundamentação; regime domiciliar (§ 9º do art. 126); ficta até o retorno efetivo
(tese, só texto); 12x36 (ressalva); "à parte" com ressalva (trabalho posterior ao fato; outros autos); vínculo sem baixa depois do
último atestado = confirmar com a unidade; baixa tardia com o resto a conferir; matrícula sem fim com pedido de certidão;
ENCCEJA só peticionado = a verificar, requisitar o certificado; tentativa de fuga continua explicando a falta.
Casos hipotéticos, sem nomes. Rodar: python teste_dec_ficha_remicao.py"""
import copy
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_auditoria as ra
import rspe_ficha as rf
import rspe_remicao as rrm
import rspe_scraper as rs

falhas = []
HOJE = date(2026, 10, 20)
PROC = "0000001-11.2018.8.12.0001"
P1 = "0000001-11.2020.8.12.0001"
PEXEC = "6000009-99.2023.8.12.0001"


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def rem(n, dec, ref=None):
    return {"tipo": "REMIÇÃO", "complemento": "%s Dia(s) Remido(s)" % n, "data_decisao": dec, "data_referencia": ref or dec, "situacao": "CONCEDIDO"}


def fgr(d, dec=None):
    return {"tipo": "HOMOLOGAÇÃO DE FALTA GRAVE", "situacao": "CONCEDIDO", "complemento": d, "data_referencia": d, "data_decisao": dec or d}


def perda(n, d, dec=None):
    return {"tipo": "DIAS PERDIDOS NA REMIÇÃO", "situacao": "CONCEDIDO", "complemento": "%d" % n, "data_referencia": d, "data_decisao": dec or d}


def R(*incs, ini="01/07/2018", crimes=None, eventos=None, **kw):
    r = {"processo_execucao": PROC, "_crimes": crimes or [], "_eventos": eventos or [{"data": ini, "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}],
         "_incidentes": list(incs)}
    rr = sum(float(i["complemento"].split()[0]) for i in incs if i["tipo"] == "REMIÇÃO")
    pp = sum(float(i["complemento"]) for i in incs if i["tipo"].startswith("DIAS PERDIDOS"))
    r["saldo_remidos"] = "%g dias (%g dias remidos - %g dias perdidos)" % (rr - pp, rr, pp)
    r.update(kw)
    return r


def F(eventos, impressao="06/10/2026"):
    f = rf.atualizar({"data_impressao": impressao, "eventos": [{"data": d, "texto": t} for d, t in eventos]})
    for k in ("leituras", "exames", "cursos_peticionados", "certidoes_estudo"):
        f.setdefault(k, [])
    return f


def N_(r, f):
    o = rf.comparativo(r, f, HOJE)
    return o, o["fd_novo"]


def tipos(N):
    return {p["tipo"]: p for p in N["pontos"]}


def crime(**kw):
    c = {"processo_criminal": P1, "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto", "tipo_penal": "CAPUT: Subtrair",
         "pena_imposta": "5 ano(s), 0 mês(es) e 0 dia(s)", "data_infracao": "01/07/2019", "data_denuncia": "10/08/2019",
         "data_sentenca": "10/06/2021", "transito_mp": "10/07/2021", "transito_processo": "10/07/2021", "extinto": "Não", "suspenso": "Não",
         "vga": "N", "resultado_morte": "N", "reincidente_comum": "N", "reincidente_especifico": "N", "comando_orcrim": "N",
         "fracao_progressao": "40% - Art.112, V, da LEP", "fracao_livramento": "1/3 - Comum", "regime_sentenca": "Fechado", "hediondo_ou_equiparado": "N"}
    c.update(kw)
    return c


ENT = "Entrada na Unidade Penal: %s, Procedente: %s, Conforme OF/CI 1."
INI = "TRABALHO: Iniciou atividade laboral, no setor de trabalho %s, conforme documento CI 1."
FIM = "TRABALHO: Deixa de trabalhar, no setor de trabalho %s, conforme documento , motivo: %s."
PEN = "PENITENCIÁRIA DE DOIS IRMÃOS DO BURITI"
AT = ("Peticionado o Atestado de trabalho n %s, no Sistema SEEU, Autos %s, função %s (%s a %s) totalizando %d dias trabalhados e %s remidos.")

try:
    # ---- P08: certificado de conclusão do ENEM conta (fora de 2017-2024); P56: ENCCEJA só peticionado - a verificar, requisitar ----
    ok(rf.exame_conclui("ENEM", 2025, "CERTIFICADO DE CONCLUSÃO DO ENSINO MÉDIO PELO ENEM 2025"), "P08: ENEM 2025 com certificado")
    ok(not rf.exame_conclui("ENEM", 2022, "CERTIFICADO DE CONCLUSÃO DO ENSINO MÉDIO PELO ENEM 2022"), "P08: ENEM 2022 (sem certificação)")
    ok(rf.exame_conclui("ENEM 2016", None, "CERTIFICADO DE CONCLUSÃO DO ENSINO MÉDIO - ENEM 2016"), "P08: ENEM 2016 pelo nome")
    ok(not rf.exame_conclui("ENEM", 2025, "PETICIONADO CERTIFICADO DE CONCLUSÃO DO ENEM 2025"), "P08: petição não é certificado")

    def _r13():
        return {"_eventos": [{"data": "01/01/2020", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}],
                "indulto_2025": "A VERIFICAR: art. 9º, XIII", "indulto_2025_status": "verificar",
                "indulto_2025_detalhe": "Situação em 25/12/2025: regime Fechado · primário\n? XIII: pena ≤ 12 anos, 1/5 cumprido - verificar "
                                        "conclusão de curso certificado nos 3 anos anteriores"}

    def xiii(txt, exame):
        r = _r13()
        f = {"eventos": [{"data": "11.04.2025", "texto": txt.upper()}], "exames": [{"exame": exame, "data": "11.04.2025"}], "trabalho": [], "estudos": []}
        rf.complementar_decretos(r, f, HOJE)
        return next((l for l in r["indulto_2025_detalhe"].split("\n") if " XIII:" in l), "")
    l1 = xiii("Certificado de conclusão do ensino médio - ENEM 2025", "ENEM 2025")
    ok(l1.startswith("✔"), "P08: XIII com o certificado do ENEM 2025: %s" % l1)
    l2 = xiii("Certificado de conclusão do ensino médio - ENEM 2023", "ENEM 2023")
    ok(l2.startswith("?") and "2017 a 2024" in l2, "P08: ENEM 2023 a verificar: %s" % l2)
    l3 = xiii("Peticionado Certificado do ENCCEJA 2024 no Sistema SEEU nos autos nº 1", "ENCCEJA 2024")
    ok(l3.startswith("?") and "requisitar o certificado de conclusão" in l3, "P56: ENCCEJA peticionado: %s" % l3)

    # ---- P09: monitoramento cautelar - só monitoramento = verificar (tese); com recolhimento noturno = alerta (Tema 1155) ----
    r9 = {"nome": "T", "regime_atual": "Fechado - ATIVO", "pena_total": "5a0m0d", "data_geracao_rspe": "01/10/2026", "data_base_seeu": "30/01/2026",
          "progressao_previsao_seeu": "22/07/2027", "_crimes": [crime()], "_incidentes": [], "status_execucao": "ATIVO", "processo_execucao": PEXEC,
          "_eventos": [{"tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO EM FLAGRANTE", "data": "30/07/2019", "processos": P1},
                       {"tipo": "INTERRUPÇÃO", "motivo": "LIBERDADE PROVISÓRIA", "data": "20/12/2020", "processos": P1},
                       {"tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "INÍCIO DO CUMPRIMENTO REGIME FECHADO", "data": "30/01/2026", "processos": P1}]}
    f9 = {"data_impressao": "02/10/2026", "eventos": [
        {"data": "15.02.2024", "texto": "Entrada na Unidade Penal: UNIDADE MISTA DE MONITORAMENTO VIRTUAL ESTADUAL, Procedente: DECISÃO JUDICIAL, Conforme OF/CI %s." % P1},
        {"data": "04.02.2026", "texto": "Saída da Unidade Penal: UNIDADE MISTA DE MONITORAMENTO VIRTUAL ESTADUAL, Destino: PENITENCIÁRIA X, Conforme: %s." % P1}]}
    i9 = rf._monitoramento_x_ficha(r9, f9)
    ok(i9 and i9[0]["nivel"] == "verificar" and "tese defensiva" in i9[0]["detalhe"] and "1.078.634" in i9[0]["detalhe"]
       and i9[0].get("prog_rotulo", "").startswith("se acolhida"), "P09: só monitoramento: %s" % i9)
    f9b = copy.deepcopy(f9)
    f9b["eventos"].insert(1, {"data": "15.02.2024", "texto": "Medida cautelar com recolhimento domiciliar noturno e nos dias de folga, autos %s." % P1})
    i9b = rf._monitoramento_x_ficha(r9, f9b)
    ok(i9b and i9b[0]["nivel"] == "alerta" and "recolhimento noturno" in i9b[0]["titulo"] and "teto" in i9b[0]["detalhe"], "P09: recolhimento: %s" % i9b)
    f9c = copy.deepcopy(f9)
    for e in f9c["eventos"]:
        e["texto"] = e["texto"].replace(P1, PEXEC)
    i9c = rf._monitoramento_x_ficha(r9, f9c)
    ok(i9c and i9c[0]["nivel"] == "alerta" and "pena cumprida" in i9c[0]["detalhe"], "P09: monitoramento da execução: %s" % i9c)

    # ---- P10: isolamento preventivo com PADIC, sem a natureza: incidente "a confirmar", fora das janelas de 12 meses ----
    fic = {"faltas": [{"data_registro": "24.08.2026", "data_fato": "24.08.2026", "artigo": "", "grave": False, "grave_indicio": True,
                       "texto": "CONSELHO DISCIPLINAR: ISOLADO PREVENTIVAMENTE EM CELA DISCIPLINAR - RESPONDE PADIC/XX.", "padic": "",
                       "resultado": "", "situacao": "PADIC instaurado"}], "eventos": []}
    r10 = {"_crimes": [crime()], "_incidentes": [], "_eventos": [{"tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO", "data": "01/02/2021"}]}
    rs.faltas_da_ficha(r10, fic, HOJE)
    i10 = [i for i in r10["_incidentes"] if i.get("_ficha")]
    ok(i10 and i10[0].get("_natureza_a_confirmar") and "natureza a confirmar" in i10[0]["complemento"], "P10: incidente: %s" % i10)
    ok(not rs.indicios_falta(r10["_incidentes"], HOJE, eventos=r10["_eventos"]), "P10: isolamento sozinho entrou na janela")
    i10[0]["_falta"] = "sim"
    ok(rs.indicios_falta(r10["_incidentes"], HOJE, eventos=r10["_eventos"]), "P10: com a decisão do operador (falta), entra na janela")

    # ---- P11: TJDFT citado com os dois números ----
    ok("1230029" in ra.FUND_127 and "0716724-08.2019.8.07.0000" in ra.FUND_127, "P11: %s" % ra.FUND_127)

    # ---- P15: perda de 1/3 - aviso cinza para conferir a fundamentação ----
    o, N = N_(R(rem(90, "10/03/2023"), fgr("01/06/2024", "01/08/2024"), perda(30, "01/06/2024", "01/08/2024")),
              F([("02.07.2018", ENT % (PEN, "DP"))]))
    pm = tipos(N).get("perda_maxima")
    ok(pm and pm["cor"] == "cinza" and "HC 692.749" in pm["texto"], "P15: perda máxima: %s" % [(p["tipo"], p["cor"]) for p in N["pontos"]])
    o, N = N_(R(rem(90, "10/03/2023"), fgr("01/06/2024", "01/08/2024"), perda(10, "01/06/2024", "01/08/2024")),
              F([("02.07.2018", ENT % (PEN, "DP"))]))
    ok("perda_maxima" not in tipos(N), "P15: perda menor que 1/3 gerou aviso")

    # ---- P13: regime domiciliar no RSPE - § 9º do art. 126, a conferir ----
    o, N = N_(R(rem(20, "10/03/2023"), {"tipo": "FIXAÇÃO/ALTERAÇÃO DE REGIME", "complemento": "Semiaberto - Prisão domiciliar (harmonizado)",
                                        "data_decisao": "10/05/2025", "data_referencia": "10/05/2025", "situacao": "CONCEDIDO"}),
              F([("02.07.2018", ENT % (PEN, "DP"))]))
    p13 = tipos(N).get("domiciliar_9")
    ok(p13 and p13["cor"] == "amarelo" and "§ 9º" in p13["texto"] and "10/05/2025" in p13["texto"], "P13: %s" % [(p["tipo"], p["cor"], p["texto"][:120]) for p in N["pontos"]])
    o, N = N_(R(rem(20, "10/03/2023")), F([("02.07.2018", ENT % (PEN, "DP"))]))
    ok("domiciliar_9" not in tipos(N), "P13: sem domiciliar, sem ponto")

    # ---- P14: ficta até 22/05/2022, com a tese do retorno efetivo (só texto) ----
    ev14 = [("02.07.2018", ENT % (PEN, "DP")), ("01.08.2019", INI % "COZINHA"),
            ("20.03.2020", FIM % ("COZINHA", "suspensão das atividades - pandemia COVID-19"))]
    o, N = N_(R(), F(ev14))
    pf = tipos(N).get("ficta")
    ok(pf and "a 22/05/2022" in pf["texto"] and "retorno efetivo" in pf["texto"], "P14: %s" % (pf and pf["texto"]))

    # ---- P16: 12x36 no pedido de atestado: ressalva das horas além da 8ª ----
    ev16 = [("02.07.2018", ENT % (PEN, "DP")),
            ("01.02.2026", "TRABALHO: Iniciou atividade laboral, no setor de trabalho PORTARIA, em escala 12x36, conforme documento CI 1.")]
    o, N = N_(R(), F(ev16))
    p16 = tipos(N).get("pedir_atestado")
    ok(p16 and "12x36" in p16["texto"] and "REsp 1.483.755" in p16["texto"], "P16: %s %s" % (p16 and p16["texto"][-300:], [p["tipo"] for p in N["pontos"]]))

    # ---- P17/P18: "à parte" com ressalva visível ----
    d_ = {"fora": "anterior ao início desta execução (01/07/2018)", "periodo": "01/03/2018 a 30/06/2018", "emissao": date(2018, 7, 5)}
    ok("conferir o aproveitamento" in rrm._ressalva_aparte(d_, date(2017, 12, 1)), "P17: posterior ao fato")
    ok(rrm._ressalva_aparte(d_, date(2018, 5, 1)) == "", "P17: trabalho anterior ao fato não se aproveita")
    ok("em qual execução" in rrm._ressalva_aparte({"fora": "dirigido a outros autos (1)"}, None), "P18: outros autos")
    ev17 = [("02.07.2018", ENT % (PEN, "DP")),
            ("05.07.2018", AT % ("010/2018", "0009999-11.2017.8.12.0001", "Faxina", "01/03/2018", "30/06/2018", 90, "30"))]
    o, N = N_(R(crimes=[crime(processo_criminal=PROC, data_infracao="01/12/2017")]), F(ev17))
    d17 = next((d for d in N["docs"] if d["num"] == "010/2018"), None)
    ok(d17 and d17["sit"].startswith("À parte: dirigido a outros autos") and "em qual execução" in d17["sit"], "P18: sit: %s" % (d17 and d17["sit"]))

    # ---- P19: vínculo sem baixa depois do último atestado do vínculo: confirmar com a unidade (sem pedido) ----
    ev19 = [("02.07.2018", ENT % (PEN, "DP")), ("01.02.2024", INI % "MARCENARIA"),
            ("05.07.2024", AT % ("060/2024", PROC, "Marcenaria", "01/02/2024", "30/06/2024", 150, "50"))]
    o, N = N_(R(rem(50, "01/08/2024", "30/06/2024")), F(ev19))
    tp = tipos(N)
    ok("sem_baixa_curso" in tp and "pedir_atestado" not in tp and o["fd_atestar"] != "Sim" and N["diag"]["t"].startswith("Confirmar com a unidade"),
       "P19: %s / %s" % (list(tp), N["diag"]))
    ok(any("confirmar com a unidade" in L["sit"] for L in o["fd_linhas"]), "P19: linha: %s" % [L["sit"] for L in o["fd_linhas"]])

    # ---- P20: baixa tardia - o resto do período, sem outro trabalho, fica a conferir (sem dias) ----
    ev20 = [("02.07.2018", ENT % (PEN, "DP")), ("10.01.2025", INI % "HORTA"), ("01.04.2025", INI % "COZINHA"),
            ("30.04.2025", FIM % ("COZINHA", "A PEDIDO")), ("20.06.2025", FIM % ("HORTA", "A PEDIDO"))]
    f20 = F(ev20)
    o, N = N_(R(), f20)
    # (o outro setor já tinha acabado antes da baixa: os dois correram juntos e a horta vai até a baixa - sem ponto)
    hor = [t for t in f20["trabalho"] if "HORTA" in t["setor"]]
    ok(hor and hor[0].get("fim") == "20.06.2025" and "baixa_tardia" not in tipos(N), "P20: simultâneo: %s" % hor)
    ev20b = [("02.07.2018", ENT % (PEN, "DP")), ("10.01.2025", INI % "HORTA"), ("01.04.2025", INI % "COZINHA"),
             ("20.06.2025", FIM % ("HORTA", "A PEDIDO"))]
    o, N = N_(R(), F(ev20b))
    ok("baixa_tardia" not in tipos(N), "P20: resto coberto pela cozinha em curso gerou ponto: %s" % tipos(N).get("baixa_tardia"))

    # ---- P21: matrícula sem fim - estimativa com o pedido de certidão ----
    ev21 = [("02.07.2018", ENT % (PEN, "DP")), ("03.08.2026", "EDUCAÇÃO: Matriculou-se na Série: EJA ENSINO MÉDIO Turma: B Período: NOTURNO")]
    o, N = N_(R(), F(ev21))
    p21 = tipos(N).get("estudo_estimado")
    ok(p21 and "matrícula sem registro de fim" in p21["texto"] and "certidão de frequência" in p21["texto"], "P21: %s" % (p21 and p21["texto"]))

    # ---- P55: a tentativa de fuga continua explicando a regressão (falta), sem virar fuga ----
    r55 = {"_incidentes": [{"tipo": "FIXAÇÃO/ALTERAÇÃO DE REGIME", "complemento": "Fechado - Regressão", "data_decisao": "10/09/2026",
                            "data_referencia": "10/09/2026", "situacao": "CONCEDIDO"}], "_eventos": []}
    rs.explicar_indicios_ficha(r55, {"eventos": [{"data": "01.08.2026", "texto": "Tentativa de fuga frustrada pelo agente de plantão, conforme CI 12."}]}, HOJE)
    ok(r55["_incidentes"][0].get("_ficha_falta"), "P55: tentativa de fuga deixou de explicar")
    ok(not rf._RE_FUGA_FICHA_RX.search(rf._sem_fuga_falsa("Tentativa de fuga frustrada pelo agente de plantão")), "P55: tentativa virou fuga")
except Exception:
    import traceback
    traceback.print_exc()
    falhas.append("exceção")

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for x in falhas:
        print(" -", x)
    sys.exit(1)
print("teste_dec_ficha_remicao: ok")
