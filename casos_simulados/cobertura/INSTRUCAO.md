# Base simulada de cobertura — instrução para os redatores de casos

## Objetivo
Montar uma base simulada do APTO (v7.14.7) com **um ou dois casos para cada modo e situação** que o programa promete tratar,
para o usuário (NUSPEN, Defensoria) abrir no APTO e analisar o sistema aba por aba. Cada caso tem um **gabarito**: o resultado
que a lei e as regras declaradas mandam, calculado **à mão, sem olhar o que o programa responde**. Depois roda-se o programa e as
diferenças viram achados.

## Material
- Código: /home/user/rspe-base (rspe_*.py). NÃO altere nenhum arquivo existente do repositório.
- Relatório técnico-jurídico da 7.14.7 (regras, uma por "### "), em
  /tmp/claude-0/-home-user-rspe-base/67b958a0-60f3-59ee-97bc-991a7ff6445e/scratchpad/rel/cap_N.txt. É o checklist do que cobrir.
- BASE INDEPENDENTE (pedido do usuário): a bateria antiga casos.json (S001–S144) foi usada para ajustar o programa. Não a use
  como modelo nem para escolher situações; cubra todas as situações da área com casos novos. O gabarito vem da lei, não do
  relatório nem do código (o código só para formato e nomes de campos).
- Construtores: /home/user/rspe-base/casos_simulados/base_casos.py (crime, rspe, ev, prisao, interr, inc, C, AUD, P, caso).
  Veja exemplos de uso lendo casos.json (formato final) e os testes teste_conf*.py / teste_q1610_*.py (formato do RSPE e da ficha).
  A ficha do SIAPEN entra no formato gravado na tabela fichas (dict); com "versao_leitura": 0 o programa relê os textos dos
  eventos (rspe_ficha.atualizar), então casos de ficha podem trazer o texto bruto dos lançamentos.
- Executor: /home/user/rspe-base/casos_simulados/roda_casos.py. Rode SEMPRE com destino próprio, para não colidir com os outros:
  `APTO_SIM_DESTINO=/home/user/rspe-base/casos_simulados/cobertura/tmp_<area>.sqlite python3 roda_casos.py cobertura/<area>.json --vazia`
  (a partir de /home/user/rspe-base/casos_simulados). Data de referência fixa: 12/10/2026; RSPE gerados em 05/10/2026.

## O que entregar (só arquivos novos, em /home/user/rspe-base/casos_simulados/cobertura/)
1. `gera_<area>.py`: script que importa base_casos e grava `<area>.json` (lista de casos no formato de casos.json).
2. `<area>.json`.
3. Relatório final (sua resposta): quantos casos, lista das situações cobertas, e os achados (ver abaixo).

Formato de cada caso: o de `caso(...)` mais três chaves:
- `"aba"`: aba principal (Geral, Progressão, Livramento, Saída temporária, Progressão antecipada, Auditoria, Ficha/Remição,
  Indulto, Prescrição, Extinção);
- `"situacao"`: a situação testada, em uma frase simples;
- `"esperado"`: o resultado esperado, em linguagem simples (ex.: "Progressão em 14/03/2027, fração 16%; sem alerta").
`"conta"` traz a conta passo a passo e o fundamento (lei, artigo, súmula, decreto). `"checks"` traduz o esperado em verificações
do executor (C campo, AUD item da Auditoria, P linha de prescrição). Use os campos que a tela mostra (veja CAMPOS_RESUMO em
roda_casos.py e o que Api._json_de devolve). `id` e número do processo: use SOMENTE a faixa de k reservada à sua área
(caso(k, ...) gera id "S%03d" e processo 99xxxxx). Nome do assistido: o gerado pelo construtor (SIMULADO CASO nnn). Nunca use
nomes reais nem dados reais.

## Regras do gabarito
- Calcule o esperado pela lei e pelas convenções do programa: ano de 365 dias, mês de 30, soma em anos/meses/dias, dia do começo
  incluído (CP, art. 10), fração em dias arredondada para baixo. Use o capítulo do relatório como descrição da regra, mas confira
  contra a lei; se o capítulo e a lei divergem, o gabarito segue a lei e o caso vira achado.
- Escolhas de política já decididas (o gabarito as segue):
  - Auditoria alerta só o que prejudica o assistido; fração do SEEU menor que a legal não gera alerta.
  - Data-base, art. 75 do CP e monitoramento lançado como interrupção: a aba mantém a data do SEEU com ressalva; a Auditoria alerta.
  - "Provavelmente remido" só até 180 dias da emissão do documento; de 180 dias a 3 anos, "mesmo valor decidido em ...: conferir".
  - Remição sem documento correspondente cobre primeiro o trabalho mais próximo dela.
  - Saída temporária com crimes de antes e depois da Lei 14.843/2024: requisito atendido.
  - Execução unificada: não se sugere extinção de pena isolada.
- Evite que o resultado mude entre 12/10/2026 e 31/03/2027 (o usuário vai abrir a base depois): nenhum prazo, vencimento ou
  janela de 12 meses deve cair nesse intervalo, salvo se o caso testar justamente isso (diga no "esperado").
- Um caso = uma situação principal (no máximo duas). Casos curtos e legíveis.

## Achados
Rode o executor. Para cada verificação que falhar:
1. Reconfira o gabarito contra a lei. Se o gabarito estava errado, corrija-o (diga isso no relatório).
2. Se o gabarito está certo, NÃO o ajuste ao programa: mantenha a verificação falhando e acrescente `"nota"` explicando a
   divergência. Se for tese discutível ou escolha de política, marque `"decisao": true` e explique.
3. Se o caso não montou (erro de montagem), conserte o formato do caso.
No relatório final, liste: casos criados por situação; verificações; falhas (programa diverge da lei), com caso, esperado,
o que o programa mostrou e o fundamento; falhas por tese discutível. Linguagem simples, sem jargão de programação.
Seja econômico: não leia o código inteiro, só o necessário para acertar o formato e os nomes dos campos.
