#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSPE Scraper - SEEU
====================
Extrai dados do Relatório da Situação Processual Executória (RSPE) do SEEU
(PDF) e gera planilha Excel / CSV / JSON com:

  * nome, CPF, número do processo de execução, vara, data de geração
  * regime atual, penas (total, cumprida, remanescente, interrupções, remidos)
  * progressão de regime  (fração, data-base, previsão do SEEU se constar,
                           histórico de progressões e ESTIMATIVA de lapso)
  * livramento condicional (fração, previsão do SEEU se constar, ESTIMATIVA)
  * término de pena (previsão do SEEU se constar, ESTIMATIVA)
  * crimes (lei, artigo, pena imposta, data do fato, VGA, morte, reincidência)
  * indulto / comutação: incidentes registrados no RSPE + triagem de vedações
    (crime hediondo/equiparado, tráfico, organização criminosa, tortura etc.)

Uso:
    rspe_scraper.exe                          -> abre janela para escolher PDFs
    rspe_scraper.exe arq1.pdf arq2.pdf ...    -> processa os arquivos
    rspe_scraper.exe -d PASTA                 -> processa todos os PDFs da pasta
    rspe_scraper.exe ... -o saida.xlsx        -> define o arquivo de saída

As colunas marcadas como ESTIMATIVA são calculadas a partir dos eventos do
próprio RSPE (prisão, interrupções, remições) e das frações adotadas pelo
SEEU. Servem de triagem: o valor oficial é o do Atestado de Pena.
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from fractions import Fraction

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    sys.exit("Falta a biblioteca pdfplumber:  pip install pdfplumber")

VERSAO = "2.1.0"

# --------------------------------------------------------------------------- #
# utilidades
# --------------------------------------------------------------------------- #

RE_DATA = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
RE_CNJ = re.compile(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}")
RE_PENA_AMD = re.compile(r"(\d+)a(\d+)m(\d+)d")
RE_PENA_EXT = re.compile(r"(\d+)\s*ano\(s\),\s*(\d+)\s*m[êe]s\(es\)\s*e\s*(\d+)\s*dia\(s\)")


def to_date(s):
    try:
        return datetime.strptime(s.strip(), "%d/%m/%Y").date()
    except Exception:
        return None


def fmt(d):
    return d.strftime("%d/%m/%Y") if isinstance(d, date) else (d or "")


DIAS_ANO = 365  # SEEU: ano de 365 dias e mês de 30 (o remanescente vira término pelo calendário)


def pena_para_dias(txt):
    """'5a10m0d' ou '5 ano(s), 10 mês(es) e 0 dia(s)' -> dias (ano=365, mês=30: convenção do SEEU,
    conferida contra o término impresso no RSPE)."""
    if not txt:
        return None
    m = RE_PENA_AMD.search(txt) or RE_PENA_EXT.search(txt)
    if not m:
        return None
    a, me, d = (int(x) for x in m.groups())
    return a * DIAS_ANO + me * 30 + d


def pena_amd(txt):
    """'5a10m0d' -> (5, 10, 0) ou None."""
    if not txt:
        return None
    m = RE_PENA_AMD.search(txt) or RE_PENA_EXT.search(txt)
    return tuple(int(x) for x in m.groups()) if m else None


def amd_normal(a, m, d):
    """Normaliza anos/meses/dias como o SEEU (30 dias = 1 mês, 12 meses = 1 ano) e devolve um número comparável."""
    m += d // 30; d %= 30
    a += m // 12; m %= 12
    return a * 10000 + m * 100 + d


