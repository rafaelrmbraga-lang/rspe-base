# Revisão jurídica — Cap. 2: Leitura da ficha disciplinar (SIAPEN)

- **Relatório revisado:** APTO 7.14.7, relatório técnico-jurídico de outubro de 2026 (aba Remição e ficha disciplinar), Cap. 2.
- **Data da revisão:** 27/10/2026. Situação dos achados reconferida em 05/11/2026 no código da `main` (versão 7.15.1).
- **Etapa:** só revisão. Nenhum código foi alterado.
- **Relatório em PDF:** [cap2-ficha_APTO_7.14.7.pdf](cap2-ficha_APTO_7.14.7.pdf) (reflete a versão 7.14.7).
- Sem dados reais: todos os casos citados são fictícios.

## Resumo

| Item | Resultado |
|---|---|
| Regras revisadas | 86 (itens 2.1 a 2.18) |
| Sem achado | 72 |
| Achados | 14 (em 14 regras) |
| Erro de resultado | 8 (alta 2, média 4, baixa 2) |
| Erro de fundamento ou citação | 3 |
| Erro só de texto | 1 |
| Tese discutível | 2 |
| Pontos já conhecidos (6) | todos confirmados na 7.14.7 |
| `python3 testes.py` na 7.14.7 | 80 de 80 passam |

**Situação na `main` (7.15.1):** 3 corrigidos (1, 5 e 10), 2 corrigidos em parte (2 e 9) e 9 abertos.

Nas 72 regras sem achado, a lei e o exemplo foram conferidos. O código foi conferido por amostra, não linha a linha.

## Achados

Legenda: **Decisão sua?** = a correção depende de uma escolha de política ou de tese, não só de corrigir o programa.

### 1. Ano digitado errado no trecho do atestado, com trabalho sem baixa (2.8; 2.1) — ponto conhecido
- **Tipo:** erro de resultado. **Prioridade:** alta. **Decisão sua?** Não.
- **Problema:** sem baixa, o fim do trabalho era a data máxima do calendário. Somar 3 dias a ela dava erro de data, e a análise do histórico inteiro caía: a ficha ficava sem trabalho, estudo, atestados e faltas. Caso fictício: FAXINA desde 01/07/2022, sem baixa, e atestado "(01/07/2023 A 05/10/2022)".
- **Fundamento:** LEP, art. 126. Os dias trabalhados existem; a falha é só de leitura.
- **Efeito para o assistido:** remição, estudo, faltas e os incisos XI a XIII dos decretos sumiam da ficha.
- **Correção proposta:** com o trabalho sem baixa, usar a data de impressão (ou hoje) como fim. Isolar a conferência de cada atestado, para que uma falha deixe só aquele atestado "a conferir".
- **Situação na 7.15.1:** corrigido. O mesmo caso agora lê o atestado com "ano corrigido".

### 2. Fuga lida da ficha sem o filtro de falsas fugas (2.13) — ponto conhecido, com extensão
- **Tipo:** erro de resultado. **Prioridade:** alta. **Decisão sua?** Não.
- **Problema:** "Tentativa de fuga frustrada pelo agente", "sob pena de evasão" e "será considerado evasão" geravam "FALTA GRAVE - FUGA/EVASÃO NA FICHA DISCIPLINAR (SIAPEN)" pendente. **Extensão:** a regra "Indícios do RSPE explicados pela ficha" (até 120 dias antes) também lê o texto bruto. Assim, um "sob pena de evasão" transforma uma regressão sem falta em falta grave datada.
- **Fundamento:** LEP, art. 50, II; art. 49, p. ú. (a tentativa é punida, mas como outra falta); STJ, HC 527.625 (fuga é falta permanente; conferido).
- **Efeito para o assistido:** falta grave inexistente; indulto e comutação ficam "a verificar"; a data-base sugerida pode mudar.
- **Correção proposta:** aplicar o filtro `_sem_fuga_falsa` nas duas regras.
- **Situação na 7.15.1:** corrigido em parte. As faltas da ficha já usam o filtro, mas a regra dos indícios (`explicar_indicios_ficha`, com `RE_FALTA_NA_FICHA`) ainda lê o texto sem ele.

