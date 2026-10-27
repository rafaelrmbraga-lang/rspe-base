# APTO: análise de design da extensão, do conversor, da identidade e das petições

Escopo: extensão do Chrome (`extensao_seeu/`), Conversor de Áudio (`conversor.py` do ramo `origin/claude/hopeful-newton-zqnh4j`), identidade visual (`rspe.ico`, `apto_selo.png`, `logo_defensoria.png`, `extensao_seeu/icones/*`) e modelos de petição `.docx`.
Este documento é só diagnóstico. Os únicos arquivos criados no repositório são as capturas em `docs/analise_design/capturas/`. Todos os dados das capturas são fictícios.

**Como as capturas foram feitas**
- **Popup e Triagem:** renderizados com Playwright/Chromium. O stub de `chrome.*` (`runtime`, `storage`, `tabs`) foi injetado por `add_init_script`, e as páginas foram servidas por `http.server` local, porque `triagem.js` é um módulo ES e não carrega por `file://`. Viewport do popup: 360 px.
- **Elementos injetados:** só o aviso flutuante do SEEU (`content.js`) cria interface visível. Ele foi capturado sobre uma página fictícia que imita o SEEU, com `comum.js` e `content.js` reais. O `siapen.js`, o `siapen_pagina.js` e o `sap.js` **não injetam nenhum elemento visível**: o `sap.js` cria só um iframe oculto em `left:-30000px` (`sap.js:45-49`), e o SIAPEN só lê e clica em componentes ExtJS. Por isso esses três foram analisados pelo código.
- **Conversor:** o `python3-tk` foi instalado na 2ª tentativa (`apt-get update` + `install`). O programa rodou sob `xvfb-run` com Python 3.12, e as capturas saíram por `import -window root`. A análise e a ffmpeg foram simuladas: um vídeo fictício de 3 h 12 min, sem ffmpeg real, com relógio controlado.
  - **Ressalva:** no Linux o tema é `clam` e a fonte é a DejaVu. No Windows o programa usa o tema `vista` e Segoe UI (`conversor.py:278,295`). A disposição dos elementos é a mesma, mas o acabamento muda.
- **Petições:** convertidas com `soffice --headless` para PDF e depois com `pdftoppm -r 70`. Os modelos são templates docxtpl/Jinja (`{{nome}}`, `{% if %}`), sem dados reais.

---

## 1. Paleta e fontes de cada superfície

### 1.1 Extensão: popup (`extensao_seeu/popup.html`)
| token | valor | onde |
|---|---|---|
| `--pri` / `--g` | `#1D5A3B` | popup.html:7 |
| `--pri2` (hover) | `#164A30` (a tela principal usa `#153F2A`) | popup.html:7 |
| `--tx` / `--tx2` / `--tx3` | `#1E2A24` / `#5C6660` / `#8E958F` | popup.html:7 |
| `--line` | `#DDE3DD` | popup.html:7 |
| `--r` / `--rbg` | `#B42318` / `#FBEAEA` (a tela principal usa `#A3201D`) | popup.html:7 |
| `--gbg` | `#E8F2EC` | popup.html:7 |
| cantos | 6 px em campos, botões e estados (a tela principal usa 3-4 px) | popup.html:18,21,28 |

**Fontes:**
- corpo: `13px/1.4 system-ui,"Segoe UI",Arial` (popup.html:9);
- nome "APTO": **Georgia** 15 px (popup.html:12), e não a Cinzel da tela principal;
- lote: `ui-monospace,Consolas` 12 px (popup.html:69).

### 1.2 Extensão: Triagem (`extensao_seeu/triagem.html`)
Usa os mesmos tokens do popup (triagem.html:9-10) e acrescenta estes:
- `--a` `#8A5A00` sobre `--abg` `#FFF4D6` (a tela principal usa `#7E6200`);
- `--b` `#1F4E79` sobre `--bbg` `#E7EEF7` (a tela principal usa `#2E4D6E`);
- `--bg` `#F6F8F6`;
- cabeçalho de tabela `#EEF2EE` (l.52) e linhas `#FAFBF9`/`#F3F7F4`/`#FBFCFB` (l.55-56, 77).

Cantos: 6 px nos campos, 8-10 px nos cartões e na tabela, 999 px em chips e etiquetas (l.20, 31, 51, 65).

**Fontes:**
- corpo: `13px/1.45 system-ui,"Segoe UI",Arial` (l.12);
- título: `600 16px Georgia` (l.15);
- nº do processo e dígitos: `ui-monospace,Consolas` (l.34, 57, 58).

