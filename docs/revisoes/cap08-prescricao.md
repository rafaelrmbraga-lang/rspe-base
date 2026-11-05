# Revisão jurídica — Capítulo 8 (Prescrição)

- **Objeto:** relatório técnico-jurídico do APTO, aba Prescrição (capítulo 8), versão 7.14.7.
- **Revisão feita em:** 27/10/2026, sobre o `main` da versão 7.14.7 (commit `04bd716`).
- **Reconferido em:** 05/11/2026, sobre o `main` da versão 7.15.1 (commit `0ed0b1a`). Os casos fictícios dos achados 1, 2, 5 e 6 foram rodados de novo e o resultado não mudou. As citações dos achados 3a, 8, 9 e 11 continuam iguais no código.
- **Etapa:** primeira etapa, só revisão. Nenhum código foi alterado.
- **PDF:** [Revisao_Cap8_Prescricao_APTO_7.14.7.pdf](Revisao_Cap8_Prescricao_APTO_7.14.7.pdf), com a tabela completa de precedentes e os casos fictícios.
- **Dados:** só casos fictícios. Nenhum nome ou processo real.

## Resumo

| Item | Quantidade |
|---|---|
| Regras do capítulo revisadas | 55 |
| Regras sem nenhum achado | 41 |
| Erros de resultado | 3 (achados 1, 2 e 4) |
| Erros de fundamento ou citação | 5 (achados 3a, 8, 9, 10 e 11) |
| Erros só de texto | 3 (achados 5, 6 e 7) |
| Teses discutíveis não sinalizadas ou mal fundamentadas | 3 (achados 3b, 12 e 13) |
| Citações procuradas no JusRatio | 47: 42 confirmadas, 3 com pertinência fraca ou imprópria, 1 diz o contrário, 1 não localizada |

Pontos já conhecidos: os quatro foram confirmados (achados 1, 4, 5 e 6).

Lei vigente em outubro de 2026:
- A Lei 15.160/2025 (art. 115, em vigor desde 04/07/2025) está aplicada corretamente.
- A Lei 15.358/2026 não altera nenhuma regra de prescrição.
- As mudanças do art. 112 da LEP tratam de progressão e não afetam este capítulo.

## Achados

Na coluna "Decisão sua?": **não** quer dizer que a correção decorre da lei ou de regra já descrita no relatório; **sim** quer dizer que há uma escolha a fazer antes de corrigir.

