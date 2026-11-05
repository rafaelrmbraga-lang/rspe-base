# Revisão jurídica — Cap. 6: Indulto 2022 a 2025

- **Versão revisada:** APTO 7.14.7 (commit `04bd716`), revisão de 27/10/2026.
- **Reconferida em 05/11/2026 na versão 7.15.1 (commit `0ed0b1a`):** os 12 achados continuam presentes. Os números de linha abaixo são da 7.14.7; por isso cada achado indica também a função ou o trecho do código.
- **Etapa:** só revisão. Nenhum código foi alterado.
- **Relatório em PDF:** [APTO_7.14.7_revisao_cap6_indulto.pdf](APTO_7.14.7_revisao_cap6_indulto.pdf)
- **Dados:** só casos fictícios. Nenhum nome real e nenhum dado real.

## Resumo

- **26 regras revisadas.** 16 corretas, 1 erro de resultado, 4 erros de fundamento ou citação, 4 erros só de texto e 1 tese discutível.
- **2 lacunas**, ou seja, situações que a regra não cobre. Uma delas tem efeito grande na comutação.
- **O que mais pesa para o assistido:**
  - Achado 1: nos Decretos de 2024 e 2025, quem só teve prisão provisória pelo próprio processo recebe "não iniciou o cumprimento", embora o art. 5º e o Tema 1277 do STJ mandem contar esse tempo.
  - Achado 2: a comutação de 2/3 do art. 13, § 4º, nunca é lembrada para mães, pais que cuidam sozinhos dos filhos e pessoas com deficiência.

### Limite da revisão

O PDF fornecido ("1_Leitura_e_alertas") não contém o cap. 6. Por isso o código foi comparado com:

- os textos oficiais dos Decretos 11.302/2022, 12.338/2024 e 12.790/2025, que estão no repositório;
- o resumo oficial do Decreto 11.846/2023 no Planalto;
- o que os caps. 10 e 11 dizem sobre o indulto.

A comparação do texto e dos exemplos do cap. 6 ainda está pendente.

### Pontos já conhecidos

| Ponto | Conclusão |
|---|---|
| Fundamentações prontas que nunca aparecem | **Confirmado.** Ver achado 6. |
| Histórico de versões errado sobre o triângulo | **Confirmado**, só texto. Ver achado 9. |
| Aviso de 60 anos sem o decreto de 2022 | **Descartado como erro do programa.** O Decreto 11.302/2022 não reduz os prazos pela metade aos 60 anos; tem só o art. 4º, para quem tem mais de 70. O erro está na frase do cap. 11. Ver achado 10. |

## Achados

A coluna "Decisão sua?" indica se a correção depende de uma escolha jurídica ou de política sua, e não só de ajuste técnico.