### 1.3 Extensão: elementos injetados e ícone na barra
- **Aviso no SEEU** (`content.js:35-55`): fundo `#E8F2EC`, texto `#1D5A3B` e borda `#B9D6C4` no sucesso; fundo `#FBEAEA`, texto `#8E2424` e borda `#E3B4B4` no erro. Raio 8 px, `font:12px/1.35 system-ui,Segoe UI,Arial`, `box-shadow 0 6px 18px rgba(0,0,0,.18)`, `z-index 2147483000`, some após 6 s (`content.js:53`).
- **Selo do ícone** (`background.js:71-72`): fundo `#1D5A3B` (contagem do dia), `#B42318` ("!") ou `#8E958F` ("off").
- **SIAPEN e SAP:** sem interface visível.

### 1.4 Conversor de Áudio (`conversor.py`)
- **Tema:** ttk `vista` no Windows, `clam` nos demais (l.278). O fundo vem do tema: `#F0F0F0` no Windows, `#DCDAD5` no `clam`.
- **Títulos de seção:** `("Segoe UI", 12, "bold")` (l.295). O resto usa a fonte padrão do Tk (Segoe UI 9 pt no Windows).
- **Cores próprias:** estimativa `#1a5d1a` (l.361), um quarto verde diferente dos outros; texto secundário `#555` (l.412, 428).
- **Ícone:** nenhum. Não há `iconbitmap`, então a janela mostra a pena padrão do Tk.

### 1.5 Identidade
Cores extraídas com PIL, pixels opacos mais frequentes:

| arquivo | cores predominantes | observação |
|---|---|---|
| `rspe.ico` | `#00602C` | disco verde cheio, com detalhes claros; tamanhos 16/24/32/48/64/128/256 |
| `apto_selo.png` (400 px) | `#FFFFFF`, `#00602C`, `#7FB894` | fundo branco com traço verde |
| `extensao_seeu/icones/*.png` | `#FFFFFF` (maioria), traço verde | é o selo reduzido, ou seja, a versão **clara**, oposta à do `.ico` |
| `logo_defensoria.png` | `#1E6B34`, `#D8BB73` (dourado), `#373737` | logo institucional |
| `ui.html` | Cinzel 700 (embutida em base64, `ui.html:30`; `font-family:Cinzel,Georgia,serif` em `ui.html:33,379`) | Arial 13 px no restante |

Ao todo, são cinco verdes de marca ou de sucesso circulando: `#00602C` (selo/.ico), `#1D5A3B` (UI e extensão), `#1E6B34` (logo da Defensoria), `#1D6B37` (verde de situação) e `#1a5d1a` (conversor).

### 1.6 Petições (`*.docx` na raiz)
| modelo | margens (sup/dir/inf/esq, cm) | rodapé a partir da borda | fontes |
|---|---|---|---|
| Progressão ao regime semiaberto | 2,5 / 3,0 / 2,5 / 3,0 (`w:pgMar top=1417 right=1701 bottom=1417`) | 1,25 cm | Arial 12 pt, entrelinha 1,5 |
| Prescrição executória | 3,0 / 2,0 / 2,0 / 3,0 (`top=1701 right=1134 bottom=1134`) | 1,25 cm | Arial 12 pt, entrelinha 1,5 |
| Indulto 2025 inc. VIII primário | 3,5 / 3,0 / 2,0 / 3,0 (`top=1985 right=1701 bottom=1134`) | **0,25 cm** (`w:footer=142`) | Arial 12 pt, mais trechos residuais em Times New Roman, Courier New e Tahoma |

O timbre do cabeçalho é a imagem "Defensoria Pública MS | NUSPEN" (`word/media/image1.png`, a mesma nos três). No PDF, a Arial foi trocada pela Liberation Sans, que tem as mesmas métricas.

---

## 2. Achados

Contrastes calculados pela fórmula de luminância relativa do WCAG 2.x.

