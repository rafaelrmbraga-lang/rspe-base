# Revisão jurídica — Capítulo 3: Progressão e livramento

- **Objeto:** relatório técnico-jurídico do APTO, aba Progressão e livramento (Cap. 3), versão 7.14.7.
- **Revisão feita em:** 27/10/2026. Situação dos achados conferida no `main` 7.15.1 em 05/11/2026.
- **Material:** PDF do capítulo; código do `main` (7.14.7 na revisão); `base_juridica.json`; texto vigente das leis (JusRatio e Planalto); precedentes conferidos no JusRatio.
- **Casos rodados no programa:** só fictícios. Não há nomes reais neste documento.
- **PDFs:** `cap3-progressao-livramento.pdf` (revisão completa) e `cap3-progressao-livramento-pendencias.pdf` (só o que ficou em aberto depois das correções).

## Resumo

| | |
|---|---|
| Regras revisadas | 53 |
| Corretas | 37 (4 com tese discutível sinalizada) |
| Erros de resultado | 11 (1 alta, 5 média, 5 baixa) |
| Erros de fundamento ou citação | 5 |
| Erros só de texto | 2 |
| Teses discutíveis | 10 |
| Pontos não confirmados | 7 |

- **Lei vigente:** o texto atual do art. 112 da LEP confirma as janelas do programa.
  - Lei 15.358/2026: DOU de 25/03/2026, vigência imediata (V 70%, VI 75%, VII 80%, VIII 85%).
  - Lei 15.402/2026: DOU de 08/05/2026 (edição extra), vigência imediata (caput 1/6, I 25%, II 30%, III 20%). Está questionada no STF nas ADIs 7966 a 7969. A liminar suspendeu a aplicação só nos processos dos atos de 8 de janeiro; o mérito está pendente.
  - Datas de corte conferidas: 29/03/2007, 23/01/2020, 10/10/2024, 25/03/2026 e 08/05/2026.
- **Decisão:** todos os achados foram aprovados em 27/10/2026. As correções de código foram aplicadas no branch `claude/kind-keller-0dc0y0` (versão 7.14.8, 81 testes passando, `teste_rev_cap3.py` com um teste por correção). Esse branch não foi mesclado e está na base 7.14.7.
- **Situação no `main` 7.15.1:**
  - corrigido por conta própria: item 1;
  - corrigidos em parte: itens 4 e 7;
  - código já correto: itens 12, 14 e 15;
  - pendentes: os demais.

### Decisões pendentes

1. **Levar as correções para o `main`.** O branch `claude/kind-keller-0dc0y0` parte da 7.14.7, e o `main` já está na 7.15.1, com mudanças nos mesmos trechos. É preciso refazer as correções sobre o `main` (não dá para mesclar direto).
2. **Item 7: nível do item.** O `main` aplica a exceção do Título XII como **alerta**; a correção do branch a trata como **verificar**, com aviso das ADIs. É preciso escolher um dos dois.
3. **Item 11: convenção de contagem.** A correção usa “data-base + lapso”, a convenção que o próprio programa atribui ao SEEU. Isso deixa a estimativa da unificação 1 dia mais tarde que antes. É preciso confirmar.

## Os seis pontos já conhecidos

| Ponto | Veredito | Achado |
|---|---|---|
| Progressão refeita mantém 1/6 para fato anterior a 23/01/2020; a Auditoria diz que o 16% retroage | Confirmado: erro de resultado | 1 |
| Homicídio qualificado ou latrocínio sem “resultado morte”: três tratamentos | Confirmado: erro de resultado | 2 |
| Saída temporária usa a reincidência do SEEU | Confirmado: erro de resultado | 3 |
| Selo de hediondo reconhecido pelo valor da fração | Confirmado e ampliado (milícia com 50% legal recebia o alerta) | 4 |
| 1/6 rotulado “percentual de reincidente” | Confirmado: erro só de texto | 17 |
| Contravenção anterior nunca gera reincidência | Confirmado: erro de fundamento, com resultado favorável ao assistido | 16 |

## Achados

