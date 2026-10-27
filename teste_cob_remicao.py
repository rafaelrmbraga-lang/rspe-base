"""Correção da cobertura (7.15.1), frente Remição (aba Ficha): limite de 12 obras de leitura a cada 12 meses (Res. CNJ 391/2021,
art. 5º); certidão de semestre peticionada sem nenhuma remição do RSPE que a explique = provável pendência (amarelo, mesmo com o
RSPE maior que a ficha); trabalho só em período em que esta execução estava interrompida = à parte e nada a atestar; a jornada de
um lançamento que cita outro setor não passa para o vínculo que começa no mesmo dia. Casos hipotéticos, nomes fictícios.
Rodar: python teste_cob_remicao.py"""
import copy
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf

falhas = []
HOJE = date(2026, 10, 12)


def ok(cond, msg):
    print(("ok: " if cond else "FALHA: ") + msg)
    if not cond:
        falhas.append(msg)


def rspe(eventos=(), incidentes=(), interr="0a0m0d"):
    return {"nome": "PESSOA FICTICIA", "processo_execucao": "9909999-00.2026.8.12.0001", "tribunal": "TJMS",
            "vara": "TJMS - 1ª VARA DE EXECUÇÃO PENAL", "status_execucao": "ATIVO", "regime_atual": "Fechado - ATIVO",
            "pena_total": "8a0m0d", "pena_cumprida": "3a9m0d", "pena_remanescente": "4a3m0d", "total_interrupcoes": interr,
            "saldo_remidos": "", "data_base_seeu": "02/01/2023", "data_geracao_rspe": "05/10/2026",
            "_crimes": [{"processo_criminal": "8809999-00.2022.8.12.0001", "pena_total_processo": "8a0m0d - PENA ORIGINÁRIA",
                         "artigo": "ART 157: Roubo", "pena_imposta": "8 ano(s), 0 mês(es) e 0 dia(s)", "data_infracao": "15/03/2022",
                         "transito_processo": "20/12/2022", "extinto": "Não", "suspenso": "Não"}],
            "_eventos": [{"tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO DEFINITIVA", "complemento": "", "data": "02/01/2023",
                          "data_decisao": "", "data_referencia": "", "processos": "8809999-00.2022.8.12.0001"}] + list(eventos),
            "_incidentes": list(incidentes)}


def ficha(eventos):
    ev = [{"data": "02.01.2023", "texto": "Entrada na Unidade Penal: ESTABELECIMENTO PENAL FICTICIO, Procedente: DEPAC, Conforme OF 1/2023."}]
    f = {"tipo": "ficha_disciplinar", "nome": "PESSOA FICTICIA", "data_prisao": "02/01/2023", "data_impressao": "05/10/2026",
         "conduta": "BOA", "autos": ["9909999-00.2026.8.12.0001"], "eventos": ev + [{"data": d, "texto": t} for d, t in eventos],
         "versao_leitura": 0}
    return rf.atualizar(f) or f


def remicao(dias, dec):
    return {"tipo": "REMIÇÃO", "motivo": "", "complemento": "%d Dia(s)" % dias, "data": "", "data_decisao": dec, "data_referencia": dec,
            "processos": "", "situacao": "CONCEDIDO"}


