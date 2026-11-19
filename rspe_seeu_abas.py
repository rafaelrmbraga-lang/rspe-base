# -*- coding: utf-8 -*-
"""Leitura das ABAS do processo no SEEU (sem PDF e sem o APTO): o painel da extensão busca, na própria aba do processo e com
a sessão de quem está logado, as páginas das abas (Informações Gerais, Informações Adicionais, Partes, Processos Criminais e a
página de cada processo criminal, Eventos, Incidentes Concedidos, Não-Concedidos e Pendentes) e entrega o HTML aqui.

Como o RSPE ("Situação Carcerária") é o relatório que o próprio SEEU monta com esses mesmos dados, o caminho é: abas -> o
texto no formato do RSPE -> o LEITOR DO APTO (rspe_scraper.extrair_paginas), sem mudança nenhuma. Assim valem as mesmas
derivações (custódia, interrupções, frações, extinções, data-base) e o motor recebe o mesmo registro que receberia do RSPE.

A leitura é pelo TEXTO dos rótulos ("Data Base:", "Data do Requisito Temporal:") e dos cabeçalhos das tabelas ("Tipo do
Incidente", "Data de Referência"), não pela marcação: a estrutura foi tirada das capturas de tela oficiais do SEEU (TJSP,
02/2026) e precisa ser conferida com o HTML real das abas. O que não for achado fica em branco - e o que fica em branco no
registro o motor trata como "a verificar" (amarelo no painel), nunca como dado. A lista "faltou" diz o que não foi lido."""
import html.parser
import re

import rspe_scraper as rs

SECOES_CALC = ("Progressão de Regime", "Livramento Condicional", "Término de Pena", "Término da Pena")
RE_CNJ = re.compile(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}")


def _txt(s):
    return " ".join(str(s or "").replace("\xa0", " ").split())


