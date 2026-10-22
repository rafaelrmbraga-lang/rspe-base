"""Terceira conferência independente (7.14.7), frente remição, auditoria, livramento, prescrição e progressão: estudo encerrado pelo
"desligado da Escola"; teto do exame (ENEM 100 dias) e o atestado do mesmo dia com valor próximo; duas certidões semestrais e uma só
remição (provável pendência); ficha que cita o número do próprio RSPE (sem aviso de outra execução); primeiro atestado sem período
que cobre o trabalho contínuo; data-base na recaptura depois de "descumprimento das condições" sem falta homologada; regressão da
mesma decisão da falta homologada; número de processo truncado na ficha; pena acima do máximo do dispositivo; encaminhamento à
Disciplinar como falta a apurar; livramento de 1/2 em contravenção; evasão da ficha na interrupção (art. 113); art. 28 preso pelas
outras condenações (suspensão, não cumprimento); homicídio qualificado anterior à Lei 13.964/2019 na saída temporária.
Casos hipotéticos, nomes fictícios. Rodar: python teste_conf8_demais.py"""
import copy
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_auditoria as ra
import rspe_ficha as rf
import rspe_prescricao as rp
import rspe_remicao as rrm
import rspe_view as rv

falhas = []
HOJE = date(2026, 10, 21)
P1, P2 = "0000001-11.2020.8.12.0001", "0000002-22.2025.8.12.0001"
PEXEC = "6000009-99.2023.8.12.0001"


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def crime(**kw):
    c = {"processo_criminal": P1, "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto", "tipo_penal": "CAPUT: Subtrair",
         "pena_imposta": "2 ano(s), 0 mês(es) e 0 dia(s)", "data_infracao": "10/01/2021", "data_denuncia": "10/03/2021",
         "data_sentenca": "10/06/2021", "transito_mp": "10/07/2021", "transito_processo": "10/07/2021", "extinto": "Não", "suspenso": "Não",
         "vga": "N", "resultado_morte": "N", "reincidente_comum": "N", "reincidente_especifico": "N", "comando_orcrim": "N",
         "fracao_progressao": "1/6 - Comum", "fracao_livramento": "1/3 - Comum", "regime_sentenca": "Fechado", "hediondo_ou_equiparado": "N"}
    c.update(kw)
    return c


def ev(tipo, motivo, data, processos=P1):
    return {"tipo": tipo, "motivo": motivo, "data": data, "processos": processos}


def reg(crimes, eventos=(), **kw):
    r = {"nome": "Teste Ficticio", "regime_atual": "Fechado - ATIVO", "pena_total": "2a0m0d", "pena_cumprida": "0a6m0d",
         "pena_remanescente": "1a6m0d", "data_geracao_rspe": "01/10/2026", "data_base_seeu": "", "_crimes": crimes,
         "_incidentes": [], "_eventos": list(eventos), "data_nascimento": "01/01/1980", "status_execucao": "ATIVO", "processo_execucao": PEXEC}
    r.update(kw)
    return r


def inc(tipo, comp, dec, ref=None, sit="CONCEDIDO"):
    return {"tipo": tipo, "complemento": comp, "data_decisao": dec, "data_referencia": ref or dec, "situacao": sit}


def R(*rem, eventos=None, **kw):
    r = {"processo_execucao": PEXEC, "_crimes": [],
         "_eventos": eventos or [{"data": "01/01/2020", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}],
         "_incidentes": [inc("REMIÇÃO", "%s Dia(s)" % d, dec, ref) for d, dec, ref in rem]}
    r.update(kw)
    return r


def F(trabalho=(), atestados=(), eventos=(), **kw):
    f = {"data_impressao": "05.10.2026", "trabalho": list(trabalho), "atestados": list(atestados),
         "eventos": [{"data": d, "texto": t} for d, t in eventos], "leituras": [], "exames": [], "cursos_peticionados": [],
         "certidoes_estudo": [], "estudos": [], "faltas": []}
    f.update(kw)
    return f


