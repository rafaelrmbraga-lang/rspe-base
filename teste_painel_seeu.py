"""Painel do APTO no SEEU (7.32 / extensão 1.15, painel v2): a análise do painel (rspe_painel) usa o cálculo do APTO sem
conta nova e aplica as regras de 11/2026 - só VERDE (confere, há certeza) e AMARELO (conferir), sem "agir já"; ordem da ficha
do assistido (marcos, benefícios, demais pontos); o que depende da ficha sai amarelo sem ela (nunca verde); custodiado sem
remição decidida há mais de 6 meses: conferir o atestado. A mesma entrada dá a mesma chave e a mesma assinatura (base da
paridade navegador x APTO). Também roda o teste da tela do painel (node). Rodar: python teste_painel_seeu.py"""
import copy
import json
import os
import shutil
import subprocess
import sys
import types
from datetime import date

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "ferramentas", "seeu_ficticio"))
sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_painel as rp  # noqa: E402
import rspe_seeu_abas as ra  # noqa: E402
import seeu  # noqa: E402

HOJE = date(2026, 10, 12)
falhas = []


def ok(c, m):
    if not c:
        falhas.append(m)


casos = {c["id"]: c for c in json.load(open(os.path.join(AQUI, "casos_simulados", "casos.json"), encoding="utf-8"))}


def itens(p):
    """Todos os pontos do painel: os alertas (para conferir) e o que confere; os marcos entram como pontos pelo id."""
    return p["alertas"] + p["confere"] + [{"id": m["id"], "status": "amarelo" if m["alerta"] else "verde", "status_txt": "Conferir" if m["alerta"] else "Confere",
                                           "conferir": "", "motivo": m["quando"]} for m in p["marcos"]]


# 1) indulto possível sem ficha: amarelo (falta grave na ficha), nunca verde
p = rp.analisar(casos["S001"]["rspe"], hoje=HOJE)
i25 = next((x for x in itens(p) if x["id"] == "i25"), None)
ok(i25 and i25["status"] == "amarelo" and "falta grave" in i25["conferir"] and "ficha" in i25["conferir"], "S001 sem ficha: indulto 2025 a conferir (%r)" % (i25,))
ok(not any(x["status"] == "verde" and x["id"][:1] in "ic" and x["id"][1:].isdigit() for x in itens(p)), "sem ficha: nenhum indulto/comutação verde")
ok(p["ficha"] is False, "sem ficha: marcado")

# 2) mesma entrada = mesma chave e mesma assinatura; a entrada não é alterada pelo cálculo
r = copy.deepcopy(casos["S141"]["rspe"])
r0 = json.dumps(r, sort_keys=True)
a, b = rp.analisar(r, hoje=HOJE), rp.analisar(r, hoje=HOJE)
ok(a["assinatura"] == b["assinatura"] and a["chave"] == b["chave"], "mesma entrada, mesmo resultado")
ok(json.dumps(r, sort_keys=True) == r0, "o cálculo não altera a entrada")
ok(rp.analisar(r, hoje=date(2026, 10, 13))["chave"] != a["chave"], "outra data de referência, outra chave")

# 3) atestado: custodiado sem remição decidida há mais de 6 meses -> amarelo; com remição recente, não
r = copy.deepcopy(casos["S001"]["rspe"])
r["_incidentes"] = [i for i in r.get("_incidentes") or [] if "REMI" not in (i.get("tipo") or "").upper()]
at = next((x for x in itens(rp.analisar(r, hoje=HOJE)) if x["id"] == "atestado"), None)
ok(at and at in rp.analisar(r, hoje=HOJE)["alertas"] and at["status"] == "amarelo" and "atestado" in at["conferir"], "sem remição há mais de 6 meses: pedir atestado (%r)" % (at,))
r["_incidentes"].append({"tipo": "REMIÇÃO", "complemento": "10 Dia(s) Remido(s)", "data_decisao": "01/09/2026", "data_referencia": "01/09/2026", "situacao": "CONCEDIDO"})
ok(not any(x["id"] == "atestado" for x in itens(rp.analisar(r, hoje=HOJE))), "remição decidida há 1 mês: sem alerta de atestado")

