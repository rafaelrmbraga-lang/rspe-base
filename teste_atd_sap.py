"""Leitura do SAP para a função Atendimentos (extensão, atd_sap.js), numa imitação da tela do SAP com dados fictícios: roda o
teste em node + Playwright (extensao_seeu_testes/teste_atd_sap.js), se houver; sem eles, avisa e não falha.
Rodar: python teste_atd_sap.py"""
import os
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
node = shutil.which("node")
if not node:
    print("ok: (sem node: teste da leitura do SAP não executado)")
    sys.exit(0)
r = subprocess.run([node, os.path.join(AQUI, "extensao_seeu_testes", "teste_atd_sap.js")], capture_output=True, text=True, timeout=300)
print((r.stdout or r.stderr).strip())
sys.exit(r.returncode)
