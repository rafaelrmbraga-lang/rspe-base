"""Segunda conferência manual (7.14.1), frente Auditoria: nascimento lido da ficha sem mandar informar; artigo revogado antes do
fato; recaptura lançada como "início do cumprimento" depois de fuga sem falta; fundamento do livramento fora do tráfico; detração
antes da fração pela conta do SEEU em meses e lapso total somado em anos/meses/dias; regime inicial "sem efeito" só com data-base
firme; soltura da ficha não lançada no RSPE; prisão definitiva não é detração; livramento revogado (CP, art. 88); remição pretérita
sem efeito atual; perda de remidos e remição posterior à perda; limite de 1/3 por falta; crime cometido em liberdade provisória;
extinção da ficha com número de outra execução (art. 28); ressalva nas frações derivadas; término de execução extinta; "Data
Prisão" da ficha anterior a um alvará; custódia ligada pela ficha a esta execução com saída para a comarca. Casos hipotéticos,
nomes fictícios. Rodar: python teste_conf2_auditoria.py"""
import copy
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_auditoria as ra
import rspe_ficha as rf
import rspe_reincidencia as rr
import rspe_scraper as rs
import rspe_view as rv

falhas = []
HOJE = date(2026, 10, 16)


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


AR = "FIXAÇÃO/ALTERAÇÃO DE REGIME"
PR = "PRISÃO/INÍCIO DE CUMPRIMENTO"
P1, P2 = "0000001-11.2022.8.12.0001", "0000002-22.2024.8.12.0001"


def inc(tipo, compl, dec, ref, sit="CONCEDIDO", procs=""):
    return {"tipo": tipo, "motivo": "", "complemento": compl, "data": "", "data_decisao": dec, "data_referencia": ref, "processos": procs, "situacao": sit}


def ev(tipo, motivo, data, procs=P1):
    return {"tipo": tipo, "motivo": motivo, "data": data, "processos": procs}


def crime(**kw):
    c = {"processo_criminal": P1, "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto", "pena_total_processo": "",
         "tipo_penal": "CAPUT: Subtrair, Reclusão: 1 a 4 anos", "pena_imposta": "10 ano(s), 0 mês(es) e 0 dia(s)",
         "data_infracao": "10/01/2015", "data_sentenca": "10/06/2015", "transito_mp": "10/07/2015", "transito_processo": "10/07/2015",
         "extinto": "Não", "suspenso": "Não", "vga": "N", "resultado_morte": "N", "reincidente_comum": "N", "reincidente_especifico": "N",
         "comando_orcrim": "N", "fracao_progressao": "1/6 - Comum", "fracao_livramento": "1/3 - Comum"}
    c.update(kw)
    return c


def reg(crimes, incs=(), eventos=(), **kw):
    r = {"nome": "Teste Ficticio", "regime_atual": "Fechado - ATIVO", "pena_total": "10a0m0d", "pena_cumprida": "3a0m0d", "pena_remanescente": "7a0m0d",
         "fracao_progressao_aplicada": "1/6", "data_geracao_rspe": "01/10/2026", "data_base_seeu": "01/03/2024", "_crimes": crimes,
         "_incidentes": list(incs), "_eventos": list(eventos), "data_nascimento": "01/01/1980"}
    r.update(kw)
    return r


def itens(r, tipo=None):
    its = ra.auditar(copy.deepcopy(r), HOJE)["aud_itens"]
    return [i for i in its if tipo is None or i.get("tipo") == tipo]


# ---- nascimento lido da ficha: o texto não manda informar nem diz que os pontos ficam a verificar ----
r = reg([crime()], data_nascimento="26/06/1997", _nasc_fonte="lida da ficha disciplinar do SIAPEN", _nasc_data="")
x = itens(r, "nascimento-nao-consta")
ok(len(x) == 1 and x[0]["nivel"] == "info" and "Informe a data" not in x[0]["detalhe"] and "A VERIFICAR" not in x[0]["detalhe"]
   and "26/06/1997" in x[0]["detalhe"], "nascimento da ficha: %s" % x)
