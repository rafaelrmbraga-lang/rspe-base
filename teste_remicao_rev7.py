"""Teste de regressão da conferência da remição (rev7, 08.10; ajustado ao modelo da 7.14, sem a conciliação atestado x remição): remição decidida antes da data registrada na ficha, com
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

falhas = []
HOJE = date(2026, 10, 8)


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def F(eventos, impressao="06/10/2026"):
    return {"data_impressao": impressao, "eventos": [{"data": d, "texto": t} for d, t in eventos]}


def rem(dias, dec, ref=None):
    return {"tipo": "REMIÇÃO", "complemento": "%s Dia(s) Remido(s)" % dias, "data_decisao": dec, "data_referencia": ref or dec, "situacao": "CONCEDIDO"}


def R(*incs):
    return {"_eventos": [{"data": "01/01/2015", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}], "_incidentes": list(incs)}


# (7.14: a conciliação atestado x remição saiu - itens 1 a 5, 7 e 8 eram regras de casamento (decisão antes da emissão, linhas da mesma
# decisão, soma com arredondamento, capacidade da remição sem atestado, referência no fim, período já remido, teto) e o item 9 era da
# prioridade por dias a requerer; ficam a leitura dos atestados e o que o modelo novo faz com os mesmos dados)
def N_(r, f):
    rf.atualizar(f)
    return rf.comparativo(r, f, HOJE)


# ---- 1: remição decidida antes da data em que a ficha registra o atestado: os totais batem, sem diferença nem fato vermelho ----
f = F([("15.03.2026", "Peticionado o Atestado de Trabalho n 022/2026, no Sistema SEEU, função Poligonal (14/05/2025 a 23/02/2026) totalizando "
                      "630 dias trabalhados e 210 remidos.")])
o = N_(R(rem(210, "09/03/2026", "23/02/2026")), f)
ok(o["fd_novo"]["dif"] == 0 and o["fd_cor"] != "vermelho", "1: totais iguais: %s %s" % (o["fd_novo"]["dif"], o["fd_sit"]))

# ---- 2: atestado lançado em duas linhas da mesma decisão (164 = 52 + 112): a comparação soma as linhas ----
f = F([("27.06.2024", "Peticionado o Atestado de Trabalho n 347/2024, no Sistema SEEU, função Artesanato (01/12/2022 a 28/03/2023) totalizando 101 dias "
                      "trabalhados e 33,66 remidos; função Padaria (01/06/2023 a 27/06/2024) totalizando 392 dias trabalhados e 130,66 remidos.")])
o = N_(R(rem(52, "05/08/2024", "28/03/2023"), rem(112, "05/08/2024", "27/06/2024")), f)
ok(o["fd_novo"]["R"]["concedido"] == 164 and abs(o["fd_novo"]["dif"] - 0.32) < 0.01 and o["fd_novo"]["concl"].startswith("Sem diferença:"),
   "2: linhas 52 + 112: %s" % o["fd_novo"]["dif"])

# ---- 6: leitura - 2ª função sem o parêntese de abertura e atestado de estudo na mesma linha ----
a = rrm.atestados(F([("14.08.2024", "Peticionado o Atestado de Trabalho n 128/2024, no Sistema SEEU, Autos 0049107-59.2007.8.12.0001, função Prendedores "
                                    "Prendebem 19/06/2023 a 22/10/2023) totalizando 90 trabalhados e 30 remidos; função Artesanato (23/10/2023 a 07/06/2024) "
                                    "totalizando 164 dias trabalhados e 54,66 remidos.")])["eventos"])
ok(len(a) == 1 and a[0]["rem"] == 84.66 and len(a[0]["segs"]) == 2, "6: 2ª função sem parêntese: %s" % [(x["rem"], len(x["segs"])) for x in a])
f = F([("15.02.2018", "Nesta data foi emitido Atestado de Trabalho 06/2018, na função de faxineiro, totalizando 627 dias trabalhados e 209 dias remidos. "
                      "E Atestado de Trabalho 07/2018, de estudo, totalizando 80 h/a de estudo e 6 dias remidos. (Enviados para advogada, via email)")])
a = rrm.atestados(f["eventos"])
ok(len(a) == 1 and a[0]["rem"] == 209 and a[0].get("rem_estudo") == 6, "6: atestado de estudo na mesma linha: %s" % [(x["rem"], x.get("rem_estudo")) for x in a])

# ---- 8: atestado sem período no texto, com mais dias que o possível: entra na comparação como está; sugerido para o trabalho do mesmo
# nome desde o fim do atestado anterior (período implícito), com o aviso de dias implausíveis; depois da emissão, "pedir atestado" ----
f = F([("22.04.2023", "Peticionado atestado DE Trabalho n 066/2023, no sistema SEEU, função Prendebem (07/03/2022 a 21/04/2023) totalizando 294 dias trabalhados e 98 remidos."),
       ("22.04.2023", "TRABALHO: Iniciou atividade laboral, no setor de trabalho PRENDE BEM, conforme documento 1."),
       ("24.06.2026", "TRABALHO, nesta data foi emitido atestado de trabalho nº 115 setor de PRENDE BEM com 448 dias de remição.")])
o = N_(R(rem(98, "17/05/2023")), f)
L = o["fd_novo"]["trab"]["linhas"]
p8 = next((p for p in o["fd_novo"]["pontos"] if p["tipo"] == "pedir_atestado"), {})
ok(o["fd_novo"]["comp"] == 546 and o["fd_cor"] == "vermelho" and [x["st"] for x in L] == ["provavel", "sem"] and "25/06/2026 a 06/10/2026" in p8.get("texto", "")
   and any(p["tipo"] == "implausivel" for p in o["fd_novo"]["pontos"]),
   "8: atestado sem período: %s %s %s %s" % (o["fd_novo"]["comp"], o["fd_sit"], [(x["periodo"], x["st"], x["at"]) for x in L], p8.get("texto")))

if falhas:
    print("FALHOU (remição rev7):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: remição rev7 (7.14: totais com decisão antes da emissão e em duas linhas, 2ª função e estudo na leitura, atestado sem período sugerido)")