# 4) hierarquia: marcos em linhas (data e quanto falta), alertas = tudo que é amarelo, confere = o verde dos benefícios
for cid in ("S001", "S006", "S035", "S093", "S141"):
    p = rp.analisar(casos[cid]["rspe"], hoje=HOJE)
    ok(all(a["status"] == "amarelo" for a in p["alertas"]) and all(c["status"] == "verde" for c in p["confere"]), "%s: alertas só amarelos, confere só verde" % cid)
    ok(all(x["status_txt"] == "Conferir" for x in p["alertas"]), "%s: texto da situação" % cid)
    ok(p["contagem"]["amarelo"] == len(p["alertas"]), "%s: contagem dos alertas" % cid)
    ok([m["id"] for m in p["marcos"]][:1] == ["db"] and all(m["data"] for m in p["marcos"]), "%s: marcos começam pela data-base, todos com data" % cid)
    ok(all(m["destaque"] in ("", "proximo", "atingida") for m in p["marcos"]), "%s: destaque dos marcos" % cid)
    ok(p["pena"]["total"] and "agir" not in json.dumps(p, ensure_ascii=False).lower(), "%s: pena no topo, sem 'agir já'" % cid)
# marco próximo: destaque, sem virar alerta só por estar perto
p = rp.analisar(casos["S037"]["rspe"], hoje=date(2026, 10, 18))
prog = next(m for m in p["marcos"] if m["id"] == "prog")
ok(prog["destaque"] == "proximo" and not prog["alerta"] and not any(a["id"] == "prog" for a in p["alertas"]), "progressão a 19 dias: próximo, sem alerta (%r)" % prog)
# marco com dúvida no cálculo (percentual do SEEU acima do legal): sinal na linha E alerta
p = rp.analisar(casos["S006"]["rspe"], hoje=HOJE)
ok(any(m["id"] == "prog" and m["alerta"] for m in p["marcos"]) and any(a["id"] == "prog" for a in p["alertas"]), "progressão com dúvida: alerta")

# 5) progressão já atingida com data certa: verde, dita como fato (sem urgência)
prog = next((m for m in rp.analisar(casos["S035"]["rspe"], hoje=HOJE)["marcos"] if m["id"] == "prog"), None)
ok(prog and not prog["alerta"] and prog["destaque"] == "atingida" and "atingida" in prog["quando"], "progressão atingida, data certa: destaque, sem alerta (%r)" % (prog,))

# 6) pelas abas do SEEU (a entrada da extensão, em texto): mesmo resultado que ler + analisar
ab = seeu.abas_dict(casos["S093"]["rspe"])
p1 = json.loads(rp.analisar_abas(json.dumps({"abas": ab, "hoje": "12/10/2026"}, ensure_ascii=False)))
p2 = rp.analisar(ra.ler(ab, "12/10/2026")[0], hoje=HOJE)
ok(p1["assinatura"] == p2["assinatura"], "analisar_abas = ler + analisar")

# 7) a tela do painel (node), se houver node neste computador
if shutil.which("node"):
    ok(subprocess.call(["node", os.path.join(AQUI, "extensao_seeu_testes", "teste_painel_core.js")]) == 0, "teste da tela do painel (node)")
    ok(subprocess.call(["node", os.path.join(AQUI, "extensao_seeu_testes", "teste_painel_resumo.js")]) == 0, "teste do resumo para o assistido (node)")

# 8) resumo para o assistido: parte da última análise; o canhoto só quando a pessoa diz que o atendimento é na unidade
rp.analisar_abas(json.dumps({"abas": seeu.abas_dict(casos["S035"]["rspe"]), "hoje": "12/10/2026"}, ensure_ascii=False))
d = json.loads(rp.resumo_assistido(json.dumps({"processo": casos["S035"]["processo"]})))
ok(d.get("nome") and any(s_["id"] == "direitos" for s_ in d["secoes"]) and d.get("providencias"), "resumo montado a partir da análise")
ok(json.loads(rp.resumo_assistido(json.dumps({"processo": "0000000-00.0000.0.00.0000"}))).get("erro") == "sem_analise", "sem análise: pedir de novo")
try:
    import tempfile
    import pdfplumber
    for canhoto in (True, False):
        cam = os.path.join(tempfile.mkdtemp(), "r.pdf")
        x = json.loads(rp.resumo_pdf(json.dumps({"d": d, "canhoto": canhoto}, ensure_ascii=False), cam))
        with pdfplumber.open(cam) as pdf:
            t = "\n".join(pg.extract_text() or "" for pg in pdf.pages)
        ok(("Pedido de atendimento" in t) == canhoto and x["canhoto"] == canhoto, "resumo %s canhoto" % ("com" if canhoto else "sem"))
except ImportError:
    pass

if falhas:
    print("FALHOU:\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: painel do APTO no SEEU v2 (verde/amarelo, ordem da ficha, conferir sem ficha, atestado, mesma entrada = mesmo resultado)")
