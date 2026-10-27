"""Revisão jurídica do Capítulo 3 (progressão e livramento), 7.14.8: um teste por correção aprovada. Casos hipotéticos, nomes
fictícios. Rodar: python teste_rev_cap3.py

 1 progressão refeita e unificação pendente: 16% retroage ao fato anterior a 23/01/2020 (Tema 1354/STJ)
 2 homicídio/latrocínio sem "resultado morte": o livramento 1/1 fica "verificar", como a progressão
 3 saída temporária: 1/6 ou 1/4 pela reincidência pelas datas, não pela marcação do SEEU
 4 "SEEU tratou como hediondo" não sai para o percentual do comando de organização criminosa nem da milícia
 5 trânsito só para o MP não demonstra reincidência
 6 pena anterior extinta pelo livramento ou sursis: o período de prova entra nos 5 anos (depuração a conferir)
 7 crimes do Título XII (Estado Democrático de Direito): exceção da Lei 15.402/2026, retroativa, "verificar"
 8 saída para estudo (art. 122, II) continua possível depois da Lei 14.843/2024
 9 crime a crime: condenação só de outra execução, sem marcação, não torna o outro crime reincidente
10 art. 148 fora da lista de tipos com violência ou grave ameaça
11 estimativa da unificação pendente na convenção do SEEU (data-base + lapso) - também em teste_conf3_progressao
12 Lei 15.402: o inciso que continua no texto é o IV
13 TJMS 1421350-44.2026: negou efeito suspensivo em cautelar (não "manteve")
14 AgRg no REsp 2.248.958 descrito como precedente sobre a data-base
15 HC 1.076.656 citado como decisão monocrática
16 contravenção seguida de contravenção: não conta (escolha favorável, LCP, art. 7º, declarada)
17 rótulo do 1/6 da redação anterior no item crime a crime
"""
import copy
import sys
import types
from datetime import date, timedelta
from fractions import Fraction

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_auditoria as ra
import rspe_regras as rg
import rspe_reincidencia as rr
import rspe_view as rv

falhas = []
HOJE = date(2026, 10, 27)
P1, P2, P3 = "0000001-11.2020.8.12.0001", "0000002-22.2015.8.12.0001", "0000003-33.2022.8.12.0001"


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def crime(**kw):
    c = {"processo_criminal": P1, "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto", "tipo_penal": "CAPUT: Subtrair",
         "pena_imposta": "2 ano(s), 0 mês(es) e 0 dia(s)", "data_infracao": "10/01/2021", "data_sentenca": "10/06/2021",
         "transito_mp": "10/07/2021", "transito_processo": "10/07/2021", "extinto": "Não", "suspenso": "Não", "vga": "N",
         "resultado_morte": "N", "reincidente_comum": "N", "reincidente_especifico": "N", "comando_orcrim": "N",
         "fracao_progressao": "1/6 - Comum", "fracao_livramento": "1/3 - Comum", "regime_sentenca": "Fechado",
         "tipo_processo": "ACAO PENAL"}
    c.update(kw)
    return c


def reg(crimes, **kw):
    r = {"nome": "Teste Ficticio", "regime_atual": "Semiaberto - ATIVO", "pena_total": "14a0m0d", "pena_cumprida": "3a0m0d",
         "pena_remanescente": "11a0m0d", "data_geracao_rspe": "01/10/2026", "data_base_seeu": "", "_crimes": crimes,
         "_incidentes": [], "_eventos": [], "data_nascimento": "01/01/1980", "status_execucao": "ATIVO", "reincidente": "N"}
    r.update(kw)
    return r


def itens(r, tipo=None):
    its = ra.auditar(copy.deepcopy(r), HOJE)["aud_itens"]
    return [i for i in its if tipo is None or i.get("tipo") == tipo]


# ---- 1. progressão refeita: 16% retroage ----
ok(rv._fr_prog_refeita(crime(data_infracao="01/03/2018")) == Fraction(16, 100), "1: fato de 2018 deveria usar 16%")
ok(rv._fr_prog_refeita(crime(data_infracao="01/03/2021")) == Fraction(16, 100), "1: fato de 2021 deveria usar 16%")
ok(rv._fr_prog_refeita(crime(data_infracao="01/06/2026")) == Fraction(1, 6), "1: fato desde 08/05/2026 fica 1/6 (Lei 15.402)")
ok(rv._fr_prog_refeita(crime(data_infracao="01/03/2018", vga="S")) == Fraction(1, 6), "1: crime com violência fica com a fração do SEEU")
ok(rv._fr_prog_refeita(crime(data_infracao="01/03/2018", reincidente_comum="S")) == Fraction(1, 6), "1: reincidente fica 1/6 (ultra-ativo)")

