# Método da revisão jurídica por aba

Roteiro usado na revisão da aba Indulto (versão 7.16.2), para repetir nas abas Progressão, Livramento, Saída temporária,
Remição, Prescrição, Extinção e Auditoria. Nenhum dado real entra no repositório: bases, planilhas e scripts de trabalho
ficam fora dele (pasta de rascunho do revisor).

## 0. Proteção dos dados
- A base real é aberta só para leitura (`sqlite3` com `mode=ro`) numa pasta própria, fora do repositório.
- O programa roda numa CÓPIA da base, como em `casos_simulados/roda_casos.py`.
- Em relatório e planilha, o assistido aparece só por INICIAIS e número do processo.
- Erro achado na base real vira teste com dados FICTÍCIOS (`casos_simulados/base_casos.py`, nome "SIMULADO CASO nnn",
  processo 99xxxxx).
- Antes de cada commit: procurar no diff números de processo e nomes da base real (tem de dar zero).

## 1. Amostra
- Sorteio com semente fixa (registrar a semente). Na aba Indulto: 150 de 633 assistidos.
- Data de referência fixa, a mesma no avaliador e no programa.

## 2. Extração dos fatos (camada de leitura)
- Pode-se usar o que o programa já leu do RSPE e da ficha (`assistidos.dados`, `fichas.dados`), nunca as funções de análise.
- Conferir a leitura por coerência interna: soma das penas x pena total; tempo cumprido recalculado pelos eventos x
  "pena cumprida" do SEEU; saldo de remição x incidentes; datas impossíveis; campos truncados.
- Limite conhecido: a base não guarda o texto bruto do PDF; se a revisão precisar dele, pedir os PDFs.

## 3. Avaliador independente
- Fonte: o TEXTO OFICIAL da norma (Planalto ou publicação original do DOU), nunca o código nem o `base_juridica.json`.
- Escrever um script próprio, regra por regra, com as mesmas convenções de conta (ano 365, mês 30, dia do começo incluído,
  frações para baixo).
- Saída por assistido: resultado (cabe / depende / não / vedado / fora / já decidido), a conta, a data em que o requisito se
  cumpre e o fundamento (artigo).
- "Depende" só quando falta um dado que decide o resultado; testar os dois cenários (com e sem o dado) e só marcar "depende"
  se o resultado mudar.
- Ponto controvertido: pesquisar no JusRatio (STF, STJ, TJMS primeiro) e registrar como "tese".
- Muitos casos: poucos ajudantes, todos com o mesmo arquivo de regras comuns e as mesmas funções de conta.

## 4. Comparação
- Uma linha por assistido e regra (ou decreto); quando o programa separa resultados (ex.: indulto e comutação), comparar cada um.
- Mapear os rótulos do programa para as mesmas classes do avaliador; "os dois negam por motivos diferentes" confere quanto
  ao cabimento e é contado à parte.

## 5. Classificação (por causa, não por caso)
- Para cada divergência, reconferir primeiro o lado do avaliador.
- Tipos: (a) erro do programa; (b) erro de leitura do RSPE/ficha; (c) erro do avaliador; (d) tese discutível ou escolha de
  política.
- Corrigir o avaliador nos itens (c) e rodar de novo, até sobrarem só (a), (b) e (d).
- Classificar por regras escritas (script) e, no resto, à mão, com a causa em linguagem simples.

## 6. Correções
- (a) e (b): correção geral, nunca por caso; teste de regressão com dados fictícios em `teste_rev_<aba>_*.py`, registrado em
  `testes.py` antes da linha "# saída em UTF-8".
- (d): não se decide; vai para o relatório com as duas leituras, a jurisprudência (tribunal, órgão, relator, data, número) e a
  recomendação.
- Baterias obrigatórias, sem regressão:
  - `python3 testes.py`
  - `cd casos_simulados && APTO_SIM_DESTINO=/tmp/x.sqlite python3 roda_casos.py --vazia` (0 falhas)
  - `cd casos_simulados/cobertura && python3 falhas.py /tmp/f.json base_falhas.json` ("PASSARAM A FALHAR: nenhuma")
- Caso simulado que mudar de resultado: explicar e só aceitar se o gabarito antigo estava errado.
- Rodar de novo a comparação e informar quantas divergências sobraram.

## 7. Entregas
- Planilha (fora do repositório): comparação linha a linha, resumo por regra/decreto, resumo por causa, teses para parecer,
  conferência da leitura e legenda.
- Relatório curto em linguagem simples.
- Um branch e um PR contra main (sem merge), com VERSAO e LEIA-ME.txt atualizados.

## Lições da aba Indulto
- O programa costuma ser mais cuidadoso que um avaliador novo: antes de chamar algo de erro do programa, procurar no código o
  motivo do "a verificar" e checar a jurisprudência que ele cita.
- Pontos que pegaram o avaliador e valem para outras abas: condenação posterior à publicação não é alcançada; evento
  "BENEFICIO CONCEDIDO" interrompe o cumprimento; livramento revogado não conta; tempo anterior ao fato não cumpre a pena do
  crime; fuga é falta permanente; tráfico privilegiado não é hediondo nem impeditivo (STJ, Tema 1.336).
