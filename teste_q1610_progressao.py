"""Teste dos quesitos de 16/10/2026, grupo "progressão" (itens 31 a 36, 39 a 42, 162 e 163): reincidência crime a crime como tese
defensiva (não "fração legal"), reincidência pelas datas sem marcação em "info" e nota no indulto, marcado reincidente sem condenação
anterior em "verificar", homicídio simples com selo de hediondo a verificar (progressão, livramento e indulto), lei nova (Lei 15.358)
e Lei 15.402 em "verificar", feminicídio sem morte ou tentado a verificar, livramento e crime culposo, Tema 1196 com a nota do
recurso extraordinário sobrestado, progressão refeita com 16% e ancorada na previsão do SEEU.
Rodar: python teste_q1610_progressao.py"""
import json
import os
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_auditoria as ra
import rspe_decretos as rd
import rspe_indulto_tl as tl
import rspe_scraper as rs
import rspe_view as rv

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


CP = "2848/40 - Código Penal"


def crime(proc, artigo, tipo, fato, transito, prog, liv, reinc="N", vga="N", morte="N", lei=CP, pena="8 ano(s), 0 mês(es) e 0 dia(s)", esp="N"):
    return {"processo_criminal": proc, "lei": lei, "artigo": artigo, "tipo_penal": tipo, "data_infracao": fato,
            "transito_processo": transito, "transito_mp": transito, "data_sentenca": "", "pena_imposta": pena,
            "vga": vga, "resultado_morte": morte, "reincidente_comum": reinc, "reincidente_especifico": esp, "comando_orcrim": "N",
            "fracao_progressao": prog, "fracao_livramento": liv, "extinto": "Não"}


def reg(crimes):
    return {"nome": "PESSOA FICTICIA", "processo_execucao": "9990000-00.2026.8.12.0001", "pena_total": "16a0m0d",
            "_crimes": crimes, "_eventos": [{"tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO DEFINITIVA", "data": "01/01/2025"}],
            "_incidentes": []}


def itens(r, tipo=None):
    out = ra.auditar(r, date(2026, 10, 16))["aud_itens"]
    return [i for i in out if tipo is None or i.get("tipo") == tipo]


FURTO = ("ART 155: Furto", "§ 4º: furto qualificado, Reclusão: 2 a 8 anos E Multa")
ROUBO = ("ART 157: Roubo", "§ 2º, II: concurso de pessoas, Reclusão: 4 a 10 anos E Multa")

# 31 - fato anterior ao primeiro trânsito, outro crime reincidente: 1/2 do SEEU vira tese defensiva (verificar), não alerta
a = crime("0000001-00.2015.8.12.0001", *FURTO, "01/01/2015", "01/01/2016", "1/6 - Comum", "1/2 - Comum Reincidente")
b = crime("0000002-00.2018.8.12.0001", *FURTO, "01/01/2018", "01/01/2019", "1/6 - Comum", "1/2 - Comum Reincidente", reinc="S")
r = reg([a, b])
it = itens(r)
t31 = [i for i in it if i["tipo"] == "reincidencia-crime-a-crime-livramento"]
ok(len(t31) == 1 and t31[0]["nivel"] == "verificar" and "tese defensiva" in t31[0]["titulo"] and "790.968" in t31[0]["detalhe"], "31 livramento: %s" % t31)
ok(not [i for i in it if i["tipo"] == "fracao-de-livramento-diverge" and i["nivel"] == "alerta"], "31: sem alerta de fração legal")
ok(ra.fundamentacao(t31[0], r) and "1/3" in ra.fundamentacao(t31[0], r), "31: fundamentação da tese")
# o mesmo 1/2 sem nenhum crime reincidente na execução: continua alerta
r = reg([crime("0000001-00.2015.8.12.0001", *FURTO, "01/01/2015", "01/01/2016", "1/6 - Comum", "1/2 - Comum Reincidente")])
ok([i for i in itens(r) if i["tipo"] == "fracao-de-livramento-diverge" and i["nivel"] == "alerta"], "31: sem reincidência na execução, alerta")
# progressão: 20% de reincidente em fato anterior ao primeiro trânsito
a = crime("0000003-00.2021.8.12.0001", *FURTO, "01/03/2021", "01/03/2022", "20% - Art.112, II, da LEP", "1/2 - Comum Reincidente")
b = crime("0000004-00.2023.8.12.0001", *FURTO, "01/03/2023", "01/03/2024", "20% - Art.112, II, da LEP", "1/2 - Comum Reincidente", reinc="S")
t = itens(reg([a, b]), "reincidencia-crime-a-crime-progressao")
ok(len(t) == 1 and t[0]["nivel"] == "verificar" and "16%" in t[0]["titulo"], "31 progressão: %s" % t)

