# Revisão jurídica — Capítulo 5: Remição (trabalho, estudo, leitura, exames) e aba Ficha

- **Objeto:** relatório técnico-jurídico do APTO, versão 7.14.7 (pp. 42–66), comparado com o código e com a lei vigente.
- **Revisão feita em:** 27/10/2026, sobre a versão 7.14.7 (commit `04bd716`).
- **Reconferida em:** 05/11/2026, sobre a versão 7.15.1 (commit `0ed0b1a`). Os achados 1, 2, 4, 5 e 7 foram confirmados de novo com os mesmos casos fictícios. Os demais foram confirmados no código. A 7.15.1 passou a aplicar o limite de 12 obras de leitura em 12 meses. Esse era um "ponto discutível" do relatório, não um achado desta revisão.
- **Etapa:** só revisão. Nenhum código foi alterado.
- **Dados:** todos os casos usados são fictícios. Não há nomes nem dados de assistidos.
- **Relatório em PDF:** [Revisao_Cap5_Remicao_APTO_7.14.7.pdf](Revisao_Cap5_Remicao_APTO_7.14.7.pdf)

## Resumo

| Regras revisadas | Corretas | Com achado | Erro de resultado | Erro de fundamento ou citação | Erro só de texto | Tese discutível | Prioridade alta / média / baixa |
|---|---|---|---|---|---|---|---|
| 63 | 50 | 13 | 10 | 3 | 3 | 4 | 3 / 7 / 10 |

Uma regra pode ter mais de um achado. São 20 achados no total. As escolhas de política já decididas não foram tratadas como erro.

**Principais pontos.**
1. Quando o RSPE tem remições antigas que somam mais que a ficha, o programa rebaixa a cinza também o documento posterior à última remição.
2. A perda acima de 1/3 (art. 127) sofre o mesmo rebaixamento.
3. A Lei 15.402/2026 incluiu o § 9º no art. 126 da LEP (o regime domiciliar não impede a remição), e o programa não o considera.
4. A remição ficta da pandemia termina em 22/04/2022, mas a emergência sanitária só acabou em 22/05/2022.

## Achados

Coluna "Decisão sua?": **Sim** quando a correção depende de uma escolha sua (tese, data ou forma do pedido); **Não** quando a correção decorre da lei ou da coerência interna do programa.