x = itens(reg([crime()], data_nascimento=""), "nascimento-nao-consta")
ok(len(x) == 1 and x[0]["nivel"] == "verificar" and "Informe a data" in x[0]["detalhe"], "sem nascimento: continua pedindo: %s" % x)

# ---- artigo revogado antes do fato: informação, e o "confere" diz a capitulação provável ----
c217 = crime(artigo="ART 217: (Revogado pela Lei nº 11.106, de 2005)", tipo_penal="CAPUT: texto, Reclusão: 8 a 15 anos",
             pena_imposta="8 ano(s), 6 mês(es) e 0 dia(s)", data_infracao="19/08/2016", data_sentenca="10/06/2018", transito_mp="10/07/2018",
             transito_processo="10/07/2018", fracao_progressao="40% - Hediondo Primario", fracao_livramento="2/3 - Hediondo")
x = itens(reg([c217], pena_total="8a6m0d", fracao_progressao_aplicada="2/5"), "artigo-revogado-antes-do-fato")
ok(len(x) == 1 and x[0]["nivel"] == "info" and "2005" in x[0]["titulo"] and "217-A" in x[0]["detalhe"], "artigo revogado: %s" % x)
x = itens(reg([dict(c217, data_infracao="10/01/2004")], pena_total="8a6m0d"), "artigo-revogado-antes-do-fato")
ok(not x, "fato anterior à revogação: sem item: %s" % x)

# ---- recaptura lançada como "início do cumprimento" depois de fuga, sem falta reconhecida: data-base a verificar ----
evs = [ev(PR, "PRISÃO EM FLAGRANTE", "06/08/2022"), ev(PR, "INÍCIO DO CUMPRIMENTO REGIME SEMIABERTO", "06/07/2025"),
       ev("INTERRUPÇÃO", "FUGA", "15/07/2025", ""), ev(PR, "INÍCIO DO CUMPRIMENTO REGIME FECHADO", "11/09/2025")]
r = reg([crime(data_infracao="06/08/2022", data_sentenca="10/06/2025", transito_mp="10/06/2025", transito_processo="10/06/2025")],
        [inc(AR, "Semiaberto - Regime Inicial", "", "06/08/2022")], evs, data_base_seeu="11/09/2025")
x = itens(r, "data-base-movida-para-a-recaptura-sem-falta-homo")
ok(len(x) == 1 and x[0]["nivel"] == "verificar", "recaptura como início de cumprimento: %s" % x)
ok(not itens(r, "data-base-confere-com-o-rspe"), "sem 'confere' da data-base da recaptura sem falta")

# ---- livramento fora do tráfico: o fundamento não cita a Lei de Drogas ----
c16 = crime(lei="10.826/03 - Estatuto do Desarmamento", artigo="ART 16: Posse ou porte ilegal de arma de fogo de uso restrito",
            tipo_penal="CAPUT: texto, Reclusão: 3 a 6 anos", pena_imposta="4 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="19/03/2024",
            data_sentenca="10/06/2024", transito_mp="10/07/2024", transito_processo="10/07/2024", fracao_progressao="16% - Art.112, I, da LEP",
            fracao_livramento="2/3 - Hediondo")
x = [i for i in itens(reg([c16], pena_total="4a0m0d"), "fracao-de-livramento-diverge")]
ok(x and all("11.343" not in i["fundamento"] for i in x), "fundamento do livramento do porte de arma: %s" % [i["fundamento"] for i in x])

# ---- detração antes da fração: conta do SEEU em meses (44 m x 16% = 7m1d) e total somado em anos/meses/dias ----
c16b = crime(processo_criminal=P1, pena_imposta="3 ano(s), 8 mês(es) e 0 dia(s)", data_infracao="14/01/2022",
             fracao_progressao="16% - Art.112, I, da LEP")
