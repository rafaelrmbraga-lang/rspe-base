"""Remição, modelo da 7.14 (aba Ficha): comparação por totais RSPE x ficha, pontos a conferir, trabalho da ficha x atestados com
vinculação (automática, possível, sugerida, sem atestado, informada na conferência) e ✓ Homologado gravado na base. O programa não liga
remição a atestado. Dados fictícios (sem nomes). Rodar: python teste_remicao_714.py"""
import os
import shutil
import sys
import tempfile
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_app as app
import rspe_ficha as rf
import rspe_remicao as rrm
import rspe_view as rv

falhas = []
HOJE = date(2026, 10, 20)
PROC = "0000001-11.2020.8.12.0001"


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def R(*rem, eventos=None):
    """RSPE mínimo: prisão em 2020 e remições [(dias, decisão, referência)]."""
    return {"processo_execucao": PROC, "_crimes": [],
            "_eventos": eventos or [{"data": "01/01/2020", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}],
            "_incidentes": [{"tipo": "REMIÇÃO", "complemento": "%s Dia(s)" % d, "data_decisao": dec, "data_referencia": ref or dec,
                             "situacao": "CONCEDIDO"} for d, dec, ref in rem]}


def T(setor, ini, fim=""):
    return {"setor": setor, "inicio": ini, "fim": fim, "externo": False}


def A(num, data, ini="", fim="", rem=0, trab=0, empresa="", trechos=None, autos=""):
    return {"numero": num, "data": data, "periodo_inicio": ini, "periodo_fim": fim, "dias_remidos": rem, "dias_trabalhados": trab,
            "empresa": empresa, "autos": autos, "trechos": trechos or []}


def F(trabalho=(), atestados=(), eventos=(), **kw):
    f = {"data_impressao": "15.10.2026", "trabalho": list(trabalho), "atestados": list(atestados),
         "eventos": [{"data": d, "texto": t} for d, t in eventos], "leituras": [], "exames": [], "cursos_peticionados": [],
         "certidoes_estudo": [], "estudos": [], "faltas": []}
    f.update(kw)
    return f


def linhas(f, vinculos=None, manuais=None):
    return rrm.trabalho_x_atestados(f, HOJE, manuais, vinculos, date(2020, 1, 1))["linhas"]


def st(L):
    return [(x["local"], x["periodo"].split(" (")[0], x["st"], x["at"]) for x in L]