Legenda da coluna “Decisão”: **aprovado** = aprovado em 27/10/2026, sem decisão pendente. **Sim** = depende de decisão sua (ver “Decisões pendentes”).

### Erros de resultado

| Nº | Regra | Problema | Fundamento | Efeito para o assistido | Correção proposta | Prioridade | Decisão | Situação no `main` 7.15.1 |
|---|---|---|---|---|---|---|---|---|
| 1 | 3.4 Progressão refeita; 3.4 Unificação pendente | Mantém o 1/6 do SEEU para fato anterior a 23/01/2020 em crime comum de primário; a Auditoria pede 16%. | LEP, art. 112, I (Lei 13.964/2019); CF, art. 5º, XL; STJ, Tema 1354 (REsp 2.037.377/SC, 18/06/2026) | Data da aba e da petição mais tarde que a correta, cerca de 1/150 da pena remanescente (6 anos ≈ 14 dias). A data da aba diverge da Auditoria. | Usar 16% quando alguma janela a partir do fato prevê 16% (fato até 07/05/2026), primário, sem violência e não hediondo. | Alta | Aprovado | **Corrigido** |
| 2 | 3.6 Vedações; 3.2 Resultado morte | Homicídio doloso ou latrocínio hediondo sem a marcação de morte: o 1/1 do livramento vira alerta, enquanto a progressão fica “verificar”. | LEP, art. 112, VI, a, e VIII; CP, arts. 14, II, e 83, V | Pedido indevido se o crime foi consumado; mensagens contraditórias. | No livramento, “verificar: vedado se consumado; 2/3 se tentado”. | Média | Aprovado | Pendente (corrigido no branch) |
| 3 | 3.7 Fração cumprida | A saída temporária usa a marcação de reincidência do SEEU, não a reincidência pelas datas. | LEP, art. 123, II; CP, art. 63 | Exige 1/4 de quem pode ser primário; requisito “não atendido” indevido. | Reincidência pelas datas: se desmentida, 1/6; se marcada sem base, “a conferir”; se demonstrada, 1/4. | Média | Aprovado | Pendente (corrigido no branch) |
| 4 | 3.2 Hediondos; 3.2 Comando e milícia; 3.6 1/1 lançado no crime | “Selo de hediondo” pelo valor: o percentual do comando de organização criminosa e da milícia, e o 1/1 da revogação do livramento, geram “SEEU tratou como hediondo, mas o tipo não consta do rol”. | LEP, art. 112, VI, b e c; Lei 8.072/90, art. 1º | Alerta falso (milícia com 50% legal) ou duplicado (comando, 1/1); pedido de retificação sem base. | Não emitir o alerta quando a fração coincide com a hipótese do comando ou da milícia, ou quando já há o alerta próprio do 1/1 pela revogação. | Média | Aprovado | **Parcial:** a milícia foi corrigida; o comando com 75% e livramento 1/1 (fato de 2026) ainda recebe o alerta |
| 5 | 3.3 Teste geral | Sem a data do trânsito do processo, o programa usa a do trânsito para o MP para afirmar a reincidência. | CP, art. 63 (trânsito definitivo) | Declara reincidente quem pode não ser; a fração de reincidente do SEEU passa como certa. | Trânsito só para o MP vira indício (“verificar”), não reincidência demonstrada. | Média | Aprovado | Pendente (corrigido no branch) |
| 6 | 3.3 Teste geral (depuração) | Os 5 anos do art. 64, I, contam só da extinção lançada. Não consideram que o período de prova do livramento ou do sursis entra nos 5 anos. | CP, art. 64, I | Pode afirmar reincidência de quem tem a condenação depurada. | Pena anterior extinta por livramento ou sursis, com fato mais de 5 anos após o trânsito: “a conferir”. | Média | Aprovado | Pendente (corrigido no branch) |
| 7 | 3.1 Janelas; 3.2 Lei 15.402 | A exceção do Título XII (crimes contra o Estado Democrático de Direito) não tinha regra. Por ser mais benéfica, ela retroage. | LEP, art. 112, I e II (Lei 15.402/2026); CF, art. 5º, XL | Fato de 08/01/2023 com 25% saía como “confere”; pela lei vigente seria 1/6. | Esperar o caput (1/6) ou o III (20%), como “verificar”, com o aviso das ADIs 7966 a 7969. | Baixa | **Sim** (nível do item) | **Parcial:** a exceção é aplicada, mas como alerta e sem o aviso das ADIs |
| 8 | 3.7 Lei 14.843/2024 | Com só crimes desde 11/04/2024, o programa diz “vedada”, mas a saída para estudo (art. 122, II) continua possível sem crime hediondo ou violento. | LEP, art. 122, II e § 2º (texto vigente) | Pode deixar de apontar a saída para estudo. | Apontar a saída para estudo como “a conferir”. | Baixa | Aprovado | Pendente (corrigido no branch) |
| 9 | 3.3 Reincidência usada no cálculo | No teste crime a crime, uma condenação só de outra execução, sem marcação, já torna o outro crime reincidente. | CP, art. 63 | O alerta 16% × 1/6 cai para “verificar”. | Usar no teste crime a crime a mesma regra do cálculo. | Baixa | Aprovado | Pendente (corrigido no branch) |
| 10 | 3.2 Violência ou grave ameaça | A lista da base marca o art. 148 (sequestro e cárcere privado) como tipo com violência. | CP, art. 148 | A marcação “VGA = S” indevida no 148 não gera alerta (25% em vez de 16%). | Tirar o 148 da lista “S”. | Baixa | Aprovado | Pendente (corrigido no branch) |
| 11 | 3.4 Progressão refeita × unificação | A progressão refeita soma o lapso à data; a estimativa da unificação soma e tira 1 dia. | Convenção de contagem (CP, art. 10) | Diferença de 1 dia entre as duas estimativas. | Usar nas duas a convenção do SEEU (data-base + lapso). | Baixa | **Sim** (confirmar a convenção) | Pendente (corrigido no branch) |