c40 = crime(processo_criminal=P2, lei="11.343/06 - Lei de Drogas", artigo="ART 33: Tráfico de drogas", pena_imposta="8 ano(s), 9 mês(es) e 0 dia(s)",
            data_infracao="26/04/2024", fracao_progressao="40% - Art.112, V, da LEP")
evs = [ev(PR, "PRISÃO EM FLAGRANTE", "14/01/2022"), ev("INTERRUPÇÃO", "LIBERDADE PROVISÓRIA", "09/03/2022", ""),
       ev(PR, "PRISÃO EM FLAGRANTE", "26/04/2024", P2)]
r = reg([c16b, c40], [inc(AR, "Fechado - Regime Inicial", "", "26/04/2024")], evs, pena_total="12a5m0d", data_base_seeu="26/04/2024",
        progressao_previsao_seeu="01/01/2029",
        seeu_fracoes_progressao=["Primário sem violência ou grave ameaça (16%): 0a6m22d", "Hediondo primário (40%): 3a6m0d"])
bl = ra._detracao_blocos(r, r["_crimes"], 55)
ok(bl and [b[3] for b in bl if b[3]] == [55], "bloco de 16%% com 55 dias (não 72): %s" % bl)
x = itens(r, "regime-inicial-depois-da-primeira-prisao")
ok(len(x) == 1 and "55 dias" in x[0]["detalhe"] and "4 anos e 22 dias" in x[0]["detalhe"] and "1 mês e 16 dias" in x[0]["detalhe"],
   "contas pelo total impresso: %s" % [i["detalhe"][-400:] for i in x])

# ---- regime inicial: "sem efeito" só com data-base firme; data-base sem marco deixa o item condicionado ----
evs = [ev(PR, "PRISÃO EM FLAGRANTE", "12/11/2022"), ev("INTERRUPÇÃO", "LIBERDADE PROVISÓRIA", "28/01/2024", ""),
       ev(PR, "PRISÃO PREVENTIVA", "04/03/2024")]
cb = crime(data_infracao="12/11/2022", fracao_progressao="20% - Art.112, II, da LEP", reincidente_comum="S")
r = reg([cb], [inc(AR, "Fechado - Regime Inicial", "", "04/03/2024")], evs, data_base_seeu="26/02/2025", fracao_progressao_aplicada="1/5")
x = itens(r, "regime-inicial-depois-da-primeira-prisao")
ok(len(x) == 1 and x[0]["nivel"] == "verificar" and "se cair" in x[0]["detalhe"], "data-base sem marco: condicionado: %s" % x)
r2 = copy.deepcopy(r)
r2["_eventos"].append(ev(PR, "PRISÃO EM FLAGRANTE", "26/02/2025"))
x = itens(r2, "regime-inicial-depois-da-primeira-prisao")
ok(len(x) == 1 and x[0]["nivel"] == "info" and "sem efeito atual" in x[0]["titulo"], "data-base com prisão: sem efeito: %s" % x)

# ---- prisão definitiva (cumprimento de pena, com progressões) não é detração antes do regime inicial ----
evs = [ev(PR, "PRISÃO DEFINITIVA", "08/12/2011"), ev("INTERRUPÇÃO", "LIVRAMENTO CONDICIONAL", "06/09/2019", ""),
       ev(PR, "INÍCIO DO CUMPRIMENTO REGIME FECHADO", "01/08/2024")]
r = reg([crime(data_infracao="11/04/2010")], [inc(AR, "Semiaberto - Progressão de Regime", "19/01/2017", "06/09/2016"),
                                              inc(AR, "Fechado - Regime Inicial", "", "01/08/2024")], evs, data_base_seeu="01/08/2024")
ok(not itens(r, "regime-inicial-depois-da-primeira-prisao"), "prisão definitiva não é detração: %s" % itens(r, "regime-inicial-depois-da-primeira-prisao"))

