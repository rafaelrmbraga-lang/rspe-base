"""Quarta rodada de correções (7.14.3), frente das demais abas (progressão, livramento, auditoria, indulto e prescrição): saída
temporária sem somar duas vezes a detração da ficha; 16% no lugar do 1/6 só sem violência; estimativa com a data-base legal na
Auditoria; soma das penas por anos, meses e dias; último regime inicial válido; falta nos 12 meses com a mesma referência na nota e
na coluna; concordância da execução suspensa; "faltavam" pelos eventos também ao lado da falta grave; indulto concedido sem baixa
(pode ter sido só da multa) na aba Indulto; reincidência pela ficha também na prescrição; quadro do art. 180 coerente com o
cumprimento posterior; forma favorável pela conta direta e detração com a soltura que não se efetivou.
Casos hipotéticos, nomes fictícios. Rodar: python teste_conf4_demais.py"""
import copy
import sys
import types
from datetime import date, timedelta
from fractions import Fraction

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_auditoria as ra
import rspe_decretos as rd
import rspe_ficha as rf
import rspe_prescricao as rp
import rspe_scraper as rs
import rspe_view as rv

falhas = []
HOJE = date(2026, 10, 21)


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


AR = "FIXAÇÃO/ALTERAÇÃO DE REGIME"
PR = "PRISÃO/INÍCIO DE CUMPRIMENTO"
P1, P2 = "0000001-11.2020.8.12.0001", "0000002-22.2025.8.12.0001"


def inc(tipo, compl, dec, ref, sit="CONCEDIDO", processos=""):
    return {"tipo": tipo, "motivo": "", "complemento": compl, "data": "", "data_decisao": dec, "data_referencia": ref,
            "processos": processos, "situacao": sit}


def ev(tipo, motivo, data, **kw):
    return dict({"tipo": tipo, "motivo": motivo, "data": data, "processos": P1}, **kw)


def crime(**kw):
    c = {"processo_criminal": P1, "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto", "tipo_penal": "CAPUT: Subtrair",
         "pena_imposta": "2 ano(s), 0 mês(es) e 0 dia(s)", "data_infracao": "10/01/2021", "data_sentenca": "10/06/2021",
         "transito_mp": "10/07/2021", "transito_processo": "10/07/2021", "extinto": "Não", "suspenso": "Não", "vga": "N",
         "resultado_morte": "N", "reincidente_comum": "N", "reincidente_especifico": "N", "comando_orcrim": "N",
         "fracao_progressao": "1/6 - Comum", "fracao_livramento": "1/3 - Comum", "regime_sentenca": "Fechado"}
    c.update(kw)
    return c


def reg(crimes, incs=(), eventos=(), **kw):
    r = {"nome": "Teste Ficticio", "regime_atual": "Fechado - ATIVO", "pena_total": "2a0m0d", "pena_cumprida": "0a6m0d",
         "pena_remanescente": "1a6m0d", "data_geracao_rspe": "01/10/2026", "data_base_seeu": "", "_crimes": crimes,
         "_incidentes": list(incs), "_eventos": list(eventos), "data_nascimento": "01/01/1980", "status_execucao": "ATIVO"}
    r.update(kw)
    return r


def itens(r, tipo=None):
    its = ra.auditar(copy.deepcopy(r), HOJE)["aud_itens"]
    return [i for i in its if tipo is None or i.get("tipo") == tipo]


# ---- 1: saída temporária - a custódia da guia sem cálculo já inclui a prisão provisória da ficha: não soma de novo ----
r = reg([crime(data_infracao="22/12/2023", pena_imposta="4 ano(s), 4 mês(es) e 0 dia(s)")], [],
        [ev(PR, "PRISÃO EM FLAGRANTE", "17/08/2025")], pena_total="0a0m0d", pena_cumprida="0a0m0d", pena_remanescente="0a0m0d",
        regime_atual="Semiaberto - ATIVO", _detracao_ficha=[("29/12/2023", "15/08/2024", P1)])
cs = rv.custodia_sem_calculo(r)
ok(cs and cs.get("ficha_dias") == 231, "1: custódia sem cálculo não informa os dias da ficha já incluídos: %s" % cs)
_dx, _sn = rf._detracao_x_ficha, rf.solturas_nao_lancadas
rf._detracao_x_ficha = lambda r_, f_, so_periodos=False: [(date(2023, 12, 29), date(2024, 8, 15), 231)]
rf.solturas_nao_lancadas = lambda *a, **k: []
try:
    st = rv.saida_temporaria(r, {"unidade": "", "eventos": []}, {}, hoje=HOJE)
finally:
    rf._detracao_x_ficha, rf.solturas_nao_lancadas = _dx, _sn
txt = next((i["txt"] for i in (st.get("st_itens") if isinstance(st, dict) else st) if "da pena cumprida" in i["txt"]), "") if st else ""
ok("já incluída a prisão provisória" in txt and "somada a prisão" not in txt, "1: detração da ficha somada duas vezes: %s" % txt)

