#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSPE Scraper - SEEU
====================
Extrai dados do Relatório da Situação Processual Executória (RSPE) do SEEU
(PDF), aplica as regras do programa (indulto/comutação, falta nos 12 meses,
hediondez pela data do fato) e gera planilha Excel / CSV / JSON com:

  * nome, CPF, número do processo de execução, vara, data de geração
  * regime atual, penas (total, cumprida, remanescente, interrupções, remidos)
  * progressão de regime  (fração, data-base, previsão impressa pelo SEEU,
                           histórico de progressões e regressões)
  * livramento condicional (fração e previsão impressa pelo SEEU)
  * término de pena (previsão impressa pelo SEEU)
  * crimes (lei, artigo, pena imposta, data do fato, VGA, morte, reincidência)
  * falta nos 12 meses anteriores à geração do RSPE (indícios)
  * indulto / comutação: incidentes registrados no RSPE, triagem de vedações e
    análise dos Decretos 11.302/2022, 12.338/2024 e 12.790/2025

As datas de progressão, livramento e término são as impressas pelo SEEU: o
programa não as recalcula nem estima.

Uso:
    rspe_scraper.exe                          -> abre janela para escolher PDFs
    rspe_scraper.exe arq1.pdf arq2.pdf ...    -> processa os arquivos
    rspe_scraper.exe -d PASTA                 -> processa todos os PDFs da pasta
    rspe_scraper.exe ... -o saida.xlsx        -> define o arquivo de saída
    --sem-csv / --sem-json / --sem-planilha   -> não grava esses arquivos
    --relatorios / --relatorio-geral          -> relatórios em PDF (individual e geral)
    --anonimo                                 -> fila do relatório geral sem nomes
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


def chave_processo(num):
    """Chave de comparação de número de processo: só dígitos, sem zeros à esquerda. O SEEU imprime o mesmo
    processo antigo de dois jeitos ("0000000-00.0000.0.03.2698" no crime e "32698" no evento)."""
    return re.sub(r"\D", "", num or "").lstrip("0")


def lista_processos(txt):
    """'Processos Selecionados' (texto do RSPE) -> lista de números como impressos (separados por vírgula/ponto e vírgula)."""
    if not txt:
        return []
    if isinstance(txt, (list, tuple, set)):
        return [str(x).strip() for x in txt if str(x).strip()]
    out = []
    for x in re.split(r"[,;\n]+", txt):
        x = x.strip()
        if not x:
            continue
        partes = x.split()
        # números separados só por espaço ("0001111-11.2015.8.12.0001 32698"): cada um é um processo
        if len(partes) > 1 and all(re.fullmatch(r"[\d.\-]+", t) for t in partes):
            out.extend(partes)
        else:
            out.append(x)
    return out


def mesmo_processo(a, b):
    ka, kb = chave_processo(a), chave_processo(b)
    return bool(ka) and ka == kb


def completar_processos(txt, crimes):
    """Completa número truncado pela quebra de linha do PDF ("0020835-") com o único processo criminal que o inicia."""
    nums = list(dict.fromkeys(c.get("processo_criminal") or "" for c in crimes if c.get("processo_criminal")))
    out = []
    for t in lista_processos(txt):
        if not RE_CNJ.fullmatch(t) and re.fullmatch(r"\d{1,7}-?(\d{0,2}\.?)*", t) and ("-" in t or "." in t):
            cand = [n for n in nums if n.startswith(t)]
            if len(cand) == 1:
                t = cand[0]
        out.append(t)
    return ", ".join(out)
RE_PENA_AMD = re.compile(r"(\d+)a(\d+)m(\d+)d")
RE_PENA_EXT = re.compile(r"(\d+)\s*ano\(s\),\s*(\d+)\s*m[êe]s\(es\)\s*e\s*(\d+)\s*dia\(s\)")


def num_txt(n):
    """12 -> '12'; 12.5 -> '12,5' (remição fracionada)."""
    if isinstance(n, float) and n != int(n):
        return ("%.2f" % n).rstrip("0").replace(".", ",")
    return "%d" % n


def pl(n, um, varios):
    """'1 dia' / '3 dias' / '12,5 dias' (sem o '(s)')."""
    return "%s %s" % (num_txt(n), um if n == 1 else varios)


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


