"""Pontos abertos do relatório do indulto (7.16.4), cada um com caso fictício (SIMULADO CASO 911 a 915):
1. Decretos 2019 a 2021, art. 2º, II c/c § 2º (agente de segurança, CRIME CULPOSO): a hipótese não aferida (sinal "?") só para quem
   tem crime culposo - antes, quase todo assistido recebia o sinal nesses três decretos.
2. 2024/2025: a interrupção que entra como falta a verificar usa a mesma janela do art. 6º (12 meses com o dia do começo incluído:
   de 26/12 do ano anterior) - antes começava em 25/12.
3. Decreto 11.302/2022: sentença registrada depois do trânsito (dado incoerente), com o trânsito anterior à publicação - vale o
   trânsito e fica a verificar, como em 2024/2025 (antes: "não alcançado").
4. Livramento confirmado pelo operador: a reanálise dos decretos aplica também a camada do nascimento divergente.
5. Nota de mora estatal na fuga: os 6 meses contam da recaptura (a apuração só começa com ela), não da evasão.
Rodar: python teste_rev_indulto_pontos.py"""
import inspect
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_decretos as rd  # noqa: E402
import rspe_scraper as rs  # noqa: E402
import rspe_view as rv  # noqa: E402

falhas = []
HOJE = date(2026, 11, 11)


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def crime(**kw):
    c = {"processo_criminal": "9900911-00.2016.8.12.0001", "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto",
         "tipo_penal": "§ 4º: Furto qualificado, Reclusão: 2 a 8 anos", "pena_imposta": "6 ano(s), 0 mês(es) e 0 dia(s)",
         "pena_total_processo": "", "data_infracao": "10/01/2016", "data_sentenca": "10/06/2016", "transito_mp": "10/07/2016",
         "transito_processo": "10/07/2016", "extinto": "Não", "suspenso": "Não", "vga": "N", "resultado_morte": "N",
         "reincidente_comum": "N", "reincidente_especifico": "N", "comando_orcrim": "N", "regime_sentenca": "Semiaberto",
         "fracao_progressao": "1/6 - Comum"}
    c.update(kw)
    return c


def ev(t, m, d, p=""):
    return {"tipo": t, "motivo": m, "data": d, "processos": p}


PR, IN = "PRISÃO/INÍCIO DE CUMPRIMENTO", "INTERRUPÇÃO"


def reg(crimes, eventos, incidentes=None, n=911):
    return {"nome": "SIMULADO CASO %d" % n, "processo_execucao": "99009%02d-00.2026.8.12.0001" % (n - 900), "pena_total": "6a0m0d",
            "pena_cumprida": "", "pena_remanescente": "", "data_geracao_rspe": "05/10/2026", "termino_previsao_seeu": "",
            "data_nascimento": "01/01/1985", "_sexo": "M", "status_execucao": "ATIVO", "regime_atual": "Semiaberto - ATIVO",
            "total_interrupcoes": "", "saldo_remidos": "0 dias (0 dias remidos - 0 dias perdidos)",
            "_crimes": crimes, "_eventos": eventos, "_incidentes": incidentes or []}


