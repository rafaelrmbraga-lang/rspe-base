# 3. Proposta de sistema de design

Objetivo: **uma fonte de verdade para cor, letra, espaço e componentes**, usada pela tela, pelos PDFs, pelo Excel e pela extensão. Nada aqui muda regra, cálculo ou texto jurídico.

A implementação de referência está em [`antes_depois/ds.css`](antes_depois/ds.css). É um único `:root`, sem camadas, e funciona offline no WebView2. Os contrastes foram calculados com [`ferramentas/cor.py`](ferramentas/cor.py) pela fórmula do WCAG 2.2.

## 3.1 Tokens de cor (tema claro)

### Neutros e marca
| token | valor | uso | contraste |
|---|---|---|---|
| `--bg` | `#F5F6F6` | fundo da janela | — |
| `--surface` / `--surface-2` | `#FFFFFF` / `#F9FAFA` | cartões, tabela / faixas de grupo | — |
| `--line` / `--line-strong` | `#DADDE0` / `#8C9399` | divisórias (decorativas) / borda de campos e botões | 3,1:1 na borda de controle (WCAG 1.4.11) |
| `--tx` | `#1E2226` | texto principal | 16,0:1 no branco |
| `--tx-2` | `#454B50` | texto secundário | 8,8:1 |
| `--tx-3` | `#5C636A` | dicas, rótulos, rodapé (substitui `#767C82`, de 4,2:1) | 6,1:1 no branco · 5,6:1 no fundo |
| `--icon` | `#6B7278` | ícones de ação (substitui `#C4CAD4`, de 1,7:1) | 4,9:1 |
| `--brand` / `--brand-strong` / `--brand-soft` | `#1D5A3B` / `#153F2A` / `#E7EFEA` | marca, botão primário, seleção | 8,2:1 / 11,8:1 |

A marca fica com **um verde só** (`#1D5A3B`), e o `#00602C` do selo, do `.ico` e dos PDFs converge para ele. O verde de **situação** (`--ok`) é outro, para que "salvo/em ordem" não se confunda com a marca.

### Situação: uma escala só, válida em todas as abas
Cada nível tem **texto · fundo · marca** e **uma forma própria**. A cor nunca aparece sozinha: sempre vem com forma e rótulo.

| nível | onde se aplica hoje (rótulos inalterados) | forma | texto | fundo | marca | texto/branco | marca/branco |
|---|---|---|---|---|---|---|---|
| **crit**: agir já | Vencido · Prescrição aparente · Com alertas · Extinção cabível · Atestado sem peticionamento · Falta "Sim" | ◆ losango | `#A3201D` | `#FBEAEA` | `#A3201D` | 7,6:1 | 7,6:1 |
| **urg**: até 30 dias | Até 30 dias · Vence hoje · Término em até 30 dias | ▲ triângulo | `#9A4600` | `#FCEEDF` | `#C2620A` | 6,5:1 | 4,2:1 |
| **med**: até 60 dias ou a verificar | Até 60 dias · A verificar · Iminente · Pontos a verificar · Conferir remição · A apurar | ● círculo cheio | `#765C00` | `#F8F0D8` | `#A07C00` | 6,4:1 | 3,9:1 |
| **prox**: até 90 dias | Até 90 dias · Término em até 90 dias | ○ círculo vazado | `#454B50` | `#F1F2F3` | `#7A8188` | 8,8:1 | 4,0:1 |
| **ok**: em ordem ou cabe | Guia em ordem · Em ordem · Cabe/Cabível | ✓ visto | `#1D6B37` | `#E6F1E9` | `#2B8048` | 6,5:1 | 4,9:1 |
| **info**: registrado | Pena extinta · Pedido feito · Concedido | ■ quadrado | `#2E4D6E` | `#E7EDF4` | `#3F658D` | 8,7:1 | 6,1:1 |
| **neutro**: sem prazo | Sem prazo · Sem dados · Sem ficha · Não se aplica · Em cumprimento | — traço | `#5C636A` | `#F1F2F3` | `#8A9096` | 6,1:1 | 3,2:1 |

**Mudança de semântica proposta (pergunta 1):** "até 90 dias" deixa de ser verde e passa a cinza com círculo vazado. Com isso, o **verde passa a significar só "em ordem / cabe"**, em todas as abas.

**Daltonismo:** as formas são distintas por silhueta, então funcionam com protanopia, deuteranopia e tritanopia, e também impressas em P&B. Os pares que hoje se confundem (laranja × âmbar com ΔE 7 na deuteranopia; "não cabe" × "impeditivo" com ΔE 8) passam a se distinguir pela forma.

### Selos de decreto (Indulto e comutação)
O selo mostra o ano do decreto e um símbolo, e todos têm texto branco ≥ 5,9:1.