def A(num, data, ini="", fim="", rem=0, trab=0, empresa=""):
    return {"numero": num, "data": data, "periodo_inicio": ini, "periodo_fim": fim, "dias_remidos": rem, "dias_trabalhados": trab,
            "empresa": empresa, "autos": "", "trechos": []}


def comp(r, f):
    return rf.comparativo(r, f, HOJE)["fd_novo"]


PR, INT = "PRISÃO/INÍCIO DE CUMPRIMENTO", "INTERRUPÇÃO"

try:
    # ---- 1: "desligado da Escola" encerra a matrícula (sem nova matrícula, não há estudo depois) ----
    evs = [{"data": "18.03.2025", "texto": "Nesta data o interno iniciou no setor Escolar."},
           {"data": "20.03.2025", "texto": "Nesta data o interno foi desligado da Escola pelo motivo de problemas de visão, a próprio pedido."}]
    E1 = rf._estudos([dict(e, d=rf._dp(e["data"])) for e in evs])
    ok(len(E1) == 1 and E1[0]["fim"] == "20.03.2025" and E1[0]["motivo_fim"] == "desligado da escola", "1: desligamento não encerrou: %s" % E1)

    # ---- 2: ENEM acima do teto (100 dias) não é "possivelmente remido"; o atestado do mesmo dia, de valor próximo, explica ----
    f2 = F([], [A("193/2026", "07.07.2026", rem=131)], exames=[{"exame": "ENEM 2025", "data": "21.02.2026", "certificado": False, "ano": 2025, "autos": ""}])
    N2 = comp(R((138, "07/07/2026", None)), f2)
    d_at = next(d for d in N2["docs"] if d["num"] == "193/2026")
    d_ex = next(d for d in N2["docs"] if d["tipo"] == "Exame")
    ok(d_at["sit"].startswith("Provavelmente remido em 07/07/2026 (valor próximo: 138 dias no RSPE, 131 no documento)"), "2: atestado: %s" % d_at["sit"])
    ok(not d_ex.get("provavel_ex"), "2: ENEM ligado à remição de 138 (acima de 100): %s" % d_ex.get("provavel_ex"))
    # sem o atestado, a remição de 138 também não serve ao ENEM (teto de 100); a de 60, sim
    N2b = comp(R((138, "07/07/2026", None)), F([], [], exames=f2["exames"]))
    ok(not next(d for d in N2b["docs"] if d["tipo"] == "Exame").get("provavel_ex"), "2b: ENEM com 138 dias")
    N2c = comp(R((60, "07/07/2026", None)), F([], [], exames=f2["exames"]))
    ok(next(d for d in N2c["docs"] if d["tipo"] == "Exame").get("provavel_ex"), "2c: ENEM com 60 dias deixou de ser ligado")

    # ---- 3: duas certidões semestrais peticionadas e uma só remição: provável pendência (amarelo), não "nada a requerer" ----
    est3 = [{"curso": "SETOR ESCOLAR", "turma": "", "turno": "", "inicio": "22.08.2025", "fim": "", "motivo_fim": "", "horas": None}]
    cert3 = [{"data": "05.03.2026", "semestre": 2, "ano": 2025, "horas": None, "texto": "PETICIONADO CERTIDÃO DE FREQUÊNCIA ESCOLAR 2º SEMESTRE DE 2025", "autos": ""},
             {"data": "20.08.2026", "semestre": 1, "ano": 2026, "horas": None, "texto": "PETICIONADO CERTIDÃO DE FREQUÊNCIA ESCOLAR 1º SEMESTRE DE 2026", "autos": ""}]
    N3 = comp(R((33, "31/08/2026", None)), F([], [], estudos=est3, certidoes_estudo=cert3))
    p3 = [p for p in N3["pontos"] if p["tipo"] == "pend_cert"]
    ok(p3 and p3[0]["cor"] == "amarelo" and "uma só remição de 33 dias" in p3[0]["texto"], "3: sem a provável pendência: %s" % [p["texto"][:120] for p in N3["pontos"]])
    ok(N3["concl_cor"] == "amarelo" and "Nada a requerer" not in N3["concl"], "3: conclusão: %s" % N3["concl"])

    # ---- 4: a ficha cita o número do próprio RSPE: sem aviso de "RSPE de outra execução", ainda que de outro tribunal ----
    r4 = R(tribunal="TJGO", vara="VARA DE EXECUÇÃO PENAL", processo_execucao="7000001-11.2024.8.09.0001")
    ok(rrm.outra_execucao(r4, {"autos": ["7000001-11.2024.8.09.0001"]}) == "", "4: aviso com o número do próprio RSPE")
    ok(rrm.outra_execucao(r4, {"autos": []}).startswith("RSPE de outra execução?"), "4b: aviso do outro tribunal sumiu")

    # ---- 5: primeiro atestado da ficha, sem período nem setor, com os dias corridos do único trabalho até a emissão: sugerido ----
    f5 = F([{"setor": "BIBLIOTECA", "inicio": "21.11.2016", "fim": "01.04.2022", "externo": False}], [A("024/2021", "23.02.2021", rem=518, trab=1554)])
    L5 = rrm.trabalho_x_atestados(f5, HOJE, None, None, date(2015, 1, 1))["linhas"]
    ok(any(x["st"] == "provavel" and x["at"] == "024/2021" and x["periodo"].startswith("21/11/2016 a 23/02/2021") for x in L5),
       "5: atestado sem período não cobriu o trabalho: %s" % [(x["periodo"], x["st"], x["at"]) for x in L5])

    # ---- 6: data-base na recaptura depois de "descumprimento das condições", sem falta homologada (só a regressão cautelar) ----
    c6 = crime(pena_imposta="6 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="30/08/2023", transito_mp="10/07/2024", transito_processo="10/07/2024",
               fracao_progressao="40% - Art.112, V, da LEP")
    r6 = reg([c6], [ev(PR, "PRISÃO EM FLAGRANTE", "30/08/2023"), ev(PR, "INÍCIO DO CUMPRIMENTO REGIME SEMIABERTO", "12/06/2025"),
                    ev(INT, "DESCUMPRIMENTO DAS CONDIÇÕES", "22/02/2026"), ev(PR, "RECAPTURA/REINÍCIO DE CUMPRIMENTO", "22/09/2026")],
             pena_total="6a0m0d", data_base_seeu="22/09/2026", data_base_motivo="RECAPTURA/REINÍCIO DE CUMPRIMENTO",
             _incidentes=[inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Semiaberto - Progressão de Regime", "02/06/2025", "12/06/2025"),
                          inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Fechado - Regressão Cautelar", "16/09/2026")])
    A6 = ra.auditar(copy.deepcopy(r6), HOJE)["aud_itens"]
    i6 = [i for i in A6 if i.get("tipo") == "data-base-movida-para-a-recaptura-sem-falta-homo"]
    ok(i6 and i6[0]["nivel"] == "verificar" and "descumprimento das condições" in i6[0]["detalhe"], "6: sem o 'verificar': %s" % [i["titulo"] for i in A6])
    # com a falta homologada, nada a verificar
    r6b = copy.deepcopy(r6)
    r6b["_incidentes"].append(inc("HOMOLOGAÇÃO DE FALTA GRAVE", "22/02/2026", "30/09/2026", "22/02/2026"))
    ok(not [i for i in ra.auditar(r6b, HOJE)["aud_itens"] if i.get("tipo") == "data-base-movida-para-a-recaptura-sem-falta-homo"],
       "6b: verificar com a falta homologada")

    # ---- 7: regressão decidida com a homologação da fuga: não é falta a preencher; na fuga, a data-base é a recaptura ----
    r7 = reg([c6], [ev(PR, "PRISÃO DEFINITIVA", "18/11/2021"), ev(INT, "FUGA", "31/12/2023"), ev(PR, "RECAPTURA/REINÍCIO DE CUMPRIMENTO", "26/05/2024")],
             pena_total="6a0m0d", data_base_seeu="26/05/2024",
             _incidentes=[inc("HOMOLOGAÇÃO DE FALTA GRAVE", "31/12/2023", "29/01/2025", "31/12/2023"),
                          inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Fechado - Regressão", "29/01/2025")])
    A7 = ra.auditar(copy.deepcopy(r7), HOJE)["aud_itens"]
    ok(not any("sanção que pressupõe falta grave" in i["titulo"] for i in A7), "7: regressão da mesma decisão como falta a preencher")
    i7 = [i for i in A7 if i.get("tipo") == "regressao-registrada-em"]
    ok(i7 and "recaptura (26/05/2024)" in i7[0]["detalhe"] and "a data-base da progressão é a data da falta" not in i7[0]["detalhe"],
       "7: regressão: %s" % (i7[0]["detalhe"] if i7 else None))

    # ---- 8: número truncado na ficha conta como processo à parte; pena acima do máximo do dispositivo cadastrado ----
    r8 = reg([crime()])
    it8 = rf._processos_x_ficha(r8, {"autos": [], "autos_incompletos": ["0000219-84.2025.8.12.001"]})
    ok(it8 and "número incompleto" in it8[0]["detalhe"], "8: número truncado: %s" % it8)
    ok(not rf._processos_x_ficha(r8, {"autos": [], "autos_incompletos": [P1[:-1]]}), "8b: truncado do próprio processo do RSPE contado")
    c8 = crime(artigo="ART 129: Lesão corporal", tipo_penal="CAPUT: Lesão corporal, Detenção: 3 meses a 1 ano Sem Multa",
               pena_imposta="2 ano(s), 9 mês(es) e 0 dia(s)", vga="S")
    A8 = ra.auditar(reg([c8], [ev(PR, "PRISÃO EM FLAGRANTE", "25/01/2021")], pena_total="2a9m0d"), HOJE)["aud_itens"]
    ok(any(i.get("tipo") == "pena-acima-do-maximo-do-dispositivo" and i["nivel"] == "verificar" for i in A8), "8c: pena acima do máximo")
    A8b = ra.auditar(reg([dict(c8, pena_imposta="1 ano(s), 2 mês(es) e 0 dia(s)")], [ev(PR, "PRISÃO EM FLAGRANTE", "25/01/2021")], pena_total="1a2m0d"), HOJE)["aud_itens"]
    ok(not any(i.get("tipo") == "pena-acima-do-maximo-do-dispositivo" for i in A8b), "8d: aumento comum apontado")

    # ---- 9: encaminhamento à Disciplinar (celular) é falta a apurar ----
    f9 = rf.derivar({"data_impressao": "05/10/2026", "eventos": [{"data": "01.01.2026", "texto": "Nesta data o interno foi encaminhado para a "
                     "Disciplinar conforme CI 001/26/SDV, foto em celular apreendido."}]},
                    [{"data": "01.01.2026", "texto": "Nesta data o interno foi encaminhado para a Disciplinar conforme CI 001/26/SDV, foto em "
                      "celular apreendido.", "d": date(2026, 1, 1)}])
    ok(len(f9["faltas"]) == 1 and f9["faltas"][0]["grave"] and "50, VII" in f9["faltas"][0]["artigo"], "9: encaminhamento: %s" % f9["faltas"])

    # ---- 10: livramento de 1/2 em contravenção: 1/3 (CP, art. 83, II, exige reincidência em crime doloso) ----
    c10 = crime(lei="3688/41 - Lei das Contravenções Penais", artigo="ART 21: Vias de fato", tipo_penal="CAPUT: Praticar vias de fato, Prisão Simples: 15 dias a 3 meses",
                pena_imposta="0 ano(s), 0 mês(es) e 16 dia(s)", reincidente_comum="S", fracao_livramento="1/2 - Comum Reincidente",
                fracao_progressao="16,67% - Comum")
    A10 = ra.auditar(reg([c10], [ev(PR, "PRISÃO EM FLAGRANTE", "02/09/2020")], pena_total="0a0m16d"), HOJE)["aud_itens"]
    i10 = [i for i in A10 if i.get("tipo") == "livramento-contravencao-fracao"]
    ok(i10 and "1/3" in i10[0]["titulo"], "10: contravenção: %s" % [i["titulo"] for i in A10])
    ok(not any(i.get("tipo") == "fracao-livramento-reincidencia-a-conferir" for i in A10), "10b: texto de 'a do SEEU' na contravenção")

    # ---- 11: interrupção por "descumprimento das condições" com evasão na ficha: prazo pelo saldo (art. 113) ----
    c11 = crime(pena_imposta="7 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="09/09/2017", transito_mp="03/09/2018", transito_processo="03/09/2018")
    r11 = reg([c11], [ev(PR, "PRISÃO DEFINITIVA", "05/02/2021"), ev(INT, "DESCUMPRIMENTO DAS CONDIÇÕES", "22/09/2023"),
                      ev(PR, "RECAPTURA/REINÍCIO DE CUMPRIMENTO", "30/11/2023")], pena_total="7a0m0d")
    fic11 = {"eventos": [{"data": "25.09.2023", "texto": "Saída da Unidade Penal: ESTABELECIMENTO PENAL SEMIABERTO, Destino: DESTINO NAO DEFINIDO, Motivo: Evasão"}]}
    L11 = rp.analisar(copy.deepcopy(r11), HOJE, ficha=fic11)["presc_linhas"][0]
    ok("Evasão em 22/09/2023" in (L11.get("ppe_detalhe") or "") and "registra evasão em 25/09/2023" in L11["ppe_detalhe"],
       "11: evasão da ficha: %s" % (L11.get("ppe_detalhe") or "")[-600:])
    L11b = rp.analisar(copy.deepcopy(r11), HOJE)["presc_linhas"][0]
    ok("Interrupção sem evasão de 22/09/2023" in (L11b.get("ppe_detalhe") or ""), "11b: sem a ficha, continua sem evasão")

    # ---- 12: art. 28 sem pena: a custódia pelas outras condenações suspende o prazo, não o interrompe ----
    c12 = crime(processo_criminal=P2, lei="11343/06 - Lei de Drogas", artigo="ART 28: Posse de drogas para consumo", tipo_penal="CAPUT: Quem adquirir",
                pena_imposta="0 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="05/10/2017", transito_mp="18/04/2018", transito_processo="11/05/2018",
                data_denuncia="18/04/2018", data_sentenca="18/04/2018")
    r12 = reg([c11, c12], [ev(PR, "PRISÃO DEFINITIVA", "10/06/2019", P1 + ", " + P2)], pena_total="7a0m0d")
    L12 = [L for L in rp.analisar(copy.deepcopy(r12), HOJE)["presc_linhas"] if L.get("proc_crim") == P2][0]
    ok("interrupção" not in L12["ppe_status"].lower() and "interrompido em" not in L12["ppe_status"] and "preso" in L12["ppe_status"],
       "12: art. 28 interrompido pela custódia: %s" % L12["ppe_status"])

    # ---- 13: homicídio qualificado (fato anterior à Lei 13.964/2019) sem a marcação de morte: não é "sem hediondo com resultado morte" ----
    c13 = crime(artigo="ART 121: Homicídio qualificado", tipo_penal="§ 2º: Se o homicídio é cometido: I - mediante paga", hediondo_ou_equiparado="S",
                pena_imposta="12 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="02/09/2019", vga="N")
    st13 = rv.saida_temporaria(reg([c13], regime_atual="Semiaberto - ATIVO", pena_total="12a0m0d", pena_cumprida="4a0m0d"), {}, {}, hoje=HOJE)
    t13 = [x["txt"] for x in (st13.get("st_itens") if isinstance(st13, dict) else st13)]
    ok(any("se consumado" in t and "não se aplica" in t for t in t13) and not any(t.startswith("Sem hediondo com resultado morte") for t in t13),
       "13: saída temporária: %s" % t13)
except Exception:
    import traceback
    falhas.append(traceback.format_exc())

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for x in falhas:
        print(" -", x)
    sys.exit(1)
print("teste_conf8_demais: OK")
