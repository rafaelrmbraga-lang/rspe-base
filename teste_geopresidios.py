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

if falhas:
    print("FALHOU (Geopresídios):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: Geopresídios (relatório, unidades penais, mapa, cidades, assistidos da base, números idênticos)")
