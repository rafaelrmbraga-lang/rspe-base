# APTO SEEU

Extensão separada, só com o painel do APTO na página do processo no SEEU (análise, chips dos marcos e benefícios, destaques das
movimentações, prévia dos documentos, ficha disciplinar por upload, resumo para o assistido, medidas alternativas). Sem SIAPEN, SEI,
SAP, Triagem da Mesa nem download do RSPE para o APTO: para quem vai testar sem a extensão completa.

Os arquivos do painel são os MESMOS da extensão do APTO (`extensao_seeu/painel`, `comum.js`, `pdfjs`, `motor`): correção no painel
vale para as duas. Próprios desta extensão: `fonte/` (service worker, popup) e o manifesto (em `montar.py`).

    python ferramentas/motor_extensao/empacotar.py          # o motor (os .py do APTO no Pyodide)
    python ferramentas/apto_seeu/montar.py dist             # dist/apto_seeu/ e dist/apto_seeu_<versão>.zip
    python ferramentas/apto_seeu/montar.py dist capturas    # idem, com o guia em PDF (capturas do SEEU fictício)

As capturas do guia (nenhuma com dado real) saem do teste de ponta a ponta com a própria APTO SEEU e das telas do Chrome:

    python extensao_seeu_testes/paginas_painel.py S035,S141,S001 paginas.json
    APTO_EXT=dist/apto_seeu node extensao_seeu_testes/teste_painel_e2e.js paginas.json e2e
    node ferramentas/apto_seeu/capturas_chrome.js dist/apto_seeu capturas
    python -c "import sys; sys.path.insert(0, 'ferramentas/apto_seeu'); import guia; guia.preparar('capturas', 'e2e')"
    python ferramentas/apto_seeu/montar.py dist capturas
 O teste `teste_apto_seeu.py` confere o manifesto (permissões mínimas, só o SEEU) e os arquivos.
