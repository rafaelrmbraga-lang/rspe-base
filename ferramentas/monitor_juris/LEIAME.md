# Geração do monitor_juris.bin (Monitor da aba Jurisprudências)

Scripts usados para gerar `monitor_juris.bin` a partir do acervo `acervo_jurisprudencia.db` (não versionado: 903 MB).

1. Copie o acervo para uma pasta de trabalho e defina `APTO_MJ_PASTA` com o caminho dela (o acervo em `APTO_MJ_PASTA/acervo/acervo_jurisprudencia.db`).
2. `python3 carga.py` — lê o acervo (somente leitura).
3. `python3 rodar.py` — escopo de execução penal, temas e sentido para a defesa (regras em `classif.py`).
4. `python3 gerar_bin.py` — grava o `monitor_juris.bin` (cabeçalho APTOMON1 + JSON comprimido); copie-o para a raiz do repositório.

Precisão medida na 7.16.1 (577 decisões lidas; rodada final fora do ajuste): TJMS 90,6%, STJ 100%, STF 93,1%.
Confira os caminhos de entrada e saída no começo de cada script antes de rodar.