# ---- livramento já concedido e nova prisão: "livramento possível" condicionado ao art. 88 ----
ct = crime(lei="11.343/06 - Lei de Drogas", artigo="ART 33: Tráfico de drogas", pena_imposta="6 ano(s), 0 mês(es) e 0 dia(s)",
           data_infracao="13/04/2014", data_sentenca="10/01/2015", transito_mp="10/02/2015", transito_processo="10/02/2015",
           reincidente_comum="S", reincidente_especifico="S", fracao_progressao="60% - Art.112, VII, da LEP",
           fracao_livramento="1/1 - Hediondo Reincidente/Reincidente Específico")
cant = crime(processo_criminal=P2, artigo="ART 121: Matar alguem", tipo_penal="§ 2º qualificado, Reclusão: 12 a 30 anos", pena_imposta="12 ano(s), 0 mês(es) e 0 dia(s)",
             data_infracao="11/04/2010", data_sentenca="10/03/2013", transito_mp="05/07/2013", transito_processo="05/07/2013",
             fracao_progressao="2/5 - Hediondo Primário", fracao_livramento="2/3 - Hediondo")
evs = [ev(PR, "PRISÃO DEFINITIVA", "08/12/2011"), ev("INTERRUPÇÃO", "LIVRAMENTO CONDICIONAL", "06/09/2019", ""),
       ev(PR, "INÍCIO DO CUMPRIMENTO REGIME FECHADO", "01/08/2024")]
r = reg([ct, cant], [inc("LIVRAMENTO CONDICIONAL", "Concessão", "29/08/2019", "06/09/2019")], evs, pena_total="18a0m0d", data_base_seeu="01/08/2024")
x = [i for i in itens(r, "fracao-de-livramento-diverge") if "art. 33" in i["titulo"]]
ok(x and all("art. 88" in i["detalhe"] and i["nivel"] != "alerta" for i in x), "livramento e nova prisão: art. 88: %s" % x)

# ---- remição de período anterior à progressão, lançada depois, com a contagem reiniciada por falta: informação ----
incs = [inc(AR, "Semiaberto - Progressão de Regime", "21/03/2022", "11/01/2022"),
        inc("REMIÇÃO", "12 Dias", "16/05/2022", "10/01/2022"),
        inc("HOMOLOGAÇÃO DE FALTA GRAVE", "Data do fato: 10/01/2024", "20/02/2024", "10/01/2024")]
