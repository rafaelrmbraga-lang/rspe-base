"""Teste da segunda conferência independente (7.14.6), frente indulto e comutação: interrupção por incompatibilidade de regime
lançada no mesmo dia da prisão definitiva - ordem do SEEU (prisão e depois a interrupção) e, quando a "Pena Cumprida" impressa
mostra que o SEEU não contou o período, a interrupção corta a custódia (sem custódia contínua falsa); Decreto 11.846/2023, incisos
XV e XVI (crime patrimonial sem violência) analisados sobre o tempo excedente aos 2/3 do impeditivo; pena considerada somada em
anos/meses/dias (a mesma de 2024/2025); sursis concedido no RSPE nas hipóteses "não beneficiadas com sursis"; reincidência pelas
datas também no detalhamento de 2024/2025 que diz "primário". Casos hipotéticos, nomes fictícios.
Rodar: python teste_conf7_indulto.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_decretos as rd
import rspe_scraper as rs

falhas = []
HOJE = date(2026, 10, 21)
D = rs.to_date


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


P1 = "0000001-11.2019.8.12.0001"
P2 = "0000002-11.2019.8.12.0001"
PR = "PRISÃO/INÍCIO DE CUMPRIMENTO"
IN = "INTERRUPÇÃO"


def crime(**kw):
    c = {"processo_criminal": P1, "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto",
         "tipo_penal": "CAPUT: Subtrair, Reclusão: 1 a 4 anos", "pena_imposta": "1 ano(s), 0 mês(es) e 0 dia(s)",
         "pena_total_processo": "", "data_infracao": "10/01/2019", "data_sentenca": "10/06/2019", "transito_mp": "10/07/2019",
         "transito_processo": "10/07/2019", "extinto": "Não", "suspenso": "Não", "vga": "N", "resultado_morte": "N",
         "reincidente_comum": "N", "reincidente_especifico": "N", "comando_orcrim": "N", "regime_sentenca": "Fechado"}
    c.update(kw)
    return c


def ev(tipo, motivo, data, procs=P1):
    return {"tipo": tipo, "motivo": motivo, "data": data, "processos": procs}


def inc(tipo, compl, data, sit="CONCEDIDO", procs=""):
    return {"tipo": tipo, "motivo": "", "complemento": compl, "data": "", "data_decisao": data, "data_referencia": data,
            "processos": procs, "situacao": sit}


def reg(crimes, eventos, pena_total, cumprida="", incid=None, ger="05/10/2026", **kw):
    r = {"nome": "T", "processo_execucao": "X", "pena_total": pena_total, "pena_cumprida": cumprida, "pena_remanescente": "",
         "data_geracao_rspe": ger, "termino_previsao_seeu": "", "data_nascimento": "01/01/1980", "_sexo": "M",
         "status_execucao": "ATIVO", "regime_atual": "Fechado - ATIVO", "_crimes": crimes, "_eventos": eventos,
         "_incidentes": incid or [], "total_interrupcoes": "", "saldo_remidos": "0 dias (0 dias remidos - 0 dias perdidos)"}
    r.update(kw)
    return r


def dec(r, ano, completo=False):
    return next(x for x in rd.avaliar(r, HOJE, completo)["decretos"] if str(x["id"]) == ano)


# 1. Mesmo dia: prisão definitiva e interrupção por incompatibilidade de regime - a interrupção vai depois da prisão (ordem do
#    SEEU), qualquer que seja a ordem de entrada (registro gravado pela versão anterior, que a punha antes)
pdef = ev(PR, "PRISÃO DEFINITIVA", "28/07/2022")
iinc = ev(IN, "INCOMPATIBILIDADE DE REGIME", "28/07/2022")
for entrada in ([pdef, iinc], [iinc, pdef]):
    out = rs.eventos_cronologicos([ev(PR, "PRISÃO EM FLAGRANTE", "12/04/2021"), ev(IN, "LIBERDADE PROVISÓRIA", "14/04/2021")] + entrada)
    ok([e["tipo"] for e in out[2:]] == [PR, IN], "1: ordem do dia %s" % [e["tipo"] for e in out[2:]])


# 2. SEEU com 4 dias cumpridos (flagrante de 3 dias + o dia da prisão definitiva): o período depois da incompatibilidade não foi
#    contado - a interrupção corta, e a custódia não fica contínua desde 28/07/2022
def evs2():
    return [ev(PR, "PRISÃO EM FLAGRANTE", "12/04/2021"), ev(IN, "LIBERDADE PROVISÓRIA", "14/04/2021"),
            ev(PR, "PRISÃO DEFINITIVA", "28/07/2022"), ev(IN, "INCOMPATIBILIDADE DE REGIME", "28/07/2022")]


e2 = evs2()
cortou = rs.incompatibilidade_pelo_seeu({"pena_cumprida": "0a0m4d", "pena_total": "5a2m0d", "pena_remanescente": "5a1m26d",
                                         "data_geracao_rspe": "05/10/2026", "saldo_remidos": "0 dias"}, e2)
ok(len(cortou) == 1, "2: incompatibilidade não marcada (%s)" % cortou)
per = rs.periodos_custodia(e2)
ok(per == [(D("12/04/2021"), D("14/04/2021")), (D("28/07/2022"), D("28/07/2022"))], "2: custódia %s" % per)

# 3. SEEU que contou o período (pena cumprida coerente com o cumprimento contínuo): a regra do programa segue (SV 56)
e3 = evs2()
ok(not rs.incompatibilidade_pelo_seeu({"pena_cumprida": "4a2m14d", "pena_total": "5a2m0d", "pena_remanescente": "0a11m16d",
                                       "data_geracao_rspe": "05/10/2026", "saldo_remidos": "0 dias"}, e3), "3: marcou sem divergência")
ok(rs.periodos_custodia(e3)[-1] == (D("28/07/2022"), None), "3: custódia contínua perdida %s" % rs.periodos_custodia(e3))
# 3b. divergência que o corte não explica (o SEEU conta mais que o corte): não marca
e3b = evs2()
ok(not rs.incompatibilidade_pelo_seeu({"pena_cumprida": "2a0m0d", "pena_total": "5a2m0d", "pena_remanescente": "3a2m0d",
                                       "data_geracao_rspe": "05/10/2026", "saldo_remidos": "0 dias"}, e3b), "3b: marcou sem explicar a diferença")

# 4. Na importação (derivar): comutações de 2023/2024/2025 não ficam "a verificar" por custódia inexistente
cs4 = [crime(lei="10826/03 - Estatuto do Desarmamento", artigo="ART 12 - Posse irregular de arma de fogo de uso permitido",
             tipo_penal="CAPUT: Possuir, Detenção: 1 a 3 anos", pena_imposta="4 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="12/04/2021", data_sentenca="13/07/2022",
             transito_processo="20/07/2022", transito_mp="20/07/2022", regime_sentenca="Semiaberto")]
r4 = reg(cs4, evs2(), "4a0m0d", "0a0m4d", regime_atual="Semiaberto - ATIVO", pena_remanescente="3a11m26d",
         total_interrupcoes="4a2m0d")
rs.derivar(r4, r4["_crimes"], r4["_eventos"], r4["_incidentes"])
ok(any(e.get("_incompat_corta") for e in r4["_eventos"]), "4: derivar não marcou a incompatibilidade")
for ano in ("2023", "2024", "2025"):
    x = dec(r4, ano)
    ok(x["s"] == "nao", "4: %s %s - %s" % (ano, x["s"], x.get("mot")))
ok("livramento revogado" not in str(r4), "4: 'livramento revogado' citado sem livramento")

# 5. Decreto 11.846/2023, XV e XVI: 2/3 do tráfico cumpridos; o excedente (1 ano) alcança o inciso XVI (5 meses), embora não
#    alcance o art. 2º, I, a comutação nem o XV (1/4 da soma de 5 anos; só sobre a pena patrimonial atenderia - tese) - A VERIFICAR
#    (valor do bem)
cs5 = [crime(processo_criminal=P1, lei="11343/06 - Lei de Drogas", artigo="ART 33: Tráfico ilícito de drogas",
             tipo_penal="CAPUT: Importar, exportar, Reclusão: 5 a 15 anos", pena_imposta="6 ano(s), 0 mês(es) e 0 dia(s)",
             reincidente_comum="S"),
       crime(processo_criminal=P2, pena_imposta="2 ano(s), 0 mês(es) e 0 dia(s)", reincidente_comum="S"),
       crime(processo_criminal="0000003-11.2019.8.12.0001", lei="9503/97 - Código de Trânsito Brasileiro",
             artigo="ART 311: Trafegar em velocidade incompatível", tipo_penal="CAPUT: Trafegar, Detenção: 6 meses a 1 ano",
             pena_imposta="3 ano(s), 0 mês(es) e 0 dia(s)", reincidente_comum="S")]
r5 = reg(cs5, [ev(PR, "PRISÃO DEFINITIVA", "01/01/2019")], "11a0m0d", "7a9m4d")
x5 = dec(r5, "2023", True)
ok(x5["s"] == "ver" and "art. 2º, XVI" in (x5.get("mot") or "") and "salário mínimo" in (x5.get("mot") or ""), "5: %s - %s" % (x5["s"], x5.get("mot")))
h15 = next((h for h in x5.get("hips") or [] if h["dispositivo"] == "art. 2º, XV"), {})
ok(not h15.get("ok") and "tese: só sobre a pena dos crimes patrimoniais" in (h15.get("mot") or ""), "5: XV pela soma %s" % h15)
ok("alcança só as penas de art. 155 CP" in (x5.get("mot") or ""), "5: crimes alcançados %s" % x5.get("mot"))
# 5b. sem crime patrimonial: o inciso não se aplica (não fica a verificar)
r5b = reg([cs5[0], cs5[2]], [ev(PR, "PRISÃO DEFINITIVA", "01/01/2019")], "9a0m0d", "7a9m4d")
x5b = dec(r5b, "2023", True)
ok(x5b["s"] != "ver" or "XV" not in (x5b.get("mot") or ""), "5b: %s - %s" % (x5b["s"], x5b.get("mot")))
# 5c. tempo insuficiente para o XV (1/4 da pena patrimonial): não atinge por ele
r5c = reg([crime(pena_imposta="4 ano(s), 0 mês(es) e 0 dia(s)", reincidente_comum="S")], [ev(PR, "PRISÃO DEFINITIVA", "01/10/2023")],
          "4a0m0d", "3a0m0d")
x5c = dec(r5c, "2023", True)
ok(x5c["s"] == "nao", "5c: %s - %s" % (x5c["s"], x5c.get("mot")))

# 6. Pena considerada pela soma em anos/meses/dias (1a6m20d + 2a4m + 1a8m = 5a6m20d), a mesma da análise de 2024/2025
cs6 = [crime(pena_imposta="1 ano(s), 6 mês(es) e 20 dia(s)"), crime(processo_criminal=P2, pena_imposta="2 ano(s), 4 mês(es) e 0 dia(s)"),
       crime(processo_criminal="0000003-11.2019.8.12.0001", pena_imposta="1 ano(s), 8 mês(es) e 0 dia(s)")]
x6 = dec(reg(cs6, [ev(PR, "PRISÃO DEFINITIVA", "01/01/2019")], "5a6m20d", "7a0m0d"), "2023")
ok((x6.get("detalhe") or {}).get("pena") == 5 * 365 + 6 * 30 + 20, "6: pena considerada %s" % (x6.get("detalhe") or {}).get("pena"))

# 7. Sursis concedido no RSPE, sem revogação: a comutação do art. 3º (não beneficiadas com sursis) não se afirma
cs7 = [crime(pena_imposta="3 ano(s), 0 mês(es) e 0 dia(s)")]
r7 = reg(cs7, [ev(PR, "PRISÃO DEFINITIVA", "01/06/2022")], "3a0m0d", "4a4m0d", incid=[inc("SURSIS", "", "21/07/2020")])
x7 = dec(r7, "2023")
ok(x7["s"] == "ver" and "sursis" in (x7.get("mot") or ""), "7: %s - %s" % (x7["s"], x7.get("mot")))
x7b = dec(reg(cs7, [ev(PR, "PRISÃO DEFINITIVA", "01/06/2022")], "3a0m0d", "4a4m0d"), "2023")
ok(x7b["s"] == "cabe", "7b: sem sursis %s - %s" % (x7b["s"], x7b.get("mot")))

# 8. 2024/2025: RSPE marca primário, mas as datas mostram reincidência - o detalhamento não afirma "primário" sozinho
cs8 = [crime(processo_criminal=P2, artigo="ART 147: Ameaça", tipo_penal="CAPUT: Ameaçar, Detenção: 1 a 6 meses",
             pena_imposta="0 ano(s), 2 mês(es) e 0 dia(s)", data_infracao="10/01/2014", data_sentenca="10/06/2014",
             transito_processo="21/07/2020", transito_mp="21/07/2020"),
       crime(pena_imposta="9 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="12/04/2021", data_sentenca="13/07/2022",
             transito_processo="20/07/2022", transito_mp="20/07/2022")]
r8 = reg(cs8, [ev(PR, "PRISÃO DEFINITIVA", "28/07/2022")], "9a2m0d", "4a2m0d", pena_remanescente="5a0m0d")
rs.derivar(r8, r8["_crimes"], r8["_eventos"], r8["_incidentes"])
for k in ("indulto_2024_detalhe", "comutacao_2024_detalhe", "indulto_2025_detalhe"):
    t = r8.get(k) or ""
    ok(not t or "primário" not in t or "Reincidência pelas datas" in t, "8: %s afirma primário sem a ressalva: %s" % (k, t[:300]))

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for f in falhas:
        print(" -", f)
    sys.exit(1)
print("OK - teste_conf7_indulto")
