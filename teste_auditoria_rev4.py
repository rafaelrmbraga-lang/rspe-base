"""Teste de regressão das correções da 3ª e da 4ª revisão da Auditoria (progressão, livramento, data-base) e da revisão da leitura
do RSPE (alteração de data-base não é progressão nem regime; data-base derivada só de incidente concedido).
3ª revisão (A1-A15): alteração de data-base lida como progressão, guia nova de quem já estava preso, regressão e progressão da
ficha, regime inicial sem efeito (aberto; falta posterior à progressão), caixa da data-base, falta prescrita, alteração na data da
progressão, itens de data-base no aberto, soma favorável, capitulação, majorante, reinício pela "Data Prisão" da ficha, texto da
reincidência e prescrição da falta na sanção.
4ª revisão (A1-A13): data-base do livramento, reincidência específica da progressão, "hediondo até 24/07/1990", dano qualificado,
prisão de processo extinto, limite do art. 75, fração ponderada, max() da view, texto da recaptura, rótulo do dispositivo, datas
de vigência da base, citações e livramento concedido antes.
Rodar: python teste_auditoria_rev4.py"""
import sys
import types
from datetime import date, timedelta

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_auditoria as ra
import rspe_ficha as rf
import rspe_regras as rg
import rspe_scraper as rs
import rspe_view as rv

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


AR = "FIXAÇÃO/ALTERAÇÃO DE REGIME"
DB = "ALTERAÇÃO DE DATA-BASE DE PROGRESSÃO DE REGIME/LIVRAMENTO CONDICIONAL"
PR = "PRISÃO/INÍCIO DE CUMPRIMENTO"


def inc(tipo, compl, dec, ref, sit="CONCEDIDO", procs=""):
    return {"tipo": tipo, "motivo": "", "complemento": compl, "data": "", "data_decisao": dec, "data_referencia": ref, "processos": procs, "situacao": sit}


def ev(tipo, motivo, data, procs="0000001-11.2020.8.12.0001"):
    return {"tipo": tipo, "motivo": motivo, "data": data, "processos": procs}


def crime(**kw):
    c = {"processo_criminal": "0000001-11.2020.8.12.0001", "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto",
         "tipo_penal": "CAPUT: Subtrair, Reclusão: 1 a 4 anos", "pena_imposta": "10 ano(s), 0 mês(es) e 0 dia(s)",
         "data_infracao": "10/01/2016", "data_sentenca": "10/06/2016", "transito_mp": "10/07/2016", "transito_processo": "10/07/2016",
         "extinto": "Não", "suspenso": "Não", "vga": "N", "resultado_morte": "N", "reincidente_comum": "N", "reincidente_especifico": "N",
         "comando_orcrim": "N", "fracao_progressao": "1/6 - Comum", "fracao_livramento": "1/3 - Comum"}
    c.update(kw)
    return c


def reg(crimes, incs=(), eventos=(), **kw):
    r = {"nome": "Teste", "regime_atual": "Fechado - ATIVO", "pena_total": "10a0m0d", "pena_cumprida": "3a0m0d", "pena_remanescente": "7a0m0d",
         "fracao_progressao_aplicada": "1/6", "data_geracao_rspe": "01/10/2026", "data_base_seeu": "01/03/2024", "_crimes": crimes,
         "_incidentes": list(incs), "_eventos": list(eventos)}
    r.update(kw)
    return r


def itens(r):
    return ra.auditar(r, date(2026, 10, 1))["aud_itens"]


def por_tipo(r):
    out = {}
    for i in itens(r):
        out.setdefault(i["tipo"], []).append(i)
    return out


# ---------------- revisão da leitura (A5 e A6) ----------------
alt = inc(DB, "Progressão de Regime", "23/09/2019", "23/09/2019")
ok(not rs.e_incidente_regime(alt) and rs.e_alteracao_data_base(alt), "rspe A5: alteração de data-base tida como regime")
ok(rs._rotulo_incidente(alt) == "Alteração de data-base (Progressão de Regime)", "rspe A5: rótulo %s" % rs._rotulo_incidente(alt))
r = reg([crime()], [inc(AR, "Fechado - Regime Inicial", "", "01/02/2017"), alt,
                    inc(AR, "Semiaberto - Progressão de Regime", "28/09/2024", "28/09/2024", sit="NÃO CONCEDIDO"),
                    inc(AR, "Semiaberto - Progressão de Regime", "", "12/11/2026", sit="PENDENTE")],
        [ev(PR, "PRISÃO EM FLAGRANTE", "01/02/2017")])
