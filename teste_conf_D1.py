"""Conferência manual 7.13.0, frente D1 - remição ligada à sua origem: certidão de frequência escolar e curso de qualificação
peticionados explicam a remição decidida logo depois (não é "sem origem" nem trabalho); a decisão que soma atestado e leitura;
a remição sem atestado que não cabe no trabalho registrado antes dela fica "sem origem" (o trabalho do período, a conferir);
atestado contido em outro atestado cumulativo não se soma; atestado de período em que a execução estava interrompida pela
liberdade é de outra custódia; remição posterior sem origem que não alcança o atestado não o tira do total; excedente de uma
remição a maior abate o outro atestado não lançado; leitura remida pouco antes da petição registrada; exame com a referência
anterior ao ano da prova; lacuna sem os períodos de liberdade; referência tardia só com os dias do atestado e sem a progressão
desfeita por nova fixação de regime; perdas de remidos sem falta datada; "último atestado há 6 meses" a partir do início do
trabalho atual; matrícula cancelada sem matrícula registrada. Dados fictícios. Rodar: python teste_conf_D1.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_auditoria as ra
import rspe_ficha as rf
import rspe_remicao as rrm

falhas = []
HOJE = date(2026, 10, 20)
PROC = "0009999-11.2020.8.12.0001"
INI = "TRABALHO: Iniciou atividade laboral, no setor de trabalho %s, conforme documento 1."
FIM = "TRABALHO: Deixa de trabalhar, no setor de trabalho %s, conforme documento 1, motivo: %s."


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def FD(eventos, impressao="05/10/2026"):
    """Ficha com os campos derivados do histórico (certidões, cursos, leituras, exames, estudo), como na importação."""
    f = {"data_impressao": impressao, "eventos": [{"data": d, "texto": t} for d, t in eventos]}
    return rf.derivar(f, [dict(e, d=rf._dp(e["data"])) for e in f["eventos"]])


def rem(dias, dec, ref=None):
    return {"tipo": "REMIÇÃO", "complemento": "%s Dia(s) Remido(s)" % dias, "data_decisao": dec, "data_referencia": ref or dec, "situacao": "CONCEDIDO"}


def R(*incs, eventos=(), prisao="01/01/2020"):
    return {"processo_execucao": PROC, "_eventos": [{"data": prisao, "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}] + list(eventos),
            "_incidentes": list(incs), "_crimes": []}


def blocos(res):
    return [i for b in res.get("blocos") or [] for i in b["itens"]]


def alertas(C):
    return " | ".join(a["texto"] for a in C["alertas"])


try:
    # ---- 1: certidões de frequência peticionadas explicam as remições (referência no fim do semestre) ----
    f = FD([("02.03.2025", "EDUCAÇÃO: Matrículou-se na Série: 1ª FASE B ENSINO FUNDAMENTAL Turma: Período: Matutino"),
            ("06.03.2026", "EDUCAÇÃO: Peticionado Certidão de Frequência Escolar referente ao 2º semestre de 2025, no Sistema SEEU nos Autos Nº 00099991120208120001."),
            ("20.08.2026", "EDUCAÇÃO: Peticionado Certidão de Frequência Escolar referente ao 1º semestre de 2026, no Sistema SEEU nos Autos Nº 0009999-11.2020.8.12.0001.")])
    ok([(c["semestre"], c["ano"]) for c in f["certidoes_estudo"]] == [(2, 2025), (1, 2026)], "1: certidões lidas %r" % f["certidoes_estudo"])
    r = R(rem(33, "13/03/2026", "22/12/2025"), rem(15, "01/09/2026", "30/07/2026"))
    _l, res = rf.quadro_trabalho(r, f, HOJE)
    C = res["conc"]
    ok("sem origem" not in alertas(C).lower() and "origem não identificada" not in alertas(C), "1: remição de estudo dada como sem origem: %s" % alertas(C))
    its = {i["emp"]: i for i in blocos(res)}
    c2 = its.get("Certidão de frequência escolar (2º semestre de 2025)") or {}
    ok(c2.get("cor") == "verde" and "33 dias em 13/03/2026" in c2.get("sit", ""), "1: certidão do 2º semestre %r" % c2)
    est = next((i for i in blocos(res) if "Fase" in i["emp"]), {})
    ok("Requerer remição após 30/07/2026" in est.get("sit", "") or "após 30/07/2026" in est.get("sit", ""), "1: corte do estudo na referência da última certidão %r" % est)

    # ---- 2: curso de qualificação (dois grupos de meses) explica a remição; o trabalho do período não é "remido" por ela ----
    f = FD([("21.02.2025", INI % "POLIGONAL"),
            ("14.05.2025", "Peticionados os Cursos de Qualificação - Instituto Avelar, referentes aos meses 10 de 2024 e mês 04 de 2025, no sistema SEEU nos Autos 0009999-11.2020.8.12.0001."),
            ("30.06.2025", FIM % ("POLIGONAL", "A PEDIDO"))])
    ok(f["cursos_peticionados"][0]["meses"] == ["10/2024", "04/2025"], "2: meses do curso %r" % f["cursos_peticionados"])
    _l, res = rf.quadro_trabalho(R(rem(20, "23/05/2025", "19/04/2025")), f, HOJE)
    C = res["conc"]
    ok(not [t for t in C["tabela"] if t["atestado"] == "Remição sem atestado na ficha"], "2: remição do curso atribuída ao trabalho")
    ok(any(p["status"] == "SEM_ATESTADO" and p["texto"].startswith("Poligonal") for p in C["pendencias"]), "2: trabalho sem atestado sumiu %r" % C["pendencias"])
    cur = next((i for i in blocos(res) if i["emp"].startswith("Curso de qualificação")), {})
    ok(cur.get("cor") == "verde" and "20 dias em 23/05/2025" in cur.get("sit", ""), "2: curso %r" % cur)

    # ---- 3: a decisão soma atestado e leitura (35 = 31,33 + 4) ----
    f = FD([("17.11.2020", INI % "OLARIA"),
            ("21.05.2021", "Emitido Atestado de Trabalho nº 066/2021, período de 17/11/2020 a 16/04/2021, 94 dias trabalhados e 31,33 dias remidos."),
            ("27.05.2021", "EDUCAÇÃO: Peticionados os relatórios de leitura, referentes aos meses 04 de 2021, no sistema SEEU, Autos Nº 0009999-11.2020.8.12.0001."),
            ("16.04.2021", FIM % ("OLARIA", "A PEDIDO"))])
    _l, res = rf.quadro_trabalho(R(rem(35, "20/07/2021")), f, HOJE)
    C = res["conc"]
    t = next(t for t in C["tabela"] if "066" in t["atestado"])
    ok(t["status"] == "CONCILIADO", "3: atestado + leitura %r" % t["status"])
    lt = next((i for i in blocos(res) if i["emp"].startswith("Leitura")), {})
    ok(lt.get("cor") == "verde" and "somada ao atestado" in lt.get("sit", ""), "3: leitura somada %r" % lt)
    ok(not res.get("leituras_f"), "3: leitura pedida de novo na fundamentação %r" % res.get("leituras_f"))

    # ---- 4: remição sem atestado que não cabe no trabalho curto antes dela: sem origem, trabalho a conferir ----
    f = FD([("11.03.2023", INI % "CONVENIO"), ("17.03.2023", FIM % ("CONVENIO", "A PEDIDO"))])
    C = rrm.conciliar(R(rem(129, "28/07/2023")), f, HOJE)
    ok(not [t for t in C["tabela"] if t["atestado"] == "Remição sem atestado na ficha"], "4: 129 dias dados como do trabalho de 6 dias")
    ok("maiores que o trabalho registrado antes delas" in alertas(C) and "129 dias em 28/07/2023" in alertas(C), "4: alerta %s" % alertas(C))
    ok(not any(p["status"] == "SEM_ATESTADO" for p in C["pendencias"]), "4: trabalho pedido apesar da remição maior")

    # ---- 5: atestado contido em atestado posterior (cumulativo) não entra na soma ----
    f = FD([("22.03.2022", INI % "PRENDEBEM"),
            ("09.09.2022", "Emitido Atestado de Trabalho nº 275/2022, período de 22/03/2022 a 05/07/2022, 91 dias trabalhados e 30 dias remidos."),
            ("01.02.2023", "Emitido Atestado de Trabalho nº 051/2023, período de 22/03/2022 a 05/07/2022 e 15/09/2022 a 01/02/2023, 211 dias trabalhados e 70 dias remidos."),
            ("06.07.2023", "Emitido Atestado de Trabalho nº 175/2023, período de 02/02/2023 a 06/07/2023, 133 dias trabalhados e 44 dias remidos.")])
    C = rrm.conciliar(R(rem(144, "18/09/2023")), f, HOJE)
    st = {a["numero"]: a["status"] for a in C["atestados"]}
    ok(st.get("051/2023") == "CONCILIADO" and st.get("175/2023") == "CONCILIADO", "5: 051 + 175 %r" % st)
    t275 = next(t for t in C["tabela"] if "275" in t["atestado"])
    ok(t275["status"] != "CONCILIADO" and t275["cor"] == "cinza", "5: atestado contido somado %r" % t275)
    ok("cumulativo e já inclui" in alertas(C), "5: aviso do atestado contido")

    # ---- 6: atestado de período em que a execução estava interrompida pela liberdade: outra custódia ----
    f = FD([("29.07.2016", "Emitido Atestado de Trabalho nº 499, período de 14/06/2016 a 28/07/2016, 39 dias trabalhados e 13 dias remidos.")])
    r = R(prisao="20/04/2015", eventos=[{"data": "27/05/2015", "tipo": "INTERRUPÇÃO", "motivo": "LIBERDADE PROVISÓRIA"},
                                         {"data": "17/05/2017", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}])
    C = rrm.conciliar(r, f, HOJE)
    t = C["tabela"][0]
    ok(t["rot"].startswith("Outra custódia") and t["cor"] == "cinza", "6: atestado da liberdade %r" % t["rot"])
    ok(any(p["status"] == "OUTROS_AUTOS" and "interrompida no RSPE" in p["texto"] for p in C["pendencias"]), "6: pendência %r" % C["pendencias"])

    # ---- 7: remição posterior sem origem menor que o atestado: o restante segue no total (vermelho) ----
    f = FD([("17.11.2021", INI % "PRENDEBEM"),
            ("31.10.2022", "Emitido Atestado de Trabalho nº 318/2022, período de 17/11/2021 a 31/10/2022, 186 dias trabalhados e 62 dias remidos."),
            ("31.10.2022", FIM % ("PRENDEBEM", "A PEDIDO"))])
    _l, res = rf.quadro_trabalho(R(rem(8, "24/10/2023")), f, HOJE)
    p = next(p_ for p_ in res["conc"]["pendencias"] if p_["texto"].startswith("Atestado 318"))
    ok(p["status"] == "NAO_LANCADO" and p["cor"] == "vermelho" and "faltam ≈ 54" in p["texto"], "7: pendência %r" % p)
    ok(abs((res.get("pendentes") or 0) - 54) < 0.01, "7: total %r" % res.get("pendentes"))

    # ---- 8: remição a maior que o atestado ligado: o excedente abate o outro atestado não lançado, emitido antes da decisão ----
    f = FD([("01.11.2023", INI % "HORTA"),
            ("30.07.2024", "Emitido Atestado de Trabalho nº 120/2024, período de 01/11/2023 a 29/07/2024, 201 dias trabalhados e 67 dias remidos."),
            ("03.02.2025", "Emitido Atestado de Trabalho nº 015/2025, período de 30/07/2024 a 03/02/2025, 162 dias trabalhados e 54 dias remidos.")])
    C = rrm.conciliar(R(rem(94, "12/03/2025", "03/02/2025")), f, HOJE)
    a120 = next(a for a in C["atestados"] if a["numero"] == "120/2024")
    ok(abs(a120.get("rem_pend", 99) - 27) < 0.01, "8: pendente do 120/2024 %r" % a120.get("rem_pend"))

    # ---- 9: leitura com remição dos mesmos dias pouco antes da petição registrada: provavelmente remida, fora do total ----
    f = FD([("24.02.2026", "EDUCAÇÃO: Peticionados os relatórios de leitura, referentes aos meses 10, 11 e 12 de 2025 e mês 01 de 2026, no sistema SEEU, Autos Nº 0009999-11.2020.8.12.0001.")])
    _l, res = rf.quadro_trabalho(R(rem(16, "09/02/2026")), f, HOJE)
    lt = next((i for i in blocos(res) if i["emp"].startswith("Leitura")), {})
    ok(lt.get("cor") == "amarelo" and lt.get("sit", "").startswith("Provavelmente remida"), "9: leitura %r" % lt)
    ok(not res.get("leituras_f") and not (res["rem_det"]["leitura"]["dias"]), "9: leitura no total %r" % res.get("leituras_f"))

    # ---- 10: ENEM 2024 não explica remição com referência em 2023; ENCCEJA decidido 5 dias antes do registro do certificado ----
    f = FD([("11.04.2025", "Peticionado Certificado do Enem 2024 no Sistema SEEU nos Autos Nº 0009999-11.2020.8.12.0001."),
            ("30.01.2024", "FOI APROVADO, RECEBEU O CERTIFICADO DE CONCLUSÃO DO ENSINO FUNDAMENTAL PELA PROVA DO ENCCEJA 2023.")])
    C = rrm.conciliar(R(rem(26, "14/08/2025", "31/07/2023"), rem(177, "25/01/2024", "31/12/2023")), f, HOJE)
    ok("ENEM 2024" not in alertas(C) and "177 dias em 25/01/2024: provável ENCCEJA 2023" in alertas(C), "10: exames %s" % alertas(C))

    # ---- 11: lacuna entre atestados sem o período de liberdade ----
    f = FD([("18.10.2013", INI % "MANDIOCA"),
            ("28.04.2025", "Emitido Atestado de Trabalho nº 119/2025, período de 17/09/2012 a 04/11/2013, 180 dias trabalhados e 60 dias remidos."),
            ("16.04.2024", INI % "PRENDEBEM"),
            ("18.05.2026", "Emitido Atestado de Trabalho nº 065/2026, período de 16/04/2024 a 18/05/2026, 277 dias trabalhados e 92,33 dias remidos.")])
    r = R(prisao="10/09/2012", eventos=[{"data": "05/11/2013", "tipo": "INTERRUPÇÃO", "motivo": "ALVARÁ DE SOLTURA"},
                                         {"data": "05/10/2023", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}])
    C = rrm.conciliar(r, f, HOJE)
    lac = [p["texto"] for p in C["pendencias"] if p["status"] == "LACUNA"]
    ok(lac and all(not t.startswith("05/11/2013") for t in lac) and any(t.startswith("05/10/2023") for t in lac), "11: lacuna %r" % lac)

    # ---- 12: inteiro sem truncar (963 / 3 = 321) ----
    ok(rrm._fmtn(962.9999999999 / 3) == "321", "12: _fmtn %r" % rrm._fmtn(962.9999999999 / 3))

    # ---- 13: referência tardia: só os dias do atestado na decisão conjunta; progressão desfeita por nova fixação de regime ----
    f = FD([("10.02.2020", "Emitido Atestado de Trabalho nº 0111/2020, período de 29/08/2019 a 07/10/2019, 35 dias trabalhados e 12 dias remidos."),
            ("21.07.2022", "Emitido Atestado de Trabalho nº 272/2022, período de 20/01/2021 a 21/07/2022, 341 dias trabalhados e 113 dias remidos.")])
    prog = {"tipo": "FIXAÇÃO/ALTERAÇÃO DE REGIME", "complemento": "Semiaberto - Progressão de Regime", "data_decisao": "23/06/2020",
            "data_referencia": "27/04/2020", "situacao": "CONCEDIDO"}
    r = R(rem(125, "28/07/2022"), prog)
    C = rrm.conciliar(r, f, HOJE)
    al = rf._referencia_remicao(r, C)
    ok(any("12 dias do atestado 0111/2020 (parte da remição de 125 dias" in i["titulo"] for i in al), "13: alerta da decisão conjunta %r" % [i["titulo"] for i in al])
    refix = {"tipo": "FIXAÇÃO/ALTERAÇÃO DE REGIME", "complemento": "Fechado - Somatório de Penas", "data_decisao": "18/03/2021",
             "data_referencia": "18/03/2021", "situacao": "CONCEDIDO"}
    r2 = R(rem(125, "28/07/2022"), prog, refix)
    ok(not rf._referencia_remicao(r2, rrm.conciliar(r2, f, HOJE)), "13: progressão desfeita pelo somatório ainda gera alerta")

    # ---- 14: perda sem falta datada antes da falta, somadas acima de 1/3 ----
    incs = [rem(250, "01/08/2014"), {"tipo": "DIAS PERDIDOS NA REMIÇÃO", "complemento": "83 Dia(s)", "data_decisao": "24/08/2015", "situacao": "CONCEDIDO"},
            {"tipo": "FALTA GRAVE", "complemento": "Fuga em 18/11/2019", "data_decisao": "10/01/2020", "data_referencia": "18/11/2019", "situacao": "CONCEDIDO"},
            {"tipo": "DIAS PERDIDOS NA REMIÇÃO", "complemento": "26 Dia(s)", "data_decisao": "10/01/2020", "situacao": "CONCEDIDO"}]
    its = ra._perda_remidos(incs, 109)
    tits = " | ".join(i["titulo"] for i in its)
    ok("sem falta grave datada no RSPE (decisão de 24/08/2015)" in tits and "somadas acima de 1/3" in tits, "14: perdas %s" % tits)
    ok(not any(i["nivel"] == "info" and "Dentro do limite" in (i.get("detalhe") or "") for i in its), "14: 'dentro do limite' contraditório")

    # ---- 15: trabalho atual iniciado há menos de 6 meses: o atestado antigo não está "vencido" ----
    f = FD([("01.03.2019", INI % "FAXINA"), ("31.08.2019", FIM % ("FAXINA", "A PEDIDO")),
            ("05.09.2019", "Emitido Atestado de Trabalho nº 100/2019, período de 01/03/2019 a 31/08/2019, 155 dias trabalhados e 51 dias remidos."),
            ("15.08.2026", INI % "PRENDEBEM")])
    out = rf.comparativo(R(rem(51, "10/10/2019", "31/08/2019")), f, HOJE)
    ok("Último atestado há 6 meses" not in out["fd_sit"], "15: último atestado vencido com trabalho novo %r" % out["fd_sit"])

    # ---- 16: matrícula cancelada sem a matrícula registrada: estudo a conferir ----
    f = FD([("12.02.2019", "EDUCAÇÃO: Cancelamento de Matrícula. Saida do Presidio")])
    out = rf.comparativo(R(prisao="02/03/2018"), f, HOJE)
    ok("matrícula cancelada em 12/02/2019" in (out.get("fd_sit_det") or ""), "16: estudo sem matrícula %r" % out.get("fd_sit_det"))
except Exception as e:
    import traceback
    traceback.print_exc()
    falhas.append("exceção: %r" % e)
print("\n".join(falhas) if falhas else "ok: conferência 7.13.0 - D1 (remição ligada à origem: estudo, cursos, leitura somada, capacidade, "
      "cumulativo contido, outra custódia, remição sem origem parcial, excedente, exame, lacuna, referência tardia, perdas, último atestado, matrícula)")
sys.exit(1 if falhas else 0)
