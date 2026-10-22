"""Monta a demonstração 'alfabética × por urgência' com os dados fictícios exportados do próprio APTO (Api.listar)."""
import json, base64, os, sys
D = os.path.dirname(os.path.abspath(__file__))
SAIDA = sys.argv[1]
r = json.load(open(os.path.join(D, "listar.json"), encoding="utf-8"))
dados = [{"id": x["id"], "nome": x["nome"], "proc": x["proc"], "regime": x["regime"], "prog": x["prog"], "sit": x["prog_sit"],
          "prog_cor": x["prog_cor"], "dias": x["prog_dias"], "conduta": x["conduta"], "falta": x["falta"]} for x in r["registros"]]
b64 = lambda f: base64.b64encode(open(os.path.join(D, f), "rb").read()).decode()
fontes = [("Cinzel", 700, "Cinzel-Bold"), ("Source Sans 3", 400, "SourceSans3-Regular"), ("Source Sans 3", 600, "SourceSans3-SemiBold"),
          ("Source Sans 3", 700, "SourceSans3-Bold"), ("Source Serif 4", 600, "SourceSerif4-SemiBold")]
css = "\n".join(f'@font-face{{font-family:"{n}";font-weight:{w};font-style:normal;font-display:block;src:url(data:font/woff2;base64,{b64(f + ".woff2")}) format("woff2")}}' for n, w, f in fontes)
h = open(os.path.join(D, "modelo.html"), encoding="utf-8").read()
h = h.replace("__FONTS__", css).replace("__SELO__", "data:image/png;base64," + b64("selo96.png")).replace("__DADOS__", json.dumps(dados, ensure_ascii=False))
open(SAIDA, "w", encoding="utf-8").write(h)
print(SAIDA, len(h) // 1024, "KB", len(dados), "assistidos")