def dias_para_pena(n):
    if n is None:
        return ""
    neg = n < 0
    n = abs(int(n))
    a, r = divmod(n, DIAS_ANO)
    m = min(r // 30, 11)
    d = r - 30 * m
    return ("-" if neg else "") + "%da%dm%dd" % (a, m, d)


def parse_fracao(txt):
    """'1/6 - Comum' -> Fraction(1,6); '16% - ...' -> Fraction(16,100)."""
    if not txt:
        return None
    m = re.search(r"(\d+)\s*/\s*(\d+)", txt)
    if m:
        return Fraction(int(m.group(1)), int(m.group(2)))
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", txt)
    if m:
        return Fraction(m.group(1).replace(",", ".")).limit_denominator(1000) / 100
    return None


def campo(texto, rotulo, flags=re.I):
    """Valor após 'rotulo:' até o fim da linha."""
    m = re.search(re.escape(rotulo) + r"[ \t]*:?[ \t]*(.*)", texto, flags)
    return m.group(1).strip() if m else ""


def campo_data(texto, rotulo):
    v = campo(texto, rotulo)
    m = RE_DATA.search(v)
    return m.group(1) if m else ""


# --------------------------------------------------------------------------- #
# leitura do PDF
# --------------------------------------------------------------------------- #

RODAPE = re.compile(r"^Processo Eletr[ôo]nico\s*-\s*SEEU.*P[áa]g\.?:.*$", re.I)
CABECALHO = (
    "PODER JUDICIÁRIO",
    "RELATÓRIO DA SITUAÇÃO PROCESSUAL EXECUTÓRIA",
)


def ler_pdf(caminho):
    """Devolve (texto_limpo, vara, comarca, tribunal, data_geracao)."""
    paginas = []
    with pdfplumber.open(caminho) as pdf:
        for p in pdf.pages:
            paginas.append(p.extract_text() or "")
    bruto = "\n".join(paginas)

    linhas = [l.rstrip() for l in bruto.splitlines()]
    # cabeçalho: linhas 1-3 da primeira página
    tribunal_comarca = linhas[1].strip() if len(linhas) > 1 else ""
    vara = linhas[2].strip() if len(linhas) > 2 else ""
    tribunal, comarca = "", ""
    m = re.match(r"(\S+)\s*-\s*COMARCA DE\s*(.+)", tribunal_comarca, re.I)
    if m:
        tribunal, comarca = m.group(1), m.group(2).strip()

    geracao = ""
    m = re.search(r"Gerado em:\s*(\d{2}/\d{2}/\d{4})", bruto)
    if m:
        geracao = m.group(1)

    if "RELATÓRIO DA SITUAÇÃO PROCESSUAL EXECUTÓRIA" not in bruto.upper().replace("RELATORIO", "RELATÓRIO"):
        raise ValueError("não é um RSPE do SEEU")
    limpas = []
    for l in linhas:
        s = l.strip()
        if not s or RODAPE.match(s):
            continue
        if s in CABECALHO or s == tribunal_comarca or s == vara:
            continue
        limpas.append(s)
    return "\n".join(limpas), vara, comarca, tribunal, geracao


def secao(texto, inicio, fins):
    """Trecho entre o título 'inicio' e o primeiro dos títulos 'fins'."""
    i = texto.find(inicio)
    if i < 0:
        return ""
    i += len(inicio)
    fim = len(texto)
    for f in fins:
        j = texto.find(f, i)
        if 0 <= j < fim:
            fim = j
    return texto[i:fim]


TITULOS = [
    "CÁLCULOS DA PENA",
    "GRÁFICO REPRESENTATIVO",
    "PROCESSOS CRIMINAIS",
    "EVENTOS DE INÍCIO",
    "INCIDENTES CONCEDIDOS",
    "INCIDENTES NÃO CONCEDIDOS",
    "INCIDENTES NEGADOS",
    "INCIDENTES PENDENTES",
    "INCIDENTES EM ANÁLISE",
    "Fim do Relatório",
]


def outros(titulo):
    return [t for t in TITULOS if t != titulo]


# --------------------------------------------------------------------------- #
# blocos "Tipo: ... / Complemento: ... / Data ..."
# --------------------------------------------------------------------------- #

def blocos_tipo(trecho):
    """Divide um trecho em blocos que começam por 'Tipo:'."""
    partes = re.split(r"(?m)^(?=Tipo\s*:)", trecho)
    out = []
    for p in partes:
        p = p.strip()
        if not p.startswith("Tipo"):
            continue
        b = {
            "tipo": campo(p, "Tipo"),
            "motivo": campo(p, "Motivo"),
            "complemento": campo(p, "Complemento"),
            "data": campo_data(p, "Data:") if re.search(r"(?m)^Data\s*:", p) else "",
            "data_decisao": "",
            "data_referencia": "",
            "processos": campo(p, "Processos Selecionados"),
        }
        m = re.search(r"Data Decis[ãa]o\s*:\s*(\d{2}/\d{2}/\d{4})?", p)
        if m and m.group(1):
            b["data_decisao"] = m.group(1)
        m = re.search(r"Data Refer[êe]ncia\s*:\s*(\d{2}/\d{2}/\d{4})?", p)
        if m and m.group(1):
            b["data_referencia"] = m.group(1)
        out.append(b)
    return out


# --------------------------------------------------------------------------- #
# crimes
# --------------------------------------------------------------------------- #

def parse_crimes(trecho):
    """Trecho de PROCESSOS CRIMINAIS -> lista de dicts (um por lei/artigo)."""
    crimes = []
    processos = re.split(r"(?m)^(?=N[úu]mero\s*:)", trecho)
    for proc in processos:
        proc = proc.strip()
        if not proc.startswith("N"):
            continue
        _num = campo(proc, "Número")
        _msit = re.search(r"\(([^)]*)\)\s*$", _num)
        base = {
            "processo_criminal": re.sub(r"\s*\([^)]*\)\s*$", "", _num).strip(),
            "processo_situacao": (_msit.group(1).strip() if _msit else ""),
            "tipo_processo": campo(proc, "Tipo"),
            "vara_condenacao": campo(proc, "Juízo/Vara de condenação"),
            "data_denuncia": campo_data(proc, "Data do recebimento da denúncia"),
            "data_sentenca": campo_data(proc, "Data da Sentença"),
            "transito_mp": campo_data(proc, "Data do trânsito em julgado do Ministério Público"),
            "transito_processo": campo_data(proc, "Data do trânsito em julgado do processo"),
            "pena_total_processo": campo(proc, "Pena total"),
            "regime_sentenca": campo(proc, "Regime imposto na sentença/acórdão"),
        }
        m = RE_CNJ.search(base["processo_criminal"])
        if m:
            base["processo_criminal"] = m.group(0)

        leis = re.split(r"(?m)^(?=Lei\s*:)", proc)
        for lei in leis:
            lei = lei.strip()
            if not lei.startswith("Lei"):
                continue
            c = dict(base)
            c["lei"] = campo(lei, "Lei")
            c["artigo"] = campo(lei, "Artigo da Lei")
            m = re.search(r"(?m)^Pena\s*:\s*(.*?)(?=^Pena Imposta)", lei, re.S)
            c["tipo_penal"] = " ".join(m.group(1).split()) if m else campo(lei, "Pena")
            c["pena_imposta"] = campo(lei, "Pena Imposta")
            c["data_infracao"] = campo_data(lei, "Data da infração")
            c["vga"] = campo(lei, "Violência ou grave ameaça")[:1].upper()
            c["resultado_morte"] = campo(lei, "Resultado morte")[:1].upper()
            c["reincidente_comum"] = campo(lei, "Reincidente comum").strip()[:1].upper()
            if c["reincidente_comum"] not in ("S", "N"):
                c["reincidente_comum"] = ""
            c["reincidente_especifico"] = campo(lei, "Reincidente específico")[:1].upper()
            c["comando_orcrim"] = campo(lei, "Condenado por exercer comando de organização criminosa")[:1].upper()
            c["fracao_progressao"] = campo(lei, "Fração adotada no cálculo para progressão de regime")
            c["fracao_livramento"] = campo(lei, "Fração adotada no cálculo para livramento condicional")
            c["extinto"] = campo(lei, "Extinto")[:3]
            c["suspenso"] = re.sub(r"\s*Data de suspens.*", "", campo(lei, "Suspenso"))[:3]
            c["hediondo_ou_equiparado"] = "S" if e_hediondo(c) else "N"
            crimes.append(c)
    return crimes


# ------------------------- triagem de vedação a indulto -------------------- #

HEDIONDOS_CP = {  # Lei 8.072/90, art. 1º (rol atual)
    "121": "homicídio (só se qualificado, grupo de extermínio ou feminicídio)",
    "121-A": "feminicídio", "122": "induzimento ao suicídio (§§ 1º-2º)",
    "129": "lesão corporal (só §2º-A e §3º contra agentes de segurança)",
    "148": "sequestro/cárcere privado? não hediondo",  # não; mantido só p/ referência
    "157": "roubo (só §2º-A, §2º VI, §3º)", "158": "extorsão (só §3º)", "159": "extorsão mediante sequestro",
    "213": "estupro", "217-A": "estupro de vulnerável", "218-B": "favorecimento da prostituição de menor",
    "267": "epidemia com morte", "273": "falsificação de produto medicinal", "288-A": "milícia privada",
    "155": "furto (só §4º-A, explosivo)", "316": "concussão? não", "317": "corrupção passiva? não",
}
# Somente os que são hediondos em qualquer modalidade (sem depender do § / inciso):
HEDIONDOS_SEMPRE = {"121-A", "159", "213", "217-A", "218-B", "273"}
HEDIONDOS_CONDICIONAIS = {"121", "122", "129", "155", "157", "158"}
EQUIPARADOS = {
    "11343": {"33", "34", "36", "35"},          # tráfico (33 caput/§1º, 34, 36; 35 associação NÃO é hediondo, mas decretos vedam)
    "9455": {"1"},                                # tortura
    "13260": {"2", "3", "5", "6"},                # terrorismo
    "10826": {"16", "17", "18"},                  # Estatuto do Desarmamento (art. 16 §2º hediondo; 17/18 hediondos)
}
LEIS_VEDACAO_DECRETO = {
    "12850": "organização criminosa (Lei 12.850/13) - vedação nos decretos recentes",
    "2889": "genocídio",
    "11343": "tráfico de drogas (Lei 11.343/06, arts. 33 caput e §1º, 34 a 37) - vedação",
    "9455": "tortura",
    "13260": "terrorismo",
}


def num_lei(txt):
    m = re.search(r"(\d[\d.]*)\s*/\s*(\d{2,4})", txt or "")
    return m.group(1).replace(".", "") if m else ""


def num_art(txt):
    m = re.search(r"ART\.?\s*(\d+(?:-[A-Z])?)", txt or "", re.I)
    return m.group(1).upper() if m else ""


RE_PARAGRAFO = re.compile(r"^\s*§\s*(\d+)\s*[ºo°]?\s*(-\s*[A-Z])?\s*,?\s*([IVXL]+\b)?", re.I)


def paragrafo_inciso(c):
    """Parágrafo e inciso lidos do início do tipo penal impresso no RSPE:
    '§ 3º, I: ...' -> ('3', 'I'); '§ 2º-A, I:' -> ('2-A', 'I'); 'CAPUT: ...' -> ('', ''); 'PARÁGRAFO ÚNICO' -> ('pu', ''); ilegível -> None."""
    t = (c.get("tipo_penal") or "").strip()
    if not t:
        return None
    m = RE_PARAGRAFO.match(t)
    if m:
        par = m.group(1) + (m.group(2).replace(" ", "").upper() if m.group(2) else "")
        return (par, (m.group(3) or "").upper())
    tu = t.upper()
    if tu.startswith("CAPUT"):
        return ("", "")
    if tu.startswith("PAR") and "NICO" in tu[:20]:
        return ("pu", "")
    return None


def paragrafo_texto(c):
    """'§ 3º, I' / '§ 2º-A, I' / 'p. ú.' / '' (caput ou ilegível)."""
    pi = paragrafo_inciso(c)
    if not pi or not pi[0]:
        return ""
    if pi[0] == "pu":
        return "p. ú."
    num, suf = (pi[0].split("-", 1) + [""])[:2]
    return "§ %sº%s%s" % (num, ("-" + suf) if suf else "", (", " + pi[1]) if pi[1] else "")


def hediondo_condicional(c):
    """Para artigos cuja hediondez depende do parágrafo (base: hediondos.condicional_paragrafos):
    True/False pelo parágrafo impresso; None se o artigo não é condicional ou o parágrafo é ilegível."""
    try:
        import rspe_regras as _rg
        regras = ((_rg.hediondos() or {}).get("condicional_paragrafos") or {})
    except Exception:
        regras = {}
    lei, art = num_lei(c.get("lei")), num_art(c.get("artigo"))
    if not (lei in ("2848", "") or ("PENAL" in (c.get("lei") or "").upper() and "MILITAR" not in (c.get("lei") or "").upper())):
        return None
    if art not in regras or art.startswith("_"):
        return None
    pi = paragrafo_inciso(c)
    if pi is None:
        return None
    par, inc = pi
    for regra in regras[art]:
        partes = regra.replace("§", "").split()
        if partes and partes[0].upper() == par and (len(partes) == 1 or partes[1].upper() == inc):
            return True
    return False


def hediondo_desde(c):
    """(data, lei) a partir da qual o tipo do crime é hediondo, pela tabela hediondos.desde da base jurídica; (None, '') se não tabelado."""
    try:
        import rspe_regras as _rg
        tab = (_rg.hediondos() or {}).get("desde", {}) or {}
    except Exception:
        return None, ""
    lei, art = num_lei(c.get("lei")) or "2848", num_art(c.get("artigo"))
    if "PENAL" in (c.get("lei") or "").upper() and "MILITAR" not in (c.get("lei") or "").upper():
        lei = "2848"
    if not art:
        return None, ""
    t = (c.get("tipo_penal") or "").strip()
    chaves = []
    mp = re.match(r"§\s*(\d+[ºo°]?(?:-[A-Z])?)\s*,?\s*([IVXL]+)?", t)
    if mp:
        par = mp.group(1).replace("º", "").replace("o", "").replace("°", "")
        if mp.group(2):
            chaves.append("%s:%s §%s %s" % (lei, art, par, mp.group(2)))
        chaves.append("%s:%s §%s" % (lei, art, par))
    chaves.append("%s:%s" % (lei, art))
    for k in chaves:
        v = tab.get(k)
        if isinstance(v, dict) and v.get("desde"):
            try:
                return datetime.strptime(v["desde"], "%Y-%m-%d").date(), v.get("lei", "")
            except Exception:
                return None, ""
    return None, ""


def hediondo_na_epoca(c):
    """False se a tabela 'desde' mostra que o fato é anterior à lei que tornou o tipo hediondo; True/None caso contrário."""
    d, lei = hediondo_desde(c)
    fato = to_date(c.get("data_infracao") or "")
    if d and fato and fato < d:
        return False
    return True if d else None


def e_hediondo(c):
    """Hediondez pelo rótulo do SEEU ou pelo rol da base jurídica (Lei 8.072/90, art. 1º), respeitada a lei da época do fato."""
    if hediondo_na_epoca(c) is False:
        return False
    if "HEDIONDO" in ((c.get("fracao_progressao") or "") + (c.get("fracao_livramento") or "")).upper():
        return True
    try:
        import rspe_regras as _rg
        h = _rg.hediondos()
    except Exception:
        h = {}
    lei, art = num_lei(c.get("lei")), num_art(c.get("artigo"))
    if not art:
        return False
    if lei in ("2848", "") or ("PENAL" in (c.get("lei") or "").upper() and "MILITAR" not in (c.get("lei") or "").upper()):
        if art in h.get("lei_8072_art1_cp_sempre", HEDIONDOS_SEMPRE):
            return True
        return bool(hediondo_condicional(c))  # pelo parágrafo/inciso impresso (época já conferida acima)
    eq = h.get("equiparados", EQUIPARADOS)
    if lei in eq and art in eq[lei]:
        if lei == "11343" and art == "33" and "§ 4" in (c.get("tipo_penal") or ""):
            return False
        return True
    pu = h.get("paragrafo_unico", {})
    regra = pu.get(lei)
    if isinstance(regra, dict):
        return regra.get(art) == "sempre"
    if isinstance(regra, list):
        return art in regra
    return False


def triagem_indulto(crimes):
    """Devolve (situacao, motivos[]) — apenas triagem, a lei do decreto muda ano a ano."""
    motivos = []
    for c in crimes:
        lei, art = num_lei(c.get("lei")), num_art(c.get("artigo"))
        nome = "%s art. %s" % (c.get("lei", "").split(" - ")[0], art or "?")
        if c.get("extinto", "").upper().startswith("S"):
            continue
        if e_hediondo(c):
            motivos.append("crime hediondo/equiparado: " + nome)
        elif lei in ("2848", "") and art in HEDIONDOS_CONDICIONAIS:
            motivos.append("possível hediondo conforme §/inciso (%s): conferir - %s" % (art, nome))
        if lei in LEIS_VEDACAO_DECRETO and not e_hediondo(c):
            motivos.append(LEIS_VEDACAO_DECRETO[lei] + " - " + nome)
        if c.get("vga") == "S":
            motivos.append("crime com violência ou grave ameaça: " + nome)
        if c.get("resultado_morte") == "S":
            motivos.append("resultado morte: " + nome)
        if c.get("comando_orcrim") == "S":
            motivos.append("comando de organização criminosa: " + nome)
    motivos = list(dict.fromkeys(motivos))
    if not motivos:
        return "SEM VEDAÇÃO APARENTE (conferir requisitos do decreto vigente)", motivos
    return "POSSÍVEL VEDAÇÃO - conferir decreto", motivos


# --------------------------------------------------------------------------- #
# cumprimento de pena (estimativas)
# --------------------------------------------------------------------------- #

def periodos_custodia_detalhe(eventos):
    """Como periodos_custodia, mas devolve (inicio, fim|None, motivo, processos) do evento de início."""
    per = []
    aberto = None
    for e in eventos:
        d = to_date(e.get("data", ""))
        if not d:
            continue
        t = (e.get("tipo") or "").upper()
        if "INTERRUP" in t:
            if aberto:
                per.append((aberto[0], d, aberto[1], aberto[2]))
                aberto = None
        else:
            if not aberto:
                aberto = (d, (e.get("motivo") or "").strip(), (e.get("processos") or "").strip())
    if aberto:
        per.append((aberto[0], None, aberto[1], aberto[2]))
    return per


def periodos_custodia(eventos):
    """A partir dos eventos, devolve lista de (inicio, fim|None)."""
    per = []
    aberto = None
    for e in eventos:
        d = to_date(e.get("data", ""))
        if not d:
            continue
        t = (e.get("tipo") or "").upper()
        if "INTERRUP" in t:
            if aberto:
                per.append((aberto, d))
                aberto = None
        else:  # PRISÃO / INÍCIO / REINÍCIO
            if not aberto:
                aberto = d
    if aberto:
        per.append((aberto, None))
    return per


def dias_cumpridos_ate(periodos, remicoes, ate):
    total = 0
    for ini, fim in periodos:
        if ini > ate:
            continue
        f = fim if (fim and fim <= ate) else ate
        total += (f - ini).days
    for d, n in remicoes:
        if d and d <= ate:
            total += n
    return total


def cumprida_seeu_dias(campos):
    """Pena cumprida na data do RSPE, em dias, pelos números do próprio SEEU:
    pena total (ano 365 / mês 30) menos os dias reais entre a geração do RSPE e o término impresso.
    Sem término (pena interrompida), usa a 'Pena cumprida' impressa. None se não houver dados."""
    total = pena_para_dias(campos.get("pena_total"))
    ger = to_date(campos.get("data_geracao_rspe") or "")
    term = to_date(campos.get("termino_previsao_seeu") or "")
    if total and ger and term:
        return total - (term - ger).days, ger
    c = pena_para_dias(campos.get("pena_cumprida"))
    return (c, ger) if (c is not None and ger) else (None, ger)


def cumprido_na_data(campos, periodos, remicoes, ref):
    """Pena cumprida em 'ref' ancorada no SEEU: cumprida na data do RSPE menos a custódia real
    entre ref e a data do RSPE e menos as remições concedidas depois de ref.
    Sem âncora, soma os períodos de custódia e as remições (dias reais)."""
    base, ger = cumprida_seeu_dias(campos)
    if base is None or not ger:
        return dias_cumpridos_ate(periodos, remicoes, ref), "custódia + remições (dias de calendário)"
    if ref >= ger:
        return base, "pena cumprida do SEEU em %s" % fmt(ger)
    depois = 0
    for ini, fim in periodos:
        a, b = max(ini, ref), min(fim or ger, ger)
        if b > a:
            depois += (b - a).days
    rem_depois = sum(n for d, n in remicoes if d and ref < d <= ger)
    return max(0, base - depois - rem_depois), "pena cumprida do SEEU em %s menos %d dia(s) de custódia e %d de remição posteriores a %s" % (
        fmt(ger), depois, rem_depois, fmt(ref))


def em_custodia(periodos, hoje):
    return any(ini <= hoje and (fim is None or fim > hoje) for ini, fim in periodos)


def situacao_execucao(campos, eventos, incidentes, crimes, hoje):
    """Leitura de apoio (sem projetar datas: progressão, livramento e término são os do SEEU):
    situação do cumprimento pelos eventos, fração mais gravosa impressa entre os crimes ativos e data-base."""
    out = {}
    periodos = periodos_custodia(eventos)
    out["situacao_cumprimento"] = "EM CUMPRIMENTO" if em_custodia(periodos, hoje) else "PENA INTERROMPIDA (sem evento de reinício)"
    fp = [parse_fracao(c.get("fracao_progressao")) for c in crimes if not c.get("extinto", "").upper().startswith("S")]
    fl = [parse_fracao(c.get("fracao_livramento")) for c in crimes if not c.get("extinto", "").upper().startswith("S")]
    fp = [f for f in fp if f]
    fl = [f for f in fl if f]
    out["fracao_progressao_aplicada"] = str(max(fp)) if fp else ""
    out["fracao_livramento_aplicada"] = str(max(fl)) if fl else ""
    # data-base: última FIXAÇÃO/ALTERAÇÃO DE REGIME (data de referência)
    data_base = None
    for i in incidentes:
        if "REGIME" in (i.get("tipo") or "").upper():
            d = to_date(i.get("data_referencia") or i.get("data_decisao") or "")
            if d and (data_base is None or d > data_base):
                data_base = d
    out["data_base"] = fmt(data_base)
    return out


def campos_faltantes(r):
    """Dados essenciais que não foram lidos do RSPE (layout diferente, página faltando, guia sem cálculo)."""
    falta = []
    for k, rot in (("nome", "nome"), ("data_geracao_rspe", "data de geração"), ("pena_total", "pena total"),
                   ("pena_cumprida", "pena cumprida"), ("regime_atual", "regime atual")):
        if not r.get(k):
            falta.append(rot)
    ativos = [c for c in r.get("_crimes", []) if not c.get("extinto", "").upper().startswith("S")]
    if not r.get("_crimes"):
        falta.append("crimes")
    else:
        if any(not c.get("pena_imposta") for c in ativos):
            falta.append("pena de algum crime")
        if any(not c.get("data_infracao") for c in ativos):
            falta.append("data do fato de algum crime")
    if not r.get("termino_previsao_seeu") and "INTERROMPIDA" not in (r.get("situacao_cumprimento") or "") and not r.get("execucao_extinta"):
        falta.append("término")
    return falta


def lei_curta(lei):
    """'2848/40 - Código Penal' -> 'CP'; '11343/06 - Lei de Drogas' -> 'Lei 11.343/06'."""
    num = (lei or "").split(" - ")[0].strip()
    if num.startswith("2848/") or "PENAL" in (lei or "").upper() and "MILITAR" not in (lei or "").upper():
        return "CP"
    if num.startswith("1001/"):
        return "CPM"
    m = re.match(r"(\d+)/(\d+)", num)
    if m:
        n = m.group(1)
        n = "{:,}".format(int(n)).replace(",", ".") if len(n) > 3 else n
        return "Lei %s/%s" % (n, m.group(2))
    return num or (lei or "")


def saldo_remidos_num(txt):
    """'661 dias (661 dias remidos - 0 dias perdidos)' -> (661, 0)."""
    t = txt or ""
    m = re.search(r"(\d+)\s*dias remidos\s*-\s*(\d+)\s*dias perdidos", t, re.I)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"\s*(\d+)", t)
    return (int(m.group(1)) if m else 0), 0


