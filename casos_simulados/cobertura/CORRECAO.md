# Correção 7.14.8 — divergências da base simulada independente

Base: branch claude/vibrant-wright-db4zqo, commit d7c789f. ANTES de tudo, no seu worktree, confirme que está nesse commit
(`git merge-base --is-ancestor d7c789f HEAD`); se não estiver, `git fetch origin claude/vibrant-wright-db4zqo && git reset --hard d7c789f`.

## O que corrigir
Os casos da sua frente estão em casos_simulados/cobertura/<area>.json (campo "conta", "esperado" e a "nota" de cada verificação
que falha). Rode só os seus casos com:
`cd casos_simulados && APTO_SIM_DESTINO=/tmp/<frente>.sqlite python3 roda_casos.py cobertura/<area>.json --vazia --so S2032,S2038`
Para cada divergência:
1. Confirme pela lei (e pela política abaixo) que o gabarito está certo. Se concluir que o gabarito está errado, NÃO mexa no
   programa: explique no relatório final, com fundamento (o coordenador decide).
2. Corrija a causa no programa, de forma geral (não por caso), sem quebrar o resto.
3. Escreva um teste de regressão em arquivo NOVO `teste_cob_<frente>.py` na raiz (padrão dos teste_conf*.py: imprime "ok: ..." e
   sai com código 1 se falhar). NÃO edite testes.py (o coordenador registra o arquivo).
4. NÃO edite casos.json, os <area>.json da cobertura (salvo erro de montagem óbvio, que você relata), LEIA-ME.txt nem VERSAO.

## Política (decisões do usuário)
- Auditoria alerta só o que prejudica o assistido; erro do SEEU que o favorece não é alerta (no máximo info).
- Data do SEEU contrária à lei (data-base, art. 75, monitoramento lançado como interrupção): a aba mantém a data do SEEU com
  ressalva e a Auditoria ALERTA (nível alerta) com a data correta e o fundamento.
- "Provavelmente remido" só até 180 dias; 180 dias a 3 anos "mesmo valor decidido em ...: conferir".
- Remição sem documento cobre primeiro o trabalho mais próximo.
- Execução unificada: não sugerir extinção de pena isolada.
- Contagem: ano 365, mês 30, dia do começo incluído (CP, art. 10).

## Antes de terminar (obrigatório)
- `python3 testes.py` inteiro passando (hoje: 80 testes), mais o seu teste novo.
- A bateria antiga sem regressão: `cd casos_simulados && APTO_SIM_DESTINO=/tmp/<frente>_old.sqlite python3 roda_casos.py --vazia`
  (144 casos, 0 falhas).
- A cobertura inteira sem regressão: `cd casos_simulados/cobertura && python3 falhas.py /tmp/<frente>_falhas.json base_falhas.json`.
  A linha "PASSARAM A FALHAR" tem de dizer "nenhuma"; "passaram a acertar" deve listar as suas verificações.
  (Ponto de partida: 66 verificações falhando, 16 delas "decisão" — teses que ficam.)
- Commit no seu worktree com mensagem clara, terminando com:
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_011o5EBezULNdZvepBWf2Zff
- Não faça push.

## Relatório final
Em linguagem simples: cada divergência (caso, o que estava errado, o que mudou, fundamento); as que você não corrigiu e por
quê; resultado dos testes e das duas baterias; arquivos alterados. Nunca use nomes reais de assistidos.