| Nº | Regra | Problema | Fundamento | Efeito para o assistido | Correção proposta | Tipo | Prior. | Decisão sua? |
|---|---|---|---|---|---|---|---|---|
| 1 | Decretos 2024/2025: pessoa com só prisão provisória pelo próprio processo, ou com regime fixado e sem início registrado. Código: `rspe_scraper.py`, análise detalhada dos decretos, blocos `sem_inicio` e `not em_cumprimento`. | Responde "não se aplica: não iniciou o cumprimento" e ignora a prisão provisória, mesmo com a condenação já existente na publicação do decreto. | Decretos 12.338/2024 e 12.790/2025, art. 5º (prisão cautelar conta como pena cumprida) e art. 2º, IV (cabe sem guia de recolhimento). STJ, Tema 1277 (repetitivo): a prisão provisória conta nos requisitos do indulto e da comutação. O AgRg no HC 1.042.931 (5ª T., 24/06/2026), citado pelo programa, trata de condenação nova sem nenhuma custódia (inciso VIII). | Indulto e comutação deixam de ser apontados para quem só cumpriu prisão provisória, normalmente quem tem penas curtas. | Contar a custódia provisória pelo próprio processo anterior à data do decreto. Avaliar os incisos de fração (I a III, XII, XIII, XIV) e a comutação; deixar "a verificar" os incisos que dependem do regime (VI a XI); citar o Tema 1277. Teste: caso fictício 1. | Erro de resultado | Alta | Não. Escolha a confirmar: manter "a verificar" quando não houver custódia nenhuma, como no AgRg no HC 1.042.931. |
| 2 | Comutação: art. 13, § 4º (2/3 para as pessoas do art. 9º, § 2º). | Aplica 2/3 só a quem tem 60 anos ou mais (§ 2º, I). Para os demais grupos do § 2º (II a VI) não há aviso, e a tela mostra só a comutação de 1/5. No indulto, o mesmo § 2º gera "a conferir". | Decretos 2024/2025, art. 13, § 4º, e art. 9º, § 2º, II a VI. O § 3º afasta a redução no crime violento contra filho, criança ou adolescente. | Diferença grande. Num remanescente de 5 anos, a comutação de 1/5 tira 1 ano; a de 2/3 tira 3 anos e 4 meses. | Quando couber a comutação do art. 13 e a idade for abaixo de 60, acrescentar: "a conferir: 2/3 (art. 13, § 4º) se estiver no § 2º, II a VI", com a ressalva do § 3º. | Lacuna | Alta | Não. |
| 3 | Art. 6º (falta grave nos 12 meses). Texto: "só impede se a sanção for reconhecida em juízo; STJ, Tema 1195". | A regra está certa (a falta sem homologação fica "a verificar"), mas a citação diz o contrário do tema. O Tema 1195 diz que a falta impede mesmo com a apuração concluída depois do decreto, salvo inércia do Estado. O mesmo erro aparece no cap. 10. | STJ, Tema 1195 (REsp 2.011.706, 3ª Seção, 10/12/2025; tese retificada em embargos de 10/06/2026). STJ, AgRg no AREsp 3.175.620, 5ª T., 09/06/2026 (Decreto 12.338/2024). Corrente favorável ao assistido: leitura literal do art. 6º. | Uma petição que cite o Tema 1195 a favor do assistido seria rebatida com o próprio tema. | Trocar por: "o art. 6º exige sanção reconhecida em juízo; o STJ (Tema 1195; AgRg no AREsp 3.175.620) admite que a homologação posterior impeça se a falta foi cometida na janela". Manter "a verificar" e corrigir também o cap. 10. | Erro de citação | Média | Não. |
| 4 | Indulto 2022, art. 5º, para reincidente: "POSSÍVEL" passa a "A VERIFICAR (reincidente)". Código: `REINC_ART5_2022` e o uso dela na análise de 2022. | O rebaixamento está alinhado aos tribunais, mas o fundamento está desatualizado. Cita só o TJDFT e diz que a constitucionalidade do art. 5º "está no Tema 1267", que já foi julgado. Não diz que o óbice vem do art. 12 do decreto. | STF, Tema 1267 (RE 1.450.100, 19/05/2025): o art. 5º é constitucional. STJ, AgRg no REsp 2.268.813 (5ª T., 01/10/2026) e AgRg no REsp 2.280.116 (6ª T., 16/09/2026): a reincidência impede, pelo art. 12. TJMS, 1ª Câm., 1603080-85.2026 (04/08/2026): no mesmo sentido. TJDFT, 0749686-45.2023 e 0700400-64.2024: confirmados. | Não muda o resultado, mas confunde o operador sobre a força do óbice. | Reescrever a nota: Tema 1267 já julgado; óbice pelo art. 12 no STJ (5ª e 6ª Turmas) e no TJMS (1ª Câm.). Tese defensiva: o art. 12 é regra de competência do juízo do conhecimento, não requisito do art. 5º. Manter "a verificar". | Erro de fundamento e tese discutível | Média | Sim: manter "a verificar" ou passar a "não cabe" com a tese em ressalva. |
| 5 | Hediondez posterior ao fato: menção ao TJMS. Código: `rspe_auditoria.py` (item de hediondez superveniente) e `rspe_scraper.py` (`impeditivo_decreto` e texto do inciso I). | Diz que "a 2ª Câmara Criminal" do TJMS afere a hediondez na data do fato. Só o Des. Waldir Marques adota essa tese; outros julgados da mesma Câmara seguem o STJ. | TJMS, 2ª Câm.: a favor, 1602182-72.2026 (26/06/2026) e 1603697-45.2026 (20/08/2026), ambos do Des. Waldir Marques. Contra: 1603823-95.2026, 1602868-64.2026, 1604006-66.2026 e 1601883-95.2026. 1ª Câm. (1602495-33.2026) e 3ª Câm. (1602318-69.2026): data do decreto. STF: 2ª T., RHC 267.297 AgR, a favor; 1ª T., RHC 273.867 AgR, contra. STJ: AgRg no HC 1.087.914 (6ª T.), contra. | Superestima a chance de êxito no TJMS. O resultado ("a verificar, tese") não muda. | Trocar "a 2ª Câmara Criminal" por: "na 2ª Câmara, o Des. Waldir Marques (1602182-72.2026, 1603697-45.2026); outros relatores da mesma Câmara, e a 1ª e a 3ª Câmaras, seguem o STJ". | Erro de fundamento | Média | Não. |
| 6 | Fundamentação pronta da hediondez posterior ao fato (ponto conhecido nº 1). | Os 4 textos de petição de indulto da Auditoria nunca aparecem. Três são retirados antes de o texto ser montado (`rspe_view.AUD_OUTRAS_ABAS`); o quarto é de nível "info". A aba Indulto cobre dois deles. Quando a única vedação é a hediondez posterior ao fato, a aba diz "Não cabe" e não mostra a tese. | CF, art. 5º, XL; CP, art. 2º; STF, 2ª T., RHC 267.297 AgR. | O defensor perde o texto pronto justamente da tese mais útil nesses casos. | Na aba Indulto (`rspe_indulto_tl._fundamentacao`), quando a vedação for só a hediondez posterior ao fato, acrescentar o parágrafo da tese e o pedido alternativo. Apagar da Auditoria os textos que nunca aparecem. | Erro só de texto (texto pronto ausente) | Média | Sim: oferecer ou não a tese, já que o STJ e o TJMS são majoritariamente contrários. |
| 7 | Indulto 2022 com crime marcado "Suspenso: Sim". Código: `rspe_scraper._penas_a_verificar`. | O aviso diz que "a pena sai das contas só com o sursis ou a substituição confirmados". No Decreto 2022, o art. 8º exclui a pena restritiva de direitos, a multa e a suspensão condicional do processo, mas não o sursis (suspensão condicional da pena). | Decreto 11.302/2022, art. 8º, I a III. | Pequeno: o resultado fica "a verificar", sem negar o indulto, mas o texto orienta mal. | Novo texto: "se for substituição por restritivas, a pena fica fora do decreto (art. 8º, I); se for sursis, continua alcançada". | Erro de fundamento | Baixa | Não. |
| 8 | Inciso XV sem início do cumprimento (texto do "a verificar"). | Diz que o STJ exigiu início do cumprimento "para o inciso VIII, que depende de fração". O inciso VIII não depende de fração: exige pena remanescente de até 6 ou 4 anos, em livramento ou no regime aberto. | Decreto 12.338/2024, art. 9º, VIII; STJ, AgRg no HC 1.042.931. | Só texto. | Novo texto: "o STJ exigiu início do cumprimento no inciso VIII, numa condenação nova sem nenhuma custódia (AgRg no HC 1.042.931)". | Erro só de texto | Baixa | Não. |
| 9 | Histórico de versões e comentários sobre o triângulo (ponto conhecido nº 2). | A entrada 7.13.0 do LEIA-ME fala em "sem o '!'", mas o sinal de divergência é o triângulo vermelho; o "!" do programa é outro sinal (RSPE desatualizado, laranja). A entrada 7.9.3 diz "triângulo vermelho" e "era âmbar" na mesma versão. Comentários de `rspe_view.py` também falam em "!". | Organização da tela. | Nenhum. | Trocar "!" por "triângulo vermelho" no LEIA-ME (7.13.0) e nos comentários; ajustar a entrada 7.9.3. | Erro só de texto | Baixa | Não. |
| 10 | Aviso de idade da Auditoria e frase do cap. 11 (ponto conhecido nº 3). | A regra está certa: o aviso de prazos pela metade considera só 2024 e 2025. O cap. 11 aponta uma falha que não existe ("Aviso ausente em 2022"). O aviso também não lembra o art. 4º de 2022 (mais de 70 anos) nem as hipóteses de idade de 2023. | Decreto 11.302/2022, arts. 4º e 5º. Decreto 11.846/2023, art. 2º, III e IV, e art. 3º, § 3º, I. | Nenhum efeito no resultado. | Corrigir o cap. 11. Opcional: o aviso citar o art. 4º de 2022 e as hipóteses de 2023. | Erro só de texto | Baixa | Não. |
| 11 | Incisos I e II (crime sem violência) quando a soma tem crimes com e sem violência. Código: `vga = any(...)` na análise detalhada. | Basta um crime com violência para toda a execução sair dos incisos I e II. A pena do crime sem violência não é avaliada à parte, como já acontece nos incisos XIV e XV. | Art. 7º (soma das penas) em confronto com o art. 9º, I e II ("por crime praticado sem violência"). A jurisprudência não foi pesquisada nesta revisão. | Pode deixar de apontar o indulto parcial da pena do crime sem violência. | No mínimo, "a verificar (tese)": aplicar o I ou o II só à pena dos crimes sem violência. Decidir depois de pesquisar a jurisprudência. | Lacuna e tese discutível | Baixa | Sim. |
| 12 | Indulto 2022, art. 9º: condenação sem trânsito para a acusação na data da publicação. | Fica "a verificar", com a tese literal (art. 9º, p. ú.) e a posição do STJ. Está correto; o item está aqui só por ser tese em disputa. | STJ, AgRg no HC 864.086 (5ª T., 18/12/2023) e AgRg no HC 633.240 (6ª T., 15/06/2021), confirmados. AgRg nos EDcl no HC 991.402: não confirmado. | Nenhum (o resultado é cauteloso). | Nenhuma. | Tese discutível | — | Não. |

