"""Conferência 7.14.3 -> 7.14.4 (resíduos da validação): saldo de remição sem documento antes do atestado sem período que absorve o
intervalo pela capacidade; atestado de estudo ligado pela carga horária; detração antes da fração com a "Diferença" = lapso impresso −
forma favorável; regime inicial citado pelo último válido; "execução suspensa ou sobrestada"; âncora do SEEU só como referência;
extinção da ficha repetida uma vez só no aviso de reincidência. Dados fictícios (sem nomes). Rodar: python teste_conf5.py"""
import sys
import types
from datetime import date
from fractions import Fraction

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_auditoria as ra
import rspe_ficha as rf
import rspe_reincidencia as rr
import rspe_scraper as rs
import rspe_view as rv
from teste_remicao_714 import R, T, A, F, HOJE

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def lin(N):
    return [(L["local"], L["periodo"].split(" (")[0], L["st"], L["at"]) for L in N["trab"]["linhas"]]


try:
    # ---- 1) remição sem documento x atestado sem período emitido depois (decisão do usuário): o saldo cobre primeiro o trabalho mais
    # próximo da remição; o atestado sem período, que só absorve o intervalo pela capacidade, fica com o restante ----
    f = F([T("COPA", "04.01.2021", "30.01.2021"), T("MANUAL", "01.03.2021", "30.06.2021"), T("COSTURA", "01.03.2022", "31.12.2022"),
           T("MARCENARIA", "01.03.2023", "31.10.2023")],
          [A("001/2021", "01.02.2021", "04/01/2021", "30/01/2021", 8, 24, "Copa"), A("050/2024", "15.01.2024", rem=250)])
    o, N = (lambda o: (o, o["fd_novo"]))(rf.comparativo(R((20, "30/06/2022", None)), f, HOJE))
    L = lin(N)
    cos = [x for x in L if x[0] == "Costura"]
    ok(("Costura", "22/04/2022 a 30/06/2022", "sem", "") in cos and ("Costura", "01/03/2022 a 21/04/2022", "provavel", "050/2024") in cos
       and ("Costura", "01/07/2022 a 31/12/2022", "provavel", "050/2024") in cos, "1: Costura dividida (saldo antes do atestado): %s" % cos)
    ok(abs(N["talvez_dias"] - 20) <= 1 and N["pedir_dias"] == 0, "1: saldo de 20 dias no trabalho mais próximo: %s %s" % (N["talvez_dias"], N["pedir_dias"]))
    ok(all(x[2] == "provavel" for x in L if x[0] in ("Manual", "Marcenaria")), "1: o atestado fica com o restante: %s" % L)
    # sem remição sem documento: o atestado continua com todo o intervalo
    o, N = (lambda o: (o, o["fd_novo"]))(rf.comparativo(R(), f, HOJE))
    ok([x for x in lin(N) if x[0] == "Costura"] == [("Costura", "01/03/2022 a 31/12/2022", "provavel", "050/2024")],
       "1: sem saldo, nada muda: %s" % lin(N))
    # atestado cujos dias batem com o intervalo (não pela capacidade): continua com tudo
    f2 = F(f["trabalho"], [f["atestados"][0], A("050/2024", "15.01.2024", rem=190)])
    o, N = (lambda o: (o, o["fd_novo"]))(rf.comparativo(R((20, "30/06/2022", None)), f2, HOJE))
    ok([x for x in lin(N) if x[0] == "Costura"] == [("Costura", "01/03/2022 a 31/12/2022", "provavel", "050/2024")],
       "1: atestado que fecha com o intervalo: %s" % lin(N))

    # ---- 2) atestado de estudo com 180 h: os dias declarados (7,5) não fecham com remição próxima; 180 ÷ 12 = 15 fecha ----
    est = [{"curso": "Atestado de estudo nº 329/2022", "data": "03.11.2022", "inicio": "02.05.2022", "fim": "02.08.2022", "horas": 180,
            "dias_remidos": 7.5, "texto": ""}]
    o = rf.comparativo(R((15, "17/02/2023", None), (8, "24/10/2023", None)), F(estudos=est), HOJE)
    d = next(x for x in o["fd_novo"]["docs"] if x["tipo"] == "Atestado de estudo")
    ok(d.get("provavel") == "17/02/2023" and "180 h ÷ 12" in d["sit"] and "a ficha declara 7,5" in d["sit"], "2: ligação pela carga horária: %s" % d["sit"])
    # com remição próxima do valor declarado, fica a dos dias declarados
    o = rf.comparativo(R((15, "17/02/2023", None), (7.5, "10/12/2022", None)), F(estudos=[dict(est[0])]), HOJE)
    d = next(x for x in o["fd_novo"]["docs"] if x["tipo"] == "Atestado de estudo")
    ok(d.get("provavel") == "10/12/2022" and not d.get("provavel_horas"), "2: o valor declarado fecha: %s" % d["sit"])

    # ---- 3) detração antes da fração: Diferença = lapso impresso − forma favorável (as três linhas fecham) ----
    t = ra._texto_blocos([[Fraction(2, 5), rs.pena_para_dias("15a2m20d"), rs.pena_para_dias("5a4m24d"), 626, [5, 4, 24], [15, 2, 20]]])
    # (7.14.5) ano de 365 dias: forma favorável 4a4m16d; diferença 1a0m8d (373 dias ≈ 626 × 0,6)
    ok("Lapso total impresso: 5 anos, 4 meses e 24 dias" in t and "4 anos, 4 meses e 16 dias" in t and "Diferença: 1 ano e 8 dias" in t,
       "3: diferença coerente: %s" % t)

    # ---- 4) regime inicial relançado: o item "sem efeito atual" cita o último válido (a análise não muda) ----
    AR, PR = "FIXAÇÃO/ALTERAÇÃO DE REGIME", "PRISÃO/INÍCIO DE CUMPRIMENTO"
    inc = lambda tipo, compl, dec, ref: {"tipo": tipo, "motivo": "", "complemento": compl, "data": "", "data_decisao": dec,
                                         "data_referencia": ref, "processos": "", "situacao": "CONCEDIDO"}
    ev = lambda tipo, motivo, data, procs="0000001-11.2020.8.12.0001": {"tipo": tipo, "motivo": motivo, "data": data, "processos": procs}
    cr = {"processo_criminal": "0000001-11.2020.8.12.0001", "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto",
          "tipo_penal": "CAPUT: Subtrair, Reclusão: 1 a 4 anos", "pena_imposta": "10 ano(s), 0 mês(es) e 0 dia(s)",
          "data_infracao": "10/01/2016", "data_sentenca": "10/06/2016", "transito_mp": "10/07/2016", "transito_processo": "10/07/2016",
          "extinto": "Não", "suspenso": "Não", "vga": "N", "resultado_morte": "N", "reincidente_comum": "N", "reincidente_especifico": "N",
          "comando_orcrim": "N", "fracao_progressao": "1/6 - Comum", "fracao_livramento": "1/3 - Comum"}
    evs = [ev(PR, "PRISÃO EM FLAGRANTE", "01/02/2017"), ev("INTERRUPÇÃO", "SOLTURA", "01/06/2017", ""), ev(PR, "PRISÃO DEFINITIVA", "26/08/2019"),
           ev("INTERRUPÇÃO", "FUGA", "01/03/2020", ""), ev(PR, "RECAPTURA", "06/05/2020")]
    incs = [inc(AR, "Aberto - Regime Inicial", "", "26/08/2019"), inc(AR, "Fechado - Regime Inicial", "", "06/05/2020"),
            inc(AR, "Semiaberto - Progressão de Regime", "01/02/2022", "01/02/2022"),
            inc("HOMOLOGAÇÃO DE FALTA GRAVE", "16/03/2026", "20/04/2026", "16/03/2026"), inc(AR, "Fechado - Regressão", "20/04/2026", "16/03/2026")]
    r = {"nome": "Teste", "regime_atual": "Fechado - ATIVO", "pena_total": "10a0m0d", "pena_cumprida": "3a0m0d", "pena_remanescente": "7a0m0d",
         "fracao_progressao_aplicada": "1/6", "data_geracao_rspe": "01/10/2026", "data_base_seeu": "16/03/2026", "_crimes": [cr],
         "_incidentes": incs, "_eventos": evs}
    it = [i for i in ra.auditar(r, HOJE)["aud_itens"] if i.get("tipo") == "regime-inicial-depois-da-primeira-prisao"]
    ok(it and "sem efeito atual" in it[0]["titulo"] and "06/05/2020" in it[0]["titulo"] and "último regime inicial válido" in it[0]["detalhe"]
       and "26/08/2019" in it[0]["detalhe"], "4: último regime inicial válido: %s" % it)

    # ---- 5) "execução suspensa ou sobrestada" (concordância com execução) ----
    fc = rv._fora_de_curso({"status_execucao": "Suspenso ou Sobrestado"}, None, False)
    ok(fc == "execução suspensa ou sobrestada", "5: concordância: %s" % fc)
    ok(rv._fora_de_curso({"status_execucao": "Arquivado"}, None, False) == "execução arquivada", "5: arquivada")

    # ---- 6) âncora do SEEU só como referência; extinção repetida na ficha, uma vez só ----
    nt = rs.nota_falta_eventos("faltavam 3a0m19d para 1/3 em 25/12/2007")
    ok(nt.startswith("vale a contagem pelos eventos") and "só como referência" in nt, "6: âncora: %s" % nt)
    ext = [{"processo": "0000009-99.2010.8.12.0001", "data": date(2016, 3, 21), "texto": "PENA EXTINTA"}] * 2
    c6 = dict(cr, data_infracao="15/01/2018", reincidente_comum="S")
    R6 = rr.reincidencia_pelas_datas(c6, [c6], None, ext)
    ok(R6["fonte"] == "ficha" and R6["motivo"].count("0000009-99.2010.8.12.0001") == 1, "6: processo-base uma vez só: %s" % R6["motivo"])
except Exception:
    import traceback
    traceback.print_exc()
    falhas.append("exceção")

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for x in falhas:
        print(" -", x)
    sys.exit(1)
print("teste_conf5: ok")