| Nº | Regra (seção) | Problema | Fundamento | Efeito para o assistido | Correção proposta | Tipo | Prioridade | Decisão sua? |
|---|---|---|---|---|---|---|---|---|
| 1 | Suspensão do processo pelo art. 366 do CPP (8.3) | Sem a data de fim, a suspensão vai "até hoje" (limitada ao teto), aparece "(ainda suspenso)" mesmo com sentença e é somada também ao trecho sentença → trânsito. No trecho denúncia → sentença, conta até o dia da sentença e afirma "não configurada" quando o resultado depende do fim. Caso fictício: furto, pena de 1 ano, denúncia em 01/02/2012, suspensão desde 01/06/2012 sem fim, sentença em 01/06/2019, trânsito em 01/09/2023. Sem a suspensão, a intercorrente venceu em 31/05/2023. Com ela, o programa soma 366 dias ao trecho depois da sentença e mostra "não configurada". | CPP, art. 366 (a sentença pressupõe o processo retomado); STF, Tema 438; STJ, Súmula 415 | Esconde prescrição intercorrente aparente; afirma "não configurada" quando a retroativa depende de dado ausente | Sem fim informado, a suspensão termina no máximo na véspera da sentença e nunca entra em trecho posterior; o dia da sentença não conta como suspenso. Se o trecho denúncia → sentença depender do fim: "A VERIFICAR: informe quando o processo voltou a correr", com a data-limite que ainda daria prescrição. | Erro de resultado | Alta | Não |
| 2 | Crime continuado e concurso formal (8.2) | O cálculo usa a pena com o acréscimo; só há aviso, e o resultado e a cor não mudam. Caso fictício: furto continuado, pena de 2a4m, denúncia em 01/02/2014, sentença em 01/03/2019. O programa mostra "não configurada" (8 anos). Sem o acréscimo (pena-base de 1a4m24d a 2a), o prazo é de 4 anos, vencido em 31/01/2018, em todas as frações. | STF, Súmula 497; CP, art. 119; STJ, RHC 14.277 | Deixa de apontar prescrição punitiva e executória | Testar a pena sem o acréscimo nas frações possíveis (continuidade de 1/6 a 2/3; específica até o triplo; concurso formal de 1/6 a 1/2). Todas prescritas: aparente, com nota. Divergentes: A VERIFICAR, com a fração que decide. Permitir que o operador informe a pena sem o acréscimo. | Erro de resultado (lacuna) | Alta | Sim: confirmar se, com todas as frações prescritas, o resultado sai firme (vermelho) ou em amarelo |
| 3a | Livramento condicional (8.5) e Ficha do SIAPEN — monitoramento, domiciliar ou aberto por outro processo (8.5) | O relatório cita o STJ, HC 429.545, e o Tema 1.367/STJ em apoio a "livramento de outra pena: a prescrição desta corre". O acórdão diz o contrário: "Prevalece no STJ o entendimento no sentido de que o regramento trazido no art. 116, parágrafo único, do CP abrange também aqueles que se encontram cumprindo pena em regime aberto, prisão domiciliar ou em livramento condicional". O Tema 1.367 trata do início do cumprimento da pena de crime praticado no livramento, e não de prescrição. | STJ, HC 429.545 (5ª Turma, 24/04/2018); STJ, Tema 1.367 | A citação contrária pode chegar ao pedido e enfraquecer a tese | Retirar o HC 429.545 e o Tema 1.367 como apoio; registrar o HC 429.545 como a posição contrária do STJ | Erro de citação | Alta | Não |
| 3b | Mesmas regras (8.5) | A tese adotada (só a prisão suspende; livramento, aberto, domiciliar ou monitoramento por outra pena não suspendem) favorece o assistido, mas o resultado sai em vermelho, como prescrição firme | Corrente favorável: o texto do art. 116, parágrafo único, fala em "preso"; a norma não se amplia contra o réu. STJ: contrário (HC 429.545). STF e TJMS: posição não localizada nesta revisão | Risco de pedido indeferido | Manter a tese, mas mostrar em amarelo "Prescrição aparente pela tese defensiva — o STJ entende que o prazo fica suspenso (HC 429.545)", com as duas contas | Tese discutível | Média | Sim: manter a tese defensiva ou seguir o STJ |
| 4 | Suspensão somada ao vencimento (8.6); restritiva, sursis e art. 28 (8.8); art. 366 (8.3) | Três contas de dias suspensos tratam os dias de borda de formas diferentes. (a) Pena privativa: não conta o início do trecho nem o dia do início do cumprimento. (b) Restritiva, sursis e art. 28: contam o dia da conversão. (c) Art. 366: conta o primeiro dia do intervalo e o dia da sentença (o mesmo dia em dois intervalos). | CP, art. 10; regra descrita no próprio relatório (8.6) | Diferença de 1 dia no vencimento; só muda o resultado quando o marco cai no último dia | Uma regra única: o dia do início do trecho não conta; o dia da prisão e o da soltura contam; o dia do ato que interrompe não conta | Erro de resultado (raro) | Baixa | Não |
| 5 | Revogação do livramento; pedido do saldo (8.7) | Os textos chamam a revogação de "fuga": "A fuga durou 6 anos (de 01/02/2018 …)", "Confirme o saldo na fuga de …", "informe a pena remanescente na fuga de …" | CP, arts. 88 e 113 | Texto impreciso que pode ir para a petição | Usar "revogação do livramento" no quadro, no alerta, no pedido do saldo e na memória | Só texto | Baixa | Não |
| 6 | Saldo zero na fuga (8.7) | "saldo zero; nada a prescrever; recaptura em … → interrompe (art. 117, V)": com saldo zero, não há prazo a interromper | LEP, art. 66, II; CP, art. 117, V | Texto contraditório; esconde a possível prisão depois da pena cumprida | "Recaptura em … — sem efeito na prescrição (saldo zero); ver a hipótese de pena cumprida na aba Extinção" | Só texto | Baixa | Não |
| 7 | Exemplo do art. 366 (8.3) | O relatório diz "teto da suspensão 4 anos"; o correto é 8 anos (art. 109, IV, pela pena máxima de 4 anos), o que o próprio exemplo usa (limite em 31/05/2020) | STJ, Súmula 415; STF, Tema 438 | Nenhum no cálculo | Corrigir o texto do exemplo | Só texto | Baixa | Não |
| 8 | Art. 366 — fundamento (8.3) | Cita só a Súmula 415/STJ; falta a tese vinculante do STF, Tema 438 (RE 600.851, 07/12/2020) | STF, Tema 438; STJ, Corte Especial, AgRg no RE nos EDcl no AgRg no AREsp 1.664.109 | Fundamentação mais fraca | Acrescentar o Tema 438 e a ressalva dos crimes imprescritíveis | Fundamento | Baixa | Não |
| 9 | Reincidência: acréscimo de 1/3 (8.2) | A regra "a punitiva não recebe o +1/3" está correta, mas sem fundamento expresso | STJ, Súmula 220 | Nenhum no cálculo | Citar a Súmula 220/STJ | Fundamento | Baixa | Não |
| 10 | Medida de segurança (8.8) | A Súmula 527/STJ trata da duração máxima da medida, e não da prescrição | STJ, AgRg no REsp 1.667.508; STJ, HC 53.170 | Citação imprópria | Manter os dois acórdãos; retirar a súmula ou usá-la só como reforço | Fundamento | Baixa | Não |
| 11 | Art. 28 da Lei 11.343/2006 (8.2 e 8.8) | Não há alerta sobre o STF, Tema 506 (RE 635.659, 26/06/2024): portar maconha para consumo pessoal não é infração penal | STF, Tema 506; Lei 11.343/2006, arts. 28 e 30 | Perde-se o pedido mais forte; a condenação pode seguir como base de reincidência | Aviso em todo crime do art. 28 ("se a droga era maconha, conferir o Tema 506"); não usar o art. 28 como base de reincidência sem esse aviso | Fundamento (lacuna) | Média | Sim: como tratar o art. 28 como base de reincidência nas outras linhas |
| 12 | Prazo pela pena aplicada sem evasão (8.6) | A regra está de acordo com o STF e o STJ, mas não traz o quadro de ponto discutível | Corrente favorável: art. 113 por analogia. STF: contrário (HC 236.292, 2025). STJ: contrário (RHC 67.403; AgRg no HC 751.110; AgRg no HC 847.217). TJMS: não localizado | Nenhum no cálculo | Incluir o quadro "Ponto discutível" no relatório e na memória | Tese discutível | Baixa | Não |
| 13 | Revogação do livramento — termo inicial (8.7) × sursis (8.8) | No sursis, o programa pede para conferir a data do trânsito da decisão que revoga; no livramento, usa a data da decisão, sem aviso. As duas regras vêm do mesmo art. 112, I | CP, art. 112, I; STJ, AgRg no HC 514.499 (sursis: contou da data da revogação) | A data usada é a favorável; o Ministério Público pode sustentar o trânsito | Harmonizar: usar a data da decisão e mostrar a hipótese do trânsito (A VERIFICAR) quando decidir | Tese discutível | Baixa | Sim: qual data adotar nos dois casos |