## Regras corretas (16)

1. Datas de referência e de publicação dos decretos, e janela da falta grave até a publicação.
2. 2022, art. 5º: pena máxima de até 5 anos, crime a crime. STF, Tema 1267: o artigo é constitucional.
3. 2022, art. 5º, e tráfico privilegiado. Precedentes: STJ, AgRg no HC 818.978, AgRg no HC 873.240 e AgRg no REsp 2.113.265; STF, Rcl 72.176. O TJMS tem decisões nos dois sentidos, e o programa avisa.
4. 2022, art. 4º: mais de 70 anos e 1/3 da pena cumprido, com as exceções do art. 7º, § 2º.
5. 2022, art. 7º, e art. 11, p. ú.: a pena integral do crime impeditivo vem antes. Precedentes: STF, RHC 246.431 e SL 1.698; STJ, AgRg no HC 890.929, HC 930.896 e AgRg no HC 992.164.
6. 2022 sem requisito disciplinar. A ADI 7.330 (medida cautelar) suspendeu o art. 6º e o art. 7º, § 3º.
7. 2022: condenação posterior à publicação fica fora da soma. STJ, AgRg no HC 441.551 e AgRg no HC 919.210.
8. 2023 (Decreto 11.846): frações, idade, comutação, detração e 2/3 do crime impeditivo. STJ, Tema 1336.
9. 2024 e 2025, art. 1º: rol completo dos crimes impeditivos, inclusive os arts. 147-A e 359-I a 359-R e a exceção da pena de até 4 anos. Tráfico privilegiado fora do rol: STF, Tema 1400.
10. Hediondez aferida na data do decreto (STJ), com a tese contrária como "a verificar". As leis de 2026 não alcançam os decretos de 2022 a 2025.
11. Art. 7º, p. ú. (2/3 da pena do crime impeditivo): STJ, HC 1.066.254. Súmula 535/STJ.
12. Art. 9º, I a III: tetos de pena e frações.
13. Art. 9º, IV a XIII. A redução do § 2º vale só para os incisos I a XI.
14. Art. 9º, XIV e XV: crime patrimonial sem violência, reparação dispensada pela hipossuficiência presumida (art. 12, § 2º, I).
15. § 2º, I, e art. 13, § 4º, aos 60 anos (caso fictício 2).
16. Arts. 10 e 11 (mulheres) e art. 13 (§§ 1º, 2º e 5º).

