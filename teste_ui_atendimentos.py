"""Tela de Atendimentos dentro do APTO (7.20): roda atendimentos/teste_painel.js (node + Playwright), se houver; sem eles, avisa e
não falha. Ver o cabeçalho do .js. Rodar: python teste_ui_atendimentos.py"""
import os
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
node = shutil.which("node")
if not node:
    print("ok: (sem node: teste da tela de Atendimentos não executado)")
    sys.exit(0)
r = subprocess.run([node, os.path.join(AQUI, "atendimentos", "teste_painel.js")], capture_output=True, text=True, timeout=300)
print((r.stdout or r.stderr).strip())
sys.exit(r.returncode)