### Erros de fundamento ou citação

| Nº | Regra | Problema | Fundamento | Efeito para o assistido | Correção proposta | Prioridade | Decisão | Situação |
|---|---|---|---|---|---|---|---|---|
| 12 | 3.2 Lei 15.402 (20% × 30%) | O relatório diz “(II, que continua no texto)”; o inciso que continua é o IV. | LEP, art. 112, II e IV (texto vigente) | Nenhum no resultado; citação errada no relatório. | Corrigir o relatório para “inciso IV”. | Baixa | Aprovado | Código já correto; falta corrigir o PDF |
| 13 | 3.8 Progressão antecipada | “Mantido pelo TJMS (1421350-44.2026.8.12.0000)”. O acórdão (2ª Câm. Crim., 14/10/2026) é de ação cautelar: negou efeito suspensivo ao agravo do MP, sem julgar o mérito. | TJMS, 2ª Câm. Crim., 1421350-44.2026.8.12.0000 | Nenhum no resultado; fundamento superestimado. | “O TJMS negou efeito suspensivo ao agravo do MP (cautelar), sem julgar o mérito.” | Baixa | Aprovado | Pendente no código, no LEIA-ME e no PDF (corrigido no branch) |
| 14 | 3.4 Regime inicial (detração) | AgRg no REsp 2.248.958 (5ª T., 09/09/2026) é citado no relatório como “em sentido diverso” sobre a base da fração; o acórdão trata da data-base. | STJ, AgRg no REsp 2.248.958 | Nenhum no resultado. | Descrevê-lo como precedente sobre a data-base, como o código já faz. | Baixa | Aprovado | Código já correto; falta corrigir o PDF |
| 15 | 3.4 Conferência da data-base | HC 1.076.656 é decisão monocrática (Rel. Joel Ilan Paciornik, 04/03/2026), sobre a data-base depois do indulto. | STJ, HC 1.076.656 | Nenhum no resultado. | Citar como monocrática. | Baixa | Aprovado | Código já correto; falta corrigir o PDF |
| 16 | 3.3 Teste geral | “A contravenção anterior não gera reincidência (qualquer que seja o crime novo)”. Para fato novo que é contravenção, a LCP, art. 7º, diz o contrário. | LCP, art. 7º; CP, art. 63 | Favorável ao assistido; não muda alerta contra ele. | Manter o comportamento e declarar no texto que é escolha favorável. | Baixa | Aprovado | Pendente no código e no PDF (corrigido no branch) |