try:
    # 1) leitura: 13 relatórios em 12 meses (dois no mês 09/2026) - até 12 obras a cada 12 meses: 48 dias, não 52
    lei = []
    meses = [(10, 2025), (11, 2025), (12, 2025)] + [(m, 2026) for m in range(1, 10)]
    for k, (m, y) in enumerate(meses, 1):
        em = "05.%02d.%d" % (m % 12 + 1, y + (m == 12))
        lei.append((em, "EDUCAÇÃO: Peticionado relatório de leitura referente ao mês %02d de %d, título do livro: Obra %d, no sistema SEEU." % (m, y, k)))
    lei.append(("02.10.2026", "EDUCAÇÃO: Peticionado relatório de leitura referente ao mês 09 de 2026, título do livro: Obra 13, no sistema SEEU."))
    o1 = rf.comparativo(rspe(), ficha(lei), HOJE)
    ok(o1["fd_remidos"] == "48 / 0", "leitura: 13 obras em 12 meses somam 48 dias (limite de 12 obras) - %s" % o1["fd_remidos"])
    ok(any("limite de 12 obras" in (d.get("sit") or "") for d in o1["fd_novo"]["docs"]), "leitura: a obra que passa do limite diz o motivo")
    # 12 obras de 10/2025 a 09/2026 e a 13ª em 10/2026: nenhum período de 12 meses tem mais de 12 obras - conta inteira (52)
    lei2 = lei[:-1] + [("05.10.2026", "EDUCAÇÃO: Peticionado relatório de leitura referente ao mês 10 de 2026, título do livro: Obra 13, no sistema SEEU.")]
    o1b = rf.comparativo(rspe(), ficha(lei2), HOJE)
    ok(o1b["fd_remidos"] == "52 / 0", "leitura: 13 obras em 13 meses (uma por mês) somam 52 - %s" % o1b["fd_remidos"])
    # 11 obras de 11/2025 a 09/2026 e mais duas em 10/2026: 13 nos 12 meses de 11/2025 a 10/2026 - 48
    lei3 = lei[1:] + [("05.11.2026", "EDUCAÇÃO: Peticionado relatório de leitura referente ao mês 10 de 2026, título do livro: Obra 13, no sistema SEEU.")]
    o1c = rf.comparativo(rspe(), ficha(lei3), date(2026, 11, 20))
    ok(o1c["fd_remidos"] == "48 / 0", "leitura: 13 obras de 11/2025 a 10/2026 somam 48 - %s" % o1c["fd_remidos"])

    # 2) duas certidões semestrais peticionadas sem carga horária e uma só remição de 15 dias, ligada à segunda: a primeira, sem
    # remição que a explique há mais de 180 dias, é provável pendência (amarelo), não "conferir (informativo)" em cinza
    cert = [("03.02.2025", "EDUCAÇÃO: Matrículou-se na Série: EJA ENSINO MÉDIO Turma: A Período: Matutino"),
            ("05.08.2025", "EDUCAÇÃO: Peticionado Certidão de Frequência Escolar referente ao 1º semestre de 2025, no Sistema SEEU."),
            ("10.02.2026", "EDUCAÇÃO: Peticionado Certidão de Frequência Escolar referente ao 2º semestre de 2025, no Sistema SEEU.")]
    o2 = rf.comparativo(rspe(incidentes=[remicao(15, "25/02/2026")]), ficha(cert), HOJE)
    N2 = o2["fd_novo"]
    ok(o2["fd_cor"] == "amarelo" and "Conferir pontos" in o2["fd_sit"], "certidões: situação amarela 'Conferir pontos' - %s / %s" % (o2["fd_cor"], o2["fd_sit"]))
    ok(any("Provável pendência" in x["t"] and "1º semestre de 2025" in x["t"] and x["c"] == "amarelo" for x in N2["onde"]),
       "certidões: ponto amarelo de provável pendência da certidão do 1º semestre")
    ok(N2["diag"]["c"] == "amarelo", "certidões: diagnóstico amarelo - %s" % N2["diag"])
    # a mesma certidão com remição livre depois do peticionamento (duas remições): não é pendência
    o2b = rf.comparativo(rspe(incidentes=[remicao(30, "20/09/2025"), remicao(15, "25/02/2026")]), ficha(cert), HOJE)
    ok(not any("Provável pendência" in x["t"] for x in o2b["fd_novo"]["onde"]), "certidões: com uma remição para cada certidão, sem pendência")
    # peticionada há menos de 180 dias da impressão da ficha: ainda pode vir a decisão - não é pendência
    f2c = ficha(cert)
    f2c["data_impressao"] = "20/12/2025"
    o2c = rf.comparativo(rspe(incidentes=[remicao(15, "25/11/2025")]), f2c, date(2025, 12, 20))
    ok(not any(d.get("pend_sem_rem") for d in o2c["fd_novo"]["docs"]), "certidões: peticionada há menos de 180 dias não vira pendência")

    # 3) trabalho só no período em que esta execução estava interrompida (custódia por outro processo): à parte e nada a atestar
    r3 = rspe(eventos=[{"tipo": "INTERRUPÇÃO", "motivo": "LIBERDADE PROVISÓRIA", "complemento": "", "data": "01/03/2025", "data_decisao": "",
                        "data_referencia": "", "processos": ""},
                       {"tipo": "PRISÃO", "motivo": "RECAPTURA", "complemento": "", "data": "01/07/2025", "data_decisao": "",
                        "data_referencia": "", "processos": ""}], interr="0a4m0d")
    f3 = ficha([("01.03.2025", "Saída da Unidade Penal: ESTABELECIMENTO PENAL FICTICIO, motivo: ALVARÁ DE SOLTURA."),
                ("15.04.2025", "Entrada na Unidade Penal: ESTABELECIMENTO PENAL FICTICIO, Procedente: DEPAC, Conforme OF 9/2025."),
                ("20.04.2025", "TRABALHO: Iniciou atividade laboral, no setor de trabalho HORTA, conforme documento CI 5/2025."),
                ("30.06.2025", "TRABALHO: Deixa de trabalhar, no setor de trabalho HORTA, conforme documento CI 9/2025, motivo: a pedido.")])
    o3 = rf.comparativo(r3, f3, HOJE)
    ok("interrompida" in str(o3["fd_novo"]), "interrupção: o trabalho fica à parte (execução interrompida)")
    ok(o3["fd_atestar"] == "Não", "interrupção: trabalho a atestar 'Não' - %s" % o3["fd_atestar"])
    # o mesmo trabalho estendido para depois da recaptura: há o que atestar nesta execução
    f3b = copy.deepcopy(f3)
    f3b["eventos"][-1] = {"data": "30.09.2025", "texto": "TRABALHO: Deixa de trabalhar, no setor de trabalho HORTA, conforme documento CI 9/2025, motivo: a pedido."}
    f3b["versao_leitura"] = 0
    o3b = rf.comparativo(r3, rf.atualizar(f3b) or f3b, HOJE)
    ok(o3b["fd_atestar"] == "Sim", "interrupção: com trabalho também depois da recaptura, há o que atestar - %s" % o3b["fd_atestar"])

    # 4) jornada: a baixa da Horta "de segunda a sexta" no dia em que a Portaria começa em escala 12x36 não passa para a Portaria
    f4 = ficha([("01.03.2026", "TRABALHO: Iniciou atividade laboral, no setor de trabalho HORTA, conforme documento CI 2/2026, cumprindo carga horária de segunda a sexta."),
                ("01.07.2026", "TRABALHO: Deixa de trabalhar, no setor de trabalho HORTA, conforme documento CI 6/2026, motivo: a pedido, cumprindo carga horária de segunda a sexta."),
                ("01.07.2026", "TRABALHO: Iniciou atividade laboral, no setor de trabalho PORTARIA, conforme documento CI 7/2026. Escala de 12x36."),
                ("31.07.2026", "TRABALHO: Deixa de trabalhar, no setor de trabalho PORTARIA, conforme documento CI 8/2026, motivo: a pedido.")])
    jor = {t["setor"]: t.get("jornada") for t in f4["trabalho"]}
    ok(jor.get("PORTARIA") == "12x36" and jor.get("HORTA") == "seg-sex", "jornada: cada setor com a sua (%s)" % jor)
except Exception:
    import traceback
    falhas.append(traceback.format_exc())
    print(falhas[-1])

if falhas:
    print("FALHAS (%d)" % len(falhas))
    sys.exit(1)
print("teste_cob_remicao: OK")