rs.derivar(r, r["_crimes"], r["_eventos"], r["_incidentes"])
ok(r["progressoes_concedidas"] == 0 and not r["ultima_progressao"], "rspe A5: progressões %s / %s" % (r["progressoes_concedidas"], r["ultima_progressao"]))
ok(r["data_base"] == "23/09/2019", "rspe A6: data-base derivada %s (não usa negada/pendente)" % r["data_base"])
r2 = reg([crime()], [inc(AR, "Fechado - Regime Inicial", "", "01/02/2017"), inc(AR, "Fechado - Unificação", "26/01/2023", "26/01/2023")],
         data_base_seeu="")
ok(rs.situacao_execucao(r2, [], r2["_incidentes"], r2["_crimes"], date(2026, 10, 1))["data_base"] == "01/02/2017", "rspe A6: unificação na data-base derivada")
# a Auditoria não diz "o RSPE adota" com a data derivada
lc = inc("LIVRAMENTO CONDICIONAL", "01/02/2022", "01/02/2022", "01/02/2022")
r = reg([crime()], [inc(AR, "Fechado - Regime Inicial", "", "01/02/2017"), lc, inc(AR, "Fechado - Regressão Cautelar", "01/05/2023", "01/05/2023")],
        [ev(PR, "PRISÃO EM FLAGRANTE", "01/02/2017")], data_base_seeu="", data_base="01/05/2023")
ok(not any("o RSPE adota" in i["detalhe"] for i in itens(r)), "rspe A6: 'o RSPE adota' com data derivada")

# ---------------- 3ª revisão ----------------
# A1: alteração de data-base com complemento "Progressão de Regime" não é progressão lançada na data da decisão
r = reg([crime()], [inc(AR, "Fechado - Regime Inicial", "", "01/02/2017"), alt], [ev(PR, "PRISÃO EM FLAGRANTE", "01/02/2017")],
        data_base_seeu="23/09/2019")
t = por_tipo(r)
ok("progressao-com-data-base-igual-a-data-da-decisao" not in t and "progressao-na-decisao-superada" not in t, "A1: %s" % list(t))

# A2: início do cumprimento da guia nova com a pessoa já presa não é marco da data-base
cs = [crime(processo_criminal="0000745-96.2016.8.12.0005", data_infracao="08/11/2015"),
      crime(processo_criminal="0000336-52.2018.8.12.0005", data_infracao="03/08/2019")]
r = reg(cs, [inc(AR, "Semiaberto - Regime Inicial", "", "09/10/2021")],
        [ev(PR, "PRISÃO DEFINITIVA", "09/10/2021", "0000745-96.2016.8.12.0005"),
         ev(PR, "INÍCIO DO CUMPRIMENTO REGIME FECHADO", "08/04/2022", "0000745-96.2016.8.12.0005, 0000336-52.2018.8.12.0005")],
        data_base_seeu="08/04/2022", pena_total="20a0m0d")
t = por_tipo(r)
ok("data-base-confere-com-o-rspe" not in t and t.get("data-base-na-guia-nova-de-quem-ja-estava-preso", [{}])[0].get("nivel") == "alerta", "A2: %s" % list(t))
ok(ra.fundamentacao(t["data-base-na-guia-nova-de-quem-ja-estava-preso"][0], r), "A2: sem fundamentação")
# a alteração de data-base para a guia nova não tem fundamento (Odair)
cs2 = [crime(processo_criminal="0001401-65.2016.8.12.0001", data_infracao="26/09/2015"),
       crime(processo_criminal="0005907-55.2014.8.12.0001", data_infracao="01/05/2012")]
r = reg(cs2, [inc(AR, "Fechado - Regime Inicial", "", "03/07/2016"), inc(DB, "Progressão de Regime", "21/11/2017", "21/11/2017")],
        [ev(PR, "PRISÃO PREVENTIVA", "03/07/2016", "0001401-65.2016.8.12.0001"),
         ev(PR, "INÍCIO DO CUMPRIMENTO REGIME FECHADO", "20/11/2017", "0005907-55.2014.8.12.0001")], data_base_seeu="21/11/2017")
