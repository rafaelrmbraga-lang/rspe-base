"""Fundamentação da remição (aba Ficha, "Copiar fundamentação"): divergência ficha x RSPE no trabalho e no estudo, com os pedidos
de declaração, de certificação pela unidade e de atualização do cálculo; estudo sozinho (ENCCEJA/ENEM, leitura) também gera texto.
Dados fictícios. Rodar: python teste_fundamentacao_remicao.py"""
import sys
import types
from datetime import date, timedelta

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf

falhas = []
HOJE = date(2026, 10, 8)


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def F(eventos, exames=(), leituras=()):
    return {"data_impressao": "07/10/2026", "eventos": [{"data": d, "texto": t} for d, t in eventos],
            "exames": list(exames), "leituras": list(leituras)}


def R(*incs, prog=None):
    r = {"_eventos": [{"data": "01/01/2024", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}], "_incidentes": list(incs)}
    if prog:
        r["progressao_previsao_seeu"] = prog
    return r


try:
    # atestado emitido e não lançado + ENEM/ENCCEJA + leitura sem remição (o cenário do retorno da equipe, com dados fictícios)
    prog = (date.today() + timedelta(days=400)).strftime("%d/%m/%Y")
    f = F([("24.01.2025", "TRABALHO: Iniciou atividade laboral, no setor de trabalho Oficina Teste, conforme documento CI 1."),
           ("07.07.2026", "FOI EMITIDO ATESTADO DE TRABALHO Nº 185/TESTE, PERÍODO DE 24/01/2025 A 07/07/2026, 453 DIAS TRABALHADOS E 151 DIAS REMIDOS")],
          exames=[{"exame": "ENEM 2024", "data": "11/04/2025", "certificado": True}, {"exame": "ENCCEJA 2024", "data": "01/05/2025", "certificado": True}],
          leituras=[{"data": "17/06/2026", "meses": ["02/2026", "03/2026", "04/2026"]}])
    o = rf.comparativo(R(prog=prog), f, HOJE)
    t = o.get("fd_fund") or ""
    ok(t.startswith("DA REMIÇÃO DE PENA E DA DIVERGÊNCIA ENTRE A FICHA DISCIPLINAR (SIAPEN) E O RSPE"), "título: %s" % t[:90])
    ok("nº 185/TESTE, de 07/07/2026, referente ao período de 24/01/2025 a 07/07/2026" in t and "O RSPE, contudo, não registra remição" in t,
       "fatos do atestado: %s" % t[:400])
    ok("ENEM 2024 (certificado registrado em 11/04/2025)" in t and "Res. CNJ 391/2021, art. 3º, parágrafo único" in t and "1/3" in t,
       "estudo: ENEM/ENCCEJA: %s" % t)
    ok("relatórios de leitura peticionados em 17/06/2026 (3 obras)" in t and "art. 5º, V" in t, "estudo: leitura")
    ok("(LEP, art. 129)" in t and "Portaria AGEPEN 15/2021, art. 11" in t and 'art. 66, III, "c"' in t and "(LEP, art. 128)" in t, "fundamentos")
    ok("a) a declaração da remição de 151 dias, referente ao atestado nº 185/TESTE" in t and "b) a declaração da remição pelo estudo" in t
       and "c) a expedição de ofício à direção da unidade" in t and "d) a certificação, pela Secretaria" in t and "e) após a juntada" in t,
       "pedidos a) a e): %s" % t[t.find("requer-se:"):][:900])
    ok("DO REFLEXO NA PROGRESSÃO DE REGIME" in t and "passará de %s para [data recalculada: por volta de" % prog in t, "reflexo na progressão")
    # só estudo: o texto sai, sem pedido de declaração de atestado e sem reflexo
    o2 = rf.comparativo(R(), F([], exames=[{"exame": "ENCCEJA 2025", "data": "01/05/2026", "certificado": True}]), HOJE)
    t2 = o2.get("fd_fund") or ""
    ok(t2 and "a) a declaração da remição pelo estudo" in t2 and "REFLEXO" not in t2 and "atestado nº" not in t2, "só estudo: %s" % t2[:500])
    # nada pendente: sem texto
    o3 = rf.comparativo(R(), F([]), HOJE)
    ok(not o3.get("fd_fund"), "sem pendência, sem fundamentação: %s" % (o3.get("fd_fund") or "")[:200])
except Exception as e:
    import traceback
    traceback.print_exc()
    falhas.append("erro: %s" % e)

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for x in falhas:
        print(" -", x)
    sys.exit(1)
print("ok: fundamentação da remição (trabalho e estudo, divergência ficha x RSPE, pedidos e reflexo na progressão)")