try:
    # ---- vinculação automática pelo nome: dois trabalhos ao mesmo tempo, o atestado cita a horta ----
    f = F([T("MARCENARIA", "01.02.2024", "30.06.2024"), T("FAXINA", "01.03.2024", "30.04.2024")],
          [A("010/2024", "05.07.2024", "01/02/2024", "30/06/2024", 50, 150, "Marcenaria")])
    L = linhas(f)
    ok(("Marcenaria", "01/02/2024 a 30/06/2024", "auto", "010/2024") in st(L) and L[0]["como"].startswith("período e nome"),
       "auto pelo nome: %s" % st(L))
    # ---- possível: o outro trabalho, no mesmo período, com nome que não confere ----
    ok(("Faxina", "01/03/2024 a 30/04/2024", "possivel", "010/2024") in st(L), "possível com trabalhos sobrepostos: %s" % st(L))
    # ---- automática por exclusividade: único trabalho no período, nome diferente ----
    L = linhas(F([T("COZINHA", "01.02.2024", "30.06.2024")], [A("011/2024", "05.07.2024", "01/02/2024", "30/06/2024", 50, 150, "Empresa Xyz")]))
    ok(st(L) == [("Cozinha", "01/02/2024 a 30/06/2024", "auto", "011/2024")] and "único trabalho" in L[0]["como"], "auto por exclusividade: %s" % st(L))
    # ---- sugerido: atestado sem período, do mesmo nome, emitido depois do início; a parte depois da emissão fica sem atestado ----
    f = F([T("AUXILIAR ADMINISTRATIVO", "22.05.2025", "14.07.2026"), T("LAVANDERIA", "14.07.2026", "08.09.2026")],
          [A("173/PDIB", "07.07.2026", rem=117, empresa="Auxiliar Adm")])
    L = linhas(f)
    ok(st(L) == [("Auxiliar Administrativo", "22/05/2025 a 07/07/2026", "provavel", "173/PDIB"),
                 ("Auxiliar Administrativo", "08/07/2026 a 14/07/2026", "sem", ""),
                 ("Lavanderia", "14/07/2026 a 08/09/2026", "sem", "")], "sugerido + corte na emissão: %s" % st(L))
    T_ = rrm.trabalho_x_atestados(f, HOJE, None, None, date(2020, 1, 1))
    ok(T_["n_vinc"] == 0 and T_["n_tot"] == 3 and T_["dias_sem"] == 7 + 57 - 1, "cabeçalho: %s %s %s" % (T_["n_vinc"], T_["n_tot"], T_["dias_sem"]))
    # ---- lacuna de até 2 dias ignorada; de 3 dias, sem atestado ----
    f = F([T("MARCENARIA", "01.02.2024", "31.05.2024")], [A("020/2024", "01.03.2024", "01/02/2024", "29/02/2024", 10, 30, "Marcenaria"),
                                                    A("021/2024", "01.06.2024", "03/03/2024", "31/05/2024", 10, 30, "Marcenaria")])
    ok([x[2] for x in st(linhas(f))] == ["auto", "auto"], "lacuna de 2 dias ignorada: %s" % st(linhas(f)))
    f["atestados"][1]["periodo_inicio"] = "04/03/2024"
    ok([x[2] for x in st(linhas(f))] == ["auto", "sem", "auto"] and linhas(f)[1]["dias"] == 3, "lacuna de 3 dias: %s" % st(linhas(f)))
    # ---- vínculo informado na conferência; atestado que deixou de existir: vínculo órfão ignorado (sem erro) ----
    f = F([T("PADARIA", "01.02.2025", "30.06.2025"), T("MARCENARIA", "01.02.2025", "30.06.2025")],
          [A("030/2025", "05.07.2025", "01/02/2025", "30/06/2025", 50, 150, "Empresa Abc")])
    L = linhas(f)
    ok([x[2] for x in st(L)] == ["possivel", "possivel"], "dois possíveis: %s" % st(L))
    ch_t, ch_a = L[0]["chave"], rrm.chave_atestado("030/2025", date(2025, 7, 5))
    ok(ch_t == "fd:vt:PADARIA:01.02.2025" and ch_a == "fd:at:030/2025:05.07.2025", "chaves estáveis: %s %s" % (ch_t, ch_a))
    L2 = linhas(f, {ch_t: ch_a, L[1]["chave"]: "sem"})
    ok(st(L2) == [("Padaria", "01/02/2025 a 30/06/2025", "manual", "030/2025"), ("Marcenaria", "01/02/2025 a 30/06/2025", "sem", "")]
       and L2[1]["sem_confirmado"], "vínculo manual e 'sem atestado' confirmado: %s" % st(L2))
    ok([x[2] for x in st(linhas(F(f["trabalho"], []), {ch_t: ch_a}))] == ["sem", "sem"], "vínculo órfão ignorado")

    # ---- persistência: ✓ Homologado e vínculo gravados na base, valendo depois de nova ficha; marca antiga migrada ----
    d = tempfile.mkdtemp()
    try:
        cam = os.path.join(d, "b.sqlite")
        b = app.Base(cam)
        b.baixar(PROC, ch_t, "vínculo (ficha disciplinar)", ch_a)
        b.baixar(PROC, ch_a, "conferido (ficha disciplinar)", "")  # ✓ Homologado (mesma chave das versões anteriores)
        b.baixar(PROC, "fd:est:ESCOLA:01/02/2025 a 30/06/2025", "conferido (ficha disciplinar)", "")  # marca de linha que deixou de existir
        b.con.close()
        b = app.Base(cam)  # reabrir a base: migração
        bx = b.baixas().get(PROC, {})
        ok(ch_a in bx and ch_t in bx and not any(k.startswith("fd:est:") for k in bx), "migração das marcas: %s" % sorted(bx))
        conf, vinc = rv.marcas_ficha(bx)
        ok(conf == {ch_a} and vinc == {ch_t: ch_a}, "marcas: %s %s" % (conf, vinc))
        # nova ficha importada (mais eventos, mesmo trabalho e mesmo atestado): as marcas continuam valendo
        f2 = dict(f, eventos=[{"data": "06.07.2025", "texto": "PETICIONADO ATESTADO DE TRABALHO Nº 030/2025"}], data_impressao="10.10.2026")
        o = rf.comparativo(R((50, "10/08/2025", "30/06/2025")), f2, HOJE, conferidos=conf, vinculos=vinc)
        N = o["fd_novo"]
        ok([x["st"] for x in N["trab"]["linhas"]][0] == "manual", "vínculo depois da nova ficha: %s" % N["trab"]["linhas"])
        dc = [x for x in N["docs"] if x["chave"] == ch_a]
        ok(dc and dc[0]["hom"] and dc[0]["sit"].startswith("Homologado") and o["fd_conf_n"] == 1 and o["fd_conf_tot"] == 1, "✓ Homologado: %s" % dc)
        b.con.close()
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # ---- comparação por totais com tolerância de 3 dias ----
    f = F([T("MARCENARIA", "01.02.2024", "30.06.2024")], [A("040/2024", "05.07.2024", "01/02/2024", "30/06/2024", 52.5, 150, "Marcenaria")],
          [("05.07.2024", "PETICIONADO ATESTADO DE TRABALHO Nº 040/2024")])
    o = rf.comparativo(R((50, "10/08/2024", "30/06/2024")), f, HOJE)
    N = o["fd_novo"]
    ok(N["onde"] == [{"t": "Sem diferença a conferir.", "c": "verde"}], "onde sem diferença: %s" % N["onde"])
    ok(N["comp"] == 52.5 and N["dif"] == 2.5 and N["concl"].startswith("Sem diferença:") and o["fd_cor"] == "verde" and o["fd_sit"] == "Em ordem",
       "tolerância de 3 dias: %s %s %s" % (N["dif"], o["fd_cor"], N["concl"]))
    o = rf.comparativo(R((48, "10/08/2024", "30/06/2024")), f, HOJE)
    N = o["fd_novo"]
    ok(N["dif"] == 4.5 and N["concl"].startswith("Verificar remição") and o["fd_cor"] == "amarelo" and "Verificar remição" in o["fd_sit"]
       and any(i["t"].startswith("Verificar remição: a ficha comprova 52,50 dias e o RSPE concedeu 48 (diferença de 4,50 dias) - conferir nos autos")
               for i in o["fd_sit_itens"]) and "requerer 4" not in str(o), "diferença acima da tolerância: %s" % o["fd_sit_itens"])
    o = rf.comparativo(R((200, "10/08/2024", "30/06/2024")), f, HOJE)
    ok("Comparação pouco informativa" in o["fd_novo"]["concl"] and o["fd_cor"] == "verde", "RSPE muito maior: %s" % o["fd_novo"]["concl"])

    # ---- pontos a conferir: exame, curso sem horas, enviado à Defensoria, posterior à última decisão; vermelho só no fato certo ----
    f = F([T("MARCENARIA", "01.02.2024", "30.06.2024")],
          [A("050/2024", "05.07.2024", "01/02/2024", "30/06/2024", 50, 150, "Marcenaria"),
           A("051/2024", "10.09.2024", "01/07/2024", "31/08/2024", 20, 60, "Marcenaria"),
           A("052/2025", "20.03.2025", "01/09/2024", "28/02/2025", 30, 90, "Marcenaria")],
          [("05.07.2024", "PETICIONADO ATESTADO DE TRABALHO Nº 050/2024"),
           ("10.09.2024", "ATESTADO DE TRABALHO Nº 051/2024 ENCAMINHADO À DEFENSORIA PÚBLICA"),
           ("20.03.2025", "FOI EMITIDO ATESTADO DE TRABALHO Nº 052/2025")],
          exames=[{"exame": "ENCCEJA 2024", "data": "01.12.2024", "certificado": True, "autos": ""}],
          cursos_peticionados=[{"data": "01.02.2025", "texto": "PETICIONADO CURSO DE QUALIFICAÇÃO", "meses": ["10/2024"], "autos": ""}])
    o = rf.comparativo(R((50, "01/08/2024", "30/06/2024"), (20, "15/01/2025", "31/08/2024")), f, HOJE)
    N = o["fd_novo"]
    tp = {p["tipo"]: p for p in N["pontos"]}
    ok("exame" in tp and "ENCCEJA 2024" in tp["exame"]["texto"] and "áreas" in tp["exame"]["texto"], "ponto: exame %s" % list(tp))
    ok("sem_valor" in tp and "Curso de qualificação" in tp["sem_valor"]["texto"] and "carga horária" in tp["sem_valor"]["texto"], "ponto: curso sem horas")
    ok("defensoria" in tp and "051/2024" in tp["defensoria"]["texto"] and "sem registro de protocolo" in tp["defensoria"]["texto"], "ponto: enviado à Defensoria")
    ok("sem_pet_posterior" in tp and "052/2025" in tp["sem_pet_posterior"]["texto"] and "15/01/2025" in tp["sem_pet_posterior"]["texto"]
       and o["fd_cor"] == "vermelho" and o["fd_sit"].startswith("Atestado sem peticionamento"),
       "fato certo (sem peticionamento e posterior à última decisão): %s / %s" % (list(tp), o["fd_sit"]))
    d052 = next(x for x in N["docs"] if x["num"] == "052/2025")
    ok(d052["cor"] == "vermelho" and N["fatos"] and N["fatos"][0]["dias"] == 30 and rf.remicao_pendente(o)[0][2] == 30.0,
       "fato: dias a conferir nos autos: %s" % N["fatos"])
    # "Onde pode estar a diferença" (visão inicial): até 4 linhas, o fato certo primeiro
    ok(N["onde"] and len(N["onde"]) <= 4 and N["onde"][0]["c"] == "vermelho" and "052/2025" in N["onde"][0]["t"]
       and "sem decisão de remição posterior no RSPE (última: 15/01/2025)" in N["onde"][0]["t"], "onde: %s" % N["onde"])
    # o corte é a data da DECISÃO, não a da referência: o 051/2024 (emitido antes da decisão de 15/01/2025, ref. 31/08/2024) não é posterior
    ok(not any("051/2024" in x["rotulo"] for x in N["fatos"]), "corte pela decisão: %s" % N["fatos"])
    # curso posterior à última decisão: amarelo "posterior"
    ok("posterior" in tp and "Curso de qualificação" in tp["posterior"]["texto"], "posterior à última decisão: %s" % tp.get("posterior"))
    # ✓ Homologado tira o documento dos pontos e do fato
    o2 = rf.comparativo(R((50, "01/08/2024", "30/06/2024"), (20, "15/01/2025", "31/08/2024")), f, HOJE,
                        conferidos={rrm.chave_atestado("052/2025", date(2025, 3, 20))})
    ok(o2["fd_cor"] == "amarelo" and not o2["fd_novo"]["fatos"], "homologado sai do fato: %s" % o2["fd_novo"]["fatos"])
    # ---- trabalho sem atestado depois do último atestado: pedir atestado (estimativa, fora da comparação) ----
    f = F([T("MARCENARIA", "01.02.2024", "")], [A("060/2024", "05.07.2024", "01/02/2024", "30/06/2024", 50, 150, "Marcenaria")],
          [("05.07.2024", "PETICIONADO ATESTADO DE TRABALHO Nº 060/2024")])
    o = rf.comparativo(R((50, "01/08/2024", "30/06/2024")), f, HOJE)
    tp = {p["tipo"]: p for p in o["fd_novo"]["pontos"]}
    ok("pedir_atestado" in tp and "Pedir o atestado" in tp["pedir_atestado"]["texto"] and o["fd_atestar"] == "Sim"
       and o["fd_novo"]["comp"] == 50 and "Pedir atestado" in o["fd_sit"], "pedir atestado: %s / %s" % (list(tp), o["fd_sit"]))
    # trabalho em curso há até 90 dias: acompanhar (o atestado ainda não costuma ter sido emitido), sem "pedir atestado"
    f = F([T("MARCENARIA", "01.02.2024", "30.06.2024"), T("COPA", "01.09.2026", "")],
          [A("061/2024", "05.07.2024", "01/02/2024", "30/06/2024", 50, 150, "Marcenaria")], [("05.07.2024", "PETICIONADO ATESTADO DE TRABALHO Nº 061/2024")])
    o = rf.comparativo(R((50, "01/08/2024", "30/06/2024")), f, HOJE)
    tp = [p["tipo"] for p in o["fd_novo"]["pontos"]]
    ok("em_curso" in tp and "pedir_atestado" not in tp and o["fd_cor"] == "verde", "em curso há até 90 dias: %s %s" % (tp, o["fd_cor"]))
except Exception as e:
    import traceback
    traceback.print_exc()
    falhas.append("erro: %s" % e)

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for x in falhas:
        print(" -", x)
    sys.exit(1)
print("ok: remição 7.14 (comparação por totais, pontos a conferir, trabalho x atestados com vinculação, ✓ Homologado e vínculo gravados)")