| Nº | Regra (seção) | Problema | Classe | Fundamento | Efeito para o assistido | Correção proposta | Prioridade | Decisão sua? |
|---|---|---|---|---|---|---|---|---|
| 1 | Situação e cores; documento posterior à última remição (5.1, 5.2) | Com o RSPE maior que a ficha, todo ponto amarelo vira cinza, inclusive o do documento emitido ou peticionado **depois** da última decisão de remição. Caso fictício: remições de 100 dias (2020) e 20 dias (2025); atestado de 52 dias de 2026, peticionado e sem decisão: linha cinza, "Conferir (informativo)". Uma remição antiga não explica um documento posterior a ela. | Erro de resultado | LEP, arts. 126, § 8º, e 128; a própria regra 5.2 (o documento posterior é o "fato certo") | A pendência certa fica escondida na triagem: sai dos relatórios por assistido, que só listam pontos não cinza, e entra no filtro "Sem ficha". Os decretos e a prioridade continuam a vê-la. | Não rebaixar o ponto "posterior à última remição" nem o documento posterior; idem o estudo estimado que passa da última decisão. Ajustar o texto de 5.1. | Alta | Não |
| 2 | Testes do art. 127 na aba Ficha (5.8). Ponto já conhecido. | Confirmado: a perda acima de 1/3 vira cinza quando o RSPE é maior que a ficha. Exemplo do próprio relatório: base 90, limite 30, perdidos 40; aparece em cinza, "Conferir (informativo)". | Erro de resultado | LEP, art. 127; STJ, HC 293.475, HC 377.088 e HC 398.850 (conferidos) | A perda ilegal de 10 dias passa despercebida e não aparece nos relatórios por assistido. | Não rebaixar a perda (incluí-la nas exceções, como o "Pedir atestado"). A perda é questão de lei e não depende da comparação de totais. | Alta | Não |
| 3 | Períodos fora da unidade (5.4); fundamentação (5.10) | O capítulo diz que no aberto e no livramento só o estudo remite (art. 126, § 6º). Desde 08/05/2026, a Lei 15.402/2026 incluiu o § 9º: "O cumprimento da pena restritiva de liberdade em regime domiciliar não impede a remição da pena." O programa não cita o § 9º. | Erro de fundamento (ver também o nº 17) | LEP, art. 126, §§ 6º e 9º (Lei 15.402/2026) | Quem cumpre o aberto ou o semiaberto em casa, situação comum em MS, pode ter trabalho remível que o programa nem estima nem pede. | Atualizar o fundamento. Manter o corte no aberto, mas com ponto amarelo: "trabalho em regime domiciliar: remição pelo § 9º do art. 126 (Lei 15.402/2026) — conferir". Na fundamentação, parágrafo opcional com o § 9º. | Alta | Sim (como tratar a tese) |
| 4 | Afastamento do trabalho: pandemia (5.2) | A remição ficta vai até 22/04/2022, tida como fim da emergência sanitária. A Portaria GM/MS 913/2022 é dessa data, mas só entrou em vigor 30 dias após a publicação: a emergência terminou em 22/05/2022. | Erro de resultado e de fundamento | STJ, Tema 1.120; Portaria GM/MS 913/2022 (fonte oficial) | Caso de trabalho suspenso em 21/03/2020, sem retorno: 634 dias de trabalho (211,33 dias de remição) em vez de 659 (219,67), ou seja, 8,3 dias a menos no pedido. | Usar 22/05/2022 e dizer no texto que vale o retorno efetivo das atividades na unidade, se posterior (corrente favorável). | Média | Sim (22/05/2022 ou retorno efetivo) |
| 5 | Estudo sem certidão (5.5) × fundamentação (5.10). Ponto já conhecido. | Confirmado: a matrícula aberta há mais de 1 ano sem registro escolar sai da estimativa na tela, mas a fundamentação afirma "matrícula em estudo … (03/02/2024 em diante)". O erro está no código da fundamentação, que não aplica o corte descrito no capítulo. | Erro de resultado | LEP, art. 126, § 1º, I | A petição afirma uma frequência que a ficha não mostra. Risco de indeferimento e de perda de credibilidade. | Não pedir a remição desse período como certa; trocar por pedido de requisição da certidão, com a ressalva "[a ficha não registra frequência desde …: conferir]". | Média | Sim (retirar ou converter em requisição) |
| 6 | Prioridade (5.9). Ponto já conhecido. | Confirmado em parte: a prioridade recua as datas pelos dias inteiros da remição pendente. No livramento e no término isso está certo, porque a remição é pena cumprida. Na progressão, o trabalho anterior à data-base só reduz a fração, como a própria fundamentação calcula. | Erro de resultado | LEP, arts. 112 e 128 | Falsa prioridade na progressão e risco de pedido prematuro. Não afeta livramento nem término. | Na progressão, usar a mesma conta do "Reflexo na progressão". Corrigir o "Ponto discutível" de 5.9. | Média | Não |
| 7 | Certidão, curso e estimativa (5.5). Ponto já conhecido. | Confirmado: a carga horária nunca é lida. Certidão com "CARGA HORÁRIA DE 412 HORAS" fica como "sem a carga horária no texto da ficha". Persiste na 7.15.1. | Erro de resultado | LEP, art. 126, § 1º, I (12 h = 1 dia) | O documento fica fora do total; a ficha fica menor que o RSPE e dispara o rebaixamento a cinza do nº 1. | Ler "N horas" ou "N h/a" na certidão e no curso; valor = horas ÷ 12. | Média | Não |
| 8 | Situação da linha (5.1). Ponto já conhecido. | Confirmado: vínculo "Possível" ou "Sugerido · confirmar" não muda a situação. A linha pode ficar verde, "Em ordem", enquanto o quadro ao lado pede para confirmar. | Erro de resultado | LEP, art. 129 | Um vínculo sugerido errado pode esconder trabalho sem atestado e o pedido deixa de ser feito. | Rótulo amarelo "Confirmar vínculo"; nunca "Em ordem" com vínculo a confirmar. | Média | Não |
| 9 | Filtros da aba (5.1). Ponto já conhecido. | Confirmado: o filtro "Sem ficha" seleciona qualquer linha cinza, inclusive "Conferir (informativo)", "RSPE maior" e "Acompanhar atestado". | Erro de resultado (triagem) | — | Somado aos nºs 1 e 2, casos com pendência ou perda ilegal aparecem como "sem ficha". | Filtro "Sem ficha" só para ficha não importada; novo filtro "Informativo / acompanhar". | Média | Não |
| 10 | Estudo sem certidão (5.5) | A estimativa usa o início da matrícula sem cortar no início desta execução: só exclui o estudo que termina antes dela. | Erro de resultado (pequeno) | LEP, art. 126, caput e § 7º | Estimativa maior e risco de pedir período de outra execução. | Começar a estimativa no início desta execução. | Baixa | Não |
| 11 | Coluna "Trabalho a atestar" (5.1). Citado no Cap. 11. | Aparece "Sim" para trabalho coberto pelo saldo ("pode já estar remido") ou em curso a acompanhar, sem pedido. | Erro de resultado (indicador) | — | Ruído na triagem. | "Sim" só quando houver "Pedir atestado". | Baixa | Não |
| 12 | Pontos e quadro "Onde pode estar a diferença" (5.1, 5.2). Ponto já conhecido. | Confirmado: o mesmo documento gera dois pontos (por exemplo, "posterior" e "sem valor na ficha"; "sem peticionamento" e "abaixo de 1/3") e ocupa duas das quatro linhas do quadro. | Erro só de texto | — | Linhas importantes podem ir para "… e mais N". | Agrupar por documento: uma linha com todos os motivos. | Baixa | Não |
| 13 | Certidão sem valor (5.5) | Texto "certidão sem a carga horária no texto da ficha" quando o texto traz as horas (decorre do nº 7). | Erro só de texto | — | Informação falsa ao operador. | Resolve-se com o nº 7. | Baixa | Não |
| 14 | Estudo sem certidão (5.5) | Os dias aparecem truncados (92 em vez de 92,67), como o próprio capítulo registra. | Erro só de texto | — | Diferença de até 1 dia no texto. | Mostrar duas casas decimais, como nas demais estimativas. | Baixa | Não |
| 15 | Testes do art. 127 (5.8) | "TJDFT, Acórdão 1230029" não foi localizado no JusRatio. Os três HCs do STJ foram confirmados e dizem o que o programa afirma. | Erro de citação (não confirmado) | — | Citação sem fonte verificável numa petição. | Substituir por TJDFT, 0720055-22.2024.8.07.0000 (3ª Turma Criminal, 27/06/2024: perda limitada a 1/3, novo período aquisitivo desde a infração anterior), ou conferir o número. | Baixa | Sim (substituir ou conferir) |
| 16 | Testes do art. 127 (5.8) | Cita "Súmula 533/STJ; STF, Tema 941" lado a lado. A súmula exige procedimento disciplinar; o Tema 941 (RE 972.598, 2020) diz que a audiência de justificação em juízo o dispensa. A citação conjunta não diz qual prevalece. | Erro de fundamento (redação) | STF, Tema 941; Súmula 533/STJ (conferidos) | Nenhum no resultado. | Escrever "Súmula 533/STJ, mitigada pelo STF, Tema 941". | Baixa | Não |
| 17 | Períodos fora da unidade (5.4) | Ver o nº 3. Tese: o § 9º permite remir pelo trabalho também no aberto cumprido em casa. | Tese discutível | Favorável: art. 126, § 9º. **STJ:** não cabe remição pelo trabalho no aberto (AgRg no RHC 147.478, 2021); cabe no semiaberto em prisão domiciliar (AgRg no REsp 1.689.353, 2018). **TJMS:** não cabe no aberto (1605853-74.2024.8.12.0000, 1ª Câm. Crim., 2024). **STF:** não localizado. Não há julgado posterior ao § 9º. | Pedido possível que hoje não é sugerido. | Ponto amarelo com a tese, sem afirmar o direito. | Média | Sim |
| 18 | Testes do art. 127 (5.8). Lacuna. | O programa não confere se a perda acima de 1/6 (até o máximo de 1/3) foi fundamentada. | Tese discutível / lacuna | Favorável e do **STJ:** o patamar máximo exige fundamentação concreta (HC 692.749, 6ª T., 2021). **TJMS:** não pesquisado. | Perda máxima sem motivação não é apontada. | Ponto informativo: "perda de 1/3: conferir a fundamentação do patamar". | Baixa | Sim |
| 19 | Contagem: jornada 12x36 (5.4) | No 12x36, o programa conta um dia por plantão de 12 horas. Corrente favorável: as horas acima de 8 contam para a remição. | Tese discutível | Precedentes não conferidos nesta revisão | Estimativa menor para quem trabalha em plantão. | Só ressalva no texto da estimativa; a conta não muda sem precedente conferido. | Baixa | Sim |
| 20 | Documento à parte: anterior à execução (5.1) | Atestado de trabalho feito em prisão cautelar por outro processo fica "à parte". Corrente favorável: aproveitá-lo na execução atual, como a detração (CP, art. 42). | Tese discutível | LEP, art. 126, § 7º; precedentes não conferidos | Remição possível perdida. | Trocar "à parte" por "à parte: conferir aproveitamento (detração)" quando o período for posterior ao crime desta execução. | Baixa | Sim |

