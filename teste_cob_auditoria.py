"""Correção 7.14.8, frente auditoria (base simulada independente): citação do REsp 2.037.377/SC por inteiro e parágrafo do prejuízo
na fundamentação do 1/6 x 16%; prisão desta execução lançada como "interrupção por prisão em outro processo", sem reinício
(alerta); data-base no início da guia nova com a pessoa presa (alerta); monitoramento/domiciliar e espera de vaga lançados como
interrupção (alerta); remição em duplicidade que favorece o assistido (info); medida de segurança sem "Faltam dados" nem "guia
sem pena calculada"; milícia com 75% sem "tratou como hediondo"; domínio social estruturado (ultraviolenta elementar do tipo);
crime do Título XII do CP (Lei 15.402/2026, retroativa).
Casos hipotéticos, nomes fictícios. Rodar: python teste_cob_auditoria.py"""
import copy
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_auditoria as ra
import rspe_ficha as rf
import rspe_scraper as rs

falhas = []
HOJE = date(2026, 10, 12)
P1, P2 = "0000001-11.2020.8.12.0001", "0000002-22.2023.8.12.0001"
PEXEC = "6000009-99.2026.8.12.0001"
PR, INT = "PRISÃO/INÍCIO DE CUMPRIMENTO", "INTERRUPÇÃO"


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def crime(**kw):
    c = {"processo_criminal": P1, "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto", "tipo_penal": "CAPUT: Subtrair",
         "pena_imposta": "6 ano(s), 0 mês(es) e 0 dia(s)", "pena_total_processo": "6a0m0d - PENA ORIGINÁRIA", "data_infracao": "03/08/2020",
         "data_denuncia": "02/09/2020", "data_sentenca": "19/02/2021", "transito_mp": "20/04/2021", "transito_processo": "20/04/2021",
         "extinto": "Não", "suspenso": "Não", "vga": "N", "resultado_morte": "N", "reincidente_comum": "N", "reincidente_especifico": "N",
         "comando_orcrim": "N", "fracao_progressao": "1/6 - Comum", "fracao_livramento": "1/3 - Comum Primário", "regime_sentenca": "Fechado"}
    c.update(kw)
    return c


def ev(tipo, motivo, data, processos=P1):
    return {"tipo": tipo, "motivo": motivo, "complemento": "", "data": data, "data_decisao": "", "data_referencia": "", "processos": processos}


def inc(tipo, comp, dec="", ref="", sit="CONCEDIDO"):
    return {"tipo": tipo, "motivo": "", "complemento": comp, "data": "", "data_decisao": dec, "data_referencia": ref or dec, "processos": "", "situacao": sit}