### 3. ENEM tratado como exame que não certifica (2.11; inciso XIII em 2.9)
- **Tipo:** erro de resultado e de fundamento. **Prioridade:** média. **Decisão sua?** Sim: confirmar a partir de qual edição o ENEM volta a certificar e se o programa deve aceitar o certificado do ENEM.
- **Problema:** o relatório e o código afirmam que "o ENEM não certifica a conclusão do ensino médio desde 2017". O código só aceita o certificado de conclusão do ENCCEJA.
- **Fundamento:** STJ, Tema 1270 (REsp 2.115.433/SP, 3ª Seção, j. 08/10/2026, DJEN 23/10/2026). Segundo o tema, a Portaria MEC 382/2025 restaurou a certificação pelo ENEM (450 pontos por área e 500 na redação), cada área vale 20 dias, e o acréscimo de 1/3 cabe só com aprovação plena que certifique. STJ, Tema 1357.
- **Efeito para o assistido:** o certificado do ENEM não conta no inciso XIII (fica "a verificar") e o acréscimo de 1/3 (LEP, art. 126, § 5º) não é apontado.
- **Correção proposta:** aceitar o ENEM como conclusão certificada quando a ficha registrar o certificado de conclusão e a edição for coberta pela Portaria MEC 382/2025. Atualizar o texto e citar os Temas 1270 e 1357.
- **Situação na 7.15.1:** aberto.

### 4. Matrícula sem o prefixo "EDUCAÇÃO:" (2.9) — ponto conhecido
- **Tipo:** erro de resultado. **Prioridade:** média. **Decisão sua?** Não.
- **Problema:** "Matriculou-se na Série: ..." sem o prefixo não abre estudo.
- **Fundamento:** LEP, art. 126, § 1º, I; Decretos 12.338/2024 e 12.790/2025, art. 9º, XII.
- **Efeito para o assistido:** o estudo some; a remição por estudo não é sugerida; o inciso XII pode ficar "não atende".
- **Correção proposta:** aceitar a matrícula transcrita sem o prefixo.
- **Situação na 7.15.1:** aberto (reproduzido).

### 5. "CICLO Nº 03/2020" não reconhecido (2.10) — ponto conhecido
- **Tipo:** erro de resultado. **Prioridade:** média. **Decisão sua?** Não.
- **Problema:** com "Nº", o lançamento ficava sem ciclo, sem meses e sem obras.
- **Fundamento:** LEP, art. 126; Resolução CNJ 391/2021, art. 5º (texto não confirmado).
- **Efeito para o assistido:** a remição pela leitura não casava com o documento.
- **Correção proposta:** aceitar "CICLO N/Nº/N°/NO".
- **Situação na 7.15.1:** corrigido (o ciclo é reconhecido com "Nº").

### 6. Conduta readquirida pelo requisito temporal (2.13, "Conduta má sem falta recente")
- **Tipo:** erro de resultado (lacuna). **Prioridade:** média. **Decisão sua?** Não.
- **Problema:** o alerta só considera o prazo de 1 ano da falta. Com falta grave recente, sem regressão e com o novo requisito temporal já cumprido, a lei considera o bom comportamento readquirido, e o programa não mostra nada. O texto do alerta cita o prazo do RIBUP (12 meses do cumprimento da sanção), mas a conta usa a data do fato.
- **Fundamento:** LEP, art. 112, § 7º: "após 1 (um) ano da ocorrência do fato, ou antes, após o cumprimento do requisito temporal exigível" (conferido). TJMS, 1603197-76.2026.8.12.0000 e 1604181-94.2025.8.12.0000 (3ª Câm.) e 1605442-31.2024.8.12.0000 (1ª Câm.), todos conferidos.
- **Efeito para o assistido:** o pedido de progressão pode atrasar.
- **Correção proposta:** alertar também quando a data da progressão refeita for anterior a "fato + 1 ano"; ajustar o texto para dizer que a conta segue a LEP.
- **Situação na 7.15.1:** aberto.

