# Revisão jurídica — Capítulo 9 (Extinção)

- **Relatório revisado:** APTO, relatório técnico-jurídico, aba Extinção, versão 7.14.7 (outubro de 2026).
- **Código conferido:** versão 7.14.7 (80 testes passando). Em 05/11/2026, os erros A1, A2, A3 e A7 e a falta do Tema 1.367 (A4) foram reconferidos na versão 7.15.1 (`main`, commit 0ed0b1a) e continuam presentes.
- **Lei e jurisprudência:** vigentes em outubro de 2026, conferidas no JusRatio.
- **Etapa:** só revisão. Nenhuma alteração no código. Todos os casos de teste são fictícios; não há dados de assistidos.
- **PDF do relatório:** [cap9-extincao.pdf](cap9-extincao.pdf)

## Resumo

| Item | Quantidade |
|---|---|
| Regras revisadas | 19 |
| Corretas | 11 (2 delas com reflexo de achado de outra regra ou aba) |
| Regras com achado | 8 |
| Achados | 10 |
| Erro de resultado | 3 (A1, A2, A3) |
| Erro de fundamento ou citação | 1 (A4) |
| Erro só de texto | 3 (A7, A8, A9) |
| Tese discutível | 3 (A5, A6, A10) |

### Pontos que já eram conhecidos

| Ponto | Conclusão |
|---|---|
| Art. 366 sem data de fim: a suspensão é somada depois da sentença | **Confirmado** (A2, erro de resultado) |
| Diferença de 1 dia no dia final entre somas parecidas | **Descartado como erro de conta.** A soma do período de prova está certa nesse ponto; o quadro do relatório explica mal (A9). A diferença real é outra, de até 6 dias (A1) |
| Revogação do livramento descrita como fuga | **Confirmado em parte.** A aba Extinção já usa o termo certo; o erro continua em textos da Prescrição e da Auditoria (A8) |
| Saldo zero com "interrompe (art. 117, V)" | **Confirmado** (A7, texto) |

### Leis recentes

As Leis 14.843/2024, 15.358/2026 e 15.402/2026 e as mudanças do art. 112 da LEP tratam de progressão, exame criminológico, saídas e remição. Nenhuma delas muda as hipóteses de extinção deste capítulo.

## Achados

A coluna "Decisão sua?" indica se a correção depende de uma escolha da equipe ("sim") ou se é correção técnica sem margem de escolha ("não").

