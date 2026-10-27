# 4. Tarefas reais: atrito medido

Cada tarefa foi percorrida na ponte (o `ui.html` real ligado à `Api` real, com a base fictícia de 144 assistidos; e a de 720 para desempenho).

- **Cliques** contam a partir da aba Geral aberta.
- **Dúvidas** são os pontos em que a tela não diz o que fazer.
- **Onde o olho se perde** aponta onde a leitura trava.
- As tarefas 8 e 9 vêm da análise da extensão e do conversor: [`anexos/extensao_conversor_identidade.md`](anexos/extensao_conversor_identidade.md), seção 3.

| # | tarefa | cliques hoje | cliques com a proposta | atrito principal | achados |
|---|---|---|---|---|---|
| 1 | Criar uma base e importar 300 PDFs; entender o progresso e o que deu erro | 4-5 (criar, nomear, Importar, escolher, Fechar o resumo) | 4-5 | Durante a importação, o progresso é um texto de 12 px no rodapé. No fim, falhas, parciais e duplicados vêm misturados numa lista de 23 itens. | APP-11 |
| 2 | Descobrir quem atingiu o lapso de progressão sem pedido e marcar "pedido feito" | 4 por pessoa (aba, cartão "Vencido", caixa "Pedido", "Marcar pedido feito") + rolagem | 2 por pessoa (aba; "Marcar" na linha, que abre o mesmo formulário já com a data) | A lista abre em ordem alfabética, e o cartão "Vencido" é a única entrada. "Sem pedido **no RSPE**" (SEEU) e "Pedido feito" (marcado no APTO) são duas noções de pedido que a tela não diferencia. | APP-01, APP-02, APP-05 |
| 3 | Abrir a ficha de um assistido, entender por que uma data está "A VERIFICAR" e copiar a fundamentação | 4-6 (abrir, rolar até "Cálculos do programa", "ver cálculo completo", "Copiar") | 3 (abrir, clicar no "A verificar" da linha, "Copiar fundamentação") | A linha "Indulto" da ficha mostra só os cabíveis; o "a verificar" está mais abaixo, em "Cálculos do programa", e muda de nome ("possível"). Na Prescrição, o "A VERIFICAR" fica na linha expandida, e a expansão estoura a largura. | APP-12, APP-04 |
| 4 | Verificar o cabimento de indulto ou comutação por decreto e inciso | 3 (aba Indulto, decreto na barra lateral, "Verificar indulto/comutação"); o comparativo por inciso fica recolhido (+1) | 3 | O resultado está só na cor do selo; "não cabe" e "impeditivo" quase não se distinguem. A boa notícia: a linha do tempo tem estrutura clara (1 Crimes · 2 Resultado · 3 Comparativo · 4 Como cheguei aqui · 5 Fundamentação). | APP-06, APP-22 |
| 5 | Achar uma prescrição na linha do tempo | 3 (aba Prescrição, cartão "Prescrição aparente", clicar na linha) + rolagem horizontal | 2 | A lista mistura os 19 "aparente" com 119 "não prescrita". A linha expandida obriga a rolar para o lado e corta o botão "Abrir ficha". A figura da linha do tempo não chega ao PDF. | APP-01, APP-04, PDF-13 |
| 6 | Registrar um atendimento e usar o Quadro do Usuário | Atendimentos: 2 (botão na Geral, "Importar…"); Quadro: 2-3 (ícone ▦ na linha ou "+ Cartão") | iguais | O modal de Atendimentos abre sem véu, colado na tabela. No Quadro, renomear coluna é um `prompt()`, e deixar o nome vazio **exclui a coluna**. O ícone ▦ que manda ao Quadro tem contraste de 3,1:1 e só uma dica ao passar o mouse. | APP-09, APP-10, APP-08 |
| 7 | Gerar um relatório PDF e uma exportação | 3 (Exportar, "Relatórios em PDF", "Gerar") e 3 para o Excel | iguais | Os padrões da janela trazem "Remição com nome" marcado. O PDF perde o negrito; o Excel imprime 687 páginas e tem datas em texto. | APP-20, PDF-01, XLS-01, XLS-02 |
| 8 | Salvar um RSPE pelo popup da extensão | 2-3 + rolagem para confirmar | 2, com a confirmação visível | O popup é mais alto que o limite de 600 px do Chrome, e a confirmação fica fora da tela. "Baixando…" aparece em verde antes de salvar. Há dois botões primários iguais. | EXT-01, EXT-02, EXT-05 |
| 9 | Converter um vídeo longo no Conversor de Áudio | 9-12 | 8-10 | Sem estimativa de tempo antes de começar; "0x mais rápido" no VP9; "Cancelar" no lugar de "Converter", sem confirmação; erro bruto da ffmpeg. | CONV-01 a CONV-05 |

## Desempenho percebido (base de 720 assistidos)

Medições no Chromium do servidor de análise. Num computador de repartição com WebView2, conte 2 a 4 vezes mais.

| ação | tempo | observação |
|---|---|---|
| abrir a base | 11 s | tela "Abrindo a base", com etapa e cronômetro (bom) |
| `listar` (dados para a tela) | 7,3 s no Python · 16,8 MB de JSON | cada recarga completa passa tudo pela ponte do pywebview |
| trocar de aba | 108-168 ms | redesenha 720 linhas e 24-29 mil elementos |
| cada tecla na busca | 81 ms | redesenha tudo a cada tecla, sem espera entre teclas |
| base de 144 | 32-46 ms por aba | sem problema perceptível |

Proposta (APP-18): espera de 150 ms na busca, `content-visibility:auto` nas linhas e desenho em lotes. Nada disso muda o que é mostrado.
