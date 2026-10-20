"""Teste de regressão da remição pela ficha x RSPE (modelo da 7.14: comparação por totais e trabalho da ficha x atestados; até a 7.13,
conciliação atestado x remição), caso-modelo com os textos da ficha do SIAPEN e as remições do RSPE (dados de identificação
removidos). Rodar: python teste_remicao.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf
import rspe_remicao as rr

EV = [
    ("23.09.2015", "Nesta data passa a exercer atividade laboral no setor de Artesanato, conforme CI nº 072/15/ST/PDIB/AGEPEN/MS."),
    ("04.09.2017", "Nesta data foi emitido o atestado de Trabalho Prisional nº 058/2017, do período de 23/09/2015 à 04/09/2017 totalizando 510 dias Trabalhados e 170 dias Remidos."),
    ("23.11.2018", "Nesta data foi peticionado o Atestado n 143/2018, na função Artesanato (05/09/2018 a 23/11/2018) totalizando 318 dias trabalhados e 106 dias remidos."),
    ("07.03.2019", "TRABALHO: Iniciou atividade laboral, no setor de trabalho PP - AGS PRESTADORA - ME, conforme documento 014/19/ST/PDIB/AGEPEN/MS."),
    ("05.03.2020", "Nesta data foi peticionado o Atestado de trabalho n 041/2020, no Sistema SEEU Autos 0000000-00.2015.8.12.0005, Artesanato (24/11/2018 a 07/03/2019) totalizando 75 dias trabalhados e 25 dias remidos, função Horta (08/03/2019 a 05/03/2020) totalizando 312 dias trabalhados e 104 remidos."),
    ("23.11.2021", "Peticionado o Atestado de trabalho n 219/2021, no Sistema SEEU, Autos 0000000-00.2015.8.12.0005, função Horta (06/03/2020 a 23/11/2021) totalizando 538 dias trabalhados e 179,33 dias remidos."),
    ("13.11.2023", "Peticionado o Atestado de trabalho n 193/2023, no Sistema SEEU, Autos 0000000-00.2015.8.12.0005, função Horta (24/11/2021 a 13/11/2023) totalizando 617 dias trabalhados e 205,66 remidos."),
    ("18.12.2023", "TRABALHO: Iniciou atividade laboral, no setor de trabalho POLIGONAL ENGENHARIA LTDA, conforme documento 079/23/ST/PDIB/AGEPEN/MS."),
    ("28.06.2024", "TRABALHO: Deixa de trabalhar, no setor de trabalho POLIGONAL ENGENHARIA LTDA, conforme documento N/C, motivo: Dispensado pelo empregador. ."),
    ("10.08.2024", "TRABALHO: Iniciou atividade laboral, no setor de trabalho ARTESANATO, conforme documento N/C."),
    ("10.08.2024", "TRABALHO: Deixa de trabalhar, no setor de trabalho PP - AGS PRESTADORA - ME, conforme documento N/C, motivo: N/C."),
    ("19.02.2025", "TRABALHO: Iniciou atividade laboral, no setor de trabalho POLIGONAL ENGENHARIA LTDA, conforme documento CI 015/25/ST/PDIB/AGEPEN/MS."),
    ("19.02.2025", "TRABALHO: Deixa de trabalhar, no setor de trabalho ARTESANATO, conforme documento N/C, motivo: N/C."),
    ("24.03.2026", "TRABALHO: Deixa de trabalhar, no setor de trabalho POLIGONAL ENGENHARIA LTDA, conforme documento N/C, motivo: DISPENSADO PELO EMPREGADOR ."),
    ("30.06.2026", "TRABALHO: Iniciou atividade laboral, no setor de trabalho EMPRESA PAIVA LINGERIE, conforme documento C.I N110/2026/ST/C.T.C/PDIB/AG."),
    ("07.07.2026", "TRABALHO: Deixa de trabalhar, no setor de trabalho EMPRESA PAIVA LINGERIE, conforme documento N/C, motivo: LIBERADO PELO EMPREGADOR ."),
    ("07.07.2026", "TRABALHO, nesta data foi emitido atestado de trabalho nº183/PDIB/AGEPEN/MS setor de PAIVA LANGERIE E POLIGONAL NÃO RESTANDO NADA A PETICIONAR ANTES DESTA DATA. com 116dias de remição."),
]
REM = [(170, "26/09/2017", "26/09/2017"), (106, "12/02/2019", "12/02/2019"), (129, "06/04/2020", "06/04/2020"),
       (179, "30/03/2022", "30/03/2022"), (205, "17/11/2023", "13/11/2023"), (102, "29/04/2025", "18/02/2025")]
F = {"data_impressao": "03/10/2026", "eventos": [{"data": d, "texto": t} for d, t in EV]}
R = {"_eventos": [{"data": "10/07/2014", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}], "_incidentes": [{"tipo": "REMIÇÃO", "complemento": "%d Dia(s) Remido(s)" % n, "data_decisao": dd, "data_referencia": rf, "situacao": "CONCEDIDO"}
                     for n, dd, rf in REM]}
M033 = [{"id": 1, "dados": {"tipo": "Trabalho", "numero": "033/2025", "remidos": "102",
                            "trechos": "Horta; 14/11/2023; 17/12/2023\nPoligonal Engenharia; 18/12/2023; 28/06/2024\nArtesanato; 10/08/2024; 18/02/2025"}}]


def linhas(N):
    return [(L["local"], L["periodo"].split(" (")[0], L["st"], L["at"]) for L in N["trab"]["linhas"]]


f = rf.atualizar(dict(F, eventos=[dict(e) for e in F["eventos"]]))
# leitura (funções de leitura de rspe_remicao): segmentos do atestado com dois setores; atestado sem período
ats = {a["numero"]: a for a in rr.atestados(f["eventos"])}
assert [(x["setor"], x["ini"], x["fim"]) for x in ats["041/2020"]["segs"]] == [
    ("Artesanato", date(2018, 11, 24), date(2019, 3, 7)), ("Ags Prestadora - Me (Horta)", date(2019, 3, 8), date(2020, 3, 5))], ats["041/2020"]["segs"]
assert not any(x["ini"] for x in ats["183/PDIB"]["segs"]) and ats["183/PDIB"]["rem"] == 116, ats["183/PDIB"]


def caso(manuais):
    o = rf.comparativo(R, f, date(2026, 10, 3), manuais=manuais)
    N = o["fd_novo"]
    # o RSPE concedeu 891 dias em 6 decisões; a ficha comprova os atestados desta execução (sem ligar remição a atestado)
    assert N["R"]["concedido"] == 891 and len(N["R"]["remicoes"]) == 6, N["R"]
    # 183/PDIB: emitido depois da última decisão (29/04/2025) e sem peticionamento ("não restando nada a peticionar" não é peticionamento)
    d183 = next(d for d in N["docs"] if d["num"] == "183/PDIB")
    assert d183["cor"] == "vermelho" and not d183["pet_ok"] and o["fd_cor"] == "vermelho", (d183, o["fd_sit"])
    # trabalho já remido (anterior ao último atestado): nunca "pedir atestado"
    assert not any(p["tipo"] == "pedir_atestado" for p in N["pontos"]), N["pontos"]
    # atestados com período e nome do setor: vinculados automaticamente
    L = linhas(N)
    for per, at in (("07/03/2019 a 05/03/2020", "041/2020"), ("06/03/2020 a 23/11/2021", "219/2021"), ("24/11/2021 a 13/11/2023", "193/2023")):
        assert ("Ags Prestadora - Me (Horta)", per, "auto", at) in L, (per, L)
    # o 183/PDIB (sem período no texto, mesmo nome) é sugerido para o último trabalho, posterior ao último período atestado
    assert ("Paiva Lingerie", "30/06/2026 a 07/07/2026", "provavel", "183/PDIB") in L, L
    return o, N, L


o, N, L = caso([])
assert N["comp"] == 905.99 and N["dif"] == 14.99 and "Verificar remição" in o["fd_sit"], (N["comp"], N["dif"], o["fd_sit"])
assert ("Poligonal Engenharia Ltda", "18/12/2023 a 28/06/2024", "sem", "") in L and ("Artesanato", "10/08/2024 a 19/02/2025", "sem", "") in L, L
# com o atestado 033/2025 informado pela equipe (juntado nos autos): entra na soma e cobre os trechos que cita
o, N, L = caso(M033)
assert N["comp"] == 1007.99 and N["dif"] == 116.99 and N["man"] == 102, (N["comp"], N["dif"])
assert ("Poligonal Engenharia Ltda", "18/12/2023 a 28/06/2024", "auto", "033/2025") in L and ("Artesanato", "10/08/2024 a 18/02/2025", "auto", "033/2025") in L, L
assert ("Ags Prestadora - Me (Horta)", "14/11/2023 a 18/12/2023", "auto", "033/2025") in L, L  # trecho "Horta" do atestado
print("ok: remição pela ficha x RSPE (caso-modelo, com e sem o atestado 033/2025 informado)")

# atestado em lote com vários setores ("setor de A, B e C com N dias") e setor desativado no SIAPEN ("XXDESATIVADO")
EV2 = [
    ("18.01.2026", "TRABALHO: Iniciou atividade laboral, no setor de trabalho XXDESATIVADO6098, conforme documento CI 003/26/ST/PDIB/AGEPEN/MS."),
    ("18.01.2026", "SETOR DE TRABALHO: NESTA DATA PASSA A TRABALHAR NO SETOR PRENDEDORES PRENDEBEM"),
    ("04.05.2026", "TRABALHO: Deixa de trabalhar, no setor de trabalho XXDESATIVADO6098, conforme documento N/C, motivo: MUDANÇA DE ATIVIDADE"),
    ("04.05.2026", "Liberação do Setor de Trabalho - Doc.: N/C Motivo: MUDANÇA DE ATIVIDADE"),
    ("05.05.2026", "TRABALHO: Iniciou atividade laboral, no setor de trabalho POLIGONAL ENGENHARIA LTDA, conforme documento N/C."),
    ("10.06.2026", "TRABALHO: Deixa de trabalhar, no setor de trabalho POLIGONAL ENGENHARIA LTDA, conforme documento N/C, motivo: N/C."),
    ("10.06.2026", "TRABALHO: Iniciou atividade laboral, no setor de trabalho FAXINA, conforme documento N/C."),
    ("14.07.2026", "TRABALHO, nesta data foi emitido atestado de trabalho nº227/PDIB/AGEPEN/MS setor de PRENDE BEM, POLIGONAL ENGENHARIA LTDA e FAXINA com 50 dias de remição."),
]
evs2 = [{"data": d, "texto": t} for d, t in EV2]
v2 = [(v["setor"], v["ini"], v["fim"]) for v in rr.vinculos(evs2, date(2026, 7, 20), date(2026, 7, 20))[0]]
assert ("Prendebem (prendedores)", date(2026, 1, 18), date(2026, 5, 4)) in v2 and not any("DESATIV" in s.upper() for s, _, _ in v2), v2
a227 = [a for a in rr.atestados(evs2) if a["numero"].startswith("227")][0]
assert [s["setor"] for s in a227["segs"]] == ["Prendebem (prendedores)", "Poligonal Engenharia Ltda", "Faxina"], a227["segs"]
print("ok: atestado com vários setores e setor desativado no SIAPEN")
