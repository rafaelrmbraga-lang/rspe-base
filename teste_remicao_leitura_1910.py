"""Remição pela leitura x atestado (19/10/2026; modelo da 7.14): o programa não decide qual remição é da leitura e qual é do atestado -
compara os totais (leitura 4 dias por obra, 1 obra por mês quando a ficha só traz os meses; atestado com os dias dele) com o
concedido no RSPE e aponta a diferença para conferir nos autos, sem valor a requerer. (Até a 7.13: casamento leitura x remição e
"faltam ≈ 13" do atestado, pela conciliação, que saiu.) Dados fictícios. Rodar: python teste_remicao_leitura_1910.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


E = lambda d, t: {"data": d, "texto": t}
AUTOS = "0000002-22.2023.8.12.0001"
f = {"data_impressao": "06.10.2026", "conduta": "BOA", "eventos": [
    E("14.08.2023", "INICIOU SUAS ATIVIDADES LABORAIS NO SETOR DE LIMPEZA, CONFORME DETERMINAÇÃO DO SETOR DE TRABALHO."),
    E("22.12.2023", "AFASTADO DO TRABALHO A PEDIDO."),
    E("25.03.2024", "EMITIDO ATESTADO DE TRABALHO Nº 024/2024/ST, COM 86 DIAS TRABALHADOS E 29 DIAS REMIDOS, NO PERIODO DE 14/08/2023 A 22/12/2023."),
], "leituras": [
    {"data": "14.08.2023", "meses": ["06/2023"], "obras": 1, "texto": "REALIZOU PROJETO REMIÇÃO PELA LEITURA; REFERENTE AO MES DE JUNHO DE 2023", "oficio": "1/23"},
    {"data": "25.10.2023", "meses": ["08/2023"], "obras": 1, "texto": "REALIZOU PROJETO REMIÇÃO PELA LEITURA; REFERENTE AO MES DE AGOSTO DE 2023", "oficio": "2/23"},
    {"data": "15.05.2024", "meses": ["03/2024", "04/2024"], "obras": 0, "texto": "REALIZOU PROJETO REMIÇÃO PELA LEITURA: referente aos meses: março e abril", "oficio": ""},
]}
rem = lambda d, n: {"tipo": "REMIÇÃO", "complemento": "%d dias" % n, "data_decisao": d, "data_referencia": d, "situacao": "CONCEDIDO"}
r = {"processo_execucao": AUTOS, "_eventos": [{"data": "01/03/2023", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}],
     "_incidentes": [rem("11/10/2023", 4), rem("18/08/2024", 12), rem("07/01/2025", 8), rem("10/09/2025", 8)], "_crimes": []}
try:
    lei = f["leituras"]
    rf.atualizar(f)
    f["leituras"] = lei
    o = rf.comparativo(r, f, date(2026, 10, 19))
    N = o["fd_novo"]
    ok(N["leitura"] == 16 and N["obras"] == 4 and N["at_desta"] == 29 and N["R"]["concedido"] == 32, "totais: %s %s %s" % (N["leitura"], N["at_desta"], N["R"]))
    ok(N["dif"] == 13 and N["concl"].startswith("Verificar remição: a ficha comprova 45 dias e o RSPE concedeu 32, diferença de 13 dias")
       and "não o quanto requerer" in N["concl"], "conclusão: %s" % N["concl"])
    # o atestado é anterior à última decisão: não é fato vermelho; sem registro de peticionamento, é ponto a conferir
    ok(o["fd_cor"] == "amarelo" and any(p["tipo"] == "sem_pet" and "024/2024" in p["texto"] for p in N["pontos"]) and not N["fatos"],
       "situação: %s %s" % (o["fd_cor"], [p["tipo"] for p in N["pontos"]]))
    ok(not (o.get("fd_fund") or ""), "fundamentação sem fato certo: %s" % (o.get("fd_fund") or "")[:200])
except Exception as e:
    import traceback
    traceback.print_exc()
    falhas.append("exceção: %r" % e)
print("\n".join(falhas) if falhas else "ok: remição pela leitura e atestado comparados pelos totais (7.14)")
sys.exit(1 if falhas else 0)
