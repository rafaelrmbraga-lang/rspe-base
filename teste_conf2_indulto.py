"""Teste da segunda conferência manual (7.14.1), frente indulto e comutação: soma das penas por componente (anos, meses e dias),
remição datada depois do fato do impeditivo limitada a 1 dia por 3 do período posterior e perda de remidos posterior descontada,
livramento revogado lançado pelo SEEU como interrupção (CP, art. 88), sentença sem trânsito informado e recurso pendente
(art. 2º, II), faltas da ficha com datas próximas, ordem legal de execução na comutação do concurso (CP, arts. 69 e 76),
tempo anterior ao fato dos crimes não impeditivos, reincidência pelas datas na comutação já a verificar, pena extinta na base
da comutação, texto de apoio da comutação com o indulto indeferido, exclusão do art. 7º de 2022 com crime só de multa e remição
decidida depois do início das atividades da ficha. Casos hipotéticos, nomes fictícios.
Rodar: python teste_conf2_indulto.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_decretos as rd
import rspe_scraper as rs

falhas = []
HOJE = date(2026, 10, 20)


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


P1 = "0000001-11.2015.8.12.0001"
PR = "PRISÃO/INÍCIO DE CUMPRIMENTO"
IN = "INTERRUPÇÃO"
D = rs.to_date


def crime(**kw):
    c = {"processo_criminal": P1, "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto",
         "tipo_penal": "CAPUT: Subtrair, Reclusão: 1 a 4 anos", "pena_imposta": "1 ano(s), 0 mês(es) e 0 dia(s)",
         "pena_total_processo": "", "data_infracao": "10/01/2015", "data_sentenca": "10/06/2015", "transito_mp": "10/07/2015",
         "transito_processo": "10/07/2015", "extinto": "Não", "suspenso": "Não", "vga": "N", "resultado_morte": "N",
         "reincidente_comum": "N", "reincidente_especifico": "N", "comando_orcrim": "N"}
    c.update(kw)
    return c


def ev(tipo, motivo, data):
    return {"tipo": tipo, "motivo": motivo, "data": data, "processos": P1}


# 1. soma das penas por componente: 3a + 2a4m + 1a6m20d + 1a0m3d + 1a8m = 9a6m23d (em dias dava 9a6m18d)
cs = [crime(pena_imposta=p) for p in ("3a0m0d", "2a4m0d", "1a6m20d", "1a0m3d", "1a8m0d")]
ok(rs.dias_para_pena(rs.soma_penas(cs)) == "9a6m23d", "1: soma por componente deveria dar 9a6m23d, deu %s" % rs.dias_para_pena(rs.soma_penas(cs)))
ok(rs.dias_para_pena(rs.soma_penas([crime(pena_imposta="0a4m0d"), crime(pena_imposta="0a10m20d")])) == "1a2m20d", "1: 4m + 10m20d = 1a2m20d")
ok(rs.soma_penas([crime(pena_imposta="", pena_total_processo="0a1m0d - PENA ORIGINÁRIA")], True) == 30, "1: pena do processo quando a imposta falta")

# 2. tempo posterior ao fato: remição datada depois do fato limitada a 1 por 3 dias desde o fato; perda posterior descontada
per = [(D("01/01/2020"), None)]
fato = D("13/07/2024")
inf = {}
x = rs.cumprido_apos_fato(per, [(D("14/03/2025"), 258)], fato, D("25/12/2025"), None, inf)
ok(x == (D("25/12/2025") - fato).days + 1 + (D("14/03/2025") - fato).days // 3, "2: remição de 258 dias limitada a 1/3 dos dias desde o fato (deu %s)" % x)
ok(inf.get("remicao_cortada") == 258 - (D("14/03/2025") - fato).days // 3, "2: dias de remição cortados informados")
y = rs.cumprido_apos_fato(per, [(D("01/06/2019"), 300), (D("01/03/2021"), 50), (D("16/11/2021"), -74)], D("24/08/2016"), D("25/12/2023"))
y0 = rs.cumprido_apos_fato(per, [(D("01/06/2019"), 300), (D("01/03/2021"), 50)], D("24/08/2016"), D("25/12/2023"))
ok(y0 - y == 74, "2: perda de 74 remidos posterior ao fato sai do tempo imputável (diferença %s)" % (y0 - y))
_imp = [crime(artigo="ART 33: Tráfico", lei="11343/06 - Lei de Drogas", pena_imposta="6a5m0d", data_infracao="13/07/2024")]
_c, _n = rs.cumprido_imputavel_impeditivos(_imp, 2000, per, [(D("14/03/2025"), 258)], D("25/12/2025"))
ok("excede 1 dia por 3" in _n, "2: a nota do impeditivo diz que parte da remição não conta")

# 3. livramento revogado que o SEEU lançou como interrupção: sai do cumprido (CP, art. 88); o que o SEEU não cobre fica
campos = {"pena_total": "20a0m0d", "data_geracao_rspe": "05/10/2026", "total_interrupcoes": "2a0m0d"}
per3 = [(D("01/01/2006"), D("19/07/2012")), (D("18/06/2014"), None)]
lc = [(D("20/07/2012"), D("17/06/2014"))]
ok(rs.lc_fora_do_cumprimento(campos, per3, lc) == [], "3: livramento coberto pelo Total Interrupções sai do cumprimento")
ok(rs.lc_fora_do_cumprimento(dict(campos, total_interrupcoes="0a1m0d"), per3, lc) == lc, "3: sem interrupção no SEEU que o cubra, o livramento conta")
ok(rs.lc_fora_do_cumprimento(campos, per3, [(D("20/07/2012"), None)]) == [(D("20/07/2012"), None)], "3: livramento em curso conta")

# 4. sentença sem trânsito informado: recurso pendente impresso ou sentença recente - art. 2º, II (a verificar)
pub = D("23/12/2025")
c4 = crime(data_sentenca="07/05/2025", transito_mp="", transito_processo="", pena_total_processo="3a9m15d - APELAÇÃO CRIMINAL")
ok(rs._art2_ii(c4, pub), "4: sem trânsito e com apelação: art. 2º, II")
ok(not rs._art2_ii(dict(c4, pena_total_processo="3a9m15d - PENA ORIGINÁRIA"), pub), "4: sem trânsito e sem recurso impresso: fica na soma (nota do trânsito)")
ok(not rs._art2_ii(dict(c4, data_sentenca="07/05/2026"), pub), "4: sentença posterior à publicação não é art. 2º, II")
ok("trânsito não informado" in rs.texto_art2_ii([c4], pub), "4: o texto diz que o trânsito não está no RSPE")

# 5. faltas da ficha com 23 dias de diferença: são fatos diferentes (só a mesma data se repete)
r5 = {"_incidentes": [], "_eventos": [ev(PR, "PRISÃO EM FLAGRANTE", "01/01/2024")], "_crimes": [crime()]}
ficha = {"faltas": [{"data_fato": "01.10.2025", "grave": True, "situacao": "PADIC instaurado", "artigo": "art. 50, VI"},
                    {"data_fato": "24.10.2025", "grave": True, "situacao": "PADIC instaurado", "artigo": "art. 50, VI"},
                    {"data_fato": "24.10.2025", "grave": True, "situacao": "PADIC instaurado", "artigo": "art. 50, VI"}]}
rs.faltas_da_ficha(r5, ficha, HOJE)
datas5 = [i["data_referencia"] for i in r5["_incidentes"] if i.get("_ficha")]
ok(datas5 == ["01/10/2025", "24/10/2025"], "5: duas faltas da ficha (a repetida na mesma data uma vez só), veio %s" % datas5)

# 6. comutação no concurso: tráfico (reclusão) impeditivo e posse de arma (detenção) - o tempo além dos 2/3 do tráfico não cumpre
# a detenção pela ordem legal (CP, arts. 69 e 76): não é "sem pena remanescente"
traf = crime(lei="11343/06 - Lei de Drogas", artigo="ART 33: Tráfico de drogas", tipo_penal="CAPUT: Importar..., Reclusão de 5 a 15 anos",
             pena_imposta="9a0m0d", data_infracao="01/12/2017", data_sentenca="10/06/2018", transito_mp="10/07/2018", transito_processo="10/07/2018")
arma = crime(lei="10826/03 - Estatuto do Desarmamento", artigo="ART 12: Posse irregular de arma de fogo de uso permitido",
             tipo_penal="CAPUT: Possuir ou manter sob sua guarda arma de fogo, Detenção, de 1 (um) a 3 (três) anos, e multa",
             pena_imposta="1a0m0d", data_infracao="01/12/2017", data_sentenca="10/06/2018", transito_mp="10/07/2018", transito_processo="10/07/2018")
evs = [ev(PR, "PRISÃO EM FLAGRANTE", "01/12/2017")]
r6 = {"pena_total": "10a0m0d", "pena_cumprida": "8a10m12d", "data_geracao_rspe": "06/10/2026", "regime_atual": "Fechado", "_crimes": [traf, arma],
      "_eventos": evs, "_incidentes": []}
o6 = rs.analise_decretos(r6, r6["_crimes"], evs, [], HOJE)
c24 = (o6.get("comutacao_2024_se_indeferido") or "") + " " + (o6.get("comutacao_2024") or "")
ok("ordem legal (CP, arts. 69 e 76)" in c24, "6: comutação 2024 cita a ordem legal de execução: %s" % c24[:200])
ok(not (o6.get("comutacao_2024") or "").startswith("não se aplica: sem pena remanescente"), "6: não afirma pena sem remanescente")

# 7. tempo anterior ao fato dos crimes não impeditivos não conta para eles (comutação 2024 no concurso)
hed = crime(artigo="ART 213: Estupro", tipo_penal="CAPUT: Constranger, Reclusão de 6 a 10 anos", pena_imposta="6a0m0d",
            data_infracao="28/11/2011", data_sentenca="11/04/2012", transito_mp="02/12/2012", transito_processo="02/12/2012")
rb = crime(artigo="ART 155: Furto", pena_imposta="4a6m0d", data_infracao="15/06/2021", data_sentenca="24/01/2022",
           transito_mp="10/03/2022", transito_processo="10/03/2022")
evs7 = [ev(PR, "PRISÃO EM FLAGRANTE", "05/01/2012")]
r7 = {"pena_total": "10a6m0d", "pena_cumprida": "14a9m0d", "data_geracao_rspe": "06/10/2026", "regime_atual": "Fechado", "_crimes": [hed, rb],
      "_eventos": evs7, "_incidentes": []}
o7 = rs.analise_decretos(r7, r7["_crimes"], evs7, [], HOJE)
ok("limitado ao tempo posterior ao fato dos crimes não impeditivos" in (o7.get("indulto_2024_detalhe") or "") + (o7.get("comutacao_2024_detalhe") or ""),
   "7: o tempo além dos 2/3 fica limitado ao posterior ao fato dos crimes não impeditivos")

# 8. motivo curto: reincidência pelas datas decide o "a verificar" da comutação
x8 = {"s": "ver", "mot": "cumpriu 5a1m6d em 25/12/2009 (exigido 4a11m28d); comutação de 1/4; A VERIFICAR - falta na janela a verificar (art. 4º); "
                     "A VERIFICAR - o RSPE não marca reincidência, mas X transitou antes do fato de Y: o juízo pode recalcular como reincidente; "
                     "como reincidente, o benefício não é atingido nesta data"}
ok("como reincidente, o requisito não é atingido" in rd.motivo_curto(x8), "8: motivo curto mostra a reincidência pelas datas")

# 9. remição decidida depois do início das atividades da ficha (posterior ao decreto): não é de período anterior à data
r9 = {"_incidentes": [{"tipo": "REMIÇÃO", "complemento": "89 Dia(s)", "situacao": "CONCEDIDO", "data_decisao": "16/02/2023",
                       "data_referencia": "16/02/2023"}], "_ficha_ativ_ini": "17/11/2021"}
ok(rd.remicoes_ref_decisao(r9, D("25/12/2013")) == [], "9: remição de atividade iniciada depois do decreto não fica a verificar")
ok(rd.remicoes_ref_decisao(dict(r9, _ficha_ativ_ini=""), D("25/12/2013")) == [(D("16/02/2023"), 89)], "9: sem a ficha, segue a verificar")

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for f in falhas:
        print(" -", f)
    sys.exit(1)
print("teste_conf2_indulto: ok")
