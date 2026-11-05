# Revisão jurídica — Capítulo 1 (Leitura do RSPE e situação da execução)

- **Versão revisada:** APTO 7.14.7 (relatório técnico-jurídico, cap. 1, p. 5-31; contexto: apresentação e cap. 11).
- **Data da revisão:** 27/10/2026. Lei vigente em outubro de 2026, inclusive Leis 14.843/2024, 15.358/2026 e 15.402/2026.
- **Etapa:** primeira (só revisão; nenhum código alterado). Relatório em PDF: [`cap1-leitura.pdf`](cap1-leitura.pdf).
- **Método:** cada regra conferida contra a lei (JusRatio e textos dos decretos no repositório), contra o código e pelo exemplo refeito à mão. Casos rodados no programa: só fictícios. Nenhum nome real.
- **Conferência posterior (05/11/2026) no main 7.15.1:** os casos fictícios foram rodados de novo. A4 e A7 já foram corrigidos nessa versão; os demais continuam como descritos.

## Resumo

| Regras revisadas | Corretas | Erros de resultado | Erros de fundamento ou citação | Erros só de texto | Teses discutíveis |
|---|---|---|---|---|---|
| 79 | 67 | 8 | 3 | 2 | 4 |

17 achados em 12 regras. Prioridade: 1 alta, 6 médias, 10 baixas. Os cinco pontos já conhecidos foram todos confirmados: art. 75 (A5), escala 1-7 (C1), data-base com crime sem trânsito (A1), Falta até a emissão (A3) e data-base da regressão (A6).

As 17 contas dos exemplos do capítulo foram refeitas à mão e bateram com o relatório.

## Achados

Coluna "Decisão": **sim** = depende de escolha do usuário antes de corrigir; **não** = correção decorre da lei ou da política já decidida.

