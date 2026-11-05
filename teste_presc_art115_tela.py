"""Prescrição: a tela diz por que o prazo caiu pela metade (CP, art. 115) - o motivo vem da linha (art115_motivo)."""
import os, sys
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rspe_prescricao as rp
falhas = []
c = {"processo_criminal": "0000001-00.2014.8.12.0001", "artigo": "ART 35: Associação para o tráfico", "lei": "11343/06 - Lei de Drogas",
     "tipo_penal": "CAPUT", "pena_imposta": "3 ano(s), 5 mês(es) e 0 dia(s)", "data_infracao": "19/02/2014", "data_denuncia": "05/05/2014",
     "data_sentenca": "29/06/2018", "transito_mp": "26/03/2019", "transito_processo": "26/03/2019", "extinto": "Não", "suspenso": "Não",
     "reincidente_comum": "N", "reincidente_especifico": "N"}
r = {"processo_execucao": "0000002-00.2020.8.12.0001", "data_nascimento": "31/05/1995", "data_geracao_rspe": "05/10/2026",
     "_crimes": [c], "_eventos": [], "_incidentes": []}
try:
    out = rp.analisar(r, date(2026, 10, 12))
except TypeError:
    out = rp.analisar(r)
L = (out.get("presc_linhas") if isinstance(out, dict) else out)[0]
if not L.get("art115"): falhas.append("art115 deveria valer (18 anos no fato)")
if L.get("art115_motivo") != "menor de 21 anos na data do fato": falhas.append("motivo: %r" % L.get("art115_motivo"))
h = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui.html"), encoding="utf-8").read()
if "reduzido à metade (CP, art. 115" not in h: falhas.append("ui.html sem o motivo")
if falhas:
    print("FALHOU (art. 115 na tela): " + "; ".join(falhas)); sys.exit(1)
print("ok: prescrição mostra a metade do art. 115 e o motivo")
