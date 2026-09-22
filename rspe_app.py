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
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
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

APP = "RSPE Base"
VERSAO = "6.10.4"


def pasta_app():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def recurso(nome):
    return os.path.join(getattr(sys, "_MEIPASS", pasta_app()), nome)


PASTA_BASES = os.path.join(pasta_app(), "bases")
CONFIG = os.path.join(pasta_app(), "rspe_config.json")
BASE_PADRAO = os.path.join(PASTA_BASES, "base_padrao.sqlite")

AJUDA = """
<h4>Cores</h4>
Progressão e Livramento: <b>amarelo forte</b> = prazo vencido - verificar exame criminológico, indeferimento ou falta (a dica da
célula mostra os pedidos do RSPE). Extinção (término): <b>vermelho</b> = cabível. Prazos: <b>laranja</b> = vence em até 30 dias; <b>amarelo</b> = em até
60 dias; <b>verde</b> = em até 90 dias. Acima de 90 dias a situação fica em branco (não há o que fazer ainda). <b>Cinza</b> = não se
aplica (pena interrompida, já no aberto, em livramento, cumprida); <b>azul</b> = execução extinta. Indulto/Comutação: <b>vermelho</b> =
crime impeditivo; <b>verde</b> = possível; <b>amarelo</b> = a verificar; <b>cinza</b> = não atinge. Clique num cartão de resumo para filtrar.
<h4>Datas</h4>
Progressão, livramento e término são os impressos pelo SEEU no RSPE; o programa não os recalcula. Sem data no RSPE aparece
"Não consta no RSPE" ou "Pena interrompida". O programa só calcula indulto/comutação e prescrição, na convenção do SEEU
(ano de 365 dias, mês de 30, prazos pelo calendário), partindo da pena cumprida impressa no RSPE.
<h4>Falta (12 meses)</h4>
O RSPE não lista faltas formalmente. A coluna aponta indícios nos 12 meses anteriores: regressão, perda de dias remidos,
fuga/evasão, sanção. "Não consta" não garante ausência de falta: conferir o PAD.
<h4>Indulto / Comutação</h4>
Art. 1º (mesmo rol nos dois decretos): hediondos/equiparados, tortura, lavagem (&gt;4 anos), ORCRIM e milícia, terrorismo, racismo,
escravidão/tráfico de pessoas, genocídio, sistema financeiro (&gt;4 anos), licitações (&gt;4 anos), crimes sexuais (215, 216-A, 217-A,
218 a 218-C), administração pública 312-319 e 333 (&gt;4 anos), ECA 239-244-B, ambientais, Estado Democrático, abuso de autoridade,
violência contra a mulher, tráfico (33 caput/§1º, 34-37, 39). Art. 6º: falta grave nos 12 meses antes de 25/12.
Art. 9º, testado inciso por inciso com a situação em 25/12 de cada ano (regime, pena cumprida, remanescente, reincidência):
I, II, III (frações por faixa de pena), IV e V (15/20 e 20/25 anos), VI (semiaberto ininterrupto), VII (regime aberto, 1/6 ou 1/5),
VIII (aberto ou livramento com remanescente ≤ 6 anos, ≤ 4 se reincidente), IX a XV marcados como "a verificar" quando a parte
objetiva é atendida (programa de egressos, monitoramento, saídas temporárias, estudo, valor do bem, reparação do dano).
§ 2º, I: para maiores de 60 anos os lapsos dos incisos I a XI caem pela metade (aplicado automaticamente pela data de nascimento);
os demais grupos do § 2º, o inciso XVI (saúde) e o art. 10 (mulheres) não são aferíveis pelo RSPE.
Art. 13 (comutação): 1/5 do remanescente (ou do cumprido, se maior) para quem cumpriu 1/5 (primário) ou 1/4 (reincidente);
2/3 para os grupos do § 2º; não cumula com indulto (§ 5º). A análise completa está na ficha, em "Análise inciso por inciso".
<b>Decreto 11.302/2022</b> (referência 25/12/2022) tem lógica própria: art. 5º alcança o crime cuja <b>pena máxima em abstrato</b>
não supere 5 anos (em concurso, cada crime é avaliado isoladamente - parágrafo único), sem exigir fração cumprida nem regime;
art. 4º, maiores de 70 anos com 1/3 cumprido; art. 1º, saúde (laudo); art. 7º exclui hediondos, violência/grave ameaça e violência
doméstica, tortura, lavagem, ORCRIM, terrorismo, crimes sexuais (215 a 218-C), 312/316/317/333, tráfico (33 caput e § 1º, 34, 36 -
exceto o § 4º) e ECA 240-244-B; art. 9º dispensa o trânsito em julgado. A pena máxima é lida do tipo penal impresso no RSPE; quando o
SEEU corta o texto, usa-se a tabela editável "pena_maxima_abstrata" da base jurídica (indicado na análise). O trecho relativo a
agentes de segurança (arts. 2º, 3º e 6º) foi suspenso pelo STF na ADI 7.330 e não é avaliado.
<b>Hediondez pela época do fato</b>: a tabela "hediondos.desde" da base jurídica guarda a data em que cada tipo passou a ser
hediondo (Lei 8.072/90 e alterações - 8.930/94, 9.695/98, 12.015/2009, 13.104 e 13.142/2015, 13.497/2017, 13.654/2018,
13.964/2019, 14.811 e 14.994/2024, 15.358/2026). Fato anterior à data não é tratado como hediondo (CF, art. 5º, XL): isso
vale para as frações, o livramento e o art. 1º dos decretos, e a Auditoria alerta quando o SEEU rotulou como hediondo um
fato anterior à lei.
<h4>Prescrição (arts. 109 a 119 do CP), crime a crime</h4>
<b>Pretensão punitiva (retroativa e intercorrente, art. 110, § 1º)</b>: prazo pela pena aplicada (art. 109), metade se menor de 21 anos
no fato ou maior de 70 na sentença (art. 115); intervalos fato→denúncia (só para fatos anteriores a 05/05/2010, Lei 12.234/2010),
denúncia→sentença e sentença→trânsito. O acórdão confirmatório também interrompe (art. 117, IV; STF HC 176.473) e sua data não
consta no RSPE: conferir antes de pedir.
<b>Pretensão executória (art. 110, caput)</b>: prazo pela pena aplicada, +1/3 se reincidente, metade pelo art. 115. Termo inicial no
trânsito em julgado para ambas as partes (STF, Tema 788) ou, se o trânsito para a acusação é anterior a 12/11/2020, nessa data
(art. 112, I, com a modulação do Tema). Não corre enquanto preso (art. 116, p. único) e interrompe-se pelo início ou continuação
do cumprimento (art. 117, V); na evasão ou revogação do livramento, regula-se pela pena restante (art. 113). Cada crime é analisado
isoladamente (art. 119). A "memória de cálculo" de cada crime mostra intervalos, prazos e datas.
Só a prescrição já consumada aparece: vermelho = prescrição aparente; sem cor = não prescrita; cinza = sem dados ou extinta.
<h4>Filtro de situação</h4>
O seletor ao lado dos botões filtra a aba: vencidas / a vencer em 30 ou 60 dias / interrompidas (progressão e livramento); possível /
a verificar / não atinge / impeditivo (indulto); aparente / não prescrita (prescrição). O número da execução é copiado com um clique.
<h4>Ficha disciplinar (SIAPEN/AGEPEN)</h4>
Importe o PDF da Ficha Disciplinar pelo mesmo botão "Importar PDFs": o programa reconhece o documento e o vincula ao RSPE
pelos autos citados na ficha (ou pelo nome). Extrai conduta, períodos de trabalho (setor/empresa), atestados de trabalho com
dias trabalhados e remidos, faltas disciplinares (registro, PADIC, arquivamento/homologação), regressão/restabelecimento,
isolamento e recusa de trabalho. A Auditoria confronta: dias remidos atestados x homologados no RSPE (LEP, art. 126), proporção
1 para 3, trabalho sem atestado e baixa de trabalho sem início registrado, falta grave nos últimos 12 meses (CP, art. 83, III, b;
art. 6º dos decretos), falta arquivada que ainda produza efeitos e perda de dias remidos em duplicidade (LEP, art. 127: a nova
perda só alcança a remição adquirida depois da falta anterior). A aba <b>Ficha disciplinar</b> trata só de remição (trabalho e estudo) e mostra uma linha por emprego e por matrícula de estudo:
período, atestado que o cobre, remição homologada no RSPE e providência. Trabalho anterior à 1ª prisão do RSPE fica só no resumo.
<h4>Regras de leitura</h4>
Quem não tem início de cumprimento definitivo no RSPE (só prisão provisória encerrada, ou nenhuma) aparece como "Não iniciou o
cumprimento", e não como regime aberto ou pena interrompida. Livramento suspenso ou revogado em incidente posterior aparece como tal.
Dar baixa no alerta de livramento incerto confirma o livramento em todas as abas. A Auditoria confere só a matemática do RSPE (frações, soma das penas, data-base, perda de dias remidos, reincidência,
marcações de hediondez e violência, livramento incerto); remição, indulto, comutação, prescrição e prazos ficam nas próprias abas.
O programa não usa a expressão "indulto parcial", sinônimo de comutação na jurisprudência (STF, HC 81.567 e HC 96.431; STJ, REsp
753.646): no concurso com crime impeditivo, fala em "indulto dos crimes não impeditivos (art. 7º, p. ú.)". Sem cumprimento em curso na
data do decreto (não iniciado ou interrompido), indulto e comutação de 2024 e 2025 "não se aplicam". O programa não presume datas. Sem data do fato, recebimento da denúncia, sentença ou trânsito em julgado no RSPE, a prescrição
daquele trecho não é calculada e a Auditoria aponta "verificar na ação penal". Quando a 1ª página do RSPE diz "Em livramento
condicional deferido em ...", o assistido é tratado como em livramento, ainda que o "Regime Atual" traga o regime anterior. A
data-base é conferida com a última prisão, progressão/regressão ou falta grave homologada; sem esse evento no RSPE, a Auditoria
aponta a inconsistência (e, se coincidir com a soma/unificação das penas, o Tema 1006 do STJ).
<h4>Relatórios em PDF</h4>
O botão <b>Relatórios</b> gera, numa pasta com a data e a hora: um PDF por assistido (resumo, benefícios, condenações, linha do
tempo, remição e alertas), o relatório geral da base (perfil, benefícios, remição, alertas e fila de prioridade) e a planilha.
Vale para os assistidos visíveis (busca e filtro). Na ficha do assistido, "Relatório em PDF" gera só o dele.
<h4>Presunção de hipossuficiência (Defensoria)</h4>
Em qualquer hipótese o programa presume a incapacidade econômica do assistido: a <b>multa</b> pendente não obsta a extinção da
punibilidade (STJ Tema 931, rev. 28/02/2024; STF ADI 7.032), é indultável e não é óbice ao indulto (Decretos 12.338/2024 e
12.790/2025, art. 12, § 2º, I - presunção expressa para quem é assistido pela Defensoria); a <b>reparação do dano</b> é dispensada
no inciso XV do art. 9º (crime patrimonial sem VGA) e não bloqueia o livramento (CP, art. 83, IV, "salvo efetiva impossibilidade").
O tráfico privilegiado (art. 33, § 4º) não é hediondo nem impeditivo de indulto (STF PSV 125 e Tema 1400; STJ Tema 1336).
A petição deve instruir a impossibilidade (há julgados do STJ exigindo prova - ver base jurídica).
<h4>Petições a partir de modelos .docx</h4>
Recurso desativado nesta versão (foco na exatidão dos cálculos). Os modelos e o cadastro de defensores permanecem no programa
para reativação futura.
<h4>Auditoria</h4>
Confronta o RSPE com a base jurídica (arquivo base_juridica.json, editável e versionado): soma das penas, cumprida + remanescente,
remições, hediondez pelo rol da Lei 8.072/90 (e art. 112, § 5º, LEP para o tráfico privilegiado), marcação de VGA pelo tipo,
fração de progressão pela lei da data do fato (1/6 até 22/01/2020; Lei 13.964/2019 de 23/01/2020 a 24/03/2026; Lei 15.358/2026
a partir de 25/03/2026 para hediondos; Lei 15.402/2026 a partir de 08/05/2026), com retroatividade só do mais benéfico (STJ Temas
1084, 1196 e 1354; STF Tema 1169), fração de livramento (CP, art. 83; Lei 11.343, art. 44), reincidência sem condenação anterior
no RSPE (CP, art. 63), data-base e regressões (LEP, art. 112, § 6º), idade (art. 115 CP; § 2º dos decretos), marcos vencidos sem
decisão, prescrição aparente e indulto/comutação possível sem incidente. Os pontos têm quatro níveis: <b>Alerta</b> (divergência com efeito concreto para o apenado: fração, hediondez, marco vencido,
prescrição, indulto, remição, falta), <b>Verificar</b> (depende de dado que o RSPE não traz, mas pode ter efeito), <b>Info</b>
(registro sem efeito prático - fica oculto por padrão; "mostrar informativos") e <b>OK</b>. "Guia demanda atenção" = há ao menos um alerta objetivo;
"a verificar" = depende de dado que o RSPE não traz. Nada é afirmado como erro: cada item traz o fundamento para conferência.
<b>Dar baixa</b>: cada ponto pode ser baixado (com observação) quando já foi tratado ou não se aplica; ele sai da contagem,
fica registrado na base com data e pode ser reaberto. A baixa é por processo e por ponto, e sobrevive à reimportação do RSPE.
<h4>Extinção</h4>
Só a extinção pelo cumprimento: pena integralmente cumprida ou término previsto já alcançado (LEP, art. 109); livramento
condicional com período de prova expirado sem revogação (CP, arts. 82 e 90); detração que alcança toda a pena do crime.
Prescrição e indulto ficam nas próprias abas. Cores: vermelho =
extinção cabível; amarelo/verde = término em até 30/60 dias; cinza = pena interrompida ou sem previsão.
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
        self.con.execute("""CREATE TABLE IF NOT EXISTS fichas (
            chave TEXT PRIMARY KEY, processo TEXT, nome_norm TEXT, data_impressao TEXT, importado_em TEXT, dados TEXT)""")
        self.con.commit()

    def gravar_ficha(self, f, processo):
        chave = processo or ("nome:" + _norm(f.get("nome", "")))
        with self.lock:
            self.con.execute("INSERT OR REPLACE INTO fichas VALUES (?,?,?,?,?,?)",
                             (chave, processo or "", _norm(f.get("nome", "")), f.get("data_impressao", ""),
                              datetime.now().strftime("%d/%m/%Y %H:%M"), json.dumps(f, ensure_ascii=False)))
            self.con.commit()

    def fichas(self):
        """{processo: ficha} + {'nome:xxx': ficha} para as não vinculadas."""
        with self.lock:
            rows = self.con.execute("SELECT chave, processo, nome_norm, importado_em, dados FROM fichas").fetchall()
        out = {}
        for ch, p, nn, imp, dados in rows:
            f = json.loads(dados)
            f["importado_em"] = imp
            out[ch] = f
            if nn:
                out.setdefault("nome:" + nn, f)
        return out

    def remover_ficha(self, chave):
        with self.lock:
            self.con.execute("DELETE FROM fichas WHERE chave=? OR processo=?", (chave, chave))
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
        rg.carregar()

    # ---- configuração (só a lista de bases recentes) ----
    def _recentes(self):
        try:
            with open(CONFIG, encoding="utf-8") as f:
                c = json.load(f)
            return [p for p in c.get("recentes", []) if os.path.exists(p)]
        except Exception:
            return []

    def _salvar_config(self):
        try:
            rec = self._recentes()
            if self.base:
                rec = [self.base.caminho] + [p for p in rec if p != self.base.caminho]
            with open(CONFIG, "w", encoding="utf-8") as f:
                json.dump({"recentes": rec[:8]}, f)
        except Exception:
            pass

    def _js(self, codigo):
        if self._janela:
            try:
                self._janela.evaluate_js(codigo)
            except Exception:
                pass

    # ---- dados ----
    def listar(self):
        if not self.base:
            return {"sem_base": True, "recentes": [{"caminho": p, "nome": os.path.splitext(os.path.basename(p))[0]} for p in self._recentes()],
                    "hoje": rv.HOJE.strftime("%d/%m/%Y"), "abas": rv.ABAS, "rotulos": rv.ROTULO, "ajuda": AJUDA,
                    "base_juridica": {"versao": rg.versao(), "origem": rg.origem()}, "registros": []}
        brutos = self.base.todos()
        baixas = self.base.baixas()
        fichas = self.base.fichas()
        self._modelos = []
        for r in brutos:
            ch = r.get("processo_execucao") or r.get("arquivo")
            ficha = fichas.get(ch) or fichas.get("nome:" + _norm(r.get("nome", "")))
            m = rv.modelo(r, baixas.get(ch, {}), ficha)
            m["_bruto"] = r
            self._modelos.append(m)
        return {
            "base": self.base.nome,
            "hoje": rv.HOJE.strftime("%d/%m/%Y"),
            "abas": rv.ABAS,
            "rotulos": rv.ROTULO,
            "ajuda": AJUDA,
            "base_juridica": {"versao": rg.versao(), "origem": rg.origem()},
            "registros": [{k: v for k, v in m.items() if k != "_bruto"} for m in self._modelos],
        }

    def baixar_alerta(self, processo, chave, titulo, obs):
        if not self.base:
            return None
        self.base.baixar(processo, chave, titulo, obs)
        r = self.listar()
        r["msg"] = "Alerta baixado."
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

    def _worker(self, arqs):
        novos, atualizados, duplicados, antigos, erros = 0, 0, [], [], []
        fichas_ok = []
        incompletos = []
        total = len(arqs)
        vistos = set()
        lock = threading.Lock()
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
                            proc = self._vincular_ficha(r)
                            self.base.gravar_ficha(r, proc)
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
                        ex_ = self.base.existente(chave)
                        if ex_:
                            data_ex, hash_ex = ex_
                            if hash_ex == r["_hash"] or (data_ex and data_ex == r.get("data_geracao_rspe")):
                                duplicados.append("%s: RSPE de %s já está na base (%s)" % (nome_arq, r.get("data_geracao_rspe"), r.get("nome")))
                                continue
                            d_ex, d_novo = rs.to_date(data_ex or ""), rs.to_date(r.get("data_geracao_rspe") or "")
                            if d_ex and d_novo and d_novo < d_ex:
                                antigos.append("%s: RSPE de %s é mais antigo que o da base (%s) - ignorado" % (nome_arq, r.get("data_geracao_rspe"), data_ex))
                                continue
                            self.base.gravar(r)
                            atualizados += 1
                        else:
                            self.base.gravar(r)
                            novos += 1
                        faltam = rs.campos_faltantes(r)
                        if faltam:
                            incompletos.append("%s: %s - não foi possível ler %s" % (nome_arq, r.get("nome") or "?", ", ".join(faltam)))
                except Exception as e:
                    erros.append("%s: %s" % (nome_arq, e))
                if n % 3 == 0 or n == total:
                    self._js("ui.progresso(%d,%d)" % (n, total))
        avisos = incompletos + duplicados + antigos + erros + fichas_ok
        if avisos:
            with open(os.path.join(pasta_app(), "importacao_avisos.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(avisos))
        resumo = {"novos": novos, "atualizados": atualizados, "duplicados": len(duplicados), "antigos": len(antigos),
                  "erros": len(erros), "fichas": len(fichas_ok), "incompletos": len(incompletos), "avisos": avisos[:60]}
        self._js("ui.importado(%s)" % json.dumps(resumo, ensure_ascii=False))

    def _vincular_ficha(self, f):
        """Processo de execução da base ao qual a ficha pertence: pelos autos citados na ficha, senão pelo nome."""
        with self.base.lock:
            rows = self.base.con.execute("SELECT processo, nome FROM assistidos").fetchall()
        procs = {p for p, _ in rows}
        for a in f.get("autos", []):
            if a in procs:
                return a
        nn = _norm(f.get("nome", ""))
        for p, n in rows:
            if _norm(n) == nn:
                return p
        return ""

    # ---- petições a partir de modelos .docx ----
    def listar_modelos(self):
        rpet.gerar_modelo_exemplo(pasta_app(), recurso("modelos_padrao"))
        return {"modelos": rpet.listar(pasta_app()), "defensores": _ler_defensores()}

    def modelo_restaurar_padrao(self):
        n = rpet.instalar_modelos_padrao(pasta_app(), recurso("modelos_padrao"))
        return {"msg": "%d modelo(s) da unidade restaurado(s) (os existentes não foram alterados)." % n}

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
            return {"msg": "%d defensor(es) salvo(s)." % len(lista), "lista": lista}
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
        return {"msg": "%d modelo(s) adicionado(s)." % n}

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
        self.base.remover_ficha(chave)
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
    def relatorios(self, ids, individual, geral, planilha, nominal):
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
            destino, n, erros = rrel.gerar(modelos, pasta, self.base.nome, individual=individual, geral=geral, nominal=nominal)
            if planilha:
                rx.exportar_xlsx(modelos, os.path.join(destino, "%s - planilha.xlsx" % self.base.nome),
                                 ["geral", "prog", "liv", "ind", "presc", "ext", "fd", "aud", "completo"])
        except Exception as e:
            return {"erro": "Falha ao gerar relatórios: %s" % e}
        _abrir(destino)
        msg = "Relatórios em %s" % destino + (" · %d individual(is)" % n if individual else "")
        if erros:
            msg += " · %d falha(s): %s" % (len(erros), "; ".join(erros[:3]))
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
