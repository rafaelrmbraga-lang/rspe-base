"""Correção 7.15.2, frente ficha e remição (revisões jurídicas dos caps. 2 e 5): falsa fuga ("sob pena de evasão") não explica o
indício do RSPE; matrícula sem o prefixo "EDUCAÇÃO:"; conduta readquirida pelo requisito temporal (LEP, art. 112, § 7º); nome do setor
sem o começo do lançamento; documento posterior à última remição e perda acima de 1/3 não viram cinza com o RSPE maior; carga horária
da certidão lida; prioridade da progressão pela fração (trabalho anterior à data-base); fim da emergência sanitária em 22/05/2022;
matrícula sem registro há mais de 1 ano fora do pedido da fundamentação; estimativa do estudo no início desta execução; vínculo a
confirmar na situação; "Trabalho a atestar" só com atestado a pedir; motivos do mesmo documento numa linha; citações do art. 127.
Casos hipotéticos, sem nomes. Rodar: python teste_rev_ficha_remicao.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_auditoria as ra
import rspe_ficha as rf
import rspe_remicao as rrm
import rspe_scraper as rs
import rspe_view as rv

falhas = []
HOJE = date(2026, 10, 20)
PROC = "0000001-11.2018.8.12.0001"


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def rem(n, dec, ref=None):
    return {"tipo": "REMIÇÃO", "complemento": "%s Dia(s) Remido(s)" % n, "data_decisao": dec, "data_referencia": ref or dec, "situacao": "CONCEDIDO"}


def fgr(d, dec=None):
    return {"tipo": "HOMOLOGAÇÃO DE FALTA GRAVE", "situacao": "CONCEDIDO", "complemento": d, "data_referencia": d, "data_decisao": dec or d}


def perda(n, d, dec=None):
    return {"tipo": "DIAS PERDIDOS NA REMIÇÃO", "situacao": "CONCEDIDO", "complemento": "%d" % n, "data_referencia": d, "data_decisao": dec or d}


def R(*incs, ini="01/07/2018", **kw):
    r = {"processo_execucao": PROC, "_crimes": [], "_eventos": [{"data": ini, "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}],
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


def doc(N, num=None, tipo=None):
    return next((d for d in N["docs"] if (num is None or d["num"] == num) and (tipo is None or d["tipo"] == tipo)), None)


ENT = "Entrada na Unidade Penal: %s, Procedente: %s, Conforme OF/CI 1."
INI = "TRABALHO: Iniciou atividade laboral, no setor de trabalho %s, conforme documento CI 1."
FIM = "TRABALHO: Deixa de trabalhar, no setor de trabalho %s, conforme documento , motivo: %s."

try:
    # ---- cap. 2, nº 2: "sob pena de evasão" não explica a regressão sem falta; a evasão de fato explica ----
    def reg_(texto):
        r = {"_incidentes": [{"tipo": "FIXAÇÃO/ALTERAÇÃO DE REGIME", "complemento": "Fechado - Regressão", "data_decisao": "10/09/2026",
                              "data_referencia": "10/09/2026", "situacao": "CONCEDIDO"}], "_eventos": []}
        rs.explicar_indicios_ficha(r, {"eventos": [{"data": "01.08.2026", "texto": texto}]}, HOJE)
        return r["_incidentes"][0]
    i1 = reg_("O interno foi advertido de que deve retornar ao pernoite, sob pena de evasão imediata.")
    ok(not i1.get("_ficha_falta"), "2.2: 'sob pena de evasão' virou falta: %s" % i1.get("_ficha_falta"))
    i1b = reg_("Saída da Unidade Penal: ESTABELECIMENTO PENAL SEMIABERTO, Motivo: Evasão")
    ok(i1b.get("_ficha_falta") and i1b["_ficha_falta"]["data"] == "01/08/2026", "2.2b: evasão de fato não explicou: %s" % i1b)
    i1c = reg_("Tentativa de fuga frustrada pelo agente de plantão, conforme CI 12.")
    ok(i1c.get("_ficha_falta"), "2.2c: tentativa de fuga (falta, LEP, art. 49, p. ú.) deixou de explicar: %s" % i1c)

    # ---- cap. 2, nº 4: matrícula transcrita sem o prefixo "EDUCAÇÃO:" abre o estudo ----
    evs = [{"data": "03.02.2025", "texto": "Matriculou-se na Série: 1º ANO ENSINO MÉDIO Turma: A Período: MATUTINO"}]
    E = rf._estudos([dict(e, d=rf._dp(e["data"])) for e in evs])
    ok(len(E) == 1 and E[0]["inicio"] == "03.02.2025" and "ENSINO" in E[0]["curso"], "2.4: matrícula sem prefixo: %s" % E)

    # ---- cap. 2, nº 6: falta grave há menos de 1 ano, sem regressão, requisito temporal já cumprido: conduta readquirida ----
    f6 = {"conduta": "MÁ", "faltas": [{"data_fato": "10.03.2026", "grave": True, "situacao": "homologada"}], "eventos": []}
    r6 = {"_incidentes": [], "_eventos": [], "progressao_previsao_seeu": "01/09/2026"}
    it6 = rf._conduta_x_ficha(r6, f6, HOJE)
    ok(it6 and "requisito temporal cumprido em 01/09/2026" in it6[0]["titulo"] and "112, § 7º" in it6[0]["detalhe"], "2.6: %s" % it6)
    ok(not rf._conduta_x_ficha(dict(r6, progressao_previsao_seeu="01/12/2026"), f6, HOJE), "2.6b: requisito futuro gerou alerta")
    ok(not rf._conduta_x_ficha(dict(r6, progressao_previsao_seeu="01/02/2026"), f6, HOJE), "2.6c: data anterior à falta gerou alerta")
    it6d = rf._conduta_x_ficha(r6, dict(f6, faltas=[]), HOJE)
    ok(it6d and "pela data do fato" in it6d[0]["detalhe"] and "112, § 7º" in it6d[0]["detalhe"], "2.6d: texto da conta: %s" % it6d)

    # ---- cap. 2, nº 14: o nome do setor começa depois do número do atestado ----
    for t in ("Atestado de Trabalho Prisional nº 010/2023 Faxina (01/01/2023 a 30/03/2023) e Cozinha (01/04/2023 a 30/06/2023) "
              "totalizando 150 dias trabalhados e 50 dias remidos",
              "Atestado de Trabalho Prisional nº 010/2023 Faxina (01/01/2023 a 30/03/2023) totalizando 80 dias trabalhados e 26 dias remidos"):
        a = rrm.atestados([{"data": "05.07.2023", "texto": t}])[0]
        ok(a["segs"][0]["setor_txt"] == "FAXINA", "2.14: setor: %s" % a["segs"][0]["setor_txt"])

    # ---- cap. 5, nº 1: RSPE maior que a ficha; atestado de 2026 peticionado, posterior à última remição: amarelo, não cinza ----
    ev1 = [("02.07.2018", ENT % ("PENITENCIÁRIA DE DOIS IRMÃOS DO BURITI", "DP")), ("01.02.2026", INI % "PRENDEBEM"),
           ("10.06.2026", "Peticionado o Atestado de trabalho n 090/2026, no Sistema SEEU, Autos %s, função Prendebem (01/02/2026 a 31/05/2026) "
                          "totalizando 156 dias trabalhados e 52 remidos." % PROC),
           ("31.05.2026", FIM % ("PRENDEBEM", "N/C"))]
    o, N = N_(R(rem(100, "10/03/2020"), rem(20, "10/03/2025")), F(ev1))
    d1 = doc(N, "090/2026")
    p1 = [p for p in N["pontos"] if p["tipo"] == "posterior"]
    ok(N["rspe_maior"] and d1 and d1["cor"] == "amarelo", "5.1: documento posterior: %s %s" % (N["rspe_maior"], d1 and (d1["cor"], d1["sit"])))
    ok(p1 and p1[0]["cor"] == "amarelo", "5.1: ponto posterior: %s" % [(p["tipo"], p["cor"]) for p in N["pontos"]])
    ok(o["fd_cor"] == "amarelo" and "informativo" not in o["fd_sit"], "5.1: situação: %s %s" % (o["fd_cor"], o["fd_sit"]))
    ok(any("090/2026" in x["t"] and x["c"] == "amarelo" for x in N["onde"]), "5.1: onde: %s" % N["onde"])

    # ---- cap. 5, nº 2: perda acima de 1/3 com o RSPE maior que a ficha: continua amarela ----
    o, N = N_(R(rem(90, "10/03/2023"), fgr("01/06/2024", "01/08/2024"), perda(40, "01/06/2024", "01/08/2024")), F(ev1[:1]))
    pp = [p for p in N["pontos"] if p["tipo"] == "perda"]
    ok(N["rspe_maior"] and pp and all(p["cor"] == "amarelo" for p in pp), "5.2: perda: %s %s" % (N["rspe_maior"], [(p["cor"], p["texto"][:80]) for p in pp]))
    ok(o["fd_cor"] == "amarelo", "5.2: situação: %s %s" % (o["fd_cor"], o["fd_sit"]))

    # ---- cap. 5, nºs 7 e 13: carga horária no texto da certidão ----
    ok(rrm.horas_texto("PETICIONADO CERTIDÃO DE FREQUÊNCIA ESCOLAR 1º SEMESTRE DE 2026, CARGA HORÁRIA DE 412 HORAS") == 412, "5.7: 412 horas")
    ok(rrm.horas_texto("certidão de frequência escolar com 396 h/a") == 396, "5.7: h/a")
    ok(rrm.horas_texto("às 08:00 horas foi peticionada a certidão") is None, "5.7: hora do relógio")
    ev7 = [("02.07.2018", ENT % ("PENITENCIÁRIA DE DOIS IRMÃOS DO BURITI", "DP")),
           ("05.08.2026", "PETICIONADO CERTIDÃO DE FREQUÊNCIA ESCOLAR 1º SEMESTRE DE 2026, CARGA HORÁRIA DE 412 HORAS, no Sistema SEEU")]
    o, N = N_(R(), F(ev7))
    d7 = doc(N, tipo="Certidão de frequência escolar")
    ok(d7 and abs((d7["dias"] or 0) - 412 / 12.0) < 0.01 and not d7["sem_valor"], "5.7: certidão: %s" % ((d7["dias"], d7["sem_valor"]) if d7 else [d["tipo"] for d in N["docs"]],))

    # ---- cap. 5, nº 4: remição ficta da pandemia até 22/05/2022 (Portaria GM/MS 913/2022, em vigor 30 dias após 22/04/2022) ----
    ev4 = [("02.07.2018", ENT % ("PENITENCIÁRIA DE DOIS IRMÃOS DO BURITI", "DP")), ("01.08.2019", INI % "COZINHA"),
           ("20.03.2020", FIM % ("COZINHA", "suspensão das atividades - pandemia COVID-19"))]
    o, N = N_(R(), F(ev4))
    pf = [p for p in N["pontos"] if p["tipo"] == "ficta"]
    ok(pf and "a 22/05/2022" in pf[0]["texto"] and "Portaria GM/MS 913/2022" in pf[0]["texto"], "5.4: ficta: %s" % [p["texto"] for p in pf])

    # ---- cap. 5, nº 6: prioridade da progressão - remição de trabalho anterior à data-base só reduz a fração ----
    r6 = {"_rem_pend": [["30/06/2024", "Atestado nº 1/2024", 60.0]], "data_base_seeu": "01/01/2025", "fracao_progressao_aplicada": "1/6"}
    m6 = {"prog": "10/11/2026", "liv": "10/11/2026"}
    pr = rv.prioridade_remicao(m6, r6, HOJE)
    ok(not any(x.startswith("Progressão") for x in pr) and any(x.startswith("Livramento") for x in pr),
       "5.6: progressão com a remição anterior à data-base (≈ 10 dias) deu prioridade: %s" % pr)
    r6b = dict(r6, _rem_pend=[["30/06/2025", "Atestado nº 2/2025", 60.0]])
    ok(any(x.startswith("Progressão") for x in rv.prioridade_remicao(m6, r6b, HOJE)), "5.6b: trabalho posterior à data-base conta inteiro")

    # ---- cap. 5, nº 5 e nº 10: fundamentação sem a matrícula parada há mais de 1 ano; estimativa no início desta execução ----
    ev5 = [("02.07.2018", ENT % ("PENITENCIÁRIA DE DOIS IRMÃOS DO BURITI", "DP")),
           ("03.02.2024", "EDUCAÇÃO: Matriculou-se na Série: EJA ENSINO FUNDAMENTAL Turma: B Período: NOTURNO"),
           ("01.02.2026", INI % "PRENDEBEM"),
           ("10.06.2026", "Peticionado o Atestado de trabalho n 091/2026, no Sistema SEEU, Autos %s, função Prendebem (01/02/2026 a 31/05/2026) "
                          "totalizando 104 dias trabalhados e 34,66 remidos." % PROC),
           ("31.05.2026", FIM % ("PRENDEBEM", "N/C"))]
    o, N = N_(R(), F(ev5))
    fund = o["fd_fund"]
    ok("matrícula em estudo sem remição" not in fund and "não se afirma a frequência" in fund and "03/02/2024" in fund,
       "5.5: fundamentação: %s" % fund[:1500])
    ev10 = [("02.07.2018", ENT % ("PENITENCIÁRIA DE DOIS IRMÃOS DO BURITI", "DP")),
            ("03.02.2026", "EDUCAÇÃO: Matriculou-se na Série: EJA ENSINO FUNDAMENTAL Turma: B Período: NOTURNO"),
            ("20.08.2026", "EDUCAÇÃO: Matrícula Cancelada Série: EJA ENSINO FUNDAMENTAL")]
    o, N = N_(R(ini="01/06/2026"), F(ev10))
    ok(N["est_estim"] and all("01/06/2026 a" in x["txt"] for x in N["est_estim"]), "5.10: estimativa antes do início: %s" % [x["txt"] for x in N["est_estim"]])

    # ---- cap. 5, nº 8: vínculo sugerido nunca fica "Em ordem"; nº 11: "Trabalho a atestar" só com "Pedir atestado" ----
    ev8 = [("02.07.2018", ENT % ("PENITENCIÁRIA DE DOIS IRMÃOS DO BURITI", "DP")), ("21.11.2016", INI % "BIBLIOTECA"),
           ("23.02.2021", "EMITIDO ATESTADO DE TRABALHO PRISIONAL Nº 024/2021, TOTALIZANDO 1554 DIAS TRABALHADOS E 518 DIAS REMIDOS."),
           ("01.04.2021", FIM % ("BIBLIOTECA", "N/C"))]
    o, N = N_(R(rem(518, "10/04/2021"), ini="01/07/2016"), F(ev8))
    vinc = [L for L in N["trab"]["linhas"] if L["st"] in ("possivel", "provavel")]
    if vinc:
        ok(o["fd_sit"] != "Em ordem" and "Confirmar vínculo" in o["fd_sit"] and o["fd_cor"] == "amarelo", "5.8: %s %s" % (o["fd_cor"], o["fd_sit"]))
    else:
        falhas.append("5.8: caso sem vínculo sugerido: %s" % [(L["periodo"], L["st"]) for L in N["trab"]["linhas"]])
    ev11 = [("02.07.2018", ENT % ("PENITENCIÁRIA DE DOIS IRMÃOS DO BURITI", "DP")), ("01.09.2026", INI % "PRENDEBEM")]
    o, N = N_(R(), F(ev11))
    ok(N.get("acomp") and o["fd_atestar"] == "Não", "5.11: trabalho em curso a acompanhar marcado a atestar: %s %s" % (N.get("acomp"), o["fd_atestar"]))

    # ---- cap. 2, nº 11; cap. 5, nº 16: cada precedente na sua tese ----
    ok("até 1/3 no total - STJ, HC 293.475/SP e HC 377.088/SP" in ra.FUND_127 and "infração anterior - STJ, HC 398.850/SP" in ra.FUND_127,
       "2.11: FUND_127: %s" % ra.FUND_127)
    it16 = ra._perda_remidos([perda(10, "01/06/2024")], 10, [])
    ok(it16 and "mitigada pelo STF, Tema 941" in it16[0]["fundamento"], "5.16: %s" % [i.get("fundamento") for i in it16])
except Exception:
    import traceback
    traceback.print_exc()
    falhas.append("exceção")

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for x in falhas:
        print(" -", x)
    sys.exit(1)
print("ok: revisão 7.15.2, ficha e remição (falsa fuga no indício, matrícula sem prefixo, conduta pelo requisito temporal, setor, posterior "
      "e perda sem cinza, carga horária, pandemia até 22/05/2022, prioridade pela fração, matrícula parada fora do pedido, início da "
      "execução, vínculo a confirmar, trabalho a atestar, citações do art. 127)")