t = por_tipo(r)
ok("data-base-confere-com-o-rspe" not in t and "alteracao-de-data-base-sem-falta-homologada" in t
   and "guia da condenação nova" in t["alteracao-de-data-base-sem-falta-homologada"][0]["detalhe"], "A2 (alteração): %s" % list(t))
# a prisão em flagrante de quem estava no semiaberto é prisão nova (marco legítimo)
r = reg([crime()], [inc(AR, "Fechado - Regime Inicial", "", "01/02/2017"), inc(AR, "Semiaberto - Progressão de Regime", "01/02/2019", "01/02/2019")],
        [ev(PR, "PRISÃO EM FLAGRANTE", "01/02/2017"), ev(PR, "PRISÃO EM FLAGRANTE", "16/12/2022")], data_base_seeu="16/12/2022")
ok("data-base-confere-com-o-rspe" in por_tipo(r), "A2: flagrante no semiaberto deixou de ser marco")

# A3 e A4: regressão e progressão da ficha
SAI = "Saída da Unidade Penal: UMMVE, Destino: PDIB, Motivo: Regressão de Regime, Conforme Ofício: 1."
f = {"eventos": [{"data": "27.05.2026", "texto": SAI}]}
r = reg([crime()], [inc(AR, "Fechado - Regressão Cautelar", "10/03/2026", "10/03/2026")],
        [ev(PR, "PRISÃO EM FLAGRANTE", "01/02/2017"), ev("INTERRUPÇÃO", "FUGA", "01/02/2026", ""), ev(PR, "RECAPTURA", "26/05/2026")])
ok(not rf._regime_x_ficha(r, f), "A3: regressão cautelar do RSPE antes da ida à unidade: %s" % rf._regime_x_ficha(r, f))
f = {"eventos": [{"data": "04.12.2018", "texto": "TOMOU CIÊNCIA DA DECISÃO DE REGRESSÃO DE REGIME"}]}
r = reg([crime()], [inc(AR, "Fechado - Regressão", "26/03/2019", "26/03/2019")], [ev(PR, "PRISÃO EM FLAGRANTE", "23/11/2018")])
ok(not rf._regime_x_ficha(r, f), "A3: regressão decidida depois do registro da ficha")
f = {"eventos": [{"data": "25.05.2018", "texto": "Saída da Unidade Penal: X, Destino: CENTRO PENAL AGROINDUSTRIAL DA GAMELEIRA, Motivo: Progressão de Regime"},
                 {"data": "25.05.2019", "texto": "Saída da Unidade Penal: X, Destino: PDIB, Motivo: Regressão de Regime"}]}
r = reg([crime()], [], [ev(PR, "PRISÃO EM FLAGRANTE", "01/02/2017"), ev("INTERRUPÇÃO", "FUGA", "24/08/2017", ""), ev(PR, "RECAPTURA", "22/08/2020")])
ok(not rf._regime_x_ficha(r, f), "A4: progressão/regressão da ficha no período de fuga: %s" % rf._regime_x_ficha(r, f))

# A5: regime inicial aberto e data-base depois de falta posterior à progressão: informativo
evs = [ev(PR, "PRISÃO EM FLAGRANTE", "01/02/2017"), ev("INTERRUPÇÃO", "SOLTURA", "01/06/2017", ""), ev(PR, "PRISÃO DEFINITIVA", "26/08/2019")]
t = por_tipo(reg([crime()], [inc(AR, "Aberto - Regime Inicial", "", "26/08/2019")], evs, data_base_seeu="26/08/2019", regime_atual="Aberto - ATIVO"))
ok(t.get("regime-inicial-depois-da-primeira-prisao", [{}])[0].get("nivel") == "info", "A5 aberto: %s" % t.get("regime-inicial-depois-da-primeira-prisao"))
incs = [inc(AR, "Fechado - Regime Inicial", "", "26/08/2019"), inc(AR, "Semiaberto - Progressão de Regime", "01/02/2022", "01/02/2022"),
        inc("HOMOLOGAÇÃO DE FALTA GRAVE", "16/03/2026", "20/04/2026", "16/03/2026"), inc(AR, "Fechado - Regressão", "20/04/2026", "16/03/2026")]
