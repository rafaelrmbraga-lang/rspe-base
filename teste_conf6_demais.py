"""Conferência independente da 7.14.4 (rodada 7.14.5), frente livramento, extinção, auditoria, prescrição e progressão: reincidência
específica pela lei no tráfico (livramento vedado) e fração de livramento do SEEU acima da legal refletidas na aba do livramento;
falta a apurar cujos 12 meses passam da data do SEEU; livramento que só alcançava pena já extinta (sem Súmula 617); remição decidida
com o livramento abatida do período de prova; textos de alteração de data-base e de interrupção que não é fuga; blocos de detração sem a
guia suspensa; forma favorável com ano de 365 dias; número da execução com o segmento do tribunal trocado; trânsito com data impossível;
dias de suspensão contados como na data-limite; aviso de livramento só com livramento concedido; +1/3 afastado com fração de primário
no SEEU; setor com baixa fora do trabalho atual; isolamento preventivo com PADIC como falta a apurar.
Casos hipotéticos, nomes fictícios. Rodar: python teste_conf6_demais.py"""
import copy
import sys
import types
from datetime import date, timedelta
from fractions import Fraction

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_auditoria as ra
import rspe_ficha as rf
import rspe_prescricao as rp
import rspe_scraper as rs
import rspe_view as rv

falhas = []
HOJE = date(2026, 10, 22)
rv.HOJE = HOJE


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


PR = "PRISÃO/INÍCIO DE CUMPRIMENTO"
P1, P2, P3 = "0000001-11.2024.8.12.0001", "0000002-22.2026.8.12.0001", "0000003-33.2025.8.12.0001"
TRAF = dict(lei="11343/06 - Lei de Drogas", artigo="ART 33: Tráfico de drogas", tipo_penal="CAPUT: Importar, exportar, remeter",
            fracao_progressao="40% - Art.112, V, da LEP", fracao_livramento="2/3 - Hediondo")


def inc(tipo, compl, dec, ref, sit="CONCEDIDO", processos=""):
    return {"tipo": tipo, "motivo": "", "complemento": compl, "data": "", "data_decisao": dec, "data_referencia": ref,
            "processos": processos, "situacao": sit}


def ev(tipo, motivo, data, processos=P1):
    return {"tipo": tipo, "motivo": motivo, "complemento": "", "data": data, "data_decisao": "", "data_referencia": "", "processos": processos}


def crime(**kw):
    c = {"processo_criminal": P1, "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto", "tipo_penal": "CAPUT: Subtrair",
         "pena_imposta": "2 ano(s), 0 mês(es) e 0 dia(s)", "data_infracao": "10/01/2021", "data_sentenca": "10/06/2021",
         "transito_mp": "10/07/2021", "transito_processo": "10/07/2021", "extinto": "Não", "suspenso": "Não", "vga": "N",
         "resultado_morte": "N", "reincidente_comum": "N", "reincidente_especifico": "N", "comando_orcrim": "N",
         "fracao_progressao": "1/6 - Comum", "fracao_livramento": "1/3 - Comum", "regime_sentenca": "Fechado"}
    c.update(kw)
    return c


def reg(crimes, incs=(), eventos=(), **kw):
    r = {"nome": "Teste Ficticio", "regime_atual": "Fechado - ATIVO", "pena_total": "2a0m0d", "pena_cumprida": "0a6m0d",
         "pena_remanescente": "1a6m0d", "data_geracao_rspe": "06/10/2026", "data_base_seeu": "", "_crimes": crimes,
         "_incidentes": list(incs), "_eventos": list(eventos), "data_nascimento": "01/01/1980", "status_execucao": "ATIVO",
         "processo_execucao": "0000009-99.2024.8.12.0001"}
    r.update(kw)
    return r


def modelo(r, ficha=None):
    return rv.modelo(copy.deepcopy(r), {}, ficha, [])


