# APTO: relatórios em PDF e exportação em Excel. Diagnóstico de design

Escopo: `rspe_relatorio.py` (ReportLab 5.0.1) e `rspe_export.py` (openpyxl), vistos como peças impressas e de leitura.
Dados usados: só os fictícios, de uma cópia de `Comarca_Ficticia.sqlite` (144 assistidos "Simulado Caso NNN"). A data de referência é 12/10/2026, fixada pela ponte.

Peças geradas com a `Api` real (ponte):
- `relatorio_um`: relatórios individuais dos casos 001 (prescrição aparente e indulto cabível), 002 (indulto a verificar ou cabível), 055 (fuga e cálculo da prescrição executória por crime) e 093 (ficha disciplinar com atestado sem peticionamento).
- `relatorios(...)`: relatório geral (6 páginas) e planilha.
- `exportar('pdf', ...)`: abas Progressão (11 p.), Prescrição (26 p.), Indulto (19 p.) e Ficha disciplinar (18 p.).
- `exportar('xlsx', todas)`: 11 folhas, que convertidas com o LibreOffice imprimem **687 páginas A4**.

Nenhum arquivo do repositório foi alterado. Só foram criadas capturas em `docs/analise_design/capturas/`.

---

## 1. Paleta e fontes efetivas

### 1.1 Fontes dos PDFs
| Papel | Fonte efetiva (confirmada com `pdffonts` e `pdfplumber`) | Onde |
|---|---|---|
| Texto, células e rótulos | Source Sans 3 Regular, SemiBold e Bold (TTF embutida, subconjunto) | `rspe_relatorio.py:48-56` (`registerFont("Apto-"+k)`) |
| Títulos (h2, título, números grandes) | Source Serif 4 SemiBold e Bold | `rspe_relatorio.py:50`, estilos em `:132-141` |
| Marca "APTO" (cabeçalho e capa) | Cinzel Bold, 11 pt com `charSpace` 1,6 (34 pt na capa) | `rspe_relatorio.py:182-187`, `:257` |
| Reserva | Helvetica e Times-Bold (sem acentos especiais) se `fontes/` faltar; Arial ou DejaVu se existirem | `rspe_relatorio.py:35-36`, `:57-69` |

- As fontes de `fontes/` **são registradas e usadas** em todas as peças. "Helvetica" aparece no `pdffonts` sem nenhum glyph desenhado: é a fonte inicial do canvas do ReportLab e não tem efeito visual. No geral também aparece "Times-Roman", igualmente sem texto.
- **Não existe `registerFontFamily`.** Por isso o `<b>` dentro de `Paragraph` cai na própria Apto-n, a Regular. Teste: `tt2ps('Apto-n',1,0)` devolve `'Apto-n'`, e um PDF de teste com `<b>NEGRITO</b>` sai em SourceSans3-Regular. Ver o achado PDF-01.
- **Números tabulares.** Os dígitos da Source Sans 3 têm largura fixa por padrão (Regular 497 u, Bold 528 u) e os da Source Serif 4 Bold também (569 u). As datas `dd/mm/aaaa` alinham verticalmente. **OK.** Já os dígitos da Cinzel são proporcionais (393 a 653 u), mas ela só é usada na marca.
- Faltam glyphs: `⚠` não existe em nenhuma das fontes e é trocado por "!" (`:107-108`). `●` não existe na Source Serif 4 nem na Cinzel; ele só é usado em Source Sans, então está OK.
- Escala tipográfica efetiva medida no relatório geral: **19 corpos distintos**, de 6,4 a 24 pt (6,4 · 6,6 · 6,8 · 7 · 7,2 · 7,4 · 7,6 · 7,8 · 8,2 · 8,4 · 9 · 10 · 10,5 · 11 · 13 · 15 · 18 · 20 · 24). O corpo de tabela é 8,2 pt no individual e 7,8 pt no PDF da aba. O rodapé jurídico tem 6,6 pt e a paginação 7,2 pt. O código morto `figura_prescricao` usaria 5,2 a 5,8 pt.

### 1.2 Fontes do Excel
- Nenhum `Font(name=...)` é definido (`rspe_export.py:48`, `:68`, `:77`). Tudo sai em **Calibri 11**, o padrão do openpyxl. O cabeçalho é Calibri 11 negrito branco. A tela usa Arial e o PDF usa Source Sans 3: são três famílias para a mesma informação.

