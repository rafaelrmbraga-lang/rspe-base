# Revisão jurídica — Capítulo 6: Indulto e comutação (Decretos 11.302/2022, 12.338/2024 e 12.790/2025)

- **Objeto:** relatório técnico-jurídico do APTO, aba Indulto e comutação, Capítulo 6, e o código correspondente.
- **Versão revisada:** 7.14.7 (commit `04bd716`). Revisão concluída em 27/10/2026.
- **Reconferência rápida em 7.15.1** (commit `0ed0b1a`, 05/11/2026): os casos fictícios da revisão foram rodados de novo. A coluna "Situação em 7.15.1" diz o que se viu; "não reconferido" quer dizer que o item não foi testado de novo.
- **Etapa:** só revisão. Nenhum código foi alterado. Bateria de testes na 7.14.7: 80 de 80.
- **Dados:** só casos fictícios. Nenhum nome real.
- **Relatório completo em PDF:** [`cap6-indulto.pdf`](cap6-indulto.pdf).

## Resumo

| | Quantos |
|---|---|
| Regras revisadas | 107 |
| Regras sem achado | 82 |
| Regras com achado | 25 |
| Achados numerados | 24 (+3 observações de redação, item 25) |

| Tipo | Total | Alta | Média | Baixa |
|---|---|---|---|---|
| Erro de resultado | 11 | 1 | 6 | 4 |
| Tese discutível | 4 | 0 | 2 | 2 |
| Erro de fundamento ou citação | 6 | 0 | 0 | 6 |
| Erro só de texto | 3 | 0 | 0 | 3 |
| **Total** | **24** | **1** | **8** | **15** |

Dos 33 precedentes, súmulas e temas citados no capítulo, 27 dizem o que o programa afirma, 2 tratam de situação vizinha e 4 não foram confirmados. Nenhum foi superado.

### Leis citadas no pedido

| Lei | Efeito neste capítulo |
|---|---|
| Art. 112 da LEP (redação de 2026) | Não é usado pelos três decretos, que têm frações próprias. Sem efeito. |
| Lei 14.843/2024 | No inciso XI, as saídas temporárias usufruídas antes da lei continuam contando, e o programa conta todas até a data. Correto. |
| Lei 15.358/2026 | Novos hediondos e mudanças no art. 112. A hediondez é aferida na data de cada decreto (25/12/2024 e 25/12/2025), então não muda 2024 nem 2025. O decreto de 2026 vai precisar da data de início desses hediondos. |
| Lei 15.402/2026 | Não localizada no JusRatio. Efeito não confirmado. |

## Pontos já conhecidos

| Ponto | Situação na revisão | Achado |
|---|---|---|
| Art. 5º de 2024/2025: a prisão cautelar não conta | Confirmado | 1 |
| Empate entre âncora e eventos: vence a âncora | Confirmado | 3 |
| A petição usa outra conta de tempo | Confirmado | 4 |
| Comutação "prejudicada" depois que o indulto é rebaixado | Confirmado | 2 |
| Divergências entre o motor geral e a análise detalhada | Confirmado em parte | 5 e 6 |
| Art. 4º de 2022 usa 1/3 exato | Confirmado | 7 |
| Restos de 360 a 364 dias na exibição | Confirmado | 21 |

## Achados

Legenda da coluna **Decisão sua?**:
- **Sim:** a correção envolve escolha de tese ou de apresentação.
- **Não:** a correção decorre diretamente da lei ou da coerência do programa.

