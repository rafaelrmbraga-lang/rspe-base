"""Monitor da aba Jurisprudências (7.16.0/7.16.1): sentido de cada decisão, turma inferida pelo relator, números e séries, taxa de
acolhimento só com desfavoráveis no recorte, filtros e facetas, relatório em PDF; base nos dois sentidos (monitor_juris.bin) e
Api.teses_monitor com a base real; a Pesquisa continua só com as favoráveis."""
import os, sys, tempfile, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
wv = types.ModuleType("webview"); wv.SAVE_DIALOG = 1; wv.FOLDER_DIALOG = 2; wv.OPEN_DIALOG = 0; sys.modules["webview"] = wv
import rspe_monitor as M

falhas = []


def ok(c, m):
    if not c:
        falhas.append(m)


# ---- sentido ----
S = M.sentido
ok(S({"rot": "Recurso do MP desprovido", "resultado": "Desprovido / Improcedente"}) == "favoravel", "MP desprovido = favorável")
ok(S({"rot": "Ordem concedida de ofício", "resultado": "Não conhecido"}) == "favoravel", "HC não conhecido com ordem de ofício = favorável")
ok(S({"rot": "Ordem concedida", "resultado": "Parcialmente provido / procedente"}) == "parcial", "resultado parcial = parcial")
ok(S({"rot": "Parcialmente provido", "resultado": "Provido / Procedente"}) == "parcial", "rótulo parcial = parcial")
ok(S({"rot": "Recurso da defesa provido"}) == "favoravel", "defesa provido = favorável")
ok(S({"rot": "Recurso da defesa desprovido"}) == "desfavoravel", "defesa desprovido = desfavorável")
ok(S({"rot": "Recurso do MP provido"}) == "desfavoravel", "MP provido = desfavorável")
ok(S({"rot": "Ordem denegada"}) == "desfavoravel", "ordem denegada = desfavorável")
ok(S({"rot": "Reclamação improcedente"}) == "desfavoravel", "reclamação improcedente = desfavorável")
ok(S({"rot": "Reclamação procedente", "resultado": "Provido / Procedente"}) == "favoravel", "reclamação procedente = favorável")
ok(S({"resultado": "Provido / Procedente"}) == "favoravel", "sem rótulo: provido = favorável")
ok(S({"resultado": "Desprovido / Improcedente"}) == "desfavoravel", "sem rótulo: desprovido = desfavorável")
ok(S({"resultado": "Não conhecido"}) == "nao_conhecido", "sem rótulo: não conhecido")
ok(S({"resultado": "Provido / Procedente", "sentido": "desfavoravel"}) == "desfavoravel", "campo sentido explícito prevalece")
ok(S({"rot": "Ordem concedida", "sentido": "qualquer"}) == "favoravel", "sentido inválido é ignorado")

# ---- nível do órgão ----
ok(M.nivel("1ª Câmara Criminal") == "camara" and M.nivel("Sexta Turma") == "camara", "câmara/turma")
ok(all(M.nivel(o) == "secao" for o in ("1ª Seção Criminal", "Terceira Seção", "Corte Especial", "Tribunal Pleno", "Seção Especial - Criminal")), "seções")
ok(M.nivel("") == "", "vazio")


# ---- conjunto fictício ----
def it(i, trib, tipo, orgao, rel, julg, temas, rot="Ordem concedida", res="Provido / Procedente", **k):
    d = {"id": "x%d" % i, "tribunal": trib, "tipo": tipo, "orgao": orgao, "relator": rel, "julg": julg, "temas": temas, "rot": rot,
         "resultado": res, "proc": "HC %d" % i, "tese": "Tese %d" % i}
    d.update(k)
    return d


