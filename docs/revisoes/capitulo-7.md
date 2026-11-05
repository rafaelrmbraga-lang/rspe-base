# Revisão jurídica do Capítulo 7 do relatório do APTO (versão 7.14.7)

Indulto e comutação: decretos de 2000 a 2021 e de 2023, decreto por decreto.

- Revisão feita em 27/10/2026, sobre a branch `main` da versão 7.14.7.
- Primeira etapa: só revisão. Nenhuma linha de código foi alterada.
- Foram usados apenas casos fictícios, sem nenhum dado real de assistido.
- Relatório completo em PDF: [capitulo-7.pdf](capitulo-7.pdf).

## Resumo

| Item | Quantidade |
|---|---|
| Regras revisadas | 53: as 34 regras comuns (7.1.1 a 7.1.34) e 19 blocos de decretos (7.3) |
| Regras corretas | 30: 17 regras comuns e 13 blocos de decretos |
| Erros de resultado | 12, sendo 4 de prioridade alta |
| Erros de fundamento ou citação | 3 |
| Erros só de texto | 6 |
| Teses discutíveis | 7 |

Uma mesma regra pode ter mais de um achado. Por isso, os 28 achados não coincidem com as 23 regras que não estão inteiramente corretas.

Tipos de achado: R = erro de resultado; F = erro de fundamento ou citação; T = erro só de texto; D = tese discutível.

A coluna "Depende de decisão" indica:

- **Não**: a correção decorre da lei, do texto do decreto, de precedente vinculante ou da regra do próprio programa;
- **Sim**: a correção envolve uma escolha que cabe ao responsável, como um ponto que antes era tratado como escolha de política, um critério de apresentação ou uma tese.

## Achados