### 1.3 Paleta dos PDFs
| Token | Hex | Uso | Arquivo:linha |
|---|---|---|---|
| NAVY | #0B3B22 | títulos e h2 | `rspe_relatorio.py:20` |
| PRI | #00602C | marca, filete do cabeçalho e linha sob o cabeçalho das tabelas | `:21` |
| TX / TX2 / TX3 | #262B28 / #5F6662 / #7B827E | texto, rótulos, rodapé e paginação | `:22-24` |
| LINE / ZEBRA | #D5DAD6 / #FAFBFA | fios e zebra | `:25-26` |
| COR (fundo, texto) | vermelho #F6E4E3/#8E2424 · laranja #F7EADB/#8A4A12 · amarelo #F5EDDA/#7A5410 · verde #E3EFE7/#1F5B39 · cinza #ECEEEB/#5F6662 · azul #E6ECF2/#334E68 | pílulas, filete lateral e fundo de linha | `:27-29` (cópia de `rspe_view.py:24-33`) |
| DOT (bolinha e filete do PDF da aba) | vermelho #A33A36 · laranja #B5651D · amarelo #C49A3A · verde #2F7A4F · cinza #AEB5B0 · azul #4A6A8A | cartões, `●` e filete lateral | `rspe_export.py:14` |
| CAT (roscas e colunas do geral) | #0B3B22 · #3E8E62 · #C9A55C · #7FB894 · #8A5D0E · #4A6A8A · #B08497 · #A33A36; "Outros" #C6CBC6 | gráficos | `rspe_relatorio.py:1376-1377` |
| Traço de vazio "—" | #AEB5B0 | célula vazia no PDF da aba | `rspe_export.py:325` |

### 1.4 Paleta do Excel
Cabeçalho: branco sobre #0B3B22 (`rspe_export.py:48-49`). Linha inteira com o fundo de `rv.CORES[cor][0]` (`:61`). Texto da coluna de situação ("pílula") com `rv.CORES[cor][1]` em negrito (`:68`). Fio inferior #D5DAD6 (`:29`, `:59`). Os mesmos 6 pares da tabela COR, sem zebra.

### 1.5 Comparação com a tela
| Semântica | Tela | PDF e Excel (texto) | PDF (bolinha e filete) | Gráficos do geral |
|---|---|---|---|---|
| Marca | #1D5A3B / #153F2A | #00602C / #0B3B22 | — | #0B3B22 |
| Vermelho | #A3201D | #8E2424 | #A33A36 | #A33A36 |
| Laranja | #A85100 | #8A4A12 | #B5651D | — |
| Âmbar | #7E6200 | #7A5410 | #C49A3A | #C9A55C |
| Verde de situação | #1D6B37 | #1F5B39 | #2F7A4F | #3E8E62 e #0B3B22 |
| Azul | #2E4D6E | #334E68 | #4A6A8A | #4A6A8A |

