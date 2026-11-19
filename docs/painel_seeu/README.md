# Painel do APTO na página do processo do SEEU (extensão 1.15)

O painel aparece à direita da página do processo no SEEU e mostra a análise do APTO **sem precisar do APTO aberto**.
O SEEU não muda: o painel só reserva a sua largura na página, não clica, não abre aba nem janela.

## Como funciona

1. **Leitura das abas, em segundo plano, na própria aba do processo.** São lidas as abas Informações Gerais, Informações
   Adicionais, Partes, Processos Criminais (e a página de cada processo criminal), Eventos e Incidentes (concedidos, não
   concedidos e pendentes). Só GET, só endereços de leitura do SEEU, um pedido por vez com intervalo, com a sessão de quem
   está logado (`extensao_seeu/painel/painel_seeu.js`).
2. **As abas viram o registro no formato do RSPE** (`rspe_seeu_abas.py`) e passam pelo **leitor do APTO sem mudança**
   (`rspe_scraper.extrair_paginas`): as mesmas derivações valem.
3. **O cálculo é o do APTO** (`rspe_motor.py`), os mesmos `.py`, rodando no navegador (Pyodide, Python 3.12).
4. **O painel** (`rspe_painel.py`) segue a ordem da ficha do assistido no APTO: pena e data-base, marcos (progressão,
   livramento, término), benefícios (indulto, comutação, prescrição, extinção, saída temporária) e os demais pontos
   (atestado, auditoria do cálculo, crimes em execução, hipóteses afastadas).

## Hierarquia

1. **Pena e marcos**, compactos: pena total, cumprida e remanescente e uma linha por marco (data-base, progressão,
   livramento, término) com a data e quanto falta. Destaque só quando o marco está **próximo** (até 60 dias) ou já foi
   **atingido** (progressão e livramento). A fração e a conta abrem no clique.
2. **Para conferir**, em cartões: o destaque do painel. Tudo o que é amarelo, inclusive a dúvida num marco (o marco
   ganha um sinal na linha).
3. **Confere**, em linhas discretas: o que está verde nos benefícios (ex.: prescrição não aparente).
4. Crimes em execução e, recolhidas, as hipóteses afastadas.

## Ficha disciplinar

- **Carregar:** botão "Carregar a ficha (PDF)" no painel, ou arrastar o PDF para ele. A ficha só é lida neste computador e
  fica só na sessão do navegador ("Retirar" tira na hora).
- **Automático:** a ficha aberta no SIAPEN nesta sessão (com a ficha automática ligada) também vale para o painel.
- **Leitura:** caracteres pelo pdf.js (posição, tamanho e fonte, como o pdfplumber: `extensao_seeu/painel/pdf_chars.mjs`)
  -> `rspe_pdf_paginas.py` -> **o mesmo leitor do APTO** (`rspe_ficha.extrair_paginas_pdf`). O texto da página sai pelas
  mesmas funções do pdfplumber (`pdfplumber.utils.text`, licença MIT, copiadas sem alteração no pacote do motor).
- **Identidade:** o motor só usa a ficha que for desta pessoa (nome e mãe, CPF, autos ou nascimento); senão o painel diz
  "Ficha disciplinar não usada". Ficha impressa há mais de 90 dias: conferir a atual.
- **Testes:** `paridade_ficha.py` (fichas sintéticas: pdf.js = pdfplumber) e `teste_ficha_painel.py` (15 casos com ficha:
  mesmo painel que o APTO com a ficha vinculada na base; outra pessoa; homônimo; ficha velha).
- **Validar com ficha real:** só há fichas sintéticas (`ferramentas/seeu_ficticio/ficha_pdf.py`); conferir com um PDF real
  do SIAPEN (nomes trocados).

## Resumo para o assistido

- Botão "Resumo para o assistido" no rodapé do painel: o texto em linguagem simples que o APTO propõe (`rspe_resumo.montar`,
  a partir da última análise), conferido no próprio painel como na janela do APTO (frase a frase, "+ frase", providências,
  verso de trabalho e estudo quando há ficha).