| Nº | Regra (seção) | Tipo | Problema | Fundamento | Efeito para o assistido | Correção proposta | Prioridade | Decisão sua? | Situação em 7.15.1 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Cumprimento em curso e início do cumprimento (6.2) | Erro de resultado | Quem teve só prisão cautelar e estava solto em 25/12 recebe "não se aplica: não iniciou o cumprimento" no indulto (salvo o XV) e na comutação. Caso fictício: porte de arma, pena de 2 anos e 153 dias de flagrante, deu "não se aplica" com 1/5 (146 dias) já cumprido. | Decretos 2024/2025, art. 5º (prisão cautelar computada como pena cumprida). STJ, 3ª Seção, Tema 1277 (REsp 2.069.773, 06/02/2025). A favor: TJMG, 4ª Câm., 0270269-38.2026; TJRJ, 3ª Câm., 5012600-44.2025; TJSP, 7ª Câm., 0002284-40.2025. Contra: STJ, 5ª T., AgRg no REsp 2.257.552 (exige início da execução no inciso VII); TJRS, 8001551-06.2026; TJBA, 2000080-84.2026. TJMS: posição não localizada. | Indulto e comutação deixam de ser apontados. Casos comuns: flagrante longo, liberdade na sentença, aberto não iniciado. | Contar a prisão cautelar e dar "A VERIFICAR (art. 5º; STJ, Tema 1277)", com nota da corrente contrária. Alinhar com o motor dos demais decretos, que já conta a detração. | Alta | Sim (adotar A VERIFICAR, e não POSSÍVEL) | Persiste (dois casos fictícios) |
| 2 | Prejudicada pelo indulto (6.11) e ordem das camadas (6.1) | Erro de resultado | As camadas de data de nascimento divergente e de custódia por outro processo rebaixam o indulto para A VERIFICAR, mas a comutação continua "prejudicada: indulto cabível". | Art. 13, § 5º: a comutação só cede ao indulto cabível. | A comutação some da aba. Caso fictício: com a data da ficha, a comutação seria POSSÍVEL. | Quando o indulto deixa de ser "POSSÍVEL", devolver a comutação sem o indulto, com "- se o indulto não couber (art. 13, § 5º)". | Média | Não | Persiste (nascimento divergente) |
| 3 | Âncora × eventos: decisão pelo requisito (6.3) | Erro de resultado | No empate em "a verificar", ficava a versão da âncora, mesmo quando a dos eventos tinha inciso atendido (o caso mostrava só "§ 2º, II a VI", e não o inciso I). | Regra do programa: mais pena cumprida nunca piora. Art. 9º, I. | O pedido sugerido vinha pela condição pessoal, e não pelo inciso I. | No empate, ficar com a versão com mais incisos atendidos. | Média | Não | **Corrigido**: o caso agora mostra "A VERIFICAR: art. 9º, I, XII, XIII" |
| 4 | Fundamentação para a petição (6.14) | Erro de resultado | A petição usa o total cumprido da exibição (âncora), e não o tempo que decidiu o resultado (eventos). | Coerência interna; o Cap. 11 já registra o ponto. | O pedido se contradiz: "exige 1 ano, 2 meses e 13 dias... foram cumpridos 1 ano, 1 mês e 5 dias". | Usar na petição o mesmo tempo da decisão; citar a âncora só como referência. | Média | Não | Persiste |
| 5 | Sentença registrada depois do trânsito (6.2) | Erro de resultado | A análise detalhada vale a data da sentença do RSPE e dá "sem condenação até 23/12", embora o trânsito seja anterior. O motor geral, com o mesmo dado, dá A VERIFICAR. | Dado incoerente (no júri, o "trânsito" pode ser o da pronúncia). | Benefício descartado por erro de lançamento. | Aplicar a regra do motor geral: condenação pelo trânsito anterior, com A VERIFICAR. | Média | Não | Não reconferido |
| 6 | Trânsito: condenação sem data de trânsito (6.2) | Erro de resultado | Sem data de trânsito e sem sinal de recurso, a condenação fica na soma. Se ela leva a "não atinge", não se faz a conta sem ela. | Decretos 2024/2025, arts. 2º e 7º. STJ, AgRg no HC 919.210 e AgRg nos EDcl no HC 991.402 (entram na soma as condenações transitadas para a acusação até a publicação). | Pena que talvez não entre na soma pode afastar o benefício. | Fazer também a conta sem essas condenações; se der o benefício, A VERIFICAR. | Média | Não | Não reconferido |
| 7 | Art. 4º do Decreto 2022 (6.9) | Erro de resultado | Compara com 1/3 exato, sem arredondar para baixo (também no 1/3 "dos demais" do art. 11). | Decreto 11.302/2022, art. 4º; critério uniforme do programa. | Até 1 dia a mais exigido. | Usar a fração em dias arredondada para baixo. | Baixa | Não | Persiste (código igual) |
| 8 | Falta grave: janela (6.8) | Erro de resultado | A janela começa em 25/12 do ano anterior, ou seja, 12 meses e 1 dia. Uma falta de 25/12/2024 impede o Decreto 2025. | Art. 6º ("doze meses... contados retroativamente a 25 de dezembro"); CP, art. 10. | Falta de um único dia por ano afasta o benefício. | Janela de 26/12 do ano anterior até a publicação. | Baixa | Sim (forma de contar os 12 meses) | Persiste (caso fictício) |
| 9 | Incisos VI e X: tempo no semiaberto (6.10) | Erro de resultado | O tempo é contado sem o dia do começo (exemplo do VI: 3.668 dias; com o dia do começo, 3.669). | CP, art. 10; convenções do relatório. | Um dia a mais exigido. | Contar com o dia do começo e corrigir o exemplo do relatório. | Baixa | Não | Persiste (código igual) |
| 10 | Incisos IX e X e o § 2º (6.10) | Erro de resultado | Os 2 anos do IX e os 3 anos do X não são reduzidos pela metade pelo § 2º. | Art. 9º, § 2º ("incisos I a XI"). | O X não aparece para quem tem 60 anos ou mais e está entre 1,5 e 3 anos no semiaberto. | Aplicar a metade ao IX e ao X e incluir o X no "a verificar" do § 2º, II a VI. | Baixa | Não | Persiste (código igual) |
| 11 | Art. 13: redução e base (6.11) | Erro de resultado | A proporção de 2/3 (§ 4º) só aparece pela idade. Para as demais pessoas do § 2º (II a VI) a comutação sai com 1/5, sem nota. | Art. 13, § 4º. | Redução de 1/5 em vez de 2/3 quando a condição existe e não está no RSPE. | Nota "? § 4º: se se enquadrar no art. 9º, § 2º, II a VI, a redução é de 2/3: X dias", sem mudar o status. | Média | Não | Persiste (código igual) |
| 12 | Comutação anterior e decretos sucessivos (6.11) | Tese discutível | A dispensa do requisito temporal (§ 2º) só vale para comutação anterior decidida até a data do decreto. | Art. 13, § 2º. Corrente favorável: a decisão é declaratória. Precedente específico não localizado (STJ, STF e TJMS). | Comutação negada a quem só não tinha a decisão anterior a tempo. | Aceitar a comutação de decreto anterior, qualquer que seja a data da decisão; A VERIFICAR (tese) quando a decisão for posterior. | Média | Sim | Persiste (código igual) |
| 13 | Inciso VIII: aberto ou livramento (6.10) | Tese discutível | O VIII é dado como POSSÍVEL também no regime aberto inicial. | Texto literal: favorável. Contra: STJ, 6ª T., AgRg no HC 1.060.635 (19/08/2026: no aberto inicial vale o VII, não o VIII); TJSE, 0028401-65.2025. STF e TJMS: não localizados. | Pedido apontado como certo pode ser negado. | Ressalva "aberto inicial: STJ aplica o VII, não o VIII"; A VERIFICAR quando o VIII for o único inciso. | Média | Sim | Não reconferido |
| 14 | Hediondez na data do decreto e tese da irretroatividade (6.5) | Tese discutível (programa correto) | A regra está bem aplicada, mas o texto cita só a 2ª Câmara do TJMS. | A favor: STF, 2ª T., RHC 267.297 AgR e HC 273.296 AgR; TJMS, 2ª Câm. (1602182-72.2026, 1602006-93.2026, 1604388-59.2026). Contra: STF, 1ª T., RHC 273.867 AgR; STJ, 6ª T., AgRg no HC 1.087.914; TJMS, 1ª Câm. (1602236-38.2026, 1602495-33.2026) e 3ª Câm. (1600825-57.2026, 1604099-29.2026, 1602318-69.2026). | Nenhum no resultado; o operador pode supor que o TJMS é favorável. | Texto: "TJMS dividido: 2ª Câmara a favor; 1ª e 3ª contra". | Baixa | Não | Não reconferido |
| 15 | Falta firme e Tema 1195 (6.8) | Tese discutível | Falta homologada depois é sempre impeditiva. A tese do Tema 1195 foi retificada (10/06/2026) e ressalva a "inércia ou mora estatal". | STJ, Tema 1195 (REsp 2.011.706). Aplicação ao Decreto 2024: STJ, 5ª T., AgRg no AREsp 3.175.620. | Falta apurada muito depois tratada como impeditiva sem a ressalva. | Homologação muito posterior ao fato (ex.: mais de 6 meses): "? Tema 1195: conferir mora estatal". Atualizar a citação. | Baixa | Sim (prazo que dispara a nota) | Não reconferido |
| 16 | Sentença posterior à publicação (6.2) | Erro de citação | O AgRg no HC 441.551 trata de trânsito posterior (Decreto 8.615/2015), não de sentença posterior. | STJ, 5ª T., AgRg no HC 894.488; 6ª T., AgRg no RHC 202.756 e AgRg no AREsp 2.644.592 (Decreto 11.302/2022, sentença posterior). | Nenhum. | Trocar ou complementar a citação. | Baixa | Não | Persiste (texto igual) |
| 17 | Início do cumprimento (6.2) e XV (6.10) | Erro de citação | O AgRg no HC 1.042.931 é citado como regra para "incisos com fração", mas trata do inciso VIII e de pena nova não iniciada de quem estava em livramento. | STJ, 5ª T., AgRg no HC 1.042.931 (24/06/2026); para o VII, AgRg no REsp 2.257.552. | Reforça indevidamente o achado 1. | Descrever o caso como é e acrescentar o Tema 1277. | Baixa | Não | Não reconferido |
| 18 | Remição pendente apontada pela ficha (6.3) | Erro de citação | O "STJ, HC 1.089.923" é decisão monocrática (Min. Og Fernandes, 11/06/2026), não acórdão. | O teor confere: reapreciar o indulto contando o tempo remido. | Nenhum. | Citar como decisão monocrática, com a data. | Baixa | Não | Não reconferido |
| 19 | Trânsito e recurso da acusação no Decreto 2022 (6.9) | Erro de fundamento | O STJ funda a exigência de trânsito para a acusação no art. 12 do Decreto 11.302/2022; o programa cita só o art. 9º, p. ú. | STJ, 6ª T., AgRg nos EDcl no HC 991.402 (29/04/2026). O TJDFT usa o mesmo art. 12 para os reincidentes. | Nenhum. | Acrescentar o art. 12 ao fundamento e à ressalva do reincidente (6.7). | Baixa | Não | Não reconferido |
| 20 | Tráfico: caput, § 1º e § 4º (6.5) | Erro de citação | O número "STF, Tema 1400" não foi confirmado. Falta a Súmula Vinculante 63. | STF, SV 63; STF, RE 1.542.482 RG (30/05/2025); STJ, Tema 1336 (confirmado, com ressalva do § 4º). | Nenhum. | Citar a SV 63 e o RE 1.542.482; conferir o número do tema. | Baixa | Não | Persiste (texto igual) |
| 21 | Exibição em anos, meses e dias (6.4) | Erro só de texto | Restos de 360 a 364 dias saem como 11 meses e 25 a 29 dias: 2.186 dias aparecem como "5a11m26d", que lido de volta dá 2.181. | Convenção do SEEU (ano de 365, mês de 30). | Tempo escrito a menor na petição. | Nesses casos, mostrar também os dias: "5a11m26d (2.186 dias)". | Baixa | Sim (forma de exibir) | Persiste (código igual) |
| 22 | Trânsito e recurso da acusação, Decretos 2024/2025 (6.2) | Erro de fundamento | A corrente contrária ao art. 2º, II, vem de decretos com texto diferente (AgRg no HC 864.086: Decreto 9.246/2017; AgRg no HC 633.240: Decreto 8.172/2013). | Os precedentes existem, mas tratam de decretos sem a regra do art. 2º, II. | Nenhum; enfraquece a nota. | Dizer que são de decretos anteriores, aplicados por analogia. | Baixa | Não | Não reconferido |
| 23 | Incisos XII e XIII sem a metade (6.10) | Erro só de texto | O relatório trata como ponto discutível, mas o decreto é expresso ("incisos I a XI"): o programa está certo. | Art. 9º, § 2º. | Nenhum. | Retirar o quadro de ponto discutível. | Baixa | Não | — |
| 24 | Exemplo da exibição (6.4) | Erro só de texto | A frase "1/5 do cumprido (437) aparece como 1a2m12d, e não 1a2m11d" confunde: 437 dias são exatamente 1a2m12d. | 365 + 72 = 437. | Nenhum. | Reescrever o exemplo. | Baixa | Não | — |