| id | superfície | tela e local no código (arquivo:linha) | problema | evidência | princípio violado | gravidade | esforço | mudança sugerida |
|---|---|---|---|---|---|---|---|---|
| EXT-01 | extensão | Popup inteiro: `popup.html:41-90`, largura fixa em `popup.html:9` | O conteúdo tem 912 px de altura no estado inicial e chega a 1 378 px com o lote aberto. O Chrome limita o popup a 600 px, então tudo abaixo de "Lote" fica fora da tela: a pasta, o aviso no SEEU e os **últimos downloads**, que são a confirmação de que o RSPE foi salvo. | extensao_popup_inicial.png, extensao_popup_inicial_600px.png, extensao_popup_lote_sap.png | Nielsen 1 (visibilidade do estado do sistema); Nielsen 8 (estética e design minimalista) | alta | M | Reordenar: (1) "Baixar o RSPE do processo aberto" com o destino logo abaixo; (2) últimos downloads (3 itens); (3) Triagem como link secundário. Levar Base, Pasta e Aviso para uma área recolhível "Configurações" e o Lote para `<details>` ou uma página própria, como a Triagem. Meta: estado inicial ≤ 600 px. |
| EXT-02 | extensão | `popup.html:57` e `popup.html:62` (dois `button.pri`) | Dois botões primários verdes cheios, de mesmo peso e largura total ("Triagem da Mesa" e "Baixar o RSPE"). A Triagem vem primeiro, embora a tarefa principal do popup seja salvar o RSPE. | extensao_popup_inicial.png | Nielsen 8; Nielsen 4 (consistência: a tela principal usa um único primário por área) | média | P | Deixar um único primário, "Baixar o RSPE", no topo. A Triagem vira botão secundário (contorno) ou link "Abrir Triagem ↗". |
| EXT-03 | extensão | `.dica` em `popup.html:25`, rodapé em `popup.html:36`, `li .q`/`.m` em `popup.html:33-35`; triagem `.sub` em `triagem.html:62`, `footer` em l.87 | O texto auxiliar de 11-12 px em `#8E958F` sobre branco tem **3,07:1** (2,87:1 sobre `#F6F8F6` e 2,98:1 sobre `#FBFCFB`). É justamente onde ficam instruções críticas: o destino do arquivo, a regra de "um RSPE por dia" e a ajuda do lote. | código, mais extensao_popup_inicial.png e extensao_triagem_com_dados.png | WCAG 1.4.3 Contraste mínimo (4,5:1) | alta | P | Usar `--tx3: #6B726C` (≈ 5,0:1 sobre branco) ou o `#767C82` da tela principal (4,4:1, ainda abaixo de 4,5:1 em 11 px; prefira `#6B726C`). Subir as dicas para 12 px. O mesmo vale para a etiqueta "lendo…" da Triagem (`triagem.html:70`, `#8E958F` sobre `#EFF1EF` = **2,70:1**): passar para `#5C6660`. No botão desabilitado por `opacity:.5` (`triagem.html:28`, branco sobre `#8EAC9D` = 2,46:1), usar fundo `#E9ECE9` e texto `#6B726C`. |
| EXT-04 | extensão | `select,input` em `popup.html:18`, `button` em l.21; `triagem.html:25-26` | A borda de campos e botões secundários (`#DDE3DD` sobre branco) tem **1,30:1**. Os botões "Incluir", "Retirar…", "Iniciar", "Parar" e "Limpar histórico" e o campo "Base nova" quase não se distinguem do fundo. | extensao_popup_inicial.png | WCAG 1.4.11 Contraste não textual (3:1) | média | P | Borda dos controles em `#8E958F` (3,07:1) ou mais escura. Manter `#DDE3DD` só nos divisores de seção. |
| EXT-05 | extensão | `popup.js:116` ("Baixando: Downloads\…" em verde); `popup.js:118` (`setTimeout(carregar, 2500)`) | A mensagem verde "Baixando…" aparece quando o pedido **só começou**. Se a gravação falhar depois (por exemplo, "o Chrome recusou gravar o arquivo", `background.js:183`), a caixa verde continua lá. O erro só surge na lista "Últimos downloads", que está fora da área visível (EXT-01). | extensao_popup_sucesso.png, mais o código | Nielsen 1; Nielsen 9 (ajudar a reconhecer e recuperar erros) | alta | M | Estado em 3 fases na mesma caixa: "Baixando…" (neutro, com indicador), depois "Salvo em …\<arquivo>.pdf" (verde, com o nº do processo) ou "Não salvou: <motivo>" (vermelho). Atualizar pela resposta final do service worker, e não por um temporizador. |
| EXT-06 | extensão | `popup.js:114-115` | O erro "link do RSPE não encontrado" junta duas causas e duas ações num parágrafo de 4 linhas ("recarregue a página" e "Clique em Situação Carcerária…"). Não diz qual tentar primeiro. | extensao_popup_erro_rspe_nao_achado.png | Nielsen 9; Nielsen 10 (ajuda e documentação) | média | P | Título curto ("RSPE não encontrado nesta página") e duas ações numeradas: "1. Abra a página do processo (não a Mesa) · 2. Se acabou de instalar, recarregue (F5)". Opcional: botão "Recarregar aba". |
| EXT-07 | extensão | `popup.html:78-82` (campo "Pasta dentro de Downloads") | O campo pode ser editado livremente, mas o LEIA-ME manda **não trocar** ("é a que o APTO vigia", `LEIA-ME.txt:40`). Trocar o valor quebra a ligação com o APTO sem nenhum aviso na tela. | extensao_popup_inicial.png, mais `LEIA-ME.txt:40` | Nielsen 5 (prevenção de erros) | média | P | Mostrar como texto só de leitura ("Downloads\APTO"), com um "alterar…" escondido em Configurações avançadas e um aviso de que o APTO só vigia essa pasta. |
| EXT-08 | extensão | `triagem.html:51` (`table-layout:fixed`) e `triagem.html:155` (colunas fixas de 44+205+130+118+210 px) | Em janelas de ~800 px (meia tela num monitor de 1600 px, uso comum ao lado do SEEU), as colunas flexíveis "Motivo" e "Última decisão" ficam com cerca de 20 px e o texto quebra **letra por letra**. | extensao_triagem_800px.png | WCAG 1.4.10 Reflow; Nielsen 8 | alta | M | `min-width` nas colunas flexíveis (≥ 220 px) com rolagem horizontal da tabela, ou, abaixo de 1100 px, layout em cartões (processo/prazo em cima, motivo e decisão empilhados). |
| EXT-09 | extensão | `triagem.js:610` (`th.onclick`); `triagem.js:480` (`tr.l` onclick para abrir os detalhes) | A ordenação pelos cabeçalhos e a abertura do detalhe de cada processo só funcionam com o mouse: `<th>` e `<tr>` não recebem foco, não têm `tabindex` nem `aria-sort`/`aria-expanded`. Os chips de filtro (`triagem.js:349,382`) não informam o estado ligado (sem `aria-pressed`). | código | WCAG 2.1.1 Teclado; WCAG 4.1.2 Nome, função, valor | média | M | Colocar `<button>` dentro do `th` com `aria-sort`; dar a cada linha um botão "▸ detalhes" com `aria-expanded`; usar `aria-pressed` nos chips. |
| EXT-10 | extensão | `content.js:43-53` (aviso no SEEU) | O aviso de **erro** também some sozinho em 6 s, e pede uma ação ("clique em 'retomar' no ícone do APTO"). Com `pointer-events:none`, não dá para fixar, selecionar o texto ou fechar. O aviso fica sobre o canto inferior direito do SEEU. | extensao_injetado_seeu_aviso_erro.png, extensao_injetado_seeu_aviso_ok.png | WCAG 2.2.1 Tempo ajustável; Nielsen 9 | média | P | Sucesso some em 6 s. Erro fica até ser fechado (botão ×, com `pointer-events:auto` só no ×) e usa `role="alert"`. Colocar a ação no próprio aviso ("Retomar"). |
| EXT-11 | extensão | Paleta e fontes de `popup.html:7-12` e `triagem.html:9-15` comparadas com `ui.html` | A extensão tem sistema visual próprio: vermelho `#B42318` (no app, `#A3201D`), âmbar `#8A5A00` (`#7E6200`), azul `#1F4E79` (`#2E4D6E`), cinza terciário `#8E958F` (`#767C82`), cantos de 6-10 px e chips de 999 px (no app, 3-4 px), fonte system-ui (no app, Arial 13 px) e nome em Georgia (no app, Cinzel). Parece outro produto. | código, mais extensao_popup_inicial.png e extensao_triagem_com_dados.png | Nielsen 4 (consistência e padrões) | média | M | Extrair os tokens de `ui.html` para um `tokens.css` copiado para `extensao_seeu/` (cores, raio 4 px, Arial 13 px) e embutir a Cinzel (woff2 local, como em `ui.html:30`) só para a palavra "APTO". |
| CONV-01 | conversor | `conversor.py:261` (`f"{vel:.0f}x mais rápido que o tempo real"`) | Quando a conversão é **mais lenta** que o tempo real (WebM com vídeo VP9, num vídeo longo), a tela mostra "**0x mais rápido que o tempo real**". O número é absurdo e engana justamente no caso mais demorado. | conversor_convertendo_lento_vp9.png | Nielsen 2 (linguagem do usuário); Nielsen 1 | média | P | Se `vel < 1`, mostrar "≈ 2,2× mais lento que a duração do vídeo". Com uma casa decimal quando `vel < 10`. Ou retirar a velocidade e deixar só "faltam ~6 h 13 min". |
| CONV-02 | conversor | `conversor.py:226-229`, `480`, `499-500` | Uma falha mostra numa caixa de diálogo os últimos 600 caracteres do stderr do ffmpeg, em inglês e com endereços hexadecimais ("[aac @ 0x55d0…] Error while decoding stream…"), em negrito e sem quebra legível. Não diz se o arquivo está corrompido nem o que fazer. | conversor_erro.png | Nielsen 9 (mensagens de erro em linguagem simples); Nielsen 2 | alta | M | Traduzir os casos comuns ("arquivo corrompido ou incompleto", "formato não suportado", "sem permissão na pasta", "disco cheio"), cada um com a ação sugerida. Guardar o texto técnico num `.log` ao lado da saída e oferecer "Copiar detalhes". |
| CONV-03 | conversor | `conversor.py:456` (o mesmo botão vira "Cancelar") e `519-523`; `490-494` (fim cancelado) | "Converter" vira "Cancelar" **no mesmo lugar**, e cancelar não pede confirmação: um clique errado depois de 2 h de VP9 apaga a parte gerada. Num lote, os arquivos que já ficaram prontos são mantidos, mas a tela só diz "Cancelado." e não informa o que sobrou. | conversor_convertendo.png, conversor_cancelado.png | Nielsen 5 (prevenção de erros); Nielsen 1 | alta | P | Botão "Cancelar" separado (secundário, à esquerda), com confirmação quando já se passaram mais de 2 min. Status final no formato "Cancelado. 1 de 2 arquivos ficou pronto: …", com "Abrir pasta" habilitado. |
| CONV-04 | conversor | `conversor.py:287` (`dividir=True` por padrão), `362-364`, `389` | Com "WebM com vídeo", a opção de dividir continua marcada e a estimativa diz "~1,87 GB para 3 h 59 min **de áudio** (em 11 partes)". Um vídeo vira 11 pedaços sem o usuário pedir, e o texto chama vídeo de "áudio". O LEIA-ME manda desmarcar à mão. | conversor_formato_webm_video.png | Nielsen 5; Nielsen 2 | média | P | Desmarcar a divisão automaticamente quando o formato for de vídeo, avisando com uma linha de texto. Trocar "de áudio" por "de gravação". |
| CONV-05 | conversor | `conversor.py:389` (estimativa só de tamanho) | Antes de começar, o programa estima o **tamanho**, mas não o **tempo**. Para VP9 a diferença é enorme (o LEIA-ME fala em cerca de 1 h para 3 h de vídeo), e a pessoa só descobre depois de iniciar. | conversor_formato_webm_video.png, conversor_arquivos_mp3.png | Nielsen 1; Nielsen 5 | média | P | Mostrar uma faixa de tempo por formato antes de converter ("tempo estimado: 40-70 min nesta máquina"), com velocidade típica por codec e um aviso âmbar para VP9 ≥ 1 h. |
| CONV-06 | conversor | `conversor.py:274` (título fixo), `484-502` (fim) | Numa conversão de horas, a pessoa minimiza a janela, mas o título e a barra de tarefas não mostram o progresso. O fim só é avisado por um diálogo modal. Também não há como tirar **um** arquivo da lista: só existe "Limpar", que tira todos (`conversor.py:341-348`). | conversor_convertendo.png, conversor_concluido.png | Nielsen 1; Nielsen 3 (controle e liberdade) | baixa | P | Título no formato "37% · Conversor de Áudio"; som de sistema ou `bell()` ao terminar; botão "Remover" para o item selecionado (e tecla Delete). |
| ID-01 | identidade | `extensao_seeu/icones/16.png`, `32.png`, `48.png`; `manifest.json:69-79` | O ícone da extensão é o selo **claro** (fundo branco com traços finos verdes). Em 16 px vira um disco quase branco, com uma ampulheta de cerca de 3 px; numa barra escura do Chrome, é uma mancha branca. O ícone do app (`rspe.ico`) é o **inverso**: disco verde cheio. São duas marcas para o mesmo produto. | identidade_extensao_icones.png, identidade_ico_tamanhos.png | Nielsen 6 (reconhecer em vez de lembrar); WCAG 1.4.11 (3:1 para gráficos essenciais) | alta | M | Um único glifo de 16 a 32 px: ampulheta branca grossa sobre disco ou quadrado `#1D5A3B`, sem anéis nem texto. Usar esse glifo no `.ico` (16/24/32) e em `icones/16`/`32`. O selo completo fica só a partir de 64 px. |
| ID-02 | identidade | `apto_selo.png` (texto circular "Auditoria de Prazos e Tempo de Cumprimento Organizada"); popup `popup.html:42` (48 px exibido a 24 px) e triagem `triagem.html:100` (26 px) | A sigla "APTO" **não aparece** no selo. O texto circular é ilegível abaixo de ~128 px, e no cabeçalho da extensão (24-26 px) os anéis e as letras viram ruído. O nome da marca depende de um texto em Georgia ao lado. | identidade_selo_reduzido.png, extensao_popup_inicial.png | Nielsen 6; Nielsen 8 | média | M | Fazer uma variante "lockup": glifo da ampulheta + "APTO" em Cinzel, para cabeçalhos ≤ 48 px. Reservar o selo com texto circular para relatórios e PDFs (`rspe_relatorio.py:158`), onde aparece grande. |
| ID-03 | identidade | `rspe.ico`/`apto_selo.png` (`#00602C`), `ui.html` (`#1D5A3B`, `#1D6B37`), `logo_defensoria.png` (`#1E6B34`), `conversor.py:361` (`#1a5d1a`) | Cinco verdes parecidos, mas diferentes. Na extensão, o verde de **sucesso** (`--g`) é o próprio verde da marca (`popup.html:7`), então uma mensagem de "salvo" se confunde com um elemento de marca. Em contraste, todos passam (`#00602C`/branco 7,75:1; `#1D5A3B`/branco 8,15:1). | código, mais identidade_ico_tamanhos.png | Nielsen 4 (consistência) | baixa | P | Fixar dois verdes: marca `#1D5A3B` (e ajustar o `#00602C` do selo a ele) e sucesso `#1D6B37`. Usar no conversor a cor de sucesso definida. |
| ID-04 | identidade | `conversor.py:273-280` (sem `iconbitmap`; título "Conversor de Áudio 1.2.0") | O conversor não tem ícone (aparece a pena do Tk na barra de tarefas e no Alt+Tab) nem nenhum vínculo visual com o APTO ou a Defensoria. Num computador com vários utilitários, fica difícil reconhecê-lo. | conversor_inicial.png | Nielsen 6 | baixa | P | Ícone próprio (por exemplo, uma onda sonora sobre o mesmo disco verde do glifo do APTO) via `iconbitmap`/`--icon` no PyInstaller, e o mesmo verde nos títulos de seção. |
| DOC-01 | petição | `Progressao ao regime semiaberto.docx`, `Prescricao executoria.docx` (word/document.xml, parágrafo de qualificação e pedido em `<w:b/>`) | Nesses dois modelos, o parágrafo inteiro de qualificação e pedido está em **negrito** (8 a 10 linhas). No Indulto, o negrito marca só os termos-chave ("DEFENSORIA PÚBLICA…", "Mutirão Processual – Pena Justa"). Com tudo em negrito, o pedido não se destaca, e os três modelos ficam com hierarquias diferentes. | peticao_progressao_semiaberto_p1.png, peticao_prescricao_executoria_p1.png, peticao_indulto2025_viii_primario_p1.png | Nielsen 4 (consistência); Nielsen 8 | média | P | Padronizar pela regra do Indulto: corpo normal, negrito só no nome da instituição, no programa e no pedido ("PROGRESSÃO AO REGIME SEMIABERTO", "prescrição da pretensão executória"). O texto jurídico não muda. |
| DOC-02 | petição | `w:pgMar` dos três modelos (ver §1.6) | Margens diferentes em cada modelo (superior de 2,5, 3,0 ou 3,5 cm; direita de 2,0 ou 3,0 cm). No Indulto, o rodapé fica a **0,25 cm** da borda (`w:footer=142`), dentro da área que muitas impressoras não imprimem. | código (document.xml), mais peticao_indulto2025_viii_primario_p1.png | Nielsen 4 | média | P | Uma margem única (por exemplo, 3/2/2/3 cm, como no padrão ABNT de peças) com rodapé a 1,25 cm. Aplicar com um `styles.xml`/`sectPr` comum aos 12 modelos. Os rodapés também divergem: o Indulto não traz a linha da instituição mas numera as páginas; Progressão e Prescrição não numeram, apesar de terem 2 páginas; o Indulto tem resíduos de Times, Courier e Tahoma. Usar um rodapé padrão com "pág. X de Y" e limpar as fontes para Arial (peticao_prescricao_executoria_p1.png). |
| DOC-03 | petição | `Progressao ao regime semiaberto.docx` (parágrafos vazios ou quebra no fim) | Uma petição de uma página gera uma **2ª página em branco**, só com o timbre e o rodapé. Ao imprimir ou protocolar o PDF, sai uma folha vazia. | peticao_progressao_semiaberto_p2.png | Nielsen 8 | média | P | Remover os parágrafos vazios e a quebra final do modelo; conferir no teste de geração que o nº de páginas é igual ao esperado. |
| DOC-04 | petição | Campos `{{…}}` e `{% if %}` em todos os modelos (por exemplo, `qualificad{{o_a}}`, `{{Sentenciado}}`) | No modelo, os campos e condicionais têm a mesma aparência do texto, e o documento gerado não destaca o que foi preenchido automaticamente (concordância `o_a`, frações, datas). O defensor precisa reler tudo para achar o que conferir. | peticao_prescricao_executoria_p1.png, peticao_indulto2025_viii_primario_p1.png | Nielsen 5 (prevenção de erros); Nielsen 6 | baixa | M | No modelo, deixar os campos com realce de cor (estilo de caractere "Campo APTO"). No documento gerado, opção "realçar campos preenchidos" (estilo removível de uma vez), sem alterar o texto. |