- **Onde é o atendimento?** (escolha obrigatória antes do PDF): **na unidade prisional** - o resumo leva o canhoto para o
  assistido pedir o próximo atendimento (com a data e a unidade); **fora da unidade** (Defensoria, fórum, telefone ou vídeo) -
  sem o canhoto.
- "Imprimir": abre o resumo numa aba do navegador e já pede a impressão (o visualizador de PDF também deixa baixar). O PDF sai
  do MESMO gerador do APTO (`rspe_relatorio.relatorio_resumo_assistido`), com o reportlab em Python puro na
  versão instalada com o APTO, o Pillow do Pyodide, as fontes e o logo do APTO; carregados só quando o resumo é pedido.
- Sem a base do APTO, os pedidos já feitos não entram sozinhos: marque nas providências.
- **Teste:** na compilação, os PDFs do resumo (com e sem canhoto) saem com os mesmos bytes no navegador e no APTO.

## Duas situações só

| Situação | Quando |
|---|---|
| ✓ **Confere** (verde) | há certeza: o dado do SEEU e o cálculo do APTO fecham, sem pendência |
| ! **Conferir** (amarelo) | dúvida no cálculo, dado que as abas não trazem, ou requisito que depende da ficha disciplinar |

Sem "agir já" e sem escala de urgência. Sem a ficha disciplinar, o que depende dela (falta grave, comportamento, trabalho)
nunca fica verde. Custodiado sem remição decidida há mais de 6 meses: conferir o atestado de trabalho ou estudo.
Nos marcos, a cor diz respeito à **data** (o requisito subjetivo aparece na conta).

## Garantias (testes)

- `teste_seeu_abas.py`: nos 144 casos simulados, as abas do SEEU fictício dão **o mesmo conteúdo do RSPE** e **o mesmo painel**.
- `ferramentas/motor_extensao/paridade_*.{py,mjs}` (na compilação): o painel calculado no **Pyodide** (navegador) é
  **idêntico** ao do **CPython** (APTO) nos 144 casos.
- `extensao_seeu_testes/teste_painel_e2e.js` (manual): Chromium com a extensão, páginas fictícias servidas por rota:
  nenhuma aba nova, só GET de leitura, mesma assinatura do Python, trocar de aba não refaz a leitura.

## Limite conhecido: o HTML real das abas

O **visual** do SEEU fictício (`ferramentas/seeu_ficticio/seeu.py`) segue as capturas oficiais
([TJSP, Informações do processo de execução criminal, 02/2026](https://www.tjsp.jus.br/Download/CapacitacaoSistemas/6.1-SEEU-MP-DPE-Info-Processo-Exec-Criminal_20.02.2026.pdf);
[TJSP, Mesa de trabalho Promotor/Defensor, 02/2026](https://www.tjsp.jus.br/Download/CapacitacaoSistemas/4.3-SEEU-MP-DPE-Mesa-Trabalho-Promotor-Defensor_20.02.2026.pdf)).
A **marcação HTML** é suposição: as capturas não mostram o código. O leitor procura pelo texto dos rótulos ("Data Base:",
"Data do Requisito Temporal:") e dos cabeçalhos das tabelas ("Tipo do Incidente", "Data de Referência"), não pela marcação,
mas só o HTML real confirma. Pontos a validar com páginas salvas do SEEU (nomes trocados):

- endereço de cada aba (o leitor usa o link da própria página: `href`, endereço no `onclick` ou o id `tabXxx`);
- página de cada processo criminal e onde ficam, por artigo, violência/grave ameaça, hediondez, reincidência e frações;
- data de nascimento (aba Partes) e "Processos Selecionados" de eventos e incidentes.

O que não for achado não vira dado: fica em branco, e o painel mostra "Não lido nas abas do SEEU" em amarelo.

## Protótipo

`python ferramentas/seeu_ficticio/prototipo.py S037 saida.html --hoje 18/10/2026` gera a página fictícia do SEEU com o painel calculado de
verdade (imagens em `v2/`).
