#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSPE Base - SEEU
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import webview

import rspe_scraper as rs
import rspe_view as rv
import rspe_ficha as rf
import rspe_peticao as rpet
import rspe_export as rx
import rspe_regras as rg
import rspe_relatorio as rrel
import rspe_indulto_tl as rtl

APP = "RSPE Base"
VERSAO = "6.16.2"


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

AJUDA = """
<h4>Cores</h4>
Progressão e Livramento: <b>amarelo forte</b> = prazo vencido ("Vencido há N dias · verificar criminológico, indeferimento ou
falta"; a dica mostra os pedidos do RSPE e, quando houver, o aviso sobre o exame criminológico, que é só dica: não muda a cor nem
gera alerta). Prazos: <b>laranja</b> = vence em até 30 dias; <b>amarelo</b> = em até 60; <b>verde</b> = em até 90. Acima de 90 dias:
"Em cumprimento", sem cor. <b>Cinza</b> = "Pena cumprida" ou "Não se aplica" (em livramento, já no aberto, não iniciou, pena
interrompida - o motivo fica na ficha); <b>amarelo</b> também para "A verificar (livramento)"; <b>azul</b> = execução extinta.
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
Incidente negado não conta. A ficha disciplinar não entra nesta coluna. "Não consta" não garante ausência de falta: conferir o PAD.
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
9.158) e a da ordem cronológica do trânsito (STJ, HC 627.646). O prazo (art. 109 sobre o saldo, +1/3, metade) é testado em cada
faixa do art. 109 atravessada pelos dois limites e a data-limite soma os dias de suspensão. Todas as faixas prescrevem:
"Prescrição executória aparente" (data mais tardia); nenhuma: "Não prescrita"; divergem: "A VERIFICAR: saldo na evasão depende da
imputação do cumprimento entre as condenações unificadas" (amarelo), com a lista do que falta (cálculo do SEEU com o saldo por
condenação, ordem de imputação, prisões por outro processo). Recaptura ou reinício interrompe (art. 117, V); cada crime prescreve
isoladamente pelo seu saldo (art. 119; STJ, AgRg no REsp 2.256.555, RHC 35.425, HC 261.866). Nunca se usa "tempo total preso
igual ou maior que a pena do crime": a mesma prisão serve a várias condenações. Custódia provisória anterior ao trânsito igual ou
maior que a pena do processo não é resultado de prescrição: vira aviso na memória e hipótese "a verificar" na aba Extinção.
A "memória de cálculo" de cada crime mostra, nesta ordem: pena aplicada; termo inicial; prazo pela pena aplicada; prisão provisória
(informativa); cada período (cumprimento, prisão por outro motivo, evasão com cumprido, saldo, prazo, vencimento e recaptura,
liberdade sem evasão); conclusão. Abaixo dela, a tabela da linha do tempo do crime (Período | Classificação | Fonte | Efeito na prescrição).
<b>Linha do tempo visual</b>: na linha de cada crime da aba Prescrição (e no cartão da prescrição executória da ficha do assistido),
"cálculo" abre a memória em texto e "linha do tempo" abre a figura, um de cada vez (clicar de novo fecha). A figura é a memória de
cálculo desenhada e não faz conta própria: eixo do fato à situação atual com os marcos (fato, sentença, trânsito, fuga, recaptura, hoje)
e cada período classificado. Legenda das faixas: verde = cumprimento da pena; vermelho hachurado = fuga/evasão; listras cinza = prisão
provisória (detração); roxo = suspensão (preso por outro motivo); cinza claro = liberdade sem evasão; azul claro = livramento; laranja
hachurado com "?" = atribuição não comprovada (cumprimento registrado no SEEU só para outro processo: conta na execução unificada, mas
a imputação a esta condenação não consta). Sob cada fuga, a linha de contagem pelo saldo (art. 113) com os vencimentos (saldo mínimo,
faixa intermediária do art. 109, saldo máximo) e a recaptura, e o cartão com pena aplicada, cumprido, imputável ao crime, saldo, prazo e
vencimento. Abaixo, os blocos "detração → saldo → prazo", as hipóteses de imputação (CP, art. 76 e ordem cronológica do trânsito) e o
cartão do resultado (A VERIFICAR / PRESCRITO / Não reconhecida) com o motivo e "Falta para concluir". Clique em marco, faixa ou linha de
contagem para o balão "Como cheguei aqui?" (evento do SEEU, período, tratamento, fundamento e efeito). O relatório individual traz a
mesma figura, sem os balões.
<h4>Filtro de situação</h4>
O seletor ao lado dos botões filtra a aba (a Geral não tem). Progressão e Livramento: vencidas, vence em até 30, 60 ou 90 dias, não
iniciou, pena interrompida, não se aplica (cumprida / livramento / aberto), sem data. Indulto/Comutação: por benefício e resultado
("Indulto 2024 · Sim", "Comutação 2025 · Verificar" etc.), fato posterior à data do decreto, falta nos 12 meses e crime impeditivo.
Prescrição: aparente, iminente / a verificar, não prescrita / não configurada, sem dados, extinta. Extinção: extinção cabível,
término em até 30, 60 ou 90 dias, pena interrompida, sem previsão. Ficha disciplinar: remição a requerer, conferir remição / sem atestado
/ estudo, em ordem, sem ficha. Auditoria: com alertas, pontos a verificar, sem inconsistências. O número da execução é copiado com um clique.
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
de incapacidade econômica para quem é assistido pela Defensoria). Na extinção da punibilidade, a multa pendente só não obsta se
comprovada a impossibilidade de pagamento, ainda que parcelado (STF ADI 7.032, vinculante; STJ Tema 931, rev. 28/02/2024): instruir
o pedido. A <b>reparação do dano</b> é dispensada no inciso XV do art. 9º (crime patrimonial sem VGA); no livramento (CP, art. 83,
IV, "salvo efetiva impossibilidade"), a impossibilidade deve ser demonstrada (STJ, AgRg no HC 799.167).
O tráfico privilegiado (art. 33, § 4º) não é hediondo nem impeditivo de indulto (STF, SV 63 e Tema 1400; STJ Tema 1336).
<h4>Petições a partir de modelos .docx</h4>
Recurso desativado nesta versão (foco na exatidão dos cálculos). Os modelos e o cadastro de defensores permanecem no programa
para reativação futura.
<h4>Auditoria</h4>
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
<b>Dar baixa</b>: cada ponto pode ser baixado (com observação) quando já foi tratado ou não se aplica; ele sai da contagem,
fica registrado na base com data e pode ser reaberto. A baixa é por processo, pelo tipo do ponto e pelo crime (ou ano do decreto,
ou falta) a que ele se refere: sobrevive à reimportação do RSPE e continua valendo quando o título muda (números, datas ou
agrupamento de crimes). Baixas gravadas em versões anteriores passam sozinhas para a chave nova na primeira abertura. Os avisos
"Ficha disciplinar ignorada" e "Falha ao analisar" contam como alerta e também podem ser baixados.
<h4>Extinção</h4>
Só a extinção pelo cumprimento: pena integralmente cumprida ou término previsto já alcançado (LEP, arts. 66, II, e 109); livramento
condicional com período de prova expirado sem revogação (CP, arts. 89 e 90; LEP, art. 146); detração que iguala ou supera a pena do
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

def _norm(txt):
    import unicodedata
    t = unicodedata.normalize("NFKD", txt or "").encode("ascii", "ignore").decode()
    return " ".join(t.upper().split())


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
        self.con.execute("""CREATE TABLE IF NOT EXISTS atestados_manuais (
            processo TEXT, id TEXT, dados TEXT, data TEXT, PRIMARY KEY (processo, id))""")
        self.con.execute("""CREATE TABLE IF NOT EXISTS fichas (
            chave TEXT PRIMARY KEY, processo TEXT, nome_norm TEXT, data_impressao TEXT, importado_em TEXT, dados TEXT)""")
        # ajustes manuais da tabela de prescrição executória (padrão SEEU): por processo e linha (ação penal + crime)
        self.con.execute("""CREATE TABLE IF NOT EXISTS presc_ajustes (
            processo TEXT, chave TEXT, dados TEXT, data TEXT, PRIMARY KEY (processo, chave))""")
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
        out = {}
        for ch, p, nn, imp, dados in rows:
            f = json.loads(dados)
            f["importado_em"] = imp
            out[ch] = f
            if nn and not p:
                out.setdefault("nome:" + nn, f)
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

    def migrar_baixa(self, processo, antiga, nova):
        with self.lock:
            if not self.con.execute("SELECT 1 FROM baixas WHERE processo=? AND chave=?", (processo, nova)).fetchone():
                self.con.execute("UPDATE baixas SET chave=? WHERE processo=? AND chave=?", (nova, processo, antiga))
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

    @property
    def nome(self):
        return os.path.splitext(os.path.basename(self.caminho))[0]

    def gravar(self, r):
        chave = r.get("processo_execucao") or r.get("arquivo")
        with self.lock:
            self.con.execute(
                "INSERT OR REPLACE INTO assistidos VALUES (?,?,?,?,?,?)",
                (chave, r.get("nome", ""), r.get("data_geracao_rspe", ""), r.get("arquivo", ""),
                 datetime.now().strftime("%d/%m/%Y %H:%M"), json.dumps(r, ensure_ascii=False)))
            self.con.commit()

    def todos(self):
        with self.lock:
            rows = self.con.execute("SELECT dados, importado_em FROM assistidos ORDER BY nome").fetchall()
        out = []
        for dados, imp in rows:
            d = json.loads(dados)
            d["importado_em"] = imp
            out.append(d)
        return out

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
                    "hoje": rv.HOJE.strftime("%d/%m/%Y"), "abas": rv.ABAS, "rotulos": rv.ROTULO, "ajuda": AJUDA,
                    "base_juridica": {"versao": rg.versao(), "origem": rg.origem()}, "registros": []}
        brutos = self.base.todos()
        baixas = self.base.baixas()
        fichas = self.base.fichas()
        manuais = self.base.manuais()
        ajustes = self.base.presc_ajustes()
        self._modelos = []
        _homonimos = {}
        for _r in brutos:
            _homonimos[_norm(_r.get("nome", ""))] = _homonimos.get(_norm(_r.get("nome", "")), 0) + 1
        for r in brutos:
            try:
                imp = r.get("importado_em")
                r = rs.reprocessar(r)  # análise refeita com as regras desta versão (a leitura do PDF fica como foi gravada)
                r["importado_em"] = imp
            except Exception:
                pass
            ch = r.get("processo_execucao") or r.get("arquivo")
            r["_presc_ajustes"] = ajustes.get(ch, {})  # dados de prescrição preenchidos/corrigidos pelo operador (só em memória)
            _nn = _norm(r.get("nome", ""))
            ficha = fichas.get(ch) or (fichas.get("nome:" + _nn) if _homonimos.get(_nn, 0) == 1 else None)
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
            # baixas gravadas pelo título (até a 6.15.11): passam para a chave estável (tipo do ponto + crime)
            for it in m.get("aud_itens") or []:
                if it.get("migrar_de"):
                    try:
                        self.base.migrar_baixa(ch, it["migrar_de"], it["chave"])
                    except Exception:
                        logging.getLogger("rspe").exception("falha ao migrar baixa %s", ch)
            m["_bruto"] = r
            self._modelos.append(m)
        return {
            "base": self.base.nome,
            "hoje": rv.HOJE.strftime("%d/%m/%Y"),
            "abas": rv.ABAS,
            "rotulos": rv.ROTULO,
            "ajuda": AJUDA,
            "base_juridica": {"versao": rg.versao(), "origem": rg.origem()},
            # json_seguro: um Fraction ou date esquecido no modelo derrubava a lista inteira ("Object of type Fraction is not JSON serializable")
            "registros": rv.json_seguro([{k: v for k, v in m.items() if k != "_bruto"} for m in self._modelos]),
        }

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
        return self.listar()

    def baixar_alerta(self, processo, chave, titulo, obs):
        if not self.base:
            return None
        self.base.baixar(processo, chave, titulo, obs)
        r = self.listar()
        r["msg"] = "Alerta baixado."
        return r

    # ---- ficha disciplinar: conferência e atestados fora da ficha ----
    def fd_conferir(self, processo, chave, marcar):
        if not self.base:
            return None
        if marcar:
            self.base.baixar(processo, chave, "conferido (ficha disciplinar)", "")
        else:
            self.base.reabrir(processo, chave)
        return self.listar()

    def fd_adicionar(self, processo, dados):
        if not self.base:
            return None
        dados = {k: str(v or "").strip() for k, v in (dados or {}).items()}
        if not (dados.get("remidos") or dados.get("trabalhados") or dados.get("horas")):
            return {"erro": "Informe ao menos os dias remidos, os dias trabalhados ou as horas."}
        self.base.manual_gravar(processo, dados)
        r = self.listar()
        r["msg"] = "Adicionado."
        return r

    def fd_remover(self, processo, id_):
        if not self.base:
            return None
        self.base.manual_remover(processo, id_)
        r = self.listar()
        r["msg"] = "Removido."
        return r

    def reabrir_alerta(self, processo, chave):
        if not self.base:
            return None
        self.base.reabrir(processo, chave)
        r = self.listar()
        r["msg"] = "Alerta reaberto."
        return r

    def remover(self, chave):
        if not self.base:
            return None
        self.base.remover(chave)
        return self.listar()

    # ---- bases ----
    def _trocar_base(self, caminho):
        with self._imp_lock:
            return self._trocar_base_(caminho)

    def _trocar_base_(self, caminho):
        if self.base:
            self.base.fechar()
        self.base = Base(caminho)
        self._salvar_config()
        return self.listar()

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
                                                   file_types=("Base RSPE (*.sqlite)",)))
            if not c:
                return None
            if not c.lower().endswith(".sqlite"):
                c += ".sqlite"
            if os.path.exists(c):
                os.remove(c)
        return self._trocar_base(c)

    def abrir_base(self, caminho=None):
        if caminho and os.path.exists(caminho):
            return self._trocar_base(caminho)
        os.makedirs(PASTA_BASES, exist_ok=True)
        c = _um(self._janela.create_file_dialog(webview.OPEN_DIALOG, directory=PASTA_BASES, file_types=("Base RSPE (*.sqlite)",)))
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
                                               save_filename=self.base.nome + ".sqlite", file_types=("Base RSPE (*.sqlite)",)))
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
        fichas_ok = []
        incompletos = []
        total = len(arqs)
        vistos = set()
        lock = threading.Lock()
        if not silencioso:
            self._js("ui.progresso(0,%d)" % total)
        with ThreadPoolExecutor(max_workers=min(4, os.cpu_count() or 2)) as ex:
            futs = {ex.submit(_extrair_com_hash, a): a for a in arqs}
            for n, fut in enumerate(as_completed(futs), 1):
                a = futs[fut]
                nome_arq = os.path.basename(a)
                try:
                    r = fut.result()
                    if r.get("tipo") == "ficha_disciplinar":
                        with lock:
                            proc, mesma_pessoa = self._vincular_ficha(r, base)
                            if not base.gravar_ficha(r, proc, mesma_pessoa):
                                antigos.append("%s: ficha de %s impressa em %s é mais antiga que a da base - ignorada" % (nome_arq, r.get("nome"), r.get("data_impressao") or "?"))
                                continue
                            fichas_ok.append("%s: ficha de %s %s" % (nome_arq, r.get("nome"), ("vinculada a " + proc) if proc else "SEM RSPE correspondente na base (fica guardada pelo nome)"))
                        continue
                    if not r.get("processo_execucao"):
                        raise ValueError("não parece um RSPE do SEEU nem uma Ficha Disciplinar do SIAPEN")
                    with lock:
                        chave = r["processo_execucao"]
                        if r["_hash"] in vistos:
                            duplicados.append("%s: arquivo repetido no mesmo lote" % nome_arq)
                            continue
                        vistos.add(r["_hash"])
                        ex_ = base.existente(chave)
                        if ex_:
                            data_ex, hash_ex = ex_
                            if hash_ex == r["_hash"] or (data_ex and data_ex == r.get("data_geracao_rspe")):
                                duplicados.append("%s: RSPE de %s já está na base (%s)" % (nome_arq, r.get("data_geracao_rspe"), r.get("nome")))
                                continue
                            d_ex, d_novo = rs.to_date(data_ex or ""), rs.to_date(r.get("data_geracao_rspe") or "")
                            if d_ex and d_novo and d_novo < d_ex:
                                antigos.append("%s: RSPE de %s é mais antigo que o da base (%s) - ignorado" % (nome_arq, r.get("data_geracao_rspe"), data_ex))
                                continue
                            if d_ex and not d_novo:
                                antigos.append("%s: RSPE sem data de geração legível; a base já tem o de %s - ignorado" % (nome_arq, data_ex))
                                continue
                            base.gravar(r)
                            atualizados += 1
                        else:
                            base.gravar(r)
                            novos += 1
                        faltam = rs.campos_faltantes(r)
                        if faltam:
                            incompletos.append("%s: %s - não foi possível ler %s" % (nome_arq, r.get("nome") or "?", ", ".join(faltam)))
                except Exception as e:
                    erros.append("%s: %s" % (nome_arq, e))
                if not silencioso and (n % 3 == 0 or n == total):
                    self._js("ui.progresso(%d,%d)" % (n, total))
        avisos = incompletos + duplicados + antigos + erros + fichas_ok
        if avisos:
            with open(os.path.join(pasta_app(), "importacao_avisos.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(avisos))
        resumo = {"novos": novos, "atualizados": atualizados, "duplicados": len(duplicados), "antigos": len(antigos),
                  "erros": len(erros), "fichas": len(fichas_ok), "incompletos": len(incompletos), "avisos": avisos[:60]}
        if not silencioso:
            self._js("ui.importado(%s)" % json.dumps(resumo, ensure_ascii=False))
        return resumo

    def _vincular_ficha(self, f, base=None):
        """(processo, mesma_pessoa): processo de execução da base ao qual a ficha pertence, pelos autos citados na ficha ou
        pelo nome; mesma_pessoa = sem homônimo na base (a ficha guardada pelo nome pode ser comparada e migrada)."""
        base = base or self.base
        with base.lock:
            rows = base.con.execute("SELECT processo, nome FROM assistidos").fetchall()
        procs = {p for p, _ in rows}
        nn = _norm(f.get("nome", ""))
        mesmos = [p for p, n in rows if _norm(n) == nn]
        for a in f.get("autos", []):
            if a in procs:
                # vinculada pelos autos: sem homônimo na base, a ficha guardada pelo nome é da mesma pessoa
                return a, len(mesmos) <= 1
        # pelo nome só quando não há homônimo na base (com homônimos, a ficha fica guardada pelo nome, sem vínculo)
        return (mesmos[0], True) if len(mesmos) == 1 else ("", False)

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


    # ---- relatórios (PDF) ----
    def relatorios(self, ids, individual, geral, planilha, nominal, ids_individual=None):
        """Gera, numa pasta escolhida, a subpasta 'Relatorios <data hora>' com o relatório geral, os individuais e a planilha."""
        if not self.base:
            return {"erro": "Nenhuma base aberta."}
        modelos = [m for m in self._modelos if m["id"] in set(ids)]
        if not modelos:
            return {"erro": "Nada para gerar."}
        if not (individual or geral or planilha):
            return {"erro": "Marque ao menos uma saída."}
        pasta = _um(self._janela.create_file_dialog(webview.FOLDER_DIALOG))
        if not pasta:
            return None
        try:
            sel = set(ids_individual) if ids_individual else None
            individuais = [m for m in modelos if m["id"] in sel] if sel is not None else modelos
            destino, n, erros = rrel.gerar(modelos, pasta, self.base.nome, individual=individual, geral=geral, nominal=nominal,
                                           individuais=individuais)
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


def _extrair_com_hash(caminho):
    h = hashlib.sha1()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    try:
        r = rs.extrair(caminho)
    except ValueError as e:
        # pode ser uma Ficha Disciplinar do SIAPEN
        try:
            r = rf.extrair(caminho)
        except Exception:
            raise e
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
        logging.warning("RSPE Base %s iniciado", VERSAO)
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
    try:
        main()
    except Exception:
        import traceback, logging
        logging.error(traceback.format_exc())
        raise