### Erros só de texto

| Nº | Regra | Problema | Fundamento | Efeito para o assistido | Correção proposta | Prioridade | Decisão | Situação |
|---|---|---|---|---|---|---|---|---|
| 17 | 3.3 Crime a crime | O 1/6 da redação anterior aparece rotulado como “percentual de reincidente (16,67%)”. | LEP, art. 112 (redação anterior à Lei 13.964/2019) | Nenhum; rótulo confuso. | “1/6 da redação anterior à Lei 13.964/2019 (igual para primário e reincidente)”. | Baixa | Aprovado | Pendente (corrigido no branch) |
| 18 | 3.4 Progressão refeita (exemplo) | No exemplo, a âncora é 01/03/2026 − 49 dias = **11/01/2026**, e não 10/01/2026. | Conta refeita à mão | Nenhum; o resultado (17/12/2025) não muda. | Corrigir a data no exemplo do relatório. | Baixa | Aprovado | Falta corrigir o PDF |

Ao reescrever o capítulo, também é preciso atualizar as regras alteradas pelos itens 1 a 11 e retirar do item 3.9 e do Capítulo 11 as incoerências resolvidas.

## Teses discutíveis

“Não localizado” quer dizer que a busca no JusRatio não trouxe precedente específico, não que ele não exista.

| Tese (regra) | Corrente favorável ao assistido | STJ | STF | TJMS | Avaliação | Decisão |
|---|---|---|---|---|---|---|
| Validade da Lei 15.402/2026 (3.1) | Vício formal: voltaria a redação da Lei 13.964, com 16% ao primário sem violência para fatos desde 08/05/2026 | Não localizado | ADIs 7966 a 7969; liminar só para o 8 de janeiro; mérito pendente | Não localizado | Acompanhar; não mudar a fração | Sim (acompanhar o julgamento) |
| Reincidente sem violência: 20% (III) × 30% (IV) (3.2) | 20%: inciso mais específico e mais benéfico | Não localizado | Não localizado | Não localizado | Correto como “verificar” | Não |
| Reincidente genérico em hediondo pela Lei 15.358: 70% ou 75% (3.2) | Analogia in bonam partem | Sem precedente sobre a lei nova; a razão dos Temas 1084 e 1196 sustenta | Tema 1169 (razão) | Não localizado | Correto como “verificar” | Não |
| Feminicídio tentado: percentual do hediondo sem morte (3.2) | A hipótese especial pressupõe a morte consumada | Não localizado | Não localizado | Não localizado | Tese defensável; manter “verificar” | Não |
| Ameaça (art. 147) com 25% (3.2) | 16% | HC 1.032.430 (6ª T., 11/03/2026): o percentual segue as elementares do tipo | Não localizado | Não localizado | Correto | Não |
| Reincidência crime a crime na pena unificada (3.3, 3.6) | Só o crime cometido após o trânsito recebe a fração de reincidente | **Contra:** AgRg no HC 790.968 (5ª T., 10/12/2024); AgRg no HC 494.119 (5ª T., 10/09/2019); AgRg no HC 1.086.646/SP (6ª T., 08/10/2026) | Não localizado | Não localizado | Correto como “verificar”, nunca alerta | Não |
| Detração antes da fração (3.4) | Fração sobre a pena total; a detração conta como pena cumprida | **A favor (6ª T.):** AgRg no HC 719.763 (29/03/2022); AgRg no AREsp 2.956.206 (18/03/2026); AgRg no HC 1.039.806/AM (19/08/2026) | Não localizado | Não localizado | Correto | Não |
| 50% sem vedação do livramento para fato anterior a 2020 (3.6) | Retroage o 50%, e o livramento segue pelo art. 83, V | Tema 1196: tese firmada; recurso extraordinário sobrestado | Tema 1319: repercussão geral, mérito pendente | Não localizado | Correto | Não |
| Exame criminológico da Lei 14.843 não alcança fato anterior (3.4) | Irretroatividade | **A favor:** HC 950.729 (6ª T., 03/12/2024); AgRg no HC 974.282 (5ª T., 30/04/2025); EDcl no AgRg no HC 1.091.257/RS (5ª T., 15/09/2026) | RE 1.536.743, repercussão geral reconhecida (13/06/2025) | Não localizado | Correto | Não |
| Primário com maus antecedentes: 1/3 no livramento (3.6) | 1/3 | **A favor (5ª T.):** HC 57.300 (05/12/2006); REsp 751.762 (06/10/2005); HC 39.741 (21/06/2005) | Não localizado | Não localizado | Correto (confirmado depois da revisão) | Não |