def pena_extenso(txt):
    """'14a10m0d' -> '14 anos e 10 meses'; '5a1m17d' -> '5 anos, 1 mês e 17 dias'. Mantém o texto se não reconhecer."""
    t = pena_amd(txt) if isinstance(txt, str) else txt
    if not t:
        return txt or ""
    a, m, d = t
    partes = []
    if a:
        partes.append("%d ano%s" % (a, "s" if a > 1 else ""))
    if m:
        partes.append("%d %s" % (m, "mês" if m == 1 else "meses"))
    if d:
        partes.append("%d dia%s" % (d, "s" if d > 1 else ""))
    if not partes:
        return "0 dia"
    neg = "-" if isinstance(txt, str) and txt.strip().startswith("-") else ""
    return neg + (partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " e " + partes[-1])


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
    # ano de 365 e mês de 30: o resto de 360 a 364 dias fica em 11 meses e 30 a 34 dias (o SEEU nunca imprime "12 meses")
    m = min(r // 30, 11)
    d = r - 30 * m
    return ("-" if neg else "") + "%da%dm%dd" % (a, m, d)


def pct(fr):
    """Fraction/'1/6'/'16%' -> '16,67%' (progressão sempre em percentual)."""
    if fr is None or fr == "":
        return ""
    f = fr if isinstance(fr, Fraction) else parse_fracao(str(fr))
    if f is None:
        return str(fr)
    v = round(float(f) * 100, 2)
    t = ("%.2f" % v).rstrip("0").rstrip(".")
    return t.replace(".", ",") + "%"


def pct_rotulo(txt):
    """'1/6 - Comum' -> '16,67% - Comum'; '3/5 (LEP ...)' -> '60% (LEP ...)'; percentuais ficam como estão."""
    t = txt or ""
    return re.sub(r"^\s*(\d+)\s*/\s*(\d+)", lambda m: pct(Fraction(int(m.group(1)), int(m.group(2)))), t)


def pct_texto(t):
    """Frações simples soltas no texto ('1/6', '2/5', '3/5') -> percentual; não toca em números de lei ('13.964/2019')."""
    return re.sub(r"(?<![\d./])([1-9])/([1-9]\d?)(?![\d/])", lambda m: pct(Fraction(int(m.group(1)), int(m.group(2)))), t or "")


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


def _campo_rg(texto):
    """RG: rótulo isolado em maiúsculas (evita casar "rg" dentro do nome, como em JORGE)."""
    m = re.search(r"(?<![A-Za-zÀ-ÿ])RG(?![A-Za-zÀ-ÿ])[ \t]*:?[ \t]*(.*)", texto)
    return m.group(1).strip() if m else ""


def _nascimento(cab):
    """Data de nascimento do cabeçalho: aceita 'Data de Nascimento', 'Data Nascimento', 'Dt. Nascimento' ou 'Nascimento',
    com a data na mesma linha ou na seguinte (quebra do texto do PDF)."""
    for rot in (r"Data\s+de\s+Nascimento", r"Data\s+Nascimento", r"Dt\.?\s*(?:de\s+)?Nascimento", r"Nascimento"):
        m = re.search(rot + r"[ \t]*:?[\s]{0,40}?(\d{2}/\d{2}/\d{4})", cab or "", re.I)
        if m:
            return m.group(1)
    return ""


def chave_pena_max(c):
    """Chave do tipo penal na tabela 'pena_maxima_abstrata' da base jurídica: 'lei:artigo' ou 'lei:artigo §X'."""
    t = c.get("tipo_penal") or ""
    lei, art = num_lei(c.get("lei")) or "2848", num_art(c.get("artigo"))
    mp = re.match(r"§\s*(\d+[ºo°]?(?:-[A-Z])?|único)", t)
    chave = "%s:%s" % (lei, art)
    if mp:
        chave += " §" + mp.group(1).replace("º", "").replace("o", "").replace("°", "")
    return chave


def pena_livre(txt):
    """Pena digitada pelo operador: '0a3m0d', '3 meses', '1 ano e 6 meses', '15 dias' -> dias (ano 365, mês 30)."""
    t = (txt or "").strip().lower()
    d = pena_para_dias(t)
    if d is not None:
        return d
    a = re.search(r"(\d+)\s*(?:a\b|ano)", t)
    m = re.search(r"(\d+)\s*(?:m\b|m[eê]s)", t)
    dd = re.search(r"(\d+)\s*(?:d\b|dia)", t)
    if not (a or m or dd):
        return None
    return (int(a.group(1)) * DIAS_ANO if a else 0) + (int(m.group(1)) * 30 if m else 0) + (int(dd.group(1)) if dd else 0)


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
            c["artigo_rspe"] = c["artigo"]
            inferir_artigo(c)
            c["hediondo_ou_equiparado"] = "S" if e_hediondo(c) else "N"
            crimes.append(c)
    return crimes


# Artigo reconhecido pela descrição do tipo, quando o SEEU grava "Não informado".
# (lei, regex sobre a descrição sem acentos e em maiúsculas, artigo, nome). A ordem importa: o mais específico primeiro.
TIPOS_POR_DESCRICAO = [
    ("2848", r"CONJUNCAO CARNAL OU (PRATICAR|A PRATICA DE) OUTRO ATO LIBIDINOSO COM MENOR DE 14", "217-A", "Estupro de vulnerável"),
    ("2848", r"CONSTRANGER ALGUEM, MEDIANTE VIOLENCIA OU GRAVE AMEACA, A TER CONJUNCAO CARNAL", "213", "Estupro"),
    ("2848", r"CONSTRANGER MULHER A CONJUNCAO CARNAL", "213", "Estupro"),
    ("2848", r"ATO LIBIDINOSO DIVERSO DA CONJUNCAO CARNAL", "214", "Atentado violento ao pudor"),
    ("2848", r"PRATICAR CONTRA ALGUEM E SEM A SUA ANUENCIA ATO LIBIDINOSO", "215-A", "Importunação sexual"),
    ("2848", r"MATAR ALGUEM", "121", "Homicídio"),
    ("2848", r"SEQUESTRAR PESSOA COM O FIM DE OBTER", "159", "Extorsão mediante sequestro"),
    ("2848", r"CONSTRANGER ALGUEM, MEDIANTE VIOLENCIA OU GRAVE AMEACA, E COM O INTUITO DE OBTER", "158", "Extorsão"),
    ("2848", r"SUBTRAIR COISA MOVEL ALHEIA, PARA SI OU PARA OUTREM, MEDIANTE GRAVE AMEACA OU VIOLENCIA", "157", "Roubo"),
    ("2848", r"SUBTRAIR, PARA SI OU PARA OUTREM, COISA ALHEIA MOVEL", "155", "Furto"),
    ("2848", r"COISA QUE SABE SER PRODUTO DE CRIME", "180", "Receptação"),
    ("2848", r"OBTER, PARA SI OU PARA OUTREM, VANTAGEM ILICITA", "171", "Estelionato"),
    ("2848", r"APROPRIAR-SE DE COISA ALHEIA MOVEL", "168", "Apropriação indébita"),
    ("2848", r"OFENDER A INTEGRIDADE CORPORAL OU A SAUDE|^(CAPUT: )?LESAO CORPORAL", "129", "Lesão corporal"),
    ("2848", r"AMEACAR ALGUEM", "147", "Ameaça"),
    ("2848", r"PRIVAR ALGUEM DE SUA LIBERDADE", "148", "Sequestro e cárcere privado"),
    ("2848", r"ENTRAR OU PERMANECER, CLANDESTINA OU ASTUCIOSAMENTE", "150", "Violação de domicílio"),
    ("2848", r"DESTRUIR, INUTILIZAR OU DETERIORAR COISA ALHEIA", "163", "Dano"),
    ("2848", r"DESTRUIR, SUBTRAIR OU OCULTAR CADAVER", "211", "Destruição, subtração ou ocultação de cadáver"),
    ("2848", r"ASSOCIAREM-SE (3|TRES) OU MAIS PESSOAS", "288", "Associação criminosa"),
    ("2848", r"OPOR-SE A EXECUCAO DE ATO LEGAL", "329", "Resistência"),
    ("2848", r"DESOBEDECER A ORDEM LEGAL", "330", "Desobediência"),
    ("2848", r"DESACATAR FUNCIONARIO", "331", "Desacato"),
    ("11340", r"DESCUMPRIR DECISAO JUDICIAL QUE DEFERE MEDIDAS PROTETIVAS", "24-A", "Descumprimento de medida protetiva"),
    ("11343", r"ASSOCIAREM-SE DUAS OU MAIS PESSOAS", "35", "Associação para o tráfico"),
    ("11343", r"PARA CONSUMO PESSOAL", "28", "Posse de droga para consumo pessoal"),
    ("11343", r"IMPORTAR, EXPORTAR, REMETER, PREPARAR, PRODUZIR|NOS DELITOS DEFINIDOS NO CAPUT E NO § 1", "33", "Tráfico de drogas"),
    ("10826", r"USO (PROIBIDO|RESTRITO)", "16", "Posse ou porte ilegal de arma de fogo de uso restrito"),
    ("10826", r"DISPARAR ARMA DE FOGO", "15", "Disparo de arma de fogo"),
    ("10826", r"POSSUIR OU MANTER SOB SUA GUARDA ARMA DE FOGO", "12", "Posse irregular de arma de fogo de uso permitido"),
    ("10826", r"PORTAR, DETER, ADQUIRIR, FORNECER", "14", "Porte ilegal de arma de fogo de uso permitido"),
    ("9503", r"CAPACIDADE PSICOMOTORA ALTERADA|SOB A INFLUENCIA DE ALCOOL", "306", "Embriaguez ao volante"),
    ("9503", r"HOMICIDIO CULPOSO NA DIRECAO", "302", "Homicídio culposo na direção de veículo"),
    ("9503", r"LESAO CORPORAL CULPOSA NA DIRECAO", "303", "Lesão corporal culposa na direção de veículo"),
    ("9503", r"SEM A DEVIDA PERMISSAO PARA DIRIGIR OU HABILITACAO", "309", "Direção sem habilitação"),
]


def inferir_artigo(c):
    """SEEU sem artigo ("Não informado"): reconhece o tipo pela descrição da pena. Marca c["artigo_inferido"]."""
    if num_art(c.get("artigo") or ""):
        return
    desc = _sem_acento(c.get("tipo_penal") or "").upper()
    desc = re.sub(r"^\s*(CAPUT|§\s*[\dº°A-Z-]+)\s*:\s*", "", desc)
    desc = re.sub(r"^\((ATE|APOS)[^)]*\)\s*", "", desc)
    lei = num_lei(c.get("lei") or "") or "2848"
    fato = to_date(c.get("data_infracao") or "")
    for l, rx, art, nome in TIPOS_POR_DESCRICAO:
        if l == lei and re.search(rx, desc):
            c["artigo_inferido"] = "reconhecido pela descrição do tipo (o SEEU não informou o artigo)"
            lt = LEI_DO_TEMPO.get((l, art))
            if lt and fato:
                vig, lei_txt, antes, nota_antes, depois, nota_depois = lt
                if fato < vig and antes is not None:
                    art, nome = antes
                    c["lei_do_tempo"] = "fato de %s, anterior à %s (vigência %s): %s" % (fmt(fato), lei_txt, fmt(vig), nota_antes)
                elif fato < vig:
                    c["lei_do_tempo"] = "fato de %s, anterior à %s (vigência %s): %s" % (fmt(fato), lei_txt, fmt(vig), nota_antes)
                elif fato >= vig and depois is not None:
                    art, nome = depois
                    c["lei_do_tempo"] = "fato de %s, posterior à %s (vigência %s): %s" % (fmt(fato), lei_txt, fmt(vig), nota_depois)
            elif lt and not fato:
                c["lei_do_tempo"] = "sem data do fato: o tipo depende da %s (vigência %s) - verificar na ação penal" % (lt[1], fmt(lt[0]))
            c["artigo"] = "ART %s: %s" % (art, nome)
            return


# Tipo reconhecido pela descrição x lei da data do fato.
# (lei, art reconhecido): (vigência, lei, (art, nome) se o fato for anterior | None, nota se anterior,
#                          (art, nome) se o fato for posterior | None, nota se posterior)
LEI_DO_TEMPO = {
    ("2848", "217-A"): (date(2009, 8, 10), "Lei 12.015/2009", ("213", "Estupro (ou art. 214) c/c art. 224, a - violência presumida"),
                        "à época, art. 213 (conjunção carnal) ou art. 214 (outro ato libidinoso) c/c art. 224, a, do CP; conferir na sentença qual foi aplicado e a pena cominada (6 a 10 anos)",
                        None, ""),
    ("2848", "213"): (date(2009, 8, 10), "Lei 12.015/2009", None,
                      "à época, o art. 213 abrangia só a conjunção carnal; outro ato libidinoso era o art. 214 - conferir na sentença",
                      None, ""),
    ("2848", "214"): (date(2009, 8, 10), "Lei 12.015/2009", None, "",
                      ("213", "Estupro"), "o art. 214 foi revogado e a conduta passou ao art. 213 (continuidade normativa)"),
    ("2848", "215-A"): (date(2018, 9, 25), "Lei 13.718/2018", None,
                        "o tipo não existia na data do fato (irretroatividade - CF, art. 5º, XL): verificar a capitulação na sentença", None, ""),
    ("11340", "24-A"): (date(2018, 4, 4), "Lei 13.641/2018", None,
                        "o descumprimento de medida protetiva não era crime na data do fato (STJ considerava atípico): verificar", None, ""),
    ("2848", "288"): (date(2013, 9, 19), "Lei 12.850/2013", None,
                      "à época, 'quadrilha ou bando' (mais de três pessoas, pena de 1 a 3 anos)", None, ""),
}


# ------------------------- triagem de vedação a indulto -------------------- #

# Somente os que são hediondos em qualquer modalidade (sem depender do § / inciso):
HEDIONDOS_SEMPRE = {"121-A", "121-B", "159", "213", "217-A", "218-B"}
HEDIONDOS_CONDICIONAIS = {"121", "122", "129", "155", "157", "158", "273"}
EQUIPARADOS = {
    "11343": {"33", "34", "36", "35"},          # tráfico (33 caput/§1º, 34, 36; 35 associação NÃO é hediondo, mas decretos vedam)
    "9455": {"1"},                                # tortura
    "13260": {"2", "3", "5", "6"},                # terrorismo
    "10826": {"16", "17", "18"},                  # Estatuto do Desarmamento (art. 16 §2º hediondo; 17/18 hediondos)
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


NOMES_CRIME = {  # nome jurídico usual quando o SEEU traz o texto do tipo (ex.: "Matar alguem:")
    ("CP", "121"): "Homicídio", ("CP", "211"): "Ocultação de cadáver", ("CP", "129"): "Lesão corporal",
    ("CP", "147"): "Ameaça", ("CP", "148"): "Sequestro e cárcere privado", ("CP", "171"): "Estelionato",
    ("CP", "180"): "Receptação", ("CP", "213"): "Estupro", ("CP", "217-A"): "Estupro de vulnerável",
    ("CP", "288"): "Associação criminosa", ("CP", "329"): "Resistência", ("CP", "330"): "Desobediência",
    ("CP", "331"): "Desacato", ("CP", "307"): "Falsa identidade", ("CP", "155"): "Furto", ("CP", "157"): "Roubo",
    ("CP", "158"): "Extorsão", ("CP", "159"): "Extorsão mediante sequestro", ("CP", "163"): "Dano",
    ("Lei 10.826/03", "12"): "Posse irregular de arma de uso permitido", ("Lei 10.826/03", "14"): "Porte ilegal de arma de uso permitido",
    ("Lei 10.826/03", "16"): "Posse ou porte de arma de uso restrito", ("Lei 10.826/03", "15"): "Disparo de arma de fogo",
    ("Lei 11.343/06", "33"): "Tráfico de drogas", ("Lei 11.343/06", "35"): "Associação para o tráfico",
    ("Lei 11.343/06", "28"): "Posse de drogas para consumo", ("Lei 9.503/97", "306"): "Embriaguez ao volante",
    ("Lei 9.503/97", "309"): "Direção sem habilitação", ("Lei 3.688/41", "21"): "Vias de fato",
}


def nome_crime(c):
    """'ART 157: Roubo' -> 'Roubo'; 'ART 121: Matar alguem:' -> 'Homicídio' (qualificado, se § 2º)."""
    t = c.get("artigo") or ""
    art = num_art(t)
    nome = NOMES_CRIME.get((lei_curta(c.get("lei")), art))
    if nome:
        if art == "121" and (paragrafo_inciso(c) or ("", ""))[0] == "2":
            nome = "Homicídio qualificado"
        pi = paragrafo_inciso(c) or ("", "")
        if art == "155" and pi[0] in ("4", "4-A", "4-B", "4-C", "5", "6", "7"):
            nome = "Furto qualificado"
        if art == "157" and pi[0] == "3" and pi[1] == "II":
            nome = "Latrocínio"
        if art == "33" and lei_curta(c.get("lei")) == "Lei 11.343/06" and pi[0] == "4":
            nome = "Tráfico privilegiado"
        return nome
    m = re.match(r"\s*ART\.?\s*[\dA-Z-]+\s*[:\-–]\s*(.+)$", t, re.I)
    return m.group(1).strip().rstrip(":").strip() if m else ""


def dispositivo(c):
    """'art. 157, § 3º, I, do CP' / 'art. 157, caput, do CP' / 'art. 33, § 4º, da Lei 11.343/06'."""
    art = num_art(c.get("artigo"))
    if not art:
        return "artigo não informado (%s)" % lei_curta(c.get("lei"))
    par = paragrafo_texto(c)
    pi = paragrafo_inciso(c)
    if not par and pi == ("", ""):
        par = "caput"
    lei = lei_curta(c.get("lei"))
    return "art. %s%s, %s %s" % (art, (", " + par) if par else "", "do" if lei == "CP" else "da", lei)


def paragrafo_texto(c):
    """'§ 3º, I' / '§ 2º-A, I' / 'p. ú.' / '' (caput ou ilegível)."""
    pi = paragrafo_inciso(c)
    if not pi or not pi[0]:
        return ""
    if pi[0] == "pu":
        return "p. ú."
    num, suf = (pi[0].split("-", 1) + [""])[:2]
    return "§ %sº%s%s" % (num, ("-" + suf) if suf else "", (", " + pi[1]) if pi[1] else "")


def qualificado_privilegiado(c):
    """Homicídio qualificado-privilegiado (CP, art. 121, § 2º com o § 1º): não é hediondo (STJ, HC 41.579, 5ª T.,
    19/04/2005; HC 23.973, 5ª T., 15/10/2002). True só se o RSPE cita o § 1º junto do § 2º."""
    if num_art(c.get("artigo")) != "121" or num_lei(c.get("lei")) not in ("2848", ""):
        return False
    pi = paragrafo_inciso(c)
    t = " ".join(str(c.get(k) or "") for k in ("tipo_penal", "artigo"))
    if not pi or pi[0] != "2":
        return False
    resto = RE_PARAGRAFO.sub("", (c.get("tipo_penal") or "").strip(), count=1) + " " + (c.get("artigo") or "")
    return bool(re.search(r"§\s*1[º°o]?(?![\d-])|PRIVILEGIAD", resto, re.I))


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
    if qualificado_privilegiado(c):
        return False
    par, inc = pi
    if art == "129":
        # Lei 8.072, art. 1º, I-A: só a lesão gravíssima (§ 2º) ou seguida de morte (§ 3º) contra agente de segurança,
        # membro do Judiciário, MP etc., ou em escola - a vítima não consta do RSPE: a verificar (None). O § 12 é só
        # causa de aumento de qualquer lesão dolosa e não torna o crime hediondo.
        return None if par in ("2", "3") else False
    for regra in regras[art]:
        partes = regra.replace("§", "").split()
        if partes and partes[0].upper() == "CAPUT" and par == "":
            return True
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


# tipo, qualificadora ou majorante criados por lei posterior ao Código: a capitulação com fato anterior à criação é
# anacronismo do cadastro (a sentença usou a redação da época) - chave como em hediondos.desde
TIPO_CRIADO = {
    "2848:157 §2-A": ("2018-04-24", "Lei 13.654/2018 (antes, o roubo com arma era o art. 157, § 2º, I)"),
    "2848:157 §2 VI": ("2018-04-24", "Lei 13.654/2018"),
    "2848:157 §2 VII": ("2020-01-23", "Lei 13.964/2019"),
    "2848:157 §2-B": ("2020-01-23", "Lei 13.964/2019"),
    "2848:155 §4-A": ("2018-04-24", "Lei 13.654/2018"),
    "2848:155 §4-B": ("2021-05-28", "Lei 14.155/2021"),
    "2848:155 §4-C": ("2021-05-28", "Lei 14.155/2021"),
    "2848:155 §7": ("2018-04-24", "Lei 13.654/2018"),
    "2848:171 §2-A": ("2021-05-28", "Lei 14.155/2021"),
    "2848:121 §2 VI": ("2015-03-10", "Lei 13.104/2015"),
    "2848:121 §2 VII": ("2015-07-07", "Lei 13.142/2015"),
    "2848:121-A": ("2024-10-10", "Lei 14.994/2024 (antes, feminicídio era o art. 121, § 2º, VI)"),
    "2848:147-A": ("2021-04-01", "Lei 14.132/2021"),
    "2848:147-B": ("2021-07-29", "Lei 14.188/2021"),
    "2848:149-A": ("2016-11-22", "Lei 13.344/2016"),
    "2848:215-A": ("2018-09-25", "Lei 13.718/2018"),
    "2848:217-A": ("2009-08-10", "Lei 12.015/2009 (antes, arts. 213/214 c/c 224)"),
    "2848:218-B": ("2009-08-10", "Lei 12.015/2009"),
    "2848:218-C": ("2018-09-25", "Lei 13.718/2018"),
    "11343:33": ("2006-10-08", "Lei 11.343/2006 (antes, Lei 6.368/76, art. 12)"),
    "11343:35": ("2006-10-08", "Lei 11.343/2006 (antes, Lei 6.368/76, art. 14)"),
    "10826:12": ("2003-12-23", "Lei 10.826/2003"), "10826:14": ("2003-12-23", "Lei 10.826/2003"),
    "10826:16": ("2003-12-23", "Lei 10.826/2003"), "10826:17": ("2003-12-23", "Lei 10.826/2003"),
    "12850:2": ("2013-09-19", "Lei 12.850/2013 (antes, quadrilha - CP, art. 288)"),
    "11340:24-A": ("2018-04-04", "Lei 13.641/2018"),
}


def _chaves_tipo(c):
    lei, art = num_lei(c.get("lei")) or "2848", num_art(c.get("artigo"))
    if "PENAL" in (c.get("lei") or "").upper() and "MILITAR" not in (c.get("lei") or "").upper():
        lei = "2848"
    if not art:
        return []
    t = (c.get("tipo_penal") or "").strip()
    chaves = []
    mp = re.match(r"§\s*(\d+[ºo°]?(?:\s*-\s*[A-Z])?)\s*,?\s*([IVXL]+)?", t)
    if mp:
        par = re.sub(r"[ºo°\s]", "", mp.group(1))
        if mp.group(2):
            chaves.append("%s:%s §%s %s" % (lei, art, par, mp.group(2)))
        chaves.append("%s:%s §%s" % (lei, art, par))
    chaves.append("%s:%s" % (lei, art))
    return chaves


def tipo_criado_em(c):
    """(data, lei) de criação do tipo/qualificadora/majorante capitulado, se posterior ao Código; (None, '') se não tabelado."""
    for k in _chaves_tipo(c):
        if k in TIPO_CRIADO:
            d, lei = TIPO_CRIADO[k]
            return datetime.strptime(d, "%Y-%m-%d").date(), lei
    return None, ""


def hediondo_na_epoca(c):
    """False se a tabela 'desde' mostra que o fato é anterior à lei que tornou o tipo hediondo; True/None caso contrário."""
    d, lei = hediondo_desde(c)
    fato = to_date(c.get("data_infracao") or "")
    if d and fato and fato < d:
        return False
    return True if d else None


def e_hediondo(c, ref=None):
    """Hediondez pelo rótulo do SEEU ou pelo rol da base jurídica (Lei 8.072/90, art. 1º).
    ref=None: lei da época do FATO (frações de progressão/livramento - irretroatividade).
    ref=data: lei vigente nessa data (vedação dos decretos de indulto/comutação: STJ afere na data do decreto)."""
    if qualificado_privilegiado(c):
        return False  # homicídio qualificado-privilegiado: não hediondo, ainda que o SEEU o rotule (STJ)
    if num_art(c.get("artigo")) == "129" and num_lei(c.get("lei")) in ("2848", "") and hediondo_condicional(c) is False:
        return False  # lesão que não é a gravíssima nem a seguida de morte (§ 12 é causa de aumento): não hediondo
    if ref is None:
        if hediondo_na_epoca(c) is False:
            return False
    else:
        d, _ = hediondo_desde(c)
        if d and d > ref:
            return False
    if "HEDIONDO" in ((c.get("fracao_progressao") or "") + (c.get("fracao_livramento") or "")).upper():
        # selo do SEEU: vale (na data do decreto, só não vale se a lei que tornou o tipo hediondo é posterior à referência - tratado acima)
        lei_, art_ = num_lei(c.get("lei")), num_art(c.get("artigo"))
        if not (lei_ == "11343" and art_ in ("35", "37") and "HEDIONDO" not in (c.get("fracao_progressao") or "").upper()):
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
        if lei == "11343" and art == "33" and ("§ 4" in (c.get("tipo_penal") or "") or re.match(r"\s*§\s*[23](?!\d)", c.get("tipo_penal") or "")):
            return False  # § 4º: privilegiado (LEP 112, § 5º); §§ 2º e 3º: induzimento e uso compartilhado, fora do tráfico equiparado
        return True
    pu = h.get("paragrafo_unico", {})
    regra = pu.get(lei)
    if isinstance(regra, dict):
        return regra.get(art) == "sempre"
    if isinstance(regra, list):
        return art in [str(x).split()[0] for x in regra]
    return False


def triagem_indulto(crimes):
    """Devolve (situacao, motivos[]) — triagem pelo art. 1º dos Decretos 12.338/2024 e 12.790/2025 (mesmo rol).
    Só aponta vedação que o decreto prevê: violência ou grave ameaça, resultado morte e tráfico privilegiado não são
    impeditivos (a VGA só limita os incisos I a III do art. 9º; STJ, Tema 1336; STF, Tema 1400)."""
    motivos = []
    ref = max(DECRETOS.values()) if DECRETOS else date(2025, 12, 25)
    for c in crimes:
        if c.get("extinto", "").upper().startswith("S"):
            continue
        if (to_date(c.get("data_infracao") or "") or date.min) > ref:
            continue  # fato posterior ao decreto: não é alcançado por ele
        lei, art = num_lei(c.get("lei")), num_art(c.get("artigo"))
        nome = "%s art. %s" % (c.get("lei", "").split(" - ")[0], art or "?")
        imp = impeditivo_decreto(c, ref)
        if imp:
            motivos.append("art. 1º, %s: %s - %s" % (imp[0], imp[1], nome))
        elif lei in ("2848", "") and art in HEDIONDOS_CONDICIONAIS and hediondo_condicional(c) is None:
            motivos.append("possível hediondo conforme §/inciso (%s): conferir - %s" % (art, nome))
        v = impeditivo_verificar(c)
        if v:
            motivos.append("%s - %s" % (v, nome))
        if c.get("comando_orcrim") == "S":
            motivos.append("comando de organização criminosa: art. 1º, § 3º, I (liderança) - conferir - " + nome)
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


def uniao_periodos(periodos):
    """Une períodos sobrepostos ou contíguos (inclusive interrupção e reinício no mesmo dia), para que nenhum dia
    seja contado duas vezes. Período em aberto (fim None) segue em aberto."""
    ps = sorted(((a, b) for a, b in periodos if a), key=lambda x: (x[0], x[1] or date.max))
    out = []
    for a, b in ps:
        if out and a <= (out[-1][1] or date.max):
            ult_a, ult_b = out[-1]
            out[-1] = (ult_a, None if (ult_b is None or b is None) else max(ult_b, b))
        else:
            out.append((a, b))
    return out


def dias_cumpridos_ate(periodos, remicoes, ate):
    """Dias de pena cumpridos até 'ate'. Conta o dia da prisão e o da soltura, como o SEEU (detração, CP, art. 42);
    interrupção e reinício no mesmo dia contam esse dia uma vez só."""
    total = 0
    for ini, fim in uniao_periodos(periodos):
        if ini > ate:
            continue
        f = fim if (fim and fim <= ate) else ate
        total += (f - ini).days + 1
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


def cumprido_na_data(campos, periodos, remicoes, ref, extras=None):
    """Pena cumprida em 'ref' ancorada no SEEU: cumprida na data do RSPE menos o cumprimento real entre ref e a data
    do RSPE (custódia e, em extras, o período de prova do livramento, que o SEEU também conta) e menos as remições
    concedidas depois de ref. Sem âncora, soma os períodos de custódia e as remições (dias reais)."""
    base, ger = cumprida_seeu_dias(campos)
    todos = uniao_periodos(list(periodos) + list(extras or []))
    if base is None or not ger:
        return dias_cumpridos_ate(todos, remicoes, ref), "custódia%s + remições (dias de calendário)" % (" e livramento" if extras else "")
    if ref >= ger:
        # RSPE anterior à data de referência: soma o cumprimento registrado como em curso entre a geração e a data
        mais = 0
        for ini, fim in todos:
            a, b = max(ini, ger), min(fim or ref, ref)
            if b > a:
                mais += (b - a).days
        if mais:
            return base + mais, ("pena cumprida do SEEU em %s mais %s de cumprimento em curso até %s (projeção: o RSPE é anterior a essa data; "
                                 "remições posteriores não constam)" % (fmt(ger), pl(mais, "dia", "dias"), fmt(ref)))
        return base, "pena cumprida do SEEU em %s" % fmt(ger)
    depois = 0
    for ini, fim in todos:
        a, b = max(ini, ref), min(fim or ger, ger)
        if b > a:
            depois += (b - a).days
    rem_depois = sum(n for d, n in remicoes if d and ref < d <= ger)
    return max(0, base - depois - rem_depois), "pena cumprida pelo SEEU em %s, descontados %s de cumprimento (custódia%s) e %s de remição posteriores a %s" % (
        fmt(ger), pl(depois, "dia", "dias"), " e livramento" if extras else "", pl(rem_depois, "dia", "dias"), fmt(ref))


def em_custodia(periodos, hoje):
    return any(ini <= hoje and (fim is None or fim > hoje) for ini, fim in periodos)


def situacao_execucao(campos, eventos, incidentes, crimes, hoje):
    """Leitura de apoio (sem projetar datas: progressão, livramento e término são os do SEEU):
    situação do cumprimento pelos eventos, fração mais gravosa impressa entre os crimes ativos e data-base."""
    out = {}
    periodos = periodos_custodia(eventos)
    out["situacao_cumprimento"] = "EM CUMPRIMENTO" if em_custodia(periodos, hoje) else "PENA INTERROMPIDA (sem evento de reinício)"
    # interrupção por prisão em outro processo: a execução fica suspensa com a pessoa presa (não é liberdade nem fuga)
    ult = max((e for e in eventos if to_date(e.get("data") or "")), key=lambda e: to_date(e["data"]), default=None)
    if (out["situacao_cumprimento"] != "EM CUMPRIMENTO" and ult and "INTERRUP" in (ult.get("tipo") or "").upper()
            and RE_OUTRO_PROC.search(ult.get("motivo") or "")):
        out["situacao_cumprimento"] = "PENA SUSPENSA (preso em outro processo desde %s)" % fmt(to_date(ult["data"]))
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
    if not r.get("termino_previsao_seeu") and not re.search(r"INTERROMPIDA|SUSPENSA", r.get("situacao_cumprimento") or "") and not r.get("execucao_extinta"):
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


NUM_DIAS = r"(\d+(?:[.,]\d+)?)"  # "12", "12,5" ou "12.5" (o SEEU registra remição fracionada)


def num_br(s):
    """'12,5' -> 12.5; '12' -> 12 (inteiro quando não há fração)."""
    try:
        v = float((s or "0").replace(",", "."))
    except ValueError:
        return 0
    return int(v) if v == int(v) else v


def dias_de(txt, rotulo=r"Dia"):
    """Número de dias antes do rótulo ('12,5 Dia(s) Remido(s)' -> 12.5), ou None."""
    m = re.search(NUM_DIAS + r"\s*" + rotulo, txt or "", re.I)
    return num_br(m.group(1)) if m else None


def saldo_remidos_num(txt):
    """'661 dias (661 dias remidos - 0 dias perdidos)' -> (661, 0); aceita decimal com vírgula."""
    t = txt or ""
    m = re.search(NUM_DIAS + r"\s*dias remidos\s*-\s*" + NUM_DIAS + r"\s*dias perdidos", t, re.I)
    if m:
        return num_br(m.group(1)), num_br(m.group(2))
    m = re.match(r"\s*" + NUM_DIAS, t)
    return (num_br(m.group(1)) if m else 0), 0


def resumir_nomes(nomes):
    """['art. 155 CP', 'art. 155 CP', 'art. 12 Lei 10.826/03'] -> 'art. 155 CP (x2); art. 12 Lei 10.826/03'."""
    cont, ordem = {}, []
    for x in nomes:
        if x not in cont:
            ordem.append(x)
        cont[x] = cont.get(x, 0) + 1
    return "; ".join(x + (" (x%d)" % cont[x] if cont[x] > 1 else "") for x in ordem)


def crimes_curto(crimes):
    """'art. 180 CP; art. 33 Lei 11.343/06 (x2)'."""
    itens = []
    ativos = [c for c in crimes if not c.get("extinto", "").upper().startswith("S")]
    suf = ""
    if not ativos and crimes:
        ativos, suf = crimes, " (extinto)"  # só crimes extintos: mostra os artigos, marcados
    for c in ativos:
        art = num_art(c.get("artigo"))
        if art:
            par = paragrafo_texto(c)
            txt = "art. %s%s %s" % (art, (" " + par) if par else "", lei_curta(c.get("lei")))
        else:
            txt = "art. n/i %s" % lei_curta(c.get("lei"))
        itens.append(txt + suf)
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


RE_FALTA_PROPRIA = re.compile(r"FALTA|SAN[ÇC][ÃA]O|DISCIPLIN|RDD|ISOLAMENTO", re.I)


def _negado(i):
    sit = _sem_acento(i.get("situacao") or "").upper()
    return sit.startswith("NAO") or "INDEFER" in sit or "NEGAD" in sit


def _pendente(i):
    sit = _sem_acento(i.get("situacao") or "").upper()
    return sit.startswith("PEND") or "ANALISE" in sit


def _data_fato_falta(i):
    """Data do fato da falta: o complemento da homologação traz a data da infração; na falta, a data de referência."""
    m = RE_DATA.search(i.get("complemento") or "")
    return to_date(m.group(1)) if m else to_date(i.get("data_referencia") or i.get("data_decisao") or "")


RE_OUTRO_PROC = re.compile(r"OUTRO PROCESSO|OUTRA EXECU|OUTRO FEITO|PRESO POR OUTRO|PRIS[ÃA]O EM OUTRO|OUTRA CONDENA", re.I)
RE_FUGA_EV = re.compile(r"FUGA|EVAS|ABANDON|FORAGID|N[ÃA]O RETORN", re.I)


def chave_falta(texto, d):
    """Identificador estável de um indício de falta (data + texto), para a decisão do operador ("é falta grave" / "não é")."""
    return "%s|%s" % (fmt(d) if d else "?", re.sub(r"[^A-Z0-9]", "", _sem_acento(texto or "").upper())[:40])


def _texto_evento(e):
    return " ".join(("%s %s" % (e.get("tipo", ""), e.get("motivo", ""))).split())


def corte_faltas(hoje=None):
    """Data a partir da qual um indício de falta ainda importa: a janela do art. 6º do decreto mais antigo em análise
    (12 meses antes de 25/12/2024) ou os 3 anos anteriores a hoje (prazo da falta disciplinar - STJ, art. 109, VI, do CP
    por analogia), o que for anterior. Indício mais antigo não pede decisão: não afeta indulto, comutação nem livramento,
    e a data-base de progressão já está fixada no RSPE."""
    hoje = hoje or date.today()
    return min(hoje - timedelta(days=3 * 365), min(DECRETOS.values()) - timedelta(days=365))


def faltas_editaveis(incidentes, eventos, hoje=None):
    return [x for x in _faltas_editaveis(incidentes, eventos) if not x["data"] or to_date(x["data"]) >= corte_faltas(hoje)]


def _faltas_editaveis(incidentes, eventos):
    """Todos os indícios de falta da execução que admitem decisão do operador: fuga (falta grave por padrão - LEP, art. 50, II),
    descumprimento, incidente pendente, perda de remidos ou regressão sem falta homologada. Cada um com a chave, a data, o
    texto, o estado padrão e a decisão gravada (_falta: 'sim' / 'nao')."""
    out = []
    proprias = [i for i in incidentes if RE_FALTA_PROPRIA.search(_rotulo_incidente(i)) and not _negado(i)]
    datas_proprias = [d for d in (_data_fato_falta(i) for i in proprias) if d]
    for i in incidentes:
        txt = _rotulo_incidente(i)
        if not RE_FALTA.search(txt) or _negado(i):
            continue
        if i in proprias:
            if not _pendente(i):
                continue  # homologada/concedida: já é falta grave reconhecida
            d = _data_fato_falta(i)
        else:
            d = to_date(i.get("data_referencia") or i.get("data_decisao") or "")
            if re.search(r"PERD|REGRESS", txt, re.I) and any(d and d - timedelta(days=365) <= x <= d for x in datas_proprias):
                continue
        out.append({"chave": chave_falta(txt, d), "data": fmt(d) if d else "", "texto": txt, "padrao": "apurar",
                    "decisao": i.get("_falta") or "", "origem": "incidente"})
    for e in eventos or []:
        t = _texto_evento(e)
        if not re.search(r"FUGA|EVAS|ABANDON|FORAGID|N[ÃA]O RETORN|DESCUMPRIMENTO", t, re.I):
            continue
        d = to_date(e.get("data") or "")
        if not d or any(abs((x - d).days) <= 1 for x in datas_proprias):
            continue
        out.append({"chave": chave_falta(t, d), "data": fmt(d), "texto": t, "padrao": "falta" if RE_FUGA_EV.search(t) else "apurar",
                    "decisao": e.get("_falta") or "", "origem": "evento"})
    return out


def faltas_da_ficha(r, ficha, hoje=None):
    """Faltas graves registradas na ficha disciplinar do SIAPEN que o RSPE não traz (sem falta própria em até 30 dias da
    mesma data): entram como incidente PENDENTE (falta a apurar), datado pelo fato - a sanção do conselho disciplinar não é
    reconhecimento em juízo (decretos, art. 6º). O operador decide ("é falta grave" / "não é") como nos demais indícios, e a
    decisão vale no sistema inteiro. Falta arquivada não entra."""
    r["_incidentes"] = [i for i in r.get("_incidentes", []) if not i.get("_ficha")]
    if not ficha:
        return
    proprias = [i for i in r["_incidentes"] if RE_FALTA_PROPRIA.search(_rotulo_incidente(i)) and not _negado(i)]
    datas = [d for d in (_data_fato_falta(i) for i in proprias) if d]
    for x in ficha.get("faltas") or []:
        d = to_date(x.get("data_fato") or x.get("data_registro") or "")
        if (not d or not x.get("grave") or x.get("situacao") == "arquivada" or d < corte_faltas(hoje)
                or any(abs((d - y).days) <= 30 for y in datas)):
            continue
        sit = x.get("situacao") or "registrada"
        r["_incidentes"].append({"tipo": "FALTA GRAVE NA FICHA DISCIPLINAR (SIAPEN)",
                                 "complemento": "Data da infração: %s%s - %s" % (fmt(d), (" - " + x["artigo"]) if x.get("artigo") else "", sit),
                                 "situacao": "PENDENTE", "data_referencia": fmt(d), "data_decisao": "", "_ficha": True})
        datas.append(d)


def aplicar_decisoes_falta(r, decisoes):
    """Grava em cada evento/incidente do registro a decisão do operador sobre a falta (decisoes: {chave: 'sim'|'nao'})."""
    for e in r.get("_eventos", []):
        e.pop("_falta", None)
        v = decisoes.get(chave_falta(_texto_evento(e), to_date(e.get("data") or "")))
        if v:
            e["_falta"] = v
    proprias = [i for i in r.get("_incidentes", []) if RE_FALTA_PROPRIA.search(_rotulo_incidente(i)) and not _negado(i)]
    for i in r.get("_incidentes", []):
        i.pop("_falta", None)
        txt = _rotulo_incidente(i)
        d = _data_fato_falta(i) if i in proprias else to_date(i.get("data_referencia") or i.get("data_decisao") or "")
        v = decisoes.get(chave_falta(txt, d))
        if v:
            i["_falta"] = v


def indicios_falta(incidentes, ref, dias=365, eventos=None, ate=None):
    """Faltas nos 'dias' anteriores a ref (art. 6º dos decretos; CP, art. 83, III, b), pela data do FATO.
    Devolve [(texto, firme)]: firme = falta grave, homologação ou sanção CONCEDIDA (sanção reconhecida em juízo);
    não firme = pendente, regressão sem menção a falta, perda de remidos sem falta datada (a perda é datada pela
    decisão, não pelo fato), fuga ou descumprimento só registrados como evento. Incidente não concedido não conta.
    ate: último dia da janela (art. 6º, p. ú.: falta posterior à publicação do decreto não impede); padrão = ref."""
    limite = ref - timedelta(days=dias)
    fim = ate or ref
    proprias = [i for i in incidentes if RE_FALTA_PROPRIA.search(_rotulo_incidente(i)) and not _negado(i)]
    datas_proprias = [d for d in (_data_fato_falta(i) for i in proprias) if d]
    out = []
    for i in incidentes:
        txt = _rotulo_incidente(i)
        if not RE_FALTA.search(txt) or _negado(i):
            continue
        if i.get("_falta") == "nao":
            continue  # o operador informou que não houve falta grave
        if i in proprias:
            d = _data_fato_falta(i)
            if d and limite <= d <= fim:
                if i.get("_falta") == "sim":
                    out.append(("%s (%s - falta grave confirmada pelo operador)" % (txt, fmt(d)), True))
                elif _pendente(i):
                    out.append(("%s (%s - pendente: só impede se a sanção for reconhecida em juízo)" % (txt, fmt(d)), False))
                else:
                    out.append(("%s (%s)" % (txt, fmt(d)), True))
            continue
        d = to_date(i.get("data_referencia") or i.get("data_decisao") or "")
        if not d:
            continue
        if i.get("_falta") == "sim":
            if limite <= d <= fim:
                out.append(("%s (%s - falta grave confirmada pelo operador)" % (txt, fmt(d)), True))
            continue
        if re.search(r"PERD|REGRESS", txt, re.I):
            # perda de remidos e regressão decorrem da falta: só se descartam se houver falta homologada nos 12 meses
            # anteriores a elas (a falta já conta pela data do fato); senão ficam "a verificar"
            if any(d - timedelta(days=dias) <= x <= d for x in datas_proprias):
                continue
            if limite <= d <= fim:
                if re.search(r"PERD", txt, re.I):
                    out.append(("%s (decisão de %s; data do fato não consta)" % (txt, fmt(d)), False))
                else:
                    out.append(("%s (%s; sem falta homologada no RSPE - pode ser soma de penas)" % (txt, fmt(d)), False))
            continue
        if limite <= d <= fim:
            out.append(("%s (%s%s)" % (txt, fmt(d), " - pendente" if _pendente(i) else ""), False))
    # fuga registrada só como evento: falta grave (LEP, art. 50, II), salvo decisão contrária do operador; descumprimento: a
    # apurar (LEP, art. 50, V). A homologação pode vir depois - STJ, Tema 1195
    for e in eventos or []:
        t = _texto_evento(e)
        if not re.search(r"FUGA|EVAS|ABANDON|FORAGID|N[ÃA]O RETORN|DESCUMPRIMENTO", t, re.I) or e.get("_falta") == "nao":
            continue
        d = to_date(e.get("data") or "")
        if d and limite <= d <= fim and not any(abs((x - d).days) <= 1 for x in datas_proprias):
            if e.get("_falta") == "sim":
                out.append(("%s (%s - falta grave confirmada pelo operador)" % (t, fmt(d)), True))
            elif RE_FUGA_EV.search(t):
                out.append(("%s (%s - fuga: falta grave, LEP, art. 50, II)" % (t, fmt(d)), True))
            else:
                out.append(("%s (%s; falta a apurar)" % (t, fmt(d)), False))
    return list(dict.fromkeys(out))


def faltas(campos, eventos, incidentes, hoje):
    """O RSPE não lista faltas formalmente; procura indícios (falta grave, regressão, perda de remidos, fuga,
    sanção) nos últimos 12 meses antes da geração do relatório, com a mesma regra do art. 6º dos decretos
    (incidente não concedido não conta). falta_12m: SIM (sanção reconhecida), A APURAR (só indício) ou não consta."""
    ind = indicios_falta(incidentes, hoje, eventos=eventos)
    firmes = [t for t, f in ind if f]
    achados = [t for t, f in ind if not f]  # a apurar: sem sanção reconhecida em juízo
    m = re.search(NUM_DIAS + r"\s*dias perdidos", campos.get("saldo_remidos", ""), re.I)
    # só vira indício "sem data" se o RSPE não trouxer incidente datado da falta/perda (homologação, dias perdidos)
    # incidente negado (falta não homologada, perda indeferida) não explica os dias perdidos do saldo
    datados = [i for i in incidentes if re.search(r"FALTA GRAVE|PERDIDOS", (i.get("tipo") or ""), re.I)
               and to_date(i.get("data_referencia") or i.get("data_decisao") or "") and not _negado(i)]
    if m and num_br(m.group(1)) > 0 and not datados:
        achados.append("%s remidos perdidos (data não consta)" % pl(num_br(m.group(1)), "dia", "dias"))
    firmes, achados = list(dict.fromkeys(firmes)), list(dict.fromkeys(achados))
    # "SIM" só com falta de sanção reconhecida (homologação, sanção ou falta grave concedida); indício sem ela: "A APURAR"
    return {
        "falta_12m": "SIM" if firmes else ("A APURAR" if achados else "não consta"),
        "falta_12m_detalhe": "; ".join(firmes + achados),
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
}  # CPM (XIX): só impede se corresponder aos incisos I a XVIII - ver impeditivo_verificar
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
    "333": ("XII", "corrupção ativa", 4),
}
for _a in range(312, 320):
    ART1_CP[str(_a)] = ("XII", "crime contra a administração pública (art. %d)" % _a, 4)
ART1_CP["313-A"] = ("XII", "inserção de dados falsos em sistema de informações (art. 313-A)", 4)
ART1_CP["313-B"] = ("XII", "modificação ou alteração não autorizada de sistema de informações (art. 313-B)", 4)
ART1_CP_RANGE = [("359-I", "359-R", "XV", "crimes contra o Estado Democrático de Direito")]
for _l in "EFGHIJKLMNOP":  # Lei 14.133/2021 (art. 1º, X): crimes em licitações inseridos no CP, arts. 337-E a 337-P
    ART1_CP["337-" + _l] = ("X", "crime em licitações (art. 337-%s do CP, Lei 14.133/2021)" % _l, 4)
ART1_ECA = {str(a): ("XIII", "crime do ECA (art. %d)" % a, None) for a in range(239, 245)}
for _x in ("241-A", "241-B", "241-C", "241-D", "241-E"):
    ART1_ECA[_x] = ("XIII", "crime do ECA (art. %s)" % _x, None)
ART1_ECA["244-A"] = ("XIII", "exploração sexual de menor (ECA 244-A)", None)
ART1_ECA["244-B"] = ("XIII", "corrupção de menores (ECA 244-B)", None)
ART1_DROGAS = {"33", "34", "35", "36", "37", "39"}


# publicação no DOU (d22: DOU de 23.12.2022; d24: DOU de 23.12.2024 - edição extra; d25: DOU de 23/12/2025, assinado em 22/12)
DECRETOS_PUB = {"2022": date(2022, 12, 23), "2024": date(2024, 12, 23), "2025": date(2025, 12, 23)}


def _sentenca_posterior(c, lim):
    """Condenação cuja sentença é posterior à data-limite (publicação do decreto): não havia condenação na data - fora da soma."""
    d = to_date(c.get("data_sentenca") or "")
    return bool(d and lim and d > lim)


def _art2_ii(c, lim):
    """Sentença anterior à data-limite (ou sem data), mas trânsito (para a acusação e final) só depois: o decreto alcança se
    não havia recurso da acusação, ou se ele não visava majorar a pena (art. 2º, II) - ponto controvertido, a verificar."""
    if not lim or _sentenca_posterior(c, lim):
        return False
    ds = [d for d in (to_date(c.get("transito_mp") or ""), to_date(c.get("transito_processo") or "")) if d]
    return bool(ds) and min(ds) > lim


def texto_art2_ii(crs, lim):
    return ("sentença anterior à publicação do decreto (%s), com trânsito para a acusação só depois (%s). Se não havia recurso da acusação, "
            "ou se ele não visava majorar a pena, o decreto alcança (art. 2º, II; TJMG, 9ª Câm. Crim., 1294534-24.2025). Em sentido contrário, "
            "o STJ exige os requisitos na data da publicação (AgRg no HC 864.086, 5ª T., 18/12/2023) - a verificar" % (
                fmt(lim), "; ".join("%s, trânsito em %s" % (crimes_curto([c]), c.get("transito_mp") or c.get("transito_processo")) for c in crs)))


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
            DECRETOS_PUB.update({ano: to_date_iso(v.get("publicacao")) for ano, v in refs.items() if to_date_iso(v.get("publicacao"))})
        if b.get("art1_leis"):
            ART1_LEIS = {k: tuple(v) for k, v in b["art1_leis"].items()}
        if b.get("art1_cp"):
            cp = {k: tuple(v) for k, v in b["art1_cp"].items()}
            for fx in b.get("art1_cp_faixas") or []:
                de, ate = str(fx["de"]), str(fx["ate"])
                ml, ml2 = re.match(r"^(\d+)-([A-Z])$", de), re.match(r"^(\d+)-([A-Z])$", ate)
                if ml and ml2 and ml.group(1) == ml2.group(1):
                    # faixa por letra (ex.: 337-E a 337-P)
                    for o in range(ord(ml.group(2)), ord(ml2.group(2)) + 1):
                        a = "%s-%s" % (ml.group(1), chr(o))
                        cp[a] = (fx["inciso"], "%s (art. %s)" % (fx.get("descricao", ""), a), fx.get("teto_anos"))
                    continue
                for a in range(int(de), int(ate) + 1):
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
    """Crime contra o patrimônio do CP (Título II) - arts. 155 a 180, inclusive os com letra (155-A, 168-A, 171-A, 180-A)."""
    if not (num_lei(c.get("lei")) in ("2848", "") or ("PENAL" in (c.get("lei") or "").upper() and "MILITAR" not in (c.get("lei") or "").upper())):
        return False
    art = num_art(c.get("artigo"))
    try:
        import rspe_regras as _rg
        de, ate, sufixos = _rg.patrimonio_faixa()
    except Exception:
        de, ate, sufixos = 155, 180, True
    m = re.match(r"^(\d+)(-[A-Z])?$", art or "")
    if not m or (m.group(2) and not sufixos):
        return art in PATRIMONIO_CP
    return de <= int(m.group(1)) <= ate


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
    if art == "147-A" and (lei in ("2848", "") or "PENAL" in (c.get("lei") or "").upper()):
        # art. 1º, XVII: "crimes de violência contra a mulher previstos no art. 147-A" - a vítima da perseguição pode ser homem
        # (o § 1º, II, e o tipo que indica a mulher já dão "sim" acima)
        if re.match(r"\s*§\s*1[º°o]?\s*,?\s*II\b", c.get("tipo_penal") or ""):
            return ("sim", "art. 147-A, § 1º, II (contra a mulher por razões da condição do sexo feminino)")
        return ("provavel", "art. 147-A (perseguição): confirmar se a vítima é mulher")
    if art == "215-A" and (lei in ("2848", "") or "PENAL" in (c.get("lei") or "").upper()):
        # art. 1º, XVII: "crimes de violência contra a mulher" da Lei 13.718/2018 - a vítima da importunação pode ser homem
        return ("provavel", "art. 215-A (importunação sexual): confirmar se a vítima é mulher")
    return None


def trafico_incerto(c):
    """Tráfico (art. 33 da Lei 11.343/06) sem indicação, no RSPE, de caput/§ 1º nem dos §§ 2º a 4º: a natureza (impeditivo
    ou tráfico privilegiado) não se presume - fica a verificar."""
    if c.get("extinto", "").upper().startswith("S"):
        return False
    if num_lei(c.get("lei")) != "11343" or num_art(c.get("artigo")) != "33":
        return False
    txt = " ".join(str(c.get(k) or "") for k in ("tipo_penal", "artigo", "artigo_rspe"))
    if re.search(r"§\s*[1234](?!\d)|PRIVILEGI|CAPUT", txt, re.I):
        return False
    return True


def impeditivo_decreto(c, ref=date(2024, 12, 25)):
    """Devolve (inciso, motivo) se o crime está no art. 1º dos Decretos 12.338/24 e 12.790/25, senão None.
    Hediondez aferida na data do decreto (ref), conforme o STJ."""
    if c.get("extinto", "").upper().startswith("S"):
        return None
    lei, art = num_lei(c.get("lei")), num_art(c.get("artigo"))
    pena_anos = (pena_para_dias(c.get("pena_imposta")) or 0) / float(DIAS_ANO)
    codigo_penal = lei in ("2848", "") or ("PENAL" in (c.get("lei") or "").upper() and "MILITAR" not in (c.get("lei") or "").upper())
    if trafico_incerto(c):
        return None  # a verificar (impeditivo_verificar): caput/§ 1º impede; § 4º não
    if e_hediondo(c, ref):
        if not e_hediondo(c):
            d, lei_h = hediondo_desde(c)
            return ("I", "crime hediondo (%s, vigência %s) - fato anterior, mas a hediondez é aferida na data do decreto (STJ) · "
                         "tese defensiva: irretroatividade (STF, 2ª T., RHC 267.297 AgR e HC 273.296 AgR; monocráticas do STF; TJMS, 2ª Câm. Crim.)" % (lei_h or "Lei 8.072/90", fmt(d)))
        return ("I", "crime hediondo ou equiparado (Lei 8.072/90)")
    if lei == "11343" and art in ART1_DROGAS:
        _tp = c.get("tipo_penal") or ""
        if art == "33" and (re.match(r"\s*§\s*[234](?!\d)", _tp) or "§ 4" in _tp):
            # o art. 1º, XVIII, só alcança o art. 33, caput e § 1º; § 2º (induzimento), § 3º (uso compartilhado)
            # e § 4º (tráfico privilegiado: STJ Tema 1336; STF Tema 1400) não são impeditivos
            return None
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
                  "11340": "III, c: crime da Lei 11.340/06", "12850": "III, d: organização criminosa (Lei 12.850/13)",
                  "13260": "III, e: terrorismo (Lei 13.260/16)"}
