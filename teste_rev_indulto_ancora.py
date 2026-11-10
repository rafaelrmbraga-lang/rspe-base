"""Revisão do indulto (7.16.2), achado A1: âncora do SEEU zerada na data do decreto e tempo pelos eventos abaixo de 180 dias.
Pena curta (5 meses, 1/3 = 50 dias) com 68 dias de prisão provisória pelo próprio processo, antes da sentença, num decreto que manda
computar a detração (Decreto 5.620/2005, art. 3º). O SEEU atual não conta esse tempo (âncora zerada em 25/12/2005): antes, o
programa dava "não atinge, faltavam 50 dias", embora a ressalva dissesse "contada como pena cumprida"; agora usa os eventos e deixa
o favorável A VERIFICAR, como já fazia acima de 180 dias. Caso fictício (SIMULADO CASO 901).
Rodar: python teste_rev_indulto_ancora.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_decretos as rd
import rspe_scraper as rs

P1, P2 = "9900901-00.2005.8.12.0001", "9900902-00.2006.8.12.0001"
falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def crime(**kw):
    c = {"processo_criminal": P1, "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto",
         "tipo_penal": "§ 1º: Furto noturno, Reclusão: 1 ano e 4 meses a 5 anos e 4 meses", "pena_imposta": "0 ano(s), 5 mês(es) e 0 dia(s)",
         "pena_total_processo": "", "data_infracao": "17/06/2005", "data_sentenca": "12/09/2005", "transito_mp": "12/09/2005",
         "transito_processo": "12/09/2005", "extinto": "Não", "suspenso": "Não", "vga": "N", "resultado_morte": "N",
         "reincidente_comum": "N", "reincidente_especifico": "N", "comando_orcrim": "N", "regime_sentenca": "Semiaberto",
         "fracao_progressao": "1/6 - Comum"}
    c.update(kw)
    return c


def ev(t, m, d, p=""):
    return {"tipo": t, "motivo": m, "data": d, "processos": p}


def reg(eventos):
    return {"nome": "SIMULADO CASO 901", "processo_execucao": "9900901-00.2026.8.12.0001", "pena_total": "4a5m0d", "pena_cumprida": "3a0m1d",
            "pena_remanescente": "1a4m29d", "data_geracao_rspe": "05/10/2026", "termino_previsao_seeu": "", "data_nascimento": "01/01/1985",
            "_sexo": "M", "status_execucao": "ATIVO", "regime_atual": "Semiaberto - ATIVO", "total_interrupcoes": "",
            "saldo_remidos": "0 dias (0 dias remidos - 0 dias perdidos)",
            "_crimes": [crime(), crime(processo_criminal=P2, data_infracao="09/06/2006", data_sentenca="10/01/2007", transito_mp="10/02/2007",
                                       transito_processo="10/02/2007", pena_imposta="4 ano(s), 0 mês(es) e 0 dia(s)",
                                       tipo_penal="CAPUT: Furto, Reclusão: 1 a 4 anos")],
            "_eventos": eventos, "_incidentes": []}


PR, IN = "PRISÃO/INÍCIO DE CUMPRIMENTO", "INTERRUPÇÃO"
EVS = [ev(PR, "PRISÃO EM FLAGRANTE", "17/06/2005", P1), ev(IN, "LIBERDADE PROVISÓRIA", "24/08/2005"),
       ev(PR, "PRISÃO EM FLAGRANTE", "09/06/2006", P2), ev(IN, "LIBERDADE PROVISÓRIA", "09/06/2009")]
HOJE = date(2026, 11, 10)

# 1) 68 dias de prisão provisória (17/06 a 24/08/2005) contra 50 exigidos: favorável a verificar, com o tempo pelos eventos
x = next(d for d in rd.avaliar(reg(EVS), HOJE)["decretos"] if d["id"] == "2005")
ok(x["s"] == "ver", "2005: âncora zerada com 68 dias pelos eventos deve ficar a verificar, veio %r (%s)" % (x["s"], x.get("mot")))
ok("dá zero" in (x.get("mot") or "") and "pelos eventos" in (x.get("mot") or ""), "2005: motivo deve citar a âncora zerada e os eventos: %s" % x.get("mot"))
ok((x.get("detalhe") or {}).get("cumprido", 0) >= 50, "2005: cumprido pelos eventos deve alcançar 50 dias: %r" % (x.get("detalhe") or {}).get("cumprido"))

# 2) a mesma conta pela função comum: no modo "eventos" a âncora zerada cede aos eventos; sem modo (exibição) nada muda
per = [(date(2005, 6, 17), date(2005, 8, 24)), (date(2006, 6, 9), date(2009, 6, 9))]
r = reg(EVS)
e = rs.cumprido_decreto_info(r, per, [], date(2005, 12, 25), [], r["_crimes"], "eventos")
ok(e["dias"] >= 50 and e["origem"] == "ancora", "modo eventos: deveria usar os eventos (%r)" % e)
a = rs.cumprido_decreto_info(r, per, [], date(2005, 12, 25), [], r["_crimes"], "ancora")
ok(a["dias"] == 0 and a.get("alt"), "modo âncora: fica a âncora (0) com o aviso de alternativa (%r)" % a)

# 3) sem prisão nenhuma até a data, nada muda: continua "não atinge"/fora
x2 = next(d for d in rd.avaliar(reg(EVS[2:]), HOJE)["decretos"] if d["id"] == "2005")
ok(x2["s"] in ("nao", "fora"), "2005 sem prisão até a data: não pode virar favorável, veio %r" % x2["s"])

if falhas:
    print("FALHAS:\n- " + "\n- ".join(falhas))
    sys.exit(1)
print("ok: revisão do indulto 7.16.2 - âncora do SEEU zerada com poucos dias pelos eventos (pena curta, prisão provisória)")