São **quatro tons por semântica**, e nenhum coincide com a tela. A marca dos PDFs (#00602C, verde mais saturado) também difere da marca da tela (#1D5A3B).

### 1.6 Contraste WCAG calculado (texto sobre fundo)
| Par | Razão | Situação |
|---|---|---|
| TX #262B28 / branco | 14,40 | OK |
| TX2 #5F6662 / branco | 5,89 | OK |
| TX2 / ZEBRA #FAFBFA | 5,68 | OK |
| **TX3 #7B827E / branco** (rodapé jurídico de 6,6 pt e "página X de Y") | **3,94** | **falha 1.4.3** (texto pequeno precisa de 4,5) |
| **TX3 #7B827E / #F6E4E3** (número do processo em linha vermelha) | **3,21** | **falha** |
| PRI #00602C / branco | 7,75 | OK |
| NAVY #0B3B22 / branco (e cabeçalho do Excel branco/NAVY) | 12,63 | OK |
| vermelho #8E2424 / #F6E4E3 | 7,05 | OK |
| laranja #8A4A12 / #F7EADB | 5,78 | OK |
| amarelo #7A5410 / #F5EDDA | 5,80 | OK |
| verde #1F5B39 / #E3EFE7 | 6,80 | OK |
| cinza #5F6662 / #ECEEEB | 5,05 | OK |
| azul #334E68 / #E6ECF2 | 7,26 | OK |
| **traço "—" #AEB5B0 / branco** | **2,09** | falha (a ausência de dado fica quase invisível impressa) |
| **branco / #7FB894** (% sobre fatia da rosca, 7 pt) | **2,29** | **falha** |
| **branco / #C9A55C** (% sobre fatia) | **2,33** | **falha** |
| **branco / #AEB5B0** (% sobre fatia cinza) | **2,09** | **falha** |
| branco / #B08497 | 3,19 | falha |
| branco / #3E8E62 | 4,00 | falha para 7 pt |
| branco / #A33A36 e branco / #0B3B22 | 6,53 / 12,63 | OK |
| *Não texto (1.4.11, mínimo 3:1)*: bolinha amarela #C49A3A / #F5EDDA | 2,24 | falha |
| bolinha cinza #AEB5B0 / #ECEEEB | 1,79 | falha |
| bolinha "sem cor" #C8CEC8 / branco | 1,60 | falha |
| bolinha laranja #B5651D / #F7EADB · verde #2F7A4F / #E3EFE7 · vermelha #A33A36 / #F6E4E3 | 3,66 · 4,42 · 5,33 | OK |

Referência das cores da tela sobre branco: #A3201D 7,55 · #A85100 5,47 · #7E6200 5,78 · #1D6B37 6,54 · #2E4D6E 8,74.

**Impressão em P&B e daltonismo:**
- Os fundos de linha têm luminância relativa entre 0,806 e 0,850 (vermelho 0,806 · azul 0,832 · laranja 0,837 · verde 0,838 · amarelo 0,850 · cinza 0,850). O contraste de cada um contra o branco fica entre 1,17 e 1,23:1: **impressos em cinza, os seis viram o mesmo cinza-claro**.
- Os filetes laterais de 2,2 a 2,4 pt também se confundem em cinza: vermelho 0,111, azul 0,136, verde 0,151, laranja 0,192.
- Simulação de deuteranopia (Machado 2009): o ΔE entre os fundos vermelho e verde cai de 11,5 para **1,5**, o que torna os dois indistinguíveis. Entre as bolinhas vermelha e verde, cai de 77,7 para 15,9. A informação continua no texto da coluna de situação, mas a varredura por cor, que é o modo de leitura proposto, deixa de funcionar.

---

## 2. Achados

| id | superfície | tela e local no código (arquivo:linha) | problema | evidência (nome da captura) | princípio violado | gravidade | esforço | mudança sugerida |
|---|---|---|---|---|---|---|---|---|
| PDF-01 | PDF | Todos os PDFs: `rspe_relatorio.py:44-56` (só `registerFont`, sem `registerFontFamily`). Afeta os 24 `<b>` de `rspe_relatorio.py` (ex.: `:855`, `:944-948`, `:968-970`, `:1851`) e os 4 de `rspe_export.py` (ex.: `:319`) | O `<b>` inline não fica negrito. "1 · TEMPO DE PRISÃO / DETRAÇÃO", "PRESCRIÇÃO: PRESCRITO", "Falta para concluir:", o nome do crime nas condenações e o texto da situação no PDF da aba saem em peso Regular. A ênfase planejada some justamente nas conclusões. | pdf_negrito_perdido_zoom.png, pdf_individual_prescricao_p2.png, pdf_aba_p1.png | Nielsen 8 (estética e hierarquia); WCAG 1.3.1 (a ênfase estrutural se perde) | alta | P | Depois de registrar as fontes, chamar `pdfmetrics.registerFontFamily("Apto-n", normal="Apto-n", bold="Apto-b", italic="Apto-n", boldItalic="Apto-b")`, e fazer o mesmo para "RelN"/"RelB" na reserva. |
| PDF-02 | PDF | Relatório individual: `rspe_relatorio.py:794`, `:848`, `:863`, `:867`, `:872` e `:896` (h2 anexado solto, sem `keepWithNext` nem `KeepTogether` com a tabela) | Título de seção órfão no pé da página ("Incidentes…", "Remição (ficha disciplinar)", "Condenações"), com o conteúdo começando na página seguinte sem título. Isso aconteceu em 3 dos 4 individuais gerados. | pdf_individual_p1.png, pdf_individual_ficha_p1.png, pdf_individual_ficha_p2.png, pdf_individual_prescricao_p1.png | Nielsen 4 (consistência e padrões de impressão); WCAG 1.3.2 (sequência significativa) | alta | P | Usar `keepWithNext=1` no estilo `h2` (`:134`), ou envolver o h2 e as primeiras linhas da tabela em `KeepTogether`, como já é feito em `:939`. |
| PDF-03 | PDF | PDF das abas: `rspe_export.py:328-332` (fundo da linha e filete pela cor), `:290` e `:319` (bolinha `●` colorida); cores em `rspe_view.py:24-33` e `rspe_export.py:14` | A situação é codificada só por matiz. Em P&B os 6 fundos têm luminância de 0,81 a 0,85 (contraste de 1,17 a 1,23 contra o branco) e os filetes de 0,11 a 0,19. Na deuteranopia, o ΔE entre os fundos vermelho e verde é 1,5. Linhas "Vencido", "Até 60 dias" e "Até 90 dias" ficam iguais impressas, e os cartões do topo perdem a chave de cor. | pdf_aba_p1_pb.png, pdf_individual_prescricao_p1_pb.png, pdf_aba_indulto_p2_deuteranopia.png, pdf_aba_p1_deuteranopia.png | WCAG 1.4.1 (uso da cor); Nielsen 6 (reconhecer em vez de lembrar) | alta | M | Somar uma redundância que não depende de cor: forma ou ícone por nível (● ▲ ◆ ○), filete de espessura ou padrão distinto (cheio, tracejado, duplo) e o rótulo curto do nível em negrito no início da célula de situação. Escurecer os filetes para tons com luminância bem separada. Testar com `pdftoppm -gray`. |
| PDF-04 | PDF | PDF das abas: `rspe_export.py:335` (`splitInRow=1`) e `:299-300` (larguras por peso) | Uma linha de assistido é partida entre páginas: o "Caso 004" começa no pé da p. 1 e continua no topo da p. 2 sem o nome. Além disso, o cabeçalho da tabela reaparece no meio da p. 1, logo antes da linha partida. O leitor perde a quem pertence o texto. | pdf_aba_indulto_p1.png, pdf_aba_indulto_p2.png, pdf_aba_prescricao_p1.png | Nielsen 4 (consistência); WCAG 1.3.2 | alta | M | Usar `splitInRow` só como último recurso, para linhas mais altas que a página. Para as demais, `splitByRow` sem partir a linha (`TableStyle NOSPLIT` por linha). Na continuação de uma linha partida, repetir o nome com "(cont.)". |
| PDF-05 | PDF | PDF das abas: `rspe_export.py:299-300` (peso fixo +6 para `proc`) e pesos de `rspe_view.py:2022ss` | Grade de colunas mal calibrada. Na Progressão, "Nº da execução" ocupa cerca de 18% da largura com folga, enquanto "Situação" quebra em 3 linhas. Na Prescrição, o número do processo **quebra no meio dos dígitos** ("9900001-00.2026.8.12.0 / 001"), e "Pena" quebra "5 anos e 4 m / eses". Na Ficha, "Unidad/e". Resultado: 19 páginas para o indulto e 26 para a prescrição, com 144 assistidos. | pdf_aba_p1.png, pdf_aba_prescricao_zoom.png, pdf_aba_ficha_p1.png | Nielsen 8 (design minimalista); WCAG 1.4.12 e 1.4.8 (apresentação legível) | alta | M | Largura mínima para o número CNJ (25 caracteres em 7,8 pt dão cerca de 75 pt), com `wordWrap` desligado nessa coluna. Distribuir as sobras para Situação e Observação. Não deixar quebrar dentro de palavra (`splitLongWords=0`). |
| PDF-06 | PDF | PDF das abas: ordem de `modelos_aba` em `rspe_export.py:272` e `:310`, sem ordenação por cor | Linhas em ordem alfabética. Os 13 "Vencido" da Progressão e os 3 casos vermelhos da Ficha ficam espalhados em 11 e 18 páginas. Na Ficha, as primeiras páginas são só as 130 linhas cinza "Sem ficha", com a instrução de tela "Importe o PDF… pelo botão Importar PDFs" repetida em cada uma. | pdf_aba_ficha_p1.png, pdf_aba_p1.png | Nielsen 7 (eficiência de uso); Nielsen 8 | média | P | Ordenar a peça impressa por gravidade (vermelho, laranja, amarelo, verde, azul, cinza) e depois pelo nome, sem omitir linha. Agrupar "Sem ficha" no fim, sob um subtítulo. |
| PDF-07 | PDF | Todos: rodapé em `rspe_relatorio.py:206` e `:215-216` (6,6 pt, TX3, 3 linhas em 10,5, 7,5 e 4,5 mm) e paginação em `:313` (7,2 pt, TX3) | O aviso legal ("Não substitui o Atestado de Pena…") sai em 6,6 pt com contraste de 3,94:1. A 3ª linha tem a linha de base a 4,5 mm da borda, dentro da margem não imprimível de muitas impressoras de escritório (4 a 5 mm), com risco de corte. | pdf_individual_p1.png, pdf_aba_p1.png | WCAG 1.4.3 (contraste mínimo de 4,5:1); Nielsen 9 e 10 (o aviso que previne erro precisa ser legível) | média | P | Usar TX2 (#5F6662, 5,89:1) com no mínimo 7 pt. Subir o bloco do rodapé para que a última linha fique acima de 7 mm (ex.: `bottomMargin` de 22 mm e linhas em 14, 11 e 8 mm). |
| PDF-08 | PDF | Relatório geral, roscas: `rspe_relatorio.py:1443-1445` (% sempre branco, 7 pt) e paleta CAT em `:1376-1377` | O percentual branco sobre fatias claras não se lê: #7FB894 dá 2,29, #C9A55C 2,33 e #AEB5B0 2,09. A paleta CAT categórica é usada para faixas **ordinais** (idade, pena, prazo), e o mesmo verde-escuro #0B3B22 quer dizer "Fechado", "Mais de 180 dias", "Homologadas" e "Não prescrita". | pdf_geral_rosca_zoom.png, pdf_geral_p1.png, pdf_geral_p3.png | WCAG 1.4.3 e 1.4.11; Nielsen 4 (consistência semântica da cor) | média | P | Escolher a cor do rótulo pelo contraste (TX sobre fatia clara, branco sobre escura), como já é feito em `:1521-1524`. Para faixas ordinais, usar uma rampa sequencial de um só matiz. Reservar vermelho, âmbar e verde para situação. |
| PDF-09 | PDF | Relatório geral: subtítulos por `secao()`, `ros()` e `trio()` (`rspe_relatorio.py:1776`, `:1817-1848`) | Hierarquia inconsistente. "1.1 Faixa etária" e "3.1 Indicadores" saem em Sans Bold pequeno alinhado à margem, enquanto "1.5", "1.6" e "3.4" ficam recuados cerca de 7 pt e "3.2" e "3.3" são h2 serifados. Colunas numéricas ("Assistidos", "% da base", "Cabe"…) alinhadas à esquerda nas tabelas, mas à direita nas legendas das roscas. | pdf_geral_p1.png, pdf_geral_p3.png, pdf_geral_p4.png, pdf_geral_p5.png | Nielsen 4 (consistência e padrões) | média | M | Definir 3 níveis fixos (seção numerada em serif 15, subseção em serif 11 e rótulo de gráfico em sans semibold 8) com o mesmo recuo zero. Alinhar números à direita (`ALIGN RIGHT`) em todas as tabelas. |
| PDF-10 | PDF | Relatório individual: chip de situação em `rspe_relatorio.py:759-765` e `:790-792`; coluna "Hediondo" em `:849` e `:860` (8% da largura) | A pílula "Em cumprimento" (cor "") tem fundo branco: não parece pílula e quebra em 2 linhas, enquanto as outras pílulas são de uma linha. O cabeçalho "Hediondo" quebra em "Hediond/o". | pdf_individual_p1.png, pdf_individual_indulto_p1.png, pdf_individual_ficha_p1.png | Nielsen 4 (consistência); Nielsen 8 | baixa | P | Dar à pílula neutra um contorno de 0,5 pt em LINE e largura mínima igual à da coluna. Ajustar as larguras de Condenações (ex.: Hediondo 9%, Crime 29%) ou usar o rótulo "Hed." com a legenda no rodapé da tabela. |
| PDF-11 | PDF | PDF das abas: legenda só no fim da tabela (`rspe_export.py:342-344`); cartões em `:286-296` com `●` de 9 pt e número em 9 pt | A legenda das cores aparece uma única vez, depois de 11 a 26 páginas. Nos cartões, número e rótulo têm o mesmo peso e corpo (9 pt), sem destaque. As bolinhas amarela e cinza têm contraste de 2,24 e 1,79 sobre o fundo. | pdf_aba_p1.png, pdf_aba_indulto_p1.png | Nielsen 6 (reconhecer em vez de lembrar); WCAG 1.4.11 | média | P | Repetir a legenda compacta no rodapé ou no cabeçalho de cada página, ou logo abaixo dos cartões. Nos cartões, número em serif 14 a 16 pt e rótulo em 8 pt TX2, com a mesma forma e ícone por nível do PDF-03. |
| PDF-12 | PDF | Coerência entre peças: `rspe_relatorio.py:20-29`, `rspe_export.py:14`, `rspe_relatorio.py:1376` e `:3060` (COR_ATD) | Quatro conjuntos de cor para a mesma semântica (texto COR, DOT, CAT e COR_ATD), nenhum igual ao da tela (ex.: vermelho na tela #A3201D, no texto do PDF #8E2424, no filete #A33A36). A marca do PDF (#00602C) difere da tela (#1D5A3B). | pdf_aba_p1.png, pdf_individual_p1.png, pdf_geral_p3.png | Nielsen 4 (consistência interna e externa) | baixa | M | Criar um único módulo de tokens (ex.: `rspe_cores.py`) lido pela tela, pelo PDF e pelo Excel, com pares de texto, fundo e marcador por nível e um token de marca. |
| PDF-13 | PDF | `rspe_relatorio.py:586-741` (`figura_prescricao`, `legenda_prescricao`) não é chamada em nenhum lugar (comentário em `:921`: "sem a figura da linha do tempo") | A linha do tempo da prescrição, que existe na tela, não chega a nenhum PDF. O cálculo por crime aparece só em caixas de texto (1 → 2 → 3). A figura pronta usa corpos de 5,2 a 5,8 pt, ilegíveis impressos, o que explica em parte o abandono. | pdf_individual_prescricao_p2.png | Nielsen 2 (correspondência com o mundo real: a fuga e o saldo são temporais); Nielsen 4 (tela × papel) | baixa | G | Reativar a figura no individual com corpo mínimo de 7 pt e altura maior (largura total da página), mantendo as 3 caixas como memória de cálculo. |
| XLS-01 | Excel | `rspe_export.py:25-84` (não há `page_setup`, `print_title_rows`, `fitToWidth` nem `oddHeader`/`oddFooter` em nenhuma folha) | Impressão sem configuração: retrato, margens de 0,75", sem ajuste à largura e sem títulos repetidos. O livro completo imprime **687 páginas**. Até a folha "Geral", com 6 colunas, separa Nome e Nº (p. 1 a 4) das datas (p. 5 a 8). Da p. 2 em diante não há cabeçalho de colunas. | excel_impressao_p1.png, excel_impressao_p2_sem_cabecalho.png, excel_impressao_p5_colunas_separadas.png, excel_impressao_progressao_p1.png | Nielsen 4 (padrões da plataforma); Nielsen 9 (o erro de impressão só é descoberto no papel) | alta | P | Em cada folha: `ws.page_setup.orientation='landscape'`, `paperSize=9` (A4), `ws.sheet_properties.pageSetUpPr.fitToPage=True`, `fitToWidth=1`, `fitToHeight=0`, `ws.print_title_rows='1:1'`, `print_options.gridLines=False` e margens de 1,5 cm. |
| XLS-02 | Excel | `rspe_export.py:54` (os valores vão como texto) | Datas como **texto** "17/12/2026" (tipo `s`, formato General), em todas as colunas de data (Progressão, Livramento, Término, Fato, Trânsito…). Ordenar ou filtrar põe "01/09/2026" antes de "17/12/2026" de qualquer ano e não permite filtro por período. O "*" de "calculado pelo programa" vem colado à data ("05/12/2028*"). | excel_impressao_p5_colunas_separadas.png (ex.: coluna Progressão) | Nielsen 7 (eficiência e flexibilidade); Nielsen 5 (prevenção de erros na triagem por prazo) | alta | M | Gravar `datetime.date` com `number_format='DD/MM/YYYY'`. Mover o "*" para uma coluna vizinha "Data calculada pelo programa" (Sim/Não), mantendo a informação. Deixar texto ("—", "Pena extinta") só onde não há data. |
| XLS-03 | Excel | `rspe_export.py:25-84` (nenhuma linha de título nem aviso) e `:252-253` (o aviso existe no PDF) | O Excel não traz o aviso legal ("Triagem automatizada… não substitui o Atestado de Pena… as marcadas com * foram calculadas pelo programa"), nem o nome da base, a data de referência ou a data de emissão. Nenhuma folha explica o que as cores querem dizer. Uma planilha repassada perde o contexto que o PDF garante. | excel_impressao_p1.png | Nielsen 10 (ajuda e documentação); Nielsen 1 (visibilidade do estado: data de referência); WCAG 1.4.1 | alta | P | Pôr o aviso, a base, a referência e a emissão no cabeçalho e rodapé de impressão (`oddHeader.left`, `oddFooter.center` com `&P de &N`). Acrescentar uma folha "Leia-me" com a legenda das cores (`rv.ROTULO`), mantendo o texto integral do aviso. |
| XLS-04 | Excel | Folha "Completo": `rspe_export.py:73-83` | Cabeçalhos em snake_case ("processo_execucao", "fracao_progressao_aplicada"), já que `TITULOS_BONITOS` não cobre todas as colunas. Não há larguras, quebra de texto nem filtro. Penas no formato bruto "3a0m0d", enquanto os PDFs usam "3 anos". Impressa, a folha sai com colunas cortadas ("01/01/20201/03/202") e linhas altíssimas com 1 linha visível. | excel_impressao_completo.png | Nielsen 2 (linguagem do usuário); Nielsen 8 | média | P | Aplicar larguras (máx. 40), `wrap_text` só nas colunas longas, `auto_filter` e título legível para todas as colunas. Manter a coluna bruta e acrescentar ao lado a versão por extenso ("Pena total (extenso)"), para não perder o dado original. |
| XLS-05 | Excel | `rspe_export.py:58-61` (fundo da linha inteira pela cor, sem zebra) e `:68` (cor do texto da situação) | Repete a codificação só por matiz do PDF-03: os fundos claros (contraste de 1,17 a 1,23 contra o branco) somem em impressão P&B e na deuteranopia. As linhas "Até 90 dias" (verde) e "Em ordem" (verde) usam o mesmo fundo com sentidos diferentes conforme a folha. | excel_impressao_progressao_p1.png | WCAG 1.4.1; Nielsen 4 | média | M | Acrescentar uma coluna "Nível" (Vencido, Até 30 dias…) logo depois do Nome, filtrável, com o mesmo símbolo do PDF-03. Opcionalmente, usar formatação condicional ligada a essa coluna em vez de cor fixa. |
| XLS-06 | Excel | `rspe_export.py:48`, `:68` e `:77` (`Font` sem `name`) | Fonte Calibri 11 padrão: difere da tela (Arial) e do PDF (Source Sans 3). Em 11 pt com `wrap_text` em todas as células e largura máxima de 50, as folhas Auditoria e Indulto ficam com linhas de 6 a 10 linhas de texto (ver p. 181 do PDF convertido: 618 linhas na "Conferência completa"). | excel_impressao_progressao_p1.png | Nielsen 4 (consistência entre peças); Nielsen 8 | baixa | P | Definir `Font(name="Arial", size=10)` como estilo nomeado (`NamedStyle`) para o corpo e o cabeçalho. Ligar `wrap_text` só nas colunas de texto longo e manter Nome, Nº e datas em uma linha. |

Total: 13 achados de PDF e 6 de Excel.

Pontos positivos, para não perder:
- As fontes do programa são de fato embutidas, com acentos e símbolos corretos.
- Os dígitos são tabulares.
- O cabeçalho é coerente (selo, APTO, título, base, emissão e filete) e há "página X de Y" em todas as peças.
- O cabeçalho da tabela se repete em cada página no PDF da aba e no individual.
- As pílulas de texto têm contraste de 5 a 7:1.
- No Excel, os painéis ficam congelados em B2 e há autofiltro em todas as folhas de aba. O `_sem_formula` protege contra injeção de fórmula.

---

## 3. Sugestões de maior impacto

1. **Registrar a família da fonte (PDF-01).** Uma linha de código devolve o negrito a todas as conclusões ("PRESCRIÇÃO: PRESCRITO", passos 1 a 3, situações na aba). É o maior ganho de hierarquia por esforço.
2. **Codificação redundante da situação, além da cor (PDF-03, PDF-11, XLS-05).** Símbolo e forma por nível, rótulo do nível em negrito e uma coluna "Nível" no Excel. Os relatórios são impressos em impressoras de repartição, quase sempre P&B, e hoje as 6 cores viram um único cinza.
3. **Configuração de impressão do Excel e contexto na planilha (XLS-01, XLS-03).** Paisagem, ajuste a 1 página de largura, linha 1 repetida, cabeçalho e rodapé com base, referência, aviso legal e "página X de Y", e uma folha de legenda. O livro passa de 687 páginas com colunas órfãs para algo imprimível.
4. **Paginação do PDF das abas (PDF-04, PDF-05, PDF-06).** Não partir a linha do assistido, recalibrar as colunas (número CNJ inteiro e Situação mais larga) e ordenar por gravidade. Isso reduz as páginas (19 a 26 hoje) e põe os vencidos na primeira folha, sem omitir ninguém.
5. **Datas como datas no Excel (XLS-02).** Permite ordenar e filtrar por prazo, que é a tarefa principal da defensoria, e separa o marcador "*" numa coluna própria, sem perder a informação.

---

## 4. Capturas geradas (em `docs/analise_design/capturas/`)

**Relatório individual**
- pdf_individual_p1.png: caso 001, p. 1, com título "Incidentes" órfão e "Hediond/o"
- pdf_individual_indulto_p1.png: caso 002, indulto
- pdf_individual_prescricao_p1.png e pdf_individual_prescricao_p2.png: caso 055, fuga e cálculo da prescrição por crime
- pdf_individual_prescricao_p1_pb.png: o mesmo em tons de cinza
- pdf_individual_ficha_p1.png e pdf_individual_ficha_p2.png: caso 093, ficha disciplinar, com "Remição" órfão
- pdf_negrito_perdido_zoom.png: 200 dpi, o `<b>` saindo em Regular

**Relatório geral**
- pdf_geral_capa.png, pdf_geral_p1.png, pdf_geral_p3.png, pdf_geral_p4.png e pdf_geral_p5.png
- pdf_geral_rosca_zoom.png: % branco sobre fatias claras

**PDF das abas**
- pdf_aba_p1.png: Progressão
- pdf_aba_p1_pb.png: Progressão em cinza
- pdf_aba_p1_deuteranopia.png: Progressão com simulação de deuteranopia
- pdf_aba_prescricao_p1.png e pdf_aba_prescricao_zoom.png: número CNJ partido
- pdf_aba_indulto_p1.png e pdf_aba_indulto_p2.png: linha partida entre páginas e cabeçalho no meio da página
- pdf_aba_indulto_p2_deuteranopia.png
- pdf_aba_ficha_p1.png

**Excel (convertido com LibreOffice)**
- excel_impressao_p1.png
- excel_impressao_p2_sem_cabecalho.png
- excel_impressao_p5_colunas_separadas.png
- excel_impressao_progressao_p1.png
- excel_impressao_completo.png

Arquivos de trabalho (fictícios, fora do repositório): `<pasta de trabalho>/pdfx/out/` (PDFs, `abas.xlsx`, `xl/abas.pdf`, PNGs) e os scripts `g2.py` e `g4.py` em `<pasta de trabalho>/pdfx/`.
