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
TESTES += ["teste_linha_e.py"]  # tela da linha E (27/10/2026): importar, menu lateral, filtros combináveis, situação, avisos, parar a importação
TESTES += ["teste_cob_ficha.py", "teste_cob_remicao.py", "teste_cob_indulto.py", "teste_cob_situacao.py", "teste_cob_auditoria.py"]  # 7.15.1: base simulada independente
TESTES += ["teste_rev_ficha_remicao.py", "teste_rev_progressao_auditoria.py", "teste_rev_leitura_prazos.py", "teste_rev_indulto.py", "teste_rev_comparacao.py"]  # 7.15.2: revisões jurídicas por capítulo
TESTES += ["teste_ui_remicao.py"]  # 7.15.3: aba Ficha didática ("O que pedir", remições x o que cada uma cobre, vínculos e documentos)
TESTES += ["teste_dec_leitura_prazos.py", "teste_dec_ficha_remicao.py", "teste_dec_progressao_auditoria.py", "teste_dec_indulto.py"]  # 7.15.3: decisões dos pareceres P01-P57
TESTES += ["teste_teses_favoritos.py"]  # 7.15.4: favoritos na aba Jurisprudências
TESTES += ["teste_presc_art115_tela.py"]  # 7.15.4: motivo da metade do art. 115 no quadro da prescrição
TESTES += ["teste_monitor_juris.py"]  # 7.16.0: Monitor na aba Jurisprudências (sentido, turma pelo relator, taxa, filtros, relatório)
TESTES += ["teste_rev_indulto_ancora.py"]  # 7.16.2: revisão do indulto - âncora zerada com poucos dias pelos eventos
TESTES += ["teste_rev_ficha_leitura.py", "teste_rev_ficha_estudo.py", "teste_rev_ficha_exame.py", "teste_rev_ficha_cela.py",
           "teste_rev_ficha_pagamento.py"]  # revisão da aba Ficha na base real (150 casos): leitura, estudo, exame, cela, pagamento
TESTES += ["teste_rev_presc_termo_mp.py"]  # revisão da Prescrição (11/2026): termo pelo trânsito para a acusação não informado (Tema 788)
TESTES += ["teste_rev_presc_reinc.py"]  # revisão da Prescrição (11/2026): +1/3 da reincidência marcada no prazo principal, hipótese sem ele no aviso
TESTES += ["teste_ui_avisos.py"]  # 7.16.2: avisos do Python chegam à tela (window.ui; andamento dos dados prisionais)
TESTES += ["teste_ui_menu.py"]  # 7.16.2: menu lateral recolhido (balão com nome, número e Alt+n; expansão mantida)
TESTES += ["teste_cache_calculo.py"]  # 7.16.2: cache dos cálculos idêntico ao cálculo do zero
TESTES += ["teste_rev_randomizada.py"]  # revisão independente e randomizada (11/2026): hediondos, progressão, livramento, extinção e indulto
TESTES += ["teste_rev_indulto_pontos.py"]  # 7.16.4: pontos abertos do relatório do indulto (crime culposo 2019-2021, janela, sentença incoerente 2022, nascimento x livramento, mora)
TESTES += ["teste_ui_718.py"]  # 7.18.0: CSS consolidado e propostas de interface
TESTES += ["teste_ui_funcoes.py"]  # 7.19.0: barra fixa das funções (Atendimentos, Execução, SEEU, SEI, Quadro, Relatório)
TESTES += ["teste_atendimentos_apto.py"]  # 7.20.0: Atendimentos no APTO (base do gabinete, servidor da extensão, pedidos ao SAP)
TESTES += ["teste_atd_sap.py"]  # 7.20.0: extensão lê a fila e o Fato Narrado do SAP para o APTO (SAP fictício)
TESTES += ["teste_indulto_saidas_fechado.py", "teste_painel_seeu.py", "teste_seeu_abas.py"]  # 7.32.0: saídas temporárias só "a conferir" quando o regime da data permitia; painel do APTO no SEEU e leitura das abas do SEEU
TESTES += ["teste_ui_atendimentos.py"]  # 7.20.0: tela de Atendimentos no APTO (moldura, subabas, Word, petição, Quadro, produção do mês)
TESTES += ["teste_nuspen_regras.py"]  # 7.21.0: regras e leitor do SEI vindos do NUSPEN, com os testes originais
TESTES += ["teste_sei_apto.py"]  # 7.21.0: SEI no APTO, ponta a ponta com o SEI fictício
TESTES += ["teste_seeu_apto.py"]  # 7.23.0: intimações do SEEU guardadas até concluir, baixa na produção do mês, botões Ler a Mesa / Ler o SEI
TESTES += ["teste_ui_sei_seeu.py"]  # 7.21.0: telas SEEU (Mesa do Defensor) e SEI
TESTES += ["teste_quadro_unico.py"]  # 7.26.0: Quadro único (sem Quadro do Usuário na Execução)
TESTES += ["teste_nuspen_gestao.py", "teste_ui_nuspen.py"]  # 7.27.0: gestão do NUSPEN (demandas, providências, prazos, ofícios, inspeções, minutas, PDF)
TESTES += ["teste_ui_metodos.py"]  # 7.30.1: toda função chamada pela tela existe
# saída em UTF-8 em qualquer console (no Windows o padrão cp1252 não imprime símbolos como "✓" e derruba o teste)
_env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
falhas = [t for t in TESTES if subprocess.call([sys.executable, t], env=_env) != 0]
if falhas:
    print("FALHOU: " + ", ".join(falhas))
    sys.exit(1)
print("todos os testes passaram (%d)" % len(TESTES))