| Nº | Tipo | Regra | Problema | Fundamento | Efeito para o assistido | Correção proposta | Prioridade | Depende de decisão |
|---|---|---|---|---|---|---|---|---|
| A1 | R | 7.1.3 e 7.1.4; decretos de 2000 a 2003, 2016, Dia das Mães de 2017 e 2018 | Nos decretos sem cláusula de detração, quem só teve prisão provisória até a data recebe "não cabe: não iniciou o cumprimento". O teste `teste_conf8_indulto.py` (caso 2) exige esse resultado para 2016. | STJ, Tema Repetitivo 1277 (REsp 2.069.773, j. 06/02/2025, transitado em julgado): a prisão provisória é computada nos requisitos de indulto e comutação de qualquer decreto (CP, art. 42). A regra antiga seguia o AgRg no RHC 141.638 (6ª T., 2021), superado pelo tema. | Deixa de apontar indulto ou comutação cabível. Caso fictício: furto qualificado de 4 anos e flagrante de 548 dias. No Decreto 8.940/2016 o programa dá "não cabe", mas o art. 3º, I exige 365 dias. | Contar a prisão provisória pelo próprio processo em todos os decretos, citando o Tema 1277 na nota. Ajustar o caso 2 de `teste_conf8_indulto.py`. | Alta | Não |
| A2 | R | Cap. 6 (análise detalhada) e 7.1.34; Decretos 12.338/2024 e 12.790/2025 (art. 5º) e 11.302/2022 | Ponto já conhecido, confirmado no código (`rspe_scraper.py`, linhas 5444 a 5461). Quem só teve prisão cautelar recebe "não se aplica: não iniciou o cumprimento". | Art. 5º dos dois decretos: deve ser computado "como pena cumprida [...] o período cumprido em prisão cautelar". Em 2022, que não tem a cláusula, vale o Tema 1277. | Deixa de apontar indulto ou comutação nos decretos mais usados hoje. | Tratar a prisão cautelar como pena cumprida, com a mesma nota usada no Decreto 11.846/2023. | Alta | Não |
| A3 | R | 7.3; Dia das Mães de 2017 (sem número) e de 2018 (Decreto 9.370) | A vedação a hediondos e tráfico vale só para o indulto. A comutação do art. 2º, I "cabe" para tráfico do caput. No caso fictício, o natalino de 2017 deu "impeditivo" para o mesmo crime. | Lei 8.072/1990, art. 2º, I, e CF, art. 5º, XLIII. A comutação é indulto parcial: STJ, HC 187.943 e REsp 345.809; STF, HC 103.618. | Aponta um benefício que a lei veda, levando a pedido inviável. | Fazer a vedação legal valer também para a comutação. A restrição própria do decreto (outro crime violento) fica como está. | Alta | Sim (era escolha de política) |
| A4 | R | 7.1.10; decretos de 2011 a 2015 (XIV, XV e XVI) e de 2023 (art. 2º, XIV) | Na hipótese "regime aberto ou livramento condicional", a hipótese falha para quem está em livramento se o RSPE registra um regime anterior, como uma progressão ao semiaberto. | Texto das hipóteses: "regime aberto, ou em livramento condicional". O livramento é uma alternativa autônoma. | Perde o indulto e fica só a comutação. Caso fictício no Decreto 7.873/2012: sem regime registrado, cabe o XIV; com a progressão de 2009 registrada, cabe só a comutação. | Em `hip_ok` (`rspe_decretos.py`), o livramento em curso na data atende a hipótese. A dúvida sobre o livramento continua tratada pela regra 7.1.26. | Alta | Sim (era escolha de política) |
| M1 | R | 7.1.20; Decreto 4.495/2002 | No crime violento, a janela da falta de 24 meses vale só para o indulto, e a comutação fica sem janela nenhuma. Caso fictício: roubo com falta grave homologada deu "Cabe – Comutação"; o mesmo caso com estelionato deu "não cabe". | Art. 3º, I: janela de 12 meses para os dois benefícios. Art. 1º, § 1º, I: 24 meses para o indulto do crime violento. | Aponta comutação vedada. | Usar 24 meses no indulto e 12 meses na comutação, com dois campos na ficha. | Média | Sim (era escolha de política) |
| M2 | R | 7.1.20; Decretos 6.294/2007 e 8.940/2016 | A fuga sem apuração nem homologação é tratada como falta firme, com resultado "não cabe". | STJ, Súmula 533 e Tema 652; STF, Tema 941. O Decreto 8.940/2016, art. 9º, parágrafo único, manda adiar a declaração até a apuração. | Dá "não cabe" firme a quem pode ter direito. | Tratar a fuga sem homologação como "a verificar" em todos os decretos. | Média | Sim (critério da fuga) |
| M3 | R | 7.1.12; Decreto 9.246/2017, art. 1º, IV, e as demais hipóteses por sexo | Sexo não informado é tratado como masculino. Caso fictício: sem sexo, "faltavam 4 dias para 1/4"; com sexo feminino, cabe com 1/6. | Texto das hipóteses e regra do próprio programa (sem o dado, "a verificar"). | A mulher sem o sexo cadastrado perde a hipótese mais favorável. | Com sexo vazio e a hipótese das mulheres atendida, dar "a verificar: sexo não informado". | Média | Não |
| M4 | R | 7.1.28 | A remição pendente só é comparada com o que falta para o indulto. Se ela cobre só o que falta para a comutação, o "não cabe" continua. | LEP, art. 128. | A comutação cabível não aparece. | Comparar também com o que falta para a comutação e dar "a verificar (remição pendente)". | Média | Não |
| M5 | R | 7.1.34 (execução iniciada depois do decreto) | Nesse caminho, o tráfico sem indicação de caput, § 1º ou § 4º é tratado como impeditivo firme. No caminho normal, fica "a verificar" (regra 7.1.15). | Regra 7.1.15; LEP, art. 112, § 5º; STF, HC 118.533. | Dá "impeditivo" a quem pode ter tráfico privilegiado. | Passar a lista de dúvidas também nesse caminho. | Média | Não |
| B1 | R | 7.1.17; Decreto 8.940/2016 | O programa procura "praticado após" no singular, mas o decreto diz "praticados após". | Decreto 8.940/2016, art. 2º, III. | Um "cabe" vira "a verificar" sem necessidade. | Aceitar o singular e o plural. | Baixa | Sim (era escolha de política) |
| B2 | R | Cap. 6; Decreto 11.302/2022, art. 4º (ponto já conhecido) | Usa 1/3 exato, sem arredondar (pena ÷ 3,0). Os demais decretos arredondam o exigido para baixo. | Regra 7.1.8 do próprio programa; `rspe_scraper.py`, linhas 3852, 3865 e 3869. | Pode exigir 1 dia a mais no limite. | Usar a mesma conta inteira dos demais decretos, arredondada para baixo. | Baixa | Não |
| B3 | R | 7.1.14; 2012 (XVI), 2013 e 2014 (XVII), 2015 (XVIII), 2017 (VII) | O piso de pena "superior a dezoito meses" não é conferido. | Texto das hipóteses. | Gera "a verificar" indevido; não prejudica o resultado. | Conferir pena maior que 540 dias. | Baixa | Sim (era escolha de política) |
| F1 | F | 7.1.2 e 7.1.34 | Os precedentes AgRg no HC 441.551 e AgRg no HC 919.210 tratam de quais penas entram na soma pelo trânsito em julgado, não da sentença posterior à publicação. | STJ, AgRg no HC 894.488 (5ª T., 29/04/2024) trata diretamente da condenação proferida depois da publicação. | Deixa a citação fraca. | Citar o AgRg no HC 894.488 como precedente principal. | Baixa | Não |
| F2 | F | 7.1.17 | Cita "STF, 2ª Turma" sem número do precedente, e não cita o STJ. | STF, RHC 267.297 AgR (2ª T., 16/03/2026). STJ, AgRg no HC 1.076.488 (5ª T., 19/08/2026) e AgRg no HC 1.087.914 (6ª T., 11/06/2026). | O texto fica sem precedente verificável. | Incluir os números dos precedentes. | Baixa | Não |
| F3 | F | 7.1.28 e 7.1.20 | (a) O HC 1.089.923 é uma decisão monocrática. (b) O Tema 1195 é usado sem a ressalva de inércia ou mora do Estado. | STJ, HC 1.089.923 (decisão monocrática de 11/06/2026). Tema 1195 (tese retificada em 10/06/2026). | (a) A citação é imprecisa. (b) Omite um argumento da defesa. | Citar como decisão monocrática e acrescentar a ressalva da inércia estatal. | Baixa | Não |
| T1 | T | 7.1.8, 7.1.9, 7.1.14 e a exibição em anos, meses e dias (ponto já conhecido) | Restos de 360 a 364 dias aparecem como "11 meses e 25 a 29 dias", e a conta não fecha. Exemplo: 5.838 dias aparecem como 15a11m28d; 1.455 dias, como 3a11m25d. "15 anos" aparece como "exigido 15a0m4d". | Convenção do SEEU, que é escolha de política. O problema está só na exibição (`rs.dias_para_pena`). | O tempo cumprido pode aparecer até 5 dias menor no texto e na petição. | Mostrar também o total em dias, ou exibir o resto como "12m0d" a "12m4d". | Média | Sim (formato de exibição) |
| T2 | T | 7.1.7; `avaliar_ficha` e `mesclar_por_requisito` (ponto já conhecido) | Quando a âncora do SEEU e os eventos empatam em "a verificar", vale a conta da âncora, mesmo que a conta pelos eventos tenha inciso atendido. | Regra 7.1.7. | O texto fica contraditório. | No empate, ficar com a versão que tem mais hipóteses atendidas. | Média | Sim |
| T3 | T | 7.1.32 | Um benefício "Concedido" ou "Indeferido" mostra o dispositivo que resultou da conta, e não o da decisão. | — | Texto e prioridade ficam enganosos. | Limpar o dispositivo ou trocá-lo por "conforme decisão do RSPE". | Baixa | Sim (era escolha de política) |
| T4 | T | 7.1.24 | A ressalva sobre comutações anteriores aparece em decreto "impeditivo" e identifica o decreto só pelo ano. | — | Texto confuso. | Não exibir a ressalva no impeditivo e usar o número do decreto. | Baixa | Não |
| T5 | T | 7.1.33 | No decreto restrito de 2019, com falta firme, o motivo mostrado é a falta, e não o próprio decreto restrito. | — | Nenhum efeito no resultado. | Mostrar primeiro o motivo do decreto restrito. | Baixa | Não |
| T6 | T | Cap. 6 e 7.1.34 (ponto já conhecido) | Na tabela da aba, a comutação continua "prejudicada" depois que o indulto é rebaixado. | Decretos de 2024 e 2025, art. 13, § 5º. | Pequeno, porque a falta também alcança a comutação. | Usar o resultado guardado em `_se_indeferido`. | Baixa | Não |