it = por_tipo(reg([crime()], incs, evs, data_base_seeu="16/03/2026")).get("regime-inicial-depois-da-primeira-prisao", [{}])[0]
ok(it.get("nivel") == "info" and "sem efeito atual" in it.get("titulo", ""), "A5 falta depois da progressão: %s" % it)

# A6: caixa da data-base coerente com a Auditoria
r = reg([crime()], [inc(AR, "Fechado - Regime Inicial", "", "01/02/2017"), inc(AR, "Semiaberto - Progressão de Regime", "06/01/2024", "06/01/2024")],
        [ev(PR, "PRISÃO EM FLAGRANTE", "01/02/2017"), ev("INTERRUPÇÃO", "SOLTURA", "01/12/2022", ""), ev(PR, "PRISÃO EM FLAGRANTE", "16/12/2022")],
        data_base_seeu="16/12/2022")
x = rv.data_base_info(r, itens(r))
ok(x["db_cor"] == "" and "favorável" in x["db_motivo"], "A6 favorável: %s" % x)
r = reg([crime(data_infracao="13/03/2023")], [inc(AR, "Fechado - Regime Inicial", "", "01/02/2017")], [ev(PR, "PRISÃO EM FLAGRANTE", "01/02/2017")],
        data_base_seeu="13/03/2023")
x = rv.data_base_info(r, itens(r))
ok("data do fato" in x["db_motivo"], "A6 data do fato: %s" % x)

# A7: falta prescrita não fica como data-base que "confere" nem como perda "dentro do limite"
incs = [inc(AR, "Fechado - Regime Inicial", "", "14/09/2015"),
        inc("HOMOLOGAÇÃO DE FALTA GRAVE", "Data da infração: 01/04/2022", "15/05/2025", "01/04/2022"),
        inc("REMIÇÃO", "435 Dia(s) Remido(s)", "01/01/2022", "01/01/2022"), inc("DIAS REMIDOS PERDIDOS", "145 Dia(s)", "15/05/2025", "15/05/2025")]
r = reg([crime()], incs, [ev(PR, "PRISÃO PREVENTIVA", "14/09/2015")], data_base_seeu="01/04/2022",
        saldo_remidos="(435 dias remidos - 145 dias perdidos)")
t = por_tipo(r)
pr = t.get("falta-homologada-apos-prescricao", [{}])[0]
ok("data-base-confere-com-o-rspe" not in t and "perda-de-remidos-pela-falta-grave-de" not in t
   and "145 dias remidos" in pr.get("detalhe", "") and "volta a ser 14/09/2015" in pr.get("detalhe", ""), "A7: %s / %s" % (list(t), pr.get("detalhe")))

# A8: alteração de data-base na data de uma progressão concedida não é "sem falta homologada"
r = reg([crime()], [inc(AR, "Fechado - Regime Inicial", "", "01/02/2017"), inc(AR, "Semiaberto - Progressão de Regime", "09/11/2023", "09/11/2023"),
                    inc(DB, "Progressão de Regime", "09/11/2023", "09/11/2023"), inc(DB, "Progressão de Regime", "09/11/2023", "09/11/2023")],
        [ev(PR, "PRISÃO EM FLAGRANTE", "01/02/2017")], data_base_seeu="09/11/2023")
t = por_tipo(r)
ok("alteracao-de-data-base-sem-falta-homologada" not in t and len(t.get("alteracao-de-data-base-no-lugar-do-incidente", [])) <= 1, "A8: %s" % list(t))

# A9: no aberto, os itens de data-base também ficam sem efeito
r = reg([crime()], [inc(AR, "Aberto - Progressão de Regime", "01/02/2025", "01/02/2025"), inc(DB, "Progressão de Regime", "04/09/2025", "04/09/2025")],
        [ev(PR, "PRISÃO EM FLAGRANTE", "01/02/2017")], data_base_seeu="04/09/2025", regime_atual="Aberto - ATIVO")
ok(all(i["nivel"] == "info" for i in itens(r) if i["tipo"] == "alteracao-de-data-base-sem-falta-homologada"), "A9: aberto")

# A10: soma das penas maior que o total (favorece o assistido): informativo
r = reg([crime(), crime(processo_criminal="0000004-44.2016.8.12.0001", pena_imposta="1 ano(s), 0 mês(es) e 0 dia(s)")], pena_total="10a0m0d")
ok(por_tipo(r).get("soma-das-penas-difere-da-pena-total", [{}])[0].get("nivel") == "info", "A10: soma favorável")