A = [it(1, "STJ", "Acórdão", "Sexta Turma", "Ana Alves", "10/03/2021", ["Remição"]),
     it(2, "STJ", "Acórdão", "Sexta Turma", "Ana Alves", "11/03/2022", ["Remição"]),
     it(3, "STJ", "Acórdão", "Terceira Seção", "Ana Alves", "12/03/2022", ["Remição"]),  # seção não conta para a turma
     it(4, "STJ", "Monocrática", "", "Ana Alves", "01/02/2024", ["Remição", "Falta grave e PAD"]),  # turma inferida: Sexta
     it(5, "STJ", "Acórdão", "Quinta Turma", "Bruno Borges", "05/05/2023", ["Falta grave e PAD"]),
     it(6, "STJ", "Acórdão", "Sexta Turma", "Bruno Borges", "06/05/2023", ["Falta grave e PAD"]),
     it(7, "STJ", "Monocrática", "", "Bruno Borges", "07/05/2023", ["Falta grave e PAD"]),  # 1x1: sem turma inequívoca
     it(8, "STJ", "Monocrática", "", "", "08/05/2024", ["Remição"]),  # sem relator
     it(9, "TJMS", "Acórdão", "1ª Câmara Criminal", "Des. Fulano", "09/09/2025", ["Remição"], rot="Recurso do MP desprovido", res="Desprovido / Improcedente"),
     it(10, "TJMS", "Acórdão", "1ª Câmara Criminal", "Fulano", "10/09/2025", ["Remição"], rot=None, res="Parcialmente provido / procedente"),
     it(11, "TJMS", "Acórdão", "1ª Seção Criminal", "Fulano", "11/09/2025", ["Remição"], rot=None, res="Provido / Procedente"),
     it(12, "STF", "Monocrática", "", "Carla Costa", "12/12/2025", ["Prescrição"]),
     it(13, "STJ", "Monocrática", "", "Rogerio Schietti", "01/01/2026", ["Remição"]),  # grafia alternativa: mesmo relator
     it(14, "STJ", "Acórdão", "Sexta Turma", "Rogerio Schietti Cruz", "02/01/2026", ["Remição"])]

T = M.turmas_por_relator(A)
ok(T.get(("STJ", "Ana Alves")) == "Sexta Turma", "turma inferida pela maioria (seção não conta): %r" % T)
ok(("STJ", "Bruno Borges") not in T, "empate 1x1 não infere turma")
ok(T.get(("STJ", "Rogerio Schietti Cruz")) == "Sexta Turma", "alias do relator")
ok(M.turmas_por_relator([it(1, "STJ", "Acórdão", "Sexta Turma", "Xavier", "", []), it(2, "STJ", "Acórdão", "Sexta Turma", "Xavier", "", []),
                         it(3, "STJ", "Acórdão", "Quinta Turma", "Xavier", "", [])]).get(("STJ", "Xavier")) == "Sexta Turma", "2 de 3 (2/3) basta")
ok(("STJ", "Xavier") not in M.turmas_por_relator([it(1, "STJ", "Acórdão", "Sexta Turma", "Xavier", "", []), it(2, "STJ", "Acórdão", "Sexta Turma", "Xavier", "", []),
                                             it(3, "STJ", "Acórdão", "Quinta Turma", "Xavier", "", []), it(4, "STJ", "Acórdão", "Quinta Turma", "Xavier", "", [])]), "2x2 não basta")

L = M.preparar(A)
P = {x["id"]: x for x in L}
ok(P["x4"]["orgao"] == "Sexta Turma" and P["x4"]["inferido"] and P["x4"]["camara"] == "Sexta Turma", "monocrática do relatora Ana: Sexta Turma inferida")
ok(P["x7"]["orgao"] == M.SEM_ORGAO and not P["x7"]["inferido"], "sem turma inequívoca: órgão não informado")
ok(P["x8"]["relator"] == M.SEM_RELATOR, "relator vazio")
ok(P["x9"]["relator"] == "Fulano", "título 'Des.' tirado do nome")
ok(P["x13"]["relator"] == "Rogerio Schietti Cruz" and P["x13"]["orgao"] == "Sexta Turma", "alias e turma inferida")
ok(P["x11"]["secao"] == "1ª Seção Criminal" and P["x11"]["camara"] == "", "seção no campo seção")
ok(P["x9"]["ano"] == 2025 and P["x9"]["data"] == "20250909", "ano e data")