Total: 25 achados. São 11 da extensão, 6 do conversor, 4 de identidade e 4 de petições.

---

## 3. Tarefas reais

### 3.1 "Salvar um RSPE pelo popup da extensão"
Pré-condição: SEEU logado, processo de execução aberto e APTO aberto com a base certa.

| passo | ação | cliques | dúvidas e onde o olho se perde |
|---|---|---|---|
| 1 | Abrir o processo no SEEU | 1-2 (no SEEU) | **O automático talvez já tenha salvo.** O único sinal é o aviso de 6 s no canto do SEEU (EXT-10) ou o número no ícone. Quem não viu o aviso abre o popup para conferir. |
| 2 | Clicar no ícone APTO na barra | 1 (2 se o ícone não estiver fixado: quebra-cabeça e APTO) | Em 16 px, o ícone claro do selo se perde na barra (ID-01). |
| 3 | Conferir a base de destino | 0 (leitura) | O olho passa por "Base de destino", "Base nova", "Incluir" e "Retirar a base escolhida da lista" antes de chegar à linha que importa: "Salva em: Downloads\APTO\<base>\…", em cinza 11 px a 3,07:1 (EXT-03). Se o APTO estiver fechado, o aviso vermelho "APTO fechado…" aparece **abaixo** do destino. |
| 4 | Achar o botão | 0 | Primeiro aparece "Triagem da Mesa do Defensor", um botão verde idêntico (EXT-02). O botão certo é o **segundo** verde, a 420 px do topo. |
| 5 | Clicar em "Baixar o RSPE do processo aberto (SEEU)" | 1 | A caixa verde "Baixando: …" aparece e o usuário entende que terminou, mas não há confirmação de gravação (EXT-05). Fora do SEEU, o erro vermelho é claro (extensao_popup_erro_sem_seeu.png). Se o link não foi achado, o texto de 4 linhas mistura duas ações (EXT-06). |
| 6 | Confirmar que salvou | 0-1 (rolar) | "Últimos downloads" atualiza após 2,5 s, mas está **abaixo da área visível do popup de 600 px** (EXT-01). Sem rolar, a pessoa não vê nem sucesso nem erro. |

