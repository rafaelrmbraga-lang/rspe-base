"""Roda os testes de regressão do APTO; sai com erro se algum falhar (o build não gera o .exe). Rodar: python testes.py"""
import subprocess
import sys

TESTES = ["teste_remicao.py", "teste_indulto_transito.py", "teste_auditoria_calculo.py", "teste_leitura_ficha.py", "teste_indulto_auditoria.py", "teste_ficha_redacoes.py", "teste_auditoria_revisao.py", "teste_auditoria_rev4.py", "teste_prescricao_revisao.py", "teste_prescricao_rev2.py", "teste_remicao_rev6.py", "teste_remicao_rev7.py", "teste_remicao_rev8.py", "teste_prescricao_rev4.py", "teste_leitura_rspe_rev4.py"]
falhas = [t for t in TESTES if subprocess.call([sys.executable, t]) != 0]
if falhas:
    print("FALHOU: " + ", ".join(falhas))
    sys.exit(1)
print("todos os testes passaram (%d)" % len(TESTES))