def reg(crimes, eventos=(), incidentes=None, **kw):
    r = {"nome": "Teste Ficticio", "processo_execucao": PEXEC, "regime_atual": "Fechado - ATIVO", "pena_total": "6a0m0d",
         "pena_cumprida": "1a0m0d", "pena_remanescente": "5a0m0d", "total_interrupcoes": "0a0m0d",
         "saldo_remidos": "0 dias (0 dias remidos - 0 dias perdidos)", "data_geracao_rspe": "05/10/2026", "data_base_seeu": "",
         "termino_previsao_seeu": "01/01/2030", "data_nascimento": "01/01/1975", "status_execucao": "ATIVO", "_crimes": crimes,
         "_eventos": list(eventos), "_incidentes": list(incidentes if incidentes is not None else [inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Fechado - Regime Inicial")])}
    r.update(kw)
    return r


def aud(r):
    r = copy.deepcopy(r)
    rs.derivar(r, r["_crimes"], r["_eventos"], r["_incidentes"])
    return ra.auditar(r, HOJE)["aud_itens"]


def tipo(A, t):
    return [i for i in A if i.get("tipo") == t]


try:
    # ---- 1 (S4056): citação dos precedentes por inteiro e parágrafo do prejuízo ----
    cit = ra._citacoes("LEP, art. 112 (CF, art. 5º, XL; STJ Temas 1084, 1196 e 1354 - na pena unificada, cada condenação mantém a sua "
                       "fração, REsp 2.037.377/SC, 3ª Seção, 18/06/2026; STF Tema 1169).", "")
    ok(cit == "STJ, Temas 1084, 1196 e 1354, e REsp 2.037.377/SC (3ª Seção, 18/06/2026); STF, Tema 1169", "1: citação: %s" % cit)
    ok(ra._citacoes("CP, art. 63; em sentido contrário, STJ, AgRg no HC 790.968.", "") == "", "1: precedente contrário citado como 'nesse sentido'")
    ok(ra._citacoes("STJ, HC 57.300, REsp 751.762 e HC 1.000", "") == "STJ, HC 57.300, REsp 751.762 e HC 1.000",
       "1: lista de julgados: %s" % ra._citacoes("STJ, HC 57.300, REsp 751.762 e HC 1.000", ""))
    r1 = reg([crime()], [ev(PR, "PRISÃO DEFINITIVA", "14/08/2022")], data_base_seeu="14/08/2022", pena_cumprida="4a1m24d",
             progressao_previsao_seeu="13/08/2023")
    A1 = [i for i in tipo(aud(r1), "percentual-de-progressao-diverge") if i["nivel"] == "alerta"]
    f1 = ra.fundamentacao(A1[0], r1) if A1 else ""
    ok("REsp 2.037.377/SC (3ª Seção, 18/06/2026)" in f1 and "18, 06" not in f1 and "2.037.377, 18" not in f1, "1: fundamentação: %s" % f1)
    ok(len(f1.split("\n\n")) == 4 and "Com isso, exige-se para a progressão mais pena cumprida" in f1, "1: sem o parágrafo do prejuízo: %s" % f1)
    ok("pedir a retificação" not in f1.split("\n\n")[0], "1: orientação ao operador no parágrafo dos fatos: %s" % f1)

    # ---- 2 (S4027): interrupção "por prisão em outro processo" que cita processo desta execução, sem reinício ----
    r2 = reg([crime(artigo="ART 157: Roubo", vga="S", fracao_progressao="25% - Art.112, III", pena_imposta="8 ano(s), 0 mês(es) e 0 dia(s)",
                    pena_total_processo="8a0m0d - PENA ORIGINÁRIA", data_infracao="10/02/2021")],
             [ev(PR, "PRISÃO DEFINITIVA", "01/06/2021"), ev(INT, "INTERRUPÇÃO POR PRISÃO EM OUTRO PROCESSO", "10/01/2024")],
             pena_total="8a0m0d", pena_cumprida="2a7m14d", pena_remanescente="5a4m16d", total_interrupcoes="2a8m29d",
             data_base_seeu="01/06/2021", termino_previsao_seeu="")
    A2 = [i for i in tipo(aud(r2), "pena-cumprida-menor-que-custodia") if i["nivel"] == "alerta" and "interrupção" in i["titulo"]]
    ok(A2 and "sem cômputo" in A2[0]["titulo"] and "CP, art. 42" in A2[0]["fundamento"], "2: prisão desta execução como interrupção: %s" % A2)
    # interrupção por prisão em processo que não é desta execução: sem o alerta
    r2b = copy.deepcopy(r2)
    r2b["_eventos"][1]["processos"] = P2
    ok(not [i for i in tipo(aud(r2b), "pena-cumprida-menor-que-custodia") if i["nivel"] == "alerta"], "2: outro processo de fato virou alerta")

    # ---- 3 (S4014): data-base no início da guia nova com a pessoa presa sem interrupção: alerta ----
    c3a = crime(artigo="ART 171: Estelionato", fracao_progressao="16% - Art.112, I", pena_imposta="4 ano(s), 0 mês(es) e 0 dia(s)",
                pena_total_processo="4a0m0d - PENA ORIGINÁRIA", data_infracao="02/03/2021", data_sentenca="18/09/2021",
                transito_mp="17/11/2021", transito_processo="17/11/2021")
    c3b = crime(processo_criminal=P2, artigo="ART 157: Roubo", vga="S", fracao_progressao="25% - Art.112, III", data_infracao="16/02/2021",
                pena_imposta="5 ano(s), 4 mês(es) e 0 dia(s)", pena_total_processo="5a4m0d - PENA ORIGINÁRIA", data_sentenca="04/09/2021",
                transito_mp="21/11/2023", transito_processo="21/11/2023")
    r3 = reg([c3a, c3b], [ev(PR, "PRISÃO EM FLAGRANTE", "11/03/2021"), ev(PR, "PRISÃO DEFINITIVA", "18/12/2023", P2)],
             [inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Fechado - Regime Inicial", ref="11/03/2021"),
              inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Fechado - Regime Inicial", ref="18/12/2023")],
             pena_total="9a4m0d", pena_cumprida="5a7m0d", pena_remanescente="3a9m0d", data_base_seeu="18/12/2023",
             progressao_previsao_seeu="19/12/2025")
    A3 = tipo(aud(r3), "data-base-no-inicio-da-guia-nova-com-a-pessoa-presa")
    ok(A3 and A3[0]["nivel"] == "alerta" and "11/03/2021" in A3[0]["titulo"], "3: data-base na guia nova: %s" % [(i["nivel"], i["titulo"]) for i in A3])

    # ---- 4 (S1010/S1012): domiciliar com monitoramento e espera de vaga lançadas como interrupção: alerta ----
    r4 = reg([crime(data_infracao="02/02/2022")], [ev(PR, "PRISÃO DEFINITIVA", "08/02/2024"),
                                                   ev(INT, "PRISÃO DOMICILIAR COM MONITORAMENTO ELETRÔNICO", "01/04/2026", "")],
             regime_atual="Semiaberto - ATIVO", pena_cumprida="2a1m24d", total_interrupcoes="0a6m7d", termino_previsao_seeu="",
             data_base_seeu="08/02/2024")
    A4 = tipo(aud(r4), "cumprimento-lancado-como-interrupcao")
    ok(A4 and A4[0]["nivel"] == "alerta" and "187 dias" in A4[0]["titulo"] and "146-B" in A4[0]["fundamento"], "4: monitoramento: %s" % A4)
    r4b = reg([crime(data_infracao="02/02/2022", pena_imposta="4 ano(s), 0 mês(es) e 0 dia(s)", pena_total_processo="4a0m0d - PENA ORIGINÁRIA")],
              [ev(PR, "PRISÃO DEFINITIVA", "03/03/2026"), ev(INT, "INCOMPATIBILIDADE DE REGIME - AGUARDANDO VAGA", "03/03/2026", "")],
              [inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Semiaberto - Regime Inicial", ref="03/03/2026")],
              regime_atual="Semiaberto - ATIVO", pena_total="4a0m0d", pena_cumprida="0a0m1d", pena_remanescente="3a11m29d",
              total_interrupcoes="0a7m6d", termino_previsao_seeu="", data_base_seeu="03/03/2026")
    A4b = tipo(aud(r4b), "cumprimento-lancado-como-interrupcao")
    ok(A4b and A4b[0]["nivel"] == "alerta" and "incompatibilidade" in A4b[0]["titulo"] and "Vinculante 56" in A4b[0]["fundamento"],
       "4: espera de vaga: %s" % A4b)
    # fuga não é cumprimento: sem o item
    r4c = copy.deepcopy(r4)
    r4c["_eventos"][1]["motivo"] = "FUGA"
    ok(not tipo(aud(r4c), "cumprimento-lancado-como-interrupcao"), "4: fuga tratada como cumprimento")
    # ficha: monitoramento desta execução no período que o RSPE trata como interrupção - alerta
    r4d = reg([crime()], [ev(PR, "PRISÃO DEFINITIVA", "01/06/2021"), ev(INT, "INTERRUPÇÃO DO CUMPRIMENTO DA PENA", "01/03/2023"),
                          ev(PR, "RECAPTURA", "10/02/2024")], data_base_seeu="10/02/2024", progressao_previsao_seeu="15/04/2027")
    f4d = {"data_impressao": "02/10/2026", "eventos": [
        {"data": "03.03.2023", "texto": "Entrada na Unidade Penal: UNIDADE MISTA DE MONITORAMENTO VIRTUAL ESTADUAL, Conforme OF/CI %s." % PEXEC},
        {"data": "05.02.2024", "texto": "Saída da Unidade Penal: UNIDADE MISTA DE MONITORAMENTO VIRTUAL ESTADUAL, Destino: PENITENCIÁRIA X, Conforme: %s." % PEXEC}]}
    I4d = rf._monitoramento_x_ficha(r4d, f4d)
    ok(I4d and I4d[0]["nivel"] == "alerta", "4: monitoramento da ficha: %s" % I4d)

    # ---- 5 (S4035): remição em duplicidade com o saldo também em dobro: info; saldo sem a duplicata: alerta ----
    rem = [inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Fechado - Regime Inicial", ref="05/01/2021"),
           inc("REMIÇÃO", "45 Dia(s) Remido(s)", "10/05/2024", "30/04/2024"), inc("REMIÇÃO", "45 Dia(s) Remido(s)", "10/05/2024", "30/04/2024")]
    r5 = reg([crime()], [ev(PR, "PRISÃO DEFINITIVA", "05/01/2021")], rem, saldo_remidos="90 dias (90 dias remidos - 0 dias perdidos)")
    A5 = tipo(aud(r5), "remicao-lancada-em-duplicidade")
    ok(A5 and all(i["nivel"] == "info" for i in A5), "5: duplicidade favorável: %s" % [(i["nivel"], i["titulo"]) for i in A5])
    r5b = reg([crime()], [ev(PR, "PRISÃO DEFINITIVA", "05/01/2021")], rem, saldo_remidos="45 dias (45 dias remidos - 0 dias perdidos)")
    ok([i for i in tipo(aud(r5b), "remicao-lancada-em-duplicidade") if i["nivel"] == "alerta"], "5: duplicidade fora do saldo sem alerta")

    # ---- 6 (S1045): medida de segurança - sem "Faltam dados" de término e pena nem "guia sem pena calculada" ----
    r6 = reg([crime(pena_total_processo="1a0m0d - MEDIDA DE SEGURANÇA", regime_sentenca="Indefinido", pena_imposta="0 ano(s), 0 mês(es) e 0 dia(s)",
                    data_infracao="02/02/2023")], [ev(PR, "INTERNAÇÃO", "15/09/2025")], pena_total="0a0m0d", pena_cumprida="0a0m0d",
             pena_remanescente="0a0m0d", regime_atual="", termino_previsao_seeu="", data_base_seeu="15/09/2025")
    A6 = aud(r6)
    ok(not [i for i in A6 if i.get("tipo") in ("faltam-dados-termino_previsao_seeu", "faltam-dados-pena_total", "guia-sem-pena-calculada-pena-total-com")],
       "6: medida de segurança: %s" % [i["titulo"] for i in A6 if i["nivel"] == "alerta"])

    # ---- 7 (S3022): milícia privada com 75% - percentual legal, não "tratou como hediondo" ----
    r7 = reg([crime(artigo="ART 288-A: Constituição de milícia privada", tipo_penal="CAPUT: Constituir milícia particular",
                    data_infracao="01/06/2026", fracao_progressao="75% - Art.112, VI, c, da LEP", pena_imposta="5 ano(s), 0 mês(es) e 0 dia(s)",
                    pena_total_processo="5a0m0d - PENA ORIGINÁRIA", data_sentenca="01/09/2026", transito_mp="20/09/2026", transito_processo="20/09/2026")],
             [ev(PR, "PRISÃO EM FLAGRANTE", "01/06/2026")], pena_total="5a0m0d", data_base_seeu="01/06/2026")
    A7 = aud(r7)
    ok(not tipo(A7, "seeu-tratou-como-hediondo-mas-o-tipo-nao-consta") and tipo(A7, "percentual-de-progressao-confere"),
       "7: milícia: %s" % [(i["nivel"], i["titulo"]) for i in A7])

    # ---- 8 (S3023): domínio social estruturado com comando - organização ultraviolenta é elementar do tipo ----
    r8 = reg([crime(lei="15358/26 - Marco Legal do Combate ao Crime Organizado", artigo="ART 2: Domínio social estruturado",
                    tipo_penal="§ 1º, I: domínio social estruturado - comando da organização criminosa ultraviolenta, Reclusão: 20 a 40 anos",
                    data_infracao="02/05/2026", vga="S", comando_orcrim="S", fracao_progressao="75% - Art.112, VI, b, da LEP",
                    fracao_livramento="1/1 - Comando de organização ultraviolenta", pena_imposta="25 ano(s), 0 mês(es) e 0 dia(s)",
                    pena_total_processo="25a0m0d - PENA ORIGINÁRIA", data_sentenca="01/09/2026", transito_mp="20/09/2026", transito_processo="20/09/2026")],
             [ev(PR, "PRISÃO EM FLAGRANTE", "02/05/2026")], pena_total="25a0m0d", data_base_seeu="02/05/2026")
    A8 = aud(r8)
    ok(not [i for i in A8 if i.get("tipo") in ("comando-de-organizacao-criminosa-fato-em-75-so-s", "livramento-vedado-pelo-seeu-1-1-so-se-a-organiza",
                                                 "percentual-de-progressao-diverge", "fracao-de-livramento-diverge")],
       "8: domínio social estruturado: %s" % [(i["nivel"], i["titulo"]) for i in A8 if i["nivel"] != "ok"])

    # ---- 9 (S3027): crime do Título XII (art. 359-L), fato de 2023: Lei 15.402/2026 retroage - 1/6, SEEU 25% = alerta ----
    r9 = reg([crime(processo_criminal=P2, artigo="ART 359-L: Abolição violenta do Estado Democrático de Direito",
                    tipo_penal="CAPUT: Tentar, com emprego de violência ou grave ameaça, abolir o Estado Democrático de Direito",
                    data_infracao="08/01/2023", vga="S", fracao_progressao="25% - Art.112, III, da LEP", pena_imposta="5 ano(s), 6 mês(es) e 0 dia(s)",
                    pena_total_processo="5a6m0d - PENA ORIGINÁRIA", data_sentenca="10/06/2026", transito_mp="10/08/2026", transito_processo="10/08/2026")],
             [ev(PR, "PRISÃO DEFINITIVA", "25/09/2026", P2)], pena_total="5a6m0d", data_base_seeu="25/09/2026", pena_cumprida="0a0m10d")
    A9 = [i for i in tipo(aud(r9), "percentual-de-progressao-diverge") if i["nivel"] == "alerta"]
    ok(A9 and "25%" in A9[0]["titulo"] and "16,67%" in A9[0]["titulo"] and "Título XII" in A9[0]["detalhe"], "9: Título XII: %s" % A9)
    # crime com violência fora do Título XII, mesmo fato: 25% confere
    r9b = copy.deepcopy(r9)
    r9b["_crimes"][0].update(artigo="ART 157: Roubo", tipo_penal="CAPUT: Subtrair mediante grave ameaça")
    ok(not tipo(aud(r9b), "percentual-de-progressao-diverge"), "9: roubo de 2023 com 25% virou divergência")
except Exception:
    import traceback
    falhas.append(traceback.format_exc())

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for x in falhas:
        print(" -", x)
    sys.exit(1)
print("ok: correção 7.14.8, frente auditoria (citação do REsp, prejuízo, prisão desta execução como interrupção, data-base da guia nova, "
      "monitoramento e espera de vaga, remição em dobro favorável, medida de segurança, milícia, domínio social estruturado, Título XII)")