# ---- 2: 16% no lugar do 1/6 só no crime sem violência (lesão corporal dolosa mantém o 1/6 do SEEU) ----
ok(rv._fr_prog_refeita(crime(data_infracao="05/12/2022")) == Fraction(16, 100), "2: furto de 2022 deveria ir a 16%")
ok(rv._fr_prog_refeita(crime(artigo="ART 129: Lesão corporal", tipo_penal="CAPUT: Ofender", data_infracao="05/12/2022")) == Fraction(1, 6),
   "2: lesão corporal dolosa (violência elementar) foi a 16%")
ok(rv._fr_prog_refeita(crime(data_infracao="05/12/2022", reincidente_comum="S")) == Fraction(1, 6), "2: reincidente foi a 16%")

# ---- 3: guia nova com a pessoa presa - a Auditoria estima a progressão com a data-base legal e as remições abatidas ----
r = reg([crime(data_infracao="01/07/2025", pena_imposta="2 ano(s), 0 mês(es) e 0 dia(s)")],
        [inc(AR, "Aberto - Regime Inicial", "", "02/09/2020"), inc(AR, "Semiaberto - Regime Inicial", "", "17/01/2026"),
         inc("REMIÇÃO", "30 Dia(s) Remido(s)", "10/03/2026", "10/03/2026")],
        [ev(PR, "PRISÃO EM FLAGRANTE", "08/07/2025"), ev(PR, "INÍCIO DO CUMPRIMENTO REGIME SEMIABERTO", "17/01/2026")],
        data_base_seeu="17/01/2026", regime_atual="Semiaberto - ATIVO", pena_cumprida="0a9m0d", pena_remanescente="1a3m0d",
        seeu_fracoes_progressao=["Comum (1/6): 0a4m0d"], progressao_previsao_seeu=rs.fmt(date(2026, 1, 17) + timedelta(days=121)))
g = itens(r, "data-base-no-inicio-da-guia-nova-com-a-pessoa-presa")
ok(g and g[0].get("prog_estimada"), "3: Auditoria sem a estimativa com a data-base legal: %s" % [i["titulo"] for i in itens(r)])
if g and g[0].get("prog_estimada"):
    # 193 dias de deslocamento x (1 - 1/6) = 160; mais os 30 dias remidos que a previsão (data-base + lapso inteiro) não descontou
    esp = date(2026, 1, 17) + timedelta(days=121) - timedelta(days=160 + 30)
    ok(g[0]["prog_estimada"] == rs.fmt(esp) and "remições abatidas" in g[0]["detalhe"], "3: estimativa: %s %s" % (g[0]["prog_estimada"], rs.fmt(esp)))

# ---- 4: soma das penas por anos, meses e dias (como o SEEU), não em dias corridos ----
cs4 = [crime(pena_imposta="1 ano(s), 0 mês(es) e 12 dia(s)"), crime(pena_imposta="0 ano(s), 11 mês(es) e 20 dia(s)"),
       crime(pena_imposta="27 ano(s), 1 mês(es) e 10 dia(s)")]
ok(ra._soma_amd_txt(cs4) == "29a1m12d", "4: soma por componentes: %s" % ra._soma_amd_txt(cs4))
ok(ra._soma_amd_txt(cs4, cs4[:2]) == "27a1m10d", "4: soma sem as indultadas: %s" % ra._soma_amd_txt(cs4, cs4[:2]))

# ---- 5: o último regime inicial válido rege (aberto antigo, fechado relançado depois de interrupção) ----
r = reg([crime(data_infracao="01/10/2017", pena_imposta="6 ano(s), 0 mês(es) e 0 dia(s)")],
        [inc(AR, "Aberto - Regime Inicial", "", "18/01/2019"), inc(AR, "Fechado - Regime Inicial", "", "06/05/2020")],
        [ev(PR, "PRISÃO EM FLAGRANTE", "07/10/2017"), ev("INTERRUPÇÃO", "LIBERDADE PROVISÓRIA", "09/10/2017"),
         ev(PR, "PRISÃO EM FLAGRANTE", "18/01/2019"), ev("INTERRUPÇÃO", "LIBERDADE PROVISÓRIA", "15/06/2019"),
         ev(PR, "PRISÃO DEFINITIVA", "06/05/2020")],
        data_base_seeu="06/05/2020", pena_total="6a0m0d")
t5 = [i["titulo"] for i in itens(r, "regime-inicial-depois-da-primeira-prisao")]
ok(not any("aberto lançado em 18/01/2019" in t for t in t5), "5: usou o primeiro regime inicial (aberto): %s" % t5)
ok(not any("sem progressão a calcular" in t for t in t5), "5: 'sem progressão a calcular' com regime inicial fechado depois: %s" % t5)