**25. Observações de redação do relatório** (sem efeito no programa; decisão sua: não):
- (a) Em 6.2, o "ponto discutível" do art. 5º descreve como tese o que é erro de resultado (achado 1).
- (b) Em 6.10, o § 2º de 2024 diz "filho com até quatorze anos" no inciso II e "menor de quatorze" no inciso III; o relatório trata os dois como "até 14".
- (c) Em 6.11, o exemplo do art. 11, I, não diz que a comutação das mulheres não se acumula com a do art. 13 (§ 3º). O código faz isso certo.

## O que não foi confirmado

| Item | Situação |
|---|---|
| Lei 15.402/2026 | Não localizada no JusRatio. Não confirmado se afeta o indulto. |
| Lei 15.358/2026: texto integral e vigência | Vistos só os reflexos no art. 112 da LEP e no art. 1º da Lei 8.072. A data de 25/03/2026 vem da base jurídica do programa. |
| TJMG, 9ª Câm. Crim., 1294534-24.2025 (art. 2º, II) | Não localizado. |
| STF, Tema 1400 | Número não confirmado. O julgado localizado sobre o ponto é o RE 1.542.482 RG. |
| STF, HC 118.533 e Súmula Vinculante 56 | Não conferidos nesta revisão. |
| Posição do TJMS sobre o art. 5º (preso cautelar solto na data) | Não localizada. Um julgado da 2ª Câm. (1603470-60.2023) contou a prisão provisória no Decreto 9.246/2017. |
| Natureza declaratória da comutação anterior (achado 12) | Sem precedente específico localizado. |
| STJ, HC 1.066.254 e STF, HC 273.296 AgR | Existência e tema confirmados pela ementa; o inteiro teor não foi lido. |
| Como o SEEU lança a comutação anterior (na pena total ou como pena cumprida) | Afeta o § 1º do art. 13. Não confirmado. |
| Situação em 7.15.1 dos itens marcados "não reconferido" | Não testados de novo depois das mudanças de 7.14.8 a 7.15.1. |

## Próxima etapa

Depende da sua aprovação. Sugestão: começar pelos achados 1, 2, 4, 5, 6 e 11 (o 3 já está corrigido em 7.15.1). Os de texto e citação (14 a 24) podem ir num lote único.

Cada correção aprovada vai num branch próprio, com teste de caso fictício e a bateria completa. O PR só será aberto quando você pedir.
