# 1. Resumo executivo

O APTO já é uma ferramenta séria e confiável: os textos jurídicos são precisos, todo clicável alcança o teclado, os PDFs embutem as fontes e a ficha do assistido é bem organizada. O que pesa é outra coisa: **a tela não põe o urgente na frente, e as cores querem dizer coisas diferentes em cada lugar**. Somam-se a isso camadas de estilo acumuladas, quatro paletas que não conversam entre si e peças impressas que perdem informação no papel.

Foram encontrados **70 problemas** (6 críticos, 21 altos), na tela, nos PDFs, no Excel, na extensão, no conversor, na identidade e nas petições. A lista completa está em [`02_achados.md`](02_achados.md).

## As 10 mudanças de maior impacto

1. **Abrir as listas de prazo pelo mais urgente.** Hoje Progressão, Livramento, Prescrição e Extinção abrem em ordem alfabética, e os 13 vencidos ficam espalhados entre 144 nomes. Com grupos "Vencido · Até 30 dias · …", quem já pode pedir aparece primeiro, sem esconder ninguém.

2. **Uma cor quer dizer uma coisa só, em todas as abas.** Hoje o verde é "vence em 90 dias" na Progressão e "está tudo certo" na Auditoria e no Indulto, e o amarelo tem quatro sentidos. A proposta é uma escala única: vermelho = agir já, laranja = até 30 dias, âmbar = até 60 dias ou a verificar, cinza = até 90 dias, verde = em ordem, azul = registrado.

3. **Cada situação ganha um símbolo, além da cor** (◆ ▲ ● ○ ✓ ■ –). Assim a leitura funciona para quem não distingue vermelho de verde e funciona impressa em preto e branco. Hoje, no papel, as 6 cores viram o mesmo cinza, e na aba Indulto o resultado de cada decreto está **só** na cor.

4. **Mais lista e menos moldura em telas pequenas.** Num notebook com o Windows em 150 %, cabeçalho, barras e rodapé tomam quase metade da altura e cabem 2,5 linhas da tabela. Com o cabeçalho numa faixa e as abas agrupadas, cabem cerca de 7.

5. **A resposta ao "por que A VERIFICAR?" fica junto da pergunta.** Na ficha do assistido, a linha "Indulto" mostra só o que é cabível, e o "a verificar" com a fundamentação fica mais abaixo, em "Cálculos do programa", com outro nome. A proposta mostra o motivo em passos numerados, com "Copiar fundamentação" ao lado.

6. **Importação que conta o que aconteceu.** Ao importar 300 PDFs, o progresso hoje é um texto pequeno no rodapé, e o resumo mistura falhas com duplicados. A proposta mostra quatro totais (entraram, falharam, com ressalva, ignorados), as falhas primeiro e o que fazer com cada uma.

7. **PDFs que imprimem como foram pensados.**
   - O negrito some em todo parágrafo dos relatórios (corrige-se com uma linha de código).
   - Títulos ficam sozinhos no pé da página.
   - O número do processo quebra no meio.
   - A linha de um assistido é partida entre duas páginas.

8. **Excel que ordena e imprime.**
   - As datas estão gravadas como texto, e por isso **ordenar por prazo dá resultado errado**.
   - Sem configuração de impressão, a planilha sai em 687 páginas.
   - A planilha não traz o aviso legal nem a data de referência.

9. **Textos e ícones legíveis e diálogos do próprio programa.**
   - O texto cinza auxiliar e os ícones das linhas não têm contraste suficiente (os ícones parecem desabilitados).
   - Dezesseis perguntas usam as caixas do Windows, inclusive a **correção da data-base**, digitada sem validação.

10. **Uma identidade só.** Hoje convivem cinco verdes, o ícone da extensão é o inverso do ícone do programa e fica ilegível em 16 px, e a extensão usa outras cores e outra letra. A proposta é um glifo único para tamanhos pequenos, dois verdes (marca e "em ordem") e os mesmos tokens na tela, no PDF, no Excel e na extensão.

## Por onde começar

A fase 1 do [roteiro](05_roteiro.md) junta 15 itens de até 1 dia cada. Os itens 1.1 a 1.10 resolvem boa parte dos pontos 1, 3, 7, 8 e 9 sem mudar o jeito de usar o programa, exceto a ordem das listas. As mudanças que alteram hábito (escala de cores, cabeçalho, regra de clique) ficam para depois das [perguntas](06_perguntas.md).