ART7_2022_CP = {"215": "IV", "216-A": "IV", "217-A": "IV", "218": "IV", "218-A": "IV", "218-B": "IV", "218-C": "IV",
                "312": "V", "316": "V", "317": "V", "333": "V"}
ART7_2022_ECA = ["240", "241", "241-A", "241-B", "241-C", "241-D", "241-E", "242", "243", "244", "244-A", "244-B"]


def pena_maxima_abstrata(c):
    """Pena máxima em abstrato (dias) lida do tipo penal impresso no RSPE:
    'Reclusão: 6 anos e 8 meses a 16 anos e 8 meses', 'Detenção: 2 meses a 2 anos', 'Reclusão: 1 a 4 anos'.
    Texto ausente, cortado ou ilegível: tabela da base jurídica (pena_maxima_abstrata) e, para contravenção, o teto do
    art. 10 da LCP (5 anos)."""
    if c.get("_pena_max_inf"):
        c["_pena_max_fonte"] = "informada pelo operador"
        return int(c["_pena_max_inf"])
    t = c.get("tipo_penal") or ""
    lei, art = num_lei(c.get("lei")) or "2848", num_art(c.get("artigo"))
    if re.search(r"CONTRAVEN", (c.get("lei") or "") + " " + (c.get("artigo") or ""), re.I):
        lei = "3688"
    if lei == "11343" and art == "33" and t.startswith("§ 4"):
        return int(15 * DIAS_ANO * 5 / 6)  # tráfico privilegiado: máximo de 15 anos com a redução mínima de 1/6
    m = re.search(r"(Reclus[ãa]o|Deten[çc][ãa]o|Pris[ãa]o simples)\s*:\s*(.+?)(?:\s+(?:E|OU|e|ou)\s+Multa|\s+Sem\s+Multa|$)", t, re.I)
    if m:
        d = _pena_max_do_texto(m.group(2))
        if d:
            return d
    # texto do tipo cortado ou ilegível: tabela editável da base jurídica (pena_maxima_abstrata)
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
    if v is None and (lei == "3688" or (not mp and t.upper().startswith("CAPUT"))):
        v = tab.get("%s:%s" % (lei, art))  # contravenção: o caput vale para os parágrafos sem aumento próprio
    if v is None and lei == "3688":
        # contravenção fora da tabela: a prisão simples nunca passa de 5 anos (LCP, art. 10)
        c["_pena_max_fonte"] = "LCP, art. 10"
        return 5 * DIAS_ANO
    if v is None:
        return None
    c["_pena_max_fonte"] = "tabela"
    # anos inteiros de 365 dias e a fração em meses de 30 dias (convenção do SEEU): 0.25 = 3 meses = 90 dias
    anos_ = int(float(v))
    return anos_ * DIAS_ANO + int(round((float(v) - anos_) * 12 * 30))