## Pontos já conhecidos: resultado

| Ponto | Resultado | Achado |
|---|---|---|
| Matrícula aberta há mais de 1 ano: a tela tira, a fundamentação pede | Confirmado (caso fictício rodado) | 5 |
| Filtro "Sem ficha" pega qualquer linha cinza | Confirmado no código da tela | 9 |
| Perda acima de 1/3 fica cinza | Confirmado (exemplo do relatório rodado) | 2 |
| Prioridade e fundamentação usam contas diferentes | Confirmado só para a progressão; livramento e término estão certos | 6 |
| "Em ordem" com vínculo a confirmar | Confirmado no código | 8 |
| Mesmo documento gera ponto duplicado | Confirmado (dois casos fictícios) | 12 |
| Carga horária nunca é lida | Confirmado (caso fictício com 412 horas) | 7, 13 |

## Precedentes citados pelo programa neste capítulo

| Citação | Situação |
|---|---|
| STJ, Tema 1.120 (REsp 1.953.607, 3ª Seção, 14/09/2022) | Confirmado. Vale para quem já trabalhava ou estudava e parou só pela pandemia. |
| STJ, HC 1.089.923 (Rel. Og Fernandes, 11/06/2026) | Existe e diz o que o programa afirma. É decisão monocrática; convém dizer isso no texto. |
| STJ, HC 293.475 (5ª T., 2015); HC 377.088 (6ª T., 2017); HC 398.850 (5ª T., 2017) | Confirmados: a perda é limitada a 1/3 no total, não por falta, e alcança o período entre a falta anterior e a atual. |
| Súmula 533/STJ; STF, Tema 941 (RE 972.598, 04/05/2020) | Confirmados; ver o nº 16. |
| TJDFT, Acórdão 1230029 | Não localizado (nº 15). |
| Res. CNJ 391/2021, arts. 3º e 5º; Portaria AGEPEN 15/2021, art. 11 | Não confirmados (ver abaixo). |