# ---- monitor sem desfavoráveis: volume, sem taxa, com aviso ----
r = M.monitor(L, {})
N = r["numeros"]
ok(r["total"] == 14 and N["total"] == 14, "total")
ok(N["favoravel"] == 13 and N["parcial"] == 1 and N["desfavoravel"] == 0, "contagem por sentido: %r" % N)
ok(N["taxa"] is None and not N["tem_desfavoravel"], "sem desfavoráveis: sem taxa")
ok(r["aviso"] == M.AVISO_SO_FAVORAVEIS, "aviso de base só com favoráveis")
ok(N["ano_de"] == 2021 and N["ano_ate"] == 2026 and [a["nome"] for a in r["series"]["ano"]] == [str(a) for a in range(2021, 2027)], "anos contínuos (inclui ano sem decisão)")
ok(N["acordaos"] == 9 and N["monocraticas"] == 5, "acórdãos e monocráticas")
ok(N["relatores"] == 5, "relatores distintos (sem o vazio; alias junta): %r" % N["relatores"])
ok(N["orgao_inferido"] == 2, "órgão inferido em 2")
ok(r["ids"][0] == "x14" and r["ids"][-1] == "x1", "lista das mais recentes às mais antigas")
ok(r["lista"][0][:2] == ["x14", "favoravel"], "lista com sentido")
org = {o["nome"]: o for o in r["series"]["orgao"]}
ok(org.get("Sexta Turma · monocráticas", {}).get("n") == 2, "monocráticas à parte no órgão: %r" % list(org))
ok(org.get("Sexta Turma", {}).get("n") == 4, "acórdãos da Sexta Turma")
ok(r["series"]["orgao"][0]["nivel"] == "camara" and any(o["nivel"] == "secao" for o in r["series"]["orgao"]), "câmaras antes das seções")
rel = {x["nome"]: x for x in r["series"]["relator"]}
ok(rel["Ana Alves"]["n"] == 4 and rel["Rogerio Schietti Cruz"]["n"] == 2 and M.SEM_RELATOR not in rel, "decisões por relator")
ok(rel["Ana Alves"]["tribunal"] == "STJ", "tribunal do relator")

# ---- filtros ----
ok(M.monitor(L, {"tribunal": "TJMS"})["total"] == 3, "filtro tribunal")
ok(M.monitor(L, {"tipo": "Monocrática"})["total"] == 5, "filtro monocrática")
ok(M.monitor(L, {"relator": "Ana Alves"})["total"] == 4, "como vota o relator: só a relatoria dele")
ok(M.monitor(L, {"camara": "Sexta Turma"})["total"] == 6, "como vota a turma (inclui monocráticas com turma inferida)")
ok(M.monitor(L, {"camara": "Sexta Turma", "tipo": "Acórdão"})["total"] == 4, "turma só acórdãos")
ok(M.monitor(L, {"secao": "Terceira Seção"})["total"] == 1, "como vota a seção")
ok(M.monitor(L, {"ano_de": 2025})["total"] == 6 and M.monitor(L, {"ano_de": "2023", "ano_ate": "2023"})["total"] == 3, "período")
ok(M.monitor(L, {"tema": "Falta grave e PAD"})["total"] == 4, "área")
ok(M.monitor(L, {"termo": "x"}, ids_termo={"x1", "x9"})["total"] == 2, "termo (ids da busca)")
ok(M.monitor(L, {"tema": "Prescrição", "tribunal": "TJMS"})["total"] == 0 and M.monitor(L, {"tema": "Prescrição", "tribunal": "TJMS"})["aviso"] == "", "recorte vazio sem aviso")
F = M.monitor(L, {"tribunal": "TJMS", "relator": "Fulano"})["facetas"]
ft = {z["v"]: z["n"] for z in F["tribunal"]}
ok(ft == {"TJMS": 3}, "faceta tribunal conta com os outros filtros e sem ele mesmo: %r" % ft)
fr = {z["v"]: z["n"] for z in F["relator"]}
ok(fr == {"Fulano": 3}, "faceta relator só do tribunal escolhido: %r" % fr)
ok(F["ano"] == [2025], "faceta ano")
fr2 = {z["v"]: z["n"] for z in M.monitor(L, {"relator": "Ana Alves"})["facetas"]["relator"]}
ok(fr2.get("Bruno Borges") == 3, "faceta do relator mostra os demais relatores")

# ---- com desfavoráveis: taxa ----
B = A + [it(20, "TJMS", "Acórdão", "1ª Câmara Criminal", "Fulano", "01/10/2025", ["Remição"], rot=None, res="Desprovido / Improcedente"),
         it(21, "TJMS", "Acórdão", "1ª Câmara Criminal", "Fulano", "02/10/2025", ["Remição"], rot="Ordem denegada"),
         it(22, "TJMS", "Acórdão", "1ª Câmara Criminal", "Fulano", "03/10/2025", ["Remição"], rot=None, res="Não conhecido")]