Total: 2-3 cliques e, no mínimo, uma rolagem para confirmar. O caminho feliz é curto, mas a hierarquia esconde o resultado.

### 3.2 "Converter um vídeo longo no Conversor de Áudio"
Exemplo: reunião fictícia de 3 h 12 min, 3,2 GB.

| passo | ação | cliques | dúvidas e onde o olho se perde |
|---|---|---|---|
| 1 | Abrir o programa (duplo clique) | 2 | Sem ícone próprio, ele se perde entre os outros atalhos (ID-04). |
| 2 | "Escolher…" e selecionar o vídeo | 2-3 | Não dá para arrastar o arquivo para a janela. A lista mostra "lendo…" e depois o tamanho e a duração, o que é bom. |
| 3 | Escolher formato e qualidade | 2-4 | São 8 formatos com nomes técnicos (Vorbis, Opus, VP9, FLAC). A recomendação "recomendado para reuniões" só aparece **dentro** da qualidade do MP3. A estimativa em verde (`#1a5d1a`, 7,0:1 no Windows) é clara para tamanho, mas **não dá tempo** (CONV-05). Para WebM com vídeo, a divisão em 11 partes já vem marcada (CONV-04). |
| 4 | (Opcional) "Mudar…" a pasta | 2 | O texto cinza "Mesma pasta do arquivo original" funciona bem. |
| 5 | "Converter" | 1 | Se faltar espaço, um aviso aparece antes, o que é bom (`conversor.py:504-517`). |
| 6 | Acompanhar | 0 | A barra, o percentual e "decorrido · faltam ~ · Nx" funcionam bem em MP3 (conversor_convertendo.png). Em VP9 aparece "0x mais rápido" (CONV-01). Com a janela minimizada não há progresso no título (CONV-06). O botão "Converter" virou "Cancelar" no mesmo lugar: risco de clique acidental (CONV-03). |
| 7 | Fim | 1 (OK) e 1 ("Abrir pasta") | O diálogo de conclusão lista os arquivos e os tamanhos, o que é bom. Em caso de erro, o diálogo traz o stderr do ffmpeg em inglês (CONV-02). |

