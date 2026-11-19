"""Páginas do SEEU fictício (ferramentas/seeu_ficticio) dos casos pedidos, por endereço, o RSPE de cada um em PDF (o que o SEEU
devolve ao link do relatório) e o painel esperado (calculado como o APTO lê o RSPE: pdfplumber -> leitor do RSPE -> motor), para o teste de ponta a ponta da extensão (teste_painel_e2e.js).
Uso: python extensao_seeu_testes/paginas_painel.py S035,S141 saida.json [dd/mm/aaaa]"""
import json
import os
import sys
import types

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "ferramentas", "seeu_ficticio"))
sys.modules.setdefault("webview", types.ModuleType("webview"))
import seeu  # noqa: E402
import rspe_motor  # noqa: E402
import rspe_painel as rp  # noqa: E402
import rspe_view as rv  # noqa: E402
import rspe_seeu_abas as ra  # noqa: E402
import rspe_pdf  # noqa: E402
import hashlib  # noqa: E402
import pdfplumber  # noqa: E402

import tempfile  # noqa: E402
import ficha_pdf as fp  # noqa: E402
import rspe_ficha as rf  # noqa: E402

ids, saida = sys.argv[1].split(","), sys.argv[2]
hoje = sys.argv[3] if len(sys.argv) > 3 else None
with open(os.path.join(RAIZ, "extensao_seeu", "motor", "motor.json"), encoding="utf-8") as f:
    rspe_motor.VERSAO = json.load(f)["versao"]
casos = {c["id"]: c for c in json.load(open(os.path.join(RAIZ, "casos_simulados", "casos.json"), encoding="utf-8"))}
out = {}
for i in ids:
    r = dict(casos[i]["rspe"], nome="FULANO DE TAL EXEMPLO %s" % i[1:], nome_mae="MARIA EXEMPLO DA SILVA")
    from datetime import date
    h = hoje or date.today().strftime("%d/%m/%Y")
    rspe = rspe_pdf.gerar(os.path.join(tempfile.mkdtemp(), "rspe_%s.pdf" % i), ra.montar_texto(seeu.abas_dict(r), h)[0])
    with pdfplumber.open(rspe) as doc:
        textos = [x.extract_text() or "" for x in doc.pages]
    entrada = {"textos": textos, "hoje": h, "hash": hashlib.sha1(open(rspe, "rb").read()).hexdigest()}
    p = json.loads(rp.analisar_rspe(json.dumps(entrada, ensure_ascii=False)))
    # a ficha disciplinar desta pessoa, em PDF (para o teste de carregar a ficha): o esperado é o painel com a ficha lida pelo APTO
    pdf = fp.gerar(os.path.join(tempfile.mkdtemp(), "ficha_%s.pdf" % i), nome=r["nome"], cpf=r.get("cpf") or "", filiacao=r["nome_mae"] + " \\ PAI EXEMPLO",
                   eventos=fp.EXEMPLO, impresso=h)
    pf = json.loads(rp.analisar_rspe(json.dumps(dict(entrada, fichas=[rv.json_seguro(rf.extrair(pdf))]), ensure_ascii=False)))
    out[i] = {"processo": r["processo_execucao"], "nome": p["nome"], "paginas": seeu.paginas(r), "rspe_pdf": rspe, "url_rspe": seeu.URL_RSPE % seeu.id_execucao(r), "esperado": {"assinatura": p["assinatura"], "contagem": p["contagem"]},
              "ficha_pdf": pdf, "esperado_ficha": {"assinatura": pf["assinatura"], "contagem": pf["contagem"], "ficha": pf["ficha"]}}
json.dump(out, open(saida, "w", encoding="utf-8"), ensure_ascii=False)
print("ok", len(out))
