"""Teste de regressão da conferência manual (frente C1, 20/10/2026): reincidência pelas datas do RSPE e da ficha
(rspe_reincidencia), frações de reincidente "a verificar" quando a reincidência não está demonstrada, 1/6 do SEEU onde a lei
dá 16% (alerta com os dias), vedação do livramento no tráfico só com reincidência específica em crime da Lei de Drogas,
consumação do homicídio pela pena, atentado violento ao pudor como crime violento, extorsão sem "crime patrimonial sem VGA",
reincidência específica marcada sem efeito no cálculo e condenação anterior sentenciada antes do fato.
Rodar: python teste_conf_C1.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_auditoria as ra
import rspe_reincidencia as rr

falhas = []
HOJE = date(2026, 10, 20)


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def crime(proc="0000001-11.2020.8.12.0001", **kw):
    c = {"processo_criminal": proc, "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto",
         "tipo_penal": "CAPUT: Subtrair, Reclusão: 1 a 4 anos", "pena_imposta": "2 ano(s), 0 mês(es) e 0 dia(s)",
         "data_infracao": "10/01/2021", "data_sentenca": "10/06/2021", "transito_mp": "", "transito_processo": "10/07/2021",
         "extinto": "Não", "suspenso": "Não", "vga": "N", "resultado_morte": "N", "reincidente_comum": "N", "reincidente_especifico": "N",
         "comando_orcrim": "N", "fracao_progressao": "16% - Art.112, I, da LEP", "fracao_livramento": "1/3 - Comum Primário"}
    c.update(kw)
    return c


def reg(crimes, **kw):
    r = {"nome": "Teste", "regime_atual": "Fechado - ATIVO", "pena_total": "10a0m0d", "pena_cumprida": "3a0m0d", "pena_remanescente": "7a0m0d",
         "data_geracao_rspe": "01/10/2026", "data_base_seeu": "01/03/2024", "data_nascimento": "01/01/1980", "_crimes": crimes,
         "_incidentes": [], "_eventos": []}
    r.update(kw)
    return r


def itens(r):
    return ra.auditar(r, HOJE)["aud_itens"]


def com(its, tipo, texto="", nivel=None):
    return [i for i in its if i["tipo"] == tipo and texto in i["titulo"] + " " + i["detalhe"] and (nivel is None or i["nivel"] == nivel)]


ANT = crime("0000009-11.2015.8.12.0001", data_infracao="10/01/2015", data_sentenca="10/06/2015", transito_processo="10/08/2015",
            fracao_progressao="1/6 - Comum")

# ---------------- 1. rspe_reincidencia.reincidencia_pelas_datas ----------------
c = crime(reincidente_comum="S")
R = rr.reincidencia_pelas_datas(c, [c, ANT])
ok(R["estado"] == "reincidente" and R["fonte"] == "rspe" and R["anteriores"] == [ANT], "RSPE: trânsito anterior ao fato: %s" % R)
R = rr.reincidencia_pelas_datas(c, [c], nasc=date(2002, 12, 20))
ok(R["estado"] == "nao_reincidente" and R["fonte"] == "idade" and "18 anos" in R["motivo"], "idade: 18 anos e poucos dias no fato: %s" % R)
R = rr.reincidencia_pelas_datas(c, [c], nasc=date(1990, 1, 1))
ok(R["estado"] == "indeterminado" and rr.reincidencia_em_duvida(R) and rr.reincidente_para_calculo(R), "sem base: indeterminado: %s" % R)
tp = crime(lei="11343/06 - Lei de Drogas", artigo="ART 33: Tráfico de drogas", tipo_penal="§ 4º: Nos delitos...", reincidente_comum="S")
R = rr.reincidencia_pelas_datas(tp, [tp])
ok(R["estado"] == "nao_reincidente" and R["fonte"] == "privilegio" and not rr.reincidente_para_calculo(R), "tráfico privilegiado: %s" % R)
ext = [{"processo": "0001308-32.2012.8.12.0005", "data": date(2017, 6, 22), "texto": ""}]
R = rr.reincidencia_pelas_datas(crime(data_infracao="13/05/2020", reincidente_comum="S"), [], extincoes=ext)
ok(R["estado"] == "reincidente" and R["fonte"] == "ficha", "ficha: pena extinta há menos de 5 anos: %s" % R)
R = rr.reincidencia_pelas_datas(crime(data_infracao="13/05/2023", reincidente_comum="S"), [], extincoes=ext)
ok(R["estado"] == "indeterminado" and not R["ficha"], "ficha: pena extinta há mais de 5 anos (depurada): %s" % R)
s_ant = crime("0000008-11.1997.8.12.0001", data_infracao="10/01/1997", data_sentenca="10/06/1997", transito_processo="")
c2 = crime(data_infracao="10/01/2005")
R = rr.reincidencia_pelas_datas(c2, [c2, s_ant])
ok(R["estado"] == "indeterminado" and R["sem_transito"] == [s_ant], "sentença anterior sem trânsito: indício: %s" % R)
duv = crime("0000007-11.2022.8.12.0001", data_infracao="01/01/2022", data_sentenca="30/08/2023", transito_processo="08/05/2023")
c3 = crime(data_infracao="01/01/2024", reincidente_comum="S")
R = rr.reincidencia_pelas_datas(c3, [c3, duv])
ok(R["estado"] == "indeterminado" and R["transito_duvidoso"] == [duv], "trânsito antes da sentença: duvidoso: %s" % R)
f = {"eventos": [{"data": "22.06.2017", "texto": "Saída da Unidade Penal: X, Destino: EXTINÇÃO DE PENA, Motivo: Extinção de Pena, "
                                                 "Conforme Ofício: AUT. 0001308-32.2012.8.12.0005."},
                 {"data": "05.07.2025", "texto": "PENA EXTINTA EM 24/06/2025, CONFORME DECISÃO, AUTOS DA EXECUÇÃO PENAL Nº 6005284-39.2021.8.12.0001."},
                 {"data": "04.04.2025", "texto": "CONSELHO DISCIPLINAR: FOI EXTINTO O PROCESSO - PADIC Nº 31/078983/2023"}]}
E = rr.extincoes_ficha(f)
ok([(e["processo"], e["data"]) for e in E] == [("0001308-32.2012.8.12.0005", date(2017, 6, 22)), ("6005284-39.2021.8.12.0001", date(2025, 6, 24))],
   "extinções da ficha: %s" % E)

# ---------------- 2. 1/6 do SEEU onde a lei dá 16%: alerta com os dias ----------------
it = itens(reg([crime(fracao_progressao="1/6 - Comum", pena_imposta="3 ano(s), 0 mês(es) e 0 dia(s)")]))
a = com(it, "percentual-de-progressao-diverge", nivel="alerta")
ok(a and "7 dias a mais" in a[0]["titulo"] and a[0].get("dias_diferenca") == 7, "1/6 x 16%%: alerta com 7 dias (1.095 dias / 150): %s" % a)
ok(not com(it, "percentual-de-progressao-confere"), "1/6 x 16%: não confere")
it = itens(reg([crime(data_infracao="10/03/2015", data_sentenca="10/06/2015", transito_processo="10/08/2015", fracao_progressao="1/6 - Comum",
                      pena_imposta="0 ano(s), 0 mês(es) e 15 dia(s)")]))
ok(com(it, "percentual-de-progressao-diverge", "menos de 1 dia", "info"), "1/6 x 16%%: pena de 15 dias - só informação: %s" % it)

# ---------------- 3. reincidência não demonstrada: frações de reincidente a verificar (não "confere") ----------------
c = crime(reincidente_comum="S", data_infracao="06/10/2023", data_sentenca="10/01/2024", transito_processo="10/03/2024",
          artigo="ART 180: Receptação", fracao_progressao="20% - Art.112, II, da LEP", fracao_livramento="1/2 - Comum Reincidente")
it = itens(reg([c]))
ok(com(it, "percentual-reincidencia-a-conferir", "16%", "verificar"), "reincidência sem base: 20%% a verificar (primário 16%%): %s" %
   [(i["nivel"], i["titulo"]) for i in it])
ok(com(it, "fracao-livramento-reincidencia-a-conferir", "1/3", "verificar"), "reincidência sem base: livramento 1/2 a verificar")
ok(not com(it, "percentual-de-progressao-confere"), "reincidência sem base: não confere")
# com a condenação anterior transitada no RSPE, o 20% confere
it = itens(reg([c, dict(ANT, extinto="Não")]))
ok(com(it, "percentual-de-progressao-confere") and not com(it, "percentual-reincidencia-a-conferir"), "reincidência demonstrada: confere")
# marcada, mas a ficha registra pena de outro processo extinta antes do fato: reincidência com base (informação)
it = itens(reg([c], _extincoes_ficha=[{"processo": "0005284-39.2021.8.12.0001", "data": "24/06/2023"}]))
ok(com(it, "reincidencia-com-base-na-ficha", nivel="info") and not com(it, "marcado-reincidente-sem-condenacao-anterior-tran"),
   "ficha confirma a reincidência: %s" % [(i["nivel"], i["titulo"]) for i in it])

# ---------------- 4. marcado reincidente, mas não pode ser (idade no fato) ----------------
c = crime(reincidente_comum="S", data_infracao="28/03/1994", data_sentenca="10/06/1995", transito_processo="10/08/1995",
          fracao_progressao="1/6 - Comum", fracao_livramento="1/2 - Comum Reincidente")
it = itens(reg([c], data_nascimento="18/03/1976"))
ok(com(it, "marcado-reincidente-desmentido-pelas-datas", "18 anos", "alerta"), "idade: marcado reincidente desmentido: %s" %
   [(i["nivel"], i["titulo"]) for i in it])
ok(com(it, "fracao-de-livramento-diverge", nivel="alerta"), "idade: livramento 1/2 maior que 1/3")
ok(not com(it, "marcado-reincidente-sem-condenacao-anterior-tran"), "idade: sem o 'verificar' de reincidência sem base")

# ---------------- 5. tráfico: vedação do livramento só com reincidência específica em crime da Lei de Drogas ----------------
hom = crime("0012996-16.2011.8.12.0008", artigo="ART 121: Matar alguem:", tipo_penal="§ 2º: Se o homicídio é cometido, Reclusão: 12 a 30 anos",
            pena_imposta="12 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="12/07/2011", data_sentenca="15/06/2016", transito_processo="03/08/2017",
            fracao_progressao="3/5 - Hediondo Reincidente", fracao_livramento="2/3 - Hediondo")
trf = crime("0000288-94.2022.8.12.0800", lei="11343/06 - Lei de Drogas", artigo="ART 33: Tráfico de drogas", tipo_penal="CAPUT: Importar",
            pena_imposta="5 ano(s), 6 mês(es) e 0 dia(s)", data_infracao="07/12/2021", data_sentenca="12/04/2022", transito_processo="09/05/2022",
            reincidente_especifico="S", fracao_progressao="60% - Art.112, VII, da LEP", fracao_livramento="1/1 - Hediondo Reincidente/Reincidente Específico")
it = itens(reg([hom, trf]))
ok([i for i in com(it, "fracao-de-livramento-diverge", "Lei de Drogas", "alerta") if "0000288" in i["titulo"]],
   "tráfico com anterior por homicídio: livramento 2/3: %s" % [(i["nivel"], i["titulo"]) for i in it])
ok(com(it, "reincidencia-especifica-confere-com-o-rspe", "para a progressão", "ok"), "tráfico: 60% confere (anterior hediondo)")
trf2 = crime("0900056-96.2024.8.12.0053", lei="11343/06 - Lei de Drogas", artigo="ART 33: Tráfico de drogas", tipo_penal="CAPUT: Importar",
             pena_imposta="7 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="15/08/2024", data_sentenca="03/02/2025", transito_processo="09/07/2025",
             reincidente_especifico="S", fracao_progressao="60% - Art.112, VII, da LEP", fracao_livramento="1/1 - Hediondo Reincidente/Reincidente Específico")
it = itens(reg([hom, trf, trf2]))
ok(not [i for i in com(it, "fracao-de-livramento-diverge") if "0900056" in i["titulo"] + i["detalhe"]],
   "tráfico com anterior por tráfico: livramento vedado confere")

# ---------------- 6. homicídio: a pena mostra a consumação (resultado morte) ----------------
h = crime("0900096-27.2026.8.12.0015", artigo="ART 121: Matar alguem:", tipo_penal="CAPUT: Matar alguém., Reclusão: 6 a 20 anos Sem Multa",
          pena_imposta="18 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="25/12/2025", data_sentenca="01/03/2026", transito_processo="28/05/2026",
          hediondo_ou_equiparado="S", reincidente_comum="S", fracao_progressao="3/5 - Hediondo Reincidente",
          fracao_livramento="1/1 - Hediondo Reincidente/Reincidente Específico")
it = itens(reg([h]))
a = com(it, "percentual-de-progressao-diverge", nivel="alerta")
ok(a and "50%" in a[0]["titulo"] and "40%" not in a[0]["titulo"] and "Consumação" in a[0]["detalhe"],
   "homicídio de 18 anos (máximo na tentativa 13a4m): legal 50%%, não 40%%: %s" % a)
ok(com(it, "homicidio-simples-com-selo-de-hediondo", "30%"), "homicídio simples sem grupo de extermínio: 30%")

# ---------------- 7. reincidente em crime violento: atentado violento ao pudor tem violência elementar ----------------
avp = crime("0001159-92.2005.8.12.0001", artigo="ART 214: Atentado violento ao pudor", tipo_penal="CAPUT: Constranger alguém",
            pena_imposta="6 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="10/01/2004", data_sentenca="10/06/2005", transito_processo="15/12/2005")
rb = crime("0000709-82.2020.8.12.0015", artigo="ART 157: Roubo", tipo_penal="CAPUT: Subtrair coisa móvel, Reclusão: 4 a 10 anos",
           pena_imposta="5 ano(s), 4 mês(es) e 0 dia(s)", data_infracao="14/05/2020", data_sentenca="10/01/2021", transito_processo="10/03/2021",
           reincidente_comum="S", fracao_progressao="30% - Art.112, IV, da LEP", fracao_livramento="1/2 - Comum Reincidente")
it = itens(reg([avp, rb]))
ok(not com(it, "reincidente-vga-percentual-se-nao-especifica", nivel="alerta") and com(it, "reincidente-vga-percentual-se-nao-especifica", "atentado violento", "verificar"),
   "roubo com anterior por AVP: 30%% se sustenta (verificar a violência presumida): %s" % [(i["nivel"], i["titulo"]) for i in it])

# ---------------- 8. extorsão (violência elementar) não é "crime patrimonial sem VGA" ----------------
ex = crime(artigo="ART 158: Extorsão", tipo_penal="§ 3º: Se o crime é cometido mediante restrição", vga="N", pena_imposta="8 ano(s), 0 mês(es) e 0 dia(s)",
           fracao_progressao="25% - Art.112, III, da LEP")
ok(not com(itens(reg([ex])), "crime-patrimonial-sem-vga-reparacao-do-dano"), "extorsão: sem 'crime patrimonial sem VGA'")

# ---------------- 9. reincidência específica marcada sem efeito no cálculo: só informação ----------------
t40 = crime(lei="11343/06 - Lei de Drogas", artigo="ART 33: Tráfico de drogas", tipo_penal="CAPUT: Importar", pena_imposta="5 ano(s), 0 mês(es) e 0 dia(s)",
            data_infracao="10/01/2026", data_sentenca="10/05/2026", transito_processo="10/06/2026", reincidente_especifico="S",
            fracao_progressao="40% - Art.112, V, da LEP", fracao_livramento="2/3 - Hediondo")
it = itens(reg([t40]))
ok(com(it, "reincidencia-especifica-nao-demonstrada-no-rspe", "sem efeito", "info"), "específico marcado, SEEU 40%% e 2/3: info: %s" %
   [(i["nivel"], i["titulo"]) for i in it])

# ---------------- 10. condenação anterior sentenciada antes do fato, sem trânsito: verificar (não alerta) ----------------
a12 = crime("0800746-90.1998.8.12.0001", lei="6368/76 - Lei de Tóxicos", artigo="ART 12: Importar ou exportar", tipo_penal="CAPUT: Importar",
            data_infracao="05/05/1995", data_sentenca="28/02/1997", transito_processo="", fracao_progressao="1/6 - Crime Hediondo até 28/03/2007")
t10 = crime("0058226-05.2011.8.12.0001", lei="11343/06 - Lei de Drogas", artigo="ART 33: Tráfico de drogas", tipo_penal="CAPUT: Importar",
            pena_imposta="8 ano(s), 9 mês(es) e 0 dia(s)", data_infracao="18/04/2010", data_sentenca="08/10/2015", transito_processo="03/11/2015",
            reincidente_especifico="S", fracao_progressao="60% - Hediondo Reincidente", fracao_livramento="1/1 - Hediondo Reincidente/Reincidente Específico")
it = itens(reg([a12, t10]))
ok([i for i in com(it, "reincidencia-especifica-nao-demonstrada-no-rspe", "provável", "verificar") if "0058226" in i["titulo"] + i["detalhe"]],
   "sentença anterior ao fato sem trânsito: reincidência específica a verificar: %s" % [(i["nivel"], i["titulo"]) for i in it])

# ---------------- 11. reincidente pela lei sem marcação, com efeito: o item traz o efeito (as abas avisam) ----------------
c = crime(data_infracao="27/01/2024", data_sentenca="10/06/2024", transito_processo="10/08/2024", artigo="ART 157: Roubo",
          tipo_penal="CAPUT: Subtrair coisa móvel, Reclusão: 4 a 10 anos", pena_imposta="5 ano(s), 4 mês(es) e 0 dia(s)",
          fracao_progressao="25% - Art.112, III, da LEP", fracao_livramento="1/3 - Comum Primário")
it = itens(reg([c, dict(ANT, extinto="Não")]))
r_ = com(it, "reincidente-pela-lei-sem-marcacao")
ok(r_ and "livramento 1/2 em vez de 1/3" in (r_[0].get("efeito") or ""), "reincidente pela lei: efeito no livramento: %s" % r_)

if falhas:
    print("FALHOU (conferência C1 - reincidência e frações):")
    for x in falhas:
        print("  " + x)
    sys.exit(1)
print("ok: conferência C1 (reincidência pelas datas e pela ficha, frações de reincidente a verificar, 1/6 x 16% com os dias, tráfico e "
      "Lei de Drogas, consumação pela pena, AVP, extorsão, específico sem efeito, sentença anterior sem trânsito)")
