"""Teste de regressão da conciliação atestado x remição (rspe_remicao), caso-modelo com os textos da ficha do SIAPEN e
as remições do RSPE (dados de identificação removidos). Rodar: python teste_remicao.py"""
from datetime import date

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
R = {"_incidentes": [{"tipo": "REMIÇÃO", "complemento": "%d Dia(s) Remido(s)" % n, "data_decisao": dd, "data_referencia": rf, "situacao": "CONCEDIDO"}
                     for n, dd, rf in REM]}
M033 = [{"id": 1, "dados": {"tipo": "Trabalho", "numero": "033/2025", "remidos": "102",
                            "trechos": "Horta; 14/11/2023; 17/12/2023\nPoligonal Engenharia; 18/12/2023; 28/06/2024\nArtesanato; 10/08/2024; 18/02/2025"}}]


def _status(C):
    return {(t["atestado"].split("nº ")[-1].split(" ")[0] if "nº" in t["atestado"] else t["atestado"]): (t["status"], t["rspe"]) for t in C["tabela"]}


def caso(manuais):
    C = rr.conciliar(R, F, date(2026, 10, 3), manuais, date(2014, 7, 10))
    st = _status(C)
    for n, d in (("058/2017", 170), ("143/2018", 106), ("041/2020", 129), ("219/2021", 179), ("193/2023", 205)):
        assert st[n] == ("CONCILIADO", "%d dias" % d), (n, st[n])
    assert st["183/PDIB"][0] == "NAO_LANCADO", st["183/PDIB"]
    t183 = next(t for t in C["tabela"] if "183" in t["atestado"])
    assert all(x["inferido"] for x in t183["segs"]) and {x["per"] for x in t183["segs"]} == {"19/02/2025 a 24/03/2026", "30/06/2026 a 07/07/2026"}, t183["segs"]
    assert not any(p["acao"] == "Pedir atestado" for p in C["pendencias"]), "Pedir atestado indevido"
    assert not any(a["tipo"] == "baixa sem início" for a in C["alertas"]), "baixa sem início"
    assert not any(a["tipo"] == "ref" for a in C["alertas"]), "data de referência não pode gerar divergência neste caso"
    tipos = [a["tipo"] for a in C["alertas"]]
    assert "erro de ano" in tipos and "resíduo" in tipos and C["residuo"] == 1, tipos
    return C, st, tipos


C, st, tipos = caso([])
assert st["Atestado não registrado na ficha"] == ("CONCILIADO", "102 dias"), st
C, st, tipos = caso(M033)
assert st["033/2025"] == ("CONCILIADO", "102 dias"), st
assert any(a["tipo"] == "baixa tardia" and "Ags" in a["texto"] and "10/08/2024" in a["texto"] and "17/12/2023" in a["texto"] for a in C["alertas"]), C["alertas"]
assert any(p["status"] == "LACUNA" and p["texto"].startswith("29/06/2024 a 09/08/2024") for p in C["pendencias"]), C["pendencias"]
print("ok: conciliação atestado x remição (caso-modelo, com e sem o atestado 033/2025 informado)")

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
F2 = {"data_impressao": "20/07/2026", "eventos": [{"data": d, "texto": t} for d, t in EV2]}
R2 = {"_incidentes": [{"tipo": "REMIÇÃO", "complemento": "50 Dia(s) Remido(s)", "data_decisao": "16/07/2026", "data_referencia": "14/07/2026", "situacao": "CONCEDIDO"}]}
C2 = rr.conciliar(R2, F2, date(2026, 7, 20))
v2 = [(v["setor"], v["ini"], v["fim"]) for v in C2["vinculos"]]
assert ("Prendebem (prendedores)", date(2026, 1, 18), date(2026, 5, 4)) in v2 and not any("DESATIV" in s.upper() for s, _, _ in v2), v2
a227 = [a for a in C2["atestados"] if a["numero"].startswith("227")][0]
assert [s["setor"] for s in a227["segs"]] == ["Prendebem (prendedores)", "Poligonal Engenharia Ltda", "Faxina"], a227["segs"]
assert not [p for p in C2["pendencias"] if p["status"] in ("SEM_ATESTADO", "A_CONFERIR") and p["data"] < date(2026, 7, 14)], C2["pendencias"]
print("ok: atestado com vários setores e setor desativado no SIAPEN")