## Exemplos refeitos à mão

Todos os 15 exemplos numéricos do capítulo batem com a conta à mão, exceto a data final da remição ficta da pandemia (nº 4). No reflexo na progressão, há só uma diferença de arredondamento intermediário (30,48 × 30,47), sem efeito no resultado (30 dias, 30/01/2027).

## Escolhas de política: riscos jurídicos

As escolhas já decididas foram mantidas. Registram-se dois riscos:

- A tolerância de 3 dias e o "mesmo valor decidido em …: conferir" podem esconder atestados pequenos anteriores à última remição. O capítulo já avisa disso.
- A regra de que o "RSPE maior" é só informativo é razoável para a diferença de totais, mas não deve alcançar fatos que independem dela: o documento posterior e a perda acima de 1/3 (nºs 1 e 2).

## O que não foi confirmado

- **Lei 15.358/2026:** o texto não está na base do JusRatio. No código, ela só define frações do art. 112 e não afeta a remição.
- **Lugar do § 9º:** a LEP compilada (Planalto, via JusRatio) o coloca no art. 126. Na íntegra da Lei 15.402/2026 na base, ele aparece logo após o texto do art. 112. Conferir no DOU de 08/05/2026 (edição extra) antes de citar.
- **Res. CNJ 391/2021, arts. 3º e 5º** (1.600 h e 1.200 h; 4 dias por obra; 12 obras em 12 meses): o texto não está na base do JusRatio e o site do CNJ recusou o acesso. Os números conferem com a conta, mas o texto não foi lido.
- **Portaria AGEPEN 15/2021, art. 11** (envio mensal ao juízo): não encontrada.
- **TJDFT, Acórdão 1230029:** não localizado pelo número.
- **Feriado estadual de 11 de outubro em MS:** o número da lei estadual não foi conferido.
- **Teses dos nºs 19 e 20:** os precedentes não foram pesquisados, porque a conta do JusRatio tinha duas pesquisas de outra sessão em andamento e só aceita duas ao mesmo tempo. A posição do STJ, do STF e do TJMS não foi confirmada.
- **Julgados posteriores ao § 9º** sobre o aberto cumprido em casa: nenhum encontrado (STJ, STF, TJMS).
- **Posição do TJMS sobre os nºs 4, 18, 19 e 20:** não pesquisada.