r = M.monitor(M.preparar(B), {"relator": "Fulano"})
N = r["numeros"]
ok(N["favoravel"] == 2 and N["parcial"] == 1 and N["desfavoravel"] == 2 and N["nao_conhecido"] == 1, "contagem com desfavoráveis: %r" % N)
ok(N["taxa"] == 60.0 and N["taxa_integral"] == 40.0, "taxa (fav+parc)/(mérito) = 3/5 e integral 2/5: %r %r" % (N["taxa"], N["taxa_integral"]))
ok(r["aviso"] == "", "com desfavoráveis: sem aviso")
ok(r["series"]["relator"][0]["taxa"] == 60.0, "taxa por relator")
ok(M.monitor(M.preparar(B), {"tribunal": "STJ"})["numeros"]["taxa"] is None, "taxa só quando há desfavoráveis no recorte")
ok(M.descrever({"tema": "Remição", "tribunal": "TJMS", "relator": "Fulano", "ano_de": 2024}) == "Área: Remição · TJMS · Relator: Fulano · 2024 a hoje", "descrição do recorte")

# ---- relatório em PDF ----
try:
    import reportlab  # noqa
    tmp = tempfile.mkdtemp()
    c = os.path.join(tmp, "m.pdf")
    M.relatorio_pdf(r, {"relator": "Fulano"}, {x["id"]: x for x in B}, c, "teste")
    ok(os.path.getsize(c) > 3000, "PDF gerado")
    c2 = os.path.join(tmp, "m2.pdf")
    M.relatorio_pdf(M.monitor(L, {}), {}, {x["id"]: x for x in A}, c2, "teste")
    ok(os.path.getsize(c2) > 3000, "PDF sem desfavoráveis")
except ImportError:
    pass

# ---- base do Monitor nos dois sentidos (monitor_juris.bin, 7.16.1) ----
import json, struct, zlib
from collections import Counter
AQUI = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(AQUI, "monitor_juris.bin")
ok(os.path.isfile(BIN), "monitor_juris.bin presente no repositório (embutido no .exe)")
JB = {"cab": {}, "itens": []}
if os.path.isfile(BIN):
    b_ = open(BIN, "rb").read()
    ok(b_[:8] == b"APTOMON1", "cabeçalho APTOMON1")
    ok(len(b_) < 25 * 1024 * 1024, "arquivo compacto (< 25 MB): %d bytes" % len(b_))
    n_ = struct.unpack("<I", b_[8:12])[0]
    JB = json.loads(zlib.decompress(b_[12:12 + n_]).decode("utf-8"))
IT = JB["itens"]
ok(len(IT) > 50000, "base com dezenas de milhares de decisões: %d" % len(IT))
ok(len({x["id"] for x in IT}) == len(IT), "ids únicos")
ok(all(x.get("sentido") in M.SENTIDOS for x in IT), "toda decisão traz o sentido (favorável, parcial, desfavorável, não conhecido)")
ok(all(len(x.get("tese") or "") <= 301 and x.get("tese") for x in IT), "tese/ementa curta (até ~300 caracteres) em todas")
ok(all(set(("id", "tribunal", "tipo", "orgao", "relator", "julg", "pub", "ano", "classe", "proc", "temas", "sentido", "resultado", "rot", "link", "tese")) <= set(x) for x in IT),
   "campos de cada decisão")
ok(not any("ementa" in x or "texto" in x for x in IT), "sem texto integral nem ementa longa")
cs = Counter((x["tribunal"], x["sentido"]) for x in IT)
for t_ in ("TJMS", "STJ", "STF"):
    ok(cs[(t_, "desfavoravel")] > 100 and cs[(t_, "favoravel")] > 100, "%s com favoráveis e desfavoráveis: %r" % (t_, {k[1]: v for k, v in cs.items() if k[0] == t_}))
