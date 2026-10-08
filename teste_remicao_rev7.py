"""Teste de regressão da conferência da remição (rev7, 08.10): remição decidida antes da data registrada na ficha, com
referência no fim do período; atestado lançado em duas linhas; soma de atestados com 1 dia de arredondamento; teste de
capacidade da remição sem atestado; referência no fim do atestado com dias diferentes; leitura da 2ª função sem parêntese e do
atestado de estudo na mesma linha; atestado que repete período já remido; atestado acima do possível; livramento travado pela
falta grave nos últimos 12 meses. Rodar: python teste_remicao_rev7.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf
import rspe_remicao as rrm
import rspe_relatorio as rrel

falhas = []
HOJE = date(2026, 10, 8)


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def F(eventos, impressao="06/10/2026"):
    return {"data_impressao": impressao, "eventos": [{"data": d, "texto": t} for d, t in eventos]}


def rem(dias, dec, ref=None):
    return {"tipo": "REMIÇÃO", "complemento": "%s Dia(s) Remido(s)" % dias, "data_decisao": dec, "data_referencia": ref or dec, "situacao": "CONCEDIDO"}


def st(C):
    return {a["numero"]: (a["status"], a["remicao"]["dias"] if a.get("remicao") else None) for a in C["atestados"] if a["numero"]}


def R(*incs):
    return {"_eventos": [{"data": "01/01/2015", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}], "_incidentes": list(incs)}


# ---- 1: remição decidida antes da data em que a ficha registra o atestado, com referência no fim do período (Geraldo) ----
f = F([("15.03.2026", "Peticionado o Atestado de Trabalho n 022/2026, no Sistema SEEU, função Poligonal (14/05/2025 a 23/02/2026) totalizando "
                      "630 dias trabalhados e 210 remidos.")])
ok(st(rrm.conciliar(R(rem(210, "09/03/2026", "23/02/2026")), f, HOJE)).get("022/2026") == ("CONCILIADO", 210.0), "1: decisão antes da emissão (ref = fim)")
# atestado sem período (em lote): a referência fica entre o atestado anterior e a emissão (Wanderley, 218/2026)
f = F([("19.03.2026", "Peticionado o Atestado de Trabalho n 050/2026, no Sistema SEEU, função Padaria (23/05/2025 a 02/03/2026) totalizando 243 dias "
                      "trabalhados e 81 remidos."),
       ("10.07.2026", "Emitido atestado de trabalho nº 218/2026 setor de PADARIA com 64 dias trabalhados e 21 dias remidos.")])
s1 = st(rrm.conciliar(R(rem(81, "25/03/2026", "02/03/2026"), rem(21, "16/06/2026", "15/05/2026")), f, HOJE))
ok(s1.get("218/2026") == ("CONCILIADO", 21.0), "1: atestado em lote com decisão 24 dias antes: %s" % s1)
# remição de mesmos dias, mas decidida muito antes e com referência fora do período, continua sem par
f = F([("15.03.2026", "Peticionado o Atestado de Trabalho n 023/2026, no Sistema SEEU, função Poligonal (14/05/2025 a 23/02/2026) totalizando "
                      "630 dias trabalhados e 210 remidos.")])
ok(st(rrm.conciliar(R(rem(210, "09/03/2024", "23/02/2024")), f, HOJE)).get("023/2026", ("",))[0] == "NAO_LANCADO", "1: remição antiga casada")

# ---- 2: atestado lançado em duas linhas da mesma decisão (164 = 52 + 112) ----
f = F([("27.06.2024", "Peticionado o Atestado de Trabalho n 347/2024, no Sistema SEEU, função Artesanato (01/12/2022 a 28/03/2023) totalizando 101 dias "
                      "trabalhados e 33,66 remidos; função Padaria (01/06/2023 a 27/06/2024) totalizando 392 dias trabalhados e 130,66 remidos.")])
C = rrm.conciliar(R(rem(52, "05/08/2024", "28/03/2023"), rem(112, "05/08/2024", "27/06/2024")), f, HOJE)
ok(st(C).get("347/2024") == ("CONCILIADO", 164.0) and len(C["atestados"]) == 1, "2: linhas 52 + 112: %s" % st(C))

# ---- 3: uma remição para três atestados, com 1 dia de diferença no arredondamento (113 + 16 + 12 = 141 x 140) ----
f = F([("10.02.2020", "Emitido Atestado de Trabalho nº 0111/2020, período de 29/08/2016 a 07/10/2016, 35 dias trabalhados e 12 dias remidos."),
       ("21.07.2022", "Emitido Atestado de Trabalho nº 272/2022, período de 20/01/2021 a 21/07/2022, 341 dias trabalhados e 113 dias remidos."),
       ("23.07.2022", "Emitido Atestado de Trabalho nº 1234/2022, período de 08/02/2020 a 15/04/2020, 48 dias trabalhados e 16 dias remidos.")])
s3 = st(rrm.conciliar(R(rem(140, "28/07/2022")), f, HOJE))
ok(all(s3.get(n) == ("CONCILIADO", 140.0) for n in ("0111/2020", "272/2022", "1234/2022")), "3: soma com 1 dia de diferença: %s" % s3)

# ---- 4: remição grande não cabe no período curto sem atestado: abrange o atestado ainda sem par (Mauri: 153 x 92,66) ----
f = F([("08.07.2022", "TRABALHO: Iniciou atividade laboral, no setor de trabalho FAXINA, conforme documento 1."),
       ("28.05.2023", "Peticionado o Atestado de Trabalho n 087/2023, no Sistema SEEU, função Faxina (08/07/2022 a 28/05/2023) totalizando "
                      "278 dias trabalhados e 92,66 remidos."),
       ("15.06.2023", "TRABALHO: Deixa de trabalhar, no setor de trabalho FAXINA, conforme documento 1, motivo: N/C.")])
C = rrm.conciliar(R(rem(153, "25/07/2023")), f, HOJE)
ok(st(C).get("087/2023") == ("CONCILIADO", 153.0), "4: atestado não absorvido pela remição maior que o período: %s" % st(C))
ok(any(al["tipo"] == "capacidade" for al in C["alertas"]), "4: sem alerta de capacidade")
# remição pequena que cabe no período: continua como atestado não registrado, e o atestado segue sem par
C = rrm.conciliar(R(rem(5, "25/07/2023")), f, HOJE)
ok(st(C).get("087/2023", ("",))[0] == "NAO_LANCADO", "4: remição que cabe no período absorveu o atestado: %s" % st(C))

# ---- 5: referência no fim do atestado com dias diferentes (Moisés: 102 com referência em 08/08/2023, atestado de 69) ----
f = F([("20.09.2023", "Peticionado o Atestado de Trabalho n 112/2023, no Sistema SEEU, função Cela Livre (18/01/2023 a 08/08/2023) totalizando "
                      "207 dias trabalhados e 69 remidos.")])
C = rrm.conciliar(R(rem(102, "29/01/2024", "08/08/2023")), f, HOJE)
ok(st(C).get("112/2023") == ("DIVERGENCIA", 102.0), "5: referência no fim do atestado: %s" % st(C))
_L, res = rf.quadro_trabalho(R(rem(102, "29/01/2024", "08/08/2023")), f, HOJE)
ok(res["rem_det"]["nao_lancado"]["dias"] == 0 and res["rem_det"]["divergencia"]["dias"] == 0, "5: remição maior que o atestado ainda pendente")

# ---- 6: leitura - 2ª função sem o parêntese de abertura (Luziano) e atestado de estudo na mesma linha (Rito) ----
a = rrm.atestados(F([("14.08.2024", "Peticionado o Atestado de Trabalho n 128/2024, no Sistema SEEU, Autos 0049107-59.2007.8.12.0001, função Prendedores "
                                    "Prendebem 19/06/2023 a 22/10/2023) totalizando 90 trabalhados e 30 remidos; função Artesanato (23/10/2023 a 07/06/2024) "
                                    "totalizando 164 dias trabalhados e 54,66 remidos.")])["eventos"])
ok(len(a) == 1 and a[0]["rem"] == 84.66 and len(a[0]["segs"]) == 2, "6: 2ª função sem parêntese: %s" % [(x["rem"], len(x["segs"])) for x in a])
f = F([("15.02.2018", "Nesta data foi emitido Atestado de Trabalho 06/2018, na função de faxineiro, totalizando 627 dias trabalhados e 209 dias remidos. "
                      "E Atestado de Trabalho 07/2018, de estudo, totalizando 80 h/a de estudo e 6 dias remidos. (Enviados para advogada, via email)")])
a = rrm.atestados(f["eventos"])
ok(len(a) == 1 and a[0]["rem"] == 209 and a[0].get("rem_estudo") == 6, "6: atestado de estudo na mesma linha: %s" % [(x["rem"], x.get("rem_estudo")) for x in a])
ok(st(rrm.conciliar(R(rem(215, "22/10/2018", "16/02/2016")), f, HOJE)).get("006/2018") == ("CONCILIADO", 215.0), "6: 215 = 209 + 6 não conciliado")

# ---- 7: atestado novo que repete período já remido (José Almeida: Faxina de 2018-2019 já remida com 87 dias) ----
f = F([("16.08.2018", "Nesta data foi peticionado o Atestado de Trabalho n 110/2018, na função Faxina (10/07/2017 a 16/08/2018), sendo 346 dias trabalhados e 115 remidos."),
       ("17.01.2026", "Peticionado o Atestado de Trabalho n 005/2026, no Sistema SEEU, função Faxina (17/08/2018 a 29/07/2019) 297 dias trabalhados e 99 remidos; "
                      "função Piva Lingerie (21/05/2023 a 18/01/2025) totalizando 435 dias trabalhados e 145 remidos.")])
C = rrm.conciliar(R(rem(115, "16/08/2018"), rem(87, "19/07/2019")), f, HOJE)
a = next(a for a in C["atestados"] if a["numero"] == "005/2026")
ok(a["status"] == "NAO_LANCADO" and a.get("rem_pend") == 157, "7: período já remido contado de novo: %s %s" % (a["status"], a.get("rem_pend")))
# remição que cabe no trabalho sem atestado logo antes do período não é parcial (Venâncio, 51 dias)
f = F([("25.09.2022", "TRABALHO: Iniciou atividade laboral, no setor de trabalho PRENDEBEM, conforme documento 1."),
       ("26.09.2022", "Peticionado o Atestado de Trabalho n 301/2022, no Sistema SEEU, função Prendebem (17/11/2021 a 24/09/2022) totalizando 267 dias trabalhados e 89 remidos."),
       ("06.08.2023", "Peticionado o Atestado de Trabalho n 183/2023, no Sistema SEEU, função Prendebem (24/03/2023 a 06/08/2023) totalizando 116 dias trabalhados e 38 remidos.")])
C = rrm.conciliar(R(rem(89, "16/02/2023"), rem(51, "17/05/2023")), f, HOJE)
a = next(a for a in C["atestados"] if a["numero"] == "183/2023")
ok(a["status"] == "NAO_LANCADO" and "rem_pend" not in a, "7: remição do trabalho anterior tratada como parcial: %s" % a.get("rem_pend"))

# ---- 8: atestado acima do possível (Clemilson: 448 remidos de 22/04/2023 a 24/06/2026, máximo ≈ 321) ----
f = F([("22.04.2023", "Peticionado atestado DE Trabalho n 066/2023, no sistema SEEU, função Prendebem (07/03/2022 a 21/04/2023) totalizando 294 dias trabalhados e 98 remidos."),
       ("22.04.2023", "TRABALHO: Iniciou atividade laboral, no setor de trabalho PRENDE BEM, conforme documento 1."),
       ("24.06.2026", "TRABALHO, nesta data foi emitido atestado de trabalho nº 115 setor de PRENDE BEM com 448 dias de remição.")])
r8 = R(rem(98, "17/05/2023"))
C = rrm.conciliar(r8, f, HOJE)
a = next(a for a in C["atestados"] if a["numero"] == "115")
ok(a["status"] == "NAO_LANCADO" and 300 <= (a.get("teto") or 0) <= 335 and any(al["tipo"] == "plausibilidade" for al in C["alertas"]),
   "8: atestado acima do possível sem teto/alerta: %s" % a.get("teto"))
_L, res = rf.quadro_trabalho(r8, f, HOJE)
it = res["rem_det"]["emitido"]["itens"]
ok(it and it[0]["dias"] == a["teto"] and "acima do máximo" in it[0]["base"], "8: dias exatos sem o teto: %s" % [(i["dias"], i["base"]) for i in it])

# ---- 9: livramento travado pela falta grave nos últimos 12 meses: a remição não o antecipa ----
m = {"nome": "Teste", "liv_dias": 60, "prog_dias": 500, "ext_dias": None, "liv": "28/01/2027",
     "fd_rem_det": {"emitido": {"dias": 100}, "total": 100},
     "_bruto": {"livramento_previsao_seeu": "28/01/2027", "livramento_obs_seeu": "", "data_base_seeu": "28/01/2026",
                "_incidentes": [{"tipo": "HOMOLOGAÇÃO DE FALTA GRAVE", "complemento": "28/01/2026", "data_referencia": "28/01/2026", "situacao": "CONCEDIDO"}]}}
ok(rrel.livramento_travado_por_falta(m), "9: livramento travado não reconhecido")
p = rrel.prioridade_remicao(m)
ok(p[0] == 3 and "travado" in p[1] and "já a alcançam" not in p[1], "9: prioridade com livramento travado: %s" % (p[:2],))
m["_bruto"]["_incidentes"], m["_bruto"]["data_base_seeu"] = [], "10/10/2020"
p = rrel.prioridade_remicao(m)
ok(p[0] == 2 and "livramento" in p[1], "9: sem falta, a remição alcança o livramento: %s" % (p[:2],))

if falhas:
    print("FALHOU (remição rev7):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: remição rev7 (decisão antes da emissão, linhas, soma com arredondamento, capacidade, referência no fim, 2ª função e estudo, "
      "período já remido, teto do atestado, livramento travado pela falta)")