### 7. Monitoramento cautelar contado inteiro como detração (2.6)
- **Tipo:** erro de fundamento e tese discutível. **Prioridade:** média. **Decisão sua?** Sim: qual tese o programa adota.
- **Problema:** pelos autos de uma ação penal, todo o período de monitoramento vira detração, com citação do Tema 1155. Esse tema trata do recolhimento noturno e nos dias de folga, contado em horas e convertido em dias. Monitoramento sem recolhimento não é o caso do tema.
- **Fundamento:** STJ, Tema 1155 (REsp 1.977.135, 3ª Seção, j. 23/11/2022), conferido. Contra a detração sem recolhimento: STJ, AgRg no HC 1.078.634 (5ª T., j. 27/05/2026), AgRg no HC 968.518 (5ª T., 2025) e AgRg no HC 742.154 (5ª T., 2022). Corrente favorável ao assistido: detração integral, porque há restrição da liberdade (analogia com o art. 42 do CP). STJ: contra. STF e TJMS: não pesquisados.
- **Efeito para o assistido:** petição com fundamento impróprio. O item já é só "verificar", e a data do SEEU fica mantida.
- **Correção proposta:** separar três casos: (a) monitoramento pelos autos da execução = cumprimento de pena; (b) cautelar com recolhimento noturno = Tema 1155, em horas convertidas em dias; (c) só monitoramento = "tese defensiva; STJ contra".
- **Situação na 7.15.1:** aberto (o texto ainda cita o Tema 1155 para o monitoramento cautelar).

### 8. Isolamento preventivo presumido como falta grave (2.13)
- **Tipo:** tese discutível (fundamento impreciso). **Prioridade:** média. **Decisão sua?** Sim.
- **Problema:** o isolamento preventivo com PADIC, sem a natureza da falta, vira "indício de falta grave", com base no art. 57, p. ú. Mas o isolamento preventivo (art. 60) vale para qualquer faltoso e não é sanção.
- **Fundamento:** LEP, arts. 49, 57, p. ú., e 60 (conferidos). Corrente favorável ao assistido: sem a natureza, não se presume falta grave. STJ, STF e TJMS: não pesquisados especificamente.
- **Efeito para o assistido:** indulto e comutação podem ficar "a verificar" por uma falta que pode ser leve ou média.
- **Correção proposta:** no isolamento só preventivo, registrar "falta de natureza a confirmar", fora das janelas dos decretos, até haver a natureza ou o resultado.
- **Situação na 7.15.1:** aberto.

### 9. Dias de monitoramento sem o dia do começo (exemplo de 2.6)
- **Tipo:** erro de resultado (1 dia). **Prioridade:** baixa. **Decisão sua?** Não.
- **Problema:** o período de 05/03/2023 a 01/12/2023 dava 271 dias. Incluindo o dia do começo (CP, art. 10), são 272.
- **Fundamento:** CP, art. 10; convenção de contagem do próprio relatório.
- **Efeito para o assistido:** a estimativa da progressão sai 1 dia mais tarde.
- **Correção proposta:** contar os dois extremos, como na detração de 2.5.
- **Situação na 7.15.1:** corrigido em parte. O dia a mais só entra quando o fim é a saída do monitoramento; conferir os outros fins (retomada no RSPE, próxima interrupção, impressão).

### 10. Regressão judicial sem a palavra "falta" ignorada (2.13, "Narrativas") — ponto conhecido
- **Tipo:** erro de resultado (lacuna). **Prioridade:** baixa. **Decisão sua?** Não.
- **Problema:** o filtro geral barrava a regressão judicial que não citava falta disciplinar, falta grave ou conselho. O relatório descreve esse limite.
- **Fundamento:** LEP, art. 118, I.
- **Efeito para o assistido:** em geral favorável (a fuga seguia "pendente"), mas a leitura ficava incompleta.
- **Correção proposta:** deixar a regressão por evasão chegar à regra só para casar com a fuga já registrada na ficha.
- **Situação na 7.15.1:** corrigido (a regressão por evasão sem "falta" agora homologa a fuga da ficha).

### 11. Citações da perda de remidos (2.13, "Falta anterior registrada na ficha e perda de remidos")
- **Tipo:** erro de fundamento. **Prioridade:** baixa. **Decisão sua?** Não.
- **Problema:** o HC 398.850 sustenta o limite do período entre as faltas. Os HCs 293.475 e 377.088 tratam de outra tese: o teto de 1/3 no total, e não 1/3 por falta. O "TJDFT, Acórdão 1230029" não foi localizado por esse número.
- **Fundamento:** LEP, art. 127; STJ, HC 398.850 (5ª T., j. 13/06/2017), conferido. TJDFT com a mesma tese: 0716724-08.2019.8.07.0000 (3ª T. Crim., j. 06/02/2020), 0709216-35.2024.8.07.0000 e 0710789-16.2021.8.07.0000.
- **Efeito para o assistido:** nenhum no resultado; risco de citação imprópria na petição.
- **Correção proposta:** manter o HC 398.850, usar os HCs 293.475 e 377.088 só para o teto de 1/3 e trocar o número do TJDFT pelo CNJ conferido (em `rspe_auditoria.py`, `FUND_127`, e em `base_juridica.json`).
- **Situação na 7.15.1:** aberto.

