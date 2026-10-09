"""Teste de regressão da aba Dados prisionais (Geopresídios/CNJ), sem internet: leitura do relatório de inspeção (capacidade,
população por regime, perfil, servidores), seleção das unidades penais, posição no mapa (coordenada da cidade ou município
citado no nome) e assistidos da base por unidade. Rodar: python teste_geopresidios.py"""
import sys
import types

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_geopresidios as rgeo
import rspe_mapa_ms as rmapa
import rspe_app as app

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


R = lambda q, v, perg=None: {"numero_questao": q, "resposta": v, "pergunta": perg}
rel = {"respostas": [R("100034", 1181), R("100034", 999), R("100902", 0), R("100903", 2), R("100904", 1613), R("100905", 0),
                     R("100911", 1613), R("100917", 45), R("100001", "Colônia agrícola, industrial ou similar"),
                     R("100002", "Cumprimento de pena em regime semiaberto"), R("100093", 40, "Total de homens"),
                     R("100093", 25, "Total de mulheres"), R("100094", 28, "Total de RH na área de segurança")]}
u = rgeo._extrair(rel)
ok(u["capacidade"] == 1181 and u["semiaberto"] == 1613 and u["fechado"] == 2 and u["idosos"] == 45, "extrair números: %s" % u)
ok(u["servidores"] == 65 and u["servidores_seguranca"] == 28, "servidores: %s" % u)
ok(u["classificacao"].startswith("Colônia") and "semiaberto" in u["destinacao"], "textos: %s" % u)
# população de qualquer tema (o número da questão leva o tema na frente) e indicadores dos demais temas
p = rgeo._populacao({"respostas": [R("400902", 10), R("400903", 100), R("400904", 5), R("400905", 0), R("400906", 2)]}, 4)
ok(p == {"provisorios": 10, "fechado": 100, "semiaberto": 5, "aberto": 0, "pop": 117}, "população do tema 4: %s" % p)
ok(rgeo._populacao({"respostas": [R("100903", 9)]}, 4) is None, "população de outro tema não entra")
ind = rgeo._indicadores({"respostas": [R("200028", "Não"), R("200006", "Não"), R("200014", "Não há regularidade no fornecimento"),
                                       R("200004", "Regular")]}, 2)
ok(ind["refeicoes"]["ruim"] and not ind["agua_racion"]["ruim"] and ind["vestuario"]["ruim"] and not ind["sanitarios"]["ruim"], "habitabilidade: %s" % ind)
ind = rgeo._indicadores({"respostas": [R("300064", "Não"), R("300043", 2), R("300087", 552, "Com cômputo para remição da pena"),
                                       R("300087", 9, "Sem cômputo"), R("300072", 115, "Alfabetização"), R("300072", 200, "Fundamental"),
                                       R("300044", "Não há atendimento periódico presencial")]}, 3)
ok(ind["rem_leitura"]["ruim"] and ind["defensores"]["n"] == 2 and ind["trab_remicao"]["n"] == 552 and ind["escola"]["n"] == 315
   and ind["defensoria"]["ruim"], "assistências: %s" % ind)
ind = rgeo._indicadores({"respostas": [R("400005.3", "Sim*"), R("400010", "NA")]}, 4)
ok(ind["forcas_especiais"] == {"v": "Sim", "ruim": True} and "procedimento" not in ind, "segurança (asterisco e NA): %s" % ind)
ok(not rgeo._indicadores({"respostas": [R("200028", "Não informado")]}, 2)["refeicoes"]["ruim"], "\"Não informado\" não é problema")
ok(rgeo.ordem_ciclo("Julho/2026") == (2026, 7) and rgeo.ordem_ciclo("Março/26") == (2026, 3) and rgeo.ordem_ciclo("?") == (0, 0), "ciclos")
ok(all(ch in rgeo.PROBLEMA for ch, t, q, rot, ruim in rgeo.INDICADORES if ruim), "toda constatação tem a frase do problema")
# tipo do estabelecimento
ok([rgeo.categoria(n) for n in ("PRESIDIO MILITAR ESTADUAL", "INSTITUTO PENAL DE CAMPO GRANDE", "1ª DELEGACIA DE POLÍCIA DE CORUMBÁ",
                                "GRUPO DOS FUZILEIROS NAVAIS DE LADÁRIO", "SUPERINTENDÊNCIA REGIONAL DA POLÍCIA FEDERAL", "PENITENCIÁRIA FEDERAL EM CAMPO GRANDE")]
   == ["militar", "penal", "delegacia", "militar", "outra", "penal"], "categorias")
# unidades penais x delegacias e militares
ok(rgeo.RE_PENAL.search(rgeo._sem_acento("PENITENCIÁRIA DE DOIS IRMÃOS DO BURITI")), "penitenciária")
ok(rgeo.RE_PENAL.search(rgeo._sem_acento("CENTRO DE DETENÇÃO PROVISÓRIA DE IGUATEMI")), "CDP")
ok(not rgeo.RE_PENAL.search(rgeo._sem_acento("1ª DELEGACIA DE POLÍCIA DE CORUMBÁ")), "delegacia fora")
ok(not rgeo.RE_PENAL.search(rgeo._sem_acento("9º BATALHÃO DE POLÍCIA DO EXÉRCITO")), "militar fora")
# mapa: 79 municípios; ponto de Campo Grande dentro do quadro
ok(len(rmapa.MAPA["municipios"]) == 79, "79 municípios")
x, y = rmapa.ponto(-20.4662, -54.6069)
ok(0 < x < rmapa.MAPA["proj"]["W"] and 0 < y < rmapa.MAPA["proj"]["H"], "Campo Grande no quadro: %s" % ((x, y),))
U = [{"nome": "PENITENCIARIA ESTADUAL DE DOURADOS", "ibge": "5003702", "lat": -22.22, "lon": -54.80},
     {"nome": "CENTRO DE DETENÇÃO PROVISÓRIA DE SIDROLÂNDIA", "ibge": "", "endereco": ""},
     {"nome": "ESTABELECIMENTO PENAL FEMININO LUIZ PEREIRA DA SILVA", "ibge": "", "endereco": "RUA OLIMPIO JORGE LEITE, 423 JATEI"}]