| # | Regra | Problema | Fundamento | Efeito para o assistido | Correção proposta | Tipo | Prioridade | Decisão sua? |
|---|---|---|---|---|---|---|---|---|
| A1 | Livramento: revogação depois do período de prova (Súmula 617) e livramento incerto; reflexo no término calculado e em "preso em outro processo" | Ao transformar um saldo em dias em anos, meses e dias, o resto de 360 a 364 dias vira "12 meses e 0 a 4 dias", mais de um ano, em vez de "11 meses e 25 a 29 dias" (regra que o próprio programa usa para escrever penas). No exemplo do relatório (pena de 4 anos, presa de 01/02/2021 a 01/02/2023, livramento em 01/02/2023), o fim do período de prova sai 05/02/2025; pela conta do SEEU (4a − 2a0m1d = 1a11m29d) o fim é 30/01/2025, a mesma data que o programa dá como término no mesmo caso. Caso fictício com revogação decidida em 03/02/2025: a hipótese da Súmula 617 não aparece. | CP, art. 90; LEP, art. 146; Súmula 617/STJ (vigente); convenção de contagem do SEEU adotada pela equipe | Revogação ou suspensão decidida até 6 dias depois do fim real do período de prova é tratada como tempestiva, e a extinção deixa de ser apontada. O término calculado pode sair até 5 dias mais tarde | Converter o saldo do mesmo modo que o programa escreve penas (resto de 360–364 dias = 11 meses e 25–29 dias) ou, melhor, calcular o saldo do período de prova em anos, meses e dias, como o SEEU (pena da época − cumprido no deferimento). Corrigir o exemplo do relatório (fim em 30/01/2025). Teste: o caso do exemplo com revogação em 03/02/2025 deve dar "Extinção cabível" | Erro de resultado | Alta | Sim: escolher entre as duas formas de conversão |
| A2 | Prescrição (reflexo na aba Extinção): art. 366 do CPP | Sem a data de fim da suspensão, o programa a considera em curso até hoje e soma esses dias também aos trechos sentença → acórdão → trânsito. O texto diz "(ainda suspenso)" mesmo com trânsito em julgado | CPP, art. 366 (a suspensão cessa com o comparecimento do réu, antes da sentença); teto pela pena máxima: Súmula 415/STJ; STF, Tema 438 (RE 600.851) | O prazo da prescrição punitiva (retroativa e intercorrente) fica alongado e pode esconder uma prescrição já ocorrida | Sem data de fim, limitar a suspensão ao marco processual seguinte (no máximo a sentença), nunca somá-la a trechos posteriores, e marcar "a verificar: informe a data em que o processo voltou a correr". Trocar "(ainda suspenso)" por "sem data de fim informada". Teste: suspensão sem fim, anterior à sentença, não altera o trecho sentença → trânsito | Erro de resultado | Alta | Não |
| A3 | Término do SEEU já alcançado | A regra não verifica se a execução foi interrompida antes do término. Caso fictício: fuga em 01/03/2024 e término impresso em 31/01/2025 → "Extinção cabível", vermelho, prioridade crítica | LEP, art. 66, II; CP, art. 113 (na fuga, conta-se o saldo) | Falso "cabível": petição de extinção indevida e prioridade errada; o ponto real (saldo na fuga, prescrição pelo saldo) fica em segundo plano | Se houver interrupção posterior ao último início de cumprimento e anterior ao término impresso, não afirmar a extinção: "A verificar: término do SEEU anterior à interrupção de &lt;data&gt;". Teste com o caso fictício acima | Erro de resultado | Média | Sim: confirmar se o SEEU imprime término nessa situação |
| A4 | Livramento (três regras); preso em outro processo; detração por prisão em outro processo | O programa não considera o STJ, Tema 1.367 (REsp 2.200.477, Terceira Seção, j. 07/05/2026, DJEN 12/05/2026): "o cumprimento de pena relativa a delito praticado no curso de livramento condicional terá como seu termo inicial o dia subsequente ao fim do período de prova, dada a impossibilidade de cumprimento simultâneo de duas penas não unificadas" | Tema 1.367/STJ; CP, arts. 42 e 90; LEP, art. 111; Súmula 617/STJ | Nesta execução, a prisão por novo crime não impede, sozinha, a extinção; o programa a trata como dúvida e só marca "a verificar". Na execução nova, o programa pode sugerir detração de período que o STJ não admite | Nas regras do livramento, explicar que a prisão por outro crime não suspende o livramento (Súmula 617; Tema 1.367) e manter "a verificar" só pela falta de dado sobre decisão de suspensão. Nas regras de prisão em outro processo e detração, não propor detração de período em que a pessoa estava em livramento não suspenso de outra execução; citar o Tema 1.367 | Erro de fundamento | Média | Não |
| A5 | Livramento incerto; livramento em curso com término alcançado | A ressalva "observado o art. 89 do CP" é apresentada sem a leitura dominante: o art. 89 não prorroga o período de prova automaticamente | Súmula 617/STJ; STJ, AgRg no HC 972.875 (5ª T., 14/04/2025); HC 558.474 (5ª T., 2020); STF, HC 119.938 (1ª T., 2014) | O leitor pode deixar de pedir a extinção por haver processo pendente, embora ela seja devida se não houve suspensão decidida no período | Redação: "o art. 89 só impede a extinção se o juiz suspendeu o livramento antes do fim do período de prova (Súmula 617/STJ); processo pendente, sozinho, não prorroga" | Tese discutível | Média | Sim: redação da ressalva |
| A6 | Detração que cobre a pena do processo (exclusiva) | Afirma "Extinção cabível" (vermelho) da pena de um processo mesmo quando a execução tem outras penas ativas, contra a escolha da equipe de não sugerir extinção de pena isolada na execução unificada. Também não sabe se a mesma prisão já foi usada em execução de outra comarca | CP, art. 42; LEP, arts. 66, II, e 111; escolha de política da equipe | Na execução unificada, a extinção isolada pode ser negada (o tempo já está na pena unificada); risco de petição sem efeito | Com outras penas ativas, rebaixar para "a verificar", alinhado à política; com condenação única, manter vermelho. Ou registrar expressamente a exceção à política | Tese discutível | Baixa | Sim: manter a exceção ou alinhar à política |
| A7 | Pena já cumprida na fuga / prescrição (saldo zero) | Com saldo zero, a linha da fuga termina em "recaptura em &lt;data&gt; → interrompe (art. 117, V)" e "não prescrita", como se a pena seguisse em curso | CP, arts. 113 e 117, V; LEP, art. 66, II | Texto contraditório com a hipótese de extinção; pode levar a pedir a prescrição em vez da extinção pelo cumprimento, ou a não pedir nada | Com saldo zero: "recaptura em &lt;data&gt; — sem efeito sobre esta pena, já cumprida na fuga (ver aba Extinção)" | Erro só de texto | Média | Não |
| A8 | Pena já cumprida na fuga (textos da Prescrição e da Auditoria) | Quando a interrupção é revogação do livramento, ainda aparecem "saldo calculado zero na fuga de…", "condenações em execução na fuga", "informe a pena remanescente na fuga", "a fuga durou…". A aba Extinção já usa "revogação do livramento" | CP, art. 113 (fuga ou revogação do livramento) | Petição com fato errado (atribuir fuga a quem teve o livramento revogado) | Usar o nome do evento (fuga, abandono, revogação do livramento, interrupção) em todos esses textos | Erro só de texto | Baixa | Não |
| A9 | Livramento: revogação depois do período de prova (quadro "Ponto discutível" do relatório) | O quadro diz que a soma "não desconta o dia do começo", ao contrário de outras somas. A conta está certa: o dia do deferimento já está na pena cumprida (os 731 dias incluem 01/02/2023), então o saldo começa no dia seguinte. As outras somas tiram 1 porque o primeiro dia é o da própria prisão | CP, art. 10 | Nenhum no resultado; induz o auditor a "corrigir" o que está certo | Reescrever o quadro no relatório e remeter à diferença real (A1) | Erro só de texto | Baixa | Não |
| A10 | Livramento incerto | A "prisão depois do deferimento" vira indício de que o livramento terminou, e a hipótese fica sempre amarela | Súmula 617/STJ; Tema 1.367/STJ; TJMS: 1ª Câm. Crim., 1607270-28.2025.8.12.0000 (28/11/2025) e 3ª Câm. Crim., 1602357-71.2023.8.12.0000 (02/08/2023) aplicam a Súmula 617; 2ª Câm. Crim., 1413300-34.2023.8.12.0000 (30/08/2023) nega quando houve suspensão a tempo | Amarelo onde, sem decisão de suspensão no RSPE, a corrente dominante dá extinção | Manter amarelo (o RSPE pode não trazer a suspensão), mas pedir no texto a conferência específica: "houve decisão de suspensão antes de &lt;fim&gt;? Se não, extinção (Súmula 617)" | Tese discutível | Baixa | Sim: manter amarelo ou não |

