import os
import sys
S=os.environ.get("APTO_TRABALHO", os.path.join(__import__("tempfile").gettempdir(), "apto_analise"))
sys.path.insert(0,S+"/ponte")
import ponte
api,jan=ponte.criar(S+"/pdfx/base.sqlite"); api.listar()
for i in ("9900055","9900045"):
    id_=next(m["id"] for m in api._modelos if m["id"].startswith(i))
    jan.dialogo=S+"/pdfx/out/ind_%s.pdf"%i; print(api.relatorio_um(id_))