# ---- 2. livramento do homicídio qualificado sem a marcação de morte ----
hom = crime(artigo="ART 121: Homicídio", tipo_penal="§ 2º, II: motivo fútil", pena_imposta="14 ano(s), 0 mês(es) e 0 dia(s)",
            data_infracao="01/06/2021", fracao_progressao="50% - Hediondo com morte", fracao_livramento="1/1 - Vedado",
            hediondo_ou_equiparado="S")
t = itens(reg([hom]))
ok(any(i["tipo"] == "livramento-consumacao-a-conferir" and i["nivel"] == "verificar" for i in t), "2: livramento deveria ficar verificar: %s" %
   [(i["nivel"], i["titulo"]) for i in t])
ok(not any(i["tipo"] == "fracao-de-livramento-diverge" and i["nivel"] == "alerta" for i in t), "2: alerta do 1/1 não deveria sair")
t = itens(reg([dict(hom, tipo_penal="§ 2º, II c/c art. 14, II: motivo fútil, tentado")]), "fracao-de-livramento-diverge")
ok(t and t[0]["nivel"] == "alerta", "2: tentado declarado no RSPE mantém o alerta do 1/1: %s" % t)

# ---- 3. saída temporária: reincidência pelas datas ----
FICHA = {"unidade": "CENTRO PENAL AGROINDUSTRIAL DA GAMELEIRA", "conduta": "OTIMA", "data_impressao": "20.10.2026", "eventos": [], "trabalho": []}


def frac_st(r):
    x = rv.saida_temporaria(r, FICHA, {}, None, False, HOJE)
    return next((i for i in x["st_itens"] if "da pena cumprida" in i["txt"]), None)


# marcado reincidente, mas tinha 18 anos no fato (desmentido pelas datas): 1/6
jov = crime(data_infracao="10/05/2019", reincidente_comum="S")
i = frac_st(reg([jov], pena_total="8a0m0d", pena_cumprida="1a5m0d", data_nascimento="01/04/2001"))
ok(i and i["ok"] is True and i["txt"].startswith("1/6"), "3: desmentido pelas datas deveria exigir 1/6: %s" % i)
# marcado sem base no RSPE: 1/6 alcançado, 1/4 não - a conferir
i = frac_st(reg([dict(jov)], pena_total="8a0m0d", pena_cumprida="1a5m0d"))
ok(i and i["ok"] is None and "atendido se primário" in i["txt"], "3: marcado sem base deveria ficar a conferir: %s" % i)
# reincidência demonstrada no RSPE: 1/4
ant = crime(processo_criminal=P2, data_infracao="01/01/2014", data_sentenca="01/01/2015", transito_mp="01/02/2015", transito_processo="01/02/2015")
i = frac_st(reg([jov, ant], pena_total="8a0m0d", pena_cumprida="1a5m0d"))
ok(i and i["ok"] is False and i["txt"].startswith("1/4"), "3: reincidente demonstrado deveria exigir 1/4: %s" % i)

# ---- 4. selo de hediondo: milícia e comando ----
mil = crime(artigo="ART 288-A: Constituição de milícia privada", tipo_penal="CAPUT", pena_imposta="6 ano(s), 0 mês(es) e 0 dia(s)",
            data_infracao="01/03/2021", fracao_progressao="50% - Milícia")
t = itens(reg([mil]))
ok(not any(i["tipo"] == "seeu-tratou-como-hediondo-mas-o-tipo-nao-consta" for i in t), "4: milícia não é 'tratou como hediondo'")
ok(any(i["tipo"] == "percentual-de-progressao-confere" for i in t), "4: milícia 50% confere")
com = crime(artigo="ART 157: Roubo", tipo_penal="§ 2º, II: concurso", pena_imposta="8 ano(s), 0 mês(es) e 0 dia(s)",
            data_infracao="01/04/2026", comando_orcrim="S", vga="S", fracao_progressao="75% - Comando", fracao_livramento="1/1 - Vedado")