| resultado | selo | fundo | texto/fundo |
|---|---|---|---|
| Cabe | `25 ✓` cheio | `#1D6B37` | 6,5:1 |
| A verificar | `25 ?` cheio | `#8A5A00` | 5,9:1 |
| Não cabe | `25 ✕` **contorno** vermelho | branco, borda `#A3201D` | 7,6:1 |
| Impeditivo | `25 ⊘` cheio escuro | `#6E1512` | 11,8:1 |
| Concedido | `25 ★` cheio | `#2E4D6E` | 8,7:1 |
| Indeferido | `25 ✕` contorno roxo | branco, borda `#5A4A78` | 7,8:1 |
| Não alcançado / fora | `25 –` tracejado | branco | 6,1:1 |

### Tema escuro (opcional; pergunta 4)
O uso é diurno, em escritório, então o tema escuro não é prioridade. Os tokens já permitem um, sem tocar nos componentes:

| token | escuro |
|---|---|
| `--bg` / `--surface` / `--surface-2` | `#15191C` / `#1D2226` / `#232A2F` |
| `--line` / `--line-strong` | `#323A40` / `#4A545B` |
| `--tx` / `--tx-2` / `--tx-3` | `#E8EBED` / `#C2C8CD` / `#9AA3AA` |
| `--brand` / `--brand-soft` | `#5FB385` / `#1F3A2C` |
| crit / urg / med / ok / info (texto) | `#F08A85` / `#F0A35E` / `#E0C25A` / `#7CCB98` / `#8FB5E0` |

A ativação seria por `@media (prefers-color-scheme: dark)` ou por um botão na configuração. Os PDFs e o Excel continuam claros.

## 3.2 Tipografia

| papel | tela | PDF | Excel |
|---|---|---|---|
| Família | **Arial** (mantida: é a do SEEU e do PJe; hoje já é a efetiva) | Source Sans 3 / Source Serif 4 (mantidas: embutidas e bem resolvidas) | Arial (hoje Calibri) |
| Marca "APTO" | Cinzel só no subconjunto "APTO" (~3 KB) ou SVG | Cinzel | — |
| Números | `font-variant-numeric: tabular-nums` em toda tabela e data | os dígitos da Source Sans já são tabulares | datas como datas |

**Escala da tela: 5 tamanhos** (hoje são 19):

| token | px | uso |
|---|---|---|
| `--f-xs` | 12 | rótulos de cabeçalho, contagens, rodapé (mínimo absoluto) |
| `--f-sm` | 13 | corpo e tabela (padrão) |
| `--f-md` | 14 | número dos cartões, títulos de seção da ficha |
| `--f-lg` | 16 | títulos de modal pequeno |
| `--f-xl` | 20 | nome do assistido na ficha, títulos de modal |

Pesos: 400 e 700, mais nada. O negrito marca a **primeira parte da situação** ("Vencido há 41 dias") e os rótulos de grupo.

O controle "A A" de tamanho da letra continua: a escala inteira acompanha (`--f-*` multiplicados).

## 3.3 Espaço, raio e sombra

- **Espaço** (grade de 4): `--s1` 4 · `--s2` 8 · `--s3` 12 · `--s4` 16 · `--s5` 24 · `--s6` 32.
- **Altura de linha da tabela:** 36 px no modo compacto, que é o padrão proposto, e 44 px no confortável (pergunta 3).
- **Raio:** `--r-sm` 2 (selos) · `--r-md` 4 (controles, cartões) · `--r-lg` 8 (modais). Hoje são 17 valores.
- **Sombra:** `--sh-0` nenhuma (padrão) · `--sh-1` popover e painel de progresso · `--sh-2` modal e gaveta. Hoje são 20.
- **Foco:** `--focus` = anel duplo branco + verde de 2 px, visível em qualquer fundo.

## 3.4 Inventário de componentes