# A11: capitulação criada depois do fato com divergência de fração que não decorre dela: informativo
c = crime(artigo="ART 157: Roubo", tipo_penal="§ 2º-A, I: se a violência ou ameaça é exercida com emprego de arma de fogo, Reclusão: 4 a 10 anos",
          data_infracao="10/01/2007", fracao_livramento="1/2 - Comum Reincidente", vga="S")
ok(all(i["nivel"] == "info" for i in itens(reg([c])) if i["tipo"] == "capitulacao-criada-depois-do-fato"), "A11: capitulação")

# A12: parágrafo de majorante (art. 136, § 3º): o máximo é o do caput aumentado
c = crime(artigo="ART 136: Maus-tratos", tipo_penal="§ 3º: Maus-tratos se o crime é praticado contra pessoa menor de 14 anos, Detenção: 2 a 4 meses OU Multa",
          pena_imposta="0 ano(s), 8 mês(es) e 26 dia(s)", data_infracao="05/01/2021", fracao_progressao="20% - Comum")
ok("pena-acima-do-maximo-do-tipo-cadastrado" not in por_tipo(reg([c], pena_total="0a8m26d")), "A12: majorante")

# A13: o reinício lançado pela ficha usa a "Data Prisão" (delegacia) poucos dias antes da entrada na unidade
f = {"data_prisao": "09.10.2025", "eventos": [{"data": "15.10.2025", "texto": "Entrada na Unidade Penal: PRESÍDIO, Procedente: DEPAC CENTRO"}]}
r = reg([crime()], [], [ev(PR, "PRISÃO EM FLAGRANTE", "01/02/2017"), ev("INTERRUPÇÃO", "FUGA", "01/02/2025", "")])
rf.reconciliar_eventos(r, f)
ok(any(e.get("_ficha") and e["data"] == "09/10/2025" for e in r["_eventos"]), "A13: reinício %s" % [e["data"] for e in r["_eventos"]])
ok(not rf._prisao_x_ficha(r, f), "A13: alerta contra o próprio reinício")

# A14: texto da reincidência sem condenação anterior cita os crimes marcados
r = reg([crime(reincidente_comum="S")])
it = por_tipo(r).get("marcado-reincidente-sem-condenacao-anterior-tran", [{}])[0]
ok("art. 155" in it.get("detalhe", "") and not it.get("detalhe", "").startswith("Nenhum processo"), "A14: %s" % it.get("detalhe"))

# A15: o info da sanção (regressão definitiva) não recebe o prazo de prescrição contado da regressão
r = reg([crime()], [inc(AR, "Fechado - Regressão", "10/01/2024", "10/01/2024")], [ev(PR, "PRISÃO EM FLAGRANTE", "01/02/2017")], data_base_seeu="10/01/2024")
ok(not any("Prescrição da falta disciplinar" in i["detalhe"] for i in itens(r) if "sanção que pressupõe" in i["titulo"]), "A15")

# ---------------- 4ª revisão ----------------
# A1: alteração da data-base do livramento não é item da data-base da progressão
r = reg([crime()], [inc(AR, "Fechado - Regime Inicial", "", "18/04/2018"), inc(DB, "Livramento Condicional", "30/09/2026", "18/04/2018")],
        [ev(PR, "PRISÃO EM FLAGRANTE", "18/04/2018")], data_base_seeu="18/04/2018")
t = por_tipo(r)
ok(not any(k.startswith("alteracao-de-data-base") for k in t), "4-A1: %s" % list(t))

# A2: anterior por associação para o tráfico (art. 35) não é reincidência em hediondo para a progressão
DR = dict(lei="11343/06 - Lei de Drogas", artigo="ART 33: Tráfico de drogas", tipo_penal="CAPUT: Importar, Reclusão: 5 a 15 anos E Multa",
          data_infracao="10/02/2021", transito_processo="10/02/2022", pena_imposta="5 ano(s), 0 mês(es) e 0 dia(s)",
          fracao_progressao="60% - Reincidente Hediondo", fracao_livramento="2/3", reincidente_comum="S")
