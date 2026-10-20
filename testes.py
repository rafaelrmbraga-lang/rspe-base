"""Roda os testes de regressão do APTO; sai com erro se algum falhar (o build não gera o .exe). Rodar: python testes.py"""
import subprocess
import sys

TESTES = ["teste_remicao.py", "teste_indulto_transito.py", "teste_auditoria_calculo.py", "teste_leitura_ficha.py", "teste_indulto_auditoria.py", "teste_ficha_redacoes.py", "teste_auditoria_revisao.py", "teste_auditoria_rev4.py", "teste_prescricao_revisao.py", "teste_prescricao_rev2.py", "teste_remicao_rev6.py", "teste_remicao_rev7.py", "teste_remicao_rev8.py", "teste_prescricao_rev4.py", "teste_leitura_rspe_rev4.py", "teste_sistema.py", "teste_remicao_rev9.py", "teste_ficha_rev4.py", "teste_saida_temporaria.py", "teste_progressao_antecipada.py", "teste_geopresidios.py", "teste_rev_1110.py", "teste_linha_tempo_rev.py", "teste_calculadora.py", "teste_auditoria_externa.py", "teste_trabalho_rev1012.py", "teste_casos_simulados.py", "teste_legislacao.py", "teste_leitura_rev1210.py", "teste_divergencia_seeu.py", "teste_leitura_robusta.py", "teste_prescricao_outra_acao.py", "teste_extensao_seeu.py", "teste_atendimentos.py", "teste_resumo_assistido.py", "teste_fundamentacao_remicao.py", "teste_precedentes_2026.py", "teste_remicao_intervalos.py", "teste_q1610_ficha.py", "teste_q1610_rspe.py", "teste_q1610_progressao.py", "teste_q1610_database.py", "teste_q1610_prescricao.py", "teste_q1610_indulto.py", "teste_q1610_remicao.py", "teste_q1610_sistema.py", "teste_q1610_juncao.py", "teste_remicao_leitura_1910.py"]
TESTES += ["teste_conf_D2.py"]  # conferência manual (7.13.0), frente D2: remição - contas e apresentação
TESTES += ["teste_conf_C1.py"]  # conferência manual (7.13.0), frente C1: reincidência e frações
TESTES += ["teste_conf_C2.py"]
TESTES += ["teste_conf_F.py"]
TESTES += ["teste_conf_E.py"]
TESTES += ["teste_conf_B.py"]
TESTES += ["teste_conf_A.py"]  # conferência manual (7.13.0), frente A: RSPE, eventos e custódia
falhas = [t for t in TESTES if subprocess.call([sys.executable, t]) != 0]
if falhas:
    print("FALHOU: " + ", ".join(falhas))
    sys.exit(1)
print("todos os testes passaram (%d)" % len(TESTES))