# 1) 2019 a 2021: furto (sem crime culposo) não recebe o sinal; homicídio culposo recebe
EVS = [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2016", "9900911-00.2016.8.12.0001")]
dec = {d["id"]: d for d in rd.avaliar(reg([crime()], EVS), HOJE)["decretos"]}
for a in ("2019", "2020", "2021"):
    ok(a in dec and not dec[a].get("naf"), "%s: furto não pode receber o sinal da hipótese do crime culposo (%r)" % (a, dec.get(a, {}).get("naf")))
cul = crime(artigo="ART 121: Homicídio simples", tipo_penal="§ 3º: Homicídio culposo, Detenção: 1 a 3 anos",
            pena_imposta="3 ano(s), 0 mês(es) e 0 dia(s)")
dec = {d["id"]: d for d in rd.avaliar(reg([cul], EVS, n=912), HOJE)["decretos"]}
ok(any(dec.get(a, {}).get("naf") for a in ("2019", "2020", "2021")), "homicídio culposo: a hipótese do agente de segurança deve ficar como não aferida (%r)"
   % {a: (dec.get(a, {}).get("s"), dec.get(a, {}).get("naf")) for a in ("2019", "2020", "2021")})
ok(rs.crime_culposo({"lei": "9503/97 - CTB", "artigo": "ART 302: Homicídio culposo na direção"}) and not rs.crime_culposo(crime()),
   "identificação do crime culposo")

# 2) janela da interrupção como falta: a mesma do art. 6º
src = inspect.getsource(rs._analise_decretos_modo)
ok("ref - timedelta(days=dias_anos(1, ref) - 1) <= ult_i" in src, "janela da interrupção como falta deve começar em 26/12 do ano anterior")
lim = date(2024, 12, 25) - __import__("datetime").timedelta(days=rs.dias_anos(1, date(2024, 12, 25)) - 1)
ok(lim == date(2023, 12, 26), "12 meses até 25/12/2024 começam em 26/12/2023 (veio %s)" % lim)

# 3) 2022: sentença registrada depois do trânsito, trânsito antes da publicação - a verificar, não "não alcançado"
inc = crime(processo_criminal="9900913-00.2016.8.12.0001", lei="11343/06 - Drogas", artigo="ART 28: Porte para consumo",
            tipo_penal="CAPUT", pena_imposta="0 ano(s), 6 mês(es) e 0 dia(s)")
inc = crime(processo_criminal="9900913-00.2021.8.12.0001", artigo="ART 155: Furto", tipo_penal="CAPUT: Furto, Reclusão: 1 a 4 anos",
            pena_imposta="1 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="10/01/2021", data_sentenca="10/03/2023",
            transito_mp="01/06/2022", transito_processo="01/06/2022")
r3 = reg([inc], [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2021", "9900913-00.2021.8.12.0001")], n=913)
o = rs.analise_decreto_2022(r3, r3["_crimes"], r3["_eventos"], [])
t = o.get("indulto_2022") or ""
ok("não alcançado" not in t.lower() or "dado incoerente" in t, "2022: sentença incoerente não pode tirar o crime do alcance: %s" % t[:300])
ok("A VERIFICAR" in t.upper() or "VERIFICAR" in t.upper(), "2022: sentença incoerente deve deixar o resultado a verificar: %s" % t[:300])

# 4) livramento confirmado: a reanálise aplica a camada do nascimento divergente
src = inspect.getsource(rv.modelo)
i0 = src.index('r["_lc_confirmado"] = True')
ok("nascimento_divergente_decretos" in src[i0:i0 + 1400], "reanálise do livramento confirmado deve aplicar o nascimento divergente")

# 5) mora estatal: conta da recaptura
fuga = {"tipo": "FALTA GRAVE", "complemento": "FUGA em 01/01/2024", "data_referencia": "01/01/2024", "data_decisao": "01/12/2024",
        "situacao": "Homologado"}
rot = rs._rotulo_incidente(fuga)
evs5 = [ev(IN, "FUGA", "01/01/2024"), ev(PR, "RECAPTURA", "01/09/2024")]
sem = rs.nota_mora_estatal([fuga], [rot], None)[0]
com = rs.nota_mora_estatal([fuga], [rot], evs5)[0]
ok("mora estatal" in sem, "sem eventos (como antes): 11 meses depois do fato - com a nota")
ok("mora estatal" not in com, "com a recaptura em 01/09/2024 e a homologação 3 meses depois: sem a nota (%s)" % com)
fuga2 = dict(fuga, data_decisao="01/06/2025")
com2 = rs.nota_mora_estatal([fuga2], [rs._rotulo_incidente(fuga2)], evs5)[0]
ok("da recaptura (01/09/2024)" in com2, "homologação 9 meses depois da recaptura: nota contada da recaptura (%s)" % com2)

if falhas:
    print("FALHAS:\n- " + "\n- ".join(falhas))
    sys.exit(1)
print("ok: pontos abertos do indulto - hipótese do crime culposo (2019-2021), janela da interrupção, sentença incoerente em 2022, "
      "nascimento divergente com livramento confirmado e mora estatal da recaptura")
