"""Precedentes do caderno de teses 2026 aplicados: Tema 1354 (fração por condenação na pena unificada), hediondez do tráfico
privilegiado no Decreto 12.790, data-base movida pelo indulto/comutação e remição pendente que completa o lapso do decreto.
Dados fictícios. Rodar: python teste_precedentes_2026.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_auditoria as ra
import rspe_ficha as rf
import rspe_scraper as rs

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


DB = "ALTERAÇÃO DE DATA-BASE DE PROGRESSÃO DE REGIME/LIVRAMENTO CONDICIONAL"
AR = "FIXAÇÃO/ALTERAÇÃO DE REGIME"


def inc(tipo, compl, dec, ref, sit="CONCEDIDO"):
    return {"tipo": tipo, "motivo": "", "complemento": compl, "data": "", "data_decisao": dec, "data_referencia": ref, "processos": "", "situacao": sit}


crime = {"processo_criminal": "0000001-11.2020.8.12.0001", "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto",
         "tipo_penal": "CAPUT: Subtrair, Reclusão: 1 a 4 anos", "pena_imposta": "10 ano(s), 0 mês(es) e 0 dia(s)",
         "data_infracao": "10/01/2016", "data_sentenca": "10/06/2016", "transito_mp": "10/07/2016", "transito_processo": "10/07/2016",
         "extinto": "Não", "suspenso": "Não", "vga": "N", "resultado_morte": "N", "reincidente_comum": "N", "reincidente_especifico": "N",
         "comando_orcrim": "N", "fracao_progressao": "1/6 - Comum", "fracao_livramento": "1/3 - Comum"}

try:
    # (5) data-base alterada na mesma data da comutação concedida, sem falta, regressão ou prisão: alerta próprio
    r = {"nome": "Teste", "regime_atual": "Fechado - ATIVO", "pena_total": "10a0m0d", "pena_cumprida": "3a0m0d", "pena_remanescente": "7a0m0d",
         "fracao_progressao_aplicada": "1/6", "data_geracao_rspe": "01/10/2026", "data_base_seeu": "10/03/2025", "_crimes": [crime],
         "_incidentes": [inc(AR, "Fechado - Regime Inicial", "", "10/07/2016"), inc("COMUTAÇÃO DE PENA", "Decreto 12.338/2024", "10/03/2025", "25/12/2024"),
                         inc(DB, "Progressão de Regime", "10/03/2025", "10/03/2025")], "_eventos": []}
    its = [i for i in ra.auditar(r, date(2026, 10, 1))["aud_itens"] if i["tipo"] == "data-base-movida-pelo-indulto"]
    ok(len(its) == 1, "indulto: alerta da data-base movida não saiu (%d)" % len(its))
    ok(its and "HC 1.076.656" in its[0]["fundamento"] and "Tema 1006" in its[0]["fundamento"], "indulto: fundamento sem os precedentes")

    # (1) e (9) citações nos textos
    src_a = open("rspe_auditoria.py", encoding="utf-8").read()
    src_s = open("rspe_scraper.py", encoding="utf-8").read()
    ok("REsp 2.037.377/SC" in src_a, "Tema 1354: REsp 2.037.377/SC não citado")
    ok("1602182-72.2026" in src_a and "1602182-72.2026" in src_s, "hediondez: TJMS 1602182-72.2026 não citado")
    ok("1.087.914/SP" in src_s, "hediondez: AgRg no HC 1.087.914/SP não citado")

    # (3) comutação 2025 que não atinge por 20 dias, com 30 dias de remição pendente (atestado emitido) até 25/12/2025: a verificar
    comp = {"fd_rem_det": {"emitido": {"itens": [{"setor": "Oficina Teste", "per": "01/01/2025 a 31/03/2025", "dias": 30}]},
                           "nao_lancado": {"itens": [{"setor": "Horta", "per": "01/01/2026 a 31/03/2026", "dias": 40}]},
                           "sem_atestado": {"itens": [{"setor": "Cozinha", "per": "01/04/2025 a hoje", "dias": 90, "estimado": True}]}}}
    r = {"comutacao_2025": "não atinge (1/5 até 25/12/2025)",
         "comutacao_2025_detalhe": "✘ Requisito: 1/5 da pena cumprida até 25/12/2025 = 1a0m24d; cumprido 1a0m4d.",
         "indulto_2025": "não atinge (1/3 até 25/12/2025)", "indulto_2025_status": "nao",
         "indulto_2025_detalhe": "✘ II: pena ≤ 12 anos sem VGA, exige 1/3 (cumprido 1a0m0d de 6a0m0d)"}
    rf.remicao_pendente_decretos(r, comp)
    ok(r["comutacao_2025"].startswith("A VERIFICAR (remição pendente)"), "remição: comutação não virou a verificar: %s" % r["comutacao_2025"])
    ok("HC 1.089.923" in r["comutacao_2025"] and "art. 128" in r["comutacao_2025"], "remição: fundamento ausente")
    ok("Horta" not in r["comutacao_2025"] and "Cozinha" not in r["comutacao_2025"], "remição: contou período posterior ou estimado")
    ok(r["indulto_2025"].startswith("não atinge") and r["indulto_2025_status"] == "nao", "remição: indulto com déficit de 1 ano mudou")
    ok(rs.status_texto_decreto(r["comutacao_2025"]) == "verificar", "remição: status do texto")

    # indulto com déficit coberto
    r = {"indulto_2024": "não atinge (1/3 até 25/12/2024)", "indulto_2024_status": "nao",
         "indulto_2024_detalhe": "✘ II: pena ≤ 12 anos sem VGA, exige 1/3 (cumprido 1a11m10d de 6a0m0d)"}
    rf.remicao_pendente_decretos(r, {"fd_rem_det": {"emitido": {"itens": [{"setor": "Oficina", "per": "01/01/2024 a 30/06/2024", "dias": 30}]}}})
    ok(r["indulto_2024_status"] == "verificar" and "? Remição pendente" in r["indulto_2024_detalhe"], "remição: indulto 2024 não virou a verificar")

    # sem remição pendente nada muda; crimes impeditivos também não
    r = {"indulto_2024": "não atinge: pena dos crimes impeditivos", "indulto_2024_detalhe": "✘ II: exige 1/3 (cumprido 1a0m0d de 6a0m0d)"}
    rf.remicao_pendente_decretos(r, {"fd_rem_det": {"emitido": {"itens": [{"setor": "O", "per": "01/01/2024 a 30/06/2024", "dias": 900}]}}})
    ok(r["indulto_2024"] == "não atinge: pena dos crimes impeditivos", "remição: mexeu no impeditivo")
except Exception as e:
    import traceback
    traceback.print_exc()
    falhas.append("exceção: %r" % e)

if falhas:
    print("FALHAS:")
    for f_ in falhas:
        print(" -", f_)
    sys.exit(1)
print("ok - precedentes 2026")
