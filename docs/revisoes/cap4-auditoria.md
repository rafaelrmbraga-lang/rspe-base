# Revisão jurídica — Capítulo 4 (Auditoria) — APTO 7.14.7

- Revisão feita em 27/10/2026, com a lei vigente em outubro de 2026.
- Código revisado: versão 7.14.7, base jurídica 2026-10-08i, commit `04bd716`. A `main` já está na 7.15.1: conferir se algum achado foi resolvido antes de corrigir.
- Etapa: só revisão. Nenhum código foi alterado.
- Relatório completo em PDF: [cap4-auditoria.pdf](cap4-auditoria.pdf).
- Só foram usados casos fictícios. Nenhum nome real e nenhum dado de assistido.

## Resumo

| Item | Quantidade |
|---|---|
| Regras revisadas (subtítulos de 4.1 a 4.14) | 69 |
| Corretas | 49 |
| Com erro de resultado | 3 |
| Com erro de fundamento ou citação | 8 |
| Com erro só de texto | 4 |
| Tese discutível, sem erro | 5 |
| Achados | 18 (2 de prioridade alta, 6 média e 10 baixa) |

Cada regra foi contada uma vez, pelo achado mais grave.

Os 7 pontos já conhecidos foram todos confirmados:

| Ponto conhecido | Achado |
|---|---|
| 1/6 × 16%: citação deformada e falta o parágrafo do prejuízo | A2 e A3 |
| "4/25" | A10 |
| "incidente de somatório ()" | A11 |
| Divergência de nascimento duplicada | A8 |
| CPF inválido da ficha como alerta | A7 |
| Data-base do livramento só testada com fuga | A1 |
| Custódia contada sem o dia final | A9 |

## Achados

Coluna "Decisão sua?": **sim** quando a correção depende de uma escolha sua antes de ser aplicada.

