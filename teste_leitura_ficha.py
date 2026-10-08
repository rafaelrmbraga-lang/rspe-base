"""Teste de regressão da leitura da ficha do SIAPEN e dos relatórios (conferência da base 08.10): datas dd.mm.aaaa, situação do
PADIC, julgamento registrado como lançamento próprio, números de atestado (milhar, "50 DIAS"), chave da baixa de alertas
e arredondamento dos dias a remir. Rodar: python teste_leitura_ficha.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_scraper as rs
import rspe_ficha as rf
import rspe_remicao as rrm
import rspe_view as rv
import rspe_relatorio as rrel

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


# datas: SEEU (dd/mm/aaaa) e ficha (dd.mm.aaaa); separadores misturados não valem
ok(rs.to_date("26.02.2025") == date(2025, 2, 26), "data com ponto")
ok(rs.to_date("1/2/2024") == date(2024, 2, 1), "data com barra")
ok(rs.to_date("26.02/2025") is None, "separadores misturados")

# atestados: milhar com ponto e "TEMPO DE REMIÇÃO: 50 DIAS"
ats = rrm.atestados([
    {"data": "03.12.2014", "texto": "FOI EMITIDO PELO IPCG, O ´ATESTADO DE TRABALHO´ Nº 649/2015/ST/IPCG/AGEPEN/MS, COM 1.359 DIAS TRABALHADOS E 453 DIAS REMIDOS."},
    {"data": "23.10.2023", "texto": "EMITIDO ATP Nº 255/2023 - PRENDEDORES DE ROUPAS - DATA INICIAL: 02.05.23 à 29.07.23; TEMPO DE TRABALHO: 150 DIAS; TEMPO DE REMIÇÃO: 50 DIAS REMIDOS."}])
por_num = {a["numero"]: a for a in ats}
ok(por_num.get("649/2015", {}).get("trab") == 1359, "milhar nos dias trabalhados")
ok(por_num.get("255/2023", {}).get("rem") == 50.0, "ATP com 50 dias remidos")
ok(rrm._num("140,33") == 140.33 and rrm._num("1.359") == 1359.0 and rrm._num("4.33") == 4.33, "números da ficha")

# faltas: registro com "RESPONDE PROCESSO - PADIC" já é PADIC instaurado; resultado antigo não é falta nova
f = {"eventos": [
    {"data": "26.02.2025", "texto": "CONSELHO DISCIPLINAR: REGISTRO DE FALTA DISCIPLINAR COM FULCRO NO ART. 60 DA LEI Nº 7.210, POR TER INFRINGINDO EM TESE O ART 50, INCISO VI DA LEP.. RESPONDE PROCESSO - PADIC/PDIB."},
    {"data": "11.04.2013", "texto": "REGISTRO DE FALTA DISCIPLINAR: FALTA GRAVE, ART. 50, INCISO VII DA LEP."},
    {"data": "11.09.2013", "texto": "Tomou ciencia do Padic n. 31/606.780/2013, Falta Grave, foi sancionado a 22 dias de isolamento e teve sua conduta carceraria rebaixada para Má por 12 meses a contar da data de 11/04/2013."},
    {"data": "07.10.2015", "texto": "Nesta data após ter cumprido a CD em falta grave retorna ao comportamento BOM."},
    {"data": "14.07.2025", "texto": "CONSELHO DISCIPLINAR: REGISTRO DE FALTA DISCIPLINAR COM FULCRO NO ART. 60 DA LEI Nº 7.210 DE 11 DE JULHO DE 1984 (LEI DE EXECUÇÃO PENAL), POR TER INFRINGINDO EM TESE O ART 79, INCISOS I, III, XV E XVI; 102, INCISO XXII, E 103, INCISO III E XXXVII DO RIBUP E ARTIGOS 39, INCISOS I E VI E 50, INCISO VI E VII, DA LEP.. RESPONDE PROCESSO - PADIC/PDIB."}]}
try:
    rf.atualizar(f)
except Exception:
    pass
fal = sorted(f.get("faltas") or [], key=lambda x: rs.to_date(x["data_fato"].replace(".", "/")))
ok(len(fal) == 3, "faltas: %d (esperado 3: a de 2013, já julgada, e as duas de 2025)" % len(fal))
if len(fal) == 3:
    ok(fal[2]["data_fato"] == "14.07.2025" and fal[2]["grave"], "falta que cita o art. 50 da LEP depois de artigos do RIBUP é grave")
    ok(fal[0]["data_fato"] == "11.04.2013" and fal[0]["situacao"] == "homologada/punida", "julgamento casado com a falta de 2013")
    ok(fal[1]["situacao"] == "PADIC instaurado", "registro com PADIC é PADIC instaurado")

# baixa: dois pontos do confronto RSPE x ficha não podem ter a mesma chave
a = {"tipo": "rspe-x-ficha", "ref": "", "titulo": "Fuga/evasão em 29/06/2026 registrada na ficha e ausente no RSPE"}
b = {"tipo": "rspe-x-ficha", "ref": "", "titulo": "Processos na ficha que o RSPE não lista: 5"}
ok(rv.chave_item(a) != rv.chave_item(b), "chaves distintas para pontos distintos")
ok(rv.chave_item(b) == rv.chave_item(dict(b, titulo="Processos na ficha que o RSPE não lista: 6")), "chave estável quando a contagem muda")
antiga = {"t:" + __import__("hashlib").sha1(b"rspe-x-ficha|").hexdigest()[:12]: {"titulo": a["titulo"], "obs": "x", "data": ""}}
ok(rv.baixa_de(a, antiga)[0] is not None and rv.baixa_de(b, antiga)[0] is None, "baixa antiga vale só para o alerta baixado")

# arredondamento: a coluna fecha com o total arredondado
v = [2282.21, 34.0, 16.0, 24.0, 66.0, 0.99, 0.5, 0.5]
ok(sum(rrel._arred_coluna(v)) == round(sum(v)), "coluna arredondada fecha")
ok(rrel._dias(9165.99) == "9.166", "arredonda, não trunca")

if falhas:
    print("FALHOU (leitura da ficha):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: leitura da ficha (datas, PADIC, atestados), chave de baixa e arredondamento")