temas_aba = {"Progressão de regime", "Remição", "Falta grave e PAD", "Hediondos e frações", "Exame criminológico", "Indulto e comutação", "Prisão domiciliar",
             "Livramento condicional", "Saúde e condições prisionais", "Competência e processamento", "Unificação e soma de penas", "Monitoração eletrônica",
             "Regressão de regime", "Detração", "Extinção da pena", "Regime aberto e condições", "Penas restritivas de direitos", "Data-base", "Prescrição",
             "Pena de multa", "Medida de segurança", "Saída temporária", "Trabalho externo", "Execução provisória", "Outros"}
ok({t for x in IT for t in x["temas"]} <= temas_aba, "temas com o mesmo vocabulário da aba")
ok({x["orgao"] for x in IT if x["tribunal"] == "TJMS"} >= {"1ª Câmara Criminal", "2ª Câmara Criminal", "3ª Câmara Criminal", "1ª Seção Criminal"}, "órgãos do TJMS normalizados")
ok({x["orgao"] for x in IT if x["tribunal"] == "STJ"} >= {"Quinta Turma", "Sexta Turma", "Terceira Seção"}, "turmas e seção do STJ")
ok(not any(x["relator"].startswith(("Des", "Min.")) or "(" in x["relator"] for x in IT), "relator sem título nem '(desembargador convocado ...)'")
ok("Rogerio Schietti" not in {x["relator"] for x in IT} and "Marluce Caldas" not in {x["relator"] for x in IT}, "grafias do mesmo ministro unificadas")
ok(all(x["link"] for x in IT if x["tribunal"] == "TJMS"), "TJMS: link do inteiro teor (e-SAJ) em todas")
ok(all(not x["julg"] or (len(x["julg"]) == 10 and x["julg"][2] == "/") for x in IT), "data dd/mm/aaaa")
ok("precisao" in JB["cab"] and "por_tribunal" in JB["cab"], "cabeçalho com a precisão medida e os números por tribunal")