### Teses discutíveis: posições

**A5 e A10 — art. 89 do CP e prisão durante o livramento**
- Corrente favorável ao assistido: sem suspensão ou revogação decidida antes do fim do período de prova, a pena está extinta; o processo por crime cometido no livramento não prorroga o prazo automaticamente.
- STJ: pacífico nesse sentido (Súmula 617; AgRg no HC 972.875; HC 558.474; AgRg no HC 731.254, 6ª T., 2023). O Tema 1.367 (2026) confirma a extinção e fixa o início da pena nova no dia seguinte ao fim do período de prova.
- STF: HC 119.938, 1ª T., 2014 — extinção quando não houve suspensão nem revogação no período de prova.
- TJMS: aplica a Súmula 617 (1ª e 3ª Câmaras Criminais, acórdãos acima); nega a extinção quando a suspensão foi decidida a tempo (2ª Câmara Criminal).

**A6 — extinção pela detração de uma pena dentro da execução unificada**
- Corrente favorável: a pena do processo cuja prisão provisória a cobre está cumprida e pode ser declarada extinta, com reflexo no prazo da reincidência (CP, art. 64, I).
- STJ, STF e TJMS: não pesquisados (ver abaixo).

## Regra por regra

| Nº | Regra | Conclusão | Exemplo refeito |
|---|---|---|---|
| 1 | O que a aba lê (cumprida = total − remanescente) | Correta | 4a − 4m = 3a8m ✔ |
| 2 | Extinções registradas no RSPE | Correta | Coerente com o código |
| 3 | Pena integralmente cumprida | Correta | ✔ |
| 4 | Término do SEEU já alcançado | A3 | 55 dias ✔; caso com fuga dá falso "cabível" |
| 5 | Término calculado pelo programa | Correta (sujeita a A1 quando o saldo cai em 360–364 dias) | 20/02/2027 ✔; 30/12/2025 ✔ |
| 6 | Extinção parcial | Correta | 31/01/2025 e 28/02/2027 ✔ |
| 7 | Livramento: revogação depois do período de prova | A1, A4, A9 | Relatório 05/02/2025; conta do SEEU 30/01/2025 |
| 8 | Livramento com situação incerta | A1, A4, A5, A10 | Mesmo desvio de A1 |
| 9 | Livramento em curso com término alcançado | A5 | ✔ |
| 10 | Detração que cobre a pena | A6 | 395 dias = 1a1m ✔ |
| 11 | Pena já cumprida na fuga | A7, A8 (AgRg no REsp 1.858.048 conferido) | 371 dias ≥ 1 ano ✔ |
| 12 | Detração por prisão em outro processo | A4 | — |
| 13 | Preso em outro processo, execução suspensa | A4 | 31/01/2024 ✔ |
| 14 | Indulto | Correta (escolha da equipe) | ✔ |
| 15 | Prescrição (reflexos) | Correta nesta aba; A2 na aba Prescrição | ✔ |
| 16 | Execução arquivada | Correta | ✔ |
| 17 | Limite do art. 75 | Correta (escolha da equipe; Súmula 715/STF conferida) | 31/12/2040 ✔ |
| 18 | Situação e cor | Correta | 45 e 80 dias ✔ |
| 19 | Prioridade | Correta | ✔ |

