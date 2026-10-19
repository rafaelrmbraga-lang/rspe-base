"""Remição pela leitura x atestado (19/10/2026): uma decisão pode apreciar vários relatórios de leitura de uma vez (12 dias = relatórios
de 1 e 2 obras) - não sobra "leitura peticionada sem remição"; a remição múltipla de 4 só conta como leitura até as obras registradas
na ficha, e a que sobra, posterior a um atestado sem remição, deixa o "não lançado" a conferir (amarelo, fora do total). Dados
fictícios. Rodar: python teste_remicao_leitura_1910.py"""
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
    linhas, res = rf.quadro_trabalho(r, f, date(2026, 10, 19))
    ok(res.get("leituras_f") == [], "leitura: todos os relatórios casados (12 dias = 1 + 2 obras): %r" % res.get("leituras_f"))
    C = res["conc"]
    t = next(t for t in C["tabela"] if "024" in t["atestado"])
    ok(t["cor"] == "amarelo" and t["rot"] == "Verificar remição" and "8 dias em 07/01/2025" in t["nota"], "atestado a conferir: %r / %r" % (t["rot"], t["nota"]))
    p = next(p_ for p_ in C["pendencias"] if p_["texto"].startswith("Atestado 024"))
    ok(p["status"] == "ORF_POST" and p["cor"] == "amarelo", "pendência: %r" % p)
    ok(not res.get("atestados_pendentes") and (res.get("pendentes") or 0) == 0, "fora do total: %r" % res.get("pendentes"))
    R = C["resumo"]["texto"]
    ok("possui 32 dias remidos" in R and "fazendo jus a 29 dias" in R and "insuficientes: faltam cerca de 13 dias" in R, "resumo simples: %s" % R)
    al = " ".join(a["texto"] for a in C["alertas"])
    ok("além das obras de leitura registradas na ficha (4 obras)" in al, "alerta das remições além das obras: %s" % al)
except Exception as e:
    import traceback
    traceback.print_exc()
    falhas.append("exceção: %r" % e)
print("\n".join(falhas) if falhas else "ok: remição pela leitura somada e atestado com remição sem origem posterior (19/10/2026)")
sys.exit(1 if falhas else 0)