## Teses discutíveis

| Nº | Regra | O que o programa faz | Corrente favorável ao assistido | STJ | STF | TJMS | Depende de decisão |
|---|---|---|---|---|---|---|---|
| D1 | 7.1.17: hediondez posterior ao fato | Afere a hediondez na data do fato e deixa "a verificar" | Irretroatividade da lei mais grave | Afere na data do decreto (AgRg no HC 1.076.488, AgRg no HC 1.117.779 e AgRg no HC 1.087.914) | 2ª Turma: irretroatividade (RHC 267.297 AgR) | Dividido: a 2ª Câmara aplica a irretroatividade (1604388-59.2026); a 1ª e a 3ª Câmaras aferem na data do decreto (1602236-38.2026 e 1604099-29.2026) | Sim |
| D2 | 7.1.15: Decreto 6.294/2007 e o § 4º | Trata o silêncio do decreto sobre o tráfico privilegiado como vedação ("impeditivo") | O tráfico privilegiado não é hediondo, logo deveria ficar "a verificar" | Não confirmado | Não confirmado | Não confirmado | Sim |
| D3 | 7.1.23: base da comutação de 2000 a 2002 | Calcula sobre a pena total (leitura literal, mais favorável) | A mesma do programa | Não confirmado | Não confirmado | Não confirmado | Sim |
| D4 | 2023, art. 2º, XIV | Trata a hipótese como indiferente à violência (leitura literal) | A mesma do programa | Não pesquisado | Não pesquisado | Não pesquisado | Sim |
| D5 | 7.1.1: hipóteses não aferidas | Essas hipóteses não mudam a cor da tabela | Sinalizar na tabela quando o resultado é "não cabe" | — | — | — | Sim |
| D6 | 7.1.18: imputação no concurso | Imputa o tempo pela fração exigida | A mesma do programa | Não pesquisado | Não pesquisado | A 1ª Câmara exige os 2/3 do crime impeditivo | Sim |
| D7 | 7.1.20: falta no dia da publicação | Inclui o próprio dia da publicação na janela | "Anteriores" exclui o dia da publicação | Não pesquisado | Não pesquisado | Não pesquisado | Sim |