# ---- 6: nota do SEEU "fora dos 12 meses" só quando a coluna Falta também tira a falta da janela ----
nota = "Existe falta grave nos últimos 12 meses em 09/10/2025"
# a coluna Falta segue a emissão do RSPE (05/10/2026: falta de 09/10/2025 ainda nos 12 meses); a nota usa a mesma referência e
# diz quando a janela venceu
n6 = rv._com_nota("Vencido", nota, None, HOJE, ger=date(2026, 10, 5))
ok("fora dos 12 meses" not in n6 and "venceu em 09/10/2026" in n6, "6: nota incoerente com a coluna Falta: %s" % n6)
ok("fora dos 12 meses" in rv._com_nota("Vencido", nota, None, HOJE, ger=date(2026, 10, 15)), "6: nota sem o 'fora dos 12 meses'")

# ---- 7: concordância da execução suspensa ----
r = reg([crime()], [], [], status_execucao="SUSPENSO OU SOBRESTADO", regime_atual="", termino_previsao_seeu="", pena_cumprida="0a0m0d")
d7 = " ".join(i["detalhe"] for i in itens(r, "pena-interrompida-seeu"))
ok("suspenso ou sobrestado" not in d7, "7: concordância: %s" % d7[:200])

# ---- 8: "faltavam" pelos eventos também ao lado da falta grave (o número da âncora mistura bases) ----
m8 = rd._mot_eventos("faltavam 263 dias para 1/3 em 25/12/2007; também falta grave nos 12 meses anteriores: FUGA", "faltavam 3a0m19d para 1/3 em 25/12/2007")
ok(m8.index("contagem pelos eventos") < m8.index("também falta grave"), "8: fonte do 'faltavam' depois da falta grave: %s" % m8)

# ---- 9: indulto concedido sem baixa no cálculo - a aba Indulto diz que pode ter sido só da multa ----
cs9 = [crime(indulto_duvida={"data": "16/04/2024", "decreto": "11.302", "multa": True}), crime(processo_criminal=P2)]
r = {"indulto_2022": "não atinge: pena dos crimes impeditivos não cumprida até 25/12/2022 (art. 11, p. ú.)", "indulto_2022_detalhe": "x"}
rs.aplicar_decisoes_decretos(r, [inc("INDULTO", "Decreto 11.302/2022", "16/04/2024", "16/04/2024", processos=P1)], cs9)
ok("só da multa" in r["indulto_2022"] and "só da multa" in r["indulto_2022_detalhe"], "9: aba sem o aviso do indulto só da multa: %s" % r)
ok("a decisão prevalece" in r["indulto_2022_detalhe"], "9: 'não atinge' ao lado de 'concedido' sem explicação: %s" % r["indulto_2022_detalhe"][:200])
ok(rv.curto_indulto(r["indulto_2022"]).startswith("Concedido · 16/04/2024 · sem baixa"), "9: coluna: %s" % rv.curto_indulto(r["indulto_2022"]))

# ---- 10: reincidência com base na ficha (pena de outro processo extinta) também na prescrição: prazo com +1/3 ----
c10 = crime(data_infracao="01/07/2024", data_sentenca="06/04/2025", transito_mp="22/04/2025", transito_processo="28/07/2025",
            pena_imposta="1 ano(s), 0 mês(es) e 0 dia(s)", reincidente_comum="S", fracao_progressao="20% - Art.112, II, da LEP")
c10b = crime(processo_criminal=P2, data_infracao="09/09/2025", data_sentenca="01/06/2026", transito_mp="10/07/2026",
             transito_processo="13/08/2026", reincidente_comum="S", fracao_progressao="20% - Art.112, II, da LEP")
base10 = reg([c10, c10b], [], [ev(PR, "PRISÃO EM FLAGRANTE", "09/09/2025")], pena_total="3a0m0d", pena_cumprida="1a1m0d")
r10 = dict(copy.deepcopy(base10), _extincoes_ficha=[{"processo": "0002516-90.2008.8.12.0005", "data": "19/07/2024", "texto": "PENA EXTINTA",
                                                      "cumprimento_desde": "10/11/2020"}])
A10 = rp.analisar(r10, HOJE)
lin = A10.get("linhas") or A10.get("presc_linhas") or []
l10 = [L for L in lin if L.get("proc_crim") == P1]
ok(l10 and l10[0].get("reinc") and not l10[0].get("reinc_sem_base"), "10: prescrição sem a reincidência da ficha: %s" % [(L.get("reinc"), L.get("reinc_sem_base")) for L in l10])

# ---- 12a: forma favorável pela conta direta (pena do bloco x fração em meses, menos a detração) ----
blocos = [[Fraction(2, 5), rs.pena_para_dias("15a2m20d"), rs.pena_para_dias("5a4m24d"), 626, [5, 4, 24], [15, 2, 20]]]
t12 = ra._texto_blocos(blocos)
# (7.14.6) conta em anos, meses e dias, como o SEEU: 6a1m2d − 626 dias (1a8m21d) = 4a4m11d
ok("pena × fração − detração): 4 anos, 4 meses e 11 dias" in t12, "12a: forma favorável: %s" % t12[-300:])

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for f in falhas:
        print(" -", f)
    sys.exit(1)
print("teste_conf4_demais: ok")
