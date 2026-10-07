#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
APTO - Auditoria de Prazos e Tempo de Cumprimento Organizada (SEEU)
=================
Janela nativa (pywebview) com interface em HTML (ui.html). A leitura dos PDFs
está em rspe_scraper.py, os campos exibidos em rspe_view.py e as exportações
em rspe_export.py. Bases locais (.sqlite) ficam na pasta "bases".
"""

import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from datetime import date, datetime

import webview

import rspe_scraper as rs
import rspe_view as rv
import rspe_ficha as rf
import rspe_peticao as rpet
import rspe_export as rx
import rspe_regras as rg
import rspe_decretos as rd
import rspe_relatorio as rrel
import rspe_indulto_tl as rtl

APP = "APTO"
VERSAO = "7.4.0"


def pasta_app():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def recurso(nome):
    return os.path.join(getattr(sys, "_MEIPASS", pasta_app()), nome)


PASTA_BASES = os.path.join(pasta_app(), "bases")
CONFIG = os.path.join(pasta_app(), "rspe_config.json")
VIGIA_ESTADO = os.path.join(pasta_app(), "pasta_vigiada_estado.json")
VIGIA_INTERVALO = 15  # segundos entre as varreduras da pasta vigiada
PASTAS_TIPO = {"RSPE", "RSPES", "FD", "FDS", "FICHA", "FICHAS", "FICHA DISCIPLINAR", "FICHAS DISCIPLINARES"}


def _nome_seguro(nome):
    return "".join(ch for ch in (nome or "") if ch not in '\\/:*?"<>|').strip()


def base_da_pasta(raiz, arquivo):
    """Nome da base pelo caminho do PDF dentro da pasta vigiada:
    <mãe>/<base>/... ou <mãe>/<RSPE|FD>/<base>/...  (PDF solto na pasta mãe: None)."""
    partes = os.path.relpath(arquivo, raiz).split(os.sep)[:-1]
    if partes and partes[0].strip().upper() in PASTAS_TIPO:
        partes = partes[1:]
    return _nome_seguro(partes[0]) if partes else None
BASE_PADRAO = os.path.join(PASTA_BASES, "base_padrao.sqlite")

def _ajuda_juris():
    """Lista de jurisprudência da base jurídica (editável), exibida na Legenda: tese, nível e onde o programa a aplica."""
    try:
        lst = rg.jurisprudencia() or []
    except Exception:
        lst = []
    if not lst:
        return ""
    esc = lambda t: str(t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    itens = "".join("<li><b>%s</b>%s - %s%s</li>" % (esc(j.get("tema")), (" <i>(%s)</i>" % esc(j.get("nivel"))) if j.get("nivel") else "",
                                                     esc(j.get("tese")), ("<br><span class=\"muted\">No programa: %s</span>" % esc(j.get("aplicacao"))) if j.get("aplicacao") else "")
                    for j in lst if isinstance(j, dict))
    return ("<h3>Jurisprudência da base jurídica (versão %s)</h3><p class=\"muted\">Referência das teses adotadas; editar a base altera esta lista. "
            "As regras de cálculo ficam nas demais seções da base e no programa.</p><ul>%s</ul>" % (esc(rg.versao()), itens))


AJUDA = """
<h4>Cores</h4>
Progressão e Livramento: <b>amarelo forte</b> = prazo vencido ("Vencido há N dias · sem pedido no RSPE - requerer" quando não há pedido,
exame criminológico nem falta nos 12 meses; nos demais casos, "· verificar criminológico, indeferimento ou falta"); a dica mostra os pedidos do RSPE e, quando houver, o aviso sobre o exame criminológico, que é só dica: não muda a cor nem
gera alerta). Prazos: <b>laranja</b> = vence em até 30 dias; <b>amarelo</b> = em até 60; <b>verde</b> = em até 90. Acima de 90 dias:
"Em cumprimento", sem cor. <b>Cinza</b> = "Pena cumprida" ou "Não se aplica" (Progressão: em livramento, já no aberto, não iniciou, pena
interrompida; Livramento: em livramento, não iniciou, pena interrompida - o motivo fica na ficha); <b>amarelo</b> também para "A verificar (livramento)"; <b>azul</b> = execução extinta.
Extinção: <b>vermelho</b> = extinção cabível; <b>laranja</b>/<b>amarelo</b>/<b>verde</b> = término em até 30/60/90 dias; cinza = pena
interrompida ou sem previsão; azul = extinta (registrada).
Indulto/Comutação (células): <b>vermelho</b> = "Vedado (art. 1º)", "Vedado (art. 7º)", "Indeferido" ou "Falta" (falta com sanção
reconhecida nos 12 meses); <b>verde</b> = "Sim" (possível, também quando depende de tese defensiva, indicada no texto); <b>amarelo</b> =
"Verificar" (inclusive falta a apurar e a controvérsia do art. 2º, II); <b>cinza</b> = "Não atinge", "Não se aplica" (nenhuma
condenação na publicação do decreto), "Fato posterior" ou "Prejudicada"; <b>azul</b> = "Concedido" no RSPE.
Prescrição: vermelho = aparente; amarelo = iminente (executória em até 180 dias) ou "A VERIFICAR" (saldo na evasão que depende da
imputação do cumprimento entre condenações); sem cor = não prescrita; cinza = sem dados; azul = extinta. Clique num cartão de resumo
para filtrar pela cor.
<h4>Datas e cálculos</h4>
Progressão, livramento e término são os impressos pelo SEEU no RSPE; o programa não os recalcula. Sem data no RSPE, a tabela mostra
"—" e o motivo ("Não consta no RSPE", "Pena interrompida", "Não iniciou") fica na ficha. O programa calcula indulto e comutação,
prescrição, extinção pelo cumprimento, estado da execução, falta nos 12 meses, remição a requerer (ficha x RSPE, estudo estimado) e as
conferências da Auditoria, na convenção do SEEU (ano de 365 dias, mês de 30, prazos pelo calendário).
Nos decretos, a pena cumprida é ancorada no SEEU: pena total menos os dias entre a geração do RSPE e o término impresso (sem término,
a pena cumprida impressa); para a data do decreto, desconta o cumprimento e as remições posteriores a ela ou, se o RSPE é anterior,
projeta o cumprimento que ele mostra em curso. Na prescrição, o tempo cumprido de cada crime é o dos períodos de cumprimento
posteriores ao seu termo inicial (custódia e livramento, unidos) mais as remições concedidas; a pena remanescente impressa só entra
no trecho em aberto com um só crime ativo. Dias de custódia contam o dia da prisão e o da soltura; na prescrição e no desconto entre
a data do decreto e o RSPE, a conta é pela diferença das datas. Remição: só a concedida; aceita decimal ("12,5 Dia(s)").
<h4>Falta (12 meses)</h4>
O RSPE não lista faltas formalmente. A janela é de 365 dias até a data de geração do RSPE (não até hoje). A coluna mostra "Sim"
(vermelho) só para falta com sanção reconhecida no RSPE (falta grave homologada, sanção concedida), pela data do fato; indício sem essa
sanção (fuga ou abandono só como evento, regressão cautelar, falta pendente, perda de remidos sem falta datada, dias perdidos sem data)
aparece como "A apurar" (amarelo), com o detalhe na ficha do assistido. Regressão e perda de remidos são datadas pela decisão.
Incidente negado não conta. Falta grave da ficha disciplinar ausente do RSPE entra como "A apurar" (decidir na Auditoria). "Não consta" não garante ausência de falta: conferir o PAD.
<h4>Indulto / Comutação</h4>
Art. 1º (mesmo rol nos dois decretos): hediondos/equiparados, tortura, lavagem (&gt;4 anos), ORCRIM e milícia, terrorismo, racismo,
escravidão/tráfico de pessoas, genocídio, sistema financeiro (&gt;4 anos), licitações (&gt;4 anos), crimes sexuais (215, 216-A, 217-A,
218 a 218-C), administração pública 312-319 e 333 (&gt;4 anos), ECA 239-244-B, ambientais, Estado Democrático, abuso de autoridade,
violência contra a mulher, tráfico (33 caput/§1º, 34-37, 39); crime militar só se corresponder a esses incisos (XIX - fica "a verificar").
Lesão do art. 129, § 2º ou § 3º, só é hedionda contra agente ou autoridade (Lei 8.072, art. 1º, I-A): "a verificar"; o § 12
sozinho não torna o crime hediondo. Importunação sexual (215-A) e perseguição (147-A): impeditivas só se a vítima for mulher ("a
verificar"). Violência doméstica sem sinal de que a vítima é mulher: "a verificar" no texto do indulto.
Art. 6º: falta grave com sanção reconhecida em juízo nos 12 meses antes de 25/12, pela data do fato - o benefício que seria Sim
aparece como "Falta" (vermelho); falta pendente, regressão sem falta homologada, perda de remidos sem falta datada e fuga só registrada
como evento aparecem como "Verificar". Falta depois da publicação do decreto (23/12) não impede (art. 6º, p. ú.). Condenação por
fato posterior a 25/12, ou com sentença posterior à publicação do decreto (23/12), fica fora da soma do art. 7º (STJ, AgRg no HC 441.551);
sentença anterior com trânsito para a acusação só depois fica "A VERIFICAR (art. 2º, II)", com as duas correntes - por cautela,
mesmo quando algum inciso seria possível (o "POSSÍVEL" passa a "A VERIFICAR" até se conferir o recurso da acusação).
Art. 9º, testado inciso por inciso com a situação em 25/12 de cada ano (regime, pena cumprida, remanescente, reincidência):
I, II, III (frações por faixa de pena), IV (15/20 anos ininterruptos; a remição do período conta, art. 5º) e V (20/25 anos),
VI (semiaberto ininterrupto), VII (regime aberto, PRD ou sursis, 1/6 ou 1/5),
VIII (aberto ou livramento com remanescente ≤ 6 anos, ≤ 4 se reincidente); IX "a verificar" (programa de egressos) só com aberto,
livramento, PRD ou sursis; X "a verificar" (monitoramento) só com semiaberto há 3 anos ou mais; XI (pena ≤ 12 anos em semiaberto ou
aberto com a fração cumprida): possível com 5 saídas temporárias no RSPE até a data, senão "a verificar"; XII e XIII (pena ≤ 12 anos com
a fração cumprida): "a verificar" (estudo, curso); XIV (crime patrimonial sem VGA com 3 meses cumpridos): "a verificar" (valor do bem);
XV possível (reparação dispensada, art. 12, § 2º, I). XIV e XV são aferidos crime a crime.
§ 2º, I: para maiores de 60 anos os lapsos dos incisos I a XI caem pela metade (aplicado automaticamente pela data de nascimento;
não alcança as frações do XII e do XIII nem o requisito do art. 13);
os demais grupos do § 2º, o inciso XVI (saúde), os arts. 10 e 11 (mulheres) e o art. 1º, § 1º (colaboração premiada) não são aferíveis pelo RSPE.
Com a ficha disciplinar importada, os incisos XI (5 saídas temporárias ou 12 meses de trabalho externo nos 3 anos), XII (estudo por 12 meses nos 3 anos; 18 meses nos 5 anos se reincidente, em 2024 e em 2025) e XIII (curso concluído ou certificado ENCCEJA/ENEM durante a execução e nos 3 anos anteriores a 25/12) são conferidos na ficha: atende = possível; não consta = não atendido.
Art. 13 (comutação): 1/5 do remanescente (ou do cumprido, se maior) para quem cumpriu 1/5 (primário) ou 1/4 (reincidente);
2/3 para os grupos do § 2º; não cumula com indulto (§ 5º: "Prejudicada"); com comutação anterior concedida, dispensa novo requisito
temporal (§ 2º). Sem cumprimento em curso na data (não iniciado ou interrompido), indulto e comutação de 2024 e 2025 "não se aplicam"
(célula "Não atinge"), salvo o inciso XV, que não exige fração e fica "a verificar". A análise completa está na ficha, em "Análise
inciso por inciso". O programa não usa a expressão "indulto parcial", sinônimo de comutação na jurisprudência (STF, HC 81.567 e HC
96.431; STJ, REsp 753.646): no concurso com crime impeditivo, fala em "indulto dos crimes não impeditivos (art. 7º, p. ú.)", analisado
depois de 2/3 da pena do impeditivo.
Livramento incerto (o SEEU imprime o livramento como vigente, mas há regressão, prisão ou interrupção posterior): no indulto e na
comutação de 2024 e 2025, o que seria possível passa a "A VERIFICAR" com a ressalva "livramento a confirmar". Dar baixa no alerta da Auditoria confirma o livramento em todas as abas.
<b>Decreto 11.302/2022</b> (referência 25/12/2022) tem lógica própria: art. 5º alcança o crime cuja <b>pena máxima em abstrato</b>
não supere 5 anos (em concurso, cada crime é avaliado isoladamente - parágrafo único), sem exigir fração cumprida nem regime; havendo crime excluído pelo art. 7º em concurso, o crime não impeditivo só é indultado depois de cumprida a pena do impeditivo (art. 11, p. ú.; STJ, 3ª Seção, AgRg no HC 890.929/SE) - o programa compara a soma das penas impeditivas com a pena cumprida em 25/12/2022;
art. 4º, maiores de 70 anos com 1/3 cumprido (as vedações do art. 7º, III, b e d, e V não se aplicam a ele - art. 7º, § 2º; com outro crime excluído, 1/3 dos demais depois de cumprida a pena do excluído - art. 11, p. ú.); art. 1º, saúde (laudo); art. 7º exclui hediondos, violência/grave ameaça e violência
doméstica, tortura, lavagem, ORCRIM, terrorismo, crimes sexuais (215 a 218-C), 312/316/317/333, tráfico (33 caput e § 1º, 34, 36 -
exceto o § 4º) e ECA 240-244-B; art. 9º dispensa o trânsito em julgado. A pena máxima é lida do tipo penal impresso no RSPE; quando o
SEEU corta o texto, usa-se a tabela editável "pena_maxima_abstrata" da base jurídica (indicado na análise). O trecho relativo a
agentes de segurança e militares (arts. 2º, 3º e 6º) não é avaliado; o art. 8º exclui PRD, multa e suspensão condicional do processo (pena marcada
"CONVERTIDA" fica "a verificar"); crime militar, "a verificar" (art. 7º, VII). O Decreto 11.846/2023 não é analisado.
<b>Hediondez pela época do fato</b>: a tabela "hediondos.desde" da base jurídica guarda a data em que cada tipo passou a ser
hediondo (Lei 8.072/90 e alterações - 8.930/94, 9.695/98, 12.015/2009, 13.104 e 13.142/2015, 13.497/2017,
12.978/2014, 13.964/2019, 14.811 e 14.994/2024, 15.134 e 15.159/2025, 15.358, 15.384 e 15.487/2026). Fato anterior à data não é
tratado como hediondo (CF, art. 5º, XL) nas frações e no livramento, e a Auditoria alerta quando o SEEU rotulou como hediondo um
fato anterior à lei. No art. 1º dos decretos de indulto, a hediondez é aferida na data de cada decreto (STJ); a tese da
irretroatividade (STF, 2ª Turma) aparece como "tese hed. superv.", com a corrente contrária (STF, 1ª Turma) no texto.
<h4>Prescrição (arts. 109 a 119 do CP), crime a crime</h4>
<b>Quadro da executória</b>: ao abrir o cálculo, só quatro linhas - resultado, período que decide (fuga, soltura sem fuga, sem
início do cumprimento ou em cumprimento), saldo remanescente (com a origem; sem fuga é informativo, pois o prazo segue a pena aplicada)
e prazo com o vencimento. "Ver cálculo completo e linha do tempo" abre o quadro das fugas, a memória de cálculo e a linha do tempo. <b>Saldo na fuga</b>: quando a fuga
alcança o menor prazo do art. 109 e o saldo não foi informado nem confirmado pelo SEEU, o programa calcula o saldo crítico (até quanto
de saldo a fuga já teria prescrito) e pede a pena remanescente na data da fuga ("A VERIFICAR: informe a pena remanescente"); o campo
dessa fuga vem destacado em "informar saldo". Com prescrição aparente pelo saldo calculado, pede a confirmação antes de requerer.
<b>Pretensão punitiva (retroativa e intercorrente, art. 110, § 1º)</b>: prazo pela pena aplicada (art. 109), metade se menor de 21 anos
no fato ou maior de 70 na sentença (art. 115; salvo violência sexual contra a mulher, com aviso); intervalos fato→denúncia (só para
fatos até 05/05/2010; Lei 12.234/2010, DOU e vigência em 06/05/2010), denúncia→sentença e sentença→trânsito final (a intercorrente vai
até o trânsito para a defesa). O acórdão condenatório também interrompe (art. 117, IV; STF HC 176.473), assim como a pronúncia e sua
confirmação nos crimes do júri (art. 117, II e III; Súmula 191); essas datas não constam do RSPE: conferir antes de pedir. Pena menor
que 1 ano por fato anterior a 06/05/2010: prazo de 2 anos (art. 109, VI, na redação anterior à Lei 12.234/2010). Crime continuado e
concurso formal: o prazo se calcula sem o acréscimo (STF, Súmula 497; art. 119) - a memória avisa.
<b>Pretensão executória (art. 110, caput)</b>: prazo pela pena aplicada, +1/3 se reincidente, metade pelo art. 115. Termo inicial no
trânsito em julgado para ambas as partes (STF, Tema 788) ou, se o trânsito para a acusação é anterior a 12/11/2020, nessa data
(art. 112, I, com a modulação do Tema). Cada período dos eventos do RSPE é classificado em relação ao crime: custódia anterior ao
termo inicial = prisão provisória (detração, CP, art. 42), só informativa - não reduz a pena nem o prazo (STJ, AgRg no HC 967.565;
RHC 67.403); custódia a partir do termo = cumprimento da pena unificada (LEP, art. 111), que interrompe (art. 117, V) - inclusive o
flagrante ou a preventiva cujo campo "Processos" inclui o processo do crime (também no formato curto do SEEU) ou não indica processo;
prisão provisória registrada só para outro processo e iniciada depois do termo = prisão por outro motivo: suspende (art. 116, p.
único) e não conta como cumprimento (se foi convertida em cumprimento, o efeito é de interrupção - a conferir). Livramento
condicional concedido conta como cumprimento. Intervalo sem custódia depois do termo começado por fuga, evasão, abandono ou
revogação do livramento é evasão: o prazo corre pelo saldo da pena (art. 113); motivo não informado: também, com aviso; soltura sem
culpa (liberdade provisória, relaxamento, habeas corpus, alvará) ou sem início do cumprimento: prazo pela pena aplicada (STJ, RHC
67.403).
<b>Saldo na evasão</b>: com uma só condenação, pena menos o cumprido desde o termo (ou a pena remanescente do RSPE no trecho em
aberto). Com várias condenações unificadas, o RSPE não informa como o tempo cumprido foi imputado entre elas: o programa calcula
dois limites - saldo mínimo (este crime imputado primeiro) e saldo máximo (este crime imputado por último, depois das outras
condenações com trânsito anterior à evasão) - e mostra, como referência, a hipótese do art. 76 do CP (mais grave primeiro; STJ, RHC
9.158) e a da ordem cronológica do trânsito (STJ, AgRg no REsp 1.858.048). O prazo (art. 109 sobre o saldo, +1/3, metade) é testado em cada
faixa do art. 109 atravessada pelos dois limites e a data-limite soma os dias de suspensão. Todas as faixas prescrevem:
"Prescrição executória aparente" (data mais tardia); nenhuma: "Não prescrita"; divergem: "A VERIFICAR: saldo na evasão depende da
imputação do cumprimento entre as condenações unificadas" (amarelo), com a lista do que falta (cálculo do SEEU com o saldo por
condenação, ordem de imputação, prisões por outro processo). Recaptura ou reinício interrompe (art. 117, V); cada crime prescreve
isoladamente pelo seu saldo (art. 119; STJ, AgRg no REsp 2.256.555, RHC 35.425, HC 261.866). Nunca se usa "tempo total preso
igual ou maior que a pena do crime": a mesma prisão serve a várias condenações. Custódia provisória anterior ao trânsito igual ou
maior que a pena do processo não é resultado de prescrição: vira aviso na memória e hipótese "a verificar" na aba Extinção.
A "memória de cálculo" de cada crime mostra, nesta ordem: pena aplicada; termo inicial; prazo pela pena aplicada; prisão provisória
(informativa); cada período (cumprimento, prisão por outro motivo, evasão com cumprido, saldo, prazo, vencimento e recaptura,
liberdade sem evasão); conclusão.
Na linha de cada crime da aba Prescrição, "cálculo" abre a memória em texto e "editar dados" o formulário de ajuste; a
pretensão executória não tem linha do tempo (nem na tela nem no relatório individual).
<h4>Filtro de situação</h4>
O seletor ao lado dos botões filtra a aba (a Geral não tem). Progressão e Livramento: vencidas, vence em até 30, 60 ou 90 dias, não
iniciou, pena interrompida, não se aplica (cumprida / livramento / aberto), sem data. Indulto/Comutação: por benefício e resultado
("Indulto 2024 · Sim", "Comutação 2025 · Verificar" etc.), fato posterior à data do decreto, falta nos 12 meses e crime impeditivo.
Prescrição: aparente, iminente / a verificar, não prescrita / não configurada, sem dados, extinta. Extinção: extinção cabível,
término em até 30, 60 ou 90 dias, pena interrompida, sem previsão. Ficha disciplinar: remição a requerer, conferir remição / sem atestado
/ estudo, em ordem, sem ficha. Auditoria: com alertas, pontos a verificar, sem inconsistências. O número da execução é copiado com um clique.
<h4>Jurisprudências</h4>
Acórdãos do TJMS em execução penal favoráveis à defesa (recurso defensivo provido, recurso do MP desprovido, ordem concedida), triados
pela ementa, com a tese em uma frase e o tema. Pesquise por palavras (todas devem constar da tese ou da ementa) e filtre por tema.
"Copiar ementa" leva a ementa com a referência (tribunal, classe, número, relator, órgão, julgamento). Um teses_execucao.json ao lado
do programa substitui a cópia embutida. STJ e STF entrarão depois.
<h4>Indulto: todos os decretos</h4>
A barra lateral traz "Geral" e os decretos de 2025 a 2000. Em "Geral", cada linha mostra o mapa dos decretos desde o início do
cumprimento informado no RSPE (verde cabe, cinza não cabe, vermelho impeditivo, azul concedido, roxo indeferido); clique no nome
para ver o encaixe em cada decreto. Clicando num decreto, setas passam de um a outro e os chips filtram. Concedidos e indeferidos
vêm dos incidentes do RSPE. Só entram hipóteses que se resolvem pela conta (frações, pena, regime, reincidência, violência, falta);
as que dependem de dado fora do RSPE (filhos, doença, idade, estudo, PRD/sursis) não são calculadas. "Verificar indulto/comutação"
tem, no topo, o seletor dos decretos do assistido; todos abrem a linha do tempo completa. Nos decretos de 2000 a 2023 a
hediondez é aferida na data do fato.
<h4>Fixados e Quadro do Usuário</h4>
O alfinete ao lado do nome prende o assistido no topo de todas as abas; Ctrl+K ou "/" vai à busca. O Quadro do Usuário é um quadro
de cartões (estilo Trello): envie um assistido pelo botão da linha, escreva observações, prazo e etiquetas e arraste entre colunas.
<h4>Histórico de RSPE (aba Geral)</h4>
Cada RSPE importado fica guardado na base. O botão "Histórico · N", na linha do assistido, abre uma tabela com uma coluna por
RSPE (do mais antigo ao atual): regime, penas, dias remidos e perdidos, data-base, previsões de progressão e livramento, término,
faltas graves, incidentes novos e os pedidos marcados com o retorno (o incidente decidido depois do pedido). O que mudou em relação
ao RSPE anterior fica em destaque. Importar um PDF mais antigo o acrescenta ao histórico sem substituir o atual.
<h4>RSPE desatualizado e cópias de segurança</h4>
RSPE emitido há mais de 60 dias ganha um "!" laranja ao lado do nome (passe o mouse para ver a data e os dias); o chip "RSPE antigo" da faixa de resumo
filtra esses assistidos. Ao abrir a base, o programa faz uma cópia de segurança (pasta "copias", ao lado da base) e guarda as
10 últimas; o menu da base &gt; "Cópias de segurança…" mostra as cópias e restaura uma delas (a versão de agora também é copiada antes).
O botão "Letra" (A pequeno / A grande) muda o tamanho de tudo na tela e fica gravado neste computador.
<h4>Pasta vigiada</h4>
Menu da base &gt; "Pasta vigiada…": escolha uma pasta mãe com uma subpasta por base (ex.: "2ª VEP", "1ª VEP", ou RSPE\\2ª VEP e
FD\\2ª VEP). Os PDFs salvos numa subpasta entram sozinhos na base de mesmo nome, com o programa aberto; a base é criada se não
existir. PDF solto na pasta mãe é ignorado; nada é apagado ou movido.
<h4>Ficha disciplinar (SIAPEN/AGEPEN)</h4>
Importe o PDF da Ficha Disciplinar pelo mesmo botão "Importar PDFs": o programa reconhece o documento e o vincula ao RSPE pelos autos
citados na ficha. Sem esse vínculo, a ficha fica guardada pelo nome e vale para o assistido de mesmo nome só se houver um único na base
(com homônimos, não é ligada a ninguém). Extrai conduta, períodos de trabalho (setor/empresa), atestados de trabalho com dias
trabalhados e remidos, estudo, faltas disciplinares (registro, PADIC, arquivamento/homologação), regressão/restabelecimento, isolamento e
recusa de trabalho. A análise da ficha é de remição: a aba <b>Ficha disciplinar</b> agrupa por atestado (dias trabalhados e remidos,
como constam nele, e os empregos que ele cobre); depois vêm os períodos sem atestado na ficha (procurar nos autos ou pedir à unidade),
a baixa de trabalho sem início registrado, o estudo e o que você adicionou ("+ Adicionar atestado": ENCCEJA/ENEM, trabalho fora da
ficha). O círculo à direita marca o atestado ou o período como conferido (fica gravado na base). A remição do trabalho vem dos dias
trabalhados do atestado; a coluna "Dias" mostra os dias corridos do período, só como referência. O estudo sem carga declarada é
estimado em 4 h por dia útil (1 dia remido a cada 12 h); início ou fim ilegível = "Conferir datas". O RSPE não diz de onde vem cada
remição (trabalho, estudo, ENCCEJA/ENEM, leitura), então o programa não liga remição a atestado: aponta "Requerer remição" só quando não
há nenhuma remição lançada no RSPE depois do atestado (ou depois do período de estudo); os demais ficam "conferir a homologação", com as
somas e a lista das remições do RSPE no cabeçalho. Trabalho anterior à 1ª prisão do RSPE fica só no resumo. As faltas da ficha não
entram na coluna Falta nem no indulto; na Auditoria, só no ponto "Perda de remidos pode alcançar remição anterior à falta" (desconto
em duplicidade, LEP, art. 127).
<h4>Regras de leitura</h4>
Quem não tem início de cumprimento definitivo no RSPE (só prisão provisória encerrada, ou nenhuma) aparece como "Não iniciou o
cumprimento", e não como regime aberto ou pena interrompida. Livramento suspenso ou revogado em incidente posterior aparece como tal.
A Auditoria confere a matemática e as marcações do RSPE (frações, soma das penas, data-base, perda de dias remidos, reincidência,
marcações de hediondez e violência, livramento incerto) e mantém os avisos que nenhuma outra aba mostra: idade (LEP, art. 117, I; § 2º
dos decretos), multa cominada, reparação do dano no crime patrimonial sem VGA e progressão especial da mulher (1/8). Remição da ficha,
indulto, comutação, prescrição e prazos vencidos ficam nas próprias abas.
O programa não presume datas. Sem data do fato, recebimento da denúncia, sentença ou trânsito em julgado no RSPE, a prescrição
daquele trecho não é calculada e a Auditoria aponta "verificar na ação penal". Quando a 1ª página do RSPE diz "Em livramento
condicional deferido em ...", o assistido é tratado como em livramento, ainda que o "Regime Atual" traga o regime anterior, salvo se
houver regressão (inclusive cautelar), suspensão ou revogação posterior: aí vale o regime do RSPE e a Auditoria pede a conferência do
desfecho. Sem artigo no RSPE ("Não informado"), o crime é reconhecido pela descrição do tipo (ex.: "conjunção carnal ... com menor de
14 anos" = art. 217-A do CP), conforme a lei da data do fato: antes da Lei 12.015/2009 (10/08/2009), arts. 213/214 c/c 224, a; o art.
214 posterior a ela vira art. 213; tipos criados depois do fato (215-A, 24-A da Lei Maria da Penha) são apontados na Auditoria. Fuga: a
data-base vai para a recaptura (falta permanente), mas a Auditoria pede a homologação da falta; falta grave não move a data-base do
livramento, do indulto nem da comutação (Súmulas 441 e 535 do STJ). A data-base é conferida com a última prisão, progressão/regressão
ou falta grave homologada; sem esse evento no RSPE, a Auditoria aponta a inconsistência (e, se coincidir com a soma/unificação das
penas, o Tema 1006 do STJ).
<h4>Telas e cópia para a petição</h4>
Nas abas Geral, Progressão, Livramento, Indulto/Comutação e Extinção, o clique na linha abre a ficha do assistido; em Prescrição, Ficha
disciplinar e Auditoria, expande a linha, e a ficha abre por "Abrir ficha completa". A ficha do assistido mostra pena, benefícios,
falta, pontos de atenção, crimes, a ficha disciplinar (conduta, remição atestada x homologada, o que requerer, o detalhe da falta -
"Sim" ou "A apurar" -, trabalho, atestados e faltas) e os cálculos do programa.
Na Prescrição, o seletor ao lado do filtro escolhe a pretensão (executória ou punitiva): a tela mostra uma de cada vez, com os
crimes de prescrição aparente, iminente ou com datas a verificar, agrupados por ação penal.
As tabelas mostram só o essencial: data do SEEU ou "—"; indulto e comutação como Concedido, Sim, Verificar, Falta, Vedado (art. 1º),
Vedado (art. 7º), Indeferido, Prejudicada, Fato posterior, Não se aplica ou Não atinge; prescrição como Aparente, Iminente, A verificar,
Não prescrita (executória) / Não configurada (punitiva), Sem dados ou Extinta. O motivo e o cálculo ficam na ficha do
assistido. Condenação por fato posterior à data do decreto na mesma execução: o decreto não alcança essa pena, que segue em execução,
mas ela não impede o indulto nem a comutação das penas anteriores (art. 7º; art. 6º, p. ú.; STJ, HC 190.963). A análise usa só os
crimes anteriores e a ficha traz a nota; "Fato posterior" só aparece quando não resta crime anterior.
Para levar ao Word: "Copiar resumo" (ficha do assistido), "Copiar pretensão punitiva" e "Copiar pretensão executória" (prescrição), "Copiar cálculo" (indulto e comutação), "Copiar" e
"Copiar pendências" (Auditoria). O texto vai em linhas simples, pronto para colar.
<h4>Relatórios em PDF</h4>
O botão <b>Relatórios</b> gera, numa pasta com a data e a hora: um PDF por assistido (bloco da pena, tabela de benefícios com
etiquetas e observação, condenações, linha do tempo em eventos e incidentes, remição, um bloco por alerta em frases curtas com o
fundamento em lista e, para os crimes com evasão, prescrição aparente ou a verificar, a figura da linha do tempo da prescrição
executória com o cartão de saldo de cada fuga, as hipóteses de imputação e o resultado), o relatório geral da base (perfil, benefícios, remição, alertas e fila de prioridade, com a prescrição
punitiva e a executória em linhas separadas) e a planilha. No próprio botão dá para escolher de quem sai o relatório individual, na
lista com busca e "Todos"/"Nenhum". Vale para os assistidos visíveis pela busca (o filtro de situação e os cartões não restringem).
Na ficha do assistido, "Relatório em PDF" gera só o dele. A exportação Excel/PDF segue a mesma regra.
<h4>Presunção de hipossuficiência (Defensoria)</h4>
No indulto, a <b>multa</b> é indultável e não é óbice (Decretos 12.338/2024 e 12.790/2025, art. 12, § 2º, I - presunção expressa
de incapacidade econômica para quem é assistido pela Defensoria). Na extinção da punibilidade, a multa pendente não obsta ante a
alegada hipossuficiência, salvo decisão que indique concretamente a capacidade de pagamento (STJ Tema 931, rev. 28/02/2024); parte da
jurisprudência, invocando a ADI 7.032 ("salvo comprovada impossibilidade"), exige prova (STJ, REsp 2.055.935): instruir o pedido por cautela. A <b>reparação do dano</b> é dispensada no inciso XV do art. 9º (crime patrimonial sem VGA); no livramento (CP, art. 83,
IV, "salvo efetiva impossibilidade"), a impossibilidade deve ser demonstrada (STJ, AgRg no HC 799.167).
O tráfico privilegiado (art. 33, § 4º) não é hediondo nem impeditivo de indulto (STF, SV 63 e Tema 1400; STJ Tema 1336).
<h4>Petições a partir de modelos .docx</h4>
Recurso desativado nesta versão (foco na exatidão dos cálculos). Os modelos e o cadastro de defensores permanecem no programa
para reativação futura.
<h4>Auditoria</h4>
Cada alerta ou ponto a verificar traz o campo <b>Fundamentação</b>: até três parágrafos para a impugnação do cálculo (o erro, o correto com
o fundamento e o pedido), só nos pontos favoráveis ao assistido. "Copiar todas as fundamentações" junta as dos pontos pendentes.
Confronta o RSPE com a base jurídica (arquivo base_juridica.json, editável e versionado): soma das penas, cumprida + remanescente,
remições, hediondez pelo rol da Lei 8.072/90 (e art. 112, § 5º, LEP para o tráfico privilegiado), marcação de VGA pelo tipo,
percentual de progressão pela lei da data do fato (1/6 para crimes comuns até 22/01/2020 e para hediondos até 28/03/2007 - STJ Súmula 471;
2/5 ou 3/5 para hediondos de 29/03/2007 a 22/01/2020 - Lei 11.464/2007; Lei 13.964/2019 de 23/01/2020 a 24/03/2026, com o VI-A
(feminicídio, 55%) de 10/10/2024 a 24/03/2026; Lei 15.358/2026 a partir de 25/03/2026 para hediondos, feminicídio, milícia e comando de
organização criminosa; Lei 15.402/2026 a partir de 08/05/2026), com retroatividade só do mais benéfico (STJ Temas
1084, 1196 e 1354; STF Tema 1169), fração de livramento (CP, art. 83; Lei 11.343, art. 44), reincidência sem condenação anterior
no RSPE (CP, art. 63) e reincidência específica (art. 83, V), data-base e regressões (LEP, art. 112, § 6º), livramento incerto, idade
(LEP, art. 117, I; § 2º dos decretos), multa, reparação do dano, progressão especial da mulher (1/8) e, para o reincidente em crime
com violência ou grave ameaça, o percentual por analogia (25%) se a condenação anterior não teve violência (informativo). Os pontos que outras abas já
mostram (prazos vencidos sem decisão, prescrição, indulto/comutação possível sem incidente, hediondez posterior ao fato, violência
doméstica a confirmar, não iniciou, interrompida, trânsito não informado, detração) são gerados, mas ficam fora da aba e da contagem.
Os pontos têm quatro níveis: <b>Alerta</b> (divergência com efeito concreto para o apenado), <b>Verificar</b> (depende de dado que o RSPE
não traz, mas pode ter efeito), <b>Info</b> (registro sem efeito prático - fica oculto por padrão; "ver conferências OK / informativas")
e <b>OK</b>. "Com alertas" = há ao menos um alerta; "pontos a verificar" = dependem de dado que o RSPE não traz. Nada é afirmado como
erro: cada item traz o fundamento para conferência.
<b>Dar baixa</b>: cada ponto pode ser baixado (com o motivo, obrigatório) quando já foi tratado ou não se aplica; ele sai da linha
e da contagem (sem pendências, a linha mostra "Guia em ordem") e fica no <b>Histórico de alertas</b> do assistido, com a data e o motivo,
de onde pode ser reaberto. A baixa é por processo, pelo tipo do ponto e pelo crime (ou ano do decreto,
ou falta) a que ele se refere: sobrevive à reimportação do RSPE e continua valendo quando o título muda (números, datas ou
agrupamento de crimes). Baixas gravadas em versões anteriores passam sozinhas para a chave nova na primeira abertura. Os avisos
"Ficha disciplinar ignorada" e "Falha ao analisar" contam como alerta e também podem ser baixados.
<h4>Extinção</h4>
Só a extinção pelo cumprimento: pena integralmente cumprida ou término previsto já alcançado (LEP, arts. 66, II, e 109); livramento
condicional com período de prova expirado sem revogação (CP, art. 90; LEP, art. 146; Súmula 617/STJ - observado o art. 89); detração que iguala ou supera a pena do
processo, como hipótese "a verificar" (a mesma prisão pode servir a várias condenações - CP, art. 42; LEP, arts. 66, II, e 111).
Prescrição e indulto ficam nas próprias abas; o livramento incerto não gera hipótese (fica na Auditoria). Situação: "Extinção
cabível" (vermelho), "Término em N dias" (laranja até 30, amarelo até 60, verde até 90), "Em cumprimento" (acima de 90 dias), "Pena
extinta (registrada)" (azul), "Não se aplica" (cinza: pena interrompida ou sem previsão).
<h4>Base jurídica</h4>
O arquivo base_juridica.json ao lado do programa tem prioridade sobre a cópia embutida. Para atualizar (novo decreto, nova fração,
nova tese), edite o arquivo e use "Base ▾ → Recarregar base jurídica". A versão em uso aparece na aba Auditoria.
<h4>Crimes</h4>
Resumidos pelo artigo: "art. 33 Lei 11.343/06 (x2)". "n/i" = artigo não informado pelo SEEU. A ficha traz a descrição completa.
"""


# --------------------------------------------------------------------------- #
# banco local
# --------------------------------------------------------------------------- #

_mesma_mae = rf.mesma_mae


def _so_digitos(x):
    return re.sub(r"\D", "", x or "")


def _ficha_prova(f, r):
    """A ficha é desta pessoa por dado objetivo: mesmo CPF, autos da ficha com o número desta execução (ou de uma ação penal
    dela) ou mesma data de nascimento com nome parecido."""
    cpf_f, cpf_r = _so_digitos(f.get("cpf")), _so_digitos(r.get("cpf"))
    if len(cpf_f) == 11 and cpf_f == cpf_r:
        return True
    autos = {_so_digitos(a) for a in f.get("autos") or []} - {""}
    procs = {_so_digitos(r.get("processo_execucao"))} | {_so_digitos(c.get("processo_criminal")) for c in r.get("_crimes") or []}
    if autos & (procs - {""}):
        return True
    import difflib
    return bool(f.get("data_nascimento") and f.get("data_nascimento") == r.get("data_nascimento")
                and difflib.SequenceMatcher(None, _norm(f.get("nome")), _norm(r.get("nome"))).ratio() >= 0.9)


def _ficha_alternativa(fichas, r):
    """Ficha guardada pelo nome que não casou pela grafia exata (Fretez/Fretes, Cezar/Cesar, Sousa/Souza) ou que ficou de fora por
    homônimo: vale só com prova objetiva (CPF, autos ou nascimento - _ficha_prova) e nome parecido; havendo mais de uma, a mais
    recente."""
    import difflib
    nn = _norm(r.get("nome"))
    if not nn:
        return None
    cand = []
    for k, f in fichas.items():
        if not k.startswith("nome:") or not isinstance(f, dict):
            continue
        nf = _norm(f.get("nome") or k[5:])
        if nf[:1] != nn[:1]:
            continue
        mesmo_cpf = len(_so_digitos(f.get("cpf"))) == 11 and _so_digitos(f.get("cpf")) == _so_digitos(r.get("cpf"))
        if (mesmo_cpf or difflib.SequenceMatcher(None, nf, nn).ratio() >= 0.85) and _ficha_prova(f, r):
            cand.append(f)
    return max(cand, key=lambda f: rs.to_date(f.get("data_impressao") or "") or date.min) if cand else None


def _fichas_candidatas(fichas, r):
    """Fichas guardadas pelo nome, de nome igual ou parecido, que não vincularam por falta de prova (CPF, autos ou nascimento):
    vão para a Auditoria, com os dados lado a lado, para o operador vincular se for a mesma pessoa."""
    import difflib
    nn = _norm(r.get("nome"))
    out = []
    for k, f in fichas.items():
        if not k.startswith("nome:") or k.startswith("nome:~") or not isinstance(f, dict):
            continue
        nf = _norm(f.get("nome") or k[5:])
        cf, cr = _so_digitos(f.get("cpf")), _so_digitos(r.get("cpf"))
        if (len(cf) == 11 and len(cr) == 11 and cf != cr) or (f.get("data_nascimento") and r.get("data_nascimento")
                                                              and f["data_nascimento"] != r["data_nascimento"]):
            continue  # CPF ou nascimento diferentes: é de outra pessoa, não há dúvida a resolver
        if nf[:1] == nn[:1] and difflib.SequenceMatcher(None, nf, nn).ratio() >= 0.85:
            out.append({"chave": k, "nome": f.get("nome") or "", "cpf": f.get("cpf") or "", "nasc": f.get("data_nascimento") or "",
                        "mae": f.get("nome_mae") or "", "impressa": f.get("data_impressao") or ""})
    return out[:3]


def _norm(txt):
    import unicodedata
    t = unicodedata.normalize("NFKD", txt or "").encode("ascii", "ignore").decode()
    return " ".join(t.upper().split())


def fmt_(d):
    return d.strftime("%d/%m/%Y") if d else ""


class Base:
    _serializable = False   # impede o pywebview de percorrer este objeto ao expor a Api

    def __init__(self, caminho):
        os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
        self.caminho = caminho
        self.con = sqlite3.connect(caminho, check_same_thread=False)
        self.lock = threading.Lock()
        self.con.execute("""CREATE TABLE IF NOT EXISTS assistidos (
            processo TEXT PRIMARY KEY, nome TEXT, data_geracao TEXT,
            arquivo TEXT, importado_em TEXT, dados TEXT)""")
        self.con.execute("""CREATE TABLE IF NOT EXISTS baixas (
            processo TEXT, chave TEXT, titulo TEXT, obs TEXT, data TEXT, PRIMARY KEY (processo, chave))""")
        # histórico das baixas e reaberturas de alertas da Auditoria (com o motivo), para consulta posterior
        self.con.execute("""CREATE TABLE IF NOT EXISTS baixas_hist (
            id INTEGER PRIMARY KEY AUTOINCREMENT, processo TEXT, chave TEXT, titulo TEXT, obs TEXT, data TEXT, acao TEXT)""")
        if not self.con.execute("SELECT 1 FROM baixas_hist LIMIT 1").fetchone():
            self.con.execute("""INSERT INTO baixas_hist (processo, chave, titulo, obs, data, acao)
                                SELECT processo, chave, titulo, obs, data, 'baixa' FROM baixas WHERE titulo != 'conferido (ficha disciplinar)'""")
        self.con.execute("""CREATE TABLE IF NOT EXISTS atestados_manuais (
            processo TEXT, id TEXT, dados TEXT, data TEXT, PRIMARY KEY (processo, id))""")
        self.con.execute("""CREATE TABLE IF NOT EXISTS fichas (
            chave TEXT PRIMARY KEY, processo TEXT, nome_norm TEXT, data_impressao TEXT, importado_em TEXT, dados TEXT)""")
        # ajustes manuais da tabela de prescrição executória (padrão SEEU): por processo e linha (ação penal + crime)
        self.con.execute("""CREATE TABLE IF NOT EXISTS presc_ajustes (
            processo TEXT, chave TEXT, dados TEXT, data TEXT, PRIMARY KEY (processo, chave))""")
        # dados objetivos que o RSPE não trouxe, informados pelo operador pela Auditoria (data de nascimento, pena máxima)
        # controle de pedidos: por assistido e aba (progressão, livramento, indulto, prescrição, extinção, remição)
        self.con.execute("""CREATE TABLE IF NOT EXISTS pedidos (
            processo TEXT, aba TEXT, data TEXT, obs TEXT, ref TEXT, registrado TEXT, PRIMARY KEY (processo, aba))""")
        try:
            # tipo de providência (pedido nos autos, ofício à unidade prisional, outra): coluna nova da 6.16.16
            self.con.execute("ALTER TABLE pedidos ADD COLUMN tipo TEXT")
        except sqlite3.OperationalError:
            pass
        self.con.execute("""CREATE TABLE IF NOT EXISTS dados_manuais (
            processo TEXT, campo TEXT, valor TEXT, data TEXT, PRIMARY KEY (processo, campo))""")
        # histórico: cada RSPE importado fica guardado (o atual também está em assistidos); a base antiga entra com o que tem
        self.con.execute("""CREATE TABLE IF NOT EXISTS rspe_historico (
            processo TEXT, data_geracao TEXT, arquivo TEXT, importado_em TEXT, dados TEXT, PRIMARY KEY (processo, data_geracao))""")
        self.con.execute("""INSERT OR IGNORE INTO rspe_historico SELECT processo, data_geracao, arquivo, importado_em, dados FROM assistidos""")
        # assistidos fixados (ficam no topo de todas as abas) e o Quadro do Usuário (cartões no estilo Trello)
        self.con.execute("CREATE TABLE IF NOT EXISTS fixados (processo TEXT PRIMARY KEY, data TEXT)")
        self.con.execute("""CREATE TABLE IF NOT EXISTS quadro_colunas (id TEXT PRIMARY KEY, nome TEXT, ordem REAL)""")
        self.con.execute("""CREATE TABLE IF NOT EXISTS quadro_cartoes (id TEXT PRIMARY KEY, coluna TEXT, ordem REAL, processo TEXT,
            titulo TEXT, obs TEXT, prazo TEXT, etiqueta TEXT, criado TEXT, atualizado TEXT)""")
        if "arquivado" not in [r[1] for r in self.con.execute("PRAGMA table_info(quadro_cartoes)").fetchall()]:
            self.con.execute("ALTER TABLE quadro_cartoes ADD COLUMN arquivado TEXT DEFAULT ''")  # data do arquivamento ('' = no quadro)
        if "aba" not in [r[1] for r in self.con.execute("PRAGMA table_info(quadro_cartoes)").fetchall()]:
            self.con.execute("ALTER TABLE quadro_cartoes ADD COLUMN aba TEXT DEFAULT ''")  # benefício do cartão (prog, liv, ind...)
        if not self.con.execute("SELECT 1 FROM quadro_colunas").fetchone():
            for i, (cid, nome) in enumerate((("fazer", "A fazer"), ("andamento", "Em andamento"), ("aguardando", "Aguardando decisão"), ("concluido", "Concluído"))):
                self.con.execute("INSERT INTO quadro_colunas VALUES (?,?,?)", (cid, nome, i))
        self.con.commit()

    def gravar_ficha(self, f, processo, mesma_pessoa=False):
        """Grava a ficha; não substitui ficha impressa depois (devolve False nesse caso). A comparação vale também
        contra a ficha guardada pelo nome (antes de o RSPE existir); ao vincular a ficha ao processo, a linha pelo
        nome da mesma pessoa sai, para não ficar órfã."""
        nn = _norm(f.get("nome", ""))
        chave = processo or ("nome:" + nn)
        with self.lock:
            chaves = [chave]
            if processo and nn:
                # a ficha guardada pelo nome só conta se for da mesma pessoa: sem autos, ou com este processo nos autos
                row = self.con.execute("SELECT dados FROM fichas WHERE chave=?", ("nome:" + nn,)).fetchone()
                try:
                    autos = (json.loads(row[0]) or {}).get("autos") or [] if row else None
                except Exception:
                    autos = []
                # sem homônimo na base, a ficha guardada pelo nome é da mesma pessoa; com homônimo, só se ela citar o processo
                if row and (mesma_pessoa or processo in autos):
                    chaves.append("nome:" + nn)
            rows = [self.con.execute("SELECT data_impressao FROM fichas WHERE chave=?", (ch,)).fetchone() for ch in chaves]
            datas = [rs.to_date((row[0] if row else "") or "") for row in rows]
            d_ex = max((d for d in datas if d), default=None)
            d_novo = rs.to_date(f.get("data_impressao") or "")
            if d_ex and (not d_novo or d_novo < d_ex):
                return False
            self.con.execute("INSERT OR REPLACE INTO fichas VALUES (?,?,?,?,?,?)",
                             (chave, processo or "", nn, f.get("data_impressao", ""),
                              datetime.now().strftime("%d/%m/%Y %H:%M"), json.dumps(f, ensure_ascii=False)))
            if len(chaves) > 1:
                self.con.execute("DELETE FROM fichas WHERE chave=?", (chaves[1],))
            self.con.commit()
        return True

    def fichas(self):
        """{processo: ficha} + {'nome:xxx': ficha} só para as não vinculadas (a ficha vinculada a um processo não é
        entregue a outro RSPE pelo nome)."""
        with self.lock:
            rows = self.con.execute("SELECT chave, processo, nome_norm, importado_em, dados FROM fichas").fetchall()
        out, relidas = {}, []
        for ch, p, nn, imp, dados in rows:
            f = json.loads(dados)
            if f.get("versao_leitura") != rf.VERSAO_LEITURA:
                try:
                    rf.atualizar(f)  # regras de leitura novas: refaz a partir dos eventos guardados, sem reimportar o PDF
                    relidas.append((json.dumps(f, ensure_ascii=False), ch))
                except Exception:
                    logging.getLogger("rspe").exception("falha ao reler a ficha %s", ch)
            f["importado_em"] = imp
            out[ch] = f
            if nn and not p:
                out.setdefault("nome:" + nn, f)
        if relidas:
            with self.lock:
                self.con.executemany("UPDATE fichas SET dados=? WHERE chave=?", relidas)
                self.con.commit()
        return out

    def remover_ficha(self, chave, nome_norm=None):
        """Remove a ficha do processo; sem ela, a ficha guardada pelo nome (a que o assistido recebe sem homônimo)."""
        with self.lock:
            cur = self.con.execute("DELETE FROM fichas WHERE chave=? OR processo=?", (chave, chave))
            if not cur.rowcount and nome_norm:
                self.con.execute("DELETE FROM fichas WHERE chave=?", ("nome:" + nome_norm,))
            self.con.commit()

    def baixas(self):
        with self.lock:
            rows = self.con.execute("SELECT processo, chave, titulo, obs, data FROM baixas").fetchall()
        out = {}
        for p, ch, t, o, d in rows:
            out.setdefault(p, {})[ch] = {"titulo": t, "obs": o, "data": d}
        return out

    def baixar(self, processo, chave, titulo, obs):
        with self.lock:
            self.con.execute("INSERT OR REPLACE INTO baixas VALUES (?,?,?,?,?)",
                             (processo, chave, titulo, obs or "", datetime.now().strftime("%d/%m/%Y %H:%M")))
            self.con.commit()

    def hist_add(self, processo, chave, titulo, obs, acao):
        with self.lock:
            self.con.execute("INSERT INTO baixas_hist (processo, chave, titulo, obs, data, acao) VALUES (?,?,?,?,?,?)",
                             (processo, chave, titulo or "", obs or "", datetime.now().strftime("%d/%m/%Y %H:%M"), acao))
            self.con.commit()

    def hist_alertas(self, processo):
        with self.lock:
            rows = self.con.execute("SELECT id, chave, titulo, obs, data, acao FROM baixas_hist WHERE processo=? ORDER BY id DESC",
                                    (processo,)).fetchall()
            ativas = {ch for (ch,) in self.con.execute("SELECT chave FROM baixas WHERE processo=?", (processo,))}
        vistos, out = set(), []
        for i, ch, t, o, d, a in rows:
            out.append({"chave": ch, "titulo": t, "obs": o, "data": d, "acao": a,
                        "ativa": a == "baixa" and ch in ativas and ch not in vistos})
            vistos.add(ch)
        return out

    def migrar_baixa(self, processo, antiga, nova):
        with self.lock:
            if not self.con.execute("SELECT 1 FROM baixas WHERE processo=? AND chave=?", (processo, nova)).fetchone():
                self.con.execute("UPDATE baixas SET chave=? WHERE processo=? AND chave=?", (nova, processo, antiga))
                self.con.execute("UPDATE baixas_hist SET chave=? WHERE processo=? AND chave=?", (nova, processo, antiga))
            self.con.commit()

    def presc_ajustes(self):
        with self.lock:
            rows = self.con.execute("SELECT processo, chave, dados, data FROM presc_ajustes").fetchall()
        out = {}
        for p, ch, d, dt in rows:
            try:
                v = json.loads(d or "{}")
            except Exception:
                continue
            v["_data"] = dt
            out.setdefault(p, {})[ch] = v
        return out

    def presc_ajuste_gravar(self, processo, chave, dados):
        with self.lock:
            if dados:
                self.con.execute("INSERT OR REPLACE INTO presc_ajustes VALUES (?,?,?,?)",
                                 (processo, chave, json.dumps(dados, ensure_ascii=False), datetime.now().strftime("%d/%m/%Y %H:%M")))
            else:
                self.con.execute("DELETE FROM presc_ajustes WHERE processo=? AND chave=?", (processo, chave))
            self.con.commit()

    def pedidos(self):
        with self.lock:
            rows = self.con.execute("SELECT processo, aba, data, obs, ref, registrado, tipo FROM pedidos").fetchall()
        out = {}
        for p, a, d, o, rf_, rg_, tp in rows:
            out.setdefault(p, {})[a] = {"data": d or "", "obs": o or "", "ref": rf_ or "", "registrado": rg_ or "",
                                        "tipo": tp or ("oficio" if a == "fd" else "pedido")}
        return out

    def pedido_gravar(self, processo, aba, dados):
        with self.lock:
            if not dados:
                self.con.execute("DELETE FROM pedidos WHERE processo=? AND aba=?", (processo, aba))
            else:
                self.con.execute("INSERT OR REPLACE INTO pedidos (processo, aba, data, obs, ref, registrado, tipo) VALUES (?,?,?,?,?,?,?)",
                                 (processo, aba, dados.get("data", ""), dados.get("obs", ""), dados.get("ref", ""),
                                  datetime.now().strftime("%d/%m/%Y %H:%M"), dados.get("tipo", "") or "pedido"))
            self.con.commit()

    def dados_manuais(self):
        with self.lock:
            rows = self.con.execute("SELECT processo, campo, valor, data FROM dados_manuais").fetchall()
        out = {}
        for p, c, v, dt in rows:
            out.setdefault(p, {})[c] = {"valor": v, "data": dt}
        return out

    def dado_gravar(self, processo, campo, valor):
        with self.lock:
            if valor in (None, ""):
                self.con.execute("DELETE FROM dados_manuais WHERE processo=? AND campo=?", (processo, campo))
            else:
                self.con.execute("INSERT OR REPLACE INTO dados_manuais VALUES (?,?,?,?)",
                                 (processo, campo, str(valor), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            self.con.commit()

    def manuais(self):
        with self.lock:
            rows = self.con.execute("SELECT processo, id, dados, data FROM atestados_manuais ORDER BY data").fetchall()
        out = {}
        for p, i, d, dt in rows:
            out.setdefault(p, []).append({"id": i, "dados": json.loads(d or "{}"), "data": dt})
        return out

    def manual_gravar(self, processo, dados):
        import uuid
        with self.lock:
            self.con.execute("INSERT INTO atestados_manuais VALUES (?,?,?,?)",
                             (processo, uuid.uuid4().hex[:10], json.dumps(dados, ensure_ascii=False), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            self.con.commit()

    def manual_remover(self, processo, id_):
        with self.lock:
            self.con.execute("DELETE FROM atestados_manuais WHERE processo=? AND id=?", (processo, id_))
            self.con.commit()

    def reabrir(self, processo, chave):
        with self.lock:
            self.con.execute("DELETE FROM baixas WHERE processo=? AND chave=?", (processo, chave))
            self.con.commit()

    def fixados(self):
        with self.lock:
            return {p: d for p, d in self.con.execute("SELECT processo, data FROM fixados").fetchall()}

    def fixar(self, processo, on):
        with self.lock:
            if on:
                self.con.execute("INSERT OR REPLACE INTO fixados VALUES (?,?)", (processo, datetime.now().strftime("%d/%m/%Y %H:%M")))
            else:
                self.con.execute("DELETE FROM fixados WHERE processo=?", (processo,))
            self.con.commit()

    def quadro(self):
        with self.lock:
            cols = [{"id": i, "nome": n, "ordem": o} for i, n, o in self.con.execute("SELECT id, nome, ordem FROM quadro_colunas ORDER BY ordem").fetchall()]
            cards = [dict(zip(("id", "coluna", "ordem", "processo", "titulo", "obs", "prazo", "etiqueta", "criado", "atualizado", "arquivado", "aba"), row))
                     for row in self.con.execute("SELECT id, coluna, ordem, processo, titulo, obs, prazo, etiqueta, criado, atualizado, "
                                                 "COALESCE(arquivado, ''), COALESCE(aba, '') FROM quadro_cartoes ORDER BY ordem").fetchall()]
        return {"colunas": cols, "cartoes": cards}

    def quadro_gravar(self, c):
        import uuid
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        with self.lock:
            cid = c.get("id") or uuid.uuid4().hex[:12]
            ant = self.con.execute("SELECT criado, ordem, coluna, COALESCE(arquivado, ''), COALESCE(aba, '') FROM quadro_cartoes WHERE id=?", (cid,)).fetchone()
            col = c.get("coluna") or (ant[2] if ant else "fazer")
            if c.get("ordem") is not None:
                ordem = float(c["ordem"])
            elif ant and ant[2] == col:
                ordem = ant[1]
            else:
                ordem = (self.con.execute("SELECT MIN(ordem) FROM quadro_cartoes WHERE coluna=?", (col,)).fetchone()[0] or 0) - 1
            arq = c["arquivado"] if "arquivado" in c else (ant[3] if ant else "")
            aba = c["aba"] if "aba" in c else (ant[4] if ant else "")
            self.con.execute("INSERT OR REPLACE INTO quadro_cartoes (id, coluna, ordem, processo, titulo, obs, prazo, etiqueta, criado, atualizado, "
                             "arquivado, aba) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                             (cid, col, ordem, c.get("processo") or "", (c.get("titulo") or "").strip(), (c.get("obs") or "").strip(),
                              (c.get("prazo") or "").strip(), c.get("etiqueta") or "", ant[0] if ant else agora, agora, arq or "", aba or ""))
            self.con.commit()
        return cid

    def quadro_pedido_feito(self, processo, aba):
        """Pedido marcado na aba: os cartões do mesmo assistido e benefício, no quadro, ganham a etiqueta "Pedido feito"."""
        with self.lock:
            n = self.con.execute("UPDATE quadro_cartoes SET etiqueta='pedido' WHERE processo=? AND aba=? AND COALESCE(arquivado, '')=''",
                                 (processo, aba.split("_")[0] if aba.startswith("ind_") else aba)).rowcount
            self.con.commit()
        return n

    def quadro_excluir(self, cid):
        with self.lock:
            self.con.execute("DELETE FROM quadro_cartoes WHERE id=?", (cid,))
            self.con.commit()

    def quadro_coluna(self, cid, nome):
        with self.lock:
            if nome:
                if self.con.execute("SELECT 1 FROM quadro_colunas WHERE id=?", (cid,)).fetchone():
                    self.con.execute("UPDATE quadro_colunas SET nome=? WHERE id=?", (nome, cid))
                else:
                    o = (self.con.execute("SELECT MAX(ordem) FROM quadro_colunas").fetchone()[0] or 0) + 1
                    self.con.execute("INSERT INTO quadro_colunas VALUES (?,?,?)", (cid, nome, o))
            else:
                self.con.execute("DELETE FROM quadro_colunas WHERE id=?", (cid,))
                self.con.execute("UPDATE quadro_cartoes SET coluna=(SELECT id FROM quadro_colunas ORDER BY ordem LIMIT 1) WHERE coluna=?", (cid,))
            self.con.commit()

    @property
    def nome(self):
        return os.path.splitext(os.path.basename(self.caminho))[0]

    def gravar(self, r):
        chave = r.get("processo_execucao") or r.get("arquivo")
        agora, dados = datetime.now().strftime("%d/%m/%Y %H:%M"), json.dumps(r, ensure_ascii=False)
        with self.lock:
            self.con.execute(
                "INSERT OR REPLACE INTO assistidos VALUES (?,?,?,?,?,?)",
                (chave, r.get("nome", ""), r.get("data_geracao_rspe", ""), r.get("arquivo", ""), agora, dados))
            self.con.execute("INSERT OR REPLACE INTO rspe_historico VALUES (?,?,?,?,?)",
                             (chave, r.get("data_geracao_rspe", ""), r.get("arquivo", ""), agora, dados))
            self.con.commit()

    def arquivar(self, r):
        """Guarda no histórico um RSPE que não substitui o atual (mais antigo). Devolve False se já estava guardado."""
        chave = r.get("processo_execucao") or r.get("arquivo")
        with self.lock:
            cur = self.con.execute("INSERT OR IGNORE INTO rspe_historico VALUES (?,?,?,?,?)",
                                   (chave, r.get("data_geracao_rspe", ""), r.get("arquivo", ""),
                                    datetime.now().strftime("%d/%m/%Y %H:%M"), json.dumps(r, ensure_ascii=False)))
            self.con.commit()
        return cur.rowcount > 0

    def historico(self, processo):
        """RSPEs guardados do processo, do mais antigo para o mais novo."""
        with self.lock:
            rows = self.con.execute("SELECT data_geracao, arquivo, importado_em, dados FROM rspe_historico WHERE processo=?",
                                    (processo,)).fetchall()
        out = [{"geracao": g or "", "arquivo": a or "", "importado_em": i or "", "dados": json.loads(d)} for g, a, i, d in rows]
        return sorted(out, key=lambda x: rs.to_date(x["geracao"]) or date.min)

    def historico_n(self):
        with self.lock:
            return dict(self.con.execute("SELECT processo, COUNT(*) FROM rspe_historico GROUP BY processo").fetchall())

    def pessoa_man(self):
        """{processo: identificador comum} dos assistidos que o operador marcou como a mesma pessoa (Auditoria, homônimo)."""
        with self.lock:
            rows = self.con.execute("SELECT processo, valor FROM dados_manuais WHERE campo='mesma_pessoa'").fetchall()
        return {p: v for p, v in rows if v}

    def todos(self):
        with self.lock:
            rows = self.con.execute("SELECT dados, importado_em FROM assistidos ORDER BY nome").fetchall()
        man = self.pessoa_man()
        out = []
        for dados, imp in rows:
            d = json.loads(dados)
            d["importado_em"] = imp
            if d.get("processo_execucao") in man:
                d["_pessoa_man"] = man[d["processo_execucao"]]
            out.append(d)
        return out

    def um(self, processo):
        with self.lock:
            row = self.con.execute("SELECT dados, importado_em FROM assistidos WHERE processo=?", (processo,)).fetchone()
        if not row:
            return None
        d = json.loads(row[0])
        d["importado_em"] = row[1]
        man = self.pessoa_man()
        if processo in man:
            d["_pessoa_man"] = man[processo]
        return d

    def nomes_pessoas(self):
        """Nome, CPF e mãe de cada registro (contagem de homônimos sem ler a base inteira)."""
        with self.lock:
            rows = self.con.execute("SELECT nome, dados FROM assistidos").fetchall()
        man = self.pessoa_man()
        out = []
        for n, d in rows:
            try:
                j = json.loads(d)
            except Exception:
                j = {}
            out.append({"nome": n, "cpf": j.get("cpf") or "", "nome_mae": j.get("nome_mae") or "",
                        "data_nascimento": j.get("data_nascimento") or "", "processo_execucao": j.get("processo_execucao") or "",
                        "_pessoa_man": man.get(j.get("processo_execucao") or "", "")})
        return out

    def nomes(self):
        with self.lock:
            return [n for (n,) in self.con.execute("SELECT nome FROM assistidos").fetchall()]

    def existente(self, processo):
        """(data_geracao, hash) do registro já gravado para o processo, ou None."""
        with self.lock:
            row = self.con.execute("SELECT data_geracao, dados FROM assistidos WHERE processo=?", (processo,)).fetchone()
        if not row:
            return None
        try:
            h = json.loads(row[1]).get("_hash", "")
        except Exception:
            h = ""
        return (row[0], h)

    def remover(self, processo):
        with self.lock:
            self.con.execute("DELETE FROM assistidos WHERE processo=?", (processo,))
            self.con.execute("DELETE FROM rspe_historico WHERE processo=?", (processo,))
            self.con.commit()

    def fechar(self):
        with self.lock:
            self.con.close()


# --------------------------------------------------------------------------- #
# API exposta ao HTML
# --------------------------------------------------------------------------- #

class Api:
    _serializable = True

    def __init__(self):
        self._janela = None
        self.base = None          # o programa abre sem base carregada
        self._modelos = []
        self._json = {}
        self._imp_lock = threading.RLock()   # uma importação por vez (manual ou pela pasta vigiada)
        self._vigia_thread = None
        self._vigia_tam = {}
        self._vigia_ultima = ""
        rg.carregar()

    # ---- configuração (só a lista de bases recentes) ----
    def _recentes(self):
        try:
            with open(CONFIG, encoding="utf-8") as f:
                c = json.load(f)
            return [p for p in c.get("recentes", []) if os.path.exists(p)]
        except Exception:
            return []

    def _cfg(self):
        try:
            with open(CONFIG, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _cfg_gravar(self, **kv):
        c = self._cfg()
        c.update(kv)
        try:
            with open(CONFIG, "w", encoding="utf-8") as f:
                json.dump(c, f, ensure_ascii=False)
        except Exception:
            pass

    def _salvar_config(self):
        rec = self._recentes()
        if self.base:
            rec = [self.base.caminho] + [p for p in rec if p != self.base.caminho]
        self._cfg_gravar(recentes=rec[:8])

    def _js(self, codigo):
        if self._janela:
            try:
                self._janela.evaluate_js(codigo)
            except Exception:
                pass

    # ---- dados ----
    def listar(self):
        rv.HOJE = datetime.now().date()  # a data de referência acompanha o relógio (programa aberto após a meia-noite)
        if not self.base:
            return {"sem_base": True, "recentes": [{"caminho": p, "nome": os.path.splitext(os.path.basename(p))[0]} for p in self._recentes()],
                    "hoje": rv.HOJE.strftime("%d/%m/%Y"), "abas": rv.ABAS, "rotulos": rv.ROTULO, "ajuda": AJUDA + _ajuda_juris(),
                    "base_juridica": {"versao": rg.versao(), "origem": rg.origem()}, "registros": []}
        brutos = self.base.todos()
        ctx = self._contexto(brutos)
        self._modelos = []
        self._json = {}
        self._hoje_modelos = rv.HOJE
        res = None
        if len(brutos) >= 80:
            # base grande: cada assistido é montado num processo paralelo (a análise é pesada: ~45 ms por assistido)
            try:
                with ProcessPoolExecutor(max_workers=max(2, min(8, (os.cpu_count() or 2) - 1))) as ex:
                    res = list(ex.map(_montar_proc, [(r, _ctx_de(ctx, r), rv.HOJE) for r in brutos], chunksize=10))
            except Exception:
                logging.getLogger("rspe").exception("montagem paralela indisponível; montando em sequência")
                res = None
        if res is not None:
            for m, migrar in res:
                for ch, de, para in migrar:
                    try:
                        self.base.migrar_baixa(ch, de, para)
                    except Exception:
                        logging.getLogger("rspe").exception("falha ao migrar baixa %s", ch)
                self._modelos.append(m)
        else:
            for r in brutos:
                self._modelos.append(self._montar(r, ctx))
        _todos = self._modelos
        self._modelos = _so_ativos(self._modelos, brutos)
        _ids = {id(m) for m in self._modelos}
        self._ocultos = [m for m in _todos if id(m) not in _ids]  # outras execuções de quem tem mais de um RSPE (fora da lista)
        return {
            "base": self.base.nome,
            "hoje": rv.HOJE.strftime("%d/%m/%Y"),
            "abas": rv.ABAS,
            "rotulos": rv.ROTULO,
            "rotulos_dica": rv.ROTULO_DICA,
            "ajuda": AJUDA + _ajuda_juris(),
            "base_juridica": {"versao": rg.versao(), "origem": rg.origem()},
            # json_seguro: um Fraction ou date esquecido no modelo derrubava a lista inteira ("Object of type Fraction is not JSON serializable")
            # versão leve (sem os textos de prescrição e auditoria): a base grande chega à tela em segundos; o registro completo
            # vem quando a ficha, a linha expandida ou o cálculo da fuga é aberto (Api.registro)
            "registros": [_leve(self._json_de(m)) for m in self._modelos],
            "copia": self._copia_info(),
        }

    def registro(self, processo):
        """Registro completo de um assistido (a lista chega à tela na versão leve)."""
        m = next((x for x in (self._modelos or []) if x.get("id") == processo), None)
        if m is None:
            return self._atualizar(processo)
        return {"parcial": [self._json_de(m)]}

    def _json_de(self, m):
        """Registro pronto para a tela (sem o bruto), guardado até o assistido mudar."""
        j = self._json.get(m.get("id"))
        if j is None:
            j = self._json[m.get("id")] = rv.json_seguro({k: v for k, v in m.items() if k != "_bruto"})
        return j

    def _contexto(self, brutos=None):
        """Tabelas auxiliares da base e a contagem de homônimos (a ficha guardada pelo nome só vale sem homônimo)."""
        ctx = {"baixas": self.base.baixas(), "fichas": self.base.fichas(), "manuais": self.base.manuais(),
               "ajustes": self.base.presc_ajustes(), "dmanuais": self.base.dados_manuais(), "peds": self.base.pedidos(),
               "hist_n": self.base.historico_n(), "fixados": self.base.fixados()}
        # homônimos contam pessoas, não RSPEs: duas execuções da mesma pessoa (mesmo CPF; sem CPF, nome + mãe) não impedem a ficha pelo nome
        regs = brutos if brutos is not None else self.base.nomes_pessoas()
        regs = list(regs)
        repetidos = {id(r) for g in _grupos_pessoa(regs) for r in g[1:]}  # mesma pessoa conta uma vez
        h = {}
        for r in regs:
            if id(r) not in repetidos:
                h[_norm(r.get("nome", ""))] = h.get(_norm(r.get("nome", "")), 0) + 1
        ctx["homonimos"] = h
        ctx["outras_cond"] = _outras_cond(brutos) if brutos is not None else {}
        ctx["outros_procs"] = _outros_procs(brutos) if brutos is not None else {}
        ctx["outras_exec"] = _outras_exec(brutos) if brutos is not None else {}
        ctx["homon_det"] = _homonimos_det(brutos) if brutos is not None else {}
        return ctx

    def _atualizar(self, processo, msg=None):
        """Refaz só o assistido alterado (marcar pedido, baixar alerta, dado informado...) em vez da base inteira:
        a tela recebe apenas esse registro e o troca na lista que já tem."""
        if not self._modelos or getattr(self, "_hoje_modelos", None) != datetime.now().date():
            r = self.listar()
            if msg:
                r["msg"] = msg
            return r
        r = self.base.um(processo)
        self._json.pop(processo, None)
        rv.HOJE = datetime.now().date()
        if r is None:
            self._modelos = [m for m in self._modelos if m.get("id") != processo]
            out = {"parcial": [], "removido": processo}
        else:
            ctx = self._contexto()
            k = _chaves_pessoa(r)
            _todos = [r] + [o for o in self.base.todos() if o.get("processo_execucao") != processo]
            # homônimos (mesmo nome, outra pessoa): sem isto, o aviso sumia ao refazer só este assistido
            _hd = _homonimos_det(_todos).get(processo)
            ctx["homon_det"] = {processo: _hd} if _hd else {}
            if k:
                _g = next((g for g in _grupos_pessoa(_todos) if any(x is r for x in g)), [r])
                ctx["outras_cond"], ctx["outros_procs"], ctx["outras_exec"] = _outras_cond(_g), _outros_procs(_g), _outras_exec(_g)
            m = self._montar(r, ctx)
            i = next((k for k, x in enumerate(self._modelos) if x.get("id") == m.get("id")), None)
            oc = getattr(self, "_ocultos", None) or []
            j = next((k for k, x in enumerate(oc) if x.get("id") == m.get("id")), None)
            if i is None and j is not None:
                oc[j] = m  # execução que não é a principal da pessoa: continua fora da lista
                out = {"parcial": []}
            else:
                if i is None:
                    self._modelos.append(m)
                else:
                    self._modelos[i] = m
                out = {"parcial": [self._json_de(m)]}
        out["copia"] = self._copia_info()
        if msg:
            out["msg"] = msg
        return out

    def _montar(self, r, ctx):
        m, migrar = _montar_modelo(r, ctx)
        for ch, de, para in migrar:
            try:
                self.base.migrar_baixa(ch, de, para)
            except Exception:
                logging.getLogger("rspe").exception("falha ao migrar baixa %s", ch)
        return m

    def fixar(self, processo, on):
        """Fixa (ou solta) o assistido: fica no topo de todas as abas, com a faixa de fixados para achá-lo rápido."""
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        self.base.fixar(processo, bool(on))
        return self._atualizar(processo, "Assistido fixado no topo das abas." if on else "Assistido solto.")

    def quadro(self):
        """Quadro do Usuário: colunas e cartões (processos acompanhados de perto, com observação, prazo e etiqueta)."""
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        return self.base.quadro()

    def quadro_gravar(self, cartao):
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        cartao = dict(cartao or {})
        if cartao.get("prazo") and not rs.to_date(cartao["prazo"]):
            return {"erro": "Prazo inválido: use dd/mm/aaaa."}
        if not (cartao.get("titulo") or "").strip() and not cartao.get("processo"):
            return {"erro": "Dê um título ao cartão ou escolha um assistido."}
        self.base.quadro_gravar(cartao)
        q = self.base.quadro()
        q["msg"] = "Cartão gravado no Quadro do Usuário."
        return q

    def quadro_mover(self, cid, coluna, ordem):
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        c = next((x for x in self.base.quadro()["cartoes"] if x["id"] == cid), None)
        if not c:
            return {"erro": "Cartão não encontrado."}
        c.update(coluna=coluna, ordem=ordem)
        self.base.quadro_gravar(c)
        return self.base.quadro()

    def quadro_arquivar(self, cid, on, coluna=None):
        """Arquiva o cartão (sai do quadro e fica na lista "Cartões arquivados") ou o devolve ao quadro, na coluna indicada."""
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        c = next((x for x in self.base.quadro()["cartoes"] if x["id"] == cid), None)
        if not c:
            return {"erro": "Cartão não encontrado."}
        c["arquivado"] = datetime.now().strftime("%d/%m/%Y %H:%M") if on else ""
        if not on and coluna and coluna != c["coluna"]:
            c.update(coluna=coluna, ordem=None)
        self.base.quadro_gravar(c)
        q = self.base.quadro()
        q["msg"] = "Cartão arquivado: consulte em \"Cartões arquivados\"." if on else "Cartão devolvido ao quadro."
        return q

    def quadro_excluir(self, cid):
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        self.base.quadro_excluir(cid)
        q = self.base.quadro()
        q["msg"] = "Cartão excluído."
        return q

    def quadro_coluna(self, cid, nome):
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        self.base.quadro_coluna(cid, (nome or "").strip())
        return self.base.quadro()

    HIST_ABAS = {"prog": ("Progressão", r"PROGRESS"), "liv": ("Livramento condicional", r"LIVRAMENTO"),
                 "ind": ("Indulto/comutação", r"INDULTO|COMUTA"), "presc": ("Prescrição", r"PRESCRI"),
                 "ext": ("Extinção", r"EXTIN"), "rem": ("Remição", r"REMI"), "fd": ("Remição (ofício)", r"REMI")}

    def historico(self, processo):
        """Histórico comparativo dos RSPEs importados do assistido (aba Geral): uma coluna por RSPE, do mais antigo ao
        atual, com os campos que costumam mudar e o que mudou em relação ao anterior. Cada RSPE é lido com as regras
        desta versão (a mesma análise do atual), sem a ficha disciplinar e sem os ajustes do operador."""
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        hs = self.base.historico(processo)
        if not hs:
            return {"erro": "Assistido não encontrado."}
        peds = self.base.pedidos().get(processo, {})
        cols = []
        ant_inc = None
        for h in hs:
            r = h["dados"]
            try:
                m = rv.modelo(rs.reprocessar(json.loads(json.dumps(r))), {}, None, [])
            except Exception:
                logging.getLogger("rspe").exception("histórico %s %s", processo, h["geracao"])
                m = {}
            rem, perd = rs.saldo_remidos_num(r.get("saldo_remidos") or "")
            incs = r.get("_incidentes") or []
            chaves = ["|".join(str(i.get(k) or "") for k in ("tipo", "situacao", "complemento", "data_decisao", "data_referencia")) for i in incs]
            novos = [] if ant_inc is None else [i for i, k in zip(incs, chaves) if k not in ant_inc]
            ant_inc = set(chaves)
            nd = lambda v: (v if v not in (None, "", "—") else "—")
            cols.append({
                "geracao": h["geracao"], "arquivo": h["arquivo"], "importado_em": h["importado_em"], "_incs": incs,
                "campos": {
                    "regime": nd(m.get("regime") or r.get("regime_atual")),
                    "pena_total": nd(m.get("pena_total")), "pena_cumprida": nd(m.get("pena_cumprida")),
                    "remidos": "%s (%s)" % (rs.num_txt(rem), rs.num_txt(perd)),
                    "db": nd(m.get("db") or m.get("dbase")), "prog": nd(m.get("prog")), "liv": nd(m.get("liv")),
                    "termino": nd(m.get("termino")), "falta": self._falta_curta(m.get("falta_full")),
                },
                "novos": [self._inc_txt(i) for i in novos],
                "pedidos": [],
            })
        # pedido: vai para a coluna do primeiro RSPE emitido depois dele; o retorno é o incidente do tipo decidido depois do pedido
        for aba, p in peds.items():
            dp = rs.to_date(p.get("data") or "")
            if not dp:
                continue
            nome, rx_ = self.HIST_ABAS.get(aba, (aba, None))
            col = next((c for c in cols if (rs.to_date(c["geracao"]) or date.min) >= dp), None)
            txt = "%s pedida em %s" % (nome, p["data"])
            if col is None:
                cols[-1]["pedidos"].append({"txt": txt + " · aguardando RSPE posterior", "ret": ""})
                continue
            ret = ""
            for i in col["_incs"]:
                di = rs.to_date(i.get("data_decisao") or "") or rs.to_date(i.get("data_referencia") or "")
                if rx_ and re.search(rx_, rs._sem_acento(i.get("tipo") or "")) and di and di >= dp:
                    sit = rs._sem_acento(i.get("situacao") or "")
                    ret = ("indeferida" if re.search(r"NAO CONCEDID|INDEFERID|NEGAD", sit) else
                           "deferida" if re.search(r"CONCEDID|DEFERID|HOMOLOG", sit) else "em análise")
                    ret = "%s (incidente de %s)" % (ret, fmt_(di))
                    break
            col["pedidos"].append({"txt": txt, "ret": ret or "sem retorno neste RSPE"})
        for c in cols:
            c.pop("_incs", None)
        m0 = next((x for x in self._modelos if x.get("id") == processo), {})
        return rv.json_seguro({"nome": m0.get("nome") or hs[-1]["dados"].get("nome", ""), "processo": processo, "colunas": cols})

    @staticmethod
    def _inc_txt(i):
        """'Falta grave: Data da infração: 18/07/2025 · concedido em 30/08/2025'."""
        t = (i.get("tipo") or "Incidente").capitalize()
        c = (i.get("complemento") or "").strip()
        sit = (i.get("situacao") or "").strip().lower()
        d = i.get("data_decisao") or i.get("data_referencia") or ""
        return t + (": " + c if c and len(c) <= 80 else "") + (" · " + sit if sit else "") + ((" em " if sit else " · ") + d if d else "")

    @staticmethod
    def _falta_curta(f):
        """'Sim · FALTA GRAVE Data da infração: 18/07/2025 (18/07/2025)' -> 'Sim (18/07/2025)'."""
        f = (f or "").strip()
        if not f:
            return "—"
        if f.startswith("Sim"):
            ds = sorted(set(re.findall(r"\d{2}/\d{2}/\d{4}", f)), key=lambda x: rs.to_date(x) or date.min)
            return "Sim" + (" (%s)" % ", ".join(ds) if ds else "")
        return f

    def indulto_linha(self, id_):
        """Linha do tempo de indulto e comutação de um assistido (aba Indulto / Comutação)."""
        m = next((x for x in self._modelos if x.get("id") == id_), None)
        if not m or not m.get("_bruto"):
            return {"erro": "Assistido não encontrado."}
        try:
            return rv.json_seguro(rtl.linha(m["_bruto"], rv.HOJE))
        except Exception as e:
            logging.getLogger("rspe").exception("linha do tempo de indulto %s", id_)
            return {"erro": "Falha ao montar a linha do tempo: %s" % e}

    def presc_ajuste(self, processo, chave, dados):
        """Grava (ou apaga, com dados vazios) os dados de prescrição preenchidos ou corrigidos pelo operador para um crime
        (datas, pena, reincidência, art. 115, saldo na data da fuga) e refaz a análise."""
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        self.base.presc_ajuste_gravar(processo, chave, dados or None)
        return self._atualizar(processo)

    def presc_saldos_calc(self, processo, fuga, saldos, fonte="calculadora"):
        """Grava os saldos apurados na calculadora para a fuga: {chave_ajuste do crime: dias}. Cada saldo vale como informado,
        com a fonte "calculadora"; saldo vazio apaga o daquele crime."""
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        if not rs.to_date(fuga or ""):
            return {"erro": "Data da fuga inválida."}
        atuais = self.base.presc_ajustes().get(processo, {})
        for ch, dias in (saldos or {}).items():
            d = dict(atuais.get(ch) or {})
            d.pop("_data", None)
            sal, fon = dict(d.get("saldos") or {}), dict(d.get("saldo_fonte") or {})
            if dias is None or str(dias).strip() == "":
                sal.pop(fuga, None)
                fon.pop(fuga, None)
            else:
                sal[fuga], fon[fuga] = int(dias), (fonte if fonte in ("calculadora", "digitado") else "calculadora")
            d["saldos"], d["saldo_fonte"] = sal, fon
            if not d["saldos"]:
                d.pop("saldos")
                d.pop("saldo_fonte")
            self.base.presc_ajuste_gravar(processo, ch, d or None)
        return self._atualizar(processo, "Saldos gravados: prescrição recalculada.")

    def pedido(self, processo, aba, data, obs, ref, tipo="pedido"):
        """Marca (ou desmarca, com data vazia) o pedido já feito na aba: data do protocolo, observação livre e a situação
        da aba no momento da marcação (para avisar se ela mudar depois, com um RSPE novo)."""
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        data = (data or "").strip()
        if data and not rs.to_date(data):
            return {"erro": "Data inválida: use dd/mm/aaaa."}
        self.base.pedido_gravar(processo, aba, {"data": data, "obs": (obs or "").strip(), "ref": ref or "", "tipo": tipo or "pedido"} if data else None)
        n = self.base.quadro_pedido_feito(processo, aba) if data else 0
        out = self._atualizar(processo, ("Pedido registrado." + (" Cartão do Quadro marcado como \"Pedido feito\"." if n else "")) if data else "Marcação de pedido removida.")
        if n and isinstance(out, dict):
            out["quadro"] = self.base.quadro()
        return out

    # ---- jurisprudências da triagem automática (teses_auto.bin): índice leve para a tela; texto integral sob demanda ----
    _auto = None
    _auto_txt = None
    _auto_norm = None

    def _teses_auto(self):
        if Api._auto is None:
            import struct
            import zlib
            Api._auto = {"cab": {}, "itens": []}
            c = recurso("teses_auto.bin")
            if not os.path.isfile(c) and os.path.isfile(os.path.join(pasta_app(), "teses_auto.bin")):
                c = os.path.join(pasta_app(), "teses_auto.bin")  # cópia ao lado do .exe
            try:
                with open(c, "rb") as f:
                    b = f.read()
                if b[:8] == b"APTOTES1":
                    na, nb = struct.unpack("<II", b[8:16])
                    Api._auto = json.loads(zlib.decompress(b[16:16 + na]).decode("utf-8"))
                    Api._auto["_z"] = b[16 + na:16 + na + nb]
                    Api._auto["resumos"] = {i["id"]: i.pop("ementa", "") for i in Api._auto["itens"]}
            except Exception:
                logging.getLogger("rspe").exception("jurisprudências automáticas %s", c)
        return Api._auto

    def _teses_textos(self):
        if Api._auto_txt is None:
            import zlib
            z = self._teses_auto().get("_z")
            Api._auto_txt = json.loads(zlib.decompress(z).decode("utf-8")) if z else {}
        return Api._auto_txt

    def tese_texto(self, id_):
        """Texto integral (como veio do acervo) de uma decisão da triagem automática."""
        return {"id": id_, "texto": self._teses_textos().get(id_, "")}

    @staticmethod
    def _norm_busca(t):
        import unicodedata
        return " " + re.sub(r"\s+", " ", unicodedata.normalize("NFD", t or "").encode("ascii", "ignore").decode().lower()) + " "

    def _teses_indice(self):
        if Api._auto_norm is None:
            Api._auto_norm = [(k, self._norm_busca(t)) for k, t in self._teses_textos().items()]
        return Api._auto_norm

    def teses_buscar(self, q):
        """Ids das decisões da triagem automática cujo texto integral tem todas as palavras da busca (começo de palavra; sem
        acento e caixa)."""
        ws = [" " + w for w in self._norm_busca(q).split() if len(w) >= 2]
        if not ws:
            return []
        return [k for k, t in self._teses_indice() if all(w in t for w in ws)][:5000]

    def teses_resumos(self, ids):
        """Resumo (EMENTA do fim da decisão ou o começo do texto) das decisões da triagem automática pedidas pela tela."""
        R = self._teses_auto().get("resumos") or {}
        return {i: R.get(i, "") for i in (ids or [])[:200]}

    def teses(self):
        """Jurisprudências da execução penal (aba Jurisprudências): decisões do TJMS, STJ e STF favoráveis à defesa, triadas pela
        ementa. Um teses_execucao.json ao lado do programa só substitui a cópia embutida (módulo rspe_teses) se for de versão igual
        ou mais nova - um arquivo antigo esquecido na pasta não esconde a base atual."""
        emb = None
        try:
            import rspe_teses
            emb = rspe_teses.DADOS
        except Exception:
            logging.getLogger("rspe").exception("banco de teses embutido")
        c = os.path.join(pasta_app(), "teses_execucao.json")
        if os.path.isfile(c):
            try:
                with open(c, encoding="utf-8") as f:
                    ext = json.load(f)
                if not emb or str(ext.get("versao") or "") >= str(emb.get("versao") or ""):
                    return self._juntar_auto(ext)
            except Exception:
                logging.getLogger("rspe").exception("banco de teses %s", c)
        return self._juntar_auto(emb) if emb else {"erro": "Falha ao carregar as jurisprudências."}

    def _juntar_auto(self, d):
        """Base curada + triagem automática (sem repetir processo já curado)."""
        A = self._teses_auto()
        for i in d["itens"] + A.get("itens", []):
            # monocrática do STJ: o link do acervo é a pesquisa do processo; o inteiro teor é a página da decisão (registro + publicação)
            m = re.search(r"processo\.stj\.jus\.br/processo/pesquisa/\?num_registro=(\d{12})", i.get("link") or "")
            if m and re.match(r"\d{2}/\d{2}/\d{4}$", i.get("pub") or ""):
                i["link"] = "https://processo.stj.jus.br/processo/monocraticas/decisoes/?num_registro=%s&dt_publicacao=%s" % (m.group(1), i["pub"])
        if not A.get("itens"):
            return dict(d, aviso="Arquivo teses_auto.bin não encontrado junto do programa: aparecem só as decisões curadas. Gere o .exe com o "
                                 "build atual (que inclui o arquivo) ou copie teses_auto.bin para a pasta do APTO.exe.")
        ja = {((i.get("tribunal") or "TJMS"), re.sub(r"\D", "", i.get("proc") or "")) for i in d["itens"]}
        novos = [i for i in A["itens"] if (i["tribunal"], re.sub(r"\D", "", i["proc"])) not in ja]
        threading.Thread(target=self._teses_indice, daemon=True).start()  # índice da busca no texto integral, em segundo plano
        itens = d["itens"] + novos
        cont = {}
        for i in itens:
            for t in i.get("temas") or []:
                cont[t] = cont.get(t, 0) + 1
        temas = [{"tema": t, "n": n} for t, n in sorted(cont.items(), key=lambda z: (z[0] == "Outros", -z[1]))]
        trib = [t for t in ("TJMS", "STJ", "STF") if any((i.get("tribunal") or "TJMS") == t for i in itens)]
        return dict(d, itens=itens, temas=temas, tribunais=trib, total=len(itens), n_auto=len(novos),
                    fonte=d.get("fonte", "") + " · " + (A.get("cab") or {}).get("fonte", ""))

    def abrir_url(self, url):
        """Abre no navegador o inteiro teor de um acórdão das jurisprudências (só endereços http/https)."""
        if not re.match(r"^https?://", url or "", re.I):
            return {"erro": "Endereço inválido."}
        import webbrowser
        webbrowser.open(url)
        return {"msg": "Abrindo no navegador…"}

    def dado_manual(self, processo, campo, valor):
        """Dado objetivo que o RSPE não trouxe, informado pelo operador no alerta da Auditoria (data de nascimento,
        pena máxima em abstrato de um tipo). Valor vazio apaga. A análise é refeita com ele."""
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        valor = (valor or "").strip()
        if valor and campo == "data_nascimento" and not rs.to_date(valor):
            return {"erro": "Data inválida: use dd/mm/aaaa."}
        if valor and campo == "data_base" and not rs.to_date(valor.split("|")[0]):
            return {"erro": "Data-base inválida: use dd/mm/aaaa."}
        if campo == "sexo" and valor not in ("", "M", "F"):
            return {"erro": "Sexo inválido."}
        if campo.startswith("falta|") and valor not in ("", "sim", "nao"):
            return {"erro": "Decisão inválida sobre a falta."}
        if campo.startswith("rspe|"):
            c = campo[5:]
            if c not in rs.CAMPOS_MANUAIS:
                return {"erro": "Campo inválido."}
            tipo = rs.CAMPOS_MANUAIS[c][1]
            if valor and tipo == "data" and not rs.to_date(valor):
                return {"erro": "Data inválida: use dd/mm/aaaa."}
            if valor and tipo == "pena" and not rs.pena_livre(valor):
                return {"erro": "Pena inválida: use, por exemplo, 4 anos e 6 meses ou 4a6m0d."}
            if valor and tipo == "regime" and not rs.regime_manual(valor):
                return {"erro": "Regime inválido: fechado, semiaberto ou aberto."}
        if valor and campo.startswith("pena_max|") and not rs.pena_livre(valor):
            return {"erro": "Pena inválida: use, por exemplo, 3 meses, 1 ano e 6 meses ou 0a3m0d."}
        self.base.dado_gravar(processo, campo, valor)
        return self._atualizar(processo, "Dado gravado; análise refeita." if valor else "Dado informado apagado.")

    def vincular_ficha(self, processo, chave):
        """Vincula ao assistido a ficha guardada pelo nome (Auditoria: ficha de nome parecido que não vinculou sozinha)."""
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        with self.base.lock:
            row = self.base.con.execute("SELECT dados FROM fichas WHERE chave=?", (chave,)).fetchone()
        if not row:
            return {"erro": "Ficha não encontrada (já vinculada?)."}
        f = json.loads(row[0])
        self.base.gravar_ficha(f, processo, True)
        with self.base.lock:
            self.base.con.execute("DELETE FROM fichas WHERE chave=? AND chave!=?", (chave, processo))
            self.base.con.commit()
        r = self.listar()
        r["msg"] = "Ficha vinculada; análise refeita."
        return r

    def desvincular_ficha(self, processo, assinatura):
        """Tira de um assistido a ficha que é de outra pessoa (alerta de CPF, mãe ou nome na Auditoria). A ficha fica na base,
        guardada pelo nome, e pode ser vinculada a outro assistido; "Desfazer" (revincular_ficha) devolve o vínculo."""
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        atual = (self.base.dados_manuais().get(processo, {}).get("ficha_recusada") or {}).get("valor") or ""
        self.base.dado_gravar(processo, "ficha_recusada", "\n".join(sorted((set(atual.split("\n")) | {assinatura}) - {""})))
        with self.base.lock:
            row = self.base.con.execute("SELECT dados FROM fichas WHERE chave=?", (processo,)).fetchone()
            f = json.loads(row[0]) if row else None
            if f and rf.assinatura_ficha(f) == assinatura:
                # gravada no processo deste assistido: volta a ser guardada pelo nome (sem apagar a ficha mais nova do nome)
                ch = "nome:" + _norm(f.get("nome", ""))
                if not self.base.con.execute("SELECT 1 FROM fichas WHERE chave=?", (ch,)).fetchone():
                    self.base.con.execute("UPDATE fichas SET chave=?, processo='' WHERE chave=?", (ch, processo))
                else:
                    self.base.con.execute("DELETE FROM fichas WHERE chave=?", (processo,))
                self.base.con.commit()
        r = self.listar()
        r["msg"] = "Ficha desvinculada deste assistido; análise refeita sem ela."
        return r

    def revincular_ficha(self, processo):
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        self.base.dado_gravar(processo, "ficha_recusada", "")
        r = self.listar()
        r["msg"] = "Desvínculo desfeito; análise refeita."
        return r

    def mesma_pessoa(self, processo, outro):
        """Marca dois assistidos (homônimos) como a mesma pessoa: passam a uma linha só, como os RSPEs do mesmo CPF."""
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        gid = min(processo, outro)
        self.base.dado_gravar(processo, "mesma_pessoa", gid)
        self.base.dado_gravar(outro, "mesma_pessoa", gid)
        r = self.listar()
        r["msg"] = "Marcados como a mesma pessoa; análise refeita."
        return r

    def baixar_alerta(self, processo, chave, titulo, obs):
        if not self.base:
            return None
        if not (obs or "").strip():
            return {"erro": "Informe o motivo da baixa: ele fica no Histórico de alertas."}
        self.base.baixar(processo, chave, titulo, obs.strip())
        self.base.hist_add(processo, chave, titulo, obs.strip(), "baixa")
        return self._atualizar(processo, "Alerta baixado: a guia segue em ordem e o motivo fica no Histórico de alertas.")

    def historico_alertas(self, processo):
        """Baixas e reaberturas de alertas da Auditoria deste assistido, da mais recente para a mais antiga."""
        if not self.base:
            return []
        return self.base.hist_alertas(processo)

    # ---- ficha disciplinar: conferência e atestados fora da ficha ----
    def fd_conferir(self, processo, chave, marcar):
        if not self.base:
            return None
        if marcar:
            self.base.baixar(processo, chave, "conferido (ficha disciplinar)", "")
        else:
            self.base.reabrir(processo, chave)
        return self._atualizar(processo)

    def fd_adicionar(self, processo, dados):
        if not self.base:
            return None
        dados = {k: str(v or "").strip() for k, v in (dados or {}).items()}
        if not (dados.get("remidos") or dados.get("trabalhados") or dados.get("horas")):
            return {"erro": "Informe ao menos os dias remidos, os dias trabalhados ou as horas."}
        self.base.manual_gravar(processo, dados)
        return self._atualizar(processo, "Adicionado.")

    def fd_remover(self, processo, id_):
        if not self.base:
            return None
        self.base.manual_remover(processo, id_)
        return self._atualizar(processo, "Removido.")

    def reabrir_alerta(self, processo, chave):
        if not self.base:
            return None
        h = next((x for x in self.base.hist_alertas(processo) if x["chave"] == chave), None)
        self.base.reabrir(processo, chave)
        self.base.hist_add(processo, chave, (h or {}).get("titulo", ""), "", "reaberto")
        return self._atualizar(processo, "Alerta reaberto.")

    def remover(self, chave):
        if not self.base:
            return None
        self.base.remover(chave)
        return self.listar()

    # ---- bases ----
    def _trocar_base(self, caminho):
        with self._imp_lock:
            return self._trocar_base_(caminho)

    def _etapa(self, texto):
        """Mostra a etapa na tela de carregamento (a tela já fica visível enquanto a base abre)."""
        self._js("window.ui && ui.carregando && ui.carregando(%s)" % json.dumps(texto))

    def _trocar_base_(self, caminho):
        if self.base:
            self.base.fechar()
        self._etapa("Abrindo o arquivo da base…")
        self.base = Base(caminho)
        self._salvar_config()
        self._etapa("Fazendo a cópia de segurança…")
        try:
            self._fazer_copia()
        except Exception:
            logging.getLogger("rspe").exception("cópia de segurança de %s", caminho)
        try:
            n = len(self.base.nomes())
        except Exception:
            n = 0
        self._etapa("Calculando prazos e benefícios de %s…" % rs.pl(n, "assistido", "assistidos") if n else "Calculando prazos e benefícios…")
        r = self.listar()
        self._etapa("Montando a tela…")
        return r

    # ---- cópias de segurança: uma a cada abertura da base, guardadas as 10 últimas ----
    COPIAS_MAX = 10

    def _pasta_copias(self):
        return os.path.join(os.path.dirname(os.path.abspath(self.base.caminho)), "copias", self.base.nome)

    def _copias(self):
        """Cópias da base aberta, da mais nova para a mais antiga: [(caminho, datetime)]."""
        pasta = self._pasta_copias()
        out = []
        if os.path.isdir(pasta):
            for a in os.listdir(pasta):
                m = re.search(r"_(\d{8}_\d{6})\.sqlite$", a)
                if m:
                    out.append((os.path.join(pasta, a), datetime.strptime(m.group(1), "%Y%m%d_%H%M%S")))
        return sorted(out, key=lambda x: x[1], reverse=True)

    def _fazer_copia(self, manter=None):
        """Copia a base (API de backup do SQLite: cópia íntegra mesmo com a base aberta). Base vazia não é copiada."""
        if not self.base or not self.base.nomes():
            return
        pasta = self._pasta_copias()
        os.makedirs(pasta, exist_ok=True)
        agora = datetime.now()
        destino = os.path.join(pasta, "%s_%s.sqlite" % (self.base.nome, agora.strftime("%Y%m%d_%H%M%S")))
        if os.path.exists(destino):
            return
        dst = sqlite3.connect(destino)
        try:
            with self.base.lock:
                self.base.con.backup(dst)
        finally:
            dst.close()
        for c, _ in self._copias()[self.COPIAS_MAX:]:
            if c == manter:
                continue
            try:
                os.remove(c)
            except OSError:
                pass

    def _copia_info(self):
        try:
            c = self._copias()
        except Exception:
            c = []
        if not c:
            return None
        d = c[0][1]
        dia = "hoje" if d.date() == datetime.now().date() else d.strftime("%d/%m/%Y")
        return {"quando": "%s %s" % (dia, d.strftime("%H:%M")), "n": len(c)}

    def copias_listar(self):
        """Cópias de segurança da base aberta (menu da base: restaurar)."""
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        out = []
        for c, d in self._copias():
            try:
                con = sqlite3.connect("file:%s?mode=ro" % c.replace("\\", "/"), uri=True)
                n = con.execute("SELECT COUNT(*) FROM assistidos").fetchone()[0]
                con.close()
            except Exception:
                n = None
            out.append({"arquivo": os.path.basename(c), "quando": d.strftime("%d/%m/%Y %H:%M"), "assistidos": n})
        return {"copias": out, "pasta": self._pasta_copias()}

    def copia_restaurar(self, arquivo):
        """Volta a base para uma cópia de segurança. Antes, a base atual também é copiada (a restauração pode ser desfeita)."""
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        with self._imp_lock:
            alvo = next((c for c, _ in self._copias() if os.path.basename(c) == arquivo), None)
            if not alvo:
                return {"erro": "Cópia não encontrada."}
            try:
                self._fazer_copia(manter=alvo)
            except Exception:
                logging.getLogger("rspe").exception("cópia antes de restaurar")
            src = sqlite3.connect(alvo)
            try:
                with self.base.lock:
                    src.backup(self.base.con)
            finally:
                src.close()
            r = self.listar()
            r["msg"] = "Base restaurada para a cópia de %s. A versão anterior ficou guardada entre as cópias." % \
                       datetime.strptime(re.search(r"_(\d{8}_\d{6})\.sqlite$", arquivo).group(1), "%Y%m%d_%H%M%S").strftime("%d/%m/%Y %H:%M")
            return r

    def nova_base(self, nome=None):
        """Cria base nomeada na pasta 'bases' (nome vindo da tela inicial) ou pergunta o arquivo."""
        os.makedirs(PASTA_BASES, exist_ok=True)
        nome = (nome or "").strip()
        if nome:
            seguro = "".join(ch for ch in nome if ch not in '\\/:*?"<>|').strip() or "Nova base"
            c = os.path.join(PASTA_BASES, seguro + ".sqlite")
            if os.path.exists(c):
                return {"erro": "Já existe uma base chamada '%s'. Escolha outro nome ou abra a existente." % seguro}
        else:
            c = _um(self._janela.create_file_dialog(webview.SAVE_DIALOG, directory=PASTA_BASES, save_filename="Nova base.sqlite",
                                                   file_types=("Base APTO (*.sqlite)",)))
            if not c:
                return None
            if not c.lower().endswith(".sqlite"):
                c += ".sqlite"
            if os.path.exists(c):
                os.remove(c)
        return self._trocar_base(c)

    def escolher_base(self):
        """Só o diálogo de arquivo: a tela mostra o carregamento depois que o arquivo é escolhido."""
        os.makedirs(PASTA_BASES, exist_ok=True)
        return _um(self._janela.create_file_dialog(webview.OPEN_DIALOG, directory=PASTA_BASES, file_types=("Base APTO (*.sqlite)",)))

    def abrir_base(self, caminho=None):
        if caminho and os.path.exists(caminho):
            return self._trocar_base(caminho)
        os.makedirs(PASTA_BASES, exist_ok=True)
        c = _um(self._janela.create_file_dialog(webview.OPEN_DIALOG, directory=PASTA_BASES, file_types=("Base APTO (*.sqlite)",)))
        return self._trocar_base(c) if c else None

    def fechar_base(self):
        if self.base:
            self.base.fechar()
        self.base = None
        self._modelos = []
        return self.listar()

    def recarregar_base_juridica(self):
        rg.carregar(forcar=True)
        return self.listar()

    def salvar_base_como(self):
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        c = _um(self._janela.create_file_dialog(webview.SAVE_DIALOG, directory=PASTA_BASES,
                                               save_filename=self.base.nome + ".sqlite", file_types=("Base APTO (*.sqlite)",)))
        if not c:
            return None
        if not c.lower().endswith(".sqlite"):
            c += ".sqlite"
        if os.path.abspath(c) == os.path.abspath(self.base.caminho):
            return {"msg": "A base já está salva neste arquivo."}
        self.base.con.commit()
        shutil.copyfile(self.base.caminho, c)
        r = self._trocar_base(c)
        r["msg"] = "Base salva: " + os.path.basename(c)
        return r

    def abrir_pasta_bases(self):
        os.makedirs(PASTA_BASES, exist_ok=True)
        _abrir(PASTA_BASES)
        return None

    # ---- importação em lote ----
    def importar_pdfs(self):
        if not self.base:
            return {"erro": "Crie ou abra uma base antes de importar."}
        arqs = self._janela.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True, file_types=("RSPE em PDF (*.pdf)",))
        if arqs:
            self._importar(list(arqs))
        return None

    def importar_pasta(self):
        if not self.base:
            return {"erro": "Crie ou abra uma base antes de importar."}
        d = _um(self._janela.create_file_dialog(webview.FOLDER_DIALOG))
        if not d:
            return None
        arqs = []
        for raiz, _, nomes in os.walk(d):
            arqs += [os.path.join(raiz, n) for n in nomes if n.lower().endswith(".pdf")]
        if not arqs:
            return {"erro": "Nenhum PDF encontrado na pasta."}
        self._importar(sorted(arqs))
        return None

    def _importar(self, arqs):
        threading.Thread(target=self._worker, args=(arqs,), daemon=True).start()

    def _worker(self, arqs, base=None, silencioso=False):
        with self._imp_lock:
            return self._worker_(arqs, base or self.base, silencioso)

    def _worker_(self, arqs, base, silencioso):
        novos, atualizados, duplicados, antigos, erros = 0, 0, [], [], []
        historicos = 0
        fichas_ok = []
        pend_fichas = []
        incompletos = []
        lote = []
        registro = []  # uma linha por arquivo: o que entrou, como foi lido e, se não entrou ou entrou incompleto, a causa provável

        def reg(arq, tipo, nome, proc, resultado, leitura="completa", obs=None):
            with lock:
                registro.append({"arquivo": arq, "tipo": tipo, "nome": nome or "", "proc": proc or "", "resultado": resultado,
                                 "leitura": leitura, "obs": list(obs or [])})
        total = len(arqs)
        vistos = set()
        lock = threading.Lock()
        if not silencioso:
            self._js("ui.progresso(0,%d)" % total)
        # lote grande: a leitura dos PDFs (pdfplumber, puro Python) vai para processos paralelos, um por núcleo; em lote pequeno
        # ou se os processos não subirem, threads
        ex = None
        if len(arqs) >= 20:
            try:
                ex = ProcessPoolExecutor(max_workers=max(2, min(8, (os.cpu_count() or 2) - 1)))
            except Exception:
                ex = None
        ex = ex or ThreadPoolExecutor(max_workers=min(4, os.cpu_count() or 2))
        with ex:
            futs = {ex.submit(_extrair_com_hash, a): a for a in arqs}
            for n, fut in enumerate(as_completed(futs), 1):
                a = futs[fut]
                nome_arq = os.path.basename(a)
                try:
                    try:
                        r = fut.result()
                    except BrokenProcessPool:
                        r = _extrair_com_hash(futs[fut])  # processos de leitura indisponíveis: lê aqui mesmo
                    if r.get("tipo") == "ficha_disciplinar":
                        with lock:
                            pend_fichas.append((nome_arq, r))  # vinculada no fim, com todos os RSPE do lote já na base
                        continue
                    if not r.get("processo_execucao"):
                        if r.get("nome") or r.get("_crimes") or r.get("data_geracao_rspe"):
                            raise ValueError("RSPE sem o número da execução legível (a 1ª página falta ou está ilegível) - gere o PDF de novo no SEEU")
                        raise ValueError("não parece um RSPE do SEEU nem uma Ficha Disciplinar do SIAPEN")
                    with lock:
                        chave = r["processo_execucao"]
                        if r["_hash"] in vistos:
                            duplicados.append("%s: arquivo repetido no mesmo lote" % nome_arq)
                            registro.append({"arquivo": nome_arq, "tipo": "RSPE", "nome": r.get("nome") or "", "proc": chave, "resultado": "repetido no lote",
                                             "leitura": "—", "obs": ["o mesmo arquivo veio duas vezes; só a primeira conta"]})
                            continue
                        vistos.add(r["_hash"])
                        ex_ = base.existente(chave)
                        if ex_:
                            data_ex, hash_ex = ex_
                            if hash_ex == r["_hash"] or (data_ex and data_ex == r.get("data_geracao_rspe")):
                                base.arquivar(r)
                                duplicados.append("%s: RSPE de %s já está na base (%s)" % (nome_arq, r.get("data_geracao_rspe"), r.get("nome")))
                                registro.append({"arquivo": nome_arq, "tipo": "RSPE", "nome": r.get("nome") or "", "proc": chave, "resultado": "já na base",
                                                 "leitura": "—", "obs": ["RSPE de %s, igual ao que a base já tem" % (r.get("data_geracao_rspe") or "?")]})
                                continue
                            d_ex, d_novo = rs.to_date(data_ex or ""), rs.to_date(r.get("data_geracao_rspe") or "")
                            if d_ex and d_novo and d_novo < d_ex:
                                registro.append({"arquivo": nome_arq, "tipo": "RSPE", "nome": r.get("nome") or "", "proc": chave, "resultado": "histórico",
                                                 "leitura": "—", "obs": ["RSPE de %s, mais antigo que o da base (%s): guardado no histórico" % (r.get("data_geracao_rspe"), data_ex)]})
                                if base.arquivar(r):
                                    historicos += 1
                                    antigos.append("%s: RSPE de %s é mais antigo que o da base (%s) - guardado no histórico, sem substituir o atual" % (nome_arq, r.get("data_geracao_rspe"), data_ex))
                                else:
                                    duplicados.append("%s: RSPE de %s já está no histórico (%s)" % (nome_arq, r.get("data_geracao_rspe"), r.get("nome")))
                                continue
                            if d_ex and not d_novo:
                                antigos.append("%s: RSPE sem data de geração legível; a base já tem o de %s - ignorado" % (nome_arq, data_ex))
                                registro.append({"arquivo": nome_arq, "tipo": "RSPE", "nome": r.get("nome") or "", "proc": chave, "resultado": "ignorado",
                                                 "leitura": "parcial", "obs": ["data de geração do RSPE ilegível (rodapé cortado): sem ela não dá para saber se é mais novo que o da base (%s)" % data_ex]})
                                continue
                            base.gravar(r)
                            lote.append(chave)
                            atualizados += 1
                        else:
                            base.gravar(r)
                            lote.append(chave)
                            novos += 1
                        faltam = rs.campos_faltantes(r)
                        if faltam:
                            incompletos.append("%s: %s - não foi possível ler %s" % (nome_arq, r.get("nome") or "?", ", ".join(faltam)))
                        obs, parcial = _leitura_rspe(r, faltam)
                        registro.append({"arquivo": nome_arq, "tipo": "RSPE", "nome": r.get("nome") or "", "proc": chave,
                                         "resultado": "atualizado" if ex_ else "novo", "leitura": "parcial" if parcial else "completa", "obs": obs})
                except Exception as e:
                    erros.append("%s: %s" % (nome_arq, e))
                    reg(nome_arq, "?", "", "", "não importado", "falhou", [str(e)])
                if not silencioso and (n % 3 == 0 or n == total):
                    self._js("ui.progresso(%d,%d)" % (n, total))
        if True:  # fichas do lote e fichas que esperavam o RSPE
            info = self._indice_vinculo(base)
            for nome_arq, r in pend_fichas:
                try:
                    proc, mesma_pessoa = self._vincular_ficha(r, base, info)
                    obs, parcial = rf.leitura_parcial(r)
                    if not base.gravar_ficha(r, proc, mesma_pessoa):
                        antigos.append("%s: ficha de %s impressa em %s é mais antiga que a da base - ignorada" % (nome_arq, r.get("nome"), r.get("data_impressao") or "?"))
                        reg(nome_arq, "Ficha", r.get("nome"), proc, "ignorada", "parcial" if parcial else "completa",
                            ["impressa em %s, mais antiga que a ficha da base" % (r.get("data_impressao") or "?")] + obs)
                        continue
                    reg(nome_arq, "Ficha", r.get("nome"), proc, "vinculada" if proc else "sem RSPE na base", "parcial" if parcial else "completa",
                        obs + ([] if proc else ["guardada pelo nome: vincula sozinha quando o RSPE entrar (CPF, autos ou nome sem homônimo)"]))
                    fichas_ok.append("%s: ficha de %s %s" % (nome_arq, r.get("nome"), ("vinculada a " + proc) if proc else
                                                             "SEM RSPE correspondente na base (fica guardada pelo nome; vincula sozinha quando o RSPE entrar)"))
                except Exception as e:
                    erros.append("%s: %s" % (nome_arq, e))
                    reg(nome_arq, "Ficha", r.get("nome"), "", "não importado", "falhou", [str(e)])
            # fichas de lotes anteriores que esperavam o RSPE
            try:
                nrev = self._revincular_fichas(base, info)
                if nrev:
                    fichas_ok.append("%s guardada(s) pelo nome agora vinculada(s) ao RSPE" % rs.pl(nrev, "ficha", "fichas"))
            except Exception as e:
                erros.append("revinculação de fichas: %s" % e)
        parciais = ["%s: ficha de %s - leitura parcial: %s" % (x["arquivo"], x["nome"] or "?", "; ".join(x["obs"]))
                    for x in registro if x["tipo"] == "Ficha" and x["leitura"] == "parcial"]
        avisos = incompletos + parciais + duplicados + antigos + erros + fichas_ok
        if avisos:
            with open(os.path.join(pasta_app(), "importacao_avisos.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(avisos))
        # guardado para o PDF de falhas do lote (Api.falhas_pdf)
        self._falhas_lote = {"quando": datetime.now().strftime("%d/%m/%Y %H:%M"), "erros": list(erros), "incompletos": list(incompletos),
                             "ignorados": [a for a in antigos if "ignorad" in a], "processos": list(lote), "arquivos": len(arqs),
                             "registro": sorted(registro, key=lambda x: x["arquivo"].lower())}
        resumo = {"novos": novos, "atualizados": atualizados, "historico": historicos, "duplicados": len(duplicados), "antigos": len(antigos),
                  "erros": len(erros), "fichas": len(fichas_ok), "incompletos": len(incompletos), "avisos": avisos[:60]}
        if not silencioso:
            self._js("ui.importado(%s)" % json.dumps(resumo, ensure_ascii=False))
        return resumo

    def _indice_vinculo(self, base):
        """Dados de cada assistido para vincular fichas (lido uma vez por lote: a base pode ter centenas de RSPE)."""
        with base.lock:
            rows = base.con.execute("SELECT processo, nome, dados FROM assistidos").fetchall()
        info = {}
        for p, n, d in rows:
            try:
                dd = json.loads(d) or {}
            except Exception:
                dd = {}
            info[p] = {"nome": _norm(n), "mae": _norm(dd.get("nome_mae") or ""), "cpf": re.sub(r"\D", "", dd.get("cpf") or ""),
                       "procs": {re.sub(r"\D", "", p)} | {re.sub(r"\D", "", c.get("processo_criminal") or "") for c in (dd.get("_crimes") or [])} - {""}}
        return info

    def _vincular_ficha(self, f, base=None, info=None):
        """(processo, mesma_pessoa): processo de execução da base ao qual a ficha pertence. Ordem: CPF; autos citados na ficha
        (número da execução ou de uma ação penal da execução); nome. mesma_pessoa = sem homônimo na base (a ficha guardada pelo
        nome pode ser comparada e migrada). O nome da mãe só afasta quando é claramente outro (grafia, abreviação e acento
        não contam)."""
        base = base or self.base
        if info is None:
            info = self._indice_vinculo(base)
        mae_f = _norm(f.get("nome_mae") or "")

        def mae_ok(p):
            return _mesma_mae(mae_f, info[p]["mae"])
        nn = _norm(f.get("nome", ""))
        # o RSPE também corta nomes longos: vale o nome igual ou um começo do outro (com tamanho que não confunda)
        mesmos = [p for p in info if info[p]["nome"] == nn or (min(len(nn), len(info[p]["nome"])) >= 15
                                                                and (nn.startswith(info[p]["nome"]) or info[p]["nome"].startswith(nn)))]
        mesmos_mae = [p for p in mesmos if mae_ok(p)]
        cpf = re.sub(r"\D", "", f.get("cpf") or "")
        if len(cpf) == 11:
            por_cpf = [p for p in info if info[p]["cpf"] == cpf]
            if len(por_cpf) == 1:
                return por_cpf[0], len(mesmos_mae) <= 1
        autos = {re.sub(r"\D", "", a) for a in f.get("autos", [])} - {""}
        por_autos = [p for p in info if autos & info[p]["procs"] and mae_ok(p)]
        if len(por_autos) == 1:
            return por_autos[0], len(mesmos_mae) <= 1
        # pelo nome (e pela mãe): só quando resta um único assistido (com homônimos, a ficha fica guardada pelo nome)
        return (mesmos_mae[0], True) if len(mesmos_mae) == 1 else ("", False)

    def _revincular_fichas(self, base=None, info=None):
        """Fichas guardadas pelo nome (importadas antes do RSPE, no mesmo lote ou antes) passam ao processo quando ele existe."""
        base = base or self.base
        info = info if info is not None else self._indice_vinculo(base)
        with base.lock:
            rows = base.con.execute("SELECT chave, dados FROM fichas WHERE processo=''").fetchall()
        n = 0
        for ch, d in rows:
            try:
                f = json.loads(d)
            except Exception:
                continue
            proc, mesma = self._vincular_ficha(f, base, info)
            if proc:
                with base.lock:
                    base.con.execute("DELETE FROM fichas WHERE chave=?", (ch,))
                    base.con.commit()
                base.gravar_ficha(f, proc, mesma)
                n += 1
        return n

    # ---- pasta vigiada: <pasta mãe>/<nome da base>/*.pdf entra sozinho na base de mesmo nome ----
    def vigia_info(self):
        c = self._cfg()
        pasta = c.get("pasta_vigiada") or ""
        subs = []
        if pasta and os.path.isdir(pasta):
            for n in sorted(os.listdir(pasta)):
                if os.path.isdir(os.path.join(pasta, n)):
                    if n.strip().upper() in PASTAS_TIPO:
                        subs += ["%s / %s" % (n, m) for m in sorted(os.listdir(os.path.join(pasta, n))) if os.path.isdir(os.path.join(pasta, n, m))]
                    else:
                        subs.append(n)
        bases = sorted(os.path.splitext(n)[0] for n in os.listdir(PASTA_BASES) if n.lower().endswith(".sqlite")) if os.path.isdir(PASTA_BASES) else []
        return {"pasta": pasta, "ativa": bool(c.get("vigiar") and pasta and os.path.isdir(pasta)), "pastas": subs, "bases": bases,
                "ultima": self._vigia_ultima, "intervalo": VIGIA_INTERVALO}

    def vigia_escolher(self):
        d = _um(self._janela.create_file_dialog(webview.FOLDER_DIALOG))
        if not d:
            return None
        self._cfg_gravar(pasta_vigiada=d, vigiar=True)
        self._vigia_iniciar()
        r = self.vigia_info()
        r["msg"] = "Pasta vigiada: %s" % d
        return r

    def vigia_ativar(self, ativo):
        self._cfg_gravar(vigiar=bool(ativo))
        if ativo:
            self._vigia_iniciar()
        r = self.vigia_info()
        r["msg"] = "Pasta vigiada %s." % ("ativada" if ativo else "desativada")
        return r

    def vigia_criar_pastas(self):
        """Cria na pasta mãe uma subpasta para cada base existente."""
        pasta = self._cfg().get("pasta_vigiada") or ""
        if not pasta or not os.path.isdir(pasta):
            return {"erro": "Escolha a pasta mãe primeiro."}
        # se a pasta mãe já separa por tipo (RSPE\, FD\), cria dentro de cada uma; senão, direto na pasta mãe
        tipos = [os.path.join(pasta, x) for x in os.listdir(pasta)
                 if x.strip().upper() in PASTAS_TIPO and os.path.isdir(os.path.join(pasta, x))] or [pasta]
        n = 0
        for b in self.vigia_info()["bases"]:
            for t in tipos:
                alvo = os.path.join(t, b)
                if not os.path.isdir(alvo):
                    os.makedirs(alvo, exist_ok=True)
                    n += 1
        r = self.vigia_info()
        r["msg"] = ("%s." % rs.pl(n, "pasta criada", "pastas criadas")) if n else "Todas as bases já têm pasta."
        return r

    def vigia_agora(self):
        threading.Thread(target=self._vigia_varrer, kwargs={"imediato": True}, daemon=True).start()
        return {"msg": "Verificando a pasta vigiada…"}

    def vigia_abrir(self):
        pasta = self._cfg().get("pasta_vigiada") or ""
        if pasta and os.path.isdir(pasta):
            _abrir(pasta)
        return None

    def _vigia_iniciar(self):
        if self._vigia_thread and self._vigia_thread.is_alive():
            return
        self._vigia_thread = threading.Thread(target=self._vigia_loop, daemon=True)
        self._vigia_thread.start()

    def _vigia_loop(self):
        while True:
            try:
                c = self._cfg()
                if c.get("vigiar") and c.get("pasta_vigiada") and os.path.isdir(c["pasta_vigiada"]):
                    self._vigia_varrer()
            except Exception as e:
                logging.warning("pasta vigiada: %s", e)
            time.sleep(VIGIA_INTERVALO)

    def _vigia_varrer(self, imediato=False):
        c = self._cfg()
        raiz = c.get("pasta_vigiada") or ""
        if not raiz or not os.path.isdir(raiz):
            return
        try:
            with open(VIGIA_ESTADO, encoding="utf-8") as f:
                estado = json.load(f)
        except Exception:
            estado = {}
        pend, soltos = {}, 0
        agora = time.time()
        for dirpath, _, nomes in os.walk(raiz):
            for n in nomes:
                if not n.lower().endswith(".pdf"):
                    continue
                p = os.path.join(dirpath, n)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                sig = "%d:%d" % (st.st_size, int(st.st_mtime))
                if estado.get(p) == sig:
                    continue
                # download ainda em andamento: só entra quando o tamanho parar de mudar
                if not imediato and (self._vigia_tam.get(p) != st.st_size or agora - st.st_mtime < 5):
                    self._vigia_tam[p] = st.st_size
                    continue
                b = base_da_pasta(raiz, p)
                if not b:
                    soltos += 1
                    continue
                pend.setdefault(b, []).append((p, sig))
        for b, itens in sorted(pend.items()):
            os.makedirs(PASTA_BASES, exist_ok=True)
            caminho = os.path.join(PASTA_BASES, b + ".sqlite")
            nova = not os.path.exists(caminho)
            aberta = bool(self.base) and os.path.normcase(os.path.abspath(self.base.caminho)) == os.path.normcase(os.path.abspath(caminho))
            base = self.base if aberta else Base(caminho)
            try:
                res = self._worker([p for p, _ in itens], base=base, silencioso=True)
            finally:
                if not aberta:
                    base.fechar()
            for p, sig in itens:
                estado[p] = sig
            try:
                with open(VIGIA_ESTADO, "w", encoding="utf-8") as f:
                    json.dump(estado, f, ensure_ascii=False)
            except Exception:
                pass
            partes = []
            for k, rot in (("novos", ("novo", "novos")), ("atualizados", ("atualizado", "atualizados")), ("fichas", ("ficha", "fichas")), ("duplicados", ("já na base", "já na base")), ("erros", ("com erro", "com erro"))):
                if res.get(k):
                    partes.append("%d %s" % (res[k], rot[0] if res[k] == 1 else rot[1]))
            self._vigia_ultima = "%s · %s: %s" % (datetime.now().strftime("%d/%m %H:%M"), b, ", ".join(partes) or "nada novo")
            self._js("ui.toast(%s)" % json.dumps("Pasta vigiada · base %s%s: %s" % (b, " (criada agora)" if nova else "", ", ".join(partes) or "nada novo"), ensure_ascii=False))
            if aberta:
                self._js("api('listar')")
        if soltos and imediato:
            self._js("ui.toast(%s)" % json.dumps("%s na pasta mãe: %s. Coloque na pasta da base." % (rs.pl(soltos, "PDF solto", "PDFs soltos"), "ignorado" if soltos == 1 else "ignorados"), ensure_ascii=False))

    # ---- petições a partir de modelos .docx ----
    def listar_modelos(self):
        rpet.gerar_modelo_exemplo(pasta_app(), recurso("modelos_padrao"))
        return {"modelos": rpet.listar(pasta_app()), "defensores": _ler_defensores()}

    def modelo_restaurar_padrao(self):
        n = rpet.instalar_modelos_padrao(pasta_app(), recurso("modelos_padrao"))
        return {"msg": "%s (os existentes não foram alterados)." % rs.pl(n, "modelo da unidade restaurado", "modelos da unidade restaurados")}

    # ---- defensores ----
    def defensores_listar(self):
        return _ler_defensores()

    def defensores_salvar(self, lista):
        try:
            lista = [{"nome": (d.get("nome") or "").strip(), "cargo": (d.get("cargo") or "Defensor Público").strip(),
                      "matricula": (d.get("matricula") or "").strip(), "email": (d.get("email") or "").strip(),
                      "padrao": bool(d.get("padrao"))} for d in (lista or []) if (d.get("nome") or "").strip()]
            with open(DEFENSORES, "w", encoding="utf-8") as f:
                json.dump(lista, f, ensure_ascii=False, indent=1)
            return {"msg": "%s." % rs.pl(len(lista), "defensor salvo", "defensores salvos"), "lista": lista}
        except Exception as e:
            return {"erro": "Não foi possível salvar: %s" % e}

    def modelos_info(self):
        rpet.gerar_modelo_exemplo(pasta_app(), recurso("modelos_padrao"))
        pasta = rpet.pasta_modelos(pasta_app())
        out = []
        for n in rpet.listar(pasta_app()):
            c = os.path.join(pasta, n)
            try:
                usados = rpet.campos_do_modelo(c)
            except Exception:
                usados = []
            conhecidos = {k for k, _ in rpet.CAMPOS}
            out.append({"nome": n, "modificado": datetime.fromtimestamp(os.path.getmtime(c)).strftime("%d/%m/%Y %H:%M"),
                        "campos": len(usados), "desconhecidos": sorted(u for u in usados if u not in conhecidos)})
        return {"pasta": pasta, "modelos": out}

    def modelo_campos(self):
        return [list(x) for x in rpet.CAMPOS]

    def modelo_adicionar(self):
        arqs = self._janela.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True, file_types=("Modelo Word (*.docx)",))
        if not arqs:
            return None
        pasta = rpet.pasta_modelos(pasta_app())
        n = 0
        for a in arqs:
            if a.lower().endswith(".docx"):
                shutil.copy2(a, os.path.join(pasta, os.path.basename(a)))
                n += 1
        return {"msg": "%s." % rs.pl(n, "modelo adicionado", "modelos adicionados")}

    def modelo_substituir(self, nome):
        a = _um(self._janela.create_file_dialog(webview.OPEN_DIALOG, file_types=("Modelo Word (*.docx)",)))
        if not a:
            return None
        shutil.copy2(a, os.path.join(rpet.pasta_modelos(pasta_app()), nome))
        return {"msg": "Modelo substituído: %s" % nome}

    def modelo_renomear(self, nome, novo):
        pasta = rpet.pasta_modelos(pasta_app())
        novo = re.sub(r"[\\/:*?\"<>|]", "", novo).strip()
        if not novo:
            return {"erro": "Nome inválido."}
        if not novo.lower().endswith(".docx"):
            novo += ".docx"
        try:
            os.rename(os.path.join(pasta, nome), os.path.join(pasta, novo))
        except Exception as e:
            return {"erro": "Não foi possível renomear: %s" % e}
        return {"msg": "Renomeado para %s" % novo}

    def modelo_excluir(self, nome):
        try:
            os.remove(os.path.join(rpet.pasta_modelos(pasta_app()), nome))
        except Exception as e:
            return {"erro": "Não foi possível excluir: %s" % e}
        return {"msg": "Modelo excluído."}

    def modelo_novo(self, nome):
        pasta = rpet.pasta_modelos(pasta_app())
        nome = re.sub(r"[\\/:*?\"<>|]", "", nome).strip()
        if not nome:
            return {"erro": "Nome inválido."}
        c = os.path.join(pasta, nome + ".docx")
        if os.path.exists(c):
            return {"erro": "Já existe um modelo com esse nome."}
        try:
            rpet.criar_modelo_branco(c)
        except Exception as e:
            return {"erro": "Não foi possível criar: %s" % e}
        _abrir(c)
        return {"msg": "Modelo criado e aberto no Word: %s" % nome}

    def modelo_abrir(self, nome):
        _abrir(os.path.join(rpet.pasta_modelos(pasta_app()), nome))
        return {"msg": "Abrindo no Word. Salve e feche para usar."}

    def modelo_pasta(self):
        _abrir(rpet.pasta_modelos(pasta_app()))
        return None

    def gerar_peticao(self, chave, modelo, pdf=True, defensor_idx=None):
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        m = next((x for x in self._modelos if x["id"] == chave), None)
        if not m:
            return {"erro": "Assistido não encontrado."}
        if m.get("erro"):
            return {"erro": "Registro não analisado (%s): conferir o PDF antes de gerar a petição." % m["erro"]}
        caminho_modelo = os.path.join(rpet.pasta_modelos(pasta_app()), modelo)
        if not os.path.exists(caminho_modelo):
            return {"erro": "Modelo não encontrado: %s" % modelo}
        defs = _ler_defensores()
        defensor = None
        try:
            if defensor_idx is not None and 0 <= int(defensor_idx) < len(defs):
                defensor = defs[int(defensor_idx)]
        except Exception:
            defensor = None
        if defensor is None:
            defensor = next((d for d in defs if d.get("padrao")), defs[0] if defs else None)
        dados = rpet.campos(m, m["_bruto"], self.base.nome, defensor)
        nome = "%s - %s.docx" % (os.path.splitext(modelo)[0], re.sub(r"[^\w\s-]", "", m["nome"]).strip()[:60])
        c = _um(self._janela.create_file_dialog(webview.SAVE_DIALOG, save_filename=nome, file_types=("Word (*.docx)",)))
        if not c:
            return None
        if not c.lower().endswith(".docx"):
            c += ".docx"
        ok, aviso = rpet.preencher(caminho_modelo, c, dados)
        if not ok:
            return {"erro": "Falha ao preencher o modelo: %s" % aviso}
        out = {"caminho": c, "aviso": aviso}
        if pdf:
            p, av = rpet.para_pdf(c)
            out["pdf"] = p
            if av:
                out["aviso"] = (aviso + " · " if aviso else "") + av
        _abrir(out.get("pdf") or c)
        return out

    def remover_ficha(self, chave):
        if not self.base:
            return None
        m = next((x for x in self._modelos if x.get("id") == chave), None)
        self.base.remover_ficha(chave, _norm(m.get("nome", "")) if m else None)
        return self.listar()

    # ---- exportação ----
    def exportar(self, formato, abas, ids):
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        modelos = [m for m in self._modelos if m["id"] in set(ids)]
        if not modelos:
            return {"erro": "Nada para exportar."}
        sufixo = rv.ABA_POR_ID[abas[0]]["titulo"].split(" /")[0] if len(abas) == 1 and abas[0] in rv.ABA_POR_ID else "abas"
        nome = "%s - %s %s.%s" % (self.base.nome, sufixo, datetime.now().strftime("%d-%m-%Y"), formato)
        c = _um(self._janela.create_file_dialog(webview.SAVE_DIALOG, save_filename=nome,
                                               file_types=("Excel (*.xlsx)",) if formato == "xlsx" else ("PDF (*.pdf)",)))
        if not c:
            return None
        if not c.lower().endswith("." + formato):
            c += "." + formato
        try:
            if formato == "xlsx":
                rx.exportar_xlsx(modelos, c, abas)
            else:
                rx.exportar_pdf(modelos, c, self.base.nome, abas)
        except Exception as e:
            return {"erro": "Falha ao exportar: %s" % e}
        _abrir(c)
        return {"caminho": c}


    def providencias_xlsx(self, titulo, linhas):
        """Salva em Excel o relatório de providências montado na tela (mês escolhido)."""
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        if not linhas:
            return {"erro": "Nenhuma providência no período."}
        nome = "%s - %s.xlsx" % (self.base.nome, re.sub(r"[^\w\s-]", "", titulo).strip()[:60])
        c = _um(self._janela.create_file_dialog(webview.SAVE_DIALOG, save_filename=nome, file_types=("Excel (*.xlsx)",)))
        if not c:
            return None
        if not c.lower().endswith(".xlsx"):
            c += ".xlsx"
        try:
            rx.exportar_providencias(linhas, c, titulo)
        except Exception as e:
            return {"erro": "Falha ao salvar: %s" % e}
        _abrir(c)
        return {"caminho": c, "msg": "Relatório salvo."}

    def _falhas_dados(self):
        """Falhas do último lote importado: arquivos não importados, campos não lidos e falhas de análise/ficha dos assistidos do lote."""
        F = getattr(self, "_falhas_lote", None)
        if not F:
            return None
        procs = set(F["processos"])
        pessoas, faltam = [], []
        for m in (self._modelos or []) + (getattr(self, "_ocultos", None) or []):
            if m.get("id") not in procs:
                continue
            its = [i for i in m.get("aud_itens") or [] if not i.get("baixado") and not i.get("auto_baixa")]
            # dado não lido: uma linha por assistido, com todos os campos (a causa vai uma vez só no PDF)
            campos = [re.sub(r"^Faltam dados:\s*|\s*(não lido do RSPE)?\s*-\s*informar$", "", i.get("titulo") or "")
                      for i in its if (i.get("tipo") or "").startswith("faltam-dados") or (i.get("titulo") or "").startswith("Faltam dados")]
            if campos:
                faltam.append({"nome": m.get("nome", ""), "proc": m.get("proc", ""), "campos": campos})
            falhas = [i for i in its if (i.get("tipo") or "").startswith("falha")]
            if falhas:
                pessoas.append({"nome": m.get("nome", ""), "proc": m.get("proc", ""),
                                "itens": [(i.get("titulo") or "", re.sub(r"<[^>]+>", "", i.get("detalhe") or "")) for i in falhas]})
        # arquivo de cada assistido com dado não lido (lista da importação), pelo nome
        arq = {}
        for e in F.get("incompletos") or []:
            a, _, resto = e.partition(": ")
            arq.setdefault(_norm(resto.split(" - não foi possível ler ")[0]), a)
        for x in faltam:
            x["arquivo"] = arq.get(_norm(x["nome"]), "")
        return dict(F, pessoas=pessoas, faltam=faltam)

    def falhas_tem(self):
        """Há lote importado nesta sessão? (o registro da importação em PDF vale para todo lote, com ou sem falha)"""
        return bool(getattr(self, "_falhas_lote", None))

    def falhas_pdf(self):
        """PDF do registro do último lote importado: resumo, falhas com a causa e o registro de cada arquivo."""
        d = self._falhas_dados()
        if not d:
            return {"erro": "Nenhuma importação nesta sessão."}
        nome = "%s - registro da importação %s.pdf" % (self.base.nome, datetime.now().strftime("%Y-%m-%d %H%M"))
        c = _um(self._janela.create_file_dialog(webview.SAVE_DIALOG, save_filename=nome, file_types=("PDF (*.pdf)",)))
        if not c:
            return None
        if not c.lower().endswith(".pdf"):
            c += ".pdf"
        try:
            rrel.relatorio_falhas(d, c, self.base.nome)
        except Exception as e:
            return {"erro": "Falha ao gerar o PDF: %s" % e}
        _abrir(c)
        return {"caminho": c, "msg": "PDF salvo."}

    def providencias_pdf(self, titulo, linhas, todas, mes):
        """Salva em PDF o relatório de providências (totais, gráficos e lista)."""
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        nome = "%s - %s.pdf" % (self.base.nome, re.sub(r"[^\w\s-]", "", titulo).strip()[:60])
        c = _um(self._janela.create_file_dialog(webview.SAVE_DIALOG, save_filename=nome, file_types=("PDF (*.pdf)",)))
        if not c:
            return None
        if not c.lower().endswith(".pdf"):
            c += ".pdf"
        try:
            rrel.relatorio_providencias(linhas or [], todas or [], mes or "", c, titulo, self.base.nome)
        except Exception as e:
            return {"erro": "Falha ao gerar o PDF: %s" % e}
        _abrir(c)
        return {"caminho": c, "msg": "PDF salvo."}

    # ---- relatórios (PDF) ----
    def relatorios(self, ids, individual, geral, planilha, nominal, ids_individual=None, remicao=False):
        """Gera, numa pasta escolhida, a subpasta 'Relatorios <data hora>' com o relatório geral, os individuais e a planilha."""
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        modelos = [m for m in self._modelos if m["id"] in set(ids)]
        if not modelos:
            return {"erro": "Nada para gerar."}
        if not (individual or geral or planilha or remicao):
            return {"erro": "Marque ao menos uma saída."}
        pasta = _um(self._janela.create_file_dialog(webview.FOLDER_DIALOG))
        if not pasta:
            return None
        try:
            sel = set(ids_individual) if ids_individual else None
            individuais = [m for m in modelos if m["id"] in sel] if sel is not None else modelos
            destino, n, erros = rrel.gerar(modelos, pasta, self.base.nome, individual=individual, geral=geral, nominal=nominal,
                                           individuais=individuais, remicao=remicao)
            if planilha:
                rx.exportar_xlsx(modelos, os.path.join(destino, "%s - planilha.xlsx" % self.base.nome),
                                 ["geral", "prog", "liv", "ind", "presc", "ext", "fd", "aud", "completo"])
        except Exception as e:
            return {"erro": "Falha ao gerar relatórios: %s" % e}
        _abrir(destino)
        msg = "Relatórios em %s" % destino + (" · %s" % rs.pl(n, "individual", "individuais") if individual else "")
        if erros:
            msg += " · %s: %s" % (rs.pl(len(erros), "falha", "falhas"), "; ".join(erros[:3]))
        return {"caminho": destino, "msg": msg}

    def relatorio_um(self, id_):
        """Relatório individual de um assistido (botão na ficha)."""
        m = next((x for x in self._modelos if x["id"] == id_), None)
        if not m:
            return {"erro": "Assistido não encontrado."}
        c = _um(self._janela.create_file_dialog(webview.SAVE_DIALOG, save_filename=rrel.nome_arquivo(m), file_types=("PDF (*.pdf)",)))
        if not c:
            return None
        if not c.lower().endswith(".pdf"):
            c += ".pdf"
        try:
            rrel.relatorio_individual(m, c, self.base.nome)
        except Exception as e:
            return {"erro": "Falha ao gerar o relatório: %s" % e}
        _abrir(c)
        return {"caminho": c}


DEFENSORES = os.path.join(pasta_app(), "defensores.json")


def _ler_defensores():
    try:
        with open(DEFENSORES, encoding="utf-8") as f:
            lst = json.load(f)
        return lst if isinstance(lst, list) else []
    except Exception:
        return []


def _montar_modelo(r, ctx):
    """Modelo de um assistido (todas as abas) a partir do registro gravado e das tabelas auxiliares. Função do módulo (sem
    a base aberta), para montar a base grande em processos paralelos; devolve (modelo, baixas a migrar)."""
    migrar = []
    baixas, fichas, manuais, ajustes = ctx["baixas"], ctx["fichas"], ctx["manuais"], ctx["ajustes"]
    dmanuais, peds, _homonimos = ctx["dmanuais"], ctx["peds"], ctx["homonimos"]
    # dados que o RSPE não trouxe: informados na Auditoria ou, para a data de nascimento, lidos da ficha disciplinar
    _ch0 = r.get("processo_execucao") or r.get("arquivo")
    _dm = dmanuais.get(_ch0, {})
    r["_outras_condenacoes"] = (ctx.get("outras_cond") or {}).get(_ch0, [])
    r["_outras_execucoes"] = (ctx.get("outras_exec") or {}).get(_ch0, [])
    r["_homonimos_base"] = (ctx.get("homon_det") or {}).get(_ch0, [])
    _n0 = _norm(r.get("nome", ""))
    _f0 = fichas.get(_ch0) or (fichas.get("nome:" + _n0) if _homonimos.get(_n0, 0) == 1 else None)
    if _f0 and _f0 is not fichas.get(_ch0) and not _mesma_mae(_norm(_f0.get("nome_mae") or ""), _norm(r.get("nome_mae") or "")) \
            and not _ficha_prova(_f0, r):
        _f0 = None  # ficha de homônimo: a mãe não confere (nem CPF, autos ou nascimento)
    if not _f0:
        # ficha vinculada a outra execução da mesma pessoa (mesmo CPF): a ficha é da pessoa, vale para a execução em curso
        _fo = [fichas[o] for o in (ctx.get("outros_procs") or {}).get(_ch0, []) if fichas.get(o)]
        _f0 = max(_fo, key=lambda f: rs.to_date(f.get("data_impressao") or "") or date.min) if _fo else None
    if not _f0:
        # ficha guardada pelo nome com grafia diferente ou bloqueada por homônimo: só com CPF, autos ou nascimento conferindo
        _f0 = fichas.get("nome:~alt") or _ficha_alternativa(fichas, r)
    # fichas desvinculadas pelo operador (Auditoria): não voltam a este assistido, nem como candidatas
    _rec = set(((_dm.get("ficha_recusada") or {}).get("valor") or "").split("\n")) - {""}
    if _f0 and rf.assinatura_ficha(_f0) in _rec:
        _f0 = None
    r["_ficha_recusada"] = "/".join((_dm["ficha_recusada"]["data"] or "")[:10].split("-")[::-1]) if _rec else ""
    r["_fichas_cand"] = [] if _f0 else [c for c in (fichas["~cands"] if "~cands" in fichas else _fichas_candidatas(fichas, r))
                                        if rf.assinatura_ficha({"nome": c["nome"], "cpf": c["cpf"], "data_nascimento": c["nasc"]}) not in _rec]
    r.pop("_nasc_fonte", None); r.pop("_nasc_data", None)
    if _dm.get("data_nascimento"):
        if r.get("data_nascimento") != _dm["data_nascimento"]["valor"]:
            r["_nasc_rspe"] = r.get("data_nascimento") or ""
        r["data_nascimento"] = _dm["data_nascimento"]["valor"]
        r["_nasc_data"] = "/".join(_dm["data_nascimento"]["data"][:10].split("-")[::-1])
        r["_nasc_fonte"] = "informada pelo operador"
    elif not r.get("data_nascimento") and _f0 and (_f0.get("data_nascimento") or ""):
        r["data_nascimento"] = _f0["data_nascimento"]
        r["_nasc_fonte"] = "lida da ficha disciplinar do SIAPEN"
        r["_nasc_data"] = ""
    # RSPE x ficha: retomada do cumprimento omitida no RSPE é lançada pela ficha; divergência vira alerta
    try:
        rf.reconciliar_eventos(r, _f0)
    except Exception:
        logging.getLogger("rspe").exception("reconciliação com a ficha %s", _ch0)
    # faltas graves da ficha disciplinar que o RSPE não traz: entram como falta a apurar
    try:
        rs.faltas_da_ficha(r, _f0, rv.HOJE)
        rs.explicar_indicios_ficha(r, _f0, rv.HOJE)  # regressão/perda/pendente: a ficha explica?
    except Exception:
        logging.getLogger("rspe").exception("faltas da ficha %s", _ch0)
    # sexo para a concordância dos textos (SAP, fundamentações): o informado pelo operador; senão o cadastro da ficha
    # (sexo biológico ou unidade feminina). Sem isso, o texto fica neutro; o nome não serve de indício
    _sx = ((_dm.get("sexo") or {}).get("valor") or "")
    if not _sx and _f0:
        _sx = _f0.get("sexo") or ("F" if "FEMININ" in rs._sem_acento(_f0.get("unidade") or "").upper() else "")
    r["_sexo"] = _sx
    r["_sexo_fonte"] = "operador" if (_dm.get("sexo") or {}).get("valor") else ("ficha" if _sx else "")
    # data-base corrigida pelo operador ("dd/mm/aaaa|motivo"): refaz a previsão de progressão em todas as abas
    r.pop("_db_manual", None)
    if (_dm.get("data_base") or {}).get("valor"):
        r["_db_manual"] = _dm["data_base"]["valor"]
    # decisões do operador sobre indícios de falta (fuga, pendente, perda sem falta): valem em todas as abas
    rs.aplicar_decisoes_falta(r, {k.split("|", 1)[1]: v["valor"] for k, v in _dm.items() if k.startswith("falta|")})
    for _c in r.get("_crimes", []):
        _c.pop("_pena_max_inf", None)
        _v = _dm.get("pena_max|" + rs.chave_pena_max(_c))
        if _v:
            _c["_pena_max_inf"] = rs.pena_livre(_v["valor"])
            _c["_pena_max_data"] = "/".join(_v["data"][:10].split("-")[::-1])
    # dados do cabeçalho que o RSPE não trouxe, informados pelo operador na Auditoria ("Faltam dados"): entram antes da análise
    r.pop("_manuais", None)
    for _k, _v in _dm.items():
        if _k.startswith("rspe|") and _k[5:] in rs.CAMPOS_MANUAIS and _v.get("valor") and not r.get(_k[5:]):
            r[_k[5:]] = rs.valor_manual(_k[5:], _v["valor"])
            r.setdefault("_manuais", {})[_k[5:]] = {"valor": r[_k[5:]], "data": "/".join(_v["data"][:10].split("-")[::-1])}
    try:
        imp = r.get("importado_em")
        r = rs.reprocessar(r)  # análise refeita com as regras desta versão (a leitura do PDF fica como foi gravada)
        r["importado_em"] = imp
    except Exception:
        pass
    ch = r.get("processo_execucao") or r.get("arquivo")
    r["_presc_ajustes"] = ajustes.get(ch, {})  # dados de prescrição preenchidos/corrigidos pelo operador (só em memória)
    _nn = _norm(r.get("nome", ""))
    ficha = _f0 if ch == _ch0 else (fichas.get(ch) or (fichas.get("nome:" + _nn) if _homonimos.get(_nn, 0) == 1 else None))
    # um registro com dado ilegível não pode derrubar a base: tenta sem a ficha e, se ainda falhar, mostra o
    # registro com o aviso da falha
    try:
        m = rv.modelo(r, baixas.get(ch, {}), ficha, manuais.get(ch, []))
    except Exception as e:
        logging.getLogger("rspe").exception("falha ao montar %s", ch)
        try:
            # o aviso entra antes da contagem: conta no resumo e na cor, e a baixa dele fica gravada
            m = rv.modelo(r, baixas.get(ch, {}), None, manuais.get(ch, []),
                          extras=[rv.item_falha("Ficha disciplinar ignorada: falha ao ler (%s)" % e, "falha-ficha")])
        except Exception as e2:
            m = rv.modelo_erro(r, e2, baixas.get(ch, {}))
    m["sexo"], m["sexo_fonte"] = r.get("_sexo") or "", r.get("_sexo_fonte") or ""
    # baixas gravadas pelo título (até a 6.15.11): passam para a chave estável (tipo do ponto + crime)
    for it in m.get("aud_itens") or []:
        if it.get("migrar_de"):
            migrar.append((ch, it["migrar_de"], it["chave"]))
    m["pedidos"] = peds.get(ch, {})  # pedidos já feitos, por aba (coluna "Pedido")
    m["hist_n"] = ctx["hist_n"].get(ch, 1)
    m["fixado"] = ch in ctx["fixados"]
    try:
        m["dec"] = rv.json_seguro(rd.avaliar(m.get("_final") or r, rv.HOJE))  # aba Indulto: todos os decretos desde o início do cumprimento
    except Exception:
        logging.getLogger("rspe").exception("decretos %s", ch)
        m["dec"] = {"inicio": "", "decretos": []}  # RSPEs guardados no histórico (botão "Histórico · N" da aba Geral)
    try:
        m["faltas_itens"] = rs.faltas_editaveis(r.get("_incidentes", []), r.get("_eventos", []), rv.HOJE)
    except Exception:
        m["faltas_itens"] = []
    m["_bruto"] = m.pop("_final", None) or r
    return m, migrar


# campos de cada crime da prescrição que a lista usa (colunas, cores, "Calcular"); o resto vem com o registro completo
_PRESC_LEVE = {"ppe_termo_txt", "crime", "rotulo", "proc_crim", "pena", "fato", "denuncia", "sentenca", "transito", "transito_mp", "acordao", "modalidade",
               "ppe_status", "ppe_cor", "retro_status", "retro_cor", "prazo_ppe", "prazo_ppp", "ppe_termo", "ppe_previsao", "ppe_dias",
               "chave_ajuste", "ajustado"}


def _leve(j):
    """Registro para a lista: sem os textos da prescrição (memória, linha do tempo, fundamentação) e sem os itens da auditoria."""
    out = dict(j)
    out["_leve"] = True
    out["aud_itens"] = []
    if isinstance(j.get("dec"), dict):
        out["dec"] = dict(j["dec"], decretos=[{k: v for k, v in x.items() if k != "detalhe"} for x in (j["dec"].get("decretos") or [])])
    out["presc_linhas"] = [dict({k: v for k, v in L.items() if k in _PRESC_LEVE},
                                ppe_saldos=[{"evasao": S.get("evasao"), "saldo_origem": S.get("saldo_origem")} for S in (L.get("ppe_saldos") or [])])
                           for L in (j.get("presc_linhas") or [])]
    return out


def _pessoa_chave(r):
    """Mesma pessoa em RSPEs diferentes: CPF; sem CPF, nome + mãe."""
    cpf = re.sub(r"\D", "", r.get("cpf") or "")
    if len(cpf) == 11 and cpf != "0" * 11:
        return "cpf:" + cpf
    mae = _norm(r.get("nome_mae") or "")
    return ("nm:%s|%s" % (_norm(r.get("nome", "")), mae)) if mae and r.get("nome") else None


def _chaves_pessoa(r):
    """Identificadores da pessoa num RSPE: CPF (11 dígitos), RJI (13 dígitos, quando o SEEU imprime o registro judicial no lugar
    do CPF), nome + nascimento e nome + mãe (início do nome, porque o RSPE às vezes corta o nome da mãe)."""
    ks = ["man:" + r["_pessoa_man"]] if r.get("_pessoa_man") else []
    doc = re.sub(r"\D", "", r.get("cpf") or "")
    if len(doc) == 11 and doc != "0" * 11:
        ks.append("cpf:" + doc)
    elif len(doc) == 13:
        ks.append("rji:" + doc)
    nome = _norm(r.get("nome") or "")
    if nome:
        if rs.to_date(r.get("data_nascimento") or ""):
            ks.append("nn:%s|%s" % (nome, r["data_nascimento"]))
        mae = _norm(r.get("nome_mae") or "")
        if len(mae) >= 8:
            ks.append("nm:%s|%s" % (nome, mae[:18]))
    return ks


def _grupos_pessoa(regs):
    """Agrupa os RSPEs da mesma pessoa: basta um identificador em comum (o mesmo CPF; ou o mesmo nome com a mesma data de
    nascimento ou a mesma mãe) - um RSPE com CPF e outro com RJI, da mesma pessoa, ficam juntos. Devolve listas com 2 ou mais."""
    regs = list(regs)
    pai = list(range(len(regs)))

    def raiz(i):
        while pai[i] != i:
            pai[i] = pai[pai[i]]
            i = pai[i]
        return i
    vistos = {}
    for i, r in enumerate(regs):
        for k in _chaves_pessoa(r):
            if k in vistos:
                pai[raiz(i)] = raiz(vistos[k])
            else:
                vistos[k] = i
    g = {}
    for i, r in enumerate(regs):
        g.setdefault(raiz(i), []).append(r)
    return [v for v in g.values() if len(v) > 1]


def _homonimos_det(regs):
    """{processo: outros assistidos com o mesmo nome que o programa trata como pessoas diferentes} - para o aviso da Auditoria,
    com os dados lado a lado e a opção de marcar como a mesma pessoa."""
    regs = list(regs)
    gid = {}
    for n, g in enumerate(_grupos_pessoa(regs)):
        for r in g:
            gid[id(r)] = n
    por_nome = {}
    for r in regs:
        por_nome.setdefault(_norm(r.get("nome") or ""), []).append(r)
    out = {}
    for nome, rr in por_nome.items():
        if not nome or len(rr) < 2:
            continue
        for r in rr:
            outros = [o for o in rr if o is not r and (gid.get(id(o), "o%d" % id(o)) != gid.get(id(r), "r%d" % id(r)))]
            pessoas = {}
            for o in outros:  # uma entrada por pessoa (as execuções dela juntas, a principal primeiro)
                pessoas.setdefault(gid.get(id(o), "o%d" % id(o)), []).append(o)
            if pessoas:
                out[r.get("processo_execucao") or r.get("arquivo")] = []
                for g in pessoas.values():
                    o = max(g, key=_rank_exec)
                    out[r.get("processo_execucao") or r.get("arquivo")].append(
                        {"processo": o.get("processo_execucao") or "", "cpf": o.get("cpf") or "", "nasc": o.get("data_nascimento") or "",
                         "mae": o.get("nome_mae") or "", "vara": o.get("vara") or "", "status": o.get("status_execucao") or "",
                         "outros": [x.get("processo_execucao") or "" for x in g if x is not o]})
    return out


def _outras_cond(regs):
    """{processo: condenações das outras execuções da mesma pessoa} - a condenação anterior que fundamenta a reincidência pode
    estar noutro RSPE (execução arquivada ou extinta)."""
    out = {}
    for g in _grupos_pessoa(regs):
        for r in g:
            ch = r.get("processo_execucao") or r.get("arquivo")
            out[ch] = [dict(c, _execucao=o.get("processo_execucao") or "") for o in g if o is not r for c in (o.get("_crimes") or [])]
    return out


def _outros_procs(regs):
    """{processo: processos das outras execuções da mesma pessoa}."""
    grupos = [[r.get("processo_execucao") or r.get("arquivo") for r in g] for g in _grupos_pessoa(regs)]
    return {p: [o for o in g if o != p] for g in grupos for p in g}


def _exec_encerrada(b):
    st = _norm(b.get("status_execucao") or "").upper()
    return bool(rv.execucao_extinta(b)) or "ARQUIV" in st or "BAIXAD" in st


def _rank_exec(b):
    """Execução principal da pessoa: não encerrada > com condenação cadastrada > com pena calculada > mais eventos e incidentes no
    SEEU > RSPE mais recente."""
    ativos = [c for c in b.get("_crimes") or [] if not (c.get("extinto") or "").upper().startswith("S")]
    mov = len([e for e in b.get("_eventos") or [] if not e.get("_ficha")]) + len([i for i in b.get("_incidentes") or [] if not i.get("_ficha")])
    return (not _exec_encerrada(b), bool(ativos), bool(rs.pena_para_dias(b.get("pena_total"))), mov,
            rs.to_date(b.get("data_geracao_rspe") or "") or date.min)


def _outras_exec(regs):
    """{processo: resumo das outras execuções da mesma pessoa} - para o aviso da Auditoria na execução que fica na lista."""
    out = {}
    for g in _grupos_pessoa(regs):
        for r in g:
            out[r.get("processo_execucao") or r.get("arquivo")] = [
                {"processo": o.get("processo_execucao") or o.get("arquivo"), "status": o.get("status_execucao") or "",
                 "encerrada": _exec_encerrada(o), "crimes": o.get("crimes_curto") or "", "geracao": o.get("data_geracao_rspe") or "",
                 "tem_crime": any(not (c.get("extinto") or "").upper().startswith("S") for c in o.get("_crimes") or [])}
                for o in g if o is not r]
    return out


def _so_ativos(modelos, brutos=None):
    """Mesma pessoa com mais de um RSPE: fica uma linha só, a da execução principal (_rank_exec); as outras saem da lista e são
    citadas no aviso da Auditoria da principal."""
    por_bruto = {id(m.get("_bruto")): m for m in modelos if m.get("_bruto")}
    fora = set()
    for gb in _grupos_pessoa([m["_bruto"] for m in modelos if m.get("_bruto")]):
        g = [por_bruto[id(b)] for b in gb]
        if len(g) > 1:
            princ = max(g, key=lambda m: _rank_exec(m.get("_bruto") or {}))
            fora |= {id(m) for m in g if m is not princ}
    return [m for m in modelos if id(m) not in fora]


def _ctx_de(ctx, r):
    """Fatia do contexto que interessa a um assistido (o processo paralelo não recebe as tabelas da base inteira)."""
    ch = r.get("processo_execucao") or r.get("arquivo")
    nn = _norm(r.get("nome", ""))
    um = lambda d: {ch: d[ch]} if ch in d else {}
    fichas = {}
    for k in [ch, "nome:" + nn] + list((ctx.get("outros_procs") or {}).get(ch, [])):
        if k in ctx["fichas"]:
            fichas[k] = ctx["fichas"][k]
    if ch not in ctx["fichas"]:
        alt = _ficha_alternativa(ctx["fichas"], r)
        if alt:
            fichas["nome:~alt"] = alt
        else:
            fichas["~cands"] = _fichas_candidatas(ctx["fichas"], r)
    fx = ctx["fixados"]
    return {"baixas": um(ctx["baixas"]), "fichas": fichas, "manuais": um(ctx["manuais"]), "ajustes": um(ctx["ajustes"]),
            "dmanuais": um(ctx["dmanuais"]), "peds": um(ctx["peds"]), "hist_n": um(ctx["hist_n"]),
            "fixados": ({ch: fx[ch]} if ch in fx else {}) if isinstance(fx, dict) else ({ch} if ch in fx else set()),
            "homonimos": {nn: ctx["homonimos"].get(nn, 0)}, "outras_cond": um(ctx.get("outras_cond") or {}), "outros_procs": um(ctx.get("outros_procs") or {}),
            "outras_exec": um(ctx.get("outras_exec") or {}), "homon_det": um(ctx.get("homon_det") or {})}


def _montar_proc(args):
    """Processo paralelo da montagem: (registro, fatia do contexto, data de hoje) -> (modelo, baixas a migrar)."""
    r, sub, hoje = args
    rv.HOJE = hoje
    return _montar_modelo(r, sub)


def _leitura_rspe(r, faltam):
    """Leitura do RSPE para o registro da importação: (observações, parcial). Campo vazio porque o SEEU não o tem (sem processo,
    sem crime, pena não iniciada) é observação, não leitura parcial."""
    obs, parcial = [], False
    if faltam:
        obs.append("não lido: %s - campo em branco no SEEU, página faltando ou texto quebrado na extração" % ", ".join(faltam))
        parcial = True
    if rs.sem_condenacao_seeu(r):
        obs.append("o SEEU não tem processo criminal cadastrado nesta execução (o RSPE só traz o cabeçalho): não é falha de leitura")
    elif rs.sem_crime_seeu(r):
        obs.append("processo criminal cadastrado sem crimes lançados no SEEU: não é falha de leitura")
    elif not r.get("_crimes"):
        obs.append("nenhuma condenação lida: quadro de processos criminais ausente ou fora do layout")
        parcial = True
    if rs.sem_inicio_seeu(r):
        obs.append("sem eventos nem incidentes: pena não iniciada no SEEU")
    elif not [e for e in r.get("_eventos") or [] if not e.get("_ficha")]:
        obs.append("nenhum evento de prisão/soltura lido: conferir a aba Eventos no SEEU ou se faltam páginas")
    return obs, parcial


def _extrair_com_hash(caminho):
    h = hashlib.sha1()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    # a primeira página decide o tipo: a ficha disciplinar não passa pela leitura do RSPE (mais rápido no lote grande, e um
    # erro qualquer na leitura do RSPE não esconde a ficha)
    try:
        p1 = rf.texto_pagina1(caminho)
    except Exception:
        p1 = ""
    if rf.e_ficha(p1):
        try:
            r = rf.extrair(caminho)
        except Exception as e2:
            raise ValueError("ficha disciplinar do SIAPEN com falha na leitura (%s) - enviar o arquivo para correção" % e2)
        r["_hash"] = h.hexdigest()
        return r
    try:
        r = rs.extrair(caminho)
    except Exception as e:
        # pode ser uma Ficha Disciplinar do SIAPEN com o cabeçalho fora da primeira página
        try:
            txt = rf.texto_pdf(caminho)
        except Exception:
            raise e
        if not txt.strip():
            raise ValueError("PDF sem texto (digitalizado ou imagem): gere o PDF direto do SEEU/SIAPEN, não escaneado")
        if not rf.e_ficha(txt):
            raise e
        try:
            r = rf.extrair(caminho)
        except Exception as e2:
            raise ValueError("ficha disciplinar do SIAPEN com falha na leitura (%s) - enviar o arquivo para correção" % e2)
    r["_hash"] = h.hexdigest()
    return r


def _um(x):
    if isinstance(x, (list, tuple)):
        return x[0] if x else None
    return x


def _abrir(caminho):
    try:
        if sys.platform.startswith("win"):
            os.startfile(caminho)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", caminho])
        else:
            subprocess.Popen(["xdg-open", caminho])
    except Exception:
        pass


def _preparar_log():
    """No .exe (modo janela) não há console: erros vão para rspe_log.txt ao lado do programa."""
    try:
        import logging
        caminho = os.path.join(pasta_app(), "rspe_log.txt")
        if sys.stdout is None or sys.stderr is None:
            f = open(caminho, "a", encoding="utf-8", buffering=1)
            sys.stdout = sys.stdout or f
            sys.stderr = sys.stderr or f
        logging.basicConfig(filename=caminho, level=logging.WARNING,
                            format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        logging.getLogger("pywebview").setLevel(logging.WARNING)
        logging.warning("APTO %s iniciado", VERSAO)
    except Exception:
        pass


def main():
    _preparar_log()
    api = Api()
    janela = webview.create_window(APP, recurso("ui.html"), js_api=api, width=1440, height=860, min_size=(1100, 600),
                                   background_color="#F4F6FA")
    api._janela = janela

    def ao_abrir():
        api._vigia_iniciar()
        arqs = [a for a in sys.argv[1:] if a.lower().endswith(".pdf") or os.path.isdir(a)]
        lista = []
        for a in arqs:
            if os.path.isdir(a):
                for raiz, _, nomes in os.walk(a):
                    lista += [os.path.join(raiz, n) for n in nomes if n.lower().endswith(".pdf")]
            else:
                lista.append(a)
        if lista:
            if not api.base:
                api.nova_base("Importação %s" % datetime.now().strftime("%d-%m-%Y %H-%M"))
                api._js("api('listar')")
            api._importar(lista)

    webview.start(ao_abrir)


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()  # executável (PyInstaller): os processos de leitura do lote reabrem o programa
    try:
        main()
    except Exception:
        import traceback, logging
        logging.error(traceback.format_exc())
        raise