## Escolhas de política: riscos

- **Crimes de antes e de depois da Lei 14.843 na saída temporária (“atendido”).** A irretroatividade está confirmada no STJ para o exame criminológico. Não foi localizado precedente sobre condenação nova cumprida junto com a antiga. Risco moderado: apresentar como tese, sem afirmar entendimento firmado.
- **Fração do SEEU menor que a legal sem alerta.** O Tema 1208/STJ permite ao juízo da execução reconhecer reincidência não declarada na sentença, e a data pode ser recalculada para mais. O programa já avisa disso no item “reincidente pela lei”.
- As demais escolhas não trazem risco jurídico relevante.

## Leis e precedentes conferidos

- **LEP, art. 112 (texto vigente):** confere com a base do programa.
- **Leis 15.358/2026, 15.402/2026 e 14.994/2024:** datas de publicação e vigência conferidas.
- **CP, art. 83, e LEP, art. 122 (textos vigentes):** conferem com o programa.
- **Precedentes qualificados:** Temas 1084, 1196 e 1354 do STJ, e Tema 1169 do STF; teses conferidas.
- **Tema 1195/STJ:** a tese trata da falta nos 12 meses do Decreto 9.246/2017 (comutação); o uso por analogia está correto.
- **Acórdãos e decisões do STJ:**
  - AgRg no HC 675.062 e HC 947.647 (reincidente genérico em crime violento: 25%);
  - HC 1.032.430 (importunação sexual: sem os 25%);
  - AgRg no HC 790.968 e AgRg no HC 494.119 (reincidência na pena unificada);
  - HC 950.729 e AgRg no HC 974.282 (exame criminológico);
  - AgRg no HC 719.763 e AgRg no AREsp 2.956.206 (detração);
  - AgRg no REsp 2.248.958 (data-base);
  - HC 1.076.656 (monocrática, data-base depois do indulto);
  - HC 57.300, REsp 751.762 e HC 39.741 (maus antecedentes, 1/3).
- **Súmulas:** 441 e 534 do STJ e SV 26 conferidas.

## Pontos não confirmados

1. Precedentes do STJ, STF ou TJMS sobre:
   - feminicídio tentado e o percentual especial;
   - 20% × 30% da Lei 15.402;
   - analogia do reincidente genérico na Lei 15.358;
   - condenação nova somada à antiga na saída temporária (Lei 14.843);
   - a ameaça (art. 147) com 25%.
2. **RE 1.536.743** (exame criminológico): número do tema no STF (o programa diz Tema 1408) e situação do mérito.
3. **Situação atual das ADIs 7966 a 7969** contra a Lei 15.402/2026: não foi localizada decisão do Plenário.
4. **HC 1.076.656:** o inteiro teor trata da data-base depois do indulto, mas a conclusão sobre o indulto parcial não foi lida até o fim.
5. **Súmulas não reconferidas na fonte:** 40, 471, 526, 533, 535 e 617 do STJ; SV 56; Tema 445/STJ; Tema 1319/STF (só a anotação do STJ foi vista).
6. **Datas de vigência não reconferidas na fonte oficial:** Lei 11.464/2007 (29/03/2007), Lei 13.964/2019 (23/01/2020), Lei 14.843/2024 (11/04/2024) e Lei 10.792/2003 (02/12/2003).
7. **Precedentes fora do núcleo do capítulo:** RHC 267.297 AgR (STF); HC 575.933, HC 41.579 e HC 23.973 (STJ).