# 32 - reincidência pelas datas sem marcação: info (a fração de primário favorece o assistido)
a = crime("0000005-00.2015.8.12.0001", *FURTO, "01/01/2015", "01/01/2016", "1/6 - Comum", "1/3 - Comum Primário")
b = crime("0000006-00.2018.8.12.0001", *FURTO, "01/01/2018", "01/01/2019", "1/6 - Comum", "1/3 - Comum Primário")
t = itens(reg([a, b]), "reincidente-pela-lei-sem-marcacao")
ok(len(t) == 1 and t[0]["nivel"] == "info" and "juízo pode recalcular" in t[0]["detalhe"], "32: %s" % t)
ok(rd._reinc_pelas_datas([b], [a, b]) and not rd._reinc_pelas_datas([a], [a, b]), "32: reincidência pelas datas no indulto")

# 33 - marcado reincidente sem condenação anterior: verificar
a = crime("0000007-00.2018.8.12.0001", *FURTO, "01/01/2018", "01/01/2019", "1/6 - Comum", "1/2 - Comum Reincidente", reinc="S")
t = itens(reg([a]), "marcado-reincidente-sem-condenacao-anterior-tran")
ok(len(t) == 1 and t[0]["nivel"] == "verificar", "33: %s" % t)

# 34 - homicídio qualificado sem a marca de morte, 50% do SEEU: verificar (consumado), não alerta
a = crime("0000008-00.2014.8.12.0001", "ART 121: Matar alguem", "§ 2º: Se o homicídio é cometido: I - mediante paga", "23/11/2014",
          "01/01/2016", "50% - Art.112, VI, da LEP", "2/3 - Hediondo", reinc="S")
it = itens(reg([a]))
ok([i for i in it if i["tipo"] == "percentual-homicidio-consumacao-a-conferir" and i["nivel"] == "verificar"], "34: verificar")
ok(not [i for i in it if i["tipo"] == "percentual-de-progressao-diverge" and i["nivel"] == "alerta"], "34: sem alerta")

# 35 - homicídio simples com o selo de hediondo: verificar na progressão/livramento e a verificar no indulto
hs = crime("0000009-00.2015.8.12.0001", "ART 121: Matar alguem", "CAPUT: Matar alguém., Reclusão: 6 a 20 anos Sem Multa", "05/04/2015",
           "01/01/2016", "2/5 - Hediondo Primario", "2/3 - Hediondo")
it = itens(reg([hs]))
ok([i for i in it if i["tipo"] == "homicidio-simples-com-selo-de-hediondo" and i["nivel"] == "verificar"], "35: item verificar")
ok(not [i for i in it if i["nivel"] == "alerta" and i["tipo"] in ("seeu-tratou-como-hediondo-mas-o-tipo-nao-consta", "percentual-de-progressao-diverge",
                                                                   "fracao-de-livramento-diverge")], "35: sem alerta: %s" % [i["titulo"] for i in it if i["nivel"] == "alerta"])
ok(rs.homicidio_simples_selo(hs) and not rs.homicidio_simples_selo(a), "35: homicidio_simples_selo")
inc = []
ok(not rd._impeditivos({"impeditivos": {}}, [hs], date(2019, 12, 25), incerto=inc) and inc, "35: indulto a verificar (tabela)")
ok(rd._impeditivos({"impeditivos": {}, "_hom_selo_imp": True}, [hs], date(2019, 12, 25), incerto=[]), "35: com o selo, impeditivo")
n = tl.natureza(hs, {"numero": "12.338/2024", "vedacoes": {"regra": "art1_2024_2025"}}, date(2024, 12, 25))
ok(n["selo"] == "A_VERIFICAR" and "extermínio" in n["motivo"], "35: linha do tempo %s" % n)

# 36 - reincidência específica não demonstrada em fato da Lei 15.358/2026: verificar; antes dela, alerta
tr = ("ART 33: Tráfico", "CAPUT: Importar, exportar, remeter, preparar, Reclusão: 5 a 15 anos E Multa")
a = crime("0000010-00.2026.8.12.0001", *tr, "01/05/2026", "01/09/2026", "80% - Art.112, VII, da LEP", "1/1 - Hediondo Reincidente/Reincidente Específico",
          lei="11343/06 - Lei de Drogas", esp="S")
