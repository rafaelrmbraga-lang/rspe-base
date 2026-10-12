"""Bateria de 141 casos simulados (situações que a base real não tem: frações de todas as leis, livramento, prazos, prescrição,
extinção, faltas e data-base, indulto e comutação 2024/2025, ficha e remição), cada um com a conta feita à parte, conferida pela
Api da tela numa base nova só com os casos. As divergências marcadas "decisão jurídica" não contam como falha.
Rodar: python teste_casos_simulados.py"""
import os
import subprocess
import sys

aqui = os.path.dirname(os.path.abspath(__file__))
p = subprocess.run([sys.executable, os.path.join(aqui, "casos_simulados", "roda_casos.py"), "--vazia"], capture_output=True, text=True)
fim = (p.stdout.strip().splitlines() or [""])[-1]
if p.returncode != 0:
    print("FALHOU (casos simulados): " + fim)
    print("\n".join(l for l in p.stdout.splitlines() if " - FALHA" in l or l.startswith("    x") or "ERRO" in l))
    print(p.stderr[-2000:])
    sys.exit(1)
print("ok: casos simulados (%s)" % fim)
