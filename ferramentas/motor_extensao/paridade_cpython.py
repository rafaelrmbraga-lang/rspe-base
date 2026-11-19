"""Paridade navegador x APTO, lado do APTO (CPython): para cada caso simulado, monta as abas do SEEU fictício
(ferramentas/seeu_ficticio) e calcula o painel pelo mesmo caminho da extensão (rspe_painel.analisar_abas: abas -> leitor do
APTO -> motor). Grava a entrada (as abas, a data) e a assinatura; o lado da extensão (paridade_pyodide.mjs) refaz a conta
no Pyodide, com os MESMOS arquivos do pacote, e tem de chegar à mesma assinatura em todos.
Uso: python ferramentas/motor_extensao/paridade_cpython.py saida.json"""
import json
import os
import sys
import types

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "ferramentas", "seeu_ficticio"))
sys.modules.setdefault("webview", types.ModuleType("webview"))
import seeu  # noqa: E402
import rspe_motor  # noqa: E402
import rspe_painel as rp  # noqa: E402

HOJE = "12/10/2026"


def main():
    with open(os.path.join(RAIZ, "extensao_seeu", "motor", "motor.json"), encoding="utf-8") as f:
        rspe_motor.VERSAO = json.load(f)["versao"]  # a mesma versão que a extensão usa (motor.json)
    casos = json.load(open(os.path.join(RAIZ, "casos_simulados", "casos.json"), encoding="utf-8"))
    out = {}
    for c in casos:
        entrada = json.dumps({"abas": seeu.abas_dict(c["rspe"]), "hoje": HOJE}, ensure_ascii=False)
        p = json.loads(rp.analisar_abas(entrada))
        if p.get("erro"):
            raise SystemExit("%s: as abas não foram lidas (%s)" % (c["id"], p))
        out[c["id"]] = {"entrada": entrada, "assinatura": p["assinatura"], "chave": p["chave"]}
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        json.dump({"motor": rspe_motor.VERSAO, "casos": out}, f, ensure_ascii=False)
    print("CPython %s: %d processos lidos pelas abas e calculados" % (sys.version.split()[0], len(out)))


if __name__ == "__main__":
    main()