## Casos fictícios

**Caso 1 (achado 1)**

- Furto qualificado, pena de 2 anos, primário.
- Flagrante em 10/01/2024; solto em 10/07/2024; trânsito em julgado em 20/08/2024.
- Tempo de prisão provisória, contado o dia do começo: 183 dias.
- Exigência do art. 9º, I: 1/5 de 730 dias = 146 dias.
- Resultado do programa: "não iniciou o cumprimento", e a comutação "não se aplica". **Diverge da lei.**
- Na versão 7.15.1 o resultado é o mesmo.

**Caso 2 (regra correta)**

- Furto qualificado, pena de 4 anos, primário, prisão definitiva em 01/08/2024.
- Tempo cumprido até 25/12/2024: 147 dias.
- Exigência: 1/5 de 1.460 dias = 292 dias, ou 146 dias pela metade (§ 2º, I).
- Com 64 anos, o programa aponta "POSSÍVEL: art. 9º, I, XV". Com 44 anos, aponta só o XV. **Confere.**

## Não confirmado

- Texto e exemplos do cap. 6, que não estavam no PDF fornecido.
- Decreto 11.846/2023: conferido pelo resumo oficial do Planalto, não pelo texto integral.
- Tema 1195/STJ: o teor da retificação feita nos embargos de 10/06/2026.
- STJ: AgRg nos EDcl no HC 991.402; HC 190.963; AgRg no HC 799.167; HC 1.089.923; HC 429.545.
- STF: HC 273.296 AgR e as decisões monocráticas RE 1.572.734, HC 258.516, RHC 269.076, HC 271.716 e RE 1.607.670.
- TJMS: 1602006-93.2026 e 1602467-65.2026, que não apareceram na busca.
- TJMG: 1294534-24.2025.
- Posição do STF sobre a reincidência no indulto de 2022 (art. 12).
- Jurisprudência sobre crimes com e sem violência na mesma soma (achado 11).
- Art. 13, § 1º ("descontadas as comutações anteriores"): não foi montado caso que teste esse ponto.

## Próximo passo

Depois da sua aprovação, as correções serão aplicadas em branch próprio, com um teste para cada uma, e com `python3 testes.py` rodado ao final. O PR só será aberto quando você pedir.