app.Api._geo_pontos(U)
ok(U[0]["cidade"] == "Dourados" and U[0].get("x"), "Dourados pela coordenada: %s" % U[0])
ok(U[1]["cidade"] == "Sidrolândia" and U[1].get("x"), "Sidrolândia pelo nome: %s" % U[1])
ok(U[2]["cidade"] == "Jateí" and U[2].get("x"), "Jateí pelo endereço: %s" % U[2])
# assistidos da base: ficha da PDIB (grafia do SIAPEN) e regime do RSPE
a = app.Api()
a._modelos = [{"ficha": {"unidade": "PENITENCIÁRIA DE DOIS IRMÃO DO BURITI"}, "regime_rspe": "Semiaberto"},
              {"ficha": {"unidade": "PENITENCIÁRIA DE DOIS IRMÃO DO BURITI"}, "regime_rspe": "Fechado"},
              {"ficha": {"unidade": "UNIDADE MISTA DE MONITORAMENTO VIRTUAL ESTADUAL DE CAMPO GRANDE"}, "regime_rspe": "Aberto"}]
V = [{"nome": "PENITENCIÁRIA DE DOIS IRMÃOS DO BURITI", "inspecao": {"id": 1}, "capacidade": 209, "fechado": 527},
     {"nome": "PENITENCIARIA ESTADUAL DE DOURADOS", "inspecao": {"id": 1}, "capacidade": 209, "fechado": 527}]
a._geo_assistidos(V)
ok(V[0]["assistidos"] == 2 and V[0]["assistidos_semi"] == 1, "assistidos na PDIB: %s" % V[0])
ok(V[1]["assistidos"] == 0, "Dourados sem assistidos: %s" % V[1])
ok(V[0]["igual_a"] == [V[1]["nome"]], "números idênticos de outra unidade: %s" % V[0].get("igual_a"))

# relatório em PDF com dados sintéticos (mapa, ranking, condições e evolução)
import os, tempfile
import rspe_relatorio as rrel
D = {"atualizado": "09/10/2026 10:00", "unidades": []}
for n, (cid, cap, s0, s1) in enumerate([("Campo Grande", 100, 150, 180), ("Dourados", 200, 190, 210)]):
    D["unidades"].append({"id": n, "nome": "PENITENCIARIA TESTE %d" % n, "penal": True, "cidade": cid, "x": 400 + 50 * n, "y": 500, "capacidade": cap,
                          "pop": s1, "fechado": s1, "provisorios": 0, "semiaberto": 0, "aberto": 0, "pop_ciclo": "Setembro/2026",
                          "inspecao": {"data": "2026-06-30", "ciclo": "Junho/2026"},
                          "temas": {"2": {"ciclo": "Julho/2026", "ind": {"refeicoes": {"v": "Não", "ruim": True}}}},
                          "serie": [{"ciclo": "Junho/2026", "data": "2026-06-30", "pop": s0}, {"ciclo": "Setembro/2026", "data": "2026-09-29", "pop": s1}]})
arq = os.path.join(tempfile.mkdtemp(), "dp.pdf")
rrel.relatorio_prisional(D, rmapa.MAPA, arq, "teste")
txt = open(arq, "rb").read()
ok(txt.startswith(b"%PDF") and len(txt) > 5000, "PDF dos dados prisionais")

# relatório da unidade (com os assistidos da base) e relatório de condições por unidade
lista = a._geo_lista({"nome": "PENITENCIÁRIA DE DOIS IRMÃOS DO BURITI"})
ok(len(lista) == 2 and {x["regime"] for x in lista} == {"Semiaberto", "Fechado"}, "assistidos na unidade: %s" % lista)
U0 = dict(D["unidades"][0], destinacao="Cumprimento de pena em regime fechado", cat="penal")
arq2 = os.path.join(tempfile.mkdtemp(), "un.pdf")
rrel.relatorio_unidade_prisional(U0, "09/10/2026", [{"nome": "Fulano", "proc": "1", "regime": "Semiaberto"}], arq2, "teste")
ok(open(arq2, "rb").read(4) == b"%PDF", "PDF da unidade")
arq3 = os.path.join(tempfile.mkdtemp(), "cond.pdf")
rrel.relatorio_condicoes_prisional(D, arq3, "teste", "", ["penal"])
ok(open(arq3, "rb").read(4) == b"%PDF", "PDF das condições por unidade")
ok(len(rrel._geo_sel(dict(D, unidades=D["unidades"] + [{"nome": "1ª DELEGACIA", "cat": "delegacia"}]), "", ["penal"])) == 2, "filtro por tipo")

if falhas:
    print("FALHOU (Geopresídios):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: Geopresídios (relatório, unidades penais, mapa, cidades, assistidos da base, números idênticos)")
