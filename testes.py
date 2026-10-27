"""Roda os testes de regressão do APTO; sai com erro se algum falhar (o build não gera o .exe). Rodar: python testes.py"""
import os
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
TESTES += ["teste_conf_D1.py"]  # conferência manual (7.13.0), frente D1: remição ligada à origem
TESTES += ["teste_remicao_714.py"]  # remição 7.14: comparação por totais e trabalho x atestados com vinculação
TESTES += ["teste_remicao_714b.py"]  # remição 7.14, segunda rodada: provavelmente remido, cinza com RSPE maior, atestado sem período, aviso de outra execução
TESTES += ["teste_leitura_714.py"]
TESTES += ["teste_conf2_remicao.py"]  # conferência 7.14.1, frente remição
TESTES += ["teste_conf2_prescricao.py"]
TESTES += ["teste_conf2_indulto.py"]
TESTES += ["teste_conf2_auditoria.py"]
TESTES += ["teste_conf3_prescricao.py"]  # conferência 7.14.2, frente prescrição e extinção
TESTES += ["teste_conf3_indulto.py"]
TESTES += ["teste_conf3_progressao.py"]
TESTES += ["teste_conf3_remicao.py"]
TESTES += ["teste_conf4_remicao.py"]  # conferência 7.14.3, frente remição
TESTES += ["teste_conf4_demais.py"]
TESTES += ["teste_conf5.py"]  # validação da 7.14.3: resíduos (7.14.4)
TESTES += ["teste_conf6_demais.py"]  # conferência independente (7.14.5): livramento, extinção, auditoria, prescrição e progressão
TESTES += ["teste_conf6_indulto.py"]
TESTES += ["teste_conf7_demais.py"]
TESTES += ["teste_triagem_seeu.py"]  # extensão: triagem da Mesa do Defensor
TESTES += ["teste_conf6_remicao.py"]  # conferência 7.14.4 (70 casos novos), frente remição (7.14.5)
TESTES += ["teste_conf6_art75.py"]  # extinção mostra a ressalva do art. 75 (7.14.5)
TESTES += ["teste_conf7_indulto.py"]
TESTES += ["teste_conf7_detracao.py"]  # forma favorável da detração em a/m/d (7.14.6)
TESTES += ["teste_conf8_indulto.py"]  # terceira conferência independente (7.14.7), frente indulto e comutação
TESTES += ["teste_conf8_demais.py"]
TESTES += ["teste_rev_cap3.py"]  # revisão jurídica do Capítulo 3, progressão e livramento (7.14.8)
# saída em UTF-8 em qualquer console (no Windows o padrão cp1252 não imprime símbolos como "✓" e derruba o teste)
_env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
falhas = [t for t in TESTES if subprocess.call([sys.executable, t], env=_env) != 0]
if falhas:
    print("FALHOU: " + ", ".join(falhas))
    sys.exit(1)
print("todos os testes passaram (%d)" % len(TESTES))