prev = crime(processo_criminal="0000009-00.2015.8.12.0001", lei="11343/06 - Lei de Drogas", artigo="ART 35: Associação para o tráfico",
             tipo_penal="CAPUT: Associarem-se, Reclusão: 3 a 10 anos E Multa", data_infracao="01/01/2015", transito_processo="01/01/2016",
             fracao_progressao="16,67%")
t = por_tipo(reg([prev, crime(**DR)], pena_total="13a0m0d"))
ok(any(i["nivel"] == "alerta" and "(40%" in i["titulo"] for i in t.get("percentual-de-progressao-diverge", [])), "4-A2: %s" % t.get("percentual-de-progressao-diverge"))

# A3: "Crime Hediondo até 24/07/1990" com frações comuns não é tratamento de hediondo
c = crime(lei="10826/03 - Estatuto do Desarmamento", artigo="ART 12: Posse irregular", tipo_penal="CAPUT: Possuir, Detenção: 1 a 3 anos E Multa",
          data_infracao="01/01/2021", fracao_progressao="16% - Art. 112, I", fracao_livramento="1/3 - Crime Hediondo até 24/07/1990")
ok("seeu-tratou-como-hediondo-mas-o-tipo-nao-consta" not in por_tipo(reg([c])), "4-A3")

# A4: dano qualificado com violência (art. 163, p. ú., I): violência elementar
c = crime(artigo="ART 163: Dano", tipo_penal="Parágrafo Único, I: Com violência à pessoa ou grave ameaça, Detenção: 6 meses a 3 anos E Multa", vga="S")
ok("marcacao-de-violencia-grave-ameaca-diverge-do-ti" not in por_tipo(reg([c])), "4-A4")

# A5: prisão de processo extinto (anterior ao fato do crime ativo) não entra na conta do regime inicial
cs = [crime(processo_criminal="0000002-22.2015.8.12.0001", data_infracao="10/06/2015", extinto="Sim"),
      crime(processo_criminal="0000003-33.2017.8.12.0001", data_infracao="01/11/2017")]
evs = [ev(PR, "PRISÃO EM FLAGRANTE", "13/06/2015", "0000002-22.2015.8.12.0001"), ev("INTERRUPÇÃO", "SOLTURA", "10/01/2016", ""),
       ev(PR, "PRISÃO PREVENTIVA", "01/11/2017", "0000003-33.2017.8.12.0001")]
ok("regime-inicial-depois-da-primeira-prisao" not in por_tipo(reg(cs, [inc(AR, "Fechado - Regime Inicial", "", "01/11/2017")], evs, data_base_seeu="01/11/2017")),
   "4-A5: prisão de processo extinto")

# A6: término além de 30 anos para fatos anteriores a 23/01/2020
c = crime(artigo="ART 217-A: Estupro de vulnerável", tipo_penal="CAPUT: Ter conjunção, Reclusão: 8 a 15 anos", data_infracao="01/01/2017",
          pena_imposta="48 ano(s), 9 mês(es) e 0 dia(s)", fracao_progressao="2/5 - Hediondo", fracao_livramento="2/3 - Hediondo")
r = reg([c], [inc(AR, "Fechado - Regime Inicial", "", "30/12/2020")], [ev(PR, "PRISÃO PREVENTIVA", "30/12/2020")], pena_total="48a9m0d",
        termino_previsao_seeu="30/12/2060", data_base_seeu="30/12/2020")
it = por_tipo(r).get("limite-de-cumprimento-art-75", [{}])[0]
ok(it.get("nivel") == "alerta" and "30/12/2050" in it.get("titulo", "") and ra.fundamentacao(it, r), "4-A6: %s" % it)
r["termino_previsao_seeu"] = "30/12/2049"
ok("limite-de-cumprimento-art-75" not in por_tipo(r), "4-A6: dentro do limite")

# A7: frações diferentes entre os crimes: média ponderada, não a maior
cs = [crime(fracao_progressao="2/5 - Hediondo", artigo="ART 217-A: Estupro de vulnerável", tipo_penal="CAPUT: Ter, Reclusão: 8 a 15 anos",
            pena_imposta="8 ano(s), 0 mês(es) e 0 dia(s)", fracao_livramento="2/3 - Hediondo"),
      crime(processo_criminal="0000004-44.2016.8.12.0001", pena_imposta="2 ano(s), 0 mês(es) e 0 dia(s)")]
