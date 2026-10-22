# 5. Roteiro em fases

Regras válidas para todas as fases:
- nenhuma regra, cálculo ou texto jurídico muda;
- nenhuma informação some, só muda de lugar;
- tudo continua offline e em português;
- o `ui.html` segue arquivo único.

Cada item vem com os arquivos afetados e o risco:
- **baixo**: só aparência;
- **médio**: muda interação ou ordem;
- **alto**: mexe na estrutura ou em muitos lugares.

**Validação de cada entrega:**
1. Rodar `python testes.py`.
2. Rodar a ponte de capturas (`ferramentas/roteiro.py`) e comparar com as capturas de hoje.
3. Para PDF e Excel, gerar as peças fictícias e conferir em cinza (`pdftoppm -gray`).

## Fase 1: ganhos rápidos (até 1 dia cada)

| # | item | achados | arquivos | risco |
|---|---|---|---|---|
| 1.1 | **Negrito de volta nos PDFs:** `registerFontFamily` | PDF-01 | `rspe_relatorio.py` (~4 linhas) | baixo |
| 1.2 | **Abas de prazo abrem por urgência**, com faixas de grupo ("Vencido · 13"); o título de coluna continua ordenando | APP-01 | `ui.html` (ordem padrão em `render`); `rspe_app.py:1544` fica, pois exportação e relatórios mantêm a ordem atual salvo decisão em contrário | médio (muda o hábito) |
| 1.3 | **Contraste:** `--tx3` → `#5C636A`, ícones → `#6B7278`, borda de controle → `#8C9399` | APP-08 | `ui.html` (3 valores) | baixo |
| 1.4 | **Selos do indulto com símbolo** (✓ ? ✕ ⊘ ★ –) e cores ≥ 5,9:1 | APP-06 | `ui.html` (`.mx i`, `DEC_COR`, `decLegenda`) | baixo |
| 1.5 | **Larguras das colunas:** Situação mais larga, primeira parte em negrito | APP-02 | `rspe_view.py` (pesos de `cols`), `ui.html` | baixo |
| 1.6 | **Modais com véu**, Esc fecha e o foco volta | APP-09 | `ui.html` (`.modal`) | baixo |
| 1.7 | **Expansão da Prescrição sem estourar a tabela** | APP-04 | `ui.html:208` | baixo |
| 1.8 | **Título não fica órfão no pé da página** (`keepWithNext`) e rodapé legal legível | PDF-02, PDF-07 | `rspe_relatorio.py` | baixo |
| 1.9 | **Excel imprimível:** paisagem, ajuste à largura, títulos repetidos, cabeçalho e rodapé com base, referência e aviso, folha "Leia-me" | XLS-01, XLS-03 | `rspe_export.py` | baixo |
| 1.10 | **Avisos acessíveis:** `role="status"`/`"alert"`; erro fica até fechar | APP-21 | `ui.html` (`toast`) | baixo |
| 1.11 | **Popup da extensão:** um primário só, contraste, confirmação visível no topo | EXT-02, EXT-03, EXT-04 | `extensao_seeu/popup.html` | baixo |
| 1.12 | **Conversor:** "Cancelar" separado com confirmação, velocidade < 1× correta, vídeo sem divisão automática | CONV-01, CONV-03, CONV-04 | `conversor_audio/conversor.py` (outro ramo) | baixo |
| 1.13 | **Nomes:** aba "Ficha disciplinar", "Indulto e comutação", maiúscula só no início; "Remição com nome" desmarcado por padrão | APP-15, APP-20 | `ui.html`, `rspe_view.py` (rótulos), `LEIA-ME.txt` | baixo; os testes que procuram `titulo:'Dados da Base'` precisam acompanhar |
| 1.14 | **Peso morto:** tirar a Source Serif duplicada e o PNG repetido (−150 KB) | APP-23 | `ui.html` | baixo |
| 1.15 | **Petições:** margem e rodapé únicos, sem página em branco, negrito só nos termos-chave | DOC-01 a DOC-03 | `*.docx` (estão desativados no .exe) | baixo |

## Fase 2: melhorias médias (2 a 5 dias cada)