ok(not itens(reg([com]), "seeu-tratou-como-hediondo-mas-o-tipo-nao-consta"), "4: comando com 75% não é 'tratou como hediondo'")
ok(itens(reg([crime(fracao_progressao="2/5 - Hediondo")]), "seeu-tratou-como-hediondo-mas-o-tipo-nao-consta"),
   "4: furto com 2/5 continua com o alerta")

# ---- 5. trânsito só para o MP ----
a5 = crime(processo_criminal=P2, data_infracao="01/01/2014", data_sentenca="01/01/2015", transito_mp="10/01/2015", transito_processo="")
b5 = crime(data_infracao="01/03/2015", data_sentenca="01/01/2016")
R = rr.reincidencia_pelas_datas(b5, [a5, b5])
ok(R["estado"] == "indeterminado" and R["so_transito_mp"] and "trânsito só para o MP" in R["motivo"], "5: só MP não demonstra: %s" % R)
R = rr.reincidencia_pelas_datas(b5, [dict(a5, transito_processo="10/02/2015"), b5])
ok(R["estado"] == "reincidente", "5: com o trânsito do processo é reincidente")

# ---- 6. depuração com período de prova ----
a6 = crime(processo_criminal=P2, data_infracao="01/01/2010", data_sentenca="01/06/2010", transito_mp="01/01/2011",
           transito_processo="01/01/2011", extinto="Sim", data_extincao="01/06/2016",
           extincao_motivo="Cumprimento do período de prova do livramento condicional")
b6 = crime(data_infracao="01/03/2021")
R = rr.reincidencia_pelas_datas(b6, [a6, b6])
ok(R["estado"] == "indeterminado" and R["depuracao_a_conferir"] and "período de prova" in R["motivo"], "6: livramento: %s" % R)
R = rr.reincidencia_pelas_datas(b6, [dict(a6, extincao_motivo="Cumprimento da pena"), b6])
ok(R["estado"] == "reincidente", "6: extinção pelo cumprimento continua reincidente")
R = rr.reincidencia_pelas_datas(dict(b6, data_infracao="01/03/2015"), [a6, dict(b6, data_infracao="01/03/2015")])
ok(R["estado"] == "reincidente", "6: fato a menos de 5 anos do trânsito continua reincidente")

# ---- 7. Título XII ----
x7 = crime(artigo="ART 359-L: Abolição violenta do Estado Democrático de Direito", tipo_penal="CAPUT", pena_imposta="6 ano(s), 0 mês(es) e 0 dia(s)",
           data_infracao="08/01/2023", vga="S", fracao_progressao="25% - Primário com violência")
t = itens(reg([x7]), "percentual-de-progressao-diverge")
ok(t and t[0]["nivel"] == "verificar" and "ADIs 7966" in t[0]["detalhe"], "7: 359-L deveria ficar verificar com 1/6: %s" % t)
ok(rg.titulo_xii("359-L") and rg.titulo_xii("359-M-A") and not rg.titulo_xii("359-H") and not rg.titulo_xii("157"), "7: rol do Título XII")
ok(itens(reg([crime(artigo="ART 157: Roubo", tipo_penal="CAPUT", vga="S", data_infracao="08/01/2023",
                    fracao_progressao="25% - Primário com violência")]), "percentual-de-progressao-confere"), "7: roubo segue 25%")

# ---- 8. saída para estudo ----
x = rv.saida_temporaria(reg([crime(data_infracao="10/05/2025")], pena_total="2a0m0d", pena_cumprida="1a0m0d"), FICHA, {}, None, False, HOJE)
ok(any("Saída para estudo" in i["txt"] for i in x["st_itens"]) and not x["st_ok"], "8: estudo deveria aparecer: %s" % x["st_itens"])
x = rv.saida_temporaria(reg([crime(data_infracao="10/05/2025", artigo="ART 157: Roubo", vga="S")], pena_total="6a0m0d"), FICHA, {}, None, False, HOJE)
ok(not any("Saída para estudo" in i["txt"] for i in x["st_itens"]), "8: crime violento não tem estudo")

# ---- 9. crime a crime e outra execução sem marcação ----
a9 = crime(data_infracao="01/01/2017", data_sentenca="01/01/2023", transito_mp="01/02/2023", transito_processo="01/02/2023")
b9 = crime(processo_criminal=P3, data_infracao="01/03/2022", data_sentenca="01/06/2022", transito_mp="01/07/2022", transito_processo="01/07/2022")
outra = crime(processo_criminal=P2, data_infracao="01/01/2018", data_sentenca="01/06/2019", transito_mp="01/07/2019",
              transito_processo="01/07/2019", _execucao="0009999-99.2019.8.12.0001")