Total: cerca de 9-12 cliques. O fluxo 1-2-3 numerado é claro. Os pontos fracos estão no feedback de tempo, nos erros técnicos e no cancelamento sem confirmação.

---

## 4. Capturas (em `docs/analise_design/capturas/`)

**Extensão: popup (360 px, página inteira, salvo indicação)**
- `extensao_popup_inicial.png`: ligado, APTO aberto, com histórico.
- `extensao_popup_inicial_600px.png`: o que cabe no limite de 600 px do Chrome.
- `extensao_popup_foco_teclado.png`: foco visível no campo "Base nova".
- `extensao_popup_apto_fechado.png`, `extensao_popup_sucesso.png`, `extensao_popup_erro_sem_seeu.png`, `extensao_popup_erro_rspe_nao_achado.png`, `extensao_popup_desligada.png`, `extensao_popup_pausada.png`.
- `extensao_popup_lote_seeu.png` (lote em andamento) e `extensao_popup_lote_sap.png` (lote SAP concluído, com as ações).

**Extensão: Triagem**
- `extensao_triagem_vazia.png`: sem SEEU aberto.
- `extensao_triagem_com_dados.png`: 1366 px, com 5 processos fictícios.
- `extensao_triagem_detalhe.png`: linha expandida.
- `extensao_triagem_800px.png`: colunas colapsadas.