## Pontos já conhecidos

| Ponto | Situação | Achado |
|---|---|---|
| Art. 5º dos decretos de 2024 e 2025: prisão cautelar | Confirmado | A2 |
| Empate entre âncora e eventos | Confirmado nos dois motores | T2 |
| A petição usa outra conta de tempo | Não confirmado. É provável, porque o campo `pena_cumprida_extenso` usa a pena cumprida na emissão do RSPE, mas o caso não foi reproduzido | — |
| Comutação "prejudicada" depois do rebaixamento do indulto | Confirmado em parte | T6 |
| Divergências entre os motores | Confirmado quanto à detração. Os demais casos não foram testados | A1 e A2 |
| Art. 4º de 2022 usa 1/3 exato | Confirmado | B2 |
| Restos de 360 a 364 dias na exibição | Confirmado | T1 |

## Pontos não confirmados

- **Lei 15.358/2026:** não foi localizada na base de legislação consultada.
- **Decretos de 2000 a 2021 e de 2023:** não houve acesso ao site do Planalto, então o texto oficial e as datas de publicação não foram conferidos na fonte. A conferência foi feita contra as fichas da base jurídica e contra os PDFs dos decretos de 2022, 2024 e 2025 que estão no repositório.
- **STF, HC 118.533:** não foi pesquisado nesta revisão. A regra que ele sustenta coincide com a LEP, art. 112, § 5º, que foi conferida.
- **Dia das Mães de 2017:** não foi possível confirmar se a falta grave e o requisito de não ter outro crime violento alcançam também a comutação.
- **Jurisprudência sem resultado:** a pesquisa não encontrou decisões sobre a base de cálculo da comutação nos decretos de 2000 a 2002, nem sobre o § 4º no Decreto 6.294/2007.
- **Petição:** a hipótese de que ela usa outra conta de tempo não foi reproduzida.
- **Divergências entre os motores:** não foram testadas a custódia por outro processo, a sentença registrada depois do trânsito e a condenação sem data de trânsito.
- **Tema 1195:** o inteiro teor da retificação feita em embargos (10/06/2026) não foi lido.
- **HC 1.089.923:** só a parte dispositiva da decisão foi lida.

## Lei vigente

- **Lei 15.402/2026:** altera só o art. 112 da LEP e os arts. 359-M-A e 359-M-B do CP. Não tem efeito sobre este capítulo.
- **Lei 14.843/2024:** trata de assuntos fora deste capítulo.