| Nº | Regra | Problema | Fundamento | Efeito para o assistido | Correção proposta | Tipo | Prioridade | Decisão | Situação no 7.15.1 |
|---|---|---|---|---|---|---|---|---|---|
| A1 | 1.7 Ajustes da data-base calculada (p. 23), ajuste 3 — ponto conhecido 3 | Sem data-base do SEEU, o programa move a data-base para a nova prisão sempre que há crime com fato entre a soltura e essa prisão, sem exigir trânsito nem falta homologada. A coluna Falta exige trânsito para o mesmo crime; a recaptura sem falta homologada mantém a data-base. Caso fictício: progressão 10/03/2022, soltura 01/02/2023, crime sem sentença 01/06/2023, flagrante 05/06/2023 → data-base 05/06/2023. O relatório descreve o código; a regra está errada. | LEP, art. 112, § 6º; Súmulas 526 e 533/STJ; STJ, Tema 1006. | Perde, para a progressão, o tempo cumprido entre a data-base antiga e a soltura (328 dias no exemplo). | Mover só com falta homologada ou condenação transitada pelo crime; sem isso, manter a última alteração de regime, em amarelo: "crime no período sem trânsito nem falta reconhecida — conferir". | Erro de resultado | Alta | não | Pendente |
| A2 | 1.10 Coluna Conduta (p. 29) — saída temporária e progressão antecipada | Falta "SIM" nos 12 meses dá "não atende", mesmo quando o lapso contado da falta já foi cumprido. | LEP, art. 112, § 7º. TJMS: 1ª Câm. Crim., 1608385-84.2025.8.12.0000 (11/06/2026) e 1604752-31.2026.8.12.0000 (13/10/2026); 2ª Câm. Crim., 1604657-98.2026.8.12.0000 (13/10/2026). STJ, HC 1.112.988 (monocrática, 08/10/2026). | Benefício apontado como incabível quando pode caber. | Com lapso posterior à falta cumprido: "a conferir — conduta readquirida (LEP, art. 112, § 7º)". | Erro de resultado | Média | não | Pendente |
| A3 | 1.10 Coluna Falta (12 meses) (p. 28) — ponto conhecido 4 | A janela termina na emissão do RSPE; saída temporária e progressão antecipada contam até hoje. Falta de 13 meses atrás pode aparecer "SIM" na coluna e no livramento. | CP, art. 83, III, "b". | Livramento pode parecer barrado por falta já fora do prazo. | Contar até hoje na coluna e no livramento; manter no detalhe a leitura na data do RSPE. | Erro de resultado | Média | sim (a coluna foi pensada como retrato do documento) | Pendente |
| A4 | 1.7 Data-base do operador e progressão refeita (p. 23) | 1/6 vira 16% só para fatos de 23/01/2020 a 07/05/2026; fato anterior a 23/01/2020 fica com 1/6, embora a Auditoria diga que o 16% retroage. | LEP, art. 112, I (Lei 13.964/2019); CF, art. 5º, XL; CP, art. 2º, par. único; STJ, Tema 1354. | Progressão alguns dias mais tarde (pena de 8 anos: cerca de 19 dias). | Aplicar 16% a todo fato até 07/05/2026 de primário, sem violência, não hediondo. | Erro de resultado | Média | não | **Corrigido** (fato de 10/01/2019 → 16%) |
| A5 | 1.8 Limite do art. 75 (p. 25) — ponto conhecido 1 | Com o alerta, a coluna Término da lista mostra o término máximo com "*"; a aba Extinção mantém a data do SEEU com ressalva. Duas datas para o mesmo término. O máximo em si está certo. | Política decidida: a aba mantém a data do SEEU com ressalva e a Auditoria alerta. | Operador pode pedir com uma data e ver outra; vencimentos com datas diferentes. | Na lista, data do SEEU com sinal de ressalva e o máximo na dica (ou mudar também a Extinção). | Erro de resultado (divergência interna) | Média | sim (qual das duas datas mostrar) | Pendente |
| A6 | 1.7 Data-base calculada — regressão com falta homologada (p. 22-23) — ponto conhecido 5 | A tela mostra a data da falta; o dado gravado é a data da regressão; a planilha "Completo" e o resumo usam o gravado. Caso fictício: gravado 20/02/2025, tela 05/01/2025. | Súmula 534/STJ; STJ, Tema 709. | Planilha com data-base mais tardia. | Gravar e exportar a data-base calculada com o motivo, ou exportar as duas com rótulos claros. | Erro de resultado (só na planilha) | Baixa | sim (formato da planilha) | Pendente |
| A7 | 1.4 Incompatibilidade de regime que o SEEU não contou (p. 17) | O programa corta o período "aguardando vaga" em todas as áreas, sem alerta. | Súmula Vinculante 56/STF; política para monitoramento lançado como interrupção. | Tempo cumprido some de progressão, indulto e término sem aviso. | Manter a conta do SEEU e criar item na Auditoria pedindo o cômputo (SV 56). | Erro de resultado (lacuna) | Média | não | **Corrigido** (a Auditoria agora alerta "espera de vaga lançada como interrupção") |
| A8 | 1.7 Data-base calculada quando o SEEU não a imprime (p. 22) | Sem data de referência, usa a data da decisão de progressão. | STJ, Tema 1165 (decisão declaratória; vale a data do preenchimento do último requisito). | Data-base mais tardia (situação rara). | Amarelo: "data de referência ausente: a data-base é a do preenchimento dos requisitos (Tema 1165) — conferir". | Erro de resultado (lacuna) | Baixa | não | Pendente |
| B1 | 1.3 Violência ou grave ameaça (p. 15) | O relatório diz que os Temas 1336/STJ e 1400/STF são citados para dizer que a VGA não é vedação geral dos decretos. Nenhum trata de violência: o 1336 diz que o indulto de 2023 não alcança o tráfico do caput e § 1º (salvo privilegiado); o 1400 (RE 1.542.482) diz que é constitucional indultar o tráfico privilegiado. No código, as citações estão no tráfico privilegiado (correto), salvo uma nota interna. O relatório está errado. | Teses conferidas no JusRatio. | Nenhum no resultado; risco de citação errada em peça. | Fundamentar a VGA no próprio decreto (art. 9º); Temas 1336 e 1400 só no tráfico privilegiado, com a SV 63. | Erro de citação | Baixa | não | Pendente |
| B2 | 1.8 Art. 75 — texto do alerta | "Término máximo em ..., antes ainda com o desconto de N remidos" sugere que a remição encurta o limite. A data na coluna não desconta (correto). | STJ e STF: remição sobre a pena total, não sobre o limite (Súmula 715/STF; STJ, AgRg no HC 331.882; HC 426.786; AgRg no HC 903.986; STF, HC 242.974). Corrente favorável: LEP, art. 128. | Risco de pedido com tese rejeitada sem aviso. | Reescrever: "pela jurisprudência do STJ e do STF, a remição abate da pena total, não do limite; tese contrária possível (LEP, art. 128)". | Erro de fundamento | Baixa | não | Pendente |
| B3 | 1.10 Coluna Falta — fuga "só impede se reconhecida (STJ, Tema 1195)" | O Tema 1195 (Decreto 9.246/2017) diz que a falta nos 12 meses conta mesmo se apurada depois, salvo mora do Estado; não sustenta a frase. Tese retificada em embargos em 10/06/2026. | Tema 1195/STJ; Súmula 533/STJ. | Nenhum no resultado; citação inadequada. | Trocar por Súmula 533/STJ; Tema 1195 só nos decretos, com o sentido certo. | Erro de citação | Baixa | não | Pendente (a Auditoria já cita Súmula 533 e Tema 1195 juntos; a coluna Falta não mudou) |
| C1 | 1.11 Escala de prioridade de 1 a 7 (p. 31) — ponto conhecido 2 | A escala e a "fila de prioridade do relatório geral" existem no código e não são usadas; o LEIA-ME as cita nas notas das versões 6.10.x. | Não se aplica. | Nenhum. | Retirar o código sem uso ou marcar as notas como históricas. | Erro só de texto | Baixa | sim (retirar ou só anotar) | Pendente |
| C2 | 1.10 Prescrição da falta disciplinar (p. 29) | "A mais antiga ... isto é, 26/12/2023": a mais antiga é a primeira (em 26/10/2026, 27/10/2023) e muda a cada dia. O código está certo; o texto não. | Não se aplica. | Nenhum. | Corrigir o texto do relatório. | Erro só de texto | Baixa | não | Pendente |
| D1 | 1.9 Não iniciou o cumprimento (p. 27) e 1.7 ajuste 3 | Prisão provisória encerrada antes do trânsito vira detração e a contagem começa na nova prisão. | Favorável: data-base na prisão cautelar, lapso sobre a pena total. STJ: Tema 1457 afetado em 16/06/2026 (REsp 2.266.131), sem tese. STF e TJMS: não confirmado. | Pode atrasar a progressão de quem foi preso, solto e preso de novo. | Citar o Tema 1457 pendente no ponto discutível e no motivo da data-base; estimar pela corrente favorável na Auditoria, como "verificar". | Tese discutível | Média | sim | Pendente (a frente "não iniciou" do 7.14.8 não trata do Tema 1457) |
| D2 | 1.3 Hediondez — homicídio simples com selo | Selo mantido (pode ser grupo de extermínio); benefícios "a verificar". | Favorável: hediondo só com grupo de extermínio reconhecido na sentença (Lei 8.072/90, art. 1º, I). Tribunais: não confirmado. | Coluna "hediondo" e resumo podem indicar hediondez não reconhecida. | Resumo: "hediondo a verificar (grupo de extermínio não informado)". | Tese discutível | Baixa | sim | Pendente |
| D3 | 1.8 Art. 75 com fatos antes e depois de 23/01/2020 (p. 26) | 30 anos para as penas dos fatos anteriores, com "verificar". | Favorável: CF, art. 5º, XL. Contrária: 40 anos ao conjunto. Tribunais: não confirmado. | Nenhum além do aviso. | Manter. | Tese discutível | Baixa | sim (manter a tese) | Sem mudança necessária |
| D4 | 1.3 Hediondez — homicídio do art. 121, § 2º-D (Lei 15.358/2026) | Sem selo: não hediondo; com selo: hediondo. | Favorável: Lei 8.072, art. 1º, I, fala em "art. 121, § 2º"; o § 2º-D não está escrito no rol. Jurisprudência: não localizada. | Fração de 70% ou mais quando a lei pode não exigir. | Com selo: "hediondo a verificar (§ 2º-D fora do texto do art. 1º, I)". | Tese discutível | Baixa | sim | Pendente |