try:
    # ---- 1) tráfico cometido depois do trânsito de outro tráfico, sem a marcação do SEEU: reincidente específico pela lei -
    # livramento vedado quanto a esse crime; a aba do livramento avisa que a data do SEEU não se sustenta ----
    r = reg([crime(**TRAF, processo_criminal=P1, pena_imposta="5 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="13/07/2024",
                   data_sentenca="10/03/2025", transito_mp="08/08/2025", transito_processo="08/08/2025"),
             crime(**TRAF, processo_criminal=P2, pena_imposta="5 ano(s), 6 mês(es) e 0 dia(s)", data_infracao="23/01/2026",
                   data_sentenca="10/06/2026", transito_mp="", transito_processo="")],
            eventos=[ev(PR, "PRISÃO PREVENTIVA", "23/01/2026", P2)], pena_total="10a6m0d", pena_cumprida="0a9m0d",
            pena_remanescente="9a9m0d", livramento_previsao_seeu="13/06/2031", progressao_previsao_seeu="13/06/2029",
            data_base_seeu="23/01/2026")
    m = modelo(r)
    it = [i for i in m["aud_itens"] if i.get("tipo") == "reincidente-pela-lei-sem-marcacao" and P2 in (i.get("ref") or "")]
    ok(it and it[0]["nivel"] == "verificar" and "livramento vedado" in it[0].get("efeito", ""), "1: item da reincidência específica: %s" % it)
    ok("livramento vedado quanto a esse crime" in m["liv_sit"] and "11.343" in m["liv_sit"] and m["liv_cor"] == "amarelo",
       "1: aba do livramento: %s / %s" % (m["liv_sit"], m["liv_cor"]))
    # anterior por crime fora da Lei de Drogas (furto): no tráfico, não veda o livramento
    r2 = copy.deepcopy(r)
    r2["_crimes"][0].update(lei="2848/40 - Código Penal", artigo="ART 155: Furto", tipo_penal="CAPUT: Subtrair",
                            fracao_progressao="16% - Art.112, I, da LEP", fracao_livramento="1/3 - Comum Primário")
    m2 = modelo(r2)
    ok("livramento vedado" not in (m2["liv_sit"] or "") + (m2["liv_sit_full"] or ""), "1: anterior por furto não veda: %s" % m2["liv_sit"])

    # ---- 2) art. 16 da Lei 10.826 (uso restrito) tratado como hediondo: a fração legal (1/3) e a data por ela na aba ----
    ART16 = dict(lei="10826/03 - Estatuto do Desarmamento", artigo="ART 16 - Posse ou porte ilegal de arma de fogo de uso restrito",
                 tipo_penal="CAPUT: (Após 26.10.2017 - Lei n. 13497/2017) Possuir, deter, portar",
                 fracao_progressao="40% - Art.112, V, da LEP", fracao_livramento="2/3 - Hediondo")
    r = reg([crime(**TRAF, processo_criminal=P3, pena_imposta="6 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="01/10/2025",
                   data_sentenca="10/05/2026", transito_mp="", transito_processo=""),
             crime(**ART16, processo_criminal=P3, pena_imposta="3 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="01/10/2025",
                   data_sentenca="10/05/2026", transito_mp="", transito_processo="")],
            eventos=[ev(PR, "PRISÃO EM FLAGRANTE", "01/10/2025", P3)], pena_total="9a0m0d", pena_cumprida="1a0m6d",
            pena_remanescente="7a11m24d", livramento_previsao_seeu="30/09/2031", progressao_previsao_seeu="05/05/2029",
            data_base_seeu="01/10/2025", seeu_fracoes_livramento=["Hediondo (2/3): 6a0m0d"])
    m = modelo(r)
    ok(m["frac_liv"].startswith("1/3 e 2/3 (cada fração sobre a pena do seu crime)") and "SEEU: 2/3" in m["frac_liv"],
       "2: fração legal na coluna: %s" % m["frac_liv"])
    ok("30/09/2030" in m["liv_sit"] and "acima da legal" in m["liv_sit"] and m["liv_cor"] == "amarelo" and m["liv"] == "30/09/2031",
       "2: data pela fração legal, a do SEEU mantida: %s / %s" % (m["liv"], m["liv_sit"]))

    # ---- 3) fuga sem PAD com recaptura: 12 meses da recaptura depois da data do SEEU - a verificar, com a data se reconhecida ----
    lf = rs.falta_livramento
    rs.falta_livramento = lambda r_, d_, h_: ("apurar_depois", date(2027, 8, 15), "INTERRUPÇÃO FUGA (27/09/2025; recaptura em 15/08/2026)")
    try:
        r = reg([crime(pena_imposta="6 ano(s), 0 mês(es) e 0 dia(s)", fracao_livramento="1/2 - Comum Reincidente")],
                eventos=[ev(PR, "PRISÃO EM FLAGRANTE", "01/02/2023")], pena_total="6a0m0d", livramento_previsao_seeu="02/04/2027")
        m = modelo(r)
    finally:
        rs.falta_livramento = lf
    ok(m["liv_cor"] == "amarelo" and "15/08/2027" in m["liv_sit"] and "Súmula 533" in m["liv_sit"] and m["liv"] == "02/04/2027",
       "3: falta a apurar depois da data do SEEU: %s / %s" % (m["liv_sit"], m["liv_cor"]))

    # ---- 4) extinção: livramento que alcançava só a pena já extinta - sem a hipótese da Súmula 617 ----
    r = {"_crimes": [crime(data_infracao="24/05/2017", data_sentenca="10/06/2018", extinto="Sim"),
                     crime(processo_criminal=P3, data_infracao="29/09/2020", data_sentenca="10/06/2022")]}
    ok(rv._livramento_so_penas_extintas(r, date(2019, 9, 9)), "4: livramento só da pena extinta")
    r["_crimes"][0]["extinto"] = "Não"
    ok(not rv._livramento_so_penas_extintas(r, date(2019, 9, 9)), "4: pena do livramento ativa")
    # remição datada depois do início do livramento, mas decidida até a decisão que o deferiu: abate o período de prova
    lcs = [inc("LIVRAMENTO CONDICIONAL", "20/01/2016", "11/01/2017", "20/01/2016")]
    ok(rv._rem_ate_decisao_lc([(date(2015, 9, 8), 120), (date(2017, 1, 11), 102), (date(2025, 2, 17), 94)], date(2016, 1, 20), lcs) == 102,
       "4: remição decidida com o livramento")

    # ---- 5) textos: alteração de data-base não é alteração de regime; interrupção genérica não é fuga ----
    duv = rs.duvidas_livramento({}, [], [inc("ALTERAÇÃO DE DATA-BASE DE PROGRESSÃO DE REGIME/LIVRAMENTO CONDICIONAL", "Progressão de Regime",
                                             "28/11/2022", "21/10/2022")], date(2016, 1, 20))
    ok(any("alteração de data-base em 21/10/2022" in d for d in duv) and not any("alteração de regime em 21/10/2022" in d for d in duv),
       "5: data-base: %s" % duv)
    ok(rp._evento_interrupcao("INTERRUPÇÃO DO CUMPRIMENTO DA PENA") == "interrupção" and rp._evento_interrupcao("FUGA") == "fuga"
       and rp._evento_interrupcao("ABANDONO DO REGIME") == "abandono do regime", "5: evento da interrupção")

    # ---- 6) Auditoria: forma favorável com ano de 365 dias (6 anos x 40% = 2a4m24d; menos 417 dias = 1a3m2d; diferença 8m7d) ----
    t = ra._texto_blocos([[Fraction(2, 5), 2190, 699, 417, [1, 11, 9], [6, 0, 0]]])
    ok("1 ano, 3 meses e 2 dias" in t and "Diferença: 8 meses e 7 dias" in t, "6: forma favorável: %s" % t[-300:])

    # ---- 7) guia "Suspenso: Sim" fora do total: não entra no bloco - sem detração inventada (data-base = a única prisão) ----
    FR16 = "16% - Art.112, I, da LEP"
    r = reg([crime(processo_criminal=P1, tipo_penal="§ 4º: A pena é de reclusão", data_infracao="01/04/2021", data_sentenca="28/06/2025",
                   transito_mp="26/06/2026", transito_processo="26/06/2026", suspenso="Sim", fracao_progressao=FR16),
             crime(processo_criminal=P3, artigo="ART 211: Ocultação de cadáver", pena_imposta="1 ano(s), 0 mês(es) e 0 dia(s)",
                   data_infracao="07/10/2021", data_sentenca="18/03/2024", transito_mp="31/05/2023", transito_processo="31/05/2023",
                   fracao_progressao=FR16),
             crime(processo_criminal=P3, artigo="ART 347: Fraude processual", pena_imposta="0 ano(s), 6 mês(es) e 0 dia(s)",
                   data_infracao="07/10/2021", data_sentenca="18/03/2024", transito_mp="31/05/2023", transito_processo="31/05/2023",
                   fracao_progressao=FR16),
             crime(processo_criminal=P3, artigo="ART 121: Matar alguem:", tipo_penal="§ 2º: Se o homicídio é cometido",
                   pena_imposta="16 ano(s), 6 mês(es) e 0 dia(s)", data_infracao="07/10/2021", data_sentenca="18/03/2024",
                   transito_mp="31/05/2023", transito_processo="31/05/2023", fracao_progressao="50% - Art.112, VI, da LEP",
                   resultado_morte="S", fracao_livramento="1/1 - Hediondo")],
            [inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Fechado - Regime Inicial", "", "15/10/2021")],
            [ev(PR, "PRISÃO PROVISÓRIA", "15/10/2021", P3)], pena_total="18a0m0d", pena_cumprida="5a0m0d",
            pena_remanescente="13a0m0d", data_base_seeu="15/10/2021", progressao_previsao_seeu="08/02/2030",
            seeu_fracoes_progressao=["Primário sem violência ou grave ameaça (16%): 0a2m26d",
                                     "Hediondo primário com resultado morte (50%): 8a3m0d"])
    its = ra.auditar(copy.deepcopy(r), HOJE)["aud_itens"]
    ok(not any("detração descontada antes da fração" in (i.get("titulo") or "") and i["nivel"] == "alerta" for i in its),
       "7: sem alerta de detração com a guia suspensa: %s" % [i["titulo"] for i in its if i["nivel"] == "alerta"])

    # ---- 8) número da própria execução com o segmento do tribunal trocado na ficha: provável digitação, não processo novo ----
    r = reg([crime()], processo_execucao="6006744-90.2023.8.12.0001")
    o = rf._processos_x_ficha(r, {"autos": ["Petição 6006744-90.2023.8.23.0001", "0000590-89.2013.8.12.0008"]})
    txt = " ".join(i.get("titulo", "") + " " + i.get("detalhe", "") for i in o)
    ok("não lista: 1" in txt and "segmento do tribunal" in txt, "8: segmento do tribunal: %s" % txt[:300])
    # número válido de outro tribunal (DV confere): continua processo não listado
    o = rf._processos_x_ficha(r, {"autos": ["0000590-89.2013.8.12.0008"]})
    ok(any("não lista: 1" in i.get("titulo", "") for i in o), "8: outro processo válido")

    # ---- 9) prescrição: "o resultado não muda" só quando as duas hipóteses concluem; ambas a verificar, a data muda ----
    La = {"ppe_status": "A VERIFICAR: prescrição aparente", "ppe_resumo": "... venceu em 08/02/2021."}
    Lb = {"ppe_status": "A VERIFICAR: prescrição aparente", "ppe_resumo": "... venceu em 09/10/2021."}
    ok("09/10/2021" in rp._nao_muda(La, Lb) and "segue a verificar" in rp._nao_muda(La, Lb), "9: hipótese a verificar")
    ok(rp._nao_muda({"ppe_status": "Não prescrita"}, {"ppe_status": "Não prescrita"}) == "o resultado não muda", "9: conclusão igual")
    ok(rp._dias_susp(date(2019, 6, 9), date(2019, 8, 8), date(2018, 12, 10), date(2019, 8, 8)) == 61, "9: 61 dias de 09/06 a 08/08")

    # ---- 10) prescrição: uma condenação só, marcada reincidente sem base, com fração de primário no SEEU: sem o +1/3 ----
    r = reg([crime(artigo="ART 213: Estupro", tipo_penal="§ 1º: Se da conduta resulta", pena_imposta="12 ano(s), 0 mês(es) e 0 dia(s)",
                   data_infracao="09/12/2012", data_sentenca="13/04/2022", transito_mp="14/02/2023", transito_processo="14/02/2023",
                   reincidente_comum="S", fracao_progressao="2/5 - Hediondo Primario", fracao_livramento="2/3 - Hediondo")],
            eventos=[ev(PR, "PRISÃO DEFINITIVA", "20/02/2023")], pena_total="12a0m0d", reincidente="S")
    _A = rp.analisar(copy.deepcopy(r), HOJE)
    L = (_A.get("linhas") or _A.get("presc_linhas"))[0]
    ok(not L["reinc"] and "+1/3" not in (L.get("prazo_ppe") or "") and "fração de primário" in (L.get("ppe_reinc_aviso") or ""),
       "10: +1/3 afastado: %s | %s" % (L.get("prazo_ppe"), (L.get("ppe_reinc_aviso") or "")[:200]))

    # ---- 11) progressão: setor com baixa posterior sai do "trabalho atual" ----
    t = {"inicio": "04.05.2023", "fim": "", "setor": "FABRICA / EMPRESA TESTE", "setores": ["FABRICA", "EMPRESA TESTE"]}
    evs = [{"data": "18.06.2026", "texto": "Trabalho: Deixa de trabalhar, no setor de trabalho FABRICA, conforme adequação do mapa"}]
    ok(rf._sem_setores_baixados(t, evs)["setor"] == "EMPRESA TESTE", "11: setor baixado")
    ok(rf._sem_setores_baixados(t, [])["setor"] == "FABRICA / EMPRESA TESTE", "11: sem baixa")

    # ---- 12) isolamento preventivo com PADIC, sem a natureza da falta: falta a apurar (incidente pendente vindo da ficha) ----
    ficha = {"faltas": [{"data_registro": "24.11.2025", "data_fato": "24.11.2025", "artigo": "", "grave": False, "grave_indicio": True,
                         "texto": "CONSELHO DISCIPLINAR: ISOLADO PREVENTIVAMENTE EM CELA DISCIPLINAR - RESPONDE PADIC/XX.",
                         "padic": "", "resultado": "", "situacao": "PADIC instaurado"}], "eventos": []}
    r = reg([crime()], eventos=[ev(PR, "PRISÃO EM FLAGRANTE", "01/02/2021")])
    rs.faltas_da_ficha(r, ficha, HOJE)
    ok(any(i.get("_ficha") and "isolamento preventivo com PADIC" in i.get("complemento", "") for i in r["_incidentes"]),
       "12: falta a apurar da ficha: %s" % r["_incidentes"])
    ficha["faltas"][0]["grave_indicio"] = False
    rs.faltas_da_ficha(r, ficha, HOJE)
    ok(not any(i.get("_ficha") for i in r["_incidentes"]), "12: sem o indício, não entra")
except Exception:
    import traceback
    traceback.print_exc()
    falhas.append("exceção")

if falhas:
    print("FALHAS:\n- " + "\n- ".join(falhas))
    sys.exit(1)
print("ok - teste_conf6_demais")