# ---- Api com a base real ----
import rspe_app as app
app.CONFIG = os.path.join(tempfile.mkdtemp(), "c.json")
api = app.Api()
R = api.teses_monitor({})
ok(not R.get("erro"), "Api.teses_monitor: %r" % R.get("erro"))
d = api.teses()
ok(R["base"] == "juris" and R["total"] == len(IT), "Monitor usa monitor_juris.bin (%s x %s)" % (R.get("total"), len(IT)))
ok(R["numeros"]["desfavoravel"] > 0 and R["aviso"] == "" and R["numeros"]["taxa"] is not None, "com desfavoráveis: taxa e sem o aviso de 'só favoráveis'")
# a Pesquisa não muda: continua só com as favoráveis curadas
ok(not any(M.sentido(x) == "desfavoravel" for x in d["itens"]), "Pesquisa continua só com favoráveis")
ok(len(d["itens"]) < len(IT), "Pesquisa e Monitor com bases distintas")
# recorte conhecido: como vota um relator do TJMS (taxa conferida com a contagem direta da base)
rel_ = Counter(x["relator"] for x in IT if x["tribunal"] == "TJMS" and x["relator"]).most_common(1)[0][0]
mine = [x for x in IT if x["tribunal"] == "TJMS" and x["relator"] == rel_]
c_ = Counter(x["sentido"] for x in mine)
tx = round(100.0 * (c_["favoravel"] + c_["parcial"]) / (c_["favoravel"] + c_["parcial"] + c_["desfavoravel"]), 1)
R3 = api.teses_monitor({"tribunal": "TJMS", "relator": rel_})
ok(R3["total"] == len(mine) and R3["numeros"]["desfavoravel"] == c_["desfavoravel"], "como vota %s: %s decisões" % (rel_, R3["total"]))
ok(R3["numeros"]["taxa"] == tx and 0 < tx < 100, "taxa de acolhimento de %s = %s%% (base: %s%%)" % (rel_, R3["numeros"]["taxa"], tx))
ok(R3["series"]["orgao"] and all(o["taxa"] is not None for o in R3["series"]["orgao"] if o["desfavoravel"]), "taxa por câmara no recorte do relator")
R4 = api.teses_monitor({"camara": "1ª Câmara Criminal"})
ok(R4["total"] > 500 and R4["numeros"]["taxa"] is not None and all(z["tribunal"] == "TJMS" for z in R4["facetas"]["relator"]), "como vota a 1ª Câmara Criminal")
R5 = api.teses_monitor({"tema": "Remição", "tribunal": "STJ", "tipo": "Acórdão", "ano_de": 2023, "ano_ate": 2025})
ok(R5["total"] > 0 and R5["numeros"]["ano_de"] >= 2023 and R5["numeros"]["ano_ate"] <= 2025, "filtro de área, tribunal, tipo e período")
ok(R5["numeros"]["monocraticas"] == 0, "só acórdãos")
R6 = api.teses_monitor({"secao": "Terceira Seção"})
ok(R6["total"] > 20 and R6["numeros"]["taxa"] is not None, "como vota a Terceira Seção do STJ")
R2 = api.teses_monitor({"tema": "Remição", "tribunal": "TJMS"})
ok(0 < R2["total"] < R["total"] and all(z["tribunal"] == "TJMS" for z in R2["facetas"]["relator"]), "recorte por área e tribunal")
ok(R2["recorte"] == "Área: Remição · TJMS", "recorte descrito")
ok(R2["itens"] and all(k in R2["itens"] for k, *_ in R2["lista"][:50]), "itens das primeiras linhas vêm com o recorte")
desf = [k for k, s_, *_ in R2["lista"] if s_ == "desfavoravel"]
ok(desf and api.teses_monitor_itens(desf[:5])[desf[0]]["sentido"] == "desfavoravel", "desfavoráveis na lista, com o sentido")
mais = api.teses_monitor_itens([k for k, *_ in R2["lista"][150:200]])
ok(len(mais) == len(R2["lista"][150:200]) and all(v.get("link") for v in mais.values()), "Mostrar mais: itens sob demanda, com o link do inteiro teor")
info = api.teses_monitor_info()
ok(info["base"] == "juris" and info["total"] == len(IT) and info["temas"][0]["n"] > 1000 and info["sentidos"]["desfavoravel"] > 1000, "pergunta inicial com os números da base")
stj = api._monitor_base()["linhas"]
ok(sum(1 for x in stj if x["inferido"]) > 1000, "turma inferida em boa parte do STJ (monocráticas)")
R7 = api.teses_monitor({"termo": "encceja"})
ok(R7["total"] > 50 and R7["numeros"]["desfavoravel"] > 0, "termo (ENCCEJA) também nas desfavoráveis")
# recorte sem desfavoráveis na base nova: aviso do recorte (não da base)
L2 = M.preparar([dict(x, sentido="favoravel") for x in A[:3]])
ok(M.monitor(L2, {}, dois_sentidos=True)["aviso"] == M.AVISO_SEM_DESF_RECORTE, "aviso de recorte sem desfavoráveis")
# relatório com a base nova
try:
    import reportlab  # noqa
    c3 = os.path.join(tempfile.mkdtemp(), "m3.pdf")
    M.relatorio_pdf(R3, {"tribunal": "TJMS", "relator": rel_}, api._monitor_base()["por_id"], c3, "teste", rodape=M.RODAPE_JURIS, fonte="Base do Monitor")
    ok(os.path.getsize(c3) > 5000, "PDF do relator com taxa")
except ImportError:
    pass
# sem o arquivo: volta à base da Pesquisa (só favoráveis, com o aviso)
app.Api._juris, app.Api._mon = {}, None
Rf = api.teses_monitor({})
ok(Rf["base"] == "pesquisa" and Rf["total"] == len(d["itens"]) and Rf["numeros"]["desfavoravel"] == 0 and Rf["aviso"] == M.AVISO_SO_FAVORAVEIS,
   "sem monitor_juris.bin: base da Pesquisa, com aviso")
app.Api._juris, app.Api._mon = None, None

h = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui.html"), encoding="utf-8").read()
for t in ("O que você quer acompanhar?", "API().teses_monitor(", "API().teses_monitor_pdf(", "tesVer('monitor')", "Como vota o relator",
          "Como vota a câmara / turma", "Como vota a seção", "monBarras", "Copiar referência", "tesFavoritar", "API().teses_monitor_itens(",
          "API().teses_monitor_info(", "mon-desf", "Base do Monitor", "x.link"):
    ok(t in h, "ui.html: " + t)
if falhas:
    print("FALHOU (monitor de jurisprudência): " + "; ".join(falhas)); sys.exit(1)
print("ok: monitor de jurisprudência (sentido, turma pelo relator, números, taxa só com desfavoráveis, filtros, facetas, PDF)")