r = reg([crime()], incs, [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2015")], data_base_seeu="10/01/2024")
x = [i for i in ra._lancamentos_seeu(r, r["_crimes"], r["_crimes"], r["_incidentes"], r["_eventos"]) if i["tipo"] == "remicao-preterita-apos-progressao"]
ok(len(x) == 1 and x[0]["nivel"] == "info" and "sem efeito atual" in x[0]["titulo"], "remição pretérita superada: %s" % x)
r2 = reg([crime()], incs[:2], [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2015")], data_base_seeu="11/01/2022")
x = [i for i in ra._lancamentos_seeu(r2, r2["_crimes"], r2["_crimes"], r2["_incidentes"], r2["_eventos"]) if i["tipo"] == "remicao-preterita-apos-progressao"]
ok(len(x) == 1 and x[0]["nivel"] == "verificar", "remição pretérita com efeito: pedir: %s" % x)

# ---- perda de remidos: não incide sobre remição decidida depois da perda; limite de 1/3 por falta ----
incs = [inc("REMIÇÃO", "327 Dias", "10/12/2023", "10/12/2023"),
        inc("HOMOLOGAÇÃO DE FALTA GRAVE", "Data do fato: 10/01/2024", "03/10/2024", "10/01/2024"),
        inc("DIAS PERDIDOS NA REMIÇÃO", "17 Dias", "03/10/2024", "03/10/2024"),
        inc("REMIÇÃO", "49 Dias", "12/09/2025", "12/09/2025")]
its = itens(reg([crime()], incs, saldo_remidos="359 dias (376 dias remidos - 17 dias perdidos)"))
ok([i for i in its if i["tipo"] == "perda-de-remidos-pela-falta-grave-de"], "perda de 17 dias analisada: %s" % [i["tipo"] for i in its])
ok(not [i for i in its if i["tipo"] == "perda-sobre-remicao-posterior-a-falta"], "perda sobre remição posterior à própria perda: %s" %
   [i["titulo"] for i in its if "erda" in i["titulo"]])
incs = [inc("REMIÇÃO", "89 Dias", "12/03/2019", "12/03/2019"),
        inc("DIAS PERDIDOS NA REMIÇÃO", "22 Dias", "21/05/2020", "21/05/2020"),
        inc("HOMOLOGAÇÃO DE FALTA GRAVE", "Data do fato: 10/07/2023", "04/04/2024", "10/07/2023"),
        inc("DIAS PERDIDOS NA REMIÇÃO", "22 Dias", "04/04/2024", "04/04/2024")]
its = itens(reg([crime()], incs, saldo_remidos="45 dias (89 dias remidos - 44 dias perdidos)"))
ok(not [i for i in its if i["tipo"] == "perdas-somadas-acima-de-1-3"] and
   [i for i in its if i["tipo"] == "perda-de-remidos-pela-falta-grave-de" and "saldo é 67" in i["detalhe"]],
   "limite de 1/3 por falta: %s" % [(i["tipo"], i["detalhe"]) for i in its if "erda" in i["titulo"]])

# ---- crime cometido em liberdade provisória, com o regime aberto nunca iniciado: não é falta da execução ----
evs = [ev(PR, "PRISÃO EM FLAGRANTE", "28/11/2021"), ev("INTERRUPÇÃO", "LIBERDADE PROVISÓRIA", "29/11/2021", ""),
       ev(PR, "PRISÃO EM FLAGRANTE", "08/10/2025", P2)]
cn = crime(processo_criminal=P2, artigo="ART 180: Receptação", data_infracao="08/10/2025", data_sentenca="", transito_mp="", transito_processo="")
x = rs.indicios_falta([inc(AR, "Aberto - Regime Inicial", "", "28/11/2021")], date(2026, 10, 1), eventos=evs, crimes=[cn],
                      inicio=date(2021, 11, 28), hoje=HOJE)
ok(not x, "crime em liberdade provisória antes de iniciar o aberto: %s" % x)
evs2 = [ev(PR, "PRISÃO EM FLAGRANTE", "28/11/2021"), ev(PR, "INÍCIO DO CUMPRIMENTO REGIME FECHADO", "01/02/2022")]
x = rs.indicios_falta([inc(AR, "Fechado - Regime Inicial", "", "28/11/2021")], date(2026, 10, 1), eventos=evs2, crimes=[cn],
                      inicio=date(2021, 11, 28), hoje=HOJE)
ok(x, "crime com a pena em cumprimento: indício mantido")

# ---- extinção da ficha com o número de outra execução já lida (só art. 28): não é base de reincidência ----
c_now = crime(processo_criminal=P1, data_infracao="09/01/2025", reincidente_comum="S", data_sentenca="", transito_mp="", transito_processo="")
c28 = crime(processo_criminal="0000512-79.2021.8.12.0052", lei="11.343/06 - Lei de Drogas", artigo="ART 28: Porte para consumo",
            data_infracao="10/01/2021", transito_processo="05/04/2022", extinto="Sim", _execucao="6004263-91.2022.8.12.0001")
ext = [{"processo": "6004263-91.2022.8.12.0001", "data": date(2023, 11, 7), "texto": "PENA EXTINTA"}]
R = rr.reincidencia_pelas_datas(c_now, [c_now, c28], extincoes=ext)
ok(R["estado"] != "reincidente" and not R["ficha"], "extinção de execução só do art. 28: %s" % R)
R = rr.reincidencia_pelas_datas(c_now, [c_now], extincoes=ext)
ok(R["estado"] == "reincidente" and R["fonte"] == "ficha", "extinção de execução desconhecida: indício mantido: %s" % R)

# ---- término de execução extinta: não "Interrompida" ----
r = reg([crime(extinto="Sim")], (), [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2015"), ev("INTERRUPÇÃO", "FUGA", "10/01/2016", "")],
        situacao_eventos="INTERROMPIDA", execucao_extinta="Sim", termino_previsao_seeu="")
ok(rv.termino(r) == "Pena extinta", "término da execução extinta: %s" % rv.termino(r))

# ---- ficha: soltura não lançada no RSPE; "Data Prisão" anterior a um alvará; saída para a comarca ----
ENT = "Entrada na Unidade Penal: PENITENCIARIA ESTADUAL FICTICIA, Procedente: DP CENTRO - INTERIOR, Conforme OF/CI 123/2018."
SAI = "Saída da Unidade Penal: PENITENCIARIA ESTADUAL FICTICIA, Destino: LIBERDADE, Motivo: ALVARÁ DE SOLTURA, Conforme AUTOS %s." % P1
f = {"eventos": [{"data": "18/01/2018", "texto": ENT}, {"data": "18/10/2018", "texto": SAI}, {"data": "03/04/2019", "texto": ENT}]}
r = reg([crime(data_infracao="15/01/2018")], (), [ev(PR, "PRISÃO EM FLAGRANTE", "15/01/2018"), ev(PR, "PRISÃO EM FLAGRANTE", "02/04/2019")])
sol = rf.solturas_nao_lancadas(r, f)
ok(sol == [(date(2018, 10, 18), date(2019, 4, 3))], "soltura não lançada: %s" % sol)
it = {"tipo": "regime-inicial-depois-da-primeira-prisao", "nivel": "alerta", "detalhe": "x.",
      "titulo": "Regime inicial lançado em 02/04/2019, depois da primeira prisão (15/01/2018)"}
rv._ajustar_regime_inicial_ficha([it], r, f)
ok(it["nivel"] == "verificar" and "277 dias" in it["detalhe"] and "favorável ao assistido" in it["detalhe"], "alerta com soltura na ficha: %s" % it)

ENT2 = "Entrada na Unidade Penal: PENITENCIARIA ESTADUAL FICTICIA, Procedente: DP NORTE - INTERIOR, Conforme OF/CI 99/2026."
SAI2 = "Saída da Unidade Penal: PENITENCIARIA ESTADUAL FICTICIA, Destino: LIBERDADE, Motivo: ALVARÁ DE SOLTURA, Conforme AUTOS 0009999-99.2026.8.12.0001."
f = {"data_prisao": "24/09/2026", "eventos": [{"data": "16/04/2026", "texto": ENT2}, {"data": "24/09/2026", "texto": SAI2},
                                              {"data": "01/10/2026", "texto": ENT2}]}
r = reg([crime(data_infracao="26/05/2021")], (), [ev(PR, "PRISÃO EM FLAGRANTE", "26/05/2021"), ev("INTERRUPÇÃO", "LIBERDADE PROVISÓRIA", "27/08/2021", "")])
av = rf.reconciliar_eventos(r, f)
ent = [d.get("entrada") for t, d in av if t == "reinicio-a-conferir"]
ok(ent == [date(2026, 10, 1)], "nova prisão = entrada depois do alvará, não a Data Prisão: %s" % av)

SAI3 = "Saída da Unidade Penal: PENITENCIARIA ESTADUAL FICTICIA, Destino: COMARCA DE ORIGEM, Motivo: Progressão na Cidade de Origem, Conforme Ofício: AUTOS%s." % P1
f = {"eventos": [{"data": "08/11/2021", "texto": ENT2}, {"data": "07/02/2022", "texto": SAI3}, {"data": "12/05/2026", "texto": ENT2}]}
cl = rf.custodia_ficha_processo(reg([crime()]), f, date(2021, 11, 8))
ok(cl and cl["tipo"] == "desta" and cl.get("saida") and cl["saida"][0] == "07/02/2022", "custódia desta execução com saída: %s" % cl)

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for m in falhas:
        print(" -", m)
    sys.exit(1)
print("ok: conferência 2 (7.14.1) - frente Auditoria")
