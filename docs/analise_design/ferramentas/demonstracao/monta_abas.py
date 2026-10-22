import json, base64, os, sys
D = os.path.dirname(os.path.abspath(__file__))
r = json.load(open(os.path.join(D, "listar.json"), encoding="utf-8"))
K = ["id","nome","proc","regime","prog","liv","termino","geral_cor","prog_sit","prog_cor","prog_dias","liv_sit","liv_cor","liv_dias","conduta","falta",
     "imp","imp_cor","i22","i22_cor","i24","i24_cor","c24","c24_cor","i25","i25_cor","c25","c25_cor","ind_cor","presc_ppe","presc_ppe_cor","presc_prox","presc_dias",
     "ext_termino","ext_sit","ext_cor","ext_dias","fd_trab","fd_atestar","fd_estudo","fd_sit","fd_cor","aud_resumo","aud_cor","hist_n",
     "pena_total","pena_cumprida","pena_rem","db","db_motivo","geracao","i24_full","presc_ppe_full","ext_sit"]
dados = [{k: x.get(k) for k in K} for x in r["registros"]]
b64 = lambda f: base64.b64encode(open(os.path.join(D, f), "rb").read()).decode()
fontes = [("Cinzel", 700, "Cinzel-Bold"), ("Source Sans 3", 400, "SourceSans3-Regular"), ("Source Sans 3", 600, "SourceSans3-SemiBold"), ("Source Sans 3", 700, "SourceSans3-Bold"), ("Source Serif 4", 600, "SourceSerif4-SemiBold")]
css = "\n".join(f'@font-face{{font-family:"{n}";font-weight:{w};src:url(data:font/woff2;base64,{b64(f + ".woff2")}) format("woff2")}}' for n, w, f in fontes)
h = open(os.path.join(D, "abas_modelo.html"), encoding="utf-8").read().replace("__FONTS__", css).replace("__SELO__", "data:image/png;base64," + b64("selo96.png")).replace("__DADOS__", json.dumps(dados, ensure_ascii=False, default=str))
open(sys.argv[1], "w", encoding="utf-8").write(h); print(sys.argv[1], len(h)//1024, "KB")
