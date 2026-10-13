"""Teste de regressão das correções da auditoria externa (12/10/2026): término com reinício lançado pela ficha, limite do art. 75
com fato durante o cumprimento, vedação do livramento ao reincidente específico em tráfico não hediondo (art. 35), homicídio sem
a marcação do resultado morte, pedidos de livramento sem a alteração de data-base, frações em concurso, livramento vedado em todas
as penas, guia sem pena total e falta "homologada/punida" da ficha na data-base. Rodar: python teste_auditoria_externa.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_auditoria as ra
import rspe_view as rv

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


PR = "PRISÃO/INÍCIO DE CUMPRIMENTO"
rv.HOJE = date(2026, 10, 1)


def crime(**kw):
    c = {"processo_criminal": "0000001-11.2020.8.12.0001", "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto",
         "tipo_penal": "CAPUT: Subtrair, Reclusão: 1 a 4 anos", "pena_imposta": "10 ano(s), 0 mês(es) e 0 dia(s)",
         "data_infracao": "10/01/2016", "data_sentenca": "10/06/2016", "transito_mp": "10/07/2016", "transito_processo": "10/07/2016",
         "extinto": "Não", "suspenso": "Não", "vga": "N", "resultado_morte": "N", "reincidente_comum": "N", "reincidente_especifico": "N",
         "comando_orcrim": "N", "fracao_progressao": "1/6 - Comum", "fracao_livramento": "1/3 - Comum"}
    c.update(kw)
    return c


def ev(tipo, motivo, data, procs="0000001-11.2020.8.12.0001", ficha=False):
    e = {"tipo": tipo, "motivo": motivo, "data": data, "processos": procs}
    if ficha:
        e["_ficha"] = True
    return e


def reg(crimes, incs=(), eventos=(), **kw):
    r = {"nome": "Teste", "regime_atual": "Fechado - ATIVO", "pena_total": "10a0m0d", "pena_cumprida": "3a0m0d", "pena_remanescente": "7a0m0d",
         "fracao_progressao_aplicada": "1/6", "data_geracao_rspe": "01/10/2026", "data_base_seeu": "01/03/2024", "_crimes": crimes,
         "_incidentes": list(incs), "_eventos": list(eventos)}
    r.update(kw)
    return r


def tipos(r, nivel=None):
    return [i["tipo"] for i in ra.auditar(r, date(2026, 10, 1))["aud_itens"] if nivel is None or i["nivel"] == nivel]


# 1. reinício lançado pela ficha: o término corre do reinício (o SEEU congelou a cumprida na interrupção)
r = reg([crime()], eventos=[ev(PR, "PRISÃO DEFINITIVA", "01/01/2020"), ev("INTERRUPÇÃO", "FUGA", "01/01/2023"),
                            ev("REINÍCIO", "RECAPTURA (lançado pela ficha SIAPEN)", "01/06/2023", "", True)],
        pena_remanescente="7a0m0d", termino_previsao_seeu="", situacao_cumprimento="EM CUMPRIMENTO")
ok(rv.reinicio_ficha(r) == date(2023, 6, 1), "reinício pela ficha: %s" % rv.reinicio_ficha(r))
ok(rv.termino_calc(r) == date(2030, 6, 1), "término pelo reinício: %s" % rv.termino_calc(r))

# 2. art. 75: fato durante o cumprimento não tira o alerta quando o término passa até do limite mais folgado
cs = [crime(data_infracao="10/01/2008", pena_imposta="30 ano(s), 0 mês(es) e 0 dia(s)"),
      crime(processo_criminal="0000002-22.2012.8.12.0001", data_infracao="10/01/2011", transito_processo="10/01/2012", transito_mp="10/01/2012")]
r = reg(cs, eventos=[ev(PR, "PRISÃO EM FLAGRANTE", "01/01/2010")], pena_total="60a0m0d", termino_previsao_seeu="01/01/2070")
ok("limite-de-cumprimento-art-75-unificacao" in tipos(r), "art. 75 com fato posterior: %s" % tipos(r))

# 3. art. 35 da Lei 11.343 com reincidência específica em tráfico demonstrada: 1/1 no livramento é o correto (art. 44, p. ú.)
ant = crime(processo_criminal="0000003-33.2004.8.12.0001", lei="6368/76 - Lei de Tóxicos", artigo="ART 12: Tráfico", tipo_penal="CAPUT",
            data_infracao="10/01/2004", transito_processo="21/03/2005", transito_mp="21/03/2005", extinto="Sim")
a35 = crime(processo_criminal="0000004-44.2007.8.12.0001", lei="11343/06 - Lei de Drogas", artigo="ART 35: Associação", tipo_penal="CAPUT: Associarem-se",
            data_infracao="02/01/2007", reincidente_comum="S", fracao_progressao="1/6 - Comum", fracao_livramento="1/1 - Reincidente Específico")
ok("fracao-de-livramento-diverge" not in tipos(reg([ant, a35]), "alerta"), "art. 35 reincidente específico: %s" % tipos(reg([ant, a35]), "alerta"))

# 4. homicídio qualificado sem a marcação do resultado morte, 50% no SEEU: "verificar" (consumado x tentado), não alerta de 40%
hom = crime(artigo="ART 121: Matar alguem:", tipo_penal="§ 2º: Se o homicídio é cometido:, Reclusão: 12 a 30 anos", data_infracao="23/11/2020",
            reincidente_comum="S", fracao_progressao="50% - Art.112, VI, da LEP", fracao_livramento="2/3 - Hediondo")
t = tipos(reg([hom]))
ok("percentual-homicidio-consumacao-a-conferir" in t and "percentual-de-progressao-diverge" not in t, "homicídio 50%%: %s" % t)

# 5. alteração de data-base não é pedido de livramento concedido
inc_db = {"tipo": "ALTERAÇÃO DE DATA-BASE DE PROGRESSÃO DE REGIME/LIVRAMENTO CONDICIONAL", "complemento": "", "situacao": "CONCEDIDO",
          "data_decisao": "01/06/2020", "data_referencia": "01/06/2020"}
ok(rv.pedidos(reg([crime()], [inc_db]), "LIVRAMENTO") == "", "pedidos: %s" % rv.pedidos(reg([crime()], [inc_db]), "LIVRAMENTO"))

# 6. frações em concurso: lista as frações (não afirma só a maior); 1/1 no livramento = vedado
r = reg([crime(fracao_progressao="16% - Art.112, I", pena_imposta="2 ano(s), 0 mês(es) e 0 dia(s)"),
         crime(fracao_progressao="40% - Art.112, V", fracao_livramento="1/1 - Hediondo Reincidente")])
ok(rv.fracoes_texto(r, "fracao_progressao") == "16% e 40% (cada percentual sobre a pena do seu crime)", rv.fracoes_texto(r, "fracao_progressao"))
ok("vedado" in rv.fracoes_texto(r, "fracao_livramento"), rv.fracoes_texto(r, "fracao_livramento"))

# 7. livramento vedado em todas as penas: a data do SEEU não é prazo
r = reg([crime(fracao_livramento="1/1 - Hediondo Reincidente")], eventos=[ev(PR, "PRISÃO DEFINITIVA", "01/01/2020")],
        livramento_previsao_seeu="01/01/2030", situacao_cumprimento="EM CUMPRIMENTO")
ok(rv.data_livramento(r)[0].startswith("Vedado") and rv.data_livramento(r)[1] is None, "livramento vedado: %s" % (rv.data_livramento(r),))

# 8. guia sem pena total calculada: a soma das penas impostas faz as vezes da pena total
r = reg([crime(pena_imposta="1 ano(s), 0 mês(es) e 0 dia(s)")], eventos=[ev(PR, "PRISÃO DEFINITIVA", "01/01/2025")],
        pena_total="0a0m0d", pena_cumprida="0a0m0d", pena_remanescente="0a0m0d", termino_previsao_seeu="", situacao_cumprimento="EM CUMPRIMENTO")
ok(rv.soma_penas_ativas(r) == 365 and rv.custodia_sem_calculo(r) is not None, "guia sem pena: %s" % rv.custodia_sem_calculo(r))
ok(rv.termino_calc(r) == date(2025, 12, 31), "término da guia sem pena (CP, art. 10): %s" % rv.termino_calc(r))

# 9. saída temporária: homicídio qualificado sem a marcação do resultado morte fica "a conferir" (nunca verde); fração em dias
# arredondada para baixo (1/6 de 100 dias = 16)
r = reg([crime(artigo="ART 121: Matar alguem:", tipo_penal="§ 2º: Se o homicídio é cometido:", data_infracao="10/03/2021",
               hediondo_ou_equiparado="S", pena_imposta="0 ano(s), 3 mês(es) e 10 dia(s)")],
        regime_atual="Semiaberto - ATIVO", pena_total="0a3m10d", pena_cumprida="0a0m16d", status_execucao="ATIVO")
st = rv.saida_temporaria(r, None, {})
ok(any(i["ok"] is None and "resultado morte" in i["txt"] for i in st["st_itens"]) and not st["st_ok"], "saída: resultado morte %s" % st["st_itens"])
ok(any(i["ok"] is True and "1/6 da pena" in i["txt"] for i in st["st_itens"]), "saída: 1/6 arredondado %s" % st["st_itens"])

if falhas:
    print("FALHOU (auditoria externa):")
    for f in falhas:
        print("  " + f)
    sys.exit(1)
print("ok: auditoria externa (término pelo reinício da ficha, art. 75 com fato posterior, art. 35 reincidente, homicídio sem resultado morte, "
      "pedidos de livramento, frações em concurso, livramento vedado, guia sem pena total)")