evs = [ev(PR, "PRISÃO EM FLAGRANTE", "01/02/2016"), ev("INTERRUPÇÃO", "SOLTURA", "01/06/2016", ""), ev(PR, "PRISÃO DEFINITIVA", "01/02/2018")]
it = por_tipo(reg(cs, [inc(AR, "Fechado - Regime Inicial", "", "01/02/2018")], evs, data_base_seeu="01/02/2018", fracao_progressao_aplicada="2/5")).get(
    "regime-inicial-depois-da-primeira-prisao", [{}])[0]
ok("ponderada" in it.get("detalhe", "") and "a fração aplicada pelo SEEU (2/5)" not in it.get("detalhe", ""), "4-A7: %s" % it.get("detalhe"))

# A8: data-base corrigida pelo operador: a maior fração pelo valor
r = {"_db_manual": "01/01/2024|", "data_base_seeu": "01/01/2025", "progressao_previsao_seeu": "01/01/2027", "fracao_progressao_aplicada": "",
     "_crimes": [crime(fracao_progressao="40% - Hediondo"), crime(fracao_progressao="3/5 - Hediondo Reincidente")]}
# fração 3/5 (e não 40%): previsão - (1 - 3/5) x 366 dias
ok(rv._prog_pela_db_manual(r) == date(2027, 1, 1) - timedelta(days=round(0.4 * 366)),
   "4-A8: %s" % rv._prog_pela_db_manual(r))

# A9: recaptura sem remição: sem "0 dias remidos" e sem o Tema 709 no fundamento
incs = [inc(AR, "Semiaberto - Regime Inicial", "", "01/08/2025")]
evs = [ev(PR, "INÍCIO DO CUMPRIMENTO REGIME SEMIABERTO", "01/08/2025"), ev("INTERRUPÇÃO", "FUGA", "01/02/2026", ""), ev(PR, "RECAPTURA", "01/05/2026")]
it = por_tipo(reg([crime()], incs, evs, data_base_seeu="01/05/2026")).get("data-base-movida-para-a-recaptura-sem-falta-homo", [{}])[0]
ok(it and "0 dias remidos" not in it["detalhe"] and "((" not in it["detalhe"] and "709" not in it["fundamento"], "4-A9: %s" % it)

# A10: rótulo do dispositivo pela data do fato (redação original antes da Lei 10.792/2003)
ok("redação original" in ra._rot_dispositivo("16,67% (LEP art. 112 (redação original de 1984 e Lei 10.792/2003))".replace("16,67%", "1/6"), date(1993, 6, 13)),
   "4-A10: %s" % ra._rot_dispositivo("1/6 (LEP art. 112 (redação original de 1984 e Lei 10.792/2003))", date(1993, 6, 13)))

# A11: datas de vigência lidas da base
ok(rg.data_lei_15358() == date(2026, 3, 25) and rg.data_lei_13964() == date(2020, 1, 23) and rg.data_lei_15402() == date(2026, 5, 8)
   and rg.data_lei_11464() == date(2007, 3, 29), "4-A11: vigências")

# A12: citações (RE 1.236.835 retirado; SV 63; maus antecedentes; Tema 941)
ok("1.236.835" not in open(ra.__file__, encoding="utf-8").read(), "4-A12: RE 1.236.835")
ok("Súmula Vinculante 63" in ra.FUND_TIPOS["seeu-tratou-como-hediondo-mas-o-tipo-nao-consta"][0]
   and "HC 57.300" in ra.FUND_TIPOS["fracao-de-livramento-diverge"][0] and "Tema 941" in ra.FUND_TIPOS["perda-de-remidos-sem-falta-grave-datada-no-rspe"][0], "4-A12")

# A13: alteração de data-base do livramento não é "livramento concedido antes"
c = crime(fracao_livramento="1/1 - Hediondo Reincidente/Reincidente Específico")
t = por_tipo(reg([c], [inc(DB, "Livramento Condicional", "01/02/2023", "01/02/2023")]))
ok("livramento-1-1-pela-revogacao" not in t, "4-A13: %s" % list(t))

if falhas:
    print("FALHOU (revisão 3 e 4 da auditoria):")
    for f_ in falhas:
        print("  " + f_)
    sys.exit(1)
print("ok: revisões 3 e 4 da auditoria (alteração de data-base, guia nova, ficha, regime inicial, data-base, falta prescrita, art. 75, "
      "reincidência específica, frações, textos e citações)")