## Fontes principais

- LEP compilada: https://www.planalto.gov.br/ccivil_03/leis/l7210compilado.htm
- Portaria GM/MS 913/2022: https://bvsms.saude.gov.br/bvs/saudelegis/gm/2022/prt0913_22_04_2022.html
- STJ, Tema 1.120 (REsp 1.953.607): https://scon.stj.jus.br/SCON/GetInteiroTeorDoAcordao?num_registro=202102579184&dt_publicacao=20/09/2022
- STJ, HC 1.089.923: https://processo.stj.jus.br/processo/monocraticas/decisoes/?num_registro=202601483419&dt_publicacao=15/06/2026
- STJ, HC 293.475: https://scon.stj.jus.br/SCON/GetInteiroTeorDoAcordao?num_registro=201400980458&dt_publicacao=11/06/2015
- STJ, HC 377.088: https://scon.stj.jus.br/SCON/GetInteiroTeorDoAcordao?num_registro=201602881219&dt_publicacao=11/05/2017
- STJ, HC 398.850: https://scon.stj.jus.br/SCON/GetInteiroTeorDoAcordao?num_registro=201701050277&dt_publicacao=27/06/2017
- STJ, HC 692.749: https://scon.stj.jus.br/SCON/GetInteiroTeorDoAcordao?num_registro=202102915502&dt_publicacao=06/10/2021
- STF, RE 972.598 (Tema 941): https://portal.stf.jus.br/jurisprudencia/obterInteiroTeor.asp?idDocumento=753393432
- STJ, AgRg no RHC 147.478: https://scon.stj.jus.br/SCON/GetInteiroTeorDoAcordao?num_registro=202101484796&dt_publicacao=01/06/2021
- STJ, AgRg no REsp 1.689.353: https://scon.stj.jus.br/SCON/GetInteiroTeorDoAcordao?num_registro=201702006995&dt_publicacao=15/02/2018
- TJMS, 1605853-74.2024.8.12.0000: https://esaj.tjms.jus.br/cjsg/getArquivo.do?cdAcordao=1634018
- TJDFT, 0720055-22.2024.8.07.0000: https://jurisdf.tjdft.jus.br/api/v1/pesquisa/download/3237a3af-3dc4-458c-86e8-ab6a3986e135

## Próximo passo

A etapa 2 depende da sua aprovação: aplicar as correções aprovadas num branch próprio, com um teste para cada uma, rodar `python3 testes.py` e abrir o PR só quando você pedir.