| # | item | achados | arquivos | risco |
|---|---|---|---|---|
| 2.1 | **Uma escala de situação para todas as abas, com forma:** ◆ ▲ ● ○ ✓ ■ –; "até 90 dias" sai do verde | APP-05, APP-07 | `ui.html` (`.pill`, `.stat`, legendas), `rspe_view.py` (`CORES`), `LEIA-ME.txt` (seção CORES) | médio: muda um hábito visual; depende da pergunta 1 |
| 2.2 | **A mesma escala no papel:** forma + rótulo + filete distinto; PDF da aba sem partir linha, colunas recalibradas e ordem por gravidade | PDF-03 a PDF-06, PDF-11 | `rspe_export.py`, `rspe_relatorio.py` | médio |
| 2.3 | **Excel com datas de verdade** e coluna "Nível"; o "*" vira coluna própria | XLS-02, XLS-05 | `rspe_export.py` | médio: quem tem planilhas e fórmulas próprias precisa saber |
| 2.4 | **Ficha do assistido: "por quê" junto da linha**, com todos os resultados (cabível e a verificar) e "Copiar fundamentação" ao lado | APP-12 | `ui.html` (`resumoTela`/`lin`, ~`:2600-2650`) | médio |
| 2.5 | **Resumo e painel de importação:** totais, grupos, falhas primeiro, "Parar" | APP-11 | `ui.html` (`importado`, `modalAvisos`, `progresso`), `rspe_app.py` (sinal de parar entre arquivos) | médio |
| 2.6 | **Confirmações próprias** no lugar dos 10 `confirm()` e 6 `prompt()`; campo de data validado; "Desfazer" | APP-10 | `ui.html` | médio |
| 2.7 | **Legenda e método em tabela por aba**, com amostra de forma e cor | APP-17, APP-22 | `rspe_view.py` (`ajuda`), `ui.html` | baixo |
| 2.8 | **Busca e listas grandes mais leves:** espera de 150 ms, `content-visibility`, desenho em lotes | APP-18 | `ui.html` | médio |
| 2.9 | **Extensão:** popup ≤ 600 px, estado em 3 fases, aviso de erro que fica, Triagem estreita em cartões, teclado | EXT-01, EXT-05 a EXT-10 | `extensao_seeu/popup.*`, `background.js`, `content.js`, `triagem.*` | médio; rodar `teste_extensao_seeu.py` e `teste_triagem_seeu.py` |
| 2.10 | **Identidade:** glifo único para 16-32 px (`.ico` e extensão), lockup "glifo + APTO", dois verdes | ID-01 a ID-04 | `rspe.ico`, `extensao_seeu/icones/*`, `apto_selo.png`, `build_exe.bat` | baixo |
| 2.11 | **Conversor:** erros em português com ação, estimativa de tempo, progresso no título | CONV-02, CONV-05, CONV-06 | `conversor.py` | baixo |

## Fase 3: mudanças estruturais (1 a 3 semanas)

| # | item | achados | arquivos | risco |
|---|---|---|---|---|
| 3.1 | **Sistema de tokens único:** um `:root` no lugar de 4; as variáveis antigas viram apelidos; regras mortas apagadas; cores do JS lidas dos tokens; `rspe_cores.py` para PDF e Excel; `tokens.css` para a extensão | APP-19, PDF-12, EXT-11, ID-03 | `ui.html` (CSS inteiro), `rspe_view.py`, `rspe_relatorio.py`, `rspe_export.py`, `extensao_seeu/*` | **alto** (muitas linhas); fazer por componente. Atualizar `teste_sistema.py:209-211`, que confere cores literais |
| 3.2 | **Cabeçalho compacto e abas agrupadas** (uma faixa; grupos; "Mais" abaixo de 1 400 px): a tabela ganha ~120 px e, em 150 %, passa de 2,5 para ~7 linhas | APP-03, APP-16 | `ui.html` (HTML do topo, `render` das abas, `@media`) | **alto**: muda a navegação de todos; testar com 2-3 usuários antes |
| 3.3 | **Uma regra de clique para todas as abas** (linha expande; ↗ ou Enter abre a ficha) e ordem fixa Pedido → Ações | APP-13 | `ui.html` (`render`, `subTabela`) | médio-alto: muda o hábito em 5 abas |
| 3.4 | **Tabela navegável por teclado** (setas, Enter, Espaço), link "Ir para a lista", nomes acessíveis nos ícones | APP-14 | `ui.html` (`kbFocaveis` e tabela) | médio |
| 3.5 | **Linha do tempo da prescrição no PDF individual** | PDF-13 | `rspe_relatorio.py` | médio |
| 3.6 | **Tema escuro** (opcional) e `prefers-reduced-motion` | APP-26 | `ui.html` | baixo, depois de 3.1 |

## Ordem sugerida

1. **Semana 1:** itens 1.1 a 1.10 da fase 1. São os de mais impacto por esforço; nenhum muda hábito, salvo o 1.2.
2. **Semanas 2 e 3:** 2.1 e 2.2 juntos (a mesma escala na tela e no papel), depois 2.4, 2.3 e 2.5.
3. **Depois:** 3.1 (tokens) antes de 3.2 (cabeçalho), porque o cabeçalho novo já nasce com os tokens.

Os itens da extensão, do conversor e das petições são independentes e podem correr em paralelo.
