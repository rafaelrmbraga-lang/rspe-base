"""Teste de regressão dos alertas corrigidos na revisão de 08.10 (progressão/livramento e confronto RSPE x ficha): feminicídio
aumentado e art. 217 revogado como hediondos, reincidência específica não demonstrada (2007-2020), data-base na recaptura após
fuga, contravenção sem reincidência, porte para consumo, soma com guia suspensa, regime inicial sem efeito, idade impossível,
remição em duplicidade e, na ficha, fuga de outra execução, retorno de evasão, alvará na data da fuga e identidade por grafia.
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
it = [i for i in itens(reg([crime()], [inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Fechado - Regime Inicial", "", "07/02/2024")], evs))
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

if falhas:
    print("FALHOU (revisão da auditoria):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: revisão da auditoria (hediondez, Tema 1084, data-base, reincidência, porte, soma, regime inicial, idade, remição, ficha)")
