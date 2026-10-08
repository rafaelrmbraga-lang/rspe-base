"""Teste de regressão dos alertas corrigidos na revisão de 08.10 (progressão/livramento e confronto RSPE x ficha): feminicídio
aumentado e art. 217 revogado como hediondos, reincidência específica não demonstrada (2007-2020), data-base na recaptura após
fuga, contravenção sem reincidência, porte para consumo, soma com guia suspensa, regime inicial sem efeito, idade impossível,
remição em duplicidade e, na ficha, fuga de outra execução, retorno de evasão, alvará na data da fuga e identidade por grafia.
2ª rodada (A1-A16): data-base favorável sem pedido, porte sem prisão efetiva, progressão/regressão da ficha já no RSPE, mais de um
regime inicial com liberdade ou superado, prisão anterior aos fatos, regime inicial sem efeito, aberto/livramento, falta "a apurar"
da própria sanção, pena acima do máximo do tipo, capitulação sem efeito, um alerta por erro, data-base no fato do novo crime,
rótulo do dispositivo, HC 1.032.430 e data-base do livramento.
Rodar: python teste_auditoria_revisao.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_auditoria as ra
import rspe_ficha as rf

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def inc(tipo, compl, dec, ref, sit="CONCEDIDO"):
    return {"tipo": tipo, "motivo": "", "complemento": compl, "data": "", "data_decisao": dec, "data_referencia": ref, "processos": "", "situacao": sit}


def ev(tipo, motivo, data, procs="0000001-11.2020.8.12.0001"):
    return {"tipo": tipo, "motivo": motivo, "data": data, "processos": procs}


def crime(**kw):
    c = {"processo_criminal": "0000001-11.2020.8.12.0001", "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto",
         "tipo_penal": "CAPUT: Subtrair, Reclusão: 1 a 4 anos", "pena_imposta": "10 ano(s), 0 mês(es) e 0 dia(s)",
         "data_infracao": "10/01/2020", "data_sentenca": "10/06/2020", "transito_mp": "10/07/2020", "transito_processo": "10/07/2020",
         "extinto": "Não", "suspenso": "Não", "vga": "N", "resultado_morte": "N", "reincidente_comum": "N", "reincidente_especifico": "N",
         "comando_orcrim": "N", "fracao_progressao": "16% - Art.112, I, da LEP", "fracao_livramento": "1/3 - Comum"}
    c.update(kw)
    return c


def reg(crimes, incs=(), eventos=(), **kw):
    r = {"nome": "Teste", "regime_atual": "Fechado - ATIVO", "pena_total": "10a0m0d", "pena_cumprida": "3a0m0d", "pena_remanescente": "7a0m0d",
         "fracao_progressao_aplicada": "2/5", "data_geracao_rspe": "01/10/2026", "data_base_seeu": "01/03/2024", "_crimes": crimes,
         "_incidentes": list(incs), "_eventos": list(eventos)}
    r.update(kw)
    return r


def itens(r):
    return ra.auditar(r, date(2026, 10, 1))["aud_itens"]


def tipos(r, nivel=None):
    return [i["tipo"] for i in itens(r) if not nivel or i["nivel"] == nivel]


# 1. feminicídio aumentado (art. 121, § 7º) com morte: hediondo - 50% e livramento vedado estão certos
fem = crime(artigo="ART 121: Matar alguem:", tipo_penal="§ 7º: Feminicídio aumentado:, Reclusão: 16 a 45 anos", data_infracao="08/09/2023",
            vga="S", resultado_morte="S", fracao_progressao="50% - Art.112, VI, da LEP", fracao_livramento="1/1 - Hediondo Reincidente/Reincidente Específico")
t = tipos(reg([fem]), "alerta")
ok(not {"percentual-de-progressao-diverge", "fracao-de-livramento-diverge", "seeu-tratou-como-hediondo-mas-o-tipo-nao-consta"} & set(t), "§ 7º: %s" % t)

# 2. "ART 217: (Revogado...)" com selo de hediondo: é o 217-A
e217 = crime(artigo="ART 217: (Revogado pela Lei nº 11.106, de 2005)", tipo_penal="CAPUT: Na mesma pena incorre quem realiza montagem",
             data_infracao="19/08/2016", fracao_progressao="2/5 - Hediondo Primario", fracao_livramento="2/3 - Hediondo")
t = tipos(reg([e217]), "alerta")
ok(not {"percentual-de-progressao-diverge", "fracao-de-livramento-diverge", "seeu-tratou-como-hediondo-mas-o-tipo-nao-consta"} & set(t), "art. 217: %s" % t)

# 3. reincidência específica marcada e não demonstrada, fato entre 2007 e 2020: 40% (Tema 1084), não os 3/5
hom = crime(artigo="ART 121: Matar alguem:", tipo_penal="§ 2º: Se o homicídio é cometido:, Reclusão: 12 a 30 anos", data_infracao="14/02/2014",
            vga="S", reincidente_especifico="S", fracao_progressao="60% - Hediondo Reincidente", fracao_livramento="1/1 - Hediondo Reincidente/Reincidente Específico")
it = {i["tipo"]: i for i in itens(reg([hom]))}
ok("percentual-de-progressao-diverge" in it and "40%" in it["percentual-de-progressao-diverge"]["titulo"], "Tema 1084: %s" % list(it))
ok("40%" in it["reincidencia-especifica-nao-demonstrada-no-rspe"]["detalhe"] and "3/5 só se" not in it["reincidencia-especifica-nao-demonstrada-no-rspe"]["detalhe"], "texto 3/5")

# 4. regressão por fuga: a data-base é a recaptura, ainda que a regressão seja decidida depois
evs = [ev("PRISÃO/INÍCIO DE CUMPRIMENTO", "PRISÃO DEFINITIVA", "18/11/2011"), ev("INTERRUPÇÃO", "FUGA", "31/12/2023", ""),
       ev("PRISÃO/INÍCIO DE CUMPRIMENTO", "RECAPTURA/REINÍCIO DE CUMPRIMENTO", "26/05/2024")]
incs = [inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Fechado - Regime Inicial", "", "18/11/2011"),
        inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Semiaberto - Progressão de Regime", "24/06/2022", "01/07/2021"),
        inc("HOMOLOGAÇÃO DE FALTA GRAVE", "31/12/2023", "29/01/2025", "31/12/2023"),
        inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Fechado - Regressão", "29/01/2025", "29/01/2025")]
ok("data-base-de-progressao-anterior-a-ultima-altera" not in tipos(reg([crime()], incs, evs, data_base_seeu="26/05/2024")), "data-base na recaptura")

# 5. contravenção anterior não gera reincidência (CP, art. 63; LCP, art. 7º)
lcp = crime(processo_criminal="0000002-22.2017.8.12.0001", lei="3688/41 - Lei das Contravenções Penais", artigo="ART 21: Vias de fato",
            data_infracao="01/01/2017", transito_processo="13/07/2018", transito_mp="13/07/2018")
t = tipos(reg([crime(data_infracao="28/09/2021", fracao_progressao="25% - Art.112, III, da LEP", vga="S",
                     artigo="ART 157: Roubo", tipo_penal="§ 2º: A pena aumenta-se"), lcp]))
ok("reincidente-pela-lei-sem-marcacao" not in t, "contravenção: %s" % t)

# 6. porte para consumo próprio (art. 16 da Lei 6.368/76): sem pena de prisão
por = crime(lei="6368/76 - Lei de Tóxicos", artigo="ART 16: Adquirir, guardar ou trazer consigo", data_infracao="18/12/2002",
            pena_imposta="1 ano(s), 6 mês(es) e 0 dia(s)", fracao_progressao="1/6 - Comum")
t = tipos(reg([por]))
ok("pena-de-prisao-por-porte-para-consumo-proprio" in t and "percentual-de-progressao-diverge" not in t, "porte: %s" % t)

# 7. soma das penas: guia suspensa fora da soma; soma maior que o total não gera texto de impugnação
sus = crime(processo_criminal="0000003-33.2024.8.12.0001", pena_imposta="2 ano(s), 6 mês(es) e 0 dia(s)", suspenso="Sim")
t = tipos(reg([crime(), sus]))
ok("soma-das-penas-difere-da-pena-total" not in t and "soma-das-penas-confere-com-a-pena-total" in t, "suspensa: %s" % t)
r = reg([crime(), crime(processo_criminal="0000004-44.2024.8.12.0001", pena_imposta="1 ano(s), 5 mês(es) e 17 dia(s)")], pena_total="10a5m22d")
it = [i for i in itens(r) if i["tipo"] == "soma-das-penas-difere-da-pena-total"]
ok(it and "diferença 0a11m25d" in it[0]["detalhe"] and not ra.fundamentacao(it[0], r), "soma maior que o total: %s" % (it and it[0]["detalhe"]))

# 8. regime inicial depois da primeira prisão com diferença menor que 10 dias: informativo
evs = [ev("PRISÃO/INÍCIO DE CUMPRIMENTO", "PRISÃO EM FLAGRANTE", "29/11/2016"), ev("INTERRUPÇÃO", "SOLTURA", "30/11/2016", ""),
       ev("PRISÃO/INÍCIO DE CUMPRIMENTO", "PRISÃO DEFINITIVA", "07/02/2024")]
it = [i for i in itens(reg([crime()], [inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Fechado - Regime Inicial", "", "07/02/2024")], evs, data_base_seeu="07/02/2024"))
      if i["tipo"] == "regime-inicial-depois-da-primeira-prisao"]
ok(it and it[0]["nivel"] == "info" and "2.248.958" in it[0]["detalhe"] and "Houve soltura" in it[0]["detalhe"], "regime inicial: %s" % it)

# 9. idade impossível no fato e remição lançada em duplicidade
t = tipos(reg([crime(data_infracao="30/10/2013")], data_nascimento="17/07/2004"))
ok("idade-no-fato-menor-de-18-erro-de-cadastro" in t and "menor-de-21-anos-no-fato-prescricao-pela-metade" not in t, "idade: %s" % t)
rem = inc("REMIÇÃO", "10 Dia(s) Remido(s)", "29/08/2025", "04/06/2025")
ok("remicao-lancada-em-duplicidade" in tipos(reg([crime()], [rem, dict(rem)])), "remição duplicada")

# 10. ficha: fuga de outra execução e retorno de evasão não são fuga omitida; alvará na data da fuga do RSPE é alerta
f = {"eventos": [{"data": "06.08.2014", "texto": "Saída da Unidade Penal: CPAIG, Destino: EVASÃO, Motivo: Fuga"},
                 {"data": "07.08.2014", "texto": "REAPRESENTAÇÃO NO CPAIG, RETORNOU DE EVASÃO"},
                 {"data": "20.05.2025", "texto": "Entrada na Unidade Penal: PTRAN, Procedente: DEPAC"},
                 {"data": "24.08.2025", "texto": "Saída da Unidade Penal: PTRAN, Destino: , Motivo: Alvará de Soltura"},
                 {"data": "01.10.2025", "texto": "Entrada na Unidade Penal: PTRAN"}]}
r = reg([crime()], eventos=[ev("PRISÃO/INÍCIO DE CUMPRIMENTO", "PRISÃO EM FLAGRANTE", "14/04/2025"), ev("INTERRUPÇÃO", "FUGA", "24/08/2025", "")])
tt = [(i["nivel"], i["titulo"]) for i in rf._fuga_x_ficha(r, f)]
ok(not any("registrada na ficha" in x for _, x in tt), "fuga de outra execução / retorno: %s" % tt)
ok(any(n == "alerta" and "alvará de soltura" in x for n, x in tt), "alvará na data da fuga: %s" % tt)

# 11. identidade: grafia diferente com CPF e nascimento iguais não é alerta; mãe lida da filiação "PAI \ MÃE"
r = {"nome": "CINEI DIEGO JESUS NUNEZ", "cpf": "70542638126", "data_nascimento": "10/11/1989", "nome_mae": "JANDIRA DE OLIVEIRA VASQUES", "_crimes": []}
f = {"nome": "CINEI DIEGO JESUS NUNES", "cpf": "705.426.381-26", "data_nascimento": "10.11.1989", "nome_mae": "ARLINDO VASQUES",
     "filiacao": "ARLINDO VASQUES \\ JANDIRA DE OLIVEIRA VASQUES"}
ok(not [i for i in rf._identidade_x_ficha(r, f) if i["nivel"] == "alerta"], "identidade: %s" % rf._identidade_x_ficha(r, f))

# ---------------- 2ª rodada (auditoria.md, A1-A16) ----------------
def por_tipo(r):
    out = {}
    for i in itens(r):
        out.setdefault(i["tipo"], []).append(i)
    return out


AR = "FIXAÇÃO/ALTERAÇÃO DE REGIME"
PR = "PRISÃO/INÍCIO DE CUMPRIMENTO"

# A1/A13. data-base fixa anterior aos marcos posteriores: favorável (info, sem fundamentação), texto com o nome do marco, sem
# "confere" junto; A2: data-base anterior à última alteração de regime também é favorável (info)
evs = [ev(PR, "PRISÃO EM FLAGRANTE", "01/01/2020")]
incs = [inc(AR, "Fechado - Regime Inicial", "", "01/01/2020"), inc("HOMOLOGAÇÃO DE FALTA GRAVE", "01/05/2021", "20/05/2021", "01/05/2021"),
        inc("ALTERAÇÃO DE DATA-BASE", "", "20/05/2021", "01/06/2021"), inc(AR, "Semiaberto - Progressão de Regime", "10/06/2023", "01/06/2023")]
r = reg([crime()], incs, evs, data_base_seeu="01/06/2021")
pt = por_tipo(r)
fx = pt.get("alteracao-de-data-base-no-lugar-do-incidente", [{}])[0]
ok(fx.get("nivel") == "info" and "favorável" in fx.get("titulo", "") and not ra.fundamentacao(fx, r), "A1 data-base fixa: %s" % fx)
ok("progressão de regime (semiaberto) em 01/06/2023" in fx.get("detalhe", ""), "A13 marco no texto: %s" % fx.get("detalhe"))
ok(all(i["nivel"] == "info" for i in pt.get("data-base-de-progressao-anterior-a-ultima-altera", [])) and pt.get("data-base-de-progressao-anterior-a-ultima-altera"),
   "A2: %s" % pt.get("data-base-de-progressao-anterior-a-ultima-altera"))
ok("data-base-confere-com-o-rspe" not in pt, "A1/A2 sem 'confere' junto: %s" % list(pt))
# A1. "prisão definitiva" de quem já estava preso (guia nova) não é marco posterior: a data-base não está "presa"
evs = [ev(PR, "PRISÃO DEFINITIVA", "16/10/2024"), ev(PR, "PRISÃO DEFINITIVA", "15/05/2025")]
r = reg([crime()], [inc("ALTERAÇÃO DE DATA-BASE", "", "20/10/2024", "16/10/2024")], evs, data_base_seeu="16/10/2024")
fx = por_tipo(r).get("alteracao-de-data-base-no-lugar-do-incidente", [{}])[0]
ok("fixada" not in fx.get("titulo", "") and fx.get("nivel") == "info", "A1 prisão fictícia: %s" % fx.get("titulo"))

# A3. art. 28 com pena zerada (prestação de serviços) ou suspensa: sem alerta de pena de prisão
for kw in ({"pena_imposta": "0 ano(s), 0 mês(es) e 0 dia(s)"}, {"pena_imposta": "0 ano(s), 6 mês(es) e 0 dia(s)", "suspenso": "Sim"}):
    p28 = crime(processo_criminal="0000005-55.2019.8.12.0001", lei="11343/06 - Lei de Drogas", artigo="ART 28: Quem adquirir",
                tipo_penal="CAPUT, II: prestação de serviços", data_infracao="01/02/2019", **kw)
    ok("pena-de-prisao-por-porte-para-consumo-proprio" not in tipos(reg([crime(), p28])), "A3 porte sem prisão efetiva: %s" % kw)

# A4. ficha: transferência com "Motivo: Progressão" de quem já está no regime pelo RSPE (regime inicial semiaberto ou progressão
# decidida meses antes) ou com evento do RSPE na data não é progressão omitida; ida ao monitoramento não é regressão
SAI = "Saída da Unidade Penal: PENITENCIÁRIA DE DOIS IRMÃO DO BURITI, Destino: %s, Motivo: %s, Conforme Ofício: 1."
SEMI = "ESTABELECIMENTO PENAL REGIME SEMIABERTO E ABERTO AQUIDAUANA"
f = {"eventos": [{"data": "30.06.2026", "texto": SAI % (SEMI, "Progressão de Regime")}]}
r = reg([crime()], [inc(AR, "Semiaberto - Regime Inicial", "", "25/03/2026")], [ev(PR, "PRISÃO EM FLAGRANTE", "25/03/2026")])
ok(not rf._regime_x_ficha(r, f), "A4 regime inicial semiaberto: %s" % rf._regime_x_ficha(r, f))
f = {"eventos": [{"data": "24.04.2025", "texto": SAI % (SEMI, "Progressão de Regime")}]}
r = reg([crime()], [inc(AR, "Fechado - Regime Inicial", "", "01/01/2020"), inc(AR, "Semiaberto - Progressão de Regime", "26/02/2025", "09/03/2025"),
                    inc(AR, "Fechado - Regressão Cautelar", "23/05/2025", "23/05/2025")], [ev(PR, "PRISÃO EM FLAGRANTE", "01/01/2020")])
ok(not rf._regime_x_ficha(r, f), "A4 progressão decidida 46 dias antes: %s" % rf._regime_x_ficha(r, f))
r = reg([crime()], [inc(AR, "Fechado - Regime Inicial", "", "01/01/2020")], [ev(PR, "PRISÃO EM FLAGRANTE", "01/01/2020"),
                                                                          ev(PR, "RECAPTURA/REINÍCIO DE CUMPRIMENTO", "24/04/2025")])
ok(not rf._regime_x_ficha(r, f), "A4 evento do RSPE na data: %s" % rf._regime_x_ficha(r, f))
r = reg([crime()], [inc(AR, "Fechado - Regime Inicial", "", "01/01/2020")], [ev(PR, "PRISÃO EM FLAGRANTE", "01/01/2020")])
ok(rf._regime_x_ficha(r, f), "A4 progressão omitida de fato continua alerta")
f = {"eventos": [{"data": "13.11.2025", "texto": SAI % ("UMMVE - UNIDADE MISTA DE MONITORAMENTO VIRTUAL ESTADUAL", "Regressão de Regime")}]}
ok(not rf._regime_x_ficha(r, f), "A4 ida ao monitoramento não é regressão: %s" % rf._regime_x_ficha(r, f))

# A5. mais de um regime inicial: com liberdade entre eles, nada; mesma data, info; sem liberdade e data-base no segundo, alerta
evs = [ev(PR, "PRISÃO EM FLAGRANTE", "19/07/2018"), ev("INTERRUPÇÃO", "LIBERDADE PROVISÓRIA", "01/08/2018", ""), ev(PR, "PRISÃO PREVENTIVA", "22/01/2025")]
ris = [inc(AR, "Aberto - Regime Inicial", "", "09/03/2020"), inc(AR, "Fechado - Regime Inicial", "", "22/01/2025")]
ok("mais-de-um-regime-inicial" not in tipos(reg([crime()], ris, evs, data_base_seeu="22/01/2025")), "A5 liberdade entre os regimes iniciais")
evs = [ev(PR, "PRISÃO EM FLAGRANTE", "01/01/2020")]
ris = [inc(AR, "Fechado - Regime Inicial", "", "01/01/2020"), inc(AR, "Fechado - Regime Inicial", "", "01/06/2021")]
ok([i["nivel"] for i in itens(reg([crime()], ris, evs, data_base_seeu="01/06/2021")) if i["tipo"] == "mais-de-um-regime-inicial"] == ["alerta"], "A5 alerta real")
ok([i["nivel"] for i in itens(reg([crime()], ris, evs, data_base_seeu="01/03/2024")) if i["tipo"] == "mais-de-um-regime-inicial"] == ["info"], "A5 superado")

# A6. prisão da ficha anterior a todos os fatos da execução: não é detração
f = {"data_prisao": "14/04/2019", "eventos": []}
r = reg([crime(data_infracao="19/03/2024")], eventos=[ev(PR, "PRISÃO EM FLAGRANTE", "19/03/2024")])
ok(not rf._prisao_x_ficha(r, f), "A6 prisão anterior ao fato: %s" % rf._prisao_x_ficha(r, f))

# A7. regime inicial depois da primeira prisão, sem progressão e com data-base posterior: sem efeito (info)
evs = [ev(PR, "PRISÃO EM FLAGRANTE", "06/08/2022"), ev(PR, "PRISÃO DEFINITIVA", "06/07/2025"), ev("INTERRUPÇÃO", "FUGA", "15/07/2025", ""),
       ev(PR, "RECAPTURA/REINÍCIO DE CUMPRIMENTO", "11/09/2025")]
it = [i for i in itens(reg([crime()], [inc(AR, "Fechado - Regime Inicial", "", "06/07/2025")], evs, data_base_seeu="11/09/2025"))
      if i["tipo"] == "regime-inicial-depois-da-primeira-prisao"]
ok(it and it[0]["nivel"] == "info" and "sem efeito" in it[0]["titulo"], "A7: %s" % it)

# A8. já no regime aberto: percentual de progressão sem efeito (info); progressão ao aberto na data da decisão: sem progressão seguinte
r = reg([crime(data_infracao="01/02/2021", fracao_progressao="1/6 - Comum", pena_imposta="2 ano(s), 0 mês(es) e 0 dia(s)")],
        [inc(AR, "Fechado - Regime Inicial", "", "01/01/2021"), inc(AR, "Aberto - Progressão de Regime", "10/03/2024", "10/03/2024")],
        [ev(PR, "PRISÃO EM FLAGRANTE", "01/01/2021")], regime_atual="Aberto - ATIVO", data_base_seeu="10/03/2024")
pt = por_tipo(r)
ok(all(i["nivel"] == "info" for i in pt.get("percentual-de-progressao-diverge", [])) and pt.get("percentual-de-progressao-diverge"), "A8 aberto: %s" % pt.get("percentual-de-progressao-diverge"))
ok("progressao-com-data-base-igual-a-data-da-decisao" not in pt, "A8 progressão ao aberto: %s" % list(pt))

# A9. perda de remidos sem incidente de falta: a própria sanção não vira "falta a apurar" (verificar)
it = [i for i in itens(reg([crime()], [inc("DIAS PERDIDOS NA REMIÇÃO", "5", "18/08/2026", "18/08/2026")], [ev(PR, "PRISÃO EM FLAGRANTE", "01/01/2020")]))
      if i["tipo"] == "falta-a-apurar"]
ok(it and all(i["nivel"] == "info" for i in it), "A9: %s" % [(i["nivel"], i["titulo"]) for i in it])

# A10. pena acima do máximo do tipo cadastrado (art. 33, § 2º, com 5a10m): aviso de cadastro, não "fração correta"; o selo de
# hediondo não alcança o § 2º
mar = crime(processo_criminal="0001522-12.2020.8.12.0015", lei="11343/06 - Lei de Drogas", artigo="ART 33: Tráfico de drogas",
            tipo_penal="§ 2º: Induzir, instigar ou auxiliar alguém ao uso indevido de droga, Detenção: 1 a 3 anos E Multa",
            data_infracao="20/10/2020", pena_imposta="5 ano(s), 10 mês(es) e 0 dia(s)", reincidente_comum="S",
            fracao_progressao="40% - Art.112, V, da LEP", fracao_livramento="2/3 - Hediondo")
pt = por_tipo(reg([mar]))
ok("pena-acima-do-maximo-do-tipo-cadastrado" in pt and not [i for i in pt.get("percentual-de-progressao-diverge", []) + pt.get("fracao-de-livramento-diverge", [])
                                                         if i["nivel"] == "alerta"], "A10: %s" % list(pt))
import rspe_scraper as rs
ok(rs.e_hediondo(dict(mar)) is False, "A10 selo de hediondo no art. 33, § 2º")

# A11. capitulação criada depois do fato, com as frações do SEEU corretas: info
cap = crime(artigo="ART 157: Roubo", vga="S", data_infracao="10/01/2015", fracao_progressao="1/6 - Comum", fracao_livramento="1/3 - Comum",
            tipo_penal="§ 2º-A, I: Se a violência ou ameaça é exercida com emprego de arma de fogo, Reclusão: 6 anos e 8 meses a 16 anos e 8 meses E Multa")
it = por_tipo(reg([cap])).get("capitulacao-criada-depois-do-fato", [])
ok(it and it[0]["nivel"] == "info", "A11: %s" % it)

# A12. reincidência específica não demonstrada: um só alerta para o erro (o do item 3)
ok([i["tipo"] for i in itens(reg([hom])) if i["nivel"] == "alerta"] == ["reincidencia-especifica-nao-demonstrada-no-rspe"],
   "A12: %s" % [i["tipo"] for i in itens(reg([hom])) if i["nivel"] == "alerta"])

# A13. data-base na data do fato de condenação desta execução: verificar com o motivo, não "inconsistência"
r = reg([crime(), crime(processo_criminal="0000006-66.2024.8.12.0001", data_infracao="25/03/2024")], [inc(AR, "Fechado - Regime Inicial", "", "01/01/2020")],
        [ev(PR, "PRISÃO EM FLAGRANTE", "01/01/2020")], data_base_seeu="25/03/2024")
pt = por_tipo(r)
ok("data-base-na-data-do-fato-de-condenacao" in pt and "inconsistencia-da-data-base-sem-prisao-alteracao" not in pt, "A13: %s" % list(pt))

# A14. rótulo da fração cita o dispositivo do crime (furto: LEP, art. 112, I), não a janela (feminicídio, Lei 8.072)
it = por_tipo(reg([crime(data_infracao="01/02/2025", fracao_progressao="1/6 - Comum", pena_imposta="2 ano(s), 0 mês(es) e 0 dia(s)")])).get("percentual-de-progressao-diverge", [{}])[0]
ok("LEP, art. 112, I" in it.get("titulo", "") and "14.994" not in it.get("titulo", ""), "A14: %s" % it.get("titulo"))
it = por_tipo(reg([crime(artigo="ART 121: Matar alguem:", tipo_penal="CAPUT: Matar alguém, Reclusão: 6 a 20 anos", vga="S",
                         data_infracao="01/02/2015", fracao_progressao="2/5 - Hediondo")])).get("percentual-de-progressao-diverge", [{}])[0]
ok("8.072" not in it.get("titulo", "x"), "A14 homicídio simples: %s" % it.get("titulo"))

# A15. HC 1.032.430 (concessão na importunação sexual) não é base para presumir violência
ok(not any("1.032.430" in i["detalhe"] for i in itens(reg([crime(artigo="ART 121: Matar alguem:", tipo_penal="CAPUT: Matar alguém, Reclusão: 6 a 20 anos",
                                                                  data_infracao="01/02/2021", fracao_progressao="1/6 - Comum")]))), "A15")

# A16. data-base do livramento igual à da progressão sem falta nessa data: fundamento próprio (não a Súmula 441)
evs = [ev(PR, "PRISÃO EM FLAGRANTE", "19/11/2020"), ev("INTERRUPÇÃO", "FUGA", "01/03/2022", ""), ev(PR, "RECAPTURA/REINÍCIO DE CUMPRIMENTO", "01/05/2022"),
       ev(PR, "PRISÃO PREVENTIVA", "10/12/2024", "0000009-99.2024.8.12.0001")]
r = reg([crime()], [inc(AR, "Fechado - Regime Inicial", "", "19/11/2020"), inc(AR, "Fechado - Regime Inicial", "", "10/12/2024")], evs,
        data_base_seeu="10/12/2024", livramento_data_base_seeu="10/12/2024")
pt = por_tipo(r)
ok("data-base-do-livramento-igual-a-da-progressao" in pt and "data-base-do-livramento-alterada-por-falta-grave" not in pt, "A16: %s" % list(pt))

# âncora das asserções negativas (A25): todo tipo testado com "not in" (ou num conjunto que não pode aparecer) precisa existir
# como identificador em rspe_auditoria ou rspe_ficha; se for renomeado, a asserção negativa passaria sem testar nada
import os
import re
_aqui = open(os.path.abspath(__file__), encoding="utf-8").read()
_neg = set(re.findall(r'"([a-z0-9]+(?:-[a-z0-9]+){2,})" not in', _aqui))
for _cj in re.findall(r"ok\(not \{([^}]*)\} & set", _aqui):
    _neg |= set(re.findall(r'"([a-z0-9]+(?:-[a-z0-9]+){2,})"', _cj))
_mods = open(ra.__file__, encoding="utf-8").read() + open(rf.__file__, encoding="utf-8").read()
ok(len(_neg) >= 10, "âncora: poucas asserções negativas encontradas (%d)" % len(_neg))
for _t in sorted(_neg):
    ok('"%s"' % _t in _mods, "âncora: o tipo %s não existe mais em rspe_auditoria/rspe_ficha (a asserção negativa não testa nada)" % _t)

if falhas:
    print("FALHOU (revisão da auditoria):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: revisão da auditoria (hediondez, Tema 1084, data-base, reincidência, porte, soma, regime inicial, idade, remição, ficha)")
