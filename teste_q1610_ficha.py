"""Teste dos quesitos de 16/10 - grupo "ficha" (itens 1, 2, 3, 4, 5, 6, 9, 12, 16, 17): histórico anterior ao SIAPEN só exibido
(a conferir quando cai nesta execução); filiação completa; lançamento sem data datado pela única data citada; saídas por
determinação judicial (transferência, monitoramento, apresentação, a conferir - nunca liberdade automática); recaptura e
apresentação espontânea encerram a fuga, cidade do interior é transferência, flagrante só narrado a conferir; autorização e termo
de compromisso de trabalho externo a conferir; falta só pela ciência; sublançamento só com verbo e fora de período; domiciliar e
monitoramento como custódia, e monitoramento por outro processo sem suspender a prescrição; faltas de execução anterior só como
informação. Casos fictícios. Rodar: python teste_q1610_ficha.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf
import rspe_prescricao as rp
import rspe_scraper as rs

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def ficha(evs, **extra):
    f = dict({"eventos": [{"data": d, "texto": t} for d, t in evs], "versao_leitura": 0}, **extra)
    return rf.atualizar(f)


def ev(tipo, motivo, data, proc=""):
    return {"tipo": tipo, "motivo": motivo, "complemento": "", "data": data, "data_decisao": "", "data_referencia": "", "processos": proc}


PRI, INT = "PRISÃO/INÍCIO DE CUMPRIMENTO", "INTERRUPÇÃO"
SAI = "Saída da Unidade Penal: PDIB, Destino: %s, Motivo: Determinação Judicial, Conforme Ofício: 1."

# ---- item 4: saída por determinação judicial, por grupo ----
ok(rf.saida_judicial(SAI % "UMMVE - UNIDADE MISTA DE MONITORAMENTO VIRTUAL ESTADUAL")[0] == "monitoramento", "4: UMMVE")
ok(rf.saida_judicial(SAI % "1ª DELEGACIA DE POLÍCIA DE AQUIDAUANA")[0] == "apresentacao", "4: delegacia")
ok(rf.saida_judicial(SAI % "ESTABELECIMENTO PENAL DE AQUIDAUANA")[0] == "transferencia", "4: presídio")
for dest in ("", "DECISÃO JUDICIAL", "COMARCA DE MIRANDA/MS", "1ª VARA DE JARDIM / MS", "LOCAL INCERTO E NÃO SABIDO"):
    ok(rf.saida_judicial(SAI % dest)[0] == "a_conferir", "4: destino %r devia ficar a conferir" % dest)
    ok(not rf.RE_SAIDA_LIVRE.search(SAI % dest), "4: destino %r lido como liberdade" % dest)
_ev = [(date(2020, 5, 1), SAI % "DECISÃO JUDICIAL"), (date(2020, 5, 3), "Entrada na Unidade Penal: IPCG, Procedente: PDIB - CAPITAL, Conforme OF/CI 1.")]
ok(rf.saida_judicial(_ev[0][1], _ev, _ev[0][0])[0] == "transferencia", "4: nova entrada em até 3 dias devia ser transferência")
# custódia ininterrupta (indulto, inciso IV): monitoramento mantém a custódia; destino incerto sem nova entrada fica a conferir
base_ev = [("01.01.2019", "Entrada na Unidade Penal: PDIB, Procedente: DP MARACAJU - INTERIOR, Conforme OF/CI 1."),
           ("10.01.2020", "TRABALHO: Iniciou no setor de trabalho FAXINA"),
           ("10.03.2021", "MUDANÇA DE CELA: PDIB, Motivo: x")]
f = ficha(base_ev + [("01.06.2020", SAI % "UMMVE - UNIDADE MISTA DE MONITORAMENTO VIRTUAL ESTADUAL")])
res, nota = rf.custodia_na_ficha(f, date(2019, 1, 1), [date(2020, 9, 1)])
ok(res is True, "4/16: saída para o monitoramento interrompeu a custódia: %s %s" % (res, nota))
f = ficha(base_ev + [("01.06.2020", SAI % "COMARCA DE MIRANDA/MS")])
res, nota = rf.custodia_na_ficha(f, date(2019, 1, 1), [date(2020, 9, 1)])
ok(res is None and "a conferir" in nota, "4: destino incerto devia ficar a conferir: %s %s" % (res, nota))
f = ficha(base_ev + [("01.06.2020", "Saída da Unidade Penal: PDIB, Destino: , Motivo: Prisão Domiciliar, Conforme Ofício: 1.")])
res, nota = rf.custodia_na_ficha(f, date(2019, 1, 1), [date(2020, 9, 1)])
ok(res is True, "16: domiciliar interrompeu a custódia: %s %s" % (res, nota))
# custódia depois da interrupção do RSPE
f = ficha([("01.01.2019", "Entrada na Unidade Penal: PDIB, Procedente: DP"), ("01.06.2020", SAI % "UMMVE - UNIDADE MISTA DE MONITORAMENTO VIRTUAL")])
ok(rf.custodia_apos(f, date(2020, 1, 1))[0] is True, "16: monitoramento depois da interrupção lido como liberdade: %s" % (rf.custodia_apos(f, date(2020, 1, 1)),))
f = ficha([("01.01.2019", "Entrada na Unidade Penal: PDIB, Procedente: DP"), ("01.06.2020", SAI % "")])
ok(rf.custodia_apos(f, date(2020, 1, 1))[0] is None and "a conferir" in rf.custodia_apos(f, date(2020, 1, 1))[1], "4: saída de destino vazio devia ficar a conferir")
r = {"_eventos": [ev(PRI, "PRISÃO DEFINITIVA", "01/01/2019"), ev(INT, "DESCUMPRIMENTO", "01/05/2020")], "_crimes": [], "_incidentes": []}
its = rf._interrupcao_x_ficha(r, f)
ok(any(i["nivel"] == "verificar" and "a conferir" in i["titulo"] for i in its), "4: Auditoria da interrupção com saída incerta: %s" % [i["titulo"] for i in its])

# ---- item 5: recaptura e apresentação espontânea; cidade do interior; flagrante só narrado ----
ok(not rf.RE_ENTRADA_RUA.search("Entrada na Unidade Penal: PDIB, Procedente: SIDROLÂNDIA - INTERIOR, Conforme OF/CI 1."), "5: cidade do interior lida como vinda da rua")
ok(not rf.RE_SAIDA_LIVRE.search("NESTA DATA APRESENTOU-SE ESPONTANEAMENTE APÓS EVASÃO DO EPRACA"), "5: apresentação espontânea lida como fuga")
ok(not rf.RE_FUGA_FICHA.search("Entrada na Unidade Penal: EPRSAA, Procedente: RECAPTURA - INTERIOR, Conforme OF/CI 1.") or
   rf.RE_RETORNO_FUGA.search(rf._sem_fuga_falsa("Entrada na Unidade Penal: EPRSAA, Procedente: RECAPTURA - INTERIOR")), "5: recaptura lida como fuga")
r = {"_eventos": [ev(PRI, "PRISÃO DEFINITIVA", "01/01/2019"), ev(INT, "FUGA", "01/05/2020")], "_crimes": [], "_incidentes": []}
f = ficha([("01.01.2019", "Entrada na Unidade Penal: EPRSAA, Procedente: DP"),
           ("10.03.2021", "Entrada na Unidade Penal: EPRSAA, Procedente: RECAPTURA - INTERIOR, Conforme OF/CI 1."),
           ("10.04.2021", "TRABALHO: Iniciou no setor de trabalho FAXINA")])
av = rf.reconciliar_eventos(r, f)
ok(any(t == "reinicio-pela-ficha" and x["rua"] for t, x in av), "5: recaptura não encerrou a fuga (reinício pela ficha): %s" % av)
f = ficha(base_ev + [("25.08.2020", "Nesta data ... foi preso em Flagrante referente aos Autos 0000001-00.2020.8.12.0001 - Prisão Preventiva")])
res, nota = rf.custodia_na_ficha(f, date(2019, 1, 1), [date(2020, 9, 1)])
ok(res is None and "flagrante" in nota, "5: flagrante narrado devia ficar a conferir: %s %s" % (res, nota))

# ---- item 6: autorização e termo de compromisso de trabalho externo: a conferir, sem prestação efetiva ----
f = ficha([("09.06.2024", "Foi autorizado o trabalho externo, Juiz de Direito X, autos 0000001-00.2020.8.12.0001."),
           ("12.01.2025", "TERMO DE COMPROMISSO DE HORÁRIOS Assumo o compromisso de Trabalho Externo para a função/empresa X"),
           ("13.01.2025", "MUDANÇA DE CELA: Ala B SEMIABERTO TRABALHO EXTERNO/CONVÊNIO")])
ok(len(f["externo_a_conferir"]) == 2 and not any(t.get("externo") for t in f["trabalho"]), "6: externo a conferir: %s %s" % (f["externo_a_conferir"], f["trabalho"]))
r = {"_eventos": [ev(PRI, "PRISÃO DEFINITIVA", "01/01/2020")], "indulto_2025": "A VERIFICAR: art. 9º, XI", "indulto_2025_status": "verificar",
     "indulto_2025_detalhe": "Situação em 25/12/2025: regime semiaberto · primário\n? XI: exige 1/4 e 5 saídas temporárias - verificar na ficha"}
rf.complementar_decretos(r, dict(f, estudos=[], exames=[]), date(2026, 10, 16))
lin = [l for l in r["indulto_2025_detalhe"].split("\n") if " XI:" in l]
ok(lin and lin[0].startswith("?") and "termo de compromisso" in lin[0] and r["indulto_2025_status"] == "verificar", "6: XI devia ficar a conferir: %s" % lin)

# ---- item 3: lançamento sem data ----
evs = rf._datar_sem_data([{"data": "", "texto": "CONSELHO DISCIPLINAR: FOI CONCLUSO PROCESSO, REFERENTE AO FATO OCORRIDO EM 05/10/2023"},
                          {"data": "01.01.2023", "texto": "x"}, {"data": "01.01.2024", "texto": "y"}])
ok([e["data"] for e in evs] == ["01.01.2023", "05.10.2023", "01.01.2024"] and evs[1].get("data_do_texto"), "3: data citada única: %s" % evs)
evs = rf._datar_sem_data([{"data": "", "texto": "ALVARÁ DE SOLTURA EM 16/02/2016, AUDIÊNCIA EM 20/02/2016"}, {"data": "01.01.2017", "texto": "x"}])
ok(evs[0]["data"] == "" and not evs[0].get("data_do_texto"), "3: duas datas no texto deviam deixar sem data: %s" % evs)

# ---- item 12: sublançamento só com verbo e fora de período ----
f = ficha([("01.03.2009", "Iniciou trabalho no setor X. Em 15/06/09 Evasão CPA. Em 20/04/10 Nesta data deu entrada no IPCG, procedente da DERF.")])
ds = [(e["data"], bool(e.get("a_conferir"))) for e in f["eventos"]]
ok(("20.04.2010", False) in ds and ("", True) in ds and "15.06.2009" not in [d for d, _ in ds], "12: sublançamentos: %s" % ds)
ok(any("a conferir" in n for n in rf.leitura_parcial(f)[0]), "12: aviso do trecho a conferir: %s" % rf.leitura_parcial(f)[0])
f = ficha([("01.03.2019", "Trabalhou no período de Em 16/05/19 a 16/07/19 no setor X.")])
ok(len(f["eventos"]) == 1 and f["eventos"][0]["data"] == "01.03.2019", "12: período partido em dois: %s" % f["eventos"])

# ---- item 9: falta registrada só pela ciência ----
f = ficha([("15.03.2024", "TOMOU CIÊNCIA DO RESULTADO DO PROCESSO DISCIPLINAR Nº 12/2024, SENDO SANCIONADO POR FALTA DE NATUREZA GRAVE")])
fa = f["faltas"]
ok(fa and fa[0].get("data_fato_ciencia") and fa[0]["data_fato"] == "15.03.2024", "9: falta só pela ciência sem marca: %s" % fa)
r = {"_eventos": [ev(PRI, "PRISÃO DEFINITIVA", "01/01/2020")], "_incidentes": [], "_crimes": []}
rs.faltas_da_ficha(r, f, date(2026, 10, 16))
inc = [i for i in r["_incidentes"] if i.get("_ficha")]
ok(inc and inc[0].get("_data_ciencia") and "ciência" in inc[0]["complemento"], "9: aviso da ciência no incidente: %s" % inc)
if inc:
    inc[0]["_falta"] = "sim"
    ach = rs.indicios_falta(inc, date(2024, 12, 25))
    ok(ach and not any(firme for _t, firme in ach), "9: falta pela ciência na janela devia ficar a verificar: %s" % ach)

# ---- item 17: falta anterior a esta execução: só informação ----
f = ficha([("10.05.2025", "REGISTRO DE FALTA DISCIPLINAR: ART. 50, VI DA LEP, COMETIDA EM 10/05/2025")])
r = {"_eventos": [ev(PRI, "PRISÃO DEFINITIVA", "01/01/2026")], "_incidentes": [], "_crimes": []}
rs.faltas_da_ficha(r, f, date(2026, 10, 16))
ok(not [i for i in r["_incidentes"] if i.get("_ficha")], "17: falta de execução anterior virou falta a apurar: %s" % r["_incidentes"])
its = rf._faltas_outra_execucao_x_ficha(r, f)
ok(its and its[0]["nivel"] == "info", "17: falta anterior sem a informação: %s" % its)
r["_eventos"] = [ev(PRI, "PRISÃO DEFINITIVA", "01/01/2025")]
rs.faltas_da_ficha(r, f, date(2026, 10, 16))
ok([i for i in r["_incidentes"] if i.get("_ficha")], "17: falta desta execução não entrou")

# ---- item 1: histórico anterior ao SIAPEN ----
f = {"eventos": [], "historico_oculto": ["Em 16/02/97 evadiu do EPRACA", "Em 21/09/10 Classificado conduta disciplinar em ÓTIMA"]}
r = {"_eventos": [ev(PRI, "PRISÃO DEFINITIVA", "01/01/2015")]}
its = rf._historico_anterior_x_ficha(r, f)
ok(its and its[0]["nivel"] == "info" and "fora das contas" in its[0]["titulo"], "1: histórico anterior: %s" % its)
r = {"_eventos": [ev(PRI, "PRISÃO DEFINITIVA", "01/01/1996")]}
its = rf._historico_anterior_x_ficha(r, f)
ok(its and its[0]["nivel"] == "verificar" and "16/02/1997" in its[0]["detalhe"], "1: fato no período desta execução devia ficar a conferir: %s" % its)
ok(not any("evadiu" in e["texto"] for e in ficha([("01.01.2015", "x")], historico_oculto=f["historico_oculto"])["eventos"]), "1: histórico anterior virou lançamento")

# ---- item 2: filiação completa (leitura antiga com o campo vizinho colado) ----
f = ficha([("01.01.2020", "x")], filiacao="MARIA FICTICIA DE TAL \\ JOSE FICTICIO DE TALNº Pront Saúde: PDIB - 1.234")
ok(f["filiacao"] == "MARIA FICTICIA DE TAL \\ JOSE FICTICIO DE TAL" and f["nome_mae"] == "MARIA FICTICIA DE TAL", "2: filiação: %r" % f.get("filiacao"))

# ---- item 16 (prescrição): monitoramento por outro processo não suspende ----
EXEC = "0000009-99.2015.8.12.0001"
c3 = {"processo_criminal": "0000001-11.2013.8.12.0001", "pena_imposta": "3 ano(s), 0 mês(es) e 0 dia(s)", "pena_total_processo": "3a0m0d - PENA ORIGINÁRIA",
      "transito_mp": "01/01/2015", "transito_processo": "01/01/2015", "data_infracao": "01/01/2013", "data_denuncia": "01/02/2013", "data_sentenca": "01/06/2014",
      "artigo": "ART 155: Furto", "lei": "2848/40 - Código Penal", "extinto": "Não"}
r = {"data_nascimento": "01/01/1970", "pena_total": "3a0m0d", "pena_cumprida": "1a0m0d", "pena_remanescente": "2a0m0d", "data_geracao_rspe": "06/10/2026",
     "processo_execucao": EXEC, "situacao_cumprimento": "EM CUMPRIMENTO", "_crimes": [c3], "_incidentes": [],
     "_eventos": [ev(PRI, "PRISÃO DEFINITIVA", "01/02/2015", c3["processo_criminal"]), ev(INT, "FUGA", "01/02/2016")]}
L = rp.analisar(r, date(2026, 10, 16), {"eventos": [{"data": "10.02.2016", "texto": "Entrada na Unidade Penal: UNIDADE MISTA DE MONITORAMENTO VIRTUAL, "
                                                                               "Conforme Ofício: 0005555-55.2016.8.12.0001"}]})["presc_linhas"][0]
ok(not any(p["tipo"] == "outro_motivo" for p in L["ppe_linha_tempo"]) and any("não suspende" in p["efeito"] for p in L["ppe_linha_tempo"]),
   "16: monitoramento por outro processo suspendeu a executória: %s" % [(p["tipo"], p["fonte"]) for p in L["ppe_linha_tempo"]])

if falhas:
    print("FALHOU (quesitos 16/10 - ficha):")
    for x in falhas:
        print("  " + x)
    sys.exit(1)
print("ok: quesitos 16/10 - ficha (histórico anterior, filiação, lançamento sem data, saídas por determinação judicial, recaptura e flagrante "
      "narrado, trabalho externo autorizado, sublançamentos, falta pela ciência, faltas de execução anterior, monitoramento e domiciliar)")