def crimes_curto(crimes):
    """'art. 180 CP; art. 33 Lei 11.343/06 (x2)'."""
    itens = []
    ativos = [c for c in crimes if not c.get("extinto", "").upper().startswith("S")]
    if not ativos and crimes:
        return "todos extintos"
    for c in ativos:
        art = num_art(c.get("artigo"))
        if art:
            par = paragrafo_texto(c)
            txt = "art. %s%s %s" % (art, (" " + par) if par else "", lei_curta(c.get("lei")))
        else:
            txt = "art. n/i %s" % lei_curta(c.get("lei"))
        itens.append(txt)
    cont = {}
    ordem = []
    for x in itens:
        if x not in cont:
            ordem.append(x)
        cont[x] = cont.get(x, 0) + 1
    return "; ".join(x + (" (x%d)" % cont[x] if cont[x] > 1 else "") for x in ordem)


def pena_curta(txt):
    d = pena_para_dias(txt)
    return dias_para_pena(d) if d is not None else (txt or "")


# --------------------------------------------------------------------------- #
# faltas (indicadores no RSPE)
# --------------------------------------------------------------------------- #

RE_FALTA = re.compile(r"FALTA|REGRESS|PERDA|PERDID|FUGA|EVAS|SAN[ÇC][ÃA]O|RDD|DISCIPLIN|ISOLAMENTO", re.I)


def _rotulo_incidente(i):
    tipo, comp = i.get("tipo", ""), i.get("complemento", "")
    if "REGIME" in tipo.upper() and comp:
        return " ".join(comp.split())
    return " ".join(("%s %s" % (tipo, comp)).split())


def faltas(campos, eventos, incidentes, hoje):
    """O RSPE não lista faltas formalmente; procura indícios (regressão, perda de
    remidos, fuga, sanção) nos últimos 12 meses antes da geração do relatório."""
    achados = []
    limite = hoje - timedelta(days=365)
    for i in incidentes:
        txt = _rotulo_incidente(i)
        if RE_FALTA.search(txt):
            d = to_date(i.get("data_referencia") or i.get("data_decisao") or "")
            if d and d >= limite:
                achados.append("%s (%s)" % (txt, fmt(d)))
    for e in eventos:
        txt = "%s %s" % (e.get("tipo", ""), e.get("motivo", ""))
        if re.search(r"FUGA|EVAS", txt, re.I):
            d = to_date(e.get("data", ""))
            if d and d >= limite:
                achados.append("%s (%s)" % (" ".join(txt.split()), fmt(d)))
    m = re.search(r"(\d+)\s*dias perdidos", campos.get("saldo_remidos", ""), re.I)
    # só vira indício "sem data" se o RSPE não trouxer incidente datado da falta/perda (homologação, dias perdidos)
    datados = [i for i in incidentes if re.search(r"FALTA GRAVE|PERDIDOS", (i.get("tipo") or ""), re.I)
               and to_date(i.get("data_referencia") or i.get("data_decisao") or "")]
    if m and int(m.group(1)) > 0 and not datados:
        achados.append("%s dias remidos perdidos (data não consta)" % m.group(1))
    achados = list(dict.fromkeys(achados))
    return {
        "falta_12m": "SIM" if achados else "não consta",
        "falta_12m_detalhe": "; ".join(achados),
    }


# --------------------------------------------------------------------------- #
# indulto / comutação - Decretos 12.338/2024 e 12.790/2025 (mesmo art. 1º e art. 6º)
# --------------------------------------------------------------------------- #

DECRETOS = {"2024": date(2024, 12, 25), "2025": date(2025, 12, 25)}

ART1_LEIS = {  # lei -> (inciso, descrição, teto de pena em anos que afasta a vedação ou None)
    "9455": ("II", "tortura", None),
    "9613": ("III", "lavagem de dinheiro", 4),
    "12850": ("IV", "organização criminosa", None),
    "13260": ("V", "terrorismo", None),
    "7716": ("VI", "racismo", None),
    "2889": ("VIII", "genocídio", None),
    "7492": ("IX", "crimes contra o sistema financeiro", 4),
    "14133": ("X", "crimes em licitações", 4),
    "8666": ("X", "crimes em licitações", 4),
    "9605": ("XIV", "crimes ambientais", None),
    "13869": ("XVI", "abuso de autoridade", None),
    "11340": ("XVII", "violência contra a mulher (Lei Maria da Penha)", None),
    "13718": ("XVII", "violência contra a mulher", None),
    "14192": ("XVII", "violência política contra a mulher", None),
    "1001": ("XIX", "Código Penal Militar (correspondente aos incisos I a XVIII)", None),
}
ART1_CP = {  # artigo do CP -> (inciso, descrição, teto)
    "288-A": ("IV", "constituição de milícia privada", None),
    "149": ("VII", "redução a condição análoga à de escravo", None),
    "149-A": ("VII", "tráfico de pessoas", None),
    "215": ("XI", "violação sexual mediante fraude", None),
    "216-A": ("XI", "assédio sexual", None),
    "217-A": ("XI", "estupro de vulnerável", None),
    "218": ("XI", "mediação para satisfazer lascívia", None),
    "218-A": ("XI", "satisfação de lascívia na presença de menor", None),
    "218-B": ("XI", "favorecimento da prostituição de vulnerável", None),
    "218-C": ("XI", "divulgação de cena de estupro", None),
    "121-A": ("XVII", "feminicídio", None),
    "147-A": ("XVII", "perseguição (stalking)", None),
    "333": ("XII", "corrupção ativa", 4),
}
for _a in range(312, 320):
    ART1_CP[str(_a)] = ("XII", "crime contra a administração pública (art. %d)" % _a, 4)
ART1_CP_RANGE = [("359-I", "359-R", "XV", "crimes contra o Estado Democrático de Direito")]
ART1_ECA = {str(a): ("XIII", "crime do ECA (art. %d)" % a, None) for a in range(239, 245)}
ART1_ECA["244-A"] = ("XIII", "exploração sexual de menor (ECA 244-A)", None)
ART1_ECA["244-B"] = ("XIII", "corrupção de menores (ECA 244-B)", None)
ART1_DROGAS = {"33", "34", "35", "36", "37", "39"}


def _base_decretos():
    try:
        import rspe_regras as _rg
        return (_rg.carregar() or {}).get("decretos_indulto", {}) or {}
    except Exception:
        return {}


def carregar_tabelas_decretos():
    """Sobrepõe as tabelas embutidas com as da base jurídica (decretos_indulto), quando presentes."""
    global DECRETOS, ART1_LEIS, ART1_CP, ART1_ECA, ART1_DROGAS, PATRIMONIO_CP
    b = _base_decretos()
    try:
        refs = b.get("referencias") or {}
        if refs:
            DECRETOS = {ano: to_date_iso(v.get("data")) for ano, v in refs.items() if to_date_iso(v.get("data"))}
        if b.get("art1_leis"):
            ART1_LEIS = {k: tuple(v) for k, v in b["art1_leis"].items()}
        if b.get("art1_cp"):
            cp = {k: tuple(v) for k, v in b["art1_cp"].items()}
            for fx in b.get("art1_cp_faixas") or []:
                for a in range(int(fx["de"]), int(fx["ate"]) + 1):
                    cp[str(a)] = (fx["inciso"], "%s (art. %d)" % (fx.get("descricao", ""), a), fx.get("teto_anos"))
            ART1_CP = cp
        if b.get("art1_eca"):
            e = b["art1_eca"]
            eca = {str(a): (e.get("inciso", "XIII"), "crime do ECA (art. %d)" % a, None) for a in range(int(e["de"]), int(e["ate"]) + 1)}
            for x in e.get("extras") or []:
                eca[str(x)] = (e.get("inciso", "XIII"), "crime do ECA (art. %s)" % x, None)
            ART1_ECA = eca
        if b.get("art1_drogas"):
            ART1_DROGAS = set(str(x) for x in b["art1_drogas"])
        try:
            import rspe_regras as _rg
            p = _rg.patrimonio()
            if p:
                PATRIMONIO_CP = set(str(x) for x in p)
        except Exception:
            pass
    except Exception:
        pass


def to_date_iso(txt):
    try:
        return datetime.strptime(str(txt), "%Y-%m-%d").date()
    except Exception:
        return None


def art9_param(inciso, chave, padrao):
    """Parâmetro do art. 9º na base jurídica (decretos_indulto.art9_incisos), com valor de reserva."""
    try:
        v = (_base_decretos().get("art9_incisos") or {}).get(inciso, {}).get(chave)
        return padrao if v is None else v
    except Exception:
        return padrao


def crime_patrimonial(c):
    """Crime contra o patrimônio do CP (Título II) - arts. 155 a 180."""
    return (num_lei(c.get("lei")) in ("2848", "") or "PENAL" in (c.get("lei") or "").upper()) and num_art(c.get("artigo")) in PATRIMONIO_CP


