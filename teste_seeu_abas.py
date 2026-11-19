"""Leitura das ABAS do SEEU (painel da extensão, sem o APTO): para cada um dos 144 casos simulados, as páginas do SEEU
fictício (ferramentas/seeu_ficticio, no visual das capturas oficiais) passam pelo leitor das abas (rspe_seeu_abas) e o
registro tem de trazer EXATAMENTE o conteúdo do RSPE (rspe_motor._conteudo_rspe: cabeçalho, cálculo, crimes, eventos e
incidentes) e dar o mesmo painel que o RSPE daria. Também: o leitor só lê a aba (a capa se repete em toda página), o que
falta vira ponto a conferir e página sem processo não inventa nada.
Limite conhecido: a marcação HTML do SEEU fictício é suposição (as capturas não mostram o código); conferir com o HTML real.
Rodar: python teste_seeu_abas.py"""
import copy
import json
import os
import sys
import types
from datetime import date

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "ferramentas", "seeu_ficticio"))
sys.modules.setdefault("webview", types.ModuleType("webview"))
import seeu  # noqa: E402
import rspe_motor as mt  # noqa: E402
import rspe_painel as rp  # noqa: E402
import rspe_scraper as rs  # noqa: E402
import rspe_seeu_abas as ra  # noqa: E402

HOJE = date(2026, 10, 12)
falhas = []


def ok(c, m):
    if not c:
        falhas.append(m)


casos = json.load(open(os.path.join(AQUI, "casos_simulados", "casos.json"), encoding="utf-8"))
igual = mesmo_painel = 0
for c in casos:
    r = copy.deepcopy(c["rspe"])
    for x in r["_crimes"]:
        if not x.get("artigo_rspe"):
            x["artigo_rspe"] = x.get("artigo")  # artefato do gerador dos casos: o RSPE sempre traz o artigo
    r2, faltou = ra.ler(seeu.abas_dict(c["rspe"]), c["rspe"].get("data_geracao_rspe"))
    if json.loads(mt._conteudo_rspe(r)) == json.loads(mt._conteudo_rspe(r2)):
        igual += 1
    else:
        falhas.append("%s: conteúdo lido das abas diferente do RSPE" % c["id"])
    ok(not faltou, "%s: faltou %s" % (c["id"], faltou))
    p1 = rp.analisar(rs.reprocessar(copy.deepcopy(c["rspe"])), hoje=HOJE)
    p2 = rp.analisar(r2, hoje=HOJE)
    # o aviso "reimportar o RSPE lido por versão anterior" é do arquivo antigo, não da leitura nova das abas
    sem_reimp = lambda p: [[{k: v for k, v in i.items() if k != "id"} for i in s["itens"] if "Reimportar" not in i["titulo"]] for s in p["secoes"]]
    if sem_reimp(p1) == sem_reimp(p2) and p1["pena"] == p2["pena"] and p1["nao_cabe"] == p2["nao_cabe"]:
        mesmo_painel += 1
    else:
        falhas.append("%s: painel pelas abas diferente do painel pelo RSPE" % c["id"])
ok(igual == len(casos), "conteúdo igual ao RSPE em %d de %d" % (igual, len(casos)))
ok(mesmo_painel == len(casos), "mesmo painel em %d de %d" % (mesmo_painel, len(casos)))

# a capa se repete em toda página: o leitor lê o corpo da aba (o nome do sentenciado vem da aba Partes, não da capa)
r = dict(casos[0]["rspe"], nome="NOME NA ABA PARTES")
ab = seeu.abas_dict(r)
ab["capa"] = ab["capa"].replace("NOME NA ABA PARTES", "NOME SÓ NA CAPA")
r2, _ = ra.ler(ab, "12/10/2026")
ok(r2["nome"] == "NOME NA ABA PARTES", "nome da aba Partes (veio %r)" % r2["nome"])

# aba que não veio: o que faltou é dito e vira ponto a conferir no painel (nunca dado inventado)
ab = seeu.abas_dict(casos[0]["rspe"])
del ab["eventos"]
p = json.loads(rp.analisar_abas(json.dumps({"abas": ab, "hoje": "12/10/2026"}, ensure_ascii=False)))
fal = [i for s in p["secoes"] for i in s["itens"] if i["id"] == "faltou"]
ok(fal and fal[0]["status"] == "amarelo" and "eventos" in fal[0]["motivo"].lower(), "aba Eventos ausente: ponto a conferir (%r)" % fal)

# página sem processo (sessão expirada, página de erro): sem dados, sem painel
p = json.loads(rp.analisar_abas(json.dumps({"abas": {"capa": "<html><body>Sessão expirada</body></html>"}, "hoje": "12/10/2026"})))
ok(p.get("erro") == "sem_dados", "página sem processo: sem_dados (%r)" % p.get("erro"))

if falhas:
    print("FALHOU:\n  " + "\n  ".join(falhas[:20]))
    sys.exit(1)
print("ok: leitura das abas do SEEU (%d casos com o mesmo conteúdo do RSPE e o mesmo painel; só a aba; o que falta vira conferir)" % len(casos))