| componente | hoje (exemplos de classes) | proposta |
|---|---|---|
| **Botão** | `.btn`, `.btn.pri`, `.btn.ghost`, `.mini`, `.hbtn`, `.jz-b`, `.fdn-det`, `.fdn-vb`, `.cpf`, `.btn-sal`, `.qd-add`… (11 variantes) | 4 variantes (primário, secundário, fantasma, perigo) × 2 tamanhos (32 e 26 px). Um primário por área. |
| **Botão de ícone** | `.qbtn`, `.fico`, `.pin`, `.cpn`, `.st-ok`, `.pa-ok` | 28 × 28 px (alvo ≥ 24 px), cor `--icon`, `aria-label` obrigatório e dica igual ao rótulo. |
| **Abas** | `.tab` (12 iguais) | Abas em grupos com rótulo; menu "Mais" abaixo de 1 400 px. |
| **Sub-abas / alternador** | `.subtabs`, `.tlv-dec`, `.cw-tabs`, `.geo-vis` | Um "controle segmentado" com `aria-pressed`. |
| **Filtro de situação** | `.stat` (cartão) + `<select>` | Chip com **forma + número + rótulo**, que liga e desliga; o seletor fica para filtros que não são de cor. |
| **Texto de situação** | `.pill` (com 3 camadas sobrepostas), `.falta`, `.apurar`, `.dres`, `.stt`, `.selo`, `.dc-ch` | `.sit.{nível}`: marca + texto, com a 1ª parte em negrito. Um componente para todas as abas. |
| **Selo de decreto** | `.mx i` | `.dz.{resultado}` com símbolo (ver 3.1). |
| **Tabela** | `table`, `.subtab`, `.pc`, `.fdt`, `.lt`, `.px-tab`, `.bd-t`, `.enc`, `table.atd`, `table.hist` | Uma tabela base (cabeçalho fixo, linha com foco, faixas de grupo, densidade) e uma subtabela (linha expandida) com rolagem própria. |
| **Linha expandida** | `tr.sub` com várias estruturas | Mesma regra em todas as abas: clique ou Enter expande, e "↗" abre a ficha. |
| **Gaveta (ficha do assistido)** | `.drawer` | Mantém. Cabeçalho com ações agrupadas; o "por quê" fica junto da linha. |
| **Modal** | `.modal .box` (sem véu) | Véu, foco preso, Esc fecha, foco volta; rodapé com ações à direita e a secundária à esquerda. |
| **Confirmação** | `confirm()` ×10, `prompt()` ×6 | `Confirmar` com verbo e consequência; `Desfazer` para ações reversíveis; campo de data próprio. |
| **Aviso** | `.toast` (3,5 s, sem `role`) | `status` (sucesso, 5 s, com "Desfazer") e `alert` (erro, fica até fechar). |
| **Progresso** | `.prog` no rodapé, `.lbox` (tela cheia) | Painel fixo de importação (contagem, falhas ao vivo, "Parar"); a tela de carregar a base fica como está. |
| **Chamada (callout)** | `.qd`, `.ac`, `.fdn-onde`, `.fdal`, `.dbbox`, `.rsm`, `.rc`, `.px-res`, `.ptl-res`, `.expl` (10 variantes) | `.call.{nível}`: filete + forma + título + passos numerados + ações. |
| **Legenda** | `.leg`, `.ptl-legend`, `.tlv-leg`, `.provleg`, `.dleg`, `.bd-cl` | Uma legenda que usa as mesmas formas e, quando faz sentido, filtra. |
| **Campo** | `input` com 4 estilos (`.wrow`, `.pf`, `.fq-n`, `.qd-form`) | Um campo (32 px, raio 4, foco com anel); campo de data dd/mm/aaaa com validação. |
| **Cartão do Quadro** | `.qd-card`, `.qa-c`, `.fq-c` | Mantém; usa os tokens de situação no prazo. |
| **Estado vazio** | `.empty` | Título + uma frase + ação primária (ex.: "Importar listagem…"). |

## 3.5 Como chegar lá sem quebrar o arquivo único

1. **Camada de tokens no topo do `<style>`:** um `:root` novo com os nomes da proposta. As variáveis antigas (`--pri`, `--tx3`, `--r-dot`…) viram **apelidos** delas (`--tx3: var(--tx-3)`), e os 4 blocos `:root` atuais saem.
2. **Componentes um a um**, começando pelos de maior uso (`.sit`, `.chip`, `.btn`, `.modal`), apagando as regras mortas das camadas antigas.
3. **JS:** as cores fixas (`DEC_COR`, roscas) passam a ler `getComputedStyle(document.documentElement)`.
4. **PDF e Excel:** `rspe_cores.py` exporta os mesmos valores (tela → `rspe_view.CORES` → `rspe_relatorio`/`rspe_export`).
5. **Extensão:** `extensao_seeu/tokens.css`, cópia gerada do mesmo arquivo.

Testes: a maior parte de `python testes.py` testa cálculo e leitura. Porém `teste_sistema.py:203-211`, `teste_q1610_sistema.py` e `teste_atendimentos.py:167-169` leem o `ui.html` como texto e conferem trechos literais. Alguns são de CSS: `.dv-seeu{…#C0261F…}` e `.pr-rem{…#FBE8EF…}`. Ao trocar essas cores por tokens, esses testes precisam ser atualizados na mesma mudança, com a mesma intenção (a caixinha vermelha e a vinho continuam existindo). Ainda assim, cada passo deve ser validado com a ponte de capturas (`ferramentas/roteiro.py`), comparando antes e depois.