def _pena_max_do_texto(faixa):
    """'6 anos e 8 meses a 16 anos e 8 meses' / '1 a 4 anos' / '15 dias a 3 meses' -> dias do máximo; None se ilegível."""
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


TIPOS_VD_COMUNS = {("3688", "21"), ("2848", "147"), ("2848", "129"), ("2848", "150"), ("2848", "163"), ("2848", "140"), ("2848", "139"), ("2848", "138")}


def vd_contexto(c, ativos):
    """Crime típico de violência doméstica (vias de fato, ameaça, lesão, dano, crimes contra a honra etc.) sem sinal
    próprio no RSPE, mas na mesma execução há condenação por violência doméstica: não se presume nem se afasta -
    devolve o motivo para conferir; senão None."""
    if violencia_domestica(c):
        return None
    lei = num_lei(c.get("lei")) or "2848"
    if "PENAL" in (c.get("lei") or "").upper() and "CONTRAVEN" not in (c.get("lei") or "").upper():
        lei = "2848"
    if (lei, num_art(c.get("artigo"))) not in TIPOS_VD_COMUNS:
        return None
    outros = [o for o in ativos if o is not c and (violencia_domestica(o) or ("", ""))[0] == "sim"]
    if not outros:
        return None
    return "a execução tem condenação por violência doméstica (%s, proc. %s) e o RSPE não informa a vara nem a vítima deste processo (%s)" % (
        crimes_curto(outros[:1]), outros[0].get("processo_criminal") or "?", c.get("processo_criminal") or "?")


def exclusao_art7_2022(c):
    """Devolve texto do inciso do art. 7º do Decreto 11.302/2022 que exclui o crime, ou None."""
    lei, art = num_lei(c.get("lei")), num_art(c.get("artigo"))
    codigo_penal = lei in ("2848", "") or ("PENAL" in (c.get("lei") or "").upper() and "MILITAR" not in (c.get("lei") or "").upper())
    if trafico_incerto(c):
        return None  # a verificar (impeditivo_verificar)
    if e_hediondo(c, DECRETO_2022_REF):
        if not e_hediondo(c):
            if c.get("vga") == "S":
                # a tese da hediondez superveniente não aproveita: o crime é excluído também pela violência (inciso II)
                return "II: praticado com violência ou grave ameaça"
            d, lei_h = hediondo_desde(c)
            return "I: hediondo (%s, vigência %s) aferido na data do decreto (STJ) · fato anterior - tese defensiva: irretroatividade (STF, 2ª T. e monocráticas; TJMS, 2ª Câm. Crim.)" % (lei_h or "Lei 8.072/90", fmt(d))
        return "I: hediondo ou equiparado (Lei 8.072/90)"
    vd = violencia_domestica(c)
    if vd and vd[0] == "sim":
        if lei == "11340":
            return "III, c: crime da Lei 11.340/06"
        return "II: com violência doméstica e familiar contra a mulher - %s" % vd[1]
    if c.get("vga") == "S":
        return "II: praticado com violência ou grave ameaça"
    if lei in ART7_2022_LEIS:
        return ART7_2022_LEIS[lei]
    if codigo_penal and art in ART7_2022_CP:
        return "%s: art. %s do CP" % (ART7_2022_CP[art], art)
    if lei == "11343" and art in ("33", "34", "36"):
        _tp = c.get("tipo_penal") or ""
        if art == "33" and (re.match(r"\s*§\s*[234](?!\d)", _tp) or "§ 4" in _tp):
            return None  # o inciso VI alcança só o caput e o § 1º do art. 33 (exceção expressa do § 4º; §§ 2º e 3º fora)
        return "VI: art. %s da Lei 11.343/06" % art
    if lei == "8069" and art in ART7_2022_ECA:
        return "VIII: art. %s do ECA" % art
    return None


def impeditivo_verificar(c):
    """Crime que só impede o indulto conforme dado que o RSPE não traz. Hoje: crime do Código Penal Militar, que só é
    impeditivo se corresponder aos incisos I a XVIII do art. 1º (Decretos 2024 e 2025, art. 1º, XIX) ou I a V do
    art. 7º (Decreto 2022, art. 7º, VII). Devolve o texto para conferir, ou ''."""
    if c.get("extinto", "").upper().startswith("S"):
        return ""
    if trafico_incerto(c):
        return ("tráfico (art. 33 da Lei 11.343/06) sem indicação, no RSPE, de caput/§ 1º ou do § 4º: caput ou § 1º é impeditivo "
                "(Decretos 2024 e 2025, art. 1º, XVIII; Decreto 2022, art. 7º, I e VI); o § 4º (privilegiado) não é (STJ, Tema 1336; STF, Tema 1400) - conferir na sentença")
    if num_lei(c.get("lei")) == "1001" or "MILITAR" in (c.get("lei") or "").upper():
        return "crime militar (CPM): só impede se corresponder a crime do art. 1º, I a XVIII (Decretos 2024 e 2025, XIX) ou do art. 7º, I a V (Decreto 2022, VII) - conferir"
    if num_art(c.get("artigo")) == "129" and num_lei(c.get("lei")) in ("2848", "") and hediondo_condicional(c) is None and not e_hediondo(c):
        return ("lesão gravíssima ou seguida de morte (art. 129, § 2º ou § 3º): hediondo só contra agente de segurança, membro do Judiciário, "
                "do MP ou da Defensoria, ou em escola (Lei 8.072, art. 1º, I-A) - conferir a vítima")
    return ""


NUM_DECRETO = {"2022": "11.302/2022", "2024": "12.338/2024", "2025": "12.790/2025"}


def _pct_txt(v):
    return ("%.1f" % v).replace(".", ",") + "%"


def _explica_inciso(p, pena_total, cumprido):
    """'VII: regime aberto, cumprido 1/5' -> texto com a conta (exigido x cumprido)."""
    inc, _, txt = p.partition(":")
    txt = txt.strip()
    if not re.match(r"^[IVX]+(\s+e\s+[IVX]+)?$", inc.strip()):
        return "Obs.: " + p.strip()  # observação, não inciso
    # fração simples perto de "cumprid" (não confunde com número de lei, como 10.826/03)
    m = re.search(r"(?<![\d./])([1-9])/([1-9]\d?)(?![\d/])\s*(?:\([^)]*\)\s*)?cumprid|cumprid[oa]s?\s+(?<![\d./])([1-9])/([1-9]\d?)(?![\d/])", txt)
    if m:
        a, b = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        m = type("M", (), {"group": lambda self, i, _a=a, _b=b: {1: _a, 2: _b}[i]})()
    conta = ""
    if m and pena_total:
        fr = Fraction(int(m.group(1)), int(m.group(2)))
        exig = int(pena_total * fr)
        conta = " Exige %s da pena (%s); cumprido %s: %s." % (
            "%s/%s" % (m.group(1), m.group(2)), dias_para_pena(exig), dias_para_pena(cumprido), "atende" if cumprido >= exig else "não atende")
    return "Inciso %s: %s.%s" % (inc.strip(), txt.rstrip("."), conta)


def _curto_nao(n):
    inc, _, txt = n.partition(":")
    txt = re.sub(r"^\s*não se aplica[m]?\s*-\s*", "", txt.strip())
    return "%s (%s)" % (inc.strip(), txt)


def analise_decreto_2022(campos, crimes, eventos, incidentes):
    """Decreto 11.302/2022: art. 5º (pena máxima em abstrato do crime ≤ 5 anos, crime a crime - parágrafo único),
    art. 4º (maiores de 70 anos com 1/3 cumprido), art. 1º (saúde - laudo), art. 7º (exclusões), art. 9º (independe
    de trânsito em julgado). Não exige fração cumprida nem regime. STF: a ADI 7.330 suspendeu (medida cautelar de
    16/01/2023) o art. 6º, caput e parágrafo único, e o art. 7º, § 3º (agentes de segurança pública); os arts. 2º, 3º e 6º
    (agentes públicos) não são avaliados aqui; o art. 5º foi mantido pelo STF em 2025 (RE 1.450.100)."""
    ref = DECRETO_2022_REF
    out = {}
    ativos = [c for c in crimes if not c.get("extinto", "").upper().startswith("S")]
    # fato posterior ao decreto: não é alcançado, mas não impede o indulto das penas anteriores (art. 11: penas somadas
    # até 25/12/2022; STJ, HC 190.963). A análise segue só com os crimes de fato anterior.
    posteriores = [c for c in ativos if (to_date(c.get("data_infracao") or "") or date.min) > ref]
    ativos = [c for c in ativos if c not in posteriores]
    linhas, alcanca, verificar = [], [], []
    vd_conf = []
    if posteriores:
        linhas.append("Obs.: fato posterior a 25/12/2022 (%s): o decreto não alcança essa pena, que segue em execução; a análise usa só os crimes anteriores "
                      "(art. 11; STJ, HC 190.963)." % "; ".join("%s, fato de %s" % (crimes_curto([c]), c.get("data_infracao")) for c in posteriores))
    for c in ativos:
        nome = crimes_curto([c]) or ("art. %s %s" % (num_art(c.get("artigo")) or "?", lei_curta(c.get("lei"))))
        fato = to_date(c.get("data_infracao") or "")
        excl = exclusao_art7_2022(c)
        cpm = impeditivo_verificar(c)
        if cpm and not excl:
            linhas.append("? %s: %s" % (nome, cpm))
            verificar.append(nome)
            continue
        if excl:
            linhas.append("✗ %s: excluído pelo art. 7º, %s" % (nome, excl))
            continue
        pm = pena_maxima_abstrata(c)
        vdc = vd_contexto(c, ativos)
        if vdc and pm is not None and pm <= 5 * DIAS_ANO and not (fato and fato > ref):
            linhas.append("? %s: pena máxima em abstrato %s ≤ 5 anos (art. 5º), mas %s - confirmar se houve violência doméstica e familiar contra a mulher (art. 7º, II)" % (
                nome, dias_para_pena(pm), vdc))
            verificar.append(nome)
            vd_conf.append(nome)
            continue
        if pm is None:
            linhas.append("? %s: pena máxima em abstrato não lida do RSPE - conferir o tipo penal" % nome)
            verificar.append(nome)
            continue
        if pm <= 5 * DIAS_ANO and ("CONVERTIDA" in (c.get("pena_total_processo") or "").upper() or re.search(r"RESTRITIVA|\bPRD\b", (c.get("regime_sentenca") or "").upper())):
            # art. 8º, I: o indulto não se estende às penas restritivas de direitos; o RSPE não diz se, em 25/12/2022,
            # a pena já tinha sido reconvertida em privativa de liberdade (caso em que o art. 5º a alcança)
            linhas.append("? %s: pena substituída ou convertida (%s) - se em 25/12/2022 ainda era restritiva de direitos, o art. 8º, I, exclui o indulto; "
                          "reconvertida em privativa de liberdade antes dessa data, vale o art. 5º - conferir" % (
                              nome, (c.get("pena_total_processo") or c.get("regime_sentenca") or "").split(" - ")[-1].strip().lower()))
            verificar.append(nome)
            continue
        if fato and fato > ref:
            linhas.append("✗ %s: fato de %s, posterior ao decreto" % (nome, fmt(fato)))
            continue
        if pm <= 5 * DIAS_ANO:
            tr = to_date(c.get("transito_processo") or c.get("transito_mp") or "")
            tr_mp = to_date(c.get("transito_mp") or "")
            if tr and tr > ref and tr_mp and tr_mp <= ref:
                # art. 9º: cabe sem trânsito para a defesa; a acusação já não recorria em 25/12/2022 (art. 9º, p. ú.)
                linhas.append("✓ %s: pena máxima em abstrato %s ≤ 5 anos (art. 5º) - trânsito para a acusação em %s, antes do decreto (art. 9º)" % (nome, dias_para_pena(pm), fmt(tr_mp)))
                alcanca.append(nome)
            elif tr and tr > ref and not tr_mp:
                # art. 9º: o indulto cabe sem trânsito em julgado; o RSPE não registra recurso da acusação (p. ú.)
                linhas.append("✓ %s: pena máxima em abstrato %s ≤ 5 anos (art. 5º) - trânsito em %s, depois do decreto: o art. 9º admite o indulto sem trânsito e o RSPE não registra recurso da acusação" % (nome, dias_para_pena(pm), fmt(tr)))
                alcanca.append(nome)
            elif tr and tr > ref:
                linhas.append("? %s: pena máxima em abstrato %s ≤ 5 anos (art. 5º), mas trânsito em %s, depois de 25/12/2022, e trânsito para a acusação em %s - conferir se havia recurso da acusação após o 2º grau nessa data (art. 9º, p. ú.)" % (nome, dias_para_pena(pm), fmt(tr), fmt(tr_mp)))
                verificar.append(nome)
            else:
                linhas.append("✓ %s: pena máxima em abstrato %s ≤ 5 anos (art. 5º)%s" % (nome, dias_para_pena(pm), (" - contravenção: prisão simples não passa de 5 anos (LCP, art. 10)" if c.get("_pena_max_fonte") == "LCP, art. 10"
                     else " - pena máxima informada pelo operador (Auditoria)" if c.get("_pena_max_fonte") == "informada pelo operador"
                     else " - tipo cortado no RSPE, valor da tabela da base jurídica" if c.get("_pena_max_fonte") else "")))
                alcanca.append(nome)
        else:
            linhas.append("✗ %s: pena máxima em abstrato %s supera 5 anos" % (nome, dias_para_pena(pm)))
    idade = _idade_em(campos.get("data_nascimento"), ref)
    pena_total = pena_para_dias(campos.get("pena_total"))
    # art. 11: penas somadas até 25/12/2022 - condenação sem trânsito para a acusação nessa data fica fora da soma do art. 4º
    # (STJ, AgRg no HC 441.551); no art. 5º cada crime conta isoladamente e o art. 9º dispensa o trânsito
    pub22 = DECRETOS_PUB.get("2022") or ref
    sem_tr22 = [c for c in ativos if _sentenca_posterior(c, pub22)]
    if sem_tr22:
        linhas.append("Obs.: sentença posterior à publicação do decreto (23/12/2022) (%s): não havia condenação na data - fora da soma do art. 11 (art. 4º) - "
                      "STJ, AgRg no HC 441.551." % crimes_curto(sem_tr22))
    art9_22 = [c for c in ativos if _art2_ii(c, pub22)]
    if art9_22:
        linhas.append("? art. 9º: sentença anterior à publicação e trânsito só depois (%s) - o indulto cabe sem trânsito para a defesa, salvo recurso "
                      "da acusação após o julgamento em 2º grau (art. 9º, p. ú.) - conferir." % "; ".join(
                          "%s, trânsito em %s" % (crimes_curto([c]), c.get("transito_mp") or c.get("transito_processo")) for c in art9_22))
    if pena_total and (posteriores or sem_tr22):
        pena_total = max(1, pena_total - sum(pena_para_dias(c.get("pena_imposta")) or 0 for c in posteriores + sem_tr22))
    art4_ok = False
    art4_parcial = False
    art4_tese = False
    if idade is not None and idade >= 70 and pena_total and ativos:
        periodos = periodos_custodia(eventos)
        _rem = []
        for i in incidentes:
            if e_remicao_concedida(i):
                mr = dias_de(i.get("complemento", ""))
                if mr is not None:
                    _rem.append((to_date(i.get("data_referencia") or i.get("data_decisao") or ""), mr))
        try:
            cumprido, _ = cumprido_na_data(campos, periodos, _rem, ref, periodos_livramento(eventos, incidentes))
        except Exception:
            cumprido = dias_cumpridos_ate(periodos, _rem, ref)
        # art. 7º, § 2º: as vedações do inciso III, "b" (lavagem) e "d" (organização criminosa), e do inciso V
        # (arts. 312, 316, 317 e 333 do CP) não se aplicam ao art. 4º
        _bloq4 = [c for c in ativos if c not in sem_tr22 and exclusao_art7_2022(c) and not re.match(r"(III, [bd]|V):", exclusao_art7_2022(c))]
        if not _bloq4:
            if cumprido >= pena_total / 3.0:
                linhas.append("✓ art. 4º: %s em 25/12/2022 e 1/3 cumprido (%s de %s)" % (pl(idade, "ano", "anos"), dias_para_pena(cumprido), dias_para_pena(pena_total)))
                art4_ok = True
            else:
                linhas.append("✗ art. 4º: %s, mas 1/3 não cumprido até 25/12/2022 (%s de %s)" % (pl(idade, "ano", "anos"), dias_para_pena(cumprido), dias_para_pena(pena_total)))
        else:
            # art. 11, p. ú.: o crime excluído adia, não veda - cumprida a pena dele, o art. 4º alcança os demais
            # (1/3 da pena dos não impeditivos, com o tempo cumprido além da pena do impeditivo)
            p_imp = sum(pena_para_dias(c.get("pena_imposta")) or 0 for c in _bloq4)
            p_liv = max(0, pena_total - p_imp)
            if cumprido < p_imp:
                linhas.append("✗ art. 4º: %s, mas a pena do crime impeditivo (%s) não estava cumprida até 25/12/2022 (%s cumpridos; art. 11, p. ú.)" % (
                    pl(idade, "ano", "anos"), dias_para_pena(p_imp), dias_para_pena(cumprido)))
            elif p_liv and (cumprido - p_imp) >= p_liv / 3.0:
                linhas.append("✓ art. 4º: %s em 25/12/2022; pena do impeditivo cumprida (%s) e 1/3 da pena dos demais crimes cumprido (%s de %s; art. 11, p. ú.)" % (
                    pl(idade, "ano", "anos"), dias_para_pena(p_imp), dias_para_pena(cumprido - p_imp), dias_para_pena(p_liv)))
                art4_ok = art4_parcial = True
            elif p_liv and cumprido >= (p_imp + p_liv) / 3.0:
                # leitura literal, mais favorável e sem precedente específico: 1/3 da pena unificada (art. 11, caput) com a
                # pena do impeditivo cumprida (art. 11, p. ú.)
                linhas.append("? art. 4º: %s; pena do impeditivo cumprida (%s). Pela leitura do programa faltaria 1/3 da pena dos demais (%s de %s); "
                              "pela leitura literal (1/3 da pena unificada, art. 11, caput, com o impeditivo cumprido) atende: %s de %s - tese a sustentar, "
                              "sem precedente específico" % (pl(idade, "ano", "anos"), dias_para_pena(p_imp), dias_para_pena(cumprido - p_imp), dias_para_pena(p_liv),
                                                              dias_para_pena(cumprido), dias_para_pena(pena_total)))
                art4_tese = True
            elif p_liv:
                linhas.append("✗ art. 4º: %s; pena do impeditivo cumprida (%s), mas 1/3 da pena dos demais crimes não (%s de %s; art. 11, p. ú.)" % (
                    pl(idade, "ano", "anos"), dias_para_pena(p_imp), dias_para_pena(cumprido - p_imp), dias_para_pena(p_liv)))
    linhas.append("? art. 1º: saúde (paraplegia, doença grave, terminal) - não aferível pelo RSPE (laudo médico)")
    linhas.append("? art. 15: prestação de serviços à comunidade com 1/6 cumprido pode ser comutada em prestação pecuniária (salvo crimes do art. 7º, "
                  "I, II, III, a, c e e, IV, VI, VII e VIII) - conferir se há PSC")
    linhas.append("Obs.: art. 9º - indulto cabe mesmo sem trânsito para a defesa ou guia, salvo recurso da acusação após o 2º grau (p. ú.); "
                  "art. 8º - não se estende a PRD, multa e suspensão condicional do processo; arts. 2º e 6º (agentes de segurança) e 3º (militares em GLO) não avaliados; "
                  "art. 7º, § 1º (integrantes de facção) não aferível pelo RSPE.")
    if art4_ok:
        out["indulto_2022"] = ("POSSÍVEL: art. 4º para os crimes não impeditivos (%s em 25/12/2022; pena do impeditivo cumprida, art. 11, p. ú.)" % pl(idade, "ano", "anos")
                               if art4_parcial else "POSSÍVEL: art. 4º (%s em 25/12/2022 e 1/3 da pena cumprido)" % pl(idade, "ano", "anos"))
        out["indulto_2022_status"] = "possivel"
    elif art4_tese:
        out["indulto_2022"] = "A VERIFICAR: art. 4º (%s) - 1/3 da pena unificada cumprido e pena do impeditivo cumprida (leitura literal do art. 11)" % pl(idade, "ano", "anos")
        out["indulto_2022_status"] = "verificar"
    elif not ativos and posteriores:
        out["indulto_2022"], out["indulto_2022_status"] = "não se aplica: fatos posteriores a 25/12/2022", "nao"
    elif not ativos:
        out["indulto_2022"], out["indulto_2022_status"] = "sem crimes ativos no RSPE", "nao"
    elif alcanca and len(alcanca) >= len([c for c in ativos]):
        out["indulto_2022"] = "POSSÍVEL: art. 5º (todos os crimes com pena máxima ≤ 5 anos)"
        out["indulto_2022_status"] = "possivel"
    elif alcanca or (verificar and any(exclusao_art7_2022(c) for c in ativos)):
        # (com crime impeditivo, o art. 11, p. ú., decide antes do que ficou a verificar nos demais: pena do impeditivo
        # não cumprida em 25/12/2022 = não atinge, qualquer que seja o resultado da conferência)
        # art. 11: só entram na soma as penas existentes em 25/12/2022 - condenação por crime excluído posterior ao decreto
        # não trava o indulto (o p. ú. fala do concurso na data)
        _fora7_pos = [c for c in ativos if exclusao_art7_2022(c) and _sentenca_posterior(c, pub22)]
        _fora7 = [c for c in ativos if exclusao_art7_2022(c) and c not in _fora7_pos]
        if _fora7_pos:
            linhas.append("? art. 11 - tese: condenação por crime excluído com sentença posterior à publicação (%s) não entra na unificação de 25/12/2022 "
                          "(art. 11; STJ, AgRg no HC 441.551) e não impediria o indulto dos demais; o STF (SL 1.698 MC-Ref, 21/02/2024) e o STJ "
                          "(AgRg no HC 890.929) consideram óbice a pena de impeditivo remanescente - a verificar." % "; ".join(
                "%s, sentença de %s" % (crimes_curto([c]), c.get("data_sentenca")) for c in _fora7_pos))
        if not _fora7 and not alcanca:
            out["indulto_2022"] = "A VERIFICAR: %s%s" % (resumir_nomes(verificar), " - confirmar se houve violência doméstica (art. 7º, II)" if vd_conf else "")
            out["indulto_2022_status"] = "verificar"
        elif not _fora7:
            # art. 5º, p. ú.: em concurso, cada crime é avaliado isoladamente; o crime com pena máxima > 5 anos só não é alcançado
            _acima = len([c for c in ativos if not exclusao_art7_2022(c)]) - len(alcanca) - len(verificar)
            out["indulto_2022"] = "%s: art. 5º para %s%s%s%s" % (
                "A VERIFICAR" if _fora7_pos else "POSSÍVEL", resumir_nomes(alcanca),
                " (os crimes com pena máxima acima de 5 anos não são alcançados)" if _acima > 0 else "",
                " - tese: crime do art. 7º com sentença posterior à publicação fora da soma do art. 11 (o STF, SL 1.698, considera óbice a pena de impeditivo remanescente)" if _fora7_pos else "",
                (" | conferir %s" % resumir_nomes(verificar)) if verificar else "")
            out["indulto_2022_status"] = "verificar" if _fora7_pos else "possivel"
        else:
            # art. 11, p. ú.: o crime não impeditivo só é indultado depois de cumprida a pena do crime impeditivo
            # (STJ, 3ª Seção, AgRg no HC 890.929/SE, 24/04/2024: vale também para penas unificadas)
            pena_imp = sum(pena_para_dias(c.get("pena_imposta")) or 0 for c in _fora7)
            periodos = periodos_custodia(eventos)
            remicoes = []
            for i in incidentes:
                if e_remicao_concedida(i):
                    mr = dias_de(i.get("complemento", ""))
                    if mr is not None:
                        remicoes.append((to_date(i.get("data_referencia") or i.get("data_decisao") or ""), mr))
            try:
                cump22, _ = cumprido_na_data(campos, periodos, remicoes, ref, periodos_livramento(eventos, incidentes))
            except Exception:
                cump22 = None
            procs = "; ".join("proc. %s (%s, %s)" % (c.get("processo_criminal") or "?", crimes_curto([c]), dias_para_pena(pena_para_dias(c.get("pena_imposta")) or 0)) for c in _fora7)
            if cump22 is not None and pena_imp:
                # imputação: a pena inteira do impeditivo primeiro (no Decreto 2022, a pena integral - STF, RHC 246.431;
                # STJ, HC 930.896); o que sobra do cumprido é o tempo que vale para os demais crimes
                out["indulto_2022_imp"] = {"pena_imp": pena_imp, "exigido": pena_imp, "fracao": "100%", "cumprido_total": cump22}
            if cump22 is not None and pena_imp and cump22 < pena_imp:
                linhas.append("✗ Art. 11, p. ú.: o crime não impeditivo só é indultado depois de cumprida a pena do impeditivo. Impeditivos: %s; soma %s; cumprido em 25/12/2022: %s - faltavam %s." % (
                    procs, dias_para_pena(pena_imp), dias_para_pena(cump22), dias_para_pena(pena_imp - cump22)))
                out["indulto_2022"] = "não atinge: pena dos crimes impeditivos não cumprida até 25/12/2022 (art. 11, p. ú.)"
                out["indulto_2022_status"] = "nao"
            elif cump22 is not None and pena_imp:
                linhas.append("✓ Art. 11, p. ú.: pena dos crimes impeditivos cumprida até 25/12/2022 (soma %s; cumprido %s; a pena mais grave se executa primeiro - CP, art. 76). "
                              "Sobram %s de pena cumprida para os demais crimes. Impeditivos: %s." % (
                    dias_para_pena(pena_imp), dias_para_pena(cump22), dias_para_pena(cump22 - pena_imp), procs))
                if alcanca:
                    out["indulto_2022"] = "POSSÍVEL: art. 5º para %s (pena dos impeditivos já cumprida, art. 11, p. ú.)%s" % (
                        resumir_nomes(alcanca), (" | conferir %s" % resumir_nomes(verificar)) if verificar else "")
                    out["indulto_2022_status"] = "possivel"
                else:
                    out["indulto_2022"] = "A VERIFICAR: %s (pena dos impeditivos já cumprida, art. 11, p. ú.)" % resumir_nomes(verificar)
                    out["indulto_2022_status"] = "verificar"
            else:
                linhas.append("? Art. 11, p. ú.: conferir se a pena dos crimes impeditivos foi integralmente cumprida até 25/12/2022 - %s. Sem a pena cumprida na data, o programa não afere." % procs)
                out["indulto_2022"] = "A VERIFICAR: art. 5º para %s - conferir se a pena dos crimes impeditivos (%s) foi cumprida até 25/12/2022 (art. 11, p. ú.)" % (
                    resumir_nomes(alcanca or verificar), "; ".join("proc. %s" % (c.get("processo_criminal") or "?") for c in _fora7))
                out["indulto_2022_status"] = "verificar"
    elif verificar:
        out["indulto_2022"] = "A VERIFICAR: %s%s" % (resumir_nomes(verificar), " - confirmar se houve violência doméstica (art. 7º, II)" if vd_conf else "")
        out["indulto_2022_status"] = "verificar"
    else:
        if all(to_date(c.get("data_infracao") or "") and to_date(c.get("data_infracao")) > ref for c in ativos):
            out["indulto_2022"] = "não se aplica: fatos posteriores a 25/12/2022"
        elif all(exclusao_art7_2022(c) for c in ativos):
            out["indulto_2022"] = "excluído (art. 7º)"
        else:
            out["indulto_2022"] = "não atinge: pena máxima em abstrato superior a 5 anos (art. 5º)"
        out["indulto_2022_status"] = "nao"
    if posteriores and ativos:
        out["indulto_2022"] += " | fato posterior a 25/12/2022 (%s): pena segue em execução" % crimes_curto(posteriores)
    out["indulto_2022_detalhe"] = "Decreto 11.302/2022 - referência 25/12/2022\n" + "\n".join(linhas)
    ex = ["Decreto 11.302/2022 · data de referência 25/12/2022. Art. 5º: indulto para o crime com pena máxima cominada de até 5 anos; "
          "em concurso, cada crime conta isoladamente. Não exige tempo cumprido nem regime. Havendo crime excluído (art. 7º), o crime não impeditivo só é indultado depois de cumprida a pena do impeditivo (art. 11, p. ú.; STJ, 3ª Seção, AgRg no HC 890.929/SE)."]
    for l in linhas:
        if re.search(r"saúde|^Obs\.: art\. 9º", l):
            continue
        l2 = l.replace("tipo cortado no RSPE, valor da tabela da base jurídica", "o RSPE não trouxe a pena cominada; valor da tabela do programa")
        l2 = re.sub(r"^✓ (.+?): pena máxima em abstrato (\S+) ≤ 5 anos \(art\. 5º\)", r"✔ \1: pena máxima cominada de \2, dentro do limite de 5 anos", l2)
        l2 = re.sub(r"^✗ (.+?): pena máxima em abstrato (\S+) supera 5 anos", r"✘ \1: pena máxima cominada de \2, acima de 5 anos", l2)
        l2 = re.sub(r"^\? (.+?): pena máxima em abstrato (\S+) ≤ 5 anos \(art\. 5º\), mas trânsito em (\S+), depois de 25/12/2022, e trânsito para a acusação em (\S+) - ",
                    r"? \1: pena máxima cominada de \2 (dentro do limite), mas o trânsito é de \3 e o da acusação de \4, posteriores ao decreto; o art. 9º admite o indulto sem trânsito, salvo recurso da acusação após o 2º grau - ", l2)
        l2 = re.sub(r"^✓ (.+?): pena máxima em abstrato (\S+) ≤ 5 anos \(art\. 5º\) - trânsito em",
                    r"✔ \1: pena máxima cominada de \2, dentro do limite de 5 anos; trânsito em", l2)
        l2 = re.sub(r"^✓ (.+?): pena máxima em abstrato (\S+) ≤ 5 anos \(art\. 5º\) - trânsito para a acusação",
                    r"✔ \1: pena máxima cominada de \2, dentro do limite de 5 anos; trânsito para a acusação", l2)
        ex.append(l2.replace("✓", "✔").replace("✗", "✘"))
    # crimes iguais com o mesmo resultado: uma linha só, com (xN)
    cont, ordem = {}, []
    for l in ex:
        if l not in cont:
            ordem.append(l)
        cont[l] = cont.get(l, 0) + 1
    ex = [re.sub(r"^([✔✘?] [^:]+):", lambda m: "%s (x%d):" % (m.group(1), cont[l]), l, count=1) if cont[l] > 1 else l for l in ordem]
    st22 = out.get("indulto_2022_status")
    ex.append("Conclusão: " + {"possivel": ("indulto possível pelo art. 4º (idade)." if art4_ok else "indulto possível pelo art. 5º."), "verificar": "a verificar - " + out.get("indulto_2022", "").replace("A VERIFICAR: ", "") + "."}.get(
        st22, (out.get("indulto_2022") or "não atinge").split(" | ")[0] + "."))
    out["indulto_2022_explica"] = "\n".join(ex)
    return out


