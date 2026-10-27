import os
import sys,os,time
S=os.environ.get("APTO_TRABALHO", os.path.join(__import__("tempfile").gettempdir(), "apto_analise"))
O=S+"/pdfx/out"
sys.path.insert(0,S+"/ponte")
import ponte
api,jan=ponte.criar(S+"/pdfx/base.sqlite")
api.listar()
ids=[m["id"] for m in api._modelos]
for i in ("9900001","9900002","9900093"):
    id_=next(x for x in ids if x.startswith(i))
    jan.dialogo=O+"/ind_%s.pdf"%i
    print(api.relatorio_um(id_))
jan.dialogo=O
t=time.time()
print(api.relatorios(ids, True, True, True, True, ids_individual=[x for x in ids if x[:7] in ("9900001","9900002","9900093")]), time.time()-t)
jan.dialogo=O+"/aba_prog.pdf"; print(api.exportar("pdf",["prog"],ids))
jan.dialogo=O+"/aba_presc.pdf"; print(api.exportar("pdf",["presc"],ids))
jan.dialogo=O+"/aba_ind.pdf"; print(api.exportar("pdf",["ind"],ids))
jan.dialogo=O+"/aba_fd.pdf"; print(api.exportar("pdf",["fd"],ids))
jan.dialogo=O+"/abas.xlsx"; print(api.exportar("xlsx",["geral","prog","liv","ind","presc","ext","fd","aud","completo"],ids))