t = itens(reg([a]), "reincidencia-especifica-nao-demonstrada-no-rspe")
ok(len(t) == 1 and t[0]["nivel"] == "verificar", "36 lei nova: %s" % t)
ok(not [i for i in itens(reg([a])) if i["nivel"] == "alerta" and i["tipo"] in ra._TIPOS_FRACAO], "36: frações no mesmo item")
a = crime("0000011-00.2021.8.12.0001", *tr, "01/05/2021", "01/09/2021", "60% - Art.112, VII, da LEP", "1/1 - Hediondo Reincidente/Reincidente Específico",
          lei="11343/06 - Lei de Drogas", esp="S")
t = itens(reg([a]), "reincidencia-especifica-nao-demonstrada-no-rspe")
ok(len(t) == 1 and t[0]["nivel"] == "alerta", "36 60%% após 2020 continua alerta: %s" % t)
# reincidente genérico (específico não marcado) com 80% em fato desde 25/03/2026: verificar
ant = crime("0000012-00.2020.8.12.0001", *FURTO, "01/01/2020", "01/01/2021", "16% - Art.112, I, da LEP", "1/3 - Comum Primário")
a = crime("0000013-00.2026.8.12.0001", *tr, "01/05/2026", "01/09/2026", "80% - Art.112, VII, da LEP", "2/3 - Hediondo", lei="11343/06 - Lei de Drogas", reinc="S")
t = [i for i in itens(reg([ant, a]), "percentual-de-progressao-diverge") if i["ref"] == ra._nome(a)]
ok(t and t[0]["nivel"] == "verificar" and "sem precedente específico" in t[0]["detalhe"], "36 genérico: %s" % t)

# 39 - Lei 15.402/2026: 30% do SEEU a reincidente em crime sem violência - verificar com a tese dos 20%
ant = crime("0000014-00.2020.8.12.0001", *ROUBO, "01/01/2020", "01/01/2021", "25% - Art.112, III, da LEP", "1/3 - Comum Primário", vga="S")
a = crime("0000015-00.2026.8.12.0001", *FURTO, "10/05/2026", "01/09/2026", "30% - Art.112, II, da LEP", "1/2 - Comum Reincidente", reinc="S")
t = [i for i in itens(reg([ant, a]), "percentual-de-progressao-diverge") if i["ref"] == ra._nome(a)]
ok(t and t[0]["nivel"] == "verificar" and "20%" in t[0]["detalhe"], "39: %s" % t)

# 40 - feminicídio sem a marca de morte (ou tentado): verificar com a tese do hediondo sem morte
fem = crime("0000016-00.2025.8.12.0001", "ART 121-A: Feminicídio", "CAPUT: Matar mulher por razões da condição do sexo feminino", "01/06/2025",
            "01/12/2025", "55% - Art.112, VI-A, da LEP", "1/1 - Hediondo Reincidente/Reincidente Específico", vga="S")
it = itens(reg([fem]))
t = [i for i in it if i["tipo"] == "feminicidio-consumacao-a-conferir"]
ok(t and t[0]["nivel"] == "verificar" and "40%" in t[0]["titulo"] and "2/3" in t[0]["detalhe"], "40: %s" % t)
ok(not [i for i in it if i["nivel"] == "alerta" and i["tipo"] in ra._TIPOS_FRACAO], "40: sem alerta")
ft = dict(fem, resultado_morte="S", tipo_penal="CAPUT: Matar mulher ... c/c art. 14, II (tentado)")
ok(ra._tentado(ft) and not ra._tentado(crime("x", "ART 214: Atentado violento ao pudor", "CAPUT", "", "", "", "")), "40: tentativa lida no tipo")
ok([i for i in itens(reg([ft])) if i["tipo"] == "feminicidio-consumacao-a-conferir"], "40: tentado com morte marcada")
ok(not [i for i in itens(reg([dict(fem, resultado_morte="S")])) if i["tipo"] == "feminicidio-consumacao-a-conferir"], "40: consumado sem item")

# 41 - Tema 1196: tese firmada, com a nota do recurso extraordinário sobrestado
hm = crime("0000017-00.2022.8.12.0001", "ART 121: Matar alguem", "§ 2º: Se o homicídio é cometido: I - mediante paga", "10/12/2022", "01/12/2023",
           "50% - Art.112, VI, da LEP", "1/1 - Hediondo Reincidente/Reincidente Específico", morte="S")
t = itens(reg([hm]), "hediondo-com-resultado-morte-fato-em-livramento")
ok(t and "sobrestado até o julgamento do Tema 1319" in t[0]["detalhe"], "41 auditoria: %s" % t)
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "base_juridica.json"), encoding="utf-8") as f:
    bj = json.load(f)
