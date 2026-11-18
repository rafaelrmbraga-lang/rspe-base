"""Regras e leitor do SEI vindos do NUSPEN (7.21), com os testes originais do NUSPEN: nuspen_regras/testes (pytest: obrigações,
prazo expresso, rodapé do SEI, sinalizações) e extensao_seeu/sei/teste (node --test: leitor só leitura, contrato dos adaptadores,
estado do painel, sanitizador de estrutura). Sem pytest ou sem node, a parte correspondente é avisada e pulada.
Rodar: python teste_nuspen_regras.py"""
import glob
import os
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
falhou = False
saida = []
try:
    import pytest  # noqa: F401
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", os.path.join(AQUI, "nuspen_regras", "testes")],
                       capture_output=True, text=True, cwd=AQUI, timeout=300)
    ult = (r.stdout.strip().splitlines() or ["?"])[-1]
    saida.append("regras do NUSPEN: " + ult)
    if r.returncode:
        falhou = True
        print(r.stdout[-3000:])
except ImportError:
    saida.append("regras do NUSPEN: sem pytest, não executado")
node = shutil.which("node")
if node:
    arqs = sorted(glob.glob(os.path.join(AQUI, "extensao_seeu", "sei", "teste", "*.test.mjs")))
    r = subprocess.run([node, "--test", *arqs], capture_output=True, text=True, timeout=300)
    pas = [l for l in r.stdout.splitlines() if l.startswith(("# pass", "# fail"))]
    saida.append("leitor do SEI: " + ", ".join(pas))
    if r.returncode:
        falhou = True
        print(r.stdout[-3000:])
else:
    saida.append("leitor do SEI: sem node, não executado")
print(("FALHA: " if falhou else "ok: ") + "; ".join(saida))
sys.exit(1 if falhou else 0)