| # | Regra | Problema | Fundamento | Efeito para o assistido | Correção proposta | Prioridade | Tipo | Decisão sua? |
|---|---|---|---|---|---|---|---|---|
| A1 | 4.3 Data-base do livramento (Súmula 441) | A coincidência entre a data-base do livramento e a da progressão só é testada quando a execução tem fuga ou descumprimento. Sem esse evento, nenhum aviso sai. Caso rodado: início em 10/01/2020; progressão e data-base do livramento em 01/03/2023; sem item. | CP, art. 83; Súmula 441/STJ; STJ, Tema 709. A progressão não é marco do livramento. | Livramento atrasado sem aviso. No caso rodado (pena de 9 anos, 1/3): cerca de jan/2023 pela lei e mar/2026 pelo SEEU. | Tirar a exigência de fuga. Alertar quando a data coincide com progressão, regime ou soma. Teste com o caso rodado. | Alta | Resultado | **Sim**: quando a data coincide com nova prisão depois de soltura, não alertar ou usar "verificar"? A 5ª Turma admite a última prisão (AgRg no REsp 2.263.217). |
| A2 | 4.14 e 4.6 Fundamentação dos percentuais de progressão | (a) 1/6 × 16%: sai "STJ, Temas 1084, 1196, 1354, 2.037.377, 18, 06 e 2026". (b) Em todo alerta de percentual, o "Nesse sentido" cita os Temas 1084 e 1196 do STJ e o Tema 1169 do STF (hediondo de reincidente genérico), mesmo em crime comum. (c) O 1º parágrafo traz a orientação "pedir a retificação do cálculo". | O pertinente para fração por condenação e retroatividade é o Tema 1354/STJ (REsp 2.037.377/SC, 3ª Seção, 18/06/2026). | Petição com citação errada ou fora do caso. | Ler "REsp nº/UF, órgão, data" como um único precedente. Citar conforme o perfil: crime comum, Tema 1354 e CF, art. 5º, XL; hediondo de reincidente genérico, Temas 1084 e 1169; com morte, Tema 1196. Tirar a orientação ao operador. | Alta | Fundamento | Não |
| A3 | 4.14 Fundamentações prontas | 16 dos 81 textos saem sem o 3º parágrafo (prejuízo). Entre eles: 1/6 × 16%, detração lançada como remição, unificação usada como soma, pena cumprida menor que a custódia, livramento 1/1 pela revogação, "marcado reincidente desmentido pelas datas", comutações fora de ordem e remição tardia. | O próprio 4.14 prevê o parágrafo do prejuízo concreto. | Peça sem o dano concreto. | Escrever o prejuízo de cada tipo. Teste: todo tipo com texto pronto gera o 3º parágrafo. | Média | Texto | Não (revisar a redação depois) |
| A4 | 4.3 Regime inicial depois da 1ª prisão; nova prisão depois de soltura | O texto diz que a 5ª Turma "reserva a primeira [prisão] para livramento, indulto e comutação". | A 5ª Turma fixa a última prisão para progressão **e livramento**: AgRg no REsp 2.263.217 (24/06/2026); AgRg no REsp 2.248.958 (09/09/2026); AgRg no AREsp 3.222.593 (06/10/2026). | Argumento sem respaldo; pedido de livramento pela 1ª prisão com base errada. | Reescrever a frase e citar os três acórdãos. | Média | Fundamento | Não |
| A5 | 4.3 (as mesmas regras de A4) | Não menciona o Tema 1457/STJ, afetado no REsp 2.266.131 (data-base com prisão descontínua: 1ª prisão cautelar ou retorno à prisão). | STJ, Tema 1457 (afetado, sem tese). | A tese firmada vai valer para todos esses casos. | Citar no fundamento e no "Ponto discutível"; rever a regra depois do julgamento. | Média | Fundamento | **Sim**: manter a regra atual até o julgamento ou rebaixar para "verificar"? |
| A6 | 4.3 Fundamentação do regime inicial | A peça cita o AgRg no REsp 2.248.958 (5ª T.) como apoio à detração depois da fração. A ementa diz que a custódia "deve ser deduzida do total da reprimenda", frase que pode ser lida como a conta gravosa. | 6ª T.: AgRg no HC 719.763 e AgRg no AREsp 2.956.206. TJMS em 2026, favorável: 1ª Câm., 1602525-68, 1603757-18 e 1605123-92; 3ª Câm., 1604202-36 (01/10/2026). Contrário: 3ª Câm., 1600716-43 (20/03/2026). | Risco de o precedente ser usado contra o pedido. | Citar o 2.248.958 só para a data-base; apoiar a conta na 6ª Turma e no TJMS. | Média | Tese | **Sim**: estratégia de citação na peça |
| A7 | 4.12 Confronto com a ficha (CPF) | CPF com dígito inválido fica em alerta vermelho. O filtro de rebaixamento procura "CPF na ficha", mas o título do item é "CPF da ficha". | O próprio capítulo trata divergência de identidade como "verificar". | Estado "atenção" falso; ruído na triagem. | Corrigir o filtro. CPF inválido passa a "verificar", com "provável erro de digitação". | Média | Texto | Não |
| A8 | 4.11, 4.12 e 4.13 Nascimento divergente | Saem dois itens para a mesma divergência, com critérios diferentes de "muda marco" (um usa a data do computador). Só um recebe baixa automática. | CP, arts. 27 e 115; decretos de indulto. | Ruído; um item pode ficar aberto depois de resolvido. | Manter um item só, com o botão Preencher e a baixa automática. | Média | Texto | **Sim**: manter o item da divergência da fonte (4.13) ou o do confronto com a ficha (4.12)? |
| A9 | 4.4 Pena cumprida menor que a custódia; 4.10 Monitoramento | Os períodos são contados sem o dia final. | CP, art. 10; o resto do programa conta os dois dias (detração de outro processo: 192 dias). | Diferença subestimada perto do limite de 60 dias; monitoramento com 330 dias em vez de 331. | Usar a mesma contagem do resto do programa. Teste: de 01/01 a 31/01 dá 31 dias. | Baixa | Resultado | Não |
| A10 | 4.3 Regime inicial | "fração aplicada pelo SEEU (4/25)". | — | Texto confuso. | Escrever "16%". | Baixa | Texto | Não |
| A11 | 4.3 Data-base na soma | "incidente de somatório ()" quando falta o complemento. | — | Texto confuso. | Omitir os parênteses vazios. | Baixa | Texto | Não |
| A12 | 4.5 Indícios de falta | O Tema 1195 é citado para dizer que a falta "só produz efeitos depois de reconhecida". | Pelo Tema 1195 (Decreto 9.246/2017), vale a data em que a falta ocorreu, ainda que apurada depois, salvo inércia ou mora do Estado. Tese retificada em 10/06/2026. | Citação que não sustenta a frase; a ressalva favorável fica de fora. | Citar o tema para o que ele diz e usar a ressalva da mora estatal. | Baixa | Fundamento | Não |
| A13 | 4.5 Prescrição disciplinar | Não menciona o Tema 1126/STJ (prazo da prescrição da falta), afetado e sem tese. | As Turmas aplicam 3 anos: AgRg no HC 779.723; HC 527.625; AgRg no AREsp 2.208.674 (2025). | Nenhum hoje; risco se a tese mudar. | Citar no "Ponto discutível". | Baixa | Fundamento | Não |
| A14 | 4.8 Soma das penas × pena total | Cita o Tema 1106/STJ como fundamento geral. | O Tema 1106 trata da unificação de pena restritiva de direitos com pena de prisão. | Citação fora do caso. | Citar só quando houver pena restritiva convertida. | Baixa | Fundamento | Não |
| A15 | 4.6 1/6 × 16% | A diferença é calculada em dias (14 dias em 6 anos). Pela convenção de anos e meses (mês de 30 dias), são 15 dias. | Convenções de contagem do relatório. | 1 dia a menos no texto do prejuízo. | Calcular em anos, meses e dias. Teste: 6 anos dá 15 dias. | Baixa | Texto | Não |
| A16 | 4.3 Data-base do livramento | O título diz "coincide com a de falta grave" quando o marco é só fuga ou descumprimento, sem homologação. | Súmula 533/STJ; STF, Tema 941. | Afirma falta grave que pode não existir. | "coincide com fuga ou descumprimento lançado no RSPE". | Baixa | Texto | Não |
| A17 | 4.6 Pena acima do máximo (relatório) | O exemplo diz "1.005 dias" para 2 anos e 9 meses; são 1.000 dias. | — | Nenhum. | Corrigir o relatório. | Baixa | Texto | Não |
| A18 | Vários (atualização) | Precedentes que convém acrescentar. | 25% no reincidente: HC 947.647 (5ª T., 03/12/2024). Hediondez posterior: STF, 2ª T., HC 273.296 AgR (06/08/2026) e ARE 1.624.717 (14/10/2026). Crime a crime, contra: AgRg no HC 1.121.539 (6ª T., 08/10/2026) e AgRg no REsp 2.167.914 (5ª T., 2025). Indulto: o HC 1.076.656 aplica o Tema 1006 diretamente. | Peças mais atuais. | Atualizar a base jurídica. | Baixa | Correto (sugestão) | Não |