def _sem_acento(t):
    import unicodedata
    return "".join(ch for ch in unicodedata.normalize("NFD", t or "") if unicodedata.category(ch) != "Mn").upper()


RE_VD_FORTE = re.compile(r"VIOLENCIA DOMESTICA|MARIA DA PENHA|11\.?340|CONTRA A MULHER|SEXO FEMININO|FEMINICIDIO|VIOLENCIA DE GENERO")


def violencia_domestica(c):
    """Contexto de violência doméstica/contra a mulher no crime, pelo que o RSPE traz.
    ('sim', motivo): vara especializada, Lei 11.340, art. 129 § 13, 'sexo feminino' etc. no tipo;
    ('provavel', motivo): art. 129 §§ 9º a 11 sem esse sinal (a vítima pode não ser mulher); None."""
    vara = _sem_acento(c.get("vara_condenacao"))
    tipo = _sem_acento(c.get("tipo_penal"))
    lei, art = num_lei(c.get("lei")), num_art(c.get("artigo"))
    if lei == "11340":
        return ("sim", "crime da Lei 11.340/06")
    if RE_VD_FORTE.search(vara) or "VIOLENCIA DOMESTICA" in vara or ("DOMESTICA" in vara and "MULHER" in vara):
        return ("sim", "condenado por: %s" % (c.get("vara_condenacao") or "vara de violência doméstica"))
    if RE_VD_FORTE.search(tipo):
        return ("sim", "tipo penal indica violência contra a mulher")
    if art == "129" and (lei in ("2848", "") or "PENAL" in (c.get("lei") or "").upper()):
        m = re.match(r"\s*§\s*(\d+)", c.get("tipo_penal") or "")
        par = m.group(1) if m else ""
        if par == "13":
            return ("sim", "art. 129, § 13 (lesão contra a mulher por razões da condição do sexo feminino)")
        if par in ("9", "10", "11"):
            return ("provavel", "art. 129, § %sº (violência doméstica): confirmar se a vítima é mulher" % par)
    return None


def impeditivo_decreto(c):
    """Devolve (inciso, motivo) se o crime está no art. 1º dos Decretos 12.338/24 e 12.790/25, senão None."""
    if c.get("extinto", "").upper().startswith("S"):
        return None
    lei, art = num_lei(c.get("lei")), num_art(c.get("artigo"))
    pena_anos = (pena_para_dias(c.get("pena_imposta")) or 0) / float(DIAS_ANO)
    codigo_penal = lei in ("2848", "") or "PENAL" in (c.get("lei") or "").upper()
    if e_hediondo(c):
        return ("I", "crime hediondo ou equiparado (Lei 8.072/90)")
    if lei == "11343" and art in ART1_DROGAS:
        if art == "33" and (c.get("tipo_penal") or "").strip().startswith("§ 4"):
            return None  # tráfico privilegiado: não é impeditivo (STJ Tema 1336; STF Tema 1400; PSV 125)
        return ("XVIII", "tráfico de drogas (art. %s da Lei 11.343/06)" % art)
    if lei == "8069" and art in ART1_ECA:
        return ART1_ECA[art][:2]
    vd = violencia_domestica(c)
    if vd and vd[0] == "sim":
        return ("XVII", "violência contra a mulher (Lei 11.340/06) - %s" % vd[1])
    if lei in ART1_LEIS:
        inc, desc, teto = ART1_LEIS[lei]
        if teto and pena_anos <= teto:
            return None
        return (inc, desc)
    if codigo_penal and art:
        if art in ART1_CP:
            inc, desc, teto = ART1_CP[art]
            if teto and pena_anos <= teto:
                return None
            return (inc, desc)
        m = re.match(r"359-([I-R])$", art)
        if m:
            return ("XV", "crime contra o Estado Democrático de Direito (art. %s)" % art)
    return None


# ---------------- Decreto 11.302/2022 (indulto natalino de 2022) ----------------
DECRETO_2022_REF = date(2022, 12, 25)
ART7_2022_LEIS = {"9455": "III, a: tortura (Lei 9.455/97)", "9613": "III, b: lavagem de dinheiro (Lei 9.613/98)",
                  "11340": "III, c: violência doméstica (Lei 11.340/06)", "12850": "III, d: organização criminosa (Lei 12.850/13)",
                  "13260": "III, e: terrorismo (Lei 13.260/16)"}
ART7_2022_CP = {"215": "IV", "216-A": "IV", "217-A": "IV", "218": "IV", "218-A": "IV", "218-B": "IV", "218-C": "IV",
                "312": "V", "316": "V", "317": "V", "333": "V"}
ART7_2022_ECA = ["240", "241", "241-A", "241-B", "241-C", "241-D", "241-E", "242", "243", "244", "244-A", "244-B"]


def pena_maxima_abstrata(c):
    """Pena máxima em abstrato (dias) lida do tipo penal impresso no RSPE:
    'Reclusão: 6 anos e 8 meses a 16 anos e 8 meses', 'Detenção: 2 meses a 2 anos', 'Reclusão: 1 a 4 anos'."""
    t = c.get("tipo_penal") or ""
    lei, art = num_lei(c.get("lei")) or "2848", num_art(c.get("artigo"))
    if lei == "11343" and art == "33" and t.startswith("§ 4"):
        return int(15 * DIAS_ANO * 5 / 6)  # tráfico privilegiado: máximo de 15 anos com a redução mínima de 1/6
    m = re.search(r"(Reclus[ãa]o|Deten[çc][ãa]o|Pris[ãa]o simples)\s*:\s*(.+?)(?:\s+(?:E|OU|e|ou)\s+Multa|\s+Sem\s+Multa|$)", t)
    if not m:
        # texto do tipo cortado pelo SEEU: tabela editável da base jurídica (pena_maxima_abstrata)
        try:
            import rspe_regras as _rg
            tab = (_rg.carregar() or {}).get("pena_maxima_abstrata", {})
        except Exception:
            tab = {}
        mp = re.match(r"§\s*(\d+[ºo°]?(?:-[A-Z])?|único)", t)
        chave = "%s:%s" % (lei, art)
        if mp:
            chave += " §" + mp.group(1).replace("º", "").replace("o", "").replace("°", "")
        v = tab.get(chave)
        if v is None and not mp and t.upper().startswith("CAPUT"):
            v = tab.get("%s:%s" % (lei, art))
        if v is None:
            return None
        c["_pena_max_fonte"] = "tabela"
        return int(float(v) * DIAS_ANO)
    faixa = m.group(2)
    partes = re.split(r"\s+a\s+", faixa, maxsplit=1)
    maximo = partes[-1].strip()
    anos = meses = dias = 0
    ma = re.search(r"(\d+)\s*ano", maximo)
    mm = re.search(r"(\d+)\s*m[eê]s", maximo)
    md = re.search(r"(\d+)\s*dia", maximo)
    if ma:
        anos = int(ma.group(1))
    if mm:
        meses = int(mm.group(1))
    if md:
        dias = int(md.group(1))
    if not (ma or mm or md):
        mn = re.match(r"(\d+)", maximo)
        if not mn:
            return None
        # "1 a 4 anos" -> unidade vem do fim da faixa
        if "ano" in faixa:
            anos = int(mn.group(1))
        elif "m" in faixa:
            meses = int(mn.group(1))
        else:
            return None
    return anos * DIAS_ANO + meses * 30 + dias


def exclusao_art7_2022(c):
    """Devolve texto do inciso do art. 7º do Decreto 11.302/2022 que exclui o crime, ou None."""
    lei, art = num_lei(c.get("lei")), num_art(c.get("artigo"))
    codigo_penal = lei in ("2848", "") or "PENAL" in (c.get("lei") or "").upper()
    if e_hediondo(c):
        return "I: hediondo ou equiparado (Lei 8.072/90)"
    vd = violencia_domestica(c)
    if vd and vd[0] == "sim":
        return "III, c: violência doméstica (Lei 11.340/06) - %s" % vd[1]
    if c.get("vga") == "S":
        return "II: praticado com violência ou grave ameaça"
    if lei in ART7_2022_LEIS:
        return ART7_2022_LEIS[lei]
    if codigo_penal and art in ART7_2022_CP:
        return "%s: art. %s do CP" % (ART7_2022_CP[art], art)
    if lei == "11343" and art in ("33", "34", "36"):
        if art == "33" and "§ 4" in (c.get("tipo_penal") or ""):
            return None  # exceção expressa: art. 33, § 4º
        return "VI: art. %s da Lei 11.343/06" % art
    if lei == "8069" and art in ART7_2022_ECA:
        return "VIII: art. %s do ECA" % art
    if lei == "1001":
        return "VII: crime militar correspondente (verificar)"
    return None


def analise_decreto_2022(campos, crimes, eventos, incidentes):
    """Decreto 11.302/2022: art. 5º (pena máxima em abstrato do crime ≤ 5 anos, crime a crime - parágrafo único),
    art. 4º (maiores de 70 anos com 1/3 cumprido), art. 1º (saúde - laudo), art. 7º (exclusões), art. 9º (independe
    de trânsito em julgado). Não exige fração cumprida nem regime. STF: ADI 7.330 suspendeu o trecho relativo a
    agentes de segurança (arts. 2º, 3º e 6º) - não avaliado aqui; o art. 5º foi mantido pelo STF em 2025 (RE 1.450.100)."""
    ref = DECRETO_2022_REF
    out = {}
    ativos = [c for c in crimes if not c.get("extinto", "").upper().startswith("S")]
    linhas, alcanca, verificar = [], [], []
    for c in ativos:
        nome = "art. %s %s" % (num_art(c.get("artigo")) or "?", lei_curta(c.get("lei")))
        fato = to_date(c.get("data_infracao") or "")
        excl = exclusao_art7_2022(c)
        if excl:
            linhas.append("✗ %s: excluído pelo art. 7º, %s" % (nome, excl))
            continue
        pm = pena_maxima_abstrata(c)
        if pm is None:
            linhas.append("? %s: pena máxima em abstrato não lida do RSPE - conferir o tipo penal" % nome)
            verificar.append(nome)
            continue
        if fato and fato > ref:
            linhas.append("✗ %s: fato de %s, posterior ao decreto" % (nome, fmt(fato)))
            continue
        if pm <= 5 * DIAS_ANO:
            tr = to_date(c.get("transito_processo") or c.get("transito_mp") or "")
            if tr and tr > ref:
                linhas.append("? %s: pena máxima em abstrato %s ≤ 5 anos (art. 5º), mas trânsito em %s, depois de 25/12/2022 - art. 9º admite sem trânsito; conferir" % (nome, dias_para_pena(pm), fmt(tr)))
                verificar.append(nome)
            else:
                linhas.append("✓ %s: pena máxima em abstrato %s ≤ 5 anos (art. 5º)%s" % (nome, dias_para_pena(pm), " - tipo cortado no RSPE, valor da tabela da base jurídica" if c.get("_pena_max_fonte") else ""))
                alcanca.append(nome)
        else:
            linhas.append("✗ %s: pena máxima em abstrato %s supera 5 anos" % (nome, dias_para_pena(pm)))
    idade = _idade_em(campos.get("data_nascimento"), ref)
    pena_total = pena_para_dias(campos.get("pena_total"))
    if idade is not None and idade >= 70 and pena_total:
        periodos = periodos_custodia(eventos)
        cumprido = dias_cumpridos_ate(periodos, [], ref)
        if not any(exclusao_art7_2022(c) for c in ativos):
            if cumprido >= pena_total / 3.0:
                linhas.append("✓ art. 4º: %d anos em 25/12/2022 e 1/3 cumprido (%s de %s)" % (idade, dias_para_pena(cumprido), dias_para_pena(pena_total)))
                alcanca.append("art. 4º (idade)")
            else:
                linhas.append("✗ art. 4º: %d anos, mas 1/3 não cumprido até 25/12/2022 (%s de %s)" % (idade, dias_para_pena(cumprido), dias_para_pena(pena_total)))
    linhas.append("? art. 1º: saúde (paraplegia, doença grave, terminal) - não aferível pelo RSPE (laudo médico)")
    linhas.append("Obs.: art. 9º - indulto cabe mesmo sem trânsito em julgado ou guia; art. 8º - não alcança PRD, multa e sursis; "
                  "arts. 2º, 3º e 6º (agentes de segurança) com eficácia discutida na ADI 7.330 - não avaliados.")
    if not ativos:
        out["indulto_2022"], out["indulto_2022_status"] = "sem crimes ativos no RSPE", "nao"
    elif alcanca and len(alcanca) >= len([c for c in ativos]):
        out["indulto_2022"] = "POSSÍVEL: art. 5º (todos os crimes com pena máxima ≤ 5 anos)"
        out["indulto_2022_status"] = "possivel"
    elif alcanca:
        out["indulto_2022"] = "POSSÍVEL (parcial): %s" % ", ".join(alcanca)
        out["indulto_2022_status"] = "possivel"
    elif verificar:
        out["indulto_2022"] = "A VERIFICAR: %s" % ", ".join(verificar)
        out["indulto_2022_status"] = "verificar"
    else:
        if all(to_date(c.get("data_infracao") or "") and to_date(c.get("data_infracao")) > ref for c in ativos):
            out["indulto_2022"] = "não se aplica: fatos posteriores a 25/12/2022"
        elif all(exclusao_art7_2022(c) for c in ativos):
            out["indulto_2022"] = "excluído (art. 7º)"
        else:
            out["indulto_2022"] = "não atinge: pena máxima em abstrato superior a 5 anos (art. 5º)"
        out["indulto_2022_status"] = "nao"
    out["indulto_2022_detalhe"] = "Decreto 11.302/2022 - referência 25/12/2022\n" + "\n".join(linhas)
    return out


