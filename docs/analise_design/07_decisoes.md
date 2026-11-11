# Decisões sobre a proposta (27/10/2026)

Linha gráfica escolhida: **E · menu lateral que recolhe e expande**, no visual do Windows 11 (Fluent 2). Telas de todas as abas e dos detalhes em [APTO_linha_E_aprovada.pdf](APTO_linha_E_aprovada.pdf).

## Ajustes pedidos sobre a linha E

| item | como fica |
|---|---|
| Importar | um botão só, “Importar ▾”, com “Arquivos PDF…” e “Uma pasta inteira…” |
| Complemento “sem pedido no RSPE - requerer” | sai da coluna Situação da tela; os demais complementos do programa ficam (ex.: “verificar criminológico, indeferimento ou falta”). O texto continua sendo gerado pelo programa (relatório em PDF, dica) |
| Ações da linha | os ícones de hoje (ficha, Quadro, abrir), mais escuros, com dica; a ficha fica verde quando importada |
| Filtro | “Combinar filtros ▾”: caixas de marcar nos grupos Situação, Pedido, Benefícios a conferir e Conferência, que podem ser combinadas |

## As 15 sugestões

| nº | sugestão | decisão |
|---|---|---|
| 1 | Estrutura igual em todas as abas | aprovada |
| 2 | Cabeçalho em uma faixa; filtro ao lado da ordem da lista | aprovada |
| 3 | Abas agrupadas por tarefa, nomes por extenso | aprovada |
| 4 | Contadores | aprovada no formato 2 (número maior, traço de cor, rótulo ao lado). “Até 60 dias” fica sozinho; “A verificar” ganha contador e grupo próprios, na cor do RSPE antigo |
| 5 | Ordem inicial | por situação; alfabética a um clique |
| 6 | Situação curta + complemento embaixo | aprovada |
| 7 | Caixa do pedido | só a caixa, como hoje |
| 8 | Uma cor, um significado | aprovada (verde só “em ordem / cabe”; até 90 dias em azul-acinzentado) |
| 9 | Legenda por aba, em tabela | aprovada |
| 10 | Painel do assistido essencial | aprovada; na linha Indulto, só os decretos cabíveis, como hoje |
| 11 | Detalhe da Prescrição em passos | aprovada |
| 12 | Avisos (sucesso com Desfazer, erro fica) | aprovada |
| 13 | Importação com progresso e resumo | aprovada |
| 14 | Lista vazia que orienta | aprovada |
| 15 | Notebooks | aprovada; o menu começa recolhido abaixo de 1400 px e expandido em telas largas; depois vale a última escolha do usuário |

Protótipo: `demonstracao/abas_simuladas.html?tema=7&menu=aberto` (ou `menu=recolhido`, `menu=sobre`).

## Aplicação no programa (versão 7.15.0)

A linha E e as 15 decisões foram aplicadas no `ui.html` (e, para "Parar depois deste arquivo", uma função nova na `Api` do `rspe_app.py`). Antes e depois, com o programa real e a base fictícia, em [APTO_7.15_antes_depois.pdf](APTO_7.15_antes_depois.pdf). Nenhuma regra, cálculo ou texto jurídico mudou; o inventário de controles da tela, antes e depois, não perdeu nenhuma função. Os 81 testes passam (o novo `teste_linha_e.py` cobre a tela e a parada da importação).

## Revisão de interface da 7.18.0 (11/11/2026)

Revisão feita com a skill de interface (ui-ux-pro-max) sobre a 7.17.0, com o programa real e a base fictícia. As 12 propostas ficaram numa página de apresentação, com antes e depois. A troca de abas continua instantânea: transições foram dispensadas.

| nº | proposta | decisão |
|---|---|---|
| A1 | tirar o filete verde que sobrava sob a aba ativa do menu | aplicada |
| A2 | contadores sempre numa linha, rótulo em até duas | aplicada; "A verificar" passa a "Verificar", para não quebrar |
| A3 | tabela do decreto (Indulto) cabendo na tela; legenda só no rodapé | aplicada; o botão passa a "Linha do tempo", como na Extinção |
| A4 | Quadro com as quatro colunas na janela; quadro vazio orienta | aplicada |
| A5 | dica própria no rodapé de Dados prisionais | aplicada |
| A6 | busca legível no notebook ("Buscar (Ctrl+K)") | aplicada |
| B1 | subnavegação em três formatos (segmentado, lista lateral, seções), verde cheio só nas ações principais | aplicada |
| B2 | um título só em Dados da base e Dados prisionais | aplicada |
| B3 | ficha do assistido: ações no topo, "Mais" para remover, conduta em etiqueta, barra de cumprimento | aplicada |
| B4 | ícones desenhados no lugar de caracteres | aplicada |
| B5 | algarismos alinhados nas colunas | aplicada |
| C1 | consolidar o CSS (uma regra por seletor, paleta, escalas, menos !important) | aplicada de uma vez, em seis etapas conferidas com o estilo calculado de 220 mil elementos em 47 telas |