**Extensão: elementos injetados** (página fictícia que imita o SEEU)
- `extensao_injetado_seeu_aviso_ok.png` e `_zoom`.
- `extensao_injetado_seeu_aviso_erro.png` e `_zoom`.

**Conversor** (xvfb, tema `clam`/Linux)
- `conversor_inicial.png`, `conversor_arquivos_mp3.png`, `conversor_formato_webm_video.png`.
- `conversor_convertendo.png`, `conversor_convertendo_lento_vp9.png`.
- `conversor_cancelando.png`, `conversor_cancelado.png`.
- `conversor_concluido.png`, `conversor_erro.png`.
- `conversor_tamanho_minimo_580x560.png`.

**Identidade**
- `identidade_ico_tamanhos.png`: `.ico` em 16/24/32/48, em 1× e 4×, sobre fundo claro e escuro.
- `identidade_extensao_icones.png`: 16/32/48/128.
- `identidade_selo_reduzido.png`: selo reduzido para 16/32/64.

**Petições**
- `peticao_progressao_semiaberto_p1.png` e `peticao_progressao_semiaberto_p2.png` (página em branco).
- `peticao_indulto2025_viii_primario_p1.png`.
- `peticao_prescricao_executoria_p1.png`.

**Scripts de captura** (fora do repositório):
- `<pasta de trabalho>/cap_ext.py`
- `<pasta de trabalho>/cap_conv.py`