### Posição dos tribunais nas teses discutíveis

| Achado | Corrente favorável | STJ | STF | TJMS |
|---|---|---|---|---|
| D1 | Data-base na prisão cautelar | Tema 1457 afetado, sem tese | Não confirmado | Não confirmado |
| D2 | Hediondo só com grupo de extermínio reconhecido | Não confirmado | Não confirmado | Não confirmado |
| D3 | 30 anos para fatos anteriores | Não confirmado | Não confirmado | Não confirmado |
| D4 | § 2º-D fora do rol | Sem precedente localizado | Sem precedente localizado | Sem precedente localizado |
| B2 | Remição abate o limite (LEP, art. 128) | Contrário | Contrário (HC 242.974; Súmula 715) | Não confirmado |
| A2 | Conduta readquirida com o lapso | Favorável (HC 1.112.988, monocrática) | Não confirmado | Favorável (1ª e 2ª Câmaras) |

## Conferido e correto (destaques)

- Rol de hediondos da base jurídica igual ao texto vigente da Lei 8.072/90, art. 1º (vicaricídio, I-A "c", XI, XII, ECA arts. 240 § 1º e 241-B, domínio social estruturado), com as datas de corte.
- Tráfico privilegiado não hediondo (LEP, art. 112, § 5º; STF, HC 118.533; SV 63). Homicídio qualificado-privilegiado não hediondo (STJ, HC 41.579 e HC 23.973).
- Fuga como falta permanente e prescrição da recaptura (STJ, HC 527.625; AgRg no HC 779.723); prazo de 2 anos antes da Lei 12.234/2010 (HC 140.870); 3 anos depois.
- Súmula 534/STJ, Temas 709 e 1006/STJ (salvo A1, A6 e A8); art. 75 com 30/40 anos, dia do começo incluído e Súmula 715/STF; SV 56 na incompatibilidade.
- Decretos 12.338/2024 e 12.790/2025: art. 3º, I e III, e art. 13, § 5º, conferidos no texto.
- Texto atual do art. 112 da LEP (Leis 14.843/2024, 15.358/2026 e 15.402/2026). Lei 15.358/2026 em vigor desde 25/03/2026.