### Observação sobre uma escolha já decidida

No saldo zero com várias condenações (8.7), o capítulo diz que a tese vai à aba Extinção quando a ordem do trânsito e o art. 76 zeram o saldo. Isso parece conflitar com a escolha "na execução unificada, não se sugere a extinção de uma pena isolada". **Decisão sua:** confirmar se essa exceção é desejada.

## Pontos já conhecidos

| Ponto | Situação |
|---|---|
| Art. 366 sem data de fim: a suspensão é somada depois da sentença | Confirmado — erro de resultado (achado 1) |
| Diferença de 1 dia no dia final entre somas parecidas | Confirmado — erro de resultado raro (achado 4) |
| A revogação do livramento é descrita como fuga | Confirmado — só texto (achado 5) |
| Saldo zero aparece com "interrompe (art. 117, V)" | Confirmado — só texto (achado 6) |

## Não confirmado

- **TJMS, 0000230-65.2010** (citado para a ordem cronológica do trânsito): não localizado no JusRatio.
- **Lei 15.402/2026:** texto não localizado na base consultada. A data de 08/05/2026 e o conteúdo (progressão) vêm só do código.
- **Lei 12.234/2010 — data de publicação:** a lei é de 05/05/2010 e entrou em vigor na publicação. A data de 06/05/2010 usada no programa não pôde ser conferida no DOU.
- **Resolução CNJ 391/2021** (leitura: 4 dias por obra, até 12 por ano): não reconferida.
- **Posição do STF e do TJMS** sobre o livramento, o aberto e a domiciliar por outra pena (achado 3b) e sobre o art. 113 por analogia (achado 12): não localizada. Não se afirma que não exista.
- **Pertinência fraca ou imprópria:** STJ, Tema 1.367 (achado 3a); TJMS, 1603205-53.2026.8.12.0000 (trata de regime aberto descumprido e da pandemia, não diretamente do "último comparecimento"); STJ, Súmula 527 (achado 10).

## Próximo passo

A segunda etapa depende da sua aprovação. Para cada achado aprovado: correção num branch próprio, com um teste de caso fictício por correção e a rodada completa de `python3 testes.py`. O PR só será aberto quando você pedir. Ordem sugerida: 1, 2, 3a/3b e 11; depois os de prioridade baixa num bloco só.