t = [i for i in itens(reg([a9, b9], pena_total="4a0m0d", _outras_condenacoes=[outra])) if i.get("ref") == ra._nome(a9)
     and i["tipo"] in ("percentual-de-progressao-diverge", "reincidencia-crime-a-crime-progressao")]
ok(t and t[0]["tipo"] == "percentual-de-progressao-diverge" and t[0]["nivel"] == "alerta", "9: alerta 16%% x 1/6 deveria ficar: %s" % t)

# ---- 10. art. 148 ----
ok(rg.vga_esperado("148") is None and rg.vga_esperado("157") == "S", "10: 148 fora da lista S")

# ---- 11. convenção da unificação pendente (data-base + lapso) ----
import inspect
ok("ini + timedelta(days=max(0, lap))" in inspect.getsource(rv), "11: estimativa da unificação na convenção do SEEU")

# ---- 12. Lei 15.402: inciso IV ----
r12 = reg([crime(processo_criminal=P3, data_infracao="01/06/2026", reincidente_comum="S", fracao_progressao="30% - Reincidente"),
           crime(processo_criminal=P2, data_infracao="01/01/2019", data_sentenca="01/06/2019", transito_mp="01/01/2020",
                 transito_processo="01/01/2020")])
t = [i for i in itens(r12, "percentual-de-progressao-diverge") if P3 in i["ref"]]
ok(t and t[0]["nivel"] == "verificar" and "inciso IV, que continua no texto" in t[0]["detalhe"], "12: inciso IV: %s" % t)

# ---- 13 a 15. citações ----
src_v, src_a = inspect.getsource(rv), inspect.getsource(ra)
leia = open("LEIA-ME.txt", encoding="utf-8").read()
ok("mantido pelo TJMS" not in src_v and "mantido pelo TJMS" not in leia and "negou efeito suspensivo" in src_v
   and "negou efeito suspensivo" in leia, "13: TJMS 1421350 descrito como cautelar")
ok("fixa a data-base na última prisão" in src_a and "AgRg no REsp 2.248.958" in src_a, "14: REsp 2.248.958 como precedente da data-base")
ok("HC 1.076.656, monocrática" in src_a, "15: HC 1.076.656 como monocrática")

# ---- 16. contravenção seguida de contravenção ----
LCP = "3688/41 - Lei das Contravenções Penais"
c1 = crime(processo_criminal=P2, lei=LCP, artigo="ART 21: Vias de fato", data_infracao="01/01/2018", data_sentenca="01/06/2018",
           transito_mp="01/01/2019", transito_processo="01/01/2019")
c2 = crime(lei=LCP, artigo="ART 21: Vias de fato", data_infracao="01/03/2021")
ok(rr.reincidencia_pelas_datas(c2, [c1, c2])["estado"] != "reincidente" and "LCP, art. 7º" in rr.gera_reincidencia.__doc__
   and "favorável" in rr.gera_reincidencia.__doc__, "16: contravenção anterior não conta, e a escolha está declarada")

# ---- 17. rótulo do 1/6 no crime a crime ----
c0 = crime(processo_criminal="0000004-44.2018.8.12.0001", data_infracao="01/01/2018", data_sentenca="01/06/2019",
           transito_mp="01/07/2019", transito_processo="01/07/2019", extinto="Sim", data_extincao="01/01/2020")
b17 = dict(b9, reincidente_comum="S", fracao_progressao="20% - Reincidente")
t = [i for i in itens(reg([a9, b17, c0], pena_total="4a0m0d"), "reincidencia-crime-a-crime-progressao")]
ok(t and "1/6 da redação anterior" in t[0]["titulo"] and "percentual de reincidente" not in t[0]["titulo"], "17: rótulo: %s" % t)

if falhas:
    print("FALHOU:")
    for f in falhas:
        print("  -", f)
    sys.exit(1)
print("ok: revisão do Capítulo 3 (7.14.8) - 16% retroativo na progressão refeita, livramento sem resultado morte, saída temporária "
      "pelas datas, selo de hediondo, trânsito do MP, período depurador, Título XII, saída para estudo, crime a crime, art. 148, "
      "convenção da unificação e citações")