class _Leitor(html.parser.HTMLParser):
    """HTML -> sequência de fichas: ('h', texto) para títulos, ('kv', rótulo, valor) para linhas "rótulo: valor" e
    ('tab', cabeçalhos, linhas) para tabelas com cabeçalho. Também guarda os links (texto, href)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fichas, self.links = [], []
        self._tabs = []          # pilha de tabelas: {"cab": [...], "linhas": [[...]]}
        self._linha = None       # células da linha atual
        self._cel = None         # texto da célula atual
        self._cel_th = False
        self._ignora = 0
        self._link = None
        self._tit = None
        self.corpo = None        # índice das fichas em que começa o corpo da aba (depois do link da última aba, "BNMP3")

    def handle_starttag(self, tag, a):
        a = dict(a)
        if tag in ("script", "style", "template"):
            self._ignora += 1
        elif tag == "table":
            self._tabs.append({"cab": [], "linhas": []})
        elif tag == "tr":
            self._linha = []
        elif tag in ("td", "th"):
            self._cel, self._cel_th = [], tag == "th"
        elif tag == "a":
            self._link = [a.get("href") or "", []]
        elif tag in ("h1", "h2", "h3", "h4", "h5"):
            self._tit = []
        elif tag == "input" and a.get("type") == "hidden" and a.get("id") == "processoNumeroFormatado":
            self.fichas.append(("kv", "processoNumeroFormatado", a.get("value") or ""))

    def handle_endtag(self, tag):
        if tag in ("script", "style", "template"):
            self._ignora = max(0, self._ignora - 1)
        elif tag in ("td", "th") and self._cel is not None and self._linha is not None:
            self._linha.append((_txt("".join(self._cel)), self._cel_th))
            self._cel = None
        elif tag == "tr" and self._linha is not None:
            if self._tabs:
                t = self._tabs[-1]
                if self._linha and all(th for _, th in self._linha) and not t["cab"]:
                    t["cab"] = [x for x, _ in self._linha]
                elif self._linha:
                    t["linhas"].append([x for x, _ in self._linha])
            self._linha = None
        elif tag == "table" and self._tabs:
            t = self._tabs.pop()
            if t["cab"]:
                self.fichas.append(("tab", t["cab"], t["linhas"]))
            else:
                for ln in t["linhas"]:
                    if len(ln) >= 2 and ln[0].endswith(":"):
                        self.fichas.append(("kv", ln[0][:-1].strip(), ln[1]))
        elif tag == "a" and self._link is not None:
            t = _txt("".join(self._link[1]))
            self.links.append((t, self._link[0]))
            if re.match(r"BNMP\s*3", t):
                self.corpo = len(self.fichas)
            self._link = None
        elif tag in ("h1", "h2", "h3", "h4", "h5") and self._tit is not None:
            self.fichas.append(("h", _txt("".join(self._tit))))
            self._tit = None

    def handle_data(self, d):
        if self._ignora:
            return
        if self._cel is not None:
            self._cel.append(d)
        if self._link is not None:
            self._link[1].append(d)
        if self._tit is not None:
            self._tit.append(d)
        t = _txt(d)
        # títulos de seção do cálculo também valem quando não estão em <h>: o texto basta
        if t and self._tit is None and self._cel is None and any(t.startswith(s) for s in SECOES_CALC):
            self.fichas.append(("h", t))


def _ler(htm):
    p = _Leitor()
    p.feed(htm or "")
    p.close()
    # fichas da ABA (sem a capa, que se repete em toda página do processo); sem a barra de abas, a página inteira
    p.aba = p.fichas[p.corpo:] if p.corpo is not None else p.fichas
    return p


def _kv(fichas, rotulo, secao=None, depois=None):
    """Valor do primeiro "rótulo:" (sem acento e sem caixa), dentro da seção (título) indicada, se houver."""
    alvo = rs._sem_acento(rotulo).upper()
    sec_atual = None
    for f in fichas:
        if f[0] == "h":
            sec_atual = rs._sem_acento(f[1]).upper()
            continue
        if f[0] != "kv":
            continue
        if secao and not (sec_atual or "").startswith(rs._sem_acento(secao).upper()):
            continue
        if rs._sem_acento(f[1]).upper() == alvo:
            return f[2]
    return ""


def _tabela(fichas, *colunas):
    """Primeira tabela que tem todas as colunas pedidas (pelo texto do cabeçalho) -> lista de dicts {cabeçalho: valor}; as
    linhas de detalhe (uma célula larga depois da linha principal) entram como "_detalhe" da linha anterior."""
    want = [rs._sem_acento(c).upper() for c in colunas]
    for f in fichas:
        if f[0] != "tab":
            continue
        cab = [rs._sem_acento(c).upper() for c in f[1]]
        if not all(any(w == c for c in cab) for w in want):
            continue
        out = []
        for ln in f[2]:
            vals = [v for v in ln]
            if len(vals) < len(cab) - 1 and out:
                out[-1]["_detalhe"] = " ".join(v for v in vals if v)
                continue
            out.append({f[1][i]: vals[i] if i < len(vals) else "" for i in range(len(f[1]))})
        return out
    return []


def _det(texto, rotulo):
    m = re.search(re.escape(rotulo) + r"\s*:\s*([^·]*)", texto or "")
    return _txt(m.group(1)) if m else ""


def _col(linha, nome):
    alvo = rs._sem_acento(nome).upper()
    for k, v in linha.items():
        if rs._sem_acento(k).upper() == alvo:
            return v
    return ""


def montar_texto(abas, gerado=""):
    """abas: {nome da aba: HTML} com as chaves "capa" (página do processo), "gerais", "adicionais", "partes", "criminais",
    "eventos", "concedidos", "nao_concedidos", "pendentes" e "crim:<n>" (uma por processo criminal). Devolve (texto no
    formato do RSPE, lista do que não foi achado)."""
    faltou = []
    L = {k: _ler(v) for k, v in (abas or {}).items()}
    cap = L.get("capa") or _ler("")
    fc = cap.fichas
    numero = _kv(fc, "processoNumeroFormatado") or ""
    if not numero:
        m = RE_CNJ.search(" ".join(t for t, _ in cap.links) + " " + " ".join(str(f[1:]) for f in fc))
        numero = m.group(0) if m else ""
    sent = _kv(fc, "Sentenciado")
    nome = re.split(r"\s*\(RJI|\s*\(CPF", sent)[0].strip() if sent else ""
    cpf = _det(sent.replace(";", " ·"), "CPF") if sent else ""
    rg = _det(sent.replace(";", " ·"), "RG") if sent else ""
    gerais = (L.get("gerais") or _ler("")).aba
    adic = (L.get("adicionais") or _ler("")).fichas
    partes = (L.get("partes") or _ler("")).aba
    nome = _kv(partes, "Sentenciado") or nome
    cpf = _kv(partes, "CPF") or cpf
    rg = _kv(partes, "RG") or rg
    if re.search(r"n[aã]o cadastrado", cpf or "", re.I):
        cpf = ""
    if re.search(r"n[aã]o cadastrado", rg or "", re.I):
        rg = ""
    nasc = _kv(partes, "Data de Nascimento")
    mae = _kv(partes, "Nome da Mãe") or _kv(fc, "Nome da Mãe")
    juizo = _kv(fc, "Juízo") or _kv(gerais, "Juízo")
    comarca = _kv(gerais, "Comarca/Subseção")
    trib = comarca.split(" - ")[0].strip() if " - " in comarca else ""
    comarca = comarca.split(" - ", 1)[1].strip() if " - " in comarca else comarca
    situ = _kv(gerais, "Situação")
    status = "ARQUIVADO" if re.search(r"ARQUIV|BAIXAD", rs._sem_acento(situ).upper()) else "ATIVO"
    # pena: o gráfico da capa (total, cumprida, restante)
    total = cumprida = restante = ""
    m = re.search(r"(\d+a\d+m\d+d)\s*Cumprida:\s*(\d+a\d+m\d+d)\s*Restante:\s*(\d+a\d+m\d+d)", _txt(re.sub(r"<[^>]+>", " ", abas.get("capa") or "")))
    if m:
        total, cumprida, restante = m.groups()
    elif re.search(r"Cumprida", abas.get("capa") or ""):
        faltou.append("pena total, cumprida e restante (gráfico da capa)")
    regime = _kv(adic, "Regime Atual")
    if regime and "ATIVO" not in regime.upper():
        regime += " - ATIVO"
    db_p = _kv(adic, "Data Base", "Progressão de Regime")
    pr_p = _kv(adic, "Data do Requisito Temporal", "Progressão de Regime")
    db_l = _kv(adic, "Data Base", "Livramento Condicional")
    pr_l = _kv(adic, "Data do Requisito Temporal", "Livramento Condicional")
    interr = _kv(adic, "Total de Interrupção", "Término")
    saldo = _kv(adic, "Saldo dias Remidos", "Término")
    term = _kv(adic, "Data do Requisito Temporal", "Término")
    if saldo and re.fullmatch(r"\d+(\s*\(nenhum dia perdido\))?", saldo.strip()):
        n = re.match(r"\d+", saldo.strip()).group(0)
        saldo = "%s dias (%s dias remidos - 0 dias perdidos)" % (n, n)
    # campo vazio no SEEU não é falha de leitura (pena não iniciada, cumprida...): só a aba ou a seção do cálculo ausente
    if "adicionais" not in L:
        faltou.append("aba Informações Adicionais (regime e cálculo dos requisitos temporais)")
    elif not any(f[0] == "h" and rs._sem_acento(f[1]).upper().startswith("PROGRESSAO DE REGIME") for f in adic):
        faltou.append("cálculo dos requisitos temporais (Informações Adicionais)")
    linhas = ["PODER JUDICIÁRIO", "%s - COMARCA DE %s" % (trib or "TJ", comarca or "?"), juizo, "RELATÓRIO DA SITUAÇÃO PROCESSUAL EXECUTÓRIA",
              "PROCESSO DE EXECUÇÃO", "Número Único: %s (%s)" % (numero, status), "Número Antigo: %s" % (_kv(fc, "Número Antigo") or ""),
              "Nome: %s" % nome, "CPF: %s" % cpf, "RG: %s" % rg, "Nome da Mãe: %s" % (mae or ""), "Data de Nascimento: %s" % (nasc or ""),
              "CÁLCULOS DA PENA:", "Regime Atual: %s" % regime, "Pena Total Imposta: %s" % total, "Pena Cumprida Até Data Atual: %s" % cumprida,
              "Pena Remanescente: %s" % restante, "Total Interrupções: %s" % (interr or ""), "Saldo dias Remidos: %s" % (saldo or ""),
              "TÉRMINO DE PENA", "Data prevista para o Término da Pena: %s" % (term or ""),
              "CÁLCULOS PARA PROGRESSÃO DE REGIME:", "Data-base adotada no cálculo para progresso regime: %s" % (db_p or ""),
              "Data prevista para progressão de regime: %s" % (pr_p or ""),
              "CÁLCULOS PARA LIVRAMENTO CONDICIONAL:", "Data-base adotada no cálculo para livramento condicional: %s" % (db_l or ""),
              "Data prevista livramento condicional: %s" % (pr_l or ""), "PROCESSOS CRIMINAIS"]
    # processos criminais: uma página por processo (hiperlink do número na aba)
    crims = sorted((k for k in L if k.startswith("crim:")), key=lambda k: int(re.sub(r"\D", "", k) or 0))
    if "criminais" not in L:
        faltou.append("aba Processos Criminais")
    elif not crims and re.search(r"Processo Criminal", abas.get("criminais") or ""):
        faltou.append("páginas dos processos criminais")
    for k in crims:
        f = L[k].aba
        num = _kv(f, "Número Único")
        linhas += ["Número: %s" % num, "Tipo: %s" % _kv(f, "Tipo de Processo Criminal"),
                   "Juízo/Vara de condenação: %s" % _kv(f, "Vara de Origem"),
                   "Data do recebimento da denúncia: %s" % _kv(f, "Data de Recebimento da Denuncia"),
                   "Data da Sentença: %s" % _kv(f, "Data da Sentença"),
                   "Data do trânsito em julgado do Ministério Público: %s" % _kv(f, "Data de Trânsito em Julgado do Ministério Público"),
                   "Data do trânsito em julgado do processo: %s" % _kv(f, "Data de Trânsito Julgado do Processo"), "Observação:"]
        penas = _tabela(f, "Pena Imposta", "Regime de Pena")
        linhas += ["SENTENÇA/ACÓRDÃO/RECURSO (ATIVO)", "Pena total: %s" % (_col(penas[0], "Pena Imposta") if penas else ""),
                   "Regime imposto na sentença/acórdão:%s" % (_col(penas[0], "Regime de Pena") if penas else "")]
        arts = _tabela(f, "Lei", "Artigo")
        if not arts:
            faltou.append("artigos do processo %s" % num)
        for a in arts:
            linhas += ["Lei: %s" % _col(a, "Lei"), "Artigo da Lei: %s" % _col(a, "Artigo"), "Pena:%s" % _col(a, "Tipo Penal"),
                       "Pena Imposta: %s" % _col(a, "Pena Imposta"),
                       "Data da infração: %s Violência ou grave ameaça: %s Resultado morte: %s" % (
                           _col(a, "Data da Infração"), _col(a, "Violência ou Grave Ameaça"), _col(a, "Resultado Morte")),
                       "Reincidente comum:%s Reincidente específico: %s" % (_col(a, "Reincidente Comum"), _col(a, "Reincidente Específico")),
                       "Condenado por exercer comando de organização criminosa:%s" % _col(a, "Comando de Organização Criminosa"),
                       "Fração adotada no cálculo para progressão de regime: %s" % _col(a, "Fração Progressão"),
                       "Fração adotada no cálculo para livramento condicional: %s" % _col(a, "Fração Livramento"),
                       "Extinto:%s Suspenso: %s" % (_col(a, "Extinto"), _col(a, "Suspensão da Pena")),
                       "Data da extinção: %s" % _col(a, "Data da Extinção") if _col(a, "Data da Extinção") else ""]
    linhas.append("EVENTOS DE INÍCIO, REINÍCIO E INTERRRUPÇÃO(ÕES) DO CUMPRIMENTO DA PENA")
    evs = _tabela((L.get("eventos") or _ler("")).aba, "Tipo do Incidente", "Data de Referência")
    if "eventos" not in L:
        faltou.append("aba Eventos (prisões, solturas, interrupções)")
    for e in evs:
        d = e.get("_detalhe", "")
        linhas += ["Tipo:%s" % _col(e, "Tipo do Incidente"), "Motivo:%s" % _col(e, "Complemento")]
        if _det(d, "Complemento"):
            linhas.append("Complemento:%s" % _det(d, "Complemento"))
        dt = re.match(r"\d{2}/\d{2}/\d{4}", _col(e, "Data de Referência") or "")
        linhas += ["Data:%s" % (dt.group(0) if dt else ""), "Processos Selecionados:%s" % _det(d, "Processos Selecionados")]
    for chave, titulo in (("concedidos", "INCIDENTES CONCEDIDOS"), ("nao_concedidos", "INCIDENTES NÃO CONCEDIDOS"), ("pendentes", "INCIDENTES PENDENTES")):
        linhas.append(titulo)
        if chave not in L:
            faltou.append("aba " + {"concedidos": "Incidentes Concedidos", "nao_concedidos": "Incidentes Não-Concedidos", "pendentes": "Incidentes Pendentes"}[chave])
        for i in _tabela((L.get(chave) or _ler("")).aba, "Tipo do Incidente", "Complemento"):
            d = i.get("_detalhe", "")
            linhas.append("Tipo:%s" % _col(i, "Tipo do Incidente"))
            if _det(d, "Motivo"):
                linhas.append("Motivo:%s" % _det(d, "Motivo"))
            linhas.append("Complemento:%s" % _col(i, "Complemento"))
            if _det(d, "Data"):
                linhas.append("Data:%s" % _det(d, "Data"))
            linhas += ["Data Decisão: %s Data Referência:%s" % (_col(i, "Data de Decisão"), _col(i, "Data de Referência")),
                       "Processos Selecionados:%s" % _det(d, "Processos Selecionados")]
    linhas.append("Fim do Relatório")
    linhas.append("Processo Eletrônico - SEEU Gerado em: %s 00:00:00 Pág.: 1 de 1" % (gerado or rs.fmt(__import__("datetime").date.today())))
    return "\n".join(linhas), faltou


def ler(abas, gerado=""):
    """Registro no formato do RSPE (o mesmo que o leitor do APTO produz) + o que faltou ler. Sem o número do processo na
    página (sessão expirada, página de erro), não há registro: ({}, faltou)."""
    texto, faltou = montar_texto(abas, gerado)
    if not RE_CNJ.search(texto.split("Número Único:", 1)[-1][:40]):
        return {}, faltou + ["número do processo (a página não é a de um processo do SEEU)"]
    r = rs.extrair_paginas([texto], "abas do SEEU")
    r["_fonte"] = "abas do SEEU"
    if faltou:
        r["_abas_faltou"] = faltou
    return r, faltou