## Não confirmado

- **Lei 15.358/2026:** não encontrada no JusRatio. O programa a descreve como lei de progressão (hediondos, feminicídio, milícia, a partir de 25/03/2026). Não há indício de efeito sobre a extinção, mas o texto da lei não foi conferido.
- **Lei 15.402/2026:** a íntegra no JusRatio aparece incompleta (incisos do art. 112 marcados como fora de vigor). As partes visíveis (art. 112 e remição em prisão domiciliar, § 9º) não mudam este capítulo; conferir a redação final no capítulo de Progressão.
- **A3:** não sei se o SEEU imprime término quando a execução está interrompida por fuga. Na amostra da versão 7.14.6, a aba Extinção não teve erro, o que sugere que o caso é raro.
- **A6:** posições do STJ, do STF e do TJMS sobre extinção isolada pela detração na execução unificada.
- **Regras 18 e 19:** exemplos conferidos à mão; não rodei todas as combinações de cor e prioridade no programa.
- Não refiz conferências de casos reais.

## Referências conferidas no JusRatio

Súmula 617/STJ; REsp 2.200.477 (Tema 1.367/STJ); AgRg no HC 972.875; HC 558.474; AgRg no HC 731.254; STF, HC 119.938; TJMS 1607270-28.2025.8.12.0000, 1602357-71.2023.8.12.0000 e 1413300-34.2023.8.12.0000; Súmula 415/STJ; STF, RE 600.851 (Tema 438); AgRg no REsp 1.858.048; Súmula 715/STF; Lei 15.402/2026.

## Próximo passo

Aguarda aprovação. Sugestão de ordem: A1 e A2 → A3, A4, A5, A7 → A6, A8, A9, A10. Cada correção aprovada vai para um branch próprio, com teste fictício, e `python3 testes.py` roda antes de qualquer PR.
