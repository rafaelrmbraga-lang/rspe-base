"""Conferência 7.14.3, frente remição: atestado sem período e sem setor que comporta todo o trabalho sem atestado do intervalo
(sugerido, não pedido em dobro), vínculo sem baixa (só a saída da unidade) depois do último dia documentado ("a conferir", não
"pedir atestado"), atestados repetidos (fica o que tem remição do mesmo valor no RSPE), certidão do semestre interrompido (estimativa
e ligação só quando o valor fecha) e atestado de estudo com dias declarados (documento da comparação, com "conferir datas").
Dados fictícios (sem nomes). Rodar: python teste_conf4_remicao.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf

falhas = []
HOJE = date(2026, 10, 20)
PROC = "0000001-11.2018.8.12.0001"
EV = [{"data": "01/03/2014", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}]


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def R(*rem):
    """RSPE mínimo: prisão em 2014 e remições [(dias, decisão, referência)]."""
    return {"processo_execucao": PROC, "_crimes": [], "_eventos": EV,
            "_incidentes": [{"tipo": "REMIÇÃO", "complemento": "%s Dia(s)" % d, "data_decisao": dec, "data_referencia": ref or dec,
                             "situacao": "CONCEDIDO"} for d, dec, ref in rem]}


def T(setor, ini, fim="", **kw):
    return dict({"setor": setor, "inicio": ini, "fim": fim, "externo": False}, **kw)


def A(num, data, ini="", fim="", rem=0, trab=0, empresa="", trechos=None, autos=""):
    return {"numero": num, "data": data, "periodo_inicio": ini, "periodo_fim": fim, "dias_remidos": rem, "dias_trabalhados": trab,
            "empresa": empresa, "autos": autos, "trechos": trechos or []}


def F(trabalho=(), atestados=(), eventos=(), **kw):
    f = {"data_impressao": "15.10.2026", "trabalho": list(trabalho), "atestados": list(atestados),
         "eventos": [{"data": d, "texto": t} for d, t in eventos], "leituras": [], "exames": [], "cursos_peticionados": [],
         "certidoes_estudo": [], "estudos": [], "faltas": []}
    f.update(kw)
    return f


def comp(r, f):
    o = rf.comparativo(r, f, HOJE)
    return o, o["fd_novo"]


def linha(N, local):
    return next(L for L in N["trab"]["linhas"] if L["local"].startswith(local))


def doc(N, num):
    return next(d for d in N["docs"] if d["num"] == num)


def tipos(N):
    return {p["tipo"]: p for p in N["pontos"]}


try:
    # ---- 1) atestado sem período e sem setor que declara mais dias do que todo o trabalho sem atestado do intervalo (do fim do
    # atestado anterior à emissão): o trabalho cabe nele - "Sugerido · confirmar", não "pedir atestado" (pedido em dobro) ----
    f = F([T("LAVOURA", "01.03.2016", "30.06.2016"), T("COSTURA", "01.08.2020", "31.12.2020"), T("MADEIREIRA", "01.04.2022", "30.10.2022")],
          [A("010/2017", "10.01.2017", "01/03/2016", "30/06/2016", 30, 90, "Lavoura"), A("012/2024", "29.01.2024", rem=118, trab=356)])
    o, N = comp(R((30, "01/03/2017", None)), f)
    cos, mad = linha(N, "Costura"), linha(N, "Madeireira")
    ok(cos["st"] == "provavel" and mad["st"] == "provavel" and cos["at"] == "012/2024" and mad["at"] == "012/2024",
       "1: trabalho no intervalo sugerido para o 012/2024: %s %s" % (cos["st"], mad["st"]))
    ok(not N["pedir_dias"] and "pedir_atestado" not in tipos(N), "1: nada a pedir em dobro: %s" % N["pedir_dias"])
    # com setor no atestado que não confere, nada muda (sem ligação por nome nem por capacidade)
    f["atestados"][1]["empresa"] = "Olaria"
    o, N = comp(R((30, "01/03/2017", None)), f)
    ok(linha(N, "Costura")["st"] == "sem", "1: atestado de outro setor não cobre: %s" % linha(N, "Costura")["st"])
    # sem o atestado anterior delimitando o intervalo, também nada muda
    f = F([T("COSTURA", "01.08.2020", "31.12.2020")], [A("012/2024", "29.01.2024", rem=118, trab=356)])
    o, N = comp(R(), f)
    ok(linha(N, "Costura")["st"] == "sem", "1: sem intervalo delimitado: %s" % linha(N, "Costura")["st"])

    # ---- 2) vínculo sem baixa (o fim é só a saída da unidade, anos depois): depois do último dia documentado do vínculo (remição
    # que o cobre), "a conferir" - não "pedir atestado"; o vínculo com baixa continua a pedir ----
    sg = T("SERVIÇOS GERAIS", "15.02.2012", "10.06.2016", texto_livre=True, motivo_fim="saída/evasão/transferência")
    o, N = comp(R((120, "05/03/2013", None), (100, "29/08/2014", None), (45, "14/04/2015", None)), F([sg]))
    L = linha(N, "Servicos Gerais")
    ok(L.get("talvez_dias") and L.get("conf_dias") and (not L.get("pedir_dias") or L["pedir_fim"] < date(2015, 4, 15)),
       "2: %s" % {k: L.get(k) for k in ("talvez_dias", "pedir_dias", "pedir_fim", "conf_dias")})
    ok(L.get("conf_ini") == date(2015, 4, 15) and L.get("conf_fim") == date(2016, 6, 10) and "sem_baixa" in tipos(N),
       "2: trecho a conferir: %s %s" % (L.get("conf_ini"), list(tipos(N))))
    ok("15/04/2015" not in o["fd_fund"] and "10/06/2016" not in o["fd_fund"], "2: fundamentação não pede o trecho sem baixa")
    # coberto até a última remição: a linha toda fica "pode já estar remido" + "a conferir"
    o, N = comp(R((400, "14/04/2015", None)), F([sg]))
    L = linha(N, "Servicos Gerais")
    ok(not L.get("pedir_dias") and L.get("conf_dias") and not N["pedir_dias"], "2: %s" % {k: L.get(k) for k in ("talvez_dias", "pedir_dias", "conf_dias")})
    ok("vínculo sem baixa" in next(x["sit"] for x in o["fd_linhas"] if x["emp"].startswith("Servicos Gerais")), "2: linha da aba")
    sg2 = dict(sg, motivo_fim="desligado")
    o, N = comp(R((120, "05/03/2013", None), (100, "29/08/2014", None), (45, "14/04/2015", None)), F([sg2]))
    L = linha(N, "Servicos Gerais")
    ok(L.get("pedir_dias") and not L.get("conf_dias"), "2: com baixa, pedir: %s" % {k: L.get(k) for k in ("pedir_dias", "conf_dias")})
    # vínculo sem baixa sem nenhum dia documentado: continua a pedir (não há "última remição" do vínculo)
    o, N = comp(R(), F([sg]))
    L = linha(N, "Servicos Gerais")
    ok(L.get("pedir_dias") and not L.get("conf_dias"), "2: sem remição, pedir: %s" % {k: L.get(k) for k in ("pedir_dias", "conf_dias")})

    # ---- 3) dois atestados que se repetem (mesmo período, setores simultâneos): fica o que tem remição do mesmo valor no RSPE, ainda
    # que tenha menos dias; sai o outro ----
    f = F([T("PRENDEDOR", "16.07.2023", "16.12.2023"), T("COZINHA", "16.07.2023", "16.12.2023")],
          [A("349/2023", "11.10.2023", "16/07/2023", "08/10/2023", 24.3, 73, "Prendedor"), A("350/2023", "11.10.2023", "16/07/2023", "11/10/2023", 25.3, 76, "Cozinha")])
    o, N = comp(R((24, "12/03/2024", "08/10/2023")), f)
    ok(not doc(N, "349/2023").get("contido") and doc(N, "349/2023").get("provavel") == "12/03/2024", "3: 349 fica: %s" % doc(N, "349/2023")["sit"])
    ok(doc(N, "350/2023").get("dias_soma") == 0 and "349/2023" in doc(N, "350/2023")["sit"], "3: 350 sai: %s" % doc(N, "350/2023")["sit"])
    # sem remição de nenhum dos dois: fica o de mais dias (regra anterior)
    o, N = comp(R(), f)
    ok(doc(N, "349/2023").get("dias_soma") == 0 and not doc(N, "350/2023").get("contido"), "3: sem remição, fica o de mais dias")

    # ---- 4) certidões sem a carga horária: estimativa pela matrícula (semestre interrompido aparece); a remição que pode ser de duas
    # certidões liga-se só quando o valor fecha (sozinha ou somadas); senão, "conferir" ----
    est = [{"curso": "SETOR ESCOLAR", "inicio": "17.02.2025", "fim": "29.08.2025", "motivo_fim": "matrícula cancelada", "horas": None}]
    cert = lambda d, s, a: {"data": d, "semestre": s, "ano": a, "autos": "", "texto": "Peticionado Certidão de Frequência Escolar referente ao %dº semestre de %d" % (s, a)}
    f = F(estudos=est, certidoes_estudo=[cert("17.11.2025", 1, 2025), cert("05.03.2026", 2, 2025)])
    o, N = comp(R((40, "11/03/2026", None)), f)
    c1, c2 = doc(N, "1º semestre de 2025"), doc(N, "2º semestre de 2025")
    ok(c2.get("estim") and c2["estim"]["corte"] == date(2025, 8, 29) and 9 <= c2["estim"]["dias"] <= 12, "4: estimativa do 2º sem.: %s" % c2.get("estim"))
    ok("semestre interrompido: estimativa" in c2["sem_valor"], "4: texto da estimativa: %s" % c2["sem_valor"])
    ok("somada à certidão do 2º semestre" in c1["sit"] and "somada à certidão do 1º semestre" in c2["sit"], "4: soma fecha: %s | %s" % (c1["sit"], c2["sit"]))
    o, N = comp(R((80, "11/03/2026", None)), f)
    c1, c2 = doc(N, "1º semestre de 2025"), doc(N, "2º semestre de 2025")
    ok(c1["sit"].startswith("A remição de 80 dias de 11/03/2026 pode ser deste documento ou da certidão do 2º semestre") and not c2.get("provavel_ex"),
       "4: não fecha, conferir: %s | %s" % (c1["sit"], c2["sit"]))
    # uma certidão só: liga como antes (sem ambiguidade)
    f = F(estudos=est, certidoes_estudo=[cert("05.03.2026", 2, 2025)])
    o, N = comp(R((7, "11/03/2026", None)), f)
    ok(doc(N, "2º semestre de 2025")["sit"].startswith("Possivelmente remido em 11/03/2026 (7 dias)"), "4: única: %s" % doc(N, "2º semestre de 2025")["sit"])

    # ---- 5) atestado de estudo com os dias declarados ("06 dias a serem remidos") e datas invertidas: documento de 6 dias na
    # comparação, com "conferir datas"; a leitura da ficha guarda os dias e a emissão ----
    ev = [{"data": "31.03.2016", "texto": "Foi emitido para fins de Progressão de Regime: Atestado de Trabalho Prisional nº 028/2016 na função de "
                                         "estudante de 27/04/2015 à 10/02/2015, totalizando 75 H/A , com 06 dias a serem remidos."}]
    es = rf._estudos(ev)
    e0 = next((x for x in es if x["curso"] == "Atestado de estudo nº 028/2016"), None)
    ok(e0 and e0.get("dias_remidos") == 6 and e0.get("data") == "31.03.2016", "5: leitura: %s" % es)
    es2 = rf._estudos([{"data": "03.11.2022", "texto": "EMITIDO ATP Nº 329/2022; CURSO DE PINTOR; DATA INICIAL: 02.05.2022; DATA FINAL 02.08.2022; "
                                                      "CARGA HORÁRIA TOTAL EM HORAS: 180 H; TEMPO TOTAL DE REMIÇÃO: 7,5 DIAS REMIDOS."}])
    ok(es2 and es2[0].get("dias_remidos") == 7.5, "5: dias com fração: %s" % es2)
    if e0:
        o, N = comp(R(), F(estudos=[e0]))
        d = doc(N, "028/2016")
        ok(d["tipo"] == "Atestado de estudo" and d["dias"] == 6 and d["periodo"] == "10/02/2015 a 27/04/2015" and "conferir datas" in d["sit"],
           "5: documento: %s" % {k: d.get(k) for k in ("tipo", "dias", "periodo", "sit")})
        ok(N["est_comp"] == 6 and N["comp"] == 6 and not N["est_estim"], "5: na comparação, fora da estimativa: %s %s" % (N["est_comp"], N["est_estim"]))
    # sem os dias declarados, continua estimativa (estudo sem certidão)
    o, N = comp(R(), F(estudos=[{"inicio": "27.04.2015", "fim": "10.02.2015", "curso": "Atestado de estudo nº 028/2016", "horas": 75, "livre": True}]))
    ok(N["est_estim"] and not N["est_comp"], "5: sem dias declarados, estimativa")
except Exception as e:
    import traceback
    traceback.print_exc()
    falhas.append("exceção: %r" % e)

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for x in falhas:
        print(" -", x)
    sys.exit(1)
print("ok: conferência 7.14.3, remição (atestado sem período que comporta o trabalho, vínculo sem baixa, atestados repetidos, certidão do "
      "semestre interrompido, atestado de estudo com dias declarados)")