DECRETO_NUM = {"2022": "11302", "2024": "12338", "2025": "12790"}


def decisoes_decreto(incidentes, ano, tipo):
    """Incidentes do RSPE sobre o decreto do ano (tipo 'INDULTO' ou 'COMUTA'): [(situacao, data)]."""
    num = DECRETO_NUM[ano]
    out = []
    for i in incidentes:
        txt = ((i.get("tipo") or "") + " " + (i.get("complemento") or "")).upper()
        if tipo in (i.get("tipo") or "").upper() and num in re.sub(r"[.\s]", "", txt):
            out.append((i.get("situacao") or "", i.get("data_decisao") or i.get("data_referencia") or ""))
    return out


def aplicar_decisoes_decretos(r, incidentes):
    """Se o RSPE já registra decisão sobre o decreto (concedido/indeferido/pendente), ela prevalece sobre a triagem."""
    for ano in ("2022", "2024", "2025"):
        for chave, tipo in (("indulto_%s" % ano, "INDULTO"), ("comutacao_%s" % ano, "COMUTA")):
            if chave not in r:
                continue
            dec = decisoes_decreto(incidentes, ano, tipo)
            if not dec:
                continue
            sit, dt = dec[-1]
            calc = r.get(chave) or ""
            if sit == "CONCEDIDO":
                r[chave] = "CONCEDIDO no RSPE em %s" % dt
            elif sit.startswith("NÃO") or sit.startswith("NAO"):
                r[chave] = "INDEFERIDO no RSPE em %s" % dt
            else:
                r[chave] = calc + " | pedido pendente no RSPE"
                continue
            if chave.startswith("indulto"):
                r[chave + "_status"] = "nao"
                kc = "comutacao_%s" % ano
                if r.get(kc, "").startswith("prejudicada") and r.get(kc + "_se_indeferido"):
                    # indulto indeferido/concedido no RSPE: a comutação não fica prejudicada pela triagem
                    r[kc] = r[kc + "_se_indeferido"] if sit != "CONCEDIDO" else "prejudicada: indulto concedido no RSPE"
                    r[kc + "_detalhe"] = (r.get(kc + "_detalhe") or "").replace(
                        "Prejudicada: o indulto é cabível e prevalece (art. 13, § 5º).",
                        ("Indulto indeferido no RSPE em %s: a comutação não fica prejudicada." % dt) if sit != "CONCEDIDO" else ("Prejudicada: indulto concedido no RSPE em %s." % dt))
                r[chave + "_detalhe"] = ("Decisão registrada no RSPE (%s em %s). Triagem do programa: %s\n" % (sit.lower(), dt, calc.split(" | ")[0])) + (r.get(chave + "_detalhe") or "")


def aplicar_extincoes(r, crimes, incidentes):
    """Leva em conta as extinções que o RSPE registra fora da linha "Extinto:" do crime:
    - "(Extinta)" ao lado do número do processo criminal;
    - incidente EXTINÇÃO (concedido) com "Processos Selecionados" - ou sem processo, quando alcança a execução toda.
    Marca o crime como extinto (extinto_rspe guarda o valor original para a auditoria)."""
    ext_inc = [i for i in incidentes if "EXTIN" in (i.get("tipo") or "").upper() and i.get("situacao", "CONCEDIDO") == "CONCEDIDO"]
    geral = []
    for c in crimes:
        c["extinto_rspe"] = c.get("extinto_rspe", c.get("extinto", ""))  # valor original do RSPE (a análise pode ser refeita)
        c["extinto"] = c["extinto_rspe"]
        c["extincao_fonte"] = ""
        c.pop("indulto_duvida", None)
        c.pop("indultado_rspe", None)
        sit_p = (c.get("processo_situacao") or "").upper()
        if sit_p.startswith("EXTINT") or sit_p.startswith("INDULTAD"):
            # "(Indultada)": a pena do processo foi extinta pelo indulto (CP, art. 107, II)
            c["extinto"] = "Sim"
            c["extincao_fonte"] = "processo marcado \"(%s)\" no RSPE" % c["processo_situacao"]
            if sit_p.startswith("INDULTAD"):
                c["extincao_motivo"] = "indulto"
    # indulto concedido no RSPE com processos selecionados: extingue a pena desses processos (CP, art. 107, II)
    for i in incidentes:
        if (i.get("tipo") or "").strip().upper().startswith("INDULTO") and i.get("situacao", "CONCEDIDO") == "CONCEDIDO":
            procs = [chave_processo(p) for p in lista_processos(i.get("processos") or "")]
            d = i.get("data_decisao") or i.get("data_referencia") or ""
            dec = re.search(r"(\d{1,2}\.\d{3})", i.get("complemento") or "")
            d_ind = to_date(d)
            # comutação concedida depois, para o mesmo processo: a pena continuou em execução (o indulto pode ter sido
            # revogado ou reformado sem registro no RSPE) - não se trata como extinta; a Auditoria pede conferência
            com_dep = [j for j in incidentes if "COMUTA" in (j.get("tipo") or "").upper() and j.get("situacao", "CONCEDIDO") == "CONCEDIDO"
                       and (to_date(j.get("data_decisao") or j.get("data_referencia") or "") or date.min) > (d_ind or date.max)]
            for c in crimes:
                k = chave_processo(c.get("processo_criminal"))
                if procs and k in procs and any(mesmo_processo(c.get("processo_criminal"), x) for j in com_dep for x in lista_processos(j.get("processos") or "")):
                    c["indulto_duvida"] = {"data": d, "decreto": dec.group(1) if dec else "",
                                           "comutacao": next(j.get("data_decisao") or j.get("data_referencia") for j in com_dep
                                                             if any(mesmo_processo(c.get("processo_criminal"), x) for x in lista_processos(j.get("processos") or "")))}
                    continue
                if procs and k in procs and not c.get("extinto", "").upper().startswith("S"):
                    c["extinto"] = "Sim"
                    c["data_extincao"] = c.get("data_extincao") or d
                    c["extincao_motivo"] = "indulto%s" % ((" (Decreto %s)" % dec.group(1)) if dec else "")
                    c["extincao_fonte"] = "incidente INDULTO concedido%s%s" % ((" (Decreto %s)" % dec.group(1)) if dec else "", " em " + d if d else "")
                    c["indultado_rspe"] = True
    for i in ext_inc:
        procs = [chave_processo(p) for p in lista_processos(i.get("processos") or "")]
        d = i.get("data_referencia") or i.get("data_decisao") or ""
        motivo = (i.get("complemento") or "").strip() or "extinção"
        if procs:
            for c in crimes:
                if chave_processo(c.get("processo_criminal")) in procs:
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


def e_concessao_livramento(i):
    """Incidente CONCEDIDO que concede o livramento (exclui revogação e suspensão do livramento)."""
    if i.get("situacao") != "CONCEDIDO" or not e_incidente_livramento(i):
        return False
    return not re.search(r"REVOG|SUSPENS|CASSA", ((i.get("tipo") or "") + " " + (i.get("complemento") or "")).upper())


def e_revogacao_livramento(i):
    """Revogação do livramento condicional efetivamente decidida: incidente CONCEDIDO que menciona revogação e
    livramento. Pedido de revogação indeferido, revogação de prisão ou de saída temporária não contam."""
    t = ((i.get("tipo") or "") + " " + (i.get("complemento") or "")).upper()
    return (i.get("situacao") or "CONCEDIDO") == "CONCEDIDO" and "REVOG" in t and "LIVRAMENTO" in t


def e_suspensao_livramento(i):
    """Suspensão do livramento condicional decidida (incidente CONCEDIDO)."""
    t = ((i.get("tipo") or "") + " " + (i.get("complemento") or "")).upper()
    return (i.get("situacao") or "CONCEDIDO") == "CONCEDIDO" and "SUSPENS" in t and "LIVRAMENTO" in t


def periodos_livramento(eventos, incidentes):
    """Períodos de prova do livramento condicional concedido [(inicio, fim|None)]: terminam na revogação ou
    suspensão decidida, na regressão concedida ou na interrupção posterior (a prescrição não corre e a pena se cumpre)."""
    per = []
    for i in incidentes:
        if not e_concessao_livramento(i):
            continue
        ini = to_date(i.get("data_referencia") or i.get("data_decisao") or i.get("complemento") or "")
        if not ini:
            continue
        fins = []
        for j in incidentes:
            t = ((j.get("tipo") or "") + " " + (j.get("complemento") or "")).upper()
            if e_revogacao_livramento(j) or e_suspensao_livramento(j) or (j.get("situacao") == "CONCEDIDO" and "REGRESS" in t):
                fins.append(to_date(j.get("data_referencia") or j.get("data_decisao") or ""))
        for e in eventos:
            if "INTERRUP" in (e.get("tipo") or "").upper():
                fins.append(to_date(e.get("data") or ""))
        fins = [d for d in fins if d and d > ini]
        per.append((ini, min(fins) if fins else None))
    return per