### 12. Fundamento da CD simplificada (2.13, "CD simplificada (semiaberto) e falta justificada")
- **Tipo:** erro de fundamento. **Prioridade:** baixa. **Decisão sua?** Não.
- **Problema:** o relatório cita "LEP, art. 50, V", que é o descumprimento das condições do regime aberto. Faltar ao pernoite no semiaberto não se enquadra nesse inciso.
- **Fundamento:** LEP, art. 50, V (conferido).
- **Efeito para o assistido:** nenhum na conta.
- **Correção proposta:** citar "LEP, art. 50 (inciso conforme o fato) e RIBUP-MS", ou o inciso II quando a ausência for tratada como fuga.
- **Situação na 7.15.1:** aberto (texto do relatório).

### 13. Sexta-feira Santa como feriado nacional (2.7, "Jornada de trabalho")
- **Tipo:** erro de fundamento. **Prioridade:** baixa. **Decisão sua?** Sim: manter a data na estimativa como feriado municipal ou retirá-la.
- **Problema:** a Sexta-feira Santa não está na Lei 662/1949; é feriado religioso declarado por lei municipal (Lei 9.093/1995).
- **Fundamento:** Leis 662/1949 e 9.093/1995 (não conferidas na fonte).
- **Efeito para o assistido:** a estimativa de dias trabalhados pode perder 1 dia por ano.
- **Correção proposta:** marcar a data como feriado municipal e conferir a lei estadual do 11/10.
- **Situação na 7.15.1:** aberto (`feriados()` ainda a inclui na lista nacional).

### 14. Nome do setor absorve o começo do lançamento (2.8, "Trechos de um mesmo atestado") — ponto conhecido
- **Tipo:** erro só de texto. **Prioridade:** baixa. **Decisão sua?** Não.
- **Problema:** o setor sai como "Atestado de Trabalho Prisional nº 010/2023 Faxina".
- **Fundamento:** LEP, art. 126.
- **Efeito para o assistido:** nenhum na conta; a exibição fica poluída.
- **Correção proposta:** cortar o nome do setor depois do número do atestado.
- **Situação na 7.15.1:** aberto (reproduzido).

## Conferido e sem achado (principais pontos)

- **Decretos 12.338/2024 e 12.790/2025 (texto oficial):** art. 6º e art. 9º, IV, XI, XII e XIII.
- **Faltas:** a sanção do Conselho Disciplinar não é reconhecimento em juízo (art. 6º dos decretos). A prescrição da falta é de 3 anos e, na fuga, conta da recaptura (STJ, HC 527.625 e AgRg no HC 779.723).
- **Precedentes:** Súmula Vinculante 56 e RE 641.320; Súmulas 534 e 441 e Tema 709 do STJ.
- **Contas dos exemplos de 2.4 e 2.5:** certas (77, 19, 183 e 144 dias).
- **Leis 15.358/2026 e 15.402/2026:** no texto compilado da LEP, mudaram só o art. 112 (caput, incisos e frações). Os arts. 49, 50, 52, 57, 60, 112, § 7º, 122 a 127 e 146-B/C não mudaram.

## Não confirmado

- Resolução CNJ 391/2021, arts. 3º e 5º: texto não consultado. Os valores do ENEM foram confirmados pelo Tema 1270. O valor da leitura (4 dias por obra, até 12 obras por ano) não foi confirmado.
- Portaria MEC 382/2025: texto não lido; a edição inicial da certificação pelo ENEM não foi confirmada.
- TJDFT, "Acórdão 1230029": número não localizado; o provável correspondente é o 0716724-08.2019.8.07.0000.
- RIBUP-MS (Decreto Estadual 12.140/2006), arts. 133 e 136, e prazos de reabilitação para falta leve e média.
- Lei estadual MS 10/1979 (11/10); Leis 662/1949, 6.802/1980, 14.759/2023 e 9.093/1995.
- Leis 15.358/2026 e 15.402/2026: texto integral não lido (conferido o texto compilado da LEP).
- Posição do TJMS e do STF sobre a detração do monitoramento sem recolhimento.
- STJ, HC 140.870 (citado na base jurídica, não no Cap. 2).