def aplicar_extincoes(r, crimes, incidentes):
    """Leva em conta as extinções que o RSPE registra fora da linha "Extinto:" do crime:
    - "(Extinta)" ao lado do número do processo criminal;
    - incidente EXTINÇÃO (concedido) com "Processos Selecionados" - ou sem processo, quando alcança a execução toda.
    Marca o crime como extinto (extinto_rspe guarda o valor original para a auditoria)."""
    ext_inc = [i for i in incidentes if "EXTIN" in (i.get("tipo") or "").upper() and i.get("situacao", "CONCEDIDO") == "CONCEDIDO"]
    geral = []
    for c in crimes:
        c["extinto_rspe"] = c.get("extinto", "")
        c["extincao_fonte"] = ""
        if (c.get("processo_situacao") or "").upper().startswith("EXTINT"):
            c["extinto"] = "Sim"
            c["extincao_fonte"] = "processo marcado \"(%s)\" no RSPE" % c["processo_situacao"]
    for i in ext_inc:
        procs = [p.strip() for p in re.split(r"[;,\s]+", i.get("processos") or "") if p.strip()]
        d = i.get("data_referencia") or i.get("data_decisao") or ""
        motivo = (i.get("complemento") or "").strip() or "extinção"
        if procs:
            for c in crimes:
                if c.get("processo_criminal") in procs:
                    c["extinto"] = "Sim"
                    if d and not c.get("data_extincao"):
                        c["data_extincao"] = d
                    c["extincao_motivo"] = motivo
                    c["extincao_fonte"] = (c["extincao_fonte"] + "; " if c["extincao_fonte"] else "") + "incidente EXTINÇÃO (%s%s)" % (motivo, " em " + d if d else "")
        else:
            geral.append("%s%s" % (motivo, " em " + d if d else ""))
    if geral:
        r["execucao_extinta"] = "; ".join(geral)
        for c in crimes:
            if not c.get("extinto", "").upper().startswith("S"):
                c["extinto"] = "Sim"
                c["extincao_fonte"] = "incidente EXTINÇÃO da execução (%s)" % geral[0]
                c["extincao_motivo"] = geral[0]
    else:
        r["execucao_extinta"] = ""
    r["crimes_extintos_detalhe"] = "; ".join(
        "%s: %s%s" % (crimes_curto([c]), c.get("extincao_motivo") or "extinto", (" em " + c["data_extincao"]) if c.get("data_extincao") else "")
        for c in crimes if c.get("extinto", "").upper().startswith("S"))


def _idade_em(nasc, ref):
    d = to_date(nasc or "")
    if not d:
        return None
    return ref.year - d.year - ((ref.month, ref.day) < (d.month, d.day))


def e_incidente_livramento(i):
    """Incidente que concede/trata o livramento condicional em si. Exclui 'ALTERAÇÃO DE DATA-BASE DE
    PROGRESSÃO DE REGIME/LIVRAMENTO CONDICIONAL', que só muda a data-base e não concede nada."""
    t = (i.get("tipo") or "").upper()
    return "LIVRAMENTO" in t and "DATA-BASE" not in t and "DATA BASE" not in t


def livramento_em_curso(campos, incidentes, ref=None):
    """(True/False, data) - livramento condicional vigente: o SEEU imprime "(Em livramento condicional
    deferido em dd/mm/aaaa)", ou há incidente de LC concedido sem revogação posterior."""
    dl = None
    m = RE_DATA.search(campos.get("livramento_obs_seeu") or "")
    if "LIVRAMENTO" in (campos.get("livramento_obs_seeu") or "").upper():
        dl = to_date(m.group(1)) if m else date.min
    if not dl:
        for i in incidentes:
            if i.get("situacao") == "CONCEDIDO" and e_incidente_livramento(i) and "REVOG" not in ((i.get("tipo") or "") + (i.get("complemento") or "")).upper():
                d = to_date(i.get("data_referencia") or i.get("data_decisao") or i.get("complemento") or "")
                if d and (dl is None or d > dl):
                    dl = d
    if not dl:
        return False, None
    revog = [to_date(j.get("data_referencia") or j.get("data_decisao") or "") or date.max for j in incidentes
             if "REVOG" in ((j.get("tipo") or "") + " " + (j.get("complemento") or "")).upper() and "LIVRAMENTO" in ((j.get("tipo") or "") + " " + (j.get("complemento") or "")).upper()]
    if any(d > dl and (ref is None or d <= ref) for d in revog):
        return False, dl
    if ref is not None and dl != date.min and dl > ref:
        return False, dl
    if "LIVRAMENTO" in (campos.get("regime_atual") or "").upper():
        return True, dl
    return True, (dl if dl != date.min else None)


def duvidas_livramento(campos, eventos, incidentes, dl=None):
    """Indícios no RSPE de que o livramento pode ter sido suspenso/revogado sem registro expresso.
    Devolve lista de textos (vazia = sem dúvida)."""
    if dl is None:
        ok, dl = livramento_em_curso(campos, incidentes)
        if not ok:
            return []
    d0 = dl if isinstance(dl, date) and dl != date.min else None
    duv = []
    reg = (campos.get("regime_atual") or "").replace(" - ATIVO", "").strip()
    if reg and "LIVRAMENTO" not in reg.upper():
        duv.append("Regime Atual no RSPE é %s" % reg)
    for e in eventos:
        d = to_date(e.get("data") or "")
        t = ((e.get("tipo") or "") + " " + (e.get("motivo") or "")).upper()
        if d and d0 and d > d0:
            if "INTERRUP" in t:
                duv.append("interrupção em %s (%s)" % (fmt(d), (e.get("motivo") or "").strip().lower() or "sem motivo"))
            elif "PRIS" in t or "REIN" in t:
                duv.append("prisão/reinício em %s (%s)" % (fmt(d), (e.get("motivo") or "").strip().lower() or "sem motivo"))
    for i in incidentes:
        d = to_date(i.get("data_referencia") or i.get("data_decisao") or "")
        t = ((i.get("tipo") or "") + " " + (i.get("complemento") or "")).upper()
        if d and d0 and d > d0 and "REGIME" in t and i.get("situacao") == "CONCEDIDO":
            duv.append("alteração de regime em %s (%s)" % (fmt(d), (i.get("complemento") or "").strip()))
        if "SUSPENS" in t and "LIVRAMENTO" in t:
            duv.append("suspensão do livramento registrada" + (" em %s" % fmt(d) if d else ""))
    return duv


def _regime_em(incidentes, ref, regime_atual, custodia=True, campos=None):
    """Regime vigente na data ref (última fixação/alteração de regime até ref) e se está em LC.
    Sem incidente de regime até ref, só recorre ao regime atual se a pessoa estava presa em ref;
    do contrário devolve regime vazio (não havia pena em cumprimento naquela data)."""
    reg, dreg = None, None
    for i in incidentes:
        if i.get("situacao") != "CONCEDIDO":
            continue
        if "REGIME" in (i.get("tipo") or "").upper():
            d = to_date(i.get("data_referencia") or i.get("data_decisao") or "")
            if d and d <= ref and (dreg is None or d >= dreg):
                dreg, reg = d, (i.get("complemento") or "").split(" - ")[0].strip()
    lc = False
    dlc = None
    for i in incidentes:
        if i.get("situacao") == "CONCEDIDO" and e_incidente_livramento(i):
            d = to_date(i.get("data_referencia") or i.get("data_decisao") or i.get("complemento") or "")
            if d and d <= ref and (dlc is None or d > dlc):
                dlc = d
    if dlc:
        revogado = any("REVOG" in ((j.get("tipo") or "") + " " + (j.get("complemento") or "")).upper()
                       and (to_date(j.get("data_referencia") or j.get("data_decisao") or "") or date.min) > dlc for j in incidentes)
        if not revogado and (dreg is None or dlc >= dreg):
            lc = True
            reg = "Livramento condicional"
    if not lc and campos is not None:
        ok, dl = livramento_em_curso(campos, incidentes, ref)
        if ok:
            lc, reg = True, "Livramento condicional"
    if not reg and custodia:
        reg = (regime_atual or "").replace(" - ATIVO", "").split(" - ")[0].strip()
    return reg or "", dreg, lc


def _maior_periodo_continuo(periodos, ref):
    melhor = 0
    for ini, fim in periodos:
        if ini > ref:
            continue
        f = fim if (fim and fim <= ref) else ref
        melhor = max(melhor, (f - ini).days)
    return melhor


def _tempo_em_liberdade(periodos, ref):
    """Soma dos intervalos entre períodos de custódia (até ref)."""
    ps = sorted([(a, b if b else ref) for a, b in periodos if a <= ref])
    total = 0
    for k in range(1, len(ps)):
        gap = (ps[k][0] - ps[k - 1][1]).days
        if gap > 0:
            total += gap
    return total


PATRIMONIO_CP = set(str(a) for a in range(155, 181))  # Título II do CP