## Teses discutíveis

| Tese (regra) | Corrente favorável | STJ | STF | TJMS |
|---|---|---|---|---|
| Detração depois da fração (4.3) | Fração sobre a pena inteira; detração depois | 6ª T. favorável. A 5ª T. usa a última prisão como data-base. Tema 1457 pendente. | Não pesquisado | Maioria favorável em 2026; um acórdão contra (3ª Câm., mar/2026) |
| Reincidente em crime violento com anterior não violenta: 25% (4.6) | 25% | Favorável nas duas Turmas | Não pesquisado | Não pesquisado |
| Reincidente sem violência, fato desde 08/05/2026: III (20%) × IV (30%) (4.6) | 20% | Sem precedente encontrado | — | — |
| Hediondez posterior ao fato, no indulto e na comutação (4.6) | Data do fato | Data do decreto, segundo o programa (não conferido) | 2ª T. favorável | Não pesquisado |
| Reincidência aferida crime a crime (4.7) | Fração de primário no crime anterior ao 1º trânsito | Contra nas duas Turmas | Não pesquisado | Contra (1ª e 3ª Câm., 2026) |
| Indulto e comutação não criam data-base (4.3) | Mantém a data-base anterior | Favorável (HC 1.076.656, monocrática) | Não pesquisado | Não pesquisado |
| Art. 75 com fatos antes e depois de 23/01/2020 (4.9) | 30 anos para as penas dos fatos anteriores | Não pesquisado | Súmula 715 | Não pesquisado |
| Prescrição da falta: 3 anos; na fuga, conta da recaptura (4.5) | 3 anos | Pacífico nas Turmas; Tema 1126 pendente | — | Não pesquisado |

## Leis conferidas

- **LEP, art. 112, texto vigente:** caput 1/6; I 25%; II 30%; III 20%; IV 30%; V 70%; VI 75%; VI-A revogado; VII 80%; VIII 85%. Confere com a tabela do programa.
- **Lei 15.358/2026:** publicada no DOU de 25/03/2026 e em vigor na data da publicação. Confirmada.
- **CP, art. 83, texto vigente:** confere.
- **Decretos 12.338/2024 e 12.790/2025, art. 9º, § 2º, I:** lapsos pela metade para maiores de 60 anos. Confere.

## Pontos não confirmados

- Data de vigência da Lei 15.402/2026 (08/05/2026). O conteúdo aparece no texto vigente; a data não.
- Súmula Vinculante 26, Súmula Vinculante 56 e RE 641.320; STF, Tema 506.
- STF, Tema 1319: só aparece de forma indireta, na anotação do Tema 1196/STJ.
- TJDFT, Acórdão 1230029 (perda de remidos).
- Texto retificado do Tema 1195/STJ (embargos de 10/06/2026).
- Datas dos boletins de correção do SEEU: 15/05/2025; 15 a 19/09/2025; 31/10/2025; 30/07/2026.
- Datas de vigência das Leis 14.994/2024, 13.964/2019, 11.464/2007, 8.930/1994 e 12.234/2010: não pesquisadas.
- RIBUP-MS (Decreto Estadual 12.140/2006), art. 136.
- Posição do STF e do TJMS nas teses marcadas "não pesquisado".