def livramento_em_curso(campos, incidentes, ref=None):
    """(True/False, data) - livramento condicional vigente: o SEEU imprime "(Em livramento condicional
    deferido em dd/mm/aaaa)", ou há incidente de LC concedido sem revogação posterior."""
    dl = None
    m = RE_DATA.search(campos.get("livramento_obs_seeu") or "")
    if "LIVRAMENTO" in (campos.get("livramento_obs_seeu") or "").upper():
        dl = to_date(m.group(1)) if m else date.min
    if not dl:
        for i in incidentes:
            if e_concessao_livramento(i):  # a suspensão e a revogação não são deferimento
                d = to_date(i.get("data_referencia") or i.get("data_decisao") or i.get("complemento") or "")
                if d and (dl is None or d > dl):
                    dl = d
    if not dl:
        return False, None
    revog = [to_date(j.get("data_referencia") or j.get("data_decisao") or "") or date.max for j in incidentes if e_revogacao_livramento(j)]
    if any(d > dl and (ref is None or d <= ref) for d in revog):
        return False, dl
    # suspensão do livramento registrada em incidente concedido depois do deferimento: não está em livramento
    susp = [to_date(j.get("data_referencia") or j.get("data_decisao") or "") or date.max for j in incidentes if e_suspensao_livramento(j)]
    if dl != date.min and any(d > dl and (ref is None or d <= ref) for d in susp):
        return False, dl
    if ref is not None and dl != date.min and dl > ref:
        return False, dl
    # regressão (inclusive cautelar) concedida depois do deferimento: o livramento deixou de vigorar,
    # ainda que a 1ª página do RSPE continue a imprimir "Em livramento condicional deferido em ..."
    if dl != date.min:
        for i in incidentes:
            t = ((i.get("tipo") or "") + " " + (i.get("complemento") or "")).upper()
            d = to_date(i.get("data_referencia") or i.get("data_decisao") or "")
            if i.get("situacao") == "CONCEDIDO" and "REGRESS" in t and d and d > dl and (ref is None or d <= ref):
                return False, dl
    if "LIVRAMENTO" in (campos.get("regime_atual") or "").upper():
        return True, dl
    # livramento superado: regime fixado/alterado por decisão posterior (nova condenação, somatório,
    # regressão, progressão). Vale o regime que o RSPE imprime.
    if dl != date.min and "LIVRAMENTO" not in (campos.get("livramento_obs_seeu") or "").upper():
        for i in incidentes:
            t = ((i.get("tipo") or "") + " " + (i.get("complemento") or "")).upper()
            d = to_date(i.get("data_referencia") or i.get("data_decisao") or "")
            if i.get("situacao") == "CONCEDIDO" and "REGIME" in t and "DATA-BASE" not in t and d and d > dl and (ref is None or d <= ref):
                return False, dl
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
    # a 1ª página do RSPE declarando "Em livramento condicional deferido em ..." prevalece sobre o "Regime Atual"
    # (o SEEU mantém ali o regime anterior ao livramento)
    seeu_lc = bool(re.search(r"LIVRAMENTO CONDICIONAL DEFERIDO", (campos.get("livramento_obs_seeu") or "").upper()))
    if reg and "LIVRAMENTO" not in reg.upper() and not seeu_lc:
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
        if e_concessao_livramento(i):
            d = to_date(i.get("data_referencia") or i.get("data_decisao") or i.get("complemento") or "")
            if d and d <= ref and (dlc is None or d > dlc):
                dlc = d
    if dlc:
        revogado = any((e_revogacao_livramento(j) or e_suspensao_livramento(j))
                       and dlc < (to_date(j.get("data_referencia") or j.get("data_decisao") or "") or date.min) <= ref for j in incidentes)
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
    Parâmetros (frações, tetos, anos) vêm da base jurídica (decretos_indulto.art9_incisos).
    Condenação por fato posterior à data do decreto não é alcançada, mas não impede o indulto nem a comutação das
    penas anteriores (art. 7º: penas somadas até 25/12; art. 6º, p. ú.; STJ, HC 190.963): a análise usa só os
    crimes de fato anterior e anota que a pena do fato posterior segue em execução."""
    carregar_tabelas_decretos()
    A = art9_param
    out = {}
    todos_ativos = [c for c in crimes if not c.get("extinto", "").upper().startswith("S")]

    ano_de = {v: k for k, v in DECRETOS.items()}

    def _posteriores(ref):
        """Fora da soma do art. 7º: fato posterior à data do decreto, ou sentença posterior à publicação (não havia condenação
        na data - STJ, AgRg no HC 441.551). Sentença anterior com trânsito posterior fica na análise, a verificar (art. 2º, II)."""
        pub = DECRETOS_PUB.get(ano_de.get(ref)) or ref
        return [c for c in todos_ativos if (to_date(c.get("data_infracao") or "") or date.min) > ref or _sentenca_posterior(c, pub)]

    def _imped_em(ref):
        # hediondez aferida na data de cada decreto (25/12/2024 ou 25/12/2025), conforme o STJ; fato posterior fica fora
        post = _posteriores(ref)
        lst = []
        for c in crimes:
            if c in post:
                continue
            r = impeditivo_decreto(c, ref)
            if r:
                lst.append("art. 1º, %s: %s" % r)
        return list(dict.fromkeys(lst))
    imped_geral = []
    orcrim_algum = False
    for _ref in DECRETOS.values():
        imped_geral += _imped_em(_ref)
        orcrim_algum = orcrim_algum or any(c.get("comando_orcrim") == "S" for c in todos_ativos if c not in _posteriores(_ref))
    imped_geral = list(dict.fromkeys(imped_geral))
    if orcrim_algum:
        imped_geral.append("art. 1º, § 3º, I: comando de organização criminosa (em 2024 só o indulto, em 2025 indulto e comutação)")
    out["indulto_crime_impeditivo"] = "SIM" if imped_geral else "NÃO"
    out["indulto_crime_impeditivo_detalhe"] = "; ".join(imped_geral)

    pena_total_geral = pena_para_dias(campos.get("pena_total"))
    periodos = periodos_custodia(eventos)
    periodos_lc = periodos_livramento(eventos, incidentes)
    remicoes = []
    for i in incidentes:
        if e_remicao_concedida(i):
            m = dias_de(i.get("complemento", ""))
            if m is not None:
                remicoes.append((to_date(i.get("data_referencia") or i.get("data_decisao") or ""), m))
    saidas = [i for i in incidentes if i.get("situacao") == "CONCEDIDO" and re.search(r"SA[ÍI]DA TEMPOR", i.get("tipo", ""), re.I)]
    F = Fraction
    notas_post = {}
    notas_tr = {}

    for ano, ref in DECRETOS.items():
        k = "indulto_%s" % ano
        kc = "comutacao_%s" % ano
        posteriores = _posteriores(ref)
        ativos = [c for c in todos_ativos if c not in posteriores]
        pena_total = pena_total_geral
        publicacao = DECRETOS_PUB.get(ano)
        if posteriores:
            nomes_post = "; ".join(("%s, fato de %s" % (crimes_curto([c]), c.get("data_infracao"))) if (to_date(c.get("data_infracao") or "") or date.min) > ref else
                                   ("%s, sentença de %s" % (crimes_curto([c]), c.get("data_sentenca"))) for c in posteriores)
            so_sentenca = not [c for c in posteriores if (to_date(c.get("data_infracao") or "") or date.min) > ref]
            if not ativos and so_sentenca:
                out[k] = "não se aplica: sem condenação até %s (%s)" % (fmt(publicacao), nomes_post)
                out[k + "_status"] = "nao"
                out[k + "_detalhe"] = ("Nenhuma condenação existia na publicação do decreto (%s): sentenças posteriores (%s). As penas não entram na soma do art. 7º "
                                       "(STJ, AgRg no HC 441.551; AgRg no HC 919.210)." % (fmt(publicacao), nomes_post))
                out[kc] = "não se aplica: sem condenação até %s" % fmt(publicacao)
                continue
            if not ativos:
                out[k] = "não se aplica: condenação por fato posterior a %s (%s)" % (fmt(ref), nomes_post)
                out[k + "_status"] = "nao"
                out[k + "_detalhe"] = ("Todas as condenações ativas são por fato posterior a %s (%s): o decreto não as alcança." % (fmt(ref), nomes_post))
                out[k + "_explica"] = ("Decreto %s · data de referência %s.\n✘ Condenação só por fato posterior à data do decreto: %s. O decreto não alcança essas penas.\n"
                                       "Conclusão: não é hipótese de indulto deste decreto." % (NUM_DECRETO.get(ano, ano), fmt(ref), nomes_post))
                out[kc] = "não se aplica: condenação por fato posterior a %s" % fmt(ref)
                out[kc + "_detalhe"] = "Comutação: só há condenação por fato posterior a %s; o decreto não a alcança." % fmt(ref)
                continue
            p_post = sum(pena_para_dias(c.get("pena_imposta")) or 0 for c in posteriores)
            if pena_total:
                pena_total = max(1, pena_total - p_post)
            notas_post[ano] = (posteriores, nomes_post, p_post)
        vga = any(c.get("vga") == "S" for c in ativos)
        reinc = any(c.get("reincidente_comum") == "S" or c.get("reincidente_especifico") == "S" for c in ativos)
        patrimonial = ativos and all(crime_patrimonial(c) for c in ativos)
        orcrim = any(c.get("comando_orcrim") == "S" for c in ativos)
        cpm = [impeditivo_verificar(c) for c in ativos if impeditivo_verificar(c)]
        # sem nenhuma data de trânsito no RSPE: não se presume
        sem_tr_dado = [c for c in ativos if not (c.get("transito_mp") or c.get("transito_processo"))]
        if sem_tr_dado:
            notas_tr[ano] = ("Trânsito não consta no RSPE (%s): conferir a data da sentença e se havia recurso da acusação para majorar a pena em %s "
                             "(art. 2º, II; STJ, AgRg no HC 864.086 e 441.551)." % (crimes_curto(sem_tr_dado), fmt(publicacao)))
        # sentença anterior à publicação e trânsito depois: controvérsia do art. 2º, II - fica na análise, a verificar
        art2 = [c for c in ativos if _art2_ii(c, publicacao)]
        nota_art2 = ("\n? " + texto_art2_ii(art2, publicacao)[0].upper() + texto_art2_ii(art2, publicacao)[1:]) if art2 else ""
        imped = _imped_em(ref)
        imp_c = [c for c in ativos if impeditivo_decreto(c, ref)]
        imp_sup = [c for c in imp_c if "fato anterior" in impeditivo_decreto(c, ref)[1]]  # hediondez superveniente
        imp_est = [c for c in imp_c if c not in imp_sup]
        livres = [c for c in ativos if not impeditivo_decreto(c, ref)]
        veda_crime = bool(imped) and not livres and not (imp_sup and not imp_est)
        # art. 1º, § 3º, I: em 2024 a liderança de facção afasta só o indulto; em 2025, indulto e comutação
        orcrim_so_indulto = orcrim and ano == "2024" and not veda_crime
        if veda_crime or (orcrim and not orcrim_so_indulto):
            out[k] = "VEDADO (art. 1º)"
            out[k + "_status"] = "vedado"
            out[k + "_detalhe"] = "Crime impeditivo: " + "; ".join(imped + (["art. 1º, § 3º, I: comando de organização criminosa"] if orcrim else []))
            out[kc] = "VEDADA (art. 1º)"
            continue
        if not pena_total:
            out[k] = out[kc] = "sem pena no RSPE"
            out[k + "_status"] = "nao"
            # a pena total zerada não apaga o que já se sabe dos crimes: impeditivo e controvérsia do art. 2º, II
            out[k + "_detalhe"] = "\n".join(
                (["Pena total do RSPE zerada: conferir no SEEU se há pena a cumprir."] if ativos else []) +
                (["Crime impeditivo: " + "; ".join(imped)] if imped else []) +
                ([nota_art2.strip()] if art2 else []))
            continue

        def _xv_sem_cumprimento(motivo, det_base):
            """Art. 9º, XV: não exige fração cumprida nem regime. Sem cumprimento na data, fica 'a verificar' (ponto
            controvertido): o STJ exige início do cumprimento nos incisos com fração (AgRg no HC 1.042.931)."""
            pat = [c for c in ativos if crime_patrimonial(c) and c.get("vga") != "S"]
            if not pat or [c for c in ativos if impeditivo_decreto(c, ref)]:
                return False
            if orcrim:
                # art. 1º, § 3º, I: a liderança de facção afasta o indulto também aqui
                out[k] = "VEDADO (art. 1º, § 3º, I)"
                out[k + "_status"] = "vedado"
                out[k + "_detalhe"] = det_base + "\nArt. 1º, § 3º, I: o indulto não alcança integrante de facção com liderança em organização criminosa."
                return True
            ff, fv = falta_art6(incidentes, ref, eventos, publicacao)
            av = ""
            if ff:
                av = "FALTA nos 12 meses (art. 6º): " + "; ".join(ff) + (("; a verificar: " + "; ".join(fv)) if fv else "")
            elif fv:
                av = "falta a verificar (art. 6º: só impede se a sanção for reconhecida em juízo; STJ, Tema 1195): " + "; ".join(fv)
            out[k] = ("A VERIFICAR: art. 9º, XV - %s até %s; o inciso XV não exige fração cumprida (STJ exige início do cumprimento nos incisos com fração: "
                      "AgRg no HC 1.042.931)" % (motivo, fmt(ref))) + (" | " + av if av else "")
            if av:
                det_base += "\n⚠ " + av
            out[k + "_status"] = "verificar"
            out[k + "_detalhe"] = det_base + ("\n? XV: crime patrimonial sem violência ou grave ameaça (%s) - reparação do dano dispensada (art. 12, § 2º, I). "
                                              "Ponto controvertido: (a) o XV não exige tempo cumprido nem regime e o art. 2º, IV, admite o indulto sem guia; "
                                              "(b) o STJ exigiu início do cumprimento para o inciso VIII, que depende de fração (AgRg no HC 1.042.931, 5ª T., 24/06/2026). "
                                              "Não se localizou precedente sobre o XV.\n? XVI: saúde/deficiência - não aferível pelo RSPE (laudo médico)\n"
                                              "Multa: indultável (art. 12; incapacidade econômica presumida para assistido da Defensoria, art. 12, § 2º, I)." % crimes_curto(pat))
            out[k + "_explica"] = ("Decreto %s · data de referência %s.\n? Inciso XV: crime patrimonial sem violência (%s); %s. O inciso não exige fração; "
                                   "o STJ exige início do cumprimento nos incisos com fração - a verificar.\nConclusão: a verificar (XV)." % (
                                       NUM_DECRETO.get(ano, ano), fmt(ref), crimes_curto(pat), motivo))
            return True

        custodia_ref = em_custodia(periodos, ref)
        regime, dreg, lc = _regime_em(incidentes, ref, campos.get("regime_atual"), custodia_ref, campos)
        # Em cumprimento na data do decreto: preso/em regime naquela data, ou em regime (aberto/LC)
        # fixado por incidente anterior à data, ainda que sem custódia física.
        em_cumprimento = custodia_ref or lc or bool(regime and dreg and dreg <= ref)
        # regime fixado, mas sem início de cumprimento (sem custódia nem início do aberto registrado na data)
        sem_inicio = not custodia_ref and not lc and bool(regime and dreg and dreg <= ref)
        if sem_inicio:
            # regime fixado, mas a pena não estava sendo cumprida na data do decreto: não há indulto nem comutação
            definitivo = [e for e in eventos if re.search(r"PRIS|IN[ÍI]CIO|RECAPTURA", ((e.get("tipo") or "") + " " + (e.get("motivo") or "")).upper())
                          and not re.search(r"FLAGRANTE|PREVENTIV|TEMPOR|PROVIS", (e.get("motivo") or "").upper())
                          and (to_date(e.get("data") or "") or date.max) <= ref]
            motivo = "não iniciou o cumprimento" if not definitivo else "cumprimento interrompido"
            out[k] = "não se aplica: %s até %s" % (motivo, fmt(ref))
            out[k + "_status"] = "nao"
            out[k + "_detalhe"] = ("Regime %s fixado em %s, mas o RSPE não registra cumprimento em curso em %s (%s). "
                                   "Sem cumprimento na data, não há fração a aferir: os incisos com tempo cumprido e a comutação não se aplicam."
                                   % (regime, fmt(dreg), fmt(ref), motivo)) + nota_art2
            out[kc] = "não se aplica: %s até %s" % (motivo, fmt(ref))
            _xv_sem_cumprimento(motivo, out[k + "_detalhe"])
            continue
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
            out[k + "_detalhe"] = det + nota_art2
            out[kc] = "não se aplica"
            _xv_sem_cumprimento("sem pena em cumprimento", det + nota_art2)
            continue
        cumprido, cump_fonte = cumprido_na_data(campos, periodos, remicoes, ref, periodos_lc)
        cumprido_ref = cumprido  # tempo total cumprido na execução (IV e V contam anos de prisão, não fração da pena)
        remanescente = max(0, pena_total - cumprido)
        anos_pena = pena_total / float(DIAS_ANO)
        aberto = regime.upper().startswith("ABERTO")
        semi = regime.upper().startswith("SEMI")
        # art. 3º: indulto e comutação alcançam PRD e sursis (inciso VII e IX tratam deles como o aberto)
        prd = bool(re.search(r"RESTRITIVA|\bPRD\b|SURSIS|SUSPENS[ÃA]O CONDICIONAL DA PENA", (regime or "").upper()))
        idade = _idade_em(campos.get("data_nascimento"), ref)
        idade_min = (_base_decretos().get("art9_incisos") or {}).get("par2_idade_minima") or 60
        meia = idade is not None and idade >= idade_min  # § 2º, I (único grupo aferível pelo RSPE)
        red = F(1, 2) if meia else F(1, 1)
        falta_firme, falta_verif = falta_art6(incidentes, ref, eventos, publicacao)
        # art. 13, § 2º: com comutação anterior já concedida, a nova não exige novo requisito temporal
        com_ant = [i for i in incidentes if i.get("situacao") == "CONCEDIDO" and "COMUTA" in (i.get("tipo") or "").upper()
                   and (to_date(i.get("data_decisao") or i.get("data_referencia") or "") or date.max) <= ref
                   and DECRETO_NUM[ano] not in re.sub(r"[.\s]", "", (i.get("tipo") or "") + " " + (i.get("complemento") or ""))]

        def avaliar(pena_total, cumprido, remanescente, vga, patrimonial, ativos):
            anos_pena = pena_total / float(DIAS_ANO)
            def frac(nr, r, par2=True):
                # § 2º do art. 9º reduz pela metade só os lapsos dos incisos I a XI (não XII, XIII nem o art. 13)
                return (F(r) if reinc else F(nr)) * (red if par2 else 1)

            def tem(fr):
                return cumprido >= pena_total * fr

            def fmt_fr(nr, r, par2=True):
                f = frac(nr, r, par2)
                return "%s%s" % (f, " (½ pelo § 2º)" if (meia and par2) else "")

            possiveis, verificar, nao = [], [], []
            cump_txt = "cumprido %s de %s" % (dias_para_pena(cumprido), dias_para_pena(pena_total))

            # I
            if vga:
                nao.append("I: não se aplica - crime com violência ou grave ameaça")
            elif anos_pena > A("I", "pena_max_anos", 8):
                nao.append("I: não se aplica - pena total %s superior a %s" % (dias_para_pena(pena_total), pl(A("I", "pena_max_anos", 8), "ano", "anos")))
            else:
                f1 = (A("I", "fracao_primario", "1/5"), A("I", "fracao_reincidente", "1/3"))
                (possiveis if tem(frac(*f1)) else nao).append("I: pena ≤ %s sem VGA, exige %s (%s)" % (pl(A("I", "pena_max_anos", 8), "ano", "anos"), fmt_fr(*f1), cump_txt))
            # II
            if vga:
                nao.append("II: não se aplica - crime com violência ou grave ameaça")
            elif anos_pena > A("II", "pena_max_anos", 12):
                nao.append("II: não se aplica - pena total superior a %s" % pl(A("II", "pena_max_anos", 12), "ano", "anos"))
            else:
                f2 = (A("II", "fracao_primario", "1/3"), A("II", "fracao_reincidente", "1/2"))
                (possiveis if tem(frac(*f2)) else nao).append("II: pena ≤ %s sem VGA, exige %s (%s)" % (pl(A("II", "pena_max_anos", 12), "ano", "anos"), fmt_fr(*f2), cump_txt))
            # III
            if not vga:
                nao.append("III: não se aplica - crime sem violência ou grave ameaça (ver I e II)")
            elif anos_pena > A("III", "pena_max_anos", 4):
                nao.append("III: não se aplica - crime com VGA e pena total superior a %s" % pl(A("III", "pena_max_anos", 4), "ano", "anos"))
            else:
                f3 = (A("III", "fracao_primario", "1/3"), A("III", "fracao_reincidente", "1/2"))
                (possiveis if tem(frac(*f3)) else nao).append("III: pena ≤ %s com VGA, exige %s (%s)" % (pl(A("III", "pena_max_anos", 4), "ano", "anos"), fmt_fr(*f3), cump_txt))
            # IV
            continuo = _maior_periodo_continuo(periodos, ref)
            # art. 5º: a remição conta para integralizar o requisito temporal (remições concedidas dentro do período contínuo)
            _pc = max(((ini, (fim if (fim and fim <= ref) else ref)) for ini, fim in periodos if ini <= ref), key=lambda x: (x[1] - x[0]).days, default=None)
            rem_cont = sum(n for d, n in remicoes if _pc and d and _pc[0] <= d <= _pc[1])
            req = (A("IV", "anos_ininterruptos_reincidente", 20) if reinc else A("IV", "anos_ininterruptos_primario", 15)) * DIAS_ANO * red
            # indícios de interrupção dentro do período contínuo (o SEEU só separa os períodos quando registra INTERRUPÇÃO):
            # nova prisão/recaptura sem interrupção registrada, ou incidente de fuga/evasão/não retorno
            sinais_iv = []
            if _pc:
                for e in eventos:
                    d_e = to_date(e.get("data") or "")
                    if d_e and _pc[0] < d_e <= _pc[1] and "INTERRUP" not in (e.get("tipo") or "").upper():
                        sinais_iv.append("nova prisão (%s) em %s" % ((e.get("motivo") or e.get("tipo") or "").strip().lower(), fmt(d_e)))
                for i in incidentes:
                    t_i = ((i.get("tipo") or "") + " " + (i.get("complemento") or "")).upper()
                    d_i = to_date(i.get("data_referencia") or i.get("data_decisao") or "")
                    if d_i and _pc[0] <= d_i <= _pc[1] and re.search(r"FUGA|EVAS|ABANDONO|N[ÃA]O RETORNO|RECAPTURA", t_i):
                        sinais_iv.append("%s em %s" % ((i.get("tipo") or "").strip().lower(), fmt(d_i)))
            txt_iv = "IV: %s ininterruptos (tem %s%s)" % (
                pl(int(round(req / DIAS_ANO)), "ano", "anos"), dias_para_pena(continuo + rem_cont), (" = %s de custódia contínua desde %s + %s remidos, art. 5º" % (dias_para_pena(continuo), fmt(_pc[0]), pl(rem_cont, "dia", "dias"))) if rem_cont else (" desde %s" % fmt(_pc[0]) if _pc else ""))
            if continuo + rem_cont < req:
                nao.append(txt_iv)
            elif sinais_iv:
                verificar.append(txt_iv + " - verificar se houve interrupção no período: " + "; ".join(dict.fromkeys(sinais_iv)))
            else:
                possiveis.append(txt_iv)
            # V
            req = (A("V", "anos_reincidente", 25) if reinc else A("V", "anos_primario", 20)) * DIAS_ANO * red
            # anos de pena cumpridos na execução toda (penas somadas, art. 7º); no concurso com crime do art. 1º,
            # o parágrafo único só adia o indulto dos não impeditivos até 2/3 do impeditivo - não desconta esse tempo do V
            ct = max(cumprido, cumprido_ref)
            obs_ct = " na execução toda, penas somadas pelo art. 7º" if ct > cumprido else ""
            lib = _tempo_em_liberdade(periodos, ref)
            if ct >= req:
                (possiveis if lib <= A("V", "liberdade_max_anos", 2) * DIAS_ANO else nao).append(
                    "V: %s não ininterruptos (cumprido %s%s), liberdade %s %s (%s)" % (
                        pl(int(round(req / DIAS_ANO)), "ano", "anos"), dias_para_pena(ct), obs_ct, "≤" if lib <= A("V", "liberdade_max_anos", 2) * DIAS_ANO else ">",
                        pl(A("V", "liberdade_max_anos", 2), "ano", "anos"), dias_para_pena(lib)))
            else:
                nao.append("V: %s não ininterruptos (cumprido %s%s)" % (pl(int(round(req / DIAS_ANO)), "ano", "anos"), dias_para_pena(ct), obs_ct))
            # VI
            req = (A("VI", "anos_semiaberto_reincidente", 15) if reinc else A("VI", "anos_semiaberto_primario", 10)) * DIAS_ANO * red
            if semi and dreg:
                t = (ref - dreg).days
                (possiveis if t >= req else nao).append("VI: %s ininterruptos no semiaberto (desde %s: %s)" % (pl(int(round(req / DIAS_ANO)), "ano", "anos"), fmt(dreg), dias_para_pena(t)))
            else:
                nao.append("VI: exige semiaberto ininterrupto por %s" % pl(int(round(req / DIAS_ANO)), "ano", "anos"))
            # VII
            if aberto or prd:
                f7 = (A("VII", "fracao_primario", "1/6"), A("VII", "fracao_reincidente", "1/5"))
                (possiveis if tem(frac(*f7)) else nao).append("VII: %s, cumprido %s" % ("regime aberto" if aberto else "PRD/sursis", fmt_fr(*f7)))
            else:
                nao.append("VII: exige regime aberto, PRD ou sursis (em %s) - se houve PRD ou sursis, conferir nos autos" % (regime or "?"))
            # VIII
            lim = (A("VIII", "remanescente_max_anos_reincidente", 4) if reinc else A("VIII", "remanescente_max_anos_primario", 6)) * DIAS_ANO
            if aberto or lc:
                (possiveis if remanescente <= lim else nao).append(
                    "VIII: %s, remanescente em %s de %s (limite %s)" % ("livramento condicional" if lc else "regime aberto", fmt(ref), dias_para_pena(remanescente), pl(lim // DIAS_ANO, "ano", "anos")))
            else:
                nao.append("VIII: exige regime aberto ou livramento (em %s)" % (regime or "?"))
            # IX
            if aberto or lc or prd:
                verificar.append("IX: %s - verificar 2 anos em programa de egressos (patronato, escritório social)%s" % (
                    "PRD/sursis" if prd else "aberto/LC", " e se o regime aberto é o inicial (Decreto 2025)" if (ano == "2025" and aberto and not lc and not prd) else ""))
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
                sai_ref = [i for i in saidas if (to_date(i.get("data_referencia") or i.get("data_decisao") or "") or date.max) <= ref]
                if len(sai_ref) >= A("XI", "saidas_min", 5):
                    possiveis.append(txt + "%d saídas temporárias no RSPE até %s" % (len(sai_ref), fmt(ref)))
                else:
                    verificar.append(txt + "verificar 5 saídas temporárias ou 12 meses de trabalho externo (RSPE registra %s até %s)" % (pl(len(sai_ref), "saída", "saídas"), fmt(ref)))
            # XII
            f12 = (A("XII", "fracao_primario_%s" % ano, "1/6" if ano == "2025" else "1/5"), A("XII", "fracao_reincidente_%s" % ano, "1/5" if ano == "2025" else "1/4"))
            if anos_pena > 12:
                nao.append("XII: não se aplica - pena superior a 12 anos")
            elif tem(frac(*f12, par2=False)):
                verificar.append("XII: pena ≤ 12 anos, %s cumprido - verificar estudo por %s" % (
                    fmt_fr(*f12, par2=False), "18 meses nos 5 anos anteriores (reincidente)" if reinc else "12 meses nos 3 anos anteriores"))
            else:
                nao.append("XII: exige %s cumprido (%s)" % (fmt_fr(*f12, par2=False), cump_txt))
            # XIII
            if anos_pena > 12:
                nao.append("XIII: não se aplica - pena superior a 12 anos")
            elif tem(frac(A("XIII", "fracao_primario", "1/5"), A("XIII", "fracao_reincidente", "1/4"), par2=False)):
                verificar.append("XIII: pena ≤ 12 anos, %s cumprido - verificar conclusão de curso certificado nos 3 anos anteriores" % fmt_fr(A("XIII", "fracao_primario", "1/5"), A("XIII", "fracao_reincidente", "1/4"), par2=False))
            else:
                nao.append("XIII: exige %s cumprido (%s)" % (fmt_fr(A("XIII", "fracao_primario", "1/5"), A("XIII", "fracao_reincidente", "1/4"), par2=False), cump_txt))
            # XIV / XV: valem pelo crime (não têm teto de pena nem fração, salvo os 3 meses do XIV).
            # A soma do art. 7º serve aos incisos com teto/lapso; só o concurso com crime do art. 1º trava (art. 7º, p. ú.).
            pat = [c for c in ativos if crime_patrimonial(c) and c.get("vga") != "S"]
            imp_conc = [c for c in ativos if impeditivo_decreto(c, ref)]
            if pat and not imp_conc:
                parcial = "" if len(pat) == len(ativos) else " - alcança as penas de %s; as dos demais crimes (%s) seguem" % (
                    crimes_curto(pat), crimes_curto([c for c in ativos if c not in pat]))
                if cumprido >= A("XIV", "meses_cumpridos", 3) * 30:
                    verificar.append("XIV: crime patrimonial sem VGA, %s cumpridos - verificar bem ≤ 1 salário mínimo à época do fato%s" % (
                        pl(A("XIV", "meses_cumpridos", 3), "mês", "meses"), parcial))
                else:
                    nao.append("XIV: exige %s cumpridos" % pl(A("XIV", "meses_cumpridos", 3), "mês", "meses"))
                # art. 12, § 2º, I: incapacidade econômica presumida para o assistido da Defensoria -> reparação dispensada no XV
                possiveis.append("XV: crime patrimonial sem VGA - reparação do dano dispensada (art. 9º, XV c/c art. 12, § 2º, I: hipossuficiência presumida, Defensoria)%s" % parcial)
                if parcial:
                    verificar.append("XIV e XV são aferidos crime a crime: não têm teto de pena nem fração, e a soma do art. 7º serve aos incisos com teto/lapso. "
                                     "O art. 7º, parágrafo único, só trava o indulto no concurso com crime do art. 1º, e só até o cumprimento de 2/3 da pena dele.")
            elif pat and imp_conc:
                nao.append("XIV e XV: concurso com crime do art. 1º (%s) - o indulto do crime não impeditivo só depois de 2/3 da pena do impeditivo (art. 7º, p. ú.)" % crimes_curto(imp_conc))
            else:
                nao.append("XIV e XV: não se aplicam - exigem crime contra o patrimônio sem violência ou grave ameaça")
            verificar.append("XVI: saúde/deficiência - não aferível pelo RSPE (laudo médico)")
            # ordena por inciso
            ordem_inc = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI"]
            def _k(t):
                n = t.split(":")[0].split(" ")[0]
                return ordem_inc.index(n) if n in ordem_inc else 99
            possiveis.sort(key=_k); verificar.sort(key=_k); nao.sort(key=_k)

            return possiveis, verificar, nao, frac, tem, fmt_fr, _k

        def concluir(possiveis, verificar, nao, pena_total, cumprido, remanescente, frac, tem, fmt_fr, _k, cump_fonte):
            # art. 6º: só a sanção reconhecida em juízo impede; pendente, regressão ou perda sem falta datada ficam a verificar
            if falta_firme:
                aviso = "FALTA nos 12 meses (art. 6º): " + "; ".join(falta_firme) + (("; a verificar: " + "; ".join(falta_verif)) if falta_verif else "")
            elif falta_verif:
                aviso = "falta a verificar (art. 6º: só impede se a sanção for reconhecida em juízo; STJ, Tema 1195): " + "; ".join(falta_verif)
            else:
                aviso = ""
            ressalvas = []
            # baixa dada na Auditoria ao alerta de livramento incerto = livramento confirmado (vale também aqui)
            lc_duvida = bool(lc and not campos.get("_lc_confirmado") and duvidas_livramento(campos, eventos, incidentes))
            if lc_duvida:
                ressalvas.append(("livramento a confirmar", "livramento condicional com situação incerta no RSPE (ver Auditoria)"))
            vd_prov = [v[1] for v in (violencia_domestica(c) for c in ativos) if v and v[0] == "provavel"]
            if vd_prov:
                # art. 1º, XVII (violência contra a mulher): só se confirma com a vítima - nem nega, nem concede
                ressalvas.append(("confirmar se houve violência contra a mulher (art. 1º, XVII)", "; ".join(dict.fromkeys(vd_prov))))
            if art2:
                ressalvas.append(("conferir recurso da acusação (art. 2º, II)", texto_art2_ii(art2, publicacao)))
            for txt_v in dict.fromkeys(cpm):
                ressalvas.append(("conferir o crime militar (art. 1º, XIX)" if txt_v.startswith("crime militar") else
                                  "conferir se o tráfico é do caput/§ 1º ou do § 4º (art. 1º, XVIII)" if txt_v.startswith("tráfico") else
                                  "conferir a vítima da lesão (art. 1º, I)", txt_v))
            out[k + "_ressalva"] = "; ".join(x[0] for x in ressalvas)
            if ressalvas:
                # todas as ressalvas vão para o texto, haja ou não inciso atendido
                aviso = "; ".join(t for _, t in ressalvas) + ("; " + aviso if aviso else "")
                if possiveis:
                    suf = " - " + "; ".join(x[0] for x in ressalvas)
                    verificar = [p + suf for p in possiveis] + verificar
                    possiveis = []
            verificar = sorted(verificar, key=_k)
            # indulto só pelo XIV/XV de parte dos crimes: a pena dos demais segue e a comutação não fica prejudicada
            so_parcial = bool(possiveis) and all(" - alcança as penas de " in p for p in possiveis)
            if possiveis:
                inc = ", ".join(p.split(":")[0].replace(" (parcial)", "") for p in possiveis)
                out[k] = "POSSÍVEL: art. 9º, " + inc + (" | " + aviso if aviso else "")
                out[k + "_status"] = "possivel"
            elif [v for v in verificar if not v.startswith("XVI")]:
                inc = ", ".join(p.split(":")[0] for p in verificar if not p.startswith("XVI") and re.match(r"^[IVX]+(\s+e\s+[IVX]+)?:", p))
                out[k] = "A VERIFICAR: art. 9º, " + inc + (" | " + aviso if aviso else "")
                out[k + "_status"] = "verificar"
            else:
                out[k] = "não atinge (cumprido %s de %s%s%s até %s)" % (
                    dias_para_pena(cumprido), dias_para_pena(pena_total), ", reincidente" if reinc else "", ", VGA" if vga else "", fmt(ref)) + (" | " + aviso if aviso else "")
                out[k + "_status"] = "nao"
            if art2 and out[k].startswith("A VERIFICAR: ") and not possiveis:
                out[k] = out[k].replace("A VERIFICAR: ", "A VERIFICAR (art. 2º, II): ", 1)
            linhas = ["Situação em %s: regime %s%s · %s%s%s" % (
                fmt(ref), regime or "?", " + livramento condicional" if (lc and not regime.lower().startswith("livramento")) else "",
                "reincidente" if reinc else "primário", " · VGA" if vga else "", (" · %s (§ 2º, I: lapsos pela metade)" % pl(idade, "ano", "anos")) if meia else ""),
                "Cumprido em %s: %s (%s) · remanescente %s." % (fmt(ref), dias_para_pena(cumprido), cump_fonte, dias_para_pena(remanescente))]
            todos = [("✔ ", p) for p in possiveis] + [("? ", v) for v in verificar] + [("✘ ", n) for n in nao]
            todos.sort(key=lambda x: _k(x[1]))
            linhas += [a + b for a, b in todos]
            if aviso:
                linhas.append("⚠ " + aviso)
            linhas.append("Não aferíveis pelo RSPE: § 2º, II a VI (filhos, deficiência, justiça restaurativa) - se presentes, os lapsos I a XI caem pela metade; "
                          "art. 10 (indulto especial para mulheres) e art. 11 (comutação para mulheres); art. 1º, § 1º (acordo de colaboração premiada "
                          "afasta indulto e comutação, qualquer que seja o crime); art. 1º, § 3º, II e III (RDD; estabelecimento de segurança máxima: "
                          "em 2024 só o indulto, em 2025 também a comutação) - a verificar nos autos.")
            linhas.append("Multa: indultável e não é óbice - incapacidade econômica presumida para assistido da Defensoria (art. 12, § 2º, I). "
                          "Tráfico privilegiado (art. 33, § 4º) não é impeditivo (STJ Tema 1336; STF Tema 1400).")
            out[k + "_detalhe"] = "\n".join(linhas)
            # números desta análise, para a linha do tempo desenhar o mesmo cálculo (sem refazê-lo)
            out[k + "_num"] = {"pena": pena_total, "cumprido": cumprido, "remanescente": remanescente, "fonte": cump_fonte,
                               "reinc": bool(reinc), "vga": bool(vga), "regime": regime or "", "meia": bool(meia),
                               "falta_firme": list(falta_firme), "falta_verif": list(falta_verif)}
            # explicação objetiva do cálculo (o que o decreto exige, os números do assistido e a conclusão)
            ex = ["Decreto %s · data de referência %s." % (NUM_DECRETO.get(ano, ano), fmt(ref)),
                  "Na data: regime %s, %s%s. Pena total %s; cumprido %s (%s da pena); falta cumprir %s." % (
                      regime or "não informado", "reincidente" if reinc else "primário", ", crime com violência ou grave ameaça" if vga else "",
                      dias_para_pena(pena_total), dias_para_pena(cumprido), _pct_txt(100.0 * cumprido / pena_total) if pena_total else "?", dias_para_pena(remanescente))]
            if meia:
                ex.append("Idade de %s: as frações caem pela metade (§ 2º, I)." % pl(idade, "ano", "anos"))
            ex += ["✔ " + _explica_inciso(x, pena_total, cumprido) for x in possiveis]
            for x in verificar:
                if x.startswith("XVI"):
                    continue
                e1 = _explica_inciso(x, pena_total, cumprido)
                ex.append(e1 if e1.startswith("Obs.") else "? " + e1 + " Depende de dado que o RSPE não traz.")
            if nao:
                ex.append("Não atendidos: " + "; ".join(_curto_nao(x) for x in sorted(nao, key=_k)) + ".")
            if aviso:
                ex.append("⚠ " + aviso)
            st = out[k + "_status"]
            _incs = lambda xs: ", ".join(x.split(":")[0] for x in xs if re.match(r"^[IVX]+(\s+e\s+[IVX]+)?:", x) and not x.startswith("XVI"))
            ex.append("Conclusão: " + ("indulto possível pelo inciso %s." % _incs(possiveis) if st == "possivel" else
                                      "a verificar (%s)." % _incs(verificar) if st == "verificar" else
                                      "não atinge nenhum inciso nesta data."))
            out[k + "_explica"] = "\n".join(ex)

            # art. 13 - comutação
            f13 = (A("art13_comutacao", "fracao_primario", "1/5"), A("art13_comutacao", "fracao_reincidente", "1/4"))
            ok13 = tem(frac(*f13, par2=False)) or bool(com_ant)
            base13 = "cumprido" if cumprido > remanescente else "remanescente"
            prop13 = A("art13_comutacao", "proporcao_par2", "2/3") if meia else A("art13_comutacao", "proporcao", "1/5")
            # texto da comutação sem indulto (vale também quando o indulto é indeferido ou vedado só a ele)
            # todas as ressalvas valem também para a comutação (inclusive o livramento incerto: a pena cumprida depende dele)
            if ok13 and ressalvas:
                com_txt = "A VERIFICAR: art. 13 (%s do %s) - %s" % (prop13, base13, "; ".join(x[0] for x in ressalvas))
            elif ok13:
                com_txt = "POSSÍVEL: art. 13 (%s do %s)" % (prop13, base13)
            else:
                com_txt = "não atinge (%s até %s)" % (fmt_fr(*f13, par2=False), fmt(ref))
            com_txt += (" | " + aviso if aviso else "")
            out[kc + "_se_indeferido"] = com_txt
            if possiveis and not so_parcial:
                # art. 13, § 5º: a comutação não se aplica a quem preenche os requisitos do indulto (prevalece o mais benéfico)
                out[kc] = "prejudicada: indulto cabível (art. 13, § 5º)"
            elif ok13 and so_parcial:
                out[kc] = ("A VERIFICAR: art. 13 (%s do %s) - sobre a pena dos crimes não alcançados pelo indulto do inciso XV" % (prop13, base13)
                           + (" | " + aviso if aviso else ""))
            else:
                out[kc] = com_txt
            # memória da comutação
            fr13 = frac(*f13, par2=False)
            exig13 = int(pena_total * fr13)
            cl13 = ["Situação em %s: %s · %s" % (fmt(ref), "reincidente" if reinc else "primário", ("pena considerada %s" % dias_para_pena(pena_total)))]
            if True:
                if com_ant and cumprido < exig13:
                    cl13.append("✔ Requisito temporal dispensado: comutação anterior concedida em %s (art. 13, § 2º)." % (
                        com_ant[-1].get("data_decisao") or com_ant[-1].get("data_referencia") or "?"))
                else:
                    cl13.append("%s Requisito: %s da pena cumprida até %s = %s; cumprido %s." % (
                        "✔" if cumprido >= exig13 else "✘", fmt_fr(*f13, par2=False), fmt(ref), dias_para_pena(exig13), dias_para_pena(cumprido)))
                out[kc + "_num"] = {"fracao": str(fr13), "exigido": exig13, "cumprido": cumprido, "ok": bool(ok13), "pena": pena_total}
                if ok13:
                    base = "cumprido" if cumprido > remanescente else "remanescente"
                    prop = A("art13_comutacao", "proporcao_par2", "2/3") if meia else A("art13_comutacao", "proporcao", "1/5")
                    bval = cumprido if base == "cumprido" else remanescente
                    red13 = int(bval * F(prop))
                    out[kc + "_num"].update({"base": base, "base_dias": bval, "prop": str(prop), "reducao": red13,
                                             "antes": remanescente, "depois": max(0, remanescente - red13)})
                    cl13.append("Redução: %s da pena %s (%s) = %s a menos; remanescente passa de %s para %s." % (
                        prop, "cumprida" if base == "cumprido" else "remanescente", dias_para_pena(bval), dias_para_pena(red13), dias_para_pena(remanescente), dias_para_pena(max(0, remanescente - red13))))
                if aviso:
                    cl13.append("⚠ " + aviso)
            if possiveis and not so_parcial:
                cl13.append("Prejudicada: o indulto é cabível e prevalece (art. 13, § 5º).")
            elif so_parcial:
                cl13.append("O indulto do inciso XV alcança só parte dos crimes; a comutação incide sobre a pena dos demais - recalcular sem as penas indultadas.")
            out[kc + "_detalhe"] = "\n".join(cl13)
            out[kc + "_explica"] = "\n".join(["Decreto %s, art. 13 · data de referência %s. Exige %s da pena cumprida (primário) ou %s (reincidente) e reduz a pena em %s%s." % (
                NUM_DECRETO.get(ano, ano), fmt(ref), f13[0], f13[1], A("art13_comutacao", "proporcao", "1/5"),
                (" (%s no § 2º)" % A("art13_comutacao", "proporcao_par2", "2/3")))] + cl13)

        def rotulo(txt, prefixo):
            return txt.replace("POSSÍVEL: ", "POSSÍVEL (%s): " % prefixo, 1) if txt.startswith("POSSÍVEL: ") else txt

        if not imped or (imp_sup and not imp_est):
            # sem impeditivo, ou só hediondez posterior ao fato: análise da pena toda
            res = avaliar(pena_total, cumprido, remanescente, vga, patrimonial, ativos)
            concluir(*res[:3], pena_total, cumprido, remanescente, *res[3:], cump_fonte)
            if imp_sup:
                nomes_sup = crimes_curto(imp_sup)
                nota = ("Hediondez posterior ao fato (%s): o STJ afere a hediondez na data do decreto e veda o benefício; "
                        "pela irretroatividade concedem o STF (2ª Turma, RHC 267.297 AgR e HC 273.296 AgR; monocráticas) e a 2ª Câmara Criminal do TJMS; "
                        "em sentido contrário, a 1ª Turma do STF afere na data do decreto (RHC 273.867 AgR, 24/08/2026)." % nomes_sup)
                out[k] = rotulo(out[k], "tese: hediondez superveniente")
                if out[kc].startswith("POSSÍVEL: "):
                    out[kc] = rotulo(out[kc], "tese: hediondez superveniente")
                out[k + "_detalhe"] = "⚠ " + nota + "\n" + out[k + "_detalhe"]
                out[k + "_explica"] = "⚠ " + nota + "\n" + out.get(k + "_explica", "")
                out[kc + "_detalhe"] = "⚠ " + nota + "\n" + out.get(kc + "_detalhe", "")
                # pela corrente do STJ: art. 7º, p. ú. (só os crimes não impeditivos, depois de 2/3 do impeditivo)
                if livres:
                    pena_imp = sum(pena_para_dias(c.get("pena_imposta")) or 0 for c in imp_sup)
                    exig = int(pena_imp * 2 / 3)
                    if cumprido >= exig:
                        cl = cumprido - exig
                        pena_liv = max(1, pena_total - pena_imp)
                        r2 = avaliar(pena_liv, cl, max(0, pena_liv - cl), any(c.get("vga") == "S" for c in livres), all(crime_patrimonial(c) for c in livres), livres)
                        inc2 = ", ".join(x.split(":")[0] for x in r2[0])
                        f13 = (A("art13_comutacao", "fracao_primario", "1/5"), A("art13_comutacao", "fracao_reincidente", "1/4"))
                        com2 = r2[4](r2[3](*f13, par2=False))
                        out[k + "_detalhe"] += ("\nPela corrente do STJ (art. 7º, p. ú.): 2/3 do impeditivo cumpridos (%s de %s); crimes não impeditivos (%s, pena %s, "
                                                "%s cumpridos além dos 2/3): %s; comutação deles (art. 13, exige %s) %s." % (
                            dias_para_pena(exig), dias_para_pena(pena_imp), crimes_curto(livres), dias_para_pena(pena_liv), dias_para_pena(cl),
                            ("indulto pelo art. 9º, " + inc2) if inc2 else "nenhum inciso de indulto atingido", r2[5](*f13, par2=False), "possível" if com2 else "não atingida"))
                    else:
                        out[k + "_detalhe"] += ("\nPela corrente do STJ: vedado; o art. 7º, p. ú. só libera os crimes não impeditivos depois de 2/3 do impeditivo (%s de %s; cumprido %s)." % (
                            dias_para_pena(exig), dias_para_pena(pena_imp), dias_para_pena(cumprido)))
        else:
            # art. 7º, p. ú.: em concurso, os crimes NÃO impeditivos podem ser indultados/comutados depois de 2/3 da pena do impeditivo;
            # o tempo cumprido além desses 2/3 conta para os crimes não impeditivos
            pena_imp = sum(pena_para_dias(c.get("pena_imposta")) or 0 for c in imp_c)
            exig = int(pena_imp * 2 / 3)
            nomes = crimes_curto(livres)
            out[k + "_imp"] = {"pena_imp": pena_imp, "exigido": exig, "fracao": "2/3", "cumprido_total": cumprido}
            cab = "Crime impeditivo: " + "; ".join(imped)
            if cumprido < exig:
                out[k] = "VEDADO (art. 1º) · art. 7º, p. ú.: faltam %s para 2/3 do impeditivo" % dias_para_pena(exig - cumprido)
                out[k + "_status"] = "vedado"
                out[kc] = "VEDADA (art. 1º)"
                out[k + "_detalhe"] = cab + ("\nArt. 7º, p. ú.: os crimes não impeditivos (%s) só depois de cumpridos 2/3 da pena dos impeditivos (%s de %s); cumprido em %s: %s. "
                                             "Os 2/3 se aferem sobre a pena do impeditivo, à parte (STJ, HC 1.066.254, 6ª T., 18/03/2026)." % (
                    nomes, dias_para_pena(exig), dias_para_pena(pena_imp), fmt(ref), dias_para_pena(cumprido)))
                continue
            cl = cumprido - exig
            pena_liv = max(1, pena_total - pena_imp)
            res = avaliar(pena_liv, cl, max(0, pena_liv - cl), any(c.get("vga") == "S" for c in livres), all(crime_patrimonial(c) for c in livres), livres)
            concluir(*res[:3], pena_liv, cl, max(0, pena_liv - cl), *res[3:],
                     "tempo cumprido além de 2/3 do impeditivo: %s de %s cumpridos em %s, menos %s (2/3 de %s)" % (
                         dias_para_pena(cl), dias_para_pena(cumprido), fmt(ref), dias_para_pena(exig), dias_para_pena(pena_imp)))
            out[k] = rotulo(out[k], "crimes não impeditivos, art. 7º, p. ú.")
            if out[kc].startswith("POSSÍVEL: "):
                out[kc] = rotulo(out[kc], "crimes não impeditivos, art. 7º, p. ú.")
            if out[k].startswith("não atinge"):
                out[k] = "não atinge: crimes não impeditivos (art. 7º, p. ú.)" + (" | " + out[k].split(" | ", 1)[1] if " | " in out[k] else "")
            out[kc + "_detalhe"] = ("Art. 7º, p. ú.: comutação só da pena dos crimes não impeditivos (%s), com o tempo cumprido além de 2/3 do impeditivo.\n" % nomes) + out.get(kc + "_detalhe", "")
            out[k + "_detalhe"] = (cab + "\nArt. 7º, p. ú.: 2/3 da pena dos impeditivos cumpridos (%s de %s; aferidos à parte - STJ, HC 1.066.254, 6ª T., 18/03/2026). A análise abaixo usa só os crimes não impeditivos (%s): pena %s." % (
                dias_para_pena(exig), dias_para_pena(pena_imp), nomes, dias_para_pena(pena_liv)) + "\n" + out[k + "_detalhe"])
        if orcrim_so_indulto and not str(out.get(k, "")).startswith("VEDADO"):
            out[k] = "VEDADO (art. 1º, § 3º, I)"
            out[k + "_status"] = "vedado"
            out[k + "_detalhe"] = ("Art. 1º, § 3º, I, do Decreto 12.338/2024: o indulto não alcança integrante de facção com função de liderança ou participação relevante "
                                   "em organização criminosa. O § 3º de 2024 trata só do indulto: a comutação segue analisada.\n" + (out.get(k + "_detalhe") or ""))
            if str(out.get(kc, "")).startswith("prejudicada"):
                # a comutação volta com o próprio texto (falta do art. 6º e ressalvas incluídas)
                out[kc] = out.get(kc + "_se_indeferido") or out[kc]
                out[kc + "_detalhe"] = (out.get(kc + "_detalhe") or "").replace(
                    "Prejudicada: o indulto é cabível e prevalece (art. 13, § 5º).",
                    "Indulto vedado pelo art. 1º, § 3º, I (em 2024, só o indulto): a comutação não fica prejudicada.")
                out[kc + "_explica"] = (out.get(kc + "_explica") or "").replace(
                    "Prejudicada: o indulto é cabível e prevalece (art. 13, § 5º).",
                    "Indulto vedado pelo art. 1º, § 3º, I (em 2024, só o indulto): a comutação não fica prejudicada.")
    # fato posterior à data do decreto, ou condenação sem trânsito na data: a análise acima usou só as demais penas
    for ano, (post, nomes_post, p_post) in notas_post.items():
        k, kc = "indulto_%s" % ano, "comutacao_%s" % ano
        ref = DECRETOS[ano]
        fatos = [c for c in post if (to_date(c.get("data_infracao") or "") or date.min) > ref]
        semtr = [c for c in post if c not in fatos]
        pub = DECRETOS_PUB.get(ano) or ref
        partes = []
        if fatos:
            partes.append("fato posterior a %s (%s): o decreto não alcança essa pena, que segue em execução; ela não impede o indulto nem a comutação "
                          "das penas anteriores (art. 7º: penas somadas até %s; art. 6º, p. ú.; STJ, HC 190.963)" % (
                              fmt(ref), "; ".join("%s, fato de %s" % (crimes_curto([c]), c.get("data_infracao")) for c in fatos), fmt(ref)))
        if semtr:
            partes.append("sentença posterior à publicação do decreto (%s: %s): não havia condenação na data, a pena não entra na soma do art. 7º "
                          "e segue em execução (STJ, AgRg no HC 441.551; AgRg no HC 919.210)" % (fmt(pub), "; ".join(
                              "%s, sentença de %s" % (crimes_curto([c]), c.get("data_sentenca")) for c in semtr)))
        nota = ("Fora da soma (%s): " % dias_para_pena(p_post)) + "; ".join(partes) + ". Análise feita só com as demais penas."
        for kk in (k + "_detalhe", k + "_explica", kc + "_detalhe", kc + "_explica"):
            if kk in out:
                out[kk] = "⚠ " + nota + "\n" + (out.get(kk) or "")
        suf = ""
        if fatos:
            suf += " | fato posterior a %s (%s): pena segue em execução" % (fmt(ref), crimes_curto(fatos))
        if semtr:
            suf += " | sentença posterior a %s (%s): fora da soma" % (fmt(pub), crimes_curto(semtr))
        for kk in (k, kc):
            if kk in out and out[kk] and not out[kk].startswith("não se aplica"):
                out[kk] += suf
    # art. 6º: falta grave com sanção reconhecida em juízo nos 12 meses (até a publicação) -> não cabe o indulto nem a
    # comutação (a declaração fica condicionada à inexistência dessa sanção). A falta é conferida aqui, uma vez por decreto,
    # e vale para os dois - qualquer que tenha sido o caminho da triagem (incisos com fração, XV, art. 7º, p. ú.)
    for ano in DECRETOS:
        k, kc = "indulto_%s" % ano, "comutacao_%s" % ano
        ref_a = DECRETOS[ano]
        ff, _fv = falta_art6(incidentes, ref_a, eventos, DECRETOS_PUB.get(ano) or ref_a)
        if not ff:
            continue
        faltas_txt = "; ".join(ff)
        txt = out.get(k) or ""
        triagem = txt.split(" | ")[0]
        nota = ("✘ Art. 6º: falta grave com sanção reconhecida nos 12 meses anteriores a 25/12/%s (%s): a declaração do indulto e da comutação "
                "fica condicionada à inexistência dessa sanção - não cabe." % (ano, faltas_txt))
        for kk, nome in ((k, "a triagem"), (kc, "a comutação")):
            t = out.get(kk) or ""
            if not t or t.upper().startswith(("VEDAD", "NÃO SE APLICA", "CONCEDID", "INDEFERID", "NÃO CABE", "DECRETO SEM", "EXCLU")):
                continue
            out[kk] = "NÃO CABE (art. 6º): falta grave com sanção reconhecida nos 12 meses - %s" % faltas_txt
            out[kk + "_status"] = "nao"
            n2 = nota + " Sem a falta, %s seria: %s." % (nome, t.split(" | ")[0])
            for dk in (kk + "_detalhe", kk + "_explica"):
                if dk in out or dk.endswith("_detalhe"):
                    out[dk] = (out.get(dk) or "").replace("Prejudicada: o indulto é cabível e prevalece (art. 13, § 5º).", "") + "\n" + n2
    for ano, nota in notas_tr.items():
        for kk in ("indulto_%s_detalhe" % ano, "comutacao_%s_detalhe" % ano):
            if kk in out:
                out[kk] = (out.get(kk) or "") + "\n? " + nota
    return out


def e_remicao_concedida(i):
    """Incidente de remição concedida: exclui perda de dias remidos e remição não concedida ou pendente."""
    t = (i.get("tipo") or "").upper()
    if "REMI" not in t or re.search(r"PERD|REVOG", t):
        return False
    return (i.get("situacao") or "CONCEDIDO") == "CONCEDIDO"


def falta_art6(incidentes, ref, eventos=None, publicacao=None):
    """(firmes, a_verificar): textos das faltas do art. 6º com sanção reconhecida e das que dependem de conferência.
    A janela vai até a publicação do decreto: falta posterior não impede (art. 6º, p. ú.)."""
    ach = indicios_falta(incidentes, ref, eventos=eventos, ate=publicacao)
    return [t for t, f in ach if f], [t for t, f in ach if not f]


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
        "rg": _campo_rg(cab),
        "nome_mae": campo(cab, "Nome da Mãe"),
        "data_nascimento": _nascimento(cab),
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
    _completar_processos_eventos(crimes, eventos, incidentes)
    return derivar(r, crimes, eventos, incidentes)


def reprocessar(r):
    """Refaz a análise de um registro já gravado na base (leitura do PDF preservada), com as regras desta versão."""
    _completar_processos_eventos(r.get("_crimes", []), r.get("_eventos", []), r.get("_incidentes", []))
    return derivar(r, r.get("_crimes", []), r.get("_eventos", []), r.get("_incidentes", []))


def derivar(r, crimes, eventos, incidentes):
    """Tudo o que o programa conclui a partir do que foi lido do RSPE. Roda na importação e de novo ao abrir a base,
    para que cada versão nova valha também para quem já estava importado."""
    hoje = to_date(r.get("data_geracao_rspe") or "") or date.today()
    inc_conc = [i for i in incidentes if i.get("situacao") == "CONCEDIDO"]
    inc_neg = [i for i in incidentes if i.get("situacao") == "NÃO CONCEDIDO"]
    inc_pend = [i for i in incidentes if i.get("situacao") == "PENDENTE"]
    for c in crimes:
        if c.get("artigo_inferido"):  # artigo reconhecido pela descrição: refaz com a regra atual
            c["artigo"] = c.get("artigo_rspe") or "Não informado"
            c.pop("artigo_inferido", None)
            c.pop("lei_do_tempo", None)
        c.setdefault("artigo_rspe", c.get("artigo", ""))
        inferir_artigo(c)
        c["hediondo_ou_equiparado"] = "S" if e_hediondo(c) else "N"
    aplicar_extincoes(r, crimes, incidentes)  # antes de tudo: o resto da análise considera só os crimes ativos

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

    r.update(situacao_execucao(r, eventos, incidentes, crimes, hoje))
    r.update(faltas(r, eventos, incidentes, hoje))
    r.update(analise_decretos(r, crimes, eventos, incidentes, hoje))
    r.update(analise_decreto_2022(r, crimes, eventos, incidentes))
    aplicar_decisoes_decretos(r, incidentes)
    r["eventos"] = " | ".join("%s/%s %s" % (e["tipo"], e["motivo"], e["data"]) for e in eventos)

    r["_crimes"] = crimes
    r["_incidentes"] = incidentes
    r["_eventos"] = eventos
    return r


def _completar_processos_eventos(crimes, eventos, incidentes):
    for x in list(eventos) + list(incidentes):
        if x.get("processos"):
            x["processos"] = completar_processos(x["processos"], crimes)


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
    ap.add_argument("--relatorios", action="store_true", help="gera um relatório individual em PDF por assistido")
    ap.add_argument("--relatorio-geral", action="store_true", help="gera o relatório geral em PDF do lote")
    ap.add_argument("--sem-planilha", action="store_true", help="não grava planilha, CSV nem JSON (só os relatórios)")
    ap.add_argument("--anonimo", action="store_true", help="fila de prioridade do relatório geral sem nomes")
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

    if registros and not args.sem_planilha:
        gravar_xlsx(registros, saida)
        base = os.path.splitext(saida)[0]
        if not args.sem_csv:
            gravar_csv(registros, base + ".csv")
        if not args.sem_json:
            gravar_json(registros, base + ".json")
        print("-" * 70)
        print("%s. Planilha: %s" % (pl(len(registros), "RSPE processado", "RSPE processados"), saida))
    if registros and (args.relatorios or args.relatorio_geral):
        import rspe_view as rv
        import rspe_relatorio as rrel
        modelos = []
        for r in registros:
            m = rv.modelo(r)
            m["_bruto"] = r
            modelos.append(m)
        destino, n, falhas = rrel.gerar(modelos, os.path.dirname(os.path.abspath(saida)), "Lote",
                                        individual=args.relatorios, geral=args.relatorio_geral, nominal=not args.anonimo)
        print("Relatórios em %s (%s)" % (destino, pl(n, "individual", "individuais")))
        for e in falhas:
            print("Falha no relatório: " + e)
    for e in erros:
        print("Falhou: " + e)

    if modo_gui:
        from tkinter import messagebox
        msg = "%s.\nPlanilha: %s" % (pl(len(registros), "RSPE processado", "RSPE processados"), saida)
        if erros:
            msg += "\n\nFalhas:\n" + "\n".join(erros)
        messagebox.showinfo("RSPE Scraper", msg)


if __name__ == "__main__":
    main()