def analise_decretos(campos, crimes, eventos, incidentes, hoje):
    """Decretos 12.338/2024 e 12.790/2025: art. 1º (vedações), art. 6º (falta),
    art. 9º (16 hipóteses de indulto), § 2º (redução pela metade), art. 13 (comutação).
    Parâmetros (frações, tetos, anos) vêm da base jurídica (decretos_indulto.art9_incisos)."""
    carregar_tabelas_decretos()
    A = art9_param
    out = {}
    imped = []
    for c in crimes:
        r = impeditivo_decreto(c)
        if r:
            imped.append("art. 1º, %s: %s" % r)
    imped = list(dict.fromkeys(imped))
    if any(c.get("comando_orcrim") == "S" for c in crimes):
        imped.append("art. 1º, § 3º, I: comando de organização criminosa")
    out["indulto_crime_impeditivo"] = "SIM" if imped else "NÃO"
    out["indulto_crime_impeditivo_detalhe"] = "; ".join(imped)

    pena_total = pena_para_dias(campos.get("pena_total"))
    ativos = [c for c in crimes if not c.get("extinto", "").upper().startswith("S")]
    vga = any(c.get("vga") == "S" for c in ativos)
    reinc = any(c.get("reincidente_comum") == "S" or c.get("reincidente_especifico") == "S" for c in ativos)
    patrimonial = ativos and all(crime_patrimonial(c) for c in ativos)
    periodos = periodos_custodia(eventos)
    remicoes = []
    for i in incidentes:
        if "REMI" in (i.get("tipo") or "").upper():
            m = re.search(r"(\d+)\s*Dia", i.get("complemento", ""), re.I)
            if m:
                remicoes.append((to_date(i.get("data_referencia") or i.get("data_decisao") or ""), int(m.group(1))))
    saidas = [i for i in incidentes if i.get("situacao") == "CONCEDIDO" and "SA[ÍI]DA" and re.search(r"SA[ÍI]DA TEMPOR", i.get("tipo", ""), re.I)]
    F = Fraction

    for ano, ref in DECRETOS.items():
        k = "indulto_%s" % ano
        kc = "comutacao_%s" % ano
        if imped:
            out[k] = "VEDADO (art. 1º)"
            out[k + "_status"] = "vedado"
            out[k + "_detalhe"] = "Crime impeditivo: " + "; ".join(imped)
            out[kc] = "VEDADA (art. 1º)"
            # art. 7º, p. ú.: em concurso, os crimes NÃO impeditivos podem ser indultados/comutados
            # depois de cumpridos 2/3 da pena do crime impeditivo (o comando de ORCRIM, § 3º, alcança a pessoa)
            imp_c = [c for c in ativos if impeditivo_decreto(c)]
            livres = [c for c in ativos if not impeditivo_decreto(c)]
            if livres and imp_c and not any(c.get("comando_orcrim") == "S" for c in crimes):
                pena_imp = sum(pena_para_dias(c.get("pena_imposta")) or 0 for c in imp_c)
                exig = int(pena_imp * 2 / 3)
                cump_ref, _f = cumprido_na_data(campos, periodos, remicoes, ref)
                nomes = crimes_curto(livres)
                if pena_imp and cump_ref >= exig:
                    out[k] = "A VERIFICAR: art. 7º, p. ú. - 2/3 do crime impeditivo cumpridos; indulto dos crimes não impeditivos (%s)" % nomes
                    out[k + "_status"] = "verificar"
                    out[kc] = "A VERIFICAR: art. 7º, p. ú. - comutação dos crimes não impeditivos (%s)" % nomes
                    out[k + "_detalhe"] += ("\nArt. 7º, p. ú.: cumprido %s até %s ≥ 2/3 da pena dos crimes impeditivos (%s de %s). "
                                            "Os crimes não impeditivos (%s) podem ser indultados/comutados: analisar os incisos do art. 9º "
                                            "só com a pena desses crimes." % (dias_para_pena(cump_ref), fmt(ref), dias_para_pena(exig), dias_para_pena(pena_imp), nomes))
                else:
                    out[k + "_detalhe"] += ("\nArt. 7º, p. ú.: há crimes não impeditivos (%s), mas o indulto/comutação deles só depois de cumpridos 2/3 da pena "
                                            "dos impeditivos (%s de %s); cumprido até %s: %s." % (nomes, dias_para_pena(exig), dias_para_pena(pena_imp), fmt(ref), dias_para_pena(cump_ref)))
            continue
        if not pena_total:
            out[k] = out[kc] = "sem pena no RSPE"
            out[k + "_status"] = "nao"
            out[k + "_detalhe"] = ""
            continue

        custodia_ref = em_custodia(periodos, ref)
        regime, dreg, lc = _regime_em(incidentes, ref, campos.get("regime_atual"), custodia_ref, campos)
        # Em cumprimento na data do decreto: preso/em regime naquela data, ou em regime (aberto/LC)
        # fixado por incidente anterior à data, ainda que sem custódia física.
        em_cumprimento = custodia_ref or lc or bool(regime and dreg and dreg <= ref)
        if not em_cumprimento:
            primeiro = min((ini for ini, _ in periodos), default=None)
            if not any(ini <= ref for ini, _ in periodos):
                det = "Nenhum evento de prisão/início de cumprimento até %s (primeiro evento: %s)." % (fmt(ref), fmt(primeiro) or "nenhum")
            else:
                ult = max((fim for _, fim in periodos if fim and fim <= ref), default=None)
                det = ("Cumprimento interrompido em %s e sem reinício nem regime fixado até %s; o regime atual (%s) foi fixado depois dessa data. "
                       "Os incisos VII e VIII exigem estar em regime aberto ou livramento na data do decreto." % (
                           fmt(ult) or "?", fmt(ref), (campos.get("regime_atual") or "?").replace(" - ATIVO", "")))
            out[k] = "não se aplica: sem pena em cumprimento em %s" % fmt(ref)
            out[k + "_status"] = "nao"
            out[k + "_detalhe"] = det
            out[kc] = "não se aplica"
            continue
        cumprido, cump_fonte = cumprido_na_data(campos, periodos, remicoes, ref)
        remanescente = max(0, pena_total - cumprido)
        anos_pena = pena_total / float(DIAS_ANO)
        aberto = regime.upper().startswith("ABERTO")
        semi = regime.upper().startswith("SEMI")
        idade = _idade_em(campos.get("data_nascimento"), ref)
        idade_min = (_base_decretos().get("art9_incisos") or {}).get("par2_idade_minima") or 60
        meia = idade is not None and idade >= idade_min  # § 2º, I (único grupo aferível pelo RSPE)
        red = F(1, 2) if meia else F(1, 1)
        falta_ref = _falta_ate(campos, eventos, incidentes, ref)

        def frac(nr, r):
            return (F(r) if reinc else F(nr)) * red

        def tem(fr):
            return cumprido >= pena_total * fr

        def fmt_fr(nr, r):
            f = frac(nr, r)
            return "%s%s" % (f, " (½ pelo § 2º)" if meia else "")

        possiveis, verificar, nao = [], [], []
        cump_txt = "cumprido %s de %s" % (dias_para_pena(cumprido), dias_para_pena(pena_total))

        # I
        if vga:
            nao.append("I: não se aplica - crime com violência ou grave ameaça")
        elif anos_pena > A("I", "pena_max_anos", 8):
            nao.append("I: não se aplica - pena total %s superior a %s anos" % (dias_para_pena(pena_total), A("I", "pena_max_anos", 8)))
        else:
            f1 = (A("I", "fracao_primario", "1/5"), A("I", "fracao_reincidente", "1/3"))
            (possiveis if tem(frac(*f1)) else nao).append("I: pena ≤ %s anos sem VGA, exige %s (%s)" % (A("I", "pena_max_anos", 8), fmt_fr(*f1), cump_txt))
        # II
        if vga:
            nao.append("II: não se aplica - crime com violência ou grave ameaça")
        elif anos_pena > A("II", "pena_max_anos", 12):
            nao.append("II: não se aplica - pena total superior a %s anos" % A("II", "pena_max_anos", 12))
        else:
            f2 = (A("II", "fracao_primario", "1/3"), A("II", "fracao_reincidente", "1/2"))
            (possiveis if tem(frac(*f2)) else nao).append("II: pena ≤ %s anos sem VGA, exige %s (%s)" % (A("II", "pena_max_anos", 12), fmt_fr(*f2), cump_txt))
        # III
        if not vga:
            nao.append("III: não se aplica - crime sem violência ou grave ameaça (ver I e II)")
        elif anos_pena > A("III", "pena_max_anos", 4):
            nao.append("III: não se aplica - crime com VGA e pena total superior a %s anos" % A("III", "pena_max_anos", 4))
        else:
            f3 = (A("III", "fracao_primario", "1/3"), A("III", "fracao_reincidente", "1/2"))
            (possiveis if tem(frac(*f3)) else nao).append("III: pena ≤ %s anos com VGA, exige %s (%s)" % (A("III", "pena_max_anos", 4), fmt_fr(*f3), cump_txt))
        # IV
        continuo = _maior_periodo_continuo(periodos, ref)
        req = (A("IV", "anos_ininterruptos_reincidente", 20) if reinc else A("IV", "anos_ininterruptos_primario", 15)) * DIAS_ANO * red
        (possiveis if continuo >= req else nao).append("IV: %s anos ininterruptos (tem %s)" % (int(round(req / DIAS_ANO)), dias_para_pena(continuo)))
        # V
        req = (A("V", "anos_reincidente", 25) if reinc else A("V", "anos_primario", 20)) * DIAS_ANO * red
        if cumprido >= req:
            (possiveis if _tempo_em_liberdade(periodos, ref) <= A("V", "liberdade_max_anos", 2) * DIAS_ANO else nao).append(
                "V: %s anos não ininterruptos, liberdade ≤ %s anos" % (int(round(req / DIAS_ANO)), A("V", "liberdade_max_anos", 2)))
        else:
            nao.append("V: %s anos não ininterruptos (cumprido %s)" % (int(round(req / DIAS_ANO)), dias_para_pena(cumprido)))
        # VI
        req = (A("VI", "anos_semiaberto_reincidente", 15) if reinc else A("VI", "anos_semiaberto_primario", 10)) * DIAS_ANO * red
        if semi and dreg:
            t = (ref - dreg).days
            (possiveis if t >= req else nao).append("VI: %s anos ininterruptos no semiaberto (desde %s: %s)" % (int(round(req / DIAS_ANO)), fmt(dreg), dias_para_pena(t)))
        else:
            nao.append("VI: exige semiaberto ininterrupto por %s anos" % int(round(req / DIAS_ANO)))
        # VII
        if aberto:
            f7 = (A("VII", "fracao_primario", "1/6"), A("VII", "fracao_reincidente", "1/5"))
            (possiveis if tem(frac(*f7)) else nao).append("VII: regime aberto, cumprido %s" % fmt_fr(*f7))
        else:
            nao.append("VII: exige regime aberto, PRD ou sursis (em %s)" % (regime or "?"))
        # VIII
        lim = (A("VIII", "remanescente_max_anos_reincidente", 4) if reinc else A("VIII", "remanescente_max_anos_primario", 6)) * DIAS_ANO
        if aberto or lc:
            (possiveis if remanescente <= lim else nao).append(
                "VIII: %s, remanescente em %s de %s (limite %d anos)" % ("livramento condicional" if lc else "regime aberto", fmt(ref), dias_para_pena(remanescente), lim // DIAS_ANO))
        else:
            nao.append("VIII: exige regime aberto ou livramento (em %s)" % (regime or "?"))
        # IX
        if aberto or lc:
            verificar.append("IX: aberto/LC - verificar 2 anos em programa de egressos (patronato, escritório social)")
        else:
            nao.append("IX: não se aplica - exige regime aberto, PRD, livramento ou sursis")
        # X
        if semi and dreg and (ref - dreg).days >= 3 * DIAS_ANO:
            verificar.append("X: semiaberto há mais de 3 anos - verificar monitoramento eletrônico (SV 56)")
        else:
            nao.append("X: não se aplica - exige semiaberto com monitoramento há mais de 3 anos" + (" (semiaberto desde %s)" % fmt(dreg) if semi and dreg else ""))
        # XI
        if anos_pena > 12:
            nao.append("XI: não se aplica - pena superior a 12 anos")
        elif not (semi or aberto):
            nao.append("XI: não se aplica - exige regime semiaberto ou aberto")
        elif not tem(frac(A("XI", "fracao_primario", "1/3"), A("XI", "fracao_reincidente", "1/2"))):
            nao.append("XI: exige %s cumprido em semiaberto/aberto (%s)" % (fmt_fr(A("XI", "fracao_primario", "1/3"), A("XI", "fracao_reincidente", "1/2")), cump_txt))
        else:
            txt = "XI: pena ≤ 12 anos, %s cumprido em semiaberto/aberto - " % fmt_fr(A("XI", "fracao_primario", "1/3"), A("XI", "fracao_reincidente", "1/2"))
            if len(saidas) >= A("XI", "saidas_min", 5):
                possiveis.append(txt + "%d saídas temporárias no RSPE" % len(saidas))
            else:
                verificar.append(txt + "verificar 5 saídas temporárias ou 12 meses de trabalho externo (RSPE registra %d saída(s))" % len(saidas))
        # XII
        f12 = (A("XII", "fracao_primario_%s" % ano, "1/6" if ano == "2025" else "1/5"), A("XII", "fracao_reincidente_%s" % ano, "1/5" if ano == "2025" else "1/4"))
        if anos_pena > 12:
            nao.append("XII: não se aplica - pena superior a 12 anos")
        elif tem(frac(*f12)):
            verificar.append("XII: pena ≤ 12 anos, %s cumprido - verificar estudo por 12 meses (18 se reincidente)" % fmt_fr(*f12))
        else:
            nao.append("XII: exige %s cumprido (%s)" % (fmt_fr(*f12), cump_txt))
        # XIII
        if anos_pena > 12:
            nao.append("XIII: não se aplica - pena superior a 12 anos")
        elif tem(frac(A("XIII", "fracao_primario", "1/5"), A("XIII", "fracao_reincidente", "1/4"))):
            verificar.append("XIII: pena ≤ 12 anos, %s cumprido - verificar conclusão de curso certificado" % fmt_fr(A("XIII", "fracao_primario", "1/5"), A("XIII", "fracao_reincidente", "1/4")))
        else:
            nao.append("XIII: exige %s cumprido (%s)" % (fmt_fr(A("XIII", "fracao_primario", "1/5"), A("XIII", "fracao_reincidente", "1/4")), cump_txt))
        # XIV / XV
        if patrimonial and not vga:
            if cumprido >= A("XIV", "meses_cumpridos", 3) * 30:
                verificar.append("XIV: crime patrimonial sem VGA, %s meses cumpridos - verificar bem ≤ 1 salário mínimo" % A("XIV", "meses_cumpridos", 3))
            else:
                nao.append("XIV: exige %s meses cumpridos" % A("XIV", "meses_cumpridos", 3))
            # art. 12, § 2º, I: incapacidade econômica presumida para o assistido da Defensoria -> reparação dispensada no XV
            possiveis.append("XV: crime patrimonial sem VGA - reparação do dano dispensada (art. 9º, XV c/c art. 12, § 2º, I: hipossuficiência presumida, Defensoria)")
        elif any(crime_patrimonial(c) and c.get("vga") != "S" for c in ativos):
            verificar.append("XV: crime patrimonial sem VGA em concurso com outro crime - indulto parcial da pena do crime patrimonial "
                             "(reparação dispensada: art. 12, § 2º, I - hipossuficiência presumida); verificar separação das penas")
            nao.append("XIV: não se aplica - concurso com crime não patrimonial")
        else:
            nao.append("XIV e XV: não se aplicam - exigem crime contra o patrimônio sem VGA")
        verificar.append("XVI: saúde/deficiência - não aferível pelo RSPE (laudo médico)")
        # ordena por inciso
        ordem_inc = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI"]
        def _k(t):
            n = t.split(":")[0].split(" ")[0]
            return ordem_inc.index(n) if n in ordem_inc else 99
        possiveis.sort(key=_k); verificar.sort(key=_k); nao.sort(key=_k)

        if falta_ref:
            aviso = "FALTA nos 12 meses (art. 6º): " + falta_ref
        else:
            aviso = ""
        lc_duvida = bool(lc and duvidas_livramento(campos, eventos, incidentes))
        if lc_duvida and possiveis:
            # a situação de livramento é incerta no RSPE: o que dependeria dela vai para "a verificar"
            verificar = [p + " - livramento a confirmar" for p in possiveis] + verificar
            possiveis = []
            aviso = ("livramento condicional com situação incerta no RSPE (ver Auditoria)" + ("; " + aviso if aviso else ""))
        vd_prov = [v[1] for v in (violencia_domestica(c) for c in ativos) if v and v[0] == "provavel"]
        if vd_prov and possiveis:
            # art. 1º, XVII (violência contra a mulher): só se confirma com a vítima - nem nega, nem concede
            verificar = [p + " - confirmar se houve violência contra a mulher (art. 1º, XVII)" for p in possiveis] + verificar
            possiveis = []
            aviso = ("; ".join(dict.fromkeys(vd_prov)) + ("; " + aviso if aviso else ""))
        if possiveis:
            inc = ", ".join(p.split(":")[0] for p in possiveis)
            out[k] = "POSSÍVEL: art. 9º, " + inc + (" | " + aviso if aviso else "")
            out[k + "_status"] = "possivel"
        elif [v for v in verificar if not v.startswith("XVI")]:
            inc = ", ".join(p.split(":")[0] for p in verificar if not p.startswith("XVI"))
            out[k] = "A VERIFICAR: art. 9º, " + inc + (" | " + aviso if aviso else "")
            out[k + "_status"] = "verificar"
        else:
            out[k] = "não atinge (cumprido %s de %s%s%s até %s)" % (
                dias_para_pena(cumprido), dias_para_pena(pena_total), ", reincidente" if reinc else "", ", VGA" if vga else "", fmt(ref)) + (" | " + aviso if aviso else "")
            out[k + "_status"] = "nao"
        linhas = ["Situação em %s: regime %s%s · cumprido %s · remanescente %s · %s%s%s" % (
            fmt(ref), regime or "?", " + livramento condicional" if (lc and not regime.lower().startswith("livramento")) else "", dias_para_pena(cumprido), dias_para_pena(remanescente),
            "reincidente" if reinc else "primário", " · VGA" if vga else "", (" · %d anos (§ 2º, I: lapsos pela metade)" % idade) if meia else ""), "Cumprido em %s: %s (%s)." % (fmt(ref), dias_para_pena(cumprido), cump_fonte)]
        todos = [("✔ ", p) for p in possiveis] + [("? ", v) for v in verificar] + [("✘ ", n) for n in nao]
        todos.sort(key=lambda x: _k(x[1]))
        linhas += [a + b for a, b in todos]
        if aviso:
            linhas.append("⚠ " + aviso)
        linhas.append("Não aferíveis pelo RSPE: § 2º, II a VI (filhos, deficiência, justiça restaurativa) e art. 10 (mulheres) - se presentes, os lapsos I a XI caem pela metade.")
        linhas.append("Multa: indultável e não é óbice - incapacidade econômica presumida para assistido da Defensoria (art. 12, § 2º, I). "
                      "Tráfico privilegiado (art. 33, § 4º) não é impeditivo (STJ Tema 1336; STF Tema 1400).")
        out[k + "_detalhe"] = "\n".join(linhas)

        # art. 13 - comutação
        f13 = (A("art13_comutacao", "fracao_primario", "1/5"), A("art13_comutacao", "fracao_reincidente", "1/4"))
        if possiveis:
            # art. 13, § 5º: a comutação não se aplica a quem preenche os requisitos do indulto (prevalece o mais benéfico)
            out[kc] = "prejudicada: indulto cabível (art. 13, § 5º)"
        elif tem(frac(*f13)):
            base = "cumprido" if cumprido > remanescente else "remanescente"
            prop = A("art13_comutacao", "proporcao_par2", "2/3") if meia else A("art13_comutacao", "proporcao", "1/5")
            if vd_prov:
                out[kc] = "A VERIFICAR: art. 13 (%s do %s) - confirmar se houve violência contra a mulher (art. 1º, XVII)" % (prop, base) + (" | " + aviso if aviso else "")
            else:
                out[kc] = "POSSÍVEL: art. 13 (%s do %s)" % (prop, base) + (" | " + aviso if aviso else "")
        else:
            out[kc] = "não atinge (%s%s até %s)" % (fmt_fr(*f13), "", fmt(ref)) + (" | " + aviso if aviso else "")
    return out


def _falta_ate(campos, eventos, incidentes, ref):
    """Indícios de falta nos 12 meses anteriores à data de referência do decreto."""
    limite = ref - timedelta(days=365)
    achados = []
    for i in incidentes:
        txt = _rotulo_incidente(i)
        if RE_FALTA.search(txt):
            d = to_date(i.get("data_referencia") or i.get("data_decisao") or "")
            if d and limite <= d <= ref:
                achados.append("%s (%s)" % (txt, fmt(d)))
    return "; ".join(achados)


# --------------------------------------------------------------------------- #
# extração principal
# --------------------------------------------------------------------------- #

def extrair(caminho):
    texto, vara, comarca, tribunal, geracao = ler_pdf(caminho)
    hoje = to_date(geracao) or date.today()

    cab = secao(texto, "PROCESSO DE EXECUÇÃO", ["CÁLCULOS DA PENA"])
    calc = secao(texto, "CÁLCULOS DA PENA", outros("CÁLCULOS DA PENA"))
    crim = secao(texto, "PROCESSOS CRIMINAIS", ["EVENTOS DE INÍCIO", "INCIDENTES", "Fim do Relatório"])
    ev = secao(texto, "EVENTOS DE INÍCIO", ["INCIDENTES", "Fim do Relatório"])
    conc = secao(texto, "INCIDENTES CONCEDIDOS", ["INCIDENTES NÃO", "INCIDENTES NEGADOS", "INCIDENTES PENDENTES", "INCIDENTES EM", "Fim do Relatório"])
    neg = secao(texto, "INCIDENTES NÃO CONCEDIDOS", ["INCIDENTES PENDENTES", "INCIDENTES EM", "Fim do Relatório"]) \
        or secao(texto, "INCIDENTES NEGADOS", ["INCIDENTES PENDENTES", "INCIDENTES EM", "Fim do Relatório"])
    pend = secao(texto, "INCIDENTES PENDENTES", ["Fim do Relatório"]) \
        or secao(texto, "INCIDENTES EM ANÁLISE", ["Fim do Relatório"])

    numero = campo(cab, "Número Único")
    status = ""
    m = re.search(r"\(([^)]+)\)", numero)
    if m:
        status = m.group(1)
    m = RE_CNJ.search(numero)
    numero = m.group(0) if m else numero

    r = {
        "arquivo": os.path.basename(caminho),
        "tribunal": tribunal,
        "comarca": comarca,
        "vara": vara,
        "data_geracao_rspe": geracao,
        "processo_execucao": numero,
        "status_execucao": status,
        "numero_antigo": campo(cab, "Número Antigo"),
        "nome": campo(cab, "Nome:"),
        "cpf": campo(cab, "CPF"),
        "rg": campo(cab, "RG"),
        "nome_mae": campo(cab, "Nome da Mãe"),
        "data_nascimento": campo_data(cab, "Data de Nascimento"),
        "regime_atual": campo(calc, "Regime Atual"),
        "pena_total": campo(calc, "Pena Total Imposta"),
        "pena_cumprida": campo(calc, "Pena Cumprida Até Data Atual"),
        "pena_remanescente": campo(calc, "Pena Remanescente"),
        "total_interrupcoes": campo(calc, "Total Interrupções"),
        "saldo_remidos": campo(calc, "Saldo dias Remidos"),
        # previsões que o SEEU imprime em alguns modelos de RSPE
        "progressao_previsao_seeu": "" if campo(calc, "Data prevista para progressão de regime").startswith("(")
            else campo_data(calc, "Data prevista para progressão de regime"),
        "progressao_obs_seeu": re.sub(r"[()]", "", campo(calc, "Data prevista para progressão de regime")).strip()
            if campo(calc, "Data prevista para progressão de regime").startswith("(") else "",
        "data_base_seeu": campo_data(calc, "Data-base adotada no cálculo para progresso regime")
            or campo_data(calc, "Data-base adotada no cálculo para progressão de regime"),
        "livramento_previsao_seeu": "" if (campo(calc, "Data prevista livramento condicional") or campo(calc, "Data prevista para livramento condicional")).startswith("(")
            else (campo_data(calc, "Data prevista livramento condicional") or campo_data(calc, "Data prevista para livramento condicional")),
        "livramento_obs_seeu": re.sub(r"[()]", "", campo(calc, "Data prevista livramento condicional") or campo(calc, "Data prevista para livramento condicional")).strip()
            if (campo(calc, "Data prevista livramento condicional") or campo(calc, "Data prevista para livramento condicional")).startswith("(") else "",
        "livramento_data_base_seeu": campo_data(calc, "Data-base adotada no cálculo para livramento condicional"),
        "termino_previsao_seeu": campo_data(calc, "Data prevista para o Término da Pena"),
    }

    crimes = parse_crimes(crim)
    eventos = blocos_tipo(ev)
    inc_conc = blocos_tipo(conc)
    inc_neg = blocos_tipo(neg)
    inc_pend = blocos_tipo(pend)
    for i in inc_conc:
        i["situacao"] = "CONCEDIDO"
    for i in inc_neg:
        i["situacao"] = "NÃO CONCEDIDO"
    for i in inc_pend:
        i["situacao"] = "PENDENTE"
    incidentes = inc_conc + inc_neg + inc_pend

    # resumo de crimes
    def _nome_crime(c):
        art = c["artigo"]
        if not art or art.lower().startswith("não informado"):
            art = "art. não informado: " + (c["tipo_penal"] or "")[:60]
        lei = c["lei"]
        nome_lei = lei.split(" - ", 1)[1].strip() if " - " in lei else lei
        nome_lei = {"Código Penal": "CP", "Lei de Drogas": "Lei de Drogas"}.get(nome_lei, nome_lei)
        return "%s, %s (%s)" % (nome_lei, art, pena_curta(c["pena_imposta"] or c["pena_total_processo"]))
    r["crimes"] = "; ".join(_nome_crime(c) for c in crimes) or ""
    r["crimes_curto"] = crimes_curto(crimes)
    r["qtd_processos_criminais"] = len({c["processo_criminal"] for c in crimes})
    r["qtd_crimes"] = len(crimes)
    r["crime_hediondo_equiparado"] = "S" if any(c["hediondo_ou_equiparado"] == "S" for c in crimes) else "N"
    r["vga"] = "S" if any(c["vga"] == "S" for c in crimes) else "N"
    r["reincidente"] = "S" if any(c["reincidente_comum"] == "S" or c["reincidente_especifico"] == "S" for c in crimes) else "N"

    # histórico de regime / progressões
    reg = [i for i in inc_conc if "REGIME" in i["tipo"].upper()]
    r["historico_regime"] = " | ".join(
        "%s (ref. %s, dec. %s)" % (i["complemento"], i["data_referencia"] or "-", i["data_decisao"] or "-") for i in reg)
    prog = [i for i in reg if "PROGRESS" in i["complemento"].upper()]
    r["progressoes_concedidas"] = len(prog)
    r["ultima_progressao"] = prog[-1]["complemento"] + " em " + (prog[-1]["data_referencia"] or prog[-1]["data_decisao"]) if prog else ""
    regr = [i for i in reg if "REGRESS" in i["complemento"].upper()]
    r["regressoes"] = " | ".join("%s (%s)" % (i["complemento"], i["data_referencia"] or i["data_decisao"]) for i in regr)

    # livramento condicional registrado
    liv = [i for i in incidentes if e_incidente_livramento(i)]
    r["livramento_incidentes"] = " | ".join("%s: %s %s" % (i["situacao"], i["complemento"], i["data_decisao"]) for i in liv)

    # indulto / comutação registrados
    ind = [i for i in incidentes if re.search(r"INDULTO|COMUTA", i["tipo"] + " " + i["complemento"], re.I)]
    r["indulto_comutacao_incidentes"] = " | ".join(
        "%s: %s %s %s" % (i["situacao"], i["tipo"], i["complemento"], i["data_decisao"]) for i in ind) or "nenhum registro no RSPE"
    sit, motivos = triagem_indulto(crimes)
    r["indulto_comutacao_triagem"] = sit
    r["indulto_comutacao_motivos"] = "; ".join(motivos)

    # negados relevantes
    r["incidentes_nao_concedidos"] = " | ".join("%s %s %s" % (i["tipo"], i["complemento"], i["data_decisao"]) for i in inc_neg)
    r["incidentes_pendentes"] = " | ".join("%s %s" % (i["tipo"], i["complemento"]) for i in inc_pend)

    aplicar_extincoes(r, crimes, incidentes)
    r.update(situacao_execucao(r, eventos, incidentes, crimes, hoje))
    r.update(faltas(r, eventos, incidentes, hoje))
    r.update(analise_decretos(r, crimes, eventos, incidentes, hoje))
    r.update(analise_decreto_2022(r, crimes, eventos, incidentes))
    r["eventos"] = " | ".join("%s/%s %s" % (e["tipo"], e["motivo"], e["data"]) for e in eventos)

    r["_crimes"] = crimes
    r["_incidentes"] = incidentes
    r["_eventos"] = eventos
    return r


# --------------------------------------------------------------------------- #
# saída
# --------------------------------------------------------------------------- #

COLUNAS = [
    "nome", "processo_execucao", "status_execucao", "vara", "comarca", "data_geracao_rspe",
    "regime_atual", "situacao_cumprimento",
    "pena_total", "pena_cumprida", "pena_remanescente", "total_interrupcoes", "saldo_remidos",
    "fracao_progressao_aplicada", "data_base", "progressao_previsao_seeu", 
    "progressoes_concedidas", "ultima_progressao", "regressoes", "historico_regime",
    "fracao_livramento_aplicada", "livramento_previsao_seeu", "livramento_incidentes",
    "termino_previsao_seeu", 
    "crimes", "crimes_curto", "qtd_processos_criminais", "qtd_crimes", "crime_hediondo_equiparado", "vga", "reincidente",
    "falta_12m", "falta_12m_detalhe",
    "indulto_crime_impeditivo", "indulto_crime_impeditivo_detalhe", "indulto_2022", "indulto_2024", "indulto_2025",
    "indulto_2024_detalhe", "indulto_2025_detalhe",
    "comutacao_2024", "comutacao_2025", "indulto_comutacao_incidentes",
    "indulto_comutacao_triagem", "indulto_comutacao_motivos",
    "progressao_obs_seeu", "livramento_obs_seeu", "data_base_seeu", "livramento_data_base_seeu",
    "incidentes_nao_concedidos", "incidentes_pendentes", "eventos",
    "cpf", "rg", "data_nascimento", "nome_mae", "numero_antigo", "arquivo",
]
COL_CRIMES = [
    "nome", "processo_execucao", "processo_criminal", "vara_condenacao", "lei", "artigo", "tipo_penal",
    "pena_imposta", "data_infracao", "data_denuncia", "data_sentenca", "transito_processo", "regime_sentenca",
    "vga", "resultado_morte", "reincidente_comum", "reincidente_especifico", "comando_orcrim",
    "hediondo_ou_equiparado", "fracao_progressao", "fracao_livramento", "extinto", "suspenso",
]
COL_INC = ["nome", "processo_execucao", "situacao", "tipo", "complemento", "data_decisao", "data_referencia", "processos"]

TITULOS_BONITOS = {}


def gravar_xlsx(registros, caminho):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    wb = Workbook()

    def aba(ws, cols, linhas):
        ws.append([TITULOS_BONITOS.get(c, c) for c in cols])
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1F4E78")
            cell.alignment = Alignment(vertical="center", wrap_text=True)
        for l in linhas:
            ws.append([l.get(c, "") for c in cols])
        for i, c in enumerate(cols, 1):
            larg = max([len(str(l.get(c, ""))) for l in linhas] + [len(c)]) if linhas else len(c)
            ws.column_dimensions[get_column_letter(i)].width = min(max(12, larg + 2), 60)
        ws.freeze_panes = "C2"
        ws.auto_filter.ref = ws.dimensions

    aba(wb.active, COLUNAS, registros)
    wb.active.title = "RSPE"
    aba(wb.create_sheet("Crimes"), COL_CRIMES,
        [dict(c, nome=r["nome"], processo_execucao=r["processo_execucao"]) for r in registros for c in r["_crimes"]])
    aba(wb.create_sheet("Incidentes"), COL_INC,
        [dict(i, nome=r["nome"], processo_execucao=r["processo_execucao"]) for r in registros for i in r["_incidentes"]])
    ws = wb.create_sheet("Leia-me")
    for l in [
        "RSPE Scraper - SEEU  v" + VERSAO,
        "",
        "Colunas *_previsao_seeu: datas impressas pelo próprio SEEU no RSPE (quando o modelo traz).",
        "Colunas *_ESTIMATIVA: calculadas pelo programa a partir dos eventos de prisão/interrupção, remições e",
        "  frações do RSPE (ano = 365 dias, mês = 30 dias, como o SEEU). Servem para triagem: o valor oficial é o do Atestado de Pena.",
        "Progressão: data-base = última fixação/alteração de regime; fração aplicada sobre o remanescente na data-base;",
        "  usa a fração mais gravosa entre os crimes não extintos.",
        "Livramento: fração mais gravosa aplicada sobre a pena total.",
        "Indulto/comutação: 'incidentes' = o que consta no RSPE; 'triagem' = alerta por tipo de crime (hediondo,",
        "  tráfico, organização criminosa, tortura, VGA, resultado morte). Os requisitos mudam a cada decreto: conferir.",
        "Nada é inventado: campo em branco = não consta no RSPE.",
    ]:
        ws.append([l])
    ws.column_dimensions["A"].width = 120
    wb.save(caminho)


def gravar_csv(registros, caminho):
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([TITULOS_BONITOS.get(c, c) for c in COLUNAS])
        for r in registros:
            w.writerow([r.get(c, "") for c in COLUNAS])


def gravar_json(registros, caminho):
    limpos = []
    for r in registros:
        d = {k: v for k, v in r.items() if not k.startswith("_")}
        d["crimes_detalhe"] = r["_crimes"]
        d["incidentes"] = r["_incidentes"]
        d["eventos_detalhe"] = r["_eventos"]
        limpos.append(d)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(limpos, f, ensure_ascii=False, indent=2)


def resumo_terminal(r):
    return "\n".join([
        "-" * 70,
        "%s  |  %s  |  %s" % (r["nome"], r["processo_execucao"], r["vara"]),
        "Regime atual: %s   (%s)" % (r["regime_atual"], r["situacao_cumprimento"]),
        "Pena: total %s | cumprida %s | remanescente %s | remidos %s" % (
            r["pena_total"], r["pena_cumprida"], r["pena_remanescente"], r["saldo_remidos"]),
        "Progressão: fração %s | data-base %s | SEEU: %s" % (
            r["fracao_progressao_aplicada"], r["data_base"], r["progressao_previsao_seeu"] or "-"),
        "Livramento: fração %s | SEEU: %s" % (r["fracao_livramento_aplicada"], r["livramento_previsao_seeu"] or "-"),
        "Término:    SEEU: %s" % (r["termino_previsao_seeu"] or "-"),
        "Crimes: " + r["crimes"],
        "Indulto/comutação: %s | %s" % (r["indulto_comutacao_incidentes"], r["indulto_comutacao_triagem"]),
        "  " + r["indulto_comutacao_motivos"] if r["indulto_comutacao_motivos"] else "",
    ])


# --------------------------------------------------------------------------- #
# interface
# --------------------------------------------------------------------------- #

def coletar_pdfs(args):
    pdfs = []
    for a in args.arquivos:
        if os.path.isdir(a):
            pdfs += [os.path.join(a, f) for f in sorted(os.listdir(a)) if f.lower().endswith(".pdf")]
        elif a.lower().endswith(".pdf"):
            pdfs.append(a)
    if args.dir:
        pdfs += [os.path.join(args.dir, f) for f in sorted(os.listdir(args.dir)) if f.lower().endswith(".pdf")]
    return pdfs


def gui():
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except ImportError:
        sys.exit("Sem interface gráfica. Uso: rspe_scraper arquivo.pdf [-o saida.xlsx]")
    root = tk.Tk()
    root.withdraw()
    pdfs = filedialog.askopenfilenames(title="Selecione os RSPE (PDF) do SEEU", filetypes=[("PDF", "*.pdf")])
    if not pdfs:
        return None, None
    saida = filedialog.asksaveasfilename(
        title="Salvar planilha como", defaultextension=".xlsx",
        initialfile="rspe_extraido_%s.xlsx" % datetime.now().strftime("%Y%m%d_%H%M"),
        filetypes=[("Excel", "*.xlsx")])
    if not saida:
        return None, None
    return list(pdfs), saida


def main():
    ap = argparse.ArgumentParser(description="Scraper de RSPE (SEEU) -> Excel/CSV/JSON")
    ap.add_argument("arquivos", nargs="*", help="PDFs ou pastas")
    ap.add_argument("-d", "--dir", help="pasta com PDFs")
    ap.add_argument("-o", "--saida", help="arquivo .xlsx de saída")
    ap.add_argument("--sem-csv", action="store_true")
    ap.add_argument("--sem-json", action="store_true")
    args = ap.parse_args()

    pdfs = coletar_pdfs(args)
    saida = args.saida
    modo_gui = False
    if not pdfs:
        modo_gui = True
        pdfs, saida = gui()
        if not pdfs:
            print("Nenhum arquivo selecionado.")
            return
    if not saida:
        saida = "rspe_extraido_%s.xlsx" % datetime.now().strftime("%Y%m%d_%H%M")

    registros, erros = [], []
    for p in pdfs:
        try:
            r = extrair(p)
            registros.append(r)
            print(resumo_terminal(r))
        except Exception as e:  # segue com os demais
            erros.append("%s: %s" % (os.path.basename(p), e))
            print("ERRO em %s: %s" % (p, e))

    if registros:
        gravar_xlsx(registros, saida)
        base = os.path.splitext(saida)[0]
        if not args.sem_csv:
            gravar_csv(registros, base + ".csv")
        if not args.sem_json:
            gravar_json(registros, base + ".json")
        print("-" * 70)
        print("%d RSPE processado(s). Planilha: %s" % (len(registros), saida))
    for e in erros:
        print("Falhou: " + e)

    if modo_gui:
        from tkinter import messagebox
        msg = "%d RSPE processado(s).\nPlanilha: %s" % (len(registros), saida)
        if erros:
            msg += "\n\nFalhas:\n" + "\n".join(erros)
        messagebox.showinfo("RSPE Scraper", msg)


if __name__ == "__main__":
    main()