ok("sobrestado" in bj["livramento"]["vedado_lc_lep112"] and any("Tema 1196" in j.get("fonte", "") and "sobrestado" in j["fonte"] for j in bj["jurisprudencia"]),
   "41 base jurídica")

# 42 - livramento 1/2 com crime atual culposo ou condenação anterior só culposa: verificar com a tese de 1/3
ctb = crime("0000018-00.2019.8.12.0001", "ART 303: Lesão corporal culposa na direção de veículo automotor", "CAPUT: Praticar lesão corporal culposa",
            "28/04/2019", "01/01/2020", "1/6 - Comum", "1/2 - Comum Reincidente", reinc="S", lei="9503/97 - CTB (Código de Trânsito Brasileiro)")
t = itens(reg([ctb]), "livramento-reincidencia-em-crime-culposo")
ok(t and t[0]["nivel"] == "verificar" and "crime atual culposo" in t[0]["titulo"], "42 atual: %s" % t)
ant = dict(ctb, processo_criminal="0000019-00.2015.8.12.0001", data_infracao="01/01/2015", transito_processo="01/01/2016", transito_mp="01/01/2016",
           reincidente_comum="N", fracao_livramento="1/3 - Comum Primário")
a = crime("0000020-00.2018.8.12.0001", *FURTO, "01/01/2018", "01/01/2019", "1/6 - Comum", "1/2 - Comum Reincidente", reinc="S")
t = [i for i in itens(reg([ant, a]), "livramento-reincidencia-em-crime-culposo") if i["ref"] == ra._nome(a)]
ok(t and "anterior só por crime culposo" in t[0]["titulo"], "42 anterior: %s" % t)
ok(not itens(reg([dict(ant, processo_criminal="0000021-00.2015.8.12.0001", lei=CP, artigo=FURTO[0], tipo_penal=FURTO[1]), a]),
             "livramento-reincidencia-em-crime-culposo"), "42: anterior doloso, sem item")

# 162 - progressão refeita: 16% no lugar do 1/6 até o fim da janela da Lei 13.964/2019 (retroativo); depois dela, a fração literal
ok(rv._fr_prog_refeita({"fracao_progressao": "1/6 - Comum", "data_infracao": "01/06/2023"}) == rs.Fraction(16, 100), "162: 16%")
# (7.14.8, S3040) fato anterior a 2020: os 16% da Lei 13.964/2019 são mais benéficos e retroagem (CF, art. 5º, XL), como diz a Auditoria
ok(rv._fr_prog_refeita({"fracao_progressao": "1/6 - Comum", "data_infracao": "01/06/2015"}) == rs.Fraction(16, 100), "162: 16% retroativo antes de 2020")
ok(rv._fr_prog_refeita({"fracao_progressao": "1/6 - Art.112, caput, da LEP", "data_infracao": "10/05/2026"}) == rs.Fraction(1, 6), "162: 1/6 da Lei 15.402")

# 163 - ancorada na previsão do SEEU: nunca depois dela deslocada pela diferença das datas-base
r = {"pena_total": "6a0m0d", "data_base_seeu": "01/01/2025", "progressao_previsao_seeu": "19/10/2025", "_db_manual": "01/07/2024",
     "_crimes": [{"fracao_progressao": "16% - Art.112, I, da LEP", "pena_imposta": "6 ano(s), 0 mês(es) e 0 dia(s)", "data_infracao": "01/06/2023", "extinto": "Não"}],
     "_eventos": [{"tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "data": "01/01/2024"}], "_incidentes": []}
ok(rv._prog_pela_db_manual(r) == date(2025, 5, 18), "163: conta igual à do SEEU: %s" % rv._prog_pela_db_manual(r))
# eventos que dão custódia a menos (conta independente pior): a data fica na âncora, antes da previsão do SEEU
r2 = dict(r, _eventos=[{"tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "data": "01/06/2024"}])
v = rv._prog_pela_db_manual(r2)
ok(v and v <= date(2025, 5, 18) and v < date(2025, 10, 19), "163: âncora %s" % v)
ok(rv._ancora(date(2024, 7, 1), date(2025, 1, 1), date(2025, 10, 19), rs.Fraction(16, 100), []) == date(2025, 5, 18), "163: âncora")

if falhas:
    print("FALHOU:")
    for x in falhas:
        print("  -", x)
    sys.exit(1)
print("ok: quesitos de 16/10 - progressão (reincidência crime a crime como tese, reincidência pelas datas, homicídio simples com selo, "
      "lei nova e Lei 15.402 a verificar, feminicídio tentado, Tema 1196, livramento e culposo, progressão refeita com 16% e âncora)")