## Não confirmado

1. Data de vigência da Lei 15.402/2026 (08/05/2026): texto confirmado; a data veio só do programa.
2. Data de vigência da Lei 15.384/2026 (vicaricídio, 10/04/2026 na base): texto confirmado; a data, não.
3. Tema 1195/STJ: texto da tese depois da retificação em embargos (10/06/2026).
4. Temas 1126 e 1457/STJ: "afetado", sem tese, na base consultada (atualização de 24/09/2026); pode ter havido julgamento depois.
5. Posição do TJMS sobre A1, B2, D3, A4 e D1.
6. Precedente do STJ que aplique o 16% expressamente a fato anterior a 23/01/2020 (A4 se apoia na CF, no CP e no Tema 1354).
7. Jurisprudência sobre hediondez do homicídio simples com selo (D2) e do § 2º-D (D4).
8. Datas de vigência das Leis 12.015/2009, 12.234/2010, 12.850/2013, 13.641/2018, 13.718/2018 e 13.964/2019: coerentes com o conhecimento geral, não conferidas na fonte oficial.
9. STF, Tema 758 (falta por crime doloso exige apuração com contraditório): não citado por não ter sido conferido.

## Onde está no código (referência do 7.14.7)

| Achado | Local |
|---|---|
| A1 | `rspe_view.py`, `data_base_calculada` (crime no período) |
| A2 | `rspe_view.py`, `_conduta_requisito` |
| A3 | `rspe_scraper.py`, `faltas` (janela pela geração); `rspe_view.py`, `falta_12m_hoje` |
| A4 | `rspe_view.py`, `_fr_prog_refeita` |
| A5 | `rspe_view.py`, coluna Término (`_l75`) × aba Extinção |
| A6 | `rspe_scraper.py`, `situacao_execucao` (`data_base`); `rspe_export.py`, aba "Completo" |
| A7 | `rspe_scraper.py`, `incompatibilidade_pelo_seeu` |
| A8 | `rspe_scraper.py`, `situacao_execucao` (referência ou decisão) |
| B1 | relatório, p. 15; `rspe_scraper.py`, `triagem_indulto` (nota interna) |
| B2 | `rspe_auditoria.py`, alerta `limite-de-cumprimento-art-75` |
| B3 | `rspe_scraper.py`, indícios de falta (texto da fuga) |
| C1 | `rspe_view.py`, `prioridade`/`aplicar_prioridade`; `rspe_relatorio.py`, `fila_prioridade`; `LEIA-ME.txt` (notas 6.10.x) |
| C2 | relatório, p. 29; `rspe_scraper.py`, `corte_faltas` |

## Próxima etapa

Só depois da aprovação: correções num branch próprio, um teste com caso fictício para cada uma, `python3 testes.py` completo e PR apenas quando pedido. Ordem sugerida: A1, A2, A3, A5, D1; depois os de prioridade baixa.
